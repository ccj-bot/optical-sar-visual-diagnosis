# OTY2 Crop ReID Embedding Probe

Timestamp: `20260705_164500`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Git commit before changes: `6eb2737`

## Boundary

This probe is limited to OTY0 real optical crop learned-embedding readiness for the next ReID-aware tracklet stitching input. It does not implement final stitching, modify OTY0/OTY1/OTY1a/OTY1t runtime, tune tracker parameters, replace detector/tracker, run SAR pairing/support, generate final annotation, generate revised GT, generate final boxes, generate selector/ranking output, generate weighted fusion output, generate identity truth, or promote `GM_RM011` into clean `215`.

Embedding arrays, if produced, are written only under ignored `outputs/` and are not committed. Detection IDs are always reported as `det_id_ignored` and must not be treated as identity truth.

## Command

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_crop_reid_embedding_probe.py --scenes GM_RM011 GM_RM019 GM_RM017 --output-root outputs --timestamp 20260705_164500 --device cpu --reid-backend torchvision_resnet18 --reid-weights D:/models/torchvision/resnet18-f37072fd.pth --checked-weight-candidate D:/models/torchvision/resnet18-f37072fd.pth --checked-weight-candidate D:/profile/models/torchvision/resnet18-f37072fd.pth --checked-weight-candidate D:/models/reid/resnet18-f37072fd.pth
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
| GM_RM011 | 422 | 422 | 0 | 0 | torchvision_resnet18_weights_missing |  |  | False | D:\models\torchvision\resnet18-f37072fd.pth | False |  | CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING |
| GM_RM019 | 334 | 334 | 0 | 0 | torchvision_resnet18_weights_missing |  |  | False | D:\models\torchvision\resnet18-f37072fd.pth | False |  | CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING |
| GM_RM017 | 215 | 215 | 0 | 0 | torchvision_resnet18_weights_missing |  |  | False | D:\models\torchvision\resnet18-f37072fd.pth | False |  | CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING |

Summary CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_crop_reid_embedding_probe_summary_20260705_164500.csv`
Schema preview CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_crop_reid_embedding_schema_preview_20260705_164500.csv`

## Backend

- requested backend: `torchvision_resnet18`
- backend used: `torchvision_resnet18_weights_missing`
- backend status: `weights_missing`
- learned backend used: `False`
- reason: --reid-weights does not exist: D:\models\torchvision\resnet18-f37072fd.pth
- import status: `{"torch": true, "torchvision": true, "torchreid": false, "PIL": true, "cv2": true, "numpy": true}`
- external weight path: `D:\models\torchvision\resnet18-f37072fd.pth`
- checked weight candidates: `["D:/models/torchvision/resnet18-f37072fd.pth", "D:/profile/models/torchvision/resnet18-f37072fd.pth", "D:/models/reid/resnet18-f37072fd.pth"]`
- weight downloaded: `False`
- weight committed: `False`

When `torchvision_resnet18` is used, it is an ImageNet learned appearance feature baseline, not a dedicated vehicle ReID model. It is allowed only with an explicit local/external ResNet18 weight path and must not be described as a ReID-specific model.

## Missing Weight Setup

- missing external weight file: `D:\models\torchvision\resnet18-f37072fd.pth`
- no embeddings were computed because a valid explicit external weight file was unavailable
- no download was attempted and no weight file was committed
- exact rerun command after placing the external weight file at the requested path or replacing `--reid-weights` with another external path:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_crop_reid_embedding_probe.py --scenes GM_RM011 GM_RM019 GM_RM017 --output-root outputs --timestamp 20260705_164500 --device cpu --reid-backend torchvision_resnet18 --reid-weights D:/models/torchvision/resnet18-f37072fd.pth --checked-weight-candidate D:/models/torchvision/resnet18-f37072fd.pth --checked-weight-candidate D:/profile/models/torchvision/resnet18-f37072fd.pth --checked-weight-candidate D:/models/reid/resnet18-f37072fd.pth
```


## Required Answers

1. Did the previous clean crop extraction result remain valid?

- `GM_RM011`: `422/422` crops extractable, embedding_failed=`0`.
- `GM_RM019`: `334/334` crops extractable, embedding_failed=`0`.
- `GM_RM017`: `215/215` crops extractable, embedding_failed=`0`.

2. Which learned embedding backend was used?

`torchvision_resnet18_weights_missing`. Learned backend used: `False`.

3. Was the backend a dedicated ReID model or an ImageNet feature baseline?

`torchvision_resnet18` was requested, but no baseline embeddings were produced because valid external weights were unavailable.

4. Was any weight file downloaded?

`False`. The script does not download weights.

5. Was any weight file committed?

`False`. No weight path is staged or committed by this probe.

6. What external weight path was used?

`D:\models\torchvision\resnet18-f37072fd.pth`

7. How many embeddings were computed per scene?

- `GM_RM011`: `0`
- `GM_RM019`: `0`
- `GM_RM017`: `0`

8. What is the embedding dimension?

``

9. Were embeddings L2-normalized?

``

10. Were any crops skipped or failed?

- `GM_RM011`: crop_failed=`0`, reasons=`{}`.
- `GM_RM019`: crop_failed=`0`, reasons=`{}`.
- `GM_RM017`: crop_failed=`0`, reasons=`{}`.

11. Where are the uncommitted embedding artifacts located?

- output directory: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2\crop_reid_embedding_probe_20260705_164500`
- feature artifact: `none; no learned backend available`
- index artifact: `none; no learned backend available`

12. What exact detection-level embedding schema was produced?

`row_uid`, `scene`, `frame_id`, `det_id_ignored`, `source_detection_table`, `optical_path`, `bbox_xyxy_original`, `bbox_xyxy_clamped`, `bbox_status`, `crop_w`, `crop_h`, `crop_area`, `embedding_backend`, `embedding_dim`, `embedding_l2_normed`, `embedding_array_key`, `embedding_artifact_path_uncommitted`, `weights_path_external`, `created_at`.

13. How should these embeddings connect to OTY1t BoT-SORT/ByteTrack tracks?

Detection embeddings do not define identity truth. Detection IDs are ignored for identity. Embeddings connect to OTY1t BoT-SORT/ByteTrack tracks through same-scene/same-frame box association. If OTY1t replay preserves source detection row IDs, use direct linkage. Otherwise, use deterministic IoU matching between tracker boxes and OTY0 detection boxes in the same scene/frame. Only after detection-to-track linkage is validated should tracklet-level embeddings be aggregated. Candidate stitching pairs are only proposals for review/probe, not final identity assignments.

14. Why this still does not produce final identity truth, final annotations, or clean-215 promotion.

This probe only checks whether real optical crop embeddings can be generated and indexed. It does not merge tracker hypotheses, does not set stitch decisions, does not emit final object identities, does not write annotation or SAR-support outputs, and does not promote `GM_RM011` into the clean `215` pool.

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
