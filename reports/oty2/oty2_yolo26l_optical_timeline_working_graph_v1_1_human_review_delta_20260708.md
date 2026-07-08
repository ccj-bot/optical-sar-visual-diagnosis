# OTY2 YOLO26l 光学时序工作图 V1.1 Delta 人工复核入口

日期：`2026-07-08`

本文件用于人工复核 V1 到 V1.1 的变化。它不是人工逐帧标注入口，不允许画新 bbox，不允许生成 final/revised annotation，不允许生成 final boxes 或 GT boxes，不允许进入 SAR。

## Delta 输出位置

Ignored 逐帧复核包：

```text
outputs/oty2/y26l_wgv1_1_delta_frames_20260708/
```

该目录不得提交 Git。

## 优先复核顺序

1. `GM_RM011 237-270`：确认 A/B/C 结构，尤其是 `F12 -> F13` 是否应保持 `front_to_front_encounter`，`F13 -> F14` 是否应保持 `rear_to_front_adjacency`。
2. `GM_RM011 135-166`：确认 `137 -> 138` 是否为主体切换，是否保持 `occlusion_context`。
3. `GM_RM011 231-292`：确认 V1.1 删除 `WGSVE004` 是否合理，是否应保留 `vehicle_turnover_context`。
4. `GM_RM017 118-214`：确认多目标 review 拆分、forbidden guard 和 non-vehicle exclusion。
5. `GM_RM011 000-035`：确认 `26-30 blocked` 与 `31-35 review_required` 是否合理。

## 人工只需要回答的问题

- V1.1 fragment 内部是否仍是同一辆真实车的局部连续观察？
- V1.1 删除的 same-vehicle edge 是否确实不应保留？
- V1.1 新增或固化的 temporal context edge 是否正确？
- 哪些 `review_required` 可以保持 review，哪些必须改为 blocked？
- 是否有任何 weak same-vehicle edge 应被继续删除？

## 禁止

```text
不得生成 final/revised annotation
不得生成 final boxes
不得生成 GT boxes
不得进入 SAR pairing/support/selector/ranking
不得把 V1.1 当成 SAR-ready evidence
```

## 复核记录模板

```text
window_id:
accepted_fragments:
weak_fragments:
blocked_fragments:
same_vehicle_edges_to_keep:
same_vehicle_edges_to_remove:
temporal_context_edges_to_keep:
temporal_context_edges_to_change:
notes:
```
