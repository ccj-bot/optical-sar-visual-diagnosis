# OTY2 Optical Evidence Targeted Repair Validation

Timestamp: `20260705_231500`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified starting HEAD: `656b198 Review blocked optical cases for repairability`

## Boundary

This round validates targeted optical evidence repairs. It is not another broad failure report and it is not a track-stitching or annotation-generation step.

Allowed output is limited to diagnostic evidence levels for SAR migration review:

- `weak_migration_evidence`
- `continuity_candidate`
- `review_hint_only`
- `blocked_negative_guard`
- `needs_split_before_use`
- `not_usable`

This report does not merge tracker IDs, assign identity truth, generate final tracks, create final or revised annotation, create final boxes, run SAR pairing/support, create selector/ranking output, tune thresholds, train models, or promote `GM_RM011` into the clean paired pool.

## Inputs Reused

- `reports/oty2/oty2_blocked_case_repair_review_20260705_224500.md`
- `reports/oty2/samples/oty2_blocked_case_repair_review_summary_20260705_224500.csv`
- `reports/oty2/oty2_optical_evidence_repair_plan_20260705_214500.md`
- `reports/oty2/samples/oty2_optical_evidence_repair_plan_summary_20260705_214500.csv`
- `reports/oty2/oty2_optical_evidence_visual_judgement_20260705_205500.md`
- ignored visual panels under `outputs/oty2/optical_blocked_case_repair_review_20260705_224500/`

No new panels were required. The existing panels already show full-frame context, red focus boxes, blue competing tracker boxes, and focus crops for the cases that need before/after repair validation.

## Why This Is Repair Validation

The previous rounds established which optical evidence was weak, blocked, or review-only. This round starts from the subset already judged repairable or partially repairable and asks whether a minimal diagnostic repair changes the usable evidence level.

The validation criterion is not "can we merge the track." The validation criterion is:

1. whether a weak or blocked optical relation can safely become graded SAR migration evidence;
2. whether the repair action is local and explainable;
3. whether the same rule would incorrectly upgrade known negative controls.

## Minimal Repair Actions Used

| Repair action | Meaning in this validation | Output consequence |
| --- | --- | --- |
| fit-frame selection | use frames where the focus box actually covers the intended visible vehicle region | representative optical evidence only, not a new annotation |
| bad-frame exclusion | ignore tiny, edge-only, or background-polluted frames when judging representative appearance | weak evidence may recover, but full segment remains review context |
| appearance downweighting | treat ResNet18 appearance as auxiliary when human visual continuity is clear but crop quality is poor | prevents model weakness from becoming automatic rejection |
| state tagging | add diagnostic states such as `edge_contact`, `partial_visible`, `box_partial`, `part_state_transition`, `competition_unresolved`, `needs_split`, `continuity_candidate` | controls how SAR migration may use the evidence |
| continuity evidence edge | record that two short optical segments may be continuous | candidate edge only; no track ID merge |
| negative guard | preserve blocked cases as rules against false upgrades | prevents appearance-only or spatial-only merging |

## Sample-Level Repair Validation

| Case | Pre-repair status | Minimal repair action | Post-repair level | SAR migration use | Remaining risk |
| --- | --- | --- | --- | --- | --- |
| `GM_RM017 bs_0010` | unstable / weak; partial edge crop; ResNet18-sensitive | select frames `196-199` as fit evidence, downweight appearance, tag `edge_contact`, `partial_visible`, `model_weak_visual_confirmed`; keep frame `200` as too-thin edge context rather than full-body evidence | `weak_migration_evidence` | weak existence and edge-contact timing hint for SAR review; no hard spatial constraint | only a partial optical vehicle front is visible; cannot become strong identity evidence |
| `GM_RM011 bs_0015 seg_001 -> seg_002` | visually plausible short-gap continuity, but partial front/side crop | create diagnostic continuity edge, use endpoint fit frames `13-16` and `18-22`, tag `partial_front_side` | `continuity_candidate` | prioritize SAR-side inspection over the same time span; preserve same-target hypothesis | still a partial front/window observation, not a whole-vehicle constraint |
| `GM_RM011 bs_0061 seg_002 -> seg_003` | visually plausible short-gap continuity with edge-neighbor competitor | create diagnostic continuity edge, use fit frames `279-281` and `283-287`, keep `edge_neighbor_present` / competitor-exclusion note | `continuity_candidate` | prioritize SAR review for the central white-car continuity hypothesis | left-edge vehicle remains a competitor if the tag is ignored |
| `GM_RM011 bs_0061 seg_001 -> seg_002` | weak continuity candidate; longer gap and rear/side to front/windshield part transition | add `part_state_transition` edge and keep as weak unless intermediate motion bridge is inspected | `continuity_candidate` | temporal continuity hint only; no hard spatial constraint | part-state change could hide an unobserved switch |
| `GM_RM011 bs_0044 seg_002 -> bs_0038 seg_002` | weak evidence; same white vehicle plausible but box covers different parts | state-tag before crop as upper side/window and after crop as front/hood; use state-compatible comparison | `weak_migration_evidence` | candidate priority and weak time-continuity hint | different vehicle parts must not be treated as whole-car identity evidence |
| `GM_RM011 bs_0002 seg_001 -> bs_0007 seg_001` | weak evidence; same white SUV plausible but rear/body changes to upper-window strip | use representative fit frames, tag `vehicle_part_box_change`, require expanded-context review before stronger use | `weak_migration_evidence` | rough continuity and candidate priority | window strip could be overtrusted as a full-vehicle cue |
| `GM_RM011 bs_0029 seg_001 -> seg_002` | weak edge continuity; later crop becomes a very thin edge strip | use only frames with enough visible vehicle area, tag `edge_truncated`, keep thin tail frames out of representative evidence | `review_hint_only` | rough existence or timing hint near frame edge | tiny edge strip cannot constrain SAR as a full vehicle |
| `GM_RM017 bs_0008` | blocked/manual review; same track spans different target regions and competitors | do not repair by bad-frame removal; require visible-state split first | `needs_split_before_use` | manual review prompt only | whole-segment use can attach the wrong dark vehicle |
| `GM_RM017 bs_0012` | blocked/manual review; mixed left/right edge partial views and identity ambiguity | split before embedding repair; manual identity audit first | `needs_split_before_use` | manual review prompt only | bad-frame exclusion could hide an internal target switch |
| `GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001` | blocked competition; high appearance points to left-edge vehicle while central white car remains separate | preserve as negative comparator; require same target region and competitor rejection before any upgrade | `not_usable` | reject appearance-only false bridge | wrong target would propagate into SAR migration |
| `GM_RM011 bs_0056 seg_001 -> bs_0061 seg_001` | blocked/manual review; side/window strip to left-edge rear fragment | do not merge; preserve as part-switch and competition negative guard | `blocked_negative_guard` | manual review only; no automatic SAR constraint | spatial closeness can create false bridge across different parts or vehicles |

## Positive Upgrade Result

The positive repair validations pass at a bounded evidence level:

- `GM_RM017 bs_0010` upgrades from `unstable_weak` to `weak_migration_evidence`.
- `GM_RM011 bs_0015 seg_001 -> seg_002` remains a candidate relation, but its use is clarified as a `continuity_candidate` suitable for SAR-side priority review.
- `GM_RM011 bs_0061 seg_002 -> seg_003` remains a candidate relation, but with explicit competitor-state handling, so it can enter a SAR evidence table as a `continuity_candidate`.

These upgrades are not strong SAR migration constraints. They only say the optical evidence is now organized enough to guide SAR review without claiming final identity.

## Weak Repair Result

Four weak cases were validated as partial or review-only:

- `GM_RM011 bs_0061 seg_001 -> seg_002`: partial upgrade to `continuity_candidate`, but weak because of longer gap and part-state transition.
- `GM_RM011 bs_0044 seg_002 -> bs_0038 seg_002`: partial upgrade to `weak_migration_evidence`, with part-state tags.
- `GM_RM011 bs_0002 seg_001 -> bs_0007 seg_001`: partial upgrade to `weak_migration_evidence`, with `vehicle_part_box_change`.
- `GM_RM011 bs_0029 seg_001 -> seg_002`: remains `review_hint_only` because the later edge strip is too thin.

These cases cannot be used as strong constraints. Their SAR role is candidate priority, rough timing, and manual review focus.

## Negative Guard Result

The negative guard cases do not upgrade:

- `GM_RM017 bs_0008`: requires split before use.
- `GM_RM017 bs_0012`: requires split before use.
- `GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001`: not usable as migration evidence.
- `GM_RM011 bs_0056 seg_001 -> bs_0061 seg_001`: blocked negative guard.

The guard rules are:

1. If a same-frame competitor can explain the successor region, do not upgrade the relation.
2. If the focus crop switches vehicle part in a way that cannot be visually explained, do not merge by appearance or proximity.
3. If one track ID spans different edge states or likely different targets, split or manually review before migration use.
4. If only a local crop is similar but full-frame continuity does not support the relation, do not upgrade.

These rules prevent false optical continuity from becoming a SAR-side prior around the wrong vehicle.

## Split-First Cases

`GM_RM017 bs_0008` and `GM_RM017 bs_0012` need split-first handling. They should not be repaired by dropping a few bad frames and aggregating the rest, because the full-frame panels show unresolved competing vehicles and strong edge-state changes. Their current safe use is manual review or visible-state subsegment construction, not migration evidence.

## Model-Weak But Human-Confirmed Case

`GM_RM017 bs_0010` is the clearest `model_weak_visual_confirmed` case. The visual target is a right-edge white vehicle front that remains coherent in the reviewed frames, while the crop becomes partial and thin enough to weaken ResNet18 appearance. The repair is to downweight appearance, use fit frames, and tag edge/partial visibility. The result is weak migration evidence only.

## Why This Is Not Final Track Merge

The repaired evidence still contains partial crops, edge visibility, part-state transitions, and competitor tags. A continuity candidate records that SAR should inspect a time span or target hypothesis with priority; it does not assert that two optical tracklets are the same identity. Therefore this round cannot generate final track merges.

## Why This Is Not Final SAR Annotation

Optical evidence is only a prior for SAR migration. SAR still has to localize the vehicle using SAR-side evidence inside the optical prior context. This report creates no final boxes, no revised GT, no SAR support artifact, and no final annotation.

## How To Connect To A SAR Migration Evidence Table

The next safe integration is a small table, not an automatic merger. Each accepted row should carry:

- `scene`
- `case_id`
- `evidence_level`
- `repair_action`
- `state_tags`
- `sar_migration_use`
- `negative_guard`
- `requires_manual_review`
- `forbidden_use`

`continuity_candidate` rows should prioritize SAR-side inspection across the candidate time span. `weak_migration_evidence` rows should provide weak existence, rough timing, or edge/partial visibility hints. `review_hint_only`, `needs_split_before_use`, `blocked_negative_guard`, and `not_usable` rows should never constrain SAR automatically.

## Required Answers

1. This round is repair validation because it checks whether known weak or repairable evidence changes usable level after local diagnostic handling.
2. Upgradable samples are `GM_RM017 bs_0010`, `GM_RM011 bs_0015 seg_001 -> seg_002`, `GM_RM011 bs_0061 seg_002 -> seg_003`, plus partial weak upgrades for `bs_0061 seg_001 -> seg_002`, `bs_0044 -> bs_0038`, and `bs_0002 -> bs_0007`.
3. `bs_0010` moves from unstable/weak to weak migration evidence; the two short GM_RM011 gaps move into explicit continuity-candidate use; the partial weak cases become weak or candidate hints only.
4. Repair actions are fit-frame selection, bad-frame exclusion, appearance downweighting, state tags, continuity evidence edges, and negative guards.
5. Repaired evidence serves SAR migration by prioritizing time spans and candidate regions for SAR-side checking, not by writing final boxes.
6. Weak-only samples are `bs_0061 seg_001 -> seg_002`, `bs_0044 -> bs_0038`, `bs_0002 -> bs_0007`, and `bs_0029`.
7. Samples that must continue blocking upgrade are `bs_0008`, `bs_0012`, `bs_0061 -> bs_0064`, and `bs_0056 -> bs_0061`.
8. Negative rules require competitor rejection, target-region consistency, split-first handling for suspected same-track switches, and full-frame support beyond crop similarity.
9. These rules prevent false merges by blocking appearance-only, spatial-only, and part-switch-only relations.
10. `GM_RM017 bs_0008` and `GM_RM017 bs_0012` need split-first handling.
11. Yes. `GM_RM017 bs_0010` is model weak but visually confirmable.
12. Treat that case as `model_weak_visual_confirmed`: downweight appearance, select fit frames, tag edge/partial state, and use only weak SAR migration support.
13. Final track merging is not allowed from the current evidence.
14. Final SAR annotation is not allowed from the current evidence.
15. The next step is to insert the graded rows into a SAR migration evidence table with evidence level, state tags, negative guards, and forbidden-use fields.

## Conclusion

```text
TARGETED_REPAIR_VALIDATION_READY_FOR_SAR_EVIDENCE_TABLE
```

Interpretation: several positive repairs can safely enter a SAR migration evidence table as weak evidence or continuity candidates, and the negative guards are clear enough to prevent the same logic from upgrading known false bridges.
