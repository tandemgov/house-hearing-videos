"""Tests for the committee-meeting API fetcher."""

import json

import httpx
import respx

from src.fetch_meetings import (
    build_jacket_meeting_map,
    extract_committee_codes,
    extract_youtube_urls,
    extract_youtube_video_ids,
    fetch_meeting,
)

SAMPLE_MEETING_RESPONSE = {
    "committeeMeeting": {
        "chamber": "House",
        "congress": 119,
        "eventId": "118749",
        "title": "Test Hearing Title",
        "videos": [
            {
                "name": "Subcommittee Hearing",
                "url": "https://www.congress.gov/event/119th-Congress/house-event/118749",
            },
            {
                "name": "Subcommittee Hearing",
                "url": "https://www.youtube.com/watch?v=pVa7gbsjKBE",
            },
        ],
    }
}

SAMPLE_MEETING_NO_VIDEOS = {
    "committeeMeeting": {
        "chamber": "House",
        "congress": 119,
        "eventId": "999999",
        "title": "No Video Hearing",
        "videos": [],
    }
}

SAMPLE_MEETING_CONGRESS_ONLY = {
    "committeeMeeting": {
        "chamber": "House",
        "congress": 119,
        "eventId": "888888",
        "title": "Congress.gov Only",
        "videos": [
            {
                "name": "Hearing",
                "url": "https://www.congress.gov/event/119th-Congress/house-event/888888",
            },
        ],
    }
}


class TestExtractYoutubeUrls:
    def test_extracts_youtube_url(self):
        urls = extract_youtube_urls(SAMPLE_MEETING_RESPONSE)
        assert urls == ["https://www.youtube.com/watch?v=pVa7gbsjKBE"]

    def test_empty_videos(self):
        urls = extract_youtube_urls(SAMPLE_MEETING_NO_VIDEOS)
        assert urls == []

    def test_congress_gov_only(self):
        urls = extract_youtube_urls(SAMPLE_MEETING_CONGRESS_ONLY)
        assert urls == []

    def test_multiple_youtube_urls(self):
        meeting = {
            "committeeMeeting": {
                "videos": [
                    {"url": "https://www.youtube.com/watch?v=abc12345678"},
                    {"url": "https://www.youtube.com/watch?v=def12345678"},
                ]
            }
        }
        urls = extract_youtube_urls(meeting)
        assert len(urls) == 2


class TestExtractYoutubeVideoIds:
    def test_extracts_video_id(self):
        ids = extract_youtube_video_ids(SAMPLE_MEETING_RESPONSE)
        assert ids == ["pVa7gbsjKBE"]

    def test_empty(self):
        ids = extract_youtube_video_ids(SAMPLE_MEETING_NO_VIDEOS)
        assert ids == []


@respx.mock
class TestFetchMeeting:
    def test_fetches_and_caches(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.fetch_meetings.RAW_MEETINGS_DIR", tmp_path)

        respx.get(
            "https://api.congress.gov/v3/committee-meeting/119/house/118749"
        ).mock(return_value=httpx.Response(200, json=SAMPLE_MEETING_RESPONSE))

        result = fetch_meeting(119, "118749")
        assert result is not None
        assert result["committeeMeeting"]["eventId"] == "118749"

        # Check cache was written
        cache = tmp_path / "meeting_119_118749.json"
        assert cache.exists()
        cached = json.loads(cache.read_text())
        assert cached["committeeMeeting"]["eventId"] == "118749"

    def test_returns_cached(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.fetch_meetings.RAW_MEETINGS_DIR", tmp_path)

        cache = tmp_path / "meeting_119_118749.json"
        cache.write_text(json.dumps(SAMPLE_MEETING_RESPONSE))

        # No HTTP mock needed — should use cache
        result = fetch_meeting(119, "118749")
        assert result is not None
        assert result["committeeMeeting"]["eventId"] == "118749"

    def test_returns_none_on_404(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.fetch_meetings.RAW_MEETINGS_DIR", tmp_path)

        respx.get(
            "https://api.congress.gov/v3/committee-meeting/119/house/000000"
        ).mock(return_value=httpx.Response(404))

        result = fetch_meeting(119, "000000")
        assert result is None


class TestExtractCommitteeCodes:
    def test_extracts_codes(self):
        meeting = {
            "committeeMeeting": {
                "committees": [
                    {"name": "China Select", "systemCode": "hszs00"},
                ]
            }
        }
        assert extract_committee_codes(meeting) == ["hszs00"]

    def test_empty_committees(self):
        meeting = {"committeeMeeting": {"committees": []}}
        assert extract_committee_codes(meeting) == []


class TestBuildJacketMeetingMap:
    def test_builds_map_with_codes_and_videos(self):
        meetings = [
            {
                "committeeMeeting": {
                    "eventId": "118132",
                    "committees": [{"systemCode": "hlzs00"}],
                    "videos": [
                        {"url": "https://www.youtube.com/watch?v=eg-TRtZDX6A"}
                    ],
                    "hearingTranscript": [{"jacketNumber": 60494}],
                }
            }
        ]
        result = build_jacket_meeting_map(meetings)
        assert "60494" in result
        assert result["60494"]["video_ids"] == ["eg-TRtZDX6A"]
        assert result["60494"]["committee_codes"] == ["hlzs00"]
        assert result["60494"]["event_id"] == "118132"

    def test_merges_multiple_meetings(self):
        meetings = [
            {
                "committeeMeeting": {
                    "eventId": "100",
                    "committees": [{"systemCode": "hsju00"}],
                    "videos": [{"url": "https://www.youtube.com/watch?v=abc12345678"}],
                    "hearingTranscript": [{"jacketNumber": 12345}],
                }
            },
            {
                "committeeMeeting": {
                    "eventId": "200",
                    "committees": [{"systemCode": "hsfa00"}],
                    "videos": [{"url": "https://www.youtube.com/watch?v=def12345678"}],
                    "hearingTranscript": [{"jacketNumber": 12345}],
                }
            },
        ]
        result = build_jacket_meeting_map(meetings)
        assert "12345" in result
        assert set(result["12345"]["video_ids"]) == {"abc12345678", "def12345678"}
        assert set(result["12345"]["committee_codes"]) == {"hsju00", "hsfa00"}
