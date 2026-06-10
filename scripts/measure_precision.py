#!/usr/bin/env python3
"""Measure match precision against API ground truth, from cached data only.

The committee-meeting API's ``videos`` field links actual YouTube URLs for
thousands of meetings. This script compares the pipeline's matched video
for each hearing against those links — the answer key the matcher itself
never sees — and reports per-method precision.

It then re-gates the crosswalk: instead of trusting hand-assigned
confidence scores, it admits only matches from methods whose *measured*
precision clears a bar, and routes the rest to a manual-review queue.

Reads ``data/raw/meetings/`` and ``data/output/all_matches.csv``. No API
calls; no pipeline re-run needed.
"""

import argparse
import json

import polars as pl

from src.config import DATA_DIR, OUTPUT_DIR
from src.fetch_meetings import extract_youtube_video_ids
from src.validate import ground_truth_precision, print_ground_truth_precision

RAW_MEETINGS_DIR = DATA_DIR / "raw" / "meetings"

# A method is trusted when its measured lenient precision clears this bar
# on a sample at least this large.
PRECISION_BAR = 0.95
MIN_LABELED = 50


def build_truth_maps() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build eventID->video and jacket->video maps from cached meeting JSON."""
    meeting_videos: dict[str, list[str]] = {}
    jacket_videos: dict[str, list[str]] = {}
    for path in sorted(RAW_MEETINGS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            continue
        cm = data.get("committeeMeeting")
        if not isinstance(cm, dict):
            continue
        video_ids = extract_youtube_video_ids(data)
        if not video_ids:
            continue
        event_id = str(cm.get("eventId") or "")
        if event_id:
            meeting_videos.setdefault(event_id, []).extend(video_ids)
        for t in cm.get("hearingTranscript") or []:
            jacket = str(t.get("jacketNumber") or "")
            if jacket:
                jacket_videos.setdefault(jacket, []).extend(video_ids)
    return meeting_videos, jacket_videos


def main():
    parser = argparse.ArgumentParser(
        description="Measure match precision against API video links"
    )
    parser.add_argument(
        "--matches-csv",
        default=str(OUTPUT_DIR / "all_matches.csv"),
        help="Path to all_matches.csv (default: data/output/all_matches.csv)",
    )
    args = parser.parse_args()

    meeting_videos, jacket_videos = build_truth_maps()
    print(
        f"Ground truth: {len(meeting_videos)} events / "
        f"{len(jacket_videos)} jackets with API video links"
    )

    df = pl.read_csv(args.matches_csv, infer_schema_length=0).with_columns(
        pl.col("match_confidence").cast(pl.Float64)
    )

    report = ground_truth_precision(df, meeting_videos, jacket_videos)
    print()
    print_ground_truth_precision(report)

    trusted = sorted(
        m["match_method"]
        for m in report["by_method"]
        if m["precision_lenient"] >= PRECISION_BAR and m["labeled"] >= MIN_LABELED
    )
    print(
        f"\nTrusted methods (lenient precision >= {PRECISION_BAR:.0%}, "
        f"n >= {MIN_LABELED}): {', '.join(trusted)}"
    )

    matched = df.filter(pl.col("youtube_video_id").is_not_null())
    net_new = pl.col("net_new") == "true"
    conf_gate = pl.col("match_confidence") >= 0.70
    method_gate = pl.col("match_method").is_in(trusted)

    print("\nRE-GATED CROSSWALK")
    print("-" * 60)
    print(f"{'':40s} {'rows':>6s} {'net-new':>8s}")
    print(
        f"{'Current gate (confidence >= 0.70)':40s}"
        f" {matched.filter(conf_gate).height:6d}"
        f" {matched.filter(conf_gate & net_new).height:8d}"
    )
    print(
        f"{'Method gate (trusted methods only)':40s}"
        f" {matched.filter(method_gate).height:6d}"
        f" {matched.filter(method_gate & net_new).height:8d}"
    )
    demoted = matched.filter(conf_gate & ~method_gate)
    promoted = matched.filter(~conf_gate & method_gate)
    print(
        f"{'Demoted to review (conf gate only)':40s}"
        f" {demoted.height:6d}"
        f" {demoted.filter(net_new).height:8d}"
    )
    print(
        f"{'Promoted (method gate only)':40s}"
        f" {promoted.height:6d}"
        f" {promoted.filter(net_new).height:8d}"
    )

    print("\nDemoted rows by method:")
    for r in (
        demoted.group_by("match_method")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        .to_dicts()
    ):
        print(f"  {r['match_method']:35s} {r['count']:5d}")


if __name__ == "__main__":
    main()
