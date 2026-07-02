# OTY2 运行时空间先验可视化诊断报告

生成时间：`20260702_151419`

本报告解释当前 OTY2 运行时空间先验为什么仍然偏弱。它只读取已经生成的目标级时间窗、时间窗质量审阅和运行时空间先验审计结果；不读取雷达图像，不使用雷达真值，不做空间搜索，不生成搜索区域或候选框，不评分，不选择，不训练，不给自动标注建议。

## 一句话结论

当前弱空间先验的最核心短板在**距离向**：所有非 blocked 的 normal / relaxed / review-only 行都只能给出 `broad_unknown_range_prior`。方位向已经有弱约束，但它来自运行时安全的配置几何和光学 bbox envelope；时间窗已经能回答“什么时候看”，但不能回答“在哪里找”。

## 总体分布

| scene | normal primary | relaxed normal | review-only | blocked |
| --- | --- | --- | --- | --- |
| `GM_RM011` | 0 | 0 | 0 | 1 |
| `GM_RM017` | 2 | 3 | 1 | 0 |
| `GM_RM019` | 2 | 4 | 6 | 9 |

- normal downstream 总数：`11`，其中稳定/主观测 normal 为 `4`，带不确定性扩展的 relaxed normal 为 `7`。
- review-only 空间上下文：`7`。
- blocked：`10`，其中 `GM_RM011` 是“有时间元数据、无目标流”的场景级 blocked。
- SAR 时间窗宽度范围：`14` 到 `160` 帧，均值约 `88.167` 帧。
- 方位角宽度范围：`8.501` 到 `86.002` 度，均值约 `58.774` 度。

## 当前“弱”具体弱在哪里

| weakness source | count |
| --- | --- |
| `missing_optical_object_flow` | 1 |
| `object_not_ready_or_short_noise` | 9 |
| `range_missing_info` | 11 |
| `range_missing_plus_review_uncertainty` | 7 |

1. **距离向弱**：这是最主要的弱。当前输入没有运行时安全的 per-object range/depth 几何，所以所有可用行都保留 `broad_unknown_range_prior`。这是信息缺失导致的弱，同时也是边界保守性：不为了让图好看而编造距离向。
2. **方位向弱但可用**：方位向来自 `configs/scene_config.yaml` 的配置几何和光学 bbox envelope。它能给“弱方位范围”，但不是最终位置，也不是雷达证据。bbox envelope 宽、edge/partial/secondary/handoff 状态会让方位范围更宽。
3. **时间窗有用但不是空间信息**：24 fps 到 50 fps 的软件同步时间窗只限定“雷达帧什么时候相关”，不直接产生距离向或二维空间区域。
4. **状态不确定性弱**：secondary、edge、partial、duplicate、handoff 不直接 blocked，而是扩大余量或降级到 relaxed；ambiguous/review-required 进入 review-only；short/noise 或 not-ready 才 blocked。
5. **场景/对象困难导致的弱**：`GM_RM019` 同时包含较多 review-only 和 blocked 对象，弱主要来自对象状态复杂和 not-ready 目标；`GM_RM011` 的弱是目标流缺失，不是时间元数据缺失。

## 各组成部分的作用

- **光学目标流**：提供目标级 object_hypothesis_id、主/辅观测、起止帧、状态标签和不确定性来源。它使 OTY2 不再回退到单帧检测框级合并。
- **主观测**：决定一个对象能否形成正常运行时输入。稳定主连续目标使用较小余量。
- **辅助观测**：不是身份真值；它提示 partial、duplicate、handoff 或跨片段不确定性，因此扩大方位和时间余量。
- **edge / partial / duplicate / handoff / ambiguity**：edge/partial/duplicate/handoff 倾向于扩大或放松先验；ambiguity/review-required 倾向于 review-only；short/noise 则 blocked。
- **时间窗**：从光学帧段和 24:50 软件同步契约得到 SAR 帧范围。它限制“何时看雷达”，但不产生“在哪里找”的空间位置。
- **场景几何**：当前真正起作用的是光学 x 到方位角的弱配置映射；距离向几何尚未形成运行时安全的目标级字段。
- **规则层**：把对象分成 normal、relaxed、review-only、blocked。它的作用是保留不确定性来源，而不是把弱证据硬说成真值。
- **最终空间先验**：表达运行时安全的空间约束描述；不是最终位置，不是 SAR 搜索结果，不是候选框，不是标注建议。

## 联合逻辑

一个对象的路径是：

`光学目标流 -> 目标状态/主辅观测 -> 24:50 软件同步时间窗 -> 方位弱映射 -> 距离向可用性检查 -> normal / relaxed / review-only / blocked`

- 直接传递的信息：`scene`、`object_hypothesis_id`、目标起止帧、主辅观测标记、状态类别、时间窗起止帧。
- 扩余量时起作用的信息：secondary、edge、partial、duplicate、handoff、ambiguity、软件同步抖动和时间换算取整余量。
- 分流时起作用的信息：稳定主连续目标进入 normal；有不确定性但仍可用的目标进入 relaxed；强 ambiguity/review-required 进入 review-only；short/noise、not-ready、缺目标流进入 blocked。
- 较窄先验来自稳定主观测且状态不复杂的对象；宽松先验来自仍可用但带 secondary/edge/handoff 的对象；review-only 来自强含混对象；blocked 来自 short/noise 或缺目标级输入。

## 可视化怎么读

- `overview_distribution.svg`：看每个场景 normal / relaxed / review-only / blocked 的数量，以及时间窗宽度分布。
- `weakness_decomposition.svg`：看时间、方位、距离、状态、几何五个维度的强弱分解。绿色/蓝色只表示诊断可用性，不是性能分数。
- `rule_influence.svg`：看规则如何把对象从目标流分到 normal、relaxed、review-only 或 blocked。
- 对象级样例图：展示单个对象从光学目标流到时间窗、再到空间先验类别的链条。

## 下一步最值得补强什么

优先补强**运行时安全的距离向几何**，例如可审计的场景级 range convention、目标级弱深度/尺度先验、或者不依赖 SAR 图像和真值的粗距离分层。其次再收紧方位向：把 bbox envelope、edge/partial 方向和多分量先验拆开，而不是继续把所有不确定性压成一个很宽的单区间。

本轮不建议直接进入 SAR 图像搜索。当前报告先把弱在哪里、为什么弱、哪些弱是设计保守性讲清楚，便于下一阶段决定补哪类运行时字段。

## 输出文件

- 本地全量输出目录：`D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_runtime_spatial_prior_visual_diagnosis_20260702_151419`
- 本地全量对象级图目录：`D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_runtime_spatial_prior_visual_diagnosis_20260702_151419\objects`
- 远端总览报告：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_visual_diagnosis_report_20260702_151419.md`
- 远端总览统计表：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_visual_summary_20260702_151419.csv`
- 远端精选 SVG 样例目录：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples`

## 输入来源

- runtime spatial priors: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_runtime_spatial_priors_20260702_144929.csv`
- runtime spatial prior summary: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_summary_20260702_144929.json`
- temporal window quality audit: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_quality_audit_20260702_142454.csv`

## Boundary Flags

| flag | value |
| --- | --- |
| `sar_image_content_used` | `false` |
| `sar_spatial_search_implemented` | `false` |
| `sar_search_region_generated` | `false` |
| `sar_candidate_boxes_generated` | `false` |
| `candidate_box_scoring_used` | `false` |
| `sar_gt_used` | `false` |
| `final_manual_oracle_review_runtime_fields_used` | `false` |
| `selector_or_ranking_used` | `false` |
| `annotation_proposal_entered` | `false` |
| `training_or_threshold_tuning_entered` | `false` |
| `identity_truth_claimed` | `false` |
| `detection_box_level_merge_reintroduced` | `false` |
| `spatial_prior_claimed_as_final_location` | `false` |
