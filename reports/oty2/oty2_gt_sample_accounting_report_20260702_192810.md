# OTY2 GT 样本账本审计报告

生成时间：`20260702_192810`

本轮只做 GT 样本 accounting，不继续做机制分层验证。脚本读取 GT 表、review queue 和已有 OTY 输出；不读取 SAR 图像，不生成自动标注建议，不训练或调阈值，也不把 GT 写入 runtime prior construction。

## 总账结论

- 全部 GT 标注总数：`442`。
- 每个场景 GT 数：`{"GM_RM011": 201, "GM_RM017": 216, "GM_RM019": 25}`。
- 每个类别数量：`{"paired_optical_object_sar_gt": 215, "blocked_missing_gm011_object_stream": 195, "sar_only_gt": 20, "missing_review_optical_bbox": 0, "no_oty_iou_match": 12, "other_unclassified_blocker": 0}`。
- 当前成功配对样本：`215`。
- SAR-only GT：`20`。
- GM_RM011 缺当前 OTY 光学对象流：`195`。
- no_oty_iou_match：`12`。
- missing_review_optical_bbox：`0`。
- other_unclassified_blocker：`0`。

这 442 条样本被完整分账；`paired_optical_object_sar_gt + blocked_missing_gm011_object_stream + sar_only_gt + no_oty_iou_match + missing_review_optical_bbox + other_unclassified_blocker` 等于全部 GT 数。

## 215/442 的含义

`215` 不是总标注数，也不代表只有 215 条 SAR GT。它只是当前可用于“光学对象—SAR GT 后验机制审计”的成功配对子集：同一场景、同一光学帧、review 光学框与当前 OTY 对象帧主观测框 IoU 达到 `0.05` 的样本。

## 类别解释

- `paired_optical_object_sar_gt`：成功建立光学对象和 SAR GT 的后验对应样本；可用于本轮后验机制审计，但不是身份真值，也不是 runtime prior 输入。
- `blocked_missing_gm011_object_stream`：GM_RM011 有 SAR GT，也有 review 光学框，但当前缺 OTY 光学对象流；这不是没有标注，后续补建 GM011 对象流后可重新进入配对。
- `sar_only_gt`：SAR-only 标注，不能用于光学—SAR 对应机制；但应该保留用于 SAR-only 目标尺度、散射强度和形态统计。
- `missing_review_optical_bbox`：非 SAR-only 样本缺 review 光学框或光学对应字段；本次为单独类别，不再和 SAR-only 混在一起。
- `no_oty_iou_match`：有 review 光学框，也有当前 OTY 对象帧候选，但没有任何主观测框达到 IoU `0.05`；需要单独做匹配失败诊断。
- `other_unclassified_blocker`：其他原因；如果非零，需要逐条解释。

## 场景分账

| scene | category_counts |
| --- | --- |
| GM_RM011 | `{"paired_optical_object_sar_gt": 0, "blocked_missing_gm011_object_stream": 195, "sar_only_gt": 6, "missing_review_optical_bbox": 0, "no_oty_iou_match": 0, "other_unclassified_blocker": 0}` |
| GM_RM017 | `{"paired_optical_object_sar_gt": 199, "blocked_missing_gm011_object_stream": 0, "sar_only_gt": 11, "missing_review_optical_bbox": 0, "no_oty_iou_match": 6, "other_unclassified_blocker": 0}` |
| GM_RM019 | `{"paired_optical_object_sar_gt": 16, "blocked_missing_gm011_object_stream": 0, "sar_only_gt": 3, "missing_review_optical_bbox": 0, "no_oty_iou_match": 6, "other_unclassified_blocker": 0}` |

## no_oty_iou_match 样例索引

| scene | sar_gt_id | sar_frame | optical_frame | best_oty_iou | best_oty_object_hypothesis_id | oty_frame_candidate_count |
| --- | --- | --- | --- | --- | --- | --- |
| GM_RM017 | 97 | 310 | 149 | 0.018733 | oty1t_obj_GM_RM017_bytetrack_bt_0008 | 4 |
| GM_RM017 | 263 | 381 | 183 | 0 |  | 4 |
| GM_RM017 | 266 | 382 | 183 | 0 |  | 4 |
| GM_RM017 | 275 | 385 | 185 | 0 |  | 4 |
| GM_RM017 | 278 | 386 | 185 | 0 |  | 4 |
| GM_RM017 | 308 | 446 | 214 | 0 |  | 1 |
| GM_RM019 | 313 | 8 | 4 | 0 |  | 3 |
| GM_RM019 | 321 | 88 | 42 | 0 |  | 6 |
| GM_RM019 | 322 | 202 | 97 | 0 |  | 3 |
| GM_RM019 | 329 | 306 | 147 | 0 |  | 1 |
| GM_RM019 | 332 | 350 | 168 | 0.023328 | oty1t_obj_GM_RM019_bytetrack_bt_0111 | 2 |
| GM_RM019 | 333 | 354 | 170 | 0 |  | 1 |

这些样本不是 SAR-only，也不是缺 GT；它们需要下一轮单独 triage：检查 review 光学框、OTY 主观测框、对象流断裂、重复框或 handoff 是否导致 IoU 低。

## SAR-only 样例索引

| scene | sar_gt_id | sar_frame | target_identity |
| --- | --- | --- | --- |
| GM_RM017 | 96 | 302 | saronly_gm_rm017_000145_000302_01 |
| GM_RM017 | 281 | 387 | saronly_gm_rm017_000186_000387_01 |
| GM_RM017 | 284 | 388 | saronly_gm_rm017_000186_000388_02 |
| GM_RM017 | 287 | 389 | saronly_gm_rm017_000187_000389_01 |
| GM_RM017 | 290 | 390 | saronly_gm_rm017_000187_000390_02 |
| GM_RM017 | 293 | 391 | saronly_gm_rm017_000188_000391_01 |
| GM_RM017 | 296 | 392 | saronly_gm_rm017_000188_000392_02 |
| GM_RM017 | 299 | 393 | saronly_gm_rm017_000189_000393_01 |
| GM_RM017 | 302 | 394 | saronly_gm_rm017_000189_000394_01 |
| GM_RM017 | 304 | 429 | saronly_gm_rm017_000206_000429_01 |
| GM_RM017 | 306 | 438 | saronly_gm_rm017_000210_000438_01 |
| GM_RM019 | 310 | 0 | saronly_gm_rm019_000000_000000_01 |

SAR-only 样本仍然有 SAR GT 框，可以进入 SAR-only 物理尺度、散射和形态统计；但它们没有可用的光学对象对应，不应混入 optical-to-SAR correspondence 机制审计。

## missing_review_optical_bbox 样例索引

无。

## 处理建议

1. GM_RM011：不要把 195 条解释成没有标注；应补建或接入 GM_RM011 的 OTY 光学对象流，再重新跑配对账本。
2. SAR-only：保留为 SAR-only morphology/scattering 统计池；不要用于光学—SAR 对应机制。
3. no_oty_iou_match：单独做 12 条匹配失败诊断，优先检查 review 光学框和 OTY 对象帧是否存在坐标系、对象流断裂或 handoff 问题。
4. paired 215：只作为当前后验机制审计配对子集使用，不代表全量 GT。

## Boundary Flags

- gt_table_read: `true`
- review_queue_read: `true`
- existing_oty_outputs_read: `true`
- sar_image_content_read: `false`
- automatic_annotation_proposal_generated: `false`
- training_or_threshold_tuning_entered: `false`
- gt_written_to_runtime_prior_construction: `false`
- candidate_box_scoring_output: `false`
- selector_or_ranking_used: `false`
- identity_truth_claimed: `false`

## 数据源

- final_gt_csv: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv`
- review_queue_csv: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\review_queue.csv`
- object_frame_state_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- previous_gt_mechanism_summary: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_summary_20260702_190435.json`
