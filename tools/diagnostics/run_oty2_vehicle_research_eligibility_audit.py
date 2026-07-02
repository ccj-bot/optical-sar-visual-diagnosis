"""Audit vehicle research eligibility for OTY2 object-level priors.

This diagnostic keeps the current OTY2 boundary intact. It reads optical-side
object streams, YOLO detection metadata, temporal windows, and runtime spatial
prior descriptions. It renders real optical frame pages with object boxes, but
it does not read SAR image content, use SAR GT, generate SAR search regions,
score candidates, train/tune thresholds, make annotation proposals, or claim
identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLE_DIR = REPORT_DIR / "samples" / "vehicle_research_eligibility_visualizations"
OUTPUT_PARENT = REPO_ROOT / "outputs"
DEFAULT_OBJECT_DIR = REPO_ROOT / "outputs" / "oty1t_object_hypothesis_generalization_audit_20260701_231500"

OPTICAL_FPS = 24
SAR_FPS = 50
FPS_RATIO = SAR_FPS / OPTICAL_FPS
DEFAULT_IMAGE_WIDTH = 800
DEFAULT_IMAGE_HEIGHT = 600
ESTIMATED_SAR_SCENE_FRAMES = math.ceil(368 * FPS_RATIO)

VEHICLE_LIKE_CLASSES = {"car", "truck", "bus", "van", "vehicle"}

AUDIT_DEFAULTS = {
    "min_track_frames_for_main_research": 8,
    "short_track_block_frames": 5,
    "unresolved_tiny_area_ratio": 0.0005,
    "far_small_area_ratio": 0.0030,
    "medium_area_ratio": 0.0200,
    "unresolved_tiny_min_dimension_px": 10.0,
    "far_small_width_px": 40.0,
    "far_small_height_px": 30.0,
    "medium_min_dimension_px": 55.0,
    "low_confidence_median": 0.45,
}

BOUNDARY_FLAGS = {
    "sar_image_content_used": False,
    "sar_gt_used": False,
    "sar_spatial_search_region_generated": False,
    "sar_candidate_boxes_generated": False,
    "candidate_box_scoring_used": False,
    "annotation_proposal_generated": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "detection_box_level_merge_reintroduced": False,
    "stronger_yolo_claimed_validated_improvement": False,
    "model_weights_committed_or_generated": False,
}

AUDIT_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "class_name",
    "class_group",
    "is_vehicle_like",
    "bbox_width",
    "bbox_height",
    "bbox_area",
    "bbox_area_ratio",
    "median_bbox_width",
    "median_bbox_height",
    "median_bbox_area",
    "median_bbox_area_ratio",
    "min_bbox_width",
    "max_bbox_width",
    "min_bbox_height",
    "max_bbox_height",
    "min_bbox_area_ratio",
    "max_bbox_area_ratio",
    "visible_frame_count",
    "track_frame_span",
    "optical_start_frame",
    "optical_end_frame",
    "median_confidence",
    "edge_contact",
    "partial_or_occluded",
    "duplicate_or_handoff",
    "ambiguity_status",
    "resolvability_tier",
    "vehicle_research_eligibility",
    "downstream_recommendation",
    "spatial_prior_status",
    "spatial_prior_mode",
    "spatial_prior_vehicle_admission_consistency",
    "sar_start_frame",
    "sar_end_frame",
    "sar_window_frame_count",
    "range_prior_mode",
    "azimuth_prior_available",
    "degradation_reason",
    "notes",
    "local_visualization_path",
    "repo_sample_visualization_path",
]

SUMMARY_VIS_FIELDS = [
    "sample_role",
    "scene",
    "object_hypothesis_id",
    "class_name",
    "resolvability_tier",
    "vehicle_research_eligibility",
    "spatial_prior_status",
    "local_visualization_path",
    "repo_sample_visualization_path",
]


def latest_path(pattern: str, base: Path = REPORT_DIR) -> Path:
    paths = sorted(base.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No file matched {base / pattern}")
    return paths[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_int(value: Any, default: int | None = None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def bool_text(value: Any) -> str:
    return "true" if is_true(value) else "false"


def is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def fmt_num(value: Any, digits: int = 3) -> str:
    numeric = safe_float(value)
    if numeric is None:
        return ""
    return f"{numeric:.{digits}f}"


def median_or_blank(values: Sequence[float], digits: int | None = None) -> float | str:
    if not values:
        return ""
    value = float(median(values))
    if digits is None:
        return value
    return round(value, digits)


def min_or_blank(values: Sequence[float], digits: int | None = None) -> float | str:
    if not values:
        return ""
    value = float(min(values))
    if digits is None:
        return value
    return round(value, digits)


def max_or_blank(values: Sequence[float], digits: int | None = None) -> float | str:
    if not values:
        return ""
    value = float(max(values))
    if digits is None:
        return value
    return round(value, digits)


def mode_or_blank(values: Iterable[str]) -> str:
    cleaned = [str(value).strip() for value in values if str(value or "").strip()]
    if not cleaned:
        return ""
    return Counter(cleaned).most_common(1)[0][0]


def choose_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


FONTS = {
    "title": choose_font(38, True),
    "h1": choose_font(28, True),
    "h2": choose_font(22, True),
    "body": choose_font(19),
    "small": choose_font(16),
    "tiny": choose_font(13),
}


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: Any, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    raw = str(text if text is not None else "")
    if not raw:
        return [""]
    lines: list[str] = []
    for paragraph in raw.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if text_size(draw, candidate, font)[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines or [raw]


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: Any,
    font: ImageFont.ImageFont,
    fill: str,
    max_width: int,
    line_gap: int = 6,
    max_lines: int | None = None,
) -> int:
    x, y = xy
    lines = wrap_text(draw, text, font, max_width)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [lines[max_lines - 1] + "..."]
    cursor = y
    for line in lines:
        draw.text((x, cursor), line, font=font, fill=fill)
        cursor += text_size(draw, line or " ", font)[1] + line_gap
    return cursor


def draw_card(
    draw: ImageDraw.ImageDraw,
    xywh: tuple[int, int, int, int],
    title: str,
    body: Sequence[Any],
    border: str = "#cbd5e1",
    fill: str = "#ffffff",
) -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=fill, outline=border, width=2)
    draw.text((x + 18, y + 14), title, font=FONTS["h2"], fill="#0f172a")
    cursor = y + 50
    for item in body:
        cursor = draw_wrapped(draw, (x + 18, cursor), item, FONTS["small"], "#334155", w - 36, max_lines=4)
        cursor += 5
        if cursor > y + h - 18:
            break


def draw_tag(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str) -> int:
    x, y = xy
    pad_x = 14
    pad_y = 7
    w, h = text_size(draw, text, FONTS["small"])
    draw.rounded_rectangle((x, y, x + w + pad_x * 2, y + h + pad_y * 2), radius=13, fill=fill)
    draw.text((x + pad_x, y + pad_y - 1), text, font=FONTS["small"], fill="#ffffff")
    return x + w + pad_x * 2 + 10


def parse_secondary_boxes(text: str) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for part in str(text or "").split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        det_id, coords = part.split(":", 1)
        values = [safe_float(value) for value in coords.split(",")]
        if len(values) >= 4 and all(value is not None for value in values[:4]):
            boxes.append(
                {
                    "det_id": det_id,
                    "bbox": (float(values[0]), float(values[1]), float(values[2]), float(values[3])),
                }
            )
    return boxes


def primary_box(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    values = [
        safe_float(row.get("primary_bbox_x1")),
        safe_float(row.get("primary_bbox_y1")),
        safe_float(row.get("primary_bbox_x2")),
        safe_float(row.get("primary_bbox_y2")),
    ]
    if all(value is not None for value in values):
        x1, y1, x2, y2 = [float(value) for value in values]
        if x2 > x1 and y2 > y1:
            return x1, y1, x2, y2
    return None


def parse_azimuth(text: str) -> dict[str, float | str]:
    center_match = re.search(r"center_deg=([-+]?\d+(?:\.\d+)?)", text or "")
    interval_match = re.search(r"interval_deg=\[([-+]?\d+(?:\.\d+)?),([-+]?\d+(?:\.\d+)?)\]", text or "")
    margin_match = re.search(r"margin_deg=([-+]?\d+(?:\.\d+)?)", text or "")
    start = safe_float(interval_match.group(1)) if interval_match else None
    end = safe_float(interval_match.group(2)) if interval_match else None
    center = safe_float(center_match.group(1)) if center_match else None
    margin = safe_float(margin_match.group(1)) if margin_match else None
    width = None if start is None or end is None else max(0.0, end - start)
    return {
        "center": "" if center is None else center,
        "start": "" if start is None else start,
        "end": "" if end is None else end,
        "width": "" if width is None else width,
        "margin": "" if margin is None else margin,
    }


def object_short_id(object_id: str) -> str:
    if not object_id:
        return "scene_only"
    match = re.search(r"bt_\d+", object_id)
    return match.group(0) if match else object_id[-20:]


def file_token(scene: str, object_id: str) -> str:
    return f"{scene.lower()}_{object_short_id(object_id).replace('_', '')}"


def load_frame_paths(manifest_csv: Path) -> tuple[dict[tuple[str, int], Path], dict[str, Path], dict[tuple[str, int], tuple[int, int]]]:
    paths: dict[tuple[str, int], Path] = {}
    dims: dict[tuple[str, int], tuple[int, int]] = {}
    frame_dirs: dict[str, Path] = {}
    for inventory in sorted((REPO_ROOT / "outputs").glob("oty0_yolo_detection_stream_audit_*/oty0_optical_frame_inventory.csv")):
        for row in read_csv(inventory):
            scene = str(row.get("scene", ""))
            frame = safe_int(row.get("optical_frame_num"))
            path = Path(str(row.get("optical_path", "")))
            width = safe_int(row.get("image_width"))
            height = safe_int(row.get("image_height"))
            if scene and frame is not None and path.exists():
                paths[(scene, frame)] = path
            if scene and frame is not None and width and height:
                dims[(scene, frame)] = (width, height)
    if manifest_csv.exists():
        for row in read_csv(manifest_csv):
            scene = str(row.get("scene", ""))
            frame_dir = Path(str(row.get("optical_frames_dir", "")))
            if scene and frame_dir.exists():
                frame_dirs[scene] = frame_dir
    return paths, frame_dirs, dims


def resolve_frame_path(scene: str, frame: int, frame_paths: Mapping[tuple[str, int], Path], frame_dirs: Mapping[str, Path]) -> Path | None:
    direct = frame_paths.get((scene, frame))
    if direct and direct.exists():
        return direct
    frame_dir = frame_dirs.get(scene)
    if frame_dir:
        for suffix in (".png", ".jpg", ".jpeg"):
            candidate = frame_dir / f"{frame:06d}{suffix}"
            if candidate.exists():
                return candidate
    return None


def frame_dimensions(
    scene: str,
    frame: int,
    frame_dims: Mapping[tuple[str, int], tuple[int, int]],
    frame_paths: Mapping[tuple[str, int], Path],
    frame_dirs: Mapping[str, Path],
) -> tuple[int, int]:
    dim = frame_dims.get((scene, frame))
    if dim:
        return dim
    path = resolve_frame_path(scene, frame, frame_paths, frame_dirs)
    if path and path.exists():
        try:
            with Image.open(path) as image:
                return image.width, image.height
        except OSError:
            pass
    return DEFAULT_IMAGE_WIDTH, DEFAULT_IMAGE_HEIGHT


def load_yolo_detections() -> tuple[dict[tuple[str, str], dict[str, str]], Counter[str]]:
    detections: dict[tuple[str, str], dict[str, str]] = {}
    class_counter: Counter[str] = Counter()
    for table in sorted((REPO_ROOT / "outputs").glob("oty0_yolo_detection_stream_audit_*/oty0_yolo_detection_table.csv")):
        for row in read_csv(table):
            scene = str(row.get("scene", ""))
            det_id = str(row.get("det_id", ""))
            if scene and det_id:
                detections[(scene, det_id)] = row
                class_counter[f"{scene}:{row.get('class_name', '')}"] += 1
    return detections, class_counter


def group_by_object(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        scene = str(row.get("scene", ""))
        object_id = str(row.get("object_hypothesis_id", ""))
        if scene and object_id:
            grouped[(scene, object_id)].append(dict(row))
    for object_rows in grouped.values():
        object_rows.sort(key=lambda item: safe_int(item.get("optical_frame_num"), 0) or 0)
    return grouped


def rows_by_key(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))): dict(row) for row in rows}


def state_present(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text and text not in {"none", "false", "0", "single_observation", "visible_main_observation", "low_uncertainty"})


def choose_frame_rows(object_rows: Sequence[Mapping[str, str]]) -> list[Mapping[str, str]]:
    rows = [row for row in object_rows if safe_int(row.get("optical_frame_num")) is not None]
    rows = sorted(rows, key=lambda row: safe_int(row.get("optical_frame_num"), 0) or 0)
    if not rows:
        return []
    indices = [0, len(rows) // 2, len(rows) - 1]
    selected: list[Mapping[str, str]] = []
    for idx in indices:
        row = rows[idx]
        if row not in selected:
            selected.append(row)
    return selected


def scene_only_frame_rows(scene: str, frame_paths: Mapping[tuple[str, int], Path], frame_dirs: Mapping[str, Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for frame in (0, 183, 367):
        if resolve_frame_path(scene, frame, frame_paths, frame_dirs):
            rows.append({"scene": scene, "optical_frame_num": str(frame)})
    return rows


def class_group(class_name: str, is_vehicle: bool) -> str:
    if not class_name:
        return "unknown_class_from_object_stream"
    if is_vehicle:
        return f"vehicle_like:{class_name}"
    return f"non_vehicle_or_irrelevant:{class_name}"


def object_bbox_stats(
    scene: str,
    object_rows: Sequence[Mapping[str, str]],
    detections: Mapping[tuple[str, str], Mapping[str, str]],
    frame_paths: Mapping[tuple[str, int], Path],
    frame_dirs: Mapping[str, Path],
    frame_dims: Mapping[tuple[str, int], tuple[int, int]],
) -> dict[str, Any]:
    widths: list[float] = []
    heights: list[float] = []
    areas: list[float] = []
    area_ratios: list[float] = []
    confidences: list[float] = []
    classes: list[str] = []
    edge_hits = 0
    partial_hits = 0
    multi_obs_hits = 0
    uncertainty_hits = 0

    for row in object_rows:
        frame = safe_int(row.get("optical_frame_num"))
        if frame is None:
            continue
        width = safe_float(row.get("primary_bbox_w"))
        height = safe_float(row.get("primary_bbox_h"))
        confidence = safe_float(row.get("primary_confidence"))
        box = primary_box(row)
        image_w, image_h = frame_dimensions(scene, frame, frame_dims, frame_paths, frame_dirs)
        if width is not None and height is not None:
            widths.append(width)
            heights.append(height)
            area = width * height
            areas.append(area)
            area_ratios.append(area / max(1, image_w * image_h))
        if confidence is not None:
            confidences.append(confidence)
        det_id = str(row.get("primary_det_id", ""))
        det = detections.get((scene, det_id))
        if det:
            classes.append(str(det.get("class_name", "")).strip())
        if box:
            x1, y1, x2, y2 = box
            if x1 <= 2 or y1 <= 2 or x2 >= image_w - 2 or y2 >= image_h - 2:
                edge_hits += 1
        if state_present(row.get("boundary_truncation_state")):
            edge_hits += 1
        if state_present(row.get("partial_full_transition_state")):
            partial_hits += 1
        if state_present(row.get("multi_observation_state")):
            multi_obs_hits += 1
        if str(row.get("state_uncertainty_status", "")).strip() in {"moderate_uncertainty", "high_uncertainty"}:
            uncertainty_hits += 1

    frames = [safe_int(row.get("optical_frame_num")) for row in object_rows]
    frames = [frame for frame in frames if frame is not None]
    class_name = mode_or_blank(classes)
    is_vehicle = class_name.lower() in VEHICLE_LIKE_CLASSES if class_name else False
    return {
        "class_name": class_name,
        "class_group": class_group(class_name, is_vehicle),
        "is_vehicle_like": bool_text(is_vehicle),
        "bbox_width": fmt_num(median_or_blank(widths), 3) if widths else "",
        "bbox_height": fmt_num(median_or_blank(heights), 3) if heights else "",
        "bbox_area": fmt_num(median_or_blank(areas), 3) if areas else "",
        "bbox_area_ratio": fmt_num(median_or_blank(area_ratios), 6) if area_ratios else "",
        "median_bbox_width": fmt_num(median_or_blank(widths), 3) if widths else "",
        "median_bbox_height": fmt_num(median_or_blank(heights), 3) if heights else "",
        "median_bbox_area": fmt_num(median_or_blank(areas), 3) if areas else "",
        "median_bbox_area_ratio": fmt_num(median_or_blank(area_ratios), 6) if area_ratios else "",
        "min_bbox_width": fmt_num(min_or_blank(widths), 3) if widths else "",
        "max_bbox_width": fmt_num(max_or_blank(widths), 3) if widths else "",
        "min_bbox_height": fmt_num(min_or_blank(heights), 3) if heights else "",
        "max_bbox_height": fmt_num(max_or_blank(heights), 3) if heights else "",
        "min_bbox_area_ratio": fmt_num(min_or_blank(area_ratios), 6) if area_ratios else "",
        "max_bbox_area_ratio": fmt_num(max_or_blank(area_ratios), 6) if area_ratios else "",
        "visible_frame_count": str(len(object_rows)),
        "track_frame_span": str(max(frames) - min(frames) + 1) if frames else "",
        "optical_start_frame": str(min(frames)) if frames else "",
        "optical_end_frame": str(max(frames)) if frames else "",
        "median_confidence": fmt_num(median_or_blank(confidences), 6) if confidences else "",
        "edge_contact": bool_text(edge_hits > 0),
        "partial_or_occluded": bool_text(partial_hits > 0),
        "duplicate_or_handoff_from_frame_state": bool_text(multi_obs_hits > 0),
        "uncertainty_from_frame_state": bool_text(uncertainty_hits > 0),
    }


def resolvability_tier(stats: Mapping[str, Any], spatial_row: Mapping[str, str]) -> str:
    if not stats.get("visible_frame_count"):
        return "no_object_flow"
    if not is_true(stats.get("is_vehicle_like")):
        return "non_vehicle_or_irrelevant"

    visible = safe_int(stats.get("visible_frame_count"), 0) or 0
    area_ratio = safe_float(stats.get("median_bbox_area_ratio"), 0.0) or 0.0
    med_width = safe_float(stats.get("median_bbox_width"), 0.0) or 0.0
    med_height = safe_float(stats.get("median_bbox_height"), 0.0) or 0.0
    med_conf = safe_float(stats.get("median_confidence"), 0.0) or 0.0
    spatial_status = str(spatial_row.get("spatial_prior_status", ""))

    if spatial_status.startswith("blocked") or visible < AUDIT_DEFAULTS["short_track_block_frames"]:
        return "blocked_noise_or_short_track"
    if (
        area_ratio < AUDIT_DEFAULTS["unresolved_tiny_area_ratio"]
        or min(med_width, med_height) < AUDIT_DEFAULTS["unresolved_tiny_min_dimension_px"]
    ):
        return "unresolved_tiny_vehicle"
    if (
        area_ratio < AUDIT_DEFAULTS["far_small_area_ratio"]
        or med_width < AUDIT_DEFAULTS["far_small_width_px"]
        or med_height < AUDIT_DEFAULTS["far_small_height_px"]
    ):
        return "low_resolvable_far_vehicle"
    if (
        area_ratio < AUDIT_DEFAULTS["medium_area_ratio"]
        or min(med_width, med_height) < AUDIT_DEFAULTS["medium_min_dimension_px"]
        or med_conf < AUDIT_DEFAULTS["low_confidence_median"]
    ):
        return "medium_resolvable_vehicle"
    return "high_resolvable_vehicle"


def eligibility(
    stats: Mapping[str, Any],
    tier: str,
    spatial_row: Mapping[str, str],
    duplicate_or_handoff: bool,
    ambiguity_status: str,
) -> tuple[str, str]:
    spatial_status = str(spatial_row.get("spatial_prior_status", ""))
    if tier == "no_object_flow":
        return "blocked_no_object_flow", "block_no_object_level_input"
    if tier == "non_vehicle_or_irrelevant":
        return "non_vehicle_excluded", "exclude_from_vehicle_mainline_keep_record"
    if spatial_status.startswith("blocked") or tier == "blocked_noise_or_short_track":
        return "blocked_vehicle_or_noise", "block_from_vehicle_research_flow"
    if tier in {"unresolved_tiny_vehicle", "low_resolvable_far_vehicle"}:
        return "far_small_vehicle_layer", "keep_far_small_layer_not_main_research"
    if spatial_status == "review_only_spatial_context_generated":
        return "review_only_vehicle", "review_only_do_not_use_as_main_input"
    if spatial_status == "loose_spatial_prior_generated" or duplicate_or_handoff:
        return "weak_vehicle_layer", "keep_as_weak_vehicle_review_layer"
    if ambiguity_status == "ambiguous_or_review_required":
        return "review_only_vehicle", "review_only_do_not_use_as_main_input"
    return "main_research_vehicle", "enter_vehicle_main_research_input"


def consistency(spatial_status: str, eligibility_status: str, tier: str) -> str:
    if spatial_status.startswith("blocked") and eligibility_status.startswith("blocked"):
        return "consistent_blocked"
    if spatial_status == "review_only_spatial_context_generated" and eligibility_status == "review_only_vehicle":
        return "consistent_review_only"
    if spatial_status in {"normal_spatial_prior_generated", "loose_spatial_prior_generated"}:
        if eligibility_status == "main_research_vehicle":
            return "consistent_main_vehicle"
        if eligibility_status == "weak_vehicle_layer":
            return "consistent_but_needs_weak_vehicle_layer"
        if eligibility_status == "far_small_vehicle_layer":
            return "spatial_prior_available_but_vehicle_admission_demotes_far_small"
        if eligibility_status.startswith("blocked"):
            return "spatial_prior_available_but_vehicle_admission_blocks"
    if eligibility_status == "non_vehicle_excluded":
        return "vehicle_mainline_excludes_non_vehicle"
    if tier == "no_object_flow":
        return "consistent_no_object_flow"
    return "needs_manual_audit"


def degradation_reason(
    stats: Mapping[str, Any],
    tier: str,
    spatial_row: Mapping[str, str],
    duplicate_or_handoff: bool,
    ambiguity_status: str,
) -> tuple[str, str]:
    reasons: list[str] = []
    notes: list[str] = []
    if tier == "no_object_flow":
        reasons.append("第十一场景时间元数据可用，但缺光学目标流，不能生成对象级车辆准入。")
    if not is_true(stats.get("is_vehicle_like")) and tier != "no_object_flow":
        reasons.append("当前主线只研究 vehicle/car-like；该对象不进入主结果。")
    if tier == "blocked_noise_or_short_track":
        reasons.append("对象被现有空间先验或短轨迹/not-ready 状态阻断。")
    if tier == "unresolved_tiny_vehicle":
        reasons.append("目标框过小，光学侧可解析度不足；保留记录但不进入主研究流。")
    if tier == "low_resolvable_far_vehicle":
        reasons.append("远小车辆：检测存在，但框面积/尺寸低，作为远小车层保留。")
    if tier == "medium_resolvable_vehicle":
        reasons.append("中等可解析车辆：可进入弱车层或主研究候选，但需要状态约束共同判断。")
    if tier == "high_resolvable_vehicle":
        reasons.append("光学上较清晰：如果空间先验和状态稳定，可进入主研究流。")
    if is_true(stats.get("edge_contact")):
        reasons.append("存在边缘接触/截断风险，会扩大或降低空间先验可信度。")
    if is_true(stats.get("partial_or_occluded")):
        reasons.append("存在 partial/遮挡类状态，不直接删除，但需要更保守处理。")
    if duplicate_or_handoff:
        reasons.append("存在 duplicate/handoff/多观测风险，保留弱层或审阅层。")
    if ambiguity_status == "ambiguous_or_review_required":
        reasons.append("对象含混或 upstream 已转为 review-only，不混入正常主结果。")
    if "broad_unknown" in str(spatial_row.get("range_prior_mode", "")):
        notes.append("距离向仍是 broad_unknown_range_prior：时间窗和方位弱约束不能解决距离收敛。")
    notes.append("所有阈值仅为 audit defaults / 建议阈值，不是训练阈值或调参结果。")
    return " | ".join(reasons), " | ".join(notes)


def build_audit_rows(
    spatial_rows: Sequence[Mapping[str, str]],
    temporal_by_key: Mapping[tuple[str, str], Mapping[str, str]],
    object_rows_by_key: Mapping[tuple[str, str], list[dict[str, str]]],
    hypotheses_by_key: Mapping[tuple[str, str], Mapping[str, str]],
    detections: Mapping[tuple[str, str], Mapping[str, str]],
    frame_paths: Mapping[tuple[str, int], Path],
    frame_dirs: Mapping[str, Path],
    frame_dims: Mapping[tuple[str, int], tuple[int, int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spatial in spatial_rows:
        scene = str(spatial.get("scene", ""))
        object_id = str(spatial.get("object_hypothesis_id", ""))
        key = (scene, object_id)
        object_rows = object_rows_by_key.get(key, [])
        temporal = temporal_by_key.get(key, {})
        hypothesis = hypotheses_by_key.get(key, {})
        if object_rows:
            stats = object_bbox_stats(scene, object_rows, detections, frame_paths, frame_dirs, frame_dims)
        else:
            stats = {
                "class_name": "",
                "class_group": "no_object_flow" if str(spatial.get("spatial_prior_status")) == "blocked_missing_object_level_flow" else "unknown_class_from_object_stream",
                "is_vehicle_like": "false",
                "visible_frame_count": "",
                "track_frame_span": "",
                "edge_contact": "false",
                "partial_or_occluded": "false",
                "duplicate_or_handoff_from_frame_state": "false",
                "uncertainty_from_frame_state": "false",
            }
        duplicate_or_handoff = (
            is_true(spatial.get("duplicate_or_handoff_state"))
            or safe_int(hypothesis.get("main_tracker_duplicate_overlap_count"), 0) not in {None, 0}
            or safe_int(hypothesis.get("main_tracker_possible_id_switch_count"), 0) not in {None, 0}
            or is_true(stats.get("duplicate_or_handoff_from_frame_state"))
        )
        ambiguity_status = str(spatial.get("ambiguity_status", "") or "not_ambiguous")
        tier = resolvability_tier(stats, spatial)
        eligibility_status, downstream = eligibility(stats, tier, spatial, duplicate_or_handoff, ambiguity_status)
        reason, notes = degradation_reason(stats, tier, spatial, duplicate_or_handoff, ambiguity_status)
        row: dict[str, Any] = {
            "scene": scene,
            "object_hypothesis_id": object_id,
            **stats,
            "partial_or_occluded": bool_text(is_true(stats.get("partial_or_occluded")) or is_true(spatial.get("edge_or_partial_state"))),
            "duplicate_or_handoff": bool_text(duplicate_or_handoff),
            "ambiguity_status": ambiguity_status,
            "resolvability_tier": tier,
            "vehicle_research_eligibility": eligibility_status,
            "downstream_recommendation": downstream,
            "spatial_prior_status": spatial.get("spatial_prior_status", ""),
            "spatial_prior_mode": spatial.get("spatial_prior_mode", ""),
            "spatial_prior_vehicle_admission_consistency": consistency(str(spatial.get("spatial_prior_status", "")), eligibility_status, tier),
            "sar_start_frame": spatial.get("sar_start_frame") or temporal.get("sar_start_frame", ""),
            "sar_end_frame": spatial.get("sar_end_frame") or temporal.get("sar_end_frame", ""),
            "sar_window_frame_count": temporal.get("sar_window_frame_count", ""),
            "range_prior_mode": spatial.get("range_prior_mode", ""),
            "azimuth_prior_available": spatial.get("azimuth_prior_available", ""),
            "degradation_reason": reason,
            "notes": notes,
        }
        if not row.get("optical_start_frame") and temporal:
            row["optical_start_frame"] = temporal.get("optical_start_frame", "")
        if not row.get("optical_end_frame") and temporal:
            row["optical_end_frame"] = temporal.get("optical_end_frame", "")
        rows.append(row)
    return rows


def tier_cn(tier: str) -> str:
    return {
        "high_resolvable_vehicle": "高清晰车辆",
        "medium_resolvable_vehicle": "中等可解析车辆",
        "low_resolvable_far_vehicle": "远小车辆",
        "unresolved_tiny_vehicle": "极小不可解析车辆",
        "non_vehicle_or_irrelevant": "非车辆/无关",
        "blocked_noise_or_short_track": "阻断/短轨迹/噪声",
        "no_object_flow": "缺目标流",
    }.get(tier, tier)


def eligibility_cn(value: str) -> str:
    return {
        "main_research_vehicle": "主研究车辆",
        "weak_vehicle_layer": "弱车目标层",
        "far_small_vehicle_layer": "远小车辆层",
        "review_only_vehicle": "仅审阅车辆",
        "blocked_vehicle_or_noise": "阻断目标",
        "blocked_no_object_flow": "缺目标流阻断",
        "non_vehicle_excluded": "非车辆排除",
    }.get(value, value)


def spatial_status_cn(value: str) -> str:
    return {
        "normal_spatial_prior_generated": "正常空间先验",
        "loose_spatial_prior_generated": "宽松空间先验",
        "review_only_spatial_context_generated": "仅审阅空间上下文",
        "blocked_no_spatial_prior": "阻断",
        "blocked_missing_object_level_flow": "阻断：缺目标流",
    }.get(value, value)


def eligibility_color(value: str) -> str:
    return {
        "main_research_vehicle": "#2563eb",
        "weak_vehicle_layer": "#0891b2",
        "far_small_vehicle_layer": "#a16207",
        "review_only_vehicle": "#9333ea",
        "blocked_vehicle_or_noise": "#dc2626",
        "blocked_no_object_flow": "#7c3aed",
        "non_vehicle_excluded": "#64748b",
    }.get(value, "#64748b")


def draw_dashed_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, width: int = 4) -> None:
    x1, y1, x2, y2 = box
    dash = 14
    for x in range(x1, x2, dash * 2):
        draw.line((x, y1, min(x + dash, x2), y1), fill=fill, width=width)
        draw.line((x, y2, min(x + dash, x2), y2), fill=fill, width=width)
    for y in range(y1, y2, dash * 2):
        draw.line((x1, y, x1, min(y + dash, y2)), fill=fill, width=width)
        draw.line((x2, y, x2, min(y + dash, y2)), fill=fill, width=width)


def scale_and_draw_frame(source: Image.Image, panel_size: tuple[int, int], frame_row: Mapping[str, Any]) -> tuple[Image.Image, int, int]:
    panel_w, panel_h = panel_size
    image = source.convert("RGB")
    scale = min(panel_w / image.width, panel_h / image.height)
    new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (panel_w, panel_h), "#111827")
    offset_x = (panel_w - new_size[0]) // 2
    offset_y = (panel_h - new_size[1]) // 2
    panel.paste(resized, (offset_x, offset_y))
    draw = ImageDraw.Draw(panel)

    def project(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        return (
            int(offset_x + x1 * scale),
            int(offset_y + y1 * scale),
            int(offset_x + x2 * scale),
            int(offset_y + y2 * scale),
        )

    primary_count = 0
    secondary_count = 0
    pbox = primary_box(frame_row)
    if pbox:
        projected = project(pbox)
        draw.rectangle(projected, outline="#22c55e", width=5)
        draw.text((projected[0] + 6, max(6, projected[1] + 6)), "主观测框", font=FONTS["small"], fill="#22c55e")
        primary_count = 1
    for secondary in parse_secondary_boxes(str(frame_row.get("secondary_bbox_summary", ""))):
        projected = project(secondary["bbox"])
        draw_dashed_box(draw, projected, "#f59e0b", width=4)
        draw.text((projected[0] + 6, max(6, projected[1] + 28)), "辅助观测", font=FONTS["small"], fill="#f59e0b")
        secondary_count += 1
    return panel, primary_count, secondary_count


def draw_timeline(draw: ImageDraw.ImageDraw, xywh: tuple[int, int, int, int], audit: Mapping[str, Any]) -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill="#ffffff", outline="#cbd5e1", width=2)
    draw.text((x + 18, y + 14), "雷达时间窗（示意，不读取 SAR 图像）", font=FONTS["h2"], fill="#0f172a")
    draw_wrapped(
        draw,
        (x + 18, y + 48),
        f"软件同步换算：光学 {OPTICAL_FPS} fps -> 雷达 {SAR_FPS} fps，必须用 50/24 = {FPS_RATIO:.6f}，不是简单 2 倍关系。",
        FONTS["small"],
        "#334155",
        w - 36,
        max_lines=2,
    )
    bar_x = x + 42
    bar_y = y + 118
    bar_w = w - 84
    draw.line((bar_x, bar_y, bar_x + bar_w, bar_y), fill="#94a3b8", width=10)
    sar_start = safe_int(audit.get("sar_start_frame"))
    sar_end = safe_int(audit.get("sar_end_frame"))
    if sar_start is not None and sar_end is not None:
        sx = bar_x + int(max(0, min(1, sar_start / ESTIMATED_SAR_SCENE_FRAMES)) * bar_w)
        ex = bar_x + int(max(0, min(1, sar_end / ESTIMATED_SAR_SCENE_FRAMES)) * bar_w)
        draw.line((sx, bar_y, max(sx + 4, ex), bar_y), fill="#2563eb", width=16)
        draw.text((sx, bar_y + 24), f"SAR {sar_start}", font=FONTS["tiny"], fill="#334155")
        draw.text((max(sx + 90, ex - 80), bar_y + 24), f"SAR {sar_end}", font=FONTS["tiny"], fill="#334155")
        draw.text((x + 18, y + 168), f"窗口宽度：{sar_end - sar_start + 1} 帧；它只说明何时看雷达，不直接说明在哪里找。", font=FONTS["small"], fill="#0f172a")
    else:
        draw.text((x + 18, y + 150), "该对象未生成目标级雷达时间窗；只能保留阻断或场景级说明。", font=FONTS["small"], fill="#dc2626")


def draw_spatial_canvas(draw: ImageDraw.ImageDraw, xywh: tuple[int, int, int, int], audit: Mapping[str, Any], spatial: Mapping[str, str]) -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill="#ffffff", outline="#cbd5e1", width=2)
    draw.text((x + 18, y + 14), "空间先验说明（不是搜索区域）", font=FONTS["h2"], fill="#0f172a")
    canvas = (x + 70, y + 84, x + w - 52, y + h - 80)
    cx1, cy1, cx2, cy2 = canvas
    draw.rectangle(canvas, outline="#94a3b8", width=2)
    draw.text((cx1, cy2 + 14), "方位向 azimuth（由光学框包络弱约束）", font=FONTS["small"], fill="#334155")
    draw.text((cx1 - 48, cy1), "距离向", font=FONTS["small"], fill="#334155")
    draw.text((cx1 - 48, cy1 + 24), "range", font=FONTS["small"], fill="#334155")
    for ratio in (0.0, 0.5, 1.0):
        yy = int(cy1 + ratio * (cy2 - cy1))
        draw.line((cx1, yy, cx2, yy), fill="#e2e8f0", width=1)
    az = parse_azimuth(str(spatial.get("azimuth_center_or_interval", "")))
    if is_true(spatial.get("azimuth_prior_available")) and az["start"] != "" and az["end"] != "":
        amin, amax = -55.0, 40.0
        start = float(az["start"])
        end = float(az["end"])
        ix1 = cx1 + int(max(0.0, min(1.0, (start - amin) / (amax - amin))) * (cx2 - cx1))
        ix2 = cx1 + int(max(0.0, min(1.0, (end - amin) / (amax - amin))) * (cx2 - cx1))
        if ix2 <= ix1:
            ix2 = ix1 + 4
        draw.rectangle((ix1, cy1, ix2, cy2), fill="#bfdbfe", outline="#2563eb", width=3)
        draw.text((ix1 + 8, cy1 + 12), f"方位弱先验：{start:.1f}° 到 {end:.1f}°", font=FONTS["small"], fill="#0f172a")
        draw.text((ix1 + 8, cy1 + 40), "来源：主/辅光学框包络 + 场景方位映射", font=FONTS["small"], fill="#0f172a")
    else:
        draw.text((cx1 + 20, cy1 + 22), "当前无可用方位向先验", font=FONTS["small"], fill="#dc2626")
    range_mode = str(audit.get("range_prior_mode", ""))
    if "broad_unknown" in range_mode:
        draw.rectangle((cx1 + 8, cy1 + 8, cx2 - 8, cy2 - 8), outline="#f59e0b", width=4)
        draw_wrapped(
            draw,
            (cx1 + 18, cy2 - 82),
            "距离向：broad_unknown_range_prior。当前缺运行时安全的目标级 range/depth 字段，所以只能保持宽未知，不能画真实距离位置。",
            FONTS["small"],
            "#92400e",
            cx2 - cx1 - 36,
            max_lines=3,
        )
    else:
        draw_wrapped(draw, (cx1 + 18, cy2 - 70), f"距离向：{range_mode or '未生成'}。", FONTS["small"], "#334155", cx2 - cx1 - 36, max_lines=3)
    draw.text((x + 18, y + h - 40), "边界：不是最终定位、不是候选框、不是搜索区域、不是自动标注。", font=FONTS["small"], fill="#dc2626")


def render_object_page(
    audit: Mapping[str, Any],
    spatial: Mapping[str, str],
    object_rows: Sequence[Mapping[str, str]],
    frame_paths: Mapping[tuple[str, int], Path],
    frame_dirs: Mapping[str, Path],
    out_path: Path,
) -> dict[str, Any]:
    scene = str(audit.get("scene", ""))
    object_id = str(audit.get("object_hypothesis_id", ""))
    eligibility_status = str(audit.get("vehicle_research_eligibility", ""))
    color = eligibility_color(eligibility_status)
    page = Image.new("RGB", (1900, 2260), "#f8fafc")
    draw = ImageDraw.Draw(page)

    draw.text((60, 42), "OTY2 车辆准入对象级真实诊断", font=FONTS["title"], fill="#0f172a")
    tag_x = draw_tag(draw, (60, 102), eligibility_cn(eligibility_status), color)
    tag_x = draw_tag(draw, (tag_x, 102), tier_cn(str(audit.get("resolvability_tier", ""))), "#0f766e")
    draw_tag(draw, (tag_x, 102), spatial_status_cn(str(audit.get("spatial_prior_status", ""))), "#475569")
    draw.text((60, 150), f"场景：{scene}", font=FONTS["h1"], fill="#0f172a")
    draw_wrapped(draw, (60, 188), f"目标编号：{object_id or '场景级说明：缺光学目标流'}", FONTS["body"], "#334155", 1220, max_lines=2)
    draw.text((60, 226), "绿色实线=主观测框；橙色虚线=辅助观测框；右侧雷达部分仅显示时间轴和先验状态，不读取 SAR 图像。", font=FONTS["small"], fill="#475569")

    selected_rows = choose_frame_rows(object_rows) if object_rows else scene_only_frame_rows(scene, frame_paths, frame_dirs)
    panel_x = 60
    panel_y = 290
    panel_w = 560
    panel_h = 420
    labels = ["起始帧", "中间帧", "结束帧"]
    primary_count = 0
    secondary_count = 0
    existing_frame_count = 0
    for idx in range(3):
        x = panel_x + idx * 610
        y = panel_y
        frame_row = selected_rows[idx] if idx < len(selected_rows) else {}
        frame = safe_int(frame_row.get("optical_frame_num"))
        draw.text((x, y - 38), f"{labels[idx]}：{frame if frame is not None else '无'}", font=FONTS["h2"], fill="#0f172a")
        frame_path = resolve_frame_path(scene, frame, frame_paths, frame_dirs) if frame is not None else None
        if frame_path and frame_path.exists():
            with Image.open(frame_path) as source:
                panel, pcount, scount = scale_and_draw_frame(source, (panel_w, panel_h), frame_row)
            page.paste(panel, (x, y))
            primary_count += pcount
            secondary_count += scount
            existing_frame_count += 1
            draw.text((x, y + panel_h + 10), f"光学帧：{frame_path.name}", font=FONTS["tiny"], fill="#475569")
        else:
            draw.rounded_rectangle((x, y, x + panel_w, y + panel_h), radius=10, fill="#e2e8f0", outline="#94a3b8", width=2)
            draw_wrapped(draw, (x + 22, y + 165), "未找到可用光学帧；该页只能保留表格字段诊断。", FONTS["body"], "#475569", panel_w - 44, max_lines=3)

    draw_card(
        draw,
        (60, 790, 860, 305),
        "车辆准入结论",
        [
            f"类别：{audit.get('class_name') or '无'}；类别组：{audit.get('class_group') or '无'}；vehicle-like：{audit.get('is_vehicle_like')}",
            f"可解析度：{tier_cn(str(audit.get('resolvability_tier', '')))}；准入：{eligibility_cn(eligibility_status)}；下游建议：{audit.get('downstream_recommendation')}",
            f"bbox 中位尺寸：{audit.get('median_bbox_width')} x {audit.get('median_bbox_height')} px；面积比例：{audit.get('median_bbox_area_ratio')}",
            f"持续帧数：{audit.get('visible_frame_count') or '无'}；轨迹跨度：{audit.get('track_frame_span') or '无'}；置信度中位数：{audit.get('median_confidence') or '无'}",
            f"判定原因：{audit.get('degradation_reason') or '无'}",
        ],
        border=color,
    )
    draw_timeline(draw, (980, 790, 860, 305), audit)

    draw_card(
        draw,
        (60, 1130, 860, 340),
        "状态标签如何影响准入",
        [
            f"edge_contact：{audit.get('edge_contact')}；partial_or_occluded：{audit.get('partial_or_occluded')}",
            f"duplicate_or_handoff：{audit.get('duplicate_or_handoff')}；ambiguity_status：{audit.get('ambiguity_status')}",
            "稳定、清晰、连续的车辆才适合主研究流；远小、极小、短轨迹或含混对象保留为远小车层/仅审阅/阻断。",
            "辅助观测、edge、partial、duplicate、handoff 不会自动删除对象，但会导致弱车层、审阅层或更保守的空间先验解释。",
        ],
        border="#bae6fd",
    )
    draw_spatial_canvas(draw, (980, 1130, 860, 520), audit, spatial)

    draw_card(
        draw,
        (60, 1510, 860, 325),
        "当前空间先验为什么仍弱",
        [
            "时间窗给出“何时看 SAR”，不直接给出“在哪里找”。",
            "方位向来自光学目标框和场景方位映射，只是弱先验；目标框很小、边缘或重复时，方位先验会变宽或转为审阅。",
            "距离向仍是 broad_unknown_range_prior：缺少运行时安全的 per-object range/depth 几何字段。",
            "因此该图不表示最终位置，也不是候选框或自动标注。",
        ],
        border="#fbbf24",
    )
    draw_card(
        draw,
        (980, 1690, 860, 185),
        "本页绘制检查",
        [
            f"真实光学帧：{existing_frame_count}/3；主观测框：{primary_count}；辅助观测框：{secondary_count}",
            "默认仍不读取 SAR 图像、不使用 SAR GT、不生成搜索区域、不做候选评分。",
        ],
        border="#cbd5e1",
    )

    draw_wrapped(
        draw,
        (60, 1905),
        f"备注：{audit.get('notes')}",
        FONTS["small"],
        "#475569",
        1780,
        max_lines=4,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page.save(out_path)
    return {
        "has_real_optical_frames": existing_frame_count > 0,
        "real_optical_frame_count": existing_frame_count,
        "primary_boxes_drawn": primary_count,
        "secondary_boxes_drawn": secondary_count,
    }


def select_samples(audit_rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, Mapping[str, Any]]]:
    selected: list[tuple[str, Mapping[str, Any]]] = []
    used: set[tuple[str, str]] = set()

    def add(role: str, predicate: Any, preferred_scene: str | None = None) -> None:
        candidates = [row for row in audit_rows if predicate(row)]
        if preferred_scene:
            candidates = sorted(candidates, key=lambda row: (row.get("scene") != preferred_scene, row.get("object_hypothesis_id", "")))
        else:
            candidates = sorted(candidates, key=lambda row: (row.get("scene", ""), row.get("object_hypothesis_id", "")))
        for candidate in candidates:
            key = (str(candidate.get("scene", "")), str(candidate.get("object_hypothesis_id", "")))
            if key not in used:
                selected.append((role, candidate))
                used.add(key)
                return

    add(
        "清晰主研究车辆",
        lambda row: row.get("vehicle_research_eligibility") == "main_research_vehicle"
        and row.get("resolvability_tier") == "high_resolvable_vehicle",
        "GM_RM017",
    )
    add(
        "远小车辆",
        lambda row: row.get("vehicle_research_eligibility") == "far_small_vehicle_layer",
        "GM_RM019",
    )
    add(
        "宽松空间先验车辆",
        lambda row: row.get("spatial_prior_status") == "loose_spatial_prior_generated"
        and row.get("vehicle_research_eligibility") in {"weak_vehicle_layer", "far_small_vehicle_layer", "review_only_vehicle"},
        "GM_RM017",
    )
    add(
        "仅审阅车辆",
        lambda row: row.get("vehicle_research_eligibility") == "review_only_vehicle",
        "GM_RM019",
    )
    add(
        "阻断目标",
        lambda row: row.get("vehicle_research_eligibility") == "blocked_vehicle_or_noise",
        "GM_RM019",
    )
    add(
        "第十一场景说明",
        lambda row: row.get("scene") == "GM_RM011" and row.get("vehicle_research_eligibility") == "blocked_no_object_flow",
        "GM_RM011",
    )
    return selected


def slugify_role(role: str) -> str:
    mapping = {
        "清晰主研究车辆": "clear_main_vehicle",
        "远小车辆": "far_small_vehicle",
        "宽松空间先验车辆": "relaxed_spatial_vehicle",
        "仅审阅车辆": "review_only_vehicle",
        "阻断目标": "blocked_target",
        "第十一场景说明": "gmrm011_no_object_flow",
    }
    return mapping.get(role, "sample")


def render_visualizations(
    timestamp: str,
    audit_rows: list[dict[str, Any]],
    spatial_by_key: Mapping[tuple[str, str], Mapping[str, str]],
    object_rows_by_key: Mapping[tuple[str, str], list[dict[str, str]]],
    frame_paths: Mapping[tuple[str, int], Path],
    frame_dirs: Mapping[str, Path],
) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]]]:
    output_dir = OUTPUT_PARENT / f"oty2_vehicle_research_eligibility_visual_diagnosis_{timestamp}"
    page_dir = output_dir / "object_pages"
    page_dir.mkdir(parents=True, exist_ok=True)
    sample_dir = SAMPLE_DIR / f"vehicle_eligibility_{timestamp}"
    sample_dir.mkdir(parents=True, exist_ok=True)
    samples = select_samples(audit_rows)
    sample_keys = {(str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))): role for role, row in samples}
    sample_rows: list[dict[str, Any]] = []
    all_visual_rows: list[dict[str, Any]] = []

    for audit in audit_rows:
        scene = str(audit.get("scene", ""))
        object_id = str(audit.get("object_hypothesis_id", ""))
        key = (scene, object_id)
        local_path = page_dir / f"oty2_vehicle_eligibility_{file_token(scene, object_id)}_{timestamp}.png"
        render_info = render_object_page(
            audit,
            spatial_by_key.get(key, {}),
            object_rows_by_key.get(key, []),
            frame_paths,
            frame_dirs,
            local_path,
        )
        audit["local_visualization_path"] = str(local_path)
        audit.update(render_info)
        role = sample_keys.get(key)
        repo_sample_path = ""
        if role:
            repo_sample_path = str(sample_dir / f"oty2_vehicle_eligibility_{slugify_role(role)}_{file_token(scene, object_id)}_{timestamp}.png")
            shutil.copyfile(local_path, repo_sample_path)
            audit["repo_sample_visualization_path"] = repo_sample_path
            sample_rows.append(
                {
                    "sample_role": role,
                    "scene": scene,
                    "object_hypothesis_id": object_id,
                    "class_name": audit.get("class_name", ""),
                    "resolvability_tier": audit.get("resolvability_tier", ""),
                    "vehicle_research_eligibility": audit.get("vehicle_research_eligibility", ""),
                    "spatial_prior_status": audit.get("spatial_prior_status", ""),
                    "local_visualization_path": str(local_path),
                    "repo_sample_visualization_path": repo_sample_path,
                }
            )
        else:
            audit["repo_sample_visualization_path"] = ""
        all_visual_rows.append(
            {
                "sample_role": role or "",
                "scene": scene,
                "object_hypothesis_id": object_id,
                "class_name": audit.get("class_name", ""),
                "resolvability_tier": audit.get("resolvability_tier", ""),
                "vehicle_research_eligibility": audit.get("vehicle_research_eligibility", ""),
                "spatial_prior_status": audit.get("spatial_prior_status", ""),
                "local_visualization_path": str(local_path),
                "repo_sample_visualization_path": repo_sample_path,
            }
        )
    write_csv(output_dir / "oty2_vehicle_research_eligibility_visual_index.csv", all_visual_rows, SUMMARY_VIS_FIELDS)
    return output_dir, sample_rows, all_visual_rows


def count_by(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field, "")) for row in rows))


def count_by_scene(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(row.get("scene", ""))][str(row.get(field, ""))] += 1
    return {scene: dict(counter) for scene, counter in sorted(grouped.items())}


def scene_table(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for scene in sorted({str(row.get("scene", "")) for row in rows}):
        scene_rows = [row for row in rows if row.get("scene") == scene]
        elig = Counter(str(row.get("vehicle_research_eligibility", "")) for row in scene_rows)
        tiers = Counter(str(row.get("resolvability_tier", "")) for row in scene_rows)
        table.append(
            {
                "scene": scene,
                "total_rows": len(scene_rows),
                "main_research_vehicle": elig.get("main_research_vehicle", 0),
                "weak_vehicle_layer": elig.get("weak_vehicle_layer", 0),
                "far_small_vehicle_layer": elig.get("far_small_vehicle_layer", 0),
                "review_only_vehicle": elig.get("review_only_vehicle", 0),
                "blocked": elig.get("blocked_vehicle_or_noise", 0) + elig.get("blocked_no_object_flow", 0),
                "high_resolvable_vehicle": tiers.get("high_resolvable_vehicle", 0),
                "medium_resolvable_vehicle": tiers.get("medium_resolvable_vehicle", 0),
                "low_resolvable_far_vehicle": tiers.get("low_resolvable_far_vehicle", 0),
                "unresolved_tiny_vehicle": tiers.get("unresolved_tiny_vehicle", 0),
            }
        )
    return table


def render_markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def render_report(
    path: Path,
    timestamp: str,
    audit_rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    sample_rows: Sequence[Mapping[str, Any]],
    local_output_dir: Path,
    sources: Mapping[str, str],
) -> None:
    eligibility_counts = Counter(str(row.get("vehicle_research_eligibility", "")) for row in audit_rows)
    tier_counts = Counter(str(row.get("resolvability_tier", "")) for row in audit_rows)
    consistency_counts = Counter(str(row.get("spatial_prior_vehicle_admission_consistency", "")) for row in audit_rows)
    lines = [
        "# OTY2 车目标准入审计报告",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本轮聚焦 vehicle / car-like 目标准入、远小目标分层和对象级真实可视化。更高级 YOLO 可能改善检测，但本报告不把“检测到了”直接等同为“适合光学到 SAR 自动标注迁移主研究对象”。",
        "",
        "## 边界",
        "",
        "- 不读取 SAR 图像内容。",
        "- 不使用 SAR GT。",
        "- 不生成 SAR 搜索区域或候选框。",
        "- 不做候选评分、selector/ranking、训练或阈值调参。",
        "- 不生成自动标注建议，不声明身份真值。",
        "- 不提交或生成模型权重，不声称更强 YOLO 已被验证为改进。",
        "",
        "## 总结",
        "",
        f"- 审计行数：`{len(audit_rows)}`（含第十一场景缺目标流说明行）。",
        f"- vehicle-like 对象：`{sum(1 for row in audit_rows if is_true(row.get('is_vehicle_like')))}`。",
        f"- 主研究车辆：`{eligibility_counts.get('main_research_vehicle', 0)}`。",
        f"- 弱车目标层：`{eligibility_counts.get('weak_vehicle_layer', 0)}`。",
        f"- 远小车辆层：`{eligibility_counts.get('far_small_vehicle_layer', 0)}`。",
        f"- 仅审阅车辆：`{eligibility_counts.get('review_only_vehicle', 0)}`。",
        f"- 阻断目标：`{eligibility_counts.get('blocked_vehicle_or_noise', 0) + eligibility_counts.get('blocked_no_object_flow', 0)}`。",
        "",
        "## 每场景准入结果",
        "",
        render_markdown_table(
            scene_table(audit_rows),
            [
                "scene",
                "total_rows",
                "main_research_vehicle",
                "weak_vehicle_layer",
                "far_small_vehicle_layer",
                "review_only_vehicle",
                "blocked",
                "high_resolvable_vehicle",
                "medium_resolvable_vehicle",
                "low_resolvable_far_vehicle",
                "unresolved_tiny_vehicle",
            ],
        ),
        "",
        "## 当前弱点在哪里",
        "",
        "- 主要弱点不是时间窗。24 fps 到 50 fps 的软件同步换算已经给出目标级雷达帧窗口。",
        "- 主要弱点也不完全是方位向。方位弱先验已能从光学框包络和场景方位映射得到，但远小框、边缘、partial、duplicate、handoff 会导致方位解释变宽或降级。",
        "- 最弱的是距离向。当前非阻断对象仍是 `broad_unknown_range_prior`，缺少运行时安全的 per-object range/depth 几何字段。",
        "- 第二个弱点是目标可解析度。GM_RM019 中有多辆远小车，YOLO 检测存在，但框面积比例很低；它们不应该直接混入主研究流。",
        "- 第三个弱点是目标状态稳定性。短轨迹、含混、多观测、边缘/遮挡对象需要进入弱车层、仅审阅层或阻断层。",
        "",
        "## 分层依据",
        "",
        "这些阈值是 `audit defaults / audit suggestion`，用于解释分布和挑样例，不是训练阈值，也不是调参结果。",
        "",
        "```json",
        json.dumps(AUDIT_DEFAULTS, ensure_ascii=False, indent=2),
        "```",
        "",
        f"- 可解析度分层计数：`{json.dumps(dict(tier_counts), ensure_ascii=False)}`",
        f"- 准入分层计数：`{json.dumps(dict(eligibility_counts), ensure_ascii=False)}`",
        f"- 空间先验与车辆准入一致性：`{json.dumps(dict(consistency_counts), ensure_ascii=False)}`",
        "",
        "## 输入部件各自作用",
        "",
        "- 光学目标流：提供 object_hypothesis_id、主观测框、辅助观测、帧范围、轨迹长度、置信度和状态标签。它决定这个对象是否有足够稳定的光学证据。",
        "- 主观测框：用于车辆可解析度统计、目标框面积比例、光学截图叠框，以及方位向弱先验来源说明。",
        "- 辅助观测：不直接阻断对象，但会提示 duplicate / handoff / 多观测风险，通常进入弱车层或仅审阅层。",
        "- 时间窗：提供对应 SAR 帧范围，限制“何时看雷达”；它不解决“在哪里找”。",
        "- 场景几何：当前主要提供方位向弱映射；距离向仍缺可运行时使用的对象级几何输入。",
        "- 规则层：把对象分为主研究车辆、弱车层、远小车层、仅审阅和阻断，避免把所有 YOLO 检测都混入主研究对象。",
        "",
        "## 代表样例",
        "",
        render_markdown_table(sample_rows, ["sample_role", "scene", "object_hypothesis_id", "class_name", "resolvability_tier", "vehicle_research_eligibility", "spatial_prior_status", "repo_sample_visualization_path"]),
        "",
        "## 第十一场景",
        "",
        "GM_RM011 的时间元数据可用，可以沿用 24:50 软件同步契约；但当前缺光学目标流，所以不能生成对象级车辆准入、目标级雷达时间窗映射或对象级空间先验。报告和样例图单独把这件事标出来，不把它混入目标级结果。",
        "",
        "## 对后续 SAR 搜索的影响",
        "",
        "- 主研究车辆可以作为后续空间约束设计的优先对象。",
        "- 弱车目标层需要更大的方位余量或先人工审阅状态，不适合作为干净主样本直接汇总。",
        "- 远小车辆层应该保留记录，但如果全部放入主研究，会增加宽未知距离向和弱方位先验的比例，使后续 SAR 搜索约束失去研究解释性。",
        "- 仅审阅和阻断对象不应进入正常 downstream 主结果。",
        "",
        "## 输出",
        "",
        f"- 本地全量对象图目录：`{local_output_dir}`",
        f"- 审计 CSV：`{path.with_name('oty2_vehicle_research_eligibility_audit_' + timestamp + '.csv')}`",
        f"- 摘要 JSON：`{path.with_name('oty2_vehicle_research_eligibility_summary_' + timestamp + '.json')}`",
        f"- YOLO 升级 A/B 计划：`{path.with_name('oty2_yolo_upgrade_ablation_plan_' + timestamp + '.md')}`",
        "",
        "## 数据源",
        "",
    ]
    for name, source in sources.items():
        lines.append(f"- {name}: `{source}`")
    lines.extend(
        [
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_yolo_plan(path: Path, timestamp: str, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 YOLO 升级 A/B 对比接口设计",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本文件只设计对比接口，不替换主线模型，不下载权重，不训练或调阈值，也不声称更高级 YOLO 已被验证为改进。",
        "",
        "## 当前 YOLO 可能的问题",
        "",
        "- 漏检：当前对象流只反映已被检测并跟踪到的目标，无法证明所有车辆都被召回。",
        "- 误检：本轮对象级主流中没有发现非车辆类主对象，但这不代表更大范围没有误检。",
        "- 框不准：远小车和边缘对象的 bbox 面积很小，少量像素误差会显著影响方位弱先验。",
        "- 重复框 / handoff：辅助观测、多观测和可能 ID 切换会把对象降级为弱车层或仅审阅层。",
        "- 远小车过多：更强 YOLO 可能检出更多远小车，这对检测数量是好事，但会提高远小车层和 review-only 比例。",
        "- 类别不聚焦：当前主线只研究 vehicle/car-like，不应把所有 YOLO 类别都混入主结果。",
        "- 跟踪断裂：短轨迹对象即便类别是 car，也不适合作为主研究迁移对象。",
        "",
        "## 更高级 YOLO 可能改善什么",
        "",
        "- 可能提高车辆召回，尤其是远小车或遮挡车辆。",
        "- 可能让框更稳定，从而改善轨迹连续性和方位弱先验的包络质量。",
        "- 可能减少部分误检或类别混淆。",
        "",
        "## 可能副作用",
        "",
        "- 检出更多极小远车，导致主研究对象池被弱目标稀释。",
        "- 产生更多短轨迹、重复框和 handoff，需要更多 review-only 处理。",
        "- 检测数量上升不等于 SAR 标注迁移质量上升。",
        "- 如果只看 detection count，会误判模型升级价值。",
        "",
        "## A/B 对比接口",
        "",
        "1. 固定同一批场景、光学帧范围和软件同步时间契约。",
        "2. 分别运行 baseline YOLO 与 candidate YOLO，输出同 schema 的 OTY0 检测表。",
        "3. 用同一 OTY1/OTY1t 对象流构造逻辑生成对象假设，禁止引入 SAR GT 或后验 selector。",
        "4. 运行本准入审计脚本，比较对象级 eligibility，而不是只比较检测数量。",
        "5. 只把模型权重路径写入本地配置或命令参数，不提交权重文件。",
        "",
        "## 推荐指标",
        "",
        "- `vehicle_research_eligibility` 分布：主研究车辆、弱车、远小车、仅审阅、阻断分别如何变化。",
        "- `track_frame_span` 和 `visible_frame_count`：轨迹是否更连续。",
        "- 远小车比例：`low_resolvable_far_vehicle` + `unresolved_tiny_vehicle` 是否显著上升。",
        "- duplicate/handoff 比率：更多检测是否制造更多重复对象。",
        "- downstream normal / review-only / blocked 变化：是否真正增加可进入主研究的对象，而不是只增加审阅负担。",
        "- bbox 面积比例和置信度分布：框是否更稳定、更可解析。",
        "",
        "## 当前建议",
        "",
        "不建议马上把主线替换成更高级 YOLO。应先做 A/B 对比，判断升级是否增加主研究车辆和轨迹连续性，同时不显著增加远小车、重复框和 review-only 负担。",
        "",
        "## 本轮基线摘要",
        "",
        "```json",
        json.dumps(
            {
                "eligibility_counts": summary.get("eligibility_counts", {}),
                "resolvability_tier_counts": summary.get("resolvability_tier_counts", {}),
                "scene_summary": summary.get("scene_summary", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_summary(
    timestamp: str,
    audit_rows: Sequence[Mapping[str, Any]],
    sample_rows: Sequence[Mapping[str, Any]],
    local_output_dir: Path,
    sources: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "total_rows": len(audit_rows),
        "vehicle_like_count": sum(1 for row in audit_rows if is_true(row.get("is_vehicle_like"))),
        "eligibility_counts": count_by(audit_rows, "vehicle_research_eligibility"),
        "eligibility_counts_by_scene": count_by_scene(audit_rows, "vehicle_research_eligibility"),
        "resolvability_tier_counts": count_by(audit_rows, "resolvability_tier"),
        "resolvability_tier_counts_by_scene": count_by_scene(audit_rows, "resolvability_tier"),
        "spatial_prior_status_counts": count_by(audit_rows, "spatial_prior_status"),
        "class_counts": count_by(audit_rows, "class_name"),
        "class_group_counts": count_by(audit_rows, "class_group"),
        "scene_summary": scene_table(audit_rows),
        "sample_rows": list(sample_rows),
        "local_visualization_output_dir": str(local_output_dir),
        "local_object_page_count": len(audit_rows),
        "audit_defaults_not_training_thresholds": AUDIT_DEFAULTS,
        "boundary_flags": BOUNDARY_FLAGS,
        "sources": dict(sources),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    spatial_path = Path(args.spatial_priors_csv) if args.spatial_priors_csv else latest_path("oty2_object_runtime_spatial_priors_*.csv")
    temporal_path = Path(args.temporal_windows_csv) if args.temporal_windows_csv else latest_path("oty2_object_sar_temporal_windows_*.csv")
    quality_path = Path(args.temporal_quality_csv) if args.temporal_quality_csv else latest_path("oty2_object_sar_temporal_window_quality_audit_*.csv")
    object_frame_path = Path(args.object_frame_state_csv) if args.object_frame_state_csv else DEFAULT_OBJECT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv"
    hypotheses_path = Path(args.object_hypotheses_csv) if args.object_hypotheses_csv else DEFAULT_OBJECT_DIR / "oty1t_object_hypotheses_generalized.csv"
    manifest_path = Path(args.manifest_csv)

    spatial_rows = read_csv(spatial_path)
    temporal_rows = read_csv(temporal_path)
    # Loaded to keep the contract explicit; this script does not use it to tune thresholds.
    quality_rows = read_csv(quality_path)
    object_frame_rows = read_csv(object_frame_path)
    hypotheses_rows = read_csv(hypotheses_path)
    detections, yolo_class_counter = load_yolo_detections()
    frame_paths, frame_dirs, frame_dims = load_frame_paths(manifest_path)

    object_rows_by_key = group_by_object(object_frame_rows)
    hypotheses_by_key = rows_by_key(hypotheses_rows)
    temporal_by_key = rows_by_key(temporal_rows)
    spatial_by_key = rows_by_key(spatial_rows)

    audit_rows = build_audit_rows(
        spatial_rows,
        temporal_by_key,
        object_rows_by_key,
        hypotheses_by_key,
        detections,
        frame_paths,
        frame_dirs,
        frame_dims,
    )
    local_output_dir, sample_rows, visual_index_rows = render_visualizations(
        timestamp,
        audit_rows,
        spatial_by_key,
        object_rows_by_key,
        frame_paths,
        frame_dirs,
    )

    audit_csv = REPORT_DIR / f"oty2_vehicle_research_eligibility_audit_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_vehicle_research_eligibility_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_vehicle_research_eligibility_summary_{timestamp}.json"
    yolo_plan_md = REPORT_DIR / f"oty2_yolo_upgrade_ablation_plan_{timestamp}.md"
    visual_summary_csv = REPORT_DIR / f"oty2_vehicle_research_eligibility_visual_summary_{timestamp}.csv"

    write_csv(audit_csv, audit_rows, AUDIT_FIELDS)
    write_csv(visual_summary_csv, visual_index_rows, SUMMARY_VIS_FIELDS)
    sources = {
        "spatial_priors_csv": str(spatial_path),
        "temporal_windows_csv": str(temporal_path),
        "temporal_quality_csv": str(quality_path),
        "object_frame_state_csv": str(object_frame_path),
        "object_hypotheses_csv": str(hypotheses_path),
        "manifest_csv": str(manifest_path),
        "yolo_class_counter": json.dumps(dict(yolo_class_counter), ensure_ascii=False),
        "temporal_quality_rows_loaded": str(len(quality_rows)),
    }
    summary = build_summary(timestamp, audit_rows, sample_rows, local_output_dir, sources)
    write_json(summary_json, summary)
    render_report(report_md, timestamp, audit_rows, summary, sample_rows, local_output_dir, sources)
    render_yolo_plan(yolo_plan_md, timestamp, summary)

    summary.update(
        {
            "audit_csv": str(audit_csv),
            "report_md": str(report_md),
            "summary_json": str(summary_json),
            "yolo_plan_md": str(yolo_plan_md),
            "visual_summary_csv": str(visual_summary_csv),
            "sample_output_dir": str(SAMPLE_DIR / f"vehicle_eligibility_{timestamp}"),
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="", help="Timestamp suffix for outputs; defaults to current local time.")
    parser.add_argument("--spatial-priors-csv", default="", help="Override OTY2 runtime spatial priors CSV.")
    parser.add_argument("--temporal-windows-csv", default="", help="Override OTY2 temporal windows CSV.")
    parser.add_argument("--temporal-quality-csv", default="", help="Override temporal quality audit CSV.")
    parser.add_argument("--object-frame-state-csv", default="", help="Override OTY1t object frame state CSV.")
    parser.add_argument("--object-hypotheses-csv", default="", help="Override OTY1t object hypotheses CSV.")
    parser.add_argument("--manifest-csv", default=str(REPO_ROOT / "manifests" / "oty0_yolo_manifest.csv"))
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
