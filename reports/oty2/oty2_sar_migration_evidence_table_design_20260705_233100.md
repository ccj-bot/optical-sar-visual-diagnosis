# OTY2 SAR Migration Evidence Table Design

Timestamp: `20260705_233100`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified starting HEAD: `dbf6804 Validate targeted optical evidence repairs`

## Boundary

This round converts repaired optical evidence into a SAR migration evidence table. It does not continue optical visual review, does not run SAR pairing/support, and does not generate final SAR annotations.

The table is an intermediate evidence surface for SAR-side review. It records what the optical side can safely say after targeted repair validation:

- weak optical support;
- possible optical continuity;
- manual review hints;
- split-first requirements;
- negative guards that block false upgrades.

It must not be consumed as final boxes, revised GT, identity truth, clean-pool membership, selector/ranking output, or automatic annotation.

## Inputs

- `reports/oty2/oty2_optical_evidence_targeted_repair_validation_20260705_231500.md`
- `reports/oty2/samples/oty2_optical_evidence_targeted_repair_validation_summary_20260705_231500.csv`
- `reports/oty2/oty2_blocked_case_repair_review_20260705_224500.md`
- `reports/oty2/oty2_optical_evidence_repair_plan_20260705_214500.md`
- `reports/oty2/oty2_optical_evidence_visual_judgement_20260705_205500.md`

No auxiliary script was needed. The sample table is a direct design-level mapping from the validated optical repair summary.

## Evidence Table Purpose

The table answers six operational questions for downstream SAR migration review:

1. which optical cases can be consumed at all;
2. what type of support each case provides;
3. how strong the support is;
4. what SAR-side action is allowed;
5. what SAR-side action is explicitly forbidden;
6. which negative or split-first rules must prevent automatic upgrade.

The table therefore separates candidate construction from final localization. Optical evidence can prioritize where SAR should look, but SAR-side image evidence must still decide precise localization.

## Field Contract

| Field | Meaning |
| --- | --- |
| `scene` | Optical scene identifier. |
| `evidence_id` | Stable row identifier for this evidence table. |
| `evidence_type` | One of `weak_track_evidence`, `continuity_candidate`, `review_hint`, `split_required`, `negative_guard`. |
| `source_case_id` | Source case from the repair validation summary. |
| `source_track_or_segment` | Optical tracklet or relation represented by this evidence row. |
| `optical_time_range` | Human-readable optical frame span used for the evidence. |
| `optical_frame_start`, `optical_frame_end` | Numeric frame bounds where known. |
| `optical_evidence_level` | Repaired optical level from the validation stage. |
| `repair_action_applied` | Minimal repair or guard action that made the row safe. |
| `visual_judgement` | Visual same-target status. |
| `box_quality_status` | Crop/box condition that limits use. |
| `appearance_status` | How appearance evidence should be interpreted. |
| `competition_status` | Whether competitors are excluded, present, unresolved, or blocking. |
| `sar_migration_use` | Specific SAR-side use category. |
| `sar_use_strength` | One of `medium`, `weak`, `review_only`, `blocked`, `negative_guard`. |
| `allowed_sar_action` | What the SAR migration flow may do with this row. |
| `forbidden_sar_action` | Explicit forbidden use. |
| `risk_tags` | Machine-readable risk and state tags. |
| `needs_manual_review` | Whether this row still needs manual or SAR-side confirmation before stronger use. |
| `negative_guard` | Guard rule, if the row blocks an automatic action. |
| `reason` | Short human explanation. |

## Evidence Classes

### Weak Track Evidence

Rows:

- `GM_RM017 bs_0010`
- `GM_RM011 bs_0044 seg_002 -> bs_0038 seg_002`
- `GM_RM011 bs_0002 seg_001 -> bs_0007 seg_001`

Allowed SAR action:

- `use_as_weak_support_only`
- `prioritize_sar_candidate_review`

Forbidden SAR action:

- do not generate final boxes;
- do not assign identity truth;
- do not auto-merge tracks;
- do not promote to clean paired evidence;
- do not use as a strong spatial constraint.

These rows carry weak existence, timing, or candidate-priority hints. They are useful because visual repair made the target relation plausible, but each row still has partial visibility, part-box change, edge contact, or appearance-model weakness.

### Continuity Candidate

Rows:

- `GM_RM011 bs_0015 seg_001 -> seg_002`
- `GM_RM011 bs_0061 seg_002 -> seg_003`
- `GM_RM011 bs_0061 seg_001 -> seg_002`

Allowed SAR action:

- `check_same_target_continuity`
- `prioritize_sar_candidate_review`

Forbidden SAR action:

- do not auto-merge optical track IDs;
- do not produce a final track;
- do not generate final SAR annotation;
- do not treat continuity as identity truth.

The first two rows are stable short-gap continuity candidates. The third is a weaker continuity row because it spans a longer gap and a visible part-state transition; it remains useful only as a temporal hint.

### Review Hint

Row:

- `GM_RM011 bs_0029 seg_001 -> seg_002`

Allowed SAR action:

- `manual_review_only`

Forbidden SAR action:

- do not use as an automatic constraint;
- do not turn a thin edge crop into a full-vehicle prior.

This row marks where SAR or human review should look, but the optical evidence is too thin for migration support.

### Split Required

Rows:

- `GM_RM017 bs_0008`
- `GM_RM017 bs_0012`

Allowed SAR action:

- `manual_review_only`

Forbidden SAR action:

- do not use the original whole track ID as a continuous target;
- do not aggregate the whole segment;
- do not use as migration evidence before split or identity audit.

These rows are not evidence to migrate. They are table entries that protect later processing from treating a mixed or edge-shifted optical track as a single target.

### Negative Guard

Rows:

- `GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001`
- `GM_RM011 bs_0056 seg_001 -> bs_0061 seg_001`

Allowed SAR action:

- `block_auto_merge`

Forbidden SAR action:

- do not auto-upgrade on appearance similarity;
- do not auto-upgrade on spatial proximity;
- do not use as same-target continuity;
- do not use as migration support.

These rows are guardrails. They are present to prevent false optical evidence from propagating into SAR-side candidate construction.

## Preventing Weak Evidence Misuse

Weak evidence rows are marked with `sar_use_strength=weak`, risk tags, and forbidden actions. A downstream consumer must treat them as soft review context only. They can raise the priority of a SAR candidate review, but they cannot shrink a SAR search region into a final box, decide identity, or override SAR-side structure evidence.

The important rule is: weak optical evidence can say "look here first" or "this time span is worth checking"; it cannot say "this is the final SAR vehicle."

## Preventing Continuity Candidate Misuse

Continuity candidates are not merges. They only record that two optical segments may form a continuous target hypothesis. The evidence table therefore stores both the allowed action `check_same_target_continuity` and forbidden actions such as `do_not_auto_merge_tracks` and `do_not_assign_identity_truth`.

SAR review may use the continuity candidate to compare SAR-side evidence over the relevant time span. It may not inherit the optical continuity candidate as final identity.

## Connection To SAR Candidate Review

The next bounded step is to join this evidence table to a SAR candidate-review queue, not to a SAR pairing/support output. The SAR review queue should:

1. read `weak_track_evidence` and `continuity_candidate` rows as priority hints;
2. surface `review_hint` rows for manual inspection only;
3. exclude `split_required` rows from automatic migration until split review is complete;
4. apply `negative_guard` rows as block rules against appearance-only or spatial-only candidate promotion;
5. record SAR-side findings in a separate review artifact.

## Missing Before True SAR Pairing/Support

True SAR pairing/support still requires:

- SAR-side image evidence for the candidate time span;
- explicit SAR candidate regions or review queue entries;
- a rule for consuming negative guards before any automatic promotion;
- manual or SAR-side confirmation for review-only and split-required rows;
- a separate boundary check proving that no final boxes, revised GT, clean-pool promotion, selector/ranking, or training logic is being generated.

The current table is therefore ready for small-scale review, not for final SAR support generation.

## Required Answers

1. This is not final SAR annotation because the optical side only provides a graded prior; SAR still performs precise localization.
2. Repair validation results become SAR-side evidence by mapping each case to an evidence type, use strength, allowed action, forbidden action, and risk tags.
3. Weak migration evidence rows are `GM_RM017 bs_0010`, `GM_RM011 bs_0044 -> bs_0038`, and `GM_RM011 bs_0002 -> bs_0007`.
4. Continuity candidates are `GM_RM011 bs_0015 seg_001 -> seg_002`, `GM_RM011 bs_0061 seg_002 -> seg_003`, and weak candidate `GM_RM011 bs_0061 seg_001 -> seg_002`.
5. `GM_RM011 bs_0029` is review hint only.
6. `GM_RM017 bs_0008` and `GM_RM017 bs_0012` need split-first handling.
7. `GM_RM011 bs_0061 -> bs_0064` and `GM_RM011 bs_0056 -> bs_0061` are negative guards.
8. Allowed SAR actions are candidate prioritization, same-target continuity checking, weak support only, manual review only, and blocking auto-merge.
9. Forbidden SAR actions are final box generation, identity truth assignment, auto track merge, clean-pool promotion, strong-constraint use, selector/ranking output, and SAR support generation.
10. Weak evidence is protected by `sar_use_strength=weak`, risk tags, and forbidden actions.
11. Continuity candidates are protected by `allowed_sar_action=check_same_target_continuity` plus `forbidden_sar_action=do_not_auto_merge_tracks`.
12. The next step is to connect the table to a small SAR candidate-review queue.
13. True SAR pairing/support still needs SAR-side candidate evidence, guard-aware consumption, and separate review outputs.
14. The current stage does not allow final boxes, revised GT, clean `215` promotion, SAR pairing/support, selector/ranking, or automatic annotation.

## Conclusion

```text
SAR_MIGRATION_EVIDENCE_TABLE_READY_FOR_SMALL_SCALE_REVIEW
```

Interpretation: the evidence table now contains weak evidence, continuity candidates, review hints, split requirements, and negative guards. It is ready to drive a small SAR candidate-review queue, but not final SAR annotation or automatic pairing/support.
