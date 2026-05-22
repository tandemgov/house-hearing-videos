# Matching Methodology

This document explains *why* the matching algorithm works the way it does — the design decisions, trade-offs, and limitations behind each layer.

## The core problem

House committees publish hearing records on Congress.gov and upload video recordings to YouTube, but these two systems are not reliably linked. The `eventID` field that *should* connect them is missing from most House hearing records. Without it, there's no authoritative join key.

This project bridges that gap by matching on the information that *is* available: committee identity, hearing dates, and titles. Because none of these are perfect identifiers on their own, the algorithm uses multiple layers of progressively looser matching.

## Why a layered approach

A single matching strategy can't handle the variety of data quality across committees. Some committees use identical titles on Congress.gov and YouTube; others add prefixes, abbreviate, or completely rephrase. Some upload videos on the hearing date; others upload days later.

The layered approach lets us:

- **Maximize precision for easy cases** (exact eventID or title matches)
- **Recover harder matches** (fuzzy titles, relaxed dates) without contaminating the easy ones
- **Assign meaningful confidence scores** that reflect how much evidence supports each match

Each layer only considers hearings not yet matched by a higher-confidence layer.

## Title normalization

Before any title comparison, both hearing titles and video titles are normalized to remove noise that would cause false mismatches:

1. **Lowercase** the entire title
2. **Strip common prefixes**: "Full Committee Hearing:", "Hearing on", "Markup of", "Hearing entitled", "Subcommittee Hearing", "Legislative Hearing", "Oversight Hearing", "Field Hearing"
3. **Strip trailing quotes** (straight and curly)
4. **Remove embedded dates**: Both written (e.g., "January 15, 2024") and numeric (e.g., "01/15/2024")
5. **Remove punctuation**: Replace all non-alphanumeric characters with spaces
6. **Collapse whitespace**: Multiple spaces to single space, trim edges

These steps reflect observed patterns in how Congress.gov titles and YouTube titles differ for the same hearing.

## Matching layers in detail

### Layer 1: Event ID (Confidence: 1.0)

If a hearing has an `associatedMeeting.eventID`, search for that ID in the video's title and description. This is the closest thing to ground truth, but it is rarely available for House hearings — which is the whole reason this project exists.

### Layer 2: Exact title + nearby date (Confidence: 0.95)

Normalized titles must match exactly, and the video's publish date must be within ±1 day of the hearing date.

**Why ±1 day?** Committees frequently upload videos the day after a hearing. A strict same-day requirement would miss these.

**Why 0.95 and not 1.0?** Title normalization could theoretically produce a false collision (two different hearings normalizing to the same string). The 0.05 discount reflects that small risk.

### Layer 3: Fuzzy title + nearby date (Confidence: 0.70–0.90)

Uses token-sort-ratio from the `thefuzz` library with a threshold of 80%. Date must be within ±1 day. Confidence scales linearly: 80% ratio = 0.70, 100% ratio = 0.90.

**Why token-sort-ratio?** It handles word reordering (common when committees rearrange title components) better than simple sequence matching.

**Why 80% threshold?** Below 80%, false positive rates increase sharply in testing. This threshold balances recall against precision.

### Layer 3b: Substring + nearby date (Confidence: 0.80–0.88)

Checks if one normalized title is a substring of the other (minimum 15 characters to avoid trivial matches). Date must be within ±1 day.

**Why a separate layer?** Some committees prepend or append boilerplate to their YouTube titles. Fuzzy matching penalizes this extra text, but substring matching handles it cleanly.

### Layer 3c: Token-set ratio + nearby date (Confidence: 0.55–0.68)

Uses `token_set_ratio` from the `thefuzz` library instead of `token_sort_ratio`. This metric asks: "are all the words from the shorter title present in the longer one?" It requires a threshold of 85%, both normalized titles to be at least 10 characters, and `token_sort_ratio` to be below 80% (otherwise Layer 3 would already have matched).

**Why a separate layer?** Some hearings have short, keyword-rich titles (e.g., "THE JFK FILES") while the corresponding video has a much longer descriptive title ("Task Force on the Declassification of Federal Secrets: the JFK Files"). `token_sort_ratio` gives only ~32% for this pair because of the length mismatch, but `token_set_ratio` gives 100% because all tokens from the short title appear in the long one.

**Why below 0.70 confidence?** `token_set_ratio` is generous — common government jargon can cause coincidental overlaps. Keeping confidence below 0.70 ensures these matches appear only in `all_matches.csv` for manual review, not in the primary crosswalk.

### Layer 4: Fuzzy title + relaxed date (Confidence: 0.50–0.75)

Same fuzzy matching as Layer 3, but the date window expands to ±3 days. Confidence factors in both the fuzzy ratio and date distance.

**Why the wider window?** Some committees have inconsistent upload schedules. The trade-off is lower confidence — matches from this layer are excluded from the primary `crosswalk.csv` output.

### Layer 5: Bill numbers (Confidence: 0.40–0.65)

Extracts bill numbers (H.R., S., H.Res., etc.) from hearing titles and video titles/descriptions. Matches when at least one bill number is shared. Date proximity within 7 days provides a bonus.

**Why so low confidence?** Bill numbers are not unique to a single hearing — the same bill may be discussed across multiple hearings. This layer captures matches that title-based approaches miss, but with lower reliability.

## Committee scoping and cross-referencing

Videos are only compared against hearings from the same committee. For subcommittee hearings, the parent committee's YouTube channel is also checked, since subcommittees rarely have their own channels. This prevents cross-committee false positives (e.g., two committees holding hearings on the same topic on the same day).

### Committee code cross-referencing

The hearing detail API and the committee-meeting API both provide committee codes for hearings. These sometimes disagree — for example, jacket 60494 (119th Congress) was tagged `hlse00` (defunct House Aging Select Committee) in the hearing API, but correctly attributed to the China Select Committee (`hlzs00`) in the committee-meeting API.

The pipeline cross-references both sources via `enrich_hearing_with_meeting_data()`:

1. Builds a jacket→meeting map from the committee-meeting API's `hearingTranscript` fields
2. For each hearing, looks up its jacket in the meeting map
3. Merges committee codes from both sources into `effective_committee_codes`
4. Flags discrepancies for logging
5. Fills in missing `event_id` from the meeting map when the hearing API lacks one

Matching uses the merged `effective_committee_codes`, so a hearing miscoded in one API can still match against the correct committee's YouTube videos.

**Why not use the meeting API's jacket→video links for matching?** The `hearingTranscript` field sometimes links unrelated jacket numbers to the same meeting. Using those links for direct matching caused incorrect matches and excessive deduplication. The jacket→meeting map is used only for committee code enrichment and `api_has_video` classification.

### Committee code aliases

The meeting API sometimes uses different system codes than the canonical codes in the committee map (e.g., `hlzs00` for the China Select Committee vs `hszs00` in our committee definitions). A code alias mapping resolves these before committee matching.

## Post-processing

### Date sanity filter

Matches below 0.95 confidence are rejected if the video publish date is more than 30 days from the hearing date. This catches false positives from generic title matches that happen to score well across different time periods.

### Deduplication

When multiple hearings match the same video, only the highest-confidence match is kept. The others are marked `no_match_deduped`. This reflects the assumption that one video corresponds to one hearing.

### Description date extraction

Many committees embed the hearing date in the video description (e.g., "On Wednesday, September 10, 2025, at 2:00 p.m. ..."). The pipeline extracts these dates and uses them alongside `published_at` for date matching in Layers 2–4. This is important because YouTube's `published_at` reflects when the recording was made public, which can be 1–3 days after a livestreamed hearing.

### Fallback: Date + description keywords (Confidence: 0.75–0.85)

When all title-based layers fail, a fallback layer matches by committee + date + keyword overlap between the hearing title and the video's title and description. This handles cases where committees use entirely different naming conventions on Congress.gov vs YouTube (e.g., Congress.gov: "DEPARTMENTS OF LABOR, HEALTH AND HUMAN SERVICES, EDUCATION, AND RELATED AGENCIES APPROPRIATIONS FOR 2025"; YouTube: "Budget Hearing – Fiscal Year 2025 Request for the Department of Health and Human Services").

Three modes:
- **Unique date match** (0.85): If exactly one video exists for that committee on that date, it's matched directly — the date+committee uniqueness is sufficient evidence.
- **Keyword disambiguation** (0.75–0.85): If multiple videos exist on the same date, the hearing title keywords are compared against each video's title+description. The best candidate is selected only if it clearly outscores the second-best (≥0.15 ratio gap, ≥30% overlap, ≥3 matching words).
- **Relaxed keyword disambiguation** (0.45–0.60): A looser tier that fires when the strict keyword tier doesn't — requiring only ≥0.10 ratio gap, ≥15% overlap, and ≥1 matching word. This handles cases with short hearing titles that have few keywords.

The date window for all fallback modes is ±2 days (wider than the ±1 day used by title-based layers).

### Last resort: Committee + date only (Confidence: 0.20–0.30)

When all other layers and fallbacks fail, a final catch-all matches purely by committee and date (±2 days), with no text matching at all. If exactly one video exists for that committee on that date, it matches at 0.30 confidence. If multiple candidates exist, the one with the highest `token_set_ratio` is picked at 0.20–0.30 confidence.

**Why include this?** Some committees use entirely generic video titles (e.g., Rules Committee posts every video as "Rules Committee Hearing H.R. ____"; Natural Resources uses "Legislative Hearing | [Subcommittee Name]") with empty descriptions. Title-based matching is impossible for these. At very low confidence, these matches appear only in `all_matches.csv` for manual review — they never contaminate the primary crosswalk.

## Known limitations

1. **Committees that don't post full hearings**: Several committees (Homeland Security, Ways & Means, Oversight) primarily post clips and opening statements rather than full hearing recordings, resulting in low match rates for those committees.
2. **No eventID ground truth for benchmarking**: The 118th Congress House hearings have no eventIDs, so there is no authoritative dataset to validate against.
3. **Multi-part hearings**: Hearings spanning multiple days may match to only one video.
4. **Title divergence**: Some committees use significantly different titles on YouTube than the official hearing title, which may not be captured by fuzzy matching. A known case is Financial Services, which truncates long titles with "..." on YouTube, causing fuzzy match scores to fall just below the 80% threshold.
5. **Majority/minority channel split**: The `congress-legislators` YAML may point to a minority-party channel (e.g., House Administration Democrats) rather than the majority channel that hosts full hearings. This causes the pipeline to find only clips, not full recordings.
6. **Generic video titles**: Some committees (Rules, Natural Resources) use template titles that carry no hearing-specific information. The committee+date fallback handles these, but when multiple hearings occur on the same day, the match is a best guess that requires manual review.
7. **Low-confidence matches need review**: The aggressive fallback layers (confidence < 0.70) trade precision for recall. These matches appear in `all_matches.csv` but are excluded from the primary crosswalk and should be manually verified before use.
8. **Hearings with no committee code**: ~94 hearings come back from the Congress.gov hearing API with an empty `committeeCode`. They can't be scoped to any channel and are therefore unmatchable — a data-quality issue upstream, not a matching failure.

## Future work

These are known opportunities to raise coverage, in rough priority order:

- **The pre-eventID era (111th–114th Congresses) dominates the gap.** Roughly 3,250 of the 3,512 "no discoverable video" hearings are from 2009–2016, before most committees adopted YouTube. The likely off-YouTube source for these is the **C-SPAN archive**, which holds committee-hearing video back to 1987. C-SPAN access for bulk crosswalking requires coordination with the Center for C-SPAN Scholarship & Engagement (CCSE) at Purdue University — there is an academic API, but it is undocumented and gated, and automated scraping of c-span.org likely violates their terms. A manual spot-check of 20–30 older unmatched hearings would quantify the potential before any integration is scoped.
- **Tune the fuzzy threshold for truncated titles.** Financial Services (and others) truncate long titles with "..." on YouTube, landing fuzzy scores at ~79 — just under the 80 threshold. A targeted normalization or a slightly lower threshold for the truncation case would recover these without broadly sacrificing precision.
- **Select/special committees with low match rates** are tracked in [Committee Channels](committee_channels.md#known-select-committee-gaps).
