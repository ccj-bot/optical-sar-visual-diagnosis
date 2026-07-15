# OTY2 S0-M SAR GT Structure Foundation Audit (20260715)

## 1. Executive result

- Execution mode: independent parallel SAR worktree.
- Frozen base: `1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5`.
- Starting revision: `abdad5c0e89427911b26782c9f852d86830f85b4`.
- Worktree: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation`.
- Branch: `feature/oty2-sar-gt-structure-foundation`.
- S0 state: `S0_SAR_FOUNDATION_PARTIALLY_READY`.
- Mapping state: `MAPPING_BLOCKED`.
- S1-L entry allowed: `false`.

S0-M corrects the previous statement that the valid imaging mask was unknown. The deterministic common fan is now frozen as `imaging_valid_mask`. S0 remains only partially ready because the physical metric grid is unresolved and the filtered mapping set contains only one development complete vehicle, one scene, and one stable pose group.

## 2. SAR asset and time lineage

Each scene has 766 gray PNGs, 766 same-index pseudocolor PNGs, a gray source video, and a pseudocolor source video. No current-scene ADC/IQ, range-compressed array, complex SAR image, amplitude/power matrix before display conversion, current-pipeline `.mat`, authoritative acquisition configuration, or authoritative metric-grid generator was located.

The gray PNG is an 8-bit display product and does not retain phase. Pseudocolor is an 8-bit display derivative and does not add a physical observation dimension. For GM_RM019, the pseudocolor container reports approximately `48.300063 fps`, but all 766 frames remain index-aligned to the authoritative gray `50 fps` sequence; pseudocolor frame `j` therefore inherits `j/50` seconds.

## 3. Coordinate and metric-grid conclusion

The reproducible display coordinate is:

```text
r_px = hypot(x - 1154.0, y - 1330.6)
theta_deg = atan2(x - 1154.0, 1330.6 - y)
```

This is a fan-polar display coordinate, not proof of uniform full-image Cartesian scale. `0.03 m/pixel` remains only a historical/project-local radial grid-spacing claim and is not range resolution, azimuth resolution, PSF width, or actual vehicle-structure resolution. Metric GT and mapping fields remain blank.

## 4. Frozen imaging-valid Mask

The fixed mask uses the `2308 x 1334` canvas, origin `(1154.0,1330.6)`, radius `1332.7 px`, and azimuth interval `[-90,90] deg`.

- valid pixels: `2,628,412`;
- canvas fraction: `0.8536931707456497`;
- SHA-256: `7bdfbc5417db5f96405751d7503973f16db85957cf9aa0c6a8f30975cc0502ef`;
- three scenes and all 766 frame indices per scene bind to the same generation parameters and hash.

`imaging_valid_mask`, `fixed_black_region_inside_mask`, `display_nonzero_mask`, `gt_box_region`, and the not-yet-established `vehicle_response_mask` are separate contracts. The fixed black counts inside the valid mask remain `749,541 / 749,427 / 749,903` for GM_RM011/017/019.

All 442 reviewed GT rows have `gt_valid_mask_fraction=1.0`; no GT is clipped by or touches the valid-mask boundary. The mask-clipped diagnostic subset is therefore empty, not unknown.

## 5. Canonical-GT and quality accounting

- reviewed GT rows: `442`;
- canonical-linked rows: `422`;
- unresolved/conflict rows: `20`;
- canonical vehicles with linked GT: `17 / 22`;
- GT quality: `gold=3`, `usable=295`, `diagnostic_only=124`, `identity_or_geometry_conflict=17`, `exclude_from_structure_discovery=3`.

The new residual-independent eligibility accounting is:

- `calibration_usable=20`;
- `heldout_usable=45`;
- `pose_or_geometry_diagnostic=338`;
- `identity_conflict=32`;
- `exclude=7`;
- all other allowed categories: `0`.

The identity-conflict category includes unresolved canonical links and low-confidence identity cases; it is intentionally stricter than the original 20-row unresolved count.

## 6. Independent re-audit of extreme anchors

The raw GM_RM019 extreme remains exactly `39.439805 deg` center error for the historical old mapping. It is fully inside the Mask and its predicted azimuth is inside the full GT azimuth interval `[-44.233547,50.940869] deg`. Direct optical review—not the residual—shows that the foreground vehicle is cut by the left, right, and bottom image boundaries and that the reference box is only a local fragment. It is reclassified as `pose_or_geometry_diagnostic`.

The GM_RM011 `11.809661 deg` row is also inside its full GT interval but has independent left/bottom optical boundary truncation. It is diagnostic-only for the same residual-independent reason.

After Mask/completeness filtering, the old mapping maximum center error is `3.740868 deg`, from GM_RM017:PV003 at optical/SAR frame `185/386`.

## 7. Center and GT-interval mapping evaluation

| subset/model | n | vehicles | median | P90 | max | predicted center inside full GT interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| all historical / old linear | 70 | 5 | 1.0651 | 3.2045 | 39.4398 | 100% |
| filtered complete / old linear | 65 | 3 | 1.0295 | 3.0642 | 3.7409 | 100% |
| filtered complete / dev refit linear | 65 | 3 | 0.6030 | 1.4145 | 1.9431 | 100% |
| filtered complete / centered linear | 65 | 3 | 0.6030 | 1.4145 | 1.9431 | 100% |
| filtered complete / pinhole LOS | 65 | 3 | 0.6488 | 1.5749 | 3.1098 | 100% |

The filtered median GT azimuth width is `25.4154 deg`. Old-model median center error/GT-width ratio is `0.0420`. Because every GT is inside the fixed Mask, full-interval and GT-intersection-mask interval hit rates are identical.

The optical partial/boundary diagnostic subset has 148 nearest-sync rows: center median/P90/max `8.3630 / 18.6846 / 39.4398 deg`, yet full-GT-interval hit rate remains `99.32%`. Center residual alone therefore overstates shell failure on partial vehicles.

## 8. Model comparison and freeze

Development-complete fitting uses 20 anchors from only `GM_RM017:PV002`. Heldout-complete evaluation uses 45 anchors from `GM_RM017:PV003` and `GM_RM017:PV004`.

```text
old:       theta = 0.0875154 * x - 40.413555
dev refit: theta = 0.091778579301 * x - 40.421051198963
```

The centered line is an equivalent parameterization. The pinhole LOS fit is an effective diagnostic projection, not a physical-intrinsics claim. Heldout P90/max improve for the refit line, but whole-vehicle development LOO is impossible, and complete data cover only GM_RM017 and one pose. A low-order monotonic nonlinear comparison is not justified.

Freeze decision: retain the old line as a diagnostic prior only; do not freeze a new center function. Status remains `MAPPING_BLOCKED`.

## 9. Pose-proxy audit

Pose is derived only from complete optical appearance. All 65 complete anchors are `left_side_dominant`; the other required pose groups have zero complete anchors. The audit can describe optical bbox-proxy residual, SAR GT-center residual, interval distance, GT width, and bias direction, but it cannot identify a reproducible pose effect or separate optical-center bias from SAR scattering-center bias.

No pose-conditioned center correction is allowed. Pose may only become a corridor-uncertainty variable after multiple development vehicles and heldout vehicles reproduce the same bias independently of Mask, truncation, and GT geometry.

## 10. Azimuth corridor

For the old diagnostic center and all 65 complete anchors, full GT-interval containment is `1.54% / 64.62% / 100%` for half-widths `10 / 15 / 20 deg`. The corresponding mean corridor widths are `20 / 30 / 40 deg`; mean expansion relative to GT azimuth width is `0.818 / 1.228 / 1.637`.

This is full-interval containment, not center hit rate. A 20-degree half-width is the smallest audited sweep value with 100% current complete-interval coverage, but it is not frozen for runtime use because cross-scene and pose coverage are absent.

## 11. S1-L synchronization revision

The S1-L ledger contains all 442 rows and selects 12 representative future candidates spanning the three retained GM_RM017 vehicles and their available azimuth/radius range. These are marked `candidate_only_s1l_not_started`.

S1-L is not authorized because:

1. no mapping center function is frozen;
2. only one development complete vehicle remains;
3. complete anchors cover only GM_RM017;
4. complete anchors cover only left-side-dominant pose.

Mask-clipped, optical-partial, identity-conflict, and direct-competition rows remain diagnostic-only and are not mixed into complete-vehicle structure statistics.

## 12. Validation and Explicit non-execution

The revised validator checks Mask parameters/hash/frame invariance, all 442 eligibility rows, residual-independent exclusions, the raw/filtered extreme values, interval metrics, model/role boundaries, corridor sweep, pose-source boundary, and the S1-L non-entry state.

This run did not consume P1-F outputs, modify P0 synchronization, modify P1-E canonical identity, infer a vehicle-response mask, generate SAR candidates, run a Gate/selector/ranking/oracle, train a model, perform automatic annotation, or start S1-L structure dynamics.
