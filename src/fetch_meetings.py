"""Congress.gov committee-meeting API client.

Fetches meeting data from the committee-meeting API, extracting
YouTube video URLs from the ``videos`` field when present.

Two fetch strategies:
1. **By eventID** (``fetch_all_meeting_videos``): looks up meetings for
   hearings that already have an eventID in their hearing detail record.
2. **Full list** (``fetch_all_meetings_for_congress``): fetches every
   meeting from the list endpoint, then fetches each detail.  This
   discovers eventIDs for hearings that lack them, using the
   ``hearingTranscript.jacketNumber`` link to join back to hearings.
"""

import json
import re
import time
from pathlib import Path

import httpx

from src.config import (
    CONGRESS_API_BASE,
    CONGRESS_API_RATE_LIMIT,
    CONGRESS_GOV_API_KEY,
    DATA_DIR,
)

RAW_MEETINGS_DIR = DATA_DIR / "raw" / "meetings"
RAW_MEETINGS_DIR.mkdir(parents=True, exist_ok=True)

_YT_VIDEO_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})"
)


def _meeting_cache_path(congress: int, event_id: str) -> Path:
    return RAW_MEETINGS_DIR / f"meeting_{congress}_{event_id}.json"


def fetch_meeting(
    congress: int,
    event_id: str,
    *,
    client: httpx.Client | None = None,
    force_refresh: bool = False,
) -> dict | None:
    """Fetch a single committee-meeting record by eventID.

    Returns the parsed JSON response, or None on 404/error.
    """
    cache_path = _meeting_cache_path(congress, event_id)
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text())

    url = f"{CONGRESS_API_BASE}/committee-meeting/{congress}/house/{event_id}"
    params = {"api_key": CONGRESS_GOV_API_KEY, "format": "json"}

    def _do_request(c: httpx.Client) -> dict | None:
        for attempt in range(5):
            try:
                resp = c.get(url, params=params)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
                cache_path.write_text(json.dumps(data, indent=2))
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503) and attempt < 4:
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)
                else:
                    raise
            except (httpx.ReadTimeout, httpx.ConnectTimeout):
                if attempt < 4:
                    time.sleep(2 ** (attempt + 1))
                else:
                    raise
        return None

    if client:
        return _do_request(client)

    with httpx.Client(timeout=30) as c:
        return _do_request(c)


def extract_youtube_urls(meeting: dict) -> list[str]:
    """Extract YouTube video URLs from a committee-meeting response."""
    cm = meeting.get("committeeMeeting", meeting)
    videos = cm.get("videos", [])
    urls = []
    for v in videos:
        url = v.get("url", "")
        if _YT_VIDEO_RE.search(url):
            urls.append(url)
    return urls


def extract_youtube_video_ids(meeting: dict) -> list[str]:
    """Extract YouTube video IDs from a committee-meeting response."""
    urls = extract_youtube_urls(meeting)
    ids = []
    for url in urls:
        m = _YT_VIDEO_RE.search(url)
        if m:
            ids.append(m.group(1))
    return ids


def fetch_all_meeting_videos(
    hearings: list[dict],
    *,
    force_refresh: bool = False,
) -> dict[str, list[str]]:
    """Fetch committee-meeting data for all hearings with eventIDs.

    Returns a dict mapping eventID -> list of YouTube video IDs found
    in the API response.
    """
    # Collect unique (congress, event_id) pairs
    to_fetch: list[tuple[int, str]] = []
    seen: set[str] = set()
    for h in hearings:
        event_id = h.get("event_id")
        congress = h.get("congress")
        if event_id and event_id not in seen:
            seen.add(str(event_id))
            to_fetch.append((congress, str(event_id)))

    if not to_fetch:
        return {}

    results: dict[str, list[str]] = {}

    with httpx.Client(timeout=30) as client:
        for i, (congress, event_id) in enumerate(to_fetch):
            meeting = fetch_meeting(
                congress, event_id, client=client, force_refresh=force_refresh
            )
            if meeting:
                video_ids = extract_youtube_video_ids(meeting)
                results[event_id] = video_ids

            if (i + 1) % 100 == 0:
                print(f"  Fetched {i + 1}/{len(to_fetch)} meetings...")

            # Rate limit (skip if cached)
            cache_path = _meeting_cache_path(congress, event_id)
            if not cache_path.exists() or force_refresh:
                time.sleep(CONGRESS_API_RATE_LIMIT)

    with_videos = sum(1 for v in results.values() if v)
    print(
        f"  Meetings fetched: {len(results)} | "
        f"With YouTube links: {with_videos} ({with_videos * 100 // max(len(results), 1)}%)"
    )

    return results


# ---------------------------------------------------------------------------
# Full meeting list approach
# ---------------------------------------------------------------------------

def _meeting_list_cache_path(congress: int) -> Path:
    return RAW_MEETINGS_DIR / f"meeting_list_{congress}.json"


def _fetch_meeting_list_page(
    client: httpx.Client,
    congress: int,
    offset: int,
    page_size: int,
) -> dict | None:
    """Fetch one page of the meeting list, retrying with smaller pages on 500."""
    for size in [page_size, 50, 7]:
        params = {
            "api_key": CONGRESS_GOV_API_KEY,
            "format": "json",
            "limit": size,
            "offset": offset,
        }
        for attempt in range(5):
            try:
                resp = client.get(
                    f"{CONGRESS_API_BASE}/committee-meeting"
                    f"/{congress}/house",
                    params=params,
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 502, 503) and attempt < 4:
                    time.sleep(2 ** (attempt + 1))
                elif e.response.status_code == 500:
                    if size > 7:
                        print(f"    500 at limit={size}, "
                              f"trying smaller page size...")
                        break  # try smaller page size
                    elif attempt < 4:
                        time.sleep(2 ** (attempt + 1))
                    else:
                        raise
                else:
                    raise
            except (httpx.ReadTimeout, httpx.ConnectTimeout):
                if attempt < 4:
                    time.sleep(2 ** (attempt + 1))
                else:
                    raise
    return None


def fetch_meeting_list(
    congress: int,
    *,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch all committee-meeting stubs for a congress from the list endpoint.

    Returns a list of stub dicts, each containing at minimum ``eventId``.
    """
    cache_path = _meeting_list_cache_path(congress)
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text())

    stubs: list[dict] = []
    offset = 0
    page_size = 250

    with httpx.Client(timeout=30) as client:
        while True:
            data = _fetch_meeting_list_page(
                client, congress, offset, page_size
            )
            if data is None:
                break
            page = data.get("committeeMeetings", [])
            if not page:
                break
            stubs.extend(page)
            offset += len(page)

            if not data.get("pagination", {}).get("next"):
                break
            time.sleep(CONGRESS_API_RATE_LIMIT)

    cache_path.write_text(json.dumps(stubs, indent=2))
    return stubs


def fetch_all_meetings_for_congress(
    congress: int,
    *,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch the full detail for every committee meeting in a congress.

    Uses the list endpoint to discover eventIDs, then fetches each detail.
    Returns a list of full meeting detail dicts.
    """
    stubs = fetch_meeting_list(congress, force_refresh=force_refresh)
    print(f"  Meeting stubs: {len(stubs)}")

    details: list[dict] = []
    with httpx.Client(timeout=30) as client:
        for i, stub in enumerate(stubs):
            event_id = str(stub.get("eventId", ""))
            if not event_id:
                continue

            meeting = fetch_meeting(
                congress, event_id,
                client=client, force_refresh=force_refresh,
            )
            if meeting:
                details.append(meeting)

            if (i + 1) % 200 == 0:
                print(f"  Fetched {i + 1}/{len(stubs)} meeting details...")

            # Rate limit only for uncached
            cache_path = _meeting_cache_path(congress, event_id)
            if not cache_path.exists() or force_refresh:
                time.sleep(CONGRESS_API_RATE_LIMIT)

    return details


def extract_jacket_numbers(meeting: dict) -> list[str]:
    """Extract hearing jacket numbers from a meeting's hearingTranscript."""
    cm = meeting.get("committeeMeeting", meeting)
    transcripts = cm.get("hearingTranscript", [])
    return [
        str(t["jacketNumber"])
        for t in transcripts
        if t.get("jacketNumber")
    ]


def extract_committee_codes(meeting: dict) -> list[str]:
    """Extract committee system codes from a committee-meeting response."""
    cm = meeting.get("committeeMeeting", meeting)
    return [
        c.get("systemCode", "")
        for c in cm.get("committees", [])
        if c.get("systemCode")
    ]


def build_jacket_video_map(
    meetings: list[dict],
) -> dict[str, list[str]]:
    """Build a mapping from jacket number to YouTube video IDs.

    For hearings that lack an eventID in their hearing detail,
    this provides an alternate path to discover whether the
    committee-meeting API already has a video link.
    """
    full_map = build_jacket_meeting_map(meetings)
    return {jacket: info["video_ids"] for jacket, info in full_map.items()}


def build_jacket_meeting_map(
    meetings: list[dict],
) -> dict[str, dict]:
    """Build a rich mapping from jacket number to meeting API data.

    Returns per jacket: video_ids, committee_codes, and event_id from
    the committee-meeting API. Used to cross-reference hearing data.
    """
    result: dict[str, dict] = {}
    for meeting in meetings:
        cm = meeting.get("committeeMeeting", meeting)
        video_ids = extract_youtube_video_ids(meeting)
        committee_codes = extract_committee_codes(meeting)
        event_id = str(cm.get("eventId", ""))

        for jacket in extract_jacket_numbers(meeting):
            if jacket not in result:
                result[jacket] = {
                    "video_ids": video_ids,
                    "committee_codes": committee_codes,
                    "event_id": event_id,
                }
            else:
                # Merge video IDs
                if video_ids:
                    existing = set(result[jacket]["video_ids"])
                    result[jacket]["video_ids"] = list(existing | set(video_ids))
                # Merge committee codes
                if committee_codes:
                    existing = set(result[jacket]["committee_codes"])
                    result[jacket]["committee_codes"] = list(
                        existing | set(committee_codes)
                    )
    return result
