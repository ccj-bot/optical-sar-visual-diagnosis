# OTY2 WGV3.3B Visual Source And Mapping Diagnosis

Date: 20260710

## Actual Images Inspected

### Optical Frames

| frame | exists | size | mean | std | path |
| --- | --- | --- | --- | --- | --- |
| 8 | true | 800x600 | 179.004 | 60.112 | D:/profile/research/data/GM_RM011/GM_RM011_frames/000008.png |
| 10 | true | 800x600 | 175.187 | 61.216 | D:/profile/research/data/GM_RM011/GM_RM011_frames/000010.png |
| 13 | true | 800x600 | 164.899 | 63.577 | D:/profile/research/data/GM_RM011/GM_RM011_frames/000013.png |
| 18 | true | 800x600 | 159.048 | 68.943 | D:/profile/research/data/GM_RM011/GM_RM011_frames/000018.png |
| 25 | true | 800x600 | 144.6 | 72.383 | D:/profile/research/data/GM_RM011/GM_RM011_frames/000025.png |

### SAR / SAR-Gray Frames

| frame | exists | size | image_mean | target_sector_top5_mean | control_sector_top5_mean | target_sector_max | control_sector_max | path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | true | 2308x1334 | 18.537 | 49.574 | 0 | 224 | 0 | D:/profile/research/data/GM_RM011/GM_RM011_SARframes_gray/000000.png |
| 18 | true | 2308x1334 | 24.112 | 62.124 | 0 | 241 | 0 | D:/profile/research/data/GM_RM011/GM_RM011_SARframes_gray/000018.png |
| 36 | true | 2308x1334 | 29.367 | 79.386 | 0 | 222 | 0 | D:/profile/research/data/GM_RM011/GM_RM011_SARframes_gray/000036.png |
| 37 | true | 2308x1334 | 28.176 | 76.277 | 0 | 193 | 0 | D:/profile/research/data/GM_RM011/GM_RM011_SARframes_gray/000037.png |
| 58 | true | 2308x1334 | 17.827 | 47.783 | 0 | 170 | 0 | D:/profile/research/data/GM_RM011/GM_RM011_SARframes_gray/000058.png |

## Chinese Visual Judgment

- 光学 T001：frame 8/10/13/18/25 显示的是近场白车的连续局部外观，主体从侧窗/车身局部逐步变成车头/引擎盖局部；画面存在强截断和主框选择不稳定，因此不能把它升级成唯一身份真值。
- 自动通道：WGV3.3A 在同一时间邻域保留了多个自动节点，合理候选包括 `AUTO_GM_RM011_0001`、`AUTO_GM_RM011_0003`、`AUTO_GM_RM011_0005`，同时也保留 `AUTO_GM_RM011_0002/0006/0007` 等竞争或不确定节点。
- SAR 映射：T001 posthoc field 的粗方位代理为 `-55.052..44.587` deg，负例/背景控制为 `70..85` deg；二者都只是在相近 SAR 时间窗内观察响应，不是最终车位。
- SAR 图像：0/18/36 等 SAR-gray 帧能打开，目标方位扇区可见强散射峰；shifted control 扇区在当前采样下没有同级亮点，主要作为同时间非目标方位边界对照。这支持进入非 GT SAR 响应实验，但当前证据不足以宣布车辆精确位置。
- 相邻 SAR 帧：37/58 帧仍有可见结构变化，说明短窗响应可观察；但缺少 raw pulse/window 映射和 range anchor，不能把峰值直接当目标。

## Feasible Fields Reviewed

| message_id | optical_source_channel | sar_frame_start | sar_frame_end | azimuth_min | azimuth_max | range_status | runtime_safe | posthoc_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WGV33B_H001 | automatic_uncertain_hypothesis | 0 | 44 | -55.052 | 38.971 | broad_unknown_range_prior | true | false |
| WGV33B_H002 | automatic_runtime_hypothesis | 0 | 21 | 9.894 | 41.573 | broad_unknown_range_prior | true | false |
| WGV33B_H003 | automatic_uncertain_hypothesis | 8 | 48 | -38.777 | 44.283 | broad_unknown_range_prior | true | false |
| WGV33B_H004 | automatic_uncertain_hypothesis | 22 | 48 | -39.121 | 42.739 | broad_unknown_range_prior | true | false |
| WGV33B_H005 | automatic_uncertain_hypothesis | 27 | 86 | -34.189 | 44.587 | broad_unknown_range_prior | true | false |
| WGV33B_H006 | automatic_uncertain_hypothesis | 29 | 119 | -55.377 | 45.14 | broad_unknown_range_prior | true | false |
| WGV33B_H007 | automatic_uncertain_hypothesis | 37 | 75 | -55.32 | 5.225 | broad_unknown_range_prior | true | false |
| A_POSTHOC_T001 | posthoc_visual_constraint | 0 | 36 | -55.052 | 44.587 | broad_unknown_range_prior | false | true |
| NEG_T001_SHIFTED_AZIMUTH_CONTROL | negative_background_control | 0 | 36 | 70 | 85 | broad_unknown_range_prior | true | false |
