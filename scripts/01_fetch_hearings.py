#!/usr/bin/env python3
"""Step 1: Fetch House hearings from Congress.gov API."""

import argparse
import json

from src.config import RAW_HEARINGS_DIR, TARGET_CONGRESS
from src.fetch_hearings import (
    fetch_all_hearing_details,
    fetch_all_hearings,
    load_normalized_hearings,
)


def main():
    parser = argparse.ArgumentParser(description="Fetch House hearings from Congress.gov")
    parser.add_argument("--congress", type=int, default=TARGET_CONGRESS)
    parser.add_argument("--force", action="store_true", help="Bypass cache")
    args = parser.parse_args()

    congress = args.congress

    print(f"Fetching House hearings for {congress}th Congress...")
    raw = fetch_all_hearings(congress, force_refresh=args.force)
    print(f"  Hearing stubs: {len(raw)}")

    print("Fetching hearing details (this may take a while)...")
    details = fetch_all_hearing_details(congress, force_refresh=args.force)
    print(f"  Hearing details: {len(details)}")

    hearings = load_normalized_hearings(congress)
    print(f"  Normalized hearings: {len(hearings)}")

    # Save normalized for inspection
    out = RAW_HEARINGS_DIR / f"hearings_{congress}_normalized.json"
    out.write_text(json.dumps(hearings, indent=2))
    print(f"  Saved to {out}")

    # Summary
    with_event_id = sum(1 for h in hearings if h.get("event_id"))
    print(f"  Hearings with eventID: {with_event_id}")
    print(f"  Hearings without eventID: {len(hearings) - with_event_id}")


if __name__ == "__main__":
    main()
