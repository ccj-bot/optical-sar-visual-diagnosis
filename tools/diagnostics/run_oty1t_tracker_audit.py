"""Run OTY1t standard MOT tracker audit.

OTY1t replays OTY0 YOLO detections through a standard MOT tracker and writes
optical identity hypotheses, tracker state streams, event audits, and
comparison rows against OTY1/OTY1a. Tracker ids are runtime optical hypotheses
only. This runner does not use SAR, GT, final/manual/oracle/review fields,
selector/G2/A008 scores, threshold tuning, training signals, or annotation
proposal labels for runtime tracking.
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

from src.optical_state.state_features import BBox, center_distance, parse_float, parse_int  # noqa: E402
from src.optical_state.tracklet_builder import normalize_detections  # noqa: E402
from src.optical_state.tracker_audit import (  # noqa: E402
    TrackerAuditConfig,
    build_comparison_row,
    build_tracker_state_timeseries,
    build_tracker_tracks,
    bytetrack_dependency_facts,
    case_0039_0045_analysis,
    run_bytetrack_detection_table_replay,
)


FORBIDDEN_RUNTIME_TOKENS = (
    "gt",
    "final",
    "manual",
    "oracle",
    "review",
    "sar",
    "posthoc",
    "target_identity",
    "group_id",
    "selector",
    "g2",
    "a008",
    "threshold",
    "training",
    "proposal",
)

ASSIGNMENT_FIELDS = [
    "scene",
    "optical_frame_num",
    "det_id",
    "tracker_name",
    "tracker_input_mode",
    "tracker_track_id",
    "optical_identity_hypothesis_id",
    "class_name",
    "confidence",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "bbox_center_x",
    "bbox_center_y",
    "bbox_w",
    "bbox_h",
    "track_state",
    "association_confidence_proxy",
    "is_low_score_detection",
    "is_recovered_detection",
    "is_unmatched_detection",
    "is_new_track",
    "is_lost_track",
    "is_reactivated_track",
    "runtime_source_policy",
]

TRACK_FIELDS = [
    "scene",
    "tracker_name",
    "tracker_track_id",
    "optical_identity_hypothesis_id",
    "frame_start",
    "frame_end",
    "detection_count",
    "frame_span",
    "missing_gap_count",
    "max_gap",
    "mean_confidence",
    "min_confidence",
    "mean_center_speed",
    "max_center_speed",
    "mean_area_change_ratio",
    "max_area_change_ratio",
    "boundary_contact_count",
    "neighbor_ambiguity_count",
    "low_score_detection_count",
    "lost_count",
    "reactivated_count",
    "track_fragmentation_proxy",
    "possible_id_switch_count",
    "duplicate_track_overlap_count",
    "track_status",
    "identity_status",
]

STATE_FIELDS = [
    "scene",
    "optical_frame_num",
    "tracker_track_id",
    "optical_identity_hypothesis_id",
    "det_id",
    "bbox_center_x",
    "bbox_center_y",
    "bbox_w",
    "bbox_h",
    "bbox_area",
    "bbox_aspect",
    "bottom_y",
    "velocity_x",
    "velocity_y",
    "center_speed",
    "area_change_ratio",
    "aspect_change_ratio",
    "bottom_y_shift",
    "boundary_contact",
    "neighbor_ambiguity_proxy",
    "partial_to_full_transition_proxy",
    "full_to_partial_transition_proxy",
    "state_status",
    "identity_status",
]

EVENT_FIELDS = [
    "scene",
    "tracker_name",
    "event_type",
    "tracker_track_id",
    "related_tracker_track_id",
    "optical_frame_num",
    "frame_start",
    "frame_end",
    "event_score_proxy",
    "event_reason",
    "review_required",
]

COMPARISON_FIELDS = [
    "scene",
    "oty1_component_count",
    "oty1_fragmented_count",
    "oty1_ambiguous_count",
    "oty1a_review_candidates_including_ambiguous",
    "oty1a_nonambiguous_candidates",
    "oty1a_ambiguous_competing_candidates",
    "tracker_track_count",
    "tracker_short_track_count",
    "tracker_fragmented_hypothesis_count",
    "tracker_ambiguous_hypothesis_count",
    "tracker_duplicate_overlap_count",
    "tracker_possible_id_switch_count",
    "singleton_reduction_proxy",
    "fragment_reduction_proxy",
    "comparison_policy",
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


def markdown_list(items: Iterable[str]) -> str:
    values = list(items)
    return "\n".join(f"- {item}" for item in values) if values else "- none"


def boolish(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


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


def frame_sizes_from_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[int, int] | None]:
    out: dict[str, tuple[int, int] | None] = {}
    for row in rows:
        optical_path = str(row.get("optical_path", "") or "").strip()
        if optical_path and optical_path not in out:
            out[optical_path] = png_size(optical_path)
    return out


def optical_frame_inventory(rows: Sequence[Mapping[str, Any]], oty0_summary: Mapping[str, Any]) -> list[int]:
    frames = {value for value in (parse_int(row.get("optical_frame_num")) for row in rows) if value is not None}
    frame_dirs: set[Path] = set()
    for row in rows:
        optical_path = str(row.get("optical_path", "") or "").strip()
        if optical_path:
            frame_dirs.add(Path(optical_path).parent)
    for frame_dir in frame_dirs:
        if not frame_dir.exists():
            continue
        for item in frame_dir.iterdir():
            if item.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            frame_num = parse_int(item.stem)
            if frame_num is not None:
                frames.add(frame_num)
    frame_count = parse_int(oty0_summary.get("optical_frame_count")) or parse_int(oty0_summary.get("total_optical_frames"))
    if frame_count and (not frames or min(frames) == 0):
        frames.update(range(frame_count))
    return sorted(frames)


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
        table = Path(args.oty0_detection_table)
        if table.exists():
            return table
        raise FileNotFoundError(f"OTY0 detection table not found: {table}")
    latest = latest_oty0_detection_table(args.output_root, args.scene)
    if latest is not None:
        return latest
    if not args.run_oty0_if_missing:
        raise FileNotFoundError(f"No OTY0 detection table found for {args.scene} under {args.output_root}")
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
        raise FileNotFoundError("OTY0 runner completed but no detection table was found.")
    return latest


def _summary_scene(output_dir: Path, summary_name: str) -> str:
    summary = read_json(output_dir / summary_name)
    return str(summary.get("scene", "") or "").strip()


def latest_output_dir(output_root: str | Path, prefix: str, summary_name: str, scene: str) -> Path | None:
    root = Path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(root.glob(f"{prefix}_*"), key=lambda path: path.name, reverse=True):
        if (output_dir / summary_name).exists() and _summary_scene(output_dir, summary_name) == scene:
            return output_dir
    return None


def ensure_optional_output_dir(
    explicit_path: str,
    output_root: str | Path,
    prefix: str,
    summary_name: str,
    scene: str,
) -> Path | None:
    if explicit_path:
        path = Path(explicit_path)
        return path if path.exists() else None
    return latest_output_dir(output_root, prefix, summary_name, scene)


def forbidden_input_fields(fieldnames: Sequence[str]) -> list[str]:
    out: list[str] = []
    for field in fieldnames:
        lower = str(field).lower()
        if any(token in lower for token in FORBIDDEN_RUNTIME_TOKENS):
            out.append(str(field))
    return out


def count_status(rows: Sequence[Mapping[str, Any]], field: str, value: str) -> int:
    return sum(1 for row in rows if str(row.get(field, "")) == value)


def count_events(events: Sequence[Mapping[str, Any]], event_type: str) -> int:
    return sum(1 for row in events if str(row.get("event_type", "")) == event_type)


def assignment_bbox(row: Mapping[str, Any]) -> BBox:
    return BBox(
        parse_float(row.get("bbox_x1")) or 0.0,
        parse_float(row.get("bbox_y1")) or 0.0,
        parse_float(row.get("bbox_x2")) or 0.0,
        parse_float(row.get("bbox_y2")) or 0.0,
    )


def ambiguous_association_events(
    assignments: Sequence[Mapping[str, Any]],
    config: TrackerAuditConfig,
) -> list[dict[str, Any]]:
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for row in assignments:
        frame = parse_int(row.get("optical_frame_num"))
        if frame is not None:
            grouped.setdefault(frame, []).append(row)
    events: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for frame, rows in grouped.items():
        tracked = [row for row in rows if str(row.get("tracker_track_id", "") or "")]
        for left_index, left in enumerate(tracked):
            left_id = str(left.get("tracker_track_id", ""))
            left_box = assignment_bbox(left)
            for right in tracked[left_index + 1 :]:
                right_id = str(right.get("tracker_track_id", ""))
                if not right_id or right_id == left_id:
                    continue
                distance = center_distance(left_box, assignment_bbox(right))
                if distance > config.neighbor_distance_px:
                    continue
                pair = (frame, left_id, right_id)
                if pair in seen:
                    continue
                seen.add(pair)
                events.append(
                    {
                        "scene": left.get("scene", ""),
                        "tracker_name": config.tracker_name,
                        "event_type": "ambiguous_association",
                        "tracker_track_id": left_id,
                        "related_tracker_track_id": right_id,
                        "optical_frame_num": frame,
                        "frame_start": frame,
                        "frame_end": frame,
                        "event_score_proxy": 1.0 / (1.0 + distance / max(1.0, config.neighbor_distance_px)),
                        "event_reason": "two tracker hypotheses have close same-frame optical centers",
                        "review_required": True,
                    }
                )
    return events


def sort_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(row) for row in events],
        key=lambda row: (
            parse_int(row.get("optical_frame_num")) or 0,
            str(row.get("event_type", "")),
            str(row.get("tracker_track_id", "")),
            str(row.get("related_tracker_track_id", "")),
        ),
    )


def identity_color(identity_status: str) -> str:
    if identity_status == "tracker_stable_hypothesis":
        return "#0f766e"
    if identity_status == "tracker_fragmented_hypothesis":
        return "#f97316"
    if identity_status == "tracker_ambiguous_hypothesis":
        return "#dc2626"
    if identity_status == "tracker_duplicate_overlap_hypothesis":
        return "#7c3aed"
    if identity_status == "tracker_short_hypothesis":
        return "#64748b"
    return "#2563eb"


def render_tracker_timeline_svg(
    path: Path,
    tracks: Sequence[Mapping[str, Any]],
    state_rows: Sequence[Mapping[str, Any]],
    scene: str,
    max_tracks: int,
) -> None:
    rows_by_track: dict[str, list[Mapping[str, Any]]] = {}
    for row in state_rows:
        rows_by_track.setdefault(str(row.get("tracker_track_id", "")), []).append(row)
    top_tracks = sorted(
        tracks,
        key=lambda row: (-(parse_int(row.get("detection_count")) or 0), parse_int(row.get("frame_start")) or 0),
    )[:max_tracks]
    frame_values = [parse_int(row.get("optical_frame_num")) for row in state_rows]
    frame_values = [value for value in frame_values if value is not None]
    min_frame = min(frame_values) if frame_values else 0
    max_frame = max(frame_values) if frame_values else 1
    span = max(1, max_frame - min_frame)
    width = 1280
    left = 230
    right = 42
    top = 90
    row_h = 26
    height = max(190, top + row_h * max(1, len(top_tracks)) + 70)
    plot_w = width - left - right
    parts = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
        f'<text x="24" y="34" font-size="22" fill="#111827">OTY1t tracker timeline: {html_escape(scene)}</text>',
        '<text x="24" y="58" font-size="13" fill="#64748b">ByteTrack ids are optical identity hypotheses only. Runtime source is OTY0 YOLO detections; no SAR, GT, review, final boxes, or annotation proposal.</text>',
        f'<line x1="{left}" y1="{top - 22}" x2="{left + plot_w}" y2="{top - 22}" stroke="#cbd5e1" />',
        f'<text x="{left}" y="{top - 30}" font-size="12" fill="#475569">frame {min_frame}</text>',
        f'<text x="{left + plot_w - 74}" y="{top - 30}" font-size="12" fill="#475569">frame {max_frame}</text>',
    ]
    for index, track in enumerate(top_tracks):
        track_id = str(track.get("tracker_track_id", ""))
        identity = str(track.get("identity_status", ""))
        color = identity_color(identity)
        y = top + index * row_h
        track_rows = sorted(rows_by_track.get(track_id, []), key=lambda row: parse_int(row.get("optical_frame_num")) or 0)
        parts.append(f'<text x="24" y="{y + 4}" font-size="11" fill="#111827">{html_escape(track_id)}</text>')
        parts.append(f'<text x="100" y="{y + 4}" font-size="10" fill="{color}">{html_escape(identity)}</text>')
        if not track_rows:
            continue
        xs = [
            left + ((parse_int(row.get("optical_frame_num")) or min_frame) - min_frame) / span * plot_w
            for row in track_rows
        ]
        parts.append(f'<line x1="{min(xs):.2f}" y1="{y}" x2="{max(xs):.2f}" y2="{y}" stroke="{color}" stroke-width="2" opacity="0.75" />')
        for row, x in zip(track_rows, xs):
            fill = "#f97316" if boolish(row.get("boundary_contact")) else color
            radius = 5 if boolish(row.get("neighbor_ambiguity_proxy")) else 4
            parts.append(f'<circle cx="{x:.2f}" cy="{y}" r="{radius}" fill="{fill}" opacity="0.9" />')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def sample_case_rows(oty1_state_rows: Sequence[Mapping[str, Any]], max_rows_per_tracklet: int) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    for tracklet_id in ("oty1_tracklet_0039", "oty1_tracklet_0045"):
        rows = [
            row
            for row in oty1_state_rows
            if str(row.get("tracklet_candidate_id", "")) == tracklet_id
        ]
        rows = sorted(rows, key=lambda row: (parse_int(row.get("optical_frame_num")) or 0, str(row.get("det_id", ""))))
        if len(rows) <= max_rows_per_tracklet:
            out.extend(rows)
        else:
            step = max(1, len(rows) // max_rows_per_tracklet)
            out.extend(rows[::step][:max_rows_per_tracklet])
    return out


def render_case_0039_0045_svg(
    path: Path,
    oty1_state_rows: Sequence[Mapping[str, Any]],
    assignments: Sequence[Mapping[str, Any]],
    case: Mapping[str, Any],
) -> None:
    det_to_assignment = {
        str(row.get("det_id", "")): row
        for row in assignments
        if str(row.get("det_id", ""))
    }
    rows = sample_case_rows(oty1_state_rows, 6)
    if not rows:
        text = "OTY1 state rows for 0039/0045 were not available."
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="150" font-family="Arial, Helvetica, sans-serif"><rect width="900" height="150" fill="#ffffff"/><text x="24" y="44" font-size="18" fill="#111827">{html_escape(text)}</text><text x="24" y="78" font-size="13" fill="#64748b">confirmed_identity=false; no SAR, GT, final boxes, or fan/range band.</text></svg>\n',
            encoding="utf-8",
        )
        return
    cell_w = 190
    image_w = 166.0
    left = 24
    top = 150
    row_gap = 86
    rows_0039 = [row for row in rows if str(row.get("tracklet_candidate_id", "")) == "oty1_tracklet_0039"]
    rows_0045 = [row for row in rows if str(row.get("tracklet_candidate_id", "")) == "oty1_tracklet_0045"]
    cols = max(1, max(len(rows_0039), len(rows_0045)))
    width = max(1120, left * 2 + cols * cell_w)
    parts = [
        f'<rect x="0" y="0" width="{width}" height="100%" fill="#ffffff" />',
        '<text x="24" y="34" font-size="22" fill="#111827">OTY1t case review: OTY1 0039 and 0045</text>',
        f'<text x="24" y="58" font-size="13" fill="#475569">tracker_connected={str(case.get("tracker_connected", False)).lower()} | confirmed_identity=false | shared_tracker_ids={html_escape(str(case.get("shared_tracker_track_ids", [])))}</text>',
        f'<text x="24" y="80" font-size="12" fill="#64748b">0039 tracker ids={html_escape(str(case.get("track_ids_for_0039", [])))} | 0045 tracker ids={html_escape(str(case.get("track_ids_for_0045", [])))}</text>',
        '<text x="24" y="102" font-size="12" fill="#b45309">Visual review remains required. This is an OTY2 continuity hint only, not confirmed same-target identity.</text>',
        '<text x="24" y="124" font-size="12" fill="#64748b">No SAR alignment, SAR band, SAR GT, SAR evidence, final box, selector, training, or annotation proposal is shown.</text>',
    ]

    def render_row(tracklet_rows: Sequence[Mapping[str, Any]], label: str, y_start: int, color: str) -> int:
        parts.append(f'<text x="{left}" y="{y_start - 18}" font-size="14" fill="#111827">{html_escape(label)}</text>')
        max_h = 0
        for index, row in enumerate(tracklet_rows):
            x0 = left + index * cell_w
            optical_path = str(row.get("optical_path", "") or "")
            frame_w = parse_float(row.get("frame_width")) or 800.0
            frame_h = parse_float(row.get("frame_height")) or 600.0
            display_h = image_w * frame_h / max(frame_w, 1.0)
            max_h = max(max_h, int(display_h))
            scale_x = image_w / max(frame_w, 1.0)
            scale_y = display_h / max(frame_h, 1.0)
            bbox_x1 = parse_float(row.get("bbox_x1")) or 0.0
            bbox_y1 = parse_float(row.get("bbox_y1")) or 0.0
            bbox_w = parse_float(row.get("bbox_width")) or ((parse_float(row.get("bbox_x2")) or bbox_x1) - bbox_x1)
            bbox_h = parse_float(row.get("bbox_height")) or ((parse_float(row.get("bbox_y2")) or bbox_y1) - bbox_y1)
            det_id = str(row.get("det_id", ""))
            assignment = det_to_assignment.get(det_id, {})
            tracker_id = str(assignment.get("tracker_track_id", "") or "unmatched")
            stroke = "#f97316" if boolish(row.get("touch_any")) else color
            if optical_path:
                parts.append(
                    f'<image href="{html_escape(file_uri(optical_path))}" x="{x0}" y="{y_start}" width="{image_w:.2f}" height="{display_h:.2f}" preserveAspectRatio="xMidYMid meet" />'
                )
            else:
                parts.append(f'<rect x="{x0}" y="{y_start}" width="{image_w:.2f}" height="{display_h:.2f}" fill="#f1f5f9" />')
            parts.append(
                f'<rect x="{x0 + bbox_x1 * scale_x:.2f}" y="{y_start + bbox_y1 * scale_y:.2f}" width="{bbox_w * scale_x:.2f}" height="{bbox_h * scale_y:.2f}" fill="none" stroke="{stroke}" stroke-width="3" />'
            )
            conf = parse_float(row.get("confidence"))
            conf_text = f"{conf:.2f}" if conf is not None else ""
            parts.append(f'<text x="{x0}" y="{y_start + display_h + 17:.2f}" font-size="10" fill="#111827">f={html_escape(str(row.get("optical_frame_num", "")))} | {html_escape(det_id)} | conf={conf_text}</text>')
            parts.append(f'<text x="{x0}" y="{y_start + display_h + 33:.2f}" font-size="10" fill="{stroke}">tracker={html_escape(tracker_id)}</text>')
        return max_h + 48

    first_h = render_row(rows_0039, "oty1_tracklet_0039", top, "#2563eb")
    second_y = top + first_h + row_gap
    second_h = render_row(rows_0045, "oty1_tracklet_0045", second_y, "#7c3aed")
    height = second_y + second_h + 36
    parts[0] = f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def write_runtime_boundary(path: Path, detection_table: Path) -> None:
    path.write_text(
        f"""# OTY1t Runtime/Posthoc Boundary

## Runtime Sources

- Raw optical frame inventory for optical frame replay gaps
- OTY0 YOLO detection table: `{detection_table}`
- ByteTrack replay over OTY0 detection-table boxes

## Comparison-Only Sources

OTY1 and OTY1a outputs may be read only for comparison rows and the GM_RM019
0039/0045 review note. They do not change tracker assignment.

## Posthoc-Only Or Forbidden For Runtime Tracking

- review_queue.csv, final_gt_working.csv, SAR GT, SAR evidence, SAR frame image content
- final/manual/oracle/review fields, posthoc IoU, target identity, group ids
- selector, G2, A008, threshold tuning, training signals, annotation proposal labels

Tracker ids are written as `tracker_track_id` and
`optical_identity_hypothesis_id`. They are not confirmed identities.
""",
        encoding="utf-8",
    )


def write_case_review(path: Path, case: Mapping[str, Any], output_svg: Path | None) -> None:
    lines = [
        "# OTY1t GM_RM019 0039/0045 Tracker Review",
        "",
        f"- tracker_connected: `{str(case.get('tracker_connected', False)).lower()}`",
        "- confirmed_identity: `false`",
        f"- track_ids_for_0039: `{case.get('track_ids_for_0039', [])}`",
        f"- track_ids_for_0045: `{case.get('track_ids_for_0045', [])}`",
        f"- shared_tracker_track_ids: `{case.get('shared_tracker_track_ids', [])}`",
        f"- competing_track_or_duplicate_overlap: `{str(case.get('competing_track_or_duplicate_overlap', False)).lower()}`",
        f"- duplicate_overlap_event_count: `{case.get('duplicate_overlap_event_count', 0)}`",
        f"- possible_id_switch_or_fragment_event_count: `{case.get('possible_id_switch_or_fragment_event_count', 0)}`",
        f"- visual_review_required: `{str(case.get('visual_review_required', True)).lower()}`",
        f"- oty2_continuity_hint: `{str(case.get('oty2_continuity_hint', False)).lower()}`",
        "",
        "## Boundary",
        "",
        "This case review uses OTY1/OTY1a only as comparison context. Runtime tracking was built from OTY0 YOLO detections only. The tracker connection is not a same-target proof and must not be treated as a confirmed identity, SAR band, or annotation proposal.",
    ]
    if output_svg is not None:
        lines.extend(["", f"Visualization: `{output_svg}`"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(path: Path, summary: Mapping[str, Any], blockers: Sequence[str]) -> None:
    lines = [
        "# OTY1t Standard MOT Tracker Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Scene: `{summary['scene']}`",
        "",
        "## Runtime Input",
        "",
        f"- OTY0 detection table: `{summary['input_oty0_detection_table']}`",
        f"- tracker: `{summary['tracker_name']}`",
        f"- tracker input mode: `{summary['tracker_input_mode']}`",
        f"- detector source: `{summary['detector_source']}`",
        "- runtime source policy: OTY0 YOLO detections only, plus raw optical frame inventory for replay gaps",
        "",
        "## Results",
        "",
        f"- detection rows in: `{summary['detection_rows_in']}`",
        f"- tracked assignment rows: `{summary['tracked_assignment_rows']}`",
        f"- tracker track count: `{summary['tracker_track_count']}`",
        f"- stable hypotheses: `{summary['stable_hypothesis_count']}`",
        f"- fragmented hypotheses: `{summary['fragmented_hypothesis_count']}`",
        f"- ambiguous hypotheses: `{summary['ambiguous_hypothesis_count']}`",
        f"- short hypotheses: `{summary['short_hypothesis_count']}`",
        f"- possible ID switch events: `{summary['possible_id_switch_count']}`",
        f"- duplicate overlap events: `{summary['duplicate_track_overlap_count']}`",
        f"- lost events: `{summary['lost_event_count']}`",
        f"- reactivated events: `{summary['reactivated_event_count']}`",
        f"- low-score recovery events: `{summary['low_score_recovery_count']}`",
        "",
        "## 0039/0045",
        "",
        f"- tracker connected: `{str(summary['case_0039_0045_tracker_connected']).lower()}`",
        "- confirmed identity: `false`",
        "",
        "## Boundary",
        "",
        "- posthoc sources used for runtime tracking: `false`",
        "- SAR alignment entered: `false`",
        "- SAR band entered: `false`",
        "- SAR GT coverage entered: `false`",
        "- annotation proposal entered: `false`",
        "",
        "OTY1t adds standard MOT tracker-derived optical identity hypotheses and state/event audits. Tracker IDs remain runtime optical hypotheses, not confirmed identities. No SAR alignment, SAR band, SAR GT coverage, SAR evidence sampling, selector, training, or annotation proposal was introduced.",
        "",
        "## Blockers",
        "",
        markdown_list(blockers),
        "",
        "## Next Step",
        "",
        "OTY2 can start as a temporal alignment audit only: optical track/state time must be mapped to SAR high-FPS time without assuming equal frame numbers and before any SAR fan/range band generation.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sample_tracks(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("identity_status", "")) == "tracker_stable_hypothesis",
            -(parse_int(row.get("detection_count")) or 0),
            parse_int(row.get("frame_start")) or 0,
        ),
    )
    return [dict(row) for row in ordered[:max_rows]]


def sample_events(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    priority = {
        "possible_id_switch": 0,
        "duplicate_track_overlap": 1,
        "fragment_bridge": 2,
        "ambiguous_association": 3,
        "track_lost": 4,
        "track_reactivated": 5,
        "low_score_recovery": 6,
    }
    ordered = sorted(
        rows,
        key=lambda row: (
            priority.get(str(row.get("event_type", "")), 99),
            parse_int(row.get("optical_frame_num")) or 0,
            str(row.get("tracker_track_id", "")),
        ),
    )
    return [dict(row) for row in ordered[:max_rows]]


def write_report_samples(
    timestamp: str,
    summary: Mapping[str, Any],
    tracks: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    case: Mapping[str, Any],
    local_case_svg: Path,
    max_sample_rows: int,
) -> dict[str, str]:
    report_dir = REPO_ROOT / "reports" / "oty1t"
    sample_dir = report_dir / "samples"
    sample_viz_dir = sample_dir / "visualizations"
    scene_slug = safe_name(str(summary.get("scene", "")).lower())
    report_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_viz_dir.mkdir(parents=True, exist_ok=True)

    summary_md = report_dir / f"oty1t_tracker_audit_summary_{timestamp}.md"
    summary_json = report_dir / f"oty1t_tracker_audit_summary_{timestamp}.json"
    write_report(summary_md, summary, [] if summary.get("largest_blocker", "").startswith("No hard") else [str(summary.get("largest_blocker", ""))])
    write_json(summary_json, summary)

    scene_tracks = sample_dir / f"oty1t_{scene_slug}_tracker_tracks_sample.csv"
    scene_events = sample_dir / f"oty1t_{scene_slug}_tracker_events_sample.csv"
    write_csv(scene_tracks, sample_tracks(tracks, max_sample_rows), TRACK_FIELDS)
    write_csv(scene_events, sample_events(events, max_sample_rows), EVENT_FIELDS)

    artifacts = {
        "summary_md": str(summary_md),
        "summary_json": str(summary_json),
        "scene_tracks_sample": str(scene_tracks),
        "scene_events_sample": str(scene_events),
    }

    if str(summary.get("scene", "")) == "GM_RM019":
        generic_tracks = sample_dir / "oty1t_tracker_tracks_sample.csv"
        generic_events = sample_dir / "oty1t_tracker_events_sample.csv"
        generic_case = sample_dir / "oty1t_case_0039_0045_tracker_review.md"
        generic_case_svg = sample_viz_dir / "oty1t_case_0039_0045.svg"
        write_csv(generic_tracks, sample_tracks(tracks, max_sample_rows), TRACK_FIELDS)
        write_csv(generic_events, sample_events(events, max_sample_rows), EVENT_FIELDS)
        write_case_review(generic_case, case, generic_case_svg)
        if local_case_svg.exists():
            generic_case_svg.write_text(local_case_svg.read_text(encoding="utf-8"), encoding="utf-8")
        artifacts.update(
            {
                "tracks_sample": str(generic_tracks),
                "events_sample": str(generic_events),
                "case_review": str(generic_case),
                "case_visualization": str(generic_case_svg),
            }
        )
    return artifacts


def blocker_summary(
    args: argparse.Namespace,
    output_dir: Path,
    detection_table: Path | None,
    blockers: Sequence[str],
    dependency_facts: Mapping[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "timestamp": timestamp,
        "scene": args.scene,
        "tracker_name": args.tracker,
        "tracker_input_mode": "detection_table_replay",
        "detector_source": "oty0_yolo_detection_table",
        "input_oty0_detection_table": str(detection_table or ""),
        "output_dir": str(output_dir),
        "detection_rows_in": 0,
        "tracked_assignment_rows": 0,
        "tracker_track_count": 0,
        "stable_hypothesis_count": 0,
        "fragmented_hypothesis_count": 0,
        "ambiguous_hypothesis_count": 0,
        "short_hypothesis_count": 0,
        "possible_id_switch_count": 0,
        "duplicate_track_overlap_count": 0,
        "lost_event_count": 0,
        "reactivated_event_count": 0,
        "low_score_recovery_count": 0,
        "case_0039_0045_tracker_connected": False,
        "case_0039_0045_confirmed_identity": False,
        "posthoc_sources_used_for_runtime_tracking": False,
        "sar_alignment_entered": False,
        "sar_band_entered": False,
        "sar_gt_coverage_entered": False,
        "annotation_proposal_entered": False,
        "tracker_dependency_facts": dict(dependency_facts),
        "largest_blocker": blockers[0] if blockers else "Tracker dependency unavailable.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "oty1t_tracker_detection_assignments.csv", [], ASSIGNMENT_FIELDS)
    write_csv(output_dir / "oty1t_tracker_tracks.csv", [], TRACK_FIELDS)
    write_csv(output_dir / "oty1t_tracker_state_timeseries.csv", [], STATE_FIELDS)
    write_csv(output_dir / "oty1t_tracker_events.csv", [], EVENT_FIELDS)
    write_csv(output_dir / "oty1t_comparison_with_oty1_oty1a.csv", [], COMPARISON_FIELDS)
    write_json(output_dir / "oty1t_summary.json", summary)
    write_report(output_dir / "oty1t_report.md", summary, blockers)
    if detection_table is not None:
        write_runtime_boundary(output_dir / "oty1t_runtime_posthoc_boundary.md", detection_table)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_root) / f"oty1t_tracker_audit_{timestamp}"
    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)

    if args.tracker != "bytetrack":
        raise ValueError("This OTY1t runner currently implements ByteTrack audit only.")

    detection_table: Path | None = None
    blockers: list[str] = []
    dependency_facts = bytetrack_dependency_facts()
    try:
        detection_table = ensure_oty0_detection_table(args)
    except Exception as exc:
        blockers.append(f"OTY0 detection table unavailable: {exc}")
        return blocker_summary(args, output_dir, detection_table, blockers, dependency_facts, timestamp)

    raw_rows = read_csv_rows(detection_table)
    oty0_summary = read_json(detection_table.parent / "oty0_summary.json")
    forbidden_fields = forbidden_input_fields(list(raw_rows[0].keys()) if raw_rows else [])
    if forbidden_fields:
        blockers.append("OTY0 detection table contains forbidden runtime-looking fields: " + ", ".join(forbidden_fields))
    if not raw_rows:
        blockers.append("OTY0 detection table is empty.")
    if not dependency_facts.get("bytetrack_available"):
        blockers.append(
            "ByteTrack dependency unavailable: "
            + str(dependency_facts.get("dependency_error", ""))
            + "; install hint: "
            + str(dependency_facts.get("install_hint", ""))
        )
    if blockers:
        return blocker_summary(args, output_dir, detection_table, blockers, dependency_facts, timestamp)

    frame_sizes = frame_sizes_from_rows(raw_rows)
    detections = normalize_detections(raw_rows, frame_sizes=frame_sizes, scene=args.scene)
    frame_numbers = optical_frame_inventory(raw_rows, oty0_summary)
    config = TrackerAuditConfig(
        tracker_name=args.tracker,
        tracker_input_mode="detection_table_replay",
        detector_source="oty0_yolo_detection_table",
        frame_rate=args.frame_rate,
        track_high_thresh=args.track_high_thresh,
        track_low_thresh=args.track_low_thresh,
        new_track_thresh=args.new_track_thresh,
        track_buffer=args.track_buffer,
        match_thresh=args.match_thresh,
        fuse_score=args.fuse_score,
        neighbor_distance_px=args.neighbor_distance_px,
        contact_margin_px=args.contact_margin_px,
        min_stable_track_length=args.min_stable_track_length,
        short_track_length=args.short_track_length,
        duplicate_iou_threshold=args.duplicate_iou_threshold,
        duplicate_center_distance_px=args.duplicate_center_distance_px,
        possible_switch_gap_frames=args.possible_switch_gap_frames,
        possible_switch_distance_px=args.possible_switch_distance_px,
    )

    assignments, events, dependency_facts = run_bytetrack_detection_table_replay(detections, frame_numbers, config)
    events = sort_events(list(events) + ambiguous_association_events(assignments, config))
    tracks = build_tracker_tracks(assignments, events, config)
    state_rows = build_tracker_state_timeseries(assignments, tracks, config)

    oty1_dir = ensure_optional_output_dir(
        args.oty1_output_dir,
        args.output_root,
        "oty1_optical_tracklet_audit",
        "oty1_summary.json",
        args.scene,
    )
    oty1a_dir = ensure_optional_output_dir(
        args.oty1a_output_dir,
        args.output_root,
        "oty1a_fragment_merge_audit",
        "oty1a_summary.json",
        args.scene,
    )
    oty1_summary = read_json(oty1_dir / "oty1_summary.json") if oty1_dir else {}
    oty1a_summary = read_json(oty1a_dir / "oty1a_summary.json") if oty1a_dir else {}
    oty1_state_rows = read_csv_rows(oty1_dir / "oty1_optical_tracklet_state_timeseries.csv") if oty1_dir else []
    comparison = [build_comparison_row(args.scene, oty1_summary, oty1a_summary, tracks, events)]
    case = (
        case_0039_0045_analysis(assignments, oty1_state_rows, events)
        if args.scene == "GM_RM019" and oty1_state_rows
        else {
            "track_ids_for_0039": [],
            "track_ids_for_0045": [],
            "shared_tracker_track_ids": [],
            "tracker_connected": False,
            "confirmed_identity": False,
            "competing_track_or_duplicate_overlap": False,
            "duplicate_overlap_event_count": 0,
            "possible_id_switch_or_fragment_event_count": 0,
            "visual_review_required": args.scene == "GM_RM019",
            "oty2_continuity_hint": False,
        }
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "oty1t_tracker_detection_assignments.csv", assignments, ASSIGNMENT_FIELDS)
    write_csv(output_dir / "oty1t_tracker_tracks.csv", tracks, TRACK_FIELDS)
    write_csv(output_dir / "oty1t_tracker_state_timeseries.csv", state_rows, STATE_FIELDS)
    write_csv(output_dir / "oty1t_tracker_events.csv", events, EVENT_FIELDS)
    write_csv(output_dir / "oty1t_comparison_with_oty1_oty1a.csv", comparison, COMPARISON_FIELDS)
    write_runtime_boundary(output_dir / "oty1t_runtime_posthoc_boundary.md", detection_table)

    timeline_svg = viz_dir / "oty1t_tracker_timeline.svg"
    case_svg = viz_dir / "oty1t_case_0039_0045.svg"
    render_tracker_timeline_svg(timeline_svg, tracks, state_rows, args.scene, args.max_visual_tracks)
    render_case_0039_0045_svg(case_svg, oty1_state_rows, assignments, case)
    write_case_review(output_dir / "oty1t_case_0039_0045_tracker_review.md", case, case_svg)

    hard_blockers: list[str] = []
    if not detections:
        hard_blockers.append("No usable OTY0 YOLO detections were parsed for the requested scene.")
    if not tracks:
        hard_blockers.append("ByteTrack ran, but no tracker hypotheses were produced.")
    if oty1_dir is None:
        hard_blockers.append("No OTY1 output was available for comparison.")
    if oty1a_dir is None:
        hard_blockers.append("No OTY1a output was available for comparison.")

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "timestamp": timestamp,
        "scene": args.scene,
        "tracker_name": config.tracker_name,
        "tracker_input_mode": config.tracker_input_mode,
        "detector_source": config.detector_source,
        "input_oty0_detection_table": str(detection_table),
        "input_oty1_output_dir_for_comparison": str(oty1_dir or ""),
        "input_oty1a_output_dir_for_comparison": str(oty1a_dir or ""),
        "output_dir": str(output_dir),
        "visualizations_dir": str(viz_dir),
        "detection_rows_in": len(detections),
        "raw_oty0_rows_in": len(raw_rows),
        "optical_frame_inventory_count": len(frame_numbers),
        "tracked_assignment_rows": sum(1 for row in assignments if str(row.get("tracker_track_id", "") or "")),
        "unmatched_detection_rows": sum(1 for row in assignments if boolish(row.get("is_unmatched_detection"))),
        "tracker_track_count": len(tracks),
        "stable_hypothesis_count": count_status(tracks, "identity_status", "tracker_stable_hypothesis"),
        "fragmented_hypothesis_count": count_status(tracks, "identity_status", "tracker_fragmented_hypothesis"),
        "ambiguous_hypothesis_count": count_status(tracks, "identity_status", "tracker_ambiguous_hypothesis"),
        "short_hypothesis_count": count_status(tracks, "identity_status", "tracker_short_hypothesis"),
        "duplicate_overlap_hypothesis_count": count_status(tracks, "identity_status", "tracker_duplicate_overlap_hypothesis"),
        "possible_id_switch_count": count_events(events, "possible_id_switch"),
        "duplicate_track_overlap_count": count_events(events, "duplicate_track_overlap"),
        "ambiguous_association_count": count_events(events, "ambiguous_association"),
        "lost_event_count": count_events(events, "track_lost"),
        "reactivated_event_count": count_events(events, "track_reactivated"),
        "low_score_recovery_count": count_events(events, "low_score_recovery"),
        "case_0039_0045_tracker_connected": bool(case.get("tracker_connected", False)),
        "case_0039_0045_confirmed_identity": False,
        "case_0039_0045": dict(case),
        "posthoc_sources_used_for_runtime_tracking": False,
        "sar_alignment_entered": False,
        "sar_band_entered": False,
        "sar_gt_coverage_entered": False,
        "annotation_proposal_entered": False,
        "selector_g2_a008_threshold_training_entered": False,
        "identity_truth_claimed": False,
        "tracker_dependency_facts": dict(dependency_facts),
        "largest_blocker": hard_blockers[0] if hard_blockers else "No hard OTY1t blocker; tracker ids remain optical hypotheses only.",
        "oty2_recommendation": "GO for OTY2 temporal alignment audit only; do not generate SAR band before high-FPS optical-to-SAR time mapping is audited.",
        "audit_config": {
            "frame_rate": config.frame_rate,
            "track_high_thresh": config.track_high_thresh,
            "track_low_thresh": config.track_low_thresh,
            "new_track_thresh": config.new_track_thresh,
            "track_buffer": config.track_buffer,
            "match_thresh": config.match_thresh,
            "fuse_score": config.fuse_score,
            "neighbor_distance_px": config.neighbor_distance_px,
            "contact_margin_px": config.contact_margin_px,
            "min_stable_track_length": config.min_stable_track_length,
            "short_track_length": config.short_track_length,
            "duplicate_iou_threshold": config.duplicate_iou_threshold,
            "duplicate_center_distance_px": config.duplicate_center_distance_px,
            "possible_switch_gap_frames": config.possible_switch_gap_frames,
            "possible_switch_distance_px": config.possible_switch_distance_px,
        },
        "artifacts": {
            "assignments": str(output_dir / "oty1t_tracker_detection_assignments.csv"),
            "tracks": str(output_dir / "oty1t_tracker_tracks.csv"),
            "state_timeseries": str(output_dir / "oty1t_tracker_state_timeseries.csv"),
            "events": str(output_dir / "oty1t_tracker_events.csv"),
            "comparison": str(output_dir / "oty1t_comparison_with_oty1_oty1a.csv"),
            "case_review": str(output_dir / "oty1t_case_0039_0045_tracker_review.md"),
            "summary": str(output_dir / "oty1t_summary.json"),
            "report": str(output_dir / "oty1t_report.md"),
            "timeline": str(timeline_svg),
            "case_visualization": str(case_svg),
            "runtime_posthoc_boundary": str(output_dir / "oty1t_runtime_posthoc_boundary.md"),
        },
    }
    write_json(output_dir / "oty1t_summary.json", summary)
    write_report(output_dir / "oty1t_report.md", summary, hard_blockers)
    report_artifacts = write_report_samples(
        timestamp,
        summary,
        tracks,
        events,
        case,
        case_svg,
        args.max_sample_rows,
    )
    summary["reports_artifacts"] = report_artifacts
    write_json(output_dir / "oty1t_summary.json", summary)
    write_json(REPO_ROOT / "reports" / "oty1t" / f"oty1t_tracker_audit_summary_{timestamp}.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--tracker", default="bytetrack", choices=["bytetrack"])
    parser.add_argument("--oty0-detection-table", default="")
    parser.add_argument("--oty1-output-dir", default="")
    parser.add_argument("--oty1a-output-dir", default="")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--run-oty0-if-missing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--frame-rate", type=int, default=30)
    parser.add_argument("--track-high-thresh", type=float, default=0.25)
    parser.add_argument("--track-low-thresh", type=float, default=0.10)
    parser.add_argument("--new-track-thresh", type=float, default=0.25)
    parser.add_argument("--track-buffer", type=int, default=30)
    parser.add_argument("--match-thresh", type=float, default=0.80)
    parser.add_argument("--fuse-score", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--neighbor-distance-px", type=float, default=120.0)
    parser.add_argument("--contact-margin-px", type=float, default=2.0)
    parser.add_argument("--min-stable-track-length", type=int, default=8)
    parser.add_argument("--short-track-length", type=int, default=3)
    parser.add_argument("--duplicate-iou-threshold", type=float, default=0.50)
    parser.add_argument("--duplicate-center-distance-px", type=float, default=80.0)
    parser.add_argument("--possible-switch-gap-frames", type=int, default=4)
    parser.add_argument("--possible-switch-distance-px", type=float, default=140.0)
    parser.add_argument("--max-visual-tracks", type=int, default=80)
    parser.add_argument("--max-sample-rows", type=int, default=80)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
