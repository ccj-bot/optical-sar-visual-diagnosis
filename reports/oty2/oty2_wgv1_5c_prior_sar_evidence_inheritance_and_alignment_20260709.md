# OTY2 WGV1.5C prior SAR evidence inheritance and optical-thread alignment audit

Date: 2026-07-09

## Scope

WGV1.5C inherits prior SAR-side mechanism evidence and checks whether it can be aligned to WGV1.5A optical consumption rows. It does not run SAR, does not create SAR-ready annotations, and does not generate any final box, GT box, revised annotation, selector/ranking output, runtime prediction artifact, or tracked image/video output.

Hard boundary statements:

1. SAR evidence is not unknown from scratch; it has been explored in earlier posthoc mechanism diagnostics.
2. WGV1.5C inherits prior SAR evidence as posthoc mechanism evidence only.
3. No inherited SAR evidence is allowed to create SAR-ready annotations.
4. Optical WGV1.4b threads remain pre-SAR constraints or search hints.
5. SAR identity support still requires independent SAR evidence plus an explicit mapping/alignment protocol.
6. If mapping is unresolved, alignment remains conservative.

Additional guardrails:

- Optical evidence is not SAR evidence.
- Long-window optical stability does not imply a SAR-ready annotation.
- Posthoc SAR GT and SAR image observations are not runtime prior construction.
- Boundary/context rows must not be implicitly treated as same-vehicle continuity.

## Required Reading Used

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md`
- `docs/oty2_gt_support_failure_concept_correction_archive.md`
- `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
- `docs/oty2_gt_local_energy_field_atlas_correction_archive.md`
- `reports/oty2/oty2_wgv1_5_pre_sar_consumption_and_sar_internal_evidence_protocol_20260709.md`

## Inputs

Optical contract inputs:

- `reports/oty2/samples/oty2_yolo26l_wgv1_5a_optical_to_sar_consumption_contract_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5b_sar_internal_evidence_schema_20260709.csv`

Prior SAR evidence sources inherited:

- `reports/oty2/oty2_gt_anchored_energy_morphology_20260703_222135.csv`
- `reports/oty2/oty2_atom_part_shell_hierarchy_20260703_222135.csv`
- `reports/oty2/oty2_gt_local_energy_field_features_20260704_145752.csv`
- `reports/oty2/oty2_scatter_cluster_structure_probe_20260703_095159.csv`
- `reports/oty2/oty2_temporal_cluster_association_probe_20260703_095159.csv`
- `reports/oty2/oty2_detection_dropout_sar_posthoc_support_audit_20260702_200455.csv`
- `reports/oty2/oty2_detection_dropout_temporal_support_audit_20260702_200455.csv`
- `reports/oty2/oty2_gt_support_miss_failure_cases_20260703_222135.csv`

The requested filename `reports/oty2/oty2_detection_dropout_temporal_sar_support_audit_20260702_200455.csv` was not present. The actual SAR-side dropout table from the same report family is `reports/oty2/oty2_detection_dropout_sar_posthoc_support_audit_20260702_200455.csv`; this substitution is recorded in the provenance CSV.

## Outputs

- `reports/oty2/samples/oty2_wgv1_5c_sar_prior_evidence_ledger_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5c_optical_thread_sar_evidence_alignment_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5c_sar_evidence_source_provenance_20260709.csv`

## Part A: Prior SAR Evidence Ledger

The ledger contains 60 aggregated inherited evidence units. Rows are source-level or category-level evidence units, not annotations.

Evidence category counts:

- `background_or_static_reflector_risk`: 3
- `boundary_support`: 4
- `competitor_or_multi_target_signal`: 6
- `temporal_continuity`: 16
- `unknown_or_insufficient_evidence`: 12
- `vehicle_like_scatter`: 19

Scene coverage:

- `GM_RM011`: 6
- `GM_RM017`: 29
- `GM_RM019`: 25

Interpretation:

- `vehicle_like_scatter` rows record prior SAR morphology or scatter observations that may help later SAR-only exploration.
- `temporal_continuity` rows record prior SAR temporal tube or dropout continuation observations, including contradictory or weak cases where noted.
- `boundary_support` rows record support construction or miss diagnostics, not boundary proof.
- `competitor_or_multi_target_signal` rows record neighbor, ambiguity, or multi-target risk.
- `background_or_static_reflector_risk`, `imaging_quality_or_motion_artifact`, and `unknown_or_insufficient_evidence` rows remain review or risk evidence.

## Part B: Optical-Thread to Prior-SAR Alignment Audit

The alignment audit contains 50 WGV1.5A optical rows.

WGV1.4b class counts:

- `blocked_for_sar_consumption`: 1
- `boundary_preserved`: 9
- `context_only`: 9
- `optical_identity_constraint`: 7
- `optical_search_hint_only`: 24

WGV1.5A consumption status counts:

- `blocked`: 1
- `pre_sar_only`: 49

Alignment decision counts:

- `blocked_due_to_identity_risk`: 1
- `blocked_due_to_mapping_uncertainty`: 24
- `prior_sar_boundary_relevant`: 14
- `prior_sar_contradiction_or_competitor_risk`: 1
- `prior_sar_support_weak_or_ambiguous`: 10

Mapping status counts:

- `posthoc_overlap_checked_but_consumption_blocked`: 1
- `scene_level_prior_available_but_no_thread_frame_mapping`: 24
- `traceable_prior_optical_frame_overlap_posthoc_only_no_wgv15_mapping_resolution`: 25

Conservative alignment rules applied:

- GM_RM017 prior scatter-cluster rows can be referenced only when inherited rows contain an explicit `optical_frame` overlapping the WGV1.5A optical span.
- Those GM_RM017 overlaps remain posthoc-only. They do not resolve WGV1.5 optical-to-SAR mapping and do not confirm SAR identity.
- GM_RM011 prior SAR morphology is inherited as scene-level evidence only. The inherited SAR rows do not contain optical-frame mapping for WGV1.4b threads, so GM_RM011 thread and boundary consumption remains blocked by mapping uncertainty.
- Boundary and context rows are kept as boundary or context review items; they are not converted into same-vehicle SAR continuity.
- `blocked_for_sar_consumption` rows remain blocked even when prior SAR evidence overlaps a frame span.

## Part C: Provenance

The provenance table contains 15 source rows. It records whether posthoc SAR GT or SAR image content was used, whether a source is runtime-prior-safe, and which uses remain forbidden.

Key provenance outcome:

- The prior SAR evidence is real posthoc evidence, not an empty starting point.
- It is not runtime prior construction.
- It cannot be used to create SAR-ready annotations.
- It cannot be used as final localization or identity proof.

## Current WGV1.5C Conclusion

WGV1.5C closes the inheritance gap without changing the main boundary. Prior SAR evidence exists and should be reused as posthoc mechanism evidence, but the optical-thread alignment remains conservative.

GM_RM017 has some posthoc prior SAR rows with explicit optical-frame overlap. These rows may prioritize independent SAR review, but they are weak or mixed and do not upgrade WGV1.4b weak optical threads.

GM_RM011 has substantial scene-level SAR morphology evidence, including GM_RM011 waiting-object-stream rows, but this evidence is not traceably aligned to WGV1.4b optical thread or edge ids. GM_RM011 M005 and M016 therefore remain preserved optical boundaries, not SAR-confirmed boundaries.

Current SAR state for WGV1.5 remains not consumption-ready. A later WGV1.5B/C continuation must produce independent SAR-internal evidence units and an explicit mapping protocol before any upgrade can be considered.
