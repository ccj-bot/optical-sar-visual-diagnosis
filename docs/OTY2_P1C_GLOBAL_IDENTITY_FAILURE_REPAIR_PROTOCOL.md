# OTY2 P1-C 光学全局身份失败诊断与最小修复协议

日期：`2026-07-14`

## 1. 阶段边界

P1-C 只处理完整光学时间流中的物理车辆身份失败。输入限于光学帧、光学检测、tracker provenance、光学 appearance/color 特征、P1-A 身份证据账本和 P1-B 图/线程产物。

本阶段禁止读取或使用 SAR、SAR GT、方位映射、SAR 坐标、Mask、candidate、selector、ranking、IoU 或最终标注结果。P1-C 诊断关系不得作为逐案例硬编码进入最终求解器。

## 2. 先诊断、后修复

任何求解器或配置修改前必须完成：

1. 逐帧完整审阅指定 MP4 和原始光学区间；
2. 确认失败是原始观察缺失、原子短轨迹碎片化、候选边缺失、边选择错误、生命周期代价错误、路径级证据不足，还是验证语义错误；
3. 输出失败账本、原子短轨迹粒度审计、反事实求解比较和近似等价解分析；
4. 明确正确解释是否需要同车边，或应表达为前车退出与后车出生。

## 3. 失败分类规则

- `observation_missing`：物理车辆可见但 observation pool 没有可用观察。
- `atomic_fragmentation`：局部连续观察被拆成过多 1–2 帧节点，使全局图近似逐帧关联。
- `candidate_edge_missing`：正确同车关系需要转移边，但 DAG 中不存在可行路径。
- `candidate_edge_not_selected`：正确边存在，但目标函数选择了错误边。
- `lifecycle_turnover_underpriced`：车辆已从边界退出、另一车辆从对侧边界进入，但固定 birth/exit 代价使错误桥接略优。
- `path_evidence_insufficient`：边局部证据无法表达整段运动、外观或进入—退出拓扑。
- `validation_semantics_error`：审阅窗口端点被错误当作同车锚点，或只按帧覆盖判断对象身份。

## 4. 允许的最小通用修复

修复必须是统一光学机制，优先顺序为：

1. 修正验证语义，使 evidence window 与 identity anchor 分离；
2. 在统一目标中表达边界退出—对侧新进入的生命周期 turnover，而不是增加场景或帧号 Gate；
3. 已由纯光学审阅确认的 `subject_switch` 原子切分只允许同 tracker、零缺口的局部续接；无该连续证据的外部前驱进入切分片段时必须承担独立生命周期 reset，不能借全局边抹掉主体切换边界；
4. 如仍有必要，再引入最小二阶运动或线程级原型证据；
5. 不通过大规模权重搜索选择恰好命中人工答案的配置。

## 5. 反事实使用边界

GM_RM011 已视觉确认的错误边可在诊断求解中临时禁止，用于测量目标差和连锁影响；这些 edge ID 不能进入最终运行时配置。GM_RM019 黑车不需要强制连接到 frame 29，因为完整视觉显示其真实可见生命周期为 frame 0–14。

## 6. 退出标准

只有在三场景固定种子回放后同时满足以下条件，才能标记 `P1C_GLOBAL_IDENTITY_REPAIR_READY`：

- GM_RM019 黑车留出关系按对象语义正确评价，且不向 frame 29 伪造同车延伸；
- GM_RM011 已确认的四条错误 turnover 边不再被选择；
- GM_RM017 线程和身份边不退化；
- hard constraint 违规为 0；
- 修复不含场景专用 Gate、帧号特例或 manual override；
- 临时 MP4、atlas、图片、NPZ 和 outputs 不进入提交。
