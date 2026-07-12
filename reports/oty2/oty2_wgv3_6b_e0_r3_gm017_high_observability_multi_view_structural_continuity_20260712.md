# WGV3.6B-E0-R3 GM_RM017 高可观测同车多视角结构连续性与动态区间收缩审计

## 结论

- `E0_R3_TOTAL_STATUS`: `E0_R3_PARTIAL`
- `VEHICLE_YAW_READINESS`: `NOT_READY`
- 本轮没有生成 final box、没有修改 GT、没有构造 selector/ranking、没有修改 GM_RM019 静态线。

## 锚点段

- A 类锚点段: `1`；B 类保留段: `1`；C 类压力/域外段: `1`。
- `A001`: SAR `315-360`, frames `37`, range change `4.129468` m, azimuth change `32.396214` deg, aspect span `35.868228` deg, status `ANCHOR_SEGMENT_READY`.
- `B001`: SAR `361-370`, frames `10`, range change `0.220393` m, azimuth change `8.781618` deg, aspect span `5.592755` deg, status `RESERVED_FOR_MASK_TRANSITION_NEXT_STAGE`.
- `C001`: SAR `371-394`, frames `24`, range change `0.961625` m, azimuth change `20.935711` deg, aspect span `18.756001` deg, status `STRESS_OR_OUT_OF_DOMAIN_ONLY`.

## 结构响应

- 结构化 SAR 帧数: `71`；显著匿名分量帧均值: `6.028169`。
- 分量事件计数: `{'COMPONENT_CONTINUED': 119, 'COMPONENT_SPLIT': 486, 'COMPONENT_MERGE': 478, 'COMPONENT_APPEARED': 98, 'COMPONENT_DISAPPEARED': 104}`。
- 高能 body-long 质心滑动范围: `1.171872` m。
- 峰值 body-long 位置滑动范围: `4.102221` m。
- near/far 能量比范围: `0.989928` 到 `1.383807`。

## 配对与区间

- same-aspect matched pairs: `160`；different-aspect matched pairs: `160`。
- same median structural distance: `1.077615`；different median structural distance: `1.028024`。
- median causal contraction ratio: `0.831406`；median smoothed contraction ratio: `0.776198`。

## 因素状态

| factor | status | evidence |
| --- | --- | --- |
| HIGH_OBSERVABILITY_ANCHOR_SEGMENTS | SUPPORTED | A_ready=1;segments=3 |
| POSITION_CONTINUITY_STATUS | SUPPORTED | adjacent_pairs=70 |
| ASPECT_OBSERVABILITY_STATUS | PARTIAL | diagnosis contains OUT_OF_CALIBRATION_ASPECT_DOMAIN; calibration usable for discovery |
| VEHICLE_ENVELOPE_STABILITY_STATUS | SUPPORTED | stable=68;total=71 |
| PROJECTED_SUPPORT_CONTINUITY_STATUS | SUPPORTED | classes={'STRUCTURAL_SPLIT_OR_MERGE': 59, 'ABRUPT_UNEXPLAINED_JUMP': 7, 'SMOOTH_GRADUAL_CHANGE': 2, 'PIECEWISE_GRADUAL_CHANGE': 2} |
| HIGH_ENERGY_SLIDING_STATUS | SUPPORTED | classes={'STRUCTURAL_SPLIT_OR_MERGE': 59, 'ABRUPT_UNEXPLAINED_JUMP': 7, 'SMOOTH_GRADUAL_CHANGE': 2, 'PIECEWISE_GRADUAL_CHANGE': 2} |
| NEAR_FAR_REDISTRIBUTION_STATUS | PARTIAL | near/far ratio measured per frame; not front/rear semantics |
| COMPONENT_STRUCTURE_CONTINUITY_STATUS | SUPPORTED | classes={'STRUCTURAL_SPLIT_OR_MERGE': 59, 'ABRUPT_UNEXPLAINED_JUMP': 7, 'SMOOTH_GRADUAL_CHANGE': 2, 'PIECEWISE_GRADUAL_CHANGE': 2} |
| SAME_ASPECT_REPEATABILITY_STATUS | PARTIAL | same_pairs=160;different_pairs=160;same_median=1.077615;diff_median=1.028024 |
| RANGE_CONFOUNDER_STATUS | PARTIAL | different-aspect similar-range controls exist but are sparse under 2.0m preregistered window |
| TIME_CONFOUNDER_STATUS | PARTIAL | time reversal control reported |
| BACKGROUND_COUNTERFACTUAL_STATUS | SUPPORTED | causal_background_rejections=358 |
| DYNAMIC_INTERVAL_CONTRACTION_STATUS | SUPPORTED | median_causal_ratio=0.831406;median_smoothed_ratio=0.776198;causal_contained=71/71 |
| MASK_TRANSITION_READINESS | PARTIAL | B segment is reserved; no full MASK-transition proof in E0-R3 |
| VEHICLE_YAW_READINESS | NOT_READY | body-axis proxy and SAR response axes remain separated; true yaw is not recovered |
| E0_R3_TOTAL_STATUS | E0_R3_PARTIAL | factor-level result; no weighted score |

## Failure Ledger

| failure | severity | evidence | interpretation |
| --- | --- | --- | --- |
| E0_R2_RESPONSE_INDEX_WITHDRAWN | high | E0-R3 does not use response_index, total_response_score, weighted_response_score, or multi_aspect_score. | Mechanism evidence is reported factor by factor. |
| DIAGNOSIS_OUT_OF_CALIBRATION_DOMAIN_NOT_UPGRADED | medium | Diagnosis frames are explicitly marked IN/OUT of calibration aspect domain. | Out-of-domain success is not mechanism support and out-of-domain failure is not a counterexample. |
| SAME_ASPECT_REPEATABILITY_SPARSE_DIFFERENT_CONTROL | medium | same_pairs=160;different_pairs=160 under preregistered 2.0m similar-range window. | Repeatability can be inspected but remains weaker than dense matched controls. |
| ASPECT_OBSERVABILITY_STATUS_LIMIT | medium | diagnosis contains OUT_OF_CALIBRATION_ASPECT_DOMAIN; calibration usable for discovery | Factor does not close a full physical-mechanism proof. |
| NEAR_FAR_REDISTRIBUTION_STATUS_LIMIT | medium | near/far ratio measured per frame; not front/rear semantics | Factor does not close a full physical-mechanism proof. |
| SAME_ASPECT_REPEATABILITY_STATUS_LIMIT | medium | same_pairs=160;different_pairs=160;same_median=1.077615;diff_median=1.028024 | Factor does not close a full physical-mechanism proof. |
| RANGE_CONFOUNDER_STATUS_LIMIT | medium | different-aspect similar-range controls exist but are sparse under 2.0m preregistered window | Factor does not close a full physical-mechanism proof. |
| TIME_CONFOUNDER_STATUS_LIMIT | medium | time reversal control reported | Factor does not close a full physical-mechanism proof. |
| MASK_TRANSITION_READINESS_LIMIT | medium | B segment is reserved; no full MASK-transition proof in E0-R3 | Factor does not close a full physical-mechanism proof. |
| VEHICLE_YAW_READINESS_LIMIT | medium | body-axis proxy and SAR response axes remain separated; true yaw is not recovered | Factor does not close a full physical-mechanism proof. |
| E0_R3_TOTAL_STATUS_LIMIT | medium | factor-level result; no weighted score | Factor does not close a full physical-mechanism proof. |

## Visual Review

| visual | opened | observation |
| --- | --- | --- |
| `structure_contact_sheet` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `dynamic_interval_contraction_success` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `dynamic_interval_contraction_failure_or_limit` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `a_complete_anchor_timeline_end_sar000360` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `a_complete_anchor_timeline_start_sar000315` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `a_to_b_mask_transition_reserved_sar000361` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `component_structure_sample_sar000357` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `different_aspect_similar_range_frame_b_sar000347` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `high_energy_body_long_sliding_sample_sar000327` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `high_energy_stable_control_sample_sar000358` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `out_of_domain_diagnosis_frame_sar000361` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `same_aspect_revisit_frame_a_sar000315` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
| `same_aspect_revisit_frame_b_sar000321` | true | 已实际打开 E0-R3 结构接触表和区间审阅图；可见 GT 只作事后参考，高能质心、峰值、匿名分量和 body-axis proxy 已叠加显示。 |
