"""Multi-layer matching algorithm for hearings to YouTube videos."""

import re
from datetime import datetime

from thefuzz import fuzz

from src.config import DATE_WINDOW_DAYS, FUZZY_TITLE_THRESHOLD, VIDEO_PUBLISH_SANITY_DAYS


def normalize_title(title: str) -> str:
    """Normalize a hearing/video title for comparison.

    Removes common prefixes, embedded dates, extra whitespace/punctuation,
    and lowercases the result.
    """
    t = title.lower().strip()

    # Strip common hearing prefixes
    prefixes = [
        r"^full committee hearing[:\s]*",
        r"^hearing on[:\s]*",
        r"^markup and[:\s]*",
        r"^markup of[:\s]*",
        r"^hearing entitled[:\s]*",
        r'^hearing[:\s]*["\u201c]',
        r"^subcommittee hearing[:\s]*",
        r"^legislative hearing[:\s]*",
        r"^oversight hearing[:\s]*",
        r"^field hearing[:\s]*",
    ]
    for prefix in prefixes:
        t = re.sub(prefix, "", t)

    # Strip trailing quotes
    t = t.strip('"\u201d')

    # Remove embedded dates like "January 15, 2024" or "01/15/2024"
    t = re.sub(r"\b(?:january|february|march|april|may|june|july|august|"
               r"september|october|november|december)\s+\d{1,2},?\s*\d{4}\b", "", t)
    t = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "", t)

    # Normalize whitespace and punctuation
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t


def parse_date(date_str: str) -> datetime | None:
    """Parse a date string in various formats."""
    formats_and_slices = [
        ("%Y-%m-%dT%H:%M:%SZ", 20),
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%d", 10),
        ("%m/%d/%Y", 10),
    ]
    for fmt, length in formats_and_slices:
        try:
            return datetime.strptime(date_str[:length], fmt)
        except ValueError:
            continue
    return None


def dates_match_exact(hearing_dates: list[str], video_date: str) -> bool:
    """Check if the video date matches any hearing date exactly."""
    v_date = parse_date(video_date)
    if not v_date:
        return False
    v_day = v_date.date()

    for hd in hearing_dates:
        h_date = parse_date(hd)
        if h_date and h_date.date() == v_day:
            return True
    return False


def dates_within_window(
    hearing_dates: list[str], video_date: str, window_days: int = DATE_WINDOW_DAYS
) -> tuple[bool, int]:
    """Check if video date is within +/- window_days of any hearing date.

    Returns (match, min_days_diff).
    """
    v_date = parse_date(video_date)
    if not v_date:
        return False, 999

    min_diff = 999
    for hd in hearing_dates:
        h_date = parse_date(hd)
        if h_date:
            diff = abs((v_date.date() - h_date.date()).days)
            min_diff = min(min_diff, diff)

    return min_diff <= window_days, min_diff


def extract_bill_numbers(text: str) -> set[str]:
    """Extract bill numbers like H.R. 1234, S. 567, H.Res. 89 from text."""
    pattern = r"\b(H\.?\s*R\.?|S\.?|H\.?\s*Res\.?|S\.?\s*Res\.?|H\.?\s*Con\.?\s*Res\.?)\s*(\d+)\b"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return {f"{m[0].replace(' ', '').replace('.', '').upper()}{m[1]}" for m in matches}


def committee_matches(hearing: dict, video: dict, committee_map: dict) -> bool:
    """Check if a video's channel belongs to the hearing's committee.

    Also checks the parent committee channel for subcommittee hearings,
    since subcommittees rarely have their own YouTube channels.
    """
    channel_id = video.get("channel_id", "")
    for code in hearing.get("committee_codes", []):
        committee = committee_map.get(code)
        if committee and channel_id in committee.all_youtube_ids:
            return True
        # Check parent committee (system code with '00' suffix)
        parent_code = code[:4] + "00" if len(code) > 4 else None
        if parent_code and parent_code != code:
            parent = committee_map.get(parent_code)
            if parent and channel_id in parent.all_youtube_ids:
                return True
    return False


def match_layer_1_event_id(hearing: dict, video: dict) -> dict | None:
    """Layer 1: Exact eventID match. Confidence 1.0."""
    event_id = hearing.get("event_id")
    if not event_id:
        return None

    # Check if eventID appears in video description or title
    video_text = f"{video.get('title', '')} {video.get('description', '')}"
    if str(event_id) in video_text:
        return {
            "confidence": 1.0,
            "method": "event_id_exact",
        }
    return None


def dates_match_nearby(hearing_dates: list[str], video_date: str) -> bool:
    """Check if video date is within ±1 day of any hearing date.

    YouTube videos are often published the day after the hearing.
    """
    match, diff = dates_within_window(hearing_dates, video_date, window_days=1)
    return match


def match_layer_2_exact(hearing: dict, video: dict) -> dict | None:
    """Layer 2: Same committee + nearby date + exact normalized title. Confidence 0.95."""
    h_title = normalize_title(hearing.get("title", ""))
    v_title = normalize_title(video.get("title", ""))

    if not h_title or not v_title:
        return None

    if h_title != v_title:
        return None

    if not dates_match_nearby(hearing.get("dates", []), video.get("published_at", "")):
        return None

    return {
        "confidence": 0.95,
        "method": "exact_date_title",
    }


def match_layer_3_fuzzy_title(hearing: dict, video: dict) -> dict | None:
    """Layer 3: Same committee + nearby date + fuzzy title. Confidence 0.70-0.90."""
    if not dates_match_nearby(hearing.get("dates", []), video.get("published_at", "")):
        return None

    h_title = normalize_title(hearing.get("title", ""))
    v_title = normalize_title(video.get("title", ""))

    if not h_title or not v_title:
        return None

    ratio = fuzz.token_sort_ratio(h_title, v_title)
    if ratio < FUZZY_TITLE_THRESHOLD:
        return None

    # Scale confidence: 80% ratio -> 0.70, 100% ratio -> 0.90
    confidence = 0.70 + (ratio - FUZZY_TITLE_THRESHOLD) / (100 - FUZZY_TITLE_THRESHOLD) * 0.20

    return {
        "confidence": round(confidence, 2),
        "method": "fuzzy_title_exact_date",
        "fuzzy_ratio": ratio,
    }


def match_layer_3b_substring(hearing: dict, video: dict) -> dict | None:
    """Layer 3b: Nearby date + one title contains the other. Confidence 0.80-0.88."""
    if not dates_match_nearby(hearing.get("dates", []), video.get("published_at", "")):
        return None

    h_title = normalize_title(hearing.get("title", ""))
    v_title = normalize_title(video.get("title", ""))

    if not h_title or not v_title or len(h_title) < 15 or len(v_title) < 15:
        return None

    # Check if one is a substring of the other
    if h_title in v_title or v_title in h_title:
        # Longer overlap = higher confidence
        overlap = min(len(h_title), len(v_title))
        total = max(len(h_title), len(v_title))
        ratio = overlap / total
        confidence = 0.80 + ratio * 0.08
        return {
            "confidence": round(confidence, 2),
            "method": "substring_nearby_date",
        }
    return None


def match_layer_4_relaxed_date(hearing: dict, video: dict) -> dict | None:
    """Layer 4: Same committee + fuzzy title + date within window. Confidence 0.50-0.75."""
    h_title = normalize_title(hearing.get("title", ""))
    v_title = normalize_title(video.get("title", ""))

    if not h_title or not v_title:
        return None

    ratio = fuzz.token_sort_ratio(h_title, v_title)
    if ratio < FUZZY_TITLE_THRESHOLD:
        return None

    within_window, days_diff = dates_within_window(
        hearing.get("dates", []), video.get("published_at", "")
    )
    if not within_window or days_diff == 0:
        # days_diff == 0 would have been caught by layers 2/3
        return None

    # Scale: closer date + higher ratio = higher confidence
    date_factor = 1.0 - (days_diff / (DATE_WINDOW_DAYS + 1))
    ratio_factor = (ratio - FUZZY_TITLE_THRESHOLD) / (100 - FUZZY_TITLE_THRESHOLD)
    confidence = 0.50 + 0.25 * (date_factor * 0.5 + ratio_factor * 0.5)

    return {
        "confidence": round(confidence, 2),
        "method": "fuzzy_title_relaxed_date",
        "fuzzy_ratio": ratio,
        "days_diff": days_diff,
    }


def match_layer_5_description(hearing: dict, video: dict) -> dict | None:
    """Layer 5: Description-based matching (bill numbers, witness names). Confidence 0.40-0.65."""
    h_title = hearing.get("title", "")
    v_desc = video.get("description", "")
    v_title = video.get("title", "")

    if not v_desc and not v_title:
        return None

    # Check for shared bill numbers
    h_bills = extract_bill_numbers(h_title)
    v_bills = extract_bill_numbers(f"{v_title} {v_desc}")

    if not h_bills or not v_bills:
        return None

    shared = h_bills & v_bills
    if not shared:
        return None

    # More shared bill numbers = higher confidence
    overlap_ratio = len(shared) / max(len(h_bills), 1)

    # Check date proximity as a secondary signal
    within_window, days_diff = dates_within_window(
        hearing.get("dates", []), video.get("published_at", ""), window_days=7
    )
    date_bonus = 0.10 if within_window else 0.0

    confidence = min(0.40 + overlap_ratio * 0.15 + date_bonus, 0.65)

    return {
        "confidence": round(confidence, 2),
        "method": "description_bills",
        "shared_bills": list(shared),
        "days_diff": days_diff if within_window else None,
    }


def find_best_match(hearing: dict, videos: list[dict], committee_map: dict) -> dict | None:
    """Run all matching layers against candidate videos and return the best match."""
    best = None

    for video in videos:
        # Filter to videos from the hearing's committee
        if not committee_matches(hearing, video, committee_map):
            continue

        # Try layers in order of confidence (highest first)
        for layer_fn in [
            match_layer_1_event_id,
            match_layer_2_exact,
            match_layer_3_fuzzy_title,
            match_layer_3b_substring,
            match_layer_4_relaxed_date,
            match_layer_5_description,
        ]:
            result = layer_fn(hearing, video)
            if result:
                result["video"] = video
                if best is None or result["confidence"] > best["confidence"]:
                    best = result
                break  # Use highest-confidence layer for this video

    return best


def _passes_date_sanity(hearing: dict, video: dict) -> bool:
    """Check that a match isn't wildly off by date (>VIDEO_PUBLISH_SANITY_DAYS)."""
    hearing_dates = hearing.get("dates", [])
    video_date = video.get("published_at", "")
    if not hearing_dates or not video_date:
        return True  # can't check, allow it

    v_date = parse_date(video_date)
    if not v_date:
        return True

    for hd in hearing_dates:
        h_date = parse_date(hd)
        if h_date and abs((v_date - h_date).days) <= VIDEO_PUBLISH_SANITY_DAYS:
            return True
    return False


def find_best_match_with_sanity(
    hearing: dict, videos: list[dict], committee_map: dict
) -> dict | None:
    """Run all matching layers with date sanity checking."""
    best = None

    for video in videos:
        if not committee_matches(hearing, video, committee_map):
            continue

        for layer_fn in [
            match_layer_1_event_id,
            match_layer_2_exact,
            match_layer_3_fuzzy_title,
            match_layer_3b_substring,
            match_layer_4_relaxed_date,
            match_layer_5_description,
        ]:
            result = layer_fn(hearing, video)
            if result:
                # Apply date sanity check for lower-confidence layers
                if result["confidence"] < 0.95 and not _passes_date_sanity(hearing, video):
                    break  # skip this video entirely
                result["video"] = video
                if best is None or result["confidence"] > best["confidence"]:
                    best = result
                break

    return best


def _deduplicate_matches(matches: list[dict]) -> list[dict]:
    """When multiple hearings match the same video, keep the highest-confidence one.

    Lower-confidence duplicates are reset to no_match.
    """
    # Group by video_id
    by_video: dict[str, list[int]] = {}
    for i, m in enumerate(matches):
        vid = m.get("youtube_video_id")
        if vid:
            by_video.setdefault(vid, []).append(i)

    for vid, indices in by_video.items():
        if len(indices) <= 1:
            continue
        # Keep the one with highest confidence
        best_idx = max(indices, key=lambda i: matches[i]["match_confidence"])
        for i in indices:
            if i != best_idx:
                matches[i].update(
                    {
                        "youtube_video_id": None,
                        "youtube_url": None,
                        "video_title": None,
                        "video_published_at": None,
                        "match_confidence": 0.0,
                        "match_method": "no_match_deduped",
                    }
                )

    return matches


def match_all_hearings(
    hearings: list[dict],
    videos_by_committee: dict[str, list[dict]],
    committee_map: dict,
) -> list[dict]:
    """Match all hearings against all videos.

    Returns a list of match records (hearing + video + match metadata).
    Includes date sanity filtering and deduplication.
    """
    # Build a flat list of all videos for cross-committee matching
    all_videos = []
    for vids in videos_by_committee.values():
        all_videos.extend(vids)

    matches = []
    for hearing in hearings:
        result = find_best_match_with_sanity(hearing, all_videos, committee_map)
        if result:
            video = result.pop("video")
            matches.append(
                {
                    **hearing,
                    "youtube_video_id": video["video_id"],
                    "youtube_url": f"https://www.youtube.com/watch?v={video['video_id']}",
                    "video_title": video["title"],
                    "video_published_at": video["published_at"],
                    "match_confidence": result["confidence"],
                    "match_method": result["method"],
                }
            )
        else:
            matches.append(
                {
                    **hearing,
                    "youtube_video_id": None,
                    "youtube_url": None,
                    "video_title": None,
                    "video_published_at": None,
                    "match_confidence": 0.0,
                    "match_method": "no_match",
                }
            )

    matches = _deduplicate_matches(matches)
    return matches
