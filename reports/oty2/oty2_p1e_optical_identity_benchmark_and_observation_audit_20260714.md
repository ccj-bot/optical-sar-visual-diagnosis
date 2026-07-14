# OTY2 P1-E 光学车辆身份基准与观察层缺口闭合审计报告

日期：`2026-07-14`

## 1. 执行结论

阶段状态：`P1E_OPTICAL_IDENTITY_BENCHMARK_READY`。

本轮建立的是 optical-only 研究基准，不是 P1-C 修复结果，也不允许作为运行时身份输入。未读取 SAR、SAR GT、方位映射或 P2 资产。

## 2. Canonical 车辆与逐帧状态

| scene | canonical vehicles | frame-state rows | visible vehicle frames | visible-but-unboxed |
| --- | ---: | ---: | ---: | ---: |
| GM_RM011 | 14 | 5152 | 467 | 83 |
| GM_RM017 | 4 | 1472 | 191 | 0 |
| GM_RM019 | 4 | 1472 | 135 | 0 |

## 3. 检测源可见车辆观察召回

| source | correct visible vehicle frames | visible vehicle frames | recall |
| --- | ---: | ---: | ---: |
| YOLO26l | 652 | 793 | 0.8222 |
| YOLO11l | 636 | 793 | 0.8020 |
| P1C_adopted | 692 | 793 | 0.8726 |
| YOLO26l+YOLO11l | 710 | 793 | 0.8953 |

## 4. 观察纯度与框状态

- `YOLO11l` / `correct_vehicle_observation`: `63`
- `YOLO11l` / `duplicate_observation_same_vehicle`: `588`
- `YOLO11l` / `mixed_subject_observation`: `39`
- `YOLO11l` / `non_vehicle`: `219`
- `YOLO11l` / `partial_vehicle_observation`: `62`
- `YOLO26l` / `correct_vehicle_observation`: `646`
- `YOLO26l` / `duplicate_observation_same_vehicle`: `72`
- `YOLO26l` / `mixed_subject_observation`: `13`
- `YOLO26l` / `non_vehicle`: `167`
- `YOLO26l` / `partial_vehicle_observation`: `18`

## 5. 原子短轨迹碎片化归因

- `non_vehicle_contamination`: `256`
- `tracker_local_break`: `20`
- `actual_detection_missing`: `9`
- `subject_switch_protection`: `5`
- `detector_source_switch_or_missing_tracker_support`: `2`
- `same_frame_multiple_box_competition`: `2`

保护身份纯度所必需的切分主要是 subject-switch 与 non-vehicle 排除；其余大量碎片来自检测缺失、无 tracker 补充单例、局部 tracker 断裂和同帧多框竞争，不能再依靠全局权重恢复成稳定主体。

## 6. P1-D 阻断案例闭合

- GM_RM011 GV009/GV010：同一持续可见罩车被拆为两个 global ID；中间存在可见但无稳定主体观察的区间。
- GM_RM011 PV014：307-336 的罩车没有进入任何 P1-C 线程。
- GM_RM019 GV003：行人和路侧物体的 vehicle-class 误检形成非车辆线程。
- GM_RM019 GV004：非车辆碎片在约 frame 125 切换到银色 MPV，形成线程内主体混合。
- GM_RM019 GV004/GV005：同一银色 MPV 被并行重复表示。

## 7. P1-F 设计输入

1. 保存多帧颜色分区、车窗/车灯/格栅局部结构、尺度、姿态、边界接触、可见部位和 detector/tracker provenance。
2. 只允许完整、单主体、无遮挡或轻度截断帧进入可靠外观原型。
3. 局部框、混合框、非车辆框和严重边界截断框只能进入诊断，不得污染原型。
4. 车辆专用 ReID 可作为候选，但必须与颜色、结构、姿态和时间一致性联合验证，不能预先认定必然有效。
5. visible-but-unboxed 应通过相邻帧主体传播与显式 visibility state 恢复，不伪造完全遮挡帧 bbox。
6. 先形成较长、身份纯净的局部车辆观察片段，再进入全局一车一 ID 分配。
7. 可复用成熟的多目标跟踪、轨迹片段图、车辆 ReID 和时序特征聚合，但 observation entity、非车辆稳定短轨抑制和 partial/full 主体统一需针对本数据自行设计。

## 8. Benchmark roles

- `development` (11): GM_RM011:PV001, GM_RM011:PV002, GM_RM011:PV005, GM_RM011:PV006, GM_RM011:PV007, GM_RM011:PV010, GM_RM011:PV011, GM_RM011:PV012, GM_RM017:PV001, GM_RM017:PV002, GM_RM019:PV001
- `heldout_validation` (7): GM_RM011:PV003, GM_RM011:PV008, GM_RM011:PV013, GM_RM017:PV003, GM_RM017:PV004, GM_RM019:PV002, GM_RM019:PV004
- `diagnostic_only` (4): GM_RM011:PV004, GM_RM011:PV009, GM_RM011:PV014, GM_RM019:PV003

## 9. 完整审阅与关键量化结论

完整视觉审阅已完成：`true`。三场景各 368 帧，共 1104 帧；联合检查原始光学帧、YOLO26l、YOLO11l、P1-C 线程和 P1-D 上下文。临时 review pages 仅保存在 workspace/output，未进入仓库。

- 可见车辆帧：GM_RM011=467，GM_RM017=191，GM_RM019=135，合计=793。
- visible-but-unboxed：GM_RM011=83，其余场景为 0。
- 检测观察行：完整主体=1369，局部主体=80，混合主体=52，非车辆=386。
- 出现同车重复观察的多框竞争帧=569；重复框保留 provenance，但每帧每车只选一个 preferred observation。

GM_RM011 真实车辆漏线程的直接原因是：车辆在完整时间流中可见，但检测器长期无可用主体框或观察未进入 P1-C；PV014 完全缺席，PV004 和 PV009 则在生命周期中存在观察恢复缺口。GM_RM019 虚假线程的直接原因是行人、路侧物体和小型非车辆区域被 vehicle-class 检测并形成稳定短轨。

本轮视觉复核另确认 GM_RM011:PV005 在 frame 87 已从左边界局部进入；两路检测均应归属该白色 Nissan，而同帧右边界的 PV004 仍在离场。

## 10. 对 P1-F 的明确要求

现有 ResNet18 外观表示缺少车辆专用的细粒度颜色分区、车窗/车灯/格栅局部结构、姿态与尺度条件化、可见部位对齐、多帧原型聚合，以及对局部框、混合框和非车辆污染的显式抑制；单帧通用 embedding 不能承担完整身份恢复。

可继续复用的资产包括：完整光学时间流、两路 detector 的全部 normalized observations、tracker provenance、P1-C 原子短轨迹与观察节点、P1-D 14/4/4 物理车辆视觉账本。必须由多帧机制恢复的内容包括 visible-but-unboxed、检测 gap 后重现、partial/full 主体统一、主体切换后的纯度保护和长生命周期外观原型。

P1-E benchmark 已具备车辆级 development/heldout 划分、完整逐帧状态和失败账本，可支撑 P1-F 机制设计与留出验证；它本身不是运行时输出。

## 11. 阶段边界

P1-F entry allowed: `true`。P2 entry allowed: `false`。

未修改 P1-C ILP、birth/exit 成本、身份边权重或历史 P1-B/P1-C/P1-D 产物；未训练 detector、ReID 或其他网络；未运行候选、Gate、selector、ranking、SAR 标注或 P2。

## 12. 固定输入摘要

- registry rows hash: `f41e5be629c431155cc518e44c352dc3cb9679627be492f9b29f0730e2728201`
- frame-state rows hash: `023870bfbf545422b05b59c48cc23409dd2e3bf4a92029d41b2cb94d7aee6955`
- detection-map rows hash: `88d9faccdf147e83ad50ac78e0e8a2b27aeecc7604ec5730924693d51c9b5a28`
