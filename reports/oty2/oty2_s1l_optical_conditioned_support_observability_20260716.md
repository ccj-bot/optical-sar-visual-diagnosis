# OTY2 S1-L 结论语义纠偏与光学条件支撑可观测性分解

日期：`2026-07-16`

工作名称：`S1-L Semantic Correction and GT-Discovery Proxy Audit for the Optical-Conditioned Support Question`

冻结起始 HEAD：`75eed68a19c94428c27d8a217d3dab36c56f20d6`

## 1. 总结论

本轮完成了 S1-L 的语义纠偏、等支持坐标增量、轴向安慰剂、双归一化、完整背景反事实、Raw/Smoothed 独立配对、LOPO/LOFO 和逐参数可观测性闭环。结果没有授权进入 S1-D，也没有授权潜在支撑重建或自动标注。

最重要的结论不是“车辆结构不存在”，而是：

> 在 GT 给定中心、无符号轴与参考尺度时，中心跟随和旋转各向异性窗口可以提高部分处理后 SAR 显示场的一致性；但纯车体轴增量、车辆类别相对背景的双结构族优势、任何中心/尺度/轴向物理约束，以及真实光学条件输入下的支撑就绪性均未建立。

轨迹互换的语义已固定为 `IDENTITY_NEGATIVE_CLASS_POSITIVE`。它只能否定 SAR-only 物理身份特异性，不能作为车辆类别阴性背景。光学完整时序仍负责物理车辆身份、轨迹和粗方位；SAR 只允许在这些条件下提供保守局部支撑证据。

本轮没有运行真实 optical-derived centre、axis 或 scale。当前正向结果只属于 **GT-conditioned registration evidence**，不是独立检测或部署证据。

固定边界：

- `UNIQUE_BOX_RECOVERY=NOT_EVALUATED_NOT_AUTHORIZED`
- `latent_support_reconstruction_allowed=false`
- `s1d_allowed=false`
- `automatic_annotation_allowed=false`

## 2. 正式实验契约

### 2.1 研究单位与反事实

正式 registry 共 21 个单位：

- 3 个 `TRUE_VEHICLE_POSITIVE`；
- 2 个 `IDENTITY_NEGATIVE_CLASS_POSITIVE`；
- 4 个 `VEHICLE_CLASS_NEGATIVE`；
- 12 个 `TEMPORAL_NEGATIVE`。

四个背景均受以下范围限制：

`BACKGROUND_POSITIONS_AND_SUPPORT_GEOMETRY_FROZEN_FROM_PV002_ONLY`

它们是 4 个命名控制、3 个 baseline equal-support 空间簇、2 个完整一维参数包络严格簇。精确契约为：

`BACKGROUND_CLUSTER_SCOPE=BASELINE_EQUAL_SUPPORT_3_SPATIAL_CLUSTERS;STRICT_ONE_DIM_PARAMETER_ENVELOPE_2_CLUSTERS;NOT_STATISTICAL_INDEPENDENCE`

BG0010 与 BG0011 同属第一个 baseline 空间簇；BG0011 只保留为同簇 strong-line role diagnostic。B3 是第二簇。FX88 是第三簇的 fixed anisotropic-speckle control，明确不是 strong-line control。以上簇不构成统计独立样本、跨车辆、跨时间或跨场景泛化。

### 2.2 等支持表示

四种表示均使用相同窗口尺寸、`256×128` 网格、有效 Mask、灰度输入和基于 `W-1/H-1` 的有效源像素密度：

1. `WORLD_FIXED`
2. `CENTER_TRACKED_CARTESIAN`
3. `CENTER_TRACKED_RADIAL`
4. `CENTER_TRACKED_BODY`

body 与 radial 的旋转矩形会采样不同源像素，因此其归因契约固定为：

`BODY_ORIENTED_WINDOW_ATTRIBUTION=AXIS_ORIENTATION_PLUS_ROTATED_ANISOTROPIC_SUPPORT_FOOTPRINT_NOT_PURE_BODY_AXIS`

即它是 GT-conditioned body-oriented anisotropic-window increment，不是纯 physical body-axis attribution。

### 2.3 配对与敏感性

Raw-GT 与 Smoothed-GT 为所有单位分别建立 source-positive pair set，两套配对不是独立样本。冻结引用为：

`PAIR_MEMBERSHIP_REFERENCE=SOURCE_POSITIVE|CENTER_TRACKED_BODY|GT_DERIVED_UNSIGNED_BODY|FIXED_REFERENCE|FINITE_COMMON_VALID`

反事实不得重新择对，只允许按帧交集投影：

`PAIR_PROJECTION_RULE=SOURCE_POSITIVE_PAIR_SET_FRAME_INTERSECTION_NO_RESELECTION`

pair 是共享帧上的重复对比，不是样本量。正式输出同时报告 leave-one-pair-out 与 leave-one-frame-out，并记录 unique-frame count、最大 frame degree 和 pair graph components。

### 2.4 双归一化与结构代理

所有表示、轴规则和参数网格均分别运行：

- `FIXED_REFERENCE`
- `CANDIDATE_LOCAL_REESTIMATED`

两路结果不平均、不加权。方向冲突时只能标记 `NORMALIZATION_DEPENDENT`。

连续灰度场之外只使用两个结构族：structure-tensor local orientation proxy 与 Canny thin-edge connectivity proxy。后者的正式名称是：

`CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON`

Canny 固定为 low/high `40/100`、aperture `3`、L2 gradient `true`；无效区域使用 Telea radius `3`，结构有效 Mask 腐蚀 `6 px`。这些量属于归一化 8-bit display domain，不是原始幅度、散射中心、脊线、形态骨架或物理车体拓扑。

### 2.5 时序与参数契约

`TEMPORAL_REVERSE` 是反序图像与原时刻 anchor 的错误对应，只属于 `CORRESPONDENCE_ONLY`。方向不敏感指标必须写 `NOT_APPLICABLE_TO_TIME_REVERSAL`；本轮没有 arrow-of-time 证据。

参数契约为：

`PARAMETER_OBSERVABILITY_CONTRACT=GRID_NONDOMINANCE_DIAGNOSTIC_ONLY;ALL_FORMAL_OBSERVABILITY_STATES_NOT_IDENTIFIABLE;NO_PHYSICAL_BOUNDS`

长短尺度曲线固定解释为 `WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED`。五点网格和 Pareto 非支配值只描述诊断图样，不是物理可行值、估计值、置信区间、单侧界或唯一解。

## 3. 运行完整性

配置哈希：`a62d5f6bdb3c902f1651ee03e4bd2c30e5403fdb4ee53a03e0ee3899402e9113`

正式数据规模为：

| 产物 | 行数 |
| --- | ---: |
| research units | 21 |
| sampling/normalization audit | 24,848 |
| representation metrics | 336 |
| pair incremental metrics | 24,912 |
| pair and frame sensitivity | 55,296 |
| parameter metric profiles | 14,700 |
| parameter observability | 640 |
| visual artifacts | 20 |

24,848 条归一化记录全部 `PASS`，336 条表示记录全部有效。pair preflight 的 42 个 unit-anchor scope 中，pair count bucket 为 `0:12 / 1:7 / 2-4:8 / >4:15`；source/projected pair-set hash 数为 `6/10`。eligible source pair 为 184，对端点可靠性排除 21 对。

20 张 PNG 已按 manifest 逐图直接审阅，覆盖 14 个 review entity，包括 3 个正车辆、2 个身份互换、4 个背景、4 个 PV002 时序反事实和 `GLOBAL` pair audit。

## 4. 数值与视觉结果

### 4.1 中心跟随成立，但不是纯 body-axis 结论

在 5 个可用 vehicle-anchor scope × 双归一化形成的 10 个 FIELD_NCC 范围中：

- `CENTER_TRACKED_CARTESIAN - WORLD_FIXED` 为正 `10/10`，中位增量 `+0.406685`；
- `CENTER_TRACKED_BODY - CENTER_TRACKED_RADIAL` 为正 `10/10`，中位增量 `+0.104312`；
- `CENTER_TRACKED_BODY - CENTER_TRACKED_CARTESIAN` 仅正 `4/10`，中位增量 `-0.026271`。

Raw 下 body-vs-Cartesian 的 6 个双归一化范围全部为负；Smoothed 下只有 4 个很弱的正增量。body-vs-radial 的 orientation 方向是 `4 positive / 6 negative`，thin-edge Jaccard 是 `6 positive / 4 negative`，并没有两个结构族共同稳定支持。

视觉上，PV002/PV003/PV004 的 Cartesian 与 body 均能形成紧致横向响应带，radial 表示更偏弧形；但 global fixed、trajectory tangent、frame-shuffled 和 time-shifted axis 也能保留相似均值场。因此最可靠的解释是中心跟随加上旋转各向异性窗口的 GT 条件登记效应，而不是独立车体轴归属。

### 4.2 轴向安慰剂多数门失败

GT 规则在 120 个 vehicle-anchor-normalization-submetric 范围中仅 49 个优于多数安慰剂，71 个失败。对 `GT_AXIS_PLUS_90`，FIELD_NCC、方向角与方向一致性均只有 `1 positive / 9 negative`。

直接视觉中，`GT_DERIVED_UNSIGNED_BODY`、`GLOBAL_FIXED_AXIS`、`TRAJECTORY_TANGENT_AXIS`、shuffle 与 time-shift 的主横向结构常近似；`GT_AXIS_PLUS_90` 则产生显著竖直强线。该对照说明窗口旋转会强烈改变图像，但不能证明 GT 轴是唯一或稳定优于其他可解释轴规则。

### 4.3 车辆类别相对背景没有形成稳健双结构族优势

Raw nonadjacent 证据中：

- FIELD_NCC 在 fixed/local 两路均满足三辆正车辆全部高于四个命名背景和三个 baseline 簇；
- thin-edge Jaccard 只在 `FIXED_REFERENCE` 满足完整分离；
- local thin-edge Jaccard 与两路 orientation agreement 均不满足完整分离。

Smoothed 下四个背景均无 eligible nonadjacent pair，无法形成对称的 Raw/Smoothed 类别证据。相邻帧结果又被部分背景复现，尤其 orientation agreement 在背景中同样很高。

视觉复核显示：BG0010 有持续弧/线，BG0011 有强线和热点，B3 有硬散射与弧形响应且局部归一化显著放大，FX88 是弱各向异性斑点。它们证明 display-domain 的线性、弧形、紧致散射和方向连续性都可能出现在车辆类别阴性区域。当前结果不足以支持 `VEHICLE_CLASS_SUPPORT_OVER_BACKGROUND`。

### 4.4 SAR-only 物理身份特异性未建立

`PV002 trajectory around PV003` 的 Raw nonadjacent FIELD_NCC 为 `0.542220`，高于源 PV002 的 `0.343522`；固定与局部重估两路的 adjacent field/orientation 也多次复现或超过源线程。全部 48 个可比 identity-swap metric row 中有 14 个复现或超过源值。

反向互换缺少 nonadjacent pair，因此双向身份否证不对称；但两张互换均值场都直接显示真实车辆样紧致响应。这已经足以阻止 SAR-only PV002/PV003 身份特异性结论，同时不否定车辆类别语义。

### 4.5 时序对应关系只有混合证据

time shuffle 明显削弱 PV002 紧致结构，time reverse 主要保留世界/弧线背景；但 `TRAJECTORY_TIME_SHIFT_P8` 和 `CENTER_PHASE_SHIFT_P8` 仍保留接近正车辆的紧致 body 显示场，Raw nonadjacent FIELD_NCC 分别为 `0.522335` 和 `0.399062`，并不低于源线程的全部显示规律。

因此当前证据只说明某些错误对应会破坏场，而另一些约 `0.69-0.73` 个参考短轴的 +8 帧错配仍能保留结构。它不能支持完整时间关系特异性，更不能支持时间方向。

### 4.6 pair 图存在明显帧杠杆

在 2,784 个可评 LOPO/LOFO metric group 中：

- LOPO direction-unstable：`600/2784 = 21.6%`；
- LOFO direction-unstable：`1122/2784 = 40.3%`。

LOFO 不稳定率显著更高，说明结果受少数共享帧杠杆影响。pair count 即使大于 4 也只能称 shared-frame repeated evidence，不能包装成稳定泛化或独立样本量。

### 4.7 所有参数均不可识别

640 条 observability row 全部为 `NOT_IDENTIFIABLE`，所有 reported physical bound 留空。

- `CENTER_RADIAL`：Raw 共同网格模式为 `+0.125`，Smoothed 为 `-0.125`，方向翻转；
- `CENTER_TANGENTIAL`：Raw 为空，Smoothed 只有触边 `-0.25`；
- `LONG_SCALE`：Raw 为多分量，Smoothed 为覆盖 `0.85-1.075` 的触边宽集合；
- `SHORT_SCALE`：Raw 为 `0.85/1.15` 两端多解，Smoothed 为全网格；
- `AXIS_UNSIGNED`：Raw 为空，Smoothed 只有 `-6°` singleton 诊断图样。

这些模式不能升级为物理中心、尺度或轴向约束。

## 5. 十项分解结论

| conclusion_id | status | 解释 |
| --- | --- | --- |
| `GT_CONDITIONED_BODY_ALIGNMENT` | `PARTIAL_GT_CONDITIONED_ONLY` | 中心跟随和 body-vs-radial FIELD_NCC 有一致正增量，但 GT 循环性和支持足迹混杂仍在。 |
| `BODY_AXIS_INCREMENTAL_VALUE` | `PARTIAL` | 有局部指标支持，但多数轴向安慰剂门失败，纯轴增量未识别。 |
| `VEHICLE_CLASS_SUPPORT_OVER_BACKGROUND` | `NOT_SUPPORTED` | 只有部分 Raw metric 分离；不能跨双归一化、双结构族和 Smoothed 背景配对成立。 |
| `SAR_ONLY_PHYSICAL_IDENTITY_SPECIFICITY` | `NOT_READY` | 真实错误车辆区域可复现关键显示规律；物理身份应继续由光学时序负责。 |
| `CENTER_RADIAL_OBSERVABILITY` | `NOT_IDENTIFIABLE` | Raw/Smoothed 诊断值翻转，无物理区间。 |
| `CENTER_TANGENTIAL_OBSERVABILITY` | `NOT_IDENTIFIABLE` | 共同模式为空或触边，无单侧物理界。 |
| `LONG_SCALE_OBSERVABILITY` | `NOT_IDENTIFIABLE` | 宽、多分量且与重采样耦合。 |
| `SHORT_SCALE_OBSERVABILITY` | `NOT_IDENTIFIABLE` | 多解或全网格，未收缩。 |
| `AXIS_OBSERVABILITY` | `NOT_IDENTIFIABLE` | 安慰剂多数门失败，网格 pattern 不是轴估计。 |
| `OPTICAL_CONDITIONED_SUPPORT_READINESS` | `NOT_READY` | 真实 optical input 未执行；类别证据与参数约束均未达到继续门。 |

## 6. 继续门审查

潜在支撑重建的六项继续条件中，前五项均未满足：

1. GT body-oriented rule 没有稳定优于多数轴向安慰剂；
2. 正车辆没有在两个独立结构族、双归一化和背景簇上同时占优；
3. 类别与部分拓扑结果存在归一化依赖；
4. PV003/PV004 只是同场景其他车辆固定规则重放，尚无独立数据；
5. 中心与尺度均未获得物理区间或单侧界；
6. 本轮确实未使用 selector、ranking、GT IoU、训练模型或加权/综合分数，但这一项单独成立不能授权继续。

因此本轮正式停止在 S1-L 语义纠偏与观测性审计，不进入潜在车体支撑重建。

## 7. 对整体项目的推进意义与下一步

本轮把旧的“body-support 失败/成功”单一判断拆成了身份、类别、GT 条件登记、纯轴增量、五个参数和真实光学条件就绪性，避免了三个关键语义错误：

1. 不再用另一辆真实车辆否定车辆类别；
2. 不再把不同视野或旋转窗口的 NCC 差异全部解释为坐标归属；
3. 不再把五点 Pareto 图样写成物理可观测区间。

对主线最有价值的下一步仍属于 S1-L，而不是 S1-D：用真实 optical-derived centre、unsigned axis 与 scale range 替换 GT proxy，在完全相同的等支持、双归一化、source-pair freeze、背景簇和可视化契约下做只读重放。若真实光学输入仍不能让两个结构族跨背景稳定分离，或仍不能提供至少一个物理中心/尺度区间，则应停止从当前 8-bit display-domain 结构独立恢复支撑，转向更强光学先验下的保守 SAR 证据，或获取原始幅度、complex/IQ/ADC、固定灰度映射和更可靠姿态数据。

这一路线保持主线不变：光学给搜索壳层和身份先验，SAR 只在壳层内提供精定位所需的条件证据；shell-only 评估、GUI seed 和最终 SAR prediction 不混用。
