# OTY1t Standard MOT Tracker Audit

Generated: `2026-07-01T20:30:48`
Scene: `GM_RM017`

## Runtime Input

- OTY0 detection table: `outputs\oty0_yolo_detection_stream_audit_20260701_181317\oty0_yolo_detection_table.csv`
- tracker: `bytetrack`
- tracker input mode: `detection_table_replay`
- detector source: `oty0_yolo_detection_table`
- runtime source policy: OTY0 YOLO detections only, plus raw optical frame inventory for replay gaps

## Results

- detection rows in: `215`
- tracked assignment rows: `196`
- tracker track count: `6`
- stable hypotheses: `4`
- fragmented hypotheses: `0`
- ambiguous hypotheses: `2`
- short hypotheses: `0`
- possible ID switch events: `1`
- duplicate overlap events: `0`
- lost events: `8`
- reactivated events: `2`
- low-score recovery events: `0`

## 0039/0045

- tracker connected: `false`
- confirmed identity: `false`

## Boundary

- posthoc sources used for runtime tracking: `false`
- SAR alignment entered: `false`
- SAR band entered: `false`
- SAR GT coverage entered: `false`
- annotation proposal entered: `false`

OTY1t adds standard MOT tracker-derived optical identity hypotheses and state/event audits. Tracker IDs remain runtime optical hypotheses, not confirmed identities. No SAR alignment, SAR band, SAR GT coverage, SAR evidence sampling, selector, training, or annotation proposal was introduced.

## Blockers

- none

## Next Step

OTY2 can start as a temporal alignment audit only: optical track/state time must be mapped to SAR high-FPS time without assuming equal frame numbers and before any SAR fan/range band generation.
