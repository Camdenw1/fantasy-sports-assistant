import datetime as dt
import pathlib
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import alerts

NOW = dt.datetime(2026, 10, 11, 15, 0, tzinfo=dt.timezone.utc)   # 11am ET Sunday
KICK = '2026-10-11T17:00Z'


def slot(name, injury=None, state='pre', locked=False, rec=None, kickoff=KICK):
    cur = {'id': name, 'name': name, 'injury': injury, 'game_state': state, 'kickoff': kickoff}
    return {'slot': 'RB', 'current': cur, 'recommended': rec or cur, 'change': rec is not None, 'locked': locked}


def report(*slots):
    return {'league': {'name': 'Home League', 'week': 5}, 'slots': list(slots)}


class AlertTests(unittest.TestCase):
    def test_problems_cover_out_bye_empty_and_skip_locked(self):
        bench = {'id': 'b', 'name': 'Bench Back'}
        found = alerts.problems([report(slot('Hurt', 'Out', rec=bench), slot('Idle', state='bye'), slot('Played', 'Out', locked=True),
                                        {'slot': 'FLEX', 'current': None, 'recommended': None, 'change': False, 'locked': False})], NOW)
        messages = [m for _, _, m in found]
        self.assertEqual(len(found), 3)
        self.assertIn('Hurt is OUT', messages[0])
        self.assertIn('Start Bench Back instead.', messages[0])
        self.assertIn('on bye', messages[1])
        self.assertIn('FLEX slot is empty', messages[2])

    def test_questionable_only_inside_ninety_minutes(self):
        self.assertEqual(alerts.problems([report(slot('Maybe', 'Questionable'))], NOW), [])
        soon = NOW + dt.timedelta(minutes=60)
        self.assertEqual(len(alerts.problems([report(slot('Maybe', 'Questionable'))], soon)), 1)

    def test_check_once_notifies_once_and_only_near_kickoff(self):
        sent_messages = []
        games = {'DAL': {'state': 'pre', 'kickoff': KICK}}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(alerts, 'settings', return_value={'sleeper_username': 'someone'}):
            sent = alerts.Sent(pathlib.Path(folder) / 'sent.json')
            run = lambda now: alerts.check_once(lambda: games, lambda u: {'reports': [report(slot('Hurt', 'Out'))]}, sent,
                                                lambda t, m: sent_messages.append(m), now)
            self.assertEqual(run(NOW - dt.timedelta(hours=6)), [])        # nothing within 3 hours
            self.assertEqual(len(run(NOW)), 1)
            self.assertEqual(run(NOW + dt.timedelta(minutes=10)), [])     # already sent
            self.assertEqual(len(sent_messages), 1)

    def test_opt_out_and_missing_username(self):
        for config in ({}, {'sleeper_username': 'x', 'game_day_alerts': False}):
            with mock.patch.object(alerts, 'settings', return_value=config):
                self.assertEqual(alerts.check_once(lambda: self.fail('should not fetch'), None, None), [])


if __name__ == '__main__': unittest.main()
