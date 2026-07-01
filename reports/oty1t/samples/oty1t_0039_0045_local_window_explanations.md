# OTY1t 0039/0045 Local Window Explanations

## Boundary

- These are review-only optical hypotheses.
- confirmed_identity=false
- posthoc_sources_used_for_runtime_tracking=false
- sar_alignment_entered=false
- sar_band_entered=false
- sar_gt_coverage_entered=false
- annotation_proposal_entered=false
- identity_truth_claimed=false

## Hypotheses

### Hypothesis A

- hypothesis: `0039 partial boxes and 0045 full/right-edge boxes are same-object observation variants.`
- support_level: `moderate`
- recommended_use: `optional_continuity_hint_with_visual_review`
- evidence:
  - bridge pair GM_RM019_000172_002->GM_RM019_000173_001 raw IoU=0.534101 center_distance_px=71.596
  - OTY1a status=partial_to_full_box_transition_candidate with partial/full transition context
  - existing optical visual panel impression is contiguous but review-only
  - boundary / partial / shape transition evidence is present in OTY1/OTY1a context
- counter_evidence:
  - ByteTrack chose GM_RM019_000172_001 instead of the bridge source
  - same-frame detection competition remains unresolved

### Hypothesis B

- hypothesis: `0039 boxes are duplicate / partial / wide detector artifacts that should not override the stable tracker hypothesis.`
- support_level: `moderate`
- recommended_use: `optional_uncertainty_hint_only`
- evidence:
  - frame 172 rejected neighbor det_ids=GM_RM019_000172_002
  - 0039-side boxes include wide / shallow / boundary-touching observations
  - tracker chose alternative det=GM_RM019_000172_001 on the 0045 side
  - 0039 unmatched sequence persists through the local transition window
- counter_evidence:
  - bridge pair still has nontrivial raw IoU=0.534101
  - artifact interpretation is an optical review hypothesis, not identity truth

### Hypothesis C

- hypothesis: `0039/0045 region contains multi-vehicle or same-frame detection competition.`
- support_level: `strong`
- recommended_use: `candidate_for_tracklet_stitching_review`
- evidence:
  - multi-det observation clusters in analyzed window=8
  - frame 172 cluster contains both 172_001 and 172_002 with tracker choosing one and rejecting the other
  - OTY1/OTY1a context marks ambiguous crossing / competing merge risk
  - nearby detections appear across frames 162-174 in OTY0 rows
- counter_evidence:
  - same-frame clusters are optical observation clusters, not confirmed multi-vehicle truth
  - tracker id continuity alone cannot resolve identity

## Final Conclusion

OTY1t-P3 keeps 0039/0045 as review-only optical observation and tracker association hypotheses. The audit supports an observation-cluster / tracklet-stitching review handoff, not confirmed identity.
