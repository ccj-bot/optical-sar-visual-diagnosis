# OTY2 P1-E 光学车辆身份基准与观察层缺口闭合审计协议

日期：`2026-07-14`

## 1. 目的

P1-E 在完整光学时间流上建立独立于运行时预测的物理车辆身份基准，并审计 detector、tracker、原子短轨迹与 P1-C 线程在观察层遗漏、截断、重复、混合和非车辆污染方面的具体缺口。

本阶段只回答“光学画面中真实车辆是谁、何时可见、现有观察是否正确覆盖主体，以及观察失败如何影响身份恢复”。它不修改 P1-C 输出，不实现新的运行时身份算法，也不读取 SAR、SAR GT、光学到 SAR 方位映射或 P2 资产。

## 2. 基准与运行时预测强制分离

P1-E canonical registry、逐帧状态、reference bbox 和检测归属均为研究 benchmark。它们可用于后续机制开发、development/heldout 评估和失败诊断，但不得：

- 写回或替换 P1-C 线程；
- 作为运行时 manual override；
- 将 canonical ID 硬编码进求解器；
- 直接生成最终光学自动跟踪输出；
- 参与 SAR 精定位或最终 SAR 标注。

reference bbox 优先复用正确的 YOLO26l、YOLO11l 或其他既有观察。只有车辆明显可见而所有检测均失败时，才允许建立 benchmark-only 的直接视觉参考；完全遮挡时不得伪造 bbox。

## 3. Canonical 车辆与逐帧状态

Canonical 车辆数以 P1-D 完整场景视觉审计为基础：

- GM_RM011：14 辆；
- GM_RM017：4 辆；
- GM_RM019：4 辆。

每辆 canonical vehicle 必须有唯一 ID、首末可见帧、进入和退出状态、完整可见范围、局部可见范围、可见但无框范围、外观摘要及 P1-C/tracker provenance。每辆车均生成 368 行逐帧状态，使生命周期外、进入、活动、遮挡、可见但无框、退出和离场后状态可直接核验。

若直接视觉审阅与 P1-D 账本存在明确矛盾，P1-E 必须记录证据并修正 benchmark 解释，不得为匹配 P1-C 的 `14/4/6` 线程数而改变真实车辆数。本轮确认的两项审阅修正为：

- GM_RM019:PV003 的真实银色 MPV 生命周期为 frame 98-143；更早的 GV004 片段属于非车辆或行人观察；
- GM_RM011:PV005 在 frame 87 已从左边界局部进入，两路检测均正确观察该白色 Nissan；同帧右边界的 PV004 仍在离场。

## 4. 检测观察归属

所有六张 normalized detection table 中的现有检测必须逐条保留并归为以下状态之一：

- `correct_vehicle_observation`
- `duplicate_observation_same_vehicle`
- `partial_vehicle_observation`
- `mixed_subject_observation`
- `wrong_vehicle_assignment`
- `non_vehicle`
- `ambiguous_detection_geometry`
- `unassigned`

同一帧、同一 canonical vehicle 最多只能有一个 `preferred_subject_observation`。其他同车框必须保留为辅助、重复或局部观察。非车辆检测不得绑定 canonical vehicle；混合框不得进入身份原型。

## 5. 观察失败账本

失败账本必须覆盖三场景全部时间流，而不只记录 P1-D 已知阻断案例。至少包括：可见但无检测、局部框、同车多框、混合主体框、主体切换、非车辆误检、检测源分歧、tracker 碎片化、身份混合、同车多 global ID、不同车共用 global ID、真实车辆漏线程、虚假线程及遮挡恢复失败。

以下 P1-D 阻断案例必须显式闭合：

- GM_RM011 GV009/GV010 同车多 ID；
- GM_RM011 PV014 完全漏线程；
- GM_RM011 PV004 退出前观察恢复失败；
- GM_RM019 GV003 非车辆线程；
- GM_RM019 GV004 主体混合；
- GM_RM019 GV004/GV005 重复表示同一银色 MPV。

## 6. 原子短轨迹碎片化归因

每条 P1-C 原子短轨迹必须追溯到 canonical vehicle 或非车辆污染，并区分：

- 为避免 subject switch 或非车辆污染而必要的纯度保护切分；
- 检测缺失、同帧多框竞争、检测源切换、tracker 局部断裂或补充单例导致的观察层碎片；
- 其他仅由局部连续性构造产生、并非身份纯度所必需的过度碎片化。

P1-E 只做归因，不修改 P1-C 原子短轨迹或 ILP。

## 7. Development 与 heldout

角色必须按物理车辆划分，不得按帧随机拆分。同一车辆的全部 368 行状态继承同一角色：

- `development`：允许用于 P1-F 机制设计；
- `heldout_validation`：只允许最终评估，不得用于特征、阈值或规则选择；
- `diagnostic_only`：只用于阻断案例和失败机制诊断。

三个场景均至少保留一辆 heldout vehicle；GM_RM017 不得全部作为开发正样本。

## 8. 完整视觉验收

READY 前必须实际审阅三个场景各 368 帧原始光学画面，并联合核对 YOLO26l、YOLO11l、P1-C 最终线程和 P1-D 场景上下文。临时 JPG、视频、atlas 或 review page 只允许位于 `D:\profile\research\workspace\output`，不得提交。

视觉审阅用于确认车辆生命周期、主体纯度、局部/完整框、可见但无框、非车辆误检与主体切换；CSV 几何匹配和 validator 不能替代视觉验收。

## 9. Validator 验收条件

validator 至少检查：

1. canonical 数量为 14/4/4，ID 唯一且生命周期有序；
2. 每辆车有且仅有 368 行逐帧状态；
3. 每帧每车最多一个 preferred observation；
4. 每条检测只出现一次，且 provenance 覆盖六张完整检测表；
5. non-vehicle 不绑定 canonical vehicle；
6. fully occluded 不伪造可见 bbox；
7. visible-but-unboxed 与检测归属一致；
8. entry/active/exit/outside 状态一致；
9. P1-D 阻断案例均进入失败账本；
10. benchmark role 按车辆唯一划分且 heldout 无角色泄漏；
11. 固定输入重放前后所有正式输出 hash 一致；
12. P1-B/P1-C/P1-D 历史产物未修改；
13. 工作树中无临时视觉、二进制、NPZ、权重、`.docx` 或 archive 产物进入 P1-E 提交范围。

## 10. 阶段状态

P1-E 只允许：

- `P1E_OPTICAL_IDENTITY_BENCHMARK_READY`
- `P1E_OPTICAL_IDENTITY_BENCHMARK_PARTIALLY_READY`
- `P1E_OPTICAL_IDENTITY_BENCHMARK_BLOCKED`

只有 canonical 总账、完整逐帧审阅、全部检测归属、失败闭合、车辆级角色划分、固定输入重放和 validator 全部通过时才可使用 READY。

`P1E_OPTICAL_IDENTITY_BENCHMARK_READY` 只允许进入 P1-F 多帧车辆表示与观察层恢复设计。它不允许进入 P2；最终车辆精定位仍必须由后续 SAR 阶段在光学先验范围内完成。

## 11. 本轮明确未执行

未修改 P1-C solver、ILP cost、birth/exit cost、身份边权重或历史 P1-B/P1-C/P1-D 产物；未训练 detector、ReID 或其他网络；未运行候选、Gate、selector、ranking、SAR 标注或 P2；未读取 SAR、SAR GT 或方位映射；未触碰 stash 或其他分支。
