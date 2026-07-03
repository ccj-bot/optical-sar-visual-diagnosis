# OTY2 Parallel Mechanism Exploration Report

Generated: `20260703_102237`

This bootstrap runs counterfactual / negative-control support validation. It does not generate annotation proposals, selector/ranking outputs, training, tuned thresholds, or identity truth.

## Ledger Boundary

- paired_optical_object_sar_gt = 215
- blocked_missing_gm011_object_stream = 195
- sar_only_gt = 20
- dropout/no_oty_iou_match/temporal continuation pool = 12

Counterfactual rows use paired optical-object/SAR-GT rows for broad_fan_baseline and state_conditioned_range_band. Dropout/no-match rows are not mixed into clean morphology; SAR-only and GM_RM011 blocked rows are not used for optical-SAR correspondence.

## Key Metrics

- broad_true_topk_contains_near_gt_rate_posthoc: `0.0279`
- broad_average_negative_topk_contains_near_gt_rate_posthoc: `0.0166`
- state_conditioned_true_topk_contains_near_gt_rate_posthoc: `0.8977`
- state_conditioned_average_negative_topk_contains_near_gt_rate_posthoc: `0.4965`
- state_conditioned_random_topk_contains_near_gt_rate_posthoc: `0.1163`
- state_conditioned_azimuth_shifted_topk_contains_near_gt_rate_posthoc: `0.7151`
- state_conditioned_range_shifted_topk_contains_near_gt_rate_posthoc: `0.0419`
- state_conditioned_wrong_object_topk_contains_near_gt_rate_posthoc: `0.6977`
- state_conditioned_wrong_sar_frame_topk_contains_near_gt_rate_posthoc: `0.9116`

## Required Answers

1. For state-conditioned support, true top-k near-GT rate is 0.8977 versus average negative-control rate 0.4965; true support is clearly above random and range-shift controls, but wrong-object or wrong-frame controls remain high and expose association-risk pseudo signal. Broad true support remains weak at 0.0279.
2. If true and negative controls are close, the likely pseudo-signal is broad support area, same-scene object confusion, or frame-insensitive SAR scattering: strong background or neighboring-object peaks can appear inside many supports without proving association.
3. State-conditioned true support is compared with azimuth-shifted=0.7151, range-shifted=0.0419, random=0.1163, wrong-object=0.6977, and wrong-frame=0.9116. Its strongest separation is radial/state versus range-shift and random controls; wrong-object and wrong-frame need gate-provenance follow-up.
4. Broad support spans the full fan radius with large area, so local peak/background and top1/top2 competition mostly describe SAR clutter and sidelobe competition, not precise localization.
5. State-conditioned true support scatter mix is {"azimuth_spread_cluster": 139, "compact_cluster": 2, "range_spread_cluster": 21, "diffuse_clutter": 33, "multi_peak_nearby_cluster": 20}. Compact, multi-peak nearby, and stable tube patterns are more interpretable than diffuse or jumping peaks.
6. The strongest runtime-safe optical cues remain time, fan azimuth, object/state uncertainty, and vehicle-shell assumptions. Bbox-height/radius, scene residual, and object-smoothed range trend remain posthoc hypotheses.
7. GT-near top-k, GT-inside support, object-smoothed GT range, and scene residual are posthoc. Time, optical object stream, azimuth mapping, state labels, and vehicle physical shell have runtime-safe potential.
8. Next priority should be counterfactual gate provenance plus SAR scatter-structure modeling. GM_RM019 review should support object-hypothesis quality; GM_RM011 object-stream recovery is the scale-expansion blocker.

## Provenance Boundary

Conclusions use provenance labels: `runtime_safe_optical_evidence`, `runtime_safe_temporal_evidence`, `runtime_safe_geometry_or_vehicle_physics`, `SAR_image_observation`, `SAR_temporal_observation`, `SAR_GT_posthoc_evidence`, `manual_or_review_anchor`, `hypothesis_to_validate`, and `insufficient_or_not_supported`.

GT-near peak and GT-inside support metrics are posthoc diagnostics only. They are not written into runtime prior construction.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- topk_peak_gt_distance_used_for_posthoc_diagnosis: `true`
- negative_control_support_constructed: `true`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- gt_peak_or_residual_written_to_runtime_prior: `false`
- annotation_proposal_entered: `false`
- candidate_box_scoring_output: `false`
- selector_or_ranking_used: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- model_weights_committed: `false`
- matlab_zip_or_any_zip_committed: `false`
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`

## Bootstrap Blockers

- range_shifted_support blocked for P00001 mode=broad_fan_baseline multiplier=-1.5; full or clamped range band
- range_shifted_support blocked for P00001 mode=broad_fan_baseline multiplier=1.5; full or clamped range band
- range_shifted_support blocked for P00006 mode=broad_fan_baseline multiplier=-1.5; full or clamped range band
- range_shifted_support blocked for P00006 mode=broad_fan_baseline multiplier=1.5; full or clamped range band
- range_shifted_support blocked for P00011 mode=broad_fan_baseline multiplier=-1.5; full or clamped range band
- range_shifted_support blocked for P00011 mode=broad_fan_baseline multiplier=1.5; full or clamped range band
- range_shifted_support blocked for P00016 mode=broad_fan_baseline multiplier=-1.5; full or clamped range band
- range_shifted_support blocked for P00016 mode=broad_fan_baseline multiplier=1.5; full or clamped range band
- range_shifted_support blocked for P00021 mode=broad_fan_baseline multiplier=-1.5; full or clamped range band
- range_shifted_support blocked for P00021 mode=broad_fan_baseline multiplier=1.5; full or clamped range band
- range_shifted_support blocked for P00026 mode=broad_fan_baseline multiplier=-1.5; full or clamped range band
- range_shifted_support blocked for P00026 mode=broad_fan_baseline multiplier=1.5; full or clamped range band

## Outputs

- design_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_parallel_mechanism_exploration_design.md`
- counterfactual_support_validation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_support_validation_20260703_102237.csv`
- negative_control_support_comparison_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_negative_control_support_comparison_20260703_102237.csv`
- sar_scatter_structure_mechanism_notes_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_scatter_structure_mechanism_notes_20260703_102237.csv`
- optical_cue_contribution_sketch_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_cue_contribution_sketch_20260703_102237.csv`
- parallel_mechanism_exploration_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_parallel_mechanism_exploration_report_20260703_102237.md`
- parallel_mechanism_exploration_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_parallel_mechanism_exploration_summary_20260703_102237.json`
- workspace_log: `D:\profile\research\workspace\logs\oty2_parallel_mechanism_exploration_bootstrap_20260703_102237.log`

## Sources

- peak_competition_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_peak_competition_audit_20260703_091849.csv`
- range_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_peak_competition_summary_20260703_091849.json`
- gated_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gated_association_scatter_cluster_summary_20260703_095159.json`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
