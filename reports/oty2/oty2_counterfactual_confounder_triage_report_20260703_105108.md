# OTY2 Counterfactual Confounder Triage Report

Generated: `20260703_105108`

This report closes the current OTY2 session with a small confounder triage. It reuses existing counterfactual outputs and does not open a new experiment.

## Ledger Boundary

- paired_optical_object_sar_gt = 215
- blocked_missing_gm011_object_stream = 195
- sar_only_gt = 20
- dropout/no_oty_iou_match/temporal continuation pool = 12

This triage reuses the prior counterfactual support validation rows. It does not add new SAR image extraction and does not mix dropout/no-match, SAR-only, or GM_RM011 blocked rows into clean optical-SAR correspondence.

## Key Metrics

- broad_true_topk_contains_near_gt_rate_posthoc: `0.0279`
- state_conditioned_true_topk_contains_near_gt_rate_posthoc: `0.8977`
- state_conditioned_random_topk_contains_near_gt_rate_posthoc: `0.1163`
- state_conditioned_range_shifted_topk_contains_near_gt_rate_posthoc: `0.0419`
- state_conditioned_azimuth_shifted_topk_contains_near_gt_rate_posthoc: `0.7151`
- state_conditioned_wrong_object_topk_contains_near_gt_rate_posthoc: `0.6977`
- state_conditioned_wrong_sar_frame_topk_contains_near_gt_rate_posthoc: `0.9116`

## Confounder Answers

- wrong_frame_confounder: State-conditioned wrong-frame top-k near-GT remains 0.9116. Observed wrong-frame buckets are far_offset_21_50=1. Because high rates persist at the available wrong-frame offsets, the current SAR observation is not time-discriminative enough by itself; it needs temporal-change and object-motion gates.
- wrong_object_confounder: State-conditioned wrong-object top-k near-GT remains 0.6977. Overlap mix is low_overlap_lt_0p25=128;medium_overlap_0p25_0p75=68;high_overlap_ge_0p75=11;no_overlap=8. 79 state-conditioned wrong-object rows have medium/high support overlap, so object confusion/support overlap explains part of the high rate; low-overlap hits still need SAR structure or graph-level disambiguation.
- azimuth_shift_confounder: State-conditioned azimuth-shift top-k near-GT remains 0.7151. High-rate azimuth-shift groups: 9. The shift controls indicate that azimuth alone is weak under current margins; overlap and sector width must be audited before using azimuth as a strong gate.
- range_shift_confounder: State-conditioned true top-k near-GT is 0.8977, while range-shift is 0.0419 and random is 0.1163. This is the clearest discriminative signal, but it is still posthoc because current range bands inherit GT-validated state/shape hypotheses.
- stage_handoff: The closeout should hand off to gate provenance, object-time confounding, SAR scatter-structure mechanism, GM_RM019 review, and GM_RM011 object-stream recovery. It should not continue local top-k/cluster metric tuning.

## Provenance Boundary

All GT-near, GT-inside, and residual-style conclusions are `SAR_GT_posthoc_evidence` and `hypothesis_to_validate`. Runtime-safe potential is limited to optical object stream, timing ratio, fan geometry, state labels, and vehicle physical assumptions.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `false`
- counterfactual_existing_sar_observation_reused: `true`
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

## Outputs

- handoff_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_counterfactual_confounder_triage_and_handoff.md`
- counterfactual_confounder_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_confounder_triage_20260703_105108.csv`
- wrong_object_overlap_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wrong_object_overlap_triage_20260703_105108.csv`
- wrong_frame_offset_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wrong_frame_offset_triage_20260703_105108.csv`
- azimuth_shift_overlap_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_azimuth_shift_overlap_triage_20260703_105108.csv`
- counterfactual_confounder_triage_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_confounder_triage_report_20260703_105108.md`
- counterfactual_confounder_triage_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_confounder_triage_summary_20260703_105108.json`
- workspace_log: `D:\profile\research\workspace\logs\oty2_counterfactual_confounder_triage_20260703_105108.log`

## Sources

- counterfactual_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_support_validation_20260703_102237.csv`
- negative_control_comparison_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_negative_control_support_comparison_20260703_102237.csv`
- parallel_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_parallel_mechanism_exploration_summary_20260703_102237.json`
