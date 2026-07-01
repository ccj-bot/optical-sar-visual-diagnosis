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
    CANDIDATE_LOADING_REPORT_FIELDS,
    MISSING_FIELD_REPORT_FIELDS,
    collect_missing_candidate_fields,
    collect_missing_paths,
    load_candidates_with_report,
    load_manifest,
    write_csv,
)
from src.io.source_registry import (
    REGISTRY_FIELDS,
    build_input_source_registry,
    write_registry_json,
    write_registry_markdown,
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
            f"<td>{item['target_identity']}</td>"
            f"<td>{item['source_id']}</td>"
            f"<td>{item['source_kind']}</td>"
            f"<td>{item['candidate_count']}</td>"
            f"<td>{item['fallback_used']}</td>"
            f"<td>{item['posthoc_debug_enabled']}</td>"
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
    <li>candidate loading fallbacks: {summary['candidate_loading']['fallback_count']}</li>
    <li>missing field rows: {summary['missing_field_count']}</li>
    <li>missing paths: {summary['missing_path_count']}</li>
  </ul>
  <p>
    Reports:
    <a href="{summary['artifacts']['report_md']}">run report</a>,
    <a href="{summary['artifacts']['input_source_alignment_report']}">source alignment</a>,
    <a href="{summary['artifacts']['candidate_loading_report']}">candidate loading CSV</a>,
    <a href="{summary['artifacts']['case_review_sheet_prefill']}">review sheet prefill</a>.
  </p>
  <table>
    <thead>
      <tr>
        <th>sample_id</th><th>sample_type</th><th>scene</th><th>target</th>
        <th>source_id</th><th>source_kind</th><th>candidates</th><th>fallback</th><th>posthoc_debug</th>
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


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "") or "missing")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "- none\n"
    return "".join(f"- {key}: {value}\n" for key, value in counts.items())


def _join_missing(rows: list[dict[str, Any]], sample_id: str, key: str) -> str:
    values = [str(row.get(key, "")) for row in rows if row.get("sample_id") == sample_id]
    return ";".join(value for value in values if value) or ""


def _write_review_sheet(
    path: Path,
    entries: list[dict[str, Any]],
    missing_fields: list[dict[str, Any]],
    missing_paths: list[dict[str, Any]],
) -> None:
    review_fields = [
        "sample_id",
        "scene",
        "target_identity",
        "sample_type",
        "panel_transfer_path",
        "panel_candidate_overlay_path",
        "panel_factor_breakdown_path",
        "panel_temporal_strip_path",
        "source_id",
        "source_kind",
        "candidate_count",
        "fallback_used",
        "missing_fields",
        "missing_paths",
        "optical_azimuth_ok",
        "range_prior_contains_target",
        "candidate_pool_contains_vehicle_like_box",
        "top1_visually_on_vehicle",
        "top5_contains_vehicle_like_box",
        "top20_contains_vehicle_like_box",
        "candidates_centered_on_wrong_prior",
        "wedge_helpful",
        "ray_helpful",
        "signed_helpful",
        "temporal_context_helpful",
        "likely_root_cause",
        "next_action",
        "notes",
    ]
    rows: list[dict[str, Any]] = []
    for entry in entries:
        sample_id = entry["sample_id"]
        rows.append(
            {
                "sample_id": sample_id,
                "scene": entry["scene"],
                "target_identity": entry["target_identity"],
                "sample_type": entry["sample_type"],
                "panel_transfer_path": entry["transfer_panel"],
                "panel_candidate_overlay_path": entry["candidate_overlay"],
                "panel_factor_breakdown_path": entry["factor_breakdown"],
                "panel_temporal_strip_path": entry["temporal_strip"],
                "source_id": entry["source_id"],
                "source_kind": entry["source_kind"],
                "candidate_count": entry["candidate_count"],
                "fallback_used": entry["fallback_used"],
                "missing_fields": _join_missing(missing_fields, sample_id, "field"),
                "missing_paths": _join_missing(missing_paths, sample_id, "kind"),
                "optical_azimuth_ok": "",
                "range_prior_contains_target": "",
                "candidate_pool_contains_vehicle_like_box": "",
                "top1_visually_on_vehicle": "",
                "top5_contains_vehicle_like_box": "",
                "top20_contains_vehicle_like_box": "",
                "candidates_centered_on_wrong_prior": "",
                "wedge_helpful": "",
                "ray_helpful": "",
                "signed_helpful": "",
                "temporal_context_helpful": "",
                "likely_root_cause": "",
                "next_action": "",
                "notes": "",
            }
        )
    write_csv(path, rows, review_fields)


def _write_markdown_report(path: Path, summary: dict[str, Any], changed_files: list[str]) -> None:
    fallback_rows = summary["candidate_loading"]["fallback_rows"]
    fallback_text = "\n".join(
        f"- {row['sample_id']}: source={row['requested_source_id']} reason={row['fallback_reason']} rows={row['fallback_row_count']} first_target={row['first_target_used_if_fallback']}"
        for row in fallback_rows
    ) or "- none"
    missing_path_text = "\n".join(
        f"- {row['sample_id']}: {row['kind']} -> {row['reason']} ({row['path']})"
        for row in summary["missing_paths"][:40]
    ) or "- none"
    lines = [
        "# V0.1 Input Source Alignment Report",
        "",
        "## Working Hypothesis",
        "",
        "- H0: The repository has inherited enough guidance/archive context, but V0 remains a bootstrap visualization shell.",
        "- H1: The largest engineering risk is input source lineage confusion, especially C1.4 frozen ranked candidates versus workspace C1.4 partial factor tables.",
        "- H2: If source lineage and fallback behavior are not made explicit first, visual panels can look complete while relying on the wrong input source.",
        "- H3: GM_RM019 is the candidate/range/structure/temporal pilot scene.",
        "- H4: GM_RM017 is only a reference/control scene; legacy proxy experience is not a runtime rule.",
        "- H5: GM_RM011 is a geometry/path/convention probe scene until its candidate chain is reproduced.",
        "",
        "## Files Read",
        "",
        "Guidance, archive, config, manifest, runner, geometry/io, visualization modules, and V0 report snapshots listed in the V0.1 task request were read before code edits.",
        "",
        "## Changed Files",
        "",
        _format_counts({path: 1 for path in changed_files}),
        "## Input Source Lineage",
        "",
        f"- registry entries: {summary['input_source_count']}",
        f"- workspace sources: {summary['input_source_origin_counts'].get('workspace', 0)}",
        f"- synthesis mirror sources: {summary['input_source_origin_counts'].get('synthesis_mirror', 0)}",
        f"- manual sources: {summary['input_source_origin_counts'].get('manual', 0)}",
        "- frozen ranked tables, partial factor audits, posthoc accounting, and manual probes are separate source kinds.",
        "",
        "## Fallback Summary",
        "",
        fallback_text,
        "",
        "## Scene Coverage Summary",
        "",
        _format_counts(summary["scene_coverage"]),
        "## Sample Type Coverage Summary",
        "",
        _format_counts(summary["sample_type_coverage"]),
        "## Missing Fields / Paths",
        "",
        f"- missing field rows: {summary['missing_field_count']}",
        f"- missing path rows: {summary['missing_path_count']}",
        missing_path_text,
        "",
        "## Boundary Check",
        "",
        "- no selector",
        "- no threshold",
        "- no G2",
        "- no A008 scoring",
        "- no posthoc/final/oracle/GT leakage into runtime generation or ranking",
        "- candidate_source_family remains provenance only",
        "- temporal strip is context shell only, not identity-supported track-level temporal evidence",
        "",
        "## What Remains Hypothesis",
        "",
        "Human review still needs to decide whether failures are optical azimuth, range prior expression, candidate pool ceiling, structural evidence, temporal shallowness, or scene convention.",
        "",
        "## What Is Supported By Visual/Accounting Evidence",
        "",
        "This run supports source lineage visibility, fallback visibility, bounded sample coverage, and panel generation. It does not support selector, threshold, G2, A008, or mechanism-success claims.",
        "",
        "## Next Recommended Action",
        "",
        "Fill the human review sheet from the generated panels before authorizing scoring, threshold, selector, or candidate-generation changes.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    manifest_path = Path(args.manifest)
    output_root = Path(args.output_root)
    reports_dir = Path(args.reports_dir)
    config = load_scene_config(config_path)
    samples = load_manifest(manifest_path, config)
    registry = build_input_source_registry(config)

    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = args.run_name
    output_dir = output_root / f"{run_name}_{timestamp}"
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
    candidates_by_sample: dict[str, list[dict[str, str]]] = {}
    loading_reports: list[dict[str, Any]] = []
    for sample in samples:
        scene = sample.get("scene", "")
        scene_config = get_scene_config(config, scene)
        candidates, loading_report = load_candidates_with_report(sample)
        sample["_candidate_count"] = str(len(candidates))
        sample["_fallback_used"] = str(bool(loading_report.get("fallback_used", False))).lower()
        candidates_by_sample[sample.get("sample_id", "")] = candidates
        loading_reports.append(loading_report)
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
                "source_id": sample.get("source_id", ""),
                "source_kind": sample.get("source_kind", ""),
                "candidate_count": len(candidates),
                "fallback_used": bool(loading_report.get("fallback_used", False)),
                "posthoc_debug_enabled": sample.get("posthoc_debug_enabled", ""),
                "transfer_panel": str(transfer_path.relative_to(output_dir)).replace("\\", "/"),
                "candidate_overlay": str(overlay_path.relative_to(output_dir)).replace("\\", "/"),
                "factor_breakdown": str(factor_path.relative_to(output_dir)).replace("\\", "/"),
                "temporal_strip": str(temporal_path.relative_to(output_dir)).replace("\\", "/"),
            }
        )

    missing_paths = collect_missing_paths(samples, extra_missing)
    missing_path_report = output_dir / "missing_path_report.csv"
    write_csv(missing_path_report, missing_paths, ["sample_id", "kind", "path", "reason"])
    missing_fields = collect_missing_candidate_fields(samples, candidates_by_sample)
    missing_field_report = output_dir / "missing_field_report.csv"
    write_csv(missing_field_report, missing_fields, MISSING_FIELD_REPORT_FIELDS)
    candidate_loading_report = output_dir / "candidate_loading_report.csv"
    write_csv(candidate_loading_report, loading_reports, CANDIDATE_LOADING_REPORT_FIELDS)

    registry_json = output_dir / "input_source_registry.json"
    registry_md = output_dir / "input_source_alignment_report.md"
    write_registry_json(registry_json, registry)
    write_registry_json(Path(args.registry_json), registry)
    write_registry_markdown(Path(args.registry_doc), registry)
    write_registry_markdown(registry_md, registry)

    case_review_sheet_prefill = output_dir / "case_review_sheet_prefill.csv"
    _write_review_sheet(case_review_sheet_prefill, entries, missing_fields, missing_paths)
    _write_review_sheet(Path(args.review_sheet), entries, missing_fields, missing_paths)

    fallback_rows = [row for row in loading_reports if row.get("fallback_used")]
    report_name = "v0_1_report.md" if run_name.startswith("v0_1") else "v0_report.md"
    summary_name = "v0_1_summary.json" if run_name.startswith("v0_1") else "v0_summary.json"

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config": str(config_path),
        "manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "sample_count": len(samples),
        "counts": counts,
        "missing_path_count": len(missing_paths),
        "missing_field_count": len(missing_fields),
        "missing_path_report": str(missing_path_report),
        "missing_field_report": str(missing_field_report),
        "input_source_count": len(registry),
        "input_source_origin_counts": _count_by(registry, "source_origin"),
        "scene_coverage": _count_by(entries, "scene"),
        "sample_type_coverage": _count_by(entries, "sample_type"),
        "candidate_loading": {
            "report": str(candidate_loading_report),
            "fallback_count": len(fallback_rows),
            "fallback_rows": fallback_rows,
        },
        "missing_paths": missing_paths,
        "reports": {
            "findings_template": str(reports_dir / "v0_findings_template.md"),
            "problem_hypotheses": str(reports_dir / "v0_problem_hypotheses.md"),
        },
        "artifacts": {
            "report_md": report_name,
            "input_source_registry": str(registry_json.relative_to(output_dir)).replace("\\", "/"),
            "input_source_alignment_report": str(registry_md.relative_to(output_dir)).replace("\\", "/"),
            "candidate_loading_report": str(candidate_loading_report.relative_to(output_dir)).replace("\\", "/"),
            "missing_field_report": str(missing_field_report.relative_to(output_dir)).replace("\\", "/"),
            "missing_path_report": str(missing_path_report.relative_to(output_dir)).replace("\\", "/"),
            "case_review_sheet_prefill": str(case_review_sheet_prefill.relative_to(output_dir)).replace("\\", "/"),
        },
        "scope_boundary": config.get("forbidden_scope", {}),
        "entries": entries,
    }
    changed_files = [
        "configs/scene_config.yaml",
        "manifests/v0_1_sample_manifest.csv",
        "src/io/config.py",
        "src/io/manifest.py",
        "src/io/source_registry.py",
        "src/visualization/candidate_overlay.py",
        "src/visualization/factor_breakdown.py",
        "src/visualization/temporal_strip.py",
        "src/visualization/transfer_panel.py",
        "tools/diagnostics/run_v0_visual_diagnosis_bootstrap.py",
        "docs/v0_1_input_source_registry.md",
        "reports/v0_1/input_source_registry.json",
        "reports/v0_1/input_source_alignment_report.md",
        "reports/v0_1/v0_1_case_review_sheet.csv",
    ]
    _write_markdown_report(output_dir / report_name, summary, changed_files)
    _write_markdown_report(Path(args.alignment_report), summary, changed_files)
    _write_json(output_dir / summary_name, summary)
    _write_index(output_dir, entries, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/scene_config.yaml")
    parser.add_argument("--manifest", default="manifests/v0_sample_manifest.csv")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--run-name", default="v0_visual_diagnosis")
    parser.add_argument("--registry-doc", default="docs/v0_1_input_source_registry.md")
    parser.add_argument("--registry-json", default="reports/v0_1/input_source_registry.json")
    parser.add_argument("--alignment-report", default="reports/v0_1/input_source_alignment_report.md")
    parser.add_argument("--review-sheet", default="reports/v0_1/v0_1_case_review_sheet.csv")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
