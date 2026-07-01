"""Run OTY0 YOLO-first optical detection stream audit.

OTY0 starts from raw optical frames and a local YOLO model. Existing review
queues, final boxes, SAR GT, and manual labels are inventoried as posthoc-only
sources and are never used to generate runtime detections.
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
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
RUNTIME_DETECTION_FIELDS = [
    "scene",
    "optical_frame_num",
    "optical_path",
    "det_id",
    "class_id",
    "class_name",
    "confidence",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "bbox_cx",
    "bbox_cy",
    "bbox_w",
    "bbox_h",
]


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if not _is_duplicate_header_row(row)]


def _is_duplicate_header_row(row: dict[str, str]) -> bool:
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


def parse_int(value: Any) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def path_exists(value: str | Path | None) -> bool:
    return bool(value and Path(str(value)).exists())


def frame_num_from_path(path: str | Path) -> int | None:
    match = re.search(r"(\d+)", Path(path).stem)
    return int(match.group(1)) if match else None


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


def collect_frames(frames_dir: str | Path, start: int | None, end: int | None) -> list[dict[str, Any]]:
    root = Path(frames_dir)
    if not root.exists():
        return []
    frames: list[dict[str, Any]] = []
    for item in sorted(root.iterdir(), key=lambda p: p.name):
        if not item.is_file() or item.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        frame_num = frame_num_from_path(item)
        if frame_num is None:
            continue
        if start is not None and frame_num < start:
            continue
        if end is not None and frame_num > end:
            continue
        size = png_size(item)
        frames.append(
            {
                "optical_frame_num": frame_num,
                "optical_path": str(item),
                "exists": True,
                "image_width": size[0] if size else "",
                "image_height": size[1] if size else "",
                "image_size_status": "read_from_png" if size else "missing_or_non_png_size",
            }
        )
    return frames


def count_files(path: str | Path, suffixes: set[str]) -> int:
    root = Path(path)
    if not root.exists():
        return 0
    return sum(1 for item in root.iterdir() if item.is_file() and item.suffix.lower() in suffixes)


def select_model_path(config: dict[str, Any], manifest_row: dict[str, str]) -> str:
    candidates = [
        manifest_row.get("yolo_model_path", ""),
        config.get("yolo", {}).get("preferred_model_path", ""),
        *config.get("yolo", {}).get("fallback_model_paths", []),
    ]
    for candidate in candidates:
        if candidate and Path(str(candidate)).exists():
            return str(candidate)
    return str(candidates[0] if candidates else "")


def probe_dependencies(model_path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    facts: dict[str, Any] = {
        "ultralytics_available": False,
        "torch_available": False,
        "cuda_available": False,
        "cuda_device_name": "",
        "model_exists": Path(model_path).exists() if model_path else False,
        "yolo_can_run": False,
    }
    rows.append({"component": "python", "status": "available", "detail": sys.executable})
    rows.append({"component": "yolo_model_path", "status": str(facts["model_exists"]).lower(), "detail": model_path})
    try:
        import ultralytics  # type: ignore

        facts["ultralytics_available"] = True
        rows.append({"component": "ultralytics", "status": "available", "detail": getattr(ultralytics, "__version__", "")})
    except Exception as exc:
        rows.append({"component": "ultralytics", "status": "missing", "detail": repr(exc)})
    try:
        import torch  # type: ignore

        facts["torch_available"] = True
        facts["cuda_available"] = bool(torch.cuda.is_available())
        facts["cuda_device_name"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
        rows.append({"component": "torch", "status": "available", "detail": getattr(torch, "__version__", "")})
        rows.append(
            {
                "component": "cuda",
                "status": str(facts["cuda_available"]).lower(),
                "detail": facts["cuda_device_name"],
            }
        )
    except Exception as exc:
        rows.append({"component": "torch", "status": "missing", "detail": repr(exc)})
    facts["yolo_can_run"] = bool(
        facts["ultralytics_available"] and facts["torch_available"] and facts["model_exists"]
    )
    rows.append({"component": "oty0_yolo_can_run", "status": str(facts["yolo_can_run"]).lower(), "detail": ""})
    return rows, facts


def derive_class_ids(model_names: dict[int, str], config: dict[str, Any]) -> tuple[list[int], set[str]]:
    filter_cfg = config.get("yolo", {}).get("yolo_class_filter", {})
    requested_names = {str(name).lower() for name in filter_cfg.get("class_names", [])}
    requested_ids = {int(value) for value in filter_cfg.get("class_ids", []) if str(value) != ""}
    aliases = {"vehicle": {"car", "truck", "bus", "motorcycle"}}
    expanded = set(requested_names)
    for name in requested_names:
        expanded.update(aliases.get(name, set()))
    class_ids = set(requested_ids)
    for class_id, name in model_names.items():
        if str(name).lower() in expanded:
            class_ids.add(int(class_id))
    return sorted(class_ids), expanded


def run_yolo(
    frames: list[dict[str, Any]],
    scene: str,
    model_path: str,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from ultralytics import YOLO  # type: ignore

    yolo_cfg = config.get("yolo", {})
    model = YOLO(model_path)
    names_raw = getattr(model, "names", {})
    model_names = {int(key): str(value) for key, value in dict(names_raw).items()}
    class_ids, class_names_filter = derive_class_ids(model_names, config)
    conf = float(yolo_cfg.get("confidence_threshold_for_detection_audit", 0.25))
    imgsz = int(yolo_cfg.get("imgsz", 960))
    batch_size = int(yolo_cfg.get("batch_size", 16))
    device_value = str(yolo_cfg.get("device", "auto"))
    device = None if device_value == "auto" else device_value

    detections: list[dict[str, Any]] = []
    frame_by_path = {str(row["optical_path"]): row for row in frames}
    frame_paths = list(frame_by_path.keys())
    for start in range(0, len(frame_paths), batch_size):
        batch = frame_paths[start : start + batch_size]
        kwargs: dict[str, Any] = {
            "source": batch,
            "imgsz": imgsz,
            "conf": conf,
            "save": False,
            "verbose": False,
            "stream": False,
        }
        if class_ids:
            kwargs["classes"] = class_ids
        if device is not None:
            kwargs["device"] = device
        results = model.predict(**kwargs)
        for result_index, result in enumerate(results):
            source_path = batch[result_index] if result_index < len(batch) else str(result.path)
            result_path = str(Path(source_path))
            frame = frame_by_path.get(result_path)
            if frame is None:
                frame = frame_by_path.get(str(Path(result_path).resolve()), {})
            frame_num = frame.get("optical_frame_num", frame_num_from_path(result_path))
            boxes = getattr(result, "boxes", None)
            if boxes is None or len(boxes) == 0:
                continue
            xyxy = boxes.xyxy.detach().cpu().tolist()
            confs = boxes.conf.detach().cpu().tolist()
            classes = boxes.cls.detach().cpu().tolist()
            det_index = 0
            for box, confidence, class_value in zip(xyxy, confs, classes):
                class_id = int(class_value)
                class_name = model_names.get(class_id, str(class_id))
                if class_ids and class_id not in class_ids:
                    continue
                if not class_ids and class_names_filter and class_name.lower() not in class_names_filter:
                    continue
                x1, y1, x2, y2 = [float(value) for value in box]
                det_index += 1
                width = max(0.0, x2 - x1)
                height = max(0.0, y2 - y1)
                detections.append(
                    {
                        "scene": scene,
                        "optical_frame_num": frame_num,
                        "optical_path": result_path,
                        "det_id": f"{scene}_{int(frame_num):06d}_{det_index:03d}" if frame_num is not None else f"{scene}_unknown_{len(detections) + 1:06d}",
                        "class_id": class_id,
                        "class_name": class_name,
                        "confidence": float(confidence),
                        "bbox_x1": x1,
                        "bbox_y1": y1,
                        "bbox_x2": x2,
                        "bbox_y2": y2,
                        "bbox_cx": (x1 + x2) / 2.0,
                        "bbox_cy": (y1 + y2) / 2.0,
                        "bbox_w": width,
                        "bbox_h": height,
                    }
                )
    meta = {
        "model_names": model_names,
        "class_ids": class_ids,
        "class_name_filter": sorted(class_names_filter),
        "confidence_threshold_for_detection_audit": conf,
        "imgsz": imgsz,
        "batch_size": batch_size,
        "device": device_value,
    }
    return detections, meta


def inventory_posthoc_sources(manifest_row: dict[str, str], scene: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name, path_key, policy in (
        ("review_queue", "posthoc_review_queue_csv", "posthoc_audit_only_not_runtime_detection_source"),
        ("final_gt_working", "posthoc_final_gt_csv", "posthoc_gt_only_not_runtime_detection_source"),
    ):
        path = manifest_row.get(path_key, "")
        row_count = ""
        scene_rows = ""
        if path and Path(path).exists():
            try:
                raw = read_csv_rows(path)
                row_count = len(raw)
                scene_rows = sum(1 for item in raw if item.get("scene") == scene)
            except Exception as exc:
                row_count = f"read_error:{exc!r}"
        rows.append(
            {
                "source_name": source_name,
                "path": path,
                "exists": path_exists(path),
                "row_count": row_count,
                "scene_rows": scene_rows,
                "use_policy": policy,
                "runtime_detection_source": False,
            }
        )
    return rows


def detection_schema() -> dict[str, Any]:
    return {
        "schema_name": "oty0_yolo_detection_table",
        "runtime_source": "YOLO detections from raw optical frames",
        "forbidden_sources": [
            "review_queue bbox columns",
            "final_gt_working final boxes",
            "SAR GT",
            "manual/review/oracle labels",
        ],
        "fields": {
            "scene": "scene id",
            "optical_frame_num": "numeric frame id parsed from optical frame filename",
            "optical_path": "source optical frame path",
            "det_id": "detector-row id assigned by OTY0",
            "class_id": "YOLO class id",
            "class_name": "YOLO class name",
            "confidence": "YOLO detector confidence, used only as optical detector output filter",
            "bbox_x1": "left image coordinate",
            "bbox_y1": "top image coordinate",
            "bbox_x2": "right image coordinate",
            "bbox_y2": "bottom image coordinate",
            "bbox_cx": "bbox center x",
            "bbox_cy": "bbox center y",
            "bbox_w": "bbox width",
            "bbox_h": "bbox height",
        },
    }


def write_boundary_doc(path: Path) -> None:
    path.write_text(
        """# OTY0 Runtime/Posthoc Boundary

## Runtime Source

OTY0 runtime detections come only from YOLO inference over raw optical frames.

Allowed runtime fields:

- scene
- optical frame number and path
- YOLO detector id
- YOLO class id/name
- YOLO confidence
- YOLO bbox geometry

## Posthoc Sources

`review_queue.csv`, `final_gt_working.csv`, SAR GT, final boxes, manual labels, oracle labels, and review metadata are posthoc/audit-only. OTY0 may count them in inventories, but it cannot use them to generate detections.

## Explicit Non-Goals

OTY0 does not perform tracking, SAR band transfer, SAR GT coverage, selector, G2, A008 scoring, annotation proposal, threshold tuning, or training.

YOLO confidence is an optical detector output filter for this audit. It is not a SAR selector threshold.
""",
        encoding="utf-8",
    )


def render_detection_count_svg(path: Path, frames: list[dict[str, Any]], detections: list[dict[str, Any]]) -> None:
    counts: dict[int, int] = {}
    for det in detections:
        frame_num = parse_int(det.get("optical_frame_num"))
        if frame_num is not None:
            counts[frame_num] = counts.get(frame_num, 0) + 1
    frame_nums = [int(row["optical_frame_num"]) for row in frames]
    if not frame_nums:
        frame_nums = sorted(counts)
    min_frame = min(frame_nums) if frame_nums else 0
    max_frame = max(frame_nums) if frame_nums else 1
    max_count = max(counts.values(), default=1)
    width = 1080
    height = 360
    left = 60
    top = 45
    plot_w = 960
    plot_h = 240

    def scale_x(frame: int) -> float:
        if max_frame == min_frame:
            return left
        return left + (frame - min_frame) * plot_w / (max_frame - min_frame)

    def scale_y(count: int) -> float:
        return top + plot_h - count * plot_h / max_count

    points = " ".join(f"{scale_x(frame):.2f},{scale_y(counts.get(frame, 0)):.2f}" for frame in frame_nums)
    bars = []
    bar_w = max(1.0, plot_w / max(1, len(frame_nums)) * 0.7)
    for frame in frame_nums:
        count = counts.get(frame, 0)
        x = scale_x(frame) - bar_w / 2.0
        y = scale_y(count)
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{top + plot_h - y:.2f}" fill="#0f766e" opacity="0.45" />'
        )
    body = f"""
<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />
<text x="40" y="30" font-size="22" fill="#111827">OTY0 YOLO detection count over optical frames</text>
<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#475569" />
<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#475569" />
<text x="{left}" y="{top + plot_h + 28}" font-size="13" fill="#475569">frame {min_frame}</text>
<text x="{left + plot_w - 70}" y="{top + plot_h + 28}" font-size="13" fill="#475569">frame {max_frame}</text>
<text x="12" y="{top + 10}" font-size="13" fill="#475569">max {max_count}</text>
{''.join(bars)}
<polyline points="{points}" fill="none" stroke="#0f172a" stroke-width="2" />
"""
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="Arial, Helvetica, sans-serif">\n'
        + body
        + "\n</svg>\n",
        encoding="utf-8",
    )


def render_overlay_svg(path: Path, frame: dict[str, Any], detections: list[dict[str, Any]]) -> None:
    image_width = parse_float(frame.get("image_width")) or 800.0
    image_height = parse_float(frame.get("image_height")) or 600.0
    display_w = 420.0
    display_h = display_w * image_height / image_width
    scale_x = display_w / image_width
    scale_y = display_h / image_height
    parts = [
        f'<rect x="0" y="0" width="{display_w + 260:.0f}" height="{display_h + 80:.0f}" fill="#ffffff" />',
        f'<text x="16" y="28" font-size="18" fill="#111827">frame {html_escape(str(frame.get("optical_frame_num", "")))}</text>',
        f'<image href="{html_escape(file_uri(frame["optical_path"]))}" x="16" y="45" width="{display_w:.2f}" height="{display_h:.2f}" preserveAspectRatio="xMidYMid meet" />',
    ]
    colors = ["#f97316", "#0ea5e9", "#22c55e", "#a855f7", "#ef4444"]
    for idx, det in enumerate(detections):
        color = colors[idx % len(colors)]
        x = (parse_float(det.get("bbox_x1")) or 0.0) * scale_x + 16
        y = (parse_float(det.get("bbox_y1")) or 0.0) * scale_y + 45
        w = (parse_float(det.get("bbox_w")) or 0.0) * scale_x
        h = (parse_float(det.get("bbox_h")) or 0.0) * scale_y
        label = f"{det.get('class_name','')} {float(det.get('confidence', 0.0)):.2f}"
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" stroke="{color}" stroke-width="3" />')
        parts.append(f'<text x="{x:.2f}" y="{max(58, y - 5):.2f}" font-size="12" fill="{color}">{html_escape(label)}</text>')
        parts.append(f'<text x="{display_w + 44:.2f}" y="{70 + idx * 22:.2f}" font-size="13" fill="#111827">{html_escape(label)} | {html_escape(str(det.get("det_id", "")))}</text>')
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{display_w + 260:.0f}" height="{display_h + 80:.0f}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(parts)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def render_contact_sheet(
    path: Path,
    overlay_paths: list[Path],
    summary: dict[str, Any],
) -> None:
    links = "\n".join(
        f'<a class="card" href="yolo_detection_overlay_samples/{html_escape(item.name)}" target="_blank">{html_escape(item.stem)}</a>'
        for item in overlay_paths
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>OTY0 YOLO Detection Contact Sheet</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #111827; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
    .card {{ display: block; padding: 12px; border: 1px solid #cbd5e1; text-decoration: none; color: #0f172a; background: #f8fafc; }}
    code {{ background: #f1f5f9; padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>OTY0 YOLO Detection Contact Sheet</h1>
  <p>Scene <code>{html_escape(str(summary.get("scene", "")))}</code>, detections <code>{html_escape(str(summary.get("detection_row_count", "")))}</code>. Images are referenced from local frame paths and are not copied.</p>
  <p><a href="detection_count_timeseries.svg">Detection count timeseries</a></p>
  <div class="grid">{links}</div>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def render_blocker_summary(path: Path, blockers: list[str]) -> None:
    items = "\n".join(f"<li>{html_escape(item)}</li>" for item in blockers) or "<li>none</li>"
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><title>OTY0 YOLO Blockers</title></head>
<body>
  <h1>OTY0 YOLO Blockers</h1>
  <ul>{items}</ul>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_report(path: Path, summary: dict[str, Any], blockers: list[str]) -> None:
    blocker_text = "\n".join(f"- {item}" for item in blockers) if blockers else "- none"
    lines = [
        "# OTY0 YOLO-First Optical Detection Stream Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Scene: `{summary['scene']}`",
        "",
        "## Input",
        "",
        f"- optical frames dir: `{summary['optical_frames_dir']}`",
        f"- YOLO model: `{summary['yolo_model_path']}`",
        f"- posthoc review queue: `{summary['posthoc_review_queue_csv']}`",
        f"- posthoc final GT: `{summary['posthoc_final_gt_csv']}`",
        "",
        "## Results",
        "",
        f"- optical frame count: `{summary['optical_frame_count']}`",
        f"- YOLO runnable: `{summary['yolo_can_run']}`",
        f"- detection table generated: `{summary['detection_table_generated']}`",
        f"- detection row count: `{summary['detection_row_count']}`",
        f"- frames with detections: `{summary['frames_with_detections']}`",
        f"- cache used: `{summary['cache_used']}`",
        "",
        "## Boundary Check",
        "",
        "- no formal pipeline modification",
        "- no selector, G2, threshold, A008 scoring, or training",
        "- no tracking, SAR band, SAR GT coverage, or annotation proposal",
        "- existing CSV/SAR GT sources are posthoc inventory only",
        "- no optical/SAR one-to-one frame sync assumed",
        "",
        "## Blockers",
        "",
        blocker_text,
        "",
        "## OTY1 Readiness",
        "",
        summary["oty1_readiness"],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scene_runnability(manifest_rows: list[dict[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in manifest_rows:
        scene = row.get("scene", "")
        frames_ok = path_exists(row.get("optical_frames_dir", ""))
        model_ok = path_exists(row.get("yolo_model_path", ""))
        if frames_ok and model_ok:
            out[scene] = "runnable_if_requested"
        elif frames_ok:
            out[scene] = "blocked_missing_model"
        else:
            out[scene] = "blocked_missing_optical_frames"
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = load_json_config(args.config)
    manifest_rows = read_csv_rows(args.manifest)
    manifest_row = next((row for row in manifest_rows if row.get("scene") == args.scene), None)
    if manifest_row is None:
        raise KeyError(f"scene {args.scene!r} not found in {args.manifest}")

    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_root) / f"oty0_yolo_detection_stream_audit_{timestamp}"
    viz_dir = output_dir / "visualizations"
    overlay_dir = viz_dir / "yolo_detection_overlay_samples"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    scene = args.scene
    start = parse_int(args.frame_range_start) if args.frame_range_start else parse_int(manifest_row.get("frame_range_start"))
    end = parse_int(args.frame_range_end) if args.frame_range_end else parse_int(manifest_row.get("frame_range_end"))
    frames = collect_frames(manifest_row.get("optical_frames_dir", ""), start, end)
    if args.max_frames and args.max_frames > 0:
        frames = frames[: args.max_frames]
    yolo_model_path = select_model_path(config, manifest_row)
    dependency_rows, dependency_facts = probe_dependencies(yolo_model_path)
    posthoc_rows = inventory_posthoc_sources(manifest_row, scene)

    blockers: list[str] = []
    if not frames:
        blockers.append("No optical frames found for the configured scene/range.")
    if not dependency_facts["model_exists"]:
        blockers.append("Configured YOLO model path does not exist.")
    if not dependency_facts["ultralytics_available"]:
        blockers.append("Python ultralytics dependency is unavailable.")
    if not dependency_facts["torch_available"]:
        blockers.append("Python torch dependency is unavailable.")

    cache_used = False
    yolo_meta: dict[str, Any] = {}
    detections: list[dict[str, Any]] = []
    cache_dir = manifest_row.get("yolo_output_dir", "").strip()
    cache_path = Path(cache_dir) / "oty0_yolo_detection_table.csv" if cache_dir else Path("")
    if cache_dir and cache_path.exists():
        detections = read_csv_rows(cache_path)
        cache_used = True
    elif not blockers:
        try:
            detections, yolo_meta = run_yolo(frames, scene, yolo_model_path, config)
        except Exception as exc:
            blockers.append(f"YOLO execution failed: {exc!r}")

    detection_counts: dict[int, int] = {}
    for det in detections:
        frame_num = parse_int(det.get("optical_frame_num"))
        if frame_num is not None:
            detection_counts[frame_num] = detection_counts.get(frame_num, 0) + 1
    frame_inventory = []
    for frame in frames:
        frame_num = int(frame["optical_frame_num"])
        frame_inventory.append(
            {
                "scene": scene,
                "optical_frame_num": frame_num,
                "optical_path": frame["optical_path"],
                "exists": frame["exists"],
                "image_width": frame["image_width"],
                "image_height": frame["image_height"],
                "image_size_status": frame["image_size_status"],
                "detection_count": detection_counts.get(frame_num, 0),
                "runtime_source_policy": "raw_optical_frame_for_yolo_only",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "oty0_optical_frame_inventory.csv", frame_inventory, list(frame_inventory[0].keys()) if frame_inventory else ["scene", "optical_frame_num", "optical_path", "exists", "image_width", "image_height", "image_size_status", "detection_count", "runtime_source_policy"])
    write_csv(output_dir / "oty0_yolo_dependency_audit.csv", dependency_rows, ["component", "status", "detail"])
    write_csv(output_dir / "oty0_posthoc_source_inventory.csv", posthoc_rows, ["source_name", "path", "exists", "row_count", "scene_rows", "use_policy", "runtime_detection_source"])
    write_json(output_dir / "oty0_detection_field_schema.json", detection_schema())
    write_boundary_doc(output_dir / "oty0_runtime_posthoc_boundary.md")

    if detections:
        write_csv(output_dir / "oty0_yolo_detection_table.csv", detections, RUNTIME_DETECTION_FIELDS)
        frame_by_num = {int(frame["optical_frame_num"]): frame for frame in frames}
        detections_by_frame: dict[int, list[dict[str, Any]]] = {}
        for det in detections:
            frame_num = parse_int(det.get("optical_frame_num"))
            if frame_num is not None:
                detections_by_frame.setdefault(frame_num, []).append(det)
        overlay_paths: list[Path] = []
        for frame_num in sorted(detections_by_frame)[:60]:
            frame = frame_by_num.get(frame_num)
            if not frame:
                continue
            overlay_path = overlay_dir / f"{scene}_{frame_num:06d}_yolo_overlay.svg"
            render_overlay_svg(overlay_path, frame, detections_by_frame[frame_num])
            overlay_paths.append(overlay_path)
        render_detection_count_svg(viz_dir / "detection_count_timeseries.svg", frames, detections)
    else:
        (output_dir / "oty0_yolo_blockers.md").write_text(
            "# OTY0 YOLO Blockers\n\n" + "\n".join(f"- {item}" for item in blockers) + "\n",
            encoding="utf-8",
        )
        render_blocker_summary(viz_dir / "yolo_blocker_summary.html", blockers)
        overlay_paths = []

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scene": scene,
        "config": str(Path(args.config)),
        "manifest": str(Path(args.manifest)),
        "output_dir": str(output_dir),
        "optical_frames_dir": manifest_row.get("optical_frames_dir", ""),
        "optical_frame_count": len(frames),
        "yolo_model_path": yolo_model_path,
        "yolo_can_run": bool(dependency_facts["yolo_can_run"] and not any("YOLO execution failed" in item for item in blockers)),
        "cuda_available": dependency_facts["cuda_available"],
        "cuda_device_name": dependency_facts["cuda_device_name"],
        "actual_yolo_device_policy": config.get("yolo", {}).get("device", "auto"),
        "detection_table_generated": bool(detections),
        "detection_row_count": len(detections),
        "frames_with_detections": len(detection_counts),
        "cache_used": cache_used,
        "posthoc_review_queue_csv": manifest_row.get("posthoc_review_queue_csv", ""),
        "posthoc_final_gt_csv": manifest_row.get("posthoc_final_gt_csv", ""),
        "posthoc_sources_used_for_runtime_detection": False,
        "formal_pipeline_modified": False,
        "selector_g2_threshold_training_entered": False,
        "tracking_entered": False,
        "sar_band_entered": False,
        "sar_gt_coverage_entered": False,
        "annotation_proposal_entered": False,
        "alignment_assumption": "alignment_unknown_no_optical_sar_one_to_one_assumption",
        "gmrm011_gmrm017_status": scene_runnability(manifest_rows),
        "largest_blocker": blockers[0] if blockers else "No OTY0 blocker; YOLO detection stream was generated.",
        "oty1_readiness": (
            "GO for OTY1 tracklet construction from YOLO detections only; keep CSV/SAR GT posthoc-only."
            if detections
            else "NO_GO until YOLO detections are generated."
        ),
        "yolo_meta": yolo_meta,
        "artifacts": {
            "frame_inventory": str(output_dir / "oty0_optical_frame_inventory.csv"),
            "dependency_audit": str(output_dir / "oty0_yolo_dependency_audit.csv"),
            "detection_table": str(output_dir / "oty0_yolo_detection_table.csv") if detections else "",
            "blockers": str(output_dir / "oty0_yolo_blockers.md") if not detections else "",
            "schema": str(output_dir / "oty0_detection_field_schema.json"),
            "posthoc_inventory": str(output_dir / "oty0_posthoc_source_inventory.csv"),
            "boundary": str(output_dir / "oty0_runtime_posthoc_boundary.md"),
            "report": str(output_dir / "oty0_report.md"),
        },
    }
    write_json(output_dir / "oty0_summary.json", summary)
    if detections:
        render_contact_sheet(viz_dir / "yolo_detection_contact_sheet.html", overlay_paths, summary)
    write_report(output_dir / "oty0_report.md", summary, blockers)

    workspace_log_dir = Path("D:/profile/research/workspace/logs")
    if workspace_log_dir.exists():
        log_path = workspace_log_dir / f"oty0_yolo_detection_stream_audit_{timestamp}.md"
        log_path.write_text(
            "# OTY0 YOLO Detection Stream Audit Log\n\n"
            f"- repo: `{REPO_ROOT}`\n"
            f"- output: `{output_dir}`\n"
            f"- interpreter: `{sys.executable}`\n"
            f"- yolo_model_path: `{yolo_model_path}`\n"
            "- boundary: raw optical frames -> YOLO detections only; posthoc CSV/GT not used for runtime\n",
            encoding="utf-8",
        )
        summary["workspace_log"] = str(log_path)
        write_json(output_dir / "oty0_summary.json", summary)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/oty_yolo_stream_config.yaml")
    parser.add_argument("--manifest", default="manifests/oty0_yolo_manifest.csv")
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--frame-range-start", default="")
    parser.add_argument("--frame-range-end", default="")
    parser.add_argument("--max-frames", type=int, default=0)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
