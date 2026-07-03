# OTY2 Support-Wide Energy Structure And Temporal Morphology Plan

Updated: 20260703

This plan implements a bounded OTY2 posthoc mechanism diagnostic. It starts from the fixed `20260703_174930` support overlay QA and the `20260703_163000` GT-anchored support coverage audit, then expands the unit of inspection from GT-local/top-k peaks to the whole reconstructed support region.

## Inputs

- `reports/oty2/oty2_support_region_peak_competition_audit_20260703_091849.csv`
- `reports/oty2/oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- `reports/oty2/oty2_optical_support_coverage_hypothesis_audit_20260703_163000.csv`
- `reports/oty2/oty2_gt_box_energy_distribution_audit_20260703_163000.csv`
- `reports/oty2/oty2_complete_optical_high_confidence_coverage_pool_20260703_163000.csv`
- `reports/oty2/oty2_truncated_occluded_temporal_compensation_pool_20260703_163000.csv`
- `reports/oty2/oty2_chinese_review_card_index_20260703_174930.csv`
- `reports/oty2/oty2_overlay_case_geometry_debug_20260703_174930.csv`

The paired diagnostic rows are the `215` `state_conditioned_range_band` rows in the peak-competition audit. Other pools remain reference-only or special-pool evidence as defined in the correction archive.

## Diagnostic A: Support-Wide Energy Atoms And Components

For each paired row, reconstruct the support mask from the existing sector/range fields and extract SAR image observations inside the whole support:

- high-energy atoms from a fixed public support-internal `p97` rule
- local maxima with a fixed minimum separation
- connected bright components from a fixed public support-internal `p85` rule
- GT-inside atoms and outside-GT-inside-support atoms as posthoc validation only
- dominant component area, range extent, azimuth extent, and coarse shape type

The output must not include a final box, selected component, ranking, or tuned threshold.

## Diagnostic B: Vehicle Shell / Boundary Morphology Proxy

The script emits proxy rows for:

- `dominant_side_ridge_proxy`
- `facing_side_hotspot_proxy`
- `endpoint_or_corner_reflector_proxy`
- `far_side_weak_return_proxy`
- `discontinuous_aligned_edges_proxy`
- `strip_plus_corner_composition_proxy`
- `multi_peak_enclosed_shell_proxy`
- `block_like_vehicle_body_proxy`
- `range_spread_with_core_proxy`
- `support_wide_vehicle_shell_proxy`

These proxies are descriptive posthoc mechanism diagnostics. They are not selector features and must not be promoted to runtime rules.

## Diagnostic C: Support Failure Taxonomy

The support failure taxonomy combines support coverage, support-wide morphology, GT relation validation, and optical state. The taxonomy distinguishes:

- azimuth aligned but range misaligned
- support too narrow or too broad
- support above/below the main energy strip
- range compression too strong
- optical truncation or near-field induced shift
- missing state or temporal compensation
- support reconstruction uncertainty
- support ok but not exclusive
- support contains neighbor/background structure
- reference-only no-support cases

The taxonomy must explicitly keep support quality separate from association success and SAR morphology strength.

## Diagnostic D: Temporal Morphology Drift Probe

The temporal probe reuses the current support region and checks `3`, `5`, and `10` frame windows where images are available. It records:

- dominant structure persistence
- hotspot drift and drift direction
- component centroid drift
- ridge/strip persistence
- shell structure persistence
- gradual-change versus jump behavior
- vehicle-like temporal tube hypothesis
- background-stable risk
- optical-tracklet compatibility as posthoc review guidance only

Dropout/no-match rows remain outside clean paired morphology and are not added to this paired diagnostic.

## Atlas

If images are available, generate a Chinese review atlas under `reports/oty2/visual_exemplars/`. Each panel should show current support-wide structure and multi-frame context. The panel text must say that the figure checks whether support-wide atoms, strips, and blocks can form vehicle structure and whether that structure drifts continuously over time. It may record morphology strength, support failure type, temporal compensation need, background-stable risk, and association review need. It must not record identity truth, final annotation, or selector success.

## Outputs

- `reports/oty2/oty2_support_wide_energy_atoms_and_components_<timestamp>.csv`
- `reports/oty2/oty2_support_wide_vehicle_shell_proxy_<timestamp>.csv`
- `reports/oty2/oty2_support_failure_taxonomy_<timestamp>.csv`
- `reports/oty2/oty2_temporal_morphology_drift_probe_<timestamp>.csv`
- `reports/oty2/oty2_multiframe_structure_continuity_cases_<timestamp>.csv`
- `reports/oty2/oty2_panel_review_correction_notes_<timestamp>.csv`
- `reports/oty2/oty2_support_wide_energy_structure_and_temporal_morphology_report_<timestamp>.md`
- `reports/oty2/oty2_support_wide_energy_structure_and_temporal_morphology_summary_<timestamp>.json`
- `reports/oty2/visual_exemplars/oty2_support_wide_energy_structure_temporal_atlas_cn_<timestamp>.html`
- `D:\profile\research\workspace\logs\oty2_support_wide_energy_structure_and_temporal_morphology_<timestamp>.log`

## Boundary Flags

- `posthoc_sar_gt_used=true`
- `posthoc_sar_image_content_used=true`
- `support_wide_energy_structure_diagnostic_entered=true`
- `vehicle_shell_proxy_entered=true`
- `support_failure_taxonomy_entered=true`
- `temporal_morphology_drift_probe_entered=true`
- `gt_or_sar_image_used_for_runtime_prior_construction=false`
- `runtime_prior_construction_used_gt=false`
- `annotation_proposal_entered=false`
- `final_candidate_box_output=false`
- `selected_component_output=false`
- `selector_or_ranking_used=false`
- `training_or_threshold_tuning_entered=false`
- `best_weight_selected=false`
- `identity_truth_claimed=false`
- `detection_dropout_rows_mixed_into_clean_paired=false`
- `gm011_missing_object_stream_rows_mixed_into_correspondence=false`
- `sar_only_rows_mixed_into_optical_sar_correspondence=false`
- `matlab_zip_or_any_zip_committed=false`
