# OTY2 P1-A 光学资产与全局物理车辆身份设计审计

日期：`2026-07-13`

工作树：`D:\profile\research\optical-sar-visual-diagnosis-data-foundation`

起始 HEAD：`10ba95418f56b11b1bea311bf7c82004fd2d426d`

## 1. 研究结论

三个场景的完整光学资产已足以进入受限 P1-B，构建并求解“完整时间流上的离线全局物理车辆身份图”。资产包括完整 368 帧光学流、YOLO11l/YOLO26l 完整检测表、同帧归一化表、两类 tracker 的局部短轨迹、逐检测 ResNet18 embedding、tracker linkage、短轨迹聚合，以及已经审阅的 same/different/forbidden/non-vehicle 关系。

它们不足以把现有 tracker ID、OTY1 tracklet 或 WGV1.x thread 直接宣布为物理车辆真值。当前仍存在同色车辆替换、遮挡驱动主体切换、可见但无框、相似灰车先后进入和非车辆稳定短轨等问题；这些正是 P1-B 全局图需要表达和求解的对象。

P1-A 最终状态：

`P1A_GLOBAL_IDENTITY_DESIGN_READY`

P1-B 准入：`yes, optical-only and bounded`。

本结论不提升 P0 总状态；P0 仍为 `P0_DATA_FOUNDATION_PARTIALLY_READY`，而独立决策文档已授权 `P1_OPTICAL_GLOBAL_IDENTITY_ALLOWED`。

## 2. 是否直接审阅了完整光学时间流

是。审阅不是只看 CSV、231/442 行稀疏样本或旧关键窗口。

对每个场景均生成并直接检查：

- 全部 368 帧 raw contact sheet；
- 全部 368 帧 YOLO11l/YOLO26l/BoT-SORT/ByteTrack overlay contact sheet；
- 多车、遮挡、漏检、进入/退出关键窗口的连续逐帧条带。

临时审阅材料位于被 `.gitignore` 控制的：

`outputs/oty2_p1a_visual_audit_20260713/`

该目录不提交。三场景 `_C.MP4` 均为 368 帧、800×600、24 fps；抽查 frame 0/100/200/367，解码像素与 PNG 完全一致。

## 3. 场景级物理车辆生命周期

| scene | 当前完整流视觉估计 | 关键说明 |
| --- | ---: | --- |
| `GM_RM011` | 约 `8-10` 个 | 多个近场白车生命周期、同色替换、遮挡主体切换和 231-292 多车竞争使精确计数仍需 P1-B/P1-C 冻结。 |
| `GM_RM017` | 约 `4` 个 | 白色箱式货车、领先深色轿车、白色 SUV、尾随深色轿车；另有蓝色手推车/前景结构非车辆误检。 |
| `GM_RM019` | 约 `4` 个 | 早期黑色轿车、白色 MPV、99-143 银色 MPV、149-183 灰色 SUV；后两辆颜色相近但为独立生命周期。 |

GM_RM017 和 GM_RM019 的计数不能由 tracker 数量或旧摘要直接代替。完整帧流显示 GM_RM017 的四辆车在 162 附近可同时出现；GM_RM019 的两辆灰车之间是“前车完整退出、后车重新进入”，不能合并。

## 4. 原始光学资产

| scene | frame path | count/range | size | direct video |
| --- | --- | --- | --- | --- |
| `GM_RM011` | `D:\profile\research\data\GM_RM011\GM_RM011_frames` | 368 / 0..367 | 800×600 | `D:\profile\research\data\mp4\GM_RM011_C.MP4` |
| `GM_RM017` | `D:\profile\research\data\GM_RM017\GM_RM017_frames` | 368 / 0..367 | 800×600 | `D:\profile\research\data\mp4\GM_RM017_C.MP4` |
| `GM_RM019` | `D:\profile\research\data\GM_RM019\GM_RM019_frames` | 368 / 0..367 | 800×600 | `D:\profile\research\data\mp4\GM_RM019_C.MP4` |

原始图片和视频均只读，未复制、修改或重新编码。

## 5. 完整检测源对照

定义：低置信为 `confidence < 0.50`；边界截断 proxy 为 bbox 距 800×600 图像左右边界不超过 16 px 或上下边界不超过 12 px；高重叠为同帧 pair IoU≥0.50，duplicate-like 子集为 IoU≥0.70。这些只是资产描述，不是身份 Gate。

| scene | source | rows | 有框帧 | 空帧 | 单框帧 | 多框帧 | low<0.50 | border rows | IoU≥0.70 pairs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GM_RM011 | YOLO11l | 422 | 233 | 135 | 86 | 147 | 112 | 412 | 9 |
| GM_RM011 | YOLO26l | 413 | 243 | 125 | 110 | 133 | 103 | 413 | 35 |
| GM_RM017 | YOLO11l | 215 | 100 | 268 | 31 | 69 | 19 | 99 | 3 |
| GM_RM017 | YOLO26l | 215 | 104 | 264 | 42 | 62 | 20 | 104 | 4 |
| GM_RM019 | YOLO11l | 334 | 193 | 175 | 93 | 100 | 158 | 175 | 2 |
| GM_RM019 | YOLO26l | 288 | 193 | 175 | 121 | 72 | 85 | 169 | 18 |

类别分布：

- GM_RM011 YOLO11l=`car 413/truck 9`，YOLO26l=`car 392/truck 21`；
- GM_RM017 YOLO11l=`car 153/truck 58/bus 4`，YOLO26l=`car 159/truck 55/bus 1`；
- GM_RM019 YOLO11l=`car 327/truck 1/bus 6`，YOLO26l=`car 285/truck 2/bus 1`。

完整表都经过 vehicle-class 过滤，因此 `non_vehicle_class_rows=0` 不等于视觉上没有非车辆框。例如 GM_RM017 蓝色手推车和 GM_RM019 259-261 路牌/展示物仍可被 vehicle 类别框住，必须由完整帧视觉和证据账本排除。

YOLO26n 不是完整检测源：

- GM_RM011 只有 56 个窗口帧、93 rows，包含 20 个非车辆类别 rows（boat/mouse/surfboard/motorcycle）；
- GM_RM017 只有 79 个窗口帧、223 rows，包含 23 个非车辆类别 rows（fire hydrant/person/potted plant）。

因此 YOLO26n 仅保留为窗口敏感性证据。

## 6. 归一化表可用性

YOLO11l 和 YOLO26l 均存在完整的同帧 observation normalization probe。表中保留原 detection row，并增加：

`observation_group_id, active_for_tracking, normalization_action, primary_detection_id, suppression_reason, grouping_diagnosis_label, state_tags, safe_for_identity_claim, why_not_identity_truth`

| scene | source | total | active | inactive duplicate-like |
| --- | --- | ---: | ---: | ---: |
| GM_RM011 | YOLO11l | 422 | 413 | 9 |
| GM_RM011 | YOLO26l | 413 | 383 | 30 |
| GM_RM017 | YOLO11l | 215 | 215 | 0 |
| GM_RM017 | YOLO26l | 215 | 211 | 4 |
| GM_RM019 | YOLO11l | 334 | 330 | 4 |
| GM_RM019 | YOLO26l | 288 | 272 | 16 |

这些字段可直接复用于 P1-B observation pool，但其语义仅是同帧几何归一化；所有行都明确 `safe_for_identity_claim=false`。GM_RM011 YOLO26l 的 30 个 inactive duplicate-like rows 说明它改善可见车身的同时也增加重复/类别冲突压力。

## 7. 推荐检测源策略

推荐 `YOLO26l normalized-active` 作为 P1-B 的计算主干，YOLO11l normalized 表作为受控补充和反例源，并构建保留 provenance 的同帧 observation union。

理由：

1. YOLO26l 三场景完整，并有同源 raw MOT、逐检测 embedding、linkage 和 tracklet embedding 资产。
2. GM_RM011 有框帧比 YOLO11l 多 10 帧，并能在 237-270 可见白车缺口中提供更完整车身候选。
3. GM_RM019 在有框帧数相同的情况下，将低置信 rows 从 158 降到 85，多框帧从 100 降到 72。
4. GM_RM011 的 duplicate-like 压力更高，因此必须使用 normalization provenance，不能直接把 raw YOLO26l 当真值。
5. YOLO11l 在部分帧保留不同的可见部位和候选，适合作为漏框补充；它不应被删除。

这不是“YOLO26l 全面优于 YOLO11l”的结论，也不覆盖旧 detector-swap probe 的阶段性 `neutral` 结论。它只规定新 P1-B 图构造的主干与补充角色。

## 8. 现有 tracker 的作用和局限

### 8.1 raw YOLO26l replay 摘要

| scene | tracker | tracks | tracked/unmatched | length min/median/max |
| --- | --- | ---: | --- | --- |
| GM_RM011 | BoT-SORT | 18 | 345/68 | 1/17.5/43 |
| GM_RM011 | ByteTrack | 23 | 324/89 | 1/12/40 |
| GM_RM017 | BoT-SORT | 4 | 191/24 | 41/48.5/53 |
| GM_RM017 | ByteTrack | 4 | 187/28 | 40/48/51 |
| GM_RM019 | BoT-SORT | 14 | 200/88 | 1/11/43 |
| GM_RM019 | ByteTrack | 15 | 194/94 | 1/6/42 |

这些 replay 使用 raw YOLO26l detections、空白图像，`with_reid=false`。外观没有进入 tracker。它们适合复用为 short-tracklet seed、局部连续边和跨 tracker 稳定性对照；不适合复用为物理车辆 ID。

GM_RM011 的主要问题是同一物理车跨多个短轨迹、同色车被错误桥接、重复框形成并行轨迹和 231-292 多车替换。GM_RM017 的四条长轨迹恰好提供局部车辆片段，但最高置信 stream 仍会在四辆车之间切换。GM_RM019 的四辆物理车被 14/15 个 track IDs 分裂，说明 tracker fragmentation 很强。

历史报告中的 GM_RM011 最佳诊断版本为 YOLO11l `BoT-SORT normalized-active`；这与本表的 raw YOLO26l replay 不是同一个资产，不得混写。

## 9. 外观和颜色能否支撑跨片段同车判断

可以作为软证据，不足以单独决定。

当前逐检测 embedding：

- backend=`torchvision_resnet18_imagenet_feature_baseline`；
- 512 维、L2 normalized；
- GM_RM011/017/019 分别 413/215/288 rows；
- crop 和 embedding failure 均为 0；
- tracklet aggregation 分别 33/4/16 segments。

GM_RM017 的最小 segment 内部 cosine 低至 `0.476059`，GM_RM019 为 `0.574272`。这说明局部框、背景、截断和姿态足以显著改变 ImageNet 特征。颜色同样不能解决 GM_RM011 白车替换或 GM_RM019 两辆灰车替换。

正确用法是把颜色、appearance、形状、尺度、运动、进入/退出和同帧竞争统一放入边代价，并输出每项证据；不得把颜色/appearance 变成硬 Gate。

## 10. 主要身份失败类型

1. `same_color_vehicle_replacement`：GM_RM011 0-35、231-292；GM_RM019 99-183。
2. `occlusion_driven_subject_switch`：GM_RM011 135-166。
3. `visible_but_unboxed`：GM_RM011 237-270，包含 detector miss、旧 graph omission 和 render skip。
4. `over_merged_node`：YOLO26l identity-safe diagnosis 的五个关键窗口。
5. `same_vehicle_fragment_split`：GM_RM019 149-183，旧 OTY1 tracklet_0039/0045。
6. `similar_vehicle_false_merge`：GM_RM017 leading/trailing dark sedan。
7. `non_vehicle_false_track`：GM_RM017 bs_0002/蓝色手推车，GM_RM019 259-261 展示物。
8. `edge_truncation_and_partial_full_transition`：近场车辆和进入/退出边界。
9. `historical_thread_evidence_conflict`：GM_RM011 WGV1.4b 231-288 search hint 与当前完整流车辆替换证据冲突。

## 11. 已冻结的关键身份关系

详细表见 `manifests/oty2/oty2_p1a_known_optical_identity_evidence.csv`。关键结论包括：

- GM_RM011 0-18 局部同车；31-35 主体与早期近场白车不同。
- GM_RM011 135-166 存在白车/深色车遮挡驱动主体切换；151-166 白车局部同车。
- GM_RM011 frame 237 右车与 frame 245 左车不同；245-262 局部同车。
- GM_RM011 262-288 保留弱/未决；289-292 左白 SUV 与此前右车禁止合并。
- GM_RM017 四辆车分别形成局部连续生命周期；leading/trailing dark sedans 必须 forbidden merge。
- GM_RM019 99-143 银色 MPV 与 149-183 灰色 SUV 不同；149-183 内的 OTY1 0039/0045 是正向 fragment repair 样例。

## 12. 多车竞争和生命周期如何表达

P1-B 应将每个物理车辆建模为一条带状态的路径：

`outside_before_entry -> entering -> active_visible -> partially_occluded/fully_occluded_or_missed -> recovered -> exiting -> outside_after_exit`

同帧不同车辆由排他约束共同分配，不采用“先按分数选一个主框、再局部修补”的顺序。可见但无框的帧使用 `fully_occluded_or_missed` 或明确的 `visible_but_unboxed` audit state，不生成虚构坐标。

## 13. 推荐全局求解方法

推荐 short-tracklet DAG 上的 ILP 约束路径覆盖：

- birth/exit edge 表达准入和准出；
- gap/recovery edge 表达遮挡或漏检恢复；
- 一 observation 至多属于一个线程；
- 一车辆同帧至多一个主体 observation；
- confirmed forbidden edge 固定为 0；
- 颜色、appearance、运动、尺度、姿态、边界和遮挡统一进入软代价；
- 输出每条采用/拒绝边的 cost breakdown。

每场景 368 帧、几十个短轨迹，精确 ILP 的规模可控。最小费用流可做简化 baseline，但遇到同帧排他和人工禁止边时 ILP 表达更直接。纯图聚类缺少生命周期和时间顺序；多假设跟踪适合生成候选，不适合作为唯一审计结果。

## 14. P1-B 最小新增代码

1. multi-source observation pool builder；
2. observation/tracklet/edge schema 和 validator；
3. soft evidence feature/cost builder；
4. known evidence/forbidden edge loader；
5. ILP path-cover solver；
6. lifecycle state exporter；
7. full-stream renderer 与 conflict queue；
8. deterministic replay 和 constraint tests。

无需重新训练 detector 或 ResNet18；无需在开始 P1-B 前再次调 ByteTrack/BoT-SORT。

## 15. 仍无法从现有光学数据唯一判断的问题

- GM_RM011 部分同色白车在长遮挡/长 gap 后是否同一车辆，特别是 262-288 冲突区；
- 严重近场截断只剩窗框/车身局部时，车体完整轮廓和精确姿态；
- 完全不可见期间车辆是否在视场外绕行后重新进入；
- 现有 ImageNet embedding 对相同车型、相似颜色车辆的可分性；
- 没有稳定 detector box 的可见帧应选择哪一个既存 detection 作为主体；
- 精确车辆数量和线程边界最终仍需 P1-B 求解与 P1-C 高风险 conflict review 冻结。

这些未决项不阻断 P1-B 实现，因为 solver 和 schema 必须允许 `unresolved`，而不是把所有关系强行二值化。

## 16. 本轮明确没有运行的内容

本轮没有：

- 使用 SAR 灰度、伪彩或 SAR GT 判断光学身份；
- 修改光学—SAR 映射或硬同步关系；
- 重新运行或调参 detector、ByteTrack、BoT-SORT；
- 训练 detector、appearance 或 ReID 模型；
- 运行最终全局身份 solver；
- 更新 SAR Working Graph；
- 生成 SAR candidate、Gate、selector、ranking 或自动标注；
- 生成 final/revised/GT boxes；
- 修改原始图片或视频；
- 触碰 stash 或其他分支；
- 提交临时 contact sheet、图片、视频、权重、NPZ 或 outputs。

## 17. 正式产物

- `docs/OTY2_P1_OPTICAL_GLOBAL_IDENTITY_PROTOCOL.md`
- `manifests/oty2/oty2_p1a_optical_asset_inventory.csv`
- `manifests/oty2/oty2_p1a_known_optical_identity_evidence.csv`
- `manifests/oty2/oty2_p1a_scene_identity_problem_inventory.csv`
- `reports/oty2/oty2_p1a_optical_asset_and_global_identity_design_audit_20260713.md`

阶段结论：现有资产足以进入 P1-B 设计实现，但当前结果仍是“设计就绪”，不是“物理车辆线程重建完成”。
