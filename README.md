# Fantasy Sports Assistant

A personal hub for fantasy leagues across platforms, with the longer-term goal of
showing sports bets in the same place. The intended home screen should answer
what needs attention across leagues, then let Camden reach the relevant lineup,
waiver, matchup, draft, or bet without opening every app to find it.

**Current state:** the finished, tracked app is a 2026 fantasy football draft
board. It has a 12-team half-PPR Sleeper profile and a 10-team profile for Dad's
weekly-bucket league. The multi-league dashboard and league-aware tools are still
prototypes and product proposals under `prototypes/` and `docs/product/`; they are
not wired into the board or a deployed app yet. Lineup changes and bet placement
are not implemented.

The draft board combines public draft timing, an expert board, custom projection
models, and live injuries.

```
draft-board-2026.html   presentation — hand-edited, never overwritten
board-data.js           generated — overwritten every refresh
rankings.csv            generated — same data, spreadsheet form
CLAUDE.md               project context for Claude Code
REFRESH.md              runbook: "Read REFRESH.md and do a full refresh"
refresh/                inputs + build chain
docs/product/           proposed product, UX, design, and dashboard behavior
prototypes/dashboard/   static home-screen mockup with fictional data
prototypes/draft-board/ league-neutral scoring and settings experiments
prototypes/start-sit/  read-only Sleeper start/sit experiment
```

## Use

Open `draft-board-2026.html` in any browser. Tap a row to cross a player off, or
hit the **+** next to a name to put him on your own team. State persists in
localStorage, so closing the tab mid-draft is safe; "Reset board" clears it.
Filter by position to switch the tier bands from overall to positional.

Use **Rank for → Sleeper league / Dad's league** at the top to switch scoring and
roster logic. Drafted players and My Team are shared between views, so switching
never loses draft state.

### Dad's league profile

The alternate profile models the supplied weekly passing/rushing/receiving yard
buckets, position-specific reception tiers, distance-based TDs, kicker and DST
rules, two unrestricted flexes, and eight bench spots. Weekly buckets use 40,000
simulated games per player. No projection feed supplies touchdown length, so those
points use a documented league-average distance distribution. The profile is
calibrated for the confirmed **10-team**, 18-round league.

Three panels sit above the board:

- **Best available** — top of the board plus the best player left at each skill position
- **Value coming up** — where your rank most disagrees with the room, limited to
  players actually in range of your next pick and capped at two per position. A
  +37 edge on someone going 90 picks from now isn't a decision you get to make,
  and without the position cap the TE premium turns this into a tight-end list.
- **My team** — your picks slotted into the real roster, with a bye-week clash warning

Type your **next pick** number and the *Lasts* column fills in: the chance each
player survives to that pick, from FFC's real ADP dispersion. Sort by it to find
who you must take now versus who will still be there.

### Sleeper live sync

Paste your Sleeper **draft id** and your **slot** (1–12), then hit Sync. The board
polls Sleeper's public picks endpoint every five seconds, crosses off everyone
taken, routes your own picks into *My team*, and recomputes your next pick from
the snake order. No auth, no setup. It gives up after three consecutive failures
rather than hammering the API, and you can always fall back to tapping rows.

The draft id is the long number in your Sleeper draft URL.

## Rebuild

Install the data dependencies once:

```bash
python3 -m pip install -r requirements.txt
```

Then rebuild from the project root:

```bash
python3 refresh/build.py
```

Takes about fifteen seconds and generates both ranking profiles. Every source is cached independently for six hours in
`refresh/pubranks_cache.json` (gitignored). A failure uses that source's last known
good copy without making it look newly fetched. The build aborts before overwriting
if core coverage, injuries, source freshness, player identity, or K/DST floors fail.

## Columns

| | |
|---|---|
| **#** | blended rank — 50% custom model in the Sleeper view, 65% in Dad's view |
| **Lasts** | chance he's still there at your next pick, from FFC's real ADP mean and dispersion |
| **Market** | FFC/Yahoo half-PPR ADP lane, weighted 2 / 1 |
| **Expert** | RotoBaller's free, expert-authored half-PPR overall Top 100 |
| **Model** | where the projection alone ranks him, ignoring every public board — the half of this that isn't aggregated ADP |
| **Edge** | outside anchor minus blended rank; positive means a potential discount |

In Dad's view, **Market** instead uses the median of FFC, Yahoo, and FantasyCalc
half-PPR signals. This prevents a single platform outlier from defining the
headline market number; the Sleeper view keeps its format-exact FFC-led weighting.

Badges: **SLEEPER** = 25+ slots later on FFC's half-PPR ADP than he ranks here,
outside the top 75. **VALUE** = 18+ slots of edge. **FADE** = 18+ the other way.

### Kickers and defenses

They're in the pool and scored properly, but the model deliberately discounts
them. Raw value-over-replacement says the best defense is ~38 points clear of a
replacement one — true on paper, and misleading. Kicker scoring is close to noise
year over year, and both positions get streamed off waivers all season, so most of
that projected edge is not something you can draft against.

So their VOR is scaled to the share worth planning around (K 0.15, DST 0.30), which
moves them late in the **Model** column itself rather than hiding a model that still
wanted a kicker in round 5. On top of that, no defense appears before **pick 145**
and no kicker before **pick 169** — rounds 13 and 15 of a 16-round, 192-pick draft.
Only the top 12 of each are placed there, interleaved with bench fliers, since only
one per team is ever drafted.

Dad's 10-team, 18-round profile keeps the same round strategy: DST cannot appear
before pick 141 (round 15) and K before 161 (round 17). Only the top 10 of each
are inserted into the draftable range.

Full methodology is behind the "How this works" button on the board itself.

## Refresh schedule

The GitHub Actions workflow has a hard cutoff of 2026-09-07 19:40:09 UTC. Scheduled
and manual runs after that instant are clean no-ops. The generated 2026 board is
therefore an archived draft snapshot, not an in-season data feed.

## Data sources

All rankings come from free, public, no-auth endpoints, fetched at build time by
`refresh/sources.py`. Nothing here is scraped from behind a paywall.

| Source | What it gives | Endpoint |
|---|---|---|
| [Fantasy Football Calculator](https://fantasyfootballcalculator.com) | Real **half-PPR, 12-team ADP** from thousands of public mock drafts — the only source whose format matches this league exactly, so it anchors the blend | `/api/v1/adp/half-ppr` |
| [RotoBaller](https://www.rotoballer.com/nfl-fantasy-football-rankings-tiered-ppr/265860/rankings?spreadsheet=half-ppr&league=Overall) | Free, expert-authored **half-PPR overall Top 100** — the editorial expert lane | structured JSON-LD on the public rankings page |
| **FantasyCalc** | Market value at `ppr=0.5&numQbs=1&numTeams=12` — sentiment and 30-day trend, not ADP | `api.fantasycalc.com/values/current` |
| ESPN | PPR ADP context (`ownership.averageDraftPosition`); displayed in details but excluded from the half-PPR blend | `lm-api-reads.fantasy.espn.com` |
| **Sleeper (injuries)** | **Live injury status** — IR / PUP / Out / Doubtful / Questionable plus body part, updated constantly | `api.sleeper.app/v1/players/nfl` |
| Yahoo | Public draft-analysis average pick | `pub-api-ro.fantasysports.yahoo.com` |

The outside anchor deliberately keeps unlike signals separate: **55% half-PPR
market ADP, 30% expert rank, 15% FantasyCalc sentiment**. ESPN is PPR context only.
The final rank blends that anchor 50/50 with the league-specific model.

### Projections

The stat projections are a **three-source consensus**: the hand-entered baseline in
`players.py`, averaged with ESPN's and Sleeper's own season projections. 219 of 220
players carry two or more sources.

This replaced a single hand-entered source, which was the model's biggest weakness —
every ranking inherited its errors. It also carried **integer touchdown counts**: 28
players sat at exactly 7 receiving TDs. A touchdown is 6 points, so that rounding
alone moved players several slots. The consensus has 70 distinct TD values instead
of 18.

Sleeper's feed also carries `fum_lost`, so the league's **−2 per lost fumble** is
modelled for the first time, and projected interceptions replaced a hand-kept table.

A feed whose line implies a different *role* for a player — a projected starter
listed as a deep backup — is rejected rather than averaged in.

### Injuries

Live from Sleeper's player feed on every build. Injured players get a badge, and
IR / PUP / Out / Doubtful / Sus are struck through and **excluded from the value
panel** — cheap for a reason is not the same as cheap.

The build also cross-checks that feed against the hand-set `avail` in
`players.py`. For a feed-confirmed inactive player whose availability is still
at least 0.95, `proj.py` caps it automatically and prints the change. Lower
hand-set values are preserved.

Two sources were tried and rejected rather than padding the count. **Sleeper**
publishes no ADP at all — `search_rank` is search popularity, and their GraphQL has
no ADP field either (every draft query needs a `draft_id`). **MyFantasyLeague** has
a real ADP endpoint but no way to exclude superflex drafts, and their pool is full
of them: measured against FFC, MFL's QBs went an average of 38 slots earlier (Josh
Allen 3rd overall vs FFC's 33rd) while RBs and WRs went later. That would have
wrecked QB ranking in a 1QB league.

Season stat projections and the betting-market layer are point-in-time snapshots
in `refresh/players.py` and `refresh/market.py`. Green/red flag notes are
hand-written. Coverage is uneven by design: a player unranked by one source shows
`NR` and is simply excluded from that player's average, and Sleeper covers the
full pool so every player keeps at least one column.

## Working with Claude and Codex

`AGENTS.md` (Codex) and `CLAUDE.md` (Claude Code) carry the same project rules.
Read the current code and Git status at the start of a task; these files preserve
intent but can lag implementation. Use a focused branch for each change, review
the diff and tests, then merge it before the other assistant starts a dependent
change. If work overlaps, use separate worktrees and integrate through Git rather
than editing the same checkout at once. Keep unfinished files visible in the
handoff; do not reset or overwrite another assistant's uncommitted work.

The existing board's key boundary is generated data in `board-data.js` versus
hand-edited presentation in `draft-board-2026.html`. A data refresh must not
regenerate the HTML. This boundary applies whichever assistant makes the change.
