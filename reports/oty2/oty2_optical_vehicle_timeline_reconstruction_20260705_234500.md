# OTY2 Optical Vehicle Timeline Reconstruction

Timestamp: `20260705_234500`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified starting HEAD: `cd47254 Define SAR migration evidence table from optical repairs`

## Boundary

This round pauses SAR-side migration evidence consumption and returns to the optical temporal mainline. The question is not how SAR should consume repaired optical evidence. The question is whether the optical side can express diagnostic timelines for the same physical vehicle.

This report does not generate final annotations, revised GT, final boxes, SAR pairing/support, selector/ranking output, clean-pool promotion, or identity truth. The output is diagnostic only:

- visual vehicle-chain reconstruction for `GM_RM017`;
- method failure localization for current tracker IDs and crop appearance;
- minimal repair actions before any later SAR migration input.

## Inputs And Visual Panels

Read source artifacts:

- `outputs/oty2/tracklet_embedding_aggregation_probe_20260705_193000/tracklet_embedding_index.csv`
- `outputs/oty2/embedding_track_linkage_probe_20260705_183000/embedding_track_linkage_rows.csv`
- `outputs/oty2/crop_reid_embedding_probe_20260705_170500/crop_reid_embedding_index.csv`
- `reports/oty2/oty2_optical_evidence_visual_judgement_20260705_205500.md`
- `reports/oty2/oty2_optical_evidence_repair_plan_20260705_214500.md`
- `reports/oty2/oty2_blocked_case_repair_review_20260705_224500.md`
- `reports/oty2/oty2_optical_evidence_targeted_repair_validation_20260705_231500.md`

Generated ignored visual panels:

- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_all_tracks_critical_frames.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_all_tracks_dense_frames_145_214.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0001_focus_frames.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0002_focus_frames.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0008_focus_frames.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0010_focus_frames.jpg`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/panels/GM017_bs_0012_focus_frames.jpg`

Generated ignored metadata:

- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/GM017_track_summary.csv`
- `outputs/oty2/optical_vehicle_timeline_reconstruction_20260705_234500/metadata.json`

Only the report, summary CSV, and helper script are committed. The panels remain under ignored `outputs/`.

## Why Pause SAR And Return To Optical Timelines

SAR migration cannot safely consume optical evidence if the optical side cannot say which observations belong to the same physical vehicle. Tracker IDs and crop embeddings are not identity truth. In `GM_RM017`, the dense visual panels show that several weak or unstable embeddings are caused by frame-edge crops and partial vehicle boxes, not necessarily by a failure of physical vehicle continuity.

Therefore the safe order is:

1. reconstruct diagnostic physical vehicle chains from full-frame visual continuity;
2. classify tracker/crop failures against those chains;
3. only then decide whether optical timelines can become later SAR migration input.

## GM_RM017 Track Inventory

The current BoT-SORT `normalized_active` tracklet index contains five GM_RM017 track IDs:

| Track ID | Frames | Visual role | Timeline judgement |
| --- | ---: | --- | --- |
| `bs_0001` | `118-164` | large white box/truck-like vehicle moving through the frame | keep as a stable diagnostic vehicle chain |
| `bs_0002` | `121-129` | road barrier / non-vehicle structure near the foreground | not usable as a physical vehicle chain |
| `bs_0008` | `145-185` | leading dark sedan moving from left edge through center toward right edge | keep as a weak optical timeline after fit-frame selection |
| `bs_0010` | `151-200` | white SUV moving from left edge through center toward right edge | keep as a weak optical timeline after edge/partial handling |
| `bs_0012` | `162-214` | trailing dark sedan moving from left edge through center toward right edge | keep as a weak optical timeline after fit-frame selection |

The dense `145-214` panel is important: it resolves part of the earlier ambiguity. Looking only at the two ends made `bs_0008` and `bs_0012` look like possible same-track switches. The dense view shows a plausible sequence of distinct moving vehicles: a leading dark sedan (`bs_0008`), a white SUV (`bs_0010`), and a trailing dark sedan (`bs_0012`). Their crop embeddings are unstable because the boxes are partial or edge-truncated at entry and exit, not because the whole scene lacks optical vehicle timelines.

## Diagnostic Vehicle Chains

| Chain | Source track IDs | Frames | Visual basis | Competition | Repair action | SAR migration use level |
| --- | --- | ---: | --- | --- | --- | --- |
| `GM017_chain_01_large_white_box_vehicle` | `bs_0001` | `118-164` | the same large white rear/box body is followed across the crossing area | low for that object, though it overlaps other traffic later | keep | `strong_optical_timeline` |
| `GM017_chain_02_white_suv` | `bs_0010` | `151-200` | the same white SUV is visible from left entry, through center, to right-edge exit | nearby dark sedans exist but are separable in full-frame context | select fit frames, downweight appearance, tag edge/partial visibility | `weak_optical_timeline` |
| `GM017_chain_03_dark_sedan_lead` | `bs_0008` | `145-185` | a dark sedan moves continuously from the left edge to the right side ahead of the white SUV | competing dark sedan appears later, but dense motion separates the leading vehicle | drop edge-only frames, select fit frames, downweight appearance | `weak_optical_timeline` |
| `GM017_chain_04_dark_sedan_trail` | `bs_0012` | `162-214` | a trailing dark sedan follows a similar left-to-right path after the white SUV/dark lead sequence | visually close to other vehicles near entry/exit, but not the same as `bs_0008` | drop edge-only frames, select fit frames, downweight appearance | `weak_optical_timeline` |
| `GM017_reject_01_non_vehicle_barrier` | `bs_0002` | `121-129` | the crop follows a foreground road barrier/temporary structure, not a physical vehicle | not applicable | manual review / exclude from vehicle timeline | `not_usable` |

## Track-Level Answers

### `bs_0001`

`bs_0001` is visually stable. It follows the same large white box/truck-like vehicle from frames `118-164`. The box is bright and partially saturated, but it consistently covers the same object. It should be retained as a diagnostic vehicle chain. It does not need a candidate link or split.

### `bs_0002`

`bs_0002` is not a valid physical vehicle chain. It tracks a foreground road barrier or similar non-vehicle structure from frames `121-129`. It should be excluded or manually reviewed as a false vehicle-track candidate. It should not feed SAR migration.

### `bs_0008`

`bs_0008` should not be treated as a direct failure after dense-frame review. It follows a leading dark sedan from left-edge entry through the scene toward right-edge exit. The appearance instability is caused mainly by:

- left/right edge contact;
- crop truncation at entry and exit;
- partial rear/front views;
- nearby competing vehicles when the white SUV and trailing dark sedan enter the same frame.

Repair action: keep as a weak timeline, use fit frames in the middle of the chain, drop or downweight edge-only frames, and keep a competitor-separation note. It does not need a split under the current visual evidence.

### `bs_0010`

`bs_0010` is the cleanest car-like physical chain. It follows the white SUV from left-edge entry through center to right-edge exit. The ResNet18 weakness is not evidence that it is a different vehicle; it is a crop-quality problem. The start and end frames are partial, and frame `200` is especially thin at the right edge.

Repair action: keep as a weak optical timeline, select fit frames, tag `edge_contact`, `partial_visible`, and `model_weak_visual_confirmed`, and downweight appearance. It can serve later SAR migration as optical timeline input, but not as a final box or hard identity claim.

### `bs_0012`

`bs_0012` tracks a trailing dark sedan from left-edge entry to right-edge exit. Earlier endpoint-only panels made it look like a possible identity ambiguity, but the dense frame sequence supports a separate trailing-vehicle interpretation. Its embedding instability is due to edge crops and partial views, especially at the right edge.

Repair action: keep as a weak timeline, select fit frames, drop edge-only endpoints, and do not connect it to `bs_0008`. `bs_0012` should remain a separate diagnostic vehicle chain unless later manual review proves otherwise.

## Method Failure Localization

The main failure is not that GM_RM017 lacks optical temporal structure. The main failure is that the current method tries to express physical vehicle continuity through tracker IDs plus crop appearance, where the crop can be a partial vehicle part or frame-edge sliver.

Failures found:

- `bs_0010`: model weak but human-confirmed same vehicle; caused by partial white-SUV crops and edge contact.
- `bs_0008`: low minimum appearance is caused by edge-truncated leading dark sedan crops and competing vehicles, not by a proven track switch.
- `bs_0012`: low minimum appearance is caused by partial/edge dark-sedan crops and late right-edge truncation.
- `bs_0002`: detection-level false vehicle candidate; this is a track eligibility problem, not a repairable vehicle timeline.

True identity conflict found:

- No forced merge between `bs_0008` and `bs_0012` is allowed. They are visually similar dark sedans, but the dense panel supports two distinct physical vehicles. Treating them as one chain would create a real identity conflict.

Candidate links:

- No cross-track candidate link among the five GM_RM017 track IDs is required by the current evidence.
- Untracked detections near frame `117` can remain context only; they are not enough to create a diagnostic link in this round.

## Can GM_RM017 Serve SAR Migration After Optical Repair?

Yes, but only after keeping the optical evidence at diagnostic timeline level:

- `bs_0001`: strong optical timeline for a large vehicle-like object; target relevance should be checked before any car-focused migration use.
- `bs_0010`: weak optical timeline for the white SUV; usable as later SAR migration input with edge/partial tags.
- `bs_0008`: weak optical timeline for the leading dark sedan; usable with fit-frame selection and competitor notes.
- `bs_0012`: weak optical timeline for the trailing dark sedan; usable with fit-frame selection and explicit separation from `bs_0008`.
- `bs_0002`: not usable.

The output should not go back to SAR consumption immediately unless the next step consumes only these repaired optical timelines and preserves the no-final-box boundary.

## Implication For GM_RM011

GM_RM011 should not be repaired by raw appearance thresholds. The GM_RM017 result shows the correct diagnostic order:

1. view dense full-frame context;
2. identify physical vehicle chains;
3. decide whether two similar dark or white crops are actually the same vehicle;
4. only then decide whether a tracklet should be kept, split, or linked.

For GM_RM011, this means short-gap candidates should be checked against dense full-frame motion and competitor exclusion before any connection is recorded. Appearance similarity alone is not enough.

## Required Answers

1. SAR-side work is paused because optical physical vehicle timelines must be established before migration evidence can be safely consumed.
2. GM_RM017 can form clear diagnostic vehicle timelines from full-frame visual continuity.
3. The five track IDs map to four physical vehicle chains plus one non-vehicle/road-barrier false track.
4. `bs_0008` should be kept as a weak leading dark-sedan timeline; `bs_0010` should be kept with appearance downweighting and fit-frame selection; `bs_0012` should be kept as a separate weak trailing dark-sedan timeline; `bs_0002` should be excluded/manual-reviewed; `bs_0001` should be kept.
5. `bs_0008`, `bs_0010`, and `bs_0012` instability is mainly box quality, edge truncation, partial crop, and model feature weakness, not proven same-vehicle failure.
6. The true identity-risk is false connection between visually similar dark sedans, especially `bs_0008` and `bs_0012`; they must remain separate unless later evidence proves otherwise.
7. After repair, GM_RM017 can form optical timeline evidence for later SAR migration input.
8. `bs_0001` is strong optical timeline; `bs_0008`, `bs_0010`, and `bs_0012` are weak optical timelines; `bs_0002` is not usable.
9. The main remaining weakness is crop/box quality at frame edges, not global optical timeline failure.
10. For GM_RM011, repair must start from dense full-frame vehicle-chain inspection before any candidate connection.
11. The next step can return to SAR only if it consumes repaired optical timelines as soft migration input and does not generate final boxes or pairing/support automatically.
12. Final annotations, revised GT, and final boxes are not allowed in the current stage.

## Conclusion

```text
OPTICAL_VEHICLE_TIMELINE_READY_FOR_SAR_MIGRATION_INPUT
```

Interpretation: GM_RM017 can be reconstructed into diagnostic optical vehicle timelines. Most failures are repairable box/crop/state issues, with one non-vehicle false track and one important guard against merging two similar dark sedans.
