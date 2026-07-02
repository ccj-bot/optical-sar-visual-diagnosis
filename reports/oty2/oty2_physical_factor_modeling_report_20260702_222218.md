# OTY2 Physical Factor Modeling Report

生成时间：`20260702_222218`

本报告是 OTY2 physical factor evidence ledger / mechanism modeling report。它使用 SAR GT、SAR 图像和人工/review 信息只做 posthoc validation 与 SAR observation 分层记录；不生成最终自动标注，不做 selector/ranking，不训练或调阈值，不声明 identity truth。

## 样本总账

- 442 ledger：`{"blocked_missing_gm011_object_stream": 195, "paired_optical_object_sar_gt": 215, "sar_only_gt": 20, "no_oty_iou_match": 12}`。
- paired frame-level rows：`215`；object hypotheses：`9`。
- 场景 paired：`{"GM_RM017": 199, "GM_RM019": 16}`。
- 状态分布：`complete=103;edge=58;ambiguous_or_review_only=37;duplicate_or_handoff=17`。
- GM_RM011 的 195 条是 blocked_missing_object_stream，不是未标注；SAR-only 20 条只作 SAR morphology reference；dropout/no-match 12 条只作特殊机制池。

## 核心量化结果

- F_time：temporal window pass rate `0.9953`，使用 24fps -> 50fps 软件同步 temporal tube。
- F_az：original interval pass `0.9535`；40deg fixed margin pass `0.9674`；GM_RM019 是弱场景。
- F_shell：tight/base/relaxed pass `0.986` / `1` / `1`；tight miss 仍有信息量。
- F_range_shape：area/height/bottom_y/aspect vs SAR radius Pearson `-0.7384` / `-0.8418` / `-0.7722` / `0.1061`。
- F_traj：object-level trajectory reliability `{"review_only_temporal_signal": 4, "center_direction_signal_only": 2, "clean_object_temporal_signal": 1, "insufficient_temporal_pairs": 2}`；area-vs-radius object trend `{"opposite_sign_consistent": 6, "same_sign_conflict": 2, "insufficient_temporal_pairs": 1}`。
- F_sar_image：paired peak/background median `3.2415`；paired box/background median `1.1336`；SAR-only local peak supported `12/20`。

## 十个问题回答

1. F_time, broad F_az, F_shell compression, F_range_shape for height/bottom_y/area, and F_sar_image local peak evidence. Paired peak/background median=3.2415; temporal window pass=0.9953.
2. F_az and F_range_shape are state/scene conditioned; GM_RM019, edge, duplicate/handoff, review-only, and dropout rows need wider uncertainty or separate routing.
3. Mainlobe/sidelobe, IRW/PSLR/ISLR/ENL-like metrics, SAR scattering centroid drift, and scene-level bias have SAR imaging explanations but need non-GT region extraction and more balanced objects.
4. Use F_az+F_shell+F_sar_image, F_range_shape+F_traj, F_traj+SAR temporal peak drift, and dropout+optical continuation+SAR support as joint probes.
5. Results are dominated by GM_RM017 and repeated frame-level rows: 199/215 paired frames are GM_RM017, while object hypotheses total only 9.
6. GM_RM019 needs optical-side continuity/identity review for sparse objects, weak azimuth coverage, partial/edge/duplicate states, and six dropout/no-match cases.
7. GM_RM011 needs OTY optical object stream recovery for 195 blocked rows; it is not unannotated and cannot be mixed into clean paired correspondence yet.
8. F_time, F_az, F_shell, F_state, and optical trajectory features can become runtime-safe candidates; F_range_shape needs an independent runtime-safe range hypothesis first.
9. SAR GT coverage, GT-crop SAR image statistics, manual review anchors, SAR-only morphology, dropout SAR support, and shape-radius correlations remain posthoc observations.
10. The MATLAB toolbox inspires range-azimuth grids, focusing, local peak, mainlobe/sidelobe, IRW/PSLR/ISLR/ENL, and motion-compensation vocabulary, but it is similar_imaging_reference_only because its raw data, parameters, axes, frame rate, and preprocessing are not the current OTY2 pipeline.

## 边界与下一步

- 可以进入未来 runtime-safe factor 的方向：F_time、F_az、F_shell、F_state、光学对象轨迹；F_range_shape 需要独立 runtime-safe range hypothesis 后再验证。
- 仍只能作为 posthoc observation 的内容：SAR GT 覆盖率、GT crop SAR 图像统计、SAR-only morphology、dropout SAR support、manual/review anchors、shape-radius 后验相关。
- GM_RM019：补少量手动光学 GT / identity-continuity review，用于确认 object hypothesis、轨迹方向和完整形态帧；不声明身份真值。
- GM_RM011：补 OTY optical object stream；不能把 195 blocked rows 混入 clean paired mechanism statistics。
- MATLAB imaging code：只作为 similar_imaging_reference_only；不要提交 zip，不假设同 pipeline。

## 输出文件

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_object_sar_physical_mechanism_modeling_plan.md`
- physical_factor_evidence_taxonomy_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_factor_evidence_taxonomy_20260702_222218.csv`
- joint_factor_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_joint_factor_probe_20260702_222218.csv`
- object_level_factor_evidence_ledger_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_level_factor_evidence_ledger_20260702_222218.csv`
- sar_temporal_observation_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_temporal_observation_probe_20260702_222218.csv`
- manual_review_candidate_list_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_manual_review_candidate_list_20260702_222218.csv`
- physical_factor_modeling_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_factor_modeling_report_20260702_222218.md`
- physical_factor_modeling_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_physical_factor_modeling_summary_20260702_222218.json`

## 数据源

- stratified_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_mechanism_stratified_validation_summary_20260702_204915.json`
- stratified_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_mechanism_stratified_validation_20260702_204915.csv`
- azimuth_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_azimuth_margin_ablation_20260702_204915.csv`
- shell_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_vehicle_shell_ablation_20260702_204915.csv`
- shape_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_shape_range_stratified_probe_20260702_204915.csv`
- temporal_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_trajectory_mechanism_probe_20260702_204915.csv`
- sar_only_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_only_morphology_reference_20260702_204915.csv`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- correspondence_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_summary_20260702_190435.json`
- dropout_temporal_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_detection_dropout_temporal_support_audit_20260702_200455.csv`
- dropout_sar_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_detection_dropout_sar_posthoc_support_audit_20260702_200455.csv`
- accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`

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
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`
