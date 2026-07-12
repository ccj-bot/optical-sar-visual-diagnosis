# WGV3.6B-E0-R1 GM_RM017 Metric-Heading Physical Region Contrast Repair

## Conclusion

- `CURRENT_CONFIG_METRIC_GRID_VALID`: `PASS`
- `PIXEL_TO_METER_CONVERSION_VALID`: `PASS_CURRENT_IMAGING_CONFIG`
- `PSF_CORRECTED_PHYSICAL_EXTENT_READY`: `NOT_READY`
- `BODY_AXIS_REFERENCE_AVAILABLE`: `PASS_PROXY_HIGH_CONF`
- `BODY_SUPPORT_MODEL_IDENTIFIABLE`: `PASS`
- `E0_R1_PHYSICAL_SEPARABILITY_SUPPORTED`: `NOT_READY`
- `E0_R1_READY_FOR_CROSS_SCENE_VALIDATION`: `NOT_READY`

E0-R1 corrects the E0 metric wording: the current image grid supports raw metric-image extents, but SAR range/azimuth resolution and PSF-corrected physical target dimensions remain unresolved. The stage remains GT-conditioned posthoc diagnosis and produces no selector, ranker, final box, annotation, GT edit, or training signal.

## Body Axis And Support

- body-axis source: `PASS_PROXY_HIGH_CONF` from SAR motion-heading proxy.
- body-support fit: `PASS`; L=`4.764934` m grid, W=`2.077648` m grid; source=`SAR_MOTION_HEADING_PROXY_CALIBRATION_FIT`.
- optical paired frames are rendered only for straight/turning plausibility; no optical image angle is copied into SAR.

## Paired Contrast

- paired rows: `54`.
- median fraction vehicle higher on local-background-normalized energy: `0.894366`.
- paired comparison is within-frame vehicle region versus matched same-frame controls; global class means are not used as the primary proof.

## Translation Structure

- translation surface rows: `284`.
- near-GT peak/plateau fraction across range/azimuth/body axes: `1`.
- a stable offset toward radar-near or one body side is recorded as a physical pattern, not forced to the GT geometric center.

## Hard Negatives

- multi-gate physical confusion rows: `0`.
- single-feature energy-confusion-only rows: `414`.
- E0's broad `mean_energy OR occupancy` confusion rule is replaced by the independent Gate matrix. A hard negative matching only mean energy is not called physical inseparability.

## Visual Review

- `metric_grid_closure_frame371` SAR371: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\metric_grid_closure_frame371.png` - 结论：网格可用；分辨率未就绪。
- `sar_range_azimuth_axes_frame371` SAR371: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\sar_range_azimuth_axes_frame371.png` - 结论：距离方位轴可用；仅作诊断。
- `motion_heading_fit` SAR: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\motion_heading_fit.png` - 结论：高置信航向进入主分析。
- `paired_optical_straight_turning_review` SAR: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\paired_optical_straight_turning_review.png` - 结论：光学只判断直行转弯。
- `body_support_fit` SAR: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\body_support_fit.png` - 结论：车体支撑由校准段冻结。
- `body_aligned_regions_frame371` SAR371: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\body_aligned_regions_frame371.png` - 结论：车体对齐区域合理。
- `metric_translation_surface_frame376` SAR376: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\metric_translation_surface_frame376.png` - 结论：平移面保留近GT平台。
- `body_axis_relative_rotations_frame381` SAR381: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\body_axis_relative_rotations_frame381.png` - 结论：零度为车体轴对齐。
- `gt_vs_rings_frame394` SAR394: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\gt_vs_rings_frame394.png` - 结论：环带检验邻近背景。
- `matched_moving_controls_frame371` SAR371: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\matched_moving_controls_frame371.png` - 结论：匹配背景提供压力。
- `fixed_hard_negative_frame371` SAR371: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\fixed_hard_negative_frame371.png` - 结论：固定负例单独保留。
- `n005_fixed_hard_negative_panel` SAR249: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\n005_fixed_hard_negative_panel.png` - 结论：N005为已知非车辆。
- `successful_vehicle_separation_frame` SAR373: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\successful_vehicle_separation_frame.png` - 结论：该帧车辆更集中。
- `failure_confusion_frame` SAR336: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\failure_confusion_frame.png` - 结论：该帧负例压力强。
- `heading_unreliable_frame` SAR325: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\heading_unreliable_frame.png` - 结论：低置信航向已排除。
- `registration_suspected_frame` SAR336: `outputs\wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_20260712\visual_review\registration_suspected_frame.png` - 结论：能量偏移作为发现。

## Failure Ledger

| failure | severity | evidence | interpretation |
| --- | --- | --- | --- |
| psf_or_resolution_corrected_extent_unresolved | medium | SAR_RANGE_RESOLUTION_AVAILABLE=NOT_READY; SAR_AZIMUTH_RESOLUTION_AVAILABLE=NOT_READY | Raw image-grid metric extents are available, but PSF-corrected physical dimensions are not claimed. |
| body_support_model_identifiability | low | status=PASS;condition=1.065359;q90_residual=0.330216 | Heading-constrained support is used only if calibration fit is identifiable; otherwise axis-aligned fallback remains explicit. |
| near_gt_translation_structure | low | near_gt_peak_or_plateau_fraction=1 | Translation surfaces support the claim only when near-GT plateau is stable across axes and frames. |
| matched_control_pressure | low | median_fraction_vehicle_higher_local_bg_norm=0.894366 | Within-frame controls are the primary non-vehicle pressure; global class means are secondary. |
| single_feature_energy_confusion_only | medium | single_feature_rows=414;multi_gate_confusions=0 | High mean energy alone is not treated as physical inseparability. |

## Gates

| gate | status | evidence |
| --- | --- | --- |
| WORKTREE_BRANCH_VALID | PASS | branch=feature/oty2-gm017-physical-factor-discovery;head=ae70bde7cc4ae3710ce79029c38cba283b04b534 |
| START_COMMIT_ANCESTRY_VALID | PASS | ae70bde7cc4ae3710ce79029c38cba283b04b534 |
| P0_D1_D1_R1_E0_FROZEN_UNCHANGED | PASS | P0=git diff --quiet 1a3edd9 -- P0 frozen artifact paths; D1=git diff --quiet 57a82b1 -- D1 frozen artifact paths; D1_R1=git diff --quiet 593f898 -- D1_R1 frozen artifact paths; E0=git diff --quiet ae70bde -- E0 frozen artifact paths |
| PRE_EVAL_SEAL_VALID | PASS | seal ok |
| FROZEN_REPLAY_IDENTICAL | PASS | replay_rows=7 |
| CURRENT_CONFIG_METRIC_GRID_VALID | PASS | 40m maximum range; 0.03m/px image grid; 2308x1334 canvas |
| PIXEL_TO_METER_CONVERSION_VALID | PASS_CURRENT_IMAGING_CONFIG | current imaging configuration only |
| PSF_CORRECTED_PHYSICAL_EXTENT_READY | NOT_READY | SAR range/azimuth resolution metadata unresolved |
| BODY_AXIS_REFERENCE_AVAILABLE | PASS_PROXY_HIGH_CONF | high_confidence_frames=43 |
| MOTION_HEADING_PROXY_VALID | PASS | high_confidence_diagnosis_frames=9 |
| BODY_SUPPORT_MODEL_IDENTIFIABLE | PASS | source=SAR_MOTION_HEADING_PROXY_CALIBRATION_FIT;L=4.764934;W=2.077648 |
| CALIBRATION_DIAGNOSIS_SEPARATION_VALID | PASS | heading thresholds and body-support fit frozen from SAR<=360; guard not fit; diagnosis not retuned |
| MATCHED_BACKGROUND_CONTROLS_VALID | PASS | control_rows=432;no_overlap=True |
| WITHIN_FRAME_PAIRED_CONTRAST_COMPLETE | PASS | paired_rows=54 |
| HARD_NEGATIVE_MULTI_GATE_COMPLETE | PASS | gate_rows=576;physical_confusions=0 |
| TEMPORAL_PHYSICAL_CONSISTENCY_COMPLETE | PASS | temporal_rows=7 |
| VISUAL_REVIEW_GROUNDED | PASS | visual_rows=16 |
| VEHICLE_METRIC_SCALE_PATTERN_SUPPORTED | SUPPORTED | vehicle_principal_gate_fraction=1 |
| VEHICLE_SPATIAL_CONCENTRATION_SUPPORTED | SUPPORTED | median_fraction_vehicle_higher_local_bg_norm=0.894366 |
| VEHICLE_DIRECTIONAL_STRUCTURE_SUPPORTED | NOT_READY | directional_gate_fraction=0.138889;high_diag=9 |
| VEHICLE_HARD_NEGATIVE_REJECTION_SUPPORTED | SUPPORTED | multi_gate_confusions=0;paired_higher=0.894366 |
| E0_R1_PHYSICAL_SEPARABILITY_SUPPORTED | NOT_READY | requires metric scale + concentration + direction + temporal + hard-negative rejection |
| E0_R1_READY_FOR_CROSS_SCENE_VALIDATION | NOT_READY | same-scene posthoc only; cross-scene validation requires frozen transport package |

## Direct Answer

Under the current 40 m and 0.03 m-per-pixel imaging configuration, the vehicle GT neighbourhood does show raw image-grid metric-scale response evidence, stable near-GT translation/plateau evidence, and stronger within-frame paired contrast than the matched controls. The difficult non-vehicle regions do not reproduce the full multi-Gate vehicle pattern; most hard-negative pressure is `single_feature_energy_confusion_only`. However, the body/range directional structure gate remains `NOT_READY`, and SAR range/azimuth resolution plus PSF-corrected physical extent remain unresolved. Therefore the complete question is answered as `E0_R1_PHYSICAL_SEPARABILITY_SUPPORTED=NOT_READY`, not as a final supported physical separability claim.
