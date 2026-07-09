# OTY2 WGV3.1 GM_RM011 T004 Controlled Interactive Loop Prototype

Date: 2026-07-09

## Scope

WGV3.1 is a controlled exploratory prototype of the WGV3.0 interactive optical-SAR mechanism inference loop. It uses committed reports and CSVs only. It does not run a new experiment, create media, add `outputs/`, score or rank candidates, tune thresholds, create final boxes, revise GT, produce SAR-ready annotation, emit runtime prediction, or claim identity truth.

The prototype goal is to show how optical evidence and SAR evidence can exchange constraints, expose contradictions, and update a mechanism explanation. It is not a SAR consumption protocol.

This is a controlled missing-factor exposure prototype, not a positive SAR-response closure example. T004 shows that the optical-to-geometry message can be formed, while the SAR side still lacks a traceable non-GT opened-stage response unit for the selected window.

Created companion tables:

- `reports/oty2/samples/oty2_wgv3_1_gm011_t004_interactive_message_trace_20260709.csv`
- `reports/oty2/samples/oty2_wgv3_1_gm011_t004_mechanism_state_updates_20260709.csv`
- `reports/oty2/samples/oty2_wgv3_1_gt_posthoc_validation_boundary_20260709.csv`

## 1. Why Choose T004 As The Primary Prototype Window?

Primary window: `GM_RM011_WGV14T004`.

T004 is chosen because WGV3.0 explicitly allows either `GM_RM011_WGV14T001` or `GM_RM011_WGV14T004`, but requires the choice to be justified. T004 is the better first controlled prototype for testing the transition from static factor graph to interactive loop because it already has a stronger WGV2 graph-instantiated mechanism relation than a purely fresh design target:

- WGV2.1 instantiates T004 with optical thread, optical behavior state, SAR morphology summary, geometry feasible-domain, boundary/competition, permission, and mechanism-relation nodes.
- WGV2.1 records two T004 relation decisions: `supports_vehicle_existence` and `insufficient_evidence`.
- WGV2.2 propagates T004 as `mapping_unresolved_blocks_consumption`, not as closure.
- WGV2.2 says T004 can support posthoc mechanism explanation and review constraint, but cannot support identity or annotation generation.

This makes T004 a good WGV3.1 target: it has enough inherited structure to test a feedback loop, but still exposes the missing factors that prevent SAR consumption.

T001 remains an auxiliary reference only. It is useful for near-field truncation and partial-vehicle message design, but it is not silently substituted as the primary window. M005 and M016 are boundary guardrails only. GM_RM017 weak/blocked examples are conservativeness references only.

## 2. What Existing Evidence Is Inherited?

| Source | Inheritance role | Used for | Boundary |
| --- | --- | --- | --- |
| `docs/OTY2_SESSION_START_HERE.md` | active boundary source | non-negotiable OTY2 scope, sample-pool semantics, physical-structure-first rule | no final annotation, no revised GT, no selector/ranking, no runtime prediction |
| `docs/OTY2_WGV3_INTERACTIVE_OPTICAL_SAR_MECHANISM_INFERENCE_DESIGN.md` | active design source | WGV3 loop stages, message permissions, state vocabulary | GT validates only after mechanism proposal |
| `reports/oty2/oty2_wgv3_0_interactive_optical_sar_mechanism_inference_design_20260709.md` | active design summary | compact WGV3.0 rationale and WGV3.1 route | no weighted fusion or identity truth |
| `reports/oty2/samples/oty2_wgv3_0_interactive_loop_state_plan_20260709.csv` | active schema seed | loop-stage vocabulary for the WGV3.1 trace | pre-GT negative contrast remains non-GT |
| `docs/OTY2_WGV2_FACTOR_GRAPH_PHASE_CLOSEOUT_AND_REPOSITORY_INHERITANCE_20260709.md` | active inheritance rule | historical source classification and missing-factor priorities | repository is not a flat approved-facts list |
| `docs/OTY2_CROSS_MODAL_FACTOR_IDEA_BANK.md` | active idea/admission source | factor lifecycle, candidate factors, joint-factor gates | divergent discovery, strict admission |
| `docs/OTY2_CROSS_MODAL_MECHANISM_FACTOR_GRAPH_DESIGN.md` | active schema source | graph levels, node/factor types, relation outcomes | graph is not annotation-producing |
| `reports/oty2/oty2_wgv2_1_small_window_factor_graph_instantiation_20260709.md` | active evidence summary | T004 graph-instantiated role and conservative result | T004 meaningful but mapping unresolved |
| `reports/oty2/oty2_wgv2_2_factor_graph_constraint_propagation_and_missing_factor_audit_20260709.md` | active missing-factor source | propagated T004 state and missing factors | missing factors block SAR consumption, not posthoc explanation |
| `reports/oty2/oty2_wgv2_3_factor_idea_bank_gt_validation_boundary_and_joint_factor_admission_rules_20260709.md` | active admission-boundary source | GT use, negative contrast, forbidden shortcuts | GT cannot define runtime factors |
| `reports/oty2/oty2_wgv1_8_gm011_optical_behavior_to_sar_gt_local_mechanism_audit_20260709.md` | mixed source: optical active evidence plus reserved posthoc reference | T004 optical behavior; later validation source inventory | SAR reference material stays posthoc-only |
| `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md` | archived correction / guardrail | atom/part/shell hierarchy and temporal-drift caution | no weighted fusion or baby-car shortcut |
| `docs/oty2_gt_local_energy_field_atlas_correction_archive.md` | archived correction / failed-path warning | prevents support-wide panel or component-box misuse | failed atlas is not evidence for vehicle shell grammar |
| `docs/oty2_gt_support_failure_concept_correction_archive.md` | archived correction / guardrail | separates support miss, GT quality, and vehicle-scale structure | support is not final box |

The prototype also reads the committed WGV2/WGV1.8 CSVs listed in the companion tables. Those rows are inherited with provenance labels instead of being treated as a single truth table.

## 3. What Optical Message Is Sent?

For `GM_RM011_WGV14T004`, the optical message is:

- `time_tube`: optical frames `151-166` within the broader WGV1.8 `WGV18W003` segment `135-166`.
- `optical_thread_strength`: accepted optical window / optical identity constraint inside the optical graph, but `pre_sar_only`.
- `target_state_tags`: `stable_visible_vehicle`, `edge_contact`, `partial_vehicle`, with upstream `occlusion` and `subject_transition` context.
- `boundary_and_competition_tags`: `multi_vehicle_competition`, `local_competition`, and subject-transition context.
- `visible_unboxed_or_missing_gap_context`: no direct T004 visible-unboxed claim is used; the broader WGV18W003 context warns that partial visibility and subject transition can confuse support.
- `allowed_review_constraint`: prioritize SAR review of the T004 temporal neighborhood and vehicle-scale morphology vocabulary after an SAR evidence stage is explicitly opened.

Forbidden optical message content:

- no SAR identity truth;
- no final box;
- no GT-derived location;
- no annotation permission;
- no score, rank, or candidate target;
- no one-to-one optical-SAR mapping claim.

## 4. What Geometry/Time Feasible Field Is Proposed?

The geometry/time field is a feasible review field only.

It may carry:

- the T004 optical time neighborhood;
- the fact that WGV1.8 traces a broad SAR reference range `281-335` for `WGV18W003`;
- the missing direct GM_RM011 azimuth/fan-polar source;
- the missing precise optical-to-SAR temporal alignment;
- the fact that no offset band or selected SAR location is available.

It may not carry:

- a selected SAR box;
- a final candidate;
- a GT-derived sector center;
- a ranking or score;
- a runtime prediction.

The correct WGV3.1 state is therefore `missing_factor_exposed`: the loop can propose review constraints, but cannot close geometry. `missing_gm011_azimuth_source` and `missing_precise_temporal_alignment` remain explicit blockers.

## 5. What SAR Response Is Allowed?

During the loop, SAR may answer only with runtime-safe or explicitly opened-SAR-stage morphology vocabulary.

Allowed SAR response families:

- vehicle-scale structure support;
- side ridge;
- endpoint or corner hotspot;
- weak opposite-side return;
- shell contour;
- SAR temporal drift or jump;
- background or static-reflector risk;
- insufficient evidence.

For T004, the controlled prototype does not construct the SAR response from posthoc reference material. No committed opened SAR-stage T004 evidence unit has been identified in the current source stack. The pre-validation SAR response is therefore:

- allowed vocabulary request only: if a later SAR evidence stage is explicitly opened, it may inspect vehicle-scale shell, corner hotspot, side ridge, weak opposite-side return, temporal drift, and background/static risk;
- current loop response: insufficient evidence for SAR-side mechanism closure;
- SAR temporal drift chain is missing;
- non-GT background/static contrast is not yet available;
- direct mapping to T004 is unresolved;
- competitor ambiguity remains active.

Reserved SAR reference summaries are postponed to the GT posthoc validation section and do not construct this SAR response.

This SAR response cannot become final annotation, identity truth, SAR-ready output, a selected component, or a runtime prior.

## 6. What Feedback Does SAR Send Back To The Optical Hypothesis?

The SAR-side feedback to the optical hypothesis is conservative:

- the optical hypothesis remains plausible as a review constraint, because T004 has accepted optical continuity and vehicle-scale SAR vocabulary exists in inherited summaries;
- mapping remains unresolved, so the optical hypothesis cannot be promoted into a cross-modal identity relation;
- edge contact and partial visibility remain useful state tags, but they request support-shift or geometry review rather than final localization;
- SAR morphology is too weak as a loop response unless an explicit SAR evidence stage produces thread-local observations;
- SAR temporal drift chain is missing;
- non-target negative contrast is missing;
- competitor ambiguity from the mid-window context remains active;
- boundary guardrails from M005/M016 remain preserved and must not be relaxed by one cue.

## 7. What Mechanism State Transition Occurs?

The WGV3.1 T004 loop starts from the WGV2.2 static state:

```text
mapping_unresolved_blocks_consumption
```

After the interactive message exchange, the conservative state becomes:

```text
mechanism_weak_but_plausible
missing_factor_exposed
insufficient_evidence
```

Auxiliary guardrail states also remain active:

```text
boundary_preserved
identity_risk_blocked
```

The loop does not reach `mechanism_supported_posthoc_only` as a closed result, because the pre-GT SAR response lacks a traceable SAR temporal drift chain and non-GT negative contrast. It also does not reach `non_target_rejected`, because non-target rejection has not been demonstrated.

## 8. What Contradictions Or Missing Factors Are Exposed?

The controlled loop exposes these missing factors:

- `missing_gm011_azimuth_source`: T004 lacks a direct runtime-safe GM_RM011 azimuth/fan-polar source.
- `missing_precise_temporal_alignment`: T004 lacks a unique optical-to-SAR temporal offset or thread-level frame mapping.
- `missing_sar_temporal_drift_chain`: no opened-stage SAR-internal drift chain is available for T004.
- `missing_non_target_negative_contrast`: no non-GT background/road-edge/static-reflector/competitor contrast is available in the loop.
- `missing_boundary_sar_evidence`: M005/M016 remain boundary guardrails and do not have enough boundary-specific SAR evidence to relax.
- `missing_competitor_separation_evidence`: T004 inherits multi-vehicle and subject-transition risk from WGV18W003.
- `missing_runtime_safe_geometry_source`: geometry remains a review field, not a selected domain.

The main contradiction is useful: T004 has accepted optical continuity and posthoc-readable vehicle vocabulary, but the permission, geometry, temporal, and competitor gates prevent it from becoming a mapped SAR relation.

## 9. How Is GT Used Posthoc?

GT is used only after the loop has proposed the state above. It is not used to construct the optical message, geometry field, SAR response, factor value, threshold, candidate, score, rank, runtime prior, final annotation, or identity claim.

For T004, posthoc validation may ask:

- positive GT-local fit question: if the proposed T004 mechanism is plausible, do the reserved SAR reference rows show vehicle-scale fit such as shell composition, corner hotspot, side ridge, or coherent body-scale structure?
- negative outside-GT / non-target contrast question: do nearby background, road-edge, static-reflector, guardrail-like, competitor, or outside-GT regions fail the same vehicle-scale mechanism?
- leakage-control question: was the mechanism proposed from optical state, graph nodes, permission gates, and opened-stage SAR vocabulary before GT was consulted?

Available posthoc evidence:

- WGV1.8 `WGV18W003` maps T004 context to SAR range `281-335` with `prior_report_traceable` status.
- The reserved SAR reference row reports patterns such as `enclosed_shell`, `corner_hotspot`, `discontinuous_edges`, `side_ridge`, and `weak_boundary`, with quality caveats.

Missing validation evidence:

- direct T004 GT-local exemplar PNG rows are not available in WGV1.8;
- no precise T004 optical-to-SAR alignment is selected;
- non-target contrast is not closed;
- competitor separation is unresolved.

Allowed posthoc conclusion:

```text
T004 remains a plausible mechanism-construction and repair-planning window.
```

Forbidden conclusions:

- final annotation;
- revised GT;
- SAR-ready annotation;
- selected SAR box;
- selector/ranking result;
- runtime prediction;
- identity truth;
- GT-defined geometry, threshold, factor value, or candidate.

## 10. Does The Interactive Loop Add Value Beyond Static Factor Tables?

Yes. The static WGV2 tables already record T004 as useful but unresolved. The WGV3.1 loop adds value by showing how each unresolved layer feeds back into the next repair question:

- optical evidence does not just sit in a table; it sends a constrained review message;
- geometry does not become a box; it returns missing azimuth and time-alignment requirements;
- SAR morphology does not become proof; it responds with weak vocabulary or insufficiency;
- background and competitor risk remain active instead of being averaged away;
- GT validation is delayed until after a mechanism state is proposed;
- the final output is a repair direction, not a selection.

The loop makes the missing-factor path more concrete: recover GM_RM011 azimuth/time feasibility, then design SAR temporal drift and non-target contrast checks, while preserving M005/M016 boundaries.

## 11. What Should WGV3.2 Do Next?

WGV3.2 should choose one small route rather than broad CSV expansion:

1. GM_RM011 azimuth-source recovery / runtime-safe feasible-field design for T004/T001.
2. SAR temporal drift-chain design for T004/T001, with non-target negative contrast planned from the start.

If the next route focuses on boundary risk instead, use M005 or M016 as a boundary-SAR evidence design, not as a bridge or identity-relaxation task.

## Boundary Summary

WGV3.1 produces a controlled mechanism-loop prototype only. It does not create new visual evidence, new experiment outputs, final boxes, revised GT, SAR-ready annotation, selector/ranking output, runtime prediction, identity truth, or GT-guided algorithm construction.
