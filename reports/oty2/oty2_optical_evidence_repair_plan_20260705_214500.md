# OTY2 Optical Evidence Repair Plan For SAR Migration

Timestamp: `20260705_214500`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified HEAD before this plan: `4a0ca37 Add OTY2 optical evidence visual judgement`

## 1. Position

This round is not another risk report and not direct track stitching. It starts from evidence that was previously classified as weak, unstable, blocked, or not directly usable, then asks a narrower question:

If visual judgement suggests a case is physically plausible, which method layer failed to express it, and what is the smallest repair that could turn it into useful SAR migration evidence?

The output is a repair plan for targeted validation. It does not merge track ids, assign identity truth, create final annotations, create revised GT, create final boxes, run SAR pairing/support, create selector/ranking output, tune thresholds, train models, or promote `GM_RM011` into the clean `215` pool.

## Inputs

- `reports/oty2/oty2_optical_evidence_visual_judgement_20260705_205500.md`
- `reports/oty2/samples/oty2_optical_evidence_visual_judgement_summary_20260705_205500.csv`
- `tools/diagnostics/run_oty2_optical_evidence_visual_judgement_pack.py`
- `reports/oty2/oty2_tracklet_embedding_aggregation_probe_20260705_193000.md`
- `reports/oty2/samples/oty2_tracklet_embedding_aggregation_probe_summary_20260705_193000.csv`
- existing temporary panels under `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/`

No new temporary panels were required for this plan.

## 2. Method Failure Types

The reviewed samples expose seven repairable or partially repairable failure types:

| Failure type | Meaning | Minimal compensation |
| --- | --- | --- |
| `edge_truncation` | Vehicle appears at image boundary; crop sees only a side, front, rear, or thin strip. | State tag as `edge_contact` / `partial_visible`; use only fit frames or expanded diagnostic crop. |
| `part_box_change` | Different segments crop different parts of the same vehicle. | Do not compare raw appearance directly; compare state-tagged part views and keep relation weak. |
| `bad_frame_pollution` | A few tail or edge frames dominate the minimum cosine and make a segment look unstable. | Remove bad frames from representative embedding; keep full segment as review context. |
| `background_pollution` | Crop contains large vegetation, road edge, bridge, or frame-edge background. | Prefer tighter fit frames or expanded crop with explicit context; do not promote to strong evidence. |
| `appearance_model_mismatch` | ResNet18 score is weak even when human visual continuity is plausible. | Treat ResNet18 as auxiliary; require visual/state/motion support before repair. |
| `short_gap_unbridged` | Tracker splits a visually continuous target across a small gap. | Create continuity candidate, not final merge. |
| `competition_unexcluded` | Another vehicle can explain the target region or successor segment. | Use as blocked case or negative comparator until competition is excluded. |

These failures are mostly at the box/crop/state layers, not at crop extraction. The crops exist; many are not reliable whole-vehicle appearance observations.

## 3. Sample-Level Repair Analysis

| Item | Current status | Visual judgement | Failure cause | Repairability | Minimal repair action | Post-repair expected level | SAR migration use | Risk and negative comparison |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GM_RM017 bs_0008 seg_001` | unstable / blocked | Not safely confirmable as one target; later frames are thin right-edge dark-vehicle crops with competing dark vehicles in context. | edge truncation plus competition; bad tail frames dominate appearance instability. | uncertain to no | Split into visible-state subsegments before any use; keep only well-fit frames as existence hints; require manual identity review. | review only | manual review prompt or existence hint only | If repaired by appearance alone it can attach the wrong dark vehicle. Unlike `bs_0010`, the competing dark vehicle context is not cleanly excludable. |
| `GM_RM017 bs_0010 seg_001` | unstable / weak | Likely same white vehicle edge fragment, but only partial front/edge views are available. | edge-contact partial crop; ResNet18 penalizes partial view and crop width changes. | partial | Drop tiny/edge-only frames from representative embedding; use fit-frame selection; optionally create expanded diagnostic crop with context. | weak migration evidence | existence and rough edge-contact timing hint; not a hard spatial constraint | Misuse would over-constrain SAR to a partial optical front instead of a vehicle body. More repairable than `bs_0008` because the white-vehicle interpretation is visually more coherent. |
| `GM_RM017 bs_0012 seg_001` | unstable / blocked | Mixed left/right edge partial views; identity continuity is not closed. | edge truncation plus possible identity ambiguity; extreme crop-state shift. | no for migration, uncertain for review | Split before any embedding repair; route to manual identity audit; do not aggregate whole segment. | review only | manual review prompt only | Bad-frame removal alone may hide an internal identity switch. This is not a safe candidate for weak migration until split points are established. |
| `GM_RM011 bs_0015 seg_001 -> seg_002` | continuity candidate | Same white vehicle front/windshield region is visually continuous across a 2-frame gap. | tracker short gap; boxes are partial front/side crops, so migration grade was downgraded. | yes | Bridge as candidate edge only; use endpoint fit frames as representative appearance; add `partial_front_side` state tag. | continuity candidate, weak migration evidence | time continuity hint and candidate priority for SAR-side checking | If used as strong constraint, it may localize to only the optical front/windshield. It is stronger than cross-track candidates because no better nearby successor is visible. |
| `GM_RM011 bs_0061 seg_002 -> seg_003` | continuity candidate | Same white vehicle front/windshield continues over a 2-frame gap. | tracker short gap; partial front crop; neighboring left-edge vehicle must remain a competitor tag. | yes | Bridge as candidate edge only; use fit frames and competitor exclusion note; keep `edge_neighbor_present` tag. | continuity candidate, weak migration evidence | time continuity hint and candidate priority | The left-edge vehicle is a risk but does not explain the central white-car crop. Stronger than `bs_0061 -> bs_0064`, which points to the left-edge vehicle. |
| `GM_RM011 bs_0029 seg_001 -> seg_002` | weak continuity candidate | Same right-edge white vehicle is plausible, but later crop becomes a very thin edge strip. | severe edge truncation and narrow crop. | partial | Use only frames with enough visible vehicle area; mark as edge-truncated; do not aggregate thin tail frames as full appearance. | review only to weak migration evidence | rough existence/timing hint near edge | Misuse would convert a tiny edge strip into a full vehicle cue. Less repairable than `bs_0015` because visible area collapses after the gap. |
| `GM_RM011 bs_0061 seg_001 -> seg_002` | weak continuity candidate | Same white vehicle is plausible, but relation spans a 9-frame gap and changes from rear/side to front/windshield. | part-state transition plus longer gap. | partial | Add `part_state_transition` edge; validate with intermediate frames if available; keep weak unless motion bridge can be shown. | continuity candidate | temporal continuity hint; not spatial hard constraint | If treated as direct merge, it may bridge across an unobserved part transition. It is weaker than `bs_0061 seg_002 -> seg_003` due to longer gap and part change. |
| `GM_RM011 bs_0044 seg_002 -> bs_0038 seg_002` | weak evidence | Same white vehicle is plausible under part-box transition, but before/after boxes cover different vehicle parts. | part-box change; appearance comparison is unfair. | partial | State-tag before crop as upper side/window and after crop as front/hood; use state-compatible comparison rather than raw cosine. | weak migration evidence | candidate priority and time continuity hint | Misuse would treat different vehicle parts as whole-car identity evidence. More repairable than competition cases because target vehicle remains visually coherent. |
| `GM_RM011 bs_0002 seg_001 -> bs_0007 seg_001` | weak evidence | Same white SUV is plausible, but box changes from rear/body to upper-window strip. | part-box change and crop representative mismatch. | partial | Use representative fit frames; add `vehicle_part_box_change`; validate with expanded context crop. | weak migration evidence | rough continuity and candidate priority | Misuse can overtrust a window-strip crop. It should remain weaker than `bs_0015` and `bs_0061 seg_002 -> seg_003`. |
| `GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001` | blocked conflict | High appearance candidate points to the left-edge competing vehicle, not the central white vehicle. | appearance-only cross-track candidate lacks competition rejection. | no as merge; yes as negative rule | Preserve as negative comparator for competition exclusion; require same target region, not just high appearance. | not usable as migration evidence | reject appearance-only candidate; protect SAR from wrong target propagation | This is the clearest example that visual repair must include competing-target exclusion. |
| `GM_RM011 bs_0056 seg_001 -> bs_0061 seg_001` | blocked/manual review | Relation switches from side-window strip to left-edge rear fragment/competing area. | part-box switch plus competition; spatial closeness is not enough. | no to uncertain | Do not merge; use as negative comparator; if revisited, first split/label visible parts and competitors. | review only or not usable | manual review prompt only | If repaired automatically, it can create a false bridge across different vehicle parts or neighboring vehicles. |

## 4. GM_RM017 Repair Conclusion

GM_RM017 is not cleanly reliable, but it is not uniformly useless.

Repairable:

- `bs_0010` can likely recover to weak migration evidence if the repair uses fit-frame selection, bad-frame exclusion, and explicit `edge_contact` / `partial_visible` state tags.

Not directly repairable:

- `bs_0008` needs identity review before any migration use because dark-vehicle edge fragments and competing vehicles cannot be cleanly separated.
- `bs_0012` should be split or manually audited before use. Whole-segment re-aggregation would be unsafe because the visible state and edge side change too strongly.

The main GM_RM017 correction is therefore not "use a better appearance threshold." It is box/state-aware representative selection, plus a stop rule for unresolved competing targets.

## 5. GM_RM011 Repair Conclusion

Visually continuous but under-expressed by current method:

- `bs_0015 seg_001 -> seg_002`
- `bs_0061 seg_002 -> seg_003`

These should enter a small targeted validation as continuity repair candidates. They still should not become final merges or strong SAR constraints.

Partially repairable weak candidates:

- `bs_0061 seg_001 -> seg_002`
- `bs_0044 seg_002 -> bs_0038 seg_002`
- `bs_0002 seg_001 -> bs_0007 seg_001`
- `bs_0029 seg_001 -> seg_002`

These need state-tagged part comparison, fit-frame representative selection, and edge/partial visibility tags.

Blocked or negative comparators:

- `bs_0061 seg_001 -> bs_0064 seg_001`
- `bs_0056 seg_001 -> bs_0061 seg_001`

These are useful because they show what the repair logic must not do: high appearance or nearby endpoint alone cannot override competing-target evidence.

## 6. SAR Migration Use After Repair

The repaired optical evidence should enter SAR migration as graded support:

| Evidence level | Eligible samples | SAR-side use |
| --- | --- | --- |
| continuity candidate | `bs_0015 seg_001 -> seg_002`, `bs_0061 seg_002 -> seg_003`, possibly `bs_0061 seg_001 -> seg_002` after validation | prioritize SAR-side checking over the corresponding time span; preserve same-target continuity hypothesis |
| weak migration evidence | `bs_0010`, `bs_0044 -> bs_0038`, `bs_0002 -> bs_0007`, selected `bs_0029` frames | existence, rough timing, weak candidate priority, edge/partial visibility hint |
| review only | `bs_0008`, `bs_0012`, `bs_0056 -> bs_0061` | manual review prompt; do not constrain SAR automatically |
| negative comparator | `bs_0061 -> bs_0064`, `bs_0056 -> bs_0061` | reject appearance-only or spatial-only false bridges |

No sample in this plan should become a final SAR box, revised annotation, identity truth, or selector/ranking output.

## 7. Targeted Validation Plan

Do not run a full automatic repair. The next safe step is a small validation pack:

1. For each repairable item, generate before/after panels:
   - original crop;
   - fit-frame representative crop;
   - optional expanded diagnostic crop;
   - state tag overlay.
2. Recompute only diagnostic representative appearance for repaired frame subsets.
3. Compare repaired representative evidence against blocked negative comparators.
4. Require a competition-exclusion note before any candidate is upgraded.
5. Keep outputs under `outputs/oty2/optical_evidence_repair_plan_<timestamp>/`.
6. Commit only the report/summary or a narrow helper script, not images or arrays.

The validation success criterion is not "more merges." It is whether the repaired evidence becomes a safer SAR migration hint without increasing wrong-target risk.

## 8. Required Answers

1. Repairable weak/blocked samples were found: `GM_RM017 bs_0010`, `GM_RM011 bs_0015`, `GM_RM011 bs_0061 seg_002 -> seg_003`, plus partial repair candidates `bs_0061 seg_001 -> seg_002`, `bs_0044 -> bs_0038`, `bs_0002 -> bs_0007`, and selected `bs_0029` frames.
2. They were judged weak or bad because current aggregation treats partial vehicle crops, edge crops, and different vehicle-part views as if they were comparable full-vehicle appearance observations.
3. The dominant fix is not tracker tuning. It is box/crop/state compensation: bad-frame exclusion, fit-frame representative selection, diagnostic crop expansion, part-state tags, and competition-exclusion rules.
4. `bs_0061 -> bs_0064` and `bs_0056 -> bs_0061` remain blocked because they demonstrate target competition or part-switch risk.
5. "Model weak but human plausible" cases exist: `bs_0044 -> bs_0038`, `bs_0002 -> bs_0007`, and `bs_0061 seg_001 -> seg_002` are visually plausible but cannot be promoted by raw appearance alone.
6. A "split before use" need exists for GM_RM017 `bs_0012`, and likely for `bs_0008`; whole-track aggregation is unsafe there.

## Conclusion

```text
REPAIRABLE_OPTICAL_EVIDENCE_READY_FOR_TARGETED_VALIDATION
```

Interpretation: several weak or unstable optical evidence cases are repairable enough for a small targeted validation pack, but the repaired output must remain graded SAR migration evidence, not final identity or annotation.
