# OTY2 GM_RM017 Body-Canonical Response E0-R3 Protocol

Updated: 2026-07-13

This protocol defines `WGV3.6B-E0-R3 GM_RM017 Body-Canonical Response Transport and Aspect-Driven Scattering Migration`.
It is a first controlled audit loop, not a detector, selector, ranker, classifier, final-box generator, GT edit, training
signal, or cross-scene validation package.

## Research Question

The E0-R3 research unit is the same physical vehicle observed through a body-canonical SAR response field:

```text
A_t(u,v)
```

where `u` is the normalized vehicle long-axis coordinate and `v` is the normalized vehicle short-axis coordinate. The
field is generated from frozen GT centers, frozen same-vehicle thread membership, frozen image-grid support, and a frozen
body-axis proxy. The audit studies the response field as a spatial structure, not as a vector of per-frame summary
statistics.

The core question is whether high-energy SAR responses in GM_RM017 are mainly located on radar-near body structures and
whether the same-vehicle structure shows visually reviewable migration, switching, splitting, merging, birth, or
disappearance beyond distance, time, registration error, mask/boundary effects, and background counterfactuals.

## Three Separated Propositions

E0-R3 keeps these propositions separate:

| proposition | question | allowed conclusion |
| --- | --- | --- |
| A: near-side localization | Is high-energy response mainly on the radar-near side of the body-canonical vehicle support? | May be evaluated descriptively even if aspect causality is not identifiable. |
| B: same-vehicle structural dynamics | Does the same vehicle show stable, sliding, switching, splitting, merging, birth, or disappearance events in `A_t(u,v)`? | May be evaluated as descriptive structure dynamics. |
| C: aspect causality | Are structural events primarily explained by relative aspect beyond range, time, body-axis variation, GT jitter, mask changes, interpolation, registration error, and background controls? | Requires independent controls; cannot be inferred from visible structure alone. |

No report may collapse A, B, and C into one statement. Visible structure is not automatically aspect-driven structure.

## Frozen Inputs

E0-R3 reads, but does not overwrite, these frozen sources:

- E0-R2 protocol and report.
- E0-R2 generate/evaluate scripts.
- E0-R2 relative-aspect, heading-observability, response-descriptor, range-confounding, repeatability, shuffle,
  GT-attached-corridor, persistent-strong, fixed-background, Gate, failure-ledger, replay, and manifest CSVs.
- E0-R1-R1 unique GT-center sequence, axial body heading, subject manifest, subject temporal features, symmetric Gate
  matrix, hard-negative confusion report, and frozen manifest.
- `configs/scene_config.yaml` for SAR canvas, fan center, and GM_RM017 SAR image paths.

The expected frozen geometry is:

| field | source | value |
| --- | --- | --- |
| SAR canvas | `configs/scene_config.yaml` | `2308 x 1334` |
| fan center | `configs/scene_config.yaml` | `(1154.0, 1330.6)` |
| image-grid spacing | frozen P0/E0/E0-R1 convention | `0.03 m/px` |
| imaging-domain check | fan-center radial distance | `40 m` |
| body support | E0-R1-R1 subject manifest | `L ~= 4.764934 m`, `W ~= 2.077648 m` |

The `0.03 m/px` value is an inherited image-grid convention for this audit. It is not a PSF-corrected SAR resolution
claim.

## Legacy Conclusion Withdrawal And Downgrade

| legacy item | old status | E0-R3 status | reason |
| --- | --- | --- | --- |
| `multi_gate_physical_confusions=0` | E0-R1 zero-confusion claim | `WITHDRAWN` | Old G10 depended on `is_vehicle`, so non-vehicles could not pass by construction. |
| `RANGE_CONFOUNDER_REJECTED=SUPPORTED` | E0-R2 supported | `WITHDRAWN` | E0-R2 absolute range used distance from image origin rather than from SAR fan center. |
| `response_index` | E0-R2 summary descriptor | `EXPLORATORY_ONLY` | It is an equal-weight average of nine standardized descriptors and is not primary physical evidence. |
| same-aspect repeatability | partial support in E0-R2 wording risk | `NOT_EVALUABLE_NO_DIFFERENT_ASPECT_MATCHED_PAIRS` | E0-R2 found `different_aspect_similar_range pairs = 0`. |
| local smoothness | E0-R2 smoothness candidate | `DOWNGRADED` | The old threshold used whole-sequence information and the monotone smoothness premise is not a general SAR law. |
| GT-attached corridor rejection | E0-R2 overall rejection | `DOWNGRADED` | Axis family, sign, offset distance, and GT-overlap risk must remain separated. |
| motion tangent yaw | body-axis proxy | `AXIAL_PROXY_ONLY` | The tangent is unsigned body-axis support for registration, not true yaw or front/rear pose. |

`response_index` must not be used for primary evidence, Gate decisions, counterfactual rejection, event definition,
transport parameter choice, or aspect-mechanism conclusion.

## Distance-Origin Correction Gate

E0-R3 recomputes range from the SAR fan center:

```python
range_m = hypot(cx - fan_center_x, cy - fan_center_y) * 0.03
```

The audit output records at least:

```text
sar_frame,cx,cy,fan_center_x,fan_center_y,range_px_corrected,range_m_corrected,within_40m_domain,failure_reason
```

The legacy E0-R2 range field is retained only for comparison. Old E0-R2 CSVs are not modified. A frame outside the
corrected 40 m domain enters the E0-R3 failure ledger.

## Aspect/Range/Time Identifiability Gate

E0-R3 must audit actual usable controls, not just correlations. It reports:

- similar corrected range with different aspect;
- similar aspect with different corrected range;
- non-adjacent similar aspect;
- different aspect with similar corrected range;
- aspect-time monotonicity risk;
- aspect-corrected-range collinearity risk;
- whether paired frames also have reliable body-axis and registration states.

The audit must not relax thresholds until pairs appear. If independent controls are missing:

```text
ASPECT_CAUSAL_IDENTIFIABILITY=NOT_READY
```

Near-side localization and descriptive structural dynamics may still be reviewed under that status.

## Body-Canonical Coordinate Definition

The body-canonical field maps each selected SAR frame into a normalized canvas:

| item | definition |
| --- | --- |
| grid | `128 x 64` for the core body support |
| horizontal axis | body long axis `u` |
| vertical axis | body short axis `v` |
| support | current dataset image-grid support, not true vehicle dimensions |
| intensity field | raw grayscale intensity resampled from SAR image |
| normalized field | per-frame local-background normalization only |
| mask | valid pixels after inverse mapping into the SAR image |
| interpolation | bilinear for intensity; nearest/boolean for masks |

The transform and inverse transform must be recorded. Border padding, valid-mask area, boundary proximity, and obvious
interpolation artifacts are audit fields, not hidden implementation details.

## 180-Degree Axis-Continuity Rule

The frozen body axis is axial:

```text
theta == theta + 180 deg
```

E0-R3 chooses a directed registration representation only to prevent canonical-map flips:

```text
For theta and theta+180 deg, choose the representation with the smallest directed-axis difference from the previous
reliable frame.
```

The output records:

```text
axis_unsigned_deg
axis_signed_for_registration_deg
axis_sign_flip_applied
axis_continuity_residual_deg
```

This directed representation does not identify vehicle front or rear. Reports use only `body_long_positive` and
`body_long_negative`.

## Radar Direction And Near/Far Structure

Radar-near side is not a fixed top or bottom half of the canonical image. For each frame:

1. Compute the image vector from vehicle center to SAR fan center.
2. Rotate that vector into body-canonical coordinates using the signed registration axis.
3. Define near half, far half, near boundary band, far boundary band, body-long end regions, and middle region from that
   transformed vector.

The near-side boundary uses an arc-length coordinate:

```text
s in [0,1]
```

The origin and direction of `s` are frozen by the body-axis sign-continuity rule. E0-R3 may extract
`E_t(s)`, `s_peak_t`, `secondary_peak`, `peak_count`, `peak_width`, `peak_prominence`,
`near_side_boundary_energy_fraction`, `far_side_boundary_energy_fraction`, and `peak_inside_valid_mask`, but these are
indices for review, not a weighted score.

## Minimal Visual Casebook

Before generating visuals, E0-R3 freezes a small representative-frame manifest. It should cover:

- one locally stable window;
- one possible near-side sliding window;
- one possible primary-response switching window;
- one possible splitting or merging window;
- one GT/mask/boundary difficult window;
- one difficult background counterfactual window.

The manifest records:

```text
sar_frame,window_id,selection_reason,same_vehicle_thread,axis_reliability,registration_reliability,
relative_aspect_angle_deg,range_m_corrected,expected_review_role
```

The selection rule is part of the audit and cannot be revised after seeing the most attractive rendered frames.

## Visual Outputs To Review

E0-R3 generates ignored PNGs under `outputs/` and tracks only their relative paths in committed CSV/Markdown files:

- canonical raw response maps sorted by time;
- local-normalized maps sorted by time;
- canonical maps sorted by aspect;
- overlays with radar direction, near-side boundary, far-side boundary, body-long positive/negative ends, and valid mask;
- `E_t(s)` heatmap;
- `s_peak_t` versus time;
- `s_peak_t` versus aspect;
- original SAR, GT center, body axis, and canonical map four-panel views;
- mask/boundary anomaly views;
- vehicle versus difficult counterfactual views.

Visual review must give frame-specific Chinese judgments. A PNG existing on disk is not evidence by itself.

## Minimal Frame-Difference Audit

For selected neighboring frame pairs only:

```python
delta_A = A_next - A_current
gain = maximum(delta_A, 0)
loss = maximum(-delta_A, 0)
```

The audit records whether gain/loss is spatially adjacent, whether it lies on the radar-near structure, and whether it
could be explained by GT-center jitter, body-axis variation, mask change, boundary effects, or interpolation.

E0-R3 may define a future response-transport interface, but it does not batch implement or tune a complete transport
solver.

## Registration Perturbation Audit

Representative frames are perturbed with small GT-center translations, small body-axis rotations, and small L/W scale
changes. The purpose is sensitivity analysis, not optimization. If a visually important event can be reproduced by a
reasonable perturbation, that case is marked:

```text
REGISTRATION_SUSPECTED
```

Such cases cannot support a physical-mechanism claim.

## Counterfactual Requirements

At minimum, E0-R3 runs the same canonical flow for:

- one GT-attached corridor with low or no GT-overlap risk where available;
- N005 or an existing difficult non-vehicle subject;
- one fixed strong-scatterer or persistent strong-scatterer subject.

GT-attached corridors keep:

```text
axis_family,direction_sign,offset_distance,gt_overlap_risk
```

Corridors with GT-overlap risk are marked `COUNTERFACTUAL_CONTAMINATED_BY_GT` and cannot reject background explanations.

## Gate Status Semantics

Allowed states are:

```text
PASS,SUPPORTED,PARTIAL,NOT_READY,NOT_EVALUABLE,FAIL
```

E0-R3 reports at least:

```text
REPOSITORY_LINEAGE_VERIFIED
REQUIRED_FROZEN_ARTIFACTS_READ
LEGACY_CONCLUSIONS_WITHDRAWN
METRIC_RANGE_ORIGIN_CORRECTED
CORRECTED_RANGE_WITHIN_IMAGING_DOMAIN
ASPECT_RANGE_TIME_IDENTIFIABILITY_AUDITED
ASPECT_CAUSAL_IDENTIFIABILITY
BODY_AXIS_SIGN_CONTINUITY_VALID
BODY_CANONICAL_INPUTS_SUFFICIENT
BODY_CANONICAL_FIELD_VALID
NEAR_SIDE_RESPONSE_LOCALIZATION_VISUALLY_AUDITED
MINIMAL_STRUCTURAL_TIMELINE_VISUALLY_AUDITED
REGISTRATION_FAILURE_MODES_AUDITED
MINIMAL_COUNTERFACTUAL_STRUCTURAL_AUDIT_COMPLETED
```

Script execution, CSV existence, PNG existence, contact-sheet generation, and replay success are not Gate PASS by
themselves.

These extended mechanism Gates default to `NOT_READY` or at most `PARTIAL` unless unusually strong evidence is produced:

```text
NEAR_SIDE_RESPONSE_MIGRATION_SUPPORTED
RESPONSE_TRANSPORT_BEYOND_REGISTRATION_SUPPORTED
ASPECT_EFFECT_BEYOND_RANGE_AND_TIME_SUPPORTED
GT_ATTACHED_CORRIDOR_STRUCTURAL_COUNTERFACTUAL_REJECTED
PERSISTENT_STRONG_STRUCTURAL_COUNTERFACTUAL_REJECTED
VEHICLE_BODY_STRUCTURAL_DYNAMICS_SUPPORTED
E0_R3_PHYSICAL_MECHANISM_SUPPORTED
```

## Stop Conditions

E0-R3 stops expansion if any of these occur:

- fan center cannot be reliably read from frozen config;
- GT and SAR image coordinates cannot be mapped consistently;
- corrected range still has many frames outside 40 m;
- same-vehicle thread cannot be confirmed;
- key-window body axis is unstable;
- 180-degree flips cannot be removed reliably;
- canonical field is dominated by boundary or interpolation artifacts;
- aspect/range/time lacks independent usable controls;
- suspected sliding is reproduced by GT-center or axis perturbation;
- background counterfactuals show the same near-side migration;
- only a weighted composite can separate cases;
- visual review cannot form concrete frame-by-frame structural judgments.

If stopped, the report states the root cause and asks for constrained new data such as bidirectional passes, turning
trajectories, same-vehicle repeat passes, similar-range different-pose examples, rotated boxes, reliable yaw, or
camera-radar ground mapping.

## This Round Does Not Do

E0-R3 does not implement a full large-scale response-transport system, does not tune statistical Gates, does not train a
classifier, does not build a selector or ranking score, does not use `response_index` as evidence, does not edit GT, and
does not revise frozen P0/D1/D1-R1/E0/E0-R1/E0-R1-R1/E0-R2 artifacts.
