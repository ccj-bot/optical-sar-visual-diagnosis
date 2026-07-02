"""Posthoc OTY2 optical-object to SAR-GT mechanism audit.

This script intentionally crosses into SAR GT and SAR image content, but only
for posthoc mechanism discovery. It must not be used as runtime prior
construction, selector/ranking logic, threshold tuning, automatic annotation
proposal generation, or identity-truth assignment.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageStat


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
OUTPUT_PARENT = REPO_ROOT / "outputs"
SAMPLE_DIR = REPORT_DIR / "samples" / "gt_correspondence_mechanism_visualizations"
DEFAULT_OBJECT_DIR = REPO_ROOT / "outputs" / "oty1t_object_hypothesis_generalization_audit_20260701_231500"
DEFAULT_GT_CSV = Path(r"D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv")
DEFAULT_REVIEW_QUEUE_CSV = Path(r"D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\review_queue.csv")

OPTICAL_FPS = 24
SAR_FPS = 50
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7

PAIR_IOU_MIN = 0.05

BASE_VEHICLE_SIZE_SHELL = {
    "long_axis_min_px": 80.0,
    "long_axis_max_px": 220.0,
    "short_axis_min_px": 35.0,
    "short_axis_max_px": 115.0,
    "aspect_min": 1.25,
    "aspect_max": 3.35,
}
RELAXED_VEHICLE_SIZE_SHELL = {
    "long_axis_min_px": 55.0,
    "long_axis_max_px": 270.0,
    "short_axis_min_px": 25.0,
    "short_axis_max_px": 160.0,
    "aspect_min": 0.85,
    "aspect_max": 4.80,
}

BOUNDARY_FLAGS = {
    "sar_gt_used": True,
    "sar_image_content_used": True,
    "posthoc_mechanism_discovery_only": True,
    "gt_or_sar_used_for_runtime_prior_construction": False,
    "automatic_annotation_proposal_generated": False,
    "training_or_threshold_tuning_entered": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "identity_truth_claimed": False,
    "model_weights_committed_or_downloaded": False,
}

CORRESPONDENCE_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "correspondence_status",
    "correspondence_match_iou",
    "optical_track_or_observation_ids",
    "sar_frame",
    "sar_gt_id",
    "sar_gt_center",
    "sar_gt_width_height_or_rotated_box",
    "sar_gt_radius_px",
    "sar_gt_azimuth_deg",
    "optical_frame",
    "optical_bbox",
    "optical_bbox_width_height_area",
    "optical_bbox_aspect_ratio",
    "optical_bbox_bottom_y",
    "optical_bbox_bottom_y_norm",
    "optical_object_state",
    "primary_secondary_status",
    "visibility_state",
    "edge_partial_duplicate_handoff_ambiguity_flags",
    "vehicle_research_eligibility",
    "resolvability_tier",
    "spatial_prior_status",
    "temporal_window_contains_gt_frame",
    "azimuth_prior_contains_gt",
    "vehicle_size_shell_contains_gt",
    "range_shell_contains_gt",
    "notes",
]

SHELL_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "sar_gt_id",
    "sar_frame",
    "gt_azimuth_deg",
    "azimuth_prior_center_deg",
    "azimuth_prior_start_deg",
    "azimuth_prior_end_deg",
    "azimuth_prior_width_deg",
    "azimuth_error_to_center_deg",
    "azimuth_prior_contains_gt",
    "azimuth_failure_context",
    "size_shell_mode",
    "gt_long_axis_px",
    "gt_short_axis_px",
    "gt_axis_aspect",
    "vehicle_size_shell_contains_gt",
    "base_vehicle_size_shell_contains_gt",
    "size_shell_angular_width_at_gt_radius_deg",
    "size_shell_to_azimuth_width_ratio",
    "size_shell_compression_effect",
    "shape_range_shell_mode",
    "shape_range_shell_radius_min_px",
    "shape_range_shell_radius_max_px",
    "shape_range_shell_width_px",
    "range_shell_contains_gt",
    "range_shell_note",
]

SHAPE_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "sar_gt_id",
    "sar_frame",
    "optical_frame",
    "optical_bbox_area_ratio",
    "optical_bbox_height",
    "optical_bbox_width",
    "optical_bbox_aspect_ratio",
    "optical_bbox_bottom_y_norm",
    "object_optical_area_slope_per_frame",
    "object_sar_radius_slope_per_frame",
    "optical_area_vs_sar_radius_trend_status",
    "sar_gt_radius_px",
    "sar_gt_azimuth_deg",
    "sar_gt_long_axis_px",
    "sar_gt_short_axis_px",
    "sar_gt_aspect",
    "sar_box_mean_intensity",
    "sar_box_max_intensity",
    "sar_box_top5_mean_intensity",
    "sar_local_background_mean",
    "sar_box_to_background_ratio",
    "sar_peak_to_background_ratio",
    "sar_center_to_peak_distance_px",
    "scatter_observation_note",
    "posthoc_only_note",
]

VISUAL_SUMMARY_FIELDS = [
    "sample_role",
    "scene",
    "object_hypothesis_id",
    "sar_gt_id",
    "sar_frame",
    "vehicle_research_eligibility",
    "azimuth_prior_contains_gt",
    "vehicle_size_shell_contains_gt",
    "range_shell_contains_gt",
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


def safe_float(value: Any, default: float | None = None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def safe_int(value: Any, default: int | None = None) -> int | None:
    numeric = safe_float(value)
    if numeric is None:
        return default
    return int(numeric)


def is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def fmt(value: Any, digits: int = 3) -> str:
    numeric = safe_float(value)
    if numeric is None:
        return ""
    return f"{numeric:.{digits}f}"


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def choose_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
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
    "title": choose_font(34, True),
    "h1": choose_font(25, True),
    "h2": choose_font(20, True),
    "body": choose_font(17),
    "small": choose_font(14),
    "tiny": choose_font(12),
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
    line_gap: int = 5,
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


def draw_card(draw: ImageDraw.ImageDraw, xywh: tuple[int, int, int, int], title: str, body: Sequence[Any], border: str = "#cbd5e1") -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill="#ffffff", outline=border, width=2)
    draw.text((x + 16, y + 12), title, font=FONTS["h2"], fill="#0f172a")
    cursor = y + 44
    for item in body:
        cursor = draw_wrapped(draw, (x + 16, cursor), item, FONTS["small"], "#334155", w - 32, max_lines=4)
        cursor += 5
        if cursor > y + h - 12:
            break


def draw_tag(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str) -> int:
    x, y = xy
    pad_x = 12
    pad_y = 6
    w, h = text_size(draw, text, FONTS["small"])
    draw.rounded_rectangle((x, y, x + w + 2 * pad_x, y + h + 2 * pad_y), radius=12, fill=fill)
    draw.text((x + pad_x, y + pad_y - 1), text, font=FONTS["small"], fill="#ffffff")
    return x + w + 2 * pad_x + 8


def bbox_iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def parse_bbox(row: Mapping[str, Any], fields: Sequence[str]) -> tuple[float, float, float, float] | None:
    values = [safe_float(row.get(field)) for field in fields]
    if all(value is not None for value in values):
        x1, y1, x2, y2 = [float(value) for value in values]
        if x2 > x1 and y2 > y1:
            return x1, y1, x2, y2
    return None


def frame_from_path(path_text: str) -> int | None:
    try:
        return int(Path(path_text).stem)
    except ValueError:
        return None


def sar_path(scene: str, frame: int, prefer_gray: bool = False) -> Path:
    folder = f"{scene}_SARframes_gray" if prefer_gray else f"{scene}_SARframes"
    return Path(r"D:\profile\research\data") / scene / folder / f"{frame:06d}.png"


def optical_path(scene: str, frame: int) -> Path:
    return Path(r"D:\profile\research\data") / scene / f"{scene}_frames" / f"{frame:06d}.png"


def point_to_azimuth_deg(x: float, y: float) -> float:
    return math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))


def point_to_radius_px(x: float, y: float) -> float:
    return math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)


def parse_azimuth_interval(text: str) -> dict[str, float | str]:
    import re

    center_match = re.search(r"center_deg=([-+]?\d+(?:\.\d+)?)", text or "")
    interval_match = re.search(r"interval_deg=\[([-+]?\d+(?:\.\d+)?),([-+]?\d+(?:\.\d+)?)\]", text or "")
    margin_match = re.search(r"margin_deg=([-+]?\d+(?:\.\d+)?)", text or "")
    start = safe_float(interval_match.group(1)) if interval_match else None
    end = safe_float(interval_match.group(2)) if interval_match else None
    center = safe_float(center_match.group(1)) if center_match else None
    margin = safe_float(margin_match.group(1)) if margin_match else None
    return {
        "center": "" if center is None else center,
        "start": "" if start is None else start,
        "end": "" if end is None else end,
        "width": "" if start is None or end is None else max(0.0, float(end) - float(start)),
        "margin": "" if margin is None else margin,
    }


def contains_interval(value: float, start: Any, end: Any) -> bool | None:
    s = safe_float(start)
    e = safe_float(end)
    if s is None or e is None:
        return None
    return s <= value <= e


def rotated_box_corners(cx: float, cy: float, w: float, h: float, heading_deg: float) -> list[tuple[float, float]]:
    angle = math.radians(heading_deg)
    ca, sa = math.cos(angle), math.sin(angle)
    corners = []
    for dx, dy in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
        x = cx + dx * ca - dy * sa
        y = cy + dx * sa + dy * ca
        corners.append((x, y))
    return corners


def primary_box(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    return parse_bbox(row, ("primary_bbox_x1", "primary_bbox_y1", "primary_bbox_x2", "primary_bbox_y2"))


def state_is_relaxed(correspondence: Mapping[str, Any]) -> bool:
    eligibility = str(correspondence.get("vehicle_research_eligibility", ""))
    flags = str(correspondence.get("edge_partial_duplicate_handoff_ambiguity_flags", ""))
    return eligibility in {"weak_vehicle_layer", "far_small_vehicle_layer", "review_only_vehicle"} or "true" in flags.lower()


def shell_contains(long_axis: float, short_axis: float, shell: Mapping[str, float]) -> bool:
    aspect = long_axis / max(short_axis, 1e-6)
    return (
        shell["long_axis_min_px"] <= long_axis <= shell["long_axis_max_px"]
        and shell["short_axis_min_px"] <= short_axis <= shell["short_axis_max_px"]
        and shell["aspect_min"] <= aspect <= shell["aspect_max"]
    )


def quantile(values: Sequence[float], q: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * q
    low = int(math.floor(pos))
    high = int(math.ceil(pos))
    if low == high:
        return clean[low]
    return clean[low] * (high - pos) + clean[high] * (pos - low)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 3:
        return None
    xvals = [p[0] for p in pairs]
    yvals = [p[1] for p in pairs]
    mx = sum(xvals) / len(xvals)
    my = sum(yvals) / len(yvals)
    num = sum((x - mx) * (y - my) for x, y in pairs)
    denx = math.sqrt(sum((x - mx) ** 2 for x in xvals))
    deny = math.sqrt(sum((y - my) ** 2 for y in yvals))
    if denx <= 1e-12 or deny <= 1e-12:
        return None
    return num / (denx * deny)


def slope(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 2:
        return None
    mx = sum(x for x, _ in pairs) / len(pairs)
    my = sum(y for _, y in pairs) / len(pairs)
    den = sum((x - mx) ** 2 for x, _ in pairs)
    if den <= 1e-12:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / den


def load_tables(args: argparse.Namespace) -> dict[str, Any]:
    spatial_rows = read_csv(Path(args.spatial_priors_csv) if args.spatial_priors_csv else latest_path("oty2_object_runtime_spatial_priors_*.csv"))
    temporal_rows = read_csv(Path(args.temporal_windows_csv) if args.temporal_windows_csv else latest_path("oty2_object_sar_temporal_windows_*.csv"))
    vehicle_rows = read_csv(Path(args.vehicle_eligibility_csv) if args.vehicle_eligibility_csv else latest_path("oty2_vehicle_research_eligibility_audit_*.csv"))
    visual_rows = read_csv(Path(args.object_visual_summary_csv) if args.object_visual_summary_csv else latest_path("oty2_runtime_spatial_prior_visual_summary_*.csv"))
    object_frame_rows = read_csv(Path(args.object_frame_state_csv) if args.object_frame_state_csv else DEFAULT_OBJECT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv")
    object_hypotheses_rows = read_csv(Path(args.object_hypotheses_csv) if args.object_hypotheses_csv else DEFAULT_OBJECT_DIR / "oty1t_object_hypotheses_generalized.csv")
    final_gt_rows = read_csv(Path(args.final_gt_csv))
    review_queue_rows = read_csv(Path(args.review_queue_csv))
    return {
        "spatial_rows": spatial_rows,
        "temporal_rows": temporal_rows,
        "vehicle_rows": vehicle_rows,
        "visual_rows": visual_rows,
        "object_frame_rows": object_frame_rows,
        "object_hypotheses_rows": object_hypotheses_rows,
        "final_gt_rows": final_gt_rows,
        "review_queue_rows": review_queue_rows,
    }


def rows_by_key(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))): dict(row) for row in rows}


def group_object_frames(rows: Sequence[Mapping[str, str]]) -> tuple[dict[tuple[str, int], list[dict[str, str]]], dict[tuple[str, str], list[dict[str, str]]]]:
    by_frame: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    by_object: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        scene = str(row.get("scene", ""))
        frame = safe_int(row.get("optical_frame_num"))
        object_id = str(row.get("object_hypothesis_id", ""))
        if scene and frame is not None:
            by_frame[(scene, frame)].append(dict(row))
        if scene and object_id:
            by_object[(scene, object_id)].append(dict(row))
    for rows_for_object in by_object.values():
        rows_for_object.sort(key=lambda item: safe_int(item.get("optical_frame_num"), 0) or 0)
    return by_frame, by_object


def build_correspondences(
    tables: Mapping[str, Any],
    spatial_by_key: Mapping[tuple[str, str], Mapping[str, str]],
    temporal_by_key: Mapping[tuple[str, str], Mapping[str, str]],
    vehicle_by_key: Mapping[tuple[str, str], Mapping[str, str]],
    object_by_frame: Mapping[tuple[str, int], Sequence[Mapping[str, str]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    review_by_identity = {str(row.get("target_identity", "")): row for row in tables["review_queue_rows"]}
    correspondences: list[dict[str, Any]] = []
    skipped = Counter()
    for gt in tables["final_gt_rows"]:
        scene = str(gt.get("scene", ""))
        target_identity = str(gt.get("target_identity", ""))
        review = review_by_identity.get(target_identity, {})
        opt_bbox = parse_bbox(review, ("opt_x1", "opt_y1", "opt_x2", "opt_y2"))
        optical_frame = frame_from_path(str(gt.get("optical_path", "")))
        if opt_bbox is None:
            skipped["missing_review_optical_bbox_or_saronly"] += 1
            continue
        if optical_frame is None:
            skipped["missing_optical_frame"] += 1
            continue
        candidates = object_by_frame.get((scene, optical_frame), [])
        if not candidates:
            skipped[f"missing_object_frame:{scene}"] += 1
            continue
        best_iou = 0.0
        best_row: Mapping[str, str] | None = None
        for candidate in candidates:
            pbox = primary_box(candidate)
            if pbox is None:
                continue
            score = bbox_iou(opt_bbox, pbox)
            if score > best_iou:
                best_iou = score
                best_row = candidate
        if best_row is None or best_iou < PAIR_IOU_MIN:
            skipped[f"no_iou_match_ge_{PAIR_IOU_MIN}:{scene}"] += 1
            continue

        object_id = str(best_row.get("object_hypothesis_id", ""))
        key = (scene, object_id)
        spatial = spatial_by_key.get(key, {})
        temporal = temporal_by_key.get(key, {})
        vehicle = vehicle_by_key.get(key, {})
        sar_frame = safe_int(gt.get("sar_frame_num"))
        final_cx = safe_float(gt.get("final_cx"))
        final_cy = safe_float(gt.get("final_cy"))
        final_w = safe_float(gt.get("final_w"))
        final_h = safe_float(gt.get("final_h"))
        final_heading = safe_float(gt.get("final_heading_deg"), 0.0) or 0.0
        if None in {sar_frame, final_cx, final_cy, final_w, final_h}:
            skipped["missing_gt_geometry"] += 1
            continue
        gt_az = point_to_azimuth_deg(float(final_cx), float(final_cy))
        gt_radius = point_to_radius_px(float(final_cx), float(final_cy))
        az = parse_azimuth_interval(str(spatial.get("azimuth_center_or_interval", "")))
        az_contains_raw = contains_interval(gt_az, az["start"], az["end"])
        az_contains = "" if az_contains_raw is None else bool_text(az_contains_raw)
        sar_start = safe_int(spatial.get("sar_start_frame") or temporal.get("sar_start_frame"))
        sar_end = safe_int(spatial.get("sar_end_frame") or temporal.get("sar_end_frame"))
        temporal_contains = sar_start is not None and sar_end is not None and sar_start <= int(sar_frame) <= sar_end
        x1, y1, x2, y2 = opt_bbox
        ow = x2 - x1
        oh = y2 - y1
        optical_area = ow * oh
        optical_aspect = ow / max(oh, 1e-6)
        optical_bottom_y_norm = y2 / 600.0
        long_axis = max(float(final_w), float(final_h))
        short_axis = min(float(final_w), float(final_h))
        aspect = long_axis / max(short_axis, 1e-6)
        base_shell_contains = shell_contains(long_axis, short_axis, BASE_VEHICLE_SIZE_SHELL)
        relaxed = (
            is_true(vehicle.get("edge_contact"))
            or is_true(vehicle.get("partial_or_occluded"))
            or is_true(vehicle.get("duplicate_or_handoff"))
            or str(vehicle.get("vehicle_research_eligibility", "")) in {"weak_vehicle_layer", "far_small_vehicle_layer", "review_only_vehicle"}
        )
        shell = RELAXED_VEHICLE_SIZE_SHELL if relaxed else BASE_VEHICLE_SIZE_SHELL
        size_shell_contains = shell_contains(long_axis, short_axis, shell)
        flags = (
            f"edge={vehicle.get('edge_contact', '')};partial={vehicle.get('partial_or_occluded', '')};"
            f"duplicate_handoff={vehicle.get('duplicate_or_handoff', '')};ambiguity={spatial.get('ambiguity_status', '')}"
        )
        status = "posthoc_correspondence_iou_high" if best_iou >= 0.50 else "posthoc_correspondence_iou_weak_review"
        correspondences.append(
            {
                "scene": scene,
                "object_hypothesis_id": object_id,
                "correspondence_status": status,
                "correspondence_match_iou": fmt(best_iou, 4),
                "optical_track_or_observation_ids": f"track={best_row.get('main_tracker_track_id', '')};primary_det={best_row.get('primary_det_id', '')};secondary={best_row.get('secondary_det_ids', '')}",
                "sar_frame": str(sar_frame),
                "sar_gt_id": gt.get("final_id") or target_identity,
                "target_identity": target_identity,
                "sar_gt_center": f"{fmt(final_cx, 3)},{fmt(final_cy, 3)}",
                "sar_gt_width_height_or_rotated_box": f"w={fmt(final_w, 3)};h={fmt(final_h, 3)};heading={fmt(final_heading, 3)}",
                "sar_gt_radius_px": fmt(gt_radius, 3),
                "sar_gt_azimuth_deg": fmt(gt_az, 3),
                "optical_frame": str(optical_frame),
                "optical_bbox": ",".join(fmt(value, 3) for value in opt_bbox),
                "optical_bbox_width_height_area": f"w={fmt(ow, 3)};h={fmt(oh, 3)};area={fmt(optical_area, 3)};area_ratio={fmt(optical_area / 480000.0, 6)}",
                "optical_bbox_area_ratio": optical_area / 480000.0,
                "optical_bbox_width": ow,
                "optical_bbox_height": oh,
                "optical_bbox_aspect_ratio": fmt(optical_aspect, 4),
                "optical_bbox_bottom_y": fmt(y2, 3),
                "optical_bbox_bottom_y_norm": fmt(optical_bottom_y_norm, 4),
                "optical_object_state": f"eligibility={vehicle.get('vehicle_research_eligibility', '')};tier={vehicle.get('resolvability_tier', '')};spatial={spatial.get('spatial_prior_status', '')}",
                "primary_secondary_status": f"primary={spatial.get('uses_primary_observations', '')};secondary={spatial.get('uses_secondary_observations', '')}",
                "visibility_state": f"visibility={best_row.get('state_visibility_status', '')};uncertainty={best_row.get('state_uncertainty_status', '')};partial={best_row.get('partial_full_transition_state', '')};boundary={best_row.get('boundary_truncation_state', '')};multi={best_row.get('multi_observation_state', '')}",
                "edge_partial_duplicate_handoff_ambiguity_flags": flags,
                "vehicle_research_eligibility": vehicle.get("vehicle_research_eligibility", ""),
                "resolvability_tier": vehicle.get("resolvability_tier", ""),
                "spatial_prior_status": spatial.get("spatial_prior_status", ""),
                "temporal_window_contains_gt_frame": bool_text(temporal_contains),
                "azimuth_prior_contains_gt": az_contains,
                "vehicle_size_shell_contains_gt": bool_text(size_shell_contains),
                "base_vehicle_size_shell_contains_gt": bool_text(base_shell_contains),
                "range_shell_contains_gt": "",
                "sar_pseudocolor_path": gt.get("sar_pseudocolor_path", ""),
                "optical_path": gt.get("optical_path", ""),
                "review_optical_bbox": opt_bbox,
                "oty_primary_bbox": primary_box(best_row),
                "gt_cx": float(final_cx),
                "gt_cy": float(final_cy),
                "gt_w": float(final_w),
                "gt_h": float(final_h),
                "gt_heading": final_heading,
                "gt_long_axis_px": long_axis,
                "gt_short_axis_px": short_axis,
                "gt_aspect": aspect,
                "azimuth_prior_center_deg": az["center"],
                "azimuth_prior_start_deg": az["start"],
                "azimuth_prior_end_deg": az["end"],
                "azimuth_prior_width_deg": az["width"],
                "azimuth_error_to_center_deg": "" if az["center"] == "" else gt_az - float(az["center"]),
                "size_shell_mode": "relaxed_state_size_shell" if relaxed else "base_vehicle_size_shell",
                "notes": "posthoc correspondence hypothesis from optical bbox overlap; not identity truth; GT/SAR image are posthoc-only",
            }
        )
    return correspondences, {"skipped_counts": dict(skipped), "pair_iou_min": PAIR_IOU_MIN}


def build_shape_range_shells(correspondences: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    values = sorted(float(row["optical_bbox_area_ratio"]) for row in correspondences)
    if not values:
        return {}
    q1 = quantile(values, 1 / 3) or values[0]
    q2 = quantile(values, 2 / 3) or values[-1]
    bins = {
        "small_optical_area_posthoc_bin": [],
        "medium_optical_area_posthoc_bin": [],
        "large_optical_area_posthoc_bin": [],
    }
    for row in correspondences:
        area_ratio = float(row["optical_bbox_area_ratio"])
        radius = safe_float(row.get("sar_gt_radius_px"))
        if radius is None:
            continue
        if area_ratio <= q1:
            bins["small_optical_area_posthoc_bin"].append(radius)
        elif area_ratio <= q2:
            bins["medium_optical_area_posthoc_bin"].append(radius)
        else:
            bins["large_optical_area_posthoc_bin"].append(radius)
    shells: dict[str, dict[str, float]] = {}
    for name, radii in bins.items():
        if len(radii) >= 3:
            rmin = quantile(radii, 0.10)
            rmax = quantile(radii, 0.90)
        elif radii:
            rmin, rmax = min(radii), max(radii)
        else:
            continue
        shells[name] = {
            "area_q1": q1,
            "area_q2": q2,
            "radius_min": float(rmin or 0.0),
            "radius_max": float(rmax or 0.0),
            "n": float(len(radii)),
        }
    return shells


def shape_bin_for_area(area_ratio: float, shells: Mapping[str, Mapping[str, float]]) -> str:
    if not shells:
        return "not_available"
    q1 = next(iter(shells.values())).get("area_q1", 0.0)
    q2 = next(iter(shells.values())).get("area_q2", 0.0)
    if area_ratio <= q1:
        return "small_optical_area_posthoc_bin"
    if area_ratio <= q2:
        return "medium_optical_area_posthoc_bin"
    return "large_optical_area_posthoc_bin"


def patch_stats(image_path: Path, cx: float, cy: float, ax_box: tuple[float, float, float, float]) -> dict[str, Any]:
    if not image_path.exists():
        return {"sar_image_read_status": "missing"}
    try:
        with Image.open(image_path) as source:
            gray = source.convert("L")
            width, height = gray.size
            x1, y1, x2, y2 = ax_box
            x1i = max(0, int(math.floor(x1)))
            y1i = max(0, int(math.floor(y1)))
            x2i = min(width, int(math.ceil(x2)))
            y2i = min(height, int(math.ceil(y2)))
            if x2i <= x1i or y2i <= y1i:
                return {"sar_image_read_status": "empty_gt_box"}
            box_crop = gray.crop((x1i, y1i, x2i, y2i))
            box_values = list(box_crop.getdata())
            stat = ImageStat.Stat(box_crop)
            sorted_values = sorted(box_values)
            top_count = max(1, int(len(sorted_values) * 0.05))
            top5 = sorted_values[-top_count:]
            pad = 70
            ex1 = max(0, x1i - pad)
            ey1 = max(0, y1i - pad)
            ex2 = min(width, x2i + pad)
            ey2 = min(height, y2i + pad)
            expanded = gray.crop((ex1, ey1, ex2, ey2))
            expanded_values = list(expanded.getdata())
            bg_count = max(1, len(expanded_values) - len(box_values))
            bg_sum = max(0.0, float(sum(expanded_values) - sum(box_values)))
            bg_mean = bg_sum / bg_count
            max_value = max(box_values) if box_values else 0
            max_index = box_values.index(max_value) if box_values else 0
            crop_w = max(1, x2i - x1i)
            peak_x = x1i + (max_index % crop_w)
            peak_y = y1i + (max_index // crop_w)
            center_to_peak = math.hypot(peak_x - cx, peak_y - cy)
            box_mean = stat.mean[0] if stat.mean else 0.0
            top5_mean = sum(top5) / len(top5)
            return {
                "sar_image_read_status": "ok",
                "sar_box_mean_intensity": box_mean / 255.0,
                "sar_box_max_intensity": max_value / 255.0,
                "sar_box_top5_mean_intensity": top5_mean / 255.0,
                "sar_local_background_mean": bg_mean / 255.0,
                "sar_box_to_background_ratio": box_mean / max(bg_mean, 1e-6),
                "sar_peak_to_background_ratio": max_value / max(bg_mean, 1e-6),
                "sar_center_to_peak_distance_px": center_to_peak,
            }
    except OSError as exc:
        return {"sar_image_read_status": f"read_error:{exc}"}


def enrich_shell_and_shape(
    correspondences: list[dict[str, Any]],
    shape_shells: Mapping[str, Mapping[str, float]],
    object_frame_by_object: Mapping[tuple[str, str], Sequence[Mapping[str, str]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_object_pairs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in correspondences:
        by_object_pairs[(str(row["scene"]), str(row["object_hypothesis_id"]))].append(row)

    object_area_slopes: dict[tuple[str, str], float | None] = {}
    object_radius_slopes: dict[tuple[str, str], float | None] = {}
    for key, rows in by_object_pairs.items():
        optical_frames = [safe_float(row.get("optical_frame")) for row in rows]
        areas = [safe_float(row.get("optical_bbox_area_ratio")) for row in rows]
        sar_frames = [safe_float(row.get("sar_frame")) for row in rows]
        radii = [safe_float(row.get("sar_gt_radius_px")) for row in rows]
        object_area_slopes[key] = slope([x for x in optical_frames if x is not None], [y for y in areas if y is not None])
        object_radius_slopes[key] = slope([x for x in sar_frames if x is not None], [y for y in radii if y is not None])

    shell_rows: list[dict[str, Any]] = []
    shape_rows: list[dict[str, Any]] = []
    for row in correspondences:
        area_ratio = float(row["optical_bbox_area_ratio"])
        radius = float(row["sar_gt_radius_px"])
        shape_bin = shape_bin_for_area(area_ratio, shape_shells)
        shape_shell = shape_shells.get(shape_bin, {})
        rmin = shape_shell.get("radius_min")
        rmax = shape_shell.get("radius_max")
        range_contains = rmin is not None and rmax is not None and rmin <= radius <= rmax
        row["range_shell_contains_gt"] = bool_text(range_contains) if shape_shell else "not_available_no_shape_bin"
        az_width = safe_float(row.get("azimuth_prior_width_deg"))
        long_max = RELAXED_VEHICLE_SIZE_SHELL["long_axis_max_px"] if row["size_shell_mode"] == "relaxed_state_size_shell" else BASE_VEHICLE_SIZE_SHELL["long_axis_max_px"]
        shell_width_deg = math.degrees(2.0 * math.atan((long_max / 2.0) / max(radius, 1e-6)))
        ratio = shell_width_deg / az_width if az_width and az_width > 0 else None
        compression = "posthoc_size_shell_much_narrower_than_azimuth_sector" if ratio is not None and ratio < 0.5 else "posthoc_size_shell_not_narrow_or_no_azimuth_sector"
        az_contains = str(row.get("azimuth_prior_contains_gt", ""))
        failure_context = ""
        if az_contains == "false":
            failure_context = str(row.get("edge_partial_duplicate_handoff_ambiguity_flags", ""))
        shell_rows.append(
            {
                "scene": row["scene"],
                "object_hypothesis_id": row["object_hypothesis_id"],
                "sar_gt_id": row["sar_gt_id"],
                "sar_frame": row["sar_frame"],
                "gt_azimuth_deg": row["sar_gt_azimuth_deg"],
                "azimuth_prior_center_deg": fmt(row.get("azimuth_prior_center_deg"), 3),
                "azimuth_prior_start_deg": fmt(row.get("azimuth_prior_start_deg"), 3),
                "azimuth_prior_end_deg": fmt(row.get("azimuth_prior_end_deg"), 3),
                "azimuth_prior_width_deg": fmt(row.get("azimuth_prior_width_deg"), 3),
                "azimuth_error_to_center_deg": fmt(row.get("azimuth_error_to_center_deg"), 3),
                "azimuth_prior_contains_gt": row["azimuth_prior_contains_gt"],
                "azimuth_failure_context": failure_context,
                "size_shell_mode": row["size_shell_mode"],
                "gt_long_axis_px": fmt(row["gt_long_axis_px"], 3),
                "gt_short_axis_px": fmt(row["gt_short_axis_px"], 3),
                "gt_axis_aspect": fmt(row["gt_aspect"], 4),
                "vehicle_size_shell_contains_gt": row["vehicle_size_shell_contains_gt"],
                "base_vehicle_size_shell_contains_gt": row["base_vehicle_size_shell_contains_gt"],
                "size_shell_angular_width_at_gt_radius_deg": fmt(shell_width_deg, 3),
                "size_shell_to_azimuth_width_ratio": "" if ratio is None else fmt(ratio, 4),
                "size_shell_compression_effect": compression,
                "shape_range_shell_mode": shape_bin,
                "shape_range_shell_radius_min_px": "" if rmin is None else fmt(rmin, 3),
                "shape_range_shell_radius_max_px": "" if rmax is None else fmt(rmax, 3),
                "shape_range_shell_width_px": "" if rmin is None or rmax is None else fmt(rmax - rmin, 3),
                "range_shell_contains_gt": row["range_shell_contains_gt"],
                "range_shell_note": "posthoc optical-shape bin only; not runtime rule",
            }
        )
        ax1 = safe_float(row.get("gt_cx"), 0.0) - safe_float(row.get("gt_w"), 0.0) / 2.0
        ay1 = safe_float(row.get("gt_cy"), 0.0) - safe_float(row.get("gt_h"), 0.0) / 2.0
        ax2 = safe_float(row.get("gt_cx"), 0.0) + safe_float(row.get("gt_w"), 0.0) / 2.0
        ay2 = safe_float(row.get("gt_cy"), 0.0) + safe_float(row.get("gt_h"), 0.0) / 2.0
        image_path = Path(str(row.get("sar_pseudocolor_path") or sar_path(str(row["scene"]), int(row["sar_frame"]))))
        scatter = patch_stats(image_path, float(row["gt_cx"]), float(row["gt_cy"]), (ax1, ay1, ax2, ay2))
        key = (str(row["scene"]), str(row["object_hypothesis_id"]))
        area_slope = object_area_slopes.get(key)
        radius_slope = object_radius_slopes.get(key)
        if area_slope is None or radius_slope is None:
            trend_status = "insufficient_temporal_pairs"
        elif abs(area_slope) < 1e-5 or abs(radius_slope) < 1e-3:
            trend_status = "weak_or_flat_temporal_trend"
        elif area_slope * radius_slope < 0:
            trend_status = "opposite_sign_area_radius_trend_posthoc"
        else:
            trend_status = "same_sign_area_radius_trend_posthoc"
        scatter_note = "GT box shows localized scatter statistics" if scatter.get("sar_image_read_status") == "ok" else str(scatter.get("sar_image_read_status", "not_read"))
        shape_rows.append(
            {
                "scene": row["scene"],
                "object_hypothesis_id": row["object_hypothesis_id"],
                "sar_gt_id": row["sar_gt_id"],
                "sar_frame": row["sar_frame"],
                "optical_frame": row["optical_frame"],
                "optical_bbox_area_ratio": fmt(row["optical_bbox_area_ratio"], 6),
                "optical_bbox_height": fmt(row["optical_bbox_height"], 3),
                "optical_bbox_width": fmt(row["optical_bbox_width"], 3),
                "optical_bbox_aspect_ratio": row["optical_bbox_aspect_ratio"],
                "optical_bbox_bottom_y_norm": row["optical_bbox_bottom_y_norm"],
                "object_optical_area_slope_per_frame": "" if area_slope is None else fmt(area_slope, 8),
                "object_sar_radius_slope_per_frame": "" if radius_slope is None else fmt(radius_slope, 5),
                "optical_area_vs_sar_radius_trend_status": trend_status,
                "sar_gt_radius_px": row["sar_gt_radius_px"],
                "sar_gt_azimuth_deg": row["sar_gt_azimuth_deg"],
                "sar_gt_long_axis_px": fmt(row["gt_long_axis_px"], 3),
                "sar_gt_short_axis_px": fmt(row["gt_short_axis_px"], 3),
                "sar_gt_aspect": fmt(row["gt_aspect"], 4),
                "sar_box_mean_intensity": fmt(scatter.get("sar_box_mean_intensity"), 6),
                "sar_box_max_intensity": fmt(scatter.get("sar_box_max_intensity"), 6),
                "sar_box_top5_mean_intensity": fmt(scatter.get("sar_box_top5_mean_intensity"), 6),
                "sar_local_background_mean": fmt(scatter.get("sar_local_background_mean"), 6),
                "sar_box_to_background_ratio": fmt(scatter.get("sar_box_to_background_ratio"), 6),
                "sar_peak_to_background_ratio": fmt(scatter.get("sar_peak_to_background_ratio"), 6),
                "sar_center_to_peak_distance_px": fmt(scatter.get("sar_center_to_peak_distance_px"), 3),
                "scatter_observation_note": scatter_note,
                "posthoc_only_note": "SAR image and GT are used only for mechanism discovery, not runtime construction",
            }
        )
    return shell_rows, shape_rows


def scale_image_with_boxes(
    source: Image.Image,
    panel_size: tuple[int, int],
    boxes: Sequence[tuple[tuple[float, float, float, float], str, str]],
) -> Image.Image:
    panel_w, panel_h = panel_size
    image = source.convert("RGB")
    scale = min(panel_w / image.width, panel_h / image.height)
    new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (panel_w, panel_h), "#111827")
    ox = (panel_w - new_size[0]) // 2
    oy = (panel_h - new_size[1]) // 2
    panel.paste(resized, (ox, oy))
    draw = ImageDraw.Draw(panel)

    def project(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        return int(ox + x1 * scale), int(oy + y1 * scale), int(ox + x2 * scale), int(oy + y2 * scale)

    for box, label, color in boxes:
        x1, y1, x2, y2 = project(box)
        draw.rectangle((x1, y1, x2, y2), outline=color, width=5)
        draw.text((x1 + 6, max(6, y1 + 6)), label, font=FONTS["small"], fill=color)
    return panel


def scale_sar_with_gt(source: Image.Image, panel_size: tuple[int, int], row: Mapping[str, Any], spatial_row: Mapping[str, Any]) -> Image.Image:
    panel_w, panel_h = panel_size
    image = source.convert("RGB")
    scale = min(panel_w / image.width, panel_h / image.height)
    new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (panel_w, panel_h), "#111827")
    ox = (panel_w - new_size[0]) // 2
    oy = (panel_h - new_size[1]) // 2
    panel.paste(resized, (ox, oy))
    draw = ImageDraw.Draw(panel)

    def project_point(x: float, y: float) -> tuple[int, int]:
        return int(ox + x * scale), int(oy + y * scale)

    corners = rotated_box_corners(float(row["gt_cx"]), float(row["gt_cy"]), float(row["gt_w"]), float(row["gt_h"]), float(row["gt_heading"]))
    projected = [project_point(x, y) for x, y in corners]
    draw.line(projected + [projected[0]], fill="#22c55e", width=5)
    cxp, cyp = project_point(float(row["gt_cx"]), float(row["gt_cy"]))
    draw.ellipse((cxp - 5, cyp - 5, cxp + 5, cyp + 5), fill="#22c55e")
    draw.text((cxp + 8, cyp - 18), "SAR GT", font=FONTS["small"], fill="#22c55e")

    fan_c = project_point(FAN_CENTER_X, FAN_CENTER_Y)
    draw.ellipse((fan_c[0] - 5, fan_c[1] - 5, fan_c[0] + 5, fan_c[1] + 5), fill="#f97316")
    az_start = safe_float(row.get("azimuth_prior_start_deg"))
    az_end = safe_float(row.get("azimuth_prior_end_deg"))
    if az_start is not None and az_end is not None:
        for az, color in [(az_start, "#60a5fa"), (az_end, "#60a5fa"), (float(row["sar_gt_azimuth_deg"]), "#ef4444")]:
            rad = math.radians(az)
            end_x = FAN_CENTER_X + FAN_RADIUS_PX * math.sin(rad)
            end_y = FAN_CENTER_Y - FAN_RADIUS_PX * math.cos(rad)
            end_p = project_point(end_x, end_y)
            draw.line((fan_c[0], fan_c[1], end_p[0], end_p[1]), fill=color, width=3)
    return panel


def crop_gt_patch(image_path: Path, row: Mapping[str, Any], size: tuple[int, int] = (430, 430)) -> Image.Image:
    if not image_path.exists():
        return Image.new("RGB", size, "#e2e8f0")
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        cx, cy = float(row["gt_cx"]), float(row["gt_cy"])
        pad = max(float(row["gt_w"]), float(row["gt_h"]), 120.0)
        crop = (
            max(0, int(cx - pad)),
            max(0, int(cy - pad)),
            min(image.width, int(cx + pad)),
            min(image.height, int(cy + pad)),
        )
        patch = image.crop(crop)
        scale_x = patch.width / max(1, crop[2] - crop[0])
        patch = patch.resize(size, Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(patch)
        sx = size[0] / max(1, crop[2] - crop[0])
        sy = size[1] / max(1, crop[3] - crop[1])
        corners = rotated_box_corners(cx, cy, float(row["gt_w"]), float(row["gt_h"]), float(row["gt_heading"]))
        pts = [(int((x - crop[0]) * sx), int((y - crop[1]) * sy)) for x, y in corners]
        draw.line(pts + [pts[0]], fill="#22c55e", width=4)
        return patch


def render_page(
    row: Mapping[str, Any],
    shell_row: Mapping[str, Any],
    shape_row: Mapping[str, Any],
    out_path: Path,
) -> dict[str, Any]:
    page = Image.new("RGB", (1900, 2300), "#f8fafc")
    draw = ImageDraw.Draw(page)
    title = "OTY2 光学目标与 SAR GT 后验机制诊断"
    draw.text((60, 40), title, font=FONTS["title"], fill="#0f172a")
    tag_x = draw_tag(draw, (60, 94), "posthoc-only", "#dc2626")
    tag_x = draw_tag(draw, (tag_x, 94), f"方位覆盖={row['azimuth_prior_contains_gt']}", "#2563eb")
    tag_x = draw_tag(draw, (tag_x, 94), f"尺度壳={row['vehicle_size_shell_contains_gt']}", "#0f766e")
    draw_tag(draw, (tag_x, 94), f"范围壳={row['range_shell_contains_gt']}", "#a16207")
    draw.text((60, 145), f"场景：{row['scene']}  对象：{row['object_hypothesis_id']}  SAR GT：{row['sar_gt_id']}", font=FONTS["body"], fill="#334155")
    draw.text((60, 175), "SAR GT 和 SAR 图像只用于后验机制发现；不是 runtime prior，不是候选框评分，不是自动标注。", font=FONTS["small"], fill="#dc2626")

    optical_frame = int(row["optical_frame"])
    sar_frame = int(row["sar_frame"])
    opt_path = Path(str(row.get("optical_path") or optical_path(str(row["scene"]), optical_frame)))
    sar_img_path = Path(str(row.get("sar_pseudocolor_path") or sar_path(str(row["scene"]), sar_frame)))
    y = 240
    if opt_path.exists():
        with Image.open(opt_path) as opt_img:
            panel = scale_image_with_boxes(
                opt_img,
                (560, 420),
                [
                    (row["review_optical_bbox"], "GT对应光学框", "#f97316"),
                    (row["oty_primary_bbox"], "OTY主观测框", "#22c55e"),
                ],
            )
        page.paste(panel, (60, y))
    else:
        draw.rectangle((60, y, 620, y + 420), fill="#e2e8f0", outline="#94a3b8")
    draw.text((60, y - 30), f"光学帧 {optical_frame}", font=FONTS["h2"], fill="#0f172a")

    if sar_img_path.exists():
        with Image.open(sar_img_path) as sar_img:
            sar_panel = scale_sar_with_gt(sar_img, (650, 420), row, shell_row)
        page.paste(sar_panel, (680, y))
        patch = crop_gt_patch(sar_img_path, row)
        page.paste(patch, (1390, y))
    else:
        draw.rectangle((680, y, 1330, y + 420), fill="#e2e8f0", outline="#94a3b8")
        draw.rectangle((1390, y, 1820, y + 420), fill="#e2e8f0", outline="#94a3b8")
    draw.text((680, y - 30), f"SAR 帧 {sar_frame}：GT + 方位扇区示意", font=FONTS["h2"], fill="#0f172a")
    draw.text((1390, y - 30), "SAR GT 局部散射观察", font=FONTS["h2"], fill="#0f172a")

    draw_card(
        draw,
        (60, 710, 870, 320),
        "对应样本与时间/方位覆盖",
        [
            f"配对方式：同光学帧光学框 IoU={row['correspondence_match_iou']}；这是后验对应假设，不是身份真值。",
            f"时间窗覆盖 GT：{row['temporal_window_contains_gt_frame']}；SAR frame={row['sar_frame']}。",
            f"方位先验覆盖 GT：{row['azimuth_prior_contains_gt']}；GT az={row['sar_gt_azimuth_deg']}°；先验区间=[{shell_row['azimuth_prior_start_deg']}, {shell_row['azimuth_prior_end_deg']}]°。",
            f"方位误差到先验中心：{shell_row['azimuth_error_to_center_deg']}°。",
        ],
        border="#93c5fd",
    )
    draw_card(
        draw,
        (980, 710, 860, 320),
        "车辆尺度壳与范围探索",
        [
            f"GT 长/短轴：{shell_row['gt_long_axis_px']} / {shell_row['gt_short_axis_px']} px；aspect={shell_row['gt_axis_aspect']}。",
            f"尺度壳模式：{shell_row['size_shell_mode']}；覆盖 GT：{shell_row['vehicle_size_shell_contains_gt']}。",
            f"在 GT 半径处的尺度壳角宽约 {shell_row['size_shell_angular_width_at_gt_radius_deg']}°，相对当前方位扇区比例 {shell_row['size_shell_to_azimuth_width_ratio']}。",
            f"光学形态范围壳：{shell_row['shape_range_shell_mode']}；覆盖 GT：{shell_row['range_shell_contains_gt']}。",
        ],
        border="#86efac",
    )
    draw_card(
        draw,
        (60, 1070, 870, 360),
        "光学形态与时序探针",
        [
            f"光学框 area_ratio={shape_row['optical_bbox_area_ratio']}，h={shape_row['optical_bbox_height']}，bottom_y_norm={shape_row['optical_bbox_bottom_y_norm']}。",
            f"对象面积斜率/帧：{shape_row['object_optical_area_slope_per_frame']}；SAR 半径斜率/帧：{shape_row['object_sar_radius_slope_per_frame']}。",
            f"趋势状态：{shape_row['optical_area_vs_sar_radius_trend_status']}。",
            "这些趋势只用于后验机制探索；不能直接变成 runtime 距离规则。",
        ],
        border="#fbbf24",
    )
    draw_card(
        draw,
        (980, 1070, 860, 360),
        "SAR 散射/GT 形态观察",
        [
            f"box/background={shape_row['sar_box_to_background_ratio']}；peak/background={shape_row['sar_peak_to_background_ratio']}。",
            f"top5 mean={shape_row['sar_box_top5_mean_intensity']}；center-to-peak={shape_row['sar_center_to_peak_distance_px']} px。",
            f"散射观察：{shape_row['scatter_observation_note']}。",
            "GT 框主要反映 SAR 中目标呈现；散射外溢、背景杂波和框约定仍需后续审阅。",
        ],
        border="#c4b5fd",
    )
    draw_card(
        draw,
        (60, 1470, 1780, 300),
        "Runtime-safe / Posthoc-only 分离",
        [
            "Runtime-safe inputs：光学目标流、时间窗、方位映射、车辆物理尺寸假设、场景几何、目标状态。",
            "Posthoc-only inputs：SAR GT、SAR 图像内容、GT 覆盖率、人工最终框、后验 IoU、任何选择器结果。",
            "本页使用 SAR GT 与 SAR 图像是为了机制发现：看方位映射、尺度壳、光学形态和散射形态之间是否有关系。",
            "本页不输出最终候选框，不做评分，不训练/调阈值，不生成自动标注建议。",
        ],
        border="#fca5a5",
    )
    draw_wrapped(draw, (60, 1810), f"状态：{row['optical_object_state']}；flags：{row['edge_partial_duplicate_handoff_ambiguity_flags']}", FONTS["small"], "#475569", 1740, max_lines=4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page.save(out_path)
    return {"local_visualization_path": str(out_path)}


def select_samples(correspondences: Sequence[Mapping[str, Any]]) -> list[tuple[str, Mapping[str, Any]]]:
    selected: list[tuple[str, Mapping[str, Any]]] = []
    used: set[tuple[str, str]] = set()

    def add(role: str, predicate: Any) -> None:
        candidates = [row for row in correspondences if predicate(row)]
        candidates = sorted(candidates, key=lambda row: (row.get("scene", ""), row.get("object_hypothesis_id", ""), row.get("sar_frame", "")))
        for row in candidates:
            key = (str(row.get("sar_gt_id", "")), str(row.get("target_identity", "")))
            if key not in used:
                selected.append((role, row))
                used.add(key)
                return

    add("主研究车辆-方位和尺度覆盖", lambda row: row.get("vehicle_research_eligibility") == "main_research_vehicle" and row.get("azimuth_prior_contains_gt") == "true" and row.get("vehicle_size_shell_contains_gt") == "true")
    add("方位覆盖失败样本", lambda row: row.get("azimuth_prior_contains_gt") == "false")
    add("尺度壳失败样本", lambda row: row.get("vehicle_size_shell_contains_gt") == "false")
    add("远小车辆后验样本", lambda row: row.get("vehicle_research_eligibility") == "far_small_vehicle_layer")
    add("仅审阅车辆后验样本", lambda row: row.get("vehicle_research_eligibility") == "review_only_vehicle")
    add("GM_RM019 后验样本", lambda row: row.get("scene") == "GM_RM019")
    add("弱车覆盖样本", lambda row: row.get("vehicle_research_eligibility") == "weak_vehicle_layer" and row.get("azimuth_prior_contains_gt") == "true" and row.get("range_shell_contains_gt") == "true")
    add("范围壳失败样本", lambda row: row.get("range_shell_contains_gt") == "false")
    add("GM_RM019 方位失败样本", lambda row: row.get("scene") == "GM_RM019" and row.get("azimuth_prior_contains_gt") == "false")
    add("阻断对象后验样本", lambda row: row.get("vehicle_research_eligibility") == "blocked_vehicle_or_noise")
    add("GM_RM017 覆盖样本", lambda row: row.get("scene") == "GM_RM017" and row.get("azimuth_prior_contains_gt") == "true" and row.get("range_shell_contains_gt") == "true")
    if len(selected) < 6:
        for row in sorted(correspondences, key=lambda item: (item.get("scene", ""), item.get("vehicle_research_eligibility", ""), item.get("sar_frame", ""))):
            key = (str(row.get("sar_gt_id", "")), str(row.get("target_identity", "")))
            if key not in used:
                selected.append(("补充代表样本", row))
                used.add(key)
            if len(selected) >= 6:
                break
    return selected[:6]


def slug_role(role: str) -> str:
    mapping = {
        "主研究车辆-方位和尺度覆盖": "main_vehicle_covered",
        "方位覆盖失败样本": "azimuth_fail",
        "尺度壳失败样本": "size_shell_fail",
        "远小车辆后验样本": "far_small",
        "仅审阅车辆后验样本": "review_only",
        "GM_RM019 后验样本": "gmrm019",
        "弱车覆盖样本": "weak_vehicle_covered",
        "范围壳失败样本": "range_shell_fail",
        "GM_RM019 方位失败样本": "gmrm019_azimuth_fail",
        "阻断对象后验样本": "blocked_posthoc",
        "GM_RM017 覆盖样本": "gmrm017_covered",
        "补充代表样本": "extra",
    }
    return mapping.get(role, "sample")


def safe_file_part(value: Any) -> str:
    text = str(value or "na")
    for char in "\\/:*?\"<>|":
        text = text.replace(char, "_")
    return text


def render_visuals(
    timestamp: str,
    correspondences: list[dict[str, Any]],
    shell_rows: Sequence[Mapping[str, Any]],
    shape_rows: Sequence[Mapping[str, Any]],
) -> tuple[Path, list[dict[str, Any]]]:
    output_dir = OUTPUT_PARENT / f"oty2_gt_correspondence_mechanism_audit_{timestamp}"
    page_dir = output_dir / "gt_mechanism_pages"
    page_dir.mkdir(parents=True, exist_ok=True)
    sample_dir = SAMPLE_DIR / f"gt_mechanism_{timestamp}"
    sample_dir.mkdir(parents=True, exist_ok=True)
    shell_by_id = {(row["scene"], row["sar_gt_id"]): row for row in shell_rows}
    shape_by_id = {(row["scene"], row["sar_gt_id"]): row for row in shape_rows}
    samples = select_samples(correspondences)
    sample_keys = {(str(row.get("scene", "")), str(row.get("sar_gt_id", ""))): role for role, row in samples}
    visual_rows: list[dict[str, Any]] = []
    for row in correspondences:
        scene = str(row["scene"])
        gt_id = str(row["sar_gt_id"])
        object_token = safe_file_part(str(row["object_hypothesis_id"]).split("_")[-1] or "object")
        gt_token = safe_file_part(gt_id)
        local_path = page_dir / f"oty2_gt_mechanism_{safe_file_part(scene.lower())}_{object_token}_sar{int(row['sar_frame']):06d}_{gt_token}_{timestamp}.png"
        render_page(row, shell_by_id[(scene, gt_id)], shape_by_id[(scene, gt_id)], local_path)
        role = sample_keys.get((scene, gt_id), "")
        repo_path = ""
        if role:
            repo_sample_path = sample_dir / f"oty2_gt_mechanism_{slug_role(role)}_{safe_file_part(scene.lower())}_{object_token}_sar{int(row['sar_frame']):06d}_{gt_token}_{timestamp}.png"
            shutil.copyfile(local_path, repo_sample_path)
            repo_path = str(repo_sample_path)
        visual_rows.append(
            {
                "sample_role": role,
                "scene": scene,
                "object_hypothesis_id": row["object_hypothesis_id"],
                "sar_gt_id": gt_id,
                "sar_frame": row["sar_frame"],
                "vehicle_research_eligibility": row["vehicle_research_eligibility"],
                "azimuth_prior_contains_gt": row["azimuth_prior_contains_gt"],
                "vehicle_size_shell_contains_gt": row["vehicle_size_shell_contains_gt"],
                "range_shell_contains_gt": row["range_shell_contains_gt"],
                "local_visualization_path": str(local_path),
                "repo_sample_visualization_path": repo_path,
            }
        )
    write_csv(output_dir / "oty2_gt_correspondence_mechanism_visual_index.csv", visual_rows, VISUAL_SUMMARY_FIELDS)
    write_csv(REPORT_DIR / f"oty2_gt_correspondence_mechanism_visual_summary_{timestamp}.csv", visual_rows, VISUAL_SUMMARY_FIELDS)
    return output_dir, visual_rows


def count_by(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field, "")) for row in rows))


def coverage(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    total = len(rows)
    passed = sum(1 for row in rows if str(row.get(field, "")) == "true")
    failed = sum(1 for row in rows if str(row.get(field, "")) == "false")
    return {"total": total, "pass": passed, "fail": failed, "pass_rate": passed / total if total else None}


def median_field(rows: Sequence[Mapping[str, Any]], field: str) -> float | None:
    vals = [safe_float(row.get(field)) for row in rows]
    clean = [float(v) for v in vals if v is not None]
    return float(median(clean)) if clean else None


def build_summary(
    timestamp: str,
    correspondences: Sequence[Mapping[str, Any]],
    shell_rows: Sequence[Mapping[str, Any]],
    shape_rows: Sequence[Mapping[str, Any]],
    visual_rows: Sequence[Mapping[str, Any]],
    pairing_meta: Mapping[str, Any],
    shape_shells: Mapping[str, Mapping[str, float]],
    output_dir: Path,
) -> dict[str, Any]:
    xs_area = [float(row["optical_bbox_area_ratio"]) for row in correspondences]
    xs_height = [float(row["optical_bbox_height"]) for row in correspondences]
    xs_bottom = [safe_float(row["optical_bbox_bottom_y_norm"], 0.0) or 0.0 for row in correspondences]
    ys_radius = [safe_float(row["sar_gt_radius_px"], 0.0) or 0.0 for row in correspondences]
    temporal_help_counts = count_by(shape_rows, "optical_area_vs_sar_radius_trend_status")
    return {
        "timestamp": timestamp,
        "gt_correspondence_samples": len(correspondences),
        "pairing_meta": pairing_meta,
        "scene_counts": count_by(correspondences, "scene"),
        "vehicle_research_eligibility_counts": count_by(correspondences, "vehicle_research_eligibility"),
        "temporal_window_coverage": coverage(correspondences, "temporal_window_contains_gt_frame"),
        "azimuth_prior_coverage": coverage(correspondences, "azimuth_prior_contains_gt"),
        "vehicle_size_shell_coverage": coverage(correspondences, "vehicle_size_shell_contains_gt"),
        "base_vehicle_size_shell_coverage": coverage(correspondences, "base_vehicle_size_shell_contains_gt"),
        "shape_range_shell_coverage": coverage(correspondences, "range_shell_contains_gt"),
        "azimuth_width_median_deg": median_field(shell_rows, "azimuth_prior_width_deg"),
        "azimuth_error_median_deg": median_field(shell_rows, "azimuth_error_to_center_deg"),
        "size_shell_ratio_median": median_field(shell_rows, "size_shell_to_azimuth_width_ratio"),
        "sar_gt_long_axis_median_px": median_field(shell_rows, "gt_long_axis_px"),
        "sar_gt_short_axis_median_px": median_field(shell_rows, "gt_short_axis_px"),
        "sar_gt_aspect_median": median_field(shell_rows, "gt_axis_aspect"),
        "optical_area_vs_sar_radius_pearson": pearson(xs_area, ys_radius),
        "optical_height_vs_sar_radius_pearson": pearson(xs_height, ys_radius),
        "optical_bottom_y_vs_sar_radius_pearson": pearson(xs_bottom, ys_radius),
        "temporal_trend_status_counts": temporal_help_counts,
        "scatter_box_to_background_median": median_field(shape_rows, "sar_box_to_background_ratio"),
        "scatter_peak_to_background_median": median_field(shape_rows, "sar_peak_to_background_ratio"),
        "shape_shells_posthoc_only": shape_shells,
        "local_visualization_output_dir": str(output_dir),
        "local_visualization_count": len(correspondences),
        "remote_sample_visualization_count": sum(1 for row in visual_rows if row.get("repo_sample_visualization_path")),
        "boundary_flags": BOUNDARY_FLAGS,
    }


def render_report(path: Path, timestamp: str, summary: Mapping[str, Any], visual_rows: Sequence[Mapping[str, Any]], sources: Mapping[str, str]) -> None:
    sample_rows = [row for row in visual_rows if row.get("repo_sample_visualization_path")]
    lines = [
        "# OTY2 GT 对应机制后验审计报告",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本轮允许使用 SAR GT 和 SAR 图像内容，但只用于 posthoc mechanism discovery / audit。GT、SAR 图像、覆盖率和后验误差不得写入当前 runtime prior construction。",
        "",
        "## 输入边界",
        "",
        "- Runtime-safe inputs：光学目标流、时间窗、方位映射、车辆物理尺寸假设、场景几何、目标状态。",
        "- Posthoc-only inputs：SAR GT、SAR 图像内容、GT 覆盖率、人工最终框、后验 IoU、选择器结果。",
        "- 本报告使用 posthoc-only inputs 做机制发现，不输出自动标注建议，不训练或调阈值，不输出候选框评分，不声明身份真值。",
        "",
        "## 样本",
        "",
        f"- GT 对应样本数：`{summary['gt_correspondence_samples']}`。",
        f"- 场景分布：`{json.dumps(summary['scene_counts'], ensure_ascii=False)}`。",
        f"- 配对跳过统计：`{json.dumps(summary['pairing_meta']['skipped_counts'], ensure_ascii=False)}`。",
        "- 配对方法：同一场景、同一光学帧，用 review_queue 光学框与 OTY1t 主观测框 IoU 匹配；这是后验对应假设，不是身份真值。",
        "",
        "## 方位映射覆盖",
        "",
        f"- 方位扇区覆盖：`{json.dumps(summary['azimuth_prior_coverage'], ensure_ascii=False)}`。",
        f"- 方位扇区宽度中位数：`{summary['azimuth_width_median_deg']}` 度。",
        f"- GT 方位相对先验中心误差中位数：`{summary['azimuth_error_median_deg']}` 度。",
        "解释：当前方位扇区通常较宽，覆盖率主要说明“方位映射是否把 GT 放进大扇区”，不能等同为精定位成功。失败样本需要结合边缘、遮挡、重复、交接和远小状态继续审阅。",
        "",
        "## 车辆物理尺度壳",
        "",
        f"- relaxed/base 尺度壳覆盖：`{json.dumps(summary['vehicle_size_shell_coverage'], ensure_ascii=False)}`。",
        f"- base 尺度壳覆盖：`{json.dumps(summary['base_vehicle_size_shell_coverage'], ensure_ascii=False)}`。",
        f"- SAR GT 长轴/短轴/长短比中位数：`{summary['sar_gt_long_axis_median_px']}` / `{summary['sar_gt_short_axis_median_px']}` / `{summary['sar_gt_aspect_median']}`。",
        f"- 尺度壳角宽 / 当前方位扇区宽度中位比例：`{summary['size_shell_ratio_median']}`。",
        "观察：车辆尺度壳对目标 footprint 尺寸有明显约束，和方位扇区相交时有压缩潜力；但没有运行时 range anchor 时，它不能单独给出绝对距离位置。",
        "",
        "## 光学框形态和距离向探索",
        "",
        f"- 光学框面积比例 vs SAR GT 半径 Pearson：`{summary['optical_area_vs_sar_radius_pearson']}`。",
        f"- 光学框高度 vs SAR GT 半径 Pearson：`{summary['optical_height_vs_sar_radius_pearson']}`。",
        f"- 光学框 bottom_y_norm vs SAR GT 半径 Pearson：`{summary['optical_bottom_y_vs_sar_radius_pearson']}`。",
        f"- posthoc 光学面积 bin 范围壳覆盖：`{json.dumps(summary['shape_range_shell_coverage'], ensure_ascii=False)}`。",
        f"- 对象时序趋势状态：`{json.dumps(summary['temporal_trend_status_counts'], ensure_ascii=False)}`。",
        "解释：这些相关和范围壳都是后验机制探针，不是 runtime 回归器。若趋势较弱或受状态破坏，下一步应先分完整/遮挡/截断/远小目标，再评估是否有可迁移的弱先验。",
        "",
        "## SAR 散射和 GT 框形态",
        "",
        f"- box/background 强度比中位数：`{summary['scatter_box_to_background_median']}`。",
        f"- peak/background 强度比中位数：`{summary['scatter_peak_to_background_median']}`。",
        "观察：GT 框内通常能看到局部峰值和车辆长轴 footprint，但框内均值可能受背景、彩色显示映射、散射外溢和遮挡影响。此处只支持机制观察，不能直接成为评分器。",
        "",
        "## YOLO A/B 建议",
        "",
        "不建议直接替换主线 YOLO。下一步可以做小样本 A/B：同一帧、同一 vehicle-like 主线，比较主研究车辆覆盖、远小弱目标比例、框稳定性、轨迹连续性、duplicate/handoff、光学形态与 SAR GT 机制变量相关性、方位扇区覆盖率和尺度壳覆盖/压缩率。",
        "",
        "## 远端代表样例",
        "",
        "| role | scene | object | sar_gt_id | sar_frame | azimuth | size_shell | range_shell | path |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in sample_rows:
        lines.append(
            f"| {row['sample_role']} | {row['scene']} | {row['object_hypothesis_id']} | {row['sar_gt_id']} | {row['sar_frame']} | {row['azimuth_prior_contains_gt']} | {row['vehicle_size_shell_contains_gt']} | {row['range_shell_contains_gt']} | `{row['repo_sample_visualization_path']}` |"
        )
    lines.extend(
        [
            "",
            "## 输出和数据源",
            "",
        ]
    )
    for key, value in sources.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Boundary Flags", ""])
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_yolo_plan(path: Path, timestamp: str, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 YOLO A/B 机制对比计划",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本计划不替换主线 YOLO，不下载或提交权重，不训练或调阈值。目标是比较更强 YOLO 是否改善“可用于光学到 SAR 迁移机制研究”的 vehicle-like 对象，而不是只比较检测数量。",
        "",
        "## 对比设计",
        "",
        "1. 固定同一批场景、光学帧、SAR GT 表和软件同步 24:50 时间契约。",
        "2. baseline YOLO 与 candidate YOLO 分别输出 OTY0 detection table。",
        "3. 使用同一 OTY1/OTY1t 对象流构造逻辑，避免把 detector 差异和 tracker 规则差异混在一起。",
        "4. 只评估 vehicle-like objects；非车辆类别保留记录但不进入主指标。",
        "5. 运行车辆准入审计和本 GT 对应机制审计，比较机制变量，不生成自动标注建议。",
        "",
        "## 核心指标",
        "",
        "- 主研究车辆覆盖：有多少 GT 对应到 main_research_vehicle。",
        "- 远小弱目标比例：far_small / unresolved_tiny 是否膨胀。",
        "- 目标框稳定性：bbox 面积、高度、bottom_y 的时序抖动。",
        "- 轨迹连续性：visible_frame_count、track_frame_span、断裂/短轨迹比例。",
        "- duplicate / handoff 率：辅助观测、多观测、ID 切换风险。",
        "- 光学框与 SAR GT 机制变量相关性：area/height/bottom_y 与 SAR radius/azimuth 的关系。",
        "- 方位扇区覆盖率和宽度：覆盖是否改善，扇区是否更窄。",
        "- 车辆尺度壳覆盖率和压缩率：尺度壳是否更常覆盖 GT，是否减少过宽方位扇带。",
        "- normal / relaxed / review-only / blocked 分布变化。",
        "",
        "## 当前基线",
        "",
        "```json",
        json.dumps(
            {
                "gt_correspondence_samples": summary.get("gt_correspondence_samples"),
                "azimuth_prior_coverage": summary.get("azimuth_prior_coverage"),
                "vehicle_size_shell_coverage": summary.get("vehicle_size_shell_coverage"),
                "shape_correlations": {
                    "area_ratio_vs_radius": summary.get("optical_area_vs_sar_radius_pearson"),
                    "height_vs_radius": summary.get("optical_height_vs_sar_radius_pearson"),
                    "bottom_y_vs_radius": summary.get("optical_bottom_y_vs_sar_radius_pearson"),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## 建议",
        "",
        "建议先做小样本 A/B，而不是马上替换主线。只有当 candidate YOLO 同时提升主研究车辆覆盖、轨迹稳定性、方位/尺度机制覆盖，并且不显著增加远小弱目标和 handoff/review-only 负担时，才值得进入更大范围对比。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    tables = load_tables(args)
    spatial_by_key = rows_by_key(tables["spatial_rows"])
    temporal_by_key = rows_by_key(tables["temporal_rows"])
    vehicle_by_key = rows_by_key(tables["vehicle_rows"])
    object_by_frame, object_by_object = group_object_frames(tables["object_frame_rows"])

    correspondences, pairing_meta = build_correspondences(tables, spatial_by_key, temporal_by_key, vehicle_by_key, object_by_frame)
    shape_shells = build_shape_range_shells(correspondences)
    shell_rows, shape_rows = enrich_shell_and_shape(correspondences, shape_shells, object_by_object)
    output_dir, visual_rows = render_visuals(timestamp, correspondences, shell_rows, shape_rows)

    correspondence_csv = REPORT_DIR / f"oty2_gt_correspondence_mechanism_audit_{timestamp}.csv"
    shell_csv = REPORT_DIR / f"oty2_azimuth_vehicle_size_shell_audit_{timestamp}.csv"
    shape_csv = REPORT_DIR / f"oty2_optical_shape_temporal_feature_probe_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_gt_correspondence_mechanism_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_gt_correspondence_mechanism_summary_{timestamp}.json"
    yolo_plan_md = REPORT_DIR / f"oty2_yolo_ab_comparison_mechanism_plan_{timestamp}.md"

    write_csv(correspondence_csv, correspondences, CORRESPONDENCE_FIELDS)
    write_csv(shell_csv, shell_rows, SHELL_FIELDS)
    write_csv(shape_csv, shape_rows, SHAPE_FIELDS)
    summary = build_summary(timestamp, correspondences, shell_rows, shape_rows, visual_rows, pairing_meta, shape_shells, output_dir)
    write_json(summary_json, summary)
    sources = {
        "final_gt_csv": str(Path(args.final_gt_csv)),
        "review_queue_csv": str(Path(args.review_queue_csv)),
        "spatial_priors_csv": str(Path(args.spatial_priors_csv) if args.spatial_priors_csv else latest_path("oty2_object_runtime_spatial_priors_*.csv")),
        "temporal_windows_csv": str(Path(args.temporal_windows_csv) if args.temporal_windows_csv else latest_path("oty2_object_sar_temporal_windows_*.csv")),
        "vehicle_eligibility_csv": str(Path(args.vehicle_eligibility_csv) if args.vehicle_eligibility_csv else latest_path("oty2_vehicle_research_eligibility_audit_*.csv")),
        "object_frame_state_csv": str(Path(args.object_frame_state_csv) if args.object_frame_state_csv else DEFAULT_OBJECT_DIR / "oty1t_object_frame_state_timeseries_generalized.csv"),
        "local_full_visual_output": str(output_dir),
    }
    render_report(report_md, timestamp, summary, visual_rows, sources)
    render_yolo_plan(yolo_plan_md, timestamp, summary)
    summary.update(
        {
            "correspondence_csv": str(correspondence_csv),
            "shell_csv": str(shell_csv),
            "shape_csv": str(shape_csv),
            "report_md": str(report_md),
            "summary_json": str(summary_json),
            "yolo_plan_md": str(yolo_plan_md),
            "visual_summary_csv": str(REPORT_DIR / f"oty2_gt_correspondence_mechanism_visual_summary_{timestamp}.csv"),
            "sample_dir": str(SAMPLE_DIR / f"gt_mechanism_{timestamp}"),
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--final-gt-csv", default=str(DEFAULT_GT_CSV))
    parser.add_argument("--review-queue-csv", default=str(DEFAULT_REVIEW_QUEUE_CSV))
    parser.add_argument("--spatial-priors-csv", default="")
    parser.add_argument("--temporal-windows-csv", default="")
    parser.add_argument("--vehicle-eligibility-csv", default="")
    parser.add_argument("--object-visual-summary-csv", default="")
    parser.add_argument("--object-frame-state-csv", default="")
    parser.add_argument("--object-hypotheses-csv", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
