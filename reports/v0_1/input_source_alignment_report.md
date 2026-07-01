# V0.1 Input Source Alignment Report

## Working Hypothesis

- H0: The repository has inherited enough guidance/archive context, but V0 remains a bootstrap visualization shell.
- H1: The largest engineering risk is input source lineage confusion, especially C1.4 frozen ranked candidates versus workspace C1.4 partial factor tables.
- H2: If source lineage and fallback behavior are not made explicit first, visual panels can look complete while relying on the wrong input source.
- H3: GM_RM019 is the candidate/range/structure/temporal pilot scene.
- H4: GM_RM017 is only a reference/control scene; legacy proxy experience is not a runtime rule.
- H5: GM_RM011 is a geometry/path/convention probe scene until its candidate chain is reproduced.

## Files Read

Guidance, archive, config, manifest, runner, geometry/io, visualization modules, and V0 report snapshots listed in the V0.1 task request were read before code edits.

## Changed Files

- configs/scene_config.yaml: 1
- manifests/v0_1_sample_manifest.csv: 1
- src/io/config.py: 1
- src/io/manifest.py: 1
- src/io/source_registry.py: 1
- src/visualization/candidate_overlay.py: 1
- src/visualization/factor_breakdown.py: 1
- src/visualization/temporal_strip.py: 1
- src/visualization/transfer_panel.py: 1
- tools/diagnostics/run_v0_visual_diagnosis_bootstrap.py: 1
- docs/v0_1_input_source_registry.md: 1
- reports/v0_1/input_source_registry.json: 1
- reports/v0_1/input_source_alignment_report.md: 1
- reports/v0_1/v0_1_case_review_sheet.csv: 1

## Input Source Lineage

- registry entries: 12
- workspace sources: 5
- synthesis mirror sources: 4
- manual sources: 3
- frozen ranked tables, partial factor audits, posthoc accounting, and manual probes are separate source kinds.

## Fallback Summary

- none

## Scene Coverage Summary

- GM_RM011: 4
- GM_RM017: 4
- GM_RM019: 19

## Sample Type Coverage Summary

- candidate_pool_bad: 3
- factor_topk_best: 2
- gmrm011_probe: 4
- gmrm017_reference: 4
- ray_best: 2
- sar_only_blocked: 2
- signed_best: 2
- top1_bad_top20_good: 4
- top1_good: 2
- wedge_best: 2

## Missing Fields / Paths

- missing field rows: 80
- missing path rows: 2
- v0_1_018: optical_frame -> empty_path ()
- v0_1_019: optical_frame -> empty_path ()

## Boundary Check

- no selector
- no threshold
- no G2
- no A008 scoring
- no posthoc/final/oracle/GT leakage into runtime generation or ranking
- candidate_source_family remains provenance only
- temporal strip is context shell only, not identity-supported track-level temporal evidence

## What Remains Hypothesis

Human review still needs to decide whether failures are optical azimuth, range prior expression, candidate pool ceiling, structural evidence, temporal shallowness, or scene convention.

## What Is Supported By Visual/Accounting Evidence

This run supports source lineage visibility, fallback visibility, bounded sample coverage, and panel generation. It does not support selector, threshold, G2, A008, or mechanism-success claims.

## Next Recommended Action

Fill the human review sheet from the generated panels before authorizing scoring, threshold, selector, or candidate-generation changes.
