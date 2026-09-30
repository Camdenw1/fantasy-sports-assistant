# Crimson and current season — September 30, 2026

Branch: `codex/current-season-crimson`.

- Changed the accent to NFL Shield Red (#D50A0A), keeping a white/charcoal canvas.
  Selected navigation, position tabs, and context marks carry the motif subtly.
- Players now opens `app/players.html`: current ROS **projection rankings**,
  sourced directly from Sleeper's weekly projection endpoint (RotoWire provider).
  Live verified coverage is Weeks 5–17, with source revisions September 28.
- Flex ranks RB/WR/TE by remaining projected standard half-PPR points; QB ranks
  separately. Search retains the player's rank in the selected position pool.
- Current week excluded; ends Week 17. No custom league scoring, expert blend,
  trade valuation, pickup/drop decision engine, or claimed model validation yet.
- Frozen draft data and refresh cutoff untouched. Archive remains linked below.
- Background single-flight refresh, one-hour cache, persisted atomic last-good
  snapshot, browser snapshot, offline shell. Polling reads never restart failures.
- Minimum 150 actual projected skill players per remaining week. Placeholder ADP
  rows rejected; duplicate provider revisions count once/player/week. Missing
  weeks abort publication, retaining the last complete snapshot.
- Provider revision and local read dates distinguished; missing player weeks are
  not extrapolated. Injury text comes from projection payload; not a live alert.

Verification: 15 Python checks; roster-parser checks; JavaScript syntax; real
remaining-week projection read; search/position interactions; desktop and phone.

Next: support custom scoring and position-aware trade value with explicit model
assumptions and validation. Current point sorting must not become trade value
simply by renaming a column.
