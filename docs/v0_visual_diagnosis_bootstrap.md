# V0 Visual Diagnosis Bootstrap

This repository starts a visualization-first diagnostic framework for optical-to-SAR vehicle localization.

The V0 boundary is diagnostic only:

- no selector
- no threshold
- no G2
- no A008 scoring
- no candidate changes from posthoc IoU
- no large image copies into the repository

`configs/scene_config.yaml` stores scene paths and fan geometry. It is YAML-compatible JSON so the bootstrap can run without PyYAML.

`manifests/v0_sample_manifest.csv` can be edited manually. Rows may also point to old C1.3/C1.4 accounting CSVs through `candidate_accounting_csv`; the diagnostic runner reads those tables as evidence sources and leaves missing factors as `missing`.
