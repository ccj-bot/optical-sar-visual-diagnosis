# OTY2-S1D0 S1X 算法审计与多场景执行契约

日期：`2026-07-17`

冻结起始提交：`70f3cbbd62eb1889bcf7537ae27cd7f6842680ec`

本轮名称：`OTY2-S1D0 多场景生命周期驱动的 SAR 可见响应状态探索`

英文名称：`OTY2-S1D0 Multi-Scene Lifecycle-Gated SAR Visible Response Dynamics`

## 1. 本轮与 S1X 的关系

S1X 已经完成了第一次目标参考隔离的光学条件 SAR 可见响应子集恢复闭环。其正式能力边界是 `VISIBLE_RESPONSE_SUBSET_RECOVERED`，不是完整车体、唯一中心、唯一框、车辆专属散射结构或自动标注。本轮不改写 S1X 报告、配置、manifest、NPZ 或评估结论，只从冻结提交继续增加生命周期入口控制、动态响应表示和多场景重放。

S1D0 的研究单位仍是由 P1-E optical-only benchmark 确认的一条 canonical physical vehicle lifecycle。光学拥有身份、准入、退出和主体切换；SAR 只在该身份的条件壳层内组织可见响应，不创建或切换身份。

## 2. S1X optical-only shell 的实际生成

`tools/diagnostics/run_oty2_s1x_prepare_optical_conditions.py::build_conditions()` 读取：

- `oty2_p1e_canonical_vehicle_frame_states.csv` 的 optical reference bbox 与 visibility；
- `oty2_p0_hard_sync_sar_to_optical.csv` 的左右 optical frame 和插值比例；
- optical depth sidecar 的 bbox 内中位数与 MAD；
- `GM_RM017:PV004` 独立校准输出。

逐帧处理为：

1. 在 24 fps 的左右 optical state 之间线性插值 bbox；
2. 由 bbox centre-x 经 `theta_from_optical_center_x` 生成 `predicted_theta_deg`；
3. 分别由 bbox height 和 depth proxy 生成两个 radial prediction；
4. `min(two predictions)-allowance` 到 `max(two predictions)+allowance` 形成显式宽 radial interval；
5. partial/occluded 状态乘以固定 uncertainty multiplier；
6. 写出 `predicted_theta_deg/theta_half_width_deg/predicted_radius_px/radial_half_width_px`。

`tools/diagnostics/run_oty2_s1x_joint_temporal_support.py::condition_shell()` 只把以上四个方位—径向字段传给 `annular_sector_mask()`。因此 S1X optical-only shell 是 fan-polar annular sector prior，不是 final location，也不是完整车辆框。

## 3. S1X response support 的实际生成

### 3.1 共同场景运输

`estimate_pair_transport()` 在完整 `imaging_valid_mask` 的 `3×4` tile 上做 high-pass phase correlation，丢弃低响应或过大位移的 tile，再用有效 tile 位移中位数形成 pair transport。`build_transports()` 累积该位移。S1X 没有显式排除同帧所有 active optical shells，也没有独立 holdout tile 残差输出。

### 3.2 Independent support

`temporal_joint_support()` 对每帧：

1. 将 shell、扩张 context 和 SAR 灰图共同稳定到首帧坐标；
2. 优先用 `context & ~shell` 的像素估计局部 median/MAD；
3. 计算 robust-z；
4. 以 `local_positive_robust_z=2.5` 形成 positive mask；
5. `frame_response_components()` 保留与 shell 相交且跨出 shell 比例低于 `background_outside_shell_fraction=0.55` 的连通结构。

该结果写为 `independent_stack`。它不是单帧候选框，也没有排序或 winner。

### 3.3 Persistent core 与 intermittent

`temporal_joint_support()` 在整个固定窗口的稳定坐标中计算 positive frequency：

- `persistent_core`: frequency 大于 `0.55`，且不属于 background frequency，满足整窗 shell-presence gate；
- `intermittent`: frequency 位于 `0.20–0.55`，且位于 persistent core 的固定邻域内；
- `mixed`: 达到 intermittent frequency，但不属于 core/intermittent/background 的剩余响应。

这四类是全窗口静态图，不表达自然 entry、exit、migration、split 或 merge。

### 3.4 Weak maintenance 与 joint support

对第 `t` 帧，S1X 在 `[t-radius,t+radius]` 内对 independent support 求并集。若当前像素属于全窗 `persistent_core`、当前 independent 不存在、邻帧存在且当前 robust-z 高于 `0.8`，则写为 `temporally_maintained_weak`。最终 `joint_stack` 是：

```text
independent
OR weak
OR (intermittent AND current positive)
```

再与当前 shell 相交并排除 `background_region`。因为邻域同时含过去和未来，原 S1X weak maintenance 是 offline bidirectional smoothing，不是 causal runtime state。

## 4. 哪些 optical 条件实际参与推理

实际进入 mask 构造的字段只有：

- `predicted_theta_deg`；
- `theta_half_width_deg`；
- `predicted_radius_px`；
- `radial_half_width_px`。

`optical_visibility_state` 在 preparation 阶段通过 uncertainty multiplier 间接影响 shell 宽度，但 inference runner 不再读取它改变规则。`canonical_vehicle_id/window_id` 只承担分组和 provenance。

以下字段已生成但没有被 `run_oty2_s1x_joint_temporal_support.py` 主恢复逻辑读取：

- `unsigned_axis_center_deg`；
- `unsigned_axis_half_width_deg`；
- `response_length_min_px/max_px`；
- `response_width_min_px/max_px`；
- optical bbox、width、height 与 bottom contact；
- optical depth proxy 与其逐帧 delta；
- theta/radius delta；
- scale/depth trend。

其中 optical bbox 只在 blind review 页画框；方向和尺度字段没有参与 component acceptance、background rejection 或 temporal relation。

## 5. S1X 背景排除的实际定义

`frame_response_components()` 只把“与 shell 有交集、但至少 55% 面积位于 shell 外”的 positive component 写入 `background_stack`。`background_region` 再要求该类跨壳层结构在时间上达到固定频率。

因此 S1X 能处理的是大型 shell-crossing persistent background。它不能充分处理：

- 完全位于 shell 内的固定强结构；
- 与车辆响应混合但没有大面积跨出 shell 的结构；
- 全场显示增益共同变化；
- 在不同 lifecycle state 中由相邻车辆壳层重叠产生的归属歧义。

“没有大部分跨出 shell”只表示尚未被该背景规则否定，不能自动等同于车辆所有权。

## 6. 为什么 S1X 适合作为保守响应提取器

S1X 具有以下可继承性质：

- target reference 不进入 inference；
- optical shell 保留明确 uncertainty interval；
- local median/MAD 避免使用单一绝对灰度阈值；
- 不建立候选框库、加权总分、selector 或 unique box；
- 响应可以为空、间歇、混合或弱维护；
- frozen inference、blind review 和 posthoc evaluator 是不同入口；
- fixed-input replay 已证明确定性。

所以它适合作为“在宽光学条件内保守提取可见 response subset”的基础设施。

## 7. 为什么 S1X 不能直接表示自然生命周期和动力学

1. `target_windows` 手工固定，entry/exit 不是由 P1-E lifecycle 和 P0 map 自动生成。
2. 整窗 `persistent_core` 会把进入、退出、迁移、增强、减弱、split 和 merge 压成一张静态 mask。
3. symmetric weak maintenance 使用未来帧，不能代表 causal state。
4. transport 没有排除所有 active/provisional shells，车辆响应可能污染全场位移。
5. axis/length/width 条件没有进入 component relation。
6. shell 内 persistent background 缺少独立类别。
7. 同时活跃 identity 的 shell overlap 没有显式 `IDENTITY_AMBIGUOUS_OVERLAP`，也没有 closed identity reactivation 检查。

## 8. 本轮最小修正

本轮不修改 S1X 冻结阈值；新版本以独立 S1D0 runner 实现以下最小结构修正：

1. 由 P1-E entry/exit 和 P0 map 自动生成 pre-roll、lifecycle 与 post-roll；
2. 建立 `ABSENT → ENTERING_PROVISIONAL → ACTIVE_CONFIRMED/ACTIVE_WEAK_OR_OCCLUDED → EXITING → CLOSED`；
3. transport phase tiles 排除当前全部 active/provisional shells，并保留 fit/holdout 统计与冻结背景 fallback；
4. 每个响应 component 分开记录 axis、length、width、shell membership、background connectivity 与 identity overlap，不压成总分；
5. 增加 shell-inside persistent background 与 global-gain counterfactual；
6. 同时保留 current、sliding persistent、lifecycle persistent、bounded maintenance 和 dynamic birth/decay；
7. 分开输出 `CAUSAL_FORWARD_STATE` 与 `OFFLINE_BIDIRECTIONAL_STATE`；
8. 建立一对多/多对一 response graph；
9. 加入两种只使用 optical geometry 和冻结 joint area 的 equal-area baseline；
10. 在推理、线程角色和输出全部冻结后，才建立少量 visible-response reference 并独立评价。

方向或尺度不可观测时只标记 `DIRECTION_UNRESOLVED/SCALE_UNRESOLVED`，不删除弱响应。只有明确 shell 外或连接到 persistent background 的结构才优先否定。多 identity overlap 保留多解，不产生 winner。

## 9. 保持冻结的 S1X 产物

以下 S1X 内容不修改：

- `configs/oty2/oty2_s1x_*.json`；
- `manifests/oty2/oty2_s1x_*.csv`；
- `reports/oty2/oty2_s1x_*_20260717.*`；
- `tools/diagnostics/oty2_s1x_common.py`；
- `run_oty2_s1x_prepare_optical_conditions.py`；
- `run_oty2_s1x_joint_temporal_support.py`；
- `run_oty2_s1x_evaluate_frozen_outputs.py`；
- S1X Git 外冻结 NPZ、blind review 和 replay-check 目录。

S1D0 通过新文件继承函数语义，不回写 S1X freeze manifest，也不根据 S1D0 评价结果调整 S1X 阈值。

## 10. 防止退回候选工程或局部审计

- inventory 覆盖 GM_RM011、GM_RM017、GM_RM019 全部 22 条 canonical lifecycle；
- 线程选择只使用 optical lifecycle、bbox/depth availability、shell validity、scene role 和无目标参考的直接审阅；
- 推理单位是 identity lifecycle state thread，不是每帧候选；
- response graph 允许多 component 和多解，不排序、不强制 winner；
- equal-area optical baseline 在 posthoc evaluator 中单列，不形成综合分；
- 完整 SAR GT 只作冻结后的上下文评价；visible-response reference 与完整 GT 分开存储；
- 只有恢复机制通过 equal-area optical baseline 和 visible-response reference 入口控制后，才允许记录 S1-D response events；
- 至少执行一个不同场景 frozen replay、一个自然 entry/exit case 和一个 GM_RM011/GM_RM017 多车压力 case。

## 11. 停止条件

如任一目标 SAR reference 路径进入 inference、线程选择使用目标 GT、发现线程后修改核心状态定义、产生 candidate bank/ranking/unique box，立即停止并判定边界失败。

如 joint dynamic support 不优于 equal-area optical baseline，停止物理解释，只允许一次明确版本化的最小修复并完整重放。跨场景 mapping failure 与 response-dynamics failure 必须分开记录。
