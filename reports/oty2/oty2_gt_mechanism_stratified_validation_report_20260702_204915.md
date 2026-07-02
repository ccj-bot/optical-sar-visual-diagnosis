# OTY2 后验机制分层验证与壳压缩消融报告

生成时间：`20260702_204915`

本轮使用 SAR GT 和 SAR 图像内容仅做 posthoc mechanism validation。报告不输出自动标注建议，不做 runtime prior construction，不训练/调阈值，不使用 selector/ranking，不声明身份真值。

## 样本池核验

- 442 GT 总账核验：`true`。
- 类别分账：`{"blocked_missing_gm011_object_stream": 195, "paired_optical_object_sar_gt": 215, "sar_only_gt": 20, "no_oty_iou_match": 12}`。
- 场景分账：`{"GM_RM011": 201, "GM_RM017": 216, "GM_RM019": 25}`。
- 215 paired 是帧级后验配对子集，不是 215 个独立目标。
- 195 GM_RM011 样本因缺当前 OTY 光学对象流被排除出光学-SAR 对应机制；20 SAR-only 只进入 SAR 形态参考；12 dropout/no-match 只作截断/缺检/时序延续机制池。

## Frame-Level / Object-Level

- frame-level clean paired：`215` 帧。
- object-level 聚合对象数：`9`。
- object-level 轨迹可靠性：`{"review_only_temporal_signal": 4, "center_direction_signal_only": 2, "clean_object_temporal_signal": 1, "insufficient_temporal_pairs": 2}`。
- area-vs-radius object trend：`{"opposite_sign_consistent": 6, "same_sign_conflict": 2, "insufficient_temporal_pairs": 1}`。
结论：frame-level 的相关性更强，但 object-level 显示不少趋势来自重复帧和状态混合，不能把 215 帧直接当作独立对象下结论。

## 方位扇区 Margin 消融

- 原始扇区覆盖：`205/215`，覆盖率 `0.9535`，中位宽度 `80.013` 度。
- 固定中心 margin >=90% 覆盖的最小档：`35` 度，覆盖率 `0.9116`。
- 固定中心 margin >=95% 覆盖的最小档：`40` 度，覆盖率 `0.9674`。
- 系统偏移提示：`no_large_median_signed_bias`；原始中位 signed error `-3.41` 度。
结论：方位映射有可压缩空间，但窄 margin 失败呈现 scene/status 依赖，原始结果没有明显整体 signed bias；本报告不选择 runtime margin。

## 车辆尺度壳消融

- `tight_vehicle_shell`：覆盖 `212/215`，覆盖率 `0.986`，中位相交宽度 `26.57` 度，压缩率 `0.6703`。
- `base_vehicle_shell`：覆盖 `215/215`，覆盖率 `1`，中位相交宽度 `30.582` 度，压缩率 `0.6222`。
- `relaxed_vehicle_shell`：覆盖 `215/215`，覆盖率 `1`，中位相交宽度 `37.097` 度，压缩率 `0.544`。
- 需要 relaxed 才能覆盖 tight 失败的对象数：`2`。
- tight 已足够的对象数：`7`。
结论：车辆 footprint 壳能带来后验压缩，但 tight 壳会丢样本，base/relaxed 更适合作为后验机制观察；下一轮若做 runtime candidate，必须用 runtime-safe 输入重新定义。

## 光学框形态与 SAR 半径

- 全局形态关系：`{"bbox_area_ratio": {"pearson": "-0.7384", "stability": "moderate_posthoc_relation"}, "bbox_height": {"pearson": "-0.8418", "stability": "strong_posthoc_relation"}, "bbox_bottom_y_norm": {"pearson": "-0.7722", "stability": "strong_posthoc_relation"}, "bbox_aspect_ratio": {"pearson": "0.1061", "stability": "unstable_or_not_supported"}}`。
- 强/中等分层关系条目数：`63`。
结论：bbox height、area、bottom_y 与 SAR radius 的后验关系较强，但 scene/status/object 分层后会变得不均匀；aspect ratio 不能作为稳定机制。

## 光学时序轨迹

- 轨迹可靠性：`{"review_only_temporal_signal": 4, "center_direction_signal_only": 2, "clean_object_temporal_signal": 1, "insufficient_temporal_pairs": 2}`。
- 有效/近似有效趋势的场景分布：`{"GM_RM017": 3, "GM_RM019": 2}`。
结论：面积/高度/bottom_y 趋势对 review-only 解释有帮助，但仍受单场景、重复帧、截断/边缘/交接影响；不能作为身份真值或 runtime range 规则。

## SAR-Only 形态参考

- SAR-only 数量：`20`，场景分布：`{"GM_RM017": 11, "GM_RM019": 3, "GM_RM011": 6}`。
- GT 长轴/短轴/aspect 中位数：`166.184` / `76.246` / `2.1916`。
- box/background 中位数：`0.958047`；peak/background 中位数：`2.197253`。
- 散射支持分布：`{"weak_or_no_box_mean_support_but_kept_as_sar_only_reference": 8, "local_scatter_peak_supported": 12}`。
结论：SAR-only 支持车辆 footprint + 局部散射峰这一 SAR 侧观察，但不能进入光学映射机制。

## 机制判断

### strongly_supported_posthoc_mechanism
- Sample-pool routing is reproducible: 442 total GT, 215 clean paired frames, 195 GM_RM011 object-stream blockers, 20 SAR-only, and 12 dropout/no-match rows remain separated.
- SAR GT local peak morphology is supported posthoc in paired/SAR-only reference pools, but only as SAR-side morphology evidence.

### weak_but_promising_mechanism
- Azimuth center mapping remains useful, but coverage depends on wide margins; failures are scene/status dependent rather than a simple global signed-bias problem.
- Vehicle footprint shells provide meaningful angular compression when intersected with azimuth sectors; tight shell is not universally safe.
- Optical bbox height, area, and bottom-y have strong overall posthoc radius relation, but transferability depends on scene/status strata.

### unstable_mechanism
- Object-level temporal trajectory is helpful mainly for review/context explanation; repeated frames and state contamination prevent clean runtime claims.
- GM_RM019, review-only, edge, and duplicate/handoff strata are sparse or state-mixed enough that they need separate review before any runtime hypothesis.

### not_supported_mechanism
- BBox aspect ratio is not supported as a stable standalone SAR radius mechanism in this audit.
- Detection-dropout propagation is not a clean paired morphology sample and remains excluded from main statistics.

### candidate_for_future_runtime_validation
- Runtime-safe azimuth mapping plus a vehicle footprint shell may be worth designing as a future candidate, but must be rebuilt without SAR GT/image inputs.
- Optical height/bottom-y/area trends can become hypotheses for future runtime validation only after an independent runtime-safe range cue is defined.

### posthoc_observation_only
- GT coverage does not imply automatic annotation.
- SAR image evidence does not become a runtime prior-construction input.
- Posthoc support does not establish identity truth.

## 输出文件

- stratified_validation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_mechanism_stratified_validation_20260702_204915.csv`
- azimuth_margin_ablation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_azimuth_margin_ablation_20260702_204915.csv`
- vehicle_shell_ablation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_vehicle_shell_ablation_20260702_204915.csv`
- optical_shape_range_stratified_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_shape_range_stratified_probe_20260702_204915.csv`
- temporal_trajectory_mechanism_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_trajectory_mechanism_probe_20260702_204915.csv`
- sar_only_morphology_reference_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_only_morphology_reference_20260702_204915.csv`
- report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_mechanism_stratified_validation_report_20260702_204915.md`
- summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_mechanism_stratified_validation_summary_20260702_204915.json`
- visual_summary_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_mechanism_stratified_validation_visual_summary_20260702_204915.csv`
- local_full_visual_output: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_gt_mechanism_stratified_validation_20260702_204915`
- repo_sample_dir: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\gt_mechanism_stratified_validation\gt_mechanism_stratified_validation_20260702_204915`

## 数据源

- accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- dropout_temporal_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_detection_dropout_temporal_support_audit_20260702_200455.csv`
- final_gt_csv: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv`
- review_queue_csv: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\review_queue.csv`
- spatial_priors_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_runtime_spatial_priors_20260702_144929.csv`
- temporal_windows_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- vehicle_eligibility_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_vehicle_research_eligibility_audit_20260702_180326.csv`
- object_frame_state_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- object_hypotheses_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_hypotheses_generalized.csv`

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
