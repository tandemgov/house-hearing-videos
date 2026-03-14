"""Tests for the matching algorithm."""

from src.match import (
    _deduplicate_matches,
    _passes_date_sanity,
    dates_match_exact,
    dates_match_nearby,
    dates_within_window,
    extract_bill_numbers,
    match_layer_1_event_id,
    match_layer_2_exact,
    match_layer_3_fuzzy_title,
    match_layer_3b_substring,
    match_layer_4_relaxed_date,
    match_layer_5_description,
    normalize_title,
)


class TestNormalizeTitle:
    def test_lowercase(self):
        assert normalize_title("HEARING ON TAXES") == "taxes"

    def test_strip_prefix_hearing_on(self):
        assert normalize_title("Hearing on the Budget") == "the budget"

    def test_strip_prefix_full_committee(self):
        assert normalize_title("Full Committee Hearing: Climate Change") == "climate change"

    def test_strip_embedded_date(self):
        result = normalize_title("Hearing on Budget January 15, 2024 Review")
        assert "january" not in result
        assert "2024" not in result

    def test_strip_embedded_date_numeric(self):
        result = normalize_title("Budget 01/15/2024 Review")
        assert "01/15/2024" not in result

    def test_normalize_punctuation(self):
        result = normalize_title("The U.S. Economy: Challenges & Opportunities")
        assert result == "the u s economy challenges opportunities"

    def test_strip_quotes(self):
        result = normalize_title('Hearing entitled "The Future of AI"')
        assert result == "the future of ai"

    def test_markup_prefix(self):
        result = normalize_title("Markup of H.R. 1234")
        assert "markup" not in result


class TestDateMatching:
    def test_exact_match(self):
        assert dates_match_exact(["2024-03-15"], "2024-03-15T14:00:00Z")

    def test_no_match(self):
        assert not dates_match_exact(["2024-03-15"], "2024-03-16T14:00:00Z")

    def test_multiple_dates(self):
        assert dates_match_exact(["2024-03-14", "2024-03-15"], "2024-03-15T10:00:00Z")

    def test_within_window(self):
        match, diff = dates_within_window(["2024-03-15"], "2024-03-17T14:00:00Z")
        assert match
        assert diff == 2

    def test_outside_window(self):
        match, diff = dates_within_window(["2024-03-15"], "2024-03-25T14:00:00Z")
        assert not match

    def test_nearby_same_day(self):
        assert dates_match_nearby(["2024-03-15"], "2024-03-15T14:00:00Z")

    def test_nearby_next_day(self):
        assert dates_match_nearby(["2024-03-15"], "2024-03-16T14:00:00Z")

    def test_nearby_too_far(self):
        assert not dates_match_nearby(["2024-03-15"], "2024-03-17T14:00:00Z")


class TestExtractBillNumbers:
    def test_hr_bill(self):
        bills = extract_bill_numbers("Discussion of H.R. 1234 and H.R. 5678")
        assert len(bills) == 2

    def test_senate_bill(self):
        bills = extract_bill_numbers("S. 456")
        assert len(bills) == 1

    def test_resolution(self):
        bills = extract_bill_numbers("H.Res. 100")
        assert len(bills) == 1

    def test_no_bills(self):
        bills = extract_bill_numbers("General oversight hearing")
        assert len(bills) == 0


class TestMatchLayer1:
    def test_event_id_in_description(self):
        hearing = {"event_id": "12345", "title": "Test"}
        video = {"title": "Hearing", "description": "Event 12345 coverage"}
        result = match_layer_1_event_id(hearing, video)
        assert result is not None
        assert result["confidence"] == 1.0

    def test_no_event_id(self):
        hearing = {"event_id": None, "title": "Test"}
        video = {"title": "Hearing", "description": "Some video"}
        assert match_layer_1_event_id(hearing, video) is None

    def test_event_id_not_found(self):
        hearing = {"event_id": "12345", "title": "Test"}
        video = {"title": "Hearing", "description": "Unrelated video"}
        assert match_layer_1_event_id(hearing, video) is None


class TestMatchLayer2:
    def test_exact_match(self):
        hearing = {"title": "The Economy", "dates": ["2024-03-15"]}
        video = {"title": "The Economy", "published_at": "2024-03-15T14:00:00Z"}
        result = match_layer_2_exact(hearing, video)
        assert result is not None
        assert result["confidence"] == 0.95

    def test_next_day_publish(self):
        """Video published the day after hearing should still match."""
        hearing = {"title": "The Economy", "dates": ["2024-03-15"]}
        video = {"title": "The Economy", "published_at": "2024-03-16T14:00:00Z"}
        result = match_layer_2_exact(hearing, video)
        assert result is not None
        assert result["confidence"] == 0.95

    def test_different_title(self):
        hearing = {"title": "The Economy", "dates": ["2024-03-15"]}
        video = {"title": "Budget Hearing", "published_at": "2024-03-15T14:00:00Z"}
        assert match_layer_2_exact(hearing, video) is None

    def test_two_days_later(self):
        hearing = {"title": "The Economy", "dates": ["2024-03-15"]}
        video = {"title": "The Economy", "published_at": "2024-03-17T14:00:00Z"}
        assert match_layer_2_exact(hearing, video) is None


class TestMatchLayer3:
    def test_fuzzy_match(self):
        hearing = {
            "title": "Examining the Impact of Climate Change on Agriculture",
            "dates": ["2024-03-15"],
        }
        video = {
            "title": "Impact of Climate Change on Agriculture",
            "published_at": "2024-03-15T14:00:00Z",
        }
        result = match_layer_3_fuzzy_title(hearing, video)
        assert result is not None
        assert 0.70 <= result["confidence"] <= 0.90

    def test_too_different(self):
        hearing = {"title": "The Economy", "dates": ["2024-03-15"]}
        video = {"title": "Completely Unrelated Topic", "published_at": "2024-03-15T14:00:00Z"}
        assert match_layer_3_fuzzy_title(hearing, video) is None


class TestMatchLayer3bSubstring:
    def test_hearing_title_in_video(self):
        hearing = {
            "title": "Oversight of the FBI",
            "dates": ["2024-03-15"],
        }
        video = {
            "title": "Full Committee Hearing: Oversight of the FBI",
            "published_at": "2024-03-15T14:00:00Z",
        }
        result = match_layer_3b_substring(hearing, video)
        assert result is not None
        assert 0.80 <= result["confidence"] <= 0.88

    def test_video_title_in_hearing(self):
        hearing = {
            "title": "Hearing on the State of Climate Science and Policy",
            "dates": ["2024-03-15"],
        }
        video = {
            "title": "State of Climate Science and Policy",
            "published_at": "2024-03-16T14:00:00Z",
        }
        result = match_layer_3b_substring(hearing, video)
        assert result is not None

    def test_no_substring(self):
        hearing = {"title": "Oversight of the FBI", "dates": ["2024-03-15"]}
        video = {"title": "Budget Review", "published_at": "2024-03-15T14:00:00Z"}
        assert match_layer_3b_substring(hearing, video) is None

    def test_too_short(self):
        hearing = {"title": "Short", "dates": ["2024-03-15"]}
        video = {"title": "Short title", "published_at": "2024-03-15T14:00:00Z"}
        assert match_layer_3b_substring(hearing, video) is None


class TestMatchLayer4:
    def test_relaxed_date(self):
        hearing = {
            "title": "Examining the Impact of Climate Change on Agriculture",
            "dates": ["2024-03-15"],
        }
        video = {
            "title": "Impact of Climate Change on Agriculture",
            "published_at": "2024-03-17T14:00:00Z",
        }
        result = match_layer_4_relaxed_date(hearing, video)
        assert result is not None
        assert 0.50 <= result["confidence"] <= 0.75


class TestMatchLayer5:
    def test_shared_bills(self):
        hearing = {
            "title": "Hearing on H.R. 1234 and H.R. 5678",
            "dates": ["2024-03-15"],
        }
        video = {
            "title": "Committee Vote",
            "description": "Discussion of H.R. 1234",
            "published_at": "2024-03-15T14:00:00Z",
        }
        result = match_layer_5_description(hearing, video)
        assert result is not None
        assert 0.40 <= result["confidence"] <= 0.65

    def test_no_shared_bills(self):
        hearing = {"title": "General Oversight", "dates": ["2024-03-15"]}
        video = {
            "title": "Something",
            "description": "H.R. 9999",
            "published_at": "2024-03-15T14:00:00Z",
        }
        assert match_layer_5_description(hearing, video) is None


class TestDateSanity:
    def test_passes_within_window(self):
        hearing = {"dates": ["2024-03-15"]}
        video = {"published_at": "2024-03-20T14:00:00Z"}
        assert _passes_date_sanity(hearing, video)

    def test_fails_far_apart(self):
        hearing = {"dates": ["2024-03-15"]}
        video = {"published_at": "2025-03-15T14:00:00Z"}
        assert not _passes_date_sanity(hearing, video)


class TestDeduplication:
    def test_keeps_highest_confidence(self):
        matches = [
            {"youtube_video_id": "abc", "match_confidence": 0.95, "match_method": "exact"},
            {"youtube_video_id": "abc", "match_confidence": 0.70, "match_method": "fuzzy"},
            {"youtube_video_id": "def", "match_confidence": 0.80, "match_method": "exact"},
        ]
        result = _deduplicate_matches(matches)
        assert result[0]["youtube_video_id"] == "abc"
        assert result[1]["youtube_video_id"] is None
        assert result[1]["match_method"] == "no_match_deduped"
        assert result[2]["youtube_video_id"] == "def"

    def test_no_duplicates_unchanged(self):
        matches = [
            {"youtube_video_id": "abc", "match_confidence": 0.95, "match_method": "exact"},
            {"youtube_video_id": "def", "match_confidence": 0.80, "match_method": "exact"},
        ]
        result = _deduplicate_matches(matches)
        assert result[0]["youtube_video_id"] == "abc"
        assert result[1]["youtube_video_id"] == "def"
