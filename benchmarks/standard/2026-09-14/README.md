# Published Standard benchmark archive — September 14, 2026

These 37 `deck-01.txt` through `deck-37.txt` files preserve the previously saved
published lists byte-for-byte. The portable [index.json](index.json) retains
publication URL, qualification, original numeric IDs, main/side counts, relative
filenames, and SHA-256 of each exact text file.

Source: [Magic.gg Traditional Standard ranked decklists](https://magic.gg/decklists/traditional-standard-ranked-decklists-september-14-2026).
Qualification: Six or more consecutive ranked match wins by Platinum or Mythic
players; Traditional Standard BO3. **Not a metagame share or tier ranking.**
This is preservation of the prior capture, not a fresh fetch or independent
validation of the publisher's qualification.

All 37 lists were accepted by the existing `matchlab.parse_arena` parser and
its parsed main/side totals match the original index. Every main is 60 cards.
Preserved sideboards shorter than 15: ID 3 has 13, ID 5 has 12, ID 8 has 7,
IDs 14, 24, and 34 have 14, and ID 27 has 0. No missing cards were invented.
Parser acceptance does not establish Standard legality or Forge rules fidelity.

## Selectable Forge opponents

All 37 files are integrated directly as immutable Forge opponent inputs.
Selectors are `standard-2026-09-14-01` through `standard-2026-09-14-37`, mapping
exactly to original numeric IDs. The four curated role selectors and the five
curated `decks/` inputs / `decks.json` remain unchanged.

From the repository root:

```sh
python3 matchlab.py decks --json
python3 matchlab.py audit --opponent standard-2026-09-14-27
python3 matchlab.py audit --all-benchmarks
python3 matchlab.py run --opponent standard-2026-09-14-27 --seed 42
```

Discovery verifies hashes/counts offline. Audit uses the pinned Forge scripts;
run requires the privacy-patched build described in [SETUP](../../../SETUP.md).
Both main and sideboard names must be supported or the run fails closed.
No cards are substituted or added. Forge DCK output preserves both sections;
games remain preboard, with no BO3 sideboarding policy. Run summaries retain
the selected ID, publication URL/qualification, source and DCK hashes.
Script presence is not proof of legality or faithful card implementation.

No source HTML, player identifiers, raw logs, or private filesystem paths are
included. See [capture status](../../../docs/CAPTURE_STATUS.md) for boundaries.

## Offline verification

Run from the repository root:

```sh
python3 - <<'PY'
from pathlib import Path
import hashlib
import json
from matchlab import parse_arena
root = Path('benchmarks/standard/2026-09-14')
index = json.loads((root / 'index.json').read_text())
assert len(index['decks']) == len(list(root.glob('deck-*.txt'))) == 37
assert {d['id'] for d in index['decks']} == set(range(1, 38))
for row in index['decks']:
    assert Path(row['file']).name == row['file']
    data = (root / row['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['sha256']
    deck = parse_arena(data.decode('utf-8'))
    assert sum(deck['main'].values()) == row['main']
    assert sum(deck['sideboard'].values()) == row['side']
print('37 archive files: hashes and parser counts verified')
PY
```
