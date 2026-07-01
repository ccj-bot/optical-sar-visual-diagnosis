# OTY1 Optical Tracklet Construction Audit

Generated: `2026-07-01T18:13:47`
Scene: `GM_RM017`

## Input

- OTY0 detection table: `outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv`
- runtime source: OTY0 YOLO detections only
- no review/final/SAR GT source used for runtime construction

## Results

- total detections: `215`
- total optical frames: `368`
- frames with detections: `100`
- candidate edge rows: `1050`
- within-limit edge rows: `916`
- tracklet candidate count: `10`
- high-confidence geometry-only candidates: `0`
- ambiguous tracklets: `6`
- fragmented short tracks: `4`
- same-frame conflict count: `0`
- neighbor ambiguity count: `28`
- boundary contact count: `93`

## Component Size Distribution

{"1": 4, "4": 1, "10": 1, "43": 1, "48": 1, "52": 1, "54": 1}

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
