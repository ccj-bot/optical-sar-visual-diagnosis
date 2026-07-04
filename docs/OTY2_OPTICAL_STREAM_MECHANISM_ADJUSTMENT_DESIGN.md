# OTY2 Optical Stream Mechanism Adjustment Design

Updated: 2026-07-04

This document defines the next global design step after the cross-scene optical stream generalization audit. It is a design document only. It does not authorize scripts, diagnostics, runtime logic changes, SAR pairing, support audit, final annotations, revised GT, final boxes, selector/ranking logic, threshold tuning, or weighted fusion.

## 1. Design Goal

The next step is not to repair `GM_RM011` as a scene-specific exception. The next step is to adjust the global optical object-stream mechanism so that fragmented, crowded, boundary-contact, and state-unstable scenes are represented honestly.

The expected output of the adjusted mechanism is not a clean object stream. It is an uncertainty-aware optical hypothesis field.

This field may later support OTY2 posthoc diagnosis, but it must not be promoted to identity truth or directly merged into the clean `215` pool.

## 2. Why GM_RM011 Is Not A Special Patch Target

`GM_RM011` is not detector-blocked. The GM_RM011 reconstruction produced optical detections, OTY1 tracklets, OTY1a merge candidates, ByteTrack hypotheses, and P4G object hypotheses. The failure is that the recovered stream is highly fragmented and review-heavy.

Treating this as a one-scene patch would hide the actual problem: the optical object-stream mechanism depends on assumptions that are not stable across scenes. GM_RM011 exposes those assumptions because it has dense detections, crowded frames, overlap competition, boundary contact, partial/full box changes, and many uncertain object hypotheses.

Local fixes are therefore not valid mechanism evidence. A local threshold or scene-specific merge rule can make one table look better while leaving the global mechanism unvalidated.

## 3. Why Earlier GM_RM017 / GM_RM019 Passes Were Not Mechanism Success

Earlier `GM_RM017` and `GM_RM019` outputs showed that the pipeline could generate tables and schemas. That is schema-compatible result generation, not proof of identity continuity.

The cross-scene audit showed:

- `GM_RM017` is easier: fewer tracker tracks, longer ByteTrack median track length, fewer unmatched detections, and no duplicate-overlap count in the inspected tracker summary.
- `GM_RM019` already has the same failure family: high short-track ratio, many unmatched detections, duplicate-overlap risk, many ambiguous merge candidates, and high review-required object-hypothesis ratio.
- All three scenes were `ready_with_uncertainty`, not mechanism-stable.

Therefore previous "passes" must be described as diagnostic availability. They must not be described as clean optical-stream success.

## 4. Current Implicit Assumptions

The current optical object-stream mechanism implicitly assumes:

- detections are frequent enough for adjacent-frame association;
- bbox center, area, and aspect ratio change smoothly;
- one-to-one adjacent-frame geometry is usually enough to form a useful track fragment;
- same-frame targets are spatially separated enough;
- short missing gaps are rare;
- truncation, occlusion, and edge contact are secondary cases;
- a tracker ID can act as a stable continuity handle;
- a P4G object ID can be handed forward as if it were a clean object;
- fragment merge candidates are sparse enough to review later;
- `PASS_WITH_UNCERTAINTY` is good enough to continue.

These assumptions are only safe for schema construction. They are not safe for mechanism claims.

## 5. Assumptions Exposed As Unstable

`GM_RM011` exposes instability in:

- target separation, because crowded frames and same-frame overlaps are common;
- box smoothness, because boundary contact and partial/full transitions appear frequently;
- adjacent-frame association, because OTY1 produces many ambiguous or short tracklets;
- tracker continuity, because ByteTrack leaves many detections unmatched and produces possible ID switches or duplicate-overlap hypotheses;
- object-level readiness, because most P4G objects require review.

`GM_RM019` shows that the same risks already existed before GM_RM011 recovery:

- many short OTY1 tracklets;
- many unmatched tracker detections;
- duplicate/overlap competition;
- ambiguous competing merge candidates;
- many object hypotheses not suitable for direct OTY2 use.

`GM_RM017` is not clean proof. It is a less severe case where the same machinery produced fewer visible failures.

## 6. Required Layering

The adjusted mechanism should use explicit layers:

| Layer | Meaning | Allowed interpretation |
| --- | --- | --- |
| Detection observation | A detector box on one optical frame | An observation, not an object identity |
| Track fragment | A local chain of observations under runtime-safe geometry/tracker rules | A continuity hypothesis over a limited span |
| Merge candidate | A possible relation between fragments | A review or uncertainty relation, not confirmed identity |
| Object hypothesis | A grouped optical hypothesis with primary and secondary observations | A diagnostic object-level carrier |
| Uncertain continuity field | A graph of observations, fragments, relations, and uncertainty states | A posthoc-diagnosis input field |
| Not identity truth | Mandatory interpretation of all above IDs | No tracker ID, fragment ID, or P4G ID is ground-truth identity |

The core design change is to make uncertainty a first-class output rather than a side note.

## 7. Tracker ID And P4G Object ID Are Not Identity Truth

Tracker IDs are generated by runtime association rules and can be affected by occlusion, missed detections, duplicate boxes, crossing, boundary contact, and partial/full transitions. A tracker ID is a continuity hypothesis, not a proof that all attached observations belong to the same physical vehicle.

P4G object IDs aggregate tracker output, OTY1/OTY1a context, and secondary observations. They are useful as object-level handles, but they inherit upstream uncertainty. They must not be used as identity truth, final annotations, revised GT, final boxes, or clean paired objects.

Any downstream consumer must read the uncertainty fields with the ID. An ID without uncertainty state is not a valid mechanism output.

## 8. Target State Tags

The adjusted optical stream should attach explicit state tags to detections, track fragments, merge candidates, and object hypotheses.

Required target-state tags:

- `complete_visible`: bbox appears to cover a complete visible vehicle.
- `partial_visible`: bbox appears to cover only part of the vehicle.
- `truncation`: the object is likely clipped by frame boundary or field of view.
- `occlusion`: continuity is interrupted or shape changes suggest occlusion; runtime-safe evidence only.
- `edge_contact`: bbox touches or stays close to image boundary.
- `partial_to_full_transition`: bbox changes from partial-object view to fuller-object view.
- `short_missing_gap`: a short temporal gap exists between otherwise plausible fragments.
- `multi_object_competition`: same-frame neighboring objects can confuse association.
- `duplicate_overlap_detection`: duplicate or overlapping detector boxes may describe the same or competing physical objects.

These tags are not labels of truth. They are uncertainty descriptors that explain why association is strong, weak, ambiguous, or blocked.

## 9. Fragment Handling

Short fragments must not be discarded simply because they are short. A short fragment can represent:

- a true partial observation;
- an occluded or truncated vehicle segment;
- a detector dropout boundary;
- a duplicate/overlap artifact;
- a competing object during crossing;
- a fragment that should remain separate.

The adjusted mechanism should preserve interpretable fragment relations:

| Relation state | Meaning | Downstream handling |
| --- | --- | --- |
| `strong_continuity` | Geometry, timing, state, and competition context support the relation | May be used as a strong hypothesis, still not identity truth |
| `weak_continuity` | Some evidence supports continuity but gaps/state changes remain | Carry forward as uncertain continuity |
| `ambiguous_continuity` | Multiple plausible fragment relations compete | Preserve competing relations; no forced merge |
| `blocked_continuity` | Relation is rejected or unsafe due to gap, motion, class, shape, or competition conflict | Keep as diagnostic negative evidence |

The mechanism must not force identity merges to make a scene look cleaner. A confirmed identity merge requires a later globally justified rule, not a local scene fix.

## 10. Multi-Object Competition Handling

Multi-object competition should be represented explicitly, not hidden inside tracker failure.

Required competition concepts:

- `crowded_frame`: a frame with multiple vehicle detections.
- `close_neighbor_pair`: two detections close enough to risk association confusion.
- `overlap_competition`: bbox overlap suggests duplicate or competing hypotheses.
- `possible_crossing`: target paths or fragments may cross or exchange order.
- `duplicate_hypothesis`: two tracks or fragments may represent the same physical target.
- `competing_merge_candidates`: multiple plausible fragment relations compete for the same source or target fragment.

The output should preserve competition structure. It should not select one candidate as identity truth unless a later global mechanism justifies that decision.

## 11. Uncertainty-Aware Optical Hypothesis Field

The next mechanism output should be an uncertainty-aware optical hypothesis field, not a clean stream.

Minimum field semantics:

- keep detection observations with bbox, confidence, frame, and state tags;
- keep track fragments with continuity quality, length, gaps, and state summaries;
- keep merge candidate edges with relation state and rejection/ambiguity reasons;
- keep object hypotheses with primary observations, secondary observations, orphan observations, and review-required status;
- keep multi-object competition and duplicate-overlap indicators;
- keep readiness as a taxonomy: `schema_compatible`, `ready_with_uncertainty`, `mechanism_stable`, or blocked states.

The field is successful only if it describes uncertainty faithfully. It is not successful merely because it emits object IDs.

## 12. OTY2 Usage Contract

The uncertainty-aware optical hypothesis field can be used later in OTY2 only under these constraints:

- It can be used for posthoc diagnosis.
- It can enter support audit only as an uncertain hypothesis field, not as clean identity.
- It can enter temporal compatibility checks as a continuity hypothesis, not as verified pairing.
- It cannot become identity truth.
- It cannot directly enter the clean `215` pool.
- It cannot generate final annotations, revised GT, final boxes, selector/ranking outputs, or weighted-fusion rules.

If support or pairing diagnostics are later authorized, they must consume the uncertainty state instead of silently treating object IDs as clean objects.

## 13. Minimal Implementation Route

This document does not implement the route. It only defines the design sequence.

Step 1: Unified cross-scene object-stream diagnosis table

- Summarize detection continuity, fragment counts, tracker outcomes, merge candidates, object-hypothesis readiness, review burden, and competition indicators across scenes.
- Include GM_RM011, GM_RM017, and GM_RM019 at minimum.

Step 2: State tags for detection / track / object hypothesis

- Add explicit state tags for complete/partial visibility, truncation, occlusion, edge contact, partial-to-full transition, short missing gap, multi-object competition, and duplicate/overlap detection.
- Keep tags descriptive and runtime-safe.

Step 3: Fragment relation graph

- Represent fragments and candidate relations as a graph.
- Label edges as `strong_continuity`, `weak_continuity`, `ambiguous_continuity`, or `blocked_continuity`.
- Preserve competing candidates rather than forcing a single winner.

Step 4: Uncertainty-aware object hypothesis field

- Emit object hypotheses with uncertainty state, secondary observations, orphan observations, relation provenance, and review-required fields.
- Do not call this a clean object stream unless a later mechanism proves stability.

Step 5: Decide whether to enter support/pairing diagnosis

- Enter only after cross-scene optical-stream uncertainty is represented.
- If entered, consume the field as uncertain posthoc diagnosis input.
- Do not promote GM_RM011 or any uncertain object into clean `215`.

## 14. Forbidden Moves

Do not:

- tune thresholds locally to make one scene pass;
- only fix GM_RM011;
- switch trackers and declare the mechanism solved;
- treat `PASS_WITH_UNCERTAINTY` as success;
- treat tracker ID as identity;
- treat P4G object ID as identity;
- jump directly into SAR pairing or support audit;
- create final annotations;
- create revised GT;
- create final boxes;
- create selector/ranking logic;
- use weighted fusion as the explanation;
- use SAR GT, SAR image observation, or GT-local fields to construct optical runtime identity.

The mechanism is not fixed until it can explain uncertainty across scenes, including why easier scenes appeared usable and why harder scenes expose fragmentation and competition.
