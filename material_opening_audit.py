"""Experimental four-turn material stress audit. Not a full Magic game.
Explicit ETB bodies/offspring, real Passage library consumption, London-to-five.
Targeted/counter/draw/combat triggers and recursion deliberately unmodeled.
Removal is an abstract one-body deletion after turns 2 and 3, not a card simulation.
"""
import argparse,json,random,hashlib
from collections import Counter
from itertools import combinations
from opening_audit import payments,parse_cost
BASICS={'Forest','Island','Swamp','Mountain','Plains'}
def passage(library,basic,controlled_after_replacement):
 if basic not in BASICS:raise ValueError('Passage only fetches basics')
 if basic not in library:return None
 library.remove(basic)
 return basic,controlled_after_replacement<4

def entry_tapped(model,other,shock=False):
 if model not in {'basic','untapped','fast','shock','tapped','passage'}:raise ValueError('Unsupported land')
 return model=='tapped' or model=='fast' and other>2 or model=='shock' and not shock

class MaterialPilot:
 def __init__(self,cards):
  self.cards=cards;self.cost={n:parse_cost(c['cost']) for n,c in cards.items() if not c['land']}
  for c in cards.values():
   if c['land']:entry_tapped(c['model'],0)
 def options(self,hand,sources,board):
  opts=[]
  for n in sorted(set(hand)):
   c=self.cards[n]
   if c['land'] or not c.get('body') or c.get('legendary') and any(x[0]==n for x in board):continue
   colored,generic=self.cost[n]
   for offspring in ([False,True] if c.get('offspring') else [False]):
    for pay in payments(tuple(sources),colored,generic+(2 if offspring else 0)):
     bodies=1+c.get('tokens',0)+int(offspring)
     # Material first, then mana utilization; payoff when another target exists.
     score=(bodies,len(pay),int(c.get('anchor',False) and bool(board)),n)
     opts.append((score,n,pay,offspring))
  return max(opts) if opts else None
 def choose(self,hand,lands,board,library):
  opts=[(None,None,False)]; cs=self.cards
  for n in sorted(set(hand)):
   if not cs[n]['land']:continue
   if cs[n]['model']=='passage':opts += [(n,b,False) for b in sorted(BASICS) if b in library]
   else:opts += [(n,None,s) for s in ([False,True] if cs[n]['model']=='shock' else [False])]
  best=None;score=None
  for n,fetch,shock in opts:
   h=list(hand)
   if n:h.remove(n)
   actual=fetch or n;new=lands+([actual] if actual else [])
   tapped=(len(new)<4 if fetch else entry_tapped(cs[n]['model'],len(lands),shock)) if n else False
   sources=[cs[x]['colors'] for x in new];ready=sources[:-1] if tapped else sources
   cast=self.options(h,ready,board)
   future=0
   for extra in [None]+[x for x in set(h) if cs[x]['land'] and cs[x]['model']!='passage']:
    fs=sources+([cs[extra]['colors']] if extra else [])
    fh=list(h)
    if extra:fh.remove(extra)
    fc=self.options(fh,fs,board)
    future=max(future,(fc[0][0]*10+fc[0][1]) if fc else 0)
   val=((cast[0][0]*10+cast[0][1]) if cast else 0,future,-2*shock,bool(n),len(set(''.join(sources))))
   if score is None or val>score:score=val;best=(n,fetch,shock,tapped)
  return best
 def play(self,hand,library,on_play=True,seed=0,turns=4,remove=True,draw=True):
  hand=list(hand);library=list(library);lands=[];board=[];trace=[];life=0;metrics=Counter();rng=random.Random(seed)
  for t in range(1,turns+1):
   drawn=None
   if draw and (t>1 or not on_play) and library:drawn=library.pop(0);hand.append(drawn)
   before=list(hand);n,fetch,shock,tapped=self.choose(hand,lands,board,library)
   if n:
    hand.remove(n)
    if fetch:
     result=passage(library,fetch,len(lands)+1);assert result is not None;assert result[1]==tapped
     lands.append(fetch);rng.shuffle(library)
    else:lands.append(n)
   life+=2*shock
   sources=[self.cards[x]['colors'] for x in lands];ready=sources[:-1] if tapped else sources
   metrics[f't{t}_lands']=len(lands)
   metrics[f't{t}_four_lands']=len(lands)>=4
   metrics[f't{t}_jenova_mana']=bool(payments(tuple(ready),'BG',2))
   metrics[f't{t}_ouro_mana']=bool(payments(tuple(ready),'GG',2))
   anchor_in_hand=any(self.cards[x].get('anchor') for x in hand)
   metrics[f't{t}_jenova_in_hand']=anchor_in_hand
   metrics[f't{t}_jenova_hand_mana']=anchor_in_hand and bool(payments(tuple(ready),'BG',2))
   metrics[f't{t}_jenova_total_short']=anchor_in_hand and len(lands)<4
   metrics[f't{t}_jenova_tapped_short']=anchor_in_hand and len(lands)>=4 and len(ready)<4
   metrics[f't{t}_jenova_color_short']=anchor_in_hand and len(ready)>=4 and not payments(tuple(ready),'BG',2)
   casts=[]
   while True:
    opt=self.options(hand,ready,board)
    if not opt:break
    _,spell,pay,offspring=opt;hand.remove(spell);ready=[s for i,s in enumerate(ready) if i not in pay];c=self.cards[spell]
    if c.get('anchor'):
     metrics['jenova_cast']+=1;metrics['jenova_with_target']+=bool(board)
    board.append((spell,c['mv'],False))
    board += [(spell+' token',0,True)]*(c.get('tokens',0)+int(offspring))
    casts.append({'card':spell,'offspring':offspring})
   if t<=2 and casts:metrics['early_body']=1
   metrics[f't{t}_bodies_before_removal']=len(board)
   killed=None
   if remove and t in (2,3) and board:
    victim=max(range(len(board)),key=lambda i:(not board[i][2],board[i][1],board[i][0]));killed=board.pop(victim)[0]
   metrics[f't{t}_bodies_after_removal']=len(board)
   metrics[f't{t}_surviving_target']=bool(board)
   trace.append(dict(turn=t,draw=drawn,hand_before=before,land=n,fetch=fetch,tapped=tapped,shock_life=2*int(shock),casts=casts,removed=killed,board=list(board),hand_after=list(hand),lands=list(lands)))
  metrics['shock_life']=life
  return {'metrics':dict(metrics),'trace':trace}
 def quality(self,hand,deck):
  lib=list(deck)
  for n in hand:lib.remove(n)
  r=self.play(hand,lib,turns=3,draw=False,remove=False)
  nl=sum(self.cards[n]['land'] for n in hand);m=r['metrics']
  return (2<=nl<=4 and bool(m.get('early_body')),bool(m.get('early_body')),m.get('t3_bodies_before_removal',0),-abs(nl-3))
 def keep(self,seven,m,deck):
  choices=[]
  for ix in combinations(range(7),m):
   h=[n for i,n in enumerate(seven) if i not in ix];choices.append((self.quality(h,deck),ix,h))
  q,ix,h=max(choices,key=lambda x:x[0]);return q[0],ix,h

def run(config,samples,seed):
 pilot=MaterialPilot(config['cards']);rng=random.Random(seed);summary={};traces={}
 for name in config['candidates']:summary[name]={s:Counter() for s in ['play','draw']};traces[name]=[]
 for trial in range(samples):
  orders=[]
  for m in range(3):o=list(range(60));rng.shuffle(o);orders.append(o)
  for name,deck in config['candidates'].items():
   offers=[]
   for m,order in enumerate(orders):
    seven=[deck[i] for i in order[:7]];ok,ix,hand=pilot.keep(seven,m,deck);offers.append(dict(seven=seven,bottom=[seven[i] for i in ix],qualifies=ok))
    if ok or m==2:break
   library=[deck[i] for i in order[7:]]+[seven[i] for i in ix]
   for seat in ['play','draw']:
    result=pilot.play(hand,library,on_play=seat=='play',seed=seed+trial)
    c=summary[name][seat];c.update(result['metrics']);c['mulligan_ge1']+=m>=1;c['mulligan_ge2']+=m==2;c['forced5_failed']+=not ok
    c['accepted_'+str(7-m)]+=1;c['accepted_'+str(7-m)+'_early']+=result['metrics'].get('early_body',0)
    if trial<12 or result['metrics'].get('jenova_cast') and result['metrics'].get('jenova_with_target') and len(traces[name])<40:
     traces[name].append(dict(trial=trial,seat=seat,offers=offers,accepted=hand,**result))
 return dict(samples=samples,seed=seed,config_sha256=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),scope=__doc__,summary={n:{s:{'counts':dict(c),'means':{k:v/samples for k,v in c.items()}} for s,c in seats.items()} for n,seats in summary.items()},traces=traces)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('config');p.add_argument('--samples',type=int,default=100);p.add_argument('--seed',type=int,default=920);p.add_argument('--output',required=True);a=p.parse_args()
 result=run(json.load(open(a.config)),a.samples,a.seed);open(a.output,'w').write(json.dumps(result,indent=2));print(json.dumps({'status':'complete','output':a.output}))
