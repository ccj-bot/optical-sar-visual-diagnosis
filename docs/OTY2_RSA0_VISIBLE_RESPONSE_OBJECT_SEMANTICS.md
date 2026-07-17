# OTY2-RSA0 Visible Response Object Semantics

Date: `2026-07-17`

This document freezes the annotation and evaluation semantics for the OTY2-RSA0 SAR Visible Response Atlas. It is a docs-only contract. It does not authorize an automatic recovery runner, candidate ranking, final vehicle boxes, or deployment-time use of target SAR GT.

## 1. Object Definition

A visible SAR response object is the short-window, vehicle-conditioned response that a reviewer can conservatively attribute to the same physical vehicle after jointly viewing optical identity context, SAR GT neighbourhood context, and continuous SAR grayscale frames.

It is not:

- a complete vehicle box;
- a dense vehicle mask;
- a fixed horizontal-band template;
- a set of independent bright points;
- a physical scattering-centre explanation;
- a final localization output.

It is an object-level research reference made from a main response skeleton, local definite response, probable or intermittent response, temporal relations, background counterexamples, and unresolved mixed regions. Different vehicles may have different response morphology. The same vehicle may also change shape, width, intensity, continuity, and local components across weak, medium, and strong observation states.

## 2. Coordinate Systems

All region geometry must declare one coordinate system.

- `sar_display_px`: direct displayed SAR image pixel coordinates. This is the default geometry coordinate for RSA0 atlas work.
- `world_stabilized_px`: frame-stabilized display coordinates derived from background transport. This is for background and relation checks, not target truth.
- `research_gt_conditioned_px`: target-GT-conditioned research coordinates. Any artifact using this coordinate must be marked `RESEARCH_ORACLE_COORDINATE_ONLY`.
- `optical_proxy_conditioned_px`: optical-proxy-conditioned coordinates for checking whether response evidence remains available without target SAR GT.

No RSA0 document, manifest, or metric may treat the old `0.03 m/pixel` note as a global metric scale, true resolution, PSF, or vehicle-size proof.

## 3. Allowed Geometry Types

Allowed geometries are:

- `polyline`: ordered points, used for skeletons and response center traces.
- `sparse_scribble`: one or more thin strokes marking high-confidence local evidence.
- `polygon`: conservative filled region for definite, probable, background, support, mixed, or unresolved areas.
- `point`: local hotspot or endpoint only when it is tied to a skeleton, region, or temporal relation.
- `bbox`: context, crop, review window, or index only. A bbox alone cannot define visible target response.

Every geometry row must record `case_id`, `vehicle_id`, `sar_frame`, `coordinate_system`, `geometry_type`, `label`, `confidence`, `source_role`, `review_status`, and `version`.

## 4. Required Labels

### 4.1 `DEFINITE_TARGET_RESPONSE`

Pixels, scribbles, or polyline segments that a reviewer can conservatively attribute to the target vehicle response in the current frame.

Allowed geometry: `sparse_scribble`, `polyline`, `polygon`, and tied `point`.

Rules:

- keep it smaller rather than include ambiguous boundary pixels;
- do not fill the whole GT box;
- do not include a bright background line just because it intersects the target neighbourhood;
- do not infer hidden vehicle body.

### 4.2 `PROBABLE_TARGET_RESPONSE`

Weak, intermittent, boundary, or locally mixed structures that may belong to the target vehicle but are not certain enough to be positive truth.

Allowed geometry: `polygon`, `polyline`, `sparse_scribble`, and tied `point`.

Rules:

- it may overlap a response support region;
- it must not be counted as hard positive in primary precision/recall;
- it should be reported separately for activation and weak-state retention.

### 4.3 `DEFINITE_BACKGROUND`

Structures that are confidently not the target response in the current review context.

Allowed geometry: `sparse_scribble`, `polyline`, `polygon`, and tied `point`.

Rules:

- choose same-frame or comparable local background when possible;
- prefer same radial or nearby radial context with similar display range;
- exclude target GT expansion and other known vehicle neighbourhoods unless the purpose is explicit other-vehicle exclusion;
- include vertical strong lines, fan arcs, fixed hotspots, diagonal lines, low-texture background, and persistent shell-internal background only after direct review.

### 4.4 `UNRESOLVED`

Areas where target response, background, interpolation/stabilization artefact, or other-vehicle structure cannot be separated reliably.

Allowed geometry: `polygon` and, for narrow ambiguity, `polyline`.

Rules:

- do not force unresolved pixels into positive or negative labels;
- exclude unresolved areas from hard positive/negative metrics;
- report channel responses inside unresolved areas as a distribution only.

### 4.5 `MAIN_RESPONSE_SKELETON`

The conservative centerline or broken centerlines of the visually dominant target response relation in a frame or short window.

Allowed geometry: `polyline`.

Rules:

- it is the main object relation, not necessarily the brightest pixels;
- it may be discontinuous;
- it may shift, widen, weaken, or strengthen across frames;
- it has a local geometric center only for the skeleton, not for the physical vehicle.

### 4.6 `INTERMITTENT_RESPONSE_COMPONENT`

A local component that appears only in some frames or states but maintains a plausible relation to the main response object.

Allowed geometry: `polyline`, `sparse_scribble`, `polygon`, and tied `point`.

Rules:

- require temporal or spatial relation to the main skeleton;
- do not promote it to main skeleton without direct sequence evidence;
- keep it separate from isolated bright points that lack object relation.

### 4.7 `HIGH_CONFIDENCE_RESPONSE_SEED`

A minimal seed used to mark the safest local evidence for later seed-object-propagation research.

Allowed geometry: `sparse_scribble`, short `polyline`, and tied `point`.

Rules:

- it must be inside or on `DEFINITE_TARGET_RESPONSE`;
- it must not be selected by channel score after evaluation;
- it is a reference seed, not an automatic algorithm output.

### 4.8 `RESPONSE_SUPPORT_REGION`

A conservative context region around the visible response object used for cropping, local comparison, and support-limited evaluation.

Allowed geometry: `polygon`; `bbox` only for crop indexing.

Rules:

- it may contain definite response, probable response, unresolved areas, and local background;
- it is not a positive mask;
- it cannot be used as the visible-response denominator unless sublabels are explicitly selected.

### 4.9 `BACKGROUND_STRUCTURE`

A named background pattern that can visually imitate part of the target response.

Allowed geometry: `polyline`, `sparse_scribble`, `polygon`, and tied `point`.

Rules:

- record the subtype when known: `vertical_line`, `fan_arc`, `fixed_hotspot`, `diagonal_line`, `low_texture`, `persistent_shell_background`, or `other`;
- compare direction, relative position, local parts, cross-state behaviour, and world-stabilized persistence;
- do not reject a target solely because one background structure has a similar single feature.

### 4.10 `MIXED_STRUCTURE`

A region where target-like and background-like structures appear spatially mixed, and direct review cannot assign one clean owner.

Allowed geometry: `polygon` and, for thin mixtures, `polyline`.

Rules:

- it may overlap `UNRESOLVED`;
- it must not be counted as hard positive or hard negative;
- it should preserve notes about the suspected mixture source.

## 5. Mutual Exclusion And Overlap Rules

Within one atlas version and one frame:

- `DEFINITE_TARGET_RESPONSE` and `DEFINITE_BACKGROUND` must not overlap.
- `HIGH_CONFIDENCE_RESPONSE_SEED` must be contained by `DEFINITE_TARGET_RESPONSE` or by `MAIN_RESPONSE_SKELETON` with a linked definite response note.
- `MAIN_RESPONSE_SKELETON` may pass through `DEFINITE_TARGET_RESPONSE` and may have nearby `PROBABLE_TARGET_RESPONSE`.
- `PROBABLE_TARGET_RESPONSE` may overlap `RESPONSE_SUPPORT_REGION` and may touch `UNRESOLVED`, but it must not overlap `DEFINITE_BACKGROUND`.
- `UNRESOLVED` may overlap `RESPONSE_SUPPORT_REGION` and `MIXED_STRUCTURE`.
- `BACKGROUND_STRUCTURE` may be a subtype of `DEFINITE_BACKGROUND`; if it is only suspected background, use `MIXED_STRUCTURE` or `UNRESOLVED` instead.
- `RESPONSE_SUPPORT_REGION` is a container. It can overlap all local sublabels, but it has no positive or negative truth value by itself.

If a later review finds an overlap violation, the atlas must be versioned and refrozen before representation metrics are rerun.

## 6. GT Boundary

SAR GT is allowed for:

- confirming physical vehicle identity;
- confirming a reasonable target neighbourhood;
- excluding areas clearly belonging to other vehicles;
- establishing research-only target coordinates;
- posthoc evaluation of frozen atlas and representations.

SAR GT is not allowed to:

- generate a target response mask automatically;
- mark the full box as `DEFINITE_TARGET_RESPONSE`;
- define the visible-response denominator by itself;
- enter deployment inference;
- tune representation channels after metric inspection;
- turn a centroid, persistent pixel, or bright point into the physical vehicle centre.

Any artifact derived from target GT alignment must declare `source_role=RESEARCH_ORACLE_COORDINATE_ONLY`.

## 7. Annotation Confidence

Use these confidence levels:

- `1.0 definite`: direct visual evidence, stable reviewer rationale, and no unresolved ownership conflict.
- `0.75 high_probable`: strong but not final evidence, often weak-state or boundary response.
- `0.5 probable`: plausible relation to the object, but ambiguous enough to exclude from hard truth.
- `0.25 unresolved`: visible structure exists but ownership cannot be assigned.
- `0.0 negative`: definite background or explicit non-target structure.

Confidence is not a training weight. It is a review statement used to separate hard positive, probable, background, and unresolved evidence.

## 8. Evaluation Use

Primary hard-positive evaluation may use only `DEFINITE_TARGET_RESPONSE`, `MAIN_RESPONSE_SKELETON`, and `HIGH_CONFIDENCE_RESPONSE_SEED`.

Background evaluation may use only `DEFINITE_BACKGROUND` and confirmed `BACKGROUND_STRUCTURE`.

`PROBABLE_TARGET_RESPONSE`, `INTERMITTENT_RESPONSE_COMPONENT`, `UNRESOLVED`, and `MIXED_STRUCTURE` must be reported separately. They are central to diagnosis, but they must not be silently folded into a binary mask.

No channel may be declared a winner by weighted score. RSA0 reports a non-dominated representation set and failure modes.

## 9. Versioning Requirement

The atlas must be frozen before representation scoring. The freeze includes windows, keyframes, all geometries, background controls, unresolved regions, review pages, configuration files, and aggregate hashes.

If any reference geometry changes after scoring begins, publish a new atlas version and rerun the affected representation metrics. Silent correction of frozen semantics is prohibited.
