"""Tests for validation functions."""

from src.validate import build_matches_df, coverage_report, ground_truth_precision

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


class TestGroundTruthPrecision:
    PRECISION_MATCHES = [
        # agree: pipeline video is the one the API links (via eventID)
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
        # alt_upload: different video, but title matches the hearing (via jacket)
        {
            "congress": 118,
            "jacket_number": "J002",
            "title": "Oversight of the Widget Administration",
            "dates": ["2024-02-20"],
            "committee_codes": ["hsag00"],
            "committee_names": ["Committee on Agriculture"],
            "youtube_video_id": "def456",
            "youtube_url": "https://www.youtube.com/watch?v=def456",
            "video_title": "Oversight of the Widget Administration",
            "match_confidence": 0.85,
            "match_method": "date_committee_unique",
            "event_id": None,
        },
        # likely_wrong: different video, unrelated title
        {
            "congress": 118,
            "jacket_number": "J003",
            "title": "Oversight of the Widget Administration",
            "dates": ["2024-03-10"],
            "committee_codes": ["hsag00"],
            "committee_names": ["Committee on Agriculture"],
            "youtube_video_id": "ghi789",
            "youtube_url": "https://www.youtube.com/watch?v=ghi789",
            "video_title": "Rep. Smith remarks on unrelated topic",
            "match_confidence": 0.85,
            "match_method": "date_committee_unique",
            "event_id": None,
        },
        # unlabeled: matched, but the API links no video for it
        {
            "congress": 118,
            "jacket_number": "J004",
            "title": "Hearing D",
            "dates": ["2024-04-01"],
            "committee_codes": ["hsju00"],
            "committee_names": ["Committee on the Judiciary"],
            "youtube_video_id": "jkl012",
            "youtube_url": "https://www.youtube.com/watch?v=jkl012",
            "video_title": "Hearing D Video",
            "match_confidence": 0.95,
            "match_method": "exact_date_title",
            "event_id": None,
        },
    ]
    MEETING_VIDEOS = {"EVT001": ["abc123"]}
    JACKET_VIDEOS = {"J002": ["xyz999"], "J003": ["xyz998"]}

    def _report(self):
        df = build_matches_df(self.PRECISION_MATCHES)
        return ground_truth_precision(df, self.MEETING_VIDEOS, self.JACKET_VIDEOS)

    def test_labeled_counts(self):
        report = self._report()
        assert report["matched_total"] == 4
        assert report["labeled_total"] == 3

    def test_classification(self):
        report = self._report()
        by_method = {m["match_method"]: m for m in report["by_method"]}
        assert by_method["exact_date_title"]["agree"] == 1
        assert by_method["date_committee_unique"]["alt_upload"] == 1
        assert by_method["date_committee_unique"]["likely_wrong"] == 1

    def test_precision_values(self):
        report = self._report()
        by_method = {m["match_method"]: m for m in report["by_method"]}
        assert by_method["exact_date_title"]["precision_strict"] == 1.0
        assert by_method["date_committee_unique"]["precision_strict"] == 0.0
        assert by_method["date_committee_unique"]["precision_lenient"] == 0.5

    def test_no_ground_truth(self):
        df = build_matches_df(self.PRECISION_MATCHES)
        report = ground_truth_precision(df)
        assert report["labeled_total"] == 0
        assert report["by_method"] == []


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
