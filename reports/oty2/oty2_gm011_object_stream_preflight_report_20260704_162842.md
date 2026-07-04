# OTY2 GM_RM011 Object-Stream Preflight

Timestamp: `20260704_162842`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch checked: `feature/oty2-posthoc-mechanism-validation`
HEAD checked: `dd562b6`
Remote divergence checked: `0 0` against `origin/feature/oty2-posthoc-mechanism-validation`

## Boundary Reconfirmation

Mandatory OTY2 session boundary was reconfirmed from `docs/OTY2_SESSION_START_HERE.md`.

This preflight stays in Lane B: GM_RM011 optical object-stream recovery / pairing failure diagnosis only.

Runtime construction boundary:

- Do not use SAR GT, SAR image observation, SAR image-derived cues, GT-local fields, final/manual/oracle/review fields, selector scores, threshold tuning, training signals, final boxes, revised GT, or annotation-proposal labels.
- SAR raw and gray frame directories were counted only as inventory/reference; no SAR image observation was performed.
- Current task did not run full construction. Only filesystem inventory, config/manifest checks, artifact table scans, runner `--help`, and a non-writing ByteTrack dependency probe were executed.

## Raw Inventory And Model Check

| Item | Evidence | Result |
| --- | --- | --- |
| Optical raw frames | `D:\profile\research\data\GM_RM011\GM_RM011_frames` exists; `368` PNG files; first `000000.png`; last `000367.png`. | ready |
| SAR raw frames | `D:\profile\research\data\GM_RM011\GM_RM011_SARframes` exists; `766` PNG files; first `000000.png`; last `000765.png`. Counted as inventory/reference only. | present |
| SAR gray frames | `D:\profile\research\data\GM_RM011\GM_RM011_SARframes_gray` exists; `766` PNG files; first `000000.png`; last `000765.png`. Counted as inventory/reference only. | present |
| Depth sidecar | `D:\profile\research\data\GM_RM011\GM_RM011_depth` exists; `368` PNG depth visualizations, `368` NPY files, and `fail_GM_RM011.txt`. Not required for OTY0 YOLO detection. | present |
| Configured YOLO model | `D:\profile\research\workspace\artifacts\detector_weights\yolo11l.pt` exists; size `51,387,343` bytes. | ready |
| Fallback detector weights | `yolo11m.pt` and `yolo11n.pt` exist; `yolo11x.pt` absent. | fallback partial |

## Config And Manifest Check

| File | GM_RM011 evidence | Result |
| --- | --- | --- |
| `configs/oty_yolo_stream_config.yaml` | Lines `9-25` define preferred model `D:\profile\research\workspace\artifacts\detector_weights\yolo11l.pt`; lines `52-58` define GM_RM011 optical/SAR/depth paths, frame range `[0, 367]`, and `run_status: planned_runnable_if_requested`. | runnable for OTY0 when requested |
| `configs/ot_stream_config.yaml` | Lines `19-76` separate runtime-allowed and posthoc-only/forbidden fields; lines `113-117` define GM_RM011 frame directories. | present; boundary explicit |
| `configs/scene_config.yaml` | Lines `51-59` define GM_RM011 paths and `accounting_sources: {}`. | present |
| `manifests/oty0_yolo_manifest.csv` | Line `3` has GM_RM011, optical frames, frame range `0,367`, and `yolo11l.pt`; note says planned scene, path/model ready, OTY0 not default. | runnable for OTY0 when requested |
| `manifests/ot0_stream_manifest.csv` | Line `3` has GM_RM011 frame paths and notes `Reserved probe scene; no runtime optical detection table wired for OT0.` | present; pre-run OT0 detection-table field intentionally blank |

The blank runtime detection-table field in `ot0_stream_manifest.csv` is not a blocker for the OTY0-first object-stream recovery path. It records the current pre-run state: GM_RM011 needs a fresh OTY0 detection table before downstream optical stream construction.

## Current Non-Archive Artifact Scan

Scan scope: current repo `outputs/` and relevant current `reports/` text artifacts, excluding archive/old_work paths. This was a table/string scan only; no image/SAR visual observation was used.

### Output Tables

| Layer | CSV files scanned | Rows scanned | GM_RM011 rows | Scene distribution |
| --- | ---: | ---: | ---: | --- |
| OTY0 detection tables | 3 | 883 | 0 | `GM_RM017=215; GM_RM019=668` |
| OTY1 ByteTrack/object-stream CSVs | 8 | 3339 | 0 | `GM_RM017=1285; GM_RM019=2054` |
| OTY1a CSVs | 18 | 2860 | 0 | `GM_RM017=120; GM_RM019=2740` |
| OTY1t tracker/object CSVs | 107 | 8694 | 0 | `GM_RM017=2377; GM_RM019=6317` |
| P4G generalized object CSVs | 5 | 1327 | 0 | `GM_RM017=527; GM_RM019=800` |

OTY0 non-CSV summaries contain only `GM_RM011: runnable_if_requested` in:

- `outputs\oty0_yolo_detection_stream_audit_20260701_170617\oty0_summary.json`
- `outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_summary.json`
- `outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_summary.json`

No GM_RM011 current OTY0 detection table rows exist.

### P4G Object-Level Detail

| P4G file | Rows | GM_RM011 rows | Scene distribution |
| --- | ---: | ---: | --- |
| `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_hypotheses_generalized.csv` | 27 | 0 | `GM_RM017=6; GM_RM019=21` |
| `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_frame_state_timeseries_generalized.csv` | 980 | 0 | `GM_RM017=308; GM_RM019=672` |
| `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_object_orphan_observations.csv` | 50 | 0 | `GM_RM017=8; GM_RM019=42` |
| `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_same_frame_observation_clusters_generalized.csv` | 138 | 0 | `GM_RM017=100; GM_RM019=38` |
| `outputs\oty1t_object_hypothesis_generalization_audit_20260701_231500\oty1t_tracker_bbox_provenance_generalized.csv` | 132 | 0 | `GM_RM017=105; GM_RM019=27` |

Reports under `reports/oty2/` do contain GM_RM011 SAR-reference/posthoc morphology rows from prior mechanism work, but these are not current OTY0/OTY1/OTY1a/OTY1t/P4G optical object-stream artifacts and were not treated as runtime inputs.

## Runner / Command Inventory

Only `--help` and source-line checks were run for command discovery.

| Layer | Runner | Relevant interface | Output convention |
| --- | --- | --- | --- |
| OTY0 | `tools\diagnostics\run_oty0_yolo_detection_stream_audit.py` | `--scene`, `--config`, `--manifest`, `--output-root`, `--timestamp`, `--frame-range-start`, `--frame-range-end`, `--max-frames` | `outputs\oty0_yolo_detection_stream_audit_<timestamp>\oty0_yolo_detection_table.csv` |
| OTY1 | `tools\diagnostics\run_oty1_optical_tracklet_audit.py` | `--scene`, `--oty0-detection-table`, `--output-root`, `--timestamp`, `--no-run-oty0-if-missing` | `outputs\oty1_optical_tracklet_audit_<timestamp>\` |
| OTY1a | `tools\diagnostics\run_oty1a_fragment_merge_audit.py` | `--scene`, `--oty1-output-dir`, `--output-root`, `--timestamp` | `outputs\oty1a_fragment_merge_audit_<timestamp>\` |
| OTY1t | `tools\diagnostics\run_oty1t_tracker_audit.py` | `--scene`, `--tracker {bytetrack,botsort,ocsort,strongsort}`, `--oty0-detection-table`, `--oty1-output-dir`, `--oty1a-output-dir`, `--output-root`, `--timestamp`, `--no-run-oty0-if-missing` | `outputs\oty1t_tracker_audit_bytetrack_<timestamp>\` |
| P4G | `tools\diagnostics\run_oty1t_object_hypothesis_generalization_audit.py` | `--scene`, `--tracker`, `--output-root`, `--timestamp`, `--all-available-scenes` | `outputs\oty1t_object_hypothesis_generalization_audit_<timestamp>\` |

ByteTrack non-writing dependency probe:

- `ultralytics_available=True`
- `bytetrack_available=True`
- `lap_available=True`
- `dependency_status=available`
- `ultralytics_version=8.4.21`
- `adapter_status=detection_table_replay_adapter`

## Go / No-Go

State: `GO_raw_and_model_ready_artifacts_absent`

Reason:

- Not `CONFIG_BLOCKED`: GM_RM011 is present in required configs/manifests. The OT0 manifest's blank runtime detection-table field matches the current pre-run state and is resolved by running OTY0 first.
- Not `DETECTOR_BLOCKED`: configured `yolo11l.pt` exists.
- Not `TRACKER_BLOCKED`: ByteTrack dependency probe reports available; tracker is waiting on GM_RM011 OTY0 detections.
- Not `CONVENTION_BLOCKED`: the required command surfaces and output conventions exist.
- Not `UNRESOLVED`: the blocker is concretely current-object-stream artifact absence, not missing raw data/model/config.

## Recommended Next Command Sequence

Use a single timestamp for all steps so downstream paths are deterministic, for example:

```powershell
$ts = "20260704_gm011_oty_stream"
```

Run OTY0 GM_RM011-only optical detection from raw optical frames:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_yolo_detection_stream_audit.py --scene GM_RM011 --frame-range-start 0 --frame-range-end 367 --timestamp $ts
```

Run OTY1 GM_RM011-only optical tracklet construction from the generated OTY0 detection table:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1_optical_tracklet_audit.py --scene GM_RM011 --oty0-detection-table outputs\oty0_yolo_detection_stream_audit_$ts\oty0_yolo_detection_table.csv --no-run-oty0-if-missing --timestamp $ts
```

Run OTY1a GM_RM011-only fragment-merge audit from the generated OTY1 output:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1a_fragment_merge_audit.py --scene GM_RM011 --oty1-output-dir outputs\oty1_optical_tracklet_audit_$ts --timestamp $ts
```

Run OTY1t GM_RM011-only ByteTrack replay from the generated OTY0/OTY1/OTY1a artifacts:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_tracker_audit.py --scene GM_RM011 --tracker bytetrack --oty0-detection-table outputs\oty0_yolo_detection_stream_audit_$ts\oty0_yolo_detection_table.csv --oty1-output-dir outputs\oty1_optical_tracklet_audit_$ts --oty1a-output-dir outputs\oty1a_fragment_merge_audit_$ts --no-run-oty0-if-missing --timestamp $ts
```

Only after OTY0/OTY1/OTY1a/OTY1t succeed, run P4G GM_RM011-only generalized object-hypothesis preparation:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty1t_object_hypothesis_generalization_audit.py --scene GM_RM011 --tracker bytetrack --timestamp $ts
```

## Minimal Fix Needed

No config/model/raw-data fix is needed for the preflight. The minimal next action is construction, starting with the OTY0 command above. If OTY0 produces no detections or a blocker file, then the next diagnosis should remain detector/object-stream-only and inspect OTY0 dependency/blocker outputs, not SAR GT, selector/ranking, final boxes, revised GT, support audit, temporal drift, threshold tuning, weighted fusion, or OTY3 behavior.

## Forbidden Artifact Check For This Report

This report is documentation only. Planned changed file:

- `reports/oty2/oty2_gm011_object_stream_preflight_report_20260704_162842.md`

Expected forbidden artifact status before any optional commit:

- zip/7z/rar: none planned
- large binary: none planned
- generated atlas: none planned
- final annotation: none planned
- revised GT: none planned
- runtime prediction artifact: none planned
- selector/ranking output: none planned
