# OTY1t Object Hypothesis Generalization Summary

OTY1t-P4G generalizes object-level optical hypotheses across available scenes and defines the OTY2 object-level input contract. The outputs use object_hypothesis_id as the optical unit, preserve primary and secondary observations, and route ambiguous/orphan observations to review. No confirmed identity, SAR alignment, SAR band, SAR GT coverage, SAR evidence sampling, selector output, training signal, or annotation proposal was introduced.

## Summary Fields

- generated_at: `2026-07-01T23:06:41`
- tracker_name: `bytetrack`
- scenes_attempted: `GM_RM017;GM_RM019`
- scenes_completed: `GM_RM017;GM_RM019`
- scenes_blocked: ``
- object_hypothesis_count_total: `27`
- object_frame_state_rows_total: `980`
- stable_object_hypothesis_count: `4`
- main_track_with_secondary_observations_count: `7`
- ambiguous_object_hypothesis_count: `7`
- short_or_noise_track_hypothesis_count: `9`
- orphan_observation_count: `50`
- strong_same_object_hypothesis_count: `5`
- moderate_same_object_hypothesis_count: `11`
- weak_same_object_hypothesis_count: `11`
- review_required_count: `23`
- recommended_main_track_only_count: `4`
- recommended_main_track_with_uncertainty_count: `7`
- recommended_tracklet_stitching_review_count: `0`
- idx_mapping_suspicious_count_total: `0`
- posthoc_sources_used_for_runtime_tracking: `false`
- sar_alignment_entered: `false`
- sar_band_entered: `false`
- sar_gt_coverage_entered: `false`
- annotation_proposal_entered: `false`
- identity_truth_claimed: `false`

## Per-Scene

| scene | input_status | object_hypothesis_count | object_frame_state_rows | orphan_observation_count | ambiguous_object_hypothesis_count | top_blockers | oty2_input_readiness |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `GM_RM017` | `completed` | 6 | 308 | 8 | 1 | `` | `ready_with_uncertainty` |
| `GM_RM019` | `completed` | 21 | 672 | 42 | 6 | `` | `ready_with_uncertainty` |
