# C1S Legacy Handoff - 2026-07-01

## Boundary

This is a legacy-stage archive note. It does not modify the formal pipeline, does not add a selector or threshold, does not enter G2, does not add A008 scoring, and does not use posthoc/final/oracle/GT fields for runtime generation or ranking.

## Stage Timeline

| Stage | Purpose | Output directory | Key conclusion |
|---|---|---|---|
| P1 | Canonical frozen replay engine. Separate strict table replay from recomputed replay. | `D:\profile\research\optical-to-sar-vehicle-localization-research-synthesis-20260629\output\gm17_p1_canonical_frozen_replay_engine_20260630_221654` | Strict table replay reproduced G1 Focus17 with `strict_damage_count=0`; recomputed replay must remain separately named because it can drift. |
| P2 | Current reliability proxy redesign audit. | `D:\profile\research\optical-to-sar-vehicle-localization-research-synthesis-20260629\output\gm17_p2_current_reliability_proxy_redesign_audit_20260630_221802` | `current_good_proxy` is not a localization reliability proxy. Rename it to `current_local_appearance_clean_proxy`; legacy false-current-good count was 49 and false-hold opportunities were 18. |
| P3 | Missed opportunity release audit. | `D:\profile\research\optical-to-sar-vehicle-localization-research-synthesis-20260629\output\gm17_p3_missed_opportunity_release_audit_20260630_221816` | There were 18 missed current-poor/oracle-good opportunities; within GM_RM017 this was not a candidate-generation bottleneck. |
| C0 | Cross-scene input construction plan. | `D:\profile\research\optical-to-sar-vehicle-localization-research-synthesis-20260629\output\gm17_c0_cross_scene_input_construction_plan_20260630_221822` | GM_RM019 and GM_RM011 lacked the full `candidate_bank`, `A008_candidate_factors`, and `frozen_ranked_candidates` chain at the start of cross-scene work. |
| P4 | Replay/proxy synthesis and handoff. | `D:\profile\research\optical-to-sar-vehicle-localization-research-synthesis-20260629\output\gm17_p4_replay_proxy_synthesis_20260630_221848` | Handoff summarized P1-P3/C0 and kept replay/proxy conclusions separated from selector work. |
| C1 | GM_RM019 candidate input construction audit. | `D:\profile\research\optical-to-sar-vehicle-localization-research-synthesis-20260629\output\gm17_c1_gmrm019_candidate_input_construction_audit_20260630_224141` | Built a 132-row pilot over 22 GM_RM019 runtime targets from base/factor/topk/visible-support sources; no GT/final/oracle/A019/A021 runtime fields were used. |
| C1.1 | GM_RM019 structural candidate source parity / Q-schema candidate-input audit. | `D:\profile\research\workspace\output\c1_1_gmrm019_qschema_candidate_input_audit_20260630_233050` and synthesis mirror `...\gm17_c1_1_gmrm019_structural_candidate_source_parity_20260630_225805` | Candidate input fields were mapped; largest blocker was missing regenerated wedge/ray/signed mode inputs and temporal/identity context. |
| C1.2 | GM_RM019 mode regeneration and candidate parity audit. | `D:\profile\research\workspace\output\c1_2_gmrm019_mode_regeneration_candidate_parity_audit_20260701_100854` and synthesis mirror `...\gm17_c1_2_gmrm019_mode_input_generation_audit_20260630_232959` | Generated wedge/ray/signed mode candidates and a 387-row extended candidate table locally; signed direction remained partial because identity context was missing. |
| C1.3 | GM_RM019 temporal/identity context audit and structural candidate bank parity. | `D:\profile\research\workspace\output\c1_3_gmrm019_temporal_identity_context_audit_20260701_102308` and synthesis mirror `...\gm17_c1_3_gmrm019_structural_candidate_bank_parity_20260701_100609` | Short-window temporal context advanced signed evidence, but explicit same-target runtime IDs were still absent; structural candidate pool ceiling remained limited. |
| C1.4 | GM_RM019 runtime tracklet reconstruction and frozen ranked candidates input audit. | `D:\profile\research\workspace\output\c1_4_gmrm019_runtime_tracklet_reconstruction_audit_20260701_104305` and synthesis mirror `...\gm17_c1_4_gmrm019_frozen_ranked_candidates_input_audit_20260701_102425` | Partial audit tracklets were constructible; no signed identity-supported rows existed; frozen ranking was deterministic input ordering, not a calibrated selector. |
| C1S | Candidate input pipeline synthesis. | `D:\profile\research\optical-to-sar-vehicle-localization-research-synthesis-20260629\output\gm17_c1s_candidate_input_pipeline_synthesis_20260701_104520` | Consolidated P1-P4 and C1-C1.4 into a handoff; GM_RM019 candidate input chain is open, but A008-equivalent runtime factor layer is not built and GM_RM011 has not replicated the same chain. |

## Required State

- G2 / formal selector = `HOLD`.
- Phase5 = `BLOCKED_FOR_OOF_CALIBRATION`.
- `current_good_proxy` cannot be used as a localization reliability proxy. Use `current_local_appearance_clean_proxy` for the legacy visual-cleanliness meaning.
- Strict replay and recomputed replay must be named and reported separately.
- GM_RM019 candidate input chain has been connected through C1.4/C1S.
- GM_RM011 has not reproduced the same candidate input chain.
- SAR-only targets must not be backfilled with final boxes.
- Posthoc/final/oracle/GT fields remain diagnostic-only and cannot enter runtime generation or ranking.

## Transition Note

The next repository should inherit data references, accounting CSV references, and visual diagnosis questions. It should not inherit the old mixed pipeline as an execution model.
