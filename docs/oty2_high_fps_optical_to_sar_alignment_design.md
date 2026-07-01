# OTY2 High-FPS Optical-to-SAR Alignment Design

OTY2 prepares temporal alignment between the optical state stream and SAR
high-FPS frame/window candidates. It is an audit contract only. It does not
localize vehicles in SAR and does not generate SAR fan/range bands.

## C1. OTY2 Goal

OTY2 audits:

```text
OTY1 / OTY1a optical state stream
-> optical frame time representation
-> SAR high-FPS frame/window association
```

OTY2 does not do:

- SAR fan/range band generation
- SAR GT coverage
- SAR evidence sampling
- annotation proposal
- selector/ranking/scoring

## C2. Inputs

Runtime-safe OTY2 inputs may include:

- OTY1 optical tracklet state timeseries
- OTY1 optical tracklet component table
- OTY1a merge candidate review table
- optical frame index
- SAR frame index
- optional timestamp metadata if available
- scene config frame inventory

OTY2 must not use:

- SAR GT
- final/manual/oracle/review fields
- posthoc IoU
- selector/G2/A008
- SAR evidence

## C3. Alignment Modes

`timestamp_exact`
: Real optical and SAR timestamps are available. Frame mapping is derived from
timestamp proximity and reported uncertainty.

`timestamp_offset_scale`
: Start/stop time or FPS ratio is known. OTY2 estimates SAR windows using offset
and scale, then reports residual uncertainty.

`frame_ratio_hypothesis`
: Only frame counts are available. OTY2 may create a ratio-based hypothesis, but
confidence must remain hypothesis-level.

`manual_anchor_hypothesis`
: A small number of human anchors may be used as alignment hypotheses. These
anchors are not GT and must not become identity or localization truth.

`unknown_alignment`
: Insufficient timing information exists. OTY2 should output a blocker instead
of pretending optical frames map to SAR frames.

OTY2 must not assume:

```text
optical_frame_num == sar_frame_num
```

## C4. Output Contract

Future OTY2 output files should include:

- `oty2_alignment_frame_map.csv`
- `oty2_alignment_window_candidates.csv`
- `oty2_alignment_uncertainty_report.md`
- `oty2_summary.json`

Suggested fields:

- `scene`
- `optical_frame_num`
- `optical_tracklet_candidate_id`
- `optical_timestamp`
- `sar_frame_center`
- `sar_frame_window_start`
- `sar_frame_window_end`
- `alignment_mode`
- `alignment_confidence_status`
- `time_delta_ms`
- `uncertainty_frames`
- `uses_real_timestamp`
- `uses_manual_anchor`
- `alignment_policy`

These outputs are temporal alignment candidates only. They are not SAR
localization results.

## C5. OTY1a-to-OTY2 Consumption Rules

- OTY2 may consume nonambiguous OTY1a review candidates as optional candidate
  continuity hints.
- OTY2 must not treat `ambiguous_competing_merge` as merged identity.
- OTY2 must preserve multiple hypotheses for ambiguous merge candidates instead
  of force-merging them.
- GM_RM019 `oty1_tracklet_0039 -> oty1_tracklet_0045` can be a case study, but
  it must not be hard-coded as a rule.

## Boundary Statement

OTY2 is allowed to prepare high-FPS optical-to-SAR temporal alignment only. It
does not enter SAR fan/range band generation, SAR GT coverage, SAR evidence
sampling, selector/G2/A008 scoring, threshold tuning, training, or annotation
proposal.
