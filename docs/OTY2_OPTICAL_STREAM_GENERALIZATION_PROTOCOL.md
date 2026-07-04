# OTY2 Optical Stream Generalization Protocol

Updated: 2026-07-04

This document is a binding process correction for OTY2 optical-object-stream work.

Core rule:

**Do not treat GM_RM011 as a special case to patch. Treat it as a pressure test for whether the optical object-stream mechanism generalizes across scenes.**

## 1. Boundary

This remains OTY2 posthoc mechanism diagnosis.

Forbidden:

- final annotation;
- revised GT;
- final box;
- selector or ranking logic;
- threshold tuning to make one scene pass;
- weighted-fusion mainline;
- identity truth;
- clean-pool promotion of GM_RM011;
- SAR GT or SAR image evidence leaking into runtime optical object-stream construction.

Recovered optical tracks and object IDs are hypotheses only. They are not identity truth.

## 2. Why This Protocol Exists

GM_RM011 now has a recovered optical object stream, but the stream is highly fragmented and has a high review burden. That result must not be handled as a one-scene repair problem.

A single-scene failure after previous scenes appeared usable means the workflow may have hidden assumptions. The correct response is not immediate local repair. The correct response is cross-scene mechanism diagnosis.

Future sessions must answer:

- Did previous scenes truly pass, or were they only schema-compatible?
- Were previous scenes easier because of fewer targets, less occlusion, less truncation, less crossing, or more continuous detections?
- Do previous reports show the same warning signs at lower severity?
- Which general mechanism assumption did the failing scene expose?
- Which part of the optical target-stream mechanism needs global adjustment?

## 3. PASS_WITH_UNCERTAINTY Is Not Success

For optical-stream work, `PASS_WITH_UNCERTAINTY` means the stage can run and its schema is compatible.

It does not mean the mechanism succeeded.

Examples:

- detections exist, but tracks are short;
- tracker runs, but many detections are unmatched;
- object hypotheses exist, but most require review;
- fragment merge candidates exist, but no identity merges are confirmed;
- object IDs are generated, but continuity is not reliable.

Such outputs may be used for diagnosis only. They must not be treated as clean object streams.

## 4. Mandatory Cross-Scene Comparison Trigger

A cross-scene optical-stream audit is mandatory when a scene shows:

- high short-track ratio;
- high ambiguous-track ratio;
- many unmatched detections;
- many review-required object hypotheses;
- zero confirmed fragment merges;
- large gap between detection availability and stream stability;
- failure in one scene while other scenes were previously reported as usable.

The failing scene must be compared against previously usable scenes, usually GM_RM017 and GM_RM019 when available.

The mandatory question is:

**Why did other scenes appear to pass before this one failed?**

## 5. Required Audit Dimensions

Before changing logic, compare scenes on these dimensions.

### 5.1 Detection Continuity

- total frames;
- frames with detections;
- frames without detections;
- per-frame detection count distribution;
- class distribution;
- confidence distribution;
- box coordinate sanity;
- sudden box size changes;
- sudden box aspect-ratio changes.

### 5.2 Track Fragmentation

- number of tracks;
- track length distribution;
- short-track ratio;
- median and max track length;
- tracked-frame coverage;
- unmatched detections;
- possible ID-switch count;
- duplicate or overlapping hypotheses.

### 5.3 Multi-Object Competition

- crowded-frame ratio;
- number of simultaneous nearby detections;
- close-neighbor detection pairs;
- duplicate-overlap hypotheses;
- competing merge candidates;
- crossing or near-crossing risk.

### 5.4 Shape And State Instability

- abrupt box center motion;
- abrupt area changes;
- abrupt aspect-ratio changes;
- partial-to-full transitions;
- truncation hints;
- occlusion-like gaps;
- edge-contact hints.

### 5.5 Implicit Mechanism Assumptions

The report must identify which assumptions were used implicitly:

- detections are frequent enough;
- boxes change smoothly;
- adjacent-frame geometry is enough for association;
- targets are spatially separated;
- short gaps are rare;
- truncation and occlusion are minor;
- one detection corresponds to one object hypothesis;
- simple fragment merge rules are sufficient.

Any violated assumption becomes a candidate for global mechanism correction.

## 6. No Local Patch Before Mechanism Diagnosis

Before changing detector settings, merge rules, tracker parameters, support logic, or pairing logic for a failing scene, produce a cross-scene comparison report.

Do not tune thresholds locally to make one scene pass.

Do not change support or pairing logic from a single-scene failure without checking whether the same assumption already appears in other scenes.

Any proposed change must be labeled as one of:

- global mechanism correction;
- temporary diagnostic probe;
- scene-specific debug only;
- not yet justified;
- forbidden posthoc leakage.

Scene-specific fixes may be used only to diagnose failure causes. They must not become the production mechanism without cross-scene justification.

## 7. Correct Next Diagnostic After GM_RM011 Recovery

After GM_RM011 object-stream recovery, do not jump directly to optical-SAR pairing or support audit.

The next diagnostic should be:

**OTY2 cross-scene optical object-stream generalization audit**

Minimum comparison:

- GM_RM011 as pressure-test scene;
- GM_RM017 and/or GM_RM019 as previous usable scenes;
- the same OTY0 / OTY1 / OTY1a / OTY1t / P4G diagnostics where artifacts exist or can be rerun safely.

The report should classify the failure as:

- detection-continuity failure;
- track-fragmentation failure;
- multi-object competition failure;
- shape/state-instability failure;
- convention or config artifact;
- global mechanism weakness;
- unresolved.

## 8. Required Report Language

Use precise language:

- schema-compatible but mechanism-uncertain;
- object hypotheses recovered for diagnosis only;
- fragmentation indicates generalization risk;
- previous scene success must be rechecked under the same diagnostics;
- not eligible for clean-pool promotion.

Do not say:

- recovered clean stream;
- identity confirmed;
- ready for final pairing;
- GM_RM011 fixed;
- local threshold solved it;
- special-case repair.

## 9. Practical Rule

If the question is:

**Why does this scene fail when others worked?**

the required answer is not a patch.

The required answer is:

1. identify the assumption exposed by the failing scene;
2. compare that assumption across scenes;
3. determine whether previous success was real or only easier-case compatibility;
4. change the general mechanism only after cross-scene evidence supports it.
