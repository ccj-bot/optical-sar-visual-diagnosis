# OTY2 Next Branch Research Questions

This is the next-branch task list. It is not an instruction to start all work now.

## Branch Starting Point

Recommended new branch name:

`feature/oty2-posthoc-mechanism-validation`

Start it from the current pushed head after the OTY2 stage recap. Do not branch from older commits before GT accounting, no-match triage, or detection-dropout support.

## Guardrails For Next Branch

- Keep runtime-safe construction separate from posthoc mechanism validation.
- SAR GT and SAR image content may be used only in posthoc mechanism validation unless explicitly reauthorized.
- Do not generate automatic annotation proposals.
- Do not train or tune thresholds.
- Do not use selector/ranking.
- Do not claim identity truth.
- Do not submit model weights.
- Do not merge detection-dropout rows into clean paired rows.

## Research Questions

### 1. Azimuth Sector Margin Ablation

Question: how much azimuth margin is needed before coverage collapses?

Inputs:

- 215 paired optical-object-to-SAR-GT rows
- state labels: edge, partial, duplicate, handoff, ambiguous, review-only

Outputs:

- coverage vs margin table
- failure cases by scene and object state
- posthoc-only interpretation

Do not convert the best margin directly into a runtime threshold.

### 2. Vehicle Physical Size Shell Ablation

Question: do tight/base/relaxed vehicle-size shells preserve GT coverage while reducing broad azimuth bands?

Compare:

- tight shell
- base shell
- relaxed shell
- state-aware relaxed shell

Report coverage and compression separately. Do not overclaim absolute range localization without a runtime-safe range anchor.

### 3. Optical Box Shape vs SAR Radius Validation

Question: is the optical bbox area/height/bottom-y relationship with SAR radius stable across scene, object, and state?

Split by:

- GM_RM017 vs GM_RM019
- main/weak/review-only vehicle eligibility
- edge/partial/truncated
- secondary-supported detection dropout

Keep this posthoc-only until a runtime-safe hypothesis is independently defined.

### 4. Optical Temporal Trajectory vs SAR Trend

Question: does optical track motion direction or bbox growth/shrink trend align with SAR radius or azimuth trend?

Check:

- complete visible vehicles
- truncated/edge vehicles
- detection-dropout pool
- far-small vehicles

Do not use temporal trend as identity truth.

### 5. GM_RM011 Object Stream Recovery

Question: can GM_RM011 enter object-level correspondence after OTY object flow is built?

Required steps:

1. Run GM_RM011 through the same OTY0/OTY1/OTY1t object-stream construction.
2. Keep construction runtime-safe: no SAR GT, no SAR image evidence.
3. Re-run GT sample accounting.
4. Re-run correspondence mechanism audit only after accounting confirms object-frame availability.

Expected effect:

- reduce `blocked_missing_gm011_object_stream`
- possibly increase paired rows or no-match triage rows

### 6. Detection Dropout YOLO Small-Sample A/B

Question: can a stronger detector recover the 12 severe truncation/current-frame dropout cases?

Use:

- the 12 detection-dropout rows
- current frame plus +/- 3, 5, and 10 optical frames

Metrics:

- severe truncation vehicle recovery
- primary missing rate
- secondary-only rate
- containment / overlap against review box
- far-small noise increase
- track continuity
- duplicate / handoff rate

Do not submit weights. Do not treat detection count as the main metric.

### 7. SAR-Only Morphology And Scattering Statistics

Question: what do SAR-only GT boxes reveal about SAR vehicle footprint and scattering without optical correspondence?

Use the 20 SAR-only rows separately.

Outputs:

- SAR GT width/height/aspect distribution
- local scatter peak/background distribution
- state or scene grouping if available

Do not mix SAR-only rows into optical-to-SAR correspondence statistics.

### 8. Stronger YOLO And Main Research Vehicle Quality

Question: does stronger YOLO improve main research vehicle quality rather than just adding far-small noise?

Metrics:

- main research vehicle coverage
- weak/far-small/review-only/blocked distribution
- track continuity
- duplicate/handoff
- primary vs secondary observation split
- downstream normal/review/blocked prior distribution

Success means better research eligibility and continuity, not more boxes.

## Stop Rules

Stop and write a short audit note if a proposed step would:

- use SAR GT or SAR images to construct runtime priors
- turn posthoc coverage into a selector rule
- produce automatic annotation proposals
- tune a threshold as a training result
- collapse sample pools into one undifferentiated dataset

