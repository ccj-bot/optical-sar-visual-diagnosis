# OTY2 GT-Anchored Vehicle-Scale SAR Morphology And GT Quality Audit Report

Generated: `20260703_222135`

This report anchors SAR morphology to SAR GT vehicle scale and audits GT quality before interpreting support-wide structures. It is posthoc mechanism diagnosis only: no revised GT, final box, annotation proposal, selector/ranking, training, threshold tuning, or identity truth is produced.

## Ledger Boundary

- 442 = all SAR GT / SAR-side target reference pool
- 215 = current OTY optical-object to SAR-GT frame-level paired pool
- 195 = GM_RM011 blocked_missing_object_stream, not unannotated
- 20 = SAR-only GT, SAR morphology reference only
- 12 = dropout/no_oty_iou_match/temporal continuation special pool

## 442 SAR GT Scale Statistics

- gt_total: `442`
- gt_image_available: `442`
- gt_box_available: `442`
- valid_vehicle_scale_reference_count: `349`
- scale_outlier_mix: `none=361;too_small=36;too_large=24;extreme_aspect=21`
- width distribution: `{"n": "442", "min": "63.882", "q05": "73.429", "q25": "84.489", "median": "145.75", "q75": "162", "q95": "176.839", "max": "198.122"}`
- height distribution: `{"n": "442", "min": "62.847", "q05": "64.277", "q25": "70.198", "median": "76.36", "q75": "156.614", "q95": "185.464", "max": "204.011"}`
- area distribution: `{"n": "442", "min": "8065.344", "q05": "8503.404", "q25": "10549.664", "median": "11985.414", "q75": "13136.733", "q95": "15321.489", "max": "17456.434"}`
- aspect distribution: `{"n": "442", "min": "1.7218", "q05": "1.8667", "q25": "2.0167", "median": "2.1399", "q75": "2.2844", "q95": "2.4878", "max": "2.7731"}`

### By Scene

- GM_RM011: count=`201`, area=`{"n": "201", "min": "8065.344", "q05": "8116.64", "q25": "8775.939", "median": "12097.032", "q75": "13826.678", "q95": "16191.979", "max": "17456.434"}`, scale_outlier_mix=`none=133;too_small=35;too_large=19;extreme_aspect=14`
- GM_RM017: count=`216`, area=`{"n": "216", "min": "9333.137", "q05": "10190.342", "q25": "11016.843", "median": "12109.812", "q75": "12952.528", "q95": "14451.532", "max": "17041.86"}`, scale_outlier_mix=`none=204;extreme_aspect=6;too_large=5;too_small=1`
- GM_RM019: count=`25`, area=`{"n": "25", "min": "9281.233", "q05": "9404.938", "q25": "10096.746", "median": "10618.56", "q75": "11207.329", "q95": "13003.846", "max": "13569.698"}`, scale_outlier_mix=`none=24;extreme_aspect=1`

### By Pool Type

- gm011_waiting_object_stream: count=`195`, valid_scale_reference_count=`129`, scale_outlier_mix=`none=129;too_small=34;too_large=19;extreme_aspect=13`
- paired_215: count=`215`, valid_scale_reference_count=`203`, scale_outlier_mix=`none=203;extreme_aspect=7;too_large=4;too_small=1`
- sar_only: count=`20`, valid_scale_reference_count=`17`, scale_outlier_mix=`none=17;too_large=1;extreme_aspect=1;too_small=1`
- dropout_special: count=`12`, valid_scale_reference_count=`0`, scale_outlier_mix=`none=12`

## GT Quality Audit

- gt_quality_label_mix: `good=234;review_multi_structure=105;review_too_small=36;review_too_large=24;review_low_energy=22;review_extreme_aspect=21`
- manual_gt_review_candidate_count: `208`

The GT quality audit only finds review candidates. It does not modify GT, does not output revised boxes, and does not become a selector.

## GT-Anchored Morphology

- dominant_energy_pattern_mix: `side_ridge=173;corner_hotspot=133;enclosed_shell=69;discontinuous_edges=53;weak_boundary=14`
- vehicle_morphology_supported_mix: `yes=263;uncertain=179`

GT-anchored morphology uses SAR image observations inside the GT crop to describe side ridges, corner hotspots, discontinuous edges, enclosed shell hypotheses, block-like body hypotheses, weak boundaries, and uncertain cases.

## Atom / Part / Shell Hierarchy

- hierarchy_label_mix: `scattering_atom=2677;vehicle_part=781;vehicle_scale_shell_hypothesis=172`
- vehicle_scale_shell_hypothesis_rows: `172`

This hierarchy prevents the baby-car error: small bright components are `scattering_atom` or `vehicle_part`; only a GT-scale composition of multiple parts can be named `vehicle_scale_shell_hypothesis`, and even that remains a posthoc hypothesis.

## GT-Support Miss Failure Cases

- support_miss_vehicle_structure_yes: `11`
- support_miss_vehicle_structure_uncertain: `13`
- support_failure_type_mix: `support_ok_but_not_exclusive=143;support_contains_neighbor_structure=138;support_too_broad=137;state_compensation_missing=110;temporal_compensation_needed=110;optical_truncation_induced_shift=65;none=48;near_field_truncation_issue=33;support_too_narrow=13;support_miss=9`

**If GT-anchored vehicle-scale morphology is outside support, the correct diagnostic is support construction failure, not support-internal vehicle search.**

Support failure and GT quality issue are separated: GT quality asks whether the SAR GT box is a reliable morphology anchor; support failure asks whether optical-derived support covers the GT-anchored vehicle-scale structure.

## GT Quality Visual Review Candidates

- review_candidate_rows: `39`
- atlas_panels_generated: `18`
- atlas: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_gt_quality_vehicle_scale_morphology_atlas_cn_20260703_222135.html`

Review categories include possible GT too small, too large, offset, boundary affected, extreme aspect, weak but structured GT, multi-structure inside GT, support miss but GT good, support miss and GT uncertain, and good GT scale anchors.

## Why This Corrects The Support-Internal / Baby-Car Error

1. If the GT-anchored vehicle-scale body is outside support, support is wrong for that case; a tiny structure inside support cannot rescue it.
2. A small component is only a scattering atom or vehicle part. It cannot be called a vehicle shell by itself.
3. GT width, height, area, and long/short axes provide the vehicle-scale reference that prevents baby-car interpretations.
4. The hierarchy separates scattering atom, vehicle part, and vehicle-scale shell hypothesis.
5. GT quality issue and support failure must remain separate because a bad GT anchor and a bad support construction imply different next actions.
6. This run outputs no revised annotation, no final box, no selector, and no GT-guided prediction logic.
7. Manual review is still needed for GT quality flags, low-energy structured cases, multi-structure GT, and support-miss cases.
8. The next useful step is motion/drift compatibility and GM_RM019 optical continuity review, not another static support-internal metric table.

## Required Answers

1. The 442 GT scale distribution is reported above for width, height, area, aspect ratio, long axis, and short axis, with scene and pool splits.
2. Potential GT issues are summarized by `gt_quality_label_mix=good=234;review_multi_structure=105;review_too_small=36;review_too_large=24;review_low_energy=22;review_extreme_aspect=21` and review candidates in the CSV.
3. Vehicle-scale reference count: `349`.
4. Main GT morphology patterns: `side_ridge=173;corner_hotspot=133;enclosed_shell=69;discontinuous_edges=53;weak_boundary=14`.
5. The atom/part/shell hierarchy prevents baby-car promotion by blocking tiny components from being called vehicle shells.
6. Support miss yes cases: `11`; uncertain cases: `13`.
7. Rows with `support_miss_vehicle_structure=yes` are cases where GT body structure is outside support and support-internal search must stop.
8. GT quality issue is a GT anchor problem; support issue is an optical-derived feasible-region problem.
9. Manual GT review candidates: `208` quality rows plus categorized visual review CSV rows.
10. GT quality labels, morphology patterns, shell hypotheses, support miss, and atlas notes are all posthoc hypotheses.
11. Next step: motion/drift compatibility and GM_RM019 optical continuity review are more useful than more static support-internal tables; stage recap is also reasonable after this handoff.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- gt_quality_audit_entered: `true`
- gt_anchored_vehicle_scale_morphology_entered: `true`
- atom_part_shell_hierarchy_entered: `true`
- support_miss_diagnostic_entered: `true`
- visual_review_candidate_list_generated: `true`
- chinese_atlas_generated: `true`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- annotation_proposal_entered: `false`
- revised_gt_box_output: `false`
- final_candidate_box_output: `false`
- selector_or_ranking_used: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- gt_quality_audit_used_as_auto_relabel: `false`
- vehicle_scale_shell_hypothesis_written_as_annotation_rule: `false`
- support_miss_written_as_runtime_rule: `false`
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`
- archive_or_old_work_used_as_active_source: `false`
- zip_7z_rar_committed: `false`

## Outputs

- concept_correction_archive_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_gt_support_failure_concept_correction_archive.md`
- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_plan.md`
- sar_gt_vehicle_scale_statistics_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_gt_vehicle_scale_statistics_20260703_222135.csv`
- sar_gt_quality_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_gt_quality_audit_20260703_222135.csv`
- gt_anchored_energy_morphology_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_anchored_energy_morphology_20260703_222135.csv`
- atom_part_shell_hierarchy_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_atom_part_shell_hierarchy_20260703_222135.csv`
- gt_support_miss_failure_cases_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_support_miss_failure_cases_20260703_222135.csv`
- gt_quality_visual_review_candidates_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_quality_visual_review_candidates_20260703_222135.csv`
- gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_report_20260703_222135.md`
- gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_summary_20260703_222135.json`
- visual_atlas_html: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_gt_quality_vehicle_scale_morphology_atlas_cn_20260703_222135.html`
- workspace_log: `D:\profile\research\workspace\logs\oty2_gt_anchored_vehicle_scale_sar_morphology_and_gt_quality_audit_20260703_222135.log`

## Sources

- gt_accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- gt_energy_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_box_energy_distribution_audit_20260703_163000.csv`
- support_coverage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_support_coverage_hypothesis_audit_20260703_163000.csv`
- support_peak_competition_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_peak_competition_audit_20260703_091849.csv`
- support_wide_atoms_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_wide_energy_atoms_and_components_20260703_212811.csv`
- support_wide_shell_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_wide_vehicle_shell_proxy_20260703_212811.csv`
- support_failure_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_failure_taxonomy_20260703_212811.csv`
