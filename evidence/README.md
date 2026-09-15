# Curated source evidence

The four JSON files plus `opponents/README.md` were copied from the completed
`/tmp/mtg-opponents` research handoff. No raw HTML, bulk Scryfall responses,
images, or downloaded Java dependencies were copied here.

`opponents/README.md` and `provenance.json` are preserved source documents:
references to raw HTML, collection responses, downloads, and `/tmp` paths
refer to the original research workspace, **not files shipped in this repo**.
Retained files are provenance, per-card legality evidence, exact structured deck
lists, and the small Arena-printing-alternates response. These are a dated
research snapshot, not an automatic current-legality service.

`doom-provenance.json` explicitly distinguishes the prior review's legality
claim from an independently verified, retained per-card legality audit (not
available for Doom in this handoff). The Doom input is copied byte-for-byte.
The harness audits Forge scripts for every main/side name in all five lists.
