# OTY2 Parallel Mechanism Exploration Design

Updated: 2026-07-03

This document records the current OTY2 research design after the range-narrowing, peak-competition, gated-association, and scatter-cluster audits. It is not an experiment report, not OTY3, not an automatic annotation plan, not a selector/ranking design, and not training or threshold tuning.

The purpose is to keep the next stage focused on mechanism discrimination instead of local metric engineering.

## Current Evidence

The current audits establish a useful but non-final state:

- `broad_fan_baseline` keeps high posthoc GT coverage, but the support region is too wide.
- Under broad fan support, top1 SAR peak and even top-k peaks are not reliable target centers.
- `state_conditioned_range_band` and `object_smoothed_range_band` show strong posthoc potential.
- SAR observation cannot keep being modeled as `top1_peak`.
- Gated association / scatter-cluster reasoning is the right main line, but tuning only gate labels or cluster metrics would become a new local trap.

Current key numbers:

- broad paired GT coverage posthoc: `0.9628`
- broad serious peak competition rate: `1`
- broad median top1/top2 ratio: `1.004`
- broad top1 near-GT rate posthoc: `0.0093`
- broad top-k contains near-GT rate posthoc: `0.0279`
- state-conditioned top-k contains near-GT rate posthoc: `0.8977`

Interpretation:

```text
optical support -> brightest SAR point
```

is not a sufficient model. The safer next model is:

```text
optical support -> SAR scatter structure -> temporal persistence -> gated optical/SAR association
```

## Stage Strategy

The next stage should not be a single line of work. It should be:

```text
main-line convergence + side-line divergence
```

The main line should keep converging toward association-state semantics. The side lines should deliberately test whether the current signals are real, physically interpretable, and supplied by runtime-safe optical information rather than posthoc leakage or SAR background coincidence.

## Main Line A: Gated Association / Failure Transition

Goal:

```text
explain when optical object hypotheses and SAR scatter tubes may be associated
```

Not the goal:

```text
maximize associated_posthoc_strong count
```

The required questions are:

- When may an `optical object hypothesis` and a `SAR scatter tube` be associated?
- When must evidence remain isolated?
- When is only weak support allowed?
- When is manual or identity review required?
- When can dropout only provide existence support?
- Which gate is runtime-safe optical/temporal evidence, which is SAR observation, and which is posthoc-only validation?

Association states should remain explanatory labels, not final predictions:

```text
associated_posthoc_strong
associated_posthoc_weak
sar_structure_present_but_optical_ambiguous
optical_support_present_but_sar_ambiguous
review_required
rejected_for_peak_competition
rejected_for_temporal_instability
dropout_existence_support_only
```

The decision boundary must preserve isolated evidence. A SAR scatter cluster can support a hypothesis, but it does not by itself establish optical identity truth.

## Side Line B: SAR Scatter-Structure Imaging Mechanism

Goal:

```text
understand what vehicle-like SAR evidence looks like inside optical-derived support
```

Not the goal:

```text
find the brightest point
```

Vehicle targets in SAR may be extended scatter structures, not single point centers. The next stage should distinguish:

- `compact_cluster`
- `multi_peak_nearby_cluster`
- `range_spread_cluster`
- `azimuth_spread_cluster`
- `diffuse_clutter`
- `sidelobe_like_competition`
- `temporal_jumping_peak`
- `stable_scatter_tube`

Useful SAR observation descriptors include:

- top-k peak group geometry
- peak/background ratio
- top1/top2 competition
- scatter centroid
- cluster compactness and spread
- range spread and azimuth spread
- local peak density
- short-window persistence
- object-tube continuity

These are SAR observation diagnostics. They are not selector features unless a later, separately authorized runtime design proves provenance and validation.

## Side Line C: Counterfactual / Negative-Control Support Validation

Goal:

```text
test whether optical-derived support has discriminative power beyond wrong or random support
```

This is the highest-value bootstrap probe because it tests whether the current mechanism is real signal or accidental SAR background coverage.

Required negative controls:

- `true_support`: the current optical-derived support.
- `azimuth_shifted_support`: shift the fan sector, for example by `+10`, `-10`, `+20`, and `-20` degrees.
- `range_shifted_support`: shift the range band upward/downward when the band is not full fan radius.
- `wrong_object_support`: replace the current support with another object hypothesis support from the same scene.
- `wrong_sar_frame_support`: use a non-corresponding SAR frame with the same support.
- `random_same_scene_support`: construct a same-scene random support with comparable size.
- `same_state_random_support`: a later extension when enough state-balanced sampling is available.

Core interpretation:

```text
if true support ~= wrong/random support:
    current mechanism may be pseudo signal or background peak coincidence

if true support >> wrong/random support:
    optical-derived support carries discriminative signal
```

Validation metrics can include:

- `gt_inside_support_posthoc`
- `top1_near_gt_posthoc`
- `topk_contains_near_gt_posthoc`
- `multiple_topk_peaks_near_gt_posthoc`
- peak/background
- support area
- scatter cluster type
- temporal stability label
- stable-cluster-tube rate
- jumping-peak rate
- diffuse/unstable rate
- peak competition severity

GT is allowed only for posthoc validation. GT-near top-k is allowed only to diagnose whether true support is more discriminative than negative controls. GT peak distance must not be written into runtime prior construction.

## Side Line D: Optical Information Bottleneck / Cue Contribution Audit

Goal:

```text
measure how much runtime-safe optical information actually contributes to SAR support construction
```

Suggested cue ladder:

- time only
- time + azimuth
- time + azimuth + state
- time + azimuth + state + bbox height
- time + azimuth + state + object smoothing
- time + azimuth + state + trajectory
- time + azimuth + state + SAR observation gate

Boundary:

- `bbox_height_px`
- shape-radius relation
- scene residual
- object-smoothed range trend

are currently posthoc observations. They are hypotheses to validate, not runtime priors.

Runtime-safe potential should be separated from current permission:

```text
runtime-safe now:
  optical object stream
  optical frame / SAR frame software-sync ratio
  optical bbox x -> fan azimuth sector
  optical state categories
  vehicle physical shell assumptions

posthoc or hypothesis now:
  SAR GT radius relation
  GT-near top-k success
  scene residual correction
  object-smoothed GT radius trend
  SAR image-derived prior rules
```

## How The Four Lines Relate

Gated association answers:

```text
when may optical and SAR evidence be associated?
```

SAR scatter-structure answers:

```text
what does a SAR vehicle-like observation look like?
```

Counterfactual validation answers:

```text
does optical-derived support have discriminative power beyond random or wrong support?
```

Optical information bottleneck answers:

```text
which optical cues actually contribute to SAR support construction?
```

These lines should cross-check each other. A gate that works only because GT-near top-k was posthoc-selected is not a runtime gate. A cluster type that appears equally in random supports is not discriminative. A cue that helps only after SAR GT residual fitting is not runtime-safe yet.

## Sample Ledger To Preserve

The 442 ledger remains fixed:

```text
paired_optical_object_sar_gt = 215
blocked_missing_gm011_object_stream = 195
sar_only_gt = 20
detection dropout / no_oty_iou_match / temporal continuation pool = 12
```

Interpretation:

- The 215 paired rows are the current optical-object/SAR-GT posthoc correspondence subset, not the whole GT inventory.
- The 195 GM_RM011 rows are blocked by missing current OTY optical object stream; they are not unannotated.
- SAR-only rows must stay outside optical-SAR correspondence statistics.
- Dropout/no-match rows can provide temporal existence support, but must stay outside clean morphology.

## Provenance Labels

Every output should label conclusions with one or more of:

```text
runtime_safe_optical_evidence
runtime_safe_temporal_evidence
runtime_safe_geometry_or_vehicle_physics
SAR_image_observation
SAR_temporal_observation
SAR_GT_posthoc_evidence
manual_or_review_anchor
hypothesis_to_validate
insufficient_or_not_supported
```

## Core Principles

Do not:

1. Treat top1 peak as the target center.
2. Treat top-k near-GT as runtime capability.
3. Treat `associated_posthoc_strong` as the only goal.
4. Turn gated association into a selector/ranking design.
5. Write state-conditioned success directly as a runtime rule.
6. Omit provenance labels from conclusions.
7. Drift from mechanism discrimination into final annotation.

Also do not:

- generate final annotation proposals
- output selector/ranking
- train or tune thresholds
- claim identity truth
- write GT peak / GT residual into runtime prior
- mix dropout/no-match into clean morphology
- mix SAR-only into optical-SAR correspondence
- treat GM_RM011 as unannotated
- commit `MatlabToolboxZB.zip` or any zip

## Recommended Bootstrap Probe

The immediate lightweight probe should be:

```text
OTY2 parallel mechanism exploration bootstrap
```

Priority:

```text
counterfactual / negative-control support validation
```

Minimum output intent:

- Compare true support against shifted, wrong-object, wrong-frame, and random supports.
- Keep GT use posthoc only.
- Report whether state-conditioned support remains discriminative under controls.
- Explain why broad support creates pseudo peaks.
- Identify SAR scatter structures that are more discriminative for true support.
- Sketch which optical cues likely contribute most and which remain posthoc.

The expected next decision is not an annotation action. It is choosing whether the next mechanism work should emphasize gate provenance, SAR scatter-structure modeling, optical cue bottleneck analysis, GM_RM019 review, or GM_RM011 object-stream recovery.
