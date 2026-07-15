# OTY2 S1-L Body Support Attribution and GT-Neighborhood Optimality Audit Protocol

Date: `2026-07-15`

Chinese name: `S1-L 车体支撑归属与 GT 邻域最优性审计`

Frozen start HEAD: `8519696ece0760e8af6d85a655773aaedae5a0c0`

Branch: `feature/oty2-sar-gt-structure-foundation`

## 1. Purpose and boundary

This is a bounded strengthening task after S1-L. It asks why one centre, scale, and unsigned-axis neighbourhood near the current GT explains a complete SAR time sequence better than nearby translations, rescalings, or rotations.

The task does not enter S1-D and does not produce automatic annotation, a final SAR box, a candidate bank, selector, ranking, oracle, weighted classifier, trained model, GT modification, or GT-IoU-driven decision.

The research object is a latent body-support hypothesis and its relation to the current visible 8-bit SAR grayscale response. A visible response may disappear, split, merge, or change dominance without implying that the physical vehicle disappears, splits, merges, or changes identity.

## 2. Accepted S1-L state

The starting state is `S1L_CONTINUOUS_STRUCTURE_PARTIALLY_READY`.

S1-L supports display-domain local morphology and conditional temporal persistence. It does not support vehicle ownership, stable vehicle parts, body-coordinate coherence, vehicle structural dynamics, cross-scene generalization, or automatic annotation. Background pseudo-threads reproduce part of the persistence, so unconditional morphology and persistence are not vehicle-specific.

## 3. Input roles

Core research units:

- `GM_RM017:PV002`: development/mechanism-discovery vehicle;
- `GM_RM017:PV003`: heldout vehicle;
- `GM_RM017:PV004`: heldout vehicle;
- `GM_RM011:PV001`: cross-scene diagnostic only.

Short diagnostic units:

- `GM_RM011:PV002`: 7-frame coordinate/format/local counterexample only;
- `GM_RM019:PV001`: 3-frame coordinate/format/local counterexample only.

The evidence unit is one physical vehicle over a continuous window or one independent background region. Observation, relation, event, and audit-row counts are not independent samples.

## 4. Two-layer vehicle state

### 4.1 Latent body-support state

For each frame, retain centre, unsigned long axis, short axis, length, width, relative observation-angle proxy, boundary missing support, visibility, and registration reliability. This state is expected to vary slowly over time and may include currently dark locations.

### 4.2 Visible response state

Retain current peaks, ridges, weak support, missing response, strengthening/weakening, apparent split/merge, and dominant-region change as display-domain observations. This state may change quickly and must not define the latent support by itself.

## 5. Coordinate contract

### 5.1 World coordinate

Retain global SAR display pixels and frozen fan-polar `r_px/theta_deg`. No uniform full-image Cartesian metre scale is asserted.

### 5.2 Crop coordinate

Retain existing Raw-GT and Smoothed-GT centre-anchored radial/tangential coordinates. These are crop/context coordinates, not vehicle coordinates. Raw and Smoothed versions remain simultaneous counterfactuals; Smoothed-GT is not treated as truth.

### 5.3 GT-derived body coordinate

For discovery only, derive the unsigned long axis from the rotated GT rectangle:

```text
long_axis_angle = bbox_angle                  when width >= height
long_axis_angle = bbox_angle + 90 degrees     when height > width
long_axis_angle = long_axis_angle mod 180
```

The frame-to-frame mathematical sign of the axis is chosen only for transform continuity. It must not be interpreted as front/rear or head/tail. The short axis is perpendicular to the long axis.

For each physical vehicle, define robust reference length and width from the continuous eligible thread. Because the metric grid is unresolved, canonical coordinates are dimensionless GT-relative coordinates while original pixel lengths remain stored.

Every frame must record:

- source gray SHA-256;
- global centre;
- Raw-GT and Smoothed-GT centre/size;
- unsigned body long-axis angle and unit vectors;
- axis-reliability state and reasons;
- thread reference length/width in display pixels;
- raw body-canonical intensity-field path;
- local-background-normalized body-canonical field path;
- registration-valid-mask path;
- radar direction in body coordinates;
- relative observation-angle proxy modulo 180 degrees;
- boundary-missing fraction;
- registration-reliability state and reasons;
- GT information-debt labels.

The canonical field is a processed display-domain registration product, not a recovered physical scattering field.

## 6. Axis and registration reliability

Axis reliability is not a weighted score. It is an explicit conjunction of auditable conditions:

1. rotated box aspect ratio is sufficiently anisotropic for an axis to be meaningful;
2. GT quality is gold or usable;
3. adjacent unsigned-axis changes are not abrupt after accounting for the true frame gap;
4. duplicate GT records do not show material axis/size disagreement;
5. the canonical sampling region retains adequate valid pixels;
6. Raw-GT and Smoothed-GT do not disagree catastrophically.

Each failed condition is stored separately. Frames that fail remain in the audit with `AXIS_UNRELIABLE` or `REGISTRATION_UNRELIABLE`; they are not silently removed.

## 7. Three-coordinate competition

The same frozen S1-L response observations and continuous grayscale fields are evaluated in world, crop, and body coordinates. Metrics remain separate and interpretable:

- position dispersion;
- orientation dispersion;
- relative-distance stability;
- relation-graph stability;
- adjacent-frame response transport cost;
- repeatability between non-adjacent similar-state frames;
- temporal support entropy;
- boundary-missing sensitivity.

No weighted total is formed. A coordinate attribution label may be assigned only after metric agreement and direct visual review:

- `BODY_COHERENT`
- `WORLD_COHERENT`
- `CROP_COHERENT`
- `MIXED`
- `UNRESOLVED`

If the coordinate systems do not separate, the result is `UNRESOLVED`; additional features must not be added merely to force a label.

## 8. Minimum casebook gate

Before GT-neighbourhood perturbation, generate and directly inspect a minimum casebook containing:

1. representative frames shown in world, Raw/Smoothed crop, and body coordinates;
2. temporal occupancy/support maps in all three coordinates;
3. vehicle versus nearby fixed-world-background stability comparison;
4. Raw/Smoothed disagreement cases, including the GM_RM017:PV002 start outlier;
5. one development vehicle, two heldout vehicles, and GM_RM011 diagnostic cases;
6. cases where body attribution appears positive, mixed, background-like, crop-like, or unresolved.

Each case receives a non-template Chinese review that states what is visible, which coordinate is more plausible, possible vehicle/background ownership, crop artifacts, whether the GT neighbourhood appears reasonable, and what remains unresolved.

Only if at least one structure family shows a reproducible and visually credible body-coordinate advantage may the task expand to GT-neighbourhood perturbation.

## 9. GT-neighbourhood perturbation gate

If the minimum casebook passes, use a small symmetric interpretable grid around GT for centre, scale, aspect ratio, and unsigned-axis rotation. Do not generate a random or massive candidate bank.

For every parameter setting, reconstruct the same body-canonical field and report separate constraints/metrics for:

- optical azimuth-corridor compatibility;
- temporal continuity;
- plausible vehicle-scale continuity;
- valid imaging Mask;
- body-coordinate coherence versus world/crop coherence;
- fixed-world-background inclusion;
- omission of previously body-coherent response;
- boundary missing support;
- response transport;
- relation-graph stability;
- latent-support continuity.

Do not use total energy, mean energy, maximum value, occupancy, component count, GT IoU, or a weighted sum to select an answer.

The permitted term is `relative best body-support parameters`, never a recovered unique true box.

## 10. Latent temporal support gate

Only after coordinate attribution and GT-neighbourhood structure are credible may the task reconstruct a temporal support map with separate classes:

- `stable_body_support_core`
- `intermittent_body_support`
- `world_fixed_background_support`
- `crop_artifact_support`
- `uncertain_support`
- `boundary_missing_support`

The reconstruction must distinguish co-moving, world-fixed, crop-fixed, single-frame, intermittent, and unresolved support. It is not an average grayscale image and is not described as recovery of raw scattering or raw echo.

## 11. Difficult counterfactuals

The full audit must eventually run the identical coordinate, structure, perturbation, support, and visualization path on:

1. the same crop trajectory on nearby empty background;
2. a fixed world region;
3. vehicle A trajectory applied to vehicle B time/background;
4. A/B trajectory exchange;
5. spatially shifted copies of the same crop path;
6. shuffled time order;
7. reversed time order as a direction-only counterfactual;
8. strong background matched in local energy and structural complexity.

Energy means and event counts alone cannot decide these counterfactuals.

## 12. Old-event downgrade and re-entry rule

All existing stable persistence, motion consistency, strength change, split/merge, birth/death, dominant switch, and unresolved correspondence rows begin as display-domain hypotheses.

An event can become a `vehicle candidate structure event` only when it is body-coherent, exceeds world/crop explanations, is stable under reasonable representations, is not explained by boundary/GT jitter/gain/threshold changes, has complete temporal context, and is not reproduced by difficult background counterfactuals.

The existing `major_event` field is not sufficient evidence.

## 13. Imaging-chain audit

The audit must retain the confirmed 8-bit display lineage and explicitly test or mark unresolved:

- per-frame auto-stretch;
- fixed versus varying grayscale mapping;
- saturation and quantization;
- local-normalization artifacts;
- interpolation/resampling ridge artifacts;
- framewise global-gain changes;
- gray-hash lineage;
- synchronization of split/merge with display processing.

Where the upstream chain is unresolved, use only `display-domain structure` or `grayscale-amplitude-domain structure` language.

## 14. GT information debt

Every mechanism records current GT use, future non-GT replacement, and one or more labels:

- `GT_DISCOVERY_ONLY`
- `FUTURE_REPLACEABLE`
- `DEPLOYMENT_SOURCE_NOT_READY`
- `GT_PRECISION_DEPENDENT`

Required future replacements include optical azimuth mapping/time state for centre, the complete optical vehicle thread for smoothed trajectory, vehicle/optical size prior for length/width, optical pose/motion/axis estimation for body axis, optical-constrained latent support for crop, and optical global physical identity for GT identity.

## 15. Stage decision

Final allowed states remain:

- `S1L_BODY_SUPPORT_ATTRIBUTION_READY`
- `S1L_BODY_SUPPORT_ATTRIBUTION_PARTIALLY_READY`
- `S1L_BODY_SUPPORT_ATTRIBUTION_NOT_READY`

No state directly authorizes automatic annotation. READY requires body/world/crop separation, a stable GT-neighbourhood basin, temporal parameter smoothness, resistance to strong fixed background, plausible latent support, heldout reproduction of the attribution rule, failure of a difficult trajectory-swap counterfactual, reasonable Raw/Smoothed/perturbation robustness, and no selector/composite-score/GT-IoU dependency.

The minimum casebook alone cannot assign the final stage state.

## 16. Output and Git boundary

Formal protocol, compact manifests, validator, and final report may enter Git. Temporary PNG, animation, large arrays, canonical-field stacks, caches, archives, modified GT, final annotations, and selector/ranking products remain outside Git under:

`D:/profile/research/workspace/output/oty2_s1l_body_support_attribution_20260715`

No S0, S0-M, S0-MV, or frozen S1-L output may be overwritten.
