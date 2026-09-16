# MTG Matchlab — analysis tools and local Forge AI matches

**Choose a tool: [docs/TOOLS.md](docs/TOOLS.md)** — exact draw probabilities,
simplified isolated-target mana feasibility/comparison, Forge input audit, or
full Forge AI games. Agents can start at [AGENTS.md](AGENTS.md) or run
`python3 matchlab.py tools --json` for the machine-readable catalog.

Offline, fresh-checkout examples (Python 3 stdlib, no Forge or network):

```sh
python3 matchlab.py tools
python3 matchlab.py draw --deck-size 60 --sources 24 --draws 9 --at-least 3
python3 matchlab.py mana examples/mana-basic.json --samples 500 --seed 42
```

`mana` is a bounded Monte Carlo **isolated-target** analysis with perfect-lookahead
land sequencing, assumed target availability, no mulligans or prior spells.
It is not a full curve/game simulator. See the guide for supported land models,
JSON schema, actual zero-life feasibility, and unpaired comparison limitations.

## Forge game harness

Small Python 3 stdlib CLI for **one full Forge AI-versus-AI game per process**.
This is not an LLM decision API. Forge's `Default` AI pilots both decks. Results
measure these deck/AI/engine combinations, not human win rates or optimal play.

## Inputs and evidence

- `decks/doom.txt`: exact prior Doom revision, 60 main, no supplied sideboard.
- `decks/{aggro,midrange,control,combo}.txt`: exact handoff lists, each 60 main / 15 side.
- `decks.json`: immutable-input SHA-256 checks, parsed zones, evidence references.
- `evidence/opponents/`: curated September 15, 2026 research handoff: provenance,
  exact lists, per-name Scryfall legality, small Arena-alternates response, README.
- `evidence/doom-provenance.json`: origin of the prior Doom revision.
- `evidence/doom-legality.json`: fresh September 15 Scryfall check; every Doom card
  is Standard-legal. No independent official rotation/B&R audit is claimed.

Opponents: Mono-Green Landfall (aggro/ramp hybrid), Dimir Midrange, 4c Control,
and Bant Airbending Combo. See the evidence README for selection nuance, source
URLs, dates, records, and limitations. Original raw HTML/bulk API files are
intentionally not vendored; original research documents may reference them.
No dislike filters, card substitutions, or sideboard inventions are applied.

## Prerequisites

Linux/WSL, Python 3, Git, Java 17; the local build uses Maven 3.9.11.
Forge must be cloned at `vendor/forge` and pinned to
`b88dbd3ebd78b6aebfb2839cbbffee3102d59e30` (source `2.0.15-SNAPSHOT`).
See [SETUP.md](SETUP.md) for exact clone, privacy-patch, and build commands.
The harness itself neither rebuilds nor modifies Forge Java source.

**Privacy:** apply the included `options.setEnabled(false)` Sentry patch
and build from that patched source. Source pin alone does not establish the
JAR includes that patch. The harness records the actual JAR SHA-256 and Java
source worktree-diff SHA-256, but is not a network sandbox. Do not claim all
possible network traffic is disabled. The patch is in `patches/disable-sentry.patch`.

Default paths:

```
.local/jdk-17.0.20.1+1/bin/java
vendor/forge/forge-gui-desktop/target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar
```

Pass `--java /absolute/path` and `--jar /absolute/path` if the build produces a
different artifact. Do not point at a thin JAR without its dependencies.

## Usage

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 matchlab.py audit
python3 matchlab.py run --opponent aggro --seed 42
python3 matchlab.py run --opponent aggro --seed 42 --swap
```

`audit` verifies the exact Git HEAD, immutable deck input hashes, Arena sections,
60-card main, <=15 side, duplicate/combined main-side four-copy limits (basic
lands excepted). It reads actual Forge card-script **Name fields**, not guessed
filenames, and rejects missing/ambiguous names, including sideboard names.
It writes `runtime/audit/{doom,aggro,midrange,control,combo}.dck` with `[metadata]`
`Name=...`, `[Main]` and `[Sideboard]`, plus `audit.json` mapping every name to
its real script path and SHA-256. Script existence is not proof of rules fidelity,
valid printed edition, complete token/dependency support, or Standard legality.
The parser intentionally fails closed on unsupported special formats/sections
and nonbasic copy-limit exceptions; these five lists do not need exceptions.
Arena `(SET) number` suffixes are accepted and omitted in name-based DCK output.

The native command is precisely:

```
java -Djava.awt.headless=true -Duser.home=<isolated-home> -jar <jar> sim \
  -d doom.dck aggro.dck -n 1 -s 42 -a Default Default -c 180
```

`--swap` reverses deck seats, not a guarantee of being on the play. Seeds must
be 0..9223372036854775807; Forge's option parser interprets a leading minus as
an option. Each run has fresh user/cache/deck/home/XDG directories, a merged
stdout/stderr pipe, and a manifest. Runs are serialized with a nonblocking
repository lock. A temporary symlink at `vendor/forge/forge-gui/forge.profile.properties`
points at the run's properties; an existing profile is never overwritten and
causes a failure. Normal completion/errors remove the symlink. An OS-level
kill of Python can leave it behind: inspect it and remove only the stale harness
symlink before retrying. Do not run an external Forge process concurrently.

## Results and reproducibility

Each `runtime/runs/<id>/summary.json` records seed, seats, AI profiles, engine
pin/version, actual JAR and source-diff hashes, Java version, exact command,
input/DCK/script hashes, return code, bounded raw-log size, elapsed walltime,
raw SHA-256, normalized-log SHA-256, and outcome status. Preflight failures
also write a summary (without information unavailable at failure time).
Exit zero from Forge is **not sufficient**: exactly one recognized Game 1 result
with the expected player/seat is required. Exception/error indicators override
apparent wins. Statuses:

- `completed`: recognized win and winner; `draw`: recognized ordinary draw.
- `timeout`: Forge's `Stopping slow match as draw` or 300-second process deadline.
- `error`: preflight/process/error-marker failure; `invalid`: absent, duplicate,
  malformed, or unexpected winner result; `log_limit`: output exceeded 8 MiB.

Only completed/draw runs make the CLI return 0. Timeout, error, invalid, and
log-limit runs **must not be counted as wins or valid draws**. Internal timeout
is 180 seconds of simulation; outer deadline includes initialization. Exceeding
the raw-log cap kills the process group, so truncated logs never become wins.
Each log is bounded; total retained runs are not automatically pruned. Delete
old runtime run directories when no process is using them. All runtime artifacts,
Java/Maven binaries, vendor sources, and bytecode caches are gitignored.

Normalization v1 preserves full merged output order (Forge itself reverses its
stored game entries to chronological order before printing). Only CRLF -> LF,
canonical hexadecimal UUID -> `<UUID>`, and numeric `ms` durations -> `<TIME> ms`
are changed. No card numbers, life totals, turn numbers, seats, or action ordering
are removed. It hashes the full ordered log, including initialization output,
not a parsed action replay. Other nondeterministic fields remain deliberately;
a hash difference is evidence to inspect, not proof that gameplay differed.
UUID normalization can hide differences in object identity: compare raw logs
for diagnosis. Walltime in JSON is not part of this hash.

Repeat identical seed/seats/JAR/Java/input versions and compare normalized hashes
empirically. **Determinism is not assumed or proven.** The seed is set after
Forge model initialization. No proven hidden-information fairness, optimal AI,
full action replay, save-state restore, or exhaustive rules correctness is
claimed. These are **preboard games**, not BO3 sideboard matches; sideboards are
retained for fidelity/audit but no match-level sideboarding policy is evaluated.

## Source contract inspected

At the pinned tree:

- `forge-gui-desktop/.../forge/view/SimulateMatch.java`: options lines 48–90,
  AI profiles/player names 115–155, timeout 159–160, single-game loop 179–182,
  error/timeout handling and chronological results 205–244, filename resolution
  378–401. Filenames are concatenated with `decksConstructedDir`; passing an
  absolute DCK filename would be wrong. Hence basename `.dck` arguments.
- `forge-gui/.../ForgeProfileProperties.java`: `userDir`, `cacheDir`, `decksDir`,
  `decksConstructedDir` loaded from the assets-relative properties file.
- `forge-gui-desktop/.../forge/GuiDesktop.java`: assets path; running with cwd
  `vendor/forge/forge-gui` works for this snapshot layout.
- `forge-core/.../forge/deck/io/DeckSerializer.java`: metadata/section format.

## Verification scope

Tests were written and observed failing before implementing the harness;
coverage includes parsing, invalid counts/names, combined copy limits, absent
scripts, precise seeded command construction, result/error parsing, log
normalization/order, bounded subprocess output, timeout, and changed-input
rejection. `audit` was run against all supplied lists and the actual card tree.
Live smoke games against all four opponents completed on September 15, 2026.
See `evidence/smoke-verification.json` for sanitized runtime evidence. These
smoke results establish execution, not matchup win rates or pilot quality.
