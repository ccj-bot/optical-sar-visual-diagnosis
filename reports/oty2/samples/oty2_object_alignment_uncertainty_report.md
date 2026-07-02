# OTY2-P0 Object Alignment Uncertainty Report

## Run Status

- scenes_attempted: `GM_RM017;GM_RM019`
- scenes_completed: `GM_RM017;GM_RM019`
- scenes_blocked: ``
- gm_rm011_input_status: `blocked_missing_p4g`

## Alignment Modes Used

- `frame_ratio_hypothesis`: 681

## Readiness Gating Counts

- objects gated as primary: 4
- objects gated as uncertainty-expanded: 7
- objects gated as low-confidence only: 7
- objects excluded: 9
- objects blocked pending visual review: 0
- temporal window candidate rows: 18

## GM_RM011 Input Status

- `GM_RM011`: input_status=`blocked_missing_p4g`, blocker_reason=`missing_oty0;missing_oty1;missing_oty1a;missing_oty1t;missing_p4g_object_hypotheses;missing_p4g_object_frame_states`

## Top Uncertainty Causes

- `high_uncertainty`: 208
- `low_uncertainty`: 240
- `moderate_uncertainty`: 233

## Top Blocker Causes

- `missing_exact_timestamp_metadata`: 2
- `missing_oty0`: 1
- `missing_oty1`: 1
- `missing_oty1a`: 1
- `missing_oty1t`: 1
- `missing_p4g_object_frame_states`: 1
- `missing_p4g_object_hypotheses`: 1
- `using_frame_ratio_hypothesis_audit_only`: 2

## Interpretation Rules

- primary_det_id and main track are used for temporal continuity.
- secondary_det_ids and cluster risk only expand or downgrade alignment confidence.
- review_required does not confirm or deny object identity.
- identity_status never means confirmed identity.
- frame_ratio_hypothesis uses frame-count ratio only as an audit hypothesis, not as truth.

## Boundary Flags

- sar_band_entered: `false`
- sar_gt_coverage_entered: `false`
- sar_image_content_used: `false`
- posthoc_sources_used_for_runtime_tracking: `false`
- annotation_proposal_entered: `false`
- identity_truth_claimed: `false`
