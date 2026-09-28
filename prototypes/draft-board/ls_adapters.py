"""Platform settings -> canonical LeagueSettings.

sleeper_to_canonical(league_json)   GET https://api.sleeper.app/v1/league/{id}  (public, CORS *)
espn_to_canonical(settings_json)    .../leagues/{id}?view=mSettings            (public leagues; private need espn_s2/SWID)
CBS: league endpoints require an access_token (see docs section 2.4); the CBS
mapping table lives in the doc and is not exercised here.

Every key is either mapped, deliberately ignored (zero points), or listed in
scoring.unsupported with its point value -- nothing is dropped silently.
"""
import math

# ------------------------------------------------------------------ Sleeper ---
SLEEPER_SLOTS = {
    "QB": ["QB"], "RB": ["RB"], "WR": ["WR"], "TE": ["TE"], "K": ["K"], "DEF": ["DST"],
    "FLEX": ["RB", "WR", "TE"], "WRRB_FLEX": ["RB", "WR"], "REC_FLEX": ["WR", "TE"],
    "SUPER_FLEX": ["QB", "RB", "WR", "TE"],
}
SLEEPER_SLOT_LABEL = {"DEF": "DST", "REC_FLEX": "W/T", "WRRB_FLEX": "W/R",
                      "SUPER_FLEX": "SUPERFLEX", "FLEX": "FLEX"}
IDP_SLOTS = {"DL", "LB", "DB", "IDP_FLEX"}

# Linear keys: Sleeper key -> (canonical stat, positions or None)
SLEEPER_LINEAR = {
    "pass_yd": ("pass_yd", None), "pass_td": ("pass_td", None), "pass_int": ("pass_int", None),
    "pass_2pt": ("pass_2pt", None), "pass_att": ("pass_att", None), "pass_cmp": ("pass_cmp", None),
    "pass_inc": ("pass_inc", None), "pass_sack": ("pass_sack", None), "pass_fd": ("pass_fd", None),
    "pass_int_td": ("pass_int_td", None),
    "rush_yd": ("rush_yd", None), "rush_td": ("rush_td", None), "rush_2pt": ("rush_2pt", None),
    "rush_att": ("rush_att", None), "rush_fd": ("rush_fd", None),
    "rec": ("rec", None), "rec_yd": ("rec_yd", None), "rec_td": ("rec_td", None),
    "rec_2pt": ("rec_2pt", None), "rec_fd": ("rec_fd", None), "rec_tgt": ("rec_tgt", None),
    "bonus_rec_te": ("rec", ["TE"]), "bonus_rec_rb": ("rec", ["RB"]),
    "bonus_rec_wr": ("rec", ["WR"]), "bonus_rec_qb": ("rec", ["QB"]),
    "bonus_fd_qb": ("first_down", ["QB"]), "bonus_fd_rb": ("first_down", ["RB"]),
    "bonus_fd_wr": ("first_down", ["WR"]), "bonus_fd_te": ("first_down", ["TE"]),
    "fum": ("fum", None), "fum_lost": ("fum_lost", None), "fum_rec_td": ("fum_rec_td", None),
    # kicker
    "xpm": ("xpm", ["K"]), "xpmiss": ("xpmiss", ["K"]), "fgm": ("fgm", ["K"]),
    "fgmiss": ("fgmiss", ["K"]),
    # team defense (Sleeper's un-prefixed defensive keys are DST scoring)
    "sack": ("sack", ["DST"]), "int": ("def_int", ["DST"]), "fum_rec": ("fum_rec", ["DST"]),
    "ff": ("def_ff", ["DST"]), "safe": ("safe", ["DST"]), "blk_kick": ("blk_kick", ["DST"]),
    "def_td": ("def_td", ["DST"]), "def_st_td": ("st_td", ["DST"]), "st_td": ("st_td", ["DST"]),
    "def_2pt": ("def_2pt", ["DST"]), "pts_allow": ("pts_allow", ["DST"]),
    "yds_allow": ("yds_allow", ["DST"]), "def_pass_def": ("def_pass_def", ["DST"]),
    "tkl_loss": ("def_tkl_loss", ["DST"]), "qb_hit": ("def_qb_hit", ["DST"]),
}
# Per-game exclusive tiers: family -> [(key, lower bound)]
SLEEPER_TIERS = {
    "pass_yd": [("bonus_pass_yd_300", 300), ("bonus_pass_yd_400", 400)],
    "rush_yd": [("bonus_rush_yd_100", 100), ("bonus_rush_yd_200", 200)],
    "rec_yd": [("bonus_rec_yd_100", 100), ("bonus_rec_yd_200", 200)],
    "scrim_yd": [("bonus_rush_rec_yd_100", 100), ("bonus_rush_rec_yd_200", 200)],
    "pass_cmp": [("bonus_pass_cmp_25", 25)],
    "rush_att": [("bonus_rush_att_20", 20)],
}
SLEEPER_PA = [("pts_allow_0", 0, 0), ("pts_allow_1_6", 1, 6), ("pts_allow_7_13", 7, 13),
              ("pts_allow_14_20", 14, 20), ("pts_allow_21_27", 21, 27),
              ("pts_allow_28_34", 28, 34), ("pts_allow_35p", 35, None)]
SLEEPER_YA = [("yds_allow_0_100", 0, 99), ("yds_allow_100_199", 100, 199),
              ("yds_allow_200_299", 200, 299), ("yds_allow_300_349", 300, 349),
              ("yds_allow_350_399", 350, 399), ("yds_allow_400_449", 400, 449),
              ("yds_allow_450_499", 450, 499), ("yds_allow_500_549", 500, 549),
              ("yds_allow_550p", 550, None)]
SLEEPER_FG = [("fgm_0_19", 0, 19), ("fgm_20_29", 20, 29), ("fgm_30_39", 30, 39),
              ("fgm_40_49", 40, 49), ("fgm_50_59", 50, 59), ("fgm_60p", 60, None)]
SLEEPER_FG_50P = ("fgm_50p", 50, None)          # older leagues: one 50+ bucket
SLEEPER_FGMISS = [("fgmiss_0_19", 0, 19), ("fgmiss_20_29", 20, 29),
                  ("fgmiss_30_39", 30, 39), ("fgmiss_40_49", 40, 49),
                  ("fgmiss_50p", 50, None)]
SLEEPER_LONG_TD = {"pass_td_40p": ("pass_td", 40), "pass_td_50p": ("pass_td", 50),
                   "rush_td_40p": ("rush_td", 40), "rush_td_50p": ("rush_td", 50),
                   "rec_td_40p": ("rec_td", 40), "rec_td_50p": ("rec_td", 50)}
SLEEPER_UNSUPPORTED_PREFIX = ("idp_", "kr_", "pr_", "st_", "fg_ret", "blk_kick_ret",
                              "int_ret", "fum_ret", "def_st_f", "def_kr", "def_pr",
                              "tkl", "sack_yd", "rush_40p", "rec_40p", "pass_cmp_40p",
                              "bonus_def", "qb_hit")


def _r(v):
    """Sleeper stores 0.04 as 0.03999999910593033 (float32). Undo that."""
    return round(float(v), 6)


def _exclusive(pairs):
    """[(lower, pts)] sorted -> exclusive [min, max] tiers."""
    pairs = sorted(pairs)
    out = []
    for i, (lo, pts) in enumerate(pairs):
        t = {"min": lo, "points": pts}
        if i + 1 < len(pairs):
            t["max"] = pairs[i + 1][0] - 1e-9
        out.append(t)
    return out


def sleeper_to_canonical(lg):
    ss = {k: _r(v) for k, v in (lg.get("scoring_settings") or {}).items()}
    used = set()
    rules, unsupported = [], []

    for key, (stat, pos) in SLEEPER_LINEAR.items():
        if ss.get(key):
            r = {"type": "per_unit", "stat": stat, "points": ss[key], "source_key": key}
            if pos:
                r["positions"] = pos
            rules.append(r)
        used.add(key)

    for stat, keys in SLEEPER_TIERS.items():
        pairs = [(lo, ss[k]) for k, lo in keys if ss.get(k)]
        used |= {k for k, _ in keys}
        if pairs:
            rules.append({"type": "game_tiers", "stat": stat, "tiers": _exclusive(pairs),
                          "source_key": ",".join(k for k, _ in keys)})

    for table, stat in ((SLEEPER_PA, "pts_allow"), (SLEEPER_YA, "yds_allow")):
        tiers = []
        for k, lo, hi in table:
            used.add(k)
            if ss.get(k):
                t = {"min": lo, "points": ss[k]}
                if hi is not None:
                    t["max"] = hi
                tiers.append(t)
        if tiers:
            rules.append({"type": "game_tiers", "stat": stat, "positions": ["DST"],
                          "tiers": tiers, "source_key": f"{stat}_*"})

    fg = [x for x in SLEEPER_FG if x[0] in ss] or []
    if SLEEPER_FG_50P[0] in ss and not any(k in ss for k in ("fgm_50_59", "fgm_60p")):
        fg = [x for x in SLEEPER_FG if x[0] not in ("fgm_50_59", "fgm_60p")] + [SLEEPER_FG_50P]
    used |= {k for k, _, _ in SLEEPER_FG} | {SLEEPER_FG_50P[0]}
    bins = [dict({"min": lo, "points": ss[k]}, **({"max": hi} if hi is not None else {}))
            for k, lo, hi in fg if ss.get(k)]
    per_yard = ss.get("fgm_yds", 0.0)
    used.add("fgm_yds")
    if bins or per_yard:
        r = {"type": "distance", "event": "fg_made", "positions": ["K"], "bins": bins,
             "source_key": "fgm_*"}
        if per_yard:
            r["per_yard"] = per_yard
        rules.append(r)
    if ss.get("fgm_yds_over_30"):
        unsupported.append({"source_key": "fgm_yds_over_30", "points": ss["fgm_yds_over_30"],
                            "reason": "per-yard-over-30 FG bonus: expressible as distance bins, not mapped in prototype"})
    used.add("fgm_yds_over_30")

    miss = [dict({"min": lo, "points": ss[k]}, **({"max": hi} if hi is not None else {}))
            for k, lo, hi in SLEEPER_FGMISS if ss.get(k)]
    used |= {k for k, _, _ in SLEEPER_FGMISS}
    if miss:
        rules.append({"type": "distance", "event": "fg_miss", "positions": ["K"],
                      "bins": miss, "source_key": "fgmiss_*"})

    for k, (ev, lo) in SLEEPER_LONG_TD.items():
        used.add(k)
        if ss.get(k):
            rules.append({"type": "distance", "event": ev, "bins": [{"min": lo, "points": ss[k]}],
                          "source_key": k})

    for k, v in sorted(ss.items()):
        if k in used or not v:
            continue
        reason = ("IDP / return / special-teams scoring is out of scope"
                  if k.startswith(SLEEPER_UNSUPPORTED_PREFIX) else "unmapped Sleeper key")
        unsupported.append({"source_key": k, "points": v, "reason": reason})

    slots, bench, ir, idp = {}, 0, 0, 0
    for sp in lg.get("roster_positions") or []:
        if sp == "BN":
            bench += 1
        elif sp == "IR":
            ir += 1
        elif sp in IDP_SLOTS:
            idp += 1
        elif sp in SLEEPER_SLOTS:
            slots[sp] = slots.get(sp, 0) + 1
    if idp:
        unsupported.append({"source_key": "roster_positions:IDP", "points": idp,
                            "reason": "IDP starting slots are out of scope"})
    settings = lg.get("settings") or {}
    out = {
        "schema_version": 1, "name": lg.get("name", "Sleeper league"), "platform": "sleeper",
        "platform_league_id": str(lg.get("league_id", "")),
        "season": int(lg.get("season") or 0) or None,
        "teams": int(settings.get("num_teams") or lg.get("total_rosters") or 12),
        "games": 17,
        "draft": {"type": "snake"},
        "roster": {"slots": [{"id": SLEEPER_SLOT_LABEL.get(k, k), "eligible": SLEEPER_SLOTS[k], "count": n}
                             for k, n in slots.items()],
                   "bench": bench, "ir": ir or int(settings.get("reserve_slots") or 0),
                   "taxi": int(settings.get("taxi_slots") or 0)},
        "scoring": {"rules": rules, "unsupported": unsupported},
    }
    out["draft"]["rounds"] = sum(s["count"] for s in out["roster"]["slots"]) + bench
    return out


# --------------------------------------------------------------------- ESPN ---
ESPN_SLOTS = {0: ("QB", ["QB"]), 2: ("RB", ["RB"]), 3: ("W/R", ["RB", "WR"]),
              4: ("WR", ["WR"]), 5: ("W/T", ["WR", "TE"]), 6: ("TE", ["TE"]),
              7: ("SUPERFLEX", ["QB", "RB", "WR", "TE"]), 16: ("DST", ["DST"]),
              17: ("K", ["K"]), 23: ("FLEX", ["RB", "WR", "TE"])}
ESPN_SLOT_POS = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 16: "DST", 17: "K"}
ESPN_BENCH, ESPN_IR = 20, 21
ESPN_IDP_SLOTS = set(range(8, 16))

ESPN_LINEAR = {
    0: "pass_att", 1: "pass_cmp", 2: "pass_inc", 3: "pass_yd", 4: "pass_td", 19: "pass_2pt",
    20: "pass_int", 64: "pass_sack", 23: "rush_att", 24: "rush_yd", 25: "rush_td",
    26: "rush_2pt", 53: "rec", 42: "rec_yd", 43: "rec_td", 44: "rec_2pt", 58: "rec_tgt",
    63: "fum_rec_td", 68: "fum", 72: "fum_lost",
    83: "fgm", 84: "fga", 85: "fgmiss", 86: "xpm", 87: "xpa", 88: "xpmiss",
    95: "def_int", 96: "fum_rec", 97: "blk_kick", 98: "safe", 99: "sack",
    93: "st_td", 94: "def_td", 101: "st_td", 102: "st_td", 103: "def_td", 104: "def_td",
    106: "def_ff", 206: "def_2pt", 209: "def_1pt_safe", 120: "pts_allow", 127: "yds_allow",
}
DST_STATS = {"def_int", "fum_rec", "blk_kick", "safe", "sack", "st_td", "def_td", "def_ff",
             "def_2pt", "def_1pt_safe", "pts_allow", "yds_allow"}
K_STATS = {"fgm", "fga", "fgmiss", "xpm", "xpa", "xpmiss"}
# every-N per-game stats -> (canonical stat, N)
ESPN_STEP = {5: ("pass_yd", 5), 6: ("pass_yd", 10), 7: ("pass_yd", 20), 8: ("pass_yd", 25),
             9: ("pass_yd", 50), 10: ("pass_yd", 100), 11: ("pass_cmp", 5), 12: ("pass_cmp", 10),
             13: ("pass_inc", 5), 14: ("pass_inc", 10),
             27: ("rush_yd", 5), 28: ("rush_yd", 10), 29: ("rush_yd", 20), 30: ("rush_yd", 25),
             31: ("rush_yd", 50), 32: ("rush_yd", 100), 33: ("rush_att", 5), 34: ("rush_att", 10),
             47: ("rec_yd", 5), 48: ("rec_yd", 10), 49: ("rec_yd", 20), 50: ("rec_yd", 25),
             51: ("rec_yd", 50), 52: ("rec_yd", 100), 54: ("rec", 5), 55: ("rec", 10)}
ESPN_TIERS = {17: ("pass_yd", 300), 18: ("pass_yd", 400), 37: ("rush_yd", 100),
              38: ("rush_yd", 200), 56: ("rec_yd", 100), 57: ("rec_yd", 200)}
ESPN_LONG_TD = {15: ("pass_td", 40), 16: ("pass_td", 50), 35: ("rush_td", 40),
                36: ("rush_td", 50), 45: ("rec_td", 40), 46: ("rec_td", 50)}
ESPN_FG = {80: (0, 39), 77: (40, 49), 198: (50, 59), 74: (50, None), 201: (60, None)}
ESPN_FGMISS = {82: (0, 39), 79: (40, 49), 200: (50, 59), 76: (50, None), 203: (60, None)}
ESPN_PA = {89: (0, 0), 90: (1, 6), 91: (7, 13), 92: (14, 17), 121: (18, 21),
           122: (22, 27), 123: (28, 34), 124: (35, 45), 125: (46, None)}
ESPN_YA = {128: (0, 99), 129: (100, 199), 130: (200, 299), 131: (300, 349),
           132: (350, 399), 133: (400, 449), 134: (450, 499), 135: (500, 549), 136: (550, None)}


def espn_to_canonical(doc, name="ESPN league", league_id=""):
    s = doc.get("settings", doc)
    items = s["scoringSettings"]["scoringItems"]
    rules, unsupported = [], []
    tiers, pa, ya, fg, fgmiss = {}, [], [], [], []

    def emit_linear(stat, pts, pos, key):
        r = {"type": "per_unit", "stat": stat, "points": pts, "source_key": key}
        if pos:
            r["positions"] = pos
        rules.append(r)

    for it in items:
        sid, pts = it["statId"], float(it.get("points") or 0)
        ov = {int(k): float(v) for k, v in (it.get("pointsOverrides") or {}).items()}
        key = f"espn:{sid}"
        # pointsOverrides are keyed by lineup slot: {6: 1.5} on stat 53 is a TE
        # premium; {16: x} on a defensive stat is the D/ST value itself.
        if sid in ESPN_LINEAR:
            stat = ESPN_LINEAR[sid]
            if stat in DST_STATS:
                v = ov.get(16, pts)
                if v:
                    if stat == "pts_allow" or stat == "yds_allow":
                        emit_linear(stat, v, ["DST"], key)
                    else:
                        emit_linear(stat, v, ["DST"], key)
                continue
            if stat in K_STATS:
                if ov.get(17, pts):
                    emit_linear(stat, ov.get(17, pts), ["K"], key)
                continue
            if pts:
                emit_linear(stat, pts, None, key)
            for slot, v in ov.items():
                p = ESPN_SLOT_POS.get(slot)
                if p and v != pts:
                    emit_linear(stat, v - pts, [p], key + f"@slot{slot}")
        elif sid in ESPN_STEP:
            stat, n = ESPN_STEP[sid]
            if pts:
                rules.append({"type": "game_step", "stat": stat, "every": n, "points": pts,
                              "source_key": key})
        elif sid in ESPN_TIERS:
            stat, lo = ESPN_TIERS[sid]
            if pts:
                tiers.setdefault(stat, []).append((lo, pts))
        elif sid in ESPN_LONG_TD:
            ev, lo = ESPN_LONG_TD[sid]
            if pts:   # ESPN counts a 55-yard TD in BOTH 40+ and 50+: additive rules
                rules.append({"type": "distance", "event": ev, "bins": [{"min": lo, "points": pts}],
                              "source_key": key})
        elif sid in ESPN_FG:
            lo, hi = ESPN_FG[sid]
            v = ov.get(17, pts)
            if v:
                fg.append(dict({"min": lo, "points": v}, **({"max": hi} if hi is not None else {})))
        elif sid in ESPN_FGMISS:
            lo, hi = ESPN_FGMISS[sid]
            v = ov.get(17, pts)
            if v:
                fgmiss.append(dict({"min": lo, "points": v}, **({"max": hi} if hi is not None else {})))
        elif sid in ESPN_PA:
            lo, hi = ESPN_PA[sid]
            pa.append(dict({"min": lo, "points": ov.get(16, pts)}, **({"max": hi} if hi is not None else {})))
        elif sid in ESPN_YA:
            lo, hi = ESPN_YA[sid]
            ya.append(dict({"min": lo, "points": ov.get(16, pts)}, **({"max": hi} if hi is not None else {})))
        else:
            unsupported.append({"source_key": key, "points": pts or max(ov.values(), default=0),
                                "reason": "ESPN stat id not in canonical map (IDP/punter/HC/unknown)"})

    for stat, pairs in tiers.items():
        rules.append({"type": "game_tiers", "stat": stat, "tiers": _exclusive(pairs),
                      "source_key": "espn:tiers"})
    # ESPN's 50+ (74) and 50-59/60+ (198/201) overlap; keep the finer split if present.
    if any(b["min"] == 60 for b in fg):
        fg = [b for b in fg if not (b["min"] == 50 and "max" not in b)]
    if fg:
        rules.append({"type": "distance", "event": "fg_made", "positions": ["K"],
                      "bins": sorted(fg, key=lambda b: b["min"]), "source_key": "espn:fg"})
    if fgmiss:
        rules.append({"type": "distance", "event": "fg_miss", "positions": ["K"],
                      "bins": sorted(fgmiss, key=lambda b: b["min"]), "source_key": "espn:fgmiss"})
    for stat, tbl in (("pts_allow", pa), ("yds_allow", ya)):
        if tbl:
            rules.append({"type": "game_tiers", "stat": stat, "positions": ["DST"],
                          "tiers": sorted(tbl, key=lambda b: b["min"]), "source_key": f"espn:{stat}"})

    rs = s["rosterSettings"]["lineupSlotCounts"]
    slots, bench, ir = [], 0, 0
    for sid, n in ((int(k), v) for k, v in rs.items()):
        if not n:
            continue
        if sid == ESPN_BENCH:
            bench = n
        elif sid == ESPN_IR:
            ir = n
        elif sid in ESPN_SLOTS:
            lbl, el = ESPN_SLOTS[sid]
            slots.append({"id": lbl, "eligible": el, "count": n})
        else:
            unsupported.append({"source_key": f"espn:slot{sid}", "points": n,
                                "reason": "IDP / punter / head-coach slot is out of scope"})
    out = {"schema_version": 1, "name": name, "platform": "espn",
           "platform_league_id": str(league_id), "teams": int(s.get("size") or 10),
           "games": 17, "draft": {"type": "snake"},
           "roster": {"slots": slots, "bench": bench, "ir": ir},
           "scoring": {"rules": rules, "unsupported": unsupported}}
    out["draft"]["rounds"] = sum(x["count"] for x in slots) + bench
    return out
