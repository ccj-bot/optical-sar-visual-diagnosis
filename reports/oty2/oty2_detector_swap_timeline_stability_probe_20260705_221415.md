# OTY2 Detector Swap Timeline Stability Probe

Timestamp: `20260705_221415`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Probe base includes prior commit: `1050a59 Probe detector swap impact on optical timeline stability`

## Boundary

This probe tests detector plug-in impact on optical timeline stability only. It does not replace the main OTY0 detector, modify existing OTY0 detection tables, modify tracker output, modify timeline graph conclusions, run SAR consumption, create final boxes, create revised GT, create final annotation, run SAR pairing/support, run selector/ranking, tune thresholds, or commit weights.

The comparison is not an mAP evaluation. It asks whether detector output reduces timeline pressure: missing diagnostic vehicle frames, non-vehicle false positives, same-vehicle multi-boxes, edge-contact instability, weak-edge uncertainty, forbidden-edge risk, and manual override pressure.

## Detector Plug-In Status

- `ultralytics` import available: `True`
- `baseline_oty0`: status=`available`, scenes_with_tables=`GM_RM017;GM_RM011`, source_model=`ultralytics_yolo11l_current_oty0`, weight=`not_committed; current OTY0 baseline source table`
- `ultralytics_yolo26l_probe`: status=`available`, scenes_with_tables=`GM_RM017;GM_RM011`, source_model=`ultralytics_yolo26l_existing_probe`, weight=`D:/profile/research/workspace/artifacts/detector_weights/yolo26l.pt`
- `ultralytics_yolov8n_downloaded`: status=`available`, scenes_with_tables=`GM_RM011;GM_RM017`, source_model=`ultralytics_yolov8n`, weight=`D:\models\ultralytics\yolov8n.pt`
- `ultralytics_yolov8s_downloaded`: status=`available`, scenes_with_tables=`GM_RM011;GM_RM017`, source_model=`ultralytics_yolov8s`, weight=`D:\models\ultralytics\yolov8s.pt`
- `ultralytics_yolo11n_downloaded`: status=`available`, scenes_with_tables=`GM_RM011;GM_RM017`, source_model=`ultralytics_yolo11n`, weight=`D:\models\ultralytics\yolo11n.pt`
- `ultralytics_yolo12n_downloaded`: status=`available`, scenes_with_tables=`GM_RM011;GM_RM017`, source_model=`ultralytics_yolo12n`, weight=`D:\models\ultralytics\yolo12n.pt`
- `ultralytics_yolo26n_downloaded`: status=`available`, scenes_with_tables=`GM_RM011;GM_RM017`, source_model=`ultralytics_yolo26n`, weight=`D:\models\ultralytics\yolo26n.pt`

Downloaded detector weights, when available, are stored outside the repo under `D:/models/ultralytics/`. Existing YOLO26l probe outputs are kept as a prior comparison source and are not overwritten.

Downloaded weights used:

- `ultralytics_yolov8n`: `D:\models\ultralytics\yolov8n.pt`
- `ultralytics_yolov8s`: `D:\models\ultralytics\yolov8s.pt`
- `ultralytics_yolo11n`: `D:\models\ultralytics\yolo11n.pt`
- `ultralytics_yolo12n`: `D:\models\ultralytics\yolo12n.pt`
- `ultralytics_yolo26n`: `D:\models\ultralytics\yolo26n.pt`

## Outputs

- Unified detection schema: `reports\oty2\samples\oty2_detector_swap_detection_schema_20260705_221415.csv`
- Stability summary: `reports\oty2\samples\oty2_detector_swap_timeline_stability_summary_20260705_221415.csv`

The unified detection schema contains only rows in the GM_RM017 and GM_RM011 diagnostic windows. `det_id` is unique only within detector/scene/frame and is not a vehicle identity.

## Actual Detector-Level Findings

Actual detectors compared:

- `baseline_oty0`: current OTY0 YOLO11l-derived baseline tables.
- `ultralytics_yolo26l_probe`: existing YOLO26l probe tables.
- downloaded Ultralytics variants if their weights loaded and diagnostic-frame inference completed.

All non-baseline detector per-case effects:

- improved timeline stability rows: `5`
- worse rows: `39`
- neutral rows: `8`
- inconclusive rows: `2`
- manual override reduced rows: `12`
- manual override increased rows: `31`

| detector | improves | worse | neutral | inconclusive | backend_missing | manual_reduced | manual_increased |
|---|---:|---:|---:|---:|---:|---:|---:|
| ultralytics_yolo11n_downloaded | 1 | 6 | 2 | 0 | 0 | 2 | 6 |
| ultralytics_yolo12n_downloaded | 1 | 7 | 1 | 0 | 0 | 2 | 4 |
| ultralytics_yolo26l_probe | 1 | 5 | 1 | 2 | 0 | 3 | 4 |
| ultralytics_yolo26n_downloaded | 0 | 8 | 1 | 0 | 0 | 1 | 7 |
| ultralytics_yolov8n_downloaded | 1 | 7 | 1 | 0 | 0 | 2 | 5 |
| ultralytics_yolov8s_downloaded | 1 | 6 | 2 | 0 | 0 | 2 | 5 |

Backend/weight missing detectors:

- none

## Interpretation

Detector swaps are useful only if they reduce timeline pressure without creating a worse same-vehicle or forbidden-edge problem. This probe therefore treats high detection counts as insufficient evidence by themselves. Any detector that improves the GM_RM017 non-vehicle exclusion but increases GM_RM011 multi-box, missing-frame, or forbidden-edge pressure remains a diagnostic variant rather than a mainline replacement.

- GM_RM017 remains easier, but edge/partial visibility still creates pressure.
- GM_RM017 `bs_0002` remains an important non-vehicle exclusion test; detector swaps must not promote it to a vehicle identity.
- GM_RM011 strong short-gap edges remain visually supported, but detector variants frequently add multi-box or missing-frame pressure in these windows.
- GM_RM011 forbidden edges remain detection-only unresolved without tracker replay; detector output alone cannot prove safe identity separation.

Tracker replay was not run. The current result is therefore detection-level only.

## Required Answers

1. Detector replacement must be plug-in because the same optical timeline graph needs stable provenance across detector variants without overwriting OTY0 or tracker artifacts.
2. A new YOLO cannot directly replace the mainline because improved detection counts can still worsen multi-box, edge, or forbidden-edge pressure.
3. Baseline issues are partial/edge boxes, missing diagnostic frames in some windows, non-vehicle vehicle-like detections, and multi-box pressure.
4. Downloaded detector variants must be read from the summary table case by case; no detector-level aggregate is allowed to become identity truth.
5. A detector that reduces vehicle-like overlap on the `GM_RM017 bs_0002` non-vehicle barrier case still must keep that case as an exclusion.
6. Same-vehicle multi-box pressure is a first-class failure signal, not a harmless side effect.
7. Box-fit changes are diagnostic only because the reference boxes come from the optical timeline manifest, not final GT.
8. Detector swaps cannot remove edge truncation pressure by themselves.
9. Manual override pressure is reduced in some rows and increased in others.
10. Weak edges do not become strong candidates from this detector-only probe; none should be automatically upgraded.
11. Forbidden-edge safety is not broken into a merge, but it remains detection-only unresolved without tracker replay.
12. Broad tracker replay is not justified by this result. A very bounded replay can still be useful as a negative-control or sensitivity check.
13. No tested detector variant is a mainline replacement candidate from this probe; detector variants remain useful only through the plug-in interface.
14. SAR is not allowed in this stage.
15. Final/revised annotation is not allowed.

## Conclusion

```text
DETECTOR_SWAP_PROBE_NEUTRAL
```
