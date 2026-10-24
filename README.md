# House Hearing Video Coverage

How much of the public record of House committee hearings is accessible on video? This project answers that question by cross-referencing Congress.gov hearing records, committee YouTube channels, and the Congress.gov committee-meeting API.

## The coverage picture

Across the 111th–119th Congresses (2009–present), **25% of House hearings have no discoverable video recording from any source** — not on a committee YouTube channel, not linked from the Congress.gov committee-meeting API.

| Congress | Years | Hearings | Video found | Coverage | No video |
|---|---|---|---|---|---|
| 119th | 2025–26 | 657 | 629 | 96% | 28 |
| 118th | 2023–24 | 1,395 | 1,384 | 99% | 11 |
| 117th | 2021–22 | 1,134 | 1,069 | 94% | 65 |
| 116th | 2019–20 | 1,364 | 1,319 | 97% | 45 |
| 115th | 2017–18 | 1,420 | 1,313 | 92% | 107 |
| 114th | 2015–16 | 1,682 | 1,475 | 88% | 207 |
| 113th | 2013–14 | 1,739 | 1,126 | 65% | 613 |
| 112th | 2011–12 | 2,018 | 1,041 | 52% | 977 |
| 111th | 2009–10 | 1,895 | 675 | 36% | 1,220 |
| **Total** | | **13,304** | **10,031** | **75%** | **3,273** |

Congress.gov data as of October 24, 2026; YouTube channel data as of March 2026.

"Video found" means a video link was discovered from any source: our YouTube matching pipeline, the Congress.gov committee-meeting API, or both. Of the 10,031, our pipeline matched 9,873 to YouTube (7,365 in the crosswalk via methods with measured precision ≥ 95%, plus 2,508 lower-precision candidates for manual review); the remaining 158 have a Congress.gov API video link but no YouTube match. "No video" means no video link was found from any source.

### YouTube match rate by committee

Match rates vary widely — some committees post full hearings reliably, others post clips or nothing. (These are pipeline-to-YouTube match rates; a few unmatched hearings still have a Congress.gov API video link.)

| Committee | Hearings | Matched | Match rate |
|---|---|---|---|
| Energy & Commerce | 1,220 | 1,189 | 97% |
| Oversight & Gov Reform | 1,259 | 1,199 | 95% |
| Small Business | 658 | 584 | 89% |
| Foreign Affairs | 1,327 | 1,126 | 85% |
| Education & Workforce | 558 | 462 | 83% |
| Homeland Security | 738 | 595 | 81% |
| Science, Space & Technology | 692 | 554 | 80% |
| Financial Services | 1,060 | 846 | 80% |
| Natural Resources | 644 | 426 | 66% |
| Judiciary | 973 | 622 | 64% |
| Veterans' Affairs | 644 | 365 | 57% |
| Transportation & Infrastructure | 673 | 336 | 50% |
| Appropriations | 469 | 234 | 50% |
| Armed Services | 1,025 | 505 | 49% |

## What this project produces

1. **A coverage report** — per-hearing data on whether video exists, from which source, and where the gaps are
2. **A crosswalk** — 7,365 hearing-to-YouTube links from matching methods with measured precision ≥ 95%, plus 2,508 lower-precision candidates flagged for manual review
3. **Net-new links** — 3,527 high-precision hearing-to-YouTube links that Congress.gov doesn't currently have, plus 2,297 more in the review queue

### How "net new" is verified

We cross-reference every match against the Congress.gov committee-meeting API, which sometimes already has YouTube links. Hearings are checked both by eventID and by jacket number (via the full meeting list endpoint). A match is "net new" only if the API has no video for that hearing through either lookup.

## Examples

The matching algorithm handles real-world messiness in how hearings and videos are titled:

**Fuzzy title match** (confidence: 0.89) — A typo on Congress.gov ("ADMINSTRATION") would break an exact match, but fuzzy matching catches it:

> [Hearing](https://www.congress.gov/event/117th-congress/house-event/LC67774/text): *THE BIDEN ADMINSTRATION'S EFFORTS TO DEEPEN U.S. ENGAGEMENT IN THE CARIBBEAN*
> [Video](https://www.youtube.com/watch?v=zgsQHLIH4wE): *The Biden Administration's Efforts to Deepen U.S. Engagement in the Caribbean*

**Exact title match** (confidence: 0.95) — Title normalization strips casing and prefix differences:

> [Hearing](https://www.congress.gov/event/119th-congress/house-event/118171): *ASSURING ABUNDANT, RELIABLE AMERICAN ENERGY TO POWER INNOVATION*
> [Video](https://www.youtube.com/watch?v=tj2UUucNc50): *Hearing on Assuring Abundant, Reliable American Energy to Power Innovation*

**Substring match** (confidence: 0.88) — YouTube truncates the long official title and adds a prefix:

> [Hearing](https://www.congress.gov/event/119th-congress/house-event/LC75252): *WATER RESOURCES DEVELOPMENT ACT OF 2026: STAKEHOLDER PRIORITIES*
> [Video](https://www.youtube.com/watch?v=n7xQ38K7Axc): *Subcommittee Hearing on "Water Resources Development Act of 2026: Stakeholder Priorities"*

## How it works

The pipeline fetches hearing metadata from Congress.gov and video metadata from 45 YouTube channels across 28 committees, then applies thirteen matching strategies — from direct API video links through fuzzy title matching, token-set matching, bill-number extraction, date+description keyword disambiguation, and same-committee/same-date fallback matching. Committee codes are cross-referenced between the hearing API and the committee-meeting API to catch data quality issues. Post-processing filters out implausible matches and resolves duplicates.

Every run also measures its own precision: where the committee-meeting API links its own video for a matched hearing, the pipeline checks whether it picked the same one. Only methods that measured ≥ 95% precision on that check are admitted to `crosswalk.csv`; matches from lower-precision methods (26–65% measured) are kept in `all_matches.csv` as a manual-review queue.

For a deeper explanation, see [Matching Methodology](docs/matching_methodology.md).

## Documentation

This project's documentation follows the [Diataxis](https://diataxis.fr/) framework:

| If you want to... | Go to |
|---|---|
| **Get started** running the pipeline for the first time | [Tutorial](docs/tutorial.md) |
| **Accomplish a specific task** (re-run, extend, develop) | [How-to Guides](docs/how-to-guides.md) |
| **Understand** why the matching algorithm works the way it does | [Matching Methodology](docs/matching_methodology.md) |
| **Look up** output column definitions | [Data Dictionary](docs/data_dictionary.md) |
| **Look up** which committees have YouTube channels | [Committee Channels](docs/committee_channels.md) |

## Quick reference

```
data/output/crosswalk.csv           Matches from methods with measured precision >= 95%
data/output/all_matches.csv         All hearings, including the review queue and unmatched
data/output/validation_report.json  Coverage statistics, method breakdown, measured precision
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Related work

- [abigailhaddad/hearings](https://github.com/abigailhaddad/hearings) — Analysis of congressional hearing data
- [Leschonander/SenateVideoScraper](https://github.com/Leschonander/SenateVideoScraper) — Scraper for Senate committee hearing videos
- [Leschonander/SenateVideoScraperWebsite](https://github.com/Leschonander/SenateVideoScraperWebsite) — Web frontend for Senate hearing video data
- [senatecommitteehearings.com](https://senatecommitteehearings.com/about/) — Archive of Senate committee hearing links
- [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) — Community-maintained data on committees and legislators (used by this project for YouTube channel IDs)

## License

This project is dedicated to the public domain under [CC0 1.0](LICENSE). You may copy, modify, and distribute the work, even for commercial purposes, without asking permission.
