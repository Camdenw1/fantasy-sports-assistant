const byId = id => document.getElementById(id);
const cachePrefix = 'fantasy-ros-projections-v3:';
let data = null, position = 'FLEX', loading = false, ownership = 'all', sequence = 0, profile = 'standard', username = '', refreshFailed = false;
try { username = JSON.parse(localStorage.getItem('fantasy-sleeper-connection'))?.username || ''; } catch {}
function cacheKey() { return cachePrefix + profile + (profile.startsWith('league:') ? ':' + username.toLowerCase() : ''); }
function valid(value) {
  return value && Number.isInteger(value.season) && Number.isInteger(value.start_week) &&
    value.start_week >= 1 && value.end_week === 17 && value.start_week <= 17 &&
    Number.isFinite(Date.parse(value.fetched_at)) && Array.isArray(value.players) && value.players.length > 0 &&
    value.players.every(p => p && typeof p.name === 'string' && ['QB','RB','WR','TE'].includes(p.position) &&
      Number.isFinite(p.points) && Number.isFinite(p.per_game) && Number.isInteger(p.games) && p.games > 0);
}
function loadSaved() { data=null; try { const saved=JSON.parse(localStorage.getItem(cacheKey())); if (valid(saved)) data=saved; } catch {} }
try { const savedProfile=localStorage.getItem('fantasy-player-profile'); if (['standard','camden','dad'].includes(savedProfile)) {profile=savedProfile;byId('season-profile').value=profile;} } catch {}
loadSaved();
const SCHEDULE = ['Hard','Tough','Neutral','Good','Easy'];
const INJURY = {Questionable:'Q',Doubtful:'D',Out:'Out',IR:'IR',PUP:'PUP',Sus:'Sus',NA:'NA'};
function poolOf(p) { return position === 'FLEX' ? 'FLEX' : p.position; }
function el(tag, cls, text) { const e = document.createElement(tag); e.className = cls || ''; if (text != null) e.textContent = text; return e; }
function render() {
  const body = byId('season-rows'); body.replaceChildren();
  byId('season-empty').hidden = true;
  byId('season-decisions').hidden = true;
  byId('season-ownership').disabled = !data?.roster;
  if (!data) { byId('season-scoring-label').textContent = byId('season-profile').selectedOptions[0]?.textContent || 'Half PPR'; return; }
  byId('season-scoring-label').textContent = (data.profile?.label || 'Half PPR') + (position === 'FLEX' && data.replacement ? ' · Flex by starter value' : ' · Projected points');
  renderDecisions();
  byId('season-label').textContent = `Football · ${data.season} · Weeks ${data.start_week}–${data.end_week}`;
  const query = byId('player-search').value.trim().toLowerCase();
  const pool = data.players.filter(p => position === 'FLEX' ? p.position !== 'QB' : p.position === position).sort((a,b)=>(a.ranks?.[position] || 9999)-(b.ranks?.[position] || 9999));
  let tier = null;
  pool.forEach((p, index) => {
    if (!(p.name + ' ' + p.team).toLowerCase().includes(query) || (ownership !== 'all' && p.ownership !== ownership)) return;
    const key = poolOf(p), rank = p.ranks?.[key] ?? index + 1, pTier = p.tiers?.[key];
    if (!query && ownership === 'all' && pTier != null && pTier !== tier) {
      tier = pTier;
      const divider = el('tr','season-tier'), label = el('th','',`Tier ${tier}`);
      label.colSpan = 8; label.scope = 'rowgroup'; divider.append(label); body.append(divider);
    }
    const row = el('tr',p.ownership === 'mine' ? 'season-owned' : ''); row.append(el('td','season-rank',rank));
    const cell = el('td'), identity = el('div','player-identity');
    const aliases = {JAC:'JAX',WAS:'WSH',LA:'LAR',ARZ:'ARI'};
    const team = aliases[p.team] || p.team;
    const teams = 'ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WSH'.split(' ');
    if (teams.includes(team)) { const logo = el('img','team-logo'); logo.src = '/assets/teams/' + team.toLowerCase() + '.png'; logo.alt = ''; logo.width=34; logo.height=34; logo.loading='lazy'; logo.onerror=()=>logo.hidden=true; identity.append(logo); }
    const posRank = p.ranks?.[p.position] ? p.position + p.ranks[p.position] : p.position;
    const meta = el('div','player-meta',[team,posRank].filter(Boolean).join(' · '));
    if (p.injury) { const badge = el('span','injury-badge',INJURY[p.injury] || p.injury); badge.title = p.injury; badge.setAttribute('aria-label', 'Injury status: ' + p.injury); meta.append(' ', badge); }
    if (p.ownership === 'mine') {const badge=el('span','ownership-badge','My team');meta.append(' ',badge);}
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
  byId('season-source').textContent = (data.scoring_notes || []).join(' · ') + ((data.scoring_notes || []).length ? '. ' : '') + `Source: Sleeper (${(data.providers || []).join(', ')}). Read ${new Date(data.fetched_at).toLocaleString()}. ${data.source_updated_at ? 'Oldest provider revision: ' + new Date(data.source_updated_at).toLocaleString() + '.' : 'Provider revision date unavailable.'}`;
}
function note(message) { byId('season-status').textContent = message; }
function warning(message) { byId('season-warning').textContent = message; byId('season-warning').hidden = !message; }
async function read(url) {
  const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),15000);
  try { const response = await fetch(url,{signal:controller.signal}); if (!response.ok) throw Error('Unavailable'); return await response.json(); } finally {clearTimeout(timer);}
}
async function refresh(force=false) {
  const request = ++sequence;
  const params = new URLSearchParams({profile: profile.startsWith('league:') ? 'league' : profile});
  if (profile.startsWith('league:')) {params.set('league_id',profile.slice(7));params.set('username',username);}
  loading=true; refreshFailed=false; if(data?.roster)renderDecisions(); byId('season-refresh').disabled=true; note(data ? 'Saved rankings · updating…' : 'Reading remaining weeks…');
  try {
    let result = await read('/api/season?' + params + '&start=1' + (force ? '&force=1' : ''));
    if (request !== sequence) return;
    const deadline = Date.now()+90000;
    while (true) {
      const candidate = result.data?.reports?.[0];
      if (valid(candidate)) { data=candidate; render(); try {localStorage.setItem(cacheKey(),JSON.stringify(data));} catch {} }
      if (result.status !== 'refreshing') break;
      if (Date.now()>deadline) throw Error('Timed out');
      await new Promise(resolve=>setTimeout(resolve,1000)); result=await read('/api/season?' + params);
      if (request !== sequence) return;
    }
    if (result.status !== 'ready' || !data) throw Error(result.error || 'Current projections could not be loaded');
    const age = Date.now() - Date.parse(data.fetched_at);
    warning([...(data.health?.issues || []), ...(age > 86400000 ? ['Saved projections are more than a day old. Refresh before making a decision.'] : [])].join(' · '));
    note('Projections ' + (data.source_updated_at ? new Date(data.source_updated_at).toLocaleDateString([], {month:'short',day:'numeric'}) : 'date unknown') + ' · Read ' + new Date(data.fetched_at).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}));
  } catch (error) { if (request !== sequence) return; refreshFailed=true; note(data ? 'Saved rankings · refresh unavailable' : 'Projections unavailable'); warning(data ? 'Showing the last successful projection snapshot. Its source dates are listed below.' : error.message + '. Try refreshing shortly.'); }
  finally {if(request === sequence){loading=false;byId('season-refresh').disabled=false;render();}}
}
document.querySelectorAll('[data-position]').forEach(button=>button.addEventListener('click',()=>{
  position=button.dataset.position; document.querySelectorAll('[data-position]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();
}));
byId('player-search').addEventListener('input',render);byId('season-refresh').addEventListener('click',()=>refresh(true));
render();refresh();loadLeagues();
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});


function decisionIssues() {
  const issues=[...(data?.roster?.issues || [])];
  if (refreshFailed) issues.push('Refresh unavailable; refresh successfully before acting');
  if (data?.roster && Date.now()-Date.parse(data.roster.fetched_at)>30*60000) issues.push('Ownership snapshot is over 30 minutes old; refresh before acting');
  if (data && Date.now()-Date.parse(data.fetched_at)>86400000) issues.push('Projection read needs refresh');
  if (data && (!data.source_updated_at || Date.now()-Date.parse(data.source_updated_at)>72*3600000)) issues.push('Provider projections need a newer revision');
  return [...new Set(issues)];
}
function renderDecisions() {
  const area=byId('season-decisions');area.replaceChildren();
  if (!data.roster) return;
  area.hidden=false;
  area.append(el('h2','','Roster outlook'));
  const issues=decisionIssues();
  if (loading || issues.length) {
    area.append(el('p','meta',loading ? 'Updating ownership and scoring. Suggestions resume after a complete refresh.' : 'Suggestions paused · '+issues.join(' · ')));
    if (data.roster.missing?.length) area.append(el('p','meta','No projection: '+data.roster.missing.map(p=>p.name).join(', ')));
    area.append(el('p','meta','Ownership read '+new Date(data.roster.fetched_at).toLocaleString()));
    return;
  }
  const indexed=new Map(data.players.map(p=>[p.id,p]));
  const keep=(data.roster.keepers || []).map(id=>indexed.get(id)?.name).filter(Boolean);
  if (keep.length) area.append(el('p','meta','Projected core · '+keep.join(', ')));
  for (const advice of data.roster.suggestions || []) {
    const pickup=indexed.get(advice.pickup),drop=indexed.get(advice.drop);if(!pickup || !drop)continue;
    const card=el('div','season-advice');
    card.append(el('strong','',`Consider ${pickup.name} over ${drop.name}`),el('p','meta',`${advice.reason} · +${advice.projection_edge.toFixed(1)} ROS points at ${pickup.position}${advice.starter_gain>0 ? ' · +'+advice.starter_gain.toFixed(1)+' projected starter points' : ''}. Check news and waiver rules before making a move.`));area.append(card);
  }
  if (!data.roster.suggestions?.length) area.append(el('p','meta','No clear same-position bench upgrade among the highest-projected available players. Keep your core; review injuries and bye needs in your league app.'));
  area.append(el('p','meta','Ownership read '+new Date(data.roster.fetched_at).toLocaleString()));
}
byId('season-profile').addEventListener('change',()=>{
  profile=byId('season-profile').value;ownership='all';byId('season-ownership').value='all';
  try{localStorage.setItem('fantasy-player-profile',profile);}catch{}
  loadSaved();warning('');render();refresh();
});
byId('season-ownership').addEventListener('change',()=>{ownership=byId('season-ownership').value;render();});
async function loadLeagues() {
  const hint=byId('league-connect-note');
  if (!username) {hint.textContent='Connect Sleeper in Leagues for ownership and waiver views.';return;}
  const params=new URLSearchParams({username});
  try {
    let result=await read('/api/player-leagues?'+params+'&start=1');const deadline=Date.now()+60000;
    while(result.status==='refreshing') {
      if(Date.now()>deadline)throw Error('Timed out');
      await new Promise(resolve=>setTimeout(resolve,1000));result=await read('/api/player-leagues?'+params);
    }
    const leagues=result.data?.reports?.[0]?.leagues;
    if(result.status!=='ready' || !Array.isArray(leagues))throw Error('Unavailable');
    for(const league of leagues) {const option=el('option','',league.name+' · Sleeper');option.value='league:'+league.id;byId('season-profile').append(option);}
    hint.textContent='';
    let selected=null;try {selected=localStorage.getItem('fantasy-player-profile'); const connection=JSON.parse(localStorage.getItem('fantasy-sleeper-connection')); if(connection?.leagueId && !localStorage.getItem('fantasy-ownership-default:'+username.toLowerCase())) {const ownedLeague=leagues.find(l=>l.id===connection.leagueId) || leagues[0];if(ownedLeague){selected='league:'+ownedLeague.id;localStorage.setItem('fantasy-player-profile',selected);localStorage.setItem('fantasy-ownership-default:'+username.toLowerCase(),'1');}}}catch{}
    if (selected && [...byId('season-profile').options].some(o=>o.value===selected) && selected!==profile) {
      profile=selected;byId('season-profile').value=profile;loadSaved();render();refresh();
    }
  } catch {hint.textContent='League lookup unavailable. General scoring profiles still work; reconnect in Leagues.';}
}
// Freshness ages while the page is open; never leave old advice actionable.
setInterval(()=>{if(data?.roster && !loading)refresh();},5*60000);
setInterval(()=>{if(data?.roster)renderDecisions();},60000);
