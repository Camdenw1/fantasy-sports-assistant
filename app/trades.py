"""Trade ideas a league-mate might actually accept.

For each other team, find players who would raise your best rest-of-season starting
lineup, then look for an offer (one of your players, or two bench players) that also
raises *their* best lineup and is close in raw projected value. Both sides improving
is what makes an idea realistic; value parity keeps it from being a fleece. Values are
rest-of-season projections under the league's scoring, so this is a starting point for
a conversation, not a verdict.
"""
from itertools import combinations
from season_rosters import best_lineup

SKILL = {'QB', 'RB', 'WR', 'TE'}
MIN_GAIN = 8.0          # your starting lineup must improve by this many ROS points
MIN_THEIR_GAIN = 2.0    # and theirs must improve too
FAIR_SINGLE = 0.85      # 1-for-1: what you give is worth at least 85% of what you get
FAIR_PAIR = 1.0         # 2-for-1: the two you give are worth at least what you get


def lineup_total(players, slots):
    best = best_lineup(players, slots)
    return (best[0], set(best[1])) if best else (0., set())


def ideas(players, owners, me, team_names, slots, limit=4, depth=8):
    pool = [p for p in players if p['position'] in SKILL and p['id'] in owners]
    rosters = {}
    for p in pool:
        rosters.setdefault(owners[p['id']], []).append(p)
    mine = rosters.get(me, [])
    if not mine or not slots:
        return []
    base_me, core = lineup_total(mine, slots)
    bench = sorted((p for p in mine if p['id'] not in core), key=lambda p: -p['points'])[:5]
    offers_single = sorted(mine, key=lambda p: -p['points'])[:12]
    offers_pair = list(combinations(bench, 2))
    found = []
    for rid, theirs in rosters.items():
        if rid == me:
            continue
        base_them, _ = lineup_total(theirs, slots)
        targets = [b for b in sorted(theirs, key=lambda p: -p['points'])[:depth]
                   if lineup_total(mine + [b], slots)[0] - base_me >= MIN_GAIN]
        for target in targets:
            best = None
            candidates = [((a,), FAIR_SINGLE) for a in offers_single] + [(pair, FAIR_PAIR) for pair in offers_pair]
            for give, fair in candidates:
                if sum(a['points'] for a in give) < fair * target['points']:
                    continue
                ids = {a['id'] for a in give}
                me_after, _ = lineup_total([m for m in mine if m['id'] not in ids] + [target], slots)
                them_after, _ = lineup_total([t for t in theirs if t['id'] != target['id']] + list(give), slots)
                gain, their_gain = me_after - base_me, them_after - base_them
                if gain >= MIN_GAIN and their_gain >= MIN_THEIR_GAIN:
                    score = gain + 0.5 * their_gain - 2 * (len(give) - 1)
                    if not best or score > best['score']:
                        best = {'score': score, 'give': [a['id'] for a in give], 'get': [target['id']],
                                'team': team_names.get(rid, 'Team ' + str(rid)), 'roster_id': rid,
                                'my_gain': round(gain, 1), 'their_gain': round(their_gain, 1)}
            if best:
                found.append(best)
    found.sort(key=lambda t: -t['score'])
    # One idea per target player and at most two per team, so the list stays varied.
    out, per_team, seen = [], {}, set()
    for t in found:
        if t['get'][0] in seen or per_team.get(t['roster_id'], 0) >= 2:
            continue
        seen.add(t['get'][0]); per_team[t['roster_id']] = per_team.get(t['roster_id'], 0) + 1
        out.append({k: v for k, v in t.items() if k != 'score'})
        if len(out) == limit:
            break
    return out
