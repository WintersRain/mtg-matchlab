#!/usr/bin/env python3
"""Install reviewed Matchlab resource overlays without rebuilding Forge."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

PIN = 'b88dbd3ebd78b6aebfb2839cbbffee3102d59e30'

def install(root):
    root = Path(root).resolve()
    forge = root / 'vendor/forge'
    head = subprocess.check_output(['git', '-C', str(forge), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise RuntimeError(f'Forge pin mismatch: {head}; expected {PIN}')
    source = root / 'forge-resources'
    dest = forge / 'forge-gui/res'
    planned = []
    for path in sorted(source.rglob('*.txt')):
        rel = path.relative_to(source)
        target = dest / rel
        data = path.read_bytes()
        # These overlays only add cards missing from this pin. Never replace
        # an independently changed vendor resource or upstream card silently.
        if target.exists() and target.read_bytes() != data:
            raise RuntimeError(f'Refuse overwriting different resource: {target}')
        planned.append((target, data, str(rel)))
    for target, data, rel in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return [{'path': rel, 'sha256': hashlib.sha256(data).hexdigest()} for _, data, rel in planned]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps({'forge_pin': PIN, 'resources': install(args.root)}, indent=2))
