"""Review an MTG Arena match from Player.log: per-turn timeline, measured stats, ledger entry.

Read-only. Works from the client's own log (detailed logging enabled) and the installed
Arena card database for names and mana values. It reports what happened; it does not
judge play or claim hidden information (opponent hands are counts only).

    python3 matchlab.py review PLAYER_LOG --player NAME --card-db RAW_CARDDATABASE.mtga \\
        [--match latest|INDEX|MATCH_ID] [--out DIR] [--ledger LEDGER.jsonl]
"""
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3

# --- payload extraction (Arena logs mix text prefixes with single- and multi-line JSON) ---

def payloads(text):
    decoder, pos = json.JSONDecoder(), 0
    while pos < len(text):
        starts = [i for i in (text.find('{', pos), text.find('[', pos)) if i >= 0]
        if not starts:
            break
        pos = min(starts)
        try:
            value, pos = decoder.raw_decode(text, pos)
            yield value
        except (ValueError, RecursionError):
            pos += 1


def expanded(obj, depth=0):
    """Arena nests JSON documents inside string fields; decode them recursively."""
    if depth > 80:
        return None
    if isinstance(obj, str) and obj.lstrip().startswith(('{', '[')):
        try:
            return expanded(json.loads(obj), depth + 1)
        except (ValueError, RecursionError):
            return obj
    if isinstance(obj, dict):
        return {k: expanded(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expanded(v, depth + 1) for v in obj]
    return obj


def nodes(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from nodes(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from nodes(v)


def mana_value(mana_text):
    """Arena OldSchoolManaText ('o1oGoG', 'o2o(B/G)', 'oXoRoR') -> mana value; X counts as 0."""
    total = 0
    for token in re.findall(r'o(\([^)]*\)|\d+|[A-Z])', mana_text or ''):
        total += int(token) if token.isdigit() else (0 if token == 'X' else 1)
    return total


class CardDB:
    """Read-only Arena Raw_CardDatabase lookups."""
    def __init__(self, path):
        self.db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        self._cache = {}

    def _one(self, sql, arg):
        key = (sql, arg)
        if key not in self._cache:
            row = self.db.execute(sql, (arg,)).fetchone()
            self._cache[key] = row[0] if row else None
        return self._cache[key]

    def name(self, grp):
        return self._one('select l.Loc from Cards c join Localizations_enUS l on l.LocId=c.TitleId where c.GrpId=? limit 1', grp) or f'#{grp}'

    def mana_value(self, grp):
        return mana_value(self._one('select OldSchoolManaText from Cards where GrpId=?', grp))

    def ability_text(self, ability_id):
        return self._one('select l.Loc from Abilities a join Localizations_enUS l on l.LocId=a.TextId where a.Id=? limit 1', ability_id)


# --- match selection ---

def split_matches(text):
    """Completed matches in log order: [{'match_id', 'text'}]. Unfinished matches are skipped."""
    out, current, lines = [], None, []
    for line in text.split('\n'):
        m = re.search(r'Connecting to matchId ([\w-]+)', line)
        if m:
            current, lines = m.group(1), []
        if current:
            lines.append(line)
            if 'MatchGameRoomStateType_MatchCompleted' in line:
                out.append({'match_id': current, 'text': '\n'.join(lines) + '\n'})
                current, lines = None, []
    return out


def seats(text):
    for p in payloads(text):
        for n in nodes(expanded(p)):
            if isinstance(n.get('reservedPlayers'), list):
                return {rp['playerName']: rp['systemSeatId'] for rp in n['reservedPlayers']}
    return {}


# --- replay ---

def _details(annotation):
    return {d['key']: (d.get('valueString') or d.get('valueInt32') or [None])[0] for d in annotation.get('details', [])}


def review(text, cards, player):
    seat_map = seats(text)
    me = next((s for n, s in seat_map.items() if n.startswith(player)), None)
    if me is None:
        raise ValueError(f'{player!r} is not a player in this match (players: {sorted(seat_map)})')
    opponent = next((n for n, s in seat_map.items() if s != me), None)
    match_id = (re.search(r'Connecting to matchId ([\w-]+)', text) or [None, None])[1]
    objects, zones, known, life = {}, {}, {}, {}
    games, submissions = [], []
    game = None
    turn = 0
    offers = Counter()
    opp_cards = set()

    def label(seat):
        return 'me' if seat == me else ('opp' if seat else '?')

    def name_of(iid):
        if iid in (1, 2):
            return label(iid)
        o = objects.get(iid)
        if o and o.get('type') == 'GameObjectType_Ability':
            # Ability grpIds are ability ids that can collide with card ids: name by the source card.
            return 'ability of ' + (known.get(o.get('parentId')) or cards.name(o.get('objectSourceGrpId', 0)))
        if o:
            return cards.name(o['grpId'])
        return known.get(iid, f'object {iid}')

    def zone_type(zid):
        return (zones.get(zid) or {}).get('type', '?').replace('ZoneType_', '')

    def zone_objects(ztype, seat):
        res = []
        for z in zones.values():
            if z.get('type') != 'ZoneType_' + ztype:
                continue
            for i in z.get('objectInstanceIds', []):
                o = objects.get(i)
                if o and (o.get('controllerSeatId') if ztype == 'Battlefield' else z.get('ownerSeatId')) == seat:
                    res.append(o)
        return res

    def new_game(number):
        g = {'game': number, 'turns': {}, 'result': None, 'on_play': None, 'casts': {}, 'land_untapped_on_play': {},
             'seen_in_hand': {}, 'last_damage_seat': {}}
        games.append(g)
        return g

    def turn_record(t, active):
        return game['turns'].setdefault(t, {'active': label(active) if active else None, 'state': None, 'events': []})

    def snapshot():
        def board(seat):
            bf = zone_objects('Battlefield', seat)
            lands = [o for o in bf if 'CardType_Land' in o.get('cardTypes', []) and 'CardType_Creature' not in o.get('cardTypes', [])]
            return {'untapped_lands': sum(not o.get('isTapped') for o in lands), 'lands': len(lands),
                    'permanents': [_describe(o, cards) for o in bf if o not in lands]}
        hand = zone_objects('Hand', me)
        for o in hand:
            game['seen_in_hand'][cards.name(o['grpId'])] = 'CardType_Land' not in o.get('cardTypes', [])
        opp_hand = sum(len(z.get('objectInstanceIds', [])) for z in zones.values()
                       if z.get('type') == 'ZoneType_Hand' and z.get('ownerSeatId') != me)
        return {'life': {'me': life.get(me), 'opp': life.get(3 - me)},
                'my_hand': sorted(cards.name(o['grpId']) for o in hand),
                'my_hand_cards': [(cards.name(o['grpId']), cards.mana_value(o['grpId']), 'CardType_Land' in o.get('cardTypes', [])) for o in hand],
                'my_board': board(me), 'opp_board': board(3 - me), 'opp_hand_size': opp_hand}

    for raw in payloads(text):
        for n in nodes(expanded(raw)):
            kind = n.get('type')
            if kind == 'GREMessageType_MulliganReq':
                offers[game['game'] + 1 if game and game['result'] else (game['game'] if game else 1)] += 1
            for key in ('deckMessage', 'submitDeckResp'):
                v = n.get(key)
                if isinstance(v, dict):
                    deck = v.get('deck', v)
                    if deck.get('deckCards'):
                        sub = {'main': dict(Counter(cards.name(g) for g in deck['deckCards'])),
                               'side': dict(Counter(cards.name(g) for g in deck.get('sideboardCards', [])))}
                        if not submissions or submissions[-1] != sub:
                            submissions.append(sub)
            g = n.get('gameStateMessage')
            if not isinstance(g, dict):
                continue
            gi = g.get('gameInfo', {})
            number = gi.get('gameNumber') or (game['game'] if game else 1)
            if game is None or number != game['game']:
                game, turn = new_game(number), 0
            for o in g.get('gameObjects', []):
                objects[o['instanceId']] = {**objects.get(o['instanceId'], {}), **o}
                if o.get('type') != 'GameObjectType_Ability':
                    known[o['instanceId']] = cards.name(o['grpId'])
                    if o.get('ownerSeatId') not in (None, me) and o.get('type') != 'GameObjectType_Token':
                        opp_cards.add(cards.name(o['grpId']))
            for z in g.get('zones', []):
                zones[z['zoneId']] = z
            # diffDeletedInstanceIds are not dropped: annotations in the same message still refer to them,
            # and current state is read through zones, which only list live objects.
            for p in g.get('players', []):
                if 'lifeTotal' in p:
                    life[p['systemSeatNumber']] = p['lifeTotal']
            ti = g.get('turnInfo', {})
            if ti.get('turnNumber') and ti['turnNumber'] != turn:
                turn = ti['turnNumber']
                if turn == 1 and game['on_play'] is None:
                    game['on_play'] = ti.get('activePlayer') == me
            rec = turn_record(turn, ti.get('activePlayer') or (game['turns'].get(turn) or {}).get('active') and None)
            if rec['active'] is None and ti.get('activePlayer'):
                rec['active'] = label(ti['activePlayer'])
            events = rec['events']
            for a in g.get('annotations', []):
                t, d = a.get('type', [None])[0], _details(a)
                aff, src = a.get('affectedIds', []), a.get('affectorId')
                if t == 'AnnotationType_ObjectIdChanged':
                    # Arena re-ids cards as they change zones; carry identity, owner and history forward.
                    old, new = d.get('orig_id'), d.get('new_id')
                    known[new] = known.get(old, known.get(new))
                    objects[new] = {**objects.get(old, {}), **objects.get(new, {})}
                    for history in (game['casts'], game['last_damage_seat']):
                        if old in history:
                            history[new] = history[old]
                elif t == 'AnnotationType_ZoneTransfer':
                    for i in aff:
                        o = objects.get(i, {})
                        e = {'kind': 'zone', 'seat': label(o.get('ownerSeatId')), 'category': d.get('category'),
                             'card': name_of(i), 'src': zone_type(d.get('zone_src')), 'dst': zone_type(d.get('zone_dest')), 'iid': i}
                        if src and src not in (1, 2):
                            e['by'] = name_of(src)
                            e['by_seat'] = label((objects.get(src) or {}).get('controllerSeatId') or (objects.get(src) or {}).get('ownerSeatId'))
                        if e['category'] == 'Draw' and e['seat'] == 'me' and o.get('type') != 'GameObjectType_Ability':
                            game['seen_in_hand'][e['card']] = 'CardType_Land' not in o.get('cardTypes', [])
                        if e['category'] == 'CastSpell':
                            e['undone'] = True          # until any later zone event shows the spell went on
                            game['casts'][i] = e
                        elif i in game['casts']:
                            game['casts'][i]['undone'] = False
                        if e['category'] == 'PlayLand' and e['seat'] == 'me':
                            game['land_untapped_on_play'].setdefault(turn, []).append(not o.get('isTapped'))
                        if e["category"] in ("SBA_Damage", "SBA_ZeroLoyalty") and i in game["last_damage_seat"]:
                            e['by_seat'] = game['last_damage_seat'][i]
                        events.append(e)
                elif t == 'AnnotationType_PlayerSubmittedTargets':
                    events.append({'kind': 'target', 'source': name_of(src), 'targets': [name_of(i) for i in aff]})
                elif t == 'AnnotationType_UserActionTaken' and d.get('actionType') == 'ActionType_Activate' and d.get('abilityGrpId'):
                    text_ = getattr(cards, 'ability_text', lambda _: None)(d['abilityGrpId'])
                    events.append({'kind': 'activate', 'card': name_of(aff[0]) if aff else None, 'ability': text_})
                elif t == 'AnnotationType_DamageDealt':
                    source_obj = objects.get(src) or {}
                    for i in aff:
                        e = {'kind': 'damage', 'source': name_of(src), 'source_seat': label(source_obj.get('controllerSeatId')),
                             'target': name_of(i), 'amount': d.get('damage')}
                        if i in (1, 2):
                            e['target_seat'] = label(i)
                        else:
                            game['last_damage_seat'][i] = e['source_seat']
                        events.append(e)
                elif t == 'AnnotationType_ModifiedLife':
                    for i in aff:
                        events.append({'kind': 'life', 'seat': label(i), 'delta': d.get('life'), 'total': life.get(i)})
                elif t == 'AnnotationType_ManaPaid':
                    payer = (objects.get(src) or {}).get('controllerSeatId')
                    events.append({'kind': 'mana', 'seat': label(payer) if payer else None})
                elif t == 'AnnotationType_TokenCreated':
                    events.extend({'kind': 'token', 'card': name_of(i)} for i in aff)
                elif t == 'AnnotationType_CounterAdded':
                    events.extend({'kind': 'counter', 'card': name_of(i), 'amount': d.get('transaction_amount'),
                                   'counter': d.get('counter_type')} for i in aff)
            for o in g.get('gameObjects', []):
                if o.get('attackState') == 'AttackState_Attacking' and not any(e.get('iid') == o['instanceId'] and e['kind'] == 'attack' for e in events):
                    events.append({'kind': 'attack', 'seat': label(o.get('controllerSeatId')), 'card': _describe(o, cards), 'iid': o['instanceId']})
                if o.get('blockState') == 'BlockState_Blocking' and not any(e.get('iid') == o['instanceId'] and e['kind'] == 'block' for e in events):
                    events.append({'kind': 'block', 'seat': label(o.get('controllerSeatId')), 'card': _describe(o, cards), 'iid': o['instanceId'],
                                   'blocking': [name_of(i) for i in o.get('blockInfo', {}).get('attackerIds', [])]})
            if ti.get('phase') == 'Phase_Main1' and rec['state'] is None:
                rec['state'] = snapshot()
            if gi.get('stage') == 'GameStage_GameOver' and game['result'] is None:
                res = [x for x in gi.get('results', []) if x.get('scope') == 'MatchScope_Game']
                if res:
                    game['result'] = 'win' if res[-1].get('winningTeamId') == me else 'loss'
                    game['reason'] = res[-1].get('reason')
                    game['final'] = snapshot()

    for g in games:
        g['mulligans'] = max(offers.get(g['game'], 1) - 1, 0)
        g['stats'] = _stats(g)
        for k in ('casts', 'land_untapped_on_play', 'seen_in_hand', 'last_damage_seat'):
            g.pop(k)
    return {'match_id': match_id, 'me': me, 'opponent': opponent, 'games': games,
            'deck': submissions[0] if submissions else None, 'submissions': submissions, 'opponent_cards': sorted(opp_cards)}


def _describe(o, cards):
    s = cards.name(o['grpId'])
    if 'power' in o and 'CardType_Creature' in o.get('cardTypes', []):
        s += f" {o['power'].get('value', 0)}/{o.get('toughness', {}).get('value', 0)}"
    if o.get('loyalty'):
        s += f" [loyalty {o['loyalty'].get('value')}]"
    if o.get('isTapped'):
        s += ' (tapped)'
    return s


def _stats(g):
    mana, held, damage = {}, Counter(), Counter()
    first_interaction = None
    cast_names = set()
    for t, rec in sorted(g['turns'].items()):
        events = rec['events']
        my_casts = {e['card'] for e in events if e['kind'] == 'zone' and e['category'] == 'CastSpell' and e['seat'] == 'me' and not e.get('undone')}
        cast_names |= my_casts | {e['card'] for e in events if e['kind'] == 'zone' and e['category'] == 'PlayLand' and e['seat'] == 'me'}
        for e in events:
            if e['kind'] == 'damage' and e.get('target_seat') == 'me':
                damage[e['source']] += e['amount'] or 0
            if (first_interaction is None and e['kind'] == 'zone' and e['seat'] == 'opp' and e['src'] == 'Battlefield'
                    and e['dst'] != 'Battlefield' and e.get('by_seat') == 'me'):
                first_interaction = t
        if rec['active'] == 'me' and rec['state']:
            available = rec['state']['my_board']['untapped_lands'] + sum(g['land_untapped_on_play'].get(t, []))
            spent = sum(1 for e in events if e['kind'] == 'mana' and e['seat'] == 'me')
            mana[t] = {'available': available, 'spent': spent}
            for card, mv, is_land in rec['state']['my_hand_cards']:
                if not is_land and mv <= available and card not in my_casts:
                    held[card] += 1
    never_cast = sorted(card for card, nonland in g['seen_in_hand'].items() if nonland and card not in cast_names)
    final = g.get('final') or {}
    return {'mana': mana, 'held_castable': dict(held), 'damage_taken_by_source': dict(damage),
            'first_interaction_turn': first_interaction, 'never_cast': never_cast,
            'opp_permanents_at_end': (final.get('opp_board') or {}).get('permanents', [])}


def ledger_entry(rv):
    main = (rv.get('deck') or {}).get('main', {})
    deck_text = '\n'.join(f'{q} {n}' for n, q in sorted(main.items()))
    return {'schema': 1, 'reviewed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'match_id': rv['match_id'], 'opponent': rv['opponent'], 'my_seat': rv['me'],
            'deck_sha256': hashlib.sha256(deck_text.encode()).hexdigest(), 'deck_main': main,
            'sideboard_changes': [{'in': {k: v for k, v in Counter(s['main']).items() if v > Counter(rv['submissions'][0]['main'])[k]},
                                   'out': {k: v for k, v in Counter(rv['submissions'][0]['main']).items() if v > Counter(s['main'])[k]}}
                                  for s in rv['submissions'][1:]],
            'games': [{'game': g['game'], 'result': g['result'], 'reason': g.get('reason'), 'on_play': g['on_play'],
                       'mulligans': g['mulligans'], 'turns': max(g['turns'] or [0])} for g in rv['games']],
            'opponent_cards': rv['opponent_cards']}


# --- rendering and CLI ---

def render(rv):
    out = [f"Match {rv['match_id']} vs {rv['opponent']} (you are seat {rv['me']})"]
    for g in rv['games']:
        out.append(f"\n##### GAME {g['game']}: {g['result'] or 'unfinished'} ({g.get('reason')}) — "
                   f"{'on the play' if g['on_play'] else 'on the draw'}, mulligans {g['mulligans']}")
        for t, rec in sorted(g['turns'].items()):
            s = rec['state']
            out.append(f"\n--- turn {t} ({rec['active']})" + (f" life me {s['life']['me']} / opp {s['life']['opp']}" if s else ''))
            if s:
                out.append(f"  my hand: {', '.join(s['my_hand']) or '-'}")
                for who in ('my', 'opp'):
                    b = s[f'{who}_board']
                    out.append(f"  {who} board: {'; '.join(b['permanents']) or '-'} | lands {b['lands']} ({b['untapped_lands']} untapped)")
                out.append(f"  opp hand: {s['opp_hand_size']} cards")
            for e in rec['events']:
                k = e['kind']
                if k == 'zone' and not (e['category'] == 'Draw' and e['seat'] == 'opp'):
                    out.append(f"    {e['seat']:3s} {e['category']}: {e['card']}" + (' [UNDONE]' if e.get('undone') else '')
                               + (f"  (by {e['by']})" if e.get('by') and e['category'] not in ('CastSpell', 'Resolve', 'PlayLand') else ''))
                elif k == 'target':
                    out.append(f"      targets of {e['source']}: {', '.join(e['targets'])}")
                elif k == 'activate':
                    out.append(f"    activate {e['card']}: {(e['ability'] or '')[:100]}")
                elif k == 'damage':
                    out.append(f"      damage {e['source']} -> {e['target']}: {e['amount']}")
                elif k == 'life':
                    out.append(f"      life {e['seat']} {e['delta']:+} -> {e['total']}")
                elif k in ('attack', 'block'):
                    out.append(f"    {e['seat']:3s} {k.upper()}S with {e['card']}" + (f" -> {', '.join(e['blocking'])}" if e.get('blocking') else ''))
                elif k == 'token':
                    out.append(f"      token: {e['card']}")
        st = g['stats']
        out.append(f"\n  STATS game {g['game']}")
        out.append('  mana spent/available on your turns (lands only): ' + ', '.join(f"t{t} {m['spent']}/{m['available']}" for t, m in st['mana'].items()))
        out.append(f"  castable-but-held (turns, total mana only, colors not checked): {st['held_castable'] or '-'}")
        out.append(f"  first removal of an opposing permanent: turn {st['first_interaction_turn']}")
        out.append(f"  damage taken by source: {st['damage_taken_by_source'] or '-'}")
        out.append(f"  drawn but never cast: {', '.join(st['never_cast']) or '-'}")
        out.append(f"  opponent permanents at end: {'; '.join(st['opp_permanents_at_end']) or '-'}")
    return '\n'.join(out) + '\n'


def add_command(sub):
    p = sub.add_parser('review', help='Review an Arena match from Player.log (timeline, stats, ledger)')
    p.add_argument('log', type=Path)
    p.add_argument('--player', required=True, help='Your Arena player name (prefix match)')
    p.add_argument('--card-db', required=True, type=Path, help='Arena Raw_CardDatabase_*.mtga')
    p.add_argument('--match', default='latest', help='latest, a 0-based index, or a match id')
    p.add_argument('--out', type=Path, help='Directory for timeline.txt and review.json')
    p.add_argument('--ledger', type=Path, help='Append one JSON line per reviewed match')


def dispatch(args):
    matches = split_matches(args.log.read_text(encoding='utf-8', errors='replace'))
    if not matches:
        raise ValueError('No completed match in this log')
    if args.match == 'latest':
        chosen = matches[-1]
    elif args.match.isdigit():
        chosen = matches[int(args.match)]
    else:
        chosen = next(m for m in matches if m['match_id'] == args.match)
    rv = review(chosen['text'], CardDB(args.card_db), args.player)
    text = render(rv)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / f"timeline-{rv['match_id']}.txt").write_text(text)
        (args.out / f"review-{rv['match_id']}.json").write_text(json.dumps(rv, indent=1))
    if args.ledger:
        entry = ledger_entry(rv)
        existing = args.ledger.read_text().splitlines() if args.ledger.exists() else []
        if not any(json.loads(l).get('match_id') == entry['match_id'] for l in existing if l.strip()):
            with args.ledger.open('a') as f:
                f.write(json.dumps(entry) + '\n')
    return text
