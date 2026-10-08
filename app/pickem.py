"""Sleeper Pick'em helper: live NFL scores, spreads, and value since Tuesday's lock.

Sleeper's Pick'em has no public API, so picks are never read from or written to
Sleeper. Sleeper locks each week's spreads on Tuesday morning; this module records
ESPN's (DraftKings) spread for every game once that moment has passed, then compares
it with the current line using the rules in Camden's pickem skill: the side the market
moved toward is getting extra points at the locked number, and moves that cross or
land on 3 or 7 matter most.
"""
import datetime as dt
import json
import pathlib
import threading
import uuid
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo('America/New_York')
SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week}&dates={season}'
LOCK_HOUR = 10          # Sleeper locks spreads Tuesday morning ET
LATE_AFTER = dt.timedelta(hours=6)   # a lock captured later than this is approximate
KEYS = {3, 7}
SECONDARY = {4, 6, 10, 14}
ALIASES = {'WSH': 'WSH', 'WAS': 'WSH', 'LA': 'LAR', 'JAC': 'JAX'}


def number(text):
    try:
        return float(str(text).replace('+', '')) if str(text).strip().upper() not in {'PK', 'EVEN', 'EV'} else 0.
    except (TypeError, ValueError):
        return None


def games(board):
    """Normalize ESPN's scoreboard. Spreads are from the home team's perspective
    (negative = home favored)."""
    out = []
    for event in (board or {}).get('events', []):
        comp = (event.get('competitions') or [{}])[0]
        teams = {c.get('homeAway'): c for c in comp.get('competitors', [])}
        if 'home' not in teams or 'away' not in teams:
            continue
        status = (comp.get('status') or event.get('status') or {}).get('type', {})
        odds = (comp.get('odds') or [{}])[0]
        spread = odds.get('spread')
        home_close = (((odds.get('pointSpread') or {}).get('home') or {}).get('close') or {}).get('line')
        if not isinstance(spread, (int, float)):
            spread = number(home_close)
        side = lambda c: {'abbr': ALIASES.get(c['team']['abbreviation'], c['team']['abbreviation']),
                          'name': c['team'].get('shortDisplayName') or c['team'].get('name'),
                          'score': int(c['score']) if str(c.get('score', '')).isdigit() else None,
                          'record': ((c.get('records') or [{}])[0]).get('summary')}
        out.append({'id': str(event['id']), 'kickoff': event.get('date'), 'state': status.get('state'),
                    'detail': status.get('shortDetail'), 'completed': bool(status.get('completed')),
                    'home': side(teams['home']), 'away': side(teams['away']),
                    'spread_now': float(spread) if isinstance(spread, (int, float)) else None,
                    'provider': (odds.get('provider') or {}).get('name')})
    return sorted(out, key=lambda g: g['kickoff'] or '')


def lock_time(game_list):
    """Tuesday 10:00 ET before the week's first kickoff."""
    first = min(dt.datetime.fromisoformat(g['kickoff'].replace('Z', '+00:00')) for g in game_list if g['kickoff'])
    local = first.astimezone(EASTERN)
    tuesday = local.date() - dt.timedelta(days=(local.weekday() - 1) % 7)
    return dt.datetime(tuesday.year, tuesday.month, tuesday.day, LOCK_HOUR, tzinfo=EASTERN)


def line_text(home, away, home_spread):
    if home_spread is None:
        return None
    if home_spread == 0:
        return 'PK'
    favorite, value = (home, home_spread) if home_spread < 0 else (away, -home_spread)
    return f"{favorite} {value:g}"


def value(start, now):
    """Move since lock and the value side, per the pickem skill's key-number rules."""
    if start is None or now is None:
        return None
    move = round(now - start, 1)
    if move == 0:
        return {'move': 0, 'side': None, 'strength': None}
    low, high = min(start, now), max(start, now)
    touches = lambda keys: any(low <= k <= high for key in keys for k in (key, -key))
    strength = 'Strong' if touches(KEYS) else 'Solid' if abs(move) >= 1.5 or touches(SECONDARY) else 'Minor'
    return {'move': move, 'side': 'home' if move < 0 else 'away', 'strength': strength}


class LockStore:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.lock = threading.Lock()

    def read(self):
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def capture(self, season, week, game_list, now):
        """Record lines once the lock has passed. Never overwrites an existing line."""
        locked_at = lock_time(game_list)
        if now < locked_at:
            return None
        with self.lock:
            data = self.read()
            entry = data.setdefault(str(season), {}).setdefault(str(week), {
                'captured_at': now.isoformat(), 'lock_at': locked_at.isoformat(),
                'approximate': now - locked_at > LATE_AFTER, 'lines': {}})
            changed = False
            for g in game_list:
                if g['id'] not in entry['lines'] and g['spread_now'] is not None and g['state'] == 'pre':
                    entry['lines'][g['id']] = g['spread_now']
                    changed = True
            if changed or not self.path.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
                temporary.write_text(json.dumps(data))
                temporary.replace(self.path)
            return entry


def build(fetch, store, season, week, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    game_list = games(fetch(SCOREBOARD.format(season=season, week=week)))
    if not game_list:
        raise ValueError('No NFL games found for this week')
    entry = store.capture(season, week, game_list, now) or {}
    lines = entry.get('lines', {})
    for g in game_list:
        start = lines.get(g['id'])
        g['spread_lock'] = start
        g['lock_text'] = line_text(g['home']['abbr'], g['away']['abbr'], start)
        g['now_text'] = line_text(g['home']['abbr'], g['away']['abbr'], g['spread_now'])
        g['value'] = value(start, g['spread_now'])
        g['push_possible'] = start is not None and float(start).is_integer()
    return {'season': season, 'week': week, 'fetched_at': now.isoformat(), 'games': game_list,
            'lock': {'at': entry.get('lock_at') or lock_time(game_list).isoformat(),
                     'captured_at': entry.get('captured_at'), 'approximate': entry.get('approximate', False)},
            'live': any(g['state'] == 'in' for g in game_list),
            'source': 'ESPN scoreboard (' + (next((g['provider'] for g in game_list if g['provider']), None) or 'odds') + ')'}
