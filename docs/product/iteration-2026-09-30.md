# Reliability and red scorecard iteration

Branch: `codex/reliable-red-workspace`, based on the preceding visual redesign.

## User direction

Robust and consistently available is the highest priority. Apply the supplied
personal design reference, try an earthy red identity, use team marks beside
players, remove unneeded interface material, and make the player board sleek.

## Reliability changes

- Background refresh API returns immediately with any dated last-good report.
  A thread pool caps active calculations at two; matching requests share a job.
  Successful reports persist atomically to gitignored server storage. Failed or
  incomplete updates retain the last report. Fresh reports have a 60-second TTL.
- Frontend skips a separate discovery trip at startup. Saved content renders
  immediately while a job updates. Requests have a 25-second connection timeout;
  polling is bounded, and the engine subprocess has a 75-second cap.
- Stable SHA-256 feed cache keys replace Python's process-randomized `hash()`.
  State/league lookups cache for 60 seconds, user IDs for five minutes. JSON
  validates before atomic write; corrupt cache files rebuild. Player dump remains
  limited to one successful download per day, with atomic writes.
- macOS LaunchAgent starts the localhost service at login and restarts it after
  process exit. Installed at `~/Library/LaunchAgents/com.camden.fantasy-sports-assistant.plist`.
  The tracked helper supports status, install, and uninstall. It uses this
  repository and Python interpreter; reinstall if either moves.
- A service worker saves static screens, the frozen board, and 32 team marks.
  API responses never enter that cache. Failed network reads use the original
  saved roster data. First use and cleared browser storage still require service.
- Recommendation model version is carried through server/browser cache. An older
  model can retain roster visibility but cannot emit advice until refreshed.

## Recommendation correctness

A live Week 4 check exposed a speculative late-swap hedge that credited Ollie
Gordon with points from Jahmyr Gibbs as a fallback even though Gibbs was already
starting. It selected Gordon over a higher-valued healthy player. Removed that
credit: starter selection now maximizes injury-adjusted expected points subject
to eligibility and one use per player. Flexible reseating remains intact.
Regression checks cover this roster and legal, unique player assignment. This is
a correction to the start/sit experiment, not to the frozen draft models.
Missing roster projections now withhold the suggested lineup column as well as
totals; the current roster stays readable.

## Visual changes

White surfaces, charcoal text, restrained weathered red, sturdy serif page
headings, readable system sans-serif controls, and locally bundled official NFL
team marks. See `design-brief.md` for the supplied personal reference.

Removed the slogan, decorative nav glyphs, repeated lock explanations, duplicated
completed-lineup players, and decorative odds badges from player rows. Model and
expert numbers remain in details. Draft overview/settings and explanations are
folded by default. Draft state and profile switching are preserved. The player
board still contains the September 7 draft snapshot; genuine current-season
rankings/trade values remain a separate data milestone, not a relabelled archive.

Team mark provenance is recorded in `app/assets/teams/README.md`. These are visual
identifiers, not claimed endorsements. Public launch needs an asset-use review.

## Verification

- Eleven Python checks: ESPN adapter, instant job response, request deduplication,
  failed refresh retention, corrupted cache rebuild, restart persistence, model
  version invalidation, and lineup-selection regression.
- Roster parser and JavaScript/Python syntax checks; clean whitespace check.
- Refresh endpoint measured at 22.9ms with a saved report available while a new
  job ran (one local measurement, not a performance guarantee).
- Installed service restarted after a forced process exit; new PID served HTTP.
- Stopped the test server, reloaded the browser, opened Lineup: saved Week 4
  report and team logos remained available with an explicit failed-refresh state.
- Browser checks for desktop and phone layout, player search/details, column
  alignment, image rendering, and cache freshness labels.

## Remaining limits

ESPN actual league and CBS page URLs are still pending. The imports and personal
snapshots are not authenticated synchronization. Pick'em picks are not connected.
A new computer/browser needs a first successful local load. Source outages still
prevent fresh advice, and the models remain unbacktested. Never hide those limits
behind a “live” label or make frozen draft rankings appear current.
