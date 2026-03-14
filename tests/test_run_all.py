"""Tests for the run_all orchestrator logic."""

import polars as pl
import pytest

from src.config import MAX_CONGRESS, MIN_CONGRESS
from src.validate import build_matches_df, coverage_report


class TestCongressRange:
    """Test congress range configuration."""

    def test_min_congress_is_111(self):
        assert MIN_CONGRESS == 111

    def test_max_congress_at_least_118(self):
        assert MAX_CONGRESS >= 118

    def test_range_is_valid(self):
        assert MIN_CONGRESS < MAX_CONGRESS


class TestCombinedOutput:
    """Test combining DataFrames across congresses."""

    def _make_matches(self, congress: int, count: int) -> list[dict]:
        matches = []
        for i in range(count):
            m = {
                "congress": congress,
                "jacket_number": f"{congress}-{i:04d}",
                "title": f"Hearing {i}",
                "dates": ["2024-01-15"],
                "committee_codes": ["hsju00"],
                "committee_names": ["Judiciary"],
            }
            if i % 2 == 0:
                m["youtube_video_id"] = f"vid_{congress}_{i}"
                m["youtube_url"] = f"https://youtube.com/watch?v=vid_{congress}_{i}"
                m["video_title"] = f"Video {i}"
                m["match_confidence"] = 0.85
                m["match_method"] = "fuzzy_title_exact_date"
            matches.append(m)
        return matches

    def test_concat_multiple_congresses(self):
        df_118 = build_matches_df(self._make_matches(118, 10))
        df_117 = build_matches_df(self._make_matches(117, 8))
        combined = pl.concat([df_118, df_117])
        assert len(combined) == 18

    def test_combined_has_both_congresses(self):
        df_118 = build_matches_df(self._make_matches(118, 4))
        df_117 = build_matches_df(self._make_matches(117, 3))
        combined = pl.concat([df_118, df_117])
        congresses = combined["congress"].unique().to_list()
        assert sorted(congresses) == [117, 118]

    def test_combined_coverage_report(self):
        df_118 = build_matches_df(self._make_matches(118, 10))
        df_117 = build_matches_df(self._make_matches(117, 6))
        combined = pl.concat([df_118, df_117])
        report = coverage_report(combined)
        assert report["total_hearings"] == 16
        # Half of each set is matched (even indices)
        assert report["matched"] == 8

    def test_empty_congress_skipped(self):
        """An empty congress produces no DataFrame, so concat works on non-empty only."""
        df_118 = build_matches_df(self._make_matches(118, 4))
        all_dfs = [df_118]  # 117 had no hearings, wasn't added
        combined = pl.concat(all_dfs)
        assert len(combined) == 4
