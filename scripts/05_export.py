#!/usr/bin/env python3
"""Step 5: Export final crosswalk CSV."""

import argparse
import json

from src.config import CANDIDATES_DIR, OUTPUT_DIR, TARGET_CONGRESS
from src.export import export_all_matches, export_crosswalk
from src.validate import build_matches_df


def main():
    parser = argparse.ArgumentParser(description="Export crosswalk CSV")
    parser.add_argument("--congress", type=int, default=TARGET_CONGRESS)
    args = parser.parse_args()

    congress = args.congress

    candidates_path = CANDIDATES_DIR / f"candidates_{congress}.json"
    if not candidates_path.exists():
        print(f"No candidates file found at {candidates_path}")
        print("Run 03_match.py first.")
        return

    matches = json.loads(candidates_path.read_text())
    df = build_matches_df(matches)

    # Export filtered crosswalk (high confidence only)
    crosswalk_path = export_crosswalk(
        df, output_path=str(OUTPUT_DIR / f"crosswalk_{congress}.csv")
    )

    # Export all matches for analysis
    all_path = export_all_matches(
        df, output_path=str(OUTPUT_DIR / f"all_matches_{congress}.csv")
    )

    print("\nFiles written:")
    print(f"  Crosswalk (filtered): {crosswalk_path}")
    print(f"  All matches:          {all_path}")


if __name__ == "__main__":
    main()
