# OTY2 Object SAR Temporal Window Quality Audit

Generated: `20260702_142454`

This audit reviews temporal-window quality only. It does not read SAR images, use SAR GT, generate SAR spatial regions, score candidates, rank hypotheses, tune thresholds, or create annotation proposals.

## Inputs Reviewed

- source temporal windows: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- object rows reviewed: `27`
- generated object-level SAR temporal windows: `18`
- normal downstream spatial-constraint inputs: `11`
- review-only temporal contexts: `7`
- blocked spatial inputs: `10`

## Per-Scene Results

| scene | object rows | generated windows | normal downstream inputs | review-only windows | blocked/not-ready rows | width min/median/max | blocker |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `GM_RM011` | 0 | 0 | 0 | 0 | 1 | `n/a` | `missing_oty0;missing_oty1;missing_oty1a;missing_oty1t;missing_p4g_object_hypotheses;missing_p4g_object_frame_states` |
| `GM_RM017` | 6 | 6 | 5 | 1 | 0 | `26/133.5/160` | `` |
| `GM_RM019` | 21 | 12 | 6 | 6 | 9 | `14/88.0/145` | `` |

## Window Width by Object State

| object_state_category | count | width min/median/max | interpretation |
| --- | ---: | --- | --- |
| `ambiguous_review_required` | 7 | `28/105.0/145` | kept as low-confidence review windows with the largest temporal padding |
| `secondary_edge_handoff_uncertainty` | 7 | `87/107.0/160` | expanded margins preserved for secondary, edge, duplicate, partial, occlusion, or handoff uncertainty |
| `stable_primary_continuity` | 4 | `14/23.0/106` | stable primary windows are generally narrower; width can still grow when the optical object span is long |

## Checks

- width status counts: `{"compact_temporal_constraint": 6, "normal_temporal_constraint": 6, "not_applicable_no_object_flow": 1, "not_applicable_not_ready": 9, "wide_but_bounded_review": 6}`
- formula status counts: `{"not_applicable_no_object_flow": 1, "not_applicable_not_ready": 9, "pass_50_24_formula": 16, "pass_50_24_formula_with_inventory_clamp": 2}`
- fps-ratio status counts: `{"metadata_available_24_50_software_sync": 1, "not_applicable_not_ready": 9, "pass_50_over_24_mapping": 18}`
- narrowness status counts: `{"not_applicable_no_object_flow": 1, "not_applicable_not_ready": 9, "not_too_narrow_formula_padding_ok": 16, "not_too_narrow_inventory_start_or_end_clamped": 2}`
- padding policy status counts: `{"not_applicable_no_object_flow": 1, "not_applicable_not_ready": 9, "pass_expected_state_padding": 18}`

Findings:

- No generated window violated the 50/24 conversion check.
- No generated window was flagged as too narrow under the audit padding policy.
- No generated window crossed the hard overwide review band that would remove temporal constraint value.
- Wide-but-bounded windows are driven by long optical spans or uncertainty padding and remain below the scene-level overwide band.
- Stable primary windows have a lower median width than secondary/edge/handoff and ambiguous windows.
- Short/noise objects remain blocked before downstream spatial constraint construction.
- GM_RM011 keeps usable temporal metadata but has no object-level optical flow, so it has no target-level temporal-window input.

## Artifact

- quality_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_quality_audit_20260702_142454.csv`

## Boundary Flags

- sar_image_content_used: `false`
- sar_spatial_search_entered: `false`
- sar_search_region_generated: `false`
- sar_candidate_boxes_generated: `false`
- sar_gt_used: `false`
- final_manual_oracle_review_runtime_fields_used: `false`
- selector_or_ranking_used: `false`
- annotation_proposal_entered: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- detection_box_level_merge_reintroduced: `false`
