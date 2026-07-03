# OTY2 GT-Anchored SAR Vehicle Morphology And Support Coverage Report

Generated: `20260703_163000`

This report archives manual visual review notes and audits GT-anchored SAR morphology plus optical-derived support coverage. It does not generate annotation proposals, final candidate boxes, selector/ranking outputs, training, threshold tuning, best weights, or identity truth.

## Ledger Boundary

- 442 = all SAR GT / SAR-side target reference pool
- 215 = current frame-level posthoc optical-SAR paired subset
- 195 = GM_RM011 blocked_missing_object_stream, not unannotated
- 20 = SAR-only morphology reference only
- 12 = dropout/no-match temporal continuation special pool

## Key Metrics

- manual_visual_note_rows: `13`
- gt_total: `442`
- gt_image_available: `442`
- gt_energy_available: `442`
- gt_valid_for_morphology_or_special: `442`
- support_coverage_paired_rows: `215`
- support_boundary_available_paired: `215`
- support_gt_area_coverage_ge_0p80: `192`
- support_gt_energy_coverage_ge_0p80: `192`
- support_morphology_proxy_coverage_ge_0p80: `194`
- complete_pool_rows: `103`
- complete_80_85_supported: `84`
- complete_80_85_not_supported: `19`
- compensation_pool_rows: `124`
- compensation_pool_mix: `left/right or bottom truncation;edge contact=58;review-only ambiguity=37;identity ambiguity;handoff/duplicate=17;dropout/no-match temporal continuation=12`
- support_overlay_availability_rows: `13`
- support_overlay_panels_generated: `13`
- support_overlay_atlas_generated: `yes`

## Required Answers

1. Manual visual review shows SAR vehicles often have near/facing-side high energy, continuous or discontinuous body-edge strips, endpoint/corner reflectors, far-side weak return, and temporal hotspot migration.
2. GT boxes should be accepted as SAR morphology anchors when the frame shows self-consistent vehicle structure; this is separate from optical-SAR association strength.
3. Association ambiguity cannot negate GT-box SAR morphology because object-time identity and SAR vehicle body structure are different layers.
4. near-side ridge = strong body-side strip on radar-facing/near side when validated by visual or calibrated geometry; facing hotspot = local high-energy atom on facing/near endpoint; far-side weak return = lower-energy opposite side; discontinuous body edges = aligned separated high-energy fragments that still form body structure.
5. 442 SAR GT morphology audit: image_available=442, energy_available=442, morphology_reference_or_special=442.
6. 215 paired support boundary renderability: support_boundary_available=215 via reconstructed sector/range fields; explicit support mask/path files were not found.
7. Complete optical 80-85 coverage hypothesis: complete_pool=103, supported_all_three_coverage=84, uncertain_or_failed=19.
8. 80-85% is reported separately as GT area coverage, GT energy coverage, and high-energy morphology proxy coverage; it is not a single scalar and not a runtime rule.
9. Truncated/occluded/edge/ambiguous/dropout compensation pool rows=124; these require temporal/state compensation because single-frame support can miss shifted or fragmented SAR body cues.
10. Concepts still needing calibration: physical near/far side direction, support-mask file format if one exists, motion-drift compatibility, endpoint versus head/tail wording, and nearby e-bike/guardrail confounders.
11. Next priority should be visual support overlay review, then motion/drift compatibility and GM_RM019 optical continuity; GM_RM011 recovery remains later scale expansion.
12. Stage archive items: manual visual notes, morphology primitive definitions, coverage definitions, support availability audit, and posthoc-only boundary flags.

## Why This Is Not A Statistical Detour Or Local Selector Optimization

1. No training, threshold tuning, final candidate box, selector, ranking, or best-weight search is performed.
2. This is not another descriptor table: it archives manual morphology evidence and audits GT-area, GT-energy, and morphology-proxy support coverage.
3. GT-box SAR body structure is explicitly acknowledged as morphology evidence; association ambiguity is kept as a separate layer.
4. Coverage is split into GT area coverage, GT energy coverage, and high-energy morphology primitive proxy coverage.
5. Support is not left to human guessing: panels render reconstructed support boundaries when source fields exist; otherwise availability rows say why not.
6. The complete-object 80-85% coverage hypothesis is only a posthoc audit hypothesis, not a runtime rule.
7. Next work should inspect support overlays visually, then add motion/drift compatibility, GM_RM019 continuity review, and later GM_RM011 scale expansion.

## Boundary Flags

- human_visual_review_notes_archived: `true`
- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- gt_anchored_morphology_audit_entered: `true`
- support_coverage_hypothesis_audit_entered: `true`
- support_overlay_panels_generated: `true`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- complete_object_80_85_hypothesis_written_as_runtime_rule: `false`
- state_conditioned_topk_written_as_runtime_rule: `false`
- annotation_proposal_entered: `false`
- final_candidate_box_output: `false`
- selector_or_ranking_used: `false`
- training_or_threshold_tuning_entered: `false`
- best_weight_selected: `false`
- identity_truth_claimed: `false`
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`
- matlab_zip_or_any_zip_committed: `false`

## Outputs

- human_visual_review_archive_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_human_visual_review_notes_and_sar_morphology_insight_archive.md`
- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage_plan.md`
- manual_visual_review_notes_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_human_visual_review_notes_20260703_manual.csv`
- sar_vehicle_morphology_primitives_gt_anchored_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_vehicle_morphology_primitives_gt_anchored_20260703_163000.csv`
- gt_box_energy_distribution_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_box_energy_distribution_audit_20260703_163000.csv`
- optical_support_coverage_hypothesis_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_support_coverage_hypothesis_audit_20260703_163000.csv`
- complete_optical_high_confidence_coverage_pool_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_complete_optical_high_confidence_coverage_pool_20260703_163000.csv`
- truncated_occluded_temporal_compensation_pool_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_truncated_occluded_temporal_compensation_pool_20260703_163000.csv`
- support_overlay_image_availability_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_overlay_image_availability_20260703_163000.csv`
- gt_anchored_sar_vehicle_morphology_and_support_coverage_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage_report_20260703_163000.md`
- gt_anchored_sar_vehicle_morphology_and_support_coverage_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage_summary_20260703_163000.json`
- support_overlay_atlas_html: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_gt_support_energy_overlay_atlas_20260703_163000.html`
- workspace_log: `D:\profile\research\workspace\logs\oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage_20260703_163000.log`

## Sources

- gt_accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- support_peak_competition_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_peak_competition_audit_20260703_091849.csv`
- visual_review_cards_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_visual_review_candidate_cards_20260703_151500.csv`
