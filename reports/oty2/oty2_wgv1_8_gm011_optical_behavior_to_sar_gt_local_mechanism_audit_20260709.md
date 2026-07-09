# OTY2 WGV1.8 GM_RM011 optical-behavior to SAR-GT-local mechanism audit

Date: 2026-07-09

## Scope

WGV1.8 is an OTY2 posthoc mechanism-diagnosis audit for GM_RM011. It observes optical behavior, connects those observations to WGV1.4b optical threads and preserved boundaries, then uses existing SAR GT and GT-local morphology features as reference anchors for physical explanation.

This audit does not create labels, localization outputs, or runtime rules. SAR GT is used only as a posthoc local reference anchor. Optical evidence does not prove SAR identity, and SAR-local observations do not upgrade WGV1.4b optical classes.

## Required Reading

Read before generating this report:

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md`
- `docs/oty2_gt_support_failure_concept_correction_archive.md`
- `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
- `docs/oty2_gt_local_energy_field_atlas_correction_archive.md`
- `docs/oty2_sar_physical_factor_modeling_idea_archive.md`
- `reports/oty2/oty2_yolo26l_wgv1_4b_long_window_identity_stability_stress_test_20260709.md`
- `reports/oty2/oty2_wgv1_5c_prior_sar_evidence_inheritance_and_alignment_20260709.md`
- `reports/oty2/oty2_wgv1_6_small_window_optical_sar_dual_evidence_closure_audit_20260709.md`
- `reports/oty2/oty2_wgv1_7_azimuth_constrained_optical_sar_temporal_alignment_audit_20260709.md`

## Evidence Read

Optical PNG evidence was actually inspected from existing WGV1.3/WGV1.4b diagnostic PNGs via temporary contact sheets outside the repository:

- `gm011_early_m005`: frames 8, 10, 13, 18, 25, 31, 35.
- `gm011_mid_135_166`: frames 135, 136, 137, 151, 154, 160, 164, 166.
- `gm011_long_m016`: frames 231, 233, 242, 250, 259, 270, 279, 288, 289, 292.

Existing SAR GT-local exemplar PNGs were also inspected for GM_RM011 early frames: `GTREF_GM_RM011_s5_10`, `GTREF_GM_RM011_s6_12`, `GTREF_GM_RM011_s10_18`, and the broader `GTREF_GM_RM011_s0_336` reference panel. For later GM_RM011 windows, direct GT-local exemplar PNGs were not available in the current source set, so WGV1.8 used prior CSV/report features and records that limitation.

## Outputs

- `reports/oty2/samples/oty2_wgv1_8_gm011_optical_behavior_observation_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_8_gm011_optical_to_sar_gt_reference_candidates_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_8_gm011_sar_gt_local_mechanism_reading_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_8_gm011_optical_sar_physical_mechanism_links_20260709.csv`

## Window Summary

| Window | WGV item | Optical behavior tags | Optical class | Mechanism support |
| --- | --- | --- | --- | --- |
| `WGV18W001` | `GM_RM011_WGV14T001` | `stable_visible_vehicle;near_field_truncation;partial_vehicle;primary_box_selection_issue;edge_contact` | `optical_identity_constraint` | `physically_interpretable_posthoc_support` |
| `WGV18W002` | `GM_RM011_WGV14T002` | `stable_visible_vehicle;subject_transition;boundary_replacement;context_only_relation` | `optical_search_hint_only` | `weak_posthoc_support` |
| `WGV18W003` | `GM_RM011_WGV14T003-WGV14T004` | `multi_vehicle_competition;occlusion;subject_transition;stable_visible_vehicle;edge_contact;partial_vehicle` | `mixed_search_hint_and_optical_identity_constraint` | `ambiguous_or_competitor_risk` |
| `WGV18W004` | `GM_RM011_WGV14T005-WGV14T006` | `stable_visible_vehicle;near_field_truncation;partial_vehicle;visible_unboxed_vehicle_gap;same_color_competitor;multi_vehicle_competition;boundary_replacement` | `optical_search_hint_only` | `ambiguous_or_competitor_risk` |
| `WGV18W005` | `GM_RM011_WGV12M005` | `boundary_replacement;context_only_relation;same_color_competitor;blocked_identity_risk` | `boundary_preserved` | `boundary_only` |
| `WGV18W006` | `GM_RM011_WGV12M016` | `boundary_replacement;same_color_competitor;multi_vehicle_competition;context_only_relation;blocked_identity_risk` | `boundary_preserved` | `blocked` |

Mapping status counts:

- `blocked_missing_traceable_sar_reference`: 1
- `boundary_reference_only`: 1
- `prior_report_traceable`: 4

Physical mechanism claim counts:

- `boundary_preserved_until_mapping_and_sar_boundary_support_exist`: 2
- `long_window_search_hint_not_identity_constraint`: 1
- `optical_occlusion_or_subject_transition_requires_boundary_preservation`: 2
- `optical_truncation_may_shift_or_expand_sar_support`: 1


## Direct Answers

### 1. What are the main optical behavior types in GM_RM011?

The main optical behavior types are near-field truncation, edge contact, partial vehicle visibility, subject transition, same-color competitor competition, visible-unboxed vehicle gaps, and preserved replacement boundaries. The most important risk is that the same white vehicle color appears on different vehicles near M005 and M016.

### 2. Which WGV1.4b optical threads or edges correspond to those behaviors?

`GM_RM011_WGV14T001` represents the early stable near-field/truncated white car. `GM_RM011_WGV14T002` is a separate short white-car segment after M005. `GM_RM011_WGV14T003-WGV14T004` covers the mid-scene competition and later right-edge white-car stability. `GM_RM011_WGV14T005-WGV14T006` covers the long bridge-side search hint plus the M016 handoff to the left white SUV. `GM_RM011_WGV12M005` and `GM_RM011_WGV12M016` remain the key preserved different-vehicle boundaries.

### 3. What SAR GT-local evidence is available as posthoc reference?

GM_RM011 has 201 rows in the SAR GT sample accounting and 201 rows in the GT-anchored energy morphology audit. The WGV1.5C ledger records scene-level GM_RM011 evidence including vehicle-like scatter, component-level risks, and three GT-local energy-field rows for early frames 5, 6, and 10. The sample accounting also provides review-linked SAR candidate ranges for some optical windows, but current OTY object-stream mapping is still missing.

### 4. What vehicle-scale SAR morphology is physically interpretable?

Early GM_RM011 GT-local exemplars show ridge-like energy bands, weak opposite-side returns, endpoint/hotspot candidates, and vehicle-scale shell-contour candidates inside the SAR GT crop. Across the broader GM_RM011 morphology CSV, common patterns include enclosed shell, discontinuous edges, corner hotspot, side ridge, and weak boundary. These are physically interpretable as SAR vehicle morphology vocabulary, not as automatic localization output.

### 5. Where do optical truncation, occlusion, visible-unboxed gaps, same-color competitors, or preserved boundaries explain SAR support failures or ambiguity?

Near-field truncation in T001 can expand or shift expected SAR support and makes GT quality review important. The 135-166 region mixes occlusion, subject transition, and edge contact, so SAR multi-structure or corner hotspots must be read as ambiguous until optical subject boundaries are preserved. The 231-292 long window contains visible-unboxed gaps and a same-color SUV competitor, so sparse SAR support can only support existence or structure vocabulary. M005 and M016 explain why SAR-local evidence must not bridge same-color vehicles without independent boundary evidence.

### 6. Which mechanisms are supported only posthoc and cannot become runtime priors?

All SAR GT-local ridge, hotspot, shell-contour, and GT-quality observations in WGV1.8 are posthoc only. They can guide mechanism vocabulary and later SAR-internal evidence design, but they cannot be copied into runtime optical priors, thresholds, labels, or object-stream identity claims.

### 7. What remains missing before GM_RM011 can contribute to bounded SAR consumption?

Missing items are: recovered or rebuilt GM_RM011 optical object stream, explicit optical-to-SAR thread mapping, boundary-specific SAR-internal evidence for M005 and M016, competitor separation for same-color vehicles, and a later consumption protocol that separates SAR evidence from optical hints.

### 8. Does this produce annotation-producing or runtime-consuming artifacts?

No. WGV1.8 produces no final-box output, no GT-box output, no revised-GT output, no SAR-ready annotation, no selector or ranking output, no runtime-prediction output, and no identity-confirmation claim.

## Conclusion

GM_RM011 optical behavior can build a physical explanation vocabulary for SAR GT-local structures. GM_RM011 is not useless and should not remain permanently blocked. However, GM_RM011 still cannot become SAR-ready until mapping, boundary, and SAR-internal evidence protocols are explicitly closed. SAR GT is used only as posthoc reference for mechanism explanation.
