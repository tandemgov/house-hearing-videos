#!/usr/bin/env python3
"""Step 3: Run the matching algorithm."""

import argparse
import json
from collections import Counter

from src.committees import get_committee_map
from src.config import CANDIDATES_DIR, TARGET_CONGRESS
from src.fetch_hearings import load_normalized_hearings
from src.fetch_videos import fetch_all_committee_videos
from src.match import match_all_hearings


def main():
    parser = argparse.ArgumentParser(description="Run hearing-to-video matching")
    parser.add_argument("--congress", type=int, default=TARGET_CONGRESS)
    args = parser.parse_args()

    congress = args.congress

    print("Loading data...")
    hearings = load_normalized_hearings(congress)
    print(f"  Hearings: {len(hearings)}")

    committee_map = get_committee_map()
    committees_with_yt = [c for c in committee_map.values() if c.youtube_id]
    videos_by_committee = fetch_all_committee_videos(committees_with_yt)

    total_videos = sum(len(v) for v in videos_by_committee.values())
    print(f"  Videos: {total_videos}")

    print("\nRunning matching algorithm...")
    matches = match_all_hearings(hearings, videos_by_committee, committee_map)

    matched = [m for m in matches if m.get("youtube_video_id")]
    print(f"  Matched: {len(matched)} / {len(matches)}")

    # Save candidates
    out = CANDIDATES_DIR / f"candidates_{congress}.json"
    out.write_text(json.dumps(matches, indent=2))
    print(f"  Saved to {out}")

    # Quick summary by method
    methods = Counter(m.get("match_method") for m in matches)
    print("\n  By method:")
    for method, count in methods.most_common():
        print(f"    {method}: {count}")


if __name__ == "__main__":
    main()
