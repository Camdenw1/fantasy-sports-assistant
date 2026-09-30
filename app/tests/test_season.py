import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import datetime as dt
import tempfile
from season import History, aggregate, schedule, tier_breaks


def row(pid, week, points=10, modified=100, team='BUF', opponent=None):
    return {'team': team, 'opponent': opponent, 'player_id': str(pid), 'season': '2026', 'week': week,
            'last_modified': modified, 'company': 'fixture',
            'stats': {'pts_half_ppr': points, 'gp': 1},
            'player': {'first_name': 'Player', 'last_name': str(pid), 'position': 'RB', 'team': team}}


class SeasonTests(unittest.TestCase):
    def test_remaining_weeks_and_duplicates(self):
        weeks = {w: [row(p,w) for p in range(150)] for w in [16,17]}
        weeks[16].extend([row(0,16,20,200), row(0,16,99,50)])
        weeks[16].append({'player_id':'placeholder', 'stats':{'adp_dd_ppr':1000}, 'player':{'position':'WR'}})
        result = aggregate(weeks,2026,16)
        self.assertEqual(len(result['players']),150)
        self.assertEqual(result['players'][0]['id'],'0')
        self.assertEqual(result['players'][0]['points'],30)
        self.assertEqual(result['players'][0]['games'],2)
        self.assertEqual(result['players'][0]['per_game'],15)

    def test_missing_week_refuses_partial_rankings(self):
        with self.assertRaises(ValueError):
            aggregate({16:[row(p,16) for p in range(150)]},2026,16)

    def test_placeholder_only_week_refuses_rankings(self):
        with self.assertRaises(ValueError):
            aggregate({17:[{'player_id':str(p),'player':{'position':'WR'},'stats':{'adp_dd_ppr':1000}} for p in range(300)]},2026,17)

    def test_wrong_season_refuses_rankings(self):
        with self.assertRaises(ValueError):
            aggregate({17:[row(p,17) for p in range(150)]},2025,17)

    def test_bye_is_distinct_from_missing_projection(self):
        weeks = {16: [row(p,16) for p in range(150)],
                 17: [row(p,17) for p in range(149)] + [row(p,17,team='MIA') for p in range(200,350)]}
        players = {p['id']: p for p in aggregate(weeks,2026,16)['players']}
        self.assertIsNone(players['149']['bye'])      # BUF played; projection just missing
        self.assertEqual(players['149']['games'], 1)
        self.assertEqual(players['200']['bye'], 16)   # MIA had no one projected in week 16

    def test_tiers_follow_gaps_and_are_deterministic(self):
        points = [30, 29, 28, 20, 19, 18, 10, 9, 8, 7]
        self.assertEqual(tier_breaks(points, 10, 3), {3, 6})
        self.assertEqual(tier_breaks(points, 10, 3), tier_breaks(list(points), 10, 3))
        self.assertEqual(tier_breaks(points, 6, 2), {3, 6})   # past depth: one last tier

    def test_ranks_and_tiers_per_pool(self):
        weeks = {17: [row(p,17,points=200-p) for p in range(150)]}
        p = aggregate(weeks,2026,17)['players'][4]
        self.assertEqual(p['ranks'], {'FLEX': 5, 'RB': 5})
        self.assertIn('RB', p['tiers'])

    def test_schedule_rates_easier_opponents_higher(self):
        weeks = {17: [row(p,17,opponent='SOFT' if p < 75 else 'HARD') for p in range(150)]}
        result = aggregate(weeks,2026,17)
        completed = {w: [row(900+i,w,points=30,opponent='SOFT') for i in range(3)] +
                        [row(950+i,w,points=5,opponent='HARD') for i in range(3)] for w in (1,2)}
        schedule(result, completed)
        players = {p['id']: p for p in result['players']}
        self.assertGreater(players['0']['schedule'], players['149']['schedule'])
        self.assertEqual({players[str(i)]['schedule'] for i in range(75)}, {players['0']['schedule']})
        self.assertEqual(result['schedule_weeks'], [1, 2])

    def test_movement_needs_an_old_enough_snapshot(self):
        weeks = {17: [row(p,17,points=200-p) for p in range(150)]}
        with tempfile.TemporaryDirectory() as folder:
            history = History(pathlib.Path(folder) / 'h.json')
            first = aggregate(weeks,2026,17)
            history.apply(first, dt.date(2026,10,1))
            self.assertNotIn('moved', first['players'][0])
            weeks[17][0]['stats']['pts_half_ppr'] = 1       # player 0 falls to last
            soon = aggregate(weeks,2026,17)
            history.apply(soon, dt.date(2026,10,3))         # only 2 days later
            self.assertNotIn('movement_since', soon)
            later = aggregate(weeks,2026,17)
            history.apply(later, dt.date(2026,10,7))
            self.assertEqual(later['movement_since'], '2026-10-01')
            moved = {p['id']: p['moved'] for p in later['players']}
            self.assertEqual(moved['0']['RB'], -149)
            self.assertEqual(moved['1']['RB'], 1)

if __name__ == '__main__': unittest.main()
