# OTY1 GM_RM017 Optical Tracklet 审计总结

生成时间：2026-07-01T18:13:47
审计场景：GM_RM017
本地输出目录：`outputs\oty1_optical_tracklet_audit_20260701_181347`

## 1. 本轮定位

OTY1 只从 OTY0 的 YOLO detection table 构造 optical tracklet candidate 和 optical state stream。它不是自动标注完成态，也不是 SAR band、SAR GT coverage 或 selector/ranker。

## 2. 输入边界

- Runtime 输入：`outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv`
- 禁止用于 runtime：`review_queue.csv`、`final_gt_working.csv`、SAR GT、final/manual/oracle/review 字段。
- 没有假设 optical frame number 等于 SAR frame number。

## 3. 关键统计

| 项目 | 数值 |
| --- | ---: |
| total detections | 215 |
| total optical frames | 368 |
| frames with detections | 100 |
| candidate edge rows | 1050 |
| within-limit edge rows | 916 |
| tracklet candidate count | 10 |
| high-confidence geometry-only candidate count | 0 |
| ambiguous tracklet count | 6 |
| fragmented short track count | 4 |
| same-frame conflict count | 0 |
| neighbor ambiguity count | 28 |
| boundary contact count | 93 |

Component size distribution：`{"1": 4, "4": 1, "10": 1, "43": 1, "48": 1, "52": 1, "54": 1}`

## 4. 主要产物

- `oty1_tracklet_candidate_edges.csv`：候选 edge，edge 是 audit candidate，不是 same-target proof。
- `oty1_optical_tracklet_components.csv`：geometry-only component 汇总。
- `oty1_optical_tracklet_state_timeseries.csv`：带 tracklet candidate id 的 optical state stream。
- `oty1_tracklet_quality_audit.csv`：短轨迹、歧义、边界接触和冲突标记。
- `oty1_runtime_posthoc_boundary.md`：runtime/posthoc 边界。
- `oty1_summary.json` / `oty1_report.md`：机器可读和人读报告。

## 5. 可视化

可视化目录：`outputs\oty1_optical_tracklet_audit_20260701_181347\visualizations`

- `oty1_tracklet_contact_sheet.html`：候选 tracklet strip 入口。
- `oty1_tracklet_timeline.svg`：候选 tracklet 时间线。
- `oty1_tracklet_overlay_samples/`：若干 tracklet candidate 的 optical frame sequence SVG。

可视化只显示 optical frame、YOLO bbox、det_id、frame_num、confidence 和 tracklet_candidate_id；不显示 SAR frame、SAR GT、final box 或 fan/range band。

## 6. Blocker 和下一步

- none

下一步 OTY2 应审计 optical-to-SAR high-FPS temporal alignment：从 OTY1 的 optical state stream 出发，建立 optical 时间轴到 SAR 高帧率时间轴的对齐关系；仍然不能假设同帧号对应，也不能在 OTY2 之前生成 SAR fan/range band。
