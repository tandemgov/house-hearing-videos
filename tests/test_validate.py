"""Tests for validation functions."""

from src.validate import build_matches_df, coverage_report

SAMPLE_MATCHES = [
    {
        "congress": 118,
        "jacket_number": "J001",
        "title": "Hearing A",
        "dates": ["2024-01-15"],
        "committee_codes": ["hsju00"],
        "committee_names": ["Committee on the Judiciary"],
        "youtube_video_id": "abc123",
        "youtube_url": "https://www.youtube.com/watch?v=abc123",
        "video_title": "Hearing A Video",
        "match_confidence": 0.95,
        "match_method": "exact_date_title",
        "event_id": "EVT001",
    },
    {
        "congress": 118,
        "jacket_number": "J002",
        "title": "Hearing B",
        "dates": ["2024-02-20"],
        "committee_codes": ["hsag00"],
        "committee_names": ["Committee on Agriculture"],
        "youtube_video_id": "def456",
        "youtube_url": "https://www.youtube.com/watch?v=def456",
        "video_title": "Hearing B Video",
        "match_confidence": 0.75,
        "match_method": "fuzzy_title_exact_date",
        "event_id": None,
    },
    {
        "congress": 118,
        "jacket_number": "J003",
        "title": "Hearing C",
        "dates": ["2024-03-10"],
        "committee_codes": ["hsju00"],
        "committee_names": ["Committee on the Judiciary"],
        "youtube_video_id": None,
        "youtube_url": None,
        "video_title": None,
        "match_confidence": 0.0,
        "match_method": "no_match",
        "event_id": None,
    },
]


class TestBuildMatchesDf:
    def test_creates_dataframe(self):
        df = build_matches_df(SAMPLE_MATCHES)
        assert len(df) == 3

    def test_columns_present(self):
        df = build_matches_df(SAMPLE_MATCHES)
        assert "jacket_number" in df.columns
        assert "match_confidence" in df.columns


class TestCoverageReport:
    def test_total_count(self):
        df = build_matches_df(SAMPLE_MATCHES)
        report = coverage_report(df)
        assert report["total_hearings"] == 3

    def test_matched_count(self):
        df = build_matches_df(SAMPLE_MATCHES)
        report = coverage_report(df)
        assert report["matched"] == 2

    def test_high_confidence(self):
        df = build_matches_df(SAMPLE_MATCHES)
        report = coverage_report(df)
        assert report["high_confidence"] == 2  # 0.95 and 0.75 both >= 0.70
