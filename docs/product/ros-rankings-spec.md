# Players page — rest-of-season upgrades (spec)

Status: proposal, not built. Author: Claude Code, 2026-09-30. Branch `claude/ros-rankings-spec`.
Design references: `docs/product/design-brief.md` (project) and
`~/Documents/Second Brain/Design/Personal Web Design System.md` (global). Where they differ,
the project brief wins (red `#980F26` accent is a deliberate project exception to the global
earthy-accent default).

## Inspiration, not a source

Camden pointed at DraftSharks' ROS half-PPR page as a good example. Its *presentation*
ideas are worth borrowing; its *numbers* are not usable. DraftSharks is a paid,
largely paywalled service, and the project rule is no paid or paywalled sources ("free does
not automatically mean reusable"). Nothing in this spec fetches, scrapes, or copies DraftSharks
data. It may be used by a human as an eyeball benchmark only.

## What exists today

`app/season.py` sums Sleeper's `pts_half_ppr` weekly projections for weeks
`current+1..17`, skill positions only, and `app/players.html` shows Rank · Player · ROS
points · Per game · Games, with a "How these rankings work" disclosure. Rules in CLAUDE.md
that constrain this spec: independent of the frozen draft pipeline; standard half-PPR; current
week excluded; no claimed expert consensus, trade values, or custom scoring; preserve source
dates and complete-week coverage checks; placeholder ADP rows are not projections.

## Proposed additions (in priority order)

Each is buildable from Sleeper data we already fetch, so none needs a new source.

### 1. Position filter + positional rank (P0)
- Segmented control: All flex · QB · RB · WR · TE. QBs already rank separately.
- Show `WR12`-style positional rank beside overall rank. Pure display over existing data.

### 2. Tiers (P0)
- Break each position list into tiers where the drop in ROS points to the next player is large
  relative to the local spread (e.g. gap > 1.0 × rolling SD of the previous 8 gaps; tune on real
  data and freeze the rule in code with a comment).
- Render as a quiet labelled divider row ("Tier 3"), not colored backgrounds — per the global
  system, status/grouping never by color alone, and cards/boxes only where they group meaning.

### 3. Schedule strength for remaining weeks (P1)
- Derive opponent difficulty directly: for each remaining week, Sleeper
  projection rows carry the opponent (verify field name, likely `opponent`). Compute, per
  position, average fantasy points allowed by each defense from Sleeper weekly **stats**
  (`/stats/nfl/{season}/{week}`) for completed weeks.
- Show a compact 1–5 schedule rating plus a disclosure with the week-by-week opponent strip.
  Early season sample is tiny (3–4 games): label it "early, low confidence" until week 6.
- Note: Sleeper's projections likely already price matchups, so this is context, not a rank input.
  Do **not** re-weight ROS points by it (would double-count).

### 4. Movement since last snapshot (P1)
- The dashboard already keeps dated snapshots. Persist each successful ROS build's ranks and show
  ▲3 / ▼5 vs the previous snapshot at least 5 days old. Tooltip gives the dates compared.
- If no qualifying previous snapshot exists, show nothing (never a fake 0).

### 5. Bye week + injury badge columns (P1)
- Bye week from the weeks where a player has no projection row *and* his team has no game
  (distinguish from "missing projection", which today silently reduces Games). Injury badge uses
  the existing `injury_status`, words not color alone.

### 6. Roster context from connected leagues (P2)
- A chip on rows for players on your rosters ("Yours · 2 leagues") and a "Show only free agents in
  <league>" filter. Uses league data the app already imports; no new source.

## Explicitly out of scope unless Camden asks
- League-custom scoring for ROS (TE premium, yardage bonuses). CLAUDE.md currently says standard
  half-PPR only; changing that is a decision, and the draft-board settings schema in
  `prototypes/draft-board/` would be the way to do it.
- Any expert consensus, ECR, or trade-value column.
- Blending ESPN weekly projections — plausible later as a second free source, but it changes the
  "Sleeper projections" claim on the page and needs its own coverage checks.

## Layout sketch (desktop)

```
Rest of season                                  [Refresh]
Week 5–17 · Sleeper projections · updated Sep 30 9:12
[All flex] QB  RB  WR  TE                  [search]
Rank  Pos   Player              ROS pts  /G   Sched  Move  Bye
 1    RB1   ▣ Bijan Robinson     214.3  16.5  ●●●○○   ▲2    12
 2    WR1   ▣ Ja'Marr Chase      208.9  16.1  ●●○○○   –     10
──── Tier 2 ─────────────────────────────────────────────
...
▸ How these rankings work
```

Phone (375px): two-line rows — line 1 rank, team mark, name, ROS pts; line 2 pos rank, /G, sched,
move. Schedule strip and method stay in disclosures.

## Verification
- Unit tests in `app/tests` for tier breaks (deterministic on a fixture), movement with and
  without an old-enough snapshot, and bye vs missing-projection distinction.
- Coverage check stays: a week below the 150-player threshold still fails the whole build rather
  than publishing partial ROS totals.
