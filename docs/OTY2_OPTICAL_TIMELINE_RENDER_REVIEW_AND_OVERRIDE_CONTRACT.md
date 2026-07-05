# OTY2 Optical Timeline Render Review And Override Contract

Date: 2026-07-05
Repository: `D:/profile/research/optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Base closeout HEAD: `e4122c0 Document OTY2 optical timeline session closeout`

## Purpose

This stage prepares the optical diagnostic vehicle timeline for human video review and defines a manual override contract. It does not continue detector swap, does not enter SAR consumption, and does not generate final or revised annotation.

The contract answers one question:

```text
Can a reviewer express node, edge, interval, and render-only corrections for the diagnostic optical vehicle timeline without drawing final boxes?
```

The answer is yes, under the limits below.

## Current Timeline Inputs

The current graph input artifacts are:

| Role | Path | Current status |
| --- | --- | --- |
| Node table | `reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv` | 18 data rows |
| Edge table | `reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv` | 10 data rows |
| Render manifest | `reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv` | 311 data rows |
| Graph manifest builder | `tools/diagnostics/run_oty2_optical_timeline_graph_manifest.py` | existing builder; not rerun for detector/tracker work |
| Render script | `tools/visualization/render_optical_timeline_video.py` | existing renderer; skips forbidden/non-vehicle rows by default |
| Override schema | `configs/oty2_optical_timeline_override_schema.yaml` | new dry-run contract schema |
| Empty override template | `manifests/oty2_optical_timeline_override_template.csv` | new header-only CSV template |
| Override validator | `tools/diagnostics/validate_oty2_optical_timeline_overrides.py` | new dry-run validator |

Verified graph counts:

| Item | Count |
| --- | ---: |
| Nodes | 18 |
| Edges | 10 |
| Strong same-vehicle edges | 2 |
| Weak same-vehicle edges | 4 |
| Forbidden edges | 3 |
| Non-vehicle exclusions | 1 |
| Render manifest rows | 311 |
| Unique rendered scene/frame pairs | 198 |

Verified render manifest status counts:

| display_status | Count |
| --- | ---: |
| `strong_timeline` | 85 |
| `weak_timeline` | 124 |
| `review_only` | 77 |
| `forbidden_not_rendered` | 16 |
| `non_vehicle_not_rendered` | 9 |

These counts match the closeout contract.

## Smoke Render Check

The smoke render command is:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\visualization\render_optical_timeline_video.py --manifest reports\oty2\samples\oty2_optical_timeline_video_render_manifest_20260705_175222.csv --output-dir outputs\oty2\optical_timeline_render_smoke_20260705_175222
```

The smoke output path is:

```text
outputs/oty2/optical_timeline_render_smoke_20260705_175222/frames
```

Current smoke result:

```text
rendered_frames: 198
frames_dir: outputs\oty2\optical_timeline_render_smoke_20260705_175222\frames
```

The output path is ignored by `.gitignore` through `outputs/`. It produces rendered diagnostic PNG frames only and does not create tracked repo changes. The smoke check did not generate mp4, detector output, tracker replay, SAR output, final boxes, GT boxes, crops, embeddings, model weights, archives, or committed output artifacts.

## Render Review Readiness

The current render chain is sufficient to enter human video review:

1. The node table, edge table, and render manifest exist and are internally count-consistent.
2. The renderer can resolve the current manifest into 198 diagnostic frames.
3. Forbidden and non-vehicle manifest rows are present as diagnostic evidence but skipped by default in rendering.
4. Strong, weak, and review-only display states are visible through the manifest and renderer.
5. Smoke output stays under ignored `outputs/` and does not pollute the repo.

This readiness is limited to diagnostic video review. It is not readiness for SAR pairing/support, selector/ranking, final boxes, revised annotation, GT boxes, or detector replacement.

## Override Table Shape

Manual corrections are stored in one CSV table with a required `override_type` discriminator:

```text
node
edge
render
```

Every row is an event-level record. The row may also target a node, an edge, a frame interval, or render-only marker behavior through `override_scope`.

Required common fields:

```text
override_id
override_type
override_scope
scene_id
action
reason_code
review_status
note
```

Common optional fields:

```text
event_id
node_id
from_node_id
to_node_id
bs_id
seg_id
frame_start
frame_end
target_node_id
edge_strength
source_detection_id
evidence_frame_start
evidence_frame_end
confidence
```

The table is deliberately not a frame-by-frame annotation table. It cannot contain bbox coordinate columns.

## Node Overrides

Node overrides express state corrections for an existing diagnostic node or a bounded node interval.

Allowed node actions:

```text
keep_vehicle_node
exclude_non_vehicle
mark_bad_detection_node
mark_review_required
split_node
merge_node
```

Node override fields:

```text
override_id
override_type=node
override_scope=node|interval|event
scene_id
node_id
bs_id
seg_id
frame_start
frame_end
action
reason_code
confidence
review_status
note
```

Node overrides may:

- keep a diagnostic vehicle node;
- exclude a node as non-vehicle;
- mark a bad detection node;
- mark a bad frame or bad interval through `reason_code=bad_frame_unreadable`;
- mark a node as needing review;
- request a diagnostic split or merge for graph review.

Node overrides may not create final object IDs, final boxes, revised boxes, GT boxes, or SAR pairing rows.

## Edge Overrides

Edge overrides express reviewer decisions about a relation between existing diagnostic nodes.

Allowed edge actions:

```text
force_strong_connect
force_weak_connect
forbid_connect
downgrade_to_weak
upgrade_to_strong
mark_review_required
```

Edge override fields:

```text
override_id
override_type=edge
override_scope=edge|event
scene_id
from_node_id
to_node_id
action
edge_strength
reason_code
evidence_frame_start
evidence_frame_end
confidence
review_status
note
```

Edge overrides may:

- say this relation should be a strong connection;
- say this relation can only be a weak connection;
- forbid a relation;
- downgrade a strong-looking relation to weak;
- upgrade a weak relation only after review evidence supports it;
- mark a relation as review-required.

Edge overrides may not merge tracker identity as truth, produce a final trajectory, run SAR, or produce selector/ranking input.

## Render Overrides

Render overrides affect diagnostic visualization only. They can change what is displayed in the review video or frame render manifest, but they cannot create new coordinates or final labels.

Allowed render actions:

```text
hide_bad_box_for_render
select_diagnostic_primary_box
show_review_marker
show_forbidden_edge_marker
show_weak_edge_marker
show_non_vehicle_marker
```

Render override fields:

```text
override_id
override_type=render
override_scope=event|interval
scene_id
frame_start
frame_end
target_node_id
action
source_detection_id
reason_code
note
```

The action `select_diagnostic_primary_box` means only this:

```text
for diagnostic video rendering, choose an existing detection box as the primary displayed box
```

It does not mean final box selection. It must not introduce bbox coordinates. It must not generate final annotation, revised annotation, final boxes, or GT boxes.

## Allowed Override Effects

Manual override rows may affect:

```text
diagnostic node status
diagnostic edge relation
diagnostic bad-detection or bad-frame markers
diagnostic non-vehicle exclusion
diagnostic weak/strong/forbidden relation display
diagnostic primary box selection from existing detections
diagnostic review-required markers
regenerated diagnostic render manifest
diagnostic review report
```

## Forbidden Override Effects

Manual override rows must not:

```text
redraw final boxes frame by frame
write bbox coordinates
generate final annotation
generate revised annotation
generate final boxes
generate GT boxes
generate identity truth
run SAR pairing
run SAR support
run selector/ranking
advance SAR consumption
continue detector swap as mainline
run a YOLO detector probe
run tracker replay
commit outputs, videos, images, crops, embeddings, weights, archives, or large binaries
```

## Minimal Review Workflow

The intended acceptance flow is:

```text
raw node table / edge table / render manifest
-> diagnostic video or frame render
-> human fills override CSV
-> dry-run validate override CSV
-> apply override only to diagnostic timeline graph
-> regenerate diagnostic render manifest
-> rerender diagnostic video
-> generate diagnostic acceptance report
```

The "apply override" step is deliberately limited:

```text
allowed target: diagnostic timeline graph and diagnostic render manifest
forbidden target: final annotation, revised annotation, final boxes, GT boxes, SAR pairing/support, selector/ranking
```

## Dry-Run Validator

The validator command for the empty template is:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_optical_timeline_overrides.py --overrides manifests\oty2_optical_timeline_override_template.csv
```

The validator checks:

- required columns;
- allowed `override_type`, `override_scope`, `action`, `reason_code`, and `review_status`;
- node IDs against the current node table;
- edge endpoint node IDs against the current node table;
- optional existing edge-pair warnings;
- render `source_detection_id` against the current manifest when available;
- frame interval sanity;
- confidence range;
- forbidden coordinate or final-label columns.

The validator writes no files and applies no overrides.

## Current Stage Conclusion

```text
OTY2 optical timeline video review and manual override contract is ready for diagnostic human review.
```

This means the optical diagnostic render chain and review contract are ready. It does not mean the optical timeline is final, SAR-ready, or annotation-ready.
