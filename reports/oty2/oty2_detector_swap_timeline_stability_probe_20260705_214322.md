# OTY2 Detector Swap Timeline Stability Probe

Timestamp: `20260705_214322`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified starting HEAD requirement: `d52c14b Define optical timeline graph input contract`

## Boundary

This probe tests detector plug-in impact on optical timeline stability only. It does not replace the main OTY0 detector, modify existing OTY0 detection tables, modify tracker output, modify timeline graph conclusions, run SAR consumption, create final boxes, create revised GT, create final annotation, run SAR pairing/support, run selector/ranking, tune thresholds, or commit weights.

The comparison is not an mAP evaluation. It asks whether detector output reduces timeline pressure: missing diagnostic vehicle frames, non-vehicle false positives, same-vehicle multi-boxes, edge-contact instability, weak-edge uncertainty, forbidden-edge risk, and manual override pressure.

## Detector Plug-In Status

- `ultralytics` import available: `True`
- `baseline_oty0`: status=`available`, scenes_with_tables=`GM_RM017;GM_RM011`, source_model=`ultralytics_yolo11l_current_oty0`, weight=`not_committed; current OTY0 baseline source table`
- `ultralytics_yolo26l_probe`: status=`available`, scenes_with_tables=`GM_RM017;GM_RM011`, source_model=`ultralytics_yolo26l_existing_probe`, weight=`D:/profile/research/workspace/artifacts/detector_weights/yolo26l.pt`
- `ultralytics_yolo8n_no_download`: status=`weight_missing_no_download`, scenes_with_tables=`none`, source_model=`ultralytics_yolo8n`, weight=`D:/models/ultralytics/yolov8n.pt`
- `ultralytics_yolo12n_no_download`: status=`weight_missing_no_download`, scenes_with_tables=`none`, source_model=`ultralytics_yolo12n`, weight=`D:/models/ultralytics/yolo12n.pt`
- `rtdetr_l_no_download`: status=`weight_missing_no_download`, scenes_with_tables=`none`, source_model=`ultralytics_rtdetr_l`, weight=`D:/models/ultralytics/rtdetr-l.pt`

No new detector weights were downloaded. Existing YOLO26l probe outputs were reused. Extra YOLO/RT-DETR entries are present as plug-in placeholders and are marked `backend_missing` / `weight_missing_no_download` until local weights or approved download are available outside the repo.

## Outputs

- Unified detection schema: `reports\oty2\samples\oty2_detector_swap_detection_schema_20260705_214322.csv`
- Stability summary: `reports\oty2\samples\oty2_detector_swap_timeline_stability_summary_20260705_214322.csv`

The unified detection schema contains only rows in the GM_RM017 and GM_RM011 diagnostic windows. `det_id` is unique only within detector/scene/frame and is not a vehicle identity.

## Actual Detector-Level Findings

Actual detectors compared:

- `baseline_oty0`: current OTY0 YOLO11l-derived baseline tables.
- `ultralytics_yolo26l_probe`: existing YOLO26l probe tables.

YOLO26l per-case effects:

- improved timeline stability rows: `1`
- worse rows: `5`
- neutral rows: `1`
- inconclusive rows: `2`
- manual override reduced rows: `3`
- manual override increased rows: `4`

Backend/weight missing detectors:

- `rtdetr_l_no_download`
- `ultralytics_yolo12n_no_download`
- `ultralytics_yolo8n_no_download`

## Interpretation

    YOLO26l gives one useful detection-level improvement in the diagnostic windows: the GM_RM017 non-vehicle barrier case has much lower vehicle-like overlap. That is not enough to call it a general optical-timeline improvement. In several same-vehicle or forbidden-edge windows, YOLO26l increases multi-box pressure or missing diagnostic frames:

- GM_RM017 remains easier, but edge/partial visibility still creates pressure.
- GM_RM017 `bs_0002` remains an important non-vehicle exclusion test; detector swaps must not promote it to a vehicle identity.
- GM_RM011 strong short-gap edges remain visually supported, but YOLO26l adds multi-box pressure in these windows.
- GM_RM011 forbidden edges remain detection-only unresolved without tracker replay; detector output alone cannot prove safe identity separation.

Tracker replay was not run. The current result is therefore detection-level only.

## Required Answers

1. Detector replacement must be plug-in because the same optical timeline graph needs stable provenance across detector variants without overwriting OTY0 or tracker artifacts.
2. A new YOLO cannot directly replace the mainline because improved detection counts can still worsen multi-box, edge, or forbidden-edge pressure.
3. Baseline issues are partial/edge boxes, missing diagnostic frames in some windows, non-vehicle vehicle-like detections, and multi-box pressure.
4. YOLO26l does not uniformly reduce missing diagnostic frames; it introduces missing diagnostic frames in the GM_RM011 weak/forbidden windows under this detection-level check.
5. YOLO26l reduces vehicle-like overlap on the `GM_RM017 bs_0002` non-vehicle barrier case, but the case must still remain an exclusion.
6. YOLO26l does not uniformly reduce same-vehicle multi-box pressure.
7. YOLO26l improves box fit in some windows and is neutral or worse in others.
8. YOLO26l does not remove edge truncation pressure.
9. Manual override pressure is reduced in some rows and increased in others.
10. Weak edges do not become strong candidates from this detector-only probe; none should be automatically upgraded.
11. Forbidden-edge safety is not broken into a merge, but it remains detection-only unresolved without tracker replay.
12. Broad tracker replay is not justified by this result. A very bounded replay can still be useful as a negative-control or sensitivity check.
13. YOLO26l is not a mainline replacement candidate from this probe; it remains a detector variant worth keeping in the plug-in interface.
14. SAR is not allowed in this stage.
15. Final/revised annotation is not allowed.

## Conclusion

```text
DETECTOR_SWAP_PROBE_NEUTRAL
```
