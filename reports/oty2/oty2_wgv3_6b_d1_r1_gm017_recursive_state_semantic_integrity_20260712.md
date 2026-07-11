# WGV3.6B-D1-R1 GM_RM017 Recursive State Semantic Integrity Repair

## 结论

- D1_R1_SEMANTIC_INTEGRITY_READY: `PASS`
- D1_R1_PHYSICAL_DYNAMIC_MEMBERSHIP_READY: `NOT_READY`
- SAR 371-394 在本报告中只称为 `事后诊断窗口 / regression and mechanism-diagnosis window`，不是 fresh holdout。
- 本轮没有输出最终车辆框、最终标注、selector、ranking、加权综合分数或 GT 修改。
- D1 仍作为原始递归对照保留：D1 确实递归，当前 SAR 观测会改变后验状态，且 D1 优于无观测外推；但 D1 与 D1-R1 都没有证明动态物理成员机制，也未击败 P0 绝对帧线性基线。

## 语义修复结果

- 背景关联: `723` 行；background track/frame 重复: `0`；component/frame 重复: `0`。
- 背景状态: `background_recurrence_candidate=81; static_background_candidate=73; static_background_supported=37; unresolved_response=96`。
- response tracks: `18`；当前 same_motion_supported tracks: `7`。
- response associations: selected `237` / rejected `2102`；relative-structure rejected rows: `1960`。
- reappearance first-hit candidates: `36`；confirmed reappeared_supported rows: `14`。

## 对照结果

| model | mean | median | p90 | max | cumulative | velocity mean | role |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| D1_NO_OBSERVATION_UPDATE_BASELINE | 71.0202 | 69.812087 | 101.088271 | 113.678915 | 1704.484805 | 9.357032 | ablation_without_current_observation_update |
| D1_ORIGINAL_RECURSIVE_OBSERVATION_UPDATED | 17.53489 | 19.74117 | 28.354382 | 32.889737 | 420.837372 | 8.564724 | original_d1_recursive_current_sar_observation_updated_control |
| D1_R1_ALL_ASSOCIATED_TRACKS | 8.79039 | 9.142987 | 11.782611 | 15.647391 | 210.96937 | 8.662395 | d1_r1_policy_a_all_associated_tracks |
| D1_R1_STRUCTURE_CONSISTENT_ONLY | 8.90563 | 9.306458 | 12.156289 | 15.326167 | 213.735128 | 8.649488 | d1_r1_policy_c_strict_structure_admission |
| D1_R1_TEMPORALLY_SUPPORTED_ONLY | 8.959031 | 9.304193 | 11.753662 | 15.436587 | 215.016737 | 8.653362 | d1_r1_policy_b_temporal_support_admission |
| P0_ABSOLUTE_FRAME_LINEAR_BASELINE | 6.222823 | 5.514586 | 10.891643 | 13.316413 | 149.347762 | 8.641183 | p0_absolute_frame_linear_baseline |
| P0_STATIC_CENTER_BASELINE | 148.70794 | 144.278798 | 210.68961 | 220.281051 | 3568.99057 | 9.450803 | p0_static_state_360_baseline |

## 准入消融

| policy | mean | p90 | max | avg tracks | fallback frames | rejection distribution |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| ALL_ASSOCIATED_TRACKS | 8.79039 | 11.782611 | 15.647391 | 6.970588 | 0 |  |
| TEMPORALLY_SUPPORTED_ONLY | 8.959031 | 11.753662 | 15.436587 | 5.911765 | 0 | state=reappearance_candidate=36 |
| STRUCTURE_CONSISTENT_ONLY | 8.90563 | 12.156289 | 15.326167 | 5 | 1 | state=reappearance_candidate=31;state=reappearance_candidate+strict_gate_fail=5;state=reappearance_provisionally_supported=22;state=same_motion_candidate+strict_gate_fail=9 |

## 视觉审阅清单

- 接触表: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_visual_review_contact_sheet.png`
- 已实际用 `view_image` 打开接触表、SAR376、SAR361、SAR366、SAR394、SAR362、SAR364。总体观察：主亮带随帧向右移动，青色选中响应多数贴近主亮带或右侧局部响应；橙色 relative-structure 拒绝主要落在主亮带外侧、右下邻近亮斑或密集背景区；SAR394 未见单一明显跳错到远端亮斑，但邻近响应过密，不能把当前局部响应解释为已确认稳定物理成员。
- `full_contact_sheet` SAR371: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar371.png` - 完整 SAR361-394 接触表，覆盖所有生成帧。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。接触表已打开；主亮带随帧右移，青色响应主要贴近主亮带及右侧局部响应，橙色拒绝集中在远离稳定相对结构的亮斑。
- `abc_largest_divergence_frame` SAR376: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar376.png` - A/B/C 准入中心分歧最大。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；三组中心接近主亮带中段但存在小幅分离，说明准入规则改变状态修正而非执行selector排序。
- `max_state_correction_frame` SAR366: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar366.png` - 状态修正幅度最大。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；选中响应横跨主亮带与右侧局部响应，修正方向可解释但仍不是完整车辆成员证明。
- `background_duplicate_repair_typical_frame` SAR361: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar361.png` - 背景一对一关联负载最高的典型帧。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；同帧大量候选被拒绝或保留为背景候选，没有看到同一背景track吞并多个同帧component的可视迹象。
- `relative_structure_reject_max_frame` SAR361: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar361.png` - relative structure gate 拒绝最多。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；橙色叉号大量分布在主亮带外侧和右下邻近亮斑，说明relative structure gate不是空字段。
- `max_center_error_frame` SAR394: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar394.png` - D1-R1 strict policy 中心误差最大。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；右侧与上侧背景/邻近响应密集，状态仍可跟随主亮带但不支持稳定物理成员已确认。
- `suspected_wrong_association_frame` SAR394: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar394.png` - D1-R1 误差最大的后验诊断帧，需人工重点核查是否跟错局部响应。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；未见单一明显跳错到远端亮斑，但局部响应密集导致成员解释仍不充分。
- `representative_missing_frame` SAR361: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar361.png` - 代表性 temporarily_missing / terminated 状态帧。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；部分初始track未获得当前帧结构一致支持，missing状态与可视拒绝分布一致。
- `reappearance_first_hit_frame` SAR362: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar362.png` - 缺失后的首次重新关联，只允许 candidate。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；重新关联落在主亮带附近，但按规则未在同帧升级为supported。
- `reappeared_supported_confirmed_frame` SAR364: `outputs\wgv3_6b_d1_r1_gm017_semantic_integrity_20260712\visual_review\d1_r1_semantic_integrity_sar364.png` - 后续连续支持后的 confirmed reappearance。 图中青色为选中响应，橙色叉号为relative结构拒绝，绿色/蓝色/紫色分别为A/B/C中心。该帧已打开；后续支持连续性可见，但仍只能说明局部响应重新稳定，不等同完整车辆物理部件重现。

## Failure Ledger

| failure_type | severity | frame | evidence | interpretation |
| --- | --- | ---: | --- | --- |
| component_extraction_failure | medium |  | unresolved_components=381 | 未解析分量仍多，不能把所有误差压缩成单一状态更新问题。 |
| response_association_failure | medium |  | selected_associations=237 | 严格 gate 后可用关联减少，局部响应表示/跨帧关联仍是瓶颈。 |
| relative_structure_instability | high |  | relative_structure_rejected=1960 | relative structure gate 实际生效，说明不少候选只满足运动壳而非稳定相对结构。 |
| insufficient_track_support | high |  | structure_policy_fallback_frames=1 | 严格物理成员准入下部分帧退化到预测，说明成员证据不足。 |
| reappearance_not_confirmed | medium |  | candidates=36;confirmed=14 | 首次重新关联已从 confirmed 中拆出，部分重现无法确认。 |
| state_update_bias | high |  | structure_mean=8.90563;p0_linear_mean=6.222823 | 语义修复未击败 P0 绝对帧线性基线，不能宣称动态物理成员机制验证。 |
| max_error_case_for_visual_review | review | 394 | model=D1_R1_ALL_ASSOCIATED_TRACKS;center_error=15.647391 | D1-R1 最大误差帧已进入视觉重点清单。 |

## Gates

| gate | status | evidence |
| --- | --- | --- |
| WORKTREE_BRANCH_VALID | PASS | branch=feature/oty2-gm017-physical-factor-discovery;head=57a82b11ec715539fe054bbad490f069a503c928 |
| P0_ARTIFACTS_FROZEN_UNCHANGED | PASS | git diff --quiet 1a3edd97d17b167ca63d9d70651dad29d5601f5b -- P0 frozen artifact paths |
| D1_ARTIFACTS_FROZEN_UNCHANGED | PASS | git diff --quiet 57a82b11ec715539fe054bbad490f069a503c928 -- D1 frozen artifact paths |
| GENERATOR_HOLDOUT_GT_IMPORT_FORBIDDEN | PASS | D1-R1 generator source scanned before reference labels were opened |
| HOLDOUT_GT_NOT_READ_DURING_GENERATION | PASS | generation artifacts record gt_file_opened=false |
| FUTURE_FRAME_NOT_READ | PASS | max_sar_frame_read <= current SAR frame |
| PRE_EVAL_SEAL_VALID | PASS | seal ok |
| GENERATOR_SOURCE_SHA_VALID | PASS | generator source sha matches pre-eval seal |
| FROZEN_RUNTIME_PARAMETERS_VALID | PASS | runtime parameter sha matches pre-eval seal |
| FROZEN_REPLAY_IDENTICAL | PASS | replay_rows=15 |
| BACKGROUND_ONE_COMPONENT_PER_TRACK_PER_FRAME | PASS | no duplicate background_track_id+sar_frame |
| BACKGROUND_ONE_TRACK_PER_COMPONENT_PER_FRAME | PASS | no duplicate component_id+sar_frame |
| BACKGROUND_UNIQUE_FRAME_SUPPORT_VALID | PASS | support_unique_frame_count equals support_frame_ids count |
| BACKGROUND_CONFLICT_AUDIT_IMPLEMENTED | PASS | conflicting_vehicle_motion_frames field is explicit |
| RESPONSE_STATE_MACHINE_CONSISTENT | PASS | current_evidence_state is single and consistent with same_motion flag |
| CURRENT_AND_HIGHEST_STATE_SEPARATED | PASS | current and highest evidence states are separate fields |
| MOTION_SHELL_NOT_EQUAL_SAME_MOTION | PASS | motion shell candidate never implies same-motion support |
| RELATIVE_STRUCTURE_GATE_ACTIVE | PASS | relative_gate_fail_rows=1960 |
| SAME_MOTION_SUPPORT_USES_UNIQUE_FRAMES | PASS | same_motion rows require support_unique_frame_count >= 2 |
| PRIOR_RESPONSE_PREDICTION_UNCONTAMINATED | PASS | relative residual computed from prior track-relative fields |
| TRACK_SPECIFIC_MISSING_STATE_VALID | PASS | visibility_events=161 |
| REAPPEARANCE_FIRST_HIT_NOT_AUTO_SUPPORTED | PASS | candidate_rows=36 |
| REAPPEARANCE_CONFIRMATION_VALID | PASS | confirmation_rows=36 |
| ADMISSION_POLICY_ABLATION_COMPLETE | PASS | state_rows=102 |
| UNSUPPORTED_TRACKS_CANNOT_UPDATE_TARGET_STATE | PASS | eligible_track_ids and exclusion_reasons are explicit |
| STATE_UPDATE_PROVENANCE_COMPLETE | PASS | state rows include admitted/excluded tracks and update source |
| VISUAL_REVIEW_GROUNDED | PASS | visual_rows=34 |
| BASELINE_COMPARISON_COMPLETE | PASS | D1 original, D1-R1 A/B/C, no-observation, P0 linear, P0 static compared |
| FAILURE_CLASSIFICATION_SPECIFIC | PASS | failure_types=7 |
| D1_R1_SEMANTIC_INTEGRITY_READY | PASS | semantic gates pass |
| D1_R1_PHYSICAL_DYNAMIC_MEMBERSHIP_READY | NOT_READY | semantic repair does not prove stable physical dynamic membership; P0 absolute-frame baseline remains stronger |

## 下一阶段判断

- 严格结构准入下 fallback frames: `1`。
- D1-R1 已具备语义完整性审计价值，但不具备直接进入 D2 新连续留出验证的条件；下一步应先改进局部 SAR 响应表示或跨帧关联机制，而不是放宽 gate。

## 冻结与隔离

- pre_eval_seal: `reports\oty2\samples\oty2_wgv3_6b_d1_r1_gm017_pre_eval_seal_20260712.csv`
- evaluator reference source opened after seal: `reports\oty2\samples\oty2_wgv3_5a_paired_annotations_20260710.csv`
- generator artifacts record `gt_file_opened=false`, `evaluation_file_opened=false`, and `future_frame_read=false`.
- P0 and original D1 frozen artifacts are checked against their baseline commits.
