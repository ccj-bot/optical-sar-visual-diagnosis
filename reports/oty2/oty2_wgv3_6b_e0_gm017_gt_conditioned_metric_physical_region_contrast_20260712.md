# WGV3.6B-E0 GM_RM017 GT-Conditioned Metric-Scale SAR Physical Region Contrast

## Conclusion

- `VEHICLE_REGION_PHYSICAL_SEPARABILITY_SUPPORTED`: `NOT_READY`
- `ABSOLUTE_SCALE_ADDS_DISCRIMINATIVE_VALUE`: `NOT_EVALUABLE`
- `E0_READY_FOR_GENERALIZATION`: `NOT_READY`
- E0 does not output a final vehicle box, selector, ranking, training signal, GT edit, or final annotation.
- SAR 371-394 is used only as a posthoc regression and mechanism-diagnosis window.

The current evidence does not support a stable vehicle-specific SAR physical separability claim. GT-near regions often have meaningful response, but the proof chain is blocked by unresolved metric mapping, unresolved true GT orientation, zero-valued mask proxy limits, and hard-negative/background controls that can approach vehicle-region energy or occupancy.

## Coordinate Mapping

- radar origin in image: fan center `(1154.0, 1330.6)` from `configs/scene_config.yaml`.
- local range axis: fan center to each GT center in image pixels.
- local azimuth axis: perpendicular to local range axis.
- pixel-to-meter conversion: `NOT_READY`; P0 `0.03` is only `p0_convention_m`, not validated metric scale.
- SAR resolution / PSF margin: `UNRESOLVED`; no resolution-corrected extent is asserted.

## GT Body Size Reference

- width px: median `165.5385`, q10 `152.452`, q90 `179.4448`.
- height px: median `74.6415`, q10 `68.7212`, q90 `80.5684`.
- area px2: median `12509.42252`, q10 `10786.125717`, q90 `13586.907506`.
- source: dataset-conditioned axis-aligned GT statistics, not external vehicle dimensions.

## Perturbation Results

- scale rows: `30` grouped curves; total energy and mean energy must be separated because larger regions can add background.
- translation rows: `36` grouped surface cells; best local-axis offsets observed in summaries: `local_azimuth=-0.25; local_range=-0.25`.
- rotation rows: `11` grouped angles; GT heading is unresolved, so rotation is an image-axis diagnostic.
- ring rows: `5`; rings provide explicit expanded-minus-GT background contrast.

## Hard Negatives And Ablation

- hard-negative/background confusion risks: `known_non_vehicle_same_area; linear_structure_background_same_area; strong_scatterer_background_same_area; near_background_same_area; far_background_same_area`.
- pixel-only and GT-normalized arms are evaluated; metric physical-scale arm is `NOT_EVALUABLE`.

| ablation | feature | effect | status | value |
| --- | --- | ---: | --- | --- |
| PIXEL_ONLY | mean_energy | 0.855452 | EVALUATED | LIMITED |
| PIXEL_ONLY | high_energy_pixel_fraction | 1.611219 | EVALUATED | LIMITED |
| PIXEL_ONLY | range_energy90_width_px | 0.123117 | EVALUATED | NOT_SUPPORTED |
| GT_NORMALIZED | range_energy90_width_px_div_gt_projected_range_extent_px | 0.13828 | EVALUATED | NOT_SUPPORTED |
| METRIC_PHYSICAL_SCALE | true_range_m_true_azimuth_m_resolution_corrected_extent |  | NOT_EVALUABLE | NOT_EVALUABLE |

## Mask And Visual Review

- mask definition: `UNRESOLVED_ZERO_VALUE_PROXY_ONLY`; zero-valued pixels are treated as a proxy only.
- `axes_gt_frame371` SAR371: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\axes_gt_frame371.png` - 坐标方向可见；米制比例未被验证，只能读作局部像素轴。
- `scale_regions_frame371` SAR371: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\scale_regions_frame371.png` - 缩放区域覆盖合理，但响应随面积扩大也会纳入背景，不能直接当作车辆尺度证明。
- `translation_regions_frame376` SAR376: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\translation_regions_frame376.png` - 平移网格显示高响应并非只在 GT 中心；需用衰减曲面而非单点峰值解释。
- `rotation_regions_frame381` SAR381: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\rotation_regions_frame381.png` - 旋转扰动可见，但 GT 未提供真实车头方向，角度只能解释为图像轴扰动。
- `directional_expansion_frame386` SAR386: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\directional_expansion_frame386.png` - 非对称扩展可见，新增区域含背景响应，不能自动解释为车体扩散。
- `ring_frame394` SAR394: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\ring_frame394.png` - 外环包含明显邻近背景，环带对照是必要的负证据。
- `background_controls_frame371` SAR371: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\background_controls_frame371.png` - 同面积背景控制能产生可观能量，是物理可分性 gate 的主要压力。
- `mask_contact_frame371` SAR371: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\mask_contact_frame371.png` - mask-edge 控制只说明 zero-valued proxy 接触，不能作为官方 mask 结论。
- `scale_curve_mean_energy` SAR: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\e0_scale_curve_mean_energy.png` - 尺度曲线显示总能量随区域变大容易增加；必须优先看单位面积和环带对照。
- `translation_heatmap_mean_energy` SAR: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\e0_translation_mean_energy_heatmap.png` - 平移热图用于检查峰值是否偏离 GT；不能作为选择器。
- `rotation_curve_principal_axis` SAR: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\e0_rotation_principal_axis_curve.png` - 主轴角与 GT 存储轴不稳定一致，真实车辆方向仍未解析。
- `n005_hard_negative_panel` SAR249: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\e0_n005_hard_negative_panel.png` - N005 强散射/线性结构能形成车辆尺度相近的局部响应，是 hard negative。
- `gt_vs_background_hard_negative_bar` SAR: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\e0_gt_vs_background_hard_negative_bar.png` - 强散射背景的平均能量可达到或超过 GT 区域，不能宣称车辆区域稳定可分。
- `principal_axis_vs_gt_direction_frame394` SAR394: `outputs\wgv3_6b_e0_gm017_metric_region_contrast_20260712\visual_review\e0_principal_axis_vs_gt_storage_axis.png` - SAR 主轴与 GT 存储轴存在明显差异；不能预设二者一致。

## Failure Ledger

| failure | severity | evidence | interpretation |
| --- | --- | --- | --- |
| metric_mapping_failure | high | pixel_to_range_meter_mapping=UNRESOLVED; pixel_to_azimuth_meter_mapping=UNRESOLVED; sar_resolution_m=UNRESOLVED | True metric-scale physical separability cannot be claimed. |
| gt_physical_size_inconsistency | medium | max_rotation_principal_axis_delta_mean=177.511364 | GT has axis-aligned boxes but no vehicle heading; front/rear and rotation tests remain storage-axis diagnostics. |
| mask_censoring | medium | max_gt_zero_proxy_contact=0 | Zero-valued pixels are only a proxy; mask-censored extents are not reliable metric extents. |
| hard_negative_scale_confusion | high | confusing_controls=known_non_vehicle_same_area;linear_structure_background_same_area;strong_scatterer_background_same_area;near_background_same_area;far_background_same_area | Known non-vehicle/background controls can approach vehicle-region energy or occupancy. |
| absolute_scale_not_discriminative | high | NOT_EVALUABLE | Absolute scale adds no evaluable discriminative value without an independent meter mapping. |
| vehicle_nonvehicle_not_separable | high | hard_negative/background controls and unresolved meter/mask/orientation gates prevent a supported separability claim | Do not promote high GT-region energy into a stable SAR vehicle physical mechanism. |

## Gates

| gate | status | evidence |
| --- | --- | --- |
| WORKTREE_BRANCH_VALID | PASS | branch=feature/oty2-gm017-physical-factor-discovery;head=593f89894d36dfcf8da1a7a2d97c1d24355ef39f |
| P0_D1_D1_R1_FROZEN_UNCHANGED | PASS | P0=git diff --quiet 1a3edd9 -- P0 frozen artifact paths; D1=git diff --quiet 57a82b1 -- D1 frozen artifact paths; D1_R1=git diff --quiet 593f898 -- D1_R1 frozen artifact paths |
| PRE_EVAL_SEAL_VALID | PASS | seal ok |
| FROZEN_REPLAY_IDENTICAL | PASS | replay_rows=8 |
| METRIC_COORDINATE_MAPPING_AVAILABLE | NOT_READY | pixel_to_range_meter_mapping and pixel_to_azimuth_meter_mapping unresolved |
| RADAR_ORIGIN_PROVENANCE_VALID | PASS | fan center from configs/scene_config.yaml: 1154.0,1330.6 |
| RANGE_AZIMUTH_AXES_VALID | PASS | local pixel range axis fan-center-to-GT-center and perpendicular azimuth axis generated per frame |
| PIXEL_TO_METER_CONVERSION_VALID | NOT_READY | P0 0.03 is recorded as p0_convention_m only |
| GT_METRIC_SIZE_TEMPORALLY_STABLE | PASS_PIXEL_AND_P0_CONVENTION_ONLY | GT width/height stable in pixels; true meters NOT_EVALUABLE |
| BODY_SIZE_REFERENCE_FROZEN | PASS | reports\oty2\samples\oty2_wgv3_6b_e0_gm017_vehicle_body_size_reference_20260712.csv |
| BODY_LENGTH_COMPATIBILITY_IMPLEMENTED | PASS | length/width/area ratios are recorded in region manifest and feature table |
| BODY_WIDTH_COMPATIBILITY_IMPLEMENTED | PASS | same |
| BODY_AREA_COMPATIBILITY_IMPLEMENTED | PASS | area_ratio_to_gt recorded for every region |
| RESPONSE_EXTENT_SEPARATED_FROM_BODY_EXTENT | PASS | feature table records response support widths separately from GT body extents |
| PERTURBATION_GRID_FROZEN | PASS | region_count=7272; family_counts={'GT_ORIGINAL': 72, 'SCALE': 2160, 'DIRECTIONAL_EXPANSION': 504, 'INTERNAL_CROP': 432, 'TRANSLATION': 2592, 'ROTATION': 792, 'RING': 288, 'BACKGROUND_CONTROL': 432} |
| SCALE_COMPARISON_COMPLETE | PASS | scale_regions=2160 |
| TRANSLATION_COMPARISON_COMPLETE | PASS | translation_regions=2592 |
| ROTATION_COMPARISON_COMPLETE | PASS | rotation_regions=792 |
| DIRECTIONAL_EXPANSION_COMPLETE | PASS | directional_regions=504 |
| RING_COMPARISON_COMPLETE | PASS | ring_regions=288 |
| SAME_AREA_BACKGROUND_COMPLETE | PASS | background_regions=432 |
| HARD_NEGATIVE_COMPARISON_COMPLETE | PASS | reports\oty2\samples\oty2_wgv3_6b_e0_gm017_hard_negative_comparison_20260712.csv |
| AREA_NORMALIZATION_COMPLETE | PASS | mean_energy/high_energy_fraction/occupancy retained alongside total_energy |
| PIXEL_GT_NORMALIZED_METRIC_ABLATION_COMPLETE | PASS | pixel and GT-normalized evaluated; metric arm explicitly NOT_EVALUABLE |
| MASK_CENSORING_AUDIT_COMPLETE | PASS | reports\oty2\samples\oty2_wgv3_6b_e0_gm017_mask_censoring_audit_20260712.csv |
| TEMPORAL_STABILITY_AUDIT_COMPLETE | PASS | target_gt_rows=72;unique_sar_frames=71;SAR336 has two GT rows |
| VISUAL_REVIEW_GROUNDED | PASS | visual_rows=14 |
| VEHICLE_REGION_PHYSICAL_SEPARABILITY_SUPPORTED | NOT_READY | hard negatives/background controls and metric-mapping gap prevent a supported claim |
| ABSOLUTE_SCALE_ADDS_DISCRIMINATIVE_VALUE | NOT_EVALUABLE | true metric mapping and SAR resolution unavailable |
| E0_READY_FOR_GENERALIZATION | NOT_READY | E0 is GM_RM017 posthoc diagnosis; absolute metric and hard-negative gates are not closed |

## Direct Answer

The GT vehicle geometry region does not yet show a stable, metric-scale, vehicle-specific SAR physical response structure that is separable from surrounding and difficult non-vehicle regions. The safest current interpretation is `ambiguous_or_censored` for the mechanism-level claim: GT-near SAR response exists, but the complete proof chain of reasonable body scale, imaging-width allowance, GT-near concentration, controlled translation decay, direction-related structure, temporal stability, and hard-negative rejection is not closed.
