# OTY2 Support-Region Range Narrowing And Peak Competition Plan

Updated: 20260703_091849

This plan defines a posthoc audit for narrowing `broad_unknown_range_prior` into range-band hypotheses and measuring SAR peak competition. It is not OTY3, not final automatic annotation, not selector/ranking, and not training or threshold tuning.

## Boundary

- Broad fan support remains the runtime-safe baseline from the previous probe.
- Complete shape quantile, object smoothing, and scene residual bands are posthoc hypothesis audits.
- SAR image content is used only for observation extraction inside optical-derived support regions.
- SAR GT is used only for coverage and residual validation columns.
- GT crop extraction, annotation proposals, selector scores, ranking, tuned thresholds, and identity truth are out of scope.

## Compared Support Modes

A. `broad_fan_baseline`: previous `broad_unknown_range_prior`.
B. `complete_shape_quantile_range_band`: complete/stable optical shape versus SAR radius posthoc quantile relation.
C. `state_conditioned_range_band`: narrower complete bands and wider edge/truncated/duplicate/dropout bands.
D. `object_smoothed_range_band`: posthoc object-level range trend smoothing to reduce single-frame jitter.
E. `scene_residual_range_band`: scene-level residual diagnostic only; GT residual must not become runtime prior.

## Peak Competition Diagnostics

The audit extracts top1/top2 peak values and locations, top1/top2 ratio, top1/background and top2/background ratios, local peak counts above background percentile, scatter centroid, centroid residual, short-window peak persistence, and tube-level continuity.

## Generated Outputs

- plan_doc: `D:\profile\research\optical-sar-visual-diagnosis\docs\oty2_support_region_range_narrowing_and_peak_competition_plan.md`
- range_band_mode_comparison_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_band_mode_comparison_20260703_091849.csv`
- support_region_peak_competition_audit_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_support_region_peak_competition_audit_20260703_091849.csv`
- state_conditioned_range_band_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_state_conditioned_range_band_probe_20260703_091849.csv`
- object_smoothed_range_band_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_object_smoothed_range_band_probe_20260703_091849.csv`
- range_narrowing_tube_continuity_probe_csv: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_tube_continuity_probe_20260703_091849.csv`
- range_narrowing_peak_competition_report_md: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_peak_competition_report_20260703_091849.md`
- range_narrowing_peak_competition_summary_json: `D:\profile\research\optical-sar-visual-diagnosis\reports\oty2\oty2_range_narrowing_peak_competition_summary_20260703_091849.json`
- workspace_log: `D:\profile\research\workspace\logs\oty2_range_narrowing_peak_competition_audit_20260703_091849.log`
