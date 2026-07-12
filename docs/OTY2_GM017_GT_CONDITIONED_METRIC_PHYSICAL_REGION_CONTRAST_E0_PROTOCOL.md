# OTY2 GM_RM017 GT-Conditioned Metric-Scale SAR Physical Region Contrast E0 Protocol

Updated: 2026-07-12

This protocol defines `WGV3.6B-E0 GM_RM017 GT-Conditioned Metric-Scale SAR Physical Region Contrast`.
It is a GT-conditioned posthoc physical-region contrast, not a selector, ranker, detector, training stage,
final vehicle box stage, GT modification stage, or fresh holdout claim.

## Boundary

E0 may use SAR GT to generate controlled physical reference regions, body-size references, perturbations,
background controls, and posthoc physical contrast tables. GT is not treated as a SAR scattering center truth,
energy-center truth, final output, or automatic answer.

SAR `371-394` remains a regression and mechanism-diagnosis window. It is not renamed as a fresh holdout set.

The only region-level conclusions allowed by this stage are:

- `vehicle_region_physically_supported`
- `non_vehicle_region_physically_supported`
- `ambiguous_or_censored`

These are physical-evidence interpretations for controlled regions, not final detection labels.

## Input Availability Audit

| item | status | source | consequence |
| --- | --- | --- | --- |
| `radar_origin_in_image` | `AVAILABLE_AS_FAN_CENTER` | `configs/scene_config.yaml`, fan center `(1154.0, 1330.6)` | local pixel range/azimuth axes can be defined around each GT center |
| `pixel_to_range_meter_mapping` | `UNRESOLVED` | no reliable independent calibration found | true `range_m` is not evaluated |
| `pixel_to_azimuth_meter_mapping` | `UNRESOLVED` | no reliable independent calibration found | true `azimuth_m` is not evaluated |
| `range_axis_direction` | `AVAILABLE_AS_LOCAL_PIXEL_AXIS` | vector from fan center to GT center | valid for local pixel-axis contrast only |
| `azimuth_axis_direction` | `AVAILABLE_AS_LOCAL_PIXEL_AXIS` | perpendicular to local range axis | valid for local pixel-axis contrast only |
| `image_projection_type` | `UNRESOLVED` | SAR PNG/fan geometry exists; projection metadata absent | absolute physical scale conclusions are blocked |
| `sar_resolution_range_m` | `UNRESOLVED` | no resolution metadata found | PSF or resolution-corrected extent cannot be asserted |
| `sar_resolution_azimuth_m` | `UNRESOLVED` | no resolution metadata found | PSF or resolution-corrected extent cannot be asserted |
| `mask_definition` | `UNRESOLVED_ZERO_VALUE_PROXY_ONLY` | observed SAR PNG zero-valued pixels | mask contact is a proxy audit, not an official mask |
| `gt_orientation_source` | `UNRESOLVED_AXIS_ALIGNED_BBOX_ONLY` | paired annotation CSV has axis-aligned SAR boxes and no vehicle heading field | front/rear and long/short-axis tests are storage-axis tests, not vehicle-heading truth |
| `vehicle_dimension_metadata` | `UNRESOLVED_DATASET_CONDITIONED_GT_STATS_ONLY` | no external vehicle dimensions found | body-size reference is dataset-conditioned, not universal vehicle size |

The P0 script records `px_to_m=0.03`. E0 treats this only as `p0_convention_m`, not as a validated metric mapping.
Therefore:

- `METRIC_COORDINATE_MAPPING_AVAILABLE=NOT_READY`
- `PIXEL_TO_METER_CONVERSION_VALID=NOT_READY`
- `ABSOLUTE_SCALE_ADDS_DISCRIMINATIVE_VALUE=NOT_EVALUABLE`

## Frozen Coordinate Rules

For every GT center, E0 defines:

- local range axis: unit vector from the fan center to the GT center in image pixels;
- local azimuth axis: the perpendicular local pixel axis;
- pixel offsets: `local_range_offset_px`, `local_azimuth_offset_px`;
- optional convention fields: `*_p0_convention_m`, computed only with the inherited P0 `0.03` convention.

Fields named true meters are left unavailable or marked `NOT_EVALUABLE` unless an independent mapping is later added.

## Region Grid

The frozen perturbation grid includes:

- `GT_ORIGINAL`
- same-center uniform, range-only, azimuth-only, storage-long-axis-only, and storage-short-axis-only scaling
- symmetric, near-side, far-side, positive-azimuth, negative-azimuth, storage-front, and storage-rear expansion
- near/far half, storage-front/rear half, center core, and boundary band
- same-area translations along image x/y, local range/azimuth, and storage long/short axes
- same-center rotations relative to image axes
- GT expansion rings: 10%, 25%, 50%, 100%
- same-area background controls: near, far, strong scatterer, linear structure, mask-edge, and N005 known non-vehicle

The grid is fixed before evaluation and is not retuned from vehicle/background contrast results.

## Feature Definitions

Each region records total, per-area, structural, scale, and censoring features:

- energy statistics: total, mean, median, standard deviation, peak, q90, q95, q99
- high-energy count/fraction and occupancy
- connected high-energy component count and peak count
- energy centroid and local range/azimuth offset
- principal axis and range/azimuth support widths
- energy90 and second-moment extents
- near/far and storage-front/rear energy ratios
- inside-GT and ring contrast
- zero-valued proxy contact, boundary contact, visible fraction, and metric reliability status

No aggregate weighted score is produced.

## Required Commands

```powershell
D:\MINICONDA\envs\py311\python.exe -m py_compile tools\diagnostics\run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_generate.py tools\diagnostics\run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_evaluate.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_generate.py generate
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_generate.py verify-replay
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_evaluate.py evaluate
```

There is no combined `all` command.

## Success Semantics

`VEHICLE_REGION_PHYSICAL_SEPARABILITY_SUPPORTED=SUPPORTED` is allowed only if vehicle regions show stable,
GT-near spatial support, controlled translation decay, meaningful directional/rotation structure, temporal stability,
and hard negative/background regions cannot satisfy the same physical explanation.

If hard negatives or same-area backgrounds can produce comparable energy/structure, if mask/projection/metric mapping
is unresolved, or if gains exist only in total energy, the correct conclusion is `NOT_READY`.

`E0_READY_FOR_GENERALIZATION=PASS` requires metric mapping validity or a documented non-metric reason why E0 conclusions
remain generalizable. With the current input audit, this gate is expected to remain `NOT_READY`.
