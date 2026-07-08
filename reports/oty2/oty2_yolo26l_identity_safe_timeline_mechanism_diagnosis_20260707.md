# OTY2 YOLO26l 身份安全时序机制诊断

日期：`2026-07-07`

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

输入依据：

```text
reports/oty2/oty2_yolo26l_diagnostic_timeline_graph_candidate_review_packet_20260707.md
reports/oty2/samples/oty2_yolo26l_diagnostic_timeline_graph_nodes_candidate_20260707.csv
reports/oty2/samples/oty2_yolo26l_diagnostic_timeline_graph_edges_candidate_20260707.csv
reports/oty2/samples/oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv
```

输出摘要表：

```text
reports/oty2/samples/oty2_yolo26l_identity_safe_timeline_mechanism_diagnosis_summary_20260707.csv
```

## 边界

本报告只做 diagnostic mechanism diagnosis。它不应用 override，不 split node，不覆盖现有 node/edge/render manifest，不替换 baseline，不运行 tracker replay，不生成 final boxes，不生成 GT boxes，不生成 final/revised annotation，不进入 SAR pairing/support/selector/ranking。

## 诊断方法

本轮回到完整候选帧流检查，而不是只看 contact sheet 节选帧。检查对象包括：

- YOLO26l diagnostic candidate manifest 中每个 `candidate_node_id` 的全部 selected frames；
- 每帧 selected bbox 的 `center`、`area`、`width`、`height`、`confidence`、`source_detection_id`；
- 同帧所有 YOLO26l vehicle detections，用于判断 `same-frame competing boxes`；
- 当前 `candidate_edge_id` 和相关 baseline edge/node 的关系；
- 当前 ignored render frames/contact sheets 只作为可视辅助，不作为最终身份真值。

当前数据仍缺少：

- 稳定的 detector-native track id；
- ReID / appearance embedding；
- 车辆朝向标签、车头/车尾标签；
- 遮挡 mask；
- 人工确认的 vehicle identity label。

因此本文的判断是机制风险诊断和下一步修复方案，不是最终身份标注。

## 机制总述

检测连续不等于同车连续。一个窗口内持续有车辆框，只说明 detector 在持续看到某些 vehicle-like objects；它不能证明这些框都属于同一辆真实车。

一个 identity-safe node candidate 必须表示一辆真实车的连续观察片段。如果 node 内出现明显不同车辆、车头对车头交会、车尾对车头接替、遮挡导致主体切换、相邻车主框切换，node 就不能直接作为同车片段接受。

same-vehicle edge 和 temporal context relation 必须分开。same-vehicle edge 只能表示同一辆真实车；不同车辆之间的交会、遮挡、接替、邻近关系，应表达为 temporal context relation，例如：

- `front_to_front_encounter`
- `rear_to_front_adjacency`
- `vehicle_turnover_context`
- `occlusion_context_not_identity`
- `competitor_vehicle_context`

近场截断不是自动错误。只框住车窗、车身局部、局部前脸，在近场光学场景中可能仍是同一辆车；但必须有逐帧空间连续、姿态连续、相对位置连续支持。

姿态变化必须由完整帧流解释。如果某帧从侧向车身突然变成车头朝向摄像头，而中间帧没有连续过渡，应标记 `identity_switch` 或 `independent_fragment`，不能自动作为强同车边。

遮挡场景需要主体归属判断。如果框内同时包含白车和黑车，必须判断框主体是否随时序从一辆车切到另一辆车。若发生切换，应标记 `occlusion_driven_target_switch`。

## Window 1：GM_RM011 000-035

人工风险信号：`0000-0018` 看起来像同一辆近场白色 SUV，但 `0035` 可能是新车辆片段或姿态突变。

完整帧流诊断：

- `GM_RM011_Y26N001`、`Y26N002`、`Y26N003` 的局部连续性较强，可进入人工同车指称验收。
- `GM_RM011_Y26N004` 覆盖 `18-35`，但内部 bbox-flow 不安全：`26->27` center jump `504.9 px/frame`，`27->28` center jump `527.7 px/frame`，`29->30` center jump `497.8 px/frame`。
- `Y26N004` 的 same-frame competing boxes 为 `17/18`，左右位置分布为 `left/mid/right=7/3/8`，说明 selected box 在不同空间侧之间跳转。
- `Y26N003 -> Y26N004` 的边界帧 `16->18` 的 center 近似连续，但 `Y26N004` 内部不是 identity-safe 单节点。

结论：

- contact sheet signal：`confirmed_partial_risk_not_final_identity_truth`。
- same-vehicle continuity：`0-18` 局部可疑似连续，`18-35` 不能作为单一 identity-safe node 接受。
- identity switch：`yes_risk_inside_Y26N004`。
- over-merged node：`yes_Y26N004`。
- occlusion-driven target switch：不是主信号。
- structured multi-vehicle encounter：`vehicle_turnover_context_possible`。
- contact sheet sampling artifact：否，完整 bbox-flow 支持风险。
- 当前 node 是否可接受：`Y26N001/Y26N002/Y26N003` 可 review；`Y26N004` 需 split。
- 当前 edge 是否可接受：`Y26E001` weak reviewable；`Y26E002` 不应保持 strong candidate，除非先 split `Y26N004`。
- split proposal：围绕 `26-30` 的大跳变切分 `Y26N004`，至少分成 `18-25`、`26-30 ambiguous switch`、`31-35` 待复核片段。
- temporal context relation proposal：若 `0035` 经人工确认是独立片段，使用 `vehicle_turnover_context`，不是 same-vehicle edge。
- SAR-ready：`no / blocked`。

## Window 2：GM_RM011 135-166

人工风险信号：框主体可能在白车和黑车之间切换，存在遮挡驱动的 target switch。

完整帧流诊断：

- `GM_RM011_Y26N005` 覆盖 `135-161`，但内部出现明显空间跳变：`137->138` center jump `368.4 px/frame`，`150->151` area ratio `3.82`。
- `Y26N005` 的 same-frame competing boxes 为 `22/27`，first/last center 从 `153.8` 到 `727.4`，说明 selected box 从画面左/中侧跳到右边缘。
- `GM_RM011_Y26N006` 是 `164-166` thin crop，仍然只能作为 review-only。

结论：

- contact sheet signal：confirmed as occlusion / target-switch risk。
- same-vehicle continuity：not identity-safe。
- identity switch：yes risk inside `Y26N005`。
- over-merged node：yes `Y26N005`。
- occlusion-driven target switch：yes likely。
- structured multi-vehicle encounter：`occlusion_context`。
- contact sheet sampling artifact：否，完整 bbox-flow 支持风险。
- 当前 node 是否可接受：`Y26N005` 不可作为单一车辆节点接受，`Y26N006` 仍为 thin crop review。
- 当前 edge 是否可接受：`Y26E003` 只能保持 `review_only`。
- split proposal：在 `137-138` 和 `150-151` 附近切分 `Y26N005`，把白车、黑车/遮挡主体、右边缘薄片段分开验收。
- temporal context relation proposal：使用 `occlusion_context_not_identity` 表达白车和黑车邻近/遮挡关系。
- SAR-ready：`no / blocked`。

## Window 3：GM_RM011 231-292

人工风险信号：`237` 前、`245-262`、后续几帧像不同车辆片段，存在多车接替/交会。

完整帧流诊断：

- `GM_RM011_Y26N007` 在 `231-233` 内已出现较大 center jump `196.6 px/frame`。
- `GM_RM011_Y26N008` 在 `239->242` 出现 center jump `148.0 px/frame`，中间有 gap。
- `GM_RM011_Y26N009` 覆盖 `237-270`，但内部有多个身份不安全点：`239->242` jump `148.0`，`249->250` jump `178.0`，`250->251` jump `177.8`，`264->265` jump `453.9`。
- `GM_RM011_Y26N012` 在 `288->289` 出现 center jump `463.0 px/frame`，说明 `283-292` 也不应直接作为单一稳定节点接受。
- `GM_RM011_Y26N013` 是 left-edge competitor context，应保留为 forbidden/context，不是同车目标节点。

结论：

- contact sheet signal：confirmed multi-vehicle encounter risk。
- same-vehicle continuity：只有短局部片段可进入人工 review，整个 `231-292` 不是 identity-safe 连续车辆。
- identity switch：yes multiple node risks。
- over-merged node：yes，涉及 `Y26N008/Y26N009/Y26N010/Y26N012`。
- occlusion-driven target switch：possible secondary。
- structured multi-vehicle temporal encounter：yes。
- contact sheet sampling artifact：否，完整 bbox-flow 支持风险。
- 当前 node 是否可接受：只接受短局部片段进入人工验收；`Y26N009` 和 `Y26N012` 需先 split。
- 当前 edge 是否可接受：`Y26E004/Y26E006` 只能 weak review；`Y26E005` review_only；`Y26E007` forbidden guard；`Y26E008` 需先检查 `Y26N012` 的内部 split。
- split proposal：把 `231-292` 先拆成短 identity-safe fragments，例如 `231-233`、`236-245`、`237-239`、`242-264`、`265-270`、`279-288`、`289-292`，再重新评估 edge。
- temporal context relation proposal：使用 `front_to_front_encounter`、`rear_to_front_adjacency`、`vehicle_turnover_context`、`competitor_vehicle_context`。
- SAR-ready：`no / blocked`。

## Window 4：GM_RM011 237-270

人工风险信号：`237` 右侧白车与 `245` 左侧白车不是同一辆；`245-262` 可能是局部同车；`270` 与 `262` 不是同一辆；存在车头对车头和车尾对车头接替。

完整帧流诊断：

- `GM_RM011_Y26N009` 覆盖 `30/34` 帧，缺失 `240,241,267,268`。
- 该节点虽然把 visible_unboxed_vehicle_gap 转成了 YOLO26l visible-body candidate，但内部不 identity-safe。
- `Y26N009` 的最大跳变为 `264->265` center jump `453.9 px/frame`；`249->250` 和 `250->251` 也发生 `~178 px/frame` 的左右切换。
- `Y26N009` 的 `left/mid/right=10/15/5`，same-frame competing boxes 为 `19/30`，说明它跨越多个车辆主体或候选主框。
- `GM_RM011_Y26N010` 在 `262-270` 内也有 `264->265` 同一跳变，不能直接作为干净同车节点。

结论：

- contact sheet signal：confirmed，not sampling artifact。
- same-vehicle continuity：`245-262` 可作为局部同车片段候选继续人工看，但 `Y26N009` 整体不能接受。
- identity switch：yes。
- over-merged node：yes `Y26N009`。
- occlusion-driven target switch：possible secondary。
- structured_multi_vehicle_temporal_encounter：yes。
- 当前 node 是否可接受：`Y26N009` 不可 unsplit 接受；`Y26N010` 也需检查 `264-265` split。
- 当前 edge 是否可接受：`Y26E005` 必须保持 `review_only`，并改造为 temporal context candidate，而不是 same-vehicle edge。
- split proposal：将 `Y26N009` 拆为 `237-239 fragment_A`、`242-264 fragment_B_review`、`265-270 fragment_C_review`，保留缺帧 `240,241,267,268`。
- temporal context relation proposal：`front_to_front_encounter(A,B)`、`rear_to_front_adjacency(B,C)`、`vehicle_turnover_context_not_identity`。
- SAR-ready：`no / blocked`。

## Window 5：GM_RM017 118-214

人工风险信号：`145` 及之前像 truck/货车框，`164/185` 是白色轿车框，`200/214` 是黑色车框；当前 review packet 可能把多个目标放入一个窗口导致误读。

完整帧流诊断：

- `GM_RM017_Y26N002/Y26N003/Y26N004` 在 `159-162` 附近多次出现 `~600 px/frame` 的 center jump。
- `GM_RM017_Y26N005` 在 `163->164` 出现 `575.9 px/frame` jump，并在 `175->176`、`168->169`、`173->174` 等处继续跳变。
- `GM_RM017_Y26N004` 的 same-frame competing boxes 为 `50/50`，说明最高置信 vehicle candidate 在多车之间切换的风险很高。
- `GM_RM017_Y26N001` 仍是 non-vehicle/exclusion review 相关节点；当前数据不足以把 `GM_RM017_E002` 恢复为 vehicle fragment。
- `GM_RM017_E001` 是 dark-car forbidden guard。完整 bbox-flow 不支持自动合并，反而支持继续人工 forbidden guard 验收。

结论：

- contact sheet signal：confirmed window mixes review targets。
- same-vehicle continuity：整个 `118-214` 不 identity-safe；应拆成 context vehicle、white SUV、dark-car forbidden guard、non-vehicle exclusion 等目标族。
- identity switch：yes risk in highest-candidate family。
- over-merged node：yes `Y26N002/Y26N003/Y26N004/Y26N005`。
- occlusion-driven target switch：possible，但主问题是多目标混在一个 review window。
- structured_multi_vehicle_temporal_encounter：yes multi-target review window。
- contact sheet sampling artifact：否，完整 bbox-flow 支持 grouping risk。
- 当前 node 是否可接受：不能把 `Y26N001` 提升为 vehicle；其他 node 需按 target family split。
- 当前 edge 是否可接受：`GM_RM017_E001` forbidden guard 仍成立；`GM_RM017_E002` non-vehicle exclusion 不应自动恢复为 vehicle fragment。
- split proposal：分离 `pre-145 truck/context`、`164-185 white car/SUV`、`200-214 dark car`，并保留 `non_vehicle_exclusion_review` 独立项。
- temporal context relation proposal：`multi_target_review_context_not_identity`、`forbidden_guard_context`、`non_vehicle_exclusion_context`。
- SAR-ready：`no / blocked`。

## 失败层归因

| failure_layer | 涉及窗口 | 说明 |
| --- | --- | --- |
| `detector_miss` | none_primary | 本轮主要问题不是 YOLO26l miss，而是 identity-safe construction。 |
| `partial_body_detection` | `GM_RM011_000_035`, `GM_RM011_135_166` | 近场截断和局部框可接受，但必须有连续性支持。 |
| `visible_unboxed_vehicle_gap` | `GM_RM011_237_270` | 已由 YOLO26l candidate 转成 visible-body candidate，但仍 over-merged。 |
| `over_merged_node` | all five windows | 多个候选节点跨越不同车辆或不同目标族。 |
| `node_identity_switch` | all five windows | bbox center/area/空间侧跳变提示 selected box 切换。 |
| `occlusion_driven_target_switch` | `GM_RM011_135_166` | 白车/黑车遮挡和主框主体切换风险最高。 |
| `structured_multi_vehicle_temporal_encounter` | `GM_RM011_231_292`, `GM_RM011_237_270`, `GM_RM017_118_214` | 多车交会、接替或多目标 review 窗口。 |
| `temporal_context_not_identity` | `GM_RM011_135_166`, `GM_RM011_231_292`, `GM_RM011_237_270`, `GM_RM017_118_214` | 应表达上下文关系，不应表达同车边。 |
| `competitor_vehicle_risk` | `GM_RM011_231_292`, `GM_RM011_237_270` | left-edge / adjacent competitor 影响同车判断。 |
| `thin_crop_review` | `GM_RM011_135_166` | `N009/Y26N006` 仍只能 review_only。 |
| `contact_sheet_sampling_artifact` | none_confirmed | 没有窗口被确认为纯 contact sheet 抽样误差。 |
| `acceptable_same_vehicle_candidate` | local fragments only | 只限短局部片段进入人工同车指称验收。 |

## 下一步修复方案

不要直接应用修正。下一步应设计 identity-safe split proposal 和 temporal context relation proposal。

Identity-safe split proposal 规则：

1. 如果 node 内出现 `center_jump > 120 px/frame` 且同帧存在 competing boxes，必须进入 split review。
2. 如果 node 内出现左右侧反复切换，例如 selected bbox center 在 left/mid/right 多个区域之间跳转，必须进入 split review。
3. 如果 area ratio 或 width/height ratio 突变超过 `2.0`，且视觉上存在遮挡或邻车，必须标记 `occlusion_driven_target_switch` 或 `vehicle_turnover_context`。
4. 近场截断不自动判错；但必须通过连续 center、area、相对位置变化支持。
5. split proposal 只生成 diagnostic review item，不生成 final boxes。

Temporal context relation proposal 规则：

1. 车头对车头：`front_to_front_encounter`。
2. 车尾对车头：`rear_to_front_adjacency`。
3. 一车消失另一车出现：`vehicle_turnover_context`。
4. 遮挡导致框主体切换：`occlusion_context_not_identity`。
5. 邻车或竞争车辆解释更强：`competitor_vehicle_context`。

重新生成 review packet 的方式：

1. 不再把一个大窗口直接当一个同车候选链。
2. 先按 split proposal 生成短 identity-safe fragments。
3. 再将 fragment 之间的关系分成 `same_vehicle_candidate` 和 `temporal_context_not_identity`。
4. 每个 review card 同时显示完整帧范围、跳变帧、同帧 competing boxes，而不是只给节选 contact sheet。

优先级：

1. `GM_RM011 237-270`：最高，先 split `Y26N009`。
2. `GM_RM011 231-292`：最高，必须把多车接替关系从 same-vehicle edge 中剥离。
3. `GM_RM011 135-166`：高，处理遮挡驱动 target switch。
4. `GM_RM017 118-214`：高，拆分多目标 review window。
5. `GM_RM011 000-035`：中高，先解决 `Y26N004` 内部跳变，再决定 `Y26E002` 是否可作为 strong candidate review。

## 结论

YOLO26l 解决了车辆主体可见性，但没有自动解决同车身份安全。当前 candidate graph 的主要失败层已经从 detector miss 转移到 `over_merged_node`、`node_identity_switch`、`structured_multi_vehicle_temporal_encounter` 和 `temporal_context_not_identity`。

```text
No window is SAR-ready. Current work remains diagnostic mechanism diagnosis only.
```
