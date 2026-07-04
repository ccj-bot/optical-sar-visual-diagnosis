# OTY2 YOLO26 Detector-Swap Feasibility

Timestamp: `20260704_224235`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Baseline commit at start: `1dc6d7b Audit optical stream tracking insertion points`

## Boundary

This is a YOLO26 availability and detector-swap probe design report only.

No mainline detector was replaced. No OTY0, OTY1, OTY1t, tracker, P4, or P4G runtime logic was modified. No diagnostic reconstruction was run. No threshold tuning, final annotation, revised GT, final box, selector/ranking, weighted fusion, SAR pairing, support audit, identity-truth claim, or GM_RM011 clean-215 promotion was performed.

The prior local commit `1dc6d7b` was pushed to `origin/feature/oty2-posthoc-mechanism-validation` before this report was prepared.

## Sources Read

Required OTY2 sources:

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/OTY2_OPTICAL_STATE_TAGGING_SPEC.md`
- `reports/oty2/oty2_optical_stream_tracking_insertion_point_audit_20260704_215625.md`
- `reports/oty2/oty2_same_frame_multibox_and_state_tagging_audit_20260704_214019.md`

Code/config sources inspected read-only:

- `tools/diagnostics/run_oty0_yolo_detection_stream_audit.py`
- `configs/oty_yolo_stream_config.yaml`
- `manifests/oty0_yolo_manifest.csv`
- `src/optical_state/tracker_audit.py`
- `src/optical_state/tracker_diagnosis.py`
- `src/optical_state/tracklet_builder.py`
- `src/optical_state/fragment_merge.py`
- `src/optical_state/observation_cluster.py`
- `src/optical_state/object_hypothesis.py`

External reference checked for current YOLO26 behavior:

- Ultralytics YOLO26 model page: `https://docs.ultralytics.com/models/yolo26`
- Ultralytics YOLO26 end-to-end detection guide: `https://docs.ultralytics.com/guides/end2end-detection`

## Local Environment Check

Interpreter used for environment inspection:

```text
D:\MINICONDA\envs\py311\python.exe
```

Observed package state:

| Check | Result |
| --- | --- |
| `ultralytics.__version__` | `8.4.21` |
| `torch.__version__` | `2.10.0+cu128` |
| CUDA available | `True` |
| CUDA device | `NVIDIA GeForce RTX 5070 Laptop GPU` |
| Ultralytics package path | `D:\MINICONDA\envs\py311\Lib\site-packages\ultralytics` |
| Local Ultralytics YOLO26 model config directory | present: `cfg\models\26` |
| Local YOLO26 config files observed | `yolo26.yaml`, `yolo26-obb.yaml`, `yolo26-seg.yaml`, `yolo26-p2.yaml`, `yolo26-p6.yaml`, `yolo26-cls.yaml`, `yolo26-pose.yaml`, `yoloe-26.yaml`, `yoloe-26-seg.yaml` |

Detector weight inventory under `D:\profile\research\workspace\artifacts\detector_weights`:

| Weight | Size |
| --- | ---: |
| `yolo11l.pt` | 51,387,343 bytes |
| `yolo11m.pt` | 40,684,120 bytes |
| `yolo11s.pt` | 19,313,732 bytes |
| `yolo11n.pt` | 5,613,764 bytes |

A read-only search for `*yolo26*` under `D:\profile\research` and `D:\profile\research\workspace` found no local YOLO26 `.pt` weight file.

Conclusion: the installed Ultralytics package has YOLO26 code/config awareness, but this repository/workspace does not currently have a local YOLO26 weight available for an actual smoke test.

## How Current OTY0 Loads YOLO11l

Current OTY0 entry point:

```text
tools/diagnostics/run_oty0_yolo_detection_stream_audit.py
```

Model-path selection is in `select_model_path(config, manifest_row)`. Priority order:

1. manifest row `yolo_model_path`;
2. config `yolo.preferred_model_path`;
3. config `yolo.fallback_model_paths`.

The current config preferred path is:

```text
D:\profile\research\workspace\artifacts\detector_weights\yolo11l.pt
```

The current manifest rows for `GM_RM011`, `GM_RM019`, and `GM_RM017` also point at:

```text
D:\profile\research\workspace\artifacts\detector_weights\yolo11l.pt
```

The runtime code loads the model with:

```python
from ultralytics import YOLO
model = YOLO(model_path)
results = model.predict(...)
```

The script does not expose a direct `--model` CLI argument. Therefore a YOLO26 probe can be done without changing runtime code only by using a separate probe config/manifest that points to a YOLO26 weight path. The main config and manifest should not be edited for this probe.

## Current OTY0 Detection Table Contract

`run_oty0_yolo_detection_stream_audit.py` reads Ultralytics results from:

```python
boxes = result.boxes
xyxy = boxes.xyxy
confs = boxes.conf
classes = boxes.cls
```

The OTY0 runtime detection schema is:

```text
scene
optical_frame_num
optical_path
det_id
class_id
class_name
confidence
bbox_x1
bbox_y1
bbox_x2
bbox_y2
bbox_cx
bbox_cy
bbox_w
bbox_h
```

Fields provided by the detector result:

- `bbox_x1`, `bbox_y1`, `bbox_x2`, `bbox_y2` from `boxes.xyxy`;
- `confidence` from `boxes.conf`;
- `class_id` from `boxes.cls`;
- `class_name` from `model.names`.

Fields added by the OTY0 script:

- `scene`;
- `optical_frame_num`;
- `optical_path`;
- `det_id`;
- `bbox_cx`, `bbox_cy`, `bbox_w`, `bbox_h`.

The current class filter is `car`, `truck`, and `bus` at confidence `0.25`. This is an optical detector output filter for audit only and is not a SAR selector threshold.

## YOLO26 Schema Compatibility Assessment

For a standard Ultralytics YOLO26 Detect `.pt` model, schema compatibility is conditionally favorable.

Official Ultralytics documentation says the standard Ultralytics API can load YOLO26 with `YOLO("yolo26n.pt")` and call `model.predict(...)` without code changes. The same guide states YOLO26 end-to-end detection output is in `xyxy` layout with `[x1, y1, x2, y2, confidence, class_id]`.

That matches the fields OTY0 needs, provided that:

- the local YOLO26 weight is a Detect model, such as `yolo26n.pt`, `yolo26s.pt`, `yolo26m.pt`, `yolo26l.pt`, or `yolo26x.pt`;
- Ultralytics returns populated `result.boxes.xyxy`, `result.boxes.conf`, and `result.boxes.cls` for the loaded weight;
- `model.names` contains compatible vehicle class names for the configured filter (`car`, `truck`, `bus`);
- the probe uses the same OTY0 frame inventory and does not read SAR GT, final boxes, or review fields for runtime construction.

The practical local blocker is not the OTY0 schema. The practical blocker is absence of a local YOLO26 weight file.

## OBB And Segmentation Controls

YOLO26 supports Detect, segmentation, and OBB task variants, and the installed local package includes `yolo26-obb.yaml` and `yolo26-seg.yaml` configs.

Recommended design-only interpretation:

| Model type | Use as OTY0 drop-in? | Reason |
| --- | --- | --- |
| YOLO26 Detect | Yes, conditionally | Current OTY0 expects `result.boxes.xyxy`, `conf`, and `cls`; Detect should preserve this contract through the Ultralytics API. |
| YOLO26 Seg | Possible detect-like control only if `result.boxes` is populated | Masks may help diagnose partial/full observations, but masks must not become final boxes or revised annotations in this OTY2 phase. |
| YOLO26 OBB | Not a direct drop-in for current OTY0 without adapter design | OBB adds angle/oriented geometry. Current OTY0 writes axis-aligned `bbox_x1/y1/x2/y2` from `result.boxes`; an OBB probe must not silently convert oriented boxes into final boxes or identity truth. |

No OBB or segmentation probe was run in this task.

## Answers To Required Questions

1. Current `ultralytics` version:

`8.4.21` in `D:\MINICONDA\envs\py311\python.exe`.

2. How current OTY0 loads YOLO11l:

`run_oty0_yolo_detection_stream_audit.py` selects `yolo_model_path` from the manifest first, then config preferred/fallback paths, instantiates `YOLO(model_path)`, and calls `model.predict(...)`. Current manifest/config paths point to `D:\profile\research\workspace\artifacts\detector_weights\yolo11l.pt`.

3. Can the model path be directly replaced by YOLO26 weights?

At the code contract level, yes for a standard Ultralytics YOLO26 Detect `.pt` file. Operationally, the script has no `--model` flag, so the safe probe path is a separate temporary probe config/manifest, not editing the main config or runtime script. A local YOLO26 weight is currently missing.

4. Which fields does the OTY0 detection table depend on?

It depends on detector `xyxy`, confidence, class id/name, plus OTY0-derived scene/frame/path/detector-row identifiers and bbox center/size fields. Full field list is in the "Current OTY0 Detection Table Contract" section.

5. Can YOLO26 preserve bbox xyxy, class, confidence, frame id, and scene id?

For YOLO26 Detect through the Ultralytics Python API, expected yes: YOLO26 detection outputs `xyxy`, confidence, and class id. OTY0 supplies frame id and scene id from the manifest/frame path. This still requires a one-scene smoke test with the exact local weight before treating it as runnable evidence.

6. If YOLO26 is unavailable, isolate environment or upgrade current environment?

Prefer an isolated clone/probe environment or a copied py311 environment for any package upgrade or model-load smoke test. Do not upgrade the current OTY runtime environment first. The current py311 environment is already known to run the existing OTY pipeline and already contains YOLO26 config files; the missing piece is a local YOLO26 weight and a controlled load/predict schema smoke test.

7. Is OBB or segmentation available as a contrast?

Design-only yes, but not as a direct mainline replacement. The local Ultralytics package has config awareness for YOLO26 OBB and segmentation. YOLO26 Seg may be a detect-like control if boxes are present. YOLO26 OBB requires a separate adapter decision because current OTY0 writes axis-aligned xyxy boxes and must not emit final boxes.

8. Minimal detector-swap probe design:

Use scenes:

- `GM_RM011`
- `GM_RM019`
- `GM_RM017`

Compare:

- current baseline: `YOLO11l Detect`;
- probe detector: `YOLO26 Detect`;
- optional design-only controls: `YOLO26 Seg` and `YOLO26 OBB`, only after Detect smoke test passes.

Metrics:

- total detection rows;
- frames with detections;
- empty detection frames;
- per-frame detection count distribution;
- class distribution;
- confidence distribution;
- high-overlap same-frame pair count;
- class-instability duplicate-like pair count;
- one-small-one-large partial/full competition count;
- boundary-touch ratio;
- crowded-frame ratio;
- ByteTrack unmatched detections only if later authorized as a safe downstream probe.

9. Probe interpretation:

YOLO26 probe is not a mainline detector replacement. It is not an automatic tracking fix. It does not create final boxes, final annotation, revised GT, selector/ranking output, SAR pairing, or support audit. It can only answer whether detector observation quality changes before the OTY1/OTY1t association layer.

## Proposed Minimal Probe Sequence If Later Authorized

This report does not run the sequence. It records the safe design.

1. Place or reference a local YOLO26 Detect weight outside the repo, preferably:

```text
D:\profile\research\workspace\artifacts\detector_weights\yolo26*.pt
```

2. Create an ignored probe-only config/manifest under an ignored output directory, not under tracked `configs/` or `manifests/`, with the same frame paths and only `yolo_model_path` changed to the YOLO26 weight.

3. Run OTY0 only for each scene into a clearly isolated ignored output root:

```text
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_yolo_detection_stream_audit.py --config outputs\oty2_yolo26_detector_swap_probe_<timestamp>\oty_yolo26_probe_config.yaml --manifest outputs\oty2_yolo26_detector_swap_probe_<timestamp>\oty0_yolo26_probe_manifest.csv --scene GM_RM011 --output-root outputs\oty2_yolo26_detector_swap_probe_<timestamp> --timestamp yolo26_gm_rm011
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_yolo_detection_stream_audit.py --config outputs\oty2_yolo26_detector_swap_probe_<timestamp>\oty_yolo26_probe_config.yaml --manifest outputs\oty2_yolo26_detector_swap_probe_<timestamp>\oty0_yolo26_probe_manifest.csv --scene GM_RM019 --output-root outputs\oty2_yolo26_detector_swap_probe_<timestamp> --timestamp yolo26_gm_rm019
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty0_yolo_detection_stream_audit.py --config outputs\oty2_yolo26_detector_swap_probe_<timestamp>\oty_yolo26_probe_config.yaml --manifest outputs\oty2_yolo26_detector_swap_probe_<timestamp>\oty0_yolo26_probe_manifest.csv --scene GM_RM017 --output-root outputs\oty2_yolo26_detector_swap_probe_<timestamp> --timestamp yolo26_gm_rm017
```

4. Compare YOLO11l and YOLO26 OTY0 tables with a diagnostic-only summary. Do not change OTY1/OTY1t inputs until the OTY0 detector observation comparison is reviewed.

5. If later authorized and only if OTY0 schema compatibility passes, run a ByteTrack unmatched-detection comparison as a downstream probe. Treat this as association sensitivity evidence, not as tracker replacement evidence.

## Feasibility State

`YOLO26_CODEPATH_AVAILABLE_WEIGHTS_ABSENT`

Meaning:

- The installed Ultralytics package has YOLO26 model configs.
- Official Ultralytics documentation supports using YOLO26 through the same Python API pattern used by OTY0.
- Current OTY0 schema is compatible with a standard YOLO26 Detect result if `result.boxes.xyxy/conf/cls` are populated.
- No local YOLO26 weight was found, so no actual model-load or OTY0 smoke test can be claimed.

## Recommendation

Do not replace the mainline detector and do not edit OTY0/OTY1/OTY1t runtime.

Next safe step, if the user authorizes a probe, is to acquire or place a local YOLO26 Detect weight outside the repo, create a temporary ignored probe config/manifest, and run OTY0-only side-by-side on `GM_RM011`, `GM_RM019`, and `GM_RM017`. The probe should compare observation cleanliness before tracking: duplicate-like same-frame pairs, class-instability overlaps, partial/full competition, boundary-touch detections, and confidence/count distributions.

Only after the detector-observation comparison is reviewed should ByteTrack unmatched-detection comparison be considered. Even then, the result remains detector-swap diagnosis, not mainline replacement or identity truth.

## No-Overstep Check

This report did not:

- replace `yolo11l.pt`;
- edit `configs/oty_yolo_stream_config.yaml`;
- edit `manifests/oty0_yolo_manifest.csv`;
- edit OTY0, OTY1, OTY1t, P4, or P4G runtime logic;
- run OTY0/OTY1/OTY1t diagnostics;
- create outputs runtime artifacts;
- create atlas files;
- create final annotation;
- create revised GT;
- create final boxes;
- create selector/ranking output;
- tune thresholds;
- enter SAR pairing;
- enter support audit;
- promote GM_RM011 into clean `215`;
- use SAR GT or SAR image observation for optical runtime identity.
