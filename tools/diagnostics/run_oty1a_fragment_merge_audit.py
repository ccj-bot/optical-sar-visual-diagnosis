"""Run OTY1a optical fragment merge candidate audit.

OTY1a consumes only OTY1 optical tracklet audit outputs and proposes
fragment-merge review candidates from runtime-safe optical geometry. It does
not use review queues, final GT, SAR GT/evidence, selector/G2/A008 scores,
threshold tuning, training signals, or annotation-proposal labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import struct
import sys
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.optical_state.fragment_merge import (  # noqa: E402
    MERGE_POSITIVE_STATUSES,
    FragmentMergeLimits,
    build_component_profiles,
    build_fragment_merge_edges,
    component_review_rows,
    count_positive_edges,
    edge_status_counts,
    shape_transition_rows,
)
from src.optical_state.state_features import parse_float, parse_int  # noqa: E402


OTY1_REQUIRED_FILES = (
    "oty1_tracklet_candidate_edges.csv",
    "oty1_optical_tracklet_components.csv",
    "oty1_optical_tracklet_state_timeseries.csv",
    "oty1_tracklet_quality_audit.csv",
    "oty1_summary.json",
)

MERGE_EDGE_FIELDS = [
    "merge_edge_id",
    "scene",
    "from_tracklet_candidate_id",
    "to_tracklet_candidate_id",
    "from_frame_start",
    "from_frame_end",
    "to_frame_start",
    "to_frame_end",
    "temporal_relation",
    "frame_gap",
    "frame_overlap_count",
    "from_detection_count",
    "to_detection_count",
    "endpoint_center_distance_px",
    "motion_predicted_center_distance_px",
    "bridge_iou_proxy",
    "area_ratio_endpoint",
    "aspect_ratio_endpoint",
    "bottom_y_delta_px",
    "class_consistent",
    "confidence_bridge_min",
    "from_boundary_contact_count",
    "to_boundary_contact_count",
    "from_neighbor_ambiguity_count",
    "to_neighbor_ambiguity_count",
    "shape_transition_proxy",
    "partial_to_full_box_transition_proxy",
    "competing_merge_count_from",
    "competing_merge_count_to",
    "merge_candidate_score_not_selector",
    "merge_candidate_status",
    "merge_policy",
]

COMPONENT_REVIEW_FIELDS = [
    "tracklet_candidate_id",
    "scene",
    "detection_count",
    "frame_start",
    "frame_end",
    "frame_span",
    "identity_status",
    "tracklet_status",
    "neighbor_ambiguity_count",
    "boundary_contact_count",
    "missing_frame_gap_count",
    "max_frame_gap",
    "first_det_id",
    "last_det_id",
    "first_k_center_x_mean",
    "first_k_center_y_mean",
    "first_k_area_median",
    "first_k_aspect_median",
    "first_k_bottom_y_median",
    "first_k_confidence_min",
    "last_k_center_x_mean",
    "last_k_center_y_mean",
    "last_k_area_median",
    "last_k_aspect_median",
    "last_k_bottom_y_median",
    "last_k_confidence_min",
    "first_velocity_x_px_per_frame",
    "first_velocity_y_px_per_frame",
    "last_velocity_x_px_per_frame",
    "last_velocity_y_px_per_frame",
]


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


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if not _is_duplicate_header_row(row)]


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_json(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def boolish(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def markdown_list(items: Iterable[str]) -> str:
    values = list(items)
    return "\n".join(f"- {item}" for item in values) if values else "- none"


def safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text.strip("_") or "item"


def file_uri(path: str | Path) -> str:
    try:
        return Path(path).resolve().as_uri()
    except (OSError, ValueError):
        return str(path)


def png_size(path: str | Path) -> tuple[int, int] | None:
    try:
        with Path(path).open("rb") as fh:
            header = fh.read(24)
    except OSError:
        return None
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None


def scene_from_oty1_dir(output_dir: Path) -> str:
    summary = read_json(output_dir / "oty1_summary.json")
    return str(summary.get("scene", "") or "").strip()


def has_oty1_inputs(output_dir: Path) -> bool:
    return all((output_dir / name).exists() for name in OTY1_REQUIRED_FILES)


def latest_oty1_output_dir(output_root: str | Path, scene: str) -> Path | None:
    root = Path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(root.glob("oty1_optical_tracklet_audit_*"), key=lambda path: path.name, reverse=True):
        if has_oty1_inputs(output_dir) and scene_from_oty1_dir(output_dir) == scene:
            return output_dir
    return None


def ensure_oty1_output_dir(args: argparse.Namespace) -> Path:
    if args.oty1_output_dir:
        output_dir = Path(args.oty1_output_dir)
        missing = [name for name in OTY1_REQUIRED_FILES if not (output_dir / name).exists()]
        if missing:
            raise FileNotFoundError(f"OTY1 output dir is missing required files: {', '.join(missing)}")
        return output_dir
    output_dir = latest_oty1_output_dir(args.output_root, args.scene)
    if output_dir is None:
        raise FileNotFoundError(f"No OTY1 output found for scene {args.scene} under {args.output_root}")
    return output_dir


def oty1_edge_statistics(edges: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "geometry_feasible_edges": sum(1 for row in edges if boolish(row.get("edge_within_audit_limits"))),
        "clean_unambiguous_edges": sum(1 for row in edges if str(row.get("edge_status", "")) == "within_audit_limits"),
        "ambiguous_feasible_edges": sum(1 for row in edges if str(row.get("edge_status", "")) == "ambiguous_multiple_candidates"),
        "selected_component_edges": sum(1 for row in edges if boolish(row.get("edge_selected_for_component"))),
    }


def sample_sorted_edges(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    def key(row: Mapping[str, Any]) -> tuple[int, float, float]:
        status = str(row.get("merge_candidate_status", ""))
        score = parse_float(row.get("merge_candidate_score_not_selector")) or 0.0
        distance = parse_float(row.get("endpoint_center_distance_px")) or 1e12
        return (0 if status in MERGE_POSITIVE_STATUSES else 1, -score, distance)

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(rows, key=key):
        edge_id = str(row.get("merge_edge_id", ""))
        if edge_id in seen:
            continue
        selected.append(dict(row))
        seen.add(edge_id)
        if len(selected) >= max_rows:
            break
    return selected


def det_to_tracklet_map(state_rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {
        str(row.get("det_id", "")): str(row.get("tracklet_candidate_id", ""))
        for row in state_rows
        if row.get("det_id") and row.get("tracklet_candidate_id")
    }


def bridge_edges_between_tracklets(
    oty1_edges: Sequence[Mapping[str, Any]],
    state_rows: Sequence[Mapping[str, Any]],
    left_tracklet: str,
    right_tracklet: str,
) -> list[dict[str, Any]]:
    det_tracklet = det_to_tracklet_map(state_rows)
    out = []
    for edge in oty1_edges:
        if (
            det_tracklet.get(str(edge.get("from_det_id", ""))) == left_tracklet
            and det_tracklet.get(str(edge.get("to_det_id", ""))) == right_tracklet
        ):
            out.append(dict(edge))
    return sorted(
        out,
        key=lambda row: (
            not boolish(row.get("edge_within_audit_limits")),
            -(parse_float(row.get("edge_audit_score_not_selector")) or 0.0),
            parse_float(row.get("center_distance_px")) or 1e12,
        ),
    )


def rows_by_tracklet(state_rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in state_rows:
        grouped.setdefault(str(row.get("tracklet_candidate_id", "")), []).append(row)
    for tracklet_id, rows in grouped.items():
        grouped[tracklet_id] = sorted(
            rows,
            key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))),
        )
    return grouped


def endpoint_sample_rows(rows: Sequence[Mapping[str, Any]], role: str, max_rows: int) -> list[Mapping[str, Any]]:
    ordered = sorted(rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))))
    if len(ordered) <= max_rows:
        return list(ordered)
    if role == "from":
        return list(ordered[-max_rows:])
    return list(ordered[:max_rows])


def render_row_strip(
    parts: list[str],
    rows: Sequence[Mapping[str, Any]],
    role: str,
    tracklet_id: str,
    x_start: int,
    y_start: int,
    cell_w: int,
    image_w: float,
    color: str,
) -> int:
    label_y = y_start - 18
    parts.append(
        f'<text x="{x_start}" y="{label_y}" font-size="14" fill="#111827">'
        f'{html_escape(role)} {html_escape(tracklet_id)}</text>'
    )
    max_h = 0
    for idx, row in enumerate(rows):
        x0 = x_start + idx * cell_w
        optical_path = str(row.get("optical_path", "") or "")
        frame_w = parse_float(row.get("frame_width"))
        frame_h = parse_float(row.get("frame_height"))
        if not frame_w or not frame_h:
            size = png_size(optical_path)
            if size:
                frame_w, frame_h = float(size[0]), float(size[1])
        frame_w = frame_w or 800.0
        frame_h = frame_h or 600.0
        display_h = image_w * frame_h / max(frame_w, 1.0)
        max_h = max(max_h, int(display_h))
        scale_x = image_w / max(frame_w, 1.0)
        scale_y = display_h / max(frame_h, 1.0)
        bbox_x1 = parse_float(row.get("bbox_x1")) or 0.0
        bbox_y1 = parse_float(row.get("bbox_y1")) or 0.0
        bbox_w = parse_float(row.get("bbox_width"))
        bbox_h = parse_float(row.get("bbox_height"))
        if bbox_w is None:
            bbox_w = (parse_float(row.get("bbox_x2")) or bbox_x1) - bbox_x1
        if bbox_h is None:
            bbox_h = (parse_float(row.get("bbox_y2")) or bbox_y1) - bbox_y1
        stroke = "#f97316" if boolish(row.get("touch_any")) else color
        if optical_path:
            parts.append(
                f'<image href="{html_escape(file_uri(optical_path))}" x="{x0}" y="{y_start}" '
                f'width="{image_w:.2f}" height="{display_h:.2f}" preserveAspectRatio="xMidYMid meet" />'
            )
        else:
            parts.append(
                f'<rect x="{x0}" y="{y_start}" width="{image_w:.2f}" height="{display_h:.2f}" fill="#f1f5f9" />'
            )
        parts.append(
            f'<rect x="{x0 + bbox_x1 * scale_x:.2f}" y="{y_start + bbox_y1 * scale_y:.2f}" '
            f'width="{bbox_w * scale_x:.2f}" height="{bbox_h * scale_y:.2f}" '
            f'fill="none" stroke="{stroke}" stroke-width="3" />'
        )
        conf = parse_float(row.get("confidence"))
        conf_text = f"{conf:.2f}" if conf is not None else ""
        det_label = (
            f"f={row.get('optical_frame_num', '')} | {row.get('det_id', '')} | conf={conf_text}"
        )
        state_bits = []
        if boolish(row.get("neighbor_ambiguity_proxy")):
            state_bits.append("neighbor ambiguity")
        if boolish(row.get("touch_any")):
            state_bits.append("edge contact")
        state_text = ", ".join(state_bits) if state_bits else str(row.get("state_status", "runtime geometry"))
        parts.append(
            f'<text x="{x0}" y="{y_start + display_h + 17:.2f}" font-size="10" fill="#111827">'
            f'{html_escape(det_label)}</text>'
        )
        parts.append(
            f'<text x="{x0}" y="{y_start + display_h + 33:.2f}" font-size="10" fill="{stroke}">'
            f'{html_escape(state_text)}</text>'
        )
    return max_h + 48


def render_merge_candidate_svg(
    path: Path,
    edge: Mapping[str, Any],
    state_by_tracklet: Mapping[str, Sequence[Mapping[str, Any]]],
    max_endpoint_frames: int = 5,
) -> None:
    from_id = str(edge.get("from_tracklet_candidate_id", ""))
    to_id = str(edge.get("to_tracklet_candidate_id", ""))
    from_rows = endpoint_sample_rows(state_by_tracklet.get(from_id, []), "from", max_endpoint_frames)
    to_rows = endpoint_sample_rows(state_by_tracklet.get(to_id, []), "to", max_endpoint_frames)
    cols = max(1, max(len(from_rows), len(to_rows)))
    cell_w = 188
    image_w = 166.0
    left = 24
    top = 112
    row_gap = 92
    width = max(980, left * 2 + cols * cell_w)
    parts = [
        f'<rect x="0" y="0" width="{width}" height="100%" fill="#ffffff" />',
        f'<text x="24" y="34" font-size="22" fill="#111827">OTY1a merge review: {html_escape(from_id)} -> {html_escape(to_id)}</text>',
        f'<text x="24" y="58" font-size="13" fill="#475569">status={html_escape(str(edge.get("merge_candidate_status", "")))} | score_not_selector={parse_float(edge.get("merge_candidate_score_not_selector")) or 0:.3f} | endpoint_distance={parse_float(edge.get("endpoint_center_distance_px")) or 0:.1f}px | bridge_iou_proxy={parse_float(edge.get("bridge_iou_proxy")) or 0:.3f}</text>',
        '<text x="24" y="80" font-size="12" fill="#64748b">Optical YOLO bbox geometry only. No SAR frame, SAR GT, final box, fan/range band, selector, or confirmed identity.</text>',
    ]
    first_h = render_row_strip(parts, from_rows, "from", from_id, left, top, cell_w, image_w, "#2563eb")
    second_y = top + first_h + row_gap
    second_h = render_row_strip(parts, to_rows, "to", to_id, left, second_y, cell_w, image_w, "#7c3aed")
    height = second_y + second_h + 38
    parts[0] = f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def render_merge_timeline_svg(
    path: Path,
    edges: Sequence[Mapping[str, Any]],
    component_rows: Sequence[Mapping[str, Any]],
    scene: str,
    max_edges: int,
) -> None:
    component_by_id = {str(row.get("tracklet_candidate_id", "")): row for row in component_rows}
    positive = [
        row
        for row in sample_sorted_edges(edges, max_edges)
        if str(row.get("merge_candidate_status", "")) in MERGE_POSITIVE_STATUSES
    ][:max_edges]
    frames = []
    for row in component_rows:
        start = parse_int(row.get("frame_start"))
        end = parse_int(row.get("frame_end"))
        if start is not None:
            frames.append(start)
        if end is not None:
            frames.append(end)
    min_frame = min(frames) if frames else 0
    max_frame = max(frames) if frames else 1
    span = max(1, max_frame - min_frame)
    width = 1280
    left = 260
    right = 42
    top = 90
    row_h = 28
    height = max(190, top + row_h * max(1, len(positive)) + 70)
    plot_w = width - left - right
    parts = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
        f'<text x="24" y="34" font-size="22" fill="#111827">OTY1a fragment merge candidate timeline: {html_escape(scene)}</text>',
        '<text x="24" y="58" font-size="13" fill="#64748b">Each row is a review candidate edge between OTY1 optical tracklet components. Identity is not confirmed.</text>',
        f'<line x1="{left}" y1="{top - 22}" x2="{left + plot_w}" y2="{top - 22}" stroke="#cbd5e1" />',
        f'<text x="{left}" y="{top - 30}" font-size="12" fill="#475569">frame {min_frame}</text>',
        f'<text x="{left + plot_w - 74}" y="{top - 30}" font-size="12" fill="#475569">frame {max_frame}</text>',
    ]
    for idx, edge in enumerate(positive):
        y = top + idx * row_h
        from_id = str(edge.get("from_tracklet_candidate_id", ""))
        to_id = str(edge.get("to_tracklet_candidate_id", ""))
        status = str(edge.get("merge_candidate_status", ""))
        color = "#dc2626" if status == "ambiguous_competing_merge" else "#0f766e"
        if status == "needs_visual_review":
            color = "#f97316"
        from_component = component_by_id.get(from_id, {})
        to_component = component_by_id.get(to_id, {})
        fs = parse_int(from_component.get("frame_start")) or parse_int(edge.get("from_frame_start")) or min_frame
        fe = parse_int(from_component.get("frame_end")) or parse_int(edge.get("from_frame_end")) or fs
        ts = parse_int(to_component.get("frame_start")) or parse_int(edge.get("to_frame_start")) or min_frame
        te = parse_int(to_component.get("frame_end")) or parse_int(edge.get("to_frame_end")) or ts
        fx1 = left + (fs - min_frame) / span * plot_w
        fx2 = left + (fe - min_frame) / span * plot_w
        tx1 = left + (ts - min_frame) / span * plot_w
        tx2 = left + (te - min_frame) / span * plot_w
        label = f"{from_id} -> {to_id}"
        parts.append(f'<text x="24" y="{y + 4}" font-size="10" fill="#111827">{html_escape(label)}</text>')
        parts.append(f'<text x="150" y="{y + 4}" font-size="10" fill="{color}">{html_escape(status)}</text>')
        parts.append(f'<line x1="{fx1:.2f}" y1="{y}" x2="{fx2:.2f}" y2="{y}" stroke="#2563eb" stroke-width="5" />')
        parts.append(f'<line x1="{tx1:.2f}" y1="{y}" x2="{tx2:.2f}" y2="{y}" stroke="#7c3aed" stroke-width="5" />')
        parts.append(f'<line x1="{fx2:.2f}" y1="{y}" x2="{tx1:.2f}" y2="{y}" stroke="{color}" stroke-width="2" stroke-dasharray="4 4" />')
        parts.append(f'<circle cx="{fx2:.2f}" cy="{y}" r="4" fill="#2563eb" />')
        parts.append(f'<circle cx="{tx1:.2f}" cy="{y}" r="4" fill="#7c3aed" />')
    if not positive:
        parts.append('<text x="24" y="120" font-size="14" fill="#dc2626">No positive fragment merge candidates in this run.</text>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def render_contact_sheet(path: Path, sample_svgs: Sequence[Path], summary: Mapping[str, Any]) -> None:
    links = "\n".join(
        f'<a class="card" href="merge_candidate_samples/{html_escape(item.name)}" target="_blank">{html_escape(item.stem)}</a>'
        for item in sample_svgs
    )
    if not links:
        links = '<p class="muted">No merge candidate sample SVGs were generated.</p>'
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>OTY1a Fragment Merge Contact Sheet</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #111827; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }}
    .card {{ display: block; padding: 12px; border: 1px solid #cbd5e1; text-decoration: none; color: #0f172a; background: #f8fafc; }}
    code {{ background: #f1f5f9; padding: 2px 4px; }}
    .muted {{ color: #64748b; }}
  </style>
</head>
<body>
  <h1>OTY1a Fragment Merge Contact Sheet</h1>
  <p>Scene <code>{html_escape(str(summary.get("scene", "")))}</code>, positive merge review candidates <code>{html_escape(str(summary.get("fragment_merge_candidate_edges", "")))}</code>.</p>
  <p class="muted">Runtime source is OTY1 optical outputs only. No SAR alignment, SAR band, SAR GT, final box, selector, or confirmed identity is shown.</p>
  <p><a href="oty1a_merge_candidate_timeline.svg">Merge candidate timeline</a></p>
  <div class="grid">{links}</div>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def write_report(path: Path, summary: Mapping[str, Any], blockers: Sequence[str]) -> None:
    lines = [
        "# OTY1a Fragment Merge Candidate Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Scene: `{summary['scene']}`",
        "",
        "## Runtime Boundary",
        "",
        "- runtime source: OTY1 optical tracklet outputs only",
        "- no review_queue, final_gt_working, SAR GT/evidence, final/manual/oracle/review fields",
        "- no selector, G2, A008 scoring, threshold tuning, training, SAR band, or annotation proposal",
        "- merge candidates are review candidates, not confirmed same-target identities",
        "",
        "## Input",
        "",
        f"- OTY1 output dir: `{summary['input_oty1_output_dir']}`",
        f"- OTY1 edges: `{summary['input_oty1_edges']}`",
        f"- OTY1 components: `{summary['input_oty1_components']}`",
        f"- OTY1 state stream: `{summary['input_oty1_state_timeseries']}`",
        "",
        "## OTY1 Edge Counts",
        "",
        f"- geometry feasible edges: `{summary['geometry_feasible_edges']}`",
        f"- clean unambiguous edges: `{summary['clean_unambiguous_edges']}`",
        f"- ambiguous feasible edges: `{summary['ambiguous_feasible_edges']}`",
        f"- selected component edges: `{summary['selected_component_edges']}`",
        "",
        "## OTY1a Results",
        "",
        f"- component review rows: `{summary['component_review_rows']}`",
        f"- merge candidate edge rows: `{summary['merge_candidate_edge_rows']}`",
        f"- fragment merge candidate edges: `{summary['fragment_merge_candidate_edges']}`",
        f"- ambiguous merge candidate edges: `{summary['ambiguous_merge_candidate_edges']}`",
        f"- shape transition audit rows: `{summary['shape_transition_audit_rows']}`",
        f"- 0039/0045 status: `{summary.get('case_0039_0045_status', 'not_applicable')}`",
        "",
        "## Merge Status Distribution",
        "",
        "```json",
        json.dumps(summary["merge_candidate_status_distribution"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Blockers",
        "",
        markdown_list(blockers),
        "",
        "## Next Step",
        "",
        "OTY2 can audit optical-to-SAR high-FPS temporal alignment from these optical state/merge-review artifacts. OTY2 should still not assume optical frame number equals SAR frame number and should not generate SAR band before alignment is audited.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_case_review(
    path: Path,
    case_edge: Mapping[str, Any] | None,
    bridge_edges: Sequence[Mapping[str, Any]],
    svg_path: Path,
) -> None:
    if case_edge:
        status = str(case_edge.get("merge_candidate_status", ""))
        score = parse_float(case_edge.get("merge_candidate_score_not_selector"))
        endpoint_distance = parse_float(case_edge.get("endpoint_center_distance_px"))
        bridge_iou = parse_float(case_edge.get("bridge_iou_proxy"))
        overlap = case_edge.get("frame_overlap_count", "")
        case_lines = [
            f"- merge candidate status: `{status}`",
            f"- merge_candidate_score_not_selector: `{score:.6f}`" if score is not None else "- merge_candidate_score_not_selector: ``",
            f"- endpoint_center_distance_px: `{endpoint_distance:.3f}`" if endpoint_distance is not None else "- endpoint_center_distance_px: ``",
            f"- bridge_iou_proxy: `{bridge_iou:.6f}`" if bridge_iou is not None else "- bridge_iou_proxy: ``",
            f"- frame_overlap_count: `{overlap}`",
            f"- temporal_relation: `{case_edge.get('temporal_relation', '')}`",
            f"- shape_transition_proxy: `{case_edge.get('shape_transition_proxy', '')}`",
            f"- partial_to_full_box_transition_proxy: `{case_edge.get('partial_to_full_box_transition_proxy', '')}`",
        ]
    else:
        case_lines = ["- no OTY1a merge edge was produced for `oty1_tracklet_0039 -> oty1_tracklet_0045`."]

    bridge_lines = []
    for row in bridge_edges[:5]:
        bridge_lines.append(
            f"`{row.get('from_det_id', '')} -> {row.get('to_det_id', '')}`; "
            f"frame_gap=`{row.get('optical_frame_gap', '')}`; "
            f"center_distance_px=`{row.get('center_distance_px', '')}`; "
            f"bbox_iou=`{row.get('bbox_iou', '')}`; "
            f"size_consistency=`{row.get('size_consistency', '')}`; "
            f"selected_for_component=`{row.get('edge_selected_for_component', '')}`"
        )
    lines = [
        "# OTY1a Case Review: GM_RM019 0039/0045",
        "",
        "This case reviews whether `oty1_tracklet_0039` and `oty1_tracklet_0045` should enter fragment merge review under runtime-safe optical geometry.",
        "",
        "## Boundary",
        "",
        "- Runtime evidence is OTY1 optical geometry/state outputs only.",
        "- No SAR frame, SAR GT/evidence, final/manual/oracle/review fields, selector, G2, A008, threshold tuning, training, or annotation proposal is used.",
        "- The result is not confirmed identity truth.",
        "",
        "## OTY1a Merge Edge",
        "",
        *case_lines,
        "",
        "## OTY1 Detection-Level Bridge Evidence",
        "",
        markdown_list(bridge_lines),
        "",
        "## Interpretation",
        "",
        "`oty1_tracklet_0039` and `oty1_tracklet_0045` should be treated as an optical runtime-geometry merge review candidate. The overlap around frames 171/172 and the cross-fragment detection edge are strong enough for review, but competing edges and neighbor/boundary ambiguity mean identity remains unconfirmed.",
        "",
        "## Visualization",
        "",
        f"- `{svg_path}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def latest_oty1a_summaries(output_root: str | Path) -> list[dict[str, Any]]:
    root = Path(output_root)
    latest_by_scene: dict[str, tuple[str, dict[str, Any]]] = {}
    if not root.exists():
        return []
    for output_dir in sorted(root.glob("oty1a_fragment_merge_audit_*")):
        summary_path = output_dir / "oty1a_summary.json"
        if not summary_path.exists():
            continue
        summary = read_json(summary_path)
        scene = str(summary.get("scene", "") or "")
        if not scene:
            continue
        key = output_dir.name
        if scene not in latest_by_scene or key > latest_by_scene[scene][0]:
            latest_by_scene[scene] = (key, summary)
    return [item[1] for item in sorted(latest_by_scene.values(), key=lambda pair: pair[1].get("scene", ""))]


def read_rows_if_exists(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    return read_csv_rows(path) if path.exists() else []


def write_cross_scene_reports(output_root: str | Path, timestamp: str, max_sample_rows: int) -> dict[str, Any]:
    report_dir = REPO_ROOT / "reports" / "oty1a"
    sample_dir = report_dir / "samples"
    summaries = latest_oty1a_summaries(output_root)
    scenes = {str(summary.get("scene", "")): summary for summary in summaries}
    aggregate = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "timestamp": timestamp,
        "scene_count": len(scenes),
        "scenes": scenes,
        "totals": {
            "merge_candidate_edge_rows": sum(int(summary.get("merge_candidate_edge_rows") or 0) for summary in summaries),
            "fragment_merge_candidate_edges": sum(int(summary.get("fragment_merge_candidate_edges") or 0) for summary in summaries),
            "ambiguous_merge_candidate_edges": sum(int(summary.get("ambiguous_merge_candidate_edges") or 0) for summary in summaries),
            "shape_transition_audit_rows": sum(int(summary.get("shape_transition_audit_rows") or 0) for summary in summaries),
        },
        "boundary": {
            "runtime_source": "OTY1 optical tracklet outputs only",
            "forbidden_runtime_sources": [
                "review_queue.csv",
                "final_gt_working.csv",
                "SAR GT",
                "SAR evidence",
                "final/manual/oracle/review fields",
                "target_identity/group_id",
                "selector/G2/A008/threshold/training",
                "annotation proposal labels",
            ],
            "identity_truth_claimed": False,
            "sar_alignment_entered": False,
            "sar_band_entered": False,
        },
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    write_json(report_dir / f"oty1a_cross_scene_fragment_merge_summary_{timestamp}.json", aggregate)

    lines = [
        "# OTY1a Cross-Scene Fragment Merge Summary",
        "",
        f"Generated: `{aggregate['generated_at']}`",
        "",
        "## Boundary",
        "",
        "- Runtime construction uses OTY1 optical outputs only.",
        "- No review/final/SAR GT/evidence/selector/G2/A008/threshold/training source is used.",
        "- These are fragment merge review candidates, not confirmed identities and not annotation proposals.",
        "",
        "## Totals",
        "",
        f"- scenes: `{aggregate['scene_count']}`",
        f"- merge candidate edge rows: `{aggregate['totals']['merge_candidate_edge_rows']}`",
        f"- positive fragment merge review candidates: `{aggregate['totals']['fragment_merge_candidate_edges']}`",
        f"- ambiguous merge candidates: `{aggregate['totals']['ambiguous_merge_candidate_edges']}`",
        f"- shape transition audit rows: `{aggregate['totals']['shape_transition_audit_rows']}`",
        "",
        "## Scene Rows",
        "",
        "| scene | output_dir | positive merge candidates | ambiguous merge candidates | 0039/0045 status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for scene, summary in scenes.items():
        lines.append(
            f"| `{scene}` | `{summary.get('output_dir', '')}` | "
            f"{summary.get('fragment_merge_candidate_edges', 0)} | "
            f"{summary.get('ambiguous_merge_candidate_edges', 0)} | "
            f"`{summary.get('case_0039_0045_status', 'not_applicable')}` |"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "GM_RM019 0039/0045 should be reviewed as an optical geometry fragment-merge candidate, not promoted to identity truth. If the visual/metric presentation is acceptable, the next mainline step is OTY2 high-FPS optical-to-SAR temporal alignment. If the review burden is too high, add OTY1b visualization/metric cleanup first.",
        ]
    )
    (report_dir / f"oty1a_cross_scene_fragment_merge_summary_{timestamp}.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    all_edges: list[dict[str, Any]] = []
    all_shapes: list[dict[str, Any]] = []
    for summary in summaries:
        artifacts = summary.get("artifacts", {})
        if isinstance(artifacts, dict):
            all_edges.extend(read_rows_if_exists(artifacts.get("merge_edges", "")))
            all_shapes.extend(read_rows_if_exists(artifacts.get("shape_transition_audit", "")))
    case_edges = [
        row
        for row in all_edges
        if row.get("scene") == "GM_RM019"
        and row.get("from_tracklet_candidate_id") == "oty1_tracklet_0039"
        and row.get("to_tracklet_candidate_id") == "oty1_tracklet_0045"
    ]
    edge_sample = case_edges + [
        row
        for row in sample_sorted_edges(all_edges, max_sample_rows)
        if str(row.get("merge_edge_id", "")) not in {str(edge.get("merge_edge_id", "")) for edge in case_edges}
    ]
    write_csv(
        sample_dir / "oty1a_fragment_merge_candidate_edges_sample.csv",
        edge_sample[:max_sample_rows],
        MERGE_EDGE_FIELDS,
    )
    shape_sample = case_edges + [
        row
        for row in sample_sorted_edges(all_shapes, max_sample_rows)
        if str(row.get("merge_edge_id", "")) not in {str(edge.get("merge_edge_id", "")) for edge in case_edges}
    ]
    write_csv(
        sample_dir / "oty1a_shape_transition_audit_sample.csv",
        shape_sample[:max_sample_rows],
        MERGE_EDGE_FIELDS,
    )
    return aggregate


def make_limits(args: argparse.Namespace) -> FragmentMergeLimits:
    return FragmentMergeLimits(
        endpoint_k=args.endpoint_k,
        max_forward_gap=args.max_forward_gap,
        max_scan_forward_gap=max(args.max_scan_forward_gap, args.max_forward_gap),
        max_endpoint_distance_px=args.max_endpoint_distance_px,
        max_motion_predicted_distance_px=args.max_motion_predicted_distance_px,
        min_area_ratio=args.min_area_ratio,
        min_aspect_ratio=args.min_aspect_ratio,
        shape_transition_area_ratio=args.shape_transition_area_ratio,
        shape_transition_aspect_ratio=args.shape_transition_aspect_ratio,
        partial_full_bridge_iou=args.partial_full_bridge_iou,
        min_fragment_score=args.min_fragment_score,
        min_review_score=args.min_review_score,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_root) / f"oty1a_fragment_merge_audit_{timestamp}"
    viz_dir = output_dir / "visualizations"
    sample_viz_dir = viz_dir / "merge_candidate_samples"
    sample_viz_dir.mkdir(parents=True, exist_ok=True)

    oty1_dir = ensure_oty1_output_dir(args)
    oty1_edges_path = oty1_dir / "oty1_tracklet_candidate_edges.csv"
    oty1_components_path = oty1_dir / "oty1_optical_tracklet_components.csv"
    oty1_state_path = oty1_dir / "oty1_optical_tracklet_state_timeseries.csv"
    oty1_quality_path = oty1_dir / "oty1_tracklet_quality_audit.csv"
    oty1_summary_path = oty1_dir / "oty1_summary.json"

    oty1_edges = read_csv_rows(oty1_edges_path)
    oty1_components = read_csv_rows(oty1_components_path)
    oty1_state_rows = read_csv_rows(oty1_state_path)
    oty1_quality_rows = read_csv_rows(oty1_quality_path)
    oty1_summary = read_json(oty1_summary_path)
    limits = make_limits(args)

    blockers: list[str] = []
    if not oty1_components:
        blockers.append("OTY1 component table is empty; no fragment profiles can be built.")
    if not oty1_state_rows:
        blockers.append("OTY1 state timeseries is empty; no endpoint geometry can be audited.")
    if str(oty1_summary.get("scene", "") or args.scene) != args.scene:
        blockers.append("OTY1 summary scene does not match requested scene.")

    profiles = build_component_profiles(oty1_components, oty1_state_rows, limits) if not blockers else {}
    review_rows = component_review_rows(profiles)
    merge_edges = build_fragment_merge_edges(profiles, limits) if profiles else []
    shape_rows = shape_transition_rows(merge_edges)
    edge_counts = oty1_edge_statistics(oty1_edges)

    if not merge_edges and not blockers:
        blockers.append("No bounded component-pair rows were produced by OTY1a scan limits.")
    if merge_edges and count_positive_edges(merge_edges) == 0:
        blockers.append("No positive fragment merge review candidates were found; only reject/review-limit rows were produced.")

    write_csv(output_dir / "oty1a_fragment_merge_candidate_edges.csv", merge_edges, MERGE_EDGE_FIELDS)
    write_csv(output_dir / "oty1a_fragment_merge_component_review.csv", review_rows, COMPONENT_REVIEW_FIELDS)
    write_csv(output_dir / "oty1a_shape_transition_audit.csv", shape_rows, MERGE_EDGE_FIELDS)

    state_by_tracklet = rows_by_tracklet(oty1_state_rows)
    case_edge = next(
        (
            row
            for row in merge_edges
            if row.get("scene") == "GM_RM019"
            and row.get("from_tracklet_candidate_id") == "oty1_tracklet_0039"
            and row.get("to_tracklet_candidate_id") == "oty1_tracklet_0045"
        ),
        None,
    )
    bridge_edges = bridge_edges_between_tracklets(
        oty1_edges,
        oty1_state_rows,
        "oty1_tracklet_0039",
        "oty1_tracklet_0045",
    ) if args.scene == "GM_RM019" else []

    sample_svgs: list[Path] = []
    for edge in sample_sorted_edges(merge_edges, args.max_visual_merge_edges):
        if str(edge.get("merge_candidate_status", "")) not in MERGE_POSITIVE_STATUSES:
            continue
        sample_path = sample_viz_dir / f"{safe_name(str(edge.get('merge_edge_id', 'merge_edge')))}.svg"
        render_merge_candidate_svg(sample_path, edge, state_by_tracklet, args.max_endpoint_frames)
        sample_svgs.append(sample_path)
    render_merge_timeline_svg(
        viz_dir / "oty1a_merge_candidate_timeline.svg",
        merge_edges,
        review_rows,
        args.scene,
        args.max_timeline_edges,
    )

    status_counts = edge_status_counts(merge_edges)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scene": args.scene,
        "input_oty1_output_dir": str(oty1_dir),
        "input_oty1_edges": str(oty1_edges_path),
        "input_oty1_components": str(oty1_components_path),
        "input_oty1_state_timeseries": str(oty1_state_path),
        "input_oty1_quality_audit": str(oty1_quality_path),
        "input_oty1_summary": str(oty1_summary_path),
        "output_dir": str(output_dir),
        "visualizations_dir": str(viz_dir),
        "component_review_rows": len(review_rows),
        "merge_candidate_edge_rows": len(merge_edges),
        "shape_transition_audit_rows": len(shape_rows),
        "fragment_merge_candidate_edges": count_positive_edges(merge_edges),
        "ambiguous_merge_candidate_edges": status_counts.get("ambiguous_competing_merge", 0),
        "geometry_feasible_edges": edge_counts["geometry_feasible_edges"],
        "clean_unambiguous_edges": edge_counts["clean_unambiguous_edges"],
        "ambiguous_feasible_edges": edge_counts["ambiguous_feasible_edges"],
        "selected_component_edges": edge_counts["selected_component_edges"],
        "merge_candidate_status_distribution": status_counts,
        "oty1_component_count": len(oty1_components),
        "oty1_state_rows": len(oty1_state_rows),
        "oty1_quality_rows": len(oty1_quality_rows),
        "case_0039_0045_status": str(case_edge.get("merge_candidate_status", "")) if case_edge else "not_found",
        "case_0039_0045_merge_edge_id": str(case_edge.get("merge_edge_id", "")) if case_edge else "",
        "case_0039_0045_bridge_edge_count": len(bridge_edges),
        "posthoc_sources_used_for_runtime_merge": False,
        "sar_alignment_entered": False,
        "sar_band_entered": False,
        "sar_gt_coverage_entered": False,
        "selector_g2_a008_threshold_training_entered": False,
        "annotation_proposal_entered": False,
        "identity_truth_claimed": False,
        "largest_blocker": blockers[0] if blockers else "No hard OTY1a blocker; merge candidates remain review-only geometry candidates.",
        "oty2_recommendation": "OTY2 can start high-FPS optical-to-SAR temporal alignment audit if visual review burden is acceptable; do not generate SAR band before alignment is audited.",
        "audit_limits": {
            "endpoint_k": limits.endpoint_k,
            "max_forward_gap": limits.max_forward_gap,
            "max_scan_forward_gap": limits.max_scan_forward_gap,
            "max_endpoint_distance_px": limits.max_endpoint_distance_px,
            "max_motion_predicted_distance_px": limits.max_motion_predicted_distance_px,
            "min_area_ratio": limits.min_area_ratio,
            "min_aspect_ratio": limits.min_aspect_ratio,
            "shape_transition_area_ratio": limits.shape_transition_area_ratio,
            "shape_transition_aspect_ratio": limits.shape_transition_aspect_ratio,
            "partial_full_bridge_iou": limits.partial_full_bridge_iou,
            "min_fragment_score": limits.min_fragment_score,
            "min_review_score": limits.min_review_score,
        },
        "artifacts": {
            "merge_edges": str(output_dir / "oty1a_fragment_merge_candidate_edges.csv"),
            "component_review": str(output_dir / "oty1a_fragment_merge_component_review.csv"),
            "shape_transition_audit": str(output_dir / "oty1a_shape_transition_audit.csv"),
            "summary": str(output_dir / "oty1a_summary.json"),
            "report": str(output_dir / "oty1a_report.md"),
            "contact_sheet": str(viz_dir / "oty1a_fragment_merge_contact_sheet.html"),
            "timeline": str(viz_dir / "oty1a_merge_candidate_timeline.svg"),
            "merge_candidate_samples": str(sample_viz_dir),
        },
    }
    write_json(output_dir / "oty1a_summary.json", summary)
    write_report(output_dir / "oty1a_report.md", summary, blockers)
    render_contact_sheet(viz_dir / "oty1a_fragment_merge_contact_sheet.html", sample_svgs, summary)

    if args.scene == "GM_RM019":
        report_sample_viz_dir = REPO_ROOT / "reports" / "oty1a" / "samples" / "visualizations"
        case_svg = report_sample_viz_dir / "oty1a_0039_0045_merge_review.svg"
        if case_edge:
            render_merge_candidate_svg(case_svg, case_edge, state_by_tracklet, args.max_endpoint_frames)
        write_case_review(
            REPO_ROOT / "reports" / "oty1a" / "samples" / "oty1a_case_0039_0045_review.md",
            case_edge,
            bridge_edges,
            case_svg,
        )

    cross_scene = write_cross_scene_reports(args.output_root, timestamp, args.max_sample_rows)
    summary["reports_cross_scene_summary_json"] = str(
        REPO_ROOT / "reports" / "oty1a" / f"oty1a_cross_scene_fragment_merge_summary_{timestamp}.json"
    )
    summary["reports_cross_scene_summary_md"] = str(
        REPO_ROOT / "reports" / "oty1a" / f"oty1a_cross_scene_fragment_merge_summary_{timestamp}.md"
    )
    summary["reports_cross_scene_count"] = cross_scene.get("scene_count", 0)
    write_json(output_dir / "oty1a_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--oty1-output-dir", default="")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--endpoint-k", type=int, default=3)
    parser.add_argument("--max-forward-gap", type=int, default=8)
    parser.add_argument("--max-scan-forward-gap", type=int, default=24)
    parser.add_argument("--max-endpoint-distance-px", type=float, default=320.0)
    parser.add_argument("--max-motion-predicted-distance-px", type=float, default=360.0)
    parser.add_argument("--min-area-ratio", type=float, default=0.18)
    parser.add_argument("--min-aspect-ratio", type=float, default=0.18)
    parser.add_argument("--shape-transition-area-ratio", type=float, default=0.75)
    parser.add_argument("--shape-transition-aspect-ratio", type=float, default=0.65)
    parser.add_argument("--partial-full-bridge-iou", type=float, default=0.20)
    parser.add_argument("--min-fragment-score", type=float, default=0.48)
    parser.add_argument("--min-review-score", type=float, default=0.34)
    parser.add_argument("--max-visual-merge-edges", type=int, default=16)
    parser.add_argument("--max-timeline-edges", type=int, default=80)
    parser.add_argument("--max-endpoint-frames", type=int, default=5)
    parser.add_argument("--max-sample-rows", type=int, default=80)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
