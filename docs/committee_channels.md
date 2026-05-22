# Committee YouTube Channels

YouTube channel data is sourced from the [`unitedstates/congress-legislators`](https://github.com/unitedstates/congress-legislators) repository's `committees-current.yaml` file.

## House Committees with YouTube Channels (118th Congress)

| Committee | System Code | Has YouTube | Posts Full Hearings | Match Rate |
|-----------|-------------|-------------|-------------------|------------|
| Agriculture | hsag00 | Yes | Yes | High |
| Appropriations | hsap00 | Yes | Yes | High |
| Armed Services | hsas00 | Yes | Partial | Medium |
| Financial Services | hsba00 | Yes | Yes | High |
| Budget | hsbu00 | Yes | Yes | High |
| Education & Workforce | hsed00 | Yes | Yes | High |
| Foreign Affairs | hsfa00 | Yes | Yes | High |
| Oversight & Accountability | hsgo00 | Yes | Clips only | Low |
| Administration | hsha00 | Yes | Yes | High |
| Homeland Security | hshm00 | Yes | Clips only | Low |
| Energy & Commerce | hsif00 | Yes | Yes | High |
| Natural Resources | hsii00 | Yes | Clips only | Low |
| Judiciary | hsju00 | Yes | Yes | Very High |
| Transportation & Infrastructure | hspw00 | Yes | Yes | High |
| Rules | hsru00 | Yes | Yes | Medium |
| Small Business | hssm00 | Yes | Yes | Medium |
| Science, Space & Technology | hssy00 | Yes | Yes | High |
| Veterans' Affairs | hsvr00 | Yes | Partial | Low |
| Ways & Means | hswm00 | Yes | No (legacy only) | None |
| Intelligence | hlig00 | Yes | Yes | Medium |

## Select/Special Committees and Commissions

These committees are not in the `congress-legislators` YAML and are defined manually in `src/committees.py`:

| Committee | System Code | YouTube Handle | Channel ID |
|-----------|-------------|----------------|------------|
| Climate Crisis Select | hlcn00 | @HouseClimateCrisis | UCqTxfzU6vYZ2-DW-y5jYvdQ |
| January 6th Select | hlij00 | @January6thCmte | UCqSRsknSiyLARtzmop9dvhw |
| Modernization Select | hlmh00 | @selectcommitteeonthemodern9383 | UCECZaLBqABxBqN7VdtZ5sCA |
| Benghazi Select | hlzi00 | @theu.s.houseselectcommitte1053 | UCiKI7qlQqr3GfFlIzOdT_Yg |
| China Strategic Competition | hszs00 | @ChinaSelect | UCpXe-EZd7pE7QM1daNAk0mA |
| CECC (China Commission) | jcpk00 | @ChinaCommission | UCRAT_7MIzUolORlJhYBTzHA |
| Helsinki Commission | jcse00 | @HelsinkiCommission | UCtFO3w68Kumz7tRyspaqF2g |

These channels were discovered through a manual spot-check process in March 2026: the `committees-current.yaml` from `congress-legislators` has no entries for select/special committees, so each channel was found by web search and then confirmed by checking a known hearing video ID against the channel's uploads via YouTube oEmbed. Adding these seven channels lifted several committees from near-zero to 50–90% match rates (e.g. Climate Crisis 0% → 89%, Modernization 5% → 91%).

## Majority-Party Channels (Extra Channels)

The `congress-legislators` YAML often lists the minority/Democrats channel. These majority-party channels are configured as `EXTRA_CHANNELS` in `src/committees.py`:

| Committee | System Code | YouTube Handle | Channel ID |
|-----------|-------------|----------------|------------|
| Oversight/Gov Reform | hsgo00 | @OversightandGovernmentReform | UCn8TJ6Tyq2aGvhybME_itDQ |
| Energy & Commerce | hsif00 | @energyandcommerce | UC5s1kIfkfWbap31d5ef-VtQ |
| Budget | hsbu00 | @HouseBudgetGOP | UCHPaSWprI94UTePSMv0tqnw |
| Foreign Affairs | hsfa00 | @HouseForeignGOP | UCtxAmeCl0xtSuo7tHZpgcQA |
| House Administration | hsha00 | @CommitteeonHouseAdministration | UC8dXTgFnWF8NraBKhF040Qg |
| Education & Workforce | hsed00 | @EdWorkforceCmte | UC8Ewe7WqGg01KRNjJCO5cjg |
| Rules | hsru00 | @HouseRulesCommittee | UCDNcorctkmOpBfr4sgu6t3w |
| Agriculture | hsag00 | @AgRepublicans | UCWtWf-QUTnJ-UMP5ZNWVB5Q |
| Financial Services (GOP) | hsba00 | @GOPFinancialServices | UCDQFSLK68yQLJPb8E9ZWmQQ |
| Small Business | hssm00 | @HouseSmallBiz | UCoXvuW2IhFawuNyk4yL3EkQ |
| Oversight (archive) | hsgo00 | @HouseResourceOrg | UCuwpe69VxVzy4maI6ymmm6A |

## Committees Without YouTube Channels

Some committees and most subcommittees do not have their own YouTube channels. Subcommittee hearings are matched against the parent committee's channel.

Notable committees with no known YouTube channel:
- Energy Independence & Global Warming Select (hlgw00) — defunct, 111th Congress only
- 94 hearings with no committee code assigned (data quality issue from Congress.gov)

## Known select-committee gaps

Even with the channels above configured, some select/special committees still match poorly. These are the open cases worth investigating:

| Committee | Code | Symptom | Likely cause |
|-----------|------|---------|--------------|
| Benghazi Select | hlzi00 | 0% — channel has videos but none match | Titles/dates on YouTube don't align with the hearing records |
| CECC (China Commission) | jcpk00 | ~25% | Title-format differences between the API and the channel |
| January 6th Select | hlij00 | ~31% | Repeated generic titles ("HEARING ON THE JANUARY 6TH INVESTIGATION") across multiple dates collide during deduplication |
| China Strategic Competition | hszs00 | 0 hearings fetched | The hearing API returns nothing for this committee, so there is nothing to match |

## Notes

- The `congress-legislators` YAML was last updated when Democrats held the majority, so many entries point to Democrats-only channels that post clips rather than full hearings
- Channel IDs use the `UC` prefix; uploads playlists use `UU` (swap the prefix)
- Match rates vary significantly by congress — older congresses (111th–113th) have low rates because committees hadn't adopted YouTube yet
