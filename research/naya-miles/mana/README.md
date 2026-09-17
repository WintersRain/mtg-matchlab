# Naya Miles: mana-only recommendation

User baseline: `../user-export.txt` (60 main, 7 side). All 36 nonlands and all sideboard cards preserved, including one Restoration Magic and one Defend the Rider. Default Forge player deck unchanged. Proposed land change, not claimed applied or full-game validated.

## Recommended 24

```
3 Forest
3 Plains
2 Mountain
4 Hushwood Verge
3 Thornspire Verge
2 Sunbillow Verge
2 Inspiring Vantage
2 Temple Garden
2 Stomping Ground
1 Sacred Foundry
```

OUT from supplied main: 7 Forest, 6 Plains, 3 Mountain. IN: the 16 nonbasics above. Seven sideboard cards unchanged, not silently expanded to fifteen.

Eight basics and five shocklands. No mandatory tapped land; Inspiring Vantage enters tapped after the third land. Shocks may enter untapped at two life each; the tests below are not cumulative life predictions. Verge secondary colors require the stated basic land types; other Verges do not enable them. Basic Forest/Plains/Mountain and shocklands supply types. Potential sources: 14 G, 14 W, 12 R, counting enabled Verge secondary colors; not equivalent to unconditional early sources. Three colors plus GG/WW within 24 lands retains a genuine consistency cost.

Basic floor for this proposal: Forest 3, Plains 3, Mountain 2. GG matters for Ouroboroid and sideboard Tyvar; WW matters for Smile, Restoration's top tier, and Jennifer's transformation. Red single pips matter for Squelcher and RW threats. With one of each basic drawn and not yet in play, the remaining fetchable basics can still supply GG/WW/R collectively. This does not prove arbitrary boards survive unlimited destruction.

## Evidence

Existing `analysis_tools.compare`, 500 samples per configuration, seeds 9162026/9162027, 8 target tests per configuration. Run `python research/naya-miles/mana/run_research.py` from repo root. The tool optimizes isolated target feasibility with perfect lookahead, on the play, no mulligans or hand smoother, target externally available, no earlier spell payments. Samples are unpaired across configurations. These are **not actual full-curve play rates or win rates**.

- T1 G: 71.6% placeholder -> 80.0% recommendation.
- T1 W: 66.4% -> 77.6%.
- T2 Miles: 74.0% -> 83.6%.
- T2 Academic: 39.6% -> 68.2%.
- T3 Lightning: 43.4% -> 73.8%.
- T3 Tyvar: 43.2% -> 64.0%.
- T4 Ouroboroid: 42.0% -> 55.0%.
- T5 Smile: 31.2% -> 44.8%.

These unconditional tests include missing the required number of lands. They do not promise turn-five Smile. No blanket mana/performance pass asserted.

Two-hit basic-replacement stress test: enumerate eligible five-land multisets with actual copy limits; remove two nonbasics, replace with basics actually remaining, untap, and check each of 3GG, 3WW and 1RW separately. Search is end-state existence, not an online adversarial replacement policy. Cases are not weighted by game probability.

- No reserved off-board basics: 3,607 / 3,677 cases retain all tested costs; 70 fail.
- One of EACH basic reserved off-board/unavailable to search: 3,576 / 3,584 retain all tested costs; 8 fail.

Failures are preserved in `resilience.json`. For example, three Forests plus two lost duals cannot always replace those duals with two basics that simultaneously preserve access to both WW and R. That is loss of color compression, not simply too few fetch targets. The remaining vulnerability is explicit; no guarantee against every pair of land hits.

The initial seven-basic version is retained in `variant-7-basics/`. It had only one Mountain and materially more failures in the reserved-basic scenario (370 of 2,874); cases differ between variants, so this is structural evidence, not a matchup statistic.

## Source and structure checks

`recommended-land-verification.json` and `released-printings.json` verify current Standard legality and released Arena printings. Date-filtered shockland checks exclude future reprint evidence. Copperline Gorge, Razorverge Thicket and relevant painlands were not Standard legal in the checked snapshot; they are not recommended.

`export-card-records.json` preserves structured spell records. Important costs: Miles 1G, Academic RW, Lightning 1RW, Ouroboroid 2GG, Smile 3WW, Tyvar 1GG, Tyvar activation 3GG, Miles transform 3RGW, Jennifer transform 3GWW. The final mana distribution retains their demands without modifying spells.

`annotated-main.json` passes the fixed structure checker: 60 main, 24 lands / 26 creatures / 10 other; curve 8/16/6/4/2/0 for MV1/2/3/4/5/6+. Structural pass is not gameplay approval. `proposed-export.txt` contains the exact land-only revision and original seven-card sideboard.
