# OTY2 WGV3.5A-R2C Mask-Aware Visual Diagnosis

Codex generated and reviewed the following visual audit panels:

- mask_overview: `outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_sar_mask_overview.png`
- pair_contact_sheet: `outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_16_pair_mask_contact_sheet.png`
- vehicle_trajectory: `outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_vehicle_sar_trajectory_vs_mask.png`
- class_cases: `outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_s0_s1_s2_s3_cases.png`
- gm17_control: `outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm17_leakage_free_recovery_comparison.png`
- optical_timeline: `outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_optical_recovery_timeline.png`
- azimuth_residual: `outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_azimuth_residual_vs_mask_distance.png`
- leave_one: `outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_leave_one_vehicle_fold_results.png`

## Chinese Visual Judgement

- GM_RM019 16条配对的SAR框均在重建扇形mask内，但全部靠近近距下边界；框与mask交集接近1不能证明完整车辆中心可见。
- S1样本：可见响应仍在mask内，中心可能被拉向mask内部，只能弱中心/区间审计。
- S2样本：灰色左边车辆0214/0215底部有效余量约66px，完整中心可能被mask截断，不可作完整中心监督。
- 光学恢复：白色SUV较可信；银色MPV、黑色轿车、灰色左边车为部分可信；右侧暗片段身份不应合并。
- GM17无泄漏图只展示退化输入恢复前后误差，不读取原始完整框用于恢复。

## Optical State Review

|physical_vehicle_id|reviewed_frames|paired_frames|direct_full_stream_anchor_count|branch_a_recovered_pair_count|branch_b_recovered_pair_count|optical_state_review_class|identity_confidence|pure_optical_reason_cn|allowed_for_sar_mapping_audit|
|---|---|---|---|---|---|---|---|---|---|
|PV_GM19_BLACK_SEDAN_NEAR_FIELD|0-11|0;2;4|0|0|3|OPTICAL_STATE_PARTIALLY_PLAUSIBLE|0.9|早段近场底边截断，Z1B给出连续整车隐状态，但无可用全流完整锚点，径向前几帧不稳定。|true|
|PV_GM19_WHITE_SUV_NEAR_FIELD|5-27;29-41|13;15;37;39|11|4|4|OPTICAL_STATE_PLAUSIBLE|0.9|全流存在非配对光学恢复锚点，配对帧前后恢复框与近场车辆横向运动连续；但SAR中心仍受mask语义限制。|true|
|PV_GM19_RIGHT_DARK_FRAGMENT|12-14|13|0|0|1|IDENTITY_UNRESOLVED|0.55|短片段且与白色SUV同帧并存，R2B已保持不合并；不能为了恢复强行归并身份。|false|
|PV_GM19_UNPAIRED_SMALL_044_049|44-49||0|0|0|OPTICAL_STATE_PARTIALLY_PLAUSIBLE|0.65|R2B轨迹恢复可用于纯光学审计，但不提升SAR中心语义。|true|
|PV_GM19_UNPAIRED_SMALL_060_080|60-80||0|0|0|OPTICAL_STATE_PARTIALLY_PLAUSIBLE|0.65|R2B轨迹恢复可用于纯光学审计，但不提升SAR中心语义。|true|
|PV_GM19_UNPAIRED_SMALL_083_098|83-98||0|0|0|OPTICAL_STATE_PARTIALLY_PLAUSIBLE|0.65|R2B轨迹恢复可用于纯光学审计，但不提升SAR中心语义。|true|
|PV_GM19_SILVER_MPV_NEAR_FIELD|99-140|102;114;129;131;138-139|6|3|6|OPTICAL_STATE_PARTIALLY_PLAUSIBLE|0.9|轨迹较长且Z1B中心/径向连续，部分帧仍有下边缘与深度混合风险，进入SAR映射只能作为审计证据。|true|
|PV_GM19_GRAY_CAR_LEFT_EDGE|149-182|151-152|5|0|2|OPTICAL_STATE_PARTIALLY_PLAUSIBLE|0.9|左边缘进入/离开阶段可见约束单侧，恢复框方向合理但短轨迹和mask近边界使中心监督不可用。|true|
|PV_GM19_UNPAIRED_SMALL_259_261|259-261||0|0|0|OPTICAL_STATE_PARTIALLY_PLAUSIBLE|0.65|R2B轨迹恢复可用于纯光学审计，但不提升SAR中心语义。|true|

## Center Semantic Review

|pair_id|physical_vehicle_id|sar_frame|mask_class|sar_box_same_physical_vehicle|sar_response_mask_censored|sar_box_center_full_vehicle_center|center_closer_to_front_hotspot|center_closer_to_rear_hotspot|center_visible_response_only|temporal_mapping_shift_risk|azimuth_direction_consistent|polar_conversion_consistent|center_semantic_status|review_cn|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|WGV35A_PAIR_0200|PV_GM19_BLACK_SEDAN_NEAR_FIELD|0|SAR_MASK_S2_CENTER_CENSORED|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|完整车辆中心可能已被mask裁掉，当前框中心是mask内局部响应中心。|
|WGV35A_PAIR_0201|PV_GM19_BLACK_SEDAN_NEAR_FIELD|4|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_VISIBLE_RESPONSE_ONLY|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0202|PV_GM19_BLACK_SEDAN_NEAR_FIELD|8|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_VISIBLE_RESPONSE_ONLY|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0203|PV_GM19_RIGHT_DARK_FRAGMENT|27|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|PAIRING_REVIEW_REQUIRED|短片段与同帧车辆并存，SAR中心语义之外仍有配对身份复核风险。|
|WGV35A_PAIR_0204|PV_GM19_WHITE_SUV_NEAR_FIELD|27|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0205|PV_GM19_WHITE_SUV_NEAR_FIELD|31|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_VISIBLE_RESPONSE_ONLY|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0206|PV_GM19_WHITE_SUV_NEAR_FIELD|77|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0207|PV_GM19_WHITE_SUV_NEAR_FIELD|81|SAR_MASK_S2_CENTER_CENSORED|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|完整车辆中心可能已被mask裁掉，当前框中心是mask内局部响应中心。|
|WGV35A_PAIR_0208|PV_GM19_SILVER_MPV_NEAR_FIELD|212|SAR_MASK_S2_CENTER_CENSORED|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|完整车辆中心可能已被mask裁掉，当前框中心是mask内局部响应中心。|
|WGV35A_PAIR_0209|PV_GM19_SILVER_MPV_NEAR_FIELD|238|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_VISIBLE_RESPONSE_ONLY|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0210|PV_GM19_SILVER_MPV_NEAR_FIELD|269|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0211|PV_GM19_SILVER_MPV_NEAR_FIELD|273|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0212|PV_GM19_SILVER_MPV_NEAR_FIELD|288|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_VISIBLE_RESPONSE_ONLY|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0213|PV_GM19_SILVER_MPV_NEAR_FIELD|290|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|review_only_no_GT_change|true|false|unknown|unknown|true|low_to_possible|geometry_formula_consistent|true|SAR_CENTER_VISIBLE_RESPONSE_ONLY|SAR框仍在mask内，但近距边界使中心更可能表示可见散射响应中心，不能等同完整车辆中心。|
|WGV35A_PAIR_0214|PV_GM19_GRAY_CAR_LEFT_EDGE|315|SAR_MASK_S2_CENTER_CENSORED|review_only_no_GT_change|true|false|unknown|unknown|true|possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|完整车辆中心可能已被mask裁掉，当前框中心是mask内局部响应中心。|
|WGV35A_PAIR_0215|PV_GM19_GRAY_CAR_LEFT_EDGE|317|SAR_MASK_S2_CENTER_CENSORED|review_only_no_GT_change|true|false|unknown|unknown|true|possible|geometry_formula_consistent|true|SAR_CENTER_MASK_BIASED|完整车辆中心可能已被mask裁掉，当前框中心是mask内局部响应中心。|