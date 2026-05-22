"""Final CSV generation for the crosswalk dataset."""

import polars as pl

from src.config import CONFIDENCE_INCLUSION_THRESHOLD, OUTPUT_DIR

OUTPUT_COLUMNS = [
    "congress",
    "jacket_number",
    "hearing_title",
    "hearing_date",
    "committee_code",
    "committee_name",
    "youtube_video_id",
    "youtube_url",
    "video_title",
    "match_confidence",
    "match_method",
    "event_id",
    "loc_id",
    "api_has_video",
    "net_new",
    "govinfo_id",
]


def export_crosswalk(
    df: pl.DataFrame,
    *,
    min_confidence: float = CONFIDENCE_INCLUSION_THRESHOLD,
    output_path: str | None = None,
) -> str:
    """Export the crosswalk CSV, filtering to matches above the confidence threshold.

    Returns the path to the written file.
    """
    if output_path is None:
        output_path = str(OUTPUT_DIR / "crosswalk.csv")

    # Add govinfo_id column if not present
    if "govinfo_id" not in df.columns:
        df = df.with_columns(pl.lit(None).alias("govinfo_id").cast(pl.Utf8))

    # Filter to confident matches
    filtered = df.filter(pl.col("match_confidence") >= min_confidence)

    # Select and order columns (only those that exist)
    available = [c for c in OUTPUT_COLUMNS if c in filtered.columns]
    result = filtered.select(available).sort(["congress", "committee_code", "hearing_date"])

    result.write_csv(output_path)
    print(f"Exported {len(result)} matches to {output_path}")
    return output_path


def export_all_matches(
    df: pl.DataFrame,
    output_path: str | None = None,
) -> str:
    """Export all match records (including unmatched) for analysis."""
    if output_path is None:
        output_path = str(OUTPUT_DIR / "all_matches.csv")

    if "govinfo_id" not in df.columns:
        df = df.with_columns(pl.lit(None).alias("govinfo_id").cast(pl.Utf8))

    available = [c for c in OUTPUT_COLUMNS if c in df.columns]
    result = df.select(available).sort(["congress", "committee_code", "hearing_date"])

    result.write_csv(output_path)
    print(f"Exported {len(result)} records to {output_path}")
    return output_path
