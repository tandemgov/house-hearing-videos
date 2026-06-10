# Tutorial: Run the pipeline for the first time

This tutorial walks you through setting up the project and running the full hearing-to-YouTube matching pipeline. By the end, you'll have a CSV crosswalk linking House hearings to their YouTube videos.

**Time:** ~15 minutes (plus API fetch time)
**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/) package manager

## 1. Install dependencies

Clone the repository and install dependencies:

```bash
git clone <repo-url>
cd house-hearing-videos
uv sync
```

## 2. Set up API keys

The pipeline needs two API keys:

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

- **Congress.gov API key** — Register at [api.congress.gov](https://api.congress.gov). A `DEMO_KEY` works but has strict rate limits.
- **YouTube Data API v3 key** — Create one in the [Google Cloud Console](https://console.cloud.google.com). Enable the "YouTube Data API v3" for your project.

## 3. Run the pipeline

The simplest way to run everything is the unified pipeline script:

```bash
uv run python scripts/run_all.py
```

This will:

1. **Fetch YouTube videos** from all House committee channels
2. **Fetch hearing metadata** from Congress.gov (for each congress in range)
3. **Match** hearings to videos using the multi-layer algorithm
4. **Validate** matches with date-sanity and deduplication checks
5. **Export** results to CSV

The script prints progress as it runs. Expect the initial fetch to take several minutes due to API rate limits. Subsequent runs use cached data and are much faster.

## 4. Explore the results

Once the pipeline completes, you'll find three output files:

```
data/output/crosswalk.csv           Matches from methods with measured precision >= 95%
data/output/all_matches.csv         All hearings (including the review queue and unmatched)
data/output/validation_report.json  Coverage statistics and measured precision
```

Open `crosswalk.csv` to see matched hearings. Each row links a hearing to a YouTube video:

| Column | What it tells you |
|---|---|
| `hearing_title` | The official hearing title from Congress.gov |
| `youtube_url` | Direct link to the YouTube video |
| `match_confidence` | The algorithm's assigned confidence score (kept for context; crosswalk inclusion is by method) |
| `match_method` | Which matching strategy produced this result |

For the full column list, see the [Data Dictionary](data_dictionary.md).

## 5. Run individual steps (optional)

If you prefer to run each pipeline step separately:

```bash
uv run python scripts/01_fetch_hearings.py    # Fetch hearing metadata
uv run python scripts/02_fetch_videos.py      # Fetch YouTube video metadata
uv run python scripts/03_match.py             # Run matching algorithm
uv run python scripts/04_validate.py          # Validate and report
uv run python scripts/05_export.py            # Export to CSV
uv run python scripts/06_fetch_meetings.py    # Fetch committee-meeting API data (net-new check)
```

This is useful for debugging or re-running a single step after changing parameters.

## Next steps

- [How-to Guides](how-to-guides.md) — Process a different congress, bypass the cache, or set up a development environment
- [Matching Methodology](matching_methodology.md) — Understand why matches have the confidence scores they do
- [Data Dictionary](data_dictionary.md) — Full schema for output files
