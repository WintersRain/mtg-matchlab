#!/usr/bin/env python3
"""Loopback Matchlab dashboard and direct two-list JSON runner (stdlib only)."""
import argparse
import copy
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from types import SimpleNamespace
import uuid
import matchlab as m

DATA = m.ROOT / 'runtime/dashboard'
GUARD = threading.Lock()
ACTIVE = None

def import_text(text):
    if not isinstance(text, str) or len(text.encode()) > 65536:
        raise ValueError('Each Arena list must be text of at most 64 KiB')
    lines = text.lstrip('\ufeff').splitlines()
    name = 'Imported deck'
    if lines and lines[0].strip() == 'About':
        if len(lines) < 2 or not lines[1].strip().startswith('Name '):
            raise ValueError('About must be followed by Name <deck name>')
        name = lines[1].strip()[5:].strip()
        lines = lines[2:]
    if not name or len(name) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid deck name')
    return name, m.parse_arena('\n'.join(lines))

def resolve(spec, seat):
    if not isinstance(spec, dict): raise ValueError(seat + ': expected deck object')
    if 'text' in spec:
        text = spec['text']
        name, deck = import_text(text)
        info = {'selector': seat, 'kind': 'imported', 'name': name,
                'source_sha256': m.sha(text.encode()), 'source': 'Arena text',
                'source_url': str(spec.get('source_url', ''))[:2048],
                'source_date': str(spec.get('source_date', ''))[:80],
                'format': str(spec.get('format', 'unspecified'))[:80],
                'legality_checked': False, 'arena_text': text, 'imported_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    elif 'saved' in spec:
        key = spec['saved']
        if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{32}', key): raise ValueError('Invalid saved deck ID')
        saved = json.loads((DATA / 'decks' / (key + '.json')).read_text())
        return resolve(saved, seat)
    else:
        deck, info = m.load_deck(spec.get('selector'))
        info = dict(info, name=info['selector'], format='captured Standard', legality_checked=False)
        info['arena_text'] = (m.ROOT / info['source']).read_text()
    info['counts'] = {z: sum(c.values()) for z, c in deck.items()}
    return deck, info

def prepare_pair(body):
    index = m.card_index(m.ROOT / 'vendor/forge/forge-gui/res/cardsfolder')
    pair, failures = {}, []
    for key, seat in [('a', 'seat-a'), ('b', 'seat-b')]:
        try:
            deck, info = resolve(body[key], seat)
            cards = m.audit_cards(deck, index)
            pair[seat] = (deck, dict(info, cards=cards))
        except (KeyError, OSError, ValueError) as exc: failures.append(seat + ': ' + str(exc))
    if failures: raise ValueError('; '.join(failures))
    return pair

def audit_pair(pair, out):
    actual = subprocess.check_output(['git', '-C', str(m.ROOT / 'vendor/forge'), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != m.PIN: raise ValueError('Forge pin mismatch: ' + actual)
    out.mkdir(parents=True, exist_ok=True)
    report = {'engine_pin': actual, 'decks': {}}
    for seat, (deck, info) in pair.items():
        info = dict(info)
        (out / (seat + '.arena.txt')).write_text(info.pop('arena_text'))
        text = m.forge_deck(seat, deck)
        (out / (seat + '.dck')).write_text(text)
        report['decks'][seat] = dict(info, dck_sha256=m.sha(text.encode()))
    m.write_json(out / 'audit.json', report)
    return report

def duel(body):
    pair = prepare_pair(body)
    args = SimpleNamespace(opponent='seat-b', seed=body.get('seed', 42), swap=body.get('swap', False),
        java=str(m.ROOT / '.local/jdk-17.0.20.1+1/bin/java'),
        jar=str(m.ROOT / 'vendor/forge/forge-gui-desktop/target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar'),
        pair=pair, snapshots=body.get('snapshots', True))
    if type(args.seed) is not int or not 0 <= args.seed < 2**63: raise ValueError('Invalid seed')
    if type(args.swap) is not bool: raise ValueError('swap must be boolean')
    if type(args.snapshots) is not bool: raise ValueError('snapshots must be boolean')
    return m.run(args)

def series(body, on_game=None, stop_path=None):
    from reuse_runner import run_series
    return run_series(body, on_game=on_game, stop_path=stop_path)

def replay(log):
    # Snapshots are explicit engine state, never inferred from incomplete action text.
    events = []
    previous = {}
    for i, line in enumerate(log.splitlines()):
        if line.startswith('MATCHLAB_SNAPSHOT '):
            try:
                state = json.loads(line[len('MATCHLAB_SNAPSHOT '):])
                if not isinstance(state, dict) or state.get('version') != 1 or not isinstance(state.get('players'), list):
                    raise ValueError('Invalid snapshot schema')
                game_key = state.get('game', 1)
                if state.get('delta') is True:
                    if game_key not in previous: raise ValueError('Delta has no initial engine state')
                    merged = copy.deepcopy(previous[game_key])
                    merged.update({k:v for k,v in state.items() if k != 'players'})
                    players = {p['id']:p for p in merged['players']}
                    for player in state['players']:
                        if player['id'] not in players: raise ValueError('Delta refers to unknown player')
                        target = players[player['id']]
                        target.update({k:v for k,v in player.items() if k != 'zones'})
                        target.setdefault('zones', {}).update(player.get('zones', {}))
                    state = merged
                    state['materialized_from_delta'] = True
                previous[game_key] = copy.deepcopy(state)
                events.append({'index': i, 'kind': 'snapshot', 'text': state.get('event', 'Engine state'), 'snapshot': state})
            except (KeyError, ValueError, TypeError):
                events.append({'index': i, 'kind': 'Engine', 'text': 'Invalid engine snapshot (not rendered)'})
        else:
            events.append({'index': i, 'text': line, 'kind': line.partition(':')[0] if ':' in line else 'Engine'})
    snapshots = [e for e in events if e['kind'] == 'snapshot']
    # Forge prints its stored action log again at completion. Each snapshot already
    # carries its exact new actions; use those frames to avoid replaying the final
    # duplicate log, while retaining the untouched raw log on disk.
    warnings = [e for e in events if e['text'].startswith('MATCHLAB_SNAPSHOT_ERROR') or e['text'] == 'Invalid engine snapshot (not rendered)']
    return sorted(snapshots + warnings, key=lambda e:e['index']) if snapshots else events

def batch_settings(body):
    games, seed = body.get('games', 1), body.get('seed', 42)
    if type(games) is not int or not 1 <= games <= 50: raise ValueError('Games must be 1..50 per matchup')
    if type(seed) is not int or not 0 <= seed <= 2**63 - 1 - 499: raise ValueError('Seed out of batch range')
    if type(body.get('alternate', True)) is not bool: raise ValueError('alternate must be boolean')
    if type(body.get('reuse', False)) is not bool: raise ValueError('reuse must be boolean')
    return games, seed

def batch_worker(key, request):
    global ACTIVE
    path = DATA / 'batches' / (key + '.json')
    state = {'id': key, 'status': 'running', 'games': [], 'total': 0, 'request': request}
    games, seed = batch_settings(request)
    opponents = request.get('opponents') or [request['b']]
    state['total'] = games * len(opponents)
    try:
        for opponent in opponents:
            if request.get('reuse', False):
                stop_path = DATA / 'batches' / (key + '.stop')
                if stop_path.exists():
                    state['status'] = 'stopped'; return
                state['current'] = {'seed': seed + len(state['games']), 'opponent': opponent.get('selector', opponent.get('saved', 'pasted list')), 'mode': 'reused JVM'}
                m.write_json(path, state)
                recorded = 0
                def record(result):
                    nonlocal recorded
                    recorded += 1
                    state['games'].append(result)
                    if recorded < games:
                        state['current']['seed'] = result['seed'] + 1
                    else:
                        state.pop('current', None)
                    m.write_json(path, state)
                result = series({'a': request['a'], 'b': opponent, 'games': games,
                    'seed': seed + len(state['games']), 'alternate': request.get('alternate', True),
                    'snapshots': True}, on_game=record, stop_path=stop_path)
                state.setdefault('sessions', []).append(result['session_directory'])
                if result['status'] not in ('completed', 'finished'):
                    state['status'] = result['status']; return
                continue
            for n in range(games):
                if (DATA / 'batches' / (key + '.stop')).exists():
                    state['status'] = 'stopped'; return
                body = {'a': request['a'], 'b': opponent, 'seed': seed + len(state['games']),
                        'swap': request.get('alternate', True) and n % 2 == 1}
                state['current'] = {'seed': body['seed'], 'swap': body['swap'], 'opponent': opponent.get('selector', opponent.get('saved', 'pasted list'))}
                m.write_json(path, state)
                proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), 'duel'],
                    input=json.dumps(body), text=True, capture_output=True, timeout=330)
                try: result = json.loads(proc.stdout)
                except ValueError: result = {'status': 'error', 'error': proc.stderr[-4000:] or proc.stdout[-4000:]}
                state['games'].append(result)
                m.write_json(path, state)
        state['status'] = 'finished'
    except Exception as exc: state.update(status='error', error=str(exc))
    finally:
        state.pop('current', None)
        m.write_json(path, state)
        with GUARD: ACTIVE = None

def catalog():
    rows = []
    for selector in ['doom', *m.ROLES, *m.benchmark_entries()]:
        _, info = m.load_deck(selector)
        rows.append(dict(info, text=(m.ROOT / info['source']).read_text()))
    saved = [dict(json.loads(p.read_text()), saved=p.stem) for p in sorted((DATA / 'decks').glob('*.json'))]
    return {'decks': rows, 'saved': saved, 'benchmark_date': '2026-09-14', 'engine_pin': m.PIN}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Polling is frequent; keep the server terminal useful rather than noisy.
        if len(args)>1 and str(args[1]).startswith(('4','5')): super().log_message(format,*args)
    def send(self, body, code=200, content='application/json'):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code); self.send_header('Content-Type', content); self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff'); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        try:
            if self.path == '/': return self.send((m.ROOT / 'dashboard.html').read_text(), content='text/html; charset=utf-8')
            if self.path == '/api/decks': return self.send(catalog())
            if self.path == '/api/live':
                running = []
                for p in (m.ROOT / 'runtime/runs').glob('*/summary.json'):
                    summary = json.loads(p.read_text())
                    if summary.get('status') == 'running': running.append((p.stat().st_mtime, p, summary))
                if not running: return self.send({'run_id': None})
                _, p, summary = max(running, key=lambda row: row[0])
                raw = p.parent / 'raw.log'
                log = raw.read_text(errors='replace') if raw.exists() else ''
                if log and not log.endswith('\n'): log = log.rpartition('\n')[0]
                return self.send({'run_id': p.parent.name, 'summary': summary, 'events': replay(log)})
            if self.path == '/api/batches':
                return self.send([json.loads(p.read_text()) for p in sorted((DATA / 'batches').glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)][:30])
            match = re.fullmatch(r'/api/replay/([0-9a-f]{32})', self.path)
            if match:
                folder = m.ROOT / 'runtime/runs' / match[1]
                return self.send({'summary': json.loads((folder / 'summary.json').read_text()),
                    'events': replay((folder / 'raw.log').read_text(errors='replace'))})
            if self.path == '/api/history':
                return self.send([json.loads(p.read_text()) for p in sorted((m.ROOT / 'runtime/runs').glob('*/summary.json'), key=lambda p:p.stat().st_mtime, reverse=True)][:100])
            self.send({'error': 'Not found'}, 404)
        except (OSError, ValueError) as exc: self.send({'error': str(exc)}, 400)

    def do_POST(self):
        global ACTIVE
        try:
            # JSON-only mutations and same-origin checks prevent cross-site form writes.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''): raise ValueError('Cross-origin request rejected')
            if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                raise ValueError('Loopback Host required')
            if self.headers.get('Content-Type') != 'application/json': raise ValueError('JSON required')
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 1024 * 1024: raise ValueError('Request exceeds 1 MiB')
            body = json.loads(self.rfile.read(size))
            if self.path == '/api/validate':
                pair = prepare_pair(body)
                return self.send({k: v[1] for k, v in pair.items()})
            if self.path == '/api/save':
                name, deck = import_text(body['text'])
                key = uuid.uuid4().hex
                record = {k: body[k] for k in ('text', 'source_url', 'source_date', 'format') if k in body}
                record.update(name=name, sha256=m.sha(body['text'].encode()), saved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
                m.write_json(DATA / 'decks' / (key + '.json'), record)
                return self.send({'saved': key, 'name': name})
            if self.path == '/api/batch':
                batch_settings(body)
                opponents = body.get('opponents') or [body['b']]
                if not isinstance(opponents, list) or not 1 <= len(opponents) <= 10: raise ValueError('Choose 1..10 opponents')
                # Validate every input before queuing any games.
                for opponent in opponents: prepare_pair({'a': body['a'], 'b': opponent})
                with GUARD:
                    if ACTIVE: return self.send({'error': 'A dashboard batch is already running'}, 409)
                    key = uuid.uuid4().hex; ACTIVE = key
                    m.write_json(DATA / 'batches' / (key + '.json'), {'id': key, 'status': 'queued', 'games': [], 'total': body.get('games', 1)*len(opponents)})
                    threading.Thread(target=batch_worker, args=(key, body), daemon=True).start()
                return self.send({'id': key}, 202)
            if self.path == '/api/stop':
                key = body.get('id', '')
                if not re.fullmatch('[0-9a-f]{32}', key): raise ValueError('Invalid batch ID')
                (DATA / 'batches' / (key + '.stop')).touch()
                return self.send({'status': 'Will stop after current game'})
            self.send({'error': 'Not found'}, 404)
        except (KeyError, TypeError, OSError, ValueError) as exc: self.send({'error': str(exc)}, 400)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['serve', 'duel', 'series'], nargs='?', default='serve')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if args.action in ('duel', 'series'):
        try:
            text = sys.stdin.read(1024*1024 + 1)
            if len(text) > 1024*1024: raise ValueError('Input too large')
            body = json.loads(text)
            if args.action == 'series':
                report = series(body)
                print(json.dumps(report, indent=2))
                return 0 if report['status'] in ('completed', 'finished') else 1
            return duel(body)
        except (KeyError, TypeError, OSError, ValueError) as exc:
            print(json.dumps({'status': 'error', 'error': str(exc)})); return 1
    for sub in ['decks', 'batches']: (DATA / sub).mkdir(parents=True, exist_ok=True)
    print(f'Matchlab: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

if __name__ == '__main__': raise SystemExit(main())
