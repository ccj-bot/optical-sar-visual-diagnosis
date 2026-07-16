#!/usr/bin/env python3
from __future__ import annotations

"""Run the bounded S1-L semantic-correction and observability audit."""

import argparse
import bisect
import csv
import hashlib
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTIC_DIR = Path(__file__).resolve().parent
if str(DIAGNOSTIC_DIR) not in sys.path:
    sys.path.insert(0, str(DIAGNOSTIC_DIR))

import run_oty2_s1l_body_support_coordinate_casebook as base  # noqa: E402


MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")
OUTPUT_ROOT = WORKSPACE_ROOT / "output" / "oty2_s1l_optical_conditioned_support_observability_20260716"
VISUAL_ROOT = OUTPUT_ROOT / "visual_casebook"
SUMMARY_PATH = OUTPUT_ROOT / "optical_conditioned_support_observability_summary.json"
LOG_PATH = WORKSPACE_ROOT / "logs" / "oty2_s1l_optical_conditioned_support_observability_20260716.log"

LOCAL_FIELD_PATH = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
COORDINATE_FRAME_PATH = MANIFEST_DIR / "oty2_s1l_body_support_coordinate_frames.csv"
BACKGROUND_PATH = MANIFEST_DIR / "oty2_s1l_background_counterfactuals.csv"

UNIT_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_research_units.csv"
SAMPLING_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_sampling_normalization_audit.csv"
REPRESENTATION_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_representation_metrics.csv"
PAIR_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_pair_incremental_metrics.csv"
SENSITIVITY_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_pair_and_frame_sensitivity.csv"
PROFILE_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_parameter_metric_profiles.csv"
OBSERVABILITY_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_parameter_observability.csv"
VISUAL_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1l_optical_conditioned_visual_manifest.csv"

CORE_SEGMENTS = {
    "S0MV-GM_RM017-PV002-SEG02": "mechanism_discovery_gt_proxy",
    "S0MV-GM_RM017-PV003-SEG01": "within_scene_other_vehicle_fixed_rule_replay",
    "S0MV-GM_RM017-PV004-SEG01": "within_scene_other_vehicle_fixed_rule_replay",
}
DEVELOPMENT_SEGMENT = "S0MV-GM_RM017-PV002-SEG02"
OTHER_VEHICLE_REPLAY_SEGMENTS = (
    "S0MV-GM_RM017-PV003-SEG01",
    "S0MV-GM_RM017-PV004-SEG01",
)

GRID_WIDTH = 256
GRID_HEIGHT = 128
CONTEXT_FACTOR = 1.75
SUPPORT_LEVEL = 0.35
PAIR_MIN_FRAME_GAP = 10
PAIR_MAX_VIEW_DIFF_DEG = 5.0
SHUFFLE_SEED = 1702
TIME_SHIFT_FRAMES = 8
CANNY_LOW_THRESHOLD = 40
CANNY_HIGH_THRESHOLD = 100
CANNY_APERTURE_SIZE = 3
CANNY_L2_GRADIENT = True
STRUCTURE_MASK_EROSION_PX = 6
STRUCTURE_INPAINT_RADIUS_PX = 3.0
PAIR_RULE_ID = "SOURCE_POSITIVE_GT_CONDITIONED_VIEW_GAP10_DIFF5_RELIABILITY_AND_FINITE_COMMON_VALID_PROJECTED_NO_RESELECTION"
PAIR_PROJECTION_RULE = "SOURCE_POSITIVE_PAIR_SET_FRAME_INTERSECTION_NO_RESELECTION"

NORMALIZED_X = np.linspace(-1.0, 1.0, GRID_WIDTH, dtype=np.float32)[None, :]
NORMALIZED_Y = np.linspace(-1.0, 1.0, GRID_HEIGHT, dtype=np.float32)[:, None]
CENTRAL_CORE_MASK = (
    (np.abs(NORMALIZED_X) <= 1.0 / CONTEXT_FACTOR)
    & (np.abs(NORMALIZED_Y) <= 1.0 / CONTEXT_FACTOR)
)
STRUCTURE_EROSION_KERNEL = np.ones(
    (2 * STRUCTURE_MASK_EROSION_PX + 1, 2 * STRUCTURE_MASK_EROSION_PX + 1),
    dtype=np.uint8,
)

REPRESENTATIONS = (
    "WORLD_FIXED",
    "CENTER_TRACKED_CARTESIAN",
    "CENTER_TRACKED_RADIAL",
    "CENTER_TRACKED_BODY",
)
NORMALIZATION_PATHS = ("FIXED_REFERENCE", "CANDIDATE_LOCAL_REESTIMATED")
ANCHOR_VARIANTS = ("raw_gt", "smoothed_gt")
AXIS_RULES = (
    "GT_DERIVED_UNSIGNED_BODY",
    "THREAD_FIXED_MEDIAN_AXIS",
    "FRAME_SHUFFLED_AXIS",
    "TIME_SHIFTED_AXIS",
    "GT_AXIS_PLUS_90",
    "TRAJECTORY_TANGENT_AXIS",
    "GLOBAL_FIXED_AXIS",
)
PARAMETER_GRIDS: dict[str, tuple[float, ...]] = {
    "CENTER_RADIAL": (-0.25, -0.125, 0.0, 0.125, 0.25),
    "CENTER_TANGENTIAL": (-0.25, -0.125, 0.0, 0.125, 0.25),
    "LONG_SCALE": (0.85, 0.925, 1.0, 1.075, 1.15),
    "SHORT_SCALE": (0.85, 0.925, 1.0, 1.075, 1.15),
    "AXIS_UNSIGNED": (-12.0, -6.0, 0.0, 6.0, 12.0),
}

# B3 and B4 are frozen after pre-experiment hard-constraint background audits.
# Spatial clusters describe baseline equal-support footprint separation only;
# they are not statistical-independence groups.
HARD_BACKGROUND_CONFIG: dict[str, dict[str, Any]] = {
    "S1L-BG-0010": {
        "moving": True,
        "quality": "FROZEN_USABLE_PROPOSAL;SAME_BASELINE_SPATIAL_CLUSTER_AS_BG0011",
        "spatial_control_group": "GM_RM017|SPATIAL_CLUSTER_1",
        "parameter_envelope_group": "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_1",
        "control_semantic_role": "MOVING_SAME_AZIMUTH_BACKGROUND",
    },
    "S1L-BG-0011": {
        "moving": False,
        "quality": "CONTROL_QUALITY_LIMITED;STRONG_LINE_ROLE;SAME_BASELINE_SPATIAL_CLUSTER_AS_BG0010",
        "spatial_control_group": "GM_RM017|SPATIAL_CLUSTER_1",
        "parameter_envelope_group": "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_1",
        "control_semantic_role": "FIXED_STRONG_LINEAR_SAME_CLUSTER_DIAGNOSTIC",
    },
    "S1L-BG-OCS-B3-SA35N": {
        "offset_radial_px": -209.722594,
        "offset_tangential_px": 0.0,
        "moving": True,
        "quality": "B3_HARD_CONSTRAINT_PASS;HARD_SCATTER_ROLE_SUPPORTED;VEHICLE_COMPLEXITY_MATCH_PARTIAL;USABLE_VEHICLE_CLASS_NEGATIVE_WITH_LIMITATIONS",
        "background_type": "hard_scatter_partial_complexity_match",
        "reviewed_gt_overlap": 0.0,
        "spatial_control_group": "GM_RM017|SPATIAL_CLUSTER_2",
        "parameter_envelope_group": "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_2",
        "control_semantic_role": "MOVING_HARD_SCATTER_PARTIAL_COMPLEXITY_BACKGROUND",
        "notes": "first hard-constraint-feasible offset in the frozen proposal enumeration; valid mask 1.0, zero reviewed-GT overlap, spatially disjoint from BG0010/BG0011; direct 65-frame review found isolated strong scatter, sidelobes and arcs but no persistent vehicle-shaped support; complexity match remains partial",
    },
    "S1L-BG-OCS-B4-FX88": {
        "offset_radial_px": 479.36592922347614,
        "offset_tangential_px": 667.2840797804607,
        "moving": False,
        "quality": "B4_HARD_CONSTRAINT_PASS;FIXED_ANISOTROPIC_SPECKLE_ROLE;NOT_STRONG_LINE;BASELINE_SPATIALLY_DISJOINT;PARAMETER_ENVELOPE_CLUSTER_LIMITED",
        "background_type": "fixed_anisotropic_speckle_not_strong_line",
        "reviewed_gt_overlap": 0.0,
        "spatial_control_group": "GM_RM017|SPATIAL_CLUSTER_3",
        "parameter_envelope_group": "GM_RM017|PARAMETER_ENVELOPE_CLUSTER_1",
        "control_semantic_role": "FIXED_ANISOTROPIC_SPECKLE_CONTROL_NOT_STRONG_LINE",
        "notes": "FX_8_8 from the frozen fixed-offset enumeration; full valid support, zero reviewed-GT overlap and zero baseline rotated-footprint overlap with BG0010, BG0011 and B3; direct 65-frame review found no persistent strong line or vehicle-shaped support; strict one-dimensional parameter envelope is not disjoint from BG0010",
    },
}

CONFIG = {
    "grid": [GRID_WIDTH, GRID_HEIGHT],
    "context_factor": CONTEXT_FACTOR,
    "support_level": SUPPORT_LEVEL,
    "pair_rule": {"min_frame_gap": PAIR_MIN_FRAME_GAP, "max_view_diff_deg": PAIR_MAX_VIEW_DIFF_DEG},
    "shuffle_seed": SHUFFLE_SEED,
    "time_shift_frames": TIME_SHIFT_FRAMES,
    "representations": REPRESENTATIONS,
    "normalization_paths": NORMALIZATION_PATHS,
    "anchor_variants": ANCHOR_VARIANTS,
    "axis_rules": AXIS_RULES,
    "parameter_grids": PARAMETER_GRIDS,
    "hard_background_config": HARD_BACKGROUND_CONFIG,
    "pair_membership_reference": "SOURCE_POSITIVE|CENTER_TRACKED_BODY|GT_DERIVED_UNSIGNED_BODY|FIXED_REFERENCE|FINITE_COMMON_VALID",
    "pair_rule_id": PAIR_RULE_ID,
    "pair_projection_rule": PAIR_PROJECTION_RULE,
    "pair_sensitivity_modes": ("LEAVE_ONE_PAIR_OUT", "LEAVE_ONE_FRAME_OUT"),
    "normalization_failure_policy": "INVALID_EVIDENCE_NAN_EXCLUDED_FROM_PARETO",
    "body_oriented_window_attribution": "AXIS_ORIENTATION_PLUS_ROTATED_ANISOTROPIC_SUPPORT_FOOTPRINT_NOT_PURE_BODY_AXIS",
    "parameter_observability_contract": "GRID_NONDOMINANCE_DIAGNOSTIC_ONLY;ALL_FORMAL_OBSERVABILITY_STATES_NOT_IDENTIFIABLE;NO_PHYSICAL_BOUNDS",
    "scale_profile_contract": "FIXED_256X128_WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED",
    "temporal_test_contract": "CORRESPONDENCE_CONTROLS_ONLY;NO_ARROW_OF_TIME_METRIC",
    "background_cluster_scope": "BASELINE_EQUAL_SUPPORT_3_SPATIAL_CLUSTERS;STRICT_ONE_DIM_PARAMETER_ENVELOPE_2_CLUSTERS;NOT_STATISTICAL_INDEPENDENCE",
    "orientation_estimator": "STRUCTURE_TENSOR_ORIENTATION_PROXY",
    "topology_estimator": "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    "canny_config": {
        "low_threshold": CANNY_LOW_THRESHOLD,
        "high_threshold": CANNY_HIGH_THRESHOLD,
        "aperture_size": CANNY_APERTURE_SIZE,
        "l2_gradient": CANNY_L2_GRADIENT,
        "input_quantization": "NORMALIZED_SCORE_TO_UINT8",
    },
    "structure_boundary_guard": {
        "invalid_fill": "CV2_TELEA_INPAINT",
        "inpaint_radius_px": STRUCTURE_INPAINT_RADIUS_PX,
        "valid_mask_erosion_px": STRUCTURE_MASK_EROSION_PX,
    },
}
CONFIG_HASH = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode("utf-8")).hexdigest()

METRIC_DIRECTIONS = {
    "FIELD_NCC": "HIGHER_IS_BETTER",
    "ORIENTATION_PAIR_AGREEMENT": "HIGHER_IS_BETTER",
    "ORIENTATION_ANGLE_DIFF_DEG": "LOWER_IS_BETTER",
    "THIN_EDGE_JACCARD": "HIGHER_IS_BETTER",
    "THIN_EDGE_ENDPOINT_COUNT_ABSDIFF": "LOWER_IS_BETTER",
    "THIN_EDGE_BRANCH_COUNT_ABSDIFF": "LOWER_IS_BETTER",
    "THIN_EDGE_KEYPOINT_RELATION_DISTANCE_ABSDIFF": "LOWER_IS_BETTER",
    "THIN_EDGE_CENTROID_DISTANCE": "LOWER_IS_BETTER",
    "THIN_EDGE_ADJACENCY_MEAN_DEGREE_ABSDIFF": "LOWER_IS_BETTER",
    "THIN_EDGE_COLLINEARITY_PROXY_ABSDIFF": "LOWER_IS_BETTER",
    "THIN_EDGE_PARALLEL_REPRESENTATION_X_AXIS_FRACTION_ABSDIFF": "LOWER_IS_BETTER",
    "THIN_EDGE_PARALLEL_REPRESENTATION_Y_AXIS_FRACTION_ABSDIFF": "LOWER_IS_BETTER",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fmt(value: Any, digits: int = 6) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return "" if not math.isfinite(number) else f"{number:.{digits}f}"


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def finite_median(values: Iterable[float]) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return statistics.median(finite) if finite else math.nan


def finite_mean(values: Iterable[float]) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return statistics.mean(finite) if finite else math.nan


def finite_cv(values: Iterable[float]) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return math.nan
    mean = statistics.mean(finite)
    return statistics.pstdev(finite) / abs(mean) if abs(mean) > 1e-12 else math.nan


def axial_difference(a: float, b: float) -> float:
    return base.axial_difference(float(a), float(b))


def axial_median(values: Sequence[float]) -> float:
    if not values:
        return math.nan
    radians = np.radians(np.asarray(values, dtype=np.float64) * 2.0)
    angle = math.degrees(math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean()))) * 0.5
    return angle % 180.0


def axis_from_angle(angle_deg: float) -> tuple[np.ndarray, np.ndarray]:
    angle = math.radians(float(angle_deg))
    u = np.asarray([math.cos(angle), math.sin(angle)], dtype=np.float64)
    v = np.asarray([-u[1], u[0]], dtype=np.float64)
    return u, v


def rotate_axes(axes: tuple[np.ndarray, np.ndarray], delta_deg: float) -> tuple[np.ndarray, np.ndarray]:
    u, v = axes
    angle = math.radians(float(delta_deg))
    cosine, sine = math.cos(angle), math.sin(angle)
    return u * cosine + v * sine, -u * sine + v * cosine


def footprint_polygon(center: np.ndarray, u: np.ndarray, v: np.ndarray, half_x: float, half_y: float) -> np.ndarray:
    return np.asarray([
        center - u * half_x - v * half_y,
        center + u * half_x - v * half_y,
        center + u * half_x + v * half_y,
        center - u * half_x + v * half_y,
    ], dtype=np.float64)


def polygon_text(points: np.ndarray) -> str:
    return ";".join(f"{point[0]:.3f},{point[1]:.3f}" for point in points)


@dataclass
class FrameFeatures:
    orientation_deg: float
    anisotropy: float
    orientation_coherence: float
    component_count: float
    endpoint_count: float
    branch_count: float
    thin_edge_fraction: float
    largest_component_fraction: float
    relation_distance_median: float
    thin_edge_centroid_x: float
    thin_edge_centroid_y: float
    adjacency_mean_degree: float
    collinearity: float
    parallel_x_axis_fraction: float
    parallel_y_axis_fraction: float
    structure_valid_fraction: float
    thin_edge_mask: np.ndarray


@dataclass
class Evaluation:
    scores: np.ndarray
    valids: np.ndarray
    features: list[FrameFeatures]
    normalization_rows: list[dict[str, Any]]
    adjacent_metrics: dict[str, float]


def orientation_features(score: np.ndarray, valid: np.ndarray) -> tuple[float, float, float]:
    field = score.astype(np.float32)
    gx = cv2.Sobel(field, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(field, cv2.CV_32F, 0, 1, ksize=3)
    usable = valid & np.isfinite(field)
    if int(usable.sum()) < 32:
        return math.nan, math.nan, math.nan
    jxx = float(np.sum(gx[usable] * gx[usable]))
    jyy = float(np.sum(gy[usable] * gy[usable]))
    jxy = float(np.sum(gx[usable] * gy[usable]))
    trace = jxx + jyy
    if trace <= 1e-8:
        return math.nan, math.nan, math.nan
    delta = math.sqrt(max(0.0, (jxx - jyy) ** 2 + 4.0 * jxy ** 2))
    anisotropy = delta / max(trace, 1e-12)
    gradient_angle = 0.5 * math.degrees(math.atan2(2.0 * jxy, jxx - jyy))
    line_angle = (gradient_angle + 90.0) % 180.0

    local_jxx = cv2.GaussianBlur(gx * gx, (0, 0), 2.0)
    local_jyy = cv2.GaussianBlur(gy * gy, (0, 0), 2.0)
    local_jxy = cv2.GaussianBlur(gx * gy, (0, 0), 2.0)
    local_trace = local_jxx + local_jyy
    local_delta = np.sqrt(np.maximum(0.0, (local_jxx - local_jyy) ** 2 + 4.0 * local_jxy ** 2))
    coherence = np.divide(local_delta, np.maximum(local_trace, 1e-6))
    return line_angle, anisotropy, float(np.median(coherence[usable]))


def topology_features(
    score: np.ndarray,
    valid: np.ndarray,
) -> tuple[int, int, int, float, float, float, float, float, float, float, float, float, np.ndarray]:
    field = score.astype(np.float32)
    if int(valid.sum()) < 32:
        empty = np.zeros_like(valid, dtype=bool)
        return 0, 0, 0, 0.0, 0.0, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan, empty
    field_u8 = np.round(np.clip(field, 0.0, 1.0) * 255.0).astype(np.uint8)
    thin_edge_mask = (
        cv2.Canny(
            field_u8,
            CANNY_LOW_THRESHOLD,
            CANNY_HIGH_THRESHOLD,
            apertureSize=CANNY_APERTURE_SIZE,
            L2gradient=CANNY_L2_GRADIENT,
        )
        > 0
    ) & valid
    count, labels = cv2.connectedComponents(thin_edge_mask.astype(np.uint8), connectivity=8)
    component_count = max(0, count - 1)
    sizes = np.bincount(labels.ravel(), minlength=count)[1:].astype(np.int64).tolist()
    total = int(thin_edge_mask.sum())
    largest_fraction = max(sizes, default=0) / max(total, 1)
    neighbors = cv2.filter2D(thin_edge_mask.astype(np.uint8), cv2.CV_16S, np.ones((3, 3), np.int16)) - thin_edge_mask.astype(np.int16)
    endpoints = thin_edge_mask & (neighbors == 1)
    branches = thin_edge_mask & (neighbors >= 3)
    adjacency_mean_degree = float(np.mean(neighbors[thin_edge_mask])) if total else math.nan

    thin_edge_y, thin_edge_x = np.nonzero(thin_edge_mask)
    centroid_x = math.nan
    centroid_y = math.nan
    collinearity = math.nan
    if total:
        normalized_points = np.column_stack(
            (NORMALIZED_X[0, thin_edge_x], NORMALIZED_Y[thin_edge_y, 0])
        ).astype(np.float64)
        centroid_x = float(np.mean(normalized_points[:, 0]))
        centroid_y = float(np.mean(normalized_points[:, 1]))
        if len(normalized_points) >= 3:
            covariance = np.cov(normalized_points, rowvar=False)
            eigenvalues = np.linalg.eigvalsh(covariance)
            collinearity = float(
                (eigenvalues[-1] - eigenvalues[0])
                / max(float(eigenvalues[-1] + eigenvalues[0]), 1e-12)
            )

    gx = cv2.Sobel(field, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(field, cv2.CV_32F, 0, 1, ksize=3)
    gradient_magnitude = np.hypot(gx, gy)
    tangent_usable = thin_edge_mask & (gradient_magnitude > 1e-6)
    parallel_x_fraction = math.nan
    parallel_y_fraction = math.nan
    if int(tangent_usable.sum()):
        tangent_angle = (
            np.degrees(np.arctan2(gy[tangent_usable], gx[tangent_usable])) + 90.0
        ) % 180.0
        diff_x = np.minimum(tangent_angle, 180.0 - tangent_angle)
        diff_y = np.abs(tangent_angle - 90.0)
        parallel_x_fraction = float(np.mean(diff_x <= 15.0))
        parallel_y_fraction = float(np.mean(diff_y <= 15.0))

    key_y, key_x = np.nonzero(endpoints | branches)
    relation_distance = math.nan
    if len(key_x) >= 2:
        if len(key_x) > 64:
            keep = np.linspace(0, len(key_x) - 1, 64, dtype=np.int64)
            key_x = key_x[keep]
            key_y = key_y[keep]
        points = np.column_stack((key_x / max(1, score.shape[1] - 1), key_y / max(1, score.shape[0] - 1)))
        distances = []
        for left in range(len(points)):
            for right in range(left + 1, len(points)):
                distances.append(float(np.linalg.norm(points[left] - points[right])))
        relation_distance = statistics.median(distances) if distances else math.nan
    return (
        component_count,
        int(endpoints.sum()),
        int(branches.sum()),
        total / max(1, int(valid.sum())),
        float(largest_fraction),
        relation_distance,
        centroid_x,
        centroid_y,
        adjacency_mean_degree,
        collinearity,
        parallel_x_fraction,
        parallel_y_fraction,
        thin_edge_mask,
    )


def extract_features(score: np.ndarray, valid: np.ndarray) -> FrameFeatures:
    structure_valid = cv2.erode(
        valid.astype(np.uint8),
        STRUCTURE_EROSION_KERNEL,
        iterations=1,
    ).astype(bool)
    if int(structure_valid.sum()) < 32:
        return invalid_frame_features(valid.shape)
    structure_score = score.astype(np.float32).copy()
    if not bool(valid.all()):
        structure_score = cv2.inpaint(
            structure_score,
            (~valid).astype(np.uint8) * 255,
            STRUCTURE_INPAINT_RADIUS_PX,
            cv2.INPAINT_TELEA,
        )
    orientation, anisotropy, coherence = orientation_features(
        structure_score,
        structure_valid,
    )
    (
        components,
        endpoints,
        branches,
        length_fraction,
        largest,
        relation_distance,
        centroid_x,
        centroid_y,
        adjacency_mean_degree,
        collinearity,
        parallel_x_fraction,
        parallel_y_fraction,
        thin_edge_mask,
    ) = topology_features(structure_score, structure_valid)
    return FrameFeatures(
        orientation_deg=orientation,
        anisotropy=anisotropy,
        orientation_coherence=coherence,
        component_count=components,
        endpoint_count=endpoints,
        branch_count=branches,
        thin_edge_fraction=length_fraction,
        largest_component_fraction=largest,
        relation_distance_median=relation_distance,
        thin_edge_centroid_x=centroid_x,
        thin_edge_centroid_y=centroid_y,
        adjacency_mean_degree=adjacency_mean_degree,
        collinearity=collinearity,
        parallel_x_axis_fraction=parallel_x_fraction,
        parallel_y_axis_fraction=parallel_y_fraction,
        structure_valid_fraction=float(structure_valid.mean()),
        thin_edge_mask=thin_edge_mask,
    )


def invalid_frame_features(shape: tuple[int, int]) -> FrameFeatures:
    return FrameFeatures(
        orientation_deg=math.nan,
        anisotropy=math.nan,
        orientation_coherence=math.nan,
        component_count=math.nan,
        endpoint_count=math.nan,
        branch_count=math.nan,
        thin_edge_fraction=math.nan,
        largest_component_fraction=math.nan,
        relation_distance_median=math.nan,
        thin_edge_centroid_x=math.nan,
        thin_edge_centroid_y=math.nan,
        adjacency_mean_degree=math.nan,
        collinearity=math.nan,
        parallel_x_axis_fraction=math.nan,
        parallel_y_axis_fraction=math.nan,
        structure_valid_fraction=math.nan,
        thin_edge_mask=np.zeros(shape, dtype=bool),
    )


def reliability_index(rows: Sequence[dict[str, str]]) -> dict[tuple[str, int], dict[str, str]]:
    return {
        (row["research_unit_id"], int(row["sar_frame_index"])): row
        for row in rows
        if row["research_unit_type"] == "vehicle_thread"
    }


def attach_unit_contract(unit: dict[str, Any], semantic_class: str, unit_type: str, role: str) -> dict[str, Any]:
    result = dict(unit)
    result["counterfactual_semantic_class"] = semantic_class
    result["unit_type"] = unit_type
    result["research_role"] = role
    result.setdefault("image_rows", result["rows"])
    result.setdefault("reference_rows", result["rows"])
    result.setdefault("reliability_source_frames", [int(row["sar_frame_index"]) for row in result["rows"]])
    result.setdefault("target_region_id", result["segment_id"])
    result.setdefault("background_spatial_control_group", "")
    result.setdefault("background_parameter_envelope_group", "")
    result.setdefault("background_control_semantic_role", "")
    result.setdefault("transform_rule_id", "TRUE_TRAJECTORY")
    result.setdefault("vehicle_present_in_target", semantic_class in {"TRUE_VEHICLE_POSITIVE", "IDENTITY_NEGATIVE_CLASS_POSITIVE"})
    result.setdefault("valid_for_identity_test", semantic_class == "IDENTITY_NEGATIVE_CLASS_POSITIVE")
    result.setdefault("valid_for_vehicle_class_test", semantic_class in {"TRUE_VEHICLE_POSITIVE", "VEHICLE_CLASS_NEGATIVE"})
    result.setdefault("valid_for_temporal_test", semantic_class in {"TRUE_VEHICLE_POSITIVE", "TEMPORAL_NEGATIVE"})
    result.setdefault("valid_for_temporal_correspondence_test", semantic_class in {"TRUE_VEHICLE_POSITIVE", "TEMPORAL_NEGATIVE"})
    result.setdefault("valid_for_temporal_direction_test", False)
    result["valid_for_temporal_test_scope"] = (
        "CORRESPONDENCE_ONLY"
        if semantic_class == "TEMPORAL_NEGATIVE"
        else "POSITIVE_REFERENCE_FOR_CORRESPONDENCE_ONLY"
        if semantic_class == "TRUE_VEHICLE_POSITIVE"
        else "NOT_APPLICABLE"
    )
    result.setdefault("freeze_source", DEVELOPMENT_SEGMENT)
    result.setdefault("replay_status", "DEVELOPMENT_FROZEN" if result["segment_id"] == DEVELOPMENT_SEGMENT else "FIXED_REPLAY")
    result.setdefault("optical_identity_source", "OPTICAL_COMPLETE_VEHICLE_THREAD_FUTURE_SOURCE_NOT_EXECUTED")
    result.setdefault("center_source", "GT_DISCOVERY_ONLY_FUTURE_OPTICAL_AZIMUTH_AND_TIME_STATE")
    result.setdefault("axis_source", "GT_DISCOVERY_ONLY_FUTURE_OPTICAL_POSE_OR_MOTION_AXIS")
    result.setdefault("scale_source", "GT_DISCOVERY_ONLY_FUTURE_VEHICLE_OR_OPTICAL_SIZE_RANGE")
    result.setdefault("gt_information_debt", "GT_DISCOVERY_ONLY;FUTURE_REPLACEABLE;DEPLOYMENT_SOURCE_NOT_READY")
    result.setdefault("optical_condition_execution_status", "NOT_EXECUTED_GT_DISCOVERY_PROXY_ONLY")
    result.setdefault("counterfactual_scope_limitation", "NONE")
    result.setdefault("vehicle_absence_evidence_scope", "NOT_APPLICABLE")
    result.setdefault("pair_membership_source_segment_id", result["source_trajectory_segment_id"])
    result.setdefault("pair_membership_contract", PAIR_PROJECTION_RULE)
    result.setdefault("notes", "")
    return result


def temporal_direction_applicability(unit: Mapping[str, Any]) -> str:
    if unit.get("transform_rule_id") == "IMAGE_ORDER_REVERSED":
        return "NOT_APPLICABLE_TO_TIME_REVERSAL"
    if unit.get("counterfactual_semantic_class") == "TEMPORAL_NEGATIVE":
        return "NOT_EVALUATED_DIRECTION_INSENSITIVE_METRICS"
    return "NOT_A_TEMPORAL_DIRECTION_TEST"


def temporal_correspondence_applicability(unit: Mapping[str, Any]) -> str:
    if unit.get("counterfactual_semantic_class") == "TEMPORAL_NEGATIVE":
        return "APPLICABLE_TO_TEMPORAL_CORRESPONDENCE_CONTROL"
    return "NOT_A_TEMPORAL_CORRESPONDENCE_TEST"


def pair_membership_reliability_scope(unit: Mapping[str, Any]) -> str:
    if unit.get("counterfactual_semantic_class") == "TRUE_VEHICLE_POSITIVE":
        return "DIRECT_SOURCE_REGISTRATION_RELIABILITY"
    return "SOURCE_POSITIVE_MEMBERSHIP_ONLY;COUNTERFACTUAL_TARGET_REGISTRATION_NOT_INDEPENDENTLY_VALIDATED"


def build_vehicle_units(local_fields: Sequence[dict[str, str]]) -> dict[str, dict[str, Any]]:
    by_segment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in local_fields:
        if row["segment_id"] in CORE_SEGMENTS:
            by_segment[row["segment_id"]].append(row)
    output: dict[str, dict[str, Any]] = {}
    for segment_id, role in CORE_SEGMENTS.items():
        unit = base.build_vehicle_unit(by_segment[segment_id], role)
        unit = attach_unit_contract(unit, "TRUE_VEHICLE_POSITIVE", "vehicle_thread", role)
        unit["research_unit_id"] = segment_id
        unit["transform_rule_id"] = "TRUE_VEHICLE_TRAJECTORY"
        output[segment_id] = unit
    return output


def build_swap_unit(source: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    source_index = {int(row["sar_frame_index"]): index for index, row in enumerate(source["rows"])}
    target_index = {int(row["sar_frame_index"]): index for index, row in enumerate(target["rows"])}
    frames = sorted(set(source_index) & set(target_index))
    middle_frame = frames[len(frames) // 2]
    source_middle = source["smooth_anchors"][source_index[middle_frame]]
    target_middle = target["smooth_anchors"][target_index[middle_frame]]
    rows: list[dict[str, str]] = []
    image_rows: list[dict[str, str]] = []
    reference_rows: list[dict[str, str]] = []
    raw_anchors: list[dict[str, float]] = []
    smooth_anchors: list[dict[str, float]] = []
    raw_axes: list[tuple[np.ndarray, np.ndarray]] = []
    smooth_axes: list[tuple[np.ndarray, np.ndarray]] = []
    raw_angles: list[float] = []
    smooth_angles: list[float] = []
    for frame in frames:
        source_position = source_index[frame]
        target_position = target_index[frame]
        source_row = source["rows"][source_position]
        target_row = target["rows"][target_position]
        rows.append(dict(target_row))
        image_rows.append(dict(target_row))
        reference_rows.append(dict(source_row))
        raw = dict(source["raw_anchors"][source_position])
        smooth = dict(source["smooth_anchors"][source_position])
        raw["cx"] = target_middle["cx"] + raw["cx"] - source_middle["cx"]
        raw["cy"] = target_middle["cy"] + raw["cy"] - source_middle["cy"]
        smooth["cx"] = target_middle["cx"] + smooth["cx"] - source_middle["cx"]
        smooth["cy"] = target_middle["cy"] + smooth["cy"] - source_middle["cy"]
        raw_anchors.append(raw)
        smooth_anchors.append(smooth)
        raw_axes.append(source["raw_axes"][source_position])
        smooth_axes.append(source["smooth_axes"][source_position])
        raw_angles.append(source["raw_angles"][source_position])
        smooth_angles.append(source["smooth_angles"][source_position])
    identifier = f"SWAP-{source['canonical_vehicle_id'].replace(':', '_')}-AROUND-{target['canonical_vehicle_id'].replace(':', '_')}"
    unit = {
        "research_unit_id": identifier,
        "research_unit_type": "trajectory_swap_counterfactual",
        "scene": target["scene"],
        "canonical_vehicle_id": source["canonical_vehicle_id"],
        "benchmark_role": "counterfactual",
        "segment_id": identifier,
        "source_trajectory_segment_id": source["segment_id"],
        "target_region_id": target["segment_id"],
        "rows": rows,
        "image_rows": image_rows,
        "reference_rows": reference_rows,
        "raw_anchors": raw_anchors,
        "smooth_anchors": smooth_anchors,
        "raw_axes": raw_axes,
        "smooth_axes": smooth_axes,
        "raw_angles": raw_angles,
        "smooth_angles": smooth_angles,
        "reliability_source_frames": frames,
        "reference_long": source["reference_long"],
        "reference_short": source["reference_short"],
    }
    unit = attach_unit_contract(unit, "IDENTITY_NEGATIVE_CLASS_POSITIVE", "trajectory_swap", "identity_specificity_falsification")
    unit["vehicle_present_in_target"] = True
    unit["valid_for_identity_test"] = True
    unit["valid_for_vehicle_class_test"] = False
    unit["valid_for_temporal_test"] = False
    unit["transform_rule_id"] = "SOURCE_TRAJECTORY_TRANSLATED_TO_OTHER_REAL_VEHICLE"
    unit["notes"] = "identity negative for source vehicle; class positive because target region contains another reviewed real vehicle"
    unit["counterfactual_scope_limitation"] = "PV002_PV003_SWAP_SCOPE_ONLY;NO_PV004_IDENTITY_SWAP"
    return unit


def build_background_unit(
    source: Mapping[str, Any],
    background_id: str,
    background_record: Mapping[str, Any],
) -> dict[str, Any]:
    dr = float(background_record["offset_radial_px"])
    dt = float(background_record["offset_tangential_px"])
    moving = bool(background_record["moving"])
    middle = len(source["rows"]) // 2
    fixed_raw = base.offset_anchor(source["raw_anchors"][middle], dr, dt)
    fixed_smooth = base.offset_anchor(source["smooth_anchors"][middle], dr, dt)
    raw_anchors: list[dict[str, float]] = []
    smooth_anchors: list[dict[str, float]] = []
    for raw, smooth in zip(source["raw_anchors"], source["smooth_anchors"]):
        if moving:
            raw_anchors.append(base.offset_anchor(raw, dr, dt))
            smooth_anchors.append(base.offset_anchor(smooth, dr, dt))
        else:
            raw_anchor = dict(raw)
            smooth_anchor = dict(smooth)
            raw_anchor["cx"], raw_anchor["cy"] = fixed_raw["cx"], fixed_raw["cy"]
            smooth_anchor["cx"], smooth_anchor["cy"] = fixed_smooth["cx"], fixed_smooth["cy"]
            raw_anchors.append(raw_anchor)
            smooth_anchors.append(smooth_anchor)
    identifier = f"CLASS-NEGATIVE-{background_id}"
    unit = {
        "research_unit_id": identifier,
        "research_unit_type": "vehicle_class_negative_background",
        "scene": source["scene"],
        "canonical_vehicle_id": source["canonical_vehicle_id"],
        "benchmark_role": "counterfactual",
        "segment_id": identifier,
        "source_trajectory_segment_id": source["segment_id"],
        "target_region_id": background_id,
        "rows": [dict(row) for row in source["rows"]],
        "image_rows": [dict(row) for row in source["rows"]],
        "reference_rows": [dict(row) for row in source["rows"]],
        "raw_anchors": raw_anchors,
        "smooth_anchors": smooth_anchors,
        "raw_axes": source["raw_axes"],
        "smooth_axes": source["smooth_axes"],
        "raw_angles": source["raw_angles"],
        "smooth_angles": source["smooth_angles"],
        "reliability_source_frames": [int(row["sar_frame_index"]) for row in source["rows"]],
        "reference_long": source["reference_long"],
        "reference_short": source["reference_short"],
    }
    unit = attach_unit_contract(unit, "VEHICLE_CLASS_NEGATIVE", "background_counterfactual", "vehicle_class_falsification")
    unit["vehicle_present_in_target"] = False
    unit["valid_for_identity_test"] = False
    unit["valid_for_vehicle_class_test"] = True
    unit["valid_for_temporal_test"] = False
    unit["background_spatial_control_group"] = str(background_record["spatial_control_group"])
    unit["background_parameter_envelope_group"] = str(background_record["parameter_envelope_group"])
    unit["background_control_semantic_role"] = str(background_record["control_semantic_role"])
    unit["transform_rule_id"] = "SOURCE_TRAJECTORY_SHIFTED_TO_BACKGROUND" if moving else "FIXED_WORLD_BACKGROUND"
    unit["background_type"] = str(background_record["background_type"])
    unit["background_quality_status"] = str(background_record["quality"])
    unit["background_reviewed_gt_overlap"] = float(background_record["reviewed_gt_overlap"])
    unit["counterfactual_scope_limitation"] = "BACKGROUND_POSITIONS_AND_SUPPORT_GEOMETRY_FROZEN_FROM_PV002_ONLY"
    unit["vehicle_absence_evidence_scope"] = "NO_REVIEWED_GT_OVERLAP_PLUS_DIRECT_REVIEW;NOT_ABSOLUTE_PHYSICAL_ABSENCE_PROOF"
    unit["notes"] = str(background_record["notes"])
    return unit


def exact_shift_pairs(rows: Sequence[dict[str, str]], shift: int) -> list[tuple[int, int]]:
    index = {int(row["sar_frame_index"]): position for position, row in enumerate(rows)}
    return [(position, index[int(row["sar_frame_index"]) + shift]) for position, row in enumerate(rows) if int(row["sar_frame_index"]) + shift in index]


def build_temporal_units(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    count = len(source["rows"])
    shuffled_indices = list(range(count))
    random.Random(SHUFFLE_SEED).shuffle(shuffled_indices)
    temporal_specs = [
        ("TEMPORAL_SHUFFLE", shuffled_indices, "IMAGE_ORDER_DETERMINISTIC_SHUFFLE"),
        ("TEMPORAL_REVERSE", list(reversed(range(count))), "IMAGE_ORDER_REVERSED"),
    ]
    for suffix, image_indices, rule in temporal_specs:
        identifier = f"{source['segment_id']}|{suffix}"
        unit = dict(source)
        unit["research_unit_id"] = identifier
        unit["segment_id"] = identifier
        unit["image_rows"] = [dict(source["rows"][index]) for index in image_indices]
        unit["reference_rows"] = [dict(row) for row in source["rows"]]
        unit = attach_unit_contract(unit, "TEMPORAL_NEGATIVE", "temporal_counterfactual", "temporal_relation_falsification")
        unit["transform_rule_id"] = rule
        unit["valid_for_identity_test"] = False
        unit["valid_for_vehicle_class_test"] = False
        unit["valid_for_temporal_test"] = True
        unit["counterfactual_scope_limitation"] = "WITHIN_THREAD_GM_RM017_TEMPORAL_CONTROL;NO_CROSS_SCENE_REPLAY"
        unit["notes"] = (
            "reverse-order image-to-original-anchor correspondence mismatch; correspondence robustness only, not an arrow-of-time experiment"
            if suffix == "TEMPORAL_REVERSE"
            else "deterministic image-order shuffle with anchors held at original time; correspondence control only"
        )
        units.append(unit)

    pairs = exact_shift_pairs(source["rows"], TIME_SHIFT_FRAMES)
    for suffix in ("TRAJECTORY_TIME_SHIFT_P8", "CENTER_PHASE_SHIFT_P8"):
        rows = [dict(source["rows"][left]) for left, _ in pairs]
        future_positions = [right for _, right in pairs]
        current_positions = [left for left, _ in pairs]
        raw_anchors: list[dict[str, float]] = []
        smooth_anchors: list[dict[str, float]] = []
        raw_axes: list[tuple[np.ndarray, np.ndarray]] = []
        smooth_axes: list[tuple[np.ndarray, np.ndarray]] = []
        raw_angles: list[float] = []
        smooth_angles: list[float] = []
        for current, future in zip(current_positions, future_positions):
            if suffix == "TRAJECTORY_TIME_SHIFT_P8":
                raw_anchor = dict(source["raw_anchors"][future])
                smooth_anchor = dict(source["smooth_anchors"][future])
                raw_axis = source["raw_axes"][future]
                smooth_axis = source["smooth_axes"][future]
                raw_angle = source["raw_angles"][future]
                smooth_angle = source["smooth_angles"][future]
            else:
                raw_anchor = dict(source["raw_anchors"][current])
                smooth_anchor = dict(source["smooth_anchors"][current])
                raw_anchor["cx"] = source["raw_anchors"][future]["cx"]
                raw_anchor["cy"] = source["raw_anchors"][future]["cy"]
                smooth_anchor["cx"] = source["smooth_anchors"][future]["cx"]
                smooth_anchor["cy"] = source["smooth_anchors"][future]["cy"]
                raw_axis = source["raw_axes"][current]
                smooth_axis = source["smooth_axes"][current]
                raw_angle = source["raw_angles"][current]
                smooth_angle = source["smooth_angles"][current]
            raw_anchors.append(raw_anchor)
            smooth_anchors.append(smooth_anchor)
            raw_axes.append(raw_axis)
            smooth_axes.append(smooth_axis)
            raw_angles.append(raw_angle)
            smooth_angles.append(smooth_angle)
        identifier = f"{source['segment_id']}|{suffix}"
        unit = {
            **source,
            "research_unit_id": identifier,
            "segment_id": identifier,
            "rows": rows,
            "image_rows": rows,
            "reference_rows": rows,
            "raw_anchors": raw_anchors,
            "smooth_anchors": smooth_anchors,
            "raw_axes": raw_axes,
            "smooth_axes": smooth_axes,
            "raw_angles": raw_angles,
            "smooth_angles": smooth_angles,
            "reliability_source_frames": [
                int(source["rows"][future if suffix == "TRAJECTORY_TIME_SHIFT_P8" else current]["sar_frame_index"])
                for current, future in zip(current_positions, future_positions)
            ],
        }
        unit = attach_unit_contract(unit, "TEMPORAL_NEGATIVE", "temporal_counterfactual", "temporal_relation_falsification")
        unit["transform_rule_id"] = suffix
        unit["valid_for_identity_test"] = False
        unit["valid_for_vehicle_class_test"] = False
        unit["valid_for_temporal_test"] = True
        unit["counterfactual_scope_limitation"] = "WITHIN_THREAD_GM_RM017_TEMPORAL_CONTROL;NO_CROSS_SCENE_REPLAY"
        unit["notes"] = f"exact +{TIME_SHIFT_FRAMES} SAR-frame mapping; no row-order-only pseudo shuffle"
        units.append(unit)
    return units


def axis_rule_sequence(unit: Mapping[str, Any], anchor_variant: str, rule: str) -> list[tuple[np.ndarray, np.ndarray]]:
    anchors = unit["raw_anchors"] if anchor_variant == "raw_gt" else unit["smooth_anchors"]
    gt_axes = unit["raw_axes"] if anchor_variant == "raw_gt" else unit["smooth_axes"]
    gt_angles = unit["raw_angles"] if anchor_variant == "raw_gt" else unit["smooth_angles"]
    count = len(anchors)
    if rule == "GT_DERIVED_UNSIGNED_BODY":
        return [(np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64)) for u, v in gt_axes]
    if rule == "THREAD_FIXED_MEDIAN_AXIS":
        fixed = axis_from_angle(axial_median(gt_angles))
        return [fixed for _ in anchors]
    if rule == "FRAME_SHUFFLED_AXIS":
        indices = list(range(count))
        random.Random(SHUFFLE_SEED).shuffle(indices)
        return [gt_axes[index] for index in indices]
    if rule == "TIME_SHIFTED_AXIS":
        return [gt_axes[(index + TIME_SHIFT_FRAMES) % count] for index in range(count)]
    if rule == "GT_AXIS_PLUS_90":
        return [rotate_axes(axes, 90.0) for axes in gt_axes]
    if rule == "GLOBAL_FIXED_AXIS":
        fixed = (np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0]))
        return [fixed for _ in anchors]
    if rule == "TRAJECTORY_TANGENT_AXIS":
        output: list[tuple[np.ndarray, np.ndarray]] = []
        centers = [np.asarray([anchor["cx"], anchor["cy"]], dtype=np.float64) for anchor in anchors]
        for index in range(count):
            left = centers[max(0, index - 1)]
            right = centers[min(count - 1, index + 1)]
            tangent = right - left
            norm = float(np.linalg.norm(tangent))
            if norm <= 1e-9:
                output.append((np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0])))
            else:
                u = tangent / norm
                if u[0] < 0.0:
                    u = -u
                output.append((u, np.asarray([-u[1], u[0]], dtype=np.float64)))
        return output
    raise ValueError(f"unsupported axis rule: {rule}")


def image_cache(unit: Mapping[str, Any]) -> dict[tuple[str, int], tuple[np.ndarray, np.ndarray]]:
    output: dict[tuple[str, int], tuple[np.ndarray, np.ndarray]] = {}
    for row in unit["image_rows"]:
        scene = row["scene"]
        frame = int(row["sar_frame_index"])
        key = (scene, frame)
        if key in output:
            continue
        path = base.image_path(scene, frame)
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(path)
        output[key] = (image, cv2.GaussianBlur(image, (0, 0), 1.0))
    return output


def normalization(
    blurred: np.ndarray,
    valid: np.ndarray,
    reference_row: Mapping[str, str],
    path: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    outer = valid & ~CENTRAL_CORE_MASK
    candidate_outer_pixel_count = int(outer.sum())
    values = blurred[valid].astype(np.float32)
    status = "PASS"
    if path == "FIXED_REFERENCE":
        background = base.parse_float(reference_row["local_background_median"])
        high = base.parse_float(reference_row["thread_raw_p99"])
        estimator = "FROZEN_GT_CONDITIONED_ROW_REFERENCE"
        background_count = 0
        background_count_definition = "SOURCE_REFERENCE_SAMPLE_COUNT_UNAVAILABLE_NOT_REESTIMATED_FROM_CURRENT_CANDIDATE"
        if not math.isfinite(background) or not math.isfinite(high):
            status = "FAIL_NONFINITE_FIXED_REFERENCE"
        elif high - background < 1.0:
            status = "FAIL_DYNAMIC_RANGE_COLLAPSE"
    elif path == "CANDIDATE_LOCAL_REESTIMATED":
        outer_values = blurred[outer].astype(np.float32)
        background_count = int(outer_values.size)
        background_count_definition = "CURRENT_CANDIDATE_OUTER_RING_SAMPLE_COUNT"
        if outer_values.size < 256 or values.size < 512:
            background = math.nan
            high = math.nan
            status = "FAIL_INSUFFICIENT_BACKGROUND_OR_VALID_PIXELS"
        else:
            background = float(np.median(outer_values))
            high = float(np.quantile(values, 0.99))
            if high - background < 1.0:
                status = "FAIL_DYNAMIC_RANGE_COLLAPSE"
        estimator = "OUTER_RING_MEDIAN_PLUS_VALID_P99_CORE_EXCLUDED_FROM_BACKGROUND"
    else:
        raise ValueError(path)
    if status == "PASS" and values.size < 512:
        status = "FAIL_INSUFFICIENT_VALID_PIXELS"
    if status == "PASS" and math.isfinite(background) and math.isfinite(high):
        score = np.clip((blurred.astype(np.float32) - background) / max(1.0, high - background), 0.0, 1.0)
    else:
        score = np.zeros_like(blurred, dtype=np.float32)
    score[~valid] = 0.0
    low_quantile = float(np.quantile(values, 0.01)) if values.size else math.nan
    high_quantile = float(np.quantile(values, 0.99)) if values.size else math.nan
    saturation_low = float(np.mean(values <= background)) if values.size and math.isfinite(background) else math.nan
    saturation_high = float(np.mean(values >= high)) if values.size and math.isfinite(high) else math.nan
    return score, {
        "normalization_path": path,
        "background_estimator_id": estimator,
        "core_exclusion_rule_id": "CENTRAL_NOMINAL_VEHICLE_RECTANGLE_EXCLUDED",
        "candidate_outer_pixel_count": candidate_outer_pixel_count,
        "background_sample_count": background_count,
        "background_sample_count_definition": background_count_definition,
        "background_median": background,
        "dynamic_range_low": low_quantile,
        "dynamic_range_high": high_quantile,
        "normalization_high_reference": high,
        "saturation_low_fraction": saturation_low,
        "saturation_high_fraction": saturation_high,
        "normalization_status": status,
    }


def pair_metric_values(evaluation: Evaluation, left: int, right: int) -> dict[str, float]:
    valid = evaluation.valids[left] & evaluation.valids[right]
    common_valid_fraction = float(valid.mean())
    if (
        evaluation.normalization_rows[left]["normalization_status"] != "PASS"
        or evaluation.normalization_rows[right]["normalization_status"] != "PASS"
    ):
        return {
            **{metric_name: math.nan for metric_name in METRIC_DIRECTIONS},
            "COMMON_VALID_FRACTION": common_valid_fraction,
        }
    score_left = evaluation.scores[left].astype(np.float32) / 255.0
    score_right = evaluation.scores[right].astype(np.float32) / 255.0
    field_ncc = base.ncc(score_left, score_right, valid)
    feature_left = evaluation.features[left]
    feature_right = evaluation.features[right]
    orientation_diff = axial_difference(feature_left.orientation_deg, feature_right.orientation_deg)
    orientation_agreement = math.cos(math.radians(orientation_diff * 2.0)) if math.isfinite(orientation_diff) else math.nan
    thin_edge_union = (feature_left.thin_edge_mask | feature_right.thin_edge_mask) & valid
    thin_edge_intersection = feature_left.thin_edge_mask & feature_right.thin_edge_mask & valid
    thin_edge_union_count = int(thin_edge_union.sum())
    thin_edge_jaccard = (
        float(thin_edge_intersection.sum()) / thin_edge_union_count
        if thin_edge_union_count
        else math.nan
    )
    relation_diff = (
        abs(feature_left.relation_distance_median - feature_right.relation_distance_median)
        if math.isfinite(feature_left.relation_distance_median) and math.isfinite(feature_right.relation_distance_median)
        else math.nan
    )
    centroid_distance = (
        math.hypot(
            feature_left.thin_edge_centroid_x - feature_right.thin_edge_centroid_x,
            feature_left.thin_edge_centroid_y - feature_right.thin_edge_centroid_y,
        )
        if all(
            math.isfinite(value)
            for value in (
                feature_left.thin_edge_centroid_x,
                feature_left.thin_edge_centroid_y,
                feature_right.thin_edge_centroid_x,
                feature_right.thin_edge_centroid_y,
            )
        )
        else math.nan
    )
    return {
        "FIELD_NCC": field_ncc,
        "ORIENTATION_PAIR_AGREEMENT": orientation_agreement,
        "ORIENTATION_ANGLE_DIFF_DEG": orientation_diff,
        "THIN_EDGE_JACCARD": thin_edge_jaccard,
        "THIN_EDGE_ENDPOINT_COUNT_ABSDIFF": (
            float(abs(feature_left.endpoint_count - feature_right.endpoint_count))
            if thin_edge_union_count
            else math.nan
        ),
        "THIN_EDGE_BRANCH_COUNT_ABSDIFF": (
            float(abs(feature_left.branch_count - feature_right.branch_count))
            if thin_edge_union_count
            else math.nan
        ),
        "THIN_EDGE_KEYPOINT_RELATION_DISTANCE_ABSDIFF": relation_diff,
        "THIN_EDGE_CENTROID_DISTANCE": centroid_distance,
        "THIN_EDGE_ADJACENCY_MEAN_DEGREE_ABSDIFF": (
            abs(feature_left.adjacency_mean_degree - feature_right.adjacency_mean_degree)
            if math.isfinite(feature_left.adjacency_mean_degree)
            and math.isfinite(feature_right.adjacency_mean_degree)
            else math.nan
        ),
        "THIN_EDGE_COLLINEARITY_PROXY_ABSDIFF": (
            abs(feature_left.collinearity - feature_right.collinearity)
            if math.isfinite(feature_left.collinearity)
            and math.isfinite(feature_right.collinearity)
            else math.nan
        ),
        "THIN_EDGE_PARALLEL_REPRESENTATION_X_AXIS_FRACTION_ABSDIFF": (
            abs(feature_left.parallel_x_axis_fraction - feature_right.parallel_x_axis_fraction)
            if math.isfinite(feature_left.parallel_x_axis_fraction)
            and math.isfinite(feature_right.parallel_x_axis_fraction)
            else math.nan
        ),
        "THIN_EDGE_PARALLEL_REPRESENTATION_Y_AXIS_FRACTION_ABSDIFF": (
            abs(feature_left.parallel_y_axis_fraction - feature_right.parallel_y_axis_fraction)
            if math.isfinite(feature_left.parallel_y_axis_fraction)
            and math.isfinite(feature_right.parallel_y_axis_fraction)
            else math.nan
        ),
        "COMMON_VALID_FRACTION": common_valid_fraction,
    }


def adjacent_summary(evaluation: Evaluation) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for left in range(len(evaluation.features) - 1):
        for key, value in pair_metric_values(evaluation, left, left + 1).items():
            if key != "COMMON_VALID_FRACTION" and math.isfinite(value):
                values[key].append(value)
    return {f"adjacent_{key.lower()}_median": finite_median(items) for key, items in values.items()}


def transform_definition(
    unit: Mapping[str, Any],
    anchor_variant: str,
    representation: str,
    body_axes_sequence: Sequence[tuple[np.ndarray, np.ndarray]],
    index: int,
    parameter_id: str | None,
    parameter_value: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    anchors = unit["raw_anchors"] if anchor_variant == "raw_gt" else unit["smooth_anchors"]
    anchor = anchors[index]
    centers = np.asarray([[item["cx"], item["cy"]] for item in anchors], dtype=np.float64)
    tracked_center = centers[index]
    fixed_center = np.median(centers, axis=0)
    half_x = float(unit["reference_long"]) * 0.5 * CONTEXT_FACTOR
    half_y = float(unit["reference_short"]) * 0.5 * CONTEXT_FACTOR
    global_axes = (np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0]))
    radial, tangential = base.radial_tangential(anchor)
    radial_axes = (tangential, radial)
    body_axes = body_axes_sequence[index]
    if representation == "WORLD_FIXED":
        center, axes = fixed_center.copy(), global_axes
    elif representation == "CENTER_TRACKED_CARTESIAN":
        center, axes = tracked_center.copy(), global_axes
    elif representation == "CENTER_TRACKED_RADIAL":
        center, axes = tracked_center.copy(), radial_axes
    elif representation == "CENTER_TRACKED_BODY":
        center, axes = tracked_center.copy(), body_axes
    else:
        raise ValueError(representation)
    if parameter_id == "CENTER_RADIAL":
        center = center + radial * parameter_value * float(unit["reference_short"])
    elif parameter_id == "CENTER_TANGENTIAL":
        center = center + tangential * parameter_value * float(unit["reference_short"])
    elif parameter_id == "LONG_SCALE":
        half_x *= parameter_value
    elif parameter_id == "SHORT_SCALE":
        half_y *= parameter_value
    elif parameter_id == "AXIS_UNSIGNED":
        axes = rotate_axes(axes, parameter_value)
    return center, np.asarray(axes[0], dtype=np.float64), np.asarray(axes[1], dtype=np.float64), half_x, half_y


def evaluate(
    unit: Mapping[str, Any],
    anchor_variant: str,
    representation: str,
    axis_rule: str,
    normalization_path: str,
    cache: Mapping[tuple[str, int], tuple[np.ndarray, np.ndarray]],
    parameter_id: str | None = None,
    parameter_value: float = 0.0,
    collect_sampling: bool = False,
) -> tuple[Evaluation, list[dict[str, Any]]]:
    scores: list[np.ndarray] = []
    valids: list[np.ndarray] = []
    features: list[FrameFeatures] = []
    normalization_rows: list[dict[str, Any]] = []
    sampling_rows: list[dict[str, Any]] = []
    body_axes_sequence = axis_rule_sequence(unit, anchor_variant, axis_rule)
    for index, (row, image_row, reference_row) in enumerate(zip(unit["rows"], unit["image_rows"], unit["reference_rows"])):
        key = (image_row["scene"], int(image_row["sar_frame_index"]))
        image, blurred = cache[key]
        center, u, v, half_x, half_y = transform_definition(
            unit, anchor_variant, representation, body_axes_sequence, index, parameter_id, parameter_value,
        )
        raw, valid = base.warp_axes(image, center, u, v, half_x, half_y)
        blur, _ = base.warp_axes(blurred, center, u, v, half_x, half_y)
        score, normalization_row = normalization(blur, valid, reference_row, normalization_path)
        score_u8 = np.round(score * 255.0).astype(np.uint8)
        scores.append(score_u8)
        valids.append(valid.astype(bool))
        frame_features = (
            extract_features(score, valid)
            if normalization_row["normalization_status"] == "PASS"
            else invalid_frame_features(valid.shape)
        )
        features.append(frame_features)
        normalization_rows.append(normalization_row)
        if collect_sampling:
            footprint = footprint_polygon(center, u, v, half_x, half_y)
            sampling_rows.append({
                "sampling_row_id": "",
                "research_unit_id": unit["research_unit_id"],
                "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
                "temporal_direction_applicability": temporal_direction_applicability(unit),
                "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
                "sar_frame_index": row["sar_frame_index"],
                "sar_time_sec": row["sar_time_sec"],
                "source_image_frame_index": image_row["sar_frame_index"],
                "anchor_variant": anchor_variant,
                "representation": representation,
                "axis_rule": axis_rule,
                "source_image_sha256": image_row["raw_image_sha256"],
                "center_x_px": fmt(center[0]),
                "center_y_px": fmt(center[1]),
                "axis_x_x": fmt(u[0]),
                "axis_x_y": fmt(u[1]),
                "axis_y_x": fmt(v[0]),
                "axis_y_y": fmt(v[1]),
                "window_half_x_source_px": fmt(half_x),
                "window_half_y_source_px": fmt(half_y),
                "source_footprint_polygon_global_px": polygon_text(footprint),
                "grid_width": GRID_WIDTH,
                "grid_height": GRID_HEIGHT,
                "source_px_per_grid_x": fmt(2.0 * half_x / max(1, GRID_WIDTH - 1)),
                "source_px_per_grid_y": fmt(2.0 * half_y / max(1, GRID_HEIGHT - 1)),
                "interpolation_rule": "CV2_INTER_LINEAR",
                "gray_input_lineage": "FROZEN_8BIT_GRAY_DISPLAY_DOMAIN",
                "mask_rule_id": "FROZEN_FAN_AND_CANVAS_IMAGING_VALID",
                "structure_boundary_guard_id": "TELEA_INPAINT_INVALID_PLUS_ERODE_VALID_6PX",
                "structure_valid_fraction": fmt(frame_features.structure_valid_fraction),
                "valid_pixel_count": int(valid.sum()),
                "valid_fraction": fmt(valid.mean()),
                "nominal_outer_context_fraction": fmt(1.0 - (1.0 / CONTEXT_FACTOR) ** 2),
                "support_geometry_id": f"{unit['research_unit_id']}|{anchor_variant}|EQUAL_SUPPORT_V1",
                "equal_support_parity_status": "PASS_BY_CONSTRUCTION",
                "parity_fail_reasons": "",
                "review_status": "pending_direct_review",
                **{key: fmt(value) if isinstance(value, (float, np.floating)) else value for key, value in normalization_row.items()},
            })
    evaluation = Evaluation(
        scores=np.stack(scores, axis=0),
        valids=np.stack(valids, axis=0),
        features=features,
        normalization_rows=normalization_rows,
        adjacent_metrics={},
    )
    evaluation.adjacent_metrics = adjacent_summary(evaluation)
    return evaluation, sampling_rows


def pair_candidates(
    unit: Mapping[str, Any],
    anchor_variant: str,
    reliability_rows: Mapping[tuple[str, int], Mapping[str, str]],
    membership_reference: Evaluation,
) -> tuple[list[dict[str, Any]], str]:
    anchors = unit["raw_anchors"] if anchor_variant == "raw_gt" else unit["smooth_anchors"]
    axes = unit["raw_axes"] if anchor_variant == "raw_gt" else unit["smooth_axes"]
    views = [base.radar_in_body(anchor, axis[0], axis[1])[2] for anchor, axis in zip(anchors, axes)]
    frames = [int(row["sar_frame_index"]) for row in unit["rows"]]
    times = [float(row["sar_time_sec"]) for row in unit["rows"]]
    source_segment = unit["source_trajectory_segment_id"]
    candidates: list[dict[str, Any]] = []
    for left in range(len(frames)):
        for right in range(left + 1, len(frames)):
            frame_gap = frames[right] - frames[left]
            if frame_gap < PAIR_MIN_FRAME_GAP:
                continue
            view_diff = axial_difference(views[left], views[right])
            if view_diff > PAIR_MAX_VIEW_DIFF_DEG:
                continue
            left_source_frame = int(unit["reliability_source_frames"][left])
            right_source_frame = int(unit["reliability_source_frames"][right])
            left_reliability = reliability_rows.get((source_segment, left_source_frame), {})
            right_reliability = reliability_rows.get((source_segment, right_source_frame), {})
            registration_field = "raw_body_registration_status" if anchor_variant == "raw_gt" else "smoothed_body_registration_status"
            left_axis = left_reliability.get("axis_reliability", "UNAVAILABLE")
            right_axis = right_reliability.get("axis_reliability", "UNAVAILABLE")
            left_registration = left_reliability.get(registration_field, "UNAVAILABLE")
            right_registration = right_reliability.get(registration_field, "UNAVAILABLE")
            reliability_reasons: list[str] = []
            if left_axis != "AXIS_RELIABLE" or right_axis != "AXIS_RELIABLE":
                reliability_reasons.append("AXIS_RELIABILITY_FAILED")
            if left_registration != "REGISTRATION_RELIABLE" or right_registration != "REGISTRATION_RELIABLE":
                reliability_reasons.append("REGISTRATION_RELIABILITY_FAILED")
            baseline_valid = membership_reference.valids[left] & membership_reference.valids[right]
            baseline_common_valid_pixel_count = int(baseline_valid.sum())
            baseline_values = pair_metric_values(membership_reference, left, right)
            baseline_common_valid_fraction = baseline_values["COMMON_VALID_FRACTION"]
            baseline_field_ncc = baseline_values["FIELD_NCC"]
            common_valid_reasons: list[str] = []
            if baseline_common_valid_pixel_count < 20:
                common_valid_reasons.append("COMMON_VALID_PIXEL_COUNT_LT20")
            if not math.isfinite(baseline_field_ncc):
                common_valid_reasons.append("BASELINE_FIELD_NCC_NONFINITE")
            reasons = reliability_reasons + common_valid_reasons
            if common_valid_reasons:
                eligibility = "EXCLUDED_COMMON_VALID"
            elif reliability_reasons:
                eligibility = "EXCLUDED_RELIABILITY"
            else:
                eligibility = "ELIGIBLE"
            pair_id = f"{unit['research_unit_id']}|{anchor_variant}|{frames[left]}|{frames[right]}"
            candidates.append({
                "pair_id": pair_id,
                "left_index": left,
                "right_index": right,
                "left_frame": frames[left],
                "right_frame": frames[right],
                "left_time_sec": times[left],
                "right_time_sec": times[right],
                "frame_gap": frame_gap,
                "time_gap_sec": times[right] - times[left],
                "left_view_angle_deg": views[left],
                "right_view_angle_deg": views[right],
                "view_angle_diff_deg": view_diff,
                "left_axis_reliability": left_axis,
                "right_axis_reliability": right_axis,
                "left_registration_reliability": left_registration,
                "right_registration_reliability": right_registration,
                "baseline_common_valid_pixel_count": baseline_common_valid_pixel_count,
                "baseline_common_valid_fraction": baseline_common_valid_fraction,
                "baseline_field_ncc": baseline_field_ncc,
                "baseline_field_ncc_finite": bool_text(math.isfinite(baseline_field_ncc)),
                "pair_eligibility": eligibility,
                "pair_exclusion_reasons": ";".join(reasons),
            })
    pair_payload = [
        (
            row["left_frame"],
            row["right_frame"],
            row["baseline_common_valid_pixel_count"],
            row["baseline_field_ncc_finite"],
            row["pair_eligibility"],
            row["pair_exclusion_reasons"],
        )
        for row in candidates
    ]
    pair_hash = hashlib.sha256(json.dumps(pair_payload, sort_keys=True).encode("utf-8")).hexdigest()
    return candidates, pair_hash


def project_source_pair_candidates(
    unit: Mapping[str, Any],
    anchor_variant: str,
    source_pairs: Sequence[Mapping[str, Any]],
    source_pair_set_hash: str,
) -> tuple[list[dict[str, Any]], str]:
    frame_to_index = {
        int(row["sar_frame_index"]): index for index, row in enumerate(unit["rows"])
    }
    projected: list[dict[str, Any]] = []
    is_true_source = unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
    for source_pair in source_pairs:
        left_frame = int(source_pair["left_frame"])
        right_frame = int(source_pair["right_frame"])
        if left_frame not in frame_to_index or right_frame not in frame_to_index:
            continue
        left_index = frame_to_index[left_frame]
        right_index = frame_to_index[right_frame]
        row = dict(source_pair)
        row.update({
            "source_pair_id": source_pair["pair_id"],
            "source_pair_set_hash": source_pair_set_hash,
            "pair_id": f"{unit['research_unit_id']}|{anchor_variant}|{left_frame}|{right_frame}",
            "left_index": left_index,
            "right_index": right_index,
            "left_time_sec": float(unit["rows"][left_index]["sar_time_sec"]),
            "right_time_sec": float(unit["rows"][right_index]["sar_time_sec"]),
            "time_gap_sec": float(unit["rows"][right_index]["sar_time_sec"])
            - float(unit["rows"][left_index]["sar_time_sec"]),
            "pair_projection_rule": PAIR_PROJECTION_RULE,
            "pair_membership_reliability_scope": (
                "DIRECT_SOURCE_REGISTRATION_RELIABILITY"
                if is_true_source
                else "SOURCE_POSITIVE_MEMBERSHIP_ONLY;COUNTERFACTUAL_TARGET_REGISTRATION_NOT_INDEPENDENTLY_VALIDATED"
            ),
        })
        projected.append(row)
    projection_payload = [
        (
            row["source_pair_id"],
            row["pair_eligibility"],
            row["pair_exclusion_reasons"],
        )
        for row in projected
    ]
    projected_hash = hashlib.sha256(
        json.dumps(
            {
                "source_pair_set_hash": source_pair_set_hash,
                "projected_pairs": projection_payload,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return projected, projected_hash


def pair_summary(evaluation: Evaluation, pairs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values: dict[str, list[float]] = defaultdict(list)
    eligible_count = 0
    eligible_pairs: list[Mapping[str, Any]] = []
    for pair in pairs:
        if pair["pair_eligibility"] != "ELIGIBLE":
            continue
        eligible_count += 1
        eligible_pairs.append(pair)
        pair_values = pair_metric_values(evaluation, int(pair["left_index"]), int(pair["right_index"]))
        for key, value in pair_values.items():
            if math.isfinite(value):
                values[key].append(value)
    unique_frames, max_frame_degree, graph_components = pair_graph_diagnostics(eligible_pairs)
    output: dict[str, Any] = {
        "candidate_pair_count": len(pairs),
        "eligible_pair_count": eligible_count,
        "eligible_unique_frame_count": unique_frames,
        "eligible_max_frame_pair_degree": max_frame_degree,
        "eligible_pair_graph_component_count": graph_components,
        "pair_evidence_state": (
            "NO_ELIGIBLE_PAIRS"
            if eligible_count == 0
            else "SPARSE_PAIR_EVIDENCE"
            if eligible_count <= 4
            else "PAIR_COUNT_GT4_SHARED_FRAME_REPEATED_EVIDENCE"
        ),
    }
    for key in METRIC_DIRECTIONS:
        output[f"nonadjacent_{key.lower()}_median"] = finite_median(values.get(key, []))
    output["nonadjacent_common_valid_fraction_median"] = finite_median(values.get("COMMON_VALID_FRACTION", []))
    return output


def representation_summary_row(
    unit: Mapping[str, Any],
    anchor_variant: str,
    representation: str,
    normalization_path: str,
    source_pair_set_hash: str,
    pair_hash: str,
    pairs: Sequence[Mapping[str, Any]],
    evaluation: Evaluation,
) -> dict[str, Any]:
    feature_rows = evaluation.features
    summary = pair_summary(evaluation, pairs)
    statuses = Counter(row["normalization_status"] for row in evaluation.normalization_rows)
    orientation_values = [
        feature.orientation_deg
        for feature in feature_rows
        if math.isfinite(feature.orientation_deg)
    ]
    orientation_to_x = [axial_difference(value, 0.0) for value in orientation_values]
    orientation_to_y = [axial_difference(value, 90.0) for value in orientation_values]
    normalization_all_pass = all(
        row["normalization_status"] == "PASS"
        for row in evaluation.normalization_rows
    )
    row = {
        "research_unit_id": unit["research_unit_id"],
        "unit_type": unit["unit_type"],
        "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
        "temporal_direction_applicability": temporal_direction_applicability(unit),
        "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
        "scene": unit["scene"],
        "canonical_vehicle_id": unit["canonical_vehicle_id"],
        "research_role": unit["research_role"],
        "anchor_variant": anchor_variant,
        "representation": representation,
        "axis_rule": "GT_DERIVED_UNSIGNED_BODY" if representation == "CENTER_TRACKED_BODY" else "REPRESENTATION_DEFINED_AXIS",
        "normalization_path": normalization_path,
        "pair_rule_id": PAIR_RULE_ID,
        "source_pair_set_hash": source_pair_set_hash,
        "pair_set_hash": pair_hash,
        "frame_count": len(unit["rows"]),
        **summary,
        **evaluation.adjacent_metrics,
        "orientation_dominant_axial_direction_deg": axial_median(orientation_values),
        "orientation_anisotropy_median": finite_median(feature.anisotropy for feature in feature_rows),
        "orientation_coherence_median": finite_median(feature.orientation_coherence for feature in feature_rows),
        "orientation_temporal_axial_dispersion_deg": base.axial_dispersion([feature.orientation_deg for feature in feature_rows if math.isfinite(feature.orientation_deg)]),
        "orientation_to_representation_x_axis_diff_median_deg": finite_median(orientation_to_x),
        "orientation_to_representation_y_axis_diff_median_deg": finite_median(orientation_to_y),
        "orientation_to_body_long_axis_diff_median_deg": finite_median(orientation_to_x) if representation == "CENTER_TRACKED_BODY" else "",
        "orientation_to_body_short_axis_diff_median_deg": finite_median(orientation_to_y) if representation == "CENTER_TRACKED_BODY" else "",
        "orientation_axis_relation_definition": "BODY_LONG_SHORT_AXES" if representation == "CENTER_TRACKED_BODY" else "REPRESENTATION_X_Y_AXES_ONLY",
        "topology_component_count_median": finite_median(feature.component_count for feature in feature_rows),
        "topology_endpoint_count_median": finite_median(feature.endpoint_count for feature in feature_rows),
        "topology_endpoint_count_cv": finite_cv(feature.endpoint_count for feature in feature_rows),
        "topology_branch_count_median": finite_median(feature.branch_count for feature in feature_rows),
        "topology_branch_count_cv": finite_cv(feature.branch_count for feature in feature_rows),
        "topology_thin_edge_fraction_median": finite_median(feature.thin_edge_fraction for feature in feature_rows),
        "topology_thin_edge_fraction_cv": finite_cv(feature.thin_edge_fraction for feature in feature_rows),
        "topology_thin_edge_largest_component_fraction_median": finite_median(feature.largest_component_fraction for feature in feature_rows),
        "topology_thin_edge_relative_centroid_x_median": finite_median(feature.thin_edge_centroid_x for feature in feature_rows),
        "topology_thin_edge_relative_centroid_y_median": finite_median(feature.thin_edge_centroid_y for feature in feature_rows),
        "topology_thin_edge_adjacency_mean_degree_median": finite_median(feature.adjacency_mean_degree for feature in feature_rows),
        "topology_thin_edge_collinearity_proxy_median": finite_median(feature.collinearity for feature in feature_rows),
        "topology_thin_edge_parallel_representation_x_fraction_median": finite_median(feature.parallel_x_axis_fraction for feature in feature_rows),
        "topology_thin_edge_parallel_representation_y_fraction_median": finite_median(feature.parallel_y_axis_fraction for feature in feature_rows),
        "topology_thin_edge_parallel_body_long_axis_fraction_median": finite_median(feature.parallel_x_axis_fraction for feature in feature_rows) if representation == "CENTER_TRACKED_BODY" else "",
        "topology_thin_edge_parallel_body_short_axis_fraction_median": finite_median(feature.parallel_y_axis_fraction for feature in feature_rows) if representation == "CENTER_TRACKED_BODY" else "",
        "topology_axis_relation_definition": "BODY_LONG_SHORT_AXES" if representation == "CENTER_TRACKED_BODY" else "REPRESENTATION_X_Y_AXES_ONLY",
        "topology_estimator_id": "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
        "structure_boundary_guard_id": "TELEA_INPAINT_INVALID_PLUS_ERODE_VALID_6PX",
        "structure_valid_fraction_median": finite_median(feature.structure_valid_fraction for feature in feature_rows),
        "structure_valid_fraction_min": min(
            (feature.structure_valid_fraction for feature in feature_rows if math.isfinite(feature.structure_valid_fraction)),
            default=math.nan,
        ),
        "valid_fraction_mean": fmt(float(evaluation.valids.mean())),
        "valid_fraction_min": fmt(min(float(valid.mean()) for valid in evaluation.valids)),
        "normalization_status_counts": ";".join(f"{key}:{statuses[key]}" for key in sorted(statuses)),
        "background_median_median": fmt(finite_median(row["background_median"] for row in evaluation.normalization_rows)),
        "dynamic_range_high_median": fmt(finite_median(row["dynamic_range_high"] for row in evaluation.normalization_rows)),
        "saturation_high_fraction_median": fmt(finite_median(row["saturation_high_fraction"] for row in evaluation.normalization_rows)),
        "evidence_validity_status": "PASS" if normalization_all_pass else "NORMALIZATION_FAILURE_PRESENT",
        "representation_attribution_scope": (
            "AXIS_ORIENTATION_PLUS_ROTATED_ANISOTROPIC_SUPPORT_FOOTPRINT"
            if representation in {"CENTER_TRACKED_RADIAL", "CENTER_TRACKED_BODY"}
            else "TRACKED_OR_FIXED_CENTER_WITH_GLOBAL_AXES_AND_EQUAL_WINDOW_DIMENSIONS"
        ),
        "support_geometry": "EQUAL_WINDOW_DIMENSIONS_GRID_DENSITY_MASK_GRAY;ROTATED_ANISOTROPIC_WINDOWS_SAMPLE_DIFFERENT_SOURCE_PIXELS",
        "review_status": "pending_direct_review",
        "notes": "metrics remain separate; no combined score or parameter selection; rotated-window deltas are not pure coordinate-axis attribution",
    }
    return {key: fmt(value) if isinstance(value, (float, np.floating)) else value for key, value in row.items()}


COMPARISONS = {
    "TRANSLATION_COMPENSATION": ("WORLD_FIXED", "CENTER_TRACKED_CARTESIAN"),
    "RADIAL_AXIS_INCREMENT": ("CENTER_TRACKED_CARTESIAN", "CENTER_TRACKED_RADIAL"),
    "GT_BODY_ORIENTED_WINDOW_VS_CARTESIAN": ("CENTER_TRACKED_CARTESIAN", "CENTER_TRACKED_BODY"),
    "GT_BODY_ORIENTED_WINDOW_VS_RADIAL": ("CENTER_TRACKED_RADIAL", "CENTER_TRACKED_BODY"),
}


def comparison_attribution_scope(comparison_id: str) -> str:
    if comparison_id == "TRANSLATION_COMPENSATION":
        return "TRACKED_CENTER_CHANGE_WITH_EQUAL_WINDOW_DIMENSIONS"
    return "AXIS_ORIENTATION_PLUS_ROTATED_ANISOTROPIC_SUPPORT_FOOTPRINT"


def directional_delta(baseline: float, test: float, direction: str) -> float:
    if not math.isfinite(baseline) or not math.isfinite(test):
        return math.nan
    return test - baseline if direction == "HIGHER_IS_BETTER" else baseline - test


def metric_evidence_contract(submetric: str) -> tuple[str, str]:
    if submetric == "FIELD_NCC":
        return "CONTINUOUS_GRAYSCALE_FIELD", "NORMALIZED_8BIT_FIELD_NCC"
    if submetric.startswith("ORIENTATION"):
        return "LOCAL_ORIENTATION_ORGANIZATION", "STRUCTURE_TENSOR_ORIENTATION_PROXY"
    return (
        "SPATIAL_RELATION_TOPOLOGY",
        "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON",
    )


def pair_comparison_rows(
    unit: Mapping[str, Any],
    anchor_variant: str,
    normalization_path: str,
    source_pair_set_hash: str,
    pair_hash: str,
    pairs: Sequence[Mapping[str, Any]],
    evaluations: Mapping[str, Evaluation],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not pairs:
        for comparison_id, (baseline_name, test_name) in COMPARISONS.items():
            for submetric, direction in METRIC_DIRECTIONS.items():
                family, estimator = metric_evidence_contract(submetric)
                rows.append({
                    "pair_id": "", "pair_rule_id": PAIR_RULE_ID,
                    "source_pair_id": "", "source_pair_set_hash": source_pair_set_hash,
                    "pair_projection_rule": PAIR_PROJECTION_RULE,
                    "pair_membership_reliability_scope": pair_membership_reliability_scope(unit),
                    "pair_set_hash": pair_hash, "research_unit_id": unit["research_unit_id"],
                    "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
                    "temporal_direction_applicability": temporal_direction_applicability(unit),
                    "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
                    "left_frame": "", "right_frame": "", "left_time_sec": "", "right_time_sec": "",
                    "frame_gap": "", "time_gap_sec": "", "left_view_angle_deg": "", "right_view_angle_deg": "",
                    "view_angle_diff_deg": "", "anchor_variant": anchor_variant,
                    "left_axis_reliability": "", "right_axis_reliability": "",
                    "left_registration_reliability": "", "right_registration_reliability": "",
                    "baseline_common_valid_pixel_count": "", "baseline_common_valid_fraction": "",
                    "baseline_field_ncc": "", "baseline_field_ncc_finite": "",
                    "pair_eligibility": "NO_CANDIDATE_PAIRS", "pair_exclusion_reasons": "NO_NONADJACENT_SIMILAR_VIEW_PAIRS",
                    "common_valid_fraction": "", "normalization_path": normalization_path,
                    "evidence_family": family, "evidence_estimator_id": estimator,
                    "submetric_name": submetric, "metric_direction": direction,
                    "comparison_id": comparison_id, "baseline_transform": baseline_name, "test_transform": test_name,
                    "comparison_attribution_scope": comparison_attribution_scope(comparison_id),
                    "baseline_value": "", "test_value": "", "raw_delta": "", "directional_delta": "",
                    "review_status": "pending_direct_review",
                })
        return rows
    for comparison_id, (baseline_name, test_name) in COMPARISONS.items():
        baseline = evaluations[baseline_name]
        test = evaluations[test_name]
        for pair in pairs:
            left = int(pair["left_index"])
            right = int(pair["right_index"])
            baseline_values = pair_metric_values(baseline, left, right)
            test_values = pair_metric_values(test, left, right)
            for submetric, direction in METRIC_DIRECTIONS.items():
                baseline_value = baseline_values[submetric]
                test_value = test_values[submetric]
                family, estimator = metric_evidence_contract(submetric)
                rows.append({
                    "pair_id": pair["pair_id"],
                    "pair_rule_id": PAIR_RULE_ID,
                    "source_pair_id": pair["source_pair_id"],
                    "source_pair_set_hash": source_pair_set_hash,
                    "pair_projection_rule": pair["pair_projection_rule"],
                    "pair_membership_reliability_scope": pair["pair_membership_reliability_scope"],
                    "pair_set_hash": pair_hash,
                    "research_unit_id": unit["research_unit_id"],
                    "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
                    "temporal_direction_applicability": temporal_direction_applicability(unit),
                    "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
                    "left_frame": pair["left_frame"],
                    "right_frame": pair["right_frame"],
                    "left_time_sec": fmt(pair["left_time_sec"], 9),
                    "right_time_sec": fmt(pair["right_time_sec"], 9),
                    "frame_gap": pair["frame_gap"],
                    "time_gap_sec": fmt(pair["time_gap_sec"], 9),
                    "left_view_angle_deg": fmt(pair["left_view_angle_deg"]),
                    "right_view_angle_deg": fmt(pair["right_view_angle_deg"]),
                    "view_angle_diff_deg": fmt(pair["view_angle_diff_deg"]),
                    "anchor_variant": anchor_variant,
                    "left_axis_reliability": pair["left_axis_reliability"],
                    "right_axis_reliability": pair["right_axis_reliability"],
                    "left_registration_reliability": pair["left_registration_reliability"],
                    "right_registration_reliability": pair["right_registration_reliability"],
                    "baseline_common_valid_pixel_count": pair["baseline_common_valid_pixel_count"],
                    "baseline_common_valid_fraction": fmt(pair["baseline_common_valid_fraction"]),
                    "baseline_field_ncc": fmt(pair["baseline_field_ncc"]),
                    "baseline_field_ncc_finite": pair["baseline_field_ncc_finite"],
                    "pair_eligibility": pair["pair_eligibility"],
                    "pair_exclusion_reasons": pair["pair_exclusion_reasons"],
                    "common_valid_fraction": fmt(min(baseline_values["COMMON_VALID_FRACTION"], test_values["COMMON_VALID_FRACTION"])),
                    "normalization_path": normalization_path,
                    "evidence_family": family,
                    "evidence_estimator_id": estimator,
                    "submetric_name": submetric,
                    "metric_direction": direction,
                    "comparison_id": comparison_id,
                    "baseline_transform": baseline_name,
                    "test_transform": test_name,
                    "comparison_attribution_scope": comparison_attribution_scope(comparison_id),
                    "baseline_value": fmt(baseline_value),
                    "test_value": fmt(test_value),
                    "raw_delta": fmt(test_value - baseline_value if math.isfinite(test_value) and math.isfinite(baseline_value) else math.nan),
                    "directional_delta": fmt(directional_delta(baseline_value, test_value, direction)),
                    "review_status": "pending_direct_review",
                })
    return rows


def axis_placebo_rows(
    unit: Mapping[str, Any],
    anchor_variant: str,
    normalization_path: str,
    source_pair_set_hash: str,
    pair_hash: str,
    pairs: Sequence[Mapping[str, Any]],
    evaluations: Mapping[str, Evaluation],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not pairs:
        for placebo in AXIS_RULES:
            if placebo == "GT_DERIVED_UNSIGNED_BODY":
                continue
            for submetric, direction in METRIC_DIRECTIONS.items():
                family, estimator = metric_evidence_contract(submetric)
                rows.append({
                    "pair_id": "", "pair_rule_id": PAIR_RULE_ID,
                    "source_pair_id": "", "source_pair_set_hash": source_pair_set_hash,
                    "pair_projection_rule": PAIR_PROJECTION_RULE,
                    "pair_membership_reliability_scope": pair_membership_reliability_scope(unit),
                    "pair_set_hash": pair_hash, "research_unit_id": unit["research_unit_id"],
                    "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
                    "temporal_direction_applicability": temporal_direction_applicability(unit),
                    "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
                    "left_frame": "", "right_frame": "", "left_time_sec": "", "right_time_sec": "",
                    "frame_gap": "", "time_gap_sec": "", "left_view_angle_deg": "", "right_view_angle_deg": "",
                    "view_angle_diff_deg": "", "anchor_variant": anchor_variant,
                    "left_axis_reliability": "", "right_axis_reliability": "",
                    "left_registration_reliability": "", "right_registration_reliability": "",
                    "baseline_common_valid_pixel_count": "", "baseline_common_valid_fraction": "",
                    "baseline_field_ncc": "", "baseline_field_ncc_finite": "",
                    "pair_eligibility": "NO_CANDIDATE_PAIRS", "pair_exclusion_reasons": "NO_NONADJACENT_SIMILAR_VIEW_PAIRS",
                    "common_valid_fraction": "", "normalization_path": normalization_path,
                    "evidence_family": family, "evidence_estimator_id": estimator,
                    "submetric_name": submetric, "metric_direction": direction,
                    "comparison_id": f"GT_ORIENTED_WINDOW_RULE_VS_{placebo}", "baseline_transform": placebo,
                    "test_transform": "GT_DERIVED_UNSIGNED_BODY", "baseline_value": "", "test_value": "",
                    "comparison_attribution_scope": "GT_DERIVED_ORIENTATION_RULE_VS_PLACEBO_WITH_SAME_ANISOTROPIC_WINDOW_DIMENSIONS;SOURCE_PIXELS_CHANGE_WITH_ROTATION",
                    "raw_delta": "", "directional_delta": "", "review_status": "pending_direct_review",
                })
        return rows
    gt = evaluations["GT_DERIVED_UNSIGNED_BODY"]
    for placebo in AXIS_RULES:
        if placebo == "GT_DERIVED_UNSIGNED_BODY":
            continue
        baseline = evaluations[placebo]
        for pair in pairs:
            left = int(pair["left_index"])
            right = int(pair["right_index"])
            baseline_values = pair_metric_values(baseline, left, right)
            test_values = pair_metric_values(gt, left, right)
            for submetric, direction in METRIC_DIRECTIONS.items():
                baseline_value = baseline_values[submetric]
                test_value = test_values[submetric]
                family, estimator = metric_evidence_contract(submetric)
                rows.append({
                    "pair_id": pair["pair_id"],
                    "pair_rule_id": PAIR_RULE_ID,
                    "source_pair_id": pair["source_pair_id"],
                    "source_pair_set_hash": source_pair_set_hash,
                    "pair_projection_rule": pair["pair_projection_rule"],
                    "pair_membership_reliability_scope": pair["pair_membership_reliability_scope"],
                    "pair_set_hash": pair_hash,
                    "research_unit_id": unit["research_unit_id"],
                    "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
                    "temporal_direction_applicability": temporal_direction_applicability(unit),
                    "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
                    "left_frame": pair["left_frame"],
                    "right_frame": pair["right_frame"],
                    "left_time_sec": fmt(pair["left_time_sec"], 9),
                    "right_time_sec": fmt(pair["right_time_sec"], 9),
                    "frame_gap": pair["frame_gap"],
                    "time_gap_sec": fmt(pair["time_gap_sec"], 9),
                    "left_view_angle_deg": fmt(pair["left_view_angle_deg"]),
                    "right_view_angle_deg": fmt(pair["right_view_angle_deg"]),
                    "view_angle_diff_deg": fmt(pair["view_angle_diff_deg"]),
                    "anchor_variant": anchor_variant,
                    "left_axis_reliability": pair["left_axis_reliability"],
                    "right_axis_reliability": pair["right_axis_reliability"],
                    "left_registration_reliability": pair["left_registration_reliability"],
                    "right_registration_reliability": pair["right_registration_reliability"],
                    "baseline_common_valid_pixel_count": pair["baseline_common_valid_pixel_count"],
                    "baseline_common_valid_fraction": fmt(pair["baseline_common_valid_fraction"]),
                    "baseline_field_ncc": fmt(pair["baseline_field_ncc"]),
                    "baseline_field_ncc_finite": pair["baseline_field_ncc_finite"],
                    "pair_eligibility": pair["pair_eligibility"],
                    "pair_exclusion_reasons": pair["pair_exclusion_reasons"],
                    "common_valid_fraction": fmt(min(baseline_values["COMMON_VALID_FRACTION"], test_values["COMMON_VALID_FRACTION"])),
                    "normalization_path": normalization_path,
                    "evidence_family": family,
                    "evidence_estimator_id": estimator,
                    "submetric_name": submetric,
                    "metric_direction": direction,
                    "comparison_id": f"GT_ORIENTED_WINDOW_RULE_VS_{placebo}",
                    "baseline_transform": placebo,
                    "test_transform": "GT_DERIVED_UNSIGNED_BODY",
                    "comparison_attribution_scope": "GT_DERIVED_ORIENTATION_RULE_VS_PLACEBO_WITH_SAME_ANISOTROPIC_WINDOW_DIMENSIONS;SOURCE_PIXELS_CHANGE_WITH_ROTATION",
                    "baseline_value": fmt(baseline_value),
                    "test_value": fmt(test_value),
                    "raw_delta": fmt(test_value - baseline_value if math.isfinite(test_value) and math.isfinite(baseline_value) else math.nan),
                    "directional_delta": fmt(directional_delta(baseline_value, test_value, direction)),
                    "review_status": "pending_direct_review",
                })
    return rows


def leave_one_out_medians(values: Sequence[float]) -> list[float]:
    if len(values) <= 1:
        return [math.nan for _ in values]
    ordered = sorted(values)
    remaining_count = len(values) - 1

    def remaining_value(removed_rank: int, remaining_rank: int) -> float:
        source_rank = remaining_rank if removed_rank > remaining_rank else remaining_rank + 1
        return ordered[source_rank]

    output: list[float] = []
    for value in values:
        removed_rank = bisect.bisect_left(ordered, value)
        middle = remaining_count // 2
        if remaining_count % 2:
            output.append(float(remaining_value(removed_rank, middle)))
        else:
            left = remaining_value(removed_rank, middle - 1)
            right = remaining_value(removed_rank, middle)
            output.append(float((left + right) / 2.0))
    return output


def pair_graph_diagnostics(rows: Sequence[Mapping[str, Any]]) -> tuple[int, int, int]:
    frames = sorted(
        {int(row["left_frame"]) for row in rows}
        | {int(row["right_frame"]) for row in rows}
    )
    if not frames:
        return 0, 0, 0
    degree: Counter[int] = Counter()
    parent = {frame: frame for frame in frames}

    def find(frame: int) -> int:
        while parent[frame] != frame:
            parent[frame] = parent[parent[frame]]
            frame = parent[frame]
        return frame

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for row in rows:
        left = int(row["left_frame"])
        right = int(row["right_frame"])
        degree[left] += 1
        degree[right] += 1
        union(left, right)
    return len(frames), max(degree.values(), default=0), len({find(frame) for frame in frames})


def pair_and_frame_sensitivity_rows(pair_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        key = (
            row["research_unit_id"], row["pair_set_hash"], row["anchor_variant"], row["normalization_path"],
            row["evidence_family"], row["submetric_name"], row["comparison_id"],
        )
        grouped[key].append(row)
    output: list[dict[str, Any]] = []
    counter = 1
    for key, all_rows in sorted(grouped.items()):
        frozen_eligible_pair_count = len({
            row["pair_id"]
            for row in all_rows
            if row["pair_eligibility"] == "ELIGIBLE" and row["pair_id"]
        })
        rows = [row for row in all_rows if row["pair_eligibility"] == "ELIGIBLE" and row["directional_delta"]]
        values = [float(row["directional_delta"]) for row in rows]
        full = finite_median(values)
        unique_frames, max_frame_degree, graph_components = pair_graph_diagnostics(rows)
        evidence_state = (
            "NO_ELIGIBLE_PAIRS"
            if not rows
            else "SPARSE_PAIR_EVIDENCE"
            if len(rows) <= 4
            else "PAIR_COUNT_GT4_SHARED_FRAME_REPEATED_EVIDENCE"
        )
        loo_values = leave_one_out_medians(values)
        iteration_rows: list[Mapping[str, Any] | None] = list(rows) if rows else [None]
        pair_state = (
            "NO_ELIGIBLE_PAIRS"
            if not values
            else "NOT_EVALUABLE"
            if len(values) <= 1
            else "LOPO_DIRECTION_UNSTABLE"
            if any(
                math.isfinite(value)
                and ((full > 0) != (value > 0))
                and full != 0.0
                and value != 0.0
                for value in loo_values
            )
            else "LOPO_DIRECTION_STABLE"
        )
        for omitted_index, omitted in enumerate(iteration_rows):
            loo = loo_values[omitted_index] if rows else math.nan
            sign_flip = bool(rows) and math.isfinite(full) and math.isfinite(loo) and ((full > 0) != (loo > 0)) and full != 0.0 and loo != 0.0
            output.append({
                "sensitivity_id": f"S1L-OCS-SENS-{counter:07d}",
                "research_unit_id": key[0],
                "temporal_direction_applicability": all_rows[0]["temporal_direction_applicability"],
                "temporal_correspondence_applicability": all_rows[0]["temporal_correspondence_applicability"],
                "source_pair_set_hash": all_rows[0]["source_pair_set_hash"],
                "pair_projection_rule": all_rows[0]["pair_projection_rule"],
                "pair_membership_reliability_scope": all_rows[0]["pair_membership_reliability_scope"],
                "pair_set_hash": key[1],
                "sensitivity_mode": "LEAVE_ONE_PAIR_OUT",
                "sensitivity_state": pair_state,
                "frozen_eligible_pair_count": frozen_eligible_pair_count,
                "metric_usable_pair_count": len(rows),
                "eligible_pair_count": len(rows),
                "eligible_pair_count_semantics": "METRIC_USABLE_SOURCE_ELIGIBLE_PAIRS",
                "unique_frame_count": unique_frames,
                "max_frame_pair_degree": max_frame_degree,
                "pair_graph_component_count": graph_components,
                "anchor_variant": key[2],
                "normalization_path": key[3],
                "evidence_family": key[4],
                "submetric_name": key[5],
                "comparison_id": key[6],
                "full_median_directional_delta": fmt(full),
                "omitted_pair_id": omitted["pair_id"] if omitted is not None else "",
                "omitted_frame": "",
                "leave_one_out_median_directional_delta": fmt(loo),
                "sign_flip": bool_text(sign_flip),
                "leave_one_out_min_delta": fmt(min((value for value in loo_values if math.isfinite(value)), default=math.nan)),
                "leave_one_out_max_delta": fmt(max((value for value in loo_values if math.isfinite(value)), default=math.nan)),
                "leave_one_out_state": pair_state,
                "pair_evidence_state": evidence_state,
                "review_status": "pending_direct_review",
            })
            counter += 1

        frame_ids = sorted(
            {int(row["left_frame"]) for row in rows}
            | {int(row["right_frame"]) for row in rows}
        )
        frame_out_values = [
            finite_median(
                float(row["directional_delta"])
                for row in rows
                if int(row["left_frame"]) != frame_id
                and int(row["right_frame"]) != frame_id
            )
            for frame_id in frame_ids
        ]
        if not rows:
            frame_state = "NO_ELIGIBLE_PAIRS"
            frame_iteration: list[int | None] = [None]
            frame_out_values = [math.nan]
        else:
            frame_iteration = list(frame_ids)
            finite_frame_values = [value for value in frame_out_values if math.isfinite(value)]
            if not finite_frame_values:
                frame_state = "LOFO_NOT_EVALUABLE"
            elif any(
                ((full > 0) != (value > 0))
                and full != 0.0
                and value != 0.0
                for value in finite_frame_values
            ):
                frame_state = "LOFO_DIRECTION_UNSTABLE"
            elif len(finite_frame_values) != len(frame_out_values):
                frame_state = "LOFO_PARTIAL_FRAME_LEVERAGE_UNEVALUABLE"
            else:
                frame_state = "LOFO_DIRECTION_STABLE"
        for frame_index, omitted_frame in enumerate(frame_iteration):
            loo = frame_out_values[frame_index]
            sign_flip = (
                math.isfinite(full)
                and math.isfinite(loo)
                and ((full > 0) != (loo > 0))
                and full != 0.0
                and loo != 0.0
            )
            output.append({
                "sensitivity_id": f"S1L-OCS-SENS-{counter:07d}",
                "research_unit_id": key[0],
                "temporal_direction_applicability": all_rows[0]["temporal_direction_applicability"],
                "temporal_correspondence_applicability": all_rows[0]["temporal_correspondence_applicability"],
                "source_pair_set_hash": all_rows[0]["source_pair_set_hash"],
                "pair_projection_rule": all_rows[0]["pair_projection_rule"],
                "pair_membership_reliability_scope": all_rows[0]["pair_membership_reliability_scope"],
                "pair_set_hash": key[1],
                "sensitivity_mode": "LEAVE_ONE_FRAME_OUT",
                "sensitivity_state": frame_state,
                "frozen_eligible_pair_count": frozen_eligible_pair_count,
                "metric_usable_pair_count": len(rows),
                "eligible_pair_count": len(rows),
                "eligible_pair_count_semantics": "METRIC_USABLE_SOURCE_ELIGIBLE_PAIRS",
                "unique_frame_count": unique_frames,
                "max_frame_pair_degree": max_frame_degree,
                "pair_graph_component_count": graph_components,
                "anchor_variant": key[2],
                "normalization_path": key[3],
                "evidence_family": key[4],
                "submetric_name": key[5],
                "comparison_id": key[6],
                "full_median_directional_delta": fmt(full),
                "omitted_pair_id": "",
                "omitted_frame": omitted_frame if omitted_frame is not None else "",
                "leave_one_out_median_directional_delta": fmt(loo),
                "sign_flip": bool_text(sign_flip),
                "leave_one_out_min_delta": fmt(min((value for value in frame_out_values if math.isfinite(value)), default=math.nan)),
                "leave_one_out_max_delta": fmt(max((value for value in frame_out_values if math.isfinite(value)), default=math.nan)),
                "leave_one_out_state": frame_state,
                "pair_evidence_state": evidence_state,
                "review_status": "pending_direct_review",
            })
            counter += 1
    return output


PROFILE_METRICS = {
    "ADJACENT_FIELD_NCC": ("CONTINUOUS_GRAYSCALE_FIELD", "HIGHER_IS_BETTER", "adjacent_field_ncc_median"),
    "ADJACENT_ORIENTATION_AGREEMENT": ("LOCAL_ORIENTATION_ORGANIZATION", "HIGHER_IS_BETTER", "adjacent_orientation_pair_agreement_median"),
    "ADJACENT_THIN_EDGE_JACCARD": ("SPATIAL_RELATION_TOPOLOGY", "HIGHER_IS_BETTER", "adjacent_thin_edge_jaccard_median"),
    "BOUNDARY_MISSING_MEAN": ("SAMPLING_GEOMETRY", "LOWER_IS_BETTER", "boundary_missing_mean"),
    "NONADJACENT_FIELD_NCC": ("CONTINUOUS_GRAYSCALE_FIELD", "HIGHER_IS_BETTER", "nonadjacent_field_ncc_median"),
    "NONADJACENT_ORIENTATION_AGREEMENT": ("LOCAL_ORIENTATION_ORGANIZATION", "HIGHER_IS_BETTER", "nonadjacent_orientation_pair_agreement_median"),
    "NONADJACENT_THIN_EDGE_JACCARD": ("SPATIAL_RELATION_TOPOLOGY", "HIGHER_IS_BETTER", "nonadjacent_thin_edge_jaccard_median"),
}
PARETO_BASIS = (
    "ADJACENT_FIELD_NCC",
    "ADJACENT_ORIENTATION_AGREEMENT",
    "ADJACENT_THIN_EDGE_JACCARD",
    "BOUNDARY_MISSING_MEAN",
)


def profile_summary(evaluation: Evaluation, pairs: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    summary = dict(evaluation.adjacent_metrics)
    summary.update(pair_summary(evaluation, pairs))
    summary["boundary_missing_mean"] = 1.0 - float(evaluation.valids.mean())
    return {key: float(value) if isinstance(value, (int, float, np.integer, np.floating)) else value for key, value in summary.items()}


def nondominated_indices(settings: Sequence[Mapping[str, Any]]) -> set[int]:
    objective_rows: dict[int, list[float]] = {}
    for index, setting in enumerate(settings):
        if setting["validity_status"] != "PASS":
            continue
        objectives: list[float] = []
        for metric_name in PARETO_BASIS:
            _, direction, key = PROFILE_METRICS[metric_name]
            value = float(setting["summary"].get(key, math.nan))
            if not math.isfinite(value):
                objectives.append(-math.inf)
            else:
                objectives.append(value if direction == "HIGHER_IS_BETTER" else -value)
        objective_rows[index] = objectives
    output: set[int] = set()
    for index, objectives in objective_rows.items():
        dominated = False
        for other_index, other in objective_rows.items():
            if index == other_index:
                continue
            if all(left <= right for left, right in zip(objectives, other)) and any(left < right for left, right in zip(objectives, other)):
                dominated = True
                break
        if not dominated:
            output.add(index)
    return output


def classify_nondominance_pattern(
    grid: Sequence[float],
    values: Sequence[float],
) -> tuple[str, int, bool, bool, str, str]:
    unique = sorted(set(float(value) for value in values))
    if not unique:
        return "EMPTY", 0, False, False, "", ""
    indices = sorted(grid.index(value) for value in unique)
    components = 1 + sum(current != previous + 1 for previous, current in zip(indices, indices[1:]))
    lower = indices[0] == 0
    upper = indices[-1] == len(grid) - 1
    if len(unique) == len(grid):
        pattern = "ALL_GRID"
    elif components > 1:
        pattern = "MULTICOMPONENT"
    elif len(unique) == 1:
        pattern = "SINGLETON"
    elif lower or upper:
        pattern = "EDGE_CONTIGUOUS_SET"
    else:
        pattern = "INTERIOR_CONTIGUOUS_SET"
    return pattern, components, lower, upper, fmt(unique[0]), fmt(unique[-1])


def parameter_interpretation_limit(parameter_id: str) -> str:
    if parameter_id in {"LONG_SCALE", "SHORT_SCALE"}:
        return "FIXED_256X128_GRID_COUPLES_SCALE_TO_RESAMPLING;NO_PHYSICAL_SCALE_IDENTIFICATION"
    if parameter_id == "AXIS_UNSIGNED":
        return "GRID_NONDOMINANCE_PATTERN_ONLY;AXIS_PLACEBO_REVIEW_REQUIRED"
    return "GRID_NONDOMINANCE_PATTERN_ONLY;NO_CENTER_IDENTIFICATION_CRITERION"


def run_parameter_profiles(
    unit: Mapping[str, Any],
    anchor_variant: str,
    normalization_path: str,
    source_pair_set_hash: str,
    pair_hash: str,
    pairs: Sequence[Mapping[str, Any]],
    cache: Mapping[tuple[str, int], tuple[np.ndarray, np.ndarray]],
    baseline_evaluation: Evaluation,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    profile_rows: list[dict[str, Any]] = []
    observations: dict[str, dict[str, Any]] = {}
    for parameter_id, grid_values in PARAMETER_GRIDS.items():
        setting_rows: list[dict[str, Any]] = []
        for setting_index, value in enumerate(grid_values):
            is_baseline = (
                (parameter_id in {"CENTER_RADIAL", "CENTER_TANGENTIAL", "AXIS_UNSIGNED"} and float(value) == 0.0)
                or (parameter_id in {"LONG_SCALE", "SHORT_SCALE"} and float(value) == 1.0)
            )
            if is_baseline:
                evaluation = baseline_evaluation
            else:
                evaluation, _ = evaluate(
                    unit,
                    anchor_variant,
                    "CENTER_TRACKED_BODY",
                    "GT_DERIVED_UNSIGNED_BODY",
                    normalization_path,
                    cache,
                    parameter_id=parameter_id,
                    parameter_value=float(value),
                    collect_sampling=False,
                )
            summary = profile_summary(evaluation, pairs)
            if not all(row["normalization_status"] == "PASS" for row in evaluation.normalization_rows):
                validity_status = "NORMALIZATION_FAILURE_PRESENT"
            elif any(
                not math.isfinite(float(summary.get(PROFILE_METRICS[metric_name][2], math.nan)))
                for metric_name in PARETO_BASIS
            ):
                validity_status = "NONFINITE_PARETO_METRIC_PRESENT"
            else:
                validity_status = "PASS"
            setting_rows.append({
                "setting_index": setting_index,
                "parameter_value": float(value),
                "summary": summary,
                "validity_status": validity_status,
            })
        nondominated = nondominated_indices(setting_rows)
        nondominated_grid_values = [setting_rows[index]["parameter_value"] for index in sorted(nondominated)]
        pattern, components, lower, upper, diagnostic_min, diagnostic_max = classify_nondominance_pattern(
            list(grid_values),
            nondominated_grid_values,
        )
        valid_setting_count = sum(setting["validity_status"] == "PASS" for setting in setting_rows)
        observations[parameter_id] = {
            "nondominated_grid_values": nondominated_grid_values,
            "state": "NOT_IDENTIFIABLE",
            "nondominance_pattern": pattern,
            "components": components,
            "touches_lower": lower,
            "touches_upper": upper,
            "diagnostic_min": diagnostic_min,
            "diagnostic_max": diagnostic_max,
            "valid_setting_count": valid_setting_count,
            "profile_validity_state": (
                "PASS"
                if valid_setting_count == len(grid_values)
                else "PARTIAL_VALID_SETTINGS"
                if valid_setting_count
                else "NO_VALID_SETTINGS"
            ),
        }
        for setting in setting_rows:
            long_scale = float(setting["parameter_value"]) if parameter_id == "LONG_SCALE" else 1.0
            short_scale = float(setting["parameter_value"]) if parameter_id == "SHORT_SCALE" else 1.0
            effective_source_px_per_grid_x = (
                float(unit["reference_long"])
                * CONTEXT_FACTOR
                * long_scale
                / (GRID_WIDTH - 1)
            )
            effective_source_px_per_grid_y = (
                float(unit["reference_short"])
                * CONTEXT_FACTOR
                * short_scale
                / (GRID_HEIGHT - 1)
            )
            for metric_name, (family, direction, key) in PROFILE_METRICS.items():
                metric_value = float(setting["summary"].get(key, math.nan))
                if math.isfinite(metric_value):
                    metric_value_status = "AVAILABLE_FINITE"
                elif metric_name.startswith("NONADJACENT_") and not any(
                    pair["pair_eligibility"] == "ELIGIBLE" for pair in pairs
                ):
                    metric_value_status = "UNAVAILABLE_NO_ELIGIBLE_PAIRS"
                else:
                    metric_value_status = "UNAVAILABLE_NONFINITE_METRIC"
                estimator = (
                    "NORMALIZED_8BIT_FIELD_NCC"
                    if family == "CONTINUOUS_GRAYSCALE_FIELD"
                    else "STRUCTURE_TENSOR_ORIENTATION_PROXY"
                    if family == "LOCAL_ORIENTATION_ORGANIZATION"
                    else "CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON"
                    if family == "SPATIAL_RELATION_TOPOLOGY"
                    else "IMAGING_VALID_BOUNDARY_FRACTION"
                )
                profile_rows.append({
                    "profile_row_id": "",
                    "research_unit_id": unit["research_unit_id"],
                    "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
                    "temporal_direction_applicability": temporal_direction_applicability(unit),
                    "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
                    "anchor_variant": anchor_variant,
                    "normalization_path": normalization_path,
                    "evidence_family": family,
                    "evidence_estimator_id": estimator,
                    "submetric_name": metric_name,
                    "metric_direction": direction,
                    "parameter_id": parameter_id,
                    "setting_id": f"{parameter_id}|{setting['setting_index']}",
                    "parameter_value": fmt(setting["parameter_value"]),
                    "other_parameters_fixed_definition": "ALL_OTHER_PARAMETERS_AT_GT_DERIVED_BASELINE",
                    "effective_source_px_per_grid_x": fmt(effective_source_px_per_grid_x),
                    "effective_source_px_per_grid_y": fmt(effective_source_px_per_grid_y),
                    "scale_response_scope": (
                        "WINDOW_EXTENT_PLUS_RESAMPLING_COUPLED"
                        if parameter_id in {"LONG_SCALE", "SHORT_SCALE"}
                        else "NOT_A_SCALE_PROFILE"
                    ),
                    "physical_scale_bound_status": (
                        "NOT_EVALUATED_FIXED_GRID_RESAMPLING_CONFOUND"
                        if parameter_id in {"LONG_SCALE", "SHORT_SCALE"}
                        else "NOT_APPLICABLE"
                    ),
                    "metric_value": fmt(metric_value),
                    "metric_value_status": metric_value_status,
                    "validity_status": setting["validity_status"],
                    "pareto_basis_setting_validity_status": setting["validity_status"],
                    "validity_status_semantics": "SETTING_LEVEL_PARETO_BASIS_STATUS_NOT_ROW_METRIC_AVAILABILITY",
                    "valid_setting_count": valid_setting_count,
                    "pareto_nondominated": bool_text(setting["setting_index"] in nondominated),
                    "grid_nondominance_pattern": pattern,
                    "parameter_interpretation_limit": parameter_interpretation_limit(parameter_id),
                    "pareto_basis": ";".join(PARETO_BASIS),
                    "grid_lower_edge": bool_text(setting["setting_index"] == 0),
                    "grid_upper_edge": bool_text(setting["setting_index"] == len(grid_values) - 1),
                    "pair_membership_rule": PAIR_PROJECTION_RULE,
                    "source_pair_set_hash": source_pair_set_hash,
                    "pair_projection_rule": PAIR_PROJECTION_RULE,
                    "pair_membership_reliability_scope": pair_membership_reliability_scope(unit),
                    "pair_set_hash": pair_hash,
                    "candidate_pair_count": len(pairs),
                    "eligible_pair_count": sum(pair["pair_eligibility"] == "ELIGIBLE" for pair in pairs),
                    "pair_evidence_state": (
                        "NO_ELIGIBLE_PAIRS"
                        if not any(pair["pair_eligibility"] == "ELIGIBLE" for pair in pairs)
                        else "SPARSE_PAIR_EVIDENCE"
                        if sum(pair["pair_eligibility"] == "ELIGIBLE" for pair in pairs) <= 4
                        else "PAIR_COUNT_GT4_SHARED_FRAME_REPEATED_EVIDENCE"
                    ),
                    "review_status": "pending_direct_review",
                })
    return profile_rows, observations


def observability_rows_for_unit(
    unit: Mapping[str, Any],
    anchor_variant: str,
    source_pair_set_hash: str,
    pair_hash: str,
    pairs: Sequence[Mapping[str, Any]],
    by_normalization: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    counter = 1
    eligible_pair_count = sum(
        pair["pair_eligibility"] == "ELIGIBLE" for pair in pairs
    )
    pair_evidence_state = (
        "NO_ELIGIBLE_PAIRS"
        if eligible_pair_count == 0
        else "SPARSE_PAIR_EVIDENCE"
        if eligible_pair_count <= 4
        else "PAIR_COUNT_GT4_SHARED_FRAME_REPEATED_EVIDENCE"
    )
    for normalization_path in NORMALIZATION_PATHS:
        for parameter_id, observation in by_normalization[normalization_path].items():
            output.append({
                "observability_id": "",
                "scope_level": "UNIT_NORMALIZATION",
                "research_unit_id": unit["research_unit_id"],
                "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
                "temporal_direction_applicability": temporal_direction_applicability(unit),
                "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
                "parameter_id": parameter_id,
                "anchor_variant": anchor_variant,
                "evidence_family": "SEPARATE_METRIC_GRID_NONDOMINANCE_DIAGNOSTIC",
                "evidence_estimator_contract": "FIELD_NCC;STRUCTURE_TENSOR_ORIENTATION_PROXY;CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON;BOUNDARY_FRACTION",
                "normalization_path": normalization_path,
                "source_pair_set_hash": source_pair_set_hash,
                "pair_projection_rule": PAIR_PROJECTION_RULE,
                "pair_set_hash": pair_hash,
                "candidate_pair_count": len(pairs),
                "eligible_pair_count": eligible_pair_count,
                "pair_evidence_state": pair_evidence_state,
                "pair_usage_in_grid_nondominance": "NOT_USED_IN_PARETO_BASIS;CARRIED_FOR_CONTEXT_ONLY",
                "pareto_nondominated_grid_values": ";".join(
                    fmt(value) for value in observation["nondominated_grid_values"]
                ),
                "grid_nondominance_pattern": observation["nondominance_pattern"],
                "nondominated_grid_component_count": observation["components"],
                "touches_lower_grid_edge": bool_text(observation["touches_lower"]),
                "touches_upper_grid_edge": bool_text(observation["touches_upper"]),
                "reported_lower_bound": "",
                "reported_upper_bound": "",
                "diagnostic_grid_min": observation["diagnostic_min"],
                "diagnostic_grid_max": observation["diagnostic_max"],
                "parameter_interpretation_limit": parameter_interpretation_limit(parameter_id),
                "valid_setting_count": observation["valid_setting_count"],
                "profile_validity_state": observation["profile_validity_state"],
                "normalization_agreement": "SINGLE_PATH_ONLY",
                "fixed_rule_replay_scope": unit["replay_status"],
                "placebo_relation": "PENDING_AXIS_PLACEBO_REVIEW" if parameter_id == "AXIS_UNSIGNED" else "NOT_APPLICABLE",
                "observability_state": observation["state"],
                "decision_reason": (
                    "Pareto grid nondominance pattern is diagnostic only and is not an identification criterion"
                    if observation["valid_setting_count"]
                    else "NO_VALID_SETTINGS_AFTER_NORMALIZATION_AND_FINITE_METRIC_GATE"
                ),
                "review_status": "pending_direct_review",
            })
            counter += 1
    for parameter_id, grid_values in PARAMETER_GRIDS.items():
        fixed_values = set(
            float(value)
            for value in by_normalization["FIXED_REFERENCE"][parameter_id]["nondominated_grid_values"]
        )
        local_values = set(
            float(value)
            for value in by_normalization["CANDIDATE_LOCAL_REESTIMATED"][parameter_id]["nondominated_grid_values"]
        )
        fixed_valid_count = int(by_normalization["FIXED_REFERENCE"][parameter_id]["valid_setting_count"])
        local_valid_count = int(by_normalization["CANDIDATE_LOCAL_REESTIMATED"][parameter_id]["valid_setting_count"])
        intersection = sorted(fixed_values & local_values)
        union = sorted(fixed_values | local_values)
        if not fixed_valid_count or not local_valid_count:
            pattern, components, lower, upper, diagnostic_min, diagnostic_max = "EMPTY", 0, False, False, "", ""
            agreement = "INVALID_NORMALIZATION_OR_METRIC_PROFILE"
        elif not intersection:
            pattern, components, lower, upper, diagnostic_min, diagnostic_max = "EMPTY", 0, False, False, "", ""
            agreement = "NORMALIZATION_DEPENDENT"
        else:
            pattern, components, lower, upper, diagnostic_min, diagnostic_max = classify_nondominance_pattern(
                list(grid_values),
                intersection,
            )
            agreement = (
                "IDENTICAL_GRID_NONDOMINANCE_PATTERN"
                if fixed_values == local_values
                else "PARTIAL_GRID_NONDOMINANCE_OVERLAP"
            )
        output.append({
            "observability_id": "",
            "scope_level": "UNIT_DUAL_NORMALIZATION",
            "research_unit_id": unit["research_unit_id"],
            "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
            "temporal_direction_applicability": temporal_direction_applicability(unit),
            "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
            "parameter_id": parameter_id,
            "anchor_variant": anchor_variant,
            "evidence_family": "SEPARATE_METRIC_GRID_NONDOMINANCE_DIAGNOSTIC",
            "evidence_estimator_contract": "FIELD_NCC;STRUCTURE_TENSOR_ORIENTATION_PROXY;CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON;BOUNDARY_FRACTION",
            "normalization_path": "DUAL_PATH_GRID_NONDOMINANCE_INTERSECTION",
            "source_pair_set_hash": source_pair_set_hash,
            "pair_projection_rule": PAIR_PROJECTION_RULE,
            "pair_set_hash": pair_hash,
            "candidate_pair_count": len(pairs),
            "eligible_pair_count": eligible_pair_count,
            "pair_evidence_state": pair_evidence_state,
            "pair_usage_in_grid_nondominance": "NOT_USED_IN_PARETO_BASIS;CARRIED_FOR_CONTEXT_ONLY",
            "pareto_nondominated_grid_values": ";".join(fmt(value) for value in intersection),
            "grid_nondominance_pattern": pattern,
            "nondominated_grid_component_count": components,
            "touches_lower_grid_edge": bool_text(lower),
            "touches_upper_grid_edge": bool_text(upper),
            "reported_lower_bound": "",
            "reported_upper_bound": "",
            "diagnostic_grid_min": diagnostic_min,
            "diagnostic_grid_max": diagnostic_max,
            "parameter_interpretation_limit": parameter_interpretation_limit(parameter_id),
            "valid_setting_count": min(fixed_valid_count, local_valid_count),
            "profile_validity_state": (
                "PASS"
                if fixed_valid_count == len(grid_values) and local_valid_count == len(grid_values)
                else "PARTIAL_VALID_SETTINGS"
                if fixed_valid_count and local_valid_count
                else "NO_VALID_SETTINGS_IN_ONE_OR_MORE_PATHS"
            ),
            "normalization_agreement": agreement,
            "fixed_rule_replay_scope": unit["replay_status"],
            "placebo_relation": "PENDING_AXIS_PLACEBO_REVIEW" if parameter_id == "AXIS_UNSIGNED" else "NOT_APPLICABLE",
            "observability_state": "NOT_IDENTIFIABLE",
            "decision_reason": (
                "dual-path Pareto grid-pattern intersection is diagnostic only, not identification; union="
                + ";".join(fmt(value) for value in union)
                if fixed_valid_count and local_valid_count
                else "NO_VALID_SETTINGS_IN_ONE_OR_MORE_NORMALIZATION_PATHS"
            ),
            "review_status": "pending_direct_review",
        })
        counter += 1
    return output


def write_dynamic_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise AssertionError(f"no rows for {path}")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    write_csv(path, rows, fields)


def colorize_score(score: np.ndarray) -> np.ndarray:
    return cv2.applyColorMap(np.round(np.clip(score, 0.0, 1.0) * 255.0).astype(np.uint8), cv2.COLORMAP_TURBO)


def safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", value)


def visual_tile(image: np.ndarray, title: str, width: int = 300, height: int = 180) -> np.ndarray:
    resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    if resized.ndim == 2:
        resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
    base.put_text(resized, title, (6, 18), scale=0.38)
    return resized


def mean_score(evaluation: Evaluation) -> np.ndarray:
    scores = evaluation.scores.astype(np.float32) / 255.0
    valid_count = evaluation.valids.sum(axis=0)
    return np.divide((scores * evaluation.valids).sum(axis=0), valid_count, out=np.zeros_like(scores[0]), where=valid_count > 0)


def equal_support_visual(
    unit: Mapping[str, Any],
    evaluations: Mapping[tuple[str, str], Evaluation],
    review_status: str,
) -> dict[str, Any]:
    rows: list[np.ndarray] = []
    for normalization_path in NORMALIZATION_PATHS:
        tiles = []
        for representation in REPRESENTATIONS:
            evaluation = evaluations[(normalization_path, representation)]
            tiles.append(visual_tile(colorize_score(mean_score(evaluation)), f"{normalization_path} | {representation}"))
        rows.append(np.concatenate(tiles, axis=1))
    canvas = np.concatenate(rows, axis=0)
    directory = VISUAL_ROOT / safe_component(unit["research_unit_id"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "equal_support_four_representation_mean_fields.png"
    cv2.imwrite(str(path), canvas)
    return {
        "case_id": f"{unit['research_unit_id']}|EQUAL_SUPPORT",
        "artifact_type": "equal_support_four_representation_mean_fields",
        "research_unit_id": unit["research_unit_id"],
        "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
        "artifact_path": str(path),
        "review_status": review_status,
        "notes": "same window, grid, density, mask rule and gray input; two normalization paths shown separately",
    }


def axis_placebo_visual(
    unit: Mapping[str, Any],
    evaluations: Mapping[tuple[str, str], Evaluation],
    review_status: str,
) -> dict[str, Any]:
    rows: list[np.ndarray] = []
    for normalization_path in NORMALIZATION_PATHS:
        tiles = [
            visual_tile(colorize_score(mean_score(evaluations[(normalization_path, rule)])), f"{normalization_path} | {rule}", width=230)
            for rule in AXIS_RULES
        ]
        rows.append(np.concatenate(tiles, axis=1))
    canvas = np.concatenate(rows, axis=0)
    directory = VISUAL_ROOT / safe_component(unit["research_unit_id"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "axis_placebo_mean_fields.png"
    cv2.imwrite(str(path), canvas)
    return {
        "case_id": f"{unit['research_unit_id']}|AXIS_PLACEBOS",
        "artifact_type": "axis_placebo_mean_fields",
        "research_unit_id": unit["research_unit_id"],
        "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
        "artifact_path": str(path),
        "review_status": review_status,
        "notes": "same centre, size, support and pair contract; no axis ordering or aggregate score",
    }


def line_panel(values: Sequence[tuple[float, float]], title: str, width: int = 270, height: int = 170) -> np.ndarray:
    canvas = np.full((height, width, 3), 245, dtype=np.uint8)
    finite = [(x, y) for x, y in values if math.isfinite(y)]
    base.put_text(canvas, title, (6, 18), color=(20, 20, 20), scale=0.36)
    if not finite:
        base.put_text(canvas, "no finite values", (30, 90), color=(40, 40, 180), scale=0.45)
        return canvas
    xs = [item[0] for item in finite]
    ys = [item[1] for item in finite]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmax <= xmin:
        xmax = xmin + 1.0
    if ymax <= ymin:
        ymax = ymin + 1.0
    points = []
    for x, y in finite:
        px = int(round(25 + (x - xmin) / (xmax - xmin) * (width - 45)))
        py = int(round(height - 25 - (y - ymin) / (ymax - ymin) * (height - 55)))
        points.append((px, py))
    if len(points) >= 2:
        cv2.polylines(canvas, [np.asarray(points, dtype=np.int32)], False, (50, 80, 210), 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(canvas, point, 4, (20, 20, 180), -1, cv2.LINE_AA)
    base.put_text(canvas, f"min={ymin:.3f} max={ymax:.3f}", (6, height - 7), color=(20, 20, 20), scale=0.30)
    return canvas


def parameter_visual(
    unit: Mapping[str, Any],
    profile_rows: Sequence[Mapping[str, Any]],
    review_status: str,
) -> dict[str, Any]:
    metric_order = ("ADJACENT_FIELD_NCC", "ADJACENT_ORIENTATION_AGREEMENT", "ADJACENT_THIN_EDGE_JACCARD", "BOUNDARY_MISSING_MEAN")
    panels: list[np.ndarray] = []
    for parameter_id in PARAMETER_GRIDS:
        row_panels = []
        for metric_name in metric_order:
            fixed_rows = [row for row in profile_rows if row["parameter_id"] == parameter_id and row["submetric_name"] == metric_name and row["normalization_path"] == "FIXED_REFERENCE"]
            local_rows = [row for row in profile_rows if row["parameter_id"] == parameter_id and row["submetric_name"] == metric_name and row["normalization_path"] == "CANDIDATE_LOCAL_REESTIMATED"]
            fixed_values = [(float(row["parameter_value"]), base.parse_float(row["metric_value"])) for row in fixed_rows]
            local_values = [(float(row["parameter_value"]), base.parse_float(row["metric_value"])) for row in local_rows]
            panel = line_panel(fixed_values, f"{parameter_id} | {metric_name} | fixed")
            local_panel = line_panel(local_values, f"{parameter_id} | {metric_name} | local")
            row_panels.append(np.concatenate([panel, local_panel], axis=0))
        panels.append(np.concatenate(row_panels, axis=1))
    canvas = np.concatenate(panels, axis=0)
    directory = VISUAL_ROOT / safe_component(unit["research_unit_id"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "per_parameter_dual_normalization_profiles.png"
    cv2.imwrite(str(path), canvas)
    return {
        "case_id": f"{unit['research_unit_id']}|PARAMETER_PROFILES",
        "artifact_type": "per_parameter_dual_normalization_profiles",
        "research_unit_id": unit["research_unit_id"],
        "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
        "artifact_path": str(path),
        "review_status": review_status,
        "notes": "five one-dimensional parameter profiles; fixed and local normalization are not averaged",
    }


def pair_count_visual(representation_rows: Sequence[Mapping[str, Any]], review_status: str) -> dict[str, Any]:
    selected = [
        row for row in representation_rows
        if row["representation"] == "CENTER_TRACKED_BODY" and row["normalization_path"] == "FIXED_REFERENCE"
    ]
    height = max(220, 34 * (len(selected) + 2))
    canvas = np.full((height, 1250, 3), 248, dtype=np.uint8)
    base.put_text(canvas, "Frozen pair-set audit: candidate / eligible / state", (8, 22), color=(20, 20, 20), scale=0.48)
    y = 52
    for row in selected:
        text = (
            f"{row['research_unit_id']} | {row['anchor_variant']} | "
            f"{row['candidate_pair_count']}/{row['eligible_pair_count']} | {row['pair_evidence_state']} | "
            f"field={row.get('nonadjacent_field_ncc_median','')}"
        )
        color = (30, 30, 180) if row["pair_evidence_state"] == "SPARSE_PAIR_EVIDENCE" else (20, 90, 20)
        base.put_text(canvas, text, (8, y), color=color, scale=0.36)
        y += 32
    path = VISUAL_ROOT / "pair_set_sparsity_audit.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), canvas)
    return {
        "case_id": "GLOBAL|PAIR_SET_SPARSITY",
        "artifact_type": "pair_set_sparsity_audit",
        "research_unit_id": "GLOBAL",
        "counterfactual_semantic_class": "MIXED_REGISTRY_SUMMARY",
        "artifact_path": str(path),
        "review_status": review_status,
        "notes": "pair counts are evidence support, not independent sample size",
    }


def aggregate_observability_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for anchor_variant in ("raw_gt", "smoothed_gt"):
        for parameter_id, grid_values in PARAMETER_GRIDS.items():
            selected = [
                row for row in rows
                if row["scope_level"] == "UNIT_DUAL_NORMALIZATION"
                and row["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE"
                and row["anchor_variant"] == anchor_variant
                and row["parameter_id"] == parameter_id
            ]
            if len(selected) != 3:
                continue
            value_sets = [
                {
                    float(value)
                    for value in row["pareto_nondominated_grid_values"].split(";")
                    if value
                }
                for row in selected
            ]
            profiles_usable = all(int(row.get("valid_setting_count", 0)) > 0 for row in selected)
            profiles_complete = all(row.get("profile_validity_state") == "PASS" for row in selected)
            intersection = sorted(set.intersection(*value_sets)) if value_sets and all(value_sets) else []
            union = sorted(set.union(*value_sets)) if value_sets else []
            if not profiles_usable:
                pattern, components, lower, upper, diagnostic_min, diagnostic_max = "EMPTY", 0, False, False, "", ""
                agreement = "INVALID_NORMALIZATION_OR_METRIC_PROFILE"
            elif intersection:
                pattern, components, lower, upper, diagnostic_min, diagnostic_max = classify_nondominance_pattern(
                    list(grid_values),
                    intersection,
                )
                agreement = "DEVELOPMENT_AND_TWO_WITHIN_SCENE_OTHER_VEHICLE_COMMON_GRID_NONDOMINANCE_PATTERN"
            else:
                pattern, components, lower, upper, diagnostic_min, diagnostic_max = "EMPTY", 0, False, False, "", ""
                agreement = "NO_COMMON_DEVELOPMENT_OTHER_VEHICLE_GRID_NONDOMINANCE_PATTERN"
            output.append({
                "observability_id": "",
                "scope_level": "CORE_VEHICLE_AGGREGATE",
                "research_unit_id": "GM_RM017_CORE_VEHICLES",
                "counterfactual_semantic_class": "TRUE_VEHICLE_POSITIVE_AGGREGATE",
                "temporal_direction_applicability": "NOT_A_TEMPORAL_DIRECTION_TEST",
                "temporal_correspondence_applicability": "NOT_A_TEMPORAL_CORRESPONDENCE_TEST",
                "parameter_id": parameter_id,
                "anchor_variant": anchor_variant,
                "evidence_family": "SEPARATE_METRIC_GRID_NONDOMINANCE_DIAGNOSTIC",
                "evidence_estimator_contract": "FIELD_NCC;STRUCTURE_TENSOR_ORIENTATION_PROXY;CANNY_THIN_EDGE_CONNECTIVITY_PROXY_NOT_MORPHOLOGICAL_SKELETON;BOUNDARY_FRACTION",
                "normalization_path": "DUAL_PATH_AND_WITHIN_SCENE_OTHER_VEHICLE_GRID_INTERSECTION",
                "source_pair_set_hash": "",
                "pair_projection_rule": PAIR_PROJECTION_RULE,
                "pair_set_hash": "",
                "candidate_pair_count": "",
                "eligible_pair_count": "",
                "pair_evidence_state": "MIXED_CORE_VEHICLE_PAIR_SUPPORT_SEE_UNIT_ROWS",
                "pair_usage_in_grid_nondominance": "MULTIPLE_SEPARATE_CORE_PAIR_SETS;NOT_USED_IN_PARETO_BASIS;SEE_PROFILE_AND_SENSITIVITY",
                "pareto_nondominated_grid_values": ";".join(fmt(value) for value in intersection),
                "grid_nondominance_pattern": pattern,
                "nondominated_grid_component_count": components,
                "touches_lower_grid_edge": bool_text(lower),
                "touches_upper_grid_edge": bool_text(upper),
                "reported_lower_bound": "",
                "reported_upper_bound": "",
                "diagnostic_grid_min": diagnostic_min,
                "diagnostic_grid_max": diagnostic_max,
                "parameter_interpretation_limit": parameter_interpretation_limit(parameter_id),
                "valid_setting_count": min(int(row.get("valid_setting_count", 0)) for row in selected),
                "profile_validity_state": (
                    "PASS"
                    if profiles_complete
                    else "PARTIAL_VALID_SETTINGS"
                    if profiles_usable
                    else "NO_VALID_SETTINGS_IN_ONE_OR_MORE_CORE_VEHICLES"
                ),
                "normalization_agreement": agreement,
                "fixed_rule_replay_scope": "TWO_WITHIN_SCENE_OTHER_VEHICLE_FIXED_RULE_REPLAYS",
                "placebo_relation": "PENDING_AXIS_PLACEBO_REVIEW" if parameter_id == "AXIS_UNSIGNED" else "NOT_APPLICABLE",
                "observability_state": "NOT_IDENTIFIABLE",
                "decision_reason": (
                    "common Pareto grid-pattern values across development and two within-scene other-vehicle replays are diagnostic only; union="
                    + ";".join(fmt(value) for value in union)
                    if profiles_usable
                    else "NO_VALID_SETTINGS_IN_ONE_OR_MORE_CORE_VEHICLES"
                ),
                "review_status": "pending_direct_review",
            })
    return output


def research_unit_row(unit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "research_unit_id": unit["research_unit_id"],
        "scene": unit["scene"],
        "canonical_vehicle_id": unit["canonical_vehicle_id"],
        "source_segment_id": unit["source_trajectory_segment_id"],
        "target_region_id": unit["target_region_id"],
        "benchmark_role": unit["benchmark_role"],
        "research_role": unit["research_role"],
        "unit_type": unit["unit_type"],
        "counterfactual_semantic_class": unit["counterfactual_semantic_class"],
        "temporal_direction_applicability": temporal_direction_applicability(unit),
        "temporal_correspondence_applicability": temporal_correspondence_applicability(unit),
        "vehicle_present_in_target": bool_text(bool(unit["vehicle_present_in_target"])),
        "valid_for_identity_test": bool_text(bool(unit["valid_for_identity_test"])),
        "valid_for_vehicle_class_test": bool_text(bool(unit["valid_for_vehicle_class_test"])),
        "valid_for_temporal_test": bool_text(bool(unit["valid_for_temporal_test"])),
        "valid_for_temporal_test_scope": unit["valid_for_temporal_test_scope"],
        "valid_for_temporal_correspondence_test": bool_text(bool(unit["valid_for_temporal_correspondence_test"])),
        "valid_for_temporal_direction_test": bool_text(bool(unit["valid_for_temporal_direction_test"])),
        "background_spatial_control_group": unit["background_spatial_control_group"],
        "background_parameter_envelope_group": unit["background_parameter_envelope_group"],
        "background_control_semantic_role": unit["background_control_semantic_role"],
        "transform_rule_id": unit["transform_rule_id"],
        "frame_count": len(unit["rows"]),
        "freeze_source": unit["freeze_source"],
        "replay_status": unit["replay_status"],
        "optical_identity_source": unit["optical_identity_source"],
        "center_source": unit["center_source"],
        "axis_source": unit["axis_source"],
        "scale_source": unit["scale_source"],
        "gt_information_debt": unit["gt_information_debt"],
        "optical_condition_execution_status": unit["optical_condition_execution_status"],
        "counterfactual_scope_limitation": unit["counterfactual_scope_limitation"],
        "vehicle_absence_evidence_scope": unit["vehicle_absence_evidence_scope"],
        "anchor_variant_contract": "RAW_AND_SMOOTHED_SEPARATE_SOURCE_POSITIVE_PAIR_SETS_FOR_ALL_UNITS",
        "pair_membership_source_segment_id": unit["pair_membership_source_segment_id"],
        "pair_membership_contract": unit["pair_membership_contract"],
        "background_type": unit.get("background_type", ""),
        "background_quality_status": unit.get("background_quality_status", ""),
        "background_reviewed_gt_overlap": fmt(unit.get("background_reviewed_gt_overlap", math.nan)),
        "config_hash": CONFIG_HASH,
        "review_status": "pending_direct_review",
        "notes": unit["notes"],
    }


def resolved_background_records(background_rows: Sequence[Mapping[str, str]]) -> dict[str, dict[str, Any]]:
    by_id = {row["background_thread_id"]: row for row in background_rows}
    output: dict[str, dict[str, Any]] = {}
    for background_id, config in HARD_BACKGROUND_CONFIG.items():
        if background_id in by_id:
            source = by_id[background_id]
            output[background_id] = {
                "offset_radial_px": float(source["offset_radial_px"]),
                "offset_tangential_px": float(source["offset_tangential_px"]),
                "moving": bool(config["moving"]),
                "quality": str(config["quality"]),
                "background_type": source["background_type"],
                "reviewed_gt_overlap": float(source["mean_gt_overlap_fraction"]),
                "spatial_control_group": str(config["spatial_control_group"]),
                "parameter_envelope_group": str(config["parameter_envelope_group"]),
                "control_semantic_role": str(config["control_semantic_role"]),
                "notes": "frozen background position proposal; re-evaluated with equal support and direct visual review",
            }
        else:
            output[background_id] = dict(config)
    if len(output) != 4:
        raise AssertionError("exactly four named PV002-geometry background controls are frozen for this audit")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-status", choices=("pending_direct_review", "directly_reviewed_complete"), default="pending_direct_review")
    args = parser.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    VISUAL_ROOT.mkdir(parents=True, exist_ok=True)
    local_fields = read_csv(LOCAL_FIELD_PATH)
    coordinate_rows = read_csv(COORDINATE_FRAME_PATH)
    background_rows = read_csv(BACKGROUND_PATH)
    reliability_rows = reliability_index(coordinate_rows)

    vehicles = build_vehicle_units(local_fields)
    development = vehicles[DEVELOPMENT_SEGMENT]
    swaps = [
        build_swap_unit(development, vehicles[OTHER_VEHICLE_REPLAY_SEGMENTS[0]]),
        build_swap_unit(vehicles[OTHER_VEHICLE_REPLAY_SEGMENTS[0]], development),
    ]
    background_records = resolved_background_records(background_rows)
    backgrounds = [build_background_unit(development, background_id, record) for background_id, record in background_records.items()]
    temporal_units = [unit for vehicle in vehicles.values() for unit in build_temporal_units(vehicle)]
    units = list(vehicles.values()) + swaps + backgrounds + temporal_units
    expected_semantic_counts = {
        "TRUE_VEHICLE_POSITIVE": 3,
        "IDENTITY_NEGATIVE_CLASS_POSITIVE": 2,
        "VEHICLE_CLASS_NEGATIVE": 4,
        "TEMPORAL_NEGATIVE": 12,
    }
    actual_semantic_counts = Counter(
        unit["counterfactual_semantic_class"] for unit in units
    )
    if len(units) != 21 or dict(actual_semantic_counts) != expected_semantic_counts:
        raise AssertionError(
            f"frozen research-unit registry changed: count={len(units)} semantics={dict(actual_semantic_counts)}"
        )
    if len({unit["background_spatial_control_group"] for unit in backgrounds}) != 3:
        raise AssertionError("baseline background spatial-cluster count must remain 3")
    if len({unit["background_parameter_envelope_group"] for unit in backgrounds}) != 2:
        raise AssertionError("strict one-dimensional parameter-envelope cluster count must remain 2")

    source_pair_registry: dict[tuple[str, str], tuple[list[dict[str, Any]], str]] = {}
    for source_segment_id, source_unit in vehicles.items():
        source_cache = image_cache(source_unit)
        for anchor_variant in ANCHOR_VARIANTS:
            source_membership_reference, _ = evaluate(
                source_unit,
                anchor_variant,
                "CENTER_TRACKED_BODY",
                "GT_DERIVED_UNSIGNED_BODY",
                "FIXED_REFERENCE",
                source_cache,
                collect_sampling=False,
            )
            source_pair_registry[(source_segment_id, anchor_variant)] = pair_candidates(
                source_unit,
                anchor_variant,
                reliability_rows,
                source_membership_reference,
            )
        del source_cache

    unit_rows = [research_unit_row(unit) for unit in units]
    sampling_rows: list[dict[str, Any]] = []
    representation_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    observability_rows: list[dict[str, Any]] = []
    visual_rows: list[dict[str, Any]] = []

    for unit_index, unit in enumerate(units, start=1):
        print(
            f"UNIT_START {unit_index}/{len(units)} {unit['research_unit_id']} {unit['counterfactual_semantic_class']}",
            flush=True,
        )
        cache = image_cache(unit)
        for anchor_variant in ANCHOR_VARIANTS:
            membership_reference, membership_sampling = evaluate(
                unit,
                anchor_variant,
                "CENTER_TRACKED_BODY",
                "GT_DERIVED_UNSIGNED_BODY",
                "FIXED_REFERENCE",
                cache,
                collect_sampling=True,
            )
            source_pairs, source_pair_set_hash = source_pair_registry[
                (unit["source_trajectory_segment_id"], anchor_variant)
            ]
            pairs, pair_hash = project_source_pair_candidates(
                unit,
                anchor_variant,
                source_pairs,
                source_pair_set_hash,
            )
            baseline_evaluations_for_visual: dict[tuple[str, str], Evaluation] = {}
            profile_baseline_evaluations: dict[str, Evaluation] = {}
            for normalization_path in NORMALIZATION_PATHS:
                representation_evaluations: dict[str, Evaluation] = {}
                for representation in REPRESENTATIONS:
                    if (
                        normalization_path == "FIXED_REFERENCE"
                        and representation == "CENTER_TRACKED_BODY"
                    ):
                        evaluation, sampling = membership_reference, membership_sampling
                    else:
                        evaluation, sampling = evaluate(
                            unit,
                            anchor_variant,
                            representation,
                            "GT_DERIVED_UNSIGNED_BODY",
                            normalization_path,
                            cache,
                            collect_sampling=True,
                        )
                    representation_evaluations[representation] = evaluation
                    sampling_rows.extend(sampling)
                    representation_rows.append(representation_summary_row(
                        unit,
                        anchor_variant,
                        representation,
                        normalization_path,
                        source_pair_set_hash,
                        pair_hash,
                        pairs,
                        evaluation,
                    ))
                    if anchor_variant == "smoothed_gt":
                        baseline_evaluations_for_visual[(normalization_path, representation)] = evaluation
                profile_baseline_evaluations[normalization_path] = representation_evaluations["CENTER_TRACKED_BODY"]
                pair_rows.extend(pair_comparison_rows(
                    unit,
                    anchor_variant,
                    normalization_path,
                    source_pair_set_hash,
                    pair_hash,
                    pairs,
                    representation_evaluations,
                ))

            if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE":
                axis_visual_evaluations: dict[tuple[str, str], Evaluation] = {}
                for normalization_path in NORMALIZATION_PATHS:
                    axis_evaluations: dict[str, Evaluation] = {}
                    for axis_rule in AXIS_RULES:
                        if axis_rule == "GT_DERIVED_UNSIGNED_BODY":
                            evaluation = profile_baseline_evaluations[normalization_path]
                            sampling = []
                        else:
                            evaluation, sampling = evaluate(
                                unit,
                                anchor_variant,
                                "CENTER_TRACKED_BODY",
                                axis_rule,
                                normalization_path,
                                cache,
                                collect_sampling=True,
                            )
                        axis_evaluations[axis_rule] = evaluation
                        sampling_rows.extend(sampling)
                        if anchor_variant == "smoothed_gt":
                            axis_visual_evaluations[(normalization_path, axis_rule)] = evaluation
                    pair_rows.extend(axis_placebo_rows(
                        unit,
                        anchor_variant,
                        normalization_path,
                        source_pair_set_hash,
                        pair_hash,
                        pairs,
                        axis_evaluations,
                    ))
                if anchor_variant == "smoothed_gt":
                    visual_rows.append(axis_placebo_visual(unit, axis_visual_evaluations, args.review_status))

            by_normalization_observations: dict[str, dict[str, dict[str, Any]]] = {}
            unit_profile_rows: list[dict[str, Any]] = []
            for normalization_path in NORMALIZATION_PATHS:
                generated_profiles, observations = run_parameter_profiles(
                    unit,
                    anchor_variant,
                    normalization_path,
                    source_pair_set_hash,
                    pair_hash,
                    pairs,
                    cache,
                    profile_baseline_evaluations[normalization_path],
                )
                profile_rows.extend(generated_profiles)
                unit_profile_rows.extend(generated_profiles)
                by_normalization_observations[normalization_path] = observations
            observability_rows.extend(
                observability_rows_for_unit(
                    unit,
                    anchor_variant,
                    source_pair_set_hash,
                    pair_hash,
                    pairs,
                    by_normalization_observations,
                )
            )

            if anchor_variant == "smoothed_gt":
                visual_required = (
                    unit["counterfactual_semantic_class"] != "TEMPORAL_NEGATIVE"
                    or unit["source_trajectory_segment_id"] == DEVELOPMENT_SEGMENT
                )
                if visual_required:
                    visual_rows.append(equal_support_visual(unit, baseline_evaluations_for_visual, args.review_status))
                if unit["counterfactual_semantic_class"] == "TRUE_VEHICLE_POSITIVE":
                    visual_rows.append(parameter_visual(unit, unit_profile_rows, args.review_status))
        del cache
        print(f"UNIT_DONE {unit_index}/{len(units)} {unit['research_unit_id']}", flush=True)

    observability_rows.extend(aggregate_observability_rows(observability_rows))
    print("PAIR_AND_FRAME_SENSITIVITY_START", flush=True)
    sensitivity_rows = pair_and_frame_sensitivity_rows(pair_rows)
    print(f"PAIR_AND_FRAME_SENSITIVITY_DONE rows={len(sensitivity_rows)}", flush=True)
    visual_rows.append(pair_count_visual(representation_rows, args.review_status))
    if len(visual_rows) != 20:
        raise AssertionError(f"visual artifact count changed: {len(visual_rows)}")
    if len({row["research_unit_id"] for row in visual_rows}) != 14:
        raise AssertionError("visual-review entity count must remain 14 including GLOBAL")

    for index, row in enumerate(unit_rows, start=1):
        row["review_status"] = args.review_status
    for index, row in enumerate(sampling_rows, start=1):
        row["sampling_row_id"] = f"S1L-OCS-SAMPLE-{index:08d}"
    for index, row in enumerate(pair_rows, start=1):
        row["pair_metric_row_id"] = f"S1L-OCS-PAIR-{index:09d}"
    for index, row in enumerate(profile_rows, start=1):
        row["profile_row_id"] = f"S1L-OCS-PROFILE-{index:08d}"
    for index, row in enumerate(observability_rows, start=1):
        row["observability_id"] = f"S1L-OCS-OBS-{index:07d}"
    for collection in (sampling_rows, representation_rows, pair_rows, sensitivity_rows, profile_rows, observability_rows):
        for row in collection:
            row["review_status"] = args.review_status

    write_dynamic_csv(UNIT_OUTPUT_PATH, unit_rows)
    write_dynamic_csv(SAMPLING_OUTPUT_PATH, sampling_rows)
    write_dynamic_csv(REPRESENTATION_OUTPUT_PATH, representation_rows)
    write_dynamic_csv(PAIR_OUTPUT_PATH, pair_rows)
    write_dynamic_csv(SENSITIVITY_OUTPUT_PATH, sensitivity_rows)
    write_dynamic_csv(PROFILE_OUTPUT_PATH, profile_rows)
    write_dynamic_csv(OBSERVABILITY_OUTPUT_PATH, observability_rows)
    write_dynamic_csv(VISUAL_OUTPUT_PATH, visual_rows)

    summary = {
        "work_name": "S1-L Semantic Correction and GT-Discovery Proxy Audit for the Optical-Conditioned Support Question",
        "config_hash": CONFIG_HASH,
        "review_status": args.review_status,
        "research_unit_count": len(unit_rows),
        "anchor_variants": list(ANCHOR_VARIANTS),
        "all_units_run_both_anchor_variants": True,
        "pair_membership_reference": CONFIG["pair_membership_reference"],
        "pair_projection_rule": CONFIG["pair_projection_rule"],
        "pair_sensitivity_modes": list(CONFIG["pair_sensitivity_modes"]),
        "normalization_failure_policy": CONFIG["normalization_failure_policy"],
        "body_oriented_window_attribution": CONFIG["body_oriented_window_attribution"],
        "parameter_observability_contract": CONFIG["parameter_observability_contract"],
        "scale_profile_contract": CONFIG["scale_profile_contract"],
        "temporal_test_contract": CONFIG["temporal_test_contract"],
        "orientation_estimator": CONFIG["orientation_estimator"],
        "topology_estimator": CONFIG["topology_estimator"],
        "canny_config": CONFIG["canny_config"],
        "structure_boundary_guard": CONFIG["structure_boundary_guard"],
        "optical_condition_execution_status": "NOT_EXECUTED_GT_DISCOVERY_PROXY_ONLY",
        "optical_conditioned_support_readiness": "NOT_EVALUATED_WITH_REAL_OPTICAL_INPUT_GT_PROXY_ONLY",
        "semantic_class_counts": dict(Counter(row["counterfactual_semantic_class"] for row in unit_rows)),
        "pv002_geometry_background_control_count": sum(
            row["counterfactual_semantic_class"] == "VEHICLE_CLASS_NEGATIVE"
            for row in unit_rows
        ),
        "background_spatial_control_group_count": len({
            row["background_spatial_control_group"]
            for row in unit_rows
            if row["counterfactual_semantic_class"] == "VEHICLE_CLASS_NEGATIVE"
            and row["background_spatial_control_group"]
        }),
        "background_parameter_envelope_group_count": len({
            row["background_parameter_envelope_group"]
            for row in unit_rows
            if row["counterfactual_semantic_class"] == "VEHICLE_CLASS_NEGATIVE"
            and row["background_parameter_envelope_group"]
        }),
        "background_cluster_scope": CONFIG["background_cluster_scope"],
        "sampling_row_count": len(sampling_rows),
        "representation_metric_row_count": len(representation_rows),
        "pair_metric_row_count": len(pair_rows),
        "leave_one_pair_out_row_count": sum(
            row["sensitivity_mode"] == "LEAVE_ONE_PAIR_OUT" for row in sensitivity_rows
        ),
        "leave_one_frame_out_row_count": sum(
            row["sensitivity_mode"] == "LEAVE_ONE_FRAME_OUT" for row in sensitivity_rows
        ),
        "pair_and_frame_sensitivity_row_count": len(sensitivity_rows),
        "parameter_profile_row_count": len(profile_rows),
        "observability_row_count": len(observability_rows),
        "visual_artifact_count": len(visual_rows),
        "latent_support_reconstruction_run": False,
        "s1d_allowed": False,
        "automatic_annotation_allowed": False,
        "unique_box_recovery": "NOT_EVALUATED_NOT_AUTHORIZED",
        "forbidden_methods_used": [],
        "outputs": {
            "research_units": str(UNIT_OUTPUT_PATH),
            "sampling_normalization": str(SAMPLING_OUTPUT_PATH),
            "representation_metrics": str(REPRESENTATION_OUTPUT_PATH),
            "pair_incremental_metrics": str(PAIR_OUTPUT_PATH),
            "pair_and_frame_sensitivity": str(SENSITIVITY_OUTPUT_PATH),
            "parameter_profiles": str(PROFILE_OUTPUT_PATH),
            "parameter_observability": str(OBSERVABILITY_OUTPUT_PATH),
            "visual_manifest": str(VISUAL_OUTPUT_PATH),
            "temporary_visuals": str(VISUAL_ROOT),
        },
    }
    write_json(SUMMARY_PATH, summary)
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(
            "2026-07-16 OPTICAL_CONDITIONED_OBSERVABILITY_RUN\n"
            f"review_status={args.review_status}\n"
            f"research_units={len(unit_rows)}\n"
            f"sampling_rows={len(sampling_rows)}\n"
            f"representation_rows={len(representation_rows)}\n"
            f"pair_rows={len(pair_rows)}\n"
            f"pair_and_frame_sensitivity_rows={len(sensitivity_rows)}\n"
            f"profile_rows={len(profile_rows)}\n"
            f"observability_rows={len(observability_rows)}\n"
            f"visual_artifacts={len(visual_rows)}\n"
            "latent_support_reconstruction_run=false\n"
            "s1d_allowed=false\n"
            "automatic_annotation_allowed=false\n"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
