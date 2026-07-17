# OTY2 RSA0 R1 Template Atlas Correction Addendum

Date: `2026-07-17`

Branch: `feature/oty2-sar-gt-structure-foundation`

Frozen R1 start HEAD: `206fe5f5f587fec711df8d1856fbce925817d940`

This addendum explicitly corrects the RSA0 v0 response atlas and representation diagnosis without rewriting or hiding the frozen v0 artifacts.

## Frozen v0 artifacts

The following v0 artifacts remain preserved as historical evidence:

- Atlas version: `OTY2-RSA0-response-atlas-v0-manual-review-seeded`
- Original atlas freeze SHA: `12ba29f758053da5bda024d160fad4fef5fe150017b1bcd5c008bdebba26476c`
- v0 response atlas config: `configs/oty2/oty2_rsa0_response_atlas.json`
- v0 skeletons: `manifests/oty2/oty2_rsa0_response_skeletons.csv`
- v0 regions: `manifests/oty2/oty2_rsa0_response_atlas_regions.csv`
- v0 background controls: `manifests/oty2/oty2_rsa0_background_controls.csv`
- v0 representation metrics: `manifests/oty2/oty2_rsa0_representation_channel_metrics.csv`
- v0 diagnosis report: `reports/oty2/oty2_rsa0_representation_diagnosis_20260717.md`

## Required v0 problem record

1. The v0 atlas was generated from SAR GT center plus a fixed `geometry_template`.
2. The only intended per-frame skeleton adjustment in v0 was `skeleton_y_offsets`; the skeleton x-offset bank was fixed.
3. `DEFINITE_TARGET_RESPONSE`, `PROBABLE_TARGET_RESPONSE`, support, `MIXED_STRUCTURE`, and `UNRESOLVED` were fixed template rectangles translated per frame.
4. The background vertical line and fan arc were also GT-relative template geometry.
5. Positive/background/unresolved sample counts were mechanically repeated because the regions were generated from the same template shapes.
6. The direct visual review text in v0 was templated per frame and did not provide actual per-frame morphology descriptions.
7. The v0 temporal channels used sparse keyframes rather than the full continuous sequences `PV002 330-350` and `PV003 360-384`.
8. The v0 representation findings are therefore only preliminary hypotheses, not final representation conclusions.
9. The v0 atlas is not allowed as a propagation, training, physical-interpretation, final-mask, or winner/ranking reference.

## R1 correction boundary

R1 introduces a new atlas version:

`OTY2-RSA0-response-atlas-v1-free-geometry`

R1 outputs use `_v1` or `_r1` suffixes and do not overwrite v0 files. Large review overlays are stored outside Git under:

`D:\profile\research\workspace\output\oty2_rsa0_r1_20260717`

R1 stops at response-atlas correction and continuous temporal representation reaudit. It does not enter seed propagation, object memory, lifecycle modeling, cross-scene generalization, GM_RM019 automatic recovery, GM_RM011 pressure testing, S1-D events, final masks, weighted fusion, winner/ranking, VOS, or training.

## R1 validity statement

The R1 atlas is valid only as a reviewed free-geometry response atlas and representation-reaudit basis. It is not yet an authorization to start automatic propagation or training. The next stage may be designed only after keeping the v1 skeletons, background controls, temporal continuity diagnostics, and optical-proxy drift gates explicit.
