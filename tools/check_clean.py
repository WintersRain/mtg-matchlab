#!/usr/bin/env python3
"""Fail when work would be lost or unreproducible.

Engine: vendor/forge must equal the pin + patches/*.patch + forge-resources/ overlays,
nothing more. Repository: no uncommitted changes and no unpushed commits.
Exit 0 when clean, 1 otherwise; prints a JSON report.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OVERLAY_PREFIX = 'forge-gui/res/'


def patched_paths(patch_text):
    return {line[len('+++ b/'):] for line in patch_text.splitlines() if line.startswith('+++ b/')}


def parse_status(text, sep='\n'):
    """Porcelain v1 entries -> {path: code}. Pass sep='\\0' for `git status -z` output."""
    return {entry[3:]: entry[:2].strip() for entry in text.split(sep) if entry}


def classify(status, patch_paths, overlay_paths):
    expected = patch_paths | overlay_paths
    problems = [f'untracked engine change (not in patches/ or forge-resources/): {p}'
                for p in sorted(status) if p not in expected]
    problems += [f'patched file not modified (patch not applied?): {p}' for p in sorted(patch_paths) if p not in status]
    problems += [f'overlay not installed: {p}' for p in sorted(overlay_paths) if p not in status]
    return problems


def git(cwd, *args):
    return subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True)


def engine_problems(root):
    sys.path.insert(0, str(root))
    from matchlab import PIN
    forge = root / 'vendor/forge'
    problems = []
    head = git(forge, 'rev-parse', 'HEAD').stdout.strip()
    if head != PIN:
        problems.append(f'Forge HEAD {head} != pin {PIN}')
    patches = sorted((root / 'patches').glob('*.patch'))
    paths = set()
    for patch in patches:
        paths |= patched_paths(patch.read_text())
        if git(forge, 'apply', '--check', '-R', str(patch)).returncode:
            problems.append(f'working tree does not match {patch.relative_to(root)} (edited after patching?)')
    resources = root / 'forge-resources'
    overlays = {}
    for f in resources.rglob('*'):
        if f.is_file() and f.name != 'README.md':
            overlays[OVERLAY_PREFIX + f.relative_to(resources).as_posix()] = f
    for rel, source in sorted(overlays.items()):
        target = forge / rel
        if target.exists() and target.read_bytes() != source.read_bytes():
            problems.append(f'installed overlay differs from forge-resources/: {rel}')
    status = parse_status(git(forge, 'status', '--porcelain', '-z', '--untracked-files=all').stdout, sep='\0')
    status.pop('forge-gui/forge.profile.properties', None)  # reported separately below
    problems += classify(status, paths, set(overlays))
    if (forge / 'forge-gui/forge.profile.properties').is_symlink():
        problems.append('stale forge.profile.properties symlink (remove only if no run is in progress)')
    return problems


def repo_problems(root):
    problems = []
    dirty = parse_status(git(root, 'status', '--porcelain', '-z').stdout, sep='\0')
    problems += [f'uncommitted: {p}' for p in sorted(dirty)]
    ahead = git(root, 'rev-list', '--count', '@{u}..HEAD')
    if ahead.returncode == 0 and ahead.stdout.strip() != '0':
        problems.append(f'{ahead.stdout.strip()} unpushed commit(s)')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--engine-only', action='store_true', help='Skip uncommitted/unpushed repository checks')
    args = parser.parse_args()
    problems = engine_problems(ROOT) + ([] if args.engine_only else repo_problems(ROOT))
    print(json.dumps({'clean': not problems, 'problems': problems}, indent=2))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
