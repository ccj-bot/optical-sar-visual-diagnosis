# OTY2 光学时序人工验收包

日期：2026-07-06
仓库：`D:/profile/research/optical-sar-visual-diagnosis`
分支：`feature/oty2-posthoc-mechanism-validation`
英文原文件：`reports/oty2/oty2_optical_timeline_human_review_packet_20260706.md`
当前基础 HEAD：`f6ed62d Add OTY2 optical timeline human review packet`

## 怎么使用本文件

人工验收者建议按下面顺序看：

1. 先看 non-vehicle exclusion，确认这些节点是否确实不是车。
2. 再看 forbidden，确认这些节点关系是否确实不能连接。
3. 再看 strong，确认这些强连接是否确实指向同一辆真实车。
4. 最后看 weak，判断保留弱连接、升级强连接，还是改为禁止连接。

每条 edge 都是一个独立检查项。先看列出的代表帧 PNG，再按关键帧范围连续翻看快速试渲染帧。如果当前判断不需要改，通常不用填写人工修正规则表 CSV；只有当前判断需要改、需要显式留痕、或需要标记复核时，才填写 override CSV。

## 范围边界

本文件用于指导人工验收当前 optical diagnostic timeline graph。它只基于现有 node table、edge table、render manifest 和 smoke render 诊断帧。

本文件不应用 override，不运行 detector swap，不运行 YOLO probe，不运行 tracker replay，不进入 SAR pairing/support，不运行 selector/ranking，不生成 final/revised annotation，不生成 final boxes，也不生成 GT boxes。

这里的 node 表示节点 / 车辆观察片段；edge 表示边 / 节点关系。所有判断都只服务于诊断用光学时序图和诊断用渲染清单，不是最终标注。

## 来源文件

| 角色 | 路径 | 状态 |
| --- | --- | --- |
| Node table | `reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv` | 18 rows |
| Edge table | `reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv` | 10 rows |
| Render manifest | `reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv` | 311 rows |
| Smoke render frames | `outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames` | 198 ignored PNG frames |
| Override template | `manifests/oty2_optical_timeline_override_template.csv` | header-only template |
| Override schema | `configs/oty2_optical_timeline_override_schema.yaml` | dry-run contract |
| Override validator | `tools/diagnostics/validate_oty2_optical_timeline_overrides.py` | dry-run only |

渲染帧路径规则：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/<scene_id>_<frame:06d>.png
```

示例：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000013.png
```

## 人工判断尺度

| 人工判断 | 含义 | 需要填写 override CSV 时的 action |
| --- | --- | --- |
| 接受当前强连接 | 前后节点在视觉上支持同一辆真实车。 | 不需要填写，或用 `force_strong_connect` 留显式验收记录。 |
| 接受当前弱连接 | 同车指称是合理的，但只能保持弱连接或需要复核标记。 | 不需要填写，或用 `force_weak_connect` 留显式验收记录。 |
| 弱连接升级为强连接 | 全帧上下文足够支持强同车指称。 | `upgrade_to_strong`，并填 `edge_strength=strong`。 |
| 强连接降级为弱连接 | 仍可能是同一辆车，但证据不足以保持强连接。 | `downgrade_to_weak`，并填 `edge_strength=weak`。 |
| 禁止连接 | 前后节点发生目标切换、指向非车辆、或无法排除其他车辆插入。 | `forbid_connect`，并填 `edge_strength=forbidden`。 |
| 标记需要复核 | 人工当前无法安全判断。 | `mark_review_required`，并填 `edge_strength=review_only`。 |
| 确认非车辆节点 | 该节点不是车辆观察片段。 | 不需要填写，或用 node `exclude_non_vehicle` 留显式验收记录。 |
| 仅调整诊断渲染主框 | 当前渲染主框误导人工阅读，但已有检测框中有更合适的诊断主框。 | render `select_diagnostic_primary_box`；必须使用已有 `source_detection_id`，不能写新坐标。 |

重要：override row 不是最终标签。它只是在后续明确允许 apply 时，影响诊断用 timeline graph 或诊断用 render manifest。

## override CSV 填写提示

只有在人工判断不同于当前 edge，或需要显式留下验收记录时，才填写 `manifests/oty2_optical_timeline_override_template.csv`。

edge 决策建议填写这些 CSV 字段：

```text
override_id,override_type=edge,override_scope=edge,scene_id,from_node_id,to_node_id,action,edge_strength,reason_code,evidence_frame_start,evidence_frame_end,confidence,review_status,note
```

node 决策建议填写这些 CSV 字段：

```text
override_id,override_type=node,override_scope=node,scene_id,node_id,action,reason_code,confidence,review_status,note
```

仅用于诊断渲染主框选择时，建议填写：

```text
override_id,override_type=render,override_scope=event,scene_id,frame_start,frame_end,target_node_id,action=select_diagnostic_primary_box,source_detection_id,reason_code=diagnostic_primary_box_selection,review_status,note
```

禁止添加 bbox 坐标列。禁止写 final boxes 或 GT boxes。禁止把 override CSV 当成人工逐帧标注表。

编辑 override CSV 后，用校验器做 dry-run：

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_optical_timeline_overrides.py --overrides manifests\oty2_optical_timeline_override_template.csv
```

## Non-Vehicle Exclusion：非车辆排除

### GM_RM017_E002

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM017` |
| from_node | `GM_RM017_N005` |
| to_node | `GM_RM017_N005` |
| current_edge_type | `non_vehicle_exclusion` |
| connection_strength | `excluded` |
| node range | `GM_RM017_N005`, `GM_RM017_NONVEHICLE_001`, frames `121-129` |
| key frame range | `121-129` |
| rendered frame count in range | 9 |
| visual basis | 当前框跟随的是前景路障或临时结构，不是车辆。 |
| current reason | 这是一个用于排除非车辆 track content 的一元 exclusion edge。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000121.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000125.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000129.png
```

人工需要判断：

- 框内内容是否确实是前景路障、临时结构或其他非车辆对象？
- 该 node 是否应该继续从车辆时序图中排除？
- 这个问题更适合记为 `exclude_non_vehicle`、`mark_bad_detection_node`，还是 `mark_review_required`？
- 是否需要在诊断渲染中显示非车辆 marker，避免后续误读？
- 是否需要填写 override CSV？如果接受当前非车辆排除，通常不需要。

override CSV 提示：

- 接受当前排除：不需要填写；如需留痕，可填 node `action=exclude_non_vehicle`，`reason_code=non_vehicle_barrier`。
- 如果其实是车辆节点：填 node `action=keep_vehicle_node`，`reason_code=custom_vehicle_referent`。
- 如果只是坏检测框：填 node `action=mark_bad_detection_node`，`reason_code=bad_detection_box_fit`。
- 如果不确定：填 node `action=mark_review_required`，`reason_code=review_uncertain`。
- 仅需要渲染标记：填 render `action=show_non_vehicle_marker`。

## Forbidden Edges：禁止连接

### GM_RM017_E001

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM017` |
| from_node | `GM_RM017_N001` |
| to_node | `GM_RM017_N003` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM017_N001`, `GM_RM017_V001`, frames `145-185` |
| to range | `GM_RM017_N003`, `GM_RM017_V003`, frames `162-214` |
| key frame range | `145-214` |
| rendered frame count in range | 70 |
| visual basis | 密集帧显示这是两辆不同的深色轿车，不是同一个目标。 |
| current reason | 防止把前车和后车错误合并的禁止连接。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000145.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000179.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM017_000214.png
```

人工需要判断：

- `GM_RM017_N001` 和 `GM_RM017_N003` 是否明确指向两辆不同的深色轿车？
- 时间、位置、运动顺序是否说明它们不是同一个同车指称？
- 白色 SUV 或其他上下文车辆是否把前后两辆深色车分开了？
- 是否只是外观相似，但真实车辆并不一致？
- 当前 `forbidden_edge` 是否应保持？是否需要填写 override CSV？

override CSV 提示：

- 接受当前禁止连接：不需要填写。
- 如果只能弱连接：填 `action=force_weak_connect`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 如果确认同一辆车：填 `action=force_strong_connect`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 如果不确定：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

### GM_RM011_E007

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N003` |
| to_node | `GM_RM011_N006` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| to range | `GM_RM011_N006`, `GM_RM011_FORBIDDEN_CONTEXT_001`, frames `283-292` |
| key frame range | `262-292` |
| rendered frame count in range | 22 |
| visual basis | 后继框落到左边缘竞争车辆上，而中央白车仍然单独可见。 |
| current reason | 禁止 `bs_0061` 到 `bs_0064` 的错误桥接。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000280.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000292.png
```

人工需要判断：

- 后继节点是否从中央白车切换到了左边缘竞争车辆？
- 中央白车在后继帧中是否仍然可见，因此不应该把左边缘车接上？
- 是否有其他车辆插入导致身份串线？
- 当前禁止连接是否应保持为硬禁止？
- 是否需要在诊断渲染中显示 forbidden marker，提醒后续人工不要误连？

override CSV 提示：

- 接受当前禁止连接：不需要填写。
- 如果需要显示禁止连接标记：填 render `show_forbidden_edge_marker`。
- 如果实际只能弱连接：填 `action=force_weak_connect`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 如果不确定：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

### GM_RM011_E008

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N007` |
| to_node | `GM_RM011_N003` |
| current_edge_type | `forbidden_edge` |
| connection_strength | `forbidden` |
| from range | `GM_RM011_N007`, `GM_RM011_FORBIDDEN_CONTEXT_002`, frames `256-261` |
| to range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| key frame range | `256-270` |
| rendered frame count in range | 15 |
| visual basis | 前段是侧窗/条带区域，后段切到左边缘后部碎片或竞争区域。 |
| current reason | 禁止仅凭空间接近或外观相似形成错误桥接。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000256.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000263.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000270.png
```

人工需要判断：

- 前节点是否只是侧窗/条带片段，不能安全连接到 `GM_RM011_N003`？
- 时间、位置、运动方向是否真的连续，还是只是靠得近？
- 是否有其他车辆插入导致身份串线？
- 是否只是框不稳，但车辆指称仍然一致？如果不是，应保持禁止连接。
- 当前 `forbidden_edge` 是否应保持？是否需要填写 override CSV？

override CSV 提示：

- 接受当前禁止连接：不需要填写。
- 如果只能弱连接：填 `action=force_weak_connect`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 如果确认同一辆车：填 `action=force_strong_connect`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 如果不确定：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

## Strong Same-Vehicle Edges：强连接

### GM_RM011_E001

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N001` |
| to_node | `GM_RM011_N002` |
| current_edge_type | `strong_same_vehicle_edge` |
| connection_strength | `strong` |
| from range | `GM_RM011_N001`, `GM_RM011_V001`, frames `13-16` |
| to range | `GM_RM011_N002`, `GM_RM011_V001`, frames `18-35` |
| key frame range | `13-35` |
| rendered frame count in range | 22 |
| visual basis | 同一辆白车的车头和挡风玻璃区域跨短间隔保持连续。 |
| current reason | 这是强局部诊断连接，不是最终 identity merge。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000013.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000024.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000035.png
```

人工需要判断：

- 前后节点是否指向同一辆真实车？
- frames `13-16` 到 `18-35` 之间的时间、位置、运动方向是否连续？
- 短缺帧是否不影响诊断用强连接？
- 是否有其他车辆插入导致身份串线？
- 是否只是框不稳，但车辆指称仍然一致？
- 是否需要填写 override CSV？如果接受当前强连接，通常不需要。

override CSV 提示：

- 接受当前强连接：不需要填写。
- 降级为弱连接：填 `override_type=edge`，`action=downgrade_to_weak`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 标记需要复核：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

### GM_RM011_E002

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N004` |
| to_node | `GM_RM011_N005` |
| current_edge_type | `strong_same_vehicle_edge` |
| connection_strength | `strong` |
| from range | `GM_RM011_N004`, `GM_RM011_V002`, frames `279-281` |
| to range | `GM_RM011_N005`, `GM_RM011_V002`, frames `283-292` |
| key frame range | `279-292` |
| rendered frame count in range | 13 |
| visual basis | 中央白车的车头和挡风玻璃保持连续；左边缘邻车可以分开。 |
| current reason | 带有竞争车辆排除说明的强局部连接。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000279.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000286.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000292.png
```

人工需要判断：

- frames `279-292` 中中央白车是否保持同一个同车指称？
- 左边缘邻车是否足够清楚地与中央白车分开？
- 渲染框是否有从中央车漂移到邻车的情况？
- 是否有其他车辆插入导致身份串线？
- 当前强连接是否应保持，还是降级为弱连接、改为禁止连接、或标记需要复核？

override CSV 提示：

- 接受当前强连接：不需要填写。
- 降级为弱连接：填 `action=downgrade_to_weak`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 仅诊断渲染主框有问题：填 `override_type=render`，`action=select_diagnostic_primary_box`，并使用已有 `source_detection_id`。

## Weak Same-Vehicle Edges：弱连接

### GM_RM011_E003

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N003` |
| to_node | `GM_RM011_N004` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N003`, `GM_RM011_V002`, frames `262-270` |
| to range | `GM_RM011_N004`, `GM_RM011_V002`, frames `279-281` |
| key frame range | `262-281` |
| rendered frame count in range | 12 |
| visual basis | 同一辆白车是合理解释，但可见部位从 rear/side 变到 front/window，且间隔更长。 |
| current reason | 弱诊断连接；不能直接合并 track identity。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000262.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000267.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000281.png
```

人工需要判断：

- 前后节点是否仍指向同一辆真实车？
- rear/side 到 front/window 的可见部位变化是否合理？
- frame `270` 到 `279` 的间隔是否太大，导致不能升级为强连接？
- 是否有其他车辆插入导致身份串线？
- 是车辆指称一致但框不稳，还是实际目标切换？
- 是否需要填写 override CSV？

override CSV 提示：

- 保留弱连接：不需要填写；如需留痕，可填 `action=force_weak_connect`，`edge_strength=weak`。
- 升级强连接：填 `action=upgrade_to_strong`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 标记需要复核：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

### GM_RM011_E004

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N008` |
| to_node | `GM_RM011_N009` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `review_only` |
| from range | `GM_RM011_N008`, `GM_RM011_V003`, frames `135-161` |
| to range | `GM_RM011_N009`, `GM_RM011_V003`, frames `164-166` |
| key frame range | `135-166` |
| rendered frame count in range | 30 |
| visual basis | 右边缘白车可能连续，但后继 crop 太薄。 |
| current reason | review-only edge；可见车辆面积太少。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000135.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000149.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000166.png
```

人工需要判断：

- 右边缘车辆是否有足够可见内容支持同车指称？
- frames `164-166` 的后继框是否太薄，只能作为 `review_only`？
- 是车辆指称仍然一致但框太差，还是已经没有可靠车辆观察？
- 是否应该保持 `review_only`，升级为弱连接，改为禁止连接，或标记坏检测节点？
- 是否需要渲染 marker，防止后续过度信任薄边缘 crop？
- 是否需要填写 override CSV？

override CSV 提示：

- 保持 `review_only`：不需要填写；如需留痕，可填 `action=mark_review_required`，`edge_strength=review_only`。
- 升级为弱连接：填 `action=force_weak_connect`，`edge_strength=weak`，`reason_code=weak_continuity_only`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=edge_contact_thin_crop` 或 `forbidden_competitor_switch`。
- 标记坏检测节点：如果薄 crop 不可用，对 `GM_RM011_N009` 填 node `mark_bad_detection_node`。

### GM_RM011_E005

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N010` |
| to_node | `GM_RM011_N011` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N010`, `GM_RM011_V004`, frames `231-233` |
| to range | `GM_RM011_N011`, `GM_RM011_V004`, frames `236-245` |
| key frame range | `231-245` |
| rendered frame count in range | 13 |
| visual basis | upper side/window 到 front/hood 的部位转换是合理的弱同车解释。 |
| current reason | 弱 part-transition edge。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000231.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000239.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000245.png
```

人工需要判断：

- frames `231-233` 的 upper side/window 区域是否和 frames `236-245` 的 front/hood 区域指向同一辆真实车？
- 时间、位置、运动方向是否支持部位转换，而不是目标切换？
- 是否有其他车辆插入导致身份串线？
- 当前是否应保持弱连接，升级强连接，改为禁止连接，或标记需要复核？
- 是否需要填写 override CSV？

override CSV 提示：

- 保留弱连接：不需要填写。
- 升级强连接：填 `action=upgrade_to_strong`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 标记需要复核：填 `action=mark_review_required`，`edge_strength=review_only`，`reason_code=review_uncertain`。

### GM_RM011_E006

| 字段 | 值 |
| --- | --- |
| scene_id | `GM_RM011` |
| from_node | `GM_RM011_N012` |
| to_node | `GM_RM011_N013` |
| current_edge_type | `weak_same_vehicle_edge` |
| connection_strength | `weak` |
| from range | `GM_RM011_N012`, `GM_RM011_V005`, frames `0-4` |
| to range | `GM_RM011_N013`, `GM_RM011_V005`, frames `8-10` |
| key frame range | `0-10` |
| rendered frame count in range | 8 |
| visual basis | 白色 SUV 的 rear/body 到 upper-window 部位转换是合理的弱同车解释。 |
| current reason | 早期帧弱 part-transition edge。 |

代表渲染帧：

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000000.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000003.png
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames/GM_RM011_000010.png
```

人工需要判断：

- frames `0-4` 的 rear/body 区域是否合理连续到 frames `8-10` 的 upper-window strip？
- 时间、位置、运动方向是否支持弱连接？
- 是否有足够全帧证据排除其他车辆或背景混淆？
- 是否只是框不稳，但车辆指称仍然一致？
- 当前是否应保持弱连接，升级强连接，改为禁止连接，或标记需要复核？

override CSV 提示：

- 保留弱连接：不需要填写。
- 升级强连接：填 `action=upgrade_to_strong`，`edge_strength=strong`，`reason_code=same_vehicle_continuity`。
- 改为禁止连接：填 `action=forbid_connect`，`edge_strength=forbidden`，`reason_code=forbidden_competitor_switch`。
- 仅诊断渲染主框有问题：只有当另一个已有检测更适合作为诊断主框时，才使用 `select_diagnostic_primary_box`。

## 验收完成前检查

在后续任何 apply step 之前，先确认：

- 10 条 edge 都已有人工判断：接受当前、改变强弱、禁止连接、非车辆排除、或需要复核。
- 所有 override row 只使用 `node`、`edge`、`render` 三类 `override_type`。
- override CSV 不包含 bbox 坐标列。
- `select_diagnostic_primary_box` 引用的是 render manifest 中已有的 `source_detection_id`。
- override CSV 通过 dry-run validator。
- 没有生成 final annotation、revised annotation、final boxes、GT boxes、SAR output、detector output、tracker replay output、selector/ranking output。
- 没有提交 outputs、图片、视频、权重、数组、pickle、压缩包。
