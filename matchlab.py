#!/usr/bin/env python3
"""Small, fail-closed Forge single-game harness (Python stdlib, Linux/WSL)."""
import argparse
import collections
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parent
PIN = 'b88dbd3ebd78b6aebfb2839cbbffee3102d59e30'
ROLES = ('aggro', 'midrange', 'control', 'combo')
BASICS = {'Plains', 'Island', 'Swamp', 'Mountain', 'Forest', 'Wastes'}
BASICS |= {'Snow-Covered ' + n for n in BASICS - {'Wastes'}}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_arena(text):
    deck = {'main': {}, 'sideboard': {}}
    section = None
    seen = set()
    for num, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if line in ('Deck', 'Sideboard'):
            if line in seen or (line == 'Sideboard' and 'Deck' not in seen) or (line == 'Deck' and seen):
                raise ValueError(f'Invalid section at line {num}')
            seen.add(line)
            section = 'main' if line == 'Deck' else 'sideboard'
            continue
        match = re.fullmatch(r'([1-9][0-9]*) (.+?)(?: \([A-Za-z0-9]+\) [0-9]+)?', line)
        if section is None or not match:
            raise ValueError(f'Invalid Arena line {num}: {line!r}')
        count, name = int(match[1]), match[2].strip()
        if not name or any(c in name for c in '|[]\t\r\n'):
            raise ValueError(f'Invalid card name: {name!r}')
        deck[section][name] = deck[section].get(name, 0) + count
    if sum(deck['main'].values()) != 60 or sum(deck['sideboard'].values()) > 15:
        raise ValueError('This curated harness requires exactly 60 main and at most 15 sideboard')
    total = collections.Counter(deck['main']) + collections.Counter(deck['sideboard'])
    bad = [name for name, count in total.items() if count > 4 and name not in BASICS]
    if bad:
        raise ValueError('Copy limit exceeded: ' + ', '.join(bad))
    return deck


def card_index(folder):
    """Read actual first/front Name fields; never infer card names from filenames."""
    index = {}
    for path in sorted(Path(folder).rglob('*.txt')):
        data = path.read_bytes()
        names = re.findall(r'^Name:(.+)$', data.decode('utf-8-sig'), re.M)
        if not names:
            continue
        name = names[0].strip()
        entry = {'path': str(path), 'sha256': sha(data), 'faces': [n.strip() for n in names]}
        for key in (name, ' // '.join(entry['faces'])):
            if key in index and index[key]['path'] != str(path):
                raise ValueError('Ambiguous Forge card script: ' + key)
            index[key] = entry
    return index


def audit_cards(deck, index):
    names = set(deck['main']) | set(deck['sideboard'])
    missing = sorted(names - index.keys())
    if missing:
        raise ValueError('Unsupported Forge card names: ' + ', '.join(missing))
    return {name: index[name] for name in sorted(names)}


def build_command(java, jar, home, seats, seed):
    # Native parser treats a leading minus as a new option, so negative seeds cannot work.
    if not 0 <= seed < 2**63:
        raise ValueError('Seed must be a nonnegative signed Java long (0..9223372036854775807)')
    return [str(java), '-Djava.awt.headless=true', '-Duser.home=' + str(home), '-jar', str(jar),
            'sim', '-d', *[s + '.dck' for s in seats], '-n', '1', '-s', str(seed),
            '-a', 'Default', 'Default', '-c', '180']


def parse_result(log, code, seats):
    # Exact benign startup banner; do not suppress other error lines.
    log = '\n'.join(line for line in log.splitlines() if line != 'Error handling registered!')
    if 'Stopping slow match as draw' in log:
        return {'status': 'timeout', 'winner': None}
    errors = r'Exception|(?:^|\s)(?:ERROR|Error)(?:\b|:)|StackOverflowError|OutOfMemoryError|Could not load deck|No deck found|Unknown AI profile|Illegal parameter|match cannot start|Unsupported|unsupported card was requested|Alchemy card not found|Unable to|Failed to'
    if code != 0 or re.search(errors, log, re.M):
        return {'status': 'error', 'winner': None}
    lines = [s for s in log.splitlines() if s.startswith('Game Result:')]
    if len(lines) != 1:
        return {'status': 'invalid', 'winner': None}
    if re.fullmatch(r'Game Result: Game 1 ended in a Draw! Took \d+ ms\.', lines[0]):
        return {'status': 'draw', 'winner': None}
    m = re.fullmatch(r'Game Result: Game 1 ended in \d+ ms\. Ai\(([12])\)-(.+) has won!', lines[0])
    if m and m[2] == seats[int(m[1]) - 1]:
        return {'status': 'completed', 'winner': m[2], 'winner_seat': int(m[1])}
    return {'status': 'invalid', 'winner': None}


def normalized_hash(log):
    # No line sorting: Forge already prints its game log in chronological order.
    log = log.replace('\r\n', '\n')
    log = re.sub(r'\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b', '<UUID>', log)
    log = re.sub(r'\b\d+(?:\.\d+)? ms\b', '<TIME> ms', log)
    return sha(log.encode())


def capture(command, cwd, env, raw, timeout=300, limit=8 * 1024 * 1024):
    """Merged pipe order, bounded disk+memory, terminate entire child process group."""
    status = None
    size = 0
    started = time.monotonic()
    with Path(raw).open('wb') as output:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            with selectors.DefaultSelector() as sel:
                sel.register(proc.stdout, selectors.EVENT_READ)
                while sel.get_map():
                    if time.monotonic() - started > timeout:
                        status = 'timeout'
                        break
                    for key, _ in sel.select(.05):
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            sel.unregister(key.fileobj)
                            continue
                        remaining = limit - size
                        output.write(chunk[:remaining])
                        size += min(len(chunk), remaining)
                        if len(chunk) > remaining:
                            status = 'log_limit'
                            break
                    if status:
                        break
                if not status:
                    try:
                        proc.wait(timeout=max(.01, timeout - (time.monotonic() - started)))
                    except subprocess.TimeoutExpired:
                        status = 'timeout'
        finally:
            if proc.poll() is None or status:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            proc.wait()
            proc.stdout.close()
    return {'status': status, 'exit_code': proc.returncode, 'raw_bytes': size,
            'elapsed_seconds': time.monotonic() - started}


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def audit(root=ROOT, *, out=None):
    forge = root / 'vendor/forge'
    actual = subprocess.check_output(['git', '-C', str(forge), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != PIN:
        raise ValueError(f'Forge pin mismatch: {actual}')
    index = card_index(forge / 'forge-gui/res/cardsfolder')
    out = root / 'runtime/audit' if out is None else out
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / 'decks.json').read_text())
    report = {'engine_pin': actual, 'decks': {}}
    for name in ('doom', *ROLES):
        source = root / 'decks' / (name + '.txt')
        data = source.read_bytes()
        if sha(data) != manifest[name]['sha256']:
            raise ValueError('Curated deck hash mismatch: ' + name)
        deck = parse_arena(data.decode('utf-8-sig'))
        if deck != manifest[name]['zones']:
            raise ValueError('Curated deck zones mismatch: ' + name)
        cards = audit_cards(deck, index)
        text = '[metadata]\nName=' + name + '\n[Main]\n'
        text += ''.join(f'{count} {card}\n' for card, count in deck['main'].items())
        text += '[Sideboard]\n' + ''.join(f'{count} {card}\n' for card, count in deck['sideboard'].items())
        (out / (name + '.dck')).write_text(text)
        report['decks'][name] = {'source_sha256': sha(data), 'dck_sha256': sha(text.encode()),
                                'counts': {zone: sum(counts.values()) for zone, counts in deck.items()},
                                'cards': cards}
    write_json(out / 'audit.json', report)
    return report


def run(args):
    runtime = ROOT / 'runtime'
    runtime.mkdir(exist_ok=True)
    run_dir = runtime / 'runs' / uuid.uuid4().hex
    run_dir.mkdir(parents=True)
    seats = ['doom', args.opponent]
    if args.swap:
        seats.reverse()
    summary = {'schema': 1, 'engine_pin': PIN, 'engine_version': '2.0.15-SNAPSHOT',
               'seed': args.seed, 'seats': seats, 'ai_profiles': ['Default', 'Default'],
               'status': 'invalid', 'winner': None, 'preboard': True,
               'normalization': 'v1: CRLF to LF; canonical UUID to <UUID>; numeric ms to <TIME> ms; preserve line order',
               'run_directory': str(run_dir)}
    profile = ROOT / 'vendor/forge/forge-gui/forge.profile.properties'
    try:
        # ExitStack removes our profile before the lock's file descriptor closes.
        with (runtime / 'run.lock').open('w') as lock, ExitStack() as cleanup:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Never consume shared standalone audit outputs: generate a private snapshot.
            report = audit(ROOT, out=run_dir / 'audit')
            summary['decks'] = {s: report['decks'][s] for s in seats}
            java = Path(args.java).resolve()
            jar = Path(args.jar).resolve()
            if not java.is_file() or not jar.is_file():
                raise ValueError('Java/JAR missing; build Forge first or supply --java and --jar')
            summary['jar_sha256'] = sha(jar.read_bytes())
            summary['java_version'] = subprocess.check_output([str(java), '-version'], stderr=subprocess.STDOUT, text=True, timeout=15).strip()
            summary['engine_worktree_diff_sha256'] = sha(subprocess.check_output(['git', '-C', str(ROOT / 'vendor/forge'), 'diff', 'HEAD', '--', '*.java']))
            dirs = {key: run_dir / sub for key, sub in [('userDir', 'user'), ('cacheDir', 'cache'), ('decksDir', 'decks'), ('decksConstructedDir', 'decks/constructed')]}
            for directory in dirs.values():
                directory.mkdir(parents=True, exist_ok=True)
            home = run_dir / 'home'
            home.mkdir()
            for seat in seats:
                (dirs['decksConstructedDir'] / (seat + '.dck')).write_bytes((run_dir / 'audit' / (seat + '.dck')).read_bytes())
            config = ''.join(f'{key}={str(value).replace(chr(92), chr(92)*2)}\n' for key, value in dirs.items())
            (run_dir / 'forge.profile.properties').write_text(config)
            # Refuse to overwrite a real user's profile; temporary symlink removed even on errors.
            profile.symlink_to(run_dir / 'forge.profile.properties')
            cleanup.callback(profile.unlink)
            command = build_command(java, jar, home, seats, args.seed)
            summary['command'] = command
            env = os.environ.copy()
            for key in ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS'):
                env.pop(key, None)
            env.update(HOME=str(home), XDG_CONFIG_HOME=str(run_dir / 'xdg-config'),
                       XDG_CACHE_HOME=str(run_dir / 'xdg-cache'), XDG_DATA_HOME=str(run_dir / 'xdg-data'))
            raw = run_dir / 'raw.log'
            for seat in seats:
                copied = dirs['decksConstructedDir'] / (seat + '.dck')
                if sha(copied.read_bytes()) != report['decks'][seat]['dck_sha256']:
                    raise ValueError('DCK hash mismatch: ' + seat)
            result = capture(command, ROOT / 'vendor/forge/forge-gui', env, raw)
            log = raw.read_text(errors='replace')
            summary.update(result)
            summary['raw_sha256'] = sha(raw.read_bytes())
            summary['normalized_log_sha256'] = normalized_hash(log)
            summary.update(parse_result(log, result['exit_code'], seats) if not result['status'] else {'status': result['status']})
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        summary.update(status='error', winner=None, error=str(exc))
    finally:
        write_json(run_dir / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary['status'] in ('completed', 'draw') else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    from analysis_tools import add_commands, dispatch
    add_commands(sub)
    sub.add_parser('audit', help='Audit pinned Forge inputs (not legality or gameplay)')
    runner = sub.add_parser('run', help='Run one full Forge Default-AI game')
    runner.add_argument('--opponent', choices=ROLES, required=True)
    runner.add_argument('--seed', type=int, required=True)
    runner.add_argument('--swap', action='store_true')
    runner.add_argument('--java', default=str(ROOT / '.local/jdk-17.0.20.1+1/bin/java'))
    runner.add_argument('--jar', default=str(ROOT / 'vendor/forge/forge-gui-desktop/target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar'))
    args = parser.parse_args()
    if args.action == 'run':
        return run(args)
    try:
        if args.action in ('tools', 'draw', 'mana'):
            report = dispatch(args)
            print(report if isinstance(report, str) else json.dumps(report, indent=2))
            return 0
        report = audit()
        print(json.dumps({'status': 'audited', 'engine_pin': PIN, 'decks': {name: d['counts'] for name, d in report['decks'].items()}, 'report': str(ROOT / 'runtime/audit/audit.json')}, indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'invalid', 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
