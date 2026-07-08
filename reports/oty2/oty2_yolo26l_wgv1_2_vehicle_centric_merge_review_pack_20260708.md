# OTY2 YOLO26l WGV1.2 vehicle-centric merge review pack

Date: 2026-07-08

## Conclusion

This pass builds a human review pack from the same-vehicle merge review queue. It does not force multiple target families into one vehicle_group. Instead, each of the 11 review-only merge candidates is a separate review item, and each item shows selected primary candidates together with same-frame competing candidates.

The pack is diagnostic only: no final boxes, no GT boxes, no final/revised annotation, no SAR, and no tracker replay.

## Ignored Output Directory

```text
D:/profile/research/optical-sar-visual-diagnosis/outputs/oty2/y26l_wgv1_2_vehicle_centric_merge_review_20260708/
```

This directory contains annotated PNG frames and must not be committed.

## Committable Index

- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_2_vehicle_centric_merge_review_pack_manifest_20260708.csv`
- `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_2_vehicle_centric_merge_review_pack_frame_manifest_20260708.csv`

## Review Queue Summary

| review_item_id | scene_id | from_target_family | to_target_family | frames | competing | SAR-ready |
|---|---|---|---|---|---|---|
| MRQ001 | GM_RM011 | GM_RM011_WGV12TF001 | GM_RM011_WGV12TF002 | 0-9 | 9 frames | no / blocked |
| MRQ002 | GM_RM011 | GM_RM011_WGV12TF003 | GM_RM011_WGV12TF004 | 10-16 | 6 frames | no / blocked |
| MRQ003 | GM_RM011 | GM_RM011_WGV12TF004 | GM_RM011_WGV12TF005 | 13-25 | 11 frames | no / blocked |
| MRQ004 | GM_RM011 | GM_RM011_WGV12TF005 | GM_RM011_WGV12TF006 | 18-35 | 17 frames | no / blocked |
| MRQ005 | GM_RM011 | GM_RM011_WGV12TF008 | GM_RM011_WGV12TF009 | 151-166 | 8 frames | no / blocked |
| MRQ006 | GM_RM011 | GM_RM011_WGV12TF011 | GM_RM011_WGV12TF012 | 233-239 | 6 frames | no / blocked |
| MRQ007 | GM_RM011 | GM_RM011_WGV12TF017 | GM_RM011_WGV12TF018 | 265-270 | 2 frames | no / blocked |
| MRQ008 | GM_RM011 | GM_RM011_WGV12TF018 | GM_RM011_WGV12TF019 | 269-288 | 12 frames | no / blocked |
| MRQ009 | GM_RM017 | GM_RM017_WGV12TF001 | GM_RM017_WGV12TF002 | 118-148 | 9 frames | no / blocked |
| MRQ010 | GM_RM017 | GM_RM017_WGV12TF005 | GM_RM017_WGV12TF006 | 158-168 | 11 frames | no / blocked |
| MRQ011 | GM_RM017 | GM_RM017_WGV12TF011 | GM_RM017_WGV12TF012 | 200-214 | 1 frames | no / blocked |

## Human Review Questions

For every item, inspect `frames_yolo_annotated/` in frame order:

1. Do `from_target_family` and `to_target_family` preserve the same real-vehicle referent?
2. Are center position, box area, class label, and `x_bin` temporally continuous?
3. Are orange `competing` candidates more plausible as the successor target?
4. Is there any truck/car, white/black vehicle, or left/right vehicle cross-target jump?
5. If uncertain, keep `review_required`; do not auto-merge.

## Boundary

- `auto_merge_allowed=no`
- `sar_ready=no / blocked`
- Do not write new bbox coordinates.
- Do not generate final boxes / GT boxes / revised annotation.
- Do not enter SAR pairing/support/selector/ranking.
