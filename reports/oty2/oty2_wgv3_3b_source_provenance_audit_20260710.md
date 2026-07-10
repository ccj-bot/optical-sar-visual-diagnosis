# OTY2 WGV3.3B Source Provenance Audit

Date: 20260710

## Boundary

This audit recovers source chains for feasible fields only. It does not use GT to construct runtime fields, does not select a SAR vehicle location, and does not modify annotations.

## Provenance Status Counts

| status | count |
| --- | --- |
| SOURCE_NOT_PRESENT | 1 |
| SOURCE_PRESENT_AND_TRACEABLE | 5 |
| SOURCE_PRESENT_BUT_MAPPING_MISSING | 2 |
| SOURCE_PRESENT_UNREGISTERED | 1 |

## Source Table

| source_type | exists | provenance_status | frame_rate_or_prf | calibration_available | blocking_reason |
| --- | --- | --- | --- | --- | --- |
| optical_png_frames | true | SOURCE_PRESENT_AND_TRACEABLE | known_scale_metadata_optical_fps=24_not_per_frame_timestamp | legacy optical-x to SAR azimuth config available separately | direct optical timestamps absent |
| optical_depth_sidecar | true | SOURCE_PRESENT_UNREGISTERED | same optical frame ids; no direct depth timebase | not consumed for WGV3.3B range | depth-to-SAR range transfer is not calibrated in current source chain |
| sar_png_frames | true | SOURCE_PRESENT_BUT_MAPPING_MISSING | known_scale_metadata_sar_fps=50_not_per_frame_timestamp | display fan geometry only; raw pulse to png mapping missing | raw pulse/window length/step and physical range-axis mapping are absent |
| sar_gray_png_frames | true | SOURCE_PRESENT_BUT_MAPPING_MISSING | known_scale_metadata_sar_fps=50_not_per_frame_timestamp | display fan geometry only; raw pulse to png mapping missing | gray image exists but raw pulse/window derivation is not traceable |
| sar_raw_pulse_or_mat_source | false | SOURCE_NOT_PRESENT | not_found | not_found | no non-depth .mat/.bin/.dat/.raw/.h5/.npy SAR pulse source found |
| software_sync_timing_proxy | true | SOURCE_PRESENT_AND_TRACEABLE | optical_fps=24;sar_fps=50;scale=2.083333;jitter_ms=20 | time scale metadata only | not hardware-exact; no per-frame timestamps |
| legacy_optical_x_to_sar_azimuth_proxy | true | SOURCE_PRESENT_AND_TRACEABLE | not_applicable | azimuth_k=0.0875154;azimuth_b=-40.413555;fan_center=1154.0,1330.6 | coarse legacy proxy only; no full camera-radar extrinsic or range transfer |
| wgv3_3a_automatic_tracklet_nodes | true | SOURCE_PRESENT_AND_TRACEABLE | inherits optical_fps=24 proxy | uses bbox x envelope with legacy azimuth proxy | identity relations uncertain; no range |
| wgv1_4_wgv1_8_posthoc_channel | true | SOURCE_PRESENT_AND_TRACEABLE | posthoc comparison only | after-freeze comparison only | posthoc_visual_constraint; not automatic runtime input |

## Automatic Freeze

| freeze_id | hypothesis_id | source_auto_node_id | sar_frame_start | sar_frame_end | azimuth_min | azimuth_max | hypothesis_permission |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WGV33B_FREEZE_001 | WGV33B_H001 | AUTO_GM_RM011_0001 | 0 | 44 | -55.052 | 38.971 | automatic_uncertain_hypothesis |
| WGV33B_FREEZE_002 | WGV33B_H002 | AUTO_GM_RM011_0002 | 0 | 21 | 9.894 | 41.573 | automatic_runtime_hypothesis |
| WGV33B_FREEZE_003 | WGV33B_H003 | AUTO_GM_RM011_0003 | 8 | 48 | -38.777 | 44.283 | automatic_uncertain_hypothesis |
| WGV33B_FREEZE_004 | WGV33B_H004 | AUTO_GM_RM011_0004 | 22 | 48 | -39.121 | 42.739 | automatic_uncertain_hypothesis |
| WGV33B_FREEZE_005 | WGV33B_H005 | AUTO_GM_RM011_0005 | 27 | 86 | -34.189 | 44.587 | automatic_uncertain_hypothesis |
| WGV33B_FREEZE_006 | WGV33B_H006 | AUTO_GM_RM011_0006 | 29 | 119 | -55.377 | 45.14 | automatic_uncertain_hypothesis |
| WGV33B_FREEZE_007 | WGV33B_H007 | AUTO_GM_RM011_0007 | 37 | 75 | -55.32 | 5.225 | automatic_uncertain_hypothesis |

The automatic freeze above was built before WGV1.4/WGV1.8 posthoc references were read.

## Outputs

- `reports/oty2/oty2_wgv3_3b_source_provenance_audit_20260710.md`
- `reports/oty2/samples/oty2_wgv3_3b_source_provenance_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_optical_time_mapping_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_sar_window_mapping_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_dual_channel_feasible_fields_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_automatic_hypothesis_freeze_20260710.csv`
- `reports/oty2/samples/oty2_wgv3_3b_feasible_field_metrics_20260710.csv`
- `reports/oty2/oty2_wgv3_3b_visual_source_and_mapping_diagnosis_20260710.md`
- `reports/oty2/oty2_wgv3_3b_dual_channel_feasible_field_closure_20260710.md`
