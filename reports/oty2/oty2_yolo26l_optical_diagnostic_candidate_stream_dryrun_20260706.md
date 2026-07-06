# OTY2 YOLO26l Optical Diagnostic Candidate Stream Dry-Run

日期：`2026-07-06`

仓库：`D:\profile\research\optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

## 路线修正

“YOLO26l 不能直接接进最终流程”不等于“YOLO26l 不使用”。当前 `GM_RM011 frames 237-270` 局部诊断已经显示：YOLO26l 能检出人工可见的大面积白色车身主体，而 baseline / 当前 diagnostic graph 没有稳定表达该车辆。

因此本 dry-run 的结论是：

```text
YOLO26l should continue as an optical diagnostic candidate source.
```

它仍然不是 baseline replacement，不是 final annotation，不是 final boxes，不是 GT boxes，也不是 SAR-ready evidence。它应进入下一阶段的 diagnostic candidate stream / diagnostic render review packet，让人工验收者能同时看到 current baseline diagnostic graph 与 YOLO26l candidate boxes 的差异。

## 边界

本报告只比较：

1. `current baseline diagnostic graph`
2. `YOLO26l local/diagnostic candidate stream`

本报告没有：

- 替换 baseline detector；
- 运行全量 detector swap；
- 比较 YOLO zoo；
- 运行 tracker replay；
- 应用 override；
- 生成 final/revised annotation；
- 生成 final boxes；
- 生成 GT boxes；
- 进入 SAR pairing/support；
- 运行 selector/ranking。

## 输入与是否重新运行 YOLO26l

本轮没有重新运行 YOLO26l。原因是已有 YOLO26l OTY0-equivalent probe 输出已经覆盖本次所有人工验收关键窗口：

```text
outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv
outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv
```

`GM_RM011 frames 237-270` 的局部 YOLO26l check 也已存在并作为重点窗口佐证：

```text
outputs/oty2/gm_rm011_237_270_visible_unboxed_vehicle_gap_yolo26l_sensitivity_20260706/yolo26l_local_detection_table.csv
```

这些 outputs 均为 ignored artifacts，不提交。

Baseline 输入：

```text
outputs/oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream/oty0_yolo_detection_table.csv
outputs/oty0_yolo_detection_stream_audit_20260701_181317/oty0_yolo_detection_table.csv
```

Diagnostic graph 输入：

```text
reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv
reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv
reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv
```

## 覆盖的关键窗口

本 dry-run 只覆盖当前 human review packet 中的节点/边窗口：

| scene_id | 覆盖范围 | 来源 |
| --- | --- | --- |
| `GM_RM011` | `0-35` | early weak/strong white vehicle windows |
| `GM_RM011` | `135-166` | right-edge review-only thin crop |
| `GM_RM011` | `231-292` | weak/strong/forbidden local timeline windows |
| `GM_RM011` | `237-270` | visible_unboxed_vehicle_gap focus window |
| `GM_RM017` | `118-214` | non-vehicle exclusion, strong/weak vehicle fragments, forbidden dark-car edge |

不覆盖全数据集，不覆盖 `GM_RM019`，不跑无关 detector。

## 评价口径

本报告使用 candidate-level 口径，不使用 final-box 口径。

字段含义：

- `baseline_usable`：当前 baseline diagnostic graph / manifest 对人工验收仍可用。
- `yolo26l_usable`：YOLO26l candidate boxes 可以作为人工验收辅助层。
- `yolo26l_better_for_review`：YOLO26l 更适合生成诊断候选叠加，帮助人工判断。
- `both_bad`：两个 detector candidate 都不能直接支持该窗口，需要其他诊断语义或人工复核。
- `needs_human_review`：检测候选不能自动决定 same-vehicle / forbidden / non-vehicle。
- `blocked_visible_unboxed_gap`：当前图没有稳定表达人眼可见车辆，不能作为普通 edge 验收。

`det/body` 中的 `body` 是针对 `GM_RM011` 下方白车主体的 proxy。对 `GM_RM017`，该 proxy 不作为最终判断依据，因为车辆尺寸、位置和截断状态不同；`GM_RM017` 主要参考已有 same-vehicle / detector stability 语义。

窗口级统计只表示 diagnostic candidate 可见性，不表示 final box 质量，也不表示 same-vehicle 真值。

- `det`：窗口内至少有一个 `car/truck/bus` candidate 的帧数 / 总帧数，可作为连续帧覆盖率的候选层近似。
- `body`：仅对 `GM_RM011` 使用的大面积下方白车主体 proxy；`body` 低通常表示当前候选更像局部条带、车窗或不稳定部位，而不是完整车身主体。
- `multi`：同一帧存在两个及以上 vehicle candidates 的帧数，表示多框竞争压力。

## Edge / Focus Window Diagnostic Candidate Statistics

| item_id | frames | baseline det/body | baseline multi | YOLO26l det/body | YOLO26l multi |
| --- | --- | --- | --- | --- | --- |
| `GM_RM011_E001` | `GM_RM011 13-35` | `22/23 (96%)` / `9/23 (39%)` | `17/23`, max `2` | `23/23 (100%)` / `13/23 (57%)` | `21/23`, max `3` |
| `GM_RM011_E002` | `GM_RM011 279-292` | `14/14 (100%)` / `6/14 (43%)` | `10/14`, max `3` | `14/14 (100%)` / `9/14 (64%)` | `11/14`, max `3` |
| `GM_RM011_E003` | `GM_RM011 262-281` | `14/20 (70%)` / `6/20 (30%)` | `9/20`, max `2` | `18/20 (90%)` / `15/20 (75%)` | `7/20`, max `2` |
| `GM_RM011_E004` | `GM_RM011 135-166` | `32/32 (100%)` / `18/32 (56%)` | `28/32`, max `4` | `31/32 (97%)` / `13/32 (41%)` | `23/32`, max `3` |
| `GM_RM011_E005` | `GM_RM011 231-245` | `14/15 (93%)` / `6/15 (40%)` | `9/15`, max `3` | `13/15 (87%)` / `8/15 (53%)` | `11/15`, max `2` |
| `GM_RM011_E006` | `GM_RM011 0-10` | `11/11 (100%)` / `4/11 (36%)` | `9/11`, max `4` | `11/11 (100%)` / `11/11 (100%)` | `8/11`, max `3` |
| `GM_RM017_E001` | `GM_RM017 145-214` | `70/70 (100%)` / `n/a` | `56/70`, max `4` | `70/70 (100%)` / `n/a` | `56/70`, max `4` |
| `GM_RM011_E007` | `GM_RM011 262-292` | `25/31 (81%)` / `12/31 (39%)` | `19/31`, max `3` | `29/31 (94%)` / `21/31 (68%)` | `17/31`, max `3` |
| `GM_RM011_E008` | `GM_RM011 256-270` | `15/15 (100%)` / `6/15 (40%)` | `13/15`, max `3` | `13/15 (87%)` / `10/15 (67%)` | `8/15`, max `4` |
| `GM_RM017_E002` | `GM_RM017 121-129` | `9/9 (100%)` / `n/a` | `9/9`, max `3` | `9/9 (100%)` / `n/a` | `1/9`, max `2` |
| `GM_RM011_VISIBLE_GAP_237_270` | `GM_RM011 237-270` | `31/34 (91%)` / `15/34 (44%)` | `22/34`, max `3` | `30/34 (88%)` / `25/34 (74%)` | `19/34`, max `4` |

Interpretation:

- `GM_RM011_E008` / `GM_RM011_VISIBLE_GAP_237_270` 不是 detector totally missed case。baseline 仍有高 `det` 覆盖，但 `body` 覆盖低且 graph/render 表达失败；YOLO26l 的 `body` 覆盖更高，所以更适合进入 diagnostic candidate stream。
- `GM_RM011_E006`、`GM_RM011_E003`、`GM_RM011_E007` 的 YOLO26l `body` 覆盖明显更高，适合生成候选叠加给人工看；但 `multi` 仍存在，不能自动转成 strong/weak/forbidden。
- `GM_RM017_E001` 的 baseline 与 YOLO26l 都是高覆盖、高多框竞争窗口，detector-only 不能解决两辆深色车的 forbidden 判断。
- `GM_RM017_E002` 中 YOLO26l 的 `multi` 压力明显低于 baseline，可辅助 non-vehicle exclusion 验收，但不取消当前 graph exclusion。

## Edge / Focus Window Summary

| item_id | scene_id | frames | current_edge_type | 当前问题类型 | baseline 候选状态 | YOLO26l 候选状态 | candidate-level 判断 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GM_RM011_E001` | `GM_RM011` | `13-35` | `strong_same_vehicle_edge` | strong same-vehicle review | baseline 检测覆盖高，当前 strong graph 可用；但同窗多框压力存在。 | YOLO26l 覆盖同样高，但多框更多；适合候选叠加，不适合自动替换。 | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_E002` | `GM_RM011` | `279-292` | `strong_same_vehicle_edge` | central white vehicle strong review | baseline 对中央白车仍可用，当前 strong edge 可验收。 | YOLO26l 覆盖近似，但不能自动解决邻车/forbidden context。 | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_E003` | `GM_RM011` | `262-281` | `weak_same_vehicle_edge` | weak part transition | baseline 不是 miss，但 current graph 对主体表达不稳定，仍是 weak/review。 | YOLO26l 对车身可见性更强，适合候选渲染辅助；但 detector-only stability summary 仍提示风险更高，不能自动升级 strong。 | `yolo26l_better_for_review; needs_human_review` |
| `GM_RM011_E004` | `GM_RM011` | `135-166` | `weak_same_vehicle_edge` | right-edge review-only thin crop | baseline review-only 仍成立。 | YOLO26l 可用但没有消除 thin edge / review-only 问题。 | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_E005` | `GM_RM011` | `231-245` | `weak_same_vehicle_edge` | weak part transition | baseline 有检测但主体覆盖不如 YOLO26l 清楚。 | YOLO26l 更好覆盖 white vehicle body，可作为人工验收候选层。 | `yolo26l_better_for_review; needs_human_review` |
| `GM_RM011_E006` | `GM_RM011` | `0-10` | `weak_same_vehicle_edge` | weak early white SUV part transition | baseline 可用但局部部位转换明显。 | YOLO26l 对车身主体覆盖更完整，适合辅助人工判断。 | `yolo26l_better_for_review; needs_human_review` |
| `GM_RM017_E001` | `GM_RM017` | `145-214` | `forbidden_edge` | forbidden dark-car false merge guard | baseline graph 的 forbidden 判断仍可用，核心证据是 dense-frame visual separability。 | YOLO26l 与 baseline 检测质量相近，不能替代人工确认两辆深色车。 | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_E007` | `GM_RM011` | `262-292` | `forbidden_edge` | competitor / forbidden bridge | baseline 和 current graph 保留 forbidden guard 是必要的。 | YOLO26l 有更强车身可见性，但 detector-only forbidden safety 仍 unresolved，不能自动放开连接。 | `yolo26l_usable; needs_human_review` |
| `GM_RM011_E008` | `GM_RM011` | `256-270` | `forbidden_edge` | visible_unboxed_vehicle_gap + forbidden bridge | baseline 不是完全 miss，但 `256` 等帧只给条带/局部，当前 graph/render 未稳定表达主体。 | YOLO26l 能检出主体大框，应进入 diagnostic candidate stream。 | `blocked_visible_unboxed_gap; yolo26l_better_for_review; needs_human_review` |
| `GM_RM017_E002` | `GM_RM017` | `121-129` | `non_vehicle_exclusion` | non-vehicle exclusion | baseline graph exclusion 仍需要保留。 | YOLO26l detector-stability summary 中 non-vehicle false positive pressure 明显降低，适合辅助非车辆验收。 | `yolo26l_better_for_review; baseline_graph_exclusion_still_required; needs_human_review` |
| `GM_RM011_VISIBLE_GAP_237_270` | `GM_RM011` | `237-270` | diagnostic gap focus | visible_unboxed_vehicle_gap focus | baseline 在 31/34 帧有 detection，但主体覆盖不稳定，且 `246-255` manifest 缺失、`256-261` forbidden skip。 | YOLO26l 在局部 check 中能检出 frame `256` 大面积主体框，适合候选渲染。 | `blocked_visible_unboxed_gap; yolo26l_better_for_review; needs_human_review` |

## Node Window Detection Coverage Statistics

| node_id | frames | baseline det/body | YOLO26l det/body |
| --- | --- | --- | --- |
| `GM_RM017_N001` | `GM_RM017 145-185` | `41/41 (100%)` / `n/a` | `41/41 (100%)` / `n/a` |
| `GM_RM017_N002` | `GM_RM017 151-200` | `50/50 (100%)` / `n/a` | `50/50 (100%)` / `n/a` |
| `GM_RM017_N003` | `GM_RM017 162-214` | `53/53 (100%)` / `n/a` | `53/53 (100%)` / `n/a` |
| `GM_RM017_N004` | `GM_RM017 118-164` | `47/47 (100%)` / `n/a` | `47/47 (100%)` / `n/a` |
| `GM_RM017_N005` | `GM_RM017 121-129` | `9/9 (100%)` / `n/a` | `9/9 (100%)` / `n/a` |
| `GM_RM011_N001` | `GM_RM011 13-16` | `4/4 (100%)` / `0/4 (0%)` | `4/4 (100%)` / `3/4 (75%)` |
| `GM_RM011_N002` | `GM_RM011 18-35` | `18/18 (100%)` / `9/18 (50%)` | `18/18 (100%)` / `9/18 (50%)` |
| `GM_RM011_N003` | `GM_RM011 262-270` | `9/9 (100%)` / `6/9 (67%)` | `7/9 (78%)` / `4/9 (44%)` |
| `GM_RM011_N004` | `GM_RM011 279-281` | `3/3 (100%)` / `0/3 (0%)` | `3/3 (100%)` / `3/3 (100%)` |
| `GM_RM011_N005` | `GM_RM011 283-292` | `10/10 (100%)` / `6/10 (60%)` | `10/10 (100%)` / `5/10 (50%)` |
| `GM_RM011_N006` | `GM_RM011 283-292` | `10/10 (100%)` / `6/10 (60%)` | `10/10 (100%)` / `5/10 (50%)` |
| `GM_RM011_N007` | `GM_RM011 256-261` | `6/6 (100%)` / `0/6 (0%)` | `6/6 (100%)` / `6/6 (100%)` |
| `GM_RM011_N008` | `GM_RM011 135-161` | `27/27 (100%)` / `13/27 (48%)` | `27/27 (100%)` / `13/27 (48%)` |
| `GM_RM011_N009` | `GM_RM011 164-166` | `3/3 (100%)` / `3/3 (100%)` | `3/3 (100%)` / `0/3 (0%)` |
| `GM_RM011_N010` | `GM_RM011 231-233` | `3/3 (100%)` / `0/3 (0%)` | `3/3 (100%)` / `2/3 (67%)` |
| `GM_RM011_N011` | `GM_RM011 236-245` | `10/10 (100%)` / `6/10 (60%)` | `8/10 (80%)` / `5/10 (50%)` |
| `GM_RM011_N012` | `GM_RM011 0-4` | `5/5 (100%)` / `4/5 (80%)` | `5/5 (100%)` / `5/5 (100%)` |
| `GM_RM011_N013` | `GM_RM011 8-10` | `3/3 (100%)` / `0/3 (0%)` | `3/3 (100%)` / `3/3 (100%)` |

Node-level interpretation:

- `GM_RM011_N007` 是最关键的 route-correction 节点：baseline 有 vehicle detections，但 `body` 为 `0/6`；YOLO26l 为 `6/6`，说明它应作为可见白车主体的 diagnostic candidate source。
- `GM_RM011_N003` 不能因此自动改成强连接。它仍需与 `N007` 的 visible_unboxed_vehicle_gap 一起人工验收。
- `GM_RM011_N009` 和 `GM_RM017` 多车窗口仍不适合 detector-only 自动判定。

## Node Window Summary

| node_id | scene_id | frames | node_type | 当前问题类型 | candidate-level 判断 |
| --- | --- | --- | --- | --- | --- |
| `GM_RM017_N001` | `GM_RM017` | `145-185` | `same_vehicle_fragment` | edge / partial visibility review | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM017_N002` | `GM_RM017` | `151-200` | `same_vehicle_fragment` | white SUV fragment review | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM017_N003` | `GM_RM017` | `162-214` | `same_vehicle_fragment` | trailing dark sedan / guard risk | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM017_N004` | `GM_RM017` | `118-164` | `context_vehicle_fragment` | context vehicle, not target identity | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM017_N005` | `GM_RM017` | `121-129` | `non_vehicle_exclusion` | non-vehicle exclusion | `yolo26l_better_for_review; baseline_graph_exclusion_still_required; needs_human_review` |
| `GM_RM011_N001` | `GM_RM011` | `13-16` | `same_vehicle_fragment` | strong local white-vehicle fragment | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_N002` | `GM_RM011` | `18-35` | `same_vehicle_fragment` | strong local white-vehicle fragment | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_N003` | `GM_RM011` | `262-270` | `weak_same_vehicle_fragment` | weak part transition / subject mismatch risk | `baseline_usable_as_detection; yolo26l_usable; needs_human_review` |
| `GM_RM011_N004` | `GM_RM011` | `279-281` | `same_vehicle_fragment` | central white vehicle strong fragment | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_N005` | `GM_RM011` | `283-292` | `same_vehicle_fragment` | central white vehicle continuation | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_N006` | `GM_RM011` | `283-292` | `forbidden_context_fragment` | left-edge competing vehicle context | `yolo26l_usable_for_context; needs_human_review` |
| `GM_RM011_N007` | `GM_RM011` | `256-261` | `forbidden_context_fragment` | visible_unboxed_vehicle_gap risk | `blocked_visible_unboxed_gap; yolo26l_better_for_review; needs_human_review` |
| `GM_RM011_N008` | `GM_RM011` | `135-161` | `review_fragment` | edge / thin crop review | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_N009` | `GM_RM011` | `164-166` | `review_fragment` | thin right-edge strip | `both_bad_for_automatic_decision; needs_human_review` |
| `GM_RM011_N010` | `GM_RM011` | `231-233` | `weak_same_vehicle_fragment` | part transition | `yolo26l_better_for_review; needs_human_review` |
| `GM_RM011_N011` | `GM_RM011` | `236-245` | `weak_same_vehicle_fragment` | part transition | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_N012` | `GM_RM011` | `0-4` | `weak_same_vehicle_fragment` | early white SUV part transition | `baseline_usable; yolo26l_usable; needs_human_review` |
| `GM_RM011_N013` | `GM_RM011` | `8-10` | `weak_same_vehicle_fragment` | early upper-window strip | `yolo26l_better_for_review; needs_human_review` |

## GM_RM011 frames 237-270 重点结论

这个窗口不应继续作为普通 `forbidden -> weak/strong` edge 验收。它是 visible_unboxed_vehicle_gap。

关键事实：

1. baseline 不是完全 miss。baseline 在 `237-270` 有 `55` 行 detection，覆盖 `31/34` 帧。
2. baseline / current graph 的问题是表达失败：`249,252,253` baseline 缺失；`254-259` 多为上半部/车窗条带；`246-255` 没有 render manifest 行；`256-261` 是 `GM_RM011_FORBIDDEN_CONTEXT_002 / forbidden_not_rendered`，renderer 默认跳过；`262-270` 的 weak box 多帧没有稳定表达人工关注的主体白车。
3. YOLO26l 能检出主体大框。此前局部 check 中，frame `256` 的 YOLO26l candidate 为：

```text
det_id = GM_RM011_000256_001
class_name = car
confidence ~= 0.904
bbox ~= [6.3,295.6,581.2,596.3]
```

4. 这说明 YOLO26l 应进入 optical diagnostic candidate stream，作为人工验收候选叠加层。
5. 这不说明 YOLO26l 可以直接生成 final boxes，也不说明该段可以进入 SAR。

## YOLO26l 明显优于 baseline 的窗口

| item_id | 原因 |
| --- | --- |
| `GM_RM011_E008` / `GM_RM011_VISIBLE_GAP_237_270` | YOLO26l 在 frame `256` 等关键帧能检出大面积白车主体，直接补足当前 visible_unboxed_vehicle_gap 的人工验收信息。 |
| `GM_RM011_N007` | 当前 node 是 forbidden context / upper strip；YOLO26l 能提供主体车身候选，适合 diagnostic render review。 |
| `GM_RM011_E005` / `GM_RM011_N010` | YOLO26l 对 `231-245` part-transition 窗口的车身主体表达更完整。 |
| `GM_RM011_E006` / `GM_RM011_N013` | YOLO26l 对早期白 SUV upper-window / rear-body 转换窗口的主体覆盖更完整。 |
| `GM_RM017_N005` / `GM_RM017_E002` | detector-stability summary 显示 YOLO26l 显著降低该 non-vehicle barrier 的 vehicle-like false positive pressure；但 graph exclusion 必须保留。 |

## baseline 仍可用的窗口

| item_id | 原因 |
| --- | --- |
| `GM_RM011_E001` | 当前 strong edge 可验收；YOLO26l 增加多框压力，不应替换 baseline。 |
| `GM_RM011_E002` | 当前 strong central white vehicle edge 可验收；YOLO26l 近似可用但不改变结论。 |
| `GM_RM011_E004` | review-only thin crop 仍由可见面积限制决定，YOLO26l 不能自动修复。 |
| `GM_RM017_E001` | forbidden dark-car edge 依赖 dense-frame visual separability；baseline 和 YOLO26l 都只能辅助，不可自动决定 identity。 |
| `GM_RM017_N001/N002/N003/N004` | 当前 diagnostic graph 可支持人工验收；YOLO26l 可作为候选层，但不是必要替换。 |

## 两者都不可靠或不能自动决策的窗口

| item_id | 原因 |
| --- | --- |
| `GM_RM011_N009` | thin right-edge strip；baseline 与 YOLO26l 都不能自动证明 same-vehicle continuity。 |
| `GM_RM011_E007` | forbidden competitor edge；YOLO26l 有更强检测，但 detector-only evidence 不能证明连接安全。 |
| `GM_RM017_E001` | 两辆深色车的 forbidden 判断不能靠 detector boxes 自动解决，必须人工验收 dense frames。 |

## 是否建议下一阶段生成 YOLO26l diagnostic render review packet

建议生成，但只能作为 diagnostic review packet。

建议形式：

```text
current baseline diagnostic render
YOLO26l candidate boxes overlay
node/edge labels
visible_unboxed_vehicle_gap marker
manual review fillable markdown
```

限制：

- 不生成 final boxes；
- 不生成 revised annotation；
- 不生成 GT boxes；
- 不运行 tracker replay；
- 不进入 SAR；
- 不把 YOLO26l 替换为 baseline；
- 不把 detector-only candidate 自动转成 strong/weak/forbidden edge。

## 是否 SAR-ready

答案：`no / blocked`。

原因：

1. `GM_RM011_E008` 当前是 visible_unboxed_vehicle_gap，不是稳定 optical diagnostic node/edge。
2. YOLO26l candidate 只解决“候选可见性”，没有解决 node identity、edge safety、forbidden context 或人工验收。
3. 当前结果没有 final boxes、没有 GT boxes、没有 revised annotation。
4. SAR consumption 仍然必须等待人工验收后的 diagnostic graph / render manifest。

## 最小下一步

1. 生成 `YOLO26l diagnostic render review packet`，只覆盖本报告列出的关键窗口。
2. 对 `GM_RM011 frames 237-270` 单独展示 baseline render、YOLO26l candidate boxes、当前 `N007/N003` 标识和 `visible_unboxed_vehicle_gap` marker。
3. 人工在 fillable Markdown 中判断是否需要：

```text
override_type=edge
action=mark_review_required
edge_strength=review_only
reason_code=visible_unboxed_vehicle_gap
```

4. 如果后续要 apply，也只能作用于 diagnostic timeline graph / diagnostic render manifest，不能生成 final annotations 或 SAR input。

## Required Answers

1. YOLO26l 是否应该继续作为 diagnostic candidate source？

是。尤其是 `GM_RM011 frames 237-270`，YOLO26l 给出了当前 graph 没有稳定表达的主体车身候选。

2. 哪些窗口 YOLO26l 明显优于 baseline？

`GM_RM011_E008` / `GM_RM011_VISIBLE_GAP_237_270`、`GM_RM011_N007`、`GM_RM011_E005/N010`、`GM_RM011_E006/N013`，以及 `GM_RM017_N005/E002` 的 non-vehicle false-positive pressure 辅助判断。

3. 哪些窗口 baseline 仍可用？

`GM_RM011_E001`、`GM_RM011_E002`、`GM_RM011_E004`、`GM_RM017_E001` 以及 `GM_RM017_N001/N002/N003/N004`。

4. 哪些窗口两者都不可靠？

`GM_RM011_N009`、`GM_RM011_E007`、`GM_RM017_E001` 不能靠 detector-only candidate 自动决策，仍需人工验收。

5. 是否建议下一阶段生成 YOLO26l diagnostic render review packet？

是。建议生成一个只覆盖当前 human review packet 关键窗口的 candidate render review packet。

6. 是否任何结果 SAR-ready？

否。全部 blocked for SAR。YOLO26l candidate stream 只允许进入 optical diagnostic review，不允许进入 SAR。

7. 最小下一步是什么？

在 ignored outputs 中生成 YOLO26l diagnostic candidate render packet，并更新人工验收包，让人工能按 edge/node 判断是否需要 `visible_unboxed_vehicle_gap`、`mark_review_required` 或 render-only override。
