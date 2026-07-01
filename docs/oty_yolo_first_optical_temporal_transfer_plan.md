# OTY YOLO-First Optical Temporal Transfer Plan

## Why OTY Must Be YOLO-First

The automatic annotation mechanism must start from raw optical frames, not from manually paired CSV rows. The intended runtime chain is:

```text
raw optical frames
-> YOLO vehicle detections
-> optical tracklets
-> optical vehicle-state stream
-> optical-to-SAR high-FPS alignment
-> SAR fan/range band
-> SAR GT posthoc coverage audit
```

The runtime optical source is the YOLO detector output. Existing CSVs and SAR GT remain useful, but only as posthoc audit material.

## OT0 Bootstrap Limitation

The existing OT0 audit used `review_queue.csv` optical bbox fields as a bootstrap source. That is valuable for source-boundary auditing and state-feature prototyping, but it is not the future automatic pipeline.

`review_queue.csv` is a manual/review queue created after optical detections were associated with SAR review context. It can seed a boundary audit, but it cannot replace raw-frame YOLO detections in the runtime path.

OT0 should therefore be interpreted as:

```text
OT0-B: bootstrap audit from manual-paired bbox inventory
```

OTY0 starts the corrected YOLO-first line.

## Runtime Vs Posthoc Boundary

Runtime-safe OTY inputs:

- raw optical frame paths
- YOLO model path or command
- YOLO detection output fields: frame, detector id, class, confidence, bbox
- configured frame ranges
- scene paths and frame inventory

Posthoc-only OTY sources:

- `review_queue.csv`
- `final_gt_working.csv`
- SAR GT / final / manual / oracle annotations
- review status, chosen candidate source, IoU, center error, and manual notes

Forbidden for runtime generation:

- using existing CSV bbox columns as YOLO detections
- using GT/final/oracle/manual/review fields to create detections, tracklets, SAR bands, or annotation proposals
- using posthoc coverage to tune thresholds
- entering selector, G2, A008 scoring, training, or candidate-pool tuning

## SAR High-FPS Alignment Principle

SAR frame rate is higher than optical frame rate. OTY must not assume:

```text
optical frame i == SAR frame i
```

OTY0 does not perform SAR alignment. It records the alignment status as unknown unless explicit timing metadata is configured. Later stages should support:

- nearest SAR frame baseline
- SAR frame window per optical frame
- interpolated optical state at SAR frame rate
- state-conditioned SAR band tube

## Stages

OTY0: YOLO detection stream audit from raw optical frames. Output a standardized runtime detection table and dependency/source audit.

OTY1: Construct optical tracklets from YOLO detections only. CSV/GT may be used posthoc to judge coverage and failure modes.

OTY2: Audit optical-to-SAR temporal alignment under higher SAR FPS. Do not assume same frame number.

OTY3: Transfer optical tracklet states into SAR fan/range band corridors without using SAR GT to generate the band.

OTY4: Use SAR GT for posthoc band coverage audit only.

OTY5: Propose automatic annotation only after OTY0-OTY4 support the mechanism; no selector or threshold work is implied by OTY0.

## OTY0 Output Contract

OTY0 produces:

- optical frame inventory
- YOLO dependency audit
- standardized YOLO detection table or blocker report
- detection schema
- posthoc source inventory
- runtime/posthoc boundary report
- summary JSON and report markdown
- detection contact sheet and simple visual panels when detections exist

The detection table is the only runtime detection output from OTY0.
