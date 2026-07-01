# OTY0 Runtime/Posthoc Boundary

## Runtime Source

OTY0 runtime detections come only from YOLO inference over raw optical frames.

Allowed runtime fields:

- scene
- optical frame number and path
- YOLO detector id
- YOLO class id/name
- YOLO confidence
- YOLO bbox geometry

## Posthoc Sources

`review_queue.csv`, `final_gt_working.csv`, SAR GT, final boxes, manual labels, oracle labels, and review metadata are posthoc/audit-only. OTY0 may count them in inventories, but it cannot use them to generate detections.

## Explicit Non-Goals

OTY0 does not perform tracking, SAR band transfer, SAR GT coverage, selector, G2, A008 scoring, annotation proposal, threshold tuning, or training.

YOLO confidence is an optical detector output filter for this audit. It is not a SAR selector threshold.
