"""Tests for Layer 0 matching and API classification."""

from src.match import match_layer_0_api_video
from src.validate import build_matches_df, classify_matches_vs_api


class TestMatchLayer0:
    def test_matches_when_api_has_video(self):
        hearing = {"event_id": "12345", "committee_codes": ["hsju00"]}
        videos = [{"video_id": "abc123", "title": "Test", "published_at": "2024-01-01"}]
        meeting_videos = {"12345": ["abc123"]}

        result = match_layer_0_api_video(hearing, videos, meeting_videos)
        assert result is not None
        assert result["confidence"] == 1.0
        assert result["method"] == "api_video_direct"
        assert result["video"]["video_id"] == "abc123"

    def test_no_match_without_event_id(self):
        hearing = {"event_id": None, "committee_codes": ["hsju00"]}
        videos = [{"video_id": "abc123", "title": "Test", "published_at": "2024-01-01"}]
        meeting_videos = {"12345": ["abc123"]}

        result = match_layer_0_api_video(hearing, videos, meeting_videos)
        assert result is None

    def test_no_match_when_api_has_no_video(self):
        hearing = {"event_id": "12345", "committee_codes": ["hsju00"]}
        videos = [{"video_id": "abc123", "title": "Test", "published_at": "2024-01-01"}]
        meeting_videos = {"12345": []}

        result = match_layer_0_api_video(hearing, videos, meeting_videos)
        assert result is None

    def test_creates_minimal_video_when_not_in_fetch(self):
        hearing = {"event_id": "12345", "committee_codes": ["hsju00"]}
        videos = []  # Video not in our YouTube fetch
        meeting_videos = {"12345": ["xyz789"]}

        result = match_layer_0_api_video(hearing, videos, meeting_videos)
        assert result is not None
        assert result["video"]["video_id"] == "xyz789"
        assert result["video"]["title"] is None


SAMPLE_MATCHES_FOR_CLASSIFICATION = [
    # Cat A: matched + API has video
    {
        "congress": 118, "jacket_number": "J001", "title": "Hearing A",
        "dates": ["2024-01-15"], "committee_codes": ["hsju00"],
        "committee_names": ["Judiciary"], "youtube_video_id": "vid1",
        "youtube_url": "https://www.youtube.com/watch?v=vid1",
        "video_title": "Video A", "match_confidence": 0.95,
        "match_method": "api_video_direct", "event_id": "EVT001",
        "loc_id": "LC001",
    },
    # Cat B: matched + API has no video
    {
        "congress": 118, "jacket_number": "J002", "title": "Hearing B",
        "dates": ["2024-02-20"], "committee_codes": ["hsag00"],
        "committee_names": ["Agriculture"], "youtube_video_id": "vid2",
        "youtube_url": "https://www.youtube.com/watch?v=vid2",
        "video_title": "Video B", "match_confidence": 0.85,
        "match_method": "fuzzy_title_exact_date", "event_id": "EVT002",
        "loc_id": "LC002",
    },
    # Cat C: no match + API has video
    {
        "congress": 118, "jacket_number": "J003", "title": "Hearing C",
        "dates": ["2024-03-10"], "committee_codes": ["hsju00"],
        "committee_names": ["Judiciary"], "youtube_video_id": None,
        "youtube_url": None, "video_title": None, "match_confidence": 0.0,
        "match_method": "no_match", "event_id": "EVT003",
        "loc_id": "LC003",
    },
    # Cat D: no match + no API video
    {
        "congress": 118, "jacket_number": "J004", "title": "Hearing D",
        "dates": ["2024-04-01"], "committee_codes": ["hswm00"],
        "committee_names": ["Ways & Means"], "youtube_video_id": None,
        "youtube_url": None, "video_title": None, "match_confidence": 0.0,
        "match_method": "no_match", "event_id": "EVT004",
        "loc_id": "LC004",
    },
    # No eventID + matched (unconfirmed net new)
    {
        "congress": 118, "jacket_number": "J005", "title": "Hearing E",
        "dates": ["2024-05-15"], "committee_codes": ["hsag00"],
        "committee_names": ["Agriculture"], "youtube_video_id": "vid5",
        "youtube_url": "https://www.youtube.com/watch?v=vid5",
        "video_title": "Video E", "match_confidence": 0.80,
        "match_method": "exact_date_title", "event_id": None,
        "loc_id": "LC005",
    },
    # No eventID + unmatched
    {
        "congress": 118, "jacket_number": "J006", "title": "Hearing F",
        "dates": ["2024-06-01"], "committee_codes": ["hsju00"],
        "committee_names": ["Judiciary"], "youtube_video_id": None,
        "youtube_url": None, "video_title": None, "match_confidence": 0.0,
        "match_method": "no_match", "event_id": None,
        "loc_id": "LC006",
    },
]


class TestClassifyMatchesVsApi:
    def setup_method(self):
        # EVT001 has video, EVT002 doesn't, EVT003 has video, EVT004 doesn't
        self.meeting_videos = {
            "EVT001": ["vid1"],
            "EVT003": ["vid3_different"],
        }
        self.df = build_matches_df(
            SAMPLE_MATCHES_FOR_CLASSIFICATION, self.meeting_videos
        )

    def test_category_a(self):
        result = classify_matches_vs_api(self.df)
        assert result["with_event_id"]["cat_a_match_and_api"] == 1  # J001

    def test_category_b(self):
        result = classify_matches_vs_api(self.df)
        assert result["with_event_id"]["cat_b_match_no_api"] == 1  # J002

    def test_category_c(self):
        result = classify_matches_vs_api(self.df)
        assert result["with_event_id"]["cat_c_no_match_has_api"] == 1  # J003

    def test_category_d(self):
        result = classify_matches_vs_api(self.df)
        assert result["with_event_id"]["cat_d_no_match_no_api"] == 1  # J004

    def test_no_event_id_matched(self):
        result = classify_matches_vs_api(self.df)
        assert result["without_event_id"]["matched"] == 1  # J005

    def test_no_event_id_unmatched(self):
        result = classify_matches_vs_api(self.df)
        assert result["without_event_id"]["unmatched"] == 1  # J006

    def test_net_new_totals(self):
        result = classify_matches_vs_api(self.df)
        # Without jacket map, no-eventID matches are net_new (api_has_video=False)
        # Cat B from eventID hearings (J002) + no-eventID matched (J005) = 2
        assert result["all_hearings"]["cat_b_match_no_api"] == 2
        assert result["net_new_total"] == 2

    def test_api_has_video_column(self):
        assert "api_has_video" in self.df.columns
        # J001 (EVT001 in meeting_videos) should have api_has_video=True
        j001 = self.df.filter(self.df["jacket_number"] == "J001")
        assert j001["api_has_video"][0] is True

    def test_net_new_column(self):
        assert "net_new" in self.df.columns
        # J002 (matched, no API video) should be net_new=True
        j002 = self.df.filter(self.df["jacket_number"] == "J002")
        assert j002["net_new"][0] is True
        # J001 (matched, API has video) should be net_new=False
        j001 = self.df.filter(self.df["jacket_number"] == "J001")
        assert j001["net_new"][0] is False


class TestJacketVideoMap:
    """Test that jacket-based video map resolves unconfirmed matches."""

    def test_jacket_map_resolves_no_eventid_hearing(self):
        # J005 has no eventID but is matched. With a jacket map that
        # shows J005 already has video, it should NOT be net_new.
        meeting_videos = {"EVT001": ["vid1"]}
        jacket_videos = {"J005": ["vid5_from_api"]}

        df = build_matches_df(
            SAMPLE_MATCHES_FOR_CLASSIFICATION, meeting_videos, jacket_videos
        )
        j005 = df.filter(df["jacket_number"] == "J005")
        assert j005["api_has_video"][0] is True
        assert j005["net_new"][0] is False

    def test_jacket_map_no_video_stays_net_new(self):
        # J005 jacket found in meeting list but has no video
        meeting_videos = {"EVT001": ["vid1"]}
        jacket_videos = {"J005": []}

        df = build_matches_df(
            SAMPLE_MATCHES_FOR_CLASSIFICATION, meeting_videos, jacket_videos
        )
        j005 = df.filter(df["jacket_number"] == "J005")
        assert j005["api_has_video"][0] is False
        assert j005["net_new"][0] is True

    def test_jacket_map_reduces_net_new_total(self):
        meeting_videos = {"EVT001": ["vid1"]}
        jacket_videos = {"J005": ["vid5_from_api"]}

        df = build_matches_df(
            SAMPLE_MATCHES_FOR_CLASSIFICATION, meeting_videos, jacket_videos
        )
        result = classify_matches_vs_api(df)
        # J005 is no longer net new (resolved via jacket), only J002 remains
        assert result["net_new_total"] == 1
