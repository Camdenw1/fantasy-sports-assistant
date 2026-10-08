"""Live, read-only ESPN league report in the same shape as the Sleeper start/sit report.

Public ESPN leagues only: no credentials are accepted (see espn.py). One request to
ESPN's league endpoint returns rosters, ESPN's weekly projections, live matchup scores,
standings and FAAB. The lineup check uses ESPN's own projections and each player's
ESPN-eligible slots; players whose NFL game has started stay where they are.
"""
import datetime as dt
import math
from espn import SLOTS, parse_url

POSITION = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DEF'}
INJURY = {'QUESTIONABLE': 'Questionable', 'DOUBTFUL': 'Doubtful', 'OUT': 'Out',
          'INJURY_RESERVE': 'IR', 'INJURED_RESERVE': 'IR', 'SUSPENSION': 'Sus'}
INACTIVE = {'Out', 'IR', 'Sus'}
PRO_TEAMS = {1: 'ATL', 2: 'BUF', 3: 'CHI', 4: 'CIN', 5: 'CLE', 6: 'DAL', 7: 'DEN', 8: 'DET', 9: 'GB',
             10: 'TEN', 11: 'IND', 12: 'KC', 13: 'LV', 14: 'LAR', 15: 'MIA', 16: 'MIN', 17: 'NE',
             18: 'NO', 19: 'NYG', 20: 'NYJ', 21: 'PHI', 22: 'ARI', 23: 'PIT', 24: 'LAC', 25: 'SF',
             26: 'SEA', 27: 'TB', 28: 'WSH', 29: 'CAR', 30: 'JAX', 33: 'BAL', 34: 'HOU'}
BENCH, IR = 20, 21
SKIP = {BENCH, IR}
VIEWS = ('mTeam', 'mRoster', 'mSettings', 'mMatchupScore', 'mScoreboard', 'mStatus')
MARGIN_SD = 25.0   # spread of weekly fantasy margins, for the pregame win-chance estimate


def url(lid, season, week):
    views = '&'.join('view=' + v for v in VIEWS)
    return (f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}'
            f'/segments/0/leagues/{lid}?{views}&scoringPeriodId={week}')


def week_stat(player, week, source):
    for s in player.get('stats') or []:
        if s.get('scoringPeriodId') == week and s.get('statSourceId') == source and s.get('statSplitTypeId') == 1:
            return s.get('appliedTotal')
    return None


def player_view(entry, week, games):
    pl = (entry.get('playerPoolEntry') or {}).get('player') or {}
    team = PRO_TEAMS.get(pl.get('proTeamId'))
    game = games.get(team) if team else None
    state = 'bye' if team and games and game is None else (game or {}).get('state', 'pre')
    projected, actual = week_stat(pl, week, 1), week_stat(pl, week, 0)
    injury = INJURY.get(pl.get('injuryStatus'))
    view = {'id': 'espn:' + str(pl.get('id')), 'name': pl.get('fullName') or 'Unknown player',
            'pos': POSITION.get(pl.get('defaultPositionId'), '?'), 'team': team, 'injury': injury,
            'game_state': state, 'kickoff': (game or {}).get('kickoff'), 'opp': (game or {}).get('opp'),
            'locked': state in ('in', 'post'), 'proj': projected, 'actual': actual,
            'eligible': set(pl.get('eligibleSlots') or []),
            'sources': 1 if projected is not None or state == 'bye' else 0}
    # Value for lineup decisions: the projection; 0 when ruled out or on bye.
    view['value'] = 0. if state == 'bye' or injury in INACTIVE else (projected or 0.)
    if view['locked'] and actual is not None:
        view['value'] = actual
    return view


def best_assignment(players, slots):
    """Highest projected total over legal slot assignments; each player used once."""
    best = {0: (0., ())}
    for p in players:
        for mask, (score, picks) in list(best.items()):
            for i, slot in enumerate(slots):
                bit = 1 << i
                if mask & bit or slot not in p['eligible']:
                    continue
                key, total = mask | bit, score + p['value']
                if total > best.get(key, (-1, ()))[0]:
                    best[key] = (total, picks + ((i, p['id']),))
    full = max(best, key=lambda m: (bin(m).count('1'), best[m][0]))
    return dict(best[full][1])


def win_prob(mine, theirs):
    return round(0.5 * (1 + math.erf((mine - theirs) / (MARGIN_SD * math.sqrt(2)))), 3)


def public(p):
    return {k: v for k, v in p.items() if k != 'eligible'}


def build(data, lid, team_id, season, games, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    week = data.get('scoringPeriodId')
    if not isinstance(week, int):
        raise ValueError('ESPN did not return the current week.')
    teams = {t['id']: t for t in data.get('teams') or []}
    mine = teams.get(team_id)
    if not mine or (mine.get('roster') or {}).get('entries') is None:
        raise ValueError('This ESPN league did not return your roster publicly.')
    name = lambda t: t.get('name') or ' '.join(filter(None, [t.get('location'), t.get('nickname')])) or 'Team ' + str(t.get('id'))
    entries = mine['roster']['entries']
    counts = ((data.get('settings') or {}).get('rosterSettings') or {}).get('lineupSlotCounts') or {}
    slot_ids = [int(k) for k, n in sorted(counts.items(), key=lambda kv: int(kv[0])) for _ in range(int(n)) if int(k) not in SKIP]
    roster = [(int(e['lineupSlotId']), player_view(e, week, games)) for e in entries]
    starters = [(s, p) for s, p in roster if s not in SKIP]
    bench = [p for s, p in roster if s == BENCH]
    reserve = [p for s, p in roster if s == IR]
    # One row per starting slot, in ESPN's slot order; empty slots stay visible.
    rows = [{'slot_id': slot, 'current': p} for slot, p in starters]
    for slot in sorted(set(slot_ids)):
        missing = slot_ids.count(slot) - sum(r['slot_id'] == slot for r in rows)
        rows += [{'slot_id': slot, 'current': None} for _ in range(max(0, missing))]
    rows.sort(key=lambda r: slot_ids.index(r['slot_id']) if r['slot_id'] in slot_ids else 99)
    # Locked starters keep their slots; optimize the rest over unlocked players.
    candidates = [p for _, p in starters if not p['locked']] + [p for p in bench if not p['locked']]
    open_rows = [r for r in rows if not (r['current'] and r['current']['locked'])]
    chosen = best_assignment(candidates, [r['slot_id'] for r in open_rows])
    by_id = {p['id']: p for p in candidates}
    for i, r in enumerate(open_rows):
        r['recommended'] = by_id.get(chosen.get(i)) if chosen.get(i) else r['current']
    for r in rows:
        r.setdefault('recommended', r['current'])
    slots, swaps = [], []
    total_now = sum((r['current'] or {}).get('value', 0) for r in rows)
    total_best = sum((r['recommended'] or {}).get('value', 0) for r in rows)
    for r in rows:
        cur, rec = r['current'], r['recommended']
        change = bool(rec and (not cur or rec['id'] != cur['id']))
        delta = round((rec or {}).get('value', 0) - (cur or {}).get('value', 0), 1) if change else 0
        label = SLOTS.get(r['slot_id'], 'Slot ' + str(r['slot_id']))
        reason = ('Game started · lineup locked' if cur and cur['locked'] else
                  (cur['name'] + (' is ' + cur['injury'] if cur and cur['injury'] in INACTIVE else ' is on bye' if cur and cur['game_state'] == 'bye' else ' projects lower'))
                  if change and cur else 'Fill the empty slot' if change else 'Best available starter')
        slots.append({'slot': label, 'current': public(cur) if cur else None, 'recommended': public(rec) if rec else None,
                      'change': change, 'locked': bool(cur and cur['locked']), 'reason': reason, 'delta': delta})
    # Pair the moves: a player who leaves the lineup goes out for the one coming in.
    starting_now = {r['current']['id'] for r in rows if r['current']}
    starting_best = {r['recommended']['id'] for r in rows if r['recommended']}
    ins = [p for p in candidates if p['id'] in starting_best - starting_now]
    outs = sorted((p for p in candidates if p['id'] in starting_now - starting_best), key=lambda p: p['value'])
    for incoming in sorted(ins, key=lambda p: -p['value']):
        out = outs.pop(0) if outs else None
        slot = next(s['slot'] for s in slots if s['recommended'] and s['recommended']['id'] == incoming['id'])
        swaps.append({'in': incoming['id'], 'in_name': incoming['name'], 'out': out and out['id'], 'out_name': out and out['name'],
                      'slot': slot, 'delta': round(incoming['value'] - (out['value'] if out else 0), 1),
                      'reason': (out['name'] + (' is ' + out['injury'] if out['injury'] in INACTIVE else ' is on bye' if out['game_state'] == 'bye' else ' projects lower')) if out else 'Fills an empty slot'})
    # Live matchup, standings and FAAB.
    period = (data.get('status') or {}).get('currentMatchupPeriod') or week
    games_now = [g for g in data.get('schedule') or [] if g.get('matchupPeriodId') == period]
    side = lambda s: {'team_id': s.get('teamId'), 'name': name(teams.get(s.get('teamId'), {})),
                      'points': s.get('totalPointsLive', s.get('totalPoints', 0)) or 0,
                      'projected': s.get('totalProjectedPointsLive'),
                      'record': '{wins}–{losses}'.format(**((teams.get(s.get('teamId'), {}).get('record') or {}).get('overall') or {'wins': 0, 'losses': 0}))}
    board = [[side(g['home'])] + ([side(g['away'])] if g.get('away') else []) for g in games_now if g.get('home')]
    mine_game = next((pair for pair in board if any(t['team_id'] == team_id for t in pair)), None)
    opponent = next((t for t in (mine_game or []) if t['team_id'] != team_id), None)
    opp_projected = (opponent or {}).get('projected') or 0
    overall = (mine.get('record') or {}).get('overall') or {}
    all_teams = list(teams.values())
    pf = lambda t: ((t.get('record') or {}).get('overall') or {}).get('pointsFor', 0)
    by_record = sorted(all_teams, key=lambda t: (-(((t.get('record') or {}).get('overall') or {}).get('wins', 0)), -pf(t)))
    acquisition = (data.get('settings') or {}).get('acquisitionSettings') or {}
    budget = acquisition.get('acquisitionBudget') if acquisition.get('isUsingAcquisitionBudget') else None
    spent = (mine.get('transactionCounter') or {}).get('acquisitionBudgetSpent', 0)
    gaps = [p for p in [x for _, x in starters] + bench if not p['sources'] and p['injury'] not in INACTIVE]
    return {
        'schema': 'startsit/v1', 'platform': 'espn', 'generated_at': now.isoformat(),
        'league': {'id': 'espn-' + lid, 'name': (data.get('settings') or {}).get('name') or 'ESPN league ' + lid,
                   'season': season, 'week': week, 'teams': len(teams), 'scoring_fingerprint': {'platform': 'espn'}},
        'team': {'roster_id': team_id, 'name': name(mine)},
        'opponent': opponent and {'team_name': opponent['name'], 'projected': opp_projected, 'points_so_far': opponent['points'],
                                  'win_prob_current': win_prob(total_now, opp_projected),
                                  'win_prob_recommended': win_prob(total_best, opp_projected)},
        'sources': {'projections': ['espn'], 'schedule': 'espn scoreboard',
                    'projection_gaps': [{'id': p['id'], 'name': p['name'], 'position': p['pos']} for p in gaps]},
        'totals': {'current': round(total_now, 1), 'recommended': round(total_best, 1)},
        'slots': slots, 'bench': [public(p) for p in bench], 'reserve': [public(p) for p in reserve],
        'swaps': swaps, 'alerts': [],
        'apply': {'url': f'https://fantasy.espn.com/football/team?leagueId={lid}&teamId={team_id}&seasonId={season}'},
        'standing': {'wins': overall.get('wins', 0), 'losses': overall.get('losses', 0), 'ties': overall.get('ties', 0),
                     'place': by_record.index(mine) + 1, 'teams': len(all_teams), 'pf': pf(mine),
                     'pfRank': sorted(all_teams, key=lambda t: -pf(t)).index(mine) + 1,
                     'faab': None if budget is None else budget - spent, 'budget': budget,
                     'waiverPosition': mine.get('waiverRank')},
        'scoreboard': {'games': board, 'team_id': team_id},
        'fetched_at': now.isoformat()}


def live(league_url, team_id, fetch, games):
    lid, tid, season = parse_url(league_url, team_id)
    if tid is None:
        raise ValueError('Choose your team first.')
    status = fetch(f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{lid}?view=mStatus')
    week = status.get('scoringPeriodId')
    if not isinstance(week, int):
        raise ValueError('ESPN did not return the current week.')
    data = fetch(url(lid, season, week))
    return build(data, lid, tid, season, games)
