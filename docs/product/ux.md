# Product structure and flows

Status: proposal, 25 Sep 2026 (NFL week 4). Owner of this doc: UX.
Sibling docs (other agents): competitive research, visual design system, draft
board improvements, start/sit engine, home-dashboard content. This doc sets the
**skeleton** those plug into: who it's for, where things live, how you get from
"I have leagues on three platforms" to "my lineups are right", and what the
no-backend architecture allows at each stage.

---

## 1. Where we're starting from

Today the product is one page, `draft-board-2026.html`, plus a generated
`board-data.js`. It is good at one job (drafting) for two hard-coded leagues:

- **Profiles** are baked in at build time (`sleeper`, `dad`). Adding a league
  means writing Python (`score.py`, `dad_score.py`) and rebuilding.
- **State** is one localStorage key (`hp_board_v8`): drafted, mine, next pick,
  draft id, profile.
- **Live data** is exactly one client-side call: Sleeper's draft picks endpoint,
  which allows CORS.
- **Freshness** is one line: "Data as of 7 September 2026". The refresh workflow
  hit its requested cutoff on 7 Sep, so as of today that data is **18 days
  old**, and nothing on the page makes that feel alarming. That is the most
  important UX lesson for the multi-league version: in-season, stale data looks
  exactly like fresh data unless we make it look different.

What carries forward: the data/presentation split, the "tap to act, state
persists locally" interaction model, the Sleeper sync pattern (poll, give up
after three failures, manual fallback always available), and the explainability
culture (Market / Expert / Model columns, "How this works").

---

## 2. Users and jobs-to-be-done

### Primary: Camden (user zero)

Plays in Sleeper, ESPN and CBS leagues, helps run his Dad's league, lives on the
West Coast (1 pm ET kickoffs are **10 am PT**; inactives drop around **8:30 am
PT**). Comfortable with devtools and GitHub; will tolerate setup friction once,
not every week.

| When... | I want to... | So that... |
|---|---|---|
| Sunday morning, phone in hand | see every league's lineup problems in one list | I don't open three apps and miss one |
| A starter is ruled out | know the best legal replacement in *that* league's scoring | I swap in 30 seconds, not 5 minutes |
| Tuesday night / Wednesday | see who's worth a waiver claim or FAAB bid per league | I don't lose a pickup to inattention |
| Wed-Sat as news breaks | know which news touches *my* players, in which leagues | I ignore the 95% that doesn't matter |
| A player is questionable in a late game | know whether to hedge (flex placement) | I keep a swap available after early games |
| Draft season | draft off rankings built for this league's settings | "TE premium" and "Dad's buckets" are priced in |
| Helping Dad | view Dad's league as a first-class league, maybe hand him a link | he gets the same advice without the setup |

### Secondary: a shippable user

A multi-league player (2-6 leagues, mixed platforms) who is not a developer.
Differences that matter for design:

- Will not open devtools to copy cookies. ESPN private leagues and CBS need a
  path that doesn't look like "paste your session token here".
- Expects cross-device (phone Sunday, laptop Tuesday) without thinking about
  localStorage.
- Needs the "why" more, trusts the app less, and will churn on the first wrong
  recommendation that wasn't flagged as uncertain.

Design for Camden first, but never ship a flow that only works because the user
is Camden (e.g. "edit players.py"). Every Camden-only shortcut is labelled as
such in this doc.

### The weekly rhythm (in-season)

```
         Mon        Tue          Wed      Thu        Fri    Sat      Sun               Mon
         ───        ───          ───      ───        ───    ───      ───               ───
Games    MNF        -            -        TNF        -      (late    1pm/4pm/SNF       MNF
                                                             season)
Job      last       WAIVERS      news     lock TNF   news   news    INACTIVES 8:30 PT  last
         swaps      process      triage   starters   triage triage  final lineups      swaps
                    (overnight   next-wk  (Thu 5:15           Q-tags  swap late-game
                     Tue->Wed    lineup   PT)                 final   hedges
                     most plats) draft
App      Home =     Home =       Home =   Home =     Home = news digest  Home =            Home =
mode     "MNF       "Waivers"    "Plan"   "Thu lock"                     "Game day"        "MNF"
         swaps"
```

The Home screen is not a static dashboard; its top card changes with the day
(section 5.1). Draft season (Aug to early Sep) is a separate mode where Draft
becomes the primary destination.

---

## 3. Information architecture

### 3.1 Top level

```
┌──────────────────────────────────────────────────────────────┐
│  Home        cross-league "what needs doing now"              │
│  Leagues     list -> one league (Lineup · Roster · Waivers ·  │
│              Matchup · Draft · Settings)                      │
│  Players     cross-league search + player page ("my exposure")│
│  Draft       the existing board, now "draft for league X"     │
│  (gear)      Connections, data freshness, export/import       │
└──────────────────────────────────────────────────────────────┘
```

Mobile: bottom tab bar with **Home · Leagues · Players · Draft**. In-season the
Draft tab is demoted: it stays reachable inside each league (League > Draft) and
its tab slot becomes **Waivers** (cross-league claim list) from week 1 onward.
Seasonal swap is an open decision (section 10).

Desktop: same four destinations as a left rail; Home uses two columns.

### 3.2 Cross-league vs single-league: the rule

- **Cross-league views** answer "what should I do?" -- Home, Waivers, Players.
  Every row carries a **league chip** (short name + platform color) so you never
  have to wonder which league an item belongs to.
- **Single-league views** answer "show me this league" -- Lineup, Roster,
  Matchup, Settings, Draft. They carry a **league header** that is always
  visible and always shows the scoring summary.

Switching leagues inside a league view is a header dropdown (not a trip back to
the list). It keeps you on the same sub-tab: Lineup in league A -> switch ->
Lineup in league B. That is the generalisation of today's "Rank for: Sleeper
league / Dad's league" toggle, which kept draft state while switching profile.

URL routing (hash-based so it works on static hosting and off `file://`):

```
#/home
#/leagues
#/league/{localLeagueId}/lineup      (also /roster /waivers /matchup /draft /settings)
#/players  #/player/{sleeperPlayerId}
#/draft                               -> redirects to last-used league's draft
#/settings
```

`localLeagueId` is ours (e.g. `slp-1181...`, `espn-44921`, `man-3`) so manual
leagues and platform leagues route the same way.

### 3.3 Where the existing draft board goes

It becomes **League > Draft** (and the Draft tab in draft season). Concretely:

- "Rank for" profile buttons -> the league header's switcher. A league has a
  draft profile if its settings can be scored; Camden's two hand-tuned profiles
  (`sleeper`, `dad`) become the draft profiles of those two leagues.
- The draft-sync rail (draft id + slot) is prefilled when the league came from
  Sleeper: `GET /v1/league/{id}` returns `draft_id`, and the draft object gives
  `draft_order` for the user's slot. Two fields the user types today disappear.
- Draft state keys by league (`draft:{localLeagueId}`) instead of one global key,
  so two mock drafts don't collide. Migrate `hp_board_v8` into the Sleeper
  league on first load.
- Best available / Value coming up / My Team panels are unchanged in behaviour.
  After the draft, "My Team" hands off to the league's Roster view (which is
  now fed by the platform, not by taps).

The draft board's internals belong to the draft-board agent; this doc only moves
it into the IA.

### 3.4 The league object (what every screen can rely on)

```
League {
  localId, platform: sleeper|espn|cbs|manual, platformLeagueId, season,
  name, shortName (user-editable, 6 chars max: "MAIN", "DAD", "WORK"),
  color, teams, myTeamId,
  rosterSlots: [QB, RB, RB, WR, WR, TE, FLEX(RB/WR/TE), FLEX(WR/TE), K, DST, BN x6, IR x2],
  scoring: { normalized stat -> points map, plus bonuses/tiers },
  scoringModel: "generic" | "custom:dad",      // which scorer prices it
  unmodelled: ["2-pt conversions", ...],        // shown, never hidden
  waiverType: FAAB|rolling|reverse, waiverDay, faabBudget, faabLeft,
  source: { method: api|proxy|paste|form, fetchedAt, status }
}
```

---

## 4. Onboarding and connecting leagues

### 4.1 Principle: be honest per platform

The three platforms are not equally connectable, and the UI should say so up
front instead of failing mid-flow. The add-league screen shows each platform
with what it gets you:

| Platform | What we ask for | What we get | How (stage) |
|---|---|---|---|
| **Sleeper** | username | all leagues, settings, rosters, matchups, drafts; auto-updating | direct browser calls, no auth, CORS allowed (stage 1) |
| **ESPN public league** | league id (or league URL) | settings, rosters, matchups | needs a proxy: ESPN's API is not built for cross-origin browser calls (verify before stage 2; assume proxy) |
| **ESPN private league** | league id + either the bookmarklet export or `espn_s2`/`SWID` | same as public | bookmarklet (no secrets leave the browser) or cookie pair via proxy (stage 3) |
| **CBS** | paste roster + pick settings | a manual league; roster ages until you re-paste | manual (stage 1); anything better is stage 3+ and uncertain |
| **Anything else** | paste | manual league | stage 1 |

Nothing writes to a platform. Every recommendation ends in an "Open in
Sleeper / ESPN / CBS" link; the user makes the change there. (Camden's personal
`set-lineups` Claude skill can drive his logged-in browser, but that is a
Camden-only tool, not a product feature, and shouldn't shape the IA.)

### 4.2 Sleeper: username -> leagues (the happy path)

```
GET /v1/user/{username}                         -> user_id, avatar
GET /v1/state/nfl                               -> season, current week
GET /v1/user/{user_id}/leagues/nfl/{season}     -> league list
per selected league:
  GET /v1/league/{id}            -> scoring_settings, roster_positions,
                                    total_rosters, settings.waiver_type, draft_id
  GET /v1/league/{id}/users      -> map owner_id -> display name
  GET /v1/league/{id}/rosters    -> my roster (starters, players, reserve)
  GET /v1/league/{id}/matchups/{week}
```

The 5 MB `/v1/players/nfl` dump is **not** fetched from the browser (Sleeper
asks for at most once a day, and it's too heavy for a phone on stadium wifi).
The pipeline already downloads it; it publishes a slim `players.js`
(id, name, team, pos, bye, injury status, as-of) alongside `board-data.js`.

### 4.3 ESPN

- Accept a pasted league URL and extract `leagueId` (people don't know their
  league id; they know the URL).
- Try public first. If ESPN answers "not authorized", the league is private and
  the flow branches with plain language: "This league is private. ESPN doesn't
  offer a sign-in we can use, so pick one:"
  1. **Bookmarklet export (recommended).** Drag a button to the bookmarks bar,
     open the league on espn.com, click it. The bookmarklet runs on ESPN's own
     page using the user's own session, fetches the league JSON, and hands it to
     our app (copy-to-clipboard + paste, or postMessage). Nothing secret ever
     reaches us. Downside: re-export to refresh; awkward on phones. **Needs a
     technical spike** to confirm the league API is reachable from the
     fantasy.espn.com origin.
  2. **Cookie pair.** Paste `espn_s2` and `SWID`. We explain that these are a
     login session, show exactly where they're stored (this device only, stage
     3 proxy is stateless and forwards them per request), and offer "forget"
     at any time. Label it **Advanced**. Never the default for a shippable
     product.
  3. **Manual** (same as CBS).
- Map ESPN's `lineupSlotId`/`statId` numbers to our normalized slots and stats
  in one table owned by the import code; unmapped settings go into
  `unmodelled`, never silently dropped.

### 4.4 CBS

CBS's fantasy API is designed for apps running inside CBS with a league-scoped
token; there is no username-based public read. Don't pretend otherwise. MVP:

1. Pick "CBS / other", name the league.
2. **Settings:** start from a template (Standard / Half-PPR / Full PPR /
   Sleeper-style with TE premium), then edit the handful of fields that matter:
   teams, roster slots, reception points (per position), pass TD, INT, bonuses.
   A "paste scoring page" textarea attempts a best-effort parse and shows what
   it understood as a diff against the template for the user to confirm.
3. **Roster:** paste the team page text (or type names); we fuzzy-match to
   player ids and show unresolved names inline to fix. Matching reuses the
   pipeline's identity logic.
4. The league is marked **Manual** everywhere, with "roster as of {time}" and a
   nudge after each waiver day: "CBS rosters don't update automatically.
   Re-paste after waivers?"

### 4.5 Import -> show -> confirm settings (settings-awareness)

Every newly added league lands on its **Settings summary** before anything
else, because every downstream recommendation depends on it. The screen does
three things:

1. **Headline chip** (reused in the league header everywhere):
   `12T · ½PPR · TE 0.75 · 100yd +3 · 2 FLEX`
2. **"What's different here"**: an auto-generated diff against standard
   half-PPR, ranked by fantasy impact, each with a one-line consequence:
   - "TE catches pay 0.75 -- tight ends are worth more than public rankings say."
   - "100/200-yard bonuses -- boom weeks from volume backs and WR1s matter more."
   - "Kickers score normally; your scoring page shows per-yard FG points (flagged)."
3. **"Not modelled"**: settings we can read but don't price (2-pt conversions,
   return yards, odd bonuses). Shown as grey chips, with the size of the likely
   effect when known. This is the "never silently wrong" rule applied to
   scoring.

The user can **override** any imported value (Camden's kicker case: the page
says one thing, the league is being fixed). Overrides show a pencil icon and
"differs from {platform}" so they never become invisible.

Settings live in the league header on every league screen. Every "why" line in
Lineup/Waivers can cite a setting ("+1.5 from TE premium").

---

## 5. Key flows

### 5.1 First run

1. Land on an empty Home: one card, "Add your first league", with the platform
   table from 4.1 (Sleeper first, it's instant).
2. Enter Sleeper username -> show avatar + league list for 2026 with checkboxes
   (default: all redraft leagues checked, dynasty/best-ball unchecked with a
   note if we don't support them).
3. For each checked league: import, then a compact settings confirmation
   (headline chip + top 2 "what's different" lines + "Looks right" button).
   Multiple leagues confirm in a stack, not a wizard per league.
4. Ask for short names/colors (prefilled: first word of league name, platform
   color). Skippable.
5. "Add another platform?" -> ESPN / CBS / done.
6. Land on Home, now populated. If it's in-season, the first card is whatever
   the day's mode says; if not, it's Draft.
7. Existing users: `hp_board_v8` draft state is migrated into the Sleeper league
   and a one-line toast says so.

Time target: Sleeper-only user to populated Home in under 60 seconds.

### 5.2 Sunday morning: lineup check across all leagues

Goal: phone, 8:30-9:45 am PT, every league correct before 10:00.

1. Open app -> Home in **Game day** mode. Top: a freshness strip ("Injuries 4
   min ago · Rosters: MAIN 2 min, DAD 2 min, WORK (ESPN) 6 h -- refresh").
2. **Action list**, sorted by urgency (kickoff time), then severity:
   - `OUT` or inactive starter (red)
   - empty starting slot / bye starter (red)
   - `Q` starter in early game with a comparable healthy bench option (amber)
   - start/sit upgrade above a threshold, e.g. +2.0 projected points (blue)
   - hedge suggestion: Q player in a late game sitting in a non-flex slot
     ("Move Kittle to FLEX so you can swap after 1 pm games") (blue)
3. Each row: league chip · verb · players · one-line why · **Open in {platform}**.
   Tapping the row expands: projection delta, the setting that drives it, data
   as-of, alternatives.
4. User opens Sleeper, makes the swap, comes back. On return (visibilitychange)
   we re-fetch that league's roster; the row flips to **Done** automatically
   for API leagues. For manual leagues the user taps "I did this" (and the
   roster copy updates locally).
5. When the list is empty: "All 3 lineups set. Next check: 12:45 pm PT for 4 pm
   games (2 players questionable)." -- an explicit all-clear, never just a
   blank screen.

### 5.3 Acting on an injured starter

Trigger: news (Wed-Sat) or inactives (Sun). Entry points: Home action row,
Players page, or League > Lineup (the starter's slot shows the badge).

1. Row reads: `MAIN · Replace Pacheco (OUT) -- best option: Warren from bench, 11.2 proj`.
2. Expand -> ranked replacements **for that slot in that league**:
   - bench players who fit the slot (incl. flex moves: "Move Pitts TE->FLEX,
     start Kincaid at TE" when a chain beats a direct swap)
   - top 3 free agents if the league is API-connected and a waiver/free-agent
     add is possible before lock (marked "requires add/drop, FA -- instant" or
     "waivers -- won't clear before Sunday")
3. Each option shows projected points in this league's scoring and one "why".
4. Choose -> Open in platform (deep link to the team page) -> return -> auto
   confirm (API) or "I did this" (manual).
5. Same player in multiple leagues: one grouped row, "Pacheco OUT in MAIN and
   WORK", expanding into per-league replacements (they differ, because rosters
   and scoring differ).

If the injury feed is stale when a game is under 2 hours away, the row is
prefixed with "Status as of {time} -- check inactives" rather than showing a
clean "Start".

### 5.4 Drafting with a league's settings

1. Draft season: Home top card is "Draft in {n} days: MAIN (Sleeper) Sep 9, 7 pm".
2. League > Draft opens the board already scored for that league. The header
   chip shows the settings; a banner if the league's draft profile is the
   **generic** scorer vs a hand-tuned one ("Scored from imported settings. Dad's
   bucket scoring uses the custom model.").
3. For Sleeper: draft id and slot prefilled; Sync is one button. For ESPN/CBS:
   the existing tap-to-cross-off and "next pick" input remain the path.
4. After the final pick: "Draft complete -> view roster" moves the user to
   League > Roster and switches the league into in-season mode.

The ranking method, panels and columns are the draft-board agent's call.

### 5.5 Adding a league mid-season

1. Gear or Leagues > **+ Add league** -> platform picker (4.1 table, with
   honest capability notes).
2. Platform-specific step (4.2-4.4).
3. Settings summary + confirm (4.5).
4. League appears in Leagues and in Home's action list immediately; if it's
   manual, Home shows a one-time card "WORK is manual: re-paste after waivers".

Removing a league is in League > Settings, with "forget stored credentials" for
ESPN cookie leagues surfaced as a separate, explicit action.

---

## 6. Principles

1. **Glanceable.** Home answers "am I OK?" in one second: a count of red/amber
   items per league, or an all-clear. Detail is one tap away, never on top.
2. **Say what to do, and why, in one line.** Grammar:
   `{league} · {verb} {player}{ over | for } {player} -- {reason}`.
   Reasons cite a concrete cause: an injury status, a setting, a matchup, a
   projection delta with units. Never "our model likes him".
3. **Explainable on demand.** Every recommendation expands into: the numbers,
   their sources, their as-of times, and what would change the call. Same
   spirit as the current Market / Expert / Model columns.
4. **Never silently wrong.** Every datum has an as-of. Three visual states:
   **fresh** (no decoration), **aging** (amber timestamp), **stale/failed**
   (red, and recommendations that depend on it are demoted to "check this"
   rather than "do this"). Thresholds depend on context: injuries are stale
   after 30 min on Sunday morning, 12 h midweek; rosters after the league's
   waiver run; projections after 24 h. A failed fetch shows the last good copy
   **labelled as such** (the pipeline already does this for sources; the UI
   must too). Unmodelled settings are visible (4.5).
5. **Respect game state.** Players whose game has kicked off are locked and
   visibly so; we never recommend an impossible move.
6. **Mobile first on game day.** 360 px wide, one hand, poor signal: the Home
   list must render from cache instantly and refresh in place; tap targets
   44 px; no hover-only information; no horizontal scroll (the draft board's
   wide table is the exception and gets a condensed mobile column set).
7. **Offline-tolerant.** Last known state is always shown, with its age, even if
   the network is down.
8. **Honest about platforms.** Capability differences (auto-sync vs manual) are
   shown per league, not buried in help text.
9. **Nothing leaves the device without saying so.** Especially ESPN cookies.

---

## 7. Architecture implications

### 7.1 What can stay static and client-side

| Need | Static-compatible? | How |
|---|---|---|
| App shell, routing | yes | one HTML (or small set of files), hash routing |
| Player pool, injuries, projections, rankings | yes | pipeline-generated JS/JSON, like `board-data.js` today |
| Sleeper leagues, rosters, matchups, drafts | yes | direct browser `fetch`, CORS allowed |
| League settings, overrides, manual leagues, draft state | yes | localStorage (+ `window.storage` inside Claude, as today) |
| Scoring an arbitrary league | yes, with a caveat | client-side scorer applies the league's point map to per-player stat projections published by the pipeline. Bonus tiers use per-player distribution parameters the pipeline also publishes, so the browser doesn't need to run 40k-game simulations |
| Cross-device | partial | **Export / import** a JSON file (or share-to-self) in MVP |
| Hosting for phone use | yes | GitHub Pages from the (already public) repo. Note: localStorage on the hosted origin is separate from `file://`, so first run on the hosted URL needs the import/migration |

Key consequence for the pipeline (to coordinate with the start/sit agent):
today's pipeline publishes **scored** profiles for two known leagues. A
multi-league product needs it to also publish **unscored weekly stat
projections + distribution parameters + injury status**, with the client
doing the league-specific scoring. Hand-tuned custom scorers (Dad's) can stay
as pipeline-generated profiles attached to a specific league.

### 7.2 Where a backend or proxy becomes necessary

1. **In-season freshness.** GitHub Actions cron runs at most every few minutes
   and fires unreliably at peak times; inactives land 90 min before kickoff.
   A daily build is fine Tue-Sat; Sunday morning needs refreshes every ~10-15
   min from 7 to 10 am PT, or a live source the client can call. (The current
   workflow is also past its 7 Sep cutoff and publishes nothing; in-season
   refreshing needs Camden to lift or replace that cutoff.)
2. **ESPN.** Cross-origin reads need a proxy even for public leagues (to verify);
   private leagues need the cookie pair forwarded server-side, because a browser
   page can't attach cookies for espn.com.
3. **CBS** beyond manual paste.
4. **Accounts / cross-device sync** without export files.
5. **Push notifications** ("Your starter was ruled out") require a server that
   watches for changes and a push subscription.

### 7.3 Recommended path

**Stage 1 -- static, Sleeper-native (now to ~week 8).**
GitHub Pages. Sleeper leagues auto-sync; ESPN and CBS as manual leagues.
Pipeline gains an in-season mode (weekly projections, slim players file) and a
denser Sunday schedule. Export/import for devices. Zero servers, zero secrets.

**Stage 2 -- one stateless edge proxy (e.g. a free-tier Cloudflare Worker).**
Two jobs only: (a) ESPN read proxy for public leagues, (b) a cached
injury/news endpoint the client can hit every few minutes on Sundays (the
Worker fetches upstream once, all clients share it). Stores nothing
per user. The static site still works if the Worker is down; affected data just
goes amber/red.

**Stage 3 -- private data.**
ESPN private leagues: bookmarklet export first (no server-side secrets); cookie
forwarding through the Worker as an advanced option, never persisted server
side. CBS research spike. Optional thin accounts (for sync + push) only if a
second real user (Dad) or a public launch makes it worth running a database.

Never in scope without a separate decision: writing lineups or claims to any
platform on a user's behalf.

---

## 8. Wireframes (low-fi)

### 8.1 Home -- game day, mobile

```
┌─────────────────────────────────┐
│ Sun Sep 27 · Week 4    ⚙        │
│ ● Injuries 4m  ● Rosters 2m     │
│ ▲ WORK roster 6h old  [refresh] │
├─────────────────────────────────┤
│ 3 things before 10:00 PT        │
│                                 │
│ ■ MAIN  Pacheco OUT             │
│   Start Warren (bench) · 11.2   │
│   Ruled out Fri (knee)    [Open]│
│                                 │
│ ■ DAD   FLEX empty              │
│   Start Jennings · 9.8          │
│   Bye filled nothing      [Open]│
│                                 │
│ ▲ WORK  Kittle Q (4:25 game)    │
│   Move to FLEX to keep a swap   │
│   Manual league      [I did it] │
├─────────────────────────────────┤
│ Later today                     │
│ 12:45 PT  2 Q players, 4pm games│
│ ✓ MAIN ✓ DAD after the above    │
├─────────────────────────────────┤
│ This week   MAIN  W 2-1  vs Joe │
│             DAD   L 1-2  vs Dad*│
│             WORK  W 3-0  vs Sam │
├─────────────────────────────────┤
│ [Home] [Leagues] [Players] [Waiv]│
└─────────────────────────────────┘
■ red  ▲ amber   * the matchup content is the home-dashboard agent's
```

### 8.2 Home -- Tuesday (waivers mode), desktop

```
┌──────────┬───────────────────────────────────────┬──────────────────────┐
│ Home     │ Waivers run tonight (MAIN 9pm PT,      │ Freshness            │
│ Leagues  │ WORK 9pm PT) · DAD rolling            │ Projections  2h  ●   │
│ Players  │                                       │ Injuries     2h  ●   │
│ Draft    │ MAIN  Claim J. Smith-Njigba  $14 FAAB │ MAIN roster  1m  ●   │
│ Waivers  │       drop Tucker · WR3 role, 8 tgt/g │ DAD roster   1m  ●   │
│          │ MAIN  Claim Mason (RB)  $6            │ WORK manual  3d  ▲   │
│          │       handcuff; Pacheco out 4-6 wks   │                      │
│ ⚙        │ DAD   Add Tracy (RB) · 3+ catch tiers │ Not modelled         │
│          │       pay here; 5 rec/g last 3        │ MAIN: 2-pt conv.     │
│          │ WORK  Re-paste roster after waivers ▲ │                      │
│          │                                       │                      │
│          │ Players you own in 2+ leagues (4) ▸   │                      │
└──────────┴───────────────────────────────────────┴──────────────────────┘
```

### 8.3 League > Lineup, mobile

```
┌─────────────────────────────────┐
│ ‹ MAIN ▾   Sleeper · synced 2m  │
│ 12T · ½PPR · TE .75 · 100yd +3  │
│ [Lineup] Roster Waivers Matchup │
├─────────────────────────────────┤
│ Projected 118.4  (optimal 121.6)│
│                                 │
│ QB   Hurts       PHI 22.1  1pm  │
│ RB   Pacheco OUT KC   --  ■swap │
│ RB   Robinson    ATL 17.9  1pm  │
│ WR   Chase       CIN 18.2 4pm   │
│ WR   Nacua       LAR 16.0  🔒   │
│ TE   Kittle Q    SF  11.4 4pm ▲ │
│ W/R/T Warren*    PIT  11.2 1pm  │
│ W/T  Pitts       ATL  9.1  1pm  │
│ K    Aubrey      DAL  8.0  1pm  │
│ DEF  Steelers    PIT  7.5  1pm  │
│ ─ bench ─                       │
│ ...                             │
├─────────────────────────────────┤
│ * recommended change            │
│ [ Open lineup in Sleeper ]      │
└─────────────────────────────────┘
🔒 game started (locked)
```

### 8.4 Player page (cross-league)

```
┌─────────────────────────────────┐
│ ‹  Isiah Pacheco  RB · KC       │
│ ■ OUT (knee) · IR · as of 8:41  │
├─────────────────────────────────┤
│ In your leagues                 │
│ MAIN  starter -> replace (Warren)│
│ WORK  bench   -> ok, IR-eligible│
│ DAD   not rostered              │
├─────────────────────────────────┤
│ This week   MAIN 0.0 · WORK 0.0 │
│ Rest of season (MAIN scoring)   │
│ Why: IR, min 4 games · source:  │
│ Sleeper injury feed 8:41        │
├─────────────────────────────────┤
│ News (3) ▸   Projections ▸      │
└─────────────────────────────────┘
```

### 8.5 Add league

```
┌─────────────────────────────────┐
│ Add a league                    │
├─────────────────────────────────┤
│ Sleeper       instant, auto-sync│
│ [ username            ] [Find]  │
├─────────────────────────────────┤
│ ESPN          league URL        │
│ [ paste league URL    ] [Check] │
│ public: auto-sync (stage 2)     │
│ private: export button or manual│
├─────────────────────────────────┤
│ CBS / other   manual            │
│ Pick scoring template, paste    │
│ roster. You re-paste after      │
│ waivers.                 [Start]│
└─────────────────────────────────┘
```

### 8.6 League settings summary (after import)

```
┌─────────────────────────────────┐
│ MAIN  (Sleeper)  imported 2m ago│
│ 12 teams · FAAB $100 · Wed      │
├─────────────────────────────────┤
│ Lineup  QB 2RB 2WR TE           │
│         FLEX(R/W/T) FLEX(W/T)   │
│         K DEF · 6 BN · 2 IR     │
├─────────────────────────────────┤
│ What's different here           │
│ ● TE 0.75/catch -> TEs worth    │
│   more than public ranks        │
│ ● 100/200yd +3/+4 -> boom weeks │
│ ● INT -2                        │
│ ✎ Kicker: normal scoring        │
│   (differs from Sleeper page)   │
├─────────────────────────────────┤
│ Not modelled                    │
│ ○ 2-pt conversions (small)      │
├─────────────────────────────────┤
│ [ Looks right ]   [ Edit ]      │
└─────────────────────────────────┘
```

### 8.7 Draft (existing board in the new shell)

```
┌──────────┬───────────────────────────────────────────────────────────┐
│ Home     │ MAIN ▾  Draft · 12T · ½PPR · TE .75   Data as of 2h ago ● │
│ Leagues  │ Sleeper draft 1181… slot 7  [Sync on ●]  next pick #30    │
│ Players  ├───────────────┬───────────────────┬───────────────────────┤
│ Draft    │ Best available│ Value coming up   │ My team               │
│          ├───────────────┴───────────────────┴───────────────────────┤
│          │ # Lasts Player  Pos Market Expert Model Edge  (existing)  │
│          │ ...                                                       │
└──────────┴───────────────────────────────────────────────────────────┘
```

---

## 9. Prioritized scope

### MVP (stage 1, static; target: usable for Sunday of week 6)

P0
1. App shell with hash routing, Home / Leagues / Players / Draft, mobile tab bar.
2. Sleeper connect by username; import leagues with settings, rosters, matchups.
3. League object + Settings summary (headline chip, "what's different",
   "not modelled", overrides).
4. Home action list (game-day mode): OUT/inactive starter, empty/bye slot,
   Q starter, locked-state awareness; one-line why; Open-in-platform link;
   auto-confirm on return for Sleeper.
5. Freshness strip and per-datum as-of with fresh/aging/stale states;
   stale inputs demote recommendations to "check this".
6. League > Lineup view with recommended lineup (engine from start/sit agent).
7. Manual league (template settings + paste roster) for ESPN and CBS.
8. Draft board moved under League > Draft; `hp_board_v8` migration;
   Sleeper draft id/slot prefill.
9. Pipeline in-season output: weekly stat projections, slim players/injury file,
   denser Sunday refresh (needs the cutoff decision).
10. Export / import of all local state.

P1 (still stage 1)
11. Home modes by day (Waivers Tue, Plan Wed-Sat, Game day Sun, MNF Mon).
12. Waivers view: per-league claims with FAAB suggestions, cross-league list.
13. Players page with cross-league exposure.
14. Late-game hedge suggestions (Q player -> flex).
15. Grouped multi-league rows ("Pacheco OUT in MAIN and WORK").

### Later

- Stage 2: edge proxy -- ESPN public leagues auto-sync; shared Sunday injury
  endpoint polled every few minutes.
- Stage 3: ESPN private (bookmarklet export, then optional cookie forwarding);
  CBS spike.
- Accounts + cross-device sync; push notifications for starter status changes.
- Trade analyzer, rest-of-season rankings, playoff schedule strength.
- Dynasty/keeper/best-ball support (explicitly unsupported in MVP; say so at
  import).
- Writing lineups to platforms -- only with a separate product decision.

---

## 10. Open decisions for Camden

1. **Hosting:** publish the app on GitHub Pages (public URL, repo is already
   public) so it works on your phone, or keep it as a local file?
2. **In-season refresh:** the refresh workflow stopped at your 7 Sep cutoff and
   today's data is 18 days old. Lift it, replace it with an in-season schedule
   (daily plus every ~15 min Sunday mornings), or keep it off?
3. **Backend tolerance:** is a free, stateless edge Worker acceptable at stage 2?
   It's the only way to get ESPN auto-sync and fresh Sunday injuries.
4. **ESPN private leagues:** bookmarklet export (no secrets leave the browser,
   manual re-export), cookie forwarding (automatic, handles a login session),
   or manual only?
5. **CBS:** accept manual paste for this season?
6. **Dad's league:** which platform is it on, and should Dad use the app himself?
   A second real user is what makes accounts/sync worth building.
7. **Draft tab in-season:** swap it for Waivers on the mobile tab bar after
   week 1 (recommended), or keep Draft permanently?
8. **Read-only stance:** confirm the shippable product never changes lineups
   on a platform, and that your `set-lineups` skill stays a personal tool.
