# OTY1 Runtime/Posthoc Boundary

## Runtime Source

OTY1 runtime construction reads only:

- OTY0 YOLO detection table: `outputs\oty0_yolo_detection_stream_audit_20260701_170751\oty0_yolo_detection_table.csv`
- OTY0 detector fields: scene, optical frame number/path, det_id, class id/name, confidence, bbox geometry
- Optical image dimensions derived from raw optical frame files for boundary-contact proxies

## Posthoc-Only Sources

`review_queue.csv`, `final_gt_working.csv`, SAR GT, final/manual/oracle/review fields, posthoc IoU, target identity, group ids, and SAR evidence are not used to build OTY1 edges, components, or state streams.

## Forbidden In OTY1

- selector, G2, A008 scoring, threshold tuning, or training
- SAR alignment or optical/SAR same-frame assumptions
- SAR fan/range band generation
- SAR GT coverage evaluation
- automatic annotation proposal

OTY1 outputs geometry-only optical tracklet candidates. They are not confirmed same-target identity truth.
