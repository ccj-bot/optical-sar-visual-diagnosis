# OTY2 WGV2.3 Cross-Modal Factor Idea Bank

Date: 2026-07-09

## Status

WGV2.3 is a design-only factor idea bank and admission-rule document. It records how future missing factors may be discovered, validated, negative-contrast checked, admitted, deferred, or rejected inside the OTY2 cross-modal mechanism factor graph.

It does not run experiments, instantiate graph windows, create candidate boxes, generate scores, rank candidates, tune thresholds, produce final boxes, produce GT boxes, revise annotations, create SAR-ready annotations, or claim identity truth.

## 1. Core Principle

Missing-factor discovery should be divergent. Factor admission should be strict.

Candidate factors can come from optical behavior, SAR morphology, geometry, temporal continuity, imaging physics, failure cases, and cross-scene comparison. A wide source space is useful because WGV2.2 exposed missing factors that are not all in one layer: azimuth feasibility, temporal alignment, SAR temporal drift, non-vehicle rejection, competitor separation, and boundary evidence.

A factor is not valid merely because it correlates with GT. A factor is not valid merely because it helps close a desired case. A valid factor must have:

- runtime-safe observable evidence;
- physical interpretation;
- verifiable relation;
- counterexample conditions;
- evidence permission boundaries.

Mechanism relation is not identity truth. Mechanism support is not annotation permission. GT is for posthoc validation only.

## 2. Runtime Construction Vs GT Posthoc Validation

### Runtime-Safe Factor Construction Layer

Allowed inputs:

- optical frames;
- detector observations;
- optical thread state;
- optical behavior tags;
- time metadata;
- runtime-safe scene geometry;
- camera/SAR frame inventory;
- runtime-safe azimuth/range calibration if available;
- SAR image content only when the stage explicitly opens SAR evidence reading, but not SAR GT.

Forbidden inputs:

- SAR GT;
- GT box center;
- GT overlap;
- GT-local morphology labels;
- GT-derived thresholds;
- manually corrected labels;
- selector/ranking output;
- final annotation;
- revised GT.

Runtime construction may propose a factor such as truncation, edge contact, temporal tube, fan-polar feasible domain, optical continuity, or state-conditioned uncertainty only from runtime-safe evidence. It may not look at GT to decide where the factor should point, how wide it should be, which candidate should win, or what threshold should be used.

### Posthoc Validation Layer

Allowed inputs:

- SAR GT as a local reference anchor;
- GT-local SAR morphology;
- GT quality audit;
- GT-local positive evidence;
- nearby non-GT or outside-GT negative comparison;
- support miss / support shift analysis;
- background and non-vehicle comparison.

Required interpretation:

- GT can validate or falsify a proposed mechanism.
- GT cannot define the mechanism.
- GT can show that a runtime-safe factor is meaningful.
- GT cannot be used as the source of the factor.

The boundary is therefore asymmetric. Runtime-safe construction proposes the mechanism without GT. GT posthoc validation tests whether the proposed mechanism has positive GT-local fit and negative non-target contrast without leaking into runtime rules.

## 3. Required GT Validation Logic

Whenever GT is used, the validation must answer four questions.

A. Positive-fit question:

Why does the proposed mechanism fit inside the GT-local region?

B. Negative-contrast question:

Why does the same mechanism not fit nearby outside-GT, background, road-edge, guardrail, static-reflector, or competing-object regions?

C. Failure-case question:

When the mechanism fails inside GT, is the failure caused by weak SAR signal, GT quality, truncation, support miss, background clutter, or mapping uncertainty?

D. Leakage-control question:

Which part of this analysis is posthoc validation, and which part, if any, could later be runtime-safe without GT?

A GT-positive example without nearby negative contrast is not enough. A GT overlap without vehicle-scale morphology is not enough. A SAR bright point inside GT is not enough. A mechanism must explain why GT-local structure is vehicle-like and why non-target structures should be rejected.

## 4. Factor Lifecycle

| State | Meaning | Promotion Requirements |
| --- | --- | --- |
| `idea_seed` | A possible factor source or observation family has been named. | State the source dimension, expected runtime evidence, and why it is not already a weighted shortcut. |
| `candidate_factor` | The idea has a proposed mechanism role. | Define runtime-safe observable evidence, possible relation outcome, counterexample, and forbidden use. |
| `runtime_observable_factor` | The factor can be observed without SAR GT. | Identify exact runtime-safe inputs and show that GT is not used to define value, threshold, candidate, score, or rank. |
| `physically_interpretable_factor` | The factor has a physical explanation. | Connect the factor to optical state, SAR imaging physics, geometry, vehicle scale, temporal continuity, or boundary competition. |
| `gt_validated_posthoc_factor` | GT has been used only to validate or falsify the proposed mechanism. | Provide positive GT-local fit and state that GT did not create the factor. |
| `negative_contrast_checked_factor` | The factor has been checked against nearby non-target alternatives. | Explain why outside-GT, background, road edge, guardrail, static reflector, or competing vehicles do not satisfy the same mechanism. |
| `admitted_graph_factor` | The factor may enter the cross-modal factor graph vocabulary. | Pass all admission gates, including runtime observability, physical interpretation, verification path, counterexample, leakage control, and evidence permission. |
| `rejected_or_deferred_factor` | The factor is invalid, too weak, scene-specific, or not yet testable. | Record the rejection or deferral reason and the evidence needed to reconsider it. |
| `blocked_by_permission` | The factor may be informative posthoc but cannot be used by the target layer. | Preserve the evidence as explanation only and forbid runtime construction, selection, thresholding, annotation, or identity upgrade. |

Promotion rule:

A factor cannot move from `candidate_factor` to `admitted_graph_factor` unless:

- it has runtime-observable evidence not derived from GT;
- it has a physical interpretation;
- it has at least one verification path;
- it has counterexample conditions;
- if GT is used, it has GT-positive and non-target negative contrast analysis;
- it does not leak GT into runtime construction.

## 5. Divergent Factor Sources

Future idea collection should explore these dimensions without treating all ideas as admissible:

- optical behavior factors;
- optical temporal continuity factors;
- SAR local morphology factors;
- SAR temporal drift factors;
- SAR imaging geometry factors;
- azimuth/range feasible domain factors;
- support failure factors;
- non-vehicle rejection factors;
- boundary/competitor factors;
- evidence provenance/permission factors;
- scene-specific failure factors;
- cross-scene generalization factors.

## 6. Candidate Factor Examples

| Candidate Factor | Runtime-Safe Observable Evidence | GT Posthoc Validation Evidence If Applicable | Positive GT-Local Expectation | Negative Outside-GT / Background Expectation | Physical Interpretation | Possible Relation Outcome | Counterexample Or Failure Mode | Allowed Use | Forbidden Use |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| near-field truncation factor | Optical edge contact, partial-visible tag, abrupt visible extent change. | GT can test whether vehicle-scale SAR structure is shifted or only partially covered. | GT-local shell may show vehicle-scale structure outside a too-tight support. | Road edge or static reflector should not show vehicle-scale shell closure. | Near-field truncation weakens range and extent certainty. | Explains support shift or shell miss. | Complete visible vehicle with no edge contact. | Posthoc support-miss explanation and later runtime uncertainty widening if validated without GT. | GT center used to widen runtime shell or make final boxes. |
| edge-contact expansion factor | Optical bbox touches frame boundary or remains near the image border. | GT can test whether a vehicle part continues beyond the visible optical crop. | GT-local energy may include missing-side or endpoint structure. | Background border clutter should lack long/short-axis vehicle structure. | Edge contact means optical extent is censored. | Explains incomplete optical support. | Border box is a false detection or non-vehicle. | Mark state-conditioned uncertainty. | Use GT overlap to declare recovered vehicle. |
| visible-unboxed existence support factor | Optical frame shows visible vehicle evidence not captured by primary box. | GT can test whether SAR morphology supports existence, not identity. | GT crop may show vehicle-scale ridge or endpoint hotspot. | Nearby visible background should not form vehicle-scale closure. | Detector box is incomplete while target may still exist. | Supports vehicle existence only. | Visible region belongs to a competitor. | Posthoc existence-support hypothesis. | Annotation permission or identity upgrade. |
| same-color competitor risk factor | Multiple similar vehicles or competing optical boxes in same local context. | GT can test whether SAR support is ambiguous across competitors. | Target GT may be vehicle-like but not uniquely assigned. | Competitor GT or nearby vehicle-like structure may satisfy similar cues. | Visual similarity and crowding increase boundary risk. | Indicates competition or boundary block. | Only one visible object exists after review. | Preserve ambiguity and require boundary evidence. | Collapse competitors into same identity. |
| SAR side-ridge persistence factor | SAR image evidence only after a SAR evidence stage opens; adjacent-frame ridge continuity. | GT can anchor whether ridge lies in the local vehicle region. | GT-local ridge persists or drifts gradually. | Guardrail or road edge ridge remains static or fails vehicle-scale association. | Vehicle side returns can form a stable ridge. | Posthoc vehicle-structure support. | Ridge is static background or imaging artifact. | SAR morphology vocabulary and drift validation. | Runtime optical prior or selected box. |
| endpoint hotspot stability factor | Opened SAR evidence stage observes endpoint-like bright points across frames. | GT can test endpoint location relative to vehicle scale. | Hotspot aligns with plausible vehicle end or corner inside GT crop. | Isolated static bright point lacks paired shell or drift. | Corners or specular parts can dominate SAR returns. | Supports part-to-shell relation. | Single bright point is scattering atom only. | Posthoc part evidence. | Bright point equals vehicle or final support. |
| weak opposite-side return factor | Opened SAR evidence stage observes weaker return opposite a dominant ridge. | GT can test whether weak return helps close shell. | Opposite side appears weak but coherent at vehicle scale. | Background texture lacks paired dominant/weak-side geometry. | SAR vehicles may have asymmetric returns. | Supports vehicle-scale shell closure. | Noise or sidelobe imitates weak return. | Morphology explanation. | Threshold definition from GT crop. |
| vehicle-scale shell closure factor | Runtime-safe only if SAR evidence reading is explicitly opened; otherwise posthoc design. | GT crop can test long/short-axis, ridge, hotspot, and weak-side composition. | GT-local parts form a vehicle-scale shell or discontinuous outline. | Tiny components, road edges, or blobs fail scale and composition. | Vehicle is not a single scattering atom. | Posthoc vehicle-structure mechanism support. | Baby-car component or oversized background band. | Admit only after runtime observability and negative contrast. | Component box as final vehicle box. |
| background static reflector rejection factor | Static bright spots repeat without vehicle-like motion or optical support. | GT can compare target crop against nearby non-GT static reflectors. | Target GT has vehicle-scale structure beyond isolated peak. | Static reflector is point-like or fixed background. | Vehicle evidence needs scale, composition, and temporal compatibility. | Indicates background risk or rejection. | Parked static vehicle could be non-moving. | Negative non-target contrast. | Treat any bright point as target evidence. |
| non-jump SAR temporal drift factor | SAR evidence stage observes gradual ridge/hotspot drift across adjacent frames. | GT can test whether drift remains within vehicle-local region. | Local structure moves smoothly or persists. | Background reflectors do not drift with target-like continuity. | Physical vehicle returns should not teleport between frames. | Supports temporal compatibility. | Low SNR breaks visible drift. | Posthoc drift support and later runtime SAR evidence gate. | Identity truth from drift alone. |
| boundary preservation factor | Optical preserved boundary, competing merge edge, or different-vehicle marker. | GT can test whether SAR evidence remains ambiguous across the boundary. | Target-side evidence should not erase competitor or boundary evidence. | Competing object or outside-GT region may explain similar cue. | Boundary evidence blocks unsafe bridge. | Supports boundary or blocked relation. | Boundary was caused by detector duplicate of same vehicle. | Preserve blocked state until independent boundary evidence exists. | Relax boundary because one cue overlaps GT. |
| permission blocking factor | Evidence provenance says posthoc, manual, GT, selector, or final annotation. | GT role is to expose leakage risk, not promote factor. | GT may explain why evidence is useful posthoc. | Same evidence must be absent from runtime construction. | Permission is a graph factor, not bookkeeping. | Blocked by permission. | Provenance is mislabeled or incomplete. | Prevent leakage and document allowed use. | Copy posthoc evidence into runtime prior. |
| GT-positive / non-target-negative contrast factor | Runtime factor is proposed first from non-GT inputs. | GT validates positive fit and nearby non-target rejection. | Proposed mechanism fits vehicle-scale GT-local structure. | Nearby background, road edge, guardrail, and competitor fail the mechanism. | Validation must close both positive and negative logic. | Negative-contrast checked posthoc factor. | No nearby negative examples available. | Admission evidence for future graph factor. | GT overlap alone as mechanism proof. |

## 7. Joint-Factor Admission Rules

Joint factors must pass all gates:

- runtime-observable gate;
- physical plausibility gate;
- independent evidence gate;
- GT-positive validation gate if GT is used;
- non-target negative contrast gate;
- counterexample gate;
- boundary/competition gate;
- evidence-permission gate;
- cross-window or cross-scene stability gate when applicable.

Forbidden shortcut examples:

- optical thread strong + SAR bright point = same vehicle;
- SAR GT overlap + weak optical thread = upgraded identity;
- azimuth proximity + bright scatter = final support;
- multiple weak cues summed into strong truth;
- posthoc SAR GT evidence written into runtime prior;
- GT-local morphology used to define runtime threshold;
- GT center used to define azimuth/range factor;
- GT overlap used as mechanism proof without non-target contrast.

Allowed cautious relation examples:

- optical truncation + runtime support shift prediction + GT-local vehicle-scale morphology + outside-GT negative contrast = posthoc explanation of support miss;
- visible-unboxed optical gap + SAR vehicle-scale local evidence = posthoc existence-support hypothesis only;
- preserved optical boundary + competitor risk + ambiguous SAR structure = boundary remains blocked;
- weak optical thread + SAR overlap = weak posthoc support only, no upgrade;
- SAR side-ridge persistence + non-jump drift + vehicle-scale shell + non-target rejection = posthoc vehicle-structure mechanism support.

## 8. Relationship To WGV2.0-WGV2.2

WGV2.0 defines the graph schema: node types, factor types, relation outcomes, evidence permission rules, and scene roles.

WGV2.1 instantiates a bounded set of graph windows using that schema.

WGV2.2 diagnoses propagated constraints and missing factors. It shows that evidence permission, boundary preservation, competitor risk, geometry feasibility, and contradiction/blocking factors prevent unsafe upgrades, while missing azimuth, temporal alignment, SAR drift, non-vehicle rejection, competitor separation, and boundary evidence block stronger SAR consumption.

WGV2.3 records how future factors should be discovered, evolved, GT-validated, negative-contrast checked, admitted, deferred, or rejected.

## 9. Documentation Practice

The idea bank should be updated periodically, especially when:

- a new failure case appears;
- a new physical explanation is proposed;
- a candidate factor is rejected;
- a factor is promoted from idea to runtime-observable;
- a factor is validated by GT but not admitted due to leakage risk;
- a factor passes GT-positive but fails non-target negative contrast;
- a joint factor is proposed;
- a scene-specific mechanism may generalize;
- a tempting forbidden shortcut must be explicitly recorded.

Every update should keep the same boundary: divergent discovery is allowed, strict admission is required, GT posthoc validation cannot become runtime factor construction, and mechanism support cannot become annotation permission.
