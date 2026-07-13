# OTY2 P1 光学完整时间流全局物理车辆身份协议

日期：`2026-07-13`

阶段准入：`P1_OPTICAL_GLOBAL_IDENTITY_ALLOWED`

## 1. 科学目标

P1 只在三个场景各自完整的 368 帧光学时间流上，重建可审计的物理车辆生命周期。研究对象不是 detector row、tracker ID 或 crop，而是同一辆物理车辆从进入、可见、遮挡/漏检、恢复到退出的完整状态轨迹。

P1-A 负责资产与问题审计及求解设计；P1-B 才允许实现光学身份图和离线求解。本协议不声称已经完成车辆线程重建。

## 2. 物理车辆身份定义

一个 `physical_vehicle_id` 表示一个在本场景时间范围内不可分裂、不可与另一辆车合并的物理车辆生命周期。以下对象均不能直接等同于该身份：

- detector 的 `det_id`；
- ByteTrack/BoT-SORT 的 `track_id`；
- 某个 crop 或 512 维 embedding；
- Working Graph / WGV1.x 的 thread ID；
- 单个框的类别、置信度或颜色标签。

tracker ID 只提供局部短轨迹候选；WGV1.x 只提供可复核的历史关系证据；物理身份必须由完整过去与未来帧、同帧排他关系、进入/退出解释和多源证据共同决定。

## 3. 生命周期状态

每个车辆线程按帧表达以下状态：

| state | 语义 | 可观测证据 |
| --- | --- | --- |
| `outside_before_entry` | 尚未进入视场 | 之前持续不可见，且没有可连接观察 |
| `entering` | 从边界或遮挡体后进入 | 边缘截断、尺度/可见面积逐步增加 |
| `active_visible` | 主体可见 | 有一个主体观察；允许同车局部重复框待归一化 |
| `partially_occluded` | 部分遮挡 | 车体仍可辨认，但框可能只覆盖局部 |
| `fully_occluded_or_missed` | 完全遮挡或 detector 漏检 | 车辆可由前后帧支持，但当前无可靠框 |
| `recovered` | 遮挡/漏检后恢复 | 后续观察与前序生命周期全局一致 |
| `exiting` | 正在离开视场 | 边缘截断、可见面积下降且运动指向视场外 |
| `outside_after_exit` | 已退出 | 之后持续不可见；若再次出现必须重新审查是否为新车 |

`fully_occluded_or_missed` 是显式状态，不得用虚构 bbox 填补。

## 4. 硬约束与软证据

### 4.1 仅允许的硬约束

1. 同一 detection observation 只能分配给一个物理车辆。
2. 同一物理车辆同一帧最多有一个主体 observation；同车重复/局部框先归入 observation group，不成为第二个主体。
3. 边必须按时间前进。
4. 物理上不可能的瞬时空间跳跃不得连接。
5. 同帧明确可见的不同车辆不得合并。
6. 人工确认的 `different_vehicle` / `forbidden_merge` 关系必须作为禁止边。
7. `non_vehicle` observation 不得进入车辆线程。

除这些不可违反条件外，不增加按中心距离、面积、颜色、外观、轨迹长度、边界接触或多车数量串联执行的 Gate 树。

### 4.2 统一软证据

候选边的代价统一由以下证据组成，并保留每一项原始值和方向：

- 时间间隔与漏检长度；
- 运动方向、速度和加速度连续性；
- 颜色稳定性；
- ResNet18 baseline 外观相似度；
- 车体轮廓、长宽比和可见部位；
- 尺度变化趋势；
- 姿态/车头车尾变化连续性；
- 边界进入和退出解释；
- 遮挡体及同帧竞争车辆关系；
- 已确认的 same/different/forbidden 关系。

颜色和 appearance 可以支持或反对一条边，但不能单独决定身份。现有 ResNet18 是 ImageNet baseline，不是车辆 ReID；截断、背景占比、重复裁剪和框主体切换会污染相似度。

## 5. P1-B 全局图对象

### 5.1 Detection observation node

最小字段：

```text
scene, frame_id, observation_id, source_detection_ids,
source_detector, bbox_xyxy, confidence, class_name,
observation_group_id, active_for_tracking,
appearance_embedding_ref, color_feature_ref,
border_contact, truncation_state, optical_path
```

同帧 YOLO11l/YOLO26l 重叠框必须保留来源，不得用无 provenance 的 NMS 结果覆盖原表。

### 5.2 Short tracklet

短轨迹只表示局部高可信连续关系。它可以来自现有 raw YOLO26l BoT-SORT/ByteTrack replay、历史 normalized-active tracker 片段或连续 observation 的局部重组。任何 tracklet 都允许被切分，不要求覆盖完整车辆生命周期。

### 5.3 Candidate edge

候选边连接两个时间有序的 short tracklet，并允许：

- `continue_visible`；
- `occlusion_gap_recovery`；
- `detector_miss_recovery`；
- `entry` / `exit`；
- `same_vehicle_candidate`；
- `temporal_context_not_identity`。

每条边必须输出证据分解、硬约束检查结果、总代价和最终采用/拒绝原因。

### 5.4 Global vehicle thread

线程是若干 observation/tracklet 和生命周期状态的有序路径。线程必须有出生与终止解释，可以包含无框状态，但不能跨越 forbidden edge 或同帧排他冲突。

## 6. 检测源策略

P1-B 使用“主干加受控补充”，而不是选择一个 detector 后丢弃其他资产：

1. 以 `YOLO26l normalized-active observation pool` 作为计算主干。理由是三场景完整、GM_RM011 可见车身缺口和 GM_RM019 低置信压力改善明显，并且已有同源 raw MOT、逐检测 embedding、linkage 和短轨迹聚合资产。
2. YOLO11l normalized 表作为补充与反例源：只在 YOLO26l 漏检/明显局部欠拟合，或 YOLO11l 提供非重复的可见车辆主体时加入候选。
3. 多源合并必须做同帧 observation grouping，保留 detector provenance、原始置信度、bbox 和归一化动作。
4. YOLO26n 只有 GM_RM011/017 的诊断窗口表，且包含 `boat/mouse/surfboard/fire hydrant/person/potted plant` 等非车辆类别，只能作为 window-only sensitivity evidence，不得作为完整时间流主干。

该策略不是宣布 YOLO26l 在所有场景“最好”，也不是覆盖历史 baseline。它只定义 P1-B 的可审计 observation 构造优先级。

## 7. 推荐求解方式

推荐在 short-tracklet DAG 上建立带出生、退出、遮挡/漏检 gap 和恢复边的整数线性规划（ILP）约束路径覆盖：

```text
minimize:
  selected edge costs
  + birth/exit costs
  + unresolved observation costs
  + identity fragmentation costs

subject to:
  one observation -> at most one vehicle thread
  one vehicle -> at most one primary observation per frame
  flow conservation on selected tracklets
  temporal order
  forbidden edges = 0
  confirmed same-vehicle local edges enforced when non-conflicting
```

选择 ILP 的原因：每场景只有 368 帧，tracklet 数量为几十量级；精确求解规模可控，且比逐层 Gate 更容易表达同帧排他、出生/退出、遮挡恢复和人工禁止边。最小费用流可作为无高阶冲突时的简化实现；纯图聚类难以自然表达时间顺序、生命周期和同帧排他；多假设跟踪可作为候选生成，但不作为最终审计接口。

## 8. P1-B / P1-C / P1-D 边界

- `P1-B`：构造 multi-source observation/tracklet graph，实现并运行光学-only 全局求解，输出逐边证据与 unresolved 状态。
- `P1-C`：对高代价、冲突、同色替换、遮挡恢复和生命周期边界做完整视频人工复核；只修改光学身份图约束与状态。
- `P1-D`：冻结经审阅的光学车辆线程与版本化 manifest，形成后续 P2 可消费的光学身份先验；仍不生成 SAR 框。

## 9. GT 与 SAR 禁用边界

P1-A 至 P1-D 均不得使用：

- SAR 灰度、伪彩、SAR GT 或 SAR morphology 判断光学同车关系；
- 光学—SAR 映射残差修正光学身份；
- selector/ranking/final box 结果反向选择光学线程；
- review/final/oracle 字段作为运行时身份特征。

## 10. P1-B 最小新增代码

1. multi-source observation pool builder（保留原始来源和 normalization provenance）；
2. tracklet/observation graph schema 与 validator；
3. 软证据特征提取与逐边 cost breakdown；
4. forbidden/same/unresolved 人工证据加载器；
5. ILP path-cover solver；
6. 生命周期状态导出器；
7. 全 368 帧 review renderer 与 conflict queue；
8. deterministic replay、schema 和 constraint tests。

不需要重新训练 detector 或 appearance model，也不需要在 P1-B 开始前重新调 ByteTrack/BoT-SORT。

## 11. 停止条件

出现以下任一情况时，P1-B 不得宣称完成：

- 观察节点无法回溯到原始光学帧和 detection row；
- forbidden edge 被求解结果违反；
- 同帧两个不同车辆被合并为一个主体；
- 结果依赖 SAR/GT/selector 信息；
- 大量身份只能靠新增硬 Gate 才能成立；
- 高风险同色替换、遮挡恢复或退出/再进入边界没有进入人工 conflict queue；
- 结果只输出 vehicle ID，不输出逐边证据、状态和未决项。

## 12. P1-A 结论

现有完整光学帧、两套完整 detector 表、归一化表、短轨迹、外观 embedding 和历史人工/多模态光学结论，足以实现受限 P1-B。它们不足以直接把当前 tracker/WGV thread 当作物理车辆真值。

阶段状态：

`P1A_GLOBAL_IDENTITY_DESIGN_READY`
