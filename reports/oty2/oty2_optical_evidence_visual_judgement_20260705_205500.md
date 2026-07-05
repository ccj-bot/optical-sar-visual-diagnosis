# OTY2 Optical Evidence Visual Judgement And Migration Evidence Stratification

Timestamp: `20260705_205500`
Repository: `D:\profile\research\optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified HEAD: `4d973a5 Aggregate tracklet embeddings for stitching input`

## Boundary

This report is a visual judgement and migration-evidence stratification pass. It does not stitch tracklets, merge tracker ids, assign identity truth, create final annotations, create revised GT, create final boxes, run selector/ranking, run SAR pairing/support, tune thresholds, train models, or promote `GM_RM011` into the clean `215` pool.

Temporary visual panels were generated only under ignored `outputs/`:

- `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/`
- review table: `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/optical_evidence_visual_judgement_review_cases.csv`
- contact sheet: `outputs/oty2/optical_evidence_visual_judgement_20260705_205500/optical_evidence_visual_judgement_contact_sheet.jpg`

Committed summary table:

- `reports/oty2/samples/oty2_optical_evidence_visual_judgement_summary_20260705_205500.csv`

Committed helper script:

- `tools/diagnostics/run_oty2_optical_evidence_visual_judgement_pack.py`

## Why This Is Not Direct Track Stitching

The current question is not whether the optical tracks can be made prettier. The current question is whether optical temporal evidence can safely serve SAR annotation migration. Safe use means the optical evidence should not propagate a wrong target, wrong identity handle, or wrong spatial range into SAR-side annotation work.

Therefore a visually plausible relation is only a migration candidate when timing, motion, box quality, visible target state, appearance, and competing-target rejection all make sense. Tracker ids and segment ids remain hypotheses. A strong continuity candidate is not automatically a strong SAR migration constraint, especially when the optical box covers only a partial vehicle or an edge-truncated crop.

## Inputs Read

- `docs/OTY2_SESSION_START_HERE.md`
- `docs/OTY2_TEMPORAL_BACKBONE_ROUTE_RESET.md`
- `docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md`
- `docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md`
- `docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md`
- `docs/oty2_gt_support_failure_concept_correction_archive.md`
- `docs/oty2_physical_structure_first_not_weighted_fusion_archive.md`
- `docs/oty2_gt_local_energy_field_atlas_correction_archive.md`
- `reports/oty2/oty2_tracklet_embedding_aggregation_probe_20260705_193000.md`
- `reports/oty2/samples/oty2_tracklet_embedding_aggregation_probe_summary_20260705_193000.csv`
- `tools/diagnostics/run_oty1t_tracklet_embedding_aggregation_probe.py`
- `outputs/oty2/tracklet_embedding_aggregation_probe_20260705_193000/tracklet_embedding_index.csv`
- `outputs/oty2/embedding_track_linkage_probe_20260705_183000/embedding_track_linkage_rows.csv`
- `outputs/oty2/crop_reid_embedding_probe_20260705_170500/crop_reid_embedding_index.csv`

## Visual Sample Set

The helper script selected:

- `3` GM_RM017 appearance-unstable segments.
- `8` GM_RM011 breakpoint or counterexample panels.

This is a key-sample visual judgement pass, not an exhaustive audit of all `29` GM_RM011 segments.

## GM_RM017 Visual Judgement

GM_RM017 is not a simple clean scene under the current optical evidence. It has few track ids, but the three unstable segments are dominated by edge-truncated or partial-vehicle boxes. The instability mostly comes from box/crop quality, edge visibility, partial target state, and nearby vehicle competition. The reviewed evidence does not support using these unstable segments as strong SAR migration constraints.

| Segment | Frames | Visual finding | Migration grade | Primary issue |
| --- | ---: | --- | --- | --- |
| `bs_0008 seg_001` | `145-185` | The selected box moves between edge fragments; the later frames show only a small right-edge dark-vehicle crop while another dark sedan remains visible in scene context. Same-target continuity cannot be safely confirmed. | blocked / manual review | edge truncation plus competing vehicles |
| `bs_0010 seg_001` | `151-200` | The target appears to be a white vehicle fragment near the image edge. The crop switches from a tiny/partial early view to right-edge front fragments. Visual continuity is plausible but box support is too partial. | weak optical evidence | edge-contact partial crop |
| `bs_0012 seg_001` | `162-214` | The segment mixes very different partial views near the left and right image edges. The minimum-cosine tail frames are thin right-edge dark crops. Identity continuity is unclosed. | blocked / manual review | edge truncation and possible identity ambiguity |

Answer to the GM_RM017 reliability question: GM_RM017 is simpler in track-count terms, but not visually reliable enough to be treated as a clean scene. Its failure is not mainly a ResNet18-only problem. ResNet18 becomes unstable because the optical boxes often contain partial vehicle parts, frame-edge crops, and competing vehicles. The correct next use is box-quality and identity-continuity audit, not direct migration.

## GM_RM011 Breakpoint Visual Judgement

GM_RM011 has explainable candidate breakpoints, but the inspected cases are mostly partial/edge vehicle views. The useful distinction is:

- strong continuity candidate: the breakpoint can enter a next candidate-merge review list;
- weak migration evidence: the crop is still too partial to constrain SAR strongly;
- blocked/conflict: the proposed relation points to a competing target or cannot exclude one.

| Relation | Frames | Visual judgement | Candidate status | Why alternatives fail |
| --- | ---: | --- | --- | --- |
| `bs_0015 seg_001 -> bs_0015 seg_002` | `16 -> 18` | Same white vehicle front/windshield region is visually continuous across a 2-frame gap. | strong continuity candidate; weak-to-medium migration evidence | Other nearby targets are not better explanations, but the bbox is still a partial front/side crop. |
| `bs_0061 seg_002 -> bs_0061 seg_003` | `281 -> 283` | Same white vehicle front/windshield continues over a 2-frame gap. | strong continuity candidate; weak-to-medium migration evidence | The left-edge parked/neighbor vehicle is visible but does not explain the central white-car crop. |
| `bs_0029 seg_001 -> bs_0029 seg_002` | `161 -> 164` | Same right-edge white vehicle is plausible, but the later crop becomes extremely narrow at the frame edge. | weak continuity candidate | The edge crop is too thin to support strong migration or identity confidence. |
| `bs_0061 seg_001 -> bs_0061 seg_002` | `270 -> 279` | Same white vehicle is plausible after a 9-frame gap, but the visible state changes from rear/side to front/windshield. | weak continuity candidate | Longer gap and part-state change prevent a strong candidate without further review. |
| `bs_0061 seg_001 -> bs_0064 seg_001` | `270 -> 283` | Numeric appearance is high, but the after segment boxes a left-edge competing vehicle while the central white vehicle remains separate. | blocked conflict | This is the key counterexample: appearance similarity alone can point to the wrong target. |
| `bs_0056 seg_001 -> bs_0061 seg_001` | `261 -> 262` | Temporal order is close, but the before box is a long side-window strip and the after box is a left-edge rear fragment/competing vehicle area. | blocked or manual review | Spatial proximity does not exclude target competition or part-box switching. |
| `bs_0044 seg_002 -> bs_0038 seg_002` | `233 -> 236` | Likely same white vehicle under partial-to-full or part-box transition, but the box changes from upper side/window strip to front/hood region. | weak continuity candidate | Appearance is weak because boxes cover different vehicle parts; not a strong migration constraint. |
| `bs_0002 seg_001 -> bs_0007 seg_001` | `4 -> 8` | Same white SUV is plausible, but the box changes from rear/body to upper-window strip. | weak continuity candidate | Box part mismatch prevents strong evidence even though scene continuity is plausible. |

## Evidence Stratification

### Strong SAR Migration Evidence

No reviewed high-risk segment is promoted to strong SAR migration evidence in this pass. The reason is not that all optical continuity failed. The reason is that the reviewed samples are dominated by partial vehicle boxes, frame-edge crops, and box-part transitions. Those are useful for candidate review, but they should not become strong SAR-side spatial constraints.

### Strong Continuity Candidates For Next Review

These can enter a next candidate-merge review list, with the explicit caveat that they are not identity truth:

- `GM_RM011 bs_0015 seg_001 -> bs_0015 seg_002`
- `GM_RM011 bs_0061 seg_002 -> bs_0061 seg_003`

### Weak Optical Evidence

These may help SAR candidate review as weak context only:

- `GM_RM011 bs_0029 seg_001 -> bs_0029 seg_002`
- `GM_RM011 bs_0061 seg_001 -> bs_0061 seg_002`
- `GM_RM011 bs_0044 seg_002 -> bs_0038 seg_002`
- `GM_RM011 bs_0002 seg_001 -> bs_0007 seg_001`
- `GM_RM017 bs_0010 seg_001`

### Blocked Or Manual Review

These should not be used directly for migration:

- `GM_RM017 bs_0008 seg_001`
- `GM_RM017 bs_0012 seg_001`
- `GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001`
- `GM_RM011 bs_0056 seg_001 -> bs_0061 seg_001`

## Box And Identity Findings

Box-quality problem found: yes. The main recurring issue is not crop extraction failure; crops exist. The issue is that many crops are partial, edge-truncated, or cover different parts of the same vehicle across adjacent fragments.

Identity-mixing problem found: not proven as identity truth, but visual competition is real. `GM_RM011 bs_0061 seg_001 -> bs_0064 seg_001` shows that a high-appearance cross-track candidate can point to a different left-edge vehicle. GM_RM017 `bs_0008` and `bs_0012` also remain blocked because competing vehicles and edge fragments cannot be excluded.

## Required Answers

1. The current problem is not direct track stitching because stitching would collapse uncertain optical evidence into an identity claim before SAR migration safety is known.
2. Safe SAR migration use means optical evidence will not likely propagate wrong target, wrong identity handle, or wrong spatial range into SAR annotation work.
3. GM_RM017's 3 unstable segments are edge/partial visibility cases, not clean full-vehicle tracks.
4. GM_RM017 instability comes mainly from box/crop quality, edge truncation, partial visibility, and competing vehicles; ResNet18 instability is a symptom, not the root cause.
5. GM_RM017 cannot be treated as a simple reliable scene under the current evidence.
6. GM_RM011 visually plausible same-vehicle breakpoints include `bs_0015 seg_001 -> seg_002` and `bs_0061 seg_002 -> seg_003`; weaker plausible cases are listed above.
7. The strongest candidates work because timing is short, motion is locally continuous, and the visible vehicle region is consistent.
8. Other candidates fail because they box a competing left-edge vehicle, change vehicle part, are too edge-truncated, or have longer/unexplained gaps.
9. Weak candidates are `bs_0029 -> bs_0029`, `bs_0061 seg_001 -> seg_002`, `bs_0044 -> bs_0038`, and `bs_0002 -> bs_0007`.
10. Blocked/manual-review cases are GM_RM017 `bs_0008`, GM_RM017 `bs_0012`, GM_RM011 `bs_0061 -> bs_0064`, and GM_RM011 `bs_0056 -> bs_0061`.
11. Current optical evidence should serve SAR migration by ranking which optical time spans and candidate relations deserve SAR-side checking, not by writing final boxes.
12. No reviewed high-risk segment is promoted to strong SAR migration evidence.
13. Weak migration evidence includes the plausible but partial GM_RM011 candidates and GM_RM017 `bs_0010`.
14. Blocked cases should not be used for migration until manual/SAR evidence resolves them.
15. Next step should be candidate-merge review plus box-quality/state-tag audit. It should not jump to final track stitching or SAR support/pairing.

## Conclusion

```text
OPTICAL_EVIDENCE_READY_FOR_SAFE_MIGRATION_CANDIDATES
```

Interpretation: ready for a bounded safe-candidate layer, not ready for final identity merging or strong SAR migration constraints.
