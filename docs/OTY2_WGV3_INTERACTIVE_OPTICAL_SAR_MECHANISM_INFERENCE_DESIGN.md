# OTY2 WGV3.0 Interactive Optical-SAR Mechanism Inference Design

Date: 2026-07-09

## Status

WGV3.0 is a design-only proposal for an interactive optical-SAR mechanism inference route.

It does not run experiments, expand broad tables, create candidate boxes, score or rank candidates, tune thresholds, generate final boxes, revise GT, produce SAR-ready annotation, produce runtime predictions, or claim identity truth.

The target is not final annotation. The target is a physically interpretable posthoc mechanism explanation that preserves evidence permission, contradiction, boundary risk, and missing-factor exposure.

## 1. Why WGV3.0 Is Needed

WGV2 defined and instantiated a permission-gated cross-modal factor graph. It proved that optical state, geometry feasibility, SAR posthoc morphology, temporal drift, boundary factors, competitor risk, and evidence permission can be represented without collapsing into one-to-one optical-SAR mapping or weighted selector logic.

That phase is closed. The next step should not be another static schema, larger ledger, or table expansion. Static factor tables can record what evidence exists and what promotion is forbidden, but they do not by themselves explain how evidence streams revise each other over time.

WGV3.0 is needed because the unresolved mechanism questions are interactive:

- an optical hypothesis can narrow what SAR should review, but cannot prove SAR identity;
- a SAR morphology response can support or contradict a physical vehicle explanation, but cannot produce final annotation;
- SAR temporal or background evidence can reveal that the optical hypothesis was too broad, too narrow, shifted, competitor-contaminated, or unsupported;
- contradiction should be preserved as mechanism information, not hidden inside a score;
- missing factors should be exposed explicitly rather than patched by adding more weak cues.

The WGV3.0 route therefore moves from static factor-graph description to interactive mechanism inference. Optical evidence and SAR evidence repeatedly constrain, revise, and challenge each other until the loop reaches a conservative mechanism state: supported posthoc-only, weak but plausible, contradicted, boundary-preserved, identity-risk-blocked, missing-factor-exposed, non-target-rejected, background-risk-detected, or insufficient evidence.

The result is not SAR-ready. It is not a candidate-selection protocol. It is a route for explaining what kind of mechanism can be read after evidence permissions are respected.

## 2. Core Idea

The WGV3.0 loop is:

```text
optical hypothesis
  -> geometry/time feasible field
  -> SAR morphology response
  -> SAR temporal/background/negative evidence
  -> mechanism factor update
  -> feedback to optical hypothesis
  -> convergence or contradiction
```

The optical side proposes a hypothesis with permitted optical evidence: time tube, thread strength, state tags, boundary or competition tags, visible-unboxed gap, short missing gap, and allowed search or review constraints. The geometry/time layer converts that hypothesis into a feasible field, not a selected SAR box. The SAR side then reports morphology, temporal drift, background risk, negative contrast, or insufficient evidence. The mechanism layer updates the graph state and sends feedback to the optical hypothesis.

The optimal result is not a best box or best identity.

The optimal result is the least-contradictory, physically interpretable mechanism explanation under evidence-permission constraints.

This distinction is central. A loop may succeed by preserving a boundary, rejecting a background reflector, exposing a missing azimuth source, or refusing an identity upgrade. Those outcomes are useful because they improve the mechanism explanation without producing annotation.

## 3. Optical-To-SAR Message

An optical-to-SAR message is a constrained review request. It describes what the optical evidence can safely ask SAR to inspect.

Optical can send:

- `time_tube`: a bounded time interval or frame-local review tube derived from optical continuity and metadata.
- `optical_thread_strength`: accepted, weak, search-hint, context-only, boundary-preserved, or blocked thread status.
- `target_state_tags`: truncation, edge contact, partial vehicle, occlusion-like gap, visible-unboxed evidence, subject transition, dropout, or primary-box repair context.
- `boundary_and_competition_tags`: same-color competitor, multi-vehicle competition, preserved different-vehicle boundary, bridge risk, or context-only relation.
- `visible_unboxed_gap`: optical evidence that a vehicle may be visible outside the primary box, usable only as existence-support context.
- `short_missing_gap`: a short optical continuity gap that may ask for temporal compatibility review, without creating identity truth.
- `allowed_search_or_review_constraint`: a time, geometry, state, or review-priority constraint that narrows inspection but remains below selection.

Optical cannot send:

- SAR identity truth.
- A final box.
- A GT-derived location.
- Annotation permission.
- A selector target.
- A score or rank target.
- A one-to-one optical-SAR correspondence claim.
- A permission to relax M005, M016, or other preserved boundaries.

The optical message is therefore a hypothesis field. It can say where and why SAR should look, what optical uncertainty should be respected, and what boundary risk must remain visible. It cannot say what the SAR target is.

## 4. SAR-To-Optical Feedback Message

A SAR-to-optical feedback message is a constrained response. It describes what SAR evidence can safely report back to the optical hypothesis without becoming final localization.

SAR can send back:

- `vehicle_scale_structure_support`: evidence that energy is organized at vehicle scale rather than as an isolated atom or tiny component.
- `side_ridge_endpoint_hotspot_weak_opposite_side_evidence`: morphology vocabulary such as dominant side ridge, endpoint or corner hotspot, weak opposite-side return, discontinuous shell contour, or long/short-axis relation.
- `sar_temporal_drift_or_jump`: non-jump persistence, gradual drift, ambiguous drift, missing drift, or jump-like contradiction.
- `background_static_reflector_risk`: fixed bright point, road edge, guardrail-like ridge, building edge, texture clutter, or scene-static response.
- `non_target_negative_contrast`: nearby non-target, outside-GT, background, road-edge, static-reflector, guardrail, or competitor region fails the same vehicle-scale mechanism.
- `boundary_support_or_contradiction`: SAR evidence preserves a boundary, exposes competitor ambiguity, or contradicts an optical bridge.
- `insufficient_evidence`: SAR image content, temporal chain, geometry, or negative examples are not enough to support the mechanism.

SAR cannot send back:

- final identity;
- final annotation;
- GT-leaked runtime prior;
- final or revised GT;
- selected candidate box;
- selector/ranking result;
- weak-thread upgrade from posthoc overlap alone;
- boundary relaxation from one SAR cue alone.

SAR feedback may strengthen, weaken, preserve, or contradict the optical hypothesis. It does not close identity by itself. A SAR bright point is not a vehicle. A posthoc overlap is not a runtime prior. Vehicle-scale morphology must remain tied to physical interpretation and negative contrast.

## 5. GT Posthoc Validation Boundary

GT is used only after a runtime-safe or posthoc-readable mechanism is proposed.

GT validates or falsifies the mechanism. GT cannot define the factor. GT cannot define thresholds. GT cannot select candidates. GT cannot provide runtime azimuth/range centers, final locations, scores, ranks, or annotation permission.

Every GT use must include:

- `positive_gt_local_fit_analysis`: why the proposed mechanism fits inside the GT-local vehicle region, including vehicle-scale structure, ridge or endpoint evidence, weak opposite-side return, shell contour, temporal compatibility, or GT-quality caveat.
- `negative_outside_gt_or_non_target_contrast_analysis`: why nearby outside-GT, background, road-edge, static-reflector, guardrail, competitor, or non-target regions do not satisfy the same mechanism.
- `leakage_control_statement`: which evidence was used to propose the mechanism before GT, how GT was used only for validation or falsification, and what must not be copied into runtime construction.

If a GT-positive example lacks nearby negative contrast, WGV3.0 records the state as missing-factor-exposed or insufficient-evidence, not as mechanism closure. If the only support is GT overlap or an isolated bright point, the mechanism is not closed.

## 6. Interaction States

After each loop, WGV3.0 records one or more conservative interaction states:

- `mechanism_supported_posthoc_only`: optical hypothesis and SAR morphology are physically compatible after permission checks, but the support remains posthoc and non-annotation.
- `mechanism_weak_but_plausible`: evidence suggests a mechanism but lacks temporal chain, negative contrast, boundary evidence, or mapping closure.
- `mechanism_contradicted`: SAR morphology, SAR temporal behavior, geometry, negative contrast, or boundary evidence conflicts with the optical hypothesis.
- `boundary_preserved`: a different-vehicle boundary, competitor boundary, or context-only edge remains active and blocks bridging.
- `identity_risk_blocked`: evidence may be useful for review but is unsafe for same-identity interpretation.
- `missing_factor_exposed`: the loop identifies a missing azimuth source, temporal alignment, SAR drift chain, non-target contrast, competitor separation, boundary evidence, or geometry source.
- `non_target_rejected`: negative contrast rejects background, static reflector, road edge, guardrail, point-like object, or competitor explanation for the proposed mechanism.
- `background_risk_detected`: SAR evidence is consistent with background, static, road-edge, guardrail, texture, or non-vehicle clutter risk.
- `insufficient_evidence`: evidence permission, image content, temporal support, geometry, or contrast examples are not enough to decide.

These are mechanism states, not labels. Multiple states can coexist. For example, a loop can be `mechanism_weak_but_plausible` and `missing_factor_exposed`, or `boundary_preserved` and `identity_risk_blocked`.

## 7. Minimal Viable Loop

WGV3.0 proposes one minimal loop on GM_RM011, but does not run it.

Candidate windows:

- `GM_RM011_WGV14T001` or `GM_RM011_WGV14T004` for positive mechanism construction.
- `GM_RM011_M005` or `GM_RM011_M016` for boundary preservation.
- one nearby non-target or background comparison region, if available from existing reports.

The minimal loop should start with one window, one optical message, one SAR response, one mechanism update, and one GT posthoc validation package. It should not begin with broad CSV expansion.

The loop should test:

- Can optical state narrow the SAR review space?
- Can SAR morphology respond with vehicle-scale structure rather than isolated bright points?
- Can SAR temporal drift support continuity without declaring identity?
- Can non-target contrast reject background?
- Does the loop expose a missing factor rather than forcing closure?

A minimal positive construction route could use `GM_RM011_WGV14T001`:

1. Optical sends `time_tube`, `accepted_or_strong_thread`, `near_field_truncation`, `partial_vehicle`, `edge_contact`, and `allowed_review_constraint`.
2. Geometry/time converts that message into a feasible review field, not a box.
3. SAR replies with GT-local or opened-SAR-stage morphology vocabulary such as vehicle-scale ridge, endpoint hotspot, weak opposite-side return, shell contour, temporal non-jump, ambiguity, or insufficient evidence.
4. SAR adds negative contrast against a nearby non-target or background region if available.
5. Mechanism update records supported posthoc-only, weak-but-plausible, contradicted, missing-factor-exposed, or background-risk-detected.
6. Feedback tells the optical hypothesis whether truncation expansion, temporal alignment, SAR drift chain, non-target contrast, or boundary evidence is missing.

A minimal boundary route could use `GM_RM011_M005` or `GM_RM011_M016`:

1. Optical sends preserved boundary and same-color competitor tags.
2. SAR may report ambiguous structure, competitor-side support, boundary support, or insufficient boundary-specific evidence.
3. The loop must preserve the boundary unless independent boundary evidence exists under a later protocol.
4. GT posthoc validation may check local fit and negative contrast, but cannot relax the boundary by overlap alone.

This minimal loop is a design target for WGV3.1. WGV3.0 creates no prototype output.

## 8. How This Differs From Weighted Fusion

Weighted fusion adds cues.

Interactive mechanism inference exchanges constraints.

Weighted fusion hides contradictions by converting evidence to a single combined value.

Interactive mechanism inference preserves contradictions as graph state, feedback, and missing-factor diagnosis.

Weighted fusion tends toward selection.

Interactive mechanism inference tends toward explanation and repair.

Weighted fusion can accidentally make several weak cues look strong. Interactive inference asks whether the cues are physically associated, independently permitted, negatively contrasted, boundary-safe, and leakage-controlled.

The WGV3.0 loop can produce a useful result even when it does not select anything. A preserved boundary, rejected background reflector, exposed missing temporal chain, or blocked identity risk is a valid mechanism inference outcome.

## 9. How To Use Old Repository Content

Use old correct reports, failed reports, archived corrections, and visual review packs as mechanism-evolution history.

Failed or corrected work can contribute forbidden shortcuts, missing factors, and negative evidence. For example:

- support-wide or component-box failures warn against reading tiny components as vehicles;
- GT-local correction archives define how to keep GT as posthoc validation rather than runtime construction;
- factor graph ledgers preserve permission and boundary states;
- visual review packs preserve optical behavior vocabulary but not identity truth;
- failed or superseded reports can expose why weighted fusion, flat support search, or posthoc overlap is insufficient.

Do not treat the repository as a flat approved-facts list. Every inherited item must be checked for scope, provenance, correction status, allowed use, and leakage risk.

The repository should be mined historically:

- correct active reports can provide current mechanism vocabulary;
- archived corrections can provide guardrails;
- failed reports can provide anti-patterns and negative examples;
- visual review packs can provide human-readable optical behavior context;
- SAR GT-local morphology reports can provide posthoc validation vocabulary;
- support-failure audits can provide missing-factor feedback.

No old artifact should be used to produce final boxes, revised GT, SAR-ready annotation, selector/ranking output, runtime prediction, or identity truth.

## 10. Next Implementation Route

Do not implement WGV3.0 now.

The next task should be:

```text
WGV3.1 minimal interactive loop prototype design for one GM_RM011 window.
```

WGV3.1 should not start with broad CSV expansion. It should start with:

- one window;
- one optical message;
- one SAR response;
- one feedback update;
- one GT posthoc validation with positive and negative contrast.

The likely first choice is `GM_RM011_WGV14T001` for positive mechanism construction, with `GM_RM011_M005` or `GM_RM011_M016` reserved as a separate boundary-preservation route.

WGV3.1 should remain design/prototype planning until explicitly authorized to run. It should not produce final boxes, revised GT, SAR-ready annotations, selector/ranking artifacts, runtime predictions, or identity-truth claims.

## Validation Boundary For WGV3.0

A valid WGV3.0 delivery should pass:

- `git diff --check`;
- parse check for the optional small CSV if created;
- forbidden-artifact scan over changed files showing no `outputs/` additions, no media additions, no final boxes, no revised GT, no SAR-ready annotations, no selector/ranking artifacts, no runtime prediction artifacts, no identity-truth claims, and no GT leakage into runtime construction;
- `git status --short`.

WGV3.0 should remain uncommitted until a later explicit commit instruction.
