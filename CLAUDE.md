# Project context

This repository is growing from a 2026 fantasy football draft board into a
personal, cross-platform fantasy sports dashboard. The intended home screen
surfaces league actions in one place; lineup changes and bet tracking are future
capabilities, not features of the current board. `README.md` describes what is
implemented. `docs/product/` and `prototypes/` contain newer proposals and
experiments; check Git status before touching them because they may be another
assistant's unfinished work.

Codex and Claude Code share this repository. Keep `AGENTS.md` and `CLAUDE.md`
aligned on project rules. Prefer a focused branch per task, and use separate
worktrees if two tasks overlap. Preserve uncommitted work, review changes, and
hand off the branch and remaining limitations before the next assistant continues.

Fantasy football draft board with two switchable profiles: Camden's 12-team
half-PPR Sleeper league and Dad's unusual weekly-bucket league. Camden opens
`draft-board-2026.html` in a browser during drafts.

## Architecture — the one thing to understand

`draft-board-2026.html` is **presentation**, hand-tuned, and loads `board-data.js`
as a sibling `<script>`. `board-data.js` is **generated**. The split exists so data
refreshes never clobber UI work, and UI work never has to touch the pipeline.

- Changing how the board *looks or behaves* → edit the HTML
- Changing *what the numbers say* → edit `refresh/*.py`, then `python3 refresh/build.py`
- Never regenerate the HTML from a template. There isn't one anymore. It's the source.

## Pipeline

`refresh/build.py` builds two profiles and writes `board-data.js` + `rankings.csv`:

0. `proj.py` → builds CONSENSUS season projections: the hand-entered baseline in
   `players.py` averaged with ESPN's and Sleeper's own season projections. Keeps
   the pool and `avail` from players.py; a feed whose line implies a different
   role for a player is rejected rather than averaged in.
1. `score.py` → rescores those projections for this league's scoring
2. `fit.py` → Monte Carlo (40k games/player) for the 100/200-yard bonuses, since a
   bonus is a step function and E[bonus] ≠ bonus(E[yards])
3. `board.py` (which execs `blend.py`) → VOR against endogenous replacement level,
   blends model with the market/expert/sentiment anchor, assigns tiers and tags
4. `dad_score.py` → Monte Carlo weekly yard/reception buckets plus expected
   distance-based TD, kicker, and DST scoring for Dad's rules
5. `dad_board.py` → Dad-roster replacement level and a 65% model / 35% outside
   timing blend; both profiles are embedded in generated `board-data.js`

Data modules: `players.py` (projections + availability), `hp_data.py` (player pool
+ hand-written green/red flags), `sources.py` (fetches eight free public feeds,
cached per source for 6h without restamping stale fallbacks), `ranks.py`
(normalizes those into joinable columns),
`market.py` (award odds only — see below).

The paid sources this project started with — FantasyPros ECR and a Flock Fantasy
export — were removed when the repo went public. Don't reintroduce paid or
paywalled rankings; `sources.py` is the place to add a new free one.

## League rules — don't change these without being asked

Half PPR · **0.75 per catch for TE** (0.5 baseline + 0.25 premium) · INT **-2** ·
yardage bonuses are **exclusive tiers**: **+3 for 100-199 rush/rec, +4 for 200+**;
+3 for 300-399 pass, +4 for 400+ · kickers use **normal** fantasy scoring (3 under
40, 4 from 40-49, 5 from 50+, PAT 1, miss -1) · DST
points-allowed tiers 0 / 1-6 / 7-13 / 14-20 / 21-27 / 28-34 / 35+ pay
+10 / +7 / +4 / +1 / 0 / -1 / -4 · 12 teams · QB, 2RB, 2WR, TE, RB/WR/TE flex,
WR/TE flex, K, DST, 6 bench.

Verified against the league's scoring page on 24 Aug 2026. Fumble lost (-2) IS
now modelled: Sleeper's projections carry `fum_lost` (102 players). Interceptions
come from the feeds too, replacing the hand-kept QBINT table. 2-pt conversions
remain unmodelled -- no source projects them.

The scoring page currently shows kicker FG buckets of 1/2/3/4/5/6 plus a 0.10
per-yard bonus, which would make a 45-yarder worth 8.5 and put a kicker around
pick 50. Camden confirmed on 24 Aug 2026 that this is a league setup error being
fixed, so score.py models normal kicker scoring instead. **Don't "correct" it back
to match the page** without asking -- that mismatch is deliberate.

## Dad league profile

The site can switch to a second generated ranking without changing draft state.
Dad's supplied rules use weekly step-function scoring: passing yards every 75,
rushing every 25, receiving every 20; no ordinary PPR; RB/TE reception tiers
start at 3 catches and WR at 5; TD points increase with play distance; FGs pay
1/2/3/4 by distance and PATs 0.5; DST uses the supplied low-point rules. Roster:
QB, 2RB, 2WR, TE, two RB/WR/TE flexes, K, DST, 8 bench.

Camden confirmed Dad's league has **10 teams**.
Weekly buckets are simulated over 40k games/player. No feed projects TD length,
so `dad_score.py` starts from documented league-average passing/receiving and
rushing TD distance distributions and then **tilts each player's curve by how far
downfield he works** (yards per catch for receiving scores, yards per carry for
rushing ones, in log-distance space). This league pays more for longer scores, so
a flat league-average TD value quietly paid a 16 yd/catch deep threat exactly
what it paid a 10 yd/catch checkdown target. Receiving TDs now range ~3.6 to ~4.4
points instead of a fixed 3.89.

QB **passing** TDs stay at the league average -- their distance is set by the
receivers, not by anything the feeds carry about the quarterback. QB **rushing**
TDs take a fixed SHORT tilt: a quarterback's rushing scores are sneaks and
goal-line keepers regardless of how many scramble yards he accumulates, so
deriving their length from rushing volume is backwards. Defensive recoveries proxy for forced fumbles. The Dad
blend is 65% custom model / 35% outside timing context, with DST floored at pick
141 and K at 161 in the 18-round, 180-pick draft. Change these only if Camden
asks for a different risk tradeoff.

Dad's displayed **Market** is deliberately robust: the median of FFC, Yahoo, and
FantasyCalc half-PPR ranks, then combined 70/30 with the independent expert lane
to form Dad's outside anchor. This differs from the Sleeper profile's FFC-led
market. It was changed after FFC alone put Brock Bowers #45 while Yahoo,
FantasyCalc, ESPN context, and the expert board clustered at #21-23; the old 2:1
FFC/Yahoo headline misleadingly displayed #37.

## Draft-reality overrides — deliberate, don't "fix" them

- **K and DST are handled in three layers**, because a display floor alone left
  the *model* still claiming a kicker was worth pick 53:
  1. `RELIABILITY` in blend.py scales their VOR (K 0.15, DST 0.30) — the share of
     a projected edge worth planning around, given that kicker scoring is close to
     noise year over year and both positions are streamed off waivers. This is
     what makes the MODEL column rank them late (K #95, DST #80) rather than
     papering over a model that wanted them in round 5.
  2. `FLOOR` (DST 145, K 169) sets the earliest pick either may appear. The roster
     is 16 deep across 12 teams = 192 picks, so those are rounds 13 and 15.
  3. board.py inserts only the **top 12 of each** (one per team), on a stride of 2
     so they interleave with bench fliers; the rest fall to the bottom. Inserting
     all 32 defenses consecutively made "best available" read DEF for two straight
     rounds.
- The **Value coming up** panel caps at two per position and only shows players in
  range of the next pick. Uncapped it is entirely tight ends, because the 0.75
  premium means every TE beats public ADP. True, but not a draft strategy.

## Outside-information lanes

The final rank is 50% league model and 50% outside-information anchor. The anchor
keeps unlike signals separate: **55% market ADP / 30% expert / 15% sentiment**.

- **Market:** FFC real half-PPR 12-team ADP weighted 2, Yahoo half-PPR ADP
  weighted 1.
- **Expert:** RotoBaller's free, expert-authored half-PPR overall Top 100, parsed
  from its schema.org JSON-LD.
- **Sentiment:** FantasyCalc market value at `ppr=0.5&numQbs=1&numTeams=12`, plus
  its 30-day trend.
- **Context only:** ESPN `ownership.averageDraftPosition` is PPR ADP. It is shown
  in player details but does not enter the half-PPR blend.

Do not add paid or paywalled sources. Free does not automatically mean reusable;
prefer an API or explicit data license and retain attribution.

## Injuries — live, and they audit players.py

`fetch_injuries` in sources.py reads Sleeper's player dump (already downloaded)
for `injury_status`, body part and roster status. Badges render on the board;
IR/PUP/Out/Doubtful/Sus players are struck through and excluded from the value
panel.

**A feed-confirmed inactive status now CAPS `avail` automatically** (`capped_avail`
in proj.py): IR/PUP/NA/DNR/Sus cap at 0.35, Out at 0.60, Doubtful at 0.75. The cap
only applies to values at or above 0.95 — anything lower has clearly been set by a
human and is never overridden — and every cap is printed so the real number can be
set deliberately later.

This replaced a hard abort. The abort was right for a person at a keyboard and
wrong for a daily job: on 2 Sep 2026 Isiah Pacheco went on IR, `players.py` still
had him at 1.00, and the build refused to publish for two days running while
nobody was watching. Publishing slightly-conservative numbers beats publishing
nothing. build.py still aborts on the structural checks (rank sequence, duplicate
identities, K/DST floors, missing or >48h-old required sources).

Two sources were tested and rejected. Don't re-add either without new evidence:

- **Sleeper** publishes no official aggregate ADP endpoint. `search_rank` is
  search popularity, and their GraphQL draft queries need a `draft_id`.
- **MyFantasyLeague** has a real public ADP endpoint and no way to exclude
  superflex drafts, which its pool is full of. Measured against FFC on this board,
  MFL's QBs ran 38 slots earlier (Josh Allen 3rd overall vs FFC's 33rd) while RBs
  and WRs ran 7 and 20 later. `IS_PPR` filters scoring, not roster format.
  `fetch_mfl` is kept in sources.py, unused, recording exactly this.

## Removed on purpose — don't restore without asking

- **The betting layer.** Win totals and season props used to nudge the final sort.
  Measured on this board it moved skill players a mean of **1.8 slots** (max 11),
  which did not justify a column or the explanation it needed. `market.py` still
  holds `WIN` and `PROPS` if it is ever wanted back; only `AWARDS` is used now,
  for the small odds badge next to a name.
- **The "scoring fit" column.** It was **display-only** — it never entered the
  ranking. The league's quirks are already priced into `tot` through the yardage
  bonuses and the TE premium, so the column was decoration.

## Known limitations — worth stating rather than papering over

- No role-change modelling. A backup is valued at projected volume, not the volume
  he'd get if the starter went down. Handcuffs are undervalued by construction.
- Projections are now a 3-source consensus (players.py + ESPN + Sleeper), 219 of
  220 players carrying 2+ sources. The final 50/50 blend with the outside anchor
  remains unvalidated.
- `avail` is still hand-set in players.py — it is injury *judgement*, not a stat
  projection. build.py audits it against the live injury feed on every run.
- Deep bench players are smoothed across 17 games rather than modelled as spiky.
- **Injured players are discounted twice.** `players.py` lines are full-season and
  get multiplied by `avail`; the ESPN and Sleeper feeds already bake expected
  missed time into their own numbers. Averaging them and then applying `avail`
  double-counts the absence. Measured 3 Sep 2026 it affected 5 players, four of
  them past pick 184 — but Josh Jacobs (ESPN 719 rush yds vs our 1155 baseline,
  then x0.75) sits at #76 against a market rank of 49, and that gap is mostly
  this bug. Fixing it properly means applying `avail` to the players.py line
  *before* the blend rather than to the consensus after, which touches score.py,
  fit.py and dad_score.py. Not attempted mid-season.

## Built since — don't rebuild these

- **Sleeper live-draft sync.** Done. Paste a draft id and slot into the rail; it
  polls `GET /v1/draft/{draft_id}/picks` every 5s, crosses picks off, routes your
  own into My Team, and recomputes your next pick from the snake order. Gives up
  after three consecutive failures. Sleeper's API allows the cross-origin call.
- **My Team / Best available / Value coming up** panels, and the *Lasts* column
  (chance a player survives to your next pick, from FFC's ADP dispersion).

## Next build

**Backtesting.** Every constant in this project is reasoned but unvalidated:
`W=0.50`, the lane weights, `RELIABILITY`, the `FLOOR` picks, the tier
gaps, and the Monte Carlo dispersion parameters in fit.py. Nothing has ever been
scored against a finished season. Run the board against 2025 actuals and check
whether the blend actually beat drafting straight off FFC ADP — that is the only
way to know if the model half is earning its place. Offseason work, not
two-weeks-before-the-draft work.

## Refresh cutoff

The GitHub Actions workflow has a hard cutoff at **2026-09-07 19:40:09 UTC**
(12:40:09 PM PDT). At or after that instant, scheduled and manual runs are clean
no-ops and cannot rewrite generated data. Camden requested this one-week cutoff
on 31 August 2026.

## Dashboard design and reliability

Camden's priority is robust everyday use. Read `docs/product/design-brief.md` for
the current red scorecard direction and the canonical personal design reference.
The local dashboard uses background refresh jobs, dated browser/server snapshots,
and an offline shell. Cache fallback must never acquire a new source timestamp.
Missing roster projections withhold totals and suggested lineup columns.
`python3 scripts/dashboard-service.py status` checks the macOS local service;
install/uninstall are documented in README. It binds only to localhost. Preserve
its availability when updating the running server, and verify failure/recovery
paths when modifying refresh logic. Generated draft data remains frozen.

## Everyday dashboard

Lineup report engine version 3 includes `bench` and `reserve` player references.
Render these from the current roster, separate from starter recommendations;
never synthesize zero points for missing projections. Home exposes data checks
and bench/reserve injuries as visible action cards. Connection setup selects a
platform first: username-only Sleeper, URL and named-team selection for public
ESPN, guided roster paste for CBS/private ESPN. Snapshots remain local; do not
claim authenticated sync. ROS-owned rows have a translucent red fill and marker.

## Current season player view

`app/players.html`, `app/season.js`, and `app/season.py` implement ROS projection
rankings from current Sleeper weekly data. Keep this independent from the frozen
draft pipeline. Remaining full weeks through Week 17, current week excluded,
skill positions only. `season_scoring.py` supports standard half-PPR, Camden and
Dad presets, and supported live Sleeper scoring. Unknown nonzero rules fail
explicitly; configured stats missing from the feed are disclosed. Bucket/bonus
payouts are expectations over documented, unbacktested distributions. No extra
injury multiplier. Custom Flex lists use starter replacement including flex demand;
position lists still rank by ROS points. No claimed expert consensus or trade values.
`season_rosters.py` fetches complete Sleeper ownership and protects starters,
reserves, and the optimal legal core from drop comparisons. Missing owned players
or unexplained projected-week gaps withhold advice. ESPN/CBS imports are not
league-wide ownership. `season_sources.py` shares one-hour dated raw reads;
expired source failures never return a restamped fallback. Connected ownership
refreshes every five minutes; suggestions pause on failed refresh or stale dates. Preserve source dates and complete-week coverage checks;
placeholder ADP rows are not projections.
Tiers are 1-D k-means over each list's startable depth (`TIER_SHAPE`). Schedule
strength is context only, never a rank input, because Sleeper's projections already
price matchups. Movement compares against a local rank snapshot at least five days
old (`app/.cache/season-history.json`) and stays blank until one exists. Red (#980F26), with translucent fills and markers, is the subtle
project accent, with a white/charcoal canvas.
