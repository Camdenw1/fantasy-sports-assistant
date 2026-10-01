#!/usr/bin/env python3
"""Start/sit prototype for Sleeper leagues -- stdlib only, read-only.

    python3 prototypes/start-sit/startsit.py                     # your leagues (username from local-settings.json), current week
    python3 prototypes/start-sit/startsit.py SOME_USERNAME --week 4 --league LEAGUE_ID
    python3 prototypes/start-sit/startsit.py --json out.json

Pipeline (see docs/product/start-sit.md for the design):
  1. Sleeper: state -> user -> leagues -> league (slots + scoring) -> rosters ->
     matchups/{week} (current starters, opponent, points already scored) -> players.
  2. Projections: Sleeper weekly (raw stat lines, all positions) + ESPN weekly
     (raw stat lines, QB/RB/WR/TE), joined through Sleeper's espn_id.
  3. Schedule: ESPN scoreboard (kickoff time, live state, spread/total) with
     Sleeper's schedule as fallback for game status; no game => bye.
  4. Rescore every simulated stat line under THIS league's scoring_settings,
     Monte Carlo per player (game-script factor + per-stat noise + source mixture)
     -> mean / p10 / p50 / p90, including step-function yardage bonuses.
  5. Optimise: locked players stay put; exact assignment (Hungarian) over the
     open slots; then a second pass re-seats the chosen starters so GTD and
     late-kickoff players sit in the most flexible slots.
  6. Emit the platform-neutral contract (schema "startsit/v1").

Never writes to Sleeper. Setting a lineup needs an authenticated session.
"""
import uuid
import hashlib
import argparse
import datetime as dt
import json
import math
import pathlib
import random
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).parent
CACHE = HERE / ".cache"
UA = {"User-Agent": "fantasy-sports-assistant/start-sit-prototype"}
SIMS = 4000
RNG = random.Random(20260925)

# -------------------------------------------------------------------- fetch --
def get(url, headers=None, timeout=15, cache_s=0, ua=True):
    key = None
    if cache_s:
        CACHE.mkdir(exist_ok=True)
        key = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if key.exists() and time.time() - key.stat().st_mtime < cache_s:
            try: return json.loads(key.read_text())
            except (ValueError, OSError): pass
    req = urllib.request.Request(url, headers={**(UA if ua else {}), **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
    data = json.loads(body)
    if key:
        temporary = key.with_name(key.name + "." + uuid.uuid4().hex + ".tmp")
        temporary.write_text(body)
        temporary.replace(key)
    return data


SL = "https://api.sleeper.app/v1"


def sleeper_players():
    # ~5 MB; Sleeper asks callers to fetch it at most once a day.
    # hash() is salted per process, so use a fixed filename for this one.
    CACHE.mkdir(exist_ok=True)
    f = CACHE / "players_nfl.json"
    if f.exists() and time.time() - f.stat().st_mtime < 24 * 3600:
        try: return json.loads(f.read_text())
        except (ValueError, OSError): pass
    d = get(f"{SL}/players/nfl", timeout=30)
    temporary = f.with_name(f.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(d))
    temporary.replace(f)
    return d


def sleeper_week_proj(season, week):
    out = {}
    q = "&".join(f"position[]={p}" for p in ("QB", "RB", "WR", "TE", "K", "DEF"))
    rows = get(f"https://api.sleeper.app/projections/nfl/{season}/{week}"
               f"?season_type=regular&{q}")
    for r in rows:
        st = {k: float(v) for k, v in (r.get("stats") or {}).items()
              if isinstance(v, (int, float)) and not k.startswith(("adp", "pos_adp", "pts_"))}
        if st:
            out[r["player_id"]] = {"stats": st, "opp": r.get("opponent"),
                                   "company": r.get("company")}
    return out


ESPN_TO_SLEEPER = {"0": "pass_att", "1": "pass_cmp", "3": "pass_yd", "4": "pass_td",
                   "20": "pass_int", "23": "rush_att", "24": "rush_yd", "25": "rush_td",
                   "53": "rec", "42": "rec_yd", "43": "rec_td", "58": "rec_tgt",
                   "72": "fum_lost"}


def espn_week_proj(season, week):
    """ESPN weekly projections from the public leaguedefaults view (no auth).
    Raw stat lines only -- appliedTotal is ESPN default scoring, useless here."""
    filt = {"players": {"filterStatsForTopScoringPeriodIds": {
        "value": 2, "additionalValue": [f"11{season}{week}"]},
        "filterSlotIds": {"value": [0, 2, 4, 6]}, "limit": 700,
        "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
    d = get(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
            f"/segments/0/leaguedefaults/3?scoringPeriodId={week}&view=kona_player_info",
            headers={"x-fantasy-filter": json.dumps(filt), "accept": "application/json"})
    out = {}
    for pl in d.get("players", []):
        p = pl.get("player", pl)
        for s in p.get("stats") or []:
            if s.get("statSourceId") == 1 and s.get("scoringPeriodId") == week:
                st = {ESPN_TO_SLEEPER[k]: float(v) for k, v in (s.get("stats") or {}).items()
                      if k in ESPN_TO_SLEEPER}
                if st:
                    out[str(p["id"])] = st
                    pos = ESPN_POS.get(p.get("defaultPositionId"))
                    out[("name", norm(p.get("fullName", "")), pos)] = st
    return out


ESPN_POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}


def norm(name):
    """Join key when Sleeper lacks espn_id (true for most recent draftees)."""
    n = "".join(ch for ch in name.lower() if ch.isalnum() or ch == " ")
    parts = [w for w in n.split() if w not in ("jr", "sr", "ii", "iii", "iv", "v")]
    return " ".join(parts)


ESPN_ABBR = {"WSH": "WAS", "JAC": "JAX"}


def schedule(season, week):
    """team -> {kickoff (UTC datetime), state pre|in|post, opp, home, spread, total}"""
    games = {}
    try:
        d = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
                f"?dates={season}&seasontype=2&week={week}", ua=False)  # 403s custom UAs
        for e in d.get("events", []):
            c = e["competitions"][0]
            ko = dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            state = e["status"]["type"]["state"]
            odds = (c.get("odds") or [{}])[0]
            teams = {}
            for t in c["competitors"]:
                ab = t["team"]["abbreviation"]
                teams[ESPN_ABBR.get(ab, ab)] = t["homeAway"]
            ab = list(teams)
            for i, tm in enumerate(ab):
                games[tm] = {"kickoff": ko, "state": state, "opp": ab[1 - i],
                             "home": teams[tm] == "home",
                             "total": odds.get("overUnder"), "line": odds.get("details")}
    except Exception as ex:  # noqa: BLE001
        print(f"  ! ESPN scoreboard unavailable ({ex}); using Sleeper schedule", file=sys.stderr)
    source = "espn scoreboard"
    if not games:
        source = "sleeper schedule (kickoff unavailable)"
        for g in get(f"https://api.sleeper.app/schedule/nfl/regular/{season}"):
            if g["week"] != week:
                continue
            st = {"pre_game": "pre", "in_game": "in", "complete": "post"}.get(g["status"], "pre")
            for tm, op, h in ((g["home"], g["away"], True), (g["away"], g["home"], False)):
                games[tm] = {"kickoff": None, "state": st, "opp": op, "home": h,
                             "total": None, "line": None}
    return games, source


def implied_total(g, team):
    """Vegas implied team total from ESPN's 'FAV -x.5' + over/under."""
    if not g or not g.get("total") or not g.get("line"):
        return None
    try:
        fav, spread = g["line"].split()
        spread = abs(float(spread))
    except ValueError:
        return g["total"] / 2
    fav = ESPN_ABBR.get(fav, fav)
    return round(g["total"] / 2 + (spread / 2 if fav == team else -spread / 2), 1)


# ----------------------------------------------------------- simulate/score --
YARD_CV = {"pass_yd": 0.24, "rush_yd": 0.55, "rec_yd": 0.62}
FG_MID = {"fgm_0_19": 18, "fgm_20_29": 25, "fgm_30_39": 35, "fgm_40_49": 45,
          "fgm_50_59": 53, "fgm_50p": 54, "fgm_60p": 62}
PA_TIERS = [(0, 0, "pts_allow_0"), (1, 6, "pts_allow_1_6"), (7, 13, "pts_allow_7_13"),
            (14, 20, "pts_allow_14_20"), (21, 27, "pts_allow_21_27"),
            (28, 34, "pts_allow_28_34"), (35, 999, "pts_allow_35p")]
YA_TIERS = [(0, 99, "yds_allow_0_100"), (100, 199, "yds_allow_100_199"),
            (200, 299, "yds_allow_200_299"), (300, 349, "yds_allow_300_349"),
            (350, 399, "yds_allow_350_399"), (400, 449, "yds_allow_400_449"),
            (450, 499, "yds_allow_450_499"), (500, 549, "yds_allow_500_549"),
            (550, 9999, "yds_allow_550p")]
SKIP = {"gp", "cmp_pct", "pts_allow", "yds_allow"} | {t[2] for t in PA_TIERS + YA_TIERS}


def poisson(lam):
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, round(RNG.gauss(lam, math.sqrt(lam))))
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= RNG.random()
        if p <= L:
            return k
        k += 1


def gamma_mean(mu, cv):
    if mu <= 0:
        return 0.0
    k = 1 / (cv * cv)
    return RNG.gammavariate(k, mu / k)


def sim_line(st, pos):
    """One simulated game from a projected mean stat line."""
    out = {}
    if pos == "DEF":
        pa = max(0, round(RNG.gauss(st.get("pts_allow", 21), 9.5)))
        ya = max(0, round(RNG.gauss(st.get("yds_allow", 330), 60)))
        out["_pa"], out["_ya"] = pa, ya
        for k, v in st.items():
            if k not in SKIP and not k.endswith("_yd"):
                out[k] = poisson(v)
            elif k.endswith("_yd"):
                out[k] = gamma_mean(v, 0.6)
        return out
    u = math.exp(RNG.gauss(-0.02, 0.2))          # shared game-script factor
    for k, v in st.items():
        if k in SKIP:
            continue
        if k in YARD_CV:
            cv = 0.75 if (k == "rush_yd" and pos == "QB") else YARD_CV[k]
            out[k] = gamma_mean(v * u, cv)
        elif k.endswith(("_att", "_cmp", "_inc", "_tgt")):
            out[k] = v * u
        else:
            out[k] = poisson(v * u)
    return out


def score(line, pos, S):
    """Apply a Sleeper scoring_settings dict to one simulated line."""
    pts = 0.0
    for k, v in line.items():
        if k.startswith("_"):
            continue
        if k.startswith("fgm_") and k in FG_MID:
            kk = k
            if k == "fgm_50p" and not S.get("fgm_50p"):
                kk = "fgm_50_59"              # league scores 50-59 / 60+ separately
            pts += S.get(kk, 0) * v + S.get("fgm", 0) * v
            pts += S.get("fgm_yds", 0) * FG_MID[k] * v
            pts += S.get("fgm_yds_over_30", 0) * max(0, FG_MID[k] - 30) * v
            continue
        if k.startswith("fgmiss_"):
            pts += (S.get(k, 0) or S.get("fgmiss", 0)) * v
            continue
        if k in ("fgm_yds", "fga", "fgm", "xpa"):
            continue
        pts += S.get(k, 0) * v
    if pos == "TE":
        pts += S.get("bonus_rec_te", 0) * line.get("rec", 0)
    elif pos == "RB":
        pts += S.get("bonus_rec_rb", 0) * line.get("rec", 0)
    elif pos == "WR":
        pts += S.get("bonus_rec_wr", 0) * line.get("rec", 0)
    if pos == "QB":
        pts += S.get("bonus_rush_td_qb", 0) * line.get("rush_td", 0)
    # yardage bonuses: exclusive tiers (verified for Camden's league; Sleeper
    # pays the highest tier reached)
    def tier(y, lo_key, hi_key, lo, hi):
        if y >= hi and S.get(hi_key):
            return S[hi_key]
        return S.get(lo_key, 0) if y >= lo else 0
    ry, cy, py = line.get("rush_yd", 0), line.get("rec_yd", 0), line.get("pass_yd", 0)
    pts += tier(ry, "bonus_rush_yd_100", "bonus_rush_yd_200", 100, 200)
    pts += tier(cy, "bonus_rec_yd_100", "bonus_rec_yd_200", 100, 200)
    pts += tier(py, "bonus_pass_yd_300", "bonus_pass_yd_400", 300, 400)
    pts += tier(ry + cy, "bonus_rush_rec_yd_100", "bonus_rush_rec_yd_200", 100, 200)
    if pos == "DEF":
        for lo, hi, key in PA_TIERS:
            if lo <= line["_pa"] <= hi:
                pts += S.get(key, 0)
        for lo, hi, key in YA_TIERS:
            if lo <= line["_ya"] <= hi:
                pts += S.get(key, 0)
        pts += S.get("pts_allow", 0) * line["_pa"] + S.get("yds_allow", 0) * line["_ya"]
    return pts


def simulate(lines, pos, S, n=SIMS):
    """lines: list of per-source mean stat lines; each sim draws one source
    (so source disagreement widens the band) then simulates a game."""
    return sorted(score(sim_line(lines[i % len(lines)], pos), pos, S) for i in range(n))


def q(s, p):
    return s[min(len(s) - 1, int(p * len(s)))]


# --------------------------------------------------------------- optimiser --
SLOT_ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "K": {"K"},
             "DEF": {"DEF"}, "FLEX": {"RB", "WR", "TE"}, "REC_FLEX": {"WR", "TE"},
             "WRRB_FLEX": {"WR", "RB"}, "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
             "DL": {"DL", "DE", "DT"}, "LB": {"LB"}, "DB": {"DB", "CB", "S"},
             "IDP_FLEX": {"DL", "DE", "DT", "LB", "DB", "CB", "S"}}
PLAY_PROB = {None: 1.0, "Questionable": 0.80, "Doubtful": 0.20, "Out": 0.0, "IR": 0.0,
             "PUP": 0.0, "Sus": 0.0, "NA": 0.0, "DNR": 0.0, "COV": 0.0}


def hungarian(cost):
    """Min-cost assignment, rows <= cols. Returns col index per row."""
    if not cost:
        return []
    n, m = len(cost), len(cost[0])
    INF = float("inf")
    u, v, p, way = [0.0] * (n + 1), [0.0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [INF] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    res = [None] * n
    for j in range(1, m + 1):
        if p[j]:
            res[p[j] - 1] = j - 1
    return res


def assign(slots, pool, weight):
    """slots: [slot_name]; pool: [player dict]; weight(slot, player) -> float or None
    (None = ineligible). Pads with empty 'players' so every slot is fillable."""
    cols = pool + [None] * len(slots)
    BIG = 1e6
    cost = []
    for s in slots:
        row = []
        for pl in cols:
            if pl is None:
                row.append(BIG / 2)            # empty slot: legal but last resort
            else:
                w = weight(s, pl)
                row.append(BIG if w is None else -w)
        cost.append(row)
    return [cols[j] for j in hungarian(cost)]


def choose_starters(slots, pool):
    return assign(slots, pool, lambda slot, player: player['value'] if eligible(slot, player) else None)


def eligible(slot, pl):
    return bool(SLOT_ELIG.get(slot, {slot}) & set(pl["elig"]))


def flexibility(slot):
    return len(SLOT_ELIG.get(slot, {slot}))


# ------------------------------------------------------------------- build --
def run_league(lg, week, me_id, P, sproj, eproj, games, now, schedule_source="espn scoreboard"):
    S = lg["scoring_settings"]
    lid = lg["league_id"]
    all_slots = lg["roster_positions"]
    slots = [s for s in all_slots if s not in ("BN", "IR", "TAXI")]
    rosters = get(f"{SL}/league/{lid}/rosters")
    users = {u["user_id"]: u for u in get(f"{SL}/league/{lid}/users")}
    mine = next((r for r in rosters if r["owner_id"] == me_id
                 or me_id in (r.get("co_owners") or [])), None)
    if not mine:
        return None
    mus = get(f"{SL}/league/{lid}/matchups/{week}")
    mm = next((m for m in mus if m["roster_id"] == mine["roster_id"]), None)
    opp = next((m for m in mus if mm and m["matchup_id"] == mm["matchup_id"]
                and m["roster_id"] != mine["roster_id"]), None) if mm else None
    current = list((mm or {}).get("starters") or mine.get("starters") or [])
    pp = (mm or {}).get("players_points") or {}
    reserve = set(mine.get("reserve") or []) | set(mine.get("taxi") or [])
    espn_by_sleeper = {pid: str(p.get("espn_id")) for pid, p in P.items() if p.get("espn_id")}

    def player(pid, points_so_far=None):
        p = P.get(pid, {})
        pos = p.get("position") or ("DEF" if pid.isalpha() else "?")
        team = p.get("team") or (pid if pos == "DEF" else None)
        g = games.get(team)
        inj = p.get("injury_status")
        lines = []
        if pid in sproj:
            lines.append(sproj[pid]["stats"])
        e = (eproj.get(espn_by_sleeper.get(pid, ""))
             or eproj.get(("name", norm(p.get("full_name") or ""), pos)))
        if e and pos in ("QB", "RB", "WR", "TE"):
            lines.append(e)
        sims = simulate(lines, pos, S) if lines else [0.0] * 10
        mean = sum(sims) / len(sims)
        pplay = PLAY_PROB.get(inj, 1.0)
        state = g["state"] if g else "bye"
        locked = state in ("in", "post")
        actual = (points_so_far or {}).get(pid)
        if state == "bye":
            pplay = 0.0
        value = mean * pplay
        if state == "post" and actual is not None:
            value = actual
        elif state == "in" and actual is not None:
            value = actual + 0.5 * mean
        return {"id": pid, "name": p.get("full_name") or (f"{team} D/ST" if pos == "DEF" else pid),
                "pos": pos, "elig": p.get("fantasy_positions") or [pos], "team": team,
                "opp": g["opp"] if g else None,
                "kickoff": g["kickoff"] if g else None, "game_state": state,
                "implied_total": implied_total(g, team) if g else None,
                "injury": inj, "injury_body_part": p.get("injury_body_part"),
                "play_prob": pplay, "locked": locked, "actual": actual,
                "sources": len(lines), "_sims": sims,
                "proj": {"mean": round(mean, 2), "p10": round(q(sims, .1), 1),
                         "p50": round(q(sims, .5), 1), "p90": round(q(sims, .9), 1)},
                "value": round(value, 2)}

    roster_ids = [x for x in (mine.get("players") or []) if x not in reserve]
    roster_ids += [x for x in current if x and x != "0" and x not in roster_ids]  # past weeks: since-dropped starters
    pl = {pid: player(pid, pp) for pid in roster_ids}
    cur = [pl.get(pid) if pid and pid != "0" else None for pid in current]
    cur += [None] * (len(slots) - len(cur))

    # locked starters stay; locked bench players cannot come in
    fixed = {i: c for i, c in enumerate(cur) if c and c["locked"]}
    open_idx = [i for i in range(len(slots)) if i not in fixed]
    pool = [x for x in pl.values() if not x["locked"] and x["id"] not in
            {c["id"] for c in fixed.values()}]

    # Choose the legal lineup by injury-adjusted expected points. A speculative
    # late-swap hedge used to credit a questionable player with another starter's
    # points, double-counting an unavailable backup and selecting worse lineups.
    open_slots = [slots[i] for i in open_idx]
    first = choose_starters(open_slots, pool)
    chosen = [x for x in first if x]
    # pass 2: same starters, re-seated -- points are unchanged, so optimise
    # (a) GTD players into the widest slot (a flex can be backfilled by more
    # positions at inactives), (b) otherwise leave players where they are
    # (churn is noise to the user), (c) latest kickoff into flex as a tiebreak.
    t0 = min((x["kickoff"] for x in chosen if x["kickoff"]), default=None)
    was = {c["id"]: slots[i] for i, c in enumerate(cur) if c}
    def seat(s, x):
        if not eligible(s, x):
            return None
        late = ((x["kickoff"] - t0).total_seconds() / 3600) if (x["kickoff"] and t0) else 0
        gtd = 100 if x["injury"] == "Questionable" else 0
        stay = 50 if was.get(x["id"]) == s else 0
        return (gtd + 0.5 * late) * flexibility(s) + stay
    seated = assign(open_slots, chosen, seat)
    rec = list(cur)
    for i, x in zip(open_idx, seated):
        rec[i] = x
    # identical slot names are interchangeable: keep a continuing starter on
    # his original row so the UI doesn't show a phantom WR1 <-> WR2 move.
    for i in open_idx:
        c = cur[i]
        if not c or (rec[i] and rec[i]["id"] == c["id"]):
            continue
        for j in open_idx:
            if j != i and slots[j] == slots[i] and rec[j] and rec[j]["id"] == c["id"]:
                rec[i], rec[j] = rec[j], rec[i]
                break

    # ---- per-slot contract rows
    def ref(x):
        if not x:
            return None
        return {k: (v.isoformat() if isinstance(v, dt.datetime) else v)
                for k, v in x.items() if not k.startswith("_") and k != "elig"} | {
            "eligible_positions": x["elig"]}

    def p_better(a, b):
        sa, sb = a["_sims"], b["_sims"]
        pa, pb = a["play_prob"], b["play_prob"]
        n = min(len(sa), len(sb))
        wins = 0
        for i in range(n):
            va = sa[RNG.randrange(n)] if RNG.random() < pa else 0
            vb = sb[RNG.randrange(n)] if RNG.random() < pb else 0
            wins += va > vb
        return wins / n

    rows, alerts = [], []
    cur_ids = {c["id"] for c in cur if c}
    rec_ids = {r["id"] for r in rec if r}
    for i, s in enumerate(slots):
        c, r = cur[i], rec[i]
        row = {"slot_index": i, "slot": s, "eligible": sorted(SLOT_ELIG.get(s, {s})),
               "current": ref(c), "recommended": ref(r),
               "change": (c or {}).get("id") != (r or {}).get("id"),
               "locked": i in fixed}
        if i in fixed:
            row.update(action="locked", reason=f"Locked -- {c['team']} game {c['game_state']}")
        elif not row["change"]:
            why = f"{r['injury']} ({r['injury_body_part'] or 'n/a'})" if r and r["injury"] else ""
            row.update(action="keep", reason=why or "Best option")
        elif r and r["id"] in cur_ids:
            j = next(k for k, cc in enumerate(cur) if cc and cc["id"] == r["id"])
            n = rec[j]
            if c and c["id"] not in rec_ids:
                tail = f" to cover {c['name']}" + (f" ({c['injury']})" if c["injury"] else "")
            elif n and n["id"] not in cur_ids and not eligible(s, n):
                tail = f" so {n['name']} ({n['pos']}) can take {slots[j]}"
            elif r["injury"] == "Questionable":
                tail = " (GTD in the wider slot: more backfill options at inactives)"
            else:
                tail = " (later kickoff in the wider slot keeps late swaps open)"
            row.update(action="move", reason=f"{r['name']} moves here from {slots[j]}{tail}")
        else:
            row.update(action="start", reason=f"{r['name'] if r else 'nobody'} starts"
                       + (f", {c['name']} benched" if c and c["id"] not in rec_ids else ""))
        rows.append(row)

    # swaps = who comes off vs who goes on, paired best-for-best (a player who
    # just changes slot is not a swap).
    outs_ = sorted([c for c in cur if c and c["id"] not in rec_ids], key=lambda x: -x["value"])
    ins_ = sorted([r for r in rec if r and r["id"] not in cur_ids], key=lambda x: -x["value"])
    swaps = []
    for k, r in enumerate(ins_):
        c = outs_[k] if k < len(outs_) else None
        d = r["value"] - (c["value"] if c else 0)
        if c is None:
            conf, pb, why = "forced", None, "Fills empty slot"
        elif c["game_state"] == "bye":
            conf, pb, why = "forced", None, f"Replaces {c['name']} (bye)"
        elif c["play_prob"] == 0:
            conf, pb, why = "forced", None, f"Replaces {c['name']} ({c['injury']})"
        else:
            pb = round(p_better(r, c), 2)
            conf = ("clear" if pb >= .62 and d >= 2 else "lean" if pb >= .55 else "coin_flip")
            why = f"{'+' if d >= 0 else ''}{d:.1f} proj, beats him {pb:.0%} of sims"
            if r["implied_total"] and c["implied_total"]:
                why += f"; team total {r['implied_total']} vs {c['implied_total']}"
            if c["injury"]:
                why += f"; {c['name']} {c['injury']}"
        slot = next(rows[i]["slot"] for i in range(len(slots)) if rec[i] is r)
        swaps.append({"slot": slot, "out": c and c["id"], "in": r["id"],
                      "out_name": c and c["name"], "in_name": r["name"],
                      "delta": round(d, 2), "p_better": pb, "confidence": conf, "reason": why})
        for row in rows:
            if row["recommended"] and row["recommended"]["id"] == r["id"]:
                row.update(confidence=conf, delta=round(d, 2), p_better=pb, reason=why)
    # every open starter also gets its closest bench challenger, so a "keep"
    # can still read as "close call" rather than implying certainty.
    bench = [x for x in pool if x["id"] not in rec_ids]
    for i, row in enumerate(rows):
        r = rec[i]
        if not r or row["locked"]:
            continue
        alts = [b for b in bench if eligible(slots[i], b) and b["value"] > 0]
        if not alts:
            continue
        b = max(alts, key=lambda x: x["value"])
        pb = round(p_better(r, b), 2)
        m = round(r["value"] - b["value"], 2)
        row["challenger"] = {"id": b["id"], "name": b["name"], "value": b["value"],
                             "margin": m, "p_starter_better": pb}
        if row["action"] in ("keep", "move"):
            row["confidence"] = ("clear" if pb >= .62 and m >= 2 else
                                 "lean" if pb >= .55 else "coin_flip")
            if row["confidence"] != "clear":
                row["reason"] += f"; close call vs {b['name']} ({m:+.1f}, {pb:.0%})"
    for row in rows:
        row.setdefault("confidence", {"locked": "locked", "keep": "keep", "move": "reseat"}.get(row["action"], "keep"))
        row.setdefault("delta", 0.0)
        row.setdefault("p_better", None)

    for i, s in enumerate(slots):
        r = rec[i]
        if r and r["injury"] == "Questionable" and r["kickoff"] and not r["locked"]:
            at = r["kickoff"] - dt.timedelta(minutes=90)
            alerts.append({"type": "gtd_recheck", "player": r["id"], "at": at.isoformat(),
                           "message": f"{r['name']} Q -- recheck inactives at "
                                      f"{at.astimezone(PT).strftime('%a %-I:%M %p')} PT"})
        if r and r["game_state"] == "bye":
            alerts.append({"type": "bye_starter", "player": r["id"],
                           "message": f"{r['name']} is on bye and no legal replacement exists"})
        if r is None:
            alerts.append({"type": "empty_slot", "slot": s,
                           "message": f"No eligible player for {s} -- check waivers"})
    # ---- totals and win probability
    def lineup_sims(lu):
        # common random numbers: a player draws the same scenario stream in
        # every lineup he appears in, so identical lineups total identically
        # and current-vs-recommended differences are not Monte Carlo noise.
        tot = [0.0] * SIMS
        for x in lu:
            if not x:
                continue
            if x["game_state"] == "post" and x["actual"] is not None:
                for k in range(SIMS):
                    tot[k] += x["actual"]
                continue
            rr = random.Random(x["id"])
            for k in range(SIMS):
                if rr.random() < x["play_prob"]:
                    tot[k] += x["_sims"][rr.randrange(len(x["_sims"]))]
        return tot
    opp_block = None
    cur_t, rec_t = lineup_sims(cur), lineup_sims(rec)
    if opp:
        orost = next(r for r in rosters if r["roster_id"] == opp["roster_id"])
        ou = users.get(orost["owner_id"], {})
        ol = [player(pid, opp.get("players_points") or {}) for pid in (opp.get("starters") or []) if pid != "0"]
        ot = lineup_sims(ol)
        wp = lambda t: round(sum(a > b for a, b in zip(t, ot)) / SIMS, 3)
        opp_block = {"team_name": (ou.get("metadata") or {}).get("team_name") or ou.get("display_name"),
                     "projected": round(sum(ot) / SIMS, 1), "points_so_far": opp.get("points"),
                     "win_prob_current": wp(cur_t), "win_prob_recommended": wp(rec_t)}
    me_user = users.get(me_id, {})
    projection_sources = []
    if sproj:
        company = next(iter(sproj.values())).get("company") or "?"
        projection_sources.append(f"sleeper({company})")
    if eproj:
        projection_sources.append("espn")
    projection_gaps = [
        {"id": p["id"], "name": p["name"], "position": p["pos"]}
        for p in pl.values() if not p["sources"] and p["game_state"] != "bye"
    ]
    return {
        "schema": "startsit/v1",
        "generated_at": now.isoformat(),
        "platform": "sleeper",
        "league": {"id": lid, "name": lg["name"], "season": lg["season"], "week": week,
                   "teams": lg["total_rosters"], "slots": slots,
                   "scoring_fingerprint": fingerprint(S)},
        "team": {"roster_id": mine["roster_id"],
                 "name": (me_user.get("metadata") or {}).get("team_name") or me_user.get("display_name")},
        "opponent": opp_block,
        "sources": {"projections": projection_sources,
                    "schedule": schedule_source, "injuries": "sleeper players",
                    "projection_gaps": projection_gaps},
        "totals": {"current": round(sum(cur_t) / SIMS, 1), "recommended": round(sum(rec_t) / SIMS, 1)},
        "slots": rows,
        "bench": [ref(p) for p in sorted(pl.values(), key=lambda p: (-p['value'], p['name'])) if p['id'] not in cur_ids],
        "reserve": [ref(player(pid, pp)) for pid in sorted(reserve)],
        "swaps": swaps,
        "alerts": alerts,
        "apply": {"method": "deep_link", "url": f"https://sleeper.com/leagues/{lid}/team",
                  "note": "Sleeper's public API is read-only; lineup writes need the app/site."},
    }


def fingerprint(S):
    keys = ["pass_td", "pass_int", "rec", "bonus_rec_te", "bonus_rec_yd_100", "bonus_rec_yd_200",
            "bonus_rush_yd_100", "bonus_rush_yd_200", "bonus_pass_yd_300", "fum_lost",
            "fgm_30_39", "fgm_40_49", "fgm_50_59", "fgm_yds_over_30", "pts_allow_0"]
    return {k: S[k] for k in keys if S.get(k)}


PT = dt.timezone(dt.timedelta(hours=-7))


def print_table(out):
    lg = out["league"]
    print(f"\nSleeper · {lg['name']} · Week {lg['week']}  ({out['team']['name']})")
    o = out.get("opponent")
    if o:
        print(f"  vs {o['team_name']}  proj {o['projected']}  | you: current {out['totals']['current']}"
              f" -> recommended {out['totals']['recommended']}  | win prob "
              f"{o['win_prob_current']:.0%} -> {o['win_prob_recommended']:.0%}")
    print(f"  {'Slot':<9}{'Current':<24}{'Recommended':<24}{'Proj cur→rec':<16}{'Conf':<10}Why")
    for r in out["slots"]:
        c, x = r["current"], r["recommended"]
        nm = lambda p: "-" if not p else (p["name"] + (f" ({p['injury'][0]})" if p["injury"] else ""))[:22]
        pv = lambda p: "-" if not p else f"{p['value']:.1f}"
        band = f" [{x['proj']['p10']}-{x['proj']['p90']}]" if x else ""
        mark = "*" if r["change"] else " "
        print(f" {mark}{r['slot']:<9}{nm(c):<24}{nm(x):<24}{pv(c)+' → '+pv(x):<16}"
              f"{r['confidence']:<10}{r['reason']}{band}")
    for a in out["alerts"]:
        print(f"  ! {a['message']}")


def local_username():
    """Read your Sleeper username from local-settings.json at the repo root.

    That file is git-ignored, so the username stays on your machine and out of
    the public repo. Example contents: {"sleeper_username": "your_name"}
    """
    path = pathlib.Path(__file__).resolve().parents[2] / "local-settings.json"
    try:
        return json.loads(path.read_text()).get("sleeper_username")
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("username", nargs="?", default=local_username(),
                    help="Sleeper username (defaults to sleeper_username in local-settings.json)")
    ap.add_argument("--week", type=int)
    ap.add_argument("--league")
    ap.add_argument("--json", help="write contract JSON here")
    ap.add_argument("--no-espn", action="store_true")
    ap.add_argument("--what-if", action="append", default=[], metavar="NAME_OR_ID=STATUS",
                    help="override an injury status, e.g. --what-if 'Jahmyr Gibbs=Out'")
    a = ap.parse_args()
    if not a.username:
        ap.error("no Sleeper username: pass one, or put {\"sleeper_username\": \"...\"} in local-settings.json")

    now = dt.datetime.now(dt.timezone.utc)
    state = get(f"{SL}/state/nfl", cache_s=60)
    season, week = int(state["season"]), a.week or int(state["display_week"] or state["week"])
    user = get(f"{SL}/user/{a.username}", cache_s=300)
    leagues = get(f"{SL}/user/{user['user_id']}/leagues/nfl/{season}", cache_s=60)
    if a.league:
        leagues = [l for l in leagues if l["league_id"] == a.league]
    print(f"{user['display_name']} · season {season} week {week} · {len(leagues)} Sleeper league(s)",
          file=sys.stderr)
    P = sleeper_players()
    for w in a.what_if:
        who, st = w.rsplit("=", 1)
        for pid, p in P.items():
            if pid == who or (p.get("full_name") or "").lower() == who.lower():
                p["injury_status"] = None if st.lower() in ("", "none", "active") else st
                print(f"  what-if: {p.get('full_name', pid)} -> {st}", file=sys.stderr)
    sproj = sleeper_week_proj(season, week)
    eproj = {}
    if not a.no_espn:
        try:
            eproj = espn_week_proj(season, week)
        except Exception as ex:  # noqa: BLE001
            print(f"  ! ESPN projections unavailable ({ex}); Sleeper only", file=sys.stderr)
    print(f"  projections: sleeper {len(sproj)}, espn {sum(isinstance(k, str) for k in eproj)}", file=sys.stderr)
    games, schedule_source = schedule(season, week)
    outs = []
    for lg in leagues:
        if lg.get("status") not in ("in_season", "post_season", "drafting", "pre_draft", "complete"):
            continue
        o = run_league(lg, week, user["user_id"], P, sproj, eproj, games, now,
                       schedule_source)
        if o:
            outs.append(o)
            print_table(o)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(outs if len(outs) != 1 else outs[0], indent=2))
        print(f"\nwrote {a.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
