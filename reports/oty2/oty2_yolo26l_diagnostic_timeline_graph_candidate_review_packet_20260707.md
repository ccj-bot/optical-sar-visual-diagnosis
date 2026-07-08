# OTY2 YOLO26l 诊断时序图候选人工验收包

日期：`2026-07-07`

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

依据报告：

```text
reports/oty2/oty2_yolo26l_optical_diagnostic_candidate_stream_dryrun_20260706.md
reports/oty2/oty2_yolo26l_diagnostic_render_review_packet_20260707.md
```

## 路线调整

本阶段不再停留在 baseline vs YOLO26l 性能比较。基于前两份报告，YOLO26l 已接入 `optical diagnostic timeline graph candidate construction`，只在当前 OTY2 人工验收关键窗口内生成诊断候选节点、诊断候选边和诊断渲染清单。

这仍然不是全局 detector swap，不替换 baseline 主线，不运行 tracker replay，不生成 final/revised annotation，不生成 final boxes，不生成 GT boxes，不进入 SAR。

## 输出文件

```text
reports/oty2/samples/oty2_yolo26l_diagnostic_timeline_graph_nodes_candidate_20260707.csv
reports/oty2/samples/oty2_yolo26l_diagnostic_timeline_graph_edges_candidate_20260707.csv
reports/oty2/samples/oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv
```

Ignored 渲染输出：

```text
outputs/oty2/yolo26l_diagnostic_timeline_graph_candidate_20260707/
```

这些 PNG/contact sheets 不提交。

## 候选构建口径

- `detector_source=yolo26l`。
- 候选节点是固定关键窗口内的 diagnostic segment，不是 tracker identity，不是人工 GT。
- `GM_RM011` 使用 `large_lower_vehicle_body_proxy` 判断白车主体候选是否稳定覆盖。
- `GM_RM017` 不使用白车主体 proxy，仍按 detector candidate family 和 dense-frame 人工复核处理。
- render manifest 中的 bbox 坐标来自已有 YOLO26l detection CSV，只用于诊断渲染，不是 final boxes。
- 所有候选表均带有 `diagnostic_candidate_only;not_final_box;not_revised_annotation;not_GT;not_SAR_ready` 边界标记。

## Node Candidate Summary

| candidate_node_id | frames | related_baseline_node_id | coverage | body_summary | status | review |
| --- | --- | --- | --- | --- | --- | --- |
| `GM_RM011_Y26N001` | `0-4` | `GM_RM011_N012` | `5/5` | `large_lower_vehicle_body_proxy=5/5` | `diagnostic_body_candidate` | `no_standard_review_still_required` |
| `GM_RM011_Y26N002` | `8-10` | `GM_RM011_N013` | `3/3` | `large_lower_vehicle_body_proxy=3/3` | `diagnostic_body_candidate_review` | `yes` |
| `GM_RM011_Y26N003` | `13-16` | `GM_RM011_N001` | `4/4` | `large_lower_vehicle_body_proxy=4/4` | `diagnostic_body_candidate` | `no_standard_review_still_required` |
| `GM_RM011_Y26N004` | `18-35` | `GM_RM011_N002` | `18/18` | `large_lower_vehicle_body_proxy=18/18` | `diagnostic_body_candidate` | `no_standard_review_still_required` |
| `GM_RM011_Y26N005` | `135-161` | `GM_RM011_N008` | `27/27` | `large_lower_vehicle_body_proxy=22/27` | `diagnostic_review_only_candidate` | `yes` |
| `GM_RM011_Y26N006` | `164-166` | `GM_RM011_N009` | `3/3` | `large_lower_vehicle_body_proxy=0/3` | `diagnostic_thin_crop_candidate` | `yes` |
| `GM_RM011_Y26N007` | `231-233` | `GM_RM011_N010` | `3/3` | `large_lower_vehicle_body_proxy=3/3` | `diagnostic_body_candidate_review` | `yes` |
| `GM_RM011_Y26N008` | `236-245` | `GM_RM011_N011` | `8/10` | `large_lower_vehicle_body_proxy=8/10` | `diagnostic_body_candidate_review` | `yes` |
| `GM_RM011_Y26N009` | `237-270` | `GM_RM011_N007;GM_RM011_N003` | `30/34` | `large_lower_vehicle_body_proxy=30/34` | `diagnostic_visible_body_node_candidate` | `yes` |
| `GM_RM011_Y26N010` | `262-270` | `GM_RM011_N003` | `7/9` | `large_lower_vehicle_body_proxy=7/9` | `diagnostic_handoff_fragment_candidate` | `yes` |
| `GM_RM011_Y26N011` | `279-281` | `GM_RM011_N004` | `3/3` | `large_lower_vehicle_body_proxy=3/3` | `diagnostic_body_candidate` | `no_standard_review_still_required` |
| `GM_RM011_Y26N012` | `283-292` | `GM_RM011_N005` | `10/10` | `large_lower_vehicle_body_proxy=10/10` | `diagnostic_body_candidate` | `no_standard_review_still_required` |
| `GM_RM011_Y26N013` | `283-292` | `GM_RM011_N006` | `4/10` | `left_edge_competitor_proxy=4/10` | `diagnostic_forbidden_context_candidate` | `yes` |
| `GM_RM017_Y26N001` | `121-129` | `GM_RM017_N005` | `9/9` | `body_proxy=n/a_for_GM_RM017` | `diagnostic_non_vehicle_exclusion_review` | `yes` |
| `GM_RM017_Y26N002` | `118-164` | `GM_RM017_N004` | `47/47` | `body_proxy=n/a_for_GM_RM017` | `diagnostic_context_candidate_review` | `yes` |
| `GM_RM017_Y26N003` | `145-185` | `GM_RM017_N001` | `41/41` | `body_proxy=n/a_for_GM_RM017` | `diagnostic_dark_vehicle_candidate_review` | `yes` |
| `GM_RM017_Y26N004` | `151-200` | `GM_RM017_N002` | `50/50` | `body_proxy=n/a_for_GM_RM017` | `diagnostic_white_suv_candidate_review` | `yes` |
| `GM_RM017_Y26N005` | `162-214` | `GM_RM017_N003` | `53/53` | `body_proxy=n/a_for_GM_RM017` | `diagnostic_trailing_dark_vehicle_candidate_review` | `yes` |

## Edge Candidate Summary

| candidate_edge_id | related_baseline_edge_id | from_to | strength | reason_code | review |
| --- | --- | --- | --- | --- | --- |
| `GM_RM011_Y26E001` | `GM_RM011_E006` | `GM_RM011_Y26N001 -> GM_RM011_Y26N002` | `weak` | `part_state_transition` | `yes` |
| `GM_RM011_Y26E002` | `GM_RM011_E001` | `GM_RM011_Y26N003 -> GM_RM011_Y26N004` | `strong_candidate_for_review` | `short_gap_body_continuity` | `no_standard_review_still_required` |
| `GM_RM011_Y26E003` | `GM_RM011_E004` | `GM_RM011_Y26N005 -> GM_RM011_Y26N006` | `review_only` | `thin_edge_crop` | `yes` |
| `GM_RM011_Y26E004` | `GM_RM011_E005` | `GM_RM011_Y26N007 -> GM_RM011_Y26N008` | `weak` | `part_state_transition` | `yes` |
| `GM_RM011_Y26E005` | `GM_RM011_E008` | `GM_RM011_Y26N009 -> GM_RM011_Y26N010` | `review_only` | `visible_unboxed_vehicle_gap_reframed_as_yolo26l_node` | `yes` |
| `GM_RM011_Y26E006` | `GM_RM011_E003` | `GM_RM011_Y26N010 -> GM_RM011_Y26N011` | `weak` | `longer_gap_part_transition` | `yes` |
| `GM_RM011_Y26E007` | `GM_RM011_E007` | `GM_RM011_Y26N010 -> GM_RM011_Y26N013` | `forbidden` | `competitor_vehicle_risk` | `yes` |
| `GM_RM011_Y26E008` | `GM_RM011_E002` | `GM_RM011_Y26N011 -> GM_RM011_Y26N012` | `strong_candidate_for_review` | `central_white_vehicle_continuity` | `no_standard_review_still_required` |
| `GM_RM017_Y26E001` | `GM_RM017_E002` | `GM_RM017_Y26N001 -> GM_RM017_Y26N001` | `excluded_review` | `non_vehicle_box_content_review` | `yes` |
| `GM_RM017_Y26E002` | `GM_RM017_E001` | `GM_RM017_Y26N003 -> GM_RM017_Y26N005` | `forbidden` | `similar_dark_vehicle_guard` | `yes` |

## GM_RM011 237-270 重点结论

`GM_RM011 237-270` 已从单纯 `visible_unboxed_vehicle_gap` 记录推进为 YOLO26l diagnostic node candidate：

```text
candidate_node_id=GM_RM011_Y26N009
related_baseline_node_id=GM_RM011_N007;GM_RM011_N003
frame_start=237
frame_end=270
covered_frame_count=30
missing_frame_count=4
vehicle_body_coverage_summary=large_lower_vehicle_body_proxy=30/34; selected_candidate_frames=30/34
diagnostic_status=diagnostic_visible_body_node_candidate
```

该节点候选表示：YOLO26l 在旧的 `N007 -> N003 / E008` 缺口中能稳定给出白车主体诊断候选。它只允许进入人工诊断验收，不是 final box，不是 revised annotation，不是 GT，不是 SAR-ready evidence。

对 `GM_RM011_E008`，新的候选边为：

```text
candidate_edge_id=GM_RM011_Y26E005
candidate_edge_type=visible_body_gap_reframed_candidate
connection_strength=review_only
reason_code=visible_unboxed_vehicle_gap_reframed_as_yolo26l_node
```

这意味着：不要再用 baseline graph 硬判 `N007/N003`；应先让人工查看 YOLO26l candidate graph render，再决定是否填写 `mark_review_required`、`force_weak_connect` 或保持 forbidden/review_only。

## 覆盖了哪些 baseline 缺口

- `GM_RM011_N007 / GM_RM011_E008`：原来是 forbidden context / visible_unboxed_vehicle_gap，现在有 `GM_RM011_Y26N009` 白车主体诊断候选。
- `GM_RM011_N013 / GM_RM011_E006`：原 baseline 更像 upper-window strip，YOLO26l 给出更完整的早期白 SUV 主体候选。
- `GM_RM011_N010/N011 / GM_RM011_E005`：YOLO26l 改善 `231-245` part-transition 车辆主体表达，可进入人工同车指称验收。
- `GM_RM017_N005 / GM_RM017_E002`：YOLO26l 仅辅助 non-vehicle exclusion 复核，不把该节点提升为车辆身份。

## 可以重新进入人工验收的 baseline edge

- `GM_RM011_E006`：可用 `GM_RM011_Y26N001 -> GM_RM011_Y26N002` 重新看早期白 SUV 弱连接。
- `GM_RM011_E005`：可用 `GM_RM011_Y26N007 -> GM_RM011_Y26N008` 重新看 `231-245` part transition。
- `GM_RM011_E008`：必须用 `GM_RM011_Y26N009` 作为 visible-body diagnostic node candidate 重新验收，而不是沿用 baseline forbidden-context 框硬判。
- `GM_RM011_E003`：可用 `GM_RM011_Y26N010 -> GM_RM011_Y26N011` 进入 weak/review 验收。
- `GM_RM011_E001`、`GM_RM011_E002`：baseline 已可用，YOLO26l 只是辅助同车指称验收。

## 仍然 detector-only 无法决定的窗口

- `GM_RM011_E007`：竞争车辆风险仍在，候选边保持 forbidden guard。
- `GM_RM011_N009 / GM_RM011_E004`：右边缘 thin crop 仍需要 review_only。
- `GM_RM017_E001`：两辆深色车必须人工看 dense frames，不能由 detector-only 自动决定。
- `GM_RM017_E002`：仍是 non-vehicle exclusion review，不提升为 vehicle node。

## 仍然 review_required 的窗口

- `GM_RM011 237-270` / `GM_RM011_Y26N009` / `GM_RM011_Y26E005`。
- `GM_RM011 231-245` / `GM_RM011_Y26E004`。
- `GM_RM011 135-166` / `GM_RM011_Y26E003`。
- `GM_RM011_E007` forbidden guard。
- `GM_RM017_E001` 和 `GM_RM017_E002`。

## 是否可进入人工同车指称验收

可以，但只限 optical diagnostic review：

- `GM_RM011_E006`、`GM_RM011_E005`、`GM_RM011_E008`、`GM_RM011_E003`、`GM_RM011_E001`、`GM_RM011_E002` 可进入人工同车指称验收。
- `GM_RM017_E001` 可进入人工 forbidden guard 验收。
- `GM_RM017_E002` 可进入人工 non-vehicle exclusion 验收。

## 是否 SAR-ready

答案：`no / blocked`。

原因：

1. 所有节点和边都是 `diagnostic_candidate_only`。
2. bbox 坐标只来自 YOLO26l detection CSV，用于诊断渲染，不是 final boxes。
3. 没有人工 override 应用结果，没有 revised annotation，没有 GT boxes。
4. `GM_RM011 237-270` 虽然已有 YOLO26l visible-body node candidate，但仍必须人工复核 same-vehicle referent 和 edge safety。
5. SAR pairing/support/selector/ranking 仍然禁止。

## 人工验收建议

1. 先看 ignored render：`outputs/oty2/yolo26l_diagnostic_timeline_graph_candidate_20260707/contact_sheets/GM_RM011_237_270_visible_body_candidate_graph.png`。
2. 再看 `GM_RM011_231_292_candidate_graph.png`，确认白车主体、邻车和 left-edge competitor 是否分离。
3. 人工在 fillable Markdown 中填写判断；本阶段不提取 override CSV。
4. 若后续提取 override CSV，也只能作用于 diagnostic timeline graph / diagnostic render manifest。

一句话结论：

```text
YOLO26l optical diagnostic timeline graph candidate is constructed for bounded human review; GM_RM011 237-270 is now a YOLO26l diagnostic visible-body node candidate, but all windows remain no / blocked for SAR.
```
