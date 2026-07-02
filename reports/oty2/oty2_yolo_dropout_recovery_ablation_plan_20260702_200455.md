# OTY2 YOLO dropout recovery A/B 小样本计划

生成时间：`20260702_200455`

本轮没有下载或提交模型权重，也没有替换主线 YOLO。建议下一步只做 12 条样本及其前后帧的小样本 A/B。

## A/B 输入

- A 组：当前 OTY/YOLO 输出。
- B 组：本地已有或后续明确下载的更强 YOLO 权重；权重不得提交到 git。
- 帧范围：12 条 no_oty_iou_match 的当前帧，以及前后 3/5/10 帧。
- 类别范围：vehicle-like / car-like object，不把无关 YOLO 类别混入主分析。

## 核心指标

- 是否恢复当前帧重度截断车。
- primary missing 是否下降。
- secondary-only 是否下降。
- 检测框对 review 框的 containment / overlap 是否改善。
- 是否引入更多远小噪声。
- 时序连续性是否改善。
- handoff / duplicate 是否下降。

## 当前 12 条样本给出的动机

- YOLO 升级候选：`12`。
- 当前帧 secondary-supported 或 temporal continuation supported：`12`。
- SAR 后验支持 detection dropout：`12`。

## 边界

A/B 结果只能用于 detector-ablation 观察；不能直接作为 runtime prior 规则、自动标注建议、阈值调参结论或 identity truth。
