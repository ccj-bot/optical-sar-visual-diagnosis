# OTY2 WGV3.6A-A1.8A-R2 Core Response BBox Audit

## Boundary

- requested start commit: `87433c986779cb77624e652822db12e6e3b2511e`
- commands: `generate`, `blind-raw-pack`, `blind-assisted-pack`, `evaluate`, `verify-replay`; no `all` command.
- generate reads R1 frozen atoms/roles/lineage, A1.7R source shells, SAR grayscale, and static fan geometry only.
- evaluate reads GT, discovery label, vehicle identity, and bbox relation only after raw and assisted blind judgement freeze.
- final annotation space: `SAR image pixel domain`; meter fields are explanatory only.
- GM_RM011 executed: `false`

## Frozen SHA

- `causal_shell`: `df75a11b18bd09f1fe9dbf30f589d746610167de81a9609f18e6aa94323efd0f`
- `atom_nodes`: `20b9ce683a1290c909c120d7c67a3bdf783f7e56eaf73cecff1ceab4c71c71d5`
- `atom_edges`: `815c488ccb7cdea83c6e7abebb751f1af4029c0d3674a0d97a74d943ebe68e4f`
- `core_hypotheses`: `a921d6b1d192cc62ddd8b9ce37097d057e9d4178dc4f51862b7a33a49c1d3d6e`
- `core_gates`: `7846eb5f8940547c8768b87e2e5246ac94d7e718c6fab5772b8edb4ba7ddb2fa`
- `optional_membership`: `9318ebabec65734695a8ad2bffce7a6376f36eaa4a5944eed83295696738e5a0`
- `frozen_boxes`: `c8b61ab2fcd93b81a9bf95002586f9f4b7ef4acda295ff7207cf404be0d051e3`
- `bbox_temporal`: `71e16f4a365487a4e9a31c1b9a66fa1e55c22638a384a98cf726990a33e830d9`
- `FROZEN_REPLAY_IDENTICAL`: `PASS`
- replay evidence: `causal_shell:PASS; atom_nodes:PASS; atom_edges:PASS; core_hypotheses:PASS; core_gates:PASS; optional_membership:PASS; frozen_boxes:PASS; bbox_temporal:PASS`

## Source Shell Causality

- previous R1 future-source cases corrected: `11`
| sar_frame | selected_source_frame | source_is_historical | source_lag_frames | previous_r1_source_frame | r1_used_future_source | corrected_shell_provenance | gate_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 27 | true | 3 | 31 | true | causal_a1_7r_source_shell_frame_27 | PASS |
| 60 | 31 | true | 29 | 77 | true | causal_a1_7r_source_shell_frame_31 | PASS |
| 227 | 212 | true | 15 | 238 | true | causal_a1_7r_source_shell_frame_212 | PASS |
| 228 | 212 | true | 16 | 238 | true | causal_a1_7r_source_shell_frame_212 | PASS |
| 259 | 238 | true | 21 | 269 | true | causal_a1_7r_source_shell_frame_238 | PASS |
| 260 | 238 | true | 22 | 269 | true | causal_a1_7r_source_shell_frame_238 | PASS |
| 262 | 238 | true | 24 | 269 | true | causal_a1_7r_source_shell_frame_238 | PASS |
| 263 | 238 | true | 25 | 269 | true | causal_a1_7r_source_shell_frame_238 | PASS |
| 272 | 269 | true | 3 | 273 | true | causal_a1_7r_source_shell_frame_269 | PASS |
| 281 | 273 | true | 8 | 288 | true | causal_a1_7r_source_shell_frame_273 | PASS |
| 284 | 273 | true | 11 | 288 | true | causal_a1_7r_source_shell_frame_273 | PASS |

## Runtime Core And Box Counts

- graph role counts: `{'core_member_candidate': 120, 'optional_support_candidate': 74, 'conflicting_background_candidate': 8}`
- core candidates per frame: `{'27': 2, '28': 2, '29': 2, '30': 2, '31': 1, '32': 1, '34': 3, '39': 3, '40': 3, '46': 1, '52': 1, '60': 2, '77': 2, '78': 2, '79': 2, '80': 2, '81': 2, '212': 1, '216': 1, '224': 1, '227': 1, '228': 1, '239': 1, '259': 2, '260': 1, '262': 1, '263': 1, '269': 2, '270': 2, '271': 2, '272': 2, '273': 1, '276': 2, '278': 2, '279': 2, '280': 2, '281': 3, '284': 2, '288': 2, '289': 2, '290': 1}`
- core relation counts: `{'compact_partial_body': 38, 'weak_part_only': 14, 'core_to_endpoint': 11, 'side_to_endpoint': 4, 'core_to_side': 4}`
- isolated_small_atom non-veto core boxes: `42`
- core-vs-full compactness split: `core_compact_pass=71; optional_excluded_or_uncertain=98; high_blank_optional_if_full_group=77`
- optional membership counts: `{'exclude_from_bbox': 40, 'uncertain_bbox_membership': 58, 'include_in_bbox': 132}`
- response boxes: `71`
- box status counts: `{'vehicle_response_box_supported': 8, 'vehicle_response_box_possible': 39, 'vehicle_part_box_only': 0, 'background_box': 0, 'unresolved_box': 24}`
- bbox width median px/m: `150` / `4.5`
- bbox height median px/m: `120` / `3.6`

## Blind Review

- raw judgement counts: `{'vehicle_part': 46, 'background': 10, 'unresolved': 15}`
- assisted judgement counts: `{'vehicle_core': 55, 'vehicle_part': 4, 'background': 1, 'unresolved': 11}`
- raw judgement SHA: `999cf05ad086b243461973453c780492ed9c2c7abdf43ae3f09aa5f5005367b4`
- assisted judgement SHA: `e820e3e03decf5d8d051d4e09d7d3f1ae021903c9e6c6dbe74c93a66167329fc`

## Error Taxonomy

- error type counts: `{'no_error_taxonomy_flag': 56, 'blind_confirmed_vehicle_miss': 12, 'runtime_blind_vehicle_disagreement': 12, 'gt_overlap_but_blind_unresolved': 3}`
| case_id | response_box_id | sar_frame | error_type | reason | provenance |
| --- | --- | --- | --- | --- | --- |
| R2ERR0001 | R2B0001 | 27 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=overlaps_gt_eval_only | eval_only_gt_assisted |
| R2ERR0002 | R2B0002 | 27 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=overlaps_gt_eval_only | eval_only_gt_assisted |
| R2ERR0003 | R2B0003 | 28 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0004 | R2B0004 | 28 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0005 | R2B0005 | 29 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0006 | R2B0006 | 29 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0007 | R2B0007 | 30 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0008 | R2B0008 | 30 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0009 | R2B0009 | 31 | blind_confirmed_vehicle_miss | blind_confirmed_vehicle_miss: status=unresolved_box; assisted=vehicle_part; gt_relation=overlaps_gt_eval_only | eval_only_gt_assisted |
| R2ERR0010 | R2B0009 | 31 | runtime_blind_vehicle_disagreement | runtime_blind_vehicle_disagreement: status=unresolved_box; assisted=vehicle_part; gt_relation=overlaps_gt_eval_only | eval_only_gt_assisted |
| R2ERR0011 | R2B0010 | 32 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=unresolved_box; assisted=background; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0012 | R2B0011 | 34 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0013 | R2B0012 | 34 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0014 | R2B0013 | 34 | no_error_taxonomy_flag | no_error_taxonomy_flag: status=vehicle_response_box_possible; assisted=vehicle_part; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0015 | R2B0014 | 39 | blind_confirmed_vehicle_miss | blind_confirmed_vehicle_miss: status=unresolved_box; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0016 | R2B0014 | 39 | runtime_blind_vehicle_disagreement | runtime_blind_vehicle_disagreement: status=unresolved_box; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0017 | R2B0015 | 39 | blind_confirmed_vehicle_miss | blind_confirmed_vehicle_miss: status=unresolved_box; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| R2ERR0018 | R2B0015 | 39 | runtime_blind_vehicle_disagreement | runtime_blind_vehicle_disagreement: status=unresolved_box; assisted=vehicle_core; gt_relation=no_exact_gt_for_frame | eval_only_gt_assisted |
| ... |  |  |  |  |  |

## Focus Window Conclusions

- 27-31: core-only compactness separates body/endpoint support from isolated small atoms; isolated atoms no longer globally veto the core.
- 78-81: core boxes preserve lower vehicle-part responses while background arcs stay excluded from response bboxes.
- 270-273: several boxes remain part-only or possible; the method does not claim a complete vehicle response.
- 289-290: the accepted local body/side core differs from the long weak side-line unresolved alternative by body support and optional membership.
- 263: acceptance remains unsupported when assisted review is unresolved and no exact GT is available.

## Gate Verdicts

| gate | status | evidence | provenance |
| --- | --- | --- | --- |
| GENERATION_GT_ISOLATION_VALID | PASS | generate reads R1 frozen atoms/roles/lineage plus A1.7R source shells only | runtime_safe |
| SOURCE_SHELL_CAUSALITY_VALID | PASS | historical shell selected for all frames; previous R1 future-source cases=11 | runtime_safe |
| POLARITY_NOT_USED_IN_GENERATE | PASS | positive/negative labels are loaded only in evaluate through eval_label | runtime_safe |
| CORE_SUBGRAPH_INDEPENDENT_OF_OPTIONAL_ATOMS | PASS | core gates are computed before optional membership | runtime_safe |
| ISOLATED_ATOM_NOT_GLOBAL_VETO | PASS | accepted/possible/part core boxes with isolated_small_atom in surrounding group=42 | runtime_safe |
| CORE_COMPACTNESS_LOCAL_VALID | PASS | compactness uses core-only member gaps and distances | runtime_safe |
| CORE_TEMPORAL_LINEAGE_VALID | PASS | temporal gate uses core member persistent_part_track_id only | runtime_safe |
| BACKGROUND_CONFLICT_EXPLICIT | PASS | optional background exclusions=17 | runtime_safe |
| IMAGE_DOMAIN_BBOX_GENERATED | PASS | response boxes=71; final_annotation_space=sar_image_pixel_domain | runtime_safe |
| OPTIONAL_RESPONSE_MEMBERSHIP_AUDITED | PASS | optional membership rows=230 | runtime_safe |
| RAW_BLIND_REVIEW_FROZEN | PASS | raw rows=71; sha=999cf05ad086b243461973453c780492ed9c2c7abdf43ae3f09aa5f5005367b4 | blind_visual_review |
| ASSISTED_REVIEW_SEPARATED | PASS | assisted rows=71; sha=e820e3e03decf5d8d051d4e09d7d3f1ae021903c9e6c6dbe74c93a66167329fc | blind_visual_review |
| FROZEN_REPLAY_IDENTICAL | PASS | verify-replay compares all R2 frozen runtime artifacts | runtime_safe |
| ERROR_TAXONOMY_VALID | PASS | error taxonomy rows=83 | eval_only_gt_assisted |
| CORE_RESPONSE_BBOX_R2_READY | PARTIAL | core subgraph bbox logic is local-window validated but not full-scene annotation | eval_only_gt_assisted |
| VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2 | NO | R2 remains audit-only; final annotation/selector/training still blocked | eval_only_gt_assisted |
| GM_RM011_BLOCKED | true | GM_RM011 not executed | eval_only_gt_assisted |

## Created Files

- `reports/oty2/oty2_wgv3_6a_a1_8a_r2_core_response_bbox_audit_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_causal_source_shell_audit_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_atom_graph_nodes_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_atom_graph_edges_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_core_subgraph_hypotheses_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_core_subgraph_gates_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_optional_response_membership_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_frozen_response_boxes_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_bbox_temporal_consistency_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_blind_raw_judgement_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_blind_assisted_judgement_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_gt_assisted_bbox_evaluation_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_error_taxonomy_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_gate_integrity_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_frozen_artifact_manifest_20260711.csv`

## Research Judgment

R2 fixes source-shell causality and moves vehicle response reasoning from whole atom groups to local core subgraphs plus optional bbox membership. The result is still an audit artifact, not final annotation, selector, ranking, training data, or A1.7R2-ready observation input.