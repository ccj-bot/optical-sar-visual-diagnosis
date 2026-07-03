# OTY2 SAR Structure Representation And Association Provenance Report

Generated: `20260703_112931`

This report consolidates OTY2 structure, temporal, and counterfactual diagnostics into mechanism tables. It does not generate final annotations, selector/ranking output, training, tuned thresholds, or identity truth.

## Ledger Boundary

- paired_optical_object_sar_gt = 215
- blocked_missing_gm011_object_stream = 195
- sar_only_gt = 20
- dropout/no_oty_iou_match/temporal continuation pool = 12

The 215 support-observation rows are state-conditioned paired rows. SAR-only rows are only referenced as a SAR morphology pool in the transition model. Dropout/no-match rows remain temporal continuation or existence support only.

## Key Metrics

- broad_true_topk_contains_near_gt_rate_posthoc: `0.0279`
- state_conditioned_true_topk_contains_near_gt_rate_posthoc: `0.8977`
- state_conditioned_random_topk_contains_near_gt_rate_posthoc: `0.1163`
- state_conditioned_range_shifted_topk_contains_near_gt_rate_posthoc: `0.0419`
- state_conditioned_azimuth_shifted_topk_contains_near_gt_rate_posthoc: `0.7151`
- state_conditioned_wrong_object_topk_contains_near_gt_rate_posthoc: `0.6977`
- state_conditioned_wrong_sar_frame_topk_contains_near_gt_rate_posthoc: `0.9116`
- state_conditioned_support_observation_rows: `215`
- state_conditioned_sar_structure_exists_rate: `1`
- state_conditioned_vehicle_like_structure_exists_rate: `0.9349`
- state_conditioned_unique_structure_exists_rate: `0`
- state_conditioned_association_candidate_exists_rate_posthoc: `0.6884`
- state_conditioned_no_unique_structure_rate: `1`
- state_conditioned_support_too_broad_for_association_rate: `1`

## Main Mechanism Findings

- Candidate is no longer a single box candidate. This run separates optical object hypothesis, support region or feasible domain, SAR scatter-structure candidate or temporal tube, and only then posthoc association candidate.
- State-conditioned true support is stronger than random and range-shift controls, so range/state support contains real posthoc signal.
- Wrong-object and wrong-frame controls remain high; this is object-time association confounding, not a reason to declare the SAR image path failed.
- Azimuth-shift remains high, so azimuth cannot be used as a strong gate before sector overlap and margin behavior are explained.

## Line A: SAR Structure Vocabulary

The vocabulary separates compact clusters, multi-peak clusters, range/azimuth spread, diffuse clutter, weak/no-structure, jumping peaks, stable tubes, and diffuse/unstable tubes. These fields are mechanism observations and must not be promoted to selector features.

## Line B: Support Region To Structure Observation

The support table uses the 215 state-conditioned paired rows and keeps five states separate: support exists, SAR structure exists, vehicle-like structure exists, unique SAR structure exists, and posthoc association candidate exists.

## Line C: Structure By Counterfactual Cross-Check

True support is clearly stronger than random and range-shift controls, which supports real range/state signal. Wrong-object, wrong-frame, and azimuth-shift remain high enough to require provenance and confounder modeling rather than a SAR-route rejection.

## Line D: SAR Temporal Tube Probe

Temporal rows distinguish stable cluster tubes, jumping peaks, diffuse/unstable tubes, and dropout existence support. Existing inputs do not yet provide explicit range-extent or azimuth-extent stability, so those columns are marked partial instead of fabricated.

## Line E: Association Provenance And Failure Transition

The provenance matrix separates runtime-safe optical/time/geometry/state constraints from SAR image observation, SAR temporal observation, posthoc GT validation, and review anchors. The failure-transition table keeps associated_posthoc_candidate as a posthoc state only, not identity truth.

## Why This Is Not A Local Top-K/Selector Optimization

1. This run introduces no selector/ranking, no candidate scoring, no final box, no training, and no threshold tuning.
2. It is not looking for a better top-k metric; it reframes the current evidence into SAR structure vocabulary, temporal tube behavior, counterfactual provenance, and failure transitions.
3. It explains wrong-object, wrong-frame, and azimuth-shift high hits as object-time/overlap/temporal confounding that must be modeled before association.
4. It produces reusable vocabulary, provenance, and transition tables that can be checked across samples.
5. GT-near top-k, GT-inside support, state-conditioned range success, and associated_posthoc_candidate remain posthoc hypotheses and cannot enter runtime prior construction.
6. The next expansion should add motion/temporal-change gates and visual exemplars, not tune a single metric.

## Partial Data Limitations

- Existing temporal-tube CSV does not contain explicit range-extent or azimuth-extent stability columns; those fields are marked partial.
- Current support-observation rows reuse state-conditioned posthoc range bands; they are not runtime range rules.
- Wrong-object and azimuth overlap buckets come from separate triage outputs and are not available for every raw counterfactual row.
- GM_RM019 review candidate extraction is not opened in this run; it remains a next-step quality anchor, not an annotation proposal.

## Posthoc Hypotheses Only

- GT-near top-k and GT-inside support remain validation metrics.
- State-conditioned range success remains a posthoc hypothesis until derived from runtime-safe optical-only evidence.
- Associated posthoc candidate is an explanatory state, not identity truth.
- SAR structure vocabulary fields are mechanism observations, not selector features.

## Next Steps

- Inspect visual exemplars for compact, multi-peak, spread, diffuse, and stable-tube categories.
- Add motion/drift compatibility gates that can explain wrong-frame persistence.
- Audit azimuth overlap and sector-margin behavior before using azimuth as a strong gate.
- Run a small GM_RM019 optical object continuity review as a separate quality anchor.
- Recover GM_RM011 object stream only as a later scale-expansion step.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- existing_sar_image_observation_reused: `true`
- new_sar_image_extraction_entered: `false`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- gt_peak_or_residual_written_to_runtime_prior: `false`
- state_conditioned_topk_written_as_runtime_rule: `false`
- annotation_proposal_entered: `false`
- final_candidate_box_output: `false`
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

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_sar_structure_representation_and_association_provenance_plan.md`
- sar_structure_vocabulary_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_structure_vocabulary_20260703_112931.csv`
- support_region_structure_observation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_structure_observation_20260703_112931.csv`
- structure_counterfactual_crosscheck_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_structure_counterfactual_crosscheck_20260703_112931.csv`
- structure_temporal_tube_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_structure_temporal_tube_probe_20260703_112931.csv`
- association_provenance_matrix_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_association_provenance_matrix_20260703_112931.csv`
- failure_transition_table_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_failure_transition_table_20260703_112931.csv`
- sar_structure_representation_and_association_provenance_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_structure_representation_and_association_provenance_report_20260703_112931.md`
- sar_structure_representation_and_association_provenance_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_structure_representation_and_association_provenance_summary_20260703_112931.json`
- workspace_log: `D:\profile\research\workspace\logs\oty2_sar_structure_representation_and_association_provenance_20260703_112931.log`

## Sources

- scatter_cluster_structure_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_scatter_cluster_structure_probe_20260703_095159.csv`
- temporal_cluster_association_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_cluster_association_probe_20260703_095159.csv`
- counterfactual_support_validation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_support_validation_20260703_102237.csv`
- counterfactual_confounder_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_confounder_triage_20260703_105108.csv`
- wrong_object_overlap_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wrong_object_overlap_triage_20260703_105108.csv`
- wrong_frame_offset_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wrong_frame_offset_triage_20260703_105108.csv`
- azimuth_shift_overlap_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_azimuth_shift_overlap_triage_20260703_105108.csv`
- gated_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gated_association_scatter_cluster_summary_20260703_095159.json`
- parallel_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_parallel_mechanism_exploration_summary_20260703_102237.json`
- confounder_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_confounder_triage_summary_20260703_105108.json`
