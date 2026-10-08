"""Printing-aware deck audit and bounded, explicit artifact-resource scenarios.

Not a game simulator: no opponent, combat, response windows, random draws or AI.
Successful actions resolve in isolation. Only the listed operations are supported.
"""
import collections
import copy
import hashlib
import json
import re
from math import comb
from pathlib import Path

VERSION = 1
ROOT = Path(__file__).resolve().parent
RULES_SOURCE = 'https://magic.wizards.com/en/news/feature/reality-fracture-release-notes'
TOKEN_RULES_SOURCE = 'https://magic.wizards.com/en/news/feature/edge-of-eternities-release-notes'
SEMANTIC_KEYS = ('oracle_id', 'name', 'layout', 'cmc', 'mana_cost', 'type_line',
                 'oracle_text', 'power', 'toughness', 'card_faces')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def front(card):
    return (card.get('card_faces') or [card])[0]


def rules_hash(card):
    semantic = {k: card.get(k) for k in SEMANTIC_KEYS}
    if semantic['card_faces'] is not None:
        semantic['card_faces'] = [{k:f.get(k) for k in ('name','mana_cost','type_line','oracle_text','power','toughness')}
                                  for f in semantic['card_faces']]
    return digest(semantic)


def catalog(bundle):
    if bundle.get('schema_version') != 1 or not isinstance(bundle.get('records'), list):
        raise ValueError('Unsupported Oracle bundle schema')
    result, printings = {}, set()
    for row in bundle['records']:
        c = row['card']
        key = (c['set'].lower(), str(c['collector_number']))
        if key in printings:
            raise ValueError('Duplicate printing in Oracle bundle')
        printings.add(key)
        if not c.get('oracle_id') or not row.get('source') or not row.get('retrieved_at'):
            raise ValueError('Oracle identity/source/retrieval time required')
        name = front(c)['name']
        if name in result and rules_hash(result[name]) != rules_hash(c):
            raise ValueError('Inconsistent rules for multiple printings')
        result[name] = c
    return result


def inspect_deck(text, bundle, format_name=None):
    """Preserve printing identity/counts; never pad or cut a list to 60."""
    cards = catalog(bundle)
    by_printing = {(r['card']['set'].lower(), str(r['card']['collector_number'])): r for r in bundle['records']}
    if format_name not in (None, 'standard'):
        raise ValueError('Only explicit Standard assessment is supported; unspecified stays unspecified')
    zones, section, seen, entries = {'main': 0, 'sideboard': 0}, None, set(), []
    totals, curve, types = collections.Counter(), collections.Counter(), collections.Counter()
    main_names = collections.Counter()
    sources, missing_arena, unavailable, illegal = {}, set(), set(), set()
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if line in ('Deck', 'Sideboard'):
            if line in seen or (line == 'Sideboard' and 'Deck' not in seen) or (line == 'Deck' and seen):
                raise ValueError(f'Invalid section at line {lineno}')
            seen.add(line); section = 'main' if line == 'Deck' else 'sideboard'
            continue
        m = re.fullmatch(r'([1-9][0-9]*) (.+?) \(([A-Za-z0-9]+)\) ([A-Za-z0-9]+)', line)
        if not m or section is None:
            raise ValueError(f'Expected exact Arena printing at line {lineno}')
        count, name, setcode, number = int(m[1]), m[2], m[3].lower(), m[4]
        if count > 250 or sum(zones.values()) + count > 250:
            raise ValueError('Audit bounded to 250 cards')
        row = by_printing.get((setcode, number))
        if not row:
            raise ValueError(f'Missing Oracle printing: {setcode}/{number}')
        c = row['card']; f = front(c)
        if name not in (c['name'], f['name']):
            raise ValueError(f'Printing/name identity mismatch at line {lineno}')
        zones[section] += count; totals[c['oracle_id']] += count
        typ = f['type_line'].split('—')[0].strip().split()
        if section == 'main':
            main_names[f['name']] += count
            for t in ('Land', 'Creature', 'Artifact', 'Enchantment', 'Instant', 'Sorcery'):
                types[t.lower()] += count * (t in typ)
            if 'Land' not in typ:
                curve[str(int(c['cmc']))] += count
        if 'arena' not in c.get('games', []): unavailable.add(name)
        if c.get('arena_id') is None: missing_arena.add(name)
        if format_name and c.get('legalities', {}).get(format_name) != 'legal': illegal.add(name)
        sources[c['oracle_id']] = {'source': row['source'], 'retrieved_at': row['retrieved_at'], 'rules_sha256': rules_hash(c)}
        entries.append({'zone': section, 'count': count, 'input_name': name, 'name': c['name'],
                        'oracle_id': c['oracle_id'], 'set': setcode, 'collector_number': number})
    if not zones['main']: raise ValueError('Empty main deck')
    copy_errors = sorted(front(c)['name'] for c in cards.values()
                         if totals[c['oracle_id']] > 4 and 'Basic Land' not in front(c)['type_line'])
    artifact_casts = {n:v for n,v in main_names.items() if 'Artifact' in front(cards[n])['type_line'].split('—')[0]}
    prepared = {n:v for n,v in main_names.items() if cards[n].get('layout')=='prepare'}
    artifact_count = sum(artifact_casts.values()); robots=main_names['Ravenous Robots']; n=zones['main']
    def choose(n,k):return comb(n,k) if 0<=k<=n else 0
    # At least one Robot plus another artifact spell, including a second Robot.
    pair=[]
    for seen_count in (7,9,10):
        if seen_count>n:continue
        denominator=comb(n,seen_count)
        numerator=denominator-choose(n-robots,seen_count)-robots*choose(n-artifact_count,seen_count-1)
        pair.append({'cards_seen':seen_count,'numerator':numerator,'denominator':denominator,
                     'probability':numerator/denominator})
    return {'schema_version': VERSION, 'kind': 'printing_and_rules_audit',
            'deck_sha256': hashlib.sha256(text.encode()).hexdigest(), 'oracle_bundle_sha256': digest(bundle),
            'counts': zones, 'types': dict(types), 'curve': dict(sorted(curve.items(), key=lambda x:int(x[0]))),
            'format': format_name, 'format_confirmed_by_user': False,
            'format_check': None if not format_name else {'as_of': sorted(r['retrieved_at'] for r in bundle['records'])[-1],
                'minimum_main_met': zones['main'] >= 60, 'sideboard_limit_met': zones['sideboard'] <= 15,
                'copy_limit_errors': copy_errors, 'not_legal_or_unknown': sorted(illegal)},
            'arena': {'not_listed_for_platform': sorted(unavailable), 'missing_printing_ids': sorted(missing_arena),
                      'note': 'games=arena is card-platform evidence; missing arena_id is not proof of unavailability. Import was not executed.'},
            'entries': entries, 'sources': sources,
            'artifact_package': {'artifact_spell_copies':artifact_count,'artifact_spell_cards':artifact_casts,
                'prepared_front_copies':sum(prepared.values()),'prepared_front_cards':prepared,
                'robots_and_followup_artifact_draw_availability':pair,
                'draw_limits':'Uniform no-mulligan sample, unordered availability only; no casting, sequence, Arena smoothing or survival claim.'},
            'limits': ['No format was inferred from the export; --format standard is an assessment, not user confirmation.',
                       'Legality reflects the dated Oracle bundle, not an independent banned-list refresh.',
                       'Preparation front faces count once; shared spell-face names are not front-name aliases.',
                       'Counts and casting costs do not establish playability or matchup strength.']}


def fields(obj, allowed, required=()):
    if not isinstance(obj, dict) or set(obj) - set(allowed) or set(required) - set(obj):
        raise ValueError('Unsupported or missing fields')


class Board:
    """Declared battlefield checkpoint + explicit legal payment sequence, not a pilot."""
    CASTABLE = {'Tenured Tethermage', 'Puppet Crafting', 'Hungering Puppetbeast',
                'Woodwork Prodigy', 'Ravenous Robots', 'Solemn Simulacrum',
                'Aerid Konstrari', 'Edge Rover', 'Heartwood Crafter'}
    TOKENS = {'Heartwood': ('Artifact', '', 0), 'Robot': ('Artifact Creature', '', 1),
              'Lander': ('Artifact', '', 0)}

    def __init__(self, cards, setup):
        fields(setup, ('permanents','mana','hand','library_basics'), ())
        self.cards = cards
        baseline = catalog(json.loads((ROOT/'examples/artifact-oracle.json').read_text()))
        self.fingerprints = {n:rules_hash(c) for n,c in baseline.items()}
        self.permanents = {}; self.mana = []; self.hand = list(setup.get('hand', []))
        self.library_basics = dict(setup.get('library_basics', {}))
        if any(k not in {'Forest','Mountain'} or type(v) is not int or v < 0 for k,v in self.library_basics.items()):
            raise ValueError('Library contains unsupported basic inventory')
        self.graveyard = []; self.turn = 1; self.serial = 0; self.draw_triggers = 0
        self.opponent_landers = 0; self.events = []
        if len(setup.get('permanents',[])) > 50 or len(self.hand) > 100: raise ValueError('Setup too large')
        for p in setup.get('permanents', []):
            fields(p, ('id','name','new','tapped','prepared','pending_etb'), ('id','name'))
            self.add(p['id'], p['name'], new=p.get('new',False), tapped=p.get('tapped',False))
            for k in ('prepared','pending_etb'):
                if k in p:
                    if type(p[k]) is not bool:raise ValueError('State flags must be booleans')
                    self.permanents[p['id']][k] = p[k]
        for color in setup.get('mana', []):
            if color not in 'WUBRGC' or len(color)!=1:raise ValueError('Invalid initial mana')
            self.mana.append({'color':color,'restriction':'none'})

    def checked(self, name):
        if name not in self.cards or self.fingerprints.get(name) != rules_hash(self.cards[name]):
            raise ValueError('Unsupported or changed rules fingerprint: '+name)
        return front(self.cards[name])

    def add(self, id, name, new=True, tapped=False):
        if not isinstance(id,str) or not id or id in self.permanents:raise ValueError('Duplicate/invalid permanent id')
        if type(new) is not bool or type(tapped) is not bool:raise ValueError('State flags must be booleans')
        if name in self.TOKENS:typ,cost,power=self.TOKENS[name]
        else:
            f=self.checked(name);typ=f['type_line'];cost=f.get('mana_cost','');power=int(f.get('power',0))
        self.permanents[id]={'name':name,'types':typ,'new':new,'tapped':tapped,'counters':0,
            'base_power':power,'prepared':name=='Heartwood Crafter',
            'pending_etb':name=='Tenured Tethermage','abilities':[], 'attached_to':None}

    def token(self,name,tapped=False):
        self.serial+=1
        while 'token'+str(self.serial) in self.permanents:self.serial+=1
        id='token'+str(self.serial);self.add(id,name,tapped=tapped);return id

    def get(self,id,name=None):
        if id not in self.permanents:raise ValueError('Absent permanent: '+str(id))
        p=self.permanents[id]
        if name and p['name']!=name:raise ValueError('Wrong ability source')
        return p

    def own_tap(self,p):
        if p['tapped']:raise ValueError('Permanent is tapped')
        if 'Creature' in p['types'] and p['new'] and 'haste' not in p['abilities']:
            raise ValueError('Creature has summoning sickness')
        p['tapped']=True

    def pay(self,cost,origin):
        parts=re.findall(r'\{([^}]+)\}',cost)
        if ''.join('{'+x+'}' for x in parts)!=cost:raise ValueError('Unsupported mana cost')
        generic=sum(int(x) for x in parts if x.isdigit());specific=[x for x in parts if not x.isdigit()]
        if any(x not in ['W','U','B','R','G','C','R/G'] for x in specific):raise ValueError('Unsupported mana symbol')
        usable=[i for i,m in enumerate(self.mana) if origin!='hand' or m['restriction']!='not_hand']
        def match(todo,available):
            if not todo:return available[:generic] if len(available)>=generic else None
            for i in available:
                if self.mana[i]['color'] in todo[0].split('/'):
                    rest=match(todo[1:],[j for j in available if j!=i])
                    if rest is not None:return [i]+rest
            return None
        chosen=match(specific,usable)
        if chosen is None:raise ValueError('Insufficient eligible mana for '+cost+' from '+origin)
        self.mana=[m for i,m in enumerate(self.mana) if i not in chosen]

    def remove(self,id,die=True):
        p=self.get(id);del self.permanents[id]
        if p['name'] not in self.TOKENS:self.graveyard.append(p['name'])
        for aid,attached in list(self.permanents.items()):
            if attached['attached_to']==id:self.remove(aid,False)
        if die:
            if p['name']=='Edge Rover':self.token('Lander');self.opponent_landers+=1
            if p['name']=='Aerid Konstrari':self.token('Heartwood')
            if p['name']=='Solemn Simulacrum':self.draw_triggers+=1

    def snapshot(self):
        return copy.deepcopy({k:getattr(self,k) for k in ['permanents','mana','hand','library_basics','graveyard',
            'turn','serial','draw_triggers','opponent_landers','events']})

    def step(self,action):
        before=self.snapshot()
        try:self._step(action)
        except (ValueError,KeyError,TypeError) as exc:
            for k,v in before.items():setattr(self,k,v)
            raise ValueError(str(exc)) from exc

    def _step(self,a):
        op=a.get('op')
        specs={'tap_mana':('id','color'), 'cast':('name','id','target','land','basic'),
               'tether_etb':('id','land'),'tether_pump':('id','artifacts'),
               'puppet_sac':('id','sacrifice','mode'),'prepare_cast':('id',),
               'lander_fetch':('id','basic'),'die':('id',),'next_turn':(),
               'robots_haste':('id',),'crafting_return':(), 'aerid_pump':('id',)}
        if op not in specs:raise ValueError('Unsupported operation: '+str(op))
        fields(a,('op',)+specs[op],('op',))
        if op=='next_turn':
            self.turn+=1;self.mana=[]
            for p in self.permanents.values():
                p['tapped']=False;p['new']=False;p['abilities']=[];p['pending_etb']=False
                if p['name']=='Woodwork Prodigy':p['prepared']=True
            self.events.append('Untap/upkeep only; no draw or land drop was modeled');return
        if op=='crafting_return':
            if 'Puppet Crafting' not in self.graveyard:raise ValueError('No Crafting in graveyard')
            self.pay('{4}{G}','activation');self.graveyard.remove('Puppet Crafting');self.hand.append('Puppet Crafting');return
        if op=='cast':
            name=a['name']
            if name not in self.CASTABLE:raise ValueError('Unsupported spell effects: '+name)
            for option,owner in [('target','Puppet Crafting'),('land','Tenured Tethermage'),('basic','Solemn Simulacrum')]:
                if option in a and name!=owner:raise ValueError('Unsupported cast option for '+name)
            if name not in self.hand:raise ValueError('Spell absent from declared hand')
            f=self.checked(name)
            if 'Legendary' in f['type_line'] and any(p['name']==name for p in self.permanents.values()):
                raise ValueError('Legend-rule choice unsupported; cannot resolve a second legendary copy')
            self.pay(f['mana_cost'],'hand');self.hand.remove(name)
            if 'Artifact' in f['type_line']:
                for _ in range(sum(p['name']=='Ravenous Robots' for p in self.permanents.values())):self.token('Robot')
            if name=='Puppet Crafting':
                target=self.get(a['target'])
                if 'Artifact' not in target['types'] and not ('Enchantment' in target['types'] and 'Aura' not in target['types']):
                    raise ValueError('Illegal Puppet Crafting target')
                self.add(a['id'],name);self.permanents[a['id']]['attached_to']=a['target']
                target['types']+=' Creature Construct';target['base_power']=5
            else:
                self.add(a['id'],name)
                if name in ('Hungering Puppetbeast','Aerid Konstrari'):self.token('Heartwood')
                if name=='Tenured Tethermage':self._step({'op':'tether_etb','id':a['id'],**({'land':a['land']} if a.get('land') else {})})
                if name=='Solemn Simulacrum' and a.get('basic'):self.fetch(a['basic'])
            return
        p=self.get(a['id'])
        if op=='tap_mana':
            name=p['name'];color=a['color'];allowed='';restriction='none'
            if name in ('Heartwood','Stomping Ground','Restless Ridgeline'):allowed='RG'
            elif name=='Forest':allowed='G'
            elif name=='Mountain':allowed='R'
            elif name=='Thornspire Verge':
                allowed='R'
                if any(re.search(r'\b(Mountain|Forest)\b',q['types']) for q in self.permanents.values()):allowed+='G'
            elif name=='Heartwood Crafter':allowed='C';restriction='not_hand'
            else:raise ValueError('Unsupported mana ability')
            if color not in allowed or len(color)!=1:raise ValueError('Unavailable mana color')
            self.own_tap(p);self.mana.append({'color':color,'restriction':restriction})
        elif op=='tether_etb':
            self.get(a['id'],'Tenured Tethermage')
            if not p['pending_etb']:raise ValueError('No pending Tethermage ETB')
            p['pending_etb']=False
            if a.get('land'):
                if 'Land' not in self.get(a['land'])['types']:raise ValueError('Must sacrifice a land')
                self.remove(a['land']);self.token('Heartwood',True);self.token('Heartwood',True)
        elif op=='tether_pump':
            self.get(a['id'],'Tenured Tethermage');ids=a['artifacts']
            if len(ids)!=2 or len(set(ids))!=2:raise ValueError('Need two distinct artifacts')
            for id in ids:
                q=self.get(id)
                if 'Artifact' not in q['types'] or q['tapped']:raise ValueError('Need untapped artifacts')
            for id in ids:self.permanents[id]['tapped']=True
            p['counters']+=2
        elif op=='puppet_sac':
            self.get(a['id'],'Hungering Puppetbeast');q=self.get(a['sacrifice'])
            if a['sacrifice']==a['id'] or 'Artifact' not in q['types']:raise ValueError('Must sacrifice another artifact')
            if a['mode'] not in ('haste','hexproof','trample'):raise ValueError('Unknown Puppetbeast mode')
            self.pay('{1}','activation');self.remove(a['sacrifice']);p['counters']+=1;p['abilities'].append(a['mode'])
        elif op=='prepare_cast':
            if p['name'] not in ('Heartwood Crafter','Woodwork Prodigy') or not p['prepared']:raise ValueError('Not prepared')
            self.pay('{2}{R/G}','exile');p['prepared']=False;self.token('Heartwood')
            self.events.append('Soul Tether cast from exile; not an artifact cast')
        elif op=='lander_fetch':
            self.get(a['id'],'Lander');self.own_tap(p);self.pay('{2}','activation')
            self.remove(a['id']);self.fetch(a['basic'])
        elif op=='die':
            if 'Creature' not in p['types']:raise ValueError('die requires a creature; arbitrary removal is unsupported')
            self.remove(a['id'])
        elif op=='robots_haste':
            self.get(a['id'],'Ravenous Robots');self.pay('{R}','activation');self.own_tap(p)
            for q in self.permanents.values():
                if q['name'] in self.TOKENS and 'Creature' in q['types']:q['abilities'].append('haste')
        elif op=='aerid_pump':
            self.get(a['id'],'Aerid Konstrari');self.pay('{6}','activation');self.token('Heartwood')
            self.events.append('Aerid gains +'+str(sum('Artifact' in q['types'] for q in self.permanents.values()))+'/+0 until end of turn')

    def fetch(self,basic):
        if basic not in ('Forest','Mountain') or self.library_basics.get(basic,0)<1:raise ValueError('No eligible library basic')
        self.library_basics[basic]-=1;self.serial+=1
        while 'token'+str(self.serial) in self.permanents:self.serial+=1
        self.add('token'+str(self.serial),basic,tapped=True)
        self.events.append('Basic fetched tapped; no draw order/shuffle simulation')


def run_scenario(scenario,cards):
    fields(scenario,('name','setup','actions'),('name','setup','actions'))
    if len(scenario['actions'])>100:raise ValueError('Scenario too long')
    board=Board(cards,scenario['setup']);trace=[]
    for i,a in enumerate(scenario['actions']):
        try:board.step(a)
        except ValueError as exc:
            return {'name':scenario['name'],'status':'rejected','failed_action':i,'error':str(exc),'trace':trace,'final':board.snapshot()}
        trace.append({'action':a,'after':board.snapshot()})
    return {'name':scenario['name'],'status':'resolved','trace':trace,'final':board.snapshot()}


def add_command(sub):
    p=sub.add_parser('artifact-audit',help='Exact-printing deck audit and bounded artifact resource scenarios')
    p.add_argument('deck');p.add_argument('--oracle',required=True)
    p.add_argument('--format',choices=['standard']);p.add_argument('--scenarios')


def dispatch(args):
    def read_json(path):
        raw=Path(path).read_bytes()
        if len(raw)>4*1024*1024:raise ValueError('JSON input exceeds 4 MiB limit')
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('Duplicate JSON key: '+key)
                result[key]=value
            return result
        return json.loads(raw,object_pairs_hook=unique)
    bundle=read_json(args.oracle);raw=Path(args.deck).read_bytes()
    if len(raw)>65536:raise ValueError('Deck input exceeds 64 KiB limit')
    text=raw.decode('utf-8')
    result=inspect_deck(text,bundle,args.format)
    if args.scenarios:
        scenarios=read_json(args.scenarios)
        if not isinstance(scenarios,list) or len(scenarios)>100:raise ValueError('Expected <=100 scenarios')
        result['scenarios_sha256']=digest(scenarios)
        result['scenarios']=[run_scenario(s,catalog(bundle)) for s in scenarios]
        result['limits'] += ['Scenarios are declared checkpoints, not draw/cast probabilities or complete games.',
            'No opponents, combat, stack responses, replacement effects, legend rule, or arbitrary card abilities.',
            'Initial mana and permanents are premises, not proof they were reachable; costs and subsequent state are checked.',
            'Unknown operations, spells and changed supported Oracle fingerprints fail closed. Failed actions roll back.',
            'Draw triggers are recorded, not drawn. next_turn untaps/prepares and clears mana; no draw or land drop.']
        result['mechanics_sources']=[RULES_SOURCE,TOKEN_RULES_SOURCE]
    return result
