# OTY2 Corrected GT-Local Energy-Field Atlas Report

Generated: `20260704_145752`

This report marks the previous physical shell grammar atlas as failed visualization and replaces it with a GT-local energy-field atlas. The corrected atlas uses the SAR GT crop as the primary coordinate frame.

## Failed Visualization Mark

- failed artifact: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_physical_shell_grammar_temporal_drift_atlas_cn_20260704_143456.html`
- status: `failed_visualization`
- reason: the previous atlas still visualized support-internal peaks/components and small component boxes, so it could still imply baby-car shells.
- do not use as: vehicle shell evidence, selector evidence, final box evidence, or identity truth.

## Corrected GT-Local Atlas

- atlas panels generated: `18`
- feature rows: `18`
- ridge-like band mix: `lower=9;upper=8;right=1`
- weak opposite-side return mix: `uncertain=15;yes=3`
- vehicle-scale shell contour mix: `yes=16;uncertain=2`
- endpoint hotspot count mix: `6=8;5=5;0=2;1=1;2=1;4=1`

The corrected atlas displays only GT-local energy cues: ridge-like energy bands, endpoint hotspots, weak opposite-side returns, boundary occupancy, and energy-field contours inside GT.

## Visualization Contract

- GT crop is the primary coordinate frame.
- No support boundary is drawn.
- No support-internal component outside GT is drawn as a vehicle part.
- No small component box is drawn as shell.
- Vehicle-scale shell contour is an energy-field contour inside GT, not a component box and not a final box.

## Boundary Flags

- previous_physical_atlas_marked_failed: `true`
- gt_local_energy_field_atlas_generated: `true`
- gt_crop_primary_coordinate_frame: `true`
- support_internal_components_drawn_as_vehicle_parts: `false`
- small_component_boxes_drawn_as_shell: `false`
- support_boundary_drawn: `false`
- posthoc_sar_gt_used: `true`
- posthoc_sar_image_content_used: `true`
- annotation_proposal_entered: `false`
- revised_gt_box_output: `false`
- final_candidate_box_output: `false`
- selector_or_ranking_used: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- gt_or_sar_image_used_for_runtime_prior_construction: `false`
- archive_or_old_work_used_as_active_source: `false`
- zip_7z_rar_committed: `false`

## Outputs

- correction_archive_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_gt_local_energy_field_atlas_correction_archive.md`
- failed_visualization_correction_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_failed_visualization_correction_20260704_145752.csv`
- gt_local_energy_field_features_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_local_energy_field_features_20260704_145752.csv`
- report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_local_energy_field_atlas_report_20260704_145752.md`
- summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_local_energy_field_atlas_summary_20260704_145752.json`
- visual_atlas_html: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\visual_exemplars\oty2_gt_local_energy_field_atlas_cn_20260704_145752.html`
- workspace_log: `D:\profile\research\workspace\logs\oty2_gt_local_energy_field_atlas_20260704_145752.log`
