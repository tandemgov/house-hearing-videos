# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Ground-truth precision measurement (`ground_truth_precision` in `src/validate.py`, standalone `scripts/measure_precision.py`): every matched hearing where the committee-meeting API links its own video is checked for agreement, with disagreements classified as alternate-upload vs likely-wrong; per-method precision is printed by `run_all.py` and saved in `validation_report.json`
- Committee-meeting API cross-referencing: every match is checked against the Congress.gov committee-meeting API (by eventID and by jacket number) to flag `net_new` and `api_has_video`, and classified into coverage categories A–D
- Committee-code discrepancy detection between the hearing API and the committee-meeting API
- 7 select/special committee channels and 17 supplemental majority/party channels (45 channels across 28 committees), discovered via manual oEmbed verification
- Additional matching layers: token-set, substring, date+description keyword disambiguation, and same-committee/same-date fallbacks (13 methods total)
- GitHub Actions weekly pipeline run with automated coverage-trend tracking
- `loc_id` (Library of Congress identifier) column in the output

### Changed

- `crosswalk.csv` is now gated by *measured* per-method precision (`TRUSTED_MATCH_METHODS` in config) instead of the hand-assigned `match_confidence >= 0.70` threshold. Date/keyword fallback methods that measured 32–72% precision are demoted to the `all_matches.csv` review queue; `token_set_nearby_date` (measured ~99%) is promoted despite its sub-0.70 confidence
- Layer 1 eventID matching hardened: digit-bounded matching (an eventID no longer matches inside a longer number), explicit `EventID=` labels trusted regardless of upload date, bare-number occurrences now require the video date to pass the 30-day sanity window (archive-filename date fragments like `hrs04IR2172_110119` previously collided with 6-digit eventIDs)
- `benchmark_event_id_accuracy` renamed to `benchmark_event_id_recall` — it measures how many eventID hearings got any match, not whether the match is correct, and its output key now says so
- Output files renamed to drop the vestigial `_all` suffix: `crosswalk.csv`, `all_matches.csv`, `validation_report.json`
- Coverage now spans all 111th–119th hearings with full any-source analysis: 9,512 of 13,024 hearings (73%) have a discoverable video; 7,690 high-confidence YouTube matches in the crosswalk, plus 1,481 lower-confidence matches for review

### Removed

- One-off analysis/deliverable scripts that were superseded by the pipeline and CI

## [0.1.0] - 2026-03-14

Initial public release.

### Added

- Multi-layer matching algorithm (eventID, exact title, fuzzy title, substring, relaxed date, bill numbers)
- Pipeline scripts for fetching hearings from Congress.gov and videos from YouTube
- Unified `run_all.py` script with `--min-congress`, `--max-congress`, and `--force` options
- Title normalization (prefix stripping, date removal, punctuation handling)
- Post-processing: date sanity filter and deduplication
- Crosswalk output for congresses 111–119 (2009–present): 3,920 high-confidence matches from 13,024 hearings
- Documentation following the Diataxis framework (tutorial, how-to guides, explanation, reference)

### Coverage

- 119th Congress: 60.0% match rate
- 117th Congress: 71.6% match rate (best)
- 111th–112th Congress: ~3% match rate (limited YouTube availability in that era)
