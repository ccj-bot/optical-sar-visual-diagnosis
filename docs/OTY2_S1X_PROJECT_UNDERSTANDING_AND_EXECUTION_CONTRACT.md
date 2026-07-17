# OTY2-S1X 项目理解与执行契约

日期：`2026-07-17`

中文名称：`OTY2-S1X 光学条件下的 SAR 时序联合支撑恢复`

英文名称：`OTY2-S1X Optical-Conditioned Joint SAR Temporal Support Recovery`

冻结起始提交：`fb69df0bd050106a9cad62f2d8cc50e5c6750319`

## 1. 阶段转换与最终目标

本轮由此前 S1-L / S1-LR / S1-LR2 的 GT 邻域内机制审计，转为第一次正向、无待评价 SAR GT 的项目级闭环。旧报告全部保持冻结；其中关于显示域结构、共同场景运输、背景稳定化和局部响应组织的结论只作为方法设计依据，不作为本轮目标位置输入。

最终目标不是让 SAR 单独识别车辆，也不是从候选框库中选择一个最高分框。研究单位是 P1-E 光学完整时序确认的一辆物理车辆。光学线程负责身份、准入/准出、时间范围、粗方位、尺度和可见状态；SAR 灰度时序只在该条件壳层内恢复可见响应、排除背景并维持弱响应帧。输出是可解释的时序支撑状态，不是唯一精确框。

## 2. 光学、SAR 与 GT 的角色

### 2.1 光学

本轮实际光学来源为：

- `manifests/oty2/oty2_p1e_canonical_optical_vehicle_registry.csv`；
- `manifests/oty2/oty2_p1e_canonical_vehicle_frame_states.csv`；
- `manifests/oty2/oty2_p1e_detection_to_canonical_identity_map.csv`；
- `D:/profile/research/data/<scene>/<scene>_frames`；
- `D:/profile/research/data/<scene>/<scene>_depth`。

P1-E 提供三场景 `14/4/4` 个 canonical optical vehicle、逐帧可见状态和 reference bbox。它是只由光学画面建立的真实研究基准，但文件明确标记 `benchmark_only=true;not_runtime_input=true`，所以它可作为本轮真实光学观测研究代理，不能被描述为已经部署的自动身份流。

光学负责：

- canonical physical vehicle identity；
- 进入、完整可见、部分可见、退出边界；
- 24 fps bbox 中心、底部接地点代理、宽高和尺度趋势；
- depth sidecar 的近远趋势；
- 多车同时存在和主体切换边界；
- 对 SAR 50 fps 的插值条件。

### 2.2 SAR

SAR 输入只使用三场景 `2308×1334` 的 8-bit 灰度显示帧及固定 `imaging_valid_mask`。灰度图不含相位，不能恢复原始散射中心或绝对 RCS。SAR 负责：

- 在光学壳层内形成整段时空响应体；
- 通过多背景共同运输稳定化排除固定背景；
- 分离持久、间歇、混合和背景响应；
- 在弱响应帧通过前后状态维持响应；
- 输出分通道证据和每帧状态，不压成单一总分。

### 2.3 GT

SAR GT 分成两种角色：

1. `GM_RM017:PV004` 是独立校准车辆，只用于在本轮发现/重放前冻结单车研究代理映射；它不参与发现或重放评价。
2. `GM_RM017:PV002` 与 `GM_RM017:PV003` 的 GT 只允许由独立 evaluator 在推理输出写盘、冻结并计算 SHA256 后读取。

推理入口不得读取 `oty2_s0_sar_gt_quality_audit.csv`、`oty2_s1l_local_response_fields.csv` 或任何含待评价 GT 中心、尺度、角度、IoU 的文件。校准结果必须预先写成不含目标 GT 行的独立配置；推理只读取该配置。

## 3. 已解决的前序问题

仓库已经提供以下可直接继承事实：

1. P0 冻结光学 `24 fps`、SAR 灰度 `50 fps` 和 frame-0 共同起点的项目操作假设；三场景均为 368 光学帧和 766 SAR 灰度帧。
2. P1-E 建立了只由完整光学时间流确认的 canonical vehicle benchmark、逐帧状态和 detector/tracker provenance。
3. S0-M 冻结了 fan-polar display coordinate 和全场固定 `imaging_valid_mask`：`2308×1334`、origin `(1154.0,1330.6)`、radius `1332.7 px`、packed-bit SHA256 `7bdfbc5417db5f96405751d7503973f16db85957cf9aa0c6a8f30975cc0502ef`。
4. S0-MV 纠正了 mapping eligibility 与 SAR structure eligibility 的混淆。
5. S1-L 证明处理后灰度显示域存在可重复局部结构，但背景可复现部分持续性，不能直接赋予车辆所有权。
6. S1-LR2 在 `GM_RM017:PV002 / 330–350` 中以多背景相位中位数建立了最小充分的 global-translation common-scene transport，并在稳定化后确认 `21/21` 帧的局部横向响应核心。
7. S1-LR2 同时证明 Raw-GT 逐帧增量不可靠，339 的变化不是车辆专属跃迁，主带、上侧结构和热点的单项形式也可能被背景复现。

这些内容本轮只做必要重放，不再重新扩展成局部 GT 邻域审计。

## 4. 尚未解决的问题

1. P1-E canonical thread 仍是 benchmark，不是部署期自动 optical identity output。
2. 真实 optical-derived centre、axis 和 scale 尚未在 SAR 推理中执行过。
3. 旧 `azimuth_k/azimuth_b` 映射由 SAR GT 锚点建立，且开发车辆包含 PV002，不能直接作为本轮无泄漏 target mapping。
4. depth sidecar 的生成脚本和绝对尺度 lineage 未在仓库中找到；其值只能作为研究期光学派生代理。
5. SAR 物理米制网格、原始 amplitude/complex/IQ/ADC 与固定灰度映射仍缺失。
6. 不同车辆之间的 optical bbox height 到 SAR radial location 的可迁移性尚未建立。
7. 当前 8-bit SAR 能否在光学壳层内稳定区分车辆响应与所有复杂背景，仍需本轮项目级比较回答。

## 5. 与旧路线的根本区别

### 5.1 不同于每帧候选生成与排名

本轮不产生独立单帧框库，也不计算加权总分。一个 target window 只建立一个光学条件时空壳层，在整段 `x-y-t` 证据体上求持久、间歇、背景和混合状态；逐帧结果由同一时空对象投影得到。

### 5.2 不同于 SAR-only 全场盲检测

SAR-only 只作为有限诊断基线，用相同稳定化和响应体构造检查全场会产生多少背景对象。它不承担身份恢复，也不成为主方法硬门。

### 5.3 不同于已知 SAR GT 邻域内结构审计

发现和重放壳层由 P1-E 光学线程、24/50 时间契约、独立 PV004 校准与固定 fan geometry 生成。待评价 PV002/PV003 的 SAR GT 路径不会进入 inference process。

### 5.4 不同于精确 GT 框恢复

本轮允许粗支撑、多个局部区域、暂时暗响应和 mixed/unresolved 状态。SAR 的成功标准是相对 optical-only shell 的背景排除与支撑收缩，而不是恢复唯一 GT 框。

## 6. 真正可部署输入与研究期代理

### 6.1 部署期原则上可得

- 原始光学帧；
- detector bbox 与置信度；
- 光学帧号；
- 固定 24/50 软件同步契约；
- SAR 灰度帧；
- 固定 fan geometry 和 `imaging_valid_mask`；
- 从非目标区域估计的共同场景运输；
- 由当前及前后 SAR 帧形成的因果/整窗响应证据。

### 6.2 本轮研究期代理

- P1-E canonical vehicle identity、reference bbox 和 lifecycle state：真实光学 benchmark，但不是自动 runtime output；
- optical depth `.npy`：真实光学派生资产，但生成器与绝对尺度 lineage 未解析；
- PV004-only 方位/径向校准：不使用 PV002/PV003 GT，但只有单车、单场景支持；
- 光学 bbox 的无符号方向：由 bbox/轨迹和侧视可见状态形成宽范围代理，不是车辆前后方向；
- SAR 尺度范围：由独立校准车辆与宽不确定度给出，不是目标 GT 尺度。

以上代理必须在 lineage manifest 中明确标记，不能被包装为已经部署的自动输入。

## 7. 本轮窗口与冻结划分

### 7.1 独立校准

- scene/vehicle：`GM_RM017:PV004`；
- SAR frame：`352–394`；
- optical frame：`169–189`；
- 选择理由：P1-E 标记为 full-visible，且不作为发现或重放目标；
- 用途：冻结 `optical_center_x -> SAR theta`，并把 `optical_bbox_height -> SAR radius` 与 depth-proxy radial prediction 合并成宽区间研究代理；
- 禁止：用于项目级成功率或重放结论。

### 7.2 发现窗口

- scene/vehicle：`GM_RM017:PV002`；
- SAR frame：`330–350`；
- 对应 optical frame：约 `158–168`；
- 选择理由：提示指定的机制清晰窗口，且对应 P1-E full-visible optical thread；
- 推理时不得读取该车辆 SAR GT。

### 7.3 固定规则重放窗口

- scene/vehicle：`GM_RM017:PV003`；
- SAR frame：`338–391`；
- 对应 optical frame：`162–188`；
- 选择理由：由 P1-E full-visible lifecycle 自动决定，未按 SAR GT 视觉效果挑选；
- 规则、阈值、校准和背景处理在发现窗口输出冻结后保持不变。

## 8. 如何证明 SAR 相对光学单独输入有增量

三个方法共享同一 optical window、calibration config、fan mask 和评价 GT：

1. Optical-only 只输出时序方位/径向粗壳层，不读取 SAR 灰度。
2. SAR-only 在全 valid fan 上形成盲时空响应对象，记录背景对象数量与目标事后覆盖，不承担身份。
3. Optical+SAR 在 optical shell 内用稳定化 SAR 形成联合支撑管道。

冻结后 evaluator 分别报告：GT 可见响应覆盖、shell/support 面积、背景污染、收缩比例、断帧、弱帧维持、固定背景排除、其他车辆误接和主体边界越界。每个指标单独报告；不生成综合分数。只有 optical+SAR 在保持覆盖和身份边界的同时显著减少背景或断帧，才能称为 SAR 增量。

## 9. 最可能的误区与预防

1. **把 PV002 旧 mapping 当无泄漏输入。** 预防：只用 PV004 校准输出；inference 禁止导入 GT manifest。
2. **把 depth 当精确物理距离。** 预防：记录 generator unresolved，只用于宽 radial interval 和趋势。
3. **把 S1-LR2 横带写死。** 预防：主方法使用方向范围、连续响应和背景排除；不要求固定 y、固定长度、固定 339 起点或固定热点布局。
4. **退回 per-frame candidate/ranking。** 预防：只输出整窗时空对象、状态传播与分通道证据。
5. **把 brightest response 当中心。** 预防：亮度只是一条通道，不能单独决定支撑。
6. **用背景单项复现否定联合关系。** 预防：比较持续性、方向、局部多部件关系、光学壳层和背景固定性，不使用单特征否决。
7. **因不能恢复完整框而判路线失败。** 预防：可见响应管道、背景排除和弱帧连续性是正式成功产物。
8. **用项目级 NOT_READY 代替正向执行。** 预防：输入不足时扩大不确定区间；只有原始资产或必要校准完全不存在才阻塞。

## 10. 实现顺序与停止条件

实现顺序：

1. 冻结 Git、环境、输入文件与哈希；
2. 写入本执行契约；
3. 生成 input-lineage manifest；
4. 以 PV004 生成独立 calibration config；
5. 静态扫描 inference 入口，禁止 GT 路径和字段；
6. 生成统一 optical-condition JSONL；
7. 运行 optical-only、SAR-only 和 optical+SAR；
8. 写盘并冻结 inference SHA256；
9. 直接审阅不带 GT 的发现窗口可视化；
10. 独立 evaluator 才读取 PV002/PV003 GT；
11. 不改规则重放 PV003；
12. 若重放失败，只允许一次有来源的最小修复，并重新冻结版本；
13. validator、报告、commit、push。

停止条件：

- branch、HEAD 或 worktree 发生未授权冲突；
- PV004 校准资产不存在或无法与 P1-E optical state 对齐；
- inference 代码或配置出现 PV002/PV003 GT 路径、中心、尺度、角度或 IoU；
- 输出冻结前 evaluator 被调用；
- 方法退化为 per-frame candidate bank、weighted ranking、唯一框或 GT 邻域运行；
- replay 规则在查看 PV003 GT 后被修改而没有重新声明为下一轮实验。

## 11. 实现前自检

| 自检项 | 结论 | 纠正措施 |
| --- | --- | --- |
| 是否仍在尝试 SAR-only 检测作为主方法 | 否 | SAR-only 只保留有限诊断基线 |
| 是否以待评价 GT 邻域作为推理输入 | 否 | PV002/PV003 GT 仅由独立 evaluator 读取 |
| 是否把任务降回局部横带审计 | 否 | 输出覆盖完整发现与重放窗口的时序支撑管道 |
| 是否要求恢复唯一精确框 | 否 | 允许 core/intermittent/mixed/weak 状态 |
| 是否准备每帧生成候选后加权选择 | 否 | 只形成全窗口时空对象和状态传播 |
| 是否只准备输出 NOT_READY | 否 | 真实光学代理不足时保留宽区间并继续正向恢复 |

自检通过，允许进入实现。
