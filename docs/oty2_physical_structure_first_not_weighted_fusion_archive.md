# OTY2 Physical Structure First, Not Weighted Fusion Archive

Updated: 2026-07-04

This archive records a scope correction for the OTY2 mechanism diagnosis branch. The next step is not weighted evidence fusion, feature scoring, selector preparation, or score proxy optimization. The main line is physical SAR vehicle structure: vehicle-scale shell grammar plus temporal non-jump / gradual drift.

## Core Position

Weighted evidence fusion is not the main line. It is only a fallback bookkeeping layer for a later stage, after the physical structure grammar and temporal drift mechanism have been understood. A weighted sum of time, azimuth, state, and energy cues would hide the mechanism too early.

The correct OTY2 question is:

Can SAR image evidence be described as scattering atoms, vehicle parts, and GT-scale shell hypotheses whose structure persists or drifts gradually over time?

The incorrect question for this round is:

Which weighted score best selects a candidate?

## Physical SAR Vehicle Grammar

The grammar separates:

- `scattering_atom`: top-k peak, small bright point, local scatterer, or tiny component. It is not a vehicle.
- `vehicle_part`: side ridge, endpoint hotspot, corner reflector, weak far-side return, edge segment, or local body block. It can support a vehicle hypothesis but is not the whole vehicle.
- `vehicle_scale_shell_hypothesis`: a GT-scale composition of multiple parts forming a shell, boundary, long/short-axis structure, strip-plus-endpoint relation, or discontinuous but coherent body outline. It remains posthoc and is not a final box.

GT-scale compatibility is required. Small parts cannot be promoted into a baby-car shell.

## Human Contour Reference

The rough 2026-07-04 human contour markings are useful as visual vocabulary but not as truth. They emphasize:

- long side ridges as body-side structure;
- endpoint or corner hotspots;
- weaker opposite-side returns;
- discontinuous but coherent shell completion;
- the need to read parts at GT vehicle scale.

The markings are coarse, may be wrong, and are not committed as raw files. They must not be used as revised GT, annotation proposals, final boxes, selector labels, or identity truth.

## GT And Support Boundary

SAR GT is a posthoc morphology anchor, but GT quality must still be audited. A questionable GT weakens the morphology conclusion and routes the case to manual review.

Optical-derived support is a feasible region, not a final rule. If GT-anchored vehicle-scale morphology is outside support, the correct diagnostic is support construction failure / support miss, not support-internal vehicle search.

## Temporal Drift Boundary

Temporal non-jump and gradual drift are central mechanisms. A vehicle-like shell should not appear as an unrelated single-frame peak. Ridges, hotspots, and shell centroids should persist or move smoothly when data are available.

Temporal drift support is not identity truth. It is a posthoc mechanism signal.

## Forbidden In This Stage

- revised GT
- final candidate box
- annotation proposal
- selector/ranking
- weighted-fusion mainline
- best-weight selection
- training or threshold tuning
- identity truth
- GT-guided runtime prediction logic
- shell grammar as an automatic annotation rule
- temporal drift as identity truth
- mixing SAR-only or GM_RM011 rows into paired correspondence
- mixing dropout/no-match rows into clean paired morphology

## Allowed In This Stage

- GT-anchored physical morphology grammar
- part-to-shell relation diagnostics
- GT-scale compatibility checks
- temporal drift physical consistency checks
- support failure physical explanation
- weighted fusion deferred boundary
- Chinese atlas for mechanism explanation

## Why This Corrects The Local Optimum

The local optimum would be to convert every cue into a weight before the structure is understood. That would blur atom, part, shell, support failure, GT quality, and temporal drift into one score. This archive keeps those layers separate so later fusion, if needed, can be bookkeeping over understood physical evidence rather than a substitute for mechanism.
