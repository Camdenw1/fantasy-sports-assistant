"""Public ESPN roster import. Private leagues use an explicit page snapshot.

No credentials are accepted. The supplied URL contributes IDs only; requests go
solely to ESPN's fixed league endpoint. Raw private data is never saved to disk.
"""
import datetime as dt
from urllib.parse import parse_qs, urlparse

SLOTS = {0: 'QB', 2: 'RB', 3: 'RB/WR', 4: 'WR', 5: 'WR/TE', 6: 'TE',
         7: 'SUPERFLEX', 16: 'DEF', 17: 'K', 20: 'BN', 21: 'IR', 23: 'FLEX',
         1: 'TQB', 8: 'DT', 9: 'DE', 10: 'LB', 11: 'DL', 12: 'CB', 13: 'S', 14: 'DB', 15: 'IDP'}
INJURIES = {'ACTIVE': 'Active', 'NORMAL': 'Active', 'QUESTIONABLE': 'Questionable',
            'DOUBTFUL': 'Doubtful', 'OUT': 'Out', 'INJURY_RESERVE': 'IR',
            'INJURED_RESERVE': 'IR', 'SUSPENSION': 'Sus'}


def parse_url(value, team_id=None, season=None):
    url = urlparse(value)
    if url.scheme != 'https' or url.hostname != 'fantasy.espn.com':
        raise ValueError('Use an ESPN fantasy football team or league URL.')
    if not url.path.startswith('/football/'):
        raise ValueError('This importer currently supports ESPN fantasy football.')
    query = parse_qs(url.query)
    lid = query.get('leagueId', [''])[0]
    tid = team_id or query.get('teamId', [''])[0]
    year = query.get('seasonId', [str(season or dt.date.today().year)])[0]
    if not lid.isdigit() or not 1 <= len(lid) <= 15:
        raise ValueError('The ESPN URL needs a leagueId.')
    if tid and (not str(tid).isdigit() or not 1 <= int(tid) <= 100):
        raise ValueError('Team number must be between 1 and 100.')
    if not str(year).isdigit() or not 2020 <= int(year) <= 2100:
        raise ValueError('Invalid ESPN season.')
    return lid, int(tid) if tid else None, int(year)


def normalize(data, lid, team_id, season):
    teams = data.get('teams') or []
    choices = [{'id': team['id'], 'name': team.get('name') or
                ' '.join(filter(None, [team.get('location'), team.get('nickname')])) or
                'Team ' + str(team['id'])} for team in teams]
    if not teams:
        raise ValueError('No public roster returned. Open ESPN and import a roster snapshot instead.')
    if team_id is None:
        return {'teams': choices, 'needs_team': True}
    mine = next((team for team in teams if team['id'] == team_id), None)
    if mine is None:
        raise ValueError('Team number was not found in this league.')
    entries = (mine.get('roster') or {}).get('entries')
    if entries is None:
        raise ValueError('This league did not expose a roster. Use a roster snapshot instead.')
    slots = ((data.get('settings') or {}).get('rosterSettings') or {}).get('lineupSlotCounts') or {}
    starters, bench = [], []
    for entry in entries:
        slot_id = int(entry['lineupSlotId'])
        player = (entry.get('playerPoolEntry') or {}).get('player') or {}
        if not player.get('fullName'):
            raise ValueError('ESPN returned a player without a name; the import needs review.')
        row = {'slot': SLOTS.get(slot_id, 'Slot ' + str(slot_id)),
               'player': player['fullName'], 'espnId': str(player.get('id', '')),
               'status': INJURIES.get(player.get('injuryStatus'), 'Unknown')}
        (bench if slot_id in (20, 21) else starters).append(row)
    for key, count in slots.items():
        slot_id = int(key)
        if slot_id in (20, 21):
            continue
        label = SLOTS.get(slot_id, 'Slot ' + str(slot_id))
        missing = int(count) - sum(row['slot'] == label for row in starters)
        starters.extend({'slot': label, 'player': 'Empty', 'status': 'Empty'} for _ in range(max(0, missing)))
    if not starters:
        raise ValueError('No starters found; confirm the roster in ESPN before importing.')
    week = data.get('scoringPeriodId')
    if not isinstance(week, int) or not 1 <= week <= 18:
        raise ValueError('ESPN did not return a regular-season week. Use a roster snapshot with an explicit week.')
    settings = data.get('settings') or {}
    team_name = next(team['name'] for team in choices if team['id'] == team_id)
    return {'needs_team': False, 'teams': choices, 'snapshot': {
        'name': settings.get('name') or 'ESPN league ' + lid,
        'platform': 'ESPN', 'teamName': team_name, 'week': week,
        'starters': starters, 'bench': bench, 'scoring': 'ESPN league scoring · imported roster only',
        'url': f'https://fantasy.espn.com/football/team?leagueId={lid}&teamId={team_id}&seasonId={season}',
        'source': 'espn public roster', 'savedAt': dt.datetime.now(dt.timezone.utc).isoformat()}}


def import_league(value, team_id, fetch):
    lid, tid, season = parse_url(value, team_id)
    url = (f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}'
           f'/segments/0/leagues/{lid}?view=mRoster&view=mTeam&view=mSettings')
    return normalize(fetch(url), lid, tid, season)
