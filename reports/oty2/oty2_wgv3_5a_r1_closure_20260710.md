# OTY2 WGV3.5A-R1 Closure

Date: 20260710

WGV3.5A-R1 status: `CLOSED_COMPLETE_OBSERVATION_AND_TEMPORAL_RECOVERY_FEASIBLE`

## Boundary

Only GM_RM017 was used. WGV3.5A baseline files were read and frozen by SHA256, not modified. GT is used only for posthoc error/coverage evaluation.

## Frozen Baseline

| source_file | sha256 | bytes | rows |
| --- | --- | --- | --- |
| reports/oty2/oty2_wgv3_5a_pair_and_depth_audit_20260710.md | 3e929ada8518476c6cbd999aa5ae9a02a22f9a60bf1368ed1496aaca32523cc4 | 3253 |  |
| reports/oty2/oty2_wgv3_5a_visual_feasible_field_diagnosis_20260710.md | b981e9337bac30f000bebb7b0c4a3db3793aab7c7a98d6499e455785c8b0524e | 18038 |  |
| reports/oty2/oty2_wgv3_5a_weak_physical_projection_closure_20260710.md | f2bfeb65712f1c43077eb5c4a89f6162a32dacdf0dd388e0019a77f2a9ca7c8e | 6924 |  |
| reports/oty2/samples/oty2_wgv3_5a_paired_annotations_20260710.csv | 54c558f1308629f4be349dedf9618803b8b3d99eed845dffa370c47d7ec9203d | 98642 | 204 |
| reports/oty2/samples/oty2_wgv3_5a_sar_polar_targets_20260710.csv | d5da737d9d260f5cb0de24c0af4d7327999022a0d2cdb1fd417729419497a330 | 23783 | 204 |
| reports/oty2/samples/oty2_wgv3_5a_optical_vehicle_states_20260710.csv | bdff06bd75f748f84a023caddf50312fc793646eb76d5f7113a6e97ea565fba2 | 69268 | 204 |
| reports/oty2/samples/oty2_wgv3_5a_identity_safe_split_20260710.csv | 4b7648b894fc45d6f92ebfbf1ad335c05dda3c536f76abb30aa3da67d408f9fc | 2249 | 9 |
| reports/oty2/samples/oty2_wgv3_5a_azimuth_calibration_20260710.csv | a645fc0b5f5806b2b29dccc056a13fcdde191c48f73fa9974713eccd139a9867 | 1100 | 5 |
| reports/oty2/samples/oty2_wgv3_5a_radial_calibration_20260710.csv | ff80eabbd505ebbab4dab1c04b74d92af0c736ff610928c67978db4c1557413d | 943 | 4 |
| reports/oty2/samples/oty2_wgv3_5a_failure_cases_20260710.csv | f767785c164b416d7814da38584c6c1ad4a80b8440a6e1e166ae5babd9f76252 | 4349 | 13 |

## Physical Vehicle Audit

| physical_vehicle_id | source_track_ids | optical_frame_start | optical_frame_end | same_vehicle_relation | same_vehicle_confidence | evidence | conflict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PV_GM17_DARK_FOLLOW | oty1t_obj_GM_RM017_bytetrack_bt_0012 | 162 | 210 | same_physical_vehicle | 0.9 | dark sedan following the white SUV; visible from left to right across frames 162-210 | co-occurs with 0010 and 0014 in frame 184, so it is not the same vehicle as those tracks |
| PV_GM17_DARK_LEAD_CANDIDATE | oty1t_obj_GM_RM017_bytetrack_bt_0008;oty1t_obj_GM_RM017_bytetrack_bt_0014 | 145 | 212 | same_physical_vehicle | 0.65 | dark leading/right-edge vehicle; 0008 exits at the right edge by frame 181-182 and 0014 appears near the same edge from frame 184 | 0014 is only a small edge fragment and remains a candidate continuation of 0008, not a training/test identity truth |
| PV_GM17_WHITE_SUV | oty1t_obj_GM_RM017_bytetrack_bt_0010 | 151 | 189 | same_physical_vehicle | 0.95 | white SUV; appears as the middle vehicle across frames 151-189; co-occurs with dark vehicles | none for 0010 as a single physical vehicle; not independent from same-scene traffic context |
| PV_REL_0010_VS_0012 | oty1t_obj_GM_RM017_bytetrack_bt_0010;oty1t_obj_GM_RM017_bytetrack_bt_0012 | 162 | 189 | overlapping_different_vehicles | 0.98 | same frames show a white SUV and a separate dark sedan at different image positions | none |
| PV_REL_0012_VS_0014 | oty1t_obj_GM_RM017_bytetrack_bt_0012;oty1t_obj_GM_RM017_bytetrack_bt_0014 | 184 | 184 | overlapping_different_vehicles | 0.98 | frame 184 contains both track boxes simultaneously: 0012 on the left dark sedan, 0014 at the far right edge | none |
| PV_REL_0008_VS_0014 | oty1t_obj_GM_RM017_bytetrack_bt_0008;oty1t_obj_GM_RM017_bytetrack_bt_0014 | 181 | 184 | same_physical_vehicle | 0.65 | right-edge dark vehicle continuity from 0008 exit to 0014 fragment is plausible | 0014 fragment is too small for a hard identity claim |

## Observation State Audit

- direct_observable: `92`
- temporally_recoverable: `34`
- not_safely_recoverable: `62`
- natural truncation cases: `34`
- incorrect old visibility labels: `15`

## Complete-Observation Baseline

| model_target | model_name | input_features | sample_count | physical_vehicle_count | selected | parameters | median_error | p90_error | center_coverage_95 | full_box_coverage_95 | median_search_ratio | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| azimuth | linear_center_x | bbox_center_x | 92 | 2 | false | {"coefficients": [0.09704652], "intercept": -42.33557812, "ridge_alpha": 0.0} | 0.437468 | 1.177644 |  |  |  | complete-observable controlled fit; SAR GT used posthoc for mechanism evaluation only |
| azimuth | quadratic_center_x | bbox_center_x;bbox_center_x_sq | 92 | 2 | true | {"coefficients": [0.10234231, -7.54e-06], "intercept": -43.12392545, "ridge_alpha": 0.0} | 0.428394 | 1.157673 |  |  |  | complete-observable controlled fit; SAR GT used posthoc for mechanism evaluation only |
| azimuth | pinhole_like_effective | atan((bbox_center_x-400)/360) | 92 | 2 | false | {"coefficients": [0.67165213], "intercept": -3.55182094, "ridge_alpha": 0.0} | 0.690444 | 1.585435 |  |  |  | complete-observable controlled fit; SAR GT used posthoc for mechanism evaluation only |
| radial | gradient_boosting_reference | depth_D4;bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | false | reference_only;random_state=3401;max_depth=2;n_estimators=80 | 1.722598 | 5.387377 |  |  |  | reference only; not used as R1 mechanism projection |
| radial | depth_only_linear | depth_D4 | 92 | 2 | false | {"coefficients": [41.36527612], "intercept": 18.18559874, "ridge_alpha": 0.0} | 19.286194 | 40.975611 |  |  |  | interpretable complete-observable radial baseline |
| radial | bbox_geometry_linear | bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | true | {"coefficients": [-0.87848784, -1.23553812, 0.71459414], "intercept": 452.12739216, "ridge_alpha": 0.0} | 8.218456 | 22.310641 |  |  |  | interpretable complete-observable radial baseline |
| radial | depth_plus_bbox_ridge | depth_D4;bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | false | {"coefficients": [7.99359194, -0.81883957, -0.86590487, -0.18623806], "intercept": 673.12618677, "ridge_alpha": 1.0} | 8.171366 | 23.186981 |  |  |  | interpretable complete-observable radial baseline |
| complete_observation_selected | quadratic_center_x+bbox_geometry_linear | bbox_center_x;bbox_center_x_sq;bbox_width;bbox_height;bbox_bottom_y | 92 | 2 | true | {"azimuth": "{\"coefficients\": [0.10234231, -7.54e-06], \"intercept\": -43.12392545, \"ridge_alpha\": 0.0}", "radial": "{\"coefficients\": [-0.87848784, -1.23553812, 0.71459414], \"intercept\": 452.12739216, \"ridge_alpha\": 0.0}", "intervals": {"az_q50": 1.0, "az_q95": 2.0, "rad_q50": 8.218456189457498, "rad_q95": 31.795472356059967}} | az=0.428394;radial=8.218456 | az=1.157673;radial=22.310641 | 0.945652 | 0 | 0.00107227 | selected R1 interpretable complete-vehicle projection baseline |

## Projection Comparison

| evaluation_group | method | sample_count | azimuth_median_error | azimuth_p90_error | radial_median_error | radial_p90_error | center_coverage_95 | full_box_coverage_95 | median_search_ratio | multi_target_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| direct_observable_control | M0_local_direct_projection | 92 | 0.428394 | 1.157673 | 8.218456 | 22.310641 | 0.945652 | 0 | 0.00107227 | 0 |
| direct_observable_control | M1_interval_inflation_only | 92 | 0.428394 | 1.157673 | 8.218456 | 22.310641 | 0.945652 | 0 | 0.00107227 | 0 |
| direct_observable_control | M2_recovered_full_vehicle_state | 92 | 0.428394 | 1.157673 | 8.218456 | 22.310641 | 0.945652 | 0 | 0.00107227 | 0 |
| natural_truncation | M0_local_direct_projection | 34 | 1.103418 | 2.921491 | 24.599103 | 63.997887 | 0.470588 | 0 | 0.00107227 | 0 |
| natural_truncation | M1_interval_inflation_only | 34 | 1.103418 | 2.921491 | 24.599103 | 63.997887 | 0.470588 | 0 | 0.00107227 | 0 |
| natural_truncation | M2_recovered_full_vehicle_state | 18 | 0.9606 | 1.941507 | 30.867945 | 41.388449 | 0.888889 | 0 | 0.00213177 | 0 |
| simulated_truncation | M0_local_direct_projection | 120 | 3.718112 | 6.048506 | 61.461814 | 113.955562 | 0.225 | 0 | 0.00107227 | 0 |
| simulated_truncation | M1_interval_inflation_only | 120 | 3.718112 | 6.048506 | 61.461814 | 113.955562 | 0.4 | 0 | 0.00525096 | 0 |
| simulated_truncation | M2_recovered_full_vehicle_state | 120 | 0.381762 | 1.040682 | 9.616955 | 18.736635 | 0.916667 | 0 | 0.00107227 | 0 |

## Recovery

- recovered samples: `138`
- blocked samples: `16`
- simulated azimuth P90 improvement: `82.79%`
- simulated radial P90 improvement: `83.56%`
- natural truncation radial P90 improvement: `35.33%`

## Dominant Failures

`{'weak_calibration_model_suspect': 17, 'insufficient_complete_anchors': 12}`

## Created Files

- `reports/oty2/oty2_wgv3_5a_r1_physical_vehicle_identity_audit_20260710.md`
- `reports/oty2/samples/oty2_wgv3_5a_r1_physical_vehicle_map_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r1_observation_state_audit_20260710.csv`
- `reports/oty2/oty2_wgv3_5a_r1_complete_vehicle_mechanism_20260710.md`
- `reports/oty2/samples/oty2_wgv3_5a_r1_complete_vehicle_baseline_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r1_simulated_truncation_manifest_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r1_natural_truncation_cases_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r1_recovered_full_vehicle_states_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r1_projection_comparison_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r1_failure_cases_20260710.csv`
- `reports/oty2/oty2_wgv3_5a_r1_visual_diagnosis_20260710.md`
- `reports/oty2/oty2_wgv3_5a_r1_closure_20260710.md`

## Visual Outputs

- identity: `outputs/wgv3_5a_r1_20260710/identity_contact_sheet.png`
- overlap: `outputs/wgv3_5a_r1_20260710/frame_overlap_contact_sheet.png`
- complete: `outputs/wgv3_5a_r1_20260710/complete_contact_sheet.png`
- sim_left: `outputs/wgv3_5a_r1_20260710/sim_left_contact_sheet.png`
- sim_right: `outputs/wgv3_5a_r1_20260710/sim_right_contact_sheet.png`
- sim_bottom: `outputs/wgv3_5a_r1_20260710/sim_bottom_contact_sheet.png`
- natural_all: `outputs/wgv3_5a_r1_20260710/natural_all_contact_sheet.png`
- failure_all: `outputs/wgv3_5a_r1_20260710/failure_all_contact_sheet.png`

## Direct Answers

1. GM_RM017表现好主要因为中距离完整车体阶段成立：光学框中心、尺寸和相对深度仍能近似代表整车状态；这不是单纯场景偶然。
2. 模拟截断能复现GM_RM019式失败机制：左右截断先破坏方位中心，底部/半车截断显著污染径向深度和尺寸含义。
3. 仅扩大不确定区间不够：M1能提高覆盖但不修正中心和深度，搜索面积也随之扩大。
4. 时序整车恢复显著改善SAR投影，尤其在模拟截断中把M0退化拉回完整状态基线；自然截断改善取决于完整锚点质量。
5. 可以进入WGV3.5A-R2的GM_RM019真实截断验证，但必须沿用R1的观测状态、身份审计和锚点阻断规则，不能恢复成原split泛化口径。
