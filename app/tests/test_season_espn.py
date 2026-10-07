import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import season_espn


def sleeper(pid, name, pos='WR', pts=10.0, rec=4):
    first, last = name.split(' ', 1)
    return {'player_id': pid, 'week': 6, 'season': '2026', 'team': 'DAL',
            'player': {'first_name': first, 'last_name': last, 'position': pos},
            'stats': {'pts_half_ppr': pts, 'gp': 1, 'rec': rec, 'rec_yd': 60}}


def espn(name, pos_id=3, week=6, total=14.0, **stats):
    return {'player': {'fullName': name, 'defaultPositionId': pos_id, 'stats': [
        {'seasonId': 2026, 'statSourceId': 1, 'statSplitTypeId': 1, 'scoringPeriodId': week,
         'appliedTotal': total, 'stats': stats}]}}


class EspnBlendTests(unittest.TestCase):
    def blend(self, rows, players, minimum=1):
        old, season_espn.MIN_MATCHED = season_espn.MIN_MATCHED, minimum
        try:
            return season_espn.blend({6: rows}, {'players': players}, 2026)
        finally:
            season_espn.MIN_MATCHED = old

    def test_averages_stats_and_half_ppr(self):
        weekly, matched = self.blend([sleeper('1', 'CeeDee Lamb')], [espn('CeeDee Lamb', **{'53': 8, '42': 100})])
        stats = weekly[6][0]['stats']
        self.assertEqual(matched, 1)
        self.assertEqual(stats['rec'], 6)
        self.assertEqual(stats['rec_yd'], 80)
        self.assertAlmostEqual(stats['pts_half_ppr'], (10 + 14) / 2)   # ESPN half-PPR: 4 + 10

    def test_names_normalize_and_position_must_match(self):
        weekly, matched = self.blend([sleeper('1', 'Marvin Harrison Jr.'), sleeper('2', 'Josh Allen', 'QB')],
                                     [espn('Marvin Harrison', **{'53': 4}), espn('Josh Allen', pos_id=2)])
        self.assertEqual(matched, 1)
        self.assertEqual(weekly[6][1]['stats']['pts_half_ppr'], 10.0)

    def test_ambiguous_and_zero_weeks_are_ignored(self):
        _, matched = self.blend([sleeper('1', 'Mike Williams')],
                                [espn('Mike Williams', **{'53': 5}), espn('Mike Williams', **{'53': 2})])
        self.assertEqual(matched, 0)
        _, matched = self.blend([sleeper('1', 'Zay Flowers')], [espn('Zay Flowers', total=0)])
        self.assertEqual(matched, 0)

    def test_too_few_matches_falls_back_to_sleeper(self):
        rows = [sleeper('1', 'Zay Flowers')]
        weekly, matched = self.blend(rows, [espn('Zay Flowers', **{'53': 9})], minimum=2)
        self.assertEqual(matched, 0)
        self.assertIs(weekly[6], rows)


if __name__ == '__main__': unittest.main()
