# New Repo Transition Plan - 2026-07-01

## Goal

New repository goal:

```text
visualization-first root-cause diagnosis for optical-to-SAR transfer
```

新仓库不继承旧仓库混乱 pipeline。它只引用原始数据路径和旧输出中的小型 accounting/manifest/config artifacts，不复制原始大图像数据，不修改正式 pipeline。

## Recommended Directory Layout

```text
configs/
manifests/
src/geometry/
src/io/
src/priors/
src/candidates/
src/factors/
src/visualization/
src/evaluation/
tools/diagnostics/
docs/
reports/
outputs/
```

V0 bootstrap 已经建立其中的基础子集：`configs/`、`manifests/`、`src/geometry/`、`src/io/`、`src/visualization/`、`tools/diagnostics/`、`docs/`、`reports/`、`outputs/`。

## V0 Visual Diagnosis Bootstrap

第一阶段只做可视化诊断：

- `configs/scene_config.yaml`
- `manifests/v0_sample_manifest.csv`
- optical-to-SAR transfer panel
- candidate overlay panel
- factor breakdown panel
- temporal strip panel
- missing path report
- `index.html`

V0 输出应按 timestamp 写入：

```text
outputs/v0_visual_diagnosis_<timestamp>/
```

## V0 Forbidden Scope

- 不做 selector
- 不设 threshold
- 不做 G2
- 不做 A008 scoring
- 不根据 posthoc IoU 调参
- 不复制大数据进 git
- 不把 posthoc/final/oracle/GT 字段用于 runtime generation/ranking

## Diagnostic Focus

新仓库第一阶段重点诊断：

- 光学方位向扇形带是否正确
- range prior 是否系统偏
- SAR 目标是否落在 range band 内
- 候选是否围绕错误 prior 生成
- wedge/ray/signed 是否真的贴近车结构
- 时序是否支持 range 修正
- GM_RM011 与 GM_RM019 是否有几何/视觉差异

## Transition Inheritance

Allowed inheritance:

- path references to `D:\profile\research\data\GM_RM011`
- path references to `D:\profile\research\data\GM_RM017`
- path references to `D:\profile\research\data\GM_RM019`
- old C1.1/C1.2/C1.3/C1.4 accounting CSV paths
- fan-polar geometry constants and mapping correction config references
- diagnostic conclusions from archive docs

Not inherited:

- formal pipeline mutation
- old selector implementation
- threshold tuning
- G2 execution
- A008 scoring
- posthoc oracle/final/GT leakage
- large image copies

## Next Bootstrap Steps

1. Expand `v0_sample_manifest.csv` with manually selected visual failures from C1S and C1.4.
2. Add GM_RM011 accounting once its chain is reproduced or explicitly mark it as missing in visual reports.
3. Add optional `src/priors/`, `src/candidates/`, and `src/factors/` only after V0 panels show which layer is failing.
4. Keep all visual reports linked through `outputs/v0_visual_diagnosis_<timestamp>/index.html`.
