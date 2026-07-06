# OTY2 YOLO26l 诊断渲染人工验收包

日期：`2026-07-07`

仓库：`D:\profile\research\optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

上一轮依据：`reports/oty2/oty2_yolo26l_optical_diagnostic_candidate_stream_dryrun_20260706.md`

## 使用边界

本文件只服务于人工诊断验收，用来比较 `current baseline diagnostic graph` 和 `YOLO26l diagnostic candidate` 在关键窗口中的车辆表达能力。

本文件和配套 contact sheet 不表示 final annotation，不表示 revised annotation，不表示 final boxes，不表示 GT boxes，也不是 SAR-ready evidence。

允许的用途：

- 看当前 baseline diagnostic smoke render 是否已经足够人工验收；
- 看 YOLO26l candidate 是否更清楚表达车辆主体；
- 记录 `visible_unboxed_vehicle_gap`、多框竞争、车窗/条带框等诊断问题；
- 指导人工在 fillable Markdown 中判断后续是否需要 override。

禁止的用途：

- 不得把 YOLO26l candidate 写成 final boxes；
- 不得从本包生成 final/revised annotation；
- 不得把本包结果送入 SAR pairing/support/selector/ranking；
- 不得替换 baseline 主线 detector；
- 不得把 detector-only 结果自动改成 strong/weak/forbidden edge。

## 输入

Baseline diagnostic graph / render 输入：

```text
reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv
reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv
reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/
```

YOLO26l diagnostic candidate 输入：

```text
outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv
outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv
outputs/oty2/gm_rm011_237_270_visible_unboxed_vehicle_gap_yolo26l_sensitivity_20260706/yolo26l_local_detection_table.csv
```

本轮没有重新运行 detector，没有运行 tracker replay，没有应用 override。

## Contact Sheet

Contact sheet 只写入 ignored outputs，不提交。

输出目录：

```text
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/
```

生成的对照图：

```text
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM011_000_035_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM011_135_166_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM011_231_292_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM011_237_270_visible_gap_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM017_118_214_baseline_vs_yolo26l_diagnostic_contact_sheet.png
```

图像读法：

- 左列：`detector_source=baseline_current_graph`，来自当前 baseline diagnostic smoke render。
- 右列：`detector_source=yolo26l`，来自 YOLO26l diagnostic candidate overlay。
- 图上 `diagnostic_candidate=true` 只表示诊断候选，不表示 final / GT / revised。
- `body_proxy` 只用于 `GM_RM011` 下方白车主体的诊断代理，不是 final box 质量判定。

## 总览结论

建议优先看 YOLO26l candidate 的窗口：

- `GM_RM011 237-270` / `GM_RM011_E008` / `GM_RM011_N007`：visible_unboxed_vehicle_gap 重点窗口。
- `GM_RM011 231-292` 中的 `E005/N010`、`E008/N007`、`E003`、`E007`：YOLO26l 对白车主体表达更完整，但仍需人工判断 edge safety。
- `GM_RM011 0-35` 中的 `E006/N013`：YOLO26l 更完整覆盖早期白 SUV 主体。
- `GM_RM017 121-129` / `E002/N005`：YOLO26l 可辅助确认 non-vehicle exclusion，尤其是降低多框误导。

Baseline 已经够用或仍可作为主要验收入口的窗口：

- `GM_RM011_E001`、`GM_RM011_E002`：当前 strong edge 的 baseline render 已能支持人工验收。
- `GM_RM011_E004`：问题本质是右边缘 thin crop / review-only，YOLO26l 不能自动修复。
- `GM_RM017_N001/N002/N003/N004`：baseline graph 对人工查看仍可用。

Detector-only 不能决策的窗口：

- `GM_RM011_E007`：竞争车辆 / forbidden bridge，YOLO26l 检测更强也不能自动放开连接。
- `GM_RM011_N009`：thin right-edge strip，不足以自动证明 same-vehicle continuity。
- `GM_RM017_E001`：两辆深色车的 forbidden 判断必须看 dense frames。

存在 `visible_unboxed_vehicle_gap` 的窗口：

- 明确存在：`GM_RM011 237-270`、`GM_RM011_E008`、`GM_RM011_N007`。
- 需结合人工查看确认：`GM_RM011 231-292` 中 `256-270` 相关片段。

是否建议下一步从填写版 Markdown 中提取 override CSV：

```text
yes, but only after human reviewer fills the fillable Markdown.
```

本阶段不提取 override CSV，不应用 override。

是否任何窗口 SAR-ready：

```text
no / blocked
```

## Window Card 1：GM_RM011 0-35

这条窗口在判断早期白色 SUV 的局部片段是否能支持 `weak -> strong` 周边关系验收，尤其是 `E006` 的早期弱连接和 `E001` 的短间隔强连接。

- `scene_id`: `GM_RM011`
- `frame_start`: `0`
- `frame_end`: `35`
- `related_edge_id`: `GM_RM011_E006`, `GM_RM011_E001`
- `related_node_id`: `GM_RM011_N012`, `GM_RM011_N013`, `GM_RM011_N001`, `GM_RM011_N002`
- 当前 baseline 表现：`E001` 的 strong edge 可验收；`E006` 的早期部位转换仍偏 weak，baseline 有多框竞争和局部条带风险。
- YOLO26l 候选表现：YOLO26l 在 `0-10` 对白 SUV 主体覆盖更完整，尤其 `N013` 从 baseline `body_proxy=0/3` 改善为 YOLO26l `body_proxy=3/3`。
- 是否存在 `visible_unboxed_vehicle_gap`: 未作为主阻塞；更像 part-transition / body coverage improvement。
- 是否存在多框竞争：存在，baseline 和 YOLO26l 都有多框竞争，YOLO26l 在 `E001` 多框略多。
- 是否存在只框车窗/条带问题：存在于 `E006/N013` 的 baseline 表达，YOLO26l 更适合显示主体候选。
- 是否更适合人工判断同车指称：`E006/N013` 建议优先看 YOLO26l；`E001` baseline 已可用。
- 人工需要看的代表帧路径：

```text
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM011_000_035_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000000.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000008.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000013.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000035.png
```

人工判断问题：

- `N012 -> N013` 是否只是车身局部从 rear/body 变成 upper-window，而同车指称仍连续？
- `N001 -> N002` 是否可接受为当前 strong edge？
- 多框是否会导致从白 SUV 跳到邻车？
- 是否需要把 `E006` 保留 weak，而不是升级 strong？

建议填写项：

```text
override_type=edge 或 none
action=mark_review_required / force_weak_connect / none
edge_strength=weak / review_only / none
reason_code=part_state_transition / review_uncertain / none
note=YOLO26l helps body visibility for early white SUV; diagnostic only
```

## Window Card 2：GM_RM011 135-166

这条窗口在判断右边缘白车薄片段是否能安全连接，核心不是 detector 强弱，而是可见面积是否太小。

- `scene_id`: `GM_RM011`
- `frame_start`: `135`
- `frame_end`: `166`
- `related_edge_id`: `GM_RM011_E004`
- `related_node_id`: `GM_RM011_N008`, `GM_RM011_N009`
- 当前 baseline 表现：baseline render 可显示 review-only thin crop；`N009` 太薄，不适合自动连接。
- YOLO26l 候选表现：YOLO26l 在多数帧可用，但没有消除右边缘 thin crop 的本质问题；`N009` 的 YOLO26l `body_proxy=0/3`。
- 是否存在 `visible_unboxed_vehicle_gap`: 不作为主问题；主问题是 edge-contact / thin crop。
- 是否存在多框竞争：存在，但不是主阻塞。
- 是否存在只框车窗/条带问题：存在，尤其 `164-166` 的 thin right-edge strip。
- 是否更适合人工判断同车指称：baseline 已足够暴露问题；YOLO26l 只能辅助，不应自动修正。
- 人工需要看的代表帧路径：

```text
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM011_135_166_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000135.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000161.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000164.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000166.png
```

人工判断问题：

- `N008 -> N009` 是否仅凭薄边缘片段就能判断同车？
- 如果不能判断，是否应保持 `review_only`？
- 是否需要标记 `mark_review_required` 而不是强行 `force_weak_connect`？

建议填写项：

```text
override_type=edge 或 none
action=mark_review_required / force_weak_connect / forbid_connect / none
edge_strength=review_only / weak / forbidden / none
reason_code=thin_edge_crop / review_uncertain / none
note=Right-edge thin crop; YOLO26l does not remove review-only risk
```

## Window Card 3：GM_RM011 231-292

这条窗口覆盖当前最复杂的白车主体、竞争车辆、weak/strong/forbidden 混合关系。人工应先看车辆是否连续，再看当前 node 是否正确表达。

- `scene_id`: `GM_RM011`
- `frame_start`: `231`
- `frame_end`: `292`
- `related_edge_id`: `GM_RM011_E005`, `GM_RM011_E008`, `GM_RM011_E003`, `GM_RM011_E007`, `GM_RM011_E002`
- `related_node_id`: `GM_RM011_N010`, `GM_RM011_N011`, `GM_RM011_N007`, `GM_RM011_N003`, `GM_RM011_N004`, `GM_RM011_N005`, `GM_RM011_N006`
- 当前 baseline 表现：`231-245` 有 weak part transition；`246-255` render manifest 缺口明显；`256-261` 当前 graph 进入 forbidden context / skip；`262-270` weak box 不稳定；`279-292` 的 central white vehicle strong edge 可验收。
- YOLO26l 候选表现：在 `231-245`、`256-270`、`262-292` 对白车主体的 body_proxy 更高，能更好辅助人工看连续车辆主体；但 `E007` 仍有竞争车辆风险。
- 是否存在 `visible_unboxed_vehicle_gap`: 存在于 `256-270` 子窗口，尤其 `E008/N007/N003`。
- 是否存在多框竞争：存在，特别是 `262-292` 竞争车辆/邻车导致 forbidden safety 不能自动放开。
- 是否存在只框车窗/条带问题：baseline 在 `254-259` 和 `N007` 更明显；YOLO26l 有主体大框改善。
- 是否更适合人工判断同车指称：`E005/N010`、`E008/N007`、`E003` 建议优先看 YOLO26l；`E002` baseline 已够用；`E007` detector-only 仍不能决策。
- 人工需要看的代表帧路径：

```text
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM011_231_292_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000231.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000245.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000256.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000279.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000292.png
```

人工判断问题：

- 白车主体是否从 `231` 到 `292` 有人眼连续性？
- 当前 `N007` 是否只是 forbidden context / upper strip，而没有表达主体车？
- `N003 -> N004` 是否应维持 weak，还是需要 `mark_review_required`？
- `N003 -> N006` 是否仍应禁止连接，因为 successor 更像竞争车辆？
- `N004 -> N005` 是否可维持 strong？

建议填写项：

```text
override_type=edge
action=mark_review_required / force_weak_connect / forbid_connect / none
edge_strength=review_only / weak / forbidden / none
reason_code=visible_unboxed_vehicle_gap / competitor_vehicle_risk / part_state_transition / review_uncertain
note=Use YOLO26l only as diagnostic candidate overlay; do not create final boxes
```

## Window Card 4：GM_RM011 237-270 重点窗口

这条窗口不是普通 `forbidden -> weak/strong` 判断。它在判断“人眼可见的大面积白车主体是否没有被当前 node/box 稳定覆盖”。

- `scene_id`: `GM_RM011`
- `frame_start`: `237`
- `frame_end`: `270`
- `related_edge_id`: `GM_RM011_E008`
- `related_node_id`: `GM_RM011_N007`, `GM_RM011_N003`
- 当前 baseline 表现：baseline 不是完全 miss，`237-270` 有较高 detection 覆盖；但当前 graph/render 没有稳定覆盖白车主体。`249`、`252` 在 baseline smoke render 中缺帧；`256-261` 被表达为 `GM_RM011_FORBIDDEN_CONTEXT_002 / forbidden_not_rendered`；`262-270` 多帧仍不能稳定表达人工关注的主体白车。
- YOLO26l 候选表现：YOLO26l 能在关键帧检出主体大框。上一轮局部 check 的 frame `256` candidate 为 `GM_RM011_000256_001`, `class_name=car`, `confidence ~= 0.904`, `bbox ~= [6.3,295.6,581.2,596.3]`。
- 是否存在 `visible_unboxed_vehicle_gap`: 是，明确存在。
- 是否存在多框竞争：存在，尤其右列 YOLO26l 也显示邻车/局部多框；这会阻止 detector-only 自动连接。
- 是否存在只框车窗/条带问题：baseline 明显存在，`N007` 更像 upper strip / forbidden context，而不是稳定主体车。
- 是否更适合人工判断同车指称：是，YOLO26l candidate 更适合作为人工验收叠加；但仍不能自动决定 `N007 -> N003` 是 weak、strong 还是 forbidden。
- 人工需要看的代表帧路径：

```text
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM011_237_270_visible_gap_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000237.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000245.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000256.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000261.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000270.png
```

人工判断问题：

- `237-270` 中白色车辆主体是否连续可见？
- 当前 `N007` 是否没有稳定表达这辆白车主体？
- 当前 `N003` 是否表达了同一辆真实车的一部分，还是已经进入另一辆车/竞争区域？
- 如果看不清节点身份，是否应先标记 `mark_review_required`，而不是直接改成 strong/weak？
- 是否仅需要 render-only 辅助显示 YOLO26l candidate，而不改变 edge？

建议填写项：

```text
override_type=edge
action=mark_review_required
edge_strength=review_only
reason_code=visible_unboxed_vehicle_gap
note=visible-but-unboxed vehicle gap; YOLO26l body candidate exists; diagnostic only, not final box, not SAR-ready
```

如果人工只想调整诊断视频显示，而不改 edge：

```text
override_type=render
action=select_diagnostic_primary_box
edge_strength=none
reason_code=visible_unboxed_vehicle_gap
note=Select existing YOLO26l diagnostic candidate for review display only; no new bbox coordinates
```

## Window Card 5：GM_RM017 118-214

这条窗口在判断 non-vehicle exclusion、白 SUV 片段、两辆深色车 forbidden guard 是否都能被人工验收。核心不是让 YOLO26l 自动判 identity，而是降低非车辆误导并辅助 dense-frame 查看。

- `scene_id`: `GM_RM017`
- `frame_start`: `118`
- `frame_end`: `214`
- `related_edge_id`: `GM_RM017_E002`, `GM_RM017_E001`
- `related_node_id`: `GM_RM017_N001`, `GM_RM017_N002`, `GM_RM017_N003`, `GM_RM017_N004`, `GM_RM017_N005`
- 当前 baseline 表现：`N001/N002/N003/N004` 可支持人工查看；`E001` 的 forbidden dark-car guard 仍需 dense frames；`E002/N005` 是 non-vehicle exclusion，需要保留人工确认。
- YOLO26l 候选表现：对 `E002/N005` 的多框误导明显降低，适合辅助 non-vehicle exclusion；对 `E001` 与 baseline 质量接近，不能替代人工判断两辆深色车。
- 是否存在 `visible_unboxed_vehicle_gap`: 未作为主问题。
- 是否存在多框竞争：存在，尤其 `E001 145-214` baseline 与 YOLO26l 都是高覆盖、高多框竞争。
- 是否存在只框车窗/条带问题：存在 partial edge / partial visibility，但不是 `GM_RM011` 那种主体白车缺口。
- 是否更适合人工判断同车指称：`E002/N005` 建议看 YOLO26l 辅助；`E001` 必须人工看 dense frames，detector-only 不能决策。
- 人工需要看的代表帧路径：

```text
outputs/oty2/yolo26l_diagnostic_render_review_packet_20260707/contact_sheets/GM_RM017_118_214_baseline_vs_yolo26l_diagnostic_contact_sheet.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000118.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000121.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000129.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000145.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000164.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000214.png
```

人工判断问题：

- `N005` 是否确实不是车辆，而是 foreground barrier / temporary structure？
- `N001` 与 `N003` 是否确实是两辆深色车，不能连接？
- `N002` 白 SUV 片段是否保持独立于深色车片段？
- YOLO26l 是否只是减少 non-vehicle false positive pressure，而不是改变 forbidden edge？

建议填写项：

```text
override_type=node / edge / none
action=exclude_non_vehicle / forbid_connect / mark_review_required / none
edge_strength=excluded / forbidden / review_only / none
reason_code=non_vehicle_box_content / similar_dark_vehicle_guard / review_uncertain / none
note=YOLO26l assists review but detector-only cannot decide GM_RM017_E001 identity
```

## 下一步建议

1. 人工先看 `GM_RM011_237_270_visible_gap` contact sheet，再看 `GM_RM011_231_292`。
2. 人工在现有 fillable Markdown 中填写判断，不直接手写 CSV。
3. 只有人工勾选“需要生成 override CSV”的项目，后续才由 Codex 或脚本提取 override CSV。
4. override dry-run 只能作用于 diagnostic timeline graph / diagnostic render manifest。
5. 任何窗口在本阶段都不允许进入 SAR。

一句话结论：

```text
YOLO26l diagnostic render review packet is ready for bounded optical diagnostic human review; all windows remain no / blocked for SAR.
```
