"""Current ROS projection rankings, independent of the frozen draft pipeline."""
import datetime as dt
import json
import math
import pathlib
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from season_scoring import CAMDEN, SLOTS, STANDARD, weekly_score
from season_rosters import context as league_context, apply as apply_roster
import season_espn

POSITIONS = {'QB', 'RB', 'WR', 'TE'}
# Kickers and defenses rank on standard K/DST scoring; league custom rules cover skill players.
SPECIAL = {'K', 'DEF'}
RANKED = POSITIONS | SPECIAL
FLEX = {'RB', 'WR', 'TE'}
POOLS = ('FLEX', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF')
SCHEDULE_LABELS = ('Hard', 'Tough', 'Neutral', 'Good', 'Easy')
NEAR_WEEKS = 3
MOVE_MIN_DAYS = 5      # compare against a snapshot at least this old
HISTORY_DAYS = 60


def aggregate(weekly, season, start, end=17, settings=None, dad=False):
    players = {}
    providers = set()
    source_times = []
    for week in range(start, end + 1):
        rows = weekly.get(week)
        if not isinstance(rows, list):
            raise ValueError(f'Week {week} projections unavailable')
        eligible = {}
        for row in rows:
            pl = row.get('player') or {}
            stats = row.get('stats') or {}
            points = stats.get('pts_half_ppr')
            # ADP-only placeholder records are not projections. Never treat them as zero.
            if (pl.get('position') not in RANKED or not row.get('player_id')
                    or isinstance(points, bool) or not isinstance(points, (int, float))
                    or not math.isfinite(points) or float(stats.get('gp') or 0) <= 0):
                continue
            if str(row.get('season')) != str(season) or row.get('week') != week:
                raise ValueError('Projection season/week mismatch')
            pid = str(row['player_id'])
            # Prefer latest provider revision; each player counts at most once/week.
            previous = eligible.get(pid)
            if previous is None or (row.get('last_modified') or 0) > (previous.get('last_modified') or 0):
                eligible[pid] = row
        if len(eligible) < 150:
            raise ValueError(f'Week {week} projection coverage is incomplete')
        for pid, row in eligible.items():
            pl, stats = row['player'], row['stats']
            name = ' '.join(filter(None, [pl.get('first_name'), pl.get('last_name')]))
            if not name:
                continue
            player = players.setdefault(pid, {'id': pid, 'name': name,
                'position': pl['position'], 'team': row.get('team') or pl.get('team'),
                'injury': pl.get('injury_status'), 'points': 0., 'games': 0, 'opponents': {}, 'projected_weeks': []})
            if (settings is not None or dad) and pl['position'] not in SPECIAL:
                for key,value in stats.items():
                    if isinstance(value,(int,float)) and not math.isfinite(value):
                        raise ValueError('Non-finite projected statistics')
                points = weekly_score(stats, pl['position'], settings, dad)
            else:
                points = stats['pts_half_ppr']
            player['points'] += points
            # The next three weeks, for short-term (streaming, bye, injury-cover) pickups.
            if week < start + NEAR_WEEKS:
                player.setdefault('near', {})[str(week)] = round(points, 1)
            player['games'] += 1
            player['projected_weeks'].append(week)
            if row.get('opponent'):
                player['opponents'][week] = row['opponent']
            providers.add(row.get('company') or 'Sleeper')
            if row.get('last_modified'):
                source_times.append(row['last_modified'])
    # A team with no projected player in a week is on bye. Distinguishes a bye from a
    # missing player projection, which is not estimated.
    playing = {}
    for w in range(start, end + 1):
        for row in weekly[w]:
            team = row.get('team')
            if team and isinstance((row.get('stats') or {}).get('pts_half_ppr'), (int, float)):
                playing.setdefault(team, set()).add(w)
    ranked = sorted(players.values(), key=lambda p: (-p['points'], p['name']))
    for p in ranked:
        p['points'] = round(p['points'], 1)
        p['per_game'] = round(p['points'] / p['games'], 1)
        weeks = playing.get(p['team'])
        p['projection_complete'] = bool(weeks) and set(p['projected_weeks']) == weeks
        byes = [w for w in range(start, end + 1) if weeks and w not in weeks]
        p['bye'] = byes[0] if len(byes) == 1 else None
    assign_ranks(ranked)
    return {'season': season, 'start_week': start, 'end_week': end,
        'fetched_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'source_updated_at': dt.datetime.fromtimestamp(min(source_times) / 1000, dt.timezone.utc).isoformat() if source_times else None,
        'providers': sorted(providers), 'players': ranked}


def assign_ranks(ranked):
    """Overall flex/QB rank, positional rank, and tier within each pool."""
    for pool in POOLS:
        members = [p for p in ranked if (p['position'] in FLEX if pool == 'FLEX' else p['position'] == pool)]
        if pool == 'FLEX' and any('value_above_replacement' in p for p in members):
            members.sort(key=lambda p:(-p['value_above_replacement'],-p['points'],p['name']))
        breaks = tier_breaks([p.get('value_above_replacement',p['points']) if pool=='FLEX' else p['points'] for p in members], *TIER_SHAPE[pool])
        tier = 1
        for i, p in enumerate(members):
            if i in breaks:
                tier += 1
            p.setdefault('ranks', {})[pool] = i + 1
            p.setdefault('tiers', {})[pool] = tier


# Tiers cover the startable pool of each list; everyone deeper shares one last tier.
TIER_SHAPE = {'QB': (24, 6), 'TE': (24, 6), 'RB': (48, 9), 'WR': (60, 10), 'FLEX': (120, 12), 'K': (20, 5), 'DEF': (20, 5)}


def tier_breaks(points, depth, count):
    """Indices where a new tier starts. Optimal 1-D k-means (least within-tier squared
    error) over the top `depth` players, so tiers follow natural gaps in projected
    points rather than fixed rank bands. Deterministic for a given input."""
    xs = points[:depth]
    n, k = len(xs), min(count, len(xs))
    if n < 2 or k < 2:
        return {depth} if len(points) > depth else set()
    pre, pre2 = [0.], [0.]
    for x in xs:
        pre.append(pre[-1] + x)
        pre2.append(pre2[-1] + x * x)
    def cost(i, j):   # squared error of xs[i:j] around its mean
        s, m = pre[j] - pre[i], j - i
        return pre2[j] - pre2[i] - s * s / m
    inf = float('inf')
    best = [[inf] * (n + 1) for _ in range(k + 1)]
    cut = [[0] * (n + 1) for _ in range(k + 1)]
    best[0][0] = 0.
    for t in range(1, k + 1):
        for j in range(t, n + 1):
            for i in range(t - 1, j):
                c = best[t - 1][i] + cost(i, j)
                if c < best[t][j]:
                    best[t][j], cut[t][j] = c, i
    breaks, j = set(), n
    for t in range(k, 1, -1):
        j = cut[t][j]
        breaks.add(j)
    if len(points) > depth:
        breaks.add(depth)
    return breaks


def schedule(result, completed):
    """Rate each player's remaining opponents by the half-PPR points they have allowed
    to his position in completed weeks. Context only: Sleeper's projections already
    price matchups, so this never feeds the rank."""
    allowed = {}   # (defense, position) -> [points, games]
    games = {}     # (defense, position) -> set of weeks
    for week, rows in completed.items():
        for row in rows:
            pl, stats = row.get('player') or {}, row.get('stats') or {}
            pts, defense = stats.get('pts_half_ppr'), row.get('opponent')
            if pl.get('position') not in RANKED or not defense or not isinstance(pts, (int, float)):
                continue
            key = (defense, pl['position'])
            allowed.setdefault(key, 0.)
            allowed[key] += pts
            games.setdefault(key, set()).add(week)
    rate = {k: allowed[k] / len(games[k]) for k in allowed}
    by_pos = {}
    for p in result['players']:
        faced = [rate[(opp, p['position'])] for opp in p['opponents'].values() if (opp, p['position']) in rate]
        if faced and len(faced) == len(p['opponents']):
            p['schedule_allowed'] = round(sum(faced) / len(faced), 1)
            by_pos.setdefault(p['position'], []).append(p)
    for members in by_pos.values():
        values = [p['schedule_allowed'] for p in members]
        for p in members:
            # Mid-rank percentile, so identical schedules always share a rating.
            lower = sum(v < p['schedule_allowed'] for v in values)
            equal = sum(v == p['schedule_allowed'] for v in values)
            share = (lower + (equal - 1) / 2) / max(1, len(values) - 1)
            p['schedule'] = min(4, int(share * 5)) + 1   # 1 hardest .. 5 easiest
    result['schedule_weeks'] = sorted(completed)


class History:
    """Dated positional-rank snapshots, so the page can show movement since a
    snapshot at least MOVE_MIN_DAYS old. Only complete builds are recorded."""
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.lock = threading.Lock()

    def load(self):
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def apply(self, result, today=None):
        with self.lock:
            self._apply(result,today)

    def _apply(self, result, today=None):
        today = today or dt.date.today()
        envelope = self.load()
        scope = str(result['season']) + ':' + json.dumps(result.get('profile',{}),sort_keys=True)
        snapshots = envelope.get(scope,{})
        if not isinstance(snapshots,dict): snapshots={}
        cutoff = (today - dt.timedelta(days=MOVE_MIN_DAYS)).isoformat()
        older = sorted(d for d in snapshots if d <= cutoff)
        if older:
            base, previous = older[-1], snapshots[older[-1]]
            result['movement_since'] = base
            for p in result['players']:
                before = previous.get(p['id'])
                if isinstance(before, dict):
                    p['moved'] = {pool: before[pool] - rank for pool, rank in p['ranks'].items()
                                  if isinstance(before.get(pool), int)}
        snapshots[today.isoformat()] = {p['id']: p['ranks'] for p in result['players']}
        keep = (today - dt.timedelta(days=HISTORY_DAYS)).isoformat()
        snapshots = {d: v for d, v in snapshots.items() if d >= keep}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        envelope[scope]=snapshots
        temporary.write_text(json.dumps(envelope))
        temporary.replace(self.path)


def build(fetch, history=None, profile="standard", username=None, league_id=None, source_fetch=None, espn_fetch=None):
    state = fetch('https://api.sleeper.app/v1/state/nfl')
    season = int(state['season'])
    week = int(state.get('week') or state.get('display_week') or 0)
    start = max(1, week + 1)
    if state.get('season_type') != 'regular' or start > 17:
        raise ValueError('No remaining full regular-season fantasy weeks available')
    ctx=None
    settings=None
    slots=[]
    label='Half PPR'
    if profile == 'camden': settings,slots,label=CAMDEN,SLOTS['camden'],'Camden scoring · 12 teams'
    elif profile == 'dad': slots,label=SLOTS['dad'],'Dad scoring · 10 teams'
    elif profile == 'league':
        ctx=league_context(fetch,username,league_id,season)
        settings,slots,label=ctx['settings'],ctx['slots'],ctx['name']
        # Large metadata read is shared and dated, not repeated for each league.
        ctx['player_metadata']=(source_fetch or fetch)('https://api.sleeper.app/v1/players/nfl')
    read=source_fetch or fetch
    projection_urls=[]
    query = '&'.join('position[]=' + pos for pos in sorted(RANKED))
    def load(w):
        url=f'https://api.sleeper.app/projections/nfl/{season}/{w}?season_type=regular&{query}'
        projection_urls.append(url)
        return w, read(url)
    with ThreadPoolExecutor(max_workers=4) as pool:
        weekly = dict(pool.map(load, range(start, 18)))
    # Two-source consensus: Sleeper's feed is RotoWire alone. ESPN failing or matching
    # too few players leaves RotoWire-only numbers, disclosed as a health issue.
    matched = 0
    if espn_fetch:
        try:
            weekly, matched = season_espn.blend(weekly, espn_fetch(season_espn.URL.format(season=season)), season)
        except Exception:
            matched = 0
    result = aggregate(weekly, season, start, settings=settings, dad=profile=='dad')
    result['providers'] = sorted(set(result['providers']) | ({'ESPN'} if matched else set()))
    result['consensus'] = {'sources': ['RotoWire (via Sleeper)'] + (['ESPN'] if matched else []), 'espn_matched': matched}
    result['profile']={'id':profile,'league_id':league_id,'label':label,'slots':slots,
                       'scoring':'dad-buckets' if profile=='dad' else STANDARD if settings is None else settings}
    if hasattr(read,'read_at'):
        stamps=[read.read_at(url) for url in projection_urls]
        result['fetched_at']=dt.datetime.fromtimestamp(min(stamps),dt.timezone.utc).isoformat()
    issues=[] if matched or not espn_fetch else ['ESPN projections unavailable; showing RotoWire only']
    revision=result['source_updated_at']
    if not revision: issues.append('Provider revision date unavailable')
    elif (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(revision)).total_seconds()>72*3600:
        issues.append('Projection source is more than 72 hours old')
    projected_keys={k for rows in weekly.values() for row in rows for k in (row.get('stats') or {})}
    from season_scoring import LINEAR
    result['scoring_notes']=['Not projected by source: '+', '.join(sorted(k for k,v in (settings or {}).items() if v and k in LINEAR and not k.startswith('bonus_') and k not in projected_keys))] if any(v and k in LINEAR and not k.startswith('bonus_') and k not in projected_keys for k,v in (settings or {}).items()) else []
    result['health']={'issues':issues,'weeks_checked':len(weekly)}
    if ctx:
        apply_roster(result,ctx)
    # Scarcity adjusts the general skill-player list using the actual starter slots.
    # Position lists still order by points; no ADP/draft floors carry into ROS.
    if slots:
        teams=ctx['teams'] if ctx else (10 if profile=='dad' else 12)
        result['replacement']=replacement(result['players'],slots,teams)
        assign_ranks(result['players'])
    # Schedule strength is optional context: a stats failure leaves it out rather than
    # failing the projection ranking. The in-progress week is never counted.
    try:
        def stats(w):
            return w, read(f'https://api.sleeper.app/stats/nfl/{season}/{w}?season_type=regular&{query}')
        with ThreadPoolExecutor(max_workers=4) as pool:
            completed = {w: rows for w, rows in pool.map(stats, range(1, week)) if isinstance(rows, list) and rows}
        if len(completed) >= 2:
            schedule(result, completed)
    except Exception:
        pass
    for p in result['players']:
        p['opponents'] = {str(w): o for w, o in p['opponents'].items()}
    if history:
        history.apply(result)
    # RefreshStore persists only complete successful results.
    return {'engine_version': 6, 'reports': [result]}


def replacement(players, slots, teams):
    """Allocate league starter demand once, including flex; bench is not replacement."""
    needs={pos:slots.count(pos)*teams for pos in POSITIONS}
    flex=[slot for slot in slots if slot not in POSITIONS]
    selected=set()
    for pos,count in needs.items():
        selected.update(p['id'] for p in [p for p in players if p['position']==pos][:count])
    from season_scoring import ELIGIBLE
    for slot in sorted(flex,key=lambda x:len(ELIGIBLE[x])):
        selected.update(p['id'] for p in [p for p in players if p['id'] not in selected and p['position'] in ELIGIBLE[slot]][:teams])
    levels={}
    for pos in POSITIONS:
        beyond=[p for p in players if p['position']==pos and p['id'] not in selected]
        levels[pos]=beyond[0]['points'] if beyond else 0
    for p in players:
        if p['position'] in levels: p['value_above_replacement']=round(p['points']-levels[p['position']],1)
    return levels
