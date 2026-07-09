# OTY2 WGV1.6 small-window optical-SAR dual-evidence closure audit

Date: 2026-07-09

## Scope

WGV1.6 starts a small-window optical-SAR dual-evidence closure audit. It asks whether selected high-value optical windows can be explained jointly by WGV1.4b optical thread evidence, WGV1.5A consumption rules, WGV1.5C inherited prior SAR evidence, and posthoc SAR morphology or temporal evidence.

This is posthoc mechanism closure, not SAR-ready annotation. Dual evidence consistency is not identity truth. Optical evidence and SAR evidence remain separate provenance layers. Inherited SAR evidence is posthoc-only unless a later explicit protocol changes its use. Any mapping-unresolved case remains blocked from SAR-ready consumption.

No final annotation, GT revision, selector/ranking, or runtime prediction artifact was generated. No tracked media files or `outputs/` files were added.

## Inputs

Required reports and contracts were read:

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md`
- `docs/oty2_gt_support_failure_concept_correction_archive.md`
- `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
- `docs/oty2_gt_local_energy_field_atlas_correction_archive.md`
- `reports/oty2/oty2_yolo26l_wgv1_4b_long_window_identity_stability_stress_test_20260709.md`
- `reports/oty2/oty2_wgv1_5_pre_sar_consumption_and_sar_internal_evidence_protocol_20260709.md`
- `reports/oty2/oty2_wgv1_5c_prior_sar_evidence_inheritance_and_alignment_20260709.md`
- `reports/oty2/oty2_wgv1_5c_closeout_review_and_wgv1_6_readiness_20260709.md`

CSV inputs:

- `reports/oty2/samples/oty2_yolo26l_wgv1_4b_thread_stability_summary_20260709.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_4b_edge_boundary_stress_summary_20260709.csv`
- `reports/oty2/samples/oty2_yolo26l_wgv1_5a_optical_to_sar_consumption_contract_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5c_sar_prior_evidence_ledger_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5c_optical_thread_sar_evidence_alignment_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5c_sar_evidence_source_provenance_20260709.csv`

## Outputs

- `reports/oty2/samples/oty2_wgv1_6_dual_evidence_window_summary_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_6_dual_evidence_reasoning_units_20260709.csv`

## Window decisions

| Window | Item | WGV1.4b class | Mapping status | WGV1.6 decision |
| --- | --- | --- | --- | --- |
| `WGV16W001` | `GM_RM011_WGV14T001` | `optical_identity_constraint` | `scene_level_prior_available_but_no_thread_frame_mapping` | `optical_strong_sar_posthoc_support_available_but_mapping_unresolved` |
| `WGV16W002` | `GM_RM011_WGV14T004` | `optical_identity_constraint` | `scene_level_prior_available_but_no_thread_frame_mapping` | `optical_strong_sar_posthoc_support_available_but_mapping_unresolved` |
| `WGV16W003` | `GM_RM011_WGV14T005` | `optical_search_hint_only` | `scene_level_prior_available_but_no_thread_frame_mapping` | `optical_search_hint_sar_support_ambiguous` |
| `WGV16W004` | `GM_RM011_WGV12M005` | `boundary_preserved` | `scene_level_prior_available_but_no_thread_frame_mapping` | `boundary_preserved_sar_mapping_blocked` |
| `WGV16W005` | `GM_RM011_WGV12M016` | `boundary_preserved` | `scene_level_prior_available_but_no_thread_frame_mapping` | `boundary_preserved_sar_mapping_blocked` |
| `WGV16W006` | `GM_RM017_WGV14T001` | `optical_search_hint_only` | `traceable_prior_optical_frame_overlap_posthoc_only_no_wgv15_mapping_resolution` | `weak_optical_remains_weak` |
| `WGV16W007` | `GM_RM017_WGV14T002` | `optical_search_hint_only` | `traceable_prior_optical_frame_overlap_posthoc_only_no_wgv15_mapping_resolution` | `weak_optical_remains_weak` |
| `WGV16W008` | `GM_RM017_WGV14T003` | `optical_search_hint_only` | `traceable_prior_optical_frame_overlap_posthoc_only_no_wgv15_mapping_resolution` | `weak_optical_remains_weak` |
| `WGV16W009` | `GM_RM017_WGV14V004` | `blocked_for_sar_consumption` | `posthoc_overlap_checked_but_consumption_blocked` | `blocked_identity_risk_preserved` |

Decision counts:

- `blocked_identity_risk_preserved`: 1
- `boundary_preserved_sar_mapping_blocked`: 2
- `optical_search_hint_sar_support_ambiguous`: 1
- `optical_strong_sar_posthoc_support_available_but_mapping_unresolved`: 2
- `weak_optical_remains_weak`: 3

SAR evidence category coverage across selected windows:

- `background_or_static_reflector_risk`: 5
- `competitor_or_multi_target_signal`: 4
- `temporal_continuity`: 4
- `unknown_or_insufficient_evidence`: 4
- `vehicle_like_scatter`: 9

## Interpretation by window family

### GM_RM011 positive optical candidates

`GM_RM011_WGV14T001` and `GM_RM011_WGV14T004` are the strongest positive WGV1.6 candidates because WGV1.4b treats them as accepted `optical_identity_constraint` windows and WGV1.5C records scene-level GM_RM011 SAR morphology evidence. They cannot become SAR-ready or SAR identity-confirming because WGV1.5C has no thread-level optical-to-SAR frame mapping for GM_RM011.

Decision: `optical_strong_sar_posthoc_support_available_but_mapping_unresolved`.

### GM_RM011 long search-hint stress case

`GM_RM011_WGV14T005` remains a long optical search hint. It has scene-level SAR morphology evidence, but M016 and the 286-292 competitor boundary prevent identity consumption. The only safe use is pre-SAR review and search prioritization.

Decision: `optical_search_hint_sar_support_ambiguous`.

### GM_RM011 boundary checks

`GM_RM011_WGV12M005` and `GM_RM011_WGV12M016` remain boundary-protection checks. The SAR prior is scene-level only, and mapping is unresolved, so neither boundary can be bridged.

Decision: `boundary_preserved_sar_mapping_blocked`.

### GM_RM017 weak optical threads

`GM_RM017_WGV14T001`, `GM_RM017_WGV14T002`, and `GM_RM017_WGV14T003` have posthoc prior SAR overlap rows, but the overlap evidence is mixed with temporal instability, ambiguous SAR structure, competitor risk, and review-required states. WGV1.6 does not upgrade these threads.

Decision: `weak_optical_remains_weak`.

### GM_RM017 blocked identity-risk item

`GM_RM017_WGV14V004` stays blocked. Inherited SAR overlap evidence cannot override a WGV1.5A `blocked_for_sar_consumption` row.

Decision: `blocked_identity_risk_preserved`.

## Boundary and provenance conclusions

- Optical evidence does not prove SAR identity.
- SAR posthoc evidence can explain mechanism but cannot create runtime annotation permission.
- Preserved optical boundaries remain non-bridged unless a later explicit protocol documents independent SAR boundary evidence.
- Weak optical threads are not upgraded by inherited SAR overlap evidence alone.
- Blocked identity-risk rows remain blocked.
- Mapping unresolved means SAR-ready remains no / blocked.

## Next allowed use

The safe next step is a later WGV1.6 continuation that manually inspects the same small windows with an explicit mapping protocol and independent SAR-internal evidence units. It should remain a posthoc mechanism audit unless a separate SAR consumption protocol is written.
