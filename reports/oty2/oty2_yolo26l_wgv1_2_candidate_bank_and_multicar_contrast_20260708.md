# OTY2 YOLO26l WGV1.2 candidate bank and multicar contrast gate

日期：2026-07-08

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

主题：把 YOLO26l WGV1.2 从 selected-box 片段推进到候选池对照、同车合并门控和自监督策略修正。

## 结论

当前不能继续把单个 selected box 序列直接合并为同一辆车。WGV1.1 中 02、13、16、17、18 等 review folder 把 truck/car、白车/黑车、左侧/右侧目标混在一起，根因不是简单的 detector class 错，而是候选构造层只保留了主选框，缺少同一帧其他车辆候选的对照，导致同车边在多车场景中跨目标跳接。

本轮新增并修正 per-frame candidate bank 和 multicar merge gate。机制上现在要求：

1. 先检查前后 bbox 序列是否连续，不能有过大的中心跳变、面积跳变、类别切换或来回跳。
2. 再检查同帧多车候选池是否完整，避免把一个 selected primary 误当成唯一车辆。
3. 候选池缺失或只有 selected manifest fallback 时，不允许自动合并，只能进入人工复核或 blocked。
4. 所有结果仍然是 diagnostic only，不是 final box，不是 revised annotation，也不是 SAR-ready evidence。

## 自监督策略修正

上一版判断认为多数关键窗口缺少 raw all-candidate 候选表，因此不能做完整多车对照。这个判断过窄：脚本当时只读取了 `GM_RM011 237-270` 的局部 sensitivity 表，没有复用已经存在的 full-scene YOLO26l probe 表。

本轮重新检查后确认已有 ignored probe 表：

- `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv`
- `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv`

其中 `GM_RM011` full-scene 表裁剪到 `237-270` 后，与局部 sensitivity 表同为 52 rows、30 个有 detection 的帧。因此当前策略改为：复用 full-scene probe 表，只裁剪当前关键窗口内的 raw all-candidate rows，不重新运行 YOLO，不扩展到全数据集。

这次修正后的核心判断也随之改变：

- 不是“多数窗口缺少 raw candidate 表”；
- 而是“关键窗口已有 raw candidate 表后，几乎所有 target-family 都存在同帧 competing candidates，因此仍不能自动合并”。

## 输入

- `reports/oty2/samples/oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_target_family_candidates_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_same_vehicle_merge_candidates_20260708.csv`
- `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv`
- `outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv`

最后两个文件是 ignored outputs，只作为 bounded diagnostic candidate bank 输入，不提交。

## 新增输出

- `reports/oty2/samples/oty2_yolo26l_wgv1_2_per_frame_candidate_bank_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_candidate_bank_coverage_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_target_family_multicar_contrast_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_merge_candidate_multicar_gate_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_same_vehicle_merge_review_queue_20260708.csv`
- `tools/diagnostics/build_oty2_yolo26l_wgv1_2_candidate_bank.py`

这些 CSV 是轻量诊断表，不包含图像、视频、数组、pickle、权重或 final/GT/revised annotation。

行数：

- per-frame candidate bank：441 rows
- candidate bank coverage：5 rows
- target-family multicar contrast：32 rows
- merge candidate multicar gate：26 rows
- same-vehicle merge review queue：11 rows

## Candidate bank 覆盖状态

| window_id | scene_id | frames | coverage_status | raw table frames | raw candidate frames | selected-only frames | competing frames | 结论 |
|---|---|---:|---|---:|---:|---:|---:|---|
| GM_RM011_000_035 | GM_RM011 | 0-35 | raw_table_available_for_window | 36/36 | 36 | 0 | 33 | raw 表完整，但同帧竞争强，不能自动合并 |
| GM_RM011_135_166 | GM_RM011 | 135-166 | raw_table_available_for_window | 32/32 | 31 | 0 | 24 | frame 162 无 detection row，其他帧竞争明显 |
| GM_RM011_231_292 | GM_RM011 | 231-292 | raw_table_available_for_window | 62/62 | 58 | 0 | 39 | raw 表完整，240、241、267、268 无 detection row |
| GM_RM011_237_270_visible_gap_focus | GM_RM011 | 237-270 | raw_table_available_for_window | 34/34 | 30 | 0 | 19 | 仍可诊断 visible_unboxed_vehicle_gap，但缺检帧必须保留 |
| GM_RM017_118_214 | GM_RM017 | 118-214 | raw_table_available_for_window | 97/97 | 97 | 0 | 61 | raw 表完整，truck/car 和多车竞争非常强 |

`raw table frames` 表示该帧有 YOLO26l raw all-candidate 表作为对照；`raw candidate frames` 表示该帧实际有 detection row。没有 detection row 不能自动解释成同车断开，也不能解释成可合并，只能记录为 detector-detectionless context。

`GM_RM017 118-214` 现在不是缺 raw 表，而是 raw 表明确显示多车竞争严重：97 个窗口帧都有 raw table，207 条 raw candidate rows，其中 110 条是 competing candidates。truck/car 和白车/黑车混淆的机制原因因此更清楚：selected primary 在多车环境中会跨空间槽位和类别竞争目标跳转，必须用全候选对照来阻断自动合并。

## Target-family 多车对照状态

共 32 个 target-family fragments：

- 32 个 `all_candidate_contrast_available`

但这不表示 32 个 target-family 都安全。相反，所有 32 个 target-family 都需要先审阅 competing candidates：

- `GM_RM011`：111 selected primary rows，123 competing candidate rows。
- `GM_RM017`：97 selected primary rows，110 competing candidate rows。

因此当前证据支持“可以进行更细的人工同车指称验收”，不支持“自动合并为完整单车时序”。

## Same-vehicle merge gate

共 26 条 same-vehicle merge candidates：

- 15 条 `blocked`：已经被前后中心偏移、空间跳变或端点规则阻断。
- 11 条 `review_only_competing_candidates_present`：序列/端点未硬阻断，但两侧 target-family 至少一侧存在同帧 competing candidates，所以必须人工复核。

所有 merge candidate 的 `auto_merge_allowed` 都是 `no`，`sar_ready` 都是 `no / blocked`。

## Same-vehicle merge review queue

从 merge gate 中抽取 11 条未被时序/端点硬阻断、但存在 competing candidates 的人工复核项：

- `GM_RM011`：8 条
- `GM_RM017`：3 条

这些条目不是 accepted same-vehicle edges，只是下一版 vehicle-centric review pack 的候选审阅清单。每条都要求人工同时看 selected primary 和同帧 competing candidates，再判断 from/to target-family 是否保持同一辆真实车的指称。

输出文件：

```text
reports/oty2/samples/oty2_yolo26l_wgv1_2_same_vehicle_merge_review_queue_20260708.csv
```

## 机制优化

### 已经完成

1. 将目标表达拆成 target-family fragments，避免把明显跳变的片段硬塞进同一辆车。
2. 将序列连续性显式门控化：中心偏移、面积比、类别切换、source_detection_id 重用、来回跳都可以阻断同车合并。
3. 新增 per-frame candidate bank，把 raw all-candidate rows 和 selected manifest fallback 分开标记。
4. 修正 candidate bank 默认输入，复用已有 GM_RM011 / GM_RM017 full-scene YOLO26l probe 表。
5. 新增 multicar merge gate。即使候选池完整，只要同帧竞争目标存在，也不允许自动合并。

### 当前还没完成

当前还没有形成“单一真实车辆的完整时序”。更准确地说，现在做到的是：

- 能识别哪些 WGV1.1 vehicle group 是错误混合。
- 能把部分窗口拆成较安全的 target-family fragments。
- 能给出同车 merge candidates。
- 能阻断明显不安全的 merge。
- 能指出哪些 merge 因为同帧 competing candidates 或时序端点失败而不能自动决策。

但还不能把这些 fragment 自动合并成最终单车时序。当前 blocker 已经不是 raw all-candidate 表缺失，而是多车竞争证据显示：许多 fragment 周围存在同帧竞争框、类别竞争、空间槽位竞争和短时跳转风险。

## 对最终目标的影响

最终目标是把小窗车辆观察片段合并成单一车辆的完整时序。要做到这一点，不能只依赖前后 selected box，还必须同时利用：

- 前后 bbox 中心连续性；
- bbox 尺寸和面积连续性；
- 类别一致性；
- source_detection_id 不重复穿插；
- 同帧多车候选对照；
- 左/中/右空间槽位稳定性；
- 多车竞争关系和遮挡上下文。

本轮工作把这些信息从“说明性规则”推进成了可执行的诊断门控表，并补上了关键窗口的 raw all-candidate 对照。现在不能宣称 full vehicle timeline construction 完成，原因不是缺少候选池，而是候选池证明多车竞争强，必须进入更细的人工同车指称验收。

## 下一步

最小下一步不是进入 SAR，也不是生成 final boxes，而是基于当前 441-row candidate bank 和 11-row merge review queue 生成新的 vehicle-centric review pack：

1. 每个 review-only merge candidate 必须同时显示 from/to target-family 的 selected primary 和 competing candidates。
2. 每个 blocked merge candidate 只作为上下文记录，不放入同一 vehicle_group。
3. 每个 vehicle_group 文件夹必须按 target-family 和同帧 competing candidates 展开，避免只给人工看 selected primary。
4. GM_RM017 的 truck/car、白车/黑车竞争必须在 review pack 中显式分轨展示，不能再混成单一车辆组。
5. 所有内容仍然保持 diagnostic only，`sar_ready=no / blocked`。

## 边界

本轮没有生成 final boxes、GT boxes、final/revised annotation。

本轮没有进入 SAR pairing/support/selector/ranking。

本轮没有提交 outputs、图片、视频、权重、数组、pickle 或压缩包。
