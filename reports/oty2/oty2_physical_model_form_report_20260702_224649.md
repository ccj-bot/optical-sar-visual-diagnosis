# OTY2 Physical Model Form Audit Report

生成时间：`20260702_224649`

本报告推进到 `physical feasible-domain + SAR observation confirmation` 模型形式。它不是正式 OTY3，不输出最终自动标注，不做 selector/ranking，不训练或调阈值，不声明 identity truth。

## Ledger And Boundary

- 442 ledger：`{"blocked_missing_gm011_object_stream": 195, "paired_optical_object_sar_gt": 215, "sar_only_gt": 20, "no_oty_iou_match": 12}`。
- paired frames/object hypotheses：`215` / `9`。
- GM_RM017/GM_RM019 paired split：`{"GM_RM017": 199, "GM_RM019": 16}`。
- GM_RM011 195 条是缺当前 OTY optical object stream，不是未标注。
- SAR-only 20 条只作 SAR morphology/observation reference。
- dropout/no-match 12 条只作 temporal continuation + SAR support 特殊机制池。

## Recommended Model Form

第一阶段定义可行域：

```text
C_o,t = C_time(o,t) intersect C_az(o,t) intersect C_shell(o,t) intersect C_state(o,t)
```

第二阶段在可行域内做 SAR observation confirmation：

```text
X*_o,1:T = argmax_{X_1:T in C_o,1:T} P(I_sar_1:T | X_1:T) P(X_1:T | O_1:T)
```

或能量形式：

```text
argmin E_sar_image(X_1:T) + E_sar_temporal(X_1:T) + E_optical_temporal(X_1:T,O_1:T)
```

## Ten Required Answers

1. A flat weighted sum mixes different semantics: time/azimuth/shell/state are feasible-domain constraints, SAR image/temporal evidence are observation likelihoods, and SAR GT/review are posthoc validation. A single score can hide GT leakage, over-count GM_RM017 repeated frames, and treat dropout like clean morphology.
2. C_time, C_az, C_shell, and C_state should define the feasible SAR support. F_range_shape can only be a soft range-uncertainty modulator in reviewed complete states, not a hard domain constraint yet.
3. F_sar_image and F_sar_temporal should form the SAR observation likelihood: peak/background, box/background, scatter concentration, centroid residual, long/short-axis morphology, and mainlobe/sidelobe-like diagnostics extracted inside optical-derived support regions.
4. F_az, F_shell, F_range_shape, F_traj, F_sar_image, and F_sar_temporal all need state conditioning. Complete, edge/truncated, far-small, dropout, duplicate/handoff, SAR-only, GM_RM019, and GM_RM011 cannot share one global rule.
5. Object-level dynamic modeling is needed for tracklets with multiple frames, especially state-mixed GM_RM017 objects, sparse/low-azimuth GM_RM019 objects, and dropout/no-match existence recovery. Single-frame optical box to single-frame SAR GT is the wrong unit.
6. Graph matching is needed when multiple optical object hypotheses, partial boxes, duplicate/handoff, or SAR scattering tubes compete for explanation, especially GM_RM019 and dropout cases. It is a future global explanation form, not a selector implemented here.
7. GM_RM017 scene/object rows provide many posthoc residual candidates but are state-mixed and GM_RM017-dominant. GM_RM019 object 0005/0080 are useful review-gated candidates but have low azimuth coverage/sparse frames. Anchors can estimate latent residuals, not copy labels.
8. SAR GT coverage, GT-crop peak/centroid drift, GT-crop box/background, manual/review anchors, SAR-only morphology, dropout SAR support, and MATLAB imaging concepts remain posthoc observation or reference-only.
9. Currently supported as model contracts: two-stage feasible-domain plus SAR observation, state conditioning, and dynamic temporal-tube framing. Next-step only: hierarchical scene/object residuals, product-of-experts calibration, graph matching, and anchor residual propagation.
10. For the model itself, the first next step should be runtime support-region SAR peak/centroid extraction because it converts GT-crop SAR evidence into a usable SAR observation layer. GM_RM019 manual optical review is the next data-quality step for ambiguity; GM_RM011 object stream recovery is the next scale-expansion step.

## Current Support

- Current evidence supports the two-stage model as a design contract: temporal pass `0.9953`, azimuth original coverage `0.9535`, tight shell `0.986`, paired peak/background `3.2415`.
- State conditioning is required: `complete=103;edge=58;ambiguous_or_review_only=37;duplicate_or_handoff=17` plus dropout pool `12`.
- Dynamic model is partially supported: `{"review_only_temporal_signal": 4, "center_direction_signal_only": 2, "clean_object_temporal_signal": 1, "insufficient_temporal_pairs": 2}`.
- Anchor propagation is review-gated: `{"scene_anchor_dominant_but_not_global": 1, "scene_anchor_review_needed": 1, "strong_but_review_gated_scene_or_object_anchor": 3, "limited_anchor_low_azimuth_review_needed": 3, "candidate_anchor": 1, "insufficient_anchor": 2, "review_required_before_anchor_propagation": 1}`.

## Next-Step Ranking

1. Runtime support-region SAR peak/centroid extraction: highest priority for the model form because it replaces GT-crop SAR observation with optical-derived support-region observation.
2. GM_RM019 manual optical GT / identity-continuity review: needed before scene/object residual claims and graph matching examples are trusted.
3. GM_RM011 object stream recovery: needed to expand object-level correspondence beyond the current 215 paired frames, using optical data only.

## Outputs

- next_steps_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_physical_factor_model_forms_and_next_steps.md`
- physical_model_form_comparison_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_model_form_comparison_20260702_224649.csv`
- feasible_domain_factor_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_feasible_domain_factor_audit_20260702_224649.csv`
- state_conditioned_model_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_state_conditioned_model_probe_20260702_224649.csv`
- dynamic_sar_observation_model_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_dynamic_sar_observation_model_probe_20260702_224649.csv`
- anchor_propagation_candidate_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_anchor_propagation_candidate_audit_20260702_224649.csv`
- physical_model_form_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_model_form_report_20260702_224649.md`
- physical_model_form_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_model_form_summary_20260702_224649.json`

## Sources

- physical_factor_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_factor_modeling_summary_20260702_222218.json`
- factor_taxonomy_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_factor_evidence_taxonomy_20260702_222218.csv`
- joint_factor_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_joint_factor_probe_20260702_222218.csv`
- object_ledger_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_level_factor_evidence_ledger_20260702_222218.csv`
- sar_temporal_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_temporal_observation_probe_20260702_222218.csv`
- manual_review_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_manual_review_candidate_list_20260702_222218.csv`
- stratified_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_mechanism_stratified_validation_summary_20260702_204915.json`
- az_shell_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_azimuth_vehicle_size_shell_audit_20260702_190435.csv`

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
