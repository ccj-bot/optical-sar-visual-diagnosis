# OTY2 Stage Recap And Next Branch Handoff

Updated: 2026-07-02

This document closes the current OTY2 audit stage and gives a new-session handoff. It does not introduce a new experiment. It normalizes naming, sample accounting, and boundaries across the recent OTY2 outputs.

## Current Chain

The current chain is:

1. Optical object stream
2. Software-synchronized optical-to-SAR temporal windows
3. Runtime-safe weak spatial priors
4. Vehicle research eligibility audit
5. GT posthoc correspondence mechanism discovery
6. Detection-dropout temporal continuation and SAR posthoc support audit

The chain is intentionally layered. Runtime-safe construction and posthoc mechanism discovery are not the same layer.

## Naming Fix

The older name `clean_recovered_by_temporal_continuation` is misleading and has been replaced in the latest detection-dropout audit with:

`existence_recovered_by_temporal_continuation`

Chinese interpretation: 时序延续恢复目标存在性。

This means temporal context can explain target presence despite current-frame detector dropout or severe truncation. It does not mean:

- clean paired
- complete optical-box morphology sample
- automatic annotation
- identity truth
- final SAR location

The 12 detection-dropout rows remain excluded from clean optical-shape statistics.

## Normalized Boundary Flags

Use these names for new OTY2 reports:

- `posthoc_sar_gt_used`
- `posthoc_sar_image_content_used`
- `gt_or_sar_image_used_for_runtime_prior_construction`
- `runtime_prior_construction_used_gt`
- `annotation_proposal_entered`
- `training_or_threshold_tuning_entered`
- `identity_truth_claimed`
- `model_weights_committed`

For the current detection-dropout support audit:

- `posthoc_sar_gt_used=true`
- `posthoc_sar_image_content_used=true`
- `gt_or_sar_image_used_for_runtime_prior_construction=false`
- `runtime_prior_construction_used_gt=false`
- `annotation_proposal_entered=false`
- `training_or_threshold_tuning_entered=false`
- `identity_truth_claimed=false`
- `model_weights_committed=false`

Older reports may still contain legacy names such as `sar_gt_used`, `sar_image_content_used`, or `automatic_annotation_proposal_generated`. Interpret those through this normalized boundary contract rather than as a new runtime permission.

## Sample Ledger

Full GT inventory:

- Total GT: `442`
- `paired_optical_object_sar_gt`: `215`
- `blocked_missing_gm011_object_stream`: `195`
- `sar_only_gt`: `20`
- `no_oty_iou_match` / detection dropout / truncated temporal continuation pool: `12`
- `missing_review_optical_bbox`: `0`
- `other_unclassified_blocker`: `0`

Scene accounting:

- `GM_RM011`: `201` total = `195` missing OTY object stream + `6` SAR-only
- `GM_RM017`: `216` total = `199` paired + `11` SAR-only + `6` detection-dropout/no-match
- `GM_RM019`: `25` total = `16` paired + `3` SAR-only + `6` detection-dropout/no-match

The `215` paired rows are not the full GT inventory. They are only the current successful optical-object-to-SAR-GT posthoc correspondence subset.

## Current Most Trustworthy Conclusions

- Optical-to-SAR timing should use the known acquisition scale `24 fps -> 50 fps` with software-sync zero-offset assumption and jitter margin. It is not per-frame timestamp truth and not hardware synchronization.
- The 50/24 ratio must be used. Do not use `sar_frame = optical_frame * 2`.
- Target-level SAR temporal windows exist for current OTY object streams: 18 generated windows, with GM_RM011 blocked at object level because the optical object stream is missing.
- Runtime spatial priors are weak by design: 18 objects have azimuth context, but range remains `broad_unknown_range_prior` until runtime-safe per-object range geometry is available.
- Vehicle eligibility matters. Only a small subset are main research vehicles; many rows belong to weak, far-small, review-only, blocked, or no-object-flow layers.
- GT posthoc mechanism discovery suggests azimuth sectors usually cover GT but are broad; vehicle-size shells have posthoc compression potential; optical box shape has posthoc correlation with SAR radius, but these are not runtime rules.
- The 12 no-match samples are not simply garbage. They are mostly severe truncation/current-frame detection dropout cases with temporal continuation and SAR posthoc support.

## Conclusions Not Yet Allowed

Do not claim:

- final automatic annotation is possible from these audits
- SAR GT or SAR image evidence can be used in runtime prior construction
- temporal propagation boxes are final labels
- the 12 dropout samples are clean paired rows
- optical box morphology trends are validated runtime range rules
- stronger YOLO is already validated as an improvement
- identity truth between OTY object IDs and SAR GT is established by these posthoc audits

## GM_RM011 Status

GM_RM011 has SAR GT. It is not unannotated.

Current blocker:

- `195` rows have SAR GT and review optical linkage but no current OTY object stream.
- `6` rows are SAR-only.

Before rebuilding GM_RM011 object flow, GM_RM011 can be used for:

- GT inventory accounting
- SAR-only morphology/scattering statistics
- scene-level timing metadata discussion

It cannot yet be used for object-level optical-to-SAR correspondence.

GM_RM011 recovery path:

1. Build GM_RM011 through the same OTY0/OTY1/OTY1t object-stream chain as GM_RM017/GM_RM019.
2. Do not use SAR GT or SAR images to construct the optical object stream.
3. Re-run GT sample accounting.
4. Only then re-run GT correspondence mechanism discovery.

## SAR-Only Status

SAR-only rows: `20`.

They cannot be used for optical-object-to-SAR correspondence because they have no optical object counterpart. They should be preserved for:

- SAR-only GT size distribution
- SAR scattering / footprint morphology
- SAR-side background contrast checks

They must not be mixed into optical-to-SAR correspondence statistics.

## Detection Dropout Pool

The 12 no-match rows are now better described as the detection-dropout / truncated temporal continuation pool.

Current status:

- Temporal continuation supported: `12/12`
- Existence recovered by temporal continuation: `8/12`
- Secondary-supported truncated same vehicle: `8/12`
- SAR posthoc-supported dropout: `12/12`
- YOLO upgrade candidates: `12/12`
- Manual review required: `12/12`
- Excluded from clean optical-shape statistics: `12/12`

Use these rows to study:

- severe truncation
- current-frame detector dropout
- temporal continuation
- SAR posthoc target support
- detector recovery A/B

Do not merge them into clean paired rows or complete vehicle morphology statistics.

## YOLO A/B Target

The right YOLO A/B target is not higher detection count by itself.

Use a small sample A/B to test:

- whether current-frame severe truncation vehicles are recovered
- whether primary missing decreases
- whether secondary-only decreases
- whether review-box containment / overlap improves
- whether far-small noise increases
- whether track continuity improves
- whether handoff / duplicate decreases

Do not submit model weights. Do not treat a stronger YOLO as validated until this A/B shows better research eligibility and temporal continuity without adding unacceptable noise.

## New Session Handoff

Start from these current artifacts:

- `reports/oty2/oty2_gt_sample_accounting_summary_20260702_192810.json`
- `reports/oty2/oty2_gt_correspondence_mechanism_summary_20260702_190435.json`
- `reports/oty2/oty2_detection_dropout_temporal_sar_support_summary_20260702_200455.json`
- `reports/oty2/oty2_vehicle_research_eligibility_summary_20260702_180326.json`
- `reports/oty2/oty2_runtime_spatial_prior_summary_20260702_144929.json`
- `reports/oty2/oty2_object_sar_temporal_window_summary_20260702_135912.json`

Avoid redoing:

- the 442-sample accounting
- the 12 no-match triage
- the detection-dropout temporal/SAR support audit
- the basic 24:50 software-sync temporal contract
- the first runtime weak spatial prior audit

Next session should branch from the pushed head after this recap, not from an older pre-accounting commit.

## Uncommitted Worktree Note

At this handoff, there are pre-existing V0/config/visualization modified files in the worktree. They are unrelated to this OTY2 closeout and should not be mixed into the next OTY2 branch unless explicitly requested.

