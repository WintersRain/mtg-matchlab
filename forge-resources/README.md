# Reviewed card resource overlays

Install with `python3 tools/install_card_resources.py` from the repository root.
The installer checks the pinned Forge source commit and refuses to overwrite a
different resource. Forge reads the resources at initialization; these additions
do not require rebuilding its JAR or changing the runner for each deck.

The three additions are Simulacrum Shaper, Way of the Mentor, and Way of the
Paradox. They use existing Forge primitives: ChangeZone, Draw, Empower,
LifeGained, PutCounter, AbilityCast, GainLife, and an end-of-turn Effect granting
one additional land play per resolved trigger. Simulacrum's enters search is
optional; its death draw is mandatory. Mentor applies one counter per life-gain
event to every controlled planeswalker, not one per point of life. Paradox
triggers on activated loyalty abilities, including abilities from other cards;
each resolution separately grants its land allowance for the rest of that turn.

Rules references: [Reality Fracture official release notes](https://magic.wizards.com/en/news/feature/reality-fracture-release-notes)
for Mentor and Empower. Exact identities and all three Oracle texts were checked
against the supplied exact-printing Oracle bundle and installed Arena identity
capture (FRA 113/208/267). Private input files remain outside this resource
package. Native engine regression checks live in `engine_checks`.

Script support is separate from full-game correctness and AI competence. Engine
checks are bounded scenarios, not exhaustive Magic rules verification or matchup
win-rate evidence. Goldfish/matchup reports must retain exact decks, seeds,
resource and JAR hashes, and explicitly state the game/AI mode.

Bounded engine verification: `python3 run_engine_checks.py` executes both native
Java fixtures under an isolated profile and the normal repository run lock.
The new-card fixture contains 27 assertions; the companion existing-card
fixture contains 24. Together they cover the central Ajani/Talent/Paradox/Mentor
loyalty/counter/life/Cadet ordering plus Cornucopia's multi-color life event.

AI limit: this pin has no dedicated Empower AI mapping. Mandatory Empower
triggers resolve in these checks using the inherited card chooser, and Forge
prints a warning. This establishes effect execution, not a specialized Empower
strategy or optimal choice among multiple Jace tokens. No engine Java changes
were required for these three resource scripts.
