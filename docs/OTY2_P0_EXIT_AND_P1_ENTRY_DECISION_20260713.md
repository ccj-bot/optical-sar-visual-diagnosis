# OTY2 P0 Exit and P1 Entry Decision (2026-07-13)

## Decision purpose and authority

This document records the post-audit stage decision for OTY2. It does not rewrite the P0 evidence, rerun the P0 audit, or change any P0 manifest or hard-sync CSV.

The evidence source remains:

- `reports/oty2/oty2_p0_data_asset_and_hard_sync_audit_20260713.md`

The higher-level research basis remains:

- `docs/OTY2_RESEARCH_ROUTE_RESET_RECORD_20260713.md`

## 1. P0 总体状态

P0 总体状态保持为：

`P0_DATA_FOUNDATION_PARTIALLY_READY`

不得将该状态改写为全面 READY。尚未冻结的内容包括：

- 同场景光学 frame 0 与 SAR frame 0 的共同起始没有公共硬件时钟、逐帧时间戳或采集日志独立证明；
- 原始 ADC/IQ、距离压缩结果、复数成像结果及其他中间成像 lineage 尚未确认；
- SAR 唯一米制坐标、雷达原点、坐标轴、有效成像 Mask 和 Mask 语义尚未冻结；
- GM_RM019 伪彩源 MP4 的约 48.300063 fps 时间基与灰度 SAR 的 50 fps 存在冲突；
- 历史记录所述独立 231 行资产尚未找到，当前 canonical review/GT 表为 442 行。

该状态说明 P0 仍有基础事实需要在后续阶段继续关闭，但不再把所有未决项无条件作为光学侧 P1 的阻断条件。

## 2. 操作性硬同步契约

项目负责人正式采用以下同步契约：

- 光学源时间轴：24 fps；
- SAR 权威时间轴：灰度 SAR 的 50 fps；
- 同一场景中，光学 frame 0 与 SAR frame 0 作为共同时间原点；
- 全帧关系使用固定采样率计算；
- 不建立逐样本软同步分数；
- 不根据 GT、IoU、候选质量或标注结果反向调整时间偏移；
- 除非发现能够直接否定该关系的反例，否则后续研究统一使用该契约。

时间轴定义为：

\[
t_o(i)=i/24
\]

\[
t_s(j)=j/50
\]

该同步契约的证据边界是：

> **项目操作性冻结假设**

它不是公共硬件时间戳、严格同步触发或共享时钟的已证实事实。固定帧率已由当前源 MP4 容器确认；共同时间原点是项目为保持后续研究一致性而正式冻结的操作性假设。

## 3. GM_RM019 伪彩时间基决定

- SAR 灰度流是同步计算和时间配对的权威来源；
- SAR 伪彩流是派生显示资产，不构成独立物理时间轴；
- 当伪彩帧号与灰度 SAR 帧号一一对应时，伪彩帧按同编号灰度帧继承 50 fps 权威时间轴；
- `GM_RM019_R.MP4` 约 48.300063 fps 的容器元数据冲突保留为 P2 前必须完成的 lineage 审计项；
- 该冲突不改变当前灰度 SAR 的 50 fps 时间轴，也不阻断光学侧 P1；
- 本轮不重新编码视频，不修改任何原始视频、图片或派生帧资产。

## 4. P1 准入决定

P0 已确认以下光学资产事实：

- GM_RM011、GM_RM017、GM_RM019 三个场景的光学完整时间流均存在；
- 每个场景均为 368 帧；
- 帧号范围均为 0..367 且连续；
- 无重复编号；
- 无重复内容；
- 无尺寸异常；
- 光学帧尺寸均为 800×600；
- 光学直接源 MP4 均确认是 24 fps。

因此，现正式允许进入：

> **P1：光学完整时间流上的离线全局物理车辆身份重建**

阶段准入状态为：

`P1_OPTICAL_GLOBAL_IDENTITY_ALLOWED`

该状态只表示光学资产子项和阶段边界满足 P1 准入条件，不替代或提升 P0 总体状态。P0 仍保持 `P0_DATA_FOUNDATION_PARTIALLY_READY`。

## 5. P1 强制边界

P1 必须遵守以下边界：

- 只处理完整光学时间流；
- 可以审计光学检测资产、形成短轨迹并进行离线全局身份关联，但 tracker ID 不得直接等同于物理车辆身份；
- 不使用 SAR 灰度、SAR 伪彩、SAR 响应或 SAR GT 决定光学车辆身份；
- 不使用 GT、IoU、最终框、人工 SAR 选择或后验 SAR 结果修正光学身份；
- 不进入光学到 SAR 方位映射拟合；
- 不进入 SAR 米制坐标、有效成像 Mask 或散射结构研究；
- 不进入 SAR candidate、Gate、selector、ranking 或物理机制实验；
- 不生成 SAR 标注、最终 SAR 框或自动标注建议；
- P1 输出必须是可复核的物理车辆线程、身份关系、准入/遮挡/恢复/退出状态及冲突证据。

## 6. 阶段关系

- P0 evidence status: `P0_DATA_FOUNDATION_PARTIALLY_READY`；
- Operational sync contract: frozen for project use, common-start remains explicitly an assumption；
- P1 entry status: `P1_OPTICAL_GLOBAL_IDENTITY_ALLOWED`；
- P2 and later cross-modal/SAR stages: not authorized by this document；
- GM_RM019 pseudocolor timebase lineage, SAR metric coordinates, Mask semantics, and raw/imaging lineage remain future closure items。

## 7. 本轮非执行声明

本决策修订只固化研究路线和阶段准入，没有运行 P0 审计、检测器、跟踪器、轨迹生成、Working Graph、方位映射、SAR candidate、Gate、selector、ranking、GM_RM017 物理机制、训练、阈值调优或自动标注。
