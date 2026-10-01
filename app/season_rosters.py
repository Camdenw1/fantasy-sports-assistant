"""Read-only Sleeper ownership and conservative, explainable waiver comparisons."""
import datetime as dt
from season_scoring import ELIGIBLE, unsupported


def discover(fetch, username):
    state=fetch('https://api.sleeper.app/v1/state/nfl'); season=str(state['season'])
    user=fetch('https://api.sleeper.app/v1/user/'+username)
    if not isinstance(user,dict) or not user.get('user_id'): raise ValueError('Sleeper username not found')
    leagues=fetch(f'https://api.sleeper.app/v1/user/{user["user_id"]}/leagues/nfl/{season}')
    if not isinstance(leagues,list): raise ValueError('League list unavailable')
    return {'engine_version':1,'reports':[{'username':username,'season':int(season),
        'leagues':[{'id':l['league_id'],'name':l['name']} for l in leagues if l.get('sport')=='nfl'],
        'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat()}]}


def context(fetch, username, league_id, season):
    user=fetch('https://api.sleeper.app/v1/user/'+username)
    if not isinstance(user,dict) or not user.get('user_id'): raise ValueError('Sleeper username not found')
    league=fetch('https://api.sleeper.app/v1/league/'+league_id)
    if str(league.get('season'))!=str(season) or league.get('sport')!='nfl': raise ValueError('League season does not match')
    rosters=fetch('https://api.sleeper.app/v1/league/'+league_id+'/rosters')
    if not isinstance(rosters,list) or len(rosters)!=league.get('total_rosters'): raise ValueError('League rosters are incomplete')
    mine=next((r for r in rosters if r.get('owner_id')==user['user_id'] or user['user_id'] in (r.get('co_owners') or [])),None)
    if mine is None: raise ValueError('No roster for this username in the selected league')
    if any(not isinstance(r.get('players'),list) for r in rosters): raise ValueError('League ownership unavailable')
    ids=[str(p) for r in rosters for p in r['players']]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate league ownership; refresh needed')
    settings=league.get('scoring_settings')
    slots=league.get('roster_positions')
    if not isinstance(settings,dict) or not isinstance(slots,list): raise ValueError('League scoring or roster rules unavailable')
    unknown=unsupported(settings)
    if unknown: raise ValueError('Unsupported scoring rules: '+', '.join(unknown))
    return {'league_id':league_id,'name':league['name'],'teams':len(rosters),
            'settings':settings,'slots':[s for s in slots if s in ELIGIBLE],
            'unsupported_slots':[s for s in slots if s not in ELIGIBLE and s not in {'BN','IR','K','DEF'}],
            'owned':set(str(x) for x in mine['players']), 'occupied':set(ids),
            'starters':set(str(x) for x in mine.get('starters') or []),
            'reserve':set(str(x) for x in mine.get('reserve') or []),
            'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat()}


def best_lineup(players, slots):
    """Maximum legal ROS starter total; each player and slot is used once."""
    if len(slots)>10: raise ValueError('Too many skill starter slots')
    best={0:(0.,[])}
    for p in players:
        for mask,(points,ids) in list(best.items()):
            for i,slot in enumerate(slots):
                bit=1<<i
                if mask&bit or p['position'] not in ELIGIBLE[slot]: continue
                key=mask|bit; score=points+p['points']
                if score>best.get(key,(-1,[]))[0]: best[key]=(score,ids+[p['id']])
    return best.get((1<<len(slots))-1)


def apply(result, ctx):
    indexed={p['id']:p for p in result['players']}
    mine=[p for p in result['players'] if p['id'] in ctx['owned']]
    for p in result['players']:
        p['ownership']='mine' if p['id'] in ctx['owned'] else ('rostered' if p['id'] in ctx['occupied'] else 'available')
    # Non-skill players (K/DEF/IDP) are outside this page's projection pool.
    unknown=[]
    metadata=ctx.get('player_metadata',{})
    for pid in ctx['owned']-indexed.keys():
        if metadata.get(pid,{}).get('position') not in {'K','DEF','DL','LB','DB','DE','DT','CB','S'}:
            unknown.append({'id':pid,'name':metadata.get(pid,{}).get('full_name') or pid})
    issues=list(result.get('health',{}).get('issues',[]))
    if unknown: issues.append('Some roster players have no remaining-season projection')
    if any(p.get('projection_complete') is False and p.get('injury') not in {'IR','PUP','NA','Out','Doubtful','Sus','DNR'} for p in mine):
        issues.append('A roster player has missing projected weeks without an inactive status')
    if ctx['unsupported_slots']: issues.append('Unsupported starter slots')
    baseline=best_lineup(mine,ctx['slots']) if not ctx['unsupported_slots'] else None
    if not baseline: issues.append('Not enough projected players to fill the skill lineup')
    suggestions=[]
    if not issues and baseline:
        protected=set(baseline[1]) | ctx['starters'] | ctx['reserve']
        bench=sorted((p for p in mine if p['id'] not in protected),key=lambda p:p['points'])
        available=[p for p in result['players'] if p['ownership']=='available' and p.get('projection_complete',True) and p.get('injury') not in {'IR','Out','Doubtful','PUP','NA','Sus','DNR'}]
        candidates=[p for pos in ['QB','RB','WR','TE'] for p in [a for a in available if a['position']==pos][:3]]
        for p in candidates:
            drop=next((b for b in bench if b['position']==p['position']),None)
            if not drop: continue
            improved=best_lineup([m for m in mine if m['id']!=drop['id']]+[p],ctx['slots'])
            gain=round(improved[0]-baseline[0],1) if improved else 0
            edge=round(p['points']-drop['points'],1)
            if edge>=15 and edge>=drop['points']*.2:
                suggestions.append({'pickup':p['id'],'drop':drop['id'],'starter_gain':gain,'projection_edge':edge,
                  'reason':'Potential starter upgrade' if gain>=10 else 'Stronger same-position bench projection'})
        suggestions.sort(key=lambda s:(-s['starter_gain'],-s['projection_edge']))
    result['roster']={'league_id':ctx['league_id'],'name':ctx['name'],'fetched_at':ctx['fetched_at'],
        'missing':unknown,'issues':issues,'suggestions':suggestions[:3],
        'keepers':baseline[1] if baseline and not issues else []}
