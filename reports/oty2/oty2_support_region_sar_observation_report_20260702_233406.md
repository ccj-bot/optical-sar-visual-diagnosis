# OTY2 Support-Region SAR Observation Probe Report

Generated: `20260702_233406`

This report audits optical-derived SAR support regions and SAR observation extraction. It does not generate final boxes, annotation proposals, selector/ranking output, training, tuned thresholds, or identity truth.

## Ledger Boundary

- paired_optical_object_sar_gt = 215
- blocked_missing_gm011_object_stream = 195
- sar_only_gt = 20
- dropout/no_oty_iou_match/temporal continuation pool = 12

The 215 paired rows are validation rows for optical-object/SAR-GT posthoc correspondence. GM_RM011 is blocked by missing current OTY object stream, not by missing annotation. SAR-only rows are not mixed into optical-SAR correspondence. Dropout rows are excluded from clean morphology.

## Support Region Contract

```text
tau0(t) = 50/24 * t + Delta_s
tau in [tau0 - jitter, tau0 + jitter]
C_o,t,tau = C_time intersect C_az intersect C_shell intersect C_state
```

In this run, `C_az` comes from optical bbox x coordinates and configured fan-polar mapping. `C_state` widens the sector for edge/truncated, duplicate/handoff, review-only, far-small/weak, and dropout states. `C_shell` is recorded as a vehicle-footprint constraint, but it cannot localize range because the current runtime range prior is `broad_unknown_range_prior`.

## Key Metrics

- paired_frame_rows: `215`
- clean_complete_frame_rows: `103`
- dropout_special_pool_rows: `12`
- paired_support_observation_extract_rate: `1`
- clean_support_observation_extract_rate: `1`
- paired_gt_inside_support_posthoc_rate: `0.9628`
- clean_gt_inside_support_posthoc_rate: `0.9223`
- paired_peak_to_background_median: `1.9265`
- clean_peak_to_background_median: `2.0265`
- window_stability_rate: `1`
- tracklet_gt_inside_support_posthoc_rate: `0.9628`

## Required Answers

1. Support-region SAR observation was extracted for 215/215 paired rows and 103/103 clean-complete rows. Median paired peak/background is 1.9265. This confirms that coarse optical-derived sectors can be observed in SAR images, but broad_unknown_range_prior means the peak is support evidence, not a final box.
2. Short windows produced 227/227 stable peak-or-centroid labels. Median window peak/background is 1.9414. They are more useful than a single frame for continuity checks, but the current broad range support can still track clutter peaks.
3. Tracklet-to-SAR-frame support contains the posthoc GT in 207/215 paired validation rows. Because 50/24 maps most paired frames close to an observed optical frame, interpolation is a modest stabilizer now; it becomes more important for in-between SAR frames and dropout/edge states.
4. Tube rows generated: 10 with status counts {"sar_tube_centroid_continuity_observed": 9, "dropout_pool_temporal_continuation_supported_but_not_clean_tube": 1}. The tube formulation is feasible as an observation probe, but range-broad support prevents treating centroid drift as precise vehicle localization.
5. State widening is required for edge/truncated, duplicate/handoff, review-only, far-small/weak, and dropout/no-match rows. Frame state counts: {"complete": 103, "edge_or_truncated": 58, "duplicate_or_handoff": 17, "ambiguous_or_review_only": 37, "dropout_or_no_match": 12}.
6. GM_RM019 objects 0001, 0005, 0009, 0080, and 0098 remain review-relevant, with 0005 and 0080 especially useful for continuity/complete-frame checks. GM_RM011 needs object stream recovery, not SAR relabeling.
7. Next priority should be support-region peak extraction first, then SAR temporal peak tracking on the extracted observations, while GM_RM019 manual review and GM_RM011 object-stream recovery proceed as data-quality tracks.

## Current Blocker

Current OTY2 inputs expose azimuth sectors but no runtime-safe per-object SAR range prior; support regions are broad fan sectors.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- annotation_proposal_entered: `false`
- training_or_threshold_tuning_entered: `false`
- candidate_box_scoring_output: `false`
- selector_or_ranking_used: `false`
- identity_truth_claimed: `false`
- model_weights_committed: `false`
- matlab_zip_or_any_zip_committed: `false`
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`
- support_region_uses_sar_gt: `false`
- support_region_uses_gt_crop: `false`

## Outputs

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_optical_to_sar_support_region_observation_probe_plan.md`
- optical_frame_to_sar_frame_support_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_frame_to_sar_frame_support_probe_20260702_233406.csv`
- optical_frame_to_sar_window_support_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_frame_to_sar_window_support_probe_20260702_233406.csv`
- optical_tracklet_to_sar_frame_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_tracklet_to_sar_frame_probe_20260702_233406.csv`
- optical_tracklet_to_sar_tube_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_tracklet_to_sar_tube_probe_20260702_233406.csv`
- support_region_sar_observation_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_sar_observation_summary_20260702_233406.json`
- support_region_sar_observation_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_sar_observation_report_20260702_233406.md`
- workspace_log: `D:\profile\research\workspace\logs\oty2_support_region_sar_observation_probe_20260702_233406.log`

## Sources

- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- spatial_priors_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_runtime_spatial_priors_20260702_144929.csv`
- temporal_windows_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- object_frame_state_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- object_ledger_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_level_factor_evidence_ledger_20260702_222218.csv`
- manual_review_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_manual_review_candidate_list_20260702_222218.csv`
- dropout_temporal_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_detection_dropout_temporal_support_audit_20260702_200455.csv`
- dropout_sar_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_detection_dropout_sar_posthoc_support_audit_20260702_200455.csv`
- physical_model_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_model_form_summary_20260702_224649.json`
- final_gt_csv: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv`
