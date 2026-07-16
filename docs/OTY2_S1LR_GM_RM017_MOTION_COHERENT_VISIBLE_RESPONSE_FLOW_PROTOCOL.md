# OTY2 S1-LR GM_RM017 Motion-Coherent Visible Vehicle Response Flow Protocol

Date: `2026-07-16`

Frozen start HEAD: `938dd8e37b54592bc153f5518843c4f7479cfe24`

Chinese name: `S1-LR GM_RM017 330–350 可见车辆响应流与运动归属最小闭环`

## 1. Scope and semantic boundary

This is a bounded S1-L mechanism-discovery audit for `GM_RM017:PV002`, segment `S0MV-GM_RM017-PV002-SEG02`, SAR frames `330–350`. It does not enter S1-D.

The audit keeps three concepts separate:

1. `PHYSICAL_VEHICLE_TRAJECTORY`: the frozen GT research-reference centre trajectory;
2. `VISIBLE_SAR_RESPONSE_FLOW`: display-domain responses whose motion is tested against that trajectory;
3. `LATENT_FULL_BODY_SUPPORT`: unobserved or dark physical support, which is not reconstructed in this round.

Only the relation between the first two is studied. A visible response is not a final box, full-body support, identity truth, or an automatic annotation.

Forbidden operations include S1-D, GT modification, metric/pixel scaling, old optical-to-SAR mapping, final-box construction, latent full-body reconstruction, candidate-bank generation, selector/ranking, weighted/composite scoring, GT-IoU tuning, model training, and threshold tuning to manufacture PASS.

## 2. Frozen input contract

- Branch: `feature/oty2-sar-gt-structure-foundation`
- Start HEAD: `938dd8e37b54592bc153f5518843c4f7479cfe24`
- Manifest: `manifests/oty2/oty2_s1l_local_response_fields.csv`
- Manifest SHA256: `029d23d80638bfe2e115324140bfcccf9e4bb15ffeadf65f1920b244afa21092`
- Scene/vehicle/segment: `GM_RM017` / `GM_RM017:PV002` / `S0MV-GM_RM017-PV002-SEG02`
- Frames: exactly `330–350`, 21 rows
- Source size: exactly `2308×1334`
- Source SHA256: every image must match `raw_image_sha256`

`raw_anchor_center_x_px`, `raw_anchor_center_y_px`, `raw_anchor_width_px`, `raw_anchor_height_px`, `raw_anchor_angle_deg`, and crop polygons are already in SAR display pixels. They are used directly. No coordinate multiplication, metric conversion, fan-angle centre reconstruction, or historical cross-modal mapping is allowed.

## 3. Direct visual review gate

The motion runner is authorized only after direct multimodal review has been frozen in:

- `reports/oty2/oty2_s1lr_gm_rm017_motion_coherent_visible_response_direct_visual_review_20260716.md`
- `manifests/oty2/oty2_s1lr_gm_rm017_direct_visual_reviews.csv`

The review freezes these discovery facts before metric execution:

- primary response band: broad relative support around `x=[-140,+140] px`, `y=[-30,+90] px` from the raw GT centre, with the main bright response usually below the centre;
- state grouping: `330–338` weak/distributed, `339` transition onset, `340–350` strong/compact;
- mixed-background risk: `348–350` because the world-fixed vertical line and right-side bright complex approach or enter the GT neighbourhood.

These regions and stages are not selected by the metric outputs.

## 4. Pairwise motion evidence

For every adjacent pair, a fixed world-coordinate patch is centred at the midpoint of the tested trajectory positions. Two independent displacement methods are run on the same source patch and fixed preprocessing:

1. `PHASE_CORRELATION_HIGHPASS`: high-pass phase correlation with a Hanning window;
2. `DENSE_FARNEBACK_STRUCTURAL_MEDIAN`: dense Farneback flow summarized by a robust median over a frozen central structural mask.

The raw SAR sequence has a dominant image-plane drift. Four visually frozen background roles (nearby non-overlap background, vertical strong line, fan arc, and isolated hotspot) are therefore evaluated with both methods for every pair. Their method-wise median displacement is the local background/world reference `d_bg`. Raw-pixel zero displacement is not treated as world-fixed motion.

For each method and pair, retain the estimated `(dx, dy)`, method quality/support, background-reference displacement, and three separate residuals:

- `world_residual_motion = ||d_est - d_bg||`
- `vehicle_residual_motion = ||d_est - d_gt||`
- `wrong_track_residual_motion = ||d_est - (d_bg - (d_gt - d_bg))||`

Time-shifted trajectory residuals are recorded separately where the shifted reference exists. The methods are not averaged and no residuals are summed into a score.

## 5. Trajectory-conditioned offset field

Evaluate a frozen union of:

- coarse image-pixel offsets: `dx=-400…+400` step `100`, `dy=-240…+240` step `80`;
- fine image-pixel offsets: `dx=-160…+160` step `40`, `dy=-120…+120` step `40`.

Each offset independently records:

- track-aligned mean clarity;
- temporal median clarity;
- temporal MAD;
- positive-response persistence under a fixed local-background rule used only as one evidence channel;
- phase-correlation world/vehicle/wrong residuals;
- dense-flow world/vehicle/wrong residuals;
- vehicle-scale horizontal continuous-run proxy;
- fixed-world versus track-aligned clarity difference;
- valid-source fraction.

The field emits no total score, ranking, or winner. Offset category logic is relational and method-separated:

- `OUTSIDE_VALID_REGION`: insufficient valid source support;
- `MOTION_COHERENT_SUPPORT_CORRIDOR`: both independent methods have smaller vehicle residual than world and wrong-direction residuals, with usable method quality;
- `BACKGROUND_DOMINATED_REGION`: both methods have smaller world residual than vehicle residual;
- `AMBIGUOUS_OVERLAP_REGION`: method conflict, weak method quality, or mixed residual ordering.

Adjacent offsets may cover the same vehicle response and remain one support corridor. No single-point optimum is expected or required.

## 6. Spatial counterfactuals

All spatial controls use the same 21 original frames, patch size, display normalization, local-background rule, and summary metrics. The frozen roles are:

- correct trajectory;
- near-left and near-right offsets that still overlap the same vehicle response;
- nearby non-overlap background diagnostic;
- vertical strong-line diagnostic;
- fan-arc diagnostic;
- isolated-hotspot diagnostic.

Near offsets are not treated as true vehicle negatives. Role names are visual-review hypotheses; motion evidence must remain separate and may return mixed or unresolved.

## 7. Time and motion counterfactuals

Using the same source frames and extraction contract, evaluate:

- deterministic centre-order shuffle;
- reversed centre correspondence;
- exact trajectory shifts `±4`, `±8`, `±12` without circular wrap;
- horizontal speed scales `0.5×` and `1.5×`;
- constant-speed wrong horizontal direction;
- fixed median centre.

Each counterfactual reports valid frame count, aligned mean/median clarity, temporal MAD, positive persistence, phase residual after compensation, and dense-flow residual after compensation. The output describes tolerance to position, speed, and temporal error; it does not require every small perturbation to fail.

## 8. Response-state evidence

Per-frame evidence is measured in the frozen broad response patch and stored separately from direct review. It includes raw intensity, local-background-normalized intensity, positive fraction, horizontal-run proxy, weighted response centroid, and structure-tensor long-axis orientation. Stages remain fixed from direct review:

- `WEAK_DISTRIBUTED_330_338`
- `TRANSITION_ONSET_339`
- `STRONG_COMPACT_340_350`

Metrics may describe the transition but may not move the boundary or select a new template.

## 9. Exploratory response attribution map

A broad GT-centred relative patch is evaluated under three coordinate hypotheses: correct trajectory, a fixed-world trajectory constructed by accumulating the multi-background reference displacement, and a wrong-direction trajectory that reverses the GT motion relative to that world trajectory. Preserve independent maps for positive persistence, median normalized response, correct-track MAD, fixed-world MAD, and wrong-track MAD.

The exploratory map may use conservative multi-evidence rules to emit only:

- `PERSISTENT_VEHICLE_ASSOCIATED_RESPONSE`
- `INTERMITTENT_VEHICLE_ASSOCIATED_RESPONSE`
- `WORLD_FIXED_BACKGROUND`
- `CROP_OR_RESAMPLING_ARTIFACT`
- `UNRESOLVED_MIXED_RESPONSE`

`CURRENTLY_DARK_LATENT_BODY_REGION` is not auto-assigned. It remains a descriptive GT-reference debt only. Category rules do not use GT-box inside/outside membership and the evidence maps remain the primary output.

## 10. Required conclusions

The final report and stage table must separately state:

- `LOCAL_VISIBLE_VEHICLE_RESPONSE_FLOW`
- `VEHICLE_MOTION_OWNERSHIP`
- `WORLD_BACKGROUND_SEPARATION`
- `RESPONSE_STATE_TRANSITION`
- `MOTION_COHERENT_SUPPORT_CORRIDOR`
- `VISIBLE_RESPONSE_UNIQUENESS_IN_LOCAL_NEIGHBORHOOD`
- `EXACT_CENTER_IDENTIFIABILITY`
- `FULL_BODY_SUPPORT_READINESS`
- `OPTICAL_INPUT_REPLACEMENT_READINESS`
- `S1D_READINESS`

One global `NOT_READY` is invalid. Positive local-response evidence must be preserved even when exact centre, full-body support, optical-input replacement, and S1-D remain unestablished.

## 11. Replay boundary

Frames `330–350` are the mechanism-discovery window. This run must not expand to all vehicles or produce a population-level conclusion. The final report may recommend a frozen-rule replay order only:

1. adjacent PV002 window;
2. one directly visible continuous PV003 window;
3. one directly visible continuous PV004 window;
4. GM_RM011 diagnostic window.

Replay is a future action. It must reuse the frozen methods, fields, stage definitions, and counterfactual roles without reselection.
