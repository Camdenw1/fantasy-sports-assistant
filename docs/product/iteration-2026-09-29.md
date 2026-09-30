# September 29 iteration — visual redesign and imports

Branch: `codex/season-dashboard-design`, based on `product-specs`.

## User direction

Prioritize a full visual redesign: simple, sleek, easy to understand. Prefer
automatic or assisted imports for one ESPN and one CBS league. The next player
workspace should combine a general rest-of-season ranking, trade context, and
league-aware keep/drop/pickup decisions. There is also a Sleeper Pick'em league.
The ESPN/CBS team URLs and which platform hosts Dad's custom league are still
needed; an asynchronous question is pending in the chat.

## Implemented

- A shared visual language: warm neutral surfaces, green accents, system fonts,
  readable cards, desktop sidebar, compact phone navigation, automatic dark theme.
- Home puts lineup decisions first; Leagues handles connection and roster setup;
  Lineup compares current and suggested starters. Detailed data checks are folded
  on Home and remain explicit in Lineup. Unknown projections still withhold totals.
- Last successful Sleeper reports persist in this browser with original source
  timestamps. Refresh failure retains the report. A different requested week is
  flagged and cannot produce Home action cards from the older report.
- Public ESPN football roster import by URL/team ID. No credentials are accepted;
  the URL supplies IDs, and the server fetches only ESPN's fixed endpoint.
  Review then save a browser-local snapshot. Private leagues use page snapshots.
- Assisted page-table paste and preview. Labelled columns can be reordered; unknown
  injury status remains Unknown. Ambiguous rows are rejected. Bench and reserve
  slots do not generate starter alerts. This is a strict table importer, not an
  arbitrary page scraper. Exact CBS page formatting still needs the user's URL.
- Draft archive redesigned with readable rows, folded sync controls, responsive
  columns, phone overview disclosure, existing search/profile/detail/team state,
  and reset confirmation. September 7 source timestamps display their present age
  instead of the age stored when the data was generated. Preseason archive label
  prevents confusing it with current season advice.

## Verification

- JavaScript and Python syntax checks; whitespace/diff check.
- Four ESPN adapter fixture tests: foreign URL blocked before fetching, correct IDs
  and team selection, missing starter slot made explicit, bench separated, unknown
  injury not assumed healthy, missing roster rejected.
- Roster parser checks: TSV column mapping, missing injury status, strict ambiguous
  rows, malformed status, empty table, and unsafe link scheme.
- Local browser: successful live Sleeper report; Home/Leagues/Lineup navigation;
  phone layout at 390px without horizontal page overflow; draft search and player
  details; labelled CBS-format synthetic table preview/save. Only starter generated
  an injury alert, and the synthetic snapshot was removed after testing.
- ESPN actual-user import remains unverified until the league URL is supplied.
  This iteration does not validate the start/sit model's predictive accuracy.

## Next player workspace

Build a separate **Players** screen with season/draft modes, rather than renaming
preseason projections to rest-of-season rankings. In season:

1. General overall and positional ranking, position/search filters, scoring format,
   source and as-of date visible; stale/unmatched players explicit.
2. League ownership and free-agent availability from connected rosters. “Pick up”
   requires verified availability in the selected league. A snapshot alone cannot
   establish that another team's player is a free agent.
3. Keep/drop/pickup shortlist grounded in roster fit, remaining-season outlook,
   injury context, and available replacements. No automatic transactions.
4. Trade context separate from projected football points, with ranges/caveats;
   no promise that a trade partner accepts a value-based offer.

### Source review — FantasyCalc

Reviewed official [API documentation](https://fantasycalc.com/api-docs) and
[terms](https://fantasycalc.com/terms-of-usage) on September 29. The repository
already consumes a limited FantasyCalc signal in the frozen draft pipeline.
The current API supports redraft format configuration and stable Sleeper/ESPN IDs,
which are preferable to joining by display names. It provides trade-derived
values/ranks; they should not be labelled a projection consensus.

For new use: cache no more frequently than hourly (daily is recommended), retain
attribution/link adjacent to the data, validate unique player IDs and matching
coverage, and preserve the time of the successful fetch when falling back to cache.
The terms limit copying substantial portions of the service or building a material
substitute. Do not fill a new general player board by reproducing its entire value
chart. A limited roster-focused trade-context feature needs a scoped terms check;
public-facing use should follow their contact requirements. A full ranked board
needs an independently built remaining-season model or an explicitly reusable
ranking source. No fresh ranking feed was implemented or persisted in this slice.

## Handoff

Run `python3 app/server.py`; open `http://127.0.0.1:8765/`. Keep the server running.
Browser-local snapshots and reports are specific to the origin and browser; test
port 8766 has separate storage. Generated `board-data.js`, `rankings.csv`, scoring
rules, draft state key, and the refresh workflow cutoff were not changed.
`AGENTS.md` and `CLAUDE.md` remain aligned. Continue with actual league-page
validation and the independently sourced season player workspace on focused
branches. Do not publish preseason values as current trade or drop advice.
