# GM_RM019 S2-A GT 区域、边界与旋转反事实物理可辨识性评价

状态：`S2_A_REGION_IDENTIFIABILITY_READY`

OTY2 (Optical Timeline Y2，光学时序辅助阶段二) / SAR (Synthetic Aperture Radar，合成孔径雷达) / GT (Ground Truth，真值) 本轮只做事后物理可辨识性评价，不做拟合、修正或最终框生成。

## Plan seal

- 主评价 GT pair：`10`；pairing-review：`6`；physical vehicle：`2`。
- plan rows：`560`；family counts：`center_shift=120; diagonal_center_shift=80; gt_original=10; local_region_rotation=100; matched_background=10; scale_resize=80; single_boundary_shift=160`。
- plan 阶段只读几何、GT 关联、MASK 上下文和 S1-R1 independent geometry map；没有读取 SAR 灰度强度，也没有读取 S1-R1 measurement outcomes。
- `final_heading_deg` 是 GT `final_w` 存储轴；`gt_long_axis_image_deg` 是 GT 响应框视觉长轴，不是车辆真实 yaw。

## 实测结果概览

- 所有 `560` 个冻结区域均从真实 SAR 灰度重新测量，`proxy_formula_used=false`。
- 主导分量能量占比（GT original）：`count=10; median=0.85426; min=0.566319; max=0.966733`。
- 显著分量布局轴状态（GT original）：`AXIS_COMPONENT_LAYOUT_RESOLVED=3; AXIS_RESOLVED=7`。
- 区域状态：`GT_REGION_INTERVAL_IDENTIFIABLE=8; GT_REGION_PHYSICALLY_DISTINGUISHABLE=2`。
- 四边状态：`EDGE_IDENTIFIABLE=12; EDGE_INTERVAL_ONLY=21; EDGE_MASK_CENSORED=7`。
- 旋转状态：`ROTATION_90_DEG_SWAP_AMBIGUOUS=5; ROTATION_INTERVAL_ONLY=3; ROTATION_NOT_IDENTIFIABLE=2`。
- 90 度交换歧义：`5`。
- 背景敏感 GT：`6`。
- GT 物理冲突 GT：`0`。
- GT 区域平台样本：`8`。

## GT-instance summary

|gt_pair_id|physical_vehicle_id|region_status|near_edge_status|far_edge_status|left_edge_status|right_edge_status|rotation_status|axis_evidence_status|background_sensitivity_status|
|---|---|---|---|---|---|---|---|---|---|
|WGV35A_PAIR_0204|PV_GM19_WHITE_SUV_NEAR_FIELD|GT_REGION_INTERVAL_IDENTIFIABLE|EDGE_IDENTIFIABLE|EDGE_INTERVAL_ONLY|EDGE_IDENTIFIABLE|EDGE_IDENTIFIABLE|ROTATION_INTERVAL_ONLY|MULTIPLE_AXIS_REPRESENTATIONS_CONFLICT|COUNTERFACTUAL_BACKGROUND_SENSITIVE|
|WGV35A_PAIR_0205|PV_GM19_WHITE_SUV_NEAR_FIELD|GT_REGION_INTERVAL_IDENTIFIABLE|EDGE_MASK_CENSORED|EDGE_IDENTIFIABLE|EDGE_IDENTIFIABLE|EDGE_IDENTIFIABLE|ROTATION_INTERVAL_ONLY|MULTIPLE_AXIS_REPRESENTATIONS_CONFLICT|COUNTERFACTUAL_BACKGROUND_SENSITIVE|
|WGV35A_PAIR_0206|PV_GM19_WHITE_SUV_NEAR_FIELD|GT_REGION_INTERVAL_IDENTIFIABLE|EDGE_MASK_CENSORED|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|EDGE_IDENTIFIABLE|ROTATION_NOT_IDENTIFIABLE|GLOBAL_AND_COMPONENT_AXIS_CONSISTENT|COUNTERFACTUAL_BACKGROUND_SENSITIVE|
|WGV35A_PAIR_0207|PV_GM19_WHITE_SUV_NEAR_FIELD|GT_REGION_INTERVAL_IDENTIFIABLE|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|EDGE_IDENTIFIABLE|ROTATION_INTERVAL_ONLY|COMPONENT_LAYOUT_AXIS_ONLY|BACKGROUND_STABLE|
|WGV35A_PAIR_0208|PV_GM19_SILVER_MPV_NEAR_FIELD|GT_REGION_INTERVAL_IDENTIFIABLE|EDGE_IDENTIFIABLE|EDGE_IDENTIFIABLE|EDGE_IDENTIFIABLE|EDGE_IDENTIFIABLE|ROTATION_NOT_IDENTIFIABLE|GLOBAL_AND_COMPONENT_AXIS_CONSISTENT|COUNTERFACTUAL_BACKGROUND_SENSITIVE|
|WGV35A_PAIR_0209|PV_GM19_SILVER_MPV_NEAR_FIELD|GT_REGION_PHYSICALLY_DISTINGUISHABLE|EDGE_MASK_CENSORED|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|ROTATION_90_DEG_SWAP_AMBIGUOUS|GLOBAL_AND_COMPONENT_AXIS_CONSISTENT|BACKGROUND_STABLE|
|WGV35A_PAIR_0210|PV_GM19_SILVER_MPV_NEAR_FIELD|GT_REGION_INTERVAL_IDENTIFIABLE|EDGE_MASK_CENSORED|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|ROTATION_90_DEG_SWAP_AMBIGUOUS|GLOBAL_AND_COMPONENT_AXIS_CONSISTENT|COUNTERFACTUAL_BACKGROUND_SENSITIVE|
|WGV35A_PAIR_0211|PV_GM19_SILVER_MPV_NEAR_FIELD|GT_REGION_INTERVAL_IDENTIFIABLE|EDGE_MASK_CENSORED|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|ROTATION_90_DEG_SWAP_AMBIGUOUS|GLOBAL_AND_COMPONENT_AXIS_CONSISTENT|BACKGROUND_STABLE|
|WGV35A_PAIR_0212|PV_GM19_SILVER_MPV_NEAR_FIELD|GT_REGION_INTERVAL_IDENTIFIABLE|EDGE_MASK_CENSORED|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|ROTATION_90_DEG_SWAP_AMBIGUOUS|GLOBAL_AND_COMPONENT_AXIS_CONSISTENT|COUNTERFACTUAL_BACKGROUND_SENSITIVE|
|WGV35A_PAIR_0213|PV_GM19_SILVER_MPV_NEAR_FIELD|GT_REGION_PHYSICALLY_DISTINGUISHABLE|EDGE_MASK_CENSORED|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|EDGE_INTERVAL_ONLY|ROTATION_90_DEG_SWAP_AMBIGUOUS|MULTIPLE_AXIS_REPRESENTATIONS_CONFLICT|BACKGROUND_STABLE|

## Physical-vehicle summary

|physical_vehicle_id|gt_instance_count|region_status_counts|edge_status_counts|rotation_status_counts|background_sensitive_count|physical_conflict_count|interval_platform_count|vehicle_directional_consistency_status|vehicle_specific_only_status|vehicle_note_cn|
|---|---|---|---|---|---|---|---|---|---|---|
|PV_GM19_SILVER_MPV_NEAR_FIELD|6|GT_REGION_INTERVAL_IDENTIFIABLE=4; GT_REGION_PHYSICALLY_DISTINGUISHABLE=2|EDGE_IDENTIFIABLE=4; EDGE_INTERVAL_ONLY=15; EDGE_MASK_CENSORED=5|ROTATION_90_DEG_SWAP_AMBIGUOUS=5; ROTATION_NOT_IDENTIFIABLE=1|3|0|4|CROSS_VEHICLE_DIRECTIONALLY_CONSISTENT|NO_VEHICLE_SPECIFIC_ONLY|physical-vehicle 层为描述性检查，不能声称泛化。|
|PV_GM19_WHITE_SUV_NEAR_FIELD|4|GT_REGION_INTERVAL_IDENTIFIABLE=4|EDGE_IDENTIFIABLE=8; EDGE_INTERVAL_ONLY=6; EDGE_MASK_CENSORED=2|ROTATION_INTERVAL_ONLY=3; ROTATION_NOT_IDENTIFIABLE=1|3|0|4|CROSS_VEHICLE_DIRECTIONALLY_CONSISTENT|NO_VEHICLE_SPECIFIC_ONLY|physical-vehicle 层为描述性检查，不能声称泛化。|

## MASK 分层

|mask_class|gt_instance_count|physical_vehicle_count|region_status_counts|edge_status_counts|rotation_status_counts|background_sensitive_count|physical_conflict_count|mask_note_cn|
|---|---|---|---|---|---|---|---|---|
|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|8|2|GT_REGION_INTERVAL_IDENTIFIABLE=6; GT_REGION_PHYSICALLY_DISTINGUISHABLE=2|EDGE_IDENTIFIABLE=7; EDGE_INTERVAL_ONLY=18; EDGE_MASK_CENSORED=7|ROTATION_90_DEG_SWAP_AMBIGUOUS=5; ROTATION_INTERVAL_ONLY=2; ROTATION_NOT_IDENTIFIABLE=1|5|0|MASK 只作为删失/分层上下文；仅 bottom_near_range_mask 用于近距边删失解释。|
|SAR_MASK_S2_CENTER_CENSORED|2|2|GT_REGION_INTERVAL_IDENTIFIABLE=2|EDGE_IDENTIFIABLE=5; EDGE_INTERVAL_ONLY=3|ROTATION_INTERVAL_ONLY=1; ROTATION_NOT_IDENTIFIABLE=1|1|0|MASK 只作为删失/分层上下文；仅 bottom_near_range_mask 用于近距边删失解释。|

## 视觉审阅

|visual_case_id|review_label|gt_pair_id|gt_instance_id|sar_frame|visual_relpath|opened_for_review|review_observation_cn|
|---|---|---|---|---|---|---|---|
|S2AVR00|contact_sheet|ALL_PRIMARY_AND_REVIEW_EXAMPLES|||outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/00_s2a_visual_contact_sheet.png|true|contact sheet 汇总全部主 GT 综合卡与 pairing-review 代表卡，实际打开检查排版与覆盖内容。|
|S2AVR01|rotation_90_or_interval_focus|WGV35A_PAIR_0204|316|27|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/01_rotation_90_or_interval_focus_WGV35A_PAIR_0204.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR02|rotation_90_or_interval_focus|WGV35A_PAIR_0205|317|31|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/02_rotation_90_or_interval_focus_WGV35A_PAIR_0205.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR03|background_control_focus|WGV35A_PAIR_0206|319|77|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/03_background_control_focus_WGV35A_PAIR_0206.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR04|rotation_90_or_interval_focus|WGV35A_PAIR_0207|320|81|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/04_rotation_90_or_interval_focus_WGV35A_PAIR_0207.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR05|background_control_focus|WGV35A_PAIR_0208|323|212|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/05_background_control_focus_WGV35A_PAIR_0208.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR06|rotation_90_or_interval_focus|WGV35A_PAIR_0209|324|238|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/06_rotation_90_or_interval_focus_WGV35A_PAIR_0209.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR07|rotation_90_or_interval_focus|WGV35A_PAIR_0210|325|269|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/07_rotation_90_or_interval_focus_WGV35A_PAIR_0210.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR08|rotation_90_or_interval_focus|WGV35A_PAIR_0211|326|273|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/08_rotation_90_or_interval_focus_WGV35A_PAIR_0211.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR09|rotation_90_or_interval_focus|WGV35A_PAIR_0212|327|288|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/09_rotation_90_or_interval_focus_WGV35A_PAIR_0212.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR10|rotation_90_or_interval_focus|WGV35A_PAIR_0213|328|290|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/10_rotation_90_or_interval_focus_WGV35A_PAIR_0213.png|true|综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。|
|S2AVR11|pairing_unresolved_s1_mask|WGV35A_PAIR_0201|311|4|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/11_pairing_unresolved_s1_mask_WGV35A_PAIR_0201.png|true|pairing-review 样本仅用于失败账本和 MASK 敏感性，不进入主统计。|
|S2AVR12|pairing_unresolved_s2_mask|WGV35A_PAIR_0200|309|0|outputs/oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712/visual_review/12_pairing_unresolved_s2_mask_WGV35A_PAIR_0200.png|true|pairing-review 样本仅用于失败账本和 MASK 敏感性，不进入主统计。|

## Integrity gates

|gate_name|status|detail|source_file|sha256|row_count|
|---|---|---|---|---|---|
|PLAN_STAGE_DOES_NOT_READ_SAR_INTENSITY|PASS|plan seal records intensity_read=false|reports/oty2/samples/oty2_gm_rm019_s2a_plan_seal_20260712.csv|e780d6e1579bbe39cca00c684f23724cc11877a8367284339f3feb9e92192adc|21|
|PLAN_STAGE_DOES_NOT_READ_S1_R1_MEASUREMENT_OUTCOMES|PASS|plan seal records s1_r1_measurement_outcomes_read=false|reports/oty2/samples/oty2_gm_rm019_s2a_plan_seal_20260712.csv|e780d6e1579bbe39cca00c684f23724cc11877a8367284339f3feb9e92192adc|21|
|PLAN_STAGE_GT_ACCESS_EXPLICIT|PASS|GT access is explicit in plan seal|reports/oty2/samples/oty2_gm_rm019_s2a_plan_seal_20260712.csv|e780d6e1579bbe39cca00c684f23724cc11877a8367284339f3feb9e92192adc|21|
|PROJECT_CONFIRMED_CALIBRATION_APPLIED|PASS|PROJECT_CONFIRMED constants carried into S2-A|reports/oty2/samples/oty2_gm_rm019_s2a_plan_seal_20260712.csv|e780d6e1579bbe39cca00c684f23724cc11877a8367284339f3feb9e92192adc|21|
|PLAN_SOURCE_HASH_VALID|PASS|current plan script matches plan seal|tools/diagnostics/run_oty2_gm_rm019_gt_region_s2a_plan.py|2063082bcc34c746b6c4536b73e8f006bbb439704cf3ca3912fd3a3520a512c0||
|S1_R1_HASH_VALID_input_hash_paired_annotations|PASS|hash check for reports/oty2/samples/oty2_wgv3_5a_paired_annotations_20260710.csv|reports/oty2/samples/oty2_wgv3_5a_paired_annotations_20260710.csv|54c558f1308629f4be349dedf9618803b8b3d99eed845dffa370c47d7ec9203d|204|
|S1_R1_HASH_VALID_input_hash_response_unit_gt_matrix|PASS|hash check for reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_20260711.csv|reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_20260711.csv|cdbe1efbc5e36a31c3341eba32da9fff182c8c7b670155f08a3cdbeda9e02873|63|
|S1_R1_HASH_VALID_input_hash_mask_observation_audit|PASS|hash check for reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv|reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv|738c723f2ec03d53fdf67155ae8378ad204a61316eb5c9065cbcfe6a2110c22a|16|
|S1_R1_HASH_VALID_input_hash_gt_mask_visible_geometry|PASS|hash check for reports/oty2/samples/oty2_gm_rm019_gt_mask_visible_geometry_20260712.csv|reports/oty2/samples/oty2_gm_rm019_gt_mask_visible_geometry_20260712.csv|0b5ddb1a7f777f4542a57c01015af2b81daaaadfa644bf72655931c790387fe0|16|
|S1_R1_HASH_VALID_input_hash_local_response_units|PASS|hash check for reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv|reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv|83a62fb7ca01e91270c5c64ea63997b5676259ccfb5d22c3e8e789d37bdcaf64|250|
|S1_R1_HASH_VALID_input_hash_s1_r1_independent_geometry_map|PASS|hash check for reports/oty2/samples/oty2_gm_rm019_s1_r1_independent_geometry_map_20260712.csv|reports/oty2/samples/oty2_gm_rm019_s1_r1_independent_geometry_map_20260712.csv|2d3c876d3c708a1bb50234328935fcb4a38fddb1115e37803838c184ba2a4497|215|
|S1_R1_HASH_VALID_input_hash_s1_r1_report|PASS|hash check for reports/oty2/oty2_gm_rm019_static_axis_rotation_s1_r1_20260712.md|reports/oty2/oty2_gm_rm019_static_axis_rotation_s1_r1_20260712.md|9f829d91f94cbfe81038fbea2b929d8e903da37ae45fa3c5489527206619ce3b||
|S1_R1_HASH_VALID_input_hash_protocol|PASS|hash check for docs/OTY2_GM019_GT_REGION_COUNTERFACTUAL_IDENTIFIABILITY_S2_A_PROTOCOL.md|docs/OTY2_GM019_GT_REGION_COUNTERFACTUAL_IDENTIFIABILITY_S2_A_PROTOCOL.md|fec41c5b888933d0b1b78e77a364e0fdf945bed42a2ab7a43b2bc3af2774f611||
|WORKTREE_BRANCH_VALID|PASS|branch=feature/oty2-posthoc-mechanism-validation||||
|S1_R1_ARTIFACTS_FROZEN_UNCHANGED|PASS|S1-R1 hashes from plan seal still match||||
|PLAN_SEAL_VALID|PASS|plan seal gates pass|reports/oty2/samples/oty2_gm_rm019_s2a_plan_seal_20260712.csv|e780d6e1579bbe39cca00c684f23724cc11877a8367284339f3feb9e92192adc|21|
|PRIMARY_EXACT_LINKS_SEPARATED|PASS|primary=10 review=6|reports/oty2/samples/oty2_gm_rm019_s2a_evaluation_instance_manifest_20260712.csv|8c33aaa21c7300076d23d7d31eea4e5cbb106832661bd00f4a1ddd1a9cb4a826|16|
|PAIRING_REVIEW_ROWS_NOT_IN_PRIMARY_SUMMARY|PASS|summaries=10 primary=10||||
|INDEPENDENT_GEOMETRY_DEDUP_VALID|PASS|S1-R1 independent geometry map has 215 rows|reports/oty2/samples/oty2_gm_rm019_s1_r1_independent_geometry_map_20260712.csv|2d3c876d3c708a1bb50234328935fcb4a38fddb1115e37803838c184ba2a4497|215|
|GT_INSTANCE_GROUPING_VALID|PASS|10 primary GT instances||||
|PHYSICAL_VEHICLE_GROUPING_VALID|PASS|2 physical vehicles||||
|FINAL_HEADING_STORAGE_AXIS_SEMANTICS_VALID|PASS|final_heading_deg is stored final_w axis, not vehicle yaw||||
|GT_LONG_AXIS_DERIVATION_VALID|PASS|GT long axis derived in plan geometry semantics||||
|NO_TRUE_YAW_OUTPUT|PASS|no true-yaw fields||||
|ALL_COUNTERFACTUALS_PRE_REGISTERED|PASS|plan_rows=560 measurement_rows=560||||
|MATCHED_BACKGROUND_NOT_INTENSITY_SELECTED|PASS|matched backgrounds carry fixed-order rule||||
|MATCHED_BACKGROUND_COMPLETE|PASS|matched_background=10 primary=10||||
|ALL_REGIONS_REMEASURED_FROM_REAL_SAR|PASS|all measurement rows use SAR gray||||
|NO_PROXY_COUNTERFACTUAL_FORMULA|PASS|proxy_formula_used=false||||
|GLOBAL_AXIS_MEASURED|PASS|global energy axis present||||
|DOMINANT_COMPONENT_AXIS_MEASURED|PASS|dominant component axis present||||
|COMPONENT_LAYOUT_AXIS_MEASURED|PASS|component layout axis present||||
|MULTI_COMPONENT_NOT_AUTOMATICALLY_REJECTED|PASS|multi-component rows retain axis statuses||||
|FACTOR_WISE_EVALUATION_ONLY|PASS|factor-wise rows per GT instance||||
|NO_WEIGHTED_SCORE|PASS|no weighted score field||||
|NO_SELECTOR|PASS|no selector field||||
|NO_RANKING|PASS|no ranking field||||
|NO_BEST_BOX|PASS|no best-box field||||
|REGION_STATUS_COMPLETE|PASS|region status complete||||
|FOUR_EDGE_STATUS_COMPLETE|PASS|4 edge rows per primary GT||||
|ROTATION_STATUS_COMPLETE|PASS|rotation status complete||||
|MASK_CONTEXT_RECORDED|PASS|mask context retained||||
|BACKGROUND_SENSITIVITY_RECORDED|PASS|background sensitivity retained||||
|GT_INSTANCE_LEVEL_SUMMARY_PRESENT|PASS|GT-instance summary present||||
|PHYSICAL_VEHICLE_LEVEL_SUMMARY_PRESENT|PASS|physical-vehicle summary present||||
|ROW_LEVEL_NOT_USED_AS_INDEPENDENT_N|PASS|report states measurement rows are not independent N||||
|VISUAL_REVIEW_ACTUALLY_OPENED|PASS|visual manifest includes opened review rows||||
|FROZEN_REPLAY_IDENTICAL|PASS|replay_rows=11||||
|NO_GT_MODIFICATION|PASS|GT source files read only||||
|NO_FINAL_BOX_OUTPUT|PASS|no final box artifact generated||||
|NO_GM017_MODIFICATION|PASS|GM_RM017 sibling worktree not written||||

## Outputs

- `reports/oty2/samples/oty2_gm_rm019_s2a_region_measurements_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_region_factor_comparison_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_edge_identifiability_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_rotation_identifiability_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_axis_representation_ablation_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_matched_background_controls_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_mask_stratified_results_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_gt_instance_summary_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_vehicle_group_summary_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_failure_ledger_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_integrity_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_replay_check_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s2a_visual_manifest_20260712.csv`
- `reports/oty2/oty2_gm_rm019_gt_region_counterfactual_identifiability_s2a_20260712.md`

## 边界声明

本轮未拟合 GT，未修正 GT，未生成最终框，未修改 GM_RM017，未产生 selector/ranking/best-box。结果只说明单帧静态 SAR 中 GT response region、四边界和旋转反事实的物理可辨识性层级。
