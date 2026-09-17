"""Portable bounded research; run from repository root. No engine changes."""
import json, pathlib, sys, itertools, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from analysis_tools import compare, canonical_config, can_pay
P=pathlib.Path(__file__).parent

def save(name,data): (P/name).write_text(json.dumps(data,indent=2)+'\n')
def land(name,n,model,colors,types=(),**kw): return dict(name=name,count=n,model=model,colors=list(colors),types=list(types),**kw)
basics=[land('Forest',3,'basic','G',['Forest']),land('Plains',3,'basic','W',['Plains']),land('Mountain',2,'basic','R',['Mountain'])]
lands=basics+[
land('Hushwood Verge',4,'verge','G',conditional_color='W',requires_types=['Forest','Plains']),
land('Thornspire Verge',3,'verge','R',conditional_color='G',requires_types=['Mountain','Forest']),
land('Sunbillow Verge',2,'verge','W',conditional_color='R',requires_types=['Mountain','Plains']),
land('Inspiring Vantage',2,'fast','RW'),land('Temple Garden',2,'shock','GW',['Forest','Plains']),
land('Stomping Ground',2,'shock','RG',['Mountain','Forest']),land('Sacred Foundry',1,'shock','RW',['Mountain','Plains'])]
def target(name,turn,generic,**colored):return dict(name=name,turn=turn,generic=generic,colored=colored,artifact=False)
targets=[target('T1 green',1,0,G=1),target('T1 white',1,0,W=1),target('T2 Miles',2,1,G=1),target('T2 Academic',2,0,R=1,W=1),target('T3 Lightning',3,1,R=1,W=1),target('T3 Tyvar',3,1,G=2),target('T4 Ouroboroid',4,2,G=2),target('T5 Smile',5,3,W=2)]
c=dict(deck_size=60,opening_hand=7,on_play=True,lands=lands,targets=targets)
b=dict(c,lands=[land('Forest',10,'basic','G',['Forest']),land('Plains',9,'basic','W',['Plains']),land('Mountain',5,'basic','R',['Mountain'])])
assert sum(x['count'] for x in lands)==24
save('recommendation.json',c);save('placeholder.json',b)
# Eight targets x 500 samples x two configurations = 8000 isolated probes.
r=compare(b,c,samples=500,seed=9162026);save('comparison.json',r)
print('COMPARISON',[(x['name'],round(x['probability'],3),round(y['probability'],3),round(y['zero_life_probability'],3)) for x,y in zip(r['left']['targets'],r['right']['targets'])],flush=True)
# Exhaustive multiset boards of five lands. Remove two nonbasics, search basics
# remaining in library, untap, and require each cost separately, not simultaneously.
c=canonical_config(c);ls=c['lands'];basic=[i for i,l in enumerate(ls) if l['model']=='basic'];nonbasic=set(range(len(ls)))-set(basic)
req=[target('Tyvar activation',5,3,G=2),target('Smile / Curaga',5,3,W=2),target('Lightning',3,1,R=1,W=1)]
def supports(board): return all(can_pay(ls,board,board,t) for t in req)
reports=[]
for reserve in (0,1):
 cases=passed=0;failures=[]
 for board in itertools.combinations_with_replacement(range(len(ls)),5):
  counts=collections.Counter(board)
  if any(n>ls[i]['count'] for i,n in counts.items()) or not supports(board):continue
  remaining={i:ls[i]['count']-counts[i]-reserve for i in basic}
  if min(remaining.values())<0:continue
  removals=set(itertools.combinations([i for i in board if i in nonbasic],2))
  for removed in sorted(removals):
   cases+=1;kept=list(board)
   for i in removed:kept.remove(i)
   ok=False
   for replacements in itertools.combinations_with_replacement(basic,2):
    if any(n>remaining[i] for i,n in collections.Counter(replacements).items()):continue
    if supports(kept+list(replacements)):ok=True;break
   passed+=ok
   if not ok and len(failures)<8:failures.append({'board':[ls[i]['name'] for i in board],'removed':[ls[i]['name'] for i in removed],'library_basics':{ls[i]['name']:n for i,n in remaining.items()}})
 reports.append(dict(already_drawn_off_board_each_basic=reserve,cases=cases,passed=passed,failed=cases-passed,failure_examples=failures))
save('resilience.json',dict(method='Exhaustive eligible five-land multisets within copy limits; two nonbasic hits with chosen basic replacements; after untap; costs individually supported; not probability weighted. Reserved basics unavailable to search and not on board. End-state existence, not an adversarial online policy.',requirements=req,reports=reports))
print('RESILIENCE',[(x['already_drawn_off_board_each_basic'],x['cases'],x['passed'],x['failed']) for x in reports],flush=True)
