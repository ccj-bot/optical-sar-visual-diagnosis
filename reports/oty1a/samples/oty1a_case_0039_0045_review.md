# OTY1a Case Review: GM_RM019 0039/0045

This case reviews whether `oty1_tracklet_0039` and `oty1_tracklet_0045` should enter fragment merge review under runtime-safe optical geometry.

## Boundary

- Runtime evidence is OTY1 optical geometry/state outputs only.
- No SAR frame, SAR GT/evidence, final/manual/oracle/review fields, selector, G2, A008, threshold tuning, training, or annotation proposal is used.
- The result is not confirmed identity truth.

## OTY1a Merge Edge

- merge candidate status: `partial_to_full_box_transition_candidate`
- merge_candidate_score_not_selector: `0.680777`
- endpoint_center_distance_px: `80.151`
- bridge_iou_proxy: `0.541249`
- frame_overlap_count: `1`
- temporal_relation: `overlap_or_interleave`
- shape_transition_proxy: `area_transition_review`
- partial_to_full_box_transition_proxy: `partial_to_full_box_transition_review`

## OTY1 Detection-Level Bridge Evidence

- `GM_RM019_000172_002 -> GM_RM019_000173_001`; frame_gap=`1`; center_distance_px=`71.5955617878921`; bbox_iou=`0.5341011991790791`; size_consistency=`0.5857299415908697`; selected_for_component=`False`
- `GM_RM019_000172_002 -> GM_RM019_000174_001`; frame_gap=`2`; center_distance_px=`88.61250327799733`; bbox_iou=`0.48296848007113746`; size_consistency=`0.610036981072001`; selected_for_component=`False`
- `GM_RM019_000172_002 -> GM_RM019_000175_001`; frame_gap=`3`; center_distance_px=`111.90824557982823`; bbox_iou=`0.4249850642759474`; size_consistency=`0.6457744004489037`; selected_for_component=`False`
- `GM_RM019_000172_002 -> GM_RM019_000176_001`; frame_gap=`4`; center_distance_px=`138.47301577163046`; bbox_iou=`0.36199002640909983`; size_consistency=`0.7009307004640499`; selected_for_component=`False`
- `GM_RM019_000168_002 -> GM_RM019_000171_001`; frame_gap=`3`; center_distance_px=`206.87706947998913`; bbox_iou=`0.30063337264115897`; size_consistency=`0.5032317243376477`; selected_for_component=`False`

## Interpretation

`oty1_tracklet_0039` and `oty1_tracklet_0045` should be treated as an optical runtime-geometry merge review candidate. The overlap around frames 171/172 and the cross-fragment detection edge are strong enough for review, but competing edges and neighbor/boundary ambiguity mean identity remains unconfirmed.

## Visualization

- `D:\profile\research\optical-sar-visual-diagnosis\reports\oty1a\samples\visualizations\oty1a_0039_0045_merge_review.svg`
