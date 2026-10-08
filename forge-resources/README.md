# Card resource overlays

Install with `python3 tools/install_card_resources.py` from the repository root.
The installer checks the pinned Forge commit and refuses to overwrite a different
resource. Forge reads card scripts at initialization; no JAR rebuild is needed.

## Provenance: upstream official scripts only

Every file here is an **unmodified copy of the official Card-Forge script** from
`https://github.com/Card-Forge/forge` `master`, retrieved 2026-10-07, for cards
newer than the engine pin (`b88dbd3e`). They replaced earlier hand-written
scripts. Hand-written Flourishing Grapple was demonstrably wrong: its
"loses all abilities" half did nothing at this pin.

Rules for this directory:

- Do not hand-write card scripts. If upstream has a script, copy it verbatim.
  If upstream has none, the card is unsupported: say so instead of inventing one.
- Changes to *existing* pinned scripts are patches in `../patches/`, never files
  here. `garruk-origin-battlefield.patch` restricts Garruk, Veiled Butcher's
  exile replacement to creatures dying from the battlefield (upstream master
  still lacks `Origin$ Battlefield`, so opposing discards were mis-handled).
- An upstream script can depend on engine features newer than the pin. Every
  overlay card needs a check in `../engine_checks/` that asserts its Oracle text.

## Verification

`python3 run_engine_checks.py [EXTRA.java ...]` compiles and runs the tracked
native fixtures (plus any private per-deck fixtures passed as arguments) under an
isolated profile and the normal run lock. These are bounded scenarios that check
effect execution against Oracle text, not exhaustive rules verification, AI
competence, or matchup evidence.

Fixtures that bypass casting must mirror what the stack does: call
`AbilityUtils.handleRemembering(sa)` before `resolve(sa)` for scripts using
`RememberTargets` (e.g. Flourishing Grapple).

AI limit: this pin has no dedicated Empower AI mapping. Mandatory Empower
triggers resolve using the inherited card chooser and Forge prints a warning.
