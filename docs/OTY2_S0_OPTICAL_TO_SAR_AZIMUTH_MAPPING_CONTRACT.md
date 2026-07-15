# OTY2 S0-M Optical-to-SAR Azimuth Mapping Contract

Date: `2026-07-15`
Status: `MAPPING_BLOCKED`

## 1. Mapping target and eligibility order

The target remains SAR display-fan azimuth:

```text
x_optical_reference_center_px -> theta_SAR_display_deg
```

Anchor eligibility is fixed before any mapping residual is evaluated. The allowed values are exactly:

`calibration_gold`, `calibration_usable`, `heldout_gold`, `heldout_usable`, `mask_clipped_diagnostic`, `pose_or_geometry_diagnostic`, `identity_conflict`, and `exclude`.

Formal fitting/evaluation anchors require a canonical identity, a complete optical vehicle, no optical boundary truncation, a GT fully inside and not touching `imaging_valid_mask`, gold or visually reviewed usable GT geometry, no direct neighboring-GT overlap above `0.05`, and no independent geometry/identity conflict. Coarse same-frame multi-vehicle presence remains recorded separately from direct GT-region competition.

## 2. Anchor accounting after S0-M filtering

- historical anchors: `70` from `5` vehicles across `3` scenes;
- mask-clipped historical anchors: `0`;
- retained complete anchors: `65` from `3` vehicles, all in `GM_RM017`;
- development complete anchors: `20`, all from `GM_RM017:PV002`;
- heldout complete anchors: `45`, from `GM_RM017:PV003` and `GM_RM017:PV004`;
- development vehicle leave-one-out: not estimable because only one development complete vehicle remains.

The remaining complete anchors contain only `left_side_dominant` optical pose. No front, rear, right-side, oblique, or stable alternative pose group is represented.

## 3. Re-audit of the 39.440-degree case

Historical row:

- scene/vehicle: `GM_RM019 / GM_RM019:PV004`;
- optical/SAR frame: `168 / 350`;
- old prediction: `-32.597598 deg`;
- GT center azimuth: `6.842207 deg`;
- center residual: `-39.439805 deg`;
- full GT azimuth interval: `[-44.233547, 50.940869] deg`;
- distance from prediction to full GT interval: `0 deg`;
- GT valid-mask fraction: `1.0`.

The large center residual is not used as an exclusion reason. Direct optical review shows that the foreground gray vehicle is cut by the left, right, and bottom image edges, while the P1-E reference box is only a local fragment rather than the full vehicle extent. The row is therefore independently classified as `pose_or_geometry_diagnostic` and is ineligible for formal mapping evaluation.

The GM_RM011 `11.809661 deg` historical case is handled the same way: its vehicle extent is cut by the left/bottom optical boundaries and its reference box lies within the 8-pixel boundary margin. Its prediction is also inside the very wide full GT azimuth interval.

## 4. Center and interval evaluation

| subset/model | n | vehicles | center median | center P90 | center max | inside full GT interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| all historical / old linear | 70 | 5 | 1.0651 deg | 3.2045 deg | 39.4398 deg | 100% |
| filtered complete / old linear | 65 | 3 | 1.0295 deg | 3.0642 deg | 3.7409 deg | 100% |
| filtered complete / development refit linear | 65 | 3 | 0.6030 deg | 1.4145 deg | 1.9431 deg | 100% |
| filtered complete / centered linear | 65 | 3 | 0.6030 deg | 1.4145 deg | 1.9431 deg | 100% |
| filtered complete / effective pinhole LOS | 65 | 3 | 0.6488 deg | 1.5749 deg | 3.1098 deg | 100% |

The filtered median GT azimuth width is `25.4154 deg`; the old mapping's median center error/GT-width ratio is `0.0420`. All current GT boxes are inside the valid mask, so the full-GT and GT-intersection-mask interval metrics are identical.

The optical partial/boundary diagnostic subset contains `148` nearest-sync rows across `17` vehicles and three scenes. Its old-mapping center median/P90/max are `8.3630 / 18.6846 / 39.4398 deg`, while `99.32%` of predictions still fall inside the full GT interval. This separates proxy-center failure from interval coverage.

## 5. Model comparison

Historical fixed model:

```text
theta = 0.0875154 * x - 40.413555
```

Development-complete linear refit:

```text
theta = 0.091778579301 * x - 40.421051198963
```

The centered linear model is the same line reparameterized around `x0 = 400`; it does not add capacity. The effective pinhole LOS comparison uses fixed principal point `x0=400`, fitted effective focal length `485.111 px`, scale `46.704`, and offset `-3.735 deg`. These are diagnostic effective parameters, not physical camera intrinsics.

Heldout-complete results:

| model | n | vehicles | median | P90 | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| old linear | 45 | 2 | 0.9115 deg | 3.2147 deg | 3.7409 deg |
| development refit linear | 45 | 2 | 0.9069 deg | 1.4939 deg | 1.9431 deg |
| centered linear | 45 | 2 | 0.9069 deg | 1.4939 deg | 1.9431 deg |
| effective pinhole LOS | 45 | 2 | 0.9152 deg | 1.9940 deg | 3.1098 deg |

Only `GM_RM017` and only left-side-dominant pose remain in the complete set. The image-center subset has `46` rows and old-model median/P90/max `1.1837 / 3.1387 / 3.7409 deg`; the edge subset has `19` rows and `0.7337 / 2.2640 / 3.2380 deg`. No cross-scene or cross-pose freeze claim is permitted. A lower-order monotonic nonlinear model is not opened because the evidence does not satisfy the multi-vehicle/cross-scene justification threshold.

## 6. Pose-proxy audit

Pose is assigned from directly visible complete optical vehicles only; SAR GT never defines pose. All 65 eligible anchors are `left_side_dominant`. Therefore S0-M cannot decide whether the remaining residual is caused by pose, optical bbox-center bias, SAR GT-center/scattering bias, or a scene-specific projection offset. No pose-conditioned center correction is allowed. At most, pose remains a future uncertainty-corridor variable after cross-vehicle and heldout reproduction exists.

## 7. Azimuth corridor

For the old linear center and all 65 complete anchors:

| half-width | full GT-interval coverage | mean corridor width | mean expansion / GT width |
| ---: | ---: | ---: | ---: |
| 10 deg | 1.54% | 20 deg | 0.818 |
| 15 deg | 64.62% | 30 deg | 1.228 |
| 20 deg | 100% | 40 deg | 1.637 |

This table evaluates containment of the entire GT azimuth interval, not merely whether the prediction center falls inside it. The current data support a diagnostic `20 deg` half-width for complete-interval coverage, but this is not a frozen runtime corridor because the complete set lacks cross-scene and pose diversity.

## 8. Freeze decision

`MAPPING_BLOCKED`.

The development-complete refit improves same-scene heldout P90/max, but only one development vehicle remains, vehicle leave-one-out is impossible, and complete anchors do not cover another scene or pose group. No new center function is frozen. The historical line is retained only as a diagnostic prior until independent complete anchors provide cross-vehicle, cross-scene, and pose coverage.
