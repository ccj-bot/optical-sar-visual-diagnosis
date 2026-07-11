# GM_RM019 静态物理因素假设登记表 v0

OTY2（Optical Timeline Y2，光学时序辅助阶段二）本轮仅登记 SAR（Synthetic Aperture Radar，合成孔径雷达）静态图像域的物理因素假设。GT（Ground Truth，真值标注）只作为事后控制点。PSF（Point Spread Function，点扩散函数）只作为弱响应反例解释之一。

## 边界

- 状态全部为 `hypothesis`。
- 不生成候选框，不修改 bbox，不做 selector、ranking、best box、最终标注、GT 修改、身份闭合或加权总分。
- 散射原子不是车辆；局部响应单元不是完整车辆；边界变体族只表达同一局部响应核心的不同边界；同目标候选关系不是同车真值。
- GM_RM017 只作为方法、留出验证设计和反例来源；本报告不把 GM_RM017 结论复制成 GM_RM019 结论。

## Part A 依赖状态

- residual 语义修正已完成：全量 component audit rows=2368，matched frozen-atom / non-residual rows=52，真正 dropped residual rows=2316，proximity residual candidates=1563，unknown match-status rows=0。
- 因此 Part B 使用修正后的 residual 表，且不把 2368 行整体解释为 residual。

## 登记因素

### GM019_STATIC_H01 距离向-方位向方向性展宽的图像域替代观测量

- status: `hypothesis`
- 物理假设：同一局部响应对象在 SAR 图像域可能表现出距离向或方位向的非对称展宽；方向性展宽比 GT 框宽高更接近静态散射支撑观测，但仍不等于真实车辆尺寸。
- 可测观测量：局部响应框宽高、长轴/短轴、radial_span、azimuth_span、边界族不确定包络、方向主导类别。
- 可用于拟合的确认点：GT 中心、GT 局部区域、R1.1 response-unit / boundary-family GT-instance 矩阵；只用于事后拟合误差和坐标参考。
- GT 可以拟合或提供：GT 可提供局部坐标锚点、距离/方位参考和形态拟合误差。
- GT 不能确认：GT 不能确认散射支撑尺寸、不能把局部响应扩展成完整车辆框，不能用于选择唯一响应单元。
- 当前支持证据：units=250;width_dominant=166;height_dominant=84;median_unit_width_px=60;median_unit_height_px=48;median_structure_long_axis_px=137.427138;median_radial_span_px=2.283447;median_azimuth_span_px=2.026441
- 当前反例：GT 框宽高不等于真实散射支撑；背景弧线或近场边界也能形成长条形响应。
- 适用条件：仅适用于已有冻结局部响应对象和边界族；需要同时保留背景反例和遮罩边界状态。
- 必须动态确认：true
- 需要在 GM_RM017 验证的问题：在 GM_RM017 连续窗口中，方向性展宽是否比 GT 框宽高更稳定地解释响应支撑，并避免 F4 尺度拟合失败？
- 来源文件：reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv;reports/oty2/samples/oty2_wgv3_6a_a1_8a_vehicle_structure_hypothesis_20260711.csv
- 代表帧：27;28;29;30;31;32;40;46;60;77;78;79;...(+22)

### GM019_STATIC_H02 主体核心-端点热点-侧向响应的候选拓扑

- status: `hypothesis`
- 物理假设：主体核心、端点热点和侧向响应的相对位置可形成静态候选拓扑，用于提出同目标候选关系，但不能单帧确认同一车辆或真实部件。
- 可测观测量：accepted graph link 计数、part-part 候选边、中心距离、bbox gap、spatial_relation、共享核心原子。
- 可用于拟合的确认点：GT 局部区域可检查候选拓扑是否落在目标附近；focus visual review 可作人工审阅线索。
- GT 可以拟合或提供：GT 可检查拓扑是否位于事后目标区域附近，并提供正负对照。
- GT 不能确认：GT 不能把候选边升级为同车真值，不能确认端点或侧向响应是车辆物理部件。
- 当前支持证据：same_object_candidate_edges=148;edge_type_counts={'accepted_graph_link_candidate': 137, 'part_part_candidate': 11};spatial_relation_counts={'diagonal_adjacent': 9, 'overlapping_or_touching': 100, 'range_stack_side_axis': 19, 'side_by_side_endpoint_axis': 20}
- 当前反例：孤立端点样小峰、邻近车辆和非共享核心响应可产生类似拓扑。
- 适用条件：必须有主体核心或已冻结局部响应对象；孤立热点不得单独进入该因素。
- 必须动态确认：true
- 需要在 GM_RM017 验证的问题：在 GM_RM017 连续窗口中，候选拓扑是否随共同运动保持相对稳定，且能排除邻车短时同向造成的假拓扑？
- 来源文件：reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_same_object_candidate_edges_20260711.csv;reports/oty2/samples/oty2_wgv3_6a_a1_8a_point_to_structure_hypothesis_ledger_20260711.csv
- 代表帧：27;28;29;30;31;32;34;39;40;52;77;78;...(+25)

### GM019_STATIC_H03 固定背景结构和孤立小峰的静态可解释性

- status: `hypothesis`
- 物理假设：固定背景、背景弧线、道路边缘或孤立小峰可解释一部分高响应；静态背景可解释性应作为负向对照，而不是车辆支持。
- 可测观测量：background_counterexamples 数量、alternative_exclusion_reason、isolated_small_atom / background_arc 角色、positive-negative closure 中的负向排除说明。
- 可用于拟合的确认点：GT 外邻近区域、已记录背景反例、非车辆 pair 和 focus 帧审阅说明。
- GT 可以拟合或提供：GT 可标定目标局部区域和邻近非目标对照带。
- GT 不能确认：GT 不能证明 GT 外亮点必为背景，也不能把稳定高响应直接变成硬拒绝规则。
- 当前支持证据：background_counterexamples=46;positive_negative_rows=40;physical_field_insufficient_rows=40
- 当前反例：固定背景可能闪烁；静止或慢速车辆也可能短时呈现稳定高响应。
- 适用条件：只作为负向解释和反例登记；必须保留 unresolved 状态，不能覆盖动态证据。
- 必须动态确认：true
- 需要在 GM_RM017 验证的问题：在 GM_RM017 中，F2 背景稳定性如何结合 F3 间歇可见，避免把背景闪烁误作车辆弱响应？
- 来源文件：reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_background_counterexamples_20260711.csv;reports/oty2/samples/oty2_wgv3_6a_a1_8a_positive_negative_closure_20260711.csv
- 代表帧：27;28;29;30;31;32;34;39;40;46;52;60;...(+33)

### GM019_STATIC_H04 近场扇形边界接触与可见响应中心审慎解释

- status: `hypothesis`
- 物理假设：近场遮罩、扇形边界或图像边界接触会使 SAR 可见响应中心偏离完整车辆中心；应优先登记为区间/重叠控制问题，而不是中心监督。
- 可测观测量：mask class、center supervision 可用性、interval supervision 可用性、bottom valid margin、mask boundary distance、optical visibility_state 中的 boundary_truncation。
- 可用于拟合的确认点：GT 中心、遮罩交叠比例、mask boundary distance 和可见响应框；只用于事后审查可见区域。
- GT 可以拟合或提供：GT 可测试遮罩内可见响应与标注区域的重叠关系。
- GT 不能确认：GT 不能确认遮罩内响应中心就是完整车辆中心，不能用于修正最终框。
- 当前支持证据：mask_rows=16;center_supervision_false=16;interval_supervision_true=16;mask_class_counts={'SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE': 11, 'SAR_MASK_S2_CENTER_CENSORED': 5};paired_rows=16;paired_boundary_truncation_rows=2;optical_state_allowed_for_sar_mapping_audit=8
- 当前反例：并非所有边界接触都表示真实截断；无局部热带或背景边缘也可触发边界接触。
- 适用条件：仅适用于 mask/扇形边界接触、近距边界或 optical 状态提示存在截断风险的帧。
- 必须动态确认：true
- 需要在 GM_RM017 验证的问题：GM_RM017 留出窗口中，边界接触样本能否通过连续可见响应区间验证，而不是用中心误差强行拟合？
- 来源文件：reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv;reports/oty2/samples/oty2_wgv3_5a_r2c_gm019_failure_cases_20260711.csv;reports/oty2/samples/oty2_wgv3_5a_paired_annotations_20260710.csv
- 代表帧：0;4;8;27;31;77;81;212;238;269;273;288;...(+3)

### GM019_STATIC_H05 弱 residual 响应的多阈值持续性与 PSF 旁瓣区分

- status: `hypothesis`
- 物理假设：靠近冻结响应区域的弱 residual 可能包含被阈值遗漏的散射支撑，也可能只是 PSF 旁瓣、噪声或背景纹理；需要多阈值持续性和动态共运动来区分。
- 可测观测量：residual_component_status、proximity_residual_candidate、component_energy、component_area、near_frozen_core、near_boundary_family、跨阈值持续性。
- 可用于拟合的确认点：GT 局部区域、冻结响应单元、边界族和 residual 近邻关系；用于事后测量，不用于新增候选。
- GT 可以拟合或提供：GT 可作为局部区域控制点，比较 weak residual 是否反复出现在目标附近。
- GT 不能确认：GT 不能把 residual 直接确认成车辆弱部件，不能据此增加 Gate、Top-K 规则或候选排序。
- 当前支持证据：component_rows=2368;residual_status_counts={'dropped_unassigned_residual': 2316, 'matched_frozen_atom_non_residual': 52};proximity_residual_candidates=1563;gt_matrix_rows=108;max_eval_iou=0.567172
- 当前反例：大量 dropped residual 不靠近冻结区域；PSF 旁瓣、道路边缘和背景纹理可能伪装成弱侧向响应。
- 适用条件：只适用于已完成 residual_semantics_fix 后的 dropped residual 行；必须排除已匹配冻结原子行。
- 必须动态确认：true
- 需要在 GM_RM017 验证的问题：在 GM_RM017 中，弱 residual 是否能在多阈值和连续窗口中保持与主体响应共运动，并与 PSF 旁瓣分离？
- 来源文件：reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_proximity_residual_component_audit_20260711.csv;reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_20260711.csv;reports/oty2/samples/oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_family_gt_instance_matrix_20260711.csv
- 代表帧：27;28;29;30;31;32;34;39;40;46;52;60;...(+34)

## 反例索引

| counterexample_id | factor_id | 反例 | 代表帧 | 边界 |
| --- | --- | --- | --- | --- |
| GM019_STATIC_CE01 | GM019_STATIC_H01 | GT 框宽高不等于散射支撑尺寸 | 27;29;30;31 | 只能作为拟合观测量，不作为车辆尺寸 Gate。 |
| GM019_STATIC_CE02 | GM019_STATIC_H02 | 孤立端点样小峰和邻车可伪装拓扑 | 27;28;29;30;31 | 必须保留为候选边；孤立热点不得单独闭合。 |
| GM019_STATIC_CE03 | GM019_STATIC_H03 | 固定背景闪烁和稳定高响应 | 27;28;29;30;31 | 只能作负向解释，不能变成硬 Gate。 |
| GM019_STATIC_CE04 | GM019_STATIC_H04 | 遮罩内响应中心不是完整车辆中心 | 0;4;8;27;31 | 仅用于边界/遮罩接触场景的审慎解释。 |
| GM019_STATIC_CE05 | GM019_STATIC_H05 | PSF 旁瓣、纹理噪声和非邻近 residual | 27;28;29;30;31;78;79;80;81 | 必须先通过多阈值持续性和动态共运动，再进入后续验证。 |

## GM_RM017 参考边界

- F1 共运动在单一线程中获得支持，但邻车可能短时同向；GM_RM019 只能把拓扑/弱响应送去验证。
- F2 固定背景稳定性获得支持，但固定背景可能闪烁，不得成为硬 Gate。
- F3 局部响应间歇可见只有部分支持，背景闪烁是反例。
- F4 尺度-距离/方位关系在留出集劣于常量尺寸；GM_RM019 应改用方向性展宽、响应支撑和边界状态，而不是 GT 框宽高。
- F5 光学-SAR 趋势只有弱符号一致性，精确时间戳和偏移仍未解决。

## 观测表摘要

- OBS_GM019_STATIC_001 / GM019_STATIC_H01: local_unit_axis_distribution = `units=250;width_dominant=166;height_dominant=84;median_unit_width_px=60;median_unit_height_px=48;median_structure_long_axis_px=137.427138;median_radial_span_px=2.283447;median_azimuth_span_px=2.026441`
- OBS_GM019_STATIC_002 / GM019_STATIC_H02: candidate_edge_topology_counts = `same_object_candidate_edges=148;edge_type_counts={'accepted_graph_link_candidate': 137, 'part_part_candidate': 11};spatial_relation_counts={'diagonal_adjacent': 9, 'overlapping_or_touching': 100, 'range_stack_side_axis': 19, 'side_by_side_endpoint_axis': 20}`
- OBS_GM019_STATIC_003 / GM019_STATIC_H03: background_counterexample_pressure = `background_counterexamples=46;positive_negative_rows=40;physical_field_insufficient_rows=40`
- OBS_GM019_STATIC_004 / GM019_STATIC_H04: near_field_mask_boundary_semantics = `mask_rows=16;center_supervision_false=16;interval_supervision_true=16;mask_class_counts={'SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE': 11, 'SAR_MASK_S2_CENTER_CENSORED': 5};paired_rows=16;paired_boundary_truncation_rows=2;optical_state_allowed_for_sar_mapping_audit=8`
- OBS_GM019_STATIC_005 / GM019_STATIC_H05: residual_proximity_and_gt_control = `component_rows=2368;residual_status_counts={'dropped_unassigned_residual': 2316, 'matched_frozen_atom_non_residual': 52};proximity_residual_candidates=1563;gt_matrix_rows=108;max_eval_iou=0.567172`

## Replay

- verify-static-registry: `PASS`
- replay evidence: `registry:PASS; counterexamples:PASS; observations:PASS; report:PASS`

## 输出文件

- `reports/oty2/oty2_gm_rm019_static_physical_factor_registry_20260712.md`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_factor_registry_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_factor_counterexamples_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_physical_factor_observations_20260712.csv`
