# OTY2 Optical Timeline Graph Input Contract

Timestamp: `20260705_175222`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Input HEAD expectation: includes `4ca05aa Audit same-vehicle referent consistency`

## Boundary

This artifact defines the input contract for a diagnostic optical vehicle timeline graph. It does not create final annotation, revised GT, final boxes, SAR pairing/support, selector/ranking output, training data, or identity truth.

The graph is an optical-side intermediate layer. It can later feed visualization and SAR migration planning only as a soft diagnostic prior.

## Source Tables

- Same-vehicle referent audit: `reports\oty2\samples\oty2_same_vehicle_referent_consistency_summary_20260705_165636.csv`
- GM_RM011 contrast audit: `reports\oty2\samples\oty2_gm011_optical_vehicle_timeline_contrast_summary_20260705_235500.csv`
- BoT-SORT normalized_active segment index: `outputs\oty2\tracklet_embedding_aggregation_probe_20260705_193000\tracklet_embedding_index.csv`
- BoT-SORT to detection/crop linkage: `outputs\oty2\embedding_track_linkage_probe_20260705_183000\embedding_track_linkage_rows.csv`
- Crop/frame path index: `outputs\oty2\crop_reid_embedding_probe_20260705_170500\crop_reid_embedding_index.csv`

The OTY0 detection table provides `scene + optical_frame_num + det_id + bbox + optical_path`. The tracker linkage table provides `scene + tracker_name + tracker_variant + track_id + segment_id` through the BoT-SORT normalized_active stream used by the visual audits.

## ID Contract

Raw detection ID:

```text
scene + optical_frame_num + det_id
```

This points to one detector box in one optical frame.

Tracker fragment ID:

```text
scene + tracker_name + tracker_variant + track_id + segment_id
```

This points to one algorithmic short track fragment. `track_id` is not a physical vehicle identity.

Diagnostic vehicle ID:

```text
diagnostic_vehicle_id
```

Examples in this round are `GM_RM017_V001`, `GM_RM017_V002`, and `GM_RM011_V001`. This ID is a diagnostic intermediate referent, not final GT, final annotation, or human identity truth.

## Output Tables

- Nodes: `reports\oty2\samples\oty2_optical_timeline_graph_nodes_20260705_175222.csv` with `18` rows.
- Edges: `reports\oty2\samples\oty2_optical_timeline_graph_edges_20260705_175222.csv` with `10` rows.
- Video render manifest: `reports\oty2\samples\oty2_optical_timeline_video_render_manifest_20260705_175222.csv` with `311` rows.

Edge counts:

| edge_type | count |
| --- | ---: |
| `forbidden_edge` | 3 |
| `non_vehicle_exclusion` | 1 |
| `strong_same_vehicle_edge` | 2 |
| `weak_same_vehicle_edge` | 4 |

Render status counts:

| display_status | count |
| --- | ---: |
| `forbidden_not_rendered` | 16 |
| `non_vehicle_not_rendered` | 9 |
| `review_only` | 77 |
| `strong_timeline` | 85 |
| `weak_timeline` | 124 |

## Strong, Weak, Forbidden

Strong edges can share the same `diagnostic_vehicle_id` in visualization:

- `GM_RM011_N001 -> GM_RM011_N002`
- `GM_RM011_N004 -> GM_RM011_N005`

Weak edges can share a diagnostic ID only with a visible weak/review label or remain separate if the renderer cannot show uncertainty:

- `GM_RM011_N003 -> GM_RM011_N004`
- `GM_RM011_N008 -> GM_RM011_N009`
- `GM_RM011_N010 -> GM_RM011_N011`
- `GM_RM011_N012 -> GM_RM011_N013`

Forbidden edges must never be merged:

- `GM_RM017_N001 -> GM_RM017_N003`
- `GM_RM011_N003 -> GM_RM011_N006`
- `GM_RM011_N007 -> GM_RM011_N003`

The non-vehicle exclusion is represented as a unary exclusion edge on `GM_RM017_N005`.

## Video Rendering Rules

The main display label is `diagnostic_vehicle_id`, not `track_id`. Track IDs can be displayed only as auxiliary text.

For each `scene + optical_frame_num + diagnostic_vehicle_id`, the manifest keeps one primary box. If multiple candidate boxes exist, the selection order is:

1. stronger display status;
2. larger reasonable box area;
3. linkage to a diagnostic node;
4. continuity with the surrounding segment.

The manifest explicitly marks forbidden and non-vehicle rows as `forbidden_not_rendered` or `non_vehicle_not_rendered`; a renderer must skip them by default.

## Required Answers

1. A unified input contract is needed because detections, tracker output, same-vehicle audit decisions, and render labels are different evidence layers.
2. Raw detections identify boxes; tracker output identifies algorithmic fragments; same-vehicle audit identifies referent relations; `diagnostic_vehicle_id` is the diagnostic vehicle-time fragment used by the graph.
3. `track_id` cannot be vehicle identity because it can split, bridge, or switch targets.
4. Crop features cannot be vehicle identity because a crop is box content and may contain only a vehicle part, background, or an edge sliver.
5. `diagnostic_vehicle_id` is generated from scene-scoped visual referent groups: strong fragments get stable IDs, weak fragments may share IDs with uncertainty tags, forbidden/non-vehicle fragments get exclusion/context IDs.
6. Strong edges are short-gap, full-frame-confirmed same-vehicle continuities.
7. Weak edges are plausible part-state transitions or edge cases that need review labels.
8. Forbidden edges are competitor switches, false dark-car merges, or spatial/appearance bridges where same referent cannot be established.
9. Rendering preserves one primary box per vehicle per frame through the manifest deduplication rule.
10. When multiple candidates exist, the primary box is selected by diagnostic attachment, status strength, box quality, area reasonableness, and continuity.
11. The graph must not force uniqueness for thin edge crops, unresolved competitors, non-vehicle content, or forbidden edges.
12. SAR can later consume only clear or reviewed diagnostic fragments as optical-side soft prior planning input; this round does not run SAR consumption.
13. Final boxes or revised GT are not allowed.
14. Full automatic annotation is not allowed.

## Render Readiness

The render manifest contains `scene`, `optical_frame_num`, `diagnostic_vehicle_id`, source tracker fields, source detection IDs, and bounding boxes. It can drive a renderer that resolves frame paths from the known optical frame root or frame table. This round provides the manifest and a renderer interface only; it does not generate mp4 or frame outputs.

## Conclusion

```text
OPTICAL_TIMELINE_GRAPH_INPUT_CONTRACT_READY_FOR_RENDERING
```
