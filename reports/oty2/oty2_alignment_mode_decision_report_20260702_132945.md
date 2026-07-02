# OTY2-P1 Temporal Metadata and Anchor Audit

OTY2-P1 audits temporal metadata and anchor availability only. It does not enter SAR spatial search, read SAR image content, use SAR GT, use selectors, train thresholds, or create annotation proposals.

## Direct Answers

### GM_RM011

1. Optical real timestamps: `no`
2. SAR real timestamps: `no`
3. Known FPS scale: `optical_fps=24`, `sar_fps=50`, scale=`2.083333`
4. Software sync contract: `software_sync_zero_offset_assumption`, offset_seconds=`0`, jitter_ms=`20`
5. Scene start/end timing record: `false`
6. Manual optical/SAR anchor present: `false` allowed, `1` candidate rows inspected
7. Start offset status: `software_sync_zero_offset_assumed`; frame 0 alignment: `software_sync_same_start_not_hardware_exact`
8. Upgrade beyond frame_ratio_hypothesis: `true` -> `timestamp_offset_scale_hypothesis`
9. Remaining caveat/blocker: `missing_p4g_object_level_inputs;non_hardware_sync_jitter_margin_required`

Decision: `timestamp_offset_scale_hypothesis` with confidence `medium` / `software_sync_zero_offset_with_jitter_margin`.

### GM_RM017

1. Optical real timestamps: `no`
2. SAR real timestamps: `no`
3. Known FPS scale: `optical_fps=24`, `sar_fps=50`, scale=`2.083333`
4. Software sync contract: `software_sync_zero_offset_assumption`, offset_seconds=`0`, jitter_ms=`20`
5. Scene start/end timing record: `false`
6. Manual optical/SAR anchor present: `false` allowed, `1` candidate rows inspected
7. Start offset status: `software_sync_zero_offset_assumed`; frame 0 alignment: `software_sync_same_start_not_hardware_exact`
8. Upgrade beyond frame_ratio_hypothesis: `true` -> `timestamp_offset_scale_hypothesis`
9. Remaining caveat/blocker: `non_hardware_sync_jitter_margin_required`

Decision: `timestamp_offset_scale_hypothesis` with confidence `medium` / `software_sync_zero_offset_with_jitter_margin`.

### GM_RM019

1. Optical real timestamps: `no`
2. SAR real timestamps: `no`
3. Known FPS scale: `optical_fps=24`, `sar_fps=50`, scale=`2.083333`
4. Software sync contract: `software_sync_zero_offset_assumption`, offset_seconds=`0`, jitter_ms=`20`
5. Scene start/end timing record: `false`
6. Manual optical/SAR anchor present: `false` allowed, `5` candidate rows inspected
7. Start offset status: `software_sync_zero_offset_assumed`; frame 0 alignment: `software_sync_same_start_not_hardware_exact`
8. Upgrade beyond frame_ratio_hypothesis: `true` -> `timestamp_offset_scale_hypothesis`
9. Remaining caveat/blocker: `non_hardware_sync_jitter_margin_required`

Decision: `timestamp_offset_scale_hypothesis` with confidence `medium` / `software_sync_zero_offset_with_jitter_margin`.

## Per-Scene Decision Table

| scene | optical frames | SAR frames | frame count ratio | known fps scale | sync mode | offset status | manual anchor | decision | confidence status | can upgrade | caveat/blocker |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |
| `GM_RM011` | 368 | 766 | 2.081522 | 2.083333 | `software_sync_zero_offset_assumption` | `software_sync_zero_offset_assumed` | `false` | `timestamp_offset_scale_hypothesis` | `software_sync_zero_offset_with_jitter_margin` | `true` | `missing_p4g_object_level_inputs;non_hardware_sync_jitter_margin_required` |
| `GM_RM017` | 368 | 766 | 2.081522 | 2.083333 | `software_sync_zero_offset_assumption` | `software_sync_zero_offset_assumed` | `false` | `timestamp_offset_scale_hypothesis` | `software_sync_zero_offset_with_jitter_margin` | `true` | `non_hardware_sync_jitter_margin_required` |
| `GM_RM019` | 368 | 766 | 2.081522 | 2.083333 | `software_sync_zero_offset_assumption` | `software_sync_zero_offset_assumed` | `false` | `timestamp_offset_scale_hypothesis` | `software_sync_zero_offset_with_jitter_margin` | `true` | `non_hardware_sync_jitter_margin_required` |

## Interpretation

- Numeric frame filenames and frame counts define inventory/order only; they do not prove acquisition FPS or synchronization.
- The known acquisition FPS values are scale metadata only: optical_fps=24 and sar_fps=50. They are not per-frame timestamp truth.
- The acquisition contract uses a software-synchronized zero-offset start assumption, not hardware-grade exact synchronization.
- `timestamp_offset_scale_hypothesis` uses sar_frame = optical_frame * 50 / 24, not sar_frame = optical_frame * 2, and keeps a millisecond-level jitter margin for future window generation.
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
