# OTY2-RSA2-O1 状态与关系语义冻结审计

日期：2026-07-18

阶段：OTY2-RSA2-O1 Evidence-Anchored Vehicle Response State and Relation Semantics Freeze

结论：PASS。通过仅表示证据审阅、实体/关系/未知语义、正反例与核心视觉证据闭环完成；不表示任何算法、自动定位或最终响应对象已经成立。

## 1. 审计边界

本轮只执行：

- 重新审阅 O0 使用的原始 SAR、光学连续帧、旋转 GT、31 张证据图和人工清单；
- 将单帧响应实例与跨帧关系分开；
- 冻结物理车辆、观察、背景、GT、排他和未知语义；
- 制作 7 张标准化核心证据图；
- 生成状态关系实例表、反例账本和图片 manifest；
- 更新强制阅读入口。

本轮没有设计或运行检测器、阈值、Mask、候选、评分、排序、selector、winner、传播、模板、自动身份修正、自动 GT 修正、训练或下一阶段算法。

## 2. 仓库起始状态

- 分支：feature/oty2-sar-gt-structure-foundation
- 实际起始 HEAD：72a2a0fe7ca9150d67538cc5cefe9bf4dfbab1aa
- 起始本地/远端 divergence：0/0
- 起始工作树：干净
- stash：stash@{0} 只记录，未读取、应用、修改或删除

## 3. 实际阅读材料

按纠偏顺序完整阅读：

1. docs/reviews/OTY2_SAR_ROUTE_ERRORS_AND_OMISSIONS_DEEP_REVIEW_20260718.md；
2. docs/OTY2_RESEARCH_CONCLUSION_STATUS_REGISTER_20260718.md；
3. reports/oty2/oty2_rsa2_o0_open_book_vehicle_level_multitimescale_mechanism_review_20260718.md；
4. docs/OTY2_SESSION_START_HERE.md。

完整读取 O0 五份人工清单：

- reports/oty2/samples/oty2_rsa2_o0_vehicle_lifecycle_review_manifest_20260718.csv；
- reports/oty2/samples/oty2_rsa2_o0_frame_information_contribution_review_20260718.csv；
- reports/oty2/samples/oty2_rsa2_o0_multiframe_complementary_part_review_20260718.csv；
- reports/oty2/samples/oty2_rsa2_o0_multivehicle_exclusivity_review_20260718.csv；
- reports/oty2/samples/oty2_rsa2_o0_review_pack_20260718/review_pack_manifest.csv。

同时回看：

- SAR 坐标、网格和 0.03 m/px 合同；
- SAR GT 结构基础审计；
- 光学完整身份路线重置与 P0 硬同步材料；
- S1X 响应入口、低覆盖结论和 support recovery 口径；
- RSA0 对象语义、R1/R2 几何与通道法证；
- RSA1-A0 合同、报告和固定切线实现。

RSA1-A0 代码复核确认：build_segments() 沿人工 seed 轴预构造固定 12 px 直线段；图像通道只对预构造几何做接受或拒绝；连接性主要由构造保证；人工背景屏障和歧义区承担大量安全性；PV002 局部成立，PV003 未复现。因此它是负面方法论和表示错误证据，不是响应对象传播证据。

## 4. 原始 SAR 与光学连续帧复核

实际重新查看：

| 场景 | SAR 连续范围 | 高分辨率重点帧 | 光学连续范围 |
| --- | --- | --- | --- |
| GM_RM017 | 302–446 | 302、310、319、330、335、336、337、339、344、350、370、386、394、417、429、438、442、446 | PV002 145–185；PV003 151–200；PV004 162–214 |
| GM_RM019 | 0–90；另查看 20–60 同帧多车全局上下文 | 0、4、8、20、27、31、40、50、60、77、81、88、90 | PV001 0–14；PV002 5–43 |

以上是 31 个不同的提示指定 SAR 重点帧；均以高分辨率重新打开。连续接触表用于检查帧间变化、完整生命周期和多车上下文，重点帧用于回看 GT、局部响应、背景和身份冲突。

重点反向核验：

- GM17 三车在同一时段中的前后顺序；
- PV003/PV004 335–337 的身份与几何冲突；
- PV003 395–417、PV004 395–428 的直接 SAR GT 缺口；
- PV004 429/438 的同 ID 双框冲突；
- PV002 强下侧响应不能跨 PV003/PV004 推广；
- GM19 PV001 退出前后，竖线、圆弧和热点是否持续；
- GM19 27 的双车上下文和 31 的双 PV002 框；
- GM19 PV002 32–76 的直接 GT 缺口；
- 27/31 与 77/81/88 能支持的同车上下文和不能支持的固定部件身份。

## 5. 31 张 O0 证据图逐张审阅

实际打开数量：31/31。不是只检查文件存在。

检查结果：

- 路径存在：31/31；
- SHA-256 与 review_pack_manifest.csv 一致：31/31；
- 缺失：0；
- SHA 不一致：0；
- 每张均检查内容、裁剪、缩放、旋转对齐和排版可能造成的误读。

用于 O1 核心图直接重排或主要判读的 O0 图：

- gm17_pv002_vehicle_coordinate_and_parts.png；
- gm17_pv002_sar_302_386_contact_p02.png；
- gm17_pv003_sar_314_417_contact_p01.png；
- gm17_pv003_sar_314_417_contact_p02.png；
- gm17_pv003_sar_314_417_contact_p03.png；
- gm17_pv003_sar_314_417_contact_p04.png；
- gm17_pv004_sar_337_446_contact_p01.png；
- gm17_pv004_sar_337_446_contact_p02.png；
- gm17_pv004_sar_337_446_contact_p04.png；
- gm19_pv001_sar_0_35_contact_p01.png；
- gm19_pv001_sar_0_35_contact_p02.png；
- gm19_multivehicle_sar_20_60_contact_p01.png；
- gm19_pv002_vehicle_coordinate_and_background_risk.png。

其余 18 张用于辅助查证完整光学生命线、完整 SAR 范围、帧间连续性、GT 缺口、退出前后和多车全局上下文。它们仍保留在原 O0 review pack，不重复复制。

## 6. 图像与 O0 描述的一致性和降级

总体判断：O0 对“响应稀疏且不完整、不同帧提供不同局部信息、背景跨退出持续、GT 存在缺口和身份冲突”的描述与图像基本一致；没有发现需要覆盖原始图或否定 O0 整体观察的事实错误。

但部分 O0 术语的证据强度不足，必须在 O1 降级：

1. P1/P2/P3 不能被解释为跨帧固定物理部件。图像只支持帧内中性实例及有边界的帧间关系。
2. GM19 27/31 与 77/81/88 不能被写成同一响应组件持续。现有证据只支持 same_physical_vehicle_context、possibly_complementary 或 possibly_alternative_manifestation；物理部件身份保持未知。
3. 车辆坐标下的相似性不能证明刚性模板。裁剪、旋转和对齐会强化视觉相似感，背景结构也不会因坐标变换自动消失。
4. “多帧互补”不能升级为多帧并集、交集、最大值或完整响应对象。

因此本轮没有修改 O0 原报告，而是在 O1 合同、指南、实例表和反例账本中登记当前语义边界。

## 7. 冻结的实体

冻结九类核心实体/关系：

1. PhysicalVehicle：唯一默认跨帧持续的车辆实体；
2. OpticalVehicleObservation：单帧光学观察；
3. SARFrameObservation：包含多车、背景、GT 与冲突的一帧完整 SAR 上下文；
4. SARLocalResponseInstance：只属于当前帧的人工局部响应实例；
5. SceneBackgroundStructure：具有场景生命周期的竖线、圆弧、斜线、热点等；
6. GTGeometryReference：带 usable、diagnostic、duplicate、conflicting、absent 等质量状态的研究期几何参考；
7. CrossFrameRelation：连接帧内实例的有边界关系；
8. MultiVehicleExclusivityRelation：多车顺序、退出、双重解释和互斥归属；
9. UnknownOrConflictState：正式保存未知与冲突。

## 8. 冻结的证据层与跨帧关系

证据层：

- DIRECT_OBSERVATION；
- RELATION_INFERENCE；
- UNKNOWN。

冻结的跨帧关系词表：

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

关系必须保存两端实例、直接证据、推断依据、反证、证据层、适用时间范围、未知状态和图像路径。任何关系都不能省略反证后升级为物理部件身份。

## 9. 冻结的未知与冲突

- NO_DIRECT_SAR_GT；
- IDENTITY_LINK_CONFLICT；
- DUPLICATE_SAME_ID_BOX；
- BACKGROUND_VEHICLE_MIXED；
- OPTICAL_PRESENT_SAR_ATTRIBUTION_UNKNOWN；
- LOCAL_RESPONSE_PRESENT_OWNER_UNKNOWN；
- RESPONSE_BOUNDARY_UNKNOWN；
- PHYSICAL_PART_IDENTITY_UNKNOWN。

GM17 PV003 395–417、PV004 395–428 和 GM19 PV002 32–76 的 GT 缺口保持未知；插值/最近锚点裁剪标为 interpolated_review_crop_only，不是 GT 或 SAR 响应证据。

## 10. 四时间尺度和米制尺度

四时间尺度分别保存：

- 相邻帧：局部突变、量级相容、短时冲突；
- 短窗：可能互补、替代显现及其反证；
- 中窗：车辆尺度、相对位置、车辆坐标相容与背景混入；
- 完整生命周期：进入、退出、遮挡、恢复、主体切换、多车排他和背景持续。

它们不被压成 temporal score、频率图、最大值模板、投票或出现次数阈值。

0.03 m/px 只作为当前 SAR 重建显示网格有效物理尺度，用于车辆尺度、间距、搜索范围、移动量级和几何相容性；不解释为 3 cm 独立距离/方位分辨率、实体厚度、散射体尺寸或刚性模板。

## 11. 七张标准化核心证据图

目录：docs/reviews/assets/20260718_rsa2_o1_canonical/

| ID | 路径 | 用途 |
| --- | --- | --- |
| E01 | E01_GM17_PV002_MULTIFRAME_COMPLEMENTARITY.png | 帧内实例与有边界的同车多帧互补 |
| E02 | E02_GM17_CROSS_VEHICLE_NON_TEMPLATE.png | 跨车响应差异与固定切线/模板反证 |
| E03 | E03_GM19_LIFECYCLE_BACKGROUND_PERSISTENCE.png | 车辆退出后背景持续 |
| E04 | E04_GM17_IDENTITY_GEOMETRY_CONFLICT_335_337.png | 同 ID 双框与身份/几何冲突 |
| E05 | E05_GM19_MULTIVEHICLE_EXCLUSIVITY_27_31.png | 同帧多车、退出和排他 |
| E06 | E06_GT_GAP_IS_NOT_SAR_OBSERVATION.png | 光学身份与 SAR GT/像素归属分离 |
| E07 | E07_SAR_METRIC_GRID_SCALE_REFERENCE.png | 0.03 m/px 的允许和禁止解释 |

七张图全部包含场景/车辆、SAR 帧、光学状态、原始上下文、GT 质量、像素/米制说明、帧内实例或背景编号，以及“支持什么 / 不支持什么”。

## 12. 图片生成过程与辅助脚本边界

核心图由工作区任务脚本生成：

D:/profile/research/workspace/tasks/oty2_rsa2_o1_semantics_freeze/generate_canonical_evidence.py

该脚本位于工作区任务目录，未提交仓库。它只读取已有数据并执行排版、裁剪、旋转显示、GT 绘制、米制标尺和显式人工文字；没有响应检测、阈值分割、自动实例生成、自动车辆归属、评分、模板、Mask 或 GT 修改。

CSV 使用工作区任务 builder：

D:/profile/research/workspace/tasks/oty2_rsa2_o1_semantics_freeze/build_o1_csvs.mjs

builder 使用工作区依赖提供的 @oai/artifact-tool，写入三份 CSV，并在 workspace/output/oty2_rsa2_o1_semantics_freeze/csv_qa 生成只用于视觉 QA 的预览。builder 和 QA 预览均不提交仓库。

## 13. 正例、反例与清单覆盖

- manifests/oty2/oty2_rsa2_o1_state_relation_examples.csv：46 条数据行；
- manifests/oty2/oty2_rsa2_o1_counterexample_ledger.csv：14 条数据行；
- docs/reviews/assets/20260718_rsa2_o1_canonical/canonical_evidence_manifest.csv：7 条数据行。

实例表覆盖：

- GM17 PV002 330/339/344/350；
- GM17 PV003 330/335/336/337/350/394/417；
- GM17 PV004 337/394/429/438/446；
- GM19 PV001 0/4/8/27/35；
- GM19 PV002 27/31/40/60/77/81/88；
- 车辆退出后的背景结构；
- 至少 3 个 GT 缺口实例；
- 至少 4 个多车排他实例；
- 至少 4 个明确未知实例。

反例账本除题目要求的 12 类外，另外登记：

- RSA1-A0 预构造固定切线接受不能解释为对象传播；
- component continuity 只能解释为 high_intensity_pixel_frequency。

## 14. 反向硬性检查

### PhysicalVehicle

- 未等同于 GT 框；
- 未等同于单个 SAR 响应；
- tracker ID 只作为身份来源之一；
- 允许 SAR 暂时无明显响应而物理车辆仍存在。

### SARLocalResponseInstance

- 只表示单帧观察；
- 没有跨帧物理部件身份；
- 保留背景混合和未知所有权；
- 允许在 GT 框内、框边和邻域。

### CrossFrameRelation

- 保存直接证据、推断依据和反证；
- 保存时间作用域；
- 不压成数字；
- 不包含固定模板；
- 互补不写成同一部件持续。

### SceneBackgroundStructure

- 有独立场景身份；
- 可表达车辆退出后持续；
- 可表达偶然进入 GT 邻域；
- 不依赖人工 barrier 作为背景定义。

### UnknownOrConflictState

- 是可保存状态；
- 记录具体原因；
- 记录解除未知所需证据；
- 未被插值、最近邻、亮度或频率填补。

## 15. 二十项验收

| # | 条件 | 结果 |
| ---: | --- | --- |
| 1 | 31 张 O0 图逐张实际打开 | PASS |
| 2 | 关键原始 SAR 与光学连续帧重看 | PASS |
| 3 | 单帧实例和跨帧关系分开 | PASS |
| 4 | P1/P2/P3 未升级为固定部件 | PASS |
| 5 | 重要关系有具体规范图 | PASS |
| 6 | 正向关系有边界或反例 | PASS |
| 7 | GT 缺口保持未知 | PASS |
| 8 | 光学身份与 SAR 像素所有权分离 | PASS |
| 9 | 背景结构成为正式实体 | PASS |
| 10 | 多车排他成为正式关系 | PASS |
| 11 | 0.03 m/px 未写成独立分辨率 | PASS |
| 12 | 完整时序保持四层关系约束 | PASS |
| 13 | 7 图包含支持/不支持 | PASS |
| 14 | 正例和反例同时入库 | PASS |
| 15 | CSV 主键唯一 | PASS |
| 16 | 路径真实存在 | PASS |
| 17 | 图片 SHA 可复算一致 | PASS |
| 18 | 无算法、阈值、Mask、评分或自动标注 | PASS |
| 19 | 无原始 GT 修改 | PASS |
| 20 | 结构可表达强/弱/无主带、多车、GT 缺口和背景持续 | PASS |

## 16. 仍存在的语义缺口

仍未冻结为已知结论：

- 跨帧同一物理散射部件身份；
- 车头、车尾或具体构件名称；
- 完整车辆响应的逐像素边界；
- 车辆/背景混合热点的精确分解；
- GT 缺口中的 SAR 中心、方向和响应位置；
- GM19 27/31 与 77/81/88 的固定组件身份；
- 跨车辆、跨场景统一响应模板；
- 自动求解、部署表达或最终定位方式。

原因不是缺少实现，而是现有直接证据不足。O1 必须保存这些未知，不能在本轮用方案设计填补。

## 17. 最终判定

O1 冻结的状态和关系能够表达 O0 实际观察：

- GM17 PV002 330/339/344/350 的强弱与局部组合变化由帧内实例及 possibly_complementary 表达；
- GM17 PV003/PV004 的弱、碎、无固定主带和背景混合由 observation_status、SceneBackgroundStructure 与跨车排他表达；
- GM17 335–337、429/438 和 GM19 0/4/31 的同 ID 双框由 duplicate 与 identity conflict 表达；
- GM17/PV003、PV004 以及 GM19/PV002 的 GT 缺口由 NO_DIRECT_SAR_GT 等未知状态表达；
- GM19 PV001 退出后竖线、圆弧、热点持续由背景实体与 background_persistence_conflict 表达；
- GM19 27/31 的同帧双车与退出关系由 MultiVehicleExclusivityRelation 表达。

这些表达不需要固定切线、固定部件、时序统计化、身份偷换或 GT 缺口填平。O1 通过，但不授权任何下一阶段算法设计或实现。
