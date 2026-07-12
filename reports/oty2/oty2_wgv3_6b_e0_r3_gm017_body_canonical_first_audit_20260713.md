# WGV3.6B-E0-R3 GM_RM017 Body-Canonical First Audit

## 结论

- 核心回答：`当前证据不足`。
- 近侧定位：`部分支持`，仅限代表窗口的 body-canonical 可视化。
- 同车结构动力学：`部分支持`，存在可审阅的峰位、增益/损失和碎裂度变化，但只是最小窗口。
- aspect 因果：`当前不可评价`，`ASPECT_CAUSAL_IDENTIFIABILITY=NOT_READY`。
- 超越配准误差：`当前证据不足`，扰动审计显示部分差异对小扰动敏感。
- 超越背景反事实：`当前证据不足`，GT-attached corridor 仍有 contamination/overlap 风险。

## 研究问题与证据链复位

E0-R2 实际建立的是同一 GM_RM017 线程上 relative aspect、若干响应描述符和若干背景对照之间的探索性关系。它证明了这些表可以在冻结分段和同一后验 GT 线程上复现，但没有证明车体结构响应场已经被识别，也没有证明 aspect 是独立因果变量。

E0-R2 没有验证 `A_t(u,v)`：它主要处理逐帧描述符和 `response_index`，而逐帧向量会丢失高能区在车体长轴、短轴、近侧边界和端部之间的空间迁移。车辆身份也不能只用来组织样本；同一物理车辆身份必须提供一个可对齐的车体坐标系，否则响应的滑动、切换、分裂和合并无法区分于坐标翻转或配准抖动。

本轮因此把问题改写为冻结 GT 中心、冻结车体轴代理和冻结 L/W 支撑下的 `A_t(u,v)` 审计。可以继承的是同车中心序列、轴向语义、L/W 图像网格支撑、SAR fan center 和旧 hard-negative 压力；必须撤回或降级的是 E0-R1 零混淆、E0-R2 range confounder rejection、`response_index` 证据地位、same-aspect repeatability、整体 corridor 排除和 motion tangent yaw。当前仍不可识别的是 aspect 独立因果、完整输运、背景反事实排除和跨车辆机制。

## 旧结论撤回与降级表

| item | E0-R3 status | reason |
| --- | --- | --- |
| `multi_gate_physical_confusions=0` | `WITHDRAWN` | 旧 G10 使用 `is_vehicle`，零混淆由定义保证。 |
| `RANGE_CONFOUNDER_REJECTED` | `WITHDRAWN` | E0-R2 range 相对图像左上角，本轮改为 fan center。 |
| `response_index` | `EXPLORATORY_ONLY` | 9 个标准化描述符等权平均，不再作为 Gate 或机制证据。 |
| same-aspect repeatability | `NOT_EVALUABLE_NO_DIFFERENT_ASPECT_MATCHED_PAIRS` | E0-R2 `different_pairs=0`。 |
| corridor 排除 | `DOWNGRADED` | sign、offset、GT-overlap risk 未能合并排除。 |
| 运动切线 yaw | `AXIAL_PROXY_ONLY` | 只用于 180 度配准连续性，不是真实 yaw。 |
| aspect CI / E0-R2 多视角机制 | `NOT_READY` | 诊断域、时间/随机对照和 pair family 未闭合。 |

## 距离原点纠偏

- fan center: `(1154, 1330.6)`
- frames: `71`
- corrected range min/max: `11.543042` / `15.987922` m
- corrected over 40 m: `0`
- old over 40 m: `56`
- failure ledger count: `7`
- Gate: `PASS`

## aspect/range/time 可识别性

- 相近距离不同 aspect 对数: `83`
- 相近 aspect 不同距离对数: `4`
- 非相邻相似 aspect 对数: `184`
- 不同 aspect 相近距离对数: `279`
- aspect-time Spearman: `0.741615`
- aspect-range Spearman: `-0.982854`
- `ASPECT_CAUSAL_IDENTIFIABILITY=NOT_READY`

## 车体规范坐标审计

- same-vehicle frames: `71`
- selected usable vehicle maps: `14`
- axis continuity failures: `1`
- 180 deg handling: choose `theta` or `theta+180` by minimal directed residual to the previous reliable frame.
- canonical core grid: `128x64`; canvas `160x96`
- L/W: `4.764934 m / 2.077648 m` image-grid support.
- interpolation: bilinear intensity sampling; invalid pixels filled with 0 and tracked by valid mask.
- min valid support fraction: `1`
- median near-side boundary energy fraction: `0.114906`

## 实际视觉审阅入口

- `raw_time_contact_sheet`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_canonical_raw_time_contact_sheet.png`
- `norm_time_contact_sheet`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_canonical_norm_time_contact_sheet.png`
- `overlay_contact_sheet`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_canonical_overlay_contact_sheet.png`
- `E_t_s_heatmap`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_E_t_s_heatmap.png`
- `s_peak_time`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_s_peak_time.png`
- `s_peak_aspect`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_s_peak_aspect.png`

代表窗口见 visual casebook；摘要如下：

- `W_STABLE SAR 339-341`: 雷达近侧在规范图下侧偏 body_long_positive 端。339 和 341 的主响应贴近下侧近侧边界，340 仍在同一端部但更偏短轴中段；空间位置基本稳定。339->340 的差分呈整条下侧带红蓝互换，说明幅值变化可能受 1 px 级中心或轴向配准影响，不应作为输运证据。
- `W_SLIDE SAR 321-325`: 雷达近侧持续落在下侧斜向边界，主响应始终在 body_long_positive 端和近侧长边交界。321 到 323 的峰位向近侧中段回撤，323 到 325 又回到更靠右下端，表现为局部增强和回跳，而不是单调沿边界滑动。该窗口可作为候选结构动力学案例，但不能单独支持 aspect 驱动。
- `W_SWITCH SAR 351-353`: 近侧方向仍指向下侧，强响应从 351 的近侧长边带扩展到 352 的右下端部集中区，353 又出现右侧短轴侧强点。这里更像端部与近侧长边之间的主响应接管/再分配，而不是旧峰连续平移；可进入后续人工复核，但需要配准扰动和背景对照约束。
- `W_SPLIT SAR 384-386`: 雷达近侧翻到规范图下侧偏 body_long_negative 端，384-386 的下侧高能带仍存在，但左上背景强散射和底边强带同时显著。384->385 的 gain/loss 峰距很大且差分像整体形变，分裂/合并只能记为疑似事件，不能进入物理支持。
- `W_DIFFICULT SAR 386-388`: 386/387 仍有下侧近侧高能带，388 的主峰转到 body_middle 附近，axis reliability 为 LOW，并伴随上方和左侧孤立强点。该段适合记录失败模式，不适合进入输运或 aspect 因果分析。
- `Registration perturbation`: 已打开 registration perturbation contact sheet。1 px 中心平移、2 deg 轴扰动和 2% 尺度扰动都能在同一高能带附近制造红蓝交错差分；轴旋转和尺度扰动尤其呈全图放射或条带变化。因此滑动、切换和分裂候选必须标记 registration-sensitive。
- `Counterfactual SAR 352`: N005 和 fixed strong scatterer 在同一规范流程下也产生局部高能结构，其中 fixed strong 的 near-side fraction 高于车辆若干帧的远侧基线。GT-attached corridor 的强响应贴近下侧车辆高能带且为 overlap-risk corridor，不能用于拒绝背景解释。
- `E_t(s) and s_peak plots`: E_t(s) 热图和 s_peak 图显示峰位跳动和回跳，不是平滑单调迁移；321-325 与 384-388 都不满足独立 aspect 因果闭合。

逐帧指标入口如下：

- `W_STABLE` SAR `339`: near direction `(0.46781,0.883829)`, main `near_boundary;body_long_positive_end;body_short_positive_side;pixel=(130,69)`, s_peak `0.419355`, registration `HIGH`, review role `stable_review`.
- `W_STABLE` SAR `340`: near direction `(0.462508,0.886615)`, main `near_half;body_long_positive_end;short_axis_middle;pixel=(130,65)`, s_peak `0.419355`, registration `HIGH`, review role `stable_review`.
- `W_STABLE` SAR `341`: near direction `(0.46757,0.883956)`, main `near_boundary;body_long_positive_end;body_short_positive_side;pixel=(132,69)`, s_peak `0.387097`, registration `HIGH`, review role `stable_review`.
- `W_SLIDE` SAR `321`: near direction `(0.674362,0.738401)`, main `near_boundary;body_long_positive_end;short_axis_middle;pixel=(132,65)`, s_peak `0.451613`, registration `HIGH`, review role `near_side_sliding_review`.
- `W_SLIDE` SAR `323`: near direction `(0.647599,0.761981)`, main `near_boundary;body_long_positive_end;body_short_positive_side;pixel=(133,67)`, s_peak `0.322581`, registration `HIGH`, review role `near_side_sliding_review`.
- `W_SLIDE` SAR `325`: near direction `(0.614332,0.789048)`, main `near_boundary;body_long_positive_end;body_short_positive_side;pixel=(129,72)`, s_peak `0.548387`, registration `HIGH`, review role `near_side_sliding_review`.
- `W_SWITCH` SAR `351`: near direction `(0.356789,0.934185)`, main `near_boundary;body_long_positive_end;body_short_positive_side;pixel=(131,69)`, s_peak `0.290323`, registration `HIGH`, review role `switching_review`.
- `W_SWITCH` SAR `352`: near direction `(0.332565,0.94308)`, main `near_half;body_long_positive_end;short_axis_middle;pixel=(128,65)`, s_peak `0.451613`, registration `HIGH`, review role `switching_review`.
- `W_SWITCH` SAR `353`: near direction `(0.312524,0.94991)`, main `near_boundary;body_long_positive_end;body_short_positive_side;pixel=(126,69)`, s_peak `0.387097`, registration `HIGH`, review role `switching_review`.
- `W_SPLIT` SAR `384`: near direction `(-0.239448,0.970909)`, main `near_boundary;body_long_negative_end;body_short_positive_side;pixel=(36,75)`, s_peak `0.612903`, registration `MEDIUM`, review role `split_merge_review`.
- `W_SPLIT` SAR `385`: near direction `(-0.285011,0.958524)`, main `near_boundary;body_long_negative_end;body_short_positive_side;pixel=(33,76)`, s_peak `0.83871`, registration `MEDIUM`, review role `split_merge_review`.
- `W_SPLIT` SAR `386`: near direction `(-0.276452,0.961028)`, main `near_boundary;body_long_negative_end;body_short_positive_side;pixel=(38,77)`, s_peak `0.516129`, registration `MEDIUM`, review role `split_merge_review`.
- `W_DIFFICULT` SAR `386`: near direction `(-0.276452,0.961028)`, main `near_boundary;body_long_negative_end;body_short_positive_side;pixel=(38,77)`, s_peak `0.516129`, registration `MEDIUM`, review role `registration_mask_boundary_review`.
- `W_DIFFICULT` SAR `387`: near direction `(-0.275353,0.961343)`, main `near_boundary;body_long_negative_end;body_short_positive_side;pixel=(24,73)`, s_peak `0.516129`, registration `MEDIUM`, review role `registration_mask_boundary_review`.
- `W_DIFFICULT` SAR `388`: near direction `(-0.304321,0.952569)`, main `near_half;body_middle;body_short_positive_side;pixel=(100,74)`, s_peak `0.387097`, registration `LOW`, review role `registration_mask_boundary_review`.

## 反事实初步结果

- `fixed_known_non_vehicle_N005`: status `COUNTERFACTUAL_REVIEWABLE`, near fraction `0.063724`, location `near_half;body_middle;short_axis_middle;pixel=(68,48)`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\fixed_known_non_vehicle_N005_sar000352_overlay.png`.
- `fixed_strong_scatterer`: status `COUNTERFACTUAL_REVIEWABLE`, near fraction `0.154557`, location `near_half;body_middle;short_axis_middle;pixel=(63,60)`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\fixed_strong_scatterer_sar000352_overlay.png`.
- `gt_attached_corridor_body_short`: status `COUNTERFACTUAL_CONTAMINATED_BY_GT`, near fraction `0.062867`, location `near_boundary;body_long_positive_end;body_short_positive_side;pixel=(135,70)`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\gt_attached_corridor_body_short_sar000352_overlay.png`.

## Gate 状态表

| gate | status | evidence | failure | next |
| --- | --- | --- | --- | --- |
| `REPOSITORY_LINEAGE_VERIFIED` | `PASS` | branch=feature/oty2-gm017-physical-factor-discovery;ancestor=7a9d9cba9f38447e10c917227a789f4160569026 |  | yes |
| `REQUIRED_FROZEN_ARTIFACTS_READ` | `PASS` | inventory_rows=28 |  | yes |
| `LEGACY_CONCLUSIONS_WITHDRAWN` | `PASS` | zero-confusion and range-confounder support withdrawn; response_index exploratory only |  | yes |
| `METRIC_RANGE_ORIGIN_CORRECTED` | `PASS` | range_m=hypot(cx-fan_center_x,cy-fan_center_y)*0.03 |  | yes |
| `CORRECTED_RANGE_WITHIN_IMAGING_DOMAIN` | `PASS` | corrected_over40=0;legacy_over40=56 |  | yes |
| `ASPECT_RANGE_TIME_IDENTIFIABILITY_AUDITED` | `PASS` | summary_rows=7 |  | yes |
| `ASPECT_CAUSAL_IDENTIFIABILITY` | `NOT_READY` | usable_pairs_exist_but_independent_control_family_or_collinearity_gate_not_closed | independent controls not closed | no |
| `BODY_AXIS_SIGN_CONTINUITY_VALID` | `FAIL` | axis_fail_count=1 | axis flip/low reliability | no |
| `BODY_CANONICAL_INPUTS_SUFFICIENT` | `PASS` | vehicle_maps=14;L/W=4.764934/2.077648 |  | yes |
| `BODY_CANONICAL_FIELD_VALID` | `PASS` | min_valid_support_fraction=1 |  | yes |
| `NEAR_SIDE_RESPONSE_LOCALIZATION_VISUALLY_AUDITED` | `PARTIAL` | median_near_boundary_fraction=0.114906;requires manual visual review | not a supported mechanism claim | limited |
| `MINIMAL_STRUCTURAL_TIMELINE_VISUALLY_AUDITED` | `PARTIAL` | review_windows=5 | minimal windows only | limited |
| `REGISTRATION_FAILURE_MODES_AUDITED` | `PARTIAL` | visible_perturbation_cases=16 | some structure may be registration-sensitive | limited |
| `MINIMAL_COUNTERFACTUAL_STRUCTURAL_AUDIT_COMPLETED` | `PARTIAL` | counterfactual_rows=3 | GT-attached corridor contamination blocks rejection | limited |
| `NEAR_SIDE_RESPONSE_MIGRATION_SUPPORTED` | `NOT_READY` | minimal visual audit only | no full transport closure | no |
| `RESPONSE_TRANSPORT_BEYOND_REGISTRATION_SUPPORTED` | `NOT_READY` | perturbation audit is sensitivity only | transport beyond registration not established | no |
| `ASPECT_EFFECT_BEYOND_RANGE_AND_TIME_SUPPORTED` | `NOT_READY` | ASPECT_CAUSAL_IDENTIFIABILITY not closed | range/time controls not sufficient for causality | no |
| `GT_ATTACHED_CORRIDOR_STRUCTURAL_COUNTERFACTUAL_REJECTED` | `NOT_READY` | corridor rows retain overlap-risk separation | contaminated corridors cannot reject background | no |
| `PERSISTENT_STRONG_STRUCTURAL_COUNTERFACTUAL_REJECTED` | `NOT_READY` | fixed/persistent strong rendered only as minimal counterfactual | visual parity not enough for rejection | no |
| `VEHICLE_BODY_STRUCTURAL_DYNAMICS_SUPPORTED` | `PARTIAL` | minimal selected windows show reviewable structure indices | not full sequence support | limited |
| `E0_R3_PHYSICAL_MECHANISM_SUPPORTED` | `NOT_READY` | requires near-side, dynamics, aspect causality, registration, and counterfactual closure | not closed in first audit | no |

## 对核心问题的当前回答

`当前证据不足`。近侧定位在最小窗口中有部分可见证据，同车结构动力学也有可审阅的峰位和差分变化；但 aspect 因果不可识别，配准扰动和背景反事实尚未排除。因此不能回答为当前支持，也不能把 E0-R3 物理机制提升为 supported。

## 下一步建议

下一阶段只做一个受控扩展：在当前 E0-R3 规范场基础上补充一个真正低 GT-overlap 风险的 corridor 或固定背景窗口，并对相同代表窗口做人工复核后再决定是否扩大到更长序列。
