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
    enrich_hearing_with_meeting_data,
    fetch_all_hearing_details,
    fetch_all_hearings,
    load_normalized_hearings,
)
from src.fetch_meetings import (
    build_jacket_meeting_map,
    fetch_all_meeting_videos,
    fetch_all_meetings_for_congress,
)
from src.fetch_videos import fetch_all_committee_videos
from src.match import match_all_hearings
from src.validate import (
    build_matches_df,
    classify_matches_vs_api,
    coverage_report,
    ground_truth_precision,
    print_api_classification,
    print_coverage_report,
    print_ground_truth_precision,
)


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
    all_meeting_videos: dict[str, list[str]] = {}
    all_jacket_videos: dict[str, list[str]] = {}

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

        # Fetch committee-meeting API data for hearings with eventIDs
        meeting_videos = fetch_all_meeting_videos(
            hearings, force_refresh=args.force
        )
        all_meeting_videos.update(meeting_videos)

        # Fetch full meeting list to discover jacket->video mappings
        jacket_videos: dict[str, list[str]] = {}
        jacket_meeting_map: dict[str, dict] = {}
        try:
            all_meetings = fetch_all_meetings_for_congress(
                congress, force_refresh=args.force
            )
            jacket_meeting_map = build_jacket_meeting_map(all_meetings)
            jacket_videos = {
                k: v["video_ids"] for k, v in jacket_meeting_map.items()
            }
            all_jacket_videos.update(jacket_videos)
            jv_with_video = sum(1 for v in jacket_videos.values() if v)
            print(
                f"  Jacket->video map: {len(jacket_videos)} jackets, "
                f"{jv_with_video} with video"
            )
        except Exception as e:
            print(f"  Warning: could not fetch meeting list: {e}")
            print("  Jacket-based classification will be skipped.")

        # Enrich hearings with meeting API data (cross-reference committee codes)
        hearings = [
            enrich_hearing_with_meeting_data(h, jacket_meeting_map)
            for h in hearings
        ]
        discrepancies = [h for h in hearings if h.get("committee_code_discrepancy")]
        if discrepancies:
            print(f"  Committee code discrepancies: {len(discrepancies)}")
            for h in discrepancies[:3]:
                print(
                    f"    Jacket {h['jacket_number']}: "
                    f"hearing={h['committee_codes']} "
                    f"vs meeting={h['meeting_committee_codes']}"
                )

        # Match (with Layer 0 from API video links + jacket videos)
        matches = match_all_hearings(
            hearings, videos_by_committee, committee_map,
            meeting_videos, jacket_videos,
        )
        matched_count = sum(1 for m in matches if m.get("youtube_video_id"))
        print(f"  Matched: {matched_count} / {len(matches)}")

        # Save per-congress candidates
        out = CANDIDATES_DIR / f"candidates_{congress}.json"
        out.write_text(json.dumps(matches, indent=2))

        # Build DataFrame (with API classification using both maps)
        df = build_matches_df(matches, meeting_videos, jacket_videos)
        all_dfs.append(df)

        # Track per-congress stats
        report = coverage_report(df)
        congress_results[congress] = report
        print(
            f"  Match rate: {report['match_rate']}% | "
            f"High confidence: {report['high_confidence_rate']}%"
        )

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

    # API classification
    api_classification = classify_matches_vs_api(combined)
    print_api_classification(api_classification)

    # Ground-truth precision: where the API itself links a video, did we
    # pick the same one?
    precision = ground_truth_precision(
        combined, all_meeting_videos, all_jacket_videos
    )
    print_ground_truth_precision(precision)

    # Export combined CSVs
    crosswalk_path = export_crosswalk(combined)
    all_path = export_all_matches(combined)

    # Save combined validation report
    combined_validation = {
        "overall": combined_report,
        "api_classification": api_classification,
        "ground_truth_precision": precision,
        "per_congress": {str(c): r for c, r in congress_results.items()},
    }
    report_path = OUTPUT_DIR / "validation_report.json"
    report_path.write_text(json.dumps(combined_validation, indent=2))

    print("\nFiles written:")
    print(f"  Crosswalk:          {crosswalk_path}")
    print(f"  All matches:        {all_path}")
    print(f"  Validation report:  {report_path}")

    # Per-congress summary
    print("\nPer-congress summary:")
    for congress in sorted(congress_results.keys(), reverse=True):
        r = congress_results[congress]
        print(
            f"  {congress}: {r['total_hearings']} hearings, "
            f"{r['matched']} matched ({r['match_rate']}%), "
            f"{r['high_confidence']} high-conf ({r['high_confidence_rate']}%)"
        )


if __name__ == "__main__":
    main()
