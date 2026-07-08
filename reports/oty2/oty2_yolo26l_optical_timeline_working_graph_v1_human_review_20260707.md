# OTY2 YOLO26l 光学时序工作图 V1 人工验收入口

日期：`2026-07-07`

本文件用于人工验收 `YOLO26l optical timeline working graph V1`。人工只判断诊断工作图中的 fragment、same-vehicle edge、temporal context edge 和 blocked/review item 是否合理。不要在本文件中画新 bbox，不要生成 final/revised annotation，不要生成 final boxes 或 GT boxes，不要进入 SAR。

参考表：

```text
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_vehicle_fragments_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_same_vehicle_edges_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_temporal_context_edges_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_blocked_review_items_20260707.csv
```

## 验收顺序

1. 先确认 `blocked` 和 `forbidden/context` 项是否确实不能作为同车节点或同车边。
2. 再看 `temporal_context_edges_v1`，确认交会、遮挡、接替、竞争关系是否表达正确。
3. 再看 `vehicle_fragment_nodes_v1`，确认每个 fragment 内部是否只表达一辆真实车的局部连续观察。
4. 最后看 `same_vehicle_edges_v1`，只在确认同一辆真实车时才保留；否则改为 temporal context 或 blocked/review。

## 通用判断问题

- 图中真实车辆是否连续可见？
- 当前 fragment 是否稳定覆盖同一辆真实车？
- 是否发生主框跳到邻车、遮挡主体切换、车头对车头、车尾对车头或一车消失另一车出现？
- 这条关系是 same-vehicle，还是 temporal context？
- 是否需要保留 `review_required` 或 `blocked`？
- 是否只是诊断渲染/工作图判断，而不是 final box 或 SAR-ready evidence？

## GM_RM011 000-035

这组检查判断近场白车是否能拆成身份安全的短片段，而不是把 `Y26N004 18-35` 整段当作同车节点。

建议先看 frames `0-4`、`8-10`、`13-16`、`18-25`、`26-30`、`31-35`。

需要确认：

- `GM_RM011_WGF001/WGF002/WGF003/WGF004` 是否各自稳定表达同一辆局部车辆？
- `26-30` 是否确实是跳变或竞争车辆区域？
- `31-35` 是前车姿态连续变化，还是新的车辆/新片段？
- `GM_RM011_WGSVE001/WGSVE002/WGSVE003` 是否只能保持 weak？

人工填写：

```text
window_id: GM_RM011_000_035
accepted_fragments:
review_required_fragments:
blocked_fragments:
same_vehicle_edges_to_keep:
temporal_context_edges_to_keep:
notes:
```

## GM_RM011 135-166

这组检查判断遮挡场景中的框主体是否在白车和黑车之间切换。不要把 `135-166` 当作单一同车节点。

建议先看 frames `135-137`、`138-150`、`151-161`、`164-166`。

需要确认：

- `GM_RM011_WGF007` 是否为白车局部片段？
- `GM_RM011_WGF008` 是否确实是遮挡或主体切换区域？
- `GM_RM011_WGF009` 是否回到白车，还是另一个竞争目标？
- `GM_RM011_WGF010` 是否只是 thin crop review？
- `GM_RM011_WGTCE003/WGTCE004/WGTCE005` 是否应保留为 `occlusion_context`？

人工填写：

```text
window_id: GM_RM011_135_166
accepted_fragments:
review_required_fragments:
blocked_fragments:
same_vehicle_edges_to_keep:
temporal_context_edges_to_keep:
notes:
```

## GM_RM011 231-292

这组检查判断多辆白车/邻车在短时间内交会和接替，不再把整段当作同车链。

建议先看 frames `231-233`、`236-239`、`242-264`、`265-270`、`279-288`、`289-292`、`283-292 left-edge competitor`。

需要确认：

- `GM_RM011_WGF011` 到 `GM_RM011_WGF012` 是否可以弱同车复核？
- `GM_RM011_WGF012` 与 `GM_RM011_WGF013` 是否更像 `front_to_front_encounter`？
- `GM_RM011_WGF013` 与 `GM_RM011_WGF014` 是否更像 `rear_to_front_adjacency` 或接替？
- `GM_RM011_WGF017` 是否应保留为 competitor forbidden context？
- late fragments `GM_RM011_WGF015/WGF016` 是否需要继续拆分或复核？

人工填写：

```text
window_id: GM_RM011_231_292
accepted_fragments:
review_required_fragments:
blocked_fragments:
same_vehicle_edges_to_keep:
temporal_context_edges_to_keep:
notes:
```

## GM_RM011 237-270

这组是重点窗口。`GM_RM011_Y26N009` 不再被当作单一同车节点，而是拆成：

```text
fragment A: GM_RM011_WGF012 frames 236-239
fragment B: GM_RM011_WGF013 frames 242-264
fragment C: GM_RM011_WGF014 frames 265-270
```

人工重点确认：

- `237` 右侧白车与 `245` 左侧白车是否确实不同？
- `242-264` 是否可以作为局部 same-vehicle fragment？
- `262` 与 `270` 是否确实不是同一辆？
- `A -> B` 是否应保留 `front_to_front_encounter`？
- `B -> C` 是否应保留 `rear_to_front_adjacency`？
- 是否仍需 `review_required`？

人工填写：

```text
window_id: GM_RM011_237_270
accepted_fragments:
review_required_fragments:
blocked_fragments:
same_vehicle_edges_to_keep:
temporal_context_edges_to_keep:
notes:
```

## GM_RM017 118-214

这组检查拆开多个 review targets，不把整个窗口作为单一同车链。

建议先看 frames `118-144`、`145-158`、`159-163`、`164-185`、`200-214`，并单独复核 `GM_RM017_N005 / GM_RM017_E002` non-vehicle exclusion。

需要确认：

- `pre-145` 是否只是 truck/context vehicle review target？
- `164-185` 白色轿车/SUV 是否独立于前后深色车辆？
- `200-214` 深色车辆是否与 `145-158` 深色目标不同？
- `GM_RM017_E001` forbidden guard 是否继续成立？
- `GM_RM017_E002` non-vehicle exclusion 是否不应恢复为 vehicle fragment？

人工填写：

```text
window_id: GM_RM017_118_214
accepted_fragments:
review_required_fragments:
blocked_fragments:
same_vehicle_edges_to_keep:
temporal_context_edges_to_keep:
notes:
```

## 后续流程

```text
人工填写本 Markdown
→ Codex 或脚本提取需要调整的 diagnostic-only 条目
→ 生成 diagnostic override 或 V1.1 working graph 草案
→ dry-run 校验
→ 只应用到 diagnostic timeline graph / diagnostic render manifest
```

禁止流程：

```text
不得生成 final/revised annotation
不得生成 final boxes
不得生成 GT boxes
不得进入 SAR pairing/support/selector/ranking
不得把本图作为 SAR-ready evidence
```
