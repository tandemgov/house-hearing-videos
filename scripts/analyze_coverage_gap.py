#!/usr/bin/env python3
"""Analyze the coverage gap across all congresses.

Produces a breakdown of:
- How many hearings have eventIDs
- How many of those have API video links
- How many our pipeline matches
- How many are genuinely net new

Also investigates committees with low match rates and data quality issues.
"""

import argparse
import json

import polars as pl

from src.config import MAX_CONGRESS, MIN_CONGRESS, OUTPUT_DIR
from src.fetch_hearings import load_normalized_hearings
from src.fetch_meetings import (
    build_jacket_video_map,
    fetch_all_meeting_videos,
    fetch_all_meetings_for_congress,
)
from src.validate import build_matches_df, classify_matches_vs_api


def load_matches(congress: int) -> list[dict] | None:
    """Load cached candidate matches for a congress."""
    from src.config import CANDIDATES_DIR

    path = CANDIDATES_DIR / f"candidates_{congress}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description="Analyze hearing coverage gaps")
    parser.add_argument(
        "--min-congress", type=int, default=MIN_CONGRESS,
        help=f"Earliest congress (default: {MIN_CONGRESS})",
    )
    parser.add_argument(
        "--max-congress", type=int, default=MAX_CONGRESS,
        help=f"Latest congress (default: {MAX_CONGRESS})",
    )
    args = parser.parse_args()

    # Collect per-congress data
    congress_rows = []
    all_dfs = []
    committee_stats: dict[str, dict] = {}

    for congress in range(args.max_congress, args.min_congress - 1, -1):
        hearings = load_normalized_hearings(congress)
        matches = load_matches(congress)

        if not hearings or not matches:
            print(f"Congress {congress}: no data (run pipeline first)")
            continue

        # Fetch meeting videos (cached)
        meeting_videos = fetch_all_meeting_videos(hearings)

        # Fetch full meeting list for jacket-based lookup
        all_meetings = fetch_all_meetings_for_congress(congress)
        jacket_videos = build_jacket_video_map(all_meetings)

        # Build DataFrame with API classification
        df = build_matches_df(matches, meeting_videos, jacket_videos)
        all_dfs.append(df)
        classification = classify_matches_vs_api(df)

        total = len(hearings)
        has_event_id = sum(1 for h in hearings if h.get("event_id"))
        has_loc_id = sum(1 for h in hearings if h.get("loc_id"))
        all_h = classification["all_hearings"]
        api_has_video = all_h["cat_a_match_and_api"] + \
            all_h["cat_c_no_match_has_api"]
        pipeline_matches = df.filter(pl.col("match_confidence") > 0).height
        net_new = classification["net_new_total"]

        congress_rows.append({
            "congress": congress,
            "total": total,
            "has_event_id": has_event_id,
            "has_loc_id": has_loc_id,
            "api_has_video": api_has_video,
            "pipeline_matches": pipeline_matches,
            "net_new_total": net_new,
        })

        # Accumulate committee stats
        for row in df.to_dicts():
            code = row["committee_code"] or "(none)"
            if code not in committee_stats:
                committee_stats[code] = {
                    "committee_code": code,
                    "committee_name": row["committee_name"] or "",
                    "total": 0,
                    "matched": 0,
                    "net_new": 0,
                }
            committee_stats[code]["total"] += 1
            if row["match_confidence"] > 0:
                committee_stats[code]["matched"] += 1
            if row["net_new"]:
                committee_stats[code]["net_new"] += 1

    if not congress_rows:
        print("No data found. Run the pipeline first.")
        return

    # Print congress-level table
    print("=" * 100)
    print("COVERAGE GAP ANALYSIS BY CONGRESS")
    print("=" * 100)
    print(
        f"{'Congress':>8} {'Total':>7} {'EventID':>8} {'LOC ID':>8} "
        f"{'API Video':>10} {'Matched':>8} {'Net New':>8}"
    )
    print("-" * 80)

    totals = {k: 0 for k in congress_rows[0] if k != "congress"}

    for row in congress_rows:
        print(
            f"{row['congress']:>8} {row['total']:>7} "
            f"{row['has_event_id']:>8} {row['has_loc_id']:>8} "
            f"{row['api_has_video']:>10} {row['pipeline_matches']:>8} "
            f"{row['net_new_total']:>8}"
        )
        for k in totals:
            totals[k] += row[k]

    print("-" * 80)
    print(
        f"{'TOTAL':>8} {totals['total']:>7} "
        f"{totals['has_event_id']:>8} {totals['has_loc_id']:>8} "
        f"{totals['api_has_video']:>10} {totals['pipeline_matches']:>8} "
        f"{totals['net_new_total']:>8}"
    )

    # Combined API classification
    if all_dfs:
        combined = pl.concat(all_dfs)
        combined_class = classify_matches_vs_api(combined)

        print(f"\n{'=' * 60}")
        print("COMBINED API CLASSIFICATION")
        print("=" * 60)
        all_h = combined_class["all_hearings"]
        total_h = sum(all_h.values())
        print(f"\nAll {total_h} hearings:")
        print(f"  A) Match + API has video:  {all_h['cat_a_match_and_api']:>5}  (not net new)")
        print(f"  B) Match + no API video:   {all_h['cat_b_match_no_api']:>5}  (net new)")
        print(f"  C) No match + API video:   {all_h['cat_c_no_match_has_api']:>5}  (pipeline gap)")
        print(f"  D) No match + no API:      {all_h['cat_d_no_match_no_api']:>5}  (true gap)")
        print(f"\n  Net new: {combined_class['net_new_total']}")

    # Committee breakdown (sorted by total, descending)
    print(f"\n{'=' * 90}")
    print("COMMITTEE BREAKDOWN")
    print("=" * 90)
    print(f"{'Code':>10} {'Total':>6} {'Matched':>8} {'Rate':>6} {'Net New':>8}  Name")
    print("-" * 90)

    sorted_committees = sorted(
        committee_stats.values(), key=lambda x: x["total"], reverse=True
    )
    for c in sorted_committees:
        rate = c["matched"] * 100 / c["total"] if c["total"] > 0 else 0
        print(
            f"{c['committee_code']:>10} {c['total']:>6} {c['matched']:>8} "
            f"{rate:>5.1f}% {c['net_new']:>8}  {c['committee_name'][:50]}"
        )

    # Save results
    output = {
        "by_congress": congress_rows,
        "by_committee": sorted_committees,
    }
    if all_dfs:
        output["combined_classification"] = combined_class

    output_path = OUTPUT_DIR / "coverage_gap_analysis.json"
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
