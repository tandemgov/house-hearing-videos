"""Validation, confidence scoring, and coverage reports."""


import polars as pl

from src.config import CONFIDENCE_INCLUSION_THRESHOLD, VIDEO_PUBLISH_SANITY_DAYS
from src.match import parse_date


def build_matches_df(matches: list[dict]) -> pl.DataFrame:
    """Convert match records to a Polars DataFrame."""
    rows = []
    for m in matches:
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


def benchmark_event_id_accuracy(df: pl.DataFrame) -> dict:
    """Benchmark matching accuracy using hearings with known eventIDs as ground truth.

    For hearings that have an eventID, check whether the matching algorithm
    found the correct video (the one containing that eventID).
    """
    with_event_id = df.filter(pl.col("event_id").is_not_null())
    total = with_event_id.height

    if total == 0:
        return {"total_with_event_id": 0, "message": "No hearings with eventID found"}

    matched = with_event_id.filter(pl.col("match_confidence") > 0).height
    correct_method = with_event_id.filter(
        pl.col("match_method") == "event_id_exact"
    ).height

    return {
        "total_with_event_id": total,
        "matched": matched,
        "matched_via_event_id": correct_method,
        "matched_via_other": matched - correct_method,
        "unmatched": total - matched,
        "accuracy": round(matched / total * 100, 1) if total > 0 else 0,
    }


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
