# OTY2 S0 Optical-to-SAR Azimuth Mapping Contract

Date: `2026-07-15`
Status: `MAPPING_BLOCKED`

## Domain and anchors

The mapping target is SAR **display-fan azimuth**, not metric cross-range:

```text
x_optical_reference_center_px -> theta_SAR_display_deg
```

Anchors require a P1-E canonical link, `gold` or `usable` reviewed GT, full optical vehicle visibility, no explicit multi-vehicle competition, and high/moderate identity-link confidence. Development vehicles fit models. Development validation leaves one whole vehicle out. Heldout vehicles are evaluated once and never enter fitting.

- development anchors: `21` from `2` vehicles;
- heldout anchors: `49` from `3` vehicles.

## Models

Historical fallback:

```text
theta = 0.0875154 * x_optical + (-40.413555)
```

Current development-only linear refit:

```text
theta = 0.089687255891 * x_optical + (-39.136864479885)
```

The audited selection remains linear. A quadratic comparison is reported only to detect edge nonlinearity; it is not promoted from a small improvement without stable whole-vehicle validation.

## Absolute angular error

| evaluation | n | median deg | P90 deg | max deg |
| --- | ---: | ---: | ---: | ---: |
| old mapping / development | 21 | 2.105412 | 2.820879 | 11.809661 |
| old mapping / heldout | 49 | 1.029480 | 3.225934 | 39.439805 |
| refit linear / development in-sample | 21 | 0.831926 | 1.556775 | 9.894443 |
| refit linear / development vehicle LOO | 1 | 10.563780 | 10.563780 | 10.563780 |
| refit quadratic / development vehicle LOO | 1 | 10.401844 | 10.401844 | 10.401844 |
| refit linear / heldout | 49 | 1.348193 | 2.208394 | 37.969147 |

Scene residual check:

- GM_RM011: `-10.563780 deg` median residual
- GM_RM017: `1.321595 deg` median residual
- GM_RM019: `-37.969147 deg` median residual

Per-anchor tangential pixel error is approximated as `abs(error_rad) * r_px` and is also reported relative to the GT box's typical pixel width. Metric error is blank because the physical imaging grid is unresolved.

## Freeze decision

`MAPPING_BLOCKED`.

No mapping model is frozen. Development vehicle leave-one-out coverage is complete: `false`. Cross-scene extreme residual detected: `true`. The old and development-only refit remain diagnostic comparisons; they must not be retuned per frame, per GT, or from heldout vehicles. No GT-driven time offset or hard-sync modification was performed.
