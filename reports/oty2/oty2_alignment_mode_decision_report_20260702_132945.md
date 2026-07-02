# OTY2-P1 Temporal Metadata and Anchor Audit

OTY2-P1 audits temporal metadata and anchor availability only. It does not enter SAR spatial search, read SAR image content, use SAR GT, use selectors, train thresholds, or create annotation proposals.

## Direct Answers

### GM_RM011

1. Optical real timestamps: `no`
2. SAR real timestamps: `no`
3. Known FPS scale: `optical_fps=24`, `sar_fps=50`, scale=`2.083333`
4. Scene start/end timing record: `false`
5. Manual optical/SAR anchor present: `false` allowed, `1` candidate rows inspected
6. Start offset status: `unknown`; frame 0 alignment: `unverified_not_assumed`
7. Upgrade beyond frame_ratio_hypothesis: `true` -> `timestamp_offset_scale_hypothesis`
8. Exact remaining blocker: `missing_p4g_object_level_inputs;missing_start_offset_or_manual_anchor;frame0_alignment_unverified_not_assumed`

Decision: `timestamp_offset_scale_hypothesis` with confidence `low` / `known_fps_ratio_missing_start_offset`.

### GM_RM017

1. Optical real timestamps: `no`
2. SAR real timestamps: `no`
3. Known FPS scale: `optical_fps=24`, `sar_fps=50`, scale=`2.083333`
4. Scene start/end timing record: `false`
5. Manual optical/SAR anchor present: `false` allowed, `1` candidate rows inspected
6. Start offset status: `unknown`; frame 0 alignment: `unverified_not_assumed`
7. Upgrade beyond frame_ratio_hypothesis: `true` -> `timestamp_offset_scale_hypothesis`
8. Exact remaining blocker: `missing_start_offset_or_manual_anchor;frame0_alignment_unverified_not_assumed`

Decision: `timestamp_offset_scale_hypothesis` with confidence `low` / `known_fps_ratio_missing_start_offset`.

### GM_RM019

1. Optical real timestamps: `no`
2. SAR real timestamps: `no`
3. Known FPS scale: `optical_fps=24`, `sar_fps=50`, scale=`2.083333`
4. Scene start/end timing record: `false`
5. Manual optical/SAR anchor present: `false` allowed, `5` candidate rows inspected
6. Start offset status: `unknown`; frame 0 alignment: `unverified_not_assumed`
7. Upgrade beyond frame_ratio_hypothesis: `true` -> `timestamp_offset_scale_hypothesis`
8. Exact remaining blocker: `missing_start_offset_or_manual_anchor;frame0_alignment_unverified_not_assumed`

Decision: `timestamp_offset_scale_hypothesis` with confidence `low` / `known_fps_ratio_missing_start_offset`.

## Per-Scene Decision Table

| scene | optical frames | SAR frames | frame count ratio | known fps scale | offset status | manual anchor | decision | confidence status | can upgrade | blocker |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |
| `GM_RM011` | 368 | 766 | 2.081522 | 2.083333 | `unknown` | `false` | `timestamp_offset_scale_hypothesis` | `known_fps_ratio_missing_start_offset` | `true` | `missing_p4g_object_level_inputs;missing_start_offset_or_manual_anchor;frame0_alignment_unverified_not_assumed` |
| `GM_RM017` | 368 | 766 | 2.081522 | 2.083333 | `unknown` | `false` | `timestamp_offset_scale_hypothesis` | `known_fps_ratio_missing_start_offset` | `true` | `missing_start_offset_or_manual_anchor;frame0_alignment_unverified_not_assumed` |
| `GM_RM019` | 368 | 766 | 2.081522 | 2.083333 | `unknown` | `false` | `timestamp_offset_scale_hypothesis` | `known_fps_ratio_missing_start_offset` | `true` | `missing_start_offset_or_manual_anchor;frame0_alignment_unverified_not_assumed` |

## Interpretation

- Numeric frame filenames and frame counts define inventory/order only; they do not prove acquisition FPS or synchronization.
- The known acquisition FPS values are scale metadata only: optical_fps=24 and sar_fps=50. They are not per-frame timestamp truth and do not imply optical frame 0 aligns to SAR frame 0.
- `timestamp_offset_scale_hypothesis` requires the known FPS scale plus an unresolved offset audit; with no start/end timing record or manual anchor, `offset_status=unknown`.
- Filesystem modification time is recorded as weak filesystem metadata only and never upgrades the alignment mode.
- Visual-diagnosis sample pairs are treated as candidate context, not temporal anchors, unless a source explicitly declares an optical/SAR timing or frame correspondence anchor and avoids GT/selector/posthoc authority.
- OTY2-P1 leaves object_hypothesis_id, readiness gates, primary/secondary observation logic, and identity status unchanged.

## Boundary Flags

- sar_image_content_used: `false`
- sar_gt_used: `false`
- sar_band_entered: `false`
- selector_used: `false`
- annotation_proposal_entered: `false`
- identity_truth_claimed: `false`

## Artifacts

- temporal_metadata_inventory: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_metadata_inventory_20260702_132945.csv`
- scene_alignment_anchor_candidates: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_scene_alignment_anchor_candidates_20260702_132945.csv`
- alignment_mode_decision_report: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_alignment_mode_decision_report_20260702_132945.md`
- temporal_alignment_anchor_summary: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_alignment_anchor_summary_20260702_132945.json`
- alignment_mode_decision_summary: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_alignment_mode_decision_summary_20260702_132945.csv`
- temporal_metadata_inventory_sample: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_temporal_metadata_inventory_sample.csv`
- scene_alignment_anchor_candidates_sample: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_scene_alignment_anchor_candidates_sample.csv`
- alignment_mode_decision_summary_sample: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\samples\oty2_alignment_mode_decision_summary_sample.csv`
