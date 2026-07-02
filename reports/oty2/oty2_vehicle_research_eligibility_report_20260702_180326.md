# OTY2 车目标准入审计报告

生成时间：`20260702_180326`

本轮聚焦 vehicle / car-like 目标准入、远小目标分层和对象级真实可视化。更高级 YOLO 可能改善检测，但本报告不把“检测到了”直接等同为“适合光学到 SAR 自动标注迁移主研究对象”。

## 边界

- 不读取 SAR 图像内容。
- 不使用 SAR GT。
- 不生成 SAR 搜索区域或候选框。
- 不做候选评分、selector/ranking、训练或阈值调参。
- 不生成自动标注建议，不声明身份真值。
- 不提交或生成模型权重，不声称更强 YOLO 已被验证为改进。

## 总结

- 审计行数：`28`（含第十一场景缺目标流说明行）。
- vehicle-like 对象：`27`。
- 主研究车辆：`2`。
- 弱车目标层：`6`。
- 远小车辆层：`5`。
- 仅审阅车辆：`4`。
- 阻断目标：`11`。

## 每场景准入结果

| scene | total_rows | main_research_vehicle | weak_vehicle_layer | far_small_vehicle_layer | review_only_vehicle | blocked | high_resolvable_vehicle | medium_resolvable_vehicle | low_resolvable_far_vehicle | unresolved_tiny_vehicle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| GM_RM017 | 6 | 2 | 3 | 0 | 1 | 0 | 5 | 1 | 0 | 0 |
| GM_RM019 | 21 | 0 | 3 | 5 | 3 | 10 | 4 | 2 | 4 | 1 |

## 当前弱点在哪里

- 主要弱点不是时间窗。24 fps 到 50 fps 的软件同步换算已经给出目标级雷达帧窗口。
- 主要弱点也不完全是方位向。方位弱先验已能从光学框包络和场景方位映射得到，但远小框、边缘、partial、duplicate、handoff 会导致方位解释变宽或降级。
- 最弱的是距离向。当前非阻断对象仍是 `broad_unknown_range_prior`，缺少运行时安全的 per-object range/depth 几何字段。
- 第二个弱点是目标可解析度。GM_RM019 中有多辆远小车，YOLO 检测存在，但框面积比例很低；它们不应该直接混入主研究流。
- 第三个弱点是目标状态稳定性。短轨迹、含混、多观测、边缘/遮挡对象需要进入弱车层、仅审阅层或阻断层。

## 分层依据

这些阈值是 `audit defaults / audit suggestion`，用于解释分布和挑样例，不是训练阈值，也不是调参结果。

```json
{
  "min_track_frames_for_main_research": 8,
  "short_track_block_frames": 5,
  "unresolved_tiny_area_ratio": 0.0005,
  "far_small_area_ratio": 0.003,
  "medium_area_ratio": 0.02,
  "unresolved_tiny_min_dimension_px": 10.0,
  "far_small_width_px": 40.0,
  "far_small_height_px": 30.0,
  "medium_min_dimension_px": 55.0,
  "low_confidence_median": 0.45
}
```

- 可解析度分层计数：`{"no_object_flow": 1, "high_resolvable_vehicle": 9, "medium_resolvable_vehicle": 3, "blocked_noise_or_short_track": 10, "low_resolvable_far_vehicle": 4, "unresolved_tiny_vehicle": 1}`
- 准入分层计数：`{"blocked_no_object_flow": 1, "weak_vehicle_layer": 6, "main_research_vehicle": 2, "review_only_vehicle": 4, "blocked_vehicle_or_noise": 10, "far_small_vehicle_layer": 5}`
- 空间先验与车辆准入一致性：`{"consistent_blocked": 10, "consistent_but_needs_weak_vehicle_layer": 6, "consistent_main_vehicle": 2, "consistent_review_only": 4, "spatial_prior_available_but_vehicle_admission_demotes_far_small": 2, "spatial_prior_available_but_vehicle_admission_blocks": 1, "needs_manual_audit": 3}`

## 输入部件各自作用

- 光学目标流：提供 object_hypothesis_id、主观测框、辅助观测、帧范围、轨迹长度、置信度和状态标签。它决定这个对象是否有足够稳定的光学证据。
- 主观测框：用于车辆可解析度统计、目标框面积比例、光学截图叠框，以及方位向弱先验来源说明。
- 辅助观测：不直接阻断对象，但会提示 duplicate / handoff / 多观测风险，通常进入弱车层或仅审阅层。
- 时间窗：提供对应 SAR 帧范围，限制“何时看雷达”；它不解决“在哪里找”。
- 场景几何：当前主要提供方位向弱映射；距离向仍缺可运行时使用的对象级几何输入。
- 规则层：把对象分为主研究车辆、弱车层、远小车层、仅审阅和阻断，避免把所有 YOLO 检测都混入主研究对象。

## 代表样例

| sample_role | scene | object_hypothesis_id | class_name | resolvability_tier | vehicle_research_eligibility | spatial_prior_status | repo_sample_visualization_path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 第十一场景说明 | GM_RM011 |  |  | no_object_flow | blocked_no_object_flow | blocked_missing_object_level_flow | D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\vehicle_research_eligibility_visualizations\vehicle_eligibility_20260702_180326\oty2_vehicle_eligibility_gmrm011_no_object_flow_gm_rm011_sceneonly_20260702_180326.png |
| 宽松空间先验车辆 | GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0010 | car | high_resolvable_vehicle | weak_vehicle_layer | loose_spatial_prior_generated | D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\vehicle_research_eligibility_visualizations\vehicle_eligibility_20260702_180326\oty2_vehicle_eligibility_relaxed_spatial_vehicle_gm_rm017_bt0010_20260702_180326.png |
| 清晰主研究车辆 | GM_RM017 | oty1t_obj_GM_RM017_bytetrack_bt_0001 | truck | high_resolvable_vehicle | main_research_vehicle | normal_spatial_prior_generated | D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\vehicle_research_eligibility_visualizations\vehicle_eligibility_20260702_180326\oty2_vehicle_eligibility_clear_main_vehicle_gm_rm017_bt0001_20260702_180326.png |
| 阻断目标 | GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0009 | car | blocked_noise_or_short_track | blocked_vehicle_or_noise | blocked_no_spatial_prior | D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\vehicle_research_eligibility_visualizations\vehicle_eligibility_20260702_180326\oty2_vehicle_eligibility_blocked_target_gm_rm019_bt0009_20260702_180326.png |
| 远小车辆 | GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0042 | car | low_resolvable_far_vehicle | far_small_vehicle_layer | loose_spatial_prior_generated | D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\vehicle_research_eligibility_visualizations\vehicle_eligibility_20260702_180326\oty2_vehicle_eligibility_far_small_vehicle_gm_rm019_bt0042_20260702_180326.png |
| 仅审阅车辆 | GM_RM019 | oty1t_obj_GM_RM019_bytetrack_bt_0001 | car | high_resolvable_vehicle | review_only_vehicle | review_only_spatial_context_generated | D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\vehicle_research_eligibility_visualizations\vehicle_eligibility_20260702_180326\oty2_vehicle_eligibility_review_only_vehicle_gm_rm019_bt0001_20260702_180326.png |

## 第十一场景

GM_RM011 的时间元数据可用，可以沿用 24:50 软件同步契约；但当前缺光学目标流，所以不能生成对象级车辆准入、目标级雷达时间窗映射或对象级空间先验。报告和样例图单独把这件事标出来，不把它混入目标级结果。

## 对后续 SAR 搜索的影响

- 主研究车辆可以作为后续空间约束设计的优先对象。
- 弱车目标层需要更大的方位余量或先人工审阅状态，不适合作为干净主样本直接汇总。
- 远小车辆层应该保留记录，但如果全部放入主研究，会增加宽未知距离向和弱方位先验的比例，使后续 SAR 搜索约束失去研究解释性。
- 仅审阅和阻断对象不应进入正常 downstream 主结果。

## 输出

- 本地全量对象图目录：`D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_vehicle_research_eligibility_visual_diagnosis_20260702_180326`
- 审计 CSV：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_vehicle_research_eligibility_audit_20260702_180326.csv`
- 摘要 JSON：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_vehicle_research_eligibility_summary_20260702_180326.json`
- YOLO 升级 A/B 计划：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_yolo_upgrade_ablation_plan_20260702_180326.md`

## 数据源

- spatial_priors_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_runtime_spatial_priors_20260702_144929.csv`
- temporal_windows_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- temporal_quality_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_quality_audit_20260702_142454.csv`
- object_frame_state_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- object_hypotheses_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_hypotheses_generalized.csv`
- manifest_csv: `D:\profile\research\optical-sar-visual-diagnosis\manifests\oty0_yolo_manifest.csv`
- yolo_class_counter: `{"GM_RM019:car": 654, "GM_RM019:bus": 12, "GM_RM019:truck": 2, "GM_RM017:truck": 58, "GM_RM017:bus": 4, "GM_RM017:car": 153}`
- temporal_quality_rows_loaded: `28`

## Boundary Flags

- sar_image_content_used: `false`
- sar_gt_used: `false`
- sar_spatial_search_region_generated: `false`
- sar_candidate_boxes_generated: `false`
- candidate_box_scoring_used: `false`
- annotation_proposal_generated: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- detection_box_level_merge_reintroduced: `false`
- stronger_yolo_claimed_validated_improvement: `false`
- model_weights_committed_or_generated: `false`
