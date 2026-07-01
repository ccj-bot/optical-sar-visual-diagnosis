"""Run OTY1 optical tracklet construction audit.

OTY1 consumes only the OTY0 YOLO detection table and builds geometry-only
optical tracklet candidates. It does not use review queues, final GT, SAR GT,
manual/oracle labels, selector scores, G2, A008 scoring, SAR alignment, or SAR
band generation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import struct
import subprocess
import sys
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.optical_state.state_features import parse_float, parse_int  # noqa: E402
from src.optical_state.tracklet_builder import (  # noqa: E402
    TrackletAuditLimits,
    build_candidate_edges,
    build_quality_audit_rows,
    build_tracklet_components,
    compute_tracklet_state_timeseries,
    normalize_detections,
)


FORBIDDEN_RUNTIME_TOKENS = (
    "gt",
    "final",
    "manual",
    "oracle",
    "review",
    "sar",
    "iou",
    "target_identity",
    "group_id",
    "chosen_candidate",
    "a008",
    "g2",
    "selector",
)

EDGE_FIELDS = [
    "edge_id",
    "edge_kind",
    "from_det_id",
    "to_det_id",
    "scene",
    "from_optical_frame_num",
    "to_optical_frame_num",
    "optical_frame_gap",
    "from_class_name",
    "to_class_name",
    "class_consistent",
    "center_distance_px",
    "center_distance_limit_px",
    "bbox_iou",
    "size_consistency",
    "area_change_ratio",
    "aspect_change_ratio",
    "confidence_pair_min",
    "neighbor_ambiguity_from",
    "neighbor_ambiguity_to",
    "edge_audit_score_not_selector",
    "edge_within_audit_limits",
    "edge_status",
    "source_within_candidate_count",
    "target_within_candidate_count",
    "candidate_rank_for_source_detection",
    "edge_selected_for_component",
    "edge_policy",
]

COMPONENT_FIELDS = [
    "tracklet_candidate_id",
    "scene",
    "detection_count",
    "frame_start",
    "frame_end",
    "frame_span",
    "missing_frame_gap_count",
    "max_frame_gap",
    "mean_center_speed",
    "median_center_speed",
    "mean_area_change_abs",
    "edge_conflict_count",
    "same_frame_conflict_count",
    "neighbor_ambiguity_count",
    "boundary_contact_count",
    "selected_edge_count",
    "tracklet_status",
    "identity_status",
    "policy",
]

STATE_FIELDS = [
    "tracklet_candidate_id",
    "scene",
    "det_id",
    "optical_frame_num",
    "optical_path",
    "class_name",
    "confidence",
    "frame_width",
    "frame_height",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "bbox_center_x",
    "bbox_center_y",
    "bbox_width",
    "bbox_height",
    "bbox_area",
    "bbox_aspect",
    "frame_boundary_contact_status",
    "touch_left",
    "touch_right",
    "touch_top",
    "touch_bottom",
    "touch_any",
    "velocity_status",
    "velocity_x_px_per_frame",
    "velocity_y_px_per_frame",
    "center_speed_px_per_frame",
    "size_change_ratio",
    "track_jitter_proxy_status",
    "track_jitter_proxy_px",
    "neighbor_context_status",
    "neighbor_count",
    "min_neighbor_center_distance_px",
    "neighbor_ambiguity_proxy",
    "truncation_likelihood_proxy",
    "occlusion_proxy_status",
    "ambiguity_proxy_status",
    "state_status",
    "identity_status",
    "state_source_policy",
]

QUALITY_FIELDS = [
    "tracklet_candidate_id",
    "scene",
    "detection_count",
    "tracklet_status",
    "identity_status",
    "edge_conflict_count",
    "same_frame_conflict_count",
    "neighbor_ambiguity_count",
    "boundary_contact_count",
    "quality_notes",
    "policy",
]


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if not _is_duplicate_header_row(row)]


def _is_duplicate_header_row(row: Mapping[str, Any]) -> bool:
    hits = 0
    values = 0
    for key, value in row.items():
        text = str(value or "").strip()
        if not text:
            continue
        values += 1
        if text == key:
            hits += 1
    return values > 0 and hits >= max(2, values // 2)


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: str | Path) -> dict[str, Any]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def png_size(path: str | Path) -> tuple[int, int] | None:
    try:
        with Path(path).open("rb") as fh:
            header = fh.read(24)
    except OSError:
        return None
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None


def file_uri(path: str | Path) -> str:
    try:
        return Path(path).resolve().as_uri()
    except ValueError:
        return str(path)


def safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text.strip("_") or "item"


def markdown_list(items: Iterable[str]) -> str:
    values = list(items)
    return "\n".join(f"- {item}" for item in values) if values else "- none"


def _detection_table_scene(table: Path) -> str:
    summary = read_json(table.parent / "oty0_summary.json")
    summary_scene = str(summary.get("scene", "") or "").strip()
    if summary_scene:
        return summary_scene
    try:
        with table.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                return str(row.get("scene", "") or "").strip()
    except OSError:
        return ""
    return ""


def latest_oty0_detection_table(output_root: str | Path, scene: str) -> Path | None:
    root = Path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(root.glob("oty0_yolo_detection_stream_audit_*"), key=lambda path: path.name, reverse=True):
        table = output_dir / "oty0_yolo_detection_table.csv"
        if table.exists() and _detection_table_scene(table) == scene:
            return table
    return None


def ensure_oty0_detection_table(args: argparse.Namespace) -> Path:
    if args.oty0_detection_table:
        path = Path(args.oty0_detection_table)
        if path.exists():
            return path
        raise FileNotFoundError(f"Configured OTY0 detection table does not exist: {path}")

    latest = latest_oty0_detection_table(args.output_root, args.scene)
    if latest is not None:
        return latest

    if not args.run_oty0_if_missing:
        raise FileNotFoundError("No OTY0 detection table found under output root.")

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "diagnostics" / "run_oty0_yolo_detection_stream_audit.py"),
            "--scene",
            args.scene,
            "--output-root",
            args.output_root,
        ],
        cwd=str(REPO_ROOT),
        check=True,
    )
    latest = latest_oty0_detection_table(args.output_root, args.scene)
    if latest is None:
        raise FileNotFoundError("OTY0 was run, but no detection table was produced.")
    return latest


def forbidden_input_fields(fieldnames: Sequence[str]) -> list[str]:
    out: list[str] = []
    for name in fieldnames:
        lower = str(name).lower()
        if any(token in lower for token in FORBIDDEN_RUNTIME_TOKENS):
            if name not in {"bbox_iou"}:
                out.append(str(name))
    return out


def frame_sizes_from_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[int, int] | None]:
    out: dict[str, tuple[int, int] | None] = {}
    for row in rows:
        path = str(row.get("optical_path", "") or "").strip()
        if path and path not in out:
            out[path] = png_size(path)
    return out


def component_size_distribution(components: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in components:
        size = str(row.get("detection_count", ""))
        out[size] = out.get(size, 0) + 1
    return dict(sorted(out.items(), key=lambda item: int(item[0]) if item[0].isdigit() else 9999))


def status_count(rows: Sequence[Mapping[str, Any]], field: str, value: str) -> int:
    return sum(1 for row in rows if str(row.get(field, "")) == value)


def sum_int(rows: Sequence[Mapping[str, Any]], field: str) -> int:
    total = 0
    for row in rows:
        value = parse_int(row.get(field))
        if value is not None:
            total += value
    return total


def edge_status_distribution(edges: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for edge in edges:
        status = str(edge.get("edge_status", ""))
        out[status] = out.get(status, 0) + 1
    return dict(sorted(out.items()))


def color_for_identity(identity_status: str) -> str:
    if identity_status == "high_confidence_geometry_only":
        return "#0f766e"
    if identity_status == "geometry_consistent_but_unverified":
        return "#2563eb"
    if identity_status == "ambiguous_crossing_risk":
        return "#dc2626"
    if identity_status == "fragmented_short_track":
        return "#64748b"
    return "#7c3aed"


def render_tracklet_strip_svg(
    path: Path,
    component: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    max_frames: int,
) -> None:
    ordered = sorted(rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))))
    if len(ordered) > max_frames:
        step = max(1, len(ordered) // max_frames)
        sampled = ordered[::step][:max_frames]
    else:
        sampled = ordered

    cell_w = 260
    pad = 18
    title_h = 86
    image_w = 220.0
    widths = [parse_float(row.get("frame_width")) or 800.0 for row in sampled]
    heights = [parse_float(row.get("frame_height")) or 600.0 for row in sampled]
    display_heights = [image_w * h / max(w, 1.0) for w, h in zip(widths, heights)]
    max_display_h = max(display_heights) if display_heights else 180.0
    svg_w = max(900, pad * 2 + cell_w * max(1, len(sampled)))
    svg_h = int(title_h + max_display_h + 108)
    identity = str(component.get("identity_status", ""))
    color = color_for_identity(identity)
    warnings = []
    if identity == "ambiguous_crossing_risk":
        warnings.append("AMBIGUOUS")
    if identity == "fragmented_short_track":
        warnings.append("SHORT")
    if int(component.get("boundary_contact_count") or 0) > 0:
        warnings.append("EDGE_CONTACT")
    warning_text = " | ".join(warnings) if warnings else "GEOMETRY_ONLY"

    parts = [
        f'<rect x="0" y="0" width="{svg_w}" height="{svg_h}" fill="#ffffff" />',
        f'<text x="{pad}" y="30" font-size="20" fill="#111827">OTY1 {html_escape(str(component.get("tracklet_candidate_id", "")))}</text>',
        f'<text x="{pad}" y="55" font-size="13" fill="#475569">identity={html_escape(identity)} | status={html_escape(str(component.get("tracklet_status", "")))} | {html_escape(warning_text)}</text>',
        f'<text x="{pad}" y="75" font-size="12" fill="#64748b">Runtime OTY0 YOLO detections only; no SAR frame, SAR GT, final box, or fan/range band.</text>',
    ]
    for idx, row in enumerate(sampled):
        x0 = pad + idx * cell_w
        y0 = title_h
        frame_w = widths[idx]
        frame_h = heights[idx]
        display_h = display_heights[idx]
        scale_x = image_w / max(frame_w, 1.0)
        scale_y = display_h / max(frame_h, 1.0)
        bbox_x = (parse_float(row.get("bbox_x1")) or 0.0) * scale_x + x0
        bbox_y = (parse_float(row.get("bbox_y1")) or 0.0) * scale_y + y0
        bbox_w = (parse_float(row.get("bbox_width")) or 0.0) * scale_x
        bbox_h = (parse_float(row.get("bbox_height")) or 0.0) * scale_y
        label = (
            f"{row.get('det_id', '')} | f={row.get('optical_frame_num', '')} "
            f"| conf={float(row.get('confidence') or 0.0):.2f}"
        )
        tag_color = "#f97316" if str(row.get("touch_any", "")).lower() == "true" else color
        parts.append(
            f'<image href="{html_escape(file_uri(str(row.get("optical_path", ""))))}" x="{x0}" y="{y0}" width="{image_w:.2f}" height="{display_h:.2f}" preserveAspectRatio="xMidYMid meet" />'
        )
        parts.append(
            f'<rect x="{bbox_x:.2f}" y="{bbox_y:.2f}" width="{bbox_w:.2f}" height="{bbox_h:.2f}" fill="none" stroke="{tag_color}" stroke-width="3" />'
        )
        parts.append(f'<text x="{x0}" y="{y0 + display_h + 20:.2f}" font-size="11" fill="#111827">{html_escape(label)}</text>')
        parts.append(
            f'<text x="{x0}" y="{y0 + display_h + 38:.2f}" font-size="11" fill="{tag_color}">{html_escape(str(row.get("state_status", "")))}</text>'
        )
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def render_timeline_svg(
    path: Path,
    components: Sequence[Mapping[str, Any]],
    timeseries: Sequence[Mapping[str, Any]],
    scene: str,
    max_components: int,
) -> None:
    top_components = sorted(
        components,
        key=lambda row: (-(parse_int(row.get("detection_count")) or 0), parse_int(row.get("frame_start")) or 0),
    )[:max_components]
    if not top_components:
        top_components = []
    rows_by_tracklet: dict[str, list[Mapping[str, Any]]] = {}
    for row in timeseries:
        rows_by_tracklet.setdefault(str(row.get("tracklet_candidate_id", "")), []).append(row)
    min_frame = min((parse_int(row.get("optical_frame_num")) or 0 for row in timeseries), default=0)
    max_frame = max((parse_int(row.get("optical_frame_num")) or 0 for row in timeseries), default=1)
    span = max(1, max_frame - min_frame)
    width = 1250
    left = 210
    right = 40
    top = 82
    row_h = 24
    height = max(180, top + row_h * max(1, len(top_components)) + 70)
    plot_w = width - left - right

    parts = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
        f'<text x="24" y="34" font-size="22" fill="#111827">OTY1 optical tracklet timeline: {html_escape(scene)}</text>',
        '<text x="24" y="58" font-size="13" fill="#64748b">Optical YOLO detections only. Component identity is candidate-only geometry, not confirmed truth.</text>',
        f'<line x1="{left}" y1="{top - 18}" x2="{left + plot_w}" y2="{top - 18}" stroke="#cbd5e1" />',
        f'<text x="{left}" y="{top - 26}" font-size="12" fill="#475569">frame {min_frame}</text>',
        f'<text x="{left + plot_w - 70}" y="{top - 26}" font-size="12" fill="#475569">frame {max_frame}</text>',
    ]
    for idx, component in enumerate(top_components):
        y = top + idx * row_h
        tracklet_id = str(component.get("tracklet_candidate_id", ""))
        identity = str(component.get("identity_status", ""))
        color = color_for_identity(identity)
        component_rows = sorted(rows_by_tracklet.get(tracklet_id, []), key=lambda row: parse_int(row.get("optical_frame_num")) or 0)
        parts.append(f'<text x="24" y="{y + 4}" font-size="11" fill="#111827">{html_escape(tracklet_id)}</text>')
        parts.append(f'<text x="132" y="{y + 4}" font-size="10" fill="{color}">{html_escape(identity)}</text>')
        if component_rows:
            xs = [
                left + ((parse_int(row.get("optical_frame_num")) or min_frame) - min_frame) / span * plot_w
                for row in component_rows
            ]
            parts.append(f'<line x1="{min(xs):.2f}" y1="{y}" x2="{max(xs):.2f}" y2="{y}" stroke="{color}" stroke-width="2" opacity="0.8" />')
            for row, x in zip(component_rows, xs):
                radius = 4 if str(row.get("state_status", "")).startswith("runtime") else 5
                fill = "#f97316" if str(row.get("touch_any", "")).lower() == "true" else color
                parts.append(f'<circle cx="{x:.2f}" cy="{y}" r="{radius}" fill="{fill}" opacity="0.9" />')
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def render_contact_sheet(
    path: Path,
    overlay_paths: Sequence[Path],
    summary: Mapping[str, Any],
) -> None:
    links = "\n".join(
        f'<a class="card" href="oty1_tracklet_overlay_samples/{html_escape(item.name)}" target="_blank">{html_escape(item.stem)}</a>'
        for item in overlay_paths
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>OTY1 Optical Tracklet Contact Sheet</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #111827; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }}
    .card {{ display: block; padding: 12px; border: 1px solid #cbd5e1; text-decoration: none; color: #0f172a; background: #f8fafc; }}
    code {{ background: #f1f5f9; padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>OTY1 Optical Tracklet Contact Sheet</h1>
  <p>Scene <code>{html_escape(str(summary.get("scene", "")))}</code>, tracklet candidates <code>{html_escape(str(summary.get("tracklet_candidate_count", "")))}</code>. Runtime source is the OTY0 YOLO detection table only.</p>
  <p><a href="oty1_tracklet_timeline.svg">Tracklet timeline</a></p>
  <div class="grid">{links}</div>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def write_boundary_doc(path: Path, detection_table: Path) -> None:
    path.write_text(
        f"""# OTY1 Runtime/Posthoc Boundary

## Runtime Source

OTY1 runtime construction reads only:

- OTY0 YOLO detection table: `{detection_table}`
- OTY0 detector fields: scene, optical frame number/path, det_id, class id/name, confidence, bbox geometry
- Optical image dimensions derived from raw optical frame files for boundary-contact proxies

## Posthoc-Only Sources

`review_queue.csv`, `final_gt_working.csv`, SAR GT, final/manual/oracle/review fields, posthoc IoU, target identity, group ids, and SAR evidence are not used to build OTY1 edges, components, or state streams.

## Forbidden In OTY1

- selector, G2, A008 scoring, threshold tuning, or training
- SAR alignment or optical/SAR same-frame assumptions
- SAR fan/range band generation
- SAR GT coverage evaluation
- automatic annotation proposal

OTY1 outputs geometry-only optical tracklet candidates. They are not confirmed same-target identity truth.
""",
        encoding="utf-8",
    )


def write_report(path: Path, summary: Mapping[str, Any], blockers: Sequence[str]) -> None:
    lines = [
        "# OTY1 Optical Tracklet Construction Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Scene: `{summary['scene']}`",
        "",
        "## Input",
        "",
        f"- OTY0 detection table: `{summary['input_oty0_detection_table']}`",
        "- runtime source: OTY0 YOLO detections only",
        "- no review/final/SAR GT source used for runtime construction",
        "",
        "## Results",
        "",
        f"- total detections: `{summary['total_detections']}`",
        f"- total optical frames: `{summary['total_optical_frames']}`",
        f"- frames with detections: `{summary['frames_with_detections']}`",
        f"- candidate edge rows: `{summary['candidate_edge_rows']}`",
        f"- within-limit edge rows: `{summary['within_limit_edge_rows']}`",
        f"- tracklet candidate count: `{summary['tracklet_candidate_count']}`",
        f"- high-confidence geometry-only candidates: `{summary['high_confidence_geometry_only_candidate_count']}`",
        f"- ambiguous tracklets: `{summary['ambiguous_tracklet_count']}`",
        f"- fragmented short tracks: `{summary['fragmented_short_track_count']}`",
        f"- same-frame conflict count: `{summary['same_frame_conflict_count']}`",
        f"- neighbor ambiguity count: `{summary['neighbor_ambiguity_count']}`",
        f"- boundary contact count: `{summary['boundary_contact_count']}`",
        "",
        "## Component Size Distribution",
        "",
        json.dumps(summary["component_size_distribution"], ensure_ascii=False),
        "",
        "## Boundary Check",
        "",
        "- no SAR alignment",
        "- no SAR band",
        "- no SAR GT coverage",
        "- no GT/final/manual/oracle/review fields used for runtime construction",
        "- tracklet identity remains candidate-only unless a future runtime-safe track-id source is proven",
        "",
        "## Blockers",
        "",
        markdown_list(blockers),
        "",
        "## OTY2 Next Step",
        "",
        "Audit optical-to-SAR high-FPS temporal alignment from the optical tracklet state stream without assuming optical frame number equals SAR frame number.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_chinese_summary(path: Path, summary: Mapping[str, Any], blockers: Sequence[str]) -> None:
    lines = [
        f"# OTY1 {summary['scene']} Optical Tracklet 审计总结",
        "",
        f"生成时间：{summary['generated_at']}",
        f"审计场景：{summary['scene']}",
        f"本地输出目录：`{summary['output_dir']}`",
        "",
        "## 1. 本轮定位",
        "",
        "OTY1 只从 OTY0 的 YOLO detection table 构造 optical tracklet candidate 和 optical state stream。它不是自动标注完成态，也不是 SAR band、SAR GT coverage 或 selector/ranker。",
        "",
        "## 2. 输入边界",
        "",
        f"- Runtime 输入：`{summary['input_oty0_detection_table']}`",
        "- 禁止用于 runtime：`review_queue.csv`、`final_gt_working.csv`、SAR GT、final/manual/oracle/review 字段。",
        "- 没有假设 optical frame number 等于 SAR frame number。",
        "",
        "## 3. 关键统计",
        "",
        "| 项目 | 数值 |",
        "| --- | ---: |",
        f"| total detections | {summary['total_detections']} |",
        f"| total optical frames | {summary['total_optical_frames']} |",
        f"| frames with detections | {summary['frames_with_detections']} |",
        f"| candidate edge rows | {summary['candidate_edge_rows']} |",
        f"| within-limit edge rows | {summary['within_limit_edge_rows']} |",
        f"| tracklet candidate count | {summary['tracklet_candidate_count']} |",
        f"| high-confidence geometry-only candidate count | {summary['high_confidence_geometry_only_candidate_count']} |",
        f"| ambiguous tracklet count | {summary['ambiguous_tracklet_count']} |",
        f"| fragmented short track count | {summary['fragmented_short_track_count']} |",
        f"| same-frame conflict count | {summary['same_frame_conflict_count']} |",
        f"| neighbor ambiguity count | {summary['neighbor_ambiguity_count']} |",
        f"| boundary contact count | {summary['boundary_contact_count']} |",
        "",
        f"Component size distribution：`{json.dumps(summary['component_size_distribution'], ensure_ascii=False)}`",
        "",
        "## 4. 主要产物",
        "",
        f"- `oty1_tracklet_candidate_edges.csv`：候选 edge，edge 是 audit candidate，不是 same-target proof。",
        f"- `oty1_optical_tracklet_components.csv`：geometry-only component 汇总。",
        f"- `oty1_optical_tracklet_state_timeseries.csv`：带 tracklet candidate id 的 optical state stream。",
        f"- `oty1_tracklet_quality_audit.csv`：短轨迹、歧义、边界接触和冲突标记。",
        f"- `oty1_runtime_posthoc_boundary.md`：runtime/posthoc 边界。",
        f"- `oty1_summary.json` / `oty1_report.md`：机器可读和人读报告。",
        "",
        "## 5. 可视化",
        "",
        f"可视化目录：`{summary['visualizations_dir']}`",
        "",
        "- `oty1_tracklet_contact_sheet.html`：候选 tracklet strip 入口。",
        "- `oty1_tracklet_timeline.svg`：候选 tracklet 时间线。",
        "- `oty1_tracklet_overlay_samples/`：若干 tracklet candidate 的 optical frame sequence SVG。",
        "",
        "可视化只显示 optical frame、YOLO bbox、det_id、frame_num、confidence 和 tracklet_candidate_id；不显示 SAR frame、SAR GT、final box 或 fan/range band。",
        "",
        "## 6. Blocker 和下一步",
        "",
        markdown_list(blockers),
        "",
        "下一步 OTY2 应审计 optical-to-SAR high-FPS temporal alignment：从 OTY1 的 optical state stream 出发，建立 optical 时间轴到 SAR 高帧率时间轴的对齐关系；仍然不能假设同帧号对应，也不能在 OTY2 之前生成 SAR fan/range band。",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_limits(args: argparse.Namespace) -> TrackletAuditLimits:
    return TrackletAuditLimits(
        max_frame_gap=args.max_frame_gap,
        scan_frame_gap=max(args.scan_frame_gap, args.max_frame_gap),
        max_center_distance_px=args.max_center_distance_px,
        min_size_consistency=args.min_size_consistency,
        max_edges_per_detection=args.max_edges_per_detection,
        neighbor_distance_px=args.neighbor_distance_px,
        contact_margin_px=args.contact_margin_px,
        min_tracklet_length=args.min_tracklet_length,
        high_confidence_min_detections=args.high_confidence_min_detections,
        high_confidence_max_frame_gap=args.high_confidence_max_frame_gap,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_root) / f"oty1_optical_tracklet_audit_{timestamp}"
    viz_dir = output_dir / "visualizations"
    overlay_dir = viz_dir / "oty1_tracklet_overlay_samples"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    detection_table = ensure_oty0_detection_table(args)
    raw_rows = read_csv_rows(detection_table)
    input_fields = list(raw_rows[0].keys()) if raw_rows else []
    forbidden_fields = forbidden_input_fields(input_fields)
    frame_sizes = frame_sizes_from_rows(raw_rows)
    detections = normalize_detections(raw_rows, frame_sizes=frame_sizes, scene=args.scene)
    limits = make_limits(args)

    blockers: list[str] = []
    if forbidden_fields:
        blockers.append(
            "OTY0 detection table has forbidden runtime-looking fields and was not used: "
            + ", ".join(forbidden_fields)
        )
        detections = []
    if not raw_rows:
        blockers.append("OTY0 detection table is empty.")
    if raw_rows and not detections:
        blockers.append("No usable runtime-safe OTY0 YOLO detections were parsed for the scene.")

    edges = build_candidate_edges(detections, limits) if detections else []
    within_edges = [edge for edge in edges if edge.get("edge_within_audit_limits") is True]
    components, assignments = build_tracklet_components(detections, edges, limits) if detections else ([], {})
    timeseries = compute_tracklet_state_timeseries(detections, components, assignments, limits) if detections else []
    quality_rows = build_quality_audit_rows(components)

    oty0_summary = read_json(detection_table.parent / "oty0_summary.json")
    total_optical_frames = oty0_summary.get("optical_frame_count")
    if total_optical_frames in ("", None):
        total_optical_frames = len({row.get("optical_frame_num") for row in raw_rows})
    frames_with_detections = len({det["optical_frame_num"] for det in detections})
    component_ids = {row["tracklet_candidate_id"] for row in components}

    if detections and not within_edges:
        blockers.append("Detections exist, but no candidate edge stayed within OTY1 geometry audit limits.")
    if detections and not components:
        blockers.append("No optical tracklet candidate components were constructed.")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "oty1_tracklet_candidate_edges.csv", edges, EDGE_FIELDS)
    write_csv(output_dir / "oty1_optical_tracklet_components.csv", components, COMPONENT_FIELDS)
    write_csv(output_dir / "oty1_optical_tracklet_state_timeseries.csv", timeseries, STATE_FIELDS)
    write_csv(output_dir / "oty1_tracklet_quality_audit.csv", quality_rows, QUALITY_FIELDS)
    write_boundary_doc(output_dir / "oty1_runtime_posthoc_boundary.md", detection_table)

    top_components = sorted(
        components,
        key=lambda row: (-(parse_int(row.get("detection_count")) or 0), parse_int(row.get("frame_start")) or 0),
    )[: args.max_visual_tracklets]
    rows_by_tracklet: dict[str, list[Mapping[str, Any]]] = {}
    for row in timeseries:
        rows_by_tracklet.setdefault(str(row.get("tracklet_candidate_id", "")), []).append(row)
    overlay_paths: list[Path] = []
    for component in top_components:
        tracklet_id = str(component.get("tracklet_candidate_id", ""))
        rows = rows_by_tracklet.get(tracklet_id, [])
        if not rows:
            continue
        overlay_path = overlay_dir / f"{safe_name(tracklet_id)}_strip.svg"
        render_tracklet_strip_svg(overlay_path, component, rows, args.max_visual_frames_per_tracklet)
        overlay_paths.append(overlay_path)
    render_timeline_svg(viz_dir / "oty1_tracklet_timeline.svg", components, timeseries, args.scene, args.max_timeline_components)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scene": args.scene,
        "input_oty0_detection_table": str(detection_table),
        "output_dir": str(output_dir),
        "visualizations_dir": str(viz_dir),
        "total_detections": len(detections),
        "total_optical_frames": int(total_optical_frames),
        "frames_with_detections": frames_with_detections,
        "candidate_edge_rows": len(edges),
        "within_limit_edge_rows": len(within_edges),
        "edge_status_distribution": edge_status_distribution(edges),
        "tracklet_candidate_count": len(component_ids),
        "component_size_distribution": component_size_distribution(components),
        "high_confidence_geometry_only_candidate_count": status_count(
            components, "identity_status", "high_confidence_geometry_only"
        ),
        "ambiguous_tracklet_count": status_count(components, "identity_status", "ambiguous_crossing_risk"),
        "fragmented_short_track_count": status_count(components, "identity_status", "fragmented_short_track"),
        "same_frame_conflict_count": sum_int(components, "same_frame_conflict_count"),
        "neighbor_ambiguity_count": sum_int(components, "neighbor_ambiguity_count"),
        "boundary_contact_count": sum_int(components, "boundary_contact_count"),
        "posthoc_sources_used_for_runtime_tracklets": False,
        "sar_alignment_entered": False,
        "sar_band_entered": False,
        "sar_gt_coverage_entered": False,
        "selector_g2_a008_threshold_training_entered": False,
        "annotation_proposal_entered": False,
        "identity_truth_claimed": False,
        "alignment_assumption": "no_optical_sar_same_frame_assumption_in_oty1",
        "largest_blocker": blockers[0] if blockers else "No hard OTY1 blocker; tracklet candidates remain geometry-only and unconfirmed.",
        "oty2_recommendation": "GO for optical-to-SAR high-FPS temporal alignment audit using OTY1 state stream; do not generate SAR band before alignment is audited.",
        "audit_limits": {
            "max_frame_gap": limits.max_frame_gap,
            "scan_frame_gap": limits.scan_frame_gap,
            "max_center_distance_px": limits.max_center_distance_px,
            "min_size_consistency": limits.min_size_consistency,
            "max_edges_per_detection": limits.max_edges_per_detection,
            "neighbor_distance_px": limits.neighbor_distance_px,
            "contact_margin_px": limits.contact_margin_px,
            "min_tracklet_length": limits.min_tracklet_length,
            "high_confidence_min_detections": limits.high_confidence_min_detections,
            "high_confidence_max_frame_gap": limits.high_confidence_max_frame_gap,
        },
        "artifacts": {
            "edges": str(output_dir / "oty1_tracklet_candidate_edges.csv"),
            "components": str(output_dir / "oty1_optical_tracklet_components.csv"),
            "state_timeseries": str(output_dir / "oty1_optical_tracklet_state_timeseries.csv"),
            "quality_audit": str(output_dir / "oty1_tracklet_quality_audit.csv"),
            "boundary": str(output_dir / "oty1_runtime_posthoc_boundary.md"),
            "summary": str(output_dir / "oty1_summary.json"),
            "report": str(output_dir / "oty1_report.md"),
            "contact_sheet": str(viz_dir / "oty1_tracklet_contact_sheet.html"),
            "timeline": str(viz_dir / "oty1_tracklet_timeline.svg"),
            "overlay_samples": str(overlay_dir),
        },
    }
    write_json(output_dir / "oty1_summary.json", summary)
    render_contact_sheet(viz_dir / "oty1_tracklet_contact_sheet.html", overlay_paths, summary)
    write_report(output_dir / "oty1_report.md", summary, blockers)
    scene_slug = safe_name(str(args.scene).lower())
    report_path = Path("reports") / "oty1" / f"oty1_{scene_slug}_optical_tracklet_summary_{timestamp}.md"
    write_chinese_summary(report_path, summary, blockers)

    workspace_log_dir = Path("D:/profile/research/workspace/logs")
    if workspace_log_dir.exists():
        log_path = workspace_log_dir / f"oty1_optical_tracklet_audit_{timestamp}.md"
        log_path.write_text(
            "# OTY1 Optical Tracklet Audit Log\n\n"
            f"- repo: `{REPO_ROOT}`\n"
            f"- output: `{output_dir}`\n"
            f"- input_oty0_detection_table: `{detection_table}`\n"
            f"- interpreter: `{sys.executable}`\n"
            "- boundary: OTY0 YOLO detections only; no SAR alignment, SAR band, GT/final/review runtime use\n",
            encoding="utf-8",
        )
        summary["workspace_log"] = str(log_path)
        write_json(output_dir / "oty1_summary.json", summary)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--oty0-detection-table", default="")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--run-oty0-if-missing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-frame-gap", type=int, default=4)
    parser.add_argument("--scan-frame-gap", type=int, default=8)
    parser.add_argument("--max-center-distance-px", type=float, default=260.0)
    parser.add_argument("--min-size-consistency", type=float, default=0.35)
    parser.add_argument("--max-edges-per-detection", type=int, default=5)
    parser.add_argument("--neighbor-distance-px", type=float, default=120.0)
    parser.add_argument("--contact-margin-px", type=float, default=2.0)
    parser.add_argument("--min-tracklet-length", type=int, default=3)
    parser.add_argument("--high-confidence-min-detections", type=int, default=8)
    parser.add_argument("--high-confidence-max-frame-gap", type=int, default=2)
    parser.add_argument("--max-visual-tracklets", type=int, default=12)
    parser.add_argument("--max-visual-frames-per-tracklet", type=int, default=8)
    parser.add_argument("--max-timeline-components", type=int, default=60)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
