# OTY2 Object SAR Temporal Window Downstream Input Contract

Generated: `20260702_142454`

This contract freezes the current object-level SAR temporal-window output as an input to a later spatial-constraint stage. It is not a SAR detector, not a SAR spatial search, not a candidate-box generator, and not an annotation proposal.

## Eligible Inputs

Normal downstream spatial-constraint inputs are limited to object rows whose `readiness_status` is:

- `ready_primary_sar_temporal_window`: stable primary optical continuity; pass as a primary temporal prior.
- `ready_uncertainty_expanded_sar_temporal_window`: usable primary continuity with secondary/edge/handoff uncertainty; pass with expanded uncertainty flags.

`low_confidence_sar_temporal_window` rows are kept as review-only temporal context. They are not normal spatial-constraint inputs unless a later explicitly bounded review mode accepts them. `not_ready_for_sar_temporal_window` rows remain blocked.

## Blocked Inputs

- `short_noise_not_ready` objects remain blocked before spatial constraint construction.
- Scene-level missing object flow remains blocked even if temporal metadata exists.
- `GM_RM011` has 24:50 software-sync temporal metadata, but it has no committed optical object stream in this run, so it cannot produce object-level downstream inputs.

## Required Fields Passed Downstream

The minimum object-level temporal input record is:

```text
scene
object_hypothesis_id
optical_start_frame
optical_end_frame
optical_frame_count
optical_start_time_sec
optical_end_time_sec
sar_start_raw
sar_end_raw
sar_start_frame
sar_end_frame
sar_window_frame_count
optical_fps
sar_fps
fps_ratio
sync_mode
offset_seconds
software_sync_jitter_ms
padding_sar_frames
padding_reason
object_state_category
uses_primary_observations
uses_secondary_observations
readiness_status
confidence_status
blockers
notes
```

These fields carry temporal scope only. They do not carry a SAR location, SAR search region, candidate box, score, rank, GT coverage result, annotation decision, or identity truth.

## Temporal Interpretation

- `sar_start_frame` and `sar_end_frame` are inclusive SAR frame indices.
- The window is derived from object optical frame bounds, not from per-frame real timestamps.
- The conversion is `start_time = optical_start_frame / 24`, `end_time = (optical_end_frame + 1) / 24`, then `sar_time * 50`.
- The mapping must use `50/24 = 2.083333`; a simple two-times relationship is invalid.
- `offset_seconds = 0` is a software-sync zero-offset processing-start assumption, not hardware exact sync.

## Padding Semantics

- Base rounding padding covers floor/ceil quantization after converting continuous time to SAR frame indices.
- Software-sync jitter padding covers millisecond-level non-hardware synchronization error; current audit default is one SAR frame for 20 ms at 50 fps.
- Object-state padding covers optical uncertainty from secondary observations, duplicate/partial/edge/occlusion states, handoff, ambiguity, or review-required states.
- Padding defaults are audit defaults, not trained thresholds.

## Object-State Handling

| object state | downstream handling | padding policy |
| --- | --- | --- |
| `stable_primary_continuity` | normal primary input | base + software jitter + stable primary padding |
| `secondary_edge_handoff_uncertainty` | normal input with expanded uncertainty | base + software jitter + secondary/edge/duplicate/partial/occlusion/handoff padding |
| `ambiguous_review_required` | review-only temporal context, not normal spatial input | base + software jitter + ambiguous padding |
| `short_noise_not_ready` | blocked before spatial constraints | no generated temporal window |

## Scene Status

| scene | object rows | generated windows | normal downstream inputs | review-only windows | blocked/not-ready rows | blocker |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `GM_RM011` | 0 | 0 | 0 | 0 | 1 | `missing_oty0;missing_oty1;missing_oty1a;missing_oty1t;missing_p4g_object_hypotheses;missing_p4g_object_frame_states` |
| `GM_RM017` | 6 | 6 | 5 | 1 | 0 | `` |
| `GM_RM019` | 21 | 12 | 6 | 6 | 9 | `` |

## Boundary Flags

- sar_image_content_used: `false`
- sar_spatial_search_entered: `false`
- sar_search_region_generated: `false`
- sar_candidate_boxes_generated: `false`
- sar_gt_used: `false`
- final_manual_oracle_review_runtime_fields_used: `false`
- selector_or_ranking_used: `false`
- annotation_proposal_entered: `false`
- training_or_threshold_tuning_entered: `false`
- identity_truth_claimed: `false`
- detection_box_level_merge_reintroduced: `false`

## Source and Output Artifacts

- source_temporal_windows: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_windows_20260702_135912.csv`
- source_temporal_window_summary: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_summary_20260702_135912.json`
- quality_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_quality_audit_20260702_142454.csv`
- quality_report: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_sar_temporal_window_quality_report_20260702_142454.md`
- spatial_constraint_design: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_temporal_window_to_spatial_constraint_design.md`
