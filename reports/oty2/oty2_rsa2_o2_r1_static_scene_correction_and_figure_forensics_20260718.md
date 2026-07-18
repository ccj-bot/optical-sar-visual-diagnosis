# OTY2-RSA2-O2-R1 静止场景纠偏与 O2 图像来源法证报告

日期：`2026-07-18`
场景：`GM_RM011`（因果事实同时适用于 `GM_RM017`、`GM_RM019`）
结论状态：`O2_DIAGNOSED_MISSING_STATIC_WORLD_GEOMETRY`

## 1. 审阅问题

本报告回答四个问题：

1. 所有车辆静止、平台运动这一采集事实如何修订历史术语与 O2 因果解释；
2. O2 的 `W1A_R01`、C-W1 青框、红框和黄框分别来自什么；
3. SAR 16 与 SAR 80 的直接图像证据实际支持什么、不支持什么；
4. `BIDIRECTIONALLY_CLOSED=0` 是 SAR 响应无法解释，还是此前没有建立静止车辆到移动平台/SAR 图像的完整二维几何链。

本轮没有修改历史 O2 报告、冻结正向 CSV/图像、GT、代码、配置或阈值，也没有运行定位或诊断实验。仓库外脚本只执行帧读取、既有框绘制和证据排版。

## 2. 审阅材料与直接图像范围

完整复核了深度错误复盘、状态索引、RSA2-O0、RSA2-O1、O1-R1、O2 主报告、O2 正向/逆向/闭环/负控制 CSV、O2 九张核心图、P0 同步、S0/S0-M 坐标与方位合同，以及涉及 `11.809661°` 的公式与审计行。

直接打开并审阅：

- optical 3–12、6–9、33/34、36–41；
- SAR 8–24 全帧；
- SAR 12–20 GT 局部连续裁剪；
- SAR 70、73、76–84 与 SAR 80 全图；
- O2 `F_W1_FORWARD_BLIND_EVIDENCE.png`、`R_W1_REVERSE_GT_AUDIT.png`、`C_W1_CLOSURE_COUNTERFACTUAL.png`；
- 仓库外 O2 绘图脚本与执行日志。

## 3. 静止场景因果模型

用户确认三场景全部车辆静止，故物理模型为：

```text
P_vehicle_world = constant
heading_vehicle_world = constant
velocity_vehicle_world = 0
```

光学图像与 SAR 图像中的时变位置、尺度、视角、方位、距离、方向及可见状态由平台自运动、传感器坐标与成像投影引起。原“车辆生命周期”只可解释为观测生命周期；原“车辆轨迹”只可在历史语境中理解为观测线程或平台相对坐标中的表观轨迹。

## 4. 历史误导性术语法证

完整纠偏行见 [结论纠偏账本](../../manifests/oty2/oty2_rsa2_o2_r1_conclusion_correction_ledger.csv)。直接含有“车辆运动/车辆轨迹/车辆退出”且可能误导当前物理模型的历史文件包括：

- `docs/oty2_human_visual_review_notes_and_sar_morphology_insight_archive.md`：把高能区迁移写成“随车辆运动迁移”；
- `docs/OTY2_POINT_TO_STRUCTURE_OPTICAL_SAR_VEHICLE_RESPONSE_FRAMEWORK.md`：使用“与光学车辆运动不一致”；
- `docs/guidance/conversation_derived_research_notes.md` 与 `docs/guidance/temporal_usage_rethink_notes.md`：使用“同一车辆轨迹”；
- `docs/OTY2_S1L_SEMANTIC_CORRECTION_AND_OPTICAL_CONDITIONED_SUPPORT_OBSERVABILITY_PROTOCOL.md` 与对应 S1-L 报告：使用“真实车辆轨迹交换”；
- `reports/oty2/oty2_same_vehicle_referent_consistency_20260705_165636.md`：把可见变化解释为相机运动或车辆运动二选一；
- `reports/oty2/oty2_sar_vehicle_morphology_primitives_gt_anchored_20260703_163000.csv`：使用“随车辆运动或姿态变化迁移”；
- O0、O1、O1-R1、O2 及其样本账本中的“车辆进入/退出”和“车辆退出后背景持续”。

这些历史记录不删除。当前修订为：平台自运动诱导表观变化、观测线程、观测生命周期和传感器视场准入/准出。O1/O2 的身份排他与退出后排除逻辑仍保留，但“退出”只指目标车辆离开当前观测范围。

## 5. SAR 16 实图与姿态判断

![E02](../../docs/reviews/assets/20260718_rsa2_o2_r1_static_correction/E02_STATIC_VEHICLE_MULTI_VIEW_OPTICAL_SAR_8_24.png)

SAR 16 PV001 首选审计行：

```text
center = (1155.377, 1248.565) px
size   = (135.333, 64.847) px
angle  = -10 deg
quality = usable
identity_link = high
```

另有一条几乎相同的 usable PV001 行；O2 已记录二者重叠约 `0.991`，属于冗余 GT 链接，不是第二辆车。

直接图像判断：GT 内存在车辆尺度、近水平微斜结构；车辆响应只局部可见且与近原点弧形/场景纹理混合。optical 3–12 中 PV001 长轴为稳定侧向车身轴，随平台经过从侧后向侧前视角变化，与 SAR GT 的近水平长轴不矛盾。黄色 90° 框将长轴改为近竖直，明显不符合该光学车身姿态；但其仍可截取亮纹理，证明“框内有亮度”没有方向辨识力。

姿态证据只能约束方向相容性，不能提供径向距离。缺少距离时，同方位射线上的错误位置仍会看似合理。

## 6. W1A_R01 与 C-W1 控制来源

![E01](../../docs/reviews/assets/20260718_rsa2_o2_r1_static_correction/E01_C_W1_FRAME_AND_CONTROL_PROVENANCE_CORRECTED.png)

法证结论：

- `W1A_R01` 在 `D:/profile/research/workspace/tasks/oty2_rsa2_o2_bidirectional_audit/build_forward_figures.py:57` 被硬编码为 `(1040,1030,1190,1140)`；
- 中心 `(1115,1085)`、尺寸 `150 × 110 px`、方向 `0°`；
- 它是人工选定的响应审阅区域，不是光学→SAR 二维公式输出；
- 它没有使用光学横坐标、光学车身方向、车辆真实尺寸、深度、距离、平台位姿、相机—雷达外参或 `11.809661°`；
- O2 正向图同时绘制的 `-14.9°` 是硬编码宽方位上下文；当前证据不足以把该精确数值追溯为 optical 8 框经现行公式的直接计算结果；
- 已提交正向 CSV 只保存约 `150 × 110 px`，没有中心、方向或角点。

因此同时冻结：

```text
MANUAL_RESPONSE_REGION_WITH_BROAD_AZIMUTH_CONTEXT
FORWARD_REGION_NOT_REPRODUCIBLE_FROM_COMMITTED_ARTIFACTS
```

C-W1 青框为真实 GT。红色虚线框为同一 GT 平移 `x+260, y-250` 的错误位置负控制。黄色框为同一 GT 中心、尺寸不变、角度 `-10+90=80°` 的错误方向负控制。红框不是 W1A、不是正向预测、不是光学→SAR 映射结果；黄框不是候选。

完整逐面板来源见 [图像来源审计](../../manifests/oty2/oty2_rsa2_o2_r1_figure_provenance_audit.csv)。

## 7. SAR 80：只能排除 PV001，不能证明纯背景

![E03](../../docs/reviews/assets/20260718_rsa2_o2_r1_static_correction/E03_PV001_OBSERVATION_EXIT_NOT_PURE_BACKGROUND.png)

P1-E 观测状态与直接图像一致：

- PV001 在 optical 33/34 仅为右侧边缘部分可见，optical 35 标记为 `exiting`；
- PV003 在 optical 33–40 为 `active_visible/partial_visible`，optical 41 为 `active_visible/full_visible`；
- SAR 73 有 PV003 usable GT，SAR 80 在当前 GT 质量 manifest 中没有同帧行。

因此 SAR 80 不是纯背景帧。持续结构仅支持 `TARGET_VEHICLE_IDENTITY_EXCLUDED`，即不再由 PV001 独占；同帧仍有 `OTHER_VEHICLE_PRESENT`。对具体持续结构只可保留 `BACKGROUND_OR_OTHER_STATIC_OBJECT` 或 `MIXED_OR_UNRESOLVED`，除非另有身份、几何或同帧 GT 证据。

## 8. `11.809661°` 的数值法证

`manifests/oty2/oty2_s0_optical_to_sar_azimuth_mapping_audit.csv` 的 GM_RM011 optical 5 / SAR 10 行给出：

| 字段 | 数值 |
| --- | ---: |
| optical reference center x | `294.000500 px` |
| old linear prediction | `-14.683983642°` |
| SAR GT center azimuth | `-2.874323000°` |
| old linear center error | `-11.809660642°` |

所以 `11.809661°` 是中心残差绝对量级，不是预测角。S0-M 合同和 O2 主报告把它称为“historical case/prediction”的措辞容易误解；当前应写为“GM_RM011 historical old-linear center residual”。

历史公式：

```text
theta = 0.0875154 * x_optical_reference_center_px - 40.413555
```

输出是显示扇区方位角，不是 SAR `x/y`。它不含距离、车辆姿态、平台位姿、相机内参或相机—雷达外参，参数依赖历史 GT/光学锚点审计，状态 `MAPPING_BLOCKED`。

## 9. O2 零闭环的准确科学含义

O2 正向阶段的 13 个实例仍为：6 `ATTRIBUTION_PLAUSIBLE`、6 `MIXED_ATTRIBUTION`、1 `OBSERVED_WITHOUT_OWNER`，逆向对账仍为 4 `FORWARD_FALSE_ATTRIBUTION`、2 `REVERSE_POSTHOC_ONLY`、7 `BOUNDED_UNRESOLVED`、0 `BIDIRECTIONALLY_CLOSED`。正向冻结 SHA 未因本轮修改。

但 O2 测试的不是完整静止世界二维几何链。它测试的是身份、观测生命周期、操作性时间代理、宽方位和人工 SAR 响应区域能否形成正确局部几何。它没有使用世界车辆坐标、逐帧平台位姿、完整标定或径向距离。

因此：

- 可保留 `BIDIRECTIONALLY_CLOSED=0` 作为 O2 实验结果；
- 不得表述为完整光学—SAR 联合假设的强版本失败；
- 应解释为 O2 诊断出静止世界几何链缺失，尤其是径向距离与二维坐标投影缺失；
- 当前主要问题不能先归因于 SAR 响应不可解释，因为前置二维几何约束从未完整建立。

## 10. O2-R1 冻结结论

```text
O2_DIAGNOSED_MISSING_STATIC_WORLD_GEOMETRY
```

身份、观测生命周期、光学姿态和多车关系具有真实约束作用，但不能替代距离和坐标变换。下一步只有资格进入静止世界—移动平台几何资产与公式审计，不授权定位实现。

## 11. 证据图 SHA-256

| 图 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `E01_C_W1_FRAME_AND_CONTROL_PROVENANCE_CORRECTED.png` | `3,132,237` | `806a2e69f32452f090ef13c549e5bf0a25b4d3e9a3a6b340128e87a484671b20` |
| `E02_STATIC_VEHICLE_MULTI_VIEW_OPTICAL_SAR_8_24.png` | `3,471,300` | `9c7414c770a8b41c567dcb754271aa0360c2546c29ae3bf447750f66bb0f50e0` |
| `E03_PV001_OBSERVATION_EXIT_NOT_PURE_BACKGROUND.png` | `4,578,050` | `a548b730cbfc2acbfcca289d0f180e844765f6f19c1a3a411c869324d1ebaa2f` |
