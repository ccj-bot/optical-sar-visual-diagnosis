# E0-R3 GM_RM017 Body-Canonical Visual Casebook

本 casebook 记录首轮可视化审阅入口。PNG 位于 ignored `outputs/`，本文件只保存相对路径和逐窗判断。

## Contact Sheets

- `raw_time_contact_sheet`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_canonical_raw_time_contact_sheet.png`
- `norm_time_contact_sheet`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_canonical_norm_time_contact_sheet.png`
- `overlay_contact_sheet`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_canonical_overlay_contact_sheet.png`
- `E_t_s_heatmap`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_E_t_s_heatmap.png`
- `s_peak_time`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_s_peak_time.png`
- `s_peak_aspect`: `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_s_peak_aspect.png`

## Manual Visual Review Notes

- `W_STABLE SAR 339-341`: 雷达近侧在规范图下侧偏 body_long_positive 端。339 和 341 的主响应贴近下侧近侧边界，340 仍在同一端部但更偏短轴中段；空间位置基本稳定。339->340 的差分呈整条下侧带红蓝互换，说明幅值变化可能受 1 px 级中心或轴向配准影响，不应作为输运证据。
- `W_SLIDE SAR 321-325`: 雷达近侧持续落在下侧斜向边界，主响应始终在 body_long_positive 端和近侧长边交界。321 到 323 的峰位向近侧中段回撤，323 到 325 又回到更靠右下端，表现为局部增强和回跳，而不是单调沿边界滑动。该窗口可作为候选结构动力学案例，但不能单独支持 aspect 驱动。
- `W_SWITCH SAR 351-353`: 近侧方向仍指向下侧，强响应从 351 的近侧长边带扩展到 352 的右下端部集中区，353 又出现右侧短轴侧强点。这里更像端部与近侧长边之间的主响应接管/再分配，而不是旧峰连续平移；可进入后续人工复核，但需要配准扰动和背景对照约束。
- `W_SPLIT SAR 384-386`: 雷达近侧翻到规范图下侧偏 body_long_negative 端，384-386 的下侧高能带仍存在，但左上背景强散射和底边强带同时显著。384->385 的 gain/loss 峰距很大且差分像整体形变，分裂/合并只能记为疑似事件，不能进入物理支持。
- `W_DIFFICULT SAR 386-388`: 386/387 仍有下侧近侧高能带，388 的主峰转到 body_middle 附近，axis reliability 为 LOW，并伴随上方和左侧孤立强点。该段适合记录失败模式，不适合进入输运或 aspect 因果分析。
- `Registration perturbation`: 已打开 registration perturbation contact sheet。1 px 中心平移、2 deg 轴扰动和 2% 尺度扰动都能在同一高能带附近制造红蓝交错差分；轴旋转和尺度扰动尤其呈全图放射或条带变化。因此滑动、切换和分裂候选必须标记 registration-sensitive。
- `Counterfactual SAR 352`: N005 和 fixed strong scatterer 在同一规范流程下也产生局部高能结构，其中 fixed strong 的 near-side fraction 高于车辆若干帧的远侧基线。GT-attached corridor 的强响应贴近下侧车辆高能带且为 overlap-risk corridor，不能用于拒绝背景解释。
- `E_t(s) and s_peak plots`: E_t(s) 热图和 s_peak 图显示峰位跳动和回跳，不是平滑单调迁移；321-325 与 384-388 都不满足独立 aspect 因果闭合。

## Vehicle Windows

### W_STABLE SAR 339

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000339_overlay.png`
- 近侧方向：`(0.46781,0.883829)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_positive_end;body_short_positive_side;pixel=(130,69)`；`s_peak=0.419355`，峰数 `4`。
- 稳定/滑动/切换判断：该帧属于 `stable_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_STABLE SAR 340

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000340_overlay.png`
- 近侧方向：`(0.462508,0.886615)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_half;body_long_positive_end;short_axis_middle;pixel=(130,65)`；`s_peak=0.419355`，峰数 `4`。
- 稳定/滑动/切换判断：该帧属于 `stable_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_STABLE SAR 341

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000341_overlay.png`
- 近侧方向：`(0.46757,0.883956)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_positive_end;body_short_positive_side;pixel=(132,69)`；`s_peak=0.387097`，峰数 `5`。
- 稳定/滑动/切换判断：该帧属于 `stable_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SLIDE SAR 321

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000321_overlay.png`
- 近侧方向：`(0.674362,0.738401)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_positive_end;short_axis_middle;pixel=(132,65)`；`s_peak=0.451613`，峰数 `6`。
- 稳定/滑动/切换判断：该帧属于 `near_side_sliding_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SLIDE SAR 323

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000323_overlay.png`
- 近侧方向：`(0.647599,0.761981)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_positive_end;body_short_positive_side;pixel=(133,67)`；`s_peak=0.322581`，峰数 `5`。
- 稳定/滑动/切换判断：该帧属于 `near_side_sliding_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SLIDE SAR 325

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000325_overlay.png`
- 近侧方向：`(0.614332,0.789048)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_positive_end;body_short_positive_side;pixel=(129,72)`；`s_peak=0.548387`，峰数 `4`。
- 稳定/滑动/切换判断：该帧属于 `near_side_sliding_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SWITCH SAR 351

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000351_overlay.png`
- 近侧方向：`(0.356789,0.934185)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_positive_end;body_short_positive_side;pixel=(131,69)`；`s_peak=0.290323`，峰数 `4`。
- 稳定/滑动/切换判断：该帧属于 `switching_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SWITCH SAR 352

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000352_overlay.png`
- 近侧方向：`(0.332565,0.94308)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_half;body_long_positive_end;short_axis_middle;pixel=(128,65)`；`s_peak=0.451613`，峰数 `6`。
- 稳定/滑动/切换判断：该帧属于 `switching_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SWITCH SAR 353

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000353_overlay.png`
- 近侧方向：`(0.312524,0.94991)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_positive_end;body_short_positive_side;pixel=(126,69)`；`s_peak=0.387097`，峰数 `2`。
- 稳定/滑动/切换判断：该帧属于 `switching_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `HIGH`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SPLIT SAR 384

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000384_overlay.png`
- 近侧方向：`(-0.239448,0.970909)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_negative_end;body_short_positive_side;pixel=(36,75)`；`s_peak=0.612903`，峰数 `5`。
- 稳定/滑动/切换判断：该帧属于 `split_merge_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `MEDIUM`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SPLIT SAR 385

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000385_overlay.png`
- 近侧方向：`(-0.285011,0.958524)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_negative_end;body_short_positive_side;pixel=(33,76)`；`s_peak=0.83871`，峰数 `7`。
- 稳定/滑动/切换判断：该帧属于 `split_merge_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `MEDIUM`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_SPLIT SAR 386

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000386_overlay.png`
- 近侧方向：`(-0.276452,0.961028)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_negative_end;body_short_positive_side;pixel=(38,77)`；`s_peak=0.516129`，峰数 `8`。
- 稳定/滑动/切换判断：该帧属于 `split_merge_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `MEDIUM`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_DIFFICULT SAR 386

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000386_overlay.png`
- 近侧方向：`(-0.276452,0.961028)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_negative_end;body_short_positive_side;pixel=(38,77)`；`s_peak=0.516129`，峰数 `8`。
- 稳定/滑动/切换判断：该帧属于 `registration_mask_boundary_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `MEDIUM`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_DIFFICULT SAR 387

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000387_overlay.png`
- 近侧方向：`(-0.275353,0.961343)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_boundary;body_long_negative_end;body_short_positive_side;pixel=(24,73)`；`s_peak=0.516129`，峰数 `7`。
- 稳定/滑动/切换判断：该帧属于 `registration_mask_boundary_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `MEDIUM`；。
- 后续输运适合性：谨慎进入局部输运候选。

### W_DIFFICULT SAR 388

- 图像：`outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_sar000388_overlay.png`
- 近侧方向：`(-0.304321,0.952569)`；近侧边界能量高于远侧，近侧定位有局部迹象。
- 主响应位置：`near_half;body_middle;body_short_positive_side;pixel=(100,74)`；`s_peak=0.387097`，峰数 `6`。
- 稳定/滑动/切换判断：该帧属于 `registration_mask_boundary_review`，需要结合相邻帧差分；当前只能作为最小窗口证据。
- 配准和 mask 疑点：registration `LOW`；。
- 后续输运适合性：不适合进入输运，先处理配准/轴向可靠性。

## Frame Differences

- SAR 321 -> 323: `s_peak_delta=-0.129032`, gain near `0.126525`, loss near `0.074894`, hint `localized_gain_loss_reviewable`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_diff_sar000321_to_000323.png`.
- SAR 323 -> 325: `s_peak_delta=0.225806`, gain near `0.126124`, loss near `0.080574`, hint `localized_gain_loss_reviewable`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_diff_sar000323_to_000325.png`.
- SAR 339 -> 340: `s_peak_delta=0`, gain near `0.015033`, loss near `0.136539`, hint `possible_registration_or_whole-map_motion`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_diff_sar000339_to_000340.png`.
- SAR 340 -> 341: `s_peak_delta=-0.032258`, gain near `0.16231`, loss near `0.022512`, hint `localized_gain_loss_reviewable`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_diff_sar000340_to_000341.png`.
- SAR 351 -> 352: `s_peak_delta=0.16129`, gain near `0.008591`, loss near `0.230463`, hint `localized_gain_loss_reviewable`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_diff_sar000351_to_000352.png`.
- SAR 352 -> 353: `s_peak_delta=-0.064516`, gain near `0.144921`, loss near `0.020674`, hint `localized_gain_loss_reviewable`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_diff_sar000352_to_000353.png`.
- SAR 384 -> 385: `s_peak_delta=0.225807`, gain near `0.160271`, loss near `0.071921`, hint `possible_registration_or_whole-map_motion`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_diff_sar000384_to_000385.png`.
- SAR 385 -> 386: `s_peak_delta=-0.322581`, gain near `0.085544`, loss near `0.09492`, hint `localized_gain_loss_reviewable`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\vehicle_diff_sar000385_to_000386.png`.

## Counterfactuals

- `fixed_known_non_vehicle_N005` SAR 352: status `COUNTERFACTUAL_REVIEWABLE`, near fraction `0.063724`, location `near_half;body_middle;short_axis_middle;pixel=(68,48)`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\fixed_known_non_vehicle_N005_sar000352_overlay.png`.
- `fixed_strong_scatterer` SAR 352: status `COUNTERFACTUAL_REVIEWABLE`, near fraction `0.154557`, location `near_half;body_middle;short_axis_middle;pixel=(63,60)`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\fixed_strong_scatterer_sar000352_overlay.png`.
- `gt_attached_corridor_body_short` SAR 352: status `COUNTERFACTUAL_CONTAMINATED_BY_GT`, near fraction `0.062867`, location `near_boundary;body_long_positive_end;body_short_positive_side;pixel=(135,70)`, PNG `outputs\wgv3_6b_e0_r3_gm017_body_canonical_20260713\visual_review\gt_attached_corridor_body_short_sar000352_overlay.png`.
