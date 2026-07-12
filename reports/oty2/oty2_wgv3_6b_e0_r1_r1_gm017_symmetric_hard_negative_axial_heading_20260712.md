# WGV3.6B-E0-R1-R1 GM_RM017 Symmetric Hard-Negative Gates and Axial-Heading Audit

## Conclusion

- `VEHICLE_METRIC_SCALE_PATTERN_SUPPORTED`: `SUPPORTED`
- `VEHICLE_SPATIAL_CONCENTRATION_SUPPORTED`: `SUPPORTED`
- `VEHICLE_DIRECTIONAL_STRUCTURE_SUPPORTED`: `NOT_READY`
- `VEHICLE_HARD_NEGATIVE_REJECTION_SUPPORTED`: `NOT_READY`
- `E0_R1_R1_PHYSICAL_SEPARABILITY_SUPPORTED`: `NOT_READY`
- `E0_R1_R1_READY_FOR_CROSS_SCENE_VALIDATION`: `NOT_READY`

R1-R1 corrects E0-R1 locally. It does not create a detector, selector, ranker, final box, GT edit, training signal, or cross-scene validation claim.

## Withdrawn E0-R1 Result

`E0-R1 multi_gate_physical_confusions=0 was invalid as a scientific result because the prior G10 definition was label-dependent and impossible for non-vehicle regions to pass.` R1-R1 recomputes G7/G9/G10 with subject-specific inputs and records `NOT_EVALUABLE` separately.

## GT Center And Heading

- SAR336 status: `WEAK_CORRESPONDENCE_EXCLUDED`; selected pair `WGV35A_PAIR_0033`; identity status `duplicate_frame_primary_thread_selected_weak_correspondence_excluded`.
- diagnosis high-confidence heading frames: E0-R1 `9` -> E0-R1-R1 `0`.
- directed heading is motion trend in `[-180,180)`; axial body proxy is `[0,180)` and all body-axis differences are `[0,90]`.
- calibration principal/body axial q90: `4.515809`; direction interval ready: `True`.

## Hard Negatives

- worst hard negative: `matched_strong_scatterer_background`.
- matched strong scatterer: fraction vehicle higher `0.577465`, observable confusion rate `0.69697`, full confusion count `0`.
- N005: fraction vehicle higher `0.971831`, observable confusion rate `0.151515`, full confusion count `0`.
- observable structure confusion count: `42`.
- full physical confusion count: `0`.
- NOT_EVALUABLE gate count: `692`; reasons: `FRAMEWISE_MATCHED_CONTROL_NO_TRACK=426; LOW_OR_MEDIUM_HEADING_CONFIDENCE=266`.

## Subject Temporal Results

| subject | G9 | G10 | reason |
| --- | --- | --- | --- |
| fixed_known_non_vehicle_N005 | FAIL | FAIL | FAIL_BACKGROUND_EXPLANATION_SUFFICIENT |
| fixed_linear_structure | PASS | FAIL | FAIL_BACKGROUND_EXPLANATION_SUFFICIENT |
| fixed_strong_scatterer | FAIL | FAIL | FAIL_BACKGROUND_EXPLANATION_SUFFICIENT |
| matched_linear_structure_background | NOT_EVALUABLE | NOT_EVALUABLE | FRAMEWISE_MATCHED_CONTROL_NO_TRACK |
| matched_ordinary_background | NOT_EVALUABLE | NOT_EVALUABLE | FRAMEWISE_MATCHED_CONTROL_NO_TRACK |
| matched_strong_scatterer_background | NOT_EVALUABLE | NOT_EVALUABLE | FRAMEWISE_MATCHED_CONTROL_NO_TRACK |
| vehicle_body_axis_reference | PASS | PASS | region_moves_with_subject_background_fixedness_rejected |

## Worst-Control Summary

| subject | vehicle-higher fraction | observable confusion | full confusion |
| --- | --- | --- | --- |
| fixed_known_non_vehicle_N005 | 0.971831 | 5/33 | 0/71 |
| fixed_linear_structure | 0.929577 | 1/33 | 0/71 |
| fixed_strong_scatterer | 0.887324 | 5/33 | 0/71 |
| matched_linear_structure_background | 0.647887 | 7/33 | 0/0 |
| matched_ordinary_background | 0.971831 | 1/33 | 0/0 |
| matched_strong_scatterer_background | 0.577465 | 23/33 | 0/0 |

## Gates

| gate | status | evidence |
| --- | --- | --- |
| WORKTREE_BRANCH_VALID | PASS | branch=feature/oty2-gm017-physical-factor-discovery;head=76029c558a7706bd6c460b8eb31749cce75406af |
| START_COMMIT_ANCESTRY_VALID | PASS | 76029c558a7706bd6c460b8eb31749cce75406af |
| P0_D1_D1_R1_E0_E0_R1_FROZEN_UNCHANGED | PASS | P0=unchanged_since_start; D1=unchanged_since_start; D1_R1=unchanged_since_start; E0=unchanged_since_start; E0_R1=unchanged_since_start |
| PRE_EVAL_SEAL_VALID | PASS | seal ok |
| FROZEN_REPLAY_IDENTICAL | PASS | replay_check=True |
| GT_CENTER_IDENTITY_AUDIT_COMPLETE | PASS | frames=71;sar336_audited=true |
| DUPLICATE_FRAME_CONFLICTS_RESOLVED_OR_EXCLUDED | PASS | SAR336 weak correspondence excluded; no unresolved selected centers |
| FRAME_GAP_AWARE_VELOCITY_VALID | PASS | delta_frame recorded and velocity normalized per SAR frame |
| AXIAL_180_DEGREE_SEMANTICS_VALID | PASS | body_axis_proxy_deg in [0,180); axial differences in [0,90] |
| HEADING_PROXY_REAUDITED | PASS | high_total=33;high_diag=0 |
| HIGH_CONFIDENCE_DIAGNOSIS_HEADING_SUFFICIENT | NOT_READY | high_diag=0;diag_total=24 |
| SYMMETRIC_GATE_DEFINITIONS_VALID | PASS | 10 Gate definitions recorded with same fields/rules for all subjects |
| NO_LABEL_DEPENDENT_GATE_LOGIC | PASS | label_fields_used_for_status_false=True |
| VEHICLE_AND_NEGATIVE_SAME_GATE_RULES | PASS | same gate_definition_version=e0_r1_r1_symmetric_gate_v1 |
| SUBJECT_SPECIFIC_TRANSLATION_SURFACES_COMPLETE | PASS | subject_frames=497;surfaces=14910 |
| SUBJECT_SPECIFIC_TEMPORAL_GATES_COMPLETE | PASS | subjects=7;matched_controls_marked_not_evaluable_no_track |
| BACKGROUND_FIXEDNESS_GATE_VALID | PASS | G10 uses subject_center_motion_px and image_coordinate_fixedness_sufficient |
| WORST_HARD_NEGATIVE_EVALUATED | PASS | worst=WORST_CONTROL source=matched_strong_scatterer_background |
| OBSERVABLE_STRUCTURE_CONFUSION_AUDITED | PASS | observable_confusion_count=42 |
| FULL_PHYSICAL_CONFUSION_AUDITED | PASS | full_physical_confusion_count=0 |
| VEHICLE_METRIC_SCALE_PATTERN_SUPPORTED | SUPPORTED | vehicle_scale_gate_fraction=0.961268 |
| VEHICLE_SPATIAL_CONCENTRATION_SUPPORTED | SUPPORTED | vehicle_G7_fraction=0.619718;worst_fraction_vehicle_higher=0.577465 |
| VEHICLE_DIRECTIONAL_STRUCTURE_SUPPORTED | NOT_READY | direction_interval_ready=True;cal_q90=4.515809;high_diag=0;vehicle_G8_fraction=0.450704 |
| VEHICLE_HARD_NEGATIVE_REJECTION_SUPPORTED | NOT_READY | full_confusions=0;matched_strong_observable_rate=0.69697;direction_supported=False |
| E0_R1_R1_PHYSICAL_SEPARABILITY_SUPPORTED | NOT_READY | requires metric scale + spatial concentration + direction + temporal + hard-negative rejection |
| E0_R1_R1_READY_FOR_CROSS_SCENE_VALIDATION | NOT_READY | same-scene GT-conditioned posthoc correction; no cross-scene validation package |

## Failure Ledger

| failure | severity | evidence | interpretation |
| --- | --- | --- | --- |
| E0_R1_PRIOR_ZERO_CONFUSION_INVALID | high | E0-R1 G10 was label-dependent and impossible for non-vehicle regions to pass | E0-R1 multi_gate_physical_confusions=0 is withdrawn as a scientific result. |
| DIRECTION_INTERVAL_READY | low | cal_high=26;principal_body_q90=4.515809 | Vehicle directional relation is supported only if calibration is narrow enough to freeze a non-wide interval. |
| MATCHED_CONTROLS_NO_PERSISTENT_TRACK | medium | matched_linear_structure_background;matched_ordinary_background;matched_strong_scatterer_background | Framewise matched controls cannot be forced through G9/G10 as persistent subject tracks. |
| NOT_EVALUABLE_ACCOUNTING | low | not_evaluable_gate_instances=692 | NOT_EVALUABLE rows are counted separately and never treated as PASS or FAIL. |
| FULL_PHYSICAL_CONFUSION_RECHECK | low | full_physical_confusion_count=0 | Full confusion requires observable Gates plus evaluable G9/G10; label shortcuts are not used. |

## Visual Review

| visual | SAR | conclusion |
| --- | --- | --- |
| `sar336_multi_gt_weak_correspondence_conflict` | 336 | SAR336 双 GT 被单独审阅：主线程中心保留，弱对应候选排除，原 GT 未修改。 |
| `raw_gt_center_trajectory` |  | 原始轨迹显示 SAR336 同帧多行会造成轨迹歧义，不能直接按同帧平均。 |
| `selected_unique_center_trajectory` |  | 清洗后的中心序列保留唯一物理线程，重复/弱对应帧被显式标注。 |
| `directed_motion_heading_vectors` |  | 有向运动箭头仅解释运动趋势，不再当作车体长轴的有向角。 |
| `axial_body_axis_proxy_vectors` |  | 车体轴用 180 度周期显示，前后方向等价，避免把掉头角误判为轴向断裂。 |
| `directed_vs_axial_curvature` |  | 原有大角度一步曲率在轴向语义下明显收缩，说明 E0-R1 航向代理确有有向/轴向混用风险。 |
| `heading_confidence_frames` |  | 高/中/低置信度沿轨迹分布不均，诊断段方向结论必须受高置信帧数量约束。 |
| `vehicle_translation_surface` | 376 | 车辆平移面在零点附近保留局部峰/平台，但需与每类负样本同轴同网格比较。 |
| `matched_strong_scatterer_translation_surface` | 376 | 匹配强散射背景被单独成面评估，不再借用车辆 near-GT 平移结果。 |
| `matched_linear_structure_translation_surface` | 376 | 匹配线性结构有自己的主轴和垂轴扰动面，不能与普通背景合并。 |
| `n005_translation_surface` | 376 | N005 固定非车辆区域按同一网格生成平移面，G7 不再因标签直接失败。 |
| `fixed_strong_scatterer_temporal` |  | 固定强散射背景的能量稳定性被作为 G9/G10 输入，而不是作为车辆证据继承。 |
| `fixed_linear_structure_temporal` |  | 固定线性背景具有图像坐标持久性，需由 G10 判断固定背景解释是否充分。 |
| `e0_r1_false_zero_confusion_logic` |  | 旧零混淆来自标签依赖 G10 的恒假结构，不是数据证明。 |
| `typical_separable_frame` | 373 | 典型可分帧中车辆邻域相对最强负样本更集中，空间面仍需同构 Gate 约束。 |
| `typical_confusion_frame` | 327 | 典型混淆帧显示强负样本压力真实存在，不能再用旧恒假 G10 抹掉。 |
| `g9_g10_no_persistent_subject_case` | 376 | 逐帧匹配背景不是持续主体，G9/G10 只能标记不可评价，不能被算作失败制造零混淆。 |
| `vehicle_vs_hardest_negative_gate_contrast` | 315 | 车辆与最困难负样本逐 Gate 对照显示：不可评价项被单独保留，没有当作失败来制造零混淆。 |

## Direct Answer

After removing label-dependent Gates, applying the same spatial and temporal rules to vehicles and hard negatives, and correcting 180-degree axial semantics, the vehicle GT neighbourhood still shows metric-scale and centered spatial structure that matched strong scatterer, N005, and linear backgrounds do not fully reproduce under evaluable G9/G10. However, the vehicle directional relation remains `NOT_READY` because the posthoc diagnosis segment has zero HIGH-confidence axial heading frames after the duplicate/gap/axial-curvature audit. Therefore the complete米制-空间-方向-时序 physical separability claim remains `NOT_READY`, not a cross-scene or final-detection conclusion.
