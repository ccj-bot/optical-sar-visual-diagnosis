# OTY2 YOLO26l WGV1.2 merge review queue triage

Date: 2026-07-08

## Conclusion

This triage ranks the 11 review-only same-vehicle merge candidates for human inspection. It does not accept any merge and does not create final boxes, GT boxes, final/revised annotations, SAR-ready evidence, or tracker replay output.

- triage CSV: `D:/profile/research/optical-sar-visual-diagnosis/reports/oty2/samples/oty2_yolo26l_wgv1_2_merge_review_queue_triage_20260708.csv`
- high risk: 6
- medium risk: 5
- low risk: 0

Machine labels:

- `manual_review_candidate_with_competing_context`: 5
- `manual_review_high_risk_keep_separate_until_confirmed`: 6

## Review Items

| review_item_id | scene_id | frames | risk_level | label | key reasons | focus |
|---|---|---|---|---|---|---|
| MRQ001 | GM_RM011 | 0-9 | medium | manual_review_candidate_with_competing_context | high_competing_frame_ratio;same_frame_close_competition | same-frame competing vehicle choice |
| MRQ002 | GM_RM011 | 10-16 | medium | manual_review_candidate_with_competing_context | high_competing_frame_ratio;same_frame_close_competition | same-frame competing vehicle choice |
| MRQ003 | GM_RM011 | 13-25 | high | manual_review_high_risk_keep_separate_until_confirmed | high_competing_frame_ratio;same_frame_class_competition;same_frame_close_competition | class/vehicle-type conflict; same-frame competing vehicle choice |
| MRQ004 | GM_RM011 | 18-35 | high | manual_review_high_risk_keep_separate_until_confirmed | endpoint_center_jump_review;high_competing_frame_ratio;same_frame_class_competition;x_bin_switch | class/vehicle-type conflict; left/mid/right lane-slot continuity; same-frame competing vehicle choice |
| MRQ005 | GM_RM011 | 151-166 | high | manual_review_high_risk_keep_separate_until_confirmed | detectionless_gap_context;endpoint_area_ratio_review;high_competing_frame_ratio;same_frame_class_competition;same_frame_close_competition;selected_area_jump_high | class/vehicle-type conflict; same-frame competing vehicle choice; detectionless gap frames; box area / partial-full transition |
| MRQ006 | GM_RM011 | 233-239 | medium | manual_review_candidate_with_competing_context | high_competing_frame_ratio | same-frame competing vehicle choice |
| MRQ007 | GM_RM011 | 265-270 | medium | manual_review_candidate_with_competing_context | detectionless_gap_context | detectionless gap frames |
| MRQ008 | GM_RM011 | 269-288 | high | manual_review_high_risk_keep_separate_until_confirmed | high_competing_frame_ratio;same_frame_close_competition;x_bin_switch | left/mid/right lane-slot continuity; same-frame competing vehicle choice |
| MRQ009 | GM_RM017 | 118-148 | high | manual_review_high_risk_keep_separate_until_confirmed | same_frame_class_competition;same_frame_close_competition | class/vehicle-type conflict; same-frame competing vehicle choice |
| MRQ010 | GM_RM017 | 158-168 | high | manual_review_high_risk_keep_separate_until_confirmed | high_competing_frame_ratio;same_frame_class_competition;same_frame_close_competition | class/vehicle-type conflict; same-frame competing vehicle choice |
| MRQ011 | GM_RM017 | 200-214 | medium | manual_review_candidate_with_competing_context | endpoint_area_ratio_review;same_frame_close_competition | same-frame competing vehicle choice; box area / partial-full transition |

## Boundary

- `auto_merge_allowed=no` for every row.
- `sar_ready=no / blocked` for every row.
- These are review priorities, not same-vehicle truth.
- Human review must inspect selected primary boxes together with same-frame competing candidates.
