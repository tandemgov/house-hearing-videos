# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
