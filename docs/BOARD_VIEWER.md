# Actual engine board viewer

The local dashboard can follow a running Forge bot game and replay recorded
snapshots. This is a spectator view: both hands are visible. Libraries expose
counts only, never their order.

The pinned Forge desktop entrypoint subscribes a synchronous observer to its
actual game event bus when `MATCHLAB_SNAPSHOTS=1`. It writes newline-delimited
`MATCHLAB_SNAPSHOT` JSON to stdout and flushes after each meaningful event.
Priority, mana-pool and combat-update chatter are omitted. No RNG calls,
delays, game decisions or reconstructed actions are added.

Each version-1 frame records game/sequence, elapsed capture seconds, event type,
turn, phase, active player, player life/poison, actual zone contents and card
identity/tapped/token/power/toughness/counters/owner/controller, library counts,
stack descriptions, actual attacking/blocking and card type flags, native
land-play allowances/plays this turn, and newly added actual Forge log entries.

Unchanged board/stack/turn/phase with no log delta is suppressed. First and final
frames set `delta:false` and contain all zones; intermediate frames set
`delta:true` and include only changed exact zone values. A missing zone explicitly
means unchanged from the preceding supplied frame for that game/player id.
The API materializes this declared lossless delta stream into complete frames;
it never derives cards or state from log text. This compression preserves actual
state changes while preventing repeated full graveyard/hand copies from flooding
the runner's unchanged 8 MiB raw-output limit. Explicit empty arrays clear zones. Event snapshots
may show intermediate states during a resolving spell; they are observations
at engine event boundaries, not claims that each frame is a priority window.
A final frame is emitted when simulation returns. Snapshot errors are reported
as `MATCHLAB_SNAPSHOT_ERROR`; games still continue, but a missing/failed viewer
must not be reported as a complete trace.

The dashboard polls the loopback `/api/live` endpoint once per second. Simulation
runs at engine speed; replay playback controls only the displayed recorded frame.
Scrubbing or playback turns off live following. Text card tiles show actual
engine identities and state, not fabricated artwork or animations. Historical
games without snapshot instrumentation retain their actual action-log replay and
explicitly display that board snapshots are unavailable.

The instrumentation lives in the ignored pinned vendor checkout, so its portable
patch is `patches/live-snapshots.patch`. Apply it after the privacy patch and build
the same pinned desktop JAR. Preserve pre-existing local edits when applying.


## Reused engine sessions

The optional independent-game reuse mode creates a new observer for every
fresh Match. Its sequence, prior zone snapshots, deduplication state and action
cursor start cleanly. Native BEGIN/END markers contain the actual per-game seed,
game number and logical deck order. The Python runner routes their observations
into separate child runs, so the UI follows the current game and historical
replays never join one game's state to another. Failed sessions cannot continue
to a later game. Reuse is opt-in; see DASHBOARD.md for limits and paired evidence.
