"""Fetch free public draft-market, expert, injury, and projection data.

Replaces the old hand-pasted FantasyPros ECR and Flock Fantasy exports, which were
paid products. Everything here is public and needs no account or API key.

  FFC     fantasyfootballcalculator.com -- REAL half-PPR 12-team ADP from public
          mock drafts. This is the only source whose format exactly matches the
          league (half PPR, 12 teams), so it is the anchor.
  ESPN    ESPN's real PPR ADP. Kept as platform context, not included in the
          strict half-PPR market consensus.
  YAHOO   Yahoo's public draft-analysis feed -- average_pick across their drafts,
          where the default league scoring is 0.5/reception.
  RBALLER RotoBaller's free, expert-authored half-PPR overall Top 100. This is
          the expert-opinion lane, not ADP or another projection model.

The lanes stay distinct because ADP, expert rank, and market value answer different
questions. Sleeper supplies injuries and projections, not an official ADP column.
See fetch_mfl for why MyFantasyLeague is out.

Results are cached to pubranks_cache.json (gitignored) so a draft-day rebuild still
works without a network, and so repeated builds don't hammer anyone's API.
"""
import html, json, pathlib, re, sys, time, urllib.request, urllib.error

HERE = pathlib.Path(__file__).parent
CACHE = HERE / "pubranks_cache.json"
TTL = 6 * 3600          # refetch at most every 6 hours
UA = {"User-Agent": "fantasy-sports-assistant/1.0 (personal fantasy draft board)"}


def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _get_text(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ---------------------------------------------------------------- sources ---
def fetch_ffc(year):
    """Half-PPR, 12-team ADP from real public mock drafts. Format-exact."""
    d = _get(f"https://fantasyfootballcalculator.com/api/v1/adp/half-ppr"
             f"?teams=12&year={year}")
    meta = d.get("meta", {})
    out = {p["name"]: p["adp"] for p in d["players"] if p.get("adp")}
    extra = {p["name"]: {"bye": p.get("bye"), "stdev": p.get("stdev"),
                         "high": p.get("high"), "low": p.get("low"),
                         "pos": p.get("position"), "team": p.get("team")}
             for p in d["players"]}
    note = (f"{meta.get('total_drafts','?')} drafts, "
            f"{meta.get('start_date','?')}..{meta.get('end_date','?')}")
    return out, note, extra


def fetch_espn(year):
    """ESPN's real ADP from ESPN drafts (ownership.averageDraftPosition).

    Deliberately NOT draftRanksByRankType: that is a generic editorial board, and
    ESPN's STANDARD and PPR variants of it are byte-identical, so it carries no
    format information at all. averageDraftPosition is what people actually did.
    """
    filt = json.dumps({"players": {"limit": 400, "sortDraftRanks": {
        "sortPriority": 100, "sortAsc": True, "value": "PPR"}}})
    d = _get(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
             f"{year}/segments/0/leaguedefaults/3?view=kona_player_info",
             headers={"x-fantasy-filter": filt, "accept": "application/json"})
    out = {}
    for p in d.get("players", []):
        pp = p.get("player", p)
        adp = (pp.get("ownership") or {}).get("averageDraftPosition")
        nm = pp.get("fullName")
        if nm and adp and adp > 0:
            out[nm] = float(adp)
    return out, f"{len(out)} with ADP", {}


def fetch_sleeper(_year):
    """Sleeper's public player dump. search_rank is their draft-room ordering."""
    d = _get("https://api.sleeper.app/v1/players/nfl", timeout=90)
    out = {}
    for v in d.values():
        if not v.get("active"):
            continue
        if v.get("position") not in ("QB", "RB", "WR", "TE", "K", "DEF"):
            continue
        r, nm = v.get("search_rank"), v.get("full_name") or v.get("last_name")
        # Sleeper parks unranked players at a sentinel far past any draft
        if nm and r is not None and r < 2000:
            out[nm] = min(r, out.get(nm, r))
    return out, f"{len(out)} ranked", {}


def fetch_yahoo(_year):
    """Yahoo's public draft-analysis feed, paged 50 at a time."""
    out = {}
    for start in range(0, 300, 50):
        try:
            d = _get("https://pub-api-ro.fantasysports.yahoo.com/fantasy/v2/game/"
                     f"nfl/players;position=ALL;start={start};count=50;"
                     "sort=rank_season/draft_analysis?format=json_f",
                     headers={"accept": "application/json"})
        except urllib.error.HTTPError:
            break
        found = 0
        for p in _yahoo_players(d):
            nm = (p.get("name") or {}).get("full")
            ap = (p.get("draft_analysis") or {}).get("average_pick")
            if nm and ap:
                try:
                    out[nm] = float(ap)
                    found += 1
                except ValueError:
                    pass
        if not found:
            break
        time.sleep(0.4)          # be polite to a free endpoint
    return out, f"{len(out)} with ADP", {}


def _yahoo_players(node):
    """Yahoo nests players irregularly; walk for dicts that look like a player."""
    stack = [node]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if "draft_analysis" in o and "name" in o:
                yield o
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)


def fetch_trending(_year):
    """Sleeper's public trending-adds feed over the past week.

    Not a ranking -- a momentum signal. A player being added in volume right now
    is a player whose ADP is stale and who will go earlier than his board rank
    says. That is exactly the situation where you either reach a round early or
    lose him, so it is worth seeing next to the ranks.
    """
    trend = _get("https://api.sleeper.app/v1/players/nfl/trending/add"
                 "?lookback_hours=168&limit=200")
    ids = _get("https://api.sleeper.app/v1/players/nfl", timeout=90)
    out = {}
    for t in trend:
        v = ids.get(str(t.get("player_id")))
        if not v:
            continue
        nm = v.get("full_name") or v.get("last_name")
        if nm and t.get("count"):
            out[nm] = int(t["count"])
    return out, f"{len(out)} trending", {}


def fetch_mfl(year):
    """MyFantasyLeague ADP. NOT USED -- kept only so nobody re-adds it blind.

    MFL's ADP endpoint has no way to exclude superflex / 2QB drafts, and their
    pool is full of them. Measured against FFC on the 2026 board, MFL's QBs went
    an average of 38 slots EARLIER (Josh Allen 3rd overall vs FFC's 33rd) while
    its RBs and WRs went 7 and 20 slots later. That is superflex contamination,
    and it would wreck QB ranking in this 1QB league. IS_PPR=1 filters scoring,
    not roster format, so there is no fix on their side.
    """
    d = _get(f"https://api.myfantasyleague.com/{year}/export"
             "?TYPE=adp&FCOUNT=12&IS_PPR=1&IS_MOCK=-1&IS_KEEPER=N&JSON=1")
    adp = d["adp"]
    rows = adp["player"]
    names = _get(f"https://api.myfantasyleague.com/{year}/export?TYPE=players&JSON=1",
                 timeout=60)["players"]["player"]
    idx = {p["id"]: p for p in names}
    out = {}
    for r in rows:
        p = idx.get(r.get("id"))
        ap = r.get("averagePick")
        if not p or not ap:
            continue
        raw = p.get("name", "")
        if p.get("position") == "Def":
            nm = raw.replace(",", " ").strip() + " Defense"   # "Texans, Houston"
        elif "," in raw:
            last, first = [t.strip() for t in raw.split(",", 1)]
            nm = f"{first} {last}"
        else:
            nm = raw.strip()
        if nm:
            out[nm] = float(ap)
    return out, f"{adp.get('totalDrafts','?')} drafts", {}


def fetch_fantasycalc(_year):
    """FantasyCalc redraft values for EXACTLY this league: half PPR, 1 QB, 12 teams.

    Not ADP -- a market value derived from real league activity -- but it is
    format-exact and it is a genuinely independent read on the same question. It
    also carries every player's Sleeper id, which is how the injury feed joins on
    without any name matching at all.
    """
    d = _get("https://api.fantasycalc.com/values/current"
             "?isDynasty=false&numQbs=1&numTeams=12&ppr=0.5")
    out, extra = {}, {}
    for r in d:
        pl = r.get("player") or {}
        nm, rk = pl.get("name"), r.get("overallRank")
        if not nm or not rk:
            continue
        out[nm] = rk
        extra[nm] = {"trend30": r.get("trend30Day"),
                     "sleeper_id": pl.get("sleeperId"),
                     "tier": r.get("maybeTier")}
    return out, f"{len(out)} ranked (half-PPR/1QB/12tm)", extra


def fetch_rotoballer(_year):
    """Free RotoBaller half-PPR expert rankings from its stable rankings page.

    The page publishes its current top 100 as schema.org JSON-LD, including an
    explicit order and update timestamp. We intentionally use the structured
    half-PPR endpoint instead of chasing RotoBaller's dated ranking articles.
    """
    raw = _get_text(
        "https://www.rotoballer.com/nfl-fantasy-football-rankings-tiered-ppr/"
        "265860/rankings?spreadsheet=half-ppr&league=Overall")
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw, flags=re.I | re.S)
    modified_hit = re.search(r'"dateModified"\s*:\s*"([^"]+)"', raw)
    modified = modified_hit.group(1) if modified_hit else "?"
    for block in blocks:
        try:
            doc = json.loads(html.unescape(block))
        except (json.JSONDecodeError, TypeError):
            continue
        docs = doc if isinstance(doc, list) else [doc]
        for root in docs:
            if not isinstance(root, dict):
                continue
            graph = root.get("@graph", [])
            candidates = [root, *graph] if isinstance(graph, list) else [root]
            for item_list in candidates:
                if not isinstance(item_list, dict) or item_list.get("@type") != "ItemList":
                    continue
                out = {item["name"].strip(): float(item["position"])
                       for item in (item_list.get("itemListElement") or [])
                       if item.get("name") and item.get("position")}
                if len(out) >= 90:
                    return out, (f"{len(out)} expert half-PPR ranks, "
                                 f"updated {modified} (free public Top 100)"), {}
    raise ValueError("RotoBaller structured half-PPR Top 100 not found")


def fetch_injuries(_year):
    """Live injury status from Sleeper's public player dump.

    Sleeper carries injury_status (IR / PUP / Out / Doubtful / Questionable /
    Sus), the body part, and roster status for every player, updated constantly.
    Returned as a rank-shaped dict so it rides the same cache machinery;
    the payload is in the extras.
    """
    d = _get("https://api.sleeper.app/v1/players/nfl", timeout=90)
    out, extra = {}, {}
    for v in d.values():
        nm = v.get("full_name")
        st = v.get("injury_status")
        if not nm or not st:
            continue
        if v.get("position") not in ("QB", "RB", "WR", "TE", "K", "DEF"):
            continue
        out[nm] = 1
        extra[nm] = {"status": st,
                     "body": v.get("injury_body_part"),
                     "roster": v.get("status"),
                     "note": (v.get("injury_notes") or "")[:160],
                     "practice": v.get("practice_participation")}
    return out, f"{len(out)} carrying an injury tag", extra


# ------------------------------------------------------- projections --------
# The board's stat projections used to come from a single hand-entered source,
# which was the largest weakness in the whole model: every ranking inherited its
# errors, and its touchdown counts were INTEGERS -- 28 players sat at exactly 7
# receiving TDs. A touchdown is 6 points, so rounding them is expensive. These two
# feeds are free, cover the pool, and give fractional expectations.

ESPN_STAT = {"3":"passYd","4":"passTD","20":"int","24":"ruYd","25":"ruTD",
             "42":"reYd","43":"reTD","53":"rec","23":"ruAtt","58":"tgt"}


def fetch_espn_proj(year):
    """ESPN's own season projections -- fractional, and already in the payload
    we download for ADP, so this costs one extra parse and no extra request."""
    filt = json.dumps({"players": {"limit": 400, "sortDraftRanks": {
        "sortPriority": 100, "sortAsc": True, "value": "PPR"}}})
    d = _get(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
             f"{year}/segments/0/leaguedefaults/3?view=kona_player_info",
             headers={"x-fantasy-filter": filt, "accept": "application/json"})
    out, extra = {}, {}
    for pl in d.get("players", []):
        pp = pl.get("player", pl)
        blk = [b for b in (pp.get("stats") or [])
               if b.get("statSourceId") == 1 and b.get("scoringPeriodId") == 0
               and b.get("seasonId") == year]
        nm = pp.get("fullName")
        if not blk or not nm:
            continue
        st = blk[0].get("stats") or {}
        line = {v: float(st.get(k, 0) or 0) for k, v in ESPN_STAT.items()}
        if sum(line.values()) <= 0:
            continue
        out[nm] = 1
        extra[nm] = line
    return out, f"{len(extra)} season projections", extra


SLEEPER_STAT = {"pass_yd":"passYd","pass_td":"passTD","pass_int":"int",
                "rush_att":"ruAtt","rush_yd":"ruYd","rush_td":"ruTD",
                "rec":"rec","rec_yd":"reYd","rec_td":"reTD","fum_lost":"fumLost"}


def fetch_sleeper_proj(year):
    """Sleeper's season projections, which are natively half-PPR scored and are
    the only source carrying fum_lost -- the -2 the league charges for a lost
    fumble, which the board could not model before."""
    out, extra = {}, {}
    for pos in ("QB", "RB", "WR", "TE"):
        try:
            d = _get(f"https://api.sleeper.app/projections/nfl/{year}"
                     f"?season_type=regular&position[]={pos}"
                     "&order_by=pts_half_ppr", timeout=60)
        except Exception:                        # noqa: BLE001
            continue
        for r in d:
            pl = r.get("player") or {}
            nm = " ".join(x for x in (pl.get("first_name"), pl.get("last_name")) if x)
            st = r.get("stats") or {}
            if not nm or not st:
                continue
            line = {v: float(st.get(k, 0) or 0) for k, v in SLEEPER_STAT.items()}
            gp = float(st.get("gp") or 0)
            # Sleeper projects an 18-game slate; rescale to the 17 the league plays
            if gp > 17.5:
                line = {k: v * 17.0 / gp for k, v in line.items()}
            if sum(line.values()) <= 0:
                continue
            out[nm] = 1
            extra[nm] = line
        time.sleep(0.3)
    return out, f"{len(extra)} season projections", extra


SOURCES = [("ffc", fetch_ffc), ("yahoo", fetch_yahoo),
           ("rotoballer", fetch_rotoballer), ("fcalc", fetch_fantasycalc),
           ("espn", fetch_espn), ("injuries", fetch_injuries),
           ("espnproj", fetch_espn_proj), ("sleeperproj", fetch_sleeper_proj)]

RANK_SOURCES = ("ffc", "yahoo", "rotoballer", "fcalc", "espn")


# ------------------------------------------------------------------ cache ---
LAST_META = {}


def _cache_sources(cache):
    """Read v2 cache or migrate the old one-timestamp shape in memory."""
    if isinstance(cache.get("sources"), dict):
        return dict(cache["sources"])
    fetched = cache.get("fetched_at", 0)
    return {
        key: {"fetched_at": fetched, "data": value,
              "note": cache.get("notes", {}).get(key, "legacy cache"),
              "extra": cache.get("extras", {}).get(key, {})}
        for key, value in cache.get("data", {}).items()
    }


def load(year=2026, refresh=False, quiet=False):
    """Return {source: {name: value}} plus notes and per-source extras.

    Falls back to cache per-source on any network failure, so a build on draft
    day never dies because someone's API is having a bad afternoon.
    """
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text())
        except json.JSONDecodeError:
            cache = {}

    now = time.time()
    cached = _cache_sources(cache)
    data, notes, extras, meta = {}, {}, {}, {}

    for key, fn in SOURCES:
        entry = cached.get(key, {})
        fetched_at = float(entry.get("fetched_at", 0) or 0)
        is_fresh = (not refresh and fetched_at > now - TTL and entry.get("data"))
        status = "cached"
        if is_fresh:
            data[key] = entry["data"]
            notes[key] = entry.get("note", "cached") + " (cached)"
            extras[key] = entry.get("extra", {})
        else:
            try:
                got, note, extra = fn(year)
                floor = 50 if key in RANK_SOURCES else 10
                if len(got) < floor:
                    raise ValueError(f"only {len(got)} rows -- looks broken")
                data[key], notes[key], extras[key] = got, note, extra or {}
                fetched_at, status = now, "live"
                cached[key] = {"fetched_at": fetched_at, "data": got,
                               "note": note, "extra": extra or {}}
            except Exception as e:                 # noqa: BLE001 - keep last known good
                stale = entry.get("data")
                if stale:
                    age = max(0, now - fetched_at) / 3600
                    data[key] = stale
                    extras[key] = entry.get("extra", {})
                    notes[key] = (f"FETCH FAILED ({type(e).__name__}) -- using "
                                  f"{age:.1f}h-old cache")
                    status = "stale"
                else:
                    notes[key] = f"FETCH FAILED ({type(e).__name__}) -- NO CACHE, dropped"
                    status = "missing"
        meta[key] = {"fetched_at": fetched_at or None,
                     "age_hours": round(max(0, now - fetched_at) / 3600, 1) if fetched_at else None,
                     "status": status, "rows": len(data.get(key, {})),
                     "note": notes[key]}
        if not quiet:
            print(f"  {key:8} {len(data.get(key, {})):4} {notes[key]}")

    if cached:
        CACHE.write_text(json.dumps({"version": 2, "sources": cached}))
    global LAST_META
    LAST_META = meta
    return data, notes, extras


if __name__ == "__main__":
    print("fetching public half-PPR rankings...")
    d, n, x = load(refresh="--refresh" in sys.argv)
    print(f"\n{len(d)} sources, {len(x)} source-extra groups")
