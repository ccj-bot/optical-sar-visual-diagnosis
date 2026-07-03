# OTY2 Range Narrowing And Peak Competition Audit Report

Generated: `20260703_091849`

This report audits posthoc range-band hypotheses and peak competition inside optical-derived SAR support regions. It does not generate final boxes, annotation proposals, selector/ranking output, training, tuned thresholds, or identity truth.

## Ledger Boundary

- paired_optical_object_sar_gt = 215
- blocked_missing_gm011_object_stream = 195
- sar_only_gt = 20
- dropout/no_oty_iou_match/temporal continuation pool = 12

GM_RM011 remains blocked by missing current OTY object stream. SAR-only rows are not mixed into optical-SAR correspondence. Dropout/no-match rows remain outside clean paired morphology.

## Key Metrics

- broad_gt_coverage_paired_posthoc: `0.9628`
- broad_median_area_px: `551070`
- broad_serious_peak_competition_rate: `1`
- state_conditioned_gt_coverage_paired_posthoc: `0.9116`
- state_conditioned_area_ratio_vs_broad_median: `0.1587`
- object_smoothed_gt_coverage_paired_posthoc: `0.9626`
- object_smoothed_area_ratio_vs_broad_median: `0.1118`
- scene_residual_gt_coverage_paired_posthoc: `0.9628`
- scene_residual_area_ratio_vs_broad_median: `0.114`

## Mode Comparison

- broad_fan_baseline: paired coverage `0.9628`, median area ratio `1`, serious peak competition `1`, boundary `runtime-safe broad support baseline from prior probe`.
- complete_shape_quantile_range_band: paired coverage `0.9029`, median area ratio `0.0433`, serious peak competition `1`, boundary `posthoc hypothesis audit only; complete rows only`.
- object_smoothed_range_band: paired coverage `0.9626`, median area ratio `0.1118`, serious peak competition `1`, boundary `posthoc object trend diagnostic, not identity truth`.
- scene_residual_range_band: paired coverage `0.9628`, median area ratio `0.114`, serious peak competition `1`, boundary `posthoc scene residual diagnostic; GT residual not runtime prior`.
- state_conditioned_range_band: paired coverage `0.9116`, median area ratio `0.1587`, serious peak competition `1`, boundary `posthoc hypothesis audit of state uncertainty, not runtime rule`.

## Required Answers

1. The broad fan support preserves posthoc coverage, but it covers a large radial sector. Baseline median support area is 551070 px and serious peak competition rate is 1; therefore the observed top peak can be a competing clutter or sidelobe peak rather than a unique target localization.
2. State-conditioned narrowing has paired GT coverage 0.9116 with median area ratio 0.1587 versus broad fan. Object-smoothed narrowing has paired GT coverage 0.9626 with median area ratio 0.1118.
3. State-conditioned range band is the most physically interpretable next form because it separates complete, edge/truncated, duplicate, far-small, and dropout uncertainty. Complete-shape quantile is useful only for complete/stable rows, while scene residual remains posthoc diagnostic only.
4. Peak competition is nontrivial: broad fan serious competition rate is 1, with median top1/top2 ratio 1.004. This should be treated as SAR observation uncertainty, not a selector score.
5. Broad fan short-window persistence rate is 0.8722; state-conditioned short-window persistence rate is 0.7709. Tube continuity for state-conditioned rows is 0.125.
6. Complete rows can use narrower range bands. Edge/truncated rows need wider bands because optical box height/bottom are partial. Duplicate/handoff rows need review-conditioned widening. Dropout/no-match rows stay outside clean morphology and should use temporal continuation plus SAR support only.
7. The selected shape feature `bbox_height_px`, all shape-radius quantile bands, object-smoothed radius trends, and scene residual bands are posthoc observations. They must not be written back into runtime prior construction without a separate runtime-safe derivation.
8. Next priority should be runtime-safe range hypothesis design from optical-only geometry/state, then SAR temporal peak tracking. GM_RM019 review should proceed to confirm optical object continuity and complete frames; GM_RM011 object-stream recovery remains the scale-expansion blocker.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- posthoc_shape_radius_relation_used_for_hypothesis_audit: `true`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- sar_gt_residual_written_to_runtime_prior: `false`
- support_region_uses_gt_crop: `false`
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

## Outputs

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_support_region_range_narrowing_and_peak_competition_plan.md`
- range_band_mode_comparison_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_band_mode_comparison_20260703_091849.csv`
- support_region_peak_competition_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_peak_competition_audit_20260703_091849.csv`
- state_conditioned_range_band_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_state_conditioned_range_band_probe_20260703_091849.csv`
- object_smoothed_range_band_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_smoothed_range_band_probe_20260703_091849.csv`
- range_narrowing_tube_continuity_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_tube_continuity_probe_20260703_091849.csv`
- range_narrowing_peak_competition_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_peak_competition_report_20260703_091849.md`
- range_narrowing_peak_competition_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_peak_competition_summary_20260703_091849.json`
- workspace_log: `D:\profile\research\workspace\logs\oty2_range_narrowing_peak_competition_audit_20260703_091849.log`

## Sources

- frame_support_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_frame_to_sar_frame_support_probe_20260702_233406.csv`
- window_support_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_frame_to_sar_window_support_probe_20260702_233406.csv`
- tracklet_tube_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_tracklet_to_sar_tube_probe_20260702_233406.csv`
- support_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_sar_observation_summary_20260702_233406.json`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- manual_review_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_manual_review_candidate_list_20260702_222218.csv`
