# Product research: multi-league fantasy football manager

Research agent report, 25 Sep 2026 (NFL week 3 to 4). Scope: competitors, platform
integration reality, free data sources, gaps, and business model. Anything marked
**[unverified]** comes from a single secondary source or from vendor marketing I could
not check. Anything marked **[probed 2026-09-25]** I hit live with `curl` from this
machine that day. Headers and payloads are quoted from those probes.

---

## 0. TL;DR for the rest of the team

1. **Sleeper is the only easy platform.** It is official, needs no auth, sends `Access-Control-Allow-Origin: *`,
   and allows 1000 calls/min. It is **read-only**, and its docs say it is free for
   **non-commercial use only**: "For commercial use … reach out to us directly to discuss licensing."
2. **ESPN works, but it is unofficial.** Reads (`lm-api-reads.fantasy.espn.com`) and
   writes (`lm-api-writes…/transactions/`) both exist. Private leagues need the user's
   `espn_s2` + `SWID` cookies. ESPN added reCAPTCHA to login, so no tool can
   obtain those cookies programmatically. Disney's Terms of Use prohibit automated
   extraction and account sharing. ESPN absorbed NFL.com Fantasy for 2026, so it is
   now the biggest target by far.
3. **CBS is the worst-documented platform.** The v3 API is "deprecated but still available", and its
   developer site `developer.cbssports.com` **no longer resolves in DNS** [probed].
   `api.cbssports.com/fantasy` still answers (400 "Missing league_id") and reflects
   CORS [probed], but getting a token is undocumented today. Browser automation is
   the realistic path, and it is what Camden's own `set-lineups` skill already does.
4. **Yahoo was just locked down.** Write scope stopped being grantable to new apps in
   Oct 2025. On **22 Jul 2026** existing apps reportedly began getting 403 on *all*
   endpoints, and the docs now 308-redirect to an **application-and-review** program
   whose own page says "currently provides read access only". Yahoo's API terms also
   ban monetized use without written permission. **Do not plan Yahoo as a near-term
   integration.**
5. **Browser-only is feasible for Sleeper and ESPN public leagues only.** ESPN private
   leagues, CBS, and Yahoo all need either a server/proxy holding user secrets or a
   browser extension. Every serious competitor (FantasyPros, League Blitz, Draft Sharks) uses an extension for ESPN.
6. **Free weekly data exists, but "free" is not the same as "licensed".** Sleeper's weekly
   projections carry `company: "rotowire"`, and its stats carry `"sportradar"` [probed].
   ESPN projections are ESPN's own. Neither may be redistributed commercially. The cleanest
   reusable sources are **nflverse (CC-BY 4.0)** and **NWS weather (US public domain)**.
   The ESPN scoreboard's embedded DraftKings lines are usable for personal use but not licensed.
7. **Positioning.** The market is crowded with "sync + expert rankings + AI chat". Nobody
   does **per-league scoring-aware decisions across platforms in one "what needs my
   attention" queue** well, and nobody is honest about *why*. This repo already
   rescoring projections per league (TE premium, yardage-bonus Monte Carlo, Dad's bucket
   league) is a genuine differentiator. Lead with it.

---

## 1. Competitors and adjacent tools

### 1a. Host platforms (where leagues live)

| Platform | Price | Strengths | Common complaints | Integration posture |
|---|---|---|---|---|
| **Sleeper** | Free, no ads in the core game. Revenue comes from Sleeper Picks/real-money games, Pro subs and coins [unverified: ~$85M ARR and ~60% from real-money gaming, per Tracxn/secondary blogs] | Modern UX, chat-first, dynasty/best-ball friendly, public API | App-store reviews: pushes gambling (Picks) and neglects season-long, scores changing after games, slow loads, mascots removed ([App Store reviews](https://apps.apple.com/us/app/sleeper-fantasy-sports/id987367543?see-all=reviews&platform=iphone)) | Official read-only API; commercial use needs a licence ([docs](https://docs.sleeper.com/)) |
| **ESPN** | Free with ads | Biggest US host ("more than 24 million players" per ESPN). **NFL Fantasy shut down and migrated to ESPN for 2026** ([ESPN Press Room](https://espnpressroom.com/feature/nfl-fantasy-is-moving-to-espn-fantasy-your-questions-answered/), [Disney](https://thewaltdisneycompany.com/news/nfl-espn-fantasy-answers/)) | Dense mobile UI, weaker waiver/trade flows ([Scoutcast comparison, author is a competitor](https://scoutcast.ai/blog/best-fantasy-football-apps-2026/)) | Unofficial JSON API; cookies for private leagues |
| **CBS Sports** | Free and paid commissioner leagues | Deep custom scoring (likely where Dad's odd league lives) | Heavy ads, several moves (IL, add+IL) are web-only, weak trade screen ([App Store](https://apps.apple.com/us/app/cbs-sports-fantasy/id658308834), [AppGrooves](https://appgrooves.com/app/cbs-sports-fantasy-by-cbs-interactive-inc/negative)) | Deprecated v3 API, dead dev portal |
| **Yahoo** | Free; **Yahoo Fantasy Plus** ~$49 first-year promo / ~$123 list [unverified list price] ([Yahoo](https://sports.yahoo.com/fantasy/article/the-yahoo-fantasy-plus-benefits-program-is-here-see-whats-inside-142137328.html)) | Long-running; VOLS roster-aware suggestions inside Plus | n/a (not researched deeply) | API now gated and read-only (see §2) |
| **Fleaflicker** | Free | Fast app, multi-sport | Small user base | Official read-only public API ([docs](https://www.fleaflicker.com/api-docs/index.html)) |
| **Fantrax** | Free and paid tiers | Deep customization, dynasty | Clunky UI [unverified] | No official public API; community wrappers use cookies for private leagues ([FantraxAPI](https://github.com/meisnate12/FantraxAPI)) |
| **MyFantasyLeague (MFL)** | Paid per league | Most customizable; the high-stakes/dynasty standard | Dated UI | Documented read/write API with auth ([api_info](https://api.myfantasyleague.com/2020/api_info)) |
| **Underdog** | Free-to-enter, real-money best ball | Best ball / pick'em | Not season-long management | No public API; relevant only for exposure tracking |

### 1b. Advice, sync and multi-league tools

| Tool | Price (2026) | Platforms synced | Standout | Weakness / caveat |
|---|---|---|---|---|
| **FantasyPros My Playbook** | PRO $3.99, MVP $5.99, HOF $8.99/mo billed annually (list $11.99, $16.99, $22.99 monthly). Syncs 2 / 10 / 50 leagues per sport ([plans](https://www.fantasypros.com/premium/plans/bp/); that URL is a promo variant) | Sleeper, ESPN, CBS, Yahoo, MFL, NFL.com, RT Sports, Fleaflicker, FFPC, Fantrax, NFFC and more ([sync](https://www.fantasypros.com/myleagues/league-sync/)) | **Auto-Pilot** sets lineups automatically on Yahoo, ESPN, CBS, MFL and Sleeper (MVP+). It checks at least twice a day and in the hour before kickoff. Yahoo blocks it in paid Prize leagues ([Auto-Pilot](https://www.fantasypros.com/nfl/myplaybook/auto-pilot.php), [support](https://support.fantasypros.com/hc/en-us/articles/115001832073)). Also "Coach AI" chat ([FP AI tools](https://www.fantasypros.com/2026/07/best-fantasy-football-ai-tools/)) | Advice is ECR-driven, so it is **not scoring-aware** beyond simple settings. ESPN web sync has **required a Chrome extension since July 2020**, which stores an encrypted ESPN cookie server-side and asks users to allow third-party cookies ([support](https://support.fantasypros.com/hc/en-us/articles/360051313453)). There is a whole help section for "rosters no longer updating" ([support](https://support.fantasypros.com/hc/en-us/articles/115001364468)). How they write to Sleeper is not public (a private partnership or private API) [unverified] |
| **Fantasy Life+** (Matthew Berry; now also carries the Rotoworld draft guide) | $39.99/yr (Tier 1) or $99.99/yr (Tier 2) ([pricing](https://www.fantasylife.com/pricing)) | League sync is mentioned, platforms not listed | Utilization Score, projections, waiver and trade tools, best-ball exposure tool | Content-first; sync depth unclear |
| **NBC Sports Edge / Rotoworld** | Free news; premium is now bundled via Fantasy Life+ ([NBC](https://www.nbcsports.com/fantasylife)) | — | The fastest beat-writer news blurbs | Not roster-aware |
| **4for4** | Classic $29/season, Pro $59/season (LeagueSync) ([plans](https://www.4for4.com/plans), [review](https://www.fantasyaccountant.com/review/8/4for4-review)) | ESPN, Yahoo, CBS, RTSports, MFL, FFPC ([LeagueSync](https://www.4for4.com/leaguesync)) | Historically among the most accurate projections; scoring-customizable | No Sleeper listed on the LeagueSync page [unverified]; web-first |
| **PFF+** | ~$79.99/yr early bird ([PFF](https://www.pff.com/news/fantasy-football-draft-tools-pff-plus)) | Sleeper, Yahoo, ESPN, unlimited leagues ([support](https://profootballfocussupport.zendesk.com/hc/en-us/articles/32404432940563)) | Player grades and in-season start/sit | Grades don't map cleanly to fantasy points |
| **Draft Sharks** | Tiered subscription with a refund guarantee to 31 Dec ([subscribe](https://www.draftsharks.com/subscribe)) | Yahoo, ESPN, CBS, Sleeper, MFL, RT, Underdog, Fleaflicker, Fantrax ([kb](https://www.draftsharks.com/kb/fantasy-football-league-sync)) | **Free Agent Finder checks every synced league**, the closest thing to cross-league availability | Pricing opaque |
| **RotoWire** | ~$8.91/mo annual, $17.99 monthly ([pricing](https://www.rotowire.com/subscribe/pricing/)) | Yahoo, ESPN in its app | Lineup optimizer; **RotoWire also supplies Sleeper's projections** (see §3) | Narrow sync |
| **PlayerProfiler** | Premium tier (price not found) | — | Advanced metrics and player pages | Research tool, not a manager |
| **FantasyCalc** | Free | Sleeper, ESPN, MFL, Fleaflicker, FFPC ([analyzer](https://fantasycalc.com/league/analyzer)) | Trade values from millions of real trades; already used in this repo as the sentiment lane | Dynasty/trade-focused |
| **KeepTradeCut** | Free (ads) | Sleeper, MFL, FFPC, Fleaflicker, Fantrax ([KTC](https://keeptradecut.com/trade-calculator)) | Crowdsourced dynasty values | Dynasty only |
| **Dynasty Nerds / Dynasty Daddy** | Nerds is paid; Daddy is free | Sleeper-centric | **Dynasty Daddy has cross-league player exposure** ([site](https://dynasty-daddy.com/)); Nerds has a lineup optimizer ([Nerds](https://www.dynastynerds.com/dynasty-tools/lineup-optimizer/)) | Dynasty niche |
| **Footballguys** | Subscription | Multi-platform sync | Player pages show which of your synced teams roster him ([forum](https://forums.footballguys.com/threads/app-that-tracks-shares-of-players.820846/)) | Old-school UI |

### 1c. New small entrants and AI assistants (2025-26)

These are the closest analogues to what we're building. Most are free and read-only.

- **AllMyLeagues**: "all your fantasy leagues, one screen". Sleeper, Yahoo, ESPN, CBS,
  Fleaflicker and Fantrax per its search snippet; free ([site](https://allmyleagues.com/)). Auth
  methods are not documented [unverified].
- **League Blitz**: free dashboard for Yahoo (OAuth), Sleeper (username) and ESPN (public
  leagues directly, private leagues **via a browser extension**). It offers GPT matchup analysis,
  power rankings and a Game Day view, with no write actions ([site](https://leagueblitz.app/)). Its
  Yahoo integration is presumably now affected by the July 2026 lockdown [unverified].
- **Fantasy Football Analyzer**: free, open source, no account needed; Sleeper, ESPN, Yahoo ([site](https://fantasyfootballanalyzer.app/)).
- **RotoBot AI**: sync Sleeper/ESPN/Yahoo; chat assistant; also parlays and props, so it leans into betting ([site](https://rotobot.ai/fantasy-football/league-sync)).
- **Scoutcast.ai**: a ~2-minute personalized daily **audio** brief; free + $39.99/season ([blog](https://scoutcast.ai/blog/best-fantasy-football-apps-2026/)).
- **NFL Fantasy Edge**, **Sportsmind**, **DraftEdge**, **gamedai**: AI chat and start/sit
  tools with freemium question caps ([NFL Fantasy Edge](https://nflfantasyedge.com/), [Sportsmind](https://sportsmindai.com/)).
- Open-source hobby tools are proliferating: ESPN CLI + agent skill that does lineup swaps
  ([ryanjadhav/espn-fantasy](https://github.com/ryanjadhav/espn-fantasy)), Sleeper MCP servers
  ([vbudhram/sleeper-mcp](https://github.com/vbudhram/sleeper-mcp)), ESPN lineup-setting PRs
  ([example](https://github.com/gfarrenkopf/fantasy-football-war-room/pull/56)).

**Read:** "sync + AI chat" is table stakes and increasingly free. None of these tools
advertises league-scoring-aware projections that model bonuses and step-function scoring.
Most rescale an expert rank list.

---

## 2. Platform integration reality

### 2a. Summary matrix

| | Sleeper | ESPN | CBS | Yahoo |
|---|---|---|---|---|
| Official? | **Yes** ([docs.sleeper.com](https://docs.sleeper.com/)) | No, an internal API that is widely reverse-engineered | Was (v3), now "deprecated but still available" | Yes, but gated since Jul 2026 |
| Auth for reads | None; users are identified by username → `user_id` | Public leagues: none. Private: `espn_s2` + `SWID` cookies copied from the browser ([espn-api wiki](https://github.com/cwendt94/espn-api/wiki), [ffscrapr guide](https://ffscrapr.ffverse.com/articles/espn_authentication.html)) | `access_token` query param; token acquisition undocumented today | OAuth 2.0 **plus an approved app** ([sports.yahoo.com/developer](https://sports.yahoo.com/developer)) |
| Rosters, settings, scoring, matchups, transactions | Yes: league, rosters (with `starters`), users, matchups/week, transactions/week, traded picks, brackets, drafts and picks, players dump (~5MB), trending | Yes via `view=` params (`mSettings`, `mRoster`, `mMatchup`, `mTeam`, `kona_player_info`, transactions) | Yes (rosters, transactions, scoring rules) per the old docs and [ffcbs](https://rdrr.io/github/dfs-with-r/ffcbs/man/ffcbs_api.html) [unverified for 2026] | Yes in principle, for approved apps |
| Weekly projections | Unofficial `api.sleeper.com/projections/nfl/<season>/<week>` (RotoWire-sourced) [probed] | Yes, per `scoringPeriodId` in `kona_player_info` (statSourceId 1) [probed] | Unknown via API; shown on lineup page | Yes for approved apps |
| **Write (set lineup)** | **No.** "you cannot modify contents via this API" | **Yes, unofficially:** `POST lm-api-writes.fantasy.espn.com/.../transactions/` with type `ROSTER` + `LINEUP` items. Also `FREEAGENT` and `WAIVER` types ([ryanjadhav/espn-fantasy](https://github.com/ryanjadhav/espn-fantasy)) | Historically `PUT` existed [unverified]; practical path is browser automation | Roster `PUT` (XML, `coverage_type=week`) existed ([docs](https://yahoo-fantasy-node-docs.vercel.app/resource/roster)), but write scope has been ungrantable for new apps since Oct 2025 ([yfpy#79](https://github.com/uberfastman/yfpy/issues/79)) |
| Rate limit | "stay under 1000 API calls per minute" or risk an IP block | Undocumented; community advice is "don't hammer it". Responses expose a `Polling-Interval` header [probed] | Undocumented | "may temporarily throttle" (no numbers) |
| CORS (browser-only app) | `Access-Control-Allow-Origin: *` [probed] | Reflects the caller's Origin with `allow-credentials: true` [probed]. Public leagues work from the browser. **Private leagues do not** in practice: JS cannot set a `Cookie` header, and a credentialed cross-site fetch only carries `.espn.com` cookies if the user's browser permits third-party cookies (Safari doesn't) | Reflects Origin, allows all headers [probed], so a token in the query string would work from the browser | **No CORS headers** on `fantasysports.yahooapis.com` [probed]. OAuth code exchange needs a server anyway |
| ToS for a shipped product | **Non-commercial only; commercial use requires a licence.** User ToS grants a "personal and non-commercial" licence and recognizes "Approved Integration Partner" connections ([ToS](https://support.sleeper.com/en/articles/5486620-general-terms-of-use)) | Disney ToU prohibits extracting content "using a robot, spider, script, or other automated means", and says "you will not share your account or account information with others" ([Disney ToU](https://disneytermsofuse.com/english/)). A third-party app holding users' ESPN cookies is squarely grey-to-prohibited | CBS terms govern the API; no current developer programme | Yahoo API terms bar deriving income, ads, subscriptions or SaaS without written permission; attribution "Fantasy data provided by Yahoo Fantasy" required ([YDN terms](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html)) |

### 2b. Sleeper, in detail

- Endpoints ([docs](https://docs.sleeper.com/)): `/user/<name|id>`, `/user/<id>/leagues/nfl/<season>`,
  `/league/<id>`, `/league/<id>/rosters`, `/league/<id>/users`, `/league/<id>/matchups/<week>`,
  `/league/<id>/transactions/<round>`, `/league/<id>/traded_picks`, `/league/<id>/winners_bracket`,
  `/draft/<id>/picks`, `/players/nfl`, `/players/nfl/trending/{add|drop}`, `/state/nfl`.
- `/state/nfl` returned `{"week":3,"season":"2026","display_week":3,...}` [probed]. Use it as the week clock.
- `/players/nfl` is CDN-cached (`s-maxage=600`, ETag) [probed]. Docs ask you to fetch it
  **at most once per day** and store it. Never ship it to every client on page load; slim it server-side or at build time.
- **Undocumented but widely used**: `api.sleeper.com/projections/nfl/<season>/<week>` and
  `api.sleeper.com/stats/nfl/<season>/<week>` ([sleeper-api-client docs](https://sleeper-api-client.readthedocs.io/en/latest/endpoints/projections.html),
  [joeyagreco discussion](https://github.com/joeyagreco/sleeper/discussions/11)). Probed rows
  are tagged `company: "rotowire"` (projections) and `"sportradar"` (stats). There is also an
  auth-only GraphQL at `sleeper.app/graphql` that the app itself uses. Writing through it
  would need the user's Sleeper session token, which is a ToS problem and fragile.
- **No lineup writes.** Our "set lineup" story for Sleeper is a **deep link** to
  `sleeper.com/leagues/<id>/team` plus a clear diff of what to change, or browser automation for Camden personally.

### 2c. ESPN, in detail

- Read host moved to `lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/<yr>/segments/0/leagues/<id>?view=...`
  (the old `fantasy.espn.com/apis/v3` path is legacy). There is a player universe with weekly projections at
  `.../leaguedefaults/3?view=kona_player_info` with an `X-Fantasy-Filter` header. It **needs no auth** and
  returned weekly projected totals per `scoringPeriodId` [probed].
- Private-league auth: `espn_s2` (~250+ chars) + `SWID` (`{GUID}`). "These credentials cannot be
  retrieved programmatically", because ESPN added reCAPTCHA to login ([espn-api discussion #150](https://github.com/cwendt94/espn-api/discussions/150)).
  Cookies expire on an undocumented schedule, and tools surface `EXPIRED` and ask users to re-paste
  ([espn-fantasy](https://github.com/ryanjadhav/espn-fantasy)). The UX options are: paste cookies (hostile
  to normal users), a **browser extension** that reads the cookies (what FantasyPros and League Blitz do; there is
  also a third-party "ESPN Cookie Finder" extension), or on-device automation.
- Writes: a single `ROSTER` transaction containing both sides of each swap avoids slot-conflict
  409s. Validate slot eligibility, locked players, IR and bench limits before sending.
- Libraries: Python [cwendt94/espn-api](https://github.com/cwendt94/espn-api) (~1k stars, read-only),
  JS [mkreiser/ESPN-Fantasy-Football-API](https://github.com/mkreiser/ESPN-Fantasy-Football-API), R
  [ffscrapr](https://ffscrapr.ffverse.com/). Community endpoint lists: [pseudo-r/Public-ESPN-API](https://github.com/pseudo-r/Public-ESPN-API).
- Risk: undocumented, can change without notice, and the ToS prohibits automation. With NFL.com users migrated in,
  ESPN's user base (and incentive to lock down) just grew.

### 2d. CBS, in detail

- The documented base is `api.cbssports.com/fantasy/<resource>?version=3.0&response_format=json&access_token=…`.
  It is still live: it returned `400 Missing league_id` with permissive CORS [probed].
- `developer.cbssports.com` **does not resolve** (DNS ENOTFOUND, 25 Sep 2026). Community notes
  describe the API as deprecated, with restricted token issuance
  ([cbs token fetcher gem](https://github.com/geoffharcourt/cbs_fantasy_sports_api_token_fetcher)).
- The league-subdomain API (`<league>.football.cbssports.com/api/league/...`) **does not honour
  `access_token`** and redirects anonymous calls to sign-in. It needs a session cookie
  ([iron-tuna PR #252](https://github.com/krubins/iron-tuna/pull/252), a 2026 project hitting the same wall).
- Practical path for Camden: logged-in browser automation (already written up in the `set-lineups`
  skill's CBS reference, which is itself marked "unconfirmed until the first live run"). For a product, CBS
  is **extension-or-nothing** until someone proves a token flow in 2026.

### 2e. Yahoo, in detail (likely future add, but blocked)

- OAuth 2.0 authorization code. The token exchange needs a client secret, so a server is required, and there is no CORS [probed].
- **Oct 2025**: the write permission disappeared from the app-creation form. Legacy keys kept write ([yfpy#79](https://github.com/uberfastman/yfpy/issues/79)).
- **22 Jul 2026**: all endpoints began returning `403 "This application is not authorized to perform this action"` for
  existing apps ([yfpy#84](https://github.com/uberfastman/yfpy/issues/84), a single reporter, no replies, so its breadth is **[unverified]**).
  It is corroborated by (a) `developer.yahoo.com/fantasysports/guide/` now 308-redirecting to
  `sports.yahoo.com/developer` [probed], and (b) that portal's access page stating "The Yahoo Fantasy
  Sports API currently provides read access only. Write access is not available at this time", with
  every application "reviewed by the Yahoo Fantasy Sports team" ([access](https://sports.yahoo.com/developer/access/)).
  Another project independently reports that Yahoo "no longer self-serve provisions" the API
  ([fantasy-football-mcp-public#18](https://github.com/derekrbreese/fantasy-football-mcp-public/issues/18)).
- The ToS bars monetization (ads, subscriptions, SaaS) without written permission.
- **Recommendation:** apply now for personal/single-user read access (it's free and slow). Don't put
  Yahoo on the product roadmap until approval terms are known.

### 2f. Architecture implications

- **A static browser-only site can do**: Sleeper (everything readable), ESPN public leagues,
  ESPN's public player/projection universe, the ESPN scoreboard, and NWS weather (all CORS-open [probed]).
- **Anything else needs one of**:
  1. **A thin server/edge proxy** (e.g., a Cloudflare Worker) holding per-user ESPN cookies or a CBS token.
     You then become a custodian of session credentials that grant full account access. That is a security
     and ToS liability, and it needs encryption at rest and a clear "revoke" story.
  2. **A browser extension** that reads cookies and makes calls from the user's own session.
     This is the industry-standard answer for ESPN. It keeps credentials on-device, but adds store review, and
     Safari/iOS is hard.
  3. **Local/agent automation** (the current `set-lineups` skill model). Fine for Camden, not a product.
- **Writes**: only ESPN (unofficial) is feasible programmatically. Sleeper gets deep links, and CBS and Yahoo
  get deep links plus a checklist. Design the start/sit output as a **diff** ("move X → FLEX, bench Y") that
  can either be executed (ESPN) or followed by hand (everyone else).
- **Commercial line**: shipping a paid product on Sleeper data needs a Sleeper licence, and on ESPN
  data it conflicts with Disney's ToU. A free, personal, or open-source tool is the defensible posture until
  licences exist. This matters for §5.

---

## 3. Free data sources: what's usable, what's merely reachable

| Need | Source | Access | Licence / reuse notes |
|---|---|---|---|
| **Weekly projections** | Sleeper `api.sleeper.com/projections/nfl/<yr>/<wk>` | Unofficial, no auth, CORS `*` [probed]. 1,364 WR rows for week 4, including `pts_half_ppr`, raw stat lines and yardage-bucket fields like `rec_0_4`, `bonus_rec_wr` | Rows say **`company: "rotowire"`**. It is licensed data re-served by Sleeper. Reachable, not reusable commercially |
| | ESPN `kona_player_info` weekly `appliedTotal` + stat lines | Unofficial, no auth [probed] | ESPN proprietary; Disney ToU |
| | nflverse `load_ff_opportunity` (expected points from usage, retrospective) | GitHub releases | CC-BY 4.0; good for **model features**, not a forward projection |
| | **Own model** from nflverse usage + Vegas implied totals | — | Cleanest long-term answer. The repo already rescores raw stat lines, so it can consume a raw weekly line from any source for personal use |
| **Injuries / practice status** | Sleeper players dump `injury_status`, `injury_body_part` (already used) | Official API | Non-commercial |
| | ESPN `sports.core.api.espn.com/v2/.../teams/<id>/injuries` | Unofficial ([endpoint lists](https://gist.github.com/nntrn/ee26cb2a0716de0947a0a4e9a157bc1c)) | ESPN ToU |
| | nflverse `load_injuries` (official NFL reports, practice participation) | Releases, updated in season | CC-BY 4.0 |
| **Depth charts** | nflverse `load_depth_charts` (by date since 2025, now **sourced from ESPN** after NFL Data Exchange went away) ([nflreadr news](https://nflreadr.nflverse.com/news/index.html)) | Releases | CC-BY 4.0 per nflverse, but the upstream is ESPN; the licence is only as good as the upstream |
| | ESPN core `.../seasons/<yr>/teams/<id>/depthcharts` | Unofficial | ESPN ToU |
| **Vegas lines / implied totals** | ESPN scoreboard `site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard` embeds **DraftKings** spread and O/U. Week 4 example: "PIT -3", O/U 38.5, plus `indoor` and AccuWeather weather [probed]. CORS `*` | Unofficial | Fine for personal use; not licensed. Implied team total = O/U/2 ± spread/2 |
| | The Odds API | Free tier is 500 credits/mo (credits ≠ requests: 3 markets × 2 regions = 6 credits/call). NFL spreads/totals realistically need $29/mo ([analysis](https://oddspapi.io/blog/the-odds-api-free-tier-limits/), [site](https://the-odds-api.com/)) | Paid for real use; violates the project's no-paid rule |
| **Weather** | **NWS `api.weather.gov`** | Free, no key (User-Agent required), CORS `*` [probed] | **US government work: public domain.** Best choice. US stadiums only, and it has no dome flag (take `indoor` from the ESPN scoreboard or a static stadium table) |
| | Open-Meteo | Free ≤10k calls/day | **Non-commercial only**; commercial needs $29/mo+ ([terms](https://open-meteo.com/en/terms), [pricing](https://open-meteo.com/en/pricing)) |
| **Snap counts** | nflverse `load_snap_counts` (from Pro Football Reference, 2012+) ([ref](https://nflreadr.nflverse.com/reference/load_snap_counts.html)) | Releases | nflverse publishes under CC-BY 4.0; PFR's own terms restrict scraping, so there is residual upstream risk |
| **Targets, air yards, routes proxy** | nflverse play-by-play / `load_player_stats` / Next Gen Stats loaders ([nflreadpy](https://github.com/nflverse/nflreadpy)) | Releases, nightly in season | CC-BY 4.0. **FTN charting/participation is CC-BY-SA 4.0** (share-alike: be careful mixing it into a closed product) |
| **Player ID crosswalk** | nflverse `load_ff_playerids` (DynastyProcess: Sleeper, ESPN, Yahoo, MFL, CBS, Fleaflicker IDs) | Releases | Open. **Essential for multi-platform joins** |
| **Trending adds/drops** | Sleeper `/players/nfl/trending/add` (e.g. 333k adds/24h for the top player) [probed] | Official | Non-commercial. A great "what's hot" signal |
| **News** | Rotoworld/NBC, RotoWire: none free to reuse | — | Link out; don't republish |

**Project-rule reading:** for Camden's personal tool, the current pattern (ESPN + Sleeper feeds
blended with a hand baseline) is fine. For anything shipped, only **nflverse (with attribution,
minding CC-BY-SA pieces)** and **NWS** are clearly reusable. Every weekly projection feed is
someone's licensed product. A shippable product either builds its own weekly projection from
nflverse usage + market lines, or licenses one.

---

## 4. Gaps and opportunities

What multi-league players want, and why it's under-served:

1. **A cross-league "needs attention" queue** (the headline gap). Existing tools are
   league-first: pick a league, then see its advice. Multi-league players want one list sorted by
   urgency: *"3 starters Out/Doubtful across 2 leagues, 1 player on bye still starting, a
   waiver run closes in 4h in the ESPN league, a trade offer pending in Sleeper, a Thursday
   game locks in 6h."* FantasyPros' Auto-Pilot comes closest, but it acts silently on ECR and
   isn't a to-do list. Draft Sharks' Free Agent Finder and Footballguys' "rostered in which of
   my leagues" do small cross-league slices.
2. **Scoring-aware start/sit per league.** Nearly all advice is a single expert rank list
   lightly adjusted for PPR/half/standard. Leagues with TE premium, yardage bonuses, per-25-yard
   buckets, distance-based TDs or odd kicker rules (both of Camden's leagues) get wrong answers,
   and nobody explains *why* a player ranks differently in league A vs B. This repo already
   rescores raw stat lines per league and Monte-Carlos the step functions, a capability
   competitors don't advertise. **The same player can be a start in one league and a sit in another
   within one screen.** That's the demo.
3. **Exposure / portfolio view for redraft.** Exposure tools exist for best ball and dynasty
   (Dynasty Daddy, Fantasy Sanctuary, Fantasy Life). For redraft it's mostly missing: "how much of
   my week rides on the Ravens offense", "I face Player X in three matchups", "I'm starting
   both sides of a game".
4. **Honest confidence.** Tools output a single ranking. Our pipeline has distributions
   (Monte Carlo), so we can show "coin flip" vs "clear start" and say when a decision doesn't matter.
   This also reduces decision fatigue for multi-league players.
5. **Sync reliability and transparency.** FantasyPros has a support section devoted to broken
   sync, and ESPN cookie expiry silently breaks tools. A visible per-league "last synced / auth
   expires / fix it" status is cheap and trusted.
6. **Pre-lock timing.** Thursday/Saturday/international games, late-inactives 90 minutes before kickoff,
   and "your flex should hold the later-kickoff player" (flex-late strategy) are timing problems that
   a cross-league queue with kickoff clocks handles naturally.
7. **Commissioner-agnostic league rules import.** Scoring rules exist in Sleeper (`scoring_settings`)
   and ESPN (`mSettings`). CBS and odd leagues need a manual rules editor, and Dad's league proves one is needed.

Not worth chasing: AI chat as the core product (commoditized, often free), dynasty trade values
(FantasyCalc/KTC own it and are free), and betting tie-ins (off-mission, and they are what users complain about in Sleeper).

---

## 5. Business models and positioning

### Models in the space
- **Tiered subscriptions gated by league count**: FantasyPros (2/10/50 leagues), and
  Auto-Pilot on higher tiers. League count is the de facto pricing axis for multi-league tools.
- **Seasonal passes**: 4for4 ($29/$59 per season), Scoutcast ($39.99/season), Fantasy Life+ ($40/$100 per year).
- **Host upsells**: Yahoo Fantasy Plus, Sleeper Pro/coins. The **real money is in gambling**
  (Sleeper Picks is reportedly the majority of Sleeper revenue [unverified]; RotoBot bundles parlays).
- **Media/ads + affiliate sportsbook**: Rotoworld/NBC, most free AI tools.
- **Free as a funnel**: FantasyCalc, KTC, League Blitz, and Fantasy Football Analyzer are free and ad- or reputation-supported.

### Constraints specific to us
- Platform ToS make a **paid** product on Sleeper/ESPN/Yahoo data legally exposed without licences.
  (FantasyPros presumably has partner agreements. Yahoo's ToS explicitly carve out paid products.)
- The project rule forbids paid data. A paid product built on unlicensed free feeds would be the worst combination.

### Recommended positioning
**"The scoring-aware command center for people in several leagues on different sites."**
- Core promise: *one queue of what needs your attention before each lock, with every start/sit
  computed under that league's actual scoring*, plus a plain-language reason when leagues disagree.
- Platforms in order: **Sleeper** (official, easy) → **ESPN** (biggest after the NFL.com migration; read via
  public or extension, write via unofficial transactions as an opt-in) → **CBS** (manual rules import +
  browser-assisted) → Yahoo only if an approval comes through.
- Business stance for now: **free / open-source / personal-use**, with no ads, no betting, and credentials kept
  on-device (extension or local). That keeps us inside Sleeper's non-commercial grant and minimizes
  ESPN exposure, and it is itself a differentiator against tools that store your ESPN cookie on their servers.
  If it ever goes paid: seek a Sleeper commercial licence first, and swap licensed-by-someone-else
  projection feeds for an own-model projection built on CC-BY nflverse + NWS + market lines.
- Wedge feature to build first: the cross-league **attention queue** fed by Sleeper + ESPN, and the
  **per-league scoring diff** ("Kittle: start in Sleeper (TE 0.75 PPR), sit in Dad's league (5-catch
  TE tier unlikely)"). Both reuse the existing pipeline's rescoring.

---

## Appendix: raw probes (25 Sep 2026)

```
GET api.sleeper.app/v1/state/nfl            200  ACAO: *            week 3, season 2026
GET lm-api-reads.fantasy.espn.com/...        404  ACAO: <echo origin>, allow-credentials: true, exposes Polling-Interval
GET lm-api-reads.../leaguedefaults/3?view=kona_player_info  200 (no auth) weekly projections per scoringPeriodId
GET api.cbssports.com/fantasy/league/details 400 "Missing league_id"  ACAO: <echo>, allow-headers: *
GET developer.cbssports.com                  DNS ENOTFOUND
GET fantasysports.yahooapis.com/fantasy/v2/game/nfl  401 OAuth, no CORS headers
GET developer.yahoo.com/fantasysports/guide/ 308 -> sports.yahoo.com/developer
GET site.api.espn.com/.../nfl/scoreboard     200  ACAO: *  odds provider "Draft Kings", overUnder, venue.indoor, weather
GET api.sleeper.com/projections/nfl/2026/4   200  ACAO: *  company "rotowire"
GET api.sleeper.com/stats/nfl/2026/3         200  company "sportradar"
GET api.weather.gov/points/...               200  ACAO: *
```
