const $ = id => document.getElementById(id);
const connection = JSON.parse(localStorage.getItem("fantasy-sleeper-connection") || "{}");
const manualKey = "fantasy-manual-leagues-v1";
const state = {username: connection.username || "camdenw1", selected: connection.leagueId || "",
  reports: [], freshness: null, manual: JSON.parse(localStorage.getItem(manualKey) || "[]"),
  sample: false, view: "home", lastRefresh: 0, editing: null, sleeperIds: []};

function node(tag, className = "", content = null) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (content != null) el.textContent = String(content);
  return el;
}
function add(parent, ...children) { parent.append(...children); return parent; }
function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}
function age(iso) {
  const ms = Date.now() - Date.parse(iso || "");
  if (!Number.isFinite(ms)) return "unknown age";
  const mins = Math.max(0, Math.floor(ms / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return mins + "m ago";
  if (mins < 1440) return Math.floor(mins / 60) + "h ago";
  return Math.floor(mins / 1440) + "d ago";
}
function number(value) { return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—"; }
function dateTime(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.valueOf()) ? "Time unknown" : date.toLocaleString([], {
    weekday: "short", hour: "numeric", minute: "2-digit", timeZoneName: "short"
  });
}
function inactive(player) {
  return player && ["Out", "IR", "PUP", "Sus", "NA", "DNR", "COV"].includes(player.injury);
}
function reportGaps(report) { return report.sources.projection_gaps || []; }
function quality(report) {
  const issues = [];
  if (state.sample) issues.push("Historical example");
  if (reportGaps(report).length) issues.push("Missing projections: " + reportGaps(report).map(p => p.name).join(", "));
  if (report.sources.schedule !== "espn scoreboard") issues.push("Kickoff times unverified");
  const injuryMs = Date.now() - Date.parse(state.freshness?.player_list_fetched_at || "");
  const rosterMs = Date.now() - Date.parse(state.freshness?.roster_fetched_at || "");
  const soon = report.slots.some(row => row.current?.kickoff &&
    Date.parse(row.current.kickoff) > Date.now() && Date.parse(row.current.kickoff) - Date.now() < 4 * 3600000);
  const limit = soon ? 2 * 3600000 : 24 * 3600000;
  if (!Number.isFinite(injuryMs) || injuryMs > limit) issues.push("Player/injury file needs checking");
  if (!Number.isFinite(rosterMs) || rosterMs > limit) issues.push("Roster needs refresh");
  if (!report.sources.projections.length) issues.push("Projection feeds unavailable");
  return issues;
}
function actionLink(report) {
  if (state.sample) return node("span", "meta", "Historical example · no action");
  const link = node("a", "action", "Open in Sleeper ↗");
  link.href = report.apply.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}
function card(label, title, body, kind, report) {
  const el = node("article", "card action-card " + kind);
  add(el, node("span", "pill", label), node("h3", "", title), node("p", "", body));
  if (report) el.append(actionLink(report));
  return el;
}
function sleeperItems(report) {
  const items = [], league = report.league.name;
  const gaps = reportGaps(report).length > 0;
  const changed = report.slots.filter(row => row.change && !row.locked);
  const forced = report.slots.filter(row => !row.locked &&
    (!row.current || row.current.game_state === "bye" || inactive(row.current)));
  for (const row of forced) {
    const current = row.current;
    const cause = !current ? "empty" : current.game_state === "bye" ? "on bye" : current.injury;
    const plan = changed.map(change => change.slot + " → " +
      (change.recommended?.name || "empty")).join("; ");
    const advice = gaps ? "Check the available players in Sleeper; this model is missing a roster projection." :
      plan ? "Suggested lineup: " + plan + "." : "No eligible rostered replacement found; check waivers.";
    items.push({priority: 0, element: card(league + " · Fix lineup",
      (!current ? row.slot : current.name) + " is " + cause,
      advice, "urgent", report)});
  }
  if (!gaps && !quality(report).some(x => x.includes("needs checking") || x.includes("unverified") || x.includes("needs refresh"))) {
    for (const swap of report.swaps) {
      if (forced.some(row => row.current?.id === swap.out)) continue;
      if (swap.delta < 1.5) continue;
      items.push({priority: 2, element: card(league + " · Lineup upgrade",
        "Start " + swap.in_name + " over " + (swap.out_name || "an empty slot"),
        swap.reason + " · " + swap.slot + " · +" + number(swap.delta) + " projected points.",
        "", report)});
    }
  }
  for (const alert of report.alerts) {
    if (alert.type !== "gtd_recheck") continue;
    items.push({priority: 1, element: card(league + " · Recheck injury", alert.message,
      "Check official inactives before kickoff. Suggested check: " + dateTime(alert.at) + ".",
      "check", report)});
  }
  return items;
}
function manualItems(league) {
  const items = [];
  for (const row of league.starters) {
    if (["Out", "IR", "Bye", "Empty"].includes(row.status)) {
      items.push({priority: 0, element: card(league.name + " · " + league.platform + " snapshot",
        row.status === "Empty" ? row.slot + " is empty" : row.player + " is " + row.status,
        "Snapshot from " + age(league.savedAt) + ". Check the platform for a legal replacement and current status.", "urgent")});
    } else if (["Questionable", "Doubtful"].includes(row.status)) {
      items.push({priority: 1, element: card(league.name + " · " + league.platform + " snapshot",
        "Recheck " + row.player + " (" + row.status + ")",
        "Snapshot from " + age(league.savedAt) + ". Confirm the designation before lineup lock.", "check")});
    }
  }
  return items;
}
function leagueStrip() {
  const section = node("section", "league-strip");
  for (const report of state.reports) {
    const issues = quality(report);
    const el = node("article", "card league-card");
    add(el, node("span", "pill", "Sleeper · Week " + report.league.week),
      node("h3", "", report.league.name),
      node("p", "meta", issues.length ? issues.join(" · ") :
        "Lineup checked · " + age(state.freshness?.roster_fetched_at)));
    const button = node("button", "quiet", "View lineup");
    button.addEventListener("click", () => selectLeague("s:" + report.league.id));
    el.append(button); section.append(el);
  }
  for (const league of state.manual) {
    const el = node("article", "card league-card");
    add(el, node("span", "pill", league.platform + " · Week " + league.week),
      node("h3", "", league.name), node("p", "meta", "Manual snapshot · " + age(league.savedAt) +
      (league.scoring ? " · " + league.scoring : "")));
    const view = node("button", "quiet", "View snapshot");
    view.addEventListener("click", () => selectLeague("m:" + league.id));
    const edit = node("button", "text-button", "Update");
    edit.addEventListener("click", () => editManual(league));
    add(el, view, edit); section.append(el);
  }
  return section;
}
function renderHome(main) {
  add(main, node("h2", "section-head", "Your leagues"), leagueStrip());
  if (state.sample) main.prepend(node("div", "notice", "Saved week-3 example. Nothing here is current."));
  const issues = state.reports.flatMap(report => quality(report).map(issue => report.league.name + ": " + issue));
  const stale = state.manual.filter(league => Date.now() - Date.parse(league.savedAt) > 24 * 3600000);
  if (stale.length) issues.push(stale.map(league => league.name).join(", ") + ": manual snapshot over 24 hours old");
  if (issues.length) main.append(node("div", "notice", issues.join(" · ")));
  main.append(node("h2", "section-head", "What needs attention"));
  const items = [...state.reports.flatMap(sleeperItems), ...state.manual.flatMap(manualItems)]
    .sort((a, b) => a.priority - b.priority);
  if (!items.length) main.append(add(node("section", "card clear"),
    node("h3", "", issues.length ? "No confirmed lineup fix" : "No lineup change suggested"),
    node("p", "", "Check the platform before lineup lock. Manual snapshots reflect only the status you entered.")));
  else items.forEach(item => main.append(item.element));
  if (state.reports.length) main.append(node("p", "meta", "Projection feeds: " +
    [...new Set(state.reports.flatMap(report => report.sources.projections))].join(", ") +
    " · Player file downloaded " + age(state.freshness?.player_list_fetched_at) +
    " · Upstream projection update time is not provided."));
}
function playerCell(player) {
  const cell = node("td");
  if (!player) return add(cell, node("span", "", "Empty"));
  add(cell, node("strong", "", player.name));
  add(cell, node("small", inactive(player) ? "injury" : "",
    [player.pos, player.team, player.injury, player.game_state === "bye" ? "BYE" : ""].filter(Boolean).join(" · ")));
  return cell;
}
function renderSleeperLineup(main, report) {
  add(main, node("h2", "section-head", report.team.name + " · " + report.league.name + " · Week " + report.league.week),
    node("p", "meta", "Current lineup versus a league-scored estimate. Locked players stay in place."));
  const issues = quality(report);
  if (issues.length) main.append(node("div", "notice", issues.join(" · ") +
    ". Confirm uncertain recommendations in Sleeper."));
  const summary = node("section", "summary");
  const incomplete = reportGaps(report).length > 0;
  const totals = add(node("div", "card"), node("strong", "metric", incomplete ? "Incomplete" :
    number(report.totals.current) + " → " + number(report.totals.recommended)),
    node("span", "caption", incomplete ? "Missing roster projections; totals withheld" :
      "Current → recommended projected points"));
  summary.append(totals);
  if (report.opponent && !incomplete) summary.append(add(node("div", "card"),
    node("strong", "metric", Math.round(report.opponent.win_prob_current * 100) + "% → " +
      Math.round(report.opponent.win_prob_recommended * 100) + "%"),
    node("span", "caption", "Matchup win chance · uncalibrated model estimate")));
  main.append(summary);
  const table = node("table", "lineup-table"), header = node("tr");
  ["Slot", "Current", "Recommended", "Projected", "Why"].forEach(label => header.append(node("th", "", label)));
  table.append(add(node("thead"), header));
  const body = node("tbody");
  for (const row of report.slots) {
    const tr = node("tr", row.change ? "changed" : "");
    add(tr, node("td", "", row.slot), playerCell(row.current), playerCell(row.recommended),
      node("td", "", (row.current ? number(row.current.value) : "—") + " → " +
        (row.recommended ? number(row.recommended.value) : "—")),
      node("td", "", row.locked ? "Locked" : row.reason));
    body.append(tr);
  }
  table.append(body); main.append(table);
  main.append(add(node("p", "meta"), actionLink(report)));
}
function renderManualLineup(main, league) {
  add(main, node("h2", "section-head", league.name + " · " + league.platform + " · Week " + league.week),
    node("p", "meta", "Saved " + dateTime(league.savedAt) + " · " + age(league.savedAt) +
      " · " + (league.scoring || "Scoring not recorded")));
  main.append(node("div", "notice", "Manual snapshot. Injuries and roster changes do not update automatically; start/sit projections are unavailable."));
  if (league.starters.length) {
    const table = node("table", "lineup-table"), head = node("tr");
    ["Slot", "Starter", "Entered status"].forEach(label => head.append(node("th", "", label)));
    table.append(add(node("thead"), head));
    const body = node("tbody");
    for (const row of league.starters) body.append(add(node("tr"),
      node("td", "", row.slot), node("td", "", row.player), node("td", "", row.status)));
    table.append(body); main.append(table);
  }
  const update = node("button", "quiet", "Update snapshot");
  update.addEventListener("click", () => editManual(league));
  const remove = node("button", "text-button", "Remove league");
  remove.addEventListener("click", () => {
    if (!confirm("Remove " + league.name + " from this browser?")) return;
    state.manual = state.manual.filter(item => item.id !== league.id);
    saveManual(); state.selected = ""; populateLeagues(); setView("home");
    status(league.name + " removed from this browser.");
  });
  main.append(add(node("div", "manual-buttons"), update, remove));
}
function render() {
  const main = $("content"); main.replaceChildren();
  const hasData = state.reports.length || state.manual.length;
  if (!hasData) main.append(add(node("section", "empty"), node("h2", "", "Add your leagues"),
    node("p", "", "Connect Sleeper for live reads. Add ESPN, CBS, or another platform as a manual snapshot.")));
  else if (state.view === "home") renderHome(main);
  else {
    const chosen = state.selected.startsWith("s:") ? state.reports.find(x => "s:" + x.league.id === state.selected) :
      state.manual.find(x => "m:" + x.id === state.selected);
    if (chosen?.schema) renderSleeperLineup(main, chosen);
    else if (chosen) renderManualLineup(main, chosen);
    else setView("home");
  }
  const fresh = $("freshness");
  fresh.hidden = !state.reports.length;
  if (state.reports.length) {
    fresh.classList.toggle("warn", state.reports.some(report => quality(report).length));
    fresh.textContent = (state.sample ? "SAVED EXAMPLE · " : "FETCHED · ") +
      "Roster " + age(state.freshness?.roster_fetched_at) +
      " · Player/injury file " + age(state.freshness?.player_list_fetched_at) +
      " · Projection feed " + age(state.freshness?.projections_fetched_at);
  }
}
function setView(view) {
  state.view = view;
  for (const kind of ["home", "lineup"]) {
    $(kind + "-tab").classList.toggle("active", kind === view);
    $(kind + "-tab").setAttribute("aria-pressed", String(kind === view));
  }
  render();
}
function populateLeagues() {
  const select = $("league"); select.replaceChildren();
  for (const report of state.reports) {
    const option = node("option", "", "Sleeper · " + report.league.name);
    option.value = "s:" + report.league.id; select.append(option);
  }
  for (const league of state.manual) {
    const option = node("option", "", league.platform + " · " + league.name);
    option.value = "m:" + league.id; select.append(option);
  }
  select.disabled = !select.options.length;
  if (!select.disabled) {
    if (!Array.from(select.options).some(opt => opt.value === state.selected)) state.selected = select.value;
    select.value = state.selected;
  }
}
function selectLeague(key) {
  state.selected = key; $("league").value = key; setView("lineup");
}
function busy(on) {
  $("refresh").disabled = on || !state.sleeperIds.length;
  $("sample").disabled = on;
  $("connect-form").querySelector("button").disabled = on;
}
async function getJson(url, options) {
  const response = await fetch(url, options), body = await response.json();
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}
async function findLeagues() {
  const username = $("username").value.trim();
  busy(true); status("Finding Sleeper fantasy leagues…");
  try {
    const data = await getJson("/api/leagues?username=" + encodeURIComponent(username));
    state.username = username;
    state.sleeperIds = data.leagues.map(league => league.id);
    status(data.leagues.length ? data.leagues.length + " Sleeper fantasy league(s) found. Loading lineups…" :
      "No Sleeper fantasy leagues found for this season. Pick’em may need a separate connection.");
    if (state.sleeperIds.length) await refresh();
    else { busy(false); render(); }
  } catch (error) { busy(false); status(error.message, true); }
}
async function refresh() {
  if (!state.sleeperIds.length) return;
  busy(true); status("Reading all Sleeper rosters, injuries, projections, and matchups…");
  try {
    const data = await getJson("/api/lineups", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: state.username})});
    state.reports = data.reports; state.freshness = data.freshness;
    state.sample = false; state.lastRefresh = Date.now();
    populateLeagues();
    const selectedSleeper = state.selected.startsWith("s:") ? state.selected.slice(2) :
      (state.reports[0]?.league.id || "");
    localStorage.setItem("fantasy-sleeper-connection", JSON.stringify({username: state.username, leagueId: selectedSleeper}));
    status("Updated " + state.reports.length + " Sleeper league(s). Read-only: make changes in Sleeper.");
    render();
  } catch (error) { status(error.message, true); }
  finally { busy(false); }
}
function saveManual() { localStorage.setItem(manualKey, JSON.stringify(state.manual)); }
const statuses = {active: "Active", q: "Questionable", questionable: "Questionable",
  d: "Doubtful", doubtful: "Doubtful", out: "Out", ir: "IR", bye: "Bye", empty: "Empty"};
function parseStarters(text, required) {
  const lines = text.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  if (required && !lines.length) throw new Error("Enter at least one starter.");
  return lines.map((line, index) => {
    const parts = line.split("|").map(x => x.trim());
    if (parts.length !== 3 || !parts[0] || !parts[1])
      throw new Error("Line " + (index + 1) + ": use slot | player | status.");
    const result = statuses[parts[2].toLowerCase()];
    if (!result) throw new Error("Line " + (index + 1) + ": unknown status " + parts[2] + ".");
    return {slot: parts[0].slice(0, 30), player: parts[1].slice(0, 80), status: result};
  });
}
function editManual(league) {
  state.editing = league.id;
  $("manual-name").value = league.name;
  $("manual-platform").value = league.platform;
  $("manual-scoring").value = league.scoring;
  $("manual-week").value = league.week;
  $("manual-starters").value = league.starters.map(row =>
    row.slot + " | " + row.player + " | " + row.status).join("\n");
  $("manual-import").open = true;
  $("manual-import").scrollIntoView({behavior: "smooth"});
}
$("manual-form").addEventListener("submit", event => {
  event.preventDefault();
  try {
    const platform = $("manual-platform").value;
    const starters = parseStarters($("manual-starters").value, platform !== "Sleeper Pick’em");
    const league = {id: state.editing || crypto.randomUUID(), name: $("manual-name").value.trim(),
      platform, scoring: $("manual-scoring").value.trim(), week: Number($("manual-week").value),
      starters, savedAt: new Date().toISOString()};
    if (!league.name || !Number.isInteger(league.week) || league.week < 1 || league.week > 18)
      throw new Error("Enter a league name and week 1–18.");
    if (state.editing) state.manual = state.manual.map(item => item.id === state.editing ? league : item);
    else state.manual.push(league);
    saveManual(); state.selected = "m:" + league.id; populateLeagues();
    state.editing = null; $("manual-form").reset(); $("manual-import").open = false;
    status(league.name + " saved in this browser at " + dateTime(league.savedAt) + ".");
    setView("home");
  } catch (error) { status(error.message, true); }
});
$("manual-cancel").addEventListener("click", () => {
  state.editing = null; $("manual-form").reset(); $("manual-import").open = false;
});
$("manual-platform").addEventListener("change", () => {
  $("manual-starters").required = $("manual-platform").value !== "Sleeper Pick’em";
});
$("connect-form").addEventListener("submit", event => { event.preventDefault(); findLeagues(); });
$("league").addEventListener("change", () => selectLeague($("league").value));
$("refresh").addEventListener("click", refresh);
$("sample").addEventListener("click", async () => {
  try {
    const data = await getJson("/api/sample");
    state.reports = [data.report]; state.freshness = data.freshness; state.sample = true;
    populateLeagues(); status("Showing a saved week-3 injury scenario. Nothing here is live."); render();
  } catch (error) { status(error.message, true); }
});
$("home-tab").addEventListener("click", () => setView("home"));
$("lineup-tab").addEventListener("click", () => setView("lineup"));
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.reports.length && !state.sample &&
      Date.now() - state.lastRefresh > 60000) refresh();
});
$("username").value = state.username;
$("manual-week").value = 1;
populateLeagues(); render(); findLeagues();
