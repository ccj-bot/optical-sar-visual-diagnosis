# OTY2-S1X 无目标参考直接视觉审阅

日期：`2026-07-17`

审阅状态：`DIRECTLY_REVIEWED_COMPLETE`

本审阅在 inference 输出写盘后、读取发现/重放目标 SAR 参考框之前完成。六张审阅图均明确标记 `no target reference`；图中只有光学 P1-E benchmark bbox、光学条件壳层、稳定化 SAR 灰度和冻结规则产生的 response-state overlay。

## 1. 发现窗口：GM_RM017:PV002 / SAR 330–350

逐帧均匀抽取的 optical frame `158, 159, 160, 162, 163, 165, 166, 168` 中，深色轿车保持完整可见，bbox 主体连续，没有明显主体切换。由独立校准和两种 radial proxy 合并得到的壳层从约 `theta=-18.1 deg` 连续移动到 `+3.9 deg`；壳层明显宽于单车框，不是精确位置声明。

稳定化 SAR 中，壳层中下部存在一条反复出现的近水平连续响应。它不是单一亮点：由一段较连续的横带、局部增亮和少量间断组成。该响应在所有八个抽样帧都可见，且冻结时序图中形成连续 persistent/intermittent 支撑。壳层上部还存在零散短段与热点，跨帧稳定性明显弱于主横带，适合保留为 `INTERMITTENT` 或 `MIXED_OR_UNRESOLVED`，不能并入完整车体。

主竖直强线和扇形弧大多位于壳层外。当前自动 `BACKGROUND_EXCLUDED_REGION` 面积为零，视觉上更可能表示主要强背景未进入壳层，而不是已经建立了完备背景分类器。该项必须由事后面积、其他车辆 overlap 和 SAR-only 对照继续评价。

盲审结论：

`DISCOVERY_VISIBLE_RESPONSE_SEQUENCE=VISUALLY_SUPPORTED`

`DISCOVERY_COMPLETE_BODY_OR_EXACT_CENTER=NOT_CLAIMED`

## 2. 冻结规则重放：GM_RM017:PV003 / SAR 338–391

逐帧均匀抽取的 optical frame `162, 165, 169, 172, 176, 180, 183, 187` 中，白色 SUV 保持完整可见。壳层方位从约 `-29.4 deg` 连续移动到 `+19.4 deg`，对应不同车辆、不同光学轨迹和更长的 54 帧窗口；规则、阈值和独立 PV004 校准均未改变。

稳定化 SAR 中再次出现持续的近水平主响应带。该带在早、中、晚抽样帧均存在，并在 temporal summary 中形成集中的 persistent/intermittent 支撑。它的位置和周围背景布局不同于 PV002：右侧复杂结构、下部热点和上侧弧段的相对关系改变，但主响应仍被同一逻辑保留。上侧稀疏响应比主带更弱、更不稳定，没有被强迫解释为固定部件。

盲审结论：

`REPLAY_VISIBLE_RESPONSE_SEQUENCE=VISUALLY_PARTIALLY_REPRODUCED`

`REPLAY_RULE_CHANGED_AFTER_DISCOVERY=false`

`REPLAY_COMPLETE_BODY_OR_EXACT_CENTER=NOT_CLAIMED`

## 3. 两窗共同结论

1. 光学壳层没有退化为待评价 SAR 邻域，也没有成为最终框；它保留了显著径向不确定度。
2. 同一冻结规则在两辆不同物理车辆上都把大壳层压缩成较小的连续横向响应带。
3. SAR-only temporal map 同时保留多条弧、线、热点和其他稳定对象，说明 SAR-only 仍有明显背景歧义；联合方法的价值应由壳层内收缩和身份边界来评价。
4. 当前视觉证据支持“可见响应序列”，不支持完整车体、唯一中心、车辆前后方向或自动标注。
5. 背景自动分类仍偏保守；强背景多数由 optical shell 几何直接排除，而不是在壳层内被标成红色背景。

## 4. 审阅产物

- discovery：2 张 transfer review page + 1 张 temporal summary；
- replay：2 张 transfer review page + 1 张 temporal summary；
- 所有 PNG 位于 `D:/profile/research/workspace/output/oty2_s1x_20260717`，不进入 Git；
- artifact SHA256 记录在 `manifests/oty2/oty2_s1x_blind_visual_review_manifest.csv`。
