#!/usr/bin/env python3
"""Condense a Forge raw.log into a readable turn-by-turn game log.

    python3 tools/gamelog.py RUN_DIR_OR_RAW_LOG [--names YOU,OPP]

Drops empty phase lines; keeps lands, casts, triggers that target, combat, damage and life.
"""
import argparse
import re
from pathlib import Path

KEEP = ('Land:', 'Add To Stack:', 'Combat:', 'Damage:', 'Life:', 'Mulligan:', 'Game outcome', 'Destroy', 'Zone Change', 'Sacrifice')


def condense(text, names=('seat-a', 'seat-b')):
    out = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'Turn: Turn (\d+) \(Ai\(\d\)-(seat-[ab])\)', line)
        if m:
            who = names[0] if m[2] == 'seat-a' else names[1]
            out.append(f'\n== Turn {m[1]} ({who})')
            continue
        if line.startswith('Life: Life:'):
            line = 'Life: ' + line[len('Life: Life: '):]
        if line.startswith('Resolve Stack:') or line.startswith('Mana:') or line.startswith('Phase:'):
            continue
        if line.startswith(KEEP) or 'has won' in line or 'has lost' in line or 'conceded' in line:
            line = line.replace('Ai(1)-seat-a', names[0]).replace('Ai(2)-seat-b', names[1])
            line = line.replace('Ai(1)-seat-b', names[1]).replace('Ai(2)-seat-a', names[0])
            out.append('  ' + line)
    return '\n'.join(out).strip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', type=Path)
    parser.add_argument('--names', default='seat-a,seat-b')
    args = parser.parse_args()
    path = args.path / 'raw.log' if args.path.is_dir() else args.path
    print(condense(path.read_text(errors='replace'), tuple(args.names.split(','))), end='')


if __name__ == '__main__':
    main()
