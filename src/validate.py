"""Validation, confidence scoring, and coverage reports."""


import polars as pl
from thefuzz import fuzz

from src.config import (
    ALT_UPLOAD_TITLE_RATIO,
    CONFIDENCE_INCLUSION_THRESHOLD,
    VIDEO_PUBLISH_SANITY_DAYS,
)
from src.match import parse_date


def build_matches_df(
    matches: list[dict],
    meeting_videos: dict[str, list[str]] | None = None,
    jacket_videos: dict[str, list[str]] | None = None,
) -> pl.DataFrame:
    """Convert match records to a Polars DataFrame.

    If meeting_videos is provided, adds ``api_has_video`` and ``net_new``
    columns classifying each hearing.

    If jacket_videos is provided, hearings without an eventID can still
    be checked via their jacket number (discovered from the full
    committee-meeting list endpoint).
    """
    rows = []
    for m in matches:
        event_id = m.get("event_id")
        jacket = m.get("jacket_number", "")
        has_match = bool(m.get("youtube_video_id"))

        # Classify against the committee-meeting API, tracking source
        api_has_video = False
        api_video_source = "unchecked"
        if meeting_videos and event_id:
            if meeting_videos.get(str(event_id)):
                api_has_video = True
                api_video_source = "event_id"
        if not api_has_video and jacket_videos and jacket:
            if jacket_videos.get(str(jacket)):
                api_has_video = True
                api_video_source = "jacket"

        # A match is "net new" if we found a video but the API doesn't have one
        net_new = has_match and not api_has_video

        rows.append(
            {
                "congress": m.get("congress"),
                "jacket_number": m.get("jacket_number", ""),
                "hearing_title": m.get("title", ""),
                "hearing_date": m.get("dates", [""])[0] if m.get("dates") else "",
                "committee_code": m.get("committee_codes", [""])[0]
                if m.get("committee_codes")
                else "",
                "committee_name": m.get("committee_names", [""])[0]
                if m.get("committee_names")
                else "",
                "youtube_video_id": m.get("youtube_video_id"),
                "youtube_url": m.get("youtube_url"),
                "video_title": m.get("video_title"),
                "match_confidence": m.get("match_confidence", 0.0),
                "match_method": m.get("match_method", "no_match"),
                "event_id": m.get("event_id"),
                "loc_id": m.get("loc_id"),
                "api_has_video": api_has_video,
                "api_video_source": api_video_source,
                "net_new": net_new,
                "committee_code_discrepancy": m.get(
                    "committee_code_discrepancy", False
                ),
            }
        )

    schema = {
        "congress": pl.Int64,
        "jacket_number": pl.Utf8,
        "hearing_title": pl.Utf8,
        "hearing_date": pl.Utf8,
        "committee_code": pl.Utf8,
        "committee_name": pl.Utf8,
        "youtube_video_id": pl.Utf8,
        "youtube_url": pl.Utf8,
        "video_title": pl.Utf8,
        "match_confidence": pl.Float64,
        "match_method": pl.Utf8,
        "event_id": pl.Utf8,
        "loc_id": pl.Utf8,
        "api_has_video": pl.Boolean,
        "api_video_source": pl.Utf8,
        "net_new": pl.Boolean,
        "committee_code_discrepancy": pl.Boolean,
    }
    return pl.DataFrame(rows, schema=schema)


def coverage_report(df: pl.DataFrame) -> dict:
    """Generate coverage statistics."""
    total = len(df)
    matched = df.filter(pl.col("match_confidence") > 0).height
    high_conf = df.filter(
        pl.col("match_confidence") >= CONFIDENCE_INCLUSION_THRESHOLD
    ).height

    by_method = (
        df.group_by("match_method")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        .to_dicts()
    )

    by_committee = (
        df.group_by("committee_code")
        .agg(
            pl.len().alias("total"),
            (pl.col("match_confidence") > 0).sum().alias("matched"),
            (pl.col("match_confidence") >= CONFIDENCE_INCLUSION_THRESHOLD)
            .sum()
            .alias("high_confidence"),
        )
        .sort("total", descending=True)
        .to_dicts()
    )

    return {
        "total_hearings": total,
        "matched": matched,
        "match_rate": round(matched / total * 100, 1) if total > 0 else 0,
        "high_confidence": high_conf,
        "high_confidence_rate": round(high_conf / total * 100, 1) if total > 0 else 0,
        "by_method": by_method,
        "by_committee": by_committee,
    }


def benchmark_event_id_recall(df: pl.DataFrame) -> dict:
    """Report match *recall* for hearings that have an eventID.

    This only measures how many eventID hearings got a match by any
    method — it says nothing about whether the matched video is the
    right one. For correctness, see ``ground_truth_precision``, which
    checks matches against the API's own video links.
    """
    with_event_id = df.filter(pl.col("event_id").is_not_null())
    total = with_event_id.height

    if total == 0:
        return {"total_with_event_id": 0, "message": "No hearings with eventID found"}

    matched = with_event_id.filter(pl.col("match_confidence") > 0).height
    via_event_id = with_event_id.filter(
        pl.col("match_method") == "event_id_exact"
    ).height

    return {
        "total_with_event_id": total,
        "matched": matched,
        "matched_via_event_id": via_event_id,
        "matched_via_other": matched - via_event_id,
        "unmatched": total - matched,
        "recall": round(matched / total * 100, 1) if total > 0 else 0,
    }


def ground_truth_precision(
    df: pl.DataFrame,
    meeting_videos: dict[str, list[str]] | None = None,
    jacket_videos: dict[str, list[str]] | None = None,
) -> dict:
    """Measure match precision against video links in the committee-meeting API.

    For each matched hearing where the API itself links one or more YouTube
    videos (via eventID or jacket number), check whether the pipeline picked
    one of those videos. Disagreements are split by title similarity:

      agree         pipeline video is one the API links
      alt_upload    different video, but its title still matches the hearing
                    (likely another upload of the same proceeding)
      likely_wrong  different video and the title does not match

    Per method, ``precision_strict`` counts only ``agree``;
    ``precision_lenient`` also counts ``alt_upload``. The true rate sits
    between them: alt_upload classification uses the same title-similarity
    family as the matcher itself, so a member clip titled after the hearing
    can pass. The labeled subset also skews toward hearings the API covers
    (newer congresses), so extrapolation to net-new rows is optimistic.

    Rows matched via ``api_video_direct`` (Layer 0) take their video from
    the answer key itself and agree by construction — read that row as a
    consistency check, not as evidence of matching quality.
    """
    meeting_videos = meeting_videos or {}
    jacket_videos = jacket_videos or {}

    per_method: dict[str, dict[str, int]] = {}
    matched_total = 0
    labeled_total = 0
    for r in df.iter_rows(named=True):
        if not r["youtube_video_id"]:
            continue
        matched_total += 1
        truth: set[str] = set()
        if r["event_id"]:
            truth.update(meeting_videos.get(str(r["event_id"]), []))
        if r["jacket_number"]:
            truth.update(jacket_videos.get(str(r["jacket_number"]), []))
        if not truth:
            continue
        labeled_total += 1
        counts = per_method.setdefault(
            r["match_method"], {"agree": 0, "alt_upload": 0, "likely_wrong": 0}
        )
        if r["youtube_video_id"] in truth:
            counts["agree"] += 1
        else:
            ratio = fuzz.token_set_ratio(
                (r["hearing_title"] or "").lower(),
                (r["video_title"] or "").lower(),
            )
            if ratio >= ALT_UPLOAD_TITLE_RATIO:
                counts["alt_upload"] += 1
            else:
                counts["likely_wrong"] += 1

    by_method = []
    for method, c in sorted(
        per_method.items(), key=lambda kv: -sum(kv[1].values())
    ):
        labeled = sum(c.values())
        by_method.append(
            {
                "match_method": method,
                "labeled": labeled,
                **c,
                "precision_strict": round(c["agree"] / labeled, 3),
                "precision_lenient": round(
                    (c["agree"] + c["alt_upload"]) / labeled, 3
                ),
            }
        )

    return {
        "matched_total": matched_total,
        "labeled_total": labeled_total,
        "by_method": by_method,
    }


def print_ground_truth_precision(report: dict) -> None:
    """Print the ground-truth precision report."""
    print("=" * 60)
    print("GROUND-TRUTH PRECISION (vs committee-meeting API videos)")
    print("=" * 60)
    print(
        f"Labeled: {report['labeled_total']} of "
        f"{report['matched_total']} matched hearings"
    )
    print(
        f"{'method':35s} {'agree':>6s} {'alt':>5s} {'wrong':>6s}"
        f" {'strict':>7s} {'lenient':>8s}"
    )
    for m in report["by_method"]:
        print(
            f"{m['match_method']:35s} {m['agree']:6d} {m['alt_upload']:5d}"
            f" {m['likely_wrong']:6d} {m['precision_strict']:7.1%}"
            f" {m['precision_lenient']:8.1%}"
        )
    print("=" * 60)


def sanity_check_dates(matches: list[dict]) -> list[dict]:
    """Flag matches where video publish date is too far from hearing date."""
    flagged = []
    for m in matches:
        if not m.get("youtube_video_id"):
            continue

        hearing_date_str = m.get("dates", [""])[0] if m.get("dates") else ""
        video_date_str = m.get("video_published_at", "")

        if not hearing_date_str or not video_date_str:
            continue

        h_date = parse_date(hearing_date_str)
        v_date = parse_date(video_date_str)

        if h_date and v_date:
            diff = abs((v_date - h_date).days)
            if diff > VIDEO_PUBLISH_SANITY_DAYS:
                flagged.append(
                    {
                        "jacket_number": m.get("jacket_number"),
                        "hearing_title": m.get("title"),
                        "hearing_date": hearing_date_str,
                        "video_date": video_date_str,
                        "days_diff": diff,
                        "match_confidence": m.get("match_confidence"),
                    }
                )

    return flagged


def check_duplicate_matches(df: pl.DataFrame) -> pl.DataFrame:
    """Find videos matched to multiple hearings."""
    matched = df.filter(pl.col("youtube_video_id").is_not_null())
    duplicates = (
        matched.group_by("youtube_video_id")
        .agg(pl.len().alias("count"), pl.col("jacket_number"))
        .filter(pl.col("count") > 1)
    )
    return duplicates


def classify_matches_vs_api(df: pl.DataFrame) -> dict:
    """Classify matches into categories based on API video availability.

    Categories (based on api_has_video, which can be set via eventID
    lookup OR jacket-number lookup from the full meeting list):

      A: Our match + API already has the video (not net new)
      B: Our match + API does NOT have the video (genuinely net new)
      C: No pipeline match + API has the video (we're missing something)
      D: Neither pipeline nor API has a video (true gap)

    Hearings are "checked" if we could verify them against the API
    (either via eventID or via jacket-number in the meeting list).
    "Unchecked" hearings had no way to verify.
    """
    has_match = pl.col("match_confidence") > 0
    api_has = pl.col("api_has_video") == True  # noqa: E712

    # All hearings, regardless of how api_has_video was determined
    cat_a = df.filter(has_match & api_has).height
    cat_b = df.filter(has_match & ~api_has).height
    cat_c = df.filter(~has_match & api_has).height
    cat_d = df.filter(~has_match & ~api_has).height

    # Break out by eventID presence for backward-compatible reporting
    has_event_id = df.filter(pl.col("event_id").is_not_null())
    no_event_id = df.filter(pl.col("event_id").is_null())

    # "Checked" = api_has_video could have been set (has eventID,
    # or jacket was found in meeting list — proxied by api_has_video
    # being True for any no-eventID hearing)
    no_eid_checked_via_api = no_event_id.filter(api_has).height
    no_eid_matched = no_event_id.filter(has_match).height
    no_eid_unmatched = no_event_id.filter(~has_match).height

    return {
        "with_event_id": {
            "total": has_event_id.height,
            "cat_a_match_and_api": has_event_id.filter(has_match & api_has).height,
            "cat_b_match_no_api": has_event_id.filter(has_match & ~api_has).height,
            "cat_c_no_match_has_api": has_event_id.filter(~has_match & api_has).height,
            "cat_d_no_match_no_api": has_event_id.filter(~has_match & ~api_has).height,
        },
        "without_event_id": {
            "total": no_event_id.height,
            "checked_via_jacket": no_eid_checked_via_api,
            "matched": no_eid_matched,
            "unmatched": no_eid_unmatched,
        },
        "all_hearings": {
            "cat_a_match_and_api": cat_a,
            "cat_b_match_no_api": cat_b,
            "cat_c_no_match_has_api": cat_c,
            "cat_d_no_match_no_api": cat_d,
        },
        "net_new_total": cat_b,
    }


def print_coverage_report(report: dict) -> None:
    """Print a formatted coverage report."""
    print("=" * 60)
    print("COVERAGE REPORT")
    print("=" * 60)
    print(f"Total hearings:       {report['total_hearings']}")
    print(f"Matched:              {report['matched']} ({report['match_rate']}%)")
    print(f"High confidence:      {report['high_confidence']} ({report['high_confidence_rate']}%)")
    print()
    print("By matching method:")
    for m in report["by_method"]:
        print(f"  {m['match_method']:30s} {m['count']:5d}")
    print()
    print("By committee (top 10):")
    for c in report["by_committee"][:10]:
        print(
            f"  {c['committee_code']:10s} total={c['total']:4d}  "
            f"matched={c['matched']:4d}  high_conf={c['high_confidence']:4d}"
        )
    print("=" * 60)


def print_api_classification(classification: dict) -> None:
    """Print the API classification report."""
    all_h = classification["all_hearings"]
    total = sum(all_h.values())

    print("=" * 60)
    print("API CLASSIFICATION REPORT")
    print("=" * 60)
    print(f"\nAll {total} hearings:")
    print(f"  A) Match + API has video:  {all_h['cat_a_match_and_api']:5d}  (not net new)")
    print(f"  B) Match + no API video:   {all_h['cat_b_match_no_api']:5d}  (net new)")
    print(f"  C) No match + API video:   {all_h['cat_c_no_match_has_api']:5d}  (pipeline gap)")
    print(f"  D) No match + no API:      {all_h['cat_d_no_match_no_api']:5d}  (true gap)")

    eid = classification["with_event_id"]
    no_eid = classification["without_event_id"]
    print("\n  Breakdown by eventID presence:")
    print(f"    With eventID:    {eid['total']:5d}")
    print(f"    Without eventID: {no_eid['total']:5d} "
          f"({no_eid.get('checked_via_jacket', 0)} checked via jacket)")
    print(f"\n  Net new total: {classification['net_new_total']}")
    print("=" * 60)
