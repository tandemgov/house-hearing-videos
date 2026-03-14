# Data Dictionary

Reference for all output file schemas.

## crosswalk.csv

The primary output file containing high-confidence matches (>= 0.70) between House hearings and YouTube videos. This is the file most users want.

| Column | Type | Description |
|--------|------|-------------|
| `congress` | integer | Congress number (e.g., 118) |
| `jacket_number` | string | Congress.gov hearing jacket number (unique identifier) |
| `hearing_title` | string | Official hearing title from Congress.gov |
| `hearing_date` | string | Hearing date in YYYY-MM-DD format (first date if multi-day) |
| `committee_code` | string | Thomas system code (e.g., `hsju00` for House Judiciary) |
| `committee_name` | string | Full committee name |
| `youtube_video_id` | string | YouTube video ID (11-character identifier) |
| `youtube_url` | string | Full YouTube watch URL |
| `video_title` | string | YouTube video title |
| `match_confidence` | float | Confidence score from 0.0 to 1.0 |
| `match_method` | string | Which matching layer produced the match (see below) |
| `event_id` | string/null | Congress.gov eventID, if available |
| `govinfo_id` | string/null | GovInfo CHRG package ID, if available |

## Match Methods

| Method | Description | Confidence Range |
|--------|-------------|-----------------|
| `event_id_exact` | Exact eventID found in video metadata | 1.0 |
| `exact_date_title` | Normalized titles match exactly, date within ±1 day | 0.95 |
| `fuzzy_title_exact_date` | Fuzzy title match (>=80%), date within ±1 day | 0.70-0.90 |
| `substring_nearby_date` | One title contains the other, date within ±1 day | 0.80-0.88 |
| `fuzzy_title_relaxed_date` | Fuzzy title match, date within ±3 days | 0.50-0.75 |
| `description_bills` | Shared bill numbers in title/description | 0.40-0.65 |

## all_matches.csv

Same schema as `crosswalk.csv` but includes all hearings, including those with no match (`match_confidence` = 0.0, `match_method` = `no_match`). Useful for investigating unmatched hearings or analyzing the full hearing universe.

Additional `match_method` values in this file:
- `no_match`: No matching video found
- `no_match_deduped`: Match was removed because another hearing matched the same video with higher confidence
