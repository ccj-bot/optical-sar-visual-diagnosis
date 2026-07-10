# OTY2 WGV3.5A-R2 GM_RM019 Closure

Date: 20260710

R2 status: `OPEN_GM19_COMPLETE_ANCHOR_INSUFFICIENT`

## Boundary

R2 stopped at GM_RM019 because complete anchors are insufficient. R3 and R4 must not run after this state.

## 中文关闭结论

- R2关闭状态为`OPEN_GM19_COMPLETE_ANCHOR_INSUFFICIENT`：GM_RM019没有可用完整车辆恢复状态锚点。
- 所有16个样本均为阻塞；0个直接迁移样本，0个时序恢复迁移样本，0个可用于A1/A3/A5的场景校准锚点。
- 截断贡献是主导证据：近场局部框中心和底边深度明显偏离整车状态，Z0在all_evaluable上中心覆盖为0/16。
- 场景几何偏移和相对深度尺度变化仍可能存在，但当前缺少完整锚点，不能把三者稳定分离或校准。
- 因R2未达到两个正向关闭状态之一，后续GM_RM011遮挡验证和统一物理迁移前端均未执行。

## Physical Vehicles

| physical_vehicle_id | source_track_ids | frame_start | frame_end | same_vehicle_relation | different_vehicle_relation | simultaneous_visibility | appearance_evidence | motion_evidence | identity_confidence | identity_blocked_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PV_GM19_BLACK_SEDAN_NEAR_FIELD | oty1t_obj_GM_RM019_bytetrack_bt_0001 | 0 | 4 | same physical vehicle across bt_0001 frames | different from white SUV and later silver/gray vehicles | none in paired rows | black sedan side appearance; large close-range box clipped by right and bottom image borders | short forward motion from frames 0 to 4; remains near bottom/right truncation | 0.9 |  |
| PV_GM19_GRAY_CAR_LEFT_EDGE | oty1t_obj_GM_RM019_bytetrack_bt_0098 | 151 | 152 | same physical vehicle across bt_0098 frames | different from bt_0080 by time, appearance and position | none in paired rows | gray car front-left edge fragment with green plate | two adjacent edge frames 151-152 | 0.82 | only edge/front fragment visible |
| PV_GM19_RIGHT_DARK_FRAGMENT | oty1t_obj_GM_RM019_bytetrack_bt_0009 | 13 | 13 | single fragment only | different from bt_0005 because simultaneous and different appearance | frame 13 simultaneous with bt_0005 | dark front/right-edge fragment only | single-frame fragment; no safe continuation | 0.75 | fragmentary and non-vehicle pair confidence |
| PV_GM19_SILVER_MPV_NEAR_FIELD | oty1t_obj_GM_RM019_bytetrack_bt_0080 | 102 | 139 | same physical vehicle across bt_0080 frames | different from earlier sedan/SUV and later gray car | none in paired rows | silver MPV/van side with advertisement marking | moves through near-field from left edge to right edge frames 102-139 | 0.92 |  |
| PV_GM19_WHITE_SUV_NEAR_FIELD | oty1t_obj_GM_RM019_bytetrack_bt_0005 | 13 | 39 | same physical vehicle across bt_0005 frames | different from bt_0009 right-edge dark fragment in frame 13 | frame 13 has bt_0005 and bt_0009 simultaneously | white SUV side appearance; visible from left-edge phase to right-edge phase | large displacement from left to right across frames 13-39 | 0.9 |  |

## Observation Counts

- direct_observable: `0`
- temporally_recoverable: `0`
- blocked/not_safely_recoverable: `16`
- incorrect old visibility labels: `14`

## Anchor Manifest

| anchor_plan | anchor_count | anchor_pair_ids | anchor_frames | selection_rule | usable_for_scene_residual_calibration | blocked_reason |
| --- | --- | --- | --- | --- | --- | --- |
| A0 | 0 |  |  | pre-error fixed temporal spread over direct-observable high-confidence rows | true |  |
| A1 | 0 |  |  | pre-error fixed temporal spread over direct-observable high-confidence rows | false | no_direct_observable_scene_anchor_available |
| A3 | 0 |  |  | pre-error fixed temporal spread over direct-observable high-confidence rows | false | no_direct_observable_scene_anchor_available |
| A5 | 0 |  |  | pre-error fixed temporal spread over direct-observable high-confidence rows | false | no_direct_observable_scene_anchor_available |

## Projection Comparison

| evaluation_group | method | anchor_plan | sample_count | physical_vehicle_count | azimuth_median_error | azimuth_p90_error | radial_median_error | radial_p90_error | center_coverage_50 | center_coverage_80 | center_coverage_95 | center_covered_95_count | full_box_coverage_95 | median_search_ratio | p90_search_ratio | multi_target_rate | wrong_identity_rate | blocked_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| direct_observable | Z0_GM17_model_direct_local_observation | A0 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 0 |
| direct_observable | Z1_temporal_full_vehicle_recovery | A0 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 0 |
| temporally_recoverable | Z0_GM17_model_direct_local_observation | A0 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 0 |
| temporally_recoverable | Z1_temporal_full_vehicle_recovery | A0 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 0 |
| not_safely_recoverable | Z0_GM17_model_direct_local_observation | A0 | 16 | 5 | 14.070463 | 19.288789 | 170.529591 | 311.659159 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0.00107227 | 0.00107227 | 0.0625 | 0 | 0 |
| not_safely_recoverable | Z1_temporal_full_vehicle_recovery | A0 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 1 |
| all_evaluable | Z0_GM17_model_direct_local_observation | A0 | 16 | 5 | 14.070463 | 19.288789 | 170.529591 | 311.659159 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0.00107227 | 0.00107227 | 0.0625 | 0 | 0 |
| all_evaluable | Z1_temporal_full_vehicle_recovery | A0 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 1 |
| all_evaluable | Z2_recovery_plus_scene_residual_calibration | A1 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 1 |
| all_evaluable | Z2_recovery_plus_scene_residual_calibration | A3 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 1 |
| all_evaluable | Z2_recovery_plus_scene_residual_calibration | A5 | 0 | 0 |  |  |  |  | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |  |  |  |  | 1 |

## Failure Decomposition

- dominant counts: `{'insufficient_complete_anchor': 16}`
- Z0 local projection preserves the R1 zero-scene-calibration baseline but it acts on local near-field boxes whose centers and bottom depths are physically distorted.
- Z1 cannot be fairly evaluated because there are no direct-observable same-vehicle anchors in GM_RM019.
- A1/A3/A5 residual calibration cannot be run because anchor count is zero.

## Created Files

- `reports/oty2/oty2_wgv3_5a_r2_gm019_identity_and_observation_audit_20260710.md`
- `reports/oty2/samples/oty2_wgv3_5a_r2_gm019_physical_vehicle_map_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2_gm019_observation_states_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2_gm019_recovered_states_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2_gm019_anchor_manifest_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2_gm019_projection_comparison_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2_gm019_failure_cases_20260710.csv`
- `reports/oty2/oty2_wgv3_5a_r2_gm019_visual_diagnosis_20260710.md`
- `reports/oty2/oty2_wgv3_5a_r2_gm019_closure_20260710.md`
