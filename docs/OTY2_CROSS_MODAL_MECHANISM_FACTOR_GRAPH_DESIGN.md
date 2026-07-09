# OTY2 WGV2.0 Cross-Modal Mechanism Factor Graph Design

Date: 2026-07-09

## Status

WGV2.0 is a design-only mechanism document. It defines how existing WGV1.x optical and SAR-posthoc findings can be represented as a cross-modal mechanism relation graph. It does not instantiate the graph and does not run inference or optimization.

Required input stack read for this design:

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
- `docs/oty2_gt_support_failure_concept_correction_archive.md`
- `docs/oty2_gt_local_energy_field_atlas_correction_archive.md`
- `docs/oty2_sar_physical_factor_modeling_idea_archive.md`
- `reports/oty2/oty2_wgv1_8_gm011_optical_behavior_to_sar_gt_local_mechanism_audit_20260709.md`
- `reports/oty2/oty2_wgv1_6_small_window_optical_sar_dual_evidence_closure_audit_20260709.md`
- `reports/oty2/oty2_wgv1_7_azimuth_constrained_optical_sar_temporal_alignment_audit_20260709.md`

## Why WGV2.0 Is Needed

WGV1.x produced optical thread stability, SAR posthoc evidence inheritance, dual-evidence small-window closure, azimuth-constrained alignment audit, and a GM_RM011 optical-behavior-to-SAR-local mechanism reading.

Those outputs show that the remaining problem should not be represented as a one-to-one optical-SAR mapping. Accepted optical windows, weak optical windows, preserved boundaries, posthoc SAR morphology, temporal tubes, azimuth feasibility, and competitor risk are different evidence layers with different permissions. Collapsing them into a single correspondence would hide the exact failures that WGV1.x exposed.

WGV2.0 therefore represents the state as a cross-modal mechanism relation graph:

- optical observations and fragments describe optical continuity hypotheses;
- SAR GT-local and SAR morphology observations describe posthoc SAR-side structure vocabulary;
- geometry and temporal nodes describe feasible domains rather than exact identity links;
- boundary and competition nodes prevent unsafe bridging;
- evidence permission nodes determine what each relation is allowed to mean;
- mechanism relation nodes record the conservative outcome without becoming a label or prediction.

## Design Boundary

This design remains pre-SAR-consumption and posthoc-mechanism only.

Explicit non-goals:

- no final boxes
- no GT boxes
- no revised GT
- no revised annotations
- no identity truth
- no selector/ranking
- no runtime prediction
- no SAR-ready annotation
- no weighted fusion
- no score optimization
- no one-to-one strong mapping requirement
- no final object identity instantiation
- no tracked media outputs
- no additions under `outputs/`

The graph is a vocabulary and permission design. It is not an annotation-producing system.

## Graph Levels

WGV2.0 uses six levels.

| Level | Role | Boundary |
| --- | --- | --- |
| Optical evidence | Optical observations, fragments, threads, and behavior states | Can constrain review or search, but cannot prove SAR identity |
| SAR posthoc evidence | SAR GT-local references, morphology, and temporal drift observations | Can support posthoc mechanism explanation, but cannot produce runtime prior logic |
| Geometry feasible domain | Temporal tubes, azimuth/fan-polar feasibility, range/vehicle-size shell concepts | Feasible domain only, not a selected SAR box |
| Boundary and competition | Preserved different-vehicle boundaries, context-only edges, competitor or multi-target signals | Blocks unsafe merging and relation upgrading |
| Evidence permission | Provenance and allowed-use gates | Prevents leakage from posthoc evidence into runtime claims |
| Mechanism relation | Conservative relation outcomes | Explains support, ambiguity, or blockage without creating annotations |

## Node Types

The companion CSV `reports/oty2/samples/oty2_wgv2_0_factor_graph_node_schema_20260709.csv` defines the node schema. The required node types are:

- `optical_observation_node`
- `optical_fragment_node`
- `optical_thread_node`
- `optical_behavior_state_node`
- `sar_gt_local_reference_node`
- `sar_morphology_node`
- `sar_temporal_drift_node`
- `geometry_feasible_domain_node`
- `boundary_competition_node`
- `evidence_permission_node`
- `mechanism_relation_node`

Interpretation:

- An `optical_observation_node` is a frame-local optical detection or inspected visual observation.
- An `optical_fragment_node` is a short optical continuity hypothesis.
- An `optical_thread_node` is a WGV1.4b accepted, weak, search-hint, context, or blocked thread unit.
- An `optical_behavior_state_node` records visible states such as truncation, edge contact, occlusion-like gaps, primary-box repair, or multi-box competition.
- A `sar_gt_local_reference_node` is a posthoc anchor for reading SAR morphology. It is not a runtime target and not a label proposal.
- A `sar_morphology_node` records vehicle-scale SAR structure vocabulary such as ridge, endpoint hotspot, weak opposite-side return, shell contour, or background-risk evidence.
- A `sar_temporal_drift_node` records SAR-side non-jump or ambiguous drift evidence.
- A `geometry_feasible_domain_node` records temporal, azimuth, range, and vehicle-size feasibility.
- A `boundary_competition_node` records preserved boundaries, context-only relations, and competitor risk.
- An `evidence_permission_node` records allowed and forbidden uses.
- A `mechanism_relation_node` records the final conservative relation outcome for a designed graph unit.

## Factor Types

The companion CSV `reports/oty2/samples/oty2_wgv2_0_factor_graph_factor_schema_20260709.csv` defines the factor schema. The required factor types are:

- `optical_state_factor`
- `optical_continuity_factor`
- `sar_morphology_factor`
- `sar_temporal_drift_factor`
- `geometry_feasibility_factor`
- `boundary_preservation_factor`
- `competitor_risk_factor`
- `evidence_permission_factor`
- `mechanism_explanation_factor`
- `contradiction_or_blocking_factor`

Factor interpretation:

- Optical factors explain whether optical continuity is strong, weak, ambiguous, or blocked.
- SAR factors explain whether GT-local or SAR-internal observations look vehicle-like, background-like, drifting, or insufficient.
- Geometry factors restrict admissible relation hypotheses but do not select a final location.
- Boundary and competitor factors prevent context-only or different-vehicle edges from becoming same-vehicle relations.
- Permission factors determine whether evidence can be used for posthoc explanation, review prioritization, boundary preservation, or no consumption.
- Mechanism and contradiction factors record the conservative relation outcome.

## Relation Outcomes

The companion CSV `reports/oty2/samples/oty2_wgv2_0_factor_graph_relation_outcome_schema_20260709.csv` defines relation outcomes. Required outcomes are:

- `supports_vehicle_existence`
- `supports_boundary`
- `explains_support_shift`
- `explains_detection_dropout`
- `explains_visible_unboxed_gap`
- `indicates_competition`
- `indicates_background_risk`
- `weak_posthoc_support_only`
- `insufficient_evidence`
- `contradiction`
- `blocked_by_permission`
- `blocked_by_boundary`
- `blocked_by_identity_risk`

These outcomes describe mechanism status only. They do not create final labels, object identities, annotations, or runtime prediction artifacts.

## Evidence Permission Rules

WGV2.0 uses the following hard permission rules:

- SAR GT-local morphology can support posthoc mechanism explanation.
- SAR GT-local morphology cannot produce runtime prior logic.
- Optical strong thread can constrain review/search.
- Optical strong thread cannot prove SAR identity.
- SAR posthoc overlap cannot upgrade weak optical identity.
- Preserved boundaries cannot be relaxed without explicit independent boundary evidence and a later protocol.
- Blocked identity-risk items remain blocked.
- Mechanism support is not final annotation.
- Mechanism explanation is not identity truth.

Operational consequences:

- `GM_RM011_WGV14T001` and `GM_RM011_WGV14T004` can be strong optical constraints for later review/search but remain blocked for SAR consumption without independent SAR-internal evidence and mapping closure.
- `GM_RM011_WGV14T005` can prioritize review/search but remains conservative because of the M016 same-color competitor boundary.
- `GM_RM011 M005` and `GM_RM011 M016` remain preserved boundaries. The graph may explain why they block bridging, but it may not bridge them.
- `GM_RM017 WGV14T001-WGV14T003` remain weak/search-hint optical threads even where posthoc overlap exists.
- `GM_RM017 WGV14V004` remains blocked by identity risk.

## Scene Roles

The companion CSV `reports/oty2/samples/oty2_wgv2_0_scene_role_plan_20260709.csv` defines scene roles.

| Scene | Role | Reason |
| --- | --- | --- |
| `GM_RM011` | mechanism-construction scene | Rich optical behavior, near-field truncation, edge contact, occlusion or subject transition, visible-unboxed gap, same-color competitor risk, and preserved boundaries |
| `GM_RM017` | conservativeness-validation scene | Azimuth sources and posthoc overlap exist, but optical threads remain weak or ambiguous and must not be upgraded |
| `GM_RM019` | future generalization-check scene | Later test whether the mechanism vocabulary transfers beyond GM_RM011 and GM_RM017 |

## WGV2.1 Instantiation Plan

WGV2.1 may later instantiate a small set of graph units, but WGV2.0 does not implement that step.

Candidate windows for the later WGV2.1 design-only instantiation:

- `GM_RM011_WGV14T001`
- `GM_RM011_WGV14T004`
- `GM_RM011_WGV14T005`
- `GM_RM011 M005`
- `GM_RM011 M016`
- `GM_RM017 WGV14T001`
- `GM_RM017 WGV14T002`
- `GM_RM017 WGV14T003`
- `GM_RM017 WGV14V004`

WGV2.1 should record nodes, factors, permissions, and relation outcomes for those units only after a separate prompt explicitly authorizes it. Even then, graph instantiation must remain distinct from SAR-ready annotation unless a later SAR consumption protocol is designed and independently validated.

## Schema Files

WGV2.0 adds four schema files:

- `reports/oty2/samples/oty2_wgv2_0_factor_graph_node_schema_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_0_factor_graph_factor_schema_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_0_factor_graph_relation_outcome_schema_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_0_scene_role_plan_20260709.csv`

These are schemas and role plans only. They are not graph instances and not evidence units.

## Validation Boundary

A valid WGV2.0 delivery should pass:

- `git diff --check`
- `git diff --cached --check` if staging exists
- a forbidden-artifact scan showing no `outputs/` additions, no tracked image/video additions, no affirmative SAR-ready flag, no annotation-producing artifacts, no selector/ranking artifacts, no runtime prediction artifacts, and no identity-truth claim
- `git status --short`

WGV2.0 should remain uncommitted until a later explicit commit instruction.
