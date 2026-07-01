# Algorithm Notes - 2026-07-01

以下记录旧阶段可继承的算法机制。本文不是 selector 设计，也不是 A008 scoring 设计。

## 1. Fan-Polar 到 Display-XY

SAR 工作空间按 fan-polar 理解。`heading` 字段只是 display-XY storage-axis convention，不是车头方向。

给定 fan center `(Cx, Cy)`、range `r`、azimuth `az`、cross-range offset `cross`：

```text
x = Cx + r * sin(az) + cross * cos(az)
y = Cy - r * cos(az) + cross * sin(az)
```

当前三场景共享的基线参数来自旧 mapping correction：`Cx=1154.0`，`Cy=1330.6`，`radius_px_max=1332.7`，`azimuth_k=0.0875154`，`azimuth_b=-40.413555`，`theta_offset_deg=0.0`。

## 2. Candidate Delta

候选相对 runtime prior 的偏移以 fan-polar 差值表达：

```text
delta_r = r - pred_r
delta_cross = cross - pred_cross
delta_az = wrapped_angular_delta(az, pred_az)
```

`delta_az` 必须做角度环绕，建议归一到 `[-180, 180)` 或等价范围。delta 是诊断字段，用来解释候选相对 prior 的偏移，不应直接变成硬阈值。

## 3. Runtime Prior 来源

旧阶段候选输入层的 runtime prior 主要来自：

- `factor_inference_candidate`
- `base_candidate`
- `visible_support_candidate`
- `factor_topk_candidate`

这些来源构成 candidate input construction，不等于可靠性确认。`candidate_source_family` 是 provenance，不是 active selector rule。

## 4. Wedge Mode

Wedge mode 以 fan-polar 局部扇形窗口检查 SAR gray evidence。

- range window 以 `pred_r` 和 `range_prior_sigma` 为核心。
- 当 visible risk 较高、边缘可见、近底部局部可见或 prior 不稳定时，range window 可作为 audit 扩宽，但扩宽逻辑必须记录原因，不能隐式变成 threshold。
- SAR gray profile 在候选扇形或局部 wedge 内采样，沿 range 聚合强度或结构响应。
- `peak` 是 profile 中局部最大响应位置。
- `compactness` 描述响应是否集中在有限 range 范围内。
- `prominence` 描述主峰相对邻域/background 的突出程度。
- `posterior_score` 可以组合 prior proximity、peak prominence、compactness、visible risk penalty 等 audit feature。
- `posterior_score` 只能作为 audit/tie-break feature，不是 formal selector score。

## 5. Ray Mode

Ray mode 沿 `pred_az` 方向读取 range profile。

- profile 以 `pred_az` 为主轴，检查 SAR peaks 是否支持 `r_pred` 附近或 track/range 修正位置。
- 可比较的 range 量包括 `r_opt`、`r_pred`、`r_track`、以及从 SAR peaks 得到的候选 `r_peak`。
- `opt_score` 描述 optical range prior 的一致性。
- `pred_score` 描述候选与 `r_pred` 的一致性。
- `track_score` 描述候选与短时 track 推断的 range 一致性。
- `sar_peak_score` 描述 SAR profile 主峰支持。
- `posterior_score` 是 audit feature，用于解释多来源 range cue 的相对关系。
- `extreme_range_shift` 指候选 range 相对 `pred_r` 或短时 track range 出现大幅偏移。它可能指出 optical prior 错位，也可能是 SAR clutter 或身份混淆风险，因此不能单独作为强规则。

## 6. Signed Mode

Signed mode 使用邻近帧 wedge/ray 的 `delta_r` 方向作为弱时序证据。

- 对邻近帧候选的 `delta_r` 做 `pos` / `neg` / `near` / `artifact` vote。
- 如果连续邻近帧显示同向 escape，则可形成 signed `escape_direction` 解释。
- `artifact` vote 用于隔离明显不可信的局部 peak 或身份混淆。
- 当前 signed 只是弱时序证据。它可以解释 range 修正方向，但不是强 selector rule。
- C1.3/C1.4 的结果表明 GM_RM019 缺少 explicit same-target runtime track id，所以 signed evidence 仍停留在 partial audit 层。

## 7. Structural Candidates

Structural candidates 是 mode rows 到 candidate boxes 的结构化转换，不是后验 oracle 改写。

- `wedge_joint_candidate`: 从 wedge mode row 的 peak range、azimuth band、局部结构响应生成 box。box 尺寸继承车辆尺寸 prior 或 candidate row 中的 `w/h`，中心由 fan-polar 转 display-XY。
- `multi_peak_ray_candidate`: 从 ray mode 的多个 SAR peaks 产生多个 range hypothesis。每个 peak 映射成候选 box，用于检查单点 range prior 是否错过局部结构。
- `track_signed_escape_candidate`: 从 signed mode 的 escape direction 和短时 range delta 生成候选。它表达“沿时序支持方向释放 range”，但必须保留 weak temporal evidence 标记。
- `bidirectional_escape_candidate`: 当正反两个方向都存在 plausible escape cue 时，保留双向候选以供可视化审查，不能提前用规则压掉一侧。

这些 source 从 mode row 变成 candidate box 的共同步骤是：读取 `r/az/cross` 或 peak-derived fan-polar 坐标，使用 fan-polar 转换得到 `(cx, cy)`，继承或估计 `w/h/heading`，写入 `candidate_source`、`candidate_source_family`、`candidate_detail` 和 provenance 字段。

## 8. C1.4 Frozen Ranking

C1.4 的 frozen ranking 是 deterministic input rank，不是 calibrated selector。rank group 顺序用于稳定检查和可视化，不代表最终可靠性。

建议保留的 rank group 顺序：

1. `prior_core`
2. `factor_retrieval`
3. `structural_local`
4. `structural_range`
5. `structural_temporal`
6. `review_only_tail`

含义：

- `prior_core`: base/factor inference 等基础 runtime prior。
- `factor_retrieval`: factor top-k 和 visible support 等已存在 retrieval candidate。
- `structural_local`: wedge/local SAR structure 生成的候选。
- `structural_range`: ray/profile/range peak 生成的候选。
- `structural_temporal`: signed/tracklet 弱时序候选。
- `review_only_tail`: duplicate、blocked、sar-only、identity-ambiguous 或必须人工审查的候选。

这个顺序只保证输入稳定和可审计，不能替代 OOF calibration，也不能被描述为 formal selector。
