# OTY2 Support Overlay Visualization QA And Chinese Review Atlas Report

Generated: `20260703_174930`

This report fixes the support overlay visualization workflow and regenerates a Chinese review atlas. It does not generate annotation proposals, final candidate boxes, selector/ranking outputs, training, threshold tuning, best weights, or identity truth.

## Why Previous Overlay Atlas Should Not Be Used Without QA

1. The previous PNG generator cropped the SAR image and resized crops wider than 520 px before drawing overlays.
2. GT/support/energy overlay points were shifted by crop origin, but the resize scale was not applied.
3. Panels with resize-specific risk: `5` / `13`.
4. Resize-risk cases: `PAIR_GM_RM017_o153_s319_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM019_o13_s27_oty1t_obj_GM_RM019_bytetrack_bt_0005;PAIR_GM_RM019_o15_s31_oty1t_obj_GM_RM019_bytetrack_bt_0005;PAIR_GM_RM019_o13_s27_oty1t_obj_GM_RM019_bytetrack_bt_0005;PAIR_GM_RM017_o149_s310_oty1t_obj_GM_RM017_bytetrack_bt_0008`.
5. Manual SAR morphology notes can be retained as textual observations when they do not depend on support alignment.
6. Previous support coverage visual judgment must be paused because it may have been based on visually shifted support/GT boundaries.
7. The fixed atlas renders image and overlays in one crop-local axes and records full-image, crop-local, and render coordinates.

## Coordinate QA Result

- pass: `11`
- warning: `2`
- fail: `0`
- support_unjudgeable_cases: `2`

Warnings are expected for SAR-only or GM_RM011 reference panels because paired optical-derived support is unavailable there.

## Required Answers

1. The previous overlay atlas has coordinate/scale risk. The concrete bug is resize-without-overlay-scale after crop.
2. The main coordinate-transform issue is not HTML overlay scaling; the HTML embedded static PNGs. The risky transform is in PNG generation: crop-local coordinates were drawn on a resized crop without applying scale.
3. This run fixes the issue by drawing SAR crop, GT, support, and energy atoms inside one matplotlib axes with `origin='upper'` and crop-local extent `(0, crop_width, crop_height, 0)`. Render coordinates equal crop-local coordinates, so `scale_x=scale_y=1`.
4. QA pass cases: `PAIR_GM_RM017_o184_s383_oty1t_obj_GM_RM017_bytetrack_bt_0014;PAIR_GM_RM017_o153_s319_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM019_o13_s27_oty1t_obj_GM_RM019_bytetrack_bt_0005;PAIR_GM_RM017_o165_s343_oty1t_obj_GM_RM017_bytetrack_bt_0010;PAIR_GM_RM017_o165_s343_oty1t_obj_GM_RM017_bytetrack_bt_0010;PAIR_GM_RM019_o15_s31_oty1t_obj_GM_RM019_bytetrack_bt_0005;PAIR_GM_RM019_o13_s27_oty1t_obj_GM_RM019_bytetrack_bt_0005;PAIR_GM_RM017_o149_s310_oty1t_obj_GM_RM017_bytetrack_bt_0008;PAIR_GM_RM017_o165_s343_oty1t_obj_GM_RM017_bytetrack_bt_0010;PAIR_GM_RM017_o165_s343_oty1t_obj_GM_RM017_bytetrack_bt_0010;PAIR_GM_RM017_o165_s343_oty1t_obj_GM_RM017_bytetrack_bt_0010`.
5. QA warning cases: `GTREF_GM_RM017_s302_96;GTREF_GM_RM011_s0_336`.
6. QA fail cases: `none`.
7. Chinese atlas regenerated: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_gt_support_energy_overlay_atlas_cn_20260703_174930.html`.
8. Chinese review cards state what to inspect, why to inspect it, what may be recorded, and what must not be concluded.
9. Previous manual SAR morphology notes that describe GT-box body structure, near/facing-side high energy, discontinuous body edges, and temporal hotspot migration may be retained as morphology notes.
10. Previous support coverage visual judgments from the old atlas must be paused until reviewers use the fixed CN atlas and coordinate QA CSV.
11. Next manual review should use the fixed CN atlas panels and the Chinese card index, starting with warnings/reference-only cases and old resize-risk cases.
12. After human review, motion/drift compatibility or GM_RM019 optical continuity review can continue as a separate bounded stage.

## Boundary Flags

- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- visualization_coordinate_qa_entered: `true`
- chinese_review_atlas_generated: `true`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- runtime_prior_construction_used_gt: `false`
- annotation_proposal_entered: `false`
- final_candidate_box_output: `false`
- selector_or_ranking_used: `false`
- training_or_threshold_tuning_entered: `false`
- best_weight_selected: `false`
- identity_truth_claimed: `false`
- complete_object_80_85_hypothesis_written_as_runtime_rule: `false`
- detection_dropout_rows_mixed_into_clean_paired: `false`
- gm011_missing_object_stream_rows_mixed_into_correspondence: `false`
- sar_only_rows_mixed_into_optical_sar_correspondence: `false`
- matlab_zip_or_any_zip_committed: `false`

## Outputs

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_support_overlay_visualization_qa_and_chinese_review_atlas_plan.md`
- coordinate_qa_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_overlay_coordinate_qa_20260703_174930.csv`
- geometry_debug_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_overlay_case_geometry_debug_20260703_174930.csv`
- chinese_review_card_index_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_chinese_review_card_index_20260703_174930.csv`
- qa_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_overlay_visualization_qa_report_20260703_174930.md`
- qa_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_overlay_visualization_qa_summary_20260703_174930.json`
- chinese_atlas_html: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_gt_support_energy_overlay_atlas_cn_20260703_174930.html`
- workspace_log: `D:\profile\research\workspace\logs\oty2_support_overlay_visualization_qa_and_chinese_review_atlas_20260703_174930.log`
