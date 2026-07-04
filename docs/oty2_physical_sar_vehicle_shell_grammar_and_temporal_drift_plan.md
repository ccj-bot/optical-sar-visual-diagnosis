# OTY2 Physical SAR Vehicle Shell Grammar And Temporal Drift Plan

Updated: 2026-07-04

This plan continues the OTY2 posthoc mechanism branch after the GT-anchored vehicle-scale morphology audit. The purpose is to express human-visible SAR vehicle evidence as physical structure grammar plus temporal drift mechanism, not as weighted evidence fusion, score proxy optimization, selector preparation, or threshold tuning.

## Inputs

- `reports/oty2/oty2_sar_gt_vehicle_scale_statistics_20260703_222135.csv`
- `reports/oty2/oty2_sar_gt_quality_audit_20260703_222135.csv`
- `reports/oty2/oty2_gt_anchored_energy_morphology_20260703_222135.csv`
- `reports/oty2/oty2_atom_part_shell_hierarchy_20260703_222135.csv`
- `reports/oty2/oty2_gt_support_miss_failure_cases_20260703_222135.csv`
- `reports/oty2/oty2_support_wide_energy_atoms_and_components_20260703_212811.csv`
- `reports/oty2/oty2_support_wide_vehicle_shell_proxy_20260703_212811.csv`
- `reports/oty2/oty2_temporal_morphology_drift_probe_20260703_212811.csv`
- `reports/oty2/oty2_panel_review_correction_notes_20260703_212811.csv`

These are existing posthoc artifacts in `reports/oty2/`. The diagnostic does not read `archive/` or `old_work/` as active sources.

## Manual Contour Reference Boundary

The 2026-07-04 rough human contour markings are used only as non-authoritative visual reference language. They suggest recurring visual patterns such as long side ridges, endpoint hotspots, weak far-side returns, discontinuous shell completion, and GT-scale body outlines. They are not GT edits, not revised annotations, not final boxes, not identity truth, and not selector labels. The temporary marked PNG files are not committed.

## Diagnostic A: Vehicle Shell Grammar Cases

For each GT-anchored morphology row, express the case as:

- `scattering_atom`: a local bright point, peak, or tiny component. It cannot be called a vehicle.
- `vehicle_part`: a side strip, endpoint/corner reflector, edge fragment, weak far-side return, or body block. It is a possible part, not a complete vehicle.
- `vehicle-scale_shell_hypothesis`: a GT-scale composition of multiple parts forming a shell, boundary, long/short-axis relation, or strip-plus-endpoint pattern. It remains posthoc.

GT scale compatibility is required to avoid the baby-car error.

## Diagnostic B: Vehicle Part Grammar Relations

Record structural relations rather than component counts alone:

- side ridge to endpoint hotspot
- dominant side ridge to weak far-side return
- left/right endpoint relation
- upper/lower edge relation
- strip to block body
- discontinuous edge to shell completion
- range spread to body core
- near-field spread to strong side response

These are physical interpretation relations, not weights.

## Diagnostic C: Physical Structure Failure Modes

Explain why a case does not support a vehicle-scale shell. Common modes include only atoms, single part without shell, parts too small, scattered parts, background line confounders, GT quality uncertainty, support miss, near-field spread unresolved, and temporal unavailable.

## Diagnostic D: Temporal Drift Physical Consistency

Use available temporal morphology probes to check whether ridges, hotspots, centroids, and shell proxies persist and drift gradually. The preferred conceptual offsets are `-10 / -5 / 0 / +5 / +10`; when the existing probe only has `-5..+5`, record that limitation. Temporal drift is a posthoc mechanism signal, not identity truth.

## Diagnostic E: Support Failure Physical Explanation

Only after GT-anchored shell evidence is described, explain whether optical-derived support covers the shell. If the shell is outside support, mark support construction failure. Do not continue searching inside a wrong support and promote a small component to vehicle.

## Diagnostic F: Weighted Fusion Deferred Boundary

Produce a small boundary table stating why weighted fusion is deferred. Weighted fusion may only become fallback bookkeeping after physical shell grammar and temporal drift behavior are understood.

## Outputs

- `reports/oty2/oty2_vehicle_shell_grammar_cases_<timestamp>.csv`
- `reports/oty2/oty2_vehicle_part_grammar_relations_<timestamp>.csv`
- `reports/oty2/oty2_physical_structure_failure_modes_<timestamp>.csv`
- `reports/oty2/oty2_temporal_drift_physical_consistency_<timestamp>.csv`
- `reports/oty2/oty2_support_failure_physical_explanation_<timestamp>.csv`
- `reports/oty2/oty2_weighted_fusion_deferred_boundary_<timestamp>.csv`
- `reports/oty2/oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_report_<timestamp>.md`
- `reports/oty2/oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_summary_<timestamp>.json`
- `reports/oty2/visual_exemplars/oty2_physical_shell_grammar_temporal_drift_atlas_cn_<timestamp>.html`
- `reports/oty2/visual_exemplars/<case_id>_physical_shell_grammar_temporal_cn.png`
- `D:\profile\research\workspace\logs\oty2_physical_sar_vehicle_shell_grammar_and_temporal_drift_<timestamp>.log`

## Boundary Flags

- `posthoc_sar_gt_used=true`
- `posthoc_sar_image_content_used=true`
- `physical_shell_grammar_entered=true`
- `temporal_drift_mechanism_entered=true`
- `weighted_fusion_deferred=true`
- `weighted_fusion_mainline_used=false`
- `selector_or_ranking_used=false`
- `training_or_threshold_tuning_entered=false`
- `annotation_proposal_entered=false`
- `revised_gt_box_output=false`
- `final_candidate_box_output=false`
- `identity_truth_claimed=false`
- `gt_or_sar_image_used_for_runtime_prior_construction=false`
- `shell_grammar_written_as_annotation_rule=false`
- `temporal_drift_written_as_identity_truth=false`
- `archive_or_old_work_used_as_active_source=false`
- `zip_7z_rar_committed=false`
