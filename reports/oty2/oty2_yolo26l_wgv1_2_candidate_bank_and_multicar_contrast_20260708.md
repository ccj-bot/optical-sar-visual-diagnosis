# OTY2 YOLO26l WGV1.2 candidate bank and multicar contrast gate

日期：2026-07-08

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

主题：把 YOLO26l WGV1.2 从 selected-box 片段推进到候选池对照和同车合并门控。

## 结论

当前不能继续把单个 selected box 序列直接合并为同一辆车。WGV1.1 中 02、13、16、17、18 等 review folder 把 truck/car、白车/黑车、左侧/右侧目标混在一起，根因不是简单的 detector class 错，而是候选构造层只保留了主选框，缺少同一帧其他车辆候选的对照，导致同车边在多车场景中跨目标跳接。

本轮新增 per-frame candidate bank 和 multicar merge gate。机制上现在要求：

1. 先检查前后 bbox 序列是否连续，不能有过大的中心跳变、面积跳变、类别切换或来回跳。
2. 再检查同帧多车候选池是否完整，避免把一个 selected primary 误当成唯一车辆。
3. 候选池缺失或只有 selected manifest fallback 时，不允许自动合并，只能进入人工复核或 blocked。
4. 所有结果仍然是 diagnostic only，不是 final box，不是 revised annotation，也不是 SAR-ready evidence。

## 输入

- `reports/oty2/samples/oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_target_family_candidates_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_same_vehicle_merge_candidates_20260708.csv`
- `outputs/oty2/gm_rm011_237_270_visible_unboxed_vehicle_gap_yolo26l_sensitivity_20260706/yolo26l_local_detection_table.csv`

最后一个文件是 ignored output，只作为局部 raw all-candidate 诊断输入，不提交。

## 新增输出

- `reports/oty2/samples/oty2_yolo26l_wgv1_2_per_frame_candidate_bank_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_candidate_bank_coverage_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_target_family_multicar_contrast_20260708.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_2_merge_candidate_multicar_gate_20260708.csv`
- `tools/diagnostics/build_oty2_yolo26l_wgv1_2_candidate_bank.py`

这些 CSV 是轻量诊断表，不包含图像、视频、数组、pickle、权重或 final/GT/revised annotation。

行数：

- per-frame candidate bank：230 rows
- candidate bank coverage：5 rows
- target-family multicar contrast：32 rows
- merge candidate multicar gate：26 rows

## Candidate bank 覆盖状态

| window_id | scene_id | frames | coverage_status | raw all-candidate frames | selected-only frames | competing frames | 结论 |
|---|---|---:|---|---:|---:|---:|---|
| GM_RM011_000_035 | GM_RM011 | 0-35 | selected_manifest_only | 0/36 | 30 | 0 | 不能做多车安全合并 |
| GM_RM011_135_166 | GM_RM011 | 135-166 | selected_manifest_only | 0/32 | 30 | 0 | 不能做多车安全合并 |
| GM_RM011_231_292 | GM_RM011 | 231-292 | partial_all_candidate_available | 30/62 | 17 | 19 | 局部可做候选对照，其余仍 blocked |
| GM_RM011_237_270_visible_gap_focus | GM_RM011 | 237-270 | partial_all_candidate_available | 30/34 | 0 | 19 | 可用于诊断 visible_unboxed_vehicle_gap，但缺 240、241、267、268 |
| GM_RM017_118_214 | GM_RM017 | 118-214 | selected_manifest_only | 0/97 | 97 | 0 | 不能自动解决 truck/car、白车/黑车混淆 |

`GM_RM017 118-214` 在 candidate bank 中去重后有 97 条 selected manifest fallback rows，但没有 raw all-candidate table。也就是说，它能说明“当前每帧选中了哪个候选”，不能说明“同一帧是否还有其他车更应该被跟随”。这就是 GM17 truck/car 和白车/黑车会被混淆的机制原因。

## Target-family 多车对照状态

共 32 个 target-family fragments：

- 25 个 `contrast_missing_selected_manifest_only`
- 1 个 `partial_all_candidate_contrast_available`
- 6 个 `all_candidate_contrast_available`

因此，多数 target-family 目前只能说“自身序列是否相对平滑”，还不能证明“它没有和同帧另一辆车混淆”。这些 fragment 不应该进入自动同车合并。

## Same-vehicle merge gate

共 26 条 same-vehicle merge candidates：

- 15 条 `blocked`：已经被前后中心偏移、空间跳变或端点规则阻断。
- 10 条 `blocked_auto_merge_contrast_missing`：时序上可能可疑或 review_only，但缺少完整同帧多车候选对照，不允许自动合并。
- 1 条 `review_only_competing_candidates_present`：`GM_RM011_WGV12M014`，从 `GM_RM011_WGV12TF017` 到 `GM_RM011_WGV12TF018`，frame 266 到 269。它有 all-candidate 对照，但同帧存在 competing candidates，所以仍必须人工复核。

所有 merge candidate 的 `auto_merge_allowed` 都是 `no`，`sar_ready` 都是 `no / blocked`。

## 机制优化

### 已经完成

1. 将目标表达拆成 target-family fragments，避免把明显跳变的片段硬塞进同一辆车。
2. 将序列连续性显式门控化：中心偏移、面积比、类别切换、source_detection_id 重用、来回跳都可以阻断同车合并。
3. 新增 per-frame candidate bank，把 raw all-candidate rows 和 selected manifest fallback 分开标记。
4. 新增 multicar merge gate。缺少完整候选池对照时，不允许自动合并。

### 当前还没完成

当前还没有形成“单一真实车辆的完整时序”。更准确地说，现在做到的是：

- 能识别哪些 WGV1.1 vehicle group 是错误混合。
- 能把部分窗口拆成较安全的 target-family fragments。
- 能给出同车 merge candidates。
- 能阻断明显不安全的 merge。
- 能指出哪些 merge 因为缺少多车候选池而不能决策。

但还不能把这些 fragment 自动合并成最终单车时序，因为 GM_RM011 0-35、135-166 和 GM_RM017 118-214 仍缺少 raw all-candidate 候选池。

## 对最终目标的影响

最终目标是把小窗车辆观察片段合并成单一车辆的完整时序。要做到这一点，不能只依赖前后 selected box，还必须同时利用：

- 前后 bbox 中心连续性；
- bbox 尺寸和面积连续性；
- 类别一致性；
- source_detection_id 不重复穿插；
- 同帧多车候选对照；
- 左/中/右空间槽位稳定性；
- 多车竞争关系和遮挡上下文。

本轮工作把这些信息从“说明性规则”推进成了可执行的诊断门控表，但候选池覆盖还不够完整，所以不能宣称 full vehicle timeline construction 完成。

## 下一步

最小下一步不是进入 SAR，也不是生成 final boxes，而是只在当前关键窗口内补齐 YOLO26l raw all-candidate detection tables：

1. `GM_RM011 0-35`
2. `GM_RM011 135-166`
3. `GM_RM011 231-292` 中缺失的非 237-270 帧
4. `GM_RM017 118-214`

补齐后重新运行 candidate bank 和 merge gate，再生成新的 vehicle-centric review pack。新的 review pack 不应再把 `blocked_auto_merge_contrast_missing` 或 `blocked` 的 fragments 放进同一个 vehicle_group；只允许把序列连续且多车候选对照充分的 pair 放入人工同车验收候选。

## 边界

本轮没有生成 final boxes、GT boxes、final/revised annotation。

本轮没有进入 SAR pairing/support/selector/ranking。

本轮没有提交 outputs、图片、视频、权重、数组、pickle 或压缩包。
