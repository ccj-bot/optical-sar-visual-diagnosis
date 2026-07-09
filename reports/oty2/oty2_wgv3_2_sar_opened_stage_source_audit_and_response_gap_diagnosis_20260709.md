# OTY2 WGV3.2 SAR Opened-Stage Source Audit And Response Gap Diagnosis

Date: 2026-07-09

## Scope

WGV3.2 is a source-path audit for the SAR response gap exposed by WGV3.1. It does not run a new experiment, add media, add `outputs/`, create final boxes, revise GT, create SAR-ready annotation, produce selector/ranking output, emit runtime prediction, or claim identity truth.

The audit asks one narrow question:

```text
Which committed sources can legally construct a non-GT SAR response to an optical message, and which sources are only posthoc validation or boundary material?
```

## 1. WGV3.1 Diagnosis

WGV3.1 selected `GM_RM011_WGV14T004` because it bridges the WGV2 graph-instantiated mechanism relation and the WGV3 interactive loop. T004 has accepted optical context, WGV2 nodes, WGV2 relation decisions, and propagated missing-factor rows. That made it a good controlled prototype for testing whether optical constraints, geometry/time feasibility, SAR response, and feedback can be represented without collapsing into identity or annotation.

T004 did not produce a real SAR response because no traceable non-GT opened-stage SAR evidence unit exists in the inspected source stack. The available SAR morphology material for T004 is inherited from GT-local/posthoc references, and WGV3.1 correctly delays that material until validation after the mechanism state has already been proposed.

This is not a failure of the interaction idea. It exposes the missing SAR response layer. The loop can form an optical-to-geometry message and preserve useful state, but it must stop at:

- `mechanism_weak_but_plausible`
- `missing_factor_exposed`
- `insufficient_evidence`
- auxiliary `boundary_preserved` and `identity_risk_blocked`

The concrete blockers are:

- no opened-stage T004 SAR image/content response unit;
- missing GM_RM011 direct azimuth/fan-polar source;
- missing precise optical-to-SAR temporal alignment;
- missing SAR-internal temporal drift chain;
- missing non-GT background, road-edge, static-reflector, guardrail-like, texture-clutter, or competitor contrast;
- active subject-transition and multi-vehicle competition context.

## 2. Concrete Source Audit

The detailed role classification is in:

`reports/oty2/samples/oty2_wgv3_2_sar_source_role_audit_20260709.csv`

The source audit inspected WGV3.0/WGV3.1, WGV2 factor-graph reports and CSVs, WGV1.8 GM_RM011 optical/SAR-posthoc files, WGV2.3 admission-boundary files, and the correction archives. The result is conservative:

- No inspected file can currently construct a concrete non-GT SAR response for T004.
- Several files define the allowed SAR response vocabulary or requirements, but they are not SAR image/content observations.
- WGV1.8 SAR GT-local morphology files are posthoc validation sources only.
- WGV2.1/WGV2.2 files provide graph context, permission gates, missing factors, and boundary guardrails.
- M005/M016 sources preserve boundaries; they do not authorize bridging.
- Failed atlas/support archives are warning sources, not positive response sources.

Important posthoc GT-only sources:

- `reports/oty2/samples/oty2_wgv1_8_gm011_sar_gt_local_mechanism_reading_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_8_gm011_optical_sar_physical_mechanism_links_20260709.csv`
- `reports/oty2/samples/oty2_wgv3_1_gt_posthoc_validation_boundary_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_3_gt_validation_boundary_rules_20260709.csv`
- `docs/oty2_gt_local_energy_field_atlas_correction_archive.md`
- `docs/oty2_gt_support_failure_concept_correction_archive.md`

Those sources can validate or falsify a proposed mechanism. They must not define a SAR review field, SAR response unit, SAR factor value, threshold, candidate, selected component, score, rank, runtime prior, final annotation, or identity claim.

## 3. T004 Response Feasibility

`GM_RM011_WGV14T004` currently has:

- WGV2 graph context: yes;
- accepted optical message context: yes;
- posthoc SAR morphology vocabulary: yes, through reserved GT-local/posthoc references;
- non-GT SAR response evidence: no;
- SAR temporal drift chain: no;
- non-GT negative contrast: no;
- direct GM_RM011 azimuth/time field source: no;
- competitor separation: unresolved.

Therefore T004 remains the correct WGV3.1 response-gap case. It can be used to explain what source layer is missing, but it should not be promoted into a positive SAR-response closure example.

The exact source files needed before T004 can produce a legal SAR response are:

- a committed source path to SAR image/content or derived non-GT SAR content for the T004 temporal neighborhood;
- a runtime-safe GM_RM011 time and azimuth/fan-polar review field source;
- a SAR-internal adjacent-frame or neighbor-frame drift source;
- a non-GT contrast source covering background, road edge, static reflector, guardrail-like ridge, texture clutter, or competitor region;
- a permission record proving that GT-local morphology did not construct the response.

## 4. T001 Comparison

`GM_RM011_WGV14T001` looks better than T004 for a future first positive mechanism-construction prototype because it has clearer near-field truncation, partial-vehicle, edge-contact context, and stronger early GM_RM011 posthoc SAR morphology references.

That does not make T001 ready for a SAR response now. The inspected sources still do not provide an opened non-GT SAR image/content response unit for T001. T001 also remains blocked by missing direct GM_RM011 azimuth/time mapping and missing SAR temporal drift chain.

Conclusion:

- T004 should stay as the controlled response-gap / missing-factor exposure case.
- T001 is the better candidate for a future first positive response prototype only after a legal opened SAR response source is traced.
- Do not silently substitute T001 for T004 inside WGV3.1/WGV3.2 conclusions.

## 5. Boundary Guardrail Comparison

`GM_RM011_M005` and `GM_RM011_M016` are boundary guardrails. WGV2 records them as boundary-preserved / blocked cases, and WGV3.1 uses them only to keep T004 competition risk visible.

They must not be used as bridge permission:

- M005 blocks unsafe merging across a nearby different white-car boundary.
- M016 blocks unsafe merging across a same-color SUV competition boundary.
- Missing boundary-specific SAR evidence is a reason to preserve the boundary, not to relax it.

## 6. SAR Opened-Stage Response Unit Definition

A valid SAR response unit needs all of the following before it can answer an optical message:

- `source_path`: committed SAR image/content source or derived non-GT SAR content source;
- `time_frame_scope`: explicit frame or neighbor-frame scope for the response;
- `review_field_source`: runtime-safe time/azimuth/geometry field, not GT center or posthoc overlap;
- `morphology_vocabulary`: runtime-safe or explicitly opened-SAR-stage vocabulary such as vehicle-scale ridge, endpoint hotspot, weak opposite-side return, shell contour, temporal non-jump, ambiguity, or insufficient evidence;
- `temporal_neighbor_availability`: adjacent-frame or temporal-neighbor content when drift or non-jump is claimed;
- `non_gt_negative_contrast`: background-like, road-edge, static-reflector, guardrail-like ridge, texture-clutter, or competitor contrast selected without GT;
- `permission_status`: explicit proof that the response was not built from GT-local morphology;
- `downstream_gt_validation`: GT validation separated after the mechanism proposal.

If any of these are missing, the legal response is `insufficient_evidence` or a source-opening request, not a morphology closure.

## 7. Recommended Next Step

Recommended route: `WGV3.3c`.

First build a GM_RM011 runtime-safe time/azimuth review-field source before any SAR response instantiation. This is the shared blocker for T004 and T001.

After that source exists:

- keep T004 as the response-gap regression case;
- use T001 as the preferred first positive mechanism-construction candidate if a concrete opened SAR image/content source and non-GT contrast source can also be traced.

Do not start WGV3.3 by copying GT-local morphology into the SAR response. GT remains downstream validation only.

## Boundary Summary

WGV3.2 creates a concrete source audit and response-gap diagnosis. It does not create an experiment, new visual output, final box, revised GT, SAR-ready annotation, selector/ranking artifact, runtime prediction, identity truth, or GT-guided runtime construction.
