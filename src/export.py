"""Final CSV generation for the crosswalk dataset."""

import polars as pl

from src.config import OUTPUT_DIR, TRUSTED_MATCH_METHODS

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
    trusted_methods: tuple[str, ...] = TRUSTED_MATCH_METHODS,
    output_path: str | None = None,
) -> str:
    """Export the crosswalk CSV, filtering to matches from trusted methods.

    Trust is based on measured precision against the committee-meeting
    API's own video links, not on the hand-assigned confidence score
    (see TRUSTED_MATCH_METHODS in config). Returns the path to the
    written file.
    """
    if output_path is None:
        output_path = str(OUTPUT_DIR / "crosswalk.csv")

    # Add govinfo_id column if not present
    if "govinfo_id" not in df.columns:
        df = df.with_columns(pl.lit(None).alias("govinfo_id").cast(pl.Utf8))

    # Filter to matches from methods with measured-high precision
    filtered = df.filter(pl.col("match_method").is_in(list(trusted_methods)))

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
