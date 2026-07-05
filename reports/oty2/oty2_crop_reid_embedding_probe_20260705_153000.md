# OTY2 Crop ReID Embedding Probe

Timestamp: `20260705_153000`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Git commit before changes: `c348590`

## Boundary

This probe is limited to OTY0 real optical crop learned-embedding readiness for the next ReID-aware tracklet stitching input. It does not implement final stitching, modify OTY0/OTY1/OTY1a/OTY1t runtime, tune tracker parameters, replace detector/tracker, run SAR pairing/support, generate final annotation, generate revised GT, generate final boxes, generate selector/ranking output, generate weighted fusion output, generate identity truth, or promote `GM_RM011` into clean `215`.

Embedding arrays, if produced, are written only under ignored `outputs/` and are not committed. Detection IDs are always reported as `det_id_ignored` and must not be treated as identity truth.

## Command

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_crop_reid_embedding_probe.py --scenes GM_RM011 GM_RM019 GM_RM017 --output-root outputs --timestamp 20260705_153000 --device cpu
```

## Input Tables

| scene_requested | table_scene | row_count_for_scene | path | selection_policy |
| --- | --- | --- | --- | --- |
| GM_RM011 | GM_RM011 | 422 | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv | direct_oty0_output_latest_scene_match |
| GM_RM019 | GM_RM019 | 334 | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv | direct_oty0_output_latest_scene_match |
| GM_RM017 | GM_RM017 | 215 | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv | direct_oty0_output_latest_scene_match |

## Crop Extraction Check

The previous clean crop extraction result remained valid for this run: every selected OTY0 row in the three scenes produced an in-memory crop, with no crop failures.

| scene | rows_total | crop_extractable | embedding_computed | embedding_failed | embedding_backend | embedding_dim | embedding_l2_normed | learned_backend_used | weights_path_external | artifact_created_uncommitted | artifact_path_uncommitted | conclusion_scene |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | 422 | 422 | 0 | 0 | missing_learned_reid_backend |  |  | False |  | False |  | CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING |
| GM_RM019 | 334 | 334 | 0 | 0 | missing_learned_reid_backend |  |  | False |  | False |  | CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING |
| GM_RM017 | 215 | 215 | 0 | 0 | missing_learned_reid_backend |  |  | False |  | False |  | CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING |

Summary CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_crop_reid_embedding_probe_summary_20260705_153000.csv`
Schema preview CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_crop_reid_embedding_schema_preview_20260705_153000.csv`

## Backend

- requested backend: ``
- backend used: `missing_learned_reid_backend`
- backend status: `missing`
- learned backend used: `False`
- reason: no --reid-backend was provided; learned embeddings require explicit local/external weights
- import status: `{"torch": true, "torchvision": true, "torchreid": false, "PIL": true, "cv2": true, "numpy": true}`
- external weight path: ``
- weight downloaded: `False`
- weight committed: `False`

If `torchvision_resnet18` is used in a future run, it is an ImageNet feature baseline, not a dedicated ReID model. It should be used only when an explicit local/external ResNet18 weight path is provided and should not be described as a ReID-specific model.

## Required Answers

1. Did the previous clean crop extraction result remain valid?

- `GM_RM011`: `422/422` crops extractable, embedding_failed=`0`.
- `GM_RM019`: `334/334` crops extractable, embedding_failed=`0`.
- `GM_RM017`: `215/215` crops extractable, embedding_failed=`0`.

2. Which learned embedding backend was used?

`missing_learned_reid_backend`. Learned backend used: `False`.

3. Was any weight file downloaded?

`False`. The script does not download weights.

4. Was any weight file committed?

`False`. No weight path is staged or committed by this probe.

5. Where is the external weight path, if used?

`none`

6. How many embeddings were computed per scene?

- `GM_RM011`: `0`
- `GM_RM019`: `0`
- `GM_RM017`: `0`

7. What is the embedding dimension?

``

8. Are embeddings L2-normalized?

``

9. Were any crops skipped or failed after crop extraction?

- `GM_RM011`: crop_failed=`0`, reasons=`{}`.
- `GM_RM019`: crop_failed=`0`, reasons=`{}`.
- `GM_RM017`: crop_failed=`0`, reasons=`{}`.

10. Where are the uncommitted embedding artifacts located?

- output directory: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2\crop_reid_embedding_probe_20260705_153000`
- feature artifact: `none; no learned backend available`
- index artifact: `none; no learned backend available`

11. What schema should the next ReID-aware tracklet stitching probe consume?

- Detection-level embedding index: `row_uid`, `scene`, `frame_id`, `det_id_ignored`, `source_detection_table`, `optical_path`, `bbox_xyxy_original`, `bbox_xyxy_clamped`, `bbox_status`, `crop_w`, `crop_h`, `crop_area`, `embedding_backend`, `embedding_dim`, `embedding_l2_normed`, `embedding_array_key`, `embedding_artifact_path_uncommitted`, `weights_path_external`, `created_at`.
- Tracklet-level aggregation: `scene`, `tracker_name`, `tracker_variant`, `track_id`, `frame_start`, `frame_end`, `num_detections`, `linked_det_ids_ignored`, `linked_embedding_count`, `tracklet_embedding_policy`, `tracklet_embedding_artifact_path_uncommitted`, `motion_summary_path_or_inline_fields`, `source_tracker_replay`, `created_at`.

12. How do these detection-level embeddings connect to OTY1t BoT-SORT/ByteTrack tracks?

Detection embeddings do not define identity truth. Detection IDs are ignored for identity. Embeddings connect to OTY1t BoT-SORT/ByteTrack tracks through same-scene/same-frame box association. If OTY1t replay preserves source detection row IDs, use direct linkage. Otherwise, use deterministic IoU matching between tracker boxes and OTY0 detection boxes in the same scene/frame. Only after detection-to-track linkage is validated should tracklet-level embeddings be aggregated. Candidate stitching pairs are only proposals for review/probe, not final identity assignments.

13. Why this does not yet produce final identity truth or final annotations.

This probe only checks whether real optical crop embeddings can be generated and indexed. It does not merge tracker hypotheses, does not set stitch decisions, does not emit final object identities, and does not write annotation or SAR-support outputs.

## Next Stitching Input Contract

- OTY1t tracker replay output for BoT-SORT normalized active-only.
- Optionally ByteTrack replay output for comparison.
- Per-frame tracker boxes.
- Tracker `track_id`.
- Scene and frame id.
- OTY0 detection row/crop embedding index.
- Embedding artifact path.
- Same-frame detection-to-tracker box linkage.
- Tracklet segment metadata: start frame, end frame, number of detections, gaps, neighboring fragmented tracklets.
- Appearance similarity computation.
- Temporal compatibility gates.
- Motion/position compatibility gates.
- Report-only candidate stitch output.
- No final identity assignment.

## Per-Scene Crop Facts

### `GM_RM011`

- source table: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv`
- rows_total: `422`
- crop_extractable: `422`
- crop_failed: `0`
- bbox schemas: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 422}`

### `GM_RM019`

- source table: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv`
- rows_total: `334`
- crop_extractable: `334`
- crop_failed: `0`
- bbox schemas: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 334}`

### `GM_RM017`

- source table: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv`
- rows_total: `215`
- crop_extractable: `215`
- crop_failed: `0`
- bbox schemas: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 215}`

## Conclusion

```text
CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING
```
