"""Run OT0 optical temporal vehicle-state reconstruction audit.

OT0 reads optical frame paths and optional runtime-like detection rows. It
constructs only geometry-based optical tracklet candidate edges. GT/final/
oracle/manual/review columns are audited and reported, but never used for
runtime edge construction.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import struct
import sys
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.optical_state.state_features import (  # noqa: E402
    BBox,
    bbox_from_row,
    bbox_iou,
    center_distance,
    compute_state_features,
    parse_float,
    parse_int,
    size_consistency,
)


POSTHOC_TOKENS = (
    "gt",
    "final",
    "oracle",
    "manual",
    "iou",
    "review",
    "chosen_candidate",
    "center_error",
    "shared_offset",
    "current_good",
)

ID_LIKE_FIELDS = (
    "track_id",
    "object_id",
    "group_id",
    "car_id",
    "target_identity",
    "det_id",
    "opt_det_id",
)

RUNTIME_FRAME_FIELDS = (
    "scene",
    "frame",
    "frame_num",
    "optical_frame",
    "optical_frame_num",
    "sar_frame",
    "sar_frame_num",
    "optical_path",
)

RUNTIME_BBOX_FIELDS = (
    "opt_x1",
    "opt_y1",
    "opt_x2",
    "opt_y2",
    "opt_cx",
    "opt_cy",
    "opt_w",
    "opt_h",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "bbox_cx",
    "bbox_cy",
    "bbox_w",
    "bbox_h",
)


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if not _is_duplicate_header_row(row)]


def _is_duplicate_header_row(row: dict[str, str]) -> bool:
    if not row:
        return True
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


def write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_config(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(f"{path} is not JSON-compatible YAML and PyYAML is unavailable") from exc
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} did not load to a mapping")
        return loaded


def safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text.strip("_") or "item"


def count_files(path: str | Path, suffixes: tuple[str, ...]) -> int:
    root = Path(path)
    if not root.exists():
        return 0
    return sum(1 for item in root.iterdir() if item.is_file() and item.suffix.lower() in suffixes)


def png_size(path: str | Path) -> tuple[int, int] | None:
    try:
        with Path(path).open("rb") as fh:
            header = fh.read(24)
    except OSError:
        return None
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None


def path_exists(path: str | Path | None) -> bool:
    return bool(path and Path(str(path)).exists())


def frame_num_from_path(path: str) -> int | None:
    name = Path(str(path or "")).stem
    match = re.search(r"(\d+)", name)
    if not match:
        return None
    return int(match.group(1))


def first_text(row: dict[str, str], keys: Iterable[str]) -> str:
    for key in keys:
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return ""


def detection_frame_num(row: dict[str, str]) -> int | None:
    for key in ("optical_frame_num", "frame_num", "frame"):
        value = parse_int(row.get(key))
        if value is not None:
            return value
    optical_path = first_text(row, ("optical_path", "optical_frame_path"))
    value = frame_num_from_path(optical_path)
    if value is not None:
        return value
    for key in ("optical_frame", "sar_frame_num"):
        value = parse_int(row.get(key))
        if value is not None:
            return value
    return None


def sar_frame_num(row: dict[str, str]) -> int | None:
    value = parse_int(row.get("sar_frame_num"))
    if value is not None:
        return value
    return frame_num_from_path(first_text(row, ("sar_frame", "sar_pseudocolor_path", "sar_frame_path")))


def is_posthoc_or_forbidden_field(name: str, config: dict[str, Any]) -> bool:
    lower = name.lower()
    if any(lower.startswith(prefix) for prefix in config.get("forbidden_runtime_field_prefixes", [])):
        return True
    if lower in {str(item).lower() for item in config.get("forbidden_runtime_field_names", [])}:
        return True
    return any(token in lower for token in POSTHOC_TOKENS)


def classify_field(name: str, config: dict[str, Any]) -> tuple[str, str]:
    lower = name.lower()
    if is_posthoc_or_forbidden_field(name, config):
        return (
            "posthoc_or_forbidden_for_runtime",
            "audited only; not used to build OT0 runtime edges or state features",
        )
    if lower == "candidate_source_family":
        return ("provenance_only", "not an active rule")
    if lower in ID_LIKE_FIELDS:
        return (
            "id_like_needs_semantic_audit",
            "not treated as same-target runtime identity unless explicitly documented",
        )
    if lower in RUNTIME_BBOX_FIELDS:
        return ("runtime_safe_bbox_geometry", "used for bbox state features and candidate edges")
    if lower in RUNTIME_FRAME_FIELDS:
        return ("runtime_safe_frame_or_path", "used for frame order, image dimensions, or inventory")
    return ("unused_or_context", "not required by OT0 runtime construction")


def audit_fields(rows: list[dict[str, str]], config: dict[str, Any]) -> list[dict[str, Any]]:
    if not rows:
        return []
    headers = list(rows[0].keys())
    out: list[dict[str, Any]] = []
    total = len(rows)
    for name in headers:
        non_empty = sum(1 for row in rows if str(row.get(name, "")).strip())
        category, policy = classify_field(name, config)
        out.append(
            {
                "field": name,
                "category": category,
                "non_empty_rows": non_empty,
                "row_count": total,
                "runtime_use_policy": policy,
            }
        )
    return out


def fieldnames_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    return names


def source_policy_for(path: str, config: dict[str, Any]) -> dict[str, Any]:
    for source_id, meta in config.get("input_source_candidates", {}).items():
        if str(meta.get("source_path", "")).lower() == str(path).lower():
            out = dict(meta)
            out["source_id"] = source_id
            return out
    return {
        "source_id": "manifest_optional_runtime_detection_table",
        "source_kind": "manifest_provided",
        "allowed_use": "field-audited runtime-safe columns only",
        "forbidden_use": "posthoc/final/manual/review columns",
        "lineage_notes": "No matching source metadata in config.",
    }


class UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, a: str, b: str) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def make_detection_rows(
    rows: list[dict[str, str]],
    scene: str,
    source_path: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    scene_rows = [row for row in rows if str(row.get("scene", "")).strip() == scene]
    detections: list[dict[str, Any]] = []
    fallback_size = config.get("global_geometry", {}).get("optical_canvas_fallback", {})
    fallback_w = parse_float(fallback_size.get("width")) or 800.0
    fallback_h = parse_float(fallback_size.get("height")) or 600.0
    for index, row in enumerate(scene_rows, start=1):
        bbox = bbox_from_row(row)
        if bbox is None:
            continue
        optical_path = first_text(row, ("optical_path", "optical_frame_path"))
        size = png_size(optical_path) if optical_path else None
        if size is None:
            frame_w = fallback_w
            frame_h = fallback_h
            size_status = "fallback_config"
        else:
            frame_w = float(size[0])
            frame_h = float(size[1])
            size_status = "read_from_png"
        optical_frame_num = detection_frame_num(row)
        if optical_frame_num is None:
            continue
        row_id = f"{scene}_{index:05d}"
        detections.append(
            {
                "detection_id": row_id,
                "source_row_index": index,
                "scene": scene,
                "target_identity": row.get("target_identity", ""),
                "group_id": row.get("group_id", ""),
                "track_id": row.get("track_id", ""),
                "object_id": row.get("object_id", ""),
                "det_id": row.get("det_id", "") or row.get("opt_det_id", ""),
                "optical_frame_num": optical_frame_num,
                "sar_frame_num": sar_frame_num(row),
                "optical_path": optical_path,
                "optical_image_exists": path_exists(optical_path),
                "frame_width": frame_w,
                "frame_height": frame_h,
                "frame_size_status": size_status,
                "bbox": bbox,
                "source_path": source_path,
            }
        )
    return detections


def same_frame_boxes(detections: list[dict[str, Any]]) -> dict[tuple[str, int], list[BBox]]:
    grouped: dict[tuple[str, int], list[BBox]] = {}
    for det in detections:
        grouped.setdefault((det["scene"], det["optical_frame_num"]), []).append(det["bbox"])
    return grouped


def build_edges(
    detections: list[dict[str, Any]],
    limits: dict[str, Any],
) -> list[dict[str, Any]]:
    max_gap = int(limits.get("max_optical_frame_gap", 12))
    max_distance = float(limits.get("max_center_distance_px", 260.0))
    min_size = float(limits.get("min_size_consistency", 0.25))
    max_edges = int(limits.get("max_edges_per_detection", 5))
    by_id = {det["detection_id"]: det for det in detections}
    out: list[dict[str, Any]] = []
    for source in sorted(detections, key=lambda item: (item["optical_frame_num"], item["detection_id"])):
        candidates: list[dict[str, Any]] = []
        for target in detections:
            if target["detection_id"] == source["detection_id"]:
                continue
            gap = target["optical_frame_num"] - source["optical_frame_num"]
            if gap <= 0 or gap > max_gap:
                continue
            distance = center_distance(source["bbox"], target["bbox"])
            iou = bbox_iou(source["bbox"], target["bbox"])
            size_score = size_consistency(source["bbox"], target["bbox"])
            within_limits = distance <= max_distance and size_score >= min_size
            audit_score = (
                (1.0 / (1.0 + distance / max_distance))
                + size_score
                + min(1.0, iou * 4.0)
                + (1.0 / gap)
            ) / 4.0
            candidates.append(
                {
                    "from_detection_id": source["detection_id"],
                    "to_detection_id": target["detection_id"],
                    "from_target_identity": source.get("target_identity", ""),
                    "to_target_identity": target.get("target_identity", ""),
                    "from_group_id": source.get("group_id", ""),
                    "to_group_id": target.get("group_id", ""),
                    "from_optical_frame_num": source["optical_frame_num"],
                    "to_optical_frame_num": target["optical_frame_num"],
                    "from_sar_frame_num": source.get("sar_frame_num", ""),
                    "to_sar_frame_num": target.get("sar_frame_num", ""),
                    "optical_frame_gap": gap,
                    "frame_adjacency": "adjacent" if gap == 1 else "within_max_gap",
                    "bbox_center_distance_px": distance,
                    "bbox_iou": iou,
                    "bbox_size_consistency": size_score,
                    "edge_audit_score_not_selector": audit_score,
                    "neighbor_ambiguity": "",
                    "missing_frame_reason": "" if gap == 1 else f"gap_{gap}_non_adjacent_available",
                    "edge_candidate_status": "within_audit_limits" if within_limits else "outside_audit_limits",
                    "edge_source_policy": "bbox_geometry_only_no_gt_final_or_review_fields",
                }
            )
        candidates.sort(
            key=lambda item: (
                item["edge_candidate_status"] != "within_audit_limits",
                item["optical_frame_gap"],
                item["bbox_center_distance_px"],
                -item["bbox_iou"],
                -item["bbox_size_consistency"],
            )
        )
        for rank, edge in enumerate(candidates[:max_edges], start=1):
            edge["candidate_rank_for_source_detection"] = rank
            out.append(edge)
    for edge in out:
        if edge["from_detection_id"] not in by_id or edge["to_detection_id"] not in by_id:
            edge["edge_candidate_status"] = "invalid_detection_reference"
    return out


def build_components(
    detections: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    uf = UnionFind(det["detection_id"] for det in detections)
    best_by_from: dict[str, dict[str, Any]] = {}
    for edge in edges:
        if edge.get("edge_candidate_status") != "within_audit_limits":
            continue
        current = best_by_from.get(str(edge["from_detection_id"]))
        if current is None or (
            float(edge["edge_audit_score_not_selector"]) > float(current["edge_audit_score_not_selector"])
        ):
            best_by_from[str(edge["from_detection_id"])] = edge
    for edge in best_by_from.values():
        uf.union(str(edge["from_detection_id"]), str(edge["to_detection_id"]))

    root_to_component: dict[str, str] = {}
    for det in detections:
        root = uf.find(det["detection_id"])
        root_to_component.setdefault(root, f"ot0_component_{len(root_to_component) + 1:03d}")
    component_sizes: dict[str, int] = {}
    for det in detections:
        component = root_to_component[uf.find(det["detection_id"])]
        component_sizes[component] = component_sizes.get(component, 0) + 1

    rows: list[dict[str, Any]] = []
    for det in sorted(detections, key=lambda item: (item["optical_frame_num"], item["detection_id"])):
        component = root_to_component[uf.find(det["detection_id"])]
        rows.append(
            {
                "candidate_component_id": component,
                "component_size": component_sizes[component],
                "detection_id": det["detection_id"],
                "scene": det["scene"],
                "target_identity": det.get("target_identity", ""),
                "group_id": det.get("group_id", ""),
                "optical_frame_num": det["optical_frame_num"],
                "sar_frame_num": det.get("sar_frame_num", ""),
                "identity_supported": False,
                "component_policy": "candidate_edges_from_runtime_safe_bbox_geometry_no_identity_proof",
            }
        )
    return rows


def compute_timeseries(
    detections: list[dict[str, Any]],
    components: list[dict[str, Any]],
    limits: dict[str, Any],
) -> list[dict[str, Any]]:
    component_by_detection = {row["detection_id"]: row["candidate_component_id"] for row in components}
    detections_by_component: dict[str, list[dict[str, Any]]] = {}
    for det in detections:
        component = component_by_detection.get(det["detection_id"], f"singleton_{det['detection_id']}")
        detections_by_component.setdefault(component, []).append(det)
    same_boxes = same_frame_boxes(detections)
    rows: list[dict[str, Any]] = []
    for component, items in detections_by_component.items():
        ordered = sorted(items, key=lambda item: (item["optical_frame_num"], item["detection_id"]))
        for idx, det in enumerate(ordered):
            prev_det = ordered[idx - 1] if idx > 0 else None
            next_det = ordered[idx + 1] if idx + 1 < len(ordered) else None
            state = compute_state_features(
                det["bbox"],
                det["frame_width"],
                det["frame_height"],
                same_boxes.get((det["scene"], det["optical_frame_num"]), []),
                previous_bbox=prev_det["bbox"] if prev_det else None,
                previous_frame_num=prev_det["optical_frame_num"] if prev_det else None,
                current_frame_num=det["optical_frame_num"],
                next_bbox=next_det["bbox"] if next_det else None,
                contact_margin_px=float(limits.get("contact_margin_px", 2.0)),
                neighbor_distance_px=float(limits.get("neighbor_distance_px", 120.0)),
            )
            rows.append(
                {
                    "candidate_component_id": component,
                    "detection_id": det["detection_id"],
                    "scene": det["scene"],
                    "target_identity": det.get("target_identity", ""),
                    "group_id": det.get("group_id", ""),
                    "optical_frame_num": det["optical_frame_num"],
                    "sar_frame_num": det.get("sar_frame_num", ""),
                    "optical_path": det.get("optical_path", ""),
                    "frame_width": det.get("frame_width", ""),
                    "frame_height": det.get("frame_height", ""),
                    "frame_size_status": det.get("frame_size_status", ""),
                    "identity_supported": False,
                    "state_source_policy": "runtime_safe_bbox_geometry_only_component_is_candidate_not_confirmed_identity",
                    **state,
                }
            )
    return rows


def state_schema() -> dict[str, Any]:
    fields = {
        "bbox_center_x": "runtime_safe_from_bbox",
        "bbox_center_y": "runtime_safe_from_bbox",
        "bbox_width": "runtime_safe_from_bbox",
        "bbox_height": "runtime_safe_from_bbox",
        "bbox_area": "runtime_safe_from_bbox",
        "bbox_aspect": "runtime_safe_from_bbox",
        "touch_left": "runtime_safe_from_bbox_and_frame_size",
        "touch_right": "runtime_safe_from_bbox_and_frame_size",
        "touch_top": "runtime_safe_from_bbox_and_frame_size",
        "touch_bottom": "runtime_safe_from_bbox_and_frame_size",
        "velocity_x_px_per_frame": "runtime_safe_if_candidate_previous_edge_exists",
        "velocity_y_px_per_frame": "runtime_safe_if_candidate_previous_edge_exists",
        "center_speed_px_per_frame": "runtime_safe_if_candidate_previous_edge_exists",
        "size_change_ratio": "runtime_safe_if_candidate_previous_edge_exists",
        "track_jitter_proxy_px": "runtime_safe_if_previous_and_next_candidate_edges_exist",
        "neighbor_count": "runtime_safe_if_same_frame_boxes_available",
        "min_neighbor_center_distance_px": "runtime_safe_if_same_frame_boxes_available",
        "truncation_likelihood_proxy": "runtime_safe_proxy_from_boundary_contact_and_size_change",
        "occlusion_proxy_status": "missing_unless_runtime_safe_occlusion_source_exists",
        "identity_supported": "false_until_explicit_runtime_track_identity_or_separate_semantic_audit",
    }
    return {
        "schema_name": "ot0_optical_state_timeseries",
        "runtime_boundary": "GT/final/oracle/manual/review fields are excluded from runtime state construction.",
        "fields": fields,
    }


def svg_polyline(points: list[tuple[float, float]], color: str) -> str:
    if len(points) < 2:
        return ""
    text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{text}" fill="none" stroke="{color}" stroke-width="4" opacity="0.8" />'


def render_trajectory_svg(path: Path, timeseries: list[dict[str, Any]], scene: str) -> None:
    width = 900
    height = 680
    frame_w = max((parse_float(row.get("frame_width")) or 800.0 for row in timeseries), default=800.0)
    frame_h = max((parse_float(row.get("frame_height")) or 600.0 for row in timeseries), default=600.0)
    sx = 800.0 / frame_w
    sy = 560.0 / frame_h
    parts = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
        '<rect x="50" y="70" width="800" height="560" fill="#f8fafc" stroke="#94a3b8" />',
        f'<text x="50" y="38" font-size="22" fill="#111827">OT0 bbox center trajectory overlay: {html_escape(scene)}</text>',
        '<text x="50" y="62" font-size="14" fill="#475569">Blank optical canvas; source images are not copied. Components are candidate continuity only.</text>',
    ]
    colors = ["#0f766e", "#b91c1c", "#2563eb", "#ca8a04", "#7c3aed", "#475569"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in timeseries:
        grouped.setdefault(str(row.get("candidate_component_id", "")), []).append(row)
    for index, (component, rows) in enumerate(sorted(grouped.items())):
        color = colors[index % len(colors)]
        ordered = sorted(rows, key=lambda row: parse_int(row.get("optical_frame_num")) or 0)
        points: list[tuple[float, float]] = []
        for row in ordered:
            x = 50 + (parse_float(row.get("bbox_center_x")) or 0.0) * sx
            y = 70 + (parse_float(row.get("bbox_center_y")) or 0.0) * sy
            points.append((x, y))
        parts.append(svg_polyline(points, color))
        for row, (x, y) in zip(ordered, points):
            frame = html_escape(str(row.get("optical_frame_num", "")))
            touch = str(row.get("touch_any", "")).lower() == "true"
            radius = 7 if touch else 5
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" opacity="0.9" />')
            parts.append(f'<text x="{x + 8:.1f}" y="{y - 6:.1f}" font-size="11" fill="#111827">{frame}</text>')
        legend_y = 92 + index * 22
        parts.append(f'<rect x="660" y="{legend_y - 12}" width="14" height="14" fill="{color}" />')
        parts.append(
            f'<text x="680" y="{legend_y}" font-size="13" fill="#111827">{html_escape(component)} ({len(rows)} rows)</text>'
        )
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="680" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def render_state_strip_svg(path: Path, timeseries: list[dict[str, Any]], scene: str) -> None:
    ordered = sorted(timeseries, key=lambda row: (str(row.get("candidate_component_id", "")), parse_int(row.get("optical_frame_num")) or 0))
    width = 1100
    row_h = 30
    height = max(160, 92 + row_h * len(ordered))
    parts = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
        f'<text x="30" y="36" font-size="22" fill="#111827">OT0 state transition strip: {html_escape(scene)}</text>',
        '<text x="30" y="60" font-size="14" fill="#475569">Touch/contact and truncation are runtime-safe proxies; occlusion remains missing unless a runtime source appears.</text>',
    ]
    for idx, row in enumerate(ordered):
        y = 92 + idx * row_h
        touch = str(row.get("touch_any", "")).lower() == "true"
        ambiguity = str(row.get("neighbor_ambiguity_proxy", "")).lower() == "true"
        trunc = str(row.get("truncation_likelihood_proxy", ""))
        color = "#f97316" if touch else "#14b8a6"
        amb_color = "#dc2626" if ambiguity else "#94a3b8"
        parts.append(f'<text x="30" y="{y}" font-size="13" fill="#111827">{html_escape(str(row.get("candidate_component_id", "")))}</text>')
        parts.append(f'<text x="210" y="{y}" font-size="13" fill="#334155">frame {html_escape(str(row.get("optical_frame_num", "")))}</text>')
        parts.append(f'<rect x="310" y="{y - 13}" width="80" height="18" fill="{color}" opacity="0.82" />')
        parts.append(f'<text x="400" y="{y}" font-size="13" fill="#334155">touch={html_escape(str(row.get("touch_any", "")))}</text>')
        parts.append(f'<rect x="510" y="{y - 13}" width="80" height="18" fill="{amb_color}" opacity="0.82" />')
        parts.append(f'<text x="600" y="{y}" font-size="13" fill="#334155">neighbors={html_escape(str(row.get("neighbor_count", "")))}</text>')
        parts.append(f'<text x="740" y="{y}" font-size="13" fill="#334155">{html_escape(trunc)}</text>')
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def file_uri(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).resolve().as_uri()
    except ValueError:
        return path


def render_track_strip_html(path: Path, timeseries: list[dict[str, Any]], scene: str) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in timeseries:
        grouped.setdefault(str(row.get("candidate_component_id", "")), []).append(row)
    cards: list[str] = []
    for component, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))[:4]:
        frames: list[str] = []
        for row in sorted(rows, key=lambda row: parse_int(row.get("optical_frame_num")) or 0):
            image = file_uri(str(row.get("optical_path", "")))
            x = parse_float(row.get("bbox_x1")) or 0.0
            y = parse_float(row.get("bbox_y1")) or 0.0
            w = parse_float(row.get("bbox_width")) or 0.0
            h = parse_float(row.get("bbox_height")) or 0.0
            fw = parse_float(row.get("frame_width")) or 800.0
            fh = parse_float(row.get("frame_height")) or 600.0
            left = 100 * x / fw
            top = 100 * y / fh
            bw = 100 * w / fw
            bh = 100 * h / fh
            frames.append(
                f"""
                <figure>
                  <div class="thumb">
                    <img src="{html_escape(image)}" />
                    <span class="box" style="left:{left:.3f}%;top:{top:.3f}%;width:{bw:.3f}%;height:{bh:.3f}%"></span>
                  </div>
                  <figcaption>frame {html_escape(str(row.get("optical_frame_num", "")))} | touch={html_escape(str(row.get("touch_any", "")))}</figcaption>
                </figure>
                """
            )
        cards.append(
            f"""
            <section>
              <h2>{html_escape(component)} ({len(rows)} rows)</h2>
              <div class="strip">{''.join(frames)}</div>
            </section>
            """
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>OT0 Optical Track Strip</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #111827; }}
    h1 {{ font-size: 24px; }}
    h2 {{ font-size: 18px; margin-top: 24px; }}
    .strip {{ display: flex; gap: 12px; overflow-x: auto; padding-bottom: 12px; }}
    figure {{ width: 220px; margin: 0; flex: 0 0 auto; }}
    .thumb {{ position: relative; width: 220px; height: 165px; background: #f1f5f9; border: 1px solid #cbd5e1; overflow: hidden; }}
    img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
    .box {{ position: absolute; border: 3px solid #f97316; box-sizing: border-box; background: rgba(249,115,22,0.08); }}
    figcaption {{ font-size: 12px; margin-top: 4px; color: #334155; }}
    .note {{ color: #475569; }}
  </style>
</head>
<body>
  <h1>OT0 Optical Track Strip: {html_escape(scene)}</h1>
  <p class="note">Images are referenced from local data paths, not copied. Components are candidate continuity only and do not prove same-target identity.</p>
  {''.join(cards)}
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def render_blocker_svg(path: Path, blockers: list[str]) -> None:
    lines = "\n".join(
        f'<text x="40" y="{95 + idx * 32}" font-size="18" fill="#334155">{html_escape(item)}</text>'
        for idx, item in enumerate(blockers[:12])
    )
    body = f"""
<rect x="0" y="0" width="960" height="520" fill="#ffffff" />
<text x="40" y="48" font-size="26" fill="#111827">OT0 blocker summary</text>
<text x="40" y="75" font-size="16" fill="#64748b">No runtime-safe optical tracklet component was constructed.</text>
{lines}
"""
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="520" font-family="Arial, Helvetica, sans-serif">\n'
        + body
        + "\n</svg>\n",
        encoding="utf-8",
    )


def markdown_list(items: Iterable[str]) -> str:
    values = [str(item) for item in items if str(item)]
    return "\n".join(f"- {item}" for item in values) if values else "- none"


def write_boundary_doc(path: Path) -> None:
    path.write_text(
        """# OT0 Runtime/Posthoc Boundary

## Runtime Used By OT0

- scene and frame/path fields
- optical frame order
- optical bbox geometry fields such as `opt_x1`, `opt_y1`, `opt_x2`, `opt_y2`
- image dimensions read from the optical PNG when available
- same-frame optical boxes from the same runtime-like source

## Posthoc Or Forbidden For Runtime

- all `final_*`, `gt_*`, `oracle_*`, and `manual_*` fields
- `review_status`, `review_note`, `chosen_candidate_source`, and manual adjustment fields
- IoU, center error, reviewed best candidate, or coverage accounting
- `candidate_source_family` as an active rule
- shared-offset replacement

## Identity Boundary

`group_id`, `target_identity`, `car_id`, detector ids, and object labels are audited as id-like fields. They are not treated as same-target runtime track ids unless a separate semantic audit proves that meaning.

OT0 candidate components are geometry continuity hypotheses only.
""",
        encoding="utf-8",
    )


def write_lineage_doc(path: Path, source_meta: dict[str, Any], posthoc_path: str) -> None:
    path.write_text(
        "\n".join(
            [
                "# OT0 Input Source Lineage",
                "",
                f"- runtime-like source id: `{source_meta.get('source_id', '')}`",
                f"- runtime-like source kind: `{source_meta.get('source_kind', '')}`",
                f"- runtime-like source path: `{source_meta.get('source_path', '')}`",
                f"- allowed use: {source_meta.get('allowed_use', '')}",
                f"- forbidden use: {source_meta.get('forbidden_use', '')}",
                f"- lineage note: {source_meta.get('lineage_notes', '')}",
                f"- posthoc table: `{posthoc_path}`",
                "",
                "OT0 reads only runtime-safe bbox/frame/path columns from mixed sources. Final/review/manual columns are reported as forbidden for runtime.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = load_json_config(args.config)
    manifest = read_csv_rows(args.manifest)
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_root) / f"ot0_optical_temporal_state_audit_{timestamp}"
    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)

    scene = args.scene
    manifest_row = next((row for row in manifest if row.get("scene") == scene), None)
    if manifest_row is None:
        raise KeyError(f"scene {scene!r} not found in {args.manifest}")

    runtime_path = args.runtime_detection_table or manifest_row.get("optional_runtime_detection_table", "")
    posthoc_path = manifest_row.get("optional_posthoc_gt_table", "")
    source_meta = source_policy_for(runtime_path, config)

    missing_paths: list[dict[str, Any]] = []
    for kind, value in (
        ("optical_frames_dir", manifest_row.get("optical_frames_dir", "")),
        ("sar_frames_dir", manifest_row.get("sar_frames_dir", "")),
        ("sar_gray_frames_dir", manifest_row.get("sar_gray_frames_dir", "")),
        ("depth_dir", manifest_row.get("depth_dir", "")),
        ("optional_runtime_detection_table", runtime_path),
        ("optional_posthoc_gt_table", posthoc_path),
    ):
        missing_paths.append(
            {
                "scene": scene,
                "kind": kind,
                "path": value,
                "exists": path_exists(value),
                "runtime_use_policy": "runtime" if "posthoc" not in kind else "posthoc_only",
            }
        )

    raw_runtime_rows = read_csv_rows(runtime_path) if runtime_path and Path(runtime_path).exists() else []
    scene_runtime_rows = [row for row in raw_runtime_rows if row.get("scene") == scene]
    field_audit = audit_fields(raw_runtime_rows, config)
    detections = make_detection_rows(raw_runtime_rows, scene, runtime_path, config)
    limits = config.get("audit_candidate_edge_limits", {})
    edges = build_edges(detections, limits) if detections else []
    within_edges = [edge for edge in edges if edge.get("edge_candidate_status") == "within_audit_limits"]
    components = build_components(detections, edges) if detections and within_edges else []
    timeseries = compute_timeseries(detections, components, limits) if components else []

    inventory_rows = [
        {
            "scene": scene,
            "optical_frames_dir": manifest_row.get("optical_frames_dir", ""),
            "optical_frame_count": count_files(manifest_row.get("optical_frames_dir", ""), (".png", ".jpg", ".jpeg")),
            "sar_frames_dir": manifest_row.get("sar_frames_dir", ""),
            "sar_frame_count": count_files(manifest_row.get("sar_frames_dir", ""), (".png", ".jpg", ".jpeg")),
            "sar_gray_frames_dir": manifest_row.get("sar_gray_frames_dir", ""),
            "sar_gray_frame_count": count_files(manifest_row.get("sar_gray_frames_dir", ""), (".png", ".jpg", ".jpeg")),
            "depth_dir": manifest_row.get("depth_dir", ""),
            "depth_file_count": count_files(manifest_row.get("depth_dir", ""), (".npy", ".png")),
            "optional_runtime_detection_table": runtime_path,
            "runtime_table_exists": path_exists(runtime_path),
            "runtime_table_total_rows": len(raw_runtime_rows),
            "runtime_table_scene_rows": len(scene_runtime_rows),
            "usable_scene_bbox_rows": len(detections),
            "optional_posthoc_gt_table": posthoc_path,
            "posthoc_table_exists": path_exists(posthoc_path),
            "source_kind": source_meta.get("source_kind", ""),
            "source_runtime_policy": source_meta.get("allowed_use", ""),
            "source_forbidden_policy": source_meta.get("forbidden_use", ""),
            "notes": manifest_row.get("notes", ""),
        }
    ]

    hard_blockers: list[str] = []
    boundary_notes: list[str] = []
    if not runtime_path:
        hard_blockers.append("No optional runtime detection table configured.")
    elif not Path(runtime_path).exists():
        hard_blockers.append("Optional runtime detection table path does not exist.")
    if raw_runtime_rows and not scene_runtime_rows:
        hard_blockers.append(f"Runtime-like table exists but has no rows for scene {scene}.")
    if scene_runtime_rows and not detections:
        hard_blockers.append("Scene rows exist but no usable runtime-safe optical bbox geometry was found.")
    if detections and not within_edges:
        hard_blockers.append("Usable bbox rows exist but no candidate edge stayed within OT0 audit construction limits.")
    if detections:
        boundary_notes.append("No explicit same-target runtime track id was proven; components are candidate continuity only.")
    if posthoc_path:
        boundary_notes.append("Posthoc/final GT table is present but excluded from runtime tracklet construction.")

    write_csv(
        output_dir / "ot0_runtime_input_inventory.csv",
        inventory_rows,
        list(inventory_rows[0].keys()),
    )
    write_csv(
        output_dir / "ot0_optical_detection_field_audit.csv",
        field_audit,
        ["field", "category", "non_empty_rows", "row_count", "runtime_use_policy"],
    )
    write_csv(
        output_dir / "ot0_missing_path_report.csv",
        missing_paths,
        ["scene", "kind", "path", "exists", "runtime_use_policy"],
    )
    write_json(output_dir / "ot0_optical_state_timeseries_schema.json", state_schema())
    write_boundary_doc(output_dir / "ot0_runtime_posthoc_boundary.md")
    write_lineage_doc(output_dir / "ot0_input_source_lineage.md", source_meta, posthoc_path)

    if edges:
        write_csv(output_dir / "ot0_tracklet_candidate_edges.csv", edges, fieldnames_from_rows(edges))
    if not within_edges:
        (output_dir / "ot0_tracklet_blockers.md").write_text(
            "# OT0 Tracklet Blockers\n\n" + markdown_list(hard_blockers or boundary_notes) + "\n",
            encoding="utf-8",
        )
    if components:
        write_csv(output_dir / "ot0_optical_tracklet_components_pilot.csv", components, fieldnames_from_rows(components))
    else:
        (output_dir / "ot0_optical_tracklet_components_blocked.md").write_text(
            "# OT0 Candidate Components Blocked\n\n" + markdown_list(hard_blockers or boundary_notes) + "\n",
            encoding="utf-8",
        )
    if timeseries:
        write_csv(output_dir / "ot0_optical_state_timeseries_pilot.csv", timeseries, fieldnames_from_rows(timeseries))
        render_track_strip_html(viz_dir / "optical_track_strip.html", timeseries, scene)
        render_trajectory_svg(viz_dir / "bbox_center_trajectory_overlay.svg", timeseries, scene)
        render_state_strip_svg(viz_dir / "state_transition_strip.svg", timeseries, scene)
    else:
        render_blocker_svg(viz_dir / "missing_field_blocker_summary.svg", hard_blockers or boundary_notes)

    blocker_text = "# OT0 Blockers And Next Steps\n\n"
    blocker_text += "## Hard Blockers\n\n" + markdown_list(hard_blockers) + "\n\n"
    blocker_text += "## Boundary Notes\n\n" + markdown_list(boundary_notes) + "\n\n"
    blocker_text += "## Next Steps\n\n"
    if detections and within_edges:
        blocker_text += (
            "- Use the vehicle-bearing continuous substream components as OT0 state-trajectory pilots.\n"
            "- Review candidate components visually; do not treat them as same-target identity yet.\n"
            "- OT1 may proceed only as a conditional mechanism pilot that carries identity uncertainty, not as a formal SAR band pipeline.\n"
            "- Keep `final_gt_working.csv` reserved for OT2 posthoc coverage only.\n"
        )
    else:
        blocker_text += (
            "- Provide or generate a runtime-safe optical detection/tracking table with bbox geometry.\n"
            "- Keep any annotation/final table in the posthoc lane.\n"
            "- Re-run OT0 before OT1 SAR fan/range band transfer.\n"
        )
    (output_dir / "ot0_blockers_and_next_steps.md").write_text(blocker_text, encoding="utf-8")

    frame_counts = sorted({det["optical_frame_num"] for det in detections})
    component_ids = {row["candidate_component_id"] for row in components}
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scene": scene,
        "config": str(Path(args.config)),
        "manifest": str(Path(args.manifest)),
        "output_dir": str(output_dir),
        "runtime_detection_table": runtime_path,
        "runtime_detection_source_found": bool(raw_runtime_rows),
        "runtime_table_total_rows": len(raw_runtime_rows),
        "runtime_table_scene_rows": len(scene_runtime_rows),
        "usable_runtime_bbox_rows": len(detections),
        "usable_optical_frame_count": len(frame_counts),
        "candidate_edge_rows": len(edges),
        "candidate_edges_within_audit_limits": len(within_edges),
        "candidate_components_pilot_rows": len(components),
        "candidate_component_count": len(component_ids),
        "identity_supported_runtime_tracklet": False,
        "identity_support_status": "not_proven_group_id_and_target_identity_are_not_used_as_track_id",
        "boundary_contact_computable": bool(timeseries),
        "truncation_proxy_computable": bool(timeseries),
        "jitter_proxy_computable": any(str(row.get("track_jitter_proxy_status", "")).startswith("available") for row in timeseries),
        "neighbor_fields_computable": bool(timeseries),
        "occlusion_proxy_status": "missing_no_runtime_safe_occlusion_source",
        "posthoc_gt_table": posthoc_path,
        "posthoc_gt_used_for_runtime": False,
        "formal_pipeline_modified": False,
        "selector_g2_threshold_training_entered": False,
        "candidate_source_family_active_rule": False,
        "shared_offset_runtime_replacement": False,
        "hard_blocker_count": len(hard_blockers),
        "boundary_notes": boundary_notes,
        "largest_blocker": hard_blockers[0] if hard_blockers else "No hard OT0 blocker for vehicle-bearing substream pilot; same-target identity remains candidate-only.",
        "next_step_ot1_recommendation": (
            "CONDITIONAL_GO for OT1 mechanism pilot on reviewed vehicle-bearing candidate components; keep identity uncertainty explicit and do not use GT/final for band generation"
            if components
            else "NO_GO until runtime-safe optical detections/components exist"
        ),
        "artifacts": {
            "runtime_input_inventory": str(output_dir / "ot0_runtime_input_inventory.csv"),
            "field_audit": str(output_dir / "ot0_optical_detection_field_audit.csv"),
            "edges": str(output_dir / "ot0_tracklet_candidate_edges.csv") if edges else "",
            "tracklet_blockers": str(output_dir / "ot0_tracklet_blockers.md") if not within_edges else "",
            "components": str(output_dir / "ot0_optical_tracklet_components_pilot.csv") if components else "",
            "timeseries": str(output_dir / "ot0_optical_state_timeseries_pilot.csv") if timeseries else "",
            "schema": str(output_dir / "ot0_optical_state_timeseries_schema.json"),
            "boundary": str(output_dir / "ot0_runtime_posthoc_boundary.md"),
            "blockers": str(output_dir / "ot0_blockers_and_next_steps.md"),
            "report": str(output_dir / "ot0_report.md"),
        },
    }
    write_json(output_dir / "ot0_summary.json", summary)

    report_lines = [
        "# OT0 Optical Temporal Vehicle-State Reconstruction Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Scene: `{scene}`",
        "",
        "## Working Hypothesis",
        "",
        "- H0: A full optical stream exists, but only vehicle-bearing substreams need bbox rows for OT0.",
        "- H1: The 442-row review queue can provide optical bbox geometry for candidate edge audit, while review/final columns stay forbidden for runtime.",
        "- H2: Adjacent/nearby-frame bbox continuity can create candidate components, but it cannot by itself prove same-target identity.",
        "",
        "## Input Source",
        "",
        f"- runtime-like table: `{runtime_path}`",
        f"- runtime-like source kind: `{source_meta.get('source_kind', '')}`",
        f"- total runtime-like rows: `{len(raw_runtime_rows)}`",
        f"- scene rows: `{len(scene_runtime_rows)}`",
        f"- usable bbox rows: `{len(detections)}`",
        f"- posthoc/final table: `{posthoc_path}`",
        "",
        "## Results",
        "",
        f"- candidate edge rows: `{len(edges)}`",
        f"- candidate edges within audit limits: `{len(within_edges)}`",
        f"- candidate component rows: `{len(components)}`",
        f"- candidate component count: `{len(component_ids)}`",
        f"- identity-supported runtime tracklet: `false`",
        f"- boundary/contact/truncation fields computable: `{bool(timeseries)}`",
        f"- jitter available in any row: `{summary['jitter_proxy_computable']}`",
        f"- neighbor fields computable: `{summary['neighbor_fields_computable']}`",
        "",
        "## Boundary Check",
        "",
        "- no formal pipeline modification",
        "- no selector, G2, threshold, or training",
        "- no GT/final/oracle/manual/review fields used for runtime tracklet construction",
        "- `candidate_source_family` remains provenance only",
        "- shared-offset remains review-only",
        "",
        "## Largest Blocker",
        "",
        summary["largest_blocker"],
        "",
        "## Boundary Notes",
        "",
        markdown_list(boundary_notes),
        "",
        "## OT1 Readiness",
        "",
        summary["next_step_ot1_recommendation"],
    ]
    (output_dir / "ot0_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    workspace_log_dir = Path("D:/profile/research/workspace/logs")
    if workspace_log_dir.exists():
        log_path = workspace_log_dir / f"ot0_optical_temporal_state_audit_{timestamp}.md"
        log_path.write_text(
            "# OT0 Optical Temporal State Audit Log\n\n"
            f"- repo: `{REPO_ROOT}`\n"
            f"- output: `{output_dir}`\n"
            f"- interpreter: `{sys.executable}`\n"
            f"- boundary: no selector/G2/threshold/training; no posthoc fields used for runtime\n",
            encoding="utf-8",
        )
        summary["workspace_log"] = str(log_path)
        write_json(output_dir / "ot0_summary.json", summary)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/ot_stream_config.yaml")
    parser.add_argument("--manifest", default="manifests/ot0_stream_manifest.csv")
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--runtime-detection-table", default="")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
