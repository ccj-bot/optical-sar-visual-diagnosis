# OTY2-S1X Missing Inputs and Boundary Report

Date: `2026-07-17`

## Available and used

- P1-E canonical optical benchmark and frame states: available, optical-only, research benchmark.
- P0 24/50 time map: available as a frozen project operational assumption.
- GM_RM017 optical frames, depth sidecars, and SAR gray frames: available.
- Fixed fan geometry and imaging-valid mask: available and frozen.
- Independent calibration vehicle: `GM_RM017:PV004`, `43` usable rows.

## Missing or unresolved

- Automatic deployment-time canonical optical identity output is not available; P1-E is benchmark-only.
- Depth sidecar generator, absolute unit, and deployment packaging are unresolved.
- The calibration is one vehicle in one scene and does not establish cross-scene or cross-pose mapping.
- SAR metric grid, raw amplitude, complex image, IQ/ADC, and fixed grayscale mapping are unresolved.

## Forward-use decision

The missing fields do not force a return to a target-reference neighbourhood. S1X continues with explicit azimuth/radial intervals, a minimum `8 deg` azimuth half-width, a minimum `120 px` radial half-width, and broad unsigned-axis/size ranges. No missing value is silently synthesized as precise truth.

## Isolation

- Calibration target: `GM_RM017:PV004` only.
- Discovery/replay targets excluded from calibration fit: `GM_RM017:PV002, GM_RM017:PV003`.
- Target-reference rows used in inference: `0`.
- `old_work` runtime dependency: `none`.
