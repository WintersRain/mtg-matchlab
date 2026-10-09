# Deckbuilding guide

The working checklist for every list this project builds or recommends. It
paraphrases Reid Duke's *Level One* course (Wizards of the Coast, 2014–2015)
and the PowrDragn videos summarized in
[`evidence/powrdragn-deckbuilding-handoff.md`](../evidence/powrdragn-deckbuilding-handoff.md).
It ends with rules learned from real losses in this project.

No list is presented until every gate in section 9 has passed.

## 1. Decide what the deck is before choosing cards

Name the deck's job in one sentence: how it wins, on which turn it wants to
be ahead, and what it does in the turns before that.

| Shape | What it does | Construction consequence |
|---|---|---|
| Aggro | Wins before the opponent's cards matter | Cheap threats, reach (burn, evasion), answers aimed at *blockers* |
| Midrange | Defends against faster decks, attacks slower ones | Every card works on offense and defense; card advantage built into permanents |
| Control | Survives, then wins with a few resilient finishers | The fewest finishers that guarantee inevitability; the rest is defense |
| Linear / synergy | Reaches critical mass of one theme, ignoring the opponent | Cuts good off-theme cards; little interaction; easy to sideboard against |

**Linear or midrange test.** Count the good off-theme cards you would have to
cut to go all in. If that number is large and the theme cards are weak alone,
you are building midrange with a sub-theme. Build that honestly instead of
half-committing. A half-linear deck gets neither the critical mass nor the
card quality.

**Speed test for engines** (graveyard, ramp, cheat). Count the enablers you see
by turns 2–3 and what they actually produce. For example, mill 3 in a deck that
is 43% creatures puts about 1.3 creatures in the graveyard. If the payoff then
comes down on curve, the deck is not cheating anything; it is midrange with
expensive cards. Measure this with `matchlab.py draw` before calling a deck
"fast".

Source: Midrange Decks, Linear Strategies, Role Assignment, Inevitability.

## 2. Threats and answers

- Threats win games. Answers only keep you in them. Be proactive by default.
  An unanswered threat rarely loses you the game; an answer with no target
  does nothing.
- Every deck needs some answers. The slower the deck, the more answers it needs
  and the more direct they must be. There is no fixed ratio.
- Prefer answers that are never dead: broad targets, modes, or a useful
  fallback such as burn to the face or lifegain stapled on.
- Choose threat types deliberately:
  - **quick**: cheap bodies;
  - **potent**: a single game-ender;
  - **resilient**: hexproof, indestructible or recursive;
  - **guaranteed value**: an enters effect, haste, a planeswalker, a land that
    becomes a creature.

  Decks with few threats need resilient or guaranteed-value ones.
- One-card effects beat multi-card combinations (auras, equipment, two-piece
  synergies) unless the payoff is enormous.

Source: Threats and Answers, Basics of Card Advantage.

## 3. Card advantage and card quality

- Count net cards. A draw-one replacement is break-even. A permanent that
  leaves a body plus a card is +1. Removal that kills two of theirs for one of
  yours is +1.
- **Virtual card advantage** matters more on a real board. Make their cards
  dead (a big blocker stops many small attackers) and avoid dead cards of your
  own (excess lands, low-impact filler).
- High impact beats incidental value. A pile of 2-for-1s from weak cards loses
  to one unanswered bomb.
- Midrange cannot spend key turns just drawing. Get card advantage that is
  stapled to permanents that affect the board.

Source: Basics of Card Advantage, Midrange Decks.

## 4. Tempo, investment and the curve

- Unspent mana is lost tempo. Have a couple of plays at each cost you expect to
  use early, so most turns spend their mana.
- No universal curve formula exists. Non-aggressive decks should not fill up on
  1–2 drops. A deck must still be able to *act* on turns 1–3: a 1-drop or
  2-drop that matters, or cheap interaction.
- Games have an early stage, where mana is the bottleneck and tempo decides,
  and a late stage, where cards in hand decide. Know which stage your matchups
  are decided in.
- **Investments** (mana creatures, ramp, card draw, enchantments that pay off
  later, impending, sagas) give up board presence now. Each needs enough
  immediate interaction or blockers to survive until it pays off. Count how
  many investments the deck has against how many immediate-impact cards.
- Prefer cards that change the board the turn they arrive: enters triggers,
  haste, removal. Creatures without them pay off one turn late.
- Removal is the cleanest tempo: no setup, and it clears the way or stops an
  attacker. Cheap removal matters most against cheap threats.

Source: Tempo, Tempo and Card Advantage, Investment, Basics of Mana.

## 5. Mana base

### Land count

- Run just over 40% lands as a starting point: 24–25 in 60 for midrange, fewer
  for low-curve aggro, more for control.
- Adjust for nonland mana sources and for mana sinks (section 6).

### Colored sources (60 cards)

| Role of the color | Sources |
|---|---:|
| Can't function without it | 17–18 (19+ to see two in the opener) |
| Main color, needed every game | 14–16 |
| Secondary color | 10–13 |
| Splash | 4–7 |

- Two colors can work on basics. Three colors need nonbasics.
- Every added color raises color-screw risk.
- Build around the most color-demanding early card. A turn-3 `BBG` card sets
  the black count, not the deck's average.

### Tapped lands

- Tapped lands are a tempo cost scaled to the deck's speed. Aggro wants none.
- A slow midrange deck tolerates about eight, and ten to twelve with
  discomfort.
- Play them on turns where you'd waste mana anyway, so the curve should leave
  such turns.

### Choice lands, fetches and pain lands

- A land that makes one color of your choice (a fetch for a single basic type)
  counts as slightly less than a source of each color. For example, four
  count as about three.
- A few pain lands are fine. Past a point, another tapped land costs more than
  a pain land.

### Creature lands

- Creature lands are flood insurance. A spare land becomes a threat.
- They survive sorcery-speed sweepers.
- They let you turn the corner from defense to offense.
- Because flood hurts less, a deck with creature lands can run a land or two
  more, which also reduces screw.
- Treat them as plain lands early. Activate them once spare mana exists.
- In a deck that plays the long game, a strong creature land in its colors is
  close to an automatic inclusion. Account for its tapped entry (above) and its
  colored output.

Validate every list with `matchlab.py mana`. Report land-only numbers for each
colored cost on the turn it wants to be cast, on the play and on the draw.

Source: Basics of Mana, Building a Mana Base, "Creature" Lands.

## 6. Flexibility

- Modal cards, mana sinks, X spells and creature lands raise the floor. Bad
  draws stay playable.
- Take them when they cost little power.
- Good mana sinks are cheap to deploy and stay useful early. Don't add a
  top-heavy card and call it a sink.

Source: Flexibility.

## 7. Sweepers

- Know the format's sweepers and what they spare.
- Don't run a sweeper that kills your own creatures:
  - check its toughness threshold against your own creature list;
  - a symmetric wipe in a creature deck needs a reason, such as your creatures
    surviving it, or the deck being ahead on cards when it resolves.
- Against sweeper decks, diversify threats with planeswalkers, creature lands,
  recursive creatures and value on entry. Hold creatures back instead of
  overextending.
- Unconditional sweepers are strongest in the main deck. Conditional ones
  belong in the sideboard.

Source: Board Sweepers.

## 8. Sideboard

- Plan per matchup before playing: what comes in, what goes out, and that the
  counts match.
- Build the 60 and the 15 together (the "elephant" method): write the ideal list
  for each expected matchup, then split the pool.
- Fix the matchup, not one card that beat you once. Don't bring in a narrow
  answer that is dead against the rest of their deck.
- Don't over-sideboard. Keep the creature count, curve and finishers intact.
  Swap weak reactive cards for better-targeted ones.
- Sideboard card types:
  - answers to their key threats;
  - threat upgrades, such as sturdier bodies against sweepers;
  - threat diversification against control;
  - hate cards, when the target deck is popular.
- Midrange gains the most from sideboarding. Linear decks gain the least.

Source: Sideboard, Sideboard Plans, Choosing Your Deck.

## 9. Gates before presenting a list

Every gate is re-run after **any** swap, however small.

`python3 tools/vet.py LIST` automates gates 3-7 from the Forge card scripts in under a second.
Add `--forge --opponents DIR` to also play 20 Forge AI games per opponent; any matchup under 25% fails the list.
The thresholds are coarse filters. A PASS is the minimum bar, not proof the deck is good.

1. **Plan:** the one-sentence plan from section 1. The linear or midrange test,
   and the speed test if the deck has an engine.
2. **Legality:** format legality, and checked oracle text for every card
   (`sf.py` or the Arena DB). Never write from memory.
3. **Curve:** a count by mana value, plus an *effective* curve. Note
   alternate costs, adventures and impending separately; never alter rules
   mana value.
   - The deck can act on turns 1–3.
   - The 2-drop slot is not padded with filler.
   - Cards hand off well from early to late game.
4. **Mana:** land count, source counts per color against the table, the
   tapped-land count, and `matchlab.py mana` output for each colored cost.
   **Basic-land rule:** the basics alone must be able to cast every card in
   the deck (enough of each basic for the largest single-color requirement,
   such as two Swamps for {B}{B}), plus a little extra. Land destruction and
   effects like Demolition Field otherwise strand a nonbasic-heavy deck.
5. **Interaction:** count cheap answers and the probability of having one by
   turn 2–3. Confirm no answer is dead against the expected field.
6. **Self-harm:** no sweeper that kills your own board. No card dead against
   common opponents, such as a removal spell restricted by creature type that
   the field avoids.
7. **Card advantage and recovery:** count the cards that produce more than
   one card's worth of value. Check what happens when the main plan is
   answered: if the cheap cards do nothing on their own once the payoff is
   removed, exiled from the graveyard, or never shows up, the deck fails. A
   goldfish speed number (how fast the combo assembles with no opponent) does
   not prove the deck is viable.
8. **Swap discipline:** when replacing a card, match its cost and its role
   (ramp, blocker, enabler, answer). Then recheck gates 3–5.
9. **Engine check:** the deck must run in Forge. Any card the engine can't play
   gets an upstream script, or the list doesn't ship.
10. **Evidence:** label a list as untested until games have been played. Judge
   changes over many games, not one bad draw.

## 10. Lessons from this project

These rules were learned from real games and corrections.

- A deck that can't block a 1-drop or 2-drop loses to the format's fast decks.
  Cheap interaction or early bodies are mandatory, not optional.
- Use the strictly better card when one exists. Don't fill slots with
  marginal cards to hit a count.
- Check conditional removal against what the field actually plays. Shoot the
  Sheriff was dead against a deck of outlaws.
- Cutting a card cuts its role. Removing a ramp creature removes ramp, so
  replace the role or re-plan the curve.
- Review losses with full board state. A turn summary without the board can't
  diagnose anything (`matchlab.py review`).
