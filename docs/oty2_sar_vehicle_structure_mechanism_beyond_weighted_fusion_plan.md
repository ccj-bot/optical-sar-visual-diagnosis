# OTY2 SAR Vehicle Structure Mechanism Beyond Weighted Fusion Plan

Updated: 20260703_151500

This plan defines a divergent OTY2 mechanism exploration. It is not OTY3, not an automatic annotation proposal, not selector/ranking, not training, not threshold tuning, and not identity truth.

## Purpose

The current question is how vehicle-like SAR evidence is represented inside a still-large optical-derived support region. Weighted evidence fusion is treated as a small diagnostic form, not the main line.

## Representation Lines

- 442 SAR GT reference / fallback fan valid-mask audit.
- SAR structure primitives from SAR-side GT/reference patches.
- Structure composition hypotheses that do not output final boxes.
- Primitive graph probes for competing components and confounders.
- Temporal tube probes that split vehicle-like persistence from background persistence.
- Optical-conditioned structure expectations.
- Visual review cards and atlas for human mechanism inspection.

## Fixed Boundaries

- 215 paired rows are frame-level posthoc pairs, not all GT and not identity truth.
- 195 GM_RM011 rows are waiting for object stream recovery, not unannotated.
- 20 SAR-only rows are morphology references only.
- 12 dropout/no-match rows are temporal continuation/existence support only.
- SAR GT and SAR image observations may validate/posthoc-observe structure, but must not construct runtime optical priors.

## Inputs

- gt_accounting_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_sample_accounting_audit_20260702_192810.csv`
- correspondence_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_gt_correspondence_mechanism_audit_20260702_190435.csv`
- support_observation_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_structure_observation_20260703_112931.csv`
- structure_crosscheck_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_structure_counterfactual_crosscheck_20260703_112931.csv`
- temporal_tube_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_structure_temporal_tube_probe_20260703_112931.csv`
- provenance_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_sar_structure_representation_and_association_provenance_summary_20260703_112931.json`
