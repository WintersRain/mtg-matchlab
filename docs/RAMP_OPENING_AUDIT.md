# Experimental four-turn ramp opening audit

`ramp_opening_audit.py` is a standalone extension of the existing opening audit,
reusing `opening_audit.parse_cost` and `payments`. It is not a default runner,
Forge substitute, full rules engine, or matchup evaluator.

```
python3 ramp_opening_audit.py CONFIG.json --samples 3000 --seed 919 --output RESULT.json
python3 -m unittest discover -s tests -v
```

## Config

- `cards`: explicit name -> model mapping. Lands require `land: true`, `model`,
  `colors` string and `types` list. Supported models: basic, shock, untapped,
  compound, verge. Verge also requires `conditional` and `requires`.
- Nonlands require `land: false`, conventional `cost`, and an explicit `effect`:
  elf, roots, draw, interaction, body, haste, copy_target, or held. Optional
  `threat` and `legendary` booleans; draw has an optional positive `draw` count.
  Effects are caller-audited abstractions, not inferred from names. Unknown
  models/effects and unsupported costs fail closed. This experimental input is
  trusted local configuration, not the stricter public `mana` JSON contract.
- `candidates`: ordered name -> array of exactly 60 physical card-slot names.
  All nonland slots must be identical across candidates; only land slots vary.
- Other root fields may preserve provenance and explanation in the saved report.

`held` explicitly means a card occupies its proper draw slot but is never cast.
Do not hide unsupported effects as `body` or `interaction`: the latter may only
represent a deliberately chosen interaction mode that has no effect on our own
mana, library, or battlefield. The opponent is assumed to supply legal targets.
Prepared and warp abilities are optional and not used. Legendary duplicates are
not recast. `copy_target` assumes the modeled draw spells target artifacts/lands;
it copies their draws, but never copies untargeted Roots.

## Policy and outputs

The report embeds its assumptions, input, seed, source and implementation hashes,
Python version, per-seat counts/rates, paired delta standard errors, shock-life
histograms, and selected accepted hands with four-turn traces. Physical slot
shuffles are shared per trial and mulligan depth. Library shuffles after Roots
use shared per-slot random priorities, filtering independently removed cards.

The London keep/bottom policy sees only the offered hand. It keeps 2–4 lands and
an active spell of mana value at most two payable by turn two with known lands,
and bottoms by this test, land balance, active-card count and mana value. It
forces five. Play and draw use the same conservative keep test. This deliberately
simple policy is neither perfect play nor a proven optimal mulligan strategy.

Land selection consults only current hand and battlefield, including known
next-turn land options. Actual casting uses real cards, mana, Elf sickness,
Roots fetches and shuffles, Price-like draws, haste, and cumulative shock life.
There is no combat, opponent action or removal of our resources. Shocks can enter
tapped when immediate spell priority does not justify paying two life.

`mana_*` is an independent payment probe at the beginning of that turn's main
phase, after the chosen land, on the actual prior trajectory. Probes do not spend
mana, and different probes are not simultaneously payable. They do not optimize
land choice for an externally supplied target. `cast_*` means actually drawn and
cast, using spent resources; it is not conditional on drawing the card. `life`
is mean cumulative shock damage, not a probability. `RR_color_stall` requires an
active RR card in hand whose total cost fits the source count but whose colored
cost cannot be paid. Report uncertainty is Monte Carlo error, not policy/model
error. Private deck configurations and reports belong outside the repository.
