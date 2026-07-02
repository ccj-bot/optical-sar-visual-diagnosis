# OTY2 检测缺失的时序延续与 SAR 后验支持审计

生成时间：`20260702_200455`

本轮只针对 12 条 `no_oty_iou_match` 样本，检查当前帧检测缺失、重度截断、前后帧时序延续和 SAR 后验支持。运行时安全证据、posthoc-only 证据和 detector-ablation 计划分开记录。

## 三层边界

- Runtime-safe：光学帧、OTY 主/辅观测、前后帧对象流、软件同步 24:50 时间关系。
- Posthoc-only：SAR GT、SAR 图像局部散射、GT 框形态；只用于机制确认，不能写入 runtime prior construction。
- Detector-ablation：更强 YOLO 只作为 A/B 计划或小样本 dry-run，不提交权重，不把检测数量当核心指标。

## 总结

- 样本数：`12`。
- 时序延续状态：`{"temporal_continuation_with_current_secondary_support": 6, "temporal_continuation_with_detection_dropout": 2, "one_sided_temporal_continuation_hypothesis": 2, "temporal_continuation_hypothesis_supported": 2}`。
- 样本用途类别：`{"clean_recovered_by_temporal_continuation": 8, "temporal_continuation_with_detection_dropout": 12, "secondary_supported_truncated_same_vehicle": 8, "yolo_upgrade_candidate": 12, "manual_review_required": 12, "exclude_from_clean_shape_statistics": 12, "sar_posthoc_supported_dropout_case": 12}`。
- SAR 后验支持状态：`{"sar_posthoc_supported_detection_dropout": 12}`。

## 逐条样本

| scene | sar_gt_id | optical_frame | sar_frame | current_frame_secondary_available | previous_support_frame_count | next_support_frame_count | temporal_continuation_status | propagation_diagnostic_status | sample_use_categories |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM017 | 97 | 149 | 310 | true | 6 | 10 | temporal_continuation_with_current_secondary_support | temporal_propagation_can_recover_review_target | clean_recovered_by_temporal_continuation;temporal_continuation_with_detection_dropout;secondary_supported_truncated_same_vehicle;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM017 | 263 | 183 | 381 | true | 10 | 10 | temporal_continuation_with_current_secondary_support | temporal_propagation_can_recover_review_target | clean_recovered_by_temporal_continuation;temporal_continuation_with_detection_dropout;secondary_supported_truncated_same_vehicle;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM017 | 266 | 183 | 382 | true | 10 | 10 | temporal_continuation_with_current_secondary_support | temporal_propagation_can_recover_review_target | clean_recovered_by_temporal_continuation;temporal_continuation_with_detection_dropout;secondary_supported_truncated_same_vehicle;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM017 | 275 | 185 | 385 | true | 10 | 8 | temporal_continuation_with_current_secondary_support | temporal_propagation_can_recover_review_target | clean_recovered_by_temporal_continuation;temporal_continuation_with_detection_dropout;secondary_supported_truncated_same_vehicle;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM017 | 278 | 185 | 386 | true | 10 | 8 | temporal_continuation_with_current_secondary_support | temporal_propagation_can_recover_review_target | clean_recovered_by_temporal_continuation;temporal_continuation_with_detection_dropout;secondary_supported_truncated_same_vehicle;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM017 | 308 | 214 | 446 | true | 10 | 0 | temporal_continuation_with_detection_dropout | temporal_propagation_can_recover_review_target | clean_recovered_by_temporal_continuation;temporal_continuation_with_detection_dropout;secondary_supported_truncated_same_vehicle;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM019 | 313 | 4 | 8 | false | 0 | 10 | one_sided_temporal_continuation_hypothesis | temporal_propagation_can_recover_review_target | temporal_continuation_with_detection_dropout;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM019 | 321 | 42 | 88 | false | 10 | 0 | one_sided_temporal_continuation_hypothesis | temporal_propagation_can_recover_review_target | temporal_continuation_with_detection_dropout;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM019 | 322 | 97 | 202 | true | 0 | 10 | temporal_continuation_with_detection_dropout | temporal_propagation_can_recover_review_target | clean_recovered_by_temporal_continuation;temporal_continuation_with_detection_dropout;secondary_supported_truncated_same_vehicle;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM019 | 329 | 147 | 306 | false | 1 | 9 | temporal_continuation_hypothesis_supported | temporal_propagation_can_recover_review_target | temporal_continuation_with_detection_dropout;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM019 | 332 | 168 | 350 | true | 10 | 8 | temporal_continuation_with_current_secondary_support | temporal_propagation_can_recover_review_target | clean_recovered_by_temporal_continuation;temporal_continuation_with_detection_dropout;secondary_supported_truncated_same_vehicle;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |
| GM_RM019 | 333 | 170 | 354 | false | 10 | 9 | temporal_continuation_hypothesis_supported | temporal_propagation_can_recover_review_target | temporal_continuation_with_detection_dropout;yolo_upgrade_candidate;manual_review_required;exclude_from_clean_shape_statistics;sar_posthoc_supported_dropout_case |

## 解释

- 当前帧 YOLO/OTY 主观测缺失不等于目标不存在。多数样本在当前帧有辅助观测，或在前后帧有空间连续的车辆观测。
- `clean_recovered_by_temporal_continuation` 只表示目标存在性和时序延续可被较干净地解释；它不等于 clean paired，不等于完整光学框形态样本。
- `temporal_propagation_can_recover_review_target` 只表示传播诊断能解释 review 框，不是自动标注建议，也不是最终框。
- 有 SAR 后验支持的样本可以用于研究 detection dropout / 重度截断 / SAR 目标存在机制，但不能直接进入完整车辆光学框形态主统计。
- 所有 12 条仍保留 `manual_review_required` 和 `exclude_from_clean_shape_statistics`，避免污染完整车辆形态统计。

## SAR 后验支持

| scene | sar_gt_id | sar_frame | gt_in_software_sync_window | sar_box_to_background_ratio | sar_peak_to_background_ratio | sar_scatter_support_status | sar_posthoc_support_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM017 | 97 | 310 | true | 1.032459 | 3.183938 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM017 | 263 | 381 | true | 1.056214 | 3.47329 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM017 | 266 | 382 | true | 1.053509 | 3.332537 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM017 | 275 | 385 | true | 1.037821 | 3.606999 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM017 | 278 | 386 | true | 1.031852 | 3.286807 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM017 | 308 | 446 | true | 1.025154 | 2.792406 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM019 | 313 | 8 | true | 0.920578 | 2.182516 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM019 | 321 | 88 | true | 0.870405 | 2.316305 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM019 | 322 | 202 | true | 0.928614 | 2.169227 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM019 | 329 | 306 | true | 0.857991 | 2.555002 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM019 | 332 | 350 | true | 1.110669 | 3.569324 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |
| GM_RM019 | 333 | 354 | true | 0.961131 | 3.859818 | sar_gt_crop_has_local_scatter_support | sar_posthoc_supported_detection_dropout |

## 边界 flags

- optical_frames_read: `true`
- existing_oty_outputs_read: `true`
- sar_gt_used: `true`
- sar_image_content_used: `true`
- sar_posthoc_only: `true`
- sar_gt_or_image_used_for_runtime_prior_construction: `false`
- automatic_annotation_proposal_generated: `false`
- training_or_threshold_tuning_entered: `false`
- propagated_box_written_as_final_annotation: `false`
- selector_or_ranking_used: `false`
- identity_truth_claimed: `false`
- model_weights_committed_or_downloaded: `false`

## 数据源

- no_oty_iou_match_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_no_oty_iou_match_triage_20260702_194129.csv`
- gt_sample_accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- final_gt_csv: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv`
- object_frame_state_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- local_visual_output: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_detection_dropout_temporal_sar_support_20260702_200455`
- repo_sample_visual_output: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\detection_dropout_temporal_sar_support\detection_dropout_temporal_sar_support_20260702_200455`
