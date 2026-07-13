# OTY2 P1-B 光学全局物理车辆身份求解报告

日期：`2026-07-13`

## 1. 执行结论

最终状态：`P1B_GLOBAL_IDENTITY_BASELINE_PARTIALLY_READY`。三场景完整 368 帧光学流均已建图并求解；SAR、SAR GT、方位映射和最终标注均未读取或运行。

当前不能升级为 READY：GM_RM019 的早期黑车留出生命周期被拆断；GM_RM011 的线程结构对 birth/exit 与 gap 代价扰动不稳定，直接视觉审阅仍见同色车辆长 gap 串接风险。

## 2. 全局身份问题的实际建模方式

以 provenance-preserving detection observation 为底层对象，同帧跨检测器重复表示形成 alternative cluster；局部 tracker 只产生可拆分原子短轨迹；短轨迹构成 DAG，并由二进制路径覆盖模型联合决定 observation 解释、出生、退出、跨缺口恢复和 source switch。车辆数量不是输入参数。

## 3. 原子短轨迹如何形成

YOLO26l raw BoT-SORT 与 YOLO11l normalized-active BoT-SORT 只作为种子。帧缺口、已确认 subject-switch 边界以及运动跳变与 appearance/color 联合异常可触发拆分。每个拆分点保留原因和 P1-C 风险标志。

## 4. 多源观察如何整理

主源为 YOLO26l normalized-active，辅助源为 YOLO11l。跨源 alternative cluster 使用同帧 IoU 或 partial/full containment 建立；所有原框、置信度、类别、路径、feature reference 和 tracker provenance 均保留，未选框仍在审计清单。

## 5. 硬约束和软证据

硬约束仅包含时间顺序、观察/cluster 排他、保守瞬时位移可行性、已确认 non-vehicle、subject-switch 和 forbidden/different 关系。运动、颜色、ResNet18 appearance、形状尺度、边界、gap、tracker 支持与 detector provenance 均作为统一软证据并逐边输出。

## 6. ILP/CP-SAT 目标层级

使用 SciPy `milp`/HiGHS 的多阶段整数优化：先最大化可信 observation coverage；固定 coverage 后最小化可审计的身份解释代价（birth、exit 与逐边软证据代价）；再次固定该代价后，用 gap 长度和轻微 source preference 做确定性 tie-break。已确认 forbidden relation 通过求解后路径 cut 迭代至零违规。

## 7. 三场景求解结果

| scene | atomic tracklets | candidate edges | vehicle threads | solver |
| --- | ---: | ---: | ---: | --- |
| GM_RM011 | 185 | 3970 | 7 | optimal |
| GM_RM017 | 36 | 340 | 4 | optimal |
| GM_RM019 | 230 | 10960 | 6 | optimal |

检测源实际选用：GM_RM011=YOLO26l 254 / YOLO11l 121；GM_RM017=YOLO26l 191 / YOLO11l 0；GM_RM019=YOLO26l 84 / YOLO11l 136。这只是全局解的来源使用结果，不表示任一 detector 是身份真值。

## 8. 车辆线程数量及生命周期

车辆线程数是全局路径覆盖的结果，不与 P1-A 视觉估计做强制一致。每条线程显式导出 `birth_or_entry / active_visible / missed_or_occluded / recovery / exit_or_death`；gap 行没有伪造 bbox。

## 9. tracker 合并、拆分和跨缺口恢复

- `GM_RM011`：tracker merges=8，atomic splits=28，gap recoveries=10。
- `GM_RM017`：tracker merges=0，atomic splits=0，gap recoveries=0。
- `GM_RM019`：tracker merges=6，atomic splits=9，gap recoveries=10。

## 10. 已知身份证据结果

开发/硬约束结果：`{"development_evidence": {"same_vehicle:pass": 1, "forbidden_merge:unresolved_not_promoted": 1, "different_vehicle:unresolved_not_promoted": 3, "same_vehicle:fail": 1}, "hard_constraint": {"different_vehicle:unresolved_not_promoted": 3, "subject_switch:pass": 3, "forbidden_merge:pass": 3, "non_vehicle:pass": 3}, "diagnostic_only": {"unresolved:unresolved_not_promoted": 1}}`。

## 11. 留出证据结果

留出关系在求解前预先声明且未进入目标：`{"same_vehicle:pass": 8, "visible_but_unboxed:pass": 1, "temporally_continuous:unresolved_not_promoted": 2, "same_vehicle:fail": 1, "temporally_continuous:pass": 1}`。

## 12. 参数稳定性

- `GM_RM011`：thread_count_stable=False，minimum selected-edge Jaccard=0.591。
- `GM_RM017`：thread_count_stable=True，minimum selected-edge Jaccard=1.000。
- `GM_RM019`：thread_count_stable=True，minimum selected-edge Jaccard=1.000。

## 13. 直接视觉审阅的初步发现

完整线程视频、线程 contact sheet、所有 tracker merge/split、长 gap、detector source switch、高风险边和留出失败事件均已自动写入受 `.gitignore` 控制的 P1-C 临时复核包。本轮已直接审阅三场景全部 thread atlas 和覆盖全部 mandatory event 的 event atlas；视频已生成，但没有逐个 MP4 从头到尾播放。

- GM_RM017：四条线程视觉上连续、互斥，和四车竞争窗口一致。
- GM_RM019：早期黑车生命周期被拆开，留出失败有效；149-183 灰车仍存在局部 fragment 竞争。
- GM_RM011：多个 tracker merge/gap event 位于同色车辆替换与严重截断窗口，当前 7 条线程不能视为冻结物理身份。

## 14. 当前主要失败类型

主要失败类型是 GM_RM011 同色多车长窗口的过串接/近似等价解、GM_RM019 早期黑车的 fragment split、严重截断造成的 appearance/shape 不稳定，以及少量弱 detector supplement 与长 gap 的竞争。所有这些边保留分量和 review flag，不伪装为最终冻结身份。

## 15. 是否允许进入 P1-C

`no; heldout same-vehicle failure and GM_RM011 parameter instability remain open`。P1-C 只允许对复核包做多模态直接审阅、错误诊断和最小光学身份图修复，不重新设计 Gate 树。

## 16. 本轮明确没有运行的内容

没有运行或读取 SAR 灰度/伪彩/SAR GT、光学-SAR 方位映射、SAR 米制坐标、Mask、SAR candidate、Gate、selector、ranking、IoU、最终框、训练、ReID 训练、大规模权重搜索、原始资产修改或 stash 操作。

## 硬约束校验

`{"same_frame_duplicate_identity_count": 0, "forbidden_merge_violation_count": 0, "observation_duplicate_use_count": 0, "track_time_reverse_count": 0, "total_hard_constraint_violations": 0}`
