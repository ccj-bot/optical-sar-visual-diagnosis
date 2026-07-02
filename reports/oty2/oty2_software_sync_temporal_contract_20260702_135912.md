# OTY2 Software-Sync Temporal Contract and SAR Frame Windows

This audit corrects the OTY2-P1 timing contract and generates object-level SAR temporal frame windows only. It does not enter SAR image content, SAR spatial search, candidate boxes, ranking, GT, training, or annotation proposal work.

## Timing Contract

- optical_fps: `24`
- sar_fps: `50`
- fps_ratio: `2.083333`
- sync_mode: `software_sync_zero_offset_assumption`
- offset_seconds: `0`
- software_sync_jitter_ms: `20`
- This is software synchronization with a zero-offset processing-start assumption, not hardware-grade exact sync.
- No per-frame real timestamps are claimed.
- SAR frame conversion uses `sar_frame = optical_frame * 50 / 24`; it must not use `sar_frame = optical_frame * 2`.

## Window Formula

For each ready optical object segment:

```text
start_time = optical_start_frame / 24
end_time = (optical_end_frame + 1) / 24
sar_start_raw = start_time * 50
sar_end_raw = end_time * 50
sar_start_frame = floor(sar_start_raw) - padding
sar_end_frame = ceil(sar_end_raw) + padding
```

Padding combines rounding, software-sync jitter, and object-state uncertainty. These are audit defaults, not trained thresholds.

## Padding Defaults

- base_rounding_padding_sar_frames: `1`
- software_sync_jitter_padding_sar_frames: `1`
- stable_primary_padding_sar_frames: `1`
- secondary_or_edge_padding_sar_frames: `2`
- ambiguous_padding_sar_frames: `3`
- padding_source: `audit_defaults_not_training_thresholds`

## Per-Scene Summary

| scene | temporal metadata | target input | generated windows | not-ready object rows | blockers |
| --- | --- | --- | ---: | ---: | --- |
| `GM_RM011` | `timestamp_offset_scale_hypothesis` / `software_sync_zero_offset_assumed` | `blocked_missing_p4g_object_stream` | 0 | 0 | `missing_oty0;missing_oty1;missing_oty1a;missing_oty1t;missing_p4g_object_hypotheses;missing_p4g_object_frame_states` |
| `GM_RM017` | `timestamp_offset_scale_hypothesis` / `software_sync_zero_offset_assumed` | `available` | 6 | 0 | `` |
| `GM_RM019` | `timestamp_offset_scale_hypothesis` / `software_sync_zero_offset_assumed` | `available` | 12 | 9 | `` |

## Boundary Flags

- sar_image_content_used: `false`
- sar_spatial_search_entered: `false`
- sar_search_region_generated: `false`
- sar_gt_used: `false`
- selector_or_ranking_used: `false`
- annotation_proposal_entered: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`

## Artifacts

- software_sync_temporal_contract: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_software_sync_temporal_contract_20260702_135912.md`
- object_sar_temporal_windows: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- object_sar_temporal_window_summary: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_summary_20260702_135912.json`
- object_sar_temporal_windows_sample: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_object_sar_temporal_windows_sample.csv`
