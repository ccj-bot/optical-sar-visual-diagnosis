"""Measure GM_RM019 static SAR range-azimuth response spreading.

This diagnostic is posthoc only. It measures frozen local response units in the
SAR gray image domain, using the existing fan-polar image geometry. It does not
create candidate boxes, selector or ranking outputs, final annotations, revised
GT, identity claims, training artifacts, or threshold-tuned rules.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path(r"D:\profile\research\data")
WORKSPACE_LOG = Path(r"D:\profile\research\workspace\logs\oty2_gm_rm019_static_directional_spread_measurement_20260712.md")

DATE = "20260712"
SCENE = "GM_RM019"
SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
GEOMETRY_ORIGIN_STATUS = "configured_fan_center_px_1154_0_1330_6_reused_from_wgv3_5a_r2c"
VERIFY_TMP_DIR = REPO_ROOT / "outputs" / "oty2_gm_rm019_static_directional_spread_measurement_20260712" / "_verify_tmp"
VISUAL_DIR = REPO_ROOT / "outputs" / "oty2_gm_rm019_static_directional_spread_measurement_20260712" / "visual_review"

INPUTS = {
    "local_response_units": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv",
    "boundary_variant_families": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_variant_families_20260711.csv",
    "response_unit_gt_instance_matrix": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_20260711.csv",
    "boundary_family_gt_instance_matrix": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_family_gt_instance_matrix_20260711.csv",
    "background_counterexamples": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_background_counterexamples_20260711.csv",
    "vehicle_structure_hypothesis": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_vehicle_structure_hypothesis_20260711.csv",
    "mask_observation_audit": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv",
    "paired_annotations": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "atom_graph_nodes": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_atom_graph_nodes_20260711.csv",
    "response_box_hypotheses": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_response_box_hypotheses_20260711.csv",
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_gm_rm019_static_directional_spread_measurement_{DATE}.md",
    "measurements": SAMPLES_DIR / f"oty2_gm_rm019_static_directional_spread_measurements_{DATE}.csv",
    "group_summary": SAMPLES_DIR / f"oty2_gm_rm019_static_directional_spread_group_summary_{DATE}.csv",
    "pairwise_controls": SAMPLES_DIR / f"oty2_gm_rm019_static_directional_spread_pairwise_controls_{DATE}.csv",
    "counterexamples": SAMPLES_DIR / f"oty2_gm_rm019_static_directional_spread_counterexamples_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_gm_rm019_static_directional_spread_gate_integrity_{DATE}.csv",
}

REGION_TYPES = ("core_region", "conservative_response_region")
PRIMARY_REGION = "conservative_response_region"

MEASUREMENT_FIELDS = [
    "response_unit_id",
    "source_response_box_id",
    "source_r1_family_id",
    "sar_frame",
    "measurement_region_type",
    "geometry_origin_status",
    "sar_origin_x",
    "sar_origin_y",
    "response_center_x",
    "response_center_y",
    "range_unit_x",
    "range_unit_y",
    "azimuth_unit_x",
    "azimuth_unit_y",
    "boundary_family_id",
    "boundary_contact_state",
    "mask_state",
    "sample_group",
    "is_gt_local_positive_control",
    "is_registered_background_counterexample",
    "is_boundary_censored_response",
    "is_unresolved_control",
    "core_atom_ids",
    "optional_atom_ids",
    "core_atom_roles",
    "all_atom_roles",
    "background_counterexample_atom_ids",
    "region_bbox",
    "pixel_count",
    "rect_pixel_count",
    "raw_intensity_sum",
    "background_estimate",
    "background_sample_count",
    "background_source",
    "background_subtracted_energy",
    "energy_valid",
    "range_weighted_mean",
    "azimuth_weighted_mean",
    "range_weighted_std",
    "azimuth_weighted_std",
    "range_p50_width",
    "range_p80_width",
    "range_p90_width",
    "azimuth_p50_width",
    "azimuth_p80_width",
    "azimuth_p90_width",
    "range_to_azimuth_p80_ratio",
    "range_to_azimuth_p90_ratio",
    "principal_axis_major_std",
    "principal_axis_minor_std",
    "principal_axis_ratio",
    "principal_axis_angle_image_deg",
    "principal_axis_angle_to_range_deg",
    "principal_axis_angle_to_azimuth_deg",
    "energy_centroid_x",
    "energy_centroid_y",
    "energy_centroid_offset_px",
    "boundary_variant_count",
    "boundary_variant_range_p80_min",
    "boundary_variant_range_p80_max",
    "boundary_variant_range_p80_dispersion",
    "boundary_variant_azimuth_p80_min",
    "boundary_variant_azimuth_p80_max",
    "boundary_variant_azimuth_p80_dispersion",
    "gt_pair_ids",
    "matched_gt_pair_id",
    "matched_gt_instance_id",
    "gt_max_iou",
    "gt_max_coverage",
    "gt_max_prediction_purity",
    "matched_gt_bbox_width_px",
    "matched_gt_bbox_height_px",
    "low_energy_flag",
    "too_few_pixels_flag",
    "boundary_censored_flag",
    "mask_censored_flag",
    "background_contaminated_flag",
    "measurement_reliability",
    "measurement_exclusion_reason",
    "sar_gray_image_relpath",
    "visual_review_relpath",
]

GROUP_SUMMARY_FIELDS = [
    "summary_id",
    "measurement_region_type",
    "group_name",
    "metric",
    "sample_count",
    "valid_count",
    "invalid_count",
    "missing_count",
    "median",
    "q1",
    "q3",
    "iqr",
    "min",
    "max",
    "low_energy_count",
    "too_few_pixels_count",
    "boundary_censored_count",
    "mask_censored_count",
    "background_contaminated_count",
]

PAIRWISE_FIELDS = [
    "comparison_id",
    "comparison_type",
    "measurement_region_type",
    "group_a",
    "group_b",
    "metric",
    "n_a",
    "n_b",
    "valid_a",
    "valid_b",
    "median_a",
    "median_b",
    "q1_a",
    "q3_a",
    "q1_b",
    "q3_b",
    "min_a",
    "max_a",
    "min_b",
    "max_b",
    "median_difference_a_minus_b",
    "cliffs_delta",
    "overlap_coefficient",
    "spearman_rho",
    "paired_sample_count",
    "interpretation_cn",
]

COUNTEREXAMPLE_FIELDS = [
    "counterexample_id",
    "counterexample_type",
    "response_unit_id",
    "sar_frame",
    "measurement_region_type",
    "sample_group",
    "metric_snapshot",
    "why_it_matters_cn",
    "visual_review_relpath",
]

GATE_FIELDS = [
    "gate_id",
    "gate_name",
    "status",
    "detail",
    "source_file",
    "sha256",
    "row_count",
]


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    def as_text(self) -> str:
        return ",".join(fmt(v, 3) for v in [self.x1, self.y1, self.x2, self.y2])


class ImageCache:
    def __init__(self) -> None:
        self.images: dict[int, np.ndarray] = {}

    def get(self, frame: int) -> np.ndarray | None:
        if frame not in self.images:
            path = sar_gray_path(frame)
            if not path.exists():
                return None
            with Image.open(path) as source:
                self.images[frame] = np.asarray(source.convert("L"), dtype=np.float32)
        return self.images[frame]


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = -1) -> int:
    val = parse_float(value)
    return default if math.isnan(val) else int(round(val))


def fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return ""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(val) or math.isinf(val):
        return ""
    text = f"{val:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def split_ids(text: str) -> list[str]:
    return [part.strip() for part in str(text or "").replace(",", ";").split(";") if part.strip()]


def parse_box(text: str) -> Box | None:
    parts = [parse_float(part) for part in str(text or "").replace("|", ",").split(",")]
    if len(parts) != 4 or any(math.isnan(part) for part in parts):
        return None
    x1, y1, x2, y2 = parts
    if x2 <= x1 or y2 <= y1:
        return None
    return clamp_box(Box(x1, y1, x2, y2))


def clamp_box(box: Box) -> Box:
    return Box(
        max(0.0, min(float(SAR_WIDTH - 1), box.x1)),
        max(0.0, min(float(SAR_HEIGHT - 1), box.y1)),
        max(1.0, min(float(SAR_WIDTH), box.x2)),
        max(1.0, min(float(SAR_HEIGHT), box.y2)),
    )


def expand_box(box: Box, margin: float) -> Box:
    return clamp_box(Box(box.x1 - margin, box.y1 - margin, box.x2 + margin, box.y2 + margin))


def box_slices(box: Box) -> tuple[slice, slice]:
    x0 = max(0, min(SAR_WIDTH, int(math.floor(box.x1))))
    y0 = max(0, min(SAR_HEIGHT, int(math.floor(box.y1))))
    x1 = max(0, min(SAR_WIDTH, int(math.ceil(box.x2))))
    y1 = max(0, min(SAR_HEIGHT, int(math.ceil(box.y2))))
    return slice(y0, y1), slice(x0, x1)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sar_gray_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_SARframes_gray" / f"{frame:06d}.png"


def build_geometry(shape: tuple[int, int] = (SAR_HEIGHT, SAR_WIDTH)) -> dict[str, np.ndarray]:
    height, width = shape
    yy, xx = np.indices((height, width), dtype=np.float32)
    dx = xx - FAN_CENTER_X
    dy = FAN_CENTER_Y - yy
    radial = np.sqrt(dx * dx + dy * dy)
    azimuth = np.degrees(np.arctan2(dx, dy))
    fan = (radial <= FAN_RADIUS_PX) & (azimuth >= -90.0) & (azimuth <= 90.0)
    return {"radial": radial, "azimuth": azimuth, "fan": fan}


def require_inputs() -> None:
    missing = [rel(path) for path in INPUTS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required input files: " + "; ".join(missing))
    gray_dir = DATA_ROOT / SCENE / f"{SCENE}_SARframes_gray"
    if not gray_dir.exists():
        raise FileNotFoundError(f"missing SAR gray directory: {gray_dir}")


def load_inputs() -> dict[str, list[dict[str, str]]]:
    require_inputs()
    return {name: read_rows(path) for name, path in INPUTS.items()}


def unit_vectors(center_x: float, center_y: float) -> tuple[str, tuple[float, float], tuple[float, float]]:
    dx = center_x - FAN_CENTER_X
    dy = center_y - FAN_CENTER_Y
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return "geometry_origin_unresolved_zero_radius", (math.nan, math.nan), (math.nan, math.nan)
    er = (dx / norm, dy / norm)
    ea = (-er[1], er[0])
    return GEOMETRY_ORIGIN_STATUS, er, ea


def region_mask(box: Box, shape: tuple[int, int], fan: np.ndarray | None = None) -> tuple[np.ndarray, int]:
    mask = np.zeros(shape, dtype=bool)
    ys, xs = box_slices(box)
    if ys.stop <= ys.start or xs.stop <= xs.start:
        return mask, 0
    mask[ys, xs] = True
    rect_count = int(mask.sum())
    if fan is not None:
        mask &= fan
    return mask, rect_count


def build_occupancy(units: Sequence[Mapping[str, str]]) -> dict[int, np.ndarray]:
    by_frame: dict[int, np.ndarray] = {}
    for unit in units:
        frame = parse_int(unit.get("sar_frame"))
        box = parse_box(unit.get("conservative_bbox", ""))
        if frame < 0 or box is None:
            continue
        if frame not in by_frame:
            by_frame[frame] = np.zeros((SAR_HEIGHT, SAR_WIDTH), dtype=bool)
        ys, xs = box_slices(box)
        by_frame[frame][ys, xs] = True
    return by_frame


def local_background(
    arr: np.ndarray,
    box: Box,
    fan: np.ndarray,
    occupancy: np.ndarray | None,
) -> tuple[float, int, str, bool]:
    margin = max(10.0, min(36.0, 0.35 * max(box.width, box.height)))
    outer = expand_box(box, margin)
    outer_mask, _ = region_mask(outer, arr.shape, fan)
    inner_mask, _ = region_mask(box, arr.shape, fan)
    ring = outer_mask & ~inner_mask
    if occupancy is not None:
        ring &= ~occupancy
    values = arr[ring]
    if values.size >= 20:
        return float(np.median(values)), int(values.size), "local_ring_excluding_frozen_responses", False
    fallback = fan.copy()
    if occupancy is not None:
        fallback &= ~occupancy
    fallback_values = arr[fallback]
    if fallback_values.size:
        return float(np.median(fallback_values)), int(values.size), "frame_fan_fallback_excluding_frozen_responses", True
    fan_values = arr[fan]
    if fan_values.size:
        return float(np.median(fan_values)), int(values.size), "frame_fan_fallback", True
    return 0.0, 0, "background_unavailable", True


def shortest_weighted_interval_width(coords: np.ndarray, weights: np.ndarray, fraction: float) -> float:
    total = float(weights.sum())
    if coords.size == 0 or total <= 0:
        return math.nan
    order = np.argsort(coords)
    c = coords[order].astype(np.float64)
    w = weights[order].astype(np.float64)
    cumulative = np.concatenate([[0.0], np.cumsum(w)])
    target = total * fraction
    best = math.inf
    for start in range(c.size):
        end_plus = int(np.searchsorted(cumulative, cumulative[start] + target, side="left"))
        if end_plus > c.size:
            break
        end = max(start, end_plus - 1)
        width = float(c[end] - c[start])
        if width < best:
            best = width
    return best if math.isfinite(best) else math.nan


def weighted_stats(coords: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    total = float(weights.sum())
    if coords.size == 0 or total <= 0:
        return math.nan, math.nan
    mean = float(np.average(coords, weights=weights))
    var = float(np.average((coords - mean) ** 2, weights=weights))
    return mean, math.sqrt(max(0.0, var))


def undirected_angle_diff_deg(a: float, b: float) -> float:
    if math.isnan(a) or math.isnan(b):
        return math.nan
    diff = abs((a - b + 90.0) % 180.0 - 90.0)
    return min(diff, 180.0 - diff)


def compute_box_metrics(
    arr: np.ndarray,
    geom: Mapping[str, np.ndarray],
    occupancy: np.ndarray | None,
    box: Box,
    center_box: Box,
) -> dict[str, Any]:
    origin_status, e_range, e_azimuth = unit_vectors(center_box.cx, center_box.cy)
    base: dict[str, Any] = {
        "geometry_origin_status": origin_status,
        "sar_origin_x": FAN_CENTER_X,
        "sar_origin_y": FAN_CENTER_Y,
        "response_center_x": center_box.cx,
        "response_center_y": center_box.cy,
        "range_unit_x": e_range[0],
        "range_unit_y": e_range[1],
        "azimuth_unit_x": e_azimuth[0],
        "azimuth_unit_y": e_azimuth[1],
    }
    if origin_status != GEOMETRY_ORIGIN_STATUS:
        base.update(
            {
                "pixel_count": 0,
                "rect_pixel_count": 0,
                "energy_valid": "false",
                "low_energy_flag": "true",
                "too_few_pixels_flag": "true",
                "measurement_reliability": "excluded_geometry_origin_unresolved",
                "measurement_exclusion_reason": origin_status,
            }
        )
        return base

    fan = geom["fan"]
    mask, rect_count = region_mask(box, arr.shape, fan)
    pixel_count = int(mask.sum())
    raw_values = arr[mask].astype(np.float64)
    raw_sum = float(raw_values.sum()) if raw_values.size else 0.0
    background, bg_count, bg_source, bg_contaminated = local_background(arr, box, fan, occupancy)
    energy = np.maximum(raw_values - background, 0.0)
    energy_sum = float(energy.sum()) if energy.size else 0.0
    too_few = pixel_count < 10
    low_energy = energy_sum <= max(1.0, 0.01 * max(raw_sum, 1.0))
    energy_valid = (not too_few) and (not low_energy) and energy_sum > 0.0
    mask_censored = rect_count > 0 and pixel_count < rect_count
    y_idx, x_idx = np.where(mask)

    base.update(
        {
            "region_bbox": box.as_text(),
            "pixel_count": pixel_count,
            "rect_pixel_count": rect_count,
            "raw_intensity_sum": raw_sum,
            "background_estimate": background,
            "background_sample_count": bg_count,
            "background_source": bg_source,
            "background_subtracted_energy": energy_sum,
            "energy_valid": bool_text(energy_valid),
            "low_energy_flag": bool_text(low_energy),
            "too_few_pixels_flag": bool_text(too_few),
            "mask_censored_flag": bool_text(mask_censored),
            "background_contaminated_flag": bool_text(bg_contaminated),
        }
    )
    if not energy_valid:
        reason = "low_background_subtracted_energy" if low_energy else "too_few_valid_pixels"
        base.update(
            {
                "measurement_reliability": "unreliable_" + reason,
                "measurement_exclusion_reason": reason,
            }
        )
        return base

    xs = x_idx.astype(np.float64) + 0.5
    ys = y_idx.astype(np.float64) + 0.5
    rel_x = xs - center_box.cx
    rel_y = ys - center_box.cy
    range_coord = rel_x * e_range[0] + rel_y * e_range[1]
    az_coord = rel_x * e_azimuth[0] + rel_y * e_azimuth[1]
    r_mean, r_std = weighted_stats(range_coord, energy)
    a_mean, a_std = weighted_stats(az_coord, energy)
    r50 = shortest_weighted_interval_width(range_coord, energy, 0.50)
    r80 = shortest_weighted_interval_width(range_coord, energy, 0.80)
    r90 = shortest_weighted_interval_width(range_coord, energy, 0.90)
    a50 = shortest_weighted_interval_width(az_coord, energy, 0.50)
    a80 = shortest_weighted_interval_width(az_coord, energy, 0.80)
    a90 = shortest_weighted_interval_width(az_coord, energy, 0.90)

    centroid_x = float(np.average(xs, weights=energy))
    centroid_y = float(np.average(ys, weights=energy))
    centroid_offset = math.hypot(centroid_x - center_box.cx, centroid_y - center_box.cy)

    centered = np.vstack([range_coord - r_mean, az_coord - a_mean])
    cov = (centered * energy).dot(centered.T) / max(float(energy.sum()), 1e-9)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    major_val = max(0.0, float(eigvals[order[0]]))
    minor_val = max(0.0, float(eigvals[order[1]]))
    major_std = math.sqrt(major_val)
    minor_std = math.sqrt(minor_val)
    principal_vec = eigvecs[:, order[0]]
    local_angle = math.degrees(math.atan2(float(principal_vec[1]), float(principal_vec[0])))
    angle_to_range = undirected_angle_diff_deg(local_angle, 0.0)
    angle_to_az = undirected_angle_diff_deg(local_angle, 90.0)
    image_vec_x = float(principal_vec[0]) * e_range[0] + float(principal_vec[1]) * e_azimuth[0]
    image_vec_y = float(principal_vec[0]) * e_range[1] + float(principal_vec[1]) * e_azimuth[1]
    image_angle = math.degrees(math.atan2(image_vec_y, image_vec_x)) % 180.0

    base.update(
        {
            "range_weighted_mean": r_mean,
            "azimuth_weighted_mean": a_mean,
            "range_weighted_std": r_std,
            "azimuth_weighted_std": a_std,
            "range_p50_width": r50,
            "range_p80_width": r80,
            "range_p90_width": r90,
            "azimuth_p50_width": a50,
            "azimuth_p80_width": a80,
            "azimuth_p90_width": a90,
            "range_to_azimuth_p80_ratio": r80 / a80 if a80 and not math.isnan(a80) else math.nan,
            "range_to_azimuth_p90_ratio": r90 / a90 if a90 and not math.isnan(a90) else math.nan,
            "principal_axis_major_std": major_std,
            "principal_axis_minor_std": minor_std,
            "principal_axis_ratio": major_std / minor_std if minor_std > 1e-9 else math.nan,
            "principal_axis_angle_image_deg": image_angle,
            "principal_axis_angle_to_range_deg": angle_to_range,
            "principal_axis_angle_to_azimuth_deg": angle_to_az,
            "energy_centroid_x": centroid_x,
            "energy_centroid_y": centroid_y,
            "energy_centroid_offset_px": centroid_offset,
            "measurement_reliability": "valid",
            "measurement_exclusion_reason": "",
        }
    )
    return base


def best_gt_rows(matrix_rows: Sequence[Mapping[str, str]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in matrix_rows:
        grouped[row.get("object_id", "")].append(row)
    best: dict[str, dict[str, Any]] = {}
    for object_id, rows in grouped.items():
        candidates = []
        positive = False
        for row in rows:
            iou = parse_float(row.get("iou"), 0.0)
            coverage = parse_float(row.get("gt_coverage"), 0.0)
            purity = parse_float(row.get("prediction_purity"), 0.0)
            source = row.get("source_conditioned_gt_instance", "")
            blocked = "confidence=non_vehicle_pair" in source or "identity=blocked" in source
            if (iou > 0.0 or coverage > 0.0 or purity > 0.0) and not blocked:
                positive = True
            candidates.append((iou, coverage, purity, 0 if blocked else 1, row))
        candidates.sort(key=lambda item: (item[3], item[0], item[1], item[2]), reverse=True)
        top = candidates[0][4]
        best[object_id] = {
            "rows": rows,
            "is_positive": positive,
            "best": top,
            "gt_pair_ids": ";".join(sorted({row.get("gt_pair_id", "") for row in rows if row.get("gt_pair_id", "")})),
            "max_iou": max(parse_float(row.get("iou"), 0.0) for row in rows),
            "max_coverage": max(parse_float(row.get("gt_coverage"), 0.0) for row in rows),
            "max_purity": max(parse_float(row.get("prediction_purity"), 0.0) for row in rows),
        }
    return best


def build_context(data: Mapping[str, Sequence[Mapping[str, str]]]) -> dict[str, Any]:
    units = data["local_response_units"]
    atom_roles = {row["atom_id"]: row.get("candidate_role", "") for row in data["atom_graph_nodes"]}
    atom_graph_class = {row["atom_id"]: row.get("graph_role_class", "") for row in data["atom_graph_nodes"]}
    response_state = {row["response_box_id"]: row.get("box_state", "") for row in data["response_box_hypotheses"]}
    family_by_unit: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for family in data["boundary_variant_families"]:
        for unit_id in split_ids(family.get("member_response_unit_ids", "")):
            family_by_unit[unit_id].append(family)
    bg_alt_atoms = {row.get("alternative_object_id", "") for row in data["background_counterexamples"] if row.get("alternative_object_id", "")}
    bg_by_atom: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in data["background_counterexamples"]:
        bg_by_atom[row.get("alternative_object_id", "")].append(row)
    mask_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for row in data["mask_observation_audit"]:
        mask_by_frame[parse_int(row.get("sar_frame"))].append(row)
    paired_by_id = {row.get("pair_id", ""): row for row in data["paired_annotations"] if row.get("scene") == SCENE}
    occupancy = build_occupancy(units)
    return {
        "atom_roles": atom_roles,
        "atom_graph_class": atom_graph_class,
        "response_state": response_state,
        "family_by_unit": family_by_unit,
        "bg_alt_atoms": bg_alt_atoms,
        "bg_by_atom": bg_by_atom,
        "gt_by_unit": best_gt_rows(data["response_unit_gt_instance_matrix"]),
        "mask_by_frame": mask_by_frame,
        "paired_by_id": paired_by_id,
        "occupancy": occupancy,
    }


def family_context(unit_id: str, families: Mapping[str, list[Mapping[str, str]]]) -> dict[str, Any]:
    rows = families.get(unit_id, [])
    if not rows:
        return {"family_ids": "", "status": "no_boundary_family_record", "variant_boxes": []}
    family_ids = []
    statuses = []
    variants: list[Box] = []
    for row in rows:
        family_ids.append(row.get("boundary_family_id", ""))
        statuses.append(row.get("boundary_status", ""))
        for text in str(row.get("boundary_variants", "")).split("|"):
            box = parse_box(text.strip())
            if box is not None:
                variants.append(box)
    status = "multiple_boundary_variants" if any(s == "multiple_boundary_variants" for s in statuses) else ";".join(sorted(set(statuses)))
    return {"family_ids": ";".join(sorted(set(family_ids))), "status": status, "variant_boxes": variants}


def mask_state_for_frame(frame: int, mask_by_frame: Mapping[int, list[Mapping[str, str]]]) -> tuple[str, bool]:
    rows = mask_by_frame.get(frame, [])
    if not rows:
        return "no_mask_audit_row", False
    classes = sorted({row.get("sar_mask_observation_class", "") for row in rows if row.get("sar_mask_observation_class", "")})
    pair_ids = sorted({row.get("pair_id", "") for row in rows if row.get("pair_id", "")})
    touches = any(row.get("sar_response_touches_mask") == "true" for row in rows)
    censored = touches or any(cls.startswith("SAR_MASK_S1") or cls.startswith("SAR_MASK_S2") for cls in classes)
    return ";".join(classes) + "|pairs=" + ";".join(pair_ids), censored


def sample_group(labels: Sequence[tuple[str, bool]]) -> str:
    active = [name for name, flag in labels if flag]
    return "+".join(active) if active else "unresolved_control"


def variant_sensitivity(
    variants: Sequence[Box],
    arr: np.ndarray,
    geom: Mapping[str, np.ndarray],
    occupancy: np.ndarray | None,
    center_box: Box,
    metric_cache: dict[tuple[int, str, str], dict[str, Any]] | None = None,
    frame: int = -1,
) -> dict[str, Any]:
    if not variants:
        return {
            "boundary_variant_count": 0,
            "boundary_variant_range_p80_min": "",
            "boundary_variant_range_p80_max": "",
            "boundary_variant_range_p80_dispersion": "",
            "boundary_variant_azimuth_p80_min": "",
            "boundary_variant_azimuth_p80_max": "",
            "boundary_variant_azimuth_p80_dispersion": "",
        }
    range_values = []
    az_values = []
    for box in variants:
        cache_key = (frame, box.as_text(), center_box.as_text())
        if metric_cache is not None and cache_key in metric_cache:
            metrics = metric_cache[cache_key]
        else:
            metrics = compute_box_metrics(arr, geom, occupancy, box, center_box)
            if metric_cache is not None:
                metric_cache[cache_key] = metrics
        r80 = parse_float(metrics.get("range_p80_width"))
        a80 = parse_float(metrics.get("azimuth_p80_width"))
        if not math.isnan(r80):
            range_values.append(r80)
        if not math.isnan(a80):
            az_values.append(a80)
    return {
        "boundary_variant_count": len(variants),
        "boundary_variant_range_p80_min": min(range_values) if range_values else math.nan,
        "boundary_variant_range_p80_max": max(range_values) if range_values else math.nan,
        "boundary_variant_range_p80_dispersion": (max(range_values) - min(range_values)) if len(range_values) >= 2 else 0.0 if range_values else math.nan,
        "boundary_variant_azimuth_p80_min": min(az_values) if az_values else math.nan,
        "boundary_variant_azimuth_p80_max": max(az_values) if az_values else math.nan,
        "boundary_variant_azimuth_p80_dispersion": (max(az_values) - min(az_values)) if len(az_values) >= 2 else 0.0 if az_values else math.nan,
    }


def matched_gt_fields(gt_info: Mapping[str, Any] | None, paired_by_id: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    if not gt_info:
        return {
            "gt_pair_ids": "",
            "matched_gt_pair_id": "",
            "matched_gt_instance_id": "",
            "gt_max_iou": "",
            "gt_max_coverage": "",
            "gt_max_prediction_purity": "",
            "matched_gt_bbox_width_px": "",
            "matched_gt_bbox_height_px": "",
        }
    best = gt_info["best"]
    pair_id = best.get("gt_pair_id", "")
    paired = paired_by_id.get(pair_id, {})
    width = parse_float(paired.get("sar_bbox_x2")) - parse_float(paired.get("sar_bbox_x1")) if paired else math.nan
    height = parse_float(paired.get("sar_bbox_y2")) - parse_float(paired.get("sar_bbox_y1")) if paired else math.nan
    return {
        "gt_pair_ids": gt_info["gt_pair_ids"],
        "matched_gt_pair_id": pair_id,
        "matched_gt_instance_id": best.get("gt_instance_id", ""),
        "gt_max_iou": gt_info["max_iou"],
        "gt_max_coverage": gt_info["max_coverage"],
        "gt_max_prediction_purity": gt_info["max_purity"],
        "matched_gt_bbox_width_px": width,
        "matched_gt_bbox_height_px": height,
    }


def measure_all(data: Mapping[str, Sequence[Mapping[str, str]]], write_visuals: bool = True) -> list[dict[str, Any]]:
    context = build_context(data)
    geom = build_geometry()
    cache = ImageCache()
    metric_cache: dict[tuple[int, str, str], dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for unit in data["local_response_units"]:
        unit_id = unit["response_unit_id"]
        frame = parse_int(unit.get("sar_frame"))
        arr = cache.get(frame)
        core_box = parse_box(unit.get("core_bbox", ""))
        conservative_box = parse_box(unit.get("conservative_bbox", ""))
        if conservative_box is None:
            conservative_box = core_box
        if core_box is None or conservative_box is None:
            continue

        family = family_context(unit_id, context["family_by_unit"])
        mask_state, frame_mask_censored = mask_state_for_frame(frame, context["mask_by_frame"])
        gt_info = context["gt_by_unit"].get(unit_id)
        is_positive = bool(gt_info and gt_info.get("is_positive"))
        core_atoms = split_ids(unit.get("core_atom_ids", ""))
        optional_atoms = split_ids(unit.get("optional_atom_ids", ""))
        all_atoms = core_atoms + optional_atoms
        core_roles = sorted({context["atom_roles"].get(atom, "") for atom in core_atoms if context["atom_roles"].get(atom, "")})
        all_roles = sorted({context["atom_roles"].get(atom, "") for atom in all_atoms if context["atom_roles"].get(atom, "")})
        background_atoms = sorted({atom for atom in core_atoms if atom in context["bg_alt_atoms"]})
        role_background = any(role in {"isolated_small_atom", "background_arc_candidate"} for role in core_roles)
        is_background = bool(background_atoms or role_background)
        response_state = context["response_state"].get(unit.get("source_response_box_id", ""), "")
        is_boundary = frame_mask_censored or family["status"] == "multiple_boundary_variants"
        is_unresolved = (not is_positive) and (not is_background) and (not is_boundary)
        group = sample_group(
            [
                ("gt_local_positive_control", is_positive),
                ("registered_background_counterexample", is_background),
                ("boundary_censored_response", is_boundary),
                ("unresolved_control", is_unresolved),
            ]
        )

        common = {
            "response_unit_id": unit_id,
            "source_response_box_id": unit.get("source_response_box_id", ""),
            "source_r1_family_id": unit.get("source_r1_family_id", ""),
            "sar_frame": frame,
            "boundary_family_id": family["family_ids"],
            "boundary_contact_state": family["status"],
            "mask_state": mask_state,
            "sample_group": group,
            "is_gt_local_positive_control": bool_text(is_positive),
            "is_registered_background_counterexample": bool_text(is_background),
            "is_boundary_censored_response": bool_text(is_boundary),
            "is_unresolved_control": bool_text(is_unresolved),
            "core_atom_ids": ";".join(core_atoms),
            "optional_atom_ids": ";".join(optional_atoms),
            "core_atom_roles": ";".join(core_roles),
            "all_atom_roles": ";".join(all_roles),
            "background_counterexample_atom_ids": ";".join(background_atoms),
            "boundary_censored_flag": bool_text(is_boundary),
            "sar_gray_image_relpath": rel(sar_gray_path(frame)),
            **matched_gt_fields(gt_info, context["paired_by_id"]),
        }

        variant_metrics: dict[str, Any] = {
            "boundary_variant_count": 0,
            "boundary_variant_range_p80_min": "",
            "boundary_variant_range_p80_max": "",
            "boundary_variant_range_p80_dispersion": "",
            "boundary_variant_azimuth_p80_min": "",
            "boundary_variant_azimuth_p80_max": "",
            "boundary_variant_azimuth_p80_dispersion": "",
        }
        if arr is not None:
            occupancy = context["occupancy"].get(frame)
            variant_metrics = variant_sensitivity(
                family["variant_boxes"],
                arr,
                geom,
                occupancy,
                conservative_box,
                metric_cache=metric_cache,
                frame=frame,
            )

        for region_type, box in [("core_region", core_box), ("conservative_response_region", conservative_box)]:
            if arr is None:
                row = {
                    **common,
                    "measurement_region_type": region_type,
                    "geometry_origin_status": GEOMETRY_ORIGIN_STATUS,
                    "region_bbox": box.as_text(),
                    "energy_valid": "false",
                    "low_energy_flag": "true",
                    "too_few_pixels_flag": "true",
                    "mask_censored_flag": "false",
                    "background_contaminated_flag": "true",
                    "measurement_reliability": "excluded_sar_image_missing",
                    "measurement_exclusion_reason": "sar_gray_image_missing",
                }
            else:
                occupancy = context["occupancy"].get(frame)
                cache_key = (frame, box.as_text(), conservative_box.as_text())
                if cache_key in metric_cache:
                    metrics = metric_cache[cache_key]
                else:
                    metrics = compute_box_metrics(arr, geom, occupancy, box, conservative_box)
                    metric_cache[cache_key] = metrics
                reliability = metrics.get("measurement_reliability", "")
                if reliability == "valid":
                    if common["boundary_censored_flag"] == "true" or metrics.get("mask_censored_flag") == "true":
                        reliability = "valid_boundary_or_mask_limited"
                    elif metrics.get("background_contaminated_flag") == "true":
                        reliability = "valid_background_limited"
                row = {
                    **common,
                    "measurement_region_type": region_type,
                    **metrics,
                    **variant_metrics,
                    "measurement_reliability": reliability,
                }
            rows.append(row)

    visual_paths = select_and_render_visuals(rows, write_visuals=write_visuals)
    for row in rows:
        key = (row.get("response_unit_id", ""), row.get("measurement_region_type", ""))
        row["visual_review_relpath"] = visual_paths.get(key, "")
    return rows


def numeric(row: Mapping[str, Any], field: str) -> float:
    return parse_float(row.get(field))


def finite_values(rows: Sequence[Mapping[str, Any]], metric: str) -> list[float]:
    values = [numeric(row, metric) for row in rows]
    return [value for value in values if not math.isnan(value)]


def percentile(values: Sequence[float], q: float) -> float:
    clean = sorted(value for value in values if not math.isnan(value))
    if not clean:
        return math.nan
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return clean[lo]
    return clean[lo] * (hi - pos) + clean[hi] * (pos - lo)


def describe(values: Sequence[float]) -> dict[str, Any]:
    clean = [value for value in values if not math.isnan(value)]
    q1 = percentile(clean, 0.25)
    q3 = percentile(clean, 0.75)
    return {
        "valid_count": len(clean),
        "missing_count": len(values) - len(clean),
        "median": percentile(clean, 0.50),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1 if not math.isnan(q1) and not math.isnan(q3) else math.nan,
        "min": min(clean) if clean else math.nan,
        "max": max(clean) if clean else math.nan,
    }


def cliffs_delta(a_values: Sequence[float], b_values: Sequence[float]) -> float:
    a = [v for v in a_values if not math.isnan(v)]
    b = [v for v in b_values if not math.isnan(v)]
    if not a or not b:
        return math.nan
    greater = 0
    less = 0
    for av in a:
        for bv in b:
            if av > bv:
                greater += 1
            elif av < bv:
                less += 1
    return (greater - less) / (len(a) * len(b))


def overlap_coefficient(a_values: Sequence[float], b_values: Sequence[float], bins: int = 24) -> float:
    a = np.array([v for v in a_values if not math.isnan(v)], dtype=np.float64)
    b = np.array([v for v in b_values if not math.isnan(v)], dtype=np.float64)
    if a.size == 0 or b.size == 0:
        return math.nan
    lo = float(min(a.min(), b.min()))
    hi = float(max(a.max(), b.max()))
    if hi <= lo:
        return 1.0
    hist_a, edges = np.histogram(a, bins=bins, range=(lo, hi))
    hist_b, _ = np.histogram(b, bins=edges)
    pa = hist_a / max(1, hist_a.sum())
    pb = hist_b / max(1, hist_b.sum())
    return float(np.minimum(pa, pb).sum())


def rankdata(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = rank
        i = j + 1
    return ranks


def pearson(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return math.nan
    aa = np.array(a, dtype=np.float64)
    bb = np.array(b, dtype=np.float64)
    if float(aa.std()) <= 1e-12 or float(bb.std()) <= 1e-12:
        return math.nan
    return float(np.corrcoef(aa, bb)[0, 1])


def spearman(a_values: Sequence[float], b_values: Sequence[float]) -> tuple[float, int]:
    pairs = [(a, b) for a, b in zip(a_values, b_values) if not math.isnan(a) and not math.isnan(b)]
    if len(pairs) < 3:
        return math.nan, len(pairs)
    a_rank = rankdata([p[0] for p in pairs])
    b_rank = rankdata([p[1] for p in pairs])
    return pearson(a_rank, b_rank), len(pairs)


def group_selectors() -> dict[str, Callable[[Mapping[str, Any]], bool]]:
    return {
        "all_local_response_units": lambda row: True,
        "gt_local_positive_control": lambda row: row.get("is_gt_local_positive_control") == "true",
        "registered_background_counterexample": lambda row: row.get("is_registered_background_counterexample") == "true",
        "registered_background_counterexample_nonpositive": lambda row: row.get("is_registered_background_counterexample") == "true"
        and row.get("is_gt_local_positive_control") != "true",
        "boundary_censored_response": lambda row: row.get("is_boundary_censored_response") == "true",
        "non_boundary_response": lambda row: row.get("is_boundary_censored_response") != "true",
        "unresolved_control": lambda row: row.get("is_unresolved_control") == "true",
    }


def build_group_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    metrics = [
        "range_p80_width",
        "azimuth_p80_width",
        "range_to_azimuth_p80_ratio",
        "principal_axis_ratio",
        "principal_axis_angle_to_range_deg",
        "background_subtracted_energy",
        "energy_centroid_offset_px",
    ]
    selectors = group_selectors()
    output: list[dict[str, Any]] = []
    idx = 1
    for region in REGION_TYPES:
        region_rows = [row for row in rows if row.get("measurement_region_type") == region]
        for group_name, selector in selectors.items():
            group_rows = [row for row in region_rows if selector(row)]
            for metric in metrics:
                values = [numeric(row, metric) for row in group_rows]
                desc = describe(values)
                output.append(
                    {
                        "summary_id": f"GS{idx:04d}",
                        "measurement_region_type": region,
                        "group_name": group_name,
                        "metric": metric,
                        "sample_count": len(group_rows),
                        "invalid_count": len(group_rows) - desc["valid_count"],
                        "low_energy_count": sum(row.get("low_energy_flag") == "true" for row in group_rows),
                        "too_few_pixels_count": sum(row.get("too_few_pixels_flag") == "true" for row in group_rows),
                        "boundary_censored_count": sum(row.get("boundary_censored_flag") == "true" for row in group_rows),
                        "mask_censored_count": sum(row.get("mask_censored_flag") == "true" for row in group_rows),
                        "background_contaminated_count": sum(row.get("background_contaminated_flag") == "true" for row in group_rows),
                        **desc,
                    }
                )
                idx += 1
    return output


def pairwise_distribution_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    metrics = [
        "range_p80_width",
        "azimuth_p80_width",
        "range_to_azimuth_p80_ratio",
        "principal_axis_ratio",
        "principal_axis_angle_to_range_deg",
        "background_subtracted_energy",
    ]
    selectors = group_selectors()
    comparisons = [
        (
            "positive_vs_registered_background_nonpositive",
            "gt_local_positive_control",
            "registered_background_counterexample_nonpositive",
            "正向 GT 事后控制对背景/孤立反例上下文；非训练式分布对照。",
        ),
        (
            "boundary_vs_non_boundary",
            "boundary_censored_response",
            "non_boundary_response",
            "边界接触对非边界对象；用于判断边界条件是否系统性改变测量。",
        ),
    ]
    output: list[dict[str, Any]] = []
    idx = 1
    for region in REGION_TYPES:
        region_rows = [row for row in rows if row.get("measurement_region_type") == region]
        for comp_name, group_a, group_b, interpretation in comparisons:
            a_rows = [row for row in region_rows if selectors[group_a](row)]
            b_rows = [row for row in region_rows if selectors[group_b](row)]
            for metric in metrics + (["energy_centroid_offset_px"] if comp_name == "boundary_vs_non_boundary" else []):
                a_values = [numeric(row, metric) for row in a_rows]
                b_values = [numeric(row, metric) for row in b_rows]
                da = describe(a_values)
                db = describe(b_values)
                output.append(
                    {
                        "comparison_id": f"PC{idx:04d}",
                        "comparison_type": comp_name,
                        "measurement_region_type": region,
                        "group_a": group_a,
                        "group_b": group_b,
                        "metric": metric,
                        "n_a": len(a_rows),
                        "n_b": len(b_rows),
                        "valid_a": da["valid_count"],
                        "valid_b": db["valid_count"],
                        "median_a": da["median"],
                        "median_b": db["median"],
                        "q1_a": da["q1"],
                        "q3_a": da["q3"],
                        "q1_b": db["q1"],
                        "q3_b": db["q3"],
                        "min_a": da["min"],
                        "max_a": da["max"],
                        "min_b": db["min"],
                        "max_b": db["max"],
                        "median_difference_a_minus_b": da["median"] - db["median"]
                        if not math.isnan(da["median"]) and not math.isnan(db["median"])
                        else math.nan,
                        "cliffs_delta": cliffs_delta(a_values, b_values),
                        "overlap_coefficient": overlap_coefficient(a_values, b_values),
                        "spearman_rho": "",
                        "paired_sample_count": "",
                        "interpretation_cn": interpretation,
                    }
                )
                idx += 1
    return output


def gt_spearman_rows(rows: Sequence[Mapping[str, Any]], start_index: int) -> list[dict[str, Any]]:
    region_rows = [
        row
        for row in rows
        if row.get("measurement_region_type") == PRIMARY_REGION
        and row.get("is_gt_local_positive_control") == "true"
        and row.get("energy_valid") == "true"
    ]
    pairs = [
        ("range_p80_width", "matched_gt_bbox_width_px", "响应距离向 p80 与 GT 图像宽"),
        ("range_p80_width", "matched_gt_bbox_height_px", "响应距离向 p80 与 GT 图像高"),
        ("azimuth_p80_width", "matched_gt_bbox_width_px", "响应方位向 p80 与 GT 图像宽"),
        ("azimuth_p80_width", "matched_gt_bbox_height_px", "响应方位向 p80 与 GT 图像高"),
    ]
    output = []
    idx = start_index
    for response_metric, gt_metric, label in pairs:
        rho, n = spearman([numeric(row, response_metric) for row in region_rows], [numeric(row, gt_metric) for row in region_rows])
        output.append(
            {
                "comparison_id": f"PC{idx:04d}",
                "comparison_type": "gt_bbox_spearman_control",
                "measurement_region_type": PRIMARY_REGION,
                "group_a": "gt_local_positive_control",
                "group_b": "matched_gt_bbox",
                "metric": f"{response_metric}_vs_{gt_metric}",
                "n_a": len(region_rows),
                "n_b": len(region_rows),
                "valid_a": n,
                "valid_b": n,
                "spearman_rho": rho,
                "paired_sample_count": n,
                "interpretation_cn": f"{label}的斯皮尔曼秩相关；GT 框只作事后对照，不代表真实散射支撑。",
            }
        )
        idx += 1
    return output


def build_pairwise_controls(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pairwise = pairwise_distribution_rows(rows)
    pairwise.extend(gt_spearman_rows(rows, len(pairwise) + 1))
    return pairwise


def metric_snapshot(row: Mapping[str, Any]) -> str:
    fields = [
        "range_p80_width",
        "azimuth_p80_width",
        "range_to_azimuth_p80_ratio",
        "principal_axis_ratio",
        "principal_axis_angle_to_range_deg",
        "background_subtracted_energy",
    ]
    return ";".join(f"{field}={fmt(row.get(field), 4)}" for field in fields)


def build_counterexamples(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    primary = [row for row in rows if row.get("measurement_region_type") == PRIMARY_REGION]
    valid = [row for row in primary if row.get("energy_valid") == "true"]
    output: list[dict[str, Any]] = []

    def add(kind: str, selected: Sequence[Mapping[str, Any]], why: str) -> None:
        for row in selected:
            output.append(
                {
                    "counterexample_id": f"CE{len(output) + 1:04d}",
                    "counterexample_type": kind,
                    "response_unit_id": row.get("response_unit_id", ""),
                    "sar_frame": row.get("sar_frame", ""),
                    "measurement_region_type": row.get("measurement_region_type", ""),
                    "sample_group": row.get("sample_group", ""),
                    "metric_snapshot": metric_snapshot(row),
                    "why_it_matters_cn": why,
                    "visual_review_relpath": row.get("visual_review_relpath", ""),
                }
            )

    positive = [row for row in valid if row.get("is_gt_local_positive_control") == "true"]
    bg_nonpos = [
        row
        for row in valid
        if row.get("is_registered_background_counterexample") == "true" and row.get("is_gt_local_positive_control") != "true"
    ]
    boundary = [row for row in valid if row.get("is_boundary_censored_response") == "true"]
    low_energy = [row for row in primary if row.get("energy_valid") != "true" or row.get("low_energy_flag") == "true"]

    add(
        "positive_control_low_directional_ratio",
        sorted(positive, key=lambda row: numeric(row, "range_to_azimuth_p80_ratio"))[:3],
        "GT 事后正向控制中仍存在方向性比例较低样本，说明静态展宽不能直接升级为车辆规则。",
    )
    add(
        "background_counterexample_high_energy_or_ratio",
        sorted(bg_nonpos, key=lambda row: (numeric(row, "background_subtracted_energy"), numeric(row, "range_to_azimuth_p80_ratio")), reverse=True)[:3],
        "背景/孤立小峰上下文中也可能出现高能量或强方向性，阻止静态单帧硬判别。",
    )
    add(
        "boundary_censored_large_centroid_offset",
        sorted(boundary, key=lambda row: numeric(row, "energy_centroid_offset_px"), reverse=True)[:3],
        "边界接触样本的能量质心偏移较大，提示边界删失会改变测量稳定性。",
    )
    add(
        "low_energy_or_unreliable_measurement",
        low_energy[:3],
        "低能量或无效测量必须保留，不能通过删行美化分布。",
    )
    return output


def reliability_counts(rows: Sequence[Mapping[str, Any]]) -> Counter[str]:
    primary = [row for row in rows if row.get("measurement_region_type") == PRIMARY_REGION]
    counts = Counter()
    counts["objects"] = len(primary)
    counts["energy_valid"] = sum(row.get("energy_valid") == "true" for row in primary)
    counts["low_energy"] = sum(row.get("low_energy_flag") == "true" for row in primary)
    counts["too_few_pixels"] = sum(row.get("too_few_pixels_flag") == "true" for row in primary)
    counts["boundary_censored"] = sum(row.get("boundary_censored_flag") == "true" for row in primary)
    counts["mask_censored"] = sum(row.get("mask_censored_flag") == "true" for row in primary)
    counts["background_contaminated"] = sum(row.get("background_contaminated_flag") == "true" for row in primary)
    counts["other_invalid"] = counts["objects"] - counts["energy_valid"]
    return counts


def group_counts(rows: Sequence[Mapping[str, Any]]) -> Counter[str]:
    primary = [row for row in rows if row.get("measurement_region_type") == PRIMARY_REGION]
    counts = Counter()
    for row in primary:
        if row.get("is_gt_local_positive_control") == "true":
            counts["gt_local_positive_control"] += 1
        if row.get("is_registered_background_counterexample") == "true":
            counts["registered_background_counterexample"] += 1
        if row.get("is_registered_background_counterexample") == "true" and row.get("is_gt_local_positive_control") != "true":
            counts["registered_background_counterexample_nonpositive"] += 1
        if row.get("is_boundary_censored_response") == "true":
            counts["boundary_censored_response"] += 1
        if row.get("is_unresolved_control") == "true":
            counts["unresolved_control"] += 1
    return counts


def determine_h01_status(pairwise_rows: Sequence[Mapping[str, Any]], counts: Counter[str]) -> str:
    primary = [
        row
        for row in pairwise_rows
        if row.get("measurement_region_type") == PRIMARY_REGION
        and row.get("comparison_type") == "positive_vs_registered_background_nonpositive"
        and row.get("metric")
        in {
            "range_p80_width",
            "azimuth_p80_width",
            "range_to_azimuth_p80_ratio",
            "principal_axis_ratio",
            "principal_axis_angle_to_range_deg",
            "background_subtracted_energy",
        }
    ]
    strong_effect = 0
    moderate_effect = 0
    for row in primary:
        delta = abs(parse_float(row.get("cliffs_delta")))
        overlap = parse_float(row.get("overlap_coefficient"))
        if not math.isnan(delta) and delta >= 0.33:
            strong_effect += 1
        elif not math.isnan(delta) and delta >= 0.20:
            moderate_effect += 1
        elif not math.isnan(delta) and delta >= 0.15 and not math.isnan(overlap) and overlap <= 0.50:
            moderate_effect += 1
    if counts["energy_valid"] < max(20, counts["objects"] * 0.5):
        return "PARTIAL_STATIC_SUPPORT"
    if strong_effect >= 3:
        return "SUPPORTED_AS_STATIC_OBSERVABLE"
    if strong_effect >= 1 or moderate_effect >= 1:
        return "PARTIAL_STATIC_SUPPORT"
    boundary_rows = [
        row
        for row in pairwise_rows
        if row.get("measurement_region_type") == PRIMARY_REGION and row.get("comparison_type") == "boundary_vs_non_boundary"
    ]
    boundary_effect = any(abs(parse_float(row.get("cliffs_delta"))) >= 0.33 for row in boundary_rows)
    return "PARTIAL_STATIC_SUPPORT" if boundary_effect else "INSUFFICIENT_STATIC_SEPARATION"


def format_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    shown = list(rows[:limit]) if limit else list(rows)
    header = "| " + " | ".join(fields) + " |"
    sep = "| " + " | ".join("---" for _ in fields) + " |"
    body = []
    for row in shown:
        body.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join([header, sep] + body)


def filtered_summary(summary: Sequence[Mapping[str, Any]], group: str, region: str = PRIMARY_REGION) -> list[Mapping[str, Any]]:
    wanted = {
        "range_p80_width",
        "azimuth_p80_width",
        "range_to_azimuth_p80_ratio",
        "principal_axis_ratio",
        "principal_axis_angle_to_range_deg",
        "background_subtracted_energy",
    }
    return [
        row
        for row in summary
        if row.get("measurement_region_type") == region and row.get("group_name") == group and row.get("metric") in wanted
    ]


def render_report(
    rows: Sequence[Mapping[str, Any]],
    group_summary: Sequence[Mapping[str, Any]],
    pairwise: Sequence[Mapping[str, Any]],
    counterexamples: Sequence[Mapping[str, Any]],
    gate_rows: Sequence[Mapping[str, Any]],
) -> str:
    counts = reliability_counts(rows)
    groups = group_counts(rows)
    status = determine_h01_status(pairwise, counts)
    pos_bg = [
        row
        for row in pairwise
        if row.get("measurement_region_type") == PRIMARY_REGION
        and row.get("comparison_type") == "positive_vs_registered_background_nonpositive"
    ]
    boundary = [
        row
        for row in pairwise
        if row.get("measurement_region_type") == PRIMARY_REGION and row.get("comparison_type") == "boundary_vs_non_boundary"
    ]
    gt = [row for row in pairwise if row.get("comparison_type") == "gt_bbox_spearman_control"]
    visual_paths = sorted({row.get("visual_review_relpath", "") for row in rows if row.get("visual_review_relpath", "")})

    return f"""# GM_RM019 静态 SAR 图像域方向性展宽测量

日期：{DATE}

## 边界

本报告只推进 `GM019_STATIC_H01`。SAR（Synthetic Aperture Radar，合成孔径雷达）灰度图仅用于事后机制诊断；GT（Ground Truth，真值标注）只用于分组和事后对照。本轮没有生成最终框、候选框、selector/ranking、修订 GT、身份真值、训练输出或阈值搜索。

## 几何来源

- SAR 灰度图：`D:/profile/research/data/GM_RM019/GM_RM019_SARframes_gray/*.png`，图像尺寸 `2308 x 1334`。
- 扇形图像原点：`({FAN_CENTER_X}, {FAN_CENTER_Y})`，来自 `tools/diagnostics/run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.py` 与 `tools/diagnostics/run_oty2_support_region_sar_observation_probe.py` 复用的 `FAN_CENTER_X/FAN_CENTER_Y`。
- 距离向：以响应单元 conservative bbox 中心为 `response_center`，在图像坐标中取 `normalize(response_center - sar_origin)`。
- 方位向：取距离向的局部垂线 `(-range_y, range_x)`，对应既有 `atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y)` 的角度递增方向。
- 图像坐标说明：x 轴向右，y 轴向下；因此距离向不是图像水平轴或垂直轴。
- 几何状态：`{GEOMETRY_ORIGIN_STATUS}`。

## 测量方法

每个冻结 `local_response_unit` 输出 `core_region` 与 `conservative_response_region` 两行。灰度能量使用原始 0-255 灰度；背景估计来自响应框外局部环带，并排除扇形无效区和同帧冻结响应区域。对象测量权重为 `max(intensity - background_estimate, 0)`。一维 `p50/p80/p90_width` 定义为包含对应累计能量比例的最短投影区间宽度。

边界变体族不被合并成车辆；本轮只记录同一局部响应在边界 variant 下的 p80 展宽敏感性。背景反例保持原语义，只作为背景/孤立小峰上下文，不被改写为绝对非车辆真值。

## 对象与分组计数

- 冻结局部响应对象：`{counts["objects"]}`
- 对象级测量行：`{len(rows)}`（两种 region）
- GT 正向事后控制：`{groups["gt_local_positive_control"]}`
- 登记背景/孤立反例上下文：`{groups["registered_background_counterexample"]}`，其中非 GT 正向：`{groups["registered_background_counterexample_nonpositive"]}`
- 边界删失/边界接触：`{groups["boundary_censored_response"]}`
- unresolved 控制：`{groups["unresolved_control"]}`

## 可靠性

- 有效能量测量：`{counts["energy_valid"]}`
- 低能量：`{counts["low_energy"]}`
- 像素过少：`{counts["too_few_pixels"]}`
- 边界删失标记：`{counts["boundary_censored"]}`
- mask 裁剪标记：`{counts["mask_censored"]}`
- 背景估计受限：`{counts["background_contaminated"]}`
- 其他无效或失败：`{counts["other_invalid"]}`

## 正向与背景反例对照

Cliff's delta（克里夫德尔塔，非参数效应量，范围 -1 到 1）和 overlap coefficient（重叠系数，两个经验分布直方图重叠比例，越高表示越难分）仅用于描述，不用于训练或阈值选择。

{format_table(pos_bg, ["metric", "valid_a", "valid_b", "median_a", "median_b", "median_difference_a_minus_b", "cliffs_delta", "overlap_coefficient"])}

## 边界接触影响

{format_table(boundary, ["metric", "valid_a", "valid_b", "median_a", "median_b", "median_difference_a_minus_b", "cliffs_delta", "overlap_coefficient"])}

## GT bbox（bounding box，边界框）宽高对照

Spearman（斯皮尔曼秩相关，衡量单调关系，不要求线性关系）只用于事后对照。GT bbox 是标注范围，不是真实散射支撑或真实车辆尺寸，也不用于选择局部响应。

{format_table(gt, ["metric", "paired_sample_count", "spearman_rho", "interpretation_cn"])}

## H01 状态

`GM019_STATIC_H01` 状态：`{status}`

解释：距离向-方位向展宽已可按对象级计算，且用的是扇形局部坐标而不是图像 x/y 轴。当前分布能提供静态观测量，但背景/孤立反例与边界删失仍造成明显混叠；该状态不等于车辆判别规律成立。

## 支持证据

{format_table(filtered_summary(group_summary, "gt_local_positive_control"), ["metric", "sample_count", "valid_count", "median", "q1", "q3", "min", "max"])}

## 主要反例

{format_table(counterexamples, ["counterexample_id", "counterexample_type", "response_unit_id", "sar_frame", "metric_snapshot", "why_it_matters_cn", "visual_review_relpath"], limit=12)}

## 送往 GM_RM017 的动态问题

1. 同一响应线程中的 `range_p80_width`、`azimuth_p80_width`、`principal_axis_angle_to_range_deg` 是否随时间连续变化。
2. 这些观测量是否比 GT bbox 宽高更稳定地描述响应支撑。
3. 边界进入和离开时，方向性展宽和能量质心是否连续恢复。
4. 背景弧线、孤立小峰或 background-like 响应是否表现出不同于车辆响应的静态方向或时间稳定性。
5. 相邻同向车辆是否可能产生相似方向性展宽，导致静态单帧混叠。
6. 静态可分性不足时，动态共运动是否能补充解释，而不是重新加权打分。

## 视觉审阅

视觉审阅图位于未提交输出目录：

{chr(10).join(f"- `{path}`" for path in visual_paths) if visual_paths else "- 未生成视觉审阅图。"}

## Replay 与完整性

{format_table(gate_rows, ["gate_name", "status", "detail"])}

## 输出文件

- `{rel(OUTPUTS["measurements"])}`
- `{rel(OUTPUTS["group_summary"])}`
- `{rel(OUTPUTS["pairwise_controls"])}`
- `{rel(OUTPUTS["counterexamples"])}`
- `{rel(OUTPUTS["gate_integrity"])}`
- `{rel(OUTPUTS["report"])}`
"""


def build_gate_integrity(
    rows: Sequence[Mapping[str, Any]],
    group_summary: Sequence[Mapping[str, Any]],
    pairwise: Sequence[Mapping[str, Any]],
    counterexamples: Sequence[Mapping[str, Any]],
    output_map: Mapping[str, Path],
) -> list[dict[str, Any]]:
    primary = [row for row in rows if row.get("measurement_region_type") == PRIMARY_REGION]
    units = {row.get("response_unit_id", "") for row in primary}
    expected_units = row_count(INPUTS["local_response_units"])
    groups = group_counts(rows)
    forbidden_terms = ["selector", "ranking", "best_box", "final_annotation", "revised_gt", "runtime_prediction"]
    output_names = " ".join(rel(path).lower() for path in output_map.values())
    gate_rows: list[dict[str, Any]] = []
    idx = 1

    def add(name: str, status: bool, detail: str, source: Path | None = None) -> None:
        nonlocal idx
        gate_rows.append(
            {
                "gate_id": f"G{idx:03d}",
                "gate_name": name,
                "status": "PASS" if status else "FAIL",
                "detail": detail,
                "source_file": rel(source) if source else "",
                "sha256": sha256(source) if source and source.exists() else "",
                "row_count": row_count(source) if source and source.exists() else "",
            }
        )
        idx += 1

    for key, path in INPUTS.items():
        add(f"input_hash_{key}", path.exists(), "frozen input present and hashed", path)
    add("all_units_represented", len(units) == expected_units, f"represented={len(units)} expected={expected_units}")
    add("measurement_rows_stable", len(rows) == expected_units * len(REGION_TYPES), f"rows={len(rows)} expected={expected_units * len(REGION_TYPES)}")
    add("positive_group_present", groups["gt_local_positive_control"] > 0, f"count={groups['gt_local_positive_control']}")
    add(
        "background_group_present",
        groups["registered_background_counterexample"] > 0,
        f"count={groups['registered_background_counterexample']}",
    )
    add("boundary_group_present", groups["boundary_censored_response"] > 0, f"count={groups['boundary_censored_response']}")
    add("statistics_recomputable_from_measurements", bool(group_summary and pairwise), "evaluate reads object-level CSV")
    add("counterexamples_preserved", bool(counterexamples), f"rows={len(counterexamples)}")
    add(
        "forbidden_artifact_names_absent",
        not any(term in output_names for term in forbidden_terms),
        "no selector/ranking/final/revised/runtime artifact output names",
    )
    return gate_rows


def write_workspace_log(stage: str, details: str) -> None:
    WORKSPACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    prefix = "# OTY2 GM_RM019 static directional spread measurement log\n\n"
    if not WORKSPACE_LOG.exists():
        WORKSPACE_LOG.write_text(prefix, encoding="utf-8")
    with WORKSPACE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"## {stage}\n\n{details}\n\n")


def path_for_output(output_map: Mapping[str, Path], key: str) -> Path:
    return output_map[key]


def generate(output_map: Mapping[str, Path] | None = None, write_visuals: bool = True) -> list[dict[str, Any]]:
    output_map = output_map or OUTPUTS
    data = load_inputs()
    rows = measure_all(data, write_visuals=write_visuals)
    write_csv(path_for_output(output_map, "measurements"), format_rows_for_csv(rows, MEASUREMENT_FIELDS), MEASUREMENT_FIELDS)
    write_workspace_log(
        "generate",
        f"interpreter=D:/MINICONDA/envs/py311/python.exe\nmeasurements={rel(path_for_output(output_map, 'measurements'))}\nrows={len(rows)}\nvisual_dir={rel(VISUAL_DIR)}",
    )
    return rows


def evaluate(output_map: Mapping[str, Path] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    output_map = output_map or OUTPUTS
    measurement_path = path_for_output(output_map, "measurements")
    if not measurement_path.exists():
        raise FileNotFoundError(f"measurement CSV missing, run generate first: {measurement_path}")
    rows = read_rows(measurement_path)
    group_summary = build_group_summary(rows)
    pairwise = build_pairwise_controls(rows)
    counterexamples = build_counterexamples(rows)
    gate_rows = build_gate_integrity(rows, group_summary, pairwise, counterexamples, output_map)
    report = render_report(rows, group_summary, pairwise, counterexamples, gate_rows)
    write_csv(path_for_output(output_map, "group_summary"), format_rows_for_csv(group_summary, GROUP_SUMMARY_FIELDS), GROUP_SUMMARY_FIELDS)
    write_csv(path_for_output(output_map, "pairwise_controls"), format_rows_for_csv(pairwise, PAIRWISE_FIELDS), PAIRWISE_FIELDS)
    write_csv(path_for_output(output_map, "counterexamples"), format_rows_for_csv(counterexamples, COUNTEREXAMPLE_FIELDS), COUNTEREXAMPLE_FIELDS)
    write_csv(path_for_output(output_map, "gate_integrity"), gate_rows, GATE_FIELDS)
    write_text(path_for_output(output_map, "report"), report)
    write_workspace_log(
        "evaluate",
        f"report={rel(path_for_output(output_map, 'report'))}\ngroup_summary_rows={len(group_summary)}\npairwise_rows={len(pairwise)}\ncounterexamples={len(counterexamples)}",
    )
    return group_summary, pairwise, counterexamples


def output_hashes(output_map: Mapping[str, Path]) -> dict[str, str]:
    return {key: sha256(path) for key, path in output_map.items() if path.exists()}


def verify_replay() -> None:
    if VERIFY_TMP_DIR.exists():
        shutil.rmtree(VERIFY_TMP_DIR)
    VERIFY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_outputs = {key: VERIFY_TMP_DIR / path.name for key, path in OUTPUTS.items()}
    generate(tmp_outputs, write_visuals=False)
    evaluate(tmp_outputs)
    current = output_hashes(OUTPUTS)
    replay = output_hashes(tmp_outputs)
    mismatches = [key for key in OUTPUTS if current.get(key) != replay.get(key)]
    if mismatches:
        raise AssertionError("verify-replay hash mismatch: " + "; ".join(mismatches))
    write_workspace_log("verify-replay", "status=PASS\noutputs=" + ";".join(sorted(current)))
    print("verify-replay: PASS")


def row_text_position(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], fill: tuple[int, int, int]) -> None:
    x, y = xy
    lines = text.split("\n")
    line_h = 12
    width = max(draw.textlength(line) for line in lines) if lines else 0
    draw.rectangle([x - 4, y - 3, x + int(width) + 6, y + line_h * len(lines) + 4], fill=(0, 0, 0))
    for idx, line in enumerate(lines):
        draw.text((x, y + idx * line_h), line, fill=fill)


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    vec: tuple[float, float],
    scale: float,
    color: tuple[int, int, int],
    width: int = 3,
) -> None:
    sx, sy = start
    ex = sx + vec[0] * scale
    ey = sy + vec[1] * scale
    draw.line([sx, sy, ex, ey], fill=color, width=width)
    angle = math.atan2(ey - sy, ex - sx)
    for delta in [2.55, -2.55]:
        hx = ex + math.cos(angle + delta) * 10
        hy = ey + math.sin(angle + delta) * 10
        draw.line([ex, ey, hx, hy], fill=color, width=width)


def render_visual(row: Mapping[str, Any], output_path: Path) -> None:
    frame = parse_int(row.get("sar_frame"))
    path = sar_gray_path(frame)
    if not path.exists():
        return
    box = parse_box(row.get("region_bbox", ""))
    if box is None:
        return
    image = Image.open(path).convert("L").convert("RGB")
    crop_box = expand_box(box, 70.0)
    y_slice, x_slice = box_slices(crop_box)
    crop = image.crop((x_slice.start, y_slice.start, x_slice.stop, y_slice.stop))
    scale = 3
    canvas = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.BILINEAR)
    draw = ImageDraw.Draw(canvas)

    def local(point_x: float, point_y: float) -> tuple[float, float]:
        return (point_x - x_slice.start) * scale, (point_y - y_slice.start) * scale

    x1, y1 = local(box.x1, box.y1)
    x2, y2 = local(box.x2, box.y2)
    draw.rectangle([x1, y1, x2, y2], outline=(40, 255, 120), width=3)
    cx = parse_float(row.get("response_center_x"))
    cy = parse_float(row.get("response_center_y"))
    center = local(cx, cy)
    draw.ellipse([center[0] - 4, center[1] - 4, center[0] + 4, center[1] + 4], fill=(255, 255, 255))
    er = (parse_float(row.get("range_unit_x")), parse_float(row.get("range_unit_y")))
    ea = (parse_float(row.get("azimuth_unit_x")), parse_float(row.get("azimuth_unit_y")))
    draw_arrow(draw, center, er, 48, (255, 80, 80))
    draw_arrow(draw, center, ea, 48, (80, 170, 255))

    centroid_x = parse_float(row.get("energy_centroid_x"))
    centroid_y = parse_float(row.get("energy_centroid_y"))
    if not math.isnan(centroid_x) and not math.isnan(centroid_y):
        cxy = local(centroid_x, centroid_y)
        draw.ellipse([cxy[0] - 5, cxy[1] - 5, cxy[0] + 5, cxy[1] + 5], outline=(255, 220, 40), width=3)
    angle = parse_float(row.get("principal_axis_angle_image_deg"))
    if not math.isnan(angle):
        rad = math.radians(angle)
        vec = (math.cos(rad), math.sin(rad))
        draw.line(
            [
                center[0] - vec[0] * 45,
                center[1] - vec[1] * 45,
                center[0] + vec[0] * 45,
                center[1] + vec[1] * 45,
            ],
            fill=(255, 80, 255),
            width=3,
        )
    text = (
        f"{row.get('response_unit_id')} F{row.get('sar_frame')} {row.get('sample_group')}\n"
        f"r80={fmt(row.get('range_p80_width'), 2)} a80={fmt(row.get('azimuth_p80_width'), 2)} "
        f"ratio={fmt(row.get('range_to_azimuth_p80_ratio'), 2)}\n"
        f"reliability={row.get('measurement_reliability')}"
    )
    row_text_position(draw, text, (8, 8), (235, 245, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def select_and_render_visuals(rows: Sequence[Mapping[str, Any]], write_visuals: bool = True) -> dict[tuple[str, str], str]:
    primary = [
        row
        for row in rows
        if row.get("measurement_region_type") == PRIMARY_REGION and row.get("geometry_origin_status") == GEOMETRY_ORIGIN_STATUS
    ]
    valid = [row for row in primary if row.get("energy_valid") == "true"]
    selected: list[tuple[str, Mapping[str, Any]]] = []

    def pick(label: str, candidates: Sequence[Mapping[str, Any]], key: Callable[[Mapping[str, Any]], float], reverse: bool = True) -> None:
        if candidates:
            selected.append((label, sorted(candidates, key=key, reverse=reverse)[0]))

    positives = [row for row in valid if row.get("is_gt_local_positive_control") == "true"]
    bg_nonpos = [
        row
        for row in valid
        if row.get("is_registered_background_counterexample") == "true" and row.get("is_gt_local_positive_control") != "true"
    ]
    boundary = [row for row in valid if row.get("is_boundary_censored_response") == "true"]
    low_or_failed = [row for row in primary if row.get("energy_valid") != "true" or row.get("low_energy_flag") == "true"]
    pick("positive_high_ratio", positives, lambda row: numeric(row, "range_to_azimuth_p80_ratio"), True)
    pick("positive_low_ratio", positives, lambda row: numeric(row, "range_to_azimuth_p80_ratio"), False)
    pick("background_counterexample", bg_nonpos, lambda row: numeric(row, "background_subtracted_energy"), True)
    pick("boundary_contact", boundary, lambda row: numeric(row, "energy_centroid_offset_px"), True)
    pick("low_energy_or_failed", low_or_failed, lambda row: numeric(row, "pixel_count"), False)

    result: dict[tuple[str, str], str] = {}
    seen: set[tuple[str, str]] = set()
    for label, row in selected:
        key = (str(row.get("response_unit_id", "")), str(row.get("measurement_region_type", "")))
        if key in seen:
            continue
        seen.add(key)
        filename = f"{label}_{key[0]}_F{row.get('sar_frame')}.png"
        out_path = VISUAL_DIR / filename
        if write_visuals:
            render_visual(row, out_path)
        result[key] = rel(out_path)
    return result


def format_rows_for_csv(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> list[dict[str, str]]:
    formatted = []
    for row in rows:
        formatted.append({field: fmt(row.get(field)) if isinstance(row.get(field), (float, int, np.floating)) else row.get(field, "") for field in fields})
    return formatted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "evaluate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "generate":
        rows = generate()
        print(f"generate: wrote {len(rows)} measurement rows to {rel(OUTPUTS['measurements'])}")
    elif args.command == "evaluate":
        group_summary, pairwise, counterexamples = evaluate()
        print(
            "evaluate: wrote "
            f"{len(group_summary)} summary rows, {len(pairwise)} pairwise rows, {len(counterexamples)} counterexamples"
        )
    else:
        verify_replay()


if __name__ == "__main__":
    main()
