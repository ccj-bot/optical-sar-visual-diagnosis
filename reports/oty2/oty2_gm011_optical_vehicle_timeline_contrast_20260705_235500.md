# OTY2 GM_RM011 Optical Vehicle Timeline Contrast

Timestamp: `20260705_235500`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified starting HEAD: `e7f50cb Reconstruct optical vehicle timelines for migration`

## Boundary

This round continues the optical temporal mainline after the GM_RM017 vehicle timeline reconstruction. SAR-side migration consumption remains paused. The purpose is to use `GM_RM011` as a bounded second-stage contrast, not to rebuild the whole scene and not to generate SAR pairing/support, final boxes, revised GT, selector/ranking output, or identity truth.

The scope is limited to previously reviewed GM_RM011 breakpoints and counterexamples:

- `bs_0015 seg_001 -> seg_002`
- `bs_0061 seg_002 -> seg_003`
- `bs_0061 seg_001 -> seg_002`
- `bs_0029 seg_001 -> seg_002`
- `bs_0044 seg_002 -> bs_0038 seg_002`
- `bs_0002 seg_001 -> bs_0007 seg_001`
- negative guards `bs_0061 seg_001 -> bs_0064 seg_001` and `bs_0056 seg_001 -> bs_0061 seg_001`

No new visual panels were required. This report reuses ignored panels from:

- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/`
- `outputs/oty2/optical_blocked_case_repair_review_20260705_224500/`

## Why GM_RM011 Is Only A Contrast

GM_RM017 answered the main question: full-frame visual continuity can reconstruct diagnostic physical vehicle timelines when the scene is simple enough and dense frames are inspected. GM_RM011 is more cluttered and contains many short, partial, and edge-adjacent tracklets. It should therefore not be treated as a global timeline rebuild in this round.

The useful contrast question is narrower:

Can the same diagnostic logic distinguish local physical continuity from false appearance or proximity bridges?

The answer is yes. GM_RM011 provides both positive local continuity candidates and negative guards.

## Local Chain Judgement

| Relation | Visual judgement | Chain status | Repair action | Use level |
| --- | --- | --- | --- | --- |
| `bs_0015 seg_001 -> seg_002` | Same white vehicle front/windshield remains continuous across a 2-frame gap. | local diagnostic continuity chain | candidate link only; use endpoint fit frames; tag `partial_front_side` | `continuity_candidate_only` |
| `bs_0061 seg_002 -> seg_003` | Same central white vehicle front/windshield continues across a 2-frame gap; left-edge neighbor is separable. | local diagnostic continuity chain | candidate link only; retain competitor-exclusion note | `continuity_candidate_only` |
| `bs_0061 seg_001 -> seg_002` | Same white vehicle is plausible, but the relation spans 9 frames and changes from rear/side to front/windshield. | weak local chain candidate | keep as part-state transition, not a direct merge | `continuity_candidate_only` |
| `bs_0029 seg_001 -> seg_002` | Same right-edge white vehicle is plausible but the later crop collapses into a thin edge strip. | review-only local hint | edge-truncated review, not timeline evidence | `review_only` |
| `bs_0044 seg_002 -> bs_0038 seg_002` | Same white vehicle is plausible under part-box transition from upper side/window to front/hood. | weak diagnostic chain candidate | state-tag part transition and downweight raw appearance | `weak_optical_timeline` |
| `bs_0002 seg_001 -> bs_0007 seg_001` | Same white SUV is plausible, but rear/body crop changes to upper-window strip. | weak diagnostic chain candidate | state-tag part transition and require fit-frame representative | `weak_optical_timeline` |
| `bs_0061 seg_001 -> bs_0064 seg_001` | Not the same target: after segment boxes the left-edge competing vehicle while the central white car remains separate. | negative guard | block appearance-only bridge | `not_usable` |
| `bs_0056 seg_001 -> bs_0061 seg_001` | Not a safe chain: side/window strip switches to left-edge rear fragment or competing region. | negative guard | block proximity/part-switch bridge | `not_usable` |

## What Transfers From GM_RM017

GM_RM017 showed that low appearance stability can come from crop geometry rather than real identity failure. GM_RM011 confirms the same mechanism in local cases:

- `bs_0015` and `bs_0061 seg_002 -> seg_003` are positive examples: the physical continuity is visible even though boxes are partial.
- `bs_0044 -> bs_0038` and `bs_0002 -> bs_0007` are part-transition examples: the chain is plausible, but raw appearance is not a fair comparison.
- `bs_0029` is an edge-truncation example: the physical hint exists, but the visible area is too thin for a timeline chain.

The new lesson is that GM_RM011 also has true competitor failures. Those must not be repaired by the GM_RM017 rule. Dense context and competitor exclusion are required.

## Method Failure Localization

Failure causes by group:

- `short_gap_partial_crop`: tracker split but physical continuity remains visible (`bs_0015`, `bs_0061 seg_002 -> seg_003`).
- `part_state_transition`: the same physical vehicle may be visible through different parts of the body (`bs_0061 seg_001 -> seg_002`, `bs_0044 -> bs_0038`, `bs_0002 -> bs_0007`).
- `edge_truncated_thin_crop`: too little vehicle area remains to form a reliable chain (`bs_0029`).
- `competition_unresolved`: another vehicle explains the successor box better than the proposed chain (`bs_0061 -> bs_0064`, `bs_0056 -> bs_0061`).

The main diagnostic rule is:

```text
crop similarity or short spatial distance is not enough; the focus box must remain on the same physical vehicle region, and competitors must be excluded.
```

## Track ID Handling

No GM_RM011 relation in this contrast round should directly merge tracker IDs.

Allowed diagnostic actions:

- record local candidate links for `bs_0015 seg_001 -> seg_002` and `bs_0061 seg_002 -> seg_003`;
- keep `bs_0061 seg_001 -> seg_002` as weak part-transition continuity;
- keep `bs_0044 -> bs_0038` and `bs_0002 -> bs_0007` as weak part-transition timelines;
- keep `bs_0029` as review-only edge hint;
- preserve `bs_0061 -> bs_0064` and `bs_0056 -> bs_0061` as negative guards.

Forbidden actions:

- no final track merge;
- no identity truth;
- no revised GT;
- no final boxes;
- no SAR pairing/support;
- no selector/ranking output.

## Comparison With GM_RM017

| Question | GM_RM017 | GM_RM011 contrast |
| --- | --- | --- |
| Can full-frame continuity form vehicle timelines? | Yes, four diagnostic chains plus one non-vehicle reject. | Only local chains are safe in this round. |
| Main failure | Edge/partial crops and one false non-vehicle track. | Partial crops plus real competitor and part-switch traps. |
| Candidate links needed | None among the five reviewed track IDs. | Yes, two strong local continuity candidates and several weak part-transition candidates. |
| Split needed | No split after dense-frame review; keep similar dark sedans separate. | Do not split in this round, but preserve negative guards before any link. |
| SAR readiness | GM_RM017 optical timeline input is ready at diagnostic level. | GM_RM011 is not globally ready; only selected local candidates are ready for later review input. |

## Does This Open SAR Again?

Not yet as SAR consumption. The safe next step is still optical-side chain packaging:

1. keep GM_RM017 as the main positive vehicle-timeline reference;
2. add GM_RM011 local chain candidates as contrast rows;
3. require any later SAR-side use to consume only these diagnostic optical chains, not raw track IDs or raw appearance edges.

This round does not resume SAR migration evidence consumption.

## Required Answers

1. SAR side remains paused; this is GM_RM011 optical timeline contrast only.
2. GM_RM011 does not yet form a global physical vehicle timeline set in this round; it forms selected local chain candidates.
3. Strong local continuity candidates are `bs_0015 seg_001 -> seg_002` and `bs_0061 seg_002 -> seg_003`.
4. Weak local candidates are `bs_0061 seg_001 -> seg_002`, `bs_0044 -> bs_0038`, and `bs_0002 -> bs_0007`.
5. Review-only case is `bs_0029`.
6. True competitor or identity-trap cases are `bs_0061 -> bs_0064` and `bs_0056 -> bs_0061`.
7. The main transferable repair from GM_RM017 is full-frame context plus part/edge state tags before judging appearance.
8. The main additional GM_RM011 guard is competitor exclusion.
9. No final annotation, revised GT, final boxes, SAR pairing/support, selector/ranking, or track merge is allowed.

## Conclusion

```text
OPTICAL_VEHICLE_TIMELINE_PARTIAL_REPAIRABLE
```

Interpretation: GM_RM011 has usable local diagnostic continuity candidates, but it is not globally reconstructed. The scene should remain a contrast set for part-transition and competition-guard logic before any later SAR-side consumption.
