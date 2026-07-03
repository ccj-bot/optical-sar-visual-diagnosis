# OTY2 GT-Anchored Vehicle-Scale SAR Morphology And GT Quality Audit Plan

Updated: 2026-07-03

This plan runs a bounded OTY2 posthoc diagnostic that anchors SAR morphology to SAR GT vehicle scale, audits GT quality, and identifies cases where the optical-derived support misses GT vehicle-scale structure.

## Inputs

- `reports/oty2/oty2_gt_sample_accounting_audit_20260702_192810.csv`
- `reports/oty2/oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- `reports/oty2/oty2_gt_box_energy_distribution_audit_20260703_163000.csv`
- `reports/oty2/oty2_optical_support_coverage_hypothesis_audit_20260703_163000.csv`
- `reports/oty2/oty2_support_wide_energy_atoms_and_components_20260703_212811.csv`
- `reports/oty2/oty2_support_wide_vehicle_shell_proxy_20260703_212811.csv`
- `reports/oty2/oty2_support_failure_taxonomy_20260703_212811.csv`

The audit reads these as existing posthoc artifacts. It does not read from `archive/` or `old_work/` as active sources.

## Diagnostic A: SAR GT Vehicle Scale Statistics

Compute GT width, height, area, aspect ratio, long axis, short axis, orientation proxy, boundary proximity, scale outlier flags, and pool type for all 442 SAR GT rows.

Purpose: build a vehicle-scale anchor so tiny scattering atoms are not promoted to "baby car" vehicle shells.

## Diagnostic B: SAR GT Quality Audit

Audit each GT box for possible too-small, too-large, offset, boundary, extreme-aspect, low-energy, or multi-structure issues. This is a review candidate generator only. It does not revise GT and does not output a replacement box.

## Diagnostic C: GT-Anchored Energy Morphology

Use the GT crop as the morphology anchor. Record side ridge, corner hotspot, discontinuous edge, enclosed shell, block body, diffuse-with-core, weak-boundary, and uncertainty labels.

All SAR image evidence remains posthoc SAR observation.

## Diagnostic D: Atom / Part / Shell Hierarchy

Separate:

- `scattering_atom`: small local energy peaks or tiny components.
- `vehicle_part`: plausible strips, corners, endpoints, or local blocks.
- `vehicle_scale_shell_hypothesis`: a GT-scale composition of multiple parts or body-scale structure.

No small component may be called a vehicle shell.

## Diagnostic E: GT-Support Miss / Failure Cases

For the 215 paired pool, compare optical-derived support coverage against GT-anchored vehicle-scale morphology. If the GT vehicle-scale morphology is outside support, emit `support_miss_vehicle_structure=yes` and `if_support_miss_do_not_search_inside_support=yes`.

This corrects the previous support-internal failure mode: wrong support must not be rescued by interpreting a small support-internal component as the car.

## Diagnostic F: GT Quality Visual Review Candidates

Generate review candidates for:

- possible GT too small
- possible GT too large
- possible GT offset
- possible GT boundary affected
- possible extreme aspect
- weak but structured GT
- multi-structure inside GT
- support miss but GT good
- support miss and GT uncertain
- good GT scale anchor

If image paths are available, render a Chinese atlas under `reports/oty2/visual_exemplars/`.

## Outputs

- `reports/oty2/oty2_sar_gt_vehicle_scale_statistics_<timestamp>.csv`
- `reports/oty2/oty2_sar_gt_quality_audit_<timestamp>.csv`
- `reports/oty2/oty2_gt_anchored_energy_morphology_<timestamp>.csv`
- `reports/oty2/oty2_atom_part_shell_hierarchy_<timestamp>.csv`
- `reports/oty2/oty2_gt_support_miss_failure_cases_<timestamp>.csv`
- `reports/oty2/oty2_gt_quality_visual_review_candidates_<timestamp>.csv`
- `reports/oty2/oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_report_<timestamp>.md`
- `reports/oty2/oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_summary_<timestamp>.json`
- `reports/oty2/visual_exemplars/oty2_gt_quality_vehicle_scale_morphology_atlas_cn_<timestamp>.html`
- `reports/oty2/visual_exemplars/<case_id>_gt_quality_vehicle_scale_cn.png`
- `D:\profile\research\workspace\logs\oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_<timestamp>.log`

## Boundary Flags

- `posthoc_sar_gt_used=true`
- `posthoc_sar_image_content_used=true`
- `gt_quality_audit_entered=true`
- `gt_anchored_vehicle_scale_morphology_entered=true`
- `atom_part_shell_hierarchy_entered=true`
- `support_miss_diagnostic_entered=true`
- `gt_or_sar_image_used_for_runtime_prior_construction=false`
- `runtime_prior_construction_used_gt=false`
- `annotation_proposal_entered=false`
- `revised_gt_box_output=false`
- `final_candidate_box_output=false`
- `selector_or_ranking_used=false`
- `training_or_threshold_tuning_entered=false`
- `identity_truth_claimed=false`
- `vehicle_scale_shell_hypothesis_written_as_annotation_rule=false`
- `support_miss_written_as_runtime_rule=false`
- `detection_dropout_rows_mixed_into_clean_paired=false`
- `gm011_missing_object_stream_rows_mixed_into_correspondence=false`
- `sar_only_rows_mixed_into_optical_sar_correspondence=false`
- `archive_or_old_work_used_as_active_source=false`
- `zip_7z_rar_committed=false`
