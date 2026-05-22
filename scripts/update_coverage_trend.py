#!/usr/bin/env python3
"""Update the coverage trend file with today's stats.

Reads the latest validation report and appends a timestamped entry to
data/output/coverage_trend.json.  Safe to run multiple times on the
same day -- it will overwrite that day's entry rather than duplicate it.
"""

import json
import sys
from datetime import UTC, datetime

from src.config import OUTPUT_DIR


def load_validation_report() -> dict | None:
    """Load the combined validation report."""
    path = OUTPUT_DIR / "validation_report.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_coverage_gap_analysis() -> dict | None:
    """Load the coverage gap analysis for net_new_total."""
    path = OUTPUT_DIR / "coverage_gap_analysis.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def build_trend_entry(report: dict, gap_analysis: dict | None) -> dict:
    """Build a single trend entry from the validation report and gap analysis."""
    overall = report["overall"]
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    # net_new_total comes from the api_classification in the report
    # or from coverage_gap_analysis.json
    net_new_total = 0

    if "api_classification" in report:
        net_new_total = report["api_classification"].get("net_new_total", 0)
    elif gap_analysis and "combined_classification" in gap_analysis:
        net_new_total = gap_analysis["combined_classification"].get("net_new_total", 0)

    return {
        "date": today,
        "total": overall["total_hearings"],
        "matched": overall["matched"],
        "high_confidence": overall["high_confidence"],
        "net_new_total": net_new_total,
    }


def update_trend(entry: dict) -> list[dict]:
    """Load existing trend data, upsert today's entry, and return the list."""
    trend_path = OUTPUT_DIR / "coverage_trend.json"

    if trend_path.exists():
        trend = json.loads(trend_path.read_text())
    else:
        trend = []

    # Remove any existing entry for today's date to avoid duplicates
    trend = [t for t in trend if t["date"] != entry["date"]]
    trend.append(entry)

    # Sort by date ascending
    trend.sort(key=lambda t: t["date"])

    return trend


def main():
    report = load_validation_report()
    if report is None:
        print("No validation report found at data/output/validation_report.json")
        print("Run the pipeline first.")
        sys.exit(1)

    gap_analysis = load_coverage_gap_analysis()
    entry = build_trend_entry(report, gap_analysis)

    trend = update_trend(entry)

    trend_path = OUTPUT_DIR / "coverage_trend.json"
    trend_path.write_text(json.dumps(trend, indent=2) + "\n")

    print(f"Coverage trend updated: {entry}")
    print(f"  Total entries: {len(trend)}")
    print(f"  Written to: {trend_path}")


if __name__ == "__main__":
    main()
