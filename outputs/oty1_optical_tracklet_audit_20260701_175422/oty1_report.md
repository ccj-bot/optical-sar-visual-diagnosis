# OTY1 Optical Tracklet Construction Audit

Generated: `2026-07-01T17:54:22`
Scene: `GM_RM019`

## Input

- OTY0 detection table: `outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv`
- runtime source: OTY0 YOLO detections only
- no review/final/SAR GT source used for runtime construction

## Results

- total detections: `334`
- total optical frames: `368`
- frames with detections: `193`
- candidate edge rows: `1612`
- within-limit edge rows: `1367`
- tracklet candidate count: `54`
- high-confidence geometry-only candidates: `0`
- ambiguous tracklets: `24`
- fragmented short tracks: `30`
- same-frame conflict count: `0`
- neighbor ambiguity count: `115`
- boundary contact count: `138`

## Component Size Distribution

{"1": 22, "2": 8, "3": 5, "4": 3, "5": 3, "7": 1, "8": 1, "10": 1, "11": 1, "12": 2, "13": 2, "15": 1, "18": 1, "41": 1, "42": 1, "52": 1}

## Boundary Check

- no SAR alignment
- no SAR band
- no SAR GT coverage
- no GT/final/manual/oracle/review fields used for runtime construction
- tracklet identity remains candidate-only unless a future runtime-safe track-id source is proven

## Blockers

- none

## OTY2 Next Step

Audit optical-to-SAR high-FPS temporal alignment from the optical tracklet state stream without assuming optical frame number equals SAR frame number.
