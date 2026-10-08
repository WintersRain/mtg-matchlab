"""Bounded opening-deployment audit, not a Magic rules/game engine.
Explicit slot configs, London-to-five, blind-to-library deterministic pilot.
Run: python3 opening_audit.py CONFIG --samples 3000 --seed 917 --output RESULT
"""
import argparse
from collections import Counter
from functools import lru_cache
from itertools import combinations
import hashlib
import json
import math
import random
import re


def parse_cost(cost):
    tokens = re.findall(r'\{([^}]+)\}', cost)
    if ''.join('{'+x+'}' for x in tokens) != cost or any(not (x.isdigit() or x in 'WUBRGC') for x in tokens):
        raise ValueError('Unsupported cost: '+cost)
    return ''.join(x for x in tokens if not x.isdigit()), sum(int(x) for x in tokens if x.isdigit())


@lru_cache(maxsize=100000)
def payments(sources, colored, generic):
    if len(sources) < len(colored)+generic:
        return ()
    if colored:
        results=set()
        for i,s in enumerate(sources):
            if colored[0] in s:
                for used in payments(sources[:i]+sources[i+1:],colored[1:],generic):
                    results.add(tuple(sorted((i,)+tuple(j+(j>=i) for j in used))))
        return tuple(sorted(results))
    return tuple(combinations(range(len(sources)),generic))


class Pilot:
    def __init__(self, cards):
        self.cards=cards
        self.costs={n:parse_cost(c['cost']) for n,c in cards.items() if not c['land']}
        for c in cards.values():
            if c['land'] and c['model'] not in ('basic','verge','shock','fast','untapped','tapped'):
                raise ValueError('Unsupported land')

    @lru_cache(maxsize=100000)
    def colors(self, lands):
        types={t for n in lands for t in self.cards[n]['types']}
        return tuple(self.cards[n]['colors']+(self.cards[n]['conditional'] if self.cards[n]['model']=='verge' and types.intersection(self.cards[n]['requires']) else '') for n in lands)

    def mv(self,n):
        c,g=self.costs[n]
        return len(c)+g

    @lru_cache(maxsize=100000)
    def bundles(self, hand, sources, board):
        best=((),hand,0)
        for n in sorted(set(hand)):
            c=self.cards[n]
            if c['land'] or not c['body'] or (c.get('legendary') and n in board):
                continue
            for used in payments(sources,*self.costs[n]):
                rest=list(hand);rest.remove(n)
                new_sources=tuple(s for i,s in enumerate(sources) if i not in used)
                casts,remaining,spent=self.bundles(tuple(rest),new_sources,tuple(sorted(board+(n,))))
                candidate=((n,)+casts,remaining,spent+self.mv(n))
                if (len(candidate[0]),candidate[2],candidate[0])>(len(best[0]),best[2],best[0]):
                    best=candidate
        return best

    @lru_cache(maxsize=100000)
    def turn(self, hand, lands, board, turn):
        choices=[(None,False)]
        for n in sorted(set(hand)):
            if self.cards[n]['land']:
                choices.append((n,False))
                if self.cards[n]['model']=='shock':choices.append((n,True))
        best=None;best_score=None
        for land,shock in choices:
            h=list(hand);newlands=lands
            if land:
                h.remove(land);newlands=lands+(land,)
            sources=self.colors(newlands)
            tapped=land and (self.cards[land]['model']=='tapped' or (self.cards[land]['model']=='shock' and not shock) or (self.cards[land]['model']=='fast' and len(lands)>2))
            ready=sources[:-1] if tapped else sources
            casts,remaining,spent=self.bundles(tuple(h),ready,board)
            newboard=tuple(sorted(board+casts))
            # Tie-break only using cards already seen: best next-turn deployment
            # with one of the lands currently in hand. No future draws consulted.
            future=0
            for extra in [None]+[n for n in set(remaining) if self.cards[n]['land']]:
                future_lands=newlands+((extra,) if extra else ())
                future_sources=self.colors(future_lands)
                if extra and (self.cards[extra]['model']=='tapped' or self.cards[extra]['model']=='fast' and len(newlands)>2):future_sources=future_sources[:-1]
                rh=list(remaining)
                if extra:rh.remove(extra)
                fc,_,_=self.bundles(tuple(rh),future_sources,newboard)
                future=max(future,len(fc))
            stranded=any(not self.cards[n]['land'] and self.cards[n]['body'] and not (self.cards[n].get('legendary') and n in board) and self.mv(n)<=len(ready) and not payments(ready,*self.costs[n]) for n in h)
            score=(len(casts),spent,future,-2*shock,len(newlands),len(set(''.join(sources))))
            result={'hand':remaining,'lands':newlands,'board':newboard,'casts':casts,'land':land,'life':2*int(shock),'tapped':bool(tapped),'color_stranded':stranded}
            if best_score is None or score>best_score:best_score=score;best=result
        return best

    @lru_cache(maxsize=100000)
    def keep(self,hand):
        count=sum(self.cards[n]['land'] for n in hand)
        if not 2<=count<=4:return False
        r=self.play(hand,(),True)
        return r['early_body'] and r['body_count']>=2

    def bottom(self,seven,m):
        best=None;score=None
        for idx in combinations(range(7),m):
            h=tuple(sorted(n for i,n in enumerate(seven) if i not in idx))
            lands=sum(self.cards[n]['land'] for n in h)
            r=self.play(h,(),True)
            s=(self.keep(h),r['early_body'],r['body_count'],-abs(lands-3),-sum(self.mv(n) for n in h if not self.cards[n]['land']),-r['life'])
            if score is None or s>score:best=(h,tuple(seven[i] for i in idx));score=s
        return best

    def mulligan(self,hands):
        offered=[]
        for m,seven in enumerate(hands[:3]):
            hand,bottom=self.bottom(seven,m)
            qualifies=self.keep(hand)
            offered.append({'seven':seven,'bottom':bottom,'qualifies':qualifies})
            if qualifies or m==2:return hand,bottom,m,qualifies,offered
        raise ValueError('Need three offered hands')

    def play(self,hand,draws,on_play,trace=False):
        h=tuple(sorted(hand));lands=();board=();life=0;early=False;next3=False;stranded=False;steps=[];drawidx=0;body2=0;cast_names=();color_stall=False
        tapped_entries=0;mana_spent=0
        for t in range(1,4):
            drawn=None
            if (t>1 or not on_play) and drawidx<len(draws):
                drawn=draws[drawidx];drawidx+=1;h=tuple(sorted(h+(drawn,)))
            r=self.turn(h,lands,board,t)
            if trace:steps.append({'turn':t,'draw':drawn,'hand_before':h,**r})
            h=r['hand'];lands=r['lands'];board=r['board'];life+=r['life']
            tapped_entries+=int(r['tapped']);mana_spent+=sum(self.mv(n) for n in r['casts'])
            if t<=2:early=early or bool(r['casts']);body2+=len(r['casts'])
            if t==3:next3=early and bool(r['casts'])
            cast_names+=r['casts']
            if t>=2:
                stranded=stranded or r['color_stranded']
                color_stall=color_stall or (r['color_stranded'] and not r['casts'])
        return {'early_body':early,'next_deployment_t3':next3,'two_bodies_by_t3':early and len(board)>=2,'body_count':len(board),'body2':body2,'life':life,'tapped_entries':tapped_entries,'mana_spent':mana_spent,'color_stranded':stranded,'color_stall':color_stall,'cast_names':cast_names,'trace':steps}


def run(config,samples,seed):
    cards=config['cards'];pilot=Pilot(cards);decks=config['candidates']
    size=len(next(iter(decks.values())))
    if any(len(d)!=size for d in decks.values()):raise ValueError('Pairing needs equal deck sizes')
    # Same slot permutations for each candidate, seat, and mulligan depth.
    totals={n:{seat:Counter() for seat in ('play','draw')} for n in decks}
    deltas={n:{s:Counter() for s in ('play','draw')} for n in decks}
    traces={n:[] for n in decks};rng=random.Random(seed);base=next(iter(decks))
    for trial in range(samples):
        orders=[]
        for m in range(3):
            order=list(range(size));rng.shuffle(order);orders.append(order)
        outcomes={}
        for name,deck in decks.items():
            hands=[[deck[i] for i in o[:7]] for o in orders]
            hand,bottom,m,qualified,offered=pilot.mulligan(hands)
            for seat in ('play','draw'):
                draws=[deck[i] for i in orders[m][7:10]]
                r=pilot.play(hand,draws,seat=='play',trace=trial<3)
                metrics={'mulligan_ge1':m>=1,'mulligan_ge2':m>=2,'accepted5':m==2,'forced5_failed_keep':m==2 and not qualified,'early_body':r['early_body'],'next_deployment_t3':r['next_deployment_t3'],'two_bodies_by_t3':r['two_bodies_by_t3'],'color_stranded_keep':r['color_stranded']}
                metrics['color_stall_keep']=r['color_stall']
                counts=totals[name][seat]
                counts.update({'cast:'+n:q for n,q in Counter(r['cast_names']).items()})
                counts.update({k:int(v) for k,v in metrics.items()});counts['life_'+str(r['life'])]+=1
                if m!=2:counts['accepted'+str(7-m)]+=1
                counts['accepted'+str(7-m)+'_early']+=r['early_body']
                counts['accepted'+str(7-m)+'_next3']+=r['next_deployment_t3']
                counts['tapped_entries']+=r['tapped_entries'];counts['mana_spent']+=r['mana_spent']
                outcomes[name,seat]=metrics
                if trial<3 or (len(traces[name])<9 and (not r['early_body'] or r['color_stranded'])):
                    if not r['trace']:r=pilot.play(hand,draws,seat=='play',trace=True)
                    traces[name].append({'trial':trial,'seat':seat,'mulligans':m,'offered':offered,'accepted':hand,'bottom':bottom,**r})
        for name in decks:
            for seat in ('play','draw'):
                for k,v in outcomes[name,seat].items():
                    d=int(v)-int(outcomes[base,seat][k]);deltas[name][seat][k]+=d;deltas[name][seat][k+'_sq']+=d*d
    summary={n:{s:{'counts':dict(c),'rates':{k:v/samples for k,v in c.items()}} for s,c in seats.items()} for n,seats in totals.items()}
    paired={n:{s:{k:{'delta':c[k]/samples,'se':math.sqrt(max(0,c[k+'_sq']/samples-(c[k]/samples)**2)/samples)} for k in outcomes[n,s]} for s,c in seats.items()} for n,seats in deltas.items()}
    return {'samples_per_candidate_per_seat':samples,'seed':seed,'config_sha256':hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),'summary':summary,'paired_deltas_vs_baseline':paired,'traces':traces}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config');p.add_argument('--samples',type=int,default=3000);p.add_argument('--seed',type=int,default=917);p.add_argument('--output',required=True);args=p.parse_args()
    if not 1<=args.samples<=20000:p.error('samples must be 1..20000')
    with open(args.config) as f:cfg=json.load(f)
    result=run(cfg,args.samples,args.seed)
    with open(args.output,'w') as f:json.dump(result,f,indent=2)
    print(json.dumps({'status':'complete','output':args.output,'samples':args.samples}))
