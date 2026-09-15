# Current Standard tournament opponents

As of **2026-09-15**. Retrieved 2026-09-15T17:57:44.258186+00:00. Live sources contain September 2026 results through September 15; there is no future-data gap in the selected lists.

All four lists are exact published **60 main / 15 sideboard** configurations; every card is Standard-legal in the retrieved Scryfall data. No personal-dislike edits. Arena-style headers were added, but names and quantities were not changed.

| Role | Published representative | Event date/result | Goldfish 30-day share | Import |
|---|---|---|---|---|
| aggro | [Mono-Green Landfall — NeoKipper](https://www.mtggoldfish.com/deck/7951774) | 2026-09-12: 8th, 5-2 | 18.3% (250 decks; #1) | `aggro.txt` |
| midrange | [Dimir Midrange — kthanakit26](https://www.mtggoldfish.com/deck/7953795) | 2026-09-13: 2nd, 5-3 | 9.7% (133 decks; #3) | `midrange.txt` |
| control | [4c Control — Lamario Harris](https://www.mtggoldfish.com/deck/7952949) | 2026-09-12: record only, 5-0 | 6.4% (88 decks; #4) | `control.txt` |
| combo | [Bant Airbending Combo — VampireDiaries](https://www.mtggoldfish.com/deck/7949488) | 2026-09-11: 14th, 4-2 | 1.8% (25 decks; #14) | `combo.txt` |

## Selection and evidence

### Aggro: Mono-Green Landfall
Most represented Goldfish archetype; proactive creature/landfall pressure with explosive scaling, rather than a pure low-curve red aggro deck. Recent Challenge top eight. This is an aggro/ramp-combo hybrid, intentionally not a claim that all its games resemble traditional aggro.
- Event: [Standard Challenge 32](https://www.mtggoldfish.com/tournament/66540); 3 days old at cutoff.
- Original source linked by Goldfish: https://www.mtgo.com/decklist/standard-challenge-32-2026-09-1212854079
- Exact downloadable list: https://www.mtggoldfish.com/deck/download/7951774

### Midrange: Dimir Midrange
Highest represented explicitly midrange archetype in Goldfish snapshot; recent Challenge finalist. Evasive threats, interaction, Kaito and Enduring Curiosity support tempo/value midrange. MTGTop8 groups such decks as Dimir Aggro; that taxonomy is not a strategic correction.
- Event: [Standard Challenge 16](https://www.mtggoldfish.com/tournament/66580); 2 days old at cutoff.
- Original source linked by Goldfish: https://www.mtgo.com/decklist/standard-challenge-16-2026-09-1312854097
- Exact downloadable list: https://www.mtggoldfish.com/deck/download/7953795

### Control: 4c Control
Most represented explicitly control-labeled archetype in Goldfish snapshot; fresh undefeated paper event list. Removal, sweepers, Tablet/Stock Up and Jeskai Revelation define the defensive resource plan. Published 5-0 is a match record, not a verified first-place finish.
- Event: [ReCQ - Standard - Baltimore - Saturday - 3:00 pm](https://www.mtggoldfish.com/tournament/66561); 3 days old at cutoff.
- Original source linked by Goldfish: https://melee.gg/Tournament/View/445395
- Exact downloadable list: https://www.mtggoldfish.com/deck/download/7952949

### Combo: Bant Airbending Combo
Optional dedicated combo coverage, not a claim to be a top overall deck or the most prevalent combo. Recent positive-record Challenge list; selected rather than the archetype page average or an older winner. MTGTop8 separately classifies Bant Airbending under Combo (1%). Reanimator is more prevalent in its taxonomy (5%).
- Event: [Standard Challenge 32](https://www.mtggoldfish.com/tournament/66502); 4 days old at cutoff.
- Original source linked by Goldfish: https://www.mtgo.com/decklist/standard-challenge-32-2026-09-1112854067
- Exact downloadable list: https://www.mtggoldfish.com/deck/download/7949488

## Metagame interpretation
[Goldfish](https://www.mtggoldfish.com/metagame/standard) defaults to **30 days**, verified from the selected HTML option. These are publisher sample shares, not Arena queue shares or win rates. [MTGTop8](https://www.mtgtop8.com/format?f=ST) uses **last two weeks, 480 decks**: Mono Green Aggro 12%, Dimir Aggro 10%, 4/5C Control 8%, Bant Airbending 1%. Its category boundaries differ, particularly Dimir Aggro versus Dimir Midrange and Izzet Control versus Spellementals; do not merge the percentages.

## Verification
- `decks.json`: exact per-zone names/counts. `legality.json`: name-by-name Scryfall links/status, counts and copy-limit checks.
- `scryfall-collection-*.json`: raw paced collection responses using identifying User-Agent and JSON Accept header. No missing names, illegal cards or nonbasic copy-limit violations.
- `scryfall-arena-alternates.json`: confirms Arena printings for four names whose initially returned printing was paper-only. All other collection records include Arena. This is availability evidence, not a performed client import.
- `*.download.txt`: unchanged publisher downloads. `aggro.txt`, `midrange.txt`, `control.txt`, `combo.txt`: Arena headers plus those exact lists.
- Deck/event/metagame HTML and extracted source text are retained alongside provenance.

## Limitations
- No native web-search/browser tool was exposed. Used live HTTP retrieval of known deck/event/metagame sources.
- Sources are genuinely dated through September 15, 2026; selected tournaments are September 11-13, not fabricated future results. No future-event results used.
- MTGDecks returned HTTP 403. Melee upstream control-event URL returned HTTP 403.
- MTGO aggro upstream redirected to decklist index; midrange/combo upstream exposed empty JS shells through static HTTP. Exact lists/results verified against Goldfish download, deck page and event page, not independently re-parsed from upstream.
- 30-day metagame share lags the freshest event changes; role-specific representative is not proven single strongest configuration. Recent BRG/Jund results are visible but not substituted for the leading explicitly midrange-labeled Dimir shell.
- Optional Bant combo is lower prevalence and its selected finish is 14th, not a top-eight deck.
- Card legality is Scryfall live status, not independent official B&R/rotation audit. Arena has name-based imports here; import execution was not available.
- No personal card-dislike filters or substitutions applied; published main and side quantities preserved exactly.
