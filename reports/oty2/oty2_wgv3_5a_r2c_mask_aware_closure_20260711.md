# OTY2 WGV3.5A-R2C Closure

Closure status: `OPEN_GM19_SAR_MASK_CENTER_SUPERVISION_INSUFFICIENT`

## Freeze Manifest

|source_file|sha256|bytes|rows|frozen_scope|
|---|---|---|---|---|
|reports\oty2\oty2_wgv3_5a_r1_closure_20260710.md|a1e8ea691d5a4ce77af94c889a5f25793ae87cea3fd31f0f191d020649523163|11085||R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\oty2_wgv3_5a_r2_gm019_closure_20260710.md|7584cfbe78d392446adcc34f313c7bef2b5e99dd7c947f0a0b5a69f5d4ec19c1|7199||R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\oty2_wgv3_5a_r2b_gm019_closure_20260710.md|faf03244e298a08e1f188ca373ab0bef1361f514a81755b27db55777a636ab7a|8905||R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\oty2_wgv3_5a_r2b_gm019_full_stream_anchor_reaudit_20260710.md|3491863d3558361d456a44cb415b64139dd3f019126fe2b1cd9668d079342d57|30489||R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\oty2_wgv3_5a_r2b_gm019_anchorless_reconstruction_method_20260710.md|3a6fa418df6c1b10afa21cc5c84f4b38d98d0612dd8792ae7ba456483911faa3|19379||R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\oty2_wgv3_5a_r2b_gm019_visual_diagnosis_20260710.md|61cfbde4c60844ddb5c6afbd382d69e7ede4e4a1ff8f33dda60fd9c75882fbe1|3383||R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\samples\oty2_wgv3_5a_r2b_gm019_projection_evaluation_rows_20260710.csv|f48753fe33dbf83f7d2a04c1643cb556706a3482e6e1970cb7e2e5965aa93d4b|19917|112|R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\samples\oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_20260710.csv|1e3a6eecb79a306a81b4dc0937b3282afb30d4864f29d9e56a4da74949872e9b|37239|173|R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\samples\oty2_wgv3_5a_r2b_gm019_optical_recovery_anchors_20260710.csv|3d227bd90b13c68e8730052dbcb55a9373c294ef82364d06e3982492db27984b|25422|173|R1/R2/R2B historical output; R2C reads only and does not overwrite|
|reports\oty2\samples\oty2_wgv3_5a_r2b_gm019_sar_scene_calibration_anchors_20260710.csv|eda969462c03faf7028097489c06b398bbbec3a394bd9073a278d7bf319b66fc|2093|16|R1/R2/R2B historical output; R2C reads only and does not overwrite|

## Mask Audit Counts

- total GM_RM019 pairs: `16`
- S0: `0`
- S1: `11`
- S2: `5`
- S3: `0`
- vehicles affected by mask semantics: `5` (PV_GM19_BLACK_SEDAN_NEAR_FIELD;PV_GM19_GRAY_CAR_LEFT_EDGE;PV_GM19_RIGHT_DARK_FRAGMENT;PV_GM19_SILVER_MPV_NEAR_FIELD;PV_GM19_WHITE_SUV_NEAR_FIELD)

## R2B Correction

- R2B GM17 anchorless controlled-pass evidence is not retained because it leaked the synthetic crop ratio/full-frame relation.
- R2C leakage-free L2 pass: `true`.
- R2B GM19 radial improvement remains visible in R2B rows, but R2C treats it as optical-state/radial evidence only, not as complete SAR center success.

## Dimension Split

|method|mask_class|sample_count|physical_vehicle_count|azimuth_median_error|azimuth_p90_error|radial_median_error|radial_p90_error|azimuth_covered_count|radial_covered_count|joint_covered_count|masked_overlap_covered_count|blocked_count|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|Z0_local_detection_box|SAR_MASK_S0_FULLY_OBSERVABLE|0|0|||||0|0|0|0|0|
|Z0_local_detection_box|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|11|4|14.231054|18.246886|88.233313|344.745556|1|2|0|5|0|
|Z0_local_detection_box|SAR_MASK_S2_CENTER_CENSORED|5|4|13.909872|18.209781|210.075718|250.347321|0|0|0|0|0|
|Z0_local_detection_box|SAR_MASK_S3_NOT_CENTER_SUPERVISABLE|0|0|||||0|0|0|0|0|
|Z1A_full_stream_optical_anchor_recovery|SAR_MASK_S0_FULLY_OBSERVABLE|0|0|||||0|0|0|0|0|
|Z1A_full_stream_optical_anchor_recovery|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|6|2|23.793916|31.554096|54.884142|75.316185|1|1|0|2|5|
|Z1A_full_stream_optical_anchor_recovery|SAR_MASK_S2_CENTER_CENSORED|1|1|35.144045|35.144045|73.559407|73.559407|0|0|0|0|4|
|Z1A_full_stream_optical_anchor_recovery|SAR_MASK_S3_NOT_CENTER_SUPERVISABLE|0|0|||||0|0|0|0|0|
|Z1B_anchorless_track_level_completion|SAR_MASK_S0_FULLY_OBSERVABLE|0|0|||||0|0|0|0|0|
|Z1B_anchorless_track_level_completion|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|10|3|11.603518|19.66768|17.737955|132.053736|1|8|1|5|1|
|Z1B_anchorless_track_level_completion|SAR_MASK_S2_CENTER_CENSORED|5|4|11.647201|16.393768|66.616316|117.02756|0|1|0|3|0|
|Z1B_anchorless_track_level_completion|SAR_MASK_S3_NOT_CENTER_SUPERVISABLE|0|0|||||0|0|0|0|0|

## Bearing Audit

|physical_vehicle_id|mask_class|mapping_monotonic|offset_pattern|scale_pattern|depth_dependence|phase_dependence|mask_boundary_dependence|center_semantic_risk|recommended_bearing_proxy|audit_status|
|---|---|---|---|---|---|---|---|---|---|---|
|PV_GM19_BLACK_SEDAN_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE;SAR_MASK_S2_CENTER_CENSORED|not_evaluated_due_M2_gate|azimuth residual remains after radial recovery; cannot separate from mask-biased center|not_fitted|not_fitted|trajectory_phase_visible_but_center_supervision_blocked|all paired samples near lower fan/mask boundary|high|none_until_S0_or_high_confidence_center_semantics_exist|GATED_R2C_M2_CENTER_SUPERVISION_INSUFFICIENT|
|PV_GM19_GRAY_CAR_LEFT_EDGE|SAR_MASK_S2_CENTER_CENSORED|not_evaluated_due_M2_gate|azimuth residual remains after radial recovery; cannot separate from mask-biased center|not_fitted|not_fitted|trajectory_phase_visible_but_center_supervision_blocked|all paired samples near lower fan/mask boundary|high|none_until_S0_or_high_confidence_center_semantics_exist|GATED_R2C_M2_CENTER_SUPERVISION_INSUFFICIENT|
|PV_GM19_RIGHT_DARK_FRAGMENT|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|not_evaluated_due_M2_gate|azimuth residual remains after radial recovery; cannot separate from mask-biased center|not_fitted|not_fitted|trajectory_phase_visible_but_center_supervision_blocked|all paired samples near lower fan/mask boundary|high|none_until_S0_or_high_confidence_center_semantics_exist|GATED_R2C_M2_CENTER_SUPERVISION_INSUFFICIENT|
|PV_GM19_SILVER_MPV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE;SAR_MASK_S2_CENTER_CENSORED|not_evaluated_due_M2_gate|azimuth residual remains after radial recovery; cannot separate from mask-biased center|not_fitted|not_fitted|trajectory_phase_visible_but_center_supervision_blocked|all paired samples near lower fan/mask boundary|high|none_until_S0_or_high_confidence_center_semantics_exist|GATED_R2C_M2_CENTER_SUPERVISION_INSUFFICIENT|
|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE;SAR_MASK_S2_CENTER_CENSORED|not_evaluated_due_M2_gate|azimuth residual remains after radial recovery; cannot separate from mask-biased center|not_fitted|not_fitted|trajectory_phase_visible_but_center_supervision_blocked|all paired samples near lower fan/mask boundary|high|none_until_S0_or_high_confidence_center_semantics_exist|GATED_R2C_M2_CENTER_SUPERVISION_INSUFFICIENT|

## Model Comparison

|model_id|model_name|training_mask_classes|training_sample_count|training_physical_vehicle_count|selected_model|azimuth_median_error|azimuth_p90_error|radial_median_error|radial_p90_error|center_coverage|run_status|blocked_reason|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|A0|GM17_frozen_model|none|0|0|false|||||0/0|not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|
|A1|GM19_scene_linear_model|none|0|0|false|||||0/0|not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|
|A2|depth_conditioned_model|none|0|0|false|||||0/0|not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|
|A3|vehicle_boundary_conditioned_model|none|0|0|false|||||0/0|not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|
|A4|mask_distance_conditioned_model|none|0|0|false|||||0/0|not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|
|A5|monotone_piecewise_model|none|0|0|false|||||0/0|not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|

## Leave-One Vehicle Out

|fold_id|train_physical_vehicles|test_physical_vehicle|train_S0_count|train_S1_count|test_S0_count|test_S1_count|test_S2_count|selected_model|azimuth_median|azimuth_p90|radial_median|radial_p90|azimuth_coverage|radial_coverage|joint_coverage|masked_overlap_coverage|search_ratio|run_status|blocked_reason|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|LOVO_PV_GM19_WHITE_SUV_NEAR_FIELD|not_constructed|PV_GM19_WHITE_SUV_NEAR_FIELD|0|0|0|3|1|none|||||0/0|0/0|0/0|not_evaluated||not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|
|LOVO_PV_GM19_SILVER_MPV_NEAR_FIELD|not_constructed|PV_GM19_SILVER_MPV_NEAR_FIELD|0|0|0|5|1|none|||||0/0|0/0|0/0|not_evaluated||not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|
|LOVO_PV_GM19_GRAY_CAR_LEFT_EDGE|not_constructed|PV_GM19_GRAY_CAR_LEFT_EDGE|0|0|0|0|2|none|||||0/0|0/0|0/0|not_evaluated||not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|

## Mask-Aware Intervals

|interval_group|training_count|azimuth_q50|azimuth_q80|azimuth_q95|radial_q50|radial_q80|radial_q95|held_out_center_coverage|held_out_masked_overlap_coverage|search_ratio|run_status|blocked_reason|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|M2_GATED_NO_CENTER_SUPERVISION|0|||||||0/0|not_evaluated||not_run_M2_gate_failed|S0完整中心监督为0；S1仅能作为区间/相交弱证据，不能支持跨物理车辆方位中心拟合。|

## Failure Cases

|pair_id|physical_vehicle_id|mask_class|method|primary_failure_source|azimuth_error|radial_error|blocked_reason|review_cn|
|---|---|---|---|---|---|---|---|---|
|WGV35A_PAIR_0200|PV_GM19_BLACK_SEDAN_NEAR_FIELD|SAR_MASK_S2_CENTER_CENSORED|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|10.556022|135.920695|center_semantics_mask_censored_or_unconfirmed;R2B_recovered_full_state_projects_outside_reconstructed_mask|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0201|PV_GM19_BLACK_SEDAN_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|7.256916|134.249264|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0202|PV_GM19_BLACK_SEDAN_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|2.460619|131.809789|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0204|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|8.561238|3.259652|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0205|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|10.689937|20.151251|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0206|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|19.653348|12.944215|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0207|PV_GM19_WHITE_SUV_NEAR_FIELD|SAR_MASK_S2_CENTER_CENSORED|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|18.911311|20.427984|center_semantics_mask_censored_or_unconfirmed;sar_bbox_partly_outside_reconstructed_mask|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0208|PV_GM19_SILVER_MPV_NEAR_FIELD|SAR_MASK_S2_CENTER_CENSORED|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|11.647201|88.687858|center_semantics_mask_censored_or_unconfirmed;sar_bbox_partly_outside_reconstructed_mask|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0209|PV_GM19_SILVER_MPV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|0.682829|15.324659|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0210|PV_GM19_SILVER_MPV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|19.796665|24.71664|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0211|PV_GM19_SILVER_MPV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|19.643154|25.451178|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0212|PV_GM19_SILVER_MPV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|13.069722|13.678981|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0213|PV_GM19_SILVER_MPV_NEAR_FIELD|SAR_MASK_S1_PARTIALLY_CENSORED_CENTER_INSIDE|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|12.517098|15.182525|center_semantics_mask_censored_or_unconfirmed;bbox_bottom_within_110px_of_near_range_mask;observed_box_may_be_masked_response_center_not_full_vehicle_center|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0214|PV_GM19_GRAY_CAR_LEFT_EDGE|SAR_MASK_S2_CENTER_CENSORED|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|12.617453|66.616316|center_semantics_mask_censored_or_unconfirmed;sar_bbox_partly_outside_reconstructed_mask|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|
|WGV35A_PAIR_0215|PV_GM19_GRAY_CAR_LEFT_EDGE|SAR_MASK_S2_CENTER_CENSORED|Z1B_anchorless_track_level_completion|sar_mask_center_semantic_risk|10.857901|55.934478|center_semantics_mask_censored_or_unconfirmed;sar_bbox_partly_outside_reconstructed_mask|该样本不能把Z1B预测中心直接与mask内SAR框中心比较；需先做mask求交/区间语义评价。|

## Boundary Checks

- No GT or manual annotations were modified.
- No final SAR boxes were emitted.
- No full-SAR bright-response search was performed; SAR response checks were local to paired boxes.
- No YOLO training or full MOT rerun was performed.
- GM_RM011 R3 and unified R4 frontend were not executed.
- S2/S3 and S1 weak-only rows were not used for full-center model fitting.
- Held-out/test SAR labels were not used to tune optical recovery.

## Created Files

- `reports\oty2\samples\oty2_wgv3_5a_r2c_freeze_manifest_20260711.csv`
- `reports\oty2\oty2_wgv3_5a_r2c_sar_mask_definition_20260711.md`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_sar_mask_source_inventory_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv`
- `reports\oty2\oty2_wgv3_5a_r2c_gm019_mask_supervision_gate_20260711.md`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm17_hidden_degraded_inputs_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm17_scoring_truth_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm17_leakage_free_results_20260711.csv`
- `reports\oty2\oty2_wgv3_5a_r2c_gm17_leakage_free_control_20260711.md`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_optical_state_review_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_dimension_split_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_bearing_relation_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_center_semantic_review_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_model_comparison_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_leave_one_vehicle_out_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_mask_aware_intervals_20260711.csv`
- `reports\oty2\samples\oty2_wgv3_5a_r2c_gm019_failure_cases_20260711.csv`
- `reports\oty2\oty2_wgv3_5a_r2c_mask_aware_visual_diagnosis_20260711.md`
- `reports\oty2\oty2_wgv3_5a_r2c_mask_aware_closure_20260711.md`