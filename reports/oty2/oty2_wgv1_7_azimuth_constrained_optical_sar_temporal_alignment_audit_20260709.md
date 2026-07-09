# OTY2 WGV1.7 azimuth-constrained optical-SAR temporal alignment audit

Date: 2026-07-09

## Scope

WGV1.7 is a pre-SAR, posthoc mechanism-diagnosis audit. It tests whether existing azimuth or fan-polar mapping work can constrain optical-to-SAR temporal alignment for the nine WGV1.6 selected windows. It does not solve mapping, choose a runtime offset, produce localization artifacts, or upgrade weak optical threads.

Optical evidence is not SAR evidence. Optical threads may only constrain or prioritize SAR exploration. SAR identity support still requires independent SAR-internal evidence. Long-window optical stability does not imply a SAR-ready annotation. Current SAR state remains unresolved for consumption until later SAR-only evidence exploration is completed.

## Inputs Read

Required reading completed:

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/oty2_sar_physical_factor_modeling_idea_archive.md`
- `docs/oty2_temporal_window_to_spatial_constraint_design.md`
- `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
- `reports/oty2/oty2_wgv1_6_small_window_optical_sar_dual_evidence_closure_audit_20260709.md`

Additional timing contracts used for formula provenance:

- `reports/oty2/oty2_alignment_mode_decision_report_20260702_132945.md`
- `reports/oty2/oty2_software_sync_temporal_contract_20260702_135912.md`
- `reports/oty2/oty2_object_sar_temporal_window_contract_20260702_142454.md`

Structured source status is recorded in `reports/oty2/samples/oty2_wgv1_7_mapping_source_provenance_20260709.csv`.

Azimuth source coverage found in `reports/oty2/oty2_azimuth_vehicle_size_shell_audit_20260702_190435.csv`:

- `GM_RM017`: 199 rows, usable only as a posthoc azimuth-sector proxy.
- `GM_RM019`: 16 rows, context only for this audit.
- `GM_RM011`: 0 rows, so WGV1.7 has no direct GM_RM011 azimuth/object-stream mapping source.

## Method

For each WGV1.6 selected window and each integer offset from `-12` through `+12` SAR frames, WGV1.7 computed an inclusive temporal tube:

```text
sar_frame_start = round(optical_frame_start * 50 / 24 + offset_sar_frames) - 1
sar_frame_end   = round(optical_frame_end   * 50 / 24 + offset_sar_frames) + 1
```

The `+/-1` padding follows the existing software-sync jitter and rounding-padding contract. The scan range remains the requested conservative `-12..+12`; no final runtime offset is selected.

For each offset/window pair, the audit attached:

- WGV1.5C prior SAR evidence IDs when their aggregate SAR-frame range overlapped the computed tube.
- Existing azimuth-sector proxy rows when the scene-level azimuth audit had SAR frames inside the tube.
- Boundary, competitor, background, and GT-quality risk labels from the prior summaries.

Any SAR overlap in this report is posthoc proxy evidence only. It is not an annotation decision and not identity confirmation.

## Offset Scan Summary

Offset scan rows: `225`.

Offset decision counts:

- `offset_ambiguous`: 75
- `offset_blocked_by_identity_risk`: 25
- `offset_boundary_breaks`: 50
- `offset_not_testable_missing_azimuth_source`: 75

Window mapping decision counts:

- `azimuth_temporal_mapping_ambiguous`: 3
- `mapping_blocked_by_boundary_or_competitor`: 3
- `mapping_not_testable_missing_sources`: 3

## Window Decisions

| Window | Optical item | WGV1.4b class | WGV1.7 mapping decision | Offset-band interpretation |
| --- | --- | --- | --- | --- |
| `WGV16W001` | `GM_RM011_WGV14T001` | `optical_identity_constraint` | `mapping_not_testable_missing_sources` | `none_missing_direct_gm011_azimuth_object_mapping_source` |
| `WGV16W002` | `GM_RM011_WGV14T004` | `optical_identity_constraint` | `mapping_not_testable_missing_sources` | `none_missing_direct_gm011_azimuth_object_mapping_source` |
| `WGV16W003` | `GM_RM011_WGV14T005` | `optical_search_hint_only` | `mapping_not_testable_missing_sources` | `none_missing_direct_gm011_azimuth_object_mapping_source` |
| `WGV16W004` | `GM_RM011_WGV12M005` | `boundary_preserved` | `mapping_blocked_by_boundary_or_competitor` | `none_blocked_by_preserved_boundary_or_identity_risk` |
| `WGV16W005` | `GM_RM011_WGV12M016` | `boundary_preserved` | `mapping_blocked_by_boundary_or_competitor` | `none_blocked_by_preserved_boundary_or_identity_risk` |
| `WGV16W006` | `GM_RM017_WGV14T001` | `optical_search_hint_only` | `azimuth_temporal_mapping_ambiguous` | `ambiguous_posthoc_overlap_band_-12..+12; no unique offset selected` |
| `WGV16W007` | `GM_RM017_WGV14T002` | `optical_search_hint_only` | `azimuth_temporal_mapping_ambiguous` | `ambiguous_posthoc_overlap_band_-12..+12; no unique offset selected` |
| `WGV16W008` | `GM_RM017_WGV14T003` | `optical_search_hint_only` | `azimuth_temporal_mapping_ambiguous` | `ambiguous_posthoc_overlap_band_-12..+12; no unique offset selected` |
| `WGV16W009` | `GM_RM017_WGV14V004` | `blocked_for_sar_consumption` | `mapping_blocked_by_boundary_or_competitor` | `none_blocked_by_preserved_boundary_or_identity_risk` |

## Direct Answers

### 1. Can existing azimuth mapping constrain the optical-SAR temporal offset?

Only partially, and only for `GM_RM017` as a posthoc proxy. The azimuth source has frame-level `GM_RM017` rows inside the tested temporal tubes, but those rows are GT-anchored posthoc validation rows and are not direct WGV thread mapping. They can show that an offset tube intersects an existing azimuth-feasible sector, but they do not select a unique runtime offset.

For `GM_RM011`, existing WGV1.7 sources do not provide direct azimuth rows or object-level mapping, so the optical-SAR temporal offset is not testable from this source set.

### 2. Which windows have an admissible offset band?

No window receives `offset_consistent` as a resolved offset. The `GM_RM017` weak windows have an ambiguous posthoc overlap band across the tested `-12..+12` range, because their tubes intersect aggregate SAR evidence and azimuth proxy rows. This is admissible only for SAR-only evidence discovery prioritization, not for class upgrade or consumption.

`GM_RM011_WGV14T001`, `GM_RM011_WGV14T004`, and `GM_RM011_WGV14T005` do not have a testable offset band because the direct GM_RM011 azimuth/object-stream source is missing.

### 3. Which windows remain blocked because boundaries or competitor risks break the mapping?

`GM_RM011_WGV12M005` and `GM_RM011_WGV12M016` remain preserved boundary checks. Their mapping decision is `mapping_blocked_by_boundary_or_competitor`; this audit does not bridge either boundary.

`GM_RM017_WGV14V004` remains blocked because WGV1.5A marked it `blocked_for_sar_consumption`. Its offset rows are `offset_blocked_by_identity_risk` even where temporal and azimuth proxy overlap exists.

`GM_RM011_WGV14T005` is not itself a boundary row, but it remains limited by competitor/boundary context near M016 and by missing direct GM_RM011 mapping.

### 4. Does GM_RM011 have stronger mapping support than GM_RM017?

No. GM_RM011 has stronger optical identity evidence for selected accepted windows, but weaker optical-SAR mapping support in WGV1.7 because no direct GM_RM011 azimuth/object-stream mapping rows are available. GM_RM017 has direct posthoc azimuth proxy rows, but the relevant optical windows remain weak or blocked. Therefore neither scene supports SAR consumption; the failure mode differs by scene.

### 5. Does any weak or blocked window leak into stronger consumption?

No. `GM_RM017_WGV14T001`, `GM_RM017_WGV14T002`, and `GM_RM017_WGV14T003` remain `optical_search_hint_only` with `azimuth_temporal_mapping_ambiguous`. `GM_RM017_WGV14V004` remains blocked. Boundary rows remain boundary rows. No WGV1.7 row upgrades optical class or SAR consumption status.

### 6. What remains unresolved before any SAR-ready stage?

Unresolved items:

- Direct GM_RM011 object-stream recovery and azimuth/fan-polar mapping source.
- Independent SAR-internal evidence units inside temporal tubes, separate from optical proof.
- Boundary-specific SAR support that does not bridge known different-vehicle/context boundaries.
- Competitor or multi-target separation in GM_RM017 weak/blocked windows.
- A later explicit SAR consumption protocol if any annotation-producing stage is ever opened.

## Boundary Statement

WGV1.7 produces only reports and CSV summaries. It creates no localization artifact, no revised annotation artifact, no selector or ranking artifact, no tracked media, and no `outputs/` artifact. SAR-ready remains no / blocked for the tested windows.

## Output Files

- `reports/oty2/oty2_wgv1_7_azimuth_constrained_optical_sar_temporal_alignment_audit_20260709.md`
- `reports/oty2/samples/oty2_wgv1_7_offset_scan_summary_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_7_window_mapping_decisions_20260709.csv`
- `reports/oty2/samples/oty2_wgv1_7_mapping_source_provenance_20260709.csv`
