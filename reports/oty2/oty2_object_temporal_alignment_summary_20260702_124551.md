# OTY2-P0 Object Temporal Alignment Summary

OTY2-P0 maps object-level optical hypotheses and object-frame states to SAR temporal frame/window candidates with readiness gating. It uses object_hypothesis_id as the optical unit and carries primary/secondary observation uncertainty forward. It does not use SAR image content, SAR GT, SAR evidence, final/manual/oracle/review fields, selector output, training signal, SAR band generation, or annotation proposals.

## Summary Fields

- generated_at: `2026-07-02T12:46:31`
- tracker_name: `bytetrack`
- scenes_attempted: `GM_RM017;GM_RM019`
- scenes_completed: `GM_RM017;GM_RM019`
- scenes_blocked: ``
- object_hypotheses_input_count: `27`
- object_frame_state_input_rows: `980`
- object_readiness_gating_rows: `27`
- alignment_frame_map_rows: `681`
- alignment_window_candidate_rows: `18`
- alignment_mode_counts: `frame_ratio_hypothesis:681`
- use_as_primary_alignment_track_count: `4`
- use_with_uncertainty_expansion_count: `7`
- low_confidence_window_only_count: `7`
- exclude_from_oty2_count: `9`
- blocked_pending_visual_review_count: `0`
- gm_rm011_input_status: `blocked_missing_p4g`
- posthoc_sources_used_for_runtime_tracking: `false`
- sar_image_content_used: `false`
- sar_gt_coverage_entered: `false`
- sar_band_entered: `false`
- annotation_proposal_entered: `false`
- identity_truth_claimed: `false`

## Per-Scene

| scene | input_status | object_hypotheses_input_count | object_frame_state_rows | alignment_frame_map_rows | alignment_window_candidate_rows | alignment_readiness | top_blockers |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `GM_RM017` | `ready_with_uncertainty` | 6 | 308 | 308 | 6 | `ready_with_uncertainty` | `missing_exact_timestamp_metadata;using_frame_ratio_hypothesis_audit_only` |
| `GM_RM019` | `ready_with_uncertainty` | 21 | 672 | 373 | 12 | `ready_with_uncertainty` | `missing_exact_timestamp_metadata;using_frame_ratio_hypothesis_audit_only` |
| `GM_RM011` | `blocked_missing_p4g` | 0 | 0 | 0 | 0 | `blocked_missing_inputs` | `missing_oty0;missing_oty1;missing_oty1a;missing_oty1t;missing_p4g_object_hypotheses;missing_p4g_object_frame_states` |

## Boundary

- frame_ratio_hypothesis is audit-only and is not timestamp truth.
- optical_frame_num is not assumed equal to sar_frame_num.
- identity_status is not a confirmed identity claim.
- do_not_enter_sar_band=true for every temporal window candidate.
