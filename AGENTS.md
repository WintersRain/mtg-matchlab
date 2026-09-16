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
