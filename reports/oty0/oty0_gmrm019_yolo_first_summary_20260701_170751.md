# OTY0 GM_RM019 YOLO-First 审计总结

生成时间：2026-07-01 17:07:51
审计场景：GM_RM019
本地输出目录：`D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_170751`

## 1. 这轮 OTY0 的定位

OTY0 是对自动标注主线的纠偏起点：runtime 输入必须从 raw optical frames 出发，经 YOLO 生成光学检测流，再进入后续 optical tracklet、SAR 高帧率对齐和 SAR fan/range band。已有 `review_queue.csv`、`final_gt_working.csv`、SAR GT、manual/final/oracle 字段只允许作为 posthoc audit inventory，不能生成 runtime detection、tracklet 或 SAR band。

本轮没有进入 selector、G2、A008 scoring、threshold tuning、training，也没有修改正式 pipeline。

## 2. 运行结果

| 项目 | 结果 |
| --- | --- |
| optical frame 总数 | 368 |
| YOLO 权重 | `D:\profile\research\workspace\artifacts\detector_weights\yolo11l.pt` |
| YOLO 是否可运行 | 是 |
| CUDA | 是，`NVIDIA GeForce RTX 5070 Laptop GPU` |
| detection table 是否生成 | 是 |
| detection rows | 334 |
| 有检测的 optical frames | 193 |
| 类别统计 | car=327, bus=6, truck=1 |
| GM_RM011 / GM_RM017 | 仅预留 manifest/config，未默认运行 |

YOLO 输出使用车辆类别过滤：`car`、`truck`、`bus`。这里的 confidence 只是 optical detector 输出过滤条件，不是 SAR selector threshold。

## 3. 主要产物

Git 内新增的可追踪文件：

- `docs/oty_yolo_first_optical_temporal_transfer_plan.md`
- `configs/oty_yolo_stream_config.yaml`
- `manifests/oty0_yolo_manifest.csv`
- `tools/diagnostics/run_oty0_yolo_detection_stream_audit.py`
- `reports/oty0/oty0_gmrm019_yolo_first_summary_20260701_170751.md`

本地输出目录中的运行产物：

- `oty0_yolo_detection_table.csv`：OTY0 的 runtime detection table。
- `oty0_optical_frame_inventory.csv`：光学帧清单。
- `oty0_yolo_dependency_audit.csv`：YOLO、torch、CUDA、权重路径检查。
- `oty0_posthoc_source_inventory.csv`：posthoc CSV 存在性和行数审计。
- `oty0_runtime_posthoc_boundary.md`：runtime/posthoc 边界说明。
- `oty0_detection_field_schema.json`：检测表字段 schema。
- `oty0_summary.json`：机器可读汇总。
- `oty0_report.md`：英文简报。

## 4. 可视化位置

可视化位于：

`D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_170751\visualizations`

包含：

- `yolo_detection_contact_sheet.html`：YOLO 检测样例 contact sheet，可用于快速看检测框是否合理。
- `detection_count_timeseries.svg`：每帧检测数量时间序列。
- `yolo_detection_overlay_samples\`：检测框 overlay 样例图。

## 5. Runtime / Posthoc 边界核查

通过本轮审计确认：

- runtime detection 只来自 raw optical frame 上的 YOLO inference；
- `review_queue.csv` 存在 442 行，其中 GM_RM019 相关 25 行，但只作为 posthoc inventory；
- `final_gt_working.csv` 存在 442 行，其中 GM_RM019 相关 25 行，但只作为 posthoc GT inventory；
- posthoc CSV / SAR GT 未参与 detection table 生成；
- 没有假设 optical frame 编号等于 SAR frame 编号；
- 没有进入 tracking、SAR band transfer、SAR GT coverage 或 annotation proposal。

## 6. 最大 blocker 和下一步

OTY0 本身没有阻塞：YOLO 可运行，GM_RM019 detection table 已生成。

下一步可以进入 OTY1，但边界应保持为：

1. 只从 `oty0_yolo_detection_table.csv` 构造 optical tracklet；
2. 不能用 `review_queue.csv` / `final_gt_working.csv` / SAR GT 生成 runtime tracklet；
3. CSV 和 SAR GT 只能在 OTY1 后做 posthoc coverage/failure audit；
4. SAR 高帧率对齐仍需单独在 OTY2 审计，不能假设 optical/SAR 同帧号一一对应。
