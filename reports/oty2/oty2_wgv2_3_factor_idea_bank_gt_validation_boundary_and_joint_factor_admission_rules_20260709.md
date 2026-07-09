# OTY2 WGV2.3 Factor Idea Bank, GT Validation Boundary, And Joint-Factor Admission Rules

Date: 2026-07-09

## Scope

WGV2.3 is design-only. It creates an idea bank, candidate-factor lifecycle ledger, joint-factor admission rules, GT validation boundary rules, and forbidden shortcut registry. It does not run new experiments, instantiate graph windows, create candidate boxes, score candidates, rank candidates, tune thresholds, produce final boxes, produce GT boxes, revise annotations, create SAR-ready annotation, or claim identity truth.

Files created:

- `docs/OTY2_CROSS_MODAL_FACTOR_IDEA_BANK.md`
- `reports/oty2/samples/oty2_wgv2_3_factor_candidate_evolution_ledger_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_3_joint_factor_admission_rules_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_3_gt_validation_boundary_rules_20260709.csv`
- `reports/oty2/samples/oty2_wgv2_3_forbidden_shortcut_registry_20260709.csv`

## 1. How Missing-Factor Discovery Stays Divergent Without Becoming Heuristic Stacking

Discovery stays divergent by allowing candidate factors to come from optical behavior, SAR morphology, geometry, temporal continuity, imaging physics, failure cases, non-vehicle rejection, boundary/competitor evidence, permission analysis, and cross-scene comparison.

It avoids heuristic stacking by separating idea collection from admission. A candidate factor is not accepted because it correlates with GT, helps a desired case, or adds another weak cue to a sum. It must have runtime-safe observable evidence, physical interpretation, verifiable relation, counterexample conditions, evidence permission, and leakage risk control.

The key rule is:

```text
divergent discovery -> strict admission
```

not:

```text
more weak cues -> stronger truth
```

## 2. Lifecycle From Idea Factor To Admitted Graph Factor

The lifecycle is:

1. `idea_seed`
2. `candidate_factor`
3. `runtime_observable_factor`
4. `physically_interpretable_factor`
5. `gt_validated_posthoc_factor`
6. `negative_contrast_checked_factor`
7. `admitted_graph_factor`
8. `rejected_or_deferred_factor`
9. `blocked_by_permission`

Promotion from `candidate_factor` to `admitted_graph_factor` requires all of the following:

- runtime-observable evidence not derived from GT;
- physical interpretation;
- at least one verification path;
- counterexample conditions;
- positive GT-local fit and negative non-target contrast if GT is used;
- evidence permission proof that GT did not leak into runtime construction.

Any factor that is informative only because GT, manual labels, final annotation, selector output, or revised GT created it is blocked by permission or deferred.

## 3. Why GT Is A Posthoc Validation Anchor Rather Than Algorithm Construction Input

GT is allowed to validate or falsify a mechanism that was proposed without GT. It may anchor a local SAR crop, audit GT quality, describe GT-local morphology, test support miss, or compare positive and negative regions.

GT cannot define the mechanism. It cannot provide runtime factor values, runtime thresholds, candidate generation, score targets, ranking labels, azimuth/range centers, annotation logic, final boxes, or identity truth.

This distinction preserves the runtime construction layer. If a factor cannot be described from runtime-safe inputs before GT is read, it is not a runtime-safe factor. It may still be useful as posthoc explanation, but it cannot be admitted as runtime construction logic.

## 4. Why GT Requires Both Positive Fit And Negative Contrast

GT-local positive fit answers why a proposed mechanism makes sense inside the GT-local vehicle region. That is necessary but not sufficient.

Negative non-target contrast answers why the same mechanism does not fit nearby outside-GT, background, road-edge, guardrail, static-reflector, competing-vehicle, or other non-target regions. Without this check, a GT-positive example can be a coincidental bright point, road edge, baby-car component, static reflector, or competitor cue.

Therefore:

- a GT-positive example without nearby negative contrast is not enough;
- GT overlap without vehicle-scale morphology is not enough;
- a SAR bright point inside GT is not enough;
- the mechanism must explain why GT-local structure is vehicle-like and why non-target structures should be rejected.

## 5. Why Joint Factors Must Be Stricter Than Single Candidate Factors

Joint factors combine multiple evidence streams. That makes them more useful but also more dangerous. A joint factor can hide leakage, double count one cue, override a boundary, or turn several weak cues into an unsupported identity claim.

For that reason, joint factors must be stricter than single candidate factors. They must show physical association among components, independent evidence, counterexamples, boundary/competition handling, and evidence permission. They must also prove that posthoc validation evidence did not become runtime prior logic.

## 6. Gates A Joint Factor Must Pass

Every joint factor must pass:

- runtime-observable gate;
- physical plausibility gate;
- independent evidence gate;
- GT-positive validation gate if GT is used;
- non-target negative contrast gate;
- counterexample gate;
- boundary/competition gate;
- evidence-permission gate;
- cross-window or cross-scene stability gate when applicable.

If any gate fails, the rule stays as `candidate_factor`, `rejected_or_deferred_factor`, or `blocked_by_permission`.

## 7. Most Important Current Candidate Factors

The most important WGV2.3 candidate factors are:

- near-field truncation factor;
- edge-contact expansion factor;
- visible-unboxed existence support factor;
- same-color competitor risk factor;
- SAR side-ridge persistence factor;
- endpoint hotspot stability factor;
- weak opposite-side return factor;
- vehicle-scale shell closure factor;
- background static reflector rejection factor;
- non-jump SAR temporal drift factor;
- boundary preservation factor;
- permission blocking factor;
- GT-positive / non-target-negative contrast factor;
- azimuth/range feasible domain factor;
- support failure feedback factor;
- optical short-gap continuity factor;
- cross-scene generalization factor;
- SAR imaging geometry sector factor;
- vehicle-scale proportion factor;
- evidence provenance integrity factor;
- road-edge rejection factor;
- weak optical thread conservativeness factor.

These are not admitted runtime factors. The ledger records their source dimension, current lifecycle state, runtime-safe observable evidence, GT posthoc validation role, positive GT-local expectation, negative non-target expectation, physical interpretation, verifiable relation, counterexample, allowed outcome, forbidden promotion, candidate scenes, validation need, and leakage risk.

## 8. Shortcuts Explicitly Forbidden

The registry forbids these shortcut families:

- optical thread strong + SAR bright point = same vehicle;
- SAR GT overlap + weak optical thread = upgraded identity;
- azimuth proximity + bright scatter = final support;
- multiple weak cues summed into strong truth;
- posthoc SAR GT evidence written into runtime prior;
- GT-local morphology used to define runtime threshold;
- GT center used to define azimuth/range factor;
- GT overlap used as mechanism proof without non-target contrast;
- small component box interpreted as vehicle shell;
- boundary relaxed because one SAR cue overlaps GT;
- SAR side ridge alone equals vehicle;
- mechanism support becomes annotation permission.

Each forbidden shortcut has a correct treatment: preserve it as weak posthoc support, defer it, block it by permission, require negative contrast, require vehicle-scale part-to-shell evidence, or keep the boundary blocked.

## 9. How The Idea Bank Should Be Updated Over Time

The idea bank should be updated when:

- a new failure case appears;
- a new physical explanation is proposed;
- a candidate factor is rejected;
- a factor is promoted from idea to runtime-observable;
- a factor is validated by GT but not admitted due to leakage risk;
- a factor passes GT-positive but fails negative non-target contrast;
- a joint factor is proposed;
- a scene-specific mechanism may generalize;
- a tempting forbidden shortcut must be recorded.

Every update should preserve the WGV2.3 split: broad discovery is allowed, strict admission is required, GT posthoc validation is not runtime construction, and mechanism support is not annotation permission.

## 10. Does WGV2.3 Create Final Boxes, Revised GT, SAR-Ready Annotation, Selector, Identity Truth, Or Runtime Prediction?

No.

WGV2.3 creates no final boxes, no GT boxes, no revised GT, no revised annotations, no SAR-ready annotations, no selector/ranking outputs, no score optimization, no threshold tuning, no runtime prediction artifacts, and no identity truth claims.

## Relationship To WGV2.0-WGV2.2

WGV2.0 defines the graph schema.

WGV2.1 instantiates graph windows.

WGV2.2 diagnoses propagated constraints and missing factors.

WGV2.3 records how future factors should be discovered, evolved, GT-validated, negative-contrast checked, admitted, deferred, or rejected.

## Expected Conclusion

Future factor discovery can be broad and creative.

Future factor admission must be strict and physically verifiable.

GT can validate a proposed mechanism but cannot create it.

A valid GT-based analysis must explain why the mechanism fits GT-local vehicle structure and why nearby non-target regions do not satisfy the same mechanism.

Joint factors require physical association, independent evidence, counterexamples, boundary checks, and evidence-permission checks.

The factor graph must remain a mechanism-reasoning system, not a heuristic weighted selector.
