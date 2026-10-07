/* Live views: fantasy scoreboards for every connected league, and Sleeper Pick'em.
   Everything here is read-only. Scores come from Sleeper's public matchup API and
   ESPN's public NFL scoreboard; Pick'em picks are recorded in this browser only. */
const live = {pickem: null, pickemError: null, leagues: {}, shown: {}, timer: null, lastPoll: 0};
const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/* Satisfying numbers: count up to the new value, pulse, and float the gain. */
function scoreNumber(key, value, className = "score") {
  const el = node("span", className, value == null ? "—" : value.toFixed(value % 1 ? 2 : 0));
  const before = live.shown[key];
  live.shown[key] = value;
  if (value == null || before == null || before === value || reduceMotion) return el;
  const start = performance.now(), from = before, span = value - from;
  const digits = Number.isInteger(from) && Number.isInteger(value) ? 0 : 2;
  el.textContent = from.toFixed(digits);
  const step = now => {
    const t = Math.min(1, (now - start) / 900), eased = 1 - Math.pow(1 - t, 3);
    el.textContent = (from + span * eased).toFixed(digits);
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
  if (span > 0) {
    el.classList.add("bump");
    const wrap = node("span", "score-wrap");
    const gain = node("span", "score-gain", "+" + span.toFixed(span % 1 ? 1 : 0));
    wrap.append(el, gain);
    return wrap;
  }
  return el;
}

/* ---------- Fantasy scoreboards ---------- */
async function loadLeagueScores(report, week) {
  const id = report.league.id, entry = live.leagues[id] || {};
  const base = "https://api.sleeper.app/v1/league/" + id;
  try {
    // Users and rosters change rarely; matchups are the live part.
    if (!entry.teams || Date.now() - entry.teamsAt > 3600000) {
      const [users, rosters] = await Promise.all([getJson(base + "/users"), getJson(base + "/rosters")]);
      const names = Object.fromEntries(users.map(u => [u.user_id, u.metadata?.team_name || u.display_name]));
      entry.teams = Object.fromEntries(rosters.map(r => [r.roster_id, {name: names[r.owner_id] || "Team " + r.roster_id,
        record: (r.settings?.wins || 0) + "–" + (r.settings?.losses || 0)}]));
      entry.teamsAt = Date.now();
    }
    const matchups = await getJson(base + "/matchups/" + week);
    const games = {};
    for (const m of matchups) if (m.matchup_id != null) (games[m.matchup_id] ||= []).push(m);
    entry.games = Object.values(games).map(pair => pair.sort((a, b) => a.roster_id - b.roster_id));
    entry.week = week; entry.at = Date.now(); entry.error = null;
  } catch { entry.error = "Scores unavailable right now."; }
  live.leagues[id] = entry;
}
function nflState() {
  const games = live.pickem?.games || [];
  return {live: games.some(g => g.state === "in"), started: games.some(g => g.state !== "pre"),
    done: games.length && games.every(g => g.state === "post")};
}
function matchupCard(report, entry, mine) {
  const me = mine.find(m => m.roster_id === report.team.roster_id), them = mine.find(m => m !== me);
  const card = node("section", "matchup-hero");
  const nfl = nflState();
  const status = nfl.done ? "Final" : nfl.live ? "Live" : nfl.started ? "In progress" : "Kicks off " +
    (live.pickem?.games?.[0] ? dateTime(live.pickem.games[0].kickoff) : "this week");
  const side = (m, label, projected, cls) => {
    const team = entry.teams?.[m?.roster_id] || {name: label, record: ""};
    const points = m ? (m.custom_points ?? m.points ?? 0) : null;
    return add(node("div", "matchup-side " + cls),
      add(node("div", "matchup-team"), node("strong", "", team.name), node("span", "meta", team.record)),
      scoreNumber(report.league.id + ":" + (m?.roster_id ?? cls), points, "score big"),
      node("span", "matchup-proj", projected != null ? "Proj " + number(projected) : ""));
  };
  const myPts = me ? (me.custom_points ?? me.points ?? 0) : 0, theirPts = them ? (them.custom_points ?? them.points ?? 0) : 0;
  const left = side(me, report.team.name, report.totals?.current, "mine"), right = side(them, report.opponent?.team_name || "Opponent", report.opponent?.projected, "theirs");
  if (myPts !== theirPts) (myPts > theirPts ? left : right).classList.add("leading");
  add(card, add(node("div", "matchup-head"), node("span", "live-dot " + (nfl.live ? "on" : ""), status),
    node("span", "meta", report.league.name)), add(node("div", "matchup-board"), left, node("span", "matchup-vs", "vs"), right));
  if (report.opponent && !nfl.done) {
    const p = report.opponent.win_prob_current;
    const bar = node("div", "win-bar"); bar.style.setProperty("--p", Math.round(p * 100) + "%");
    bar.setAttribute("role", "img"); bar.setAttribute("aria-label", "Win chance " + Math.round(p * 100) + " percent, model estimate");
    add(card, bar, node("p", "meta", "Win chance " + Math.round(p * 100) + "% · pregame model estimate"));
  }
  return card;
}
function otherMatchups(report, entry) {
  const list = node("ol", "other-matchups");
  for (const pair of entry.games) {
    if (pair.some(m => m.roster_id === report.team.roster_id)) continue;
    const [a, b] = pair, pa = a.custom_points ?? a.points ?? 0, pb = b ? (b.custom_points ?? b.points ?? 0) : 0;
    const row = node("li", "other-row");
    const team = (m, pts, lead) => add(node("span", "other-team" + (lead ? " leading" : "")), node("span", "", entry.teams?.[m.roster_id]?.name || "Team"),
      scoreNumber(report.league.id + ":" + m.roster_id, pts, "score"));
    add(row, team(a, pa, pa > pb), b ? team(b, pb, pb > pa) : node("span", "meta", "Bye"));
    list.append(row);
  }
  return list;
}
function renderScores(main) {
  const week = activeWeek() || live.pickem?.week;
  main.append(nflStrip());
  if (!state.reports.length && !state.manual.length)
    main.append(node("p", "meta", "Connect a league in Leagues to see your matchups here."));
  for (const report of state.reports) {
    const entry = live.leagues[report.league.id];
    if (!entry || entry.week !== week) { loadLeagueScores(report, week).then(() => state.view === "scores" && render()); }
    const section = add(node("section", "league-scores"), node("h2", "", report.league.name));
    if (!entry?.games) section.append(node("p", "meta", entry?.error || "Loading scores…"));
    else {
      const mine = entry.games.find(pair => pair.some(m => m.roster_id === report.team.roster_id)) || [];
      section.append(matchupCard(report, entry, mine));
      section.append(node("h3", "", "Around the league"), otherMatchups(report, entry));
    }
    main.append(section);
  }
  for (const league of state.manual.filter(l => l.platform !== "Sleeper Pick’em")) {
    const section = add(node("section", "league-scores"), node("h2", "", league.name),
      node("p", "meta", league.platform + " is a saved roster snapshot, so live scores aren’t available here yet."));
    if (league.url) { const a = node("a", "text-link", "Open in " + league.platform + " ↗"); a.href = league.url; a.target = "_blank"; a.rel = "noopener noreferrer"; section.append(a); }
    main.append(section);
  }
}
function teamLogo(abbr) { return teamMark(abbr) || node("span", "logo-fallback", abbr); }
function nflStrip() {
  const section = add(node("section", "nfl-strip"), node("h3", "", "NFL · Week " + (live.pickem?.week || "")));
  if (!live.pickem) { section.append(node("p", "meta", live.pickemError || "Loading games…")); return section; }
  const row = node("div", "nfl-games");
  for (const g of live.pickem.games) {
    const tile = node("div", "nfl-game " + g.state);
    const line = (t, cls) => add(node("div", "nfl-team " + cls), teamLogo(t.abbr), node("span", "", t.abbr),
      scoreNumber("nfl:" + g.id + ":" + t.abbr, g.state === "pre" ? null : t.score, "score"));
    add(tile, line(g.away, ""), line(g.home, ""), node("span", "nfl-detail", g.state === "pre" ? dateTime(g.kickoff) : g.detail));
    row.append(tile);
  }
  section.append(row);
  return section;
}

/* ---------- Pick'em ---------- */
const pickKey = () => "fantasy-pickem-picks:" + live.pickem.season + ":" + live.pickem.week;
function picks() { try { return JSON.parse(localStorage.getItem(pickKey())) || {}; } catch { return {}; } }
function savePick(gameId, side) {
  const all = picks();
  if (all[gameId] === side) delete all[gameId]; else all[gameId] = side;
  try { localStorage.setItem(pickKey(), JSON.stringify(all)); } catch {}
  render();
}
function spreadFor(game, side) {
  const home = game.spread_lock ?? game.spread_now;
  return home == null ? null : side === "home" ? home : -home;
}
function lineLabel(value) { return value == null ? "" : value === 0 ? "PK" : (value > 0 ? "+" : "") + value; }
function coverResult(game, side) {
  if (game.state === "pre") return null;
  const mine = game[side].score, theirs = game[side === "home" ? "away" : "home"].score, line = spreadFor(game, side);
  if (mine == null || theirs == null || line == null) return null;
  const margin = mine - theirs + line;
  return {margin, status: margin > 0 ? "cover" : margin < 0 ? "miss" : "push", final: game.state === "post"};
}
function renderPickem(main) {
  if (!live.pickem) { main.append(node("p", "meta", live.pickemError || "Loading this week’s games…")); return; }
  const data = live.pickem, mine = picks();
  const results = data.games.map(g => mine[g.id] ? coverResult(g, mine[g.id]) : null).filter(Boolean);
  const won = results.filter(r => r.final && r.status === "cover").length, lost = results.filter(r => r.final && r.status === "miss").length;
  const covering = results.filter(r => !r.final && r.status === "cover").length;
  const values = data.games.filter(g => g.value?.side && g.state === "pre");
  const tally = add(node("section", "pickem-tally"),
    add(node("div", "tally-main"), node("span", "caption", "Your week"),
      add(node("div", "tally-score"), scoreNumber("pickem:won", won, "score big"), node("span", "tally-dash", "–"), scoreNumber("pickem:lost", lost, "score big"))),
    add(node("dl", "tally-facts"),
      node("dt", "", "Covering now"), node("dd", "", String(covering)),
      node("dt", "", "Picked"), node("dd", "", Object.keys(mine).length + " of " + data.games.length),
      node("dt", "", "Value picks"), node("dd", "", String(values.length))));
  main.append(tally);
  const lock = data.lock;
  main.append(node("p", "meta pickem-lock", lock.captured_at ?
    "Locked lines saved " + dateTime(lock.captured_at) + (lock.approximate ? " — later than Sleeper’s Tuesday-morning lock, so a line may differ slightly. Use the Sleeper number if they disagree." : ".") :
    "Sleeper locks spreads Tuesday morning; locked lines save automatically then. Until that point the current line is shown."));
  if (values.length) {
    const list = add(node("section", "home-block"), node("h3", "", "Value since the lock"));
    const ol = node("ol", "value-list");
    for (const g of values.sort((a, b) => ["Strong", "Solid", "Minor"].indexOf(a.value.strength) - ["Strong", "Solid", "Minor"].indexOf(b.value.strength))) {
      const side = g.value.side, team = g[side];
      add(ol, add(node("li", "value-row " + g.value.strength.toLowerCase()), teamLogo(team.abbr),
        add(node("div", ""), node("strong", "", team.name + " " + lineLabel(spreadFor(g, side))),
          node("span", "meta", "Locked " + g.lock_text + " · now " + g.now_text)),
        node("span", "strength", g.value.strength)));
    }
    list.append(ol); main.append(list);
  } else main.append(node("p", "meta", "No line has moved since the lock yet. Value picks appear here when the market moves."));
  const board = add(node("section", "home-block"), node("h3", "", "All games"));
  const ol = node("ol", "pickem-games");
  for (const g of data.games) {
    const row = node("li", "pickem-game " + g.state);
    const pickButton = side => {
      const t = g[side], chosen = mine[g.id] === side, result = chosen ? coverResult(g, side) : null;
      const b = node("button", "pick" + (chosen ? " chosen" : "") + (result ? " " + result.status : ""));
      b.type = "button"; b.disabled = g.state !== "pre"; b.setAttribute("aria-pressed", String(chosen));
      add(b, teamLogo(t.abbr), add(node("span", "pick-copy"), node("strong", "", t.abbr + " " + lineLabel(spreadFor(g, side))),
        node("span", "pick-name", t.name)), scoreNumber("pick:" + g.id + ":" + side, g.state === "pre" ? null : t.score, "score"));
      if (g.value?.side === side && g.state === "pre") b.append(node("span", "value-tag", g.value.strength));
      b.addEventListener("click", () => savePick(g.id, side));
      return b;
    };
    const chosen = mine[g.id], result = chosen ? coverResult(g, chosen) : null;
    const status = result ? (result.status === "push" ? "Push" : (result.status === "cover" ? (result.final ? "✓ Covered" : "Covering") : (result.final ? "✗ Missed" : "Not covering")) +
      " by " + Math.abs(result.margin)) : g.state === "pre" ? dateTime(g.kickoff) : g.detail;
    add(row, add(node("div", "pickem-meta"), node("span", "", status),
      node("span", "meta", g.lock_text ? "Locked " + g.lock_text + (g.now_text && g.now_text !== g.lock_text ? " · now " + g.now_text : "") : g.now_text ? "Now " + g.now_text : "No line yet")),
      add(node("div", "pick-pair"), pickButton("away"), pickButton("home")));
    if (result) row.classList.add(result.status);
    ol.append(row);
  }
  board.append(ol);
  main.append(board, node("p", "meta", "Tap a team to record your pick here. Make your actual picks in Sleeper; Sleeper Pick’em has no public API, so nothing is sent to it. Spreads and scores: " + data.source + "."));
}

/* ---------- Polling ---------- */
async function loadPickem() {
  try { live.pickem = await getJson("/api/pickem"); live.pickemError = null; }
  catch (error) { live.pickemError = error.message; }
}
async function poll() {
  live.lastPoll = Date.now();
  await loadPickem();
  const week = activeWeek() || live.pickem?.week;
  if (state.view === "scores" || state.view === "home") await Promise.all(state.reports.map(r => loadLeagueScores(r, week)));
  if (["scores", "pickem", "home"].includes(state.view)) render();
  clearTimeout(live.timer);
  // Fast while any NFL game is on; slow otherwise.
  live.timer = setTimeout(poll, nflState().live ? 30000 : 300000);
}
function startLive() { if (Date.now() - live.lastPoll > 20000) poll(); }
window.renderScores = renderScores;
window.renderPickem = renderPickem;
window.live = live;
document.addEventListener("visibilitychange", () => { if (!document.hidden) startLive(); });
startLive();
