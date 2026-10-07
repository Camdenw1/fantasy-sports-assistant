"""Game-day Mac notifications for lineup problems, so nobody has to remember to check.

Runs inside the local service. Only when an NFL game kicks off within the next few
hours does it build the lineup report for the Sleeper username in the git-ignored
local-settings.json, and it notifies once per problem: a starter ruled out, on bye or
doubtful, an empty slot, or a questionable starter 90 minutes before his kickoff.
Opt out with {"game_day_alerts": false} in local-settings.json.
"""
import datetime as dt
import json
import pathlib
import subprocess
import threading
import time
import uuid

SETTINGS = pathlib.Path(__file__).resolve().parents[1] / 'local-settings.json'
LOOKAHEAD = dt.timedelta(hours=3)
QUESTIONABLE_WINDOW = dt.timedelta(minutes=90)
PROBLEM = {'Out', 'IR', 'PUP', 'Sus', 'Doubtful'}


def settings():
    try:
        data = json.loads(SETTINGS.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def when(iso):
    return dt.datetime.fromisoformat(iso.replace('Z', '+00:00')) if iso else None


def kickoff_soon(games, now):
    return any(g['state'] == 'pre' and g.get('kickoff') and now <= when(g['kickoff']) <= now + LOOKAHEAD
               for g in games.values())


def problems(reports, now):
    """(key, title, message) for each unlocked starter problem worth a notification."""
    out = []
    for report in reports:
        league, week = report['league']['name'], report['league']['week']
        for row in report.get('slots') or []:
            if row.get('locked'):
                continue
            cur, rec = row.get('current'), row.get('recommended')
            fix = (' Start ' + rec['name'] + ' instead.') if row.get('change') and rec and (not cur or rec['id'] != cur['id']) else ''
            kickoff = when((cur or {}).get('kickoff'))
            local = kickoff.astimezone().strftime('%-I:%M %p') if kickoff else None
            if not cur:
                out.append((f"{league}:{week}:{row['slot']}:empty", league, f"Your {row['slot']} slot is empty.{fix}"))
            elif cur.get('game_state') == 'bye':
                out.append((f"{league}:{week}:{cur['id']}:bye", league, f"{cur['name']} is on bye this week.{fix}"))
            elif cur.get('injury') in PROBLEM:
                out.append((f"{league}:{week}:{cur['id']}:{cur['injury']}", league,
                            f"{cur['name']} is {cur['injury'].upper()}" + (f" — kickoff {local}." if local else '.') + fix))
            elif cur.get('injury') == 'Questionable' and kickoff and now <= kickoff <= now + QUESTIONABLE_WINDOW:
                out.append((f"{league}:{week}:{cur['id']}:Q", league,
                            f"{cur['name']} is questionable, kickoff {local}. Check inactives before lock." + fix))
    return out


def notify(title, message):
    script = 'display notification {} with title "Fantasy" subtitle {} sound name "Glass"'.format(
        json.dumps(message), json.dumps(title))
    subprocess.run(['osascript', '-e', script], capture_output=True, timeout=10)


class Sent:
    def __init__(self, path):
        self.path = pathlib.Path(path)

    def load(self):
        try:
            return set(json.loads(self.path.read_text()))
        except (OSError, ValueError, TypeError):
            return set()

    def save(self, keys):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(sorted(keys)[-500:]))
        temporary.replace(self.path)


def check_once(games_fn, report_fn, sent, send=notify, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    config = settings()
    username = config.get('sleeper_username')
    if not username or config.get('game_day_alerts') is False:
        return []
    if not kickoff_soon(games_fn(), now):
        return []
    done = sent.load()
    fresh = [p for p in problems(report_fn(username).get('reports') or [], now) if p[0] not in done]
    for key, title, message in fresh:
        send(title, message)
        done.add(key)
    if fresh:
        sent.save(done)
    return fresh


def start(games_fn, report_fn, sent_path, interval=600):
    sent = Sent(sent_path)

    def loop():
        while True:
            try:
                check_once(games_fn, report_fn, sent)
            except Exception:
                pass
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True, name='game-day-alerts').start()
