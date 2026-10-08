"""Expected weekly skill-player scoring. No frozen draft inputs or injury multiplier."""
import math

STANDARD = {'pass_yd':.04,'pass_td':4,'pass_int':-2,'rush_yd':.1,'rush_td':6,
            'rec':.5,'rec_yd':.1,'rec_td':6,'fum_lost':-2}
CAMDEN = dict(STANDARD, bonus_rec_te=.25, bonus_rush_yd_100=3,
              bonus_rush_yd_200=4, bonus_rec_yd_100=3, bonus_rec_yd_200=4,
              bonus_pass_yd_300=3, bonus_pass_yd_400=4)
SLOTS = {'camden':['QB','RB','RB','WR','WR','TE','FLEX','REC_FLEX'],
         'dad':['QB','RB','RB','WR','WR','TE','FLEX','FLEX']}
ELIGIBLE = {'QB':{'QB'},'RB':{'RB'},'WR':{'WR'},'TE':{'TE'},
            'FLEX':{'RB','WR','TE'},'REC_FLEX':{'WR','TE'},
            'WRRB_FLEX':{'WR','RB'},'SUPER_FLEX':{'QB','RB','WR','TE'}}
# Only explicitly modelled skill rules are accepted; unsupported nonzero rules
# never silently fall back to half PPR.
LINEAR = {'pass_yd','pass_td','pass_int','pass_2pt','pass_att','pass_cmp','pass_inc',
          'rush_yd','rush_td','rush_att','rush_2pt','rec','rec_yd','rec_td','rec_tgt',
          'rec_2pt','fum','fum_lost','fum_rec_td','bonus_rec_te','bonus_rec_rb','bonus_rec_wr',
          'bonus_rush_td_qb','pass_sack'}
BONUSES = {'bonus_rush_yd_100','bonus_rush_yd_200','bonus_rec_yd_100',
           'bonus_rec_yd_200','bonus_pass_yd_300','bonus_pass_yd_400'}
DEFENSE = {'pts_allow','yds_allow','sack','int','fum_rec','ff','def_td','safe',
           'blk_kick','def_st_td','def_st_fum_rec','def_st_ff','st_td','st_fum_rec','st_ff'}


def unsupported(settings):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in settings.values()):
        raise ValueError('League scoring contains invalid values')
    return sorted(k for k,v in settings.items() if v and k not in LINEAR | BONUSES | DEFENSE
                  and not k.startswith(('fg','xp','pts_allow_','yds_allow_','def_','st_')))


def gamma_survival(mean, cv, threshold):
    """Regularized upper gamma tail, evaluated by series/continued fraction."""
    if mean <= 0: return 0.
    a, x = 1 / cv**2, threshold / (mean * cv**2)
    log = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1:
        term = total = 1/a
        for n in range(1,201):
            term *= x/(a+n); total += term
            if abs(term) < abs(total)*1e-12: break
        return max(0.,min(1.,1-total*math.exp(log)))
    tiny=1e-30; b=x+1-a; c=1/tiny; d=1/max(b,tiny); h=d
    for n in range(1,201):
        an=-n*(n-a); b+=2; d=an*d+b; c=b+an/c
        if abs(d)<tiny: d=tiny
        if abs(c)<tiny: c=tiny
        d=1/d; delta=d*c; h*=delta
        if abs(delta-1)<1e-12: break
    return max(0.,min(1.,math.exp(log)*h))


def reception_buckets(mean, pos):
    if mean <= 0: return 0.
    r=4.5; success=r/(r+mean); probability=success**r; cumulative=probability
    start=3 if pos in {'RB','TE'} else 5
    thresholds=set(range(start,start+18,2))
    expected=0.
    for n in range(1,24):
        if n in thresholds: expected += max(0.,1-cumulative)
        probability *= (n-1+r)/n*(1-success); cumulative += probability
    return expected


def td_value(base, values, z):
    mid=[3,8,15,25,35,45,55,65,75,85,95]
    logs=[math.log(x) for x in mid]; m=sum(p*x for p,x in zip(base,logs))
    sd=math.sqrt(sum(p*(x-m)**2 for p,x in zip(base,logs)))
    weights=[p*math.exp(.35*max(-1.5,min(1.5,z))*(x-m)/sd) for p,x in zip(base,logs)]
    return sum(p*v for p,v in zip(weights,values))/sum(weights)


def weekly_score(stats, pos, settings=None, dad=False):
    if dad:
        # Same documented TD distributions/tilts as Dad's draft model; gamma
        # yardage and negative-binomial catches give expected bucket payouts.
        yards=sum(gamma_survival(stats.get(k,0),cv,step*i) for k,cv,step,cap in
                  [('pass_yd',.30,75,7),('rush_yd',.75 if pos=='QB' else .65,25,9),('rec_yd',.65,20,10)]
                  for i in range(1,cap+1))
        passing=[.28,.18,.20,.12,.08,.05,.04,.025,.015,.007,.003]
        rushing=[.58,.16,.12,.055,.03,.02,.014,.009,.005,.004,.003]
        ypr=stats.get('rec_yd',0)/max(stats.get('rec',0),1)
        centre,spread={'WR':(12.6,2.6),'TE':(11,2.2),'RB':(8,2.5)}.get(pos,(11.5,2.6))
        ypc=stats.get('rush_yd',0)/max(stats.get('rush_att',0),1)
        rush=td_value(rushing,[4,4,5,5,6,6,7,7,8,9,10],-.3 if pos=='QB' else (ypc-4.3)/.7)
        rec=td_value(passing,[3,3,4,4,5,5,6,6,7,8,9],(ypr-centre)/spread if ypr else 0)
        return yards + (reception_buckets(stats.get('rec',0),pos) if pos!='QB' else 0) + stats.get('pass_td',0)*sum(p*v for p,v in zip(passing,[3,3,4,4,5,5,6,6,7,8,9])) + stats.get('rush_td',0)*rush + stats.get('rec_td',0)*rec
    settings=STANDARD if settings is None else settings
    total=sum(stats.get(k,0)*v for k,v in settings.items() if k in LINEAR and not k.startswith('bonus_'))
    total += stats.get('rec',0)*settings.get('bonus_rec_'+pos.lower(),0)
    if pos=='QB': total+=stats.get('rush_td',0)*settings.get('bonus_rush_td_qb',0)
    for stat, cv, low, high in [('rush_yd',.75 if pos=='QB' else .65,100,200),('rec_yd',.65,100,200),('pass_yd',.30,300,400)]:
        key='bonus_'+stat+'_'; lo=settings.get(key+str(low),0); hi=settings.get(key+str(high),0)
        total += lo*gamma_survival(stats.get(stat,0),cv,low) + (hi-lo if hi else 0)*gamma_survival(stats.get(stat,0),cv,high)
    return total
