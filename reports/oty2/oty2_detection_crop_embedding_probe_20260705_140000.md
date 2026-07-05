# OTY2 Detection Crop Embedding Probe

Timestamp: `20260705_140000`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Git commit before changes: `7700ba4`

## Boundary

This diagnostic validates OTY0 detection crop extraction from real optical images and checks local embedding-backend availability. It does not modify OTY0/OTY1/OTY1a/OTY1t runtime, tune tracker parameters, replace detector/tracker, run SAR pairing/support, generate final boxes, generate identity truth, or promote `GM_RM011` into clean `215`.

No crop images, embedding arrays, model weights, atlas outputs, final annotations, revised GT, runtime predictions, selector/ranking outputs, weighted fusion artifacts, or SAR pairing/support outputs were written by the script.

## Command

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_detection_crop_embedding_probe.py --scenes GM_RM011 GM_RM019 GM_RM017 --output-root outputs --timestamp 20260705_140000
```

## Data Tables Discovered And Used

| scene_requested | table_scene | row_count_for_scene | path | selection_policy |
| --- | --- | --- | --- | --- |
| GM_RM011 | GM_RM011 | 422 | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv | direct_oty0_output_latest_scene_match |
| GM_RM019 | GM_RM019 | 334 | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv | direct_oty0_output_latest_scene_match |
| GM_RM017 | GM_RM017 | 215 | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv | direct_oty0_output_latest_scene_match |

## Identifier And BBox Schema

### `GM_RM011`

- source table: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv`
- scene id field: `scene`
- frame id field: `optical_frame_num`
- detection id field, intentionally ignored as identity: `det_id`
- optical path field: `optical_path`
- bbox schema counts: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 422}`

### `GM_RM019`

- source table: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv`
- scene id field: `scene`
- frame id field: `optical_frame_num`
- detection id field, intentionally ignored as identity: `det_id`
- optical path field: `optical_path`
- bbox schema counts: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 334}`

### `GM_RM017`

- source table: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv`
- scene id field: `scene`
- frame id field: `optical_frame_num`
- detection id field, intentionally ignored as identity: `det_id`
- optical path field: `optical_path`
- bbox schema counts: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 215}`

## Per-Scene Summary

| scene | rows_total | rows_with_optical_path | image_exists | image_missing | image_unreadable | bbox_present | bbox_parse_failed | bbox_invalid_geometry | bbox_fully_out_of_bounds | bbox_partially_out_of_bounds_clamped | crop_extractable | crop_failed | embedding_backend | embedding_available | embedded_count | conclusion_scene |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | 422 | 422 | 422 | 0 | 0 | 422 | 0 | 0 | 0 | 0 | 422 | 0 | missing_local_embedding_backend | False | 0 | DETECTION_CROP_EXTRACTION_READY_EMBEDDING_BACKEND_MISSING |
| GM_RM019 | 334 | 334 | 334 | 0 | 0 | 334 | 0 | 0 | 0 | 0 | 334 | 0 | missing_local_embedding_backend | False | 0 | DETECTION_CROP_EXTRACTION_READY_EMBEDDING_BACKEND_MISSING |
| GM_RM017 | 215 | 215 | 215 | 0 | 0 | 215 | 0 | 0 | 0 | 0 | 215 | 0 | missing_local_embedding_backend | False | 0 | DETECTION_CROP_EXTRACTION_READY_EMBEDDING_BACKEND_MISSING |

Small summary CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_detection_crop_embedding_probe_summary_20260705_140000.csv`

## Required Answers

1. Are `optical_path` values valid for `GM_RM011`, `GM_RM019`, and `GM_RM017`?

- `GM_RM011`: `422/422` rows have `optical_path`; `422` images exist; `0` missing; `0` unreadable.
- `GM_RM019`: `334/334` rows have `optical_path`; `334` images exist; `0` missing; `0` unreadable.
- `GM_RM017`: `215/215` rows have `optical_path`; `215` images exist; `0` missing; `0` unreadable.

2. Are bbox coordinates sufficient and in image bounds?

- `GM_RM011`: `422/422` bboxes present using `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 422}`; parse_failed=`0`, invalid_geometry=`0`, fully_out_of_bounds=`0`, partially_clamped=`0`.
- `GM_RM019`: `334/334` bboxes present using `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 334}`; parse_failed=`0`, invalid_geometry=`0`, fully_out_of_bounds=`0`, partially_clamped=`0`.
- `GM_RM017`: `215/215` bboxes present using `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 215}`; parse_failed=`0`, invalid_geometry=`0`, fully_out_of_bounds=`0`, partially_clamped=`0`.

3. How many detection crops can be extracted per scene?

- `GM_RM011`: `422`
- `GM_RM019`: `334`
- `GM_RM017`: `215`

4. How many fail due to missing image / invalid bbox / out-of-bounds box?

- `GM_RM011`: missing_image=`0`, invalid_bbox=`0`, out_of_bounds_or_clamped=`0`, crop_failed=`0`.
- `GM_RM019`: missing_image=`0`, invalid_bbox=`0`, out_of_bounds_or_clamped=`0`, crop_failed=`0`.
- `GM_RM017`: missing_image=`0`, invalid_bbox=`0`, out_of_bounds_or_clamped=`0`, crop_failed=`0`.

5. Which embedding backend is available locally without adding heavy committed assets?

`missing_local_embedding_backend`. Availability: `False`. Reason: torch/torchvision importable but cached resnet18-f37072fd.pth not found. Import facts: torch=`True`, torchvision=`True`, PIL=`True`, cv2=`True`.

6. What embedding schema should be used for ReID stitching?

- Detection-level embedding table fields: `scene`, `frame_id`, `det_id_ignored`, `optical_path`, `bbox_xyxy_original`, `bbox_xyxy_clamped`, `crop_w`, `crop_h`, `crop_status`, `embedding_backend`, `embedding_dim`, `embedding_l2_normed`, `embedding_artifact_path_uncommitted`, `source_detection_table`, `created_by_probe`, `created_at`.
- `det_id_ignored` must remain a source-row handle only; it must not be treated as identity truth.
- `embedding_artifact_path_uncommitted` should point to ignored/uncommitted local artifacts generated by a later embedding job, not to committed arrays.

7. How should embeddings connect to OTY1t BoT-SORT/ByteTrack tracks?

Embeddings connect to OTY1t BoT-SORT/ByteTrack tracks by frame-level detection association. The next probe should match tracker boxes and OTY0 detection boxes within the same `scene` and `frame_id` using exact source-row linkage if preserved, otherwise a deterministic IoU rule. It must not assume OTY0 detection id is identity.

8. What exact inputs will the next ReID-aware tracklet stitching probe need?

- OTY1t tracker replay output for BoT-SORT/ByteTrack, especially normalized active-only variants.
- Per-frame tracker boxes and track ids.
- OTY0 detection rows with `optical_path` and bbox.
- A deterministic same-scene/same-frame matching rule between tracker boxes and OTY0 detections, such as IoU or exact source-row linkage if already preserved.
- Detection crop embeddings generated from real optical images.
- Tracklet segmentation metadata: start/end frame, gaps, neighboring fragmented tracklets.
- Conservative thresholds for candidate stitch proposal only, not final identity truth.
- Review/report output showing candidate stitch pairs and evidence, without producing final annotation.

## Proposed ReID Stitching Schemas

Detection-level embedding table:

```text
scene
frame_id
det_id_ignored
optical_path
bbox_xyxy_original
bbox_xyxy_clamped
crop_w
crop_h
crop_status
embedding_backend
embedding_dim
embedding_l2_normed
embedding_artifact_path_uncommitted
source_detection_table
created_by_probe
created_at
```

Tracklet-level aggregation table:

```text
scene
tracker_name
tracker_variant
track_id
frame_start
frame_end
num_detections
linked_det_ids_ignored
linked_embedding_count
tracklet_embedding_policy
tracklet_embedding_artifact_path_uncommitted
motion_summary_path_or_inline_fields
source_tracker_replay
created_at
```

## Conclusion

```text
DETECTION_CROP_EXTRACTION_READY_EMBEDDING_BACKEND_MISSING
```
