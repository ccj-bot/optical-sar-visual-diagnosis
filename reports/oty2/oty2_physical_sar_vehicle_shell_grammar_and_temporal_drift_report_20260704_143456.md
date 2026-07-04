# OTY2 Physical SAR Vehicle Shell Grammar And Temporal Drift Report

Generated: `20260704_143456`

This report expresses SAR vehicle evidence as physical structure grammar plus temporal drift mechanism. It is posthoc diagnosis only: no revised GT, final box, annotation proposal, selector/ranking, training, threshold tuning, best weight, weighted-fusion mainline, or identity truth is produced.

## Ledger Boundary

- 442 = all SAR GT / SAR-side target reference pool
- 215 = current OTY optical-object to SAR-GT frame-level paired pool
- 195 = GM_RM011 blocked_missing_object_stream, not unannotated
- 20 = SAR-only GT, SAR morphology reference only
- 12 = dropout/no_oty_iou_match/temporal continuation special pool

## Why This Is Physical-Structure-First, Not Weighted Fusion

1. This run does no weighted score and no selector.
2. It explains vehicle evidence through `scattering_atom`, `vehicle_part`, and `vehicle_scale_shell_hypothesis`, not through a weighted sum.
3. GT width, height, area, and long/short axes are used as posthoc scale anchors to prevent baby-car promotion.
4. Temporal drift is checked as non-jump / gradual motion, not identity truth.
5. Support miss is explained after GT-anchored shell evidence is described; wrong support is not rescued by support-internal search.
6. Manual review remains required for GT quality uncertainty, weak structures, confounders, support miss, and temporal unavailable cases.
7. Future weighted fusion is allowed only as fallback bookkeeping after physical grammar and temporal drift are understood.

## Vehicle Shell Grammar

- shell case rows: `442`
- dominant shell pattern mix: `strip_plus_endpoint=220;bilateral_edges=130;enclosed_shell=69;weak_boundary_shell=14;side_ridge_shell=4;no_shell=3;block_shell=2`
- vehicle shell supported mix: `yes=262;uncertain=179;no=1`
- GT scale compatible mix: `uncertain=233;yes=206;no=3`
- baby-car risk rows: `3`

Shell grammar reads side ridges, endpoint hotspots, far-side weak returns, discontinuous edges, block/core responses, and GT-scale shell completion as physical relationships. A small peak remains a scattering atom.

## Part Grammar Relations

- relation rows: `1540`
- relation type mix: `upper_lower_edge_relation=273;discontinuous_edge_to_shell_completion=273;range_spread_to_body_core=213;near_field_spread_to_strong_side_response=201;dominant_side_ridge_to_far_side_weak_return=182;left_right_endpoint_relation=182;side_ridge_to_endpoint_hotspot=177;no_clear_part_relation=35;strip_to_block_body=4`
- relation support mix: `yes=967;uncertain=538;no=35`

The strongest human-readable relations are side ridge to endpoint hotspot, discontinuous edge to shell completion, dominant side ridge to weak far-side return, and range spread to body core.

## Physical Structure Failure Modes

- failure rows: `940`
- failure mode mix: `temporal_not_available=227;single_part_no_shell=160;background_line_not_vehicle_shell=129;gt_too_loose_for_structure=129;parts_too_scattered=107;range_spread_without_core=78;gt_boundary_affected=43;gt_too_small_for_structure=36;near_field_spread_unresolved=14;support_miss_structure=11;only_atoms_no_vehicle_scale=3;parts_too_small_baby_car=3`

Failures are explicit: only atoms, single part without shell, parts too small, scattered parts, GT quality uncertainty, support miss, background/road confounders, near-field spread unresolved, or temporal unavailable.

## Temporal Drift Physical Consistency

- temporal rows: `213`
- vehicle-like temporal drift mix: `yes=112;uncertain=101`
- non-jump support mix: `yes=112;no=101`
- background-stable risk mix: `no=211;yes=2`

The available temporal probe uses `-5..+5` offsets. Full `-10/+10` is not available in this artifact and is recorded as a limitation. Temporal drift remains a posthoc mechanism signal, not identity truth.

## Support Failure Physical Explanation

- support explanation rows: `215`
- support miss shell mix: `no=191;uncertain=13;yes=11`
- support failure type mix: `too_broad=128;none=48;support_ok_but_not_exclusive=15;range_misaligned=12;too_narrow=11;support_reconstruction_uncertain=1`

**If GT-anchored vehicle shell is outside support, the correct diagnostic is support construction failure, not support-internal vehicle search.**

## Weighted Fusion Deferred Boundary

- deferred rows: `5`

Conclusion: weighted fusion is deferred. It can only be a bookkeeping / fallback evidence layer after physical shell grammar and temporal drift mechanism are understood.

## Manual Contour Reference

The rough 2026-07-04 human contour markings are used as visual vocabulary only. They reinforce long side ridges, endpoint hotspots, weak far-side returns, and discontinuous shell completion. They are not GT edits, not final boxes, not selector labels, and not identity truth. The temporary marked PNG files are not committed.

## Corrected Or Paused Old Conclusions

- Weighted evidence fusion as a mainline is paused.
- Top-k peak or small component reasoning is kept at scattering atom / vehicle part level.
- Support-internal search is paused when GT-scale shell is outside support.
- Temporal drift supports physical consistency but not identity truth.

## Posthoc Hypotheses Only

- shell grammar labels are posthoc hypotheses
- part relations are posthoc physical explanations
- temporal drift labels are posthoc mechanism support
- support failure labels are support-construction diagnostics
- weighted fusion rows are deferred-boundary bookkeeping only

## Outputs

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_plan.md`
- physical_structure_first_archive_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_physical_structure_first_not_weighted_fusion_archive.md`
- vehicle_shell_grammar_cases_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_vehicle_shell_grammar_cases_20260704_143456.csv`
- vehicle_part_grammar_relations_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_vehicle_part_grammar_relations_20260704_143456.csv`
- physical_structure_failure_modes_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_structure_failure_modes_20260704_143456.csv`
- temporal_drift_physical_consistency_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_drift_physical_consistency_20260704_143456.csv`
- support_failure_physical_explanation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_failure_physical_explanation_20260704_143456.csv`
- weighted_fusion_deferred_boundary_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_weighted_fusion_deferred_boundary_20260704_143456.csv`
- summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_summary_20260704_143456.json`
- visual_atlas_html: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_physical_shell_grammar_temporal_drift_atlas_cn_20260704_143456.html`
- workspace_log: `D:\profile\research\workspace\logs\oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_20260704_143456.log`

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- physical_shell_grammar_entered: `true`
- part_to_shell_relation_diagnostic_entered: `true`
- temporal_drift_mechanism_entered: `true`
- support_failure_physical_explanation_entered: `true`
- weighted_fusion_deferred: `true`
- weighted_fusion_mainline_used: `false`
- best_weight_selected: `false`
- score_proxy_optimization_entered: `false`
- selector_or_ranking_used: `false`
- training_or_threshold_tuning_entered: `false`
- annotation_proposal_entered: `false`
- revised_gt_box_output: `false`
- final_candidate_box_output: `false`
- identity_truth_claimed: `false`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- shell_grammar_written_as_annotation_rule: `false`
- temporal_drift_written_as_identity_truth: `false`
- human_contour_reference_used_as_truth: `false`
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`
- archive_or_old_work_used_as_active_source: `false`
- zip_7z_rar_committed: `false`
