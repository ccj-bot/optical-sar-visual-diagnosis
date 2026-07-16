# OTY2 S1-LR2 GM_RM017 Common-Scene Transport and Local Vehicle Response Organization Protocol

Date: `2026-07-16`

Chinese name: `S1-LR2 共同场景运输稳定化与车辆局部响应组织审计`

English name: `S1-LR2 Common-Scene Transport Stabilization and Local Vehicle Response Organization Audit`

Frozen start HEAD: `8eb4b99e3fefb41ba2449c5e53ea3b7338e8591b`

## 1. Stage and semantic boundary

This is a bounded S1-L audit for `GM_RM017:PV002`, segment `S0MV-GM_RM017-PV002-SEG02`, SAR frames `330–350`. It does not enter S1-D.

The research objects are:

1. `COMMON_SCENE_TRANSPORT`: shared image transport without forcing one unique physical cause;
2. `LOCAL_VEHICLE_RESPONSE_ORGANIZATION`: persistent lower horizontal response, intermittent upper segments, endpoint hotspots, and their stabilized relations;
3. `LATENT_FULL_BODY_SUPPORT`: forbidden in this round.

The core question is whether, after common-scene transport removal, the frozen GT/discovery shell contains local response organization and continuous state change that is not reproduced as a complete relation set by matched background controls. Independent vehicle translation is not required.

## 2. Frozen inputs

- Branch: `feature/oty2-sar-gt-structure-foundation`
- Start HEAD: `8eb4b99e3fefb41ba2449c5e53ea3b7338e8591b`
- Input manifest: `manifests/oty2/oty2_s1l_local_response_fields.csv`
- Input manifest SHA256: `029d23d80638bfe2e115324140bfcccf9e4bb15ffeadf65f1920b244afa21092`
- Selection: `GM_RM017` / `GM_RM017:PV002` / `S0MV-GM_RM017-PV002-SEG02` / frames `330–350`
- Source size: `2308×1334`
- Raw image SHA256 must match all 21 manifest rows.

Raw and smoothed anchors are display-pixel research references. No metric conversion, historical optical-to-SAR scale, fan-angle reconstruction, GT modification, or GT-IoU parameter selection is allowed.

## 3. Required semantic correction

The previous report remains frozen. Its limiting correction is recorded in:

`docs/OTY2_S1LR_PREVIOUS_CONCLUSION_SEMANTIC_CORRECTION_20260716.md`

Required conclusions:

```text
VEHICLE_MOTION_OWNERSHIP=NOT_TESTABLE_BY_DIFFERENTIAL_BULK_TRANSLATION
MOTION_COHERENT_SUPPORT_CORRIDOR=NOT_EVALUATED_BY_VALID_SUPPORT_CRITERION
```

No previous corridor rule is replayed to another vehicle or scene.

## 4. Raw-GT motion debt

For each frame and adjacent pair retain separately:

- raw and smoothed centre positions;
- raw and smoothed adjacent increments;
- selected common-transport increment;
- raw/common and smoothed/common residuals;
- cumulative trajectories;
- local speed and acceleration;
- GT source family and source-switch indicator.

The audit reports three uses independently:

- `GT_NEIGHBORHOOD_POSITION_REFERENCE`;
- `GT_FULL_WINDOW_TRAJECTORY_REFERENCE`;
- `GT_ADJACENT_PHYSICAL_DISPLACEMENT_TRUTH`.

Raw-GT adjacent differences are not optical-flow truth.

## 5. Background anchors and identity continuity

Eight frame-330 background structures are frozen before transport-model fitting. Six are fit anchors and two are holdout anchors. They cover the required roles and at least two additional spatially independent structures:

1. vertical strong line;
2. central fan arc;
3. isolated hotspot;
4. nearby non-vehicle curved structure;
5. left arc branch holdout;
6. right diagonal background fragment;
7. an additional upper diagonal background fragment;
8. an additional left section of the fan arc.

The nearby non-vehicle curve and left arc branch are excluded from fitting and used as the two spatial holdouts. Direct review rejected an initially proposed upper-right arc because it left the tracked crop after the early frames; that proposal is not retained in the final anchor set.

For every anchor and frame retain:

- structure-match centre and displacement;
- phase-correlation centre and displacement;
- normalized template-match quality;
- phase response;
- method disagreement;
- fit/holdout role;
- direct-review identity status;
- structure-switch or vehicle-mixing status.

Anchor identity is not inferred from a GT-relative offset name. Contact sheets and before/after GIFs must be reviewed directly.

The union discovery shell around the vehicle is excluded from all common-transport fitting.

## 6. Transport-model ladder

The following models are evaluated in order with method-separated residuals:

1. `GLOBAL_TRANSLATION`;
2. `LOCAL_AFFINE`;
3. `RADIAL_TANGENTIAL_LINEAR_FIELD`;
4. `SPARSE_THIN_PLATE_FIELD`.

Model choice is based on:

- residuals on fit anchors after stabilization;
- replay residuals on holdout anchors;
- whether residuals show spatially systematic bias;
- transform complexity;
- whether added complexity materially reduces holdout residuals without instability.

No weighted or composite score is computed. The selected model is frozen in the stage report and runner output. Vehicle-region pixels, GT motion, or vehicle response are not fitting inputs.

## 7. Stabilization outputs and acceptance facts

All frames are mapped to frame 330 background coordinates. Required external artifacts include:

- raw full-frame and fixed-ROI GIFs;
- stabilized full-frame and matched fixed-ROI GIFs;
- before/after GIFs for the vertical line, fan arc, isolated hotspot, and vehicle region;
- all-anchor contact sheets;
- background residual time series;
- valid-mask GIF and montage;
- interpolation-impact GIF and temporal map;
- raw/smoothed/common-transport trajectory plots.

Stabilization is supported only if multiple holdout background structures show substantially lower residuals. Aligning one region is insufficient. Vehicle GT is not used to estimate the transform.

## 8. Frozen vehicle reference ranges

All local-response analyses are run with the same stabilized frames and fixed preprocessing over:

1. a wide GT neighbourhood used only as a discovery shell;
2. a coarse centre corridor frozen before stabilization;
3. an expanded neighbourhood;
4. non-overlapping matched background regions.

GT-box inside/outside membership is not a pixel label. The output vocabulary is limited to:

- `PERSISTENT_LOCAL_RESPONSE_CORE`;
- `INTERMITTENT_LOCAL_RESPONSE_REGION`;
- `BACKGROUND_STRUCTURE`;
- `MIXED_OR_UNRESOLVED_REGION`.

## 9. Local-response representations

Two independent local representations are required:

1. robust-z response components with connected-component geometry;
2. line-segment/direction fragments with explicit relative spatial relations.

Per frame retain the lower main horizontal response set, intermittent upper segments, endpoint hotspots, component centres, lengths, widths, orientation, connectivity, relative positions, intensity, morphology, and state group.

No embedding, candidate bank, total score, rank, winner, or final box is produced.

## 10. Matched-background counterfactuals

Matched background regions use the same stabilization, interpolation, frame range, window size, response normalization, component extraction, and relation extraction. Radial position, dynamic range, and structure complexity are reported separately; they are not combined into a matching score.

The audit independently checks whether a background region reproduces:

1. a vehicle-scale horizontal main band;
2. persistent lower-side bias;
3. the main-band/upper-hotspot relation;
4. continuous enhancement beginning at frame 339;
5. stable multi-part relations inside one spatial shell.

Reproducing one strong line or one hotspot is not reproduction of the complete relation set.

## 11. State-transition review

The frozen groups remain:

- `330–338`;
- `339`;
- `340–350`.

After stabilization, review whether the main band remains in one local position, whether frame-339 enhancement is local rather than a background line entering the window, whether frames `348–350` can be separated from fixed background structures, and whether upper responses vary coherently with the main band.

Only stabilized, relation-level evidence may support:

```text
LOCAL_VEHICLE_RESPONSE_STATE_TRANSITION_SUPPORTED
```

## 12. Required conclusions

The stage table must separately report:

- `COMMON_SCENE_TRANSPORT_MODEL`
- `BACKGROUND_STABILIZATION_QUALITY`
- `RAW_GT_ADJACENT_MOTION_RELIABILITY`
- `LOCAL_HORIZONTAL_RESPONSE_CORE`
- `LOCAL_MULTI_PART_RESPONSE_ORGANIZATION`
- `VEHICLE_VS_MATCHED_BACKGROUND_RELATION_SET`
- `RESPONSE_STATE_TRANSITION_AFTER_STABILIZATION`
- `VISIBLE_RESPONSE_SUPPORT_CORRIDOR`
- `FULL_BODY_SUPPORT_READINESS`
- `OPTICAL_INPUT_REPLACEMENT_READINESS`
- `S1D_READINESS`

## 13. Prohibited outputs

This round prohibits S1-D, final boxes, latent full-body reconstruction, automatic annotation, selector/ranking, candidate banks, embeddings, weighted/composite scores, GT-IoU tuning, model training, threshold tuning for PASS, and expansion to other vehicles before stabilization review is complete.
