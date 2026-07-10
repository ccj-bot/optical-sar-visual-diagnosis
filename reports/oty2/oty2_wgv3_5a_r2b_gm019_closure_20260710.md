# OTY2 WGV3.5A-R2B GM_RM019 Closure

Date: 20260710

R2B status: `OPEN_R2B_FULL_STREAM_RECOVERY_FOUND_SAR_PROJECTION_INSUFFICIENT`

## Stage Result

- full-stream direct optical anchors: `22`
- paired-row direct anchors: `0`
- usable SAR scene calibration anchors: `9`
- R2 remains valid as paired-row-only anchor audit; R2B expands the optical-stream search and separates recovery anchors from SAR calibration anchors.

## Projection Comparison

| evaluation_group | method | scene_anchor_plan | sample_count | physical_vehicle_count | azimuth_median_error | azimuth_p90_error | radial_median_error | radial_p90_error | center_coverage_50 | center_coverage_80 | center_coverage_95 | full_box_coverage_95 | median_search_ratio | p90_search_ratio | blocked_rate | wrong_identity_rate | raw_counts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| paired-row direct local observation | Z0_local_detection_box | A0 | 16 | 5 | 14.070463 | 19.28879 | 170.52959 | 311.659159 | 0/16 | 0/16 | 0/16 | 0/16 | 0.00107227 | 0.00107227 | 0 | 0 | unblocked=16;blocked=0 |
| full-stream optical-anchor recovery | Z1A_full_stream_optical_anchor_recovery | A0 | 7 | 2 | 28.737847 | 33.247506 | 71.855407 | 75.119085 | 0/7 | 0/7 | 0/7 | 0/7 | 0.00107227 | 0.00107227 | 0.5625 | 0 | unblocked=7;blocked=9 |
| anchorless track-level recovery | Z1B_anchorless_track_level_completion | A0 | 15 | 4 | 11.647201 | 19.64927 | 24.71664 | 133.273474 | 1/15 | 1/15 | 1/15 | 0/15 | 0.00107227 | 0.00107227 | 0.0625 | 0 | unblocked=15;blocked=1 |
| recovery plus scene calibration | Z2_recovery_plus_scene_residual_calibration | A0 | 15 | 4 | 12.617453 | 25.104047 | 55.934478 | 133.273474 | 0/15 | 0/15 | 0/15 | 0/15 | 0.00107227 | 0.00107227 | 0.0625 | 0 | unblocked=15;blocked=1 |
| recovery plus scene calibration | Z2_recovery_plus_scene_residual_calibration | A1 | 14 | 4 | 14.560992 | 27.983262 | 99.188274 | 171.430298 | 0/14 | 0/14 | 0/14 | 0/14 | 0.00107227 | 0.00107227 | 0.125 | 0 | unblocked=14;blocked=2 |
| recovery plus scene calibration | Z2_recovery_plus_scene_residual_calibration | A3 | 12 | 4 | 22.212065 | 38.466169 | 49.023687 | 80.542033 | 0/12 | 1/12 | 1/12 | 0/12 | 0.00107227 | 0.00107227 | 0.25 | 0 | unblocked=12;blocked=4 |
| recovery plus scene calibration | Z2_recovery_plus_scene_residual_calibration | A5 | 10 | 4 | 8.961071 | 18.384847 | 26.421373 | 62.404861 | 1/10 | 1/10 | 1/10 | 0/10 | 0.00107227 | 0.00107227 | 0.375 | 0 | unblocked=10;blocked=6 |

## Failure Source Split

- primary failure counts: `{'scene_radial_residual': 10, 'identity_unresolved': 1, 'scene_azimuth_residual': 5}`
| pair_id | physical_vehicle_id | method | primary_failure | no_full_anchor_in_paired_rows | no_full_anchor_in_full_optical_stream | anchorless_completion_failure | identity_unresolved | insufficient_temporal_extent | one_sided_observation_only | local_center_bias | depth_background_contamination | relative_depth_scale_shift | scene_azimuth_residual | scene_radial_residual | near_field_parallax | SAR_pairing_suspect | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WGV35A_PAIR_0200 | PV_GM19_BLACK_SEDAN_NEAR_FIELD | Z2_A0_best_recovered_state | scene_radial_residual | true | true | false | true | false | true | true | true | true | true | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0201 | PV_GM19_BLACK_SEDAN_NEAR_FIELD | Z2_A0_best_recovered_state | scene_radial_residual | true | true | false | true | false | true | true | true | true | true | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0202 | PV_GM19_BLACK_SEDAN_NEAR_FIELD | Z2_A0_best_recovered_state | scene_radial_residual | true | true | false | true | false | true | true | true | true | true | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0203 | PV_GM19_RIGHT_DARK_FRAGMENT | Z2_A0_best_recovered_state | identity_unresolved | true | true | true | true | true | true | true | true | true | false | false | true | true | missing_state |
| WGV35A_PAIR_0204 | PV_GM19_WHITE_SUV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_azimuth_residual | true | false | false | false | false | false | true | true | true | true | false | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0205 | PV_GM19_WHITE_SUV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_radial_residual | true | false | false | false | false | false | true | true | true | true | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0206 | PV_GM19_WHITE_SUV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_azimuth_residual | true | false | false | false | false | false | true | true | true | true | false | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0207 | PV_GM19_WHITE_SUV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_azimuth_residual | true | false | false | false | false | false | true | true | true | true | false | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0208 | PV_GM19_SILVER_MPV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_radial_residual | true | false | false | false | false | false | true | true | true | true | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0209 | PV_GM19_SILVER_MPV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_radial_residual | true | false | false | false | false | false | true | true | true | false | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0210 | PV_GM19_SILVER_MPV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_radial_residual | true | false | false | false | false | false | true | true | true | true | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0211 | PV_GM19_SILVER_MPV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_radial_residual | true | false | false | false | false | false | true | true | true | true | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0212 | PV_GM19_SILVER_MPV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_azimuth_residual | true | false | false | false | false | false | true | true | true | true | false | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0213 | PV_GM19_SILVER_MPV_NEAR_FIELD | Z2_A0_best_recovered_state | scene_azimuth_residual | true | false | false | false | false | false | true | true | true | true | false | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0214 | PV_GM19_GRAY_CAR_LEFT_EDGE | Z2_A0_best_recovered_state | scene_radial_residual | true | false | false | false | false | false | true | true | true | true | true | true | false | failure source split after full-stream recovery |
| WGV35A_PAIR_0215 | PV_GM19_GRAY_CAR_LEFT_EDGE | Z2_A0_best_recovered_state | scene_radial_residual | true | false | false | false | false | false | true | true | true | true | true | true | false | failure source split after full-stream recovery |

## Boundary Confirmation

- No GT/manual annotation was modified.
- No final SAR boxes were emitted.
- No full-SAR bright-response search, YOLO training, full MOT rerun, GM_RM011 R3, or R4 frontend execution was performed.
- SAR annotation is used only for held-out projection evaluation and scene residual experiments, never to recover unpaired optical states.

## Created Files

- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_freeze_manifest_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_full_stream_source_inventory_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_physical_vehicle_timeline_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_direct_observable_full_stream_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_optical_recovery_anchors_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_sar_scene_calibration_anchors_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_branch_a_anchor_recovery_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm017_anchorless_ablation_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_projection_comparison_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_projection_evaluation_rows_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_5a_r2b_gm019_failure_cases_20260710.csv`
- `reports/oty2/oty2_wgv3_5a_r2b_gm019_full_stream_anchor_reaudit_20260710.md`
- `reports/oty2/oty2_wgv3_5a_r2b_gm019_anchorless_reconstruction_method_20260710.md`
- `reports/oty2/oty2_wgv3_5a_r2b_gm019_visual_diagnosis_20260710.md`
- `reports/oty2/oty2_wgv3_5a_r2b_gm019_closure_20260710.md`
