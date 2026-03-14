# How-to Guides

Task-oriented recipes for common operations. Each guide assumes you've completed the [Tutorial](tutorial.md) and have a working environment.

---

## Process a specific congress

By default, the pipeline processes all congresses in the configured range. To target a single congress:

```bash
uv run python scripts/run_all.py --min-congress 117 --max-congress 117
```

## Force a fresh data fetch

The pipeline caches API responses to avoid redundant requests. To bypass the cache and re-fetch everything:

```bash
uv run python scripts/run_all.py --force
```

This is useful after upstream data changes on Congress.gov or YouTube.

## Interpret match confidence scores

Each match has a `match_confidence` score and a `match_method`. Use these together to assess reliability:

| Confidence | Meaning |
|---|---|
| **1.0** | Exact eventID match — essentially ground truth |
| **0.90–0.95** | Titles match exactly or nearly exactly, dates align |
| **0.70–0.89** | Fuzzy title match with close dates — high confidence |
| **0.50–0.69** | Weaker signal (relaxed dates or bill-number matching) — excluded from `crosswalk.csv` |
| **< 0.50** | Low confidence — excluded from `crosswalk.csv` |

Only matches scoring >= 0.70 appear in `crosswalk.csv`. All matches (including low-confidence and unmatched hearings) are in `all_matches.csv`.

## Investigate unmatched hearings

To find hearings that didn't match to any video:

1. Open `data/output/all_matches.csv`
2. Filter to `match_method = no_match` or `match_method = no_match_deduped`

Common reasons a hearing goes unmatched:

- The committee posts clips instead of full hearing recordings (see [Committee Channels](committee_channels.md))
- The YouTube title diverges significantly from the official hearing title
- The video was uploaded much later than the hearing date

## Set up a development environment

Install all dependencies including dev tools:

```bash
uv sync --all-extras
```

Run the test suite:

```bash
uv run pytest
```

Run the linter:

```bash
uv run ruff check src/ tests/ scripts/
```

## Add a new matching strategy

Matching layers are defined in `src/match.py`. To add a new strategy:

1. Write a function that takes a hearing and a list of candidate videos and returns a match dict with `youtube_video_id`, `match_confidence`, and `match_method`
2. Add your function to the layer chain in `match_all_hearings()`
3. Assign a confidence range that doesn't overlap with existing layers
4. Add tests in `tests/`

See [Matching Methodology](matching_methodology.md) for how the existing layers work and interact.
