# OTY2 Phase Reset: Open Questions and Mechanism Lanes

## 1. Why A Phase Reset Is Needed

Previous sessions corrected multiple errors, but old context still risks contaminating new work:

- support-wide thinking;
- peak/component thinking;
- baby-car shell;
- weighted-fusion temptation;
- treating GM_RM011 as unusable;
- treating support as fixed.

Therefore new work must be lane-based and mechanism-first.

The reset does not promote the work into OTY3. It keeps the current branch inside OTY2 posthoc mechanism diagnosis, where SAR GT, SAR image observation, and GT-local energy fields are reference material for explanation and failure diagnosis only. They must not become runtime prediction logic, final annotations, revised GT, selector labels, or identity truth.

## 2. Open Question 1: SAR-Only Positive/Negative Closure

The SAR-only lane must answer two sides of the mechanism question:

- How to explain a SAR vehicle?
- How to reject non-vehicle SAR structures?
- What negative examples are needed?
- How should GT context be used?
- What visualizations should be produced?

The goal is not a classifier yet; the goal is a physically interpretable morphology grammar.

A positive explanation should operate at vehicle scale. It should look for dominant-side or near-side ridges, endpoint or corner hotspots, weaker opposite-side returns, long-axis / short-axis structure, and discontinuous but self-consistent shell closure. A single peak, tiny component, or small green component box cannot be promoted into a vehicle.

A negative explanation must reject structures that may be visually bright but are not vehicle-scale shells: guardrail edges, road edges, building edges, flowerbeds, fixed background hotspots, pedestrian or e-bike point-like responses, isolated peaks, texture clutter, and small components without shell closure.

GT context may anchor posthoc morphology reading, but it does not revise the GT and does not create a runtime rule. Useful visualizations should use GT-local coordinates, show enough SAR context to compare vehicle and non-vehicle structures, and avoid support-internal component drawings that make a baby-car interpretation possible.

## 3. Open Question 2: Physical Mechanism Vs Heuristic Stacking

Weighted evidence fusion is shallow when it only adds scores:

```text
time_score + azimuth_score + support_score + energy_score + shell_score + temporal_score
```

This can rank something, but it does not explain why a vehicle-scale SAR structure exists, why other bright structures are non-vehicles, or how an optical hypothesis failed.

Heuristic stacking is also shallow when it layers rules without a physical role. Adding more checks does not automatically create a mechanism if each check remains an isolated score or filter.

The mechanism-first view assigns a physical role to each component:

- optical object stream supplies the hypothesis and temporal continuity;
- optical state explains truncation, occlusion, and edge contact;
- geometry supplies azimuth/range feasible fields;
- SAR morphology explains vehicle vs non-vehicle structure;
- SAR temporal continuity checks non-jump and gradual drift;
- support statistics feed back into mechanism correction.

Mechanism fusion should be represented as constraint propagation, failure feedback, and correction. For example, a support miss should route back to time mapping, range shell, azimuth mapping, optical state, near-field handling, or temporal compensation instead of being hidden inside a weaker support score.

## 4. Open Question 3: GM_RM011 Recovery

GM_RM011 can be used for SAR morphology now because it has SAR GT and SAR-side target reference value. It is not unlabeled, not unusable, and not a row family to discard.

GM_RM011 cannot yet be mixed into clean `215` paired support validation because the current OTY optical object stream is missing or blocked. Without the current object stream, it is not part of the clean paired optical-object-stream / SAR-GT frame-level pool.

Future sessions should diagnose the missing object stream directly:

- whether optical frames exist;
- whether the optical object is visible;
- whether YOLO / detection output exists;
- whether ByteTrack / object stream output exists or breaks;
- whether optical-SAR time mapping is wrong;
- whether azimuth / range mapping is wrong;
- whether optical state compensation is missing;
- whether the failure is object association rather than SAR morphology.

If optical/SAR cannot be paired, the conclusion should be a taxonomy of optical temporal stream, mapping, or object association failure. It should not be "GM_RM011 has no value."

Future Codex sessions should search for scene configuration, optical frame manifests, detection outputs, object stream or tracker artifacts, optical-SAR time mapping files, azimuth/range calibration files, and prior OTY2 reports under `reports/oty2`. They should not use `archive/` or `old_work/` as active sources.

## 5. Open Question 4: Support As Dynamic Hypothesis Field

Is support fixed? No.

support is an optical-derived hypothesis field. It is not a final box, not a selector output, and not a permission to explain only whatever happens to lie inside it.

Existing support statistics already indicate mechanism risk when support misses GT vehicle-scale shell, is too broad, contains a neighbor, contains no GT but vehicle-like energy, contains no GT and no vehicle-like structure, or covers only part of the vehicle.

Failed support statistics imply mechanism problems because the support field is the output of time mapping, azimuth mapping, range shell construction, optical state interpretation, near-field handling, temporal compensation, and object-stream association. A bad support field points back to those mechanisms.

Support failure should feed back as follows:

- support miss GT vehicle shell -> time mapping / range shell / azimuth mapping / optical state / near-field / temporal compensation;
- support too broad -> azimuth margin / range looseness / state over-compensation;
- support contains neighbor -> multi-object scene / identity ambiguity / optical tracklet / SAR temporal separation;
- support contains no GT but vehicle-like energy -> neighbor GT / missing annotation candidate / false vehicle-like clutter;
- support contains no GT and no vehicle-like structure -> optical false hypothesis / time mismatch / support false positive;
- support covers only part of vehicle -> truncation / partial optical object / range compression.

## 6. Open Question 5: Support-Without-GT Audit

Prior paired-only audits hide support regions that have no paired GT. Future audit must start from optical object hypotheses and classify:

- `support_contains_paired_gt`
- `support_misses_paired_gt`
- `support_contains_other_gt_neighbor`
- `support_contains_no_gt_but_vehicle_like_energy`
- `support_contains_no_gt_background_structure`
- `support_empty_or_weak`
- `support_unjudgeable`

This audit must include support-without-GT cases, not only the `215` paired rows. The point is to understand whether the optical-derived hypothesis field is creating useful vehicle search context, drifting to neighbors, landing on background, or missing vehicle-scale shell structure.

The output should be a support failure taxonomy and mechanism feedback, not a final candidate box.

## 7. Minimal Next Tasks

Candidate next tasks, not executed by this phase-reset document:

A. GM_RM011 object-stream recovery / pairing failure diagnosis.

B. SAR vehicle-vs-nonvehicle morphology closure design.

C. Dynamic support-without-GT audit design.

Recommended priority:

First: phase reset docs.

Then: GM_RM011 recovery audit or support-without-GT audit.

Do not go directly to large-scale motion/drift before GT-local energy-field visualization is readable.

## Mechanism Lanes

Lane A: SAR vehicle / non-vehicle morphology closure

- Input: `442` SAR GT + context, including GM_RM011 / SAR-only / dropout special as SAR morphology reference.
- Goal: explain why vehicle is vehicle and why non-vehicle is not vehicle.
- Output: vehicle-vs-nonvehicle physical morphology grammar.
- Boundary: no selector.

Lane B: GM_RM011 optical object stream recovery and pairing failure diagnosis

- Input: GM11 SAR GT, optical frames, detection / object stream pipeline artifacts if available.
- Goal: recover or diagnose missing object stream and pairing failure.
- Output: recoverable paired candidates / failure taxonomy.
- Boundary: do not force into clean `215`.

Lane C: dynamic support hypothesis audit

- Input: all optical object hypotheses with support, not only paired GT rows.
- Goal: classify support with/without GT, neighbor GT, background structure, vehicle-like but unpaired structure, empty support.
- Output: support failure taxonomy and mechanism feedback.
- Boundary: no final box.

Lane D: optical-SAR temporal compatibility

- Input: SAR morphology that is physically interpretable + optical tracklet.
- Goal: check whether ridge / hotspot / shell drifts non-jump and matches optical continuity.
- Output: motion/drift compatibility.
- Boundary: no identity truth.
