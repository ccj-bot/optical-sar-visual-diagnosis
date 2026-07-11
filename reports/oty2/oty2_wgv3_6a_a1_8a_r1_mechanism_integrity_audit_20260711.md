# OTY2 WGV3.6A-A1.8A-R1 Mechanism Integrity Audit

## Boundary

- requested start commit: `a9790e1796fb37ac5a919a35e07ea2f1a21200de`
- command boundary: `generate`, `blind-pack`, `evaluate`, `verify-replay`; no `all` command.
- generate reads: SAR gray frames, static fan geometry, A1.7R source-only search shells, current/past runtime frames.
- evaluate reads only after freeze: paired GT, discovery labels, original frame mapping, vehicle identity labels, EVAL_ONLY target boxes.
- GM_RM011 executed: `false`
- final annotation / revised GT / selector / ranking / training: `false`

## Frozen SHA

- `blind_judgement`: `daa79eaaae51d97abfe2bb1cc221026830dbae4a0873a5b8c11906a68435ed72`
- `frozen_atom_trace`: `12fd347069713da14a34f558166555c6ab1c79fba38576669144a258a905eb81`
- `frozen_role_proposals`: `a2421e906b506c6d34be5b4672441e5003f5a3de8bf0eb3ef39c0f61439232d4`
- `support_extent`: `69734783038748b5dfeab57f24d31341bc8f68a16a0448865aed48be17c62cb7`
- `lineage_nodes`: `1d6f1989b36b9812f223b2c8b49fda1b115209346376e88002ade7bdf210c1ec`
- `lineage_edges`: `af3dd3229815e5ffd1c686451c9b97c300fdd3182c0adc9fc04bb3b342b68656`
- `runtime_entities`: `8cf534dcb72e7e6b1b6a0b5e1812ae8898482abc52f915d478aef500ae58753e`
- `FROZEN_REPLAY_IDENTICAL`: `PASS`
- replay evidence: `frozen_atom_trace:PASS; frozen_role_proposals:PASS; support_extent:PASS; lineage_nodes:PASS; lineage_edges:PASS; runtime_entities:PASS`

## Blind Holdout

| interval_id | random_seed | selected_sar_frame | selection_rule | gt_loaded_during_sampling |
| --- | --- | --- | --- | --- |
| HOLDOUT_033_076 | 1801 | 34 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_033_076 | 1801 | 39 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_033_076 | 1801 | 52 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_214_237 | 1801 | 216 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_214_237 | 1801 | 224 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_214_237 | 1801 | 228 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_240_268 | 1801 | 259 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_240_268 | 1801 | 262 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_240_268 | 1801 | 263 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_274_287 | 1801 | 278 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_274_287 | 1801 | 279 | deterministic_random_sample_without_gt_or_visual_resampling | false |
| HOLDOUT_274_287 | 1801 | 281 | deterministic_random_sample_without_gt_or_visual_resampling | false |

## Runtime Counts

- scattering atoms: `202`
- candidate roles: `{'isolated_small_atom': 57, 'unresolved_atom': 69, 'body_core_candidate': 27, 'endpoint_hotspot_candidate': 29, 'side_ridge_candidate': 12, 'background_arc_candidate': 8}`
- part lineage nodes/edges/tracks: `202/522/27`
- lineage edge states: `{'unique_continuation': 41, 'blocked_by_geometry': 198, 'blocked_by_extent_jump': 43, 'ambiguous_successors': 48, 'blocked_by_energy_jump': 39, 'ambiguous_predecessors': 18, 'blocked_by_orientation_jump': 73, 'blocked_by_role_incompatibility': 37, 'blocked_by_radial_azimuth_drift': 25}`
- runtime entities: `{'unresolved_runtime': 32, 'vehicle_supported_runtime': 7, 'background_like_runtime': 8, 'vehicle_possible_runtime': 7}`
- blind judgements: `{'vehicle_structure': 11, 'vehicle_part': 22, 'unresolved': 13, 'background': 8}`
- support-pixel median L/W: `138.731931/115.717868`
- centroid median L/W: `90.988512/28.775241`
- extent_degeneracy_fixed count: `13`

## Temporal Gate

`G_temporal` is computed from `persistent_part_track_id` produced by unique adjacent-frame lineage edges. It is not derived from `runtime_class`, blind judgement, GT, or polarity.

## Evaluation Counts

- eval rows: `54`
- runtime false reject: `11`
- runtime false accept: `1`
- runtime/blind disagreement: `23`
- blind/GT disagreement: `0`
- unresolved count: `13`

## Visual Review Notes

- Opened blind sheets use only opaque BLIND_FRAME and BLIND_OBJECT IDs, candidate roles, support-pixel axes, relation edges, and lineage ids.
- White 27-31: runtime/blind support is concentrated in compact lower responses with core/side/endpoint candidates; nearby isolated candidates remain non-decisive.
- White 78-81: lower body/side candidates are separated from the horizontal background-arc candidate; the arc is the decisive non-vehicle alternative.
- Silver 270-273: lower local body/side response appears weaker and often only partially supported; far-side line/arc candidates are not accepted as vehicle closure.
- Silver 289-290: side/core candidates exist but remain conditional; unresolved alternatives and missing exact support keep A1.7R2 blocked.
- Blind holdout: selected frames provide local intermediate-frame checks, but not full-scene completion.

## Vehicle Vs Other Contrast

| contrast_id | accepted_object_id | alternative_object_id | same_frame_or_cross_frame | accepted_runtime_class | alternative_runtime_class | accepted_blind_judgement | alternative_blind_judgement | decisive_difference_cn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1C0001 | BLIND_OBJECT_001 | BLIND_OBJECT_025 | cross_frame | unresolved_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;isolated_small_atom;unresolved_atom 和谱系 R1PT002；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0002 | BLIND_OBJECT_002 | BLIND_OBJECT_025 | cross_frame | vehicle_supported_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;unresolved_atom 和谱系 R1PT002；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0003 | BLIND_OBJECT_003 | BLIND_OBJECT_025 | cross_frame | vehicle_supported_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;unresolved_atom 和谱系 R1PT002；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0004 | BLIND_OBJECT_004 | BLIND_OBJECT_025 | cross_frame | unresolved_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;isolated_small_atom;unresolved_atom 和谱系 R1PT002;R1PT003；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0005 | BLIND_OBJECT_005 | BLIND_OBJECT_025 | cross_frame | unresolved_runtime | background_like_runtime | vehicle_part | background | 接受对象具有 endpoint_hotspot_candidate;unresolved_atom 和谱系 R1PT002;R1PT003；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0006 | BLIND_OBJECT_007 | BLIND_OBJECT_025 | cross_frame | unresolved_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;endpoint_hotspot_candidate;unresolved_atom 和谱系 ；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0007 | BLIND_OBJECT_008 | BLIND_OBJECT_009 | same_frame | unresolved_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;endpoint_hotspot_candidate;isolated_small_atom 和谱系 R1PT006;R1PT007;R1PT008；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0008 | BLIND_OBJECT_011 | BLIND_OBJECT_012 | same_frame | unresolved_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;endpoint_hotspot_candidate;isolated_small_atom;side_ridge_candidate 和谱系 R1PT004;R1PT006;R1PT007;R1PT008；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0009 | BLIND_OBJECT_014 | BLIND_OBJECT_015 | same_frame | unresolved_runtime | background_like_runtime | vehicle_part | background | 接受对象具有 body_core_candidate;isolated_small_atom;unresolved_atom 和谱系 ；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0010 | BLIND_OBJECT_017 | BLIND_OBJECT_025 | cross_frame | vehicle_possible_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;unresolved_atom 和谱系 ；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0011 | BLIND_OBJECT_018 | BLIND_OBJECT_025 | cross_frame | vehicle_supported_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;side_ridge_candidate;unresolved_atom 和谱系 R1PT009；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0012 | BLIND_OBJECT_019 | BLIND_OBJECT_025 | cross_frame | vehicle_possible_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;side_ridge_candidate;unresolved_atom 和谱系 ；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0013 | BLIND_OBJECT_020 | BLIND_OBJECT_021 | same_frame | unresolved_runtime | background_like_runtime | vehicle_part | background | 接受对象具有 body_core_candidate;unresolved_atom 和谱系 R1PT011；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0014 | BLIND_OBJECT_022 | BLIND_OBJECT_023 | same_frame | unresolved_runtime | background_like_runtime | vehicle_structure | background | 接受对象具有 body_core_candidate;side_ridge_candidate;unresolved_atom 和谱系 R1PT011；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0015 | BLIND_OBJECT_024 | BLIND_OBJECT_025 | same_frame | unresolved_runtime | background_like_runtime | vehicle_part | background | 接受对象具有 body_core_candidate;isolated_small_atom;unresolved_atom 和谱系 R1PT010;R1PT011；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0016 | BLIND_OBJECT_026 | BLIND_OBJECT_025 | cross_frame | vehicle_supported_runtime | background_like_runtime | vehicle_part | background | 接受对象具有 endpoint_hotspot_candidate;unresolved_atom 和谱系 R1PT012；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0017 | BLIND_OBJECT_028 | BLIND_OBJECT_025 | cross_frame | vehicle_possible_runtime | background_like_runtime | vehicle_part | background | 接受对象具有 endpoint_hotspot_candidate;unresolved_atom 和谱系 ；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| R1C0018 | BLIND_OBJECT_030 | BLIND_OBJECT_025 | cross_frame | vehicle_possible_runtime | background_like_runtime | vehicle_part | background | 接受对象具有 endpoint_hotspot_candidate;unresolved_atom 和谱系 ；替代对象虽可能更长或更亮，但角色为 background_arc_candidate 并触发弧线冲突。 |
| ... |  |  |  |  |  |  |  |  |

## Failure Cases

| case_id | failure_type | object_id | sar_frame | reason_cn | provenance |
| --- | --- | --- | --- | --- | --- |
| R1F0001 | runtime_false_reject | BLIND_OBJECT_001 | 27 | 运行时拒绝或未判定 body_core_candidate;isolated_small_atom;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |
| R1F0002 | runtime_false_reject | BLIND_OBJECT_004 | 30 | 运行时拒绝或未判定 body_core_candidate;isolated_small_atom;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |
| R1F0003 | runtime_false_reject | BLIND_OBJECT_005 | 31 | 运行时拒绝或未判定 endpoint_hotspot_candidate;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |
| R1F0004 | runtime_false_reject | BLIND_OBJECT_020 | 79 | 运行时拒绝或未判定 body_core_candidate;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |
| R1F0005 | runtime_false_reject | BLIND_OBJECT_022 | 80 | 运行时拒绝或未判定 body_core_candidate;side_ridge_candidate;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |
| R1F0006 | runtime_false_reject | BLIND_OBJECT_024 | 81 | 运行时拒绝或未判定 body_core_candidate;isolated_small_atom;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |
| R1F0007 | runtime_false_reject | BLIND_OBJECT_025 | 81 | 运行时 background_like_runtime、盲审 background、GT 关系 near_gt_eval_only；保留为背景、未解或机制反例。 | eval_only_gt_assisted |
| R1F0008 | runtime_false_accept | BLIND_OBJECT_040 | 263 | 运行时接受 endpoint_hotspot_candidate;unresolved_atom，但盲审为 unresolved；GT 关系 no_exact_gt_for_frame 只能作为事后解释，不能回写生成结果。 | eval_only_gt_assisted |
| R1F0009 | runtime_false_reject | BLIND_OBJECT_043 | 271 | 运行时拒绝或未判定 body_core_candidate;endpoint_hotspot_candidate;isolated_small_atom;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |
| R1F0010 | runtime_false_reject | BLIND_OBJECT_044 | 272 | 运行时拒绝或未判定 body_core_candidate;endpoint_hotspot_candidate;isolated_small_atom;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |
| R1F0011 | runtime_false_reject | BLIND_OBJECT_045 | 273 | 运行时 unresolved_runtime、盲审 unresolved、GT 关系 overlaps_gt_eval_only；保留为背景、未解或机制反例。 | eval_only_gt_assisted |
| R1F0012 | runtime_false_reject | BLIND_OBJECT_053 | 289 | 运行时拒绝或未判定 body_core_candidate;isolated_small_atom;side_ridge_candidate;unresolved_atom，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。 | eval_only_gt_assisted |

## Gate Verdicts

| gate | status | evidence | provenance |
| --- | --- | --- | --- |
| GENERATION_GT_ISOLATION_VALID | PASS | leakage audit checks all passed | runtime_safe |
| POLARITY_LABEL_NOT_USED_IN_GENERATE | PASS | generate uses DISCOVERY_RUNTIME_FRAMES without positive/negative split | runtime_safe |
| FROZEN_REPLAY_IDENTICAL | PASS | verify-replay compares frozen atom/role/extent/entity/lineage SHA | runtime_safe |
| BLIND_OBJECT_REVIEW_FROZEN | PASS | blind rows=54; sha=daa79eaaae51d97abfe2bb1cc221026830dbae4a0873a5b8c11906a68435ed72 | blind_visual_review |
| BLIND_REVIEW_NOT_TEMPLATE_GENERATED | PASS | blind judgement was filled after opening blind sheets and varies by visible object evidence | blind_visual_review |
| SUPPORT_PIXEL_EXTENT_VALID | PASS | extent_degeneracy_fixed_count=13; no centroid short-axis clamp used | runtime_safe |
| PART_LINEAGE_RUNTIME_SAFE | PASS | nodes=202; edges=522; unique_edges=41 | runtime_safe |
| TEMPORAL_GATE_NOT_CIRCULAR | PASS | G_temporal comes from persistent_part_track_id, not runtime class | runtime_safe |
| POSITIVE_NEGATIVE_EVALUATION_UNBIASED | PARTIAL | false_reject=11; false_accept=1; labels loaded only in evaluate | eval_only_gt_assisted |
| GT_ASSISTED_EXPLANATION_COMPLETE | PASS | gt-assisted eval rows=54 | eval_only_gt_assisted |
| VEHICLE_VS_OTHER_MECHANISM_CLOSED | PARTIAL | contrast rows=35; still local window only | eval_only_gt_assisted |
| POINT_TO_STRUCTURE_R1_READY | PARTIAL | R1 fixes isolation and extent/lineage audits but remains local | eval_only_gt_assisted |
| VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2 | NO | holdout is local and mechanism remains partial | eval_only_gt_assisted |
| INTERMEDIATE_FRAME_BLIND_EVAL_PENDING | partially_completed | 12 deterministic holdout frames reviewed, not full scene | blind_visual_review |
| GM_RM011_BLOCKED | true | R1 remains GM_RM019 only | eval_only_gt_assisted |

## Created Files

- `reports/oty2/oty2_wgv3_6a_a1_8a_r1_mechanism_integrity_audit_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_blind_holdout_manifest_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_leakage_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_frozen_atom_trace_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_frozen_role_proposals_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_support_pixel_structure_extent_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_part_lineage_nodes_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_part_lineage_edges_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_frozen_runtime_entities_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_blind_review_manifest_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_blind_object_judgement_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_gt_assisted_evaluation_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_vehicle_vs_other_contrast_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_gate_integrity_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_failure_cases_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r1_frozen_artifact_manifest_20260711.csv`

## Research Judgment

R1 fixes the main integrity faults in A1.8A: generation no longer receives polarity labels, blind review is opaque, support-pixel extents replace centroid-only widths, and temporal support comes from adjacent-frame part lineage. The result is still a local mechanism audit, not a ready input contract for A1.7R2.