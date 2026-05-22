"""Tests for the matching algorithm."""

from src.fetch_hearings import enrich_hearing_with_meeting_data
from src.match import (
    _deduplicate_matches,
    _match_by_committee_date_only,
    _match_by_date_and_description,
    _passes_date_sanity,
    committee_matches,
    dates_match_exact,
    dates_match_nearby,
    dates_within_window,
    extract_bill_numbers,
    match_layer_0_api_video,
    match_layer_1_event_id,
    match_layer_2_exact,
    match_layer_3_fuzzy_title,
    match_layer_3b_substring,
    match_layer_3c_token_set,
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


class TestMatchLayer3cTokenSet:
    def test_jfk_files_pattern(self):
        """Short hearing title keywords embedded in longer video title."""
        hearing = {
            "title": "THE JFK FILES",
            "dates": ["2025-04-01"],
        }
        video = {
            "title": "Task Force on the Declassification of Federal Secrets: the JFK Files",
            "published_at": "2025-04-01T14:00:00Z",
            "description": "",
        }
        result = match_layer_3c_token_set(hearing, video)
        assert result is not None
        assert 0.55 <= result["confidence"] <= 0.68
        assert result["method"] == "token_set_nearby_date"

    def test_too_short_title_rejected(self):
        hearing = {"title": "SHORT", "dates": ["2025-04-01"]}
        video = {
            "title": "A short hearing",
            "published_at": "2025-04-01T14:00:00Z",
            "description": "",
        }
        assert match_layer_3c_token_set(hearing, video) is None

    def test_unrelated_titles_rejected(self):
        hearing = {
            "title": "Examining the Impact of Climate Change on Agriculture",
            "dates": ["2025-04-01"],
        }
        video = {
            "title": "Oversight of the Federal Bureau of Investigation",
            "published_at": "2025-04-01T14:00:00Z",
            "description": "",
        }
        assert match_layer_3c_token_set(hearing, video) is None

    def test_skips_when_sort_ratio_high(self):
        """Layer 3 would catch these, so 3c should skip."""
        hearing = {
            "title": "Examining the Impact of Climate Change on Agriculture",
            "dates": ["2025-04-01"],
        }
        video = {
            "title": "Impact of Climate Change on Agriculture",
            "published_at": "2025-04-01T14:00:00Z",
            "description": "",
        }
        # token_sort_ratio is high here, so layer 3c defers to layer 3
        assert match_layer_3c_token_set(hearing, video) is None

    def test_wrong_date_rejected(self):
        hearing = {"title": "THE JFK FILES", "dates": ["2025-04-01"]}
        video = {
            "title": "Task Force on the Declassification of Federal Secrets: the JFK Files",
            "published_at": "2025-04-10T14:00:00Z",
            "description": "",
        }
        assert match_layer_3c_token_set(hearing, video) is None


class TestMatchByDateAndDescriptionRelaxed:
    def test_relaxed_tier_fires(self):
        """Moderate keyword overlap below strict thresholds should still match."""
        hearing = {
            "title": "Examining Border Security Operations",
            "dates": ["2025-04-01"],
        }
        # Two videos: one shares "border" and "security", the other doesn't
        videos = [
            {
                "video_id": "v1",
                "title": "Border Security and Immigration Update",
                "description": "",
                "published_at": "2025-04-01T14:00:00Z",
            },
            {
                "video_id": "v2",
                "title": "AI Moonshot Hearing on Technology",
                "description": "",
                "published_at": "2025-04-01T14:00:00Z",
            },
        ]
        result = _match_by_date_and_description(hearing, videos)
        assert result is not None
        assert result["video"]["video_id"] == "v1"

    def test_no_overlap_returns_none(self):
        """Zero keyword overlap should not match even in relaxed tier."""
        hearing = {
            "title": "Examining Border Security Operations",
            "dates": ["2025-04-01"],
        }
        videos = [
            {
                "video_id": "v1",
                "title": "Completely Unrelated Topic About Space",
                "description": "",
                "published_at": "2025-04-01T14:00:00Z",
            },
            {
                "video_id": "v2",
                "title": "Another Unrelated Topic About Taxes",
                "description": "",
                "published_at": "2025-04-01T14:00:00Z",
            },
        ]
        result = _match_by_date_and_description(hearing, videos)
        assert result is None


class TestMatchByCommitteeDateOnly:
    def test_single_video_same_day(self):
        hearing = {"title": "Some Hearing", "dates": ["2025-04-01"]}
        videos = [
            {
                "video_id": "v1",
                "title": "Rules Committee Hearing H.R. ____",
                "description": "",
                "published_at": "2025-04-01T14:00:00Z",
            },
        ]
        result = _match_by_committee_date_only(hearing, videos)
        assert result is not None
        assert result["confidence"] == 0.30
        assert result["method"] == "date_committee_only_single"

    def test_multiple_videos_picks_best(self):
        hearing = {
            "title": "H.R. 1, ONE BIG BEAUTIFUL BILL ACT",
            "dates": ["2025-05-21"],
        }
        videos = [
            {
                "video_id": "v1",
                "title": "Rules Committee Hearing H.R. ____",
                "description": "",
                "published_at": "2025-05-21T14:00:00Z",
            },
            {
                "video_id": "v2",
                "title": "Rules Committee Hearing H.R. ____ Part 2",
                "description": "",
                "published_at": "2025-05-21T14:00:00Z",
            },
        ]
        result = _match_by_committee_date_only(hearing, videos)
        assert result is not None
        assert 0.20 <= result["confidence"] <= 0.30
        assert result["method"] == "date_committee_only_best_guess"

    def test_no_videos_returns_none(self):
        hearing = {"title": "Some Hearing", "dates": ["2025-04-01"]}
        videos = [
            {
                "video_id": "v1",
                "title": "Something",
                "description": "",
                "published_at": "2025-06-01T14:00:00Z",
            },
        ]
        result = _match_by_committee_date_only(hearing, videos)
        assert result is None

    def test_two_day_gap_matches(self):
        """Video published 2 days after hearing should still match."""
        hearing = {"title": "Some Hearing", "dates": ["2025-04-01"]}
        videos = [
            {
                "video_id": "v1",
                "title": "Committee Hearing",
                "description": "",
                "published_at": "2025-04-03T14:00:00Z",
            },
        ]
        result = _match_by_committee_date_only(hearing, videos)
        assert result is not None
        assert result["confidence"] == 0.30

    def test_no_dates_returns_none(self):
        hearing = {"title": "Some Hearing", "dates": []}
        videos = [
            {
                "video_id": "v1",
                "title": "Something",
                "description": "",
                "published_at": "2025-04-01T14:00:00Z",
            },
        ]
        result = _match_by_committee_date_only(hearing, videos)
        assert result is None


class TestEnrichHearingWithMeetingData:
    def test_adds_meeting_codes(self):
        hearing = {
            "jacket_number": "60494",
            "committee_codes": ["hlse00"],
            "event_id": None,
        }
        jacket_map = {
            "60494": {
                "video_ids": ["eg-TRtZDX6A"],
                "committee_codes": ["hlzs00"],
                "event_id": "118132",
            }
        }
        result = enrich_hearing_with_meeting_data(hearing, jacket_map)
        assert "hlzs00" in result["effective_committee_codes"]
        assert "hlse00" in result["effective_committee_codes"]
        assert result["meeting_committee_codes"] == ["hlzs00"]
        assert result["committee_code_discrepancy"] is True

    def test_fills_event_id(self):
        hearing = {
            "jacket_number": "60494",
            "committee_codes": ["hlse00"],
            "event_id": None,
        }
        jacket_map = {
            "60494": {
                "video_ids": [],
                "committee_codes": ["hlzs00"],
                "event_id": "118132",
            }
        }
        result = enrich_hearing_with_meeting_data(hearing, jacket_map)
        assert result["event_id"] == "118132"

    def test_no_meeting_data(self):
        hearing = {
            "jacket_number": "99999",
            "committee_codes": ["hsju00"],
            "event_id": None,
        }
        result = enrich_hearing_with_meeting_data(hearing, {})
        assert result["effective_committee_codes"] == ["hsju00"]
        assert result["committee_code_discrepancy"] is False

    def test_no_discrepancy_when_codes_match(self):
        hearing = {
            "jacket_number": "12345",
            "committee_codes": ["hsju00"],
            "event_id": "100",
        }
        jacket_map = {
            "12345": {
                "video_ids": ["abc"],
                "committee_codes": ["hsju00"],
                "event_id": "100",
            }
        }
        result = enrich_hearing_with_meeting_data(hearing, jacket_map)
        assert result["committee_code_discrepancy"] is False


class TestCommitteeMatchesEffectiveCodes:
    """Test that committee_matches uses effective_committee_codes."""

    def _make_committee_map(self):
        from src.committees import Committee
        return {
            "hszs00": Committee(
                thomas_id="HSZS",
                name="China Select",
                system_code="hszs00",
                youtube_id="UCpXe-EZd7pE7QM1daNAk0mA",
                uploads_playlist_id="UUpXe-EZd7pE7QM1daNAk0mA",
                extra_youtube_ids=None,
                extra_uploads_playlist_ids=None,
            ),
        }

    def test_uses_effective_codes(self):
        hearing = {
            "committee_codes": ["hlse00"],  # wrong code
            "effective_committee_codes": ["hlse00", "hlzs00"],  # includes alias
        }
        video = {"channel_id": "UCpXe-EZd7pE7QM1daNAk0mA"}
        cm = self._make_committee_map()
        # hlzs00 is an alias for hszs00 which has this channel
        assert committee_matches(hearing, video, cm) is True

    def test_falls_back_to_committee_codes(self):
        hearing = {"committee_codes": ["hszs00"]}  # no effective_committee_codes
        video = {"channel_id": "UCpXe-EZd7pE7QM1daNAk0mA"}
        cm = self._make_committee_map()
        assert committee_matches(hearing, video, cm) is True


class TestLayer0ApiVideo:
    def test_matches_via_event_id(self):
        hearing = {"event_id": "100", "jacket_number": "60494"}
        all_videos = [
            {"video_id": "v_event", "title": "Event", "published_at": None, "channel_id": None},
        ]
        result = match_layer_0_api_video(hearing, all_videos, {"100": ["v_event"]})
        assert result is not None
        assert result["video"]["video_id"] == "v_event"
        assert result["method"] == "api_video_direct"

    def test_no_event_id_returns_none(self):
        """Jacket→video mapping is NOT used for matching (unreliable)."""
        hearing = {"event_id": None, "jacket_number": "60494"}
        all_videos = [
            {"video_id": "eg-TRtZDX6A", "title": "Test", "published_at": None, "channel_id": None}
        ]
        result = match_layer_0_api_video(
            hearing, all_videos, {},
            jacket_videos={"60494": ["eg-TRtZDX6A"]},
        )
        assert result is None

    def test_no_event_no_jacket(self):
        hearing = {"event_id": None, "jacket_number": "99999"}
        result = match_layer_0_api_video(hearing, [], {}, jacket_videos={})
        assert result is None
