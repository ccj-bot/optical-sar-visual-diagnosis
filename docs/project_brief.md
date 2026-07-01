# Project Brief

## Goal

Build a clean visualization-first diagnostic framework for optical-to-SAR vehicle localization root-cause analysis.

The immediate target is not to reproduce the old pipeline and not to build a selector. V0 is designed to show where the transfer fails visually:

- optical azimuth fan band
- range prior band
- factor prior box
- SAR candidate source-family overlays
- factor evidence breakdown
- temporal range-offset strip

## Data Policy

Raw image data remains in local legacy paths such as `D:\profile\research\data\GM_RM019`. This repository stores only lightweight configs, manifests, code, docs, and report snapshots.

## Non-Goals

- No selector.
- No threshold tuning.
- No G2.
- No A008 scoring.
- No posthoc/final/oracle/GT leakage into runtime generation or ranking.
- No large images or binary model artifacts committed to Git.

## Required Reading

Every future Codex round must start from `docs/guidance/README.md`. The guidance documents define the current development protocol, no-go rules, hypothesis tree, file lineage, and inheritance gaps. Archive docs are historical evidence; guidance docs are the current operating rules.
