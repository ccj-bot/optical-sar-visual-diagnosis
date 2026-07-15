# OTY2 S0-M SAR GT Structure Foundation Protocol

Date: `2026-07-15`
Frozen base: `1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5`
Branch: `feature/oty2-sar-gt-structure-foundation`

## Purpose and boundary

S0-M freezes the deterministic SAR imaging-valid mask, re-labels all 442 GT rows against it, establishes residual-independent complete-vehicle mapping eligibility, audits optical pose/proxy-point bias, evaluates center and GT-azimuth-interval error, compares bounded mapping models, and prepares—but does not execute—an S1-L frame-eligibility ledger.

It does not consume P1-F propagation/recovery outputs, change P0 hard synchronization, change P1-E canonical identity, infer `vehicle_response_mask`, generate candidates, run a Gate/selector/ranking/oracle, train a model, perform automatic annotation, or start S1-L structure analysis.

## Authoritative inputs

- P0 assets and fixed 24/50 hard-sync manifests from `1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5`.
- P1-E canonical registry, frame states, vehicle-level roles, reference boxes, and identity provenance from the same frozen base.
- Three complete optical streams and three 766-frame SAR gray/pseudocolor streams under `D:\profile\research\data`.
- The reviewed 442-row SAR GT corpus and S0 visual-review atlas.

SAR gray at 50 fps remains authoritative. Pseudocolor inherits the same-index gray timestamp. GT does not change synchronization or optical identity.

## Fixed mask rule

`imaging_valid_mask` is the static `2308 x 1334` fan defined by origin `(1154.0,1330.6)`, radius `1332.7 px`, and azimuth `[-90,90] deg`. Its pixel count and hash must be reproduced on every run. It remains distinct from `fixed_black_region_inside_mask`, `display_nonzero_mask`, `gt_box_region`, and the unavailable `vehicle_response_mask`.

All later SAR mapping/corridor operations must be restricted to this mask.

## Eligibility rule

The audit first computes Mask relation, optical completeness/boundary status, identity confidence, GT quality/continuity, direct neighboring-GT competition, and optical-only pose. Only then may it compute mapping predictions or residuals. Exclusion reasons must never mention the residual magnitude.

Allowed values:

- `calibration_gold`
- `calibration_usable`
- `heldout_gold`
- `heldout_usable`
- `mask_clipped_diagnostic`
- `pose_or_geometry_diagnostic`
- `identity_conflict`
- `exclude`

## Mapping and pose rule

Development complete anchors may fit the model. Heldout complete vehicles are evaluation-only. Validation must be whole-vehicle; if only one development vehicle remains, leave-one-vehicle-out is explicitly not estimable. Pose comes from complete optical appearance only. Independent pose-conditioned formulas are forbidden without repeated development and heldout evidence that cannot be explained by Mask, optical truncation, or GT geometry.

Center error and distance to both the full GT azimuth interval and the GT-intersection-mask interval are mandatory. Corridor evaluation must report containment of the entire interval, width, and expansion relative to GT azimuth width.

## Reproducibility

Run in order:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_s0_sar_gt_structure_foundation_audit.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_s0m_mask_anchor_pose_mapping_audit.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_s0m_mask_anchor_pose_mapping_outputs.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_s0_sar_foundation_outputs.py
```

Temporary visual assets remain under `D:\profile\research\workspace\output\oty2_s0_sar_gt_structure_foundation_20260715` and are not committed.

## Decision order

1. freeze `imaging_valid_mask`;
2. re-label all GT/Mask relations;
3. select Mask-inside complete optical anchors;
4. audit pose and proxy-center bias;
5. re-evaluate the old mapping;
6. compare linear, centered-linear, and pinhole LOS models;
7. decide the center function;
8. decide whether pose-dependent corridor width is justified;
9. only then consider S1-L complete-vehicle structure research.

Current result: `S0_SAR_FOUNDATION_PARTIALLY_READY`, `MAPPING_BLOCKED`, S1-L entry not authorized. `imaging_valid_mask` is no longer a blocker; the remaining blockers are the unresolved physical metric grid and insufficient complete-anchor diversity for mapping freeze.
