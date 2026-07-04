# OTY2 Optical State Tagging Spec

Updated: 2026-07-04

This document defines review-safe optical state tags for OTY2 optical object-stream diagnosis. The tags are not truth labels. They are observable evidence tags used to explain why detection observations, track fragments, merge candidates, or object hypotheses are strong, weak, ambiguous, or blocked.

The tags do not authorize runtime logic changes, automatic grouping, final annotations, revised GT, final boxes, selector/ranking logic, weighted fusion, SAR pairing, support audit, identity truth, or clean `215` promotion.

## 1. Tagging Principles

- A state tag records observable optical evidence, not physical truth.
- `occlusion_like` must not be written as true occlusion.
- `truncation_like` must not be written as true truncation.
- `duplicate_overlap_detection` must not be treated as proof of same vehicle.
- `multi_object_competition` usually blocks automatic merge unless a later global mechanism proves a safe exception.
- Tags may support later reconnect only when combined with cross-scene evidence, temporal continuity, and competition context.
- Tags should reduce automatic reconnect strength when they indicate ambiguity, competition, or missing evidence.
- `review_required` is mandatory when tags conflict or when identity cannot be decided safely.

## 2. Normalized Tags

| Tag | Meaning | Observable evidence | Fields or proxy metrics | Can be used for | Cannot be used for | Reconnect support | Automatic reconnect strength | Review requirement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `edge_contact` | Bbox touches or stays close to image edge | box near left/right/top/bottom boundary; edge entry/exit pattern | `bbox_x1`, `bbox_y1`, `bbox_x2`, `bbox_y2`, OTY1 `touch_*`, `touch_any`, `boundary_contact_count` | flag incomplete observations and boundary-sensitive fragments | declaring true truncation or identity | supports reconnect only as explanatory state | lowers strength unless motion and state are stable | required if combined with shape jump, short gap, or competition |
| `truncation_like` | Observation may be frame-clipped or partial because of edge/FOV | edge contact plus sudden size/area change; object entering/leaving view | OTY1 `truncation_likelihood_proxy`, `frame_boundary_contact_status`, `size_change_ratio`, `boundary_contact_count` | explain partial boxes and blocked continuity | claiming real truncation or final visibility state | weak support for bridge if geometry remains plausible | lowers strength | required unless independently stable across frames |
| `partial_visible` | Bbox appears to cover only part of vehicle | smaller box than nearby observations; local/part-like detection; plausible motion area | bbox area, area ratio to same-frame or nearby boxes, OTY1 `bbox_area`, `bbox_aspect` | identify local-box fragments or partial/full candidates | declaring vehicle extent or final box | can support partial-to-full diagnosis | lowers strength until paired with transition evidence | required if paired with competition |
| `partial_to_full_transition` | Box may change from partial view to fuller view | rapid area/aspect change with possible center continuity | OTY1 `size_change_ratio`, `bbox_aspect`; OTY1a `partial_to_full_box_transition_proxy`, `area_ratio_endpoint`, `aspect_ratio_endpoint` | explain fragment boundary and candidate bridge | confirming same target identity | moderate support only when center/timing and competition are safe | lowers strength if abrupt or competed | required unless transition is globally validated |
| `occlusion_like` | Runtime-safe sign of an occlusion-like gap | short missing gap; lost/reactivated track; before/after position plausibly continuous; nearby overlap | OTY1 gap fields; OTY1t `lost_count`, `reactivated_count`, `missing_gap_count`; unmatched bucket | explain missing observations | claiming true physical occlusion | weak bridge support with short gap and stable motion | lowers strength | required when gap source is not known |
| `short_missing_gap` | Short temporal hole between plausible fragments | frame gap or tracker lost/reactivated event | OTY1a `forward_gap_frames`, `frame_gap`; OTY1t `missing_gap_count`, `max_gap`, `lost_count` | bridge candidate diagnosis | automatic stitch or identity truth | supports graph edge candidate if other evidence is strong | neutral to lower, depending on competition | required if combined with state instability |
| `multi_object_competition` | Same frame or adjacent frames have multiple plausible objects/candidates | crowded frame; multiple detections; competing successors/predecessors | OTY0 per-frame detection count; OTY1 `neighbor_count`, `neighbor_ambiguity_proxy`; OTY1a competing counts | block unsafe merge and preserve candidates | selecting identity winner | usually blocks reconnect until resolved globally | strongly lowers strength | required |
| `duplicate_overlap_detection` | Same-frame boxes overlap or centers are very close | high overlap proxy; near-identical center; duplicate-like detector output | OTY0 bbox overlap/center distance; OTY1t unmatched bucket `duplicate_or_overlap_rejected` | diagnose detection postprocess instability | proving same vehicle | can support same-frame grouping candidate only | lowers strength if class/state conflict; may become diagnostic candidate | required if class mismatch or crowding exists |
| `neighbor_competition` | Nearby detections likely represent different vehicles or unresolved neighbors | close centers with low overlap; crowded frame; high neighbor count | center distance, overlap proxy, `neighbor_count`, `min_neighbor_center_distance_px`, competing merge counts | block same-target merge and mark competition | proving different vehicle identity | generally blocks reconnect | strongly lowers strength | required |
| `shape_instability` | Bbox size/aspect/area changes abruptly | area ratio shift; aspect ratio transition; shape transition review | OTY1 `size_change_ratio`, `bbox_aspect`; OTY1a `shape_transition_proxy`, `aspect_ratio_endpoint`, `area_ratio_endpoint` | explain short fragments and partial/full candidates | final shape state or vehicle extent | weak support only when motion is continuous | lowers strength | required if paired with short fragment |
| `class_instability` | Same spatial observation has inconsistent class labels | high-overlap boxes with different classes; class changes across candidate bridge | OTY0 `class_name`, OTY1a `class_consistent`, class mismatch rejects | diagnose detector/category instability | choosing identity or class truth | can support duplicate-like diagnosis but not identity | lowers strength | required |

## 3. Tag Combinations

Some combinations should be treated as blockers before any automatic grouping:

- `duplicate_overlap_detection + class_instability`: likely duplicate-like observation, but class conflict must be resolved by a global detection-postprocess rule or visual review.
- `partial_visible + shape_instability + multi_object_competition`: possible partial/full candidate, not safe to group automatically.
- `neighbor_competition + multi_object_competition`: strong block against same-target grouping.
- `edge_contact + truncation_like + short_missing_gap`: can explain a break, but cannot prove continuity.
- `occlusion_like + lost/reactivated tracker state`: can explain missing observations, not true occlusion.

## 4. Output Contract

State tags may be attached to detection observations, track fragments, merge candidates, object hypotheses, or diagnostic samples.

Each tagged record should preserve:

- observable evidence;
- source field/proxy;
- whether the tag supports a candidate reconnect;
- whether the tag lowers automatic reconnect strength;
- whether review remains required;
- a statement that the tag is not identity truth.

The tags prepare clean observation/state inputs for a later fragment relation graph. They do not create that graph and do not merge objects.
