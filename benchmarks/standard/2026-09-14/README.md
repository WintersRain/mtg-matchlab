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

## Archive, not opponent integration

These files are reference inputs, **not 37 integrated runnable Forge opponents**.
`matchlab.py run --opponent` still accepts only `aggro`, `midrange`, `control`,
and `combo`; the five curated `decks/` inputs and `decks.json` are unchanged.
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
