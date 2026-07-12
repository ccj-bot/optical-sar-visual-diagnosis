# WGV3.6B-E0-R2 GM_RM017 Temporal Multi-Aspect Vehicle Response Audit

## Conclusion

- `VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED`: `NOT_READY`
- `E0_R2_PHYSICAL_MECHANISM_SUPPORTED`: `NOT_READY`
- `E0_R2_READY_FOR_CROSS_VEHICLE_VALIDATION`: `NOT_READY`

E0-R2 remains a same-scene GT-conditioned posthoc audit. It does not create runtime rules, a detector, selector, ranker, final box, GT edit, training signal, or cross-scene claim.

## Aspect Observability

- calibration observable frames: `37`; HIGH `33`; span `35.868228` deg; median CI `1.048169` deg.
- diagnosis observable frames: `24`; HIGH `0`; span `18.756001` deg; inside calibration domain `false`.
- all observable frames: `71`; unresolved frames `0`.

## Response Versus Aspect

- local smoothness correlation: `-0.006206`; abrupt small-aspect changes `16`; large-aspect response changes `0`.
- same-aspect repeatability effect: `0.379348` with `same_pairs=30;different_pairs=0`.
- response-index R2: aspect `0.362385`, range `0.056597`, time `0.06148`.
- aspect shuffle passed: `False`.

## Counterfactuals

| counterfactual | group | observable frames | aspect span | abs corr | reproduces vehicle coupling |
| --- | --- | --- | --- | --- | --- |
| GT-attached corridor | body_long | 288 | 45.380729 | 0.187234 | false |
| GT-attached corridor | body_short | 288 | 45.380729 | 0.268226 | false |
| GT-attached corridor | local_azimuth | 288 | 45.380729 | 0.358617 | false |
| GT-attached corridor | local_range | 288 | 45.380729 | 0.231667 | false |
| persistent strong | fixed_strong_scatterer | 71 | 45.380729 | 0.301636 | false |
| fixed background | fixed_known_non_vehicle_N005 | 71 | 45.380729 | 0.240127 | false |
| fixed background | fixed_linear_structure | 71 | 45.380729 | 0.100151 | false |
| fixed background | fixed_strong_scatterer | 71 | 45.380729 | 0.301636 | false |

## Gates

| gate | status | evidence |
| --- | --- | --- |
| G1_ASPECT_PROXY_OBSERVABLE | PASS | cal_obs=37;diag_obs=24;diag_ci=0.745718 |
| G2_ASPECT_SPAN_SUFFICIENT | PARTIAL | cal_span=35.868228;diag_span=18.756001;diag_inside_cal=false |
| G3_METRIC_SUPPORT_STABLE | PASS | metric_extent_cv=0.15415 |
| G4_LOCAL_ASPECT_RESPONSE_SMOOTHNESS | PARTIAL | smoothness=-0.006206;abrupt=16;large=0 |
| G5_SAME_ASPECT_REPEATABILITY | PARTIAL | same_pairs=30;different_pairs=0;effect=0.379348 |
| G6_ASPECT_EFFECT_NOT_EXPLAINED_BY_RANGE_ONLY | PASS | r2_aspect=0.362385;r2_range=0.056597 |
| G7_ASPECT_EFFECT_NOT_EXPLAINED_BY_TIME_ONLY | PARTIAL | r2_aspect=0.362385;r2_time=0.06148;shuffle_ok=False |
| G8_GT_ATTACHED_BACKGROUND_REJECTED | PASS | corridor_groups=4;reproducing_groups=0 |
| G9_PERSISTENT_STRONG_COUNTERFACTUAL_REJECTED | PASS | persistent_groups=1;reproducing_groups=0 |
| G10_FIXED_BACKGROUND_ASPECT_COUPLING_REJECTED | PASS | fixed_groups=3;reproducing_groups=0 |

## Integrity Gates

| gate | status | evidence |
| --- | --- | --- |
| WORKTREE_BRANCH_VALID | PASS | branch=feature/oty2-gm017-physical-factor-discovery |
| START_COMMIT_ANCESTRY_VALID | PASS | 4ec662b36d0dc203dde5e165b94c786798ee0bde |
| E0_R1_R1_FROZEN_UNCHANGED | PASS | E0_R1_R1=unchanged_since_start |
| PRE_EVAL_SEAL_VALID | PASS | seal ok |
| FROZEN_REPLAY_IDENTICAL | PASS | replay_rows=8 |
| HEADING_OBSERVABILITY_AUDIT_COMPLETE | PASS | all_frames=71 observable;unresolved=0 |
| DIAGNOSIS_ASPECT_OBSERVABLE | PASS | diag_obs=24;diag_high=0 |
| ASPECT_SPAN_SUFFICIENT | NOT_READY | cal_span=35.868228;diag_span=18.756001;diag_inside_cal=false |
| ASPECT_UNCERTAINTY_BOUNDED | PASS | median_ci_all=0.921609 |
| RESPONSE_DESCRIPTOR_COMPLETE | PASS | vehicle_observable_rows=71 |
| ASPECT_RESPONSE_MODEL_FROZEN | PASS | descriptor set and Gate thresholds fixed from calibration |
| ASPECT_RESPONSE_SMOOTHNESS_SUPPORTED | NOT_READY | smoothness=-0.006206;abrupt=16;large=0 |
| SAME_ASPECT_REPEATABILITY_SUPPORTED | NOT_READY | same_pairs=30;different_pairs=0;effect=0.379348 |
| RANGE_CONFOUNDER_REJECTED | SUPPORTED | r2_aspect=0.362385;r2_range=0.056597 |
| TIME_ORDER_CONFOUNDER_REJECTED | NOT_READY | r2_aspect=0.362385;r2_time=0.06148;shuffle_ok=False |
| GT_ATTACHED_BACKGROUND_CONTROL_COMPLETE | PASS | corridor_groups=4 |
| PERSISTENT_STRONG_COUNTERFACTUAL_COMPLETE | PASS | persistent_groups=1 |
| FIXED_BACKGROUND_ASPECT_CONTROL_COMPLETE | PASS | fixed_groups=3 |
| GT_ATTACHED_BACKGROUND_REJECTED | SUPPORTED | corridor_groups=4;reproducing_groups=0 |
| PERSISTENT_STRONG_COUNTERFACTUAL_REJECTED | SUPPORTED | persistent_groups=1;reproducing_groups=0 |
| FIXED_BACKGROUND_ASPECT_COUPLING_REJECTED | SUPPORTED | fixed_groups=3;reproducing_groups=0 |
| VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED | NOT_READY | all_primary_gates_pass=False |
| E0_R2_PHYSICAL_MECHANISM_SUPPORTED | NOT_READY | requires all E0-R2 multi-aspect Gates to pass |
| E0_R2_READY_FOR_CROSS_VEHICLE_VALIDATION | NOT_READY | GM_RM017 same-scene audit only; no cross-vehicle package |

## Failure Ledger

| failure | severity | evidence | interpretation |
| --- | --- | --- | --- |
| E0_R1_R1_DIRECTION_NOT_READY_CARRIED_FORWARD | medium | E0-R1-R1 complete direction relation was NOT_READY; E0-R2 reaudits aspect instead of inheriting support. | Multi-aspect claims must stand on bounded aspect observability and counterfactual tests. |
| DIAGNOSIS_ASPECT_DOMAIN_LIMIT | medium | diagnosis_span=18.756001;inside_calibration_domain=false | Diagnosis outside or narrower than calibration is an extrapolation limit, not fresh validation. |
| MATCHED_STRONG_REMAINS_SINGLE_FRAME_NEGATIVE | medium | matched_strong_scatterer_background has no persistent subject track in E0-R1-R1. | It remains a hard single-frame negative and cannot be used as a temporal multi-aspect counterfactual track. |
| G2_ASPECT_SPAN_SUFFICIENT_NOT_FULLY_SUPPORTED | high | cal_span=35.868228;diag_span=18.756001;diag_inside_cal=false | aspect_span_or_domain_partial |
| G4_LOCAL_ASPECT_RESPONSE_SMOOTHNESS_NOT_FULLY_SUPPORTED | medium | smoothness=-0.006206;abrupt=16;large=0 | local_smoothness_not_strong |
| G5_SAME_ASPECT_REPEATABILITY_NOT_FULLY_SUPPORTED | medium | same_pairs=30;different_pairs=0;effect=0.379348 | pair_evidence_insufficient_or_effect_small |
| G7_ASPECT_EFFECT_NOT_EXPLAINED_BY_TIME_ONLY_NOT_FULLY_SUPPORTED | high | r2_aspect=0.362385;r2_time=0.06148;shuffle_ok=False | time_order_or_shuffle_control_not_rejected |

## Visual Review

| visual | SAR | conclusion |
| --- | --- | --- |
| `aspect_timeline` |  | 相对观测角随帧号变化，但诊断段是否可用必须受可观测性状态和校准角域约束。 |
| `heading_observability_status` |  | 航向可观测性被分成高、中和未解析，不能把曲线轨迹本身等同于切线不可观测。 |
| `heading_ci_width` |  | 轴向置信区间宽度直接限制 aspect 证据，宽区间帧只能作为弱诊断或未解析处理。 |
| `tangent_method_uncertainty` |  | 四类切线方法的一致性用于约束航向代理，避免仅靠单一平滑器制造稳定方向。 |
| `along_cross_residual` |  | 横轨迹残差用于区分局部曲线运动和局部切线估计失败，残差高的帧不能支撑强 aspect 结论。 |
| `aspect_span_by_split` |  | aspect 角域必须同时看跨度和不确定性；诊断段若落在校准外只能报告外推限制。 |
| `vehicle_energy_vs_aspect` |  | 车辆局部背景归一化能量可随 aspect 呈趋势，但需要被 range/time 反事实拆解后才能称为机制证据。 |
| `body_width_vs_aspect` |  | 车体轴向展宽随 aspect 的变化是多视角候选证据，但必须保持尺度支撑稳定。 |
| `near_far_vs_aspect` |  | 近远侧能量比提供雷达向结构线索，但不单独等同于车头车尾语义。 |
| `centroid_vs_aspect` |  | 能量质心沿车体轴的漂移用于检查响应场是否随视角发生内部重分布。 |
| `fragmentation_vs_aspect` |  | 碎裂度变化可以解释散射支撑分裂或合并，但需要与背景 corridor 对照。 |
| `descriptor_trajectory` |  | 描述符随时间变化并不自动等于 aspect 规律，E0-R2 会单独审计时间顺序混杂。 |
| `same_aspect_pair_candidates` |  | 同 aspect 重复性只比较满足距离和时间间隔约束的帧对，不用总体趋势替代成对证据。 |
| `range_confounding_proxy` |  | 若 aspect 与绝对距离强耦合，响应趋势不能直接解释为视角机制。 |
| `time_confounding_proxy` |  | 如果 aspect 基本随时间单调漂移，时间顺序本身就是必须剔除的混杂解释。 |
| `aspect_shuffle_control` |  | 打乱 aspect 顺序的对照用于判断真实 aspect-response 对应是否强于随机时间配对。 |
| `gt_attached_background_corridors` |  | GT 附近随车移动的 corridor 若也呈同样趋势，会削弱车辆内部结构演化解释。 |
| `persistent_strong_counterfactual` |  | 固定强散射体的响应若仅随车辆 aspect 代理变化，需判定为背景或时间混杂而非车辆机制。 |
| `fixed_background_aspect_control` |  | N005、固定强散射和固定线性背景必须独立计算 aspect 耦合，不能继承车辆结论。 |
| `aspect_unobservable_cases` |  | 未解析帧被保留在账本中，不作为失败或通过来制造多视角结论。 |
| `vehicle_vs_counterfactual_summary` |  | 车辆多视角机制必须同时压过 corridor、固定背景、强散射反事实和随机/距离/时间对照。 |

## Direct Answer

After the E0-R1-R1 symmetric Gate repair and the E0-R2 180-degree axial/aspect re-audit, GM_RM017 shows an observable same-scene relative-aspect timeline and several vehicle response descriptors vary with that proxy. However, the current evidence does not close the full multi-aspect mechanism loop because at least one required Gate remains only partial: the diagnosis aspect domain, local smoothness, same-aspect repeatability, or time/shuffle counterfactual rejection is not fully satisfied. The GT-attached corridor, persistent strong-scatterer, and fixed-background counterfactuals were computed and did not reproduce the vehicle coupling under this response-index audit, but that is not enough to overcome the remaining partial Gates. Therefore E0-R2 reports `VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED=NOT_READY`, not a claim that the vehicle SAR response has been proven to evolve with aspect beyond the available counterfactuals.
