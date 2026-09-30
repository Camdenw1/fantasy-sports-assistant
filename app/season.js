const byId = id => document.getElementById(id);
const cacheKey = 'fantasy-ros-projections-v2';
let data = null, position = 'FLEX', loading = false;
function valid(value) {
  return value && Number.isInteger(value.season) && Number.isInteger(value.start_week) &&
    value.start_week >= 1 && value.end_week === 17 && value.start_week <= 17 &&
    Number.isFinite(Date.parse(value.fetched_at)) && Array.isArray(value.players) && value.players.length > 0 &&
    value.players.every(p => p && typeof p.name === 'string' && ['QB','RB','WR','TE'].includes(p.position) &&
      Number.isFinite(p.points) && Number.isFinite(p.per_game) && Number.isInteger(p.games) && p.games > 0);
}
try { const saved = JSON.parse(localStorage.getItem(cacheKey)); if (valid(saved)) data = saved; } catch {}
const SCHEDULE = ['Hard','Tough','Neutral','Good','Easy'];
const INJURY = {Questionable:'Q',Doubtful:'D',Out:'Out',IR:'IR',PUP:'PUP',Sus:'Sus',NA:'NA'};
function poolOf(p) { return position === 'FLEX' ? 'FLEX' : p.position; }
function el(tag, cls, text) { const e = document.createElement(tag); e.className = cls || ''; if (text != null) e.textContent = text; return e; }
function render() {
  const body = byId('season-rows'); body.replaceChildren();
  if (!data) return;
  byId('season-label').textContent = `Football · ${data.season} · Weeks ${data.start_week}–${data.end_week}`;
  const query = byId('player-search').value.trim().toLowerCase();
  const pool = data.players.filter(p => position === 'FLEX' ? p.position !== 'QB' : p.position === position);
  let tier = null;
  pool.forEach((p, index) => {
    if (!(p.name + ' ' + p.team).toLowerCase().includes(query)) return;
    const key = poolOf(p), rank = p.ranks?.[key] ?? index + 1, pTier = p.tiers?.[key];
    if (!query && pTier != null && pTier !== tier) {
      tier = pTier;
      const divider = el('tr','season-tier'), label = el('th','',`Tier ${tier}`);
      label.colSpan = 8; label.scope = 'rowgroup'; divider.append(label); body.append(divider);
    }
    const row = el('tr'); row.append(el('td','season-rank',rank));
    const cell = el('td'), identity = el('div','player-identity');
    const aliases = {JAC:'JAX',WAS:'WSH',LA:'LAR',ARZ:'ARI'};
    const team = aliases[p.team] || p.team;
    const teams = 'ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WSH'.split(' ');
    if (teams.includes(team)) { const logo = el('img','team-logo'); logo.src = '/assets/teams/' + team.toLowerCase() + '.png'; logo.alt = ''; logo.width=34; logo.height=34; logo.loading='lazy'; logo.onerror=()=>logo.hidden=true; identity.append(logo); }
    const posRank = p.ranks?.[p.position] ? p.position + p.ranks[p.position] : p.position;
    const meta = el('div','player-meta',[team,posRank].filter(Boolean).join(' · '));
    if (p.injury) { const badge = el('span','injury-badge',INJURY[p.injury] || p.injury); badge.title = p.injury; badge.setAttribute('aria-label', 'Injury status: ' + p.injury); meta.append(' ', badge); }
    const copy = el('div','player-copy'); copy.append(el('span','player-name',p.name),meta);
    identity.append(copy); cell.append(identity);
    const sched = el('td','season-sched', p.schedule ? SCHEDULE[p.schedule - 1] : '–');
    if (p.schedule) { sched.dataset.level = p.schedule; const opp = Object.entries(p.opponents || {}).map(([w,o]) => `Wk ${w} ${o}`).join(', '); sched.title = `${p.schedule_allowed} pts/game allowed to ${p.position}s on average · ${opp}`; }
    const delta = p.moved?.[key], move = el('td','season-move', delta ? (delta > 0 ? '▲' : '▼') + Math.abs(delta) : (delta === 0 ? '–' : ''));
    if (delta) { move.dataset.dir = delta > 0 ? 'up' : 'down'; move.setAttribute('aria-label', `${delta > 0 ? 'Up' : 'Down'} ${Math.abs(delta)} since ${data.movement_since}`); move.title = `Since ${data.movement_since}`; }
    row.append(cell,el('td','season-total',p.points.toFixed(1)),el('td','season-pg',p.per_game.toFixed(1)),sched,move,el('td','season-bye',p.bye ?? ''),el('td','season-games',p.games)); body.append(row);
  });
  const early = (data.schedule_weeks || []).length;
  byId('season-sched-note').textContent = early ? `Based on Weeks ${data.schedule_weeks[0]}–${data.schedule_weeks[early-1]}${early < 5 ? ', an early and noisy sample' : ''}.` : 'Unavailable for this snapshot.';
  byId('season-empty').hidden = body.querySelector('tr:not(.season-tier)') !== null;
  byId('season-source').textContent = `Source: Sleeper (${(data.providers || []).join(', ')}). Read ${new Date(data.fetched_at).toLocaleString()}. ${data.source_updated_at ? 'Oldest provider revision: ' + new Date(data.source_updated_at).toLocaleString() + '.' : 'Provider revision date unavailable.'}`;
}
function note(message) { byId('season-status').textContent = message; }
function warning(message) { byId('season-warning').textContent = message; byId('season-warning').hidden = !message; }
async function read(url) {
  const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),15000);
  try { const response = await fetch(url,{signal:controller.signal}); if (!response.ok) throw Error('Unavailable'); return await response.json(); } finally {clearTimeout(timer);}
}
async function refresh(force=false) {
  if (loading) return;
  loading=true; byId('season-refresh').disabled=true; note(data ? 'Saved rankings · updating…' : 'Reading remaining weeks…');
  try {
    let result = await read('/api/season?start=1' + (force ? '&force=1' : ''));
    const deadline = Date.now()+90000;
    while (true) {
      const candidate = result.data?.reports?.[0];
      if (valid(candidate)) { data=candidate; render(); try {localStorage.setItem(cacheKey,JSON.stringify(data));} catch {} }
      if (result.status !== 'refreshing') break;
      if (Date.now()>deadline) throw Error('Timed out');
      await new Promise(resolve=>setTimeout(resolve,1000)); result=await read('/api/season');
    }
    if (result.status !== 'ready' || !data) throw Error('Unavailable');
    const age = Date.now() - Date.parse(data.fetched_at);
    warning(age > 86400000 ? 'Saved projections are more than a day old. Refresh before making a decision.' : '');
    note('Projections ' + (data.source_updated_at ? new Date(data.source_updated_at).toLocaleDateString([], {month:'short',day:'numeric'}) : 'date unknown') + ' · Read ' + new Date(data.fetched_at).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}));
  } catch { note(data ? 'Saved rankings · refresh unavailable' : 'Projections unavailable'); warning(data ? 'Showing the last successful projection snapshot. Its source dates are listed below.' : 'Current projections could not be loaded. Try refreshing shortly.'); }
  finally {loading=false;byId('season-refresh').disabled=false;}
}
document.querySelectorAll('[data-position]').forEach(button=>button.addEventListener('click',()=>{
  position=button.dataset.position; document.querySelectorAll('[data-position]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();
}));
byId('player-search').addEventListener('input',render);byId('season-refresh').addEventListener('click',()=>refresh(true));
render();refresh();
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
