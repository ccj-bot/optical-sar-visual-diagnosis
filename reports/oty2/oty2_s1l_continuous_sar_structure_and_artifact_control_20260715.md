# OTY2 S1-L Continuous SAR Structure and Artifact Control (20260715)

## 1. Executive result

- Stage state: `S1L_CONTINUOUS_STRUCTURE_PARTIALLY_READY`.
- S1-D allowed: `false`.
- Automatic annotation allowed: `false`.
- Research object: two-dimensional SAR grayscale-display local response structure.
- GT role: local research neighbourhood and same-vehicle thread only; not a response mask or geometric truth.

## 2. Frozen inputs

- A/B/C segments: `A:6;B:11;C:14`.
- Source structure-eligible GT rows: `298` (A temporal rows `260`).
- Unique frame-level response fields: `274`.
- Six formal segment frame counts: `S0MV-GM_RM011-PV001-SEG01:36unique/60rows;S0MV-GM_RM011-PV002-SEG01:7unique/7rows;S0MV-GM_RM017-PV002-SEG02:65unique/65rows;S0MV-GM_RM017-PV003-SEG01:67unique/67rows;S0MV-GM_RM017-PV004-SEG01:58unique/58rows;S0MV-GM_RM019-PV001-SEG01:3unique/3rows`.

The 298 eligible GT rows are all retained. Nineteen same-vehicle/same-frame positions contain overlapping duplicate GT records; these rows contribute to the raw anchor consensus and GT-spread audit, while the response field is reconstructed once per unique scene/vehicle/frame.

## 3. Response-field reconstruction

- Local response fields: `274`.
- Maximum global/local inverse error: `0.0` px.
- Every field retains the raw grayscale image hash, global pixel coordinates, fan-polar r/theta, raw-GT local coordinates, smoothed-GT local coordinates, and raw intensity statistics.
- Fixed score levels are 0.35/0.50/0.65 after thread-robust normalization; local-background and log-display forms are cross-checks, not separately tuned displays.

## 4. Structure observations and relations

- Structure observations: `3194`; multi-threshold/cross-normalization major observations: `2322`.
- Single-threshold-only fragments retained as frame-level counts rather than formal objects: `6237`.
- Structure type mix: `background_connected_response_structure:872;compact_response_island:284;extended_response_ridge:285;stable_local_peak:1753`.
- Spatial relations: `4279`; relation mix: `collinear:1483;near_far_correspondence:4279;parallel:1288;possible_shared_extended_response:1635;same_azimuth_band:632;same_radial_band:813;spatial_neighbor:4279`.
- These are response observations, not vehicle parts, physical scattering centers, candidate boxes, or selector inputs.

## 5. Temporal events and artifact controls

- Temporal events: `2384`; event mix: `birth:265;death:237;dominant_component_switch:91;global_motion_consistent:667;local_relative_shift:39;merge:44;split:50;stable_persistence:446;strength_decrease:17;strength_increase:10;unresolved_correspondence:518`.
- GT/crop-jitter artifacts: `27`.
- Threshold-fragile events: `0`.
- Background-connected events: `0`.
- Four counterfactual audit rows are present for every event; total audit rows: `9536`.

## 6. Background counterfactuals

- Background pseudo-threads: `16` (four for each development A-layer thread).
- Threads reproducing stable persistence at 65% of the vehicle frequency: `3`.
- Threads reproducing the full stable-plus-complex conclusion: `3`.
- Background result: `background_controls_do_not_replicate_all_vehicle_patterns`.

- Usable background controls: `10` / `16`.

## 7. Development, heldout, and cross-scene scope

- Development finding: `multi-threshold stable observations and generic persistence exist, but vehicle specificity remains conditional because background controls reproduce part of the persistence`.
- Heldout reproduction: `conditional_generic_reproduction:2`.
- GM_RM011/GM_RM019 cross-scene diagnosis: `GM_RM011 and GM_RM019 remain diagnostic support/counterexample sources; no formal cross-scene claim`.
- Heldout is dominated by GM_RM017 and can support only same-scene cross-vehicle reproduction, never a cross-scene generalization claim.

## 8. Visual review, validation, and replay

- Visual artifacts: `81`; review status: `directly_reviewed_complete`.
- Fixed-input replay: `PASS`.
- Temporary PNG assets remain outside Git under the workspace output root.

### Direct visual findings

- Raw versus smoothed crop control: `raw and smoothed crops usually overlap, while 27 event rows collapse under GT/crop control`.
- Structure stability: `GM_RM017 shows recurring compact/horizontal response chains, but several development and heldout intervals also show abrupt dense component explosions and crop-edge contamination`.
- Split/merge/switch review: `many split, merge, and dominant-switch pages coincide with fragmentation bursts or boundary contact; they are not accepted as vehicle dynamics`.
- Background review: `3 controls reproduce stable persistence and only 10/16 controls satisfy the full quality contract`.

## 9. Decision

The final state is `S1L_CONTINUOUS_STRUCTURE_PARTIALLY_READY`. S1-D entry is `false`. Automatic annotation entry is always `false`.

## 10. Explicit non-execution

This run did not modify optical P1-F, canonical identity, hard synchronization, the frozen mapping, or any S0/S0-M/S0-MV product. It did not use P1-F propagation, infer a vehicle-response mask, generate a candidate box, selector, ranking, Gate, oracle, composite score, trained model, final SAR annotation, phase/IQ reconstruction, or authoritative metric-grid claim.
