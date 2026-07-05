# OTY2 Same-Vehicle Referent Consistency Audit

Timestamp: `20260705_165636`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified starting HEAD: `869a7ba Contrast GM011 optical timeline breakpoints`

## Boundary

This round pauses SAR migration evidence consumption and stays on the optical temporal mainline. The audit does not build a final vehicle chain, final annotation, revised GT, final box, SAR pairing/support table, selector, ranker, threshold, or identity truth.

The only question here is narrower:

```text
Do two optical observations describe the same real physical vehicle, or only similar box/crop content?
```

The answer is allowed to support a later diagnostic timeline graph, but it is not itself a final trajectory or SAR migration result.

## Visual Inputs

No new output panels were generated in this round. The audit reused existing ignored visual panels:

- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_all_tracks_dense_frames_145_214.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0002_focus_frames.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0008_focus_frames.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0010_focus_frames.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0012_focus_frames.jpg`
- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/panels/GM_RM011_breakpoint_01_same_track_short_gap_candidate_GM_RM011_bs_0015_seg_001_TO_GM_RM011_bs_0015_seg_002.jpg`
- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/panels/GM_RM011_breakpoint_02_same_track_short_gap_candidate_GM_RM011_bs_0061_seg_002_TO_GM_RM011_bs_0061_seg_003.jpg`
- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/panels/GM_RM011_breakpoint_03_same_track_short_gap_candidate_GM_RM011_bs_0029_seg_001_TO_GM_RM011_bs_0029_seg_002.jpg`
- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/panels/GM_RM011_breakpoint_04_same_track_short_gap_candidate_GM_RM011_bs_0061_seg_001_TO_GM_RM011_bs_0061_seg_002.jpg`
- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/panels/GM_RM011_breakpoint_05_cross_track_strong_candidate_GM_RM011_bs_0061_seg_001_TO_GM_RM011_bs_0064_seg_001.jpg`
- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/panels/GM_RM011_breakpoint_06_spatial_near_appearance_counterexample_GM_RM011_bs_0056_seg_001_TO_GM_RM011_bs_0061_seg_001.jpg`
- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/panels/GM_RM011_breakpoint_07_spatial_near_appearance_counterexample_GM_RM011_bs_0044_seg_002_TO_GM_RM011_bs_0038_seg_002.jpg`
- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/panels/GM_RM011_breakpoint_08_spatial_near_appearance_counterexample_GM_RM011_bs_0002_seg_001_TO_GM_RM011_bs_0007_seg_001.jpg`

## Why Same-Vehicle Referent Comes First

Optical windows, short tracklets, boxes, and crops are observations. They are not vehicle identity. Before any diagnostic timeline or later SAR migration use, the optical side must first decide whether those observations still point to the same physical car.

This is especially important because the current evidence can change in several ways without changing the underlying referent:

- view angle can change;
- visible vehicle part can change from rear, side, window, hood, windshield, or edge sliver;
- bounding box size and fit can change;
- crop background ratio can change;
- crop appearance and ResNet18 features can become weak;
- track ID can split or continue across part-state changes.

Those variations are tolerable only when full-frame continuity, motion direction, visible-part transition, box focus, and competitor exclusion still support one physical vehicle.

## Crop And Box Interpretation

A crop is box content, not the vehicle body itself. A low appearance match between two crops can mean that one crop contains hood plus windshield while the other contains side window, rear, background, or frame-edge residue. It should not directly negate same-vehicle referent consistency.

A partial box can still support same-vehicle judgement when:

- the box remains on the same physical vehicle region in the full frame;
- the temporal gap is short or the movement between frames is physically plausible;
- the visible part transition is explainable by camera motion or vehicle motion;
- a competing vehicle is visible but does not better explain the successor box;
- thin edge crops are not used as strong representatives.

A partial box should not support same-vehicle judgement when it jumps to another vehicle, follows only a background or non-vehicle object, or leaves a competitor that explains the later crop better.

## Judgement Summary

| Scene | Case | Same-vehicle judgement | Confidence | Action |
| --- | --- | --- | --- | --- |
| `GM_RM017` | `bs_0008` internal | `same_vehicle` | high | keep referent, downweight appearance |
| `GM_RM017` | `bs_0010` internal | `same_vehicle` | high | keep referent, downweight appearance |
| `GM_RM017` | `bs_0012` internal | `likely_same_vehicle` | medium-high | keep referent, downweight edge frames |
| `GM_RM017` | `bs_0008 -> bs_0012` | `not_same_vehicle` | high | forbid connection |
| `GM_RM017` | `bs_0002` | `not_same_vehicle` | high | exclude or manually review as non-vehicle |
| `GM_RM011` | `bs_0015 seg_001 -> seg_002` | `same_vehicle` | high | connect window |
| `GM_RM011` | `bs_0061 seg_002 -> seg_003` | `same_vehicle` | high | connect window |
| `GM_RM011` | `bs_0061 seg_001 -> seg_002` | `possible_same_vehicle` | medium | weak connect only |
| `GM_RM011` | `bs_0061 -> bs_0064` | `not_same_vehicle` | high | forbid connection |
| `GM_RM011` | `bs_0056 -> bs_0061` | `not_same_vehicle` | high | forbid connection |
| `GM_RM011` | `bs_0029 seg_001 -> seg_002` | `possible_same_vehicle` | low | manual review |
| `GM_RM011` | `bs_0044 -> bs_0038` | `possible_same_vehicle` | medium | weak connect only |
| `GM_RM011` | `bs_0002 -> bs_0007` | `possible_same_vehicle` | medium | weak connect only |

The row-level evidence is in `reports/oty2/samples/oty2_same_vehicle_referent_consistency_summary_20260705_165636.csv`.

## GM_RM017 Findings

`bs_0008` mainly describes the leading dark sedan. The same-car referent holds within the track because the dense full-frame panel shows continuous left-to-right motion, a stable relative position ahead of the later dark sedan, and boxes that remain on the same target despite edge truncation. The crop and feature instability are explainable as entry/exit partial boxes and nearby traffic context. The failure layer is crop/feature expression, not physical referent.

`bs_0010` mainly describes the white SUV. This is the clearest GM_RM017 car referent: the same white SUV remains visible from left entry, through the center, to right-edge exit. Late frames become thin and partial, so appearance should be downweighted, but the physical referent is stable.

`bs_0012` mainly describes the trailing dark sedan. The referent is likely the same within its window, with a visible left-to-right progression. The important guard is that it is not the same car as `bs_0008`. The two are similar dark sedans, but the dense full-frame sequence separates them spatially and temporally.

`bs_0002` does not describe a vehicle referent. The green box follows a foreground road barrier or temporary structure. It should not be used as a vehicle observation.

GM_RM017 therefore has clear same-car fragments, but it also has a necessary negative rule: similar dark-car crops must not be merged without dense full-frame referent support.

## GM_RM011 Findings

`bs_0015 seg_001 -> seg_002` can be treated as the same white vehicle. The front, windshield, mirror, and hood region continue across a short gap, and no better competitor explains the successor crop.

`bs_0061 seg_002 -> seg_003` can also be treated as the same white vehicle. The central white vehicle front and windshield remain the focus across the short gap. A left-edge neighbor appears, but it is separable and does not explain the central successor box.

`bs_0061 seg_001 -> seg_002` is only possible same-vehicle referent consistency. The observation can be explained as the same white vehicle changing from rear/side to front/window view, but the gap is longer and the visible part change is larger. It should be a weak connection only, not a direct track merge.

`bs_0061 -> bs_0064` must be forbidden. The successor observation falls on a left-edge competing vehicle while the central white vehicle is still visible separately. Appearance or proximity cannot override the full-frame target switch.

`bs_0056 -> bs_0061` must also be forbidden as a strong connection. The before segment is a side/window strip of a white vehicle, while the after segment starts on a left-edge rear fragment or competing region. The referent cannot be established.

`bs_0029 seg_001 -> seg_002` is only a low-confidence review hint. The right-edge white vehicle is plausible, but the later crop collapses into a thin edge strip.

`bs_0044 -> bs_0038` and `bs_0002 -> bs_0007` are possible same-vehicle part transitions. They can support weak diagnostic edges after fit-frame review, but not identity truth or a direct merge.

## Method Failure Layers

The audit separates failure layers as follows:

- Box layer: edge frames and partial boxes can still point to the same car, but thin edge strips cannot carry strong evidence.
- Crop layer: crop content is often only a vehicle part plus background, not a full car representation.
- Feature layer: ResNet18 weakness is expected under part-state change and should not veto full-frame continuity.
- Track ID layer: one track ID can be a useful observation container, but not a true identity label.
- Window connection layer: connections need competitor exclusion; spatial nearness or appearance similarity alone creates false bridges.

The dominant failure is not a lack of vehicle referents. It is that the current method expresses referents through crop features and track IDs that cannot represent part-state changes or competitor exclusion.

## How To Move Into A Diagnostic Timeline Graph

The next optical-side step can build a diagnostic timeline graph with three edge types:

- confirmed referent edges, such as `GM_RM017 bs_0008` internal, `GM_RM017 bs_0010` internal, `GM_RM011 bs_0015 seg_001 -> seg_002`, and `GM_RM011 bs_0061 seg_002 -> seg_003`;
- weak referent edges, such as `GM_RM011 bs_0061 seg_001 -> seg_002`, `bs_0044 -> bs_0038`, and `bs_0002 -> bs_0007`;
- forbidden edges, such as `GM_RM017 bs_0008 -> bs_0012`, `GM_RM011 bs_0061 -> bs_0064`, and `GM_RM011 bs_0056 -> bs_0061`.

The graph should keep track IDs, crops, boxes, and feature distances as evidence fields, not identity labels.

## SAR And Final Annotation Answers

Current SAR migration is not allowed to resume broadly. Only fragments with clear same-vehicle referent consistency may later be considered as optical-side input, and even then only as diagnostic prior evidence.

Current final annotation, revised GT, final boxes, SAR pairing/support, selector/ranking, threshold tuning, and model training are not allowed.

## Required Answers

1. Same-vehicle referent consistency comes first because later optical timelines and any SAR input are unsafe if the optical observations do not point to the same physical vehicle.
2. View angle, visible part, box size, crop content, feature strength, and track ID can vary without breaking same-car judgement when full-frame motion and competitor exclusion remain coherent.
3. A crop represents box content. It is not automatically the vehicle body or identity.
4. A partial box can still be same-car evidence when it remains on the same physical vehicle region and the visible-part change is plausible; it cannot do so when it jumps to a competitor or non-vehicle object.
5. GM_RM017 confirmed same-car fragments: `bs_0008`, `bs_0010`, and likely `bs_0012` internally.
6. GM_RM017 repair/guard cases: exclude `bs_0002`; forbid `bs_0008 -> bs_0012`; downweight edge/crop appearance for `bs_0008`, `bs_0010`, and `bs_0012`.
7. GM_RM011 local same-car connections: `bs_0015 seg_001 -> seg_002` and `bs_0061 seg_002 -> seg_003`.
8. GM_RM011 forbidden similar/proximity connections: `bs_0061 -> bs_0064` and `bs_0056 -> bs_0061`.
9. The main failures occur at box, crop, feature, track ID, and window-connection layers, with competitor exclusion the hardest GM_RM011 issue.
10. The next step is a diagnostic timeline graph that separates confirmed, weak, and forbidden referent edges.
11. SAR migration may only consume clearly referent-consistent fragments later; this round does not enter SAR migration.
12. Final annotation or revised GT is not allowed.

## Conclusion

```text
SAME_VEHICLE_REFERENT_READY_FOR_TIMELINE_GRAPH
```

Interpretation: enough same-vehicle and forbidden-connection fragments are now explicitly separated to enter a diagnostic vehicle timeline graph. The result remains optical-side evidence only and does not authorize SAR consumption or final labels.
