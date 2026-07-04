# OTY2 YOLO26 Detector-Swap Probe

Timestamp: `20260704_225021`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `0b94e31 Assess YOLO26 detector swap feasibility`

## Boundary

This was intended to be the minimum YOLO26 Detect smoke/probe pass after a local YOLO26 Detect weight became available. The required weight was not found, so the probe was not run.

No mainline detector was replaced. No `configs/oty_yolo_stream_config.yaml` or `manifests/oty0_yolo_manifest.csv` edits were made. No OTY0 runtime code was changed. No OTY1, OTY1a, OTY1t, P4, or P4G runtime was entered. No tracker run, threshold tuning, final annotation, revised GT, final box, selector/ranking output, weighted fusion, SAR pairing, support audit, identity-truth claim, or GM_RM011 clean-215 promotion was performed.

No YOLO26 weight, outputs runtime artifact, atlas, final annotation, revised GT, final box, runtime prediction artifact, or selector/ranking artifact is included in this report commit.

## Sources Read

Required OTY2 sources:

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports/oty2/oty2_yolo26_detector_swap_feasibility_20260704_224235.md`
- `reports/oty2/oty2_same_frame_multibox_and_state_tagging_audit_20260704_214019.md`

## Environment Recheck

Interpreter used:

```text
D:\MINICONDA\envs\py311\python.exe
```

Observed environment:

| Check | Result |
| --- | --- |
| `ultralytics.__version__` | `8.4.21` |
| `torch.__version__` | `2.10.0+cu128` |
| CUDA available | `True` |

This preserves the previous feasibility-report conclusion that the local codepath can recognize YOLO26 configs, but an actual `.pt` weight is required before smoke/predict can be claimed.

## Weight Search

Expected user-provided weight location pattern:

```text
D:\profile\research\workspace\artifacts\detector_weights\yolo26*.pt
```

Searches performed read-only:

| Search | Result |
| --- | --- |
| `D:\profile\research\workspace\artifacts\detector_weights\yolo26*.pt` | no files found |
| recursive `D:\profile\research` and `D:\profile\research\workspace` for `yolo26*.pt` | no files found |
| recursive `D:\profile\research` and `D:\profile\research\workspace` for YOLO-like `*26*.pt` | no files found |

Existing detector-weight inventory remains YOLO11-only in the expected detector weight directory:

| Weight | Status |
| --- | --- |
| `yolo11l.pt` | present |
| `yolo11m.pt` | present |
| `yolo11s.pt` | present |
| `yolo11n.pt` | present |
| `yolo26*.pt` | absent |

## Probe Status

| Stage | Status | Evidence |
| --- | --- | --- |
| YOLO26 Detect weight discovery | `FAIL` | no `yolo26*.pt` or YOLO-like `*26*.pt` found under the searched local paths |
| YOLO26 model load | `NOT_RUN` | blocked before `YOLO(weight_path)` because no local weight exists |
| `model.predict(...)` schema smoke test | `NOT_RUN` | no weight to load |
| `result.boxes.xyxy/conf/cls` check | `NOT_RUN` | no prediction result produced |
| Temporary OTY0-compatible detection table | `NOT_RUN` | no probe detections generated |
| Three-scene YOLO11l vs YOLO26 comparison | `NOT_RUN` | no YOLO26 OTY0 probe output exists |

Probe state:

```text
BLOCKED_MISSING_YOLO26_DETECT_WEIGHTS
```

## Baseline Availability

The existing YOLO11l baseline OTY0 tables are present locally and can be used for comparison once a YOLO26 Detect weight is available:

| Scene | Baseline YOLO11l table | Status |
| --- | --- | --- |
| `GM_RM011` | `outputs\oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream\oty0_yolo_detection_table.csv` | present |
| `GM_RM019` | `outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv` | present |
| `GM_RM017` | `outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv` | present |

These are existing ignored outputs and were not modified by this pass.

## Required Questions

1. Can the YOLO26 Detect weight be loaded by the current Ultralytics environment?

Unanswered. No local YOLO26 Detect `.pt` file was found, so `YOLO(weight_path)` was not attempted.

2. Does `model.predict(...)` return `result.boxes.xyxy/conf/cls`?

Unanswered. Prediction was not run because weight discovery failed.

3. Can a temporary OTY0-compatible detection table be generated?

Unanswered. The OTY0 schema remains conditionally compatible from the feasibility audit, but this pass did not generate a YOLO26 table.

4. Does YOLO26 Detect reduce same-frame high-overlap multi-boxes, class-instability duplicate-like pairs, partial/full competition, or crowded-frame conflict on `GM_RM011`, `GM_RM019`, and `GM_RM017`?

Unanswered. Three-scene comparison requires YOLO26 detection outputs, and none were generated.

## Summary CSV

No summary CSV was generated in this blocked pass because the requested precondition explicitly failed before any smoke/probe result existed. Creating a metrics CSV with no YOLO26 detections would risk looking like a probe result. The next run should generate:

```text
reports/oty2/samples/oty2_yolo26_detector_swap_probe_summary_<timestamp>.csv
```

only after a local YOLO26 Detect weight is discovered and at least the schema smoke test passes.

## Next Minimal Command Sequence After Weight Placement

Place a YOLO26 Detect weight outside the repository, for example:

```text
D:\profile\research\workspace\artifacts\detector_weights\yolo26n.pt
```

Then rerun the same bounded sequence:

1. Discover the local `yolo26*.pt` weight and verify it is not `-seg`, `-obb`, `-pose`, or `-cls`.
2. Load it with `D:\MINICONDA\envs\py311\python.exe` and `ultralytics.YOLO(weight_path)`.
3. Run a GM_RM011 few-frame smoke test and verify `result.boxes.xyxy`, `result.boxes.conf`, `result.boxes.cls`, and `model.names`.
4. If smoke passes, create temporary probe-only config/manifest under ignored `outputs\oty2_yolo26_detector_swap_probe_<timestamp>\`.
5. Run OTY0-only for `GM_RM011`, `GM_RM019`, and `GM_RM017`.
6. Compare YOLO11l baseline and YOLO26 Detect probe on detection count, frames with detections, empty frames, per-frame count distribution, class distribution, confidence distribution, high-overlap same-frame pairs, class-instability duplicate-like pairs, partial/full competition, boundary-touch ratio, and crowded-frame ratio.
7. Do not run ByteTrack unless separately authorized as a downstream tracker-side probe.

## Recommendation

Do not change the main detector, main OTY0 config/manifest, OTY0 runtime, tracker, or downstream OTY stages.

The detector-swap probe remains blocked until a local YOLO26 Detect `.pt` weight is placed in an accessible path. Once the weight is available, the next safe action is the schema smoke test, followed by an isolated OTY0-only three-scene comparison. Even if YOLO26 reduces duplicate-like boxes, OTY0-post pre-tracking observation grouping is still likely needed because the mechanism must preserve class instability, partial/full competition, boundary contact, and crowded-frame ambiguity as explicit uncertainty/context rather than silently treating detector output as identity truth.

## No-Overstep Check

This blocked pass did not:

- replace `yolo11l.pt`;
- add or commit any YOLO26 weight;
- edit `configs/oty_yolo_stream_config.yaml`;
- edit `manifests/oty0_yolo_manifest.csv`;
- edit OTY0, OTY1, OTY1a, OTY1t, P4, or P4G runtime logic;
- run OTY0, OTY1, OTY1a, OTY1t, P4, or P4G construction;
- create outputs runtime artifacts;
- create an atlas;
- create final annotation;
- create revised GT;
- create final box;
- create selector/ranking output;
- tune thresholds;
- enter SAR pairing;
- enter support audit;
- promote GM_RM011 into clean `215`;
- use SAR GT or SAR image observation for optical runtime identity.
