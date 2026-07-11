# OTY2 WGV3.5A-R2C SAR Mask Definition

## Summary

- independent mask file: not found in checked repo/data paths
- reconstructed mask: fan geometry from code, `radial<=1332.7` and `-90<=azimuth<=90` on `2308x1334`
- rendered PNG support: sampled GM_RM019 gray frames show stable zero outside the fan-like support
- physical meaning: geometry/display valid fan is confirmed; independent physical imaging-valid mask semantics remain unconfirmed
- annotation use: not explicitly documented; current SAR boxes stay inside rendered valid pixels

## Source Inventory

|source_type|source_path|mask_shape|sar_shape|static_or_dynamic|generation_rule|physical_meaning|used_during_annotation|used_during_png_generation|outside_value|confidence|open_question|mask_reconstructed_from_code|estimated_visual_mask_only|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|independent_mask_file_search|D:\profile\research\optical-sar-visual-diagnosis\outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_16_pair_mask_contact_sheet.png;D:\profile\research\optical-sar-visual-diagnosis\outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_azimuth_residual_vs_mask_distance.png;D:\profile\research\optical-sar-visual-diagnosis\outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_gm019_vehicle_sar_trajectory_vs_mask.png;D:\profile\research\optical-sar-visual-diagnosis\outputs\wgv3_5a_r2c_mask_aware_20260711\r2c_sar_mask_overview.png;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_gt_reference_mask_audit_20260703_151500.csv;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wgv3_5a_r2c_gm019_mask_supervision_gate_20260711.md;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wgv3_5a_r2c_mask_aware_closure_20260711.md;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wgv3_5a_r2c_mask_aware_visual_diagnosis_20260711.md;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wgv3_5a_r2c_sar_mask_definition_20260711.md;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_wgv3_3c_support_mask_frame_summary_20260710.csv;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_mask_aware_intervals_20260711.csv;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv;D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_wgv3_5a_r2c_sar_mask_source_inventory_20260711.csv;D:\profile\research\optical-sar-visual-diagnosis\tools\diagnostics\run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.py;D:\profile\research\optical-sar-visual-diagnosis\tools\diagnostics\__pycache__\run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.cpython-311.pyc|unverified|2308x1334|unknown_without_external_mask_file|searched names: mask, valid_mask, valid_region, fan_mask, sector_mask, sar_mask, roi_mask, effective_mask, valid_pixel, valid_area|no independent physical mask file confirmed|unknown|unknown|unknown|high_for_absence_of_named_file;low_for_physical_semantics|whether a MATLAB/imaging-time physical-valid mask exists outside the checked repo/data directories|false|false|
|fan_geometry_reconstructed_from_code|tools/diagnostics/run_oty2_wgv3_3c_non_gt_sar_response.py:432-444; tools/diagnostics/run_oty2_wgv3_3d_local_sar_response_components.py; tools/diagnostics/run_oty2_wgv3_5a_r2_gm019_real_truncation.py|1334x2308|2308x1334|static_formula_shared_by_checked_scenes|radial<=1332.7 and -90<=atan2(x-1154,1330.6-y)<=90 on 2308x1334 canvas|SAR fan display/geometry support; physical imaging-valid semantics not independently proven|not explicitly documented; annotations are inside the rendered SAR PNG fan support|consistent_with_gray_PNG_zero_outside_fan|0 in sampled gray PNG outside fan|medium|does this display fan equal the physical valid mask used by annotation|true|false|
|GM_RM019_gray_png_stable_nonzero_support|D:\profile\research\data\GM_RM019\GM_RM019_SARframes_gray|1334x2308|2308x1334|sampled_54_of_766_frames;nonzero_ratio=0.606073-0.608151|diagnostic stable support = sampled pixels nonzero in at least 95% of sampled frames, intersected with fan geometry|estimated_visual_mask_only; useful for zeroed PNG support, not sufficient to prove physical-valid area|unknown|yes_as_observed_zero/nonzero_pattern|0 for stable outside/fan-exterior pixels|medium_for_rendered_png_support;low_for_physical_mask_semantics|stable_count=1860594;fan_count=2628414;fixed_black_inside_fan=751132|false|true|

## R2C.M0 Answers

1. 独立有效mask文件：未找到。
2. 是否场景共用：代码公式看起来共用，独立场景版本未找到。
3. 是否随帧变化：扇形公式静态；PNG非零支持在抽样帧中基本静态。
4. 是否来自成像物理有效区：未被独立文件或成像MATLAB代码证明，只能确认显示/几何有效扇形。
5. 是否只是显示裁剪：当前证据更接近显示/几何裁剪；物理语义保留问题。
6. 是否参与SAR标注：未找到标注文档说明；人工框没有延伸出渲染有效区域。
7. mask外像素语义：抽样灰度PNG中为0；是未成像、无效还是渲染置零不能最终区分。
8. SAR人工框是否允许延伸到mask外：当前16条GM_RM019框未延伸到重建mask外，是否允许未知。