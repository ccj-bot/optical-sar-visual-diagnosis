# OTY2 Temporal Backbone Route Reset

Updated: 2026-07-05

This document is a route-control note for future OTY2 sessions. It freezes the current correction after the OTY1t standard MOT backbone closure and prevents the next session from treating component grouping, pair suppression, or sliding-window chaining as the primary temporal mechanism.

## Current Route Reset

- The current stage remains OTY2 posthoc mechanism diagnosis, not OTY3.
- The current primary problem is optical temporal object-stream continuity.
- Adjacent-frame association, multi-box observations, box shape changes, short fragments, and short gaps are standard MOT / tracklet stitching problems.
- The repository already has an OTY1t standard MOT route. Future work must not treat a mature MOT baseline as a new idea.
- The next mechanism must close the existing OTY1t route with real optical appearance and ReID-aware tracklet stitching, rather than continuing to self-build window/component mechanisms as the main association layer.

## Current Proven Facts

The closure report `reports/oty2/oty2_oty1t_standard_mot_backbone_closure_20260705_110947.md` established the following facts:

- ByteTrack and BoT-SORT adapters exist and are runnable.
- BoT-SORT ran on `GM_RM011`, `GM_RM019`, and `GM_RM017`, for both raw and normalized active-only inputs.
- Current BoT-SORT is configured with `with_reid=False`.
- Current tracker replay uses `_blank_image(frame_rows)`, so no real optical appearance enters the current MOT route.
- The current best continuity candidate for `GM_RM011` is BoT-SORT normalized active-only.
- BoT-SORT normalized active-only improves `GM_RM011` unmatched rate, track count, duplicate-overlap, possible ID-switch, and median/mean track length.
- `GM_RM011` still has fragmented hypotheses. This is not clean identity and not a final object stream.
- The current closure conclusion is `OTY1T_STANDARD_MOT_PARTIAL_NEEDS_REID_STITCHING`.

## Correct Main Architecture

The corrected OTY2 optical temporal route is:

```text
OTY0 detections
-> OTY1t standard MOT backbone
-> real optical crop appearance / ReID embeddings
-> ReID-aware tracklet stitching
-> optical temporal object hypothesis
-> later SAR/support only after optical stream mechanism is validated
```

Required positioning:

- OTY1t MOT/ReID is the main temporal backbone candidate.
- OTY1/OTY1a remains comparison, fallback, and fragment-relation context.
- Component grouping is not the main tracker.
- Sliding-window local continuity is not the main tracker.
- Normalized active-only input is not a mainline replacement.
- Tracker ID, component ID, window chain, P4G object ID, and stitch candidate ID are hypotheses or diagnostic handles, not identity truth.

## Role Of Existing Component / Window Work

Recent OTY2 optical-stream work should be kept, but demoted to its correct role:

- Pretracking observation grouping explains dirty detection observations.
- Pair-level normalization is a bounded duplicate-pressure probe only.
- Component grouping is a blocker/explainer and row-policy context, not a tracker.
- Sliding-window local continuity is bounded local evidence, not an object stream.
- Component grouping and sliding-window outputs may support ReID-aware stitching as blockers, explainers, or local evidence.
- They must not replace the OTY1t MOT backbone.

Required rule:

```text
component/window outputs are post-MOT evidence and safety constraints, not the primary temporal association mechanism.
```

## Next Priority

There is one next priority: prepare a ReID-aware tracklet stitching probe around the existing OTY1t route.

Step 1: build or probe real optical crop embedding extraction.

- Input: OTY0 detection table.
- Use `optical_path` and bbox fields.
- Output ignored `det_id -> embedding` artifacts.
- Do not generate final boxes.
- Do not modify OTY0 runtime or detector configuration.

Step 2: build a ReID-aware tracklet stitching probe.

- Input: OTY1t BoT-SORT and ByteTrack tracks.
- Use endpoint and representative midpoint crops.
- Use motion, gap, bbox geometry, size/aspect, bottom-y, and class context.
- Use real appearance similarity from optical crops.
- Use component blockers and component dirty-detection context.
- Use sliding-window local evidence only as supporting evidence.
- Output stitch candidates, not identity truth.

## Explicit Anti-Patterns

Do not continue down these routes as the next main mechanism:

- Do not continue sliding-window graph construction as the next main mechanism.
- Do not keep adding component fields without testing ReID-aware stitching.
- Do not treat normalized active-only input as clean tracker input.
- Do not treat tracker ID, component ID, window chain, P4G object ID, or stitch candidate ID as identity truth.
- Do not re-run YOLO detector comparison as the main next step.
- Do not run SAR pairing/support before the optical temporal backbone is stabilized.
- Do not promote `GM_RM011` into the clean `215` pool.
- Do not create final annotation, revised GT, final boxes, selector/ranking output, or weighted fusion.

## Next Codex Task Template

Recommended next task:

```text
Run OTY0 detection crop embedding probe for GM_RM011/GM_RM019/GM_RM017 and prepare ReID-aware tracklet stitching input schema.
```

Do not run this task as part of this route-reset document commit.

## Boundary Statement

This route reset does not run experiments, add tracker probes, implement ReID, modify runtime scripts, tune thresholds, enter SAR pairing/support audit, create final annotations, create revised GT, create final boxes, create selector/ranking output, use weighted fusion, claim identity truth, or promote `GM_RM011` into the clean `215` pool.
