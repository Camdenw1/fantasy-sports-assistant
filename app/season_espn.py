"""ESPN's free weekly projections as a second ROS source.

Sleeper's projections are a single provider (RotoWire). Averaging them with ESPN's
per player-week gives a two-source consensus, so one outlet's view of a player does
not set his rank alone. One public request returns every week for ~1,000 skill
players. ESPN rows are matched to Sleeper rows by normalized name and position;
ambiguous or unmatched players keep the Sleeper projection unchanged.
"""
import json
import re
import urllib.request
from season_scoring import STANDARD, weekly_score

URL = ('https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}'
       '/segments/0/leaguedefaults/3?view=kona_player_info')
FILTER = {"players": {"filterSlotIds": {"value": [0, 2, 4, 6, 16, 17]}, "limit": 1100,
                      "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
POSITION = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DEF'}
SPECIAL = {'K', 'DEF'}   # compared on ESPN's own standard total, not stat by stat
PRO_TEAMS = {1: 'ATL', 2: 'BUF', 3: 'CHI', 4: 'CIN', 5: 'CLE', 6: 'DAL', 7: 'DEN', 8: 'DET', 9: 'GB',
             10: 'TEN', 11: 'IND', 12: 'KC', 13: 'LV', 14: 'LAR', 15: 'MIA', 16: 'MIN', 17: 'NE',
             18: 'NO', 19: 'NYG', 20: 'NYJ', 21: 'PHI', 22: 'ARI', 23: 'PIT', 24: 'LAC', 25: 'SF',
             26: 'SEA', 27: 'TB', 28: 'WSH', 29: 'CAR', 30: 'JAX', 33: 'BAL', 34: 'HOU'}
TEAM_ALIASES = {'WAS': 'WSH', 'LA': 'LAR', 'JAC': 'JAX', 'ARZ': 'ARI'}
# ESPN stat id -> Sleeper stat key. Verified 2026-10-06: recomputing ESPN's PPR
# appliedTotal from these ids matched 6,160 of 6,174 player-weeks within 0.3 pts
# (the rest are return yards, which skill scoring here does not use).
STATS = {'0': 'pass_att', '1': 'pass_cmp', '3': 'pass_yd', '4': 'pass_td', '20': 'pass_int',
         '19': 'pass_2pt', '23': 'rush_att', '24': 'rush_yd', '25': 'rush_td', '26': 'rush_2pt',
         '53': 'rec', '58': 'rec_tgt', '42': 'rec_yd', '43': 'rec_td', '44': 'rec_2pt',
         '72': 'fum_lost'}
MIN_MATCHED = 150


def fetch(url):
    """Plain read with ESPN's filter header (the cache layer keys on the URL)."""
    season = re.search(r'/seasons/(\d+)/', url).group(1)
    request = urllib.request.Request(URL.format(season=season), headers={
        'User-Agent': 'fantasy-sports-assistant/local-dashboard', 'x-fantasy-filter': json.dumps(FILTER)})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def key(name, position):
    name = re.sub(r"[^a-z ]", '', name.lower().replace('-', ' '))
    name = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', name)
    return ' '.join(name.split()), position


def weekly(data, season):
    """{(name_key, pos): {week: sleeper-keyed stats}}; ambiguous identities dropped.
    A zero-point ESPN week (bye, or no projection published) is not a projection."""
    out, seen = {}, {}
    for entry in (data or {}).get('players', []):
        pl = entry.get('player') or {}
        pos = POSITION.get(pl.get('defaultPositionId'))
        if not pos or not pl.get('fullName'):
            continue
        # Defenses are one per team, so match them by team rather than by name.
        k = ('team ' + PRO_TEAMS.get(pl.get('proTeamId'), '?'), pos) if pos == 'DEF' else key(pl['fullName'], pos)
        seen[k] = seen.get(k, 0) + 1
        weeks = {}
        for s in pl.get('stats') or []:
            if (s.get('seasonId') == season and s.get('statSourceId') == 1 and s.get('statSplitTypeId') == 1
                    and s.get('appliedTotal') and isinstance(s.get('stats'), dict)):
                weeks[s['scoringPeriodId']] = ({'_total': s['appliedTotal']} if pos in SPECIAL else
                    {STATS[i]: v for i, v in s['stats'].items() if i in STATS and isinstance(v, (int, float))})
        out[k] = weeks
    return {k: v for k, v in out.items() if seen[k] == 1}


def blend(sleeper_weekly, espn, season):
    """Average Sleeper and ESPN stats per player-week, in place on copies of the rows.
    Returns (new weekly dict, matched player count). Stats ESPN does not project keep
    Sleeper's value; pts_half_ppr is the mean of both sources' half-PPR totals."""
    projections = weekly(espn, season)
    matched, blended = set(), {}
    for week, rows in sleeper_weekly.items():
        out = []
        for row in rows if isinstance(rows, list) else []:
            pl, stats = row.get('player') or {}, row.get('stats') or {}
            name = ' '.join(filter(None, [pl.get('first_name'), pl.get('last_name')]))
            pos = pl.get('position')
            if pos == 'DEF':
                team = row.get('team') or pl.get('team') or ''
                other = projections.get(('team ' + TEAM_ALIASES.get(team, team), 'DEF'))
            else:
                other = projections.get(key(name, pos)) if name else None
            theirs = (other or {}).get(week)
            if not theirs or not isinstance(stats.get('pts_half_ppr'), (int, float)) or float(stats.get('gp') or 0) <= 0:
                out.append(row)
                continue
            merged = dict(stats)
            if pos in SPECIAL:
                merged['pts_half_ppr'] = (stats['pts_half_ppr'] + theirs['_total']) / 2
                out.append(dict(row, stats=merged))
                matched.add(row.get('player_id'))
                continue
            for stat, value in theirs.items():
                merged[stat] = (stats[stat] + value) / 2 if isinstance(stats.get(stat), (int, float)) else value
            merged['pts_half_ppr'] = (stats['pts_half_ppr'] + weekly_score(theirs, pl['position'], STANDARD)) / 2
            out.append(dict(row, stats=merged))
            matched.add(row.get('player_id'))
        blended[week] = out if isinstance(rows, list) else rows
    if len(matched) < MIN_MATCHED:
        return sleeper_weekly, 0
    return blended, len(matched)
