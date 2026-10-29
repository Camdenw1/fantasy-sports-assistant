# Personal fantasy manager — free-first roadmap

Camden, 29 October 2026: build toward a FantasyPros-level helper for quick
management of all leagues. Keep data sources free for now. This is the product
target, not a claim that the current recommendations match a paid service.

## Shipped this iteration

- Home: compact review queue across leagues, prioritized by lineup problems and
  data readiness. Selected-team detail remains focused.
- Lineup: stale roster/injury reads pause advice; undated/old manual snapshots no
  longer show a reassuring green status.
- Scores: same-week fallback with original successful read time, manual retry,
  request deduplication and one-minute failure backoff. Older in-flight responses
  cannot replace a newer week's board. Player-name failures cannot create a
  render/request loop. Hidden tabs skip polling work.
- Request deadlines now include response-body reads.

Validation: 54 Python tests and four JavaScript suites, including live-score
outage/recovery, week isolation, concurrent loads and unknown player IDs.

## 1. Make all leagues equally easy to maintain

Sleeper has complete ownership. Public ESPN has live reports; private ESPN and
CBS are still snapshots. Improve assisted imports and identity matching, retain
source dates and roster completeness, and make updating an existing roster one
clear action. Do not ask for passwords or claim snapshots are authenticated sync.
Done when each connected team has complete starters/bench, an honest connection
status, and a repeatable update path requiring minimal manual reformatting.

## 2. Comparable, explainable weekly decisions

Use the league's verified scoring, lineup eligibility, ownership, injury status
and kickoff locks. Rank moves by expected starting-lineup benefit and explain
who to start, who to bench, what to add/drop and why. ESPN waiver parity and CBS
scoring/ownership remain gaps. A single-team snapshot cannot establish waiver
availability across the league. Keep news/status source dates visible.
Done when a manager can review each league's highest-priority decisions in one
pass, with incomplete data withholding affected advice.

## 3. Measure advice before adding stronger claims

Store dated prediction snapshots locally and compare finished-week outcomes:
coverage, error, recommended versus current lineup performance, and whether
waiver suggestions actually improved legal starting lineups. Evaluate trade
suggestions on both teams' gains and realistic roster constraints. No claimed
expert consensus or calibrated confidence without validation.
Done when recommendation quality and failure rates have inspectable evidence.

## Boundaries

No paid feeds, paywalled rankings, automatic lineup submission, waiver claims or
trade sending in this iteration. Free APIs may fail; last-good snapshots keep
original dates and incomplete data stays explicit. Frozen draft data stays separate.
