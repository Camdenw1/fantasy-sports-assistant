"""Projection layer: turn the repo's consensus tables into league-NEUTRAL player records.

Nothing in here knows any league's scoring. It reads refresh/proj.py (the same
consensus the live pipeline uses) through a sandbox so the prototype never
rewrites refresh/pubranks_cache.json: the cache is copied to a temp file and the
TTL is stretched so no network fetch happens and the inputs are byte-identical to
the last real build.
"""
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REFRESH = HERE.parent.parent / "refresh"


def _sandbox_sources():
    sys.path.insert(0, str(REFRESH))
    import sources  # noqa: E402
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ls_proto_")) / "pubranks_cache.json"
    shutil.copy(REFRESH / "pubranks_cache.json", tmp)
    sources.CACHE = tmp            # writes land in the temp copy, never the repo
    sources.TTL = 10 ** 12         # treat the cache as fresh: no network, exact inputs
    return sources


def load_players():
    """Return (players, pool_order) using the live consensus projections."""
    _sandbox_sources()
    cwd = os.getcwd()
    os.chdir(REFRESH)              # hp_data/proj read relative paths
    try:
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            import proj as P      # noqa: E402
            import hp_data as D   # noqa: E402
    finally:
        os.chdir(cwd)

    players = {}
    for n, tm, a, py, ptd, ry, rtd, av in P.QB:
        players[n] = dict(key=n, pos="QB", tm=tm, avail=av, season=dict(
            pass_yd=py, pass_td=ptd, pass_int=P.INT.get(n, 10), rush_yd=ry,
            rush_td=rtd, fum_lost=P.FUM.get(n, 0)))
    for n, tm, a, ra, ry, rtd, rc, red, retd, av in P.RB:
        players[n] = dict(key=n, pos="RB", tm=tm, avail=av, season=dict(
            rush_att=ra, rush_yd=ry, rush_td=rtd, rec=rc, rec_yd=red, rec_td=retd,
            fum_lost=P.FUM.get(n, 0)))
    for n, tm, a, rc, red, retd, ra, ry, rtd, av in P.WR:
        players[n] = dict(key=n, pos="WR", tm=tm, avail=av, season=dict(
            rec=rc, rec_yd=red, rec_td=retd, rush_att=ra, rush_yd=ry, rush_td=rtd,
            fum_lost=P.FUM.get(n, 0)))
    for n, tm, a, rc, red, retd, av in P.TE:
        players[n] = dict(key=n, pos="TE", tm=tm, avail=av, season=dict(
            rec=rc, rec_yd=red, rec_td=retd, fum_lost=P.FUM.get(n, 0)))
    for n, tm, a, fgm, fga, xpm, leg in P.K:
        players[n] = dict(key=n, pos="K", tm=tm, avail=1.0, leg=leg, season=dict(
            fgm=fgm, fga=fga, fgmiss=fga - fgm, xpm=xpm))
    for n, tm, a, sk, fr, it, dtd, pa, saf, ktd in P.DST:
        k = f"{tm} {n}"
        players[k] = dict(key=k, pos="DST", tm=tm, avail=1.0, season=dict(
            sack=sk, fum_rec=fr, def_int=it, def_td=dtd, st_td=ktd, safe=saf,
            pts_allow=pa))
    return players, D, P


# Stats a league may score that no feed projects, and the closest projected stat
# we stand in with. Every proxy is surfaced to the user as a caveat.
PROXIES = {"def_ff": ("fum_rec", "no feed projects forced fumbles; recoveries stand in")}
