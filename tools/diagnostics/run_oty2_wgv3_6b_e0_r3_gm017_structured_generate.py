"""Generate E0-R3 structured multi-view SAR response measurements.

Generate verifies the frozen E0-R3 anchor plan and then reads real SAR gray
frames. It measures structured response fields, significant anonymous
components, component continuity events, high-energy sliding, vehicle-envelope
stability, and background counterfactual response fields.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

import run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_generate as e0
import run_oty2_wgv3_6b_e0_r3_gm017_anchor_plan as plan


DATE = plan.DATE
REPO_ROOT = plan.REPO_ROOT
SAMPLES_DIR = plan.SAMPLES_DIR
OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_e0_r3_gm017_structured_continuity_{DATE}"
VISUAL_DIR = OUTPUT_DIR / "visual_review"
REPLAY_DIR = OUTPUT_DIR / "_verify_replay_tmp_generate"

OUTPUTS = {
    "structured_response_timeline": SAMPLES_DIR / f"e0_r3_structured_response_timeline_{DATE}.csv",
    "high_energy_sliding_timeline": SAMPLES_DIR / f"e0_r3_high_energy_sliding_timeline_{DATE}.csv",
    "significant_components": SAMPLES_DIR / f"e0_r3_significant_components_{DATE}.csv",
    "component_continuity_events": SAMPLES_DIR / f"e0_r3_component_continuity_events_{DATE}.csv",
    "vehicle_envelope_stability": SAMPLES_DIR / f"e0_r3_vehicle_envelope_stability_{DATE}.csv",
    "background_counterfactuals": SAMPLES_DIR / f"e0_r3_background_counterfactuals_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"e0_r3_replay_check_{DATE}.csv",
}

GENERATION_KEYS = [
    "structured_response_timeline",
    "high_energy_sliding_timeline",
    "significant_components",
    "component_continuity_events",
    "vehicle_envelope_stability",
    "background_counterfactuals",
]


def parse_float(value: Any, default: float = 0.0) -> float:
    return plan.parse_float(value, default)


def parse_int(value: Any, default: int = 0) -> int:
    return plan.parse_int(value, default)


def fmt(value: Any, ndigits: int = 6) -> str:
    return plan.fmt(value, ndigits)


def read_csv(path: Path) -> list[dict[str, str]]:
    return plan.read_csv(path)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    plan.write_csv(path, rows, fields)


def row_count(path: Path) -> int:
    return plan.row_count(path)


def sha256_file(path: Path) -> str:
    return plan.sha256_file(path)


def rel(path: Path) -> str:
    return plan.rel(path)


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def axis_angle_deg(angle: float) -> float:
    return plan.axis_angle_deg(angle)


def directed_angle_deg(dx: float, dy: float) -> float:
    return plan.directed_angle_deg(dx, dy)


def axial_diff_deg(a: float, b: float) -> float:
    return plan.axial_diff_deg(a, b)


def unit(angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return math.cos(rad), math.sin(rad)


def safe_ratio(a: float, b: float) -> str:
    if abs(b) <= 1e-9:
        return ""
    return fmt(a / b)


def safe_log_ratio(a: float, b: float) -> float:
    return math.log(max(a, 1e-9) / max(b, 1e-9))


def parse_polygon(text: str) -> tuple[tuple[float, float], ...]:
    points = []
    for item in str(text).split(";"):
        if not item:
            continue
        x, y = item.split(":")
        points.append((float(x), float(y)))
    return tuple(points)


def polygon_bounds(poly: Sequence[tuple[float, float]], margin: int = 0) -> tuple[int, int, int, int]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x1 = max(0, int(math.floor(min(xs))) - margin)
    y1 = max(0, int(math.floor(min(ys))) - margin)
    x2 = min(e0.SAR_WIDTH - 1, int(math.ceil(max(xs))) + margin)
    y2 = min(e0.SAR_HEIGHT - 1, int(math.ceil(max(ys))) + margin)
    return x1, y1, x2, y2


def polygon_mask(poly: Sequence[tuple[float, float]]) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    x1, y1, x2, y2 = polygon_bounds(poly)
    mask_img = Image.new("L", (x2 - x1 + 1, y2 - y1 + 1), 0)
    draw = ImageDraw.Draw(mask_img)
    draw.polygon([(x - x1, y - y1) for x, y in poly], fill=255)
    return np.asarray(mask_img, dtype=bool), (x1, y1, x2, y2)


def expanded_background_values(image: np.ndarray, poly: Sequence[tuple[float, float]], mask: np.ndarray, bounds: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = bounds
    bx1, by1, bx2, by2 = polygon_bounds(poly, margin=45)
    crop = image[by1 : by2 + 1, bx1 : bx2 + 1]
    outer = np.ones(crop.shape, dtype=bool)
    inner = np.zeros(crop.shape, dtype=bool)
    yoff = y1 - by1
    xoff = x1 - bx1
    inner[yoff : yoff + mask.shape[0], xoff : xoff + mask.shape[1]] = mask
    values = crop[outer & ~inner]
    values = values[values > 0]
    if values.size == 0:
        values = image[image > 0]
    return values.astype(float)


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    total = float(weights.sum())
    if total <= 1e-9:
        return float(np.quantile(values, q))
    cum = np.cumsum(weights)
    idx = int(np.searchsorted(cum, q * total, side="left"))
    idx = min(max(idx, 0), len(values) - 1)
    return float(values[idx])


def weighted_width(values: np.ndarray, weights: np.ndarray, q_low: float, q_high: float) -> float:
    return weighted_quantile(values, weights, q_high) - weighted_quantile(values, weights, q_low)


def weighted_pca_axis(xs: np.ndarray, ys: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    if xs.size < 3:
        return 0.0, 1.0
    w = np.maximum(weights.astype(float), 1e-6)
    w = w / max(float(w.sum()), 1e-9)
    mx = float(np.sum(xs * w))
    my = float(np.sum(ys * w))
    dx = xs - mx
    dy = ys - my
    cov = np.array(
        [
            [float(np.sum(w * dx * dx)), float(np.sum(w * dx * dy))],
            [float(np.sum(w * dx * dy)), float(np.sum(w * dy * dy))],
        ]
    )
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vec = vecs[:, order[0]]
    axis = axis_angle_deg(math.degrees(math.atan2(float(vec[1]), float(vec[0]))))
    ratio = math.sqrt(max(float(vals[order[0]]), 1e-9) / max(float(vals[order[-1]]), 1e-9))
    return axis, ratio


def component_labels(high_mask: np.ndarray) -> list[list[tuple[int, int]]]:
    visited = np.zeros(high_mask.shape, dtype=bool)
    ys, xs = np.nonzero(high_mask)
    comps: list[list[tuple[int, int]]] = []
    height, width = high_mask.shape
    for sy, sx in zip(ys.tolist(), xs.tolist()):
        if visited[sy, sx]:
            continue
        stack = [(sx, sy)]
        visited[sy, sx] = True
        pixels: list[tuple[int, int]] = []
        while stack:
            x, y = stack.pop()
            pixels.append((x, y))
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if visited[ny, nx] or not high_mask[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    stack.append((nx, ny))
        comps.append(pixels)
    return comps


def axis_consistency(global_axis: float, dominant_axis: float, layout_axis: float) -> str:
    d1 = axial_diff_deg(global_axis, dominant_axis)
    d2 = axial_diff_deg(global_axis, layout_axis)
    if d1 <= 20 and d2 <= 25:
        return "AXES_LOCALLY_CONSISTENT"
    if d1 <= 35 or d2 <= 35:
        return "AXES_PARTIALLY_CONSISTENT"
    return "AXES_DIVERGENT"


def verify_plan_seal() -> tuple[bool, str]:
    if not plan.OUTPUTS["anchor_plan_seal"].exists():
        return False, "anchor_plan_seal_missing"
    rows = read_csv(plan.OUTPUTS["anchor_plan_seal"])
    errors = []
    for row in rows:
        if row.get("status") == "FAIL":
            errors.append(f"{row['seal_item']}=FAIL")
        if row.get("path") and row.get("sha256"):
            path = REPO_ROOT / row["path"]
            if not path.exists():
                errors.append(f"missing:{row['path']}")
            elif sha256_file(path) != row["sha256"]:
                errors.append(f"sha_mismatch:{row['path']}")
    required = {
        "PLAN_STAGE_DOES_NOT_READ_SAR_INTENSITY",
        "PLAN_STAGE_DOES_NOT_READ_E0_R2_MEASUREMENT_OUTCOMES",
        "ANCHOR_SEGMENTS_PRE_REGISTERED",
        "ABSOLUTE_RANGE_USES_RADAR_FAN_CENTER",
        "NO_RESPONSE_INDEX",
    }
    by_item = {row["seal_item"]: row["status"] for row in rows}
    errors.extend(f"required_plan_gate_not_pass:{item}" for item in sorted(required) if by_item.get(item) != "PASS")
    return not errors, ";".join(errors)


def geometry_by_frame() -> dict[int, dict[str, str]]:
    return {
        parse_int(row["sar_frame"]): row
        for row in read_csv(plan.E0_R1_REGION_MANIFEST)
        if row.get("family") == "BODY_ALIGNED_REFERENCE" and row.get("variant") == "body_axis_reference"
    }


def background_geometries() -> list[dict[str, str]]:
    allowed = {
        "fixed_known_non_vehicle_same_area": "fixed_known_non_vehicle_N005",
        "fixed_linear_structure_background_same_area": "fixed_linear_structure",
        "fixed_strong_scatterer_background_same_area": "fixed_strong_scatterer",
        "matched_strong_scatterer_background_same_area": "matched_strong_scatterer_background",
        "matched_linear_structure_background_same_area": "matched_linear_structure_background",
    }
    rows = []
    for row in read_csv(plan.E0_R1_REGION_MANIFEST):
        if row.get("variant") in allowed:
            item = dict(row)
            item["counterfactual_group"] = allowed[row["variant"]]
            rows.append(item)
    return rows


def measure_region(frame_plan: Mapping[str, Any], geom: Mapping[str, Any], image: np.ndarray, *, subject_name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    frame = parse_int(frame_plan["sar_frame"])
    cx = parse_float(geom.get("center_x", frame_plan.get("center_x")))
    cy = parse_float(geom.get("center_y", frame_plan.get("center_y")))
    body_axis = parse_float(frame_plan.get("body_axis_proxy_deg", geom.get("angle_deg", 0.0)))
    range_vec = (cx - plan.FAN_CENTER_X, cy - plan.FAN_CENTER_Y)
    range_len = max(math.hypot(*range_vec), 1e-9)
    range_unit = (range_vec[0] / range_len, range_vec[1] / range_len)
    azimuth_unit = (-range_unit[1], range_unit[0])
    long_unit = unit(body_axis)
    short_unit = (-long_unit[1], long_unit[0])
    poly = parse_polygon(geom["outer_polygon"])
    mask, bounds = polygon_mask(poly)
    x1, y1, x2, y2 = bounds
    crop = image[y1 : y2 + 1, x1 : x2 + 1]
    if crop.shape != mask.shape:
        min_h = min(crop.shape[0], mask.shape[0])
        min_w = min(crop.shape[1], mask.shape[1])
        crop = crop[:min_h, :min_w]
        mask = mask[:min_h, :min_w]
    values = crop[mask].astype(float)
    if values.size == 0:
        empty = {field: "" for field in STRUCTURED_FIELDS}
        empty.update({"sar_frame": frame, "subject_name": subject_name, "measurement_status": "EMPTY_REGION"})
        return empty, []
    ys_local, xs_local = np.nonzero(mask)
    xs = xs_local.astype(float) + x1
    ys = ys_local.astype(float) + y1
    rel_x = xs - cx
    rel_y = ys - cy
    range_offsets = rel_x * range_unit[0] + rel_y * range_unit[1]
    az_offsets = rel_x * azimuth_unit[0] + rel_y * azimuth_unit[1]
    long_offsets = rel_x * long_unit[0] + rel_y * long_unit[1]
    short_offsets = rel_x * short_unit[0] + rel_y * short_unit[1]
    background_values = expanded_background_values(image, poly, mask, bounds)
    bg_median = float(np.median(background_values)) if background_values.size else 0.0
    bg_std = float(np.std(background_values)) if background_values.size else 0.0
    positive_weights = np.maximum(values - bg_median, 0.0)
    weights = positive_weights + 1e-6
    high_threshold = max(float(np.percentile(values, 90)), bg_median + bg_std, float(np.percentile(image[image > 0], 95)) if np.any(image > 0) else 0.0)
    high = values >= high_threshold
    if not bool(high.any()):
        high = values >= float(np.percentile(values, 85))
    high_values = values[high]
    high_weights = np.maximum(high_values - bg_median, 1.0)
    high_x = xs[high]
    high_y = ys[high]
    high_range = range_offsets[high]
    high_az = az_offsets[high]
    high_long = long_offsets[high]
    high_short = short_offsets[high]

    centroid_x = float(np.average(xs, weights=weights))
    centroid_y = float(np.average(ys, weights=weights))
    centroid_rel = (centroid_x - cx, centroid_y - cy)
    centroid_range = centroid_rel[0] * range_unit[0] + centroid_rel[1] * range_unit[1]
    centroid_az = centroid_rel[0] * azimuth_unit[0] + centroid_rel[1] * azimuth_unit[1]
    centroid_long = centroid_rel[0] * long_unit[0] + centroid_rel[1] * long_unit[1]
    centroid_short = centroid_rel[0] * short_unit[0] + centroid_rel[1] * short_unit[1]
    peak_idx = int(np.argmax(values))
    peak_rel = (xs[peak_idx] - cx, ys[peak_idx] - cy)
    peak_long = peak_rel[0] * long_unit[0] + peak_rel[1] * long_unit[1]
    peak_short = peak_rel[0] * short_unit[0] + peak_rel[1] * short_unit[1]
    top_centroid_long = float(np.average(high_long, weights=high_weights)) if high_long.size else centroid_long
    top_centroid_short = float(np.average(high_short, weights=high_weights)) if high_short.size else centroid_short

    near_energy = float(values[range_offsets < 0].sum())
    far_energy = float(values[range_offsets >= 0].sum())
    body_positive = float(values[long_offsets >= 0].sum())
    body_negative = float(values[long_offsets < 0].sum())
    body_short_positive = float(values[short_offsets >= 0].sum())
    body_short_negative = float(values[short_offsets < 0].sum())
    global_axis, global_ratio = weighted_pca_axis(xs, ys, weights)
    high_mask = np.zeros(mask.shape, dtype=bool)
    high_mask[ys_local[high], xs_local[high]] = True
    comps = component_labels(high_mask)
    component_rows: list[dict[str, Any]] = []
    component_centers_x = []
    component_centers_y = []
    component_energies = []
    total_positive_energy = max(float(positive_weights.sum()), 1e-9)
    for idx, pixels in enumerate(sorted(comps, key=len, reverse=True), start=1):
        if len(pixels) < 3:
            continue
        px_local = np.array([p[0] for p in pixels], dtype=int)
        py_local = np.array([p[1] for p in pixels], dtype=int)
        comp_values = crop[py_local, px_local].astype(float)
        comp_weights = np.maximum(comp_values - bg_median, 1.0)
        comp_x = px_local.astype(float) + x1
        comp_y = py_local.astype(float) + y1
        comp_energy = float(np.maximum(comp_values - bg_median, 0.0).sum())
        comp_cx = float(np.average(comp_x, weights=comp_weights))
        comp_cy = float(np.average(comp_y, weights=comp_weights))
        comp_rel = (comp_cx - cx, comp_cy - cy)
        comp_range = comp_rel[0] * range_unit[0] + comp_rel[1] * range_unit[1]
        comp_az = comp_rel[0] * azimuth_unit[0] + comp_rel[1] * azimuth_unit[1]
        comp_long = comp_rel[0] * long_unit[0] + comp_rel[1] * long_unit[1]
        comp_short = comp_rel[0] * short_unit[0] + comp_rel[1] * short_unit[1]
        comp_axis, comp_ratio = weighted_pca_axis(comp_x, comp_y, comp_weights)
        comp_fraction = comp_energy / total_positive_energy
        if comp_fraction < 0.015 and len(pixels) < 12:
            continue
        component_centers_x.append(comp_cx)
        component_centers_y.append(comp_cy)
        component_energies.append(max(comp_energy, 1e-6))
        component_rows.append(
            {
                "component_frame_id": f"SAR{frame:06d}_C{idx:02d}",
                "component_id_within_frame": idx,
                "physical_vehicle_id": frame_plan.get("physical_vehicle_id", plan.PHYSICAL_VEHICLE_ID),
                "sar_frame": frame,
                "split": frame_plan.get("split", ""),
                "component_energy": fmt(comp_energy),
                "component_energy_fraction": fmt(comp_fraction),
                "component_area_m2": fmt(len(pixels) * plan.RADIAL_GRID_SPACING_M_PER_PX * plan.RADIAL_GRID_SPACING_M_PER_PX),
                "component_centroid_range_m": fmt(comp_range * plan.RADIAL_GRID_SPACING_M_PER_PX),
                "component_centroid_azimuth_m": fmt(comp_az * plan.RADIAL_GRID_SPACING_M_PER_PX),
                "component_centroid_body_long_m": fmt(comp_long * plan.RADIAL_GRID_SPACING_M_PER_PX),
                "component_centroid_body_short_m": fmt(comp_short * plan.RADIAL_GRID_SPACING_M_PER_PX),
                "component_axis_deg": fmt(comp_axis),
                "component_axis_ratio": fmt(comp_ratio),
                "component_identity_scope": "within_frame_only_anonymous_component",
            }
        )
    if component_centers_x:
        layout_axis, layout_ratio = weighted_pca_axis(np.asarray(component_centers_x), np.asarray(component_centers_y), np.asarray(component_energies))
    else:
        layout_axis, layout_ratio = global_axis, 1.0
    if component_rows:
        dominant = max(component_rows, key=lambda row: parse_float(row["component_energy"]))
        dominant_axis = parse_float(dominant["component_axis_deg"])
        dominant_ratio = parse_float(dominant["component_axis_ratio"])
    else:
        dominant_axis, dominant_ratio = global_axis, global_ratio
    absolute_range = math.hypot(cx - plan.FAN_CENTER_X, cy - plan.FAN_CENTER_Y) * plan.RADIAL_GRID_SPACING_M_PER_PX
    absolute_azimuth = directed_angle_deg(cx - plan.FAN_CENTER_X, cy - plan.FAN_CENTER_Y)
    body_length = parse_float(frame_plan.get("body_length_m_grid"))
    body_width = parse_float(frame_plan.get("body_width_m_grid"))
    body_long_p80 = weighted_width(high_long, high_weights, 0.10, 0.90) * plan.RADIAL_GRID_SPACING_M_PER_PX if high_long.size else 0.0
    body_short_p80 = weighted_width(high_short, high_weights, 0.10, 0.90) * plan.RADIAL_GRID_SPACING_M_PER_PX if high_short.size else 0.0
    extra_long = max(0.0, body_long_p80 - body_length * 1.15)
    extra_short = max(0.0, body_short_p80 - body_width * 1.25)
    missing_support = max(0.0, body_length * 0.40 - body_long_p80) + max(0.0, body_width * 0.35 - body_short_p80)
    envelope_status = "VEHICLE_ENVELOPE_STABLE_SOFT" if extra_long <= 0.35 and extra_short <= 0.30 and missing_support <= 0.60 else "VEHICLE_ENVELOPE_STRESS"
    structured = {
        "subject_name": subject_name,
        "sar_frame": frame,
        "timestamp_or_sequence_index": frame_plan.get("timestamp_or_sequence_index", frame),
        "physical_vehicle_id": frame_plan.get("physical_vehicle_id", plan.PHYSICAL_VEHICLE_ID),
        "split": frame_plan.get("split", ""),
        "center_range_m": fmt((cx - plan.FAN_CENTER_X) * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "center_azimuth_m": fmt((cy - plan.FAN_CENTER_Y) * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "absolute_range_from_radar_m": fmt(absolute_range),
        "absolute_azimuth_deg": fmt(absolute_azimuth),
        "motion_tangent_image_deg": frame_plan.get("motion_tangent_image_deg", ""),
        "motion_tangent_uncertainty_deg": frame_plan.get("motion_tangent_uncertainty_deg", ""),
        "body_axis_proxy_deg": frame_plan.get("body_axis_proxy_deg", ""),
        "body_axis_proxy_source": frame_plan.get("body_axis_proxy_source", ""),
        "body_axis_proxy_uncertainty_deg": frame_plan.get("body_axis_proxy_uncertainty_deg", ""),
        "local_range_axis_image_deg": frame_plan.get("local_range_axis_image_deg", ""),
        "relative_aspect_angle_deg": frame_plan.get("relative_aspect_angle_deg", ""),
        "aspect_domain_status": frame_plan.get("aspect_domain_status", ""),
        "total_background_subtracted_energy": fmt(float(positive_weights.sum())),
        "inner_outer_density_ratio": safe_ratio(float(values.mean()), bg_median),
        "range_p50_width_m": fmt(weighted_width(high_range, high_weights, 0.25, 0.75) * plan.RADIAL_GRID_SPACING_M_PER_PX if high_range.size else 0.0),
        "range_p80_width_m": fmt(weighted_width(high_range, high_weights, 0.10, 0.90) * plan.RADIAL_GRID_SPACING_M_PER_PX if high_range.size else 0.0),
        "range_p90_width_m": fmt(weighted_width(high_range, high_weights, 0.05, 0.95) * plan.RADIAL_GRID_SPACING_M_PER_PX if high_range.size else 0.0),
        "azimuth_p50_width_m": fmt(weighted_width(high_az, high_weights, 0.25, 0.75) * plan.RADIAL_GRID_SPACING_M_PER_PX if high_az.size else 0.0),
        "azimuth_p80_width_m": fmt(weighted_width(high_az, high_weights, 0.10, 0.90) * plan.RADIAL_GRID_SPACING_M_PER_PX if high_az.size else 0.0),
        "azimuth_p90_width_m": fmt(weighted_width(high_az, high_weights, 0.05, 0.95) * plan.RADIAL_GRID_SPACING_M_PER_PX if high_az.size else 0.0),
        "body_long_p80_width_m": fmt(body_long_p80),
        "body_short_p80_width_m": fmt(body_short_p80),
        "vehicle_projection_envelope_status": envelope_status,
        "required_missing_support_m": fmt(missing_support),
        "required_extra_spread_m": fmt(extra_long + extra_short),
        "global_energy_axis_image_deg": fmt(global_axis),
        "dominant_component_axis_image_deg": fmt(dominant_axis),
        "significant_component_layout_axis_image_deg": fmt(layout_axis),
        "global_axis_ratio": fmt(global_ratio),
        "dominant_axis_ratio": fmt(dominant_ratio),
        "layout_axis_ratio": fmt(layout_ratio),
        "axis_representation_consistency_status": axis_consistency(global_axis, dominant_axis, layout_axis),
        "energy_centroid_body_long_offset_m": fmt(centroid_long * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "energy_centroid_body_short_offset_m": fmt(centroid_short * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "peak_energy_body_long_offset_m": fmt(peak_long * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "peak_energy_body_short_offset_m": fmt(peak_short * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "top_energy_quantile_centroid_body_long_offset_m": fmt(top_centroid_long * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "top_energy_quantile_centroid_body_short_offset_m": fmt(top_centroid_short * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "energy_centroid_range_offset_m": fmt(centroid_range * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "energy_centroid_azimuth_offset_m": fmt(centroid_az * plan.RADIAL_GRID_SPACING_M_PER_PX),
        "radar_near_half_energy": fmt(near_energy),
        "radar_far_half_energy": fmt(far_energy),
        "near_far_energy_ratio": safe_ratio(near_energy, far_energy),
        "body_positive_half_energy": fmt(body_positive),
        "body_negative_half_energy": fmt(body_negative),
        "body_half_energy_ratio": safe_ratio(body_positive, body_negative),
        "body_short_positive_half_energy": fmt(body_short_positive),
        "body_short_negative_half_energy": fmt(body_short_negative),
        "body_short_half_energy_ratio": safe_ratio(body_short_positive, body_short_negative),
        "significant_component_count": len(component_rows),
        "dominant_component_energy_fraction": max((parse_float(row["component_energy_fraction"]) for row in component_rows), default=0.0),
        "mask_observability_status": frame_plan.get("mask_observability_status", ""),
        "measurement_status": "SAR_INTENSITY_MEASURED_IN_GENERATE_STAGE",
    }
    return structured, component_rows


def build_structured() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ok, detail = verify_plan_seal()
    if not ok:
        raise SystemExit(f"E0_R3_PLAN_SEAL_VALID=FAIL {detail}")
    frame_plan = read_csv(plan.OUTPUTS["body_axis_proxy_timeline"])
    frame_by_id = {parse_int(row["sar_frame"]): row for row in frame_plan}
    body_geom = geometry_by_frame()
    cache = e0.image_cache()
    structured: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    backgrounds: list[dict[str, Any]] = []
    bg_by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in background_geometries():
        bg_by_frame[parse_int(row["sar_frame"])].append(row)
    for frame in sorted(frame_by_id):
        if frame not in body_geom:
            continue
        image = e0.load_image(frame, cache)
        srow, crows = measure_region(frame_by_id[frame], body_geom[frame], image, subject_name="vehicle_body_axis_reference")
        structured.append(srow)
        components.extend(crows)
        for bg in bg_by_frame.get(frame, []):
            brow, _ = measure_region(frame_by_id[frame], bg, image, subject_name=bg.get("counterfactual_group", bg.get("variant", "background")))
            backgrounds.append(
                {
                    "counterfactual_id": f"{bg.get('counterfactual_group', bg.get('variant', 'background'))}_sar{frame:06d}",
                    "counterfactual_group": bg.get("counterfactual_group", bg.get("variant", "")),
                    "sar_frame": frame,
                    "split": frame_by_id[frame].get("split", ""),
                    "center_x": bg.get("center_x", ""),
                    "center_y": bg.get("center_y", ""),
                    "total_background_subtracted_energy": brow.get("total_background_subtracted_energy", ""),
                    "energy_centroid_body_long_offset_m": brow.get("energy_centroid_body_long_offset_m", ""),
                    "energy_centroid_body_short_offset_m": brow.get("energy_centroid_body_short_offset_m", ""),
                    "near_far_energy_ratio": brow.get("near_far_energy_ratio", ""),
                    "component_layout_axis_deg": brow.get("significant_component_layout_axis_image_deg", ""),
                    "significant_component_count": brow.get("significant_component_count", ""),
                    "counterfactual_role": "generated_from_real_sar_intensity_in_generate_stage",
                }
            )
    return structured, components, backgrounds


def build_component_events(components: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_frame: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in components:
        by_frame[parse_int(row["sar_frame"])].append(row)
    events: list[dict[str, Any]] = []
    frames = sorted(by_frame)
    for fa, fb in zip(frames, frames[1:]):
        if fb - fa > plan.MAXIMUM_ALLOWED_FRAME_GAP:
            continue
        prev = by_frame[fa]
        curr = by_frame[fb]
        prev_to_curr: dict[str, list[tuple[float, Mapping[str, Any]]]] = {}
        curr_to_prev: dict[str, list[tuple[float, Mapping[str, Any]]]] = {}
        for a in prev:
            ax = parse_float(a["component_centroid_body_long_m"])
            ay = parse_float(a["component_centroid_body_short_m"])
            for b in curr:
                bx = parse_float(b["component_centroid_body_long_m"])
                by = parse_float(b["component_centroid_body_short_m"])
                dist = math.hypot(bx - ax, by - ay)
                if dist <= 0.75:
                    prev_to_curr.setdefault(a["component_frame_id"], []).append((dist, b))
                    curr_to_prev.setdefault(b["component_frame_id"], []).append((dist, a))
        matched_curr: set[str] = set()
        for a in prev:
            matches = sorted(prev_to_curr.get(a["component_frame_id"], []), key=lambda item: item[0])
            if not matches:
                events.append(component_event(fa, fb, "COMPONENT_DISAPPEARED", a, None, "", "", "no_current_component_within_0p75m"))
                continue
            if len(matches) > 1:
                for dist, b in matches[:3]:
                    matched_curr.add(str(b["component_frame_id"]))
                    events.append(component_event(fa, fb, "COMPONENT_SPLIT", a, b, dist, "", "multiple_current_components_near_previous"))
            else:
                dist, b = matches[0]
                matched_curr.add(str(b["component_frame_id"]))
                basis = "nearest_body_relative_component_with_energy_fraction_check"
                events.append(component_event(fa, fb, "COMPONENT_CONTINUED", a, b, dist, "", basis))
        for b in curr:
            near_prev = curr_to_prev.get(b["component_frame_id"], [])
            if len(near_prev) > 1:
                for dist, a in sorted(near_prev, key=lambda item: item[0])[:3]:
                    events.append(component_event(fa, fb, "COMPONENT_MERGE", a, b, dist, "", "multiple_previous_components_near_current"))
            if b["component_frame_id"] not in matched_curr:
                events.append(component_event(fa, fb, "COMPONENT_APPEARED", None, b, "", "", "no_previous_component_within_0p75m"))
    return events


def component_event(
    from_frame: int,
    to_frame: int,
    event_type: str,
    a: Mapping[str, Any] | None,
    b: Mapping[str, Any] | None,
    distance_m: Any,
    displacement_m: Any,
    basis: str,
) -> dict[str, Any]:
    if a and b:
        energy_change = parse_float(b["component_energy_fraction"]) - parse_float(a["component_energy_fraction"])
        displacement = math.hypot(
            parse_float(b["component_centroid_body_long_m"]) - parse_float(a["component_centroid_body_long_m"]),
            parse_float(b["component_centroid_body_short_m"]) - parse_float(a["component_centroid_body_short_m"]),
        )
    else:
        energy_change = parse_float((b or a or {}).get("component_energy_fraction", ""))
        displacement = parse_float(displacement_m)
    return {
        "event_id": f"{from_frame}_{to_frame}_{event_type}_{len(basis)}_{(a or b or {}).get('component_id_within_frame','')}",
        "event_type": event_type,
        "from_frame": from_frame,
        "to_frame": to_frame,
        "from_component_frame_id": a.get("component_frame_id", "") if a else "",
        "to_component_frame_id": b.get("component_frame_id", "") if b else "",
        "motion_compensated_distance_m": fmt(parse_float(distance_m, displacement)),
        "body_relative_displacement_m": fmt(displacement),
        "energy_fraction_change": fmt(energy_change),
        "association_basis": basis,
        "association_scope": "anonymous_structure_continuity_not_fixed_scatterer_identity",
    }


def build_sliding(structured: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_pair = {(parse_int(row["from_frame"]), parse_int(row["to_frame"])): [] for row in events}
    for row in events:
        by_pair.setdefault((parse_int(row["from_frame"]), parse_int(row["to_frame"])), []).append(row)
    rows = []
    ordered = sorted(structured, key=lambda row: parse_int(row["sar_frame"]))
    for a, b in zip(ordered, ordered[1:]):
        fa, fb = parse_int(a["sar_frame"]), parse_int(b["sar_frame"])
        if fb - fa > plan.MAXIMUM_ALLOWED_FRAME_GAP:
            continue
        delta_aspect = parse_float(b["relative_aspect_angle_deg"]) - parse_float(a["relative_aspect_angle_deg"])
        delta_peak = parse_float(b["peak_energy_body_long_offset_m"]) - parse_float(a["peak_energy_body_long_offset_m"])
        delta_centroid = parse_float(b["energy_centroid_body_long_offset_m"]) - parse_float(a["energy_centroid_body_long_offset_m"])
        delta_near_far = safe_log_ratio(parse_float(b["near_far_energy_ratio"], 1.0), parse_float(a["near_far_energy_ratio"], 1.0))
        delta_layout = parse_float(b["significant_component_layout_axis_image_deg"]) - parse_float(a["significant_component_layout_axis_image_deg"])
        pair_events = by_pair.get((fa, fb), [])
        if a.get("mask_observability_status") != "HIGH_OBSERVABILITY_MASK_INNER" or b.get("mask_observability_status") != "HIGH_OBSERVABILITY_MASK_INNER":
            change_class = "MASK_CENSORED_CHANGE"
        elif any(row["event_type"] in {"COMPONENT_SPLIT", "COMPONENT_MERGE"} for row in pair_events):
            change_class = "STRUCTURAL_SPLIT_OR_MERGE"
        elif abs(delta_centroid) > 0.75 or abs(delta_peak) > 1.25:
            change_class = "ABRUPT_UNEXPLAINED_JUMP"
        elif abs(delta_centroid) <= 0.25 and abs(delta_near_far) <= 0.25:
            change_class = "SMOOTH_GRADUAL_CHANGE"
        else:
            change_class = "PIECEWISE_GRADUAL_CHANGE"
        rows.append(
            {
                "from_frame": fa,
                "to_frame": fb,
                "split_from": a.get("split", ""),
                "split_to": b.get("split", ""),
                "delta_aspect_deg": fmt(delta_aspect),
                "delta_peak_body_long_m": fmt(delta_peak),
                "delta_energy_centroid_body_long_m": fmt(delta_centroid),
                "delta_near_far_log_ratio": fmt(delta_near_far),
                "delta_component_layout_axis_deg": fmt(delta_layout),
                "component_event_types": ";".join(sorted(Counter(row["event_type"] for row in pair_events))),
                "high_energy_sliding_class": change_class,
                "causal_locality": "adjacent_or_nearby_frames_only",
            }
        )
    return rows


def build_envelope(structured: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in structured:
        rows.append(
            {
                "sar_frame": row["sar_frame"],
                "split": row["split"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "constant_vehicle_envelope": "E0_R1_BODY_SUPPORT_FIT_SOFT_ENVELOPE",
                "body_long_p80_width_m": row["body_long_p80_width_m"],
                "body_short_p80_width_m": row["body_short_p80_width_m"],
                "required_missing_support_m": row["required_missing_support_m"],
                "required_extra_spread_m": row["required_extra_spread_m"],
                "vehicle_projection_envelope_status": row["vehicle_projection_envelope_status"],
                "view_dependent_response_support": "allowed_to_change_with_relative_aspect",
            }
        )
    stable = sum(row["vehicle_projection_envelope_status"] == "VEHICLE_ENVELOPE_STABLE_SOFT" for row in rows)
    rows.append(
        {
            "sar_frame": "SUMMARY",
            "split": "all",
            "physical_vehicle_id": plan.PHYSICAL_VEHICLE_ID,
            "constant_vehicle_envelope": "soft_envelope_summary",
            "body_long_p80_width_m": "",
            "body_short_p80_width_m": "",
            "required_missing_support_m": "",
            "required_extra_spread_m": "",
            "vehicle_projection_envelope_status": f"stable_frames={stable};total_frames={len(structured)}",
            "view_dependent_response_support": "reported_separately_from_constant_vehicle_envelope",
        }
    )
    return rows


def draw_crop_card(
    image: np.ndarray,
    frame_plan: Mapping[str, Any],
    geom: Mapping[str, Any],
    structured: Mapping[str, Any],
    comps: Sequence[Mapping[str, Any]],
    title: str,
    path: Path,
) -> None:
    base = Image.fromarray(image.astype(np.uint8)).convert("RGB")
    poly = parse_polygon(geom["outer_polygon"])
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x1 = max(0, int(min(xs)) - 95)
    y1 = max(0, int(min(ys)) - 95)
    x2 = min(base.width - 1, int(max(xs)) + 95)
    y2 = min(base.height - 1, int(max(ys)) + 95)
    crop = base.crop((x1, y1, x2 + 1, y2 + 1))
    draw = ImageDraw.Draw(crop)
    shifted_poly = [(x - x1, y - y1) for x, y in poly]
    draw.line(shifted_poly + [shifted_poly[0]], fill=(0, 240, 0), width=3)
    cx = parse_float(frame_plan["center_x"]) - x1
    cy = parse_float(frame_plan["center_y"]) - y1
    body = unit(parse_float(frame_plan["body_axis_proxy_deg"]))
    rng = unit(parse_float(frame_plan["local_range_axis_image_deg"]))
    draw.line((cx - body[0] * 80, cy - body[1] * 80, cx + body[0] * 80, cy + body[1] * 80), fill=(40, 180, 255), width=3)
    draw.line((cx - rng[0] * 70, cy - rng[1] * 70, cx + rng[0] * 70, cy + rng[1] * 70), fill=(255, 200, 0), width=2)
    long_unit = unit(parse_float(frame_plan["body_axis_proxy_deg"]))
    short_unit = (-long_unit[1], long_unit[0])
    cent_long = parse_float(structured["energy_centroid_body_long_offset_m"]) / plan.RADIAL_GRID_SPACING_M_PER_PX
    cent_short = parse_float(structured["energy_centroid_body_short_offset_m"]) / plan.RADIAL_GRID_SPACING_M_PER_PX
    peak_long = parse_float(structured["peak_energy_body_long_offset_m"]) / plan.RADIAL_GRID_SPACING_M_PER_PX
    peak_short = parse_float(structured["peak_energy_body_short_offset_m"]) / plan.RADIAL_GRID_SPACING_M_PER_PX
    cpx = cx + cent_long * long_unit[0] + cent_short * short_unit[0]
    cpy = cy + cent_long * long_unit[1] + cent_short * short_unit[1]
    ppx = cx + peak_long * long_unit[0] + peak_short * short_unit[0]
    ppy = cy + peak_long * long_unit[1] + peak_short * short_unit[1]
    draw.ellipse((cpx - 5, cpy - 5, cpx + 5, cpy + 5), fill=(255, 0, 255))
    draw.rectangle((ppx - 5, ppy - 5, ppx + 5, ppy + 5), outline=(255, 60, 60), width=3)
    for comp in comps[:6]:
        cl = parse_float(comp["component_centroid_body_long_m"]) / plan.RADIAL_GRID_SPACING_M_PER_PX
        cs = parse_float(comp["component_centroid_body_short_m"]) / plan.RADIAL_GRID_SPACING_M_PER_PX
        qx = cx + cl * long_unit[0] + cs * short_unit[0]
        qy = cy + cl * long_unit[1] + cs * short_unit[1]
        draw.ellipse((qx - 4, qy - 4, qx + 4, qy + 4), outline=(255, 255, 0), width=2)
    draw.rectangle((8, 8, min(crop.width - 8, 830), 88), fill=(0, 0, 0))
    draw.text((16, 16), title, fill=(255, 255, 255))
    draw.text((16, 38), f"SAR {frame_plan['sar_frame']} aspect={structured['relative_aspect_angle_deg']} centroid_long={structured['energy_centroid_body_long_offset_m']}m", fill=(255, 255, 255))
    draw.text((16, 60), f"magenta=energy centroid red=peak yellow=anonymous components", fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(path)


def build_visuals(structured: Sequence[Mapping[str, Any]], components: Sequence[Mapping[str, Any]], sliding: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    frame_plan = {parse_int(row["sar_frame"]): row for row in read_csv(plan.OUTPUTS["body_axis_proxy_timeline"])}
    body_geom = geometry_by_frame()
    by_comp: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for comp in components:
        by_comp[parse_int(comp["sar_frame"])].append(comp)
    by_frame = {parse_int(row["sar_frame"]): row for row in structured}
    cache = e0.image_cache()
    visual_defs: list[tuple[str, int, str]] = []
    a_frames = [parse_int(row["sar_frame"]) for row in structured if row.get("split") == "calibration"]
    if a_frames:
        visual_defs.append(("a_complete_anchor_timeline_start", min(a_frames), "A anchor segment: complete observable start"))
        visual_defs.append(("a_complete_anchor_timeline_end", max(a_frames), "A anchor segment: complete observable end"))
    if sliding:
        slide = max(sliding, key=lambda row: abs(parse_float(row["delta_energy_centroid_body_long_m"])))
        visual_defs.append(("high_energy_body_long_sliding_sample", parse_int(slide["to_frame"]), "High-energy centroid body-long sliding sample"))
        stable = min(sliding, key=lambda row: abs(parse_float(row["delta_energy_centroid_body_long_m"])))
        visual_defs.append(("high_energy_stable_control_sample", parse_int(stable["to_frame"]), "High-energy position stable control sample"))
    event_frames = [parse_int(comp["sar_frame"]) for comp in components]
    if event_frames:
        visual_defs.append(("component_structure_sample", sorted(event_frames)[len(event_frames) // 2], "Anonymous significant component structure sample"))
    same_pair = next((row for row in read_csv(plan.OUTPUTS["aspect_matched_pair_plan"]) if row.get("pair_type") == "same_aspect_similar_range"), None)
    diff_pair = next((row for row in read_csv(plan.OUTPUTS["aspect_matched_pair_plan"]) if row.get("pair_type") == "different_aspect_similar_range"), None)
    if same_pair:
        visual_defs.append(("same_aspect_revisit_frame_a", parse_int(same_pair["frame_a"]), "Same-aspect revisit pair A"))
        visual_defs.append(("same_aspect_revisit_frame_b", parse_int(same_pair["frame_b"]), "Same-aspect revisit pair B"))
    if diff_pair:
        visual_defs.append(("different_aspect_similar_range_frame_b", parse_int(diff_pair["frame_b"]), "Different-aspect similar-range matched sample"))
    b_frames = [parse_int(row["sar_frame"]) for row in structured if row.get("split") == "guard"]
    c_frames = [parse_int(row["sar_frame"]) for row in structured if row.get("aspect_domain_status") == "OUT_OF_CALIBRATION_ASPECT_DOMAIN"]
    if b_frames:
        visual_defs.append(("a_to_b_mask_transition_reserved", min(b_frames), "A to B guard transition candidate"))
    if c_frames:
        visual_defs.append(("out_of_domain_diagnosis_frame", c_frames[0], "Out-of-calibration-domain diagnosis frame"))

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for visual_id, frame, title in visual_defs:
        if frame not in frame_plan or frame not in body_geom or frame not in by_frame:
            continue
        key = f"{visual_id}_{frame}"
        if key in seen:
            continue
        seen.add(key)
        image = e0.load_image(frame, cache)
        path = VISUAL_DIR / f"{visual_id}_sar{frame:06d}.png"
        draw_crop_card(image, frame_plan[frame], body_geom[frame], by_frame[frame], by_comp.get(frame, []), title, path)
        rows.append(
            {
                "visual_id": visual_id,
                "sar_frame": frame,
                "diagnostic_png": rel(path),
                "review_requirement": title,
                "review_status": "generated_not_yet_marked_opened",
            }
        )
    make_contact_sheet(rows, VISUAL_DIR / "_structure_contact_sheet.png")
    return rows


def make_contact_sheet(rows: Sequence[Mapping[str, Any]], path: Path) -> None:
    thumbs = []
    for row in rows[:12]:
        img_path = REPO_ROOT / row["diagnostic_png"]
        if img_path.exists():
            thumbs.append((row, Image.open(img_path).convert("RGB").resize((360, 220))))
    if not thumbs:
        return
    sheet = Image.new("RGB", (3 * 380, math.ceil(len(thumbs) / 3) * 270 + 40), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 12), "E0-R3 GM_RM017 structured visual review contact sheet", fill=(0, 0, 0))
    for idx, (row, img) in enumerate(thumbs):
        x = 20 + (idx % 3) * 380
        y = 40 + (idx // 3) * 270
        sheet.paste(img, (x, y))
        draw.text((x, y + 225), f"{row['visual_id']} SAR{row['sar_frame']}", fill=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def run_generation(output_map: Mapping[str, Path] = OUTPUTS) -> None:
    structured, components, backgrounds = build_structured()
    events = build_component_events(components)
    sliding = build_sliding(structured, events)
    envelope = build_envelope(structured)
    build_visuals(structured, components, sliding)
    write_csv(output_map["structured_response_timeline"], structured, STRUCTURED_FIELDS)
    write_csv(output_map["high_energy_sliding_timeline"], sliding, SLIDING_FIELDS)
    write_csv(output_map["significant_components"], components, COMPONENT_FIELDS)
    write_csv(output_map["component_continuity_events"], events, EVENT_FIELDS)
    write_csv(output_map["vehicle_envelope_stability"], envelope, ENVELOPE_FIELDS)
    write_csv(output_map["background_counterfactuals"], backgrounds, BACKGROUND_FIELDS)
    print(f"E0_R3 generation complete: frames={len(structured)} components={len(components)} events={len(events)} backgrounds={len(backgrounds)}")


def verify_replay() -> None:
    if REPLAY_DIR.exists():
        resolved_replay = REPLAY_DIR.resolve()
        resolved_output = OUTPUT_DIR.resolve()
        if not resolved_replay.is_relative_to(resolved_output):
            raise RuntimeError(f"refusing to remove replay path outside output dir: {REPLAY_DIR}")
        shutil.rmtree(REPLAY_DIR)
    replay_outputs = {key: (REPLAY_DIR / path.name if key != "replay_check" else OUTPUTS["replay_check"]) for key, path in OUTPUTS.items()}
    run_generation(replay_outputs)
    rows = []
    for key in GENERATION_KEYS:
        frozen = OUTPUTS[key]
        replay = replay_outputs[key]
        same = frozen.exists() and replay.exists() and sha256_file(frozen) == sha256_file(replay)
        rows.append(
            {
                "artifact_key": key,
                "phase": "generate",
                "frozen_sha256": sha256_file(frozen) if frozen.exists() else "",
                "replay_sha256": sha256_file(replay) if replay.exists() else "",
                "status": "PASS" if same else "FAIL",
            }
        )
    write_csv(OUTPUTS["replay_check"], rows, REPLAY_FIELDS)
    print(f"E0_R3_GENERATE_FROZEN_REPLAY_IDENTICAL={'PASS' if all(row['status'] == 'PASS' for row in rows) else 'FAIL'}")


STRUCTURED_FIELDS = [
    "subject_name",
    "sar_frame",
    "timestamp_or_sequence_index",
    "physical_vehicle_id",
    "split",
    "center_range_m",
    "center_azimuth_m",
    "absolute_range_from_radar_m",
    "absolute_azimuth_deg",
    "motion_tangent_image_deg",
    "motion_tangent_uncertainty_deg",
    "body_axis_proxy_deg",
    "body_axis_proxy_source",
    "body_axis_proxy_uncertainty_deg",
    "local_range_axis_image_deg",
    "relative_aspect_angle_deg",
    "aspect_domain_status",
    "total_background_subtracted_energy",
    "inner_outer_density_ratio",
    "range_p50_width_m",
    "range_p80_width_m",
    "range_p90_width_m",
    "azimuth_p50_width_m",
    "azimuth_p80_width_m",
    "azimuth_p90_width_m",
    "body_long_p80_width_m",
    "body_short_p80_width_m",
    "vehicle_projection_envelope_status",
    "required_missing_support_m",
    "required_extra_spread_m",
    "global_energy_axis_image_deg",
    "dominant_component_axis_image_deg",
    "significant_component_layout_axis_image_deg",
    "global_axis_ratio",
    "dominant_axis_ratio",
    "layout_axis_ratio",
    "axis_representation_consistency_status",
    "energy_centroid_body_long_offset_m",
    "energy_centroid_body_short_offset_m",
    "peak_energy_body_long_offset_m",
    "peak_energy_body_short_offset_m",
    "top_energy_quantile_centroid_body_long_offset_m",
    "top_energy_quantile_centroid_body_short_offset_m",
    "energy_centroid_range_offset_m",
    "energy_centroid_azimuth_offset_m",
    "radar_near_half_energy",
    "radar_far_half_energy",
    "near_far_energy_ratio",
    "body_positive_half_energy",
    "body_negative_half_energy",
    "body_half_energy_ratio",
    "body_short_positive_half_energy",
    "body_short_negative_half_energy",
    "body_short_half_energy_ratio",
    "significant_component_count",
    "dominant_component_energy_fraction",
    "mask_observability_status",
    "measurement_status",
]

SLIDING_FIELDS = [
    "from_frame",
    "to_frame",
    "split_from",
    "split_to",
    "delta_aspect_deg",
    "delta_peak_body_long_m",
    "delta_energy_centroid_body_long_m",
    "delta_near_far_log_ratio",
    "delta_component_layout_axis_deg",
    "component_event_types",
    "high_energy_sliding_class",
    "causal_locality",
]

COMPONENT_FIELDS = [
    "component_frame_id",
    "component_id_within_frame",
    "physical_vehicle_id",
    "sar_frame",
    "split",
    "component_energy",
    "component_energy_fraction",
    "component_area_m2",
    "component_centroid_range_m",
    "component_centroid_azimuth_m",
    "component_centroid_body_long_m",
    "component_centroid_body_short_m",
    "component_axis_deg",
    "component_axis_ratio",
    "component_identity_scope",
]

EVENT_FIELDS = [
    "event_id",
    "event_type",
    "from_frame",
    "to_frame",
    "from_component_frame_id",
    "to_component_frame_id",
    "motion_compensated_distance_m",
    "body_relative_displacement_m",
    "energy_fraction_change",
    "association_basis",
    "association_scope",
]

ENVELOPE_FIELDS = [
    "sar_frame",
    "split",
    "physical_vehicle_id",
    "constant_vehicle_envelope",
    "body_long_p80_width_m",
    "body_short_p80_width_m",
    "required_missing_support_m",
    "required_extra_spread_m",
    "vehicle_projection_envelope_status",
    "view_dependent_response_support",
]

BACKGROUND_FIELDS = [
    "counterfactual_id",
    "counterfactual_group",
    "sar_frame",
    "split",
    "center_x",
    "center_y",
    "total_background_subtracted_energy",
    "energy_centroid_body_long_offset_m",
    "energy_centroid_body_short_offset_m",
    "near_far_energy_ratio",
    "component_layout_axis_deg",
    "significant_component_count",
    "counterfactual_role",
]

REPLAY_FIELDS = ["artifact_key", "phase", "frozen_sha256", "replay_sha256", "status"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "generate":
        run_generation()
    elif args.command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
