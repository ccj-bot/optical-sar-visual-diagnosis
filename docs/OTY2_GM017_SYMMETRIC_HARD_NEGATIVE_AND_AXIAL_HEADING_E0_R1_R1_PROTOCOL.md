# OTY2 GM_RM017 Symmetric Hard-Negative And Axial Heading E0-R1-R1 Protocol

Updated: 2026-07-12

This protocol defines `WGV3.6B-E0-R1-R1 GM_RM017 Symmetric Hard-Negative Gates and Axial-Heading Audit`.
It is a local correction over E0-R1. It is not a new model, detector, selector, ranker, final-box generator,
GT update, or cross-scene validation package.

## Frozen Boundary

- Worktree branch: `feature/oty2-gm017-physical-factor-discovery`
- Frozen start commit: `76029c558a7706bd6c460b8eb31749cce75406af`
- Calibration: SAR `<=360`
- Guard: SAR `361-370`
- Same-scene posthoc diagnosis: SAR `371-394`

Gate thresholds, heading rules, trajectory cleaning rules, and subject definitions are frozen from calibration only.
Guard does not fit thresholds. Diagnosis does not retune thresholds. SAR `371-394` remains same-scene GT-conditioned
posthoc diagnosis, not a fresh holdout.

The E0-R1 0.03 m/px image-grid mapping and body-support results are reused as frozen inputs. They are not refit from
R1-R1 diagnosis outcomes and are not called SAR range or azimuth resolution.

## Explicit E0-R1 Correction

E0-R1 had two confirmed defects that R1-R1 must correct.

First, E0-R1 used label-dependent hard-negative Gate logic:

```text
if is_vehicle:
    evaluate near-GT translation
else:
    G7 = FAIL_NON_GT_REGION
```

and:

```text
static_rejected = is_vehicle and paired_higher_median >= 0.60
```

It then defined a true physical confusion as:

```text
not is_vehicle
and principal_pass_count >= threshold
and G10 == PASS
```

Because non-vehicle regions could not pass the prior `G10`, the reported
`multi_gate_physical_confusions=0` was a logical consequence, not a scientific result. R1-R1 explicitly withdraws that
old zero-confusion claim and recomputes G7, G9, and G10 symmetrically.

Second, E0-R1 used a motion-heading proxy with ordinary directed-angle differences. It did not sufficiently separate
directed motion from the undirected vehicle body axis. The body long axis is axial: `theta` and `theta + 180 deg` are
equivalent. R1-R1 therefore evaluates body-axis stability and body-axis differences with a 180-degree axial period and
keeps directed motion only for motion-trend diagnosis.

## GT Center Identity Audit

R1-R1 constructs a single physical target center sequence before heading analysis. For each SAR frame it records:

- `sar_frame`
- `gt_row_count`
- `candidate_pair_ids`
- `candidate_centers`
- `center_selection_status`
- `selected_center_x`
- `selected_center_y`
- `identity_consistency_status`

Allowed selection statuses are:

- `UNIQUE_GT_CENTER`
- `DUPLICATE_SAME_OBJECT_CONSISTENT`
- `MULTI_GT_IDENTITY_CONFLICT`
- `WEAK_CORRESPONDENCE_EXCLUDED`
- `UNRESOLVED`

SAR336 is audited explicitly. If a duplicate frame cannot be safely resolved by pair identity, existing physical thread,
time continuity, weak-correspondence marking, and visual review, it is marked `UNRESOLVED` and excluded from the main
heading analysis. Original GT is never modified.

Velocity and heading calculations record `delta_frame` and use:

```text
velocity_px_per_sar_frame = delta_position / delta_frame
```

Cross-frame gaps are not treated as adjacent one-frame motion.

## Directed Motion Versus Axial Body Proxy

R1-R1 outputs both:

```text
motion_heading_directed_deg
```

in directed `[-180, 180)` semantics, and:

```text
body_axis_proxy_deg
```

in undirected `[0, 180)` semantics.

All body-axis differences use:

```text
axial_angle_difference_deg in [0, 90]
```

implemented as the minimum difference between two undirected axes. Directed one-step curvature is retained as a
diagnostic field, but body-axis stability, principal-axis comparison, and direction Gates use the axial version.

Heading confidence is not based on one-step curvature alone. It combines:

- speed;
- fit residual;
- support frame count;
- axial curvature;
- raw-vs-smoothed axial difference;
- duplicate/conflict status;
- trajectory-gap size;
- local displacement sign stability.

The main diagnostic body-axis relation uses only `HIGH` confidence frames. A symmetric two-sided local smoother is
allowed only because this is posthoc mechanism diagnosis; it is not a causal runtime state. A history-only version is
kept as sensitivity control.

## Symmetric Subject Set

R1-R1 evaluates the same spatial and temporal Gate definitions for:

- `vehicle_body_axis_reference`
- `matched_ordinary_background`
- `matched_strong_scatterer_background`
- `matched_linear_structure_background`
- `fixed_known_non_vehicle_N005`
- `fixed_strong_scatterer`
- `fixed_linear_structure`

Matched controls are framewise matched controls, not persistent tracks. Their G9/G10 states may therefore be
`NOT_EVALUABLE` with reason `FRAMEWISE_MATCHED_CONTROL_NO_TRACK`; this is not counted as PASS or FAIL.

## Subject-Specific Translation Surfaces

For every subject-frame, R1-R1 generates the same frozen offset grid:

```text
-1.00 m, -0.75 m, -0.45 m, 0.00 m, +0.45 m, +0.75 m, +1.00 m
```

along these axes:

- `local_range`
- `local_azimuth`
- `subject_principal_axis`
- `subject_principal_axis_perpendicular`

Vehicle rows additionally retain body-long/body-short references, but the symmetric Gate uses the four axes above.

The corrected spatial Gate is:

```text
G7_LOCAL_CENTERED_RESPONSE_STRUCTURE
```

It records:

- `center_value`
- `best_value`
- `best_offset_m`
- `center_rank`
- `center_to_far_median_contrast`
- `peak_prominence`
- `surface_curvature`
- `plateau_width_m`
- `translation_decay_slope`
- `best_offset_cross_frame_consistency`

It distinguishes:

- `sharp_center_peak`
- `near_center_plateau`
- `flat_uninformative_surface`
- `off_center_peak`
- `irregular_surface`

A flat surface cannot pass solely because its center value is close to its best value.

## Symmetric Temporal And Background Gates

`G9_TEMPORAL_PATTERN_CONSISTENT` is computed per persistent subject, not from class-level averages. It uses:

- metric extent stability;
- occupancy stability;
- compactness stability;
- linearity stability;
- local-normalized-energy stability;
- centered-surface-status stability;
- principal-axis stability;
- centroid-offset stability.

`G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED` is also computed from subject motion and response persistence, not from
vehicle/non-vehicle truth. For a moving GT-attached subject it tests whether the response moves with the subject instead
of repeatedly sampling a fixed image-coordinate background. For a world-fixed subject it tests whether image-coordinate
fixedness is sufficient to explain the response. For a framewise matched control without a persistent subject, it is
`NOT_EVALUABLE`.

## Gate Matrix

R1-R1 retains:

- `G1_VALID_OBSERVATION`
- `G2_METRIC_SIZE_COMPATIBLE`
- `G3_NOT_POINTLIKE`
- `G4_NOT_LONG_LINEAR`
- `G5_COMPACT_EXTENDED_SUPPORT`
- `G6_HIGH_ENERGY_OCCUPANCY_COMPATIBLE`
- `G7_LOCAL_CENTERED_RESPONSE_STRUCTURE`
- `G8_AXIS_RELATION_STRUCTURE_COMPATIBLE`
- `G9_TEMPORAL_PATTERN_CONSISTENT`
- `G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED`

Gate states are limited to:

- `PASS`
- `FAIL`
- `NOT_EVALUABLE`
- `CENSORED`
- `UNRESOLVED`

Each Gate row records:

- `gate_definition_version`
- `threshold_source`
- `threshold_value`
- `input_fields`
- `failure_reason`

Gate state definitions must not read `is_vehicle`, family label, vehicle/non-vehicle truth, or GT identity. Labels are
used only after Gate evaluation to summarize vehicle versus hard-negative distributions.

## Confusion Definitions

R1-R1 reports:

- `single_feature_energy_confusion`
- `metric_shape_confusion`
- `observable_structure_confusion`
- `temporal_physical_confusion`
- `full_physical_confusion`

`observable_structure_confusion` uses the shared observable Gates G1-G8 when they are actually evaluable. `full_physical_confusion`
is limited to persistent subjects where G9 and G10 are actually evaluable. `NOT_EVALUABLE` is never counted as PASS or
FAIL and cannot be used to manufacture zero confusion.

The final negative-pressure conclusion is determined by the most difficult individual negative subject, not by a median
across control categories.

## Direction Gate

For high-confidence body-axis proxy frames, R1-R1 compares:

- SAR response principal axis;
- body-axis proxy;
- local range axis;
- directed motion direction.

All reported body/principal/range differences use `[0, 90]` axial differences. R1-R1 does not use the E0-R1-style
condition `body_delta <= 45 OR range_delta <= 45`. If the calibration vehicle directional relation is too broad to freeze
a defensible interval, then:

```text
VEHICLE_DIRECTIONAL_STRUCTURE_SUPPORTED=NOT_READY
```

and direction is not forced into a broad threshold.

## Final Claim Boundary

`VEHICLE_HARD_NEGATIVE_REJECTION_SUPPORTED=SUPPORTED` is allowed only if:

- all hard negatives use the same observable Gate definitions as vehicles;
- the hardest matched strong scatterer does not stably reproduce the main Gate combination;
- N005 and fixed strong/linear backgrounds have G9/G10 actually computed;
- no label-dependent or constant true/false Gate logic remains;
- `NOT_EVALUABLE` is not counted as FAIL;
- visual review agrees with automatic outputs.

`E0_R1_R1_PHYSICAL_SEPARABILITY_SUPPORTED=SUPPORTED_IMAGE_GRID_POSTHOC` is allowed only if metric scale, spatial
concentration, directional relation, subject-specific temporal consistency, and hard-negative rejection are all supported.
Even then, the claim is limited to GM_RM017 same-scene GT-conditioned posthoc physical separability and does not imply
final automatic detection.
