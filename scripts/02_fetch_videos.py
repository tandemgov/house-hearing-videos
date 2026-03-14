#!/usr/bin/env python3
"""Step 2: Fetch YouTube videos for all House committee channels."""

import sys

from src.committees import get_committee_map
from src.fetch_videos import fetch_all_committee_videos


def main():
    force = "--force" in sys.argv

    print("Loading committee map...")
    committee_map = get_committee_map()
    committees = list(committee_map.values())

    with_youtube = [c for c in committees if c.youtube_id]
    print(f"  Total House committees/subcommittees: {len(committees)}")
    print(f"  With YouTube channels: {len(with_youtube)}")

    print("\nFetching videos from YouTube channels...")
    videos_by_committee = fetch_all_committee_videos(
        with_youtube, force_refresh=force
    )

    total_videos = sum(len(v) for v in videos_by_committee.values())
    print(f"\n  Total videos fetched: {total_videos}")
    for code, vids in sorted(videos_by_committee.items()):
        print(f"    {code}: {len(vids)} videos")


if __name__ == "__main__":
    main()
