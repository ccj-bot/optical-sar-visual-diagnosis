# OTY2-RSA2-O1 证据锚定的车辆响应状态与关系语义合同

日期：2026-07-18

阶段：OTY2-RSA2-O1 Evidence-Anchored Vehicle Response State and Relation Semantics Freeze

状态：语义冻结；不授权算法实现。

## 1. 文档性质与边界

本文是 OTY2 当前研究纠偏口径下的状态、实体、关系和证据合同。它回答的是：为了不丢失物理车辆、单帧稀疏 SAR 观察、多帧互补、完整生命周期、多车排他、背景持续、GT 缺口和身份冲突，后续研究记录至少必须能够表达什么。

本文只冻结可保存的研究语义，不定义自动求解方式。本文不产生检测器、阈值、候选、候选库、评分、排序、selector、winner、模板、Mask、传播、自动身份修正、自动 GT 修正或最终标注，也不提出下一阶段算法方案。

所有状态都必须能够回到直接图像、人工清单、GT 质量记录或明确的关系证据。不能把名称、统计量、裁剪、插值或几何构造本身升级成物理结论。

## 2. 与错误复盘及 RSA2-O0 的关系

本文的上位纠偏依据依次是：

1. docs/reviews/OTY2_SAR_ROUTE_ERRORS_AND_OMISSIONS_DEEP_REVIEW_20260718.md；
2. docs/OTY2_RESEARCH_CONCLUSION_STATUS_REGISTER_20260718.md；
3. reports/oty2/oty2_rsa2_o0_open_book_vehicle_level_multitimescale_mechanism_review_20260718.md；
4. 本文及配套核心视觉证据指南。

深度复盘定义必须纠正的路线错误；结论状态索引标明旧结论的当前状态；RSA2-O0 保存开卷式车辆级观察；本文对 O0 的观察术语进行反向核验并冻结可持久化语义。

O0 原报告继续作为历史审阅记录保留，不在本轮覆盖。O1 对下列表述进行约束性降级：

- P1/P2/P3 只允许作为历史人工中性观察索引，不能表示跨帧固定物理部件。
- GM19 27/31 与 77/81/88 只能建立有边界的同车上下文、可能互补或可能替代显现关系，不能证明同一响应部件持续。
- 车辆坐标下的相似性只能支持几何相容观察，不能证明刚性车辆响应模板。
- RSA1-A0 只作为预构造固定几何、人工屏障依赖和跨车不复现的负面方法论证据，不能作为对象传播证据。

## 3. PhysicalVehicle：物理车辆

PhysicalVehicle 是本合同中唯一默认允许跨帧持续的车辆实体。持续的是现实中的同一辆车，不是 GT 框、tracker ID、SAR 像素、局部亮带或中性部件标签。

最低字段：

| 字段 | 语义要求 |
| --- | --- |
| vehicle_id | 场景内物理车辆的研究标识，不等于任一局部 tracker/GT link |
| scene | 所属场景 |
| identity_source | 直接光学观察、人工多模态判断、tracker、GT link 等来源及其边界 |
| optical_lifecycle | 完整光学生命线范围 |
| entry_state | 进入、已在场、进入未知 |
| exit_state | 未退出、接近退出、已退出、退出未知 |
| visibility_state | 完整可见、部分可见、遮挡、检测缺失或未知 |
| vehicle_class_or_shape | 只记录可支持的车型/外观描述 |
| metric_length_interval | 基于有效显示网格和可靠几何参考的长度区间 |
| metric_width_interval | 基于有效显示网格和可靠几何参考的宽度区间 |
| heading_interval | 朝向区间及其证据来源 |
| ordering_relations | 与其他车辆的前后、进入、退出和主体竞争关系 |
| identity_conflicts | 同 ID 双框、主体切换、几何跳变等冲突 |
| evidence_sources | 光学、SAR、GT 质量记录和规范图路径 |

硬性语义：

- SAR 某帧暂时无明显局部响应时，PhysicalVehicle 仍可由完整光学生命线支持为存在。
- 一个 GT 框只是 GTGeometryReference，不等于 PhysicalVehicle 本体。
- tracker ID 只能进入 identity_source，不能单独把 identity_conflicts 置空。
- PhysicalVehicle 不拥有一个预先假定的固定 SAR 部件集合。

## 4. OpticalVehicleObservation：单帧光学车辆观察

OpticalVehicleObservation 是某一光学帧中的观察记录。它必须区分直接可见事实、检测器输出、tracker 输出和人工/多模态身份判断。

最低字段：

| 字段 | 语义要求 |
| --- | --- |
| optical_observation_id | 单帧观察主键 |
| scene / optical_frame | 场景与光学帧 |
| candidate_vehicle_id | 候选物理车辆上下文；允许未知或冲突 |
| direct_visibility | 直接可见、部分可见、遮挡、不可见 |
| detector_box | 若存在，单独保存，不等同于车辆真值 |
| tracker_id | 若存在，单独保存，不等同于完整身份 |
| identity_assessment | 人工或多模态身份判断及证据 |
| entry_exit_observation | 当前帧对进入/退出状态的贡献 |
| ordering_observation | 与同场景其他车辆的前后或主体竞争关系 |
| evidence_path | 原始光学上下文 |

OpticalVehicleObservation 可以支持同车身份、进入、退出、前后顺序、可见性和多车排他，但不能直接给出 SAR 响应 Mask、某个 SAR 亮点的唯一所有权、GT 缺口中的精确 SAR 中心或完整 SAR 响应边界。

## 5. SARFrameObservation：单帧完整 SAR 上下文

SARFrameObservation 表示一帧 SAR 的完整场景上下文，不是某辆车的独立裁剪。

最低字段：

| 字段 | 语义要求 |
| --- | --- |
| sar_frame_observation_id | 单帧主键 |
| scene / sar_frame | 场景与 SAR 帧 |
| mapped_optical_time_or_frame | 对应光学时间或帧及同步来源 |
| physical_vehicles_in_context | 当前完整车辆集合，允许含退出或身份冲突状态 |
| background_structures_in_context | 当前已知背景结构集合 |
| gt_references | 本帧所有 GTGeometryReference 及质量状态 |
| gt_conflicts | duplicate、conflicting、absent 等 |
| multivehicle_state | 单车、多车、主体竞争或未知 |
| raw_context_path | 原始 SAR 上下文 |
| evidence_paths | 规范图和辅助图路径 |

任何车辆局部裁剪都不能替代 SARFrameObservation。GM19 SAR 27/31 的归属解释必须保留 PV001、PV002、退出状态、同帧双框与背景结构，而不能把两辆车分别裁开后独立解释。

## 6. SARLocalResponseInstance：单帧局部 SAR 响应实例

SARLocalResponseInstance 是某一 SAR 帧中人工直接观察到的局部响应实例。它只属于当前帧，不自动具有跨帧身份。

最低字段：

| 字段 | 语义要求 |
| --- | --- |
| instance_id | 帧内唯一实例 ID，例如 GM17_PV002_F330_R01 |
| scene / sar_frame | 场景与单帧 |
| candidate_vehicle_id | 候选车辆上下文；允许未知或多重 |
| direct_visual_description | 只描述可见形态、强弱和位置 |
| pixel_center_or_extent | 像素中心或范围；允许区间 |
| metric_extent | 使用 0.03 m/px 换算的显示网格量级；不等于实体尺寸 |
| vehicle_relative_region | GT 内、框边、框外邻域或未知 |
| raw_context_path | 原始 SAR 上下文 |
| gt_overlay_path | 若存在，明确 GT 质量 |
| observation_status | 可见、弱、间歇、无明显主带或未知 |
| background_mixing | 无明显混合、可能混合、确认背景或未知 |
| evidence_layer | DIRECT_OBSERVATION、RELATION_INFERENCE 或 UNKNOWN |

强弱只能用于描述，不能单独决定归属。实例可以位于 GT 框内、框边或框外邻域，可以与背景混合，也可以无法唯一归属。

禁止为实例写入 same_part=true、continued_part=true 或 tracked_scatterer=true。跨帧只建立 CrossFrameRelation。

## 7. SceneBackgroundStructure：场景背景结构

SceneBackgroundStructure 是独立于车辆的正式场景实体，不再用 background_risk=true 这一空泛布尔量代替。

允许的最低类型：

- vertical_line；
- fan_arc；
- diagonal_line；
- persistent_hotspot；
- unknown_static_structure。

最低字段：

| 字段 | 语义要求 |
| --- | --- |
| background_structure_id | 场景背景实体主键，例如 GM19_BG01 |
| scene | 所属场景 |
| structure_type | 竖线、圆弧、斜线、持续热点或未知静态结构 |
| first_observed_frame / last_observed_frame | 观察范围，不要求自动追踪 |
| scene_coordinate_region | 场景坐标范围 |
| persistence_after_vehicle_exit | 车辆退出后是否仍可直接观察 |
| vehicles_whose_gt_it_enters | 曾进入或接触哪些车辆 GT 邻域 |
| evidence_path | 原始上下文和规范图 |
| exclusion_status | 背景、背景或混合、未决 |

GM19 的中央竖线、扇形圆弧和近底部热点群跨车辆进入、重叠与退出持续；GM17 的斜线/弧线结构跨 PV002、PV003、PV004 邻域出现。这些结构必须有自己的场景身份，不能依赖人工 barrier 才获得语义。

## 8. GTGeometryReference：GT 几何参考

GTGeometryReference 是研究期几何参考，不是车辆本体、可见响应 Mask、像素所有权或部署输入。

最低质量状态：

| 状态 | 含义 |
| --- | --- |
| usable/high | 可用于研究期几何和量级解释 |
| diagnostic_only | 只用于暴露问题，不进入可靠结构结论 |
| duplicate | 同 ID 同帧存在多个框 |
| conflicting | 身份、位置或几何与其他证据冲突 |
| absent | 无直接 SAR GT |
| interpolated_review_crop_only | 仅为观察而生成的插值/最近锚点裁剪，不是 GT，不是 SAR 响应证据 |

GTGeometryReference 必须保存中心、长宽、方向、质量、来源和冲突。GT 框存在只能支持 sar_geometry_known；不能自动支持 sar_local_response_observed、sar_response_attribution_supported 或 sar_response_boundary_known。

## 9. CrossFrameRelation：跨帧关系

CrossFrameRelation 连接两个帧内实例或一个实例与一个场景实体。它表达有边界的关系，不表达固定物理部件身份。

允许的关系类型：

- same_physical_vehicle_context；
- vehicle_coordinate_compatible；
- metric_extent_compatible；
- metric_scale_compatible（历史表达；新记录优先使用 metric_extent_compatible）；
- position_compatible；
- possibly_complementary；
- possibly_alternative_manifestation；
- appearance_order_compatible；
- lifecycle_compatible；
- background_persistence_conflict；
- different_vehicle_exclusivity；
- vehicle_assignment_conflict；
- identity_geometry_conflict；
- insufficient_direct_gt；
- unresolved / cannot_determine。

每条关系最低字段：

| 字段 | 语义要求 |
| --- | --- |
| relation_id | 唯一主键 |
| source_instance_id / target_instance_id | 两端实体或实例 |
| relation_type | 上述受控词表 |
| time_scope | 相邻帧、短窗、中窗或完整生命周期 |
| direct_evidence | 可直接看到的证据 |
| inference_basis | 身份、尺度、顺序、生命周期等推断依据 |
| counterevidence | 不支持更强结论的反证 |
| evidence_layer | 通常为 RELATION_INFERENCE；不能伪装成直接观察 |
| applicability_boundary | 适用车辆、帧和场景 |
| uncertainty_state | 未知或冲突状态 |
| evidence_path | 对应规范图和原图 |

possibly_complementary 只表示：在同一物理车辆上下文中，不同帧提供不同且可能互补的局部信息。它不表示这些实例是同一物理散射部件，也不表示它们的并集是完整车辆。

## 10. MultiVehicleExclusivityRelation：多车排他关系

MultiVehicleExclusivityRelation 是正式关系，不是风险标签。最低需要表达：

- 同帧有哪些 PhysicalVehicle；
- 各车辆的完整光学身份、前后顺序、进入和退出状态；
- 哪些 SARLocalResponseInstance 存在双重解释；
- 哪个 GT link 发生 duplicate 或 identity/geometry conflict；
- 哪些归属若同时成立会造成物理矛盾；
- 当前能否唯一排除，不能时必须保留未知。

最低字段包括 relation_id、scene、sar_frame、vehicle_ids、response_instance_ids、optical_ordering、exit_states、gt_link_conflicts、mutually_incompatible_assignments、exclusion_result、counterevidence、evidence_paths。

GM17 SAR 337 中 PV003/PV004 同时存在且光学前后顺序明确，两辆物理车辆不能共用同一局部响应实例；但 PV003 GT 为 diagnostic-only，因此局部所有权仍可保持未知。GM19 SAR 27 中 PV001/PV002 同帧存在；SAR 31 的两个 PV002 框中心约相距 6.75 m，必须保留 duplicate/identity conflict，不能由亮度或连续性自动选定。

## 11. UnknownOrConflictState：未知与冲突

未知是正式、可保存、可审计的状态，不是等待自动填平的空值。

最低受控状态：

| 状态 | 具体含义 |
| --- | --- |
| NO_DIRECT_SAR_GT | 当前范围无直接 SAR GT |
| IDENTITY_LINK_CONFLICT | 身份链接与光学、几何或相邻帧冲突 |
| DUPLICATE_SAME_ID_BOX | 同 ID 同帧出现多个框 |
| BACKGROUND_VEHICLE_MIXED | 局部响应可能混有背景与车辆贡献 |
| OPTICAL_PRESENT_SAR_ATTRIBUTION_UNKNOWN | 光学车辆存在，但 SAR 归属未知 |
| LOCAL_RESPONSE_PRESENT_OWNER_UNKNOWN | 局部响应存在，但所有者未知 |
| RESPONSE_BOUNDARY_UNKNOWN | 完整像素边界未知 |
| PHYSICAL_PART_IDENTITY_UNKNOWN | 是否同一物理散射部件未知 |

每个未知状态必须记录：具体原因、适用帧/范围、已知证据、反证、解除未知所需的额外直接证据。不得用 review_required 代替具体原因；不得用插值、最近邻、亮度、频率、同 ID 或人工想象消除未知。

## 12. 证据层级

每条实例和关系记录必须属于以下一层：

| 层级 | 定义 | 允许示例 | 禁止偷换 |
| --- | --- | --- | --- |
| DIRECT_OBSERVATION | 原始图或可靠叠加图中可直接看到 | 某帧存在局部响应；响应约跨多少像素；车辆退出后竖线仍在；两个同 ID 框相距约 5–7 m | 不能把跨帧同一部件、唯一所有权或完整边界写成直接观察 |
| RELATION_INFERENCE | 由多帧身份、尺度、顺序、生命周期和反证联合支持 | possibly_complementary；background_persistence_conflict；different_vehicle_exclusivity | 不能删除反证或扩大到其他车辆/场景 |
| UNKNOWN | 当前证据无法确定 | 物理部件身份、GT 缺口内 SAR 中心、完整响应边界、混合热点所有权 | 不能用插值、频率或最近邻变成已知 |

禁止把 RELATION_INFERENCE 写成 DIRECT_OBSERVATION；禁止把 UNKNOWN 通过计算或命名偷换成前两层。

## 13. 四时间尺度的关系角色

| 时间尺度 | 可约束内容 | 不能替代 |
| --- | --- | --- |
| 相邻帧 | 局部显现是否突变、几何量级是否相容、短时身份/GT 冲突 | 不能证明固定部件持续 |
| 短窗 | 同车局部观察是否可能互补或替代显现，强弱和范围如何变化 | 不能用并集、交集或出现次数生成完整对象 |
| 中窗 | 车辆尺度、相对位置、车辆坐标相容性、背景混入和跨车差异 | 不能证明刚性车辆模板 |
| 完整生命周期 | 进入、退出、遮挡、恢复、主体切换、多车排他、背景在退出后持续 | 不能压缩为统一 temporal score、频率图、最大值模板或投票 |

完整时序是多层关系约束，不是一个统计量。本合同不定义任何时间聚合计算。

## 14. 0.03 m/px 米制网格使用边界

0.03 m/px 冻结为当前固定 SAR 重建显示网格的有效物理尺度。

允许用于：

- 车辆长宽区间；
- 局部响应实例的显示网格跨度；
- 实例、GT 中心和背景结构之间的物理间距；
- 搜索范围与跨帧移动的量级记录；
- 同 ID 双框异常跳变；
- 跨帧几何相容范围。

必须使用区间、合理量级、相容范围、不确定性和观察条件。

禁止解释为：

- 3 cm 独立距离或方位分辨率；
- 亮带厚度等于实体厚度；
- 热点直径等于散射体尺寸；
- 车辆响应必须逐帧保持固定毫米/厘米位置；
- 所有车辆共享统一米制响应模板。

E07 中 GM17 PV003 335/336 的约 5.37/5.05 m 同 ID 框分离以及 GM19 PV002 31 的约 6.75 m 分离，只用于暴露身份/几何冲突，不用于构造运动或传播规则。

## 15. P1/P2/P3 术语降级

P1/P2/P3 是 O0 历史图中的人工中性观察索引，保留用于理解历史记录，但从 O1 起不得作为实体类型或跨帧主键。

新记录必须使用帧内 ID，例如：

- GM17_PV002_F330_R01；
- GM17_PV002_F330_R02；
- GM17_PV002_F339_R01。

这些 ID 只表示某帧人工直接观察到的局部响应实例。跨帧若有证据，只写 position_compatible、metric_extent_compatible、possibly_complementary、possibly_alternative_manifestation 或 cannot_determine 等关系。

不允许写 same_part=true、continued_part=true、tracked_scatterer=true。本轮没有足够直接证据解除 PHYSICAL_PART_IDENTITY_UNKNOWN。

## 16. 允许的有边界推导

| 已知证据组合 | 允许得到 | 证据层与边界 |
| --- | --- | --- |
| 完整光学生命线、外观、顺序和进入/退出一致 | same_physical_vehicle_context | RELATION_INFERENCE；不提供 SAR 像素所有权 |
| usable/high GT | sar_geometry_known 与米制量级 | DIRECT_OBSERVATION；不提供响应边界 |
| 原始 SAR 中直接可见局部响应 | sar_local_response_observed | DIRECT_OBSERVATION；所有权和边界可未知 |
| 同车上下文 + 两帧局部信息不同 + 量级相容 + 有反证记录 | possibly_complementary 或 possibly_alternative_manifestation | RELATION_INFERENCE；不等于同一部件 |
| 车辆退出后同一结构仍持续 | background_persistence_conflict | 退出与持续为直接观察，背景解释为有边界推断 |
| 同帧多车、顺序明确、归属同时成立会矛盾 | different_vehicle_exclusivity | RELATION_INFERENCE；不能唯一排除时保留未知 |
| 同 ID 双框相距约 5–7 m 或下一帧主体链接改变 | DUPLICATE_SAME_ID_BOX / IDENTITY_LINK_CONFLICT | UNKNOWN 或冲突状态；不得自动重标 |
| 光学身份继续但 SAR GT 缺失 | OPTICAL_PRESENT_SAR_ATTRIBUTION_UNKNOWN / NO_DIRECT_SAR_GT | UNKNOWN；只保存光学上下文 |

## 17. 禁止推导表

| 已知状态 | 禁止自动推出 |
| --- | --- |
| 光学车辆存在 | SAR 响应像素已知 |
| GT 框存在 | 框内所有响应属于车辆 |
| 某响应跨帧相近 | 同一物理散射部件 |
| 响应长期持续 | 车辆部件 |
| 响应高频出现 | 稳定车辆结构 |
| 多帧互补 | 多帧并集是完整对象 |
| 车辆坐标相近 | 固定刚性模板成立 |
| GT 缺失但光学继续 | 可插值得到 SAR 真值 |
| tracker ID 连续 | 完整物理车辆身份已确认 |
| 一个车辆出现明显长带 | 其他车辆也应有相同长带 |
| 单帧 GT 几何已知 | 完整 SAR 响应边界已知 |
| 相邻帧位置相容 | tracked_scatterer=true |
| 连接段连续 | 对象结构发生传播 |
| 高精度、低覆盖亮响应子集 | 车辆响应体已经恢复 |
| 人工 barrier 排除了背景 | 背景机制已自动识别 |
| 车辆坐标旋转后视觉相似 | 背景已消失或像素归属已确定 |

## 18. 正例

1. GM17 PV002 SAR 330、339、344、350：分别记录 GM17_PV002_F330_R01、F330_R02、F339_R01、F344_R01、F350_R01。可以记录同车上下文、局部响应范围改变和 possibly_complementary；不能记录固定 P1 部件或逐帧刚性模板。对应 E01。
2. GM17 PV002/PV003/PV004 SAR 344/350：PV002 有强下侧长响应，PV003 更弱更碎，PV004 未复现同等主带且背景斜线更突出。允许得到 different_vehicle_exclusivity 与跨车非模板结论；不能把 PV002 固定切线推广到其他车辆。对应 E02。
3. GM19 PV001 SAR 8、27、35：PV001 光学退出后，竖线、圆弧和热点仍持续。允许记录 SceneBackgroundStructure 与 background_persistence_conflict；不能把时间持续或高频解释为车辆部件。对应 E03。
4. GM17 PV003/PV004 SAR 335–337：同 ID duplicate 框约 5.05–5.37 m 分离，下一帧链接与三车顺序暴露冲突。允许保留 IDENTITY_LINK_CONFLICT；不能用亮度自动修正身份。对应 E04。
5. GM19 SAR 27/31：PV001/PV002 同帧上下文和退出关系必须进入归属；PV002 31 的双框约 6.75 m 分离。允许建立 MultiVehicleExclusivityRelation；不能独立裁剪后忽略排他。对应 E05。
6. GM17 PV003 395–417、PV004 395–428：光学生命线继续，但无直接 SAR GT。允许保存 NO_DIRECT_SAR_GT 与光学上下文；不能用插值裁剪生成 SAR 真值。对应 E06。
7. GM19 PV002 SAR 77、81、88：可以分别记录帧内弱/紧凑响应，并在 77→81 建立 possibly_alternative_manifestation；不能声称 27/31、77/81/88 是同一物理部件持续。

实例级完整记录见 manifests/oty2/oty2_rsa2_o1_state_relation_examples.csv。

## 19. 反例

配套反例账本 manifests/oty2/oty2_rsa2_o1_counterexample_ledger.csv 保存 14 条 ACTIVE_CORRECTION：

| ID | 被否定的错误模式 | 当前纠偏 |
| --- | --- | --- |
| CE001 | PV002 固定切线跨 PV003/PV004 推广 | 跨车显现不同，禁止统一固定切线 |
| CE002 | 高频背景等于车辆部件 | 高频只描述像素出现，不提供所有权 |
| CE003 | 车辆退出后持续结构等于对象传播 | 背景生命周期独立于车辆 |
| CE004 | 同 ID 双框 5–7 m 分离等于单车运动 | 保存 duplicate 与 identity conflict |
| CE005 | 光学身份填平 SAR GT 缺口 | GT 缺口保持 UNKNOWN |
| CE006 | 多帧并集等于完整对象 | 并集混入位置、背景和多车 |
| CE007 | 多帧交集等于稳定核心 | 交集删除间歇真实响应 |
| CE008 | 多帧最大值恢复完整车辆 | 最大值放大固定热点和背景 |
| CE009 | 车辆坐标对齐自动消除背景 | 坐标变换不改变像素所有权 |
| CE010 | GT 框等于可见响应 Mask | GT 只提供研究期几何范围 |
| CE011 | tracker/GT ID 等于完整身份真值 | 完整生命线、排他与冲突必须独立保存 |
| CE012 | P1/P2/P3 是跨帧物理部件 | 改用帧内实例 ID，跨帧只存关系 |
| CE013 | 预构造切线接受等于对象传播 | RSA1-A0 是固定几何接受测试的负面证据 |
| CE014 | component continuity 是部件连续 | 统一降级为 high_intensity_pixel_frequency |

## 20. 本轮仍未定义的内容

以下语义没有被冻结为已知结论，因为当前证据不足：

- 不同帧局部响应是否来自同一物理散射部件；
- 局部响应是否对应车头、车尾、车门、车轮或其他实体构件；
- 完整车辆响应的逐像素边界；
- 背景与车辆混合热点的精确贡献比例和唯一所有权；
- GT 缺口中的精确 SAR 中心、方向、框和响应位置；
- GM19 27/31 与 77/81/88 之间的固定部件身份；
- 一个可跨车辆、跨场景成立的统一响应模板；
- 如何自动求解、消除未知或把关系转成部署预测。

这些内容保持未定义不是遗漏，而是对证据边界的正式保存。

## 21. 不授权的算法行为

本文不授权：

- 自动响应检测、阈值分割、连通域扩展或 Mask；
- seed propagation、固定切线、曲线传播、NCC 传播；
- 候选生成、候选库、打分、排序、selector 或 winner；
- 频率图、最大值模板、多帧并集对象、多帧交集核心或统一 temporal score；
- 自动部件追踪、自动像素所有权、自动身份链接修正；
- 修改 GT、生成最终标注或训练模型；
- 把人工实例、关系和未知状态写回自动真值；
- 下一阶段算法设计或下一阶段 Codex prompt。

后续实现若只能表达单帧分数、固定部件、候选排序或时序聚合，而不能表达本文实体、证据层、排他、背景和未知，则不符合 O1。该约束只规定未来数据表达的最低语义能力，不授权本轮实施。

## 22. 语义冻结结论

O1 冻结九类核心实体/关系：

1. PhysicalVehicle；
2. OpticalVehicleObservation；
3. SARFrameObservation；
4. SARLocalResponseInstance；
5. SceneBackgroundStructure；
6. GTGeometryReference；
7. CrossFrameRelation；
8. MultiVehicleExclusivityRelation；
9. UnknownOrConflictState。

同时冻结 DIRECT_OBSERVATION、RELATION_INFERENCE、UNKNOWN 三层证据，冻结相邻帧、短窗、中窗、完整生命周期四种关系作用域，并冻结 0.03 m/px 的有效显示网格尺度口径。

这些状态足以表达 O0 中实际观察到的强响应、弱响应、无明显主带、多帧互补、多车竞争、背景持续、GT 缺口和身份冲突，同时阻止固定切线、固定部件、时序统计化、身份偷换、车辆坐标模板化和 GT 缺口填平再次被写成科学结论。

O1 的通过只表示语义合同与证据闭环完成，不表示任何自动算法、部署方法或最终车辆响应对象已经成立。
