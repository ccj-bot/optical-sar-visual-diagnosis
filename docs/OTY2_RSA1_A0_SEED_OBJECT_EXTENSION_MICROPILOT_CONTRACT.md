# OTY2-RSA1-A0 人工种子驱动的 SAR 响应对象扩展微型验证契约

日期：`2026-07-17`

英文名称：`OTY2-RSA1-A0 Manual-Seed-Guided SAR Response Object Extension Micropilot`

分支：`feature/oty2-sar-gt-structure-foundation`

冻结起始 HEAD：`871a9741aaa581818c4343d196fee54f020c0f35`

解释器：`D:/MINICONDA/envs/py311/python.exe`

Git 外输出根：`D:/profile/research/workspace/output/oty2_rsa1_a0_20260717`

## 1. 授权范围与 R2 阶段结论的衔接

RSA0-R2 的正式阶段结论是：

```text
NEXT_PROPAGATION_DESIGN=NOT_AUTHORIZED
```

该结论仍然有效。R2 否定的是从两个短窗、存在点级偏移与语义歧义的 atlas、缺失 hotspot 主控制且不存在全背景安全通道的证据，直接升级到自动传播、方法准入、训练、泛化或最终预测。

本契约不撤销或改写 R2。新任务只额外授权：

```text
BOUNDED_MANUAL_SEED_OBJECT_PROPAGATION_MICROPILOT
```

这里的 `manual-seed-guided` 表示传播起点是人眼已经确认的中央车辆响应种子；`bounded` 表示传播只能在冻结的局部结构、背景阻断和歧义停止规则内进行；`micropilot` 表示只在 GM_RM017 的两个五帧小窗中验证一个最小关系机制，不产生自动标注能力或方法级准入结论。

因此当前允许与禁止严格分开：

- 允许：从冻结 `CONFIRMED_SEED` 出发，验证局部结构原语能否形成可追踪、有 seed 路径、受背景硬门约束的有限扩展。
- 不允许：完全自动传播、模型训练、VOS、最终响应 Mask、完整车辆框、自动标注、生命周期重放、跨场景泛化、S1-D 物理事件解释、通道加权融合、candidate ranking、selector、winner 或根据最终指标调参。

本轮唯一研究问题是：

> 从人眼确认的中央车辆响应种子出发，能否利用局部结构、时序关系和背景反事实，沿实际主响应扩展，同时不跨越确定背景，并在弧线、杂波和语义不清的端点主动停止？

## 2. 已确认的历史错误

以下错误必须保留为设计约束，而不是在新实现中重新包装：

1. 曾将光学壳层内高亮像素当成车辆响应对象。
2. 曾用 robust-z、持久频率和固定核心替代对象关系。
3. 曾把光学可观测生命周期误当成 SAR 物理存在周期。
4. 曾把大矩形内部全部当作正响应。
5. 曾由 GT 中心固定模板生成 atlas。
6. 曾用稀疏关键帧计算所谓相邻时间变化。
7. 曾把 geometry-only 位移称为 optical-proxy representation。
8. 曾在世界稳定图中没有重新计算时间通道。
9. 曾把高亮像素频率称为 component continuity。
10. 曾使用 spatially ordered first-3000 AUC。
11. 曾让无效黑区参与逐帧分位数归一化。
12. 曾硬编码 atlas audit 布尔结论。
13. 曾用单一 `median difference >= 0.03` 生成通道有效结论。
14. 曾在底层响应尚未成立时构造 birth、split、merge 和 migration。
15. 曾用大量 validator PASS 掩盖科学语义未成立。
16. 曾持续增加审计门槛，却没有实际验证一个最小对象扩展机制。

因此 RSA1-A0 不再用亮点集合、固定模板、单通道阈值、综合分数或 validator 状态替代对象关系和视觉证据。

## 3. R2 已确认的事实与仍未关闭的语义

### 3.1 工程上已经关闭的部分

- 原始 PNG、有效扇区、坐标变换、图像栈、几何和点追踪已有逐层 array lineage，管线可追踪并具有工程闭合。
- R1 proxy 分支的首个系统性错位已定位：图像未移动而 atlas geometry 按 proxy-minus-GT drift 移动；PV003 SAR 384 的漂移为 `(-22.643,+130.210) px`。
- 世界稳定、GT 对齐研究栈和 optical proxy 对齐栈已正确分离，并在各自栈上重新计算时间通道。
- geometry-only proxy displacement 已诚实保留为 localization-error sampling，而不是 proxy-aligned representation。
- fan origin、扇形几何、有效扇区和对应方向通道已有冻结依据。
- normalization、AUC sampling、atlas point audit 和 conclusion lineage 已拆开审计，不能再由单一中位数差或旧 first-3000 AUC 生成正式结论。

### 3.2 科学上可用的事实

- 单一亮度、脊线、方向、时间频率或持久性均不能安全判定车辆所有权。
- 两个主帧中的 `seed_mid` 与 `skeleton_mid` 均为 `CONFIRMED`；`skeleton_left` 仅为 `MINOR_OFFSET`。
- `skeleton_right`、fan arc、clutter 和 unresolved endpoint 均仍为 `SEMANTICALLY_AMBIGUOUS`。
- 当前唯一可以作为硬背景屏障的结构是经直接审阅确认的竖线背景。
- 世界稳定 NCC 只能作为独立背景反事实证据，不能独立判定所有权。PV003 中竖线从 `0.404` 提升到 `0.775`，而 fan arc `-0.006 → 0.010`、clutter `-0.011 → 0.054` 仍未关闭。
- PV003 的 optical proxy mapping debt 必须与传播关系失败分开；不能因 proxy drift 否定 GT 对齐研究栈中的传播机制。

### 3.3 当前资格边界

R2 没有给出自动传播、训练或泛化资格，但给出了开展有限人工种子微型验证所需的最小基础：可信中央 seed、可追踪坐标栈、冻结扇形、直接背景屏障、点级歧义记录和可复用的 R2 NPZ/证据资产。

## 4. 本轮对象与边界

本轮验证的链条固定为：

```text
CONFIRMED_SEED
→ 局部结构关系
→ 有界响应扩展
→ 确定背景阻断
→ 歧义边界停止
```

本轮不是寻找万能通道，不证明完整车辆支撑可自动恢复，不恢复不可见车体，不形成像素级 target/background 二分类，也不把响应扩展升级为最终 SAR 定位。

传播的基本单位是“局部响应结构原语”，不是独立像素候选、top-N 候选、排序库或 winner。

## 5. 冻结样本划分与防泄漏顺序

只使用 GM_RM017 的两个短窗。

### 5.1 机制发现窗

- Case：`PV002_337_341`
- 主帧：`SAR 339`
- 唯一用途：原语与关系设计、代码正确性调试、单帧左右扩展、竖线阻断、fan arc/clutter 歧义停止以及五帧短时序验证。

开发只允许查看 PV002 传播结果。

### 5.2 冻结重放窗

- Case：`PV003_380_384`
- 主帧：`SAR 384`
- 唯一用途：在所有定义、门、状态、阈值和参数冻结后进行无调参重放。

首次查看任何 PV003 传播输出之前，必须冻结：结构原语定义、图边定义、关系门、背景阻断规则、歧义停止规则、时序支持定义、状态转换和全部参数。冻结记录写入：

`manifests/oty2/oty2_rsa1_a0_rule_freeze_manifest.csv`

该 manifest 必须记录所有冻结输入与规则文件的聚合 SHA256。PV003 结果不得用于修改规则。

## 6. 隐藏最小评价参考

在任何传播执行之前，必须为十帧建立并哈希冻结独立评价参考：

- PV002：`337, 338, 339, 340, 341`
- PV003：`380, 381, 382, 383, 384`

每帧只允许记录本轮评价所需的最小几何：

1. `CONFIRMED_MAIN_SKELETON`
2. `CONFIRMED_SEED_SEGMENT`
3. `CONFIRMED_VERTICAL_BACKGROUND`
4. `ARC_OR_CLUTTER_AMBIGUOUS_ZONE`
5. `UNRESOLVED_ENDPOINT_ZONE`

允许某帧只有很短主骨架、只有中央确定段、左右端全部 unresolved 或没有可靠上侧部件。禁止标注完整响应 Mask，禁止把整个 GT 框、整个下方亮带或整个光学壳层设为正。

新增：

- `manifests/oty2/oty2_rsa1_a0_hidden_skeleton_reference.csv`
- `manifests/oty2/oty2_rsa1_a0_hidden_background_reference.csv`
- `manifests/oty2/oty2_rsa1_a0_hidden_reference_freeze_manifest.csv`

大型参考 overlay 保存在 Git 外。隐藏参考必须在传播运行前完成、冻结哈希、与传播输入物理隔离，并且只能由最终独立 evaluator 读取。传播代码及其配置不得引用这些文件。

## 7. 传播输入白名单与黑名单

### 7.1 允许输入

1. 原始或同步对齐后的 SAR 图像栈。
2. 有效扇区 Mask。
3. R2 确认的中央 `CONFIRMED_SEED`。
4. 当前帧明确的竖线背景屏障。
5. 世界稳定背景栈。
6. GT 对齐研究栈，作为主研究实验。
7. optical proxy 对齐栈，仅用于敏感性检查。
8. 冻结的扇形几何。
9. 冻结的表示通道计算。
10. fan arc、clutter 与 unresolved endpoint 的歧义区域定义。

### 7.2 禁止输入

1. 隐藏主骨架或隐藏相邻帧 skeleton。
2. 完整 atlas definite polygon。
3. 完整 GT 框作为传播区域。
4. 目标 GT 中心作为每一步扩展方向。
5. R2 已审阅的完整主骨架作为直接传播输入。
6. 评价指标、hidden-reference 评价结果或由最终输出反向调整的阈值。
7. PV003 人工结果或传播结果用于规则开发。

GT 对齐栈只允许承担研究期坐标变换角色；目标 skeleton reference 不得进入传播。

## 8. 局部结构原语与结构图

允许的原语包括：

- 短脊线片段；
- 局部方向一致的像素链；
- 与 seed 相连的窄区域；
- 短时序中具有连续位置关系的局部结构片段。

每个原语至少记录：

- `primitive_id`, `case_id`, `frame`, `geometry`；
- `length`, `width`, `mean_intensity`, `median_intensity`, `local_contrast`；
- `ridge_response`, `local_orientation`, `fan_radial_relation`, `fan_tangential_relation`；
- `temporal_support`, `world_stable_recurrence`；
- `shortest_seed_path`, `crosses_confirmed_background`, `enters_ambiguity_zone`；
- `state`, `state_reason`。

新增：

`manifests/oty2/oty2_rsa1_a0_structure_primitives.csv`

原语集合必须实现为可追踪结构图；不得生成候选分数、排名或 winner。任何 `SUPPORTED_EXTENSION` 都必须有完整路径回到 seed。

## 9. 分阶段传播顺序

### 9.1 Phase A：PV002 SAR 339 单帧空间扩展

只从 SAR 339 的中央确定 seed 开始。每个图边独立记录：

- 与 seed 或已有 supported 原语的真实连通或局部距离；
- 局部方向差；
- 脊线连续性；
- 响应宽度、曲率、灰度和局部对比度变化；
- 是否跨越竖线背景；
- 是否进入 fan arc、clutter 或 unresolved endpoint；
- 世界稳定背景复现与车辆对齐后的反事实。

这些关系不得压缩成加权总分。

### 9.2 Phase B：PV002 337–341 短时序扩展

只有单帧空间关系完成并冻结后，才允许进入五帧传播。每一帧必须重新构造局部原语，不得复制上一帧 Mask。

跨帧关系分别记录 GT 对齐位移、世界稳定位移、方向/长度/灰度变化、与前后帧 supported object 的关系及临时缺失。允许一对一、一对多、多对一、临时断裂和弱帧仅保留 seed 附近 probable。

可以分别输出：

- `FORWARD_CAUSAL_MICROPILOT`
- `OFFLINE_BIDIRECTIONAL_MICROPILOT`

两者必须分别评价。未来帧不得被伪装成因果证据，也不得把当前弱像素强行补回。

### 9.3 Phase C：PV003 380–384 冻结重放

完成 PV002 后先生成 rule-freeze manifest，再执行 PV003。GT 对齐研究栈是主传播实验，optical proxy 对齐栈仅是敏感性试验。

PV003 失败必须区分：传播关系失败、weak response 不足、atlas/reference 歧义、optical proxy mapping drift、背景稳定化不足以及 fan arc/clutter 混合。不得修改冻结规则，也不执行第二次修复。

## 10. 关系门与状态空间

### 10.1 `SUPPORTED_EXTENSION` 必要条件

成为 `SUPPORTED_EXTENSION` 必须同时满足：

1. 与 seed 或已有 supported structure 连通；
2. 未跨越确认背景屏障；
3. 未进入冻结歧义区；
4. 局部结构关系没有明显断裂；
5. 至少有一个独立结构证据；
6. 至少有一个时间证据或背景反事实证据。

### 10.2 硬否决

以下任一项成立都不得成为 supported：

- 穿越 `CONFIRMED_VERTICAL_BACKGROUND`；
- 与 seed 无连通路径；
- 只在世界稳定背景中存在；
- 只有单个孤立高亮点；
- 仅因 raw intensity、ridge response 或 temporal frequency 高；
- 进入冻结歧义区且无独立额外证据。

穿越确认竖线必须立即输出 `BACKGROUND_BLOCKED`。世界稳定复现且缺乏局部对象关系时输出 `BACKGROUND_SUSPECT_WORLD_STABLE`。进入 fan arc、clutter 或 unresolved endpoint 时保留为 `UNRESOLVED_AT_ARC_OR_CLUTTER`。

### 10.3 `PROBABLE_EXTENSION`

与 seed 连通且结构方向合理，但时序支持不足、处于弱响应边缘、背景反事实不足或接近但尚未进入歧义区时，可以输出 probable。`PROBABLE_EXTENSION` 必须独立报告，禁止并入 supported 以提高召回。

### 10.4 唯一允许状态

- `CONFIRMED_SEED`
- `SUPPORTED_EXTENSION`
- `PROBABLE_EXTENSION`
- `BACKGROUND_BLOCKED`
- `BACKGROUND_SUSPECT_WORLD_STABLE`
- `UNRESOLVED_AT_ARC_OR_CLUTTER`
- `TEMPORALLY_UNSUPPORTED`
- `NOT_CONNECTED_TO_SEED`

不得输出最终 target/background 二分类。

## 11. 扩展账本与逐步证据卡

每个被访问的结构原语都必须有证据卡，保存到：

`D:/profile/research/workspace/output/oty2_rsa1_a0_20260717/evidence_cards`

每张卡至少显示：原始 SAR 局部图、seed、决策前 supported 区、待判断原语、当前 seed 路径、竖线背景、歧义区、关键通道、世界稳定背景局部图、前后帧、各独立关系值、第一个失败或决定性门、最终状态和状态理由。

新增：

`manifests/oty2/oty2_rsa1_a0_expansion_trace.csv`

每条记录至少包含：

`case_id, frame, expansion_step, source_primitive, destination_primitive, spatial_connected, distance, orientation_difference, ridge_relation, intensity_relation, width_relation, temporal_support, world_background_recurrence, crosses_confirmed_background, enters_ambiguity_zone, first_failed_gate, state_before, state_after, decision_reason, evidence_card, evidence_sha256`

最终 overlay 不能替代逐步账本和证据卡。

## 12. 独立评价与阶段结论

评价不使用完整 GT IoU，不形成加权总分。

必须分别比较：

1. seed-only；
2. 单帧空间扩展；
3. 前向时序扩展；
4. 离线双向扩展。

主要记录：hidden skeleton 覆盖长度、seed 之外新增 confirmed skeleton 长度、骨架中部/端点覆盖、确认竖线背景污染、背景屏障跨越、arc/clutter 强制归属、无 seed 路径误扩展、每帧 supported/probable 长度、临时缺失、错误漂移、世界稳定背景吸附以及双向相对前向的增量。

probable 单独报告，不计入 supported 成功。

只有以下条件同时成立，才允许判断机制获得初步支持：

1. PV002 与 PV003 均出现 seed 之外的合理扩展；
2. 扩展覆盖冻结主骨架的新增部分；
3. 至少一个弱状态仍维持中央对象关系；
4. 确认竖线背景污染为零；
5. 没有跨越背景屏障的路径；
6. fan arc 与 clutter 没有被强制全部归入目标；
7. 每个 supported primitive 都有完整 seed 路径；
8. 同一冻结规则能够在 PV003 重放；
9. 相比 seed-only 有明确增量；
10. 增量不是由完整 GT、隐藏骨架或评价反馈产生。

阶段结论只允许：

- `MICROPILOT_MECHANISM_SUPPORTED`
- `MICROPILOT_PARTIALLY_SUPPORTED`
- `MICROPILOT_FAILED`

## 13. 失败处理

失败时定位第一个失败层：seed 可靠性、原语表达、空间连通、方向/宽度关系、背景屏障、世界稳定背景反事实、弱响应时序、arc/clutter 隔离、GT 对齐实现，或 PV003 mapping/reference debt。

本轮不执行第二次修复，不扩大 seed，不扩大 GT 邻域，不减少背景控制，也不在 PV003 上调参。失败结果本身是下一阶段依据。

## 14. 实现、产物与 Git 纪律

建议实现入口：

1. `tools/diagnostics/run_oty2_rsa1_a0_prepare_hidden_reference.py`
2. `tools/diagnostics/run_oty2_rsa1_a0_build_structure_primitives.py`
3. `tools/diagnostics/run_oty2_rsa1_a0_single_frame_seed_extension.py`
4. `tools/diagnostics/run_oty2_rsa1_a0_temporal_object_extension.py`
5. `tools/diagnostics/run_oty2_rsa1_a0_freeze_rules.py`
6. `tools/diagnostics/run_oty2_rsa1_a0_replay_pv003.py`
7. `tools/diagnostics/run_oty2_rsa1_a0_evaluate_hidden_reference.py`
8. `tools/diagnostics/validate_oty2_rsa1_a0_outputs.py`

复杂计算、CSV、几何、图结构与图像输出使用 Python；不得将研究逻辑写入 PowerShell 长命令。R2 已生成的 18 个可复用 NPZ bundle 应优先复用，避免无必要重算。

大型图像、图数组、NPZ 与证据卡保存在 Git 外输出根。仓库内只提交代码、配置、轻量 manifests、报告和 validator 摘要。

本契约与 `docs/OTY2_SESSION_START_HERE.md` 的 reading-order 更新必须先形成并推送 docs-only 提交：

`docs(oty2): define RSA1 A0 seed-object extension micropilot`

该提交推送并复核工作树、divergence 与 stash 后，才允许建立隐藏参考或编写传播实现。既有 `stash@{0}` 不得触碰。

实现完成后建议提交：

`feat(oty2): add bounded seed-object extension micropilot`

## 15. 正式报告问题

正式报告只回答：

1. 从中央 seed 出发，算法实际沿什么结构扩展？
2. 每个 supported extension 通过了哪些关系门？
3. 扩展是否覆盖 seed 之外的确认主骨架？
4. 是否成功阻止确认竖线背景污染？
5. 在 fan arc、clutter 和端点处是否主动保留歧义？
6. 冻结规则在 PV003 中是否复现，失败属于传播、参考还是映射？
7. 当前结果支持继续扩大微型验证，还是应停止该传播机制？

每个回答必须引用具体帧、primitive、expansion step、gate、证据卡和 hidden-reference 评价。

本轮核心交付不是更完整的 Mask，而是证明或否定一个最小机制：以少量确定车辆响应为种子，通过局部结构与时序关系向外建立对象支持，同时以明确背景为硬阻断，并在无法确认的弧线、杂波和端点处保持未决。
