# Home dashboard: what to focus on right now

Owner: home-dashboard workstream. Status: proposal, 25 Sep 2026 (Friday of NFL week 3).
Prototype: `prototypes/dashboard/index.html` (static, fake data, open in any browser).

The home page answers one question: **what, across all my leagues, should I do next, and by
when?** It is not a league homepage, a scoreboard, or a news feed. Each element earns its place
by changing a decision. When nothing needs doing, the page says so and names the next time
something could change.

Other workstreams own the global nav (UX/IA), the visual system, the start/sit math, and the draft
board. This doc owns **which items exist, how they're ranked, what each card says, and which data
the page needs from everyone else.**

---

## 1. Ground truth and assumptions

- **Three leagues, one each on Sleeper, ESPN and CBS.** Only one mapping is on record: the 12-team
  half-PPR league (0.75 TE, 100/200-yard bonuses) is on **Sleeper** (repo name and CLAUDE.md).
  The `set-lineups` skill says the platform for Dad's 10-team weekly-bucket league and the third
  league "isn't recorded". The prototype *assumes* Dad = CBS (CBS is where custom scoring usually
  lives) and third league = ESPN. **Confirm with Camden.**
- **Time zone is Pacific** (CLAUDE.md quotes PDT). Sunday windows in PT: 10:00, 1:05, 1:25, SNF
  5:20. TNF and MNF are 5:15. Inactives are posted **90 minutes before each kickoff**: 8:30,
  11:35, 11:55, 3:50.
- **The repo is public.** Private ESPN/CBS roster data and cookies must **never** be committed.
  Whatever the pipeline agent builds, dashboard inputs from private leagues belong in a
  gitignored local file (for example `league-data.local.js`) or stay in the browser. This is a
  hard constraint, not a preference.
- **The dashboard reads only; it doesn't make changes.** Actions deep-link to the platform, or
  hand off to the existing `set-lineups` skill, which already has an approval-gated execute phase.
  The dashboard never makes a roster move itself.

---

## 2. What each platform can supply

| Capability | Sleeper | ESPN | CBS |
|---|---|---|---|
| Access | Public REST, no auth, **CORS works from a static page** (the live draft sync already relies on it) | `lm-api-reads.fantasy.espn.com/apis/v3/...`. Private leagues need the `espn_s2` + `SWID` cookies. **No CORS from a static page**, so reads go through a local proxy, the pipeline, or a logged-in browser run | No usable public API. The `api.cbssports.com/fantasy` token flow is short-lived and undocumented for this use. **Practical path: page reads in a logged-in browser** (as `set-lineups` does) |
| Rosters, starters, IR/reserve | `/league/{id}/rosters` (`starters`, `players`, `reserve`) | `view=mRoster` (lineupSlotId per entry) | Lineup page text |
| Slot layout | `/league/{id}` `roster_positions` | `view=mSettings` | Lineup page |
| Matchup and live score | `/league/{id}/matchups/{week}` (`points`, `players_points`, `matchup_id`) | `view=mMatchupScore` / `mBoxscore` | Scoreboard page |
| League-scored projections | Not in the documented API (undocumented `/projections/nfl/{season}/{week}` exists but scores in standard formats; rescore it ourselves) | Yes: `kona_player_info` stats with `statSourceId=1` and `appliedTotal` | Yes, on the lineup page ("Proj") |
| Injury designation | `/players/nfl` `injury_status`, `injury_body_part`, `practice_participation`, `news_updated` (already fetched by `sources.fetch_injuries`) | `injuryStatus` on player entries | Lineup page tag |
| Kickoff times / game state | Not in documented API. Use **ESPN's public NFL scoreboard** (`site.api.espn.com/.../nfl/scoreboard`, no auth) as the single kickoff source for all three leagues | Same | Same |
| Waiver schedule and FAAB | `league.settings` waiver fields; `roster.settings.waiver_budget_used` (field names: verify) | `view=mSettings` acquisition settings; `mTeam` FAAB | Transactions page |
| Pending trades | `/league/{id}/transactions/{week}`. Whether *pending* offers appear is unverified | `view=mPendingTransactions` (with cookies) | Trades page |
| Trending adds (waiver signal) | `/players/nfl/trending/add` (public) | n/a | n/a |
| League chat / commissioner notes | Not in public API | `communication` view (with cookies) | Message board page |
| Player ID cross-reference | Sleeper player objects carry `espn_id` (plus yahoo, sportradar, gsis). **Sleeper id is the canonical key** | Via Sleeper's `espn_id` | No shared id. Match on normalized name + team + position, flag any ambiguity |

Freshness implication: Sleeper can be read **live in the page**. ESPN and CBS data is a
**snapshot** only as fresh as its last read, so each card shows its source age (section 6), and the
ranking discounts stale evidence (section 4).

---

## 3. Catalogue of attention items

**Class** sets the severity weight `S` (section 4). **Stake** is how points-at-risk is measured.
MVP items are marked ●, later items ○.

### Lineup: hard zeros (class `ZERO`, S = 1.0)

| | Item | Trigger | Stake | Data | Platforms |
|---|---|---|---|---|---|
| ● | **Out / IR / Sus / PUP / NA starter** | Starter's designation is inactive and his game hasn't locked | Projection of the best legal replacement (bench, else best free agent) | roster, injuries, kickoffs, recs | All three. Injury status from Sleeper's feed is authoritative, keyed by canonical id |
| ● | **Ruled inactive** (game day) | Player on the posted inactive list, 90 min before kickoff | Same | Inactives (Sleeper `injury_status` flips to Out within minutes; ESPN too) | All |
| ● | **Bye-week starter** | Starter's team has no game this week | Same | Schedule plus roster | All |
| ● | **Empty starting slot** | Starter id is null / "Empty" | Best available fill | Roster | All |
| ○ | **Released / traded to unknown team** | `team` null or changed since last read | Same | Player feed | All |

### Lineup: risk (class `RISK`, S = 0.6; Doubtful uses S = 0.8)

| | Item | Trigger | Stake | Notes |
|---|---|---|---|---|
| ● | **Questionable, early window, viable backup** | Q starter, kickoff in the 10:00 window, backup within ~3 pts | `P(inactive)` × replacement proj + downside of a limited snap share | Recommendation: start the safer player now |
| ● | **Questionable, late window** | Q starter in the 1:05/1:25/SNF/MNF window | Same | A *scheduled* item: shows as "recheck at 11:35", ideally with the player moved to FLEX so late swaps stay open. Becomes live when inactives post |
| ● | **Doubtful starter** | D designation | ~0.75 × replacement proj | Usually treat like Out |
| ○ | **Practice trend** | DNP→DNP→LP pattern or new mid-week injury tag, Wed–Fri | Small | Feeds the confidence of Q/D items, also an FYI news item |
| ○ | **Weather** | Extreme wind/snow at an outdoor stadium, for K / deep passing | Small | Only extreme cases, matching `set-lineups` |

### Lineup: optimization (class `OPT`, S = 0.5)

| | Item | Trigger | Stake |
|---|---|---|---|
| ● | **Better bench option** | Start/sit engine's recommended lineup beats current by ≥ 1.5 pts total (the engine's tie band). One card per league, not one per swap | Δ projected points, converted to Δ win probability |
| ○ | **Flex ordering for late swap** | Two close options where the earlier-kickoff player sits in FLEX | ~0 pts. Option value only, FYI band |
| ○ | **Camden overrode the engine** | Current lineup differs from the rec and nothing is hurt | Shown once as "your call", then suppressed (matches the `set-lineups` rule that Camden's own edits stand) |

### Roster and transactions (class `ROSTER`, S = 0.4)

| | Item | Trigger | Stake | Platforms |
|---|---|---|---|---|
| ● | **IR slot open + IR-eligible player on bench** | IR slot empty and a bench player's status is IR/Out (per league rules) | Value of the freed bench spot (best recommended add) | Sleeper `reserve` + settings; ESPN mRoster; CBS page |
| ● | **Illegal IR** | A player in IR is now healthy. Sleeper blocks *all* transactions until fixed | High: set S = 0.8 because it blocks waivers | Sleeper, ESPN |
| ○ | **Waiver deadline + recommended adds for holes** | Waivers process in < 48h and a hole exists (upcoming bye, injured starter with no backup, empty bench) | Hole-week Δpts + rest-of-season value of the add | Sleeper settings; ESPN mSettings; CBS page. Recs come from a waiver engine (not yet owned by anyone) |
| ○ | **Waiver results** (Wed) | Claims processed | Info | All |
| ○ | **Trade offer received** | Pending offer to Camden | Fixed stake (trade value is out of scope); urgency from expiry or veto window | ESPN (mPendingTransactions); Sleeper (verify); CBS page |
| ○ | **Trade deadline approaching** | League trade deadline within 7 days | Info | Sleeper `settings.trade_deadline`; ESPN settings |

### Context (class `INFO`, S = 0.15). FYI band, never the hero

| | Item | Data |
|---|---|---|
| ● | **Matchup status / win probability** per league | Projections for both teams, live points. Rendered as the **league strip**, not a card. Becomes a card only when it changes a decision (e.g. "you need a ceiling play" is later) |
| ○ | **News on rostered players** | Sleeper `news_updated` diff; headline text from a free news source (TBD by the research agent) |
| ○ | **Exposure: one player on several rosters** | Canonical id join. "Bijan Robinson: 2 of 3 rosters, 21% of your combined projected points". Also opponent exposure (you face a player you start elsewhere) |
| ○ | **League / commissioner messages** | ESPN communication view only. Sleeper chat isn't public, CBS needs a page read. Low value, last |

### System health (class `SYS`, pinned above the ranked list)

| | Item | Why it's special |
|---|---|---|
| ● | **League data stale or auth expired** (ESPN cookie expired, CBS snapshot older than threshold, Sleeper fetch failing) | If the data is wrong, every other item is wrong. Game-day threshold 2h, weekdays 24h. Action: "Refresh" / "Run set-lineups read" |
| ● | **League not identified** (roster read but no scoring profile matched) | Engine output is suspect |

### Season phase

| | Item | Trigger |
|---|---|---|
| ● | **Draft upcoming → promote draft board** | Any league `pre_draft` with a draft ≤ 14 days out. Hero on draft day; during a live draft the whole page yields to the board |
| ○ | **Playoff / elimination** | Eliminated leagues fade to a single line; playoff matchups get a ×1.5 stake multiplier |

---

## 4. Ranking model

Every candidate item gets one number:

```
priority = S × P × C × U
```

**S, severity class weight.** Regret asymmetry, not probability: an unforced zero in the lineup is
worse than a missed optimization of the same size.
`SYS` pinned · `ZERO` 1.0 · Doubtful 0.8 · Illegal IR 0.8 · `RISK` 0.6 · `OPT` 0.5 · `ROSTER` 0.4 ·
`INFO` 0.15.

**P, points at stake, as win probability.** Stake starts in fantasy points (Δ) and is converted
into change in win probability for *this week's* matchup, so 4 points in a coin-flip outranks 4
points in a blowout:

```
WP(m)   = Φ(m / σ)                    m = my_proj − opp_proj,  σ ≈ 30 (per-league, fit from last season)
P       = max( WP(m + Δ) − WP(m),  0.3 × φ(0)·Δ/σ )      (in percentage points)
```

The floor (30% of the coin-flip value) keeps a hard zero from vanishing in a projected blowout,
since projections miss and points-for is a tiebreaker. Without matchup data, P falls back to
the coin-flip value `0.399·Δ/σ`, which is the conservative (larger) estimate. For probabilistic
items, Δ is already an expectation: Q uses `P(inactive)` priors of **Q 0.20, D 0.75, O/IR 1.0**,
to be calibrated against 2025 inactive lists when backtesting happens. Items without a points
estimate carry a fixed P: trade offer 1.5, waiver results 0.5, draft upcoming 10 percentage points.

**C, confidence, 0–1.** `C = C_model × C_fresh`.
- `C_model`: from the start/sit engine (projection gap relative to its uncertainty). 1.0 for
  facts such as a bye, an Out designation or an empty slot.
- `C_fresh = 0.5^(age / half_life)`: half-life **30 min on Sunday before and during games**, 6h
  Thu–Sat, 24h Mon–Wed. When `C_fresh < 0.5` the card shows "Verify, data is 3h old" with a
  refresh action, and the league chip turns amber. Staleness doesn't hide an item, it tells
  Camden to check it.

**U, urgency from time to the item's lock.** `t` is hours until the thing stops being actionable:
the player's kickoff, waiver processing, trade expiry.

| t | ≤ 3h | 3–24h | 1–3 days | > 3 days | no deadline |
|---|---|---|---|---|---|
| U | 1.0 | 0.8 | 0.55 | 0.35 | 0.25 |

Past-lock items are removed; missed hard zeros go to Tuesday's recap.

**Actionability gate.** An item that *can't be acted on yet*, such as a late-window Q player before
inactives post, doesn't enter the ranked list. It sits on the **timeline** with its trigger time
and moves into the ranked list with U = 1.0 when the time comes. This keeps "watch this at 11:35"
from ranking above "fix this now".

**Bands** (thresholds in P's percentage-point units, tune once real data flows):
- **Do now:** priority ≥ 3.0, or any `ZERO` with t ≤ 3h
- **Before lock:** ≥ 1.0 (lock = kickoff, waiver run or offer expiry)
- **This week:** ≥ 0.25
- **FYI:** everything else, collapsed

**The hero** is the top item after grouping, and appears only if it's in *Do now* or *Before
lock*. Otherwise the hero is the **all-clear** card. Stability rules:
- *Hysteresis:* a new item replaces the current hero only if it beats it by ≥ 15%, or if it's a
  `ZERO` with t ≤ 3h. The top of the page shouldn't flicker on every poll.
- *Tie-break:* earlier lock first, then higher S.

**Dismiss / "my call".** Each card can be dismissed. Suppression is keyed on a **fingerprint**
(type + canonical player + league + the facts that triggered it, e.g. `injury_status=Q`). If the
facts change (Q → Out), the item comes back. Hard zeros can be snoozed but not dismissed.

### De-duplication and grouping

Camden acts one platform at a time, but he thinks in terms of players. Cards group by **cause**
and list the per-league actions inside:

1. **Same player, same cause, several leagues → one card.** Key `(canonical_pid, cause)`.
   "Tee Higgins ruled OUT, starting in 2 leagues", with one action row per league. Group priority
   is the **sum** of member priorities, because each league is an independent matchup and a loss
   in each.
2. **Same slot, several causes in one league → keep the most severe.** Out outranks "better bench
   option" for that slot. The weaker item is absorbed.
3. **Optimization swaps collapse per league.** Three +1-point swaps in ESPN make one card:
   "ESPN: 3 changes, +4.1 pts". Any swap already covered by a `ZERO`/`RISK` card in that league is
   left out, and the card says "plus the Higgins fix above".
4. **Per-platform trip hint.** When the hero sends Camden to a league's lineup page, the card
   notes other open items for that same league ("while you're there: 1 more swap"), so he makes
   one trip per platform.
5. **Bye-week causes group by NFL team.** Several players on one bye team make one card.

### All-clear states

All-clear is a normal outcome, not a leftover empty state, and it always answers "when should I
look again?"

- **All leagues clear:** "All 3 lineups are set. Next checkpoint: **Sun 8:30 PT**, early inactives."
  Under it: the league strip (records, WP) and the FYI band, collapsed.
- **Partially clear:** each league chip shows ✓ "Set · locks Sun 10:00" or a count of open items.
- **Can't know:** if a league's data is stale, that league is **never** reported clear. Its
  chip reads "Unverified" and a `SYS` item leads the page.

---

## 5. How the page changes over the week

The page's *mode* comes from the clock and league state. It changes which items are **eligible**,
the half-lives, and what sits under the hero. The ranking formula stays the same.

| When (PT) | Mode | Below the hero | Typical top items |
|---|---|---|---|
| **Mon night → Tue** | Recap + waivers | Last week's results per league (W/L, points left on bench, missed zeros), then next week's holes | Illegal IR, IR stash, holes from next week's byes and injuries, waiver recs (later) |
| **Wed** | Waivers processed | Claim results; free agency open | Adds for holes that remain; trade offers |
| **Thu** | TNF lock | Countdown to 5:15 for TNF starters only | Out/Q TNF starters; first full start/sit pass for the week |
| **Fri** (today) | Final injury reports | Friday designations are the week's most important news | New Out/D designations in lineups; Q plans ("put him in FLEX, recheck Sun 11:35"); better-bench cards |
| **Sat** | Quiet | Mostly all-clear, plus any late-news items | Late designation changes (Saturday Out/activations) |
| **Sun 6:00–10:00** | Game-day prep | **Window timeline:** 8:30 inactives → 10:00 lock → 11:35/11:55 inactives → 1:05/1:25 lock → 3:50 → 5:20 | Inactive starters in the 10:00 window (Do now, countdown) |
| **Sun 10:00–17:20** | Live | Live scores + WP per league; only **unlocked** players are actionable | Late-window inactives; "SNF player still swappable" |
| **Sun night / Mon** | MNF | Live WP; "you need 14.2 from Kelce" | MNF inactive starters |
| **Aug → draft day** | Draft season | League draft dates; draft board hero | "Sleeper draft in 3 days: open draft board"; live draft = page yields to board |
| **Post-season / off-season** | Dormant | Final standings, link to draft board archive | None; one line: "Season over" |

Two rules sit on top of the table:
- **The lock timeline is always visible** during the NFL week as a thin ribbon showing the next
  lock and the next inactives time, even when everything is clear.
- **TNF and international games** create their own mini game-day. The mode is set by the
  *next kickoff involving one of Camden's starters*, not the calendar day. A London game at
  6:30 PT puts Sunday's first inactives at 5:00 PT.

---

## 6. Card content spec

Each card is one decision, laid out top to bottom:

| Field | Rule | Example |
|---|---|---|
| **Band marker** | Do now / Before lock / This week / FYI | `DO NOW` |
| **Headline** | Verb-first where possible; player + problem; ≤ 60 chars | "Bench Tee Higgins: ruled OUT (hamstring)" |
| **League rows** | One per affected league: platform badge, slot, the specific fix | "Sleeper · WR2 → start Jauan Jennings (+9.8)" |
| **Why** | One line, with numbers: stake and confidence, no jargon | "Worth ~9.8 pts and 12% win chance in a close Sleeper matchup" |
| **Lock** | Countdown when < 24h, else day + time | "Locks Sun 10:00 PT (in 49h)" |
| **Actions** | Primary: deep link to that league's lineup page. Secondary: "Snooze until …" / "My call" / "Ask Claude to set lineups" (copies `/set-lineups`) | `Open Sleeper lineup ↗` |
| **Freshness** | Source + age for each fact used; amber if `C_fresh < 0.5` | "Injury: Sleeper 12m ago · roster: CBS snapshot 3h ago" |
| **Why ranked here** (disclosure) | S, P, C, U values | For debugging and for trust |

Deep links (confirm on first live run):
- Sleeper lineup: `https://sleeper.com/leagues/{league_id}/team`
- ESPN lineup: `https://fantasy.espn.com/football/team?leagueId={id}&teamId={tid}&seasonId=2026`
- ESPN free agents: `https://fantasy.espn.com/football/players/add?leagueId={id}`
- CBS: `https://{slug}.football.cbssports.com/` (league home; team path to be confirmed)

Copy rules: never say "consider". Say what to do, with the number. When the engine can't
decide (within the 1.5-pt tie band), the card says it's a coin flip and names the tie-breaker it
used.

---

## 7. Data contracts

All times are ISO-8601 with offset. All players carry a **canonical id = Sleeper player id**, plus
the platform id. The dashboard consumes these and emits `attention.json` (section 7.5).

### 7.1 League snapshot (from league adapters; one per league)

```json
{
  "league_key": "sleeper:1180234567890",
  "platform": "sleeper",
  "name": "Sleeper league",
  "profile": "halfppr_te075",
  "teams": 12,
  "season": 2026, "week": 3, "phase": "regular",
  "fetched_at": "2026-09-25T15:58:00-07:00",
  "source": "live",
  "auth": "ok",
  "my_team": { "team_id": "4", "name": "Weber", "record": "1-1", "points_for": 241.6 },
  "slots": ["QB","RB","RB","WR","WR","TE","FLEX","WRTE","K","DEF"],
  "bench_size": 6, "ir_slots": 1,
  "roster": [
    { "pid": "6794", "platform_pid": "6794", "slot": "WR", "slot_index": 3, "locked": false },
    { "pid": "9488", "platform_pid": "9488", "slot": "BN", "locked": false },
    { "pid": "7564", "platform_pid": "7564", "slot": "IR", "locked": false }
  ],
  "matchup": {
    "opponent": "Team Chaos", "my_points": 18.4, "opp_points": 0.0,
    "my_proj": 118.2, "opp_proj": 114.9, "sigma": 30
  },
  "waivers": { "type": "faab", "next_process_at": "2026-09-30T00:00:00-07:00",
               "faab_remaining": 71, "faab_total": 100 },
  "pending_trades": [
    { "id": "t1", "direction": "received", "from": "Team Chaos",
      "give": ["9488"], "get": ["8150"], "expires_at": "2026-09-26T09:00:00-07:00" }
  ],
  "draft": null,
  "links": { "lineup": "https://sleeper.com/leagues/1180234567890/team",
             "waivers": "...", "trades": "..." }
}
```

`source` is `live` | `snapshot`. `auth` is `ok` | `expired` | `none`. For a league still before its
draft, `draft` = `{ "status": "pre_draft", "start_at": "...", "draft_id": "..." }`.

### 7.2 Player facts (injury feed + schedule; one shared map)

```json
{
  "generated_at": "2026-09-25T16:05:00-07:00",
  "players": {
    "6794": {
      "name": "Tee Higgins", "pos": "WR", "team": "CIN",
      "xref": { "espn": "4239993", "cbs": null },
      "injury": { "status": "Out", "body": "Hamstring", "practice": ["DNP","DNP","DNP"],
                  "updated_at": "2026-09-25T13:12:00-07:00", "source": "sleeper" },
      "game": { "opp": "@PIT", "kickoff": "2026-09-27T10:00:00-07:00",
                "window": "early", "state": "pre", "inactives_at": "2026-09-27T08:30:00-07:00" },
      "bye": false,
      "news_updated": "2026-09-25T13:12:00-07:00"
    }
  }
}
```

The current `fetch_injuries` keys on **name** and keeps only tagged players. The dashboard needs it
keyed by **Sleeper id**, with `espn_id` and `team` for every rostered player, including healthy
ones (so a status clearing is visible). Kickoffs come from ESPN's public scoreboard.

### 7.3 Lineup recommendation (from the start/sit engine; one per league per week)

```json
{
  "league_key": "espn:88112233",
  "week": 3, "generated_at": "2026-09-25T15:40:00-07:00",
  "engine_version": "0.1",
  "current":     { "proj": 104.3, "win_prob": 0.44 },
  "recommended": { "proj": 112.9, "win_prob": 0.53 },
  "swaps": [
    { "slot": "RB2", "out_pid": "8138", "in_pid": "9226",
      "delta_pts": 6.1, "reason": "OUT", "reason_text": "Out (ankle)",
      "confidence": 1.0, "lock_at": "2026-09-27T13:25:00-07:00" }
  ],
  "flags": [
    { "pid": "4866", "code": "Q_LATE", "text": "Q (knee), SNF",
      "p_inactive": 0.20, "recheck_at": "2026-09-27T15:50:00-07:00",
      "suggested_slot": "FLEX" }
  ],
  "tie_band_pts": 1.5,
  "your_call": ["7547"]
}
```

`reason` enum: `OUT | IR | BYE | EMPTY | DOUBTFUL | Q_EARLY | Q_LATE | PROJ | FLEX_ORDER`.
`confidence` is `C_model` in section 4. `your_call` lists players Camden deliberately started
against the recommendation (so the dashboard suppresses them).

### 7.4 Waiver recommendations (later; owner TBD)

```json
{ "league_key": "cbs:dadleague", "for_week": 4,
  "holes": [ { "slot": "DEF", "cause": "BYE", "week": 4 } ],
  "adds": [ { "pid": "PHI", "drop_pid": "5012", "faab_bid": 3, "fills": "DEF",
              "delta_pts_hole_week": 6.5, "ros_value": 0.4 } ] }
```

### 7.5 Attention items (dashboard output; consumed by the page and later by notifications)

```json
{
  "generated_at": "2026-09-25T16:06:00-07:00",
  "mode": "friday_reports",
  "next_checkpoint": { "at": "2026-09-27T08:30:00-07:00", "label": "Early inactives" },
  "hero": "g:6794:OUT",
  "items": [
    {
      "id": "g:6794:OUT", "type": "OUT_STARTER", "class": "ZERO", "band": "do_now",
      "headline": "Bench Tee Higgins: ruled OUT (hamstring)",
      "why": "Starting in 2 leagues. ~9.8 + 7.4 pts at stake.",
      "pid": "6794",
      "members": [
        { "league_key": "sleeper:1180234567890", "slot": "WR2", "fix_pid": "9488",
          "delta_pts": 9.8, "action_url": "https://sleeper.com/leagues/1180234567890/team" },
        { "league_key": "cbs:dadleague", "slot": "FLEX", "fix_pid": "8155",
          "delta_pts": 7.4, "action_url": "https://dadleague.football.cbssports.com/" }
      ],
      "lock_at": "2026-09-27T10:00:00-07:00",
      "scores": { "S": 1.0, "P": 17.1, "C": 0.97, "U": 0.55, "priority": 9.1 },
      "freshness": [ { "fact": "injury", "source": "sleeper", "age_min": 12 },
                     { "fact": "roster", "source": "cbs", "age_min": 190 } ],
      "fingerprint": "OUT_STARTER|6794|Out|sleeper,cbs",
      "dismissible": false
    }
  ]
}
```

---

## 8. MVP and later

**MVP: enough to replace opening three apps on Friday and Sunday morning.**
1. Sleeper league live in the page (rosters, matchup, `/players/nfl` injuries), plus ESPN/CBS
   from a **snapshot** written by a logged-in browser read (the `set-lineups` phase-1 read,
   saved to a gitignored local file). Kickoffs from ESPN's public scoreboard.
2. Items: Out/IR/Sus/bye/empty starter, ruled-inactive, Doubtful, Q early/late with
   recheck-time scheduling, better-bench (one card per league, from the start/sit JSON), IR slot
   open, illegal IR, stale-data/auth, draft-upcoming.
3. Full `S × P × C × U` ranking with grouping, bands, hero hysteresis, dismiss-by-fingerprint,
   and all-clear with next checkpoint.
4. Modes: Friday reports, Sunday prep/live (window timeline), draft season. Other days show the
   same page with no special content under the hero.
5. League strip with record, projections and WP.

**Next**
- ESPN read through a local proxy holding the cookies (never in the repo or GitHub secrets for a
  public repo), which turns ESPN from snapshot into live.
- Waivers: holes, recommended adds, FAAB guidance, deadline countdown, Wednesday results.
- Pending trades with expiry; trade deadline.
- News diff on rostered players (Sleeper `news_updated` as the trigger).
- Tuesday recap: points left on bench and missed zeros per league. Also the cheapest possible
  backtest of the dashboard itself: did following it avoid the zeros?

**Later**
- Notifications (push/email via a scheduled task) when a `ZERO` enters Do now and the page hasn't
  been opened. The same `attention.json` drives it.
- Exposure view and opponent-exposure hedging.
- League messages (ESPN only).
- σ fitted per league from last season; `P(inactive)` priors calibrated on 2025 inactives.
- Playoff stake multiplier and elimination fading.

## 9. Open questions for other workstreams

- **UX/IA:** is the dashboard the root URL, with the draft board one click away year-round and
  promoted to hero in draft season? (This doc assumes yes.)
- **Start/sit engine:** can it emit `win_prob` for current and recommended lineups, and
  `p_inactive` per flagged player? If not, the dashboard falls back to the coin-flip conversion.
- **Pipeline:** where do private-league snapshots live so they never reach the public repo?
- **Camden:** which league is on ESPN vs CBS, and the third league's name and format.
