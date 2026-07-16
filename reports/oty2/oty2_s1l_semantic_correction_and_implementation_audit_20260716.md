# OTY2 S1-L 结论语义纠偏与实现审计

日期：`2026-07-16`

工作名称：`S1-L 结论语义纠偏与光学条件支撑可观测性分解（GT 探索代理审计）`

冻结起始 HEAD：`75eed68a19c94428c27d8a217d3dab36c56f20d6`

本文件是上一轮 body-support 审计的新增纠偏补充。它不修改 S0、S0-M、S0-MV、S1-L 或 body-support 冻结文件，不宣布进入 S1-D，不运行潜在支撑重建，不生成自动标注、最终框、candidate bank、selector、ranking、GT-IoU 决策、训练模型或综合分数。

## 1. 必须纠正的反事实语义

上一轮的两条车辆轨迹交换把一辆真实车辆的轨迹放到另一辆真实车辆区域：

- `PV002 trajectory around PV003 vehicle region`；
- `PV003 trajectory around PV002 vehicle region`。

它们的正确类别是：

`IDENTITY_NEGATIVE_CLASS_POSITIVE`

即：

- 对源车辆的物理身份为阴性；
- 对车辆类别仍为阳性；
- 可否定 `SAR_ONLY_PHYSICAL_IDENTITY_SPECIFICITY`；
- 不可作为 `VEHICLE_CLASS_SUPPORT_OVER_BACKGROUND` 的阴性背景；
- 不可用“另一辆车区域也复现”直接否定车辆类别级结构。

旧报告中的“车辆特异性失败”必须在本补充中限定为：

> SAR-only 物理车辆身份特异性未建立。

它不等价于：

> 车辆类别相对背景的支撑规律已经失败。

光学完整时序负责物理车辆身份、轨迹和粗方位。SAR 在本轮研究的是：如果未来由光学给定这些条件，8-bit 处理后 SAR 是否可能提供保守支撑证据。但本轮实际执行的中心、轴向和尺度仍是 GT-discovery proxy，并未接入真实 optical-derived input。因此本轮不能把 `OPTICAL_CONDITIONED_SUPPORT_READINESS` 写成无条件正向结论，只能固定为 `NOT_EVALUATED_WITH_REAL_OPTICAL_INPUT_GT_PROXY_ONLY`。

## 2. 结论必须分解

后续不得再用单一 `body-support READY/NOT_READY` 包办所有语义。必须分别报告：

1. `GT_CONDITIONED_BODY_ALIGNMENT`
2. `BODY_AXIS_INCREMENTAL_VALUE`
3. `VEHICLE_CLASS_SUPPORT_OVER_BACKGROUND`
4. `SAR_ONLY_PHYSICAL_IDENTITY_SPECIFICITY`
5. `CENTER_RADIAL_OBSERVABILITY`
6. `CENTER_TANGENTIAL_OBSERVABILITY`
7. `LONG_SCALE_OBSERVABILITY`
8. `SHORT_SCALE_OBSERVABILITY`
9. `AXIS_OBSERVABILITY`
10. `OPTICAL_CONDITIONED_SUPPORT_READINESS`

另固定声明：

`UNIQUE_BOX_RECOVERY=NOT_EVALUATED_NOT_AUTHORIZED`

## 3. GT 条件循环性审计

当前 body coordinate 的证据链全部受 GT 条件控制：

- Raw/Smoothed anchor 由 GT bbox consensus 与 rolling smoothing 形成；
- body 中心直接来自 Raw/Smoothed GT anchor；
- 无符号长轴由 GT angle 和 GT width/height 决定；
- 线程参考长短轴是 Raw-GT 长短边中位数；
- 旧 world canvas 也由整条 Raw/Smoothed GT crop 包络定义；
- similar-view pair 的观测角由 GT 中心和 GT-derived axis 计算。

实现位置：

- `tools/diagnostics/run_oty2_s1l_continuous_sar_structure.py:253`
- `tools/diagnostics/run_oty2_s1l_continuous_sar_structure.py:406`
- `tools/diagnostics/run_oty2_s1l_body_support_coordinate_casebook.py:155`
- `tools/diagnostics/run_oty2_s1l_body_support_coordinate_casebook.py:344`
- `tools/diagnostics/run_oty2_s1l_body_support_coordinate_casebook.py:688`

因此旧 body advantage 的正确名称只能是：

`GT_CONDITIONED_BODY_ALIGNMENT`

它不是独立检测证据，也还没有证明 GT-derived body axis 相对安慰剂轴有纯轴向增量价值。旋转长短边不等的矩形窗口会改变实际采样的源像素，因此后续 body delta 只能称为 `GT-conditioned body-oriented anisotropic-window increment`：它混合了轴向、旋转后的源支持足迹与重采样，不能单独归因为物理 body axis。

## 4. 坐标表示视野不等价

旧 runner 的五种表示都输出 `256×128`，但覆盖的源图范围不同：

- `world`：整条 GT crop 轨迹包络；
- Raw/Smoothed crop：逐帧 GT 径向/切向外接范围；
- Raw/Smoothed body：GT 线程中位长短轴固定窗口。

只读重算表明，GM_RM017 中：

- world 每个输出格约覆盖 `3.13-3.95 × 3.53-3.69` 源像素；
- body 每格约覆盖 `1.07-1.13 × 0.99-1.05` 源像素；
- crop 每格约覆盖 `1.15-1.23 × 1.64-1.84` 源像素。

world 的目标占比、背景进入比例、频率带宽和插值模糊均与局部表示不同。GM_RM011 的有效 Mask 也明显不同：world 约 `0.727`，crop 约 `0.96`，body 约 `0.999`。

旧 fixed-background 的 world 又使用小固定窗，而车辆 world 使用整条轨迹大包络，因此“车辆 body 优势”和“背景 world 优势”跨单位也不是等支持对照。

结论：旧跨表示 NCC 只能保留为视野混杂下的初步方向证据，不能全部解释为坐标归属。

## 5. 扰动归一化债务

旧 coordinate 和 perturbation runner 对所有表示与扰动复用原 GT 行的：

- `local_background_median`；
- `thread_raw_p99`。

这两个量本身来自 GT 条件 crop。`normalized_score()` 还会 clip 到 `[0,1]`，因此固定基准会通过饱和和截断影响 NCC、support area、entropy、occupancy 和 outer mass，而不只是做线性强度换算。

额外混杂：

- fixed-background 使用 PV002 源 GT 行的归一化；
- trajectory swap 保存 target rows，因此使用目标车辆 GT 行的归一化。

新实验必须同时保留：

- `FIXED_REFERENCE`；
- `CANDIDATE_LOCAL_REESTIMATED`。

两条路径不得平均或加权。方向相反时必须标记 `NORMALIZATION_DEPENDENT`。

## 6. similar-view pair 混杂

旧 pair 规则为：

- frame gap `>=10`；
- GT-conditioned view-angle difference `<=5°`；
- NCC 有限。

但旧输出只保留 count 和 median，没有左右帧、真实时间差、视角差、端点可靠性、逐 pair NCC 或 leave-one-pair-out。

更关键的是，旧 coordinate runner 对所有表示统一传入 Raw-GT-derived pair set。因此报告中的 Smoothed-body：

- PV002 `0.574` 来自 Raw-defined 8 对；
- PV003 `0.571` 来自 Raw-defined 4 对；
- PV004 `0.429` 来自 Raw-defined 14 对。

若按 Smoothed view 真正重建 pair set：

- PV002 仅 3 对，median 约 `0.195`，且全部包含 frame 310 的 registration-unreliable 端点；
- PV003 仅 1 对，median 约 `0.469`，LOPO 不可评；
- PV004 仅 3 对，median 约 `0.458`。

旧 perturbation runner 还会随每个参数重新计算 view angle，导致不同 setting 的 pair count 变化，参数曲面同时混入场变化与 pair membership 变化。

新实验必须先在每个 source-positive vehicle 上冻结显式 pair manifest，再按 frame intersection 投影到 swap、background 和 temporal counterfactual；反事实不得重新择对。同一 anchor variant 下，四表示、七种轴规则、双归一化和所有参数扰动必须使用同一 source-pair hash 与 projected-pair hash。源端 reliability 不能冒充 counterfactual target registration 已验证，后者必须显式标记 `COUNTERFACTUAL_TARGET_REGISTRATION_NOT_INDEPENDENTLY_VALIDATED`。

pair 行是共享帧上的重复对比，不是独立样本。除 leave-one-pair-out 外必须同时输出 leave-one-frame-out、unique-frame count、最大 frame degree 和 pair graph components。pair 数 `<=4` 永远标记 `SPARSE_PAIR_EVIDENCE`；更大 pair 数也只能称 `PAIR_COUNT_GT4_SHARED_FRAME_REPEATED_EVIDENCE`，不得写成稳定泛化或有效样本量。

## 7. 反事实数据可用性

### 7.1 身份阴性、车辆类别阳性

现有两条 PV002/PV003 交换可直接复用，但只用于身份审计。正向交换有 58 个共同帧；反向交换同为 58 帧，但旧 nonadjacent pair 证据更弱。

### 7.2 车辆类别阴性

冻结背景表中可直接作为位置提案的 GM_RM017 单位包括：

- `S1L-BG-0010`：same-azimuth neighbor，65 帧，旧 GT overlap 为 0，旧状态 usable；
- `S1L-BG-0011`：fixed strong line，65 帧，旧 GT overlap 为 0，但旧质量状态 limited。

`S1L-BG-0009` 的旧 mean GT overlap 约 `0.209`，`S1L-BG-0012` 约 `0.081`，不能直接当车辆类别阴性。

第三个背景在报告完成后按预注册硬约束冻结为 `S1L-BG-OCS-B3-SA35N`：

- PV002 moving same-azimuth offset：`dr=-209.722594 px, dt=0`；
- equal-support window：`272.209 × 125.88975 px -> 256×128`；
- 65 帧 min/mean valid fraction 均为 `1.0`；
- reviewed-GT overlap 为 `0`；
- 与 BG0010/BG0011 支撑范围无重叠；
- 65 帧直接审阅只见孤立强散射点、旁瓣和弧线背景，没有持续车体形状。

该单位支持 hard-scatter 角色，但车辆复杂度匹配仅为 partial：梯度、Laplacian 和动态范围低于车辆，而亮连通片更多。因此其质量状态固定为 `B3_HARD_CONSTRAINT_PASS; HARD_SCATTER_ROLE_SUPPORTED; VEHICLE_COMPLEXITY_MATCH_PARTIAL; USABLE_VEHICLE_CLASS_NEGATIVE_WITH_LIMITATIONS`，不得宣称完整复杂度等价。

随后对“固定强线背景是否可替换为真正空间分离控制”做了冻结 64 项 fixed-grid 审计。结果是：唯一通过严格基线几何约束的 `FX_8_8`（`dr=479.36592922347614 px, dt=667.2840797804607 px`）在 65 帧、四表示直接复核中没有持续强线，只呈弱各向异性斑点；真正显示强线/弧的 `FX_4_4` 又与 BG0010 重叠。因此冻结 bank 内不存在同时满足“严格分离＋持续强线角色”的候选，不能为凑角色而错误命名。

本轮采用有界四控制方案：

- BG0010 与 BG0011 属于同一 baseline spatial cluster，BG0011 只保留为同簇 strong-line role diagnostic；
- B3 是第二个 baseline spatial cluster；
- 新增 `S1L-BG-OCS-B4-FX88` 作为 fixed anisotropic-speckle control，明确 `NOT_STRONG_LINE`，构成第三个 baseline spatial cluster。

四控制六组两两审计中，只有 BG0010-BG0011 有重叠（最大 `0.9440324609715243`，最小中心距 `6.9946758959516115 px`），其余五组 baseline rotated-footprint overlap 均为 `0`。但 FX88 与 BG0010 的 baseline outer-circle 余量只有 `9.834045584691012 px`；纳入既有一维中心/尺度扰动包络后，严格图只剩两簇 `{BG0010, BG0011, FX88}` 与 `{B3}`。因此三簇结论只适用于 baseline equal-support，不适用于完整参数 sweep。

B3 与 FX88 都没有按综合分数选择；它们分别来自冻结 proposal enumeration 的硬约束可行项。GM_RM011 的零 overlap 背景只保留为未来跨场景诊断债务。

“同路径无车时段”当前不可可靠定义：光学 outside 不等价于物理车辆不存在，因此只能作为 wrong-time temporal negative，不能标为 vehicle-class negative。

### 7.3 时序阴性

PV002/PV003/PV004 的连续帧、图像路径、中心和轴字段足以构造：

- time shuffle；
- time reverse；
- trajectory time shift；
- center trajectory phase shift。

时间错位和中心相位移固定为 `+8 SAR frames`（当前 cadence 下约 `0.16 s`）。该值在运行前冻结：PV002/PV003/PV004 分别保留 `56/55/50` 个对齐样本，中心位移中位数约为 `0.693/0.696/0.726` 个参考短轴。它不是按结果调出的阈值。

`TEMPORAL_REVERSE` 的真实操作是“反序图像对应原时刻 anchor”，因此它是 wrong-correspondence / invariance control，只检验 correspondence robustness，不是 arrow-of-time experiment。对称 NCC/无向邻接天然不敏感时，必须写 `NOT_APPLICABLE_TO_TIME_REVERSAL`，不能据此宣称时间方向成立。

## 8. 实验 gate 决定

实现与数据审计支持继续一个有界、重设计后的补充实验：

`ALLOW_BOUNDED_EQUAL_SUPPORT_OBSERVABILITY_AUDIT`

前提：

1. 所有新结果进入独立 manifest 和报告，不改写冻结产物；
2. 先建立 counterfactual registry，swap 明标 `IDENTITY_NEGATIVE_CLASS_POSITIVE`；
3. 四个 PV002-geometry vehicle-class-negative controls 完成硬约束和直接视觉复核；baseline 只计三个空间簇，完整一维参数包络只计两个严格簇，BG0010/BG0011 不得当作独立重复；
4. 四表示完全等支持；
5. pair set 固定且显式；
6. 双归一化并行；
7. 只增加局部方向组织、空间关系与拓扑两个结构族；
8. 当前五点网格只报告 `GRID_NONDOMINANCE_PATTERN`，所有正式参数状态保持 `NOT_IDENTIFIABLE`，不输出物理区间、单侧边界、winner 或排序；
9. 不运行潜在支撑重建。

若任一 parity、声明的 baseline/parameter-envelope cluster 与 overlap 契约、或 source-positive pair 投影契约失败，本轮退回实现审计，不得用旧绝对 NCC 填补。

## 9. 二次语义复盘与实验契约补强

在 runner 首轮静态复核中又发现五个会制造伪结论的实现风险，因此正式运行继续暂停，先补强契约：

1. 归一化失败原先会返回全零场并继续提取方向/连通量，可能把“无有效证据”伪装成方向完全一致、端点差为零。补强后失败帧的全部证据为 unavailable，失败 setting 不进入 Pareto。
2. pair 原先只按 frame gap、view diff 和可靠性冻结，没有在冻结前检查 common-valid 与 baseline NCC 有限性。补强后 membership reference 固定为 `CENTER_TRACKED_BODY + GT_DERIVED_UNSIGNED_BODY + FIXED_REFERENCE`，并显式记录公共有效像素、NCC finiteness、排除原因和 hash。
3. `TEMPORAL_REVERSE` 原先只有 notes 说明不适用，下游指标仍可能被误读为时间方向证据。补强后把 temporal correspondence 与 temporal direction 拆开：reverse 仅属于 correspondence mismatch control，unit、sampling、representation、pair、LOPO/LOFO、profile 和 observability 全链明确不提供时间方向证据。
4. Canny 输出原先被简称为 skeleton，且安慰剂坐标 x/y 容易被误称为 body long/short。补强后正式命名为 `CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON`；只有 `CENTER_TRACKED_BODY + GT_DERIVED_UNSIGNED_BODY` 的 x/y 可解释为 body long/short，其余均为 representation axes。
5. 固定参考路径原先把当前候选外围像素数写成 `background_sample_count`，但这些像素并未参与固定参考估计。补强后拆分为 `candidate_outer_pixel_count` 与真实 estimator sample count；固定路径明确标记 source-reference count unavailable，只有局部重估路径记录当前外围样本数。

同时补充受控扩展；新增 FX88 后 research-unit registry 从 20 个变为 21 个，但不改变研究问题、指标族或禁区：

- 所有正样本与反事实均分别运行 Raw-GT 和 Smoothed-GT 的 separate source-positive pair set，避免把平滑依赖隐藏在反事实之外；两套 pair 不是独立样本；
- unit registry 显式记录 scope limitation：swap 仅覆盖 PV002/PV003，背景均使用 PV002 冻结几何，temporal control 仅为 GM_RM017 within-thread correspondence replay；
- source-positive pair set 先冻结，反事实只按 frame intersection 投影，不得在目标区域重新择对；
- LOPO 与 LOFO 联合报告 frame leverage，但二者都不能把共享帧 pair 转换为独立样本；
- `CENTER_TRACKED_BODY` 相对 Cartesian/radial 的差值更名为 body-oriented-window increment，明确包含旋转各向异性窗口导致的源像素变化；
- Pareto 非支配值统一降格为 diagnostic grid-response pattern，正式参数状态全部为 `NOT_IDENTIFIABLE`，reported physical bounds 留空；
- long/short scale profile 在固定 `256×128` 网格下同时改变源像素密度和插值尺度，因此只代表 `WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED`，不代表物理尺度约束。

这些补强不会把结果升级为部署证据。即使全部实现检查通过，当前输出仍只能讨论 GT-conditioned、GT-discovery-proxy、8-bit display-domain 的登记与结构响应；不能宣称真实 optical-conditioned input 已执行，也不能讨论最终框、SAR-only 身份恢复、潜在车体支撑重建或自动标注。
