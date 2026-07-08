# OTY2 YOLO26l 光学时序工作图 V1.1 自动审阅与受控校正

日期：`2026-07-08`

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

## 边界

本阶段输出的是 `YOLO26l optical timeline working graph V1.1`，中文为 `YOLO26l 光学时序工作图 V1.1`。

它是 optical diagnostic working graph 层的自动审阅与受控校正结果，不是 final annotation，不是 revised annotation，不是 final boxes，不是 GT boxes，也不是 SAR-ready evidence。

本阶段没有运行 tracker replay，没有运行全量 detector swap，没有替换全局 baseline detector，没有进入 SAR pairing/support/selector/ranking，没有应用 override 到最终标注。

## 输入

V1.1 基于以下输入：

```text
reports/oty2/oty2_yolo26l_optical_timeline_working_graph_v1_design_and_results_20260707.md
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_vehicle_fragments_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_same_vehicle_edges_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_temporal_context_edges_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_blocked_review_items_20260707.csv
outputs/oty2/y26l_wgv1_frames_20260708/MY_DIAGNOSTIC_JUDGEMENT.md
```

`outputs/oty2/y26l_wgv1_frames_20260708/` 是 ignored 逐帧审阅包，只作为本地诊断依据，不提交。

## 输出

```text
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_vehicle_fragments_20260708.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_same_vehicle_edges_20260708.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_temporal_context_edges_20260708.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_blocked_review_items_20260708.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_to_v1_1_change_log_20260708.csv
reports/oty2/oty2_yolo26l_optical_timeline_working_graph_v1_1_human_review_delta_20260708.md
```

可选 ignored delta 逐帧包：

```text
outputs/oty2/y26l_wgv1_1_delta_frames_20260708/
```

## V1.1 规则

V1.1 采用以下机制规则：

1. 检测连续不等于同车连续。
2. fragment 内部必须表示一辆真实车的局部连续观察。
3. 主框主体跳到邻车、遮挡切换、车头对车头、车尾对车头、车辆接替，不能写成 same-vehicle edge。
4. `same_vehicle_edges_v1_1` 只保留低风险 weak 同车候选；高歧义关系一律转为 temporal context 或 blocked/review。
5. `accepted` 只表示 diagnostic working graph 层的局部片段可用，不表示最终身份真值。

## 表级摘要

| table | V1.1 count | 说明 |
| --- | ---: | --- |
| `vehicle_fragments` | 22 | 重编号为 `WG11F`，保留 identity-safe fragment 和 review target。 |
| `same_vehicle_edges` | 3 | 比 V1 少 1 条；移除 `231-239` 多车交会窗口中的 weak same-vehicle edge。 |
| `temporal_context_edges` | 16 | 比 V1 多 1 条；新增 `231-239` vehicle_turnover_context。 |
| `blocked_review_items` | 12 | 比 V1 多 1 条；记录被移除的 V1 weak same-vehicle edge。 |
| `change_log` | 15 | 逐条记录 V1 到 V1.1 的自动修正。 |

## 自动切分结果

V1.1 自动固化或形式化以下切分：

```text
GM_RM011 old Y26N004 -> WG11F004 18-25 / WG11F005 26-30 blocked / WG11F006 31-35 review
GM_RM011 old Y26N005 -> WG11F007 135-137 / WG11F008 138-150 blocked / WG11F009 151-161 / WG11F010 164-166
GM_RM011 old Y26N009 -> WG11F012 236-239 / WG11F013 242-264 weak / WG11F014 265-270 review
GM_RM011 late window -> WG11F015 279-288 / WG11F016 289-292 / WG11F017 283-292 competitor context
GM_RM017 118-214 -> WG11F001 pre-145 context / WG11F002 leading mixed target / WG11F003 blocked switch / WG11F004 white vehicle / WG11F005 trailing dark vehicle
```

这些切分是 working graph 层修正，不是人工 GT，不是 final annotation。

## Same-Vehicle Edge 修正

V1.1 保留的 same-vehicle edges：

```text
GM_RM011_WG11SVE001  WG11F001 -> WG11F002  weak
GM_RM011_WG11SVE002  WG11F002 -> WG11F003  weak
GM_RM011_WG11SVE003  WG11F003 -> WG11F004  weak
```

V1.1 删除的 V1 same-vehicle edge：

```text
GM_RM011_WGSVE004  WGF011 -> WGF012
```

删除原因：`231-239` 位于 structured multi-vehicle temporal encounter 内。连续出现白车片段不能自动证明同一辆真实车，V1.1 将该关系转为：

```text
GM_RM011_WG11TCE006  WG11F011 -> WG11F012  vehicle_turnover_context
```

## Temporal Context Edge 修正

V1.1 新增或固化的重点 temporal context：

```text
GM_RM011_WG11TCE003  WG11F007 -> WG11F008  occlusion_context
GM_RM011_WG11TCE004  WG11F008 -> WG11F009  occlusion_context
GM_RM011_WG11TCE006  WG11F011 -> WG11F012  vehicle_turnover_context
GM_RM011_WG11TCE007  WG11F012 -> WG11F013  front_to_front_encounter
GM_RM011_WG11TCE008  WG11F013 -> WG11F014  rear_to_front_adjacency
GM_RM017_WG11TCE005  WG11F002 -> WG11F005  competitor_vehicle_context
```

## 状态更新

从 V1 到 V1.1 的状态更新：

```text
GM_RM011_WGF002 -> GM_RM011_WG11F002: review_required -> weak
```

原因：frames `8-10` 的 YOLO26l 局部车身覆盖较完整，可作为 weak diagnostic fragment。但它仍需要人工复核 same-vehicle relation，不是 accepted，也不是 final identity。

其他高歧义项保持 `review_required`、`blocked` 或 `forbidden`。

## 重点窗口

### GM_RM011 237-270

V1.1 已落实 A/B/C 结构：

```text
A = GM_RM011_WG11F012 frames 236-239 review_required
B = GM_RM011_WG11F013 frames 242-264 weak
C = GM_RM011_WG11F014 frames 265-270 review_required
```

关系：

```text
A -> B = front_to_front_encounter
B -> C = rear_to_front_adjacency
```

`Y26N009` 不能再作为单一同车节点。`242-264` 只作为 weak 局部同车 fragment 进入人工复核。

### GM_RM011 135-166

V1.1 已落实遮挡主体切换：

```text
135-137 = review_required local white vehicle fragment
138-150 = blocked occlusion / competing-subject fragment
151-161 = review_required post-switch fragment
164-166 = review_required thin crop
```

关系全部进入 `occlusion_context`，没有生成 same-vehicle edge。

### GM_RM011 231-292

V1.1 已把 structured multi-vehicle temporal encounter 从 same-vehicle 中剥离。

最关键变化是删除 V1 的：

```text
GM_RM011_WGSVE004
```

并新增：

```text
GM_RM011_WG11TCE006 vehicle_turnover_context
```

### GM_RM011 000-035

V1.1 保留近场截断但连续的 weak 同车候选，只到 `18-25` 为止。`26-30` 保持 blocked，`31-35` 保持 review_required，不跨越 jump zone 自动连接。

### GM_RM017 118-214

V1.1 继续拆开多目标 review：

```text
pre-145 truck/context target
145-158 leading mixed/dark target
159-163 blocked transition
164-185 white vehicle target
200-214 trailing dark vehicle target
```

`GM_RM017_E001` forbidden guard 保留；`GM_RM017_E002` non-vehicle exclusion 不恢复为 vehicle fragment。

## SAR-ready

所有窗口均为：

```text
SAR-ready = no / blocked
```

原因：

1. V1.1 仍是 optical diagnostic working graph。
2. V1.1 不包含 final boxes、GT boxes 或 revised annotation。
3. 同车关系仍需要人工复核。
4. SAR pairing/support/selector/ranking 仍被禁止。

## 下一步

下一步应人工复核 V1.1 delta review packet，优先看：

```text
GM_RM011 237-270
GM_RM011 135-166
GM_RM011 231-292
GM_RM017 118-214
GM_RM011 000-035
```

人工确认后，下一阶段可以生成 diagnostic-only V1.2 或 override CSV 提取草案，但仍不能生成 final/revised annotation、final boxes、GT boxes 或 SAR-ready evidence。

一句话结论：

```text
YOLO26l optical timeline working graph V1.1 is ready as a controlled auto-repaired diagnostic working graph; obvious false same-vehicle linkage is reduced, temporal context is explicit, and all windows remain no / blocked for SAR.
```
