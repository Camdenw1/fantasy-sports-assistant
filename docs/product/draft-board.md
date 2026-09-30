# League-aware draft board

Status: product and implementation spec, 28 Sep 2026. Current shipped surface:
draft-board-2026.html with generated board-data.js. Source for the
league-neutral experiment: prototypes/draft-board/league_settings.schema.json,
ls_adapters.py, ls_projections.py, and ls_engine.py. Companion specs: ux.md
owns navigation and league onboarding; design.md owns visual treatment.

## 1. Job and migration boundary

Open **League > Draft** and get a board priced for that league's confirmed
scoring and roster, with draft timing, roster needs, and source freshness
visible. Keep the current board useful while adding leagues: two hand-tuned
2026 profiles already exist; the generic path is a prototype, not a replacement
for them yet.

The present board is one hand-edited HTML page that loads a generated sibling
script. Refreshes edit refresh/*.py and write board-data.js plus rankings.csv;
they never regenerate HTML. The 2026 workflow stopped at its requested
7 September cutoff. New in-season or future-season data needs a separate
pipeline decision; this spec does not silently reactivate that workflow.

The board currently stores drafted players, My Team, next pick, profile and
Sleeper draft sync settings in localStorage key hp_board_v8. Sleeper draft sync
polls public picks every five seconds, fills My Team for Camden's slot, and
stops after three failures. The user can always cross off players manually.
Best available, Value coming up, My Team, and Lasts are existing features.

## 2. A league profile, not a hard-coded profile button

The target profile is a confirmed LeagueSettings object conforming to
league_settings.schema.json. Its essential fields are:

| Field | Purpose |
|---|---|
| schema_version, platform, platform_league_id, name, season | Identity and provenance |
| teams, games, draft | League size, projection horizon, draft type and rounds |
| roster.slots, bench, ir, taxi | Replacement demand and My Team slotting |
| scoring.rules | Canonical scoring that the engine can price |
| scoring.unsupported | Imported nonzero rules or positions we cannot price |
| model | Optional weights, reliability, floors, market combiner and tier settings |

Each starter slot has an id, eligible positions and count. Rule types are
per_unit (points times a projected stat), game_tiers (one exclusive tier per
game), game_step (whole increments per game), and distance (TD or field-goal
length). Position-specific reception premiums are additive per_unit rules.
The schema is the machine-readable definition; this spec sets the user-facing
and integration behavior.

The initial import must show a settings summary and a diff from a standard
half-PPR baseline, as ux.md section 4.5 specifies. It must disclose unsupported
rules and projected-stat gaps before presenting a rank as league-specific.
User overrides retain the imported value and a visible differs from platform
marker. Camden's 2026 Sleeper kicker override is deliberate: the live scoring
page showed an erroneous per-yard FG setting that was to be fixed, while the
hand-tuned board models normal kicker scoring. Generic import must surface this
mismatch and preserve the confirmed override instead of reverting it.

The league identity drives URL and state: the UX plan uses
#/league/{localLeagueId}/draft and draft:{localLeagueId}. Migrate hp_board_v8
once into the original Sleeper league, preserving drafted and My Team IDs;
do not copy that draft state into Dad's or any newly imported league. A shared
profile switch is replaced by the league header switcher. For a Sleeper league,
prefill draft id and slot from verified league/draft data where available;
manual next-pick and cross-off controls remain.

## 3. Settings adapters and coverage

The prototype has two working adapter functions:

- sleeper_to_canonical converts public Sleeper league JSON, scoring_settings
  and roster_positions. It maps normal linear scoring, TE/RB/WR bonuses,
  exclusive yardage tiers, DST points/yards allowed, kicker distance and
  long-TD bonuses. Nonzero unmapped keys and IDP slots go to unsupported.
- espn_to_canonical converts an ESPN mSettings response. It maps numeric
  statIds and lineupSlotCounts, including slot-specific pointsOverrides,
  whole-yard steps, yardage tiers and distance buckets. Unknown statIds and
  slots go to unsupported. Access to a private ESPN league is a separate
  connection problem described in research.md and ux.md.

The adapter promise is: every imported scoring key is mapped, explicitly
ignored because it pays zero, or reported as unsupported with source key and
points. A settings page needs counts and a readable list for all three, with
no silent scoring loss. The current prototype tracks this at import time, but
the scorer can still skip a game-tier or distance rule when its sample/event
distribution is missing. Promotion to production requires an additional
**data coverage report** per rule and player.

There is no CBS adapter yet. A manual LeagueSettings editor can represent Dad's
rules, but it must be checked against the supplied weekly buckets and distance
scoring before it earns a league-specific label. The existing custom Dad scorer
is the reference profile in the meantime. The prototype schema supports
auction and third-round-reversal draft types as values, but the existing board
implements only snake next-pick behavior; unsupported draft formats must not
show a fabricated Lasts or next-pick number.

## 4. Neutral projections and scoring

ls_projections.py converts the existing consensus player tables to
league-neutral season stat records. It uses a temporary copy of the current
refresh cache and an extended TTL so a prototype run does not fetch or rewrite
source data. It therefore depends on a local refresh/pubranks_cache.json and
does not independently maintain fresh projections. The live board's
three-source consensus remains the input, with availability and injury
judgment inherited from refresh/players.py and refresh/proj.py.

ls_engine.py splits league-neutral uncertainty from league-specific scoring:

1. game_samples draws 40,000 per-game stat outcomes per player using a stable
   player-key seed. It samples touches, yards per touch and game-script
   variation. Adding a player should not reroll every other player's outcome.
2. distance_mixes supplies TD and FG length distributions. Receiver and rusher
   curves tilt by yards per catch/carry; QB passing TDs stay at league average
   and QB rushing TDs use a short-score tilt. Kicker leg shifts FG mix.
3. score applies the league's rules: linear expectations directly, tier/step
   rules over game samples, and distance rules over event-length mixtures.
   It returns linear, per_game, distance and total components, multiplied
   by the player's availability, plus a set of missing linear stats.
4. to_quantiles can compress simulated outcomes for a future browser scorer;
   no browser contract or generated neutral player artifact exists yet.

These distributions and defaults are model assumptions, not validation
results. Availability has a known double-discount problem for injured players
in the present consensus (AGENTS.md, Known limitations). The generic scorer
must inherit a corrected treatment or label the affected ranks; copying the
same inputs does not resolve it. The forced-fumble proxy uses defensive
recoveries and must be disclosed. Two-point conversions and several exotic
stats may have scoring rules but no projected input.

## 5. Ranking and draft decisions

The prototype stops at **points**. It does not calculate value over
replacement, ranks, tiers, market/expert/sentiment lanes, or a complete
board-data payload for an arbitrary league. The next builder should reuse
the current board concepts while making the policy explicit per league:

1. Fill league roster demand across its team count to derive positional
   replacement levels, including flex eligibility. Compute model value from
   league-scored points above replacement.
2. Keep outside signals separate: draft market, expert rank and sentiment
   answer different questions. Use a format-matched market signal when one
   exists. A generic league with no suitable ADP must show that limitation;
   it must not present the 2026 half-PPR lane as format-exact for every league.
3. Blend model and outside timing only after validating the weights.
   Camden's current board uses 50/50; Dad's uses 65/35. Their lane weights,
   kicker/DST reliability scales, floors and tier gaps are intentional for
   those profiles, not universal defaults. Backtest against a finished season
   before extending them to arbitrary leagues.
4. Show one rank and its explanation: projected league points, replacement
   value, model rank, outside signals, final rank, and the source/setting
   caveats that matter. Keep NR rather than inventing a missing source rank.
5. Compute Lasts from an applicable ADP distribution and the user's actual
   next pick. Suppress it when the draft format or ADP dispersion is unknown.
   Value coming up only includes players near that pick and caps at two per
   position, preserving the current panel's useful behavior.

The existing 2026 strategy deliberately scales K and DST reliability
(0.15/0.30), floors them at picks 169/145 in the Sleeper profile and
161/141 in Dad's, and inserts one per team among bench fliers. A generic
board should derive any floor from rounds and team count and show the choice
as a model policy. Do not silently copy the absolute pick numbers.

## 6. Generated data and UI handoff

The existing board-data.js contains BOARD_META, BOARD_PROFILES and a default
BOARD_DATA. A new league-aware artifact should be versioned and contain:

| Group | Required content |
|---|---|
| profile identity | local league key, settings version/hash, season, generated time |
| provenance | each input source, fetched time, stale/missing status |
| settings coverage | unsupported rules, missing projected stats, overrides and caveats |
| ranked rows | stable player ID, position/team, projected points, model/outside/final rank, tiers, ADP dispersion where valid |
| draft state | **not generated**; stays per league in local state |

No private league settings, roster, draft picks or session credentials may be
committed into public generated files. Public Sleeper settings can be imported
client-side; ESPN/CBS private data stays in browser storage or a gitignored
local snapshot. A stale board should visibly show its data date. The 2026
snapshot must not look like current in-season advice.

The UI keeps the existing Best available / Value coming up / My Team model,
player-detail explanation, manual cross-off, and sync failure fallback. The
design spec supplies mobile table density and touch targets. Draft completion
hands My Team to League > Roster, as ux.md section 5.4 describes.

## 7. Build order and acceptance checks

**Stage A: prove scoring parity without changing the shipped board.**

- Validate both fixture settings JSON files against
  league_settings.schema.json after conversion. Assert their actual roster
  flex eligibility and scoring rules, then use small synthetic settings cases
  for Camden's TE premium, exclusive yardage tiers, ESPN pointsOverrides,
  steps and unsupported reporting. The saved Sleeper fixture is a different
  league and does not contain Camden's TE premium.
- Hand-work scoring examples for exclusive 100/200-yard bonuses, a 75-yard
  passing step, a 3/5-catch reception step, TD distance, FG per-yard scoring
  and DST points allowed. Check that missing sample/event inputs are surfaced.
- Compare the neutral scorer against the two hand-tuned profiles on the same
  projections, documenting any differences by rule, player and rank. A
  mismatch may be a deliberate override or a model bug; do not force equality
  by hiding it.

**Stage B: build the generic board.** Add replacement value, outside lanes,
ranking, tiers and a versioned output contract. Backtest the blend and
late-position policy against 2025 actuals and 2025 ADP before defaulting to
the old constants. Keep both legacy profiles available for comparison.

**Stage C: place it in League > Draft.** Test hp_board_v8 migration,
per-league isolation, switching leagues, manual picks, Sleeper sync,
next-pick math, Lasts when supported, and stale/missing-source states at
desktop and phone widths. The generated data build must never overwrite
draft-board-2026.html.

## 8. Decisions still needed

- Confirm each league's platform and whether Dad's custom rules can be
  represented faithfully by LeagueSettings before replacing the custom scorer.
- Decide how to publish neutral projections and sampled distributions to a
  static client without oversized files or private data.
- Decide the default blend and floor policy only after backtesting; determine
  how to label leagues whose market ADP does not match scoring or draft format.
- Decide whether the old 2026 draft should remain an archive route once the
  next season's league-aware board is ready.
