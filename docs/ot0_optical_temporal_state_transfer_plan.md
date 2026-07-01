# OT0 Optical Temporal State Transfer Plan

## Line Goal

The OT line is an isolated optical temporal state transfer mechanism audit. It starts from the optical temporal stream and asks whether one vehicle can be described as a runtime-safe state trajectory before any SAR band transfer is attempted.

The target mechanism is:

```text
optical frame sequence
-> runtime-safe optical detections or tracklets
-> optical vehicle-state trajectory
-> future state-conditioned SAR fan/range band
-> posthoc SAR GT/evidence diagnosis
```

OT0 only covers the first two steps. It does not require every optical frame to contain a vehicle or a detection row. A contiguous vehicle-bearing substream is sufficient for the OT0 mechanism audit when the source provides runtime-safe bbox geometry. OT0 does not generate SAR fan/range bands, localization decisions, selector scores, thresholds, or training data.

## Relationship To V0 Visual Diagnosis

V0 is case-level visual diagnosis. It overlays optical/SAR transfer context, candidate families, factor summaries, and temporal context for human review.

OT0 is upstream of V0-style case review. It audits whether the optical stream can provide a runtime-safe state source: bbox geometry, frame order, boundary contact, truncation proxy, neighbor ambiguity, and tracklet candidate edges. OT0 can reuse the repository boundary and visualization-first discipline, but it must not modify V0 runner code or reinterpret V0 panels as track-level identity evidence.

## Isolation From Legacy C1/C2/G2

This line is not a continuation of legacy C1/C2/G2, A008 scoring, candidate pool tuning, or selector design.

Allowed legacy-adjacent use in OT0 is limited to input-source inventory and field auditing when a table contains runtime-like optical bbox geometry. Such a table remains a partial source unless it is a full optical detector/tracker output with explicit runtime-safe identity semantics.

Forbidden in OT0:

- selector, G2, threshold, calibration, or training work
- A008 score or reliability claims
- candidate pool expansion or ranking changes
- treating `candidate_source_family` as an active rule
- treating C1.4 partial components as confirmed same-target identity
- treating `group_id` as a track id without semantic proof

## Runtime Vs Posthoc Boundary

Runtime-safe OT0 inputs:

- optical frame sequence and frame order
- optical image dimensions
- runtime detection/inference rows when they contain bbox geometry
- bbox geometry and frame number fields
- same-frame neighbor boxes from the same runtime source
- configured scene paths
- annotation/review queue optical bbox fields only when used as a runtime-like geometry inventory and all final/review/manual columns are excluded

Posthoc-only inputs:

- SAR GT boxes
- final/manual/oracle annotations
- IoU, center error, reviewed best candidate, or coverage accounting
- manual identity corrections
- shared-offset replacement decisions
- A019/A021/manual labels

OT0 writes posthoc boundary reports but does not consume GT/final/oracle/manual labels to build tracklets, SAR bands, or candidates.

## GT Use Boundary

GT is reserved for later OT2 coverage audit only. In OT0:

- GT must not create runtime tracklets.
- GT must not create runtime SAR bands.
- GT must not filter, rank, or gate detections.
- GT can only be mentioned as a future posthoc source in documentation and manifest schema.

## Route

OT0: reconstruct optical vehicle-state availability and partial tracklet candidate edges from runtime-safe optical detections or runtime-like optical bbox inventories. Vehicle-bearing continuous substreams are valid OT0 inputs; empty/no-car frames do not need synthetic rows.

OT1: transfer an OT0 state trajectory into a SAR fan/range band without SAR GT.

OT2: audit SAR GT coverage of OT1 bands posthoc.

OT3: sample SAR raw-gray evidence along OT1 bands posthoc or review-only, without classifier thresholds.

## OT0 Outputs

- `ot0_runtime_input_inventory.csv`: scene paths, frame counts, optional table status, and source-use policy.
- `ot0_optical_detection_field_audit.csv`: field-level audit of bbox, frame, track, forbidden, provenance, and posthoc columns.
- `ot0_tracklet_candidate_edges.csv`: runtime-geometry-only edge candidates when usable bbox rows exist.
- `ot0_tracklet_blockers.md`: written when a usable runtime bbox source or candidate edges are unavailable.
- `ot0_optical_tracklet_components_pilot.csv`: component pilot from candidate edges; not a same-target proof.
- `ot0_optical_state_timeseries_pilot.csv`: bbox state features for pilot components.
- `ot0_optical_state_timeseries_schema.json`: stable schema for future full-stream state time series.
- `ot0_runtime_posthoc_boundary.md`: explicit allowed, posthoc-only, and forbidden fields.
- `ot0_blockers_and_next_steps.md`: blockers before OT1.
- `ot0_input_source_lineage.md`: source provenance and use boundary.
- `ot0_missing_path_report.csv`: missing path inventory.
- `ot0_summary.json`: machine-readable run summary.
- `ot0_report.md`: human-readable run report and boundary check.

If at least one tracklet candidate edge is produced, OT0 also writes:

- `visualizations/optical_track_strip.html`
- `visualizations/bbox_center_trajectory_overlay.svg`
- `visualizations/state_transition_strip.svg`

If not, it writes a missing-field/blocker visualization instead.
