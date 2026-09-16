"""Bounded, offline probability and isolated-target mana tools (stdlib only)."""
from collections import Counter
from fractions import Fraction
import hashlib
import json
from math import comb, sqrt
from pathlib import Path
import random
import platform

COLORS = set('WUBRGC')
TYPES = {'Plains', 'Island', 'Swamp', 'Mountain', 'Forest'}
MODELS = {'basic', 'untapped', 'tapped', 'shock', 'fast', 'slow', 'verge', 'artifact_castle', 'starting_town'}
ASSUMPTIONS = [
    'Isolated target availability assumed externally; targets do not occupy or alter sampled slots.',
    'No mulligans, prior spells, opponents, ramp, filtering, abilities, or extra land drops.',
    'Perfect-lookahead optimal land sequencing per target: optimistic feasibility, not a pilot policy.',
    'One land per turn; all previous lands untap; cast in target-turn main phase after draw and land drop.',
    'Each land supplies at most one mana; each colored/colorless pip needs an independent payment.',
    'Shock lands may enter tapped for zero life or untapped for two; sufficient life to pay is assumed.',
    'Starting Town enters tapped with three or more other lands; C/generic free, colored activation one life.',
    'Zero-life successes have a genuinely feasible zero-life sequence, not an average-life proxy.',
    'Each target is assessed separately, not a full curve, full gameplay, or win-rate prediction.',
]
CATALOG = {'schema_version': 1, 'guide': 'docs/TOOLS.md', 'tools': [
    {'command': 'draw', 'kind': 'exact_math', 'use_for': 'At least k sources in n draws without replacement',
     'requires': ['Python 3 stdlib'], 'limits': 'No sequencing, tapped lands, mulligans, or multi-color joint events'},
    {'command': 'mana', 'kind': 'simplified_mana_analysis', 'use_for': 'Isolated target mana feasibility; optional unpaired comparison',
     'requires': ['Python 3 stdlib', 'JSON config'], 'limits': 'Monte Carlo with perfect-lookahead sequencing, not gameplay; 16 land names, 8 targets, shared 2000000-transition budget',
     'example': 'python3 matchlab.py mana examples/mana-grixis-baseline.json --compare examples/mana-grixis-proposal.json --samples 50 --seed 42'},
    {'command': 'decks', 'kind': 'opponent_catalog', 'use_for': 'Discover four curated roles and 37 immutable archived opponent selectors; --json available',
     'requires': ['Python 3 stdlib'], 'limits': 'Hashes and counts, not legality or Forge support proof'},
    {'command': 'audit', 'kind': 'forge_input_audit', 'use_for': 'Verify pinned curated or selected/all benchmark inputs and Forge script presence',
     'requires': ['Pinned Forge source', 'Git'], 'limits': 'Not a legality or rules-fidelity proof'},
    {'command': 'run', 'kind': 'full_game', 'use_for': 'One preboard Forge Default-AI game',
     'requires': ['Pinned privacy-patched Forge build', 'Java 17', 'Linux/WSL'], 'limits': 'AI/engine outcomes, not human win rates'},
]}


def integer(value, name, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'{name} must be an integer in {lo}..{hi}')


def hypergeometric(deck_size, sources, draws, at_least=1):
    """Exact rational P(X >= at_least) under uniform sampling without replacement."""
    integer(deck_size, 'deck_size', 1, 10000)
    integer(sources, 'sources', 0, deck_size)
    integer(draws, 'draws', 0, deck_size)
    integer(at_least, 'at_least', 0, deck_size)
    lo, hi = max(at_least, draws - (deck_size - sources)), min(sources, draws)
    p = Fraction(sum(comb(sources, k) * comb(deck_size - sources, draws - k)
                     for k in range(lo, hi + 1)), comb(deck_size, draws))
    return dict(tool='draw', method='exact hypergeometric tail', deck_size=deck_size,
                sources=sources, draws=draws, at_least=at_least,
                numerator=p.numerator, denominator=p.denominator, probability=float(p),
                assumptions=['Uniform draws without replacement; no mulligans or sequencing.'])


def fields(obj, required, optional=()):
    if not isinstance(obj, dict) or set(obj) - set(required) - set(optional) or set(required) - set(obj):
        raise ValueError('Missing or unknown fields in config object')


def strings(value, allowed, name, nonempty=False):
    if (not isinstance(value, list) or (nonempty and not value)
            or any(not isinstance(x, str) or x not in allowed for x in value)
            or len(value) != len(set(value))):
        raise ValueError(f'Invalid {name}')


def named(items, label, maximum):
    if not isinstance(items, list) or not 1 <= len(items) <= maximum:
        raise ValueError(f'{label} needs 1..{maximum} entries')
    names = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not 1 <= len(item['name']) <= 80:
            raise ValueError(f'Invalid {label} name')
        names.append(item['name'])
    if len(set(names)) != len(names):
        raise ValueError(f'Duplicate {label} name')


def validate_config(c):
    fields(c, ('deck_size', 'opening_hand', 'on_play', 'lands', 'targets'))
    integer(c['deck_size'], 'deck_size', 1, 100)
    integer(c['opening_hand'], 'opening_hand', 0, min(7, c['deck_size']))
    if type(c['on_play']) is not bool:
        raise ValueError('on_play must be boolean')
    named(c['lands'], 'lands', 16)
    for l in c['lands']:
        fields(l, ('name', 'count', 'model', 'colors'), ('types', 'conditional_color', 'requires_types'))
        integer(l['count'], 'land count', 1, c['deck_size'])
        if not isinstance(l['model'], str) or l['model'] not in MODELS:
            raise ValueError('Unknown land model')
        strings(l['colors'], COLORS, 'colors', True)
        strings(l.get('types', []), TYPES, 'types')
        if l['model'] == 'verge':
            if (len(l['colors']) != 1 or not isinstance(l.get('conditional_color'), str)
                    or l['conditional_color'] not in set('WUBRG')):
                raise ValueError('Verge needs one base color and a conditional_color')
            strings(l.get('requires_types'), TYPES, 'requires_types', True)
        elif 'conditional_color' in l or 'requires_types' in l:
            raise ValueError('Conditional fields only supported for verge')
    if sum(l['count'] for l in c['lands']) > c['deck_size']:
        raise ValueError('Land counts exceed deck size')
    named(c['targets'], 'targets', 8)
    for t in c['targets']:
        fields(t, ('name', 'turn', 'colored', 'generic', 'artifact'))
        integer(t['turn'], 'turn', 1, 6)
        integer(t['generic'], 'generic', 0, 12)
        if type(t['artifact']) is not bool or not isinstance(t['colored'], dict):
            raise ValueError('Invalid target artifact/colored fields')
        for color, count in t['colored'].items():
            if color not in COLORS:
                raise ValueError('Unsupported pip: use W U B R G C (no hybrid/Phyrexian/X)')
            integer(count, 'pip count', 1, 6)
        if t['generic'] + sum(t['colored'].values()) > 12:
            raise ValueError('Target cost exceeds 12')
        if c['opening_hand'] + t['turn'] - int(c['on_play']) > c['deck_size']:
            raise ValueError('Not enough cards for requested draw horizon')
    return c


def canonical_config(c):
    validate_config(c)
    c = json.loads(json.dumps(c))
    c['lands'].sort(key=lambda l: l['name'])
    c['targets'].sort(key=lambda t: t['name'])
    for l in c['lands']:
        l['colors'].sort()
        l['types'] = sorted(l.get('types', []))
        if 'requires_types' in l:
            l['requires_types'].sort()
    return c


def read_config(path):
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ValueError('Config exceeds 64 KiB')
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError('Duplicate JSON key')
            result[k] = v
        return result
    return canonical_config(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique))


def payment_life(lands, board, available, target):
    """Minimum activation life via weighted pip matching; None if infeasible."""
    types = {ty for i in board for ty in lands[i].get('types', [])}
    options = []
    for i in available:
        l = lands[i]
        colors = set(l['colors'])
        if l['model'] == 'starting_town':
            colors.add('C')
        if l['model'] == 'artifact_castle':
            colors = {'C'} | (colors if target['artifact'] else set())
        if l['model'] == 'verge' and types.intersection(l['requires_types']):
            colors.add(l['conditional_color'])
        options.append({color: int(l['model'] == 'starting_town' and color != 'C')
                        for color in colors})
    pips = [color for color, n in sorted(target['colored'].items()) for _ in range(n)]
    if len(pips) + target['generic'] > len(options):
        return None
    # Assign constrained pips first. Bitmask states bound matching by 2**6.
    pips.sort(key=lambda p: sum(p in colors for colors in options))
    masks = {0: 0}
    for pip in pips:
        following = {}
        for mask, life in masks.items():
            for i, costs in enumerate(options):
                if not mask & (1 << i) and pip in costs:
                    new_mask = mask | (1 << i)
                    cost = life + costs[pip]
                    following[new_mask] = min(following.get(new_mask, cost), cost)
        masks = following
        if not masks:
            return None
    # All supported sources pay generic for free, including Town's C ability.
    return min(masks.values())


def can_pay(lands, board, available, target):
    """Whether independent sources cover all colored and generic pips."""
    return payment_life(lands, board, available, target) is not None


def minimum_life(c, order, target, budget=None):
    """Minimum entry plus activation life over land sequences; None if infeasible.

    order is a full sampled deck: indices into c['lands'], or -1 for inert slots.
    Caller supplies a validated configuration and a valid physical draw order.
    """
    lands = c['lands']
    budget = [2000000] if budget is None else budget
    states = {()}
    best = None
    for turn in range(1, target['turn'] + 1):
        seen = Counter(order[:c['opening_hand'] + turn - int(c['on_play'])])
        following = set()
        for board in sorted(states):
            used = Counter(board)
            choices = [-1] + [i for i in range(len(lands)) if seen[i] > used[i]]
            for i in choices:
                budget[0] -= 1
                if budget[0] < 0:
                    raise ValueError('Search state budget exceeded; reduce samples/turns/land models')
                new_board = tuple(sorted(board + ((i,) if i >= 0 else ())))
                if turn != target['turn']:
                    following.add(new_board)
                    continue
                available = list(board)  # Earlier lands untap; activation life still applies.
                modes = [(available, 0)]
                if i >= 0:
                    model = lands[i]['model']
                    if model == 'shock':
                        modes.append((available + [i], 2))
                    elif not (model == 'tapped' or (model in {'fast', 'starting_town'} and len(board) >= 3)
                              or (model == 'slow' and len(board) < 2)):
                        modes.append((available + [i], 0))
                for sources, life in modes:
                    if best is not None and life >= best:
                        continue
                    activation = payment_life(lands, new_board, sources, target)
                    if activation is not None and (best is None or life + activation < best):
                        best = life + activation
                        if best == 0:
                            return 0
        states = following
    return best


def analyze(config, samples=500, seed=42, max_states=2000000):
    integer(samples, 'samples', 1, 5000)
    integer(seed, 'seed', 0, 2**63 - 1)
    integer(max_states, 'max_states', 1, 2000000)
    c = canonical_config(config)
    digest = hashlib.sha256(json.dumps(c, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    deck = [i for i, l in enumerate(c['lands']) for _ in range(l['count'])]
    deck += [-1] * (c['deck_size'] - len(deck))
    rng = random.Random(seed)
    budget = [max_states]
    results = [dict(name=t['name'], turn=t['turn'], successes=0, zero_life_successes=0,
                    minimum_life_sum=0) for t in c['targets']]
    for _ in range(samples):
        order = deck.copy()
        rng.shuffle(order)
        for t, r in zip(c['targets'], results):
            life = minimum_life(c, order, t, budget)
            if life is not None:
                r['successes'] += 1
                r['zero_life_successes'] += life == 0
                r['minimum_life_sum'] += life
    for r in results:
        p = r['successes'] / samples
        r.update(probability=p, zero_life_probability=r['zero_life_successes'] / samples,
                 standard_error=sqrt(p * (1 - p) / samples),
                 mean_minimum_life_given_success=(r.pop('minimum_life_sum') / r['successes'] if r['successes'] else None))
    return dict(tool='mana', model_version=1, method='Monte Carlo isolated-target feasibility',
                seed=seed, samples=samples, config_sha256=digest, config=c, python_version=platform.python_version(),
                assumptions=ASSUMPTIONS, targets=results, states_visited=max_states - budget[0],
                limits=dict(max_samples=5000, max_turn=6, max_land_models=16, max_targets=8,
                            state_budget=max_states),
                uncertainty='Binomial plug-in standard errors; zero error at endpoints is not certainty.',
                reproducibility='Canonical names/order; Python random.Random shuffle; retain Python version for cross-version replay.')


def compare(left, right, samples=500, seed=42):
    left, right = canonical_config(left), canonical_config(right)
    if any(left[k] != right[k] for k in ('deck_size', 'opening_hand', 'on_play', 'targets')):
        raise ValueError('Comparison requires identical deck size, draw settings, and targets')
    integer(seed, 'comparison seed', 0, 2**63 - 2)
    a, b = analyze(left, samples, seed), analyze(right, samples, seed + 1)
    deltas = [dict(name=x['name'], probability_delta=y['probability'] - x['probability'],
                   standard_error=sqrt(x['standard_error']**2 + y['standard_error']**2),
                   zero_life_probability_delta=y['zero_life_probability'] - x['zero_life_probability'])
              for x, y in zip(a['targets'], b['targets'])]
    return dict(tool='mana', paired=False, comparison='Unpaired independent PRNG streams; right minus left. No physical-slot pairing claim.',
                left=a, right=b, deltas=deltas)


def add_commands(sub):
    catalog = sub.add_parser('tools', help='Choose a tool: human or JSON catalog')
    catalog.add_argument('--json', action='store_true', dest='as_json')
    draw = sub.add_parser('draw', help='Exact hypergeometric draw/source probability (offline)')
    for flag in ('deck-size', 'sources', 'draws'):
        draw.add_argument('--' + flag, required=True, type=int)
    draw.add_argument('--at-least', type=int, default=1)
    mana = sub.add_parser('mana', help='Simplified isolated-target mana feasibility/compare (offline)')
    mana.add_argument('config', help='Portable JSON config; see docs/TOOLS.md')
    mana.add_argument('--compare', help='Second JSON config, unpaired right-minus-left comparison')
    mana.add_argument('--samples', type=int, default=500, help='1..5000 (default: 500); search budget also applies')
    mana.add_argument('--seed', type=int, default=42)


def dispatch(args):
    if args.action == 'tools':
        if args.as_json:
            return CATALOG
        return '\n'.join([f"{t['command']}: {t['kind']} — {t['use_for']}. Limits: {t['limits']}" for t in CATALOG['tools']] + ['Guide: docs/TOOLS.md'])
    if args.action == 'draw':
        return hypergeometric(args.deck_size, args.sources, args.draws, args.at_least)
    c = read_config(args.config)
    return compare(c, read_config(args.compare), args.samples, args.seed) if args.compare else analyze(c, args.samples, args.seed)
