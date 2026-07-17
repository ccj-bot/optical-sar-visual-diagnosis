# OTY2-RSA0-R2 Phase A Frozen Findings

Date: `2026-07-17`

Phase A is audit-only. No R1 source or frozen R1 artifact is modified.

## R2A-F01 — CONFIRMED_IMPLEMENTATION_ERROR

R1 GT_CONDITIONED_RESEARCH_ORACLE uses the unwarped raw image and raw temporal maps; it is RAW_SAR_DISPLAY, not a GT-aligned image stack.

- Stage: `S06_GT_FAMILY`
- Code evidence: `run_oty2_rsa0_r1_free_geometry_reaudit.py:620-642`
- Array/manifest evidence: R1 GT family has the same source image as RAW and no GT resampling matrix or aligned stack artifact.
- Allowed Phase B action: construct GT_ALIGNED_RESEARCH_STACK by synchronously translating every image, valid-source mask, atlas geometry, and point to the first-frame GT center before recomputing time channels
- Scientific impact: R1 coordinate-family comparisons do not establish GT-conditioned temporal representation.

## R2A-F02 — CONFIRMED_IMPLEMENTATION_ERROR

R1 OPTICAL_PROXY_CONDITIONED leaves the image fixed and shifts only atlas geometry by proxy-minus-GT drift.

- Stage: `S07_PROXY_FAMILY`
- Code evidence: `run_oty2_rsa0_r1_free_geometry_reaudit.py:623-629`
- Array/manifest evidence: Primary evidence cards show nonzero geometry displacement over an unchanged image; PV003 SAR 384 drift is (-22.643,+130.210) px.
- Allowed Phase B action: separate OPTICAL_PROXY_ALIGNED_STACK from OPTICAL_PROXY_LOCALIZATION_ERROR_SAMPLING
- Scientific impact: R1 proxy results measure localization-error sampling, not proxy-aligned representation quality.

## R2A-F03 — CONFIRMED_IMPLEMENTATION_ERROR

R1 world-stabilized family computes only 11 single-frame channels and has no temporal channels.

- Stage: `S05_WORLD_STACK`
- Code evidence: `run_oty2_rsa0_r1_free_geometry_reaudit.py:630-642`
- Array/manifest evidence: R1 metrics channel sets: WORLD=11, GT-named=27, PROXY-named=27.
- Allowed Phase B action: build the full world-stabilized five-frame stack and recompute every temporal channel
- Scientific impact: R1 cannot answer what time represents after world stabilization.

## R2A-F04 — CONFIRMED_NAMING_ERROR

temporal_*_local_component_continuity is high-intensity pixel occurrence frequency and contains no connected components, IDs, or cross-frame association.

- Stage: `S10_TEMPORAL_CHANNEL`
- Code evidence: `run_oty2_rsa0_r1_free_geometry_reaudit.py:365-378`
- Array/manifest evidence: The array is a sum of per-frame >=80th-percentile boolean pixels divided by window length.
- Allowed Phase B action: rename to temporal_high_intensity_pixel_frequency and retain the old name only as historical provenance
- Scientific impact: R1 component-continuity wording overstates the formula.

## R2A-F05 — CONFIRMED_IMPLEMENTATION_ERROR

R1 AUC truncates each flattened class to its first 3000 samples.

- Stage: `S13_AUC`
- Code evidence: `run_oty2_rsa0_r1_free_geometry_reaudit.py:401-408`
- Array/manifest evidence: NumPy mask extraction is row-major, so the retained samples are spatially ordered.
- Allowed Phase B action: report exact rank AUC, fixed-seed uniform sampling, spatial stratification, legacy-first3000, and background subtype results separately
- Scientific impact: R1 AUC can be biased by mask geometry and scan order.

## R2A-F06 — CONFIRMED_IMPLEMENTATION_ERROR

R1 robust01 uses full-frame per-frame 2%-98% quantiles without the fixed fan or transformed valid-source masks.

- Stage: `S08_NORMALIZATION`
- Code evidence: `run_oty2_rsa0_r1_free_geometry_reaudit.py:95-103`
- Array/manifest evidence: Primary frames contain about 39.3% global zeros and about 29.0% zeros even inside the imaging-valid fan.
- Allowed Phase B action: compare full-frame, valid-fan, window-frozen valid-fan, and local matched ranges
- Scientific impact: Per-frame scaling and invalid black support can manufacture or suppress apparent differences.

## R2A-F07 — CONFIRMED_AUDIT_GAP

R1 consistency rows hard-code several visual audit booleans rather than deriving them from point patches or direct-review records.

- Stage: `S11_ATLAS_AUDIT`
- Code evidence: `run_oty2_rsa0_r1_free_geometry_reaudit.py:589-601`
- Array/manifest evidence: skeleton_inside_definite_or_probable, definite_covers_dark_areas, and background_controls_on_actual_background are assigned constants.
- Allowed Phase B action: generate per-point patches and explicit atlas-point statuses without modifying atlas v1
- Scientific impact: R1 atlas validity statements require direct reinspection.

## R2A-F08 — CONFIRMED_CONCLUSION_LOGIC_ERROR

R1 maps median skeleton-minus-background >=0.03 directly to skeleton_signal_retained.

- Stage: `S14_CONCLUSION_GATE`
- Code evidence: `run_oty2_rsa0_r1_free_geometry_reaudit.py:695-705`
- Array/manifest evidence: Weak/strong frames, subtype activation, ridge distance, coordinate dependence, and counterexamples are not required by the label.
- Allowed Phase B action: replace the label with separate evidence dimensions and conclusion lineage
- Scientific impact: Several R1 top-channel statements are not supported by their stated decision logic.

