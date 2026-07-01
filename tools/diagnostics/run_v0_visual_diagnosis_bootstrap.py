"""Run V0 visualization-first diagnostic bootstrap.

This runner reads only manifests/configs and existing referenced files. It does
not copy source images into the repository, change candidates, score selectors,
or use posthoc fields for runtime generation/ranking.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.io.config import get_scene_config, load_scene_config
from src.io.manifest import (
    collect_missing_paths,
    load_candidates_for_sample,
    load_manifest,
    write_csv,
)
from src.visualization.candidate_overlay import render_candidate_overlay
from src.visualization.factor_breakdown import render_factor_breakdown
from src.visualization.temporal_strip import render_temporal_strip
from src.visualization.transfer_panel import render_transfer_panel


def _safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text.strip("_") or "sample"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_index(output_dir: Path, entries: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    rows = []
    for item in entries:
        rows.append(
            "<tr>"
            f"<td>{item['sample_id']}</td>"
            f"<td>{item['sample_type']}</td>"
            f"<td>{item['scene']}</td>"
            f"<td>{item['candidate_count']}</td>"
            f"<td><a href=\"{item['transfer_panel']}\">transfer</a></td>"
            f"<td><a href=\"{item['candidate_overlay']}\">overlay</a></td>"
            f"<td><a href=\"{item['factor_breakdown']}\">factors</a></td>"
            f"<td><a href=\"{item['temporal_strip']}\">temporal</a></td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>V0 Visual Diagnosis Bootstrap</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 28px; color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    code {{ background: #f3f4f6; padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>V0 Visual Diagnosis Bootstrap</h1>
  <p>Generated at <code>{summary['generated_at']}</code>.</p>
  <p>Boundary: no selector, no threshold, no G2, no A008 scoring, no posthoc-driven candidate changes.</p>
  <ul>
    <li>transfer panels: {summary['counts']['transfer_panels']}</li>
    <li>candidate overlays: {summary['counts']['candidate_overlays']}</li>
    <li>factor breakdowns: {summary['counts']['factor_breakdowns']}</li>
    <li>temporal strips: {summary['counts']['temporal_strips']}</li>
    <li>missing paths: {summary['missing_path_count']}</li>
  </ul>
  <table>
    <thead>
      <tr>
        <th>sample_id</th><th>sample_type</th><th>scene</th><th>candidates</th>
        <th>transfer</th><th>overlay</th><th>factors</th><th>temporal</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def _ensure_report_templates(reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    findings = reports_dir / "v0_findings_template.md"
    hypotheses = reports_dir / "v0_problem_hypotheses.md"
    if not findings.exists():
        findings.write_text(
            "# V0 Visual Diagnosis Findings Template\n\n"
            "Record case-level visual findings here. Missing fields stay `missing`.\n",
            encoding="utf-8",
        )
    if not hypotheses.exists():
        hypotheses.write_text(
            "# V0 Problem Hypotheses\n\n"
            "Use transfer panels, overlays, factor tables, and temporal strips to test hypotheses visually.\n",
            encoding="utf-8",
        )


def run(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    manifest_path = Path(args.manifest)
    output_root = Path(args.output_root)
    reports_dir = Path(args.reports_dir)
    config = load_scene_config(config_path)
    samples = load_manifest(manifest_path, config)

    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / f"v0_visual_diagnosis_{timestamp}"
    subdirs = {
        "transfer_panels": output_dir / "transfer_panels",
        "candidate_overlays": output_dir / "candidate_overlays",
        "factor_breakdowns": output_dir / "factor_breakdowns",
        "temporal_strips": output_dir / "temporal_strips",
    }
    for subdir in subdirs.values():
        subdir.mkdir(parents=True, exist_ok=True)
    _ensure_report_templates(reports_dir)

    counts = {
        "transfer_panels": 0,
        "candidate_overlays": 0,
        "factor_breakdowns": 0,
        "temporal_strips": 0,
    }
    entries: list[dict[str, Any]] = []
    extra_missing: list[tuple[str, str, str]] = []
    for sample in samples:
        scene = sample.get("scene", "")
        scene_config = get_scene_config(config, scene)
        candidates = load_candidates_for_sample(sample)
        stem = _safe_name(sample.get("sample_id", "sample"))
        transfer_path = subdirs["transfer_panels"] / f"{stem}_transfer_panel.svg"
        overlay_path = subdirs["candidate_overlays"] / f"{stem}_candidate_overlay.svg"
        factor_path = subdirs["factor_breakdowns"] / f"{stem}_factor_breakdown.svg"
        temporal_path = subdirs["temporal_strips"] / f"{stem}_temporal_strip.svg"

        counts["transfer_panels"] += render_transfer_panel(sample, candidates, scene_config, transfer_path)
        counts["candidate_overlays"] += render_candidate_overlay(sample, candidates, scene_config, overlay_path)
        counts["factor_breakdowns"] += render_factor_breakdown(sample, candidates, factor_path)
        temporal_count, temporal_missing = render_temporal_strip(sample, candidates, scene_config, temporal_path)
        counts["temporal_strips"] += temporal_count
        extra_missing.extend(temporal_missing)

        entries.append(
            {
                "sample_id": sample.get("sample_id", ""),
                "sample_type": sample.get("sample_type", ""),
                "scene": scene,
                "target_identity": sample.get("target_identity", ""),
                "candidate_count": len(candidates),
                "transfer_panel": str(transfer_path.relative_to(output_dir)).replace("\\", "/"),
                "candidate_overlay": str(overlay_path.relative_to(output_dir)).replace("\\", "/"),
                "factor_breakdown": str(factor_path.relative_to(output_dir)).replace("\\", "/"),
                "temporal_strip": str(temporal_path.relative_to(output_dir)).replace("\\", "/"),
            }
        )

    missing_paths = collect_missing_paths(samples, extra_missing)
    missing_path_report = output_dir / "missing_path_report.csv"
    write_csv(missing_path_report, missing_paths, ["sample_id", "kind", "path", "reason"])

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config": str(config_path),
        "manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "sample_count": len(samples),
        "counts": counts,
        "missing_path_count": len(missing_paths),
        "missing_path_report": str(missing_path_report),
        "reports": {
            "findings_template": str(reports_dir / "v0_findings_template.md"),
            "problem_hypotheses": str(reports_dir / "v0_problem_hypotheses.md"),
        },
        "scope_boundary": config.get("forbidden_scope", {}),
        "entries": entries,
    }
    _write_json(output_dir / "v0_summary.json", summary)
    _write_index(output_dir, entries, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/scene_config.yaml")
    parser.add_argument("--manifest", default="manifests/v0_sample_manifest.csv")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
