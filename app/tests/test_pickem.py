import datetime as dt
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pickem


def board(spread=-2.5, state='pre', kickoff='2026-10-11T17:00Z'):
    team = lambda abbr, side, score: {'homeAway': side, 'score': score, 'team': {'abbreviation': abbr, 'shortDisplayName': abbr}}
    return {'events': [{'id': '1', 'date': kickoff, 'competitions': [{
        'status': {'type': {'state': state, 'shortDetail': 'Sun 1:00 PM', 'completed': state == 'post'}},
        'competitors': [team('LAR', 'home', '0'), team('SF', 'away', '0')],
        'odds': [{'spread': spread, 'provider': {'name': 'Draft Kings'}}]}]}]}


class PickemTests(unittest.TestCase):
    def test_value_rules_from_skill(self):
        # Start Rams -2.5, now -3.5: market moved toward the home Rams; crosses 3.
        self.assertEqual(pickem.value(-2.5, -3.5), {'move': -1.0, 'side': 'home', 'strength': 'Strong'})
        # Start X +3, now +7 (home): value is the away side; lands on 3 and 7.
        self.assertEqual(pickem.value(3, 7)['side'], 'away')
        self.assertEqual(pickem.value(-8.5, -9)['strength'], 'Minor')
        self.assertEqual(pickem.value(-8.5, -10)['strength'], 'Solid')
        self.assertEqual(pickem.value(-1, -1), {'move': 0, 'side': None, 'strength': None})
        self.assertIsNone(pickem.value(None, -3))

    def test_line_text(self):
        self.assertEqual(pickem.line_text('LAR', 'SF', -2.5), 'LAR -2.5')
        self.assertEqual(pickem.line_text('LAR', 'SF', 3), 'SF -3')
        self.assertEqual(pickem.line_text('LAR', 'SF', 0), 'PK')

    def test_lock_is_tuesday_morning_eastern(self):
        games = pickem.games(board(kickoff='2026-10-09T00:15Z'))   # Thursday night game
        self.assertEqual(pickem.lock_time(games).isoformat(), '2026-10-06T10:00:00-04:00')

    def test_lines_captured_once_after_lock_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            store = pickem.LockStore(pathlib.Path(folder) / 'locks.json')
            fetch = lambda spread: (lambda url: board(spread))
            monday = dt.datetime(2026, 10, 5, 18, tzinfo=dt.timezone.utc)
            self.assertIsNone(pickem.build(fetch(-2.5), store, 2026, 5, monday)['games'][0]['spread_lock'])
            tuesday = dt.datetime(2026, 10, 6, 15, tzinfo=dt.timezone.utc)   # 11am ET
            first = pickem.build(fetch(-2.5), store, 2026, 5, tuesday)
            self.assertEqual(first['games'][0]['spread_lock'], -2.5)
            self.assertFalse(first['lock']['approximate'])
            later = pickem.build(fetch(-3.5), store, 2026, 5, tuesday + dt.timedelta(days=2))
            game = later['games'][0]
            self.assertEqual((game['spread_lock'], game['spread_now']), (-2.5, -3.5))
            self.assertEqual(game['value']['strength'], 'Strong')
            self.assertEqual(game['lock_text'], 'LAR -2.5')

    def test_late_capture_is_flagged_approximate(self):
        with tempfile.TemporaryDirectory() as folder:
            store = pickem.LockStore(pathlib.Path(folder) / 'locks.json')
            saturday = dt.datetime(2026, 10, 10, 15, tzinfo=dt.timezone.utc)
            self.assertTrue(pickem.build(lambda url: board(), store, 2026, 5, saturday)['lock']['approximate'])


if __name__ == '__main__': unittest.main()
