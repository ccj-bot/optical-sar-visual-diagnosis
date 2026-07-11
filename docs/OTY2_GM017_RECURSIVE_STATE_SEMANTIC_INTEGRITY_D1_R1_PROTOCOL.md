# OTY2 GM_RM017 Recursive State Semantic Integrity D1-R1 Protocol

Updated: 2026-07-12

This protocol defines `WGV3.6B-D1-R1 GM_RM017 Recursive State Semantic Integrity Repair`. It is a repair layer over D1, not a new physical model stage and not a final dynamic-member validation stage.

## Scope

D1-R1 preserves original D1 artifacts as a frozen control and writes only new `d1_r1` artifacts. It may read:

- Frozen P0 calibration artifacts and runtime-safe parameters.
- Current and historical SAR gray frames up to the current loop frame.
- The D1 generator source only as a component-extraction helper.
- The D1-R1 generator's own prior recursive state.

D1-R1 generation must not read paired annotations, SAR 371-394 reference labels, evaluation outputs, future SAR frames, final boxes, selector/ranking outputs, or GT-derived correction fields.

SAR 371-394 is named only as a `regression and mechanism-diagnosis window / 事后诊断窗口`. It is not a fresh holdout claim.

## Required Commands

```powershell
D:\MINICONDA\envs\py311\python.exe -m py_compile tools\diagnostics\run_oty2_wgv3_6b_d1_r1_gm017_semantic_integrity_generate.py tools\diagnostics\run_oty2_wgv3_6b_d1_r1_gm017_semantic_integrity_evaluate.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_d1_r1_gm017_semantic_integrity_generate.py generate
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_d1_r1_gm017_semantic_integrity_generate.py verify-replay
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_wgv3_6b_d1_r1_gm017_semantic_integrity_evaluate.py evaluate
```

Generation and evaluation are intentionally separate. There is no combined `all` command.

## Semantic Repairs

D1-R1 repairs four D1 semantic risks:

1. Background tracks enforce one component per background track per frame and one background track per component per frame. Background support uses `support_unique_frame_count`, not same-frame observation count.
2. Response tracks use one current evidence state plus a separate highest historical state. `motion_shell_candidate` never implies `same_motion_supported`.
3. Relative structure residual is a real gate. Selected associations must pass response prediction, motion consistency, relative structure, and background-conflict gates; temporal support remains explicit and controls stronger evidence states.
4. First post-missing reassociation is only `reappearance_candidate`; later consecutive support is required for provisional or confirmed reappearance.

## Admission Policies

D1-R1 runs three fixed admission policies over the same extraction, association, background, and runtime parameter stream:

- `ALL_ASSOCIATED_TRACKS`
- `TEMPORALLY_SUPPORTED_ONLY`
- `STRUCTURE_CONSISTENT_ONLY`

These are evidence-admission ablations, not selectors and not rankers. Each frame records eligible tracks, excluded tracks, exclusion reasons, observation-supported position, posterior correction, and fallback status.

## Evaluation Boundary

The evaluator must verify the pre-evaluation seal before opening the diagnosis reference labels. It checks:

- generator source SHA,
- frozen runtime parameter SHA,
- frozen generation artifact SHAs,
- replay identity,
- P0 artifacts unchanged from `1a3edd97d17b167ca63d9d70651dad29d5601f5b`,
- D1 artifacts unchanged from `57a82b11ec715539fe054bbad490f069a503c928`.

Evaluation compares original D1, D1-R1 A/B/C, no-observation ablation, P0 absolute-frame linear baseline, and P0 static baseline. A D1-R1 performance gain over D1 is useful evidence, but not sufficient for physical dynamic membership.

## Final Status Semantics

`D1_R1_SEMANTIC_INTEGRITY_READY=PASS` means the recursive-state evidence semantics are internally auditable.

`D1_R1_PHYSICAL_DYNAMIC_MEMBERSHIP_READY=NOT_READY` remains valid when semantic repair passes but the strict evidence is still insufficient to claim stable physical dynamic membership. Code execution, lower error, or visually plausible local responses must not be promoted into final vehicle membership.
