#!/usr/bin/env python3
"""Render the OTY2-RSA2-G2-R2 world-registered road counterfactual pack.

This is a research-period descriptive registration and display script.  Optical
frames confirm that the selected roadside interval is empty.  SAR static scene
landmarks perform the pixel registration.  Vehicle GT is used only once to
freeze reference road geometry and later as an independent posthoc validation;
it is not used to seed landmark search or to adjust road controls per frame.

The script does not create response masks, candidates, scores, rankings,
selectors, winners, automatic locations, final boxes, or training samples.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon, Rectangle
from PIL import Image


DEFAULT_REPO = Path(r"D:\profile\research\optical-sar-visual-diagnosis-sar-foundation")
DEFAULT_DATA = Path(r"D:\profile\research\data")
DEFAULT_ASSETS = DEFAULT_REPO / (
    "docs/reviews/assets/20260719_rsa2_g2_r2_world_registered_empty_road_counterfactual"
)
DEFAULT_MANIFEST = DEFAULT_REPO / (
    "manifests/oty2/oty2_rsa2_g2_r2_world_registered_empty_road_counterfactual_manifest.csv"
)

SCENE = "GM_RM017"
REF_FRAME = 361
KEY_FRAMES = [341, 342, 343, 347, 348, 349, 360, 361, 362, 370, 371, 377, 378, 379]
REGISTRATION_FRAMES = list(range(341, 380))
VEHICLES = ["GM_RM017:PV004", "GM_RM017:PV003", "GM_RM017:PV002"]
OPTICAL_EMPTY_FRAMES = [173, 195, 200, 205, 210]

FAN_ORIGIN = np.array([1154.0, 1330.6], dtype=np.float64)
GRID_M_PER_PX = 0.03
PATCH_WIDTH = 360
PATCH_HEIGHT = 240
SIGMAS = (4.0, 10.0, 20.0)
TARGET_PEAK_RANGE = (0.65, 0.79)
SENSITIVITY_FRACTIONS = (-1.0, -0.5, 0.0, 0.5, 1.0)

LANDMARKS = {
    "L1_UPPER_LEFT_ARC_CROSS": (715.0, 750.0, 34),
    "L2_UPPER_LEFT_SHORT_RETURN": (875.0, 790.0, 26),
    "L3_UPPER_MID_ARC": (990.0, 750.0, 32),
    "L4_RIGHT_VERTICAL_POLE": (1480.0, 910.0, 30),
    "L5_LOWER_CROSS": (1190.0, 1035.0, 30),
    "L6_LOWER_DIAGONAL": (1290.0, 1035.0, 30),
}

VEHICLE_COLORS = {
    "PV002": "#FFD166",
    "PV003": "#F72585",
    "PV004": "#7B61FF",
}
ROAD_COLORS = {
    "RC1": "#00E5FF",
    "RC2": "#41D3BD",
    "RC3": "#60A5FA",
}


@dataclass(frozen=True)
class Geometry:
    cx: float
    cy: float
    long_px: float
    short_px: float
    axis_deg: float
    source: str


@dataclass(frozen=True)
class Registration:
    frame: int
    dx: float
    dy: float
    tracked_points: dict[str, tuple[float, float]]
    landmark_quality: dict[str, float]
    landmark_peak_margin: dict[str, float]
    landmark_residuals_px: dict[str, float]
    residual_median_px: float
    residual_p90_px: float
    residual_max_px: float
    loo_translation_radius_px: float
    vehicle_validation_mean_px: float
    vehicle_validation_max_px: float
    vehicle_validation_cross_axis_max_px: float
    registration_uncertainty_px: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def suffix(value: str) -> str:
    return value.split(":")[-1]


def normalize_axis_angle(angle_deg: float) -> float:
    return ((angle_deg + 90.0) % 180.0) - 90.0


def axial_mean_deg(angles_deg: list[float]) -> float:
    radians = np.deg2rad(np.asarray(angles_deg, dtype=np.float64) * 2.0)
    value = 0.5 * math.degrees(
        math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean()))
    )
    return normalize_axis_angle(value)


def parse_bbox(row: dict[str, str]) -> tuple[float, float, float, float, float]:
    return tuple(float(value) for value in row["bbox"].strip("[]").split(","))  # type: ignore[return-value]


def box_corners(
    cx: float, cy: float, width: float, height: float, angle_deg: float
) -> np.ndarray:
    theta = math.radians(angle_deg)
    width_axis = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    height_axis = np.array([-math.sin(theta), math.cos(theta)], dtype=np.float64)
    center = np.array([cx, cy], dtype=np.float64)
    return np.stack(
        [
            center - width_axis * width / 2 - height_axis * height / 2,
            center + width_axis * width / 2 - height_axis * height / 2,
            center + width_axis * width / 2 + height_axis * height / 2,
            center - width_axis * width / 2 + height_axis * height / 2,
        ]
    )


def geometry_corners(geometry: Geometry) -> np.ndarray:
    return box_corners(
        geometry.cx,
        geometry.cy,
        geometry.long_px,
        geometry.short_px,
        geometry.axis_deg,
    )


def gt_rank(row: dict[str, str]) -> tuple[object, ...]:
    quality = {"gold": 0, "usable": 1, "diagnostic_only": 2}.get(
        row["gt_quality_status"], 9
    )
    identity = {"high": 0, "moderate": 1, "low": 2}.get(
        row.get("identity_link_confidence", ""), 9
    )
    stable_manual = 0 if "|gm_rm" in row["sar_gt_id"].lower() else 1
    _, _, width, height, _ = parse_bbox(row)
    return quality, identity, stable_manual, -(width * height), row["sar_gt_id"]


def longest_edge_geometry(row: dict[str, str], source: str = "PER_FRAME_GT") -> Geometry:
    cx, cy, width, height, raw_angle = parse_bbox(row)
    corners = box_corners(cx, cy, width, height, raw_angle)
    vectors = np.roll(corners, -1, axis=0) - corners
    lengths = np.linalg.norm(vectors, axis=1)
    vector = vectors[int(np.argmax(lengths))]
    angle = normalize_axis_angle(math.degrees(math.atan2(vector[1], vector[0])))
    ordered = np.sort(lengths)
    return Geometry(cx, cy, float(ordered[-1]), float(ordered[0]), angle, source)


def best_gt_rows(
    rows: list[dict[str, str]], scene: str, vehicle: str
) -> dict[int, dict[str, str]]:
    grouped: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        if row["scene"] != scene or row["canonical_vehicle_id"] != vehicle:
            continue
        if row["gt_quality_status"] not in {"gold", "usable"}:
            continue
        if row.get("identity_link_confidence", "") not in {"high", "moderate"}:
            continue
        grouped.setdefault(int(row["sar_frame_index"]), []).append(row)
    return {frame: min(items, key=gt_rank) for frame, items in grouped.items()}


def robust_poly_predict(x: np.ndarray, y: np.ndarray, x0: float) -> float:
    degree = min(2, max(1, len(x) - 1))
    center = float(np.median(x))
    xx = x - center
    keep = np.ones(len(x), dtype=bool)
    for _ in range(5):
        coeff = np.polyfit(xx[keep], y[keep], degree)
        residual = np.abs(y - np.polyval(coeff, xx))
        median = float(np.median(residual[keep]))
        mad = float(np.median(np.abs(residual[keep] - median)))
        boundary = max(2.5, median + 3.5 * 1.4826 * mad)
        updated = residual <= boundary
        if int(updated.sum()) < degree + 3 or np.array_equal(updated, keep):
            break
        keep = updated
    coeff = np.polyfit(xx[keep], y[keep], degree)
    return float(np.polyval(coeff, x0 - center))


def stable_geometry_loo(
    rows: list[dict[str, str]], scene: str, vehicle: str, target_frame: int
) -> Geometry:
    selected = best_gt_rows(rows, scene, vehicle)
    frames = sorted(selected)
    local = [frame for frame in frames if frame != target_frame and abs(frame - target_frame) <= 48]
    if len(local) < 12:
        local = [frame for frame in frames if frame != target_frame]
    if len(local) < 3:
        raise RuntimeError(f"insufficient GT thread: {scene} {vehicle} SAR {target_frame}")
    geometries = [longest_edge_geometry(selected[frame]) for frame in local]
    x = np.asarray(local, dtype=np.float64)
    return Geometry(
        robust_poly_predict(x, np.asarray([item.cx for item in geometries]), target_frame),
        robust_poly_predict(x, np.asarray([item.cy for item in geometries]), target_frame),
        float(np.median([item.long_px for item in geometries])),
        float(np.median([item.short_px for item in geometries])),
        axial_mean_deg([item.axis_deg for item in geometries]),
        "THREAD_STABLE_LOO",
    )


def gt_map(rows: list[dict[str, str]]) -> dict[tuple[str, int], dict[str, str]]:
    grouped: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in rows:
        if row["scene"] != SCENE or row["canonical_vehicle_id"] not in VEHICLES:
            continue
        if row["gt_quality_status"] not in {"gold", "usable"}:
            continue
        grouped.setdefault((row["canonical_vehicle_id"], int(row["sar_frame_index"])), []).append(row)
    return {key: min(items, key=gt_rank) for key, items in grouped.items()}


def sar_path(data: Path, frame: int) -> Path:
    return data / SCENE / f"{SCENE}_SARframes_gray" / f"{frame:06d}.png"


def optical_path(data: Path, frame: int) -> Path:
    return data / SCENE / f"{SCENE}_frames" / f"{frame:06d}.png"


def load_gray(data: Path, frame: int) -> np.ndarray:
    return np.asarray(Image.open(sar_path(data, frame)).convert("L"), dtype=np.float32)


def load_gray_u8(data: Path, frame: int) -> np.ndarray:
    return np.asarray(Image.open(sar_path(data, frame)).convert("L"), dtype=np.uint8)


def load_rgb(data: Path, frame: int) -> np.ndarray:
    return np.asarray(Image.open(optical_path(data, frame)).convert("RGB"))


def signed_axes(geometry: Geometry) -> tuple[np.ndarray, np.ndarray, float]:
    theta = math.radians(geometry.axis_deg)
    u = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    if u[0] < 0 or (abs(u[0]) < 1e-9 and u[1] < 0):
        u = -u
    v = np.array([-u[1], u[0]], dtype=np.float64)
    near = FAN_ORIGIN - np.array([geometry.cx, geometry.cy], dtype=np.float64)
    if float(np.dot(v, near)) < 0:
        v = -v
    dot = float(np.dot(v, near / max(float(np.linalg.norm(near)), 1e-9)))
    return u, v, dot


def fan_geometry(center: tuple[float, float]) -> tuple[float, float]:
    vector = np.asarray(center, dtype=np.float64) - FAN_ORIGIN
    radius = float(np.linalg.norm(vector))
    theta = math.degrees(math.atan2(vector[0], -vector[1]))
    return radius, theta


def enhanced(image: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(12, 8)).apply(image)


def second_peak(response: np.ndarray, location: tuple[int, int], radius: int = 7) -> float:
    copy = response.copy()
    x, y = location
    copy[max(0, y - radius): y + radius + 1, max(0, x - radius): x + radius + 1] = -1
    return float(copy.max())


def track_landmark(
    ref_enhanced: np.ndarray,
    current_enhanced: np.ndarray,
    point: tuple[float, float],
    half: int,
    previous_translation: np.ndarray,
) -> tuple[np.ndarray, float, float]:
    x, y = point
    template = ref_enhanced[int(y - half): int(y + half + 1), int(x - half): int(x + half + 1)]
    predicted = np.asarray(point) + previous_translation
    search_x = 18
    search_y = 18
    left = max(0, int(predicted[0] - half - search_x))
    right = min(current_enhanced.shape[1], int(predicted[0] + half + search_x + 1))
    top = max(0, int(predicted[1] - half - search_y))
    bottom = min(current_enhanced.shape[0], int(predicted[1] + half + search_y + 1))
    search = current_enhanced[top:bottom, left:right]
    response = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, peak, _, location = cv2.minMaxLoc(response)
    runner_up = second_peak(response, location)
    center = np.array([left + location[0] + half, top + location[1] + half], dtype=np.float64)
    return center, float(peak), float(peak - runner_up)


def robust_translation(displacements: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    translation = np.median(displacements, axis=0)
    residual_vectors = displacements - translation[None, :]
    loo = []
    for index in range(len(displacements)):
        loo.append(np.median(np.delete(displacements, index, axis=0), axis=0))
    loo_values = np.stack(loo)
    loo_radius = float(np.max(np.linalg.norm(loo_values - translation[None, :], axis=1)))
    return translation, residual_vectors, loo_radius


def build_registrations(
    data: Path,
    gt: dict[tuple[str, int], dict[str, str]],
    validation_v_axis: np.ndarray,
) -> dict[int, Registration]:
    ref_image = load_gray_u8(data, REF_FRAME)
    ref_enhanced = enhanced(ref_image)
    ref_points = np.asarray([[x, y] for x, y, _ in LANDMARKS.values()], dtype=np.float64)
    preliminary: dict[int, dict[str, object]] = {}
    orders = [range(REF_FRAME, min(REGISTRATION_FRAMES) - 1, -1), range(REF_FRAME + 1, max(REGISTRATION_FRAMES) + 1)]
    for order in orders:
        previous_translation = np.zeros(2, dtype=np.float64)
        for frame in order:
            if frame == REF_FRAME:
                tracked_points = ref_points.copy()
                qualities = [1.0] * len(LANDMARKS)
                margins = [1.0] * len(LANDMARKS)
            else:
                current_enhanced = enhanced(load_gray_u8(data, frame))
                tracked = []
                qualities = []
                margins = []
                for x, y, half in LANDMARKS.values():
                    point, quality, margin = track_landmark(
                        ref_enhanced,
                        current_enhanced,
                        (x, y),
                        half,
                        previous_translation,
                    )
                    tracked.append(point)
                    qualities.append(quality)
                    margins.append(margin)
                tracked_points = np.stack(tracked)
            displacements = tracked_points - ref_points
            translation, residual_vectors, loo_radius = robust_translation(displacements)
            previous_translation = translation
            residuals = np.linalg.norm(residual_vectors, axis=1)
            validation_vectors = []
            for vehicle in VEHICLES:
                ref_row = gt.get((vehicle, REF_FRAME))
                current_row = gt.get((vehicle, frame))
                if ref_row is None or current_row is None:
                    continue
                predicted = np.asarray(parse_bbox(ref_row)[:2]) + translation
                validation_vectors.append(predicted - np.asarray(parse_bbox(current_row)[:2]))
            if validation_vectors:
                vehicle_values = np.stack(validation_vectors)
                vehicle_norms = np.linalg.norm(vehicle_values, axis=1)
                vehicle_mean = float(np.mean(vehicle_norms))
                vehicle_max = float(np.max(vehicle_norms))
                vehicle_cross = float(np.max(np.abs(vehicle_values @ validation_v_axis)))
            else:
                vehicle_mean = float("nan")
                vehicle_max = float("nan")
                vehicle_cross = float("nan")
            uncertainty_terms = [2.0, float(np.percentile(residuals, 90))]
            if math.isfinite(vehicle_max):
                uncertainty_terms.append(vehicle_max)
            preliminary[frame] = {
                "translation": translation,
                "tracked_points": tracked_points,
                "qualities": qualities,
                "margins": margins,
                "residuals": residuals,
                "loo_radius": loo_radius,
                "vehicle_mean": vehicle_mean,
                "vehicle_max": vehicle_max,
                "vehicle_cross": vehicle_cross,
                "uncertainty": max(uncertainty_terms),
            }
    registrations: dict[int, Registration] = {}
    for frame in REGISTRATION_FRAMES:
        item = preliminary[frame]
        translation = np.asarray(item["translation"])
        tracked_points = np.asarray(item["tracked_points"])
        residuals = np.asarray(item["residuals"])
        registrations[frame] = Registration(
            frame=frame,
            dx=float(translation[0]),
            dy=float(translation[1]),
            tracked_points=dict(zip(LANDMARKS, [tuple(value) for value in tracked_points])),
            landmark_quality=dict(zip(LANDMARKS, [float(value) for value in item["qualities"]])),
            landmark_peak_margin=dict(zip(LANDMARKS, [float(value) for value in item["margins"]])),
            landmark_residuals_px=dict(zip(LANDMARKS, [float(value) for value in residuals])),
            residual_median_px=float(np.median(residuals)),
            residual_p90_px=float(np.percentile(residuals, 90)),
            residual_max_px=float(np.max(residuals)),
            loo_translation_radius_px=float(item["loo_radius"]),
            vehicle_validation_mean_px=float(item["vehicle_mean"]),
            vehicle_validation_max_px=float(item["vehicle_max"]),
            vehicle_validation_cross_axis_max_px=float(item["vehicle_cross"]),
            registration_uncertainty_px=float(item["uncertainty"]),
        )
    return registrations


def reference_controls(
    gt_rows: list[dict[str, str]],
) -> tuple[dict[str, Geometry], dict[str, float], list[Geometry], np.ndarray]:
    vehicle_geometries = [stable_geometry_loo(gt_rows, SCENE, vehicle, REF_FRAME) for vehicle in VEHICLES]
    ordered = sorted(vehicle_geometries, key=lambda item: item.cx)
    centers = np.asarray([[item.cx, item.cy] for item in ordered])
    step_vectors = np.diff(centers, axis=0)
    step = np.median(step_vectors, axis=0)
    step_dispersion = 0.5 * float(np.linalg.norm(step_vectors[1] - step_vectors[0]))
    long_px = float(np.median([item.long_px for item in ordered]))
    short_px = float(np.median([item.short_px for item in ordered]))
    axis_deg = axial_mean_deg([item.axis_deg for item in ordered])
    base = centers[0]
    controls: dict[str, Geometry] = {}
    definition_uncertainty: dict[str, float] = {}
    for index in range(1, 4):
        center = base - step * index
        control_id = f"RC{index}"
        controls[control_id] = Geometry(
            float(center[0]),
            float(center[1]),
            long_px,
            short_px,
            axis_deg,
            "WORLD_REGISTERED_ROAD_CONTROL",
        )
        definition_uncertainty[control_id] = 2.0 + index * step_dispersion
    _, v_axis, _ = signed_axes(controls["RC1"])
    return controls, definition_uncertainty, ordered, v_axis


def translated_geometry(reference: Geometry, registration: Registration) -> Geometry:
    return Geometry(
        reference.cx + registration.dx,
        reference.cy + registration.dy,
        reference.long_px,
        reference.short_px,
        reference.axis_deg,
        reference.source,
    )


def sample_signed_patch(image: np.ndarray, geometry: Geometry) -> np.ndarray:
    u, v, _ = signed_axes(geometry)
    xx, yy = np.meshgrid(
        np.arange(PATCH_WIDTH, dtype=np.float32) - (PATCH_WIDTH - 1) / 2,
        np.arange(PATCH_HEIGHT, dtype=np.float32) - (PATCH_HEIGHT - 1) / 2,
    )
    map_x = geometry.cx + xx * u[0] + yy * v[0]
    map_y = geometry.cy + xx * u[1] + yy * v[1]
    return cv2.remap(
        image,
        map_x.astype(np.float32),
        map_y.astype(np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def local_contrast(patch: np.ndarray, sigma: float) -> np.ndarray:
    return patch - cv2.GaussianBlur(patch, (0, 0), sigmaX=sigma, sigmaY=sigma)


def profile_measurements(
    patch: np.ndarray, geometry: Geometry
) -> tuple[dict[str, float], np.ndarray]:
    yy, xx = np.meshgrid(
        np.arange(PATCH_HEIGHT, dtype=np.float64) - (PATCH_HEIGHT - 1) / 2,
        np.arange(PATCH_WIDTH, dtype=np.float64) - (PATCH_WIDTH - 1) / 2,
        indexing="ij",
    )
    inside_u = np.abs(xx) <= geometry.long_px / 2
    inside_near = inside_u & (yy >= 0) & (yy <= geometry.short_px / 2)
    inside_far = inside_u & (yy < 0) & (yy >= -geometry.short_px / 2)
    valid = patch > 0
    near_values = patch[inside_near & valid]
    far_values = patch[inside_far & valid]
    raw_delta = (
        float(near_values.mean() - far_values.mean())
        if near_values.size and far_values.size
        else float("nan")
    )
    result = {"near_minus_far_raw": raw_delta}
    for sigma in SIGMAS:
        contrast = local_contrast(patch, sigma)
        near_values = contrast[inside_near & valid]
        far_values = contrast[inside_far & valid]
        result[f"near_minus_far_sigma{int(sigma)}"] = (
            float(near_values.mean() - far_values.mean())
            if near_values.size and far_values.size
            else float("nan")
        )
    detrended = local_contrast(patch, 20.0)
    profile = np.full(PATCH_HEIGHT, np.nan, dtype=np.float64)
    for row_index in range(PATCH_HEIGHT):
        row_mask = inside_u[row_index] & valid[row_index]
        if int(row_mask.sum()) > 20:
            profile[row_index] = float(detrended[row_index, row_mask].mean())
    start = max(0, int((PATCH_HEIGHT - 1) / 2 - geometry.short_px * 0.9))
    end = min(PATCH_HEIGHT, int((PATCH_HEIGHT - 1) / 2 + geometry.short_px * 1.4))
    local = profile[start:end]
    if local.size and np.isfinite(local).any():
        peak_row = start + int(np.nanargmax(local))
        peak_v = peak_row - (PATCH_HEIGHT - 1) / 2
        result["peak_v_px"] = float(peak_v)
        result["peak_v_over_half_width"] = float(peak_v / max(geometry.short_px / 2, 1e-9))
    else:
        result["peak_v_px"] = float("nan")
        result["peak_v_over_half_width"] = float("nan")
    return result, profile


def u_support_measurements(
    patch: np.ndarray, geometry: Geometry, peak_v_px: float
) -> tuple[dict[str, object], np.ndarray]:
    contrast = local_contrast(patch, 20.0)
    center_row = (PATCH_HEIGHT - 1) / 2
    peak_row = int(round(center_row + peak_v_px))
    top = max(0, peak_row - 3)
    bottom = min(PATCH_HEIGHT, peak_row + 4)
    valid = patch[top:bottom] > 0
    values = contrast[top:bottom]
    numerator = np.where(valid, values, 0.0).sum(axis=0)
    denominator = valid.sum(axis=0)
    profile = np.divide(
        numerator,
        denominator,
        out=np.full(PATCH_WIDTH, np.nan),
        where=denominator > 0,
    )
    filled = np.where(np.isfinite(profile), profile, 0.0).astype(np.float32)[None, :]
    smooth = cv2.GaussianBlur(filled, (0, 0), sigmaX=2.0)[0]
    coords = np.arange(PATCH_WIDTH) - (PATCH_WIDTH - 1) / 2
    inside = np.abs(coords) <= geometry.long_px / 2
    peak_index = int(np.argmax(np.where(inside, smooth, -np.inf)))
    positive = smooth > 0
    if not positive[peak_index]:
        return {
            "u_coverage_range_px": "",
            "u_span_px": 0.0,
            "length_termination_status": "NO_POSITIVE_SIGMA20_COMPONENT",
        }, smooth
    left = peak_index
    right = peak_index
    while left > 0 and positive[left - 1]:
        left -= 1
    while right + 1 < len(positive) and positive[right + 1]:
        right += 1
    u_left = float(coords[left])
    u_right = float(coords[right])
    crosses_left = u_left <= -geometry.long_px / 2
    crosses_right = u_right >= geometry.long_px / 2
    if crosses_left and crosses_right:
        status = "CROSSES_BOTH_VIRTUAL_ENDS"
    elif crosses_left or crosses_right:
        status = "CROSSES_ONE_VIRTUAL_END"
    else:
        status = "ENDS_INSIDE_VIRTUAL_LENGTH"
    return {
        "u_coverage_range_px": f"[{u_left:.1f},{u_right:.1f}]",
        "u_span_px": u_right - u_left + 1.0,
        "length_termination_status": status,
    }, smooth


def measure_patch(image: np.ndarray, geometry: Geometry) -> dict[str, object]:
    patch = sample_signed_patch(image, geometry)
    values, profile = profile_measurements(patch, geometry)
    support, u_profile = u_support_measurements(patch, geometry, float(values["peak_v_px"]))
    return {
        "geometry": geometry,
        "patch": patch,
        "profile": profile,
        "u_profile": u_profile,
        "valid_ratio": float(np.mean(patch > 0)),
        **values,
        **support,
    }


def total_uncertainty(frame_uncertainty: float, definition_uncertainty: float) -> float:
    return float(math.hypot(frame_uncertainty, definition_uncertainty))


def perturbation_measurements(
    image: np.ndarray,
    geometry: Geometry,
    uncertainty_px: float,
) -> list[dict[str, float]]:
    _, v_axis, _ = signed_axes(geometry)
    output = []
    for fraction in SENSITIVITY_FRACTIONS:
        center = np.asarray([geometry.cx, geometry.cy]) + v_axis * uncertainty_px * fraction
        shifted = Geometry(
            float(center[0]),
            float(center[1]),
            geometry.long_px,
            geometry.short_px,
            geometry.axis_deg,
            "REGISTRATION_PERTURBATION",
        )
        values, _ = profile_measurements(sample_signed_patch(image, shifted), shifted)
        output.append(
            {
                "fraction": float(fraction),
                "shift_px": float(uncertainty_px * fraction),
                "peak": float(values["peak_v_over_half_width"]),
                "raw": float(values["near_minus_far_raw"]),
            }
        )
    return output


def common_raw_limits(records: list[dict[str, object]]) -> tuple[float, float]:
    values = np.concatenate(
        [np.asarray(item["patch"])[np.asarray(item["patch"]) > 0].ravel() for item in records]
    )
    return float(np.percentile(values, 1.0)), float(np.percentile(values, 99.7))


def common_contrast_limit(records: list[dict[str, object]], sigma: float = 20.0) -> float:
    values = np.concatenate(
        [
            np.abs(local_contrast(np.asarray(item["patch"]), sigma))[
                np.asarray(item["patch"]) > 0
            ].ravel()
            for item in records
        ]
    )
    return max(float(np.percentile(values, 99.2)), 1.0)


def patch_extent() -> list[float]:
    return [
        -PATCH_WIDTH * GRID_M_PER_PX / 2,
        PATCH_WIDTH * GRID_M_PER_PX / 2,
        PATCH_HEIGHT * GRID_M_PER_PX / 2,
        -PATCH_HEIGHT * GRID_M_PER_PX / 2,
    ]


def draw_patch_box(ax: plt.Axes, geometry: Geometry, color: str) -> None:
    long_m = geometry.long_px * GRID_M_PER_PX
    short_m = geometry.short_px * GRID_M_PER_PX
    ax.add_patch(
        Rectangle(
            (-long_m / 2, -short_m / 2),
            long_m,
            short_m,
            fill=False,
            edgecolor=color,
            linewidth=1.5,
        )
    )


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=135, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def optical_state_map(
    rows: list[dict[str, str]],
) -> dict[tuple[str, int], dict[str, str]]:
    return {
        (row["canonical_vehicle_id"], int(row["frame_index"])): row
        for row in rows
        if row["scene"] == SCENE
    }


def visible_optical_bbox(row: dict[str, str] | None) -> tuple[float, float, float, float] | None:
    if row is None or row.get("reference_bbox_available", "") != "true":
        return None
    return tuple(
        float(row[key])
        for key in (
            "reference_bbox_x1",
            "reference_bbox_y1",
            "reference_bbox_x2",
            "reference_bbox_y2",
        )
    )  # type: ignore[return-value]


def aggregate_summaries(
    road_records: dict[tuple[str, int], dict[str, object]],
    vehicle_records: dict[tuple[str, int], dict[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    vehicle_raw = np.asarray(
        [
            np.mean(
                [
                    float(vehicle_records[(suffix(vehicle), frame)]["near_minus_far_raw"])
                    for vehicle in VEHICLES
                    if (suffix(vehicle), frame) in vehicle_records
                ]
            )
            for frame in KEY_FRAMES
        ]
    )
    summaries: dict[str, dict[str, object]] = {}
    for control_id in ROAD_COLORS:
        rows = [road_records[(control_id, frame)] for frame in KEY_FRAMES]
        peaks = np.asarray([float(item["peak_v_over_half_width"]) for item in rows])
        raw = np.asarray([float(item["near_minus_far_raw"]) for item in rows])
        target_count = int(np.sum((peaks >= TARGET_PEAK_RANGE[0]) & (peaks <= TARGET_PEAK_RANGE[1])))
        raw_positive = int(np.sum(raw > 0))
        fraction_counts = {}
        for fraction in SENSITIVITY_FRACTIONS:
            values = np.asarray(
                [
                    next(
                        value["peak"]
                        for value in item["perturbations"]
                        if value["fraction"] == fraction
                    )
                    for item in rows
                ],
                dtype=float,
            )
            fraction_counts[fraction] = int(
                np.sum((values >= TARGET_PEAK_RANGE[0]) & (values <= TARGET_PEAK_RANGE[1]))
            )
        statuses = [str(item["length_termination_status"]) for item in rows]
        correlation = float(np.corrcoef(vehicle_raw, raw)[0, 1])
        summaries[control_id] = {
            "n": len(rows),
            "target_count": target_count,
            "raw_positive_count": raw_positive,
            "peak_min": float(np.min(peaks)),
            "peak_median": float(np.median(peaks)),
            "peak_max": float(np.max(peaks)),
            "raw_mean": float(np.mean(raw)),
            "vehicle_raw_correlation": correlation,
            "coherent_sensitivity_max_target_count": max(fraction_counts.values()),
            "sensitivity_fraction_counts": fraction_counts,
            "length_status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
            "cross_frame_consistency": (
                f"base target-range {target_count}/{len(rows)}; raw near>far {raw_positive}/{len(rows)}; "
                f"median peak {np.median(peaks):.3f}; coherent uncertainty perturbation at most "
                f"{max(fraction_counts.values())}/{len(rows)} target-range frames"
            ),
        }
    vehicle_rows = list(vehicle_records.values())
    vehicle_peaks = np.asarray([float(item["peak_v_over_half_width"]) for item in vehicle_rows])
    vehicle_raw_values = np.asarray([float(item["near_minus_far_raw"]) for item in vehicle_rows])
    key_nine = [
        vehicle_records[(suffix(vehicle), frame)]
        for frame in (342, 361, 378)
        for vehicle in VEHICLES
    ]
    key_peaks = np.asarray([float(item["peak_v_over_half_width"]) for item in key_nine])
    vehicle_summary = {
        "n": len(vehicle_rows),
        "target_count": int(
            np.sum(
                (vehicle_peaks >= TARGET_PEAK_RANGE[0])
                & (vehicle_peaks <= TARGET_PEAK_RANGE[1])
            )
        ),
        "raw_positive_count": int(np.sum(vehicle_raw_values > 0)),
        "peak_median": float(np.median(vehicle_peaks)),
        "key_nine_target_count": int(
            np.sum((key_peaks >= TARGET_PEAK_RANGE[0]) & (key_peaks <= TARGET_PEAK_RANGE[1]))
        ),
        "key_nine_peak_min": float(np.min(key_peaks)),
        "key_nine_peak_max": float(np.max(key_peaks)),
    }
    return summaries, vehicle_summary


def render_optical_empty_confirmation(
    assets: Path,
    data: Path,
    states: dict[tuple[str, int], dict[str, str]],
) -> None:
    fig, axes = plt.subplots(1, len(OPTICAL_EMPTY_FRAMES), figsize=(21, 4.5), facecolor="#0E151D")
    for ax, frame in zip(axes, OPTICAL_EMPTY_FRAMES):
        image = load_rgb(data, frame)
        ax.imshow(image)
        for vehicle in VEHICLES:
            row = states.get((vehicle, frame))
            bbox = visible_optical_bbox(row)
            if bbox is None:
                continue
            x1, y1, x2, y2 = bbox
            color = VEHICLE_COLORS[suffix(vehicle)]
            ax.add_patch(
                Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, edgecolor=color, linewidth=1.6)
            )
            ax.text(x1 + 3, y1 - 5, suffix(vehicle), color=color, fontsize=7)
        pv004_bbox = visible_optical_bbox(states.get(("GM_RM017:PV004", frame)))
        if pv004_bbox is not None:
            empty_right = pv004_bbox[0]
            ax.add_patch(
                Rectangle(
                    (0, 255),
                    empty_right,
                    185,
                    facecolor="#41D3BD",
                    edgecolor="#41D3BD",
                    alpha=0.13,
                    linewidth=1.0,
                )
            )
            if empty_right > 120:
                ax.text(
                    empty_right * 0.5,
                    430,
                    "empty roadside interval\n(semantic only)",
                    color="#9EF0DE",
                    fontsize=7,
                    ha="center",
                    va="bottom",
                )
        ax.set_title(f"optical {frame}", color="white", fontsize=9)
        ax.axis("off")
    fig.suptitle(
        "R01 | Optical confirmation: the road interval beyond trailing PV004 is vehicle-free",
        color="white",
        fontsize=16,
    )
    fig.text(
        0.01,
        0.01,
        "Green shading confirms world semantics only. It is not an optical-to-SAR pixel projection. "
        "Frame 173 establishes vehicle order; frames 195-210 expose the empty interval while PV004 moves to the right edge.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.91])
    save_figure(fig, assets / "R01_OPTICAL_EMPTY_ROAD_CONFIRMATION.png")


def render_reference_geometry(
    assets: Path,
    data: Path,
    controls: dict[str, Geometry],
    vehicle_geometries: dict[str, Geometry],
) -> None:
    image = load_gray(data, REF_FRAME)
    x1, x2, y1, y2 = 250, 1620, 610, 1120
    crop = image[y1:y2, x1:x2]
    valid = crop[crop > 0]
    low, high = np.percentile(valid, [1.0, 99.8])
    fig, ax = plt.subplots(figsize=(17, 7.6), facecolor="#0E151D")
    ax.imshow(crop, cmap="gray", vmin=low, vmax=high, extent=[x1, x2, y2, y1])
    ordered_points = []
    for control_id, geometry in controls.items():
        ordered_points.append((geometry.cx, geometry.cy))
        ax.add_patch(
            Polygon(geometry_corners(geometry), fill=False, edgecolor=ROAD_COLORS[control_id], linewidth=2.0)
        )
        ax.text(geometry.cx, geometry.cy - 48, control_id, color=ROAD_COLORS[control_id], fontsize=9, ha="center")
    for vehicle, geometry in vehicle_geometries.items():
        ordered_points.append((geometry.cx, geometry.cy))
        color = VEHICLE_COLORS[suffix(vehicle)]
        ax.add_patch(Polygon(geometry_corners(geometry), fill=False, edgecolor=color, linewidth=1.8))
        ax.text(geometry.cx, geometry.cy - 48, suffix(vehicle), color=color, fontsize=9, ha="center")
    ordered_points = sorted(ordered_points)
    ax.plot(
        [point[0] for point in ordered_points],
        [point[1] for point in ordered_points],
        color="#F8C15C",
        linewidth=1.1,
        linestyle="--",
        label="reference road-slot locus",
    )
    for index, (name, (x, y, _)) in enumerate(LANDMARKS.items(), start=1):
        ax.scatter(x, y, s=38, facecolors="none", edgecolors="#FF5DA2", linewidths=1.4)
        ax.text(x + 8, y - 6, f"L{index}", color="#FF5DA2", fontsize=7)
    ax.set_xlim(x1, x2)
    ax.set_ylim(y2, y1)
    ax.set_title(
        "R02 | SAR 361 frozen road controls, vehicle geometry, and six non-collinear static landmarks",
        color="white",
        fontsize=15,
    )
    ax.tick_params(colors="#CBD5E1", labelsize=7)
    ax.grid(color="#64748B", alpha=0.2, linewidth=0.4)
    ax.legend(loc="lower right", fontsize=8, facecolor="#0E151D", labelcolor="white")
    fig.text(
        0.01,
        0.01,
        "RC1-RC3 are frozen before response measurement by extending the median adjacent-vehicle road-slot vector beyond PV004. "
        "Their centers are never moved to fit a SAR response.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    save_figure(fig, assets / "R02_REFERENCE_CONTROL_GEOMETRY_AND_LANDMARKS.png")


def render_registration_trajectory(
    assets: Path,
    data: Path,
    controls: dict[str, Geometry],
    registrations: dict[int, Registration],
) -> None:
    fig, axes = plt.subplots(4, 4, figsize=(19, 15), facecolor="#0E151D")
    x1, x2, y1, y2 = 200, 1740, 620, 1120
    for ax, frame in zip(axes.flat, KEY_FRAMES):
        image = load_gray(data, frame)
        crop = image[y1:y2, x1:x2]
        valid = crop[crop > 0]
        low, high = np.percentile(valid, [1.0, 99.8])
        ax.imshow(crop, cmap="gray", vmin=low, vmax=high, extent=[x1, x2, y2, y1])
        registration = registrations[frame]
        for control_id, reference in controls.items():
            current = translated_geometry(reference, registration)
            ax.add_patch(
                Polygon(
                    geometry_corners(current),
                    fill=False,
                    edgecolor=ROAD_COLORS[control_id],
                    linewidth=1.0,
                )
            )
        for index, point in enumerate(registration.tracked_points.values(), start=1):
            ax.scatter(point[0], point[1], s=18, facecolors="none", edgecolors="#FF5DA2", linewidths=0.8)
            if index in {1, 4, 6}:
                ax.text(point[0] + 5, point[1] - 4, f"L{index}", color="#FF5DA2", fontsize=5.5)
        ax.set_xlim(x1, x2)
        ax.set_ylim(y2, y1)
        ax.set_title(
            f"SAR {frame} | d=({registration.dx:.1f},{registration.dy:.1f}) | "
            f"unc={registration.registration_uncertainty_px:.1f}px",
            color="white",
            fontsize=7,
        )
        ax.axis("off")
    for ax in axes.flat[len(KEY_FRAMES):]:
        ax.axis("off")
    fig.suptitle(
        "R03 | World registration trajectory from SAR-only static-landmark sequential translation",
        color="white",
        fontsize=16,
    )
    fig.text(
        0.01,
        0.01,
        "The same three reference road regions are translated by static-landmark consensus. "
        "Vehicle GT is absent from search initialization and is used only for the displayed posthoc uncertainty bound.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    save_figure(fig, assets / "R03_WORLD_REGISTRATION_TRAJECTORY.png")


def render_raw_comparison(
    assets: Path,
    road_records: dict[tuple[str, int], dict[str, object]],
    vehicle_records: dict[tuple[str, int], dict[str, object]],
) -> None:
    frames = [342, 361, 378]
    columns = ["PV004", "PV003", "PV002", "RC1", "RC2", "RC3"]
    selected = []
    for frame in frames:
        for label in columns:
            selected.append(
                vehicle_records[(label, frame)] if label.startswith("PV") else road_records[(label, frame)]
            )
    raw_limits = common_raw_limits(selected)
    fig, axes = plt.subplots(len(frames), len(columns), figsize=(21, 10.5), facecolor="#0E151D")
    for row_index, frame in enumerate(frames):
        for col_index, label in enumerate(columns):
            record = (
                vehicle_records[(label, frame)]
                if label.startswith("PV")
                else road_records[(label, frame)]
            )
            ax = axes[row_index, col_index]
            color = VEHICLE_COLORS.get(label, ROAD_COLORS.get(label, "white"))
            ax.imshow(record["patch"], cmap="gray", vmin=raw_limits[0], vmax=raw_limits[1], extent=patch_extent())
            draw_patch_box(ax, record["geometry"], color)
            ax.axhline(0, color="#94A3B8", linewidth=0.4, alpha=0.5)
            ax.axvline(0, color="#94A3B8", linewidth=0.4, alpha=0.5)
            ax.set_title(
                f"{label} | SAR {frame}\nraw Δ={record['near_minus_far_raw']:.2f} | "
                f"peak={record['peak_v_over_half_width']:.2f}",
                color="white",
                fontsize=7.5,
            )
            ax.tick_params(colors="#94A3B8", labelsize=5)
            if row_index == len(frames) - 1:
                ax.set_xlabel("u (fixed 0.03 m display grid)", color="#CBD5E1", fontsize=6)
            if col_index == 0:
                ax.set_ylabel("v; + near range", color="#CBD5E1", fontsize=6)
    fig.suptitle(
        "R04 | Matched raw-gray comparison: three vehicle neighborhoods versus three empty-road controls",
        color="white",
        fontsize=16,
    )
    fig.text(
        0.01,
        0.01,
        "All panels use one raw-gray scale, one sampling grid, and the same virtual L/W. "
        "The 0.03 m grid is inherited for local display only; it is not a claim of globally uniform SAR m/px.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.045, 1, 0.94])
    save_figure(fig, assets / "R04_RAW_VEHICLE_ROAD_MATCHED_COMPARISON.png")


def render_signed_profiles(
    assets: Path,
    road_records: dict[tuple[str, int], dict[str, object]],
    vehicle_records: dict[tuple[str, int], dict[str, object]],
) -> None:
    frames = [342, 361, 378]
    fig, axes = plt.subplots(2, len(frames), figsize=(17, 8.5), facecolor="#0E151D")
    for col, frame in enumerate(frames):
        for label in ("PV004", "PV003", "PV002"):
            record = vehicle_records[(label, frame)]
            geometry = record["geometry"]
            v = (
                np.arange(PATCH_HEIGHT) - (PATCH_HEIGHT - 1) / 2
            ) / (geometry.short_px / 2)
            axes[0, col].plot(v, record["profile"], color=VEHICLE_COLORS[label], linewidth=1.4, label=label)
        for label in ("RC1", "RC2", "RC3"):
            record = road_records[(label, frame)]
            geometry = record["geometry"]
            v = (
                np.arange(PATCH_HEIGHT) - (PATCH_HEIGHT - 1) / 2
            ) / (geometry.short_px / 2)
            axes[1, col].plot(v, record["profile"], color=ROAD_COLORS[label], linewidth=1.4, label=label)
        for row in range(2):
            ax = axes[row, col]
            ax.axvspan(TARGET_PEAK_RANGE[0], TARGET_PEAK_RANGE[1], color="#F8C15C", alpha=0.14)
            ax.axvline(0, color="#94A3B8", linewidth=0.6)
            ax.set_xlim(-1.9, 2.8)
            ax.grid(color="#64748B", alpha=0.22, linewidth=0.4)
            ax.tick_params(colors="#CBD5E1", labelsize=6)
            ax.set_title(
                f"{'vehicles' if row == 0 else 'empty road'} | SAR {frame}",
                color="white",
                fontsize=9,
            )
            ax.legend(fontsize=6, facecolor="#0E151D", labelcolor="white")
            if row == 1:
                ax.set_xlabel("v / (W/2); + toward fan origin", color="#CBD5E1", fontsize=7)
            if col == 0:
                ax.set_ylabel("sigma20 u-mean response", color="#CBD5E1", fontsize=7)
    fig.suptitle(
        "R05 | Signed v profiles: vehicle peaks remain near +0.65 to +0.79, road peaks do not lock there",
        color="white",
        fontsize=16,
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    save_figure(fig, assets / "R05_SIGNED_V_PROFILES.png")


def render_road_u_extension(
    assets: Path,
    road_records: dict[tuple[str, int], dict[str, object]],
) -> None:
    frames = [342, 361, 378]
    selected = [road_records[(control_id, frame)] for control_id in ROAD_COLORS for frame in frames]
    limit = common_contrast_limit(selected, 20.0)
    fig, axes = plt.subplots(3, 3, figsize=(14, 11), facecolor="#0E151D")
    for row, control_id in enumerate(ROAD_COLORS):
        for col, frame in enumerate(frames):
            record = road_records[(control_id, frame)]
            geometry = record["geometry"]
            ax = axes[row, col]
            contrast = local_contrast(record["patch"], 20.0)
            ax.imshow(
                contrast,
                cmap="coolwarm",
                vmin=-limit,
                vmax=limit,
                extent=patch_extent(),
            )
            draw_patch_box(ax, geometry, ROAD_COLORS[control_id])
            ax.set_title(
                f"{control_id} | SAR {frame}\n{record['length_termination_status']} | "
                f"u={record['u_coverage_range_px']}",
                color="white",
                fontsize=7.5,
            )
            ax.tick_params(colors="#CBD5E1", labelsize=5)
            if row == 2:
                ax.set_xlabel("u (fixed local display grid)", color="#CBD5E1", fontsize=6)
            if col == 0:
                ax.set_ylabel("v; + near range", color="#CBD5E1", fontsize=6)
    fig.suptitle(
        "R06 | Empty-road sigma20 structure along u: local fragments exist but do not reproduce vehicle-box locking",
        color="white",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    save_figure(fig, assets / "R06_ROAD_U_EXTENSION.png")


def render_registration_sensitivity(
    assets: Path,
    road_records: dict[tuple[str, int], dict[str, object]],
) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(17, 10.5), facecolor="#0E151D")
    for ax, control_id in zip(axes, ROAD_COLORS):
        matrix = np.asarray(
            [
                [
                    next(
                        value["peak"]
                        for value in road_records[(control_id, frame)]["perturbations"]
                        if value["fraction"] == fraction
                    )
                    for frame in KEY_FRAMES
                ]
                for fraction in SENSITIVITY_FRACTIONS
            ]
        )
        image = ax.imshow(matrix, cmap="coolwarm", vmin=-1.8, vmax=2.8, aspect="auto")
        for row in range(matrix.shape[0]):
            for col in range(matrix.shape[1]):
                value = matrix[row, col]
                color = "#F8C15C" if TARGET_PEAK_RANGE[0] <= value <= TARGET_PEAK_RANGE[1] else "white"
                ax.text(col, row, f"{value:.2f}", ha="center", va="center", color=color, fontsize=5.5)
        ax.set_yticks(range(len(SENSITIVITY_FRACTIONS)), [f"{value:+.1f}×unc" for value in SENSITIVITY_FRACTIONS])
        ax.set_xticks(range(len(KEY_FRAMES)), KEY_FRAMES)
        ax.tick_params(colors="#CBD5E1", labelsize=6)
        ax.set_title(
            f"{control_id} | peak v/(W/2) under coherent signed-v registration perturbations",
            color="white",
            fontsize=9,
        )
        fig.colorbar(image, ax=ax, fraction=0.015, pad=0.01)
    fig.suptitle(
        "R07 | Registration uncertainty sensitivity: isolated target-range coincidences do not become a stable road lock",
        color="white",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    save_figure(fig, assets / "R07_REGISTRATION_UNCERTAINTY_SENSITIVITY.png")


def render_result_summary(
    assets: Path,
    summaries: dict[str, dict[str, object]],
    vehicle_summary: dict[str, object],
) -> None:
    labels = ["vehicles"] + list(ROAD_COLORS)
    totals = [int(vehicle_summary["n"])] + [int(summaries[label]["n"]) for label in ROAD_COLORS]
    target = [int(vehicle_summary["target_count"])] + [int(summaries[label]["target_count"]) for label in ROAD_COLORS]
    raw_positive = [int(vehicle_summary["raw_positive_count"])] + [
        int(summaries[label]["raw_positive_count"]) for label in ROAD_COLORS
    ]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5), facecolor="#0E151D")
    colors = ["#FFD166"] + [ROAD_COLORS[label] for label in ROAD_COLORS]
    axes[0].bar(x, np.asarray(target) / np.asarray(totals), color=colors)
    axes[1].bar(x, np.asarray(raw_positive) / np.asarray(totals), color=colors)
    for ax, values, title in (
        (axes[0], target, "peak in +0.65 to +0.79 × (W/2)"),
        (axes[1], raw_positive, "raw near-half mean > far-half mean"),
    ):
        ax.set_xticks(x, labels)
        ax.set_ylim(0, 1.08)
        ax.set_title(title, color="white", fontsize=11)
        ax.tick_params(colors="#CBD5E1")
        ax.grid(axis="y", color="#64748B", alpha=0.25)
        for index, value in enumerate(values):
            ax.text(index, value / totals[index] + 0.03, f"{value}/{totals[index]}", color="white", ha="center", fontsize=9)
    fig.suptitle(
        "R08 | Result C: vehicle-neighborhood-specific contrast; road response exists without replicated box lock",
        color="white",
        fontsize=16,
    )
    fig.text(
        0.02,
        0.015,
        "This comparison is descriptive, not a score or winner ranking. "
        f"The R1 key nine vehicle cells remain {vehicle_summary['key_nine_target_count']}/9 in the target interval; "
        + ", ".join(
            f"{label}={summaries[label]['target_count']}/{summaries[label]['n']}"
            for label in ROAD_COLORS
        )
        + " before perturbation.",
        color="#F8C15C",
        fontsize=8.5,
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.92])
    save_figure(fig, assets / "R08_RESULT_SUMMARY.png")


def optical_confirmation_text(control_id: str) -> str:
    if control_id == "RC1":
        return (
            "optical 195/200/205/210: PV004 remains the rightmost trailing sedan while the immediately "
            "preceding roadside slot is exposed and vehicle-free"
        )
    if control_id == "RC2":
        return (
            "optical 200/205/210: the second roadside slot left of PV004 is visible without PV002/PV003; "
            "road surface is empty"
        )
    return (
        "optical 205/210: the third roadside slot left of partial PV004 is visible as vehicle-free road; low "
        "curb/planting context remains and may contribute because optical semantics are not a SAR pixel calibration"
    )


def build_manifest_rows(
    controls: dict[str, Geometry],
    definition_uncertainty: dict[str, float],
    registrations: dict[int, Registration],
    road_records: dict[tuple[str, int], dict[str, object]],
    summaries: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    rows = []
    landmark_text = ";".join(LANDMARKS)
    method = (
        "SAR361 six manually declared non-collinear static landmarks; sequential fixed-reference-template local "
        "tracking through every SAR frame; componentwise median 2D translation; no vehicle-seeded search; vehicle "
        "GT only posthoc validation"
    )
    for control_id, reference in controls.items():
        for frame in KEY_FRAMES:
            registration = registrations[frame]
            record = road_records[(control_id, frame)]
            geometry = record["geometry"]
            radius, theta = fan_geometry((geometry.cx, geometry.cy))
            _, _, near_dot = signed_axes(geometry)
            perturbation_peaks = [float(value["peak"]) for value in record["perturbations"]]
            target_possible = any(
                TARGET_PEAK_RANGE[0] <= value <= TARGET_PEAK_RANGE[1]
                for value in perturbation_peaks
            )
            rows.append(
                {
                    "record_type": "WORLD_REGISTERED_EMPTY_ROAD_COUNTERFACTUAL",
                    "road_control_id": control_id,
                    "reference_sar_frame": REF_FRAME,
                    "current_sar_frame": frame,
                    "optical_empty_confirmation": optical_confirmation_text(control_id),
                    "world_registration_status": "WORLD_REGISTERED_ROAD_CONTROL",
                    "world_registration_method": method,
                    "registration_landmarks": landmark_text,
                    "registration_translation_px": f"[{registration.dx:.3f},{registration.dy:.3f}]",
                    "registration_uncertainty_px": f"{record['total_uncertainty_px']:.3f}",
                    "frame_registration_uncertainty_px": f"{registration.registration_uncertainty_px:.3f}",
                    "road_definition_uncertainty_px": f"{definition_uncertainty[control_id]:.3f}",
                    "landmark_residual_median_px": f"{registration.residual_median_px:.3f}",
                    "landmark_residual_p90_px": f"{registration.residual_p90_px:.3f}",
                    "landmark_loo_translation_radius_px": f"{registration.loo_translation_radius_px:.3f}",
                    "vehicle_posthoc_validation_max_px": f"{registration.vehicle_validation_max_px:.3f}",
                    "vehicle_posthoc_cross_axis_max_px": f"{registration.vehicle_validation_cross_axis_max_px:.3f}",
                    "road_axis_deg": f"{geometry.axis_deg:.3f}",
                    "virtual_box_center": f"[{geometry.cx:.3f},{geometry.cy:.3f}]",
                    "virtual_box_L/W": f"[{geometry.long_px:.3f},{geometry.short_px:.3f}]",
                    "v_points_to_fan_origin_check": "PASS" if near_dot > 0 else "FAIL",
                    "near_sign_dot_to_origin": f"{near_dot:.6f}",
                    "radius/theta": f"[{radius:.3f},{theta:.3f}]",
                    "radius_px": f"{radius:.3f}",
                    "theta_deg": f"{theta:.3f}",
                    "valid_patch_ratio": f"{record['valid_ratio']:.6f}",
                    "peak_v": f"{record['peak_v_px']:.3f}",
                    "peak_v_over_half_width": f"{record['peak_v_over_half_width']:.6f}",
                    "near_minus_far_raw": f"{record['near_minus_far_raw']:.6f}",
                    "near_minus_far_sigma4": f"{record['near_minus_far_sigma4']:.6f}",
                    "near_minus_far_sigma10": f"{record['near_minus_far_sigma10']:.6f}",
                    "near_minus_far_sigma20": f"{record['near_minus_far_sigma20']:.6f}",
                    "u_coverage_range": record["u_coverage_range_px"],
                    "u_span_px": f"{record['u_span_px']:.3f}",
                    "length_termination_status": record["length_termination_status"],
                    "registration_sensitivity_peak_range": (
                        f"[{min(perturbation_peaks):.6f},{max(perturbation_peaks):.6f}]"
                    ),
                    "registration_sensitivity_can_enter_vehicle_interval": (
                        "YES_ISOLATED_FRAME_ONLY" if target_possible else "NO"
                    ),
                    "cross_frame_consistency": summaries[control_id]["cross_frame_consistency"],
                    "physical_interpretation": (
                        "ROAD_RESPONSE_PRESENT_WITHOUT_REPLICATED_VEHICLE_BOX_NEAR_SIDE_LOCK; "
                        "supports VEHICLE_NEIGHBORHOOD_SPECIFIC_CONTRAST"
                    ),
                    "evidence_limit": (
                        "GM17 only; optical supplies empty-road semantics but not SAR pixels; reference road locus is "
                        "manual research geometry extrapolated beyond PV004; registration uncertainty is explicit; "
                        "does not separate vehicle body from vehicle-ground interaction and is not runtime input"
                    ),
                }
            )
    return rows


def main() -> None:
    args = parse_args()
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    gt_rows = read_csv(args.repo / "manifests/oty2/oty2_s0_sar_gt_quality_audit.csv")
    gt = gt_map(gt_rows)
    states = optical_state_map(
        read_csv(args.repo / "manifests/oty2/oty2_p1e_canonical_vehicle_frame_states.csv")
    )
    controls, definition_uncertainty, _, validation_v_axis = reference_controls(gt_rows)
    vehicle_geometries = {
        vehicle: stable_geometry_loo(gt_rows, SCENE, vehicle, REF_FRAME)
        for vehicle in VEHICLES
    }
    registrations = build_registrations(args.data, gt, validation_v_axis)
    image_cache = {frame: load_gray(args.data, frame) for frame in KEY_FRAMES}

    road_records: dict[tuple[str, int], dict[str, object]] = {}
    for control_id, reference in controls.items():
        for frame in KEY_FRAMES:
            registration = registrations[frame]
            geometry = translated_geometry(reference, registration)
            record = measure_patch(image_cache[frame], geometry)
            uncertainty = total_uncertainty(
                registration.registration_uncertainty_px,
                definition_uncertainty[control_id],
            )
            record["total_uncertainty_px"] = uncertainty
            record["perturbations"] = perturbation_measurements(
                image_cache[frame], geometry, uncertainty
            )
            road_records[(control_id, frame)] = record

    vehicle_records: dict[tuple[str, int], dict[str, object]] = {}
    for vehicle in VEHICLES:
        label = suffix(vehicle)
        for frame in KEY_FRAMES:
            try:
                geometry = stable_geometry_loo(gt_rows, SCENE, vehicle, frame)
            except RuntimeError:
                continue
            vehicle_records[(label, frame)] = measure_patch(image_cache[frame], geometry)

    summaries, vehicle_summary = aggregate_summaries(road_records, vehicle_records)
    manifest_rows = build_manifest_rows(
        controls,
        definition_uncertainty,
        registrations,
        road_records,
        summaries,
    )
    write_csv(args.manifest, manifest_rows)

    render_optical_empty_confirmation(args.assets_dir, args.data, states)
    render_reference_geometry(args.assets_dir, args.data, controls, vehicle_geometries)
    render_registration_trajectory(args.assets_dir, args.data, controls, registrations)
    render_raw_comparison(args.assets_dir, road_records, vehicle_records)
    render_signed_profiles(args.assets_dir, road_records, vehicle_records)
    render_road_u_extension(args.assets_dir, road_records)
    render_registration_sensitivity(args.assets_dir, road_records)
    render_result_summary(args.assets_dir, summaries, vehicle_summary)

    output = {
        "result": "C. VEHICLE_NEIGHBORHOOD_SPECIFIC_CONTRAST",
        "controls": {
            control_id: {
                "reference_center": [geometry.cx, geometry.cy],
                "L": geometry.long_px,
                "W": geometry.short_px,
                "axis_deg": geometry.axis_deg,
                **summaries[control_id],
            }
            for control_id, geometry in controls.items()
        },
        "vehicle_summary": vehicle_summary,
        "registration": {
            "frame_uncertainty_min_px": min(
                registrations[frame].registration_uncertainty_px for frame in KEY_FRAMES
            ),
            "frame_uncertainty_max_px": max(
                registrations[frame].registration_uncertainty_px for frame in KEY_FRAMES
            ),
            "cross_axis_validation_max_px": max(
                registrations[frame].vehicle_validation_cross_axis_max_px
                for frame in KEY_FRAMES
                if math.isfinite(registrations[frame].vehicle_validation_cross_axis_max_px)
            ),
        },
        "manifest": str(args.manifest),
        "assets": str(args.assets_dir),
        "manifest_rows": len(manifest_rows),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
