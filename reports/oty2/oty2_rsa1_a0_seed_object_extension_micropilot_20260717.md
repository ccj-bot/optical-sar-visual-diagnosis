# OTY2-RSA1-A0 Manual-Seed-Guided SAR Response Object Extension Micropilot

Date: `2026-07-17`

Stage conclusion: `MICROPILOT_PARTIALLY_SUPPORTED`

Hidden-reference freeze SHA256: `88b165ba3657637fbb45afccbc443f53fb05a06bc25ed8a2f62222600687104c`

Rule-freeze SHA256: `76b72f566325e462dade42dfe328f703f48ce6dba91b224ce306921690df152e`

The main experiment is the GT-aligned research stack. Optical-proxy-aligned results are sensitivity evidence only and are not used to rescue the stage conclusion.

## 1. What structure did the algorithm actually extend from the central seed?

The frozen mechanism visits contiguous 12 px local line-segment primitives along the R2-confirmed seed tangent. It does not generate a top-N bank or rank alternatives. In PV002 SAR 339, `GT_RIGHT01` and `GT_RIGHT02` extend the subtle lower response immediately to the right of the 24 px seed. `GT_LEFT01` intersects the vertical-background barrier and is vetoed before any structural score can promote it.

- Exact evidence: PV002 SAR 339 primitive `PV002_337_341_339_GT_RIGHT01`, expansion step `2`, gate result `ALL_REQUIRED_GATES_PASSED`, ridge relation `1.395728`, contrast relation `1.304811`, temporal NCC `0.214282`, card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\development\pv002_temporal\evidence_cards\PV002_337_341\339\PV002_337_341_339_GT_RIGHT01.png`.
- Counterexample/barrier evidence: PV002 SAR 339 primitive `PV002_337_341_339_GT_LEFT01`, expansion step `1`, first failed gate `CONFIRMED_VERTICAL_BACKGROUND`, card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\development\pv002_temporal\evidence_cards\PV002_337_341\339\PV002_337_341_339_GT_LEFT01.png`.
- Hidden-reference evaluation: PV002 SAR 339 `SINGLE_FRAME_SPATIAL` covers `36/55 px`, with `14 px` beyond seed-only.
- PV003 reconstructs the same primitives from the frozen seed tangent, but no GT-aligned primitive reaches `SUPPORTED_EXTENSION`.

## 2. Which relation gates did supported extensions pass?

A supported primitive must retain a current-frame seed path, stay outside the vertical barrier and ambiguity zones, satisfy direction/width continuity, pass ridge or local-contrast evidence, and receive temporal support. No weighted total score exists.

PV002 totals: spatial supported `5` / `60.0 px`, forward supported `3` / `36.0 px`, bidirectional supported `6` / `72.0 px`.
Exact evidence: PV002 SAR 339 primitive `PV002_337_341_339_GT_RIGHT02`, expansion step `3`, source `PV002_337_341_339_GT_RIGHT01`, gate result `ALL_REQUIRED_GATES_PASSED`, card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\development\pv002_temporal\evidence_cards\PV002_337_341\339\PV002_337_341_339_GT_RIGHT02.png`; the matching hidden-reference row is `PV002_337_341,339,SINGLE_FRAME_SPATIAL` with `14 px` added coverage and `0` path failures.

## 3. Did extension cover confirmed skeleton beyond the seed?

PV002 gains hidden-skeleton coverage beyond seed-only: spatial `49 px`, forward `33 px`, bidirectional `56 px`. PV003 gains `0 px` in all three modes because probable is not merged into supported.

PV003 SAR 382 `GT_RIGHT01` remains probable with orientation difference `5.585492` and temporal NCC `-0.087344`; card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\frozen_replay\pv003_gt\evidence_cards\PV003_380_384\382\PV003_380_384_382_GT_RIGHT01.png`.
Exact coverage evidence: PV002 SAR 339 primitive `PV002_337_341_339_GT_RIGHT02`, expansion step `3`, gate result `ALL_REQUIRED_GATES_PASSED`, card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\development\pv002_temporal\evidence_cards\PV002_337_341\339\PV002_337_341_339_GT_RIGHT02.png`; hidden row `PV002_337_341,339,SINGLE_FRAME_SPATIAL` reports `36/55 px` covered and `14 px` added. PV003 SAR 382 primitive `PV003_380_384_382_GT_RIGHT01`, step `2`, fails `TEMPORAL_OR_STRUCTURE_SUPPORT_INCOMPLETE` and the bidirectional hidden row reports `0 px` added.

## 4. Did the vertical-background barrier prevent pollution?

Yes for supported output. Hidden-reference overlap is PV002 `0 px` and PV003 `0 px`; supported crossing-path counts are PV002 `0` and PV003 `0`. PV002 records five explicit left-side background vetoes across SAR 337-341.
Exact barrier evidence: PV002 SAR 339 primitive `PV002_337_341_339_GT_LEFT01`, expansion step `1`, first failed gate `CONFIRMED_VERTICAL_BACKGROUND`, card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\development\pv002_temporal\evidence_cards\PV002_337_341\339\PV002_337_341_339_GT_LEFT01.png`; hidden row `PV002_337_341,339,OFFLINE_BIDIRECTIONAL_MICROPILOT` reports `0 px` vertical-background overlap and `0` crossing paths.

## 5. Were fan arc, clutter, and endpoints kept unresolved?

No GT-aligned mode assigns an entire hidden ambiguity zone: PV002 bidirectional overlap is `78/47410 px` with `0` fully assigned frames; PV003 is `0/67850 px` with `0` fully assigned frames. However, PV002 bidirectional propagation does weaken endpoint restraint by promoting a localized part of the unresolved right endpoint. Proxy sensitivity ambiguity stops remain sensitivity-only evidence.
Exact endpoint evidence: PV002 SAR 339 primitive `PV002_337_341_339_GT_RIGHT03`, expansion step `4`, first failed gate `TEMPORAL_OR_STRUCTURE_SUPPORT_INCOMPLETE`, single-frame state `PROBABLE_EXTENSION`, card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\development\pv002_temporal\evidence_cards\PV002_337_341\339\PV002_337_341_339_GT_RIGHT03.png`. Offline bidirectional step `4` promotes the same primitive to `SUPPORTED_EXTENSION` through cross-frame support from `PV002_337_341_340_GT_RIGHT03`; hidden row `PV002_337_341,339,OFFLINE_BIDIRECTIONAL_MICROPILOT` reports `39/9482 px` overlap (`0.004113`), not full-zone assignment.

## 6. Did the frozen rule reproduce in PV003, and what failed?

The rule reproduced byte-identically under `76b72f566325e462dade42dfe328f703f48ce6dba91b224ce306921690df152e` and no PV003 tuning occurred. It failed at the local-structure/temporal layer rather than at the barrier: PV003 SAR 384 `GT_RIGHT01` has orientation difference `73.566053`, width relation `0.142857`, temporal NCC `-0.087344`, and first failed gate `LOCAL_STRUCTURE_OR_TEMPORAL_SUPPORT`; card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\frozen_replay\pv003_gt\evidence_cards\PV003_380_384\384\PV003_380_384_384_GT_RIGHT01.png`.
Exact replay evidence: primitive `PV003_380_384_384_GT_RIGHT01`, expansion step `2`, source `PV003_380_384_384_GT_SEED`, state `TEMPORALLY_UNSUPPORTED`; hidden row `PV003_380_384,384,OFFLINE_BIDIRECTIONAL_MICROPILOT` reports `0 px` added coverage, `0 px` vertical overlap, and `0 px` ambiguity overlap.
SAR 384 is the replay-window endpoint. Its evidence card clamps the display-only `next SAR` panel to SAR 384 itself; this duplicate panel is not future-frame support and does not change the recorded negative temporal relation.

The weak GT-aligned response does not satisfy the frozen PV002 direction/width plus temporal relation. Optical-proxy sensitivity yields many more supported primitives, but PV003 proxy mapping drift is known debt and sensitivity-only output cannot be interpreted as main-mechanism success or failure.

## 7. Continue or stop this propagation mechanism?

Conclusion: `MICROPILOT_PARTIALLY_SUPPORTED`. The mechanism is locally useful in PV002 for conservative right-side extension and hard background blocking, but it does not reproduce supported extension in PV003. The ten-condition success gate therefore fails. This exact frozen mechanism should stop; any later work must open a new versioned micropilot focused on weak-response primitive orientation/temporal support, not retune RSA1-A0 after seeing PV003.
Decision evidence: PV003 SAR 382 primitive `PV003_380_384_382_GT_RIGHT01`, expansion step `2`, first failed gate `TEMPORAL_OR_STRUCTURE_SUPPORT_INCOMPLETE`, state `PROBABLE_EXTENSION`, card `D:\profile\research\workspace\output\oty2_rsa1_a0_20260717\frozen_replay\pv003_gt\evidence_cards\PV003_380_384\382\PV003_380_384_382_GT_RIGHT01.png`; hidden row `PV003_380_384,382,OFFLINE_BIDIRECTIONAL_MICROPILOT` adds `0 px` over seed-only. Together with PV002 SAR 339 `PV002_337_341_339_GT_RIGHT01` passing all required gates and adding `23 px`, this supports partial—not full—mechanism support.

## Output counts

- Final primitive rows: `205`.
- Final expansion-trace rows: `145`.
- PV003 tuning performed: `false`.
- Hidden references were not read by preparation, primitive construction, spatial extension, temporal extension, rule freeze, or replay. They were opened only by this evaluator.
