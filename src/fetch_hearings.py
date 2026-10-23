"""Congress.gov API client for fetching House hearings."""

import json
import time
from pathlib import Path

import httpx
from thefuzz import fuzz

from src.config import (
    CONGRESS_API_BASE,
    CONGRESS_API_PAGE_SIZE,
    CONGRESS_API_RATE_LIMIT,
    CONGRESS_GOV_API_KEY,
    EVENT_ID_BACKFILL_TITLE_RATIO,
    RAW_HEARINGS_DIR,
    TARGET_CONGRESS,
)
from src.fetch_meetings import _retry_wait
from src.match import normalize_title


def _hearing_cache_path(congress: int) -> Path:
    return RAW_HEARINGS_DIR / f"hearings_{congress}.json"


def fetch_all_hearings(
    congress: int = TARGET_CONGRESS,
    *,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch all House hearings for a given congress from the Congress.gov API.

    Results are cached locally to avoid repeated API calls.
    """
    cache_path = _hearing_cache_path(congress)
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text())

    hearings = []
    offset = 0

    with httpx.Client(timeout=30) as client:
        while True:
            params = {
                "api_key": CONGRESS_GOV_API_KEY,
                "limit": CONGRESS_API_PAGE_SIZE,
                "offset": offset,
                "format": "json",
            }

            resp = client.get(
                f"{CONGRESS_API_BASE}/hearing/{congress}/house",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            page_hearings = data.get("hearings", [])
            if not page_hearings:
                break

            hearings.extend(page_hearings)
            offset += CONGRESS_API_PAGE_SIZE

            # Check if there are more pages
            pagination = data.get("pagination", {})
            if not pagination.get("next"):
                break

            time.sleep(CONGRESS_API_RATE_LIMIT)

    cache_path.write_text(json.dumps(hearings, indent=2))
    return hearings


def fetch_hearing_detail(
    congress: int,
    jacket_number: str,
    *,
    force_refresh: bool = False,
) -> dict:
    """Fetch detailed metadata for a single hearing."""
    cache_path = RAW_HEARINGS_DIR / f"hearing_{congress}_{jacket_number}.json"
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text())

    resp = httpx.get(
        f"{CONGRESS_API_BASE}/hearing/{congress}/house/{jacket_number}",
        params={"api_key": CONGRESS_GOV_API_KEY, "format": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    cache_path.write_text(json.dumps(data, indent=2))
    return data


def normalize_hearing(hearing: dict) -> dict:
    """Extract and normalize key fields from a hearing record."""
    # Handle nested structure — hearing may be at top level or under "hearing" key
    h = hearing.get("hearing", hearing)

    committees = h.get("committees", [])
    committee_codes = [c.get("systemCode", "") for c in committees]
    committee_names = [c.get("name", "") for c in committees]

    # Extract dates
    dates = h.get("dates", [])
    hearing_dates = []
    for d in dates:
        if isinstance(d, dict):
            hearing_dates.append(d.get("date", "")[:10])  # YYYY-MM-DD
        elif isinstance(d, str):
            hearing_dates.append(d[:10])

    # Extract eventID from associatedMeeting if present
    event_id = None
    associated = h.get("associatedMeeting", {})
    if associated:
        event_id = associated.get("eventId") or associated.get("eventID")

    return {
        "congress": h.get("congress", TARGET_CONGRESS),
        "jacket_number": h.get("jacketNumber", ""),
        "title": h.get("title", ""),
        "dates": hearing_dates,
        "committee_codes": committee_codes,
        "committee_names": committee_names,
        "event_id": event_id,
        "loc_id": h.get("libraryOfCongressIdentifier"),
        "part": h.get("part"),
        "url": h.get("url", ""),
    }


def _backfill_event_id(hearing: dict, meetings: list[dict]) -> str | None:
    """Borrow an eventID only from a meeting whose title agrees with the hearing's.

    Meetings often list the jackets of other same-day hearings too.
    """
    h_title = normalize_title(hearing.get("title", ""))
    if not h_title:
        return None
    best_id, best_ratio = None, EVENT_ID_BACKFILL_TITLE_RATIO - 1
    for m in meetings:
        ratio = fuzz.token_set_ratio(h_title, normalize_title(m.get("title", "")))
        if m.get("event_id") and ratio > best_ratio:
            best_id, best_ratio = m["event_id"], ratio
    return best_id


def enrich_hearing_with_meeting_data(
    hearing: dict, jacket_meeting_map: dict
) -> dict:
    """Cross-reference a hearing with committee-meeting API data.

    Merges committee codes from both the hearing API and meeting API,
    flags discrepancies, and fills in missing event_id from the meeting map.
    """
    jacket = str(hearing.get("jacket_number", ""))
    meeting_info = jacket_meeting_map.get(jacket)

    if not meeting_info:
        return {
            **hearing,
            "meeting_committee_codes": [],
            "effective_committee_codes": hearing.get("committee_codes", []),
            "committee_code_discrepancy": False,
        }

    meeting_codes = meeting_info.get("committee_codes", [])
    hearing_codes = hearing.get("committee_codes", [])

    # Detect discrepancy: do the parent committee codes differ?
    hearing_parents = {c[:4] for c in hearing_codes if len(c) >= 4}
    meeting_parents = {c[:4] for c in meeting_codes if len(c) >= 4}
    discrepancy = bool(meeting_parents and hearing_parents and meeting_parents != hearing_parents)

    # Effective codes = union of both sources
    effective = list(set(hearing_codes) | set(meeting_codes))

    event_id = hearing.get("event_id") or _backfill_event_id(
        hearing, meeting_info.get("meetings", [])
    )

    return {
        **hearing,
        "event_id": event_id,
        "meeting_committee_codes": meeting_codes,
        "effective_committee_codes": effective,
        "committee_code_discrepancy": discrepancy,
    }


def fetch_all_hearing_details(
    congress: int = TARGET_CONGRESS,
    *,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch detailed metadata for all hearings in a congress.

    Uses the list endpoint to get jacket numbers, then fetches each detail page.
    Results are cached individually per hearing.
    """
    cache_path = RAW_HEARINGS_DIR / f"hearings_{congress}_details.json"
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text())

    stubs = fetch_all_hearings(congress)
    details = []

    with httpx.Client(timeout=30) as client:
        for i, stub in enumerate(stubs):
            jacket = stub.get("jacketNumber", "")
            if not jacket:
                continue

            detail_cache = RAW_HEARINGS_DIR / f"hearing_{congress}_{jacket}.json"
            if detail_cache.exists() and not force_refresh:
                detail = json.loads(detail_cache.read_text())
            else:
                detail = None
                for attempt in range(5):
                    try:
                        resp = client.get(
                            f"{CONGRESS_API_BASE}/hearing/{congress}/house/{jacket}",
                            params={"api_key": CONGRESS_GOV_API_KEY, "format": "json"},
                        )
                        resp.raise_for_status()
                        detail = resp.json()
                        break
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code in (429, 500, 502, 503) and attempt < 4:
                            wait = _retry_wait(e.response.status_code, attempt)
                            print(f"    Retry {attempt + 1} for {jacket}"
                                  f" ({e.response.status_code}), waiting {wait}s...")
                            time.sleep(wait)
                        else:
                            raise
                    except httpx.TransportError:  # timeouts and dropped connections
                        if attempt < 4:
                            wait = 2 ** (attempt + 1)
                            print(f"    Retry {attempt + 1} for {jacket}"
                                  f" (connection), waiting {wait}s...")
                            time.sleep(wait)
                        else:
                            raise
                if detail is None:
                    continue
                detail_cache.write_text(json.dumps(detail, indent=2))
                time.sleep(CONGRESS_API_RATE_LIMIT)

            details.append(detail)

            if (i + 1) % 100 == 0:
                print(f"  Fetched {i + 1}/{len(stubs)} hearing details...")

    cache_path.write_text(json.dumps(details, indent=2))
    return details


def load_normalized_hearings(congress: int = TARGET_CONGRESS) -> list[dict]:
    """Load and normalize all hearings for a congress."""
    raw = fetch_all_hearing_details(congress)
    return [normalize_hearing(h) for h in raw]
