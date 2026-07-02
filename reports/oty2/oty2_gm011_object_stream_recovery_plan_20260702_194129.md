# GM_RM011 OTY 光学对象流补建计划

生成时间：`20260702_194129`

## 当前状态

- GM_RM011 GT 总数：`201`。
- 缺当前 OTY 光学对象流、但有 SAR GT 和 review 光学框：`195`。
- SAR-only：`6`。

这 195 条不是没有标注，也不是 SAR GT 不可用；它们只是当前 OTY2 链条里没有 GM_RM011 的对象级光学流，因此不能进入对象级光学-SAR correspondence。

## 未补流前 GM_RM011 可用于什么

- 可用于全量 GT 库存统计。
- 可用于 SAR-only 或 SAR 侧物理尺度、散射形态、GT 框尺度分布分析。
- 可用于场景级时间元数据说明。
- 不应用于光学对象到 SAR GT 的对应机制审计。
- 不应用于 runtime prior construction，也不应用于 selector、阈值或自动标注建议。

## 补进 OTY 链条的建议步骤

1. 用与 GM_RM017/GM_RM019 一致的 OTY0/OTY1/OTY1t 检测、聚类、跟踪和对象假设逻辑处理 GM_RM011 光学帧。
2. 生成 GM_RM011 的对象级输出，至少包括 `oty1t_object_frame_state_timeseries_generalized.csv` 所需字段：scene、object_hypothesis_id、optical_frame_num、primary bbox、secondary bbox summary、状态标签、review_required 和 runtime_source_policy。
3. 保持构造阶段 runtime-safe：补流时不要使用 SAR GT、SAR 图像内容、后验 IoU 或人工最终框作为对象流构造依据。
4. 补流后重新运行 `tools/diagnostics/run_oty2_gt_sample_accounting_audit.py`，确认 `blocked_missing_gm011_object_stream` 是否下降，并检查是否新增 `paired_optical_object_sar_gt` 或 `no_oty_iou_match`。
5. 只有 accounting 通过后，才重新运行 GT correspondence mechanism audit；机制审计仍应声明 GT/SAR 只用于 posthoc discovery。

## 复跑命令建议

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_gt_sample_accounting_audit.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_gt_correspondence_mechanism_audit.py
```

## 数据源

- gt_sample_accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- object_frame_state_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv`
- object_hypotheses_csv: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_hypotheses_generalized.csv`
- local_full_visual_output: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_no_oty_iou_match_triage_20260702_194129`
- repo_sample_visual_output: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\no_oty_iou_match_triage\no_oty_iou_match_triage_20260702_194129`
