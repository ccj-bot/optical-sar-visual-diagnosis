# OTY2 WGV3.3D Local SAR Response Temporal Closure

Date: 20260710

WGV3.3D status: `CLOSED_COMPONENTS_FOUND_NOT_TARGET_SPECIFIC`

## Boundary

Automatic A0-A4 used SAR PNG/gray images, display fan geometry, and WGV3.3B frozen automatic hypotheses only. WGV1.4/WGV1.8 and T001/T004 metadata were read only after the automatic freeze.

No component or thread is promoted to an object identity or final localization. All component labels remain `local_sar_response_component`.

## Key Counts

- total_local_components: `28353`
- total_component_edges: `58351`
- total_response_threads: `3547`
- dynamic_supported_thread_count: `635`
- dynamic_mixed_thread_count: `380`
- static_clutter_thread_count: `0`
- transient_unlinked_count: `2530`
- matched_control_unavailable_count: `0`

## Automatic Hypotheses

| hypothesis_id | intersecting_component_count | intersecting_response_thread_count | dynamic_like_thread_count | static_clutter_like_thread_count | component_density_per_1000_effective_units | status_note |
| --- | --- | --- | --- | --- | --- | --- |
| WGV33B_H001 | 738 | 253 | 78 | 0 | 0.52223176 | dynamic_local_response_mixed=26;dynamic_local_response_supported=52;static_clutter_like=0;transient_unlinked=175 |
| WGV33B_H002 | 87 | 19 | 11 | 0 | 0.3737478 | dynamic_local_response_mixed=8;dynamic_local_response_supported=3;static_clutter_like=0;transient_unlinked=8 |
| WGV33B_H003 | 630 | 218 | 72 | 0 | 0.55388334 | dynamic_local_response_mixed=30;dynamic_local_response_supported=42;static_clutter_like=0;transient_unlinked=146 |
| WGV33B_H004 | 415 | 162 | 55 | 0 | 0.56216801 | dynamic_local_response_mixed=20;dynamic_local_response_supported=35;static_clutter_like=0;transient_unlinked=107 |
| WGV33B_H005 | 939 | 320 | 113 | 0 | 0.5948041 | dynamic_local_response_mixed=48;dynamic_local_response_supported=65;static_clutter_like=0;transient_unlinked=207 |
| WGV33B_H006 | 1843 | 465 | 144 | 0 | 0.60325087 | dynamic_local_response_mixed=57;dynamic_local_response_supported=87;static_clutter_like=0;transient_unlinked=321 |
| WGV33B_H007 | 472 | 154 | 53 | 0 | 0.59848413 | dynamic_local_response_mixed=20;dynamic_local_response_supported=33;static_clutter_like=0;transient_unlinked=101 |

## Posthoc Evaluation

| evaluation_item | overlapping_threads | dynamic_supported_threads | dynamic_mixed_threads | static_like_threads | control_indistinguishable_threads | evaluation_status |
| --- | --- | --- | --- | --- | --- | --- |
| T001_posthoc_anchor | 195 | 38 | 23 | 0 | 0 | dynamic_supported_present |
| T004_complex_subject_switch | 441 | 84 | 33 | 0 | 0 | dynamic_supported_present |
| boundary_control_window | 23 | 11 | 7 | 0 | 0 | dynamic_supported_present |
| background_control_window | 151 | 30 | 28 | 0 | 0 | dynamic_supported_present |

## WGV3.3C Signal Changes

- H003 temporal evidence after local normalization: `dynamic_local_response_mixed=30;dynamic_local_response_supported=42;static_clutter_like=0;transient_unlinked=146`.
- H004 temporal evidence after local normalization: `dynamic_local_response_mixed=20;dynamic_local_response_supported=35;static_clutter_like=0;transient_unlinked=107`.
- H001/H006/H007 far-control artifact check: H001 `dynamic_local_response_mixed=26;dynamic_local_response_supported=52;static_clutter_like=0;transient_unlinked=175`, H006 `dynamic_local_response_mixed=57;dynamic_local_response_supported=87;static_clutter_like=0;transient_unlinked=321`, H007 `dynamic_local_response_mixed=20;dynamic_local_response_supported=33;static_clutter_like=0;transient_unlinked=101`. WGV3.3D uses equal-scale local controls rather than 1-degree far-sector controls.

## Conclusion

Local components and temporal threads are reproducible, but T001 is not sufficiently distinct from background/complex windows to claim a T001-specific dynamic prototype.

## Freeze

- combined SHA256: `da7e991c65a689a944e1f473737b726a787eefea9d17a875b56a957c88bc4350`
- wgv1_4_read_before_freeze=false
- wgv1_8_read_before_freeze=false
- sar_gt_ids_loaded=false
- gt_box_or_center_loaded=false

## Outputs

- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/oty2_wgv3_3d_png_normalization_audit_20260710.md`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_png_frame_statistics_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_local_components_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_component_edges_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_response_threads_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_static_clutter_statistics_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_matched_controls_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_automatic_field_thread_intersections_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_automatic_response_summary_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_response_freeze_manifest_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_wgv3_3d_posthoc_evaluation_20260710.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/oty2_wgv3_3d_visual_component_diagnosis_20260710.md`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/oty2_wgv3_3d_local_response_temporal_closure_20260710.md`
