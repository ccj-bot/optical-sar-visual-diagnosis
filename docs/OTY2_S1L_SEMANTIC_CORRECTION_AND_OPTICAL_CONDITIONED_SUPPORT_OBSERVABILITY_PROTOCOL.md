# OTY2 S1-L Semantic Correction and GT-Discovery Proxy Audit for Optical-Conditioned Support Observability

Date: `2026-07-16`

Frozen start HEAD: `75eed68a19c94428c27d8a217d3dab36c56f20d6`

Chinese name: `S1-L 结论语义纠偏与光学条件支撑可观测性分解（GT 探索代理审计）`

## 1. Scope

This protocol is a bounded S1-L supplement. It does not enter S1-D and does not authorize latent support reconstruction, automatic annotation, a final box, GT modification, candidate-bank generation, selector/ranking, model training, weighted/composite scoring, threshold search for PASS, or GT-IoU decisions.

All S0, S0-M, S0-MV, S1-L, and body-support products at the frozen start remain unchanged.

This round studies an optical-conditioned research question using GT-discovery proxies. No optical-derived centre, axis, or scale input is executed. Consequently, `OPTICAL_CONDITIONED_SUPPORT_READINESS` cannot receive an unrestricted positive status in this round and must remain `NOT_EVALUATED_WITH_REAL_OPTICAL_INPUT_GT_PROXY_ONLY`.

## 2. Semantic decomposition

Trajectory swaps between real vehicle regions are `IDENTITY_NEGATIVE_CLASS_POSITIVE`. They are valid for physical-identity falsification and invalid for vehicle-class-versus-background falsification.

The final report must contain exactly these ten decomposed conclusions:

- `GT_CONDITIONED_BODY_ALIGNMENT`
- `BODY_AXIS_INCREMENTAL_VALUE`
- `VEHICLE_CLASS_SUPPORT_OVER_BACKGROUND`
- `SAR_ONLY_PHYSICAL_IDENTITY_SPECIFICITY`
- `CENTER_RADIAL_OBSERVABILITY`
- `CENTER_TANGENTIAL_OBSERVABILITY`
- `LONG_SCALE_OBSERVABILITY`
- `SHORT_SCALE_OBSERVABILITY`
- `AXIS_OBSERVABILITY`
- `OPTICAL_CONDITIONED_SUPPORT_READINESS`

It must also state `UNIQUE_BOX_RECOVERY=NOT_EVALUATED_NOT_AUTHORIZED`.

## 3. Research-unit registry

Every unit must be assigned one semantic class:

- `TRUE_VEHICLE_POSITIVE`
- `IDENTITY_NEGATIVE_CLASS_POSITIVE`
- `VEHICLE_CLASS_NEGATIVE`
- `TEMPORAL_NEGATIVE`

The registry records whether each unit is valid for identity, vehicle-class, temporal-correspondence, and temporal-direction tests. Vehicle-class-negative controls must receive direct visual review and explicit baseline/parameter-envelope spatial-cluster membership. Named controls are not automatically distinct replicates and are not statistically independent, cross-vehicle, cross-time, or cross-scene samples.

The frozen registry contains exactly 21 units: 3 true-vehicle positives, 2 identity-negative/class-positive swaps, 4 vehicle-class-negative background controls, and 12 temporal-correspondence negatives. The four backgrounds form 3 baseline equal-support spatial clusters and 2 strict one-dimensional parameter-envelope clusters.

## 4. Equal-support representations

All four representations use exactly the same source-window dimensions, `256×128` grid, sampling density, interpolation, imaging-valid rule, grayscale input, and per-frame support dimensions:

1. `WORLD_FIXED`: thread-fixed world centre, global x/y axes;
2. `CENTER_TRACKED_CARTESIAN`: tracked centre, global x/y axes;
3. `CENTER_TRACKED_RADIAL`: tracked centre, radar tangential/radial axes;
4. `CENTER_TRACKED_BODY`: tracked centre, GT-derived unsigned long/short axes.

The common half-width and half-height are the frozen thread reference long/short axes times the existing `1.75` context factor. The fixed-world centre rule is frozen from PV002 as the coordinate-wise median tracked centre and replayed without tuning. Rotating an anisotropic rectangular window changes the source pixels sampled; therefore radial/body deltas combine axis orientation, rotated support footprint, and resampling. They are not pure coordinate-axis effects.

Required increments remain single-metric deltas:

- translation compensation: `CENTER_TRACKED_CARTESIAN - WORLD_FIXED`;
- radial-axis increment: `CENTER_TRACKED_RADIAL - CENTER_TRACKED_CARTESIAN`;
- GT body-oriented-window versus Cartesian: `CENTER_TRACKED_BODY - CENTER_TRACKED_CARTESIAN`;
- GT body-oriented-window versus radial: `CENTER_TRACKED_BODY - CENTER_TRACKED_RADIAL`.

No deltas may be summed across metrics.

`BODY_AXIS_INCREMENTAL_VALUE` must therefore be interpreted as `NOT_SEPARATELY_IDENTIFIED_FROM_GT_BODY_ORIENTED_ANISOTROPIC_WINDOW_SUPPORT` unless a later design holds the sampled source footprint fixed. The current measured delta is a GT-conditioned body-oriented-window increment, not pure physical body-axis attribution.

## 5. Pair contract

Every research unit is replayed under both Raw-GT and Smoothed-GT anchors. Raw-GT and Smoothed-GT define separate source-positive pair sets; they are not independent samples. Smoothing dependence may not be hidden by running counterfactuals on Smoothed-GT alone. A source-positive pair candidate requires:

- frame gap at least 10;
- time gap recorded explicitly;
- baseline GT-conditioned view-angle difference at most 5 degrees;
- at least 20 common-valid pixels and a finite field NCC in the frozen membership reference `CENTER_TRACKED_BODY + GT_DERIVED_UNSIGNED_BODY + FIXED_REFERENCE`.

Axis and registration reliability are recorded for both source-positive endpoints. Primary evidence uses source pairs whose endpoints are both axis- and registration-reliable; all source candidates remain in the audit. Counterfactual target registration is not inferred from source reliability and is explicitly marked not independently validated.

The source-positive pair set is frozen before testing representations, axis placebos, the local normalization path, perturbations, or counterfactuals. Each counterfactual receives only the frame intersection of its source-positive pair set; it may not reselect pairs from the counterfactual target. Each row stores source-pair identity/hash, projected-pair hash, frozen common-valid pixel count/fraction, membership-reference NCC finiteness, eligibility/reason, and reliability scope.

Leave-one-pair-out, leave-one-frame-out, unique-frame count, maximum frame degree, and pair-graph component count are mandatory. Pair rows are repeated contrasts over shared frames: pair count is not sample size, and neither sensitivity analysis supplies an effective independent `N`. Pair count `<=4` is always `SPARSE_PAIR_EVIDENCE`; a larger count is only `PAIR_COUNT_GT4_SHARED_FRAME_REPEATED_EVIDENCE`.

## 6. Axis-placebo rules

The same centres, scales, windows, pair sets, and normalization paths are used for:

1. `GT_DERIVED_UNSIGNED_BODY`
2. `THREAD_FIXED_MEDIAN_AXIS`
3. `FRAME_SHUFFLED_AXIS`
4. `TIME_SHIFTED_AXIS`
5. `GT_AXIS_PLUS_90`
6. `TRAJECTORY_TANGENT_AXIS`
7. `GLOBAL_FIXED_AXIS`

The deterministic shuffle seed is `1702`; the axis-placebo time shift is a circular `+8` position shift of the frozen axis sequence; and the global fixed axis is image x. Separately, the temporal trajectory/centre counterfactual uses exact `+8` SAR-frame correspondence (`0.16 s` on the current cadence). The exact temporal shift retains `56/55/50` aligned samples for PV002/PV003/PV004 while moving the centre by roughly `0.69-0.73` reference short axes. These rules are frozen before the experiment and replayed unchanged on PV003/PV004.

Each GT-versus-placebo comparison is reported separately as one of:

- `GT_DOMINATES_PLACEBO`
- `PLACEBO_INDIFFERENT`
- `PLACEBO_DOMINATES_GT`
- `NORMALIZATION_DEPENDENT`
- `INSUFFICIENT_PAIR_EVIDENCE`

The seven axes are not ranked.

## 7. Dual normalization

Every representation, axis rule, and parameter profile runs both:

- `FIXED_REFERENCE`: frozen row-level `local_background_median` and `thread_raw_p99`;
- `CANDIDATE_LOCAL_REESTIMATED`: background median estimated from the outer ring after excluding the central core, dynamic range re-estimated per candidate, and saturation plus valid-mask fractions recorded.

The audit records `candidate_outer_pixel_count` separately from `background_sample_count`. For `FIXED_REFERENCE`, the current candidate outer ring is not an estimator sample and the original source-reference sample count is unavailable; only the local path may report the current outer-ring count as background samples.

The central core never participates in background estimation. The local path may not silently fall back to the fixed reference. Opposite directions are `NORMALIZATION_DEPENDENT`.

Any failed normalization is invalid evidence, not a zero-valued image. Its field, orientation, and thin-edge metrics are unavailable and it is excluded from Pareto feasibility. If one path has no valid settings, the dual-path result is `NOT_IDENTIFIABLE` with an explicit invalid-profile reason.

## 8. Evidence families

Continuous grayscale fields remain a diagnostic channel. Exactly two additional non-embedded structure families are allowed:

### 8.1 `LOCAL_ORIENTATION_ORGANIZATION`

Report dominant axial direction, anisotropy, time-adjacent axial-orientation continuity, pair direction agreement, and relation to the active representation axes. Only `CENTER_TRACKED_BODY + GT_DERIVED_UNSIGNED_BODY` may rename representation x/y as body long/short. Use normalized structure-tensor orientation proxies, but do not claim geometric-scale or resampling invariance: fixed Sobel/Gaussian operators remain coupled to the `256×128` grid.

### 8.2 `SPATIAL_RELATION_TOPOLOGY`

Use a Canny thin-edge connectivity proxy and report thin-edge fraction, connected components, endpoint/branch counts, pixel-graph adjacency, relative centroid, pairwise keypoint-distance relations, spatial-collinearity proxy, parallel-to-representation-axis fractions, and temporal/pair stability. This is explicitly **not** a morphological skeleton and is not a recovered physical vehicle topology. Do not form an embedding or weighted family score.

## 9. Counterfactual classes

### 9.1 Identity negative, class positive

Use real-vehicle trajectory swaps only for `SAR_ONLY_PHYSICAL_IDENTITY_SPECIFICITY`.

### 9.2 Vehicle-class negative

Use four directly reviewed PV002-geometry controls:

1. `S1L-BG-0010`: moving same-azimuth background;
2. `S1L-BG-0011`: quality-limited fixed strong-line diagnostic;
3. `S1L-BG-OCS-B3-SA35N`: moving hard-scatter/partial-complexity background at `dr=-209.722594 px, dt=0`;
4. `S1L-BG-OCS-B4-FX88`: fixed anisotropic-speckle background at `dr=479.36592922347614 px, dt=667.2840797804607 px`.

BG0010 and BG0011 overlap strongly (`max rotated-footprint overlap=0.9440324609715243`, `min centre distance=6.9946758959516115 px`) and therefore form one baseline spatial cluster. B3 forms a second cluster. FX88 has full valid support, zero reviewed-GT overlap, and zero baseline rotated-footprint overlap with BG0010, BG0011, and B3, so it forms a third baseline cluster. Direct 65-frame/four-representation review found weak anisotropic speckle but no persistent strong line or vehicle-shaped support in FX88; it must not be relabelled as a strong-line replacement.

The frozen 64-member fixed-grid enumeration contains no candidate that is both strictly disjoint and visibly a persistent strong-line control. BG0011 is retained only as a same-cluster role diagnostic, not a background replicate. Under the full one-dimensional parameter envelope, FX88 is not strictly outer-circle-disjoint from BG0010, so only two strict parameter-envelope clusters may be claimed: `{BG0010, BG0011, FX88}` and `{B3}`.

These controls establish a PV002 development-geometry class-negative audit, not statistical independence, cross-vehicle/cross-time/cross-scene generalization, or proof of absolute physical absence. Vehicle-class conclusions must report both named-control and cluster-level results and may not count BG0010/BG0011 as two independent negatives.

### 9.3 Temporal negative

Use deterministic shuffle, reversal, trajectory time shift, and centre phase shift. `TEMPORAL_REVERSE` is reverse-order image-to-original-anchor correspondence mismatch. It tests correspondence robustness only; it is not an arrow-of-time experiment. All current direction-insensitive metrics must mark temporal direction as unavailable.

All counterfactuals use the same equal-support extraction dimensions, source-pair freeze/frame-intersection projection contract, dual normalization, and metrics as positive units. Their transform rules and projected frame intersections remain counterfactual-specific.

## 10. Parameter grid-response diagnostics

The frozen grids are:

- centre radial/tangential fractions: `-0.25, -0.125, 0, 0.125, 0.25`;
- long/short scales: `0.85, 0.925, 1.0, 1.075, 1.15`;
- unsigned-axis deltas: `-12, -6, 0, 6, 12` degrees.

Profiles are one-dimensional: only the named parameter changes while all others remain at baseline. Metrics remain separate. No best setting, winner, rank, or weighted objective is emitted.

The five-point profiles and Pareto-nondominated grid values describe diagnostic grid-response patterns only. They are not feasible physical values, parameter estimates, confidence intervals, identifiable intervals, or one-sided physical bounds. All formal `observability_state` values in this round remain `NOT_IDENTIFIABLE`; positive identifiability vocabulary is reserved for a later method with a real identification criterion.

A grid-edge pattern is only an edge-touching diagnostic pattern. Invalid normalization/metric settings are excluded before Pareto construction; source/projected pair-set hashes and eligible-pair counts are carried into every profile row.

Long/short-scale profiles change source-window extent while retaining a fixed `256×128` output grid. Their responses couple window extent, interpolation, effective source pixels per grid cell, and fixed-grid structure estimators. They are scale-plus-resampling responses, not physical scale bounds. Each scale profile must report effective source-pixel density and `physical_scale_bound_status=NOT_EVALUATED_FIXED_GRID_RESAMPLING_CONFOUND`.

## 11. Semantic interpretation guardrails

- Field NCC measures registered display-field stability, not vehicle identity or physical support by itself.
- Structure-tensor direction and Canny thin-edge relations are proxies in the normalized 8-bit display domain; neither may be described as raw-amplitude, scattering-centre, ridge, skeleton, or recovered-body evidence.
- Pair rows are repeated contrasts with shared frames. LOPO and LOFO are leverage diagnostics; pair count is neither independent sample size nor effective `N`.
- Time reversal is a correspondence-mismatch control only. Invariance under reversal is not positive temporal-direction or arrow-of-time evidence.
- The two identity swaps cover PV002/PV003 only. The four named background controls are PV002-geometry controls only and represent three baseline clusters but two strict parameter-envelope clusters. These scope asymmetries cap broad identity/class generalization claims.
- PV003/PV004 replay means within-scene other-vehicle fixed-rule reuse, not independent heldout generalization, deployment validation, or removal of GT conditioning.

## 12. Continue gate

Latent support reconstruction remains forbidden unless all are satisfied in a later round:

1. the GT-derived body-oriented-window rule is better than at least a majority of orientation-rule placebos, while remaining explicitly non-identifiable as pure axis attribution;
2. correct vehicles exceed vehicle-class-negative backgrounds in both new structure families;
3. conclusions do not depend on only one normalization path;
4. within-scene other vehicles replay the rule, followed by genuinely independent data in a later round;
5. at least one centre or scale parameter obtains a physical interval or one-sided constraint from a future identification method that separates scale from resampling; the present five-point grid/Pareto diagnostic cannot satisfy this item;
6. no selector, ranking, GT IoU, or weighted score is used.

Failure of SAR-only identity specificity is not by itself a veto because optical time owns physical identity.

If the directly reviewed PV002-geometry background controls reproduce both structure families under both normalization paths, stop independent support recovery from current 8-bit display structure and turn to stronger optical priors or raw amplitude/complex/IQ/fixed-mapping data. Spatially distinct controls still do not constitute statistically independent evidence.

## 13. Output boundary

Formal protocol, reports, compact CSV manifests, runner, replay checker, and validator may enter Git. Temporary PNGs, arrays, caches, animations, archives, modified GT, final annotations, and latent-support products remain outside Git under:

`D:/profile/research/workspace/output/oty2_s1l_optical_conditioned_support_observability_20260716`
