# OTY2 S0 SAR GT Structure Foundation Protocol

Date: `2026-07-15`
Frozen base: `1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5`
Branch: `feature/oty2-sar-gt-structure-foundation`

## Purpose

S0 audits the available SAR display products, their coordinate and mask semantics, gray-to-pseudocolor lineage, P1-E canonical-vehicle links to reviewed SAR GT, GT quality, vehicle-level research roles, and the optical-center to SAR display-azimuth mapping.

This stage does not repair optical P1-F identity, consume P1-F propagation/recovery outputs, change P0 hard synchronization, change the P1-E canonical benchmark, infer a vehicle-response mask, generate candidates, run a Gate/selector/ranking/oracle, train a model, or start S1 structure dynamics.

## Authoritative inputs

- P0 asset manifest and fixed 24/50 hard-sync manifests from `1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5`.
- P1-E canonical registry, 8,096 frame-state rows, vehicle-level roles, and detection-to-canonical provenance from `1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5`.
- Three complete optical streams, three complete SAR gray streams, and three complete SAR pseudocolor streams under `D:\profile\research\data`.
- The reviewed 442-row `final_gt_working.csv` and aligned `review_queue.csv`.

The project common-start relation remains an operational frozen assumption, not shared-hardware-clock evidence. SAR gray at 50 fps is authoritative. Pseudocolor inherits the timestamp of the same-index gray frame.

## Coordinate rule

S0 freezes only the reproducible display coordinate:

```text
r_px = hypot(x - 1154.0, y - 1330.6)
theta_deg = atan2(x - 1154.0, 1330.6 - y)
x = 1154.0 + r_px * sin(theta)
y = 1330.6 - r_px * cos(theta)
```

The upstream acquisition/imaging grid, maximum metric range, range/azimuth resolution, PSF, and an authoritative pixel-to-meter transform remain unresolved. `0.03 m/pixel` is retained only as a historical/project-local radial grid-spacing claim, not as proven full-image metric scale or actual resolution.

## Mask rule

`fan_geometry_mask`, `display_nonzero_mask`, and `fixed_black_region_mask` are reproducible display/geometry masks. They are not silently renamed `imaging_valid_mask`. GT boxes are research/evaluation regions and are never vehicle-scattering masks.

## Vehicle and split rule

Canonical links use P1-E benchmark provenance only. The P1-E vehicle-level role is inherited intact; a single canonical vehicle is never split by frame between development and heldout claims. Sparse GT is not interpolated.

## Mapping rule

Mapping is evaluated in `display_fan_azimuth_deg`. Development vehicles fit the model; development validation is leave-one-vehicle-out; heldout vehicles are evaluation-only. No heldout row participates in fitting. Metric error remains blank until the physical grid is resolved.

## Reproducibility and visual review

Run:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_oty2_s0_sar_gt_structure_foundation_audit.py
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\validate_oty2_s0_sar_foundation_outputs.py
```

Temporary contact sheets and case atlases are written only to `D:\profile\research\workspace\output\oty2_s0_sar_gt_structure_foundation_20260715\visual_review` and are not committed.

## Stage boundary

The only valid S0 status produced by the current evidence is `S0_SAR_FOUNDATION_PARTIALLY_READY`: display geometry, lineage, GT threads, quality audit, and display-angle mapping are reproducible, but authoritative metric coordinates and `imaging_valid_mask` remain blocked. S1 entry is therefore not authorized.
