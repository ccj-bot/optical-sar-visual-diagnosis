# GM_RM019 静态 SAR 物理观测场冻结 S1

日期：`20260712`

## 状态

`STATIC_PHYSICAL_FIELD_READY`

OTY2（Optical Timeline Y2，光学时序辅助阶段二）本轮完成 S1（Stage 1，阶段一）冻结。SAR（Synthetic Aperture Radar，合成孔径雷达）灰度响应、本轮固定几何和冻结局部响应对象已经生成 GT 无关的 physical observation field。GT（Ground Truth，真值标注）不会在本轮生成阶段打开；S2（Stage 2，阶段二）才会打开 GT 相关引用做反事实可辨识性评价。

## 项目确认标定

- calibration_status = `PROJECT_CONFIRMED`
- max_range_m = `40.0`
- radial_grid_spacing_m_per_px = `0.03`
- sar_fan_center = `(1154.0, 1330.6)`
- 本轮直接使用这些项目确认参数，不再把主要工作变成尺度来源审计。

## 生成封印

- generate 只读取 SAR 灰度图、local_response_units、boundary_variant_families 与本脚本固定参数。
- `gt_file_opened=false`、`paired_annotations_opened=false`、`mask_audit_opened=false` 已写入对象行和 pre-eval seal。
- 显示扇形边界字段只表示 display fan context，不代表 R2C pair-level MASK（掩膜）语义。

## 冻结对象统计

- frozen response unit: `250`
- independent conservative geometry: `215`
- counterfactual template rows: `9000`
- threshold rows: `750`
- scale-yaw rows: `250`
- counterfactual template bank 本轮只给出 GT 无关固定模板和冻结场代理变化量；S2 正式打开 GT/邻域区域后必须重新计算区域能量变化。

## 主要描述统计

|summary_id|metric|count|mean|median|min|max|notes_cn|
|---|---|---|---|---|---|---|---|
|FIELD_NUMERIC|absolute_range_m|250|4.618258|4.38394|2.104187|7.736485|physical observation field描述统计|
|FIELD_NUMERIC|range_p80_width_m|250|1.367047|0.921395|0.095201|3.538813|physical observation field描述统计|
|FIELD_NUMERIC|azimuth_p80_width_m|250|1.577525|1.176829|0.09842|3.843956|physical observation field描述统计|
|FIELD_NUMERIC|principal_axis_angle_to_range_deg|250|54.23991|61.44578|0.073471|89.843151|physical observation field描述统计|
|FIELD_NUMERIC|scale_yaw_residual_m|250|1.510877|1.827444|0.002171|3.154541|physical observation field描述统计|
|FIELD_NUMERIC|min_extra_blur_margin_m|250|0|0|0|0|physical observation field描述统计|
|FIELD_NUMERIC|distance_to_fan_boundary_m|250|3.114|2.718|1.458|5.808|physical observation field描述统计|
|THRESHOLD_NUMERIC|threshold_stability_count|250|2.968|3|2|3|每个对象三档固定阈值中核心连通分量持续存在的次数|
|THRESHOLD_NUMERIC|principal_axis_angle_std_deg|250|3.81161|2.119371|0.080379|21.146384|主轴角跨阈值稳定性|
|SHAPE_CLASS|azimuth_dominant|105|||||range/azimuth p80米制展宽的形状代理分类|
|SHAPE_CLASS|near_isotropic|122|||||range/azimuth p80米制展宽的形状代理分类|
|SHAPE_CLASS|range_dominant|23|||||range/azimuth p80米制展宽的形状代理分类|
|SCALE_YAW|vehicle_scale_yaw_feasible_count|98|||||软尺度-yaw一致性描述量，不是车辆确认或selector|
|DISPLAY_FAN|touches_display_fan_boundary_count|0|||||显示扇形上下文，不是R2C pair-level物理MASK语义|

## vehicle-scale-yaw 一致性

- feasible count: `98` / `250`
- 该字段是静态响应代理量，不是车辆确认、selector 或 ranking。

## 阈值稳定性

- threshold_stability_count median: `3`
- principal_axis_angle_std_deg median: `2.119371`

## 显示扇形边界上下文

- touches_display_fan_boundary: `0` / `250`
- 该字段来自扇形显示几何，不是物理成像有效 MASK 确认，也不是 R2C 的 S1/S2 pair-level 语义。

## 典型支持样本

|response_unit_id|sar_frame|range_p80_width_m|azimuth_p80_width_m|yaw_proxy_shape_class|scale_yaw_residual_m|best_yaw_deg|
|---|---|---|---|---|---|---|
|R21B00204|278|2.112273|3.270127|azimuth_dominant|0.002171|84|
|R21B00221|281|3.025488|3.424727|near_isotropic|0.002997|79|
|R21B00224|281|3.025488|3.424727|near_isotropic|0.002997|79|
|R21B00231|288|1.967405|3.314171|azimuth_dominant|0.00431|79|
|R21B00212|279|3.061984|3.370182|near_isotropic|0.00498|54|

## 典型异常样本

|response_unit_id|sar_frame|range_p80_width_m|azimuth_p80_width_m|yaw_proxy_shape_class|scale_yaw_residual_m|touches_display_fan_boundary|
|---|---|---|---|---|---|---|
|R21B00228|284|0.126497|0.09842|range_dominant|3.154541|false|
|R21B00229|284|0.136671|0.1581|near_isotropic|3.110048|false|
|R21B00239|289|0.155389|0.150325|near_isotropic|3.107008|false|
|R21B00004|27|0.101336|0.216181|azimuth_dominant|3.071836|false|
|R21B00064|52|0.182481|0.178255|near_isotropic|3.071006|false|

## 下一阶段 S2 协议

S2 只能在本轮 physical observation field 冻结后打开 `paired_annotations`、`response_unit_gt_instance_matrix` 和 `mask_observation_audit`。S2 将构造 GT 区域、邻近平移反事实、单边界反事实、尺度反事实和匹配背景反事实；再判断 GT 区域是否物理可辨识、哪些边可辨识、哪些边只能给区间、哪些边受 MASK 或歧义影响、哪些边单帧不可识别。本轮没有执行 S2，也没有进行 GT 区域判优。

## 完整性 gates

|gate_name|status|detail|source_file|sha256|row_count|
|---|---|---|---|---|---|
|WORKTREE_BRANCH_VALID|PASS|checked before generation in required command sequence||||
|PROJECT_CONFIRMED_CALIBRATION_APPLIED|PASS|max_range_m=40.0; radial_grid_spacing_m_per_px=0.03; fan_center=(1154.0,1330.6)||||
|GT_NOT_READ_DURING_GENERATION|PASS|generation artifacts record gt_file_opened=false||||
|PAIRED_ANNOTATIONS_NOT_READ_DURING_GENERATION|PASS|generation artifacts record paired_annotations_opened=false||||
|MASK_AUDIT_NOT_READ_DURING_GENERATION|PASS|generation artifacts record mask_audit_opened=false||||
|FROZEN_REPLAY_IDENTICAL|PASS|replay_rows=7||||
|OUTPUT_ROW_COUNT_STABLE|PASS|rows=250 expected=250|reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_rows_20260712.csv|e332ea6470494b7d4d80d2d4c4864b4169ced09635a408c4d162fe0c9c0e6e37|250|
|UNIQUE_RESPONSE_UNIT_COUNT_STABLE|PASS|unique_response_unit_count=250||||
|INDEPENDENT_GEOMETRY_COUNT_RECORDED|PASS|unique_conservative_bbox_count=215||||
|THRESHOLD_STABILITY_RECOMPUTABLE|PASS|threshold_rows=750||||
|SCALE_YAW_AUDIT_RECOMPUTABLE|PASS|scale_yaw_rows=250||||
|COUNTERFACTUAL_TEMPLATE_BANK_READY|PASS|template_rows=9000||||
|NO_SELECTOR_OUTPUT|PASS|no selector/ranking output names||||
|NO_FINAL_BOX_OUTPUT|PASS|no final/revised/runtime/best-box output names||||
|S2_PROTOCOL_WRITTEN_NOT_EXECUTED|PASS|main report contains next-stage protocol; no GT反事实判优 executed||||
|ALLOWED_INPUT_HASH_LOCAL_RESPONSE_UNITS|PASS|allowed generation input hash|reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv|83a62fb7ca01e91270c5c64ea63997b5676259ccfb5d22c3e8e789d37bdcaf64|250|
|ALLOWED_INPUT_HASH_BOUNDARY_VARIANTS|PASS|allowed generation input hash|reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_variant_families_20260711.csv|f76cc9d4caefa98310ac843116b9e1283073b3a18715630243a66346f30016ac|176|

## 输出文件

- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_rows_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_summary_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_threshold_stability_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_scale_yaw_audit_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_counterfactual_templates_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_integrity_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_pre_eval_seal_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_replay_check_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_observation_field_visual_manifest_20260712.csv`
- `reports/oty2/oty2_gm_rm019_static_physical_observation_field_20260712.md`

## 禁止产物声明

本轮未生成最终框，未修改 GT，未修改 GM_RM017，未产生 selector/ranking、best-box 或 runtime prediction artifact。
