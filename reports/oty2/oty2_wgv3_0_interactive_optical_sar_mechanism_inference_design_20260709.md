# OTY2 WGV3.0 Interactive Optical-SAR Mechanism Inference Design Report

Date: 2026-07-09

## Scope

WGV3.0 is design-only. It defines an interactive optical-SAR mechanism inference route after the WGV2 factor-graph phase. It does not run experiments, expand broad tables, create candidates, score or rank candidates, tune thresholds, generate final boxes, revise GT, create SAR-ready annotation, produce runtime predictions, or claim identity truth.

Files created:

- `docs/OTY2_WGV3_INTERACTIVE_OPTICAL_SAR_MECHANISM_INFERENCE_DESIGN.md`
- `reports/oty2/samples/oty2_wgv3_0_interactive_loop_state_plan_20260709.csv`

## 1. Why Static Factor Tables Are Insufficient

WGV2 closed the static representation phase: the permission-gated factor graph can encode optical evidence, SAR posthoc evidence, geometry feasibility, boundary and competition, evidence permission, and mechanism outcomes.

The next problem is not another schema or broad table. The unresolved mechanism question is how optical and SAR evidence constrain each other through repeated feedback. Static ledgers can record a missing azimuth source, weak temporal alignment, absent non-target contrast, or preserved boundary, but they do not express how a SAR contradiction should revise the optical hypothesis or expose a missing factor.

WGV3.0 therefore shifts the route from static factor graph to interactive inference loop.

## 2. Interactive Loop

The loop is:

```text
optical hypothesis
  -> geometry/time feasible field
  -> SAR morphology response
  -> SAR temporal/background/negative evidence
  -> mechanism factor update
  -> feedback to optical hypothesis
  -> convergence or contradiction
```

The loop does not optimize a score. It exchanges constraints. A good result can be a supported posthoc mechanism, a preserved boundary, a rejected background reflector, an exposed missing temporal drift chain, or an explicit contradiction.

The optimal result is the least-contradictory, physically interpretable mechanism explanation under evidence-permission constraints, not a best box or best identity.

## 3. Optical-To-SAR Messages

Optical can send constrained review information:

- time tube;
- optical thread strength;
- target state tags;
- boundary and competition tags;
- visible-unboxed gap;
- short missing gap;
- allowed search or review constraint.

Optical cannot send SAR identity truth, final box, GT-derived location, annotation permission, selector target, score or rank target, one-to-one mapping claim, or permission to relax preserved boundaries.

## 4. SAR-To-Optical Feedback

SAR can send back constrained mechanism evidence:

- vehicle-scale structure support;
- side-ridge, endpoint-hotspot, or weak-opposite-side evidence;
- SAR temporal drift or jump;
- background or static-reflector risk;
- non-target negative contrast;
- boundary support or contradiction;
- insufficient evidence.

SAR cannot send final identity, final annotation, GT-leaked runtime prior, revised GT, selected candidate, selector/ranking result, weak-thread upgrade from posthoc overlap alone, or boundary relaxation from one cue alone.

## 5. GT Validation Boundary

GT is used only after a runtime-safe or posthoc-readable mechanism has been proposed. GT validates or falsifies the mechanism; it cannot define the factor, threshold, candidate, score, rank, runtime prior, or annotation.

Every GT use must include:

- positive GT-local fit analysis;
- negative outside-GT or non-target contrast analysis;
- leakage-control statement.

GT overlap alone is not mechanism proof. A bright point inside GT is not enough. A GT-positive example without negative contrast remains insufficient or missing-factor-exposed.

## 6. Minimal Viable Loop

The minimal WGV3.1 design target should use one GM_RM011 window, not broad CSV expansion.

Candidate windows:

- `GM_RM011_WGV14T001` or `GM_RM011_WGV14T004` for positive mechanism construction.
- `GM_RM011_M005` or `GM_RM011_M016` for boundary preservation.
- one nearby non-target or background comparison region if available from existing reports.

The minimal loop should test:

- whether optical state narrows SAR review space;
- whether SAR responds with vehicle-scale structure rather than isolated bright points;
- whether SAR temporal drift supports continuity without identity declaration;
- whether non-target contrast rejects background;
- whether the loop exposes a missing factor instead of forcing closure.

## 7. Why This Is Still Not Final Annotation Or SAR-Ready

WGV3.0 is still posthoc mechanism design. It preserves the WGV2 boundary:

- no final boxes;
- no GT boxes;
- no revised GT;
- no revised annotation;
- no SAR-ready annotation;
- no selector/ranking;
- no runtime prediction;
- no identity truth;
- no weighted heuristic fusion;
- no GT leakage into runtime construction.

The loop may produce mechanism states such as `mechanism_supported_posthoc_only`, `mechanism_weak_but_plausible`, `mechanism_contradicted`, `boundary_preserved`, `identity_risk_blocked`, `missing_factor_exposed`, `non_target_rejected`, `background_risk_detected`, or `insufficient_evidence`.

These states are explanation and repair outcomes. They are not annotation permissions.

## Conclusion

WGV3.0 turns WGV2's permission-gated factor graph into an interactive mechanism inference route. Optical evidence sends constrained hypotheses. SAR evidence sends constrained feedback. GT validates or falsifies only after the mechanism is proposed. Contradictions and missing factors remain visible instead of being hidden inside weighted fusion or candidate ranking.

The next task should be WGV3.1 minimal interactive loop prototype design for one GM_RM011 window: one optical message, one SAR response, one feedback update, and one GT posthoc validation with both positive fit and negative contrast.
