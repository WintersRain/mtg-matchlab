# PowrDragn deck-building guidance — handoff for Hermes

Prepared for Winter's `mtg-matchlab` project from three requested video transcripts, reviewed September 15, 2026. This is a synthesis of the creator's advice, followed by an explicitly labeled application to this project. It is not a new deck recommendation or current metagame/legality audit.

## Core decision rule

Build around how the deck actually wins and the turns on which it needs to act. Include a card because it improves that plan or addresses an evidenced weakness at an acceptable cost. Shared keywords, a favorite card, or a theoretical interaction are insufficient. Every addition needs an explicit cut and an explanation of the tradeoff.

## 1. Structure follows the game plan

From **Secret Formulas for Building Every Magic the Gathering Deck**:

| Archetype | Rough land baseline | Creature/noncreature guidance | Approximate average nonland cost |
|---|---:|---|---:|
| Aggro | 22 | Often 23–28 creatures; remaining slots are other spells | Around 2 |
| Midrange | 24 | Example starting split: 25 creatures / 11 other spells | 2.5–3 |
| Control | 26–27 | Often few creatures, roughly 4–7 or even zero; remaining slots are other spells | Around 3 |

These are starting heuristics from the decks discussed in the video, not quotas or universal optimal ratios. Choose counts that total the intended deck size; the video's independently stated ranges are not a menu whose endpoints can all be combined. Its own examples include creature-heavy midrange and control lists outside these ranges. Do not force combo, reanimator, or another specialized engine into a generic template.

- Classify by winning pattern and game length, not creature count alone. A low-curve sacrifice/recursion deck can still be midrange.
- Count **functions**, as well as card types: creatures may supply removal, card draw, or mana; noncreature cards may supply bodies and win conditions.
- Land count supports sequencing and multiple actions in one turn, not just the most expensive card. Control needs land drops to cast a spell and hold interaction; aggro needs enough mana to deploy pressure and clear blockers.
- Audit early plays even when the deck plans to win late. A high average cost can expose a deck that cannot participate early enough.
- The creator adjusts costs for the ways cards are normally used: alternate costs, free opening effects, reanimation, adventures, and modal spells. **Keep this estimated deployment cost separate from rules-defined mana value.** Label the assumptions; do not change rules calculations for discover or other mana-value checks.
- Calculate an average over nonland **copies**, not distinct card names. An average is a diagnostic, not a substitute for the curve, colored-source requirements, or reliable access to alternate casting routes.

Source anchors: [6:48 aggro baseline](https://www.youtube.com/watch?v=3suvepBZ9LI&t=408s), [15:03 midrange baseline and averaging](https://www.youtube.com/watch?v=3suvepBZ9LI&t=903s), [22:15 control and multiple-spell turns](https://www.youtube.com/watch?v=3suvepBZ9LI&t=1335s), [24:00 summary](https://www.youtube.com/watch?v=3suvepBZ9LI&t=1440s).

## 2. Fix measured weaknesses without dismantling the deck

From **Fixing These Deck Problems Will Get You More Wins**:

- Identify a recurring problem before prescribing an answer. Occasional losses in an otherwise favorable matchup do not automatically justify extra dedicated slots.
- Evaluate answers in the context of the engine. A cheap defensive card can be counterproductive if it becomes an unwanted discover hit. An attractive four-drop can damage a deck whose early one-drops and wide attacks are essential.
- Every proposed swap must account for what disappears: early pressure, bodies, removal, mana, card advantage, or synergy density. An upgrade in isolation may be a downgrade in the full list.
- Prefer an answer that remains useful outside its target matchup when the deck supports it. A creature, artifact, or flexible spell can address the same problem but fit very different decks.
- Timing matters. An engine that produces value after the deck's intended finishing turn may be irrelevant despite matching its keywords.
- Separate BO1 main-deck needs from BO3 sideboard choices.
- Accept some bad matchups when fixing one would substantially weaken several others. Optimize against the opponents actually faced rather than trying to answer everything.
- Avoid purposeless tinkering with a functioning list. Make changes to test a concrete improvement, not just to make the deck look different.

Source anchors: [0:56 overloading answers](https://www.youtube.com/watch?v=gwupFxHb3aw&t=56s), [4:05 cuts and curve](https://www.youtube.com/watch?v=gwupFxHb3aw&t=245s), [7:18 keyword synergy versus timing](https://www.youtube.com/watch?v=gwupFxHb3aw&t=438s), [9:06 matchup answers](https://www.youtube.com/watch?v=gwupFxHb3aw&t=546s), [13:42 accepting tradeoffs](https://www.youtube.com/watch?v=gwupFxHb3aw&t=822s).

## 3. Know when to shelve an idea

From **When To Give Up On A Card Or Deck** (members-only):

- Judge iteration by changed outcomes: are the same matchups difficult, games ending the same way, and resource problems recurring? Feeling closer is not the same as demonstrable progress.
- After several materially different approaches fail to improve the same structural weakness, consider shelving the idea. The creator's references to hours/evenings and numbers of revisions are personal heuristics, not statistical stopping rules.
- Preserve the list and the lessons. A future card, metagame change, outside perspective, or discovery in another deck can make it worth revisiting.
- Distinguish enjoyment of brewing from competitive climbing. Continued experimentation is reasonable when that is the user's objective.
- Do not make originality a requirement. Borrow successful structures and adapt them; give credit when using a known source.
- A card can be interesting yet unsuitable for the current format or environment. Protect time, cash, and wildcards, particularly when an expensive craft serves only one speculative deck.

Source anchors: [1:13 iteration and failure](https://www.youtube.com/watch?v=gVbmmvFGV6A&t=73s), [2:53 stalled results](https://www.youtube.com/watch?v=gVbmmvFGV6A&t=173s), [3:47 saving and revisiting ideas](https://www.youtube.com/watch?v=gVbmmvFGV6A&t=227s), [4:29 originality](https://www.youtube.com/watch?v=gVbmmvFGV6A&t=269s), [9:12 resource costs](https://www.youtube.com/watch?v=gVbmmvFGV6A&t=552s).

## Application to mtg-matchlab (Codex synthesis, not a claim made in the videos)

The README identifies the supplied Doom list as an immutable 60-card baseline with no supplied sideboard. It uses Forge Default AI against Mono-Green Landfall, Dimir Midrange, 4c Control, and Bant Airbending Combo. Preserve that baseline and its hashes; proposed revisions need separate versioned inputs through the project's supported workflow.

1. State Doom's intended winning sequence, stabilization turns, and indispensable engine pieces using verified card text. Establish whether Winter's priority is competitive performance, retaining Doctor Doom, budget, or experimentation from the existing Hermes conversation; do not infer it from these videos.
2. The baseline contains **26 lands**, counted directly from `decks/doom.txt`. That exceeds the video's rough midrange starting point; it is a question to investigate, not evidence to cut lands. Check colored sources, tapped-land timing, early interaction, double-spelling, and late mana uses before proposing a change.
3. Diagnose each opponent separately. Keep mana failures, lack of early interaction, weak closing pressure, engine inconsistency, and pilot/implementation failures distinct. Do not report those as observed problems until logs or real games establish them.
4. For each candidate revision, record the exact adds/cuts, the targeted failure, the curve/source/engine tradeoffs, and the result that would justify retaining or reverting it.
5. Compare with the baseline under comparable recorded conditions. Report valid sample sizes and uncertainty. Treat smoke games as execution checks, not matchup estimates; exclude timeout/error/invalid/log-limit runs from valid game outcomes according to the README.
6. Forge measures the deck/AI/engine combination. These are preboard games, not sideboarded BO3 results or human ladder win rates. Check suspicious interactions/pilot decisions before attributing a loss to deck quality. The four selected opponents are a test panel, not an established frequency-weighted ladder population.
7. If repeated justified changes fail, save what was learned and identify a specific condition for revisiting the build. Do not spend Winter's resources simply because the project has already consumed time.

Suggested change-review record:

> Objective / observed problem / evidence and sample size / exact adds and cuts / why the replacement fits the plan / mana and curve consequences / expected matchup gains and losses / test conditions / observed result / retain, revert, or shelve.

## Source handling

All three sources are PowrDragn videos supplied by Winter. Transcripts can contain automatic-caption errors, especially card names and numbers. This handoff intentionally avoids turning uncertain spoken card examples into recommendations. The videos' historical metagame, card-strength, and rotation statements are not current facts; verify those separately when making actual deck changes. The numerical templates are heuristics, not validated probability models.

Full local transcripts are available from WSL at:

- `/mnt/e/VS Code Projects/YouTube-transcripts/3suvepBZ9LI.txt`
- `/mnt/e/VS Code Projects/YouTube-transcripts/gwupFxHb3aw.txt`
- `/mnt/e/VS Code Projects/YouTube-transcripts/gVbmmvFGV6A.txt`

No deck edits or simulation runs were performed for this handoff.
