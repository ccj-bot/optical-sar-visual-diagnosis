# Inheritance Gap Audit

This audit tracks whether critical legacy knowledge has entered the clean repository. `complete` means the knowledge is present in docs/guidance or docs/archive. It does not mean the underlying research problem is solved.

| Item | inherited_status | current_file | missing_detail | required_action |
|---|---|---|---|---|
| P1 strict replay vs recomputed replay conclusion | complete | `docs/archive/c1s_legacy_handoff_20260701.md`; this file | None for inheritance. | Preserve separate naming in future reports. |
| `current_good_proxy` localization-reliability meaning rejected | complete | `docs/legacy_handoff.md`; `docs/guidance/no_go_rules.md` | None for inheritance. | Use `current_local_appearance_clean_proxy` when describing legacy visual cleanliness. |
| P3 missed opportunity: 18 false-current-good holds | complete | `docs/archive/c1s_legacy_handoff_20260701.md` | No case-level review sheet yet. | Include representative cases when expanding manifest. |
| C0 GM_RM019 / GM_RM011 missing candidate_bank/A008/frozen-ranked chain | complete | `docs/archive/c1s_legacy_handoff_20260701.md`; `docs/guidance/old_pipeline_file_lineage.md` | GM_RM011 still lacks reproduced chain. | Keep GM_RM011 as probe until input source alignment is done. |
| C1-C1.4 GM_RM019 candidate input chain | complete | `docs/archive/c1s_legacy_handoff_20260701.md`; `docs/guidance/old_pipeline_file_lineage.md` | V0 manifest only samples a small subset. | Expand manifest after input source alignment. |
| C1.2 wedge/ray/signed mode generation | partial | `docs/guidance/old_pipeline_file_lineage.md`; `docs/guidance/algorithm_spec_full.md` | Mode row formulas are legacy audit formulas, not production formulas. | Preserve provenance and label formulas approximate where needed. |
| C1.3 structural candidate bank | partial | `docs/guidance/old_pipeline_file_lineage.md` | Structural bank is in synthesis mirror; current V0 does not directly align all rows. | Add input source alignment before V0.1 panels. |
| C1.4 frozen ranked candidates | partial | `docs/guidance/old_pipeline_file_lineage.md` | Frozen rank table is not yet wired into manifest as a first-class source. | Align `c1_4_frozen_ranked_candidates_pilot.csv` separately from partial factor tables. |
| Candidate pool ceiling not high enough | complete | `docs/problem_statement.md`; `docs/guidance/root_cause_hypothesis_tree.md` | No visual taxonomy yet. | Use review sheet to explain why ceiling is low. |
| Top1 poor while top20 approaches pool ceiling | complete | `docs/problem_statement.md`; `docs/guidance/failure_case_selection_plan.md` | Need more manually reviewed cases. | Select `top1_bad_top20_good` cases. |
| Optical range prior may be wrongly expressed | partial | `docs/guidance/root_cause_hypothesis_tree.md`; `docs/guidance/algorithm_spec_full.md` | Hypothesis exists but is not visually confirmed across scenes. | Run input source alignment and review range-band panels. |
| Structural candidates generated but no runtime factor layer | complete | `docs/archive/problem_diagnosis_20260701.md`; `docs/guidance/project_principles.md` | None for inheritance. | Do not claim structural selector success. |
| Temporal evidence is shallow | complete | `docs/archive/c1s_legacy_handoff_20260701.md`; `docs/guidance/root_cause_hypothesis_tree.md` | No explicit same-target runtime track IDs. | Keep temporal evidence weak until identity support exists. |
| GM_RM011 has not reproduced the chain | partial | `docs/legacy_handoff.md`; `docs/guidance/root_cause_hypothesis_tree.md` | GM_RM011 only has probe/reference placeholders in V0. | Prioritize GM_RM011 input source audit after GM_RM019 alignment. |
| SAR-only targets cannot use final backfill | complete | `docs/guidance/no_go_rules.md`; `docs/archive/c1s_legacy_handoff_20260701.md` | None for inheritance. | Keep SAR-only branch separate and missing if no runtime prior exists. |
| Visualization-first necessity | complete | `README.md`; `docs/project_brief.md`; `docs/guidance/project_principles.md` | None for inheritance. | Future rounds must begin from visual hypotheses. |

## Status Count

- complete: 11
- partial: 5
- missing: 0

## Most Important Remaining Gaps

1. C1.4 frozen ranked candidates are not yet cleanly aligned as a V0 source.
2. C1.3 structural candidate bank is present in archive lineage but not reviewed case-by-case.
3. GM_RM011 still lacks a reproduced candidate input chain.
4. Optical range prior failure is still a hypothesis, not a reviewed conclusion.
5. Human case review sheet is empty, so no scoring or threshold work is justified.
