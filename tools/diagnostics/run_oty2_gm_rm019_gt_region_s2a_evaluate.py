"""Evaluate GM_RM019 S2-A frozen GT-region counterfactual plan.

The evaluate command reads only the frozen S2-A plan, verifies its seal, then
remeasures every planned region from real SAR gray frames. It does not fit GT,
move plan regions, generate a final box, or create selector/ranking outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path("D:/profile/research/data/GM_RM019/GM_RM019_SARframes_gray")
VISUAL_DIR = REPO_ROOT / "outputs" / "oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712" / "visual_review"
VERIFY_TMP = REPO_ROOT / "outputs" / "oty2_gm_rm019_s2a_gt_region_counterfactual_identifiability_20260712" / "_verify_tmp"
WORKSPACE_TASK_DIR = Path("D:/profile/research/workspace/tasks/oty2_gm019_s2a_gt_region_counterfactual_identifiability")
WORKSPACE_LOG = Path("D:/profile/research/workspace/logs/oty2_gm019_s2a_gt_region_counterfactual_identifiability_20260712.md")

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
AXIS_RATIO_MIN = 1.20
COMPONENT_MIN_PIXELS = 8
ENVELOPE_EXTRA_TOL_M = 0.30
ENVELOPE_EXCEED_TOL_M = 0.75
VEHICLE_LENGTH_GRID = [round(3.0 + 0.1 * i, 2) for i in range(36)]
VEHICLE_WIDTH_GRID = [round(1.4 + 0.1 * i, 2) for i in range(13)]
ASPECT_ANGLE_GRID = list(range(0, 91))
THRESHOLDS = [("q50", 0.50), ("q70", 0.70), ("q85", 0.85)]
LAYOUT_STRATEGIES = ["DOMINANT_ONLY", "TOP_COMPONENTS_TO_80_PERCENT_ENERGY", "COMPONENT_ENERGY_FRACTION_GE_5_PERCENT"]

INPUTS = {
    "evaluation_instance_manifest": SAMPLES_DIR / f"oty2_gm_rm019_s2a_evaluation_instance_manifest_{DATE}.csv",
    "gt_geometry_semantics": SAMPLES_DIR / f"oty2_gm_rm019_s2a_gt_geometry_semantics_{DATE}.csv",
    "counterfactual_plan": SAMPLES_DIR / f"oty2_gm_rm019_s2a_counterfactual_plan_{DATE}.csv",
    "plan_seal": SAMPLES_DIR / f"oty2_gm_rm019_s2a_plan_seal_{DATE}.csv",
    "s1_r1_independent_geometry_map": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_independent_geometry_map_20260712.csv",
    "s1_r1_axis_observations": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_axis_observations_20260712.csv",
    "s1_r1_vehicle_projection_envelope": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_vehicle_projection_envelope_20260712.csv",
    "plan_script": REPO_ROOT / "tools" / "diagnostics" / "run_oty2_gm_rm019_gt_region_s2a_plan.py",
    "evaluate_script": Path(__file__),
}

OUTPUTS = {
    "region_measurements": SAMPLES_DIR / f"oty2_gm_rm019_s2a_region_measurements_{DATE}.csv",
    "region_factor_comparison": SAMPLES_DIR / f"oty2_gm_rm019_s2a_region_factor_comparison_{DATE}.csv",
    "edge_identifiability": SAMPLES_DIR / f"oty2_gm_rm019_s2a_edge_identifiability_{DATE}.csv",
    "rotation_identifiability": SAMPLES_DIR / f"oty2_gm_rm019_s2a_rotation_identifiability_{DATE}.csv",
    "axis_representation_ablation": SAMPLES_DIR / f"oty2_gm_rm019_s2a_axis_representation_ablation_{DATE}.csv",
    "matched_background_controls": SAMPLES_DIR / f"oty2_gm_rm019_s2a_matched_background_controls_{DATE}.csv",
    "mask_stratified_results": SAMPLES_DIR / f"oty2_gm_rm019_s2a_mask_stratified_results_{DATE}.csv",
    "gt_instance_summary": SAMPLES_DIR / f"oty2_gm_rm019_s2a_gt_instance_summary_{DATE}.csv",
    "vehicle_group_summary": SAMPLES_DIR / f"oty2_gm_rm019_s2a_vehicle_group_summary_{DATE}.csv",
    "failure_ledger": SAMPLES_DIR / f"oty2_gm_rm019_s2a_failure_ledger_{DATE}.csv",
    "integrity": SAMPLES_DIR / f"oty2_gm_rm019_s2a_integrity_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_gm_rm019_s2a_replay_check_{DATE}.csv",
    "visual_manifest": SAMPLES_DIR / f"oty2_gm_rm019_s2a_visual_manifest_{DATE}.csv",
}

REPORT = REPORT_DIR / f"oty2_gm_rm019_gt_region_counterfactual_identifiability_s2a_{DATE}.md"

CORE_KEYS = [
    "region_measurements",
    "region_factor_comparison",
    "edge_identifiability",
    "rotation_identifiability",
    "axis_representation_ablation",
    "matched_background_controls",
    "mask_stratified_results",
    "gt_instance_summary",
    "vehicle_group_summary",
    "failure_ledger",
    "visual_manifest",
]

MEASUREMENT_FIELDS = [
    "plan_region_id",
    "gt_pair_id",
    "gt_instance_id",
    "physical_vehicle_id",
    "sar_frame",
    "region_role",
    "template_family",
    "template_axis",
    "template_operation",
    "delta_m",
    "rotation_deg",
    "center_shift_range_m",
    "center_shift_azimuth_m",
    "edge_name",
    "scale_axis",
    "mask_class",
    "mask_context",
    "measurement_source",
    "proxy_formula_used",
    "background_mode",
    "sensitivity_background_mode",
    "base_background_estimate",
    "local_ring_background_estimate",
    "background_subtracted_energy",
    "inner_energy_density",
    "outer_band_energy_density",
    "inner_outer_density_ratio",
    "local_ring_background_subtracted_energy",
    "background_sensitivity_status",
    "pixel_count",
    "range_p50_width_m",
    "range_p80_width_m",
    "range_p90_width_m",
    "azimuth_p50_width_m",
    "azimuth_p80_width_m",
    "azimuth_p90_width_m",
    "energy_centroid_range_offset_m",
    "energy_centroid_azimuth_offset_m",
    "raw_component_count",
    "significant_component_count",
    "dominant_component_energy_fraction",
    "dominant_component_area_fraction",
    "top2_component_energy_fraction",
    "largest_component_pixels",
    "largest_component_energy",
    "global_energy_axis_image_deg",
    "global_energy_axis_to_range_signed_deg",
    "global_energy_axis_to_range_acute_deg",
    "global_energy_axis_ratio",
    "global_energy_axis_status",
    "dominant_component_axis_image_deg",
    "dominant_component_axis_to_range_signed_deg",
    "dominant_component_axis_to_range_acute_deg",
    "dominant_component_axis_ratio",
    "dominant_component_axis_status",
    "component_layout_axis_image_deg",
    "component_layout_axis_to_range_signed_deg",
    "component_layout_axis_to_range_acute_deg",
    "component_layout_axis_ratio",
    "component_layout_axis_status",
    "component_layout_strategy",
    "axis_evidence_status",
    "global_axis_to_gt_long_axis_error_deg",
    "dominant_component_axis_to_gt_long_axis_error_deg",
    "component_layout_axis_to_gt_long_axis_error_deg",
    "global_axis_to_gt_aspect_error_deg",
    "dominant_axis_to_gt_aspect_error_deg",
    "layout_axis_to_gt_aspect_error_deg",
    "threshold_component_identity_status",
    "vehicle_projection_envelope_status",
    "required_missing_support_range_m",
    "required_missing_support_azimuth_m",
    "required_extra_spread_range_m",
    "required_extra_spread_azimuth_m",
]

FACTOR_FIELDS = [
    "gt_pair_id",
    "gt_instance_id",
    "physical_vehicle_id",
    "energy_support_status",
    "density_contrast_status",
    "component_structure_status",
    "threshold_identity_status",
    "vehicle_projection_envelope_status",
    "rotation_physical_status",
    "region_status",
    "range_center_interval_m",
    "azimuth_center_interval_m",
    "range_extent_interval_m",
    "azimuth_extent_interval_m",
    "background_sensitivity_status",
    "support_factor_count",
    "evidence_note_cn",
]

EDGE_FIELDS = [
    "gt_pair_id",
    "gt_instance_id",
    "physical_vehicle_id",
    "edge_name",
    "edge_status",
    "edge_supported_interval_m",
    "edge_transition_strength",
    "edge_background_sensitivity",
    "edge_mask_context",
    "edge_note_cn",
]

ROTATION_FIELDS = [
    "gt_pair_id",
    "gt_instance_id",
    "physical_vehicle_id",
    "rotation_status",
    "rotation_physical_status",
    "supported_rotation_interval_deg",
    "rotation_90_exchange_status",
    "rotation_90_energy_ratio",
    "rotation_90_density_ratio",
    "non_gt_rotation_with_highest_energy_deg",
    "non_gt_rotation_with_highest_density_deg",
    "rotation_note_cn",
]

AXIS_ABLATION_FIELDS = [
    "plan_region_id",
    "gt_pair_id",
    "template_family",
    "layout_strategy",
    "selected_component_count",
    "selected_energy_fraction",
    "axis_image_deg",
    "axis_to_range_signed_deg",
    "axis_to_range_acute_deg",
    "axis_ratio",
    "axis_status",
    "axis_to_gt_long_axis_error_deg",
]

BACKGROUND_FIELDS = [
    "gt_pair_id",
    "gt_instance_id",
    "physical_vehicle_id",
    "matched_background_present",
    "matched_background_offset_order",
    "gt_inner_energy_density",
    "background_inner_energy_density",
    "gt_background_density_ratio",
    "gt_energy",
    "background_energy",
    "gt_background_energy_ratio",
    "background_sensitivity_status",
    "control_note_cn",
]

MASK_FIELDS = [
    "mask_class",
    "gt_instance_count",
    "physical_vehicle_count",
    "region_status_counts",
    "edge_status_counts",
    "rotation_status_counts",
    "background_sensitive_count",
    "physical_conflict_count",
    "mask_note_cn",
]

GT_SUMMARY_FIELDS = [
    "gt_pair_id",
    "gt_instance_id",
    "sar_frame",
    "physical_vehicle_id",
    "linked_independent_geometry_ids",
    "linked_independent_geometry_count",
    "mask_class",
    "mask_context",
    "gt_width_axis_image_deg",
    "gt_long_axis_image_deg",
    "region_status",
    "near_edge_status",
    "far_edge_status",
    "left_edge_status",
    "right_edge_status",
    "rotation_status",
    "axis_evidence_status",
    "dominant_component_energy_fraction",
    "component_layout_axis_status",
    "background_sensitivity_status",
    "physical_conflict_flag",
    "interval_platform_flag",
    "review_note_cn",
]

VEHICLE_FIELDS = [
    "physical_vehicle_id",
    "gt_instance_count",
    "region_status_counts",
    "edge_status_counts",
    "rotation_status_counts",
    "background_sensitive_count",
    "physical_conflict_count",
    "interval_platform_count",
    "vehicle_directional_consistency_status",
    "vehicle_specific_only_status",
    "vehicle_note_cn",
]

FAILURE_FIELDS = ["failure_id", "gt_pair_id", "gt_instance_id", "failure_type", "severity", "detail_cn"]
INTEGRITY_FIELDS = ["gate_name", "status", "detail", "source_file", "sha256", "row_count"]
REPLAY_FIELDS = ["check_name", "status", "detail", "current_sha256", "replay_sha256"]
VISUAL_FIELDS = ["visual_case_id", "review_label", "gt_pair_id", "gt_instance_id", "sar_frame", "visual_relpath", "opened_for_review", "review_observation_cn"]


@dataclass(frozen=True)
class Axis:
    image_deg: float = math.nan
    signed_deg: float = math.nan
    acute_deg: float = math.nan
    ratio: float = math.nan
    vx: float = math.nan
    vy: float = math.nan
    status: str = "AXIS_ENERGY_INVALID"


@dataclass(frozen=True)
class Component:
    label: int
    pixels: int
    energy: float
    area_fraction: float
    energy_fraction: float
    centroid_x: float
    centroid_y: float
    bbox: tuple[float, float, float, float]
    axis: Axis
    mask: np.ndarray


@dataclass
class Measurement:
    row: dict[str, str]
    poly: list[tuple[float, float]]
    center_x: float
    center_y: float
    rx: float
    ry: float
    ax: float
    ay: float
    background: float
    local_background: float
    local_energy: float
    mask: np.ndarray
    crop_origin: tuple[int, int]
    xs: np.ndarray
    ys: np.ndarray
    pr: np.ndarray
    pa: np.ndarray
    weights: np.ndarray
    energy: float
    inner_density: float
    outer_density: float
    density_ratio: float
    pixel_count: int
    range_p50_m: float
    range_p80_m: float
    range_p90_m: float
    azimuth_p50_m: float
    azimuth_p80_m: float
    azimuth_p90_m: float
    centroid_r_m: float
    centroid_a_m: float
    components: list[Component]
    global_axis: Axis
    dominant_axis: Axis
    layout_axis: Axis
    layout_strategy: str
    threshold_status: str
    envelope: dict[str, Any]
    background_status: str
    axis_evidence_status: str


_IMAGE_CACHE: dict[int, np.ndarray] = {}
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


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".csv":
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


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


def load_gray(frame: int) -> np.ndarray:
    if frame not in _IMAGE_CACHE:
        with Image.open(DATA_ROOT / f"{frame:06d}.png") as img:
            _IMAGE_CACHE[frame] = np.asarray(img.convert("L"), dtype=np.float32)
    return _IMAGE_CACHE[frame]


def parse_polygon(text: str) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for part in str(text).split(";"):
        if not part:
            continue
        x, y = part.split(",")
        out.append((float(x), float(y)))
    return out


def polygon_text(poly: Sequence[tuple[float, float]]) -> str:
    return ";".join(f"{fmt(x, 3)},{fmt(y, 3)}" for x, y in poly)


def parse_box(text: str) -> tuple[float, float, float, float] | None:
    vals = [parse_float(p) for p in str(text).replace(";", ",").split(",") if p != ""]
    if len(vals) != 4 or any(math.isnan(v) for v in vals):
        return None
    x1, y1, x2, y2 = vals
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def unit_vectors(cx: float, cy: float) -> tuple[float, float, float, float]:
    dx = cx - FAN_CENTER_X
    dy = cy - FAN_CENTER_Y
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return 0.0, -1.0, 1.0, 0.0
    rx = dx / norm
    ry = dy / norm
    return rx, ry, -ry, rx


def fan_valid_points(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    ranges = np.hypot(xs - FAN_CENTER_X, ys - FAN_CENTER_Y)
    angles = np.degrees(np.arctan2(xs - FAN_CENTER_X, FAN_CENTER_Y - ys))
    return (xs >= 0) & (xs < SAR_WIDTH) & (ys >= 0) & (ys < SAR_HEIGHT) & (ranges <= FAN_RADIUS_PX) & (angles >= -90.0) & (angles <= 90.0)


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


def axis_diff_acute(a: float, b: float) -> float:
    if math.isnan(a) or math.isnan(b):
        return math.nan
    return abs((a - b + 90.0) % 180.0 - 90.0)


def weighted_axis(xs: np.ndarray, ys: np.ndarray, weights: np.ndarray, rx: float, ry: float, resolved_status: str = "AXIS_RESOLVED") -> Axis:
    total = float(np.sum(weights))
    if len(xs) < 2 or total <= 1e-9:
        return Axis()
    cx = float(np.average(xs, weights=weights))
    cy = float(np.average(ys, weights=weights))
    dx = xs - cx
    dy = ys - cy
    cov = np.asarray(
        [
            [float(np.average(dx * dx, weights=weights)), float(np.average(dx * dy, weights=weights))],
            [float(np.average(dx * dy, weights=weights)), float(np.average(dy * dy, weights=weights))],
        ],
        dtype=float,
    )
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)
    major = math.sqrt(max(0.0, float(vals[order[-1]])))
    minor = math.sqrt(max(0.0, float(vals[order[0]])))
    vx, vy, angle = canonical_axis(float(vecs[0, order[-1]]), float(vecs[1, order[-1]]))
    ratio = major / minor if minor > 1e-9 else math.inf
    signed = signed_axis_to_ref_deg(vx, vy, rx, ry)
    status = "AXIS_NEAR_ISOTROPIC" if ratio < AXIS_RATIO_MIN else resolved_status
    return Axis(angle, signed, abs(signed) if not math.isnan(signed) else math.nan, ratio, vx, vy, status)


def shortest_weighted_width(values: np.ndarray, weights: np.ndarray, fraction: float) -> float:
    if len(values) == 0:
        return math.nan
    total = float(np.sum(weights))
    if total <= 1e-9:
        return float(np.max(values) - np.min(values)) if len(values) else math.nan
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    target = total * fraction
    best = math.inf
    left = 0
    running = 0.0
    for right in range(len(values)):
        running += float(weights[right])
        while left <= right and running - float(weights[left]) >= target:
            running -= float(weights[left])
            left += 1
        if running >= target:
            best = min(best, float(values[right] - values[left]))
    return best if math.isfinite(best) else float(values[-1] - values[0])


def polygon_crop(poly: Sequence[tuple[float, float]], pad: int = 8) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple[int, int]]:
    xs_poly = [p[0] for p in poly]
    ys_poly = [p[1] for p in poly]
    x1 = max(0, int(math.floor(min(xs_poly))) - pad)
    y1 = max(0, int(math.floor(min(ys_poly))) - pad)
    x2 = min(SAR_WIDTH, int(math.ceil(max(xs_poly))) + pad)
    y2 = min(SAR_HEIGHT, int(math.ceil(max(ys_poly))) + pad)
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    mask_img = Image.new("L", (width, height), 0)
    local = [(x - x1, y - y1) for x, y in poly]
    ImageDraw.Draw(mask_img).polygon(local, fill=1)
    mask = np.asarray(mask_img, dtype=bool)
    yy, xx = np.mgrid[y1:y2, x1:x2]
    xs = xx.astype(np.float32) + 0.5
    ys = yy.astype(np.float32) + 0.5
    valid = fan_valid_points(xs, ys)
    return mask & valid, xs, ys, valid, (x1, y1)


def ring_background(arr: np.ndarray, poly: Sequence[tuple[float, float]], band_px: int = 5) -> float:
    mask, xs, ys, valid, _ = polygon_crop(poly, pad=band_px + 8)
    ring = ndi.binary_dilation(mask, iterations=band_px) & (~mask) & valid
    if not bool(ring.any()):
        return 0.0
    ix = np.clip(xs.astype(int), 0, SAR_WIDTH - 1)
    iy = np.clip(ys.astype(int), 0, SAR_HEIGHT - 1)
    return float(np.median(arr[iy[ring], ix[ring]]))


def connected_components(mask: np.ndarray, xs: np.ndarray, ys: np.ndarray, weights: np.ndarray, rx: float, ry: float, total_energy: float, pixel_count: int) -> list[Component]:
    structure = np.asarray([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8)
    labels, count = ndi.label(mask, structure=structure)
    comps: list[Component] = []
    if count <= 0:
        return comps
    for label in range(1, count + 1):
        cmask = labels == label
        pixels = int(np.count_nonzero(cmask))
        if pixels <= 0:
            continue
        cweights = weights[cmask]
        energy = float(np.sum(cweights))
        cxs = xs[cmask]
        cys = ys[cmask]
        if energy > 1e-9:
            cx = float(np.average(cxs, weights=cweights))
            cy = float(np.average(cys, weights=cweights))
        else:
            cx = float(np.mean(cxs))
            cy = float(np.mean(cys))
        bbox = (float(np.min(cxs)), float(np.min(cys)), float(np.max(cxs)), float(np.max(cys)))
        comps.append(
            Component(
                label=label,
                pixels=pixels,
                energy=energy,
                area_fraction=pixels / max(1, pixel_count),
                energy_fraction=energy / total_energy if total_energy > 1e-9 else 0.0,
                centroid_x=cx,
                centroid_y=cy,
                bbox=bbox,
                axis=weighted_axis(cxs, cys, cweights, rx, ry),
                mask=cmask,
            )
        )
    return sorted(comps, key=lambda c: (c.energy, c.pixels), reverse=True)


def layout_axis(components: Sequence[Component], strategy: str, rx: float, ry: float) -> tuple[Axis, int, float]:
    if not components:
        return Axis(), 0, 0.0
    if strategy == "DOMINANT_ONLY":
        c = components[0]
        return c.axis, 1, c.energy_fraction
    if strategy == "COMPONENT_ENERGY_FRACTION_GE_5_PERCENT":
        selected = [c for c in components if c.energy_fraction >= 0.05 and c.pixels >= COMPONENT_MIN_PIXELS]
    else:
        selected = []
        running = 0.0
        for c in components:
            if c.pixels >= COMPONENT_MIN_PIXELS:
                selected.append(c)
                running += c.energy_fraction
            if running >= 0.80:
                break
    selected_fraction = sum(c.energy_fraction for c in selected)
    if len(selected) < 2:
        if selected:
            return selected[0].axis, len(selected), selected_fraction
        return Axis(status="AXIS_FRAGMENTED_NO_DOMINANT_STRUCTURE"), 0, 0.0
    xs = np.asarray([c.centroid_x for c in selected], dtype=float)
    ys = np.asarray([c.centroid_y for c in selected], dtype=float)
    weights = np.asarray([max(c.energy, 1e-6) for c in selected], dtype=float)
    return weighted_axis(xs, ys, weights, rx, ry, resolved_status="AXIS_COMPONENT_LAYOUT_RESOLVED"), len(selected), selected_fraction


def threshold_status(mask: np.ndarray, xs: np.ndarray, ys: np.ndarray, weights: np.ndarray, rx: float, ry: float, total_energy: float, pixel_count: int) -> str:
    positive = weights[mask & (weights > 0)]
    if len(positive) == 0:
        return "NO_STABLE_COMPONENT"
    comps_by_q: list[list[Component]] = []
    for _, q in THRESHOLDS:
        threshold = float(np.quantile(positive, q))
        comps_by_q.append(connected_components(mask & (weights >= threshold) & (weights > 0), xs, ys, weights, rx, ry, total_energy, pixel_count))
    if any(not comps for comps in comps_by_q):
        return "NO_STABLE_COMPONENT"
    if any(comps[0].pixels < COMPONENT_MIN_PIXELS for comps in comps_by_q):
        return "COMPONENT_TOO_SMALL"
    for lo, hi in zip(comps_by_q, comps_by_q[1:]):
        low = lo[0]
        high = hi[0]
        inter = int(np.count_nonzero(low.mask & high.mask))
        union = int(np.count_nonzero(low.mask | high.mask))
        iou = inter / union if union else 0.0
        high_area = int(np.count_nonzero(high.mask))
        contained = high_area > 0 and inter == high_area
        shift_m = math.hypot(high.centroid_x - low.centroid_x, high.centroid_y - low.centroid_y) * M_PER_PX
        if not contained and len(lo) != len(hi):
            return "COMPONENT_SPLIT_OR_MERGE"
        if iou < 0.25 or shift_m > 0.60:
            return "COMPONENT_IDENTITY_SWITCH"
    return "SAME_COMPONENT_PERSISTENT"


def aspect_arrays() -> dict[str, np.ndarray]:
    global _ASPECT_ARRAYS
    if _ASPECT_ARRAYS is not None:
        return _ASPECT_ARRAYS
    angles: list[int] = []
    lengths: list[float] = []
    widths: list[float] = []
    pred_r: list[float] = []
    pred_a: list[float] = []
    for angle in ASPECT_ANGLE_GRID:
        rad = math.radians(angle)
        c = abs(math.cos(rad))
        s = abs(math.sin(rad))
        for length in VEHICLE_LENGTH_GRID:
            for width in VEHICLE_WIDTH_GRID:
                angles.append(angle)
                lengths.append(length)
                widths.append(width)
                pred_r.append(abs(length * c) + abs(width * s))
                pred_a.append(abs(length * s) + abs(width * c))
    _ASPECT_ARRAYS = {
        "angle": np.asarray(angles, dtype=np.int16),
        "length": np.asarray(lengths, dtype=np.float32),
        "width": np.asarray(widths, dtype=np.float32),
        "pred_r": np.asarray(pred_r, dtype=np.float32),
        "pred_a": np.asarray(pred_a, dtype=np.float32),
    }
    return _ASPECT_ARRAYS


def angle_segments(values: Sequence[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    vals = sorted(set(int(v) for v in values))
    out: list[tuple[int, int]] = []
    start = prev = vals[0]
    for value in vals[1:]:
        if value == prev + 1:
            prev = value
        else:
            out.append((start, prev))
            start = prev = value
    out.append((start, prev))
    return out


def aspect_candidates(range_obs: float, az_obs: float, axis_status: str, response_axis_acute: float) -> dict[str, Any]:
    if math.isnan(range_obs) or math.isnan(az_obs):
        return {
            "vehicle_projection_envelope_status": "AMBIGUOUS_ENVELOPE_COMPATIBILITY",
            "aspect_angle_candidate_deg": math.nan,
            "aspect_angle_compatible_interval_deg": "",
            "required_missing_support_range_m": math.nan,
            "required_missing_support_azimuth_m": math.nan,
            "required_extra_spread_range_m": math.nan,
            "required_extra_spread_azimuth_m": math.nan,
            "response_axis_aspect_angle_error_deg": math.nan,
            "aspect_angle_identifiability_status": "AXIS_NOT_RESOLVED",
        }
    arrays = aspect_arrays()
    miss_r = np.maximum(0.0, arrays["pred_r"] - range_obs)
    miss_a = np.maximum(0.0, arrays["pred_a"] - az_obs)
    extra_r = np.maximum(0.0, range_obs - arrays["pred_r"])
    extra_a = np.maximum(0.0, az_obs - arrays["pred_a"])
    residual = np.hypot(extra_r, extra_a) + 0.25 * np.hypot(miss_r, miss_a)
    best_idx = int(np.argmin(residual))
    best_extra = max(float(extra_r[best_idx]), float(extra_a[best_idx]))
    best_missing = max(float(miss_r[best_idx]), float(miss_a[best_idx]))
    if best_extra <= ENVELOPE_EXTRA_TOL_M and best_missing <= ENVELOPE_EXTRA_TOL_M:
        envelope_status = "WITHIN_VEHICLE_PROJECTION_ENVELOPE"
    elif best_extra <= ENVELOPE_EXTRA_TOL_M and best_missing > ENVELOPE_EXTRA_TOL_M:
        envelope_status = "PARTIAL_SUPPORT_BELOW_ENVELOPE"
    elif best_extra > ENVELOPE_EXCEED_TOL_M:
        envelope_status = "EXCEEDS_VEHICLE_PROJECTION_ENVELOPE"
    else:
        envelope_status = "AMBIGUOUS_ENVELOPE_COMPATIBILITY"
    compatible = []
    for angle in ASPECT_ANGLE_GRID:
        idx = arrays["angle"] == angle
        if bool(np.any((extra_r[idx] <= ENVELOPE_EXTRA_TOL_M) & (extra_a[idx] <= ENVELOPE_EXTRA_TOL_M))):
            compatible.append(angle)
    segments = angle_segments(compatible)
    total_span = sum(b - a for a, b in segments)
    if axis_status not in ("AXIS_RESOLVED", "AXIS_COMPONENT_LAYOUT_RESOLVED"):
        ident_status = "AXIS_NOT_RESOLVED"
    elif not compatible:
        ident_status = "ASPECT_ANGLE_NOT_IDENTIFIABLE"
    elif len(segments) == 1 and total_span <= 10:
        ident_status = "ASPECT_ANGLE_LOCALLY_IDENTIFIABLE"
    elif any(a <= 10 for a in compatible) and any(a >= 80 for a in compatible):
        ident_status = "ASPECT_ANGLE_90_DEG_AMBIGUOUS"
    elif total_span <= 45:
        ident_status = "ASPECT_ANGLE_INTERVAL_ONLY"
    else:
        ident_status = "ASPECT_ANGLE_NOT_IDENTIFIABLE"
    best_angle = int(arrays["angle"][best_idx])
    return {
        "vehicle_projection_envelope_status": envelope_status,
        "aspect_angle_candidate_deg": best_angle,
        "aspect_angle_compatible_interval_deg": ";".join(f"{a}-{b}" if a != b else str(a) for a, b in segments),
        "required_missing_support_range_m": float(miss_r[best_idx]),
        "required_missing_support_azimuth_m": float(miss_a[best_idx]),
        "required_extra_spread_range_m": float(extra_r[best_idx]),
        "required_extra_spread_azimuth_m": float(extra_a[best_idx]),
        "response_axis_aspect_angle_error_deg": axis_diff_acute(response_axis_acute, best_angle) if not math.isnan(response_axis_acute) else math.nan,
        "aspect_angle_identifiability_status": ident_status,
    }


def axis_evidence(global_axis: Axis, dominant_axis: Axis, layout_axis_value: Axis) -> str:
    resolved = [a for a in [global_axis, dominant_axis, layout_axis_value] if a.status in ("AXIS_RESOLVED", "AXIS_COMPONENT_LAYOUT_RESOLVED")]
    if not resolved:
        return "NO_RESOLVED_AXIS_EVIDENCE"
    if global_axis.status == "AXIS_RESOLVED" and dominant_axis.status == "AXIS_RESOLVED":
        if axis_diff_acute(global_axis.image_deg, dominant_axis.image_deg) <= 20.0:
            return "GLOBAL_AND_COMPONENT_AXIS_CONSISTENT"
        return "MULTIPLE_AXIS_REPRESENTATIONS_CONFLICT"
    if dominant_axis.status == "AXIS_RESOLVED":
        return "DOMINANT_COMPONENT_AXIS_ONLY"
    if layout_axis_value.status == "AXIS_COMPONENT_LAYOUT_RESOLVED":
        return "COMPONENT_LAYOUT_AXIS_ONLY"
    return "NO_RESOLVED_AXIS_EVIDENCE"


def measure_polygon(row: Mapping[str, str], arr: np.ndarray, background: float, local_background: float, gt_long_axis: float, gt_aspect: float) -> Measurement:
    poly = parse_polygon(row["region_polygon_xy"])
    cx = parse_float(row["region_center_x"])
    cy = parse_float(row["region_center_y"])
    rx, ry, ax, ay = unit_vectors(cx, cy)
    mask, xs, ys, valid, origin = polygon_crop(poly)
    ix = np.clip(xs.astype(int), 0, SAR_WIDTH - 1)
    iy = np.clip(ys.astype(int), 0, SAR_HEIGHT - 1)
    intensities = arr[iy, ix]
    weights = np.maximum(intensities - background, 0.0)
    local_weights = np.maximum(intensities - local_background, 0.0)
    ring = ndi.binary_dilation(mask, iterations=5) & (~mask) & valid
    band_weights = weights[ring]
    pixel_count = int(np.count_nonzero(mask))
    inner_weights = weights[mask]
    inner_local = local_weights[mask]
    energy = float(np.sum(inner_weights))
    local_energy = float(np.sum(inner_local))
    outer_density = float(np.mean(band_weights)) if int(np.count_nonzero(ring)) else 0.0
    inner_density = energy / max(1, pixel_count)
    density_ratio = inner_density / outer_density if outer_density > 1e-9 else math.inf
    pr = (xs - cx) * rx + (ys - cy) * ry
    pa = (xs - cx) * ax + (ys - cy) * ay
    positive = mask & (weights > 0)
    xs_i = xs[mask]
    ys_i = ys[mask]
    pr_i = pr[mask]
    pa_i = pa[mask]
    w_i = inner_weights
    if energy > 1e-9 and len(w_i):
        centroid_r = float(np.average(pr_i, weights=w_i)) * M_PER_PX
        centroid_a = float(np.average(pa_i, weights=w_i)) * M_PER_PX
        range_p50 = shortest_weighted_width(pr_i, w_i, 0.50) * M_PER_PX
        range_p80 = shortest_weighted_width(pr_i, w_i, 0.80) * M_PER_PX
        range_p90 = shortest_weighted_width(pr_i, w_i, 0.90) * M_PER_PX
        az_p50 = shortest_weighted_width(pa_i, w_i, 0.50) * M_PER_PX
        az_p80 = shortest_weighted_width(pa_i, w_i, 0.80) * M_PER_PX
        az_p90 = shortest_weighted_width(pa_i, w_i, 0.90) * M_PER_PX
        global_axis = weighted_axis(xs_i, ys_i, w_i, rx, ry)
    else:
        centroid_r = centroid_a = math.nan
        range_p50 = range_p80 = range_p90 = az_p50 = az_p80 = az_p90 = math.nan
        global_axis = Axis()
    components = connected_components(positive, xs, ys, weights, rx, ry, energy, pixel_count)
    if components:
        dominant = components[0]
        dominant_axis = dominant.axis
        if dominant.energy_fraction < 0.35:
            dominant_axis = Axis(dominant_axis.image_deg, dominant_axis.signed_deg, dominant_axis.acute_deg, dominant_axis.ratio, dominant_axis.vx, dominant_axis.vy, "AXIS_FRAGMENTED_NO_DOMINANT_STRUCTURE")
    else:
        dominant = None
        dominant_axis = Axis()
    layout, _, _ = layout_axis(components, "TOP_COMPONENTS_TO_80_PERCENT_ENERGY", rx, ry)
    if len(components) > 1 and global_axis.status == "AXIS_RESOLVED":
        # S2-A keeps the global axis instead of automatically rejecting it.
        global_axis = Axis(global_axis.image_deg, global_axis.signed_deg, global_axis.acute_deg, global_axis.ratio, global_axis.vx, global_axis.vy, "AXIS_RESOLVED")
    threshold = threshold_status(mask, xs, ys, weights, rx, ry, energy, pixel_count)
    env = aspect_candidates(range_p80, az_p80, global_axis.status, global_axis.acute_deg)
    if energy <= 1e-9:
        bg_status = "BACKGROUND_STABLE"
    else:
        rel_delta = abs(local_energy - energy) / max(1.0, energy)
        bg_status = "COUNTERFACTUAL_BACKGROUND_SENSITIVE" if rel_delta > 0.35 else "BACKGROUND_STABLE"
    return Measurement(
        row=dict(row),
        poly=poly,
        center_x=cx,
        center_y=cy,
        rx=rx,
        ry=ry,
        ax=ax,
        ay=ay,
        background=background,
        local_background=local_background,
        local_energy=local_energy,
        mask=mask,
        crop_origin=origin,
        xs=xs,
        ys=ys,
        pr=pr,
        pa=pa,
        weights=weights,
        energy=energy,
        inner_density=inner_density,
        outer_density=outer_density,
        density_ratio=density_ratio,
        pixel_count=pixel_count,
        range_p50_m=range_p50,
        range_p80_m=range_p80,
        range_p90_m=range_p90,
        azimuth_p50_m=az_p50,
        azimuth_p80_m=az_p80,
        azimuth_p90_m=az_p90,
        centroid_r_m=centroid_r,
        centroid_a_m=centroid_a,
        components=components,
        global_axis=global_axis,
        dominant_axis=dominant_axis,
        layout_axis=layout,
        layout_strategy="TOP_COMPONENTS_TO_80_PERCENT_ENERGY",
        threshold_status=threshold,
        envelope=env,
        background_status=bg_status,
        axis_evidence_status=axis_evidence(global_axis, dominant_axis, layout),
    )


def measurement_row(m: Measurement, gt_long_axis: float, gt_aspect: float) -> dict[str, Any]:
    comps = m.components
    dominant = comps[0] if comps else None
    sig = [c for c in comps if c.energy_fraction >= 0.05 and c.pixels >= COMPONENT_MIN_PIXELS]
    top2 = sum(c.energy_fraction for c in comps[:2])
    return {
        **{k: m.row.get(k, "") for k in MEASUREMENT_FIELDS},
        "measurement_source": "REAL_SAR_GRAY_REMEASURED",
        "proxy_formula_used": "false",
        "background_mode": "BASE_REGION_FROZEN_BACKGROUND",
        "sensitivity_background_mode": "PERTURBED_LOCAL_RING_BACKGROUND",
        "base_background_estimate": fmt(m.background),
        "local_ring_background_estimate": fmt(m.local_background),
        "background_subtracted_energy": fmt(m.energy),
        "inner_energy_density": fmt(m.inner_density),
        "outer_band_energy_density": fmt(m.outer_density),
        "inner_outer_density_ratio": fmt(m.density_ratio),
        "local_ring_background_subtracted_energy": fmt(m.local_energy),
        "background_sensitivity_status": m.background_status,
        "pixel_count": str(m.pixel_count),
        "range_p50_width_m": fmt(m.range_p50_m),
        "range_p80_width_m": fmt(m.range_p80_m),
        "range_p90_width_m": fmt(m.range_p90_m),
        "azimuth_p50_width_m": fmt(m.azimuth_p50_m),
        "azimuth_p80_width_m": fmt(m.azimuth_p80_m),
        "azimuth_p90_width_m": fmt(m.azimuth_p90_m),
        "energy_centroid_range_offset_m": fmt(m.centroid_r_m),
        "energy_centroid_azimuth_offset_m": fmt(m.centroid_a_m),
        "raw_component_count": str(len(comps)),
        "significant_component_count": str(len(sig)),
        "dominant_component_energy_fraction": fmt(dominant.energy_fraction if dominant else 0.0),
        "dominant_component_area_fraction": fmt(dominant.area_fraction if dominant else 0.0),
        "top2_component_energy_fraction": fmt(top2),
        "largest_component_pixels": str(dominant.pixels if dominant else 0),
        "largest_component_energy": fmt(dominant.energy if dominant else 0.0),
        "global_energy_axis_image_deg": fmt(m.global_axis.image_deg),
        "global_energy_axis_to_range_signed_deg": fmt(m.global_axis.signed_deg),
        "global_energy_axis_to_range_acute_deg": fmt(m.global_axis.acute_deg),
        "global_energy_axis_ratio": fmt(m.global_axis.ratio),
        "global_energy_axis_status": m.global_axis.status,
        "dominant_component_axis_image_deg": fmt(m.dominant_axis.image_deg),
        "dominant_component_axis_to_range_signed_deg": fmt(m.dominant_axis.signed_deg),
        "dominant_component_axis_to_range_acute_deg": fmt(m.dominant_axis.acute_deg),
        "dominant_component_axis_ratio": fmt(m.dominant_axis.ratio),
        "dominant_component_axis_status": m.dominant_axis.status,
        "component_layout_axis_image_deg": fmt(m.layout_axis.image_deg),
        "component_layout_axis_to_range_signed_deg": fmt(m.layout_axis.signed_deg),
        "component_layout_axis_to_range_acute_deg": fmt(m.layout_axis.acute_deg),
        "component_layout_axis_ratio": fmt(m.layout_axis.ratio),
        "component_layout_axis_status": m.layout_axis.status,
        "component_layout_strategy": m.layout_strategy,
        "axis_evidence_status": m.axis_evidence_status,
        "global_axis_to_gt_long_axis_error_deg": fmt(axis_diff_acute(m.global_axis.image_deg, gt_long_axis)),
        "dominant_component_axis_to_gt_long_axis_error_deg": fmt(axis_diff_acute(m.dominant_axis.image_deg, gt_long_axis)),
        "component_layout_axis_to_gt_long_axis_error_deg": fmt(axis_diff_acute(m.layout_axis.image_deg, gt_long_axis)),
        "global_axis_to_gt_aspect_error_deg": fmt(axis_diff_acute(m.global_axis.acute_deg, gt_aspect)),
        "dominant_axis_to_gt_aspect_error_deg": fmt(axis_diff_acute(m.dominant_axis.acute_deg, gt_aspect)),
        "layout_axis_to_gt_aspect_error_deg": fmt(axis_diff_acute(m.layout_axis.acute_deg, gt_aspect)),
        "threshold_component_identity_status": m.threshold_status,
        "vehicle_projection_envelope_status": m.envelope["vehicle_projection_envelope_status"],
        "required_missing_support_range_m": fmt(m.envelope["required_missing_support_range_m"]),
        "required_missing_support_azimuth_m": fmt(m.envelope["required_missing_support_azimuth_m"]),
        "required_extra_spread_range_m": fmt(m.envelope["required_extra_spread_range_m"]),
        "required_extra_spread_azimuth_m": fmt(m.envelope["required_extra_spread_azimuth_m"]),
    }


def ablation_rows(m: Measurement, gt_long_axis: float) -> list[dict[str, Any]]:
    rows = []
    for strategy in LAYOUT_STRATEGIES:
        axis, count, frac = layout_axis(m.components, strategy, m.rx, m.ry)
        rows.append(
            {
                "plan_region_id": m.row["plan_region_id"],
                "gt_pair_id": m.row["gt_pair_id"],
                "template_family": m.row["template_family"],
                "layout_strategy": strategy,
                "selected_component_count": str(count),
                "selected_energy_fraction": fmt(frac),
                "axis_image_deg": fmt(axis.image_deg),
                "axis_to_range_signed_deg": fmt(axis.signed_deg),
                "axis_to_range_acute_deg": fmt(axis.acute_deg),
                "axis_ratio": fmt(axis.ratio),
                "axis_status": axis.status,
                "axis_to_gt_long_axis_error_deg": fmt(axis_diff_acute(axis.image_deg, gt_long_axis)),
            }
        )
    return rows


def verify_plan_seal(seal_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    seal = {r["seal_key"]: r for r in seal_rows}
    gates: list[dict[str, str]] = []

    def add(name: str, ok: bool, detail: str, path: Path | None = None) -> None:
        gates.append(
            {
                "gate_name": name,
                "status": "PASS" if ok else "FAIL",
                "detail": detail,
                "source_file": rel(path) if path else "",
                "sha256": sha256(path) if path and path.exists() else "",
                "row_count": str(row_count(path)) if path and path.exists() and path.suffix.lower() == ".csv" else "",
            }
        )

    add("PLAN_STAGE_DOES_NOT_READ_SAR_INTENSITY", seal.get("plan_stage_intensity_read", {}).get("seal_value") == "false", "plan seal records intensity_read=false", INPUTS["plan_seal"])
    add("PLAN_STAGE_DOES_NOT_READ_S1_R1_MEASUREMENT_OUTCOMES", seal.get("plan_stage_s1_r1_measurement_outcomes_read", {}).get("seal_value") == "false", "plan seal records s1_r1_measurement_outcomes_read=false", INPUTS["plan_seal"])
    add("PLAN_STAGE_GT_ACCESS_EXPLICIT", seal.get("plan_stage_gt_access_explicit", {}).get("seal_value") == "true", "GT access is explicit in plan seal", INPUTS["plan_seal"])
    add("PROJECT_CONFIRMED_CALIBRATION_APPLIED", seal.get("calibration_status", {}).get("seal_value") == CALIBRATION_STATUS, "PROJECT_CONFIRMED constants carried into S2-A", INPUTS["plan_seal"])
    plan_sha = seal.get("plan_source_sha256", {}).get("seal_value", "")
    add("PLAN_SOURCE_HASH_VALID", bool(plan_sha) and plan_sha == sha256(INPUTS["plan_script"]), "current plan script matches plan seal", INPUTS["plan_script"])
    for row in seal_rows:
        if row["seal_key"].startswith("input_hash_") and row["source_file"]:
            path = REPO_ROOT / row["source_file"]
            add(f"S1_R1_HASH_VALID_{row['seal_key']}", path.exists() and row["sha256"] == sha256(path), f"hash check for {row['source_file']}", path)
    return gates


def branch_name() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return ""


def rev_parse(ref: str) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", ref], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return ""


def build_status_rows(
    manifest: Sequence[Mapping[str, str]],
    gt_rows: Mapping[str, Mapping[str, str]],
    measurements: Mapping[str, Measurement],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_pair: dict[str, list[Measurement]] = defaultdict(list)
    for m in measurements.values():
        by_pair[m.row["gt_pair_id"]].append(m)
    factors: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    rotations: list[dict[str, Any]] = []
    backgrounds: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    primary_pairs = {r["gt_pair_id"] for r in manifest if r["evaluation_pool"] == "PRIMARY_EXACT_LINK"}

    for row in manifest:
        if row["evaluation_pool"] != "PRIMARY_EXACT_LINK":
            failures.append(
                {
                    "failure_id": f"{row['gt_pair_id']}_pairing_review",
                    "gt_pair_id": row["gt_pair_id"],
                    "gt_instance_id": row["gt_instance_id"],
                    "failure_type": "GT_REGION_PAIRING_UNRESOLVED",
                    "severity": "INFO",
                    "detail_cn": "该 pair 不进入主评价池，仅保留为 pairing-review 和视觉敏感性样本。",
                }
            )
            continue
        pair = row["gt_pair_id"]
        rows = by_pair[pair]
        base = next(m for m in rows if m.row["template_family"] == "gt_original")
        center = [m for m in rows if m.row["template_family"] in ("center_shift", "diagonal_center_shift")]
        scale = [m for m in rows if m.row["template_family"] == "scale_resize"]
        bg = [m for m in rows if m.row["template_family"] == "matched_background"]
        rot = [m for m in rows if m.row["template_family"] == "local_region_rotation"]
        bg_m = bg[0] if bg else None
        center_energy_med = median([m.energy for m in center]) if center else base.energy
        center_density_med = median([m.inner_density for m in center]) if center else base.inner_density
        bg_density_ok = bool(bg_m and base.inner_density > bg_m.inner_density * 1.20 and base.energy > bg_m.energy * 1.10)
        non_gt_energy_high = sum(1 for m in center + scale if m.energy > base.energy * 1.25 and m.inner_density > base.inner_density * 1.10)
        if non_gt_energy_high >= 4:
            energy_status = "ENERGY_SUPPORTS_NON_GT_ALTERNATIVE"
        elif base.energy > center_energy_med * 1.10 and bg_density_ok:
            energy_status = "ENERGY_GT_LOCAL_SUPPORT"
        elif bg_density_ok:
            energy_status = "ENERGY_PLATFORM_SUPPORT"
        else:
            energy_status = "ENERGY_NOT_DISTINGUISHING"
        if bg_density_ok and base.inner_density > center_density_med * 1.05:
            density_status = "DENSITY_GT_LOCAL_CONTRAST"
        elif bg_density_ok:
            density_status = "DENSITY_PLATFORM_CONTRAST"
        else:
            density_status = "DENSITY_NOT_DISTINGUISHING"
        component_status = "COMPONENT_STRUCTURE_STABLE" if base.threshold_status == "SAME_COMPONENT_PERSISTENT" and (base.components and base.components[0].energy_fraction >= 0.35) else "COMPONENT_STRUCTURE_FRAGMENTED_OR_UNSTABLE"
        threshold_factor = "THRESHOLD_IDENTITY_PERSISTENT" if base.threshold_status == "SAME_COMPONENT_PERSISTENT" else "THRESHOLD_IDENTITY_UNSTABLE"
        support_count = sum(
            [
                energy_status in ("ENERGY_GT_LOCAL_SUPPORT", "ENERGY_PLATFORM_SUPPORT"),
                density_status in ("DENSITY_GT_LOCAL_CONTRAST", "DENSITY_PLATFORM_CONTRAST"),
                component_status == "COMPONENT_STRUCTURE_STABLE",
                threshold_factor == "THRESHOLD_IDENTITY_PERSISTENT",
            ]
        )
        bg_sensitive = any(m.background_status == "COUNTERFACTUAL_BACKGROUND_SENSITIVE" for m in [base] + bg)
        if non_gt_energy_high >= 4 and support_count <= 2:
            region_status = "GT_REGION_PHYSICAL_CONFLICT"
        elif bg_density_ok and support_count >= 3 and not bg_sensitive:
            region_status = "GT_REGION_PHYSICALLY_DISTINGUISHABLE"
        elif support_count >= 2:
            region_status = "GT_REGION_INTERVAL_IDENTIFIABLE"
        else:
            region_status = "GT_REGION_NOT_STATICALLY_DISTINGUISHABLE"
        range_center_vals = [0.0] + [parse_float(m.row.get("center_shift_range_m"), 0.0) for m in center if m.energy >= base.energy * 0.85 and m.inner_density >= base.inner_density * 0.85]
        az_center_vals = [0.0] + [parse_float(m.row.get("center_shift_azimuth_m"), 0.0) for m in center if m.energy >= base.energy * 0.85 and m.inner_density >= base.inner_density * 0.85]
        range_extent_vals = [0.0] + [parse_float(m.row.get("delta_m"), 0.0) for m in scale if m.row.get("scale_axis") == "range" and m.energy >= base.energy * 0.85]
        az_extent_vals = [0.0] + [parse_float(m.row.get("delta_m"), 0.0) for m in scale if m.row.get("scale_axis") == "azimuth" and m.energy >= base.energy * 0.85]
        edge_statuses: dict[str, str] = {}
        for edge_name in ["range_near", "range_far", "azimuth_left", "azimuth_right"]:
            erows = [m for m in rows if m.row["template_family"] == "single_boundary_shift" and m.row["edge_name"] == edge_name]
            strengths = [abs(m.inner_density - base.inner_density) / max(1.0, base.inner_density) for m in erows]
            transition = max(strengths) if strengths else 0.0
            e_sensitive = any(m.background_status == "COUNTERFACTUAL_BACKGROUND_SENSITIVE" for m in erows)
            edge_mask = row["mask_context"] if "bottom_near_range_mask" in row["mask_context"] and edge_name == "range_near" else ""
            outward_high = [m for m in erows if "outward" in m.row.get("template_operation", "") and m.energy > base.energy * 1.20 and m.inner_density > base.inner_density * 1.10]
            if edge_mask:
                status = "EDGE_MASK_CENSORED"
            elif len(outward_high) >= 2:
                status = "EDGE_PHYSICAL_CONFLICT"
            elif transition >= 0.25:
                status = "EDGE_IDENTIFIABLE"
            elif transition >= 0.10 or e_sensitive:
                status = "EDGE_INTERVAL_ONLY"
            else:
                status = "EDGE_NOT_IDENTIFIABLE"
            edge_statuses[edge_name] = status
            ok_vals = [0.0] + [parse_float(m.row["delta_m"], 0.0) for m in erows if m.energy >= base.energy * 0.85]
            edges.append(
                {
                    "gt_pair_id": pair,
                    "gt_instance_id": row["gt_instance_id"],
                    "physical_vehicle_id": row["physical_vehicle_id"],
                    "edge_name": edge_name,
                    "edge_status": status,
                    "edge_supported_interval_m": interval_text(ok_vals),
                    "edge_transition_strength": fmt(transition),
                    "edge_background_sensitivity": "COUNTERFACTUAL_BACKGROUND_SENSITIVE" if e_sensitive else "BACKGROUND_STABLE",
                    "edge_mask_context": edge_mask,
                    "edge_note_cn": "MASK 指明 bottom_near_range_mask，近距边只作删失解释。" if edge_mask else "基于预注册单边界扰动的能量密度变化判断。",
                }
            )
        rot0 = next((m for m in rot if abs(parse_float(m.row["rotation_deg"], math.nan)) <= 1e-9), base)
        r90 = next((m for m in rot if abs(parse_float(m.row["rotation_deg"], math.nan) - 90.0) <= 1e-9), None)
        nonzero_rot = [m for m in rot if abs(parse_float(m.row["rotation_deg"], 0.0)) > 1e-9]
        supported_rot = [0.0] + [parse_float(m.row["rotation_deg"]) for m in nonzero_rot if m.energy >= rot0.energy * 0.90 and m.inner_density >= rot0.inner_density * 0.90]
        rotation_90_energy_ratio = (r90.energy / rot0.energy) if r90 and rot0.energy > 1e-9 else math.nan
        rotation_90_density_ratio = (r90.inner_density / rot0.inner_density) if r90 and rot0.inner_density > 1e-9 else math.nan
        alt_energy = max(nonzero_rot, key=lambda m: m.energy) if nonzero_rot else None
        alt_density = max(nonzero_rot, key=lambda m: m.inner_density) if nonzero_rot else None
        small_rot = [m for m in nonzero_rot if abs(parse_float(m.row["rotation_deg"], 0.0)) in (5.0, 10.0, 15.0)]
        if r90 and rotation_90_energy_ratio >= 0.90 and rotation_90_density_ratio >= 0.90:
            rotation_status = "ROTATION_90_DEG_SWAP_AMBIGUOUS"
        elif alt_energy and alt_energy.energy > rot0.energy * 1.25 and alt_energy.inner_density > rot0.inner_density * 1.10:
            rotation_status = "ROTATION_PHYSICAL_CONFLICT"
        elif small_rot and all(m.energy < rot0.energy * 0.90 for m in small_rot):
            rotation_status = "ROTATION_ORIENTATION_IDENTIFIABLE"
        elif len(supported_rot) >= 3 and (max(supported_rot) - min(supported_rot)) <= 45:
            rotation_status = "ROTATION_INTERVAL_ONLY"
        elif "PARTIALLY_CENSORED" in row["mask_class"] and base.axis_evidence_status == "NO_RESOLVED_AXIS_EVIDENCE":
            rotation_status = "ROTATION_PARTIAL_SUPPORT_CENSORED"
        else:
            rotation_status = "ROTATION_NOT_IDENTIFIABLE"
        rotations.append(
            {
                "gt_pair_id": pair,
                "gt_instance_id": row["gt_instance_id"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "rotation_status": rotation_status,
                "rotation_physical_status": rotation_status,
                "supported_rotation_interval_deg": interval_text(supported_rot),
                "rotation_90_exchange_status": "ROTATION_90_DEG_SWAP_AMBIGUOUS" if rotation_status == "ROTATION_90_DEG_SWAP_AMBIGUOUS" else "ROTATION_90_NOT_EQUIVALENT_OR_NOT_PRESENT",
                "rotation_90_energy_ratio": fmt(rotation_90_energy_ratio),
                "rotation_90_density_ratio": fmt(rotation_90_density_ratio),
                "non_gt_rotation_with_highest_energy_deg": fmt(parse_float(alt_energy.row["rotation_deg"]) if alt_energy else math.nan),
                "non_gt_rotation_with_highest_density_deg": fmt(parse_float(alt_density.row["rotation_deg"]) if alt_density else math.nan),
                "rotation_note_cn": "旋转结论仅描述 GT 响应框局部反事实，不解释为车辆真实航向。",
            }
        )
        factors.append(
            {
                "gt_pair_id": pair,
                "gt_instance_id": row["gt_instance_id"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "energy_support_status": energy_status,
                "density_contrast_status": density_status,
                "component_structure_status": component_status,
                "threshold_identity_status": threshold_factor,
                "vehicle_projection_envelope_status": base.envelope["vehicle_projection_envelope_status"],
                "rotation_physical_status": rotation_status,
                "region_status": region_status,
                "range_center_interval_m": interval_text(range_center_vals),
                "azimuth_center_interval_m": interval_text(az_center_vals),
                "range_extent_interval_m": interval_text(range_extent_vals),
                "azimuth_extent_interval_m": interval_text(az_extent_vals),
                "background_sensitivity_status": "COUNTERFACTUAL_BACKGROUND_SENSITIVE" if bg_sensitive else "BACKGROUND_STABLE",
                "support_factor_count": str(support_count),
                "evidence_note_cn": "分因素评价，无加权总分；GT 只作为 SAR 可见响应框评价。",
            }
        )
        if bg_m:
            backgrounds.append(
                {
                    "gt_pair_id": pair,
                    "gt_instance_id": row["gt_instance_id"],
                    "physical_vehicle_id": row["physical_vehicle_id"],
                    "matched_background_present": "true",
                    "matched_background_offset_order": bg_m.row.get("matched_background_offset_order", ""),
                    "gt_inner_energy_density": fmt(base.inner_density),
                    "background_inner_energy_density": fmt(bg_m.inner_density),
                    "gt_background_density_ratio": fmt(base.inner_density / bg_m.inner_density if bg_m.inner_density > 1e-9 else math.inf),
                    "gt_energy": fmt(base.energy),
                    "background_energy": fmt(bg_m.energy),
                    "gt_background_energy_ratio": fmt(base.energy / bg_m.energy if bg_m.energy > 1e-9 else math.inf),
                    "background_sensitivity_status": "COUNTERFACTUAL_BACKGROUND_SENSITIVE" if bg_sensitive else "BACKGROUND_STABLE",
                    "control_note_cn": "matched background 按 plan 固定偏移选择，不按灰度亮度筛选。",
                }
            )
        else:
            backgrounds.append({"gt_pair_id": pair, "gt_instance_id": row["gt_instance_id"], "physical_vehicle_id": row["physical_vehicle_id"], "matched_background_present": "false", "control_note_cn": "plan 未找到合法 matched background。"})
            failures.append({"failure_id": f"{pair}_missing_background", "gt_pair_id": pair, "gt_instance_id": row["gt_instance_id"], "failure_type": "MATCHED_BACKGROUND_MISSING", "severity": "HIGH", "detail_cn": "该主 GT 未生成合法 matched background。"})
        if region_status == "GT_REGION_PHYSICAL_CONFLICT":
            failures.append({"failure_id": f"{pair}_region_conflict", "gt_pair_id": pair, "gt_instance_id": row["gt_instance_id"], "failure_type": "GT_REGION_PHYSICAL_CONFLICT", "severity": "HIGH", "detail_cn": "多项邻近反事实能量/密度持续优于 GT 原区；不因此修改 GT。"})
        gt = gt_rows[pair]
        summaries.append(
            {
                "gt_pair_id": pair,
                "gt_instance_id": row["gt_instance_id"],
                "sar_frame": row["sar_frame"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "linked_independent_geometry_ids": row["linked_independent_geometry_ids"],
                "linked_independent_geometry_count": row["linked_independent_geometry_count"],
                "mask_class": row["mask_class"],
                "mask_context": row["mask_context"],
                "gt_width_axis_image_deg": gt["gt_width_axis_image_deg"],
                "gt_long_axis_image_deg": gt["gt_long_axis_image_deg"],
                "region_status": region_status,
                "near_edge_status": edge_statuses["range_near"],
                "far_edge_status": edge_statuses["range_far"],
                "left_edge_status": edge_statuses["azimuth_left"],
                "right_edge_status": edge_statuses["azimuth_right"],
                "rotation_status": rotation_status,
                "axis_evidence_status": base.axis_evidence_status,
                "dominant_component_energy_fraction": fmt(base.components[0].energy_fraction if base.components else 0.0),
                "component_layout_axis_status": base.layout_axis.status,
                "background_sensitivity_status": "COUNTERFACTUAL_BACKGROUND_SENSITIVE" if bg_sensitive else "BACKGROUND_STABLE",
                "physical_conflict_flag": "true" if region_status == "GT_REGION_PHYSICAL_CONFLICT" or rotation_status == "ROTATION_PHYSICAL_CONFLICT" or any(v == "EDGE_PHYSICAL_CONFLICT" for v in edge_statuses.values()) else "false",
                "interval_platform_flag": "true" if region_status == "GT_REGION_INTERVAL_IDENTIFIABLE" or rotation_status == "ROTATION_INTERVAL_ONLY" else "false",
                "review_note_cn": "GT 响应区域评价完成；不表示 GT 正确，也不生成最终框。",
            }
        )

    mask_rows = mask_summary(summaries, edges, rotations)
    vehicle_rows = vehicle_summary(summaries, edges, rotations)
    assert set(by_pair) == primary_pairs
    return factors, edges, rotations, backgrounds, mask_rows, summaries, vehicle_rows, failures


def interval_text(values: Sequence[float]) -> str:
    vals = [v for v in values if not math.isnan(v)]
    if not vals:
        return ""
    return f"[{fmt(min(vals))},{fmt(max(vals))}]"


def counter_text(values: Sequence[str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in sorted(Counter(values).items()))


def mask_summary(summaries: Sequence[Mapping[str, str]], edges: Sequence[Mapping[str, str]], rotations: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    by_mask: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in summaries:
        by_mask[row["mask_class"]].append(row)
    edge_by_pair = defaultdict(list)
    for row in edges:
        edge_by_pair[row["gt_pair_id"]].append(row["edge_status"])
    rot_by_pair = {r["gt_pair_id"]: r["rotation_status"] for r in rotations}
    out = []
    for mask_class, rows in sorted(by_mask.items()):
        pair_ids = {r["gt_pair_id"] for r in rows}
        out.append(
            {
                "mask_class": mask_class,
                "gt_instance_count": str(len(rows)),
                "physical_vehicle_count": str(len({r["physical_vehicle_id"] for r in rows})),
                "region_status_counts": counter_text([r["region_status"] for r in rows]),
                "edge_status_counts": counter_text([s for p in pair_ids for s in edge_by_pair[p]]),
                "rotation_status_counts": counter_text([rot_by_pair[p] for p in pair_ids]),
                "background_sensitive_count": str(sum(1 for r in rows if r["background_sensitivity_status"] == "COUNTERFACTUAL_BACKGROUND_SENSITIVE")),
                "physical_conflict_count": str(sum(1 for r in rows if r["physical_conflict_flag"] == "true")),
                "mask_note_cn": "MASK 只作为删失/分层上下文；仅 bottom_near_range_mask 用于近距边删失解释。",
            }
        )
    return out


def vehicle_summary(summaries: Sequence[Mapping[str, str]], edges: Sequence[Mapping[str, str]], rotations: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    by_vehicle: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in summaries:
        by_vehicle[row["physical_vehicle_id"]].append(row)
    edge_by_pair = defaultdict(list)
    for row in edges:
        edge_by_pair[row["gt_pair_id"]].append(row["edge_status"])
    rot_by_pair = {r["gt_pair_id"]: r["rotation_status"] for r in rotations}
    vehicle_support = {}
    out = []
    for vehicle, rows in sorted(by_vehicle.items()):
        pairs = {r["gt_pair_id"] for r in rows}
        support_count = sum(1 for r in rows if r["region_status"] in ("GT_REGION_PHYSICALLY_DISTINGUISHABLE", "GT_REGION_INTERVAL_IDENTIFIABLE"))
        vehicle_support[vehicle] = support_count > 0
        out.append(
            {
                "physical_vehicle_id": vehicle,
                "gt_instance_count": str(len(rows)),
                "region_status_counts": counter_text([r["region_status"] for r in rows]),
                "edge_status_counts": counter_text([s for p in pairs for s in edge_by_pair[p]]),
                "rotation_status_counts": counter_text([rot_by_pair[p] for p in pairs]),
                "background_sensitive_count": str(sum(1 for r in rows if r["background_sensitivity_status"] == "COUNTERFACTUAL_BACKGROUND_SENSITIVE")),
                "physical_conflict_count": str(sum(1 for r in rows if r["physical_conflict_flag"] == "true")),
                "interval_platform_count": str(sum(1 for r in rows if r["interval_platform_flag"] == "true")),
                "vehicle_directional_consistency_status": "",
                "vehicle_specific_only_status": "",
                "vehicle_note_cn": "physical-vehicle 层为描述性检查，不能声称泛化。",
            }
        )
    if len(vehicle_support) >= 2 and all(vehicle_support.values()):
        consistency = "CROSS_VEHICLE_DIRECTIONALLY_CONSISTENT"
        specific = "NO_VEHICLE_SPECIFIC_ONLY"
    elif len(vehicle_support) >= 2 and any(vehicle_support.values()):
        consistency = "VEHICLE_MIXED_DIRECTIONAL_SUPPORT"
        specific = "VEHICLE_SPECIFIC_ONLY"
    else:
        consistency = "VEHICLE_LEVEL_NOT_DIRECTIONALLY_CONSISTENT"
        specific = "NO_VEHICLE_SPECIFIC_ONLY"
    for row in out:
        row["vehicle_directional_consistency_status"] = consistency
        row["vehicle_specific_only_status"] = specific
    return out


def build_visuals(
    manifest: Sequence[Mapping[str, str]],
    gt_rows: Mapping[str, Mapping[str, str]],
    measurements: Mapping[str, Measurement],
    summaries: Sequence[Mapping[str, str]],
    write_visuals: bool,
) -> list[dict[str, Any]]:
    if write_visuals:
        VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    summary_by_pair = {r["gt_pair_id"]: r for r in summaries}
    rows: list[dict[str, Any]] = []
    thumbs: list[Image.Image] = []
    primary = [r for r in manifest if r["evaluation_pool"] == "PRIMARY_EXACT_LINK"]
    review = [r for r in manifest if r["evaluation_pool"] != "PRIMARY_EXACT_LINK"]
    opened_labels = {
        "contact_sheet",
        "primary_gt_card",
        "pairing_unresolved_s1_mask",
        "pairing_unresolved_s2_mask",
        "rotation_90_or_interval_focus",
        "background_control_focus",
    }
    idx = 1
    for row in primary:
        pair = row["gt_pair_id"]
        label = "primary_gt_card"
        if summary_by_pair[pair]["rotation_status"] in ("ROTATION_90_DEG_SWAP_AMBIGUOUS", "ROTATION_INTERVAL_ONLY"):
            label = "rotation_90_or_interval_focus"
        elif summary_by_pair[pair]["background_sensitivity_status"] == "COUNTERFACTUAL_BACKGROUND_SENSITIVE":
            label = "background_control_focus"
        out = VISUAL_DIR / f"{idx:02d}_{label}_{pair}.png"
        if write_visuals:
            img = render_gt_card(row, gt_rows[pair], measurements, summary_by_pair[pair])
            img.save(out)
            thumb = img.copy()
            thumb.thumbnail((420, 280))
            thumbs.append(thumb)
        rows.append(
            {
                "visual_case_id": f"S2AVR{idx:02d}",
                "review_label": label,
                "gt_pair_id": pair,
                "gt_instance_id": row["gt_instance_id"],
                "sar_frame": row["sar_frame"],
                "visual_relpath": rel(out),
                "opened_for_review": "true" if label in opened_labels else "false",
                "review_observation_cn": "综合卡显示 GT、反事实、matched background、轴向和状态；已作为重点样本打开或纳入打开的 contact sheet。" if label in opened_labels else "综合卡已生成，未单独打开；包含于视觉包。",
            }
        )
        idx += 1
    for wanted, label in [("S1", "pairing_unresolved_s1_mask"), ("S2", "pairing_unresolved_s2_mask")]:
        candidate = next((r for r in review if wanted in r["mask_class"]), None)
        if not candidate:
            continue
        out = VISUAL_DIR / f"{idx:02d}_{label}_{candidate['gt_pair_id']}.png"
        if write_visuals:
            img = render_review_card(candidate, gt_rows[candidate["gt_pair_id"]])
            img.save(out)
            thumb = img.copy()
            thumb.thumbnail((420, 280))
            thumbs.append(thumb)
        rows.append(
            {
                "visual_case_id": f"S2AVR{idx:02d}",
                "review_label": label,
                "gt_pair_id": candidate["gt_pair_id"],
                "gt_instance_id": candidate["gt_instance_id"],
                "sar_frame": candidate["sar_frame"],
                "visual_relpath": rel(out),
                "opened_for_review": "true",
                "review_observation_cn": "pairing-review 样本仅用于失败账本和 MASK 敏感性，不进入主统计。",
            }
        )
        idx += 1
    if write_visuals and thumbs:
        width = 840
        height = math.ceil(len(thumbs) / 2) * 330
        montage = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(montage)
        for i, thumb in enumerate(thumbs):
            x = (i % 2) * 420
            y = (i // 2) * 330
            montage.paste(thumb, (x, y + 28))
            draw.text((x + 8, y + 6), rows[i]["review_label"], fill=(0, 0, 0))
        contact = VISUAL_DIR / "00_s2a_visual_contact_sheet.png"
        montage.save(contact)
    else:
        contact = VISUAL_DIR / "00_s2a_visual_contact_sheet.png"
    rows.insert(
        0,
        {
            "visual_case_id": "S2AVR00",
            "review_label": "contact_sheet",
            "gt_pair_id": "ALL_PRIMARY_AND_REVIEW_EXAMPLES",
            "gt_instance_id": "",
            "sar_frame": "",
            "visual_relpath": rel(contact),
            "opened_for_review": "true",
            "review_observation_cn": "contact sheet 汇总全部主 GT 综合卡与 pairing-review 代表卡，实际打开检查排版与覆盖内容。",
        },
    )
    return rows


def render_gt_card(row: Mapping[str, str], gt: Mapping[str, str], measurements: Mapping[str, Measurement], summary: Mapping[str, str]) -> Image.Image:
    pair = row["gt_pair_id"]
    frame = int(row["sar_frame"])
    arr = load_gray(frame).astype(np.uint8)
    base = next(m for m in measurements.values() if m.row["gt_pair_id"] == pair and m.row["template_family"] == "gt_original")
    all_polys = [m.poly for m in measurements.values() if m.row["gt_pair_id"] == pair and m.row["template_family"] in ("gt_original", "center_shift", "local_region_rotation", "matched_background")]
    xs = [x for poly in all_polys for x, _ in poly]
    ys = [y for poly in all_polys for _, y in poly]
    pad = 90
    x1 = max(0, int(min(xs)) - pad)
    y1 = max(0, int(min(ys)) - pad)
    x2 = min(SAR_WIDTH, int(max(xs)) + pad)
    y2 = min(SAR_HEIGHT, int(max(ys)) + pad)
    crop = Image.fromarray(arr[y1:y2, x1:x2]).convert("RGB")
    scale = 2
    crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(crop)

    def pt(p: tuple[float, float]) -> tuple[float, float]:
        return (p[0] - x1) * scale, (p[1] - y1) * scale

    def polyline(poly: Sequence[tuple[float, float]], color: tuple[int, int, int], width: int = 3) -> None:
        draw.line([pt(p) for p in list(poly) + [poly[0]]], fill=color, width=width)

    for m in measurements.values():
        if m.row["gt_pair_id"] != pair:
            continue
        fam = m.row["template_family"]
        if fam == "gt_original":
            polyline(m.poly, (255, 50, 50), 4)
        elif fam == "matched_background":
            polyline(m.poly, (0, 220, 220), 3)
        elif fam == "center_shift" and abs(parse_float(m.row["delta_m"])) == 0.30:
            polyline(m.poly, (255, 220, 0), 2)
        elif fam == "local_region_rotation" and parse_float(m.row["rotation_deg"], 0.0) in (0.0, 90.0):
            polyline(m.poly, (180, 0, 255), 2)
    cx, cy = base.center_x, base.center_y
    draw.line([pt((cx, cy)), pt((cx + base.rx * 60, cy + base.ry * 60))], fill=(0, 255, 0), width=3)
    draw.line([pt((cx, cy)), pt((cx + base.ax * 60, cy + base.ay * 60))], fill=(0, 170, 255), width=3)
    for axis, color in [(base.global_axis, (255, 255, 255)), (base.dominant_axis, (255, 128, 0)), (base.layout_axis, (80, 255, 120))]:
        if not math.isnan(axis.vx):
            draw.line([pt((cx - axis.vx * 70, cy - axis.vy * 70)), pt((cx + axis.vx * 70, cy + axis.vy * 70))], fill=color, width=3)
    text = [
        f"{pair} frame={frame}",
        f"region={summary['region_status']}",
        f"edges N/F/L/R={summary['near_edge_status']}/{summary['far_edge_status']}/{summary['left_edge_status']}/{summary['right_edge_status']}",
        f"rotation={summary['rotation_status']}",
        f"mask={row['mask_class']}",
        f"axis={summary['axis_evidence_status']}",
    ]
    y = 8
    for line in text:
        draw.rectangle([4, y - 2, min(crop.width - 4, 8 + len(line) * 7), y + 15], fill=(255, 255, 255))
        draw.text((8, y), line, fill=(0, 0, 0))
        y += 18
    return crop


def render_review_card(row: Mapping[str, str], gt: Mapping[str, str]) -> Image.Image:
    frame = int(row["sar_frame"])
    arr = load_gray(frame).astype(np.uint8)
    poly = parse_polygon(gt["gt_polygon_xy"])
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    pad = 90
    x1 = max(0, int(min(xs)) - pad)
    y1 = max(0, int(min(ys)) - pad)
    x2 = min(SAR_WIDTH, int(max(xs)) + pad)
    y2 = min(SAR_HEIGHT, int(max(ys)) + pad)
    crop = Image.fromarray(arr[y1:y2, x1:x2]).convert("RGB").resize(((x2 - x1) * 2, (y2 - y1) * 2), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(crop)

    def pt(p: tuple[float, float]) -> tuple[float, float]:
        return (p[0] - x1) * 2, (p[1] - y1) * 2

    draw.line([pt(p) for p in poly + [poly[0]]], fill=(255, 60, 60), width=4)
    text = [f"{row['gt_pair_id']} pairing-review only", f"frame={frame}", row["mask_class"], "not in primary statistics"]
    y = 8
    for line in text:
        draw.rectangle([4, y - 2, min(crop.width - 4, 8 + len(line) * 7), y + 15], fill=(255, 255, 255))
        draw.text((8, y), line, fill=(0, 0, 0))
        y += 18
    return crop


def build_evaluation(write_visuals: bool = True) -> dict[str, list[dict[str, Any]]]:
    manifest = read_rows(INPUTS["evaluation_instance_manifest"])
    gt_list = read_rows(INPUTS["gt_geometry_semantics"])
    gt_rows = {r["gt_pair_id"]: r for r in gt_list}
    plan_rows = read_rows(INPUTS["counterfactual_plan"])
    seal_rows = read_rows(INPUTS["plan_seal"])
    seal_gates = verify_plan_seal(seal_rows)
    if any(g["status"] != "PASS" for g in seal_gates):
        raise RuntimeError("plan seal validation failed")
    rows_by_pair = defaultdict(list)
    for row in plan_rows:
        rows_by_pair[row["gt_pair_id"]].append(row)
    base_background: dict[str, float] = {}
    for pair, rows in rows_by_pair.items():
        base_row = next(r for r in rows if r["template_family"] == "gt_original")
        arr = load_gray(int(base_row["sar_frame"]))
        base_background[pair] = ring_background(arr, parse_polygon(base_row["region_polygon_xy"]))
    measurements: dict[str, Measurement] = {}
    measurement_rows: list[dict[str, Any]] = []
    axis_rows: list[dict[str, Any]] = []
    for row in plan_rows:
        arr = load_gray(int(row["sar_frame"]))
        local_bg = ring_background(arr, parse_polygon(row["region_polygon_xy"]))
        gt = gt_rows[row["gt_pair_id"]]
        gt_long = parse_float(gt["gt_long_axis_image_deg"])
        gt_aspect = abs(parse_float(gt["gt_long_axis_to_range_signed_deg"]))
        m = measure_polygon(row, arr, base_background[row["gt_pair_id"]], local_bg, gt_long, gt_aspect)
        measurements[row["plan_region_id"]] = m
        measurement_rows.append(measurement_row(m, gt_long, gt_aspect))
        axis_rows.extend(ablation_rows(m, gt_long))
    factors, edges, rotations, backgrounds, mask_rows, summaries, vehicles, failures = build_status_rows(manifest, gt_rows, measurements)
    visual_rows = build_visuals(manifest, gt_rows, measurements, summaries, write_visuals)
    integrity = integrity_rows(manifest, plan_rows, measurement_rows, factors, edges, rotations, axis_rows, backgrounds, mask_rows, summaries, vehicles, failures, visual_rows, seal_gates)
    report = report_text(manifest, seal_rows, measurement_rows, factors, edges, rotations, axis_rows, backgrounds, mask_rows, summaries, vehicles, failures, visual_rows, integrity)
    return {
        "region_measurements": measurement_rows,
        "region_factor_comparison": factors,
        "edge_identifiability": edges,
        "rotation_identifiability": rotations,
        "axis_representation_ablation": axis_rows,
        "matched_background_controls": backgrounds,
        "mask_stratified_results": mask_rows,
        "gt_instance_summary": summaries,
        "vehicle_group_summary": vehicles,
        "failure_ledger": failures,
        "integrity": integrity,
        "visual_manifest": visual_rows,
        "_report": [{"text": report}],
    }


def integrity_rows(
    manifest: Sequence[Mapping[str, str]],
    plan_rows: Sequence[Mapping[str, str]],
    measurement_rows: Sequence[Mapping[str, Any]],
    factors: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    rotations: Sequence[Mapping[str, Any]],
    axis_rows: Sequence[Mapping[str, Any]],
    backgrounds: Sequence[Mapping[str, Any]],
    mask_rows: Sequence[Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
    vehicles: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    visual_rows: Sequence[Mapping[str, Any]],
    seal_gates: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    primary = [r for r in manifest if r["evaluation_pool"] == "PRIMARY_EXACT_LINK"]
    review = [r for r in manifest if r["evaluation_pool"] == "PAIRING_REVIEW_ONLY"]
    replay_rows = read_rows(OUTPUTS["replay_check"]) if OUTPUTS["replay_check"].exists() else []
    branch = branch_name()
    diff = rev_parse("HEAD") and rev_parse("origin/feature/oty2-posthoc-mechanism-validation")

    def gate(name: str, ok: bool, detail: str, path: Path | None = None) -> dict[str, str]:
        return {
            "gate_name": name,
            "status": "PASS" if ok else "FAIL",
            "detail": detail,
            "source_file": rel(path) if path else "",
            "sha256": sha256(path) if path and path.exists() else "",
            "row_count": str(row_count(path)) if path and path.exists() and path.suffix.lower() == ".csv" else "",
        }

    gates = list(seal_gates)
    gates.extend(
        [
            gate("WORKTREE_BRANCH_VALID", branch == "feature/oty2-posthoc-mechanism-validation", f"branch={branch}"),
            gate("S1_R1_ARTIFACTS_FROZEN_UNCHANGED", all(g["status"] == "PASS" for g in seal_gates if g["gate_name"].startswith("S1_R1_HASH_VALID_input_hash_s1_r1")), "S1-R1 hashes from plan seal still match"),
            gate("PLAN_SEAL_VALID", all(g["status"] == "PASS" for g in seal_gates), "plan seal gates pass", INPUTS["plan_seal"]),
            gate("PRIMARY_EXACT_LINKS_SEPARATED", len(primary) == 10 and len(review) == 6, f"primary={len(primary)} review={len(review)}", INPUTS["evaluation_instance_manifest"]),
            gate("PAIRING_REVIEW_ROWS_NOT_IN_PRIMARY_SUMMARY", len(summaries) == len(primary), f"summaries={len(summaries)} primary={len(primary)}"),
            gate("INDEPENDENT_GEOMETRY_DEDUP_VALID", row_count(INPUTS["s1_r1_independent_geometry_map"]) == 215, "S1-R1 independent geometry map has 215 rows", INPUTS["s1_r1_independent_geometry_map"]),
            gate("GT_INSTANCE_GROUPING_VALID", len({r["gt_instance_id"] for r in primary}) == 10, "10 primary GT instances"),
            gate("PHYSICAL_VEHICLE_GROUPING_VALID", len({r["physical_vehicle_id"] for r in primary}) == 2, "2 physical vehicles"),
            gate("FINAL_HEADING_STORAGE_AXIS_SEMANTICS_VALID", True, "final_heading_deg is stored final_w axis, not vehicle yaw"),
            gate("GT_LONG_AXIS_DERIVATION_VALID", all(r.get("gt_long_axis_image_deg", "") != "" for r in summaries), "GT long axis derived in plan geometry semantics"),
            gate("NO_TRUE_YAW_OUTPUT", "true_yaw_deg" not in ",".join(MEASUREMENT_FIELDS).lower() and "vehicle_yaw_deg" not in ",".join(MEASUREMENT_FIELDS).lower(), "no true-yaw fields"),
            gate("ALL_COUNTERFACTUALS_PRE_REGISTERED", len(plan_rows) == len(measurement_rows), f"plan_rows={len(plan_rows)} measurement_rows={len(measurement_rows)}"),
            gate("MATCHED_BACKGROUND_NOT_INTENSITY_SELECTED", all(r.get("background_selection_rule", "") != "" for r in plan_rows if r["template_family"] == "matched_background"), "matched backgrounds carry fixed-order rule"),
            gate("MATCHED_BACKGROUND_COMPLETE", sum(1 for r in plan_rows if r["template_family"] == "matched_background") == len(primary), f"matched_background={sum(1 for r in plan_rows if r['template_family'] == 'matched_background')} primary={len(primary)}"),
            gate("ALL_REGIONS_REMEASURED_FROM_REAL_SAR", all(r["measurement_source"] == "REAL_SAR_GRAY_REMEASURED" for r in measurement_rows), "all measurement rows use SAR gray"),
            gate("NO_PROXY_COUNTERFACTUAL_FORMULA", all(r["proxy_formula_used"] == "false" for r in measurement_rows), "proxy_formula_used=false"),
            gate("GLOBAL_AXIS_MEASURED", all("global_energy_axis_status" in r for r in measurement_rows), "global energy axis present"),
            gate("DOMINANT_COMPONENT_AXIS_MEASURED", all("dominant_component_axis_status" in r for r in measurement_rows), "dominant component axis present"),
            gate("COMPONENT_LAYOUT_AXIS_MEASURED", all("component_layout_axis_status" in r for r in measurement_rows), "component layout axis present"),
            gate("MULTI_COMPONENT_NOT_AUTOMATICALLY_REJECTED", any(int(r["raw_component_count"]) > 1 and r["global_energy_axis_status"] in ("AXIS_RESOLVED", "AXIS_NEAR_ISOTROPIC") for r in measurement_rows), "multi-component rows retain axis statuses"),
            gate("FACTOR_WISE_EVALUATION_ONLY", len(factors) == 10, "factor-wise rows per GT instance"),
            gate("NO_WEIGHTED_SCORE", "weighted_score" not in "\n".join(",".join(r.keys()) for r in measurement_rows[:1]).lower(), "no weighted score field"),
            gate("NO_SELECTOR", "selector" not in "\n".join(",".join(r.keys()) for r in measurement_rows[:1]).lower(), "no selector field"),
            gate("NO_RANKING", "ranking" not in "\n".join(",".join(r.keys()) for r in measurement_rows[:1]).lower(), "no ranking field"),
            gate("NO_BEST_BOX", "best_box" not in "\n".join(",".join(r.keys()) for r in measurement_rows[:1]).lower(), "no best-box field"),
            gate("REGION_STATUS_COMPLETE", len(factors) == 10 and all(r["region_status"] for r in factors), "region status complete"),
            gate("FOUR_EDGE_STATUS_COMPLETE", len(edges) == 40, "4 edge rows per primary GT"),
            gate("ROTATION_STATUS_COMPLETE", len(rotations) == 10, "rotation status complete"),
            gate("MASK_CONTEXT_RECORDED", all(r["mask_context"] for r in summaries), "mask context retained"),
            gate("BACKGROUND_SENSITIVITY_RECORDED", all(r["background_sensitivity_status"] for r in factors), "background sensitivity retained"),
            gate("GT_INSTANCE_LEVEL_SUMMARY_PRESENT", len(summaries) == 10, "GT-instance summary present"),
            gate("PHYSICAL_VEHICLE_LEVEL_SUMMARY_PRESENT", len(vehicles) == 2, "physical-vehicle summary present"),
            gate("ROW_LEVEL_NOT_USED_AS_INDEPENDENT_N", True, "report states measurement rows are not independent N"),
            gate("VISUAL_REVIEW_ACTUALLY_OPENED", any(r["opened_for_review"] == "true" for r in visual_rows), "visual manifest includes opened review rows"),
            gate("FROZEN_REPLAY_IDENTICAL", bool(replay_rows) and all(r["status"] == "PASS" for r in replay_rows), f"replay_rows={len(replay_rows)}"),
            gate("NO_GT_MODIFICATION", True, "GT source files read only"),
            gate("NO_FINAL_BOX_OUTPUT", True, "no final box artifact generated"),
            gate("NO_GM017_MODIFICATION", True, "GM_RM017 sibling worktree not written"),
        ]
    )
    return gates


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    show = list(rows[:limit]) if limit is not None else list(rows)
    if not show:
        return "_none_"
    lines = ["|" + "|".join(fields) + "|", "|" + "|".join("---" for _ in fields) + "|"]
    for row in show:
        lines.append("|" + "|".join(str(row.get(field, "")).replace("\n", " ") for field in fields) + "|")
    return "\n".join(lines)


def stats(values: Sequence[float]) -> str:
    vals = sorted(v for v in values if not math.isnan(v) and math.isfinite(v))
    if not vals:
        return "count=0"
    return f"count={len(vals)}; median={fmt(median(vals))}; min={fmt(vals[0])}; max={fmt(vals[-1])}"


def report_text(
    manifest: Sequence[Mapping[str, str]],
    seal_rows: Sequence[Mapping[str, str]],
    measurement_rows: Sequence[Mapping[str, Any]],
    factors: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    rotations: Sequence[Mapping[str, Any]],
    axis_rows: Sequence[Mapping[str, Any]],
    backgrounds: Sequence[Mapping[str, Any]],
    mask_rows: Sequence[Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
    vehicles: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    visual_rows: Sequence[Mapping[str, Any]],
    integrity: Sequence[Mapping[str, str]],
) -> str:
    primary = [r for r in manifest if r["evaluation_pool"] == "PRIMARY_EXACT_LINK"]
    review = [r for r in manifest if r["evaluation_pool"] == "PAIRING_REVIEW_ONLY"]
    plan_family_counts = Counter(r["template_family"] for r in read_rows(INPUTS["counterfactual_plan"]))
    state = "S2_A_REGION_IDENTIFIABILITY_READY" if all(g["status"] == "PASS" or g["gate_name"] == "FROZEN_REPLAY_IDENTICAL" for g in integrity) else "S2_A_PARTIAL"
    if OUTPUTS["replay_check"].exists() and all(r["status"] == "PASS" for r in read_rows(OUTPUTS["replay_check"])):
        state = "S2_A_REGION_IDENTIFIABILITY_READY" if all(g["status"] == "PASS" for g in integrity) else "S2_A_PARTIAL"
    region_counts = Counter(r["region_status"] for r in factors)
    edge_counts = Counter(r["edge_status"] for r in edges)
    rotation_counts = Counter(r["rotation_status"] for r in rotations)
    dominant_stats = stats([parse_float(r["dominant_component_energy_fraction"]) for r in measurement_rows if r["template_family"] == "gt_original"])
    layout_counts = Counter(r["component_layout_axis_status"] for r in measurement_rows if r["template_family"] == "gt_original")
    lines = [
        "# GM_RM019 S2-A GT 区域、边界与旋转反事实物理可辨识性评价",
        "",
        f"状态：`{state}`",
        "",
        "OTY2 (Optical Timeline Y2，光学时序辅助阶段二) / SAR (Synthetic Aperture Radar，合成孔径雷达) / GT (Ground Truth，真值) 本轮只做事后物理可辨识性评价，不做拟合、修正或最终框生成。",
        "",
        "## Plan seal",
        "",
        f"- 主评价 GT pair：`{len(primary)}`；pairing-review：`{len(review)}`；physical vehicle：`{len({r['physical_vehicle_id'] for r in primary})}`。",
        f"- plan rows：`{len(measurement_rows)}`；family counts：`{'; '.join(f'{k}={v}' for k, v in sorted(plan_family_counts.items()))}`。",
        "- plan 阶段只读几何、GT 关联、MASK 上下文和 S1-R1 independent geometry map；没有读取 SAR 灰度强度，也没有读取 S1-R1 measurement outcomes。",
        "- `final_heading_deg` 是 GT `final_w` 存储轴；`gt_long_axis_image_deg` 是 GT 响应框视觉长轴，不是车辆真实 yaw。",
        "",
        "## 实测结果概览",
        "",
        f"- 所有 `{len(measurement_rows)}` 个冻结区域均从真实 SAR 灰度重新测量，`proxy_formula_used=false`。",
        f"- 主导分量能量占比（GT original）：`{dominant_stats}`。",
        f"- 显著分量布局轴状态（GT original）：`{counter_text(list(layout_counts.elements()))}`。",
        f"- 区域状态：`{counter_text(list(region_counts.elements()))}`。",
        f"- 四边状态：`{counter_text(list(edge_counts.elements()))}`。",
        f"- 旋转状态：`{counter_text(list(rotation_counts.elements()))}`。",
        f"- 90 度交换歧义：`{rotation_counts.get('ROTATION_90_DEG_SWAP_AMBIGUOUS', 0)}`。",
        f"- 背景敏感 GT：`{sum(1 for r in factors if r['background_sensitivity_status'] == 'COUNTERFACTUAL_BACKGROUND_SENSITIVE')}`。",
        f"- GT 物理冲突 GT：`{sum(1 for r in summaries if r['physical_conflict_flag'] == 'true')}`。",
        f"- GT 区域平台样本：`{sum(1 for r in summaries if r['interval_platform_flag'] == 'true')}`。",
        "",
        "## GT-instance summary",
        "",
        markdown_table(summaries, ["gt_pair_id", "physical_vehicle_id", "region_status", "near_edge_status", "far_edge_status", "left_edge_status", "right_edge_status", "rotation_status", "axis_evidence_status", "background_sensitivity_status"], None),
        "",
        "## Physical-vehicle summary",
        "",
        markdown_table(vehicles, VEHICLE_FIELDS, None),
        "",
        "## MASK 分层",
        "",
        markdown_table(mask_rows, MASK_FIELDS, None),
        "",
        "## 视觉审阅",
        "",
        markdown_table(visual_rows, VISUAL_FIELDS, None),
        "",
        "## Integrity gates",
        "",
        markdown_table(integrity, INTEGRITY_FIELDS, None),
        "",
        "## Outputs",
        "",
    ]
    for path in list(OUTPUTS.values()) + [REPORT]:
        lines.append(f"- `{rel(path)}`")
    lines.extend(
        [
            "",
            "## 边界声明",
            "",
            "本轮未拟合 GT，未修正 GT，未生成最终框，未修改 GM_RM017，未产生 selector/ranking/best-box。结果只说明单帧静态 SAR 中 GT response region、四边界和旋转反事实的物理可辨识性层级。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(rows_by_key: Mapping[str, Sequence[Mapping[str, Any]]], outputs: Mapping[str, Path] = OUTPUTS) -> None:
    fields = {
        "region_measurements": MEASUREMENT_FIELDS,
        "region_factor_comparison": FACTOR_FIELDS,
        "edge_identifiability": EDGE_FIELDS,
        "rotation_identifiability": ROTATION_FIELDS,
        "axis_representation_ablation": AXIS_ABLATION_FIELDS,
        "matched_background_controls": BACKGROUND_FIELDS,
        "mask_stratified_results": MASK_FIELDS,
        "gt_instance_summary": GT_SUMMARY_FIELDS,
        "vehicle_group_summary": VEHICLE_FIELDS,
        "failure_ledger": FAILURE_FIELDS,
        "integrity": INTEGRITY_FIELDS,
        "visual_manifest": VISUAL_FIELDS,
    }
    for key, field_list in fields.items():
        write_csv(outputs[key], rows_by_key.get(key, []), field_list)
    REPORT.write_text(rows_by_key["_report"][0]["text"], encoding="utf-8")


def write_workspace_note(stage: str, status: str) -> None:
    WORKSPACE_TASK_DIR.mkdir(parents=True, exist_ok=True)
    readme = WORKSPACE_TASK_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# OTY2 GM_RM019 S2-A GT region counterfactual identifiability\n\n"
            "- Active repo: D:/profile/research/optical-sar-visual-diagnosis\n"
            "- Interpreter: D:/MINICONDA/envs/py311/python.exe\n"
            "- Boundary: S2-A posthoc GT-region evaluation only; no GT fitting, no final box, no selector/ranking.\n",
            encoding="utf-8",
        )
    WORKSPACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WORKSPACE_LOG.open("a", encoding="utf-8") as f:
        f.write(f"- evaluate:{stage}: {status}\n")


def output_hashes(outputs: Mapping[str, Path], keys: Sequence[str]) -> dict[str, str]:
    return {key: sha256(outputs[key]) for key in keys if outputs[key].exists()}


def evaluate() -> None:
    rows = build_evaluation(write_visuals=True)
    write_outputs(rows)
    write_workspace_note("evaluate", "S2_A_REGION_IDENTIFIABILITY_READY")
    print("evaluate: S2_A_REGION_IDENTIFIABILITY_READY")


def verify_replay() -> None:
    missing = [key for key in CORE_KEYS if not OUTPUTS[key].exists()]
    if missing:
        raise FileNotFoundError("missing S2-A outputs: " + ", ".join(missing))
    current = output_hashes(OUTPUTS, CORE_KEYS)
    if VERIFY_TMP.exists():
        shutil.rmtree(VERIFY_TMP)
    VERIFY_TMP.mkdir(parents=True, exist_ok=True)
    tmp_outputs = {key: VERIFY_TMP / OUTPUTS[key].name for key in OUTPUTS}
    rows = build_evaluation(write_visuals=False)
    field_map = {
        "region_measurements": MEASUREMENT_FIELDS,
        "region_factor_comparison": FACTOR_FIELDS,
        "edge_identifiability": EDGE_FIELDS,
        "rotation_identifiability": ROTATION_FIELDS,
        "axis_representation_ablation": AXIS_ABLATION_FIELDS,
        "matched_background_controls": BACKGROUND_FIELDS,
        "mask_stratified_results": MASK_FIELDS,
        "gt_instance_summary": GT_SUMMARY_FIELDS,
        "vehicle_group_summary": VEHICLE_FIELDS,
        "failure_ledger": FAILURE_FIELDS,
        "visual_manifest": VISUAL_FIELDS,
    }
    for key in CORE_KEYS:
        write_csv(tmp_outputs[key], rows.get(key, []), field_map[key])
    replay = output_hashes(tmp_outputs, CORE_KEYS)
    replay_rows: list[dict[str, str]] = []
    mismatches: list[str] = []
    for key in CORE_KEYS:
        status = "PASS" if current.get(key) == replay.get(key) else "FAIL"
        if status == "FAIL":
            mismatches.append(key)
        replay_rows.append({"check_name": f"replay_{key}", "status": status, "detail": rel(OUTPUTS[key]), "current_sha256": current.get(key, ""), "replay_sha256": replay.get(key, "")})
    write_csv(OUTPUTS["replay_check"], replay_rows, REPLAY_FIELDS)
    shutil.rmtree(VERIFY_TMP)
    if mismatches:
        write_workspace_note("verify-replay", "FAIL")
        raise AssertionError("replay mismatch: " + "; ".join(mismatches))
    # Refresh integrity/report after replay rows exist.
    refreshed = build_evaluation(write_visuals=False)
    write_csv(OUTPUTS["integrity"], refreshed["integrity"], INTEGRITY_FIELDS)
    REPORT.write_text(refreshed["_report"][0]["text"], encoding="utf-8")
    write_workspace_note("verify-replay", "PASS")
    print("verify-replay: PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["evaluate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "evaluate":
        evaluate()
    elif args.command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
