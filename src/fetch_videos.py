"""YouTube Data API v3 client for fetching committee video uploads."""

import json
import time
from pathlib import Path

import httpx

from src.committees import Committee
from src.config import (
    RAW_VIDEOS_DIR,
    YOUTUBE_API_BASE,
    YOUTUBE_API_KEY,
    YOUTUBE_MAX_RESULTS,
)


def _videos_cache_path(playlist_id: str) -> Path:
    return RAW_VIDEOS_DIR / f"playlist_{playlist_id}.json"


def fetch_playlist_videos(
    playlist_id: str,
    *,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch all videos from a YouTube playlist (typically a channel's uploads).

    Uses playlistItems.list (1 quota unit per call, up to 50 results per page).
    """
    cache_path = _videos_cache_path(playlist_id)
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text())

    videos = []
    page_token = None

    with httpx.Client(timeout=30) as client:
        while True:
            params = {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": YOUTUBE_MAX_RESULTS,
                "key": YOUTUBE_API_KEY,
            }
            if page_token:
                params["pageToken"] = page_token

            resp = client.get(
                f"{YOUTUBE_API_BASE}/playlistItems",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                resource = snippet.get("resourceId", {})
                videos.append(
                    {
                        "video_id": resource.get("videoId", ""),
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "channel_id": snippet.get("channelId", ""),
                        "channel_title": snippet.get("channelTitle", ""),
                        "playlist_id": playlist_id,
                    }
                )

            page_token = data.get("nextPageToken")
            if not page_token:
                break

            time.sleep(0.2)  # gentle rate limiting

    cache_path.write_text(json.dumps(videos, indent=2))
    return videos


def fetch_all_committee_videos(
    committees: list[Committee],
    *,
    force_refresh: bool = False,
) -> dict[str, list[dict]]:
    """Fetch videos for all committees with YouTube channels.

    Returns a dict mapping system_code -> list of video metadata.
    """
    all_videos: dict[str, list[dict]] = {}

    for committee in committees:
        playlist_ids = committee.all_uploads_playlist_ids
        if not playlist_ids:
            continue

        committee_videos: list[dict] = []
        for playlist_id in playlist_ids:
            videos = fetch_playlist_videos(
                playlist_id,
                force_refresh=force_refresh,
            )
            committee_videos.extend(videos)

        all_videos[committee.system_code] = committee_videos

    return all_videos


def load_cached_videos() -> dict[str, list[dict]]:
    """Load all cached video data from disk."""
    all_videos: dict[str, list[dict]] = {}

    for cache_file in RAW_VIDEOS_DIR.glob("playlist_*.json"):
        videos = json.loads(cache_file.read_text())
        if videos:
            # Group by the committee system code via the playlist_id
            playlist_id = cache_file.stem.replace("playlist_", "")
            all_videos[playlist_id] = videos

    return all_videos
