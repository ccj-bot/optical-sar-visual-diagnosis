# V0.1 Input Source Registry

This registry separates runtime candidate banks, frozen ranked candidates, partial factor audits, posthoc accounting, and manual probe rows. Posthoc/final/oracle/GT fields remain diagnostic-only and cannot enter runtime generation or ranking.

| source_id | scene | stage | origin | kind | exists | rows | targets | geometry | rank | frozen_rank | family | wedge/ray/signed | temporal | posthoc_iou | allowed_use | forbidden_use |
|---|---|---|---|---|---:|---:|---:|---|---|---|---|---|---|---|---|---|
| workspace_c1_1_candidate_bank | GM_RM019 | C1.1 | workspace | runtime_candidate_bank | True | 132 | 22 | True | False | False | True | False | True | False | candidate overlay and transfer/factor context for GM_RM019 pilot rows | selector rule, threshold tuning, posthoc ranking, cross-scene generalization |
| workspace_c1_2_extended_candidate_bank | GM_RM019 | C1.2 | workspace | runtime_candidate_bank | True | 387 | 22 | True | False | False | True | True | True | False | bounded visual overlay of extended candidate families including wedge/ray/signed-derived candidates | A008 scoring, selector rule, threshold tuning, calibrated reliability claims |
| workspace_c1_2_partial_factor_table | GM_RM019 | C1.2 | workspace | partial_factor_audit | True | 387 | 22 | True | False | False | True | True | True | False | factor breakdown context with missing fields preserved | frozen ranked candidate table, calibrated selector, A008 score |
| workspace_c1_3_partial_factor_table | GM_RM019 | C1.3 | workspace | partial_factor_audit | True | 387 | 22 | True | False | False | True | True | True | True | temporal/context factor audit visualization with missing identity support marked | runtime candidate generation, selector rule, threshold tuning |
| workspace_c1_4_partial_factor_table | GM_RM019 | C1.4 | workspace | partial_factor_audit | True | 387 | 22 | True | False | False | True | True | True | True | tracklet/signed partial-factor visualization and missing-field accounting | C1.4 frozen rank, calibrated selector, A008 score |
| synthesis_c1_3_structural_candidate_bank | GM_RM019 | C1.3 | synthesis_mirror | runtime_candidate_bank | True | 541 | 22 | True | False | False | True | True | True | True | structural candidate overlay and pool-ceiling visual review | posthoc accounting, selector scoring, GM_RM011 generalization |
| synthesis_c1_3_posthoc_accounting | GM_RM019 | C1.3 | synthesis_mirror | posthoc_accounting | True | 25 | 25 | False | False | False | False | False | False | True | diagnostic sampling and failure explanation only | runtime candidate table, generation, ranking, selector rule |
| synthesis_c1_4_frozen_ranked_candidates | GM_RM019 | C1.4 | synthesis_mirror | frozen_ranked_candidate_table | True | 541 | 22 | True | True | True | True | True | True | True | deterministic input-order visualization and top-k visual review | calibrated selector, A008 scoring, threshold tuning, proof of structural success |
| synthesis_c1_4_posthoc_topk_accounting | GM_RM019 | C1.4 | synthesis_mirror | posthoc_accounting | True | 520 | 25 | False | False | False | False | False | False | True | diagnostic case selection and posthoc/debug reporting only | runtime candidate table, generation, ranking, selector rule |
| manual_sar_only_blocked | GM_RM019 | manual | manual | manual_probe | False | 0 | 0 | False | False | False | False | False | False | False | SAR-only blocked visual placeholder and missing-prior accounting | final-box backfill, runtime prior synthesis, candidate generation |
| manual_gmrm011_probe | GM_RM011 | manual | manual | manual_probe | False | 0 | 0 | False | False | False | False | False | False | False | geometry/path/convention probe visual panels | copy GM_RM019 candidate chain, selector rule, cross-scene conclusion |
| manual_gmrm017_reference | GM_RM017 | manual | manual | manual_probe | False | 0 | 0 | False | False | False | False | False | False | False | reference/control visual panels | turn old proxy/selector experience into runtime rule |

## Lineage Notes

- `workspace_c1_1_candidate_bank`: Workspace C1.1 audit-only pilot candidate bank; not a formal candidate bank and no regenerated wedge/ray/signed rows.
- `workspace_c1_2_extended_candidate_bank`: Workspace C1.2 extended candidate bank; separate from C1.2 partial factor audit table.
- `workspace_c1_2_partial_factor_table`: A008-equivalent partial factor table; not a frozen ranked candidate table.
- `workspace_c1_3_partial_factor_table`: Workspace C1.3 temporal identity audit table; not synthesis C1.3 structural candidate bank.
- `workspace_c1_4_partial_factor_table`: Workspace C1.4 runtime tracklet partial factor table; distinct from synthesis C1.4 frozen ranked candidates.
- `synthesis_c1_3_structural_candidate_bank`: Synthesis mirror C1.3 structural candidate bank; separate from workspace C1.3 partial factor table.
- `synthesis_c1_3_posthoc_accounting`: Posthoc coverage accounting table without candidate geometry; cannot load runtime candidates.
- `synthesis_c1_4_frozen_ranked_candidates`: Synthesis C1.4 frozen ranked candidates pilot; not the workspace C1.4 partial factor table.
- `synthesis_c1_4_posthoc_topk_accounting`: C1.4 posthoc top-k accounting; no candidate geometry and no runtime candidate authority.
- `manual_sar_only_blocked`: Manual SAR-only blocked row; missing runtime optical prior is explicit.
- `manual_gmrm011_probe`: Manual GM_RM011 probe until a reproduced candidate input chain exists.
- `manual_gmrm017_reference`: Manual GM_RM017 reference/control rows; not a runtime rule source.
