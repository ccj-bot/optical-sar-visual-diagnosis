# OTY2 GM_RM019 Static Axis And Rotation Semantic Integrity S1-R1 Protocol

Date: `20260712`

This protocol repairs the S1 static SAR observation-field semantics for GM_RM019. OTY2 (Optical Timeline Y2, optical timeline assisted phase two), SAR (Synthetic Aperture Radar), and GT (Ground Truth) remain separated: this round is still pre-GT S1-R1, not S2 GT-region counterfactual evaluation.

## Boundary

- Status space: `S1_R1_SEMANTIC_INTEGRITY_READY`, `S1_R1_PARTIAL`, `S1_R1_BLOCKED`.
- S2 is not executed here.
- Generation may read only SAR gray frames, frozen local response units, frozen S1 rows, boundary variant families, this protocol, and project-confirmed calibration constants.
- Generation must not read paired annotations, response-unit GT instance matrices, mask-observation audit tables, GT correction fields, selector/ranking outputs, final boxes, or runtime prediction artifacts.
- `calibration_status = PROJECT_CONFIRMED`.
- `max_range_m = 40.0`.
- `radial_grid_spacing_m_per_px = 0.03`.
- `sar_fan_center = (1154.0, 1330.6)`.

## Existing Box-Axis Semantics

The inherited repo rule is that `heading`, `final_heading`, `w`, and `h` are storage-axis or display-XY box conventions. They are not literal vehicle heading, width, or length. `final_heading_deg` is therefore the direction of the stored `final_w` axis in SAR display coordinates. It is not automatically the vehicle long axis, vehicle nose direction, directed yaw, or SAR gray response principal axis.

If S2 later opens GT, the GT visual long-axis proxy must be defined as:

```text
theta_gt_long = theta_w                  if final_w >= final_h
theta_gt_long = theta_w + 90 degrees     if final_h > final_w
theta_gt_long mod 180 degrees
```

This S1-R1 generation does not open GT and does not compute `theta_gt_long`.

## Unified Static Axis Fields

`response_axis_image_deg` is the background-subtracted SAR gray response covariance major eigenvector represented as an undirected image axis in `[0, 180)`. Image coordinates are x right, y down. The implementation stores the raw major eigenvector first and only canonicalizes the line direction after eigenvector extraction.

`response_axis_to_range_signed_deg` is the signed undirected-axis angle from the local radar range unit vector to the response axis:

```text
beta = atan2(e_r_x * v_y - e_r_y * v_x, e_r_x * v_x + e_r_y * v_y)
beta_signed in [-90, 90)
```

The sign is preserved, so image axes near 45 degrees and 135 degrees are not collapsed into one value. The equivalent vector `-v` maps to the same undirected axis.

`response_axis_to_range_acute_deg = abs(response_axis_to_range_signed_deg)` and lies in `[0, 90]`.

`response_axis_to_azimuth_acute_deg` is the acute undirected angle to the local azimuth unit vector. The integrity gate checks that the range and azimuth acute angles sum to approximately 90 degrees.

`axis_orientation_status` may be:

```text
AXIS_ORIENTATION_RESOLVED
AXIS_NEAR_ISOTROPIC
AXIS_MULTI_COMPONENT_AMBIGUOUS
AXIS_THRESHOLD_UNSTABLE
AXIS_ENERGY_INVALID
```

Only resolved and threshold-stable axes may be interpreted as meaningful static response axes. None of these fields is vehicle yaw.

## Aspect Angle, Not Vehicle Yaw

True vehicle yaw is a directed nose orientation and distinguishes 0 degrees from 180 degrees. A single static SAR response normally provides only an undirected axis and must not output `vehicle_yaw_deg`, `true_yaw_deg`, or `confirmed_heading_deg`.

The former static `yaw` proxy is replaced by `aspect_angle_candidate_deg`, where the aspect angle is the undirected candidate angle between a hypothetical vehicle rectangle long axis and the local radar range axis. It is scanned only over `[0, 90]`.

The projection envelope uses:

```text
W_r = |L cos psi| + |W sin psi|
W_a = |L sin psi| + |W cos psi|
L in [3.0, 6.5] meters
W in [1.4, 2.6] meters
psi in [0, 90] degrees
```

This is a soft projection envelope. It is not a selector, not a vehicle classifier, and not a true yaw estimator.

## Missing Support Versus Extra Spread

Local SAR response support can be smaller than a full vehicle projection. S1-R1 separates:

- `required_missing_support_range_m`
- `required_missing_support_azimuth_m`
- `required_extra_spread_range_m`
- `required_extra_spread_azimuth_m`

Envelope status may be:

```text
WITHIN_VEHICLE_PROJECTION_ENVELOPE
PARTIAL_SUPPORT_BELOW_ENVELOPE
EXCEEDS_VEHICLE_PROJECTION_ENVELOPE
AMBIGUOUS_ENVELOPE_COMPATIBILITY
```

Below-envelope support is not negative vehicle evidence; it can be a hotspot, local part, one-side shell, mask-visible fragment, or split local response.

## Threshold Component Identity

Threshold stability is no longer defined by mere existence of a large connected component. S1-R1 tracks the largest component under:

```text
positive_weight_q50
positive_weight_q70
positive_weight_q85
```

For adjacent thresholds, S1-R1 records overlap IoU, high-threshold containment in the lower-threshold component, centroid shift, area retention ratio, and axis change. The identity status may be:

```text
SAME_COMPONENT_PERSISTENT
COMPONENT_SPLIT_OR_MERGE
COMPONENT_IDENTITY_SWITCH
COMPONENT_TOO_SMALL
NO_STABLE_COMPONENT
```

Only `SAME_COMPONENT_PERSISTENT` supports a statement that the same core structure persists across thresholds.

## Real SAR Counterfactual Remeasurement

S1-R1 keeps the S1 perturbation families and adds `local_region_rotation`. Every perturbed region is remeasured from the SAR gray image. Proxy deltas such as fixed energy decay, area-times-density growth, preset axis change, or fixed component-count deltas are forbidden as result fields.

Families:

- `center_shift`: range and azimuth shifts by `±0.15`, `±0.30`, `±0.45` meters.
- `single_boundary_shift`: `range_min`, `range_max`, `azimuth_min`, `azimuth_max` by `±0.15`, `±0.30` meters.
- `scale_resize`: range and azimuth by `±0.15`, `±0.30` meters.
- `local_region_rotation`: `±5`, `±10`, `±15`, `±30`, and `90` degrees.

The frozen background mode is `BASE_REGION_FROZEN_BACKGROUND`. The sensitivity background mode is `PERTURBED_LOCAL_RING`.

## Independent Geometry

The response-unit table remains 250 rows for provenance, but independent statistics use stable `independent_geometry_id` values based on the frozen S1 conservative response geometry (`conservative_bbox`). This matches the inherited 215 independent conservative geometries. Member SAR frames and response units remain provenance fields. Identical conservative response geometries are measured once, then mapped back to all member response units. The expected independent geometry count is 215.

## S2 Readiness

`S2_READINESS=READY` is allowed only if raw eigenvectors are used, 45/135 degree axes are not collapsed, signed/acute angle ranges pass, near-isotropic axes are not overinterpreted, yaw terms are removed from static outputs, vehicle scale is envelope-only, missing support and extra spread are separated, threshold component identity is tracked, all counterfactuals are real SAR gray remeasurements, independent geometry deduplication is valid, replay is identical, visual review passes, and GT has not been opened for S2.
