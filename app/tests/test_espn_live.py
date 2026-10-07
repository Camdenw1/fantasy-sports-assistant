import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import espn_live


def entry(slot, pid, name, pos, eligible, proj, team=6, injury='ACTIVE', actual=None):
    stats = [{'scoringPeriodId': 5, 'statSourceId': 1, 'statSplitTypeId': 1, 'appliedTotal': proj}]
    if actual is not None:
        stats.append({'scoringPeriodId': 5, 'statSourceId': 0, 'statSplitTypeId': 1, 'appliedTotal': actual})
    return {'lineupSlotId': slot, 'playerPoolEntry': {'player': {'id': pid, 'fullName': name, 'defaultPositionId': pos,
            'proTeamId': team, 'injuryStatus': injury, 'eligibleSlots': eligible, 'stats': stats}}}


def league(entries):
    return {'scoringPeriodId': 5, 'status': {'currentMatchupPeriod': 5},
            'settings': {'name': 'Work League', 'rosterSettings': {'lineupSlotCounts': {'0': 1, '2': 1, '23': 1, '20': 2, '21': 1}},
                         'acquisitionSettings': {'isUsingAcquisitionBudget': True, 'acquisitionBudget': 100}},
            'teams': [{'id': 1, 'name': 'Mine', 'record': {'overall': {'wins': 3, 'losses': 1, 'pointsFor': 400}},
                       'transactionCounter': {'acquisitionBudgetSpent': 13}, 'roster': {'entries': entries}},
                      {'id': 2, 'name': 'Rival', 'record': {'overall': {'wins': 4, 'losses': 0, 'pointsFor': 380}}}],
            'schedule': [{'matchupPeriodId': 5, 'home': {'teamId': 1, 'totalPointsLive': 0, 'totalProjectedPointsLive': 100},
                          'away': {'teamId': 2, 'totalPointsLive': 0, 'totalProjectedPointsLive': 95}}]}


GAMES = {'DAL': {'state': 'pre', 'kickoff': '2026-10-11T17:00Z', 'opp': 'TB'}, 'KC': {'state': 'in', 'kickoff': '2026-10-11T17:00Z', 'opp': 'BUF'}}


class EspnLiveTests(unittest.TestCase):
    def test_injured_starter_swapped_for_best_eligible_bench_player(self):
        entries = [entry(0, 1, 'QB One', 1, [0, 20], 18), entry(2, 2, 'Hurt Back', 2, [2, 23, 20], 0, injury='OUT'),
                   entry(23, 3, 'Flex Back', 2, [2, 23, 20], 10), entry(20, 4, 'Bench Back', 2, [2, 23, 20], 12),
                   entry(20, 5, 'Bench Wideout', 3, [4, 23, 20], 8), entry(21, 6, 'Stashed', 2, [2, 23, 20, 21], 0, injury='INJURY_RESERVE')]
        report = espn_live.build(league(entries), '99', 1, 2026, GAMES)
        self.assertEqual(report['totals'], {'current': 28.0, 'recommended': 40.0})
        self.assertEqual([(s['in_name'], s['out_name'], s['delta']) for s in report['swaps']], [('Bench Back', 'Hurt Back', 12.0)])
        self.assertIn('is Out', report['swaps'][0]['reason'])
        self.assertEqual([p['name'] for p in report['reserve']], ['Stashed'])
        self.assertEqual(report['standing']['faab'], 87)
        self.assertEqual((report['standing']['place'], report['standing']['pfRank']), (2, 1))
        self.assertEqual(report['opponent']['team_name'], 'Rival')
        self.assertEqual(report['schema'], 'startsit/v1')

    def test_locked_starter_stays_and_empty_slot_is_filled(self):
        entries = [entry(0, 1, 'Live QB', 1, [0, 20], 18, team=12, actual=9), entry(23, 3, 'Flex Back', 2, [2, 23, 20], 10),
                   entry(20, 4, 'Bench Back', 2, [2, 23, 20], 12)]
        report = espn_live.build(league(entries), '99', 1, 2026, GAMES)
        qb = report['slots'][0]
        self.assertTrue(qb['locked'])
        self.assertEqual(qb['current']['value'], 9)          # actual points once the game is on
        rb = next(s for s in report['slots'] if s['slot'] == 'RB')
        self.assertIsNone(rb['current'])
        self.assertTrue(rb['change'])

    def test_bye_week_player_counts_as_zero(self):
        entries = [entry(0, 1, 'Bye QB', 1, [0, 20], 20, team=1), entry(20, 2, 'Backup QB', 1, [0, 20], 14)]
        report = espn_live.build(league(entries), '99', 1, 2026, GAMES)   # ATL has no game
        self.assertEqual(report['swaps'][0]['in_name'], 'Backup QB')
        self.assertIn('on bye', report['swaps'][0]['reason'])


if __name__ == '__main__': unittest.main()
