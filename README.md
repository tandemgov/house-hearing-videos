# House Hearing Video Crosswalk

An automated system that links U.S. House committee hearings (from Congress.gov) to their YouTube video recordings — closing a gap in the public record where many hearing videos are difficult to find.

## Why this matters

Congress.gov provides official records for House committee hearings, but links to video recordings are often missing. Many hearing records lack the `eventID` needed to connect to committee video pages, making it hard for researchers, journalists, and the public to find video of hearings they care about.

This project builds that missing link automatically using a multi-layer matching algorithm that pairs hearings to videos by committee, date, and title similarity.

## Results

Across the 111th–119th Congresses (2009–present):

- **13,024 hearings** processed across 20+ committees
- **3,920 matched** to YouTube videos at high confidence (score >= 0.70)

| Congress | Years | Hearings | Matched | Rate |
|---|---|---|---|---|
| 119th | 2025–26 | 370 | 222 | 60.0% |
| 118th | 2023–24 | 1,301 | 808 | 62.1% |
| 117th | 2021–22 | 1,139 | 816 | 71.6% |
| 116th | 2019–20 | 1,375 | 896 | 65.2% |
| 115th | 2017–18 | 1,429 | 492 | 34.4% |
| 114th | 2015–16 | 1,694 | 388 | 22.9% |
| 113th | 2013–14 | 1,753 | 173 | 9.9% |
| 112th | 2011–12 | 2,044 | 63 | 3.1% |
| 111th | 2009–10 | 1,919 | 62 | 3.2% |

Match rates are highest for recent congresses where committees have established consistent YouTube publishing practices.

The output is a CSV crosswalk file linking each matched hearing to its YouTube video, with confidence scores and match methods. A [sample CSV](data/output/sample_matches.csv) is included in the repository.

## Examples

The matching algorithm handles real-world messiness in how hearings and videos are titled. Here are actual matches from the crosswalk, illustrating what each layer catches:

**Exact eventID** (confidence: 1.0) — The rare ideal case, where Congress.gov provides a direct link:

> [Hearing](https://congress.gov/115/chrg/CHRG-115hhrg24726/generated/CHRG-115hhrg24726.htm): *SECTION 702 OF THE FOREIGN INTELLIGENCE SURVEILLANCE ACT*
> [Video](https://www.youtube.com/watch?v=5yriRmNvsXc): *Section 702 of the Foreign Intelligence Surveillance Act EventID=105619*

**Exact title after normalization** (confidence: 0.95) — Titles differ only in casing and prefixes, which normalization strips away:

> [Hearing](https://congress.gov/119/chrg/CHRG-119hhrg61954/generated/CHRG-119hhrg61954.htm): *USDA'S RURAL DEVELOPMENT: DELIVERING VITAL PROGRAMS AND SERVICES TO RURAL AMERICA*
> [Video](https://www.youtube.com/watch?v=j4qNJL4c8zs): *USDA's Rural Development: Delivering Vital Programs and Services to Rural America*

**Fuzzy title match** (confidence: 0.89) — A typo on Congress.gov ("ADMINSTRATION") that would break an exact match but fuzzy matching catches:

> [Hearing](https://congress.gov/117/chrg/CHRG-117hhrg46573/generated/CHRG-117hhrg46573.htm): *THE BIDEN ADMINSTRATION'S EFFORTS TO DEEPEN U.S. ENGAGEMENT IN THE CARIBBEAN*
> [Video](https://www.youtube.com/watch?v=zgsQHLIH4wE): *The Biden Administration's Efforts to Deepen U.S. Engagement in the Caribbean*

**Fuzzy title match** (confidence: 0.89) — Spelling variation ("Combating" vs. "Combatting"):

> [Hearing](https://congress.gov/118/chrg/CHRG-118hhrg51256/generated/CHRG-118hhrg51256.htm): *COMBATING THE GENERATIONAL CHALLENGE OF CCP AGGRESSION*
> [Video](https://www.youtube.com/watch?v=GQ3KslanAEs): *Combatting the Generational Challenge of CCP Aggression*

**Substring match** (confidence: 0.85) — YouTube truncates the long official title and adds a prefix:

> [Hearing](https://congress.gov/119/chrg/CHRG-119hhrg60119/generated/CHRG-119hhrg60119.htm): *AGING TECHNOLOGY, EMERGING THREATS: EXAMINING CYBERSECURITY VULNERABILITIES IN LEGACY MEDICAL DEVICES*
> [Video](https://www.youtube.com/watch?v=PCvyk6l5Wa0): *Hearing on Examining Cybersecurity Vulnerabilities in Legacy Medical Devices*

53% of all matches in the crosswalk have **no eventID** — meaning they would not be discoverable through Congress.gov's built-in links.

## How it works

The pipeline fetches hearing metadata from Congress.gov and video metadata from YouTube, then applies six matching strategies — from exact ID lookup down to fuzzy title matching and bill-number extraction. Each strategy produces a confidence score. Post-processing filters out implausible matches and resolves duplicates.

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
data/output/crosswalk_all.csv          High-confidence matches (>= 0.70)
data/output/all_matches_all.csv        All hearings, including unmatched
data/output/validation_report_all.json  Coverage statistics
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
