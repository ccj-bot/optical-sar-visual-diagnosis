# OTY2 YOLO26 Weight Download And Schema Smoke

Timestamp: `20260704_230517`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Starting commit: `7b926a4 Report YOLO26 probe blocked by missing weights`

## Boundary

This pass corrected the prior missing-weight blocker by allowing Ultralytics network download of YOLO26 Detect weights into the workspace artifact directory.

No mainline detector was replaced. No `.pt` weight was added to Git. No `configs/oty_yolo_stream_config.yaml` or `manifests/oty0_yolo_manifest.csv` edits were made. No OTY0 runtime code, OTY1, OTY1a, OTY1t, P4, P4G, or tracker code was changed. No OTY0 three-scene detector quality probe was run. No threshold tuning, final annotation, revised GT, final box, selector/ranking output, weighted fusion, SAR pairing, support audit, identity-truth claim, or GM_RM011 clean-215 promotion was performed.

## Sources Read

- `docs/OTY2_SESSION_START_HERE.md`
- `reports/oty2/oty2_yolo26_detector_swap_feasibility_20260704_224235.md`
- `reports/oty2/oty2_yolo26_detector_swap_probe_20260704_225021.md`

## Environment

Interpreter:

```text
D:\MINICONDA\envs\py311\python.exe
```

Observed environment:

| Check | Result |
| --- | --- |
| `ultralytics.__version__` | `8.4.21` |
| `torch.__version__` | `2.10.0+cu128` |
| CUDA available | `True` |

The machine has a CUDA-capable GPU and the current code path successfully used the installed Ultralytics package to download, load, and predict with YOLO26 weights.

## Download Results

Download/work directory:

```text
D:\profile\research\workspace\artifacts\detector_weights
```

The download was initiated by calling `YOLO("yolo26n.pt")` and `YOLO("yolo26l.pt")` from that directory. Ultralytics downloaded from its assets release path, observed as:

```text
https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt
https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26l.pt
```

| Model | Download status | Final local path | File size |
| --- | --- | --- | ---: |
| `yolo26n.pt` | success | `D:\profile\research\workspace\artifacts\detector_weights\yolo26n.pt` | 5,544,453 bytes |
| `yolo26l.pt` | success | `D:\profile\research\workspace\artifacts\detector_weights\yolo26l.pt` | 53,211,173 bytes |

No copy step was needed because the download command ran inside the target artifact directory.

## Local Load Check

Both local absolute paths loaded successfully through the same Ultralytics API pattern expected by OTY0:

```python
from ultralytics import YOLO
YOLO(r"D:\profile\research\workspace\artifacts\detector_weights\yolo26n.pt")
YOLO(r"D:\profile\research\workspace\artifacts\detector_weights\yolo26l.pt")
```

| Model | Local path load | `model.names` contains `car` | contains `bus` | contains `truck` | Vehicle class ids |
| --- | --- | --- | --- | --- | --- |
| `yolo26n.pt` | pass | yes | yes | yes | `car=2`, `bus=5`, `truck=7` |
| `yolo26l.pt` | pass | yes | yes | yes | `car=2`, `bus=5`, `truck=7` |

## Predict Schema Smoke

Smoke input frame:

```text
D:\profile\research\data\GM_RM011\GM_RM011_frames\000047.png
```

Smoke call shape:

```python
model.predict(source=frame, imgsz=960, conf=0.25, save=False, verbose=False, stream=False)
```

This used the existing OTY0-style image size and confidence setting for schema compatibility only. It was not threshold tuning and did not save prediction outputs.

| Model | Predict status | Result count | Boxes present | Boxes rows | `boxes.xyxy` | `boxes.conf` | `boxes.cls` | Detected class sample | Confidence sample |
| --- | --- | ---: | --- | ---: | --- | --- | --- | --- | ---: |
| `yolo26n.pt` | pass | 1 | yes | 1 | shape `[1, 4]` | shape `[1]` | shape `[1]` | `car` | 0.856208 |
| `yolo26l.pt` | pass | 1 | yes | 1 | shape `[1, 4]` | shape `[1]` | shape `[1]` | `car` | 0.703370 |

The schema fields required by current OTY0 are therefore available from both YOLO26 Detect weights:

- bbox xyxy from `result.boxes.xyxy`;
- confidence from `result.boxes.conf`;
- class id from `result.boxes.cls`;
- class name from `model.names`;
- scene/frame/path/detection ids remain OTY0-derived fields.

## Required Questions

1. Can YOLO26 Detect be downloaded over the network?

Yes. `yolo26n.pt` and `yolo26l.pt` both downloaded successfully via Ultralytics.

2. Where are the final weights?

```text
D:\profile\research\workspace\artifacts\detector_weights\yolo26n.pt
D:\profile\research\workspace\artifacts\detector_weights\yolo26l.pt
```

3. Can the weights be loaded from local path?

Yes. Both local absolute paths loaded with `ultralytics.YOLO(...)`.

4. Can prediction run on a GM_RM011 optical frame?

Yes. Both models predicted on `GM_RM011_frames\000047.png` with `save=False`.

5. Do `result.boxes.xyxy`, `result.boxes.conf`, and `result.boxes.cls` exist?

Yes for both models. Each smoke result returned one box and populated all three fields.

6. Does `model.names` contain `car`, `truck`, and `bus`?

Yes for both models, with class ids `2`, `7`, and `5` respectively.

## Conclusion

```text
YOLO26_WEIGHTS_READY_FOR_DETECTOR_SWAP_PROBE
```

The previous blocker `BLOCKED_MISSING_YOLO26_DETECT_WEIGHTS` is resolved for Detect-model smoke purposes. `yolo26n.pt` is ready as a schema smoke weight, and `yolo26l.pt` is ready as the fairer large-model detector-swap comparator against the current `yolo11l.pt` baseline.

This is not a mainline replacement. It only confirms that the next isolated OTY0-only detector quality probe can be run without changing the main OTY0 config/manifest or downstream runtime.

## Next Safe Step

Run the previously designed isolated OTY0-only detector quality probe using `yolo26l.pt` against existing YOLO11l baselines for:

- `GM_RM011`;
- `GM_RM019`;
- `GM_RM017`.

The probe should use temporary ignored config/manifest files under an ignored `outputs\oty2_yolo26_detector_swap_probe_<timestamp>\` directory and compare:

- total detection rows;
- frames with detections;
- empty detection frames;
- per-frame detection count distribution;
- class distribution;
- confidence distribution;
- high-overlap same-frame pair count;
- class-instability duplicate-like pair count;
- partial/full competition count;
- boundary-touch ratio;
- crowded-frame ratio.

Do not run ByteTrack unless separately authorized as a downstream tracker-side probe.

Even if YOLO26 improves duplicate-like observations, OTY0-post pre-tracking observation grouping remains a likely required mechanism layer because class instability, partial/full competition, boundary contact, and crowded-frame ambiguity must remain explicit uncertainty/context instead of identity truth.

## No-Overstep Check

This pass did not:

- commit `.pt` weights;
- commit outputs runtime artifacts;
- replace `yolo11l.pt`;
- edit `configs/oty_yolo_stream_config.yaml`;
- edit `manifests/oty0_yolo_manifest.csv`;
- edit OTY0 runtime;
- edit tracker code;
- tune thresholds;
- create final annotations;
- create revised GT;
- create final boxes;
- create selector/ranking output;
- enter SAR pairing;
- enter support audit;
- promote GM_RM011 into clean `215`;
- claim identity truth.
