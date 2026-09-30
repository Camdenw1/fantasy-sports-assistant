# Start/sit recommendations

Status: product and implementation spec, 28 Sep 2026. Source of truth for the
current experiment: prototypes/start-sit/startsit.py and its two saved week-3
outputs. Companion specs: ux.md owns navigation and league connection;
dashboard.md owns cross-league attention ranking; design.md owns presentation.

## 1. Job and boundary

For each league and scoring system, answer: **Which legal lineup should I use
this week, what would I change, why, and when must I recheck it?** The answer
must distinguish a forced fix (Out, bye, empty) from a close projection call.
It must never suggest moving a player whose game has started.

The present prototype reads public Sleeper leagues and produces recommendations.
It does not set a lineup, add a player, or submit a waiver claim. The product
action is a clear swap list plus an Open in platform link; returning to the app
should trigger a roster reread and show whether the change happened. An
authenticated execute path is a separate product decision. Camden's longer-term
wish to act from one dashboard remains part of the roadmap, with platform
capability and consent evaluated before building writes.

The engine covers **players already on the roster**. If nobody eligible can fill
a slot, it raises an empty-slot/waiver alert; it does not invent a free-agent
recommendation. Waivers, trades, rest-of-season value, and betting are separate
workstreams.

## 2. What the prototype does today

Run from the repository root:

    python3 prototypes/start-sit/startsit.py --week 4
    python3 prototypes/start-sit/startsit.py --week 4 --league LEAGUE_ID --json /tmp/start-sit.json
    python3 prototypes/start-sit/startsit.py --week 4 --what-if 'Player Name=Out'

It gets the current season/week from Sleeper state, discovers leagues by
username, then reads each league's settings, rosters, users, and weekly matchups.
It uses Sleeper's player dump for identities and injury tags, its weekly
projection endpoint for raw stat lines, ESPN's public weekly player projections
as a second line for QB/RB/WR/TE, and ESPN's NFL scoreboard for opponent,
kickoff, game state, spread, and total. If ESPN projections fail, it uses
Sleeper alone. If the scoreboard fails, it tries Sleeper's schedule.

Sleeper player IDs are the internal join key. ESPN IDs on the Sleeper player
object join the second projection; normalized name plus position is a fallback.
Reserve and taxi players are excluded. A past week's starter who has since
left the roster is retained for historical comparison. The player dump is
cached on disk for 24 hours in a gitignored directory, following the research
spec's note that Sleeper asks callers to fetch the full dump at most once a day.
Production may instead consume a slim shared file.

The saved normal fixture has no swaps; the Out what-if fixture recommends one
swap and improves projected total from 110.7 to 119.2. These fixtures show
contract shape and one regression scenario, not proof of predictive quality.

## 3. Scoring and uncertainty

Every projected stat line is rescored under that league's Sleeper
scoring_settings. The 0.75-TE reception rule, interception penalty, yardage
bonuses, kicker buckets, and DST tiers therefore come from the league rather
than from a universal PPR total. The current scorer treats each 100/200-yard
bonus family as exclusive, matching Camden's board.

The prototype draws 4,000 games per player. For each draw it alternates among
available projection sources, then samples game-script, yardage, and counting
stat variation. Source disagreement widens the range. It reports mean, p10,
p50, and p90, and compares candidates with a simulated probability that one
beats the other. The dispersion constants are heuristic and uncalibrated.
They should be tested against prior weekly actuals before a probability is
presented as well calibrated.

Current injury play probabilities are fixed assumptions: Questionable 0.80,
Doubtful 0.20, inactive statuses 0.0, and untagged players 1.0. A bye also
sets play probability to zero. A Questionable player's optimizer value adds a
discounted late-swap backup when another eligible player kicks off no earlier.
That is option value, not a measured probability of an actual legal swap.

For played games, the prototype uses actual points where available; for games
in progress it approximates remaining points as half of a full projection.
Production must replace that shortcut with a game-clock-aware remainder or
mark live recommendations as estimates. The scorer currently reads the raw
platform settings directly; a common multi-platform engine should instead
consume the canonical settings defined in draft-board.md and
league_settings.schema.json.

## 4. Legal lineup selection

The engine expands the league's roster positions into actual starting slots.
An assignment solver maximizes injury-adjusted projected value across all
eligible rostered players, so flex chains can beat a direct one-for-one swap.
Started or finished games are fixed. Players on a locked bench cannot enter.
Empty assignments are allowed only when no legal positive-value player fits.

A second assignment pass keeps the chosen starters but seats Questionable and
later-kickoff players in wider flex slots where useful. It favors keeping an
existing slot to avoid cosmetic churn, then restores a continuing starter to
the same row among duplicate RB/WR slots. The UI should show the final slot
diff, not a misleading independent recommendation for each position.

Each open starter gets its best eligible bench challenger. Confidence labels
in the prototype are forced, clear, lean, and coin_flip for actual swaps; keeps
and moves may also be labelled keep or reseat. Thresholds are presently clear
at probability at least 0.62 and a 2-point margin, lean at least 0.55.
These are display heuristics, not validated decision thresholds.

## 5. Output and dashboard handoff

The executable emits a JSON object per league (or an array for multiple
leagues) with schema startsit/v1:

| Field | Meaning |
|---|---|
| generated_at, platform, league, team | Run time, league identity, week, roster and scoring fingerprint |
| sources | Projection, schedule and injury provenance, currently names only |
| opponent, totals | Current and recommended lineup projections and matchup win probabilities |
| slots | One row per starting slot: current, recommended, locked, action, reason, confidence, challenger |
| swaps | True starters-out and starters-in, excluding mere flex reseating |
| alerts | GTD recheck time, bye starter, or empty slot |
| apply | Deep link and read-only note |

This is the **engine contract**, not yet the dashboard contract shown in
dashboard.md section 7.3. An integration adapter must add our stable
league_key, normalize player IDs and slot names, carry the per-league
generated_at and source timestamps, convert swaps to the dashboard's
out_pid/in_pid/delta_pts shape, and convert Questionable play_prob into
p_inactive. It must distinguish a true lineup swap from a flex reseat. The
dashboard's tie_band_pts, your_call, and reason enum are **not emitted** by
startsit/v1; the adapter or later engine version must supply them deliberately.
Do not interpret absence as zero or false.

The dashboard should use current/recommended win probability when available,
then apply its own freshness and attention rules. The Lineup screen shows the
complete slot assignment, including close calls and locks; Home shows only
actionable deltas and scheduled rechecks. Both display data age and the league
scoring summary.

## 6. Production requirements

1. **Inputs and freshness.** Use one league snapshot with roster, starters,
   scoring, reserve list, matchup and fetch times; one slim player/injury map;
   weekly raw projections with source and fetch times; and a kickoff/game-state
   map. Persist the last good values with their original timestamps. If injury
   or roster data is stale near lock, say Check in platform instead of issuing
   a confident start call (thresholds in ux.md section 6).
2. **Settings coverage.** Score every supported rule in the confirmed league
   settings. Surface missing stat projections and unmodelled rules in the
   recommendation detail. Never turn an absent input into a quiet zero.
3. **Legality.** Recompute on every roster or game-state change. A recommended
   lineup must use each eligible player at most once, respect reserve/IR/taxi,
   league flex rules, and preserve every locked slot.
4. **Actionability.** Each change names the outgoing player, incoming player,
   slot, gain, lock time, one concrete reason, confidence, and platform link.
   Re-read Sleeper after the user returns; manual leagues offer an explicit
   I did this state with a timestamp.
5. **Privacy.** The public repository and generated public assets must never
   contain private rosters or ESPN session cookies. Manual and private-league
   snapshots stay in the browser or a gitignored local file.

## 7. Build order and acceptance checks

**First integration:** preserve the existing Sleeper CLI as a fixture generator;
add a deterministic adapter from startsit/v1 to dashboard.md section 7.3;
render one Sleeper league in League > Lineup and its actionable cards on Home.
Keep ESPN/CBS as explicit snapshots until their read paths are settled.

Before treating the engine as ready:

- Reproduce the saved normal and Out what-if fixtures without changing a
  locked slot or inserting a reserve player. The Out case must produce an
  actionable replacement and higher recommended total.
- Fixture cases: empty slot, bye, Questionable early and late, duplicate RB
  slots, a flex chain, a locked starter, and a locked bench player. Assert slot
  legality and that slot-only moves are not counted as swaps.
- Verify scoring against hand-worked examples for TE premium, exclusive
  yardage tiers, kicker distance, and DST points allowed. Compare the raw
  league settings to the canonical settings summary shown to the user.
- Check failed/stale projection and injury fetches: keep last good data with
  its age, lower confidence, and never display a false all-clear.
- Backtest weekly point bands and the clear/lean probability labels against
  historical outcomes before claiming calibrated probabilities.

The present fallback schedule fabricates a 17:00 UTC kickoff when ESPN's
scoreboard is unavailable. That timestamp is not safe for lock or GTD alerts.
Production should suppress exact lock-time advice until a real kickoff is
available. Also replace the fixed PDT offset with a timezone-aware Pacific
conversion across daylight saving time.

## 8. Open decisions

- Which of Camden's non-Sleeper leagues are ESPN and CBS, and how will their
  private roster snapshots be obtained and refreshed?
- Does Camden want an explicit 1.5-point tie band for Home while keeping
  close calls visible in League > Lineup?
- When a user overrides a recommendation, how long should your_call suppress
  the card: until roster change, injury change, new projections, or kickoff?
- Should a future authenticated action path be built for any platform, and
  what review step must precede an irreversible transaction?
