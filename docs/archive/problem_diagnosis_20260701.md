# Problem Diagnosis - 2026-07-01

## Core Diagnosis

当前问题不是单纯 selector 问题。旧阶段已经证明：即使存在更多 candidate source，candidate pool 本身的高质量候选密度仍不够，且 optical range prior 的表达方式可能存在系统性问题。

## Candidate Pool Ceiling

旧 C1S / Phase4D 诊断给出的关键 AABB proxy 指标：

- full candidate pool best AABB IoU median 约 `0.650594`
- full candidate pool best AABB IoU max 约 `0.872249`
- top1 median AABB IoU 约 `0.465558`
- top20 median best AABB IoU 约 `0.645357`

这些数值说明 top20 比 top1 有明显提升，但 full pool ceiling 仍不够高，不能只靠选择器解决。

## Current Failure Modes

1. 高质量候选密度不足。候选池中存在较好候选，但并不稳定、密集地贴近真实 SAR 车辆结构。
2. 光学 range prior 可能表达方式不对。单点 range 回归容易把错误 prior 传给后续 candidate generation；更适合诊断 range band、range distribution 或 release direction。
3. SAR structural candidates 已经生成，但没有形成真正 runtime factor layer。wedge/ray/signed 仍主要是 audit/candidate input，而不是可靠性确认层。
4. 时序只浅用。C1.3/C1.4 得到 partial short-window evidence，但没有 explicit same-target runtime track id，因此 temporal release evidence 还没有闭环。
5. SAR-only targets 不能用 final boxes 回填。final/posthoc/oracle/GT 只能解释失败，不能成为 runtime generation/ranking 输入。
6. GM_RM019 candidate input chain 已经打通，但 GM_RM011 尚未复现同等链路。跨场景泛化仍是开放问题。
7. 缺少可视化诊断导致统计无法解释视觉错误。单看 median/top20/full-pool 指标，无法判断是 optical azimuth、range band、SAR local structure、source family、还是 temporal context 出错。

## Why Visualization-First

新仓库第一阶段必须 visualization-first。V0 应先把每个样本的 optical box、azimuth ray、range prior band、factor prior box、source-family candidates、factor breakdown 和 temporal strip 放到同一个诊断上下文中。

只有看清楚视觉错误类型后，后续才有资格讨论 candidate construction、factor layer 或 calibration。当前不应继续把问题压成 selector/threshold/G2/A008 scoring。
