# OTY2 WGV3.6A-A1.8A-R2.1-R1.1 Semantic Separation

## Boundary

- start commit: `aba57096e6b38e33bfac4a6e68d6d00aa40ace5c`
- start title: `Fix R2.1 bbox family grouping and evaluation integrity`
- R2.1 atoms/roles/support/lineage/graph/core/response boxes and all R2.1-R1 family/review files are frozen read-only inputs.
- This round separates local response units, strict boundary-variant families, and same-object candidate edges.
- It does not implement selector, ranking, best candidate, GM_RM017, GM_RM011, dynamic shell, final annotation, threshold tuning, or GT modification.
- GM_RM019_STATIC_STAGE_CLOSED=true after replay pass; NEXT_STAGE=GM_RM017_CONTINUOUS_PHYSICAL_RESPONSE_AUDIT.

## Counts

- boundary families before R1.1: `165`
- boundary variant families after R1.1: `176`
- zero-core-overlap old family split count: `11`
- accepted-link-only old family split count: `11`
- local response units: `250`
- same-object candidate edges: `148`
- same-object candidate edge counts: `{'accepted_graph_link_candidate': 137, 'part_part_candidate': 11}`
- body-endpoint / body-side / part-part / accepted-link candidate edges: `0` / `0` / `11` / `137`
- boundary-family zero-core-overlap pair count: `0`
- boundary-family different-core/no-overlap count: `0`
- boundary-family accepted-link-only pair count: `0`

## Top-K Reinterpretation

- residual component rows: `2368`
- proximity residual candidates: `1615`
- old possible weak vehicle part claim count: `1535`
- revoked statement: `1535 weak vehicle parts were dropped by Top-K`.
- corrected statement: Found many small residual components near frozen response regions but unmatched to frozen atoms; whether they are vehicle weak responses is unproven without exact original Top-K replay, dynamic co-motion, or object-by-object visual review.
- TOP_K_EXACT_DROP_AUDIT: `FAIL`
- TOP_K_WEAK_RESPONSE_RISK: `UNRESOLVED`

## GT Instance Evaluation

- GT instance counts by frame: `{'0': 1, '4': 1, '8': 1, '27': 2, '31': 1, '77': 1, '81': 1, '212': 1, '238': 1, '269': 1, '273': 1, '288': 1, '290': 1, '315': 1, '317': 1}`
- multi-instance GT union used: `false`
- response-unit x GT-instance matrix rows: `63`
- boundary-family x GT-instance matrix rows: `45`
- response-unit max IoU across instances eval-only: `0.567172`
- boundary-family max IoU across instances eval-only: `0.567172`

## Focus Review

- Scope is limited to frames 31, 32, 39, 78, 79, 263, 270, 271, 272, 273, 289, 290; this is not a full 165-family re-review.

| sar_frame | visual_validity_state | reviewer_note_cn |
| --- | --- | --- |
| 31 | UNPROVEN | 已实际查看 SAR31 focus 图；结论只适用于该关键帧，不提升全局 object-specific PASS。 |
| 32 | UNPROVEN | 已实际查看 SAR32 focus 图；静态语义分离可见，但不等于车辆真值确认。 |
| 39 | UNPROVEN | 已实际查看 SAR39 focus 图；候选边可解释可能部件关系，但需要后续动态审计。 |
| 78 | UNPROVEN | 已实际查看 SAR78 focus 图；静态阶段只保留候选关系。 |
| 79 | UNPROVEN | 已实际查看 SAR79 focus 图；不做身份真值或最终标注。 |
| 263 | UNPROVEN | 已实际查看 SAR263 focus 图；单元存在但车辆支持仍未由本轮证明。 |
| 270 | UNPROVEN | 已实际查看 SAR270 focus 图；候选边不构成同车确认。 |
| 271 | UNPROVEN | 已实际查看 SAR271 focus 图；本轮只记录静态候选关系。 |
| 272 | UNPROVEN | 已实际查看 SAR272 focus 图；需要后续共运动审计才可确认部件关系。 |
| 273 | UNPROVEN | 已实际查看 SAR273 focus 图；静态结论保持保守。 |
| 289 | UNPROVEN | 已实际查看 SAR289 focus 图；不输出最终车辆框。 |
| 290 | UNPROVEN | 已实际查看 SAR290 focus 图；本轮完成静态语义关闭。 |

## Gates

| gate | status | evidence | provenance |
| --- | --- | --- | --- |
| R2_1_R1_FROZEN_INPUTS_UNCHANGED | PASS | R2.1 and R2.1-R1 manifest SHA checks compared | frozen_input_replay |
| LOCAL_RESPONSE_UNIT_SEMANTICS_EXPLICIT | PASS | local response units=250; units are not complete vehicles | semantic_separation |
| BOUNDARY_VARIANT_FAMILY_SEMANTICS_VALID | PASS | boundary families=176; strict same-core variant rules applied | boundary_family_builder |
| BOUNDARY_FAMILY_ZERO_CORE_OVERLAP_PAIR_COUNT | PASS | count=0 | boundary_family_builder |
| BOUNDARY_FAMILY_DIFFERENT_CORE_NO_OVERLAP_COUNT | PASS | count=0 | boundary_family_builder |
| BOUNDARY_FAMILY_ACCEPTED_LINK_ONLY_PAIR_COUNT | PASS | count=0 | boundary_family_builder |
| SAME_OBJECT_CANDIDATE_EDGE_SEPARATED | PASS | edges=148; counts={'accepted_graph_link_candidate': 137, 'part_part_candidate': 11} | same_object_candidate |
| SAME_OBJECT_CANDIDATE_NOT_IDENTITY_TRUTH | PASS | edge_state is candidate/weak/blocked only; no confirmed same vehicle | same_object_candidate |
| STATIC_FAMILY_NOT_EQUAL_PHYSICAL_VEHICLE | PASS | boundary family represents local-response boundary variants, not physical vehicle identity | semantic_boundary |
| PROXIMITY_RESIDUAL_COMPONENT_AUDIT | PASS | residual components=2368; proximity candidates=1615 | topk_semantic_reinterpretation |
| TOP_K_EXACT_DROP_AUDIT | FAIL | R2.1-R1 top-k file is reinterpreted as proximity residual audit, not exact original top-k replay | topk_semantic_reinterpretation |
| TOP_K_WEAK_RESPONSE_RISK | UNRESOLVED | vehicle weak-part conclusion revoked; physical_vehicle_part_unproven=true | topk_semantic_reinterpretation |
| INSTANCE_LEVEL_GT_EVALUATION_VALID | PASS | response-unit matrix rows=63; boundary-family matrix rows=45 | eval_only_instance_matrix |
| MULTI_INSTANCE_GT_UNION_NOT_USED | PASS | GT instances are evaluated as per-instance rows; no frame-level union box is constructed | eval_only_instance_matrix |
| RAW_REVIEW_FIELDS_COMPLETE | PASS | R2.1-R1 raw review CSV fields checked for completeness | review_gate_semantic_downgrade |
| ASSISTED_REVIEW_FIELDS_COMPLETE | PASS | R2.1-R1 assisted review CSV fields checked for completeness | review_gate_semantic_downgrade |
| OBJECT_SPECIFIC_RAW_VISUAL_VALIDITY | UNPROVEN | fields are complete but this round did not redo independent object-by-object raw visual review | review_gate_semantic_downgrade |
| OBJECT_SPECIFIC_ASSISTED_VISUAL_VALIDITY | UNPROVEN | fields are complete but this round did not redo independent object-by-object assisted visual review | review_gate_semantic_downgrade |
| FROZEN_REPLAY_IDENTICAL | PASS | local_response_units:PASS; boundary_variant_families:PASS; boundary_family_members:PASS; boundary_pairwise_integrity:PASS; same_object_candidate_edges:PASS; proximity_residual_component_audit:PASS; response_unit_gt_instance_matrix:PASS; boundary_family_gt_instance_matrix:PASS | frozen_replay |
| R2_1_R1_1_STATIC_SEMANTIC_CLOSURE | PASS | requires strict boundary semantics, candidate edge split, top-k revocation, instance GT, gate downgrade, replay pass | stage_closure |
| VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2 | NO | R2.1-R1.1 is static semantic closure, not an A1.7R2 runtime contract | stage_boundary |
| GM_RM011_BLOCKED | true | GM_RM011 remains outside this task | stage_boundary |
| GM_RM019_STATIC_STAGE_CLOSED | true | no further R2.1-R1.x static expansion after this closure | stage_boundary |
| NEXT_STAGE | GM_RM017_CONTINUOUS_PHYSICAL_RESPONSE_AUDIT | next phase is continuous physical response audit | stage_boundary |

## Replay

- FROZEN_REPLAY_IDENTICAL: `PASS`
- replay evidence: `local_response_units:PASS; boundary_variant_families:PASS; boundary_family_members:PASS; boundary_pairwise_integrity:PASS; same_object_candidate_edges:PASS; proximity_residual_component_audit:PASS; response_unit_gt_instance_matrix:PASS; boundary_family_gt_instance_matrix:PASS`

## Stage Stop

- GM_RM019_STATIC_STAGE_CLOSED=true
- NEXT_STAGE=GM_RM017_CONTINUOUS_PHYSICAL_RESPONSE_AUDIT
