# V0.0 Inheritance Readiness Report

## Readiness

Current inheritance is sufficient for a bounded V0.1 input source alignment round, but not sufficient for V0.1 scoring, selector, threshold, G2, or A008 scoring.

The repo now has:

- historical archive docs in `docs/archive/`
- executable guidance docs in `docs/guidance/`
- V0 summary snapshots in `reports/v0/`
- a case review sheet template in `reports/v0_case_review_sheet_template.csv`

## Inheritance Gap Count

From `docs/guidance/inheritance_gap_audit.md`:

- complete: 11
- partial: 5
- missing: 0

## Still Missing

1. C1.4 frozen ranked candidates need source alignment separate from workspace partial factor tables.
2. C1.3 structural candidate bank needs case-level visual review.
3. GM_RM011 still lacks the GM_RM019-level candidate input chain.
4. Optical range prior failure remains a hypothesis requiring visual confirmation.
5. Human review sheet is not populated.

## Recommendation

Next round should be V0.1 input source alignment, not new panels and not scoring.

Recommended V0.1 scope:

- align C1.2 extended candidate bank, C1.3 structural bank, C1.4 frozen ranked table, and workspace partial factor tables as separate named input sources
- expand `manifests/v0_sample_manifest.csv` toward 20-40 cases
- populate `reports/v0_case_review_sheet_template.csv` from visual review
- keep missing fields explicit

## Forbidden Scope Remains

- no selector
- no threshold
- no G2
- no A008 scoring
- no posthoc/final/oracle/GT leakage into runtime generation or ranking
- no raw large image copies into Git

## Required Reading

Every future Codex round must first read `docs/guidance/README.md`.

## Conversation-Derived Guidance Status

Conversation-derived notes have been added under `docs/guidance/`:

- `conversation_derived_research_notes.md`
- `research_intent_not_to_lose.md`
- `visual_diagnosis_requirements_from_discussion.md`
- `range_prior_rethink_notes.md`
- `temporal_usage_rethink_notes.md`
- `candidate_quality_rethink_notes.md`
- `gmrm011_caution_notes.md`

These files capture research intent that may not be fully reconstructable from legacy repository artifacts alone.

There may still be knowledge that exists only in discussion history, especially around robust distance regression behavior and case-level visual impressions. This is acceptable only if future rounds continue to structure those judgments into guidance or review artifacts before implementation.

The next round can enter V0.1 input source alignment, but it must first read `docs/guidance/README.md` and must remain outside selector, threshold, G2, and A008 scoring.
