"""Experimental blind four-turn mana/ramp audit, NOT a full rules engine.
Reuses opening_audit cost/payment primitives. Explicit supported effects only;
held cards remain physical draws but are never cast. See report assumptions.
Run: python3 ramp_opening_audit.py CONFIG --samples 3000 --seed 919 --output RESULT
"""
import argparse
from collections import Counter
from functools import lru_cache
from itertools import combinations
import hashlib
import json
import math
import platform
import random
from pathlib import Path
from opening_audit import parse_cost, payments

EFFECTS={'elf','roots','draw','interaction','body','haste','copy_target','held'}
ASSUMPTIONS=[
    'Bounded four-turn mana/deployment policy, no combat, opponent actions, removal or matchup/win-rate inference.',
    'Same physical slot permutations per trial and mulligan depth for both candidates and seats. Candidate keep decisions may differ.',
    'London to five: keep 2-4 lands and an actually payable <=2-mana active spell by turn two using only known hand; choose bottoms by that test, land balance and cheap active cards. Forced keep at five. Same conservative keep policy on play/draw, no future library knowledge.',
    'One land per turn. Deterministic greedy cast priority: early Elves, early Roots, then RR threats/three-drops, Price, other interaction; later ramp lower priority. Land choice uses current hand and next-turn land choices in that hand, never future draws.',
    'Compound colors require entering this turn OR a basic supertype land; typed shocks are not basic. Verge requires Forest OR Mountain type. Shocks cost two cumulatively only when selected untapped.',
    'Elves have summoning sickness unless a haste effect is present. Roots removes a real basic from the library, enters tapped, shuffles remaining library including London bottoms, and may immediately enable Compound colors. Fetch preference repairs available red toward RR, otherwise green.',
    'Price draws a real library card and may permit another land/spell action in the same turn. Opponent artifact/land/creature targets are assumed available. Avengers chooses land destruction only, never sweeps our Elves.',
    'copy_target copies targeted artifact/land spells (Price and land-mode interaction), including Price draw; Roots has no targets and is not copied. No interaction with opponents changes our resources.',
    'Optional prepared and warp abilities are not activated. Held effects are explicitly not cast, not approximated. Availability means isolated payment immediately after normal draw/land drop, before that turn spells, on the SAME prior actual trajectory; actual casts require drawn cards and spent mana.',
    'Life is shock damage only, no opponent damage. Seeded per-fetch physical-slot priority shuffle preserves paired randomness even when fetched basics differ. Future random keys never enter pilot decisions.',
]


def fetch_basic(cards,deck,library,preferred,turn):
    legal=[i for i in library if cards[deck[i]]['land'] and cards[deck[i]]['model']=='basic']
    if not legal:return None
    i=next((i for i in legal if deck[i]==preferred),legal[0])
    library.remove(i)
    return deck[i],turn,True


class RampPilot:
    def __init__(self,cards):
        self.cards=cards
        self.costs={n:parse_cost(c['cost']) for n,c in cards.items() if not c['land']}
        for n,c in cards.items():
            if c['land']:
                if c['model'] not in {'basic','shock','verge','compound','untapped'}:raise ValueError('Unsupported land '+n)
                if not set(c['colors'])<=set('WUBRGC'):raise ValueError('Bad colors')
                if c['model']=='basic' and not c['types']:raise ValueError('Basic needs types')
            elif c['effect'] not in EFFECTS:raise ValueError('Unsupported effect '+n)
    def mv(self,n):return len(self.costs[n][0])+self.costs[n][1]
    def resources(self,lands,elves,turn,haste=False):
        types={t for n,_,_ in lands for t in self.cards[n]['types']}
        basic=any(self.cards[n]['model']=='basic' for n,_,_ in lands)
        out=[]
        for i,(n,entered,tapped) in enumerate(lands):
            if entered==turn and tapped:continue
            c=self.cards[n];colors=c['colors']
            if c['model']=='compound':colors='CRG' if entered==turn or basic else 'C'
            if c['model']=='verge' and types.intersection(c['requires']):colors+=c['conditional']
            out.append((('land',i),colors))
        out.extend((('elf',i),'G') for i,t in enumerate(elves) if t<turn or haste)
        return out
    def sources(self,lands,elves,turn,haste=False):return tuple(c for _,c in self.resources(lands,elves,turn,haste))
    def can_pay(self,sources,n):return bool(payments(tuple(sources),*self.costs[n]))
    def priority(self,n,t):
        c=self.cards[n];e=c.get('effect')
        if e=='held':return -1
        if e=='elf':return 120 if t==1 else (105 if t==2 else 25)
        if e=='roots':return 110 if t<=2 else 35
        if c.get('threat'):return 100+self.mv(n)
        if self.mv(n)==3:return 95
        if e=='draw':return 80
        return 60+self.mv(n)
    def best_spell(self,hand,sources,t,board=()):
        ns=[n for n in set(hand) if not self.cards[n]['land'] and not (self.cards[n].get('legendary') and n in board) and self.priority(n,t)>=0 and self.can_pay(sources,n)]
        return max(ns,key=lambda n:(self.priority(n,t),n)) if ns else None
    @lru_cache(maxsize=100000)
    def choose_land(self,hand,lands,elves,turn,haste=False):
        choices=[(None,False)]+[(n,shock) for n in sorted(set(hand)) if self.cards[n]['land'] for shock in ([False,True] if self.cards[n]['model']=='shock' else [False])]
        best=None;bs=None
        for n,shock in choices:
            ls=lands+((n,turn,self.cards[n]['model']=='shock' and not shock),) if n else lands
            h=list(hand)
            if n:h.remove(n)
            src=self.sources(ls,elves,turn,haste);cast=self.best_spell(h,src,turn)
            future=0
            for extra in [None]+[x for x in sorted(set(h)) if self.cards[x]['land']]:
                fs=self.sources(ls+((extra,turn+1,False),) if extra else ls,elves,turn+1,haste)
                future=max(future,max((self.priority(x,turn+1) for x in set(h) if not self.cards[x]['land'] and self.priority(x,turn+1)>=0 and self.can_pay(fs,x)),default=0))
            nextsrc=self.sources(ls,elves,turn+1,haste)
            score=(self.priority(cast,turn) if cast else 0, future, -2*shock, bool(n), min(2,sum('R' in x for x in nextsrc)),any('G' in x for x in nextsrc),sum(len(x) for x in nextsrc))
            if bs is None or score>bs:bs=score;best=n,shock
        return best
    @lru_cache(maxsize=100000)
    def quality(self,hand):
        nl=sum(self.cards[n]['land'] for n in hand)
        early=False
        landnames=[n for n in hand if self.cards[n]['land']]
        for a in range(len(landnames)):
            for b in [None]+[i for i in range(len(landnames)) if i!=a]:
                ls=((landnames[a],1,False),)+(((landnames[b],2,False),) if b is not None else ())
                src=self.sources(ls,(),2)
                if any(not self.cards[n]['land'] and self.cards[n]['effect']!='held' and self.mv(n)<=2 and self.can_pay(src,n) for n in hand):early=True
        active=[n for n in hand if not self.cards[n]['land'] and self.cards[n]['effect']!='held']
        return (2<=nl<=4 and early,early,-abs(nl-3),len(active),-sum(self.mv(n) for n in active))
    def mulligan(self,hands):
        offered=[]
        for m,seven in enumerate(hands):
            options=[]
            for bottom in combinations(range(7),m):
                keep=tuple(sorted(seven[i] for i in range(7) if i not in bottom))
                options.append((self.quality(keep),bottom))
            q,b=max(options,key=lambda x:x[0]);offered.append({'seven':seven,'bottom_positions':b,'qualifies':q[0]})
            if q[0] or m==2:return m,b,q[0],offered
        raise ValueError('Need 3 offers')
    def play(self,deck,hand_ids,library_ids,on_play,seed):
        hand=[deck[i] for i in hand_ids];library=list(library_ids);lands=();elves=();board=[];life=0;fetches=0;trace=[];metrics={}
        for t in range(1,5):
            drawn=None
            if (t>1 or not on_play) and library:drawn=deck[library.pop(0)];hand.append(drawn)
            before=list(hand);haste=any(self.cards[n].get('effect')=='haste' for n in board)
            land,shock=self.choose_land(tuple(sorted(hand)),lands,elves,t,haste)
            if land:hand.remove(land);lands+=((land,t,self.cards[land]['model']=='shock' and not shock),)
            life+=2*shock;used=set();casts=[];draws=[];fetched=[]
            src=self.sources(lands,elves,t,haste);initial_src=src
            costs={'G':('G',0),'R':('R',0),'1G':('G',1),'1R':('R',1),'1RR':('RR',1),'2RR':('RR',2)}
            avail={k:bool(payments(src,*v)) for k,v in costs.items()}
            metrics.update({f't{t}_mana_{k}':v for k,v in avail.items()})
            rrhand=[n for n in hand if not self.cards[n]['land'] and self.costs[n][0].count('R')>=2 and self.mv(n)<=(3 if t==3 else 4) and self.cards[n]['effect']!='held']
            metrics[f't{t}_RR_in_hand']=bool(rrhand)
            metrics[f't{t}_RR_color_stall']=any(len(src)>=self.mv(n) and not self.can_pay(src,n) for n in rrhand)
            metrics[f't{t}_RR_mana_stall']=any(not self.can_pay(src,n) for n in rrhand)
            while True:
                haste=any(self.cards[n].get('effect')=='haste' for n in board)
                res=[(i,c) for i,c in self.resources(lands,elves,t,haste) if i not in used];src=tuple(c for _,c in res)
                n=self.best_spell(hand,src,t,board)
                if n is None:break
                opts=payments(src,*self.costs[n])
                # Preserve flexible/red sources, spend narrow green first for generic.
                pay=min(opts,key=lambda ix:(sum('R' in src[i] for i in ix),sum(len(src[i]) for i in ix),ix))
                used.update(res[i][0] for i in pay);hand.remove(n);casts.append(n);c=self.cards[n];e=c['effect']
                if e in {'body','haste','copy_target','elf'}:board.append(n)
                if e=='elf':elves+=(t,)
                if e=='roots':
                    allsrc=self.sources(lands,elves,t+1,haste)
                    preferred=next((x for x,v in self.cards.items() if v['land'] and v['model']=='basic' and ('Mountain' if sum('R' in s for s in allsrc)<2 else 'Forest') in v['types']),None)
                    entry=fetch_basic(self.cards,deck,library,preferred,t)
                    if entry:lands+=(entry,);fetched.append(entry[0])
                    fetches+=1;rng=random.Random(f'{seed}:fetch:{fetches}');keys={i:rng.random() for i in range(len(deck))};library.sort(key=keys.get)
                if e=='draw':
                    copies=1+sum(self.cards[b].get('effect')=='copy_target' for b in board)
                    for _ in range(c.get('draw',1)*copies):
                        if library:x=deck[library.pop(0)];hand.append(x);draws.append(x)
                # A land drawn by Price can be played if no land was played yet.
                if land is None and any(self.cards[x]['land'] for x in hand):
                    ln,sh=self.choose_land(tuple(sorted(hand)),lands,elves,t,haste)
                    if ln:land=ln;shock=sh;hand.remove(ln);lands+=((ln,t,self.cards[ln]['model']=='shock' and not sh),);life+=2*sh
            for e in ('elf','roots','draw'):
                metrics[f't{t}_cast_{e}']=any(self.cards[n]['effect']==e for n in casts)
            metrics[f't{t}_cast_R_one']=any(self.costs[n]==('R',0) for n in casts)
            metrics[f't{t}_cast_RR']=any(self.costs[n][0].count('R')>=2 for n in casts)
            metrics[f't{t}_cast_RR_threat']=any(self.cards[n].get('threat') and self.costs[n][0].count('R')>=2 for n in casts)
            trace.append(dict(turn=t,draw=drawn,hand_before=before,land=land,shock_life=2*int(shock),sources_before_spells=initial_src,availability=avail,casts=casts,effect_draws=draws,fetched=fetched,lands=lands,hand_after=list(hand),cumulative_life=life))
        metrics['curve_early_t2_t3RR']=(metrics['t1_cast_elf'] or metrics['t1_cast_R_one']) and (metrics['t2_cast_roots'] or metrics['t2_cast_draw']) and metrics['t3_cast_RR']
        metrics['RR_threat_by_t4']=any(metrics[f't{t}_cast_RR_threat'] for t in range(1,5))
        metrics['any_RR_color_stall_t3_t4']=metrics['t3_RR_color_stall'] or metrics['t4_RR_color_stall']
        metrics['life']=life
        return dict(metrics=metrics,life=life,trace=trace)


def run(config,samples,seed):
    if not 1<=samples<=20000:raise ValueError('samples 1..20000')
    decks=config['candidates'];pilot=RampPilot(config['cards']);size=len(next(iter(decks.values())))
    if size!=60 or any(len(d)!=size for d in decks.values()):raise ValueError('60 physical slots required')
    if any(n not in pilot.cards for d in decks.values() for n in d):raise ValueError('Unknown card')
    ref=next(iter(decks));rd=decks[ref]
    for d in decks.values():
        for a,b in zip(rd,d):
            if not (pilot.cards[a]['land'] and pilot.cards[b]['land']) and a!=b:raise ValueError('Nonland physical slots differ')
    rng=random.Random(seed);tot={n:{s:Counter() for s in ('play','draw')} for n in decks};ds={n:{s:Counter() for s in ('play','draw')} for n in decks};traces={n:{s:[] for s in ('play','draw')} for n in decks};hist={n:{s:Counter() for s in ('play','draw')} for n in decks}
    for trial in range(samples):
        orders=[]
        for _ in range(3):o=list(range(size));rng.shuffle(o);orders.append(o)
        outcomes={}
        for name,deck in decks.items():
            m,b,q,offered=pilot.mulligan([[deck[i] for i in o[:7]] for o in orders])
            o=orders[m];ids=[o[i] for i in range(7) if i not in b];lib=o[7:]+[o[i] for i in b]
            for seat in ('play','draw'):
                r=pilot.play(deck,ids,lib,seat=='play',f'{seed}:{trial}:{m}');metrics=r['metrics'];metrics.update(mulligan_ge1=m>=1,accepted5=m==2,forced5_failed_keep=m==2 and not q)
                tot[name][seat].update({k:int(v) for k,v in metrics.items()});outcomes[name,seat]=metrics;hist[name][seat][str(r['life'])]+=1
                ts=traces[name][seat]
                if trial<2 or (metrics['any_RR_color_stall_t3_t4'] and len(ts)<7):ts.append(dict(trial=trial,mulligans=m,accepted=[deck[i] for i in ids],offered=offered,**r))
        for n in decks:
            for s in ('play','draw'):
                for k,v in outcomes[n,s].items():d=int(v)-int(outcomes[ref,s][k]);ds[n][s][k]+=d;ds[n][s][k+'_sq']+=d*d
    return dict(model='ramp-opening-v1',samples_per_candidate_per_seat=samples,seed=seed,python=platform.python_version(),config_sha256=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),config=config,assumptions=ASSUMPTIONS,held_cards=[n for n,c in pilot.cards.items() if c.get('effect')=='held'],summary={n:{s:dict(counts=dict(c),rates={k:v/samples for k,v in c.items()},shock_life_histogram=dict(hist[n][s])) for s,c in ss.items()} for n,ss in tot.items()},paired_deltas={n:{s:{k:dict(delta=c[k]/samples,se=math.sqrt(max(0,c[k+'_sq']/samples-(c[k]/samples)**2)/samples)) for k in outcomes[n,s]} for s,c in ss.items()} for n,ss in ds.items()},traces=traces)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config');p.add_argument('--samples',type=int,default=3000);p.add_argument('--seed',type=int,default=919);p.add_argument('--output',required=True);a=p.parse_args()
    cfg=json.loads(Path(a.config).read_text());result=run(cfg,a.samples,a.seed);Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(dict(status='complete',samples=a.samples,output=a.output)))
