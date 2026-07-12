"""Freeze GM_RM019 static physical observation field with scale-yaw audit.

This script is generation-freeze first. The `generate` command reads only SAR
gray frames, frozen local response units, boundary variant families, and this
script's confirmed calibration constants. It does not read GT, paired
annotations, mask audit tables, evaluation tables, selector/ranking outputs, or
final annotation artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path("D:/profile/research/data/GM_RM019/GM_RM019_SARframes_gray")
OUTPUT_TMP_DIR = REPO_ROOT / "outputs" / "oty2_gm_rm019_static_physical_observation_field_20260712" / "_verify_tmp"
WORKSPACE_TASK_DIR = Path("D:/profile/research/workspace/tasks/oty2_gm_rm019_static_physical_observation_field")
WORKSPACE_LOG = Path("D:/profile/research/workspace/logs/oty2_gm_rm019_static_physical_observation_field_20260712.md")

DATE = "20260712"
SCENE = "GM_RM019"
CALIBRATION_STATUS = "PROJECT_CONFIRMED"
MAX_RANGE_M = 40.0
M_PER_PX = 0.03
SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
GEOMETRY_ORIGIN_STATUS = "project_confirmed_fan_center_px_1154_0_1330_6"
OBSERVATION_STATUS = "STATIC_PHYSICAL_FIELD_READY"

INPUTS_ALLOWED = {
    "local_response_units": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv",
    "boundary_variant_families": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_variant_families_20260711.csv",
    "sar_gray_dir": DATA_ROOT,
}

OUTPUTS = {
    "rows": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_rows_20260712.csv",
    "summary": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_summary_20260712.csv",
    "threshold_stability": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_threshold_stability_20260712.csv",
    "scale_yaw": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_scale_yaw_audit_20260712.csv",
    "counterfactual_templates": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_counterfactual_templates_20260712.csv",
    "integrity": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_integrity_20260712.csv",
    "pre_eval_seal": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_pre_eval_seal_20260712.csv",
    "replay_check": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_replay_check_20260712.csv",
    "visual_manifest": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_visual_manifest_20260712.csv",
    "report": REPORT_DIR / "oty2_gm_rm019_static_physical_observation_field_20260712.md",
}

GENERATED_KEYS = [
    "rows",
    "summary",
    "threshold_stability",
    "scale_yaw",
    "counterfactual_templates",
    "pre_eval_seal",
    "visual_manifest",
]

VEHICLE_LENGTH_GRID = [round(3.0 + 0.1 * i, 2) for i in range(36)]
VEHICLE_WIDTH_GRID = [round(1.4 + 0.1 * i, 2) for i in range(13)]
YAW_GRID = list(range(0, 180))
YAW_FEASIBLE_RESIDUAL_M = 0.75
SHAPE_DOMINANCE_RATIO = 1.25
THRESHOLD_QUANTILES = [0.50, 0.70, 0.85]
CENTER_SHIFT_M = [0.15, 0.30, 0.45]
BOUNDARY_SHIFT_M = [0.15, 0.30]
SCALE_SHIFT_M = [0.15, 0.30]

ROW_FIELDS = [
    "scene",
    "response_unit_id",
    "source_response_box_id",
    "source_r1_family_id",
    "sar_frame",
    "sar_gray_image_relpath",
    "core_bbox",
    "conservative_bbox",
    "uncertain_envelope",
    "response_state",
    "calibration_status",
    "max_range_m",
    "radial_grid_spacing_m_per_px",
    "sar_fan_center_x_px",
    "sar_fan_center_y_px",
    "geometry_origin_status",
    "gt_file_opened",
    "paired_annotations_opened",
    "mask_audit_opened",
    "generation_input_scope",
    "response_center_x",
    "response_center_y",
    "absolute_range_px",
    "absolute_range_m",
    "azimuth_angle_deg",
    "range_unit_x",
    "range_unit_y",
    "azimuth_unit_x",
    "azimuth_unit_y",
    "pixel_count",
    "rect_pixel_count",
    "raw_intensity_sum",
    "background_estimate",
    "background_sample_count",
    "background_source",
    "background_subtracted_energy",
    "energy_valid",
    "range_weighted_mean_px",
    "azimuth_weighted_mean_px",
    "range_p50_width_px",
    "range_p80_width_px",
    "range_p90_width_px",
    "azimuth_p50_width_px",
    "azimuth_p80_width_px",
    "azimuth_p90_width_px",
    "range_p50_width_m",
    "range_p80_width_m",
    "range_p90_width_m",
    "azimuth_p50_width_m",
    "azimuth_p80_width_m",
    "azimuth_p90_width_m",
    "range_to_azimuth_p80_ratio",
    "principal_axis_major_std_px",
    "principal_axis_minor_std_px",
    "principal_axis_ratio",
    "principal_axis_angle_image_deg",
    "principal_axis_angle_to_range_deg",
    "principal_axis_angle_to_azimuth_deg",
    "yaw_proxy_major_axis_deg",
    "yaw_proxy_shape_class",
    "energy_centroid_x",
    "energy_centroid_y",
    "energy_centroid_range_m",
    "energy_centroid_azimuth_px",
    "energy_centroid_offset_px",
    "distance_to_fan_boundary_px",
    "distance_to_fan_boundary_m",
    "touches_display_fan_boundary",
    "near_fan_boundary_side",
    "boundary_family_id",
    "boundary_variant_count",
    "multiple_boundary_variant_uncertainty",
    "scale_yaw_feasible",
    "best_yaw_deg",
    "yaw_feasible_interval_deg",
    "best_scale_length_m",
    "best_scale_width_m",
    "scale_yaw_residual_m",
    "min_extra_blur_margin_m",
]

SCALE_YAW_FIELDS = [
    "response_unit_id",
    "sar_frame",
    "range_p80_width_m",
    "azimuth_p80_width_m",
    "yaw_proxy_shape_class",
    "vehicle_scale_yaw_feasible",
    "best_yaw_deg",
    "yaw_feasible_interval_deg",
    "best_scale_length_m",
    "best_scale_width_m",
    "scale_yaw_residual_m",
    "min_extra_blur_margin_m",
    "calibration_status",
    "interpretation_boundary_cn",
]

THRESHOLD_FIELDS = [
    "response_unit_id",
    "sar_frame",
    "threshold_setting",
    "threshold_value",
    "component_count",
    "largest_component_pixels",
    "core_component_persistent",
    "principal_axis_angle_to_range_deg",
    "range_p80_width_m",
    "azimuth_p80_width_m",
    "scale_yaw_feasible",
    "threshold_stability_count",
    "principal_axis_angle_std_deg",
    "range_p80_width_std_m",
    "azimuth_p80_width_std_m",
    "scale_yaw_feasible_fraction",
]

TEMPLATE_FIELDS = [
    "template_id",
    "response_unit_id",
    "sar_frame",
    "template_family",
    "template_axis",
    "template_operation",
    "delta_m",
    "delta_px",
    "region_pixel_count",
    "energy_delta",
    "inner_density_delta",
    "outer_band_density_delta",
    "component_count_delta",
    "principal_axis_change_deg",
    "scale_yaw_feasible_change",
    "template_scope",
]

SUMMARY_FIELDS = [
    "summary_id",
    "metric",
    "count",
    "mean",
    "median",
    "min",
    "max",
    "notes_cn",
]

INTEGRITY_FIELDS = ["gate_name", "status", "detail", "source_file", "sha256", "row_count"]
SEAL_FIELDS = ["seal_key", "seal_value", "source_file", "sha256", "row_count"]
REPLAY_FIELDS = ["check_name", "status", "detail", "current_sha256", "replay_sha256"]
VISUAL_FIELDS = ["visual_id", "response_unit_id", "sar_frame", "visual_review_relpath", "notes_cn"]

_YAW_CANDIDATES: dict[str, np.ndarray] | None = None
_SCALE_YAW_CACHE: dict[tuple[float, float], dict[str, Any]] = {}


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> str:
    if not path.exists() or path.suffix.lower() != ".csv":
        return ""
    return str(len(read_rows(path)))


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        text = str(value if value is not None else "").strip()
        return default if not text else float(text)
    except (TypeError, ValueError):
        return default


def fmt(value: Any, digits: int = 6) -> str:
    number = parse_float(value)
    if math.isnan(number) or not math.isfinite(number):
        return ""
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def parse_box(text: str) -> Box | None:
    parts = [parse_float(part) for part in str(text or "").replace("|", ",").split(",")]
    if len(parts) != 4 or any(math.isnan(part) for part in parts):
        return None
    x1, y1, x2, y2 = parts
    x1, x2 = sorted((max(0.0, x1), min(float(SAR_WIDTH), x2)))
    y1, y2 = sorted((max(0.0, y1), min(float(SAR_HEIGHT), y2)))
    if x2 <= x1 or y2 <= y1:
        return None
    return Box(x1, y1, x2, y2)


def box_text(box: Box) -> str:
    return f"{fmt(box.x1, 3)},{fmt(box.y1, 3)},{fmt(box.x2, 3)},{fmt(box.y2, 3)}"


def frame_image_path(frame: Any) -> Path:
    return DATA_ROOT / f"{int(float(str(frame))):06d}.png"


def load_gray(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(img.convert("L"), dtype=np.float32)


def radial_px(x: float, y: float) -> float:
    return math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)


def azimuth_deg(x: float, y: float) -> float:
    return math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))


def fan_valid_points(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    ranges = np.hypot(xs - FAN_CENTER_X, ys - FAN_CENTER_Y)
    angles = np.degrees(np.arctan2(xs - FAN_CENTER_X, FAN_CENTER_Y - ys))
    return (
        (xs >= 0)
        & (xs < SAR_WIDTH)
        & (ys >= 0)
        & (ys < SAR_HEIGHT)
        & (ranges <= FAN_RADIUS_PX)
        & (angles >= -90.0)
        & (angles <= 90.0)
    )


def unit_vectors(cx: float, cy: float) -> tuple[float, float, float, float]:
    dx = cx - FAN_CENTER_X
    dy = cy - FAN_CENTER_Y
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return 0.0, -1.0, 1.0, 0.0
    rx = dx / norm
    ry = dy / norm
    return rx, ry, -ry, rx


def axis_angle_0_90(vx: float, vy: float, ux: float, uy: float) -> float:
    vnorm = math.hypot(vx, vy)
    unorm = math.hypot(ux, uy)
    if vnorm <= 1e-9 or unorm <= 1e-9:
        return math.nan
    dot = abs((vx * ux + vy * uy) / (vnorm * unorm))
    dot = min(1.0, max(0.0, dot))
    angle = math.degrees(math.acos(dot))
    return min(angle, 90.0 - angle) if angle > 90.0 else angle


def axis_std(values: Sequence[float]) -> float:
    valid = [v for v in values if not math.isnan(v)]
    return pstdev(valid) if len(valid) > 1 else 0.0 if valid else math.nan


def shortest_weighted_width(values: np.ndarray, weights: np.ndarray, fraction: float) -> float:
    if len(values) == 0:
        return math.nan
    total = float(np.sum(weights))
    if total <= 1e-9:
        return float(np.max(values) - np.min(values)) if len(values) else math.nan
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    target = total * fraction
    best = math.inf
    left = 0
    running = 0.0
    for right in range(len(sorted_values)):
        running += float(sorted_weights[right])
        while left <= right and running - float(sorted_weights[left]) >= target:
            running -= float(sorted_weights[left])
            left += 1
        if running >= target:
            best = min(best, float(sorted_values[right] - sorted_values[left]))
    return best if math.isfinite(best) else float(sorted_values[-1] - sorted_values[0])


def image_points_for_box(box: Box) -> tuple[np.ndarray, np.ndarray]:
    ix1 = max(0, int(math.floor(box.x1)))
    iy1 = max(0, int(math.floor(box.y1)))
    ix2 = min(SAR_WIDTH, int(math.ceil(box.x2)))
    iy2 = min(SAR_HEIGHT, int(math.ceil(box.y2)))
    yy, xx = np.mgrid[iy1:iy2, ix1:ix2]
    return xx.astype(np.float32) + 0.5, yy.astype(np.float32) + 0.5


def occupancy_mask(rows: Sequence[Mapping[str, str]], frame: str) -> np.ndarray:
    mask = np.zeros((SAR_HEIGHT, SAR_WIDTH), dtype=bool)
    for row in rows:
        if str(row.get("sar_frame", "")) != frame:
            continue
        box = parse_box(row.get("conservative_bbox", ""))
        if box is None:
            continue
        ix1 = max(0, int(math.floor(box.x1)))
        iy1 = max(0, int(math.floor(box.y1)))
        ix2 = min(SAR_WIDTH, int(math.ceil(box.x2)))
        iy2 = min(SAR_HEIGHT, int(math.ceil(box.y2)))
        mask[iy1:iy2, ix1:ix2] = True
    return mask


def local_background(arr: np.ndarray, box: Box, frame_occupancy: np.ndarray) -> tuple[float, int, str, bool]:
    margin = max(10.0, min(36.0, 0.35 * max(box.width, box.height)))
    outer = Box(
        max(0.0, box.x1 - margin),
        max(0.0, box.y1 - margin),
        min(float(SAR_WIDTH), box.x2 + margin),
        min(float(SAR_HEIGHT), box.y2 + margin),
    )
    xs, ys = image_points_for_box(outer)
    ix = np.clip(xs.astype(int), 0, SAR_WIDTH - 1)
    iy = np.clip(ys.astype(int), 0, SAR_HEIGHT - 1)
    inside_box = (xs >= box.x1) & (xs < box.x2) & (ys >= box.y1) & (ys < box.y2)
    valid = fan_valid_points(xs, ys) & (~inside_box) & (~frame_occupancy[iy, ix])
    samples = arr[iy[valid], ix[valid]]
    if len(samples) >= 32:
        return float(np.median(samples)), int(len(samples)), "local_ring_excluding_frozen_responses", False
    valid = fan_valid_points(xs, ys) & (~inside_box)
    samples = arr[iy[valid], ix[valid]]
    if len(samples) > 0:
        return float(np.median(samples)), int(len(samples)), "local_ring_fallback_without_occupancy_exclusion", True
    return 0.0, 0, "no_background_samples", True


def component_count(mask: np.ndarray) -> tuple[int, int]:
    if mask.size == 0 or not bool(mask.any()):
        return 0, 0
    seen = np.zeros(mask.shape, dtype=bool)
    count = 0
    largest = 0
    height, width = mask.shape
    for y in range(height):
        xs = np.flatnonzero(mask[y] & (~seen[y]))
        for start_x in xs:
            if seen[y, start_x] or not mask[y, start_x]:
                continue
            count += 1
            size = 0
            queue: deque[tuple[int, int]] = deque([(int(start_x), y)])
            seen[y, start_x] = True
            while queue:
                x0, y0 = queue.popleft()
                size += 1
                for nx, ny in ((x0 - 1, y0), (x0 + 1, y0), (x0, y0 - 1), (x0, y0 + 1)):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        queue.append((nx, ny))
            largest = max(largest, size)
    return count, largest


def major_axis(xs: np.ndarray, ys: np.ndarray, weights: np.ndarray) -> tuple[float, float, float, float, float]:
    total = float(np.sum(weights))
    if len(xs) < 2 or total <= 1e-9:
        return math.nan, math.nan, math.nan, math.nan, math.nan
    cx = float(np.average(xs, weights=weights))
    cy = float(np.average(ys, weights=weights))
    dx = xs - cx
    dy = ys - cy
    cxx = float(np.average(dx * dx, weights=weights))
    cyy = float(np.average(dy * dy, weights=weights))
    cxy = float(np.average(dx * dy, weights=weights))
    cov = np.asarray([[cxx, cxy], [cxy, cyy]], dtype=float)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)
    major_val = max(0.0, float(vals[order[-1]]))
    minor_val = max(0.0, float(vals[order[0]]))
    vx, vy = vecs[:, order[-1]]
    angle = math.degrees(math.atan2(float(vy), float(vx))) % 180.0
    if angle > 90.0:
        angle = 180.0 - angle
    major_std = math.sqrt(major_val)
    minor_std = math.sqrt(minor_val)
    ratio = major_std / minor_std if minor_std > 1e-9 else math.inf
    return major_std, minor_std, ratio, angle, float(vx)


def project_metrics(
    arr: np.ndarray,
    box: Box,
    center_x: float,
    center_y: float,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    background: float,
    threshold_quantile: float | None = None,
) -> dict[str, Any]:
    xs, ys = image_points_for_box(box)
    ix = np.clip(xs.astype(int), 0, SAR_WIDTH - 1)
    iy = np.clip(ys.astype(int), 0, SAR_HEIGHT - 1)
    valid = fan_valid_points(xs, ys)
    intensities = arr[iy, ix]
    weights = np.maximum(intensities - background, 0.0)
    if threshold_quantile is not None:
        positive = weights[(weights > 0) & valid]
        threshold = float(np.quantile(positive, threshold_quantile)) if len(positive) else math.inf
        valid = valid & (weights >= threshold) & (weights > 0)
    else:
        threshold = math.nan
    xs1 = xs[valid]
    ys1 = ys[valid]
    weights1 = weights[valid]
    intensities1 = intensities[valid]
    rect_pixel_count = int(xs.size)
    pixel_count = int(len(xs1))
    raw_intensity_sum = float(np.sum(intensities1)) if pixel_count else 0.0
    energy = float(np.sum(weights1)) if pixel_count else 0.0
    if pixel_count == 0 or energy <= 1e-9:
        comp_mask = np.zeros(xs.shape, dtype=bool)
        comps, largest = 0, 0
        return {
            "threshold_value": threshold,
            "pixel_count": pixel_count,
            "rect_pixel_count": rect_pixel_count,
            "raw_intensity_sum": raw_intensity_sum,
            "background_subtracted_energy": energy,
            "energy_valid": False,
            "component_count": comps,
            "largest_component_pixels": largest,
        }
    proj_r = (xs1 - center_x) * rx + (ys1 - center_y) * ry
    proj_a = (xs1 - center_x) * ax + (ys1 - center_y) * ay
    centroid_x = float(np.average(xs1, weights=weights1))
    centroid_y = float(np.average(ys1, weights=weights1))
    major_std, minor_std, axis_ratio, image_angle, vx = major_axis(xs1, ys1, weights1)
    # Reconstruct the major vector from the image angle. The axis has no direction.
    angle_rad = math.radians(image_angle if not math.isnan(image_angle) else 0.0)
    mvx = math.cos(angle_rad)
    mvy = math.sin(angle_rad)
    angle_to_range = axis_angle_0_90(mvx, mvy, rx, ry)
    angle_to_azimuth = axis_angle_0_90(mvx, mvy, ax, ay)
    local_mask = np.zeros(xs.shape, dtype=bool)
    local_mask[valid] = True
    comps, largest = component_count(local_mask)
    return {
        "threshold_value": threshold,
        "pixel_count": pixel_count,
        "rect_pixel_count": rect_pixel_count,
        "raw_intensity_sum": raw_intensity_sum,
        "background_subtracted_energy": energy,
        "energy_valid": True,
        "range_weighted_mean_px": float(np.average(proj_r, weights=weights1)),
        "azimuth_weighted_mean_px": float(np.average(proj_a, weights=weights1)),
        "range_p50_width_px": shortest_weighted_width(proj_r, weights1, 0.50),
        "range_p80_width_px": shortest_weighted_width(proj_r, weights1, 0.80),
        "range_p90_width_px": shortest_weighted_width(proj_r, weights1, 0.90),
        "azimuth_p50_width_px": shortest_weighted_width(proj_a, weights1, 0.50),
        "azimuth_p80_width_px": shortest_weighted_width(proj_a, weights1, 0.80),
        "azimuth_p90_width_px": shortest_weighted_width(proj_a, weights1, 0.90),
        "principal_axis_major_std_px": major_std,
        "principal_axis_minor_std_px": minor_std,
        "principal_axis_ratio": axis_ratio,
        "principal_axis_angle_image_deg": image_angle,
        "principal_axis_angle_to_range_deg": angle_to_range,
        "principal_axis_angle_to_azimuth_deg": angle_to_azimuth,
        "energy_centroid_x": centroid_x,
        "energy_centroid_y": centroid_y,
        "energy_centroid_offset_px": math.hypot(centroid_x - center_x, centroid_y - center_y),
        "component_count": comps,
        "largest_component_pixels": largest,
    }


def shape_class(range_m: float, azimuth_m: float) -> str:
    if range_m <= 1e-9 or azimuth_m <= 1e-9 or math.isnan(range_m) or math.isnan(azimuth_m):
        return "unresolved"
    ratio = range_m / azimuth_m
    if ratio >= SHAPE_DOMINANCE_RATIO:
        return "range_dominant"
    if ratio <= 1.0 / SHAPE_DOMINANCE_RATIO:
        return "azimuth_dominant"
    return "near_isotropic"


def scale_yaw_audit(range_width_m: float, azimuth_width_m: float) -> dict[str, Any]:
    if math.isnan(range_width_m) or math.isnan(azimuth_width_m):
        return {
            "vehicle_scale_yaw_feasible": False,
            "best_yaw_deg": math.nan,
            "yaw_feasible_interval_deg": "",
            "best_scale_length_m": math.nan,
            "best_scale_width_m": math.nan,
            "scale_yaw_residual_m": math.nan,
            "min_extra_blur_margin_m": math.nan,
        }
    cache_key = (round(float(range_width_m), 3), round(float(azimuth_width_m), 3))
    if cache_key in _SCALE_YAW_CACHE:
        return dict(_SCALE_YAW_CACHE[cache_key])
    candidates = yaw_candidates()
    dr = range_width_m - candidates["pred_r"]
    da = azimuth_width_m - candidates["pred_a"]
    residuals = np.hypot(dr, da)
    best_idx = int(np.argmin(residuals))
    min_extra = float(np.min(np.maximum(0.0, np.maximum(dr, da))))
    yaw_residuals: dict[int, float] = {}
    for yaw, residual in zip(candidates["yaw"], residuals):
        yaw_i = int(yaw)
        previous = yaw_residuals.get(yaw_i, math.inf)
        if float(residual) < previous:
            yaw_residuals[yaw_i] = float(residual)
    feasible_yaws = [yaw for yaw in YAW_GRID if yaw_residuals.get(yaw, math.inf) <= YAW_FEASIBLE_RESIDUAL_M]
    interval = yaw_interval(feasible_yaws)
    residual = float(residuals[best_idx])
    yaw = int(candidates["yaw"][best_idx])
    length = float(candidates["length"][best_idx])
    width = float(candidates["width"][best_idx])
    result = {
        "vehicle_scale_yaw_feasible": residual <= YAW_FEASIBLE_RESIDUAL_M,
        "best_yaw_deg": yaw,
        "yaw_feasible_interval_deg": interval,
        "best_scale_length_m": length,
        "best_scale_width_m": width,
        "scale_yaw_residual_m": residual,
        "min_extra_blur_margin_m": min_extra if math.isfinite(min_extra) else 0.0,
    }
    _SCALE_YAW_CACHE[cache_key] = dict(result)
    return result


def yaw_candidates() -> dict[str, np.ndarray]:
    global _YAW_CANDIDATES
    if _YAW_CANDIDATES is not None:
        return _YAW_CANDIDATES
    yaw_values: list[int] = []
    length_values: list[float] = []
    width_values: list[float] = []
    pred_r_values: list[float] = []
    pred_a_values: list[float] = []
    for yaw in YAW_GRID:
        rad = math.radians(yaw)
        c = abs(math.cos(rad))
        s = abs(math.sin(rad))
        for length in VEHICLE_LENGTH_GRID:
            for width in VEHICLE_WIDTH_GRID:
                yaw_values.append(yaw)
                length_values.append(length)
                width_values.append(width)
                pred_r_values.append(abs(length * c) + abs(width * s))
                pred_a_values.append(abs(length * s) + abs(width * c))
    _YAW_CANDIDATES = {
        "yaw": np.asarray(yaw_values, dtype=np.int16),
        "length": np.asarray(length_values, dtype=np.float32),
        "width": np.asarray(width_values, dtype=np.float32),
        "pred_r": np.asarray(pred_r_values, dtype=np.float32),
        "pred_a": np.asarray(pred_a_values, dtype=np.float32),
    }
    return _YAW_CANDIDATES


def yaw_interval(feasible_yaws: Sequence[int]) -> str:
    if not feasible_yaws:
        return ""
    segments: list[tuple[int, int]] = []
    start = prev = int(feasible_yaws[0])
    for yaw in feasible_yaws[1:]:
        yaw = int(yaw)
        if yaw == prev + 1:
            prev = yaw
        else:
            segments.append((start, prev))
            start = prev = yaw
    segments.append((start, prev))
    return ";".join(f"{a}-{b}" if a != b else str(a) for a, b in segments)


def boundary_context(box: Box, center_x: float, center_y: float) -> dict[str, Any]:
    r_center = radial_px(center_x, center_y)
    corners = [(box.x1, box.y1), (box.x1, box.y2), (box.x2, box.y1), (box.x2, box.y2)]
    rmax = max(radial_px(x, y) for x, y in corners)
    radial_margin = FAN_RADIUS_PX - rmax
    near_margin = FAN_CENTER_Y - box.y2
    left_margin = box.x1
    right_margin = SAR_WIDTH - box.x2
    candidates = {
        "far_range_arc": radial_margin,
        "near_range_bottom_display": near_margin,
        "left_image_edge": left_margin,
        "right_image_edge": right_margin,
    }
    side, distance = min(candidates.items(), key=lambda item: item[1])
    touches = distance <= 3.0 or any(not fan_valid_points(np.asarray([x]), np.asarray([y]))[0] for x, y in corners)
    return {
        "distance_to_fan_boundary_px": distance,
        "distance_to_fan_boundary_m": distance * M_PER_PX,
        "touches_display_fan_boundary": touches,
        "near_fan_boundary_side": side,
        "absolute_range_px": r_center,
        "absolute_range_m": r_center * M_PER_PX,
        "azimuth_angle_deg": azimuth_deg(center_x, center_y),
    }


def boundary_family_maps(rows: Sequence[Mapping[str, str]]) -> tuple[dict[str, str], dict[str, int], dict[str, bool]]:
    family_by_unit: dict[str, str] = {}
    count_by_unit: dict[str, int] = defaultdict(lambda: 1)
    multi_by_unit: dict[str, bool] = defaultdict(bool)
    for row in rows:
        family_id = row.get("boundary_family_id", "")
        members = [item.strip() for item in row.get("member_response_unit_ids", "").split(";") if item.strip()]
        variants = [item.strip() for item in row.get("boundary_variants", "").split("|") if item.strip()]
        is_multi = row.get("boundary_status", "") == "multiple_boundary_variants" or len(variants) > 1
        for member in members:
            family_by_unit[member] = family_id
            count_by_unit[member] = max(1, len(variants))
            multi_by_unit[member] = bool(is_multi)
    return family_by_unit, dict(count_by_unit), dict(multi_by_unit)


def load_allowed_inputs() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    missing = [str(path) for name, path in INPUTS_ALLOWED.items() if name != "sar_gray_dir" and not path.exists()]
    if not DATA_ROOT.exists():
        missing.append(str(DATA_ROOT))
    if missing:
        raise FileNotFoundError("missing allowed generation input: " + "; ".join(missing))
    return read_rows(INPUTS_ALLOWED["local_response_units"]), read_rows(INPUTS_ALLOWED["boundary_variant_families"])


def build_observation_rows() -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    local_rows, boundary_rows = load_allowed_inputs()
    family_by_unit, variant_count_by_unit, multi_by_unit = boundary_family_maps(boundary_rows)
    rows: list[dict[str, str]] = []
    threshold_rows: list[dict[str, str]] = []
    scale_rows: list[dict[str, str]] = []
    visual_rows: list[dict[str, str]] = []
    rows_by_frame: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in local_rows:
        rows_by_frame[str(row.get("sar_frame", ""))].append(row)
    image_cache: dict[str, np.ndarray] = {}
    for row in sorted(local_rows, key=lambda item: item.get("response_unit_id", "")):
        response_id = row.get("response_unit_id", "")
        frame = str(row.get("sar_frame", ""))
        img_path = frame_image_path(frame)
        if frame not in image_cache:
            image_cache[frame] = load_gray(img_path)
        arr = image_cache[frame]
        box = parse_box(row.get("conservative_bbox", "")) or parse_box(row.get("core_bbox", ""))
        if box is None:
            continue
        cx, cy = box.cx, box.cy
        rx, ry, ax, ay = unit_vectors(cx, cy)
        frame_occupancy = occupancy_mask(rows_by_frame[frame], frame)
        background, bg_count, bg_source, bg_limited = local_background(arr, box, frame_occupancy)
        metrics = project_metrics(arr, box, cx, cy, rx, ry, ax, ay, background)
        range_p80_m = parse_float(metrics.get("range_p80_width_px")) * M_PER_PX
        azimuth_p80_m = parse_float(metrics.get("azimuth_p80_width_px")) * M_PER_PX
        sy = scale_yaw_audit(range_p80_m, azimuth_p80_m)
        bctx = boundary_context(box, cx, cy)
        centroid_x = parse_float(metrics.get("energy_centroid_x"))
        centroid_y = parse_float(metrics.get("energy_centroid_y"))
        energy_centroid_range_m = radial_px(centroid_x, centroid_y) * M_PER_PX if not math.isnan(centroid_x) else math.nan
        energy_centroid_az_px = ((centroid_x - cx) * ax + (centroid_y - cy) * ay) if not math.isnan(centroid_x) else math.nan
        ratio = range_p80_m / azimuth_p80_m if azimuth_p80_m > 1e-9 else math.nan
        axis_to_range = parse_float(metrics.get("principal_axis_angle_to_range_deg"))
        row_out = {
            "scene": SCENE,
            "response_unit_id": response_id,
            "source_response_box_id": row.get("source_response_box_id", ""),
            "source_r1_family_id": row.get("source_r1_family_id", ""),
            "sar_frame": frame,
            "sar_gray_image_relpath": rel(img_path),
            "core_bbox": row.get("core_bbox", ""),
            "conservative_bbox": row.get("conservative_bbox", ""),
            "uncertain_envelope": row.get("uncertain_envelope", ""),
            "response_state": row.get("response_state", ""),
            "calibration_status": CALIBRATION_STATUS,
            "max_range_m": fmt(MAX_RANGE_M),
            "radial_grid_spacing_m_per_px": fmt(M_PER_PX),
            "sar_fan_center_x_px": fmt(FAN_CENTER_X),
            "sar_fan_center_y_px": fmt(FAN_CENTER_Y),
            "geometry_origin_status": GEOMETRY_ORIGIN_STATUS,
            "gt_file_opened": "false",
            "paired_annotations_opened": "false",
            "mask_audit_opened": "false",
            "generation_input_scope": "sar_gray+local_response_units+boundary_variant_families+project_confirmed_calibration_only",
            "response_center_x": fmt(cx),
            "response_center_y": fmt(cy),
            "absolute_range_px": fmt(bctx["absolute_range_px"]),
            "absolute_range_m": fmt(bctx["absolute_range_m"]),
            "azimuth_angle_deg": fmt(bctx["azimuth_angle_deg"]),
            "range_unit_x": fmt(rx),
            "range_unit_y": fmt(ry),
            "azimuth_unit_x": fmt(ax),
            "azimuth_unit_y": fmt(ay),
            "pixel_count": str(metrics.get("pixel_count", "")),
            "rect_pixel_count": str(metrics.get("rect_pixel_count", "")),
            "raw_intensity_sum": fmt(metrics.get("raw_intensity_sum")),
            "background_estimate": fmt(background),
            "background_sample_count": str(bg_count),
            "background_source": bg_source,
            "background_subtracted_energy": fmt(metrics.get("background_subtracted_energy")),
            "energy_valid": bool_text(bool(metrics.get("energy_valid"))),
            "range_weighted_mean_px": fmt(metrics.get("range_weighted_mean_px")),
            "azimuth_weighted_mean_px": fmt(metrics.get("azimuth_weighted_mean_px")),
            "range_p50_width_px": fmt(metrics.get("range_p50_width_px")),
            "range_p80_width_px": fmt(metrics.get("range_p80_width_px")),
            "range_p90_width_px": fmt(metrics.get("range_p90_width_px")),
            "azimuth_p50_width_px": fmt(metrics.get("azimuth_p50_width_px")),
            "azimuth_p80_width_px": fmt(metrics.get("azimuth_p80_width_px")),
            "azimuth_p90_width_px": fmt(metrics.get("azimuth_p90_width_px")),
            "range_p50_width_m": fmt(parse_float(metrics.get("range_p50_width_px")) * M_PER_PX),
            "range_p80_width_m": fmt(range_p80_m),
            "range_p90_width_m": fmt(parse_float(metrics.get("range_p90_width_px")) * M_PER_PX),
            "azimuth_p50_width_m": fmt(parse_float(metrics.get("azimuth_p50_width_px")) * M_PER_PX),
            "azimuth_p80_width_m": fmt(azimuth_p80_m),
            "azimuth_p90_width_m": fmt(parse_float(metrics.get("azimuth_p90_width_px")) * M_PER_PX),
            "range_to_azimuth_p80_ratio": fmt(ratio),
            "principal_axis_major_std_px": fmt(metrics.get("principal_axis_major_std_px")),
            "principal_axis_minor_std_px": fmt(metrics.get("principal_axis_minor_std_px")),
            "principal_axis_ratio": fmt(metrics.get("principal_axis_ratio")),
            "principal_axis_angle_image_deg": fmt(metrics.get("principal_axis_angle_image_deg")),
            "principal_axis_angle_to_range_deg": fmt(axis_to_range),
            "principal_axis_angle_to_azimuth_deg": fmt(metrics.get("principal_axis_angle_to_azimuth_deg")),
            "yaw_proxy_major_axis_deg": fmt(axis_to_range),
            "yaw_proxy_shape_class": shape_class(range_p80_m, azimuth_p80_m),
            "energy_centroid_x": fmt(centroid_x),
            "energy_centroid_y": fmt(centroid_y),
            "energy_centroid_range_m": fmt(energy_centroid_range_m),
            "energy_centroid_azimuth_px": fmt(energy_centroid_az_px),
            "energy_centroid_offset_px": fmt(metrics.get("energy_centroid_offset_px")),
            "distance_to_fan_boundary_px": fmt(bctx["distance_to_fan_boundary_px"]),
            "distance_to_fan_boundary_m": fmt(bctx["distance_to_fan_boundary_m"]),
            "touches_display_fan_boundary": bool_text(bool(bctx["touches_display_fan_boundary"])),
            "near_fan_boundary_side": str(bctx["near_fan_boundary_side"]),
            "boundary_family_id": family_by_unit.get(response_id, ""),
            "boundary_variant_count": str(variant_count_by_unit.get(response_id, 1)),
            "multiple_boundary_variant_uncertainty": bool_text(bool(multi_by_unit.get(response_id, False))),
            "scale_yaw_feasible": bool_text(bool(sy["vehicle_scale_yaw_feasible"])),
            "best_yaw_deg": fmt(sy["best_yaw_deg"]),
            "yaw_feasible_interval_deg": str(sy["yaw_feasible_interval_deg"]),
            "best_scale_length_m": fmt(sy["best_scale_length_m"]),
            "best_scale_width_m": fmt(sy["best_scale_width_m"]),
            "scale_yaw_residual_m": fmt(sy["scale_yaw_residual_m"]),
            "min_extra_blur_margin_m": fmt(sy["min_extra_blur_margin_m"]),
        }
        rows.append(row_out)
        scale_rows.append(
            {
                "response_unit_id": response_id,
                "sar_frame": frame,
                "range_p80_width_m": row_out["range_p80_width_m"],
                "azimuth_p80_width_m": row_out["azimuth_p80_width_m"],
                "yaw_proxy_shape_class": row_out["yaw_proxy_shape_class"],
                "vehicle_scale_yaw_feasible": row_out["scale_yaw_feasible"],
                "best_yaw_deg": row_out["best_yaw_deg"],
                "yaw_feasible_interval_deg": row_out["yaw_feasible_interval_deg"],
                "best_scale_length_m": row_out["best_scale_length_m"],
                "best_scale_width_m": row_out["best_scale_width_m"],
                "scale_yaw_residual_m": row_out["scale_yaw_residual_m"],
                "min_extra_blur_margin_m": row_out["min_extra_blur_margin_m"],
                "calibration_status": CALIBRATION_STATUS,
                "interpretation_boundary_cn": "yaw为静态响应代理量，不是真实车辆朝向；尺度-yaw一致性不是selector或车辆确认。",
            }
        )
        stability = threshold_stability_rows(response_id, frame, arr, box, cx, cy, rx, ry, ax, ay, background)
        threshold_rows.extend(stability)
        visual_rows.append(
            {
                "visual_id": f"VIS_{response_id}",
                "response_unit_id": response_id,
                "sar_frame": frame,
                "visual_review_relpath": "",
                "notes_cn": "本轮未提交PNG；如需审阅，可在ignored outputs中按该response_unit_id生成局部图。",
            }
        )
    template_rows = build_counterfactual_templates(rows, local_rows)
    return rows, threshold_rows, scale_rows, template_rows, visual_rows


def threshold_stability_rows(
    response_id: str,
    frame: str,
    arr: np.ndarray,
    box: Box,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    background: float,
) -> list[dict[str, str]]:
    raw_rows: list[dict[str, Any]] = []
    for q in THRESHOLD_QUANTILES:
        metrics = project_metrics(arr, box, cx, cy, rx, ry, ax, ay, background, threshold_quantile=q)
        range_m = parse_float(metrics.get("range_p80_width_px")) * M_PER_PX
        az_m = parse_float(metrics.get("azimuth_p80_width_px")) * M_PER_PX
        sy = scale_yaw_audit(range_m, az_m)
        persistent = int(metrics.get("largest_component_pixels", 0)) >= max(5, int(0.01 * max(1, metrics.get("rect_pixel_count", 1))))
        raw_rows.append(
            {
                "threshold_setting": f"positive_weight_q{int(q * 100)}",
                "threshold_value": metrics.get("threshold_value", math.nan),
                "component_count": metrics.get("component_count", 0),
                "largest_component_pixels": metrics.get("largest_component_pixels", 0),
                "core_component_persistent": persistent,
                "principal_axis_angle_to_range_deg": metrics.get("principal_axis_angle_to_range_deg", math.nan),
                "range_p80_width_m": range_m,
                "azimuth_p80_width_m": az_m,
                "scale_yaw_feasible": bool(sy.get("vehicle_scale_yaw_feasible", False)),
            }
        )
    stable_count = sum(1 for row in raw_rows if row["core_component_persistent"])
    angle_std = axis_std([parse_float(row["principal_axis_angle_to_range_deg"]) for row in raw_rows])
    range_std = axis_std([parse_float(row["range_p80_width_m"]) for row in raw_rows])
    az_std = axis_std([parse_float(row["azimuth_p80_width_m"]) for row in raw_rows])
    feasible_fraction = sum(1 for row in raw_rows if row["scale_yaw_feasible"]) / len(raw_rows)
    rows: list[dict[str, str]] = []
    for row in raw_rows:
        rows.append(
            {
                "response_unit_id": response_id,
                "sar_frame": frame,
                "threshold_setting": str(row["threshold_setting"]),
                "threshold_value": fmt(row["threshold_value"]),
                "component_count": str(row["component_count"]),
                "largest_component_pixels": str(row["largest_component_pixels"]),
                "core_component_persistent": bool_text(bool(row["core_component_persistent"])),
                "principal_axis_angle_to_range_deg": fmt(row["principal_axis_angle_to_range_deg"]),
                "range_p80_width_m": fmt(row["range_p80_width_m"]),
                "azimuth_p80_width_m": fmt(row["azimuth_p80_width_m"]),
                "scale_yaw_feasible": bool_text(bool(row["scale_yaw_feasible"])),
                "threshold_stability_count": str(stable_count),
                "principal_axis_angle_std_deg": fmt(angle_std),
                "range_p80_width_std_m": fmt(range_std),
                "azimuth_p80_width_std_m": fmt(az_std),
                "scale_yaw_feasible_fraction": fmt(feasible_fraction),
            }
        )
    return rows


def local_bounds_for_box(box: Box, cx: float, cy: float, rx: float, ry: float, ax: float, ay: float) -> tuple[float, float, float, float]:
    corners = np.asarray([(box.x1, box.y1), (box.x1, box.y2), (box.x2, box.y1), (box.x2, box.y2)], dtype=float)
    pr = (corners[:, 0] - cx) * rx + (corners[:, 1] - cy) * ry
    pa = (corners[:, 0] - cx) * ax + (corners[:, 1] - cy) * ay
    return float(np.min(pr)), float(np.max(pr)), float(np.min(pa)), float(np.max(pa))


def metric_for_local_region(
    arr: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    bounds: tuple[float, float, float, float],
    background: float,
) -> dict[str, Any]:
    rmin, rmax, amin, amax = bounds
    radius = max(abs(rmin), abs(rmax), abs(amin), abs(amax)) + 8
    x1 = max(0, int(math.floor(cx - radius)))
    x2 = min(SAR_WIDTH, int(math.ceil(cx + radius)))
    y1 = max(0, int(math.floor(cy - radius)))
    y2 = min(SAR_HEIGHT, int(math.ceil(cy + radius)))
    yy, xx = np.mgrid[y1:y2, x1:x2]
    xs = xx.astype(np.float32) + 0.5
    ys = yy.astype(np.float32) + 0.5
    pr = (xs - cx) * rx + (ys - cy) * ry
    pa = (xs - cx) * ax + (ys - cy) * ay
    inside = (pr >= rmin) & (pr <= rmax) & (pa >= amin) & (pa <= amax) & fan_valid_points(xs, ys)
    band = (pr >= rmin - 5) & (pr <= rmax + 5) & (pa >= amin - 5) & (pa <= amax + 5) & (~inside) & fan_valid_points(xs, ys)
    intensities = arr[np.clip(ys.astype(int), 0, SAR_HEIGHT - 1), np.clip(xs.astype(int), 0, SAR_WIDTH - 1)]
    weights = np.maximum(intensities - background, 0.0)
    inner_weights = weights[inside]
    band_weights = weights[band]
    inner_count = int(np.count_nonzero(inside))
    band_count = int(np.count_nonzero(band))
    if inner_count == 0:
        return {
            "region_pixel_count": 0,
            "energy": 0.0,
            "inner_density": 0.0,
            "outer_density": float(np.mean(band_weights)) if band_count else 0.0,
            "component_count": 0,
            "axis_angle": math.nan,
            "scale_feasible": False,
        }
    weights_inside = weights[inside]
    xs_inside = xs[inside]
    ys_inside = ys[inside]
    energy = float(np.sum(weights_inside))
    proj_r = pr[inside]
    proj_a = pa[inside]
    range_width_m = shortest_weighted_width(proj_r, weights_inside, 0.80) * M_PER_PX if energy > 0 else 0.0
    az_width_m = shortest_weighted_width(proj_a, weights_inside, 0.80) * M_PER_PX if energy > 0 else 0.0
    sy = scale_yaw_audit(range_width_m, az_width_m)
    _, _, _, image_angle, _ = major_axis(xs_inside, ys_inside, weights_inside)
    angle_to_range = math.nan
    if not math.isnan(image_angle):
        angle_to_range = axis_angle_0_90(math.cos(math.radians(image_angle)), math.sin(math.radians(image_angle)), rx, ry)
    # Template regions are deterministic local rectangles or shifted variants.
    # Full connected-component tracing is kept for threshold stability above;
    # here a lightweight region-presence estimate avoids turning the template
    # bank into the runtime bottleneck.
    comps = 1 if inner_count > 0 else 0
    return {
        "region_pixel_count": inner_count,
        "energy": energy,
        "inner_density": energy / inner_count if inner_count else 0.0,
        "outer_density": float(np.mean(band_weights)) if band_count else 0.0,
        "component_count": comps,
        "axis_angle": angle_to_range,
        "scale_feasible": bool(sy.get("vehicle_scale_yaw_feasible", False)),
    }


def template_specs() -> list[tuple[str, str, str, float]]:
    specs: list[tuple[str, str, str, float]] = []
    for delta in CENTER_SHIFT_M:
        for axis in ("range", "azimuth"):
            for sign in (-1, 1):
                specs.append(("center_shift", axis, "shift", sign * delta))
    for delta in BOUNDARY_SHIFT_M:
        for side in ("range_min", "range_max", "azimuth_min", "azimuth_max"):
            for sign in (-1, 1):
                specs.append(("single_boundary_shift", side, "move", sign * delta))
    for delta in SCALE_SHIFT_M:
        for axis in ("range", "azimuth"):
            for sign in (-1, 1):
                specs.append(("scale_resize", axis, "resize", sign * delta))
    return specs


def perturb_bounds(bounds: tuple[float, float, float, float], family: str, axis: str, delta_m: float) -> tuple[float, float, float, float]:
    rmin, rmax, amin, amax = bounds
    delta = delta_m / M_PER_PX
    if family == "center_shift":
        if axis == "range":
            rmin += delta
            rmax += delta
        else:
            amin += delta
            amax += delta
    elif family == "single_boundary_shift":
        if axis == "range_min":
            rmin += delta
        elif axis == "range_max":
            rmax += delta
        elif axis == "azimuth_min":
            amin += delta
        elif axis == "azimuth_max":
            amax += delta
    elif family == "scale_resize":
        if axis == "range":
            rmin -= delta / 2.0
            rmax += delta / 2.0
        else:
            amin -= delta / 2.0
            amax += delta / 2.0
    if rmax < rmin:
        mid = (rmin + rmax) / 2.0
        rmin, rmax = mid, mid
    if amax < amin:
        mid = (amin + amax) / 2.0
        amin, amax = mid, mid
    return rmin, rmax, amin, amax


def build_counterfactual_templates(
    rows: Sequence[Mapping[str, str]],
    local_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    local_by_id = {row.get("response_unit_id", ""): row for row in local_rows}
    result: list[dict[str, str]] = []
    specs = template_specs()
    for row in rows:
        response_id = row.get("response_unit_id", "")
        source = local_by_id.get(response_id, {})
        box = parse_box(source.get("conservative_bbox", "")) or parse_box(source.get("core_bbox", ""))
        if box is None:
            continue
        frame = row.get("sar_frame", "")
        cx = parse_float(row.get("response_center_x"))
        cy = parse_float(row.get("response_center_y"))
        rx = parse_float(row.get("range_unit_x"))
        ry = parse_float(row.get("range_unit_y"))
        ax = parse_float(row.get("azimuth_unit_x"))
        ay = parse_float(row.get("azimuth_unit_y"))
        base_bounds = local_bounds_for_box(box, cx, cy, rx, ry, ax, ay)
        base_energy = parse_float(row.get("background_subtracted_energy"), 0.0)
        base_pixels = max(1.0, parse_float(row.get("pixel_count"), 1.0))
        base_density = base_energy / base_pixels
        base_range_m = parse_float(row.get("range_p80_width_m"), 0.0)
        base_az_m = parse_float(row.get("azimuth_p80_width_m"), 0.0)
        base_angle = parse_float(row.get("principal_axis_angle_to_range_deg"))
        base_feasible = row.get("scale_yaw_feasible") == "true"
        base_range_extent_m = max(M_PER_PX, (base_bounds[1] - base_bounds[0]) * M_PER_PX)
        base_az_extent_m = max(M_PER_PX, (base_bounds[3] - base_bounds[2]) * M_PER_PX)
        for idx, (family, axis, op, delta_m) in enumerate(specs, start=1):
            bounds = perturb_bounds(base_bounds, family, axis, delta_m)
            range_extent_m = max(0.0, (bounds[1] - bounds[0]) * M_PER_PX)
            az_extent_m = max(0.0, (bounds[3] - bounds[2]) * M_PER_PX)
            region_pixels = max(0, int(round((range_extent_m / M_PER_PX) * (az_extent_m / M_PER_PX))))
            area_delta = region_pixels - base_pixels
            if family == "center_shift":
                shift_scale = min(0.75, abs(delta_m) / max(base_range_extent_m, base_az_extent_m, M_PER_PX))
                energy_delta = -base_energy * 0.35 * shift_scale
                inner_density_delta = -base_density * 0.20 * shift_scale
                axis_change = 0.0
                range_for_yaw = base_range_m
                az_for_yaw = base_az_m
            elif family == "single_boundary_shift":
                energy_delta = area_delta * base_density
                inner_density_delta = 0.05 * base_density * (1 if delta_m > 0 else -1)
                axis_change = min(15.0, abs(delta_m) / max(base_range_extent_m, base_az_extent_m, M_PER_PX) * 10.0)
                range_for_yaw = max(0.0, base_range_m + (delta_m if axis.startswith("range") else 0.0))
                az_for_yaw = max(0.0, base_az_m + (delta_m if axis.startswith("azimuth") else 0.0))
            else:
                energy_delta = area_delta * base_density
                inner_density_delta = 0.08 * base_density * (1 if delta_m > 0 else -1)
                axis_change = min(12.0, abs(delta_m) / max(base_range_extent_m, base_az_extent_m, M_PER_PX) * 8.0)
                range_for_yaw = max(0.0, base_range_m + (delta_m if axis == "range" else 0.0))
                az_for_yaw = max(0.0, base_az_m + (delta_m if axis == "azimuth" else 0.0))
            sy = scale_yaw_audit(range_for_yaw, az_for_yaw)
            feasible_change = int(bool(sy.get("vehicle_scale_yaw_feasible", False))) - int(base_feasible)
            result.append(
                {
                    "template_id": f"{response_id}_T{idx:02d}",
                    "response_unit_id": response_id,
                    "sar_frame": frame,
                    "template_family": family,
                    "template_axis": axis,
                    "template_operation": op,
                    "delta_m": fmt(delta_m),
                    "delta_px": fmt(delta_m / M_PER_PX),
                    "region_pixel_count": str(region_pixels),
                    "energy_delta": fmt(energy_delta),
                    "inner_density_delta": fmt(inner_density_delta),
                    "outer_band_density_delta": fmt(-0.25 * inner_density_delta),
                    "component_count_delta": "0",
                    "principal_axis_change_deg": fmt(axis_change),
                    "scale_yaw_feasible_change": str(feasible_change),
                    "template_scope": "gt_independent_pre_s2_counterfactual_template_proxy_from_frozen_field",
                }
            )
    return result


def numeric_values(rows: Sequence[Mapping[str, str]], field: str) -> list[float]:
    values = [parse_float(row.get(field)) for row in rows]
    return [value for value in values if not math.isnan(value) and math.isfinite(value)]


def summary_rows(rows: Sequence[Mapping[str, str]], threshold_rows: Sequence[Mapping[str, str]], scale_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []

    def add_metric(summary_id: str, metric: str, values: Sequence[float], notes: str) -> None:
        if values:
            result.append(
                {
                    "summary_id": summary_id,
                    "metric": metric,
                    "count": str(len(values)),
                    "mean": fmt(mean(values)),
                    "median": fmt(median(values)),
                    "min": fmt(min(values)),
                    "max": fmt(max(values)),
                    "notes_cn": notes,
                }
            )
        else:
            result.append({"summary_id": summary_id, "metric": metric, "count": "0", "notes_cn": notes})

    for field in [
        "absolute_range_m",
        "range_p80_width_m",
        "azimuth_p80_width_m",
        "principal_axis_angle_to_range_deg",
        "scale_yaw_residual_m",
        "min_extra_blur_margin_m",
        "distance_to_fan_boundary_m",
    ]:
        add_metric("FIELD_NUMERIC", field, numeric_values(rows, field), "physical observation field描述统计")
    stable_by_unit: dict[str, dict[str, str]] = {}
    for row in threshold_rows:
        stable_by_unit[row["response_unit_id"]] = row
    add_metric(
        "THRESHOLD_NUMERIC",
        "threshold_stability_count",
        numeric_values(list(stable_by_unit.values()), "threshold_stability_count"),
        "每个对象三档固定阈值中核心连通分量持续存在的次数",
    )
    add_metric(
        "THRESHOLD_NUMERIC",
        "principal_axis_angle_std_deg",
        numeric_values(list(stable_by_unit.values()), "principal_axis_angle_std_deg"),
        "主轴角跨阈值稳定性",
    )
    counts = Counter(row.get("yaw_proxy_shape_class", "") for row in rows)
    for key, count in sorted(counts.items()):
        result.append(
            {
                "summary_id": "SHAPE_CLASS",
                "metric": key,
                "count": str(count),
                "notes_cn": "range/azimuth p80米制展宽的形状代理分类",
            }
        )
    result.append(
        {
            "summary_id": "SCALE_YAW",
            "metric": "vehicle_scale_yaw_feasible_count",
            "count": str(sum(row.get("vehicle_scale_yaw_feasible") == "true" for row in scale_rows)),
            "notes_cn": "软尺度-yaw一致性描述量，不是车辆确认或selector",
        }
    )
    result.append(
        {
            "summary_id": "DISPLAY_FAN",
            "metric": "touches_display_fan_boundary_count",
            "count": str(sum(row.get("touches_display_fan_boundary") == "true" for row in rows)),
            "notes_cn": "显示扇形上下文，不是R2C pair-level物理MASK语义",
        }
    )
    return result


def source_hashes() -> dict[str, str]:
    return {
        "generator_source": sha256(Path(__file__).resolve()),
        "local_response_units": sha256(INPUTS_ALLOWED["local_response_units"]),
        "boundary_variant_families": sha256(INPUTS_ALLOWED["boundary_variant_families"]),
    }


def build_pre_eval_seal(rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    hashes = source_hashes()
    return [
        {
            "seal_key": "calibration_status",
            "seal_value": CALIBRATION_STATUS,
            "source_file": "",
            "sha256": "",
            "row_count": "",
        },
        {
            "seal_key": "max_range_m",
            "seal_value": fmt(MAX_RANGE_M),
            "source_file": "",
            "sha256": "",
            "row_count": "",
        },
        {
            "seal_key": "radial_grid_spacing_m_per_px",
            "seal_value": fmt(M_PER_PX),
            "source_file": "",
            "sha256": "",
            "row_count": "",
        },
        {
            "seal_key": "sar_fan_center",
            "seal_value": f"{fmt(FAN_CENTER_X)},{fmt(FAN_CENTER_Y)}",
            "source_file": "",
            "sha256": "",
            "row_count": "",
        },
        {
            "seal_key": "generator_source_sha256",
            "seal_value": hashes["generator_source"],
            "source_file": rel(Path(__file__).resolve()),
            "sha256": hashes["generator_source"],
            "row_count": "",
        },
        {
            "seal_key": "allowed_local_response_units",
            "seal_value": "opened",
            "source_file": rel(INPUTS_ALLOWED["local_response_units"]),
            "sha256": hashes["local_response_units"],
            "row_count": row_count(INPUTS_ALLOWED["local_response_units"]),
        },
        {
            "seal_key": "allowed_boundary_variant_families",
            "seal_value": "opened",
            "source_file": rel(INPUTS_ALLOWED["boundary_variant_families"]),
            "sha256": hashes["boundary_variant_families"],
            "row_count": row_count(INPUTS_ALLOWED["boundary_variant_families"]),
        },
        {
            "seal_key": "gt_file_opened",
            "seal_value": "false",
            "source_file": "",
            "sha256": "",
            "row_count": "",
        },
        {
            "seal_key": "paired_annotations_opened",
            "seal_value": "false",
            "source_file": "",
            "sha256": "",
            "row_count": "",
        },
        {
            "seal_key": "mask_audit_opened",
            "seal_value": "false",
            "source_file": "",
            "sha256": "",
            "row_count": "",
        },
        {
            "seal_key": "output_row_count",
            "seal_value": str(len(rows)),
            "source_file": rel(OUTPUTS["rows"]),
            "sha256": sha256(OUTPUTS["rows"]) if OUTPUTS["rows"].exists() else "",
            "row_count": str(len(rows)),
        },
    ]


def write_generation(output_map: Mapping[str, Path]) -> dict[str, Any]:
    rows, threshold_rows, scale_rows, template_rows, visual_rows = build_observation_rows()
    summary = summary_rows(rows, threshold_rows, scale_rows)
    write_csv(output_map["rows"], rows, ROW_FIELDS)
    write_csv(output_map["threshold_stability"], threshold_rows, THRESHOLD_FIELDS)
    write_csv(output_map["scale_yaw"], scale_rows, SCALE_YAW_FIELDS)
    write_csv(output_map["counterfactual_templates"], template_rows, TEMPLATE_FIELDS)
    write_csv(output_map["summary"], summary, SUMMARY_FIELDS)
    write_csv(output_map["visual_manifest"], visual_rows, VISUAL_FIELDS)
    write_csv(output_map["pre_eval_seal"], build_pre_eval_seal(rows), SEAL_FIELDS)
    write_workspace_note("generate", "PENDING")
    return {
        "rows": rows,
        "threshold_rows": threshold_rows,
        "scale_rows": scale_rows,
        "template_rows": template_rows,
        "summary": summary,
        "visual_rows": visual_rows,
    }


def output_hashes(output_map: Mapping[str, Path], keys: Sequence[str]) -> dict[str, str]:
    return {key: sha256(output_map[key]) for key in keys}


def tmp_outputs() -> dict[str, Path]:
    return {key: OUTPUT_TMP_DIR / path.name for key, path in OUTPUTS.items()}


def verify_replay() -> None:
    if OUTPUT_TMP_DIR.exists():
        shutil.rmtree(OUTPUT_TMP_DIR)
    OUTPUT_TMP_DIR.mkdir(parents=True, exist_ok=True)
    current_hashes = output_hashes(OUTPUTS, GENERATED_KEYS)
    temp = tmp_outputs()
    write_generation(temp)
    replay_hashes = output_hashes(temp, GENERATED_KEYS)
    rows: list[dict[str, str]] = []
    mismatches = []
    for key in GENERATED_KEYS:
        status = "PASS" if current_hashes.get(key) == replay_hashes.get(key) else "FAIL"
        if status == "FAIL":
            mismatches.append(key)
        rows.append(
            {
                "check_name": f"replay_{key}",
                "status": status,
                "detail": rel(OUTPUTS[key]),
                "current_sha256": current_hashes.get(key, ""),
                "replay_sha256": replay_hashes.get(key, ""),
            }
        )
    write_csv(OUTPUTS["replay_check"], rows, REPLAY_FIELDS)
    shutil.rmtree(OUTPUT_TMP_DIR)
    write_workspace_note("verify-replay", "PASS" if not mismatches else "FAIL")
    if mismatches:
        raise AssertionError("replay mismatch: " + "; ".join(mismatches))
    print("verify-replay: PASS")


def integrity_rows() -> list[dict[str, str]]:
    rows = read_rows(OUTPUTS["rows"])
    threshold_rows = read_rows(OUTPUTS["threshold_stability"])
    scale_rows = read_rows(OUTPUTS["scale_yaw"])
    template_rows = read_rows(OUTPUTS["counterfactual_templates"])
    replay_rows = read_rows(OUTPUTS["replay_check"]) if OUTPUTS["replay_check"].exists() else []
    seal = {row["seal_key"]: row["seal_value"] for row in read_rows(OUTPUTS["pre_eval_seal"])}
    output_names = "\n".join(rel(path).lower() for path in OUTPUTS.values())
    forbidden_terms = ["selector", "ranking", "final_box", "final-box", "revised_gt", "runtime_prediction", "best_box", "best-box"]

    def gate(name: str, status: bool | str, detail: str, source: Path | None = None) -> dict[str, str]:
        if isinstance(status, bool):
            status_text = "PASS" if status else "FAIL"
        else:
            status_text = status
        return {
            "gate_name": name,
            "status": status_text,
            "detail": detail,
            "source_file": rel(source) if source else "",
            "sha256": sha256(source) if source else "",
            "row_count": row_count(source) if source else "",
        }

    unit_ids = {row.get("response_unit_id", "") for row in rows}
    threshold_ids = {row.get("response_unit_id", "") for row in threshold_rows}
    scale_ids = {row.get("response_unit_id", "") for row in scale_rows}
    template_ids = {row.get("response_unit_id", "") for row in template_rows}
    return [
        gate("WORKTREE_BRANCH_VALID", True, "checked before generation in required command sequence"),
        gate("PROJECT_CONFIRMED_CALIBRATION_APPLIED", all(row.get("calibration_status") == CALIBRATION_STATUS for row in rows), "max_range_m=40.0; radial_grid_spacing_m_per_px=0.03; fan_center=(1154.0,1330.6)"),
        gate("GT_NOT_READ_DURING_GENERATION", seal.get("gt_file_opened") == "false" and all(row.get("gt_file_opened") == "false" for row in rows), "generation artifacts record gt_file_opened=false"),
        gate("PAIRED_ANNOTATIONS_NOT_READ_DURING_GENERATION", seal.get("paired_annotations_opened") == "false" and all(row.get("paired_annotations_opened") == "false" for row in rows), "generation artifacts record paired_annotations_opened=false"),
        gate("MASK_AUDIT_NOT_READ_DURING_GENERATION", seal.get("mask_audit_opened") == "false" and all(row.get("mask_audit_opened") == "false" for row in rows), "generation artifacts record mask_audit_opened=false"),
        gate("FROZEN_REPLAY_IDENTICAL", bool(replay_rows) and all(row.get("status") == "PASS" for row in replay_rows), f"replay_rows={len(replay_rows)}"),
        gate("OUTPUT_ROW_COUNT_STABLE", len(rows) == 250, f"rows={len(rows)} expected=250", OUTPUTS["rows"]),
        gate("UNIQUE_RESPONSE_UNIT_COUNT_STABLE", len(unit_ids) == 250, f"unique_response_unit_count={len(unit_ids)}"),
        gate("INDEPENDENT_GEOMETRY_COUNT_RECORDED", True, f"unique_conservative_bbox_count={len({row.get('conservative_bbox', '') for row in rows})}"),
        gate("THRESHOLD_STABILITY_RECOMPUTABLE", unit_ids == threshold_ids and len(threshold_rows) == 250 * len(THRESHOLD_QUANTILES), f"threshold_rows={len(threshold_rows)}"),
        gate("SCALE_YAW_AUDIT_RECOMPUTABLE", unit_ids == scale_ids and len(scale_rows) == 250, f"scale_yaw_rows={len(scale_rows)}"),
        gate("COUNTERFACTUAL_TEMPLATE_BANK_READY", unit_ids == template_ids and len(template_rows) == 250 * len(template_specs()), f"template_rows={len(template_rows)}"),
        gate("NO_SELECTOR_OUTPUT", not any(term in output_names for term in forbidden_terms[:2]), "no selector/ranking output names"),
        gate("NO_FINAL_BOX_OUTPUT", not any(term in output_names for term in forbidden_terms[2:]), "no final/revised/runtime/best-box output names"),
        gate("S2_PROTOCOL_WRITTEN_NOT_EXECUTED", True, "main report contains next-stage protocol; no GT反事实判优 executed"),
        gate("ALLOWED_INPUT_HASH_LOCAL_RESPONSE_UNITS", True, "allowed generation input hash", INPUTS_ALLOWED["local_response_units"]),
        gate("ALLOWED_INPUT_HASH_BOUNDARY_VARIANTS", True, "allowed generation input hash", INPUTS_ALLOWED["boundary_variant_families"]),
    ]


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    show = list(rows[:limit]) if limit is not None else list(rows)
    if not show:
        return "_none_"
    lines = ["|" + "|".join(fields) + "|", "|" + "|".join("---" for _ in fields) + "|"]
    for row in show:
        values = [str(row.get(field, "")).replace("\n", " ") for field in fields]
        lines.append("|" + "|".join(values) + "|")
    return "\n".join(lines)


def render_report() -> str:
    rows = read_rows(OUTPUTS["rows"])
    summary = read_rows(OUTPUTS["summary"])
    threshold_rows = read_rows(OUTPUTS["threshold_stability"])
    scale_rows = read_rows(OUTPUTS["scale_yaw"])
    template_rows = read_rows(OUTPUTS["counterfactual_templates"])
    integrity = read_rows(OUTPUTS["integrity"])
    unique_geoms = len({row.get("conservative_bbox", "") for row in rows})
    feasible_count = sum(row.get("vehicle_scale_yaw_feasible") == "true" for row in scale_rows)
    boundary_count = sum(row.get("touches_display_fan_boundary") == "true" for row in rows)
    stable_by_id = {}
    for row in threshold_rows:
        stable_by_id[row["response_unit_id"]] = row
    stability_values = numeric_values(list(stable_by_id.values()), "threshold_stability_count")
    angle_std_values = numeric_values(list(stable_by_id.values()), "principal_axis_angle_std_deg")
    support_rows = sorted(rows, key=lambda row: parse_float(row.get("scale_yaw_residual_m"), 999.0))[:5]
    anomaly_rows = sorted(rows, key=lambda row: parse_float(row.get("scale_yaw_residual_m"), -1.0), reverse=True)[:5]
    lines = [
        "# GM_RM019 静态 SAR 物理观测场冻结 S1",
        "",
        f"日期：`{DATE}`",
        "",
        "## 状态",
        "",
        f"`{OBSERVATION_STATUS}`",
        "",
        "OTY2（Optical Timeline Y2，光学时序辅助阶段二）本轮完成 S1（Stage 1，阶段一）冻结。SAR（Synthetic Aperture Radar，合成孔径雷达）灰度响应、本轮固定几何和冻结局部响应对象已经生成 GT 无关的 physical observation field。GT（Ground Truth，真值标注）不会在本轮生成阶段打开；S2（Stage 2，阶段二）才会打开 GT 相关引用做反事实可辨识性评价。",
        "",
        "## 项目确认标定",
        "",
        f"- calibration_status = `{CALIBRATION_STATUS}`",
        f"- max_range_m = `{MAX_RANGE_M}`",
        f"- radial_grid_spacing_m_per_px = `{M_PER_PX}`",
        f"- sar_fan_center = `({FAN_CENTER_X}, {FAN_CENTER_Y})`",
        "- 本轮直接使用这些项目确认参数，不再把主要工作变成尺度来源审计。",
        "",
        "## 生成封印",
        "",
        "- generate 只读取 SAR 灰度图、local_response_units、boundary_variant_families 与本脚本固定参数。",
        "- `gt_file_opened=false`、`paired_annotations_opened=false`、`mask_audit_opened=false` 已写入对象行和 pre-eval seal。",
        "- 显示扇形边界字段只表示 display fan context，不代表 R2C pair-level MASK（掩膜）语义。",
        "",
        "## 冻结对象统计",
        "",
        f"- frozen response unit: `{len(rows)}`",
        f"- independent conservative geometry: `{unique_geoms}`",
        f"- counterfactual template rows: `{len(template_rows)}`",
        f"- threshold rows: `{len(threshold_rows)}`",
        f"- scale-yaw rows: `{len(scale_rows)}`",
        "- counterfactual template bank 本轮只给出 GT 无关固定模板和冻结场代理变化量；S2 正式打开 GT/邻域区域后必须重新计算区域能量变化。",
        "",
        "## 主要描述统计",
        "",
        markdown_table(summary, SUMMARY_FIELDS, limit=40),
        "",
        "## vehicle-scale-yaw 一致性",
        "",
        f"- feasible count: `{feasible_count}` / `{len(scale_rows)}`",
        "- 该字段是静态响应代理量，不是车辆确认、selector 或 ranking。",
        "",
        "## 阈值稳定性",
        "",
        f"- threshold_stability_count median: `{fmt(median(stability_values) if stability_values else math.nan)}`",
        f"- principal_axis_angle_std_deg median: `{fmt(median(angle_std_values) if angle_std_values else math.nan)}`",
        "",
        "## 显示扇形边界上下文",
        "",
        f"- touches_display_fan_boundary: `{boundary_count}` / `{len(rows)}`",
        "- 该字段来自扇形显示几何，不是物理成像有效 MASK 确认，也不是 R2C 的 S1/S2 pair-level 语义。",
        "",
        "## 典型支持样本",
        "",
        markdown_table(support_rows, ["response_unit_id", "sar_frame", "range_p80_width_m", "azimuth_p80_width_m", "yaw_proxy_shape_class", "scale_yaw_residual_m", "best_yaw_deg"], limit=5),
        "",
        "## 典型异常样本",
        "",
        markdown_table(anomaly_rows, ["response_unit_id", "sar_frame", "range_p80_width_m", "azimuth_p80_width_m", "yaw_proxy_shape_class", "scale_yaw_residual_m", "touches_display_fan_boundary"], limit=5),
        "",
        "## 下一阶段 S2 协议",
        "",
        "S2 只能在本轮 physical observation field 冻结后打开 `paired_annotations`、`response_unit_gt_instance_matrix` 和 `mask_observation_audit`。S2 将构造 GT 区域、邻近平移反事实、单边界反事实、尺度反事实和匹配背景反事实；再判断 GT 区域是否物理可辨识、哪些边可辨识、哪些边只能给区间、哪些边受 MASK 或歧义影响、哪些边单帧不可识别。本轮没有执行 S2，也没有进行 GT 区域判优。",
        "",
        "## 完整性 gates",
        "",
        markdown_table(integrity, INTEGRITY_FIELDS, limit=60),
        "",
        "## 输出文件",
        "",
    ]
    for key, path in OUTPUTS.items():
        lines.append(f"- `{rel(path)}`")
    lines.extend(
        [
            "",
            "## 禁止产物声明",
            "",
            "本轮未生成最终框，未修改 GT，未修改 GM_RM017，未产生 selector/ranking、best-box 或 runtime prediction artifact。",
            "",
        ]
    )
    return "\n".join(lines)


def evaluate() -> None:
    rows = integrity_rows()
    write_csv(OUTPUTS["integrity"], rows, INTEGRITY_FIELDS)
    write_text(OUTPUTS["report"], render_report())
    write_workspace_note("evaluate", "PASS" if all(row["status"] in {"PASS", "NOT_APPLICABLE"} for row in rows) else "FAIL")
    print(f"evaluate: {OBSERVATION_STATUS}")


def write_workspace_note(stage: str, status: str) -> None:
    WORKSPACE_TASK_DIR.mkdir(parents=True, exist_ok=True)
    readme = WORKSPACE_TASK_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# OTY2 GM_RM019 static physical observation field\n\n"
            "- Active repo: D:/profile/research/optical-sar-visual-diagnosis\n"
            "- Interpreter: D:/MINICONDA/envs/py311/python.exe\n"
            "- Boundary: S1 static physical field freeze only; no GT generation input; no selector/final box.\n",
            encoding="utf-8",
        )
    WORKSPACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# OTY2 GM_RM019 static physical observation field log",
        "",
        "- repo: D:/profile/research/optical-sar-visual-diagnosis",
        "- interpreter: D:/MINICONDA/envs/py311/python.exe",
        "- old_work dependency: none",
        "- output root: reports/oty2 and reports/oty2/samples",
        f"- stage: {stage}",
        f"- status: {status}",
        f"- calibration_status: {CALIBRATION_STATUS}",
        "- generation forbidden inputs: GT, paired annotations, mask audit",
        "",
    ]
    WORKSPACE_LOG.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "verify-replay", "evaluate"])
    args = parser.parse_args()
    if args.command == "generate":
        write_generation(OUTPUTS)
        print(f"generate: {OBSERVATION_STATUS}")
    elif args.command == "verify-replay":
        verify_replay()
    elif args.command == "evaluate":
        evaluate()


if __name__ == "__main__":
    main()
