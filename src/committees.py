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
    "hsgo00": [
        "UCn8TJ6Tyq2aGvhybME_itDQ",  # GOP Oversight (@OversightandGovernmentReform)
        "UCuwpe69VxVzy4maI6ymmm6A",  # HouseResourceOrg (public.resource.org archive, pre-2011)
    ],
    "hsba00": [
        "UCDQFSLK68yQLJPb8E9ZWmQQ",  # Financial Services GOP (@GOPFinancialServices)
    ],
    "hsif00": [
        "UC5s1kIfkfWbap31d5ef-VtQ",  # Energy & Commerce majority (@energyandcommerce)
    ],
    "hsbu00": [
        "UCHPaSWprI94UTePSMv0tqnw",  # House Budget Committee GOP (@HouseBudgetGOP)
    ],
    "hsfa00": [
        "UCtxAmeCl0xtSuo7tHZpgcQA",  # Foreign Affairs Republicans (@HouseForeignGOP)
    ],
    "hsha00": [
        "UC8dXTgFnWF8NraBKhF040Qg",  # House Administration majority (@CommitteeonHouseAdmin)
    ],
    "hsed00": [
        "UC8Ewe7WqGg01KRNjJCO5cjg",  # Education & Workforce majority (@EdWorkforceCmte)
    ],
    "hsru00": [
        "UCDNcorctkmOpBfr4sgu6t3w",  # Rules Committee majority (@HouseRulesCommittee)
    ],
    "hsag00": [
        "UCWtWf-QUTnJ-UMP5ZNWVB5Q",  # Agriculture majority (@AgRepublicans)
    ],
    "hssm00": [
        "UCoXvuW2IhFawuNyk4yL3EkQ",  # Small Business majority (@HouseSmallBiz)
    ],
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

# Select/special committees and commissions not in congress-legislators YAML.
# These committees are not standing committees, so they must be defined manually.
SELECT_COMMITTEES: list[dict] = [
    {
        "thomas_id": "HLCN",
        "name": "House Select Committee on the Climate Crisis",
        "system_code": "hlcn00",
        "youtube_id": "UCqTxfzU6vYZ2-DW-y5jYvdQ",  # @HouseClimateCrisis
    },
    {
        "thomas_id": "HLIJ",
        "name": "House Select Committee to Investigate the January 6th Attack",
        "system_code": "hlij00",
        "youtube_id": "UCqSRsknSiyLARtzmop9dvhw",  # @January6thCmte
    },
    {
        "thomas_id": "HLMH",
        "name": "House Select Committee on the Modernization of Congress",
        "system_code": "hlmh00",
        "youtube_id": "UCECZaLBqABxBqN7VdtZ5sCA",  # @selectcommitteeonthemodern9383
    },
    {
        "thomas_id": "HLZI",
        "name": "House Select Committee on Benghazi",
        "system_code": "hlzi00",
        "youtube_id": "UCiKI7qlQqr3GfFlIzOdT_Yg",  # @theu.s.houseselectcommitte1053
    },
    {
        "thomas_id": "HSZS",
        "name": "House Select Committee on Strategic Competition with China",
        "system_code": "hszs00",
        "youtube_id": "UCpXe-EZd7pE7QM1daNAk0mA",  # @ChinaSelect
    },
    {
        "thomas_id": "JCPK",
        "name": "Congressional-Executive Commission on China",
        "system_code": "jcpk00",
        "youtube_id": "UCRAT_7MIzUolORlJhYBTzHA",  # @ChinaCommission
    },
    {
        "thomas_id": "JCSE",
        "name": "Commission on Security and Cooperation in Europe (Helsinki Commission)",
        "system_code": "jcse00",
        "youtube_id": "UCtFO3w68Kumz7tRyspaqF2g",  # @HelsinkiCommission
    },
]


# Codes used in the committee-meeting API that differ from our canonical codes.
# Maps meeting-API code → our canonical code so committee_matches() can resolve them.
COMMITTEE_CODE_ALIASES: dict[str, str] = {
    "hlzs00": "hszs00",  # China Select: meeting API uses hlzs00, we use hszs00
}


def resolve_committee_code(code: str) -> str:
    """Resolve a committee code to its canonical form."""
    return COMMITTEE_CODE_ALIASES.get(code, code)


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


def _add_select_committees(committees: list[Committee]) -> None:
    """Add select/special committees not in the congress-legislators YAML.

    If a committee already exists but has no youtube_id, fill it in.
    """
    by_code = {c.system_code: c for c in committees}
    for entry in SELECT_COMMITTEES:
        code = entry["system_code"]
        youtube_id = entry["youtube_id"]
        existing = by_code.get(code)
        if existing:
            if not existing.youtube_id:
                existing.youtube_id = youtube_id
                existing.uploads_playlist_id = _uploads_playlist(youtube_id)
            continue
        committees.append(
            Committee(
                thomas_id=entry["thomas_id"],
                name=entry["name"],
                system_code=code,
                youtube_id=youtube_id,
                uploads_playlist_id=_uploads_playlist(youtube_id),
            )
        )


def get_committee_map() -> dict[str, Committee]:
    """Convenience: fetch, parse, and return the committee map."""
    yaml_text = fetch_committees_yaml()
    committees = parse_committees(yaml_text)
    _apply_extra_channels(committees)
    _add_select_committees(committees)
    return build_committee_map(committees)
