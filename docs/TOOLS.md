# Tool decision guide

Start with `python3 matchlab.py tools` or `python3 matchlab.py tools --json`.
All commands appear in `python3 matchlab.py --help`; each has its own `--help`.
The JSON catalog has a versioned envelope and distinguishes model fidelity and dependencies.

| Question | Command | What it actually establishes |
| --- | --- | --- |
| Chance of seeing at least k cards from a source pool? | `draw` | Exact hypergeometric probability, no sequencing |
| Can these lands pay one isolated target by a turn? | `mana` | Monte Carlo mana feasibility with optimal perfect-lookahead land sequencing |
| Which of two mana configurations does better under that model? | `mana --compare` | **Unpaired**, right-minus-left estimates, not physical-slot paired trials |
| Do curated inputs match the pin and have Forge scripts? | `audit` | Input/script audit, not legality or rules-fidelity proof |
| What happens in a full game with Forge's AI? | `run` | One preboard AI game, not human win rates |

## Published benchmark archive

The [37-list archive README](../benchmarks/standard/2026-09-14/README.md) and
[portable index](../benchmarks/standard/2026-09-14/index.json) preserve published
lists, source qualification, exact counts, and hashes. They are reference data,
not newly integrated Forge opponents: `run --opponent` still has four predefined
roles. See [capture status](CAPTURE_STATUS.md) for local-only research and gaps.

## Offline quick start (fresh checkout)

Python 3 stdlib on Linux/WSL; no Forge, Java, network, package installation,
private experiments, or card database required for these commands:

```sh
python3 matchlab.py tools
python3 matchlab.py tools --json
python3 matchlab.py draw --deck-size 60 --sources 24 --draws 9 --at-least 3
python3 matchlab.py mana examples/mana-basic.json --samples 500 --seed 42
python3 matchlab.py mana examples/mana-basic.json --compare examples/mana-basic.json --samples 500 --seed 42
python3 matchlab.py mana examples/mana-grixis-baseline.json --compare examples/mana-grixis-proposal.json --samples 50 --seed 42
python3 -m unittest discover -s tests -v
```

The self-comparison is a runnable interface demonstration, **not evidence of a
mana-base improvement**. Its two independently seeded samples may differ even
though the input is identical. Copy/edit the generic fixture to compare actual
alternatives; do not silently import private decklists. Existing `audit`/`run`
commands, prerequisites, engine pin, and privacy rules remain in [README](../README.md)
and [SETUP](../SETUP.md).

## Exact draw probability

`draw` returns reduced integer `numerator`/`denominator` plus a floating-point
`probability` for P(X >= k) with uniform draws **without replacement**. Supply
`--deck-size`, `--sources`, `--draws`; `--at-least` defaults to 1. The exact ratio
is authoritative; the decimal is rounded. Population is bounded to 1..10000;
counts must be nonnegative integers within the population. Impossible tails
return zero. Zero draws and a zero threshold are supported.

For a normal seven-card start, cards seen by turn T are 7+T-1 on the play or
7+T on the draw. This is only a counting convention: no mulligans, tapped-land
rules, multi-color joint constraints, or card selection are modeled. Do not
multiply separate source probabilities to claim independent color success.

## Portable mana JSON contract (model version 1)

The checked fixture [examples/mana-basic.json](../examples/mana-basic.json) is
a generic model, not a legality-checked deck. All objects reject unknown keys,
duplicate JSON keys and unsupported mechanics rather than silently approximating.
There is no card-name lookup; the caller must transcribe the supported portion
of the land's rules accurately. Names are labels only.

Root (all required):

- `deck_size`: integer 1..100, including lands and inert nonland slots.
- `opening_hand`: integer 0..7, no greater than deck size.
- `on_play`: boolean; skip turn-one draw when true.
- `lands`: 1..16 uniquely named land model entries.
- `targets`: 1..8 uniquely named independent target entries.

Each land requires `name` (1..80 characters), `count` (positive integer),
`model`, and `colors` (nonempty unique list from `W U B R G C`). Optional `types`
is a unique list of `Plains Island Swamp Mountain Forest`, default empty.
Types are **not inferred from colors or names**; even `basic` needs explicit
`types` if it should enable a Verge. Land counts may not exceed deck size;
remaining slots are inert nonlands. Each land produces at most one mana.

| `model` | Supported semantics |
| --- | --- |
| `basic`, `untapped` | Enters untapped, supplies listed colors (C is colorless) |
| `tapped` | Always enters tapped |
| `shock` | Choose tapped for no life or untapped for two life |
| `fast` | Untapped with at most two **other** lands already controlled |
| `starting_town` | Untapped with at most two **other** lands; C for zero life, listed colored mana for one life per activation |
| `slow` | Untapped with at least two **other** lands already controlled |
| `verge` | Untapped, one unconditional `colors` entry; additionally supplies `conditional_color` (W/U/B/R/G) while any controlled land has any of `requires_types` |
| `artifact_castle` | Untapped; C always, listed colors only when the target is an artifact |

Only `verge` accepts/requires `conditional_color` and a nonempty
`requires_types` list of the supported basic land types. This is an OR condition,
not a test for producing those colors. Tapped lands still supply types. The
`artifact_castle` model represents a colored-for-artifact restriction, **not**
generic always-available colored mana, and does not model any activated abilities.
Do not use it for other cards merely because their name contains "Castle".
For Starting Town, list all five colors (`W U B R G`); C is automatically
available. Its generic and C payments are always free, even for artifacts;
colored payments cost one life even for artifacts. Castle's supported artifact
colors cost no life. The matcher minimizes life across assignments, adding
Town activation payments to any target-turn shock entry payment.

Each target requires:

- `name`, `turn` (1..6).
- `colored`: map of W/U/B/R/G/C to positive integer pip counts (each <=6), or `{}`.
  Each pip is paid independently: one U/B dual cannot pay both U and B.
- `generic`: integer 0..12; total colored plus generic cost <=12.
- `artifact`: boolean, used only for the restricted land payment rule.

Hybrid, Phyrexian, variable X, snow-specific payments, fetches, surveil, scry,
checklands, bounce lands, multiple-mana production, spells, life gain, and other
mechanics are unsupported. Never relabel an unsupported mechanic as a supported
model and report the result as a faithful card simulation.

## What the mana estimator means

The target is **assumed available externally**, not drawn or reserved in the
opening hand. Thus this is neither joint draw-and-cast probability nor a formal
probability conditional on drawing that card. All nonlands are inert. There are
no mulligans, prior spells, opponents, interaction, ramp, or extra land drops.
It tests casting after the target turn's draw/land drop. One land may be played
per turn, including the option to skip. All previous lands untap normally.

The engine explores feasible land sequences for each sampled draw order and
individual target with **perfect lookahead** into that order. Future lands cannot
be played early, but earlier choices may exploit knowing later draws. This is an
optimistic existence test, not a hidden-information pilot policy, a full curve,
a full gameplay simulator, or a win-rate estimate. Different targets can use
incompatible optimal sequences and are not a jointly feasible curve.

It separately finds **actual zero-life feasibility**. Earlier shocks may enter
tapped for free because no prior spells need mana; a target-turn shock may cost
two. Town's colored activation costs one even when played on an earlier turn.
Minimum life among successful sequences is reported, not damage taken in a
real game; sufficient life to pay is assumed. Every colored pip consumes a
different land, then remaining lands pay generic requirements.

Outputs include seed, samples, canonical config SHA-256, canonical input, model
and Python versions, assumptions, bounds, success counts, zero-life counts,
probabilities, and conditional mean minimum life. Binomial plug-in standard
errors describe Monte Carlo sampling only, **not model error**; endpoint standard
errors of zero do not establish certainty. Do not interpret small noisy deltas
as proof of improvement.

Land and target entries are sorted by unique name, color/type lists normalized,
and JSON keys canonically hashed. Reordering input entries does not change a
run. Renaming an entry can change slot ordering and its hash. Retain configuration,
model version, Python version, seed, and samples for replay; cross-version PRNG
shuffle stability is not promised.

Comparisons require equal deck size, opening hand, play/draw setting, and target
specifications. They use seeds `seed` and `seed+1` with separate PRNG streams;
**no paired/physical-slot claim** is made. Both reports/hashes and seeds are
included. Deltas are right minus left, with independent-sample standard errors
for overall feasibility. Self-comparisons need not return exactly zero.

## Resource limits and failure behavior

Config files are limited to 64 KiB. Samples are 1..5000 (default 500), targets
1..8, distinct land entries 1..16, turns 1..6. Draw horizons cannot exceed deck
size. Single-run seeds are 0..2^63-1, comparison seeds 0..2^63-2.
Each analysis has a hard budget of 2,000,000 explored land transitions shared
across all samples/targets. Exhaustion fails with an error and **no partial
estimate**; reduce samples, targets, turns, or distinct land models. A comparison
gets a separate budget for each side. This is intentionally a small bounded
analysis tool, not an extensible full rules engine.

### Grixis comparison fixtures

`examples/mana-grixis-baseline.json` and `examples/mana-grixis-proposal.json`
contain 26 lands across nine and eleven names respectively, with 34 inert
nonland slots. Both assess M.O.D.O.K. ({3}{B}{B}, artifact) on turn five and
Interceptor Mechan ({2}{B}{R}, artifact) on turn four. The quick-start command
uses only 50 samples to stay comfortably within the shared work budget; this
is a reproducibility/smoke example, not statistical evidence of improvement.
All land names and counts are retained rather than merged into surrogate lands.
Other abilities (Castle token creation, Restless Vents animation/attack effects,
target abilities including lifelink/connive) are outside this isolated-payment
model. No full-deck legality or spell availability claim is made.

Public card references: [M.O.D.O.K.](https://scryfall.com/card/msh/106/modok),
[Interceptor Mechan](https://scryfall.com/card/eoe/220/interceptor-mechan),
[Castle Doom](https://scryfall.com/card/msh/263/castle-doom), and
[Starting Town](https://scryfall.com/card/fin/289/starting-town).

Successful lightweight reports print to stdout without writing runtime files;
errors print a JSON `status: invalid` object and return nonzero (argparse syntax
errors use its usual stderr/exit behavior). Python callers can reuse
`analysis_tools.hypergeometric`, `validate_config`, `analyze`, and `compare`;
`minimum_life` is the low-level evaluator for an already validated config and
valid draw-order indices, not an untrusted-input entrypoint.
