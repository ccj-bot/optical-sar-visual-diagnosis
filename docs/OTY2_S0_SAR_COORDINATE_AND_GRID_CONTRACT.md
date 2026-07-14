# OTY2 S0 SAR Coordinate and Grid Contract

Date: `2026-07-15`
Status: `PARTIAL_DISPLAY_COORDINATE_CONFIRMED_METRIC_GRID_BLOCKED`

## Frozen conclusion

The `2308×1334` files are a Cartesian **display pixel canvas** containing a fan-shaped raster. The display canvas supports a reproducible fan-polar interpretation with origin `(1154.0, 1330.6)` and radius `1332.7 px`. This does not prove the upstream SAR imager produced a Cartesian metric grid, nor does it prove a uniform metric scale in either display axis.

The only frozen transforms are:

```text
r_px = hypot(x - 1154.0, y - 1330.6)
theta_deg = atan2(x - 1154.0, 1330.6 - y)
x = 1154.0 + r_px * sin(theta)
y = 1330.6 - r_px * cos(theta)
```

- display `x` increases right;
- display `y` increases down;
- radial distance increases away from the bottom-center origin;
- local tangential direction changes with `theta` and range;
- no uniform full-image `m/px` is allowed.

## Why metric coordinates are not frozen

No current-scene ADC/IQ, range-compressed array, complex image matrix, acquisition configuration, imaging configuration, grid-generation code, maximum physical range, PRF/aperture definition, or independent imaging-time mask was found. The checked MATLAB toolbox is only a similar-imaging reference and is not the OTY2 pipeline.

The historical `0.03 m/pixel` value is therefore classified as a project/local evaluation radial grid-spacing claim. It is not independently traceable to the current imaging pipeline and must not be described as:

- uniform Cartesian scale over the full image;
- range resolution;
- azimuth resolution;
- PSF/main-lobe width;
- actual vehicle-structure resolving power.

Metric `x/y`, metric GT width/height, and metric mapping error are intentionally blank in S0 manifests.

## Raster operations

No S0 evidence proves the upstream crop/flip/rotation/resampling chain. The current display formula itself is reproducible and uses no additional flip or rotation after loading the PNG. Pseudocolor and gray use the same `2308×1334` display grid.

## Mask separation

- `imaging_valid_mask`: not located; physical semantics blocked.
- `fan_geometry_mask`: reconstructed display fan, `r<=1332.7` and `-90<=theta<=90`.
- `display_nonzero_mask`: per-frame gray intensity `>0`.
- `fixed_black_region_mask`: zero in every gray frame, inside the reconstructed fan.
- `gt_box_region`: reviewed rotated GT region, not scattering truth.
- `gt_valid_intersection_mask`: blocked because `imaging_valid_mask` is missing.
- `vehicle_response_mask`, `registration_valid_mask`, and `occlusion_or_boundary_missing_mask`: semantic contracts only in S0.

| scene | fan pixels | fixed black inside fan | fixed-black/fan | per-frame nonzero pixels |
| --- | ---: | ---: | ---: | ---: |
| GM_RM011 | 2628412 | 749541 | 0.285169 | 1865902..1873468 |
| GM_RM017 | 2628412 | 749427 | 0.285125 | 1866198..1871943 |
| GM_RM019 | 2628412 | 749903 | 0.285306 | 1866020..1873334 |

The empirical black region is a rendered-pixel fact. It does not distinguish physical non-imaging, invalid samples, clipping, display masking, or true zero return.

## Permitted use

The display `(x,y)`, `r_px`, `theta_deg`, fan geometry, and display-only masks may be used for S0 research indexing and display-angle mapping audit. They may not be promoted to a solved physical calibration. S1 remains blocked until the authoritative metric imaging grid and physical valid-mask semantics are supplied or independently reconstructed from the true imager.
