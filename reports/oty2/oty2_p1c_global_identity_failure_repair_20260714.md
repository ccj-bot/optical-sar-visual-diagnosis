# OTY2 P1-C 光学全局身份失败修复报告

日期：`2026-07-14`

## 1. 执行结论

最终状态：`P1C_GLOBAL_IDENTITY_REPAIR_READY`。本轮只读取光学资产，未读取 SAR、SAR GT、方位映射或最终标注。

GM_RM019 黑车的 P1-B 失败被确认是验证语义误报：黑车线程 0-14 已完整，P1-C 使用独立 identity anchor 后留出评价通过，没有强制延伸到 frame 29。

修复后仍被选择的 boundary-reentry turnover 边：`[]`。

## 2. 新增通用机制

1. 无 tracker 的同源连续观察使用一对一局部几何/颜色证据形成短链；不恢复原 tracker ID，不跨 subject-switch 边界。
2. 对短时重叠且每个重叠帧都满足现有 containment/center 一致性的同源片段做局部 union，用于 partial-to-full tracker handoff；不跨 subject-switch 边界。
3. 对超过 mandatory-review 长度的 gap，在边界退出后从对侧重入，或从同侧重新向画面内部出现的 transition，加入一次 exit+birth 生命周期 reset 软成本。短缺口和沿边界继续向外运动的恢复不受影响。该项不禁止边，也不含场景名、帧号或人工 edge ID。
4. 对通过一个短桥接节点绕开上述重入代价的两边路径，使用最小二阶 transition 变量施加同一软 reset 成本。
5. subject-switch 原子片段只允许同 tracker、零缺口的局部续接；其他外部前驱进入该片段时施加同一生命周期 reset，防止无关车辆借全局边抹掉主体切换边界。
6. 留出 evidence 使用独立 review window 与 identity anchor；anchor ledger 明确为 evaluation-only。

## 3. 三场景结果

| scene | atomic tracklets | candidate edges | vehicle threads | min edge Jaccard | thread-count stable |
| --- | ---: | ---: | ---: | ---: | --- |
| GM_RM011 | 130 | 1853 | 14 | 1.000000 | True |
| GM_RM017 | 26 | 127 | 4 | 1.000000 | True |
| GM_RM019 | 138 | 3716 | 6 | 1.000000 | True |

## 4. 证据与约束

heldout failures：`[]`。

hard constraints：`{"same_frame_duplicate_identity_count": 0, "forbidden_merge_violation_count": 0, "observation_duplicate_use_count": 0, "track_time_reverse_count": 0, "total_hard_constraint_violations": 0}`。

完整 MP4 审阅标记：`True`。

## 5. 修复前后与视觉复核

| scene | P1-B atomic | P1-C atomic | P1-B threads | P1-C threads |
| --- | ---: | ---: | ---: | ---: |
| GM_RM011 | 185 | 130 | 7 | 14 |
| GM_RM017 | 36 | 26 | 4 | 4 |
| GM_RM019 | 230 | 138 | 6 | 6 |

P1-B 单帧原子轨迹比例为 GM_RM011 `71.35%`、GM_RM017 `77.78%`、GM_RM019 `86.52%`；P1-C 的局部同源成链与重叠片段 union 分别把原子节点降到 130、26、138，而不恢复不可拆的原 tracker ID。

GM_RM011 四条已确认长缺口错误边的联合反事实仅使 identity cost `2995 -> 3008`（`+13`），证明 P1-B 存在近似等价退化；正确解释原本以退出+新出生的生命周期替代存在，不是候选边缺失。

最终逐帧复核确认：0-60 的前景罩车、背景 Maxus 与后续罩车互不串接；88-166 的白 Nissan、罩车、深灰轿车、白 Honda 分别保持连续；188-315 的独立生命周期与同色多车区间无错误长缺口合并；GM_RM019 黑车 0-14、灰色 MPV 98-143、灰色 SUV 149-183 均通过。

GM_RM011 的六种软代价扰动、GM_RM017 和 GM_RM019 的六种扰动最终均为线程数稳定且 selected-edge Jaccard `1.0`。

## 6. 阶段判定

允许进入 `P1-D` 物理车辆线程最终冻结与全生命周期验收；不允许直接进入 P2。

## 7. 边界

本轮未运行 P2、SAR 坐标、Mask、candidate、selector、ranking、训练或自动标注。P1-C READY 仅允许进入 P1-D，不允许直接进入 P2。
