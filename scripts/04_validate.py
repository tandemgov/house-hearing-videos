#!/usr/bin/env python3
"""Step 4: Validate matches and generate reports."""

import argparse
import json

from src.config import CANDIDATES_DIR, OUTPUT_DIR, TARGET_CONGRESS
from src.validate import (
    benchmark_event_id_accuracy,
    build_matches_df,
    check_duplicate_matches,
    coverage_report,
    print_coverage_report,
    sanity_check_dates,
)


def main():
    parser = argparse.ArgumentParser(description="Validate matches and generate reports")
    parser.add_argument("--congress", type=int, default=TARGET_CONGRESS)
    args = parser.parse_args()

    congress = args.congress

    candidates_path = CANDIDATES_DIR / f"candidates_{congress}.json"
    if not candidates_path.exists():
        print(f"No candidates file found at {candidates_path}")
        print("Run 03_match.py first.")
        return

    matches = json.loads(candidates_path.read_text())
    print(f"Loaded {len(matches)} candidate matches\n")

    df = build_matches_df(matches)

    # Coverage report
    report = coverage_report(df)
    print_coverage_report(report)

    # Benchmark against known eventIDs
    print("\nEVENT ID BENCHMARK")
    print("-" * 40)
    benchmark = benchmark_event_id_accuracy(df)
    for k, v in benchmark.items():
        print(f"  {k}: {v}")

    # Sanity checks
    print("\nDATE SANITY CHECK")
    print("-" * 40)
    flagged = sanity_check_dates(matches)
    if flagged:
        print(f"  {len(flagged)} matches with >30 day date gap:")
        for f in flagged[:5]:
            print(f"    {f['jacket_number']}: {f['days_diff']} days")
    else:
        print("  All matches pass date sanity check")

    # Duplicate check
    print("\nDUPLICATE CHECK")
    print("-" * 40)
    dupes = check_duplicate_matches(df)
    if len(dupes) > 0:
        print(f"  {len(dupes)} videos matched to multiple hearings")
    else:
        print("  No duplicate matches found")

    # Save report
    report_path = OUTPUT_DIR / f"validation_report_{congress}.json"
    report_path.write_text(
        json.dumps({"coverage": report, "benchmark": benchmark}, indent=2)
    )
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
