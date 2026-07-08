# OTY2 YOLO26l WGV1.1 多车混淆故障分析与 V1.2 机制修正

日期：`2026-07-08`

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

## 边界

本报告只处理 YOLO26l optical diagnostic working graph 的多车身份安全问题。它不是 final annotation，不是 revised annotation，不是 final boxes，不是 GT boxes，也不是 SAR-ready evidence。

本轮没有运行 detector swap、YOLO probe、tracker replay、SAR pairing/support/selector/ranking，也没有应用 override。

## 输入

```text
reports/oty2/oty2_yolo26l_optical_timeline_working_graph_v1_1_auto_review_and_repair_20260708.md
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_vehicle_fragments_20260708.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_same_vehicle_edges_20260708.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_temporal_context_edges_20260708.csv
reports/oty2/samples/oty2_yolo26l_optical_timeline_working_graph_v1_1_blocked_review_items_20260708.csv
reports/oty2/samples/oty2_yolo26l_diagnostic_render_manifest_candidate_20260707.csv
outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708/
```

新增审计摘要：

```text
reports/oty2/samples/oty2_yolo26l_wgv1_1_multivehicle_identity_audit_20260708.csv
```

## 一句话结论

用户指出的 `02`、`13`、`16`、`17`、`18` 不是普通人工验收难点，而是 V1.1 candidate construction / review-pack generation 的机制缺陷：当前流程把 detection candidate stream 当成了 identity-stable vehicle fragment stream，并且在多车画面中允许同一个 detection 被多个 candidate_node_id 复用，导致 truck/car、白车/黑车、左车/右车被同一个 fragment 或同一类候选标签串起来。

因此，V1.2 必须先加入多车身份安全门槛，再生成 vehicle-centric review pack。

## Codex 可直接作出的判断

在不进入 final annotation、不写 final boxes、不进入 SAR 的前提下，Codex 可以根据现有表、manifest 和 ignored 审阅图作出以下诊断判断：

- `02_GM_RM011_fragment_GM_RM011_WG11F005_blocked` 不是同一辆车的逐帧片段，应改为 `switch_zone` / `same_frame_competition` 事件，不应作为 vehicle fragment 文件夹展示。
- `13_GM_RM011_fragment_GM_RM011_WG11F017_forbidden` 是 context-only competitor。当前审阅包按 `283-292` 整段放图，但该 context candidate 只有 `283-286` 有 selected frames；`287-292` 不应进入该 fragment 的 `frames_yolo`。
- `16_GM_RM017_fragment_GM_RM017_WG11F002_review_required` 内部从 truck 跳到左侧 car，再跳回右侧 truck，不是同车连续。
- `17_GM_RM017_fragment_GM_RM017_WG11F003_blocked` 已经是 blocked，但仍不应以 vehicle fragment 形式审阅；它应是 `multi_target_switch_zone`。
- `18_GM_RM017_fragment_GM_RM017_WG11F004_review_required` 不能作为白车单车片段直接审阅；它存在左右/中间跳变、白车/黑车主体切换风险，并且同一 source_detection_id 被多个 candidate_node_id 复用。

这些判断是 diagnostic graph 层的 negative / blocked 判断，不是车辆身份真值，也不是最终标注。

## 逐项故障定位

### 02：GM_RM011_WG11F005

文件夹：

```text
outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708/02_GM_RM011_fragment_GM_RM011_WG11F005_blocked/
```

表内范围：

```text
scene_id=GM_RM011
fragment_id=GM_RM011_WG11F005
frames=26-30
source_candidate_node_id=GM_RM011_Y26N004
accepted_status=blocked
identity_safety_status=identity_switch_zone
```

审计结果：

```text
x_bin_sequence=right left right right left
max_center_jump_px=526.4
risk_flags=large_center_jump;left_mid_right_bin_switch;not_a_vehicle_identity_fragment
```

可视诊断：

- frame `000026`：框在画面右下白色车身区域。
- frame `000027`：框跳到左侧近处白车。
- frame `000028-000029`：框又回到右侧。
- frame `000030`：框再跳回左侧。

根因：

`GM_RM011_Y26N004` 是多车同框里的逐帧候选选择结果，不是单一车辆身份流。V1.1 已把它标成 blocked，但 vehicle-centric pack 仍把它做成“fragment 文件夹”，这会误导人工按单车连续性去看。

V1.2 修正：

```text
GM_RM011_WG11F005 -> switch_zone
不要生成 vehicle fragment folder
只在 SWITCH_ZONES / CONTEXT_LINKS 中记录 same_frame_competition
```

### 13：GM_RM011_WG11F017

文件夹：

```text
outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708/13_GM_RM011_fragment_GM_RM011_WG11F017_forbidden/
```

表内范围：

```text
scene_id=GM_RM011
fragment_id=GM_RM011_WG11F017
frames=283-292
source_candidate_node_id=GM_RM011_Y26N013
accepted_status=forbidden
identity_safety_status=context_only_competitor
```

审计结果：

```text
span_frame_count=10
selected_frame_count=4
pack_frames_yolo_count=10
risk_flags=sparse_selected_frames_inside_fragment_span;review_pack_frame_range_overrun;not_a_vehicle_identity_fragment
```

根因：

`GM_RM011_Y26N013` 只在 frames `283-286` 有 selected context candidate。审阅包生成时按 fragment 的 `frame_start-frame_end` 全范围拷图，把 `287-292` 也放进了 `frames_yolo`。这些后续帧不属于该 context-only competitor 的 selected-frame 证据。

V1.2 修正：

```text
context-only fragment 必须按 selected-frame rows 渲染/拷贝
不得按 frame range 填满缺失帧
forbidden/context-only item 不进入 vehicle identity folder
```

### 16：GM_RM017_WG11F002

文件夹：

```text
outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708/16_GM_RM017_fragment_GM_RM017_WG11F002_review_required/
```

表内范围：

```text
scene_id=GM_RM017
fragment_id=GM_RM017_WG11F002
frames=145-158
source_candidate_node_ids=GM_RM017_Y26N003;GM_RM017_Y26N004
accepted_status=review_required
identity_safety_status=target_family_context_candidate
```

审计结果：

```text
class_names=car;truck
x_bin_sequence=mid mid mid mid left left left left left left left right right left
max_center_jump_px=567.4
duplicate_source_detection_count=14
risk_flags=class_switch_inside_fragment;large_center_jump;left_mid_right_bin_switch;source_detection_reused_by_multiple_candidate_nodes
```

可视诊断：

- frame `000145`：框住中间 truck。
- frame `000149`：同一 fragment 标签下框住左侧 car。
- frame `000156`：又跳到右侧 truck。

根因：

这不是 YOLO26l 简单把 truck 误分类成 car，而是 candidate construction 把“每帧当前最强 vehicle-like detection”复用到了多个 candidate_node_id。`GM_RM017_Y26N003`、`GM_RM017_Y26N004` 在该窗口共享同一批 `source_detection_id`，candidate_node_id 不再代表稳定车辆身份。

V1.2 修正：

```text
truck <-> car class switch inside fragment = hard fail
left/mid/right 大跳变 = hard fail
source_detection_id 被多个 candidate_node_id 复用 = hard fail
GM_RM017_WG11F002 -> multi_target_review_window
必须先按 target family 拆分，再生成任何 vehicle folder
```

### 17：GM_RM017_WG11F003

文件夹：

```text
outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708/17_GM_RM017_fragment_GM_RM017_WG11F003_blocked/
```

表内范围：

```text
scene_id=GM_RM017
fragment_id=GM_RM017_WG11F003
frames=159-163
source_candidate_node_ids=GM_RM017_Y26N002;GM_RM017_Y26N003;GM_RM017_Y26N004;GM_RM017_Y26N005
accepted_status=blocked
identity_safety_status=node_identity_switch_zone
```

审计结果：

```text
class_names=car;truck
x_bin_sequence=left right left right right
max_center_jump_px=614.7
duplicate_source_detection_count=5
risk_flags=class_switch_inside_fragment;large_center_jump;left_mid_right_bin_switch;source_detection_reused_by_multiple_candidate_nodes;not_a_vehicle_identity_fragment
```

根因：

V1.1 已将该片段标成 blocked，但 vehicle-centric review pack 仍给了一个 `fragment_*` 文件夹。人工打开后会自然地尝试判断“这个 fragment 内部是否同车”，但该对象从定义上就不是 vehicle fragment，而是 switch/context event。

V1.2 修正：

```text
blocked identity_switch_zone 不得生成 vehicle fragment 文件夹
改放 SWITCH_ZONES/GM_RM017_159_163/
README 问题应改成“这里有哪些候选车辆在竞争”，而不是“是否同一辆车”
```

### 18：GM_RM017_WG11F004

文件夹：

```text
outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708/18_GM_RM017_fragment_GM_RM017_WG11F004_review_required/
```

表内范围：

```text
scene_id=GM_RM017
fragment_id=GM_RM017_WG11F004
frames=164-185
source_candidate_node_id=GM_RM017_Y26N004
accepted_status=review_required
identity_safety_status=target_family_context_candidate
```

审计结果：

```text
class_names=car
x_bin_sequence=left left left left left mid right right right right mid mid right right right right right right mid right right right
max_center_jump_px=298.8
duplicate_source_detection_count=22
risk_flags=large_center_jump;left_mid_right_bin_switch;source_detection_reused_by_multiple_candidate_nodes
```

可视诊断：

- frame `000164`：图上白车和黑车相邻，框偏向白车区域。
- frame `000176`：同一 review folder 下框到右侧黑车。

根因：

这里的混淆不是 `car` 类别标签能解决的问题，因为白车和黑车都可能被 YOLO26l 标成 `car`。问题是 candidate stream 缺少 target-family separation：颜色/外观、空间侧、相对顺序、遮挡关系没有进入节点构造门槛。再加上同一 `source_detection_id` 被 `GM_RM017_Y26N003/Y26N004/Y26N005` 多个 candidate_node_id 复用，候选标签本身失去身份含义。

V1.2 修正：

```text
GM_RM017_WG11F004 -> multi_target_review_window until target-family split passes
白车/黑车相邻场景必须先拆成 target family，再生成 vehicle-centric folder
仅凭 class_name=car 和连续检测不得建立 identity fragment
```

## 根因归纳

### 1. candidate_node_id 不是 identity-safe

当前 `candidate_node_id` 可以表示“某窗口中的候选检测流”，但在多车画面中它不一定表示同一辆真实车。GM17 中同一个 `source_detection_id` 被多个 `candidate_node_id` 同时引用，直接证明候选节点家族发生重叠。

### 2. 逐帧最高候选选择会在多车场景中跳对象

在 GM_RM011 26-30 和 GM_RM017 145-185 中，主框不是沿同一辆车平滑移动，而是在左/中/右目标之间跳。这个机制会把“同一帧里更显眼的车”误当成“同一辆车的下一帧”。

### 3. review pack 生成用了 frame range，而不是 selected-frame evidence

`GM_RM011_WG11F017` 表明 context-only candidate 只有 4 帧证据，但 pack 放了 10 张图。vehicle-centric pack 必须以 selected-frame manifest rows 为准，不能用 fragment 的完整 frame range 自动补图。

### 4. blocked/context item 的展示形态错误

V1.1 把一些片段标成 blocked / forbidden / context_only 是对的，但后续仍以 `fragment_*` 文件夹呈现，导致人工误以为它们是待判断的车辆片段。机制上要分开：

- `vehicle_fragment`：可以看同车连续性；
- `switch_zone`：只能看竞争目标和切换点；
- `context_only_competitor`：只能看禁止连接/邻接上下文；
- `multi_target_review_window`：先拆 target family，再谈 vehicle-centric review。

## V1.2 机制修正

### 硬门槛

1. `source_detection_id` 不得被多个 `candidate_node_id` 当作不同车辆身份复用；如复用，只能标成 `node_family_overlap_duplicate_detection`。
2. fragment 内出现 `truck <-> car` class switch 时，直接降级为 `class_switch_multi_target_zone`。
3. fragment 内出现 left/mid/right 反复切换，或 `center_jump > 120 px/frame` 且同帧存在多车竞争时，直接降级为 `multi_target_switch_zone`。
4. `blocked`、`forbidden`、`context_only_competitor` 不得进入 vehicle-centric folder；只能进入 `SWITCH_ZONES` 或 `CONTEXT_ONLY`。
5. review pack 必须按 selected-frame rows 生成。缺失 selected detection 的帧不能自动拷入该 fragment 的 `frames_yolo`。
6. 白车/黑车、左车/右车相邻时，`class_name=car` 不能作为 identity 证据；必须引入 target-family separation：空间侧、颜色/外观、相对顺序、遮挡关系和连续运动。

### 新状态建议

```text
candidate_vehicle_fragment
weak_vehicle_fragment
switch_zone
multi_target_review_window
context_only_competitor
class_switch_multi_target_zone
node_family_overlap_duplicate_detection
render_pack_frame_range_overrun
```

### vehicle-centric pack 生成顺序

```text
selected-frame manifest
-> source_detection_id uniqueness audit
-> class / spatial-side / center-jump guardrail
-> target-family split
-> only then build vehicle_fragment folders
-> switch/context items go to separate folders
```

## 对当前 pack 的处理建议

当前目录：

```text
outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708/
```

应标记为 `superseded_for_multivehicle_identity_review`，尤其不要继续用以下文件夹判断同车身份：

```text
02_GM_RM011_fragment_GM_RM011_WG11F005_blocked
13_GM_RM011_fragment_GM_RM011_WG11F017_forbidden
16_GM_RM017_fragment_GM_RM017_WG11F002_review_required
17_GM_RM017_fragment_GM_RM017_WG11F003_blocked
18_GM_RM017_fragment_GM_RM017_WG11F004_review_required
```

下一步应先生成 V1.2 diagnostic-only target-family split tables，再重新生成 review pack。新的 pack 不应再让人工回答“这些帧是不是同一辆车”，而应先按事件类型提问：

- 对 `switch_zone`：这里是哪几个目标在竞争？切换发生在哪些帧？
- 对 `context_only_competitor`：它是否只用于禁止连接/邻接上下文？
- 对 `multi_target_review_window`：能否拆出稳定 target family？
- 对 `candidate_vehicle_fragment`：片段内部是否同车连续？

## SAR-ready

```text
SAR-ready = no / blocked
```

这些问题属于 optical diagnostic graph 的候选构造和人工审阅入口问题。任何当前结果都不得进入 SAR pairing/support/selector/ranking。
