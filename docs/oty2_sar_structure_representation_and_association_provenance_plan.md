# OTY2 SAR Structure Representation And Association Provenance Plan

Updated: 20260703_112931

This plan defines a mechanism exploration stage. It is not OTY3, not final automatic annotation, not selector/ranking, not training, not threshold tuning, and not an identity-truth claim.

## Project Understanding Before Running

1. Current candidate cannot be understood as a simple box candidate.
2. The safer layered candidate semantics are:

- optical object hypothesis
- support region / feasible domain
- SAR scatter-structure candidate / structure tube
- posthoc association candidate

3. The key question is not whether the support region contains a bright point. The key question is how SAR target structure is represented inside a still-large compressed support region, and when that structure can be associated with a specific optical object hypothesis under provenance limits.

## Fixed Ledger Boundary

- paired_optical_object_sar_gt = 215
- blocked_missing_gm011_object_stream = 195
- sar_only_gt = 20
- dropout/no_oty_iou_match/temporal continuation pool = 12

The 215 paired rows are frame-level posthoc pairs, not all GT and not independent physical identity truth. GM_RM011 is blocked by missing current OTY optical object stream, not by missing annotation. SAR-only rows are morphology references only. Dropout/no-match rows are temporal continuation or existence support only.

## Exploration Lines

- Line A: SAR structure vocabulary. Convert bright-point observations into compact, multi-peak, spread, diffuse, weak, jumping, stable-tube, and unstable-tube structure semantics.
- Line B: Support region to structure observation. Separate support exists, SAR structure exists, vehicle-like structure exists, unique structure exists, and posthoc association candidate exists.
- Line C: Structure by counterfactual cross-check. Explain true, random, range-shift, azimuth-shift, wrong-object, and wrong-frame outcomes without reducing them to hit rates.
- Line D: SAR temporal tube probe. Keep single-frame cluster evidence separate from temporal persistence and dropout existence support.
- Line E: Association provenance and failure transition. Define which gates are runtime-safe, SAR observation, posthoc validation, manual/review anchor, or hypothesis only.

## Local-Optimization Guard

This run must answer mechanism questions instead of optimizing top-k or selector metrics. It introduces no selector/ranking, no thresholds, no candidate boxes, and no training. It reuses existing SAR observation and counterfactual outputs to build vocabulary, provenance, and transition tables.

## Inputs

- scatter_cluster_structure_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_scatter_cluster_structure_probe_20260703_095159.csv`
- temporal_cluster_association_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_temporal_cluster_association_probe_20260703_095159.csv`
- counterfactual_support_validation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_support_validation_20260703_102237.csv`
- counterfactual_confounder_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_confounder_triage_20260703_105108.csv`
- wrong_object_overlap_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wrong_object_overlap_triage_20260703_105108.csv`
- wrong_frame_offset_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_wrong_frame_offset_triage_20260703_105108.csv`
- azimuth_shift_overlap_triage_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_azimuth_shift_overlap_triage_20260703_105108.csv`
- gated_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gated_association_scatter_cluster_summary_20260703_095159.json`
- parallel_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_parallel_mechanism_exploration_summary_20260703_102237.json`
- confounder_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_counterfactual_confounder_triage_summary_20260703_105108.json`
