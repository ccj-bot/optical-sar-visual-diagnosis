# OTY2 GM_RM017 Temporal Multi-Aspect Response E0-R2 Protocol

Updated: 2026-07-12

This protocol defines `WGV3.6B-E0-R2 GM_RM017 Temporal Multi-Aspect Vehicle Response Audit`.
It continues from the frozen E0-R1-R1 correction. It is not a detector, selector, ranker, final-box
generator, GT update, training signal, fixed scatterer ID tracker, or cross-scene validation package.

## Frozen Boundary

- Worktree branch: `feature/oty2-gm017-physical-factor-discovery`
- Frozen start commit: `4ec662b36d0dc203dde5e165b94c786798ee0bde`
- Calibration: SAR `<=360`
- Guard: SAR `361-370`
- Same-scene posthoc diagnosis: SAR `371-394`

All aspect-observability rules, aspect-bin definitions, response-descriptor choices, range/time
counterfactual rules, and Gate thresholds are frozen from calibration only. Guard is not used for
fitting. Diagnosis is not used to retune. SAR `371-394` remains same-scene GT-conditioned posthoc
diagnosis, not a fresh holdout.

E0-R1-R1 remains the frozen input for metric scale, symmetric hard-negative Gate repair, GT-center
identity audit, and 180-degree axial body-axis semantics. E0-R2 does not overwrite any E0-R1-R1 CSV
or report.

## Inherited E0-R1-R1 Facts

E0-R2 explicitly inherits these E0-R1-R1 findings:

- The E0-R1 zero-confusion result was withdrawn because the old G10 was label-dependent and impossible
  for non-vehicle subjects to pass.
- E0-R1-R1 repaired G7/G9/G10 with subject-specific symmetric definitions and did not count
  `NOT_EVALUABLE` as `PASS` or `FAIL`.
- SAR336 was audited as `WEAK_CORRESPONDENCE_EXCLUDED`; the selected physical thread is
  `WGV35A_PAIR_0033`.
- Metric scale and centered spatial concentration were supported in the same-scene image-grid audit.
- Directional structure and complete physical separability remained `NOT_READY`.
- `matched_strong_scatterer_background` was the hardest single-frame negative, but it had no persistent
  subject track and therefore could not be forced through G9/G10.

## Core Question

E0-R2 answers only this question:

> During the GM_RM017 vehicle sequence, does the whole vehicle SAR response evolve with relative radar
> aspect angle in a bounded, repeatable way that is not explained by absolute range, time order,
> GT-attached background corridors, persistent strong scatterer counterfactuals, or fixed background
> controls?

The research unit is the whole vehicle response field. E0-R2 does not attempt to identify individual
stable scattering points.

## Heading Observability

E0-R2 does not simply loosen the E0-R1-R1 `HIGH` confidence rule. It separates:

- local trajectory not being globally straight;
- local tangent being unobservable.

For each selected GT-center frame, it compares at least:

- `symmetric_local_line_tangent`
- `local_quadratic_tangent`
- `history_only_line_tangent`
- `robust_median_displacement_direction`

For each method it records:

- `along_track_residual_px`
- `cross_track_residual_px`
- `total_residual_px`
- `support_frame_count`
- `speed_px_per_sar_frame`

It also records leave-one-frame-out and deterministic GT-center perturbation uncertainty:

- `body_axis_proxy_deg`
- `body_axis_axial_ci_low_deg`
- `body_axis_axial_ci_high_deg`
- `body_axis_axial_ci_width_deg`
- `method_consensus_axial_mad_deg`
- `heading_observability_status`

Allowed observability states are:

- `OBSERVABLE_HIGH`
- `OBSERVABLE_MEDIUM`
- `UNRESOLVED`

Two-sided local windows are posthoc diagnostic tools only. They are not causal runtime state.

## Relative Aspect Angle

For each observable vehicle frame:

```text
relative_aspect_angle_deg = axial_diff(body_axis_proxy_deg, local_range_axis_deg)
```

The result is in `[0, 90]`. It is a 2D same-scene image-plane relative-aspect proxy:

- near `0 deg`: radar line is roughly along the vehicle long axis;
- near `90 deg`: radar line is roughly side-looking.

It is not a full 3D pose angle.

E0-R2 records:

- `sar_frame`
- `body_axis_proxy_deg`
- `local_range_axis_deg`
- `relative_aspect_angle_deg`
- `aspect_angle_ci_width_deg`
- `absolute_range_m_grid`
- `aspect_observability_status`

## Aspect Span And Stop Conditions

E0-R2 first asks whether there is enough observable aspect variation to support a multi-aspect claim.
It records:

- `aspect_min_deg`
- `aspect_max_deg`
- `aspect_span_deg`
- `aspect_step_median_deg`
- `aspect_step_q90_deg`
- `observable_frame_count`
- `calibration_aspect_span`
- `guard_aspect_span`
- `diagnosis_aspect_span`

If the observable aspect span is too small, the diagnosis segment lacks observable frames, or diagnosis
falls outside the calibration aspect interval, the final multi-aspect mechanism remains `NOT_READY`.

## Response Descriptors

For each vehicle frame and counterfactual subject, E0-R2 records response descriptors in:

- local range / azimuth coordinates;
- body-long / body-short coordinates;
- original image-grid coordinates when needed.

Descriptors include:

- `total_energy`
- `mean_energy`
- `local_background_normalized_energy`
- `high_energy_pixel_fraction`
- `response_occupancy_ratio`
- `inside_vs_ring_contrast`
- `energy_entropy_proxy`
- `range_energy90_width_m`
- `azimuth_energy90_width_m`
- `body_long_energy90_width_m`
- `body_short_energy90_width_m`
- `range_second_moment_width_m`
- `azimuth_second_moment_width_m`
- `body_long_second_moment_width_m`
- `body_short_second_moment_width_m`
- `energy_centroid_range_offset_m`
- `energy_centroid_azimuth_offset_m`
- `energy_centroid_body_long_offset_m`
- `energy_centroid_body_short_offset_m`
- `response_principal_axis_deg`
- `principal_minus_body_axial_deg`
- `principal_minus_range_axial_deg`
- `response_compactness`
- `response_linearity`
- `response_fragment_count`
- `response_fragmentation_index`
- `radar_near_half_energy`
- `radar_far_half_energy`
- `near_far_energy_ratio`

Front/rear semantics are used only when reliable; otherwise the protocol keeps undirected body-axis
and near/far radar semantics.

## Counterfactuals

E0-R2 evaluates these controls without introducing training or selection:

- GT-attached background corridors from frozen E0-R1 translation/offset regions;
- persistent world-fixed strong scatterer from E0-R1-R1 subject definitions;
- world-fixed N005 and fixed linear/strong backgrounds;
- aspect-shuffle control that permutes aspect order while preserving response descriptors;
- range and time confounder tests.

`matched_strong_scatterer_background` remains a single-frame worst-case negative unless a persistent
subject is explicitly available. It cannot be used as a temporal counterfactual track.

## Multi-Aspect Gates

E0-R2 uses these Gates:

- `G1_ASPECT_PROXY_OBSERVABLE`
- `G2_ASPECT_SPAN_SUFFICIENT`
- `G3_METRIC_SUPPORT_STABLE`
- `G4_LOCAL_ASPECT_RESPONSE_SMOOTHNESS`
- `G5_SAME_ASPECT_REPEATABILITY`
- `G6_ASPECT_EFFECT_NOT_EXPLAINED_BY_RANGE_ONLY`
- `G7_ASPECT_EFFECT_NOT_EXPLAINED_BY_TIME_ONLY`
- `G8_GT_ATTACHED_BACKGROUND_REJECTED`
- `G9_PERSISTENT_STRONG_COUNTERFACTUAL_REJECTED`
- `G10_FIXED_BACKGROUND_ASPECT_COUPLING_REJECTED`

Gate states are limited to:

- `PASS`
- `FAIL`
- `PARTIAL`
- `NOT_EVALUABLE`
- `UNRESOLVED`
- `CENSORED`

Gates are diagnostic posthoc tests, not a classifier or weighted score. Each Gate records definition
version, threshold source, threshold value, input fields, evidence, and failure reason.

## Final Claim Rule

`VEHICLE_MULTI_ASPECT_RESPONSE_SUPPORTED=SUPPORTED` is allowed only if:

1. relative aspect is observable with bounded uncertainty;
2. the observable sequence spans enough aspect variation;
3. vehicle metric support stays stable;
4. response descriptors change locally smoothly with aspect;
5. same-aspect / similar-range frames are more similar than different-aspect / similar-range frames;
6. the effect is not explained by absolute range alone;
7. the effect is not explained by time order alone;
8. GT-attached background corridors cannot reproduce it;
9. fixed backgrounds cannot reproduce it;
10. persistent strong-scatterer counterfactuals cannot reproduce it.

If any required condition is not met or is not evaluable, E0-R2 reports `NOT_READY`. Even a supported
result would remain `GM_RM017 same-scene GT-conditioned posthoc temporal multi-aspect evidence`, not a
cross-scene or final-detection conclusion.
