# OTY2 S0-M SAR Coordinate, Grid, and Imaging-Mask Contract

Date: `2026-07-15`
Status: `DISPLAY_FAN_COORDINATE_AND_IMAGING_VALID_MASK_FROZEN_METRIC_GRID_BLOCKED`

## 1. Frozen display coordinate

The `2308 x 1334` SAR PNG is a Cartesian display canvas with a reproducible fan-polar interpretation:

```text
r_px = hypot(x - 1154.0, y - 1330.6)
theta_deg = atan2(x - 1154.0, 1330.6 - y)
x = 1154.0 + r_px * sin(theta)
y = 1330.6 - r_px * cos(theta)
```

Display `x` increases right, display `y` increases down, and radial distance increases away from the bottom-center origin. This contract does not assert a uniform Cartesian `m/px` grid. Tangential metric width still depends on range and azimuth.

## 2. Frozen `imaging_valid_mask`

The deterministic imaging-valid support is the canvas-clipped shared fan:

```text
canvas = 2308 x 1334
origin = (1154.0, 1330.6)
radius_px = 1332.7
valid = r_px <= 1332.7 and -90 deg <= theta_deg <= 90 deg
```

- pixel count: `2,628,412`;
- canvas fraction: `0.8536931707456497`;
- packed-bit SHA-256: `7bdfbc5417db5f96405751d7503973f16db85957cf9aa0c6a8f30975cc0502ef`;
- scenes: `GM_RM011`, `GM_RM017`, `GM_RM019`;
- verified frame binding: `766` frames per scene, `2,298` frame indices total;
- result: the generation parameters and mask hash are identical for every scene/frame binding.

This mask is a fixed imaging-chain contract. It is not a learned vehicle mask, not a per-frame threshold, and not a claim that the full canvas has a solved physical metric grid.

## 3. Mask semantics that must remain separate

- `imaging_valid_mask`: fixed valid imaging support defined above.
- `fixed_black_region_inside_mask`: pixels that are zero in all 766 gray frames of one scene while still inside `imaging_valid_mask`.
- `display_nonzero_mask`: per-frame `gray_scalar > 0` display support.
- `gt_box_region`: reviewed rotated GT evaluation region.
- `gt_valid_intersection_mask`: `gt_box_region AND imaging_valid_mask`.
- `vehicle_response_mask`: not established in S0-M; it must not be replaced by a GT box or bright-pixel threshold.

| scene | fixed black inside mask | fraction of valid mask | per-frame nonzero pixels |
| --- | ---: | ---: | ---: |
| GM_RM011 | 749,541 | 0.285169 | 1,865,902..1,873,468 |
| GM_RM017 | 749,427 | 0.285125 | 1,866,198..1,871,943 |
| GM_RM019 | 749,903 | 0.285306 | 1,866,020..1,873,334 |

The fixed black regions differ slightly by scene and remain empirical display/no-response facts inside a common valid support. They do not redefine the valid mask.

## 4. GT relation to the valid mask

All `442` reviewed GT rows were rasterized as rotated rectangles and intersected with the frozen mask. Results:

- `gt_clipped_by_valid_mask = true`: `0`;
- `gt_touches_valid_mask_boundary = true`: `0`;
- all 442 rows have `gt_valid_mask_fraction = 1.0`.

Mask-clipped and mask-boundary diagnostic subsets are therefore empty for the current GT corpus. The fields remain mandatory because later data may exercise them.

## 5. Metric-grid boundary

No current-scene ADC/IQ, range-compressed array, complex image matrix, acquisition configuration, imaging configuration, maximum physical range, PRF/aperture definition, or authoritative pixel-to-meter grid generator was located. The historical `0.03 m/pixel` is retained only as a project/local radial grid-spacing claim. It is not accepted as:

- uniform full-image Cartesian scale;
- range or azimuth resolution;
- PSF/main-lobe width;
- actual vehicle-structure resolving power.

Metric GT dimensions and metric mapping errors remain blank. `imaging_valid_mask` is frozen; the uniform physical metric grid is not.

## 6. Permitted use

Later calibration and search-corridor construction must intersect all SAR regions with `imaging_valid_mask`. Mask-exterior pixels are forbidden inputs. GT remains a research/evaluation anchor, not a runtime vehicle-response mask.
