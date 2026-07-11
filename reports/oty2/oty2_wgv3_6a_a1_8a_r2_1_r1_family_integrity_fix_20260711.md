# OTY2 WGV3.6A-A1.8A-R2.1-R1 Family Integrity Fix

## Boundary

- start commit: `713fb7ddad99c56303078bb7fca87c0006b00bd3`
- R2.1 atoms, roles, support metrics, lineage, atom graph, core hypotheses, optional membership, and response-box member hypotheses are frozen read-only inputs.
- R2.1 old family IDs, relations, and old family boxes are not used to generate new families; they are used only in evaluate-stage delta audit.
- This is a bbox-family integrity and evaluation-object repair, not component selection, ranking, selector design, final annotation, or dynamic mechanism work.
- SOURCE_ANCHOR_CONDITIONED_GENERATION=true; SOURCE_ANCHOR_FREE_AUTOMATIC_START_NOT_PROVEN=true.
- VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2=NO; GM_RM011_BLOCKED=true.

## Generation Statistics

- old R2.1 family count: `49`
- new R2.1-R1 family count: `165`
- new family count per frame: `{'27': 5, '28': 4, '29': 3, '30': 5, '31': 3, '32': 6, '34': 7, '39': 5, '40': 5, '46': 1, '52': 2, '60': 2, '77': 6, '78': 6, '79': 6, '80': 6, '81': 4, '212': 1, '213': 3, '216': 1, '220': 2, '224': 3, '227': 3, '228': 2, '238': 2, '239': 3, '243': 3, '250': 3, '259': 3, '260': 3, '262': 1, '263': 1, '269': 5, '270': 4, '271': 3, '272': 6, '273': 3, '276': 4, '278': 3, '279': 4, '280': 3, '281': 3, '284': 5, '288': 4, '289': 5, '290': 3}`
- relation counts: `{'nested_same_core_family': 36, 'single_member_family': 117, 'high_iou_boundary_family': 12}`
- invalid in-family member pairs: `0`
- spatially_distinct in-family pairs: `0`
- transitive bridge split count: `83`
- single-member families: `117`
- common core available families: `165`
- single consensus / multiple variants / common-core-only / unresolved: `117` / `12` / `36` / `0`

## Pairwise Integrity Sample

| family_id | sar_frame | member_box_a | member_box_b | bbox_iou | center_distance_px | core_overlap_ratio | core_subset_relation | relation_type | pairwise_valid | invalid_reason | would_single_link_component | empty_optional_equality_seen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R21R1F00001 | 27 | R21B00001 | R21B00006 | 0.705882 | 15 | 1 | a_subset_b | nested_same_core_variant | true |  | SL000027_001 | true |
| R21R1F00002 | 27 | R21B00002 | R21B00002 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000027_001 | false |
| R21R1F00003 | 27 | R21B00003 | R21B00003 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000027_002 | false |
| R21R1F00004 | 27 | R21B00004 | R21B00004 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000027_003 | false |
| R21R1F00005 | 27 | R21B00005 | R21B00005 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000027_004 | false |
| R21R1F00006 | 28 | R21B00007 | R21B00011 | 0.705882 | 15 | 1 | a_subset_b | nested_same_core_variant | true |  | SL000028_001 | true |
| R21R1F00007 | 28 | R21B00008 | R21B00008 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000028_001 | false |
| R21R1F00008 | 28 | R21B00009 | R21B00009 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000028_002 | false |
| R21R1F00009 | 28 | R21B00010 | R21B00010 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000028_003 | false |
| R21R1F00010 | 29 | R21B00012 | R21B00015 | 0.578947 | 24 | 1 | a_subset_b | nested_same_core_variant | true |  | SL000029_001 | true |
| R21R1F00011 | 29 | R21B00013 | R21B00013 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000029_001 | false |
| R21R1F00012 | 29 | R21B00014 | R21B00014 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000029_002 | false |
| R21R1F00013 | 30 | R21B00016 | R21B00021 | 0.578947 | 24 | 1 | a_subset_b | nested_same_core_variant | true |  | SL000030_001 | true |
| R21R1F00013 | 30 | R21B00016 | R21B00022 | 0.611111 | 21 | 1 | a_subset_b | nested_same_core_variant | true |  | SL000030_001 | true |
| R21R1F00013 | 30 | R21B00021 | R21B00022 | 0.947368 | 3 | 0.5 | overlap | high_iou_boundary_variant | true |  | SL000030_001 | true |
| R21R1F00014 | 30 | R21B00017 | R21B00023 | 0.6875 | 15 | 1 | a_subset_b | nested_same_core_variant | true |  | SL000030_001 | true |
| R21R1F00015 | 30 | R21B00018 | R21B00018 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000030_002 | false |
| R21R1F00016 | 30 | R21B00019 | R21B00019 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000030_001 | false |
| R21R1F00017 | 30 | R21B00020 | R21B00020 | 1 | 0 | 1 | equal | single_member_family | true |  | SL000030_003 | false |
| R21R1F00018 | 31 | R21B00024 | R21B00025 | 0.016731 | 53.303377 | 0 | none | nested_same_core_variant | true |  | SL000031_001 | true |
| ... |  |  |  |  |  |  |  |  |  |  |  |  |

## Review Statistics

- raw judgement counts: `{'background': 16, 'vehicle_response': 23, 'unresolved': 126}`
- assisted judgement counts: `{'background_or_misled': 16, 'vehicle_response': 23, 'unresolved': 126}`
- raw to assisted changes: `{'background->background_or_misled': 16, 'vehicle_response->vehicle_response': 23, 'unresolved->unresolved': 126}`

## GT Evaluation

- member mean IoU: `0.177021`
- family single-conservative mean IoU: `0.052171`
- member eval rows: `250`
- family eval rows: `165`

## Sparse Diagnostic Temporal Correspondence

- sparse diagnostic family correspondence rows: `594`

## Top-K Drop Audit

- audit component rows: `2368`
- dropped components: `2316`
- possible weak vehicle parts dropped: `1535`
- TOP_K_WEAK_RESPONSE_RISK: `HIGH`
- visual review pack: `['outputs/wgv3_6a_a1_8a_r2_1_r1_20260711/topk_component_drop_audit_sar027.png', 'outputs/wgv3_6a_a1_8a_r2_1_r1_20260711/topk_component_drop_audit_sar078.png', 'outputs/wgv3_6a_a1_8a_r2_1_r1_20260711/topk_component_drop_audit_sar227.png', 'outputs/wgv3_6a_a1_8a_r2_1_r1_20260711/topk_component_drop_audit_sar270.png', 'outputs/wgv3_6a_a1_8a_r2_1_r1_20260711/topk_component_drop_audit_sar289.png']`
- Top-K remains an audit object only and is not used for family generation or runtime localization.

## R2.1 Delta Focus Frames

| sar_frame | old_family_count | new_family_count | old_member_count | new_member_count | overmerged_old_family_ids | split_new_family_ids | old_spatially_distinct_members_in_same_family | new_spatially_distinct_members_in_same_family | old_arbitrary_representative_bbox | new_family_boundary_status | change_reason_cn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 1 | 5 | 6 | 6 | R21F00001 | R21R1F00001;R21R1F00002;R21R1F00003;R21R1F00004;R21R1F00005 | 0 | 0 | 1006,1131,1018,1137 | common_core_only:1;single_consensus_bbox:4 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 30 | 1 | 5 | 8 | 8 | R21F00004 | R21R1F00013;R21R1F00014;R21R1F00015;R21R1F00016;R21R1F00017 | 0 | 0 | 1042,1131,1193,1197 | common_core_only:2;single_consensus_bbox:3 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 31 | 1 | 3 | 8 | 8 | R21F00005 | R21R1F00018;R21R1F00019;R21R1F00020 | 0 | 0 | 1042,1135,1114,1243 | common_core_only:1;single_consensus_bbox:2 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 32 | 1 | 6 | 8 | 8 | R21F00006 | R21R1F00021;R21R1F00022;R21R1F00023;R21R1F00024;R21R1F00025;R21R1F00026 | 1 | 0 | 1048,1165,1072,1177 | multiple_valid_bbox_variants:1;single_consensus_bbox:5 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 34 | 1 | 7 | 8 | 8 | R21F00007 | R21R1F00027;R21R1F00028;R21R1F00029;R21R1F00030;R21R1F00031;R21R1F00032;R21R1F00033 | 1 | 0 | 1018,1141,1042,1159 | common_core_only:1;single_consensus_bbox:6 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 39 | 1 | 5 | 8 | 8 | R21F00008 | R21R1F00034;R21R1F00035;R21R1F00036;R21R1F00037;R21R1F00038 | 1 | 0 | 1048,1165,1192,1276 | common_core_only:2;single_consensus_bbox:3 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 40 | 2 | 5 | 6 | 6 | R21F00009 | R21R1F00039;R21R1F00040;R21R1F00041;R21R1F00042;R21R1F00043 | 1 | 0 | 1054,1207,1108,1237 / 994,1135,1090,1159 | common_core_only:1;single_consensus_bbox:4 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 77 | 1 | 6 | 8 | 8 | R21F00015 | R21R1F00049;R21R1F00050;R21R1F00051;R21R1F00052;R21R1F00053;R21R1F00054 | 0 | 0 | 1146,1133,1266,1163 | common_core_only:1;single_consensus_bbox:5 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 78 | 1 | 6 | 7 | 7 | R21F00016 | R21R1F00055;R21R1F00056;R21R1F00057;R21R1F00058;R21R1F00059;R21R1F00060 | 1 | 0 | 1146,1247,1164,1271 | multiple_valid_bbox_variants:1;single_consensus_bbox:5 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 79 | 1 | 6 | 8 | 8 | R21F00017 | R21R1F00061;R21R1F00062;R21R1F00063;R21R1F00064;R21R1F00065;R21R1F00066 | 1 | 0 | 1146,1247,1164,1271 | common_core_only:2;single_consensus_bbox:4 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 80 | 1 | 6 | 8 | 8 | R21F00018 | R21R1F00067;R21R1F00068;R21R1F00069;R21R1F00070;R21R1F00071;R21R1F00072 | 1 | 0 | 1146,1133,1266,1163 | common_core_only:1;single_consensus_bbox:5 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 81 | 1 | 4 | 5 | 5 | R21F00019 | R21R1F00073;R21R1F00074;R21R1F00075;R21R1F00076 | 0 | 0 | 1176,1181,1260,1271 | common_core_only:1;single_consensus_bbox:3 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 263 | 1 | 1 | 1 | 1 |  | R21R1F00110 | 0 | 0 | 1069,1135,1218,1261 | single_consensus_bbox:1 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 270 | 1 | 4 | 8 | 8 | R21F00036 | R21R1F00116;R21R1F00117;R21R1F00118;R21R1F00119 | 0 | 0 | 1107,1138,1263,1240 | common_core_only:1;single_consensus_bbox:3 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 271 | 1 | 3 | 8 | 8 | R21F00037 | R21R1F00120;R21R1F00121;R21R1F00122 | 0 | 0 | 1107,1138,1287,1240 | common_core_only:2;single_consensus_bbox:1 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 272 | 1 | 6 | 8 | 8 | R21F00038 | R21R1F00123;R21R1F00124;R21R1F00125;R21R1F00126;R21R1F00127;R21R1F00128 | 1 | 0 | 1107,1138,1251,1240 | common_core_only:1;multiple_valid_bbox_variants:1;single_consensus_bbox:4 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 273 | 2 | 3 | 5 | 5 | R21F00039;R21F00040 | R21R1F00129;R21R1F00130;R21R1F00131 | 0 | 0 | 1115,1140,1259,1266 / 1259,1140,1289,1152 | common_core_only:1;single_consensus_bbox:2 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 289 | 1 | 5 | 8 | 8 | R21F00048 | R21R1F00158;R21R1F00159;R21R1F00160;R21R1F00161;R21R1F00162 | 1 | 0 | 1146,1138,1308,1228 | common_core_only:2;single_consensus_bbox:3 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |
| 290 | 1 | 3 | 7 | 7 | R21F00049 | R21R1F00163;R21R1F00164;R21R1F00165 | 0 | 0 | 1146,1138,1314,1228 | common_core_only:2;single_consensus_bbox:1 | R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。 |

## Focus Conclusions

- 27: the previous single large family is split into spatially consistent response families; the raw-reviewed small box is a member-level/local response object, not inherited as old-family identity.
- 30-32, 34, 39: old broad one-family frames are expanded into multiple independent spatial hypotheses where member pairs fail two-by-two consistency.
- 31: part-only and supported boxes are kept together only when their pairwise relation is legal; otherwise they become separate families.
- 40 and 270-273: multiple families remain valid when pairwise spatial/core evidence supports independent hypotheses.
- 78-81 and 289-290: elongated or background-like responses remain family-level review objects but do not become selector/ranking outputs.
- 263: remains diagnostic-only; no GT or dynamic search shell is used to rescue generation.

## Gate Verdicts

| gate | status | evidence | provenance |
| --- | --- | --- | --- |
| R2_1_FROZEN_ATOMS_UNCHANGED | PASS | R2.1 frozen manifest SHA checks were compared for generation inputs | frozen_input_replay |
| R2_1_FROZEN_CORE_HYPOTHESES_UNCHANGED | PASS | core hypotheses are read-only inputs | frozen_input_replay |
| TARGET_GT_ISOLATION_VALID | PASS | generate reads frozen response boxes/core/atoms/lineage/graph and SAR gray only; GT is evaluate-only | generation_boundary |
| SOURCE_ANCHOR_CONDITIONED_GENERATION | true | R2.1 source shell was already source-anchor-conditioned; R2.1-R1 starts after response boxes | boundary_statement |
| SOURCE_ANCHOR_RUNTIME_AVAILABILITY_EXPLICIT | PASS | source-anchor-conditioned generation is explicitly not an automatic source-anchor-free start | boundary_statement |
| SOURCE_ANCHOR_FREE_AUTOMATIC_START_NOT_PROVEN | true | automatic anchor-free startup is outside R2.1-R1 | boundary_statement |
| EMPTY_OPTIONAL_FIELDS_NOT_USED_FOR_GROUPING | PASS | empty strong_optional equality is recorded as no_optional_evidence and never a valid pair relation | family_builder |
| HYPOTHESIS_FAMILY_GROUPING_VALID | PASS | new families=165 | family_builder |
| FAMILY_PAIRWISE_SPATIAL_CONSISTENCY_VALID | PASS | invalid in-family pairs=0 | family_builder |
| NO_TRANSITIVE_BRIDGE_OVERMERGE | PASS | transitive bridge splits=83 | family_builder |
| SPATIALLY_DISTINCT_MEMBERS_NOT_GROUPED | PASS | spatially_distinct in-family pairs=0 | family_builder |
| FAMILY_REPRESENTATIVE_BBOX_VALID | PASS | boundary statuses single/multi/core/unresolved=117/12/36/0 | family_boundary |
| FAMILY_BOUNDARY_UNCERTAINTY_EXPLICIT | PASS | multiple variants/common-core-only/unresolved are explicit states, not arbitrary first boxes | family_boundary |
| RAW_REVIEW_FAMILY_TARGET_VALID | PASS | raw judgement is family-level and uses R2.1-R1 boundary semantics | blind_review |
| ASSISTED_REVIEW_FAMILY_TARGET_VALID | PASS | assisted judgement is family-level and explanatory | blind_review |
| ASSISTED_NOT_USED_AS_TRUTH | PASS | assisted review is not read by generate and only interpreted post-freeze | blind_review |
| MEMBER_LEVEL_GT_EVALUATION_VALID | PASS | member eval rows=250 | eval_only |
| FAMILY_LEVEL_GT_EVALUATION_VALID | PASS | family eval rows=165 | eval_only |
| NO_ARBITRARY_MEMBER_USED_FOR_FAMILY_EVAL | PASS | family conservative metrics are blank unless status is single_consensus_bbox | eval_only |
| FAMILY_TEMPORAL_GEOMETRY_VALID | PASS | sparse diagnostic family correspondence rows=594 | diagnostic_temporal |
| SPARSE_LINEAGE_SCOPE_EXPLICIT | PASS | output is sparse_diagnostic_family_correspondence, not runtime tracking | diagnostic_temporal |
| WEAK_RESPONSE_TRUNCATION_AUDITED | PASS | top-k audit rows=2368 | audit_only |
| TOP_K_NOT_ASSUMED_SAFE | PASS | TOP_K_WEAK_RESPONSE_RISK=HIGH | audit_only |
| FROZEN_REPLAY_IDENTICAL | PASS | corrected_families:PASS; family_members:PASS; family_pairwise_integrity:PASS; family_boundaries:PASS; sparse_family_temporal_edges:PASS; topk_component_drop_audit:PASS | frozen_replay |
| CORE_RESPONSE_BBOX_R2_1_R1_READY | PARTIAL | integrity repair is complete only as posthoc bbox-family object, not runtime selector | stage_readiness |
| VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2 | NO | R2.1-R1 is not an A1.7R2 runtime contract | stage_boundary |
| GM_RM011_BLOCKED | true | GM_RM011 remains blocked and is outside this task | stage_boundary |

## Replay

- FROZEN_REPLAY_IDENTICAL: `PASS`
- replay evidence: `corrected_families:PASS; family_members:PASS; family_pairwise_integrity:PASS; family_boundaries:PASS; sparse_family_temporal_edges:PASS; topk_component_drop_audit:PASS`

## Created Files

- `reports/oty2/oty2_wgv3_6a_a1_8a_r2_1_r1_family_integrity_fix_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_corrected_families_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_family_members_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_family_pairwise_integrity_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_family_boundaries_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_sparse_family_temporal_edges_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_blind_raw_family_judgement_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_blind_assisted_family_judgement_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_member_gt_evaluation_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_family_gt_evaluation_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_topk_component_drop_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_r2_1_family_delta_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_error_taxonomy_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_gate_integrity_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_frozen_manifest_20260711.csv`