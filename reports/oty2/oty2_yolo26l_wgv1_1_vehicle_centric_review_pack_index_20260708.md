# OTY2 YOLO26l WGV1.1 Vehicle-Centric Review Pack Index

Date: `2026-07-08`

Repository: `D:/profile/research/optical-sar-visual-diagnosis`

Branch: `feature/oty2-posthoc-mechanism-validation`

## Boundary

This is a diagnostic vehicle-centric temporal review pack derived from YOLO26l WGV1.1. It is not final annotation, not final boxes, not GT boxes, not revised annotation, and not SAR-ready evidence. Baseline smoke render is comparison-only when available.

## Output Directory

```text
outputs/oty2/y26l_wgv1_1_vehicle_centric_review_20260708/
```

The output directory is ignored and must not be committed.

## Generated Index Files

- `README.md`
- `INDEX_BY_VEHICLE_GROUP.md`
- `INDEX_BY_SCENE_AND_FRAME.md`
- `GROUP_MANIFEST.csv`
- `FRAME_MANIFEST.csv`

## Summary

- vehicle_group folders: `1`
- standalone review/blocked/forbidden/weak fragment folders: `18`
- YOLO26l diagnostic frame images: `200`
- baseline comparison frame images: `192`
- SAR-ready: `no / blocked` for every group and fragment.

## Vehicle Groups

- `G001` `01_GM_RM011_vehicle_group_G001_weak` status `weak` fragments `GM_RM011_WG11F001;GM_RM011_WG11F002;GM_RM011_WG11F003;GM_RM011_WG11F004`. Same-vehicle links are weak diagnostic links only. SAR-ready: `no / blocked`.

## Standalone Fragment Folders

- `S001` `02_GM_RM011_fragment_GM_RM011_WG11F005_blocked` status `blocked` fragment `GM_RM011_WG11F005`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S002` `03_GM_RM011_fragment_GM_RM011_WG11F006_review_required` status `review_required` fragment `GM_RM011_WG11F006`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S003` `04_GM_RM011_fragment_GM_RM011_WG11F007_review_required` status `review_required` fragment `GM_RM011_WG11F007`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S004` `05_GM_RM011_fragment_GM_RM011_WG11F008_blocked` status `blocked` fragment `GM_RM011_WG11F008`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S005` `06_GM_RM011_fragment_GM_RM011_WG11F009_review_required` status `review_required` fragment `GM_RM011_WG11F009`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S006` `07_GM_RM011_fragment_GM_RM011_WG11F010_review_required` status `review_required` fragment `GM_RM011_WG11F010`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S007` `08_GM_RM011_fragment_GM_RM011_WG11F011_review_required` status `review_required` fragment `GM_RM011_WG11F011`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S008` `09_GM_RM011_fragment_GM_RM011_WG11F012_review_required` status `review_required` fragment `GM_RM011_WG11F012`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S009` `10_GM_RM011_fragment_GM_RM011_WG11F013_weak` status `weak` fragment `GM_RM011_WG11F013`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S010` `11_GM_RM011_fragment_GM_RM011_WG11F014_review_required` status `review_required` fragment `GM_RM011_WG11F014`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S011` `12_GM_RM011_fragment_GM_RM011_WG11F015_weak` status `weak` fragment `GM_RM011_WG11F015`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S012` `13_GM_RM011_fragment_GM_RM011_WG11F017_forbidden` status `forbidden` fragment `GM_RM011_WG11F017`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S013` `14_GM_RM011_fragment_GM_RM011_WG11F016_review_required` status `review_required` fragment `GM_RM011_WG11F016`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S014` `15_GM_RM017_fragment_GM_RM017_WG11F001_review_required` status `review_required` fragment `GM_RM017_WG11F001`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S015` `16_GM_RM017_fragment_GM_RM017_WG11F002_review_required` status `review_required` fragment `GM_RM017_WG11F002`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S016` `17_GM_RM017_fragment_GM_RM017_WG11F003_blocked` status `blocked` fragment `GM_RM017_WG11F003`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S017` `18_GM_RM017_fragment_GM_RM017_WG11F004_review_required` status `review_required` fragment `GM_RM017_WG11F004`. Not merged by temporal context. SAR-ready: `no / blocked`.
- `S018` `19_GM_RM017_fragment_GM_RM017_WG11F005_review_required` status `review_required` fragment `GM_RM017_WG11F005`. Not merged by temporal context. SAR-ready: `no / blocked`.

## Context Rule

Temporal context edges such as `front_to_front_encounter`, `rear_to_front_adjacency`, `vehicle_turnover_context`, `occlusion_context`, `competitor_vehicle_context`, and `same_frame_competition` are written into each folder `CONTEXT_LINKS.md`. They do not merge folders into the same vehicle identity group.

## Next Review

Human review should inspect each group folder slowly over time, then decide whether weak links remain valid, whether standalone fragments should remain separate, and whether any blocked/review_required item needs further diagnostic graph repair. No final boxes or SAR step should be produced from this pack.
