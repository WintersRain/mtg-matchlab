# Agent entrypoint

Read [docs/TOOLS.md](docs/TOOLS.md) before choosing an analysis. Run
`python3 matchlab.py tools --json` for the machine-readable tool catalog and
`python3 matchlab.py --help` for commands. Offline examples are checked into
`examples/`; no private artifacts, external experiments, or Forge install are
needed for `draw` and `mana`.

- Distinguish exact draw math, simplified isolated-target mana feasibility,
  Forge input audits, and full Forge AI games. Never label mana results a full
  curve/game simulation or human win rate; preserve reported assumptions.
- Keep input schemas parameterized, validate unsupported mechanics fail-closed,
  and include hashes/seeds/limits when reporting results.
- Use only public, tracked examples in documentation. Do not import, publish,
  commit, or depend on private artifacts, raw local logs, credentials, personal
  paths, or unrelated untracked evidence/experiments.
- Preserve the Forge pin, privacy requirements, and existing run interface;
  read README.md and SETUP.md before using Forge.
- Run `python3 -m unittest discover -s tests -v`; use tests before implementation.
- Discover opponents with `python3 matchlab.py decks --json`: four curated roles
  and `standard-2026-09-14-01` through `standard-2026-09-14-37`. Preserve archive
  bytes/index hashes and exact zones; never fill short/empty sideboards or swap
  in another list. `audit --opponent SELECTOR` checks Doom plus that opponent;
  `audit --all-benchmarks` checks all 42 inputs against pinned Forge scripts.
  `run --opponent SELECTOR --seed 42` remains one preboard game, recording the
  actual selector/provenance/hashes. Do not treat discovery as script support,
  legality, rules fidelity, or evidence that every opponent was smoke-tested.

For MTG analysis workflows, read [the compact shared Matchlab skill](skills/matchlab-workflow/SKILL.md). It defines task routing, exact-version evidence, and cross-bot handoffs.

## Staying clean

- Run `python3 tools/check_clean.py` before ending work; it must report clean.
- Never hand-write Forge card scripts. Copy official upstream scripts into `forge-resources/`; edits to pinned scripts go in `patches/`.
- Push from **Windows** git (WSL git has no GitHub credentials):
  `git -C //wsl.localhost/Ubuntu/home/winter/projects/mtg-matchlab -c safe.directory=* push origin main`
- Card names: always use the printed (paper) card name. Through the Omenpaths (OM1) is a digital
  reskin of Universes Beyond cards (e.g. Kavaero, Mind-Bitten is the digital name of the printed
  card **Superior Spider-Man**); MTGO lists and Scryfall use the OM1 name. Translate with `match_review.CardDB(db).display(name)`.
