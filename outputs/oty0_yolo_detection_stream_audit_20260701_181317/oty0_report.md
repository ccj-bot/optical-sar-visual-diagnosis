# OTY0 YOLO-First Optical Detection Stream Audit

Generated: `2026-07-01T18:13:35`
Scene: `GM_RM017`

## Input

- optical frames dir: `D:\profile\research\data\GM_RM017\GM_RM017_frames`
- YOLO model: `D:\profile\research\workspace\artifacts\detector_weights\yolo11l.pt`
- posthoc review queue: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\review_queue.csv`
- posthoc final GT: `D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv`

## Results

- optical frame count: `368`
- YOLO runnable: `True`
- detection table generated: `True`
- detection row count: `215`
- frames with detections: `100`
- cache used: `False`

## Boundary Check

- no formal pipeline modification
- no selector, G2, threshold, A008 scoring, or training
- no tracking, SAR band, SAR GT coverage, or annotation proposal
- existing CSV/SAR GT sources are posthoc inventory only
- no optical/SAR one-to-one frame sync assumed

## Blockers

- none

## OTY1 Readiness

GO for OTY1 tracklet construction from YOLO detections only; keep CSV/SAR GT posthoc-only.
