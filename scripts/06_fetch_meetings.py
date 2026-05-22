#!/usr/bin/env python3
"""Fetch committee-meeting data for all hearings with eventIDs.

Reports how many meetings have YouTube video links in the API response.
"""

import argparse

from src.config import MAX_CONGRESS, MIN_CONGRESS
from src.fetch_hearings import load_normalized_hearings
from src.fetch_meetings import fetch_all_meeting_videos


def main():
    parser = argparse.ArgumentParser(
        description="Fetch committee-meeting API data for hearings with eventIDs"
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

    total_hearings = 0
    total_with_event_id = 0
    total_with_video = 0

    for congress in range(args.max_congress, args.min_congress - 1, -1):
        print(f"\nCongress {congress}")
        print("-" * 40)

        hearings = load_normalized_hearings(congress)
        with_event_id = [h for h in hearings if h.get("event_id")]

        print(f"  Hearings: {len(hearings)} | With eventID: {len(with_event_id)}")

        if not with_event_id:
            total_hearings += len(hearings)
            continue

        results = fetch_all_meeting_videos(
            with_event_id, force_refresh=args.force
        )

        with_video = sum(1 for v in results.values() if v)

        total_hearings += len(hearings)
        total_with_event_id += len(with_event_id)
        total_with_video += with_video

    print(f"\n{'=' * 50}")
    print("SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total hearings:          {total_hearings}")
    print(f"With eventID:            {total_with_event_id} "
          f"({total_with_event_id * 100 // max(total_hearings, 1)}%)")
    print(f"API has YouTube link:    {total_with_video} "
          f"({total_with_video * 100 // max(total_with_event_id, 1)}%)")
    print(f"No API video link:       {total_with_event_id - total_with_video}")


if __name__ == "__main__":
    main()
