#!/usr/bin/env python3
"""Local, read-only bridge from the start/sit engine to the first dashboard view."""

import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINE = ROOT / "prototypes" / "start-sit" / "startsit.py"
SAMPLE = ROOT / "prototypes" / "start-sit" / "sample-output-week3-whatif.json"
PLAYER_CACHE = ROOT / "prototypes" / "start-sit" / ".cache" / "players_nfl.json"
UA = {"User-Agent": "fantasy-sports-assistant/local-dashboard"}
USERNAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
LEAGUE_ID = re.compile(r"^[0-9]{1,24}$")


def fetch_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as response:
        return json.load(response)


def discover(username):
    if not USERNAME.fullmatch(username):
        raise ValueError("Enter a Sleeper username (letters, numbers, _ or -).")
    state = fetch_json("https://api.sleeper.app/v1/state/nfl")
    season = str(state["season"])
    user = fetch_json("https://api.sleeper.app/v1/user/" + username)
    if not user or not user.get("user_id"):
        raise ValueError("Sleeper username not found.")
    leagues = fetch_json(
        "https://api.sleeper.app/v1/user/" + user["user_id"] + "/leagues/nfl/" + season
    )
    return {
        "username": user.get("display_name") or username,
        "season": season,
        "week": int(state.get("display_week") or state["week"]),
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "leagues": [
            {"id": item["league_id"], "name": item["name"], "status": item.get("status")}
            for item in leagues
        ],
    }


def report(username, league_id, week=None):
    if not USERNAME.fullmatch(username):
        raise ValueError("Invalid Sleeper username.")
    if not LEAGUE_ID.fullmatch(league_id):
        raise ValueError("Invalid Sleeper league ID.")
    if week is not None and (not isinstance(week, int) or not 1 <= week <= 18):
        raise ValueError("Week must be between 1 and 18.")
    with tempfile.TemporaryDirectory(prefix="fantasy-lineup-") as temp:
        output = pathlib.Path(temp) / "report.json"
        cmd = [sys.executable, str(ENGINE), username, "--league", league_id,
               "--json", str(output)]
        if week is not None:
            cmd += ["--week", str(week)]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
        if result.returncode or not output.exists():
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise RuntimeError(detail[-1] if detail else "Start/sit data unavailable.")
        data = json.loads(output.read_text())
    if isinstance(data, list):
        raise ValueError("No roster found for this username in that league.")
    if str(data["league"]["id"]) != league_id:
        raise RuntimeError("Sleeper returned a different league.")
    cache_time = (dt.datetime.fromtimestamp(PLAYER_CACHE.stat().st_mtime, dt.timezone.utc)
                  .isoformat() if PLAYER_CACHE.exists() else None)
    return {"report": data, "freshness": {
        "roster_fetched_at": data["generated_at"],
        "player_list_fetched_at": cache_time,
        "projections_fetched_at": data["generated_at"],
    }}


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/leagues":
            try:
                self.reply(200, discover(parse_qs(parsed.query).get("username", [""])[0]))
            except ValueError as exc:
                self.reply(400, {"error": str(exc)})
            except (urllib.error.URLError, TimeoutError, KeyError) as exc:
                self.reply(502, {"error": "Sleeper league lookup failed: " + str(exc)})
            return
        if parsed.path == "/api/sample":
            data = json.loads(SAMPLE.read_text())
            self.reply(200, {"report": data, "sample": True,
                             "freshness": {"roster_fetched_at": data["generated_at"],
                                           "player_list_fetched_at": data["generated_at"],
                                           "projections_fetched_at": data["generated_at"]}})
            return
        if parsed.path in {"/draft-board-2026.html", "/board-data.js"}:
            path = ROOT / parsed.path.lstrip("/")
        else:
            path = (HERE / ("index.html" if parsed.path == "/" else parsed.path.lstrip("/"))).resolve()
        if (path.parent not in {HERE, ROOT} or not path.is_file()
                or path.suffix not in {".html", ".css", ".js"}):
            self.send_error(404)
            return
        content_type = {".html": "text/html", ".css": "text/css",
                        ".js": "text/javascript"}[path.suffix]
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/api/lineup":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024:
                raise ValueError("Invalid request size.")
            payload = json.loads(self.rfile.read(size))
            self.reply(200, report(payload.get("username", ""),
                                   str(payload.get("league_id", "")), payload.get("week")))
        except (ValueError, json.JSONDecodeError) as exc:
            self.reply(400, {"error": str(exc)})
        except subprocess.TimeoutExpired:
            self.reply(504, {"error": "The lineup calculation timed out. Try again."})
        except Exception as exc:
            self.reply(502, {"error": "Lineup calculation failed: " + str(exc)})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("Fantasy Sports Assistant at http://127.0.0.1:" + str(port))
    print("Local only; press Ctrl-C to stop.")
    server.serve_forever()
