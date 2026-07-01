# OTY1t Observation Cluster Summary

OTY1t-P3 audits same-frame observation clusters, tracker association choices, and bbox provenance around GM_RM019 0039/0045. Outputs remain review-only optical hypotheses. No confirmed identity, SAR alignment, SAR band, SAR GT coverage, SAR evidence sampling, selector output, training signal, or annotation proposal was introduced.

## Summary Fields

- scene: `GM_RM019`
- case_id: `0039_0045`
- frames_analyzed: `149-183`
- observation_cluster_count: `38`
- multi_det_cluster_count: `8`
- partial_full_cluster_count: `6`
- ambiguous_multi_vehicle_cluster_count: `2`
- detector_artifact_cluster_count: `0`
- frame_172_chosen_det_id: `GM_RM019_000172_001`
- frame_172_rejected_det_ids: `GM_RM019_000172_002`
- frame_173_tracked_det_id: `GM_RM019_000173_001`
- bridge_pair_raw_iou: `0.534101`
- bridge_pair_center_distance_px: `71.596`
- tracker_chose_bridge_source_det: `false`
- tracker_chose_alternative_det: `true`
- bbox_provenance_issue_count: `25`
- idx_mapping_suspicious_count: `0`
- recommended_next_step: `tracklet_stitching_review_or_observation_cluster_handoff`
- posthoc_sources_used_for_runtime_tracking: `false`
- sar_alignment_entered: `false`
- sar_band_entered: `false`
- sar_gt_coverage_entered: `false`
- annotation_proposal_entered: `false`
- identity_truth_claimed: `false`

## Pair Metrics

- 172_001 vs 173_001 raw IoU / center distance: `0.957077` / `8.188`
- 172_002 vs 173_001 raw IoU / center distance: `0.534101` / `71.596`

## Hypothesis Support

- Hypothesis A: `moderate`, recommended_use=`optional_continuity_hint_with_visual_review`
- Hypothesis B: `moderate`, recommended_use=`optional_uncertainty_hint_only`
- Hypothesis C: `strong`, recommended_use=`candidate_for_tracklet_stitching_review`

## Boundary

- Tracker id, observation cluster, tracklet link, and visual review hypothesis are not confirmed identity.
- OTY2, SAR band, SAR GT coverage, SAR evidence sampling, selector/G2/A008, threshold tuning, training, and annotation proposal remain outside this audit.
