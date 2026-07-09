# OTY2 WGV2.2 Factor-Graph Constraint Propagation And Missing-Factor Audit

Date: 2026-07-09

## Scope

WGV2.2 uses the committed WGV2.1 graph instances as fixed input. It does not add windows, run optimization, aggregate scores, select candidates, rank candidates, generate annotations, or create runtime artifacts.

Input stack:

- `reports/oty2/samples/oty2_wgv2_1_factor_graph_node_instances_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_1_factor_graph_factor_instances_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_1_mechanism_relation_decisions_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_1_factor_graph_consistency_audit_20260709.csv`
- WGV2.0 node, factor, and relation outcome schemas.

Outputs:

- `reports/oty2/samples/oty2_wgv2_2_constraint_propagation_audit_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_2_missing_factor_diagnosis_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_2_factor_role_summary_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_2_mechanism_readiness_summary_20260709.csv`

## Direct Answers

### 1. What constraints actually propagate through the WGV2.1 graph?

Five constraint families propagate:

- Optical state and continuity propagate as optical-only support or weak support.
- SAR morphology and SAR temporal drift propagate as posthoc mechanism vocabulary, ambiguity, or insufficiency.
- Geometry feasibility propagates missing mapping, ambiguous offset bands, or boundary-blocked domains.
- Boundary and competitor factors propagate hard blockers for M005, M016, weak GM_RM017 context edges, and V004.
- Evidence permission factors propagate a hard use gate on every tested window.

The propagated states are conservative: one GM_RM011 window is `mechanism_supported_but_posthoc_only`, one is `mapping_unresolved_blocks_consumption`, one is `mechanism_weak_or_ambiguous`, two GM_RM011 boundaries are `boundary_preserved_and_blocked`, three GM_RM017 weak windows are `mechanism_weak_or_ambiguous`, and V004 is `identity_risk_blocked`.

### 2. Which factors support mechanism explanation?

The main supporting factors are:

- `optical_state_factor`: explains truncation, edge contact, visible-unboxed gaps, dropout, primary-box repair, and bridge risk.
- `optical_continuity_factor`: preserves accepted or weak optical-thread status without changing modality.
- `sar_morphology_factor`: supplies posthoc vehicle-scale vocabulary such as ridge, shell contour, hotspot, weak boundary, or background risk.
- `mechanism_explanation_factor`: links compatible optical state and SAR morphology into a conservative mechanism outcome.

GM_RM011_WGV14T001 is the strongest positive instance because optical state, optical continuity, SAR morphology, and mechanism factors all support a posthoc explanation. GM_RM011_WGV14T004 and WGV14T005 are useful but weaker because mapping, sparse evidence, and competition remain unresolved.

### 3. Which factors prevent unsafe upgrading of weak or blocked windows?

The blockers are:

- `evidence_permission_factor`: blocks SAR consumption, runtime use, and identity claims for all nine rows.
- `boundary_preservation_factor`: keeps GM_RM011 M005 and M016 as preserved different-vehicle boundaries.
- `competitor_risk_factor`: keeps same-color vehicles, multi-target signals, background risk, and long bridge risks visible.
- `geometry_feasibility_factor`: prevents feasible domains or offset bands from becoming selected locations.
- `contradiction_or_blocking_factor`: keeps V004 and boundary conflicts as blocked outcomes.

These factors prevent WGV2.2 from converting posthoc overlap, optical stability, or weak thread support into a stronger same-vehicle relation.

### 4. Which missing factors prevent stronger SAR consumption?

The blocking missing factors are:

- `missing_gm011_azimuth_source`: GM_RM011 lacks a runtime-safe direct azimuth or fan-polar source.
- `missing_precise_temporal_alignment`: optical windows are not precisely aligned to SAR frame-local evidence.
- `missing_sar_temporal_drift_chain`: selected windows lack SAR-internal non-jump drift chains.
- `missing_later_window_gt_local_exemplar`: GM_RM011 later windows lack enough traceable local SAR examples.
- `missing_boundary_sar_evidence`: M005 and M016 need boundary-specific SAR evidence if later protocols inspect them.
- `missing_non_vehicle_rejection`: vehicle-like SAR structure is not closed against background or static reflector alternatives.
- `missing_competitor_separation_evidence`: same-color, multi-target, and bridge competitors remain unresolved.

These missing factors block stronger SAR consumption. They do not block posthoc mechanism explanation.

### 5. Why is GM_RM011 useful for mechanism construction but still not SAR-ready?

GM_RM011 is useful because it contains accepted optical windows, near-field truncation, visible-unboxed gaps, primary-box repair context, same-color competitor boundaries, and GT-local SAR morphology vocabulary. These make it a strong mechanism-construction scene.

It is still not SAR-ready because the key consumption factors are missing: a runtime-safe GM_RM011 azimuth source, precise optical-to-SAR temporal alignment, SAR-internal drift chains, later-window local SAR exemplars, and boundary-specific SAR evidence for M005 and M016. The WGV2.1 permission gates remain active.

### 6. Why is GM_RM017 useful for conservativeness validation but not strong mapping?

GM_RM017 is useful because it tests whether the graph resists unsafe upgrades when posthoc overlap exists. WGV14T001-WGV14T003 remain weak because optical status is weak, offset bands are ambiguous, context edges and competitors remain unresolved, and non-vehicle rejection is incomplete.

V004 confirms the blocked path: posthoc overlap and SAR morphology vocabulary do not override identity risk or permission blocking.

### 7. Did any weak or blocked item get upgraded?

No. The WGV2.1 consistency audit has `weak_or_blocked_item_upgraded=no` for all nine windows, and WGV2.2 preserves that result. GM_RM017_WGV14T001-WGV14T003 remain weak or ambiguous, and GM_RM017_WGV14V004 remains blocked.

### 8. Did any boundary get relaxed?

No. GM_RM011 M005 and M016 remain `boundary_preserved_and_blocked`. WGV2.2 records missing boundary SAR evidence as a reason to stay conservative, not as a reason to relax either boundary.

### 9. Does this produce final boxes, revised GT, SAR-ready annotation, selector, identity truth, or runtime prediction?

No. WGV2.2 produces no final boxes, no GT boxes, no revised GT, no revised annotations, no SAR-ready annotation, no selector/ranking output, no runtime prediction artifact, no score optimization, no weighted fusion, and no identity truth.

### 10. What is the minimal next repair path?

The minimal next repair path is factor-targeted:

1. Recover or construct a GM_RM011 runtime-safe azimuth feasible source.
2. Add SAR temporal drift chains for selected GM_RM011 windows.
3. Add non-vehicle rejection evidence around SAR-local structures.
4. Keep M005 and M016 boundary checks separate.

This path repairs missing factors. It does not expand the table into candidate selection or annotation generation.

## Conclusion

WGV2.2 shows that the factor graph can express mechanism support and mechanism blocking without forcing one-to-one optical-SAR mapping. GM_RM011 is mostly ready for posthoc mechanism explanation but not SAR consumption. GM_RM017 validates conservativeness because weak and blocked items remain weak or blocked despite posthoc overlap.
