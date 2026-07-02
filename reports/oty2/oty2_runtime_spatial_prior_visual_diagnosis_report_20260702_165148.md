# OTY2 对象级弱空间先验可视化诊断报告

生成时间：`20260702_165148`

本轮修正了上一版偏流程图的问题：现在每个样例页都以**真实光学帧 + 主/辅目标框 + 雷达时间轴 + 空间先验示意**为核心。图内文字以中文解释为主，英文只保留必要字段名。

## 这轮图画了什么

- 本地全量对象页：`28` 张。
- 远端精选样例页：`5` 张，放在 `reports/oty2/samples/visualizations/`。
- 每个对象页至少展示起始/中间/结束三个光学帧位置；能找到本地光学帧时直接嵌入真实帧并画主观测框。
- 有辅助观测的帧使用橙色虚线框标出，并在说明区写出它如何扩大时间窗和方位余量。
- SAR 侧没有读取真实 SAR 图，只画时间轴、帧窗口和“方位弱约束 + 距离向宽未知”的示意画布。

## 当前弱空间先验主要弱在哪里

最主要的弱点仍然是**距离向**。当前可进入 normal / relaxed / review-only 的对象都有时间窗，也大多有方位弱先验；但距离向仍是 `broad_unknown_range_prior`，因为当前 OTY2 输入里没有运行时安全的 per-object range/depth 几何字段。

- 方位向：有弱约束，来自光学 bbox / bbox envelope 与配置几何映射；edge、partial、secondary、handoff 会扩大它。
- 距离向：最弱，当前没有可审计的目标级距离收敛信息，所以不能画真实距离位置。
- 目标状态：决定正常、宽松、仅审阅或阻断。它不是评分器，也不是身份真值。
- 时间窗：只限制“何时看雷达”，不直接提供“在哪里找”。
- 场景几何：当前主要起作用的是光学 x 到方位角的弱映射；距离向几何还没真正进入运行时安全输入。

## 每个输入部件的作用

- 主观测：提供对象级连续框，是正常空间先验的核心输入。
- 辅助观测：不证明身份真值；用于暴露 partial / duplicate / handoff / 多观测不确定性，并扩大时间窗或方位余量。
- edge / partial / duplicate / handoff：不直接阻断，优先扩大或放松先验。
- ambiguous / review-only：不混入正常下游输入，只作为审阅上下文。
- short / noise / not-ready：阻断正常空间先验。
- 时间窗：由 24 fps 光学帧与 50 fps 雷达帧的软件同步换算得到，保留抖动和状态余量。
- 场景几何：当前只支持弱方位解释；不足以生成真实 SAR 空间位置。

## 场景统计

| scene | 正常 | 宽松 | 仅审阅 | 阻断 |
| --- | ---: | ---: | ---: | ---: |
| `GM_RM011` | 0 | 0 | 0 | 1 |
| `GM_RM017` | 2 | 3 | 1 | 0 |
| `GM_RM019` | 2 | 4 | 6 | 9 |

## 远端代表样例

| 样例 | scene | object | 状态 | 文件 |
| --- | --- | --- | --- | --- |
| 第十一场景说明 | `GM_RM011` | `scene-only` | 阻断：缺目标流 | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\visualizations\oty2_object_diag_gmrm011_no_object_flow_gm_rm011_sceneonly_20260702_165148.png` |
| 稳定正常空间先验 | `GM_RM017` | `oty1t_obj_GM_RM017_bytetrack_bt_0002` | 正常 | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\visualizations\oty2_object_diag_normal_stable_gm_rm017_bt0002_20260702_165148.png` |
| 阻断对象 | `GM_RM019` | `oty1t_obj_GM_RM019_bytetrack_bt_0009` | 阻断 | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\visualizations\oty2_object_diag_blocked_object_gm_rm019_bt0009_20260702_165148.png` |
| 宽松空间先验 | `GM_RM019` | `oty1t_obj_GM_RM019_bytetrack_bt_0042` | 宽松 | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\visualizations\oty2_object_diag_relaxed_uncertain_gm_rm019_bt0042_20260702_165148.png` |
| 仅审阅空间上下文 | `GM_RM019` | `oty1t_obj_GM_RM019_bytetrack_bt_0053` | 仅审阅 | `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\visualizations\oty2_object_diag_review_only_gm_rm019_bt0053_20260702_165148.png` |

## 哪些对象可以继续往下走

- 可以继续作为下游正常输入：`正常` 和 `宽松` 对象。宽松对象必须携带不确定性说明，不能被当成精确位置。
- 只能审阅：`仅审阅` 对象。它们可作为人工诊断上下文，不进入 normal downstream。
- 被阻断：`阻断` 或 `阻断：缺目标流`。`GM_RM011` 只有时间元数据可用，缺光学目标流，不能生成对象级映射。

## 字段不足与替代图

缺字段：

- 运行时安全的目标级距离/深度字段。
- 能把光学对象转换为 SAR 距离向约束的可审计几何。
- 对 `GM_RM011`，缺目标级光学对象流。

因此不能画：

- 真实 SAR 空间位置。
- SAR 搜索区域。
- SAR 候选框或自动标注。

暂时替代：

- 真实光学帧 + 主/辅框。
- 雷达时间轴 + 当前目标 SAR 帧窗口。
- 方位弱先验示意。
- 距离向 `broad_unknown_range_prior` 的显式说明。

## 下一步建议

优先补强运行时安全的距离向信息：例如场景级 range convention、目标级弱深度/尺度先验、或不依赖 SAR 图像/真值的粗距离分层。第二优先级是把当前单一方位包络拆成多分量或方向性先验，尤其针对 edge / partial / duplicate / handoff 对象。

## 输入来源

- runtime spatial priors: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_runtime_spatial_priors_20260702_144929.csv`
- temporal windows: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- temporal quality audit: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_quality_audit_20260702_142454.csv`
- object state stream: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- optical frames: `manifests\oty0_yolo_manifest.csv`

## 输出

- 本地全量目录：`D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_runtime_spatial_prior_visual_diagnosis_20260702_165148`
- 本地对象页目录：`D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_runtime_spatial_prior_visual_diagnosis_20260702_165148\object_pages`
- 本地中文报告：`D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_runtime_spatial_prior_visual_diagnosis_20260702_165148\object_visual_diagnosis_report.md`
- 远端报告：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_visual_diagnosis_report_20260702_165148.md`
- 远端汇总表：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_runtime_spatial_prior_visual_summary_20260702_165148.csv`
- 远端样例目录：`D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\visualizations`

## Boundary Flags

- sar_image_content_used: `false`
- sar_spatial_search_implemented: `false`
- sar_search_region_generated: `false`
- sar_candidate_boxes_generated: `false`
- candidate_box_scoring_used: `false`
- sar_gt_used: `false`
- final_manual_oracle_review_runtime_fields_used: `false`
- selector_or_ranking_used: `false`
- annotation_proposal_entered: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- detection_box_level_merge_reintroduced: `false`
- spatial_prior_claimed_as_final_location: `false`
