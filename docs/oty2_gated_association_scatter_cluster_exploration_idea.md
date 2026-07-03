# OTY2 Gated Association And Scatter-Cluster Exploration Idea

Updated: 2026-07-03

This document records the next exploration idea after the OTY2 support-region range narrowing and peak competition audit. It is an idea archive and research-direction note, not OTY3, not a final automatic annotation report, not a selector/ranking design, and not training or threshold tuning.

## Why This Direction Is Needed

The latest range-narrowing audit shows a useful but non-final state:

- `broad_fan_baseline` paired GT coverage is `0.9628`.
- `broad_fan_baseline` serious peak competition rate is `1`.
- `broad_fan_baseline` median top1/top2 ratio is `1.004`.
- Range narrowing can greatly reduce support area, but peak competition remains pervasive.

This means the top SAR peak inside a support region cannot be treated as the vehicle center. The result is not a failure; it is a direction change:

```text
from: optical support region -> brightest SAR point
to: optical support region -> SAR scatter-cluster structure -> temporal persistence -> gated optical/SAR association
```

## Isolation Before Association

Single-frame evidence and temporal evidence should be isolated first, then associated only when gates pass.

### Optical Single Frame -> SAR Single Frame

Use the optical observation and current support region only to extract SAR cluster evidence:

```text
O_o,t = bbox + optical state + object_hypothesis_id + optical_frame
C_o,t,tau = C_time intersect C_az intersect C_range intersect C_state
Z_o,t,tau = ExtractSARCluster(I_tau, C_o,t,tau)
```

Allowed question:

```text
Does this optical-derived support region contain compact, multi-peak, diffuse, or clutter-like SAR scatter evidence?
```

Not allowed:

```text
final SAR box
top1 peak as vehicle center
identity truth
```

### Optical Single Frame -> SAR Short Window

Use the 24 fps to 50 fps software mapping to inspect a short SAR window:

```text
tau0(t) = 50/24 * t + Delta_s
W_t^SAR = [tau0 - jitter, tau0 + jitter]
```

Extract cluster evidence over the window and check whether the top-k peak group, scatter centroid, and cluster spread persist.

### Optical Tracklet -> SAR Single Frame

For a SAR frame, use nearby optical tracklet context instead of a single optical box:

```text
t(tau) = 24/50 * (tau - Delta_s)
O_hat_o,t(tau) = InterpOrSmooth(O_o,t-1, O_o,t, O_o,t+1)
C_o,tau^track = BuildSupport(O_hat_o,t(tau), state, trend)
```

This may stabilize support construction, especially for edge, truncated, and dropout cases, but it still does not establish identity.

### Optical Tracklet -> SAR Temporal Tube

For each object hypothesis:

```text
T_o^SAR = {(tau, C_o,tau)}
Z_o,1:K = {Z_o,tau_1, ..., Z_o,tau_K}
```

The tube should answer whether a SAR scatter structure persists, drifts smoothly, and remains compatible with optical state and motion evidence.

## Isolation-Association State Machine

### Stage 0: Isolated Single-Frame Extraction

Input:

```text
O_o,t
I_tau^SAR
C_o,t,tau
```

Output:

```text
single_frame_sar_cluster_evidence
```

No association claim is allowed.

### Stage 1: Isolated SAR Temporal Extraction

Input:

```text
{I_tau^SAR, C_o,t,tau} over a short SAR window or tube
```

Output:

```text
sar_cluster_continuity_evidence
```

No optical identity claim is allowed.

### Stage 2: Isolated Optical Tracklet Quality Audit

Classify optical object hypotheses before using them strongly:

```text
clean_complete_tracklet
state_mixed_tracklet
edge_or_truncated_tracklet
duplicate_or_handoff_tracklet
far_small_tracklet
dropout_continuation_tracklet
review_required_tracklet
```

Only clean or review-acceptable tracks can provide strong constraints.

### Stage 3: Gated Association

Association is allowed only after gates pass:

```text
G(o, Z_1:K) in {reject, weak_support, review_needed, associated_posthoc}
```

Suggested gates:

- `G_support`: SAR cluster lies inside the optical-derived support region.
- `G_cluster`: top-k peaks form compact or vehicle-like scatter evidence.
- `G_temporal`: the cluster persists in the short window or SAR tube.
- `G_optical_state`: the optical tracklet is not unresolved duplicate/handoff.
- `G_motion`: optical trajectory and SAR cluster drift do not strongly conflict.
- `G_range`: range band is not overly broad and not over-compressed.

Association should not be declared when the SAR cluster is unstable or the optical tracklet is ambiguous.

## Range Constraint Refinement

The next range hypothesis should combine object-smoothed and state-conditioned uncertainty:

```text
r_o,t in [r_hat_smooth(o,t) - sigma(state_t),
          r_hat_smooth(o,t) + sigma(state_t)]
```

with:

```text
sigma(complete) < sigma(edge/truncated) < sigma(dropout/duplicate)
```

Suggested behavior:

- `complete/stable`: associate and tighten if SAR cluster and temporal gates pass.
- `edge/truncated`: partially associate, keep wider uncertainty.
- `dropout`: use temporal existence support only; exclude from clean morphology.
- `duplicate/handoff`: hold association until review.

This remains a hypothesis direction. Current object-smoothed and state-conditioned range bands are posthoc observations, not runtime rules.

## SAR Scatter-Cluster Representation

SAR evidence should be represented as a cluster, not a single peak:

```text
Z = {
  top_k_peaks,
  peak_values,
  top1_top2_ratio,
  peak_background_ratios,
  peak_positions,
  peak_spread,
  scatter_centroid,
  scatter_covariance,
  range_profile,
  azimuth_profile,
  temporal_persistence,
  vehicle_footprint_fit
}
```

Useful diagnostics:

- `compactness`: mean distance from top-k peaks to cluster centroid.
- `topk_separation`: distance between top1 and top2 peaks.
- `profile_sharpness_range`: concentration of the range profile.
- `profile_sharpness_azimuth`: concentration of the azimuth profile.
- `temporal_persistence`: fraction of frames where a compatible cluster persists.
- `vehicle_footprint_fit`: whether cluster extent is plausible under a vehicle shell.

The goal is to distinguish:

```text
single stable vehicle-like scatter cluster
multi-peak vehicle-like scatter cluster
clutter-dominated support region
sidelobe-like peak competition
diffuse weak support
temporal jumping peak
review-required ambiguous structure
```

## Suggested Next Probes

### Probe A: Top-K Peak vs GT Posthoc Diagnosis

Use GT only for posthoc diagnosis:

- Is top1 near GT?
- Is top2 or top3 nearer to GT than top1?
- Does top-k contain a peak near GT?
- Are multiple peaks near GT, suggesting extended vehicle scatter?
- Are all top-k peaks far from GT, suggesting support-region or SAR observation failure?

### Probe B: Scatter Cluster Structure Probe

Classify each support-region SAR structure:

```text
compact_cluster
multi_peak_nearby_cluster
range_spread_cluster
azimuth_spread_cluster
diffuse_clutter
jumping_peak
weak_no_structure
```

### Probe C: Temporal Cluster Association Probe

Check whether scatter clusters persist across adjacent SAR frames:

- Does centroid drift remain smooth?
- Does the same top-k peak group persist?
- Does temporal persistence separate vehicle-like structures from clutter peaks?
- Does dropout/no-match show SAR temporal existence support?

### Probe D: Optical-State Gate Probe

Decide how optical state affects association:

- `complete/stable`: may allow strong association.
- `edge/truncated`: should widen support and weaken association.
- `duplicate/handoff`: requires review.
- `dropout`: existence support only, not clean morphology.

### Probe E: Gated Association Audit

Possible posthoc association states:

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

## Ledger Boundary To Preserve

```text
paired_optical_object_sar_gt = 215
blocked_missing_gm011_object_stream = 195
sar_only_gt = 20
dropout/no_oty_iou_match/temporal continuation pool = 12
```

`GM_RM011` is not unannotated; it is blocked by missing current OTY optical object stream. SAR-only rows must not enter optical-SAR correspondence. Dropout/no-match rows must not enter clean paired morphology.

## Provenance Labels

Future reports should explicitly label evidence as:

```text
runtime_safe_optical_evidence
runtime_safe_temporal_evidence
SAR_image_observation
SAR_temporal_observation
SAR_GT_posthoc_evidence
manual_or_review_anchor
hypothesis_to_validate
insufficient_or_not_supported
```

## What Should Not Happen

Do not:

```text
use top1 peak as target center;
generate final annotation proposal;
output selector or ranking;
train thresholds;
claim identity truth;
mix dropout/no-match into clean morphology;
mix SAR-only into optical-SAR correspondence;
treat GM_RM011 blocked rows as unannotated;
write GT residual or GT peak position into runtime priors;
commit MatlabToolboxZB.zip or any zip.
```

## Expected Research Outcome

The exploration should clarify whether the natural route is:

```text
optical support region
-> SAR scatter-cluster structure
-> SAR temporal persistence
-> gated optical/SAR association
-> later global optimization
```

The main question is not:

```text
Which peak is the vehicle?
```

The main question is:

```text
Under what optical state and SAR scatter structure is it legitimate to associate an optical object hypothesis with a SAR temporal scattering tube?
```
