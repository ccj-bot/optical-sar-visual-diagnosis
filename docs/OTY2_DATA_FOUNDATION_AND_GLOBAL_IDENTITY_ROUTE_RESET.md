# OTY2 Data Foundation and Global Identity Route Reset

## Document hierarchy and reading order

1. `docs/OTY2_RESEARCH_ROUTE_RESET_RECORD_20260713.md`
   - Highest-level research decision and complete route rationale.
2. `docs/OTY2_DATA_FOUNDATION_AND_GLOBAL_IDENTITY_ROUTE_RESET.md`
   - Execution contract for the current data foundation, global identity, coordinate, and mapping freeze boundaries.
3. `reports/oty2/oty2_p0_data_asset_and_hard_sync_audit_20260713.md`
   - P0 data evidence and reproducible audit result.

The post-audit stage gate is recorded separately in `docs/OTY2_P0_EXIT_AND_P1_ENTRY_DECISION_20260713.md`. It preserves `P0_DATA_FOUNDATION_PARTIALLY_READY` while authorizing bounded optical-only P1 under the project operational hard-sync assumption.

## Purpose and boundary

This document resets the optical-timeline-assisted SAR annotation route around data facts that must be established before downstream cross-modal or SAR model work. Its original executable scope was **P0 raw data assets and hard-sync foundation audit only**. Current stage authorization is controlled by the independent P0-exit/P1-entry decision linked above.

Unless an independent stage decision explicitly authorizes a bounded exception, this route must not run or revise optical tracking, Working Graph construction, multi-vehicle identity merging, azimuth mapping, SAR candidate generation, Gate logic, selector/ranking, GT-driven box selection, GM_RM017 physical-factor experiments, SAR structural dynamics, training, threshold tuning, or final automatic annotation. The current exception authorizes optical-only P1 global physical-vehicle identity work; it does not authorize any SAR or cross-modal stage.

## Research principles

1. Synchronization, identity, coordinate systems, and mappings are foundation facts. They must be confirmed, documented, and frozen before downstream modeling.
2. The current working assumption is that optical frame 0 and SAR frame 0 in the same scene share one acquisition start.
3. The route does not use per-sample soft synchronization scores and does not use GT to adjust synchronization backward.
4. The final optical identity representation must unify the same physical vehicle over the complete offline time stream, not by adjacent-frame greedy Gates.
5. Multi-vehicle competition must ultimately be resolved by global exclusive assignment plus explicit admission, occlusion, recovery, and exit states.
6. The future azimuth mapping must be calibrated once from complete optical vehicle histories and high-quality SAR GT anchors, validated with physical-vehicle holdout, and then frozen.
7. SAR imagery must have one unique metric coordinate system, an effective-imaging Mask, and explicit Mask semantics.
8. A SAR vehicle must ultimately be represented as a canonical body response field, scattering-structure elements, and view-dependent structural state, not as a weighted score over several grayscale statistics.
9. Cross-modal and SAR model research is not allowed before its foundations are frozen. Optical-only P1 may proceed only when an explicit independent stage decision authorizes it without changing the P0 overall state.

## Evidence-state separation

### Confirmed facts

- The repository references scene assets outside Git rather than copying large image data into the repository.
- P0 must inventory GM_RM011, GM_RM017, and GM_RM019 independently.
- The audit implementation is read-only with respect to source assets and writes only controlled manifests and reports in this worktree.
- Sparse GT/review rows, full optical streams, full SAR streams, pair ordering, and physical-vehicle identity threads are different objects and must never be conflated.

### Current working assumptions

- Within each scene, optical frame 0 and SAR frame 0 have the same acquisition start.
- A fixed-rate deterministic timeline may be constructed only when optical and SAR frame rates have adequate provenance.
- The directly matched source MP4 containers confirm `optical_fps=24` and grayscale `sar_fps=50` for the available frame products. This confirms fixed container rates, not a shared hardware clock or common-start truth.

### Still requiring data-audit confirmation

- The acquisition-level source for optical and SAR frame rates.
- Whether scene start is truly common beyond the software zero-offset convention.
- Whether any frames were dropped before the numbered frame directories were produced.
- Why the GM_RM019 pseudocolor source MP4 reports approximately 48.300063 fps while its grayscale source reports 50 fps despite one-to-one frame indices.
- The lineage from raw ADC/IQ through range compression, complex imaging, grayscale SAR, and pseudocolor SAR.
- The authoritative acquisition and imaging configurations for each scene.
- The unique SAR metric-coordinate definition, effective-imaging Mask file, and Mask semantics.
- Whether an independent legacy 231-row review/pair asset exists in addition to the current canonical tables.

### Frozen old routes

The following routes are frozen as historical evidence only and are not P0 inputs for synchronization construction: candidate banks, Gate logic, selector/ranking, integrated statistical-correlation scores, GT-driven candidate choice, GM_RM017/GM_RM017-specific physical-factor discovery, and prior SAR response-mechanism experiments. Their reports may be inspected only for asset lineage or provenance, never as authority for changing the P0 hard-sync relation.

## P0-P7 stage relation

| Phase | Purpose | Entry condition | Output/freeze condition |
| --- | --- | --- | --- |
| P0 | Raw asset, numbering, lineage, rate-evidence, and common-start hard-sync audit | Clean branch from the approved posthoc baseline | Asset manifest, candidate or confirmed full-frame maps, missing-evidence list, and explicit P0 state |
| P1 | Complete optical-stream offline global physical-vehicle identity reconstruction | Explicit `P1_OPTICAL_GLOBAL_IDENTITY_ALLOWED` decision; optical asset sub-foundation confirmed | Physical-vehicle threads and identity relations with source provenance; no SAR identity authority |
| P2 | Global same-vehicle identity and multi-vehicle exclusive assignment | P1 optical observations frozen | Physical-vehicle threads with admission/occlusion/recovery/exit states and reviewable conflicts |
| P3 | SAR coordinate system and effective-imaging Mask foundation | P0 asset lineage frozen; required imaging metadata available | Unique metric coordinate definition, Mask file, and frozen Mask semantics |
| P4 | One-time azimuth mapping calibration | P2 vehicle threads and P3 coordinates frozen; high-quality SAR GT anchors available | Physical-vehicle holdout validation and frozen mapping parameters |
| P5 | SAR canonical vehicle response and scattering-structure state | P3/P4 frozen | View-conditioned response-field representation; no weighted grayscale-statistic shortcut |
| P6 | Cross-modal inference and bounded SAR localization research | P2/P4/P5 frozen | Auditable optical prior plus SAR-localized structural prediction, without GT runtime leakage |
| P7 | Final automatic annotation validation and release | P6 frozen and independently validated | Versioned automatic annotation contract, failure policy, and release audit |

The complete P0-P7 phase definitions are governed by `docs/OTY2_RESEARCH_ROUTE_RESET_RECORD_20260713.md`. P1 is not automatically authorized by this execution contract; its current bounded authorization is recorded by `docs/OTY2_P0_EXIT_AND_P1_ENTRY_DECISION_20260713.md`, without promoting the P0 overall state.

## Hard-sync contract for P0

If fixed frame rates are independently confirmed, the deterministic time axes are:

```text
optical_time = optical_frame_index / optical_fps
sar_time = sar_frame_index / sar_fps
```

No per-frame adaptive offset, synchronization confidence Gate, GT correction, or sample-specific soft score is allowed. If frame-rate provenance is insufficient, P0 may publish candidate configurations and candidate pair tables only, with an explicit unfrozen `assumption_status`.

## P0 non-execution declaration

P0 reads asset files, metadata, repository configuration, and existing GT/pair tables for audit. It does not run a detector, tracker, Working Graph, identity merger, candidate generator, Gate, selector, ranking method, SAR physical-mechanism experiment, training job, threshold search, or annotation generator.
