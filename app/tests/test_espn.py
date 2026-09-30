"""Safety and roster completeness checks for the read-only ESPN adapter."""
import sys
import pathlib
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from espn import import_league, normalize, parse_url

class ImportTests(unittest.TestCase):
    def test_untrusted_url_never_fetched(self):
        for url in ('http://fantasy.espn.com/football/team?leagueId=1',
                    'https://evil.example/football/team?leagueId=1',
                    'https://fantasy.espn.com/basketball/team?leagueId=1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                import_league(url, None, lambda _: self.fail('Untrusted URL fetched'))

    def test_url_ids_and_team_choice(self):
        self.assertEqual(parse_url('https://fantasy.espn.com/football/team?leagueId=123&teamId=2&seasonId=2026'), ('123', 2, 2026))
        self.assertTrue(normalize({'teams': [{'id': 2, 'name': 'Team'}]}, '123', None, 2026)['needs_team'])

    def test_bench_missing_slot_and_unknown_injury(self):
        data = {'scoringPeriodId': 4, 'settings': {'name': 'League', 'rosterSettings': {'lineupSlotCounts': {'0': 1, '2': 2, '20': 6}}},
                'teams': [{'id': 2, 'name': 'Team', 'roster': {'entries': [
                    {'lineupSlotId': 0, 'playerPoolEntry': {'player': {'id': 10, 'fullName': 'QB'}}},
                    {'lineupSlotId': 2, 'playerPoolEntry': {'player': {'id': 11, 'fullName': 'RB', 'injuryStatus': 'ACTIVE'}}},
                    {'lineupSlotId': 20, 'playerPoolEntry': {'player': {'id': 12, 'fullName': 'Bench', 'injuryStatus': 'OUT'}}}]}}]}
        snapshot = normalize(data, '123', 2, 2026)['snapshot']
        self.assertEqual(snapshot['week'], 4)
        self.assertEqual(len(snapshot['starters']), 3)
        self.assertEqual(snapshot['starters'][0]['status'], 'Unknown')
        self.assertEqual(snapshot['starters'][-1]['status'], 'Empty')
        self.assertEqual([r['player'] for r in snapshot['bench']], ['Bench'])

    def test_missing_roster_not_silently_imported(self):
        with self.assertRaises(ValueError): normalize({'teams': [{'id': 1}]}, '123', 1, 2026)

if __name__ == '__main__': unittest.main()
