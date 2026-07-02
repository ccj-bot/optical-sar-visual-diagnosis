# OTY2 GT 对应机制后验审计报告

生成时间：`20260702_190435`

本轮允许使用 SAR GT 和 SAR 图像内容，但只用于 posthoc mechanism discovery / audit。GT、SAR 图像、覆盖率和后验误差不得写入当前 runtime prior construction。

## 输入边界

- Runtime-safe inputs：光学目标流、时间窗、方位映射、车辆物理尺寸假设、场景几何、目标状态。
- Posthoc-only inputs：SAR GT、SAR 图像内容、GT 覆盖率、人工最终框、后验 IoU、选择器结果。
- 本报告使用 posthoc-only inputs 做机制发现，不输出自动标注建议，不训练或调阈值，不输出候选框评分，不声明身份真值。

## 样本

- GT 对应样本数：`215`。
- 场景分布：`{"GM_RM017": 199, "GM_RM019": 16}`。
- 配对跳过统计：`{"missing_object_frame:GM_RM011": 195, "missing_review_optical_bbox_or_saronly": 20, "no_iou_match_ge_0.05:GM_RM017": 6, "no_iou_match_ge_0.05:GM_RM019": 6}`。
- 配对方法：同一场景、同一光学帧，用 review_queue 光学框与 OTY1t 主观测框 IoU 匹配；这是后验对应假设，不是身份真值。

## 方位映射覆盖

- 方位扇区覆盖：`{"total": 215, "pass": 205, "fail": 9, "pass_rate": 0.9534883720930233}`。
- 方位扇区宽度中位数：`80.013` 度。
- GT 方位相对先验中心误差中位数：`-3.4095` 度。
解释：当前方位扇区通常较宽，覆盖率主要说明“方位映射是否把 GT 放进大扇区”，不能等同为精定位成功。失败样本需要结合边缘、遮挡、重复、交接和远小状态继续审阅。

## 车辆物理尺度壳

- relaxed/base 尺度壳覆盖：`{"total": 215, "pass": 215, "fail": 0, "pass_rate": 1.0}`。
- base 尺度壳覆盖：`{"total": 215, "pass": 215, "fail": 0, "pass_rate": 1.0}`。
- SAR GT 长轴/短轴/长短比中位数：`161.0` / `74.5` / `2.1628`。
- 尺度壳角宽 / 当前方位扇区宽度中位比例：`0.46130000000000004`。
观察：车辆尺度壳对目标 footprint 尺寸有明显约束，和方位扇区相交时有压缩潜力；但没有运行时 range anchor 时，它不能单独给出绝对距离位置。

## 光学框形态和距离向探索

- 光学框面积比例 vs SAR GT 半径 Pearson：`-0.7384331151126269`。
- 光学框高度 vs SAR GT 半径 Pearson：`-0.8417789316036687`。
- 光学框 bottom_y_norm vs SAR GT 半径 Pearson：`-0.7722411362128231`。
- posthoc 光学面积 bin 范围壳覆盖：`{"total": 215, "pass": 169, "fail": 46, "pass_rate": 0.786046511627907}`。
- 对象时序趋势状态：`{"opposite_sign_area_radius_trend_posthoc": 205, "weak_or_flat_temporal_trend": 3, "insufficient_temporal_pairs": 1, "same_sign_area_radius_trend_posthoc": 6}`。
解释：这些相关和范围壳都是后验机制探针，不是 runtime 回归器。若趋势较弱或受状态破坏，下一步应先分完整/遮挡/截断/远小目标，再评估是否有可迁移的弱先验。

## SAR 散射和 GT 框形态

- box/background 强度比中位数：`1.133634`。
- peak/background 强度比中位数：`3.241493`。
观察：GT 框内通常能看到局部峰值和车辆长轴 footprint，但框内均值可能受背景、彩色显示映射、散射外溢和遮挡影响。此处只支持机制观察，不能直接成为评分器。

## YOLO A/B 建议

不建议直接替换主线 YOLO。下一步可以做小样本 A/B：同一帧、同一 vehicle-like 主线，比较主研究车辆覆盖、远小弱目标比例、框稳定性、轨迹连续性、duplicate/handoff、光学形态与 SAR GT 机制变量相关性、方位扇区覆盖率和尺度壳覆盖/压缩率。

## 远端代表样例

| role | scene | object | sar_gt_id | sar_frame | azimuth | size_shell | range_shell | path |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| 仅审阅车辆后验样本 | GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0008 | 95 | 302 | true | true | false | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\gt_correspondence_mechanism_visualizations\gt_mechanism_20260702_190435\oty2_gt_mechanism_review_only_gm_rm017_0008_sar000302_95_20260702_190435.png` |
| 弱车覆盖样本 | GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0010 | 99 | 315 | true | true | true | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\gt_correspondence_mechanism_visualizations\gt_mechanism_20260702_190435\oty2_gt_mechanism_weak_vehicle_covered_gm_rm017_0010_sar000315_99_20260702_190435.png` |
| 范围壳失败样本 | GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0008 | 105 | 321 | true | true | false | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\gt_correspondence_mechanism_visualizations\gt_mechanism_20260702_190435\oty2_gt_mechanism_range_shell_fail_gm_rm017_0008_sar000321_105_20260702_190435.png` |
| 方位覆盖失败样本 | GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0014 | 269 | 383 | false | true | false | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\gt_correspondence_mechanism_visualizations\gt_mechanism_20260702_190435\oty2_gt_mechanism_azimuth_fail_gm_rm017_0014_sar000383_269_20260702_190435.png` |
| GM_RM019 后验样本 | GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0001 | 309 | 0 | true | true | false | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\gt_correspondence_mechanism_visualizations\gt_mechanism_20260702_190435\oty2_gt_mechanism_gmrm019_gm_rm019_0001_sar000000_309_20260702_190435.png` |
| GM_RM019 方位失败样本 | GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0005 | 319 | 77 | false | true | true | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\gt_correspondence_mechanism_visualizations\gt_mechanism_20260702_190435\oty2_gt_mechanism_gmrm019_azimuth_fail_gm_rm019_0005_sar000077_319_20260702_190435.png` |

## 输出和数据源

- final_gt_csv: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv`
- review_queue_csv: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\review_queue.csv`
- spatial_priors_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_runtime_spatial_priors_20260702_144929.csv`
- temporal_windows_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- vehicle_eligibility_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_vehicle_research_eligibility_audit_20260702_180326.csv`
- object_frame_state_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- local_full_visual_output: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_gt_correspondence_mechanism_audit_20260702_190435`

## Boundary Flags

- sar_gt_used: `true`
- sar_image_content_used: `true`
- posthoc_mechanism_discovery_only: `true`
- gt_or_sar_used_for_runtime_prior_construction: `false`
- automatic_annotation_proposal_generated: `false`
- training_or_threshold_tuning_entered: `false`
- candidate_box_scoring_output: `false`
- selector_or_ranking_used: `false`
- identity_truth_claimed: `false`
- model_weights_committed_or_downloaded: `false`
