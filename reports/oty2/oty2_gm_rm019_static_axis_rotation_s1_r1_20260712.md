# GM_RM019 S1-R1 static axis rotation semantic integrity

Status: `S1_R1_SEMANTIC_INTEGRITY_READY`

S2_READINESS=`READY`

OTY2 (Optical Timeline Y2, 光学时序辅助阶段二) / SAR (Synthetic Aperture Radar, 合成孔径雷达) / GT (Ground Truth, 真值) boundary: this round repairs S1 static semantics only. It does not execute S2 GT-region evaluation.

## Existing final_heading semantics confirmed

- `docs/guidance/algorithm_spec_full.md` states that `heading`, `final_heading`, `w`, and `h` are storage-axis or display-XY box conventions, not literal vehicle heading, width, or length.
- `src/geometry/fan_polar.py` says heading values carried by candidate rows are display-XY storage axes and are not physical vehicle heading.
- `src/visualization/svg_canvas.py` draws `heading_deg` as the width-axis vector of a rotated rectangle.
- Therefore `final_heading_deg` is the stored `final_w` axis in SAR image coordinates, not vehicle yaw, not the GT long axis by default, and not the gray-response principal axis.

## Unified angle semantics

|field|meaning|range|
|---|---|---|
|response_axis_image_deg|undirected SAR gray covariance major axis in image coordinates|[0,180)|
|response_axis_to_range_signed_deg|signed undirected axis angle relative to local radar range vector|[-90,90)|
|response_axis_to_range_acute_deg|absolute range-relative axis angle|[0,90]|
|response_axis_to_azimuth_acute_deg|absolute azimuth-relative axis angle|[0,90]|
|aspect_angle_candidate_deg|hypothetical vehicle projection long-axis angle relative to local range|[0,90]|

The response principal axis is an undirected energy axis. It lacks vehicle nose direction, cannot distinguish 0 degrees from 180 degrees, can be local-part or multi-component driven, and therefore is not vehicle yaw.

## Core statistics

- response unit level: `250`; independent geometry level: `215`.
- duplicate geometries are keyed by the frozen S1 conservative response geometry (`conservative_bbox`) to match the 215 independent-geometry baseline; member SAR frames and response units are retained as provenance, and each independent geometry is measured once before mapping back to members.
- signed axis stats: `{'count': '215', 'mean': '14.723243', 'median': '35.365093', 'min': '-88.598804', 'max': '89.454371'}`.
- acute axis stats: `{'count': '215', 'mean': '55.159369', 'median': '61.597483', 'min': '0.073471', 'max': '89.454371'}`.
- axis_orientation_status: `AXIS_MULTI_COMPONENT_AMBIGUOUS=134; AXIS_NEAR_ISOTROPIC=81`.
- vehicle_projection_envelope_status: `PARTIAL_SUPPORT_BELOW_ENVELOPE=146; WITHIN_VEHICLE_PROJECTION_ENVELOPE=69`.
- aspect_angle_identifiability_status: `AXIS_NOT_RESOLVED=215`.
- required_missing_support_range_m: `{'count': '215', 'mean': '0.729738', 'median': '0.677843', 'min': '0', 'max': '2.850072'}`.
- required_missing_support_azimuth_m: `{'count': '215', 'mean': '1.195864', 'median': '1.002497', 'min': '0', 'max': '2.787108'}`.
- required_extra_spread_range_m: `{'count': '215', 'mean': '0.000188', 'median': '0', 'min': '0', 'max': '0.012378'}`.
- required_extra_spread_azimuth_m: `{'count': '215', 'mean': '0.000242', 'median': '0', 'min': '0', 'max': '0.010919'}`.
- threshold component identity transitions: `COMPONENT_IDENTITY_SWITCH=158; COMPONENT_SPLIT_OR_MERGE=54; COMPONENT_TOO_SMALL=4; SAME_COMPONENT_PERSISTENT=214`.
- counterfactual family counts: `center_shift=2580; local_region_rotation=1935; scale_resize=1720; single_boundary_shift=3440`.
- proxy formula result rows: `0`.

## Synthetic semantic tests

- `axis_45_vs_135_not_collapsed`: PASS
- `axis_v_and_minus_v_equivalent`: PASS
- `rotation_180_equivalent_to_0`: PASS
- `rotation_90_long_short_swap_recorded`: PASS

## No resolved stable-axis samples observed; lowest-complement audit samples

|independent_geometry_id|response_unit_id|sar_frame|response_axis_image_deg|response_axis_to_range_signed_deg|response_axis_to_range_acute_deg|axis_orientation_status|
|---|---|---|---|---|---|---|
|GM019IG0001|R21B00042|34|171.631075|-50.868089|50.868089|AXIS_MULTI_COMPONENT_AMBIGUOUS|
|GM019IG0002|R21B00105|212|119.037065|65.607673|65.607673|AXIS_NEAR_ISOTROPIC|
|GM019IG0003|R21B00109|213|114.023098|71.24996|71.24996|AXIS_NEAR_ISOTROPIC|
|GM019IG0004|R21B00112|216|118.173241|62.556369|62.556369|AXIS_NEAR_ISOTROPIC|
|GM019IG0005|R21B00108|213|139.387741|82.83526|82.83526|AXIS_NEAR_ISOTROPIC|

## Typical ambiguous-axis samples

|independent_geometry_id|response_unit_id|sar_frame|principal_axis_ratio|measured_component_count|axis_orientation_status|threshold_component_identity_status|
|---|---|---|---|---|---|---|
|GM019IG0001|R21B00042|34|2.011435|32|AXIS_MULTI_COMPONENT_AMBIGUOUS|SAME_COMPONENT_PERSISTENT|
|GM019IG0002|R21B00105|212|1.112766|971|AXIS_NEAR_ISOTROPIC|COMPONENT_IDENTITY_SWITCH|
|GM019IG0003|R21B00109|213|1.081945|18|AXIS_NEAR_ISOTROPIC|SAME_COMPONENT_PERSISTENT|
|GM019IG0004|R21B00112|216|1.08735|737|AXIS_NEAR_ISOTROPIC|COMPONENT_SPLIT_OR_MERGE|
|GM019IG0005|R21B00108|213|1.197245|806|AXIS_NEAR_ISOTROPIC|COMPONENT_IDENTITY_SWITCH|

## Typical rotation-sensitive samples

|template_id|independent_geometry_id|sar_frame|rotation_deg|energy_delta_measured|axis_angle_delta_deg_measured|measured_axis_orientation_status|
|---|---|---|---|---|---|---|
|GM019IG0094_T45|GM019IG0094|270|90|12424|89.780173|AXIS_MULTI_COMPONENT_AMBIGUOUS|
|GM019IG0029_T45|GM019IG0029|27|90|1822|89.205719|AXIS_NEAR_ISOTROPIC|
|GM019IG0099_T45|GM019IG0099|34|90|-22572|89.11327|AXIS_NEAR_ISOTROPIC|
|GM019IG0189_T37|GM019IG0189|276|-30|-992|88.484315|AXIS_NEAR_ISOTROPIC|
|GM019IG0004_T37|GM019IG0004|216|-30|23272|88.276025|AXIS_NEAR_ISOTROPIC|

## Typical rotation-insensitive samples

|template_id|independent_geometry_id|sar_frame|rotation_deg|energy_delta_measured|axis_angle_delta_deg_measured|measured_axis_orientation_status|
|---|---|---|---|---|---|---|
|GM019IG0027_T45|GM019IG0027|27|90|0|0|AXIS_MULTI_COMPONENT_AMBIGUOUS|
|GM019IG0043_T45|GM019IG0043|31|90|0|0|AXIS_NEAR_ISOTROPIC|
|GM019IG0054_T45|GM019IG0054|238|90|0|0|AXIS_NEAR_ISOTROPIC|
|GM019IG0056_T45|GM019IG0056|31|90|0|0|AXIS_NEAR_ISOTROPIC|
|GM019IG0057_T45|GM019IG0057|30|90|0|0|AXIS_NEAR_ISOTROPIC|

## Visual review package

|visual_case_id|review_label|independent_geometry_id|response_unit_id|sar_frame|visual_relpath|opened_for_review|
|---|---|---|---|---|---|---|
|VR01|axis_image_about_45|GM019IG0164|R21B00142|250|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/01_axis_image_about_45_GM019IG0164.png|pending_manual_open|
|VR02|axis_image_about_135|GM019IG0036|R21B00015|29|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/02_axis_image_about_135_GM019IG0036.png|pending_manual_open|
|VR03|near_range_axis|GM019IG0101|R21B00061|40|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/03_near_range_axis_GM019IG0101.png|pending_manual_open|
|VR04|near_azimuth_axis|GM019IG0199|R21B00171|270|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/04_near_azimuth_axis_GM019IG0199.png|pending_manual_open|
|VR05|near_isotropic|GM019IG0166|R21B00093|80|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/05_near_isotropic_GM019IG0166.png|pending_manual_open|
|VR06|multi_component|GM019IG0001|R21B00042|34|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/06_multi_component_GM019IG0001.png|pending_manual_open|
|VR07|threshold_identity_switch|GM019IG0002|R21B00105|212|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/07_threshold_identity_switch_GM019IG0002.png|pending_manual_open|
|VR08|rotation_sensitive|GM019IG0094|R21B00167|270|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/08_rotation_sensitive_GM019IG0094.png|pending_manual_open|
|VR09|rotation_insensitive|GM019IG0182|R21B00082|78|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/09_rotation_insensitive_GM019IG0182.png|pending_manual_open|
|VR10|no_exceeds_envelope_observed_max_extra_spread|GM019IG0096|R21B00174|270|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/10_no_exceeds_envelope_observed_max_extra_spread_GM019IG0096.png|pending_manual_open|
|VR11|partial_support_below_envelope|GM019IG0003|R21B00109|213|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/11_partial_support_below_envelope_GM019IG0003.png|pending_manual_open|
|VR12|duplicate_independent_geometry|GM019IG0041|R21B00024|31|outputs/oty2_gm_rm019_s1_r1_axis_rotation_20260712/visual_review/12_duplicate_independent_geometry_GM019IG0041.png|pending_manual_open|

## Integrity gates

|gate_name|status|detail|source_file|sha256|row_count|
|---|---|---|---|---|---|
|PROJECT_CONFIRMED_CALIBRATION_APPLIED|PASS|PROJECT_CONFIRMED constants applied|reports/oty2/samples/oty2_gm_rm019_s1_r1_axis_observations_20260712.csv|17aa557e3a5c13e6d96a494c3a42a4250facaa9839fc551897737c518000eea2|215|
|GT_NOT_READ_DURING_GENERATION|PASS|gt_file_opened=false||||
|PAIRED_ANNOTATIONS_NOT_READ_DURING_GENERATION|PASS|paired_annotations_opened=false||||
|MASK_AUDIT_NOT_READ_DURING_GENERATION|PASS|mask_audit_opened=false||||
|RAW_EIGENVECTOR_USED_FOR_RELATIVE_AXIS|PASS|raw eigenvector canonical line stored before relative angle||||
|IMAGE_AXIS_RANGE_IS_0_180|PASS|image_axis_count=215||||
|SIGNED_AXIS_RANGE_IS_MINUS90_TO90|PASS|signed_axis_count=215||||
|ACUTE_AXIS_RANGE_IS_0_TO90|PASS|acute_axis_count=215||||
|RANGE_AZIMUTH_ACUTE_COMPLEMENT_VALID|PASS|max_error=0||||
|NEAR_ISOTROPIC_AXIS_NOT_OVERINTERPRETED|PASS|near-isotropic rows have explicit status||||
|YAW_TERM_REMOVED_FROM_STATIC_OUTPUT|PASS|static S1-R1 fields use aspect angle, not yaw||||
|ASPECT_ANGLE_RANGE_IS_0_TO90|PASS|aspect_count=215||||
|VEHICLE_SCALE_USED_AS_ENVELOPE_NOT_EXACT_TARGET|PASS|vehicle scale note records envelope semantics||||
|MISSING_SUPPORT_AND_EXTRA_SPREAD_SEPARATED|PASS|missing support and extra spread columns present||||
|THRESHOLD_COMPONENT_IDENTITY_TRACKED|PASS|component_rows=645 transition_rows=430||||
|COUNTERFACTUALS_REMEASURE_REAL_SAR|PASS|measurement_rows=9675 expected=9675||||
|NO_PROXY_COUNTERFACTUAL_DELTA_FIELDS_USED_AS_RESULT|PASS|proxy_formula_used=false for all rows||||
|ROTATION_COUNTERFACTUALS_PRESENT|PASS|rotation measurements present||||
|INDEPENDENT_GEOMETRY_DEDUP_VALID|PASS|response_unit_level=250 independent_geometry_level=215||||
|FROZEN_REPLAY_IDENTICAL|PASS|replay_rows=10||||
|NO_SELECTOR_OUTPUT|PASS|no selector/ranking output names||||
|NO_FINAL_BOX_OUTPUT|PASS|no final-box/runtime output names||||
|S2_GT_EVALUATION_NOT_EXECUTED|PASS|S2 not executed; forbidden status terms absent||||
|axis_45_vs_135_not_collapsed|PASS|synthetic angle test passed||||
|axis_v_and_minus_v_equivalent|PASS|synthetic axis sign equivalence passed||||
|rotation_180_equivalent_to_0|PASS|synthetic 180 equivalence passed||||
|rotation_90_long_short_swap_recorded|PASS|synthetic projection swap passed||||
|VISUAL_REVIEW_PACKAGE_READY|PASS|visual_rows=12; files under outputs/||||

## Outputs

- `reports/oty2/samples/oty2_gm_rm019_s1_r1_axis_observations_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_threshold_components_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_threshold_component_transitions_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_vehicle_projection_envelope_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_counterfactual_specs_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_counterfactual_measurements_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_independent_geometry_map_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_semantic_failures_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_pre_eval_seal_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_replay_check_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_visual_manifest_20260712.csv`
- `reports/oty2/samples/oty2_gm_rm019_s1_r1_integrity_20260712.csv`
- `reports/oty2/oty2_gm_rm019_static_axis_rotation_s1_r1_20260712.md`

## S2 boundary

S2 may open paired annotations, response-unit GT instance matrices, and mask-observation audit tables only after this S1-R1 package is frozen. This round did not perform GT region ranking, GT boundary fitting, final-box generation, selector/ranking construction, GT modification, or GM_RM017 modification.
