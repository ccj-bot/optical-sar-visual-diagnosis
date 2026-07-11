# OTY2 WGV3.6A-A1.8A Vehicle Response Grammar Audit

## Boundary

- requested start commit: `98302c72258385b7e30f6ac9980f0336653b3578`
- scattering atom trace SHA256: `0e24a0db974bb3e13abe53fc911d187d9beab08bd3d8ccc7ff744a2b3863f46b`
- scene: `GM_RM019`
- generate/evaluate separation: `PASS`
- generate phase target manual boxes loaded: `false`
- evaluate phase target boxes loaded after freeze: `true`
- A1.6/A1.7/A1.7R historical outputs modified: `false`
- final annotation / revised GT / selector / ranking / training: `false`
- GM_RM011 executed: `false`
- TRACK_BEFORE_DETECT_DIAGNOSTIC_ONLY: `not_executed`

## Geometry And Unit Provenance

- `build_geometry().radial` is pixel-radius geometry, not verified meters.
- `build_geometry().azimuth` is image fan angle in degrees, not a calibrated SAR bearing claim.
- `ground_x/ground_y` are intentionally blank because no reliable ground-meter transform was verified.
- Structure extents are reported as `geometry_coordinate_pixel_radius_not_meter`.

## Reviewed Windows

- positive frames: `27-31, 78-81, 270-273, 289-290`
- negative/uncertain frames: `32,40,46,60,77,212,213,220,227,238,239,243,250,260,269,276,280,284,288`
- runtime visual sheets:
  - `outputs/wgv3_6a_a1_8a_20260711/a1_8a_white_positive_atom_structure_sheet.png`
  - `outputs/wgv3_6a_a1_8a_20260711/a1_8a_white_negative_atom_structure_sheet.png`
  - `outputs/wgv3_6a_a1_8a_20260711/a1_8a_silver_positive_atom_structure_sheet.png`
  - `outputs/wgv3_6a_a1_8a_20260711/a1_8a_silver_negative_atom_structure_sheet_a.png`
  - `outputs/wgv3_6a_a1_8a_20260711/a1_8a_silver_negative_atom_structure_sheet_b.png`
  - `outputs/wgv3_6a_a1_8a_20260711/a1_8a_positive_negative_contrast_sheet.png`
  - `outputs/wgv3_6a_a1_8a_20260711/a1_8a_part_temporal_drift_sheet.png`
- eval-only overlay sheet: `outputs/wgv3_6a_a1_8a_20260711/a1_8a_eval_only_target_overlay_sheet.png`

## Counts

- scattering atom count: `139`
- role counts: `body_core=13, side_ridge=20, endpoint_hotspot=8, background_arc=6, unresolved=53`
- entity counts: `vehicle_supported=13, vehicle_possible=0, background_like=13, unresolved=14`
- grammar statuses: `stable_global_candidate=0, conditional_candidate=15, falsified=0, not_testable=25`
- vehicle-scale long-axis median in positive candidate structures: `110.9375` geometry units
- negative/background long-axis median: `138.760178` geometry units
- positive false rejects: `0`
- negative false accepts: `0`

## Object-Level Visual Review

The review rows are structure/object rows, not target-coverage rows. Roles are proposed from atom features and then interpreted with the rendered object sheets; target boxes appear only in EVAL_ONLY overlays.

Visual inspection notes:

- White SUV 27-31: the lower compact response and short ridge are visible across adjacent frames; endpoint-like small atoms remain support only, not standalone vehicles.
- White SUV 78-81: a strong horizontal/background arc is visible above the lower response; the audit keeps the arc as background-like while retaining the lower core as local vehicle support.
- Silver MPV 270-273 and 289-290: the lower response is weaker and partly fragmented; supported rows are conditional local structures, while far-side arcs and isolated peaks remain excluded.
- Negative/uncertain windows: 32/40/46/60/77 and 239-288 contain many arc-like or isolated responses; no negative structure is promoted to vehicle-supported.
- EVAL_ONLY target boxes were opened after freeze and used only to visually check overlays, not to extract atoms or assign roles.

| review_id | sar_frame | review_object_type | object_id | proposed_role | same_vehicle_support | background_support | uncertain | physical_reason_cn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RV8A_001 | 27 | vehicle_structure_hypothesis | S8A_F027_001 | body_core;unresolved_atom | true | false | false | 白车 27-31 底部局部响应可见短脊线/核心/端点候选；body_core;unresolved_atom 形成几何像素尺度结构，目标框未参与角色赋值。 |
| RV8A_002 | 28 | vehicle_structure_hypothesis | S8A_F028_002 | body_core;unresolved_atom | true | false | false | 白车 27-31 底部局部响应可见短脊线/核心/端点候选；body_core;unresolved_atom 形成几何像素尺度结构，目标框未参与角色赋值。 |
| RV8A_003 | 29 | vehicle_structure_hypothesis | S8A_F029_003 | side_ridge;unresolved_atom | true | false | false | 白车 27-31 底部局部响应可见短脊线/核心/端点候选；side_ridge;unresolved_atom 形成几何像素尺度结构，目标框未参与角色赋值。 |
| RV8A_004 | 30 | vehicle_structure_hypothesis | S8A_F030_004 | side_ridge;unresolved_atom | true | false | false | 白车 27-31 底部局部响应可见短脊线/核心/端点候选；side_ridge;unresolved_atom 形成几何像素尺度结构，目标框未参与角色赋值。 |
| RV8A_005 | 31 | vehicle_structure_hypothesis | S8A_F031_005 | side_ridge;unresolved_atom | true | false | false | 白车 27-31 底部局部响应可见短脊线/核心/端点候选；side_ridge;unresolved_atom 形成几何像素尺度结构，目标框未参与角色赋值。 |
| RV8A_006 | 32 | vehicle_structure_hypothesis | S8A_F032_006 | side_ridge;unresolved_atom | false | false | true | 图上对象 side_ridge;unresolved_atom 与车辆部件关系不充分，物理尺度字段不足以判定。 |
| RV8A_007 | 40 | vehicle_structure_hypothesis | S8A_F040_007 | body_core;unresolved_atom | false | false | true | 图上对象 body_core;unresolved_atom 与车辆部件关系不充分，物理尺度字段不足以判定。 |
| RV8A_008 | 46 | vehicle_structure_hypothesis | S8A_F046_008 | body_core;unresolved_atom | false | false | true | 图上对象 body_core;unresolved_atom 与车辆部件关系不充分，物理尺度字段不足以判定。 |
| RV8A_009 | 60 | vehicle_structure_hypothesis | S8A_F060_009 | unresolved_atom | false | true | false | 图上对象更符合 unresolved_atom 的背景/孤立响应，缺少车辆尺度闭合。 |
| RV8A_010 | 77 | vehicle_structure_hypothesis | S8A_F077_010 | unresolved_atom | false | true | false | 图上对象更符合 unresolved_atom 的背景/孤立响应，缺少车辆尺度闭合。 |
| RV8A_011 | 78 | vehicle_structure_hypothesis | S8A_F078_011 | body_core | true | false | false | 白车 78-81 下侧核心在水平背景弧线下方保留；body_core 只支持局部车辆响应，红色弧线未并入车辆实体。 |
| RV8A_012 | 78 | vehicle_structure_hypothesis | S8A_F078_012 | background_arc | false | true | false | 图上 background_arc 更像沿扇形/道路背景延展的弧线或横向线状响应，缺少车辆尺度闭合。 |
| RV8A_013 | 79 | vehicle_structure_hypothesis | S8A_F079_013 | body_core | true | false | false | 白车 78-81 下侧核心在水平背景弧线下方保留；body_core 只支持局部车辆响应，红色弧线未并入车辆实体。 |
| RV8A_014 | 79 | vehicle_structure_hypothesis | S8A_F079_014 | background_arc | false | true | false | 图上 background_arc 更像沿扇形/道路背景延展的弧线或横向线状响应，缺少车辆尺度闭合。 |
| RV8A_015 | 80 | vehicle_structure_hypothesis | S8A_F080_015 | body_core | true | false | false | 白车 78-81 下侧核心在水平背景弧线下方保留；body_core 只支持局部车辆响应，红色弧线未并入车辆实体。 |
| RV8A_016 | 80 | vehicle_structure_hypothesis | S8A_F080_016 | background_arc | false | true | false | 图上 background_arc 更像沿扇形/道路背景延展的弧线或横向线状响应，缺少车辆尺度闭合。 |
| ... |  |  |  |  |  |  |  |  |

## Positive-Negative Closure

| closure_id | structure_id | sar_frame | positive_false_reject | negative_false_accept | cannot_judge | positive_vehicle_support_cn | negative_background_rejection_cn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CL8A_001 | S8A_F027_001 | 27 | false | false | false | 尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_002 | S8A_F028_002 | 28 | false | false | false | 尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_003 | S8A_F029_003 | 29 | false | false | false | 尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_004 | S8A_F030_004 | 30 | false | false | false | 尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_005 | S8A_F031_005 | 31 | false | false | false | 尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_006 | S8A_F032_006 | 32 | false | false | true | 只有部分车辆响应条件成立，不能作为最终身份或定位结论。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_007 | S8A_F040_007 | 40 | false | false | true | 只有部分车辆响应条件成立，不能作为最终身份或定位结论。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_008 | S8A_F046_008 | 46 | false | false | true | 只有部分车辆响应条件成立，不能作为最终身份或定位结论。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_009 | S8A_F060_009 | 60 | false | false | false | 只有部分车辆响应条件成立，不能作为最终身份或定位结论。 | 该对象已经因背景弧线、孤立峰值、尺度不闭合或运动不一致被排除。 |
| CL8A_010 | S8A_F077_010 | 77 | false | false | false | 只有部分车辆响应条件成立，不能作为最终身份或定位结论。 | 该对象已经因背景弧线、孤立峰值、尺度不闭合或运动不一致被排除。 |
| CL8A_011 | S8A_F078_011 | 78 | false | false | false | 尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_012 | S8A_F078_012 | 78 | false | false | false | 只有部分车辆响应条件成立，不能作为最终身份或定位结论。 | 该对象已经因背景弧线、孤立峰值、尺度不闭合或运动不一致被排除。 |
| CL8A_013 | S8A_F079_013 | 79 | false | false | false | 尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_014 | S8A_F079_014 | 79 | false | false | false | 只有部分车辆响应条件成立，不能作为最终身份或定位结论。 | 该对象已经因背景弧线、孤立峰值、尺度不闭合或运动不一致被排除。 |
| CL8A_015 | S8A_F080_015 | 80 | false | false | false | 尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。 | 邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。 |
| CL8A_016 | S8A_F080_016 | 80 | false | false | false | 只有部分车辆响应条件成立，不能作为最终身份或定位结论。 | 该对象已经因背景弧线、孤立峰值、尺度不闭合或运动不一致被排除。 |
| ... |  |  |  |  |  |  |  |

## Temporal Continuity

| temporal_id | window_id | role | frames | role_persistence | shared_motion_trend | conclusion_cn |
| --- | --- | --- | --- | --- | --- | --- |
| T8A_001 | white_27_31 | body_core | 27;28 | 2/5 | false | 该角色在短窗口中不稳定或样本不足，只能保留为条件/不可测试。 |
| T8A_002 | white_27_31 | side_ridge | 28;29;30;31 | 4/5 | true | 局部部件有短窗连续性，但允许出现/消失，不能单独闭合为车辆。 |
| T8A_003 | white_27_31 | endpoint_hotspot | 27;28 | 2/5 | false | 该角色在短窗口中不稳定或样本不足，只能保留为条件/不可测试。 |
| T8A_004 | white_78_81 | body_core | 78;79;80;81 | 4/4 | true | 主体核心在短窗口内有非跳变相邻帧支持，可作为车辆响应条件之一。 |
| T8A_005 | white_78_81 | side_ridge | 78;79;80;81 | 4/4 | true | 局部部件有短窗连续性，但允许出现/消失，不能单独闭合为车辆。 |
| T8A_006 | white_78_81 | background_arc | 78;79;80;81 | 4/4 | true | 弧线样结构不应因局部连续或高能量升级为车辆部件。 |
| T8A_007 | silver_270_273 | body_core | 270 | 1/4 | false | 该角色在短窗口中不稳定或样本不足，只能保留为条件/不可测试。 |
| T8A_008 | silver_270_273 | side_ridge | 270;273 | 2/4 | true | 局部部件有短窗连续性，但允许出现/消失，不能单独闭合为车辆。 |
| T8A_009 | silver_289_290 | body_core | 289 | 1/2 | false | 该角色在短窗口中不稳定或样本不足，只能保留为条件/不可测试。 |
| T8A_010 | silver_289_290 | side_ridge | 289;290 | 2/2 | true | 局部部件有短窗连续性，但允许出现/消失，不能单独闭合为车辆。 |

## Hypothesis Ledger

| hypothesis_id | hypothesis_cn | status | counterexamples | next_test_required |
| --- | --- | --- | --- | --- |
| H8A_001 | 车辆主体核心具有稳定的几何长短轴范围，但当前单位只能称为像素极坐标几何尺度。 | conditional_candidate | none_in_layered_gate | intermediate-frame blind review without target overlays |
| H8A_002 | 端点热点与主体核心存在有界距离关系，但不能由高峰值单独闭合为车辆。 | conditional_candidate | negative endpoint-like isolated peaks without body_core | object-level blind review of endpoint roles |
| H8A_003 | 背景弧线具有更大弧线一致性或背景冲突，不应进入车辆支持实体。 | conditional_candidate | none_in_layered_gate | more background-only frames across scenes |
| H8A_004 | 孤立小峰不能独立闭合为车辆尺度结构。 | stable_global_candidate | none promoted by layered gate | stress on intermediate blind frames |

## Failure Cases

| case_id | failure_type | sar_frame | object_id | physical_vehicle_id | reason_cn | runtime_png | eval_png |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FAIL8A_001 | mechanism_not_globally_established |  |  | GM_RM019 | 正负闭环只在局部窗口形成条件支持，尚未完成中间帧盲评，不能进入 A1.7R2。 | outputs/wgv3_6a_a1_8a_20260711/a1_8a_positive_negative_contrast_sheet.png | outputs/wgv3_6a_a1_8a_20260711/a1_8a_eval_only_target_overlay_sheet.png |

## Gate Verdicts

- `GEOMETRY_UNIT_PROVENANCE_VALID`: `PASS_NO_METRIC_METER_CLAIM`
- `OBJECT_LEVEL_VISUAL_REVIEW_NON_CIRCULAR`: `PASS`
- `SCATTERING_ATOM_ROLE_SEPARABLE`: `PARTIAL`
- `VEHICLE_SCALE_RESPONSE_SUPPORTED`: `PARTIAL`
- `POSITIVE_NEGATIVE_MORPHOLOGY_CLOSED`: `PARTIAL`
- `BACKGROUND_ARC_REJECTION_SUPPORTED`: `TRUE`
- `SHORT_WINDOW_ROLE_DRIFT_SUPPORTED`: `PARTIAL`
- `POINT_TO_STRUCTURE_GENERALIZATION_SUPPORTED`: `PARTIAL`
- `VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2`: `NO`
- `INTERMEDIATE_FRAME_BLIND_EVAL_PENDING`: `true`
- `GM_RM011_BLOCKED`: `true`

## Created Files

- `reports/oty2/oty2_wgv3_6a_a1_8a_vehicle_response_grammar_audit_20260711.md`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_geometry_unit_provenance_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_scattering_atom_trace_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_object_level_visual_review_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_atom_relation_graph_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_vehicle_structure_hypothesis_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_positive_negative_closure_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_part_temporal_continuity_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_vehicle_supported_observation_entities_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_point_to_structure_hypothesis_ledger_20260711.csv`
- `reports/oty2/samples/oty2_wgv3_6a_a1_8a_failure_cases_20260711.csv`

## Research Judgment

A1.8A establishes a conditional point-to-structure audit layer, not a final vehicle localizer. The current evidence separates some body-core/endpoint/ridge-like responses from background arcs and isolated peaks in local windows, but unit provenance remains non-metric and intermediate-frame blind evaluation is still pending. Therefore A1.7R2 must not consume all compact assemblies; it may only consume vehicle-supported or vehicle-possible observation entities after this layer is rechecked.