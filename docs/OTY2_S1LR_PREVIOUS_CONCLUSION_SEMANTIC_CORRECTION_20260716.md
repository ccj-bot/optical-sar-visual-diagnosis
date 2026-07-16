# OTY2 S1-LR Previous Conclusion Semantic Correction

Date: `2026-07-16`

Applies to frozen report:

`reports/oty2/oty2_s1lr_gm_rm017_motion_coherent_visible_response_flow_audit_20260716.md`

The frozen report is not modified. This document limits two conclusions whose original tests are not valid ownership or support-corridor tests under common scene transport.

## 1. Vehicle motion ownership

The frozen report correctly observed that the GT centre, the visible horizontal response, and multiple background structures share approximately the same cumulative image-plane transport over frames `330–350`. It then used the comparison

```text
vehicle residual < background residual
```

as a necessary condition for assigning motion ownership to the vehicle.

That condition is not applicable here. A static vehicle and static background can share the dominant image transport produced by imaging, scanning, platform, or display-coordinate change. Failure to show differential bulk translation does not show that the local response belongs to the background.

The corrected conclusion is therefore:

```text
VEHICLE_MOTION_OWNERSHIP
= NOT_TESTABLE_BY_DIFFERENTIAL_BULK_TRANSLATION
```

This correction does not positively assign the response to the vehicle. It states that the previous bulk-translation differential is not an ownership test for this sequence.

## 2. Motion-coherent support corridor

The frozen report classified offsets as a motion-coherent support corridor only when two displacement methods both gave a smaller residual to Raw-GT adjacent displacement than to common background displacement.

Raw-GT adjacent displacement is not an error-free physical motion truth, and shared scene transport removes the expected differential translation. The resulting corridor criterion is therefore invalid for this sequence.

The corrected conclusion is:

```text
MOTION_COHERENT_SUPPORT_CORRIDOR
= NOT_EVALUATED_BY_VALID_SUPPORT_CRITERION
```

The old zero-corridor result must not be read as evidence that no visible response corridor exists. A new corridor, if any, must be based on stabilized local response persistence and organization rather than differential bulk translation.

## 3. Raw-GT adjacent-motion debt

The frozen report used

```text
raw_anchor_center[t+1] - raw_anchor_center[t]
```

as the adjacent vehicle-motion reference. In this window the Raw-GT source family alternates between original and supplementary annotations, and the single-frame increments contain clear jitter while the full-window trajectory remains close to common scene transport.

The three GT uses must now remain separate:

1. `GT_NEIGHBORHOOD_POSITION_REFERENCE`: allowed for discovery-shell extraction and posthoc interpretation;
2. `GT_FULL_WINDOW_TRAJECTORY_REFERENCE`: allowed after raw/smoothed/common-transport debt is reported;
3. `GT_ADJACENT_PHYSICAL_DISPLACEMENT_TRUTH`: not established and must not be used as optical-flow truth.

## 4. Replay boundary

The frozen S1-LR rule set must not be directly replayed to `GM_RM017:PV003`, `GM_RM017:PV004`, or `GM_RM011`. Any later replay requires the S1-LR2 background-stabilized local-response protocol and a separately frozen background-anchor review for the target window.

This correction remains inside S1-L. It does not authorize S1-D, final boxes, latent full-body reconstruction, automatic annotation, selector/ranking, candidate banks, model training, GT-IoU tuning, or threshold tuning for PASS.
