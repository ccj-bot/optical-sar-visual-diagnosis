# Optical-SAR Visual Diagnosis

This repository is a clean, visualization-first root-cause diagnosis workspace for optical-to-SAR vehicle localization.

It is not a continuation of the legacy pipeline. It does not implement a selector, threshold tuning, G2, or A008 scoring. It references local raw data and legacy accounting artifacts through configs and manifests instead of copying large image data into Git.

## Scope

- Build visual diagnostics for optical-to-SAR transfer failures.
- Keep runtime candidate construction separate from posthoc evidence confirmation.
- Treat `candidate_source_family` as provenance, not an active runtime rule.
- Keep final/oracle/GT/posthoc IoU fields out of runtime generation and ranking.

## V0 Bootstrap

The V0 bootstrap contains:

- `configs/scene_config.yaml`
- `manifests/v0_sample_manifest.csv`
- `src/geometry/`
- `src/io/`
- `src/visualization/`
- `tools/diagnostics/run_v0_visual_diagnosis_bootstrap.py`
- `reports/v0/` summary snapshots from the first local run

Run from the repository root:

```powershell
D:\MINICONDA\envs\py311\python.exe tools\diagnostics\run_v0_visual_diagnosis_bootstrap.py
```

Outputs are written under `outputs/`, which is intentionally ignored by Git.

## Legacy Context

Legacy handoff notes are under `docs/archive/`. The legacy handoff zip remains outside Git and is only referenced from `docs/archive/README.md`.

## Required Guidance

Before each future development round, read `docs/guidance/README.md` and follow the guidance documents listed there. This guidance layer is the execution protocol; `docs/archive/` remains the historical record.

For any OTY2-related session, start with `docs/OTY2_SESSION_START_HERE.md` before reading task-specific prompts or reports.
