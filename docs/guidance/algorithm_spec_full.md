# Algorithm Spec Full

This is the inherited algorithm mechanism summary for V0 diagnosis. It is not a production formula spec and not a selector spec.

## Fan-Polar To Display-XY

Known formula:

```text
x = Cx + r * sin(az) + cross * cos(az)
y = Cy - r * cos(az) + cross * sin(az)
```

Angles are in degrees in the legacy tables and converted to radians inside code. Current shared baseline values are `Cx=1154.0`, `Cy=1330.6`, `radius_px_max=1332.7`, `azimuth_k=0.0875154`, `azimuth_b=-40.413555`, and `theta_offset_deg=0.0`.

## Azimuth Mapping

Known inherited mapping constants:

```text
azimuth_k = 0.0875154
azimuth_b = -40.413555
theta_offset_deg = 0.0
theta_sign = 1.0
```

The exact optical-to-azimuth derivation should be treated as legacy calibrated mapping, not a newly validated physical model. Current V0 code consumes configured values; it does not hard-code production mapping logic.

## Heading / Storage-Axis Convention

`heading`, `final_heading`, `w`, and `h` are storage-axis or display-XY box conventions. They must not be automatically interpreted as literal vehicle heading, width, or length.

## Candidate AABB / Rotated Box

- AABB is an axis-aligned proxy for display review or posthoc accounting.
- Rotated boxes carry storage-axis orientation and may be useful for overlays.
- AABB IoU is not rotated IoU and cannot justify heading conclusions.
- Posthoc AABB IoU can explain failures but cannot tune runtime generation or ranking.

## Candidate Delta

Known formula:

```text
delta_r = r - pred_r
delta_cross = cross - pred_cross
delta_az = wrapped_angular_delta(az, pred_az)
```

Recommended angular wrap:

```text
wrapped_angular_delta(a, b) = ((a - b + 180) mod 360) - 180
```

Delta fields are diagnostic features. They are not thresholds.

## Visible Risk

Approximate / legacy audit formula: visible risk combines partial visibility, edge proximity, leakage risk, support compactness, and local SAR background concerns when those fields exist. If the field is absent, V0 must show `missing`.

Visible risk can explain why a range window may need audit expansion, but it is not a selector rule.

## Runtime Prior Sources

Inherited runtime prior candidate sources:

- `base_candidate`
- `factor_inference_candidate`
- `factor_topk_candidate`
- `visible_support_candidate`

These are candidate construction inputs. They are not reliability labels.

## Wedge Mode

Approximate / legacy audit formula:

1. Start from `pred_r`, `pred_az`, `pred_cross`, and `range_prior_sigma`.
2. Define a local fan-polar wedge around the predicted azimuth.
3. Expand range window under visible-risk or partial-visibility review conditions.
4. Sample SAR gray profile inside the wedge.
5. Identify local peaks.
6. Compute audit features such as compactness, prominence, posterior/support score, and range offset.

All `posterior_score`, support, compactness, and prominence fields are audit features at the current stage. They are not selector scores.

## Ray Mode

Approximate / legacy audit formula:

1. Sample a range profile along `pred_az`.
2. Compare `r_opt`, `r_pred`, `r_track`, and SAR peak locations.
3. Compute audit features such as `opt_score`, `pred_score`, `track_score`, `sar_peak_score`, and `posterior_score`.
4. Mark extreme range shifts where the selected SAR peak is far from the predicted or track-supported range.

Extreme range shift can indicate optical prior failure, SAR clutter, or identity confusion. It is not a hard rejection rule.

## Signed Mode

Approximate / legacy audit formula:

1. Inspect neighboring-frame wedge/ray `delta_r`.
2. Vote each neighbor as `pos`, `neg`, `near`, or `artifact`.
3. Derive a weak signed `escape_direction` when neighboring evidence is consistent.
4. Keep artifact votes separate from positive temporal evidence.

C1.3/C1.4 did not reach identity-supported full temporal parity for GM_RM019. Signed evidence remains weak audit evidence.

## Structural Candidates

Structural candidates convert mode rows into boxes:

- `wedge_joint_candidate`: generated from wedge peak/range and local structure support.
- `multi_peak_ray_candidate`: generated from multiple ray-profile peaks.
- `track_signed_escape_candidate`: generated from weak temporal signed range-release evidence.
- `bidirectional_escape_candidate`: review-only or weak case where both directions remain plausible.

Common conversion:

```text
(r, az, cross) or peak-derived fan-polar coordinate
-> fan-polar to display-XY
-> inherit/estimate w, h, heading storage-axis fields
-> write candidate_source, candidate_source_family, candidate_detail
```

## Dedup Policy

Approximate / legacy audit policy: near-duplicate candidates are identified by source-family and geometric proximity. C1.4 suppressed duplicate `factor_topk_candidate` rows for deterministic input ordering. Dedup is a stable input policy, not a calibrated reliability model.

## Frozen Rank

C1.4 rank groups:

1. `prior_core`
2. `factor_retrieval`
3. `structural_local`
4. `structural_range`
5. `structural_temporal`
6. `review_only_tail`

Frozen rank is deterministic input rank. It is not a calibrated selector and does not prove reliability.

## Posthoc Accounting

Posthoc accounting includes AABB IoU, final/oracle/GT comparison, and coverage/top-k review. These fields can explain what failed after the fact. They cannot enter runtime generation, ranking, thresholds, or selector rules.
