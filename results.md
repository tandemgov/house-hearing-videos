# House hearing video coverage: results and next steps

This document summarizes what the project's current dataset shows about video coverage of House committee hearings on Congress.gov, and identifies specific steps that can be taken using `data/output/` as it stands today — no further matching or development work required.

Scope: 13,024 House committee hearings, 111th–119th Congresses, as listed by the Congress.gov hearings endpoint.

A note on what changed from earlier drafts of this document: the pipeline now measures its own precision against the committee-meeting API's video links (see [How much to trust the matches](#how-much-to-trust-the-matches)), and `crosswalk.csv` is gated on that measured precision rather than on hand-assigned confidence scores. The headline counts below are smaller than earlier drafts and more defensible.

## Two endpoints, one missing join key

The project draws on two Congress.gov endpoints:

- **Hearing detail API** (`/hearing/{congress}/house/{jacketNumber}`) — the canonical record of each House committee hearing, keyed by jacket number.
- **Committee-meeting API** (`/committee-meeting/{congress}/house/{eventId}`) — the record where video links, when present, are attached. Keyed by `eventID`.

The intended join key between the two is the `eventID` field on the hearing record (`associatedMeeting.eventID`). When that field is populated, a hearing can be resolved directly to its meeting record and any video link attached there.

**After cross-referencing both endpoints, 5,400 of 13,024 hearings (41%) still have no resolvable `eventID`.** The pipeline fills in missing eventIDs where the meeting API's transcript records point back to a hearing's jacket number, so the gap on the raw hearing records is larger still. From the House's side, the durable fix is to populate `associatedMeeting.eventID` on the hearing record whenever a meeting record exists for that jacket.

| | Hearings |
|---|---:|
| Hearings with a resolvable `eventID` | 7,624 |
| Hearings with no `eventID` from either endpoint | 5,400 |

## What the data shows

### Coverage totals

| | Hearings | Share |
|---|---:|---:|
| Total in scope | 13,024 | 100% |
| Has a video link in the Congress.gov committee-meeting API | 3,846 | 30% |
| Has a video on a tracked committee YouTube channel (any pipeline match) | 9,165 | 70% |
| — in `crosswalk.csv` (high-precision methods only) | 6,913 | 53% |
| — in the manual-review queue (lower-precision methods) | 2,252 | 17% |
| Has a video discoverable from either source | 9,530 | 73% |
| No video found in either source | 3,494 | 27% |

The four mutually exclusive categories used below come from `validation_report.json`:

| Category | Definition | Count |
|---|---|---:|
| A | API has a video and the pipeline matched one | 3,481 |
| B | Pipeline matched a video; API does not have one | 5,684 |
| C | API has a video; pipeline could not match one | 365 |
| D | Neither source has a video | 3,494 |

### How much to trust the matches

The committee-meeting API's video links double as an answer key: for the 3,541 matched hearings where the API links its own video, the pipeline checks whether it picked the same one. Per-method precision from that check (details and caveats in `docs/matching_methodology.md`):

- **Methods admitted to `crosswalk.csv`** measured **96–100%** precision: direct API links, eventID matching, and the title-based layers (exact, fuzzy, substring, token-set).
- **Methods kept in the review queue** measured **36–64%**: the date/keyword fallbacks and bill-number matching. Their failure mode is matching a member's clip or an unrelated same-day video, concentrated in the 111th–114th Congresses when committee channels posted clips rather than full hearings.

This is why crosswalk membership is by *method*, not by the `match_confidence` score: some low-scored methods measured near-perfect, and some high-scored methods measured poorly. The `match_confidence` column is retained for context.

Two honest caveats. The answer-key sample skews toward newer, API-covered hearings, so precision on the older net-new rows is likely somewhat lower than measured. And "agreement" tolerates alternate uploads of the same proceeding, which can include clips — rows where full-hearing footage matters should still get a sanity pass before ingestion.

### Coverage by Congress

Counts are Category D — no video in either the committee-meeting API or any tracked YouTube channel. (An earlier draft of this table mistakenly counted all pipeline-unmatched hearings, overstating the gap in recent congresses.)

| Congress | Hearings | No video in either source | Share |
|---|---:|---:|---:|
| 111 (2009–10) | 1,919 | 1,245 | 65% |
| 112 (2011–12) | 2,044 | 1,004 | 49% |
| 113 (2013–14) | 1,753 | 707 | 40% |
| 114 (2015–16) | 1,694 | 290 | 17% |
| 115 (2017–18) | 1,429 | 119 | 8% |
| 116 (2019–20) | 1,375 | 48 | 3% |
| 117 (2021–22) | 1,139 | 67 | 6% |
| 118 (2023–24) | 1,301 | 10 | 1% |
| 119 (2025–) | 370 | 4 | 1% |

The 111th–113th Congresses account for 2,956 of the 3,494 hearings with no video found (85%).

### Coverage by committee

Committee names are the historical names from Congress.gov (e.g., "Government Reform" is today's Oversight; "International Relations" is Foreign Affairs; "Banking" is Financial Services; "National Security" is Armed Services; "Public Works" is Transportation & Infrastructure; "Public Lands" is Natural Resources).

| Committee | Hearings | No video either source | Crosswalk net-new | Review-queue net-new |
|---|---:|---:|---:|---:|
| National Security (Armed Services) | 1,007 | 524 | 244 | 82 |
| Judiciary | 942 | 363 | 262 | 70 |
| Public Works (Transportation) | 660 | 331 | 19 | 94 |
| Veterans' Affairs | 603 | 273 | 71 | 73 |
| International Relations (Foreign Affairs) | 1,279 | 262 | 398 | 219 |
| Appropriations | 449 | 238 | 71 | 64 |
| Ways and Means | 410 | 236 | 11 | 86 |
| Banking (Financial Services) | 999 | 224 | 272 | 208 |
| Public Lands (Natural Resources) | 634 | 203 | 20 | 169 |
| Science and Technology | 679 | 141 | 220 | 155 |
| Homeland Security | 720 | 138 | 81 | 192 |
| Education and the Workforce | 531 | 89 | 254 | 97 |
| Agriculture | 311 | 78 | 55 | 84 |
| Small Business | 643 | 65 | 207 | 124 |
| Government Reform (Oversight) | 1,229 | 33 | 682 | 119 |

A full per-committee breakdown is in `data/output/validation_report.json` under `overall.by_committee`.

Note the pattern in Transportation, Ways & Means, and Natural Resources: large review queues, tiny crosswalk counts. These committees use generic video titles ("Legislative Hearing | [Subcommittee]"), so only the lower-precision date-based methods can propose candidates for them — manual review is the realistic path for those committees.

### Specific data-quality findings

These are concrete and limited in scope:

- **365 hearings (Category C)** have a video link in the committee-meeting API that the pipeline could not corroborate against any tracked YouTube channel. Possible causes: a channel not in the project's channel list, a removed video, or a stale URL. Each row has the API's URL on file.
- **95 hearings** in the Congress.gov hearing record have no `committee_code` populated. Without a committee code, the matching pipeline cannot route a hearing to a specific committee channel.
- **1,186 hearings** are in `no_match_deduped` — the pipeline found a candidate video but rejected it because another hearing had a stronger claim on the same video. Some portion are correct matches that need a tiebreaker rule or a manual pass.

### Net-new candidates by committee (crosswalk)

These are the rows in `crosswalk.csv` where `net_new = true`: **3,570 hearing→YouTube pairs the API does not currently have**, all from methods that measured 96–100% precision.

| Committee | Crosswalk net-new |
|---|---:|
| Government Reform (Oversight) | 682 |
| Energy and Commerce | 552 |
| International Relations (Foreign Affairs) | 398 |
| Banking (Financial Services) | 272 |
| Judiciary | 262 |
| Education and the Workforce | 254 |
| National Security (Armed Services) | 244 |
| Science and Technology | 220 |
| Small Business | 207 |
| Homeland Security | 81 |
| Veterans' Affairs | 71 |
| Appropriations | 71 |
| Agriculture | 55 |
| Select Committee on the Climate Crisis | 40 |
| Congressional-Executive Commission on China | 30 |

A further **2,114 net-new candidates sit in the review queue** (`all_matches.csv`, rows not in `crosswalk.csv`), proposed by the lower-precision methods.

## Steps that can be taken with the current dataset

Each step below uses files already produced; none require re-running the pipeline.

### 1. Add YouTube links to the 3,570 net-new crosswalk hearings

Source: `data/output/crosswalk.csv`, filter `net_new = true`.

Each row contains the keys needed to attach a video to the existing committee-meeting record: `event_id`, `jacket_number`, `loc_id`, and `youtube_url`. The pipeline does not modify Congress.gov; the act of ingestion is a House-side workflow.

Suggested order is largest-impact first, by committee (table above). Nine committees account for 3,091 of the 3,570 rows.

### 2. Manual review of the 2,114 review-queue candidates

Source: `data/output/all_matches.csv`, matched rows whose `match_method` is not in the trusted set (equivalently: matched rows absent from `crosswalk.csv`).

For each row the file provides the candidate `youtube_url`, the `match_method` that produced it, the `hearing_date`, `committee_name`, and the hearing identifiers. Measured hit rates by method give a realistic expectation of review yield: `date_description_keywords` ~64% (819 net-new rows), `date_committee_unique` ~62% (248), `date_committee_only_best_guess` ~36% (812). Most rows can be confirmed or rejected in under a minute by opening the hearing page and the video side by side; the dominant wrong answer is a member's clip from the right committee and day rather than the full hearing.

### 3. Audit the 365 Category C records

Source: hearings in `all_matches.csv` where `api_has_video = true` and the pipeline did not match.

Two things are worth checking on each row: whether the API's URL still resolves, and whether it points to a channel that the pipeline does not track. The second case identifies channels that should be added to `src/committees.py` so future runs catch them.

### 4. Populate `associatedMeeting.eventID` on hearing records that lack it

5,400 hearing records have no eventID resolvable from either endpoint. Where a corresponding committee-meeting record exists, populating this field on the hearing API restores the authoritative join between the two endpoints and removes the need for jacket-number fallbacks. The pipeline's jacket→meeting map (built in `src/fetch_meetings.py` via `enrich_hearing_with_meeting_data`) identifies which hearings already have a discoverable meeting record on the other side; that subset is the immediate candidate list.

### 5. Populate `committee_code` for the 95 records that lack one

These appear in `all_matches.csv` with an empty `committee_code`. The remedy is upstream — the value should be added to the hearing record in Congress.gov. Once populated, a single re-run of the pipeline will pick up any matches that become possible.

### 6. Older-Congress backfill (111th–113th)

The 2,956 unmatched hearings in the 111th–113th Congresses are unlikely to have a corresponding video on a current committee YouTube channel. For these, `all_matches.csv` provides the keys (`jacket_number`, `loc_id`, `govinfo_id`) needed to cross-reference C-SPAN, GovInfo, and committee archives. A practical approach is one committee at a time, sending each committee's office the filtered list of hearings with no video on file and asking whether an internal or external recording exists.

### 7. Recurring re-run

Coverage in the 117th–119th Congresses is 94–99%, and the gap will grow if not refreshed. Re-running the pipeline on a regular cadence (e.g., monthly) and ingesting any new `net_new = true` crosswalk rows would keep the API current as committees post new hearings. Each run now reports its own measured precision in `validation_report.json` (`ground_truth_precision`), so a regression in match quality is visible immediately.

## Files

```
data/output/crosswalk.csv           Matches from methods with measured precision >= 95%.
data/output/all_matches.csv         Full universe, including the review queue and unmatched rows.
data/output/validation_report.json  Category counts (A-D), per-committee totals, by-method
                                    tallies, and measured per-method precision.
```

A schema for both CSVs is in `docs/data_dictionary.md`. Matching methods, the measured-precision table, and the crosswalk gating rule are documented in `docs/matching_methodology.md`.
