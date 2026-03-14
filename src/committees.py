"""Committee code to YouTube channel mapping."""

from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

from src.config import COMMITTEES_YAML_URL, RAW_HEARINGS_DIR


@dataclass
class Committee:
    thomas_id: str
    name: str
    system_code: str
    youtube_id: str | None
    uploads_playlist_id: str | None
    extra_youtube_ids: list[str] | None = None
    extra_uploads_playlist_ids: list[str] | None = None

    @property
    def all_youtube_ids(self) -> list[str]:
        """All YouTube channel IDs (primary + extras)."""
        ids = [self.youtube_id] if self.youtube_id else []
        if self.extra_youtube_ids:
            ids.extend(self.extra_youtube_ids)
        return ids

    @property
    def all_uploads_playlist_ids(self) -> list[str]:
        """All uploads playlist IDs (primary + extras)."""
        ids = [self.uploads_playlist_id] if self.uploads_playlist_id else []
        if self.extra_uploads_playlist_ids:
            ids.extend(self.extra_uploads_playlist_ids)
        return ids


# Additional YouTube channels not in the congress-legislators YAML.
# Many committees have separate majority/minority/events channels.
EXTRA_CHANNELS: dict[str, list[str]] = {
    "hshm00": [
        "UCgmYwMNLJaRPj7TPgCdOllg",  # Homeland Security Republicans
        "UChdT2snPVxfp2m8n4VDdMag",  # Homeland Security Events
    ],
    "hswm00": [
        "UC8FSgDMEzdK7j3lsQ4G4L0A",  # Ways & Means Republicans
    ],
    "hsii00": [
        "UCY08wEbJ8fztRofQ9eZs0-g",  # Natural Resources GOP
    ],
    "hsvr00": [
        "UCOQgnjFDCT6kbC-b-Hy6cqg",  # Veterans' Affairs GOP
        "UC0ADPBDC8KdU52IxuW-_X5g",  # Veterans' Affairs Democrats
    ],
}


def _system_code_from_thomas(thomas_id: str) -> str:
    """Convert THOMAS ID (e.g., 'HSJU') to system code (e.g., 'hsju00').

    Full committees get '00' suffix; subcommittees use their two-digit number.
    """
    return thomas_id.lower() + "00"


def _uploads_playlist(channel_id: str) -> str:
    """Convert a YouTube channel ID (UC...) to its uploads playlist (UU...)."""
    if channel_id.startswith("UC"):
        return "UU" + channel_id[2:]
    return channel_id


def fetch_committees_yaml(cache_path: Path | None = None) -> str:
    """Fetch committees-current.yaml, using a local cache if available."""
    if cache_path is None:
        cache_path = RAW_HEARINGS_DIR / "committees-current.yaml"

    if cache_path.exists():
        return cache_path.read_text()

    resp = httpx.get(COMMITTEES_YAML_URL, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    cache_path.write_text(resp.text)
    return resp.text


def parse_committees(yaml_text: str) -> list[Committee]:
    """Parse committees YAML and return House committees with YouTube channels."""
    data = yaml.safe_load(yaml_text)
    committees = []

    for entry in data:
        committee_type = entry.get("type", "")
        if committee_type != "house":
            continue

        thomas_id = entry.get("thomas_id", "")
        youtube_id = entry.get("youtube_id")
        name = entry.get("name", "")
        system_code = _system_code_from_thomas(thomas_id)

        committees.append(
            Committee(
                thomas_id=thomas_id,
                name=name,
                system_code=system_code,
                youtube_id=youtube_id,
                uploads_playlist_id=_uploads_playlist(youtube_id) if youtube_id else None,
            )
        )

        # Also include subcommittees
        for sub in entry.get("subcommittees", []):
            sub_thomas_id = sub.get("thomas_id", "")
            sub_code = thomas_id.lower() + sub_thomas_id
            sub_youtube = sub.get("youtube_id")
            committees.append(
                Committee(
                    thomas_id=thomas_id + sub_thomas_id,
                    name=sub.get("name", ""),
                    system_code=sub_code,
                    youtube_id=sub_youtube,
                    uploads_playlist_id=_uploads_playlist(sub_youtube) if sub_youtube else None,
                )
            )

    return committees


def _apply_extra_channels(committees: list[Committee]) -> None:
    """Enrich committees with additional YouTube channels from EXTRA_CHANNELS."""
    by_code = {c.system_code: c for c in committees}
    for code, channel_ids in EXTRA_CHANNELS.items():
        committee = by_code.get(code)
        if committee:
            committee.extra_youtube_ids = channel_ids
            committee.extra_uploads_playlist_ids = [
                _uploads_playlist(cid) for cid in channel_ids
            ]


def build_committee_map(committees: list[Committee]) -> dict[str, Committee]:
    """Build a mapping from system_code to Committee."""
    return {c.system_code: c for c in committees}


def get_committee_map() -> dict[str, Committee]:
    """Convenience: fetch, parse, and return the committee map."""
    yaml_text = fetch_committees_yaml()
    committees = parse_committees(yaml_text)
    _apply_extra_channels(committees)
    return build_committee_map(committees)
