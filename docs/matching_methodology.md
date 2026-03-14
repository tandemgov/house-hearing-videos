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

### Layer 4: Fuzzy title + relaxed date (Confidence: 0.50–0.75)

Same fuzzy matching as Layer 3, but the date window expands to ±3 days. Confidence factors in both the fuzzy ratio and date distance.

**Why the wider window?** Some committees have inconsistent upload schedules. The trade-off is lower confidence — matches from this layer are excluded from the primary `crosswalk.csv` output.

### Layer 5: Bill numbers (Confidence: 0.40–0.65)

Extracts bill numbers (H.R., S., H.Res., etc.) from hearing titles and video titles/descriptions. Matches when at least one bill number is shared. Date proximity within 7 days provides a bonus.

**Why so low confidence?** Bill numbers are not unique to a single hearing — the same bill may be discussed across multiple hearings. This layer captures matches that title-based approaches miss, but with lower reliability.

## Committee scoping

Videos are only compared against hearings from the same committee. For subcommittee hearings, the parent committee's YouTube channel is also checked, since subcommittees rarely have their own channels. This prevents cross-committee false positives (e.g., two committees holding hearings on the same topic on the same day).

## Post-processing

### Date sanity filter

Matches below 0.95 confidence are rejected if the video publish date is more than 30 days from the hearing date. This catches false positives from generic title matches that happen to score well across different time periods.

### Deduplication

When multiple hearings match the same video, only the highest-confidence match is kept. The others are marked `no_match_deduped`. This reflects the assumption that one video corresponds to one hearing.

## Known limitations

1. **Committees that don't post full hearings**: Several committees (Homeland Security, Ways & Means, Oversight) primarily post clips and opening statements rather than full hearing recordings, resulting in low match rates for those committees.
2. **No eventID ground truth for benchmarking**: The 118th Congress House hearings have no eventIDs, so there is no authoritative dataset to validate against.
3. **Multi-part hearings**: Hearings spanning multiple days may match to only one video.
4. **Title divergence**: Some committees use significantly different titles on YouTube than the official hearing title, which may not be captured by fuzzy matching.
