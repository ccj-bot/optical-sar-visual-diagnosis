# WGV3.6B-D1 GM_RM017 Recursive Causal State Propagation

## 结论

- D1_RECURSIVE_CAUSAL_STAGE_READY: `PASS`
- 本轮没有输出最终车辆框、最终标注、selector、ranking、加权综合分数或 GT 修改。
- SAR（Synthetic Aperture Radar，合成孔径雷达）当前帧观测以递归方式更新状态；评价只在 seal 校验后读取 holdout GT。

## 状态更新

- 生成帧范围: SAR `361-394`
- 当前观测更新帧数: `34`
- 最大观测修正: `5.337167` px
- response track 数量: `18`
- static background track 数量: `103`
- missing 事件: `94`
- reappearance 事件: `46`

## D1 与 P0 对照

| model | mean | median | p90 | cumulative | role |
| --- | ---: | ---: | ---: | ---: | --- |
| D1_NO_OBSERVATION_UPDATE_BASELINE | 71.0202 | 69.812087 | 101.088271 | 1704.484805 | ablation_without_current_observation_update |
| D1_RECURSIVE_OBSERVATION_UPDATED | 17.53489 | 19.74117 | 28.354382 | 420.837372 | recursive_current_sar_observation_updated_model |
| P0_ABSOLUTE_FRAME_LINEAR_BASELINE | 6.222823 | 5.514586 | 10.891643 | 149.347762 | p0_absolute_frame_baseline |
| P0_STATIC_CENTER_BASELINE | 148.70794 | 144.278798 | 210.68961 | 3568.99057 | p0_static_state_360_baseline |

## 视觉审阅

- 逐帧 PNG: `outputs/wgv3_6b_d1_gm017_recursive_causal_state_propagation_20260712/visual_review/`
- 接触表: `outputs\wgv3_6b_d1_gm017_recursive_causal_state_propagation_20260712\visual_review\d1_visual_review_contact_sheet.png`
- manifest rows: `34`
- 实际审阅范围: 已打开 SAR361-394 接触表，并重点查看 SAR379 最大状态修正帧与 SAR363 track-specific 重现帧。
- 图像结论: 主亮响应带连续右移，青色 response track 与主响应/右侧局部响应相邻；紫色 background track 主要位于上边界与静止斑点区域，未在审阅帧中发现需要降级的明显错误关联。
- 限制: 视觉审阅只支持递归诊断解释，不提升为最终车辆框、最终标注或唯一成员集合。

## Gates

| gate | status | evidence |
| --- | --- | --- |
| WORKTREE_BRANCH_VALID | PASS | branch=feature/oty2-gm017-physical-factor-discovery;head=562c1c7da5859c026fca193cb18048fbbfa2ad5f |
| P0_ARTIFACTS_FROZEN_UNCHANGED | PASS | git diff --quiet 1a3edd97d17b167ca63d9d70651dad29d5601f5b -- P0 artifact paths |
| GENERATOR_GT_IMPORT_FORBIDDEN | PASS | generator source scanned before evaluator opened GT |
| HOLDOUT_GT_NOT_READ_DURING_GENERATION | PASS | state history gt_file_opened=false |
| FUTURE_FRAME_NOT_READ | PASS | max_sar_frame_read <= current frame |
| PRE_EVAL_SEAL_VALID | PASS | reports\oty2\samples\oty2_wgv3_6b_d1_gm017_pre_eval_seal_20260712.csv |
| SEQUENTIAL_STATE_DEPENDENCY_VALID | PASS | state_t prior equals state_t-1 posterior |
| CURRENT_SAR_OBSERVATION_UPDATES_STATE | PASS | max_correction_px=5.337167 |
| SPECIFIC_RESPONSE_TRACKS_EXIST | PASS | response_tracks=18;association_rows=384 |
| MOTION_SHELL_NOT_EQUAL_SAME_MOTION | PASS | same_motion_supported_rows=297 |
| BACKGROUND_TRACKS_EXIST | PASS | background_tracks=235 |
| BACKGROUND_NOT_SINGLE_FRAME_SHAPE_ONLY | PASS | static background support_frames>=3 |
| TRACK_SPECIFIC_MISSING_STATE_EXISTS | PASS | visibility_events=94 |
| TRACK_SPECIFIC_REAPPEARANCE_VALID | PASS | reappearance_events=46;empty_allowed_as_INSUFFICIENT_REAPPEARANCE_EVENTS |
| TOP_K_NOT_USED_AS_PHYSICAL_SELECTOR | PASS | safety cap only; incomplete frames cannot produce strong membership |
| VISUAL_REVIEW_EVIDENCE_COMPLETE | PASS | visual_review_rows=34 |
| FROZEN_REPLAY_IDENTICAL | PASS | replay_rows=11 |
| P0_BASELINE_COMPARISON_COMPLETE | PASS | D1, no-observation ablation, P0 linear, and P0 static baselines compared |
| D1_RECURSIVE_CAUSAL_STAGE_READY | PASS | PASS only if recursion, current observation update, response/background tracks, replay, seal, and visual evidence all hold |

## Failure Ledger

| failure_id | failure_type | evidence |
| --- | --- | --- |
| D1_PRIMARY_OUTCOME | 观测提取失败 | d1_mean=17.53489;p0_mean=6.222823;noobs_mean=71.0202;unresolved=717;cap=0 |
| REAPPEARANCE_EVENTS | TRACK_SPECIFIC_REAPPEARANCE_RECORDED | reappearance_rows=46 |

## 冻结与隔离

- pre_eval_seal: `reports\oty2\samples\oty2_wgv3_6b_d1_gm017_pre_eval_seal_20260712.csv`
- evaluator GT source opened after seal: `reports\oty2\samples\oty2_wgv3_5a_paired_annotations_20260710.csv`
- generator rows record `gt_file_opened=false`, `evaluation_file_opened=false`, and `future_frame_read=false`.
- P0 files are checked against the P0 frozen manifest.
