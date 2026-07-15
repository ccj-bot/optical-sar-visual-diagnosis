# OTY2 S1-L 车体支撑归属与 GT 邻域最优性：实现前逻辑审计

日期：`2026-07-15`

工作名称：`S1-L Body Support Attribution and GT-Neighborhood Optimality Audit`

本文件只记录实现前阅读与逻辑审计，不宣布进入 S1-D，不生成自动标注、最终 SAR 框、candidate bank、selector、ranking 或综合评分。

## 1. 冻结仓库核验

- repo root：`D:/profile/research/optical-sar-visual-diagnosis-sar-foundation`
- branch：`feature/oty2-sar-gt-structure-foundation`
- frozen HEAD：`8519696ece0760e8af6d85a655773aaedae5a0c0`
- upstream：`origin/feature/oty2-sar-gt-structure-foundation`
- fetch 后 local/remote divergence：`0/0`
- worktree：clean
- `stash@{0}`：存在；未读取、应用、删除或修改
- Python：`D:/MINICONDA/envs/py311/python.exe`

## 2. S1-L 已回答的问题

S1-L 的冻结状态是 `S1L_CONTINUOUS_STRUCTURE_PARTIALLY_READY`。它已经支持：

1. 8-bit SAR 灰度显示域中存在局部峰、紧凑岛、延展脊和背景连接结构；
2. 部分观察跨固定阈值、跨三种归一化形式并跨帧持续；
3. 原始 GT、平滑 GT、全局像素、阈值变化和部分背景伪线程已被纳入审计；
4. GM_RM017 两辆 heldout 车辆复现了部分通用形态与持续性；
5. 背景线程能够复现部分稳定持续性，因此无条件局部形态和持续性不具有车辆特异性。

这些结果描述的是处理后灰度显示域响应，不是物理散射中心、车辆部件、车辆响应 Mask 或自动标注依据。

## 3. S1-L 未回答的问题

S1-L 尚未回答：

1. 稳定响应主要随车辆共同运动、固定在世界背景，还是固定在裁剪坐标；
2. 同一响应是否在真正车体长轴/短轴坐标中更稳定；
3. GT 附近是否存在连续、跨帧稳定的相对最优盆地；
4. 是否存在比 GT 更合理且可解释的系统性中心、尺度或轴向修正；
5. 间歇响应能否累积成潜在车体支撑，而不是当前亮响应的平均包络；
6. split、merge、dominant switch 是否属于车辆结构动力学；
7. 当前规律是否超越困难背景、轨迹交换和成像链反事实；
8. 当前机制是否具备未来非 GT 运行时替代来源。

## 4. 当前坐标的真实语义

当前 S1-L 保留全局显示像素、扇形 `r_px/theta_deg`、Raw-GT local、Smoothed-GT local 和 GT-normalized local，但 Raw/Smoothed local 的轴由雷达原点到 GT 中心的径向单位向量及其切向垂线定义。

因此当前 local coordinate 是：

> 以 GT 中心为平移锚、随中心更新的雷达径向/切向局部显示坐标。

它不是：

- 车体长轴/短轴坐标；
- 旋转对齐的车体规范坐标；
- 统一物理尺度坐标；
- 已保留雷达方向的车体坐标；
- 可区分 front/rear 的有向车辆坐标。

Raw/Smoothed GT 旋转框角度虽然已经保存，但只参与旋转框角点和径向/切向外接范围计算，没有定义规范场的长轴方向。

## 5. 车体轴和尺度可用性

### 5.1 可用信息

- 每帧有旋转 GT 框中心、宽、高和角度；
- GM_RM017:PV002/PV003/PV004 的框长宽比中位数约为 `2.09-2.23`；
- 三辆 GM_RM017 长线程的无符号长轴角在大部分帧内较连续，围绕约 `176-178 deg`；
- GM_RM011:PV001 也存在连续长轴趋势，但后段轴向变化更大；
- 所有源灰度图都有内容哈希和固定 fan-coordinate lineage。

### 5.2 缺失信息

当前正式字段没有：

- 显式无符号车体长轴/短轴单位向量；
- 轴向可靠性和失败原因；
- 线程统一参考长宽；
- 车体规范原始强度场；
- 车体规范局部背景归一化场；
- 规范配准有效 Mask；
- 雷达方向在车体坐标中的向量；
- 相对观测角代理；
- 规范场边界缺失比例；
- 配准可靠性。

绝对米制尺度仍不可用：442 条 GT 的米制长宽字段全部为空，上游成像网格、重采样和显示缩放链未冻结。历史 `0.03 m/pixel` 不能作为全图统一笛卡尔尺度、真实分辨率或车辆结构分辨率。

### 5.3 可执行边界

最小 casebook 可以使用 GT 旋转框推导 180° 无符号长轴，并用每个物理车辆线程的稳健参考长宽建立无量纲规范坐标。该坐标必须标记为：

- `GT_DISCOVERY_ONLY`
- `FUTURE_REPLACEABLE`
- `DEPLOYMENT_SOURCE_NOT_READY`

如果轴向只在高精度 Smoothed-GT 下成立或对小扰动立即失效，还必须标记 `GT_PRECISION_DEPENDENT`。

## 6. 可用线程与研究单位

核心最小审计：

- `GM_RM017:PV002`：机制发现长线程；
- `GM_RM017:PV003`：heldout 长线程；
- `GM_RM017:PV004`：heldout 长线程；
- `GM_RM011:PV001`：仅跨场景诊断，不计入跨场景泛化或核心成功率。

短线程：

- `GM_RM011:PV002`：7 帧，仅格式、变换和短时反例；
- `GM_RM019:PV001`：3 帧，仅格式、变换和极短时反例。

统计单位必须是物理车辆、连续时间窗口和独立背景区域。3194 条观察、4279 条关系、2384 个事件和 9536 行审计记录不得作为独立样本数。

## 7. Raw-GT / Smoothed-GT 风险

Raw/Smoothed 中心通常接近，但不是普遍无风险。现有正式字段中至少有 6 帧中心差超过 10 px，3 帧超过 20 px；其中：

- `GM_RM017:PV002` frame 310 的中心差约 `56.21 px`；
- 两个 GM_RM011 B-tier 片段存在约 `63-65 px` 差异。

现有 rolling median 按“可用观察位置序列”滑动，不按真实帧间隔建模，也没有端点专门处理。Smoothed-GT 只能作为一种裁剪/轨迹反事实，不能自动升级为更真实的车体状态。

## 8. 旧事件定义的降级

所有旧事件在本轮开始时统一降级为“显示域对应或组件拓扑假设”。原因包括：

1. `split/merge` 由固定阈值组件和匹配代价邻域触发，不等于车辆或车辆部件分裂/合并；
2. `dominant_component_switch` 依赖相对强度最大组件，不等于车辆主体切换；
3. `global_motion_consistent` 的最终事件标签比较位移模长，未单独验证方向、车体坐标和世界固定背景；
4. `unresolved_correspondence` 仍会被旧 `major_event` 字段保留，不能作为升级证据；
5. 2384 个事件的 `background_like` 全部为 false，原因是该字段只继承组件是否连接裁剪边界，不是世界背景归属审计；
6. 四类 event counterfactual 对每个事件复用同一组 `evidence_values`，没有在四种条件下独立重建结构或重算对应；
7. 旧背景伪线程只覆盖开发 A-tier，并且 16 个中只有 10 个满足完整质量契约；
8. 强度增减、birth/death 和组件爆发尚未排除全局灰度增益、显示映射、局部归一化和边界变化同步。

在三坐标系归属、困难背景和成像链审计完成前，不使用旧 `major_event=true` 作为车辆候选结构事件证据。

## 9. 成像链结论

已确认：

- gray 为 8-bit RGB 容器且三个通道相同；
- pseudocolor 是同空间帧的 8-bit 显示变换；
- gray/pseudocolor 按帧号对齐；
- gray 不保留相位，pseudocolor 不增加独立物理观测；
- 当前 PNG 之后没有额外旋转或翻转。

未确认：

- 是否逐帧自动拉伸；
- 上游灰度映射是否固定；
- 原始幅度到 8-bit 的饱和、量化和增益规则；
- 上游插值、重采样、crop/resize 链；
- 显示域 ridge 与成像/插值处理的关系。

核心线程中全局 p50/p95/p99 随帧明显变化，说明全局显示增益或场景强度状态不是常数。未完成同步审计前，只能使用“显示域结构”或“灰度幅度域结构”措辞。

## 10. 实现决定

允许进入：

1. 最小 protocol；
2. GT-derived 无符号车体规范坐标；
3. 世界、裁剪、车体三坐标并列 casebook；
4. 车辆与固定世界背景的同合同对比；
5. 逐 case 中文直接视觉判断。

暂不允许扩大到：

- GT 邻域大批量扰动；
- 连续优化；
- 相对最佳参数输出；
- 时序潜在车体支撑重建；
- 旧事件升级；
- 最终阶段 READY/PARTIALLY_READY/NOT_READY 判定。

只有最小 casebook 显示至少一个结构族在车体坐标中与世界/裁剪坐标形成可解释差异后，才继续中心、尺度和轴向扰动。
