# OTY2 P1-F 多帧主体观察整理与缺失观察恢复协议

日期：`2026-07-14`

## 1. 阶段目标

P1-F 第一轮只建立运行时观察层：统一两路 detector 观察、保留同帧备选关系、形成短期 local subject、每主体每帧最多选择一个可信观察，并以可审计的光学传播尝试恢复短期缺失观察。

本轮不统一最终物理车辆身份，不修改 P1-C ILP、目标函数或身份边权重，不训练 detector/ReID，不读取 SAR、SAR GT、方位映射或 P2 资产。

## 2. Runtime 与 benchmark 分离

运行时脚本只允许读取原始光学帧、YOLO26l/YOLO11l normalized detections、检测 confidence/class/bbox、P1-C 观察节点中已有 tracker 局部关系及运行时可计算的颜色、形状、运动和光流证据。

运行时正式输出不得包含 canonical vehicle ID、reference bbox 或 benchmark role。local subject ID 必须由运行时顺序生成，不得从 development canonical ID 派生。

P1-E registry、逐帧状态、检测归属和车辆角色只允许由独立 evaluator 读取。heldout 车辆不得用于参数、恢复跨度、证据权重或方法分支选择；diagnostic-only 只用于失败审阅，不参与阈值选择。

## 3. 统一观察与同帧备选簇

六张 normalized detection table 的全部检测均进入统一 runtime observation 表。每条观察保留 detector provenance、tracker provenance、bbox、置信度、边界接触、颜色摘要、边缘密度、面积/长宽比和 vehicle-likeness 分项证据。

同帧聚类同时考虑 IoU、intersection-over-min、中心距离、颜色一致性、tracker 支持和来源支持。聚类只表达“可能属于同一主体的备选观察”，不得只按最高置信度删除其他框。

## 4. 主体质量证据

每条观察输出独立证据并归为：

- `complete_subject_candidate`
- `partial_subject_candidate`
- `mixed_subject_candidate`
- `duplicate_alternative`
- `possible_non_vehicle`
- `temporally_inconsistent`
- `unresolved_runtime_observation`

vehicle-likeness、完整性、混合风险和时间一致性均保留分项，不建立依次执行的硬 Gate 树。局部框可以用于运动和颜色辅助，但不默认进入身份外观原型；混合框和 possible-non-vehicle 仅用于诊断。

## 5. Local subject 与唯一选择

local subject 是短期运行时观察片段，不是 canonical 身份，也不是最终 P1-C global thread。它优先沿用已有 tracker provenance，并通过相邻帧的一对一几何、颜色和多源支持完成短期连续性整理。

出现强颜色跳变、异常空间跳跃或同帧排他冲突时必须切断。每个 local subject 在每一帧最多选择一个 `selected_subject_observation`；其他框保留为 alternative provenance。

## 6. 缺失恢复

恢复使用相邻光学帧上的 LK 特征光流、RANSAC 相似仿射和局部模板相关性。前向与后向传播分别保存；存在双向种子时以传播结果的一致性决定是否接受。

线性 bbox 插值只允许作为诊断对照，不得成为正式恢复框。传播必须记录 seed、跨度、每步有效特征点、仿射内点率、模板 NCC、尺度连续性、运动连续性和同帧主体冲突。

以下情况不接受恢复：图像支持不足、传播落到另一主体、双向严重不一致、尺度异常、主体已经从边界离场或无可靠 seed。运行时无法确认可见性的失败帧标为 `runtime_unresolved`；不得伪造 fully occluded bbox。

## 7. 非车辆与混合主体控制

非车辆证据由多帧面积/形状、颜色/结构、tracker 持续性、运动合理性和进入—活动—退出解释共同形成，不得只依赖 detector class、稳定性或短轨长度。

mixed/partial 观察必须输出 motion/color/appearance/shape/diagnostic 用途。只有完整、单主体且时间一致的观察默认允许进入下一轮多帧身份外观原型。

## 8. 四级实验

- Baseline A：YOLO26l 单源，不恢复。
- Baseline B：YOLO26l+YOLO11l 同帧备选簇与主体选择，不恢复。
- Baseline C：多源主体选择加单向短时恢复。
- Baseline D：多源主体选择、双向恢复和非车辆/混合控制。

参数只允许在 development 车辆上以少量机制驱动设置。heldout 只运行一次正式评价，并单独报告。diagnostic-only 用于恢复和失败案例视觉审阅，不参与参数选择。

## 9. 评价与验收

独立 evaluator 按 development、heldout、diagnostic-only 报告主体观察召回、完整/局部/无观察状态、恢复正确性、错误车辆恢复、遮挡误恢复、重复占用、混合/非车辆选择、连续正确段长度、单帧碎片比例和可形成可靠多帧原型的区间。

几何重叠只是评价证据之一。框必须属于正确车辆、覆盖主要车体、不混入其他车辆、保持运动/尺度连续，并适合其声明用途。

## 10. 阶段状态

只允许：

- `P1F_SUBJECT_OBSERVATION_LAYER_READY`
- `P1F_SUBJECT_OBSERVATION_LAYER_PARTIALLY_READY`
- `P1F_SUBJECT_OBSERVATION_LAYER_BLOCKED`

READY 需要 runtime/benchmark 泄漏检查、完整三场景运行、heldout 改进、实质性正确恢复、无明显错误车辆或遮挡误恢复、观察唯一性、非车辆/混合控制、连续段改进、固定输入重放、validator 和规定视觉审阅全部通过。

READY 只允许进入 P1-F 下一部分的多帧车辆外观、颜色、姿态和结构原型表示；任何状态均不允许直接进入 P2。
