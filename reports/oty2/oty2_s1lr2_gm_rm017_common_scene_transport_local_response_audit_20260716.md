# S1-LR2 GM_RM017 共同场景运输稳定化与车辆局部响应组织审计报告

日期：`2026-07-16`

英文名称：`S1-LR2 Common-Scene Transport Stabilization and Local Vehicle Response Organization Audit`

## 1. 最终摘要

本轮在 S1-L 内完成了共同场景运输、Raw/Smoothed GT 运动债务、背景稳定化、局部响应组织、匹配背景反事实和状态转移复核。

核心结果：

1. `330–350` 的主要图像运输可以由多背景相位观测的全局平移充分描述；累计横移 `124.096369 px`，与 Raw/Smoothed GT 累计横移 `126.336 px` 接近；
2. 全局平移在相位留出背景上的残差中位数 `0.526015 px`，仿射为 `1.099194 px`，更复杂模型没有给出值得复杂度升级的留出改善；
3. Raw-GT 单帧运动具有明显抖动，20 个相邻对中有 19 次标注来源家族切换；Raw 相对共同运输残差中位数 `4.729590 px`，不能再作为光流真值；
4. 稳定化后冻结粗走廊内 21/21 帧都有横向主响应，形成 `1938 px` 的保守持久核心；
5. 主带、上侧短段和端点热点的相对组织得到部分支持，但匹配背景可以复现若干单项形式，因此不能宣称完整车辆专属形态；
6. `339` 同时伴随多个背景区域的显示增益变化，不是已建立的车辆专属状态跃迁；`340–350` 的局部横向响应增强仍保留为部分证据；
7. 可见响应走廊仅为 `PARTIAL`，潜在完整车体、光学输入替换和 S1-D 均未就绪。

## 2. Git 与冻结输入审计

- 仓库：`D:/profile/research/optical-sar-visual-diagnosis-sar-foundation`
- 远端：`https://github.com/ccj-bot/optical-sar-visual-diagnosis.git`
- 分支：`feature/oty2-sar-gt-structure-foundation`
- 冻结起始 HEAD：`8eb4b99e3fefb41ba2449c5e53ea3b7338e8591b`
- 起始 upstream divergence：`0 0`
- 起始工作树：clean
- 既有 stash：`stash@{0}`，本轮未读取、未应用、未修改
- 解释器：`D:/MINICONDA/envs/py311/python.exe`
- `old_work` runtime dependency：none

冻结输入：

- `manifests/oty2/oty2_s1l_local_response_fields.csv`
- SHA256：`029d23d80638bfe2e115324140bfcccf9e4bb15ffeadf65f1920b244afa21092`
- 精确选择：`GM_RM017 / GM_RM017:PV002 / S0MV-GM_RM017-PV002-SEG02 / 330–350`
- 21/21 图像大小为 `2308×1334`
- 21/21 图像 SHA256 与 manifest 一致

没有使用车辆 GT 轨迹、车辆响应或 GT IoU 拟合背景运输模型。

## 3. 上一轮语义纠偏

旧报告保持冻结，新限定文档为：

`docs/OTY2_S1LR_PREVIOUS_CONCLUSION_SEMANTIC_CORRECTION_20260716.md`

正式限定：

```text
VEHICLE_MOTION_OWNERSHIP
= NOT_TESTABLE_BY_DIFFERENTIAL_BULK_TRANSLATION

MOTION_COHERENT_SUPPORT_CORRIDOR
= NOT_EVALUATED_BY_VALID_SUPPORT_CRITERION
```

静态车辆和静态背景本来就可以共享共同场景运输，因此 `vehicle residual < background residual` 不是当前序列的车辆所有权必要条件。旧规则不得直接重放到 PV003、PV004 或 GM_RM011。

## 4. Raw/Smoothed GT 运动债务

逐帧表：

`manifests/oty2/oty2_s1lr2_gm_rm017_gt_motion_debt.csv`

全窗口累计：

| 轨迹 | dx px | dy px |
|---|---:|---:|
| Raw-GT | 126.336000 | -6.368000 |
| Smoothed-GT | 126.336000 | -0.268000 |
| common transport | 124.096369 | -0.986924 |

局部平滑性：

| 指标 | Raw-GT | Smoothed-GT | common transport |
|---|---:|---:|---:|
| speed mean px/frame | 7.320726 | 6.534435 | 6.205976 |
| speed std px/frame | 3.868519 | 3.503773 | 0.166004 |
| acceleration mean px/frame² | 9.265435 | 6.561536 | — |
| acceleration median px/frame² | 9.046487 | 6.464700 | — |
| relative-to-transport residual median px | 4.729590 | 3.684596 | — |
| relative-to-transport residual p90 px | 8.234306 | 5.202038 | — |

标注来源在 `GM_RM017_ORIGINAL` 与 `GM17_SUPPLEMENT` 之间高度交替：20 个相邻对中 19 个发生来源家族切换。因为切换近乎与每个相邻对共线，本轮不能从统计上单独识别其因果贡献；但 Raw-y 抖动、Smoothed-y 改善和来源交替同时存在，必须保留为标注债务。

GT 三层结论：

- `GT_NEIGHBORHOOD_POSITION_REFERENCE=ALLOWED_DISCOVERY_AND_POSTHOC`
- `GT_FULL_WINDOW_TRAJECTORY_REFERENCE=ALLOWED_WITH_RAW_SMOOTHED_TRANSPORT_DEBT`
- `GT_ADJACENT_PHYSICAL_DISPLACEMENT_TRUTH=NOT_ESTABLISHED`

## 5. 背景锚点与共同运输模型

逐帧跟踪：

`manifests/oty2/oty2_s1lr2_gm_rm017_background_anchor_tracking.csv`

最终使用 8 个直接审阅锚点：6 个拟合、2 个留出。`168/168` 个 anchor-frame 身份均确认连续，算法切换嫌疑为 0。车辆发现壳层被固定排除在运输拟合之外。

模型比较：

`manifests/oty2/oty2_s1lr2_gm_rm017_transport_model_selection.csv`

| model | phase fit median/p90/max px | phase holdout median/p90/max px | complexity |
|---|---:|---:|---:|
| global translation | 0.549095 / 1.119117 / 1.439843 | 0.526015 / 1.819651 / 2.906023 | 2 |
| local affine | 0.447597 / 0.899189 / 1.211734 | 1.099194 / 2.042853 / 2.728537 | 6 |
| radial/tangential linear | 1.455488 / 5.272155 / 7.519877 | 14.826602 / 31.189432 / 39.060722 | 6 |
| sparse thin plate | 0.000009 / 0.000021 / 0.000029 | 1.462374 / 2.471172 / 3.727968 | 12 |

仿射虽然略降拟合残差，但留出中位数变差；稀疏薄板在拟合锚点近乎插值，却没有改善留出；径向/切向低阶场出现明显系统失配。因此最小充分模型冻结为：

```text
COMMON_SCENE_TRANSPORT_MODEL
= GLOBAL_TRANSLATION_FROM_MULTI_BACKGROUND_PHASE_MEDIAN
```

## 6. 稳定化与留出验证

留出表：

`manifests/oty2/oty2_s1lr2_gm_rm017_holdout_background_validation.csv`

| holdout | raw displacement median px | stabilized phase residual median/p90/max px | median reduction |
|---|---:|---:|---:|
| nearby non-vehicle curve | 62.410441 | 0.368339 / 0.632677 / 0.724816 | 99.32% |
| left arc branch | 62.446092 | 1.469039 / 2.359167 / 2.906023 | 97.95% |

两处独立留出背景均显著下降，满足“不能只对齐一个背景区域”的最低事实要求。

逐帧有效性：

`manifests/oty2/oty2_s1lr2_gm_rm017_stabilization_frame_quality.csv`

- valid fraction：最小 `0.945564`，平均 `0.972712`；
- 插值影响像素比例：平均 `0.473027`，主要反映亚像素平移；
- 线性与最近邻灰度绝对差：有效区平均 `1.512593` 灰度级；
- 有效 mask 和插值影响图没有在车辆尺度位置制造稳定横带。

大型视觉包：

`D:/profile/research/workspace/output/s1_lr2_gm_rm017_common_scene_transport_local_response_20260716_final_v2`

其中包含原始/稳定全帧与 ROI GIF、所有锚点前后 GIF、留出残差时序、有效 mask、插值影响图和直接审阅页。

## 7. 稳定化后的局部响应表达

本轮保留两类独立表达：

1. `manifests/oty2/oty2_s1lr2_gm_rm017_local_response_components.csv`：robust-z 连通片段，共 9118 条，保留中心、长度、宽度、方向、面积和强度；
2. `manifests/oty2/oty2_s1lr2_gm_rm017_direction_fragments.csv`：局部方向片段，共 242 条，不生成 embedding 或排序。

关系表：

`manifests/oty2/oty2_s1lr2_gm_rm017_local_response_relations.csv`

冻结粗走廊中：

- 主横带存在：`21/21`；
- 主带相对 y 均值 `1.072246 px`，标准差 `2.638083 px`；
- 上侧结构到主带的 dy 均值 `-16.782514 px`，标准差 `3.595752 px`；
- 左右端热点关系均在 `21/21` 帧被片段规则记录；
- LSD 方向片段中，弱阶段横向比例 `84.91%`，强阶段 `91.53%`。

保守持久图：

`manifests/oty2/oty2_s1lr2_gm_rm017_visible_response_support_regions.csv`

| class | pixels | expanded-patch fraction |
|---|---:|---:|
| persistent local response core | 1938 | 1.2423% |
| intermittent local response region | 5026 | 3.2218% |
| background structure | 3338 | 2.1397% |
| mixed or unresolved | 5566 | 3.5679% |

该结果支持可见横向核心，但大量间歇与未解析区域仍存在；没有把暗区改写为潜在完整车体。

## 8. 匹配背景反事实

阶段汇总：

`manifests/oty2/oty2_s1lr2_gm_rm017_matched_background_counterfactuals.csv`

三个控制窗口与粗走廊严格不重叠，使用相同稳定化、插值、窗口大小、robust-z、片段和关系规则。

### 8.1 右侧复杂结构控制

该控制在动态范围和结构复杂度上最接近目标：弱阶段背景中位数 `38.333` 对目标 `38.333`，MAD `3.556` 对 `3.444`，edge density `0.878` 对 `0.860`；强阶段也接近。

但它只在弱阶段 `33.3%`、强阶段 `9.1%` 的帧复现主横带关系，`339` 为 0，不能复现目标的 21/21 持续组织。

### 8.2 左侧弯曲结构控制

弱阶段和 `339` 均未形成车辆尺度主带；强阶段仅 `27.3%` 帧形成较短横带，不能复现完整窗口持续性。

### 8.3 扇形弧控制

扇形弧能在 21/21 帧形成“横带+热点”的形式，说明单条强线、端点热点或笼统多部件关系不是车辆专属证据。但其相对几何明显不同且更不稳定：

- 主带相对 y：目标均值 `1.072 px`、std `2.638 px`；扇形弧均值 `30.698 px`、std `11.341 px`；
- upper-to-main dy：目标均值 `-16.783 px`、std `3.596 px`；扇形弧均值 `-44.026 px`、std `26.334 px`；
- 目标正响应比例约 `0.082–0.097`，扇形弧约 `0.022–0.026`。

没有一个控制同时复现目标的持续横带、较稳定局部 y、稳定 upper-to-main 间隔、动态范围与时间演化。但由于匹配仍不可能在所有空间属性上完全等价，正式结论保持 `PARTIAL`，不宣称车辆唯一形态。

## 9. 状态转移复核

冻结分组仍为 `330–338 / 339 / 340–350`，但结论被修正。

目标粗走廊：

| stage | main-band present | span median px | main-band robust-z median | positive fraction mean |
|---|---:|---:|---:|---:|
| 330–338 | 1.0 | 159 | 5.895786 | 0.082101 |
| 339 | 1.0 | 223 | 5.375335 | 0.092311 |
| 340–350 | 1.0 | 163 | 6.253750 | 0.096689 |

`339` 的主带 span 变大，但 robust-z 没有同步提升；同一帧多个背景区域的中位灰度和 edge density 也上升。稳定化排除了“竖直强线逐渐进入窗口”作为主要解释，但不能排除全场成像/显示增益变化。

因此：

```text
RESPONSE_STATE_TRANSITION_AFTER_STABILIZATION
= PARTIAL_339_NOT_VEHICLE_SPECIFIC_POST340_STRENGTHENING_REMAINS
```

不升级为 `LOCAL_VEHICLE_RESPONSE_STATE_TRANSITION_SUPPORTED`。

## 10. 分层结论

正式表：

`manifests/oty2/oty2_s1lr2_gm_rm017_stage_conclusions.csv`

- `COMMON_SCENE_TRANSPORT_MODEL=SUPPORTED_GLOBAL_TRANSLATION_PHASE_MULTI_BACKGROUND_MINIMUM_SUFFICIENT`
- `BACKGROUND_STABILIZATION_QUALITY=SUPPORTED_MULTI_HOLDOUT_RESIDUAL_REDUCTION`
- `RAW_GT_ADJACENT_MOTION_RELIABILITY=NOT_RELIABLE_AS_PHYSICAL_DISPLACEMENT_TRUTH`
- `LOCAL_HORIZONTAL_RESPONSE_CORE=SUPPORTED_STABILIZED_PERSISTENT_HORIZONTAL_CORE`
- `LOCAL_MULTI_PART_RESPONSE_ORGANIZATION=PARTIAL_STABLE_MAIN_UPPER_RELATION_ENDPOINTS_NOT_UNIQUE`
- `VEHICLE_VS_MATCHED_BACKGROUND_RELATION_SET=PARTIAL_NO_SINGLE_CONTROL_REPRODUCES_COMPLETE_RELATION_SET`
- `RESPONSE_STATE_TRANSITION_AFTER_STABILIZATION=PARTIAL_339_NOT_VEHICLE_SPECIFIC_POST340_STRENGTHENING_REMAINS`
- `VISIBLE_RESPONSE_SUPPORT_CORRIDOR=PARTIAL_PERSISTENT_CORE_WITH_INTERMITTENT_AND_MIXED_REGIONS`
- `FULL_BODY_SUPPORT_READINESS=NOT_READY`
- `OPTICAL_INPUT_REPLACEMENT_READINESS=NOT_READY`
- `S1D_READINESS=NOT_READY`

语义纠偏同时保持：

- `VEHICLE_MOTION_OWNERSHIP=NOT_TESTABLE_BY_DIFFERENTIAL_BULK_TRANSLATION`
- `MOTION_COHERENT_SUPPORT_CORRIDOR=NOT_EVALUATED_BY_VALID_SUPPORT_CRITERION`

## 11. 禁止项与后续边界

本轮没有：

- 进入 S1-D；
- 生成最终框、唯一中心、候选库、selector 或 ranking；
- 使用加权综合分数；
- 使用 GT IoU 选参；
- 修改 GT；
- 把 GT 框内外作为像素标签；
- 恢复潜在完整车体；
- 自动标注或训练模型；
- 为制造 PASS 调阈值；
- 扩展到 PV003、PV004 或 GM_RM011。

若后续要重放，必须重新冻结目标窗口的背景锚点和匹配背景，使用本轮稳定化后关系协议；不得重放旧 S1-LR 的差异平移 corridor 规则。
