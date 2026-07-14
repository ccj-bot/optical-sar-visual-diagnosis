# OTY2 S0 SAR GT Structure Foundation Audit (20260715)

## 1. Executive result

- Execution mode: independent parallel worktree.
- Frozen SAR base/start HEAD: `1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5`.
- Worktree: `D:\profile\research\optical-sar-visual-diagnosis-sar-foundation`.
- Branch: `feature/oty2-sar-gt-structure-foundation`.
- S0 state: `S0_SAR_FOUNDATION_PARTIALLY_READY`.
- Mapping state: `MAPPING_BLOCKED`.
- S1 entry allowed: `false`.

The display fan coordinate, full gray/pseudocolor index lineage, canonical-to-GT research links, per-GT quality audit, vehicle-level research-role preservation, and display-angle mapping evaluation are reproducible. S0 cannot be `READY` because the current-scene acquisition/imaging configuration, complex or intermediate matrices, authoritative metric grid, and physical `imaging_valid_mask` remain unavailable.

## 2. SAR asset lineage

| scene | gray asset | pseudocolor asset | GT | unavailable upstream assets |
| --- | --- | --- | --- | --- |
| GM_RM011 | 766 gray PNG + 50 fps gray MP4 | 766 pseudocolor PNG + 50 fps container | reviewed GT table | ADC/IQ no; range-compressed no; complex image no; imaging config no |
| GM_RM017 | 766 gray PNG + 50 fps gray MP4 | 766 pseudocolor PNG + 50 fps container | reviewed GT table | ADC/IQ no; range-compressed no; complex image no; imaging config no |
| GM_RM019 | 766 gray PNG + 50 fps gray MP4 | 766 pseudocolor PNG + 48.3000630549 fps container | reviewed GT table | ADC/IQ no; range-compressed no; complex image no; imaging config no |

No current-scene raw ADC/IQ, range-compressed result, slow-time/aperture matrix, complex SAR image, amplitude/power matrix prior to 8-bit display conversion, current-pipeline MATLAB `.mat`, authoritative acquisition configuration, authoritative imaging configuration, or independent physical valid mask was located. The available gray PNG is an 8-bit three-channel container with identical channels; it does not retain phase. Pseudocolor is an 8-bit display derivative and does not add a physical observation dimension.

## 3. Coordinate and `0.03 m/pixel`

The unique reproducible coordinate is a Cartesian display canvas with fan-polar interpretation:

```text
r_px = hypot(x - 1154.0, y - 1330.6)
theta_deg = atan2(x - 1154.0, 1330.6 - y)
```

The display origin is near the bottom center. Range-like behavior is radial, not uniform image `y`; tangential metric width depends on range and angle. `0.03 m/pixel` is retained as a historical/project-local radial grid-spacing claim only. It is not proven full-image Cartesian scale and is not range resolution, azimuth resolution, PSF width, or actual vehicle-structure resolving power. Meter fields are intentionally blank.

## 4. Mask audit

`fan_geometry_mask` is reproducible from the shared display formula. `display_nonzero_mask` and the full-stream `fixed_black_region_mask` are rendered-pixel facts. The physical `imaging_valid_mask` remains missing. Consequently GT/fan intersection is reported, but GT/physical-valid intersection is not fabricated.

| scene | min gray-pseudo gradient alignment | median alignment | fixed black / fan |
| --- | ---: | ---: | ---: |
| GM_RM011 | 0.8856 | 0.9317 | 0.285169 |
| GM_RM017 | 0.8676 | 0.9476 | 0.285125 |
| GM_RM019 | 0.7505 | 0.8793 | 0.285306 |

The three scenes use the same fan formula, but their empirical always-black and stable-nonzero masks are scene-derived. Black pixels may reflect display masking, clipping, un-imaged regions, invalid samples, or true zero return; S0 cannot uniquely distinguish them.

## 5. Gray/pseudocolor lineage and GM_RM019 timebase

All three scenes have exactly 766 gray and 766 same-index pseudocolor PNGs with identical dimensions. Full-stream gradient structure remains aligned in every pair. P0 already verified source-video decoding against frame 0, 100, and last PNG.

GM_RM019's pseudocolor MP4 reports about `48.300063 fps`, while the gray source is `50 fps`. Because the indexed PNG streams remain one-to-one and pseudocolor is a display derivative, the conflict is classified as container/encoding timebase metadata, not a second sensor clock. Gray `50 fps` is authoritative; pseudocolor frame `j` inherits `j/50` seconds. No video was re-encoded.

## 6. Canonical vehicle to SAR GT threads

| scene | canonical vehicles with linked GT | linked GT rows | unresolved/nonvehicle-conflict rows |
| --- | ---: | ---: | ---: |
| GM_RM011 | 10 | 193 | 8 |
| GM_RM017 | 3 | 207 | 9 |
| GM_RM019 | 4 | 22 | 3 |

Across the 22 P1-E canonical vehicles, `17` have at least one defensible SAR GT link. The 442 reviewed rows remain sparse research anchors; missing GT never means missing SAR response, and no missing row is interpolated into GT. Optical full occlusion, partial visibility, and multi-vehicle competition are carried explicitly.

## 7. GT quality

- `gold`: `3`
- `usable`: `295`
- `diagnostic_only`: `124`
- `identity_or_geometry_conflict`: `17`
- `exclude_from_structure_discovery`: `3`

Quality combines P1-E identity provenance, optical visibility, reviewed GT geometry, reconstructed fan contact, image boundary, same-frame vehicle competition, center/size/aspect continuity, and direct atlas review. It is not an area-only or IoU-only score. Meter dimensions are not fabricated.

## 8. Golden vehicle threads

`13` vehicle-level threads are admitted for mapping development, structure development, or heldout structure validation. Role counts are `{'diagnostic_only': 4, 'exclude': 5, 'structure_development': 8, 'structure_heldout_validation': 5}`. Every vehicle inherits one P1-E role for all frames; no vehicle is split between discovery and heldout claims.

## 9. Azimuth mapping

Current development-only refit:

```text
theta_display_deg = 0.089687255891 * x_optical_center_px + (-39.136864479885)
```

| evaluation | n | median deg | P90 deg | max deg |
| --- | ---: | ---: | ---: | ---: |
| development vehicle LOO linear | 1 | 10.563780 | 10.563780 | 10.563780 |
| heldout linear | 49 | 1.348193 | 2.208394 | 37.969147 |
| old mapping development | 21 | 2.105412 | 2.820879 | 11.809661 |
| old mapping heldout | 49 | 1.029480 | 3.225934 | 39.439805 |

The audit uses `21` development anchors from `2` vehicles and `49` heldout anchors from `3` heldout vehicles. Development validation is whole-vehicle leave-one-out; heldout anchors do not fit any coefficient. Tangential pixel error and error/vehicle-width ratio are reported per anchor. Metric error is blocked.

Freeze decision: no model is frozen. Development vehicle leave-one-out coverage is incomplete and scene-extreme residuals remain large; both the old and refit formulas are diagnostic only. Status is `MAPPING_BLOCKED`.

## 10. Complete visual review

Direct visual artifacts were generated for:

- all 2,298 gray frames and all 2,298 same-index pseudocolor frames in three full-stream contact sheets;
- all `442` reviewed GT rows;
- all `420` automatic anomaly/mask/competition/jump cases;
- all `70` mapping anchors;
- `43` golden-thread representative cases.

These assets are temporary and live only under `D:\profile\research\workspace\output\oty2_s0_sar_gt_structure_foundation_20260715\visual_review`. They are excluded from Git.

## 11. Remaining blockers

1. True current-scene acquisition/imaging code and configuration.
2. Raw or intermediate complex/amplitude/power matrices with lineage.
3. Authoritative maximum range and pixel-to-meter grid generation.
4. Physical range and azimuth resolution/PSF evidence.
5. Independent physical `imaging_valid_mask` and its annotation semantics.
6. Manual resolution for the remaining unresolved or identity-conflict GT rows.
7. Physical metric validation of the display-angle mapping.

Because blockers 1-5 directly violate S0 READY conditions, S1 is not authorized.

## 12. Explicit non-execution

This run did not use P1-C global IDs as physical truth, did not consume P1-F propagation/recovery outputs, did not change the P1-E canonical benchmark, did not change hard synchronization, did not tune a time offset from GT, did not treat pseudocolor as independent physics, did not infer a vehicle-response mask, did not generate candidates, did not run a Gate/selector/ranking/oracle, did not train a model, did not run an optical tracker, did not start high-energy sliding/scatterer tracking/structure dynamics, and did not produce automatic annotations.
