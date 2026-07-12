"""Generate GM_RM019 S1-R1 static axis and counterfactual semantic repair artifacts.

The generate command is S1-only. It reads SAR gray frames, the frozen S1
physical observation field, frozen local response units, boundary variant
families, this script's constants, and the S1-R1 protocol. It does not read GT,
paired annotations, mask audit tables, selector/ranking outputs, final boxes, or
runtime prediction artifacts.
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
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DOC_PATH = REPO_ROOT / "docs" / "OTY2_GM019_STATIC_AXIS_AND_ROTATION_SEMANTIC_INTEGRITY_S1_R1_PROTOCOL.md"
DATA_ROOT = Path("D:/profile/research/data/GM_RM019/GM_RM019_SARframes_gray")
VISUAL_DIR = REPO_ROOT / "outputs" / "oty2_gm_rm019_s1_r1_axis_rotation_20260712" / "visual_review"
VERIFY_TMP = REPO_ROOT / "outputs" / "oty2_gm_rm019_s1_r1_axis_rotation_20260712" / "_verify_tmp"
WORKSPACE_TASK_DIR = Path("D:/profile/research/workspace/tasks/oty2_gm_rm019_static_axis_rotation_s1_r1")
WORKSPACE_LOG = Path("D:/profile/research/workspace/logs/oty2_gm_rm019_static_axis_rotation_s1_r1_20260712.md")

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
STATUS_READY = "S1_R1_SEMANTIC_INTEGRITY_READY"
S2_READY = "READY"

THRESHOLD_SETTINGS = [
    ("positive_weight_q50", 0.50),
    ("positive_weight_q70", 0.70),
    ("positive_weight_q85", 0.85),
]
CENTER_SHIFT_M = [0.15, 0.30, 0.45]
BOUNDARY_SHIFT_M = [0.15, 0.30]
SCALE_SHIFT_M = [0.15, 0.30]
ROTATION_DEG = [-30, -15, -10, -5, 5, 10, 15, 30, 90]
VEHICLE_LENGTH_GRID = [round(3.0 + 0.1 * i, 2) for i in range(36)]
VEHICLE_WIDTH_GRID = [round(1.4 + 0.1 * i, 2) for i in range(13)]
ASPECT_ANGLE_GRID = list(range(0, 91))
ENVELOPE_EXTRA_TOL_M = 0.30
ENVELOPE_EXCEED_TOL_M = 0.75
AXIS_RATIO_MIN = 1.20
COMPONENT_MIN_PIXELS = 8
VISUAL_LABELS = [
    "axis_image_about_45",
    "axis_image_about_135",
    "near_range_axis",
    "near_azimuth_axis",
    "near_isotropic",
    "multi_component",
    "threshold_identity_switch",
    "rotation_sensitive",
    "rotation_insensitive",
    "exceeds_vehicle_projection_envelope",
    "partial_support_below_envelope",
    "duplicate_independent_geometry",
]

INPUTS = {
    "s1_rows": SAMPLES_DIR / "oty2_gm_rm019_static_physical_observation_field_rows_20260712.csv",
    "local_response_units": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv",
    "boundary_variant_families": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_variant_families_20260711.csv",
    "sar_gray_dir": DATA_ROOT,
    "protocol": DOC_PATH,
}

OUTPUTS = {
    "axis_observations": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_axis_observations_20260712.csv",
    "threshold_components": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_threshold_components_20260712.csv",
    "threshold_transitions": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_threshold_component_transitions_20260712.csv",
    "vehicle_projection_envelope": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_vehicle_projection_envelope_20260712.csv",
    "counterfactual_specs": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_counterfactual_specs_20260712.csv",
    "counterfactual_measurements": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_counterfactual_measurements_20260712.csv",
    "independent_geometry_map": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_independent_geometry_map_20260712.csv",
    "semantic_failures": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_semantic_failures_20260712.csv",
    "pre_eval_seal": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_pre_eval_seal_20260712.csv",
    "replay_check": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_replay_check_20260712.csv",
    "visual_manifest": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_visual_manifest_20260712.csv",
}

GENERATED_KEYS = [
    "axis_observations",
    "threshold_components",
    "threshold_transitions",
    "vehicle_projection_envelope",
    "counterfactual_specs",
    "counterfactual_measurements",
    "independent_geometry_map",
    "semantic_failures",
    "pre_eval_seal",
    "visual_manifest",
]

AXIS_FIELDS = [
    "scene",
    "independent_geometry_id",
    "response_unit_id",
    "member_response_unit_count",
    "member_response_unit_ids",
    "sar_frame",
    "sar_gray_image_relpath",
    "core_bbox",
    "conservative_bbox",
    "calibration_status",
    "max_range_m",
    "radial_grid_spacing_m_per_px",
    "sar_fan_center_x_px",
    "sar_fan_center_y_px",
    "gt_file_opened",
    "paired_annotations_opened",
    "mask_audit_opened",
    "generation_input_scope",
    "response_center_x",
    "response_center_y",
    "absolute_range_m",
    "range_unit_x",
    "range_unit_y",
    "azimuth_unit_x",
    "azimuth_unit_y",
    "background_mode",
    "frozen_background_estimate",
    "measured_background_subtracted_energy",
    "measured_inner_energy_density",
    "measured_outer_band_energy_density",
    "measured_inner_outer_density_ratio",
    "measured_component_count",
    "measured_largest_component_pixels",
    "measured_range_p50_width_m",
    "measured_range_p80_width_m",
    "measured_range_p90_width_m",
    "measured_azimuth_p50_width_m",
    "measured_azimuth_p80_width_m",
    "measured_azimuth_p90_width_m",
    "principal_axis_major_std_px",
    "principal_axis_minor_std_px",
    "principal_axis_ratio",
    "response_axis_vector_x",
    "response_axis_vector_y",
    "response_axis_image_deg",
    "response_axis_to_range_signed_deg",
    "response_axis_to_range_acute_deg",
    "response_axis_to_azimuth_acute_deg",
    "range_azimuth_acute_complement_error_deg",
    "axis_orientation_status",
    "threshold_component_identity_status",
]

THRESHOLD_COMPONENT_FIELDS = [
    "independent_geometry_id",
    "sar_frame",
    "threshold_setting",
    "threshold_quantile",
    "threshold_value",
    "component_count",
    "largest_component_pixels",
    "largest_component_area_px",
    "component_mask_sha256",
    "component_centroid_x",
    "component_centroid_y",
    "component_bbox",
    "component_response_center_distance_m",
    "component_axis_image_deg",
    "component_axis_to_range_signed_deg",
    "component_axis_to_range_acute_deg",
    "component_principal_axis_ratio",
]

THRESHOLD_TRANSITION_FIELDS = [
    "independent_geometry_id",
    "sar_frame",
    "from_threshold_setting",
    "to_threshold_setting",
    "component_overlap_iou",
    "high_threshold_contained_in_low_threshold",
    "component_centroid_shift_m",
    "component_area_retention_ratio",
    "component_axis_change_deg",
    "from_component_count",
    "to_component_count",
    "threshold_component_identity_status",
]

ENVELOPE_FIELDS = [
    "independent_geometry_id",
    "response_unit_id",
    "sar_frame",
    "measured_range_p80_width_m",
    "measured_azimuth_p80_width_m",
    "vehicle_projection_envelope_status",
    "aspect_angle_candidate_deg",
    "aspect_angle_compatible_interval_deg",
    "best_scale_length_m",
    "best_scale_width_m",
    "projection_residual_m",
    "required_missing_support_range_m",
    "required_missing_support_azimuth_m",
    "required_extra_spread_range_m",
    "required_extra_spread_azimuth_m",
    "response_axis_aspect_angle_error_deg",
    "aspect_angle_identifiability_status",
    "aspect_angle_compatible_segment_count",
    "aspect_angle_compatible_total_span_deg",
    "equivalent_minimum_count",
    "vehicle_scale_semantic_note_cn",
]

SPEC_FIELDS = [
    "template_id",
    "independent_geometry_id",
    "member_response_unit_ids",
    "sar_frame",
    "template_family",
    "template_axis",
    "template_operation",
    "delta_m",
    "delta_px",
    "rotation_deg",
    "template_scope",
]

MEASUREMENT_FIELDS = [
    "template_id",
    "independent_geometry_id",
    "sar_frame",
    "template_family",
    "template_axis",
    "template_operation",
    "delta_m",
    "delta_px",
    "rotation_deg",
    "measurement_source",
    "proxy_formula_used",
    "background_mode",
    "sensitivity_background_mode",
    "counterfactual_background_sensitivity_status",
    "base_background_subtracted_energy",
    "measured_background_subtracted_energy",
    "energy_delta_measured",
    "base_inner_energy_density",
    "measured_inner_energy_density",
    "inner_density_delta_measured",
    "base_outer_band_energy_density",
    "measured_outer_band_energy_density",
    "outer_density_delta_measured",
    "measured_inner_outer_density_ratio",
    "base_component_count",
    "measured_component_count",
    "component_count_delta_measured",
    "measured_largest_component_pixels",
    "measured_range_p50_width_m",
    "measured_range_p80_width_m",
    "measured_range_p90_width_m",
    "range_p80_delta_m_measured",
    "measured_azimuth_p50_width_m",
    "measured_azimuth_p80_width_m",
    "measured_azimuth_p90_width_m",
    "azimuth_p80_delta_m_measured",
    "measured_response_axis_image_deg",
    "measured_response_axis_to_range_signed_deg",
    "measured_response_axis_to_range_acute_deg",
    "axis_angle_delta_deg_measured",
    "measured_principal_axis_ratio",
    "measured_axis_orientation_status",
    "measured_vehicle_projection_envelope_status",
    "measured_aspect_angle_candidate_deg",
]

GEOMETRY_MAP_FIELDS = [
    "independent_geometry_id",
    "scene",
    "sar_frame",
    "member_sar_frames",
    "conservative_bbox",
    "core_bbox",
    "member_response_unit_count",
    "member_response_unit_ids",
    "representative_response_unit_id",
    "measured_once_then_mapped_to_members",
]

FAILURE_FIELDS = [
    "failure_id",
    "independent_geometry_id",
    "response_unit_id",
    "failure_type",
    "severity",
    "detail",
]

SEAL_FIELDS = ["seal_key", "seal_value", "source_file", "sha256", "row_count"]
REPLAY_FIELDS = ["check_name", "status", "detail", "current_sha256", "replay_sha256"]
VISUAL_FIELDS = [
    "visual_case_id",
    "review_label",
    "independent_geometry_id",
    "response_unit_id",
    "sar_frame",
    "visual_relpath",
    "opened_for_review",
    "selection_reason",
]


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


@dataclass
class Component:
    count: int
    largest_pixels: int
    mask: np.ndarray
    xs: np.ndarray
    ys: np.ndarray
    weights: np.ndarray
    bbox: str
    centroid_x: float
    centroid_y: float
    axis_image_deg: float
    axis_signed_deg: float
    axis_acute_deg: float
    axis_ratio: float


@dataclass
class Measurement:
    pixel_count: int
    background: float
    energy: float
    inner_density: float
    outer_density: float
    density_ratio: float
    component_count: int
    largest_component_pixels: int
    range_p50_m: float
    range_p80_m: float
    range_p90_m: float
    azimuth_p50_m: float
    azimuth_p80_m: float
    azimuth_p90_m: float
    axis_major_std_px: float
    axis_minor_std_px: float
    axis_ratio: float
    axis_vx: float
    axis_vy: float
    axis_image_deg: float
    axis_signed_deg: float
    axis_acute_deg: float
    axis_azimuth_acute_deg: float
    complement_error_deg: float
    axis_status: str
    component: Component


@dataclass
class RegionGrid:
    xs: np.ndarray
    ys: np.ndarray
    pr: np.ndarray
    pa: np.ndarray
    intensities: np.ndarray
    valid_fan: np.ndarray


_IMAGE_CACHE: dict[int, np.ndarray] = {}
_ASPECT_CACHE: dict[tuple[float, float, str], dict[str, Any]] = {}
_ASPECT_ARRAYS: dict[str, np.ndarray] | None = None


def fmt(value: Any, ndigits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(f) or math.isinf(f):
        return ""
    text = f"{f:.{ndigits}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(str(value).strip())
    except ValueError:
        return default


def parse_box(text: str) -> Box | None:
    if not text:
        return None
    parts = [parse_float(p) for p in str(text).replace(";", ",").split(",")]
    if len(parts) != 4 or any(math.isnan(p) for p in parts):
        return None
    x1, y1, x2, y2 = parts
    return Box(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def box_text(box: Box, ndigits: int = 3) -> str:
    return ",".join(fmt(v, ndigits) for v in (box.x1, box.y1, box.x2, box.y2))


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def load_gray(frame: int) -> np.ndarray:
    if frame not in _IMAGE_CACHE:
        path = DATA_ROOT / f"{int(frame):06d}.png"
        with Image.open(path) as img:
            _IMAGE_CACHE[frame] = np.asarray(img.convert("L"), dtype=np.float32)
    return _IMAGE_CACHE[frame]


def frame_image_path(frame: int) -> Path:
    return DATA_ROOT / f"{int(frame):06d}.png"


def radial_px(x: float, y: float) -> float:
    return math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)


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


def local_bounds_for_box(box: Box, cx: float, cy: float, rx: float, ry: float, ax: float, ay: float) -> tuple[float, float, float, float]:
    corners = np.asarray(
        [(box.x1, box.y1), (box.x2, box.y1), (box.x2, box.y2), (box.x1, box.y2)],
        dtype=float,
    )
    pr = (corners[:, 0] - cx) * rx + (corners[:, 1] - cy) * ry
    pa = (corners[:, 0] - cx) * ax + (corners[:, 1] - cy) * ay
    return float(pr.min()), float(pr.max()), float(pa.min()), float(pa.max())


def canonical_axis(vx: float, vy: float) -> tuple[float, float, float]:
    if math.isnan(vx) or math.isnan(vy) or math.hypot(vx, vy) <= 1e-12:
        return math.nan, math.nan, math.nan
    angle = math.degrees(math.atan2(vy, vx)) % 180.0
    rad = math.radians(angle)
    return math.cos(rad), math.sin(rad), angle


def signed_axis_to_ref_deg(vx: float, vy: float, ux: float, uy: float) -> float:
    if any(math.isnan(v) for v in (vx, vy, ux, uy)):
        return math.nan
    beta = math.degrees(math.atan2(ux * vy - uy * vx, ux * vx + uy * vy))
    while beta < -90.0:
        beta += 180.0
    while beta >= 90.0:
        beta -= 180.0
    return beta


def acute_axis_to_ref_deg(vx: float, vy: float, ux: float, uy: float) -> float:
    signed = signed_axis_to_ref_deg(vx, vy, ux, uy)
    return abs(signed) if not math.isnan(signed) else math.nan


def axis_diff_acute(a: float, b: float) -> float:
    if math.isnan(a) or math.isnan(b):
        return math.nan
    diff = abs((a - b + 90.0) % 180.0 - 90.0)
    return min(diff, 180.0 - diff)


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


def weighted_major_axis(xs: np.ndarray, ys: np.ndarray, weights: np.ndarray) -> tuple[float, float, float, float, float, float]:
    total = float(np.sum(weights))
    if len(xs) < 2 or total <= 1e-9:
        return math.nan, math.nan, math.nan, math.nan, math.nan, math.nan
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
    vx_raw, vy_raw = vecs[:, order[-1]]
    vx, vy, angle = canonical_axis(float(vx_raw), float(vy_raw))
    major_std = math.sqrt(major_val)
    minor_std = math.sqrt(minor_val)
    ratio = major_std / minor_std if minor_std > 1e-9 else math.inf
    return major_std, minor_std, ratio, vx, vy, angle


def connected_components(mask: np.ndarray, xs: np.ndarray, ys: np.ndarray, weights: np.ndarray, rx: float, ry: float) -> Component:
    if mask.size == 0 or not bool(mask.any()):
        return Component(0, 0, np.zeros(mask.shape, dtype=bool), np.asarray([]), np.asarray([]), np.asarray([]), "", math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)
    structure = np.asarray([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8)
    labels, count = ndi.label(mask, structure=structure)
    if count <= 0:
        return Component(0, 0, np.zeros(mask.shape, dtype=bool), np.asarray([]), np.asarray([]), np.asarray([]), "", math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    largest_label = int(np.argmax(sizes))
    largest_size = int(sizes[largest_label])
    largest_mask = labels == largest_label
    comp_xs = xs[largest_mask]
    comp_ys = ys[largest_mask]
    comp_weights = weights[largest_mask]
    if float(np.sum(comp_weights)) <= 1e-9:
        comp_weights = np.ones_like(comp_xs, dtype=float)
    cx = float(np.average(comp_xs, weights=comp_weights))
    cy = float(np.average(comp_ys, weights=comp_weights))
    major, minor, ratio, vx, vy, angle = weighted_major_axis(comp_xs, comp_ys, comp_weights)
    signed = signed_axis_to_ref_deg(vx, vy, rx, ry)
    acute = abs(signed) if not math.isnan(signed) else math.nan
    bbox = Box(float(comp_xs.min()), float(comp_ys.min()), float(comp_xs.max() + 1), float(comp_ys.max() + 1))
    return Component(
        count=int(count),
        largest_pixels=largest_size,
        mask=largest_mask,
        xs=comp_xs,
        ys=comp_ys,
        weights=comp_weights,
        bbox=box_text(bbox),
        centroid_x=cx,
        centroid_y=cy,
        axis_image_deg=angle,
        axis_signed_deg=signed,
        axis_acute_deg=acute,
        axis_ratio=ratio,
    )


def region_arrays(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    bounds: tuple[float, float, float, float],
    rotation_deg: float = 0.0,
    center_shift_r_px: float = 0.0,
    center_shift_a_px: float = 0.0,
    margin_px: float = 8.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rmin, rmax, amin, amax = bounds
    ccx = cx + center_shift_r_px * rx + center_shift_a_px * ax
    ccy = cy + center_shift_r_px * ry + center_shift_a_px * ay
    radius = math.hypot(max(abs(rmin), abs(rmax)), max(abs(amin), abs(amax))) + abs(center_shift_r_px) + abs(center_shift_a_px) + margin_px + 8.0
    x1 = max(0, int(math.floor(ccx - radius)))
    x2 = min(SAR_WIDTH, int(math.ceil(ccx + radius)))
    y1 = max(0, int(math.floor(ccy - radius)))
    y2 = min(SAR_HEIGHT, int(math.ceil(ccy + radius)))
    yy, xx = np.mgrid[y1:y2, x1:x2]
    xs = xx.astype(np.float32) + 0.5
    ys = yy.astype(np.float32) + 0.5
    pr = (xs - ccx) * rx + (ys - ccy) * ry
    pa = (xs - ccx) * ax + (ys - ccy) * ay
    rad = math.radians(rotation_deg)
    c = math.cos(rad)
    s = math.sin(rad)
    qr = pr * c + pa * s
    qa = -pr * s + pa * c
    return xs, ys, pr, pa, qr, qa


def make_region_grid(
    arr: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    bounds: tuple[float, float, float, float],
) -> RegionGrid:
    rmin, rmax, amin, amax = bounds
    max_shift_px = max(CENTER_SHIFT_M + BOUNDARY_SHIFT_M + SCALE_SHIFT_M) / M_PER_PX
    radius = math.hypot(max(abs(rmin), abs(rmax)), max(abs(amin), abs(amax))) + max_shift_px + 28.0
    x1 = max(0, int(math.floor(cx - radius)))
    x2 = min(SAR_WIDTH, int(math.ceil(cx + radius)))
    y1 = max(0, int(math.floor(cy - radius)))
    y2 = min(SAR_HEIGHT, int(math.ceil(cy + radius)))
    yy, xx = np.mgrid[y1:y2, x1:x2]
    xs = xx.astype(np.float32) + 0.5
    ys = yy.astype(np.float32) + 0.5
    pr = (xs - cx) * rx + (ys - cy) * ry
    pa = (xs - cx) * ax + (ys - cy) * ay
    ix = np.clip(xs.astype(int), 0, SAR_WIDTH - 1)
    iy = np.clip(ys.astype(int), 0, SAR_HEIGHT - 1)
    return RegionGrid(xs=xs, ys=ys, pr=pr, pa=pa, intensities=arr[iy, ix], valid_fan=fan_valid_points(xs, ys))


def grid_rotated_coords(grid: RegionGrid, rotation_deg: float, center_shift_r_px: float, center_shift_a_px: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    pr = grid.pr - center_shift_r_px
    pa = grid.pa - center_shift_a_px
    rad = math.radians(rotation_deg)
    c = math.cos(rad)
    s = math.sin(rad)
    qr = pr * c + pa * s
    qa = -pr * s + pa * c
    return pr, pa, qr, qa


def estimate_local_ring_background_grid(
    grid: RegionGrid,
    bounds: tuple[float, float, float, float],
    rotation_deg: float,
    center_shift_r_px: float,
    center_shift_a_px: float,
    band_px: float = 5.0,
) -> float:
    rmin, rmax, amin, amax = bounds
    _, _, qr, qa = grid_rotated_coords(grid, rotation_deg, center_shift_r_px, center_shift_a_px)
    inside = (qr >= rmin) & (qr <= rmax) & (qa >= amin) & (qa <= amax)
    ring = (qr >= rmin - band_px) & (qr <= rmax + band_px) & (qa >= amin - band_px) & (qa <= amax + band_px) & (~inside) & grid.valid_fan
    if not bool(ring.any()):
        return 0.0
    return float(np.median(grid.intensities[ring]))


def measure_region_grid(
    grid: RegionGrid,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    bounds: tuple[float, float, float, float],
    background: float,
    rotation_deg: float = 0.0,
    center_shift_r_px: float = 0.0,
    center_shift_a_px: float = 0.0,
) -> Measurement:
    rmin, rmax, amin, amax = bounds
    pr, pa, qr, qa = grid_rotated_coords(grid, rotation_deg, center_shift_r_px, center_shift_a_px)
    inside = (qr >= rmin) & (qr <= rmax) & (qa >= amin) & (qa <= amax) & grid.valid_fan
    band = (qr >= rmin - 5) & (qr <= rmax + 5) & (qa >= amin - 5) & (qa <= amax + 5) & (~inside) & grid.valid_fan
    weights = np.maximum(grid.intensities - background, 0.0)
    inner_weights = weights[inside]
    band_weights = weights[band]
    pixel_count = int(np.count_nonzero(inside))
    outer_density = float(np.mean(band_weights)) if int(np.count_nonzero(band)) else 0.0
    positive_mask = inside & (weights > 0)
    component = connected_components(positive_mask, grid.xs, grid.ys, weights, rx, ry)
    if pixel_count == 0 or len(inner_weights) == 0 or float(np.sum(inner_weights)) <= 1e-9:
        return Measurement(
            pixel_count=pixel_count,
            background=background,
            energy=0.0,
            inner_density=0.0,
            outer_density=outer_density,
            density_ratio=0.0,
            component_count=component.count,
            largest_component_pixels=component.largest_pixels,
            range_p50_m=math.nan,
            range_p80_m=math.nan,
            range_p90_m=math.nan,
            azimuth_p50_m=math.nan,
            azimuth_p80_m=math.nan,
            azimuth_p90_m=math.nan,
            axis_major_std_px=math.nan,
            axis_minor_std_px=math.nan,
            axis_ratio=math.nan,
            axis_vx=math.nan,
            axis_vy=math.nan,
            axis_image_deg=math.nan,
            axis_signed_deg=math.nan,
            axis_acute_deg=math.nan,
            axis_azimuth_acute_deg=math.nan,
            complement_error_deg=math.nan,
            axis_status="AXIS_ENERGY_INVALID",
            component=component,
        )
    xs_i = grid.xs[inside]
    ys_i = grid.ys[inside]
    pr_i = pr[inside]
    pa_i = pa[inside]
    weights_i = inner_weights
    energy = float(np.sum(weights_i))
    major, minor, ratio, vx, vy, image_angle = weighted_major_axis(xs_i, ys_i, weights_i)
    signed = signed_axis_to_ref_deg(vx, vy, rx, ry)
    acute = abs(signed) if not math.isnan(signed) else math.nan
    az_acute = acute_axis_to_ref_deg(vx, vy, ax, ay)
    complement = abs((acute + az_acute) - 90.0) if not math.isnan(acute) and not math.isnan(az_acute) else math.nan
    if math.isnan(ratio):
        axis_status = "AXIS_ENERGY_INVALID"
    elif ratio < AXIS_RATIO_MIN:
        axis_status = "AXIS_NEAR_ISOTROPIC"
    elif component.count > 1:
        axis_status = "AXIS_MULTI_COMPONENT_AMBIGUOUS"
    else:
        axis_status = "AXIS_ORIENTATION_RESOLVED"
    return Measurement(
        pixel_count=pixel_count,
        background=background,
        energy=energy,
        inner_density=energy / max(1, pixel_count),
        outer_density=outer_density,
        density_ratio=(energy / max(1, pixel_count)) / outer_density if outer_density > 1e-9 else math.inf,
        component_count=component.count,
        largest_component_pixels=component.largest_pixels,
        range_p50_m=shortest_weighted_width(pr_i, weights_i, 0.50) * M_PER_PX,
        range_p80_m=shortest_weighted_width(pr_i, weights_i, 0.80) * M_PER_PX,
        range_p90_m=shortest_weighted_width(pr_i, weights_i, 0.90) * M_PER_PX,
        azimuth_p50_m=shortest_weighted_width(pa_i, weights_i, 0.50) * M_PER_PX,
        azimuth_p80_m=shortest_weighted_width(pa_i, weights_i, 0.80) * M_PER_PX,
        azimuth_p90_m=shortest_weighted_width(pa_i, weights_i, 0.90) * M_PER_PX,
        axis_major_std_px=major,
        axis_minor_std_px=minor,
        axis_ratio=ratio,
        axis_vx=vx,
        axis_vy=vy,
        axis_image_deg=image_angle,
        axis_signed_deg=signed,
        axis_acute_deg=acute,
        axis_azimuth_acute_deg=az_acute,
        complement_error_deg=complement,
        axis_status=axis_status,
        component=component,
    )


def threshold_component_grid(
    grid: RegionGrid,
    rx: float,
    ry: float,
    bounds: tuple[float, float, float, float],
    background: float,
    quantile: float,
) -> tuple[Component, float]:
    rmin, rmax, amin, amax = bounds
    _, _, qr, qa = grid_rotated_coords(grid, 0.0, 0.0, 0.0)
    inside = (qr >= rmin) & (qr <= rmax) & (qa >= amin) & (qa <= amax) & grid.valid_fan
    weights = np.maximum(grid.intensities - background, 0.0)
    positive = weights[inside & (weights > 0)]
    threshold = float(np.quantile(positive, quantile)) if len(positive) else math.inf
    mask = inside & (weights >= threshold) & (weights > 0)
    return connected_components(mask, grid.xs, grid.ys, weights, rx, ry), threshold


def estimate_local_ring_background(
    arr: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    bounds: tuple[float, float, float, float],
    rotation_deg: float,
    center_shift_r_px: float,
    center_shift_a_px: float,
    band_px: float = 5.0,
) -> float:
    rmin, rmax, amin, amax = bounds
    xs, ys, _, _, qr, qa = region_arrays(cx, cy, rx, ry, ax, ay, bounds, rotation_deg, center_shift_r_px, center_shift_a_px, margin_px=band_px + 8)
    inside = (qr >= rmin) & (qr <= rmax) & (qa >= amin) & (qa <= amax)
    ring = (qr >= rmin - band_px) & (qr <= rmax + band_px) & (qa >= amin - band_px) & (qa <= amax + band_px) & (~inside)
    valid = ring & fan_valid_points(xs, ys)
    if not bool(valid.any()):
        return 0.0
    ix = np.clip(xs.astype(int), 0, SAR_WIDTH - 1)
    iy = np.clip(ys.astype(int), 0, SAR_HEIGHT - 1)
    return float(np.median(arr[iy[valid], ix[valid]]))


def measure_region(
    arr: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    bounds: tuple[float, float, float, float],
    background: float,
    rotation_deg: float = 0.0,
    center_shift_r_px: float = 0.0,
    center_shift_a_px: float = 0.0,
) -> Measurement:
    rmin, rmax, amin, amax = bounds
    xs, ys, pr, pa, qr, qa = region_arrays(cx, cy, rx, ry, ax, ay, bounds, rotation_deg, center_shift_r_px, center_shift_a_px)
    ix = np.clip(xs.astype(int), 0, SAR_WIDTH - 1)
    iy = np.clip(ys.astype(int), 0, SAR_HEIGHT - 1)
    valid_fan = fan_valid_points(xs, ys)
    inside = (qr >= rmin) & (qr <= rmax) & (qa >= amin) & (qa <= amax) & valid_fan
    band = (qr >= rmin - 5) & (qr <= rmax + 5) & (qa >= amin - 5) & (qa <= amax + 5) & (~inside) & valid_fan
    intensities = arr[iy, ix]
    weights = np.maximum(intensities - background, 0.0)
    inner_weights = weights[inside]
    band_weights = weights[band]
    pixel_count = int(np.count_nonzero(inside))
    outer_density = float(np.mean(band_weights)) if int(np.count_nonzero(band)) else 0.0
    local_mask = inside.copy()
    positive_mask = inside & (weights > 0)
    component = connected_components(positive_mask, xs, ys, weights, rx, ry)
    if pixel_count == 0 or len(inner_weights) == 0 or float(np.sum(inner_weights)) <= 1e-9:
        return Measurement(
            pixel_count=pixel_count,
            background=background,
            energy=0.0,
            inner_density=0.0,
            outer_density=outer_density,
            density_ratio=0.0,
            component_count=component.count,
            largest_component_pixels=component.largest_pixels,
            range_p50_m=math.nan,
            range_p80_m=math.nan,
            range_p90_m=math.nan,
            azimuth_p50_m=math.nan,
            azimuth_p80_m=math.nan,
            azimuth_p90_m=math.nan,
            axis_major_std_px=math.nan,
            axis_minor_std_px=math.nan,
            axis_ratio=math.nan,
            axis_vx=math.nan,
            axis_vy=math.nan,
            axis_image_deg=math.nan,
            axis_signed_deg=math.nan,
            axis_acute_deg=math.nan,
            axis_azimuth_acute_deg=math.nan,
            complement_error_deg=math.nan,
            axis_status="AXIS_ENERGY_INVALID",
            component=component,
        )
    xs_i = xs[inside]
    ys_i = ys[inside]
    pr_i = pr[inside]
    pa_i = pa[inside]
    weights_i = inner_weights
    energy = float(np.sum(weights_i))
    major, minor, ratio, vx, vy, image_angle = weighted_major_axis(xs_i, ys_i, weights_i)
    signed = signed_axis_to_ref_deg(vx, vy, rx, ry)
    acute = abs(signed) if not math.isnan(signed) else math.nan
    az_acute = acute_axis_to_ref_deg(vx, vy, ax, ay)
    complement = abs((acute + az_acute) - 90.0) if not math.isnan(acute) and not math.isnan(az_acute) else math.nan
    if math.isnan(ratio):
        axis_status = "AXIS_ENERGY_INVALID"
    elif ratio < AXIS_RATIO_MIN:
        axis_status = "AXIS_NEAR_ISOTROPIC"
    elif component.count > 1:
        axis_status = "AXIS_MULTI_COMPONENT_AMBIGUOUS"
    else:
        axis_status = "AXIS_ORIENTATION_RESOLVED"
    return Measurement(
        pixel_count=pixel_count,
        background=background,
        energy=energy,
        inner_density=energy / max(1, pixel_count),
        outer_density=outer_density,
        density_ratio=(energy / max(1, pixel_count)) / outer_density if outer_density > 1e-9 else math.inf,
        component_count=component.count,
        largest_component_pixels=component.largest_pixels,
        range_p50_m=shortest_weighted_width(pr_i, weights_i, 0.50) * M_PER_PX,
        range_p80_m=shortest_weighted_width(pr_i, weights_i, 0.80) * M_PER_PX,
        range_p90_m=shortest_weighted_width(pr_i, weights_i, 0.90) * M_PER_PX,
        azimuth_p50_m=shortest_weighted_width(pa_i, weights_i, 0.50) * M_PER_PX,
        azimuth_p80_m=shortest_weighted_width(pa_i, weights_i, 0.80) * M_PER_PX,
        azimuth_p90_m=shortest_weighted_width(pa_i, weights_i, 0.90) * M_PER_PX,
        axis_major_std_px=major,
        axis_minor_std_px=minor,
        axis_ratio=ratio,
        axis_vx=vx,
        axis_vy=vy,
        axis_image_deg=image_angle,
        axis_signed_deg=signed,
        axis_acute_deg=acute,
        axis_azimuth_acute_deg=az_acute,
        complement_error_deg=complement,
        axis_status=axis_status,
        component=component,
    )


def threshold_component(
    arr: np.ndarray,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    ax: float,
    ay: float,
    bounds: tuple[float, float, float, float],
    background: float,
    quantile: float,
) -> tuple[Component, float]:
    rmin, rmax, amin, amax = bounds
    xs, ys, _, _, qr, qa = region_arrays(cx, cy, rx, ry, ax, ay, bounds)
    ix = np.clip(xs.astype(int), 0, SAR_WIDTH - 1)
    iy = np.clip(ys.astype(int), 0, SAR_HEIGHT - 1)
    inside = (qr >= rmin) & (qr <= rmax) & (qa >= amin) & (qa <= amax) & fan_valid_points(xs, ys)
    weights = np.maximum(arr[iy, ix] - background, 0.0)
    positive = weights[inside & (weights > 0)]
    threshold = float(np.quantile(positive, quantile)) if len(positive) else math.inf
    mask = inside & (weights >= threshold) & (weights > 0)
    return connected_components(mask, xs, ys, weights, rx, ry), threshold


def component_iou(low: Component, high: Component) -> tuple[float, bool]:
    if low.mask.size == 0 or high.mask.size == 0:
        return 0.0, False
    common_shape = low.mask.shape == high.mask.shape
    if not common_shape:
        return 0.0, False
    inter = int(np.count_nonzero(low.mask & high.mask))
    union = int(np.count_nonzero(low.mask | high.mask))
    high_area = int(np.count_nonzero(high.mask))
    iou = inter / union if union else 0.0
    contained = high_area > 0 and inter == high_area
    return iou, contained


def threshold_identity_status(components: Sequence[Component], transitions: Sequence[dict[str, Any]]) -> str:
    if any(c.largest_pixels <= 0 for c in components):
        return "NO_STABLE_COMPONENT"
    if any(c.largest_pixels < COMPONENT_MIN_PIXELS for c in components):
        return "COMPONENT_TOO_SMALL"
    for tr in transitions:
        if not tr["high_threshold_contained_in_low_threshold"] and tr["from_component_count"] != tr["to_component_count"]:
            return "COMPONENT_SPLIT_OR_MERGE"
        if tr["component_overlap_iou"] < 0.25 or tr["component_centroid_shift_m"] > 0.60:
            return "COMPONENT_IDENTITY_SWITCH"
    return "SAME_COMPONENT_PERSISTENT"


def aspect_candidates(range_obs: float, az_obs: float, axis_status: str, response_axis_acute: float) -> dict[str, Any]:
    cache_key = (round(range_obs, 4), round(az_obs, 4), axis_status)
    if cache_key in _ASPECT_CACHE:
        cached = dict(_ASPECT_CACHE[cache_key])
        if not math.isnan(response_axis_acute) and not math.isnan(parse_float(cached.get("aspect_angle_candidate_deg"))):
            cached["response_axis_aspect_angle_error_deg"] = axis_diff_acute(response_axis_acute, parse_float(cached["aspect_angle_candidate_deg"]))
        return cached
    arrays = aspect_arrays()
    miss_r = np.maximum(0.0, arrays["pred_r"] - range_obs)
    miss_a = np.maximum(0.0, arrays["pred_a"] - az_obs)
    extra_r = np.maximum(0.0, range_obs - arrays["pred_r"])
    extra_a = np.maximum(0.0, az_obs - arrays["pred_a"])
    scores = np.hypot(extra_r, extra_a) + 0.25 * np.hypot(miss_r, miss_a)
    best_idx = int(np.argmin(scores))
    angle_scores: dict[int, float] = {}
    angle_compatible: dict[int, bool] = {}
    for angle in ASPECT_ANGLE_GRID:
        idx = arrays["angle"] == angle
        angle_scores[angle] = float(np.min(scores[idx]))
        angle_compatible[angle] = bool(np.any((extra_r[idx] <= ENVELOPE_EXTRA_TOL_M) & (extra_a[idx] <= ENVELOPE_EXTRA_TOL_M)))
    best = {
        "score": float(scores[best_idx]),
        "angle": int(arrays["angle"][best_idx]),
        "length": float(arrays["length"][best_idx]),
        "width": float(arrays["width"][best_idx]),
        "miss_r": float(miss_r[best_idx]),
        "miss_a": float(miss_a[best_idx]),
        "extra_r": float(extra_r[best_idx]),
        "extra_a": float(extra_a[best_idx]),
    }
    max_extra = max(best["extra_r"], best["extra_a"])
    max_missing = max(best["miss_r"], best["miss_a"])
    if max_extra <= ENVELOPE_EXTRA_TOL_M and max_missing <= ENVELOPE_EXTRA_TOL_M:
        envelope_status = "WITHIN_VEHICLE_PROJECTION_ENVELOPE"
    elif max_extra <= ENVELOPE_EXTRA_TOL_M and max_missing > ENVELOPE_EXTRA_TOL_M:
        envelope_status = "PARTIAL_SUPPORT_BELOW_ENVELOPE"
    elif max_extra > ENVELOPE_EXCEED_TOL_M:
        envelope_status = "EXCEEDS_VEHICLE_PROJECTION_ENVELOPE"
    else:
        envelope_status = "AMBIGUOUS_ENVELOPE_COMPATIBILITY"
    compatible_angles = [a for a in ASPECT_ANGLE_GRID if angle_compatible[a]]
    segments = angle_segments(compatible_angles)
    total_span = sum(b - a for a, b in segments)
    min_score = min(angle_scores.values())
    equivalent = [a for a, score in angle_scores.items() if score <= min_score + 0.03]
    if axis_status != "AXIS_ORIENTATION_RESOLVED":
        ident_status = "AXIS_NOT_RESOLVED"
    elif not compatible_angles:
        ident_status = "ASPECT_ANGLE_NOT_IDENTIFIABLE"
    elif len(segments) == 1 and total_span <= 10:
        ident_status = "ASPECT_ANGLE_LOCALLY_IDENTIFIABLE"
    elif any(a <= 10 for a in compatible_angles) and any(a >= 80 for a in compatible_angles):
        ident_status = "ASPECT_ANGLE_90_DEG_AMBIGUOUS"
    elif total_span <= 45:
        ident_status = "ASPECT_ANGLE_INTERVAL_ONLY"
    else:
        ident_status = "ASPECT_ANGLE_NOT_IDENTIFIABLE"
    result = {
        "vehicle_projection_envelope_status": envelope_status,
        "aspect_angle_candidate_deg": best["angle"],
        "aspect_angle_compatible_interval_deg": ";".join(f"{a}-{b}" if a != b else str(a) for a, b in segments),
        "best_scale_length_m": best["length"],
        "best_scale_width_m": best["width"],
        "projection_residual_m": best["score"],
        "required_missing_support_range_m": best["miss_r"],
        "required_missing_support_azimuth_m": best["miss_a"],
        "required_extra_spread_range_m": best["extra_r"],
        "required_extra_spread_azimuth_m": best["extra_a"],
        "response_axis_aspect_angle_error_deg": axis_diff_acute(response_axis_acute, best["angle"]) if not math.isnan(response_axis_acute) else math.nan,
        "aspect_angle_identifiability_status": ident_status,
        "aspect_angle_compatible_segment_count": len(segments),
        "aspect_angle_compatible_total_span_deg": total_span,
        "equivalent_minimum_count": len(equivalent),
    }
    _ASPECT_CACHE[cache_key] = dict(result)
    return result


def aspect_arrays() -> dict[str, np.ndarray]:
    global _ASPECT_ARRAYS
    if _ASPECT_ARRAYS is not None:
        return _ASPECT_ARRAYS
    angle_values: list[int] = []
    length_values: list[float] = []
    width_values: list[float] = []
    pred_r_values: list[float] = []
    pred_a_values: list[float] = []
    for angle in ASPECT_ANGLE_GRID:
        rad = math.radians(angle)
        c = abs(math.cos(rad))
        s = abs(math.sin(rad))
        for length in VEHICLE_LENGTH_GRID:
            for width in VEHICLE_WIDTH_GRID:
                angle_values.append(angle)
                length_values.append(length)
                width_values.append(width)
                pred_r_values.append(abs(length * c) + abs(width * s))
                pred_a_values.append(abs(length * s) + abs(width * c))
    _ASPECT_ARRAYS = {
        "angle": np.asarray(angle_values, dtype=np.int16),
        "length": np.asarray(length_values, dtype=np.float32),
        "width": np.asarray(width_values, dtype=np.float32),
        "pred_r": np.asarray(pred_r_values, dtype=np.float32),
        "pred_a": np.asarray(pred_a_values, dtype=np.float32),
    }
    return _ASPECT_ARRAYS


def angle_segments(values: Sequence[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    vals = sorted(set(int(v) for v in values))
    segments: list[tuple[int, int]] = []
    start = prev = vals[0]
    for value in vals[1:]:
        if value == prev + 1:
            prev = value
        else:
            segments.append((start, prev))
            start = prev = value
    segments.append((start, prev))
    return segments


def template_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for delta in CENTER_SHIFT_M:
        for axis in ("range", "azimuth"):
            for sign in (-1, 1):
                specs.append({"family": "center_shift", "axis": axis, "operation": "shift", "delta_m": sign * delta, "rotation_deg": 0.0})
    for delta in BOUNDARY_SHIFT_M:
        for side in ("range_min", "range_max", "azimuth_min", "azimuth_max"):
            for sign in (-1, 1):
                specs.append({"family": "single_boundary_shift", "axis": side, "operation": "move", "delta_m": sign * delta, "rotation_deg": 0.0})
    for delta in SCALE_SHIFT_M:
        for axis in ("range", "azimuth"):
            for sign in (-1, 1):
                specs.append({"family": "scale_resize", "axis": axis, "operation": "resize", "delta_m": sign * delta, "rotation_deg": 0.0})
    for rotation in ROTATION_DEG:
        specs.append({"family": "local_region_rotation", "axis": "local_region", "operation": "rotate", "delta_m": 0.0, "rotation_deg": float(rotation)})
    return specs


def apply_spec(
    bounds: tuple[float, float, float, float],
    spec: Mapping[str, Any],
) -> tuple[tuple[float, float, float, float], float, float, float]:
    rmin, rmax, amin, amax = bounds
    delta_px = float(spec["delta_m"]) / M_PER_PX
    center_r = 0.0
    center_a = 0.0
    rotation = float(spec["rotation_deg"])
    family = spec["family"]
    axis = spec["axis"]
    if family == "center_shift":
        if axis == "range":
            center_r = delta_px
        else:
            center_a = delta_px
    elif family == "single_boundary_shift":
        if axis == "range_min":
            rmin += delta_px
        elif axis == "range_max":
            rmax += delta_px
        elif axis == "azimuth_min":
            amin += delta_px
        elif axis == "azimuth_max":
            amax += delta_px
    elif family == "scale_resize":
        if axis == "range":
            rmin -= delta_px / 2.0
            rmax += delta_px / 2.0
        else:
            amin -= delta_px / 2.0
            amax += delta_px / 2.0
    if rmax < rmin:
        mid = (rmin + rmax) / 2.0
        rmin, rmax = mid, mid
    if amax < amin:
        mid = (amin + amax) / 2.0
        amin, amax = mid, mid
    return (rmin, rmax, amin, amax), center_r, center_a, rotation


def conservative_geometry_key(row: Mapping[str, str]) -> str:
    box = parse_box(row.get("conservative_bbox", ""))
    if box is not None:
        return box_text(box)
    return row.get("conservative_bbox", "").strip()


def group_independent_geometries(s1_rows: Sequence[Mapping[str, str]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in s1_rows:
        key = conservative_geometry_key(row)
        grouped[key].append(row)
    groups: list[dict[str, Any]] = []
    id_by_response: dict[str, str] = {}
    def sort_key(key: str) -> tuple[float, float, float, float, str]:
        box = parse_box(key)
        if box is None:
            return (math.inf, math.inf, math.inf, math.inf, key)
        return (box.x1, box.y1, box.x2, box.y2, key)

    for idx, key in enumerate(sorted(grouped, key=sort_key), start=1):
        members = sorted(grouped[key], key=lambda r: (parse_float(r.get("sar_frame"), math.inf), r.get("response_unit_id", "")))
        gid = f"GM019IG{idx:04d}"
        for member in members:
            id_by_response[member.get("response_unit_id", "")] = gid
        rep = members[0]
        frames = sorted({str(int(float(m.get("sar_frame", "0")))) for m in members if m.get("sar_frame", "") != ""}, key=lambda v: int(v))
        groups.append(
            {
                "independent_geometry_id": gid,
                "key": key,
                "members": members,
                "representative": rep,
                "member_ids": [m.get("response_unit_id", "") for m in members],
                "member_sar_frames": frames,
            }
        )
    return groups, id_by_response


def build_geometry_map(groups: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for group in groups:
        rep = group["representative"]
        rows.append(
            {
                "independent_geometry_id": group["independent_geometry_id"],
                "scene": rep.get("scene", SCENE),
                "sar_frame": rep.get("sar_frame", ""),
                "member_sar_frames": ";".join(group.get("member_sar_frames", [])),
                "conservative_bbox": rep.get("conservative_bbox", ""),
                "core_bbox": rep.get("core_bbox", ""),
                "member_response_unit_count": str(len(group["member_ids"])),
                "member_response_unit_ids": ";".join(group["member_ids"]),
                "representative_response_unit_id": rep.get("response_unit_id", ""),
                "measured_once_then_mapped_to_members": "true",
            }
        )
    return rows


def axis_self_tests() -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    ux, uy = 1.0, 0.0

    def add(name: str, ok: bool, detail: str) -> None:
        if not ok:
            failures.append({"failure_id": name, "independent_geometry_id": "", "response_unit_id": "", "failure_type": name, "severity": "HIGH", "detail": detail})

    v45 = canonical_axis(math.cos(math.radians(45)), math.sin(math.radians(45)))
    v135 = canonical_axis(math.cos(math.radians(135)), math.sin(math.radians(135)))
    s45 = signed_axis_to_ref_deg(v45[0], v45[1], ux, uy)
    s135 = signed_axis_to_ref_deg(v135[0], v135[1], ux, uy)
    add("axis_45_vs_135_not_collapsed", s45 > 0 and s135 < 0 and abs(abs(s45) - abs(s135)) < 1e-6, f"s45={s45}; s135={s135}")
    v = canonical_axis(0.2, -0.9)
    vn = canonical_axis(-0.2, 0.9)
    add("axis_v_and_minus_v_equivalent", abs(v[2] - vn[2]) < 1e-6, f"v={v[2]}; -v={vn[2]}")
    v0 = canonical_axis(1.0, 0.0)
    v180 = canonical_axis(-1.0, 0.0)
    add("rotation_180_equivalent_to_0", abs(v0[2] - v180[2]) < 1e-6, f"0={v0[2]}; 180={v180[2]}")
    l, w = 5.0, 2.0
    pred0 = (abs(l * math.cos(0)) + abs(w * math.sin(0)), abs(l * math.sin(0)) + abs(w * math.cos(0)))
    pred90 = (abs(l * math.cos(math.radians(90))) + abs(w * math.sin(math.radians(90))), abs(l * math.sin(math.radians(90))) + abs(w * math.cos(math.radians(90))))
    add("rotation_90_long_short_swap_recorded", abs(pred0[0] - pred90[1]) < 1e-6 and abs(pred0[1] - pred90[0]) < 1e-6, f"pred0={pred0}; pred90={pred90}")
    return failures


def build_generation(write_visuals: bool = True) -> dict[str, list[dict[str, Any]]]:
    s1_rows = read_rows(INPUTS["s1_rows"])
    groups, _ = group_independent_geometries(s1_rows)
    geometry_map_rows = build_geometry_map(groups)
    axis_rows: list[dict[str, Any]] = []
    threshold_component_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    envelope_rows: list[dict[str, Any]] = []
    spec_rows: list[dict[str, Any]] = []
    measurement_rows: list[dict[str, Any]] = []
    semantic_failures: list[dict[str, str]] = axis_self_tests()
    visual_candidates: list[dict[str, Any]] = []
    specs = template_specs()

    for group_index, group in enumerate(groups, start=1):
        if group_index == 1 or group_index % 25 == 0 or group_index == len(groups):
            print(f"generate progress: independent_geometry {group_index}/{len(groups)}", flush=True)
        gid = group["independent_geometry_id"]
        rep = group["representative"]
        members = group["members"]
        member_ids = group["member_ids"]
        frame = int(float(rep["sar_frame"]))
        arr = load_gray(frame)
        box = parse_box(rep.get("conservative_bbox", "")) or parse_box(rep.get("core_bbox", ""))
        if box is None:
            semantic_failures.append({"failure_id": f"{gid}_missing_box", "independent_geometry_id": gid, "response_unit_id": rep.get("response_unit_id", ""), "failure_type": "MISSING_BOX", "severity": "HIGH", "detail": "no conservative/core bbox"})
            continue
        cx = parse_float(rep.get("response_center_x"), box.cx)
        cy = parse_float(rep.get("response_center_y"), box.cy)
        rx, ry, ax, ay = unit_vectors(cx, cy)
        bounds = local_bounds_for_box(box, cx, cy, rx, ry, ax, ay)
        grid = make_region_grid(arr, cx, cy, rx, ry, ax, ay, bounds)
        background = parse_float(rep.get("background_estimate"), 0.0)
        base = measure_region_grid(grid, rx, ry, ax, ay, bounds, background)

        components: list[Component] = []
        comp_rows_for_gid: list[dict[str, Any]] = []
        for setting, q in THRESHOLD_SETTINGS:
            comp, threshold = threshold_component_grid(grid, rx, ry, bounds, background, q)
            components.append(comp)
            distance_m = math.hypot(comp.centroid_x - cx, comp.centroid_y - cy) * M_PER_PX if not math.isnan(comp.centroid_x) else math.nan
            mask_hash = hashlib.sha256(np.packbits(comp.mask.astype(np.uint8)).tobytes()).hexdigest() if comp.mask.size else ""
            row = {
                "independent_geometry_id": gid,
                "sar_frame": str(frame),
                "threshold_setting": setting,
                "threshold_quantile": fmt(q, 2),
                "threshold_value": fmt(threshold),
                "component_count": str(comp.count),
                "largest_component_pixels": str(comp.largest_pixels),
                "largest_component_area_px": str(int(np.count_nonzero(comp.mask))),
                "component_mask_sha256": mask_hash,
                "component_centroid_x": fmt(comp.centroid_x),
                "component_centroid_y": fmt(comp.centroid_y),
                "component_bbox": comp.bbox,
                "component_response_center_distance_m": fmt(distance_m),
                "component_axis_image_deg": fmt(comp.axis_image_deg),
                "component_axis_to_range_signed_deg": fmt(comp.axis_signed_deg),
                "component_axis_to_range_acute_deg": fmt(comp.axis_acute_deg),
                "component_principal_axis_ratio": fmt(comp.axis_ratio),
            }
            threshold_component_rows.append(row)
            comp_rows_for_gid.append(row)

        local_transitions: list[dict[str, Any]] = []
        for i in range(len(components) - 1):
            low = components[i]
            high = components[i + 1]
            iou, contained = component_iou(low, high)
            centroid_shift = math.hypot(high.centroid_x - low.centroid_x, high.centroid_y - low.centroid_y) * M_PER_PX if not any(math.isnan(v) for v in (low.centroid_x, low.centroid_y, high.centroid_x, high.centroid_y)) else math.nan
            retention = high.largest_pixels / low.largest_pixels if low.largest_pixels else 0.0
            axis_change = axis_diff_acute(low.axis_image_deg, high.axis_image_deg)
            tr = {
                "independent_geometry_id": gid,
                "sar_frame": str(frame),
                "from_threshold_setting": THRESHOLD_SETTINGS[i][0],
                "to_threshold_setting": THRESHOLD_SETTINGS[i + 1][0],
                "component_overlap_iou": iou,
                "high_threshold_contained_in_low_threshold": contained,
                "component_centroid_shift_m": centroid_shift,
                "component_area_retention_ratio": retention,
                "component_axis_change_deg": axis_change,
                "from_component_count": low.count,
                "to_component_count": high.count,
            }
            local_transitions.append(tr)
        threshold_status = threshold_identity_status(components, local_transitions)
        for tr in local_transitions:
            tr["threshold_component_identity_status"] = threshold_status
            transition_rows.append({k: fmt(v) if isinstance(v, float) else ("true" if v is True else "false" if v is False else str(v)) for k, v in tr.items()})

        axis_status = base.axis_status
        if axis_status == "AXIS_ORIENTATION_RESOLVED" and threshold_status != "SAME_COMPONENT_PERSISTENT":
            axis_status = "AXIS_THRESHOLD_UNSTABLE"
        env = aspect_candidates(base.range_p80_m, base.azimuth_p80_m, axis_status, base.axis_acute_deg)
        axis_row = {
            "scene": SCENE,
            "independent_geometry_id": gid,
            "response_unit_id": rep.get("response_unit_id", ""),
            "member_response_unit_count": str(len(member_ids)),
            "member_response_unit_ids": ";".join(member_ids),
            "sar_frame": str(frame),
            "sar_gray_image_relpath": frame_image_path(frame).as_posix(),
            "core_bbox": rep.get("core_bbox", ""),
            "conservative_bbox": rep.get("conservative_bbox", ""),
            "calibration_status": CALIBRATION_STATUS,
            "max_range_m": fmt(MAX_RANGE_M),
            "radial_grid_spacing_m_per_px": fmt(M_PER_PX),
            "sar_fan_center_x_px": fmt(FAN_CENTER_X),
            "sar_fan_center_y_px": fmt(FAN_CENTER_Y),
            "gt_file_opened": "false",
            "paired_annotations_opened": "false",
            "mask_audit_opened": "false",
            "generation_input_scope": "sar_gray+s1_frozen_rows+local_response_units+boundary_variant_families+s1_r1_protocol+project_confirmed_calibration_only",
            "response_center_x": fmt(cx),
            "response_center_y": fmt(cy),
            "absolute_range_m": fmt(radial_px(cx, cy) * M_PER_PX),
            "range_unit_x": fmt(rx),
            "range_unit_y": fmt(ry),
            "azimuth_unit_x": fmt(ax),
            "azimuth_unit_y": fmt(ay),
            "background_mode": "BASE_REGION_FROZEN_BACKGROUND",
            "frozen_background_estimate": fmt(background),
            "measured_background_subtracted_energy": fmt(base.energy),
            "measured_inner_energy_density": fmt(base.inner_density),
            "measured_outer_band_energy_density": fmt(base.outer_density),
            "measured_inner_outer_density_ratio": fmt(base.density_ratio),
            "measured_component_count": str(base.component_count),
            "measured_largest_component_pixels": str(base.largest_component_pixels),
            "measured_range_p50_width_m": fmt(base.range_p50_m),
            "measured_range_p80_width_m": fmt(base.range_p80_m),
            "measured_range_p90_width_m": fmt(base.range_p90_m),
            "measured_azimuth_p50_width_m": fmt(base.azimuth_p50_m),
            "measured_azimuth_p80_width_m": fmt(base.azimuth_p80_m),
            "measured_azimuth_p90_width_m": fmt(base.azimuth_p90_m),
            "principal_axis_major_std_px": fmt(base.axis_major_std_px),
            "principal_axis_minor_std_px": fmt(base.axis_minor_std_px),
            "principal_axis_ratio": fmt(base.axis_ratio),
            "response_axis_vector_x": fmt(base.axis_vx),
            "response_axis_vector_y": fmt(base.axis_vy),
            "response_axis_image_deg": fmt(base.axis_image_deg),
            "response_axis_to_range_signed_deg": fmt(base.axis_signed_deg),
            "response_axis_to_range_acute_deg": fmt(base.axis_acute_deg),
            "response_axis_to_azimuth_acute_deg": fmt(base.axis_azimuth_acute_deg),
            "range_azimuth_acute_complement_error_deg": fmt(base.complement_error_deg),
            "axis_orientation_status": axis_status,
            "threshold_component_identity_status": threshold_status,
        }
        axis_rows.append(axis_row)
        envelope_rows.append(
            {
                "independent_geometry_id": gid,
                "response_unit_id": rep.get("response_unit_id", ""),
                "sar_frame": str(frame),
                "measured_range_p80_width_m": fmt(base.range_p80_m),
                "measured_azimuth_p80_width_m": fmt(base.azimuth_p80_m),
                "vehicle_projection_envelope_status": env["vehicle_projection_envelope_status"],
                "aspect_angle_candidate_deg": fmt(env["aspect_angle_candidate_deg"]),
                "aspect_angle_compatible_interval_deg": env["aspect_angle_compatible_interval_deg"],
                "best_scale_length_m": fmt(env["best_scale_length_m"]),
                "best_scale_width_m": fmt(env["best_scale_width_m"]),
                "projection_residual_m": fmt(env["projection_residual_m"]),
                "required_missing_support_range_m": fmt(env["required_missing_support_range_m"]),
                "required_missing_support_azimuth_m": fmt(env["required_missing_support_azimuth_m"]),
                "required_extra_spread_range_m": fmt(env["required_extra_spread_range_m"]),
                "required_extra_spread_azimuth_m": fmt(env["required_extra_spread_azimuth_m"]),
                "response_axis_aspect_angle_error_deg": fmt(env["response_axis_aspect_angle_error_deg"]),
                "aspect_angle_identifiability_status": env["aspect_angle_identifiability_status"],
                "aspect_angle_compatible_segment_count": str(env["aspect_angle_compatible_segment_count"]),
                "aspect_angle_compatible_total_span_deg": fmt(env["aspect_angle_compatible_total_span_deg"]),
                "equivalent_minimum_count": str(env["equivalent_minimum_count"]),
                "vehicle_scale_semantic_note_cn": "车辆尺度为投影包络，不是精确匹配目标；局部支撑低于包络不能作为非车辆证据。",
            }
        )

        base_rotation_90_delta = math.nan
        rotation_deltas: list[tuple[str, float]] = []
        for idx, spec in enumerate(specs, start=1):
            template_id = f"{gid}_T{idx:02d}"
            pert_bounds, shift_r, shift_a, rotation = apply_spec(bounds, spec)
            delta_px = float(spec["delta_m"]) / M_PER_PX
            spec_rows.append(
                {
                    "template_id": template_id,
                    "independent_geometry_id": gid,
                    "member_response_unit_ids": ";".join(member_ids),
                    "sar_frame": str(frame),
                    "template_family": spec["family"],
                    "template_axis": spec["axis"],
                    "template_operation": spec["operation"],
                    "delta_m": fmt(spec["delta_m"]),
                    "delta_px": fmt(delta_px),
                    "rotation_deg": fmt(rotation),
                    "template_scope": "GT-independent local frozen response geometry",
                }
            )
            pert = measure_region_grid(grid, rx, ry, ax, ay, pert_bounds, background, rotation, shift_r, shift_a)
            sensitivity_bg = estimate_local_ring_background_grid(grid, pert_bounds, rotation, shift_r, shift_a)
            pert_sens = measure_region_grid(grid, rx, ry, ax, ay, pert_bounds, sensitivity_bg, rotation, shift_r, shift_a)
            direction_a = math.copysign(1.0, pert.energy - base.energy) if abs(pert.energy - base.energy) > 1e-9 else 0.0
            direction_b = math.copysign(1.0, pert_sens.energy - base.energy) if abs(pert_sens.energy - base.energy) > 1e-9 else 0.0
            bg_status = "COUNTERFACTUAL_BACKGROUND_STABLE" if direction_a == direction_b else "COUNTERFACTUAL_BACKGROUND_SENSITIVE"
            pert_env = aspect_candidates(pert.range_p80_m, pert.azimuth_p80_m, pert.axis_status, pert.axis_acute_deg)
            angle_delta = axis_diff_acute(base.axis_image_deg, pert.axis_image_deg)
            if spec["family"] == "local_region_rotation":
                rotation_deltas.append((template_id, angle_delta if not math.isnan(angle_delta) else 0.0))
                if int(rotation) == 90:
                    base_rotation_90_delta = angle_delta
            measurement_rows.append(
                {
                    "template_id": template_id,
                    "independent_geometry_id": gid,
                    "sar_frame": str(frame),
                    "template_family": spec["family"],
                    "template_axis": spec["axis"],
                    "template_operation": spec["operation"],
                    "delta_m": fmt(spec["delta_m"]),
                    "delta_px": fmt(delta_px),
                    "rotation_deg": fmt(rotation),
                    "measurement_source": "REAL_SAR_GRAY_REMEASURED",
                    "proxy_formula_used": "false",
                    "background_mode": "BASE_REGION_FROZEN_BACKGROUND",
                    "sensitivity_background_mode": "PERTURBED_LOCAL_RING",
                    "counterfactual_background_sensitivity_status": bg_status,
                    "base_background_subtracted_energy": fmt(base.energy),
                    "measured_background_subtracted_energy": fmt(pert.energy),
                    "energy_delta_measured": fmt(pert.energy - base.energy),
                    "base_inner_energy_density": fmt(base.inner_density),
                    "measured_inner_energy_density": fmt(pert.inner_density),
                    "inner_density_delta_measured": fmt(pert.inner_density - base.inner_density),
                    "base_outer_band_energy_density": fmt(base.outer_density),
                    "measured_outer_band_energy_density": fmt(pert.outer_density),
                    "outer_density_delta_measured": fmt(pert.outer_density - base.outer_density),
                    "measured_inner_outer_density_ratio": fmt(pert.density_ratio),
                    "base_component_count": str(base.component_count),
                    "measured_component_count": str(pert.component_count),
                    "component_count_delta_measured": str(pert.component_count - base.component_count),
                    "measured_largest_component_pixels": str(pert.largest_component_pixels),
                    "measured_range_p50_width_m": fmt(pert.range_p50_m),
                    "measured_range_p80_width_m": fmt(pert.range_p80_m),
                    "measured_range_p90_width_m": fmt(pert.range_p90_m),
                    "range_p80_delta_m_measured": fmt(pert.range_p80_m - base.range_p80_m),
                    "measured_azimuth_p50_width_m": fmt(pert.azimuth_p50_m),
                    "measured_azimuth_p80_width_m": fmt(pert.azimuth_p80_m),
                    "measured_azimuth_p90_width_m": fmt(pert.azimuth_p90_m),
                    "azimuth_p80_delta_m_measured": fmt(pert.azimuth_p80_m - base.azimuth_p80_m),
                    "measured_response_axis_image_deg": fmt(pert.axis_image_deg),
                    "measured_response_axis_to_range_signed_deg": fmt(pert.axis_signed_deg),
                    "measured_response_axis_to_range_acute_deg": fmt(pert.axis_acute_deg),
                    "axis_angle_delta_deg_measured": fmt(angle_delta),
                    "measured_principal_axis_ratio": fmt(pert.axis_ratio),
                    "measured_axis_orientation_status": pert.axis_status,
                    "measured_vehicle_projection_envelope_status": pert_env["vehicle_projection_envelope_status"],
                    "measured_aspect_angle_candidate_deg": fmt(pert_env["aspect_angle_candidate_deg"]),
                }
            )

        visual_candidates.append(
            {
                "group": group,
                "axis_row": axis_row,
                "envelope": envelope_rows[-1],
                "threshold_components": comp_rows_for_gid,
                "threshold_status": threshold_status,
                "rotation_max_delta": max((v for _, v in rotation_deltas), default=0.0),
                "rotation_90_delta": base_rotation_90_delta,
                "base_bounds": bounds,
                "rx": rx,
                "ry": ry,
                "ax": ax,
                "ay": ay,
                "cx": cx,
                "cy": cy,
            }
        )

        if base.complement_error_deg > 1e-6:
            semantic_failures.append({"failure_id": f"{gid}_complement_error", "independent_geometry_id": gid, "response_unit_id": rep.get("response_unit_id", ""), "failure_type": "RANGE_AZIMUTH_COMPLEMENT", "severity": "MEDIUM", "detail": f"error={fmt(base.complement_error_deg)}"})

    visual_rows = build_visual_review(visual_candidates, write_visuals)
    return {
        "axis_observations": axis_rows,
        "threshold_components": threshold_component_rows,
        "threshold_transitions": transition_rows,
        "vehicle_projection_envelope": envelope_rows,
        "counterfactual_specs": spec_rows,
        "counterfactual_measurements": measurement_rows,
        "independent_geometry_map": geometry_map_rows,
        "semantic_failures": semantic_failures,
        "pre_eval_seal": pre_eval_seal_rows(axis_rows, geometry_map_rows),
        "visual_manifest": visual_rows,
    }


def select_visual_cases(candidates: Sequence[Mapping[str, Any]]) -> list[tuple[str, Mapping[str, Any], str]]:
    used: set[str] = set()
    chosen: list[tuple[str, Mapping[str, Any], str]] = []

    def choose(label: str, key_fn: Any, reason: str, reverse: bool = False) -> None:
        pool = [c for c in candidates if c["axis_row"]["independent_geometry_id"] not in used]
        if not pool:
            return
        best = sorted(pool, key=key_fn, reverse=reverse)[0]
        used.add(best["axis_row"]["independent_geometry_id"])
        chosen.append((label, best, reason))

    def choose_envelope_status(label: str, status: str, fallback_label: str, fallback_reason: str) -> None:
        pool = [c for c in candidates if c["axis_row"]["independent_geometry_id"] not in used]
        matching = [c for c in pool if c["envelope"]["vehicle_projection_envelope_status"] == status]
        if matching:
            best = sorted(matching, key=lambda c: c["axis_row"]["independent_geometry_id"])[0]
            used.add(best["axis_row"]["independent_geometry_id"])
            chosen.append((label, best, f"vehicle projection envelope status is {status}"))
            return
        choose(
            fallback_label,
            lambda c: max(
                parse_float(c["envelope"]["required_extra_spread_range_m"], 0.0),
                parse_float(c["envelope"]["required_extra_spread_azimuth_m"], 0.0),
            ),
            fallback_reason,
            reverse=True,
        )

    choose("axis_image_about_45", lambda c: abs(parse_float(c["axis_row"]["response_axis_image_deg"]) - 45.0), "image axis closest to 45 degrees")
    choose("axis_image_about_135", lambda c: abs(parse_float(c["axis_row"]["response_axis_image_deg"]) - 135.0), "image axis closest to 135 degrees")
    choose("near_range_axis", lambda c: parse_float(c["axis_row"]["response_axis_to_range_acute_deg"]), "acute angle closest to range axis")
    choose("near_azimuth_axis", lambda c: abs(parse_float(c["axis_row"]["response_axis_to_range_acute_deg"]) - 90.0), "acute angle closest to azimuth axis")
    choose("near_isotropic", lambda c: parse_float(c["axis_row"]["principal_axis_ratio"], 999.0), "lowest principal-axis ratio")
    choose("multi_component", lambda c: 0 if c["axis_row"]["axis_orientation_status"] == "AXIS_MULTI_COMPONENT_AMBIGUOUS" else 1, "multi-component ambiguous axis")
    choose("threshold_identity_switch", lambda c: 0 if c["threshold_status"] != "SAME_COMPONENT_PERSISTENT" else 1, "threshold identity not persistent")
    choose("rotation_sensitive", lambda c: c["rotation_max_delta"], "largest measured rotation axis delta", reverse=True)
    choose("rotation_insensitive", lambda c: c["rotation_max_delta"], "smallest measured rotation axis delta")
    choose_envelope_status(
        "exceeds_vehicle_projection_envelope",
        "EXCEEDS_VEHICLE_PROJECTION_ENVELOPE",
        "no_exceeds_envelope_observed_max_extra_spread",
        "no EXCEEDS_VEHICLE_PROJECTION_ENVELOPE row observed; fallback shows maximum extra spread",
    )
    choose_envelope_status(
        "partial_support_below_envelope",
        "PARTIAL_SUPPORT_BELOW_ENVELOPE",
        "no_partial_support_observed_min_missing_support",
        "no PARTIAL_SUPPORT_BELOW_ENVELOPE row observed; fallback shows smallest missing support",
    )
    choose("duplicate_independent_geometry", lambda c: -int(c["axis_row"]["member_response_unit_count"]), "duplicate response units mapped to one independent geometry")
    return chosen


def build_visual_review(candidates: Sequence[Mapping[str, Any]], write_visuals: bool) -> list[dict[str, str]]:
    selected = select_visual_cases(candidates)
    rows: list[dict[str, str]] = []
    if write_visuals:
        VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    thumbs: list[Image.Image] = []
    for idx, (label, candidate, reason) in enumerate(selected, start=1):
        axis_row = candidate["axis_row"]
        group = candidate["group"]
        rep = group["representative"]
        gid = axis_row["independent_geometry_id"]
        frame = int(axis_row["sar_frame"])
        out = VISUAL_DIR / f"{idx:02d}_{label}_{gid}.png"
        if write_visuals:
            img = render_visual_case(candidate, label, reason)
            img.save(out)
            thumb = img.copy()
            thumb.thumbnail((360, 260))
            thumbs.append(thumb)
        rows.append(
            {
                "visual_case_id": f"VR{idx:02d}",
                "review_label": label,
                "independent_geometry_id": gid,
                "response_unit_id": rep.get("response_unit_id", ""),
                "sar_frame": str(frame),
                "visual_relpath": rel(out),
                "opened_for_review": "pending_manual_open",
                "selection_reason": reason,
            }
        )
    if write_visuals and thumbs:
        montage_w = 720
        montage_h = math.ceil(len(thumbs) / 2) * 300
        montage = Image.new("RGB", (montage_w, montage_h), "white")
        draw = ImageDraw.Draw(montage)
        for i, thumb in enumerate(thumbs):
            x = (i % 2) * 360
            y = (i // 2) * 300
            montage.paste(thumb, (x, y + 30))
            draw.text((x + 6, y + 6), rows[i]["review_label"], fill=(0, 0, 0))
        montage_path = VISUAL_DIR / "00_visual_review_montage.png"
        montage.save(montage_path)
    return rows


def render_visual_case(candidate: Mapping[str, Any], label: str, reason: str) -> Image.Image:
    axis_row = candidate["axis_row"]
    rep = candidate["group"]["representative"]
    frame = int(axis_row["sar_frame"])
    arr = load_gray(frame).astype(np.uint8)
    box = parse_box(rep.get("conservative_bbox", "")) or Box(0, 0, 1, 1)
    pad = 90
    x1 = max(0, int(box.x1) - pad)
    y1 = max(0, int(box.y1) - pad)
    x2 = min(SAR_WIDTH, int(box.x2) + pad)
    y2 = min(SAR_HEIGHT, int(box.y2) + pad)
    crop = Image.fromarray(arr[y1:y2, x1:x2]).convert("RGB")
    scale = 2
    crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(crop)

    def pt(x: float, y: float) -> tuple[float, float]:
        return (x - x1) * scale, (y - y1) * scale

    def rect(b: Box, color: tuple[int, int, int], width: int = 3) -> None:
        draw.rectangle([pt(b.x1, b.y1), pt(b.x2, b.y2)], outline=color, width=width)

    rect(box, (255, 60, 60), 3)
    cx = parse_float(axis_row["response_center_x"], box.cx)
    cy = parse_float(axis_row["response_center_y"], box.cy)
    rx = candidate["rx"]
    ry = candidate["ry"]
    ax = candidate["ax"]
    ay = candidate["ay"]
    cpt = pt(cx, cy)
    draw.line([cpt, pt(cx + rx * 55, cy + ry * 55)], fill=(0, 255, 0), width=3)
    draw.line([cpt, pt(cx + ax * 55, cy + ay * 55)], fill=(0, 180, 255), width=3)
    vx = parse_float(axis_row["response_axis_vector_x"], 0.0)
    vy = parse_float(axis_row["response_axis_vector_y"], 0.0)
    draw.line([pt(cx - vx * 65, cy - vy * 65), pt(cx + vx * 65, cy + vy * 65)], fill=(255, 220, 0), width=3)
    for comp_row, color in zip(candidate["threshold_components"], [(255, 0, 255), (255, 128, 0), (255, 255, 255)]):
        cb = parse_box(comp_row.get("component_bbox", ""))
        if cb:
            rect(cb, color, 2)
    # Draw a +15 degree local rotation outline.
    draw_rotated_local_rect(draw, candidate, 15.0, x1, y1, scale, (120, 255, 120))
    text = [
        label,
        reason,
        f"IG={axis_row['independent_geometry_id']} RU={axis_row['response_unit_id']} F={frame}",
        f"img_axis={axis_row['response_axis_image_deg']} signed={axis_row['response_axis_to_range_signed_deg']} acute={axis_row['response_axis_to_range_acute_deg']}",
        f"axis_status={axis_row['axis_orientation_status']} threshold={axis_row['threshold_component_identity_status']}",
        f"env={candidate['envelope']['vehicle_projection_envelope_status']} aspect={candidate['envelope']['aspect_angle_candidate_deg']}",
    ]
    y_text = 8
    for line in text:
        draw.rectangle([4, y_text - 2, min(crop.width - 4, 8 + len(line) * 7), y_text + 15], fill=(255, 255, 255))
        draw.text((8, y_text), line, fill=(0, 0, 0))
        y_text += 18
    return crop


def draw_rotated_local_rect(draw: ImageDraw.ImageDraw, candidate: Mapping[str, Any], rotation_deg: float, x0: int, y0: int, scale: int, color: tuple[int, int, int]) -> None:
    bounds = candidate["base_bounds"]
    cx = candidate["cx"]
    cy = candidate["cy"]
    rx = candidate["rx"]
    ry = candidate["ry"]
    ax = candidate["ax"]
    ay = candidate["ay"]
    rmin, rmax, amin, amax = bounds
    rad = math.radians(rotation_deg)
    c = math.cos(rad)
    s = math.sin(rad)
    pts = []
    for rr, aa in ((rmin, amin), (rmax, amin), (rmax, amax), (rmin, amax)):
        pr = rr * c - aa * s
        pa = rr * s + aa * c
        x = cx + pr * rx + pa * ax
        y = cy + pr * ry + pa * ay
        pts.append(((x - x0) * scale, (y - y0) * scale))
    draw.line(pts + [pts[0]], fill=color, width=2)


def pre_eval_seal_rows(axis_rows: Sequence[Mapping[str, Any]], geometry_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {"seal_key": "calibration_status", "seal_value": CALIBRATION_STATUS, "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "max_range_m", "seal_value": fmt(MAX_RANGE_M), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "radial_grid_spacing_m_per_px", "seal_value": fmt(M_PER_PX), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "sar_fan_center", "seal_value": f"{fmt(FAN_CENTER_X)},{fmt(FAN_CENTER_Y)}", "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "gt_file_opened", "seal_value": "false", "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "paired_annotations_opened", "seal_value": "false", "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "mask_audit_opened", "seal_value": "false", "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "s1_frozen_rows", "seal_value": "opened", "source_file": rel(INPUTS["s1_rows"]), "sha256": sha256(INPUTS["s1_rows"]), "row_count": str(row_count(INPUTS["s1_rows"]))},
        {"seal_key": "local_response_units", "seal_value": "opened", "source_file": rel(INPUTS["local_response_units"]), "sha256": sha256(INPUTS["local_response_units"]), "row_count": str(row_count(INPUTS["local_response_units"]))},
        {"seal_key": "boundary_variant_families", "seal_value": "opened", "source_file": rel(INPUTS["boundary_variant_families"]), "sha256": sha256(INPUTS["boundary_variant_families"]), "row_count": str(row_count(INPUTS["boundary_variant_families"]))},
        {"seal_key": "protocol_doc", "seal_value": "opened", "source_file": rel(INPUTS["protocol"]), "sha256": sha256(INPUTS["protocol"]), "row_count": ""},
        {"seal_key": "response_unit_count", "seal_value": str(row_count(INPUTS["s1_rows"])), "source_file": rel(INPUTS["s1_rows"]), "sha256": sha256(INPUTS["s1_rows"]), "row_count": str(row_count(INPUTS["s1_rows"]))},
        {"seal_key": "independent_geometry_count", "seal_value": str(len(geometry_rows)), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "generator_source_sha256", "seal_value": sha256(Path(__file__)), "source_file": rel(Path(__file__)), "sha256": sha256(Path(__file__)), "row_count": ""},
    ]


def write_workspace_note(stage: str, status: str) -> None:
    WORKSPACE_TASK_DIR.mkdir(parents=True, exist_ok=True)
    readme = WORKSPACE_TASK_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# OTY2 GM_RM019 static axis rotation S1-R1\n\n"
            "- Active repo: D:/profile/research/optical-sar-visual-diagnosis\n"
            "- Interpreter: D:/MINICONDA/envs/py311/python.exe\n"
            "- Boundary: S1-R1 semantic repair only; no GT S2 evaluation; no selector/final box.\n",
            encoding="utf-8",
        )
    WORKSPACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WORKSPACE_LOG.open("a", encoding="utf-8") as f:
        f.write(f"- {stage}: {status}\n")


def write_outputs(rows_by_key: Mapping[str, Sequence[Mapping[str, Any]]], outputs: Mapping[str, Path]) -> None:
    field_map = {
        "axis_observations": AXIS_FIELDS,
        "threshold_components": THRESHOLD_COMPONENT_FIELDS,
        "threshold_transitions": THRESHOLD_TRANSITION_FIELDS,
        "vehicle_projection_envelope": ENVELOPE_FIELDS,
        "counterfactual_specs": SPEC_FIELDS,
        "counterfactual_measurements": MEASUREMENT_FIELDS,
        "independent_geometry_map": GEOMETRY_MAP_FIELDS,
        "semantic_failures": FAILURE_FIELDS,
        "pre_eval_seal": SEAL_FIELDS,
        "visual_manifest": VISUAL_FIELDS,
    }
    for key, fields in field_map.items():
        write_csv(outputs[key], rows_by_key.get(key, []), fields)


def current_outputs() -> dict[str, Path]:
    return dict(OUTPUTS)


def temp_outputs() -> dict[str, Path]:
    return {key: VERIFY_TMP / path.name for key, path in OUTPUTS.items()}


def output_hashes(outputs: Mapping[str, Path], keys: Sequence[str]) -> dict[str, str]:
    return {key: sha256(outputs[key]) for key in keys if outputs[key].exists()}


def generate() -> None:
    rows = build_generation(write_visuals=True)
    write_outputs(rows, current_outputs())
    write_workspace_note("generate", STATUS_READY)
    print(f"generate: {STATUS_READY}")


def verify_replay() -> None:
    outputs = current_outputs()
    missing = [key for key in GENERATED_KEYS if not outputs[key].exists()]
    if missing:
        raise FileNotFoundError("missing generated outputs: " + ", ".join(missing))
    current = output_hashes(outputs, GENERATED_KEYS)
    if VERIFY_TMP.exists():
        shutil.rmtree(VERIFY_TMP)
    VERIFY_TMP.mkdir(parents=True, exist_ok=True)
    temp = temp_outputs()
    rows = build_generation(write_visuals=False)
    write_outputs(rows, temp)
    replay = output_hashes(temp, GENERATED_KEYS)
    replay_rows: list[dict[str, str]] = []
    mismatches: list[str] = []
    for key in GENERATED_KEYS:
        status = "PASS" if current.get(key) == replay.get(key) else "FAIL"
        if status == "FAIL":
            mismatches.append(key)
        replay_rows.append(
            {
                "check_name": f"replay_{key}",
                "status": status,
                "detail": rel(outputs[key]),
                "current_sha256": current.get(key, ""),
                "replay_sha256": replay.get(key, ""),
            }
        )
    write_csv(outputs["replay_check"], replay_rows, REPLAY_FIELDS)
    shutil.rmtree(VERIFY_TMP)
    write_workspace_note("verify-replay", "PASS" if not mismatches else "FAIL")
    if mismatches:
        raise AssertionError("replay mismatch: " + "; ".join(mismatches))
    print("verify-replay: PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "generate":
        generate()
    elif args.command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
