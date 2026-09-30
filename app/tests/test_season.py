import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from season import aggregate


def row(pid, week, points=10, modified=100):
    return {'player_id': str(pid), 'season': '2026', 'week': week,
            'last_modified': modified, 'company': 'fixture',
            'stats': {'pts_half_ppr': points, 'gp': 1},
            'player': {'first_name': 'Player', 'last_name': str(pid), 'position': 'RB', 'team':'BUF'}}


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

if __name__ == '__main__': unittest.main()
