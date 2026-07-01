# Legacy Handoff

The detailed legacy archive lives in:

- `docs/archive/c1s_legacy_handoff_20260701.md`
- `docs/archive/algorithm_notes_20260701.md`
- `docs/archive/problem_diagnosis_20260701.md`
- `docs/archive/new_repo_transition_plan_20260701.md`

Key inherited state:

- G2 / formal selector = `HOLD`.
- Phase5 = `BLOCKED_FOR_OOF_CALIBRATION`.
- `current_good_proxy` should be treated as `current_local_appearance_clean_proxy`, not as localization reliability.
- Strict replay and recomputed replay must stay separately named.
- GM_RM019 candidate input chain is connected through C1.4/C1S.
- GM_RM011 has not reproduced the same chain.
- SAR-only targets must not be backfilled from final boxes.

This repository inherits diagnostic questions and lightweight accounting references, not legacy execution behavior.
