# OTY2-S1X 冻结输出事后直接视觉复核

日期：`2026-07-17`

本复核只查看已经冻结的 optical-only shell、per-frame independent support、joint temporal support 与事后参考框。它没有修改 inference 配置、校准、阈值或 mask。

## 1. 发现窗口

在均匀抽取的 SAR `330, 332, 335, 338, 341, 344, 347, 350` 中：

- optical shell 均覆盖参考框的一部分，但明显比参考框和可见响应宽；
- joint support 的主要绿色横带稳定落在参考框中下部；
- 上部零散绿色响应多数位于参考框外或边缘，符合 blind review 中的 mixed/intermittent 判断；
- 主横带只覆盖参考框的一小部分，说明它表达的是可见 SAR 响应，不是完整车体框；
- 没有看到 joint support 接入同帧其他车辆参考区域。

对应量化：reference-hit frame `21/21`，mean target coverage `0.1096`，mean precision `0.6243`，mean shell contraction `0.9465`。

## 2. 冻结重放窗口

在均匀抽取的 SAR `338, 345, 353, 360, 368, 375, 383, 391` 中：

- 绿色主响应持续落在白色 SUV 参考框下部或中下部；
- 与发现窗口相比，框外零散响应更少，主横带更集中；
- 后段局部背景结构变化没有使支撑跳到邻车；
- 仍未恢复完整参考框，也没有输出唯一中心。

对应量化：reference-hit frame `54/54`，mean target coverage `0.1198`，mean precision `0.9415`，mean shell contraction `0.9606`。

## 3. 时序比较

per-frame independent 与 joint 两条路径都没有发生整帧断裂，因此本轮不能宣称 joint 新恢复了缺失帧。joint 的作用主要表现为：

- 在目标参考区域内每帧都保留 weak-maintained pixels；
- discovery centroid-jump median 从 `13.743 px` 降到 `11.469 px`；
- replay centroid-jump median 从 `4.911 px` 降到 `3.707 px`；
- replay P90 jump 从 `17.101 px` 降到 `14.238 px`。

因此“整段联合比逐帧更稳定”只得到部分支持：跳动下降，但没有额外断帧恢复。

## 4. 事后复核结论

```text
DISCOVERY_FROZEN_SUPPORT_REFERENCE_RELATION=CONSISTENT_LOWER_OR_MID_VISIBLE_RESPONSE
REPLAY_FROZEN_SUPPORT_REFERENCE_RELATION=PARTIALLY_REPRODUCED_WITH_HIGHER_PRECISION
FULL_BODY_BOX_RECOVERY=NOT_PERFORMED
UNIQUE_CENTER_RECOVERY=NOT_PERFORMED
OTHER_VEHICLE_CONTAMINATION=NOT_OBSERVED_IN_EVALUATED_REFERENCE_ROWS
RULE_UPDATED_AFTER_EVALUATION=false
```

事后 PNG 位于 `D:/profile/research/workspace/output/oty2_s1x_20260717/*/posthoc_review`，不进入 Git。
