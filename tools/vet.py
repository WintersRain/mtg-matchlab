#!/usr/bin/env python3
"""Vet an Arena decklist against docs/DECKBUILDING_GUIDE.md before anyone plays it.

    python3 tools/vet.py LIST.arena.txt [--forge --opponents DIR [--games 20] [--workers 10]]

Static checks read card text from the pinned Forge card scripts (offline, seconds).
--forge then plays real Forge AI games against every opponent list in DIR and fails
the deck if any matchup is a blowout. Exit status is 0 only for PASS or WARN.
"""
from pathlib import Path
import argparse
import json
import math
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COLORS = 'WUBRG'
BASIC_TYPES = {'Plains': 'W', 'Island': 'U', 'Swamp': 'B', 'Mountain': 'R', 'Forest': 'G'}

REMOVAL = re.compile(
    r'destroy target|destroy up to|destroy the chosen|exile target (?:creature|nonland|permanent|artifact|enchantment|planeswalker)'
    r'|target creature(?: an opponent controls)? gets -\d|creatures your opponents control get -\d'
    r'|deals \d+ damage to (?:any target|target creature)|fights? (?:target|up to)|counter target'
    r'|each opponent sacrifices', re.I)
CARD_ADVANTAGE = re.compile(
    r'(?<!then )draws? (?:a|one|two|three|\w+) cards?(?!, then discard)|you draw a card|draw cards equal'
    r'|from your graveyard to your hand|from among (?:them|the milled cards) (?:in)?to your hand'
    r'|from among them onto the battlefield|onto the battlefield under your control'
    r'|search your library for a basic land card, put (?:that card|it) onto the battlefield'
    r'|create (?:a|an|two|three|\w+) [^.]{0,40}creature tokens?|destroy up to (?:two|three)'
    r'|enters prepared', re.I)
SELF_SAC_REANIMATE = re.compile(r'sacrifice this creature: return target creature card', re.I)
ETB_REMOVAL = re.compile(r'when [^.]* enters[^.]*(?:destroy|exile) target', re.I)
SWEEPER = re.compile(r'destroy all creatures|all creatures get -(\d+)/-\d+|each creature gets -(\d+)/-\d+'
                     r'|deals (\d+) damage to each creature', re.I)


# --- card scripts ---

def _cost(text):
    """Forge ManaCost -> (mana value, colored pips). Hybrid pips add mana value but no single-color demand."""
    mv, pips = 0, {}
    if not text or text == 'no cost':
        return None, {}
    for token in text.split():
        if token.isdigit():
            mv += int(token)
        elif token in COLORS:
            mv += 1
            pips[token] = pips.get(token, 0) + 1
        elif token == 'X':
            continue
        elif token.startswith('2/'):
            mv += 2
        else:
            mv += 1  # hybrid, phyrexian, colorless {C}, snow
    return mv, pips


def _face(block):
    fields = {}
    for line in block.splitlines():
        key, _, value = line.partition(':')
        if key in ('Name', 'ManaCost', 'Types', 'PT', 'Oracle') and key not in fields:
            fields[key] = value.strip()
    mv, pips = _cost(fields.get('ManaCost'))
    power = toughness = None
    if re.fullmatch(r'\d+/\d+', fields.get('PT', '')):
        power, toughness = map(int, fields['PT'].split('/'))
    return {'name': fields.get('Name'), 'mv': mv, 'pips': pips, 'types': fields.get('Types', '').split(),
            'power': power, 'toughness': toughness, 'text': fields.get('Oracle', '').replace('\\n', '\n')}


def parse_script(text):
    faces = [_face(b) for b in re.split(r'^ALTERNATE\s*$', text, flags=re.M)]
    main = dict(faces[0])
    costs = [f['mv'] for f in faces if f['mv'] is not None]
    main['mv'] = faces[0]['mv'] or 0
    main['min_cost'] = min(costs) if costs else 0
    main['faces'] = faces
    main['text'] = '\n'.join(f['text'] for f in faces)
    if 'Land' in main['types']:
        produced = {BASIC_TYPES[t] for t in main['types'] if t in BASIC_TYPES}
        conditional = {}
        for line in main['text'].split('\n'):
            if 'Add' not in line:
                continue
            if 'Spend this mana only' in line:
                continue  # restricted mana (Cavern of Souls style) can't cast just anything
            ability, _, condition = line.partition('Activate only')
            colors = set(re.findall(r'\{([WUBRG])\}', ability))
            if 'any color' in ability:
                colors |= set(COLORS)
            if 'if you control' in condition:
                for color in colors - produced:
                    conditional[color] = re.findall(r'Plains|Island|Swamp|Mountain|Forest', condition)
            produced |= colors
        main['produces'] = produced
        main['produces_if'] = conditional  # color -> land types you must control for it
        main['enters_tapped'] = any('enters tapped' in s and not re.search(r'unless|if you don.t|you may', s, re.I)
                                    for s in re.split(r'(?<=\.)\s|\n', main['text']))
    return main


def load_cards(names, strict=True):
    """Read only the scripts these names need: guess the Forge filename, verify Name, fall back to a full scan."""
    folders = [ROOT / 'forge-resources/cardsfolder', ROOT / 'vendor/forge/forge-gui/res/cardsfolder']
    found, missing = {}, []
    for name in names:
        stem = re.sub(r'[^a-z0-9]+', '_', name.lower().replace("'", '')).strip('_')
        for folder in folders:
            for path in list(folder.glob(f'**/{stem}.txt')) + list(folder.glob(f'**/{stem}_*.txt')):
                text = path.read_text(encoding='utf-8-sig')
                if re.search(rf'^Name:{re.escape(name)}\s*$', text, re.M):
                    found[name] = parse_script(text)
                    break
            if name in found:
                break
        else:
            missing.append(name)
    if missing:
        sys.path.insert(0, str(ROOT))
        import matchlab
        for folder in folders:
            index = matchlab.card_index(folder)
            for name in list(missing):
                if name in index:
                    found[name] = parse_script(Path(index[name]['path']).read_text(encoding='utf-8-sig'))
                    missing.remove(name)
    if missing and strict:
        raise ValueError('No Forge script (engine cannot play these): ' + ', '.join(missing))
    return found


# --- checks ---

def _hyper_at_least_one(pool, deck_size, seen):
    return 1 - math.comb(deck_size - pool, seen) / math.comb(deck_size, seen)


def _row(check, status, value, detail):
    return {'check': check, 'status': status, 'value': value, 'detail': detail}


def _grade(value, fail, warn, low_is_bad=True):
    if low_is_bad:
        return 'FAIL' if value < fail else 'WARN' if value < warn else 'PASS'
    return 'FAIL' if value > fail else 'WARN' if value > warn else 'PASS'


def is_card_advantage(card):
    text = card['text']
    if 'Planeswalker' in card['types'] or ETB_REMOVAL.search(text):
        return True
    if any('Adventure' in f['types'] for f in card['faces'][1:]):
        return True
    return bool(CARD_ADVANTAGE.search(SELF_SAC_REANIMATE.sub('', text)))


def is_cheap_removal(card):
    return any(f['mv'] is not None and f['mv'] <= 3 and REMOVAL.search(f['text']) for f in card['faces'])


def vet(deck, cards):
    main = {n: q for n, q in deck['main'].items() if q}
    size = sum(main.values())
    lands = {n: q for n, q in main.items() if 'Land' in cards[n]['types']}
    spells = {n: q for n, q in main.items() if n not in lands}
    creatures = {n: q for n, q in spells.items() if 'Creature' in cards[n]['types']}
    land_total = sum(lands.values())
    rows = []

    rows.append(_row('land count', 'FAIL' if not 21 <= land_total <= 28 else 'WARN' if not 22 <= land_total <= 26 else 'PASS',
                     land_total, f'{land_total} lands in {size} (guide: about 40%, 24-25 for midrange)'))

    demand = {}
    for n in spells:
        for f in cards[n]['faces']:
            if f['mv'] is None:
                continue
            for color, count in f['pips'].items():
                early = (f['mv'] <= 3) or (f['mv'] <= 4 and count >= 2)
                level = 'early' if early else 'late'
                if demand.get(color) != 'early':
                    demand[color] = level
    worst, notes = 'PASS', []
    for color, level in sorted(demand.items()):
        sources = sum(q for n, q in lands.items() if color in cards[n]['produces'])
        need, floor = (14, 13) if level == 'early' else (10, 9)
        status = 'FAIL' if sources < floor else 'WARN' if sources < need else 'PASS'
        worst = max(worst, status, key=['PASS', 'WARN', 'FAIL'].index)
        notes.append(f'{color}: {sources} sources, {level} demand needs {need}')
    rows.append(_row('colored sources', worst, None, '; '.join(notes)))

    # Basics alone must cast every card (land destruction, Demolition Field), with a spare.
    need = {}
    for n in spells:
        for f in cards[n]['faces']:
            for color, count in f['pips'].items():
                need[color] = max(need.get(color, 0), count)
    basics = {}
    for n, q in lands.items():
        if 'Basic' in cards[n]['types']:
            for color in cards[n]['produces']:
                basics[color] = basics.get(color, 0) + q
    short = [f'{c}: {basics.get(c, 0)} of {k}' for c, k in sorted(need.items()) if basics.get(c, 0) < k]
    exact = [c for c, k in need.items() if basics.get(c, 0) == k]
    rows.append(_row('basic lands', 'FAIL' if short else 'WARN' if exact else 'PASS', sum(basics.values()),
                     ('basics cannot cast: ' + ', '.join(short)) if short else
                     ('basics cover every card' + (f' with no spare in {"".join(sorted(exact))}' if exact else ' with a spare'))))

    tapped = sum(q for n, q in lands.items() if cards[n]['enters_tapped'])
    rows.append(_row('tapped lands', _grade(tapped, 12, 8, low_is_bad=False), tapped, f'{tapped} always-tapped lands (guide: about 8 max for midrange)'))

    early = sum(q for n, q in spells.items() if cards[n]['min_cost'] <= 2)
    rows.append(_row('early plays', _grade(early, 6, 8), early,
                     f'cards castable for 2 or less; P(one by turn 2 on the play) {100 * _hyper_at_least_one(early, size, 8):.0f}%'))

    cheap = sum(q for n, q in spells.items() if is_cheap_removal(cards[n]))
    rows.append(_row('cheap interaction', _grade(cheap, 4, 6), cheap,
                     f'removal costing 3 or less; P(one by turn 3 on the play) {100 * _hyper_at_least_one(cheap, size, 9):.0f}%'))

    harm = []
    for n in spells:
        m = SWEEPER.search(cards[n]['text'])
        if not m:
            continue
        threshold = next((int(g) for g in m.groups() if g), None)
        dying = sum(q for c, q in creatures.items()
                    if threshold is None or (cards[c]['toughness'] is not None and cards[c]['toughness'] <= threshold))
        if dying >= 6:
            harm.append((dying, f'{n} kills {dying} of your own creatures'))
    harm_status = 'FAIL' if any(d >= 16 for d, _ in harm) else 'WARN' if harm else 'PASS'
    rows.append(_row('self-harm', harm_status, len(harm), '; '.join(h for _, h in harm) or 'no sweeper hits your own board'))

    ca = {n: q for n, q in spells.items() if is_card_advantage(cards[n])}
    rows.append(_row('card advantage', _grade(sum(ca.values()), 10, 14), sum(ca.values()),
                     'cards worth more than one card: ' + (', '.join(f'{q} {n}' for n, q in ca.items()) or 'none')))

    weak = {n: q for n, q in creatures.items()
            if cards[n]['mv'] <= 3 and (cards[n]['power'] or 0) + (cards[n]['toughness'] or 0) <= 4
            and n not in ca and not is_cheap_removal(cards[n])}
    rows.append(_row('low-impact cards', _grade(sum(weak.values()), 8, 4, low_is_bad=False), sum(weak.values()),
                     'small bodies that do nothing alone: ' + (', '.join(f'{q} {n}' for n, q in weak.items()) or 'none')))

    statuses = [r['status'] for r in rows]
    verdict = 'FAIL' if 'FAIL' in statuses else 'WARN' if 'WARN' in statuses else 'PASS'
    return {'verdict': verdict, 'checks': rows}


def forge_check(per_opponent, fail_below=0.25, warn_below=0.35):
    rates = {k: v['wins'] / v['games'] for k, v in per_opponent.items() if v['games']}
    bad = sorted((r, k) for k, r in rates.items() if r < fail_below)
    shaky = sorted((r, k) for k, r in rates.items() if fail_below <= r < warn_below)
    status = 'FAIL' if bad else 'WARN' if shaky else 'PASS'
    detail = ', '.join(f'{k} {100 * r:.0f}%' for r, k in bad + shaky) or 'no matchup below 35%'
    mean = sum(rates.values()) / len(rates) if rates else 0
    return _row('forge matchups', status, round(mean, 3), f'mean {100 * mean:.0f}%; {detail}')


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('deck', type=Path)
    parser.add_argument('--forge', action='store_true', help='Also play Forge AI games against --opponents')
    parser.add_argument('--opponents', type=Path)
    parser.add_argument('--games', type=int, default=20)
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--seed', type=int, default=700000)
    parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    import matchlab
    deck = matchlab.parse_arena(args.deck.read_text())
    cards = load_cards(set(deck['main']) | set(deck['sideboard']))
    report = vet(deck, cards)
    if args.forge:
        if not args.opponents:
            parser.error('--forge needs --opponents DIR')
        out = args.deck.with_suffix('.vet-forge.json')
        subprocess.run([sys.executable, str(ROOT / 'tools/gauntlet.py'), '--deck', str(args.deck), '--opponents', str(args.opponents),
                        '--games', str(args.games), '--chunk', str(min(args.games, 10)), '--workers', str(args.workers),
                        '--seed', str(args.seed), '--out', str(out)], check=True, stdout=subprocess.DEVNULL)
        result = json.loads(out.read_text())
        row = forge_check(result['per_opponent'])
        losses = [g for games in result['games'].values() for g in games if g['status'] == 'completed' and g['winner'] != 'seat-a']
        row['games_file'] = str(out)
        row['sample_loss_log'] = losses[0]['run_directory'] + '/raw.log' if losses else None
        report['checks'].append(row)
        if row['status'] == 'FAIL' or (row['status'] == 'WARN' and report['verdict'] == 'PASS'):
            report['verdict'] = row['status']
    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        for r in report['checks']:
            print(f"{r['status']:4s}  {r['check']:18s} {r['detail']}")
            if r.get('sample_loss_log'):
                print(f"      sample loss: python3 tools/gamelog.py {r['sample_loss_log']}")
        print(f"VERDICT: {report['verdict']}")
    return 1 if report['verdict'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
