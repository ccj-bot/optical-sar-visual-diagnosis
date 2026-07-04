# OTY2 Optical Stream Tracking Insertion Point Audit

Timestamp: `20260704_215625`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`

## Boundary

This is a code-entry and mechanism-insertion-point audit only. No runtime logic was changed, no diagnostic script was run, no automatic grouping was implemented, no thresholds were tuned, no tracker was changed, no final boxes were generated, no identity truth was declared, no SAR pairing/support audit was entered, and no GM_RM011 clean-215 promotion was made.

The audit read source code and existing OTY2 optical-stream boundary/report documents only.

## Sources Read

Required session sources:

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports/oty2/oty2_same_frame_multibox_and_state_tagging_audit_20260704_214019.md`
- `reports/oty2/samples/oty2_same_frame_multibox_grouping_samples_20260704_214019.csv`

Code entry points inspected:

- `tools/diagnostics/run_oty0_yolo_detection_stream_audit.py`
- `tools/diagnostics/run_oty1_optical_tracklet_audit.py`
- `tools/diagnostics/run_oty1a_fragment_merge_audit.py`
- `tools/diagnostics/run_oty1t_tracker_audit.py`
- `tools/diagnostics/run_oty1t_object_hypothesis_audit.py`
- `tools/diagnostics/run_oty1t_object_hypothesis_generalization_audit.py`
- `src/optical_state/tracklet_builder.py`
- `src/optical_state/fragment_merge.py`
- `src/optical_state/tracker_audit.py`
- `src/optical_state/tracker_diagnosis.py`
- `src/optical_state/observation_cluster.py`
- `src/optical_state/object_hypothesis.py`
- `configs/oty_yolo_stream_config.yaml`

## Stage IO Map

| Stage | Main entry | Runtime input | Main output tables | Current interpretation |
| --- | --- | --- | --- | --- |
| OTY0 YOLO detection | `run_oty0_yolo_detection_stream_audit.py` | Raw optical frames and configured YOLO model | `oty0_yolo_detection_table.csv`, `oty0_optical_frame_inventory.csv`, schema/boundary files | Detector observations only |
| OTY1 tracklet construction | `run_oty1_optical_tracklet_audit.py`, `tracklet_builder.py` | OTY0 detection table | `oty1_tracklet_candidate_edges.csv`, `oty1_optical_tracklet_components.csv`, `oty1_optical_tracklet_state_timeseries.csv`, `oty1_tracklet_quality_audit.csv` | Geometry-only tracklet candidates, not identity |
| OTY1a fragment merge audit | `run_oty1a_fragment_merge_audit.py`, `fragment_merge.py` | OTY1 edges/components/state | `oty1a_fragment_merge_candidate_edges.csv`, `oty1a_fragment_merge_component_review.csv`, `oty1a_shape_transition_audit.csv` | Review-only fragment relation candidates, not merges |
| OTY1t tracker audit | `run_oty1t_tracker_audit.py`, `tracker_audit.py`, `tracker_diagnosis.py` | OTY0 detection table plus optional OTY1/OTY1a comparison context | `oty1t_tracker_detection_assignments.csv`, `oty1t_tracker_tracks.csv`, `oty1t_tracker_state_timeseries.csv`, `oty1t_tracker_events.csv`, `oty1t_unmatched_detection_audit.csv` | Tracker hypotheses and event diagnostics only |
| P4/P4G object hypothesis | `run_oty1t_object_hypothesis_audit.py`, `run_oty1t_object_hypothesis_generalization_audit.py`, `observation_cluster.py`, `object_hypothesis.py` | OTY0, OTY1, OTY1a, OTY1t optical artifacts | `oty1t_object_hypotheses*.csv`, `oty1t_object_frame_state_timeseries*.csv`, orphan/cluster/provenance tables | Object-level optical hypotheses with uncertainty, not identity truth |

## Current Handling By Stage

### OTY0 Detection Output

`configs/oty_yolo_stream_config.yaml` filters YOLO output to `car`, `truck`, and `bus` with confidence `0.25`. `run_oty0_yolo_detection_stream_audit.py` calls `model.predict(...)` with the configured class ids and writes each surviving YOLO box as a row with `det_id`, `class_id`, `class_name`, confidence, and bbox fields.

There is no repository-specific same-frame duplicate cleanup after the YOLO result is returned. There is also no explicit secondary NMS, cross-class overlap reconciliation, partial/full grouping, or neighbor competition labeling in OTY0. YOLO may perform its own internal model-side NMS, but this repo does not add an OTY0 postprocess layer that can explain high-overlap cross-class boxes.

Result: high-overlap same-frame boxes that survive YOLO enter the OTY0 table as separate detector observations.

### OTY1 Tracklet Construction

OTY1 reads OTY0 rows through `normalize_detections`. It does not collapse same-frame boxes before association.

`tracklet_builder.py` creates candidate edges only from earlier detections to later detections. An edge is within limits only if:

- frame gap is not greater than `max_frame_gap`;
- class is consistent by `class_name` or `class_id`;
- center distance is within `max_center_distance_px * sqrt(gap)`;
- bbox size consistency is at least `min_size_consistency`.

The audit score also uses center distance, size consistency, bbox IoU, frame gap, and minimum confidence. Selected edges are chosen by best outgoing and best target edge, then connected components are built by union-find.

Same-frame conflicts, multiple feasible edges, near neighbors, and boundary contact are recorded as ambiguity or review indicators after component construction. They are not used as a pre-association cleanup layer.

Result: class mismatch is a hard OTY1 edge blocker. One large/one small partial/full pair can split if size consistency is low, if it is same-frame, or if competing geometry prevents a selected edge.

### OTY1a Fragment Merge

OTY1a builds endpoint profiles from OTY1 components and state rows, then scans bounded tracklet pairs. It evaluates:

- temporal relation and forward gap;
- endpoint center distance;
- motion-predicted endpoint distance;
- bridge IoU proxy;
- endpoint area ratio and aspect ratio;
- bottom-y delta;
- endpoint class consistency;
- boundary-contact counts;
- neighbor-ambiguity counts;
- shape transition and partial-to-full proxies.

The first hard status check in `_base_status` rejects class mismatch. Large gaps, motion inconsistency, and size/aspect inconsistency can also reject. Partial/full transition can become a candidate only as review evidence, not identity proof. Multiple positive candidate edges are relabeled as `ambiguous_competing_merge`.

Result: OTY1a can record partial/full and shape transition candidates, but it does not override class mismatch and does not perform automatic merge.

### OTY1t ByteTrack

OTY1t replays OTY0 detections through ByteTrack. The local wrapper groups detections by frame, builds a single `ByteTrackResultAdapter` per frame, and passes all frame detections into `tracker.update(...)` together. The adapter includes xyxy boxes, confidences, and class ids.

The local code does not split ByteTrack runs by class and does not perform an OTY0/OTY1 pre-tracker same-frame grouping step. It records:

- assigned detections as tracked rows;
- unassigned frame detections as `unmatched_detection`;
- `track_lost` when a previously active tracker id is absent in the current frame;
- `track_reactivated` when a tracker id reappears after a gap;
- `low_score_recovery` when a low-score detection remains associated;
- posthoc `duplicate_track_overlap` when two active tracker hypotheses overlap or have close centers;
- posthoc `fragment_bridge` and `possible_id_switch` when successive track endpoints are close.

Result: duplicate-overlap and possible switch events are diagnostic after tracker association. They do not clean the observations before ByteTrack. Class conflict remains unresolved before tracker input; the wrapper passes class ids but does not itself define a cross-class duplicate policy.

### P4/P4G Object Hypothesis

P4G resolves latest OTY0, OTY1, OTY1a, and OTY1t artifacts per scene, then builds same-frame observation clusters, tracker bbox provenance, generalized object hypotheses, object-frame state rows, and orphan observations.

The current same-frame observation cluster helper links observations only when class labels match and bbox IoU, center distance, or containment is sufficient. Cross-class high-overlap duplicates are therefore not grouped by the current P4G cluster logic. Cluster roles can identify `same_object_duplicate_candidates`, `partial_full_observation_cluster`, `ambiguous_multi_vehicle_cluster`, `edge_truncation_cluster`, and `detector_artifact_cluster`, but these roles are review-safe evidence only.

`build_generalized_object_hypotheses` uses each tracker track as the main object-hypothesis anchor, attaches same-frame secondary observations only when they are not assigned to a different tracker id, adds attachable OTY1a fragment-edge context, and marks multi-vehicle conflict when cluster or tracker conflicts appear. It emits `object_hypothesis_type`, `recommended_use_for_oty2`, `identity_status`, and `review_required`.

Result: P4G is the current uncertainty handoff layer. It can describe secondary observations, partial/full transitions, duplicate observations, and multi-vehicle risk, but it does not solve observation cleanup before tracking.

## Required Question Answers

1. Does OTY0 currently handle same-frame duplicate dedup, secondary NMS, or class-conflict handling?

No repository-specific layer does this after YOLO output. OTY0 writes surviving YOLO rows. The only explicit filtering is configured class selection and confidence.

2. If same-frame boxes highly overlap but classes differ, how do they enter OTY1 / ByteTrack?

They enter as separate OTY0 rows. OTY1 will reject cross-frame edges between different classes as `class_mismatch`. OTY1t passes all same-frame rows into the tracker replay adapter together, with class ids included, but without local cross-class grouping or conflict resolution.

3. Is ByteTrack input class-filtered or tracked per class?

It is class-filtered upstream by OTY0 to configured vehicle classes, but not tracked per class in local OTY1t code. OTY1t calls ByteTrack once per frame with all detections in the frame.

4. Can class mismatch prevent fragments that may be the same vehicle from merging?

Yes for OTY1 and OTY1a. OTY1 marks class mismatch as outside limits, so such detections will not connect into the same OTY1 component. OTY1a rejects class-mismatched fragment edges. P4G same-frame cluster linkage also requires matching class labels, so cross-class duplicate-like pairs can stay separate or orphaned.

5. Can one large and one small partial/full box become independent targets?

Yes. There is no pre-tracker partial/full grouping. OTY1 can split them through same-frame separation, size inconsistency, class mismatch, or competing geometry. OTY1a and P4G may label partial/full evidence later, but only as review-safe hypothesis context.

6. Which geometry conditions does OTY1 tracklet construction use?

OTY1 uses forward frame gap, class consistency, center distance with a sqrt-gap limit, bbox IoU for scoring, size consistency, confidence, and neighbor ambiguity. It chooses best candidate edges before building connected components.

7. How does OTY1a fragment merge handle class mismatch, gap, motion, size/aspect, and overlap?

Class mismatch is rejected. Forward gap larger than `max_forward_gap` is rejected. Endpoint/motion inconsistency is rejected when both endpoint and motion distances are too large and bridge IoU is low. Area/aspect inconsistency is rejected unless shape transition evidence is strong enough to become review context. Overlap/bridge IoU contributes to score and can support shape or partial/full review candidates.

8. How does OTY1t ByteTrack handle unmatched detections, duplicate-overlap, lost/reactivated?

Unassigned detections are written as `unmatched_detection` rows. Lost and reactivated tracks are emitted as events based on active tracker ids across frames. Duplicate-overlap is detected after tracking between same-frame active tracker hypotheses using IoU or center-distance thresholds. These are diagnostics, not pre-tracker normalization.

9. How does P4G convert tracker hypotheses into object hypotheses?

P4G treats each tracker track as a main hypothesis anchor, maps its detections to OTY1 tracklets, pulls same-frame observation clusters and OTY1a related edges as secondary context, records orphan observations, computes support and uncertainty fields, then emits object hypotheses and object-frame state rows. It labels review and uncertainty states but does not confirm identity.

10. Where is the minimal mechanism insertion point?

Primary recommendation: `INSERT_AFTER_OTY0_BEFORE_TRACKING`.

The first safe insertion point is after OTY0 has produced detector observations and before OTY1/OTY1t consume them. At that point the mechanism can add a diagnostic observation-cleanup/context layer for same-frame multi-box grouping labels, class-instability flags, partial/full competition flags, and state tags without changing detector outputs or merging boxes.

Secondary hooks:

- `INSERT_INSIDE_OTY1_PRE_ASSOCIATION` is appropriate only after the after-OTY0 observation context is defined, so OTY1 can consume context without silently rewriting detections.
- `INSERT_AS_DIAGNOSTIC_ONLY_BEFORE_OTY1A` is appropriate for carrying fragment-relation context, but it is later than the main failure source because OTY1 and ByteTrack have already consumed dirty observations.

Do not insert first inside ByteTrack. The tracker receives dirty observations, and patching tracker behavior first would hide whether the break is detection postprocess, class conflict, partial/full competition, or true association failure.

## Minimal Safe Implementation Recommendation

The minimum safe next implementation, when implementation is explicitly authorized, should be diagnostic-only:

1. Add an OTY0-post observation context table that preserves every raw detection row and adds same-frame grouping diagnostics, state tags, class-conflict flags, partial/full competition flags, and neighbor-competition flags.
2. Do not delete, merge, or rewrite OTY0 boxes.
3. Do not output final boxes or identity.
4. Feed the context into OTY1/OTY1t only as review-safe metadata at first.
5. Only later decide whether a global normalization rule can safely influence association.

Recommended conclusion: `INSERT_AFTER_OTY0_BEFORE_TRACKING`.

## No-Overstep Check

This report did not:

- modify runtime code;
- run OTY0, OTY1, OTY1a, OTY1t, P4, or P4G;
- create or modify outputs runtime artifacts;
- create final annotations;
- create revised GT;
- create final boxes;
- create selector/ranking output;
- tune thresholds;
- switch tracker;
- enter SAR pairing or support audit;
- use SAR GT or SAR image observation for optical runtime identity;
- claim tracker ID, P4 ID, or P4G object ID as identity truth.
