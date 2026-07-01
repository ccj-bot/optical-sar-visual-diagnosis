# OTY1t Object Hypothesis Evidence

## Boundary

- Outputs are object-level optical hypotheses.
- confirmed_identity=false
- posthoc_sources_used_for_runtime_tracking=false
- sar_alignment_entered=false
- sar_band_entered=false
- sar_gt_coverage_entered=false
- annotation_proposal_entered=false
- identity_truth_claimed=false

## oty1t_obj_GM_RM019_0039_0045_bt_0098

- same_object_support_level: `strong`
- identity_status: `same_object_hypothesis_review_required`

### main_track_evidence
- bt_0098 is the main tracker trajectory with 25 tracked detections from frame 149 to 182.
- Primary tracklet ids: oty1_tracklet_0038;oty1_tracklet_0045.
- Frame 172 primary_det_id=GM_RM019_000172_001.

### secondary_observation_evidence
- Secondary tracklet ids: oty1_tracklet_0039.
- Frame 172 secondary_det_ids=GM_RM019_000172_002.
- Secondary observations are retained as same-object observation hypotheses, not discarded as independent physical objects.

### observation_cluster_evidence
- Frame 172 cluster role=partial_full_observation_cluster, risk=review_duplicate_or_partial.
- tracker_chose_bridge_source_det=false, tracker_chose_alternative_det=true.

### OTY1a_fragment_hint_evidence
- related edge ids: oty1_tracklet_0038__oty1_tracklet_0039;oty1_tracklet_0038__oty1_tracklet_0045;oty1_tracklet_0039__oty1_tracklet_0045.
- related statuses: ambiguous_competing_merge;partial_to_full_box_transition_candidate.

### counter_evidence
- 172_001 -> 173_001 raw continuity is stronger than 172_002 -> 173_001 (0.957077/8.188 vs 0.534101/71.596).
- Tracker did not assign the 0039 fragment to the same tracker id, so this remains review-required.

### risk_factors
- main_track_stability_status=reactivated_main_track.
- secondary_observation_role=mixed_secondary_observations.
- multi_vehicle_confusion_risk=true.
- idx_mapping_suspicious_count=0.

### recommended_handoff
- Use the main track for temporal continuity and pass secondary observations as uncertainty / partial-full transition state. Do not generate SAR band in P4.
