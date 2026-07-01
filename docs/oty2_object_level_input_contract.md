# OTY2 Object-Level Input Contract

This document defines the object-level optical inputs that a later OTY2 temporal
alignment audit may consume. It does not implement OTY2, SAR alignment, SAR
band generation, SAR GT coverage, SAR evidence sampling, selector output,
training signal, tuned thresholds, or annotation proposal generation.

## Purpose

OTY2 must consume object-level optical hypotheses, not raw detection-level or
tracker-level tables directly. The runtime optical unit is:

```text
object_hypothesis_id
```

A detection box is one optical observation. A tracker id is a main-track
hypothesis. Neither is an identity truth source by itself.

## OTY2 Allowed Inputs

OTY2 may consume these P4G outputs:

```text
oty1t_object_hypotheses_generalized.csv
oty1t_object_frame_state_timeseries_generalized.csv
oty1t_object_orphan_observations.csv for review/uncertainty only
oty1t_object_ambiguity_report.md for blocker context only
```

The object hypotheses provide the optical object units. The frame-state stream
provides the per-frame optical observations and uncertainty states. Orphan and
ambiguity outputs are review context only; they must not silently create object
identity.

## OTY2 Forbidden Direct Inputs

OTY2 must not directly consume:

```text
OTY0 detection table directly
OTY1 tracklets directly
OTY1a merge edges directly
OTY1t tracker assignments directly
SAR images
SAR GT
final/manual/oracle/review fields
selector/G2/A008
training/tuned thresholds
annotation proposals
```

Those sources may remain audit context for earlier stages, but the OTY2 runtime
contract starts from the P4G object-level outputs.

## Interpretation Policy

- `object_hypothesis_id` is the optical unit.
- `primary_det_id` and the main track provide temporal continuity.
- `secondary_det_ids` and cluster risk fields provide uncertainty and
  observation-state evidence.
- `recommended_oty2_weight` controls alignment confidence.
- `review_required` does not block temporal alignment, but it lowers
  confidence and must be carried forward.
- `identity_status` never means confirmed identity.
- `same_object_support_level` is support for a review-required object-level
  optical hypothesis, not a physical identity label.
- `oty1t_object_orphan_observations.csv` can only inform review or uncertainty,
  not direct object attachment.

## Required Later OTY2 Outputs

Do not implement these in P4G. A later OTY2 stage should write:

```text
oty2_object_alignment_frame_map.csv
oty2_object_alignment_window_candidates.csv
oty2_object_alignment_uncertainty_report.md
oty2_object_alignment_summary.json
```

These outputs must remain temporal alignment candidates only. SAR search
constraints belong to later stages, and final annotation decisions remain
outside OTY2.

## Boundary Flags

P4G and this contract keep:

```text
posthoc_sources_used_for_runtime_tracking = false
sar_alignment_entered = false
sar_band_entered = false
sar_gt_coverage_entered = false
annotation_proposal_entered = false
identity_truth_claimed = false
```
