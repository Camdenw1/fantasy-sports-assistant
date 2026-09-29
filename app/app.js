const $ = id => document.getElementById(id);
function stored(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch { return fallback; }
}
const connection = stored("fantasy-sleeper-connection", {});
const manualKey = "fantasy-manual-leagues-v1";
const cached = stored("fantasy-last-lineups-v1", {});
const usableCache = cached.username === (connection.username || "camdenw1");
const state = {username: connection.username || "camdenw1", selected: connection.leagueId ? "s:" + connection.leagueId : "",
  reports: usableCache && Array.isArray(cached.reports) ? cached.reports : [], freshness: usableCache ? cached.freshness : null,
  manual: Array.isArray(stored(manualKey, [])) ? stored(manualKey, []) : [], week: null, currentWeek: null, season: null, loading: false,
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
function activeWeek() { return state.sample ? state.reports[0]?.league.week :
  state.week || state.currentWeek || state.reports[0]?.league.week; }
function quality(report) {
  const issues = [];
  if (state.sample) issues.push("Historical example");
  if (activeWeek() && report.league.week !== activeWeek()) issues.push("Roster is from a different week; refresh needed");
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
  if (activeWeek() && report.league.week !== activeWeek()) return items;
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
  if (activeWeek() && league.week !== activeWeek()) return items;
  for (const row of league.starters) {
    if (["Out", "IR", "PUP", "Sus", "Bye", "Empty"].includes(row.status)) {
      items.push({priority: 0, element: card(league.name + " · " + league.platform + " snapshot",
        row.status === "Empty" ? row.slot + " is empty" : row.player + " is " + row.status,
        "Snapshot from " + age(league.savedAt) + ". Check the platform for a legal replacement and current status.", "urgent")});
    } else if (["Questionable", "Doubtful", "Unknown"].includes(row.status)) {
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
      node("p", "meta", report.team.name + " · Updated " + age(state.freshness?.roster_fetched_at)));
    if (issues.length) el.append(node("span", "health-note", "△ " + issues.length +
      " input" + (issues.length === 1 ? "" : "s") + " to check"));
    const button = node("button", "quiet", "View lineup");
    button.addEventListener("click", () => selectLeague("s:" + report.league.id));
    el.append(button); section.append(el);
  }
  for (const league of state.manual) {
    const el = node("article", "card league-card");
    add(el, node("span", "pill", league.platform + " · Week " + league.week),
      node("h3", "", league.name), node("p", "meta", "Roster snapshot · " + age(league.savedAt) +
      (league.scoring ? " · " + league.scoring : "")));
    if (activeWeek() && league.week !== activeWeek()) el.append(node("span", "health-note",
      "△ Week " + league.week + " roster · update for week " + activeWeek()));
    const view = node("button", "quiet", "View snapshot");
    view.addEventListener("click", () => selectLeague("m:" + league.id));
    const edit = node("button", "text-button", "Update");
    edit.addEventListener("click", () => editManual(league));
    add(el, view, edit); section.append(el);
  }
  return section;
}
function renderHome(main) {
  if (state.sample) main.append(node("div", "notice", "Saved week-3 example. Nothing here is current."));
  const issues = state.reports.flatMap(report => quality(report).map(issue => report.league.name + ": " + issue));
  const stale = state.manual.filter(league => Date.now() - Date.parse(league.savedAt) > 24 * 3600000);
  if (stale.length) issues.push(stale.map(league => league.name).join(", ") + ": manual snapshot over 24 hours old");
  const olderWeek = state.manual.filter(league => activeWeek() && league.week !== activeWeek());
  if (olderWeek.length) issues.push(olderWeek.map(league => league.name).join(", ") + ": snapshot from a different week");
  main.append(node("h2", "", "What needs your attention"));
  const items = [...state.reports.flatMap(sleeperItems), ...state.manual.flatMap(manualItems)]
    .sort((a, b) => a.priority - b.priority);
  if (!items.length) main.append(add(node("section", "card clear"), node("span", "clear-mark", issues.length ? "△" : "✓"),
    add(node("div"), node("h3", "", issues.length ? "A few inputs need a check" : "No lineup change suggested"),
      node("p", "", issues.length ? "Review the data checks below before treating your lineup as settled." :
        "Nothing stands out in the data we have. Check injuries again before kickoff."))));
  else items.forEach(item => main.append(item.element));
  if (issues.length) {
    const details = node("details", "health-details");
    add(details, node("summary", "", "△ " + issues.length + " data check" + (issues.length === 1 ? "" : "s")),
      node("div", "notice", issues.join(" · ")));
    main.append(details);
  }
  add(main, node("h2", "section-head", "Your leagues"), leagueStrip());
}
function playerCell(player) {
  const cell = node("td");
  if (!player) return add(cell, node("span", "", "Empty"));
  add(cell, node("strong", "", player.name));
  add(cell, node("small", inactive(player) ? "injury" : "",
    [player.pos, player.team, player.injury, player.game_state === "bye" ? "BYE" : ""].filter(Boolean).join(" · ")));
  return cell;
}
function playerBlock(player) {
  const block = node("div");
  if (!player) return add(block, node("span", "player-name", "Empty slot"));
  add(block, node("span", "player-name", player.name),
    node("span", "player-meta" + (inactive(player) ? " injury" : ""),
      [player.pos, player.team, player.injury, player.game_state === "bye" ? "Bye" : null].filter(Boolean).join(" · ")));
  return block;
}
function projected(player) {
  if (!player) return "—";
  if (!player.sources && !(player.game_state === "post" && player.actual != null) && player.game_state !== "bye") return "Unknown";
  return number(player.value);
}
function renderSleeperLineup(main, report) {
  add(main, node("h2", "", report.team.name),
    node("p", "meta", report.league.name + " · Week " + report.league.week + " · " +
      (report.league.scoring_fingerprint.rec === 0.5 ? "Half PPR" :
       report.league.scoring_fingerprint.rec === 1 ? "PPR" : "League scoring")));
  const issues = quality(report);
  if (issues.length) main.append(node("div", "notice", issues.join(" · ") +
    ". Confirm uncertain recommendations in Sleeper."));
  const summary = node("section", "summary");
  const incomplete = reportGaps(report).length > 0;
  summary.append(add(node("div", "card"), node("strong", "metric", incomplete ? "Incomplete" :
    number(report.totals.current) + " → " + number(report.totals.recommended)),
    node("span", "caption", incomplete ? "Missing projections; totals withheld" : "Current → suggested points")));
  if (report.opponent && !incomplete) summary.append(add(node("div", "card"),
    node("strong", "metric", Math.round(report.opponent.win_prob_current * 100) + "% → " +
      Math.round(report.opponent.win_prob_recommended * 100) + "%"),
    node("span", "caption", "Win chance · model estimate")));
  main.append(summary);
  const list = node("section", "lineup-list");
  add(list, add(node("div", "lineup-head"), node("span", "", "Slot"), node("span", "", "Your lineup"),
    node("span", "", "Suggested lineup"), node("span", "", "Points")));
  for (const row of report.slots) {
    const item = node("article", "lineup-row" + (row.change ? " changed" : ""));
    add(item, node("span", "slot-chip", row.slot.replace("REC_FLEX", "W/TE")),
      playerBlock(row.current), playerBlock(row.recommended),
      add(node("div", "lineup-points"), node("span", "", projected(row.current) + " → " + projected(row.recommended)),
        node("small", "", row.locked ? "Locked" : "Projected")));
    add(item, node("div", "lineup-reason", row.locked ? "Game started · lineup locked" : row.reason));
    list.append(item);
  }
  main.append(list);
  main.append(add(node("div", "manual-buttons"), actionLink(report)));
  main.append(node("p", "meta", "Source: " + report.sources.projections.join(", ") +
    ". Point ranges and win chances are model estimates and have not been backtested."));
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
  const buttons = add(node("div", "manual-buttons"), update, remove);
  if (league.url) {
    try {
      const url = RosterImport.leagueUrl(league.url), link = node("a", "action", "Open in " + league.platform + " ↗");
      link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; buttons.prepend(link);
    } catch { /* Invalid older saved URL: omit its action link. */ }
  }
  main.append(buttons);
}
function render() {
  const main = $("content"); main.replaceChildren();
  $("connections-view").hidden = state.view !== "leagues";
  $("lineup-selector").hidden = state.view !== "lineup";
  const titles = {home: ["Your week, in view.", "The lineup decisions that deserve your attention."],
    leagues: ["All your leagues.", "Connect a platform, update a roster, or pick a lineup to review."],
    lineup: ["Your lineup.", "A clear view of what to keep, change, and check."]};
  $("page-title").textContent = titles[state.view][0];
  $("page-description").textContent = titles[state.view][1];
  $("season-context").textContent = "Football · " + (state.season || state.reports[0]?.league.season || new Date().getFullYear()) +
    (activeWeek() ? " · Week " + activeWeek() : " season");
  const hasData = state.reports.length || state.manual.length;
  if (state.view === "leagues") {
    if (hasData) main.append(leagueStrip());
  } else if (!hasData) {
    const empty = add(node("section", "empty"), node("h2", "", state.loading ? "Loading your leagues…" : "Bring your leagues together"),
      node("p", "", state.loading ? "Reading rosters, injuries, and projections. This can take a moment." :
        "Connect Sleeper, import ESPN, or add a CBS roster snapshot to get started."));
    if (!state.loading) {
      const button = node("button", "", "Add your first league");
      button.addEventListener("click", () => setView("leagues")); empty.append(button);
    }
    main.append(empty);
  } else if (state.view === "home") renderHome(main);
  else {
    const chosen = state.selected.startsWith("s:") ? state.reports.find(x => "s:" + x.league.id === state.selected) :
      state.manual.find(x => "m:" + x.id === state.selected);
    if (chosen?.schema) renderSleeperLineup(main, chosen);
    else if (chosen) renderManualLineup(main, chosen);
    else main.append(node("p", "meta", "Select a league to see its lineup."));
  }
  const fresh = $("freshness");
  fresh.hidden = state.view !== "lineup" || !state.selected.startsWith("s:") || !state.reports.length;
  if (!fresh.hidden) {
    fresh.classList.toggle("warn", state.reports.some(report => quality(report).length));
    fresh.textContent = (state.sample ? "Saved example · " : "Last read · ") +
      "Roster " + age(state.freshness?.roster_fetched_at) +
      " · Injury file " + age(state.freshness?.player_list_fetched_at);
  }
}
function setView(view) {
  if (!["home", "lineup", "leagues"].includes(view)) view = "home";
  state.view = view;
  for (const kind of ["home", "lineup", "leagues"]) {
    $(kind + "-tab").classList.toggle("active", kind === view);
    $(kind + "-tab").setAttribute("aria-pressed", String(kind === view));
  }
  if (location.hash !== "#" + view) history.replaceState(null, "", "#" + view);
  document.title = "Fantasy Sports · " + (view === "home" ? "Home" : view === "lineup" ? "Lineup" : "Leagues");
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
  state.loading = on;
  $("week").disabled = on;
  $("refresh").disabled = on || !state.sleeperIds.length;
  $("sample").disabled = on;
  $("connect-form").querySelector("button").disabled = on;
  $("refresh").textContent = on ? "Refreshing…" : "↻ Refresh";
  render();
}
async function getJson(url, options) {
  let response;
  try { response = await fetch(url, options); }
  catch { throw new Error("Couldn’t reach the dashboard. Check that the local server is running."); }
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}
async function findLeagues() {
  const username = $("username").value.trim();
  busy(true); status("Finding Sleeper fantasy leagues…");
  try {
    const data = await getJson("/api/leagues?username=" + encodeURIComponent(username));
    if (state.username !== username) { state.reports = []; state.freshness = null; }
    state.username = username;
    state.currentWeek = data.week; state.season = data.season;
    $("manual-week").value = activeWeek();
    state.sleeperIds = data.leagues.map(league => league.id);
    status(data.leagues.length ? data.leagues.length + " Sleeper fantasy league(s) found. Loading lineups…" :
      "No Sleeper fantasy leagues found for this season. Pick’em may need a separate connection.");
    if (state.sleeperIds.length) await refresh();
    else { busy(false); render(); }
  } catch (error) { busy(false); status(state.reports.length ?
    "Couldn’t refresh. Showing your last successful read with its original date." : error.message, true); }
}
async function refresh() {
  if (!state.sleeperIds.length) return;
  busy(true); status("Reading all Sleeper rosters, injuries, projections, and matchups…");
  try {
    const data = await getJson("/api/lineups", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: state.username, ...(state.week ? {week: state.week} : {})})});
    state.reports = data.reports; state.freshness = data.freshness;
    state.sample = false; state.lastRefresh = Date.now();
    populateLeagues();
    const selectedSleeper = state.selected.startsWith("s:") ? state.selected.slice(2) :
      (state.reports[0]?.league.id || "");
    localStorage.setItem("fantasy-sleeper-connection", JSON.stringify({username: state.username, leagueId: selectedSleeper}));
    localStorage.setItem("fantasy-last-lineups-v1", JSON.stringify({username: state.username,
      reports: state.reports, freshness: state.freshness}));
    status("Updated " + state.reports.length + " Sleeper league" + (state.reports.length === 1 ? "" : "s") + " · " + dateTime(data.reports[0].generated_at));
    render();
  } catch (error) { status(state.reports.length ? "Refresh failed. Showing your last successful read; check its age." : error.message, true); }
  finally { busy(false); }
}
function saveManual() { localStorage.setItem(manualKey, JSON.stringify(state.manual)); }
const parseStarters = RosterImport.parseRoster;
function previewRoster() {
  const preview = $("import-preview"); preview.replaceChildren(); preview.hidden = false;
  try {
    const rows = parseStarters($("manual-starters").value, $("manual-platform").value !== "Sleeper Pick’em");
    preview.append(node("p", "", rows.length ? rows.length + " roster rows · review names and statuses before saving" : "Pick’em league listing · picks are not imported"));
    rows.forEach(row => preview.append(add(node("div", "preview-row"), node("span", "", row.slot),
      node("strong", "", row.player), node("span", "", row.status))));
  } catch (error) { preview.append(node("p", "injury", error.message)); }
}
function editManual(league) {
  setView("leagues");
  state.editing = league.id;
  state.pendingImport = {bench: league.bench || [], source: league.source, teamName: league.teamName};
  $("manual-name").value = league.name;
  $("manual-platform").value = league.platform;
  $("manual-scoring").value = league.scoring;
  $("manual-week").value = league.week;
  $("manual-url").value = league.url || "";
  $("manual-starters").value = league.starters.map(row =>
    row.slot + " | " + row.player + " | " + row.status).join("\n");
  $("manual-starters").required = league.platform !== "Sleeper Pick’em";
  $("import-preview").hidden = true; $("manual-import").open = true;
  $("manual-import").scrollIntoView({behavior: "smooth"});
}
$("manual-form").addEventListener("submit", event => {
  event.preventDefault();
  try {
    const platform = $("manual-platform").value;
    const rows = parseStarters($("manual-starters").value, platform !== "Sleeper Pick’em");
    const isBench = row => /^(BN|BE|BENCH|IR|RESERVE)$/i.test(row.slot);
    const starters = rows.filter(row => !isBench(row));
    const pastedBench = rows.filter(isBench);
    if (platform !== "Sleeper Pick’em" && !starters.length) throw new Error("Include your starting lineup, not just the bench.");
    const league = {id: state.editing || crypto.randomUUID(), name: $("manual-name").value.trim(),
      platform, scoring: $("manual-scoring").value.trim(), week: Number($("manual-week").value),
      url: RosterImport.leagueUrl($("manual-url").value),
      starters, savedAt: new Date().toISOString(),
      ...(state.pendingImport || {}), bench: pastedBench.length ? pastedBench : state.pendingImport?.bench || []};
    if (!league.name || !Number.isInteger(league.week) || league.week < 1 || league.week > 18)
      throw new Error("Enter a league name and week 1–18.");
    if (state.editing) state.manual = state.manual.map(item => item.id === state.editing ? league : item);
    else state.manual.push(league);
    saveManual(); state.selected = "m:" + league.id; populateLeagues();
    state.editing = null; state.pendingImport = null; $("manual-form").reset();
    $("manual-starters").required = true; $("import-preview").hidden = true;
    $("manual-import").open = false;
    status(league.name + " saved in this browser at " + dateTime(league.savedAt) + ".");
    setView("home");
  } catch (error) { status(error.message, true); }
});
$("manual-cancel").addEventListener("click", () => {
  state.editing = null; state.pendingImport = null; $("manual-form").reset();
  $("manual-starters").required = true; $("import-preview").hidden = true; $("manual-import").open = false;
});
$("manual-platform").addEventListener("change", () => {
  $("manual-starters").required = $("manual-platform").value !== "Sleeper Pick’em";
});
$("espn-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = $("espn-connect"), note = $("espn-status");
  button.disabled = true; note.textContent = "Reading the public ESPN roster…";
  try {
    const params = new URLSearchParams({url: $("espn-url").value});
    if ($("espn-team").value) params.set("team_id", $("espn-team").value);
    const data = await getJson("/api/espn?" + params);
    if (data.needs_team) {
      note.textContent = "Enter your team number: " + data.teams.map(team => team.id + " = " + team.name).join("; ");
      return;
    }
    const snapshot = data.snapshot;
    const existing = state.manual.find(league => league.platform === "ESPN" && league.url === snapshot.url);
    editManual({...snapshot, id: existing?.id || null});
    state.pendingImport = {bench: snapshot.bench, source: snapshot.source, teamName: snapshot.teamName};
    previewRoster();
    note.textContent = "Read " + snapshot.teamName + ". Review the roster below, then save it.";
  } catch (error) { note.textContent = error.message; }
  finally { button.disabled = false; }
});
$("connect-form").addEventListener("submit", event => { event.preventDefault(); findLeagues(); });
$("league").addEventListener("change", () => selectLeague($("league").value));
$("refresh").addEventListener("click", refresh);
$("sample").addEventListener("click", async () => {
  try {
    const data = await getJson("/api/sample");
    state.reports = [data.report]; state.freshness = data.freshness; state.sample = true;
    populateLeagues(); status("Showing a saved week-3 injury scenario. Nothing here is live."); setView("home");
  } catch (error) { status(error.message, true); }
});
$("home-tab").addEventListener("click", () => setView("home"));
$("leagues-tab").addEventListener("click", () => setView("leagues"));
$("lineup-tab").addEventListener("click", () => setView("lineup"));
$("manage-leagues").addEventListener("click", () => setView("leagues"));
$("preview-import").addEventListener("click", previewRoster);
$("week").addEventListener("change", () => { state.week = Number($("week").value) || null;
  render(); if (state.sleeperIds.length) refresh(); });
window.addEventListener("hashchange", () => setView(location.hash.slice(1)));
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.reports.length && !state.sample &&
      Date.now() - state.lastRefresh > 60000) refresh();
});
$("username").value = state.username;
$("manual-week").value = activeWeek() || 1;
for (let week = 1; week <= 18; week++) { const option = node("option", "", week); option.value = week; $("week").append(option); }
state.sleeperIds = state.reports.map(report => report.league.id);
populateLeagues(); setView(location.hash.slice(1) || "home"); findLeagues();
