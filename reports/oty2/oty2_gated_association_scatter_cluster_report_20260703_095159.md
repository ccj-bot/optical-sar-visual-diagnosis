# OTY2 Gated Association And Scatter-Cluster Audit Report

Generated: `20260703_095159`

This report audits top-k SAR scatter clusters, temporal cluster stability, optical-state gates, and posthoc gated association states. It does not generate final annotations, selector/ranking output, training, tuned thresholds, or identity truth.

## Ledger Boundary

- paired_optical_object_sar_gt = 215
- blocked_missing_gm011_object_stream = 195
- sar_only_gt = 20
- dropout/no_oty_iou_match/temporal continuation pool = 12

GM_RM011 remains blocked by missing current OTY object stream. SAR-only rows are not mixed into optical-SAR correspondence. Dropout/no-match rows remain outside clean paired morphology.

## Key Metrics

- broad_mode_paired_source_rows: `215`
- broad_mode_dropout_source_rows: `12`
- broad_paired_top1_near_gt_rate_posthoc: `0.0093`
- broad_paired_topk_contains_near_gt_rate_posthoc: `0.0279`
- broad_paired_top2_or_top3_nearer_rate_posthoc: `0.2186`
- state_conditioned_topk_contains_near_gt_rate_posthoc: `0.8977`
- clean_topk_contains_near_gt_rate_posthoc: `0.7685`
- paired_multiple_topk_peaks_near_gt_rate_posthoc: `0.7661`

## Row Expansion Note

CSV rows are support-mode-expanded diagnostics. The underlying sample pools remain 215 paired rows and 12 dropout/no-match rows; repeated rows across broad/state/object/scene modes are not new samples.

## Required Answers

1. On broad paired rows, top1-near-GT rate is 0.0093, top-k contains a near-GT peak at 0.0279, and top2/top3 is nearer than top1 at 0.2186. This confirms that top1 alone is not a reliable center diagnostic.
2. Scatter structure mix is {"diffuse_clutter": 196, "azimuth_spread_cluster": 600, "weak_no_structure": 28, "compact_cluster": 8, "range_spread_cluster": 91, "multi_peak_nearby_cluster": 63}. The classes are SAR observation diagnostics inside support regions, not selector outcomes.
3. Temporal cluster labels are {"jumping_peak": 6, "insufficient_temporal_samples": 10, "diffuse_or_unstable_cluster_tube": 8, "stable_cluster_tube": 29}. Stable cluster tubes are separated from jumping or diffuse tubes before any association status is assigned.
4. Complete rows can accept the strongest posthoc association only when cluster and temporal gates pass. Edge/truncated rows stay weak or relaxed, duplicate/handoff and review-only rows require review, and dropout rows are existence support only.
5. Gated association status counts are {"rejected_for_temporal_instability": 162, "associated_posthoc_weak": 554, "rejected_for_peak_competition": 5, "associated_posthoc_strong": 7, "optical_support_present_but_sar_ambiguous": 18, "review_required": 75, "sar_structure_present_but_optical_ambiguous": 141, "dropout_existence_support_only": 24}. These are posthoc association states, not final annotations and not identity truth.

## Provenance Boundary

Conclusions use these provenance labels: `runtime_safe_optical_evidence`, `runtime_safe_temporal_evidence`, `SAR_image_observation`, `SAR_temporal_observation`, `SAR_GT_posthoc_evidence`, `manual_or_review_anchor`, `hypothesis_to_validate`, and `insufficient_or_not_supported`.

Top-k peak distances to GT are posthoc diagnostics. They are not written into runtime prior construction and do not select a final target center.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- topk_peak_gt_distance_used_for_posthoc_diagnosis: `true`
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

- idea_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_gated_association_scatter_cluster_exploration_idea.md`
- topk_peak_gt_posthoc_diagnosis_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_topk_peak_gt_posthoc_diagnosis_20260703_095159.csv`
- scatter_cluster_structure_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_scatter_cluster_structure_probe_20260703_095159.csv`
- temporal_cluster_association_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_cluster_association_probe_20260703_095159.csv`
- optical_state_gate_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_state_gate_probe_20260703_095159.csv`
- gated_association_scatter_cluster_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gated_association_scatter_cluster_report_20260703_095159.md`
- gated_association_scatter_cluster_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gated_association_scatter_cluster_summary_20260703_095159.json`
- workspace_log: `D:\profile\research\workspace\logs\oty2_gated_association_scatter_cluster_audit_20260703_095159.log`

## Sources

- peak_competition_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_peak_competition_audit_20260703_091849.csv`
- range_tube_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_tube_continuity_probe_20260703_091849.csv`
- range_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_peak_competition_summary_20260703_091849.json`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
