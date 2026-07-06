# OTY2 GM_RM011 237-270 可见车辆未稳定框选故障定位

日期：`2026-07-06`

仓库：`D:\profile\research\optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

诊断范围：

```text
scene_id = GM_RM011
frames = 237-270
event = GM_RM011_E008 visible_unboxed_vehicle_gap
```

## 边界

本报告只定位当前 optical diagnostic timeline graph 为什么没有稳定表达人工可见的白色车辆。它不应用 override，不生成 override CSV，不生成 final/revised annotation，不生成 final boxes 或 GT boxes，不运行 tracker replay，不进入 SAR pairing/support，不运行 selector/ranking，也不替换 baseline detector。

本次唯一执行的 detector 检查是局部 YOLO26l sensitivity check，范围只限 `GM_RM011 frames 237-270`。输出只写入 ignored outputs：

```text
outputs/oty2/gm_rm011_237_270_visible_unboxed_vehicle_gap_yolo26l_sensitivity_20260706/
```

该 outputs 目录不提交。

## 使用的现有输入

| 层 | 文件 |
| --- | --- |
| baseline OTY0 detection table | `outputs/oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream/oty0_yolo_detection_table.csv` |
| tracker input table | `outputs/oty1t_standard_mot_backbone_closure_20260705_110947/GM_RM011_yolo11l_baseline_botsort_normalized_active/tracker_input_detection_table.csv` |
| tracker-to-detection linkage | `outputs/oty2/embedding_track_linkage_probe_20260705_183000/embedding_track_linkage_rows.csv` |
| tracklet segment index | `outputs/oty2/tracklet_embedding_aggregation_probe_20260705_193000/tracklet_embedding_index.csv` |
| node table | `reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv` |
| edge table | `reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv` |
| render manifest | `reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv` |
| smoke render frame example | `outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000256.png` |

## 结论

这不是一个单纯的 baseline detector miss。

`GM_RM011 frames 237-270` 的可见白色车辆没有被当前 smoke render 稳定表达，主要是三层问题叠加：

1. baseline detection 层存在局部 underfit / miss：frame `256` 有 baseline car detection，但只覆盖车窗/上半部条带，不覆盖下方大面积白色车身；frames `249,252,253` 在 baseline 表中无 detection。
2. node graph construction 层遗漏了关键 tracklet：`bs_0051` 在该窗口内持续承接大量白色车身大框，但没有进入当前 node table。
3. render manifest / render 层选择和跳过造成烟测图不稳定：frames `256-261` 的 manifest 行属于 `GM_RM011_FORBIDDEN_CONTEXT_002 / bs_0056`，`display_status=forbidden_not_rendered`，renderer 默认跳过；frames `246-255` 没有 manifest 行；frames `262-270` 虽有 `GM_RM011_V002 / bs_0061` 弱连接框，但它多帧没有采用 baseline 中覆盖右侧/主体白车的大框。

因此失败层归因是：

```text
primary: node graph construction omission + render manifest selection/skip
secondary: baseline detector underfit / intermittent miss
not supported: pure detector miss
not supported: SAR-side failure
```

## Baseline 是否检测到该车

答案：baseline 部分检测到了，但不稳定，且关键帧 `256` 没有稳定覆盖下方白色车身主体。

在 `GM_RM011 frames 237-270`：

| 指标 | 结果 |
| --- | ---: |
| 检查帧数 | 34 |
| baseline detection rows | 55 |
| baseline 有 detection 的帧数 | 31 |
| baseline 无 detection 的帧 | `249,252,253` |
| 大面积下方车身 proxy detection rows | 19 |
| 车窗/上半部条带 proxy rows | 11 |

这里的“大面积下方车身 proxy”只用于故障定位，不是 GT，也不是 final box。近似条件是 bbox 下边界接近画面底部、上边界进入车身上部、面积较大。

关键帧证据：

| frame | baseline 情况 |
| ---: | --- |
| `237-245` | baseline 有多帧大面积车身框，并且部分进入 render manifest 的 `GM_RM011_V004 / bs_0038`。 |
| `246` | baseline 有大面积车身框 `GM_RM011_000246_001`，但没有进入当前 render manifest。 |
| `249,252,253` | baseline 表中无 detection。 |
| `254-259` | baseline 主要给出上半部/车窗条带框，不能稳定覆盖人工可见的下方白色车身。 |
| `256` | baseline 有 `GM_RM011_000256_001`，bbox 约 `[12.0,293.0,704.4,370.4]`，只覆盖车窗/上半部条带；smoke render 因 forbidden context 跳过，没有画框。 |
| `260-261` | baseline 同时有上半部条带框和大面积车身框，但 render manifest 采用的是 `bs_0056` forbidden context 条带行并跳过。 |
| `262-270` | baseline 多帧存在覆盖白车主体的大框，但当前 manifest 主要显示 `bs_0061` 的弱连接框，且未采用多帧 `bs_0051` 大框。 |

## YOLO26 是否检测到该车

答案：YOLO26l 能在该局部窗口内检出人工关注的白色车身，尤其在 frame `256` 给出大面积车身框。

本次局部 sensitivity check：

```text
model = D:\profile\research\workspace\artifacts\detector_weights\yolo26l.pt
imgsz = 960
conf = 0.25
classes = car, truck, bus
frames = GM_RM011 237-270 only
```

输出：

```text
outputs/oty2/gm_rm011_237_270_visible_unboxed_vehicle_gap_yolo26l_sensitivity_20260706/yolo26l_local_detection_table.csv
outputs/oty2/gm_rm011_237_270_visible_unboxed_vehicle_gap_yolo26l_sensitivity_20260706/summary.json
```

局部结果：

| 指标 | 结果 |
| --- | ---: |
| 检查帧数 | 34 |
| YOLO26l detection rows | 52 |
| YOLO26l 有 detection 的帧数 | 30 |
| YOLO26l 无 detection 的帧 | `240,241,267,268` |
| 大面积下方车身 proxy detection rows | 26 |

关键帧 `256`：

```text
det_id = GM_RM011_000256_001
class_name = car
confidence ~= 0.904
bbox ~= [6.3,295.6,581.2,596.3]
```

这说明 YOLO26l 在该关键帧能看到下方白色车身主体。但这不能自动替换 baseline，也不能自动生成 final boxes。已有 detector-swap 结论仍成立：YOLO26l 可作为局部诊断证据，但不是主线 detector replacement。

## 当前 smoke render 为什么没有稳定显示它

### 1. frames 237-245：有框，但只覆盖现有弱节点 `GM_RM011_V004`

当前 manifest 显示 `GM_RM011_V004 / bs_0038 / weak_timeline`。这些帧有可见车身框，属于 `GM_RM011_N011`，不是 `GM_RM011_E008` 的 `N007 -> N003` 主体。

### 2. frames 246-255：baseline 有部分可用检测，但没有进入 render manifest

当前 render manifest 在 `246-255` 没有任何 `GM_RM011` 行。局部 tracker linkage 显示该窗口内有 `bs_0051` 和若干 no-track detections，但 `bs_0051` 没有进入 node table，因此不会进入诊断渲染清单。

这属于 node graph construction omission / render manifest omission，不是 renderer 画错。

### 3. frames 256-261：manifest 有行，但被设计为不渲染

当前 manifest 中 `256-261` 的行是：

```text
diagnostic_vehicle_id = GM_RM011_FORBIDDEN_CONTEXT_002
source_track_id = bs_0056
display_status = forbidden_not_rendered
```

`tools/visualization/render_optical_timeline_video.py` 默认跳过：

```text
SKIP_STATUSES = {"forbidden_not_rendered", "non_vehicle_not_rendered"}
```

所以 smoke render 不画框是符合当前 renderer 规则的。问题在于该 forbidden context 只表达 `bs_0056` 的上半部/车窗条带，并没有稳定表达人工关注的下方白车主体。

### 4. frames 262-270：有弱连接框，但多帧不是主体大框

当前 manifest 显示 `GM_RM011_V002 / bs_0061 / weak_timeline`。例如 frame `262` 的 smoke frame 有左侧小框，而右侧大面积白车主体仍未被该框覆盖。

同时 baseline linkage 中 `bs_0051` 在 `260-270` 承接了多帧大面积主体框，例如：

```text
GM_RM011_000262_001
GM_RM011_000263_001
GM_RM011_000264_001
GM_RM011_000265_001
```

这些没有进入当前 node table，因此不会成为当前诊断 render 的主框。

## 是否被过滤、是否未进入 manifest、是否未进入 node table

| 问题 | 判断 |
| --- | --- |
| 是否 baseline 完全没检测到？ | 否。baseline 在 31/34 帧有 detection，但 frame `256` 仅为上半部条带框，且 `249,252,253` 缺失。 |
| 是否被 tracker input 过滤？ | 未见证据。normalized_active tracker input 在该窗口保留了 baseline detection rows。 |
| 是否没有进入 render manifest？ | 是。`246-255` 无 manifest 行；`bs_0051` 的主体大框未进入当前 node-driven manifest。 |
| 是否没有进入 node table？ | 是。`bs_0051 seg_001/002/003` 与该窗口主体大框高度相关，但没有 node。 |
| 是否被错误归入 forbidden context？ | 部分是。`256-261` 当前表达为 `GM_RM011_N007 / bs_0056 / forbidden_context_fragment`，且 renderer 跳过；这不能表达人工关注的可见白车主体。 |
| 是否属于 bad node？ | 当前没有明确 bad node 标记；更准确是 visible_unboxed_vehicle_gap + node graph omission。 |
| 是否是 threshold/NMS 问题？ | 仅在 detector 层局部成立：baseline 在 `249,252,253` 缺失，并在 `254-259` 偏向上半部条带；但主故障不能归为单纯 threshold/NMS。 |

## 层级归因

| 层 | 结论 | 证据 |
| --- | --- | --- |
| detector miss | 部分成立 | baseline 在 `249,252,253` 无 detection；frame `256` 只给上半部条带框。 |
| filtering / threshold / NMS | 部分成立于 detector 输出 | YOLO26l 能在 `256` 检出大车身，说明 baseline 模型/检测输出对该局部车身不稳定。 |
| tracker input filtering | 未见证据 | tracker input table 在该窗口保留 baseline detection rows。 |
| node graph construction omission | 成立，且是主因之一 | `bs_0051` 相关 tracklet 覆盖 `241-247,251,260-270`，但没有进入 node table。 |
| render manifest omission | 成立，且是主因之一 | `246-255` 无 manifest 行；`bs_0051` 主体框未进入 manifest。 |
| renderer skip | 成立 | `256-261` 为 `forbidden_not_rendered`，renderer 默认跳过。 |
| ambiguous / needs further review | 成立 | `GM_RM011_E008` 不能作为普通 forbidden/weak/strong edge 验收，需要记录 `visible_unboxed_vehicle_gap`。 |

## 是否允许进入后续 SAR

不允许。

这段不能作为后续 SAR 输入，也不能作为 ordinary edge 进入 SAR consumption。原因：

1. 当前 `GM_RM011_E008` 在 edge table 中 `can_support_sar_later=no`。
2. 人工关注的可见白车主体没有稳定 node / box 表达。
3. 当前 render manifest 对 `256-261` 采取 forbidden skip，对 `262-270` 没有稳定采用主体大框。
4. YOLO26l 的局部检出只能说明 detector sensitivity，不构成 final boxes、GT boxes 或 SAR prior。

后续只有在 optical diagnostic timeline graph 内完成 bounded repair、人工验收通过、并仍保持 soft diagnostic prior 边界时，才可重新讨论是否作为 reviewed optical diagnostic input。这个报告本身不打开 SAR。

## 最小修复路径

1. 对 `GM_RM011_E008` 保持 `visible_unboxed_vehicle_gap`，不要直接改成 strong 或 weak。
2. 在人工填写版 review packet 中对该项使用：

```text
override_type=edge
action=mark_review_required
edge_strength=review_only
reason_code=visible_unboxed_vehicle_gap
note=visible-but-unboxed vehicle gap
```

3. 只在后续明确允许时，做一个 optical diagnostic graph repair dry-run：
   - 不生成 final boxes；
   - 不生成 revised annotation；
   - 不进入 SAR；
   - 只新增或调整 diagnostic node/render manifest 表达。
4. repair dry-run 的最小检查对象应是：
   - `bs_0051 seg_001` frames `241-247`；
   - `bs_0051 seg_002` frame `251`；
   - `bs_0051 seg_003` frames `260-270`；
   - baseline missing / underfit frames `249,252,253,254-259`；
   - `bs_0056` forbidden context frames `256-261` 是否仅应作为 review context，而不是主体车辆表达。
5. 如果后续需要局部 detector sensitivity 证据，YOLO26l 可作为 diagnostic comparison source，但不得替换 baseline 主线，不得触发 tracker replay，不得生成 final boxes。

## Required Answers

1. baseline 是否检测到该车？

部分检测到。baseline 在 `31/34` 帧有 detection，并有 `19` 行大面积下方车身 proxy detections；但 `249,252,253` 缺失，frame `256` 只给出上半部条带框，不稳定覆盖人工可见白车主体。

2. YOLO26 是否检测到该车？

是。局部 YOLO26l 在 `30/34` 帧有 detection，并在 frame `256` 给出大面积车身框，confidence 约 `0.904`。

3. 当前 smoke render 为什么没有稳定显示它？

因为当前 graph/render 只稳定表达了部分已选节点：`237-245` 是 `bs_0038` 弱节点，`246-255` 无 manifest，`256-261` 是 `bs_0056` forbidden context 且被 renderer 跳过，`262-270` 是 `bs_0061` 弱节点但未稳定采用 `bs_0051` 主体大框。

4. 这是 detection 层失败、render 层失败，还是 node graph 层失败？

是混合失败：主因是 node graph construction omission + render manifest selection/skip，次因是 baseline detector underfit / intermittent miss。不是纯 detection miss，也不是 SAR 失败。

5. 这段是否允许进入后续 SAR？

不允许。它必须停留在 optical diagnostic review / repair 层，直到 visible_unboxed_vehicle_gap 被人工复核并只在 diagnostic timeline graph / diagnostic render manifest 内修复。

6. 最小修复路径是什么？

先标记 `GM_RM011_E008` 为 `mark_review_required / review_only / visible_unboxed_vehicle_gap`；后续若授权，只做 bounded diagnostic graph repair dry-run，把 `bs_0051` 相关主体大框作为诊断候选表达纳入审查，不生成 final boxes，不运行 tracker replay，不进入 SAR。

## No-Overstep Check

本次没有：

- 替换 baseline detector；
- 继续 detector swap 主线；
- 运行 tracker replay；
- 应用 override；
- 生成 override CSV；
- 生成 final/revised annotation；
- 生成 final boxes；
- 生成 GT boxes；
- 进入 SAR；
- 运行 SAR pairing/support/selector/ranking；
- 提交 outputs、图片、视频、权重、数组、pickle、压缩包。
