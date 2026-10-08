# League-aware rest-of-season iteration

Branch: `codex/league-aware-season`, based on GitHub main `47301a5`.
Claude’s latest three merged pull requests were present before implementation;
a final fetch confirmed local main and origin/main still matched.

## Delivered

1. Scoring selection: standard half-PPR, Camden’s premium/bonus rules, Dad’s
   weekly buckets, and supported scoring fetched from a connected Sleeper league.
   Custom Flex ranks use points above starter replacement including flex demand;
   positional ranks remain ordered by points. Frozen draft inputs are untouched.
2. Sleeper ownership: My players / Available filters and read-only Roster outlook.
   A legal, unique-player optimization identifies the projected core. Comparisons
   protect current starters, reserves, and that core; evaluate same-position bench
   replacements; require a 15-point and 20% ROS edge; show starter improvement.
3. Reliability: shared atomic raw source cache with original network-read dates,
   separate five-minute ownership refresh, explicit unsupported-scoring errors,
   missing-player and unexplained-week-gap advice gates, and failed-refresh advice
   gating while dated rankings remain available. History is locked and namespaced
   by season/scoring so profiles cannot overwrite or compare with one another.

Preserved Claude’s tiers, positional ranks, schedule context, movement, and
private-data handling. AGENTS.md and CLAUDE.md are aligned. Accent stays #980F26.

## Verification

- 31 Python checks pass, including legal lineup selection, premium and exclusive
  bonuses, expected bucket scoring, protected-drop comparisons, coverage gates,
  invalid settings, profile-separated history, corrupt caches, concurrent source
  reads, original timestamps, source outage, recovery, and ownership validation.
- Roster import parser checks and season UI checks pass. UI checks cover league
  request parameters, retained snapshot, failed-refresh advice pause and recovery.
- Python/JavaScript syntax, whitespace, and assistant instruction alignment pass.
- Live browser: General, Camden and Dad presets, connected Sleeper scoring,
  My players filter, provider/read dates, search, logos, desktop and 390px phone
  layout with no page overflow. Local macOS dashboard service remains installed.
- Live connected roster correctly withholds suggestions when an owned player has
  no remaining projection, rather than silently valuing the missing player at zero.

## Limits and handoff

ESPN/CBS assisted roster imports remain available through Leagues but do not
provide complete league-wide ownership; this iteration’s Available/waiver view
is Sleeper only. Pick’em and league transactions remain future work.

Bonus and Dad bucket estimates are deterministic expected payouts using gamma
weekly yardage and negative-binomial reception assumptions. TD-distance curves
follow the documented draft model but the weekly dispersion assumptions remain
unbacktested. This ROS engine is independent from the frozen Monte Carlo pipeline.
Configured statistics absent from the feed are listed in the source notes.
Unknown scoring rules stop the custom profile instead of falling back silently.

Raw projections are shared for one hour even on a manual profile refresh; the
original read date remains visible. Ownership is reread on a forced refresh and
every five minutes on an open connected page. Suggestions require a successful
refresh and pause at 30-minute ownership, 24-hour read, or 72-hour revision ages.
No expert consensus or trade-value claims. No private rosters, usernames, source
caches or screenshots were added to tracked files. A new browser must connect
its own username; local snapshots do not transfer through GitHub.
