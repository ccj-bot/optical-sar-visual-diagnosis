# OTY2 S1-L Continuous SAR Structure and Artifact Control Protocol

Date: 2026-07-15

Frozen start HEAD: 32db9108c45e44e0c7d438e91bdae5d30d697e36

Branch: feature/oty2-sar-gt-structure-foundation

## Purpose

S1-L asks whether one physical vehicle has repeatable spatial and temporal response structure in the existing two-dimensional SAR grayscale display domain, and whether those observations survive GT jitter, moving-crop, threshold, normalization, and fixed-background counterfactuals.

The stage may end READY, PARTIALLY_READY, or BLOCKED. Engineering completion is not evidence for READY.

## Frozen boundary

Available observations are the three 766-frame SAR grayscale streams, their fixed 50 fps timeline, the frozen imaging-valid mask, reviewed SAR GT, canonical vehicle identity, benchmark role, and S0-MV continuous threads.

The stage has no ADC or IQ, complex image, phase, authoritative uniform metric grid, absolute scattering cross-section, or independent vehicle-response mask. Response elements must not be called true electromagnetic scattering centers, absolute scattering intensity, metric vehicle parts, or coherent scattering mechanisms.

GT defines a local research neighbourhood, thread identity, coarse spatial context, and background context. GT is not a response mask, exact vehicle geometry, exact vehicle center, or per-pixel ownership truth.

## Frozen A, B, and C inputs

The input ledger is derived mechanically from the S0-MV eligibility and segment manifests. There is no new candidate screening.

- Tier A contains the six S0-MV eligible continuous segments. Development has GM_RM011 PV001, GM_RM011 PV002, GM_RM017 PV002, and GM_RM019 PV001. Heldout has GM_RM017 PV003 and GM_RM017 PV004.
- Tier B contains every remaining reconstructed segment with at least two structure-eligible unique frames and a span of at least two frames. Tier B is diagnostic and cannot be merged with Tier A evidence.
- Tier C contains every remaining segment with exactly one structure-eligible unique frame. Tier C supports coordinate, local-existence, background, and GT-quality checks only.

All 298 structure-eligible GT rows are retained. The 260 temporal-eligible GT rows belong to Tier A. Overlapping duplicate GT rows for one vehicle and frame remain source evidence and contribute to consensus-anchor spread; the grayscale response field is reconstructed once per unique vehicle and frame.

## Coordinate contract

Every response observation retains global display pixels, fan-polar radius and azimuth, raw-GT anchored radial and tangential coordinates, smoothed-GT anchored radial and tangential coordinates, and GT-normalized local coordinates. Local coordinates must invert to global coordinates within numerical precision.

The local radial axis is the unit vector from the frozen fan origin to the GT research anchor. The tangential axis is its perpendicular. This is a display-coordinate construction and not a uniform metric vehicle coordinate system.

## Crop counterfactuals

Each temporal thread has three simultaneous representations.

1. Raw-GT moving crop uses the per-frame consensus of all eligible original GT rows.
2. Smoothed-GT moving crop applies a five-position rolling median to center and size inside the same thread only. It never reads a SAR response peak.
3. Global-coordinate control stores and tracks every observation in the original SAR canvas.

The fixed crop expansion is 1.75 times the projected GT radial and tangential half extents. The analysis neighbourhood is the union of raw and smoothed crops intersected with the frozen imaging-valid mask.

## Intensity and threshold contract

Raw 8-bit grayscale values and source hashes are always retained. Each segment records thread p05, p50, p95, and p99. Three representations are checked: thread-robust normalization, local-background normalization, and log-display normalization.

The fixed normalized score levels are 0.35, 0.50, and 0.65. They are not selected on heldout data and are not changed per frame. Gaussian sigma 1.0 and minimum connected area 6 pixels are fixed diagnostics.

A major temporal observation must persist in at least two score levels and at least two normalization forms. A single-level component is retained as threshold fragile but cannot support a principal temporal claim.

## Structure observations and relations

Allowed observations include stable local peaks, compact response islands, extended response ridges, threshold-fragile components, and response structures connected to crop or context background. These labels describe display-response morphology only.

Each observation stores global and local coordinates, area, perimeter, orientation, elongation, extent, relative and raw intensity, GT-boundary relation, background relation, threshold persistence, normalization persistence, and extraction lineage.

Frame-level relations retain quantitative geometry for spatial neighbourhood, radial or azimuth bands, parallelism, collinearity, near-far ordering, possible shared extension, and shared background connection. No graph neural network is used.

## Temporal correspondence and events

Temporal correspondence is restricted to Tier A and Tier B. Matching combines global motion residual relative to the smoothed GT trajectory, global continuity, area, orientation, strength, threshold persistence, and background relation. Nearest distance alone is insufficient.

The event vocabulary is stable persistence, global-motion consistency, local relative shift, strength increase or decrease, split, merge, birth, death, dominant-component switch, and unresolved correspondence.

Every event records global, raw-local, and smoothed-local displacement. Events that collapse after GT smoothing or global-coordinate inspection are labeled crop_or_gt_jitter_artifact. Events lacking multi-threshold support are labeled threshold_artifact.

## Background counterfactuals

Each development Tier-A thread receives four matched pseudo-threads: same-range neighbour, same-azimuth neighbour, fixed strong-linear-background control, and trajectory-shifted background. They use the source thread crop size, time span, intensity statistics, and extraction rules.

Background controls are falsification evidence, not a trained classifier. Heldout vehicles never select thresholds, relation definitions, event definitions, or background offsets.

## Visual review

Temporary contact pages cover every A, B, and C input, raw grayscale local sequences, raw and smoothed crop overlays, global-coordinate observations, every split, merge, dominant switch and artifact event, all 16 background pseudo-threads, all heldout results, and cross-scene diagnostic failures. Temporary images remain under the workspace output root and are never committed.

Review status may become directly_reviewed_complete only after those pages are directly inspected.

## Stage decision

READY requires all six formal segments, all three coordinate representations, stable multi-threshold relations and events, substantive heldout reproduction, incomplete background replication, complete direct visual review, validator PASS, deterministic replay PASS, and no candidate, selector, or final annotation product.

PARTIALLY_READY is used when the pipeline is complete but positive structure evidence is conditional or incompletely reproduced. BLOCKED is used when principal phenomena are explained by GT, crop, threshold, or background controls.

Only READY permits a later S1-D mechanism-validation task. No S1-L state permits direct entry into automatic annotation.
