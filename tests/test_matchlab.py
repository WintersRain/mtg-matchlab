import importlib.util
import pathlib
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from io import StringIO
import json
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.find_spec('matchlab')
if SPEC:
    import matchlab as m

class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(SPEC, 'matchlab implementation missing')

    def test_parse_arena_printings_and_side(self):
        d = m.parse_arena('Deck\n56 Island\n4 Opt (ABC) 12\n\nSideboard\n1 Negate\n')
        self.assertEqual(d['main'], {'Island': 56, 'Opt': 4})
        self.assertEqual(d['sideboard'], {'Negate': 1})

    def test_invalid_counts_names_sections(self):
        for text in ['Deck\n0 Island', 'Deck\n60 ', '60 Island', 'Deck\n60 Island\nCommander\n1 Foo', 'Deck\n60 Island\nSideboard\n16 Negate', 'Deck\n59 Island', 'Deck\n60 Bad|Name']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                m.parse_arena(text)

    def test_copy_limit_includes_side_and_duplicates(self):
        for text in ['Deck\n56 Island\n4 Opt\nSideboard\n1 Opt', 'Deck\n55 Island\n3 Opt\n2 Opt']:
            with self.assertRaises(ValueError):
                m.parse_arena(text)

    def test_script_index_exact_not_filename_guess(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td)
            (p / 'unexpected.txt').write_text('Name:Opt\nTypes:Instant\n')
            idx = m.card_index(p)
            self.assertEqual(m.audit_cards({'main': {'Opt': 4}, 'sideboard': {}}, idx)['Opt']['path'], str(p / 'unexpected.txt'))
            with self.assertRaises(ValueError):
                m.audit_cards({'main': {'Not a card': 1}, 'sideboard': {}}, idx)

    def test_result_success_draw_and_fail_closed(self):
        win = 'Game Result: Game 1 ended in 123 ms. Ai(1)-doom has won!\n'
        seats = ['doom', 'aggro']
        self.assertEqual(m.parse_result(win, 0, seats)['winner'], 'doom')
        self.assertEqual(m.parse_result('Game Result: Game 1 ended in a Draw! Took 123 ms.\n', 0, seats)['status'], 'draw')
        for log, code in [(win, 1), ('', 0), (win + win, 0), ('java.lang.NullPointerException\n' + win, 0), ('Could not load deck - doom\n' + win, 0), (win.replace('doom', 'other'), 0)]:
            self.assertNotIn(m.parse_result(log, code, seats)['status'], ('completed', 'draw'))
        self.assertEqual(m.parse_result('Stopping slow match as draw\n' + win, 0, seats)['status'], 'timeout')

    def test_error_handler_registration_is_not_an_error(self):
        log = 'Error handling registered!\nGame Result: Game 1 ended in 4044 ms. Ai(1)-doom has won!\n'
        self.assertEqual(m.parse_result(log, 0, ['doom', 'aggro'])['status'], 'completed')

    def test_forge_unsupported_placeholder_is_not_a_win(self):
        log = 'An unsupported card was requested: "Foo" from "XXX".\nGame Result: Game 1 ended in 9 ms. Ai(1)-doom has won!\n'
        self.assertEqual(m.parse_result(log, 0, ['doom', 'aggro'])['status'], 'error')

    def test_seed_command_and_swap(self):
        cmd = m.build_command('/java', '/forge.jar', '/home', ['aggro', 'doom'], 42)
        self.assertEqual(cmd[-13:], ['sim', '-d', 'aggro.dck', 'doom.dck', '-n', '1', '-s', '42', '-a', 'Default', 'Default', '-c', '180'])
        for seed in [-1, 2**63]:
            with self.assertRaises(ValueError):
                m.build_command('/java', '/forge.jar', '/home', ['doom', 'aggro'], seed)

    def test_normalization_preserves_order_and_game_numbers(self):
        a = 'Turn 2\nGame Result: Game 1 ended in 123 ms. Ai(1)-doom has won!\n'
        self.assertEqual(m.normalized_hash(a), m.normalized_hash(a.replace('123 ms', '999 ms')))
        self.assertNotEqual(m.normalized_hash(a), m.normalized_hash(a.replace('Turn 2', 'Turn 3')))
        self.assertNotEqual(m.normalized_hash('a\nb\n'), m.normalized_hash('b\na\n'))

    def test_audit_rejects_changed_curated_input(self):
        import shutil
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            shutil.copytree(m.ROOT / 'decks', root / 'decks')
            shutil.copy(m.ROOT / 'decks.json', root / 'decks.json')
            doom = root / 'decks/doom.txt'
            doom.write_text(doom.read_text().replace('3 Island', '2 Island').replace('4 Swamp', '5 Swamp'))
            with patch.object(m.subprocess, 'check_output', return_value=m.PIN), \
                    patch.object(m, 'card_index', return_value={}), \
                    self.assertRaisesRegex(ValueError, 'hash mismatch'):
                m.audit(root)

    @contextmanager
    def run_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / 'vendor/forge/forge-gui').mkdir(parents=True)
            (root / 'decks').mkdir()
            data = b'Deck\n60 Island\n'
            manifest = {}
            for name in ('doom', *m.ROLES):
                (root / 'decks' / (name + '.txt')).write_bytes(data)
                manifest[name] = {'sha256': m.sha(data), 'zones': m.parse_arena(data.decode())}
            m.write_json(root / 'decks.json', manifest)
            java, jar = root / 'java', root / 'forge.jar'
            java.touch()
            jar.touch()
            args = SimpleNamespace(opponent='aggro', swap=False, seed=42, java=java, jar=jar)
            real_audit = m.audit

            def check_output(command, **kwargs):
                if '-version' in command:
                    return 'fake java'
                return m.PIN if 'rev-parse' in command else b''

            def capture(command, cwd, env, raw):
                raw.write_text('Game Result: Game 1 ended in 9 ms. Ai(1)-doom has won!\n')
                return {'status': None, 'exit_code': 0}

            with patch.object(m, 'ROOT', root), \
                    patch.object(m, 'audit', side_effect=lambda *a, **kw: real_audit(root, **kw)), \
                    patch.object(m, 'card_index', return_value={'Island': {}}), \
                    patch.object(m.subprocess, 'check_output', side_effect=check_output), \
                    patch.object(m, 'capture', side_effect=capture) as launch, \
                    redirect_stdout(StringIO()):
                yield root, args, launch, real_audit

    def run_summary(self, root):
        return json.loads(next((root / 'runtime/runs').glob('*/summary.json')).read_text())

    def test_run_isolated_from_standalone_audit_outputs(self):
        with self.run_fixture() as (root, args, launch, real_audit):
            original = m.subprocess.check_output.side_effect

            def concurrent_audit(command, **kwargs):
                if '-version' in command:
                    real_audit(root)
                    # Pause the standalone writer after truncation of its shared output.
                    (root / 'runtime/audit/doom.dck').write_bytes(b'')
                return original(command, **kwargs)

            m.subprocess.check_output.side_effect = concurrent_audit
            self.assertEqual(m.run(args), 0)
            summary = self.run_summary(root)
            copied = pathlib.Path(summary['run_directory']) / 'decks/constructed/doom.dck'
            self.assertEqual(m.sha(copied.read_bytes()), summary['decks']['doom']['dck_sha256'])
            launch.assert_called_once()

    def test_run_rejects_corrupted_copied_dck_before_launch(self):
        with self.run_fixture() as (root, args, launch, _):
            original = pathlib.Path.write_bytes

            def corrupt_copy(path, data):
                if path.parent.name == 'constructed' and path.name == 'doom.dck':
                    data = b''
                return original(path, data)

            with patch.object(pathlib.Path, 'write_bytes', corrupt_copy):
                self.assertEqual(m.run(args), 1)
            launch.assert_not_called()
            summary = self.run_summary(root)
            self.assertEqual(summary['status'], 'error')
            self.assertIsNone(summary['winner'])
            self.assertIn('DCK hash mismatch', summary['error'])

    def test_profile_cleanup_holds_run_lock(self):
        with self.run_fixture() as (root, args, launch, _):
            original = pathlib.Path.unlink
            checked = []

            def check_lock(path, *a, **kw):
                if path.name == 'forge.profile.properties':
                    with (root / 'runtime/run.lock').open('w') as lock:
                        with self.assertRaises(BlockingIOError):
                            m.fcntl.flock(lock, m.fcntl.LOCK_EX | m.fcntl.LOCK_NB)
                    checked.append(True)
                return original(path, *a, **kw)

            with patch.object(pathlib.Path, 'unlink', check_lock):
                self.assertEqual(m.run(args), 0)
            self.assertEqual(checked, [True])

    def test_profile_cleanup_failure_still_writes_error_summary(self):
        with self.run_fixture() as (root, args, launch, _):
            original = pathlib.Path.unlink

            def fail_cleanup(path, *a, **kw):
                if path.name == 'forge.profile.properties':
                    raise PermissionError('profile cleanup denied')
                return original(path, *a, **kw)

            with patch.object(pathlib.Path, 'unlink', fail_cleanup):
                self.assertEqual(m.run(args), 1)
            summary = self.run_summary(root)
            self.assertEqual(summary['status'], 'error')
            self.assertIsNone(summary['winner'])
            self.assertIn('profile cleanup denied', summary['error'])
            with (root / 'runtime/run.lock').open('w') as lock:
                m.fcntl.flock(lock, m.fcntl.LOCK_EX | m.fcntl.LOCK_NB)

    def test_bounded_process_and_timeout(self):
        import sys
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'raw.log'
            result = m.capture([sys.executable, '-c', 'print("x"*10000)'], pathlib.Path(td), {}, p, 5, 100)
            self.assertEqual(result['status'], 'log_limit')
            self.assertLessEqual(p.stat().st_size, 100)
            result = m.capture([sys.executable, '-c', 'import time; time.sleep(10)'], pathlib.Path(td), {}, p, .1, 100)
            self.assertEqual(result['status'], 'timeout')

if __name__ == '__main__':
    unittest.main()
