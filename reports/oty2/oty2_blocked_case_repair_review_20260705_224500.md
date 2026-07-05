# OTY2 Blocked Case Repair Review

Timestamp: `20260705_224500`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified HEAD before this review: `6f53a37 Plan repairable optical evidence for SAR migration`

## Boundary

This review inspects previously blocked or manual-review optical evidence with full-frame panels, focus boxes, competing tracker boxes, and focus crops. It does not merge tracklets, assign identity truth, create final annotations, create revised GT, create final boxes, run SAR pairing/support, create selector/ranking output, tune thresholds, train models, or promote `GM_RM011` into the clean `215` pool.

Temporary panels were generated under ignored `outputs/` only:

- `outputs/oty2/optical_blocked_case_repair_review_20260705_224500/`
- contact sheet: `outputs/oty2/optical_blocked_case_repair_review_20260705_224500/blocked_case_repair_review_contact_sheet.jpg`
- panel metadata: `outputs/oty2/optical_blocked_case_repair_review_20260705_224500/blocked_case_repair_review_panels.csv`

Committed files for this round:

- `reports/oty2/oty2_blocked_case_repair_review_20260705_224500.md`
- `reports/oty2/samples/oty2_blocked_case_repair_review_summary_20260705_224500.csv`
- `tools/diagnostics/run_oty2_blocked_case_repair_review_pack.py`

## Principle

A crop is not a pure vehicle-body representation. It is all pixels inside the detector or tracker box. If a box contains a vehicle part, background, road edge, bridge, another vehicle, or only a frame-edge fragment, the ResNet18 appearance feature can be weak or misleading.

Therefore this review separates:

- visual continuity in full frames;
- whether the focus box actually follows that visual target;
- whether competing boxes offer a better explanation;
- whether the sample is repairable by box/frame/state handling or must stay blocked.

## Panels Reviewed

| Case | Frames shown | Role |
| --- | --- | --- |
| `GM017_bs0008_blocked` | `145-149`, `181-185` | blocked unstable segment |
| `GM017_bs0012_blocked` | `162-166`, `210-214` | blocked unstable segment |
| `GM017_bs0010_repairable_control` | `196-200` | repairable control |
| `GM011_bs0061_to_bs0064_blocked` | `266-270`, `283-287` | blocked competition relation |
| `GM011_bs0056_to_bs0061_blocked` | `257-261`, `262-266` | blocked part/competition relation |
| `GM011_bs0015_positive_control` | `13-16`, `18-22` | repairable continuity control |
| `GM011_bs0061_positive_control` | `279-281`, `283-287` | repairable continuity control |

The new panels draw the focus segment in red and same-frame competing tracker boxes in blue.

## Sample-Level Findings

| Case | Visual same vehicle? | Basis | Method failure layer | Repair category | Minimal repair action | Post-repair use |
| --- | --- | --- | --- | --- | --- | --- |
| `GM_RM017 bs_0008` | uncertain / no direct upgrade | Early frames track a left-side dark car while a box also follows the center truck; tail frames put the red focus on a right-edge dark fragment while blue boxes cover a center dark car and white car. | same track id spans visually different target regions; edge crop and competing vehicles. | `needs_track_split` | Split before any use; keep only subsegments with stable visible target region; route cross-edge relation to manual review. | `review_hint_only` |
| `GM_RM017 bs_0012` | no direct upgrade | Start frames include left-edge white fragment, center dark car, and truck; tail frames are right-edge dark fragments with no clean bridge from the early white fragment. | same track id appears to cross vehicle side/color/edge state; whole-segment embedding is unsafe. | `needs_track_split` | Split into visible-state subsegments; do not repair by simple bad-frame removal; manual identity audit first. | `review_hint_only` |
| `GM_RM017 bs_0010` | yes, weakly | The right-edge white vehicle front remains in a consistent image region; the middle dark vehicle is a blue competitor and can be excluded for the focus crop. | partial crop and model sensitivity, not core identity conflict. | `model_weak_visual_confirmed` | Downweight ResNet18; use fit frames only; tag as `edge_contact` and `partial_visible`; optional expanded diagnostic crop. | `weak_migration_evidence` |
| `GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001` | no | Before segment is the central/right white car rear-side region; after segment red box is the left-edge rear vehicle while blue box still covers the central white car. | appearance-only relation chose a competing vehicle. | `competition_unresolved` | Preserve as negative comparator; require same target region and competitor rejection before any upgrade. | `not_usable` |
| `GM_RM011 bs_0056 seg_001 -> bs_0061 seg_001` | no direct upgrade | Before segment is a long strip over the central white car side/window; after segment red box is a left-edge rear fragment while the central white car is blue. | part-box switch plus competing target. | `competition_unresolved` | Do not merge; use as negative comparator; if revisited, split part boxes and require target-region consistency. | `review_hint_only` |
| `GM_RM011 bs_0015 seg_001 -> seg_002` | yes | The same white vehicle front/windshield remains spatially and temporally continuous across a short gap. No stronger competing successor is visible. | tracker short gap and partial-front crop. | `gap_continuity_repairable` | Candidate edge only; use endpoint fit frames; tag `partial_front_side`; do not create final merge. | `continuity_candidate` |
| `GM_RM011 bs_0061 seg_002 -> seg_003` | yes | The focus remains the central white vehicle front/windshield across the gap; left-edge vehicle is visible but blue and not the focus target. | tracker short gap with edge-neighbor competitor. | `gap_continuity_repairable` | Candidate edge only; keep competitor tag; use fit frames; no identity truth. | `continuity_candidate` |

## Direct Answers

### 1. Can a box that contains only part of a car still support same-vehicle continuity?

Yes, but only as degraded evidence. `GM_RM011 bs_0015 seg_001 -> seg_002`, `GM_RM011 bs_0061 seg_002 -> seg_003`, and `GM_RM017 bs_0010` show that partial front/window crops can still follow a visually continuous vehicle in full-frame context.

They should not become strong appearance evidence. The repair action is to downweight appearance, use fit frames, add part/edge state tags, and keep the relation as a continuity candidate or weak migration hint.

### 2. If position changes little, why are some cases still blocked?

Because the red focus box may switch target region even when the image-space displacement is small. In `GM_RM011 bs_0056 -> bs_0061`, the before crop is a side/window strip of the central car, but the after red crop is the left-edge rear fragment; the central car is still present as a blue competitor. Spatial proximity alone is not enough.

In `GM_RM011 bs_0061 -> bs_0064`, high appearance and plausible timing point to the wrong left-edge vehicle. The block is identity/competition, not lack of image continuity.

### 3. What ensures same car under competition?

The positive controls show the required conditions:

- the focus box remains on the same visible vehicle region;
- motion is locally continuous;
- competing boxes are either absent or clearly separate;
- no blue competitor provides a more direct explanation of the successor target.

The blocked cases fail that test because the blue competitor often remains the central white car while the red successor moves to a left-edge vehicle.

### 4. What if the model is weak but human visual judgement confirms continuity?

Use `model_weak_visual_confirmed`, not automatic rejection. `GM_RM017 bs_0010` is the clearest case: the partial white-vehicle edge crop is visually coherent, but the crop is too partial for strong ResNet18 evidence. The correct repair is appearance downweighting, fit-frame selection, and weak SAR migration use.

## Repairability By Group

### Actually Repairable

- `GM_RM017 bs_0010`: weak migration evidence after fit-frame selection and edge/partial tags.
- `GM_RM011 bs_0015 seg_001 -> seg_002`: continuity candidate.
- `GM_RM011 bs_0061 seg_002 -> seg_003`: continuity candidate with competitor tag.

### Needs Split Before Migration

- `GM_RM017 bs_0008`: split visible states before use; current whole segment is unsafe.
- `GM_RM017 bs_0012`: split before any embedding repair; whole segment can hide a target/edge-state switch.

### Competition Or Identity Conflict Still Unresolved

- `GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001`: not usable; preserve as appearance-only negative comparator.
- `GM_RM011 bs_0056 seg_001 -> bs_0061 seg_001`: not a safe continuity repair; preserve as spatial/part-switch negative comparator or review hint.

### Truly Not Repairable With Current Evidence

No case is "forever impossible", but the two GM_RM011 blocked relations are not repairable as continuity edges with current evidence. They are useful only as negative comparators unless a future manual review or SAR-side check adds new evidence.

## SAR Migration Use

| Use level | Cases | SAR-side role |
| --- | --- | --- |
| `continuity_candidate` | `GM_RM011 bs_0015 -> bs_0015`, `GM_RM011 bs_0061 seg_002 -> seg_003` | prioritize SAR review over matching time span; maintain same-target continuity hypothesis |
| `weak_migration_evidence` | `GM_RM017 bs_0010` | weak existence and edge-contact timing hint; no hard spatial constraint |
| `review_hint_only` | `GM_RM017 bs_0008`, `GM_RM017 bs_0012`, `GM_RM011 bs_0056 -> bs_0061` | manual review prompt; no automatic SAR constraint |
| `not_usable` | `GM_RM011 bs_0061 -> bs_0064` | negative comparator for appearance-only false bridge |

## Next Step

The next bounded validation should not run a full automatic repair. It should:

1. Split GM_RM017 `bs_0008` and `bs_0012` into visible-state subsegments for review.
2. Build repaired representative crops for `bs_0010`, `bs_0015`, and `bs_0061 seg_002 -> seg_003`.
3. Compare those repaired representatives against the two GM_RM011 negative comparators.
4. Keep all outputs as diagnostic review material; no final merge, annotation, selector, or SAR support artifact.

## Conclusion

```text
BLOCKED_CASES_MAINLY_COMPETITION_OR_IDENTITY_CONFLICT
```

Interpretation: some control cases are repairable through visual continuity and box/state handling, but the previously blocked cases themselves are mostly blocked by target competition, identity uncertainty, or a need to split the track before migration use.
