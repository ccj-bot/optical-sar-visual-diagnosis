# GM_RM019 MASK感知GT锚定物理尺度拟合审计

日期：`20260712`

## 最终状态

`ABSOLUTE_SCALE_UNRESOLVED`

本轮没有进行米制M0-M5拟合。原因是未找到可靠的SAR原始物理坐标轴、raw/float到PNG的标定链、FMCW有效带宽、FFT网格、显示缩放或裁剪偏移。运行时配置中的40m最大量程只作为被拒绝候选记录，未用于当前拟合。

## 边界

- GT（Ground Truth，真值标注）只用于事后分析、验证和机制解释。
- MASK只按当前证据拆成重建扇形显示支持、pair级MASK上下文、frame-only上下文和边界变体不确定性。
- 未生成最终框、候选框、selector/ranking、best-box、runtime prediction artifact，未修改GT，未修改GM_RM017。

## 绝对尺度审计

- 已支持的几何：`2308x1334` PNG坐标、扇形中心`(1154.0, 1330.6)`、扇形半径`1332.7px`、显示方位角公式。
- 未解决尺度参数数：`9`。
- 被拒绝候选数：`2`。
- 径向m/px：未恢复。
- 距离分辨率m：未恢复。
- 二者为何不同：m/px是成像网格或显示采样间距；距离分辨率需要真实FMCW带宽/成像链路。当前两者都没有可靠来源，因此都不能用于米制拟合。

|parameter_name|value|unit|confidence|status|notes_cn|
|---|---|---|---|---|---|
|sar_image_width_px|2308|px|high_for_png_geometry|SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY|用于PNG坐标审计；不是米制标定。|
|sar_image_height_px|1334|px|high_for_png_geometry|SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY|用于PNG坐标审计；不是米制标定。|
|fan_center_x_px|1154|px|high_for_display_fan_geometry|SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY|可支持径向/方位角像素几何，不能证明物理坐标轴。|
|fan_center_y_px|1330.6|px|high_for_display_fan_geometry|SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY|可支持径向/方位角像素几何，不能证明物理坐标轴。|
|fan_radius_px|1332.7|px|high_for_display_fan_geometry|SUPPORTED_FOR_PIXEL_GEOMETRY_ONLY|只说明PNG扇形半径，不说明真实最大量程。|
|azimuth_definition|atan2(x - 1154.0, 1330.6 - y)|degree|medium_for_display_angle|SUPPORTED_FOR_ANGLE_ONLY|方位角可在PNG扇形几何内复算，但横向米制仍需要径向米制。|
|cross_range_conversion||m|none|ABSOLUTE_SCALE_UNRESOLVED|缺少可靠R_ref米制，不能把角宽转为横向米制。|
|radial_grid_spacing_m_per_px||m/px|none|ABSOLUTE_SCALE_UNRESOLVED|未找到真实成像程序输出的range_axis/x_axis/y_axis或PNG同步元数据。|
|radial_extent_m||m|none|ABSOLUTE_SCALE_UNRESOLVED|未找到真实量程轴；不能由显示扇形半径反推。|
|candidate_runtime_max_range_m_rejected|40.0|m|low_for_physical_png_scale|REJECTED_FOR_CURRENT_FIT|workspace auto_labeler配置用于运行时支持范围假设，不是PNG成像坐标轴或雷达参数。|
|candidate_radial_grid_spacing_from_runtime_config_rejected|0.03001426|m/px|low_for_physical_png_scale|REJECTED_FOR_CURRENT_FIT|这是运行时先验与显示半径的组合，不可称为物理网格间距。|
|range_resolution_m||m|none|ABSOLUTE_SCALE_UNRESOLVED|未找到真实FMCW有效带宽、chirp、采样率或FFT配置。|
|cross_range_resolution_model||m|none|ABSOLUTE_SCALE_UNRESOLVED|未找到当前数据集的方位分辨率或成像聚焦模型参数。|
|display_resize_x||ratio|none|ABSOLUTE_SCALE_UNRESOLVED|GM_RM019数据目录只有PNG/深度npy和一个空fail文本，没有raw-to-PNG缩放记录。|
|display_resize_y||ratio|none|ABSOLUTE_SCALE_UNRESOLVED|GM_RM019数据目录只有PNG/深度npy和一个空fail文本，没有raw-to-PNG缩放记录。|
|crop_offset_x||px|none|ABSOLUTE_SCALE_UNRESOLVED|未找到上游裁剪偏移。|
|crop_offset_y||px|none|ABSOLUTE_SCALE_UNRESOLVED|未找到上游裁剪偏移。|

## GT与MASK语义

- `paired_annotations.sar_bbox`与`mask_observation_audit.sar_bbox`在本轮解释为SAR侧事后响应框或MASK偏置可见响应框，不解释为完整车辆真实尺寸。
- `response_unit_gt_instance_matrix`只提供eval-only匹配/覆盖关系，不是runtime assignment，也不是选择最佳响应单元的依据。
- 当前MASK证据是由代码重建的PNG扇形显示/几何支持；独立物理有效mask文件和成像期物理有效区语义未确认。
- 重建显示扇形下的GT可见比例不能替代真实物理MASK语义；本轮把二者分开记录。
- GM_RM019 MASK pair：`16`；帧数：`15`；物理车辆数：`5`。
- 拟合候选行：`57`；精确关联GT pair：`10`；GT instance：`10`；帧：`10`；物理车辆：`2`；独立响应几何：`215`；重复几何组：`28`。
- MASK类别：`{'SAR_MASK_S2_CENTER_CENSORED': 5, 'SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE': 11}`。
- primary response中pair级MASK精确关联：`57`；frame-only上下文：`0`。

## GT完整区间与可见区间统计

- gt_visible_fraction: count=16, median=1, min=1, max=1
- gt_range_width_px: count=16, median=149.915293, min=91.132273, max=176.499335
- 米制GT区间：未生成，原因是绝对尺度未恢复。

## SAR p80展宽统计

- range_p80_width_px: count=250, median=30.713167, min=3.17338, max=117.960428
- azimuth_p80_width_deg_approx: count=250, median=20.372723, min=0.782564, max=50.681642
- SAR p80米制展宽：未生成，原因是绝对尺度未恢复。

## M0-M5模型比较

|target_dimension|model_id|training_sample_count|candidate_input_rows|holdout_fold_count|run_status|blocked_reason|
|---|---|---|---|---|---|---|
|range_p80_width_m|M0|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|range_p80_width_m|M1|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|range_p80_width_m|M2|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|range_p80_width_m|M3|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|range_p80_width_m|M4|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|range_p80_width_m|M5|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|cross_range_p80_width_m|M0|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|cross_range_p80_width_m|M1|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|cross_range_p80_width_m|M2|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|cross_range_p80_width_m|M3|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|cross_range_p80_width_m|M4|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|cross_range_p80_width_m|M5|0|57|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|

## 留出审计

|fold_strategy|potential_group_count|potential_sample_count|min_group_size|max_group_size|same_pair_cross_fold_violation|holdout_fold_count|failed_fold_count|run_status|blocked_reason|
|---|---|---|---|---|---|---|---|---|---|
|leave_one_gt_pair|10|57|2|8|false|0|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|leave_one_sar_frame|10|57|2|8|false|0|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|
|leave_one_physical_vehicle|2|57|27|30|false|0|0|not_run_absolute_scale_unresolved|no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered|

## 支持样本与反例

支持样本只支持像素/角度审计和停止结论，不支持米制物理拟合。主要支持证据是：16条GM_RM019 MASK pair被审计；250个冻结response unit保持不变；57条GT-linked拟合候选行被生成但全部标记为不可米制拟合。

|counterexample_id|counterexample_type|pair_id|response_unit_id|sar_frame|physical_vehicle_id|mask_class|gt_semantic|absolute_range_m|gt_visible_width_m|sar_p80_width_m|endpoint_errors|model_residuals|why_it_matters_cn|visual_review_relpath|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|CE_SCALE_001|absolute_scale_candidate_rejected||||||posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle||||not_computed_absolute_scale_unresolved|not_computed_absolute_scale_unresolved|workspace配置中的40m最大量程只能说明运行时支持先验，不能证明PNG径向像素的物理米制。||
|CE_MASK_001|no_fully_observable_mask_center_supervision|WGV35A_PAIR_0200||0|PV_GM19_BLACK_SEDAN_NEAR_FIELD|SAR_MASK_S2_CENTER_CENSORED|posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle||||not_computed_absolute_scale_unresolved|not_computed_absolute_scale_unresolved|GM_RM019的16个MASK pair均为S1/S2，S0为0，中心监督不能用于完整车辆物理拟合。||
|CE_GT_001|gt_center_visible_response_only|WGV35A_PAIR_0204|R21B00001|27|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle||||not_computed_absolute_scale_unresolved|not_computed_absolute_scale_unresolved|SAR框中心在R2C审阅中被标记为mask偏置或可见响应中心，不能等同完整车辆中心。||
|CE_PAIR_001|pairing_review_required|WGV35A_PAIR_0203|R21B00001|27|PV_GM19_RIGHT_DARK_FRAGMENT|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle||||not_computed_absolute_scale_unresolved|not_computed_absolute_scale_unresolved|右侧暗片段同帧并存，GT pair可作为事后关联上下文，但仍保留配对复核风险。||
|CE_WIDTH_001|small_visible_gt_but_wide_sar_not_evaluated_in_meters|WGV35A_PAIR_0204|R21B00076|77|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle||||not_computed_absolute_scale_unresolved|not_computed_absolute_scale_unresolved|像素域可见GT与SAR展宽存在不匹配候选，但没有绝对尺度时不能升级为米制物理反例。||
|CE_WIDTH_002|large_visible_gt_but_narrow_sar_not_evaluated_in_meters|WGV35A_PAIR_0205|R21B00002|27|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle||||not_computed_absolute_scale_unresolved|not_computed_absolute_scale_unresolved|像素域窄响应可能来自局部散射、边界或背景估计，缺少米制和端点误差时不能做车辆尺寸结论。||
|CE_BOUNDARY_001|multiple_boundary_variant_uncertainty|WGV35A_PAIR_0204|R21B00001|27|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle||||not_computed_absolute_scale_unresolved|not_computed_absolute_scale_unresolved|边界族存在多合法变体，不能与MASK截断或完整车辆越界混成一个变量。||
|CE_BACKGROUND_001|background_or_sidelobe_wide_response||R21B00112|216|||posthoc_sar_response_bbox_visible_or_mask_biased_not_full_vehicle||||not_computed_absolute_scale_unresolved|not_computed_absolute_scale_unresolved|上一轮背景/孤立反例也可出现高能量或大展宽，阻止静态像素展宽直接成为物理车辆规则。||

## 可支持和不可支持的结论

可支持：GM_RM019当前只具备PNG像素/显示角度/MASK上下文审计；GT框中心在近场MASK条件下不能当作完整车辆中心；M0-M5米制拟合应停止。

不可支持：不能声称完成绝对物理尺度拟合；不能把radial pixel称为meter；不能把40m运行时配置除以扇形半径称为物理分辨率或可靠m/px；不能从本轮输出生成最终框或selector/ranking。

## 完整性与重放

- verify-replay: `PASS`

|gate_name|status|detail|source_file|sha256|row_count|
|---|---|---|---|---|---|
|input_hash_directional_measurements|PASS|input present and hashed|reports/oty2/samples/oty2_gm_rm019_static_directional_spread_measurements_20260712.csv|b9296c1ff3e3150321800bdb93c52e37a932978dbb970765ab94bf5c17d2ff30|500|
|input_hash_directional_pairwise_controls|PASS|input present and hashed|reports/oty2/samples/oty2_gm_rm019_static_directional_spread_pairwise_controls_20260712.csv|c350c4b86a96397bcc40b42eed8bef85830c015e61ce5faad99a5b3c6b461881|30|
|input_hash_paired_annotations|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_5a_paired_annotations_20260710.csv|54c558f1308629f4be349dedf9618803b8b3d99eed845dffa370c47d7ec9203d|204|
|input_hash_sar_polar_targets|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_5a_sar_polar_targets_20260710.csv|d5da737d9d260f5cb0de24c0af4d7327999022a0d2cdb1fd417729419497a330|204|
|input_hash_mask_observation_audit|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv|738c723f2ec03d53fdf67155ae8378ad204a61316eb5c9065cbcfe6a2110c22a|16|
|input_hash_mask_source_inventory|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_5a_r2c_sar_mask_source_inventory_20260711.csv|d6cd0f12b0190b7b2082f2b2bee358ef14191113b6d13adbfb39c339a63a95ac|3|
|input_hash_mask_aware_intervals|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_mask_aware_intervals_20260711.csv|27fc338410738b541fe5b0710ef469c69c92ac9cb357362166a877c32bec9617|1|
|input_hash_local_response_units|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv|83a62fb7ca01e91270c5c64ea63997b5676259ccfb5d22c3e8e789d37bdcaf64|250|
|input_hash_response_unit_gt_matrix|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_20260711.csv|cdbe1efbc5e36a31c3341eba32da9fff182c8c7b670155f08a3cdbeda9e02873|63|
|input_hash_boundary_variant_families|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_variant_families_20260711.csv|f76cc9d4caefa98310ac843116b9e1283073b3a18715630243a66346f30016ac|176|
|input_hash_center_semantic_review|PASS|input present and hashed|reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_center_semantic_review_20260711.csv|546413231d67b49b58b6d0268006fa284a7e83af127842586da7856c1fe1120e|16|
|input_hash_mask_definition_report|PASS|input present and hashed|reports/oty2/oty2_wgv3_5a_r2c_sar_mask_definition_20260711.md|04591e40bb5c358f23f732d0d79d695727676b2ee6bfc4ec86d7d8a61daccabc||
|input_hash_mask_gate_report|PASS|input present and hashed|reports/oty2/oty2_wgv3_5a_r2c_gm019_mask_supervision_gate_20260711.md|e64572c90ffadf25284835ed031da6a80332f4df71f423c874ec9183b9071705||
|input_hash_mask_closure_report|PASS|input present and hashed|reports/oty2/oty2_wgv3_5a_r2c_mask_aware_closure_20260711.md|df81a199227c15f6a7f099c33c9efe33ffacaf52af0aa58d7df80549028544af||
|input_hash_static_directional_report|PASS|input present and hashed|reports/oty2/oty2_gm_rm019_static_directional_spread_measurement_20260712.md|0c2a8ed4606e63119a1d2020b502c1b3cf77cfd64f345351faf2eec702057038||
|input_hash_static_registry_report|PASS|input present and hashed|reports/oty2/oty2_gm_rm019_static_physical_factor_registry_20260712.md|74598340094c1362f920f32d376029e3526f27efe7b7e6e9be8a1ede7ee40a1e||
|input_hash_static_directional_script|PASS|input present and hashed|tools/diagnostics/run_oty2_gm_rm019_static_directional_spread_measurement.py|7164db71a3888876f614735141c100aa6ed145ec5ae6e7df8b3caf20cb8863ba||
|input_hash_mask_mapping_script|PASS|input present and hashed|tools/diagnostics/run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.py|c1d6038e548888a8b91e7b50e54789cee304272f3aa24900735427c1daaf9c15||
|input_hash_support_probe_script|PASS|input present and hashed|tools/diagnostics/run_oty2_support_region_sar_observation_probe.py|6efc36a2a66d27625e0d34a6ad24b3dd438adf073ff60bb8f010482a9723663c||
|input_hash_gm019_runtime_config|PASS|input present and hashed|D:/profile/research/workspace/tools/configs/gm_rm019_vehicle_assembly_physics_v2.json|94657cdb9e0fa1943ecce14ae189d7093772fded270ba091db31bda2e0b56bdc||
|absolute_scale_status|PASS|ABSOLUTE_SCALE_UNRESOLVED: no reliable raw SAR physical coordinate axis, pulse-to-PNG calibration, chirp bandwidth, FFT/grid, or display resize/crop provenance recovered||||
|local_response_unit_count_stable|PASS|count=250 expected=250||||
|directional_measurement_rows_stable|PASS|rows=500 expected=500||||
|primary_response_rows_stable|PASS|primary_rows=250 expected=250||||
|duplicate_structure_unique_response_unit_count|PASS|unique_response_unit_count=250||||
|duplicate_structure_unique_region_bbox_count|PASS|unique_region_bbox_count=215||||
|duplicate_structure_unique_gt_pair_count|PASS|fit_unique_gt_pair_count=10||||
|duplicate_structure_unique_gt_instance_count|PASS|fit_unique_gt_instance_count=10||||
|duplicate_structure_unique_sar_frame_count|PASS|fit_unique_sar_frame_count=10||||
|duplicate_structure_unique_physical_vehicle_count|PASS|fit_unique_physical_vehicle_count=2||||
|duplicate_structure_shared_core_group_count|PASS|shared_core_group_count=0||||
|duplicate_structure_duplicate_geometry_group_count|PASS|duplicate_geometry_group_count=28||||
|gt_mask_pair_geometry_rows|PASS|rows=16 expected=16||||
|gt_pair_linked_mask_context|PASS|linked_primary_response_rows=57||||
|frame_only_mask_context_separated|PASS|frame_only_primary_response_rows=0||||
|model_rows_blocked_not_fit|PASS|M0-M5 emitted as blocked rows; no meter fit executed||||
|fit_rows_not_eligible|PASS|fit_rows=57||||
|counterexamples_preserved|PASS|counterexample rows include scale, mask, GT, boundary, and background blockers||||
|replay_status|PASS|verify-replay compares deterministic output hashes||||

## 输出文件

- `reports/oty2/samples/oty2_gm_rm019_absolute_scale_calibration_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_gt_mask_visible_geometry_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_sar_energy_physical_intervals_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_gt_sar_physical_fit_rows_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_gt_sar_physical_model_comparison_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_gt_sar_physical_holdout_evaluation_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_gt_sar_physical_counterexamples_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_gt_sar_physical_integrity_20260712.csv`
- `reports/oty2/oty2_gm_rm019_mask_aware_gt_physical_scale_fit_20260712.md`

## 停止声明

本轮在`ABSOLUTE_SCALE_UNRESOLVED`处停止。没有生成最终框；没有修改GT；没有修改GM_RM017；没有产生selector/ranking、best-box或runtime prediction artifact。
