# OTY2-S1X 光学条件下的 SAR 时序联合支撑恢复报告

日期：`2026-07-17`

英文名称：`OTY2-S1X Optical-Conditioned Joint SAR Temporal Support Recovery`

## 1. 四个项目级问题的直接答案

### 1.1 不使用待评价 SAR 参考，仅使用真实光学条件，是否恢复了人眼可见的车辆 SAR 响应序列？

**是。** 发现窗口 `GM_RM017:PV002 / SAR 330–350` 的 `21/21` 个参考可用帧都有冻结 joint support 与目标区域相交；无参考盲审确认壳层中持续存在近水平可见响应。平均 target coverage 为 `0.1096`，平均 precision 为 `0.6243`。该结果是可见响应序列，不是完整车体或精确框。

### 1.2 相比光学单独壳层，SAR 是否排除了实际背景或缩小了支撑范围？

**是，以支撑收缩和框外面积减少成立。** 发现窗口平均 shell contraction 为 `0.9465`，重放窗口为 `0.9606`；joint precision 分别提高到 `0.6243` 和 `0.9415`，两窗其他车辆 overlap 均为 `0`。自动 `BACKGROUND_EXCLUDED_REGION` 本身仍偏保守、面积为零，主要强背景在 optical shell 阶段已被排除，因此本轮不能把“背景分类器完备”作为成功结论。

### 1.3 整段时序联合是否比逐帧处理更稳定，特别是在弱响应帧？

**部分成立。** 两条路径都没有整帧断裂，所以 joint 没有新增 frame-level recovery。joint 将 discovery centroid-jump median 从 `13.743 px` 降到 `11.469 px`，将 replay 从 `4.911 px` 降到 `3.707 px`；目标参考区域在 `21/21` 和 `54/54` 帧都有 weak-maintained pixels。结论是“跳动更低、弱像素连续性得到维持”，不是“恢复了逐帧路径完全缺失的帧”。

### 1.4 冻结规则是否在至少一个独立窗口复现？

**是，部分复现。** 不修改 inference config、校准或阈值，在 `GM_RM017:PV003 / SAR 338–391` 的 `54/54` 个参考帧都得到目标相交；平均 target coverage `0.1198`，precision `0.9415`。该窗口由 P1-E full-visible optical lifecycle 选择，不按 SAR 参考视觉效果挑选。

## 2. 阶段结论

最终项目状态：

`OTY2_S1X_PROJECT_LEVEL_CLOSED_LOOP_COMPLETED`

S1-D 决定：

`SMALL_SCALE_S1D_ALLOWED_WITH_RESEARCH_PROXY_INPUTS`

原因是本轮满足：

1. 真实光学研究条件下恢复连续 SAR 可见响应；
2. 相比 optical-only shell 产生明确支撑收缩和 precision 增量；
3. 固定规则在另一辆物理车辆上部分复现；
4. 评价行中没有其他车辆 overlap，也没有跨主体边界。

该准入不等于部署 READY。P1-E identity/reference bbox 是 optical-only benchmark，PV004 calibration 是单车/单场景研究代理，automatic annotation 仍为 `NOT_READY`。

## 3. 输入冻结与数据血缘

### 3.1 Git 与环境

- repository：`D:/profile/research/optical-sar-visual-diagnosis-sar-foundation`；
- branch：`feature/oty2-sar-gt-structure-foundation`；
- frozen start HEAD：`fb69df0bd050106a9cad62f2d8cc50e5c6750319`；
- start upstream divergence：`0 0`；
- start worktree：clean；
- existing `stash@{0}`：保留且未读取、应用、删除或修改；
- Python：`D:/MINICONDA/envs/py311/python.exe`，`3.11.14`；
- PowerShell：Windows PowerShell `5.1.26100.8875`；`pwsh` 不存在，未升级环境；
- `old_work` runtime dependency：none。

### 3.2 光学条件

`manifests/oty2/oty2_s1x_optical_condition_frames.csv` 共 `75` 行：

- discovery：`21`；
- frozen replay：`54`。

输入包括 P1-E canonical identity、逐帧 bbox/visibility、P0 24/50 时间关系、光学 depth sidecar、PV004-only calibration 和 fixed fan geometry。完整字段血缘见：

`manifests/oty2/oty2_s1x_optical_condition_input_lineage.csv`

明确未就绪项包括 automatic runtime identity、depth generator/absolute unit、cross-scene mapping、SAR metric grid、raw amplitude/complex/IQ/ADC 和固定 grayscale mapping。

### 3.3 独立校准

校准车辆：`GM_RM017:PV004 / SAR 352–394 / optical 169–189`，共 `43` 行。

- theta from optical centre x：median/P90/max absolute error `0.3945 / 0.8129 / 1.1452 deg`；
- radius from optical bbox height：median/P90/max `4.5495 / 11.9837 / 17.8973 px`；
- depth proxy to radius：median/P90/max `13.9758 / 33.2599 / 51.3702 px`。

目标车辆 PV002/PV003 不进入校准拟合。由于 bbox-height 与 depth proxy 在目标输入上明显冲突，本轮在 inference 前实施了唯一一次最小修复：不选择任一单点，而是将两种 radial prediction 及其 calibration residual 合并为显式宽区间。该修复发生在查看目标评价结果之前，不是 posthoc tuning。

## 4. 方法

### 4.1 Optical-only baseline

每个 SAR 帧从光学 canonical bbox 和 24/50 插值获得：

- theta centre 与至少 `±8 deg` 区间；
- bbox-height/depth-proxy union radial interval，至少 `±120 px`；
- `±35 deg` 无符号方向范围；
- 宽 response size range；
- visibility-conditioned uncertainty。

输出是 `OPTICAL_ONLY_CONDITION_SHELL`，不读 SAR 灰度，不是 final box。

### 4.2 SAR-only blind diagnostic

在完整 imaging-valid fan 中，以多 tile phase correlation 建立共同运输，随后形成 full-fan temporal response objects。它不使用 optical condition，不承担身份。发现/重放分别产生 `17` 和 `6` 个 persistent temporal objects；平均 target coverage 仅 `0.0321` 和 `0.0202`，显示全场背景歧义明显。

### 4.3 Optical+SAR joint method

两窗都使用同一配置 SHA256：

`e91c6ee555601d61f6d53bd9d17f069d8c1af6a25a94ed39250a33d62b59346e`

处理顺序：

1. 从 full valid fan 的多个 tile 估计 adjacent common-scene translation；
2. 将 SAR、optical shell 和 valid mask 同时稳定到窗口首帧；
3. 在 shell/context 中分别保留 local robust-z、temporal frequency、component shell-extension、背景连接、weak evidence；
4. 用逻辑约束形成 persistent core、intermittent region、background region、mixed region；
5. 用前后 `±2` 帧和当前 weak response 维持弱像素；
6. 同时输出 per-frame independent path，便于时序比较。

没有 candidate bank、加权总分、selector/ranking、winner、唯一中心或最终框。

## 5. 共同运输与无参考视觉审阅

### 5.1 Discovery

- cumulative transport：`dx=126.516 px`, `dy=-0.742 px`；
- pair median：`dx=6.342 px`, `dy=0.003 px`；
- persistent core：`1272 px`；
- intermittent region：`1308 px`；
- mixed：`566 px`；
- mean shell area：`37942.5 px`；
- mean joint support area：`2031.9 px`；
- empty joint frames：`0`。

盲审确认深色轿车光学线程连续，shell 内持续存在近水平主响应带，上部短段更间歇。主竖线和扇形弧大多在 shell 外。

### 5.2 Replay

- cumulative transport：`dx=335.616 px`, `dy=-4.468 px`；
- pair median：`dx=6.323 px`, `dy=-0.092 px`；
- persistent core：`1205 px`；
- intermittent region：`870 px`；
- mixed：`104 px`；
- mean shell area：`42083.1 px`；
- mean joint support area：`1640.3 px`；
- empty joint frames：`0`。

盲审确认白色 SUV 的另一条 optical lifecycle 上，同一冻结规则仍保留集中横向响应带；背景布局和轨迹不同，但没有重新选择规则。

## 6. 事后评价

| metric | discovery PV002 | replay PV003 |
| --- | ---: | ---: |
| reference frames | 21/21 | 54/54 |
| optical shell target coverage | 0.5898 | 0.6990 |
| optical shell precision | 0.1789 | 0.2133 |
| joint target coverage | 0.1096 | 0.1198 |
| joint precision | 0.6243 | 0.9415 |
| shell contraction | 0.9465 | 0.9606 |
| joint reference-hit frames | 21/21 | 54/54 |
| other-vehicle overlap pixels | 0 | 0 |
| independent/joint break episodes | 0 / 0 | 0 / 0 |
| independent/joint centroid jump median px | 13.743 / 11.469 | 4.911 / 3.707 |
| weak-maintained target frames | 21/21 | 54/54 |
| SAR-only target coverage | 0.0321 | 0.0202 |

target coverage 不应解释为完整框 recall：joint output 只表达可见 response support。事后图显示主支撑稳定落在参考框中下部，未覆盖完整车体，符合输出契约。

## 7. 失败点、限制与已执行修复

### 7.1 已执行的最小修复

`single-point radial proxy conflict -> explicit multi-proxy radial interval`

该修复由 optical bbox-height 与 depth proxy 的输入冲突触发，在 inference 和 evaluation 前完成。没有根据目标 IoU、目标中心或评价结果调区间。

### 7.2 未解决限制

1. P1-E 是 benchmark-only；还没有自动 runtime canonical vehicle thread。
2. calibration 只有 PV004、GM_RM017 和左侧主导 pose；不是跨场景标定。
3. depth sidecar generator 与绝对尺度未解析。
4. automatic background region 分类偏保守；主要背景收益来自 shell 几何排除和最终 support 收缩。
5. per-frame path 没有断帧，所以本轮未证明 frame-level rescue，只证明 lower jitter 与 weak-pixel maintenance。
6. replay 是同场景其他车辆，不是 GM_RM011/GM_RM019 cross-scene generalization。
7. 8-bit display domain、metric grid 和 upstream grayscale mapping 限制仍在。

这些限制不撤销项目级可见响应闭环，但限制部署、完整车体和跨场景结论。

## 8. 泄漏、冻结、重放与验证

- inference config forbidden-path hits：`0`；
- condition forbidden columns：`0`；
- target dependency rows：`0`；
- freeze manifest rows：`17/17` hash PASS；
- inference outputs modified by evaluator：`false`；
- rule update from evaluation：`false`；
- fixed-input replay：`PASS`；
- discovery/replay NPZ：逐数组一致且文件 SHA256 一致；
- blind review pages：逐像素一致；
- frame-state rows：除 Git 外输出路径外完全一致；
- SAR-only object rows：完全一致。

## 9. 产物

Git 内：

- 项目理解与执行契约；
- input preparation / inference / evaluation configs；
- independent calibration config；
- optical-condition adapter、joint inference、evaluation、replay checker、validator；
- input lineage、75-frame optical conditions、frame states、SAR-only objects、freeze manifest；
- blind/posthoc visual review manifests；
- per-frame/window evaluation、project answers、stage conclusions；
- 中文 blind/posthoc review 与本正式报告。

Git 外：

`D:/profile/research/workspace/output/oty2_s1x_20260717`

包含 frozen NPZ、blind PNG、posthoc PNG 和 window summaries。固定输入重放位于：

`D:/profile/research/workspace/output/oty2_s1x_20260717_replay_check`

## 10. Git 交付边界

- start HEAD：`fb69df0bd050106a9cad62f2d8cc50e5c6750319`；
- final delivery HEAD、commit message、push status、final divergence 和 worktree 状态在完成 commit/push 后由 session handoff 报告；
- 本报告属于 delivery commit，不能在不产生自引用循环的情况下嵌入其自身最终 commit hash。
