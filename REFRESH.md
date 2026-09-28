# Refresh runbook

Historical 2026 draft-board runbook for Claude Code or Codex. The automatic
refresh cutoff has passed; this is a manual workflow for future board work.

---

## Rule zero

Edit files in `refresh/` only. **Never edit `draft-board-2026.html` during a refresh** —
that file is hand-tuned presentation and the whole architecture exists to protect it.
`board-data.js` and `rankings.csv` are generated; overwrite them freely. The data
file contains both `sleeper` and `dad` profiles.

## What is automatic now, and what still needs you

Most of the data refreshes itself. `refresh/sources.py` pulls **eight live feeds** on
every build — half-PPR ADP, an expert board, market sentiment, ESPN PPR context,
live injuries, and two projection feeds — so
there is nothing to paste for any of them.

That leaves exactly two things that are genuinely hand-maintained, and they are the
whole job:

| File | What still needs judgement |
|---|---|
| `players.py` | **`avail`** — the share of the season you expect a player to be up for |
| `hp_data.py` | the **green/red flag** notes, and the player pool itself |

---

## 1. The two hand-maintained inputs

### `refresh/players.py` — `avail` above all

`avail` is the share of the 17-game season the player is expected to be available
(1.00 = full). It is **injury judgement, not a stat projection**, which is why the
feeds don't overwrite it and why it matters more than anything else you touch.

- Lower it for new injuries; raise it when someone is cleared. Delete anyone out
  for the year.
- Check training-camp and preseason reports, IR moves, roster cuts, suspensions,
  and depth-chart changes.
- **The build audits this for you** — see step 3. Do that step before hand-hunting
  for injuries; it will tell you exactly who is stale.

The stat lines in this file still matter, but less than they used to: they are now
one of three projection sources (see `proj.py` below), so a single number being
off no longer swings a ranking on its own.

### `refresh/hp_data.py` — the pool and the flags

- The `sl` / `es` / `fpros` / `cons` numeric columns are **dead**. Nothing reads
  them. Ignore them; don't bother updating them.
- What matters is the player list (name, team, pos) and the two flag strings.
- Rewrite any flag that has gone stale. A red flag saying "groin injury, missing
  preseason" is wrong once he's playing. **This decays fastest and is the part
  most worth your attention.**

---

## 2. The live feeds — nothing to paste, but check they landed

`refresh/sources.py` fetches all of these, cached **per source** for six hours in
`pubranks_cache.json`. A failed source keeps its original successful-fetch time;
stale data is never restamped as fresh. Force a fresh pull with:

```bash
python3 refresh/sources.py --refresh
```

| Feed | What it gives |
|---|---|
| `ffc` | **Half-PPR 12-team ADP** from thousands of live mock drafts — the anchor |
| `yahoo` | Yahoo average pick (their default is 0.5/reception) |
| `rotoballer` | Free, expert-authored **half-PPR overall Top 100** — the expert lane |
| `fcalc` | FantasyCalc value/trend at half PPR / 1QB / 12 teams — sentiment, not ADP |
| `espn` | ESPN **PPR** ADP — context only, excluded from the half-PPR blend |
| `injuries` | Live injury status + body part, from Sleeper's player dump |
| `espnproj` | ESPN's own season projections (fractional TDs) |
| `sleeperproj` | Sleeper's season projections — the only source with `fum_lost` |

Expect output like:

```
  ffc       231 2921 drafts, 2026-08-20..2026-08-25
  yahoo     217 217 with ADP
  rotoballer 100 100 expert half-PPR ranks, updated from the live rankings page
  fcalc     192 192 ranked (half-PPR/1QB/12tm)
  espn      400 400 with ADP
  injuries  258 258 carrying an injury tag
  espnproj  324 324 season projections
  sleeperproj  560 560 season projections
```

**If any line says `FETCH FAILED`, say so in the report.** It falls back to that
source's last known good copy. The build refuses to publish if FFC, RotoBaller, or
injuries are missing or more than 48 hours old.

### Don't add sources without reading why these were rejected

- **Sleeper ranks** — `search_rank` is search popularity, not ADP. Sleeper
  publishes no ADP anywhere; their GraphQL has no adp field either.
- **MyFantasyLeague** — real ADP, but no way to exclude superflex drafts, and its
  pool is full of them. Measured here, MFL's QBs ran 38 slots early.
- **FantasyPros** — needs an API key and renders its ADP client-side.
- Nothing **paid or paywalled**. The repo is public.

### `refresh/proj.py` — consensus projections

Averages `players.py` with the two projection feeds, 219/220 players carrying 2+
sources. Nothing to edit. It keeps the pool and `avail` from `players.py`, and
rejects a feed whose line implies a *different role* for a player rather than
averaging it in.

### `refresh/market.py` — mostly dormant

Only `AWARDS` is still used, for the small odds badge next to a name. `WIN` and
`PROPS` are kept but unused — the betting layer was removed because it moved
skill players a mean of 1.8 slots. Don't wire it back in without asking.

---

## 3. Rebuild

```bash
python3 refresh/build.py
```

Runs consensus projections → Sleeper scoring/bonus simulation/blending → Dad
weekly-bucket simulation/blending, then writes `board-data.js` and `rankings.csv`.
Both scoring simulations use 40,000 samples per player. It aborts rather than
overwriting if either profile loses players or violates its K/DST floors.

### Read the injury audit — this is the important part

The build cross-checks the live injury feed against the hand-set `avail`. If a
player tagged IR/PUP/Out/Doubtful/Sus is still at or above 0.95 availability,
`proj.py` caps the value and prints the change. A lower, deliberately hand-set
value is preserved:

```
  2 availability caps applied from the live injury feed:
    Alec Pierce              PUP       avail 1.0 -> 0.35  (set it deliberately in players.py)
    Zach Charbonnet          PUP       avail 1.0 -> 0.35  (set it deliberately in players.py)
```

**Review every cap.** Set `avail` deliberately in `players.py` for the next build.
If the feed is wrong, document that judgement and use a value below 0.95 so the
automatic cap does not override it. Structural and stale-source checks can still
abort the build before generated files are overwritten.

---

## 4. Verify

- `board-data.js` has a fresh `BOARD_META.generated` date and two ~249-player profiles
- Open `draft-board-2026.html`, confirm it renders, rows cross off, the **+**
  button adds to My Team, and the position filters switch the tier bands
- Switch to **Dad's league** and confirm ranks, tier bands, roster flexes, and the
  scoring breakdown in a player-detail drawer all update without losing My Team
- The table should have **9 columns**; the individual sources and flags live in
  the player-detail drawer
- Spot-check two or three players whose news you just changed

## 5. Report

Only the delta. Don't restate the board.

- Every line from the injury audit, and what you did about it
- Players who moved 10+ slots, and why
- New or dropped SLEEPER / VALUE / FADE badges
- Any feed that couldn't be reached

---

## Locked unless Camden says otherwise

- **Scoring:** half PPR · 0.75 per catch for TE · INT −2 · **fumble lost −2**
  (modelled now — Sleeper projects `fum_lost`) · yardage bonuses are **exclusive
  tiers**: +3 for 100–199 rush/rec and +4 for 200+; +3 for 300–399 pass and +4 for
  400+ · kickers use **normal** scoring (3 under 40, 4 from 40–49, 5 from 50+, PAT
  1, miss −1) — the 0.10/yard bonus on the league page is a setup error being
  fixed, see CLAUDE.md · DST points-allowed tiers simulated per game · 2-pt
  conversions still not modelled (no source projects them)
- **Roster:** 12 teams — QB, 2RB, 2WR, TE, RB/WR/TE flex, WR/TE flex, K, DST,
  6 bench. That is 16 spots, so a full draft is **192 picks**.
- **Dad profile:** supplied bucket/distance scoring; **10 teams** — QB, 2RB, 2WR,
  TE, two RB/WR/TE flexes, K, DST, 8 bench; 18 rounds / 180 picks. Its final blend
  is 65% custom model, 35% outside timing context. Dad's Market is the median of
  FFC, Yahoo, and FantasyCalc half-PPR ranks; its outside anchor is 70% that
  robust market / 30% expert. DST floor 141, K floor 161.
  TD length uses league-average distance distributions because no
  projection source carries it.
- **Blend:** 50% projection model, 50% outside-information anchor.
- **Outside lanes:** market 55% / expert 30% / sentiment 15%. Market itself is
  FFC 2 / Yahoo 1. ESPN is PPR context only and does not enter the blend.
- **K and DST are discounted on purpose**, in three layers: `RELIABILITY` scales
  their VOR (K 0.15, DST 0.30), `FLOOR` keeps DST out before pick 145 and K before
  169, and only the top 12 of each are placed there on a stride of 2. Don't
  "fix" any of it — see AGENTS.md or CLAUDE.md for the reasoning.
- **Replacement level** is computed endogenously by filling every starting slot in
  the league first. Don't hardcode it.
- **Removed on purpose:** the betting layer and the "scoring fit" column. Neither
  comes back without asking.

## Automatic refresh

`.github/workflows/refresh-board.yml` ran the same validated build every day
through **7 September 2026 at 12:40:09 PM PDT**. At and after that exact cutoff,
scheduled and manual runs are clean no-ops. Before cutoff, it commits only
`board-data.js` and `rankings.csv`, preserving the rule that automation never
overwrites `draft-board-2026.html`.
