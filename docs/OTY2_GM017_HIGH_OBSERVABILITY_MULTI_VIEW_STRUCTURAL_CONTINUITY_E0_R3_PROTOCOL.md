# OTY2 GM_RM017 High-Observability Multi-View Structural Continuity E0-R3 Protocol

Updated: 2026-07-12

本协议定义 `WGV3.6B-E0-R3 GM_RM017 高可观测同车多视角结构连续性与动态区间收缩审计`。OTY2
（Optical Timeline Y2，光学时序辅助阶段二）在这里仍然只是提供同车、时间和几何上下文；SAR
（Synthetic Aperture Radar，合成孔径雷达）灰度响应只在 Generate 阶段打开，用于结构量测。

本轮不是 detector（检测器）、selector（选择器）、ranking（排序器）、final box（最终框）、GT
（Ground Truth，人工参考标注）修改、训练、真实车辆 yaw（偏航角）恢复、固定散射点身份跟踪、跨场景泛化证明，也不是
GM_RM019 静态线修改。

## Frozen Boundary

- Worktree branch: `feature/oty2-gm017-physical-factor-discovery`
- Frozen start commit: `7a9d9cba9f38447e10c917227a789f4160569026`
- Calibration: SAR `<=360`
- Guard: SAR `361-370`
- Same-scene posthoc diagnosis: SAR `371-394`
- Radar fan center: `(1154.0, 1330.6)`
- Radial grid spacing: `0.03 m/px`

绝对距离只能从固定 SAR 扇形中心计算。禁止把 GT 左上角、局部裁剪原点、第一帧、初始中心或逐帧自适应原点当作
`absolute_range_from_radar_m` 原点。

## E0-R2 And D1-R1 Carry-Forward

E0-R2 仍为 `NOT_READY`：

- `VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED=NOT_READY`
- `E0_R2_PHYSICAL_MECHANISM_SUPPORTED=NOT_READY`
- `E0_R2_READY_FOR_CROSS_VEHICLE_VALIDATION=NOT_READY`

E0-R2 可继承的是相对观测角 timeline、body-axis proxy（车体轴代理）、同场景反事实意识和标定/guard/diagnosis
划分。E0-R2 不再继承为主线对象的是 `response_index`、`total_response_score`、`weighted_response_score`、
`multi_aspect_score` 或任何加权综合分。

D1-R1 的 `D1_R1_SEMANTIC_INTEGRITY_READY=PASS` 只说明递归状态语义可审计；`D1_R1_PHYSICAL_DYNAMIC_MEMBERSHIP_READY=NOT_READY`
仍然有效。递归状态误差下降、跟踪稳定或相关性较高不能直接解释为车辆物理机制成立。

## Stage Separation

### Plan

Plan 阶段只允许读取：

- GT 几何、物理同车身份和帧号；
- MASK（有效观测掩膜）元数据；
- 光学/轨迹中心与 body-axis proxy 几何；
- E0-R2 协议定义和相对观测角 timeline。

Plan 阶段禁止读取：

- SAR 灰度强度；
- E0-R2 response descriptors；
- E0-R2 `response_index`；
- E0-R2 Gate 结论；
- 任何按 SAR 响应结果挑选锚点段或配对的输入。

Plan 必须冻结 A/B/C 类动态段、split 角色、角度代理、结构字段、配对规则、静态扰动区间、背景/强散射体/身份错接对照和
plan seal。

### Generate

Generate 阶段在验证 plan seal 后读取真实 SAR 灰度，输出逐帧结构化车辆响应场：

- 整体响应支撑、距离向/方位向/body-long/body-short 宽度；
- global energy axis、dominant component axis、component layout axis（三类 SAR 响应轴）；
- 高能质心、峰值位置和 top-energy quantile（高能分位）质心在 body-long/body-short 坐标中的滑动；
- near/far 能量重分配；
- 匿名显著分量和相邻帧连续事件。

Generate 不得读取 diagnosis GT 评价结果、selector/ranking 输出或未来评价结论。

### Evaluate

Evaluate 阶段只做因素级状态，不合成总分。它分别评价：

- 高可观测锚点段；
- 多视角结构连续性；
- 高能区域滑动；
- 同角/异角配对可评价性；
- range/time/aspect-shuffle/identity-break confounders（距离、时间、观测角打乱、身份错接混杂）；
- static/causal/smoothed 三类可行区间；
- GT containment（参考区域包含）和背景排除。

`causal_forward_feasible_interval` 只允许使用当前帧和过去帧。`offline_forward_backward_feasible_interval`
必须标记为 posthoc（事后诊断），不能伪装成 runtime（运行时）结果。

## Angle Semantics

本轮至少分开输出：

- `motion_tangent_image_deg`
- `body_axis_proxy_deg`
- `global_energy_axis_image_deg`
- `dominant_component_axis_image_deg`
- `significant_component_layout_axis_image_deg`
- `relative_aspect_angle_deg`

禁止输出 `true_vehicle_yaw`、`confirmed_vehicle_heading`、`front_direction_confirmed`。

## Anchor Segment Rules

A 类：完整可观测锚点段，用于主要规律发现。

B 类：完整可观测到 MASK 删除或守门边界的过渡段，本轮只保留 manifest 和后续接口。

C 类：长期 MASK 删除、多响应竞争、结构歧义或标定观测角域外段，只进入失败账本、外推限制和压力测试清单。

锚点段必须在读取 SAR 强度前冻结。若没有满足规则的段，输出 `HIGH_OBSERVABILITY_ANCHOR_SEGMENT_NOT_FOUND`，不得降低规则直到获得想要结果。

## Pairing Rules

配对清单必须在 Plan 阶段预注册，包含：

- `same_aspect_similar_range`
- `different_aspect_similar_range`
- `same_aspect_different_range`
- `time_nearby_control`
- `time_distant_control`

若缺少必要对照，输出 `NOT_EVALUABLE`，不得用零样本默认通过。

## Final Status Semantics

允许的总状态：

- `E0_R3_HIGH_OBSERVABILITY_MULTI_VIEW_READY`: 锚点段、结构响应、匿名分量连续性和区间收缩审计均完成，可进入下一阶段 MASK 过渡验证；不表示完整车辆物理机制已证明。
- `E0_R3_PARTIAL`: 锚点段或结构量测完成，但重复观测角、动态区间收缩、背景反事实或留出验证仍不完整。
- `E0_R3_BLOCKED`: 输入、连续段、标定角域、代码或 replay（重放）问题阻塞。

`VEHICLE_YAW_READINESS` 本轮原则上为 `NOT_READY`。
