# OTY2 光学时序人工验收包（人工填写版）

日期：2026-07-06
仓库：`D:/profile/research/optical-sar-visual-diagnosis`
分支：`feature/oty2-posthoc-mechanism-validation`
来源中文验收包：`reports/oty2/oty2_optical_timeline_human_review_packet_20260706_zh.md`
当前基础 HEAD：`eaeaa6b Add Chinese OTY2 optical timeline review packet`

## 本文件怎么用

本文件是人工填写版。人工优先在本 Markdown 中完成判断，不需要直接编辑 CSV。后续只有勾选“需要生成 override CSV”的项目，才会被提取为 override CSV。

推荐验收顺序：

1. 先看 non-vehicle exclusion，确认这些节点是否确实不是车。
2. 再看 forbidden，确认这些节点关系是否确实不能连接。
3. 再看 strong，确认这些强连接是否确实指向同一辆真实车。
4. 最后看 weak，判断保留弱连接、升级强连接，还是改为禁止连接。

后续流程：

```text
人工填写 Markdown
→ Codex 提取需要 override 的条目
→ 生成 override CSV
→ 运行 validator dry-run
→ 只应用到 diagnostic timeline graph / diagnostic render manifest
```

每条 edge 都是一个独立检查项。先看列出的代表帧 PNG，再按关键帧范围连续翻看快速试渲染帧。如果当前判断不需要改，通常勾选“接受当前结论，无需 override”。只有当前判断需要改、需要显式留痕、或需要标记复核时，才勾选“是”并填写后续 override 字段。

注意：即使选择“仅调整诊断渲染显示”，也只能选择已有 `source_detection_id` 作为诊断渲染主框，不能写新 bbox 坐标，不能生成 final boxes 或 GT boxes。

人工验收要分清三件事：

1. 真实车辆是否在画面中可见。
2. 当前 node / box 是否稳定覆盖了这辆可见车辆。
3. 当前 edge 是否能安全连接两个 node。

如果人眼能看到车辆连续存在，但当前诊断图没有稳定 node / box 表达，不要直接把 edge 改成 strong 或 weak。应标记为 `mark_review_required`，并记录 `visible_unboxed_vehicle_gap`。

## 范围边界

本文件用于指导人工验收当前 optical diagnostic timeline graph。它只基于现有 node table、edge table、render manifest 和 smoke render 诊断帧。

本文件不应用 override，不运行 detector swap，不运行 YOLO probe，不运行 tracker replay，不进入 SAR pairing/support，不运行 selector/ranking，不生成 final/revised annotation，不生成 final boxes，也不生成 GT boxes。

这里的 node 表示节点 / 车辆观察片段；edge 表示边 / 节点关系。所有判断都只服务于诊断用光学时序图和诊断用渲染清单，不是最终标注。

## 来源文件

| 角色 | 路径 | 状态 |
| --- | --- | --- |
| Node table | `reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv` | 18 rows |
| Edge table | `reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv` | 10 rows |
| Render manifest | `reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv` | 311 rows |
| Smoke render frames | `outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames` | 198 ignored PNG frames |
| Override template | `manifests/oty2_optical_timeline_override_template.csv` | header-only template |
| Override schema | `configs/oty2_optical_timeline_override_schema.yaml` | dry-run contract |
| Override validator | `tools/diagnostics/validate_oty2_optical_timeline_overrides.py` | dry-run only |

渲染帧路径规则：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/<scene_id>_<frame:06d>.png
```

示例：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000013.png
```

## 人工判断尺度

| 人工判断 | 含义 | 需要填写 override CSV 时的 action |
| --- | --- | --- |
| 接受当前强连接 | 前后节点在视觉上支持同一辆真实车。 | 不需要填写，或用 `force_strong_connect` 留显式验收记录。 |
| 接受当前弱连接 | 同车指称是合理的，但只能保持弱连接或需要复核标记。 | 不需要填写，或用 `force_weak_connect` 留显式验收记录。 |
| 弱连接升级为强连接 | 全帧上下文足够支持强同车指称。 | `upgrade_to_strong`，并填 `edge_strength=strong`。 |
| 强连接降级为弱连接 | 仍可能是同一辆车，但证据不足以保持强连接。 | `downgrade_to_weak`，并填 `edge_strength=weak`。 |
| 禁止连接 | 前后节点发生目标切换、指向非车辆、或无法排除其他车辆插入。 | `forbid_connect`，并填 `edge_strength=forbidden`。 |
| 标记需要复核 | 人工当前无法安全判断。 | `mark_review_required`，并填 `edge_strength=review_only`。 |
| 可见车辆未被节点/框稳定覆盖 | 人眼可见车辆存在，但当前诊断图没有稳定 node / box 表达。 | `mark_review_required`，`edge_strength=review_only`，优先用 `reason_code=visible_unboxed_vehicle_gap`。 |
| 确认非车辆节点 | 该节点不是车辆观察片段。 | 不需要填写，或用 node `exclude_non_vehicle` 留显式验收记录。 |
| 仅调整诊断渲染显示 | 当前渲染主框误导人工阅读，但已有检测框中有更合适的诊断主框。 | render `select_diagnostic_primary_box`；必须使用已有 `source_detection_id`，不能写新坐标。 |

重要：override row 不是最终标签。它只是在后续明确允许 apply 时，影响诊断用 timeline graph 或诊断用 render manifest。

## override CSV 填写提示

人工不需要直接编辑 CSV。后续会从本 Markdown 中勾选“是否需要生成 override CSV：是”的检查项提取 override CSV。

edge 决策会提取这些 CSV 字段：

```text
override_id,override_type=edge,override_scope=edge,scene_id,from_node_id,to_node_id,action,edge_strength,reason_code,evidence_frame_start,evidence_frame_end,confidence,review_status,note
```

node 决策会提取这些 CSV 字段：

```text
override_id,override_type=node,override_scope=node,scene_id,node_id,action,reason_code,confidence,review_status,note
```

仅用于诊断渲染主框选择时，会提取：

```text
override_id,override_type=render,override_scope=event,scene_id,frame_start,frame_end,target_node_id,action=select_diagnostic_primary_box,source_detection_id,reason_code=diagnostic_primary_box_selection,review_status,note
```

禁止添加 bbox 坐标列。禁止写 final boxes 或 GT boxes。禁止把 override CSV 当成人工逐帧标注表。

`visible_unboxed_vehicle_gap` 是诊断事件，不是人工画框。它只记录“人眼可见车辆存在，但当前诊断图没有稳定 node / box 表达”。它不新增 bbox，不生成 final boxes，不生成 GT boxes，也不生成 final/revised annotation。如果下游 schema 暂时不支持该 `reason_code`，先用 `reason_code=review_uncertain`，并在 `note` 中写 `visible_unboxed_vehicle_gap` 或 `visible-but-unboxed vehicle gap`。

勾选“可见车辆未被节点/框稳定覆盖”时，推荐填写 `override_type=edge`、`action=mark_review_required`、`edge_strength=review_only`、`reason_code=visible_unboxed_vehicle_gap`。如果当前校验器或 schema 暂不支持该 `reason_code`，则填写 `reason_code=review_uncertain`，并在 `note` 中写 `visible_unboxed_vehicle_gap`。

从填写版 Markdown 提取 override CSV 后，用校验器做 dry-run：

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_optical_timeline_overrides.py --overrides manifests\oty2_optical_timeline_override_template.csv
```

## Node / Edge 中文对照索引

`N00x` 是观察片段，不是真实车辆身份。`V00x` 是候选车辆指称，不是 final identity。`FORBIDDEN_CONTEXT` 是禁止连接上下文片段，用来解释为什么不能连，不等于真实车辆身份。人工判断时先看图中车辆是否连续，再看当前 node / box 是否正确表达该车辆，最后才判断当前 edge 能否连接。

### Node 索引

| node_id | 含义 | 帧范围 | 人工阅读提示 |
| --- | --- | --- | --- |
| `GM_RM017_N001` | `GM_RM017_V001` 的观察片段，来源 `bs_0008` | `145-185` | leading dark sedan；注意不要与 `GM_RM017_N003` 混连。 |
| `GM_RM017_N002` | `GM_RM017_V002` 的观察片段，来源 `bs_0010` | `151-200` | white SUV；强同车指称候选。 |
| `GM_RM017_N003` | `GM_RM017_V003` 的观察片段，来源 `bs_0012` | `162-214` | trailing dark sedan；与 `GM_RM017_N001` 是禁止连接关系。 |
| `GM_RM017_N004` | `GM_RM017_V004` 的上下文车辆片段，来源 `bs_0001` | `118-164` | 大白色车/厢式车上下文；不是本轮 edge 检查核心。 |
| `GM_RM017_N005` | `GM_RM017_NONVEHICLE_001`，来源 `bs_0002` | `121-129` | 非车辆排除候选；先确认是否不是车。 |
| `GM_RM011_N001` | `GM_RM011_V001` 的观察片段，来源 `bs_0015 seg_001` | `13-16` | 白车 front/windshield 局部链起点。 |
| `GM_RM011_N002` | `GM_RM011_V001` 的观察片段，来源 `bs_0015 seg_002` | `18-35` | 白车 front/windshield 局部链后段。 |
| `GM_RM011_N003` | `GM_RM011_V002` 的弱观察片段，来源 `bs_0061 seg_001` | `262-270` | 可能同车，但有 part-state transition 和 review 风险。 |
| `GM_RM011_N004` | `GM_RM011_V002` 的观察片段，来源 `bs_0061 seg_002` | `279-281` | 中央白车 front/window 片段。 |
| `GM_RM011_N005` | `GM_RM011_V002` 的观察片段，来源 `bs_0061 seg_003` | `283-292` | 中央白车 front/window 后续片段。 |
| `GM_RM011_N006` | `GM_RM011_FORBIDDEN_CONTEXT_001`，来源 `bs_0064 seg_001` | `283-292` | 左边缘竞争车辆上下文；不是可直接连接身份。 |
| `GM_RM011_N007` | `GM_RM011_FORBIDDEN_CONTEXT_002`，来源 `bs_0056 seg_001` | `256-261` | 侧窗/条带或竞争区域上下文；用于禁止连接判断。 |
| `GM_RM011_N008` | `GM_RM011_V003` 的 review 片段，来源 `bs_0029 seg_001` | `135-161` | 右边缘白车 review 片段。 |
| `GM_RM011_N009` | `GM_RM011_V003` 的 review 片段，来源 `bs_0029 seg_002` | `164-166` | 右边缘 thin crop；可见信息很少。 |
| `GM_RM011_N010` | `GM_RM011_V004` 的弱观察片段，来源 `bs_0044 seg_002` | `231-233` | upper side/window 部位。 |
| `GM_RM011_N011` | `GM_RM011_V004` 的弱观察片段，来源 `bs_0038 seg_002` | `236-245` | front/hood 部位。 |
| `GM_RM011_N012` | `GM_RM011_V005` 的弱观察片段，来源 `bs_0002 seg_001` | `0-4` | 早期 white SUV rear/body。 |
| `GM_RM011_N013` | `GM_RM011_V005` 的弱观察片段，来源 `bs_0007 seg_001` | `8-10` | 早期 upper-window strip。 |

### Edge 索引

| edge_id | 当前类型 | 判断重点 |
| --- | --- | --- |
| `GM_RM017_E002` | `non_vehicle_exclusion` | 判断 `GM_RM017_N005` 是否确实不是车。 |
| `GM_RM017_E001` | `forbidden_edge` | 判断 `GM_RM017_N001` 和 `GM_RM017_N003` 是否是两辆不同深色车。 |
| `GM_RM011_E007` | `forbidden_edge` | 判断 `GM_RM011_N003` 是否不应连到左边缘竞争车辆 `GM_RM011_N006`。 |
| `GM_RM011_E008` | `forbidden_edge` | 判断 `GM_RM011_N007 -> GM_RM011_N003` 是否是错误桥接；同时重点检查是否存在 `visible_unboxed_vehicle_gap`。 |
| `GM_RM011_E001` | `strong_same_vehicle_edge` | 判断 `GM_RM011_N001 -> GM_RM011_N002` 是否确实是同一辆白车。 |
| `GM_RM011_E002` | `strong_same_vehicle_edge` | 判断 `GM_RM011_N004 -> GM_RM011_N005` 是否确实是中央白车连续。 |
| `GM_RM011_E003` | `weak_same_vehicle_edge` | 判断 `GM_RM011_N003 -> GM_RM011_N004` 是否只能弱连接，或需要复核。 |
| `GM_RM011_E004` | `weak_same_vehicle_edge` | 判断右边缘 thin crop 是否只能 review-only。 |
| `GM_RM011_E005` | `weak_same_vehicle_edge` | 判断 upper side/window 到 front/hood 是否是合理弱同车。 |
| `GM_RM011_E006` | `weak_same_vehicle_edge` | 判断早期 rear/body 到 upper-window strip 是否是合理弱同车。 |

## 光学标记短时时序对比提示

人工验收时，每条 edge 都建议分两层看：先看真实车辆在画面中是否连续存在，再看当前诊断框和 node 标识是否稳定覆盖这辆车。只有这两层都说得清楚时，才判断 edge 是 strong、weak、forbidden 还是 review-only。

对 `GM_RM011_E008`，建议额外按以下现有 smoke render 帧做短时时序对比，不需要运行 detector、tracker 或 SAR：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000237.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000245.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000256.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000261.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000263.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000270.png
```

如果上述序列中下方白色车辆人眼连续可见，但 `GM_RM011_N007` 和 `GM_RM011_N003` 没有稳定框/节点表达这辆车，应填写为 `visible_unboxed_vehicle_gap`。这仍然只是诊断事件：不画新框，不新增 bbox，不生成 final boxes 或 GT boxes，不把 detector swap 变成主线。

## Non-Vehicle Exclusion：非车辆排除

### GM_RM017_E002

这一项先判断一个观察片段是否确实不是车辆，而不是判断两段车辆轨迹是否相连。`from_node` 和 `to_node` 都是 `GM_RM017_N005`，对应 frames `121-129`；人工应先看 `GM_RM017_000121.png`、`GM_RM017_000125.png`、`GM_RM017_000129.png`。如果图中其实有车辆可见，但当前 node / box 没有稳定覆盖该车辆，不要直接把它改成普通车辆连接，先记录为 `visible_unboxed_vehicle_gap` 或 `mark_review_required`。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM017` |
| from_node | `GM_RM017_N005` |
| to_node | `GM_RM017_N005` |
| current_edge_type | `non_vehicle_exclusion` |
| connection_strength | `excluded` |
| node range | `GM_RM017_N005`, `GM_RM017_NONVEHICLE_001`, frames `121-129` |
| key frame range | `121-129` |
| rendered frame count in range | 9 |
| visual basis | 当前框跟随的是前景路障或临时结构，不是车辆。 |
| current reason | 这是一个用于排除非车辆 track content 的一元 exclusion edge。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000121.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000125.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000129.png
```

人工需要判断：

- 框内内容是否确实是前景路障、临时结构或其他非车辆对象？
- 该 node 是否应该继续从车辆时序图中排除？
- 这个问题更适合记为 `exclude_non_vehicle`、`mark_bad_detection_node`，还是 `mark_review_required`？
- 是否需要在诊断渲染中显示非车辆 marker，避免后续误读？
- 是否需要填写 override CSV？如果接受当前非车辆排除，通常不需要。

override CSV 提示：

- 接受当前排除：不需要填写；如需留痕，可填 node `action=exclude_non_vehicle`，`reason_code=non_vehicle_barrier`。
- 如果其实是车辆节点：填 node `action=keep_vehicle_node`，`reason_code=custom_vehicle_referent`。
- 如果只是坏检测框：填 node `action=mark_bad_detection_node`，`reason_code=bad_detection_box_fit`。
- 如果不确定：填 node `action=mark_review_required`，`reason_code=review_uncertain`。
- 仅需要渲染标记：填 render `action=show_non_vehicle_marker`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(node / render / none)

- action：
  TODO

- edge_strength：
  TODO(excluded / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / show_non_vehicle_marker；不能写新 bbox 坐标)

- note：
  TODO

## Forbidden Edges：禁止连接

### GM_RM017_E001

这一项判断前后两段深色车观察片段是否必须保持禁止连接，重点是避免把前车和后车误认为同一辆车。`from_node` 是 `GM_RM017_N001`，frames `145-185`；`to_node` 是 `GM_RM017_N003`，frames `162-214`。人工应先看 `GM_RM017_000145.png`、`GM_RM017_000179.png`、`GM_RM017_000214.png`，再补看中间帧。若图中有连续可见车辆但没有稳定对应 node / box，请不要直接改成强连接或弱连接，先标记 `mark_review_required` 并记录 `visible_unboxed_vehicle_gap`。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM017` |
| from_node | `GM_RM017_N001` |
| to_node | `GM_RM017_N003` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM017_N001`, `GM_RM017_V001`, frames `145-185` |
| to range | `GM_RM017_N003`, `GM_RM017_V003`, frames `162-214` |
| key frame range | `145-214` |
| rendered frame count in range | 70 |
| visual basis | 密集帧显示这是两辆不同的深色轿车，不是同一个目标。 |
| current reason | 防止把前车和后车错误合并的禁止连接。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000145.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000179.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000214.png
```

人工需要判断：

- `GM_RM017_N001` 和 `GM_RM017_N003` 是否明确指向两辆不同的深色轿车？
- 时间、位置、运动顺序是否说明它们不是同一个同车指称？
- 白色 SUV 或其他上下文车辆是否把前后两辆深色车分开了？
- 是否只是外观相似，但真实车辆并不一致？
- 当前 `forbidden_edge` 是否应保持？是否需要填写 override CSV？

override CSV 提示：

- 接受当前禁止连接：不需要填写。
- 如果只能弱连接：填 `action=force_weak_connect`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 如果确认同一辆车：填 `action=force_strong_connect`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 如果不确定：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / marker action；不能写新 bbox 坐标)

- note：
  TODO

### GM_RM011_E007

这一项判断中央白车片段是否不能连接到左边缘竞争车辆片段，重点是确认是否发生了身份串线。`from_node` 是 `GM_RM011_N003`，frames `262-270`；`to_node` 是 `GM_RM011_N006`，frames `283-292`。人工应先看 `GM_RM011_000262.png`、`GM_RM011_000280.png`、`GM_RM011_000292.png`，再补看 key frame range `262-292`。如果中央白车持续可见但当前 node / box 没有稳定覆盖它，请记录为 `visible_unboxed_vehicle_gap`，不要用强/弱连接掩盖缺框问题。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N003` |
| to_node | `GM_RM011_N006` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| to range | `GM_RM011_N006`, `GM_RM011_FORBIDDEN_CONTEXT_001`, frames `283-292` |
| key frame range | `262-292` |
| rendered frame count in range | 22 |
| visual basis | 后继框落到左边缘竞争车辆上，而中央白车仍然单独可见。 |
| current reason | 禁止 `bs_0061` 到 `bs_0064` 的错误桥接。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000280.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000292.png
```

人工需要判断：

- 后继节点是否从中央白车切换到了左边缘竞争车辆？
- 中央白车在后继帧中是否仍然可见，因此不应该把左边缘车接上？
- 是否有其他车辆插入导致身份串线？
- 当前禁止连接是否应保持为硬禁止？
- 是否需要在诊断渲染中显示 forbidden marker，提醒后续人工不要误连？

override CSV 提示：

- 接受当前禁止连接：不需要填写。
- 如果需要显示禁止连接标记：填 render `show_forbidden_edge_marker`。
- 如果实际只能弱连接：填 `action=force_weak_connect`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 如果不确定：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / show_forbidden_edge_marker；不能写新 bbox 坐标)

- note：
  TODO

### GM_RM011_E008

这一项不是简单判断 `forbidden_edge` 要不要改成弱连接或强连接；它先判断 frames `237-270` 附近下方白色车辆是否连续可见，以及当前 `GM_RM011_N007` / `GM_RM011_N003` 是否稳定表达了这辆车。`from_node` 是 `GM_RM011_N007`，frames `256-261`；`to_node` 是 `GM_RM011_N003`，frames `262-270`。人工应先看 `GM_RM011_000256.png`、`GM_RM011_000263.png`、`GM_RM011_000270.png`，必要时补看 frames `237-270`。如果确认白色车辆从约 frame `237` 到 `270` 连续可见，但当前 smoke render 没有稳定框或节点标识覆盖它，请不要直接改为 strong / weak；应标记 `mark_review_required`，`edge_strength=review_only`，并在 `note` 中写 `visible-but-unboxed vehicle gap`。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N007` |
| to_node | `GM_RM011_N003` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM011_N007`, `GM_RM011_FORBIDDEN_CONTEXT_002`, frames `256-261` |
| to range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| key frame range | `256-270` |
| rendered frame count in range | 15 |
| visual basis | 前段是侧窗/条带区域，后段切到左边缘后部碎片或竞争区域。 |
| current reason | 禁止仅凭空间接近或外观相似形成错误桥接。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000256.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000263.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000270.png
```

人工需要判断：

- frames `237-270` 中下方白色车辆是否人眼连续可见？
- `GM_RM011_N007` 和 `GM_RM011_N003` 的当前框/节点标识是否稳定覆盖了这辆白色车辆？
- 如果车辆可见但框或 node 标识不稳定，是否应记录为 `visible_unboxed_vehicle_gap`，而不是直接改强连接或弱连接？
- 前节点是否只是侧窗/条带片段，不能安全连接到 `GM_RM011_N003`？
- 时间、位置、运动方向是否真的连续，还是只是靠得近？
- 是否有其他车辆插入导致身份串线？
- 是否只是框不稳，但车辆指称仍然一致？如果不是，应保持禁止连接。
- 当前 `forbidden_edge` 是否应保持？是否需要填写 override CSV？

override CSV 提示：

- 接受当前禁止连接：不需要填写。
- 如果只能弱连接：填 `action=force_weak_connect`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 如果确认同一辆车：填 `action=force_strong_connect`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 如果不确定：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。
- 如果确认 frames `237-270` 中白色车辆连续可见，但当前渲染无稳定框或 node 标识：填 `override_type=edge`，`action=mark_review_required`，`edge_strength=review_only`，优先用 `reason_code=visible_unboxed_vehicle_gap`；若下游暂不支持该枚举，则用 `reason_code=review_uncertain`，并在 `note` 中写 `visible-but-unboxed vehicle gap`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / marker action；不能写新 bbox 坐标)

- note：
  TODO

## Strong Same-Vehicle Edges：强连接

### GM_RM011_E001

这一项判断短间隔内的白车车头/挡风玻璃观察片段是否可以保持强连接。`from_node` 是 `GM_RM011_N001`，frames `13-16`；`to_node` 是 `GM_RM011_N002`，frames `18-35`。人工应先看 `GM_RM011_000013.png`、`GM_RM011_000024.png`、`GM_RM011_000035.png`。如果图上车辆连续但当前 node / box 没有稳定覆盖对应车辆，请不要用强连接代替缺框记录，应勾选 `可见车辆未被节点/框稳定覆盖` 并标记 `mark_review_required`。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N001` |
| to_node | `GM_RM011_N002` |
| current_edge_type | `strong_same_vehicle_edge` |
| connection_strength | `strong` |
| from range | `GM_RM011_N001`, `GM_RM011_V001`, frames `13-16` |
| to range | `GM_RM011_N002`, `GM_RM011_V001`, frames `18-35` |
| key frame range | `13-35` |
| rendered frame count in range | 22 |
| visual basis | 同一辆白车的车头和挡风玻璃区域跨短间隔保持连续。 |
| current reason | 这是强局部诊断连接，不是最终 identity merge。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000013.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000024.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000035.png
```

人工需要判断：

- 前后节点是否指向同一辆真实车？
- frames `13-16` 到 `18-35` 之间的时间、位置、运动方向是否连续？
- 短缺帧是否不影响诊断用强连接？
- 是否有其他车辆插入导致身份串线？
- 是否只是框不稳，但车辆指称仍然一致？
- 是否需要填写 override CSV？如果接受当前强连接，通常不需要。

override CSV 提示：

- 接受当前强连接：不需要填写。
- 降级为弱连接：填 `override_type=edge`，`action=downgrade_to_weak`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 标记需要复核：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / marker action；不能写新 bbox 坐标)

- note：
  TODO

### GM_RM011_E002

这一项判断中央白车在 frames `279-292` 是否保持稳定强连接，同时确认左边缘邻车没有被误接进来。`from_node` 是 `GM_RM011_N004`，frames `279-281`；`to_node` 是 `GM_RM011_N005`，frames `283-292`。人工应先看 `GM_RM011_000279.png`、`GM_RM011_000286.png`、`GM_RM011_000292.png`。如果中央白车可见但当前 node / box 漂移或缺失，应记录为 `visible_unboxed_vehicle_gap` 或 render-only 问题，而不是直接生成新 bbox。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N004` |
| to_node | `GM_RM011_N005` |
| current_edge_type | `strong_same_vehicle_edge` |
| connection_strength | `strong` |
| from range | `GM_RM011_N004`, `GM_RM011_V002`, frames `279-281` |
| to range | `GM_RM011_N005`, `GM_RM011_V002`, frames `283-292` |
| key frame range | `279-292` |
| rendered frame count in range | 13 |
| visual basis | 中央白车的车头和挡风玻璃保持连续；左边缘邻车可以分开。 |
| current reason | 带有竞争车辆排除说明的强局部连接。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000279.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000286.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000292.png
```

人工需要判断：

- frames `279-292` 中中央白车是否保持同一个同车指称？
- 左边缘邻车是否足够清楚地与中央白车分开？
- 渲染框是否有从中央车漂移到邻车的情况？
- 是否有其他车辆插入导致身份串线？
- 当前强连接是否应保持，还是降级为弱连接、改为禁止连接、或标记需要复核？

override CSV 提示：

- 接受当前强连接：不需要填写。
- 降级为弱连接：填 `action=downgrade_to_weak`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 仅诊断渲染主框有问题：填 `override_type=render`，`action=select_diagnostic_primary_box`，并使用已有 `source_detection_id`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / select_diagnostic_primary_box；不能写新 bbox 坐标)

- note：
  TODO

## Weak Same-Vehicle Edges：弱连接

### GM_RM011_E003

这一项判断较长间隔内同一辆白车是否只能保留弱连接，重点是 rear/side 到 front/window 的部位转换是否安全。`from_node` 是 `GM_RM011_N003`，frames `262-270`；`to_node` 是 `GM_RM011_N004`，frames `279-281`。人工应先看 `GM_RM011_000262.png`、`GM_RM011_000267.png`、`GM_RM011_000281.png`。如果车辆在人眼上连续，但当前 node / box 没有稳定表达这一连续车辆，请先记录 `visible_unboxed_vehicle_gap`，不要直接升级强连接。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N003` |
| to_node | `GM_RM011_N004` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| to range | `GM_RM011_N004`, `GM_RM011_V002`, frames `279-281` |
| key frame range | `262-281` |
| rendered frame count in range | 12 |
| visual basis | 同一辆白车是合理解释，但可见部位从 rear/side 变到 front/window，且间隔更长。 |
| current reason | 弱诊断连接；不能直接合并 track identity。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000267.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000281.png
```

人工需要判断：

- 前后节点是否仍指向同一辆真实车？
- rear/side 到 front/window 的可见部位变化是否合理？
- frame `270` 到 `279` 的间隔是否太大，导致不能升级为强连接？
- 是否有其他车辆插入导致身份串线？
- 是车辆指称一致但框不稳，还是实际目标切换？
- 是否需要填写 override CSV？

override CSV 提示：

- 保留弱连接：不需要填写；如需留痕，可填 `action=force_weak_connect`，`edge_strength=weak`。
- 升级强连接：填 `action=upgrade_to_strong`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 标记需要复核：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / marker action；不能写新 bbox 坐标)

- note：
  TODO

### GM_RM011_E004

这一项判断右边缘白车的薄 crop 是否只能保持 `review_only`，而不是被过度解释为可靠弱连接。`from_node` 是 `GM_RM011_N008`，frames `135-161`；`to_node` 是 `GM_RM011_N009`，frames `164-166`。人工应先看 `GM_RM011_000135.png`、`GM_RM011_000149.png`、`GM_RM011_000166.png`。如果右边缘车辆可见但后继框太薄或缺失，请记录 `visible_unboxed_vehicle_gap` 或 node `mark_bad_detection_node`，不要补画 bbox。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N008` |
| to_node | `GM_RM011_N009` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `review_only` |
| from range | `GM_RM011_N008`, `GM_RM011_V003`, frames `135-161` |
| to range | `GM_RM011_N009`, `GM_RM011_V003`, frames `164-166` |
| key frame range | `135-166` |
| rendered frame count in range | 30 |
| visual basis | 右边缘白车可能连续，但后继 crop 太薄。 |
| current reason | review-only edge；可见车辆面积太少。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000135.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000149.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000166.png
```

人工需要判断：

- 右边缘车辆是否有足够可见内容支持同车指称？
- frames `164-166` 的后继框是否太薄，只能作为 `review_only`？
- 是车辆指称仍然一致但框太差，还是已经没有可靠车辆观察？
- 是否应该保持 `review_only`，升级为弱连接，改为禁止连接，或标记坏检测节点？
- 是否需要渲染 marker，防止后续过度信任薄边缘 crop？
- 是否需要填写 override CSV？

override CSV 提示：

- 保持 `review_only`：不需要填写；如需留痕，可填 `action=mark_review_required`，`edge_strength=review_only`。
- 升级为弱连接：填 `action=force_weak_connect`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=edge_contact_thin_crop` 或 `forbidden_competitor_switch`。
- 标记坏检测节点：如果薄 crop 不可用，对 `GM_RM011_N009` 填 node `mark_bad_detection_node`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / node / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / marker action；不能写新 bbox 坐标)

- note：
  TODO

### GM_RM011_E005

这一项判断 upper side/window 到 front/hood 的部位转换是否能作为弱同车连接保留。`from_node` 是 `GM_RM011_N010`，frames `231-233`；`to_node` 是 `GM_RM011_N011`，frames `236-245`。人工应先看 `GM_RM011_000231.png`、`GM_RM011_000239.png`、`GM_RM011_000245.png`。如果人眼看到车辆连续但 node / box 没有稳定覆盖同一辆车，请记录 `visible_unboxed_vehicle_gap` 并保持复核路径。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N010` |
| to_node | `GM_RM011_N011` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N010`, `GM_RM011_V004`, frames `231-233` |
| to range | `GM_RM011_N011`, `GM_RM011_V004`, frames `236-245` |
| key frame range | `231-245` |
| rendered frame count in range | 13 |
| visual basis | upper side/window 到 front/hood 的部位转换是合理的弱同车解释。 |
| current reason | 弱 part-transition edge。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000231.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000239.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000245.png
```

人工需要判断：

- frames `231-233` 的 upper side/window 区域是否和 frames `236-245` 的 front/hood 区域指向同一辆真实车？
- 时间、位置、运动方向是否支持部位转换，而不是目标切换？
- 是否有其他车辆插入导致身份串线？
- 当前是否应保持弱连接，升级强连接，改为禁止连接，或标记需要复核？
- 是否需要填写 override CSV？

override CSV 提示：

- 保留弱连接：不需要填写。
- 升级强连接：填 `action=upgrade_to_strong`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 标记需要复核：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / marker action；不能写新 bbox 坐标)

- note：
  TODO

### GM_RM011_E006

这一项判断早期白色 SUV 的 rear/body 到 upper-window strip 是否只能作为弱连接保留。`from_node` 是 `GM_RM011_N012`，frames `0-4`；`to_node` 是 `GM_RM011_N013`，frames `8-10`。人工应先看 `GM_RM011_000000.png`、`GM_RM011_000003.png`、`GM_RM011_000010.png`。如果车辆可见但当前框没有稳定表达，不要写新坐标，应记录 `visible_unboxed_vehicle_gap` 或仅做诊断渲染主框选择。

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N012` |
| to_node | `GM_RM011_N013` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N012`, `GM_RM011_V005`, frames `0-4` |
| to range | `GM_RM011_N013`, `GM_RM011_V005`, frames `8-10` |
| key frame range | `0-10` |
| rendered frame count in range | 8 |
| visual basis | 白色 SUV 的 rear/body 到 upper-window 部位转换是合理的弱同车解释。 |
| current reason | 早期帧弱 part-transition edge。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000000.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000003.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000010.png
```

人工需要判断：

- frames `0-4` 的 rear/body 区域是否合理连续到 frames `8-10` 的 upper-window strip？
- 时间、位置、运动方向是否支持弱连接？
- 是否有足够全帧证据排除其他车辆或背景混淆？
- 是否只是框不稳，但车辆指称仍然一致？
- 当前是否应保持弱连接，升级强连接，改为禁止连接，或标记需要复核？

override CSV 提示：

- 保留弱连接：不需要填写。
- 升级强连接：填 `action=upgrade_to_strong`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 仅诊断渲染主框有问题：只有当另一个已有检测更适合作为诊断主框时，才使用 `select_diagnostic_primary_box`。

人工填写区：

- 人工判断：
  - [ ] 接受当前结论，无需 override
  - [ ] 接受当前结论，但需要显式留痕
  - [ ] 修改为强连接
  - [ ] 修改为弱连接
  - [ ] 修改为禁止连接
  - [ ] 排除为非车辆
  - [ ] 标记为坏检测节点
  - [ ] 标记需要复核
  - [ ] 仅调整诊断渲染显示
  - [ ] 可见车辆未被节点/框稳定覆盖

- 判断理由：
  TODO

- 是否需要生成 override CSV：
  - [ ] 否
  - [ ] 是

- override_type：
  TODO(edge / render / none)

- action：
  TODO

- edge_strength：
  TODO(strong / weak / forbidden / review_only / none)

- reason_code：
  TODO

- evidence_frame_start：
  TODO

- evidence_frame_end：
  TODO

- render override：
  TODO(target_node_id / source_detection_id / select_diagnostic_primary_box；不能写新 bbox 坐标)

- note：
  TODO

## 验收完成前检查

在后续任何 apply step 之前，先确认：

- 10 条 edge 都已有人工判断：接受当前、改变强弱、禁止连接、非车辆排除、或需要复核。
- 所有 override row 只使用 `node`、`edge`、`render` 三类 `override_type`。
- override CSV 不包含 bbox 坐标列。
- `select_diagnostic_primary_box` 引用的是 render manifest 中已有的 `source_detection_id`。
- override CSV 通过 dry-run validator。
- 没有生成 final annotation、revised annotation、final boxes、GT boxes、SAR output、detector output、tracker replay output、selector/ranking output。
- 没有提交 outputs、图片、视频、权重、数组、pickle、压缩包。
