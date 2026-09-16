"""Offline analysis contracts; no Forge installation or network needed."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

SPEC = importlib.util.find_spec('analysis_tools')
if SPEC:
    import analysis_tools as a
ROOT = Path(__file__).resolve().parents[1]


def land(name, model='basic', colors=None, **kw):
    return dict(name=name, count=1, model=model, colors=colors or ['U'], **kw)


def config(lands, turn=1, colored=None, generic=0, artifact=False):
    return dict(deck_size=20, opening_hand=7, on_play=True, lands=lands,
                targets=[dict(name='target', turn=turn, colored=colored or {'U': 1},
                              generic=generic, artifact=artifact)])


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(SPEC, 'offline analysis implementation missing')

    def life(self, c, order):
        a.validate_config(c)
        return a.minimum_life(c, order, c['targets'][0])

    def test_hypergeometric_exact(self):
        r = a.hypergeometric(10, 4, 3, 2)
        self.assertEqual((r['numerator'], r['denominator']), (1, 3))
        self.assertAlmostEqual(r['probability'], 1 / 3)
        self.assertEqual(a.hypergeometric(60, 0, 7, 1)['numerator'], 0)
        self.assertEqual(a.hypergeometric(60, 60, 7, 7)['numerator'], 1)
        self.assertEqual(a.hypergeometric(60, 4, 0, 0)['numerator'], 1)
        for args in [(0, 0, 0, 0), (60, 61, 7, 1), (60, 4, 61, 1), (60, 4, 7, -1), (True, 1, 1, 1)]:
            with self.assertRaises(ValueError):
                a.hypergeometric(*args)

    def test_each_land_pays_only_one_colored_pip(self):
        c = config([land('dual', colors=['U', 'B'])], colored={'U': 1, 'B': 1})
        self.assertIsNone(self.life(c, [0] + [-1] * 19))
        c = config([land('dual', colors=['U', 'B']), land('blue')], turn=2, colored={'U': 1, 'B': 1})
        self.assertEqual(self.life(c, [0, 1] + [-1] * 18), 0)

    def test_shock_actual_zero_life_alternative(self):
        c = config([land('shock', 'shock')])
        self.assertEqual(self.life(c, [0] + [-1] * 19), 2)
        c['targets'][0]['turn'] = 2
        self.assertEqual(self.life(c, [0] + [-1] * 19), 0)
        c['lands'].append(land('basic'))
        c['targets'][0]['turn'] = 1
        self.assertEqual(self.life(c, [0, 1] + [-1] * 18), 0)

    def test_tapped_fast_slow_timing(self):
        self.assertIsNone(self.life(config([land('tap', 'tapped')]), [0] + [-1] * 19))
        self.assertEqual(self.life(config([land('fast', 'fast')]), [0] + [-1] * 19), 0)
        self.assertIsNone(self.life(config([land('slow', 'slow')]), [0] + [-1] * 19))
        for model, expected in [('fast', None), ('slow', 0)]:
            c = config([land('a'), land('b'), land('c'), land('last', model)], turn=4, generic=3)
            self.assertEqual(self.life(c, [0, 1, 2] + [-1] * 6 + [3] + [-1] * 10), expected)

    def test_verge_checks_subtypes_not_mana_colors(self):
        v = land('verge', 'verge', ['U'], conditional_color='B', requires_types=['Island', 'Swamp'])
        c = config([v, land('blue')], turn=2, colored={'B': 1})
        self.assertIsNone(self.life(c, [0, 1] + [-1] * 18))
        c['lands'][1]['types'] = ['Island']
        self.assertEqual(self.life(c, [0, 1] + [-1] * 18), 0)

    def test_artifact_castle_restriction_and_colorless(self):
        c = config([land('castle', 'artifact_castle', ['U', 'B'])])
        self.assertIsNone(self.life(c, [0] + [-1] * 19))
        c['targets'][0]['artifact'] = True
        self.assertEqual(self.life(c, [0] + [-1] * 19), 0)
        c['targets'][0].update(artifact=False, colored={'C': 1})
        self.assertEqual(self.life(c, [0] + [-1] * 19), 0)
        c['targets'][0].update(colored={}, generic=1)
        self.assertEqual(self.life(c, [0] + [-1] * 19), 0)

    def test_starting_town_payment_costs(self):
        c = config([land('Starting Town', 'starting_town', list('WUBRG'))])
        order = [0] + [-1] * 19
        self.assertEqual(self.life(c, order), 1)
        c['targets'][0].update(artifact=True)
        self.assertEqual(self.life(c, order), 1)
        c['targets'][0].update(colored={'C': 1})
        self.assertEqual(self.life(c, order), 0)
        c['targets'][0].update(colored={}, generic=1)
        self.assertEqual(self.life(c, order), 0)

    def test_starting_town_fourth_land_tapped(self):
        c = config([land('a'), land('b'), land('c'),
                    land('Starting Town', 'starting_town', list('WUBRG'))], turn=4, generic=3)
        self.assertIsNone(self.life(c, [0, 1, 2] + [-1] * 6 + [3] + [-1] * 10))
        self.assertEqual(self.life(c, [0, 1, 3] + [-1] * 6 + [2] + [-1] * 10), 0)

    def test_town_matching_minimizes_colored_cost_and_adds_shock_life(self):
        c = config([land('Town', 'starting_town', list('WUBRG')),
                    land('blue')], turn=2, generic=1)
        self.assertEqual(self.life(c, [0, 1] + [-1] * 18), 0)
        c['targets'][0].update(colored={'U': 2}, generic=0)
        self.assertEqual(self.life(c, [0, 1] + [-1] * 18), 1)
        c['lands'][1]['model'] = 'shock'
        self.assertEqual(self.life(c, [0] + [-1] * 6 + [1] + [-1] * 12), 3)
        c['lands'][1] = land('Castle', 'artifact_castle', list('WUBRG'))
        c['targets'][0].update(artifact=True, colored={'B': 1}, generic=1)
        self.assertEqual(self.life(c, [0, 1] + [-1] * 18), 0)

    def test_expanded_land_and_target_limits_keep_budget(self):
        for count in (11, 16):
            c = config([land(str(i)) for i in range(count)])
            c['targets'] = [dict(c['targets'][0], name=str(i)) for i in range(8)]
            r = a.analyze(c, samples=1)
            self.assertEqual(r['limits']['max_land_models'], 16)
            self.assertEqual(r['limits']['max_targets'], 8)
            with self.assertRaisesRegex(ValueError, 'budget'):
                a.analyze(c, samples=1, max_states=1)
        c['lands'].append(land('overflow'))
        with self.assertRaises(ValueError):
            a.validate_config(c)
        c['lands'].pop()
        c['targets'].append(dict(c['targets'][0], name='overflow'))
        with self.assertRaises(ValueError):
            a.validate_config(c)

    def test_draw_step_and_no_future_land_use(self):
        c = config([land('blue')])
        order = [-1] * 7 + [0] + [-1] * 12
        self.assertIsNone(self.life(c, order))
        c['on_play'] = False
        self.assertEqual(self.life(c, order), 0)

    def test_validation_fails_closed(self):
        base = config([land('blue')])
        mutations = [lambda c: c.update(deck_size=True), lambda c: c.update(extra=1),
                     lambda c: c['lands'][0].update(model='fetch'),
                     lambda c: c['lands'][0].update(ability='scry'),
                     lambda c: c['lands'][0].update(count=21),
                     lambda c: c['lands'][0].update(colors=['X']),
                     lambda c: c['targets'][0].update(turn=7),
                     lambda c: c['targets'][0].update(colored={'U/B': 1}),
                     lambda c: c['targets'][0].update(artifact='yes'),
                     lambda c: c['lands'].append(copy.deepcopy(c['lands'][0]))]
        for mutate in mutations:
            c = copy.deepcopy(base)
            mutate(c)
            with self.assertRaises(ValueError):
                a.validate_config(c)
        for samples in [0, 5001, True]:
            with self.assertRaises(ValueError):
                a.analyze(base, samples=samples, seed=42)

    def test_seed_order_hash_bounds_and_reports(self):
        c = config([land('b'), land('a', 'shock')], turn=2)
        r = a.analyze(c, samples=20, seed=42)
        self.assertEqual(r, a.analyze(c, samples=20, seed=42))
        c['lands'].reverse()
        self.assertEqual(r, a.analyze(c, samples=20, seed=42))
        self.assertEqual(r['samples'], 20)
        self.assertEqual(len(r['config_sha256']), 64)
        self.assertIn('perfect', ' '.join(r['assumptions']).lower())
        t = r['targets'][0]
        self.assertLessEqual(t['zero_life_successes'], t['successes'])
        with self.assertRaisesRegex(ValueError, 'budget'):
            a.analyze(c, samples=20, seed=42, max_states=1)

    def test_malformed_verge_and_comparison_contract(self):
        c = config([land('v', 'verge', ['U'], conditional_color=['B'], requires_types=['Island'])])
        with self.assertRaises(ValueError):
            a.validate_config(c)
        left = config([land('a')])
        right = copy.deepcopy(left)
        right['on_play'] = False
        with self.assertRaisesRegex(ValueError, 'identical'):
            a.compare(left, right, samples=1)
        r = a.analyze(left, samples=1, seed=42)
        self.assertIn('python_version', r)

    def test_grixis_comparison_fixtures_complete_under_budget(self):
        left = a.read_config(ROOT / 'examples/mana-grixis-baseline.json')
        right = a.read_config(ROOT / 'examples/mana-grixis-proposal.json')
        self.assertEqual((len(left['lands']), len(right['lands'])), (9, 11))
        for c in (left, right):
            self.assertEqual(sum(l['count'] for l in c['lands']), 26)
        r = a.compare(left, right, samples=50, seed=42)
        for side in ('left', 'right'):
            self.assertEqual(len(r[side]['targets']), 2)
            self.assertLess(r[side]['states_visited'], r[side]['limits']['state_budget'])

    def test_cli_discovery_probability_example_compare_and_errors(self):
        def cli(*args):
            return subprocess.run([sys.executable, 'matchlab.py', *args], cwd=ROOT, text=True, capture_output=True)
        r = cli('tools', '--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual({x['command'] for x in json.loads(r.stdout)['tools']}, {'draw', 'mana', 'audit', 'run'})
        self.assertIn('mana', cli('--help').stdout)
        r = cli('draw', '--deck-size', '10', '--sources', '4', '--draws', '3', '--at-least', '2')
        self.assertEqual(json.loads(r.stdout)['denominator'], 3)
        r = cli('mana', 'examples/mana-basic.json', '--samples', '10', '--seed', '42')
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(json.loads(r.stdout)['samples'], 10)
        r = cli('mana', 'examples/mana-basic.json', '--compare', 'examples/mana-basic.json', '--samples', '10')
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertFalse(json.loads(r.stdout)['paired'])
        self.assertNotEqual(cli('draw', '--deck-size', '1', '--sources', '2', '--draws', '1').returncode, 0)


if __name__ == '__main__':
    unittest.main()
