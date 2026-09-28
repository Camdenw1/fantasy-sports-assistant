# Visual design

Owner goal: **clean, simple, easy to follow.** This document critiques the current
draft board's look, sets the principles for the multi-league manager, and defines
the design system. Tokens live in `design-tokens.css`. `design-mockup.html` shows
them in use: open it in a browser and use the sidebar's theme button to see dark mode.

Companion docs: `ux.md` (information architecture, flows, wireframes) and
`dashboard.md` (home content). This doc covers look and feel only. Where the two
touch, this one follows `ux.md`: navigation is Home · Leagues · Players · Draft,
there are three freshness states, and 44px tap targets.

---

## 1. Critique of the current board (`draft-board-2026.html`)

Reviewed in a browser at 1440px and 375px, with live data from 25 Sep 2026.

### What works — keep it

- **The warm paper palette.** `#FBFAF7` paper, white panels and hairline
  `#E6E2D9` rules read calm and serious. They stand out from the loud,
  dark sportsbook look most fantasy tools use. It carries forward as `--color-bg`.
- **Muted position chips.** Pale tinted fills with dark same-hue text (QB blue,
  RB green, WR ochre, TE violet). You can tell positions apart at a glance, and no
  chip shouts. We keep the hues and darken the WR text to pass AA.
- **Tiers as rules, not colors.** A small green "TIER 3" label and a hairline
  across the table. This is the right call and stays: tiers are separators.
- **Tabular numerals** on every number column, so ranks and ADP line up.
- **`+` / `−` glyphs on green/red flags**, so the sign carries the meaning even
  without color. This pattern extends to every status.
- **Drafted rows fade and get struck through; my picks get a green tint.** Both
  states are clear at a glance. Keep both.
- **Data freshness is shown per source** as dots, with red for stale. The
  instinct is right; the treatment needs more weight (below).
- **Honest copy.** "Cheap for a reason is not the same as cheap." The tone is
  direct and dry. Keep that voice in reason lines.

### What doesn't — change it

1. **Monospace uppercase everywhere.** Buttons, labels, headers, kicker, hints
   and the tally are all 9–11px mono caps with 0.08–0.2em tracking. This is the
   biggest legibility cost on the page: caps at that size lose word shapes, and
   mono widens every table column, which is why the phone layout overflows.
   *Fix:* sans (Inter or the system UI font) for all UI text, with tabular figures
   for numbers. Mono is kept for ids and timestamps. Small caps labels are allowed
   only for section and group headers, at 11px with 0.04em tracking.
2. **Too many things are "dimmer" gray.** `--dimmer #98A0A9` on paper is
   **2.5:1** and is used for meta text, table headers, team codes and hints. That
   fails WCAG AA. `--warn #B5842B` as text is **3.2:1**. *Fix:* three text levels,
   all AA or better: text / text-2 (6.0:1) / text-3 (4.9:1).
3. **Green does four jobs.** It marks the brand (h1 em, kicker), the primary
   button, the "sorted" header, tier labels, "good" numbers and "mine". When
   everything is green, nothing is. *Fix:* the accent green is for **primary
   action and current selection** only. "Positive" shares the hue but always
   comes with a glyph or word. Tier labels keep it because they are wayfinding.
4. **The header is a landing page, not a tool.** A 38px headline ("Market ADP,
   expert rank, and your league model."), a paragraph and a method panel all sit
   above the work. On a phone the first player row is roughly 1,100px down.
   *Fix:* the title is the context ("Week 4", "Draft · Home League"). The method
   goes behind an "About these numbers" link. Freshness shrinks to one line.
5. **The control rail is one flat row of 15 equal-weight controls.** Position
   chips, search, hide-drafted, next pick, draft id, slot, sync, tally and reset
   all look the same. On a 375px phone it wraps to **252px of sticky chrome**.
   *Fix:* group the controls by how often they're used. Filters and search stay
   on the rail. Draft sync (id, slot, on/off) moves into a "Connect draft" sheet
   and, once connected, shows as one status pill. Reset moves into a menu.
6. **Horizontal scroll on phones.** The page measured **536px wide in a 375px
   viewport**. Names wrap to three lines because the `+` and detail buttons sit
   inline after the name. *Fix:* on phones each row becomes two lines: the name,
   then chip · team · bye underneath. Expert, Model and Bye columns drop out, and
   the row keeps #, Player, Lasts, Market and Edge.
7. **Square 2px corners and 1px borders on buttons and inputs** make controls
   look like disabled text fields. Pair that with 6px padding and the hit area is
   about 26px. *Fix:* 6px radius, 36px minimum height on desktop, 44px on touch.
8. **Badges come in four visual dialects:** `.badge`, `.inj`, `.trend` and
   `.mkn` each have their own size and border recipe. *Fix:* one badge component
   with semantic variants (section 4.3).
9. **No dark mode.** Game-day use is often on a phone in a dim room at 6:30 AM
   PT. Dark mode is now a first-class theme, driven by tokens.
10. **Hover-only information.** Column meanings sit in `title` attributes and in
   a hint paragraph below 250 rows. *Fix:* a short legend right under the table,
   plus an info affordance on headers that works on tap.

---

## 2. Principles

1. **One job per screen, visible in the first viewport.** Home answers "what do I
   need to do, and by when?" before anything else.
2. **Say the call, then the reason, in one line each.** A recommendation card is a
   verb plus players (bold), then a single plain sentence with a concrete cause.
   No paragraphs on the surface; detail is one tap away.
3. **Color is a second channel, never the only one.** Every status has an icon
   and a word. Red means "act"; amber means "check"; gray means "fine or not
   applicable". Nothing else gets saturated color.
4. **Quiet by default, loud by exception.** Most rows are black on white. A row
   earns a tint only for a problem (out, empty slot) or ownership (mine).
5. **Numbers are aligned, sized by importance, and never decorated.** Tabular
   figures; the one number that matters on a card is the large one.
6. **Freshness is part of the data.** Fresh data gets a small dot. Aging data
   gets an amber timestamp. Stale data gets a red timestamp and pulls its
   recommendations down to "Check", with a button that opens the platform
   instead of acting on it.
7. **The phone is the primary game-day device.** Design at 375px first. No
   horizontal page scroll. Primary actions sit in the thumb zone.
8. **Keep the board's personality.** Warm paper, restrained ink, tinted chips,
   tier rules. Evolve it; don't replace it with a generic dashboard kit.

---

## 3. Design system

All values are in `design-tokens.css`. Components reference tokens, never hex.

### 3.1 Color

Light theme values; dark values are re-pointed under the same names.

| Role | Token | Light | Dark | Use |
|---|---|---|---|---|
| Page | `--color-bg` | `#FAF9F6` | `#121416` | app background |
| Surface | `--color-surface` | `#FFFFFF` | `#1A1D21` | cards, tables, nav |
| Surface 2 | `--color-surface-2` | `#F4F2ED` | `#22262B` | hover, group headers, wells |
| Surface 3 | `--color-surface-3` | `#ECE9E2` | `#2A2F35` | pressed, track fills |
| Border | `--color-border` | `#E6E2D9` | `#2C3137` | hairlines, row dividers |
| Border strong | `--color-border-strong` | `#CFC8BB` | `#3D444C` | inputs, table header rule, tier rule |
| Text | `--color-text` | `#1E252C` | `#E9E7E2` | primary |
| Text 2 | `--color-text-2` | `#58616B` | `#AEB5BD` | reasons, secondary |
| Text 3 | `--color-text-3` | `#666E78` | `#8D959E` | meta, headers, timestamps |
| Accent | `--color-accent` | `#256B4D` | `#5FBF92` | primary button, current nav, "mine" |
| Focus | `--color-focus` | `#2F6E9E` | `#7DB4E0` | focus ring (blue, so it never reads as a status) |

**Feedback families.** Each has fg / bg / border: `positive` (green), `negative`
(brick), `caution` (ochre), `info` (blue), `neutral` (gray). Every fg-on-bg pair
measures **5.0:1 or better** in light mode and **6.2:1 or better** in dark.

**Status (lineups and recommendations).** These map onto the families, so a new
status never needs a new color.

| Status | Token pair | Icon | Word | Row treatment |
|---|---|---|---|---|
| Start / playing | `--status-start-*` | check | Start | none |
| Sit / bench | `--status-sit-*` | — | Bench | none |
| Suggested move | `--status-swap-*` | swap arrows | Move | none; the rec card carries it |
| Questionable | `--status-q-*` | triangle | Q | none |
| Doubtful | `--status-d-*` | triangle | D | none |
| Out / IR / PUP / Sus | `--status-out-*` | × | Out / IR | brick tint + 3px left bar + strikethrough |
| Empty starter slot | `--status-empty-fg` | dashed circle | Fill | brick tint + left bar |
| Bye | `--status-bye-*` | — | Bye | none |
| Locked / final | neutral outline | padlock | Final / Locked | text dims to text-2 |

**Positions.** These keep the board's hues. Chips are a tint fill plus dark same-hue text.

| | bg / fg (light) | bg / fg (dark) |
|---|---|---|
| QB | `#DDEBF5` / `#1D5580` | `#1B2C3B` / `#8EC0E6` |
| RB | `#DFEEE6` / `#1F6247` | `#1B3027` / `#86CFA8` |
| WR | `#F7EEDA` / `#7A5510` | `#352B17` / `#E3BF72` |
| TE | `#EEE5F4` / `#6A3E8A` | `#2C2236` / `#C9A5E4` |
| K | `#EEEDE7` / `#52554C` | `#2A2B27` / `#C2C4B8` |
| DST | `#E4EBEF` / `#3A5566` | `#212C33` / `#A2BCCB` |
| Slot labels (FLEX, W/T, BN) | `--pos-flex-*` neutral | — |

All six measure 5.8:1 or better. Position chips are always labeled with text, so
the hue is only a speed-up.

**Tiers.** Tiers use no fill color. The label is `--tier-label` (accent) and the
rule is `--tier-rule`. `--tier-band-even` is an optional near-invisible zebra
for long positional views.

**Draft tags.** `VALUE` uses info blue, `SLEEPER` uses positive green and `FADE`
uses negative brick. Tags are words, so they stay readable without color.

**Freshness.** Fresh = `--fresh-ok` dot and nothing more. Aging = `--fresh-aging-*`
amber timestamp or badge. Stale or failed = `--fresh-stale-*` red timestamp, and
the dependent recommendations are demoted. Thresholds are defined in `ux.md` §6.4.

**League identity.** `--league-1…5` are neutral hues the user assigns to each
league. They show up as an 8px dot and a 3px card edge. They are deliberately
**not** Sleeper, ESPN or CBS brand colors. The platform name is always written
out ("Home League · Sleeper"), so we never imitate another company's branding and
two leagues on the same platform stay distinct.

### 3.2 Typography

- **Face:** Inter (optional Google Fonts load), falling back to the system UI
  font. There is one family. Numbers use `font-variant-numeric: tabular-nums`, so
  columns align without monospace width.
- **Mono** only for draft ids, raw timestamps and code-like values.

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `--text-2xl` | 28 / 34 | 700 | the one hero number on a card (projected score) |
| `--text-xl` | 22 / 28 | 700 | page title ("Week 4") |
| `--text-lg` | 18 / 24 | 600 | section titles, card titles |
| `--text-md` | 15 / 22 | 400–600 | body, player names, action titles |
| `--text-sm` | 13 / 20 | 400–600 | table cells, reason lines, buttons |
| `--text-xs` | 11 / 16 | 500–600 | meta, table headers, badges, group labels |

Rules: no text below 11px (the current board goes to 8.5px). Uppercase appears
only at `--text-xs` for group headers ("LOCKS SUNDAY 10:00 AM", "TIER 3", "BENCH"),
with 0.04em tracking. Headlines get −0.011em tracking. Inputs use 16px on phones
so iOS doesn't zoom.

### 3.3 Spacing, radius, elevation

- **Spacing:** 4px grid. The tokens are `--space-1` through `--space-12`
  (4, 8, 12, 16, 20, 24, 32, 40, 48). Cards pad 16px. Sections are 24px apart on
  phones and 32px on desktop. The phone gutter is 16px.
- **Radius:** 3px chips and badges · 6px buttons and inputs · 10px cards · 14px
  sheets · pill for counts.
- **Elevation:** borders do the work. `--shadow-1` is a barely-there lift for
  cards. `--shadow-2` is for sticky bars and menus. `--shadow-3` is for sheets
  and dialogs. Dark mode uses the same levels at higher opacity.

### 3.4 Density rules for data-heavy tables

- **Three row heights.** Compact is 36px (desktop draft board, 250 rows). Default
  is 44px (lists). Touch is 52px (two-line phone rows and lineup slots).
- **Numbers right-aligned, text left.** Headers align with their column's data.
  Column order runs from most to least decision-relevant, left to right.
- **One emphasized number per row.** On the draft board that's the rank. Deltas
  (Edge) get color *and* a sign character (`+15`, `−11`). Zero stays in text-3.
- **Hairline row dividers** instead of zebra stripes. Zebra striping clashes
  with tier rules and state tints.
- **Sticky header row** on surface background, with a strong-border underline.
- **Column dropping, not squeezing.** Each column has a priority. Below 1080px
  Model drops. Below 640px Bye, Expert and Pos drop, and position moves under
  the name. A table never scrolls sideways inside the page, except for the
  optional full board, which may scroll inside its own card.
- **Inline micro-viz stays tiny:** a 32×4px bar for survival odds, always next
  to the % value, and hidden on phones where the number is enough.
- **State via row treatment:** drafted rows get text-3 plus strikethrough, mine
  get the accent-soft fill plus an accent name, problems get a tint plus a 3px
  left bar. There is never more than one treatment per row.

---

## 4. Component inventory

Each one is shown in `design-mockup.html` unless marked *(spec only)*.

### 4.1 App shell and navigation
- **Desktop (≥ 861px):** a 232px left sidebar with the brand, primary nav
  (Home · Leagues · Players · Draft, with an action count badge on Home), a
  "Leagues" list (dot + name + platform), then Settings & data and a theme
  control pinned to the bottom. A sticky top bar holds the page title, one
  freshness line and refresh.
- **Phone (≤ 860px):** the sidebar hides. The top bar is 52px: title, league
  switcher, refresh. A **bottom tab bar** (56px + safe area) carries the four
  destinations, with the count badge on Home. Content gets bottom padding so the
  last card clears the tab bar.
- The current nav item uses accent text on accent-soft (desktop) or accent
  icon+label (tabs). The item carries `aria-current="page"`.

### 4.2 League switcher
- Desktop: the sidebar league list *is* the switcher. Phone: a top-bar button
  ("● All leagues ▾") opens a sheet listing "All leagues" plus each league with
  its dot, name, platform, record and an issue count. *(Sheet is spec only.)*
- A scoped screen always shows the league tag in its header, so you never
  wonder which league you're editing.
- For the draft board, this replaces the old "Rank for: Sleeper league / Dad's
  league" buttons.

### 4.3 Status badge
- 22px tall (18px `tiny` inside dense rows), 3px radius, icon (12px) + word,
  semantic fg/bg pair. There is one component; variants are only the color class
  (`b-start`, `b-q`, `b-d`, `b-out`, `b-swap`, `b-bye`, `b-lock`, `b-stale`,
  `b-value`, `b-fade`, `b-sleeper`).
- On phones the lineup column hides the *word* only for Start and Final (the
  common, calm states). Q, D, Out, Fill and Move keep their words.

### 4.4 Player row
- Name (md, 500–600) · position chip · meta line (team, opponent, kickoff, injury
  body part) in xs text-3. The name truncates with an ellipsis and never wraps
  past two lines. Per-player controls (add, details) sit at the row end on
  phones, never inline mid-name.

### 4.5 Lineup slot card
- A card header with the league tag, "You vs {opponent}" and the projected score
  pair (hero number). If a fix is needed, the recommendation card (4.6) comes
  first. Then slot rows: slot label (xs, text-3, fixed 36–44px) · player row ·
  projection (right, semibold, tabular) · status badge. A "Bench" group header
  follows, and then the bench rows.
- The footer has one primary action ("Apply 2 changes") and a ghost link out to
  the platform. For platforms we can't write to, the primary becomes "Open in
  ESPN" and a "Mark done" ghost button.

### 4.6 Recommendation card (one-line reason)
- An info-tinted well inside the lineup card. **Title:** "Start X over Y" with
  the positive delta (`+11.8`) in positive color. **Reason:** one sentence in
  text-2 with a concrete cause. **Button:** Apply (primary), to the right on
  desktop and full width below on phones.
- Grammar follows `ux.md` §6.2. The reason never says "the model likes him".

### 4.7 Alert / action item
- The Home list, grouped under xs caps headers **by lock time** ("LOCKS SUNDAY
  10:00 AM"). Each item is a grid of a 28px status disc (icon on tinted circle),
  then a body, then an action.
  - Meta row: league dot + "League · Platform" + tiny status badge.
  - Title (md, semibold): the problem in plain words ("Isiah Pacheco is out —
    he's in your RB2 slot").
  - Reason (sm, text-2): the fix and why.
  - Action: primary when we can do it ("Start Spears"). Secondary when it needs
    judgment ("Review") or the data is stale ("Open CBS").
- A resolved league collapses to one calm line with a check disc.
- Phones stack the action under the body, left-aligned, 44px tall.

### 4.8 Stale-data banner
- It sits above page content, amber-tinted, clock icon, bold first clause naming
  the league and age, then a consequence and a "Sync now" button. One banner per
  page at most; it summarizes if several sources are stale.

### 4.9 Tables
- See §3.4. Filters use a segmented control (inverted fill for the active
  segment, `aria-pressed`). Search is a 16px input. Context ("Your next pick #27
  · 4 picks away") is right-aligned on desktop and on its own line on phones. A
  legend under the table defines each column in one short phrase.

### 4.10 Empty, loading and stale states
- **Loading:** skeleton bars at the real content's line heights. A shimmer runs
  only when reduced motion is off. The container sets `aria-busy="true"`. When
  cached data exists, render it with its age instead of a skeleton.
- **Empty (good news):** a check disc, a bold one-line all-clear ("All three
  lineups are set."), and the next relevant time. Never a blank card.
- **Empty (no data yet):** the same layout with a neutral icon and a single
  primary action ("Connect a league").
- **Stale:** the Data health card lists each source with a colored dot and age.
  An alert row explains the consequence in plain words.

### 4.11 Buttons and inputs
- Primary is solid accent. Secondary is surface with a strong border. Ghost is
  transparent with a text-2 label. Icon buttons are 36px square (44px on touch).
  Only one primary button per card.
- The focus ring is 2px `--color-focus` with a 2px offset, on every interactive
  element.

---

## 5. Responsive rules for game-day phone use

| Breakpoint | Layout |
|---|---|
| ≤ 640px | single column; action buttons under content; lineup status keeps words except Start/Final; draft rows go two-line with Pos/Bye/Expert/Model dropped; search goes full width |
| 641–860px | single column; bottom tab bar; league cards become compact rows |
| 861–1080px | sidebar appears; Home stacks actions above lineup; the Model column drops |
| > 1080px | Home is two columns (actions 7fr, lineup 5fr); full draft table |

- **Thumb zone:** navigation sits at the bottom. The primary action on each
  action item sits on the left under its text, reachable one-handed.
- **Priority order on Home (phone):** stale banner (if any) → this-week league
  rows (one line each, issue badge visible) → Needs attention → lineup. The first
  action item must start within the first viewport on a 375×667 phone.
- **No horizontal page scroll**, verified at 375px in the mockup
  (`scrollWidth === innerWidth`).
- **Sticky chrome budget on phones:** at most 52px on top plus 56px on the
  bottom. The old board spent 252px.
- Use `env(safe-area-inset-bottom)` for the tab bar and 16px input text.
- Everything must work without hover. `title` tooltips are only a bonus.

---

## 6. Accessibility

- **Contrast:** every text token pair meets WCAG AA (4.5:1) on the surfaces it
  sits on. Measured with the WCAG formula:
  text-2 on bg 6.0, text-3 on bg 4.9 and on surface-2 4.6, accent on white 6.4,
  status pairs 5.0–5.5 (light) and 6.3–7.3 (dark), position chips 5.8–6.5
  (light) and 7.2–8.1 (dark). Dark text-3 on surface is 5.6.
- **Not color-only:** statuses carry an icon + word; deltas carry a sign; tags
  are words; out/empty rows add strikethrough and a left bar; league identity
  always includes the name; freshness dots always sit next to an age.
- **Focus:** a visible 2px blue ring that is distinct from every status color.
- **Semantics:** nav uses `aria-current`, segmented filters use `aria-pressed`,
  loading regions use `aria-busy`, banners use `role="status"`, and icon-only
  buttons have `aria-label`. Count badges state their meaning ("3 items need
  action").
- **Motion:** 120–200ms fades only. `prefers-reduced-motion` zeroes the
  durations and stops the skeleton shimmer.
- **Targets:** 44px minimum on touch, 36px on desktop pointer.
- **Zoom:** layouts use rem type sizes and survive 200% zoom without clipping.

---

## 7. Applying this to the existing board

The draft board can adopt this system without touching the pipeline. Everything
below is a change to `draft-board-2026.html` only.

1. Replace the `:root` block with an import of `design-tokens.css` and map the
   old names (`--paper` → `--color-bg`, `--dim` → `--color-text-2`, `--dimmer`
   → `--color-text-3`, `--good` → `--color-accent`, position vars → `--pos-*`).
2. Switch `button`, `th`, `.kicker`, `.hint`, `.deck h4` and `.tally` from mono
   caps to sans `--text-xs`/`--text-sm`. Leave `td` numbers in sans with tabular
   figures.
3. Collapse `.badge`, `.inj`, `.trend` and `.mkn` into the single badge
   component.
4. Move the Sleeper sync inputs and Reset into a sheet/menu. The rail keeps
   position filters, search, hide-drafted and next pick.
5. Apply the phone two-line row (§3.4) so the table fits in 375px.
