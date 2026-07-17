#!/usr/bin/env python3
from __future__ import annotations

"""Shared lifecycle and geometry utilities for the bounded OTY2-S1D0 workflow."""

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from oty2_s1x_common import (
    FAN_HEIGHT,
    FAN_RADIUS_PX,
    FAN_WIDTH,
    REPO_ROOT,
    annular_sector_mask,
    fan_xy,
    fmt,
    imaging_valid_mask,
    load_json,
    read_csv,
    require,
    robust_median_mad,
    sha256_file,
    verify_git_gate,
    warp_translation,
    write_csv,
    write_json,
)


SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO_ROOT / path


def parse_ranges(text: str) -> set[int]:
    values: set[int] = set()
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            values.update(range(int(left), int(right) + 1))
        else:
            values.add(int(part))
    return values


def compact_ranges(values: set[int] | list[int]) -> str:
    ordered = sorted(set(int(value) for value in values))
    if not ordered:
        return ""
    runs: list[str] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        runs.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    runs.append(str(start) if start == previous else f"{start}-{previous}")
    return ";".join(runs)


def bbox_from_state(row: dict[str, str]) -> tuple[float, float, float, float] | None:
    if row.get("reference_bbox_available", "").lower() != "true":
        return None
    return (
        float(row["reference_bbox_x1"]),
        float(row["reference_bbox_y1"]),
        float(row["reference_bbox_x2"]),
        float(row["reference_bbox_y2"]),
    )


def interpolate_bbox(
    state_index: dict[tuple[str, str, int], dict[str, str]],
    scene: str,
    vehicle_id: str,
    left_frame: int,
    right_frame: int,
    ratio: float,
    search_radius: int = 16,
) -> tuple[tuple[float, float, float, float] | None, str, float]:
    left = state_index[(scene, vehicle_id, left_frame)]
    right = state_index[(scene, vehicle_id, right_frame)]
    left_bbox = bbox_from_state(left)
    right_bbox = bbox_from_state(right)
    if left_bbox is not None and right_bbox is not None:
        bbox = tuple((1.0 - ratio) * a + ratio * b for a, b in zip(left_bbox, right_bbox))
        return bbox, "DIRECT_INTERPOLATED_OPTICAL_BBOX", 1.0
    candidates: list[tuple[int, tuple[float, float, float, float]]] = []
    center = int(round((1.0 - ratio) * left_frame + ratio * right_frame))
    for delta in range(search_radius + 1):
        for frame in {center - delta, center + delta}:
            if frame < 0 or frame > 367:
                continue
            state = state_index[(scene, vehicle_id, frame)]
            bbox = bbox_from_state(state)
            if bbox is not None:
                candidates.append((abs(frame - center), bbox))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1], "NEAREST_OPTICAL_BBOX_RESEARCH_PROXY", 1.6
    return None, "NO_OPTICAL_BBOX_PROXY_AVAILABLE", 2.0


def positive_depth_values(depth: np.ndarray) -> np.ndarray:
    values = np.asarray(depth, dtype=np.float64).reshape(-1)
    return values[np.isfinite(values) & (values > 0)]


def sample_depth(depth_path: Path, bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    if not depth_path.is_file():
        return math.nan, math.nan
    depth = np.load(depth_path, mmap_mode="r")
    x1, y1, x2, y2 = bbox
    left = max(0, int(math.floor(x1)))
    top = max(0, int(math.floor(y1)))
    right = min(depth.shape[1], int(math.ceil(x2)))
    bottom = min(depth.shape[0], int(math.ceil(y2)))
    inset_x = max(1, int(round(0.15 * max(1, right - left))))
    inset_y = max(1, int(round(0.15 * max(1, bottom - top))))
    values = positive_depth_values(depth[top + inset_y : max(top + inset_y + 1, bottom - inset_y), left + inset_x : max(left + inset_x + 1, right - inset_x)])
    if values.size == 0:
        return math.nan, math.nan
    median = float(np.median(values))
    return median, float(np.median(np.abs(values - median)))


def combined_visibility(left: dict[str, str], right: dict[str, str]) -> str:
    values = {left["visibility_state"], right["visibility_state"]}
    if values == {"full_visible"}:
        return "full_visible"
    if "fully_occluded" in values:
        return "fully_occluded"
    if "visible_but_unboxed" in values:
        return "visible_but_unboxed"
    if "partial_visible" in values:
        return "partial_visible"
    return ";".join(sorted(values))


def build_condition_geometry(
    scene: str,
    bbox: tuple[float, float, float, float],
    depth_median: float,
    calibration: dict[str, Any],
    visibility: str,
    bbox_multiplier: float,
    uncertainty: dict[str, Any],
) -> dict[str, float | str]:
    x1, y1, x2, y2 = bbox
    center_x = 0.5 * (x1 + x2)
    center_y = 0.5 * (y1 + y2)
    width = x2 - x1
    height = y2 - y1
    theta_fit = calibration["theta_from_optical_center_x"]
    radius_fit = calibration["radius_from_optical_bbox_height"]
    depth_fit = calibration["depth_to_radius_diagnostic_not_used_for_center"]
    theta = float(theta_fit["slope"]) * center_x + float(theta_fit["intercept"])
    radius_height = float(radius_fit["slope"]) * height + float(radius_fit["intercept"])
    radius_depth = (
        float(depth_fit["slope"]) * depth_median + float(depth_fit["intercept"])
        if math.isfinite(depth_median)
        else radius_height
    )
    theta_half = max(8.0, float(theta_fit["p95_abs_error"]) + 3.0)
    radial_allowance = max(float(radius_fit["p95_abs_error"]), float(depth_fit["p95_abs_error"])) + 70.0
    mapping_status = "INDEPENDENT_PV004_SAME_SCENE_PROXY"
    if scene != calibration["scene"]:
        theta_half += float(uncertainty["theta_cross_scene_extra_deg"])
        radial_allowance += float(uncertainty["radial_cross_scene_extra_px"])
        mapping_status = "CROSS_SCENE_UNVALIDATED_PV004_PROXY"
    visibility_multiplier = float(uncertainty["partial_visibility_multiplier"]) if visibility != "full_visible" else 1.0
    multiplier = max(visibility_multiplier, bbox_multiplier)
    radial_lower = max(0.0, min(radius_height, radius_depth) - radial_allowance)
    radial_upper = min(FAN_RADIUS_PX, max(radius_height, radius_depth) + radial_allowance)
    radius = 0.5 * (radial_lower + radial_upper)
    radial_half = max(120.0, 0.5 * (radial_upper - radial_lower)) * multiplier
    theta_half *= multiplier
    center_sar_x, center_sar_y = fan_xy(radius, theta)
    return {
        "optical_center_x_px": center_x,
        "optical_center_y_px": center_y,
        "optical_width_px": width,
        "optical_height_px": height,
        "predicted_theta_deg": theta,
        "theta_half_width_deg": theta_half,
        "predicted_radius_px": radius,
        "radial_half_width_px": radial_half,
        "predicted_radius_from_optical_height_px": radius_height,
        "predicted_radius_from_depth_proxy_px": radius_depth,
        "predicted_center_x_px": float(center_sar_x),
        "predicted_center_y_px": float(center_sar_y),
        "unsigned_axis_center_deg": theta,
        "unsigned_axis_half_width_deg": 35.0,
        "response_length_min_px": 60.0,
        "response_length_max_px": 300.0,
        "response_width_min_px": 18.0,
        "response_width_max_px": 150.0,
        "mapping_status": mapping_status,
    }


def condition_shell(geometry: dict[str, Any], context_expansion: float = 0.0) -> np.ndarray:
    radius_center = float(geometry["predicted_radius_px"])
    extra_theta = math.degrees(context_expansion / max(radius_center, 80.0))
    return annular_sector_mask(
        float(geometry["predicted_theta_deg"]),
        float(geometry["theta_half_width_deg"]) + extra_theta,
        radius_center,
        float(geometry["radial_half_width_px"]) + context_expansion,
    )


def lifecycle_sar_bounds(entry_optical: int, exit_optical: int) -> tuple[int, int]:
    start = int(math.ceil(entry_optical * 50.0 / 24.0 - 1e-9))
    end = int(math.floor(exit_optical * 50.0 / 24.0 + 1e-9))
    return max(0, start), min(765, end)


def lifecycle_state(
    sar_frame: int,
    lifecycle_start: int,
    lifecycle_end: int,
    visibility: str,
    entry_span: int,
    exit_span: int,
    closure_grace: int,
) -> tuple[str, str]:
    if sar_frame < lifecycle_start:
        return "ABSENT", "PRE_ENTRY_OPTICAL_LIFECYCLE"
    if sar_frame <= lifecycle_start + entry_span - 1:
        return "ENTERING_PROVISIONAL", "OPTICAL_ENTRY_WITH_VALID_TIME_MAP"
    if sar_frame <= lifecycle_end - exit_span:
        if visibility in {"partial_visible", "fully_occluded", "visible_but_unboxed"}:
            return "ACTIVE_WEAK_OR_OCCLUDED", f"OPTICAL_{visibility.upper()}"
        return "ACTIVE_CONFIRMED", "OPTICAL_IDENTITY_ACTIVE"
    if sar_frame <= lifecycle_end + closure_grace:
        return "EXITING", "OPTICAL_EXIT_BOUNDARY_OR_FROZEN_GRACE"
    return "CLOSED", "OPTICAL_LIFECYCLE_ENDED"


def component_orientation(component: np.ndarray) -> tuple[float, float, float, float, float]:
    ys, xs = np.nonzero(component)
    if xs.size < 3:
        return math.nan, 0.0, 0.0, math.nan, math.nan
    points = np.column_stack([xs, ys]).astype(np.float32)
    rect = cv2.minAreaRect(points)
    (_, _), (width, height), angle = rect
    length = max(width, height)
    thickness = min(width, height)
    if width < height:
        angle += 90.0
    angle %= 180.0
    return float(angle), float(length), float(thickness), float(np.mean(xs)), float(np.mean(ys))


def angular_distance_mod180(left: float, right: float) -> float:
    difference = abs((left - right) % 180.0)
    return min(difference, 180.0 - difference)


__all__ = [
    "FAN_HEIGHT", "FAN_WIDTH", "REPO_ROOT", "SCENES", "angular_distance_mod180",
    "bbox_from_state", "build_condition_geometry", "combined_visibility", "compact_ranges",
    "component_orientation", "condition_shell", "fmt", "imaging_valid_mask", "interpolate_bbox",
    "lifecycle_sar_bounds", "lifecycle_state", "load_json", "parse_ranges", "read_csv", "require",
    "resolve", "robust_median_mad", "sample_depth", "sha256_file", "verify_git_gate",
    "warp_translation", "write_csv", "write_json",
]
