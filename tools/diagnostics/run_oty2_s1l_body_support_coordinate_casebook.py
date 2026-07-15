#!/usr/bin/env python3
from __future__ import annotations

"""Build the minimum S1-L world/crop/body coordinate casebook.

This runner is deliberately bounded.  It does not perturb GT, optimize a box,
rank parameter settings, reconstruct a final vehicle support, or enter S1-D.
It registers the frozen S1-L display-domain fields into three coordinate
families and writes temporary arrays/visuals outside Git for direct review.
"""

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
DATA_ROOT = Path(r"D:\profile\research\data")
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")
OUTPUT_ROOT = WORKSPACE_ROOT / "output" / "oty2_s1l_body_support_attribution_20260715"
ARRAY_ROOT = OUTPUT_ROOT / "canonical_fields"
VISUAL_ROOT = OUTPUT_ROOT / "visual_casebook"
SUMMARY_PATH = OUTPUT_ROOT / "coordinate_casebook_summary.json"
TEMP_VISUAL_MANIFEST_PATH = OUTPUT_ROOT / "coordinate_casebook_visual_manifest.csv"
LOG_PATH = WORKSPACE_ROOT / "logs" / "oty2_s1l_body_support_attribution_20260715.log"

LOCAL_FIELD_PATH = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
OBSERVATION_PATH = MANIFEST_DIR / "oty2_s1l_structure_observations.csv"
BACKGROUND_PATH = MANIFEST_DIR / "oty2_s1l_background_counterfactuals.csv"
FRAME_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_body_support_coordinate_frames.csv"
COMPETITION_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_body_support_coordinate_competition.csv"
VISUAL_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_body_support_casebook_manifest.csv"

FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS = 1332.7
CANVAS_WIDTH = 2308
CANVAS_HEIGHT = 1334
CROP_EXPANSION = 1.75
SUPPORT_LEVEL = 0.35
GRID_WIDTH = 256
GRID_HEIGHT = 128

CORE_SEGMENTS = {
    "S0MV-GM_RM017-PV002-SEG02": "mechanism_discovery",
    "S0MV-GM_RM017-PV003-SEG01": "heldout_validation",
    "S0MV-GM_RM017-PV004-SEG01": "heldout_validation",
    "S0MV-GM_RM011-PV001-SEG01": "cross_scene_diagnostic_only",
}
FIXED_BACKGROUND_SOURCE_SEGMENT = "S0MV-GM_RM017-PV002-SEG02"
FIXED_BACKGROUND_ID = "S1L-BG-0011"
FIXED_BACKGROUND_UNIT = "S1L-BG-0011-TRAJECTORY-ON-FIXED-WORLD"

REPRESENTATIONS = ("world", "raw_crop", "smoothed_crop", "raw_body", "smoothed_body")
COORDINATE_FAMILY = {
    "world": "world",
    "raw_crop": "crop",
    "smoothed_crop": "crop",
    "raw_body": "body",
    "smoothed_body": "body",
}

FRAME_FIELDS = (
    "research_unit_id", "research_unit_type", "scene", "canonical_vehicle_id", "benchmark_role",
    "research_role", "segment_id", "source_trajectory_segment_id", "sar_frame_index", "sar_time_sec",
    "bundle_index", "source_image_path", "source_image_sha256", "raw_gt_center_x_px", "raw_gt_center_y_px",
    "raw_gt_width_px", "raw_gt_height_px", "raw_gt_angle_deg", "smoothed_gt_center_x_px",
    "smoothed_gt_center_y_px", "smoothed_gt_width_px", "smoothed_gt_height_px", "smoothed_gt_angle_deg",
    "raw_body_long_axis_unsigned_deg", "smoothed_body_long_axis_unsigned_deg", "raw_body_axis_u_x",
    "raw_body_axis_u_y", "raw_body_axis_v_x", "raw_body_axis_v_y", "smoothed_body_axis_u_x",
    "smoothed_body_axis_u_y", "smoothed_body_axis_v_x", "smoothed_body_axis_v_y",
    "reference_long_axis_px", "reference_short_axis_px", "raw_aspect_ratio", "smoothed_aspect_ratio",
    "raw_axis_step_deg_per_frame", "smoothed_axis_step_deg_per_frame", "gt_center_spread_px",
    "gt_size_spread_px", "raw_smoothed_center_delta_px", "raw_smoothed_center_delta_over_ref_short",
    "axis_reliability", "axis_reliability_reasons", "raw_body_boundary_missing_fraction",
    "smoothed_body_boundary_missing_fraction", "raw_body_registration_status",
    "raw_body_registration_reasons", "smoothed_body_registration_status",
    "smoothed_body_registration_reasons", "raw_radar_direction_body_u", "raw_radar_direction_body_v",
    "smoothed_radar_direction_body_u", "smoothed_radar_direction_body_v",
    "raw_relative_observation_angle_deg_mod180", "smoothed_relative_observation_angle_deg_mod180",
    "canonical_field_bundle_path", "world_field_key", "raw_crop_field_key", "smoothed_crop_field_key",
    "raw_body_field_key", "smoothed_body_field_key", "valid_mask_key_suffix", "local_background_key_suffix",
    "axis_sign_rule", "scale_semantics", "gt_information_debt", "notes",
)

COMPETITION_FIELDS = (
    "research_unit_id", "research_unit_type", "scene", "canonical_vehicle_id", "benchmark_role",
    "research_role", "segment_id", "representation", "coordinate_family", "frame_count",
    "support_level", "response_lineage", "valid_fraction_mean", "valid_fraction_min",
    "response_centroid_x_mad_norm", "response_centroid_y_mad_norm",
    "adjacent_centroid_shift_median_norm", "adjacent_centroid_shift_p90_norm",
    "adjacent_ncc_median", "adjacent_ncc_p10", "adjacent_absdiff_median",
    "support_area_fraction_mean", "support_area_fraction_cv", "support_entropy_mean_bits",
    "nonadjacent_similar_view_pair_count", "nonadjacent_similar_view_ncc_median",
    "observation_frame_count", "observation_centroid_temporal_mad_norm",
    "relation_distance_q50_temporal_cv", "relation_distance_q90_temporal_cv",
    "observation_orientation_axial_dispersion_deg", "automatic_attribution_label",
    "review_status", "notes",
)

VISUAL_FIELDS = (
    "case_id", "artifact_type", "research_unit_id", "research_unit_type", "scene",
    "canonical_vehicle_id", "segment_id", "artifact_path", "review_status", "notes",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fmt(value: Any, digits: int = 6) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return "" if not math.isfinite(number) else f"{number:.{digits}f}"


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def parse_polygon(text: str) -> np.ndarray:
    return np.asarray([[float(value) for value in item.split(",")] for item in text.split(";")], dtype=np.float64)


def anchor_from_row(row: Mapping[str, str], prefix: str) -> dict[str, float]:
    if prefix == "raw":
        return {
            "cx": parse_float(row["raw_anchor_center_x_px"]),
            "cy": parse_float(row["raw_anchor_center_y_px"]),
            "w": parse_float(row["raw_anchor_width_px"]),
            "h": parse_float(row["raw_anchor_height_px"]),
            "angle": parse_float(row["raw_anchor_angle_deg"]),
        }
    return {
        "cx": parse_float(row["smoothed_anchor_center_x_px"]),
        "cy": parse_float(row["smoothed_anchor_center_y_px"]),
        "w": parse_float(row["smoothed_anchor_width_px"]),
        "h": parse_float(row["smoothed_anchor_height_px"]),
        "angle": parse_float(row["smoothed_anchor_angle_deg"]),
    }


def long_axis_unsigned_deg(anchor: Mapping[str, float]) -> float:
    value = float(anchor["angle"]) if float(anchor["w"]) >= float(anchor["h"]) else float(anchor["angle"]) + 90.0
    return value % 180.0


def axis_vector(angle_deg: float) -> np.ndarray:
    angle = math.radians(angle_deg)
    return np.asarray([math.cos(angle), math.sin(angle)], dtype=np.float64)


def continuous_axes(angles: Sequence[float]) -> list[tuple[np.ndarray, np.ndarray]]:
    output: list[tuple[np.ndarray, np.ndarray]] = []
    previous: np.ndarray | None = None
    for index, angle in enumerate(angles):
        u = axis_vector(angle)
        if index == 0 and (u[0] < 0.0 or abs(u[0]) < 1e-9 and u[1] < 0.0):
            u = -u
        if previous is not None and float(u @ previous) < 0.0:
            u = -u
        v = np.asarray([-u[1], u[0]], dtype=np.float64)
        output.append((u, v))
        previous = u
    return output


def radial_tangential(anchor: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray]:
    radial = np.asarray([float(anchor["cx"]) - FAN_CENTER_X, float(anchor["cy"]) - FAN_CENTER_Y], dtype=np.float64)
    norm = float(np.linalg.norm(radial))
    radial = radial / norm if norm > 1e-9 else np.asarray([0.0, -1.0], dtype=np.float64)
    tangential = np.asarray([-radial[1], radial[0]], dtype=np.float64)
    return radial, tangential


def offset_anchor(anchor: Mapping[str, float], dr: float, dt: float) -> dict[str, float]:
    radial, tangential = radial_tangential(anchor)
    center = np.asarray([anchor["cx"], anchor["cy"]], dtype=np.float64) + radial * dr + tangential * dt
    result = dict(anchor)
    result["cx"], result["cy"] = float(center[0]), float(center[1])
    return result


def axial_difference(a: float, b: float) -> float:
    difference = abs(a - b) % 180.0
    return min(difference, 180.0 - difference)


def axial_dispersion(values: Sequence[float]) -> float:
    if not values:
        return math.nan
    doubled = np.radians(np.asarray(values, dtype=np.float64) * 2.0)
    mean = 0.5 * math.degrees(math.atan2(float(np.sin(doubled).mean()), float(np.cos(doubled).mean()))) % 180.0
    return float(statistics.median(axial_difference(value, mean) for value in values))


def quantile(values: Sequence[float], probability: float) -> float:
    finite = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not finite:
        return math.nan
    index = int(round((len(finite) - 1) * probability))
    return finite[max(0, min(len(finite) - 1, index))]


def coefficient_of_variation(values: Sequence[float]) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if len(finite) < 2 or abs(statistics.mean(finite)) < 1e-12:
        return math.nan
    return float(statistics.pstdev(finite) / abs(statistics.mean(finite)))


def image_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def imaging_valid(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    radius = np.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)
    theta = np.degrees(np.arctan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))
    return (
        (x >= 0.0) & (x < CANVAS_WIDTH) & (y >= 0.0) & (y < CANVAS_HEIGHT)
        & (radius <= FAN_RADIUS) & (theta >= -90.0) & (theta <= 90.0)
    )


def warp_axes(
    image: np.ndarray,
    center: Sequence[float],
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    half_x: float,
    half_y: float,
) -> tuple[np.ndarray, np.ndarray]:
    xs = np.linspace(-half_x, half_x, GRID_WIDTH, dtype=np.float32)
    ys = np.linspace(-half_y, half_y, GRID_HEIGHT, dtype=np.float32)
    local_x, local_y = np.meshgrid(xs, ys)
    map_x = float(center[0]) + local_x * float(axis_x[0]) + local_y * float(axis_y[0])
    map_y = float(center[1]) + local_x * float(axis_x[1]) + local_y * float(axis_y[1])
    warped = cv2.remap(
        image,
        map_x.astype(np.float32),
        map_y.astype(np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    valid = imaging_valid(map_x, map_y)
    return warped, valid


def normalized_score(raw: np.ndarray, valid: np.ndarray, background_median: float, p99: float) -> np.ndarray:
    score = np.clip((raw.astype(np.float32) - background_median) / max(1.0, p99 - background_median), 0.0, 1.0)
    score[~valid] = 0.0
    return score


def radar_in_body(anchor: Mapping[str, float], u: np.ndarray, v: np.ndarray) -> tuple[float, float, float]:
    direction = np.asarray([FAN_CENTER_X - float(anchor["cx"]), FAN_CENTER_Y - float(anchor["cy"])], dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if norm <= 1e-9:
        return 0.0, 0.0, math.nan
    direction /= norm
    body_u, body_v = float(direction @ u), float(direction @ v)
    angle = math.degrees(math.atan2(body_v, body_u)) % 180.0
    return body_u, body_v, angle


def step_rates(frames: Sequence[int], angles: Sequence[float]) -> list[float]:
    output: list[float] = []
    for index in range(len(frames)):
        values: list[float] = []
        if index > 0:
            values.append(axial_difference(angles[index], angles[index - 1]) / max(1, frames[index] - frames[index - 1]))
        if index + 1 < len(frames):
            values.append(axial_difference(angles[index], angles[index + 1]) / max(1, frames[index + 1] - frames[index]))
        output.append(max(values, default=0.0))
    return output


def reliability(
    aspect: float,
    step: float,
    center_spread: float,
    size_spread: float,
    reference_short: float,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if aspect < 1.5:
        reasons.append("ASPECT_TOO_ISOTROPIC")
    if step > 10.0:
        reasons.append("ABRUPT_UNSIGNED_AXIS_CHANGE")
    if center_spread > 0.25 * reference_short:
        reasons.append("DUPLICATE_GT_CENTER_SPREAD")
    if size_spread > 0.25 * reference_short:
        reasons.append("DUPLICATE_GT_SIZE_SPREAD")
    return ("AXIS_RELIABLE" if not reasons else "AXIS_UNRELIABLE"), reasons


def registration_status(
    axis_status: str,
    center_delta: float,
    reference_short: float,
    boundary_missing: float,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if axis_status != "AXIS_RELIABLE":
        reasons.append("AXIS_UNRELIABLE")
    if center_delta > 0.25 * reference_short:
        reasons.append("RAW_SMOOTHED_CENTER_DISAGREEMENT")
    if boundary_missing > 0.05:
        reasons.append("CANONICAL_BOUNDARY_MISSING")
    return ("REGISTRATION_RELIABLE" if not reasons else "REGISTRATION_UNRELIABLE"), reasons


def world_geometry(rows: Sequence[Mapping[str, str]]) -> tuple[np.ndarray, float, float]:
    points = np.vstack([
        parse_polygon(row["raw_crop_polygon_global_px"]) for row in rows
    ] + [
        parse_polygon(row["smoothed_crop_polygon_global_px"]) for row in rows
    ])
    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    center = (minimum + maximum) * 0.5
    half = np.maximum((maximum - minimum) * 0.55, np.asarray([16.0, 16.0]))
    return center, float(half[0]), float(half[1])


def put_text(
    image: np.ndarray,
    text: str,
    origin: tuple[int, int],
    scale: float = 0.42,
    color: tuple[int, int, int] = (245, 245, 245),
    thickness: int = 1,
) -> None:
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def colorize_gray(image: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    output = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if valid is not None:
        output[~valid] = (12, 12, 12)
    return output


def tile(image: np.ndarray, title: str, width: int = 260, height: int = 150) -> np.ndarray:
    result = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    put_text(result, title, (6, 17), scale=0.40)
    return result


def world_overlay(
    world_raw: np.ndarray,
    world_valid: np.ndarray,
    world_center: np.ndarray,
    world_half_x: float,
    world_half_y: float,
    anchor: Mapping[str, float],
    body_u: np.ndarray,
    reference_long: float,
) -> np.ndarray:
    output = colorize_gray(world_raw, world_valid)

    def project(point: np.ndarray) -> tuple[int, int]:
        x = (float(point[0]) - (float(world_center[0]) - world_half_x)) / max(1e-9, 2.0 * world_half_x) * (GRID_WIDTH - 1)
        y = (float(point[1]) - (float(world_center[1]) - world_half_y)) / max(1e-9, 2.0 * world_half_y) * (GRID_HEIGHT - 1)
        return int(round(x)), int(round(y))

    rect = ((float(anchor["cx"]), float(anchor["cy"])), (float(anchor["w"]), float(anchor["h"])), float(anchor["angle"]))
    polygon = cv2.boxPoints(rect).astype(np.float64)
    cv2.polylines(output, [np.asarray([project(point) for point in polygon], dtype=np.int32)], True, (0, 220, 255), 2, cv2.LINE_AA)
    center = np.asarray([anchor["cx"], anchor["cy"]], dtype=np.float64)
    p1 = project(center - body_u * reference_long * 0.55)
    p2 = project(center + body_u * reference_long * 0.55)
    cv2.line(output, p1, p2, (70, 230, 70), 2, cv2.LINE_AA)
    return output


def ncc(a: np.ndarray, b: np.ndarray, valid: np.ndarray) -> float:
    if int(valid.sum()) < 20:
        return math.nan
    av = a[valid].astype(np.float64)
    bv = b[valid].astype(np.float64)
    av -= av.mean()
    bv -= bv.mean()
    denominator = float(np.linalg.norm(av) * np.linalg.norm(bv))
    return float(av @ bv / denominator) if denominator > 1e-12 else math.nan


def support_centroid(score: np.ndarray, valid: np.ndarray) -> tuple[float, float]:
    support = (score >= SUPPORT_LEVEL) & valid
    weights = np.where(support, score, 0.0)
    total = float(weights.sum())
    if total <= 1e-9:
        return math.nan, math.nan
    ys, xs = np.mgrid[0:score.shape[0], 0:score.shape[1]]
    return float((weights * xs).sum() / total / max(1, score.shape[1] - 1)), float((weights * ys).sum() / total / max(1, score.shape[0] - 1))


def stack_metrics(
    scores: np.ndarray,
    valids: np.ndarray,
    frames: Sequence[int],
    view_angles: Sequence[float],
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    centroids = [support_centroid(score, valid) for score, valid in zip(scores, valids)]
    finite_x = [value[0] for value in centroids if math.isfinite(value[0])]
    finite_y = [value[1] for value in centroids if math.isfinite(value[1])]
    median_x = statistics.median(finite_x) if finite_x else math.nan
    median_y = statistics.median(finite_y) if finite_y else math.nan
    mad_x = statistics.median(abs(value - median_x) for value in finite_x) if finite_x else math.nan
    mad_y = statistics.median(abs(value - median_y) for value in finite_y) if finite_y else math.nan

    adjacent_shift: list[float] = []
    adjacent_ncc: list[float] = []
    adjacent_absdiff: list[float] = []
    for index in range(len(scores) - 1):
        c1, c2 = centroids[index], centroids[index + 1]
        if all(math.isfinite(value) for value in (*c1, *c2)):
            adjacent_shift.append(math.hypot(c2[0] - c1[0], c2[1] - c1[1]))
        valid = valids[index] & valids[index + 1]
        adjacent_ncc.append(ncc(scores[index], scores[index + 1], valid))
        if valid.any():
            adjacent_absdiff.append(float(np.mean(np.abs(scores[index][valid] - scores[index + 1][valid]))))

    support = (scores >= SUPPORT_LEVEL) & valids
    valid_count = valids.sum(axis=0)
    support_count = support.sum(axis=0)
    occupancy = np.divide(support_count, valid_count, out=np.zeros_like(support_count, dtype=np.float32), where=valid_count > 0)
    entropy = np.zeros_like(occupancy, dtype=np.float32)
    usable = (valid_count >= max(2, int(math.ceil(len(scores) * 0.5)))) & (support_count > 0)
    probabilities = occupancy[usable]
    if probabilities.size:
        entropy[usable] = -(
            probabilities * np.log2(np.clip(probabilities, 1e-8, 1.0))
            + (1.0 - probabilities) * np.log2(np.clip(1.0 - probabilities, 1e-8, 1.0))
        )
    area = [float(np.mean(mask[valid])) if valid.any() else math.nan for mask, valid in zip(support, valids)]

    nonadjacent: list[float] = []
    for left in range(len(scores)):
        for right in range(left + 1, len(scores)):
            if frames[right] - frames[left] < 10:
                continue
            if axial_difference(view_angles[left], view_angles[right]) > 5.0:
                continue
            valid = valids[left] & valids[right]
            value = ncc(scores[left], scores[right], valid)
            if math.isfinite(value):
                nonadjacent.append(value)

    mean_score = np.divide((scores * valids).sum(axis=0), valid_count, out=np.zeros_like(scores[0], dtype=np.float32), where=valid_count > 0)
    metrics = {
        "valid_fraction_mean": float(np.mean(valids)),
        "valid_fraction_min": min(float(np.mean(valid)) for valid in valids),
        "response_centroid_x_mad_norm": mad_x,
        "response_centroid_y_mad_norm": mad_y,
        "adjacent_centroid_shift_median_norm": statistics.median(adjacent_shift) if adjacent_shift else math.nan,
        "adjacent_centroid_shift_p90_norm": quantile(adjacent_shift, 0.9),
        "adjacent_ncc_median": statistics.median([v for v in adjacent_ncc if math.isfinite(v)]) if any(math.isfinite(v) for v in adjacent_ncc) else math.nan,
        "adjacent_ncc_p10": quantile(adjacent_ncc, 0.1),
        "adjacent_absdiff_median": statistics.median(adjacent_absdiff) if adjacent_absdiff else math.nan,
        "support_area_fraction_mean": statistics.mean([v for v in area if math.isfinite(v)]) if any(math.isfinite(v) for v in area) else math.nan,
        "support_area_fraction_cv": coefficient_of_variation(area),
        "support_entropy_mean_bits": float(entropy[usable].mean()) if usable.any() else math.nan,
        "nonadjacent_similar_view_pair_count": len(nonadjacent),
        "nonadjacent_similar_view_ncc_median": statistics.median(nonadjacent) if nonadjacent else math.nan,
    }
    return metrics, mean_score, occupancy, entropy


def transform_point(
    point: np.ndarray,
    center: np.ndarray,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    reference_long: float,
    reference_short: float,
) -> np.ndarray:
    delta = point - center
    return np.asarray([
        float(delta @ axis_x) / max(reference_long, 1e-9),
        float(delta @ axis_y) / max(reference_short, 1e-9),
    ], dtype=np.float64)


def observation_metrics(
    representation: str,
    rows: Sequence[Mapping[str, Any]],
    observations_by_frame: Mapping[int, list[dict[str, str]]],
    raw_axes: Sequence[tuple[np.ndarray, np.ndarray]],
    smooth_axes: Sequence[tuple[np.ndarray, np.ndarray]],
    world_center: np.ndarray,
    world_half_x: float,
    world_half_y: float,
) -> dict[str, Any]:
    frame_centroids: list[np.ndarray] = []
    q50_values: list[float] = []
    q90_values: list[float] = []
    relative_orientations: list[float] = []
    used_frames = 0
    for index, row in enumerate(rows):
        frame = int(row["sar_frame_index"])
        observations = [item for item in observations_by_frame.get(frame, []) if item.get("major_temporal_eligible") == "true"]
        if not observations:
            continue
        raw_anchor = anchor_from_row(row, "raw")
        smooth_anchor = anchor_from_row(row, "smoothed")
        reference_long = statistics.median(max(anchor_from_row(item, "raw")["w"], anchor_from_row(item, "raw")["h"]) for item in rows)
        reference_short = statistics.median(min(anchor_from_row(item, "raw")["w"], anchor_from_row(item, "raw")["h"]) for item in rows)
        if representation == "world":
            center = world_center; axis_x = np.asarray([1.0, 0.0]); axis_y = np.asarray([0.0, 1.0])
            base_angle = 0.0
        elif representation == "raw_crop":
            radial, tangential = radial_tangential(raw_anchor)
            center = np.asarray([raw_anchor["cx"], raw_anchor["cy"]]); axis_x = tangential; axis_y = radial
            base_angle = math.degrees(math.atan2(float(axis_x[1]), float(axis_x[0]))) % 180.0
        elif representation == "smoothed_crop":
            radial, tangential = radial_tangential(smooth_anchor)
            center = np.asarray([smooth_anchor["cx"], smooth_anchor["cy"]]); axis_x = tangential; axis_y = radial
            base_angle = math.degrees(math.atan2(float(axis_x[1]), float(axis_x[0]))) % 180.0
        elif representation == "raw_body":
            axis_x, axis_y = raw_axes[index]
            center = np.asarray([raw_anchor["cx"], raw_anchor["cy"]])
            base_angle = long_axis_unsigned_deg(raw_anchor)
        else:
            axis_x, axis_y = smooth_axes[index]
            center = np.asarray([smooth_anchor["cx"], smooth_anchor["cy"]])
            base_angle = long_axis_unsigned_deg(smooth_anchor)

        points = [
            transform_point(
                np.asarray([parse_float(item["global_centroid_x_px"]), parse_float(item["global_centroid_y_px"])], dtype=np.float64),
                center, axis_x, axis_y, reference_long, reference_short,
            )
            for item in observations
        ]
        array = np.asarray(points, dtype=np.float64)
        frame_centroids.append(array.mean(axis=0))
        distances = [float(np.linalg.norm(array[left] - array[right])) for left in range(len(array)) for right in range(left + 1, len(array))]
        if distances:
            q50_values.append(quantile(distances, 0.5)); q90_values.append(quantile(distances, 0.9))
        relative_orientations.extend((parse_float(item["major_axis_angle_deg"]) - base_angle) % 180.0 for item in observations)
        used_frames += 1

    centroid_mad = math.nan
    if frame_centroids:
        array = np.asarray(frame_centroids)
        median = np.median(array, axis=0)
        centroid_mad = float(np.median(np.linalg.norm(array - median[None, :], axis=1)))
    return {
        "observation_frame_count": used_frames,
        "observation_centroid_temporal_mad_norm": centroid_mad,
        "relation_distance_q50_temporal_cv": coefficient_of_variation(q50_values),
        "relation_distance_q90_temporal_cv": coefficient_of_variation(q90_values),
        "observation_orientation_axial_dispersion_deg": axial_dispersion(relative_orientations),
    }


def heatmap_tile(array: np.ndarray, title: str, maximum: float = 1.0) -> np.ndarray:
    scaled = np.clip(array / max(maximum, 1e-9) * 255.0, 0.0, 255.0).astype(np.uint8)
    colored = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    return tile(colored, title, width=320, height=180)


def selected_indices(count: int, target: int = 8) -> list[int]:
    if count <= target:
        return list(range(count))
    return sorted(set(int(round(value)) for value in np.linspace(0, count - 1, target)))


def generate_frame_pages(
    unit: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    rows: Sequence[Mapping[str, Any]],
    review_status: str,
) -> list[dict[str, Any]]:
    directory = VISUAL_ROOT / unit["research_unit_id"] / "frame_triptychs"
    directory.mkdir(parents=True, exist_ok=True)
    output: list[dict[str, Any]] = []
    chosen = selected_indices(len(rows), 8)
    for page_number, start in enumerate(range(0, len(chosen), 4), start=1):
        subset = chosen[start:start + 4]
        canvas = np.full((len(subset) * 150, 5 * 260, 3), 15, dtype=np.uint8)
        for local_row, index in enumerate(subset):
            row = rows[index]
            frame = row["sar_frame_index"]
            names = ("world", "raw_crop", "smoothed_crop", "raw_body", "smoothed_body")
            if unit["research_unit_type"] == "vehicle_thread":
                titles = (
                    f"f{frame} world + GT/body axis",
                    f"f{frame} Raw-GT crop coord",
                    f"f{frame} Smoothed-GT crop coord",
                    f"f{frame} Raw-GT body coord",
                    f"f{frame} Smoothed-GT body coord",
                )
            else:
                titles = (
                    f"f{frame} fixed world + pseudo path",
                    f"f{frame} translated Raw crop path",
                    f"f{frame} translated Smooth crop path",
                    f"f{frame} translated Raw body path",
                    f"f{frame} translated Smooth body path",
                )
            for column, (name, title_text) in enumerate(zip(names, titles)):
                raw = arrays[f"{name}_raw"][index]
                valid = arrays[f"{name}_valid"][index].astype(bool)
                if name == "world":
                    image = world_overlay(
                        raw, valid, unit["world_center"], unit["world_half_x"], unit["world_half_y"],
                        unit["raw_anchors"][index], unit["raw_axes"][index][0], unit["reference_long"],
                    )
                else:
                    image = colorize_gray(raw, valid)
                canvas[local_row * 150:(local_row + 1) * 150, column * 260:(column + 1) * 260] = tile(image, title_text)
        path = directory / f"{unit['research_unit_id']}_frame_coordinates_page_{page_number:02d}.png"
        cv2.imwrite(str(path), canvas)
        output.append({
            "case_id": f"{unit['research_unit_id']}-FRAME-{page_number:02d}",
            "artifact_type": "world_crop_body_frame_comparison",
            "research_unit_id": unit["research_unit_id"], "research_unit_type": unit["research_unit_type"],
            "scene": unit["scene"], "canonical_vehicle_id": unit["canonical_vehicle_id"],
            "segment_id": unit["segment_id"], "artifact_path": str(path), "review_status": review_status,
            "notes": "world plus Raw/Smoothed crop and GT-derived unsigned body coordinates; no automatic attribution",
        })
    return output


def generate_summary_page(
    unit: Mapping[str, Any],
    summaries: Mapping[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    review_status: str,
) -> dict[str, Any]:
    directory = VISUAL_ROOT / unit["research_unit_id"]
    directory.mkdir(parents=True, exist_ok=True)
    canvas = np.full((len(REPRESENTATIONS) * 180, 3 * 320, 3), 15, dtype=np.uint8)
    for row_index, representation in enumerate(REPRESENTATIONS):
        mean_score, occupancy, entropy = summaries[representation]
        panels = (
            heatmap_tile(mean_score, f"{representation}: mean local-bg response"),
            heatmap_tile(occupancy, f"{representation}: support occupancy"),
            heatmap_tile(entropy, f"{representation}: support entropy"),
        )
        for column, panel in enumerate(panels):
            canvas[row_index * 180:(row_index + 1) * 180, column * 320:(column + 1) * 320] = panel
    path = directory / f"{unit['research_unit_id']}_temporal_coordinate_summary.png"
    cv2.imwrite(str(path), canvas)
    return {
        "case_id": f"{unit['research_unit_id']}-SUMMARY",
        "artifact_type": "temporal_coordinate_support_summary",
        "research_unit_id": unit["research_unit_id"], "research_unit_type": unit["research_unit_type"],
        "scene": unit["scene"], "canonical_vehicle_id": unit["canonical_vehicle_id"],
        "segment_id": unit["segment_id"], "artifact_path": str(path), "review_status": review_status,
        "notes": "continuous response mean, fixed 0.35 support occupancy, and temporal entropy; metrics remain separate",
    }


def build_vehicle_unit(rows: Sequence[dict[str, str]], role: str) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row["sar_frame_index"]))
    raw_anchors = [anchor_from_row(row, "raw") for row in ordered]
    smooth_anchors = [anchor_from_row(row, "smoothed") for row in ordered]
    raw_angles = [long_axis_unsigned_deg(anchor) for anchor in raw_anchors]
    smooth_angles = [long_axis_unsigned_deg(anchor) for anchor in smooth_anchors]
    reference_long = float(statistics.median(max(anchor["w"], anchor["h"]) for anchor in raw_anchors))
    reference_short = float(statistics.median(min(anchor["w"], anchor["h"]) for anchor in raw_anchors))
    world_center, world_half_x, world_half_y = world_geometry(ordered)
    raw_axes = continuous_axes(raw_angles)
    smooth_axes = continuous_axes(smooth_angles)
    relative_view_angles = [radar_in_body(anchor, axes[0], axes[1])[2] for anchor, axes in zip(raw_anchors, raw_axes)]
    return {
        "research_unit_id": ordered[0]["segment_id"], "research_unit_type": "vehicle_thread",
        "scene": ordered[0]["scene"], "canonical_vehicle_id": ordered[0]["canonical_vehicle_id"],
        "benchmark_role": ordered[0]["benchmark_role"], "research_role": role,
        "segment_id": ordered[0]["segment_id"], "source_trajectory_segment_id": ordered[0]["segment_id"],
        "rows": ordered, "raw_anchors": raw_anchors, "smooth_anchors": smooth_anchors,
        "raw_angles": raw_angles, "smooth_angles": smooth_angles,
        "raw_axes": raw_axes, "smooth_axes": smooth_axes, "relative_view_angles": relative_view_angles,
        "reference_long": reference_long, "reference_short": reference_short,
        "world_center": world_center, "world_half_x": world_half_x, "world_half_y": world_half_y,
    }


def build_fixed_background_unit(source: Mapping[str, Any], backgrounds: Sequence[dict[str, str]]) -> dict[str, Any]:
    row = next(item for item in backgrounds if item["background_thread_id"] == FIXED_BACKGROUND_ID)
    source_rows = source["rows"]
    middle = len(source_rows) // 2
    fixed = offset_anchor(source["smooth_anchors"][middle], parse_float(row["offset_radial_px"]), parse_float(row["offset_tangential_px"]))
    raw_middle = source["raw_anchors"][middle]
    smooth_middle = source["smooth_anchors"][middle]
    pseudo_raw: list[dict[str, float]] = []
    pseudo_smooth: list[dict[str, float]] = []
    for raw, smooth in zip(source["raw_anchors"], source["smooth_anchors"]):
        raw_anchor = dict(raw)
        raw_anchor["cx"] = fixed["cx"] + raw["cx"] - raw_middle["cx"]
        raw_anchor["cy"] = fixed["cy"] + raw["cy"] - raw_middle["cy"]
        smooth_anchor = dict(smooth)
        smooth_anchor["cx"] = fixed["cx"] + smooth["cx"] - smooth_middle["cx"]
        smooth_anchor["cy"] = fixed["cy"] + smooth["cy"] - smooth_middle["cy"]
        pseudo_raw.append(raw_anchor); pseudo_smooth.append(smooth_anchor)
    fixed_half_x = source["reference_long"] * 0.5 * CROP_EXPANSION
    fixed_half_y = source["reference_short"] * 0.5 * CROP_EXPANSION
    relative_view_angles = [radar_in_body(anchor, axes[0], axes[1])[2] for anchor, axes in zip(pseudo_raw, source["raw_axes"])]
    return {
        "research_unit_id": FIXED_BACKGROUND_UNIT, "research_unit_type": "fixed_world_background_counterfactual",
        "scene": source["scene"], "canonical_vehicle_id": source["canonical_vehicle_id"],
        "benchmark_role": "counterfactual", "research_role": "fixed_world_background_diagnostic",
        "segment_id": FIXED_BACKGROUND_ID, "source_trajectory_segment_id": source["segment_id"],
        "rows": source_rows, "raw_anchors": pseudo_raw, "smooth_anchors": pseudo_smooth,
        "raw_angles": source["raw_angles"], "smooth_angles": source["smooth_angles"],
        "raw_axes": source["raw_axes"], "smooth_axes": source["smooth_axes"],
        "relative_view_angles": relative_view_angles,
        "reference_long": source["reference_long"], "reference_short": source["reference_short"],
        "world_center": np.asarray([fixed["cx"], fixed["cy"]], dtype=np.float64),
        "world_half_x": fixed_half_x, "world_half_y": fixed_half_y,
        "background_quality_status": row["background_quality_status"],
        "background_definition": "frozen S1L fixed_strong_linear_background; source vehicle trajectory translated through fixed world centre",
    }


def build_unit_arrays(unit: Mapping[str, Any]) -> dict[str, np.ndarray]:
    arrays: dict[str, list[np.ndarray]] = defaultdict(list)
    body_half_x = float(unit["reference_long"]) * 0.5 * CROP_EXPANSION
    body_half_y = float(unit["reference_short"]) * 0.5 * CROP_EXPANSION
    image_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for index, row in enumerate(unit["rows"]):
        frame = int(row["sar_frame_index"])
        path = image_path(unit["scene"], frame)
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(path)
        blurred = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
        image_cache[frame] = (image, blurred)
        raw_anchor = unit["raw_anchors"][index]
        smooth_anchor = unit["smooth_anchors"][index]
        raw_radial, raw_tangential = radial_tangential(raw_anchor)
        smooth_radial, smooth_tangential = radial_tangential(smooth_anchor)
        definitions = {
            "world": (unit["world_center"], np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0]), unit["world_half_x"], unit["world_half_y"]),
            "raw_crop": (
                np.asarray([raw_anchor["cx"], raw_anchor["cy"]]), raw_tangential, raw_radial,
                parse_float(row["raw_half_extent_tangential_px"]) * CROP_EXPANSION,
                parse_float(row["raw_half_extent_radial_px"]) * CROP_EXPANSION,
            ),
            "smoothed_crop": (
                np.asarray([smooth_anchor["cx"], smooth_anchor["cy"]]), smooth_tangential, smooth_radial,
                parse_float(row["smoothed_half_extent_tangential_px"]) * CROP_EXPANSION,
                parse_float(row["smoothed_half_extent_radial_px"]) * CROP_EXPANSION,
            ),
            "raw_body": (
                np.asarray([raw_anchor["cx"], raw_anchor["cy"]]), unit["raw_axes"][index][0], unit["raw_axes"][index][1],
                body_half_x, body_half_y,
            ),
            "smoothed_body": (
                np.asarray([smooth_anchor["cx"], smooth_anchor["cy"]]), unit["smooth_axes"][index][0], unit["smooth_axes"][index][1],
                body_half_x, body_half_y,
            ),
        }
        for representation, (center, axis_x, axis_y, half_x, half_y) in definitions.items():
            raw, valid = warp_axes(image, center, axis_x, axis_y, float(half_x), float(half_y))
            blur, _ = warp_axes(blurred, center, axis_x, axis_y, float(half_x), float(half_y))
            score = normalized_score(
                blur, valid, parse_float(row["local_background_median"]), parse_float(row["thread_raw_p99"]),
            )
            arrays[f"{representation}_raw"].append(raw.astype(np.uint8))
            arrays[f"{representation}_score"].append(np.round(score * 255.0).astype(np.uint8))
            arrays[f"{representation}_valid"].append(valid.astype(np.uint8))
    return {key: np.stack(value, axis=0) for key, value in arrays.items()}


def frame_rows_for_unit(unit: Mapping[str, Any], arrays: Mapping[str, np.ndarray], bundle_path: Path) -> list[dict[str, Any]]:
    frames = [int(row["sar_frame_index"]) for row in unit["rows"]]
    raw_steps = step_rates(frames, unit["raw_angles"])
    smooth_steps = step_rates(frames, unit["smooth_angles"])
    output: list[dict[str, Any]] = []
    for index, row in enumerate(unit["rows"]):
        raw_anchor = unit["raw_anchors"][index]
        smooth_anchor = unit["smooth_anchors"][index]
        raw_u, raw_v = unit["raw_axes"][index]
        smooth_u, smooth_v = unit["smooth_axes"][index]
        raw_aspect = max(raw_anchor["w"], raw_anchor["h"]) / max(1e-9, min(raw_anchor["w"], raw_anchor["h"]))
        smooth_aspect = max(smooth_anchor["w"], smooth_anchor["h"]) / max(1e-9, min(smooth_anchor["w"], smooth_anchor["h"]))
        center_spread = parse_float(row["gt_center_spread_px"], 0.0)
        size_spread = parse_float(row["gt_size_spread_px"], 0.0)
        axis_status, axis_reasons = reliability(raw_aspect, raw_steps[index], center_spread, size_spread, unit["reference_short"])
        center_delta = math.hypot(raw_anchor["cx"] - smooth_anchor["cx"], raw_anchor["cy"] - smooth_anchor["cy"])
        raw_missing = 1.0 - float(arrays["raw_body_valid"][index].mean())
        smooth_missing = 1.0 - float(arrays["smoothed_body_valid"][index].mean())
        raw_registration, raw_reasons = registration_status(axis_status, center_delta, unit["reference_short"], raw_missing)
        smooth_registration, smooth_reasons = registration_status(axis_status, center_delta, unit["reference_short"], smooth_missing)
        raw_radar_u, raw_radar_v, raw_view = radar_in_body(raw_anchor, raw_u, raw_v)
        smooth_radar_u, smooth_radar_v, smooth_view = radar_in_body(smooth_anchor, smooth_u, smooth_v)
        output.append({
            "research_unit_id": unit["research_unit_id"], "research_unit_type": unit["research_unit_type"],
            "scene": unit["scene"], "canonical_vehicle_id": unit["canonical_vehicle_id"],
            "benchmark_role": unit["benchmark_role"], "research_role": unit["research_role"],
            "segment_id": unit["segment_id"], "source_trajectory_segment_id": unit["source_trajectory_segment_id"],
            "sar_frame_index": row["sar_frame_index"], "sar_time_sec": row["sar_time_sec"], "bundle_index": index,
            "source_image_path": row["raw_image_path"], "source_image_sha256": row["raw_image_sha256"],
            "raw_gt_center_x_px": fmt(raw_anchor["cx"]), "raw_gt_center_y_px": fmt(raw_anchor["cy"]),
            "raw_gt_width_px": fmt(raw_anchor["w"]), "raw_gt_height_px": fmt(raw_anchor["h"]), "raw_gt_angle_deg": fmt(raw_anchor["angle"]),
            "smoothed_gt_center_x_px": fmt(smooth_anchor["cx"]), "smoothed_gt_center_y_px": fmt(smooth_anchor["cy"]),
            "smoothed_gt_width_px": fmt(smooth_anchor["w"]), "smoothed_gt_height_px": fmt(smooth_anchor["h"]), "smoothed_gt_angle_deg": fmt(smooth_anchor["angle"]),
            "raw_body_long_axis_unsigned_deg": fmt(unit["raw_angles"][index]),
            "smoothed_body_long_axis_unsigned_deg": fmt(unit["smooth_angles"][index]),
            "raw_body_axis_u_x": fmt(raw_u[0]), "raw_body_axis_u_y": fmt(raw_u[1]),
            "raw_body_axis_v_x": fmt(raw_v[0]), "raw_body_axis_v_y": fmt(raw_v[1]),
            "smoothed_body_axis_u_x": fmt(smooth_u[0]), "smoothed_body_axis_u_y": fmt(smooth_u[1]),
            "smoothed_body_axis_v_x": fmt(smooth_v[0]), "smoothed_body_axis_v_y": fmt(smooth_v[1]),
            "reference_long_axis_px": fmt(unit["reference_long"]), "reference_short_axis_px": fmt(unit["reference_short"]),
            "raw_aspect_ratio": fmt(raw_aspect), "smoothed_aspect_ratio": fmt(smooth_aspect),
            "raw_axis_step_deg_per_frame": fmt(raw_steps[index]), "smoothed_axis_step_deg_per_frame": fmt(smooth_steps[index]),
            "gt_center_spread_px": fmt(center_spread), "gt_size_spread_px": fmt(size_spread),
            "raw_smoothed_center_delta_px": fmt(center_delta),
            "raw_smoothed_center_delta_over_ref_short": fmt(center_delta / max(1e-9, unit["reference_short"])),
            "axis_reliability": axis_status, "axis_reliability_reasons": ";".join(axis_reasons),
            "raw_body_boundary_missing_fraction": fmt(raw_missing), "smoothed_body_boundary_missing_fraction": fmt(smooth_missing),
            "raw_body_registration_status": raw_registration, "raw_body_registration_reasons": ";".join(raw_reasons),
            "smoothed_body_registration_status": smooth_registration, "smoothed_body_registration_reasons": ";".join(smooth_reasons),
            "raw_radar_direction_body_u": fmt(raw_radar_u), "raw_radar_direction_body_v": fmt(raw_radar_v),
            "smoothed_radar_direction_body_u": fmt(smooth_radar_u), "smoothed_radar_direction_body_v": fmt(smooth_radar_v),
            "raw_relative_observation_angle_deg_mod180": fmt(raw_view),
            "smoothed_relative_observation_angle_deg_mod180": fmt(smooth_view),
            "canonical_field_bundle_path": str(bundle_path), "world_field_key": "world_raw",
            "raw_crop_field_key": "raw_crop_raw", "smoothed_crop_field_key": "smoothed_crop_raw",
            "raw_body_field_key": "raw_body_raw", "smoothed_body_field_key": "smoothed_body_raw",
            "valid_mask_key_suffix": "_valid", "local_background_key_suffix": "_score",
            "axis_sign_rule": "temporal_continuity_first_positive_x_no_front_rear",
            "scale_semantics": "thread_robust_GT_relative_display_pixel_scale_not_metric",
            "gt_information_debt": "GT_DISCOVERY_ONLY;FUTURE_REPLACEABLE;DEPLOYMENT_SOURCE_NOT_READY"
            + (";GT_PRECISION_DEPENDENT" if raw_registration != "REGISTRATION_RELIABLE" else ""),
            "notes": "fixed 180-degree unsigned axis; no front/rear semantics; background unit inherits the source vehicle trajectory only as a falsification transform",
        })
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-status", choices=("pending_direct_review", "directly_reviewed_complete"), default="pending_direct_review")
    args = parser.parse_args()

    ARRAY_ROOT.mkdir(parents=True, exist_ok=True)
    VISUAL_ROOT.mkdir(parents=True, exist_ok=True)
    local_fields = read_csv(LOCAL_FIELD_PATH)
    observations = read_csv(OBSERVATION_PATH)
    backgrounds = read_csv(BACKGROUND_PATH)
    rows_by_segment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in local_fields:
        if row["segment_id"] in CORE_SEGMENTS:
            rows_by_segment[row["segment_id"]].append(row)

    vehicle_units = [build_vehicle_unit(rows_by_segment[segment_id], role) for segment_id, role in CORE_SEGMENTS.items()]
    source_unit = next(unit for unit in vehicle_units if unit["segment_id"] == FIXED_BACKGROUND_SOURCE_SEGMENT)
    units = vehicle_units + [build_fixed_background_unit(source_unit, backgrounds)]

    observations_by_segment_frame: dict[str, dict[int, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in observations:
        observations_by_segment_frame[row["segment_id"]][int(row["sar_frame_index"])].append(row)

    all_frame_rows: list[dict[str, Any]] = []
    competition_rows: list[dict[str, Any]] = []
    visual_rows: list[dict[str, Any]] = []
    unit_summaries: dict[str, dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}
    for unit in units:
        arrays = build_unit_arrays(unit)
        bundle_path = ARRAY_ROOT / f"{unit['research_unit_id']}_canonical_fields.npz"
        np.savez_compressed(bundle_path, frames=np.asarray([int(row["sar_frame_index"]) for row in unit["rows"]], dtype=np.int32), **arrays)
        all_frame_rows.extend(frame_rows_for_unit(unit, arrays, bundle_path))

        summaries: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        frames = [int(row["sar_frame_index"]) for row in unit["rows"]]
        view_angles = unit["relative_view_angles"]
        for representation in REPRESENTATIONS:
            scores = arrays[f"{representation}_score"].astype(np.float32) / 255.0
            valids = arrays[f"{representation}_valid"].astype(bool)
            metrics, mean_score, occupancy, entropy = stack_metrics(scores, valids, frames, view_angles)
            summaries[representation] = (mean_score, occupancy, entropy)
            observation_values = {
                "observation_frame_count": 0,
                "observation_centroid_temporal_mad_norm": math.nan,
                "relation_distance_q50_temporal_cv": math.nan,
                "relation_distance_q90_temporal_cv": math.nan,
                "observation_orientation_axial_dispersion_deg": math.nan,
            }
            if unit["research_unit_type"] == "vehicle_thread":
                observation_values = observation_metrics(
                    representation, unit["rows"], observations_by_segment_frame[unit["segment_id"]],
                    unit["raw_axes"], unit["smooth_axes"], unit["world_center"], unit["world_half_x"], unit["world_half_y"],
                )
            competition_rows.append({
                "research_unit_id": unit["research_unit_id"], "research_unit_type": unit["research_unit_type"],
                "scene": unit["scene"], "canonical_vehicle_id": unit["canonical_vehicle_id"],
                "benchmark_role": unit["benchmark_role"], "research_role": unit["research_role"],
                "segment_id": unit["segment_id"], "representation": representation,
                "coordinate_family": COORDINATE_FAMILY[representation], "frame_count": len(frames),
                "support_level": fmt(SUPPORT_LEVEL),
                "response_lineage": "frozen S1L Gaussian sigma 1.0 plus local-background normalization; fixed support level 0.35",
                **{key: fmt(value) if key != "nonadjacent_similar_view_pair_count" else value for key, value in metrics.items()},
                **{key: fmt(value) if key != "observation_frame_count" else value for key, value in observation_values.items()},
                "automatic_attribution_label": "UNASSIGNED_REQUIRES_DIRECT_VISUAL_REVIEW",
                "review_status": args.review_status,
                "notes": "no weighted score and no automatic winner; low entropy alone is not vehicle evidence; response-centroid grid metrics are within-representation diagnostics because world uses a fixed trajectory canvas",
            })
        unit_summaries[unit["research_unit_id"]] = summaries
        visual_rows.extend(generate_frame_pages(unit, arrays, unit["rows"], args.review_status))
        visual_rows.append(generate_summary_page(unit, summaries, args.review_status))

    write_csv(FRAME_OUTPUT_PATH, all_frame_rows, FRAME_FIELDS)
    write_csv(COMPETITION_OUTPUT_PATH, competition_rows, COMPETITION_FIELDS)
    write_csv(VISUAL_OUTPUT_PATH, visual_rows, VISUAL_FIELDS)
    write_csv(TEMP_VISUAL_MANIFEST_PATH, visual_rows, VISUAL_FIELDS)

    summary = {
        "work_name": "S1-L Body Support Attribution and GT-Neighborhood Optimality Audit",
        "scope": "minimum world/crop/body coordinate casebook only",
        "review_status": args.review_status,
        "final_stage_state_assigned": False,
        "s1d_allowed": False,
        "automatic_annotation_allowed": False,
        "gt_neighborhood_perturbation_run": False,
        "latent_body_support_reconstruction_run": False,
        "vehicle_unit_count": len(vehicle_units),
        "background_counterfactual_unit_count": 1,
        "frame_manifest_row_count": len(all_frame_rows),
        "coordinate_competition_row_count": len(competition_rows),
        "visual_artifact_count": len(visual_rows),
        "output_paths": {
            "frame_manifest": str(FRAME_OUTPUT_PATH),
            "coordinate_competition": str(COMPETITION_OUTPUT_PATH),
            "visual_manifest": str(VISUAL_OUTPUT_PATH),
            "temporary_arrays": str(ARRAY_ROOT),
            "temporary_visuals": str(VISUAL_ROOT),
        },
        "fixed_background_note": "reuses frozen S1L-BG-0011 fixed strong linear background, whose old quality status was insufficient_counterfactual_quality; diagnostic only",
        "non_execution": [
            "S1-D", "automatic_annotation", "final_SAR_box", "GT_modification", "candidate_bank",
            "selector", "ranking", "oracle", "weighted_total", "GT_IoU_decision", "training",
            "GT_neighborhood_optimization", "latent_support_reconstruction",
        ],
    }
    write_json(SUMMARY_PATH, summary)
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(
            "2026-07-15 MINIMUM_CASEBOOK_RUN\n"
            f"review_status={args.review_status}\n"
            f"frame_manifest_rows={len(all_frame_rows)}\n"
            f"competition_rows={len(competition_rows)}\n"
            f"visual_artifacts={len(visual_rows)}\n"
            f"output_root={OUTPUT_ROOT}\n"
            "gt_neighborhood_perturbation_run=false\n"
            "latent_body_support_reconstruction_run=false\n"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
