# OTY2 YOLO26l WGV1.3 identity-safe temporal merge candidates

Date: 2026-07-08

## 本阶段结论

WGV1.3 将 WGV1.2 的 guardrail / MRQ 结果推进为 identity-safe target-family split 和可人工验收的单车时序合并候选。核心变化是：多车竞争不再作为粗门控直接阻断，而是先用 tracking-style association 判断更高分候选是同车重复框，还是空间上分离的另一辆车。

本产物仍然严格是 diagnostic-only：不生成 final boxes、GT boxes、revised annotation，不进入 SAR，也不声明任何 thread SAR-ready。

- target-family split: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_3_identity_safe_target_family_split_20260708.csv`
- single-vehicle merge candidates: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_3_single_vehicle_temporal_merge_candidates_20260708.csv`
- vehicle thread candidates: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_3_vehicle_thread_candidates_20260708.csv`

## 计数

- target families: 32
- merge candidates: 26
- vehicle thread candidates: 22
- multi-fragment thread candidates: 8
- primary-box selection issue threads: 2
- identity split boundary edges: 16

Edge decision counts:

- `identity_safe_same_vehicle_candidate_with_primary_box_selection_issue`: 2
- `identity_safe_same_vehicle_thread_candidate`: 8
- `identity_split_boundary_blocked_by_wgv1_2`: 15
- `identity_split_boundary_spatially_distinct_competitor`: 1

Thread status counts:

- `same_vehicle_thread_candidate_supported_by_tracking_association`: 6
- `same_vehicle_thread_candidate_with_primary_box_selection_issue`: 2
- `standalone_target_family_after_identity_safe_split`: 14

Scene thread counts:

- `GM_RM011`: 13
- `GM_RM017`: 9

## 机制解释

WGV1.3 的判定顺序是：

1. 先保留 WGV1.2 已经 blocked 的边作为 identity split boundary。
2. 对 MRQ review-only 边使用 tracking-style association。
3. 如果 endpoint overlap / IoMin / normalized motion 支持同车，且 proposed to-target 是最佳局部延续，则放入同车 thread candidate。
4. 如果最佳局部候选不是 proposed to-target，但二者在同一帧压在同一辆车上，则记录 `same_object_better_box_primary_selection_issue`，仍允许放入同车 thread candidate，后续只修正诊断主框选择。
5. 如果最佳局部候选空间上分离，或原始边已经 blocked，则不合并，作为 split boundary。

这直接回应了前一轮的问题：前后帧框有重叠、光学上落在同一辆车上时，不能因为存在同帧竞争框就拒绝合并候选。应先判断竞争框是否只是同车重复框。只有空间上分离的竞争目标才构成真正的身份拆分证据。

## 可审阅 thread candidates

| thread | scene | frames | target families | included edges | primary-box issue | adjacent split boundaries | status |
|---|---|---|---:|---|---|---|---|
| `GM_RM011_WGV13T001` | GM_RM011 | 0-9 | 2 | `GM_RM011_WGV12M001` | `` | `GM_RM011_WGV12M002` | `same_vehicle_thread_candidate_supported_by_tracking_association` |
| `GM_RM011_WGV13T002` | GM_RM011 | 10-25 | 3 | `GM_RM011_WGV12M003;GM_RM011_WGV12M004` | `GM_RM011_WGV12M003` | `GM_RM011_WGV12M002;GM_RM011_WGV12M005` | `same_vehicle_thread_candidate_with_primary_box_selection_issue` |
| `GM_RM011_WGV13T003` | GM_RM011 | 31-35 | 1 | `` | `` | `GM_RM011_WGV12M005` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM011_WGV13T005` | GM_RM011 | 151-166 | 2 | `GM_RM011_WGV12M006` | `` | `` | `same_vehicle_thread_candidate_supported_by_tracking_association` |
| `GM_RM011_WGV13T006` | GM_RM011 | 231-232 | 1 | `` | `` | `GM_RM011_WGV12M007` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM011_WGV13T007` | GM_RM011 | 233-239 | 2 | `GM_RM011_WGV12M008` | `` | `GM_RM011_WGV12M007;GM_RM011_WGV12M009` | `same_vehicle_thread_candidate_supported_by_tracking_association` |
| `GM_RM011_WGV13T008` | GM_RM011 | 242-249 | 1 | `` | `` | `GM_RM011_WGV12M009;GM_RM011_WGV12M010` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM011_WGV13T009` | GM_RM011 | 250-250 | 1 | `` | `` | `GM_RM011_WGV12M010;GM_RM011_WGV12M011` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM011_WGV13T010` | GM_RM011 | 251-259 | 1 | `` | `` | `GM_RM011_WGV12M011;GM_RM011_WGV12M012` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM011_WGV13T011` | GM_RM011 | 260-264 | 1 | `` | `` | `GM_RM011_WGV12M012;GM_RM011_WGV12M013` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM011_WGV13T012` | GM_RM011 | 265-288 | 3 | `GM_RM011_WGV12M014;GM_RM011_WGV12M015` | `` | `GM_RM011_WGV12M013;GM_RM011_WGV12M016` | `same_vehicle_thread_candidate_supported_by_tracking_association` |
| `GM_RM011_WGV13T013` | GM_RM011 | 289-292 | 1 | `` | `` | `GM_RM011_WGV12M016` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM017_WGV13T001` | GM_RM017 | 118-148 | 2 | `GM_RM017_WGV12M001` | `` | `GM_RM017_WGV12M002` | `same_vehicle_thread_candidate_supported_by_tracking_association` |
| `GM_RM017_WGV13T002` | GM_RM017 | 149-155 | 1 | `` | `` | `GM_RM017_WGV12M002;GM_RM017_WGV12M003` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM017_WGV13T003` | GM_RM017 | 156-157 | 1 | `` | `` | `GM_RM017_WGV12M003;GM_RM017_WGV12M004` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM017_WGV13T004` | GM_RM017 | 158-168 | 2 | `GM_RM017_WGV12M005` | `GM_RM017_WGV12M005` | `GM_RM017_WGV12M004;GM_RM017_WGV12M006` | `same_vehicle_thread_candidate_with_primary_box_selection_issue` |
| `GM_RM017_WGV13T005` | GM_RM017 | 169-173 | 1 | `` | `` | `GM_RM017_WGV12M006;GM_RM017_WGV12M007` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM017_WGV13T006` | GM_RM017 | 174-175 | 1 | `` | `` | `GM_RM017_WGV12M007;GM_RM017_WGV12M008` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM017_WGV13T007` | GM_RM017 | 176-181 | 1 | `` | `` | `GM_RM017_WGV12M008;GM_RM017_WGV12M009` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM017_WGV13T008` | GM_RM017 | 182-185 | 1 | `` | `` | `GM_RM017_WGV12M009` | `standalone_target_family_after_identity_safe_split` |
| `GM_RM017_WGV13T009` | GM_RM017 | 200-214 | 2 | `GM_RM017_WGV12M010` | `` | `` | `same_vehicle_thread_candidate_supported_by_tracking_association` |

## 仍然 blocked 的内容

以下边界不得被 WGV1.3 自动合并，只能作为人工复核或后续机制改进对象：

| edge | scene | from -> to | frames | decision | reason |
|---|---|---|---|---|---|
| `GM_RM011_WGV12M002` | GM_RM011 | `GM_RM011_WGV12TF002 -> GM_RM011_WGV12TF003` | 9->10 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM011_WGV12M005` | GM_RM011 | `GM_RM011_WGV12TF005 -> GM_RM011_WGV12TF006` | 25->31 | `identity_split_boundary_spatially_distinct_competitor` | `endpoint_center_offset_review;endpoint_spatial_bin_change;endpoint_review_required;class_support;competing_candidate_better_match;normalized_center_too_far;scale_support;spatially_distinct_competing_vehicle;x_bin_change_review;same_frame_competing_candidates_present` |
| `GM_RM011_WGV12M007` | GM_RM011 | `GM_RM011_WGV12TF010 -> GM_RM011_WGV12TF011` | 232->233 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM011_WGV12M009` | GM_RM011 | `GM_RM011_WGV12TF012 -> GM_RM011_WGV12TF013` | 239->242 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM011_WGV12M010` | GM_RM011 | `GM_RM011_WGV12TF013 -> GM_RM011_WGV12TF014` | 249->250 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM011_WGV12M011` | GM_RM011 | `GM_RM011_WGV12TF014 -> GM_RM011_WGV12TF015` | 250->251 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM011_WGV12M012` | GM_RM011 | `GM_RM011_WGV12TF015 -> GM_RM011_WGV12TF016` | 259->260 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM011_WGV12M013` | GM_RM011 | `GM_RM011_WGV12TF016 -> GM_RM011_WGV12TF017` | 264->265 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM011_WGV12M016` | GM_RM011 | `GM_RM011_WGV12TF019 -> GM_RM011_WGV12TF020` | 288->289 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM017_WGV12M002` | GM_RM017 | `GM_RM017_WGV12TF002 -> GM_RM017_WGV12TF003` | 148->149 | `identity_split_boundary_blocked_by_wgv1_2` | `class_mismatch;endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM017_WGV12M003` | GM_RM017 | `GM_RM017_WGV12TF003 -> GM_RM017_WGV12TF004` | 155->156 | `identity_split_boundary_blocked_by_wgv1_2` | `class_mismatch;endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM017_WGV12M004` | GM_RM017 | `GM_RM017_WGV12TF004 -> GM_RM017_WGV12TF005` | 157->158 | `identity_split_boundary_blocked_by_wgv1_2` | `class_mismatch;endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM017_WGV12M006` | GM_RM017 | `GM_RM017_WGV12TF006 -> GM_RM017_WGV12TF007` | 168->169 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM017_WGV12M007` | GM_RM017 | `GM_RM017_WGV12TF007 -> GM_RM017_WGV12TF008` | 173->174 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM017_WGV12M008` | GM_RM017 | `GM_RM017_WGV12TF008 -> GM_RM017_WGV12TF009` | 175->176 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |
| `GM_RM017_WGV12M009` | GM_RM017 | `GM_RM017_WGV12TF009 -> GM_RM017_WGV12TF010` | 181->182 | `identity_split_boundary_blocked_by_wgv1_2` | `endpoint_center_offset_too_large;endpoint_spatial_bin_change;endpoint_review_required;sequence_or_endpoint_gate_already_blocked` |

## 使用边界

- 所有 rows 均为 `auto_merge_allowed=no`。
- 所有 rows 均为 `sar_ready=no / blocked`。
- `same_object_better_box_primary_selection_issue` 只表示诊断主框选择问题，不写新 bbox，不生成 final boxes。
- WGV1.3 thread candidate 只是人工验收入口，不是 identity truth。
- 本阶段未进入 SAR、未运行 tracker replay、未运行 detector swap。
