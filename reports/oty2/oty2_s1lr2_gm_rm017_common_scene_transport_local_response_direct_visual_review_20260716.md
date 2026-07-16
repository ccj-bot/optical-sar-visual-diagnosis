# S1-LR2 GM_RM017 共同场景运输与局部响应组织直接视觉审阅

日期：`2026-07-16`

## 1. 审阅范围与边界

- scene：`GM_RM017`
- vehicle：`GM_RM017:PV002`
- segment：`S0MV-GM_RM017-PV002-SEG02`
- SAR frame：`330–350`
- 冻结起始 HEAD：`8eb4b99e3fefb41ba2449c5e53ea3b7338e8591b`
- 本轮阶段：S1-L；未进入 S1-D

本审阅只确认显示域背景结构身份、稳定化质量和局部响应组织。GT 只用于发现壳层与事后解释；GT 框内外没有被用作像素车辆标签。本轮没有恢复潜在完整车体，没有最终框、自动标注、候选库、排序或综合分数。

大型视觉产物位于：

`D:/profile/research/workspace/output/s1_lr2_gm_rm017_common_scene_transport_local_response_20260716_final_v2`

## 2. 背景锚点逐帧身份审阅

逐帧接触表位于 `anchor_reviews/*_identity_contact_sheet.png`，前后对照动画位于 `anchor_reviews/*_before_after.gif`。

| anchor | split | 直接审阅结论 |
|---|---|---|
| `BG_A_VERTICAL_STRONG_LINE` | fit | `330–350` 始终为同一竖直强线；局部亮度与纹理变化，但没有身份切换或车辆混入 |
| `BG_B_FAN_ARC_CENTRAL` | fit | 始终为同一中央扇形弧段；弧上热点强度变化，不构成结构切换 |
| `BG_C_ISOLATED_HOTSPOT` | fit | 同一孤立热点/短脊连续存在；没有进入车辆壳层 |
| `BG_D_NEARBY_NONVEHICLE_CURVE` | holdout | 同一邻近非车辆斜向/弯曲结构，逐帧连续；未用于拟合 |
| `BG_E_LEFT_ARC_BRANCH` | holdout | 同一左侧弧支，方向和局部位置连续；未用于拟合 |
| `BG_F_RIGHT_DIAGONAL_FRAGMENT` | fit | 同一右侧斜向亮片段；与目标壳层空间分离 |
| `BG_G_UPPER_DIAGONAL_FRAGMENT` | fit | 同一上侧斜向背景片段；与目标壳层空间分离 |
| `BG_H_FAN_ARC_LEFT` | fit | 同一左侧扇形弧段；亮度响应变化但弧线身份连续 |

共 `168/168` 个 anchor-frame 记录标记为 `CONFIRMED_CONTINUOUS_330_350`，算法结构切换嫌疑为 `0`。结构匹配质量最小值 `0.167022`、中位数 `0.353630`；相位响应最小值 `0.274514`、中位数 `0.553629`；两种方法单步位移分歧中位数 `0.267917 px`、最大值 `1.044968 px`。

一次最初提出的上右弧锚点在早期帧后离开局部跟踪窗，直接审阅未通过，因此在最终锚点集冻结前被拒绝。最终模型没有使用该无效提议。

## 3. 背景稳定化直接审阅

关键材料：

- `01_raw_full_frame.gif`
- `02_stabilized_full_frame.gif`
- `03_raw_fixed_vehicle_neighbourhood.gif`
- `04_stabilized_vehicle_neighbourhood.gif`
- `05_vehicle_neighbourhood_before_after.gif`
- `08_holdout_background_residual_timeseries.png`
- `09_stabilization_valid_mask.gif`
- `10_stabilization_valid_mask_temporal_fraction.png`
- `11_interpolation_impact.gif`
- `12_interpolation_impact_temporal_mean_x12.png`
- `14_stabilized_local_response_review_sheet.png`

直接对照确认：

1. 原始序列中的竖直强线、扇形弧、孤立热点和其他斜向结构共同右移；稳定化后这些结构返回固定背景坐标；
2. 两个未参与拟合的背景结构也同时稳定，而不是只对齐一个拟合区域；
3. 竖直强线与右侧复杂结构在稳定坐标中保持在目标粗走廊右侧，不再表现为逐帧“进入”目标窗口；
4. `348–350` 在扩张邻域仍有背景复杂结构混合，但在冻结粗走廊内可与主要横向响应作空间分离；
5. 有效 mask 变化主要位于整幅图像平移后的外侧边界，目标与背景审阅区域保持有效；插值影响分布没有生成一条伪造的目标尺度横带。

## 4. 稳定化后的局部车辆响应

`14_stabilized_local_response_review_sheet.png` 对 `330 / 335 / 338 / 339 / 340 / 344 / 348 / 350` 同时给出原始固定 ROI、稳定 ROI 和固定 robust-z 响应覆盖。

直接事实为：

- 下侧/中下侧近水平亮带在 `330–350` 的冻结粗走廊中持续存在；
- 它由连续亮带、短亮段和热点共同组成，不是一个稳定单点；
- 稳定化后横带不随竖直强线共同横扫窗口，说明此前的主要位移确属共同场景运输；
- 上侧短段/热点在多数帧存在，与主带保持较小的垂向间隔，但其显示形态并非车辆独有；
- 左右端附近长期存在热点响应，但扇形弧背景也能产生“横带+热点”的形式，因此端点热点只能作为部分组织证据。

## 5. 对 339 状态语义的纠正

稳定化后，`338→339` 的局部平均强度和背景中位数在车辆区域及多个匹配背景中同步上升。例如粗走廊背景中位数从 `45` 升至 `51`，右侧匹配背景从 `44` 升至 `51`，扇形弧从 `45` 升至 `52`。这更像全场显示增益/成像响应变化，而不是背景强线进入窗口，也不是车辆专属突变。

车辆粗走廊的 robust-z 正响应比例从 `0.086622` 升至 `0.092311`，变化存在但幅度有限；主带 robust-z 在 `339` 为 `5.375335`，低于弱阶段中位数 `5.895786`，随后 `340–350` 中位数升至 `6.253750`。

因此：

- `339` 不能继续作为已确认的车辆专属状态跃迁；
- `340–350` 的局部横向响应相对更强这一事实仍保留；
- 正式结论只能是 `PARTIAL`，不能升级为 `LOCAL_VEHICLE_RESPONSE_STATE_TRANSITION_SUPPORTED`。

## 6. 直接审阅结论

```text
COMMON_SCENE_TRANSPORT=VISUALLY_SUPPORTED
BACKGROUND_STABILIZATION=MULTI_REGION_SUPPORTED
LOCAL_HORIZONTAL_RESPONSE_CORE=VISUALLY_SUPPORTED
LOCAL_MULTI_PART_RESPONSE_ORGANIZATION=PARTIAL
FRAME_339_VEHICLE_SPECIFIC_TRANSITION=NOT_SUPPORTED
LATENT_FULL_BODY_SUPPORT=NOT_RECOVERED
S1D=NOT_ENTERED
```
