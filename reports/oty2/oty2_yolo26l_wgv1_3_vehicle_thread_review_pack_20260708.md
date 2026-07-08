# OTY2 YOLO26l WGV1.3 vehicle-thread review pack

Date: 2026-07-08

## 输出

- ignored review pack: `D:/profile/research/optical-sar-visual-diagnosis/outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708`
- thread manifest: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_manifest_20260708.csv`
- frame manifest: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_frame_manifest_20260708.csv`
- edge frame manifest: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_edge_frame_manifest_20260708.csv`

## 说明

本包按 WGV1.3 vehicle thread candidate 组织，用于人工逐帧验收单车时序合并候选。它复用既有 WGV1.1 fragment render 和 WGV1.2 MRQ edge render，不运行 detector、不运行 tracker replay、不生成 final boxes。

人工审阅时应先看 `frames_yolo/` 的同车连续性，再看 `edge_review_frames/` 的断点和竞争关系。带 `primary_box_selection_issue` 的项目重点判断更高分框是否只是同一辆车上的重复/更优主框。

## 计数

- thread folders: 22
- fragment frame rows: 168
- edge review frame rows: 202

Thread status counts:

- `same_vehicle_thread_candidate_supported_by_tracking_association`: 6
- `same_vehicle_thread_candidate_with_primary_box_selection_issue`: 2
- `standalone_target_family_after_identity_safe_split`: 14

Fragment frame copy status:

- `copied`: 167
- `copied_edge_review_fallback`: 1

Edge frame copy status:

- `copied`: 172
- `missing_existing_edge_review_frame`: 30

## 边界

- 所有内容都是 diagnostic-only。
- 所有 thread 均为 `auto_merge_allowed=no`。
- 所有 thread 均为 `sar_ready=no / blocked`。
- 未生成 final boxes、GT boxes、revised annotation。
- 未进入 SAR pairing/support/selector/ranking。
- 图片只写入 ignored outputs，不提交。
