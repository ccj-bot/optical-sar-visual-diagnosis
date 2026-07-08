# OTY2 YOLO26l WGV1.2 Target-Family Split 与单车时序合并候选

日期：`2026-07-08`

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

## 边界

本阶段只生成 optical diagnostic timeline graph 的 V1.2 候选表。它不是 final annotation，不是 revised annotation，不是 final boxes，不是 GT boxes，也不是 SAR-ready evidence。

本轮没有运行新的 YOLO detector，没有运行 tracker replay，没有运行 SAR pairing/support/selector/ranking，没有替换 baseline 主线，也没有提交 outputs 图片/视频/权重/数组/pickle/压缩包。

## 输入

```text
reports/oty2/samples/oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_vehicle_fragments_20260708.csv
reports/oty2/samples/oty2_yolo26l_wgv1_2_sequence_contrast_audit_20260708.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_same_vehicle_edges_20260708.csv
```

## 新增输出

```text
tools/diagnostics/build_oty2_yolo26l_wgv1_2_target_family_split.py
reports/oty2/samples/oty2_yolo26l_wgv1_2_target_family_candidates_20260708.csv
reports/oty2/samples/oty2_yolo26l_wgv1_2_sequence_safe_fragments_20260708.csv
reports/oty2/samples/oty2_yolo26l_wgv1_2_switch_context_events_20260708.csv
reports/oty2/samples/oty2_yolo26l_wgv1_2_same_vehicle_merge_candidates_20260708.csv
```

这些 CSV 都是 diagnostic candidate，不是最终标注。

## 本轮向最终目标推进了什么

最终目标是把小窗合并成单一真实车辆的完整光学时序。V1.2 本轮没有直接完成完整单车时序，但完成了合并前必须有的一层：

```text
V1.1 fragment
-> 按时序连续性和多车冲突拆成 target-family candidates
-> 大跳变 / class switch / context-only item 进入 switch_context_events
-> 只对相邻 target family 生成 review_only / blocked merge candidates
```

这一步的意义是：后续再合并时，不再把 `candidate_node_id` 当成车辆身份，也不再把一个大 fragment 内的 truck/car、白车/黑车、左车/右车串成同一辆车。

## 数量摘要

| 表 | 行数 | 含义 |
| --- | ---: | --- |
| `target_family_candidates` | 32 | 从 V1.1 fragments 内切出的局部目标家族候选。 |
| `sequence_safe_fragments` | 32 | 与 target family 一一对应的短序列候选，用于后续人工审阅或边候选。 |
| `switch_context_events` | 18 | 大跳变、类别切换、context-only / blocked 片段等非同车合并事件。 |
| `same_vehicle_merge_candidates` | 26 | 相邻 target family 的诊断合并候选，只允许 `review_only` 或 `blocked`。 |

当前没有任何 `strong` merge candidate，也没有任何 SAR-ready 项。

## Target-Family Split 规则

本轮使用的切分规则：

- `class_name` 切换，直接切分；
- `center offset > 120 px/frame`，直接切分；
- `normalized offset by bbox width > 0.65`，直接切分；
- `area ratio > 2.5`，直接切分；
- `frame gap > 2`，切分为 sequence gap event；
- `blocked` / `forbidden` / context-only fragment 不进入 target family，直接进入 switch/context event；
- `source_detection_id` 被多个 candidate_node_id 复用时，不单独切断几何连续段，但会标记为 review risk。

这比上一轮更合理：复用说明 candidate_node_id 不可信，但如果 bbox 本身连续，可以先保留为 target-family review candidate，而不是切成一堆单帧。

## 重点窗口结果

### GM_RM011 frames 26-30

原问题：

```text
02_GM_RM011_fragment_GM_RM011_WG11F005_blocked
```

V1.2 结果：

```text
event_id=GM_RM011_WGV12E002
event_type=switch_or_context_event
reason_codes=hard_center_offset_jump;hard_normalized_offset_jump;review_area_ratio_jump;back_and_forth_motion;spatial_bin_transition;multicar_contrast_undercovered;not_vehicle_identity_input
```

解释：

这段不再作为 vehicle fragment 或 target family。它只作为 switch zone / same-frame competition 事件保留，不能进入同车合并。

### GM_RM011 frames 242-264

原片段：

```text
GM_RM011_WG11F013
```

V1.2 拆分：

```text
GM_RM011_WGV12TF013  frames 242-249  x_bin=left/mid
GM_RM011_WGV12TF014  frame 250       singleton review
GM_RM011_WGV12TF015  frames 251-259  x_bin=mid
GM_RM011_WGV12TF016  frames 260-264  x_bin=mid/right
```

关键 break events：

```text
249 -> 250  spatial_jump_target_family_break
250 -> 251  spatial_jump_target_family_break
259 -> 260  spatial_jump_target_family_break
```

对应 merge candidates：

```text
TF013 -> TF014  blocked  endpoint_center_offset_too_large
TF014 -> TF015  blocked  endpoint_center_offset_too_large
TF015 -> TF016  blocked  endpoint_center_offset_too_large
```

解释：

这段开始从 “YOLO26l 看见白车主体” 向 “哪些连续短段可以作为同一目标家族” 推进。V1.2 不再允许把 `242-264` unsplit 地当作一个稳定单车时序。

### GM_RM017 frames 145-158

原问题：

```text
truck / car / truck / car 混在 GM_RM017_WG11F002 内
```

V1.2 拆分：

```text
GM_RM017_WGV12TF002  frames 145-148  class=truck  x_bin=mid
GM_RM017_WGV12TF003  frames 149-155  class=car    x_bin=left
GM_RM017_WGV12TF004  frames 156-157  class=truck  x_bin=right
GM_RM017_WGV12TF005  frame 158       class=car    x_bin=left
```

关键 break events：

```text
148 -> 149  class_switch_target_family_break
155 -> 156  class_switch_target_family_break
157 -> 158  class_switch_target_family_break
```

对应 merge candidates 全部 blocked：

```text
truck(mid) -> car(left)     blocked
car(left)  -> truck(right)  blocked
truck(right) -> car(left)   blocked
```

解释：

这回答了“为什么 truck 和 car 会混淆”：不是因为它们应该合并，而是 V1.1 把一个候选检测流误包装成一个车辆片段。V1.2 已把它拆成不同 target family，并禁止直接同车合并。

### GM_RM017 frames 164-185

原问题：

```text
白车 / 黑车主体在 GM_RM017_WG11F004 内混淆
```

V1.2 拆分：

```text
GM_RM017_WGV12TF006  frames 164-168  x_bin=left
GM_RM017_WGV12TF007  frames 169-173  x_bin=mid/right
GM_RM017_WGV12TF008  frames 174-175  x_bin=mid
GM_RM017_WGV12TF009  frames 176-181  x_bin=right
GM_RM017_WGV12TF010  frames 182-185  x_bin=mid/right
```

关键 break events：

```text
168 -> 169  spatial_jump_target_family_break
173 -> 174  spatial_jump_target_family_break
175 -> 176  spatial_jump_target_family_break
181 -> 182  spatial_jump_target_family_break
```

对应 merge candidates 全部 blocked：

```text
TF006 -> TF007  blocked
TF007 -> TF008  blocked
TF008 -> TF009  blocked
TF009 -> TF010  blocked
```

解释：

这回答了“为什么白车和黑车会混淆”：`class_name=car` 不能区分白车/黑车，必须用空间侧、连续运动和同帧多车对照。V1.2 已先按大跳变切开，不允许自动合并。

## 当前仍然缺什么

当前最大缺口是：

```text
per-frame all-candidate vehicle bank 不完整
```

很多帧有 `multi_box_competition` 风险，但 committed manifest 只保留了 selected candidate，而不是该帧所有车辆候选。因此多数 target family 仍然是：

```text
review_required_multicar_contrast_undercovered
```

这意味着：几何上看起来连续的短段，也不能自动合并成同车，必须先补足同帧多车对照，或进入人工审阅。

## 下一步建议

下一步应在 diagnostic-only 边界内生成 per-frame candidate bank：

```text
scene_id
frame_id
all_vehicle_candidate_boxes
source_detection_id
class_name
confidence
bbox
x_bin
candidate_role=selected_primary / competing_candidate
target_family_candidate_id
not_final_box_flag=yes
not_SAR_ready_flag=yes
```

然后重新运行 V1.2 target-family split，使每个 target family 的合并判断能回答：

```text
是否存在另一个同帧候选比当前 selected box 更符合前后时序？
```

这一步完成后，才适合生成下一版 vehicle-centric review pack。

## 结论

```text
YOLO26l WGV1.2 has advanced from raw fragment review to diagnostic target-family split and review-only merge candidates; complete single-vehicle optical timelines are still blocked by missing all-candidate multicar contrast.
```

所有结果仍为：

```text
SAR-ready = no / blocked
```
