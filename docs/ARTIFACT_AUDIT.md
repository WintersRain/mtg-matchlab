# Artifact resource audit

`artifact-audit` adds exact-printing deck inspection and explicit resource-sequence
checks. It is not Forge, an opening-hand pilot, or a full Magic rules engine.
No network call occurs during analysis: Oracle identity, legality, and Arena
platform evidence come from a dated, replayable JSON snapshot.

```sh
python3 matchlab.py artifact-audit examples/artifact-demo.arena.txt \
  --oracle examples/artifact-oracle.json \
  --scenarios examples/artifact-scenarios.json
python3 -m unittest discover -s tests -p test_artifact_audit.py -v
```

The demonstration is intentionally a small public mechanism fixture, not a legal
or recommended deck. Private user decks belong in ignored local `runtime/` data.
Use `--format standard` for an explicit *assessment*; the export itself does not
establish the user's chosen format. Lists above 60 are preserved, not cut; the
existing curated Forge parser and its exact-60 contract are unchanged.

## Identity and evidence

Every nonblank card line requires `COUNT Name (SET) collector`. Supported zones
are `Deck`, then optional `Sideboard`. Unsupported headings and unknown printings
fail. Exact printing name must equal its full Oracle name or its **front face**.
The shared `Soul Tether` spell face is not a valid alias for either creature.
Preparations are one card and use front mana value for the printed curve, not the
sum of both costs. Card-type totals overlap (artifact creatures count in both).

Oracle bundles have `schema_version: 1` and `records`, each with `source`,
`retrieved_at` (ISO timestamp), and the Scryfall `card` object. The checked example
retains public identity/rules/printing/platform/legality fields, not private deck
quantities. Fresh captures can use full Scryfall objects; nonrules image/art metadata
does not alter the rules fingerprint. Duplicate printing entries fail closed.

The report hashes exact input text, bundle, scenario input, and each card's rules.
Legality is explicitly dated. `games: [arena]` and `arena_id` are separate evidence:
missing a printing ID does not establish card unavailability. No Arena import is
performed. No independent banned-list update is implied by cached legality.

The artifact package counts **artifact spells**, not token creation. Its exact
hypergeometric availability calculation counts a Robot plus another artifact,
including two Robots. This is unordered draw availability without mulligans or
Arena hand smoothing; it says nothing about mana, sequence, survival, or wins.

## Scenario contract

A JSON list contains named objects with `setup` and `actions`.
Setup declares `permanents` (each unique `id` and supported `name`), optional
`hand` names, `mana` color symbols, and `library_basics` inventory (Forest/Mountain).
Permanent flags `new`, `tapped`, `prepared`, and `pending_etb` are optional booleans.
`new` means not controlled continuously since the beginning of this turn; it does
not mean newly made a creature. Setup defaults to existing, untapped permanents;
Crafter is prepared, Prodigy is not, and Tethermage has one pending ETB. Override
flags explicitly for other checkpoints. Initial resources are *premises*, not
proof that an opening hand could reach this position.

All actions occur in one own main-phase window with the stack otherwise empty.
Supported triggers resolve without opponent responses. `next_turn` clears mana
and temporary abilities, untaps, ages permanents, and prepares Prodigy at upkeep.
It neither draws nor supplies a land drop. Explicit mana tapping is necessary;
no source is automatically double-used. One failed action rolls back completely,
returns `rejected`, and stops that scenario. Rejection can be a useful expected
result, so the CLI remains exit 0 for a valid report with rejected lines.

| Operation | Required arguments | Scope |
| --- | --- | --- |
| `tap_mana` | `id`, `color` | Supported lands, Heartwood, restricted Crafter |
| `cast` | `name`, new `id` | Nine supported front spells, explicit hand and mana |
| `tether_etb` | `id`, optional `land` | Consume one pending ETB; sacrifice land for two tapped Heartwoods |
| `tether_pump` | `id`, two `artifacts` IDs | Tap two distinct untapped artifacts for two counters |
| `prepare_cast` | prepared creature `id` | Pay Soul Tether from exile; unprepare; make Heartwood |
| `puppet_sac` | `id`, `sacrifice`, `mode` | Pay one; sacrifice another artifact; counter plus one temporary keyword |
| `robots_haste` | `id` | Pay R and tap Robots; current creature tokens gain haste |
| `lander_fetch` | `id`, `basic` | Pay two, tap and sacrifice Lander; consume library basic, enter tapped |
| `die` | creature `id` | Declared death; Rover both-player Landers, Solemn draw owed, Aerid Heartwood |
| `crafting_return` | none | Pay 4G; return one graveyard Crafting to hand |
| `aerid_pump` | `id` | Pay six; create Heartwood before counting artifacts; record power bonus |
| `next_turn` | none | Bounded turn transition described above |

`cast` supports Tethermage, Puppet Crafting, Puppetbeast, Prodigy, Robots, Solemn,
Aerid, Edge Rover, and Crafter. Crafting requires `target`; Tethermage can select
`land`; Solemn can select `basic` (otherwise decline its optional search).
Freshly cast Robots does not trigger itself; previously controlled Robots trigger
on artifact **casts**, including another Robots. Token entry never substitutes for
a cast. Soul Tether and Puppet Crafting are not artifact spells.

Summoning sickness restricts a creature's own tap-symbol ability, including a
newly controlled Heartwood animated by Crafting. It does not prevent tapping that
creature to pay Tethermage's tap-two-artifacts cost. Heartwood retains its mana
ability when animated. An older Heartwood is not made summoning sick by animation.
Crafting stays attached; sacrificing its bearer also puts the Aura in the graveyard.

Unknown operations, unsupported spell effects, or changed Oracle fingerprints
reject. The public snapshot is the reviewed rules baseline: a rules change needs
an explicit implementation/fixture review, not an automatic rebind. In particular,
Vibrance's spend-sensitive evoke, combat, fight damage, bargain, opponent responses,
replacement effects, arbitrary removal/layers, and duplicate-legend choices are
not simulated. Draw triggers are recorded as owed cards, never invented draws.
Aerid's power bonus is an event, not a combat outcome. Do not interpret a resolved
scenario as a recommendation, opening probability, or match prediction.

Rules sources: [Reality Fracture release notes](https://magic.wizards.com/en/news/feature/reality-fracture-release-notes)
and [Edge of Eternities release notes](https://magic.wizards.com/en/news/feature/edge-of-eternities-release-notes),
plus printing-specific Scryfall URLs and retrieval times in the Oracle fixture.
