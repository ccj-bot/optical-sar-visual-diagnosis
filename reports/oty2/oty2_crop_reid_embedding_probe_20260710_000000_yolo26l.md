# OTY2 Crop ReID Embedding Probe

Timestamp: `20260710_000000_yolo26l`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Git commit before changes: `cdc80af`

## Boundary

This probe is limited to OTY0 real optical crop learned-embedding readiness for the next ReID-aware tracklet stitching input. It does not implement final stitching, modify OTY0/OTY1/OTY1a/OTY1t runtime, tune tracker parameters, replace detector/tracker, run SAR pairing/support, generate final annotation, generate revised GT, generate final boxes, generate selector/ranking output, generate weighted fusion output, generate identity truth, or promote `GM_RM011` into clean `215`.

Embedding arrays, if produced, are written only under ignored `outputs/` and are not committed. Detection IDs are always reported as `det_id_ignored` and must not be treated as identity truth.

## Command

```powershell
D:\MINICONDA\envs\py311\python.exe tools/diagnostics/run_oty0_crop_reid_embedding_probe.py --scenes GM_RM011 GM_RM019 GM_RM017 --oty0-detection-table outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm011/oty0_yolo_detection_table.csv --oty0-detection-table outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm019/oty0_yolo_detection_table.csv --oty0-detection-table outputs/oty2_yolo26l_detector_quality_probe_20260704_231830/oty0_yolo_detection_stream_audit_yolo26l_gm_rm017/oty0_yolo_detection_table.csv --output-root outputs/oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000 --timestamp 20260710_000000_yolo26l --device cpu --reid-backend torchvision_resnet18 --reid-weights D:/models/torchvision/resnet18-f37072fd.pth --checked-weight-candidate D:/models/torchvision/resnet18-f37072fd.pth --external-weight-source https://download.pytorch.org/models/resnet18-f37072fd.pth --external-weight-acquisition-method preexisting_external_model_dir
```

## Input Tables

| scene_requested | table_scene | row_count_for_scene | path | selection_policy |
| --- | --- | --- | --- | --- |
| GM_RM011 | GM_RM011 | 413 | outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm011\oty0_yolo_detection_table.csv | explicit_cli_table |
| GM_RM019 | GM_RM019 | 288 | outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm019\oty0_yolo_detection_table.csv | explicit_cli_table |
| GM_RM017 | GM_RM017 | 215 | outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm017\oty0_yolo_detection_table.csv | explicit_cli_table |

## Crop Extraction Check

The previous clean crop extraction result remained valid for this run: every selected OTY0 row in the three scenes produced an in-memory crop, with no crop failures.

| scene | rows_total | crop_extractable | embedding_computed | embedding_failed | embedding_backend | embedding_dim | embedding_l2_normed | learned_backend_used | weights_path_external | artifact_created_uncommitted | artifact_path_uncommitted | conclusion_scene |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GM_RM011 | 413 | 413 | 413 | 0 | torchvision_resnet18_imagenet_feature_baseline | 512 | True | True | D:\models\torchvision\resnet18-f37072fd.pth | True | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embeddings.npz | LEARNED_APPEARANCE_BASELINE_READY_FOR_TRACKLET_STITCHING_INPUT |
| GM_RM019 | 288 | 288 | 288 | 0 | torchvision_resnet18_imagenet_feature_baseline | 512 | True | True | D:\models\torchvision\resnet18-f37072fd.pth | True | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embeddings.npz | LEARNED_APPEARANCE_BASELINE_READY_FOR_TRACKLET_STITCHING_INPUT |
| GM_RM017 | 215 | 215 | 215 | 0 | torchvision_resnet18_imagenet_feature_baseline | 512 | True | True | D:\models\torchvision\resnet18-f37072fd.pth | True | D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embeddings.npz | LEARNED_APPEARANCE_BASELINE_READY_FOR_TRACKLET_STITCHING_INPUT |

Summary CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_crop_reid_embedding_probe_summary_20260710_000000_yolo26l.csv`
Schema preview CSV: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_crop_reid_embedding_schema_preview_20260710_000000_yolo26l.csv`

## Backend

- requested backend: `torchvision_resnet18`
- backend used: `torchvision_resnet18_imagenet_feature_baseline`
- backend status: `available`
- learned backend used: `True`
- reason: torchvision ResNet18 ImageNet feature baseline loaded from explicit local/external weights; this is not a dedicated vehicle ReID model
- import status: `{"torch": true, "torchvision": true, "torchreid": false, "PIL": true, "cv2": true, "numpy": true}`
- external weight path: `D:\models\torchvision\resnet18-f37072fd.pth`
- external weight acquired/present before probe: `True`
- external weight source: `https://download.pytorch.org/models/resnet18-f37072fd.pth`
- external weight acquisition method: `preexisting_external_model_dir`
- external weight outside repo: `True`
- checked weight candidates: `["D:/models/torchvision/resnet18-f37072fd.pth"]`
- probe automatic weight download: `False`
- weight committed: `False`

When `torchvision_resnet18` is used, it is an ImageNet learned appearance feature baseline, not a dedicated vehicle ReID model. It is allowed only with an explicit local/external ResNet18 weight path and must not be described as a ReID-specific model.


## Required Answers

1. Was an external weight downloaded/acquired?

`True`. Source: `https://download.pytorch.org/models/resnet18-f37072fd.pth`. Acquisition method: `preexisting_external_model_dir`. The probe itself did not perform automatic weight download: `False`.

2. Where is the external weight path?

`D:\models\torchvision\resnet18-f37072fd.pth`

3. Is the weight outside the repo?

`True`. Repository: `D:\profile\research\optical-sar-visual-diagnosis`.

4. Was any weight file committed?

`False`. No weight path is staged or committed by this probe.

5. Which backend was used?

`torchvision_resnet18_imagenet_feature_baseline`. Learned backend used: `True`.

6. Is this backend a dedicated ReID model or an ImageNet learned appearance baseline?

`torchvision_resnet18` is an ImageNet learned appearance feature baseline, not a dedicated ReID model.

7. Did the previous clean crop extraction result remain valid?

- `GM_RM011`: `413/413` crops extractable, embedding_failed=`0`.
- `GM_RM019`: `288/288` crops extractable, embedding_failed=`0`.
- `GM_RM017`: `215/215` crops extractable, embedding_failed=`0`.

8. How many embeddings were computed per scene?

- `GM_RM011`: `413`
- `GM_RM019`: `288`
- `GM_RM017`: `215`

9. What is the embedding dimension?

`512`

10. Are embeddings L2-normalized?

`True`

11. Were any crops skipped or failed?

- `GM_RM011`: crop_failed=`0`, reasons=`{}`.
- `GM_RM019`: crop_failed=`0`, reasons=`{}`.
- `GM_RM017`: crop_failed=`0`, reasons=`{}`.

12. Where are the uncommitted embedding artifacts located?

- output directory: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l`
- feature artifact: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embeddings.npz`
- index artifact: `D:\profile\research\optical-sar-visual-diagnosis\outputs\oty2_wgv3_3a_yolo26l_embedding_source_20260710_000000\oty2\crop_reid_embedding_probe_20260710_000000_yolo26l\crop_reid_embedding_index.csv`

13. What exact detection-level embedding schema was produced?

`row_uid`, `scene`, `frame_id`, `det_id_ignored`, `source_detection_table`, `optical_path`, `bbox_xyxy_original`, `bbox_xyxy_clamped`, `bbox_status`, `crop_w`, `crop_h`, `crop_area`, `embedding_backend`, `embedding_dim`, `embedding_l2_normed`, `embedding_array_key`, `embedding_artifact_path_uncommitted`, `weights_path_external`, `created_at`.

14. How should these embeddings connect to OTY1t BoT-SORT/ByteTrack tracks?

Detection embeddings do not define identity truth. Detection IDs are ignored for identity. Embeddings connect to OTY1t BoT-SORT/ByteTrack tracks through same-scene/same-frame box association. If OTY1t replay preserves source detection row IDs, use direct linkage. Otherwise, use deterministic IoU matching between tracker boxes and OTY0 detection boxes in the same scene/frame. Only after detection-to-track linkage is validated should tracklet-level embeddings be aggregated. Candidate stitching pairs are only proposals for review/probe, not final identity assignments.

15. Why this still does not produce final identity truth, final annotations, or clean-215 promotion.

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

- source table: `outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm011\oty0_yolo_detection_table.csv`
- rows_total: `413`
- crop_extractable: `413`
- crop_failed: `0`
- bbox schemas: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 413}`

### `GM_RM019`

- source table: `outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm019\oty0_yolo_detection_table.csv`
- rows_total: `288`
- crop_extractable: `288`
- crop_failed: `0`
- bbox schemas: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 288}`

### `GM_RM017`

- source table: `outputs\oty2_yolo26l_detector_quality_probe_20260704_231830\oty0_yolo_detection_stream_audit_yolo26l_gm_rm017\oty0_yolo_detection_table.csv`
- rows_total: `215`
- crop_extractable: `215`
- crop_failed: `0`
- bbox schemas: `{"bbox_x1,bbox_y1,bbox_x2,bbox_y2": 215}`

## Conclusion

```text
LEARNED_APPEARANCE_BASELINE_READY_FOR_TRACKLET_STITCHING_INPUT
```
