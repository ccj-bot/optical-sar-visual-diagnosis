# OTY2 no_oty_iou_match 小规模 triage 报告

生成时间：`20260702_194129`

本轮只诊断 GT 样本账本中的 12 条 `no_oty_iou_match`。它们都有 review 光学框和同帧 OTY 对象候选，但没有通过 primary-box IoU `0.05` 配对门槛。本轮不做大规模机制消融，不改 accounting，不训练或调阈值，不生成自动标注建议。

## 总结

- 失败样本数：`12`。
- 原因分布：`{"primary_secondary_observation_mismatch": 7, "possible_optical_frame_offset_or_track_gap": 4, "secondary_observation_support_but_primary_gate_failed": 1}`。
- 可进入弱配对人工审阅候选：`8`。
- 当前应排除出光学-SAR机制配对子集：`4`。
- 建议分布：`{"需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。": 7, "需要人工审阅相邻帧；先不要进入当前机制样本，除非确认帧号或对象流断裂。": 4, "需要人工审阅；可考虑进入 weak correspondence，但必须显式标记 secondary-only 支持。": 1}`。

## 逐条 triage

| scene | sar_gt_id | optical_frame | sar_frame | best_primary_iou | best_secondary_iou | triage_reason | recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM017 | 97 | 149 | 310 | 0.018733 | 0.918612 | primary_secondary_observation_mismatch | 需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。 |
| GM_RM017 | 263 | 183 | 381 | 0 | 0.961969 | primary_secondary_observation_mismatch | 需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。 |
| GM_RM017 | 266 | 183 | 382 | 0 | 0.961937 | primary_secondary_observation_mismatch | 需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。 |
| GM_RM017 | 275 | 185 | 385 | 0 | 0.938827 | primary_secondary_observation_mismatch | 需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。 |
| GM_RM017 | 278 | 185 | 386 | 0 | 0.938747 | primary_secondary_observation_mismatch | 需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。 |
| GM_RM017 | 308 | 214 | 446 | 0 | 0.824701 | primary_secondary_observation_mismatch | 需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。 |
| GM_RM019 | 313 | 4 | 8 | 0 | 0 | possible_optical_frame_offset_or_track_gap | 需要人工审阅相邻帧；先不要进入当前机制样本，除非确认帧号或对象流断裂。 |
| GM_RM019 | 321 | 42 | 88 | 0 | 0 | possible_optical_frame_offset_or_track_gap | 需要人工审阅相邻帧；先不要进入当前机制样本，除非确认帧号或对象流断裂。 |
| GM_RM019 | 322 | 97 | 202 | 0 | 0.897788 | primary_secondary_observation_mismatch | 需要人工审阅；可作为 secondary-supported weak correspondence 候选，不应直接进 primary-only paired 子集。 |
| GM_RM019 | 329 | 147 | 306 | 0 | 0 | possible_optical_frame_offset_or_track_gap | 需要人工审阅相邻帧；先不要进入当前机制样本，除非确认帧号或对象流断裂。 |
| GM_RM019 | 332 | 168 | 350 | 0.023328 | 0.40648 | secondary_observation_support_but_primary_gate_failed | 需要人工审阅；可考虑进入 weak correspondence，但必须显式标记 secondary-only 支持。 |
| GM_RM019 | 333 | 170 | 354 | 0 | 0 | possible_optical_frame_offset_or_track_gap | 需要人工审阅相邻帧；先不要进入当前机制样本，除非确认帧号或对象流断裂。 |

## 关键观察

- `primary_secondary_observation_mismatch` 表示 review 光学框没有命中 OTY 主观测框，但命中了辅助观测框；这类样本可以作为 weak correspondence 的人工审阅候选，但不能直接混入 primary-only paired 子集。
- `iou_threshold_too_strict_with_position_or_scale_offset` 表示主框有极低重叠，但尺度或中心偏差太大；放宽阈值前必须人工确认，不能自动吸收。
- `far_small_or_edge_target_not_in_oty_primary_stream` 表示目标很小、远端或贴边，当前 OTY 对象流没有形成可匹配主框；这类更适合 review-only 或远小层，而不是当前主机制样本。
- `oty_object_stream_missed_review_target_or_large_position_difference` 表示同帧有 OTY 候选，但 review 目标不在可匹配主/辅框中；优先检查漏检、对象流断裂、坐标差异或 handoff。

## 时间错位检查

12 条样本的光学帧到 SAR 帧关系均按 `sar_frame = optical_frame * 50 / 24` 落在软件同步换算附近；本轮没有发现明显的 24:50 时间窗错位证据。失败主要来自光学对象框匹配层，而不是时间锚点层。

## 边界

- gt_accounting_read: `true`
- review_queue_or_gt_source_reused_from_accounting: `true`
- existing_oty_outputs_read: `true`
- optical_frame_content_read_for_visual_triage: `true`
- sar_image_content_read: `false`
- sar_gt_used_for_runtime_prior_construction: `false`
- automatic_annotation_proposal_generated: `false`
- training_or_threshold_tuning_entered: `false`
- selector_or_ranking_used: `false`
- identity_truth_claimed: `false`

## 数据源

- gt_sample_accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- object_frame_state_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- object_hypotheses_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_hypotheses_generalized.csv`
- local_full_visual_output: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_no_oty_iou_match_triage_20260702_194129`
- repo_sample_visual_output: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\no_oty_iou_match_triage\no_oty_iou_match_triage_20260702_194129`
