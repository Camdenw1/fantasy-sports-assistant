const $ = id => document.getElementById(id);
const saved = JSON.parse(localStorage.getItem("fantasy-sleeper-connection") || "{}");
const state = { username: saved.username || "camdenw1", leagueId: saved.leagueId || "",
  report: null, freshness: null, sample: false, view: "home", lastRefresh: 0 };

function node(tag, className, content) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (content != null) item.textContent = String(content);
  return item;
}
function add(parent, ...children) { children.forEach(child => parent.append(child)); return parent; }
function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}
function age(iso) {
  if (!iso) return "unknown age";
  const minutes = Math.max(0, Math.floor((Date.now() - Date.parse(iso)) / 60000));
  if (!Number.isFinite(minutes)) return "unknown age";
  if (minutes < 1) return "just now";
  if (minutes < 60) return minutes + "m ago";
  if (minutes < 1440) return Math.floor(minutes / 60) + "h ago";
  return Math.floor(minutes / 1440) + "d ago";
}
function number(value, digits = 1) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}
function dateTime(iso) {
  if (!iso) return "Time unknown";
  const date = new Date(iso);
  return Number.isNaN(date.valueOf()) ? "Time unknown" : date.toLocaleString([], {
    weekday: "short", hour: "numeric", minute: "2-digit", timeZoneName: "short"
  });
}
function inactive(player) {
  return player && ["Out", "IR", "PUP", "Sus", "NA", "DNR", "COV"].includes(player.injury);
}
function needsCaution() {
  if (!state.report) return true;
  if (state.sample) return true;
  const injuryAge = Date.now() - Date.parse(state.freshness.player_list_fetched_at || "");
  const rosterAge = Date.now() - Date.parse(state.freshness.roster_fetched_at || "");
  const soon = state.report.slots.some(row => {
    const kickoff = row.current && row.current.kickoff;
    return kickoff && Date.parse(kickoff) > Date.now() && Date.parse(kickoff) - Date.now() < 4 * 3600000;
  });
  const limit = soon ? 2 * 3600000 : 24 * 3600000;
  return !Number.isFinite(injuryAge) || injuryAge > limit ||
    !Number.isFinite(rosterAge) || rosterAge > limit ||
    state.report.sources.schedule !== "espn scoreboard" ||
    !!(state.report.sources.projection_gaps || []).length;
}
function actionLink(text) {
  if (state.sample) return node("span", "meta", "Historical example · no action");
  const link = node("a", "action", text);
  link.href = state.report.apply.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}
function card(label, title, body, kind) {
  const item = node("article", "card action-card " + kind);
  add(item, node("span", "pill", label), node("h3", "", title), node("p", "", body),
      actionLink("Open in Sleeper ↗"));
  return item;
}
function actions() {
  const report = state.report;
  const items = [];
  const caution = needsCaution();
  const changed = report.slots.filter(row => row.change && !row.locked);
  const forcedRows = report.slots.filter(row => !row.locked &&
    (!row.current || row.current.game_state === "bye" || inactive(row.current)));
  for (const row of report.slots) {
    if (row.locked) continue;
    const current = row.current, recommended = row.recommended;
    const forced = !current || current.game_state === "bye" || inactive(current);
    if (forced) {
      const cause = !current ? "empty" : current.game_state === "bye" ? "on bye" :
        current.injury;
      const name = current ? current.name : row.slot;
      const plan = changed.map(change => change.slot + " → " +
        (change.recommended ? change.recommended.name : "empty")).join("; ");
      items.push({priority: 0, element: card("Fix lineup", "Replace " + name,
        name + " is " + cause + ". " + (recommended ? "Recommended lineup changes: " + plan + "." :
          "No legal rostered replacement; check waivers."), "urgent")});
    }
  }
  for (const swap of report.swaps) {
    const old = report.slots.find(row => row.current && row.current.id === swap.out);
    if (old && (!old.current || old.current.game_state === "bye" || inactive(old.current))) continue;
    if (swap.delta < 1.5) continue;
    items.push({priority: 1, element: card("Lineup upgrade",
      "Start " + swap.in_name + " over " + (swap.out_name || "an empty slot"),
      swap.reason + " · " + swap.slot + " · +" + number(swap.delta) + " projected points.",
      caution ? "check" : "")});
  }
  for (const alert of report.alerts) {
    if (alert.type !== "gtd_recheck") continue;
    items.push({priority: 2, element: card("Recheck injury",
      alert.message, "Check the official inactive list before kickoff. Suggested check: " +
      dateTime(alert.at) + ".", "check")});
  }
  for (const row of report.slots) {
    if (row.locked || row.action !== "move" || !row.recommended) continue;
    if (forcedRows.length || report.swaps.some(swap => swap.in === row.recommended.id)) continue;
    items.push({priority: 3, element: card("Flex placement", "Move " + row.recommended.name +
      " to " + row.slot, row.reason, "check")});
  }
  return items.sort((a, b) => a.priority - b.priority).map(item => item.element);
}
function summaryCard(value, caption) {
  return add(node("div", "card"), node("strong", "metric", value), node("span", "caption", caption));
}
function renderHome() {
  const report = state.report, main = $("content");
  const summary = node("section", "summary");
  add(summary, summaryCard(report.league.name, "Sleeper · Week " + report.league.week),
    summaryCard(number(report.totals.current) + " → " + number(report.totals.recommended),
      "Current → recommended points"),
    summaryCard(report.opponent ?
      Math.round(report.opponent.win_prob_current * 100) + "% → " +
      Math.round(report.opponent.win_prob_recommended * 100) + "%" : "—",
      "Matchup win chance · model estimate"));
  main.append(summary);
  const list = actions();
  main.append(node("h2", "section-head", "What needs attention"));
  if (needsCaution()) main.append(node("div", "notice",
    state.sample ? "Saved week-3 example. This is historical data; no action is current." :
    "Some inputs are stale, missing projections, or have no verified kickoff time. Verify in Sleeper before acting."));
  const gaps = report.sources.projection_gaps || [];
  if (gaps.length) main.append(node("p", "meta", "No projected stat line for: " +
    gaps.map(player => player.name).join(", ") + ". Their estimated points are incomplete."));
  if (!list.length) {
    main.append(add(node("section", "card clear"), node("h3", "", "No lineup change suggested"),
      node("p", "", "This is based on the roster and projections shown below. Recheck injuries before the next kickoff.")));
  } else list.forEach(item => main.append(item));
  main.append(add(node("p", "meta"),
    document.createTextNode("Projection feeds: " +
      (report.sources.projections.length ? report.sources.projections.join(", ") : "unavailable") +
      " · Player file downloaded: " + age(state.freshness.player_list_fetched_at) +
      " · Schedule: " + report.sources.schedule +
      " · Upstream projection update time is not provided.")));
}
function playerCell(player) {
  const cell = node("td");
  if (!player) return add(cell, node("span", "", "Empty"));
  add(cell, node("strong", "", player.name));
  const details = [player.pos, player.team, player.injury || "", player.game_state === "bye" ?
    "BYE" : ""].filter(Boolean).join(" · ");
  add(cell, node("small", inactive(player) ? "injury" : "", details));
  return cell;
}
function renderLineup() {
  const report = state.report, main = $("content");
  add(main, node("h2", "section-head", report.team.name + " · Week " + report.league.week),
    node("p", "meta", "Current lineup versus the league-scored recommendation. Locked players stay in place."));
  const table = node("table", "lineup-table");
  const header = node("tr");
  ["Slot", "Current", "Recommended", "Projected", "Why"].forEach(label =>
    header.append(node("th", "", label)));
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
  table.append(body);
  main.append(table);
  main.append(add(node("p", "meta"), actionLink("Open team in Sleeper ↗")));
}
function render() {
  const main = $("content");
  main.replaceChildren();
  if (!state.report) {
    main.append(add(node("section", "empty"), node("h2", "", "Start with one league"),
      node("p", "", "Find your Sleeper leagues or view the saved example.")));
    $("freshness").hidden = true;
    return;
  }
  const fresh = $("freshness");
  fresh.hidden = false;
  fresh.classList.toggle("warn", needsCaution());
  fresh.textContent = (state.sample ? "SAVED EXAMPLE · " : "FETCHED · ") +
    "Roster " + age(state.freshness.roster_fetched_at) +
    " · Player/injury file " + age(state.freshness.player_list_fetched_at) +
    " · Projection feed " + age(state.freshness.projections_fetched_at);
  if (state.view === "home") renderHome(); else renderLineup();
}
function busy(on) {
  $("refresh").disabled = on || !$("league").value;
  $("sample").disabled = on;
  $("connect-form").querySelector("button").disabled = on;
}
async function getJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}
async function findLeagues() {
  const username = $("username").value.trim();
  busy(true); status("Finding Sleeper leagues…");
  try {
    const data = await getJson("/api/leagues?username=" + encodeURIComponent(username));
    const select = $("league");
    select.replaceChildren();
    data.leagues.forEach(league => {
      const option = node("option", "", league.name + " · " + league.status);
      option.value = league.id;
      select.append(option);
    });
    select.disabled = !data.leagues.length;
    if (state.leagueId && data.leagues.some(league => league.id === state.leagueId))
      select.value = state.leagueId;
    state.username = username;
    state.leagueId = select.value;
    status(data.leagues.length ? data.leagues.length + " leagues found for " + data.username +
      ". Choose one and refresh." : "No Sleeper leagues found for this season.");
    busy(false);
  } catch (error) { busy(false); status(error.message, true); }
}
async function refresh() {
  const leagueId = $("league").value;
  if (!leagueId) return;
  busy(true); status("Reading roster, injuries, projections, and matchup…");
  try {
    const data = await getJson("/api/lineup", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: state.username, league_id: leagueId})});
    state.report = data.report; state.freshness = data.freshness;
    state.sample = false; state.leagueId = leagueId; state.lastRefresh = Date.now();
    localStorage.setItem("fantasy-sleeper-connection",
      JSON.stringify({username: state.username, leagueId: state.leagueId}));
    status("Updated " + dateTime(data.report.generated_at) + ". Read-only: make changes in Sleeper.");
    render();
  } catch (error) { status(error.message, true); }
  finally { busy(false); }
}
function setView(view) {
  state.view = view;
  for (const kind of ["home", "lineup"]) {
    $(kind + "-tab").classList.toggle("active", kind === view);
    $(kind + "-tab").setAttribute("aria-pressed", kind === view ? "true" : "false");
  }
  render();
}
$("connect-form").addEventListener("submit", event => { event.preventDefault(); findLeagues(); });
$("league").addEventListener("change", () => { state.leagueId = $("league").value; refresh(); });
$("refresh").addEventListener("click", refresh);
$("sample").addEventListener("click", async () => {
  try {
    const data = await getJson("/api/sample");
    state.report = data.report; state.freshness = data.freshness; state.sample = true;
    status("Showing a saved week-3 injury scenario. Nothing here is live.");
    render();
  } catch (error) { status(error.message, true); }
});
$("home-tab").addEventListener("click", () => setView("home"));
$("lineup-tab").addEventListener("click", () => setView("lineup"));
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.report && !state.sample && Date.now() - state.lastRefresh > 60000)
    refresh();
});
$("username").value = state.username;
findLeagues();
