# S1-LR GM_RM017 330–350 可见车辆响应流与运动归属最小闭环报告

## 1. 最终摘要

本轮确认了一个必须分层表达的结果：

1. `330–350` 中确实存在肉眼可见、相对 GT 中心下侧持续出现的近水平亮响应，且 `339` 起始、`340–350` 稳定进入更强、更连续的显示状态；
2. 但该响应在原始 SAR 像素中的右移不能归因给车辆，因为竖直强线、扇形弧、孤立热点和邻近背景也具有近乎相同的共同图像漂移；
3. 将世界残差正确改写为“局部位移减去多背景共同位移”后，相位相关和稠密光流在 `20/20` 相邻帧对上都更支持背景共同运动，而不是 GT 逐帧运动；
4. 二维偏移场没有形成运动一致支撑走廊，也没有唯一中心；
5. 因而本轮只支持“局部可见显示响应及其状态变化”，不支持“车辆运动所有权、完整车体支撑、精确中心、光学替代或 S1-D”。

这不是用一个总的 `NOT_READY` 覆盖事实：显示响应和状态跃迁是正证据；车辆归属和下游准备度是未建立或未就绪。

## 2. Git 与输入冻结审计

- 仓库：`D:/profile/research/optical-sar-visual-diagnosis-sar-foundation`
- 分支：`feature/oty2-sar-gt-structure-foundation`
- 冻结起始 HEAD：`938dd8e37b54592bc153f5518843c4f7479cfe24`
- 起始 upstream：`origin/feature/oty2-sar-gt-structure-foundation`
- 起始 divergence：`0 0`
- 起始 worktree：clean
- 既有 stash：`stash@{0}`，来自 `feature/v0-visual-diagnosis-bootstrap`，本轮未读取、未应用、未修改
- 默认解释器：`D:/MINICONDA/envs/py311/python.exe`
- `old_work` runtime dependency：none

冻结输入：

- manifest：`manifests/oty2/oty2_s1l_local_response_fields.csv`
- manifest SHA256：`029d23d80638bfe2e115324140bfcccf9e4bb15ffeadf65f1920b244afa21092`
- 精确选择：`GM_RM017` / `GM_RM017:PV002` / `S0MV-GM_RM017-PV002-SEG02` / `330–350`
- 行数：21
- 图像尺寸：21/21 为 `2308×1334`
- 图像 SHA256：21/21 与 `raw_image_sha256` 一致
- 坐标：直接使用 raw anchor 与 crop polygon 的 SAR 像素坐标；未使用 `0.03 m/pixel`、米制框、历史跨模态比例、扇形角度中心重算或任何坐标乘法。

## 3. 直接视觉事实

直接审阅在任何运动指标运行前完成并冻结于：

- `reports/oty2/oty2_s1lr_gm_rm017_motion_coherent_visible_response_direct_visual_review_20260716.md`
- `manifests/oty2/oty2_s1lr_gm_rm017_direct_visual_reviews.csv`

Git 外视觉包：

`D:/profile/research/workspace/output/s1_lr_gm_rm017_motion_coherent_response_flow_20260716`

### 3.1 可见响应主体

- 主响应位于 GT 中心下方，常贴近框下半部或下缘；
- 长轴为近水平/切向方向，与近水平 GT 长轴大体一致；
- 它是断续亮段、连续亮带和局部热点的组合，不是单一亮点；
- 最亮局部段在左右之间变化，不能作为车辆中心。

### 3.2 状态变化

- `330–335`：弱到中等，断续、分散；
- `336–338`：横向连续性逐渐增强；
- `339`：增亮、变宽，直接审阅确认的过渡起始；
- `340–350`：强横向条带持续；
- `348–350`：与竖直强线和右侧复杂亮结构的空间混合更明显。

### 3.3 对“世界固定”的视觉纠偏

直接 montage 容易把背景角色误读为原始像素零位移。后续位置复核显示：

- 竖直强线约从 `x=1277` 到 `x=1406`，累计 `+129 px`；
- GT 中心从 `x=1050.984` 到 `x=1177.320`，累计 `+126.336 px`；
- 两者相对横向距离只变化约 `2.664 px`。

所以，原始 SAR 序列存在强共同漂移。世界坐标不能定义为“原始像素不动”，必须用背景参照的共同位移稳定化。这一纠偏不否定亮带存在，但否定了“共同右移本身等于车辆归属”。

## 4. 方法

协议：

`docs/OTY2_S1LR_GM_RM017_MOTION_COHERENT_VISIBLE_RESPONSE_FLOW_PROTOCOL.md`

runner：

`tools/diagnostics/run_oty2_s1lr_gm_rm017_motion_coherent_visible_response_flow.py`

### 4.1 两种独立位移方法

每个相邻帧对与每个轨迹偏移分别运行：

1. `PHASE_CORRELATION_HIGHPASS`：固定线性显示窗、高通、Hanning window、相位相关；
2. `DENSE_FARNEBACK_STRUCTURAL_MEDIAN`：固定显示窗、Farneback 稠密光流、冻结中心结构掩膜、稳健中位位移。

两种方法保持独立，不平均、不加权、不形成总分。

### 4.2 多背景世界参考

每个帧对使用同样处理的四个背景角色：

- nearby non-overlap background；
- vertical strong line；
- fan arc；
- isolated hotspot。

各方法分别取四个控制位移的中位数作为 `d_bg`。定义：

- `world_residual_motion = ||d_est - d_bg||`
- `vehicle_residual_motion = ||d_est - d_gt||`
- `wrong_track_residual_motion = ||d_est - (d_bg - (d_gt-d_bg))||`

这一步只建立局部图像世界参考，不声称绝对地理配准。

### 4.3 偏移场

- coarse：`dx=-400…+400` step `100`，`dy=-240…+240` step `80`；
- fine：`dx=-160…+160` step `40`，`dy=-120…+120` step `40`；
- 去重后：123 个偏移。

每个偏移独立保留清晰度、时间中位、时间 MAD、正响应持续率、两种方法的三类残差、连续长度、固定世界/轨迹清晰度差和有效比例。没有 weighted score、rank 或 winner。

### 4.4 空间与时间反事实

空间：正确轨迹、仍覆盖同车的近左/近右/近上偏移、非重叠背景、竖直强线、扇形弧、孤立热点。

时间/运动：确定性打乱、反转、`±4/±8/±12` 非循环错位、横向速度 `0.5×/1.5×`、错误横向方向、固定中位中心。

所有反事实使用同一原始帧、尺寸、处理、局部背景规则和指标。近邻偏移不当作车辆阴性。

## 5. 背景共同漂移

`manifests/oty2/oty2_s1lr_gm_rm017_background_motion_reference.csv` 给出：

- 相位相关背景横向位移中位数：`6.250750 px/pair`；
- 稠密光流背景横向位移中位数：`6.307327 px/pair`；
- 20 对累计背景横移：相位约 `125.0206 px`，光流约 `125.5531 px`；
- GT 累计横移：`126.336 px`；
- GT 相对背景的逐对横向位移中位数：相位参考 `0.645465 px`，光流参考 `0.561813 px`。

两种方法对共同漂移高度一致。主窗口的主要图像运动不是车辆特有运动，而是局部背景与 GT 共同经历的扫描/成像漂移。

## 6. 相邻帧运动归属结果

`manifests/oty2/oty2_s1lr_gm_rm017_motion_pair_evidence.csv` 含 20 对：

- 相位相关：20/20 quality usable；
- 稠密光流：20/20 quality usable；
- 方法位移差中位数约 `0.109852 px`，最大约 `0.291522 px`；
- 相位世界残差中位数：`0.092616 px`；
- 相位车辆残差中位数：`4.606634 px`；
- 光流世界残差中位数：`0.115809 px`；
- 光流车辆残差中位数：`4.662695 px`；
- 相位车辆残差小于世界残差：`0/20`；
- 光流车辆残差小于世界残差：`0/20`。

因此，本窗口的局部位移估计由共同背景漂移主导。即使亮带在 GT 对齐 montage 中清楚，位移证据仍不能把它归属给车辆。

## 7. 二维偏移场

`manifests/oty2/oty2_s1lr_gm_rm017_offset_field_evidence.csv`：

- `BACKGROUND_DOMINATED_REGION`：112；
- `AMBIGUOUS_OVERLAP_REGION`：2；
- `OUTSIDE_VALID_REGION`：9；
- `MOTION_COHERENT_SUPPORT_CORRIDOR`：0。

fine grid 全部为背景主导。两个 coarse ambiguous offset 位于 `(-300,160)` 和 `(400,160)`，属于方法残差排序冲突，不构成正确轨迹附近的支撑走廊。`dy=240` 的 9 个 coarse offset 因有效比例 `0.925238<0.95` 被标为无效区域。

正确偏移 `(0,0)` 同样为 `BACKGROUND_DOMINATED_REGION`。因此：

- 没有单点峰值；
- 没有连通车辆运动走廊；
- 不允许输出最佳中心；
- `EXACT_CENTER_IDENTIFIABILITY` 未建立。

## 8. 局部空间反事实

关键独立指标如下：

| 轨迹/偏移 | mean clarity | median clarity | positive persistence mean | horizontal run px |
|---|---:|---:|---:|---:|
| correct | 30.509 | 40.066 | 0.0639 | 68 |
| near left | 29.157 | 39.120 | 0.0538 | 112 |
| near right | 31.221 | 40.882 | 0.0796 | 94 |
| vertical line | 32.035 | 41.265 | 0.0754 | 42 |
| fan arc | 28.878 | 39.021 | 0.0340 | 14 |
| isolated hotspot | 25.121 | 35.085 | 0.0122 | 14 |

正确轨迹没有在清晰度、持续率或连续长度上形成唯一优势；近邻偏移仍覆盖相同响应，而竖直强线控制的清晰度反而更高。这里没有把这些指标加权或排序为 winner。结论是局部唯一性未建立，不是“竖线优于车辆”。

## 9. 时间与运动反事实

- shuffle 与 reverse 的均值/中位清晰度下降，错误方向残差明显增大；
- 但 `±4/±8/±12` 以及固定中心并没有统一失败；
- 不同时间错位保留的有效帧数不同，尤其 `±12` 仅 9 帧，不能把其较高清晰度与 21 帧正确轨迹直接当作优势比较；
- `0.5×` 速度降低清晰度，`1.5×` 与正确轨迹相近；
- 固定中位中心 mean clarity `30.761`，与正确轨迹 `30.509` 接近。

这些结果只说明当前显示结构对时间/速度误差存在较宽容忍，且固定背景共同漂移仍是强混杂。它们没有形成车辆专属的时间对应关系。

## 10. 响应状态变化

`manifests/oty2/oty2_s1lr_gm_rm017_response_state_evidence.csv` 保留每帧独立指标，阶段由直接审阅冻结，没有由指标重选。

| 阶段 | n | response robust-z mean | positive fraction mean | horizontal run mean px | upper-band z mean |
|---|---:|---:|---:|---:|---:|
| 330–338 weak/distributed | 9 | 0.306842 | 0.068171 | 39.11 | 0.133983 |
| 339 transition onset | 1 | 0.388416 | 0.077762 | 44.00 | 0.135262 |
| 340–350 strong/compact | 11 | 0.481655 | 0.086984 | 61.55 | 0.279129 |

强阶段的平均亮度、正响应比例、横向连续长度和上带响应均上升。`SAME_VEHICLE_RESPONSE_STATE_TRANSITION` 作为同一观察窗口中的显示状态连续变化得到支持；但“同一车辆”的物理所有权仍未由运动证据建立，所以正式状态只写 `RESPONSE_STATE_TRANSITION=SUPPORTED`，不升级为身份真值。

## 11. 探索性响应分层

分层不使用 GT 框内外作为标签，只比较正确轨迹、背景累计轨迹和错误方向轨迹的持续率/中位响应/时间 MAD。结果：

- `PERSISTENT_VEHICLE_ASSOCIATED_RESPONSE`：511 px，`0.6452%`；
- `INTERMITTENT_VEHICLE_ASSOCIATED_RESPONSE`：2796 px，`3.5303%`；
- `WORLD_FIXED_BACKGROUND`：478 px，`0.6035%`；
- `CROP_OR_RESAMPLING_ARTIFACT`：9024 px，`11.3939%`；
- `UNRESOLVED_MIXED_RESPONSE`：66391 px，`83.8270%`；
- `CURRENTLY_DARK_LATENT_BODY_REGION`：0 px，未自动赋值。

少量 persistent/intermittent 像素只是保守多证据探索标签，不足以推翻整场位移的背景主导结果。主体仍是未解析混合响应，不能用于完整车体重建或自动标注。

## 12. 分层结论

正式结论见：

`manifests/oty2/oty2_s1lr_gm_rm017_stage_conclusions.csv`

- `LOCAL_VISIBLE_VEHICLE_RESPONSE_FLOW=VISUALLY_SUPPORTED_DISPLAY_FLOW_BACKGROUND_RELATIVE_OWNERSHIP_NOT_ESTABLISHED`
- `VEHICLE_MOTION_OWNERSHIP=NOT_ESTABLISHED_MULTI_BACKGROUND_CO_MOTION`
- `WORLD_BACKGROUND_SEPARATION=PARTIALLY_SUPPORTED_BACKGROUND_DRIFT_IDENTIFIED_LOCAL_SEPARATION_NOT_ESTABLISHED`
- `RESPONSE_STATE_TRANSITION=SUPPORTED_339_ONSET_340_350_STRONG`
- `MOTION_COHERENT_SUPPORT_CORRIDOR=NOT_ESTABLISHED_NO_VALID_OFFSET_PASSED_BOTH_METHODS`
- `VISIBLE_RESPONSE_UNIQUENESS_IN_LOCAL_NEIGHBORHOOD=NOT_ESTABLISHED_NEAR_OFFSETS_AND_CONTROLS_RETAIN_STRUCTURE`
- `EXACT_CENTER_IDENTIFIABILITY=NOT_ESTABLISHED`
- `FULL_BODY_SUPPORT_READINESS=NOT_READY`
- `OPTICAL_INPUT_REPLACEMENT_READINESS=NOT_READY`
- `S1D_READINESS=NOT_READY`

## 13. 固定规则重放建议

本轮不执行重放，只给出后续冻结顺序：

1. PV002 相邻窗口；
2. PV003 一个肉眼明确连续窗口；
3. PV004 一个肉眼明确连续窗口；
4. GM_RM011 诊断窗口。

重放必须冻结：

- 多背景共同位移参考；
- 两种独立位移法及参数；
- 世界/车辆/错误方向残差定义；
- `330–338 / 339 / 340–350` 状态语义；
- coarse/fine 偏移网格；
- 空间和时间反事实角色；
- 不加权、不排名、不选 winner 的边界。

不得在重放时重新挑背景控制、指标、阈值或状态定义。

## 14. 禁止项审计

本轮没有：

- 进入 S1-D；
- 输出最终车辆框或唯一中心；
- 修改 GT；
- 重建潜在完整车体；
- 自动标注；
- 创建 candidate bank；
- selector/ranking；
- 加权综合分数；
- GT IoU 选参；
- 训练模型；
- 通过阈值调优制造 PASS；
- 把亮带中心当完整车辆中心；
- 把 GT 框内像素自动算作车辆；
- 使用比例、米制或历史映射转换。

大型 PNG、GIF、NPZ 和中间数组均位于 Git 外工作区。仓库只保留协议、runner、validator、小型 CSV、中文视觉审阅和正式报告。
