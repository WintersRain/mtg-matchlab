# Capture status

This is a selective preservation inventory, not a claim that all local research
has been examined or backed up. Scope: Git tracked/untracked names, the public
benchmark capture, the Doom research directory's top-level names, CLI help,
and only `status` fields from the run summaries in the locations below.
No local raw logs were read. This inventory accompanies the public benchmark
preservation change; local-only material below is deliberately excluded.

## Repository capture

- **37 published benchmark lists now present in the repository worktree:**
  [archive README](../benchmarks/standard/2026-09-14/README.md) and
  [portable index](../benchmarks/standard/2026-09-14/index.json). Exact copies
  of the previous public capture, with source URL/qualification, IDs, parsed
  main/side counts, and SHA-256. All 37 passed the existing parser; unusual
  sideboard sizes remain unaltered. The preservation change adds this archive
  to version control; it was previously saved only outside this repository.
- **Current player synchronized:** `decks/doom.txt`, its manifest hash, and provenance now match the latest authenticated captured September 16 submission (60 main / 0 side). Proposed lower-pain lands were not observed and remain unapplied. Four curated opponents remain unchanged. Earlier player revisions remain in Git history; historical smoke results retain their original hashes. See [current-player smoke](../evidence/current-player-smoke.json).
  accepts stable benchmark selectors while preserving all four role selectors.
- **Offline math and fixtures are already tracked:** `analysis_tools.py`,
  `tests/test_analysis.py`, `examples/mana-basic.json`,
  `examples/mana-grixis-baseline.json`, and `examples/mana-grixis-proposal.json`,
  together with their CLI integration and tool documentation. These provide
  exact draw math and simplified isolated-target mana analysis, not full
  game or full-curve simulation.
- Existing curated provenance/legality evidence and sanitized smoke evidence
  remain tracked. This is distinct from publishing all underlying research.

## Local-only material, not published by this task

Git status identified six untracked experiment directories: `density-baseline`,
`density-repair`, `consolidation-pressure`, `consolidation`, `quality-rebuild-v1`,
and `quality-rebuild-v2` under `experiments/`. An untracked
`evidence/powrdragn-deckbuilding-handoff.md` also remains local and untouched.
None was staged, imported, or declared publication-ready.

The external Doom research workspace contains additional exports, proposals,
construction/quality reviews, oracle checks, mana/density repair work, bounded
checks, and support research, based on top-level filename discovery only.
Those broader research materials are **not captured by this repository archive**.
Local runtime game logs likewise are not repository-backed; tracked sanitized
smoke evidence is not a substitute for the underlying logs. No raw logs, full
source HTML, private player identifiers, credentials, or personal paths were
imported. No exhaustive content review of that local workspace is claimed.

### Selected local run-summary snapshot

Only immediate `*/summary.json` files beneath the listed `runtime/runs`
directories were inspected for aggregate status. These are file counts, not
unique games: experiment copies may overlap. They are not matchup estimates,
and `error` is not a win or valid draw. Counts can change with later runs.

| Local directory | Summary files | `completed` | `error` |
| --- | ---: | ---: | ---: |
| `runtime/runs` | 52 | 50 | 2 |
| `experiments/density-baseline/runtime/runs` | 2 | 2 | 0 |
| `experiments/density-repair/runtime/runs` | 2 | 2 | 0 |
| `experiments/consolidation-pressure/runtime/runs` | 3 | 2 | 1 |
| `experiments/consolidation/runtime/runs` | 2 | 2 | 0 |
| `experiments/quality-rebuild-v1/runtime/runs` | 52 | 50 | 2 |
| `experiments/quality-rebuild-v2/runtime/runs` | 8 | 8 | 0 |

No other status values occurred in this selected snapshot. No raw game logs
were inspected, and these counts do not cover every possible local location.

## Distinct remaining gaps

1. **Execution coverage:** all 37 published lists are now integrated as selectable
   opponents (`standard-2026-09-14-01` through `standard-2026-09-14-37`), alongside
   the four unchanged roles. `decks --json` discovers hashes/counts/provenance;
   `audit --opponent SELECTOR` checks Doom and one list; `audit --all-benchmarks`
   checks all 42 inputs. The all-input audit passed against the pinned Forge
   scripts during integration. Tests cover all 37 source-to-DCK roundtrips,
   immutable hashes, exact short/zero sideboards, unsafe selectors, and run
   identity/provenance. Three real preboard smokes completed: selector 01/seed43,
   14/seed44 with reversed seats, and 27/seed42. These cover full, short, and
   empty sideboards. [Sanitized results](../evidence/benchmark-integration-smoke.json)
   preserve deck hashes and outcomes; raw runtime logs remain ignored/local.
   Those three earlier smokes used the historical Doom list. The newer
   current-player smoke above verifies the synchronized captured player list.
   This is not 37 live smoke games, independent legality
   verification, or proof of gameplay correctness. Use
   `python3 matchlab.py run --opponent standard-2026-09-14-01 --seed 42` with the
   privacy-patched build for one preboard game; no source lists were changed.
2. **Draft workflow:** the current tracked CLI advertises `tools`, `draw`,
   `mana`, `decks`, `audit`, and `run`, not a draft workflow. The pinned Forge source
   contains `BoosterDraft`, `BoosterDraftAI`, and `LimitedPlayerAI`, including
   pack-choice and pick entrypoints. That is source-level capability, not an
   implemented or runtime-tested Matchlab drafting interface. No draft was run.
3. **Broader backup/publication:** local experiments and external research need
   separate review and sanitization before any publication. This task does not
   stage, commit, push, or import that material.
