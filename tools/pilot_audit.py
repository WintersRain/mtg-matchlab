#!/usr/bin/env python3
"""Audit Forge AI piloting from snapshot logs: turns a player ended holding a spell it could cast.

    python3 tools/pilot_audit.py RUN_DIR [RUN_DIR ...] [--json]

A turn is idle when, at the end of that player's own turn, it holds a sorcery-speed
card (no instants or flash) whose cheapest face it can pay with its untapped lands
(colors checked), removal has an opposing creature to hit, and legend/planeswalker
copies aren't already in play; or it holds a land with no land played that turn.
Cost reductions are not modeled, so the check under-reports rather than over-reports.
Needs games run with snapshots (tools/gauntlet.py --snapshots).
"""
from pathlib import Path
import argparse
import collections
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import vet  # noqa: E402

END_PHASES = ('END_OF_TURN', 'CLEANUP')
SITUATIONAL = re.compile(r'(?:destroy|exile) all|all creatures|each creature', re.I)


def _payable(face, lands, cards):
    have = {t for c in lands if c['name'] in cards for t in cards[c['name']]['types']}

    def colors(card):
        need = card.get('produces_if', {})
        return {c for c in card['produces'] if c not in need or have & set(need[c])}
    untapped = [colors(cards[c['name']]) for c in lands if not c['tapped'] and c['name'] in cards]
    if face['mv'] is None or face['mv'] > len(untapped):
        return False
    # Greedy color assignment: scarcest-producing lands go to the pips first.
    pool = sorted(untapped, key=len)
    for color, count in sorted(face['pips'].items()):
        for _ in range(count):
            hit = next((p for p in pool if color in p), None)
            if hit is None:
                return False
            pool.remove(hit)
    return True


def _castable(card, me, them, cards):
    if 'Land' in card['types']:
        return False
    if 'Legendary' in card['types'] or 'Planeswalker' in card['types']:
        if any(c['name'] == card['name'] for c in me['zones'].get('Battlefield') or []):
            return False
    lands = [c for c in me['zones'].get('Battlefield') or [] if c.get('land')]
    opposing_creature = any(c.get('creature') for c in them['zones'].get('Battlefield') or [])
    for face in card['faces']:
        if face['mv'] is None or 'Instant' in face['types'] or re.search(r'^Flash\b', face['text'], re.M):
            continue
        # Only unconditional development and removal with a real target count. Holding a sweeper,
        # an aura, a pump spell or other situational sorcery can be correct play.
        if SITUATIONAL.search(face['text']) or 'Aura' in face['types']:
            continue
        permanent = any(t in face['types'] for t in ('Creature', 'Planeswalker', 'Artifact', 'Enchantment', 'Battle'))
        removal = vet.REMOVAL.search(face['text']) and opposing_creature
        if (permanent and not vet.REMOVAL.search(face['text'])) or removal or (permanent and opposing_creature):
            if _payable(face, lands, cards):
                return True
    return False


def _holding_up_interaction(hand, me, cards):
    lands = [c for c in me['zones'].get('Battlefield') or [] if c.get('land')]
    for c in hand:
        card = cards.get(c['name'])
        if not card:
            continue
        for face in card['faces']:
            instant_speed = 'Instant' in face['types'] or re.search(r'^Flash\b', face['text'], re.M)
            if instant_speed and face['mv'] is not None and _payable(face, lands, cards):
                return True
    return False


def idle_turns(frames, cards):
    last = {}
    for f in frames:
        # The TurnEnded frame already names the next player as active; skip it.
        if f.get('phase') in END_PHASES and f.get('turn') is not None and f.get('event') != 'GameEventTurnEnded':
            last[(f['turn'], f['active_player'])] = f
    out = []
    for (turn, active), f in sorted(last.items()):
        me = next((p for p in f['players'] if p['id'] == active), None)
        them = next((p for p in f['players'] if p['id'] != active), None)
        if me is None or them is None:  # a player already left the game
            continue
        hand = me['zones'].get('Hand') or []
        castable = sorted({c['name'] for c in hand if c['name'] in cards and _castable(cards[c['name']], me, them, cards)})
        if castable and _holding_up_interaction(hand, me, cards):
            castable = []  # untapped mana kept for an instant or flash card in hand is a real plan
        # Forge keeps a spare land once it has nothing to cast; only an early missed drop is a misplay.
        land_count = sum(1 for c in me['zones'].get('Battlefield') or [] if c.get('land'))
        missed_land = me.get('lands_played_this_turn', 1) == 0 and land_count < 5 and any(c.get('land') for c in hand)
        if castable or missed_land:
            out.append({'turn': turn, 'player': active, 'castable': castable, 'missed_land': missed_land})
    return out


def game_valid(idle, max_idle=1):
    per = collections.Counter(i['player'] for i in idle)
    return all(n <= max_idle for n in per.values())


def frames_from_run(run_dir):
    import dashboard
    text = (Path(run_dir) / 'raw.log').read_text(errors='replace')
    return [e['snapshot'] for e in dashboard.replay(text) if e['kind'] == 'snapshot']


def audit_runs(run_dirs, max_idle=1):
    frames = {d: frames_from_run(d) for d in run_dirs}
    names = {c['name'] for fs in frames.values() for f in fs for p in f['players']
             for z in ('Hand', 'Battlefield') for c in (p['zones'].get(z) or [])}
    cards = vet.load_cards(sorted(n for n in names if n and not n.endswith(' Token')), strict=False)
    for card in list(cards.values()):  # a card on an adventure or prepared shows its face name
        for face in card['faces'][1:]:
            cards.setdefault(face['name'], card)
    games = []
    for d, fs in frames.items():
        if not fs:
            games.append({'run': d, 'valid': None, 'reason': 'no snapshots recorded', 'idle': []})
            continue
        idle = idle_turns(fs, cards)
        games.append({'run': d, 'valid': game_valid(idle, max_idle), 'idle': idle})
    return games


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('runs', nargs='+')
    parser.add_argument('--max-idle', type=int, default=1, help='Idle turns allowed per player before the game is invalid')
    parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args()
    games = audit_runs(args.runs, args.max_idle)
    if args.as_json:
        print(json.dumps(games, indent=1))
        return 0
    held = collections.Counter(n for g in games for i in g['idle'] for n in i['castable'])
    for g in games:
        print(f"{'VALID  ' if g['valid'] else 'INVALID'} {g['run']}")
        for i in g['idle']:
            print(f"   turn {i['turn']:2d} seat {i['player']}: held {', '.join(i['castable']) or '-'}{' + unplayed land' if i['missed_land'] else ''}")
    print('most-held cards:', ', '.join(f'{n} x{c}' for n, c in held.most_common(10)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
