# OTY2 WGV1.5C closeout review and WGV1.6 readiness

Date: 2026-07-09

## Scope

This is a closeout review for WGV1.5C after commit and push. It verifies that prior SAR evidence inheritance was integrated conservatively and checks whether the next WGV1.6 dual-evidence closure step is safe to design.

This review does not run a new SAR experiment, does not generate SAR-ready annotations, does not generate final boxes, does not generate GT boxes, does not revise annotations, does not create selector/ranking outputs, does not create runtime prediction artifacts, and does not add tracked media or `outputs/` files.

## Commit confirmation

WGV1.5C was committed and pushed before this closeout review.

- Branch: `feature/oty2-posthoc-mechanism-validation`
- Commit: `0858622 Add WGV1.5C prior SAR evidence inheritance audit`
- Push target: `origin/feature/oty2-posthoc-mechanism-validation`
- Post-push divergence check: `0 0`
- Working tree before closeout report: clean

## Inputs reviewed

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md`
- `docs/oty2_gt_support_failure_concept_correction_archive.md`
- `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
- `docs/oty2_gt_local_energy_field_atlas_correction_archive.md`
- `reports/oty2/oty2_wgv1_5_pre_sar_consumption_and_sar_internal_evidence_protocol_20260709.md`
- `reports/oty2/oty2_wgv1_5c_prior_sar_evidence_inheritance_and_alignment_20260709.md`
- `reports/oty2/samples/oty2_wgv1_5c_sar_prior_evidence_ledger_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5c_optical_thread_sar_evidence_alignment_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_5c_sar_evidence_source_provenance_20260709.csv`

## Row-count checks

All required row counts match the WGV1.5C report.

- SAR prior evidence ledger: 60 rows.
- Optical-thread/SAR alignment audit: 50 rows, matching the WGV1.5A contract row count.
- Source provenance table: 15 rows.
- WGV1.5A contract reference: 50 rows.

## Boundary checks

The WGV1.5C artifacts keep the intended boundary.

- Ledger `usable_for_wgv15`: all 60 rows are `posthoc_mechanism_evidence_only; pre_sar_prioritization_or_protocol_design_only`.
- Alignment `wgv15a_consumption_status`: 49 rows are `pre_sar_only`; 1 row is `blocked`.
- Alignment `allowed_next_use`: only documentation, SAR review backlog selection, or pre-SAR prioritization is allowed.
- Provenance rows involving SAR GT or SAR image content: all are `runtime_prior_safe=no_posthoc_only`.
- The missing requested dropout filename is explicitly recorded as `missing_requested_csv_alias` with `allowed_use=none`.
- No row upgrades weak optical evidence using inherited SAR overlap alone.
- No row relaxes preserved optical boundaries without independent SAR boundary evidence.

SAR-ready remains no / blocked. WGV1.5C does not confirm identity.

## Inherited SAR evidence coverage

The ledger has broad enough posthoc coverage to support a small-window WGV1.6 design.

Evidence categories:

- `vehicle_like_scatter`: 19 rows.
- `temporal_continuity`: 16 rows.
- `unknown_or_insufficient_evidence`: 12 rows.
- `competitor_or_multi_target_signal`: 6 rows.
- `boundary_support`: 4 rows.
- `background_or_static_reflector_risk`: 3 rows.

Scene coverage:

- `GM_RM011`: 6 rows.
- `GM_RM017`: 29 rows.
- `GM_RM019`: 25 rows.

Pool coverage:

- GM_RM011 waiting-object-stream evidence is present as scene-level SAR morphology evidence.
- Paired GM_RM017/GM_RM019 evidence is present through GT-anchored morphology, scatter-cluster, temporal-cluster, and support-failure diagnostics.
- Dropout/no-match special-pool evidence is present through actual SAR posthoc support and temporal continuation tables.
- SAR-only and component-level atom/part/shell evidence are retained as morphology reference material, not paired correspondence.

## Required item review

GM_RM011 M005 and M016 remain preserved optical boundaries. Both are `boundary_preserved`, `pre_sar_only`, and `blocked_due_to_mapping_uncertainty` because inherited SAR rows provide only scene-level evidence, not thread-level optical-frame mapping.

GM_RM017 WGV14T001-WGV14T003 remain weak/ambiguous. Their inherited SAR overlaps are posthoc frame-overlap references with mixed support and risk. They are not upgraded and still require independent SAR-internal evidence before any stronger use.

GM_RM017 WGV14V004 remains blocked. It has inherited SAR overlap rows, but WGV1.5A marks it `blocked_for_sar_consumption`; WGV1.5C keeps `blocked_due_to_identity_risk` and allows documentation only until an explicit later protocol exists.

The absent requested dropout file name is handled correctly. The exact file `reports/oty2/oty2_detection_dropout_temporal_sar_support_audit_20260702_200455.csv` is not present, and provenance records the actual inherited SAR-side source as `reports/oty2/oty2_detection_dropout_sar_posthoc_support_audit_20260702_200455.csv`.

## Unresolved risks

- Optical-to-SAR frame mapping remains unresolved for WGV1.5A/WGV1.5C.
- GM_RM011 has useful SAR morphology evidence but no thread-level alignment to WGV1.4b optical threads.
- GM_RM017 has explicit posthoc optical-frame overlaps, but those overlaps mix weak support, temporal instability, competitor ambiguity, and review-required states.
- Boundary evidence is not yet independently closed in SAR. Optical preserved boundaries should only steer later SAR review.
- Inherited SAR evidence is source-level or aggregated evidence. It is not a case-level closure for any single WGV1.6 window.
- The mechanism still needs negative closure: vehicle-like SAR cues must be distinguished from static reflectors, background structure, and nearby vehicles.

## Missing or optional old sources before WGV1.6

No required WGV1.5C inheritance source is missing, except the absent dropout filename that was already recorded and substituted through the actual SAR posthoc support file.

WGV1.6 can start as a small-window design using the current WGV1.5C artifacts. For richer case-level review, WGV1.6 may also consult existing historical sources without treating them as runtime prior construction:

- `reports/oty2/oty2_temporal_drift_physical_consistency_20260704_143456.csv`
- `reports/oty2/oty2_vehicle_shell_grammar_cases_20260704_143456.csv`
- `reports/oty2/oty2_vehicle_part_grammar_relations_20260704_143456.csv`
- `reports/oty2/oty2_physical_structure_failure_modes_20260704_143456.csv`

These are optional WGV1.6 reading inputs, not blockers for readiness.

## WGV1.6 readiness decision

WGV1.6 is safe to start as a design and review stage only.

Recommended WGV1.6 scope: small-window optical-SAR dual-evidence closure audit. It should inspect selected high-value windows and ask whether optical thread evidence plus inherited or posthoc SAR morphology/temporal evidence form a consistent mechanism explanation. It must not produce final annotations.

Candidate windows:

- `GM_RM011_WGV14T001`: short accepted `optical_identity_constraint`.
- `GM_RM011_WGV14T004`: accepted `optical_identity_constraint` around frames 151-166.
- `GM_RM011_WGV14T005`: long frames 231-288 `optical_search_hint_only`, with attention to the 286-292 competitor boundary.
- `GM_RM011_WGV12M005` and `GM_RM011_WGV12M016`: preserved boundary checks.
- `GM_RM017_WGV14T001` through `GM_RM017_WGV14T003`: weak optical threads that must not be upgraded without independent SAR evidence.
- `GM_RM017_WGV14V004`: blocked identity-risk item.

WGV1.6 should keep every result in one of these non-consumption states unless a later explicit protocol changes the boundary:

- `pre_sar_review_only`
- `posthoc_mechanism_consistent`
- `posthoc_mechanism_mixed_or_weak`
- `boundary_review_only`
- `blocked_due_to_mapping_uncertainty`
- `blocked_due_to_identity_risk`

## Closeout conclusion

WGV1.5C was integrated correctly as a posthoc inheritance and conservative alignment audit. It preserves the WGV1.5A consumption contract, records prior SAR evidence without turning it into runtime logic, keeps GM_RM011 boundary cases blocked by mapping uncertainty, keeps GM_RM017 weak threads weak/ambiguous, and keeps WGV14V004 blocked.

The next step may be WGV1.6 small-window dual-evidence closure design, but not WGV1.6 execution or annotation generation.
