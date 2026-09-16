"""Public archive integration; no installed Forge required."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import matchlab as m
import test_matchlab

ARCHIVE = Path('benchmarks/standard/2026-09-14')

class BenchmarkTests(unittest.TestCase):
    def test_discover_select_and_roundtrip_all_37(self):
        self.assertTrue(hasattr(m, 'deck_catalog'), 'missing deck discovery')
        catalog = m.deck_catalog()
        self.assertEqual(len(catalog), 41)
        for row in catalog:
            with self.subTest(selector=row['selector']):
                deck, info = m.load_deck(row['selector'])
                self.assertEqual(info['selector'], row['selector'])
                text = m.forge_deck(row['selector'], deck)
                arena = text.split('[Main]\n', 1)[1].replace('[Sideboard]', 'Sideboard')
                self.assertEqual(m.parse_arena('Deck\n' + arena), deck)
                self.assertEqual(sum(deck['main'].values()), 60)
        rows = json.loads((m.ROOT / ARCHIVE / 'index.json').read_text())['decks']
        for row in rows:
            deck, info = m.load_deck(f"standard-2026-09-14-{row['id']:02d}")
            self.assertEqual(sum(deck['sideboard'].values()), row['side'])
            self.assertEqual(info['source_sha256'], row['sha256'])
            self.assertEqual(info['provenance']['id'], row['id'])

    def test_unknown_and_unsafe_selectors(self):
        self.assertTrue(hasattr(m, 'load_deck'), 'missing selector resolution')
        for selector in ('../doom', '/tmp/deck', 'standard-2026-09-14-38', 'doom.dck', 'aggro/../doom'):
            with self.subTest(selector=selector), self.assertRaisesRegex(ValueError, 'Unknown opponent selector'):
                m.load_deck(selector)

    def test_archive_tamper_and_unsafe_manifest_path(self):
        self.assertTrue(hasattr(m, 'load_deck'), 'missing immutable archive loader')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(m.ROOT / ARCHIVE, root / ARCHIVE)
            source = root / ARCHIVE / 'deck-01.txt'
            original = source.read_bytes()
            source.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                m.load_deck('standard-2026-09-14-01', root)
            source.write_bytes(original)
            index = root / ARCHIVE / 'index.json'
            data = json.loads(index.read_text())
            data['decks'][0]['file'] = '../../../../decks/doom.txt'
            m.write_json(index, data)
            with self.assertRaisesRegex(ValueError, 'archive'):
                m.load_deck('standard-2026-09-14-01', root)

    def test_selected_and_all_audit(self):
        self.assertTrue(hasattr(m, 'deck_catalog'), 'missing benchmark audit selection')
        names = set()
        for row in m.deck_catalog():
            deck, _ = m.load_deck(row['selector'])
            names.update(deck['main']); names.update(deck['sideboard'])
        doom, _ = m.load_deck('doom')
        names.update(doom['main'])
        with tempfile.TemporaryDirectory() as td, patch.object(m.subprocess, 'check_output', return_value=m.PIN), patch.object(m, 'card_index', return_value={n: {} for n in names}):
            report = m.audit(out=Path(td), opponent='standard-2026-09-14-27')
            self.assertEqual(set(report['decks']), {'doom', 'standard-2026-09-14-27'})
            self.assertEqual(report['decks']['standard-2026-09-14-27']['counts']['sideboard'], 0)
            report = m.audit(out=Path(td), all_benchmarks=True)
            self.assertEqual(len(report['decks']), 42)
            with patch.object(m, 'card_index', return_value={}):
                with self.assertRaisesRegex(ValueError, 'Unsupported Forge card'):
                    m.audit(out=Path(td), opponent='standard-2026-09-14-01')

    def test_cli_discovery_and_invalid_selection(self):
        def cli(*args):
            return subprocess.run([sys.executable, str(m.ROOT / 'matchlab.py'), *args], capture_output=True, text=True)
        result = cli('decks', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['decks']), 41)
        self.assertIn('standard-2026-09-14-37', cli('decks').stdout)
        for args in [('audit', '--opponent', '../doom'), ('run', '--opponent', '../doom', '--seed', '42')]:
            result = cli(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Unknown opponent selector', result.stdout + result.stderr)

class BenchmarkRunTests(unittest.TestCase):
    run_fixture = test_matchlab.HarnessTests.run_fixture
    run_summary = test_matchlab.HarnessTests.run_summary

    def test_run_records_benchmark_identity_provenance_and_hash(self):
        with self.run_fixture() as (root, args, launch, _):
            shutil.copytree(Path(__file__).resolve().parents[1] / ARCHIVE, root / ARCHIVE)
            args.opponent = 'standard-2026-09-14-03'
            args.swap = True
            source = (root / ARCHIVE / 'deck-03.txt').read_bytes()
            deck = m.parse_arena(source.decode())
            names = {'Island'} | set(deck['main']) | set(deck['sideboard'])
            with patch.object(m, 'card_index', return_value={n: {} for n in names}):
                # Fixture winner must follow the swapped seat.
                def capture(command, cwd, env, raw):
                    raw.write_text(f'Game Result: Game 1 ended in 9 ms. Ai(1)-{args.opponent} has won!\n')
                    return {'status': None, 'exit_code': 0}
                launch.side_effect = capture
                self.assertEqual(m.run(args), 0)
            summary = self.run_summary(root)
            self.assertEqual(summary['seats'], [args.opponent, 'doom'])
            self.assertEqual(summary['opponent'], args.opponent)
            info = summary['decks'][args.opponent]
            self.assertEqual(info['source_sha256'], m.sha(source))
            self.assertEqual(info['provenance']['id'], 3)
            self.assertEqual(info['counts']['sideboard'], 13)
            self.assertIn(args.opponent + '.dck', summary['command'])
            self.assertTrue(summary['preboard'])
