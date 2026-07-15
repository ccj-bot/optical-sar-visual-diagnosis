# OTY2 S1-L Body Support Attribution and GT-Neighborhood Optimality Audit

日期：`2026-07-15`

中文：`S1-L 车体支撑归属与 GT 邻域最优性审计`

## 1. 研究结论

最终阶段状态：

`S1L_BODY_SUPPORT_ATTRIBUTION_NOT_READY`

- S1-D allowed: `false`.
- Automatic annotation allowed: `false`.
- Latent body-support reconstruction run: `false`.

本轮没有进入 S1-D，也没有生成自动标注、最终 SAR 框、candidate bank、selector、ranking、oracle、加权分类器或 GT-IoU 决策。

核心结论分为两层：

1. **车体坐标归属有局部正证据。** GM_RM017:PV002、PV003、PV004 中至少一类车辆尺度横向带状显示响应，在 GT-derived 无符号车体坐标中表现出比 world 和雷达径向/切向 crop 坐标更强的跨帧重复性；固定世界强线背景呈现相反的 world-coordinate 优势。
2. **GT 邻域最优性和车辆特异性失败。** 中心、尺度和轴向扰动没有在 GT 零点周围形成跨指标、跨 Raw/Smoothed、跨车辆一致的稳定盆地。单项最优常落在网格边界，且不同指标偏好互相冲突。更关键的是，PV002 轨迹施加到 PV003 区域后仍复现了与正确车辆线程相当的高一致性。

因此当前只能说某些响应具有 body-coherent 候选性质，不能说明当前 GT 参数比邻域参数更能解释完整 SAR 时间流，也不能说明这些规律属于正确物理车辆而非另一车辆区域、固定背景、裁剪/配准或成像链结构。

## 2. 直接视觉证据

### 2.1 正向但有限的车体坐标证据

- `GM_RM017:PV002`：331-386 帧的横向条带和间歇热点进入 body coordinate 后被统一到车辆长轴方向；crop coordinate 中仍保持弧形/倾斜并混入竖向结构。
- `GM_RM017:PV003`：heldout 复现长轴对齐后的横向带状支持，但固定竖线和背景仍进入规范场。
- `GM_RM017:PV004`：heldout 在弱到强响应阶段部分复现，末端十字样背景表明整体场并不纯。
- `GM_RM011:PV001`：近场扇形弧和大范围世界结构在三坐标系中都占主导，归属不可识别。

三辆 GM_RM017 的线程级初步归属均为 `MIXED`，GM_RM011 为 `UNRESOLVED`；没有任何完整局部场被判为纯 `BODY_COHERENT`。

### 2.2 固定世界背景

固定横线与中心强点在 world coordinate 中保持固定。将 PV002 的移动裁剪/车体轨迹平移到该背景后，同一结构在 crop/body 中漂移、弯曲并离开中心。该 case 为 `WORLD_COHERENT`，说明坐标竞争能识别一种固定背景。

### 2.3 GT 与 Smoothed-GT 失败

`GM_RM017:PV002` frame 310 的 Raw/Smoothed 中心差约 `56.21 px`，Smoothed 规范场落入不同结构。Smoothed-GT 只是一种轨迹反事实，不是更真实的潜在车体状态。

### 2.4 诱人但错误的参数改善

- PV002 Smoothed-body 旋转 `-12°` 可提高部分非相邻相关性并减少外部响应质量，但与 baseline canonical 高占用支撑的重合降至约 `0.158`。逐帧图显示主要变化是规范坐标中的结构重新旋转/对齐，不是物理响应消失。
- PV004 旋转 `+12°` 可提高部分相邻/非相邻相关性，但 baseline canonical 支撑重合降至约 `0.247`，外部质量上升。
- 固定世界背景旋转 `+12°` 同样能提高相邻和非相邻相关性。

这些 case 直接证明：一致性单项改善不能定义相对最佳车体参数。

## 3. 三坐标系与 GT 邻域结果

### 3.1 三坐标系竞争

连续局部背景归一化场的 Smoothed-body 相似视角非相邻相关性为：

- PV002：`0.574`，高于 Smoothed-crop `0.292` 和 world `0.181`；
- PV003：`0.571`，高于 Smoothed-crop `0.300` 和 world `0.192`；
- PV004：`0.429`，高于 Smoothed-crop `0.271` 和 world `0.222`。

固定世界背景则是 world `0.329`，高于 Smoothed-body `0.229` 和 Smoothed-crop `0.094`。

该方向性差异是本轮最可靠的正结论。但 support entropy、观察质心离散、关系距离和方向离散并未全部支持 body coordinate；因此归属仍是 mixed。

### 3.2 中心扰动面

GT 零点没有形成共同盆地：

- PV002 Raw/Smoothed 的 adjacent NCC 最优均位于 `radial=-0.25, tangential=-0.25` 的网格边界；非相邻相关性、低熵和低外部质量分别偏向其他边界位置。
- PV003 的 adjacent NCC 偏向负 radial shift，非相邻相关性和低 area-CV 偏向正 radial/positive tangential，低熵偏向另一位置。
- PV004 的不同指标分别偏向 `-0.25/-0.25`、`-0.125/0`、`+0.25/+0.25` 等位置。

这不是稳定的相对最优盆地，而是多目标冲突和边界偏好。

### 3.3 长短轴尺度面

尺度面同样不存在统一盆地：

- adjacent/nonadjacent 相关性经常偏好 `0.85/0.85` 的缩小窗口；
- support entropy 有时偏好 `1.15/1.15` 或改变长宽比；
- 外部质量和 area-CV 又偏好不同组合；
- Raw/Smoothed 与两辆 heldout 未复现同一尺度修正。

缩小窗口提高相关性可能只是减少背景或只保留一个强部件，不能解释为更真实的车辆支撑。

### 3.4 轴向旋转曲线

- PV002 Raw 更偏 `-6°/-12°`，Smoothed 的 adjacent NCC 在 `0°` 附近最高而 nonadjacent/entropy/outer-mass 偏 `-12°`。
- PV003 Raw 的 nonadjacent 在 `0°` 附近最好，Smoothed 偏 `-12°`；其他指标又偏 `-6°` 或 `+6°`。
- PV004 的部分一致性偏 `+12°`，熵偏 `+6°`，area-CV 偏 `-12°`。

不存在跨 Raw/Smoothed、跨车辆一致的系统轴向修正。

### 3.5 相对最佳参数

本轮没有定义相对最佳参数。没有任何设置同时满足：

- 保持 baseline canonical 支撑解释；
- 提高 body coherence；
- 降低 world/background 混入；
- 保持低边界缺失；
- 在 Raw/Smoothed 中一致；
- 在两辆 heldout 中复现；
- 不被困难反事实复现。

因此没有生成“GT 与相对最佳框”的逐帧并列图；取而代之的是 baseline 与诱人但失败的参数扰动逐帧对比，明确展示为什么不能选 winner。

## 4. 反事实

### 4.1 固定世界强线背景

该背景在 world coordinate 中稳定，并且中心、尺度、旋转扰动也能提高某些一致性指标。参数曲面本身不具有车辆特异性。

### 4.2 PV002 轨迹作用于 PV003 区域

交换反事实 baseline 的 adjacent/nonadjacent 相关性约为 `0.842/0.557`；中心边界扰动可达到约 `0.851/0.592`，`0.85/0.85` 缩放可达到约 `0.858/0.584`。这一量级不低于正确车辆线程。

结论：当前一致性规律可由另一辆同场景车辆区域复现，不能证明正确物理车辆身份归属。

### 4.3 PV003 轨迹作用于 PV002 区域

反向交换 adjacent NCC 可达到约 `0.875`。非相邻相似视角配对为空，暴露出该反事实的可识别性限制；但高 adjacent coherence 已足以阻止身份特异性结论。

### 4.4 未继续执行的反事实

协议已经设计邻近无车背景、固定世界区域、A/B 轨迹交换、空间平移、时间打乱、时间反转和能量/复杂度匹配强背景。由于 GT 邻域稳定盆地这一必要条件已失败，并且第一组轨迹交换已经复现主要规律，本轮触发 stop condition，没有继续扩大为完整反事实批量管线。

这些未执行项仍是未来重新开启该方向时的必需债务；它们不是本轮 READY 证据。

## 5. 失败案例

1. **Smoothed-GT 端点失配**：PV002 frame 310 中心差约 56.21 px。
2. **中心面漂向网格边界**：多个相关性指标在 `-0.25/-0.25` 或其他边界达到最大。
3. **尺度缩小假改善**：`0.85/0.85` 常提高相关性，但可能只保留强部件或减少背景，不等于合理车体包络。
4. **旋转假改善**：`±12°` 可改善某些指标，同时破坏 baseline canonical 支撑对齐；背景也能获得相同改善。
5. **轨迹交换复现**：错误物理车辆区域仍有高一致性。
6. **跨场景不可识别**：GM_RM011 被近场弧线和大范围世界结构控制。

## 6. GT 信息债务

| 当前研究输入 | 当前用途 | 未来非 GT 替代来源 | 状态 |
| --- | --- | --- | --- |
| GT 中心 | 规范场平移和扰动零点 | 光学方位映射与时序状态 | `GT_DISCOVERY_ONLY; FUTURE_REPLACEABLE; DEPLOYMENT_SOURCE_NOT_READY` |
| Smoothed-GT | 裁剪/轨迹反事实 | 光学完整车辆线程 | 同上；frame 310 另标 `GT_PRECISION_DEPENDENT` |
| GT 长宽 | 线程参考尺度和尺度扰动零点 | 车型先验或光学尺寸估计 | 同上 |
| GT 旋转角 | 180° 无符号长轴和轴向扰动零点 | 光学姿态、运动轨迹或轴向估计 | 同上；无 front/rear 语义 |
| GT crop | 局部研究区域 | 光学约束的潜在车辆支撑 | 同上 |
| GT identity | 物理车辆研究单位 | 光学全局物理车辆身份 | 同上 |

当前任何机制都没有可用的非 GT 部署来源，且参数结论对 GT 精度和轨迹归属高度敏感。

## 7. 阶段状态

最终状态：`S1L_BODY_SUPPORT_ATTRIBUTION_NOT_READY`

直接回答本轮十个问题：

1. **稳定局部结构属于什么？** GM_RM017 的一类横向带状结构部分 body-coherent；完整局部场是 mixed；固定强线是 world-coherent；GM_RM011 unresolved。
2. **车辆与背景是否有不同坐标规律？** 对固定世界强线有；但轨迹交换可复现车辆一致性量级，规律不具车辆身份特异性。
3. **GT 是否位于稳定相对最优盆地？** 否。
4. **是否存在系统性平移、尺度或轴向修正？** 否；各指标、Raw/Smoothed 和 heldout 方向不一致。
5. **相对最优性是否超越能量？** 本轮没有用总能量、平均能量、最大值、占用率、组件数、GT IoU 或加权分数决定参数；但非能量一致性指标仍不足以建立相对最优性。
6. **能否重建潜在车体支撑？** 当前不能。GT 邻域和身份归属失败后，继续支撑重建会把不可靠参数固化，因此按 stop condition 未运行。
7. **heldout 复现了什么？** 只复现 body alignment 能提高部分重复性的弱规律；没有复现统一参数修正，且轨迹交换也能复现。
8. **哪些结论依赖 GT？** 中心、尺度、轴、crop 和身份全部依赖 GT；未来替代来源均未就绪。
9. **是否具备进入 S1-D 的科研条件？** 不具备。
10. **具体缺失什么？** 缺失非 GT 可靠车体轴/尺度/中心来源、GT 邻域稳定盆地、不能被轨迹交换复现的车辆身份归属、更完整困难背景反事实、明确成像增益/灰度映射/重采样链，以及跨场景可识别性。

## 8. 代码与产物

新增 formal products：

- `docs/OTY2_S1L_BODY_SUPPORT_ATTRIBUTION_AND_GT_NEIGHBORHOOD_OPTIMALITY_AUDIT_PROTOCOL.md`
- `reports/oty2/oty2_s1l_body_support_attribution_logic_audit_20260715.md`
- `reports/oty2/oty2_s1l_body_support_minimum_coordinate_casebook_review_20260715.md`
- `reports/oty2/oty2_s1l_body_support_attribution_and_gt_neighborhood_optimality_20260715.md`
- `tools/diagnostics/run_oty2_s1l_body_support_coordinate_casebook.py`
- `tools/diagnostics/run_oty2_s1l_gt_neighborhood_perturbation_pilot.py`
- `manifests/oty2/oty2_s1l_body_support_coordinate_frames.csv`
- `manifests/oty2/oty2_s1l_body_support_coordinate_competition.csv`
- `manifests/oty2/oty2_s1l_body_support_casebook_manifest.csv`
- `manifests/oty2/oty2_s1l_body_support_case_reviews.csv`
- `manifests/oty2/oty2_s1l_body_support_gt_neighborhood_surfaces.csv`
- `manifests/oty2/oty2_s1l_body_support_gt_neighborhood_casebook_manifest.csv`
- `manifests/oty2/oty2_s1l_body_support_gt_neighborhood_reviews.csv`

Temporary arrays and PNGs remain outside Git under:

`D:/profile/research/workspace/output/oty2_s1l_body_support_attribution_20260715`

Formal counts are descriptive only: 291 coordinate-frame rows, 25 coordinate-competition rows, 495 perturbation rows, 15 minimum-casebook artifacts and 30 perturbation artifacts. These counts are not the research conclusion.

## 9. Git 状态

冻结 S0、S0-M、S0-MV 和 S1-L 产物未覆盖。临时 PNG、NPZ、缓存、视频、压缩包、修改 GT、最终标注和 selector/ranking 产物均不进入 Git。

最终 commit 和 remote divergence 只在新 validator、旧阶段 validator、固定输入重放和 `git diff --check` 全部通过后记录。
