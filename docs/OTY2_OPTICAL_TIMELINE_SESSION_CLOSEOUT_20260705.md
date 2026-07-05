# OTY2 Optical Timeline Session Closeout

Date: 2026-07-05
Repository: `D:/profile/research/optical-sar-visual-diagnosis`
Branch: `feature/oty2-posthoc-mechanism-validation`
Closeout base HEAD: `ca45161 Probe downloaded detector variants for optical timeline stability`

## Session Goal

This session closes the OTY2 optical temporal mainline after the route reset from crop/ReID-style stitching toward visual referent consistency. The goal is not to produce final labels, not to construct SAR migration outputs, and not to replace the optical detector. The goal is to preserve the evidence needed for the next optical diagnostic step: reviewable vehicle timeline video rendering plus a manual override contract.

## Actual Route Taken

The route began with a risk of continuing in the wrong direction: more SAR migration evidence tables, more ReID/crop embedding comparisons, and direct algorithmic stitching of complete trajectories. The route was corrected to a more basic question:

**Can the optical side express that the same real vehicle is being continuously observed inside local temporal windows?**

That change moved the unit of reasoning from `track_id`, crop appearance, and detector scores to physical vehicle referents in visual context. Only after a referent is visually coherent can it become a timeline node, a strong edge, a weak edge, a forbidden edge, or a rendered review item.

The final route was:

1. Audit same-vehicle referent consistency.
2. Convert the referent audit into a graph input contract.
3. Render and smoke-test the optical timeline review manifest.
4. Run detector-swap probes only as diagnostic sensitivity checks.
5. Stop before SAR consumption, final boxes, revised GT, selector/ranking, or annotation generation.

## Mistakes, Corrections, And Current Doctrine

### 1. Mistake: SAR-side work was advanced too early

Earlier work began organizing SAR migration evidence before the optical side had a stable expression of same-vehicle observations. That risked treating optical fragments as migration-ready when their physical referent was still unresolved.

Correction: SAR consumption is paused. The mainline returns to optical physical vehicle timeline evidence first.

### 2. Mistake: `track_id`, crop, and embedding were treated too much like identity evidence

`track_id` is a tracker label, not a real vehicle identity. A crop is the content inside a box, not the pure vehicle body. Embeddings are affected by visible part, background, edge truncation, and box drift.

Correction: establish same-vehicle referent consistency before any stitching or migration claim.

### 3. Correction: local short-window continuity should become graph edges

The important user correction was that short temporal windows are the core signal. If a local window can be visually connected, it should be represented as a local edge. Strong local connections become strong edges, weaker but plausible links become weak edges, and visual counterexamples become forbidden edges.

### 4. Doctrine: structural observations may change, but physical referent must not drift

Angle, box size, crop content, visible vehicle part, and appearance feature can change. Those changes do not break same-vehicle reasoning by themselves. What cannot change silently is the physical referent: the observations must still point to the same real vehicle, with no better competing target.

### 5. Doctrine: do not fall into pure CV algorithm research

The optical side should serve reviewable visual diagnosis, initial tracking, key-breakpoint manual or multimodal repair, and local-window transfer evidence. It should not become a separate pure ReID/detector/mAP research track.

### 6. Detector swap conclusion

Better YOLO variants can reduce some detector-layer errors, but they do not solve same-vehicle referent consistency or timeline stability. The multi-version detector probe is neutral. Baseline remains the mainline; other detector variants are only local sensitivity or negative-control probes.

## Current Doctrine

The current doctrine is:

- Do not ask first whether tracker IDs are continuous.
- Do not ask first whether crops or embeddings are similar.
- Do not ask first whether detector mAP or raw detection count is higher.
- Ask first whether boxes, fragments, and windows point to the same real vehicle in full-frame visual context.
- Convert only visually grounded referent evidence into graph nodes, strong edges, weak edges, forbidden edges, render items, and manual override candidates.
- Let the next session inspect rendered optical timeline videos and write the manual correction contract.

## Commit List

The current local branch is 12 commits ahead of `origin/feature/oty2-posthoc-mechanism-validation` before push. These are the session-relevant commits from the route reset through detector swap:

| Commit | Title | Role |
|---|---|---|
| `4d973a5` | Aggregate tracklet embeddings for stitching input | Shows the earlier embedding/stitching direction that was later deprioritized. |
| `4a0ca37` | Add OTY2 optical evidence visual judgement | Starts the visual judgement turn away from pure embedding evidence. |
| `6f53a37` | Plan repairable optical evidence for SAR migration | Captures the still-too-early migration framing before the route was corrected. |
| `656b198` | Review blocked optical cases for repairability | Audits blocked optical cases and repairability before same-referent graphing. |
| `dbf6804` | Validate targeted optical evidence repairs | Validates targeted optical repairs while still keeping repair evidence separate from final annotation. |
| `cd47254` | Define SAR migration evidence table from optical repairs | Defines SAR migration evidence structure; this is now paused until optical referents are review-stable. |
| `e7f50cb` | Reconstruct optical vehicle timelines for migration | Builds an optical timeline reconstruction attempt that motivated the later referent-consistency reset. |
| `869a7ba` | Contrast GM011 optical timeline breakpoints | Provides GM_RM011 breakpoint contrast cases for local continuity and forbidden links. |
| `4ca05aa` | Audit same-vehicle referent consistency | Establishes the same-vehicle referent audit as the controlling optical evidence layer. |
| `d52c14b` | Define optical timeline graph input contract | Converts referent audit results into graph nodes, edges, and render manifest contract. |
| `1050a59` | Probe detector swap impact on optical timeline stability | First detector-swap sensitivity probe using existing YOLO26l comparison and no-download placeholders. |
| `ca45161` | Probe downloaded detector variants for optical timeline stability | Runs downloaded detector variants outside the repo and confirms detector swap remains neutral. |

## Important Files

### Same-Vehicle Referent Consistency Audit

- `reports/oty2/oty2_same_vehicle_referent_consistency_20260705_165636.md`
- `reports/oty2/samples/oty2_same_vehicle_referent_consistency_summary_20260705_165636.csv`

Key findings:

- GM_RM017 `bs_0008`, `bs_0010`, and `bs_0012` are internally same-vehicle referent fragments.
- GM_RM017 `bs_0008 -> bs_0012` is a forbidden connection.
- GM_RM017 `bs_0002` is excluded as a non-vehicle referent.
- GM_RM011 `bs_0015 seg_001 -> seg_002` and `bs_0061 seg_002 -> seg_003` are same-vehicle local connections.
- GM_RM011 `bs_0061 seg_001 -> seg_002` is weak-connect only.
- GM_RM011 `bs_0061 -> bs_0064` and `bs_0056 -> bs_0061` are forbidden connections.
- The main failure layer is box/crop/feature representation and window connection, not direct real-vehicle identity failure.
- Conclusion label: `SAME_VEHICLE_REFERENT_READY_FOR_TIMELINE_GRAPH`.

### Optical Timeline Graph Input Contract

- `reports/oty2/oty2_optical_timeline_graph_input_contract_20260705_175222.md`
- `reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv`
- `reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv`
- `reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv`
- `tools/diagnostics/run_oty2_optical_timeline_graph_manifest.py`
- `tools/visualization/render_optical_timeline_video.py`

Verified counts:

- Nodes: 18 rows.
- Edges: 10 rows.
- Edge types: 2 `strong_same_vehicle_edge`, 4 `weak_same_vehicle_edge`, 3 `forbidden_edge`, 1 `non_vehicle_exclusion`.
- Render manifest: 311 rows.
- Smoke render: 198 frame PNGs in ignored `outputs`.
- Conclusion label: `OPTICAL_TIMELINE_GRAPH_INPUT_CONTRACT_READY_FOR_RENDERING`.

### Detector Swap Probe

First probe:

- `reports/oty2/oty2_detector_swap_timeline_stability_probe_20260705_214322.md`
- `reports/oty2/samples/oty2_detector_swap_detection_schema_20260705_214322.csv`
- `reports/oty2/samples/oty2_detector_swap_timeline_stability_summary_20260705_214322.csv`
- `tools/diagnostics/run_oty2_detector_swap_timeline_stability_probe.py`
- Conclusion label: `DETECTOR_SWAP_PROBE_NEUTRAL`.

Downloaded variant probe:

- `reports/oty2/oty2_detector_swap_timeline_stability_probe_20260705_221415.md`
- `reports/oty2/samples/oty2_detector_swap_detection_schema_20260705_221415.csv`
- `reports/oty2/samples/oty2_detector_swap_timeline_stability_summary_20260705_221415.csv`
- `tools/diagnostics/run_oty2_detector_swap_timeline_stability_probe.py`

Actual detectors:

- `baseline_oty0`
- `ultralytics_yolo26l_probe`
- `yolov8n.pt`
- `yolov8s.pt`
- `yolo11n.pt`
- `yolo12n.pt`
- `yolo26n.pt`

Downloaded weights were stored outside the repo under `D:/models/ultralytics/`.

Verified detector-swap counts:

- Unified detection schema: 2370 rows.
- Stability summary: 63 rows.
- Non-baseline effects: 5 improved, 39 worse, 8 neutral, 2 inconclusive.
- Improvements mainly occur in GM_RM017 `bs_0002` non-vehicle barrier exclusion.
- GM_RM011 same-vehicle and forbidden-connection windows often get higher missing-frame or multi-box pressure.
- Tracker replay was not run.
- SAR consumption was not entered.
- Conclusion label: `DETECTOR_SWAP_PROBE_NEUTRAL`.

## What Is Now Considered Solved

- The main optical unit is no longer a raw `track_id` or crop embedding. It is a visually grounded same-vehicle referent fragment.
- A bounded set of same-vehicle, weak-connect, forbidden, and non-vehicle-exclusion relations has been identified.
- GM_RM017 has usable local same-referent fragments for `bs_0008`, `bs_0010`, and `bs_0012`, while the unsafe cross-link and non-vehicle case are marked.
- GM_RM011 has local same-vehicle edges and forbidden-edge counterexamples for timeline diagnostics.
- A graph input contract exists with nodes, edges, and a video render manifest.
- Detector swap has been tested enough to conclude it should not replace the baseline in this stage.

## What Is Not Solved

- This is not a final vehicle chain.
- This is not a final annotation.
- This is not revised GT.
- This is not final box generation.
- This is not SAR pairing/support.
- This is not selector/ranking.
- This is not an identity-truth claim.
- This is not a detector-replacement decision.
- This does not prove runtime optical-to-SAR migration is safe.

## Detector Swap Conclusion

Detector variants are diagnostic tools only. They can reduce a local detector-layer error, especially for the GM_RM017 non-vehicle barrier case, but they also introduce more missing-frame and multi-box pressure in important GM_RM011 same-vehicle and forbidden-connection windows. The correct conclusion is `DETECTOR_SWAP_PROBE_NEUTRAL`.

Baseline OTY0 remains the mainline detector source for this stage. Downloaded detector weights must remain outside the repo and should only be used for local sensitivity or negative-control probes.

## Why SAR Consumption Is Still Paused

SAR consumption is paused because the optical side is only now reaching a reviewable timeline graph input. SAR migration requires stable optical referents, explicit weak/forbidden edges, and human-reviewable render evidence. Without that, SAR migration evidence tables can accidentally consume tracker IDs, crops, embeddings, or detector variants as if they were stable vehicle identity evidence.

Only same-referent optical fragments that survive video review and manual override rules should later become inputs to SAR migration.

## Next Recommended Step

**Review optical timeline video rendering + manual override contract.**

Operationally, the next session should review the optical diagnostic vehicle timeline render outputs, verify that rendered boxes and context support the graph edges, and define the manual correction table contract.

The next step is not more detector swap, not SAR consumption, and not final/revised annotation generation.

## Mandatory Reading Order For Next Session

1. `docs/OTY2_OPTICAL_TIMELINE_SESSION_CLOSEOUT_20260705.md`
2. `reports/oty2/oty2_same_vehicle_referent_consistency_20260705_165636.md`
3. `reports/oty2/samples/oty2_same_vehicle_referent_consistency_summary_20260705_165636.csv`
4. `reports/oty2/oty2_optical_timeline_graph_input_contract_20260705_175222.md`
5. `reports/oty2/samples/oty2_optical_timeline_graph_nodes_20260705_175222.csv`
6. `reports/oty2/samples/oty2_optical_timeline_graph_edges_20260705_175222.csv`
7. `reports/oty2/samples/oty2_optical_timeline_video_render_manifest_20260705_175222.csv`
8. `tools/visualization/render_optical_timeline_video.py`
9. `reports/oty2/oty2_detector_swap_timeline_stability_probe_20260705_221415.md`

## Forbidden Next Steps

Do not continue SAR consumption yet. Do not generate final boxes. Do not generate final or revised annotation. Do not run SAR pairing/support. Do not build selector/ranking. Do not treat tracker IDs, crops, embeddings, or detector variants as identity truth. Do not continue detector swap as the next main task.

## One-Sentence Stage Conclusion

OTY2 optical timeline work is ready to move from referent-consistency graph inputs to rendered video review and manual override rules, but it is not ready for SAR migration or final annotation.
