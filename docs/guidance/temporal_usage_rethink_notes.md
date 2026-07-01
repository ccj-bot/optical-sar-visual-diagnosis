# Temporal Usage Rethink Notes

Current temporal evidence is shallow.

True temporal use should include:

- same-track identity
- frame-wise range trajectory
- temporal candidate tube
- range offset continuity
- shared offset diagnostic
- signed direction persistence
- cross-frame SAR structure consistency

The current temporal strip is only an initial visualization. It is useful context, but it does not mean temporal evidence is truly used.

## What Future Temporal Diagnosis Should Ask

- Do neighboring frames support a consistent range offset?
- Do wedge/ray offsets stay coherent across frames?
- Does a candidate belong to a plausible same-vehicle trajectory?
- Are signed pos/neg votes stable?
- Does SAR structure remain visually consistent across frames?

Temporal evidence should help decide whether a structural/range escape candidate deserves release. It should not become a hard selector rule without explicit calibration and review.
