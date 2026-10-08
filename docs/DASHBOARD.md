# Local bot table

Start from the repository root in WSL:

```sh
python3 dashboard.py serve
```

Open **http://127.0.0.1:8765** on Belladonna. `--port` changes the port;
the server always binds to loopback. No firewall changes or public hosting.

Both seats accept pasted Arena text, UTF-8 text files, captured lists, and
saved lists. About / Name headers are supported. Save and export are independent
for each seat. Imports require 60 main and at most 15 sideboard, preserve zones,
accept printing suffixes, and enforce the existing combined copy-limit rules.
Special formats and commanders remain unsupported rather than approximated.
Format labels do not imply legality checks.

Choose games and a starting seed. The optional multiple-opponent selector runs
seat A against each selected list. Up to ten opponents and fifty games each;
each seed increments by one across the batch. Engine seats alternate within
each matchup when selected, but this does not force play/draw. Stop lets the
current game finish and retains it. Only completed games and ordinary draws
are valid results; errors, timeouts and invalid output are excluded.

The 37 benchmark lists are September 14, 2026 captures, not current meta claims.
For any new tournament/archetype list, an assistant can fetch a public source,
extract the exact Arena list, then use this same import API. Preserve source URL,
source date and format in the deck object. The server does not scrape arbitrary
URLs or invent missing cards/sideboards.

## Direct assistant interface

No per-deck code edits, catalog registration, rebuilds, or manually prepared
deck files are needed. Supply JSON directly to stdin:

```sh
python3 dashboard.py duel <<'JSON'
{"a":{"text":"About\nName Deck A\n\nDeck\n60 Plains\n"},"b":{"text":"About\nName Deck B\n\nDeck\n60 Island\n"},"seed":42}
JSON
```

The basic-only lists illustrate the interface and are not useful matchups.
Use actual supported deck lists. Python callers can call `dashboard.duel(body)`.
Deck objects accept `text`, optional `source_url`, `source_date`, and `format`;
alternatively `selector` resolves a captured list, or `saved` resolves a saved ID.
Missing cards are reported for both seats before Java launches. No substitutions.

For an independent-game series in one loaded JVM, use `python3 dashboard.py series`
with the same stdin deck objects plus `games`, `seed`, `alternate`, and optional
`snapshots`. The returned session includes per-game summaries. In the dashboard,
check **Keep engine loaded between games** or pass `reuse:true` to `/api/batch`.
This option is off by default. Each matchup starts its own loaded process.

While the server runs, POST JSON to:

- `/api/validate`: `{a:deck,b:deck}` audits both inputs.
- `/api/save`: a text deck object saves it locally and returns `saved` ID.
- `/api/batch`: `{a:deck,b:deck,games:1,seed:42,alternate:true}` queues games.
  Replace `b` with `opponents:[deck,...]` for multiple matchups.
- `/api/stop`: `{id:batch_id}` requests stop after the current game.

GET `/api/decks`, `/api/batches`, `/api/history`, `/api/live`, and
`/api/replay/<run_id>` provide catalog, progress, run summaries, live state,
and recorded engine observations.
Mutations require JSON, loopback Host, and same-origin browser requests.

## Evidence and viewer limits

Saved lists and immutable batch requests are under `runtime/dashboard/`.
Runs use the existing `runtime/runs/<id>/` isolation, lock, profile cleanup,
pin, privacy-patched JAR, hashes, deadlines and bounded-log checks. Imported
Arena text is retained as `audit/seat-a.arena.txt` and `seat-b.arena.txt`, alongside
engine DCKs, card-script hashes, command, raw log and summary. Existing historical
inputs and run outputs are never overwritten.

The viewer follows actual Forge events while a game runs and replays recorded
board state afterward: life, turns/phases, both hands, battlefield, graveyard,
exile, command zone, library counts, stack, combat and action history. This is a
spectator view with both hands visible. It does not expose library order.
Playback changes the displayed observation, not the engine's speed or decisions.
Historical logs without snapshots retain their real text replay with an explicit
unavailable-board message. See [BOARD_VIEWER.md](BOARD_VIEWER.md) for the event
observer, lossless zone-delta protocol, portable patch and build requirements.

## Card overlays and verification

The missing upcoming-card overlays are in `forge-resources/cardsfolder/upcoming/`.
Install them once with `python3 tools/install_card_resources.py`; the installer
checks the source pin, reports hashes and refuses conflicting existing scripts.
It adds Way of the Paradox, Way of the Mentor and Simulacrum Shaper without
substituting other cards. Forge loads card resources at startup. Deck imports
do not require Java rebuilds. The observer patch requires a one-time pinned JAR
build; it does not change card rules or AI decisions.

Run `python3 run_engine_checks.py` for native Java rule fixtures against the
actual local JAR. The two suites currently cover 51 assertions, including the
three overlays and bounded interaction checks for Ajani Unrelenting,
Innkeeper's Talent, Ancient Cornucopia and The Mind Stone. The fixtures exercise
real native effects, triggers and costs; they are not exhaustive rules proof or
full games. The fixtures use artificial starting positions explicitly.

The local Ajani investigation preserved the proposed 60/15 and only changed its
About / Name header to Ajani's Nine Lives. Twelve complete preboard games with
recorded native board state are retained locally, four each versus curated
aggro, curated control and a no-threat 60-Plains proxy. That proxy is a full
two-player engine game with a passive opponent, not true solitaire goldfish.
Small samples describe this engine and Default AI; they are not human win rates
or evidence of optimal piloting. Local records are in
`runtime/ajani-game-series.json` and `runtime/ajani-observed-games.json`, with
individual commands, source hashes, raw logs and summaries under `runtime/runs/`.
They are private runtime evidence, not fresh-checkout dependencies.

## Runtime limits

The default launches a fresh Java process per game. Optional reuse retains the
loaded card database and static caches, while creating a fresh Match, players,
AI controllers and snapshot observer for every game. It reseeds before player
registration, using starting seed plus game index; alternating logical seat order
is independent of the native first-player coin choice. It does not use Forge's
ordinary ongoing-match `-n` behavior or sideboarding policy.

Authoritative native BEGIN/END markers route each game's raw log and immutable
audit into its own `runtime/runs/<id>` directory. Session startup/footer and
provenance remain under `runtime/reuse/<id>`. The runner validates marker seed,
game number and seats, bounds each game's output at 8 MiB, and applies a 300-second
deadline to initialization, each game and gaps between games. A failed native
game, timeout, malformed lifecycle or overflow aborts reuse; unstarted games are
explicitly skipped. Stop is checked by the native loop at a game boundary.
The existing live/replay API reads each child's actual state independently.

A local paired benchmark of three supported aggro-versus-midrange seed/seat
combinations completed in 24.40 seconds with fresh processes and 12.46 seconds
in a reused process, including initialization. All three pairs had matching
winners and canonical ordered action traces after IDs, timing and native game
number normalization. `runtime/reuse-benchmark.json` preserves the measurements
and comparisons. This bounded result does not prove universal equivalence across
all Forge static caches, decks or future engine versions. The process mode and
seed policy are explicit in every reused-game summary.

Default AI competence for the new interactions has not been established.
Observed games execute the card plan, but the generic pump heuristic evaluates
existing creatures and does not account there for Unrelenting's activation-created
Cadet; generic discard logic also tends to wait until MAIN2. These are grounded
piloting limits rather than unsupported rules or proof that different play wins.
Local per-game observations and exact loss log references are recorded in
`runtime/ajani-bot-behavior.json` and `.md`.

The additional eight preboard games use exact September 14 benchmark IDs 36
(Izzet Spellementals), 34 (Orzhov spells), 17 (Golgari Roots), and 29 (Azorius
control). Archetype names are analyst descriptions of the actual contents.
Two games per list alternate engine seats; source URL, date, qualification,
deck hashes and full run summaries are retained in
`runtime/ajani-benchmark-games.json`. These archived ranked-success lists are not
claims about October tier rankings or metagame share.
