# OTY2 SAR Physical Factor Modeling Idea Archive

Updated: 2026-07-02

This document is an idea archive and handoff note for the OTY2 optical-to-SAR automatic annotation research line. It records discussion-level mechanism ideas that are not visible to Codex unless committed. It is not an experiment report, not an annotation proposal, and not a runtime prior-construction output.

The goal is to keep the next stage aligned with physical SAR imaging behavior, vehicle geometry, optical object streams, SAR temporal evidence, and posthoc GT validation, while avoiding heuristic stacking.

## Scope and boundary

Current stage:

```text
optical object stream
-> software-synchronized SAR temporal windows
-> runtime-safe weak spatial prior
-> vehicle eligibility and far/small stratification
-> GT sample ledger
-> optical-object/SAR-GT posthoc mechanism discovery
-> detection-dropout / severe truncation / temporal continuation / SAR support audit
-> physical factor modeling and stratified validation
```

This is not final automatic annotation and not formal OTY3.

Allowed in posthoc mechanism discovery:

```text
SAR GT
SAR image content
GT coverage
SAR morphology
SAR temporal scattering support
old imaging-code concepts as reference
```

Not allowed as runtime prior construction input:

```text
SAR GT-derived thresholds
SAR-image-derived prior rules written back into optical priors
manual/oracle/review fields as runtime truth
selector/ranking scores
identity truth claims
training or tuned thresholds
annotation proposals
```

Important distinction:

```text
SAR image evidence is not forbidden.
SAR image evidence is essential for final annotation reasoning.
The forbidden part is using posthoc GT/SAR evidence to secretly construct runtime optical priors.
```

## Current sample accounting to preserve

The 442 GT ledger must remain separated:

```text
total GT = 442
paired_optical_object_sar_gt = 215
blocked_missing_gm011_object_stream = 195
sar_only_gt = 20
detection dropout / no_oty_iou_match / truncated temporal continuation pool = 12
```

Interpretation:

- 215 is the current frame-level paired subset for optical-object/SAR-GT posthoc mechanism audit. It is not all GT and not 215 independent physical objects.
- GM_RM011 is not unannotated. Its main blocker is missing current OTY optical object stream.
- SAR-only samples must stay outside optical-to-SAR correspondence mechanism statistics, but can be used as SAR morphology and scattering reference.
- The 12 dropout/no-match rows are not ordinary failures. They expose severe truncation, current-frame detector dropout, optical temporal continuation, and SAR posthoc support.
- `existence_recovered_by_temporal_continuation` means target existence is recovered by temporal continuity. It does not mean clean paired morphology, identity truth, final SAR location, or automatic annotation.

## Why this file exists

Recent discussion clarified that the next stage should not collapse into candidate-box engineering. The purpose is not to generate many SAR candidates and rank them. The purpose is to study how the same vehicle is represented across:

```text
optical object trajectory
SAR temporal window
fan-polar / range-azimuth imaging geometry
vehicle physical footprint
SAR scattering morphology
SAR temporal continuity
posthoc SAR GT
```

The desired direction is explicit physical factor modeling:

```text
same physical vehicle
= optical object evidence
+ time synchronization evidence
+ azimuth projection evidence
+ vehicle-size shell evidence
+ optical morphology/range evidence
+ SAR image scattering evidence
+ SAR temporal continuity evidence
+ object-level/global consistency evidence
```

## Imaging-code reference: similar, not identical

A user-supplied MATLAB toolbox archive was reviewed as a physical reference. It should be treated as a similar imaging variant, not the exact pipeline for the current OTY2 sample set.

Observed reference elements from the toolbox:

```text
SaveImVideo.mlx:
- supports FFT / Dechirp / BP imaging modes
- reads DCA1000 raw data
- uses 1024 range samples
- uses Fs = 22.5e6
- uses fc = 76e9 and lambda = C / fc
- uses PRF = 9660
- computes K = Fs * C / (2 * Rmax)
- builds HRRP by range FFT
- constructs range and azimuth axes
- uses a range-azimuth grid Ax/Ay
- computes AR = sqrt(AX^2 + AY^2)
- computes AQ = asin(AX / AR)
- applies a squint/beam mask by AR and AQ
- BP mode integrates over aperture time using R = sqrt(AY^2 + (AX - ta * V)^2)
- applies exp(-j * 4*pi*R/lambda) phase compensation
- uses platform velocity Vfit for motion-dependent focusing
```

Auxiliary toolbox functions include:

```text
readDCA1000.m  -> raw complex ADC loading
FFTx/FFTy/FFTxy -> shifted FFT operations
IM_FFT_fun.m -> Range-Doppler to Range-Azimuth conversion
IRW.m -> impulse response width proxy
PSLR.m -> peak sidelobe ratio
ISLR.m -> integrated sidelobe ratio
ENL.m -> equivalent number of looks proxy
Rotate2D/RotateX/RotateY/RotateZ -> geometric rotation utilities
```

How to use this reference:

- Use it to understand SAR image formation concepts: range resolution, azimuth focusing, beam/squint mask, motion compensation, mainlobe/sidelobe, and scattering concentration.
- Do not assume its exact parameters, axes, frame rate, preprocessing, coordinate convention, or image display transform are identical to the current dataset.
- Do not copy local file paths or raw toolbox code into the research pipeline without a source/license and reproducibility review.
- If a compact reference implementation is later added to the repository, it should be explicitly placed under a reference or notes directory and marked as `similar_imaging_reference_only`.

## Physical factor families

### F_time: software synchronization and temporal tube

Known facts:

```text
optical fps = 24
SAR fps = 50
scale = 50 / 24
software-synchronized same start assumption
not hardware timestamp truth
millisecond-level jitter margin retained
```

Purpose:

```text
map optical object trajectory segments to SAR temporal windows,
not to exact SAR frames with timestamp truth.
```

The correct unit should be:

```text
optical object tracklet -> SAR target temporal tube
```

not:

```text
single optical frame -> single SAR frame
```

### F_az: azimuth / fan-polar mapping

SAR image coordinates should not be treated as generic 2D image coordinates. The physically meaningful coordinates are closer to:

```text
range r
azimuth angle az
cross-range / fan-polar offset
```

Prior work and imaging-code concepts both suggest that a range-azimuth or fan-polar representation is more meaningful than raw display XY.

Purpose:

```text
use optical object state and scene geometry to define a SAR azimuth sector,
then evaluate posthoc whether SAR GT centers fall inside or near that sector.
```

Questions:

- Does each scene require a scene-level azimuth bias?
- Are failures caused by state-specific uncertainty rather than global signed bias?
- Should complete, truncated, edge, far-small, and duplicate/handoff states use different azimuth margins?
- Does optical trajectory direction shift the azimuth-sector center or only its uncertainty?

### F_shell: vehicle physical footprint shell

Vehicles have approximate physical length and width. In SAR, the apparent GT box is not identical to optical box shape, but a vehicle footprint shell is still a physical constraint.

Purpose:

```text
intersect azimuth sector with physically plausible vehicle footprint support,
then measure compression and miss cases posthoc.
```

Important interpretation:

```text
100% coverage by a base/relaxed shell does not prove a precise mechanism.
It may mean the shell is conservative.
Tight-shell misses are more informative than relaxed-shell hits.
```

Questions:

- Which frames require relaxed shell and why?
- Are tight-shell misses associated with truncation, edge state, far-small targets, SAR scatter extension, or GT storage-axis convention?
- Does SAR long/short axis reflect vehicle footprint, scattering extent, shadow, or annotation convention?

### F_range_shape: optical morphology to SAR radial relation

Posthoc validation indicates that optical bbox height, bottom-y, and area may correlate with SAR radius, while aspect ratio is unstable as a standalone factor.

This should not be directly turned into a runtime rule.

Correct use:

```text
complete/stable/non-edge targets:
    test bbox height, bottom-y, and area as possible range-compression factors.

truncated/edge/far-small/duplicate targets:
    use these variables mainly to modulate uncertainty, not as hard range localization.
```

Questions:

- Is the relation stable within object-level trajectories, or mainly a repeated-frame effect?
- Does it hold in GM_RM019 after manual optical GT/identity review?
- Does it survive after GM_RM011 object stream recovery?
- Does optical bbox height reflect physical depth, detector crop, perspective, or truncation state?

### F_traj: optical trajectory direction and state continuity

Optical temporal structure is now available at object-hypothesis level. Tracker ID is not confirmed identity, but object_hypothesis_id is the runtime optical object unit.

Purpose:

```text
use optical object trajectory direction, bbox growth/shrink trend, and continuity state
to explain SAR GT center/radius/shape trend inside the corresponding SAR temporal tube.
```

Questions:

- Does optical center motion correspond to SAR center motion after fan-polar mapping?
- Does optical bbox growth/shrink correspond to SAR radial movement?
- Can temporal continuation explain current-frame optical detector dropout?
- Can primary observations provide the main trajectory while secondary observations represent uncertainty, partial-full transitions, duplicate boxes, and edge states?

### F_sar_image: SAR scattering and morphology evidence

SAR image content is essential for final annotation reasoning. The SAR observation layer should include scattering support, not just geometric priors.

Possible SAR-side factors:

```text
local peak support
box/background contrast
peak/background contrast
scattering centroid
mainlobe width / IRW proxy
PSLR / ISLR-like sidelobe behavior
long-axis / short-axis / aspect ratio
range-profile concentration
azimuth-profile concentration
shadow or weak-background evidence when available
```

Purpose:

```text
given an optical-derived temporal and spatial support region,
use SAR image evidence to decide whether a vehicle-like scattering structure exists.
```

Boundary:

```text
SAR image evidence can be used as SAR observation evidence.
It must not be rewritten into an optical-only runtime prior via GT leakage.
```

### F_sar_temporal: SAR temporal continuity

SAR is also temporal. This is central.

Purpose:

```text
link SAR scattering structures across adjacent SAR frames within the temporal tube,
and use SAR temporal consistency to support weak, missing, or partially observed optical frames.
```

Possible checks:

- Does a local scattering peak persist across adjacent SAR frames?
- Does SAR center drift follow a physically plausible direction?
- Does the long/short-axis structure stay coherent?
- Does a dropout frame have SAR support from neighboring frames?
- Can a high-confidence SAR frame anchor nearby lower-confidence frames?

### F_state: state-conditioned uncertainty

The factor model must be conditional on optical/SAR state, not a single global rule.

Suggested interpretation:

```text
complete_visible:
    stronger use of azimuth + shell + optical morphology/range cues.

truncated / edge:
    preserve azimuth and temporal continuity;
    weaken range-shape cue;
    widen shell and SAR search support.

far-small:
    optical box morphology is weak;
    use temporal window + azimuth + SAR local peak morphology more heavily.

duplicate / handoff:
    no identity truth claim;
    use object_hypothesis review and SAR temporal consistency.

detection_dropout:
    not clean paired morphology;
    use temporal continuation and SAR posthoc support only.
```

## Object-level/global formulation

The next model should be object-level and global, not independent frame-level candidate selection.

Latent variables may include:

```text
scene-level azimuth bias
scene-level range residual bias
software-sync jitter
object existence state
object identity continuity state
object motion direction
frame-level SAR center
frame-level SAR range/azimuth
frame-level SAR footprint size
frame-level SAR scattering support
state-dependent uncertainty scale
```

A future energy/factor graph formulation may combine:

```text
E_total =
  E_time
+ E_azimuth
+ E_vehicle_shell
+ E_optical_range_shape
+ E_sar_scattering
+ E_sar_temporal
+ E_identity_continuity
+ E_multi_object_exclusion
+ E_scene_bias_regularization
```

This is a modeling target, not a current implementation.

## High-confidence anchor propagation

High-confidence samples should not be used to copy labels. They should be used to estimate and propagate physical latent parameters.

Examples:

```text
scene-level azimuth residual
range residual trend
vehicle shell margin
SAR scattering morphology template
same-object motion direction
same-scene radial compression tendency
```

Propagation should be constrained by object identity uncertainty and state labels.

## Dataset-specific next actions

### GM_RM017 / GM_RM019 paired mechanism audit

Use the 215 paired subset for posthoc mechanism modeling, but keep object-level aggregation explicit. Current paired rows are frame-level; object count is much smaller. Do not treat repeated frames as independent physical evidence.

### GM_RM019 manual optical GT / identity review

If GM_RM019 contains many optical trajectories, a small amount of manual optical GT or identity review is useful.

Purpose:

```text
confirm object hypothesis continuity
separate main trajectory from secondary/partial/edge/duplicate observations
identify complete morphology frames
validate trajectory-direction-to-SAR-trend hypotheses
```

This is optical-side anchoring, not SAR annotation leakage.

### GM_RM011 object stream recovery

GM_RM011 is not unannotated. Its current blocker is missing OTY optical object stream. It should be processed through the same OTY0/OTY1/OTY1t object stream route before entering optical-SAR correspondence mechanism modeling.

### SAR-only reference pool

The 20 SAR-only rows should remain separate. They can support SAR morphology, scattering extent, and vehicle footprint reference, but not optical-to-SAR mapping statistics.

### Dropout/no-match pool

The 12 detection-dropout/no-match rows should remain separate from clean paired morphology. They should be used for existence recovery, temporal continuation, and SAR support diagnosis.

## Recommended next repository task

Recommended next task name:

```text
OTY2 object-level optical-SAR physical mechanism modeling plan and evidence ledger
```

Recommended outputs:

```text
docs/oty2_object_sar_physical_mechanism_modeling_plan.md
reports/oty2/oty2_object_level_mechanism_ledger_<timestamp>.csv
reports/oty2/oty2_factor_evidence_taxonomy_<timestamp>.csv
reports/oty2/oty2_legacy_structural_evidence_reinterpretation_<timestamp>.md
reports/oty2/oty2_mechanism_modeling_next_actions_<timestamp>.json
```

The task should answer:

```text
which physical factors are supported posthoc;
which factors are scene/state dependent;
which factors are only SAR-side observations;
which factors can later become runtime-safe evidence;
which factors require GM_RM019 manual optical review;
which factors require GM_RM011 object stream recovery;
how old wedge/ray/signed evidence should be reinterpreted as SAR structural factors, not selector sources.
```

## Prohibited shortcuts

Do not:

```text
treat 215 as all 442 GT;
treat GM_RM011 blocked rows as unannotated;
mix SAR-only rows into optical-to-SAR correspondence statistics;
mix dropout rows into clean paired morphology statistics;
treat frame-level correlation as object-level law;
generalize GM_RM017-dominated results to all scenes;
interpret relaxed shell coverage as precise localization;
write GT/SAR-image posthoc discoveries into runtime prior construction;
replace the mechanism line with a stronger YOLO claim;
return to selector/ranking/candidate-pool engineering before physical factors are defined.
```

## Summary

The next stage should study how optical temporal object evidence and SAR temporal scattering evidence jointly describe the same physical vehicle.

The correct direction is:

```text
physical factor modeling
-> posthoc stratified validation
-> state-conditioned uncertainty
-> object-level/global consistency
-> later runtime-safe inference design
```

not:

```text
more candidates
-> stronger selector
-> tuned threshold
-> automatic annotation before mechanism closure
```
