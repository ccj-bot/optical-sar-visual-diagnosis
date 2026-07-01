# Old Pipeline File Lineage

This file records which legacy outputs can inform V0 diagnosis. It is a lineage guide, not a permission to run the old pipeline.

## Synthesis Mirror Outputs

| Output directory | Main files | Rows / targets | Candidate overlay | Factor breakdown | Posthoc accounting | frozen_rank | candidate_source_family | wedge/ray/signed fields | Partial factor table | scene_config confusion risk |
|---|---|---:|---|---|---|---|---|---|---|---|
| `gm17_c1_3_gmrm019_structural_candidate_bank_parity_20260701_100609` | `c1_3_structural_candidate_bank_pilot.csv`, `c1_3_posthoc_coverage_accounting.csv`, `c1_3_summary.json`, `c1_3_report.md` | structural bank: 541 rows / 22 targets; posthoc accounting: 25 rows / 25 targets | yes, for structural source-family overlays | partial; mostly source/provenance plus geometry | yes, separate `c1_3_posthoc_coverage_accounting.csv` | no | yes | yes through structural families and C1.2 mode-derived candidates | no, this is structural candidate bank plus accounting | medium: synthesis mirror paths are not the same as workspace C1.3 output |
| `gm17_c1_4_gmrm019_frozen_ranked_candidates_input_audit_20260701_102425` | `c1_4_frozen_ranked_candidates_pilot.csv`, `c1_4_rank_policy_spec.json`, `c1_4_posthoc_topk_coverage_accounting.csv`, `c1_4_summary.json`, `c1_4_report.md` | frozen ranked candidates: 541 rows / 22 targets; posthoc top-k accounting: 520 rows / 26 records/targets | yes, if rank fields are preserved | yes, for deterministic rank group and source-family review | yes, separate top-k accounting table | yes | yes | yes through rank groups and structural families | no, this is the frozen ranked candidate pilot | high: do not confuse with workspace C1.4 partial A008 factor table |

## Workspace Outputs

| Output directory | Main files | Rows / targets | Candidate overlay | Factor breakdown | Posthoc accounting | frozen_rank | candidate_source_family | wedge/ray/signed fields | Partial factor table | scene_config confusion risk |
|---|---|---:|---|---|---|---|---|---|---|---|
| `c1_1_gmrm019_qschema_candidate_input_audit_20260630_233050` | `c1_1_candidate_bank_pilot.csv`, `c1_1_a008_equivalent_runtime_schema.json`, `c1_1_qschema_field_mapping.csv`, `c1_1_summary.json`, `c1_1_report.md` | 132 rows / 22 targets | yes, basic base/factor/topk/visible support | limited; missing regenerated mode factors | no dedicated posthoc table in this output | no | yes | no regenerated wedge/ray/signed rows | no | low-medium: has SAR paths usable by current scene config |
| `c1_2_gmrm019_mode_regeneration_candidate_parity_audit_20260701_100854` | `c1_2_candidate_bank_pilot_extended.csv`, `c1_2_gmrm019_wedge_modes_pilot.csv`, `c1_2_gmrm019_ray_modes_pilot.csv`, `c1_2_gmrm019_signed_modes_pilot.csv`, `c1_2_a008_equivalent_partial_factor_table.csv`, `c1_2_summary.json` | extended bank: 387 rows / 22 targets; wedge 85 / 22; ray 104 / 22; signed 66 / 22 | yes, best source for wedge/ray/signed source-family overlay | yes, but factor values are partial and audit-only | no formal posthoc table; mode parity only | no | yes | yes | yes | medium: extended candidate bank and partial factor table have different meanings |
| `c1_3_gmrm019_temporal_identity_context_audit_20260701_102308` | `c1_3_a008_equivalent_partial_factor_table_v2.csv`, `c1_3_gmrm019_temporal_context_inventory.csv`, `c1_3_gmrm019_identity_neighbor_context.csv`, `c1_3_gmrm019_signed_direction_refined_pilot.csv`, `c1_3_summary.json` | partial factor table: 387 rows / 22 targets | yes, for same candidates with temporal fields | yes, for partial short-window evidence | no; this is partial factor accounting | no | yes | signed refined fields; wedge/ray inherited from C1.2 context | yes | high: workspace C1.3 is temporal identity audit, not synthesis structural bank |
| `c1_4_gmrm019_runtime_tracklet_reconstruction_audit_20260701_104305` | `c1_4_a008_equivalent_partial_factor_table_v3.csv`, `c1_4_gmrm019_runtime_tracklet_pilot.csv`, `c1_4_tracklet_candidate_edges.csv`, `c1_4_signed_direction_tracklet_refined_pilot.csv`, `c1_4_summary.json` | partial factor table: 387 rows / 22 targets | yes, with tracklet audit fields | yes, for partial tracklet/signed evidence | no; this is partial factor accounting | no | yes | signed tracklet fields; wedge/ray inherited by candidate source | yes | high: do not treat this as C1.4 frozen ranked candidates |

## Warnings

- Do not mistake an A008-equivalent partial factor table for the C1.4 frozen ranked candidate table.
- Do not mix synthesis mirror outputs and workspace audit outputs without labeling the source.
- Do not treat posthoc accounting tables as runtime candidate tables.
- Do not use posthoc coverage or IoU to alter candidate generation or rank.
- Do not infer GM_RM011 readiness from GM_RM019 lineage.
