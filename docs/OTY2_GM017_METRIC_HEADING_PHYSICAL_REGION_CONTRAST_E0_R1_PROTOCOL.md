# OTY2 GM_RM017 Metric-Heading Physical Region Contrast E0-R1 Protocol

Updated: 2026-07-12

This protocol defines `WGV3.6B-E0-R1 GM_RM017 Metric-Scale, Heading-Constrained Physical Region Contrast Repair`.
It is a narrow correction layer over E0. It does not overwrite P0, D1, D1_R1, or E0 artifacts, and it does not create
a selector, ranker, final vehicle box, final annotation, GT modification, training signal, or fresh holdout claim.

## Corrected Metric Semantics

The current imaging configuration is internally consistent with a 40 m maximum imaging range and a 0.03 m/px image grid.
Therefore E0-R1 separates three concepts:

- `METRIC_IMAGE_GRID_MAPPING_AVAILABLE=PASS`
- `PIXEL_TO_METER_CONVERSION_VALID=PASS_CURRENT_IMAGING_CONFIG`
- `RAW_METRIC_IMAGE_EXTENT_AVAILABLE=PASS`
- `SAR_RANGE_RESOLUTION_AVAILABLE=NOT_READY`
- `SAR_AZIMUTH_RESOLUTION_AVAILABLE=NOT_READY`
- `PSF_CORRECTED_PHYSICAL_EXTENT_READY=NOT_READY`

The 0.03 m/px grid interval is not called SAR range resolution or SAR azimuth resolution.

## Split And Non-Circularity

The P0 split is preserved:

- Calibration: SAR `<=360`
- Guard: SAR `361-370`
- Posthoc diagnosis: SAR `371-394`

Body-support fitting, heading-confidence thresholds, Gate definitions, and Gate thresholds are frozen from calibration
frames only. Guard frames are not used for fitting. SAR `371-394` is evaluated with the frozen definitions only and remains
a same-scene posthoc diagnosis window.

## Body-Axis Reference

E0-R1 first audits true body-axis sources. If camera-radar extrinsic calibration, ground-plane homography, rotated SAR GT,
vehicle world heading, or pose metadata is unavailable, it derives `SAR_MOTION_HEADING_PROXY` from the SAR GT center
trajectory. Optical paired images may be rendered for visual review of straight/turning/reversing plausibility, but optical
image angles are not copied into the SAR plane.

Each frame records:

- `sar_motion_heading_deg`
- `fit_residual_px`
- `trajectory_curvature_deg`
- `speed_px_per_frame`
- `heading_confidence`
- `body_axis_source`

Only `HIGH` confidence motion-heading proxy frames enter the main heading analysis.

## Body-Support Model

Using calibration frames only, E0-R1 attempts to fit:

```text
bbox_width  ~= L |cos theta| + W |sin theta|
bbox_height ~= L |sin theta| + W |cos theta|
```

where `theta` is the SAR-plane body-axis proxy and `L >= W > 0`. If the model is ill-conditioned or residuals are too
large, E0-R1 falls back to a dataset-conditioned axis-aligned metric support reference and reports
`BODY_SUPPORT_MODEL_IDENTIFIABLE=NOT_READY`.

## Region Families

E0-R1 retains the axis-aligned GT baseline and adds:

- body-axis-aligned reference regions;
- same-center body-scale variants;
- range/azimuth metric translations;
- body-long/body-short metric translations;
- body-axis-relative rotations;
- radar-near/radar-far expansions;
- body-positive/body-negative expansions;
- GT expansion rings;
- same-frame matched moving controls with same area, aspect ratio, orientation, similar radar range, and no GT overlap;
- fixed hard negatives: strong scatterer, linear structure, ordinary background, and known non-vehicle N005.

Each offset records pixels, metres, fraction of body length, and fraction of body width. Rotation zero degrees means
body-axis alignment.

## Gate Matrix

E0-R1 uses independent Gate vectors, not weighted scores and not the E0 single-feature OR confusion rule.

Required Gates:

- `G1_VALID_OBSERVATION`
- `G2_METRIC_SIZE_COMPATIBLE`
- `G3_NOT_POINTLIKE`
- `G4_NOT_LONG_LINEAR`
- `G5_COMPACT_EXTENDED_SUPPORT`
- `G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE`
- `G7_GT_NEAR_TRANSLATION_STRUCTURE`
- `G8_BODY_OR_RANGE_AXIS_STRUCTURE_COMPATIBLE`
- `G9_TEMPORAL_PATTERN_CONSISTENT`
- `G10_STATIC_BACKGROUND_EXPLANATION_REJECTED`

A hard negative is a true physical confusion case only if it satisfies essentially the same principal Gate pattern as the
vehicle. If it only matches mean energy, E0-R1 reports `single_feature_energy_confusion_only`.

## Output Boundary

The required commands are:

```powershell
D:\MINICONDA\envs\py311\python.exe -m py_compile tools\diagnostics\run_oty2_wgv3_6b_e0_r1_gm017_metric_heading_region_generate.py tools\diagnostics\run_oty2_wgv3_6b_e0_r1_gm017_metric_heading_region_evaluate.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_e0_r1_gm017_metric_heading_region_generate.py generate
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_e0_r1_gm017_metric_heading_region_generate.py verify-replay
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_e0_r1_gm017_metric_heading_region_evaluate.py evaluate
```

There is no combined `all` command.

PNG visual diagnostics are generated under ignored `outputs/` paths and must not be committed.
