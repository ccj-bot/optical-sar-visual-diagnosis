# OTY2 S1-L 车体支撑归属：最小三坐标系 Casebook 直接审阅

日期：`2026-07-15`

工作名称：`S1-L Body Support Attribution and GT-Neighborhood Optimality Audit`

本报告只关闭最小三坐标系 casebook gate。它不判定最终 READY/PARTIALLY_READY/NOT_READY，不进入 S1-D，不生成自动标注、最终框、candidate、selector、ranking 或综合评分。

## 1. 研究结论

最小 casebook 支持一个受限但重要的结论：

> GM_RM017 三辆车辆线程中，至少一类车辆尺度横向带状响应在 GT-derived 无符号车体坐标中，比 world 和雷达径向/切向 crop 坐标表现出更强的跨帧重复性；固定世界强线背景则呈现相反的 world-coordinate 优势。

该结果支持继续做小范围、规则、对称的 GT 邻域扰动 pilot，但不支持把整个局部响应场判为车辆，也不支持 GT 已处于最优盆地。

限制同样明确：

1. 三辆 GM_RM017 的总体归属都仍为 `MIXED`，不是纯 `BODY_COHERENT`；
2. body 支撑熵并不总是最低，说明 body 对齐后仍包含间歇响应和背景混入；
3. GM_RM011:PV001 在三坐标系中不可识别，不能复现 GM_RM017 的清晰规律；
4. 车体中心、尺度和轴全部来自 GT，尚未证明对合理扰动稳健；
5. 固定背景对照只覆盖一种强线结构，且旧质量状态为 `insufficient_counterfactual_quality`；
6. 上游灰度映射、增益、插值和重采样链仍未冻结。

## 2. 直接视觉证据

### 2.1 GM_RM017:PV002

331-386 帧反复出现车辆尺度横向亮条带和间歇热点。进入车体坐标后，该条带被统一到长轴方向；在 crop 坐标中同一结构保持弧形或倾斜，并受到竖向亮线和裁剪边缘影响。

frame 310 是明确失败案例：Raw/Smoothed 中心差约 `56.21 px`，Smoothed 规范场落入不同结构，因此 Smoothed-GT 不能自动当作更真实状态。

结论：一类横向带状结构具有 body-coherent 候选性质，但整体场仍为 `MIXED`。

### 2.2 GM_RM017:PV003 heldout

heldout 线程中横向带状结构和中部热点在远隔帧再次出现。车体坐标复现的是“长轴对齐后重复性提高”的规律，不是逐帧完全相同的亮斑形态。固定竖线和背景仍进入局部场。

结论：heldout 部分复现 body-alignment 规律；总体为 `MIXED`。

### 2.3 GM_RM017:PV004 heldout

早期帧响应较弱，后续横向条带逐步显现；部分帧只有断续热点，末端存在十字样或竖向背景结构。车体坐标对主要带状支持有帮助，但优势弱于 PV002/PV003。

结论：heldout 再次部分复现，仍为 `MIXED`。

### 2.4 GM_RM011:PV001 cross-scene diagnostic

近场扇形弧、强热点和大范围世界结构控制了 world、crop 和 body 三种显示。车体坐标没有形成与 GM_RM017 同样清晰的单一车辆尺度支撑。

结论：`UNRESOLVED`；不得计入核心机制成功率或跨场景泛化。

### 2.5 固定世界强线背景

固定横线与中心强点在 world 坐标中保持固定。将 PV002 的移动裁剪/车体轨迹平移到该背景后，同一横线在 crop/body 中发生漂移、弯曲并离开中心。

结论：该对照为 `WORLD_COHERENT`，说明三坐标竞争至少能识别一种固定背景。但它不能证明所有车辆框内横条都属于车辆。

## 3. 三坐标系分离指标

下表仅列连续局部背景归一化场的相关性与支撑熵。指标分别报告，不形成加权总分；低熵本身不是车辆证据。

| research unit | representation | adjacent NCC median | similar-view nonadjacent NCC median | support entropy |
| --- | --- | ---: | ---: | ---: |
| GM_RM017:PV002 | world | 0.674 | 0.181 | 0.250 |
|  | Smoothed-crop | 0.784 | 0.292 | 0.404 |
|  | Smoothed-body | **0.826** | **0.574** | 0.431 |
| GM_RM017:PV003 | world | 0.648 | 0.192 | 0.278 |
|  | Smoothed-crop | 0.812 | 0.300 | 0.371 |
|  | Smoothed-body | **0.866** | **0.571** | 0.437 |
| GM_RM017:PV004 | world | 0.642 | 0.222 | 0.392 |
|  | Smoothed-crop | 0.709 | 0.271 | 0.371 |
|  | Smoothed-body | **0.762** | **0.429** | 0.377 |
| GM_RM011:PV001 | world | 0.937 | 0.644 | 0.583 |
|  | Smoothed-crop | **0.944** | 0.718 | 0.708 |
|  | Smoothed-body | 0.938 | **0.738** | 0.615 |
| fixed world background | world | **0.733** | **0.329** | 0.320 |
|  | Smoothed-crop | 0.631 | 0.094 | 0.259 |
|  | Smoothed-body | 0.648 | 0.229 | 0.340 |

GM_RM017 三辆车的 body 优势方向一致，固定背景的 world 优势方向相反。GM_RM011 没有同样的清晰分离，符合 `UNRESOLVED`。

world 使用固定完整轨迹画布，crop/body 使用动态规范场，因此 response-centroid grid 指标只能在各自 representation 内诊断，不能跨坐标族直接比较。上表采用的相关性和视觉支撑也不能单独决定车辆归属。

## 4. 当前 GT 邻域结论

当前只能说：

- 大部分 GM_RM017 GT 框位于能包含主要横向条带的合理车辆尺度区域；
- frame 310 证明 Smoothed-GT 可发生严重端点失配；
- 尚未生成中心、尺度和轴向扰动曲面；
- 尚未证明 GT 周围存在连续稳定盆地；
- 尚未发现可报告的系统性平移、缩放或旋转修正。

因此不得使用“GT 最优”“修正框”或“恢复真实框”措辞。

## 5. 对旧事件的影响

最小 casebook 没有升级任何旧事件。相反，它进一步表明：

- 同一局部场可以同时含 body-coherent 条带和 world/crop 背景；
- split/merge/switch 可能由这些混合结构、阈值拓扑和裁剪进入/退出共同产生；
- 在结构链完成坐标归属前，旧 `major_event` 仍不具备车辆结构事件语义。

## 6. GT 信息债务

| 当前输入 | 当前用途 | 未来非 GT 替代 | 状态 |
| --- | --- | --- | --- |
| GT 中心 | 规范场平移锚 | 光学方位走廊与时序状态 | `GT_DISCOVERY_ONLY; FUTURE_REPLACEABLE; DEPLOYMENT_SOURCE_NOT_READY` |
| Smoothed-GT | 裁剪/轨迹反事实 | 光学完整车辆线程 | 同上；frame 310 另标 `GT_PRECISION_DEPENDENT` |
| GT 长宽 | 线程参考尺度 | 车型先验或光学尺寸估计 | 同上 |
| GT 旋转角 | 180° 无符号长轴 | 光学姿态、运动轨迹或轴向估计 | 同上；无 front/rear 语义 |
| GT crop | 局部研究区域 | 光学约束的潜在车辆支撑 | 同上 |
| GT identity | 物理车辆研究单位 | 光学全局物理车辆身份 | 同上 |

## 7. Gate 决定

允许下一步执行：

> 仅对 GM_RM017:PV002 使用小范围、对称、可解释的中心/尺度/轴向扰动网格；固定后在 PV003/PV004 只读重放；同时运行固定世界背景和至少一种轨迹交换反事实。

下一步仍禁止：

- 大规模 candidate bank；
- 连续优化器输出唯一框；
- 加权总分或 ranking；
- GT IoU 决策；
- 时序潜在支撑重建；
- 最终阶段状态；
- S1-D 或自动标注。

## 8. 代码与产物

Formal Git-side products:

- `docs/OTY2_S1L_BODY_SUPPORT_ATTRIBUTION_AND_GT_NEIGHBORHOOD_OPTIMALITY_AUDIT_PROTOCOL.md`
- `reports/oty2/oty2_s1l_body_support_attribution_logic_audit_20260715.md`
- `tools/diagnostics/run_oty2_s1l_body_support_coordinate_casebook.py`
- `manifests/oty2/oty2_s1l_body_support_coordinate_frames.csv`
- `manifests/oty2/oty2_s1l_body_support_coordinate_competition.csv`
- `manifests/oty2/oty2_s1l_body_support_casebook_manifest.csv`
- `manifests/oty2/oty2_s1l_body_support_case_reviews.csv`

Temporary arrays and PNGs remain outside Git under:

`D:/profile/research/workspace/output/oty2_s1l_body_support_attribution_20260715`

## 9. 阶段与 Git 状态

- Final S1-L body-support state: not assigned.
- S1-D allowed: `false`.
- Automatic annotation allowed: `false`.
- GT-neighbourhood perturbation: not yet run at this report point.
- Latent body-support reconstruction: not run.
- Commit: not created; the research closure is incomplete.
