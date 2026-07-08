# OTY2 YOLO26l 光学时序工作图 V1 设计与结果

日期：`2026-07-07`

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

## 边界

本文件构建的是 `YOLO26l optical timeline working graph V1`，中文为 `YOLO26l 光学时序工作图 V1`。

它是 optical diagnostic 层的工作产物，不是 final annotation，不是 revised annotation，不是 final boxes，不是 GT boxes，也不是 SAR-ready evidence。本阶段没有应用 override，没有替换全局 baseline detector，没有运行全量 detector swap，没有运行 tracker replay，也没有进入 SAR pairing/support/selector/ranking。

旧 baseline graph 和旧 `N00x/E00x` 只作为对照、回归窗口和来源追踪，不再作为新图骨架。YOLO26l candidate 也不再只是贴在 baseline graph 上的 overlay，而是被重新组织为身份安全的 fragment、同车边、时序上下文边和 blocked/review 项。

## 输入

本轮只使用已有文本和轻量 CSV 诊断输入：

```text
reports/oty2/oty2_yolo26l_diagnostic_timeline_graph_candidate_review_packet_20260707.md
reports/oty2/oty2_yolo26l_identity_safe_timeline_mechanism_diagnosis_20260707.md
reports/oty2/samples/oty2_yolo26l_diagnostic_timeline_graph_nodes_candidate_20260707.csv
reports/oty2/samples/oty2_yolo26l_diagnostic_timeline_graph_edges_candidate_20260707.csv
reports/oty2/samples/oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv
reports/oty2/samples/oty2_yolo26l_identity_safe_timeline_mechanism_diagnosis_summary_20260707.csv
```

未运行新的 detector、tracker replay 或 SAR 流程。

## 输出

```text
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_vehicle_fragments_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_same_vehicle_edges_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_temporal_context_edges_20260707.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_blocked_review_items_20260707.csv
reports/oty2/oty2_yolo26l_optical_timeline_working_graph_v1_human_review_20260707.md
```

这些 CSV 是 diagnostic working graph summary，不含新 bbox 坐标，不是 final boxes。

## V1 机制

检测连续不等于同车连续。一个窗口内持续出现车辆检测框，只说明 detector 持续看到 vehicle-like object，不证明这些框属于同一辆真实车。

一个 `vehicle_fragment_nodes_v1` 节点必须表示一辆真实车的局部连续观察片段。如果内部出现身份切换、不同车辆交会、车头对车头、车尾对车头、遮挡导致主体切换或主框跳到邻车，则必须拆分或标为 `blocked`。

`same_vehicle_edges_v1` 只表示同一真实车辆之间的候选连接。若关系只是交会、遮挡、接替、邻车竞争或 forbidden guard，则进入 `temporal_context_edges_v1`，不能写成 weak same-vehicle edge。

近场截断不是自动错误。只要完整帧流能解释为同一车辆连续观察，局部车窗、前脸、车身条带可以作为 `accepted` 或 `weak` diagnostic fragment；但它仍不是 final box。

## 窗口级结果

| window | V1 处理 | 结果 |
| --- | --- | --- |
| `GM_RM011 000-035` | `Y26N004` 不再整段接受，拆为 `18-25`、`26-30 blocked`、`31-35 review_required`。 | `0-25` 只保留弱同车候选；`26-30` 的大跳变进入 blocked/review。 |
| `GM_RM011 135-166` | 按遮挡主体切换拆为 `135-137`、`138-150 blocked`、`151-161`、`164-166 thin crop`。 | 同车边被移除，保留 `occlusion_context`。 |
| `GM_RM011 231-292` | 拆为多个短 fragment，并把 left-edge competitor 单独保留为 forbidden/context。 | 不再把整段当同车链；只允许短片段人工验收。 |
| `GM_RM011 237-270` | 旧 `Y26N009` 被拆为 `A=237-239`、`B=242-264`、`C=265-270`。 | visible_unboxed gap 已转为 YOLO26l 可见主体 fragment，但不是单一同车节点。 |
| `GM_RM017 118-214` | 拆为 `pre-145 context/truck`、`145-158 leading/mixed target`、`159-163 blocked switch`、`164-185 white vehicle`、`200-214 trailing dark vehicle`。 | `GM_RM017_E001` forbidden guard 和 `GM_RM017_E002` non-vehicle exclusion 仍保留。 |

## Accepted fragments

以下 fragment 被接受为 V1 diagnostic working graph 的局部车辆观察片段：

```text
GM_RM011_WGF001  frames 0-4
GM_RM011_WGF003  frames 13-16
GM_RM011_WGF004  frames 18-25
```

这里的 `accepted` 只表示该局部片段可作为 optical diagnostic working graph 节点使用。它不表示最终身份真值、final box、GT box 或 SAR-ready evidence。

## Weak / review_required fragments

以下 fragment 仍需人工验收或只能作为 weak diagnostic fragment：

```text
GM_RM011_WGF002  frames 8-10
GM_RM011_WGF006  frames 31-35
GM_RM011_WGF007  frames 135-137
GM_RM011_WGF009  frames 151-161
GM_RM011_WGF010  frames 164-166
GM_RM011_WGF011  frames 231-233
GM_RM011_WGF012  frames 236-239
GM_RM011_WGF013  frames 242-264
GM_RM011_WGF014  frames 265-270
GM_RM011_WGF015  frames 279-288
GM_RM011_WGF016  frames 289-292
GM_RM017_WGF001  frames 118-144
GM_RM017_WGF002  frames 145-158
GM_RM017_WGF004  frames 164-185
GM_RM017_WGF005  frames 200-214
```

Blocked 或 forbidden/context fragments：

```text
GM_RM011_WGF005  frames 26-30
GM_RM011_WGF008  frames 138-150
GM_RM011_WGF017  frames 283-292
GM_RM017_WGF003  frames 159-163
```

## Same-vehicle edges

V1 只保留弱同车候选边，不生成强连接：

```text
GM_RM011_WGSVE001  GM_RM011_WGF001 -> GM_RM011_WGF002
GM_RM011_WGSVE002  GM_RM011_WGF002 -> GM_RM011_WGF003
GM_RM011_WGSVE003  GM_RM011_WGF003 -> GM_RM011_WGF004
GM_RM011_WGSVE004  GM_RM011_WGF011 -> GM_RM011_WGF012
```

`GM_RM011_WGF012 -> GM_RM011_WGF013` 不写入 same-vehicle edge；它只进入 `front_to_front_encounter` temporal context。V1 没有把任何 `GM_RM017` 关系写为 same-vehicle edge。

## Temporal context edges

V1 生成的时序上下文边包括：

```text
GM_RM011_WGTCE001  same_frame_competition
GM_RM011_WGTCE002  vehicle_turnover_context
GM_RM011_WGTCE003  occlusion_context
GM_RM011_WGTCE004  occlusion_context
GM_RM011_WGTCE005  occlusion_context
GM_RM011_WGTCE006  front_to_front_encounter
GM_RM011_WGTCE007  rear_to_front_adjacency
GM_RM011_WGTCE008  vehicle_turnover_context
GM_RM011_WGTCE009  vehicle_turnover_context
GM_RM011_WGTCE010  competitor_vehicle_context
GM_RM017_WGTCE001  competitor_vehicle_context
GM_RM017_WGTCE002  same_frame_competition
GM_RM017_WGTCE003  occlusion_context
GM_RM017_WGTCE004  vehicle_turnover_context
GM_RM017_WGTCE005  competitor_vehicle_context
```

这些边保留了不同车辆之间的交会、遮挡、接替和竞争关系，但不表示同车身份。

## 重点窗口回答

### GM_RM011 237-270

已从单一 `GM_RM011_Y26N009` 改为身份安全片段与上下文边：

```text
fragment A: GM_RM011_WGF012 frames 236-239
fragment B: GM_RM011_WGF013 frames 242-264
fragment C: GM_RM011_WGF014 frames 265-270
```

`A -> B` 进入 `front_to_front_encounter`，`B -> C` 进入 `rear_to_front_adjacency`。`B` 内部可作为 weak diagnostic fragment 进入人工验收，但整段 `237-270` 不能再作为单一同车节点。

### GM_RM011 135-166

遮挡主体切换已处理：`135-137`、`138-150`、`151-161`、`164-166` 被拆开。`138-150` 标记为 `blocked`，相关关系进入 `occlusion_context`，没有生成 same-vehicle edge。

### GM_RM017 118-214

已拆开 review targets：`pre-145 context/truck`、`leading/mixed target`、`white sedan or SUV`、`trailing dark vehicle` 和 non-vehicle exclusion review 分离。`GM_RM017_E001` 仍是 forbidden guard；`GM_RM017_E002` 仍是 non-vehicle exclusion review，不恢复为 vehicle fragment。

## SAR-ready 状态

所有窗口均为：

```text
SAR-ready = no / blocked
```

原因：

1. V1 是 optical diagnostic working graph，不是 final annotation。
2. CSV 不包含新 bbox 坐标，也不生成 final boxes 或 GT boxes。
3. 同车关系仍需人工复核。
4. blocked/review 项尚未通过人工验收。
5. SAR pairing/support/selector/ranking 仍然禁止。

## 最小下一步

下一步建议使用：

```text
reports/oty2/oty2_yolo26l_optical_timeline_working_graph_v1_human_review_20260707.md
```

人工按窗口确认 fragment 是否可接受、weak same-vehicle edge 是否应保留、temporal context edge 是否正确。只有人工验收后，才可以在下一阶段生成 diagnostic-only override 或 V1.1 working graph；仍不得生成 final/revised annotation、final boxes、GT boxes 或 SAR-ready evidence。

一句话结论：

```text
YOLO26l optical timeline working graph V1 is ready as a bounded diagnostic working graph; it separates identity-safe fragments from temporal context relations, but every window remains no / blocked for SAR.
```
