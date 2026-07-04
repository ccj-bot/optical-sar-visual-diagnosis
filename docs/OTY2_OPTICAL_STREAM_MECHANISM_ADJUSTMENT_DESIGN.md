# OTY2 Optical Stream Mechanism Adjustment Design

Updated: 2026-07-04

This document defines the next global design step after the cross-scene optical stream generalization audit. It is a design document only. It does not authorize scripts, diagnostics, runtime logic changes, SAR pairing, support audit, final annotations, revised GT, final boxes, selector/ranking logic, threshold tuning, or weighted fusion.

## 1. Design Goal

The next step is not to repair `GM_RM011` as a scene-specific exception. The next step is to adjust the global optical object-stream mechanism so that fragmented, crowded, boundary-contact, and state-unstable scenes have explicit breakpoint causes, and those causes can guide safe same-vehicle fragment reconnect, multi-box merge, short-gap bridging, and multi-object competition resolution.

The expected intermediate output of the adjusted mechanism is not a clean object stream. It is an uncertainty-aware optical hypothesis field that records why continuity is strong, weak, ambiguous, or blocked.

This field may later support OTY2 posthoc diagnosis, but it must not be promoted to identity truth or directly merged into the clean `215` pool. It is not the final goal; it is the mechanism substrate for deciding which discontinuities can be corrected globally and which must remain review-required or blocked.

## 2. Uncertainty Is Not The Goal

The uncertainty-aware optical hypothesis field is not the final target. It is an intermediate representation that prevents unstable tracker IDs or P4G object IDs from being mistaken for identity truth.

The real objective is to find which uncertainties are explainable and correctable by a global mechanism:

- multi-box competition should be used to decide whether multiple observations can safely support the same target hypothesis;
- short fragments should be used to test same-vehicle reconnect rather than discarded by default;
- boundary, occlusion-like, truncation, and partial/full states should guide safe bridge decisions;
- short missing gaps should be tested as bridgeable continuity only when motion, timing, state, and competition context support it;
- ambiguous relations should stay ambiguous until the mechanism can close them across scenes.

If a breakpoint can be explained by stable cross-scene evidence, it should become part of a global reconnect, merge, bridge, or competition-resolution mechanism. If it cannot be explained safely, it should remain `review_required` or `blocked_continuity`.

Review-required is not a solution. It is the correct stop state when the mechanism cannot yet decide safely.

## 3. Why GM_RM011 Is Not A Special Patch Target

`GM_RM011` is not detector-blocked. The GM_RM011 reconstruction produced optical detections, OTY1 tracklets, OTY1a merge candidates, ByteTrack hypotheses, and P4G object hypotheses. The failure is that the recovered stream is highly fragmented and review-heavy.

Treating this as a one-scene patch would hide the actual problem: the optical object-stream mechanism depends on assumptions that are not stable across scenes. GM_RM011 exposes those assumptions because it has dense detections, crowded frames, overlap competition, boundary contact, partial/full box changes, and many uncertain object hypotheses.

Local fixes are therefore not valid mechanism evidence. A local threshold or scene-specific merge rule can make one table look better while leaving the global mechanism unvalidated.

## 4. Why Earlier GM_RM017 / GM_RM019 Passes Were Not Mechanism Success

Earlier `GM_RM017` and `GM_RM019` outputs showed that the pipeline could generate tables and schemas. That is schema-compatible result generation, not proof of identity continuity.

The cross-scene audit showed:

- `GM_RM017` is easier: fewer tracker tracks, longer ByteTrack median track length, fewer unmatched detections, and no duplicate-overlap count in the inspected tracker summary.
- `GM_RM019` already has the same failure family: high short-track ratio, many unmatched detections, duplicate-overlap risk, many ambiguous merge candidates, and high review-required object-hypothesis ratio.
- All three scenes were `ready_with_uncertainty`, not mechanism-stable.

Therefore previous "passes" must be described as diagnostic availability. They must not be described as clean optical-stream success.

## 5. Repeated Unclosed Problem: Multi-Box Competition

Multi-box competition is not a new problem. It appeared in earlier object-stream work, but it was not closed because the workflow treated it as a local anomaly or a later visual-review item rather than a core object-stream mechanism breakpoint.

In multi-box competition, multiple boxes may genuinely belong to the same vehicle. They may be duplicate detections, local-part boxes, partial/full transitions, or separate fragments of one target across adjacent frames. They may also be neighboring vehicles competing for the same track or merge edge.

The mechanism must not write "looks like one vehicle" as identity truth. It must separate:

- same-frame duplicate or overlapping boxes;
- adjacent-frame short fragments;
- competing successor or predecessor detections;
- competing OTY1a merge candidates;
- duplicate tracker hypotheses;
- neighboring vehicle competition.

The goal is to decide which fragments or boxes can form the same target hypothesis and which must remain in competition. Multi-box competition is therefore a primary mechanism problem, not only an output-quality problem.

## 6. Current Implicit Assumptions

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

## 7. Assumptions Exposed As Unstable

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

## 8. Separate Detector Ability, Detection Postprocess, And Association

Future analysis must not say only "the object stream is fragmented." It must identify the primary layer that caused the break.

### 8.1 Detector Ability

Detector ability asks whether YOLO can observe vehicles under hard optical conditions:

- missed detections near boundaries, occlusion-like regions, truncation, or dense vehicle groups;
- duplicate detections in crowded or overlapping scenes;
- incomplete local boxes that cover only part of a vehicle;
- box jumps in center, size, or aspect ratio.

These are detection-layer problems. They should be diagnosed separately from tracking.

### 8.2 Detection Postprocess

Detection postprocess asks whether the detector observations are stable before association:

- whether one vehicle appears as multiple overlapping boxes in the same frame;
- whether duplicate boxes, local boxes, or partial boxes survive into the stream input;
- whether NMS, class filtering, or confidence filtering creates unstable observations;
- whether category changes split a plausible same-vehicle sequence.

These are detection-postprocess problems. They change the observations that the stream builder receives.

### 8.3 Association / Stream Construction

Association asks whether detections that already exist can be connected safely:

- adjacent-frame boxes exist, but the mechanism cannot decide whether they are the same vehicle;
- short missing gaps break a plausible track;
- shape transitions or boundary contact make geometry-only linking unsafe;
- multi-object competition creates multiple plausible successors or predecessors;
- duplicate tracker hypotheses split the same possible target.

These are track association and fragment reconnect problems. Later fixes must state which layer they address.

## 9. Required Layering

The adjusted mechanism should use explicit layers:

| Layer | Meaning | Allowed interpretation |
| --- | --- | --- |
| Detection observation | A detector box on one optical frame | An observation, not an object identity |
| Track fragment | A local chain of observations under runtime-safe geometry/tracker rules | A continuity hypothesis over a limited span |
| Merge candidate | A possible relation between fragments | A review or uncertainty relation, not confirmed identity |
| Object hypothesis | A grouped optical hypothesis with primary and secondary observations | A diagnostic object-level carrier |
| Uncertain continuity field | A graph of observations, fragments, relations, and uncertainty states | A posthoc-diagnosis input field |
| Not identity truth | Mandatory interpretation of all above IDs | No tracker ID, fragment ID, or P4G ID is ground-truth identity |

The core design change is to make uncertainty a first-class intermediate representation rather than a side note. The downstream objective is to use that representation to identify safe global reconnect, merge, bridge, and competition-resolution rules.

## 10. Tracker ID And P4G Object ID Are Not Identity Truth

Tracker IDs are generated by runtime association rules and can be affected by occlusion, missed detections, duplicate boxes, crossing, boundary contact, and partial/full transitions. A tracker ID is a continuity hypothesis, not a proof that all attached observations belong to the same physical vehicle.

P4G object IDs aggregate tracker output, OTY1/OTY1a context, and secondary observations. They are useful as object-level handles, but they inherit upstream uncertainty. They must not be used as identity truth, final annotations, revised GT, final boxes, or clean paired objects.

Any downstream consumer must read the uncertainty fields with the ID. An ID without uncertainty state is not a valid mechanism output.

## 11. Target State Tags

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

These tags are not labels of truth. They are runtime-safe or review-safe evidence tags that explain why association is strong, weak, ambiguous, or blocked.

## 12. How To Judge Optical State Tags

State tags must be grounded in observable optical-stream evidence. They are not identity truth and must not be written from intuition alone.

`edge_contact` / `truncation`:

- bbox touches or stays close to the image boundary;
- the target enters from or exits through the image edge;
- the visible box is cut by the frame boundary;
- bbox area changes abruptly while boundary contact is present.

`partial_visible`:

- bbox size is clearly smaller than neighboring frames in a plausible track;
- the box appears to cover only a vehicle part;
- the observation remains in a plausible motion-continuity region.

`occlusion_like`:

- do not claim true physical occlusion;
- mark only occlusion-like evidence, such as short missing gaps, continuous positions before/after a gap, nearby overlapping boxes, or abrupt shape changes.

`partial_to_full_transition`:

- area or aspect ratio changes quickly;
- center motion and temporal order may still be continuous;
- the transition may explain a fragment boundary but does not confirm identity.

`multi_object_competition`:

- same-frame near-neighbor boxes are present;
- overlapping boxes or duplicate hypotheses are present;
- multiple candidate successors or predecessors exist;
- competing merge edges exist;
- crossing or ordering exchange is plausible.

`duplicate_overlap_detection`:

- same-frame boxes overlap strongly or have close centers;
- the boxes may be duplicate observations of the same vehicle;
- the boxes may also be neighboring-vehicle competition.

These tags are used to decide whether a breakpoint can be reconnected. They are not used to declare identity truth.

## 13. Fragment Handling

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

## 14. Multi-Object Competition Handling

Multi-object competition should be represented explicitly, not hidden inside tracker failure.

Required competition concepts:

- `crowded_frame`: a frame with multiple vehicle detections.
- `close_neighbor_pair`: two detections close enough to risk association confusion.
- `overlap_competition`: bbox overlap suggests duplicate or competing hypotheses.
- `possible_crossing`: target paths or fragments may cross or exchange order.
- `duplicate_hypothesis`: two tracks or fragments may represent the same physical target.
- `competing_merge_candidates`: multiple plausible fragment relations compete for the same source or target fragment.

The output should preserve competition structure until a safe global mechanism can resolve it. The point is not to preserve ambiguity forever; the point is to avoid collapsing competition into identity truth before the mechanism can justify same-target grouping.

## 15. Uncertainty-Aware Optical Hypothesis Field

The next intermediate mechanism output should be an uncertainty-aware optical hypothesis field, not a clean stream.

Minimum field semantics:

- keep detection observations with bbox, confidence, frame, and state tags;
- keep track fragments with continuity quality, length, gaps, and state summaries;
- keep merge candidate edges with relation state and rejection/ambiguity reasons;
- keep object hypotheses with primary observations, secondary observations, orphan observations, and review-required status;
- keep multi-object competition and duplicate-overlap indicators;
- keep readiness as a taxonomy: `schema_compatible`, `ready_with_uncertainty`, `mechanism_stable`, or blocked states.

The field is useful only if it describes uncertainty faithfully and makes breakpoints actionable. It is not successful merely because it emits object IDs. The objective is to use the field to determine which discontinuities can be safely reconnected by a global mechanism and which must remain review-required or blocked.

## 16. OTY2 Usage Contract

The uncertainty-aware optical hypothesis field can be used later in OTY2 only under these constraints:

- It can be used for posthoc diagnosis.
- It can enter support audit only as an uncertain hypothesis field, not as clean identity.
- It can enter temporal compatibility checks as a continuity hypothesis, not as verified pairing.
- It cannot become identity truth.
- It cannot directly enter the clean `215` pool.
- It cannot generate final annotations, revised GT, final boxes, selector/ranking outputs, or weighted-fusion rules.

If support or pairing diagnostics are later authorized, they must consume the uncertainty state instead of silently treating object IDs as clean objects.

## 17. Stop Condition Before Implementation

Do not implement mechanism changes until these questions are answered:

- Is the main GM_RM011 failure caused primarily by detector ability, detection postprocess, or association / stream construction?
- Does GM_RM019 show the same risk for the same reason, or does it fail through a different layer?
- Did GM_RM017 appear to pass only because the scene is simpler?
- In multi-box competition, which cases are likely same-vehicle duplicate or partial boxes, and which are neighboring-vehicle competition?
- Do state tags have observable optical evidence, rather than intuition-based labels?
- Which proposed changes are global mechanism corrections, and which are only scene-specific patches?

If these questions are unanswered, the next output should remain a design or audit clarification. It should not become a runtime implementation.

## 18. Minimal Implementation Route

This document does not implement the route. It only defines the design sequence.

Step 1: Unified cross-scene object-stream diagnosis table

- Summarize detection continuity, fragment counts, tracker outcomes, merge candidates, object-hypothesis readiness, review burden, and competition indicators across scenes.
- Include GM_RM011, GM_RM017, and GM_RM019 at minimum.

Step 2: State tags for detection / track / object hypothesis

- Add explicit state tags for complete/partial visibility, truncation, occlusion, edge contact, partial-to-full transition, short missing gap, multi-object competition, and duplicate/overlap detection.
- Keep tags descriptive and runtime-safe.
- Use tags to explain possible reconnect or bridge decisions, not to declare identity truth.

Step 3: Fragment relation graph

- Represent fragments and candidate relations as a graph.
- Label edges as `strong_continuity`, `weak_continuity`, `ambiguous_continuity`, or `blocked_continuity`.
- Preserve competing candidates rather than forcing a single winner.

Step 4: Uncertainty-aware object hypothesis field

- Emit object hypotheses with uncertainty state, secondary observations, orphan observations, relation provenance, and review-required fields.
- Do not call this a clean object stream unless a later mechanism proves stability.
- Treat the field as an intermediate output for finding correctable breakpoints.

Step 5: Decide whether to enter support/pairing diagnosis

- Enter only after cross-scene optical-stream uncertainty is represented.
- Enter only after deciding which breakpoints are globally correctable and which remain blocked.
- If entered, consume the field as uncertain posthoc diagnosis input.
- Do not promote GM_RM011 or any uncertain object into clean `215`.

## 19. Forbidden Moves

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

The mechanism is not fixed until it can explain uncertainty across scenes, identify which breakpoints can be safely corrected, and leave unresolved cases as review-required or blocked without pretending that review-required is a solution.
