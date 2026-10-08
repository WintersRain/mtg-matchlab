# Bounded opening, mana, and basic-replacement validation

Use when a frozen deck needs quick quantitative checks without quantity changes or a new game simulator. Keep project evidence private; this reference contains the reusable method rather than a private deck export.

## Discover and freeze

1. Read the current tool catalog and selected documentation. Confirm source/test interfaces when documentation or examples do not resolve the question; do not invent a schema or treat a missing example as a permanent tool limitation.
2. Hash exact deck bytes, cross-check parsed quantities against the supplied quantity record, and use supplied exact Oracle records for costs and type lines. Do not overwrite inputs.
3. Put configs, adapter code, raw reports, logs and summary in a new evidence directory. Record tool source hashes and Python version.

## Actual-card opening audit

The observed standalone interface is:

```sh
python3 opening_audit.py CONFIG --samples 200 --seed 917 --output RESULT
```

Verify the current interface before reuse. Config has `cards` keyed by name and `candidates` mapping labels to lists of physical card slots. Nonlands carry `land:false`, exact `cost`, `body`, and `legendary`; lands carry supported model, colors and explicit basic types. Verge models need their conditional color and enabling types. Inspect the current source for exact field names.

- Preserve every actual card slot. Mark only genuine supported creatures as bodies. Ramp artifacts, planeswalkers, selection spells and removal must not be relabeled as bodies to make metrics look relevant.
- Check cost and land-model support independently of the mana CLI: the inspected three-turn `opening_audit.py` rejects hybrid pips and slowlands even though isolated `mana` supports slowlands. Do not silently price G/W as exclusively green or rename a slowland as always tapped/untapped. If a bounded private adapter is necessary, retain exact input costs, shared-source hash and adapted source; add fixtures for payment with either hybrid color, rejection of colorless-only payment, no double-use of a land, slow entry with zero/one/two prior lands, and regression equality for previously supported costs. Update both actual-turn and known-hand lookahead tappedness. Label the adapter and omitted card effects explicitly; passing compatibility fixtures is not full gameplay validation.
- The observed engine models three turns, body costs, hidden-future deterministic deployment, and London mulligans with a forced five-card floor. It does not resolve card abilities.
- Its strict keep rule requires 2–4 lands, a known-hand body by T2 and at least two by T3, evaluated without future draws. A useful sensitivity variant requires the same land range and early body but drops the second-body requirement.
- Implement sensitivity as a retained local subclass overriding only `Pilot.keep`, importing the existing run/deployment engine. Preserve original bottoming and sequencing unless explicitly testing those too. Restore the original class after each run; do not edit shared tools.
- Use the same physical slots, sample count and seed across policies. State whether keep logic is identical on play/draw. Keep qualification is not the same as observed deployment after subsequent draws.
- Report reach-five, forced-five-fails-rule, body-by-T2 and follow-up/two-body metrics separately. A body-centric rule can over-mulligan a resource/control deck; large sensitivity is a policy warning, not a recommended real-match keep rate.
- Do not interpret the engine's self-baseline paired-delta output as a comparison between separately run policies.

## Isolated mana

```sh
python3 matchlab.py mana CONFIG --samples 200 --seed 917
```

For short bounded work, 200–500 samples per target/seat can be sufficient to expose coarse issues; respect the user's tighter bound. Separate single-target commands isolate transition budgets and simplify replay. Reusing seeds is reproducible, but targets remain separate existence tests, not a jointly feasible curve.

Transcribe basic types explicitly; they are not inferred from land names or produced colors. Distinguish tapped duals, shock choices, unconditional versus conditional Verge mana, and untapped colorless lands. Explicitly omit unsupported surveil and activated abilities.

Always label: target externally supplied, no mulligans, inert nonlands, no ramp/selection, perfect-lookahead land sequencing, one land per turn. Retain successes, denominator, seed, sampling standard error, zero-life feasibility and actual resource limits. These are neither joint draw-and-cast probabilities nor win rates.

## Inventory-conserving basic replacement

This is finite-state payment analysis, not an opening or gameplay simulator. Reuse `opening_audit.Pilot.colors` / `payments`; when available, cross-check each payment with `analysis_tools.can_pay` using explicit land-model indices.

For sequential payment fixtures, inspect the payment primitive's return contract before composing calls. In the inspected `opening_audit.payments`, each result is a tuple of **used source indices**, not remaining source colors. Remove those indexed sources from the current source tuple before paying the next spell or reserved protection cost. Include an impossible fixture (four available mana cannot fund a four-mana threat plus one-mana protection) alongside a legal five-mana case; this catches double-spending and return-shape mistakes. Payment feasibility alone does not validate land-entry timing, target legality, spell resolution or hand frequency.

Declare the state domain before enumerating:

- Battlefield size and target, e.g. exactly four lands for UUBB and six for 4BB.
- Actual per-name land inventory and at least two nonbasics on the initial battlefield.
- Each basic's unavailable reserve outside the battlefield. Fetchable count = total inventory − unavailable reserve − battlefield count. Never subtract reserve twice or conjure replacement basics.
- Filter to initially payable states. Counts of nonfunctional initial states are not replacement failures.
- Assume one basic replacement per nonbasic loss, and specify the untap checkpoint, intervening draws/land drops, and whether both post-loss states must pay.

For adaptive adversarial two-loss resilience, implement the quantifiers correctly:

`for every first loss, there exists a first fetch that preserves payment and, for every second loss, there exists a remaining legal second fetch preserving payment`.

The first fetch cannot depend on a second loss not yet chosen. Enumerate distinct nonbasic loss names from the current multiset; repeated losses of the same name are legal only with enough copies. Decrement library inventory on each fetch, and assert `battlefield basic + remaining library basic + unavailable reserve == actual basic inventory` at every checkpoint.

Enumerating bounded inventory-valid multisets may be inexpensive. Otherwise use named explicit fixtures and declare them nonexhaustive. Even an exhaustive enumeration is exhaustive only within the stated battlefield domain, not over gameplay histories. State counts are not probabilities. Success after untap does not establish resilience to replacement ETB tempo, missing land drops, nonreplacement destruction or further losses.

## Verification and evidence hygiene

- Run relevant existing unit tests and retain the result.
- Recheck the exact frozen deck hash and input quantities at completion.
- Hash finalized configs, scripts and reports. Exclude a manifest from its own artifact hash map. Do not hash an actively written log; finalize it first or omit it from the manifest.
- Verify every listed artifact hash after the final run. Avoid rerunning unchanged Monte Carlo jobs merely to refresh metadata where a separate finalization step suffices.
- Finish with a concise summary, exact deck hash, per-cell samples/seeds, explicit domain/omissions, and usable report/config/replay paths. Keep raw traces out of the conversational summary.
