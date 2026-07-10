# OTY2 WGV3.3C First Non-GT SAR Response Experiment Inside Automatic Feasible Fields

Date: 20260710

## WGV3.3B Inherited Corrections

1. `software_sync_jitter_ms = 20`.
2. `offset_stress_band = +/-12 SAR frames = +/-240 ms`.
3. The current feasible-field time uncertainty is dominated by the +/-240 ms offset stress band, not by the 20 ms software jitter.
4. WGV1.8 T001 SAR `0-36` is a GT-assisted posthoc mechanism anchor, not an automatic non-GT time mapping.
5. The prior `70..85 deg` control sector falls in an all-zero / fixed-black support area and is not a valid background control.
6. The prior `0.088729` ratio uses a theoretical full-angle denominator; WGV3.3C supplements it with the actual effective imaging-support denominator.

## Boundary

Automatic response extraction used only WGV3.3B's seven frozen automatic hypotheses, SAR-gray images, and display fan geometry. It did not read WGV1.8 SAR `0-36`, `sar_gt_ids`, GT boxes, GT centers, or final localization artifacts before the response freeze.

The posthoc stage was run only after the response freeze and reads T001 metadata for evaluation. It reports SAR response observations, not final boxes, target identity, ranking, or annotations.

## Effective SAR Support Domain

| support_sample_frame_count | valid_azimuth_min | valid_azimuth_max | valid_azimuth_bins | valid_radial_pixel_min | valid_radial_pixel_max | fixed_black_mask_ratio |
| --- | --- | --- | --- | --- | --- | --- |
| 42 | -61 | 61 | 123 | 26 | 1332 | 0.28576054 |

- Support sample frames: `0;5;8;10;15;20;21;22;25;27;28;29;30;35;37;40;44;45;48;50;56;60;70;74;75;85;86;100;119;150;200;250;300;350;400;450;500;550;600;650;700;765`.
- `radial_pixel` is image-domain radius from the display fan center, not meter-scale range.
- A stable effective pixel is a fan pixel that is nonzero in at least 20% of sampled SAR-gray frames.
- Per-frame azimuth support is preserved in the frame-azimuth CSV; the report does not collapse frame-varying support into a precise physical range.

## Search-Reduction Denominators

| full_angle_bin_count | effective_azimuth_bin_count | auto_time_azimuth_cells_full_angle | auto_time_azimuth_cells_effective_support | theoretical_full_angle_search_reduction_ratio | effective_support_search_reduction_ratio |
| --- | --- | --- | --- | --- | --- |
| 178 | 123 | 12187 | 12187 | 0.08938158 | 0.12934896 |

## Automatic Response Summary

| hypothesis_id | source_auto_node_id | sar_frame_start | sar_frame_end | azimuth_min | azimuth_max | mean_intensity | mean_top1pct_intensity | target_to_adjacent_mean_ratio | target_to_far_mean_ratio | target_to_temporal_mean_ratio | response_observation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WGV33B_H001 | AUTO_GM_RM011_0001 | 0 | 44 | -55.052 | 38.971 | 43.25966696 | 94.36175434 | 1.052841 | 2.412679 | 1.060411 | response_mixed_vs_controls_needs_sar_internal_followup |
| WGV33B_H002 | AUTO_GM_RM011_0002 | 0 | 21 | 9.894 | 41.573 | 39.12824185 | 71.96292866 | 0.987789 | 1.011713 | 0.84301 | response_not_elevated_vs_controls |
| WGV33B_H003 | AUTO_GM_RM011_0003 | 8 | 48 | -38.777 | 44.283 | 45.66565544 | 100.94049759 | 1.015982 | 1.063832 | 1.140356 | response_mixed_vs_controls_needs_sar_internal_followup |
| WGV33B_H004 | AUTO_GM_RM011_0004 | 22 | 48 | -39.121 | 42.739 | 47.19777104 | 105.75097427 | 1.016285 | 1.05779 | 1.215996 | response_mixed_vs_controls_needs_sar_internal_followup |
| WGV33B_H005 | AUTO_GM_RM011_0005 | 27 | 86 | -34.189 | 44.587 | 42.30577045 | 95.12903142 | 1.012772 | 1.065466 | 1.050908 | response_not_elevated_vs_controls |
| WGV33B_H006 | AUTO_GM_RM011_0006 | 29 | 119 | -55.377 | 45.14 | 41.41305698 | 90.61518344 | 1.068695 | 2.390872 | 0.851043 | response_mixed_vs_controls_needs_sar_internal_followup |
| WGV33B_H007 | AUTO_GM_RM011_0007 | 37 | 75 | -55.32 | 5.225 | 41.40057873 | 92.2782914 | 1.028527 | 2.401462 | 1.001269 | response_mixed_vs_controls_needs_sar_internal_followup |

## Posthoc T001 Evaluation After Freeze

| hypothesis_id | posthoc_sar_frame_start | posthoc_sar_frame_end | auto_sar_frame_start | auto_sar_frame_end | time_overlap_frame_count | time_overlap_ratio_vs_posthoc_anchor | evaluation_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WGV33B_H001 | 0 | 36 | 0 | 44 | 37 | 1 | posthoc_time_overlap_with_mixed_auto_response |
| WGV33B_H002 | 0 | 36 | 0 | 21 | 22 | 0.594595 | posthoc_time_overlap_without_control_elevation |
| WGV33B_H003 | 0 | 36 | 8 | 48 | 29 | 0.783784 | posthoc_time_overlap_with_mixed_auto_response |
| WGV33B_H004 | 0 | 36 | 22 | 48 | 15 | 0.405405 | posthoc_time_overlap_with_mixed_auto_response |
| WGV33B_H005 | 0 | 36 | 27 | 86 | 10 | 0.27027 | posthoc_time_overlap_without_control_elevation |
| WGV33B_H006 | 0 | 36 | 29 | 119 | 8 | 0.216216 | posthoc_time_overlap_with_mixed_auto_response |
| WGV33B_H007 | 0 | 36 | 37 | 75 | 0 | 0 | no_posthoc_time_overlap |

Evaluation status counts: `no_posthoc_time_overlap=1; posthoc_time_overlap_with_mixed_auto_response=4; posthoc_time_overlap_without_control_elevation=2`.

## Response Freeze

- Combined automatic response freeze SHA256: `8436449b4176acc67036a4a4fb165fb680221f2feba09d8480830ce0f4e29ad8`.
- Freeze manifest records `wgv1_4_or_wgv1_8_read_before_freeze=false`, `sar_gt_ids_loaded=false`, and `gt_box_or_center_loaded=false`.

## Outputs

- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_sar_support_domain_summary_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_support_mask_frame_summary_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_frame_azimuth_support_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_valid_azimuth_bins_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_valid_radial_bins_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_response_regions_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_response_timeseries_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_response_summary_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_response_freeze_manifest_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3c_posthoc_t001_evaluation_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/oty2_wgv3_3c_first_non_gt_sar_response_experiment_20260710.md`

## Git Context At Generation

- branch: `feature/oty2-posthoc-mechanism-validation`
- generation HEAD: `b514502d440af742eb259262302281433b852d71`
