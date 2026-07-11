# OTY2 生成冻结与 GT 辅助分析边界

Updated: 2026-07-11

## 1. 核心原则

OTY2 后续实验必须将“实验生成”和“机制分析”严格分开。

### 生成阶段

生成阶段只允许使用运行时安全或源锚点安全的信息：

- SAR 图像；
- 已冻结的源锚点；
- 静态扇形几何；
- 自动光学时序消息及其不确定状态；
- 已冻结的、与未来目标无关的搜索预算；
- 当前帧及过去帧的因果观测。

生成阶段禁止读取或使用：

- 当前待评价帧的人工 SAR GT；
- 未来目标框；
- 正向/负向窗口标签；
- “这是白车/银车”的人工身份结论；
- 由 GT 得出的角色、结构或尺度结论；
- 评价阶段的误接、误拒结果；
- 根据评价结果重新调整本轮规则。

生成阶段结束后，必须冻结核心产物并记录 SHA256。

### 盲审阶段

盲审阶段查看不带 GT、不带正负标签、不带车辆名称的运行图。对象和帧使用不透明编号。盲审结果必须先写入 CSV 并冻结 SHA256，然后才能进入 GT 辅助分析。

盲审允许判断车辆部件支持、背景结构支持和无法判断；不得看到 EVAL_ONLY GT 框、正负窗口分类、预设实体类别或按帧号生成的解释。

### GT 辅助分析阶段

生成结果和盲审结果冻结后，可以灵活使用 GT。GT 可以用于：

- 判断冻结结构与目标区域的空间关系；
- 解释为什么某结构支持车辆；
- 检查为什么另一个强响应不是车辆；
- 定位误拒、误接和漏提取原因；
- 研究尺度、部件关系、背景弧线和时序漂移；
- 提出下一轮机制假设；
- 形成反例与失败类型。

GT 不可以用于修改本轮已经冻结的散射原子、结构组合、盲审判断和运行时分类，也不得在评价后调阈值覆盖本轮结果。

## 2. 信息流

正确流程：

```text
runtime-safe inputs
    -> generate
    -> freeze prediction/artifact SHA
    -> blind visual review without GT
    -> freeze blind-review SHA
    -> load GT and polarity labels
    -> evaluate and explain
    -> mechanism diagnosis
    -> propose next-round correction
```

禁止流程：

```text
load GT/polarity
    -> alter role or entity classification
    -> report zero false accept/reject
```

## 3. 数学边界

生成阶段：

\[
\hat Y_t =
F(I_{\le t}^{SAR}, O_{\le t}^{optical}, A_{source}, G_{static})
\]

其中不得包含待评价目标：

\[
Y_t^{GT}, Y_{t+1}^{GT}, \ldots
\]

盲审阶段：

\[
J_i = H(V_i^{runtime})
\]

GT 辅助评价阶段：

\[
E_i = Q(\hat Y_i, J_i, Y_i^{GT})
\]

本轮结果必须保持：

\[
\frac{\partial \hat Y_i}{\partial Y_i^{GT}} = 0
\]

评价结果只能影响下一轮假设，不能反向覆盖本轮生成。

## 4. “为什么这个是，而其他不是”

对于每个被支持的车辆结构 \(S^+\)，至少选择一个同帧或邻近窗口中的强替代结构 \(S^-\)，逐项比较：

\[
C(S^+, S^-)
=
\{
\text{尺度},
\text{主体核心},
\text{部件关系},
\text{弧线冲突},
\text{孤立性},
\text{时序谱系},
\text{光学兼容性}
\}
\]

必须回答：

1. \(S^+\) 为什么具备车辆支持；
2. \(S^-\) 为什么不能被同样解释；
3. 哪一个差异是决定性差异；
4. 哪些差异只是辅助证据；
5. 是否存在无法区分的反例。

不能只写通用模板，必须引用该对象的实际字段、实际图像现象和实际时序关系。

## 5. 字段来源

报告中的字段必须标注为：

- `runtime_safe`
- `blind_visual_review`
- `eval_only_gt_assisted`
- `human_or_multimodal_posthoc`

## 6. 结论边界

即使 GT 辅助分析能够清楚说明某个结构是车，也只能证明该物理结构假设在事后分析中有解释力。只有在不使用 GT 的盲生成和盲审中能够稳定重现，才可以进一步讨论运行时车辆支持观测实体。
