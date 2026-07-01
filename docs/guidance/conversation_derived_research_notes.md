# Conversation-Derived Research Notes

These notes capture research judgments formed in GPT-user discussion. Some are not fully derivable from legacy files, but they are binding guidance for future work in this repository.

## 1. 当前真正不满意的点

当前不满意的点不是简单的 top1 差，而是候选池自身 ceiling 也不够高。

Legacy discussion and archive metrics:

- full candidate pool best AABB IoU median 约 `0.650594`
- full candidate pool best AABB IoU max 约 `0.872249`
- top1 median AABB IoU 约 `0.465558`
- top20 median best AABB IoU 约 `0.645357`

这些数字说明：少量样本中确实存在好候选，但不是稳定高质量；top20 已接近 pool ceiling，说明排序能保住一部分候选潜力；但 pool ceiling 本身不够，所以不能只靠 selector 解决。高质量候选密度不足是核心问题之一。

## 2. 当前问题不是单纯 selector 问题

Selector 当然没有解决，但更早的候选生成、optical-to-SAR transfer、range prior、SAR structural evidence 也没有解决。如果候选池里本来没有足够高 IoU 或视觉上足够贴车的候选，再强 selector 也救不了。

当前主线不应急着恢复 G2 或 formal selector，不应把 deterministic frozen rank 当成最终模型。当前应先查 root cause：

- 光学迁移是否可靠
- range prior 是否表达错误
- candidate generation 是否围绕错误 prior
- SAR structural evidence 是否真正贴车
- temporal evidence 是否真的闭环

## 3. 光学信息使用方式需要重新思考

旧路线可能过早把光学信息压成单点 range prior。光学到 SAR 的 azimuth / 方位向迁移可能比 range / 距离向更可靠，主要不确定性集中在 range/depth。

DepthPro 或 robust distance regression 不应被当成强精确深度。更合理的光学传输形式可能是：

- range band
- range interval
- multi-hypothesis range prior
- near/mid/far ordinal prior
- visibility-conditioned uncertainty
- temporal-smoothed range prior

目标不是从光学直接精确定位到 SAR，而是用光学压缩 SAR 搜索空间，同时把不确定性显式保留下来。

## 4. 并行的“光学鲁棒距离回归是否不适用”线必须合流

另一个并行 session 正在探究 optical robust distance regression 是否不适用。新仓库后续必须允许这条线合流。

如果单点鲁棒距离回归被证明不稳定，主线应转为 uncertainty-aware range prior。不应在没有视觉诊断的情况下继续假设单点 range prior 是正确表达。V0 可视化必须能展示 robust regression 后定位区域在哪里，而不是只输出统计表。

## 5. 可视化不是辅助，而是当前主线

旧仓库最大问题之一是统计和 CSV 多，图像诊断少。当前任务本质上是视觉迁移问题，最终还是要判断 SAR 图上哪里像车。

必须把 optical box、SAR frame、azimuth fan、range band、candidate boxes、factor evidence、temporal context 放在同一诊断视野。只有看图才能判断：

- 光学方位扇形是否落对
- range prior 是否偏
- 候选是否围绕错误 prior
- wedge/ray/signed 是否真的贴在车结构上
- top1/top5/top20 分别在哪里
- 统计上的候选是否视觉上合理

后续每轮如果只生成 CSV 而没有可视化，都视为不完整。

## 6. 视觉与统计必须结合

SAR 车辆目标不是普通框回归问题。不能只用 IoU / median / top-k 表格判断，也不能只靠人眼看图。

需要把“视觉上像车”的判断和以下统计/能量因子结合：

- local SAR intensity / contrast
- compactness
- range profile peak
- wedge response
- ray peak support
- temporal consistency
- candidate source provenance
- prior consistency
- visible risk
- conflict / ambiguity

后续 factor breakdown 的目标是解释“这个候选凭什么像车”，而不是立即做 selector score。

## 7. 时序现在没有真正用深

旧阶段已经有 greedy track、track anchor、signed vote、short-window temporal context，但这只是浅层时序。当前还没有：

- explicit same-target runtime track id
- track-level joint optimization
- temporal candidate tube
- shared offset runtime solver
- temporal release evidence

当前 temporal strip 只是 context shell，不等于真正使用时序。后续时序诊断要看：

- 前后帧 range offset 是否连续
- wedge/ray 偏移是否跨帧一致
- 某个候选是否沿同一车辆轨迹合理
- signed pos/neg 是否稳定
- SAR 结构是否跨帧保持一致

## 8. Structural Candidates 的位置

Wedge/ray/signed 已经生成，但不能说它们已经解决问题。Structural candidate presence 不等于 structural selector success。

当前 structural candidates 主要进入 top10/top20，而不是 top1/top5。它们的价值在于揭示 SAR structural uncertainty，而不是直接当规则。

- wedge 可能提供 local structure refinement
- ray 可能提供 range escape hypothesis，但也可能是 clutter
- signed 可能提供 temporal escape direction，但目前证据弱
- bidirectional escape 必须保持 review-only

## 9. GM_RM011 不能机械复制 GM_RM019

GM_RM019 是当前 pilot。GM_RM011 还没有复现同等 candidate input chain，并且可能存在 display-XY / storage-axis / OBB convention 混合风险。

GM_RM011 首先需要 visual probe 和 geometry convention audit。011 应先看：

- optical/SAR frame join 是否正常
- azimuth fan 是否落对
- range prior 是否系统偏
- SAR 目标结构是否和 019 有显著差异
- `w/h/heading` 是否只是存储轴而非车头方向

不允许把 GM_RM019 的结论直接外推到 GM_RM011。

## 10. 新仓库的真正目标

新仓库不是为了快速做一个新算法，也不是为了继续旧 pipeline。它是为了找出 optical-to-SAR transfer 为什么失败。

当前阶段不是追指标，而是建立视觉诊断闭环。先形成 failure taxonomy，再决定：

- range prior diagnosis
- candidate generation redesign
- structural factor layer
- temporal evidence
- GM_RM011-specific geometry audit
- selector/calibration

Selector 是后置问题，不是当前默认主线。
