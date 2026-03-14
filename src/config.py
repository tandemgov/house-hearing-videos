"""Configuration and settings for the house-hearing-videos pipeline."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# API keys
CONGRESS_GOV_API_KEY = os.environ.get("CONGRESS_GOV_API_KEY", "DEMO_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# API base URLs
CONGRESS_API_BASE = "https://api.congress.gov/v3"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_HEARINGS_DIR = DATA_DIR / "raw" / "hearings"
RAW_VIDEOS_DIR = DATA_DIR / "raw" / "videos"
CANDIDATES_DIR = DATA_DIR / "intermediate" / "candidates"
OUTPUT_DIR = DATA_DIR / "output"

# Ensure directories exist
for d in [RAW_HEARINGS_DIR, RAW_VIDEOS_DIR, CANDIDATES_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Congress.gov settings
TARGET_CONGRESS = 118
MIN_CONGRESS = 111  # 2009-2011, start of YouTube era for committees
MAX_CONGRESS = 119  # Current congress
CONGRESS_API_PAGE_SIZE = 250
CONGRESS_API_RATE_LIMIT = 0.5  # seconds between requests (conservative)

# YouTube settings
YOUTUBE_MAX_RESULTS = 50  # max per page

# Matching thresholds
FUZZY_TITLE_THRESHOLD = 80  # token-sort-ratio percentage
DATE_WINDOW_DAYS = 3
CONFIDENCE_INCLUSION_THRESHOLD = 0.70
VIDEO_PUBLISH_SANITY_DAYS = 30

# Committee data source
COMMITTEES_YAML_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/"
    "main/committees-current.yaml"
)
