# OTY2 YOLO26l WGV1.2 时序连续性与多车对照机制说明

日期：`2026-07-08`

仓库：`D:/profile/research/optical-sar-visual-diagnosis`

分支：`feature/oty2-posthoc-mechanism-validation`

## 边界

本报告只推进 optical diagnostic timeline graph 的候选构造机制。它不生成 final boxes，不生成 GT boxes，不生成 final/revised annotation，不进入 SAR pairing/support/selector/ranking，也不替换全局 baseline detector。

本轮没有运行新的 YOLO detector，没有运行 tracker replay，没有生成或提交 outputs 图片/视频/权重/数组/pickle/压缩包。

## 最终目标

最终目标仍然是：

```text
小窗口 / 短 fragment / 局部 detection
-> identity-safe target family
-> same-vehicle fragment sequence
-> 单一真实车辆的完整光学时序
```

现在还不能直接从 YOLO26l detection stream 合成完整车辆时序。原因不是车辆看不见，而是多车画面中必须先解决：

- 前后框偏移是否过大；
- detection 是否按时间成序列；
- 是否出现左车/右车、白车/黑车、truck/car 切换；
- 同一帧是否有多个车辆候选在竞争；
- 当前 selected box 是否只是“当帧最显眼目标”，而不是同一辆车的下一帧。

## 新增输出

```text
tools/diagnostics/audit_oty2_yolo26l_wgv1_2_sequence_contrast.py
reports/oty2/samples/oty2_yolo26l_wgv1_2_sequence_contrast_audit_20260708.csv
reports/oty2/samples/oty2_yolo26l_wgv1_2_sequence_contrast_guardrail_rules_20260708.csv
```

这些输出是 diagnostic-only precheck，不是 V1.2 final graph，不是 revised annotation。

## 当前做到的地步

V1.1 已经证明：

1. YOLO26l 能提供比 baseline 更好的车辆主体候选；
2. 一些短片段能作为人工诊断 fragment；
3. 明显错误的 same-vehicle edge 已经被大幅收缩；
4. temporal context edge 已经能表达遮挡、邻车、禁止连接、接替关系。

但 V1.1 还没有完成：

```text
identity-safe 小窗合并
```

这次 V1.2 预审进一步把问题量化为三类：

| recommendation | count | 含义 |
| --- | ---: | --- |
| `review_multicar_contrast_before_merge` | 9 | 几何序列没有明显硬失败，但当前 manifest 缺少充分同帧多车对照，不能自动合并。 |
| `block_vehicle_merge_until_target_family_split` | 9 | 已出现前后框大偏移、类别切换、source_detection_id 复用或反复跳变，必须先拆 target family。 |
| `route_to_switch_or_context_event` | 4 | 该对象不应作为 vehicle fragment 审阅，应进入 switch zone 或 context-only event。 |

没有任何 fragment 现在可以直接视为 SAR-ready 或 final identity track。

## 如何利用前后框偏移

V1.2 不能再只看“这一帧有没有车框”，而要看“这个框和上一帧是否像同一辆车的连续观察”。

新增的时序连续性指标包括：

- `max_dx_per_frame_px`：相邻 selected frames 的 bbox 中心点横向每帧最大偏移；
- `max_normalized_dx_by_box_width`：横向偏移除以较大 bbox 宽度，防止近大远小导致阈值失真；
- `max_area_ratio` / `max_width_ratio` / `max_height_ratio`：框大小是否突然变化；
- `frame_gap_sequence`：是否缺帧太多；
- `motion_sign_change_count`：是否反复左跳右跳；
- `x_bin_sequence`：是否跨 left / mid / right 大区间跳变；
- `class_sequence`：是否发生 `truck <-> car` 等类别切换。

建议 V1.2 机制规则：

```text
center offset > 120 px/frame                 -> hard fail
center offset > 60 px/frame                  -> review gate
normalized offset by bbox width > 0.65       -> hard fail
normalized offset by bbox width > 0.35       -> review gate
area ratio > 2.5                             -> hard fail
area ratio > 1.8                             -> review gate
motion direction sign changes >= 2           -> review or hard fail
frame gap > 2 without bridge evidence        -> review gate
class switch inside fragment                 -> hard fail
left/mid/right repeated switching            -> hard fail if paired with large offset
```

这些阈值不是 final annotation 阈值，而是 diagnostic graph 的安全门槛。

## 多车情况下必须做对照

多车场景不能只保留一个 selected box。否则会发生：

```text
当前帧最强检测框
-> 下一帧另一辆车更强
-> 候选节点被错误串成同一辆车
```

V1.2 必须保留每帧候选集合：

```text
frame_id
all_vehicle_candidate_boxes
candidate_id
class_name
confidence
bbox
x_bin
size
source_detection_id
whether_selected_as_primary
target_family_id_candidate
```

然后做对照判断：

1. 当前 selected box 是否有相邻竞争车辆；
2. 相邻竞争车辆是否比 selected box 更符合前后运动；
3. 前一 fragment 的尾帧外推位置是否更接近哪个 candidate；
4. 后一 fragment 的首帧反推位置是否更接近哪个 candidate；
5. 如果两个候选都合理，不能合并为同车，只能标记 review_required 或 temporal context。

当前 manifest 的问题是：很多帧有 `multi_box_competition` 风险标签，但表里只保留了一个 selected detection，导致 `multicar_contrast_undercovered`。这类 fragment 即使几何上暂时不坏，也不能自动合并。

## 重点片段解释

### GM_RM011_WG11F001

```text
frames=0-4
max_dx_per_frame_px=17.4
max_normalized_dx_by_box_width=0.031
recommendation=review_multicar_contrast_before_merge
```

该片段前后框偏移很小，几何序列本身比较平滑。问题是 `risk_tags` 显示存在 multi-box competition，但 manifest 没有保留完整对照候选。它可以作为低风险人工审阅片段，但还不能自动并入完整车辆时序。

### GM_RM011_WG11F002

```text
frames=8-10
max_dx_per_frame_px=184.2
recommendation=block_vehicle_merge_until_target_family_split
```

尽管 V1.1 把它放入 weak group，但 V1.2 预审认为前后框偏移太大。下一步不能直接用它连接完整时序，必须检查是不是 part-state transition、近场截断导致的合理跳变，还是已经换到不同车辆/不同局部。

### GM_RM011_WG11F005

```text
frames=26-30
max_dx_per_frame_px=526.4
max_normalized_dx_by_box_width=1.889
motion_sign_change_count=2
recommendation=route_to_switch_or_context_event
```

这就是用户指出的 02 左右车混淆。它不是 vehicle fragment，而是 switch zone / same-frame competition event。

### GM_RM011_WG11F013

```text
frames=242-264
max_dx_per_frame_px=177.5
motion_sign_change_count=2
source_detection_reused_by_nodes=yes
recommendation=block_vehicle_merge_until_target_family_split
```

`237-270` 重点窗口不能只靠 YOLO26l 主体大框就合并。它需要先按 target family 拆分，再判断哪些短序列是同车。

### GM_RM017_WG11F002

```text
frames=145-158
class_switch=yes
max_dx_per_frame_px=567.4
max_normalized_dx_by_box_width=3.300
recommendation=block_vehicle_merge_until_target_family_split
```

这解释了 truck/car 混淆。它不是 detector-only 分类问题，而是 candidate stream 在不同车辆间跳转。该窗口必须先做多车对照和 target-family split。

### GM_RM017_WG11F004

```text
frames=164-185
max_dx_per_frame_px=298.8
motion_sign_change_count=3
source_detection_reused_by_nodes=yes
recommendation=block_vehicle_merge_until_target_family_split
```

这解释了白车/黑车混淆。白车和黑车都可能是 `car`，所以 class_name 不足以分身份。必须加入空间侧、外观连续、相对顺序和同帧竞争对照。

## V1.2 合并机制建议

### 1. 先建 per-frame candidate bank

每帧保留所有车辆候选，不只保留 selected primary box。

### 2. 再建 target-family candidates

用以下信息分候选家族：

- bbox center 连续性；
- bbox size 连续性；
- x_bin / 画面侧；
- class_name 稳定性；
- 颜色/外观和车身局部状态；
- 与其它候选的相对顺序；
- 遮挡和交会上下文。

### 3. 再生成 short identity-safe fragments

只有通过 sequence guardrail 的片段才能成为 `candidate_vehicle_fragment`。

### 4. 最后做 same-vehicle edge

edge 不能只看两个片段时间相邻。它必须满足：

```text
tail fragment motion projection matches head fragment
box size transition plausible
spatial side transition plausible
no better competing candidate exists
class / appearance family does not conflict
gap frames have bridge evidence or explicit review_required
```

如果不满足，就写 temporal context relation，而不是 same-vehicle edge。

## 下一步

下一步应生成 diagnostic-only V1.2 target-family split tables。建议输出：

```text
reports/oty2/samples/oty2_yolo26l_wgv1_2_target_family_candidates_20260708.csv
reports/oty2/samples/oty2_yolo26l_wgv1_2_sequence_safe_fragments_20260708.csv
reports/oty2/samples/oty2_yolo26l_wgv1_2_switch_context_events_20260708.csv
```

然后再生成新的 review pack。新 pack 要把候选车辆对照放在同一个审阅单元里，而不是只给一个 selected box 序列。

## 结论

```text
YOLO26l WGV1.2 should use temporal box continuity and multi-car contrast before any small-window merge into a single vehicle timeline.
```

当前状态是：检测候选已经可用，短片段可以诊断，但完整车辆时序合并仍处于 mechanism repair 阶段；所有结果仍然 `SAR-ready = no / blocked`。
