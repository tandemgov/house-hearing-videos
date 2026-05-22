# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Committee-meeting API cross-referencing: every match is checked against the Congress.gov committee-meeting API (by eventID and by jacket number) to flag `net_new` and `api_has_video`, and classified into coverage categories A–D
- Committee-code discrepancy detection between the hearing API and the committee-meeting API
- 7 select/special committee channels and 17 supplemental majority/party channels (45 channels across 28 committees), discovered via manual oEmbed verification
- Additional matching layers: token-set, substring, date+description keyword disambiguation, and same-committee/same-date fallbacks (13 methods total)
- GitHub Actions weekly pipeline run with automated coverage-trend tracking
- `loc_id` (Library of Congress identifier) column in the output

### Changed

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
