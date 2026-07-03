# OTY2 SAR Vehicle Structure Mechanism Beyond Weighted Fusion Report

Generated: `20260703_151500`

This report explores SAR vehicle structure as primitives, compositions, graph proxies, temporal tubes, optical-conditioned hypotheses, and visual-review cards. It does not generate annotation proposals, final boxes, selector/ranking outputs, trained models, tuned thresholds, best weights, or identity truth.

## Ledger Boundary

- 442 = all SAR GT / SAR-side target reference pool
- 215 = current frame-level posthoc optical-SAR paired subset
- 195 = GM_RM011 blocked_missing_object_stream
- 20 = SAR-only morphology reference
- 12 = dropout/no-match temporal continuation special pool

## Key Metrics

- gt_total: `442`
- gt_image_available: `442`
- gt_full_inside_fallback_fan_mask: `442`
- gt_partial_overlap_fallback_fan_mask: `0`
- gt_near_mask_boundary: `0`
- gt_mask_unable_to_judge: `0`
- pool_paired_215: `215`
- pool_gm011_blocked: `195`
- pool_sar_only: `20`
- pool_dropout_special: `12`
- pool_unknown: `0`
- primitive_catalog_rows: `442`
- primitive_type_mix: `range_ridge=259;azimuth_ridge=180;background_clutter_patch=2;peak_group=1`
- composition_rows: `215`
- composition_type_mix: `range-spread body hypothesis=187;stable-tube vehicle proxy=22;azimuth-spread body hypothesis=6`
- graph_rows: `215`
- graph_multi_component_rate: `0.9907`
- tube_rows: `53`
- tube_type_mix: `vehicle-like drifting tube candidate=16;dropout_existence_tube=12;diffuse or fragmented tube=12;stable background tube risk=10;jumping peak tube=3`
- optical_condition_rows: `10`
- failure_case_index_rows: `276`
- visual_review_card_count: `13`
- visual_panels_generated: `13`
- visual_atlas_generated: `yes`

## Required Answers

1. 442 SAR GT valid-mask audit: full_inside=442, partial_overlap=0, near_boundary=0, unable_to_judge=0. The mask source is fallback fan valid region; no external mask file was found.
2. 442 pool split: paired=215, GM_RM011 waiting=195, SAR-only=20, dropout special=12, unknown=0. Only paired rows can enter optical-SAR correspondence.
3. The previous 215 paired rows have SAR structure but unique isolation remains zero because peak competition, spread structures, and multi-component graph proxies prevent a single isolated structure from being claimed.
4. Primitives improve on top-k by naming compact blobs, peak pairs/groups, range/azimuth ridges, boundary-affected proxies, and clutter patches instead of selecting the brightest point.
5. Composition hypotheses separate compact, multi-peak, range-spread, azimuth-spread, stable-tube, and reject forms without emitting final boxes.
6. Graph probes show competing/multi-component structure in 0.9907 of paired cases, explaining why support regions are not unique structures.
7. Temporal tube probing separates vehicle-like drifting-tube candidates from stable-background risk, jumping peaks, diffuse tubes, and dropout existence-only tubes; wrong-frame confounding remains a blocker.
8. Optical-conditioned hypotheses explain how truncation, edge contact, identity ambiguity, scale, tracklet smoothing, and azimuth trend should change expected SAR structure rather than directly set a box.
9. Weighted evidence is retained only as a diagnostic bookkeeping form; it cannot be the main line because it fails to explain primitive composition, graph competition, and identity confounding.
10. Most promising next forms are graph, temporal-form, rule/grammar composition, and review-gated form.
11. Visual review is required for 13 candidate-card categories; the atlas generation status is yes.
12. GM_RM019 optical continuity review is still needed as a small quality anchor for object hypothesis continuity.
13. GM_RM011 recovery should remain deferred as scale expansion until this mechanism line is visually and temporally checked.
14. A short stage recap or follow-up branch is reasonable after visual exemplar review; this still should not become OTY3 automatic annotation.

## Mechanism Forms Beyond Weighted Fusion

- `rule / grammar form`: vehicle structure is an allowed primitive composition under optical state and SAR temporal stability It explains compact vs multi-peak vs spread vs diffuse semantics; limitation: wrong-frame persistence without motion gate; local-optimum risk: low if kept grammar-like; high if turned into hand-tuned classes.
- `graph form`: vehicle is a connected SAR primitive subgraph compatible with optical support and temporal tube It explains multiple competing structures and neighbor overlap; limitation: true physical identity without review; local-optimum risk: medium if graph is just a descriptor table.
- `energy-field form`: vehicle is high structure concentration in feasible region with low competing components It explains diffuse/reject versus concentrated cases; limitation: object identity in crowded same-scene supports; local-optimum risk: high if optimized as a scalar score.
- `contrastive form`: true support should separate from random/range-shift while wrong-object/wrong-frame reveal confounding It explains real range/state signal and object-time confounding; limitation: exact association decision; local-optimum risk: low if used for falsification.
- `temporal-form`: vehicle is a structure tube with plausible drift, not a single-frame peak It explains stable vehicle-like versus background persistence; limitation: drift compatibility is incomplete; local-optimum risk: medium if persistence alone is rewarded.
- `review-gated form`: vehicle-like but object-time ambiguous cases should become review_required, not association It explains why visual review is needed before identity claims; limitation: automatic scale expansion; local-optimum risk: low.
- `weighted evidence form`: normalized evidence combination can summarize diagnostics It explains rough diagnostic bookkeeping; limitation: primitive composition, graph competition, and identity confounding; local-optimum risk: high; it can become a hidden selector.

## Why This Is Not A Local Statistical / Weighted-Fusion Optimum

1. No training, threshold tuning, or best-weight selection is performed.
2. No final box, ranking, or selector output is emitted.
3. The main outputs are primitive, composition, graph, tube, optical-conditioned, failure, and review-card mechanisms, not only descriptors.
4. Top-k near-GT, GT-inside support, peak/background, and association counts can mislead if they are treated as runtime capability.
5. Graph, temporal tube, and optical-conditioned grammar forms have cross-scene/frame/object potential, but only after visual and motion validation.
6. Compact, multi-peak, spread, diffuse, wrong-frame, wrong-object, and boundary cases require human visual review.
7. Next work should inspect visual exemplars and add motion/overlap gates, not continue stacking scalar metrics.
8. Best-weight search and top-k metric tuning should remain paused because they would hide object-time confounding.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- sar_gt_valid_mask_audit_entered: `true`
- structure_primitive_extraction_entered: `true`
- structure_composition_hypothesis_entered: `true`
- structure_graph_probe_entered: `true`
- temporal_tube_probe_entered: `true`
- visual_review_cards_generated: `true`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- gt_peak_or_residual_written_to_runtime_prior: `false`
- state_conditioned_topk_written_as_runtime_rule: `false`
- annotation_proposal_entered: `false`
- final_candidate_box_output: `false`
- selector_or_ranking_used: `false`
- training_or_threshold_tuning_entered: `false`
- best_weight_selected: `false`
- identity_truth_claimed: `false`
- model_weights_committed: `false`
- matlab_zip_or_any_zip_committed: `false`
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`

## Outputs

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion_plan.md`
- sar_gt_reference_mask_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_gt_reference_mask_audit_20260703_151500.csv`
- sar_structure_primitive_catalog_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_structure_primitive_catalog_20260703_151500.csv`
- sar_structure_composition_hypotheses_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_structure_composition_hypotheses_20260703_151500.csv`
- sar_structure_graph_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_structure_graph_probe_20260703_151500.csv`
- sar_temporal_tube_mechanism_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_temporal_tube_mechanism_probe_20260703_151500.csv`
- optical_conditioned_structure_hypotheses_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_optical_conditioned_structure_hypotheses_20260703_151500.csv`
- mechanism_failure_case_index_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_mechanism_failure_case_index_20260703_151500.csv`
- visual_review_candidate_cards_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_visual_review_candidate_cards_20260703_151500.csv`
- sar_vehicle_structure_mechanism_beyond_weighted_fusion_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion_report_20260703_151500.md`
- sar_vehicle_structure_mechanism_beyond_weighted_fusion_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion_summary_20260703_151500.json`
- visual_atlas_html: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_sar_vehicle_structure_mechanism_atlas_20260703_151500.html`
- workspace_log: `D:\profile\research\workspace\logs\oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion_20260703_151500.log`

## Sources

- gt_accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- support_observation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_structure_observation_20260703_112931.csv`
- structure_crosscheck_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_structure_counterfactual_crosscheck_20260703_112931.csv`
- temporal_tube_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_structure_temporal_tube_probe_20260703_112931.csv`
- provenance_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_structure_representation_and_association_provenance_summary_20260703_112931.json`
