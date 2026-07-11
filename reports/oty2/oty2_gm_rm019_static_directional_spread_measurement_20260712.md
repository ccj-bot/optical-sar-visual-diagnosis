# GM_RM019 静态 SAR 图像域方向性展宽测量

日期：20260712

## 边界

本报告只推进 `GM019_STATIC_H01`。SAR（Synthetic Aperture Radar，合成孔径雷达）灰度图仅用于事后机制诊断；GT（Ground Truth，真值标注）只用于分组和事后对照。本轮没有生成最终框、候选框、selector/ranking、修订 GT、身份真值、训练输出或阈值搜索。

## 几何来源

- SAR 灰度图：`D:/profile/research/data/GM_RM019/GM_RM019_SARframes_gray/*.png`，图像尺寸 `2308 x 1334`。
- 扇形图像原点：`(1154.0, 1330.6)`，来自 `tools/diagnostics/run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.py` 与 `tools/diagnostics/run_oty2_support_region_sar_observation_probe.py` 复用的 `FAN_CENTER_X/FAN_CENTER_Y`。
- 距离向：以响应单元 conservative bbox 中心为 `response_center`，在图像坐标中取 `normalize(response_center - sar_origin)`。
- 方位向：取距离向的局部垂线 `(-range_y, range_x)`，对应既有 `atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y)` 的角度递增方向。
- 图像坐标说明：x 轴向右，y 轴向下；因此距离向不是图像水平轴或垂直轴。
- 几何状态：`configured_fan_center_px_1154_0_1330_6_reused_from_wgv3_5a_r2c`。

## 测量方法

每个冻结 `local_response_unit` 输出 `core_region` 与 `conservative_response_region` 两行。灰度能量使用原始 0-255 灰度；背景估计来自响应框外局部环带，并排除扇形无效区和同帧冻结响应区域。对象测量权重为 `max(intensity - background_estimate, 0)`。一维 `p50/p80/p90_width` 定义为包含对应累计能量比例的最短投影区间宽度。

边界变体族不被合并成车辆；本轮只记录同一局部响应在边界 variant 下的 p80 展宽敏感性。背景反例保持原语义，只作为背景/孤立小峰上下文，不被改写为绝对非车辆真值。

## 对象与分组计数

- 冻结局部响应对象：`250`
- 对象级测量行：`500`（两种 region）
- GT 正向事后控制：`47`
- 登记背景/孤立反例上下文：`129`，其中非 GT 正向：`104`
- 边界删失/边界接触：`142`
- unresolved 控制：`57`

## 可靠性

- 有效能量测量：`250`
- 低能量：`0`
- 像素过少：`0`
- 边界删失标记：`142`
- mask 裁剪标记：`0`
- 背景估计受限：`14`
- 其他无效或失败：`0`

## 正向与背景反例对照

Cliff's delta（克里夫德尔塔，非参数效应量，范围 -1 到 1）和 overlap coefficient（重叠系数，两个经验分布直方图重叠比例，越高表示越难分）仅用于描述，不用于训练或阈值选择。

| metric | valid_a | valid_b | median_a | median_b | median_difference_a_minus_b | cliffs_delta | overlap_coefficient |
| --- | --- | --- | --- | --- | --- | --- | --- |
| range_p80_width | 47 | 104 | 65.580182 | 70.565934 | -4.985752000000005 | 0.04050736497545008 | 0.6204991816693944 |
| azimuth_p80_width | 47 | 104 | 61.408864 | 81.3400195 | -19.931155499999996 | 0.05155482815057283 | 0.6076104746317512 |
| range_to_azimuth_p80_ratio | 47 | 104 | 0.882698 | 0.8438540000000001 | 0.03884399999999988 | 0.07405891980360066 | 0.746317512274959 |
| principal_axis_ratio | 47 | 104 | 1.388032 | 1.3933345 | -0.005302499999999988 | -0.03314238952536825 | 0.7649345335515548 |
| principal_axis_angle_to_range_deg | 47 | 104 | 59.097068 | 60.835224499999995 | -1.7381564999999952 | -0.015957446808510637 | 0.5259819967266776 |
| background_subtracted_energy | 47 | 104 | 66262.0 | 134966.5 | -68704.5 | 0.018412438625204582 | 0.6405482815057284 |

## 边界接触影响

| metric | valid_a | valid_b | median_a | median_b | median_difference_a_minus_b | cliffs_delta | overlap_coefficient |
| --- | --- | --- | --- | --- | --- | --- | --- |
| range_p80_width | 142 | 108 | 72.0628515 | 15.749600000000001 | 56.31325149999999 | 0.5675534689619197 | 0.427621283255086 |
| azimuth_p80_width | 142 | 108 | 83.466935 | 18.323315 | 65.14362 | 0.593244653103808 | 0.44092331768388104 |
| range_to_azimuth_p80_ratio | 142 | 108 | 0.860466 | 0.8210995 | 0.03936649999999997 | 0.04564423578508085 | 0.8011215440792906 |
| principal_axis_ratio | 142 | 108 | 1.3914985 | 1.5704289999999999 | -0.17893049999999988 | -0.20135628586332813 | 0.7886019822639542 |
| principal_axis_angle_to_range_deg | 142 | 108 | 59.544008500000004 | 61.6325645 | -2.088555999999997 | 0.011476264997391758 | 0.7573030777256129 |
| background_subtracted_energy | 142 | 108 | 132011.5 | 5896.5 | 126115.0 | 0.550208659363589 | 0.42840375586854457 |
| energy_centroid_offset_px | 142 | 108 | 6.174436 | 1.378288 | 4.7961480000000005 | 0.48956703182055294 | 0.5020865936358894 |

## GT bbox（bounding box，边界框）宽高对照

Spearman（斯皮尔曼秩相关，衡量单调关系，不要求线性关系）只用于事后对照。GT bbox 是标注范围，不是真实散射支撑或真实车辆尺寸，也不用于选择局部响应。

| metric | paired_sample_count | spearman_rho | interpretation_cn |
| --- | --- | --- | --- |
| range_p80_width_vs_matched_gt_bbox_width_px | 47 | -0.10209128152966257 | 响应距离向 p80 与 GT 图像宽的斯皮尔曼秩相关；GT 框只作事后对照，不代表真实散射支撑。 |
| range_p80_width_vs_matched_gt_bbox_height_px | 47 | 0.05855406454893989 | 响应距离向 p80 与 GT 图像高的斯皮尔曼秩相关；GT 框只作事后对照，不代表真实散射支撑。 |
| azimuth_p80_width_vs_matched_gt_bbox_width_px | 47 | -0.013212497666609696 | 响应方位向 p80 与 GT 图像宽的斯皮尔曼秩相关；GT 框只作事后对照，不代表真实散射支撑。 |
| azimuth_p80_width_vs_matched_gt_bbox_height_px | 47 | 0.14708361939877843 | 响应方位向 p80 与 GT 图像高的斯皮尔曼秩相关；GT 框只作事后对照，不代表真实散射支撑。 |

## H01 状态

`GM019_STATIC_H01` 状态：`PARTIAL_STATIC_SUPPORT`

解释：距离向-方位向展宽已可按对象级计算，且用的是扇形局部坐标而不是图像 x/y 轴。当前分布能提供静态观测量，但背景/孤立反例与边界删失仍造成明显混叠；该状态不等于车辆判别规律成立。

## 支持证据

| metric | sample_count | valid_count | median | q1 | q3 | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| range_p80_width | 47 | 47 | 65.580182 | 19.2051845 | 84.29691 | 5.736653 | 117.960428 |
| azimuth_p80_width | 47 | 47 | 61.408864 | 20.909183 | 100.826191 | 6.662681 | 115.889093 |
| range_to_azimuth_p80_ratio | 47 | 47 | 0.882698 | 0.7020395 | 1.0675045 | 0.35064 | 1.481192 |
| principal_axis_ratio | 47 | 47 | 1.388032 | 1.149301 | 1.6675024999999999 | 1.017918 | 3.207544 |
| principal_axis_angle_to_range_deg | 47 | 47 | 59.097068 | 36.0099185 | 74.407112 | 9.107767 | 89.843145 |
| background_subtracted_energy | 47 | 47 | 66262.0 | 7911.5 | 175949.0 | 2264.0 | 275985.0 |

## 主要反例

| counterexample_id | counterexample_type | response_unit_id | sar_frame | metric_snapshot | why_it_matters_cn | visual_review_relpath |
| --- | --- | --- | --- | --- | --- | --- |
| CE0001 | positive_control_low_directional_ratio | R21B00076 | 77 | range_p80_width=31.4742;azimuth_p80_width=89.7622;range_to_azimuth_p80_ratio=0.3506;principal_axis_ratio=2.822;principal_axis_angle_to_range_deg=79.7457;background_subtracted_energy=66262 | GT 事后正向控制中仍存在方向性比例较低样本，说明静态展宽不能直接升级为车辆规则。 | outputs/oty2_gm_rm019_static_directional_spread_measurement_20260712/visual_review/positive_low_ratio_R21B00076_F77.png |
| CE0002 | positive_control_low_directional_ratio | R21B00001 | 27 | range_p80_width=46.6834;azimuth_p80_width=102.4624;range_to_azimuth_p80_ratio=0.4556;principal_axis_ratio=2.1835;principal_axis_angle_to_range_deg=82.0983;background_subtracted_energy=137506 | GT 事后正向控制中仍存在方向性比例较低样本，说明静态展宽不能直接升级为车辆规则。 |  |
| CE0003 | positive_control_low_directional_ratio | R21B00002 | 27 | range_p80_width=15.3478;azimuth_p80_width=30.1344;range_to_azimuth_p80_ratio=0.5093;principal_axis_ratio=2.4387;principal_axis_angle_to_range_deg=70.2743;background_subtracted_energy=18150 | GT 事后正向控制中仍存在方向性比例较低样本，说明静态展宽不能直接升级为车辆规则。 |  |
| CE0004 | background_counterexample_high_energy_or_ratio | R21B00112 | 216 | range_p80_width=89.6133;azimuth_p80_width=96.6494;range_to_azimuth_p80_ratio=0.9272;principal_axis_ratio=1.2412;principal_axis_angle_to_range_deg=59.561;background_subtracted_energy=267150 | 背景/孤立小峰上下文中也可能出现高能量或强方向性，阻止静态单帧硬判别。 | outputs/oty2_gm_rm019_static_directional_spread_measurement_20260712/visual_review/background_counterexample_R21B00112_F216.png |
| CE0005 | background_counterexample_high_energy_or_ratio | R21B00114 | 216 | range_p80_width=89.6133;azimuth_p80_width=96.6494;range_to_azimuth_p80_ratio=0.9272;principal_axis_ratio=1.2412;principal_axis_angle_to_range_deg=59.561;background_subtracted_energy=267150 | 背景/孤立小峰上下文中也可能出现高能量或强方向性，阻止静态单帧硬判别。 |  |
| CE0006 | background_counterexample_high_energy_or_ratio | R21B00207 | 278 | range_p80_width=99.6745;azimuth_p80_width=106.0158;range_to_azimuth_p80_ratio=0.9402;principal_axis_ratio=1.2068;principal_axis_angle_to_range_deg=50.2134;background_subtracted_energy=253493 | 背景/孤立小峰上下文中也可能出现高能量或强方向性，阻止静态单帧硬判别。 |  |
| CE0007 | boundary_censored_large_centroid_offset | R21B00054 | 39 | range_p80_width=74.8927;azimuth_p80_width=88.6486;range_to_azimuth_p80_ratio=0.8448;principal_axis_ratio=1.3326;principal_axis_angle_to_range_deg=67.5549;background_subtracted_energy=182259 | 边界接触样本的能量质心偏移较大，提示边界删失会改变测量稳定性。 | outputs/oty2_gm_rm019_static_directional_spread_measurement_20260712/visual_review/boundary_contact_R21B00054_F39.png |
| CE0008 | boundary_censored_large_centroid_offset | R21B00143 | 259 | range_p80_width=91.6399;azimuth_p80_width=62.5766;range_to_azimuth_p80_ratio=1.4644;principal_axis_ratio=1.4654;principal_axis_angle_to_range_deg=2.0623;background_subtracted_energy=146247 | 边界接触样本的能量质心偏移较大，提示边界删失会改变测量稳定性。 |  |
| CE0009 | boundary_censored_large_centroid_offset | R21B00248 | 290 | range_p80_width=117.9604;azimuth_p80_width=107.2147;range_to_azimuth_p80_ratio=1.1002;principal_axis_ratio=1.388;principal_axis_angle_to_range_deg=32.493;background_subtracted_energy=155774 | 边界接触样本的能量质心偏移较大，提示边界删失会改变测量稳定性。 |  |

## 送往 GM_RM017 的动态问题

1. 同一响应线程中的 `range_p80_width`、`azimuth_p80_width`、`principal_axis_angle_to_range_deg` 是否随时间连续变化。
2. 这些观测量是否比 GT bbox 宽高更稳定地描述响应支撑。
3. 边界进入和离开时，方向性展宽和能量质心是否连续恢复。
4. 背景弧线、孤立小峰或 background-like 响应是否表现出不同于车辆响应的静态方向或时间稳定性。
5. 相邻同向车辆是否可能产生相似方向性展宽，导致静态单帧混叠。
6. 静态可分性不足时，动态共运动是否能补充解释，而不是重新加权打分。

## 视觉审阅

视觉审阅图位于未提交输出目录：

- `outputs/oty2_gm_rm019_static_directional_spread_measurement_20260712/visual_review/background_counterexample_R21B00112_F216.png`
- `outputs/oty2_gm_rm019_static_directional_spread_measurement_20260712/visual_review/boundary_contact_R21B00054_F39.png`
- `outputs/oty2_gm_rm019_static_directional_spread_measurement_20260712/visual_review/positive_high_ratio_R21B00104_F81.png`
- `outputs/oty2_gm_rm019_static_directional_spread_measurement_20260712/visual_review/positive_low_ratio_R21B00076_F77.png`

## Replay 与完整性

| gate_name | status | detail |
| --- | --- | --- |
| input_hash_local_response_units | PASS | frozen input present and hashed |
| input_hash_boundary_variant_families | PASS | frozen input present and hashed |
| input_hash_response_unit_gt_instance_matrix | PASS | frozen input present and hashed |
| input_hash_boundary_family_gt_instance_matrix | PASS | frozen input present and hashed |
| input_hash_background_counterexamples | PASS | frozen input present and hashed |
| input_hash_vehicle_structure_hypothesis | PASS | frozen input present and hashed |
| input_hash_mask_observation_audit | PASS | frozen input present and hashed |
| input_hash_paired_annotations | PASS | frozen input present and hashed |
| input_hash_atom_graph_nodes | PASS | frozen input present and hashed |
| input_hash_response_box_hypotheses | PASS | frozen input present and hashed |
| all_units_represented | PASS | represented=250 expected=250 |
| measurement_rows_stable | PASS | rows=500 expected=500 |
| positive_group_present | PASS | count=47 |
| background_group_present | PASS | count=129 |
| boundary_group_present | PASS | count=142 |
| statistics_recomputable_from_measurements | PASS | evaluate reads object-level CSV |
| counterexamples_preserved | PASS | rows=9 |
| forbidden_artifact_names_absent | PASS | no selector/ranking/final/revised/runtime artifact output names |

## 输出文件

- `reports/oty2/samples/oty2_gm_rm019_static_directional_spread_measurements_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_directional_spread_group_summary_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_directional_spread_pairwise_controls_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_directional_spread_counterexamples_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_static_directional_spread_gate_integrity_20260712.csv`
- `reports/oty2/oty2_gm_rm019_static_directional_spread_measurement_20260712.md`
