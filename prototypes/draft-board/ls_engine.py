"""Generic league scorer: LeagueSettings (canonical JSON) x neutral projections -> points.

Two league-INDEPENDENT layers feed one league-SPECIFIC function:

  distributions(player)   per-game stat samples + per-event distance mixes.
                          Same primitives as refresh/fit.py and refresh/dad_score.py
                          (negative-binomial touches, lognormal yards per touch,
                          gamma game script). Nothing here reads scoring rules, so it
                          can be computed once at build time and shipped.
  score(settings, player) evaluates each rule against those distributions:
                          per_unit    closed form   points x E[stat]
                          distance    closed form   E[count] x E[points | length]
                          game_tiers  per-game      mean over game samples
                          game_step   per-game      mean over game samples

Each player gets his OWN seeded RNG (hash of his key). The live pipeline draws
every player from one sequential stream, so adding a player to players.py quietly
re-rolls the Monte Carlo noise of everyone listed after him.
"""
import hashlib

import numpy as np

N = 40000

# ---------------------------------------------------------------- sampling ---


def _rng(key, salt):
    h = hashlib.sha256(f"{salt}:{key}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def _touches(rng, mean, disp):
    if mean <= 0:
        return np.zeros(N, int)
    return rng.negative_binomial(disp, disp / (disp + mean), N)


def _per_touch_yards(rng, counts, ypt, sigma, shift=0.0):
    total = np.zeros(N)
    if ypt <= 0 or counts.size == 0 or counts.max() == 0:
        return total
    mu = np.log(ypt + shift) - sigma ** 2 / 2
    for k in range(int(counts.max())):
        total += np.where(counts > k, np.exp(rng.normal(mu, sigma, N)) - shift, 0.0)
    return total


def _script(rng, cv):
    k = 1.0 / cv ** 2
    return rng.gamma(k, 1.0 / k, N)


def game_samples(p, games=17, salt="v1"):
    """Per-game samples of every stat a per-game rule might read. League-neutral."""
    rng, s, pos = _rng(p["key"], salt), p["season"], p["pos"]
    out = {}
    if pos == "QB":
        g = _script(rng, 0.20)
        out["pass_yd"] = rng.gamma(16.0, (s["pass_yd"] / games) / 16.0, N) * g
        ry = s.get("rush_yd", 0)
        out["rush_yd"] = (rng.gamma(2.2, (ry / games) / 2.2, N) * np.sqrt(g)
                          if ry > 0 else np.zeros(N))
    elif pos in ("RB", "WR", "TE"):
        att, ry = s.get("rush_att", 0), s.get("rush_yd", 0)
        rc, cy = s.get("rec", 0), s.get("rec_yd", 0)
        g = _script(rng, 0.28)
        rush_n = (_touches(rng, att / games, 8.0) * g).round().astype(int)
        rec_n = _touches(rng, rc / games, 4.5)
        out["rush_yd"] = (_per_touch_yards(rng, rush_n, ry / max(att, 1), 0.85, 2.0)
                          if att > 0 else np.zeros(N))
        out["rec_yd"] = (_per_touch_yards(rng, rec_n, cy / max(rc, 1), 0.80)
                         if rc > 0 else np.zeros(N))
        out["rec"] = rec_n.astype(float)
        out["rush_att"] = rush_n.astype(float)
    elif pos == "DST":
        mu = s["pts_allow"] / games
        out["pts_allow"] = (7 * rng.poisson(mu / 9.5, N) + 3 * rng.poisson(mu / 11.4, N)).astype(float)
    return out


# --------------------------------------------------------- distance mixes ---
# League-average TD length (from refresh/dad_score.py), binned. Rushing scores
# cluster at the goal line; passing/receiving scores do not.
TD_EDGES = [(0, 4), (5, 9), (10, 19), (20, 29), (30, 39), (40, 49), (50, 59),
            (60, 69), (70, 79), (80, 89), (90, 99)]
TD_MID = np.array([3, 8, 15, 25, 35, 45, 55, 65, 75, 85, 95], float)
PASS_DIST = np.array([.28, .18, .20, .12, .08, .05, .04, .025, .015, .007, .003])
RUSH_DIST = np.array([.58, .16, .12, .055, .03, .02, .014, .009, .005, .004, .003])
REC_Z = {"WR": (12.6, 2.6), "TE": (11.0, 2.2), "RB": (8.0, 2.5)}

FG_EDGES = [(0, 19), (20, 29), (30, 39), (40, 49), (50, 59), (60, 70)]
FG_MID = np.array([10, 25, 35, 45, 55, 65], float)
FG_BASE_P = np.array([.02, .22, .27, .27, .19, .03])


def _tilted(base, z, beta=0.35):
    l = np.log(TD_MID)
    m = float(base @ l)
    sd = float(np.sqrt(base @ (l - m) ** 2))
    w = base * np.exp(beta * np.clip(z, -1.5, 1.5) * (l - m) / sd)
    return w / w.sum()


def distance_mixes(p):
    """P(length bin) for each scoring event this player produces. League-neutral."""
    s, pos = p["season"], p["pos"]
    mix = {}
    if pos == "QB":
        mix["pass_td"] = PASS_DIST          # length is set by his receivers
        mix["rush_td"] = _tilted(RUSH_DIST, -0.3)   # sneaks and goal-line keepers
    elif pos in ("RB", "WR", "TE"):
        ypr = s.get("rec_yd", 0) / max(s.get("rec", 0), 1)
        if ypr > 0:
            c, sd = REC_Z.get(pos, (11.5, 2.6))
            mix["rec_td"] = _tilted(PASS_DIST, (ypr - c) / sd)
        else:
            mix["rec_td"] = PASS_DIST
        ypc = s.get("rush_yd", 0) / max(s.get("rush_att", 0), 1)
        mix["rush_td"] = _tilted(RUSH_DIST, (ypc - 4.3) / 0.7) if ypc > 0 else RUSH_DIST
    elif pos == "K":
        z = np.arange(6) - 2.5
        w = FG_BASE_P * np.exp(0.45 * (p["leg"] - 1.0) * z / 2.5)
        mix["fg_made"] = w / w.sum()
        mix["fg_miss"] = mix["fg_made"]
    return mix


EVENT_BINS = {"pass_td": (TD_EDGES, TD_MID), "rush_td": (TD_EDGES, TD_MID),
              "rec_td": (TD_EDGES, TD_MID), "fg_made": (FG_EDGES, FG_MID),
              "fg_miss": (FG_EDGES, FG_MID)}
EVENT_COUNT = {"pass_td": "pass_td", "rush_td": "rush_td", "rec_td": "rec_td",
               "fg_made": "fgm", "fg_miss": "fgmiss"}


# ----------------------------------------------------------------- scoring ---
def _applies(rule, pos):
    ps = rule.get("positions")
    return ps is None or pos in ps


def _tier_points(x, tiers):
    out = np.zeros_like(x)
    for t in tiers:
        lo, hi = t["min"], t.get("max", np.inf)
        out = np.where((x >= lo) & (x <= hi), t["points"], out)
    return out


def _step_points(x, r):
    start = r.get("start", r["every"])
    steps = np.where(x >= start, np.floor((x - start) / r["every"]) + 1, 0)
    if r.get("max_steps") is not None:
        steps = np.minimum(steps, r["max_steps"])
    return steps * r["points"]


def _bin_points(bins, mid):
    for b in bins:
        if mid >= b["min"] and mid <= b.get("max", np.inf):
            return b["points"]
    return 0.0


def score(settings, p, samples, mixes, proxies=None, games=None):
    """Expected season points for one player, broken down by rule group."""
    games = games or settings.get("games", 17)
    pos, s = p["pos"], p["season"]
    parts = {"linear": 0.0, "per_game": 0.0, "distance": 0.0}
    missing = set()
    for r in settings["scoring"]["rules"]:
        if not _applies(r, pos):
            continue
        t = r["type"]
        if t == "per_unit":
            stat = r["stat"]
            if stat not in s and proxies and stat in proxies:
                stat = proxies[stat][0]
            if stat in s:
                parts["linear"] += r["points"] * s[stat]
            elif r["points"]:
                missing.add(r["stat"])
        elif t in ("game_tiers", "game_step"):
            x = samples.get(r["stat"])
            if x is None:
                continue
            f = _tier_points(x, r["tiers"]) if t == "game_tiers" else _step_points(x, r)
            parts["per_game"] += float(f.mean()) * games
        elif t == "distance":
            ev = r["event"]
            count = s.get(EVENT_COUNT.get(ev, ev), 0)
            if not count or ev not in mixes:
                continue
            _, mids = EVENT_BINS[ev]
            w = mixes[ev]
            per = sum(w[i] * _bin_points(r.get("bins", []), mids[i]) for i in range(len(w)))
            per += r.get("per_yard", 0.0) * float(w @ mids)
            parts["distance"] += count * per
    av = p["avail"]
    parts = {k: v * av for k, v in parts.items()}
    parts["total"] = sum(parts.values())
    return parts, missing


# ------------------------------------------------------------ quantiles ---
def to_quantiles(x, q=256):
    """Compress 40k samples to q mid-quantiles: what the client would receive."""
    probs = (np.arange(q) + 0.5) / q
    return np.quantile(x, probs)
