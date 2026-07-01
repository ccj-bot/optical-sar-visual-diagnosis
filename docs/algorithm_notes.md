# Algorithm Notes

This file is the short entry point. The full legacy formula archive is `docs/archive/algorithm_notes_20260701.md`.

## Fan-Polar To Display-XY

```text
x = Cx + r * sin(az) + cross * cos(az)
y = Cy - r * cos(az) + cross * sin(az)
```

`heading` is treated as a display-XY storage-axis convention, not vehicle heading.

## Candidate Delta

```text
delta_r = r - pred_r
delta_cross = cross - pred_cross
delta_az = wrapped_angular_delta(az, pred_az)
```

Delta fields are diagnostic evidence. They are not thresholds.

## Runtime Prior Sources

- `factor_inference_candidate`
- `base_candidate`
- `visible_support_candidate`
- `factor_topk_candidate`

## Structural Evidence

Wedge, ray, signed, and bidirectional candidates are visual/evidence sources. Their posterior or support fields are audit features unless a later, explicitly authorized calibration stage changes scope.
