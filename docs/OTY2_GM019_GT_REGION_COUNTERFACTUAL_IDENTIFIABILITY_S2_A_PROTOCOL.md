# OTY2 GM_RM019 S2-A GT 区域反事实物理可辨识性协议

日期：`20260712`

本协议定义 `GM_RM019 S2-A：GT 区域、边界与旋转反事实物理可辨识性评价`。OTY2（Optical Timeline Y2，光学时序辅助阶段二）、SAR（Synthetic Aperture Radar，合成孔径雷达）、GT（Ground Truth，真值）在本轮只用于事后物理机制评价。

## 任务边界

S2-A 只评价 GT response region（GT 响应区域）、四条局部边界和 GT 旋转在预注册邻近反事实中的物理可辨识性。它不拟合 GT、不修正 GT、不生成最终框、不构造 selector（选择器）、不做 ranking（排序）、不输出 best-box、不恢复车辆真实 yaw（航向角）、不修改 GM_RM017，也不训练模型。

允许的总状态只有：

```text
S2_A_REGION_IDENTIFIABILITY_READY
S2_A_PARTIAL
S2_A_BLOCKED
```

## 继承的主要纠偏

1. `40 m` 和 `0.03 m/px` 是项目确认的局部评价条件，本轮不再重复审计。
2. GT 是事后 SAR 可见响应标注，不自动等于完整车辆物理外轮廓。
3. 不能直接用物理变量拟合 GT，否则会形成循环论证。
4. `final_heading_deg` 是 `final_w` 存储轴，不是车辆 yaw（航向角）。
5. 单个局部响应不等于完整车辆，车辆尺度只能作为软投影包络。
6. 多连通分量不自动意味着没有轴向结构。
7. 反事实必须真实读取 SAR 灰度，不能使用人工变化公式。
8. 冻结的 250 个 response unit（响应单元）保留为来源视图，S1-R1（阶段一修订一）的 independent geometry（独立几何）基线为 215 个。

## 固定标定与 GT 轴语义

以下量作为项目确认条件直接沿用：

```text
calibration_status = PROJECT_CONFIRMED
max_range_m = 40.0
radial_grid_spacing_m_per_px = 0.03
sar_fan_center = (1154.0, 1330.6)
```

本轮不得输出 `ABSOLUTE_SCALE_UNRESOLVED`。

`final_heading_deg` 的固定语义为：GT 旋转框 `final_w` 存储轴在 SAR 图像坐标中的方向。GM_RM019 当前 paired annotation（配对标注）源表只含轴对齐 `sar_bbox` 字段，没有独立旋转 heading（方向角）字段，因此 S2-A 对该来源记录：

```text
gt_width_axis_image_deg = 0
gt_long_axis_image_deg = gt_width_axis_image_deg                  if final_w >= final_h
gt_long_axis_image_deg = gt_width_axis_image_deg + 90 degrees     if final_h > final_w
gt_long_axis_image_deg mod 180 degrees
```

GT 长轴仍只是 GT 响应框视觉长轴，不是车辆真实长轴、车头方向、车辆真实 yaw，也不是 SAR 灰度响应主轴。

禁止输出以下车辆航向结论字段或状态：

```text
vehicle_yaw_deg
true_yaw_deg
confirmed_heading_deg
GT_YAW_CORRECT
GT_YAW_WRONG
```

## 两阶段冻结

### S2-A Plan：评价计划冻结

Plan 阶段允许读取 paired annotations（配对标注）、response unit-GT instance matrix（响应单元与 GT 实例矩阵）、mask observation audit（掩膜观测审计）、GT 几何表、local response geometry（局部响应几何）和 S1-R1 independent geometry map（独立几何映射）。Plan 阶段只冻结主评价样本、pairing-review（配对复核）样本、GT 几何语义、全部反事实多边形、matched background（匹配背景）多边形和 plan seal（评价计划封印）。

Plan 阶段不得读取 SAR 灰度强度、S1-R1 measurement outcomes（测量结果）、S1-R1 counterfactual measurement（反事实测量）结果，也不得根据物理结果选择“最好”或“最差”的 GT 或背景对照。

### S2-A Evaluate：真实 SAR 评价

Evaluate 阶段必须先验证 plan seal，再按冻结计划读取 SAR 灰度并测量全部冻结区域。Evaluate 阶段不得根据中间结果新增、删除或移动任何对照区域。

## 评价池

S2-A 必须分开记录：

```text
PRIMARY_EXACT_LINK
PAIRING_REVIEW_ONLY
DUPLICATE_RESPONSE_VIEW
UNLINKED_CONTROL
```

主科学结论只使用 `PRIMARY_EXACT_LINK`，并以 GT-instance（GT 实例）级和 physical-vehicle（物理车辆）级为主。measurement-row（测量行）和 counterfactual-row（反事实行）不得被当作独立大样本。

## 预注册反事实

每个主 GT 实例冻结以下区域：

- `gt_original`：原始 GT 响应区域。
- `center_shift`：沿局部距离向和方位向平移 `±0.15 m`、`±0.30 m`、`±0.45 m`。
- `diagonal_center_shift`：固定对角平移 `(±0.15 m, ±0.15 m)` 和 `(±0.30 m, ±0.30 m)`。
- `single_boundary_shift`：`range_near`、`range_far`、`azimuth_left`、`azimuth_right` 分别移动 `±0.15 m`、`±0.30 m`。
- `scale_resize`：距离向和方位向尺度分别变化 `±0.15 m`、`±0.30 m`。
- `local_region_rotation`：旋转 `-30`、`-15`、`-10`、`-5`、`0`、`5`、`10`、`15`、`30`、`90` 度。
- `matched_background`：按固定偏移顺序构造同帧几何背景对照，不按灰度亮度选择。

## 三种轴向表示

每个测量区域必须并行记录：

```text
GLOBAL_ENERGY_AXIS
DOMINANT_COMPONENT_AXIS
SIGNIFICANT_COMPONENT_LAYOUT_AXIS
```

显著分量布局轴的固定消融策略为：

```text
DOMINANT_ONLY
TOP_COMPONENTS_TO_80_PERCENT_ENERGY
COMPONENT_ENERGY_FRACTION_GE_5_PERCENT
```

多连通分量不自动被判为无轴；轴向状态只是物理观测解释，不能解释为车辆 yaw。

## 分因素评价

S2-A 只进行分因素比较：

- 能量支撑；
- 内外能量密度对比；
- 连通分量结构；
- 阈值身份持续性；
- 车辆投影包络兼容性；
- 旋转反事实物理响应。

不得构造或输出：

```text
total_score
weighted_score
best_region_score
rank
selector_probability
```

## 区域、边界、旋转、MASK 与背景状态

每个 GT 实例必须输出一个区域状态：

```text
GT_REGION_PHYSICALLY_DISTINGUISHABLE
GT_REGION_INTERVAL_IDENTIFIABLE
GT_REGION_NOT_STATICALLY_DISTINGUISHABLE
GT_REGION_PHYSICAL_CONFLICT
GT_REGION_PAIRING_UNRESOLVED
```

`near`、`far`、`left`、`right` 四条边分别输出：

```text
EDGE_IDENTIFIABLE
EDGE_INTERVAL_ONLY
EDGE_MASK_CENSORED
EDGE_NOT_IDENTIFIABLE
EDGE_PHYSICAL_CONFLICT
```

旋转输出：

```text
ROTATION_ORIENTATION_IDENTIFIABLE
ROTATION_INTERVAL_ONLY
ROTATION_90_DEG_SWAP_AMBIGUOUS
ROTATION_NOT_IDENTIFIABLE
ROTATION_PARTIAL_SUPPORT_CENSORED
ROTATION_PHYSICAL_CONFLICT
```

MASK（掩膜）只作为分层变量、删失上下文和失败解释。只有源表明确提供 `bottom_near_range_mask` 时，才允许将其用于近距边删失解释；其他边界方向不得自行猜测。

背景敏感性至少区分：

```text
BASE_REGION_FROZEN_BACKGROUND
PERTURBED_LOCAL_RING_BACKGROUND
```

若结论随背景模式反转或强烈改变，该 GT 不得升级为强区域或强边界结论。

## Readiness

S2-A 必须分别报告：

```text
S2_REGION_COUNTERFACTUAL_READINESS
S2_EDGE_COUNTERFACTUAL_READINESS
S2_ROTATION_COUNTERFACTUAL_READINESS
S2_RESPONSE_AXIS_VALIDATION_READINESS
S2_VEHICLE_YAW_VALIDATION_READINESS
```

`S2_VEHICLE_YAW_VALIDATION_READINESS` 固定为 `NOT_READY`。本轮不得用单一 `S2_READINESS=READY` 掩盖不同层级。
