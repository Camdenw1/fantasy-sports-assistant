import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from trades import ideas


def p(pid, pos, pts):
    return {'id': pid, 'position': pos, 'points': pts}


class TradeTests(unittest.TestCase):
    def setUp(self):
        # Me: deep at RB, weak at WR. Them: deep at WR, weak at RB.
        self.players = [p('r1', 'RB', 150), p('r2', 'RB', 140), p('r3', 'RB', 130), p('w1', 'WR', 60),
                        p('W1', 'WR', 150), p('W2', 'WR', 140), p('R1', 'RB', 55)]
        self.owners = {'r1': 1, 'r2': 1, 'r3': 1, 'w1': 1, 'W1': 2, 'W2': 2, 'R1': 2}

    def test_finds_mutually_helpful_trade(self):
        found = ideas(self.players, self.owners, 1, {2: 'Rival'}, ['RB', 'WR'])
        self.assertTrue(found)
        top = found[0]
        self.assertEqual(top['team'], 'Rival')
        self.assertIn(top['get'][0], {'W1', 'W2'})
        self.assertGreaterEqual(top['my_gain'], 8)
        self.assertGreaterEqual(top['their_gain'], 2)

    def test_no_idea_when_it_only_helps_me(self):
        # They have no RB need: their RB already beats anything I could offer.
        self.players[-1] = p('R1', 'RB', 200)
        found = ideas(self.players, self.owners, 1, {}, ['RB', 'WR'])
        self.assertEqual(found, [])

    def test_lopsided_value_is_rejected(self):
        players = [p('r1', 'RB', 150), p('w1', 'WR', 40), p('W1', 'WR', 200), p('R1', 'RB', 10)]
        owners = {'r1': 1, 'w1': 1, 'W1': 2, 'R1': 2}
        # Giving a 150 RB for a 200 WR is under 85% of value: not offered.
        self.assertEqual(ideas(players, owners, 1, {}, ['RB', 'WR']), [])


if __name__ == '__main__': unittest.main()
