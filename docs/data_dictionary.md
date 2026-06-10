# Data Dictionary

Reference for all output file schemas.

## crosswalk.csv

The primary output file linking House hearings to YouTube videos. This is the file most users want. Inclusion is by `match_method`: only methods that measured ≥ 95% precision against the committee-meeting API's own video links are admitted (`TRUSTED_MATCH_METHODS` in `src/config.py` — see the measured-precision table in [Matching Methodology](matching_methodology.md#measured-precision)). The `match_confidence` score is retained for context but is not the inclusion gate.

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
| `loc_id` | string/null | Library of Congress identifier for the hearing, if available |
| `api_has_video` | boolean | Whether the Congress.gov committee-meeting API already has a video link for this hearing |
| `net_new` | boolean | True if the pipeline found a video but the Congress.gov API does not have it |
| `govinfo_id` | string/null | GovInfo CHRG package ID, if available |

## Match Methods

Methods marked ✓ are in the trusted set and appear in `crosswalk.csv`; the rest appear only in `all_matches.csv` as a manual-review queue.

| Method | Crosswalk | Description | Confidence Range |
|--------|:---:|-------------|-----------------|
| `api_video_direct` | ✓ | YouTube link from Congress.gov committee-meeting API | 1.0 |
| `event_id_exact` | ✓ | Exact eventID found in video metadata | 1.0 |
| `exact_date_title` | ✓ | Normalized titles match exactly, date within ±1 day | 0.95 |
| `fuzzy_title_exact_date` | ✓ | Fuzzy title match (>=80%), date within ±1 day | 0.70-0.90 |
| `substring_nearby_date` | ✓ | One title contains the other, date within ±1 day | 0.80-0.88 |
| `token_set_nearby_date` | ✓ | Short title keywords found in longer video title, date within ±1 day | 0.55-0.68 |
| `date_committee_unique` | | Only one video for this committee on this date | 0.85 |
| `date_description_keywords` | | Same date, keyword overlap in video description disambiguates | 0.75-0.85 |
| `date_description_keywords_relaxed` | | Same date, relaxed keyword overlap thresholds | 0.45-0.60 |
| `fuzzy_title_relaxed_date` | | Fuzzy title match, date within ±3 days | 0.50-0.75 |
| `description_bills` | | Shared bill numbers in title/description | 0.40-0.65 |
| `date_committee_only_single` | | Only one video for this committee within ±2 days, no title match | 0.30 |
| `date_committee_only_best_guess` | | Best guess among multiple same-committee/same-date videos | 0.20-0.30 |

## all_matches.csv

Identical columns to `crosswalk.csv`, but includes every hearing — those with no match (`match_confidence` = 0.0, `match_method` = `no_match`) and the review queue (matches from methods outside the trusted set). Useful for working the review queue, investigating unmatched hearings, or analyzing the full hearing universe.

Additional `match_method` values in this file:
- `no_match`: No matching video found
- `no_match_deduped`: Match was removed because another hearing matched the same video with higher confidence
