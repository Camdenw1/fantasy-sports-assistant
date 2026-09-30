"""Current ROS projection rankings, independent of the frozen draft pipeline."""
import datetime as dt
import math
from concurrent.futures import ThreadPoolExecutor

POSITIONS = {'QB', 'RB', 'WR', 'TE'}


def aggregate(weekly, season, start, end=17):
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
            if (pl.get('position') not in POSITIONS or not row.get('player_id')
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
                'injury': pl.get('injury_status'), 'points': 0., 'games': 0})
            player['points'] += stats['pts_half_ppr']
            player['games'] += 1
            providers.add(row.get('company') or 'Sleeper')
            if row.get('last_modified'):
                source_times.append(row['last_modified'])
    ranked = sorted(players.values(), key=lambda p: (-p['points'], p['name']))
    for p in ranked:
        p['points'] = round(p['points'], 1)
        p['per_game'] = round(p['points'] / p['games'], 1)
    return {'season': season, 'start_week': start, 'end_week': end,
        'fetched_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'source_updated_at': dt.datetime.fromtimestamp(min(source_times) / 1000, dt.timezone.utc).isoformat() if source_times else None,
        'providers': sorted(providers), 'players': ranked}


def build(fetch):
    state = fetch('https://api.sleeper.app/v1/state/nfl')
    season = int(state['season'])
    week = int(state.get('week') or state.get('display_week') or 0)
    start = max(1, week + 1)
    if state.get('season_type') != 'regular' or start > 17:
        raise ValueError('No remaining full regular-season fantasy weeks available')
    query = '&'.join('position[]=' + pos for pos in sorted(POSITIONS))
    def load(w):
        return w, fetch(f'https://api.sleeper.app/projections/nfl/{season}/{w}?season_type=regular&{query}')
    with ThreadPoolExecutor(max_workers=4) as pool:
        weekly = dict(pool.map(load, range(start, 18)))
    result = aggregate(weekly, season, start)
    # RefreshStore persists only complete successful results.
    return {'engine_version': 1, 'reports': [result]}
