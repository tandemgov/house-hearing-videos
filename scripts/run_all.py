#!/usr/bin/env python3
"""Run the full pipeline across all available congresses.

Fetches YouTube videos once, then loops over congresses (newest-first)
to fetch hearings, match, validate, and export combined results.
"""

import argparse
import json

import polars as pl

from src.committees import get_committee_map
from src.config import (
    CANDIDATES_DIR,
    MAX_CONGRESS,
    MIN_CONGRESS,
    OUTPUT_DIR,
)
from src.export import export_all_matches, export_crosswalk
from src.fetch_hearings import (
    fetch_all_hearing_details,
    fetch_all_hearings,
    load_normalized_hearings,
)
from src.fetch_videos import fetch_all_committee_videos
from src.match import match_all_hearings
from src.validate import build_matches_df, coverage_report, print_coverage_report


def main():
    parser = argparse.ArgumentParser(
        description="Run hearing-to-YouTube pipeline across multiple congresses"
    )
    parser.add_argument(
        "--min-congress", type=int, default=MIN_CONGRESS,
        help=f"Earliest congress to process (default: {MIN_CONGRESS})",
    )
    parser.add_argument(
        "--max-congress", type=int, default=MAX_CONGRESS,
        help=f"Latest congress to process (default: {MAX_CONGRESS})",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass cache and re-fetch all data",
    )
    args = parser.parse_args()

    # Step 1: Fetch videos ONCE (not congress-specific)
    print("=" * 60)
    print("FETCHING YOUTUBE VIDEOS (all committees)")
    print("=" * 60)
    committee_map = get_committee_map()
    committees_with_yt = [c for c in committee_map.values() if c.youtube_id]
    videos_by_committee = fetch_all_committee_videos(
        committees_with_yt, force_refresh=args.force
    )
    total_videos = sum(len(v) for v in videos_by_committee.values())
    print(f"Total videos: {total_videos}")

    # Step 2: Loop over congresses (newest first)
    all_dfs: list[pl.DataFrame] = []
    congress_results: dict[int, dict] = {}

    for congress in range(args.max_congress, args.min_congress - 1, -1):
        print(f"\n{'=' * 60}")
        print(f"CONGRESS {congress}")
        print("=" * 60)

        # Fetch hearings
        try:
            raw = fetch_all_hearings(congress, force_refresh=args.force)
        except Exception as e:
            print(f"  Error fetching hearings: {e}")
            print("  Skipping this congress.")
            continue

        if not raw:
            print("  No hearings found, skipping.")
            continue

        print(f"  Hearing stubs: {len(raw)}")

        # Fetch details
        try:
            fetch_all_hearing_details(congress, force_refresh=args.force)
        except Exception as e:
            print(f"  Error fetching details: {e}")
            print("  Skipping this congress.")
            continue

        hearings = load_normalized_hearings(congress)
        print(f"  Normalized hearings: {len(hearings)}")

        if not hearings:
            print("  No normalized hearings, skipping.")
            continue

        # Match
        matches = match_all_hearings(hearings, videos_by_committee, committee_map)
        matched_count = sum(1 for m in matches if m.get("youtube_video_id"))
        print(f"  Matched: {matched_count} / {len(matches)}")

        # Save per-congress candidates
        out = CANDIDATES_DIR / f"candidates_{congress}.json"
        out.write_text(json.dumps(matches, indent=2))

        # Build DataFrame
        df = build_matches_df(matches)
        all_dfs.append(df)

        # Track per-congress stats
        report = coverage_report(df)
        congress_results[congress] = report
        print(f"  Match rate: {report['match_rate']}% | High confidence: {report['high_confidence_rate']}%")

    # Step 3: Combined export
    if not all_dfs:
        print("\nNo data collected across any congress.")
        return

    combined = pl.concat(all_dfs)

    print(f"\n{'=' * 60}")
    print("COMBINED RESULTS")
    print("=" * 60)

    combined_report = coverage_report(combined)
    print_coverage_report(combined_report)

    # Export combined CSVs
    crosswalk_path = export_crosswalk(
        combined, output_path=str(OUTPUT_DIR / "crosswalk_all.csv")
    )
    all_path = export_all_matches(
        combined, output_path=str(OUTPUT_DIR / "all_matches_all.csv")
    )

    # Save combined validation report
    combined_validation = {
        "overall": combined_report,
        "per_congress": {str(c): r for c, r in congress_results.items()},
    }
    report_path = OUTPUT_DIR / "validation_report_all.json"
    report_path.write_text(json.dumps(combined_validation, indent=2))

    print(f"\nFiles written:")
    print(f"  Crosswalk:          {crosswalk_path}")
    print(f"  All matches:        {all_path}")
    print(f"  Validation report:  {report_path}")

    # Per-congress summary
    print(f"\nPer-congress summary:")
    for congress in sorted(congress_results.keys(), reverse=True):
        r = congress_results[congress]
        print(
            f"  {congress}: {r['total_hearings']} hearings, "
            f"{r['matched']} matched ({r['match_rate']}%), "
            f"{r['high_confidence']} high-conf ({r['high_confidence_rate']}%)"
        )


if __name__ == "__main__":
    main()
