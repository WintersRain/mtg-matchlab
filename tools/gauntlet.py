#!/usr/bin/env python3
"""Play one deck against a set of opponent lists, many games each, in parallel.

    python3 tools/gauntlet.py --deck DECK.arena.txt --opponents OPP_DIR \\
        --games 200 --seed 500000 --workers 10 --out RESULT.json [--weights SHARES.json]

Each opponent file is an exact Arena export (`OPP_DIR/<name>.arena.txt`). Games are
preboard Forge Default-AI vs Default-AI with alternating seats: deck-construction
evidence under one engine/AI, never human win rates. The same --seed gives every
candidate deck identical per-game seeds against each opponent (paired comparison).
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import math
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]


def plan(opponents, games, seed, chunk):
    if games % 2 or chunk % 2 or games < 2 or chunk < 2:
        raise ValueError('games and chunk must be positive even numbers (seat alternation restarts per chunk)')
    jobs = []
    for opponent in opponents:
        for offset in range(0, games, chunk):
            jobs.append({'opponent': opponent, 'seed': seed + offset, 'games': min(chunk, games - offset)})
    return jobs


def tally(games):
    out = {'wins': 0, 'losses': 0, 'draws': 0, 'failed': 0}
    for game in games:
        if game['status'] == 'completed':
            out['wins' if game['winner'] == 'seat-a' else 'losses'] += 1
        elif game['status'] == 'draw':
            out['draws'] += 1
        else:
            out['failed'] += 1
    out['games'] = out['wins'] + out['losses'] + out['draws']
    return out


def wilson(wins, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def weighted(per_opponent, shares):
    """Share-weighted win rate over tested opponents (weights renormalized) and its standard error."""
    tested = {k: shares[k] for k in per_opponent if shares.get(k)}
    total = sum(tested.values())
    rate = variance = 0.0
    for name, share in tested.items():
        w, r = share / total, per_opponent[name]
        p = r['wins'] / r['games']
        rate += w * p
        variance += w * w * p * (1 - p) / r['games']
    return rate, math.sqrt(variance)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--deck', required=True, type=Path)
    parser.add_argument('--opponents', required=True, type=Path, help='Directory of <name>.arena.txt files')
    parser.add_argument('--only', help='Comma-separated opponent names (default: all in directory)')
    parser.add_argument('--games', type=int, default=200, help='Games per matchup (even)')
    parser.add_argument('--seed', type=int, default=500000)
    parser.add_argument('--chunk', type=int, default=20, help='Games per JVM session (even, <=50)')
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--weights', type=Path, help='JSON {name: share} or gauntlet.json with share fields')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    import matchlab
    import reuse_runner

    # One script index (with per-script hashes) for the whole batch instead of one per chunk.
    index = matchlab.card_index(ROOT / 'vendor/forge/forge-gui/res/cardsfolder')
    deck_text = args.deck.read_text()
    files = {p.name[:-len('.arena.txt')]: p for p in sorted(args.opponents.glob('*.arena.txt'))}
    if args.only:
        files = {k: files[k] for k in args.only.split(',')}
    jobs = plan(list(files), args.games, args.seed, args.chunk)
    shares = {}
    if args.weights:
        raw = json.loads(args.weights.read_text())
        shares = {k: (v['share'] if isinstance(v, dict) else v) for k, v in raw.items()}
    result = {'schema': 1, 'deck': str(args.deck), 'deck_sha256': hashlib.sha256(deck_text.encode()).hexdigest(),
              'opponents': {k: {'file': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for k, p in files.items()},
              'games_per_matchup': args.games, 'seed': args.seed, 'chunk': args.chunk, 'workers': args.workers,
              'mode': 'preboard Forge Default AI both seats, alternating seats', 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sessions': [], 'games': {k: [] for k in files}}
    lock = threading.Lock()

    def run(job):
        body = {'a': {'text': deck_text, 'format': 'Standard'},
                'b': {'text': files[job['opponent']].read_text(), 'format': 'Standard'},
                'games': job['games'], 'seed': job['seed'], 'alternate': True, 'snapshots': False}
        return job, reuse_runner.run_series(body, index=index)

    def save():
        args.out.write_text(json.dumps(result, indent=1))

    with ThreadPoolExecutor(args.workers) as pool:
        for future in as_completed([pool.submit(run, job) for job in jobs]):
            job, series = future.result()
            with lock:
                games = [{k: g.get(k) for k in ('seed', 'seats', 'status', 'winner', 'run_directory')} for g in series['games']]
                result['games'][job['opponent']].extend(games)
                result['sessions'].append({**job, 'status': series['status'], 'session': series.get('session_directory'),
                                           'error': series.get('error')})
                done = sum(len(v) for v in result['games'].values())
                print(f"{job['opponent']:24s} seed {job['seed']}: {series['status']} ({done}/{len(jobs) and sum(j['games'] for j in jobs)} games)", flush=True)
                save()

    per = {}
    for name, games in result['games'].items():
        t = tally(games)
        lo, hi = wilson(t['wins'], t['games'])
        per[name] = dict(t, win_rate=t['wins'] / t['games'] if t['games'] else None, ci95=[lo, hi])
    result['per_opponent'] = per
    if shares:
        rate, se = weighted({k: v for k, v in per.items() if v['games']}, shares)
        result['weighted'] = {'win_rate': rate, 'se': se, 'ci95': [rate - 1.96 * se, rate + 1.96 * se]}
    result['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
    for name, r in per.items():
        print(f"{name:24s} {r['wins']:4d}-{r['losses']:<4d} draws {r['draws']} failed {r['failed']}  "
              f"{100 * (r['win_rate'] or 0):5.1f}%  [{100 * r['ci95'][0]:.0f}-{100 * r['ci95'][1]:.0f}]")
    if 'weighted' in result:
        w = result['weighted']
        print(f"{'WEIGHTED':24s} {100 * w['win_rate']:.1f}%  [{100 * w['ci95'][0]:.1f}-{100 * w['ci95'][1]:.1f}]")
    return 0 if all(s['status'] == 'completed' for s in result['sessions']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
