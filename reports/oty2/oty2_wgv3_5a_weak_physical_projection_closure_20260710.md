# OTY2 WGV3.5A Weak Physical Feasible-Field Closure

Date: 20260710

WGV3.5A status: `CLOSED_SCENE_SPECIFIC_WEAK_CALIBRATION_ONLY`

## Boundary

This closes a weak-calibration feasible-field experiment. SAR GT is used only for weak calibration/evaluation from existing correspondence rows. No GT or manual annotation is modified, no final SAR box is emitted, and no selector/ranking stage is introduced.

## Holdout Metrics

| model_variant | test_pair_count | center_coverage_50 | center_coverage_80 | center_coverage_95 | full_box_coverage_95 | median_search_ratio | p90_search_ratio | median_azimuth_error | p90_azimuth_error | median_radial_error | p90_radial_error | multi_target_rate | wrong_identity_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | 15 | 1 | 1 | 1 | 0.2 | 0.01496172 | 0.01496172 | 15.270456 | 23.061118 | 507.023 | 527.7256 | 0.866667 | 0.2 |
| P1 | 15 | 0.066667 | 0.066667 | 0.066667 | 0 | 0.00018258 | 0.00023299 | 13.240676 | 19.043645 | 258.7801 | 273.493035 | 0.066667 | 0.066667 |
| P2 | 15 | 0.066667 | 0.066667 | 0.133333 | 0 | 0.0003288 | 0.0005221 | 13.240676 | 19.043645 | 258.7801 | 273.493035 | 0.066667 | 0.066667 |

## Ablation

| ablation_id | features | test_pair_count | median_radial_error | p90_radial_error | median_search_ratio | center_coverage_95 | interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | optical x only | 15 | 244.609878 | 298.524799 | 0.00091224 | 0.266667 | post-freeze holdout ablation; test labels used only for final scoring |
| B | optical x + bbox geometry | 15 | 388.097134 | 698.650585 | 0.00126735 | 0.266667 | post-freeze holdout ablation; test labels used only for final scoring |
| C | optical x + bbox geometry + depth | 15 | 296.407441 | 586.570677 | 0.00126735 | 0.266667 | post-freeze holdout ablation; test labels used only for final scoring |
| D | optical x + bbox geometry + depth + temporal smoothing | 15 | 291.850793 | 580.401766 | 0.00126735 | 0.266667 | post-freeze holdout ablation; test labels used only for final scoring |
| E | optical x + depth + temporal smoothing + heading proxy | 15 | 298.8063 | 592.19051 | 0.00126735 | 0.266667 | post-freeze holdout ablation; test labels used only for final scoring |
| F | full state including visibility uncertainty | 15 | 292.687515 | 526.660316 | 0.00126735 | 0.266667 | post-freeze holdout ablation; test labels used only for final scoring |

## Selected Models

| model_family | model_name | input_features | train_count | validation_count | selected | parameters | train_median_error | train_p90_error | validation_median_error | validation_p90_error | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| time | legacy_24_50_proxy | optical_frame | 71 | 52 | true | {"a": 2.0833333333333335, "b": 0.0} | 0.5 | 0.916667 | 0.5 | 0.833333 | SAR labels from test split not used |

| model_family | model_name | input_features | train_count | validation_count | selected | parameters | train_median_error | train_p90_error | validation_median_error | validation_p90_error | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| azimuth | linear_center_x | az_center | 71 | 52 | true | {"mode": "az_center"} | 0.709793 | 2.12969 | 0.589201 | 1.164437 | effective weak parameters only; not true intrinsics/extrinsics |

| model_family | model_name | input_features | train_count | validation_count | selected | parameters | train_median_error | train_p90_error | validation_median_error | validation_p90_error | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| radial | R3_gradient_boosting_reference | radial_r1 | 71 | 52 | true | {"depth_spearman_like": 0.7682092555331992, "mode": "radial_r1"} | 1.232517 | 4.762293 | 19.537142 | 66.214125 | nonlinear_reference_not_sole_report |

## Final Summary Fields

- Branch: `feature/oty2-posthoc-mechanism-validation`
- Start commit: `3d9b0118086ec5d3dfe970c68ee083dff529c842`
- Generation HEAD: `3d9b0118086ec5d3dfe970c68ee083dff529c842`
- Pair audit: total `204`, high-confidence `138`, scenes `['GM_RM017', 'GM_RM019']`, threads `9`, blocked `66`
- Depth audit: `GM_RM011=RELATIVE_DEPTH_UNSTABLE;GM_RM017=RELATIVE_DEPTH_MONOTONIC;GM_RM019=RELATIVE_DEPTH_UNSTABLE`; selected strategy `D4`; frame alignment recorded in `reports/oty2/samples/oty2_wgv3_5a_depth_strategy_audit_20260710.csv`
- Identity split: train `1` threads, validation `1`, test `1`, external `3`
- Freeze SHA256: `e8d59b7ae66c57e12b59eae9523f52973d267ce0fda09aed7ff7e6dae2f8790a`
- Test labels read before freeze: `false`
- Test threads used for fitting: `false`
- Heading usable count: `139`; unknown heading count: `13`
- Dominant failure counts: `{'radial_miss': 13, 'azimuth_miss': 11, 'edge_truncation_failure': 2}`

## Direct Answers

1. 在没有准确内参和外参、只有20 cm以内传感器间距的条件下，可以建立可用但场景/数据依赖的弱标定；当前关闭状态是 `CLOSED_SCENE_SPECIFIC_WEAK_CALIBRATION_ONLY`，不能称为真实三维标定。
2. 光学深度在本轮提供了径向压缩证据；B到C的P90径向误差改善为 `112.0799` px，但深度被标记为相对/弱单调来源，不当作米制距离。
3. 航向和车体尺度的额外压缩有限；D到E的P90改善为 `-11.7887` px，很多边缘/短轨迹样本仍退化为 unknown。
4. P1可以作为下一步批量标注迁移的物理前端候选；P2只有在航向稳定样本上可用，暂不建议把P2作为无人工复核的批量入口。

## Created Files

- `reports/oty2/oty2_wgv3_5a_pair_and_depth_audit_20260710.md`
- `reports/oty2/samples/oty2_wgv3_5a_paired_annotations_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_depth_strategy_audit_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_identity_safe_split_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_sar_polar_targets_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_optical_vehicle_states_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_time_calibration_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_azimuth_calibration_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_radial_calibration_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_heading_state_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_feasible_fields_p0_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_feasible_fields_p1_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_feasible_fields_p2_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_model_freeze_manifest_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_holdout_evaluation_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_ablation_results_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_failure_cases_20260710.csv`
- `reports/oty2/oty2_wgv3_5a_visual_feasible_field_diagnosis_20260710.md`
- `reports/oty2/oty2_wgv3_5a_weak_physical_projection_closure_20260710.md`
