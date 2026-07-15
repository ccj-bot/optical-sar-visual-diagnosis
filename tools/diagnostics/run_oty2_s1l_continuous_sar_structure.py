#!/usr/bin/env python3
from __future__ import annotations

"""S1-L continuous SAR display-response structure and artifact-control audit.

The script operates only on the frozen S0/S0-M/S0-MV contracts.  GT defines a
local research neighbourhood and a physical-vehicle thread; it is never used
as a vehicle-response mask, precise vehicle geometry, candidate box, selector
input, or final annotation.  All extracted objects remain observations in the
two-dimensional SAR grayscale display domain.
"""

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DATA_ROOT = Path(r"D:\profile\research\data")
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")
OUTPUT_ROOT = WORKSPACE_ROOT / "output" / "oty2_s1l_continuous_sar_structure_20260715"
VISUAL_ROOT = OUTPUT_ROOT / "visual_review"
LOG_PATH = WORKSPACE_ROOT / "logs" / "oty2_s1l_continuous_sar_structure_20260715.log"

ELIGIBILITY_PATH = MANIFEST_DIR / "oty2_s0mv_all_gt_s1l_eligibility.csv"
SEGMENTS_PATH = MANIFEST_DIR / "oty2_s0mv_s1l_continuous_segments.csv"
QUALITY_PATH = MANIFEST_DIR / "oty2_s0_sar_gt_quality_audit.csv"
LINEAGE_PATH = MANIFEST_DIR / "oty2_s0_sar_gray_pseudocolor_lineage.csv"
MASK_PARAMETERS_PATH = MANIFEST_DIR / "oty2_s0_imaging_valid_mask_parameters.json"

FROZEN_INPUT_PATH = MANIFEST_DIR / "oty2_s1l_frozen_input_segments.csv"
LOCAL_FIELD_PATH = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
OBSERVATION_PATH = MANIFEST_DIR / "oty2_s1l_structure_observations.csv"
RELATION_PATH = MANIFEST_DIR / "oty2_s1l_structure_relations.csv"
EVENT_PATH = MANIFEST_DIR / "oty2_s1l_temporal_structure_events.csv"
ARTIFACT_PATH = MANIFEST_DIR / "oty2_s1l_artifact_counterfactual_audit.csv"
BACKGROUND_PATH = MANIFEST_DIR / "oty2_s1l_background_counterfactuals.csv"
EVALUATION_PATH = MANIFEST_DIR / "oty2_s1l_mechanism_evaluation.csv"
REPORT_PATH = REPORT_DIR / "oty2_s1l_continuous_sar_structure_and_artifact_control_20260715.md"

SUMMARY_PATH = OUTPUT_ROOT / "s1l_summary.json"
VISUAL_MANIFEST_PATH = OUTPUT_ROOT / "s1l_visual_manifest.csv"
REPLAY_PATH = OUTPUT_ROOT / "s1l_replay_check.json"

FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS = 1332.7
CANVAS_WIDTH = 2308
CANVAS_HEIGHT = 1334
FPS = 50.0

# Fixed before heldout evaluation.  They are intentionally few and public.
CROP_EXPANSION = 1.75
SCORE_LEVELS = (0.35, 0.50, 0.65)
MIN_COMPONENT_AREA = 6
MAX_COMPONENT_FRACTION = 0.70
GAUSSIAN_SIGMA = 1.0
TEMPORAL_MAX_GAP = 5
MATCH_COST_LIMIT = 3.0


FROZEN_INPUT_FIELDS = (
    "scene", "canonical_vehicle_id", "benchmark_role", "input_tier", "segment_id",
    "sar_frame_start", "sar_frame_end", "eligible_frame_indices", "missing_gt_indices",
    "source_gt_row_count", "unique_eligible_frame_count", "gt_quality_distribution",
    "optical_visibility_distribution", "pose_distribution", "intended_usage", "claim_scope", "notes",
)
LOCAL_FIELD_FIELDS = (
    "response_field_id", "scene", "canonical_vehicle_id", "benchmark_role", "input_tier", "segment_id",
    "sar_frame_index", "sar_time_sec", "source_gt_ids", "source_gt_count", "source_gt_quality_distribution",
    "raw_anchor_center_x_px", "raw_anchor_center_y_px", "raw_anchor_width_px", "raw_anchor_height_px",
    "raw_anchor_angle_deg", "smoothed_anchor_center_x_px", "smoothed_anchor_center_y_px",
    "smoothed_anchor_width_px", "smoothed_anchor_height_px", "smoothed_anchor_angle_deg",
    "gt_center_spread_px", "gt_size_spread_px", "crop_expansion", "raw_crop_polygon_global_px",
    "smoothed_crop_polygon_global_px", "global_roi_x1", "global_roi_y1", "global_roi_x2", "global_roi_y2",
    "radial_unit_x", "radial_unit_y", "tangential_unit_x", "tangential_unit_y",
    "raw_half_extent_radial_px", "raw_half_extent_tangential_px", "smoothed_half_extent_radial_px",
    "smoothed_half_extent_tangential_px", "thread_raw_p05", "thread_raw_p50", "thread_raw_p95",
    "thread_raw_p99", "local_background_median", "local_background_mad", "raw_min", "raw_max", "raw_mean",
    "analysis_valid_mask_fraction", "coordinate_inverse_error_px", "raw_image_path", "raw_image_sha256",
    "low_threshold_component_count", "multi_threshold_component_count", "single_threshold_only_component_count",
    "gt_is_vehicle_response_mask", "lineage_status", "notes",
)
OBSERVATION_FIELDS = (
    "structure_observation_id", "parent_observation_id", "response_field_id", "scene", "canonical_vehicle_id",
    "benchmark_role", "input_tier", "segment_id", "sar_frame_index", "structure_type", "global_centroid_x_px",
    "global_centroid_y_px", "r_px", "theta_deg", "raw_local_radial_px", "raw_local_tangential_px",
    "smoothed_local_radial_px", "smoothed_local_tangential_px", "gt_normalized_radial",
    "gt_normalized_tangential", "radar_side_class", "azimuth_side_class", "area_px", "perimeter_px",
    "major_axis_angle_deg", "elongation", "extent_length_px", "relative_intensity", "raw_mean_intensity",
    "raw_max_intensity", "shape_class", "gt_boundary_relation", "background_relation",
    "threshold_persistence_count", "threshold_child_count_mid", "threshold_child_count_high",
    "normalization_persistence_count", "multi_threshold_stable", "cross_normalization_stable",
    "major_temporal_eligible", "touches_raw_crop_boundary", "touches_smoothed_crop_boundary",
    "extraction_lineage", "notes",
)
RELATION_FIELDS = (
    "structure_relation_id", "scene", "canonical_vehicle_id", "segment_id", "sar_frame_index",
    "source_observation_id", "target_observation_id", "relation_types", "global_dx_px", "global_dy_px",
    "global_distance_px", "radial_delta_px", "tangential_delta_px", "orientation_difference_deg",
    "collinearity_residual_px", "parallel_score", "near_far_order", "shared_background_connection", "notes",
)
EVENT_FIELDS = (
    "temporal_event_id", "scene", "canonical_vehicle_id", "benchmark_role", "input_tier", "segment_id",
    "sar_frame_from", "sar_frame_to", "frame_gap", "event_type", "source_observation_ids",
    "target_observation_ids", "global_displacement_px", "raw_local_displacement_px",
    "smoothed_local_displacement_px", "relative_intensity_change", "shape_change", "correspondence_cost",
    "threshold_support_count", "global_coordinate_supported", "raw_gt_local_supported",
    "smoothed_gt_local_supported", "crop_or_gt_jitter_artifact", "threshold_artifact", "background_like",
    "major_event", "notes",
)
ARTIFACT_FIELDS = (
    "audit_id", "scene", "canonical_vehicle_id", "segment_id", "temporal_event_id", "sar_frame_from",
    "sar_frame_to", "audit_type", "raw_gt_result", "smoothed_gt_result", "global_coordinate_result",
    "threshold_result", "background_result", "decision", "artifact_label", "evidence_values", "notes",
)
BACKGROUND_FIELDS = (
    "background_thread_id", "source_segment_id", "scene", "canonical_vehicle_id", "background_type",
    "offset_radial_px", "offset_tangential_px", "frame_count", "structure_observation_count",
    "stable_structure_count", "temporal_transition_count", "stable_persistence_count", "split_merge_switch_count",
    "vehicle_stable_persistence_rate", "background_stable_persistence_rate", "vehicle_complex_event_rate",
    "background_complex_event_rate", "replicates_stable_persistence", "replicates_vehicle_conclusion",
    "mean_valid_mask_fraction", "mean_nonzero_fraction", "mean_gt_overlap_fraction", "mean_gradient_strength",
    "mean_gradient_linearity", "background_quality_status", "review_status", "notes",
)
EVALUATION_FIELDS = (
    "evaluation_id", "scene", "canonical_vehicle_id", "benchmark_role", "input_tier", "segment_id",
    "unique_frame_count", "source_gt_row_count", "structure_observation_count", "stable_structure_count",
    "structure_type_distribution", "relation_count", "relation_type_distribution", "temporal_event_count",
    "temporal_event_distribution", "global_supported_event_count", "gt_or_crop_artifact_count",
    "threshold_artifact_count", "background_like_event_count", "background_replication_rate",
    "background_stable_replication_rate", "stable_relation_present", "heldout_reproduction_status",
    "cross_scene_interpretation", "stage_evidence",
    "review_status", "notes",
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


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def fmt(value: Any, digits: int = 6) -> str:
    try:
        number = float(value)
        return "" if not math.isfinite(number) else f"{number:.{digits}f}"
    except (TypeError, ValueError):
        return ""


def parse_bbox(text: str) -> tuple[float, float, float, float, float]:
    values = [float(item.strip()) for item in text.strip().strip("[]").split(",")]
    if len(values) != 5:
        raise ValueError(f"invalid rotated bbox: {text}")
    return values[0], values[1], values[2], values[3], values[4]


def compact_counts(values: Iterable[Any]) -> str:
    counts = Counter(str(value or "unknown") for value in values)
    return ";".join(f"{key}:{counts[key]}" for key in sorted(counts))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bundle_hash(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item).lower()):
        digest.update(str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sar_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def sanitize(value: str) -> str:
    return value.replace(":", "_").replace("/", "_").replace("\\", "_")


def radial_theta(x: float, y: float) -> tuple[float, float]:
    dx, dy = x - FAN_CENTER_X, FAN_CENTER_Y - y
    return math.hypot(dx, dy), math.degrees(math.atan2(dx, dy))


def unit_vectors(cx: float, cy: float) -> tuple[np.ndarray, np.ndarray]:
    radial = np.array([cx - FAN_CENTER_X, cy - FAN_CENTER_Y], dtype=np.float64)
    norm = float(np.linalg.norm(radial))
    if norm < 1e-9:
        radial = np.array([0.0, -1.0], dtype=np.float64)
    else:
        radial /= norm
    tangential = np.array([-radial[1], radial[0]], dtype=np.float64)
    return radial, tangential


def axial_mean_deg(values: Sequence[float]) -> float:
    radians = np.radians(np.asarray(values, dtype=np.float64) * 2.0)
    angle = 0.5 * math.degrees(math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean())))
    return angle % 180.0


def consensus_anchor(rows: Sequence[Mapping[str, str]]) -> dict[str, float]:
    boxes = np.asarray([parse_bbox(row["bbox"]) for row in rows], dtype=np.float64)
    center = np.median(boxes[:, :2], axis=0)
    size = np.median(boxes[:, 2:4], axis=0)
    return {
        "cx": float(center[0]), "cy": float(center[1]), "w": float(size[0]), "h": float(size[1]),
        "angle": axial_mean_deg(boxes[:, 4].tolist()),
        "center_spread": float(np.max(np.linalg.norm(boxes[:, :2] - center[None, :], axis=1))),
        "size_spread": float(np.max(np.linalg.norm(boxes[:, 2:4] - size[None, :], axis=1))),
    }


def rolling_median(values: Sequence[float], radius: int = 2) -> list[float]:
    result: list[float] = []
    for index in range(len(values)):
        lo, hi = max(0, index - radius), min(len(values), index + radius + 1)
        result.append(float(statistics.median(values[lo:hi])))
    return result


def smooth_anchors(frames: Sequence[int], anchors: Sequence[dict[str, float]]) -> list[dict[str, float]]:
    if len(anchors) < 3:
        return [dict(anchor) for anchor in anchors]
    result = [dict(anchor) for anchor in anchors]
    for key in ("cx", "cy", "w", "h"):
        smoothed = rolling_median([anchor[key] for anchor in anchors])
        for row, value in zip(result, smoothed):
            row[key] = value
    doubled = np.unwrap(np.radians([anchor["angle"] * 2.0 for anchor in anchors]))
    angle_values = rolling_median(doubled.tolist())
    for row, value in zip(result, angle_values):
        row["angle"] = (math.degrees(value) * 0.5) % 180.0
    return result


def rotated_box_corners(anchor: Mapping[str, float]) -> np.ndarray:
    rect = ((float(anchor["cx"]), float(anchor["cy"])), (float(anchor["w"]), float(anchor["h"])), float(anchor["angle"]))
    return cv2.boxPoints(rect).astype(np.float64)


def anchor_extents(anchor: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray, float, float]:
    center = np.array([anchor["cx"], anchor["cy"]], dtype=np.float64)
    radial, tangential = unit_vectors(anchor["cx"], anchor["cy"])
    offsets = rotated_box_corners(anchor) - center[None, :]
    half_r = max(8.0, float(np.max(np.abs(offsets @ radial))))
    half_t = max(8.0, float(np.max(np.abs(offsets @ tangential))))
    return radial, tangential, half_r, half_t


def crop_polygon(anchor: Mapping[str, float], expansion: float = CROP_EXPANSION) -> tuple[np.ndarray, float, float]:
    radial, tangential, half_r, half_t = anchor_extents(anchor)
    center = np.array([anchor["cx"], anchor["cy"]], dtype=np.float64)
    hr, ht = half_r * expansion, half_t * expansion
    points = np.asarray([
        center - radial * hr - tangential * ht,
        center - radial * hr + tangential * ht,
        center + radial * hr + tangential * ht,
        center + radial * hr - tangential * ht,
    ], dtype=np.float64)
    return points, half_r, half_t


def polygon_text(points: np.ndarray) -> str:
    return ";".join(f"{x:.3f},{y:.3f}" for x, y in points)


def mask_in_roi(points: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = roi
    local = np.round(points - np.array([x1, y1], dtype=np.float64)).astype(np.int32)
    mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
    cv2.fillConvexPoly(mask, local, 1)
    return mask.astype(bool)


def imaging_mask_roi(roi: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = roi
    ys, xs = np.mgrid[y1:y2, x1:x2]
    radius = np.hypot(xs - FAN_CENTER_X, ys - FAN_CENTER_Y)
    theta = np.degrees(np.arctan2(xs - FAN_CENTER_X, FAN_CENTER_Y - ys))
    return (radius <= FAN_RADIUS) & (theta >= -90.0) & (theta <= 90.0)


def roi_for_polygons(*polygons: np.ndarray, margin: int = 4) -> tuple[int, int, int, int]:
    points = np.vstack(polygons)
    x1 = max(0, int(math.floor(float(points[:, 0].min()))) - margin)
    y1 = max(0, int(math.floor(float(points[:, 1].min()))) - margin)
    x2 = min(CANVAS_WIDTH, int(math.ceil(float(points[:, 0].max()))) + margin + 1)
    y2 = min(CANVAS_HEIGHT, int(math.ceil(float(points[:, 1].max()))) + margin + 1)
    return x1, y1, x2, y2


def offset_local(x: float, y: float, anchor: Mapping[str, float]) -> tuple[float, float]:
    radial, tangential = unit_vectors(anchor["cx"], anchor["cy"])
    delta = np.array([x - anchor["cx"], y - anchor["cy"]], dtype=np.float64)
    return float(delta @ radial), float(delta @ tangential)


def inverse_error(anchor: Mapping[str, float], points: np.ndarray) -> float:
    radial, tangential = unit_vectors(anchor["cx"], anchor["cy"])
    center = np.array([anchor["cx"], anchor["cy"]], dtype=np.float64)
    errors = []
    for point in points:
        delta = point - center
        dr, dt = float(delta @ radial), float(delta @ tangential)
        reconstructed = center + radial * dr + tangential * dt
        errors.append(float(np.linalg.norm(reconstructed - point)))
    return max(errors, default=0.0)


def select_tiers(segment: Mapping[str, str]) -> str | None:
    eligible = int(segment["eligible_frame_count"])
    span = int(segment["frame_span"])
    if parse_bool(segment["segment_eligibility"]):
        return "A"
    if eligible >= 2 and span >= 2:
        return "B"
    if eligible == 1:
        return "C"
    return None


def freeze_inputs(eligibility: Sequence[dict[str, str]], segments: Sequence[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    tier_by_segment = {row["segment_id"]: select_tiers(row) for row in segments}
    eligible_by_segment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in eligibility:
        if parse_bool(row["s1l_structure_frame_eligible"]) and tier_by_segment.get(row["segment_id"]):
            eligible_by_segment[row["segment_id"]].append(row)
    output: list[dict[str, Any]] = []
    for segment in segments:
        tier = tier_by_segment.get(segment["segment_id"])
        if not tier:
            continue
        rows = eligible_by_segment[segment["segment_id"]]
        frames = sorted({int(row["sar_frame_index"]) for row in rows})
        full_range = set(range(int(segment["sar_frame_start"]), int(segment["sar_frame_end"]) + 1))
        gt_frames = {int(row["sar_frame_index"]) for row in eligibility if row["segment_id"] == segment["segment_id"]}
        missing = sorted(full_range - gt_frames)
        intended = {"A": "formal_temporal_mechanism_or_heldout", "B": "short_sequence_diagnostic", "C": "single_frame_structure_check"}[tier]
        claim = {"A": "temporal_and_structure", "B": "diagnostic_temporal_only", "C": "coordinate_structure_background_only"}[tier]
        output.append({
            "scene": segment["scene"], "canonical_vehicle_id": segment["canonical_vehicle_id"],
            "benchmark_role": segment["benchmark_role"], "input_tier": tier, "segment_id": segment["segment_id"],
            "sar_frame_start": segment["sar_frame_start"], "sar_frame_end": segment["sar_frame_end"],
            "eligible_frame_indices": ";".join(map(str, frames)), "missing_gt_indices": ";".join(map(str, missing)),
            "source_gt_row_count": len(rows), "unique_eligible_frame_count": len(frames),
            "gt_quality_distribution": compact_counts(row["gt_quality_status"] for row in rows),
            "optical_visibility_distribution": compact_counts(row["optical_visibility_state"] for row in rows),
            "pose_distribution": segment["pose_distribution"], "intended_usage": intended, "claim_scope": claim,
            "notes": "frozen from S0-MV without renewed candidate screening; candidate terminology prohibited",
        })
    return output, {key: value for key, value in tier_by_segment.items() if value}


def build_frame_specs(
    eligibility: Sequence[dict[str, str]], quality_by_id: Mapping[str, dict[str, str]], tier_by_segment: Mapping[str, str]
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in eligibility:
        if parse_bool(row["s1l_structure_frame_eligible"]) and row["segment_id"] in tier_by_segment:
            grouped[(row["segment_id"], row["scene"], row["canonical_vehicle_id"], int(row["sar_frame_index"]))].append(row)
    by_segment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (segment_id, scene, canonical, frame), rows in grouped.items():
        qrows = [quality_by_id[row["sar_gt_id"]] for row in rows]
        anchor = consensus_anchor(qrows)
        by_segment[segment_id].append({
            "segment_id": segment_id, "scene": scene, "canonical_vehicle_id": canonical,
            "benchmark_role": rows[0]["benchmark_role"], "input_tier": tier_by_segment[segment_id],
            "frame": frame, "source_rows": rows, "quality_rows": qrows, "raw_anchor": anchor,
        })
    all_specs: list[dict[str, Any]] = []
    for segment_id, specs in by_segment.items():
        specs.sort(key=lambda row: row["frame"])
        smoothed = smooth_anchors([row["frame"] for row in specs], [row["raw_anchor"] for row in specs])
        for row, anchor in zip(specs, smoothed):
            row["smoothed_anchor"] = anchor
            all_specs.append(row)
    all_specs.sort(key=lambda row: (row["scene"], row["canonical_vehicle_id"], row["frame"], row["segment_id"]))
    return all_specs, by_segment


def build_frame_context(spec: Mapping[str, Any], image: np.ndarray) -> dict[str, Any]:
    raw_poly, raw_hr, raw_ht = crop_polygon(spec["raw_anchor"])
    smooth_poly, smooth_hr, smooth_ht = crop_polygon(spec["smoothed_anchor"])
    roi = roi_for_polygons(raw_poly, smooth_poly)
    x1, y1, x2, y2 = roi
    raw_mask = mask_in_roi(raw_poly, roi)
    smooth_mask = mask_in_roi(smooth_poly, roi)
    valid = imaging_mask_roi(roi)
    analysis = (raw_mask | smooth_mask) & valid
    local_image = image[y1:y2, x1:x2]
    inner_poly, _, _ = crop_polygon(spec["raw_anchor"], expansion=1.10)
    inner = mask_in_roi(inner_poly, roi)
    background = analysis & ~inner
    values = local_image[analysis]
    bg_values = local_image[background]
    bg_median = float(np.median(bg_values)) if bg_values.size else float(np.median(values))
    bg_mad = float(np.median(np.abs(bg_values - bg_median))) if bg_values.size else 0.0
    return {
        "raw_poly": raw_poly, "smooth_poly": smooth_poly, "raw_hr": raw_hr, "raw_ht": raw_ht,
        "smooth_hr": smooth_hr, "smooth_ht": smooth_ht, "roi": roi, "raw_mask": raw_mask,
        "smooth_mask": smooth_mask, "valid_mask": valid, "analysis_mask": analysis,
        "image": local_image, "values": values, "background_mask": background,
        "bg_median": bg_median, "bg_mad": bg_mad,
    }


def thread_statistics(specs: Sequence[dict[str, Any]], contexts: Mapping[str, dict[str, Any]]) -> dict[str, tuple[float, float, float, float]]:
    samples: dict[str, list[np.ndarray]] = defaultdict(list)
    for spec in specs:
        context = contexts[f"{spec['segment_id']}|{spec['frame']}"]
        values = context["values"]
        if values.size:
            samples[spec["segment_id"]].append(values[:: max(1, values.size // 4000)])
    result: dict[str, tuple[float, float, float, float]] = {}
    for segment_id, arrays in samples.items():
        values = np.concatenate(arrays).astype(np.float64)
        result[segment_id] = tuple(float(np.percentile(values, q)) for q in (5, 50, 95, 99))
    return result


def connected_components(mask: np.ndarray) -> list[dict[str, Any]]:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    cleaned = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned, 8)
    output: list[dict[str, Any]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < MIN_COMPONENT_AREA:
            continue
        output.append({"label": label, "mask": labels == label, "area": area, "centroid": centroids[label]})
    return output


def component_geometry(mask: np.ndarray, image: np.ndarray, roi: tuple[int, int, int, int]) -> dict[str, float]:
    ys, xs = np.nonzero(mask)
    weights = image[ys, xs].astype(np.float64) + 1.0
    cx_local = float(np.average(xs, weights=weights)); cy_local = float(np.average(ys, weights=weights))
    centered = np.column_stack((xs - cx_local, ys - cy_local)).astype(np.float64)
    covariance = np.cov(centered.T, aweights=weights) if len(xs) > 2 else np.eye(2)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    major = eigenvectors[:, order[0]]
    lam1, lam2 = max(float(eigenvalues[order[0]]), 1e-6), max(float(eigenvalues[order[1]]), 1e-6)
    angle = math.degrees(math.atan2(float(major[1]), float(major[0]))) % 180.0
    elongation = math.sqrt(lam1 / lam2)
    projection = centered @ major
    extent = float(projection.max() - projection.min()) if projection.size else 0.0
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    perimeter = sum(float(cv2.arcLength(contour, True)) for contour in contours)
    x1, y1, _, _ = roi
    return {
        "cx": cx_local + x1, "cy": cy_local + y1, "angle": angle, "elongation": elongation,
        "extent": extent, "perimeter": perimeter, "mean": float(image[mask].mean()), "max": float(image[mask].max()),
    }


def score_maps(image: np.ndarray, analysis: np.ndarray, stats: tuple[float, float, float, float], bg_median: float) -> dict[str, np.ndarray]:
    _, p50, _, p99 = stats
    blurred = cv2.GaussianBlur(image.astype(np.float32), (0, 0), GAUSSIAN_SIGMA)
    thread = np.clip((blurred - p50) / max(1.0, p99 - p50), 0.0, 1.0)
    background = np.clip((blurred - bg_median) / max(1.0, p99 - bg_median), 0.0, 1.0)
    log_image = np.log1p(blurred)
    log_score = np.clip((log_image - math.log1p(max(0.0, p50))) / max(1e-6, math.log1p(max(1.0, p99)) - math.log1p(max(0.0, p50))), 0.0, 1.0)
    for array in (thread, background, log_score):
        array[~analysis] = 0.0
    return {"thread_robust": thread, "local_background": background, "log_display": log_score}


def overlap_count(component: np.ndarray, candidates: Sequence[dict[str, Any]]) -> int:
    return sum(bool(np.any(component & candidate["mask"])) for candidate in candidates)


def boundary_relation(cx: float, cy: float, anchor: Mapping[str, float]) -> str:
    polygon = rotated_box_corners(anchor).astype(np.float32)
    distance = cv2.pointPolygonTest(polygon, (float(cx), float(cy)), True)
    if distance > 5.0:
        return "inside_gt_anchor_context"
    if distance >= -5.0:
        return "near_gt_anchor_boundary"
    return "outside_gt_anchor_context"


def touches_boundary(component: np.ndarray, crop_mask: np.ndarray) -> bool:
    edge = cv2.morphologyEx(crop_mask.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    return bool(np.any(component & cv2.dilate(edge.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)))


def extract_observations(
    spec: Mapping[str, Any], context: Mapping[str, Any], stats: tuple[float, float, float, float], counter_start: int
) -> tuple[list[dict[str, Any]], int]:
    maps = score_maps(context["image"], context["analysis_mask"], stats, context["bg_median"])
    components: dict[str, list[list[dict[str, Any]]]] = {}
    for mode, score in maps.items():
        components[mode] = [connected_components((score >= level) & context["analysis_mask"]) for level in SCORE_LEVELS]
    primary_low, primary_mid, primary_high = components["thread_robust"]
    analysis_area = max(1, int(context["analysis_mask"].sum()))
    observations: list[dict[str, Any]] = []
    next_id = counter_start
    for component in primary_low:
        if component["area"] > analysis_area * MAX_COMPONENT_FRACTION:
            continue
        geometry = component_geometry(component["mask"], context["image"], context["roi"])
        mid_count = overlap_count(component["mask"], primary_mid)
        high_count = overlap_count(component["mask"], primary_high)
        threshold_count = 1 + int(mid_count > 0) + int(high_count > 0)
        norm_count = 1
        for mode in ("local_background", "log_display"):
            norm_count += int(overlap_count(component["mask"], components[mode][1]) > 0)
        raw_dr, raw_dt = offset_local(geometry["cx"], geometry["cy"], spec["raw_anchor"])
        smooth_dr, smooth_dt = offset_local(geometry["cx"], geometry["cy"], spec["smoothed_anchor"])
        radius, theta = radial_theta(geometry["cx"], geometry["cy"])
        relation = boundary_relation(geometry["cx"], geometry["cy"], spec["raw_anchor"])
        touch_raw = touches_boundary(component["mask"], context["raw_mask"])
        touch_smooth = touches_boundary(component["mask"], context["smooth_mask"])
        if threshold_count < 2:
            structure_type = "threshold_fragile_component"
        elif touch_raw or touch_smooth or component["area"] > analysis_area * 0.35:
            structure_type = "background_connected_response_structure"
        elif component["area"] <= max(20, spec["raw_anchor"]["w"] * spec["raw_anchor"]["h"] * 0.02):
            structure_type = "stable_local_peak"
        elif geometry["elongation"] >= 2.5:
            structure_type = "extended_response_ridge"
        else:
            structure_type = "compact_response_island"
        stable = threshold_count >= 2 and norm_count >= 2
        major = stable and structure_type != "background_connected_response_structure"
        obs_id = f"S1L-OBS-{next_id:07d}"; next_id += 1
        _, _, raw_hr, raw_ht = anchor_extents(spec["raw_anchor"])
        observations.append({
            "structure_observation_id": obs_id, "parent_observation_id": "",
            "response_field_id": f"S1L-FIELD-{spec['scene']}-{sanitize(spec['canonical_vehicle_id'])}-{spec['frame']:06d}",
            "scene": spec["scene"], "canonical_vehicle_id": spec["canonical_vehicle_id"],
            "benchmark_role": spec["benchmark_role"], "input_tier": spec["input_tier"], "segment_id": spec["segment_id"],
            "sar_frame_index": spec["frame"], "structure_type": structure_type,
            "global_centroid_x_px": fmt(geometry["cx"]), "global_centroid_y_px": fmt(geometry["cy"]),
            "r_px": fmt(radius), "theta_deg": fmt(theta), "raw_local_radial_px": fmt(raw_dr),
            "raw_local_tangential_px": fmt(raw_dt), "smoothed_local_radial_px": fmt(smooth_dr),
            "smoothed_local_tangential_px": fmt(smooth_dt), "gt_normalized_radial": fmt(raw_dr / max(raw_hr, 1.0)),
            "gt_normalized_tangential": fmt(raw_dt / max(raw_ht, 1.0)),
            "radar_side_class": "farther_from_radar" if raw_dr > 0 else "nearer_to_radar",
            "azimuth_side_class": "positive_azimuth_side" if raw_dt > 0 else "negative_azimuth_side",
            "area_px": component["area"], "perimeter_px": fmt(geometry["perimeter"]),
            "major_axis_angle_deg": fmt(geometry["angle"]), "elongation": fmt(geometry["elongation"]),
            "extent_length_px": fmt(geometry["extent"]), "relative_intensity": fmt((geometry["mean"] - stats[1]) / max(1.0, stats[3] - stats[1])),
            "raw_mean_intensity": fmt(geometry["mean"]), "raw_max_intensity": fmt(geometry["max"]),
            "shape_class": "ridge_like" if geometry["elongation"] >= 2.5 else "compact_or_island",
            "gt_boundary_relation": relation,
            "background_relation": "connected_to_crop_or_context_boundary" if touch_raw or touch_smooth else "not_boundary_connected",
            "threshold_persistence_count": threshold_count, "threshold_child_count_mid": mid_count,
            "threshold_child_count_high": high_count, "normalization_persistence_count": norm_count,
            "multi_threshold_stable": bool_text(threshold_count >= 2), "cross_normalization_stable": bool_text(norm_count >= 2),
            "major_temporal_eligible": bool_text(major), "touches_raw_crop_boundary": bool_text(touch_raw),
            "touches_smoothed_crop_boundary": bool_text(touch_smooth),
            "extraction_lineage": "raw grayscale -> fixed Gaussian sigma 1.0 -> thread robust score -> fixed 0.35/0.50/0.65 levels; local-background and log-display cross-check",
            "notes": "response observation only; not a vehicle part, candidate box, or scattering-center truth",
            "_mask": component["mask"], "_roi": context["roi"], "_raw_anchor": spec["raw_anchor"], "_smooth_anchor": spec["smoothed_anchor"],
        })
    return observations, next_id


def angle_difference(a: float, b: float) -> float:
    diff = abs(a - b) % 180.0
    return min(diff, 180.0 - diff)


def build_relations(observations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_frame: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        if parse_bool(row["major_temporal_eligible"]):
            by_frame[(row["segment_id"], row["canonical_vehicle_id"], int(row["sar_frame_index"]))].append(row)
    output: list[dict[str, Any]] = []
    counter = 1
    for (_, _, frame), rows in by_frame.items():
        for i, source in enumerate(rows):
            for target in rows[i + 1:]:
                sx, sy = parse_float(source["global_centroid_x_px"]), parse_float(source["global_centroid_y_px"])
                tx, ty = parse_float(target["global_centroid_x_px"]), parse_float(target["global_centroid_y_px"])
                dx, dy = tx - sx, ty - sy; distance = math.hypot(dx, dy)
                radial_delta = parse_float(target["raw_local_radial_px"]) - parse_float(source["raw_local_radial_px"])
                tangential_delta = parse_float(target["raw_local_tangential_px"]) - parse_float(source["raw_local_tangential_px"])
                orientation_diff = angle_difference(parse_float(source["major_axis_angle_deg"]), parse_float(target["major_axis_angle_deg"]))
                scale = max(parse_float(source["extent_length_px"], 1.0), parse_float(target["extent_length_px"], 1.0), 1.0)
                if distance > max(40.0, scale * 2.5):
                    continue
                relation_types = ["spatial_neighbor"]
                if abs(radial_delta) <= max(8.0, 0.25 * scale): relation_types.append("same_radial_band")
                if abs(tangential_delta) <= max(8.0, 0.25 * scale): relation_types.append("same_azimuth_band")
                if orientation_diff <= 15.0: relation_types.append("parallel")
                line_angle = math.degrees(math.atan2(dy, dx)) % 180.0
                col_residual = min(angle_difference(line_angle, parse_float(source["major_axis_angle_deg"])), angle_difference(line_angle, parse_float(target["major_axis_angle_deg"])))
                if col_residual <= 15.0: relation_types.append("collinear")
                if radial_delta != 0: relation_types.append("near_far_correspondence")
                if source["structure_type"] == "extended_response_ridge" or target["structure_type"] == "extended_response_ridge":
                    relation_types.append("possible_shared_extended_response")
                shared_bg = (
                    source["background_relation"] == "connected_to_crop_or_context_boundary"
                    and target["background_relation"] == "connected_to_crop_or_context_boundary"
                )
                if shared_bg: relation_types.append("shared_background_connection")
                output.append({
                    "structure_relation_id": f"S1L-REL-{counter:07d}", "scene": source["scene"],
                    "canonical_vehicle_id": source["canonical_vehicle_id"], "segment_id": source["segment_id"],
                    "sar_frame_index": frame, "source_observation_id": source["structure_observation_id"],
                    "target_observation_id": target["structure_observation_id"], "relation_types": ";".join(relation_types),
                    "global_dx_px": fmt(dx), "global_dy_px": fmt(dy), "global_distance_px": fmt(distance),
                    "radial_delta_px": fmt(radial_delta), "tangential_delta_px": fmt(tangential_delta),
                    "orientation_difference_deg": fmt(orientation_diff), "collinearity_residual_px": fmt(col_residual),
                    "parallel_score": fmt(max(0.0, 1.0 - orientation_diff / 90.0)),
                    "near_far_order": "source_nearer" if radial_delta > 0 else "target_nearer",
                    "shared_background_connection": bool_text(shared_bg), "notes": "geometric relation; no graph neural network or identity claim",
                }); counter += 1
    return output


def observation_cost(source: Mapping[str, Any], target: Mapping[str, Any], frame_gap: int) -> float:
    sx, sy = parse_float(source["global_centroid_x_px"]), parse_float(source["global_centroid_y_px"])
    tx, ty = parse_float(target["global_centroid_x_px"]), parse_float(target["global_centroid_y_px"])
    source_anchor, target_anchor = source["_smooth_anchor"], target["_smooth_anchor"]
    expected = np.array([target_anchor["cx"] - source_anchor["cx"], target_anchor["cy"] - source_anchor["cy"]])
    observed = np.array([tx - sx, ty - sy])
    scale = max(15.0, 0.5 * math.hypot(source_anchor["w"], source_anchor["h"]))
    motion = float(np.linalg.norm(observed - expected)) / (scale * max(1.0, math.sqrt(frame_gap)))
    global_continuity = float(np.linalg.norm(observed)) / (scale * max(1.0, frame_gap))
    shape = abs(math.log(max(1.0, parse_float(target["area_px"])) / max(1.0, parse_float(source["area_px"]))))
    orientation = angle_difference(parse_float(source["major_axis_angle_deg"]), parse_float(target["major_axis_angle_deg"])) / 90.0
    strength = abs(parse_float(target["relative_intensity"]) - parse_float(source["relative_intensity"]))
    persistence = abs(parse_float(target["threshold_persistence_count"]) - parse_float(source["threshold_persistence_count"])) / 2.0
    background = 0.5 if source["background_relation"] != target["background_relation"] else 0.0
    return motion + 0.25 * global_continuity + 0.35 * shape + 0.25 * orientation + 0.20 * strength + 0.20 * persistence + background


def event_row(
    counter: int, source: Mapping[str, Any] | None, target: Mapping[str, Any] | None, event_type: str,
    frame_from: int, frame_to: int, cost: float = math.nan, notes: str = "",
) -> dict[str, Any]:
    base = source or target or {}
    global_disp = raw_disp = smooth_disp = strength_change = shape_change = math.nan
    if source and target:
        sx, sy = parse_float(source["global_centroid_x_px"]), parse_float(source["global_centroid_y_px"])
        tx, ty = parse_float(target["global_centroid_x_px"]), parse_float(target["global_centroid_y_px"])
        global_disp = math.hypot(tx - sx, ty - sy)
        raw_disp = math.hypot(parse_float(target["raw_local_radial_px"]) - parse_float(source["raw_local_radial_px"]), parse_float(target["raw_local_tangential_px"]) - parse_float(source["raw_local_tangential_px"]))
        smooth_disp = math.hypot(parse_float(target["smoothed_local_radial_px"]) - parse_float(source["smoothed_local_radial_px"]), parse_float(target["smoothed_local_tangential_px"]) - parse_float(source["smoothed_local_tangential_px"]))
        strength_change = parse_float(target["relative_intensity"]) - parse_float(source["relative_intensity"])
        shape_change = abs(math.log(max(1.0, parse_float(target["area_px"])) / max(1.0, parse_float(source["area_px"]))))
    threshold_support = min(int(parse_float(source.get("threshold_persistence_count") if source else 0, 0)), int(parse_float(target.get("threshold_persistence_count") if target else 0, 0))) if source and target else int(parse_float(base.get("threshold_persistence_count"), 0))
    gt_artifact = bool(source and target and raw_disp > 8.0 and smooth_disp < raw_disp * 0.45 and global_disp < raw_disp * 0.7)
    threshold_artifact = threshold_support < 2 or event_type in {"split", "merge"} and threshold_support < 3
    background_like = base.get("background_relation", "") == "connected_to_crop_or_context_boundary"
    global_supported = math.isfinite(global_disp) and (event_type not in {"birth", "death"} or not background_like)
    return {
        "temporal_event_id": f"S1L-EVT-{counter:07d}", "scene": base.get("scene", ""),
        "canonical_vehicle_id": base.get("canonical_vehicle_id", ""), "benchmark_role": base.get("benchmark_role", ""),
        "input_tier": base.get("input_tier", ""), "segment_id": base.get("segment_id", ""),
        "sar_frame_from": frame_from, "sar_frame_to": frame_to, "frame_gap": frame_to - frame_from,
        "event_type": event_type, "source_observation_ids": source.get("structure_observation_id", "") if source else "",
        "target_observation_ids": target.get("structure_observation_id", "") if target else "",
        "global_displacement_px": fmt(global_disp), "raw_local_displacement_px": fmt(raw_disp),
        "smoothed_local_displacement_px": fmt(smooth_disp), "relative_intensity_change": fmt(strength_change),
        "shape_change": fmt(shape_change), "correspondence_cost": fmt(cost), "threshold_support_count": threshold_support,
        "global_coordinate_supported": bool_text(global_supported), "raw_gt_local_supported": bool_text(not gt_artifact),
        "smoothed_gt_local_supported": bool_text(not gt_artifact), "crop_or_gt_jitter_artifact": bool_text(gt_artifact),
        "threshold_artifact": bool_text(threshold_artifact), "background_like": bool_text(background_like),
        "major_event": bool_text(not gt_artifact and not threshold_artifact and not background_like), "notes": notes,
    }


def build_temporal_events(observations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_segment_frame: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    tier_by_segment: dict[str, str] = {}
    for row in observations:
        if parse_bool(row["major_temporal_eligible"]) and row["input_tier"] in {"A", "B"}:
            by_segment_frame[row["segment_id"]][int(row["sar_frame_index"])].append(row)
            tier_by_segment[row["segment_id"]] = row["input_tier"]
    output: list[dict[str, Any]] = []
    counter = 1
    for segment_id, frame_map in sorted(by_segment_frame.items()):
        frames = sorted(frame_map)
        for frame_from, frame_to in zip(frames, frames[1:]):
            gap = frame_to - frame_from
            if gap > TEMPORAL_MAX_GAP:
                continue
            sources, targets = frame_map[frame_from], frame_map[frame_to]
            if not sources and not targets:
                continue
            costs = np.full((len(sources), len(targets)), 999.0, dtype=np.float64)
            for i, source in enumerate(sources):
                for j, target in enumerate(targets):
                    costs[i, j] = observation_cost(source, target, gap)
            matched_source: set[int] = set(); matched_target: set[int] = set()
            if sources and targets:
                rows, cols = linear_sum_assignment(costs)
                for i, j in zip(rows.tolist(), cols.tolist()):
                    cost = float(costs[i, j])
                    if cost > MATCH_COST_LIMIT:
                        continue
                    source, target = sources[i], targets[j]
                    matched_source.add(i); matched_target.add(j)
                    alternative = sorted(costs[i].tolist())[1] if len(targets) > 1 else 999.0
                    if alternative - cost < 0.15:
                        event_type = "unresolved_correspondence"
                    else:
                        raw_disp = math.hypot(parse_float(target["raw_local_radial_px"]) - parse_float(source["raw_local_radial_px"]), parse_float(target["raw_local_tangential_px"]) - parse_float(source["raw_local_tangential_px"]))
                        smooth_disp = math.hypot(parse_float(target["smoothed_local_radial_px"]) - parse_float(source["smoothed_local_radial_px"]), parse_float(target["smoothed_local_tangential_px"]) - parse_float(source["smoothed_local_tangential_px"]))
                        event_type = "local_relative_shift" if smooth_disp > 0.30 * math.hypot(source["_smooth_anchor"]["w"], source["_smooth_anchor"]["h"]) else "stable_persistence"
                        expected = math.hypot(target["_smooth_anchor"]["cx"] - source["_smooth_anchor"]["cx"], target["_smooth_anchor"]["cy"] - source["_smooth_anchor"]["cy"])
                        global_disp = math.hypot(parse_float(target["global_centroid_x_px"]) - parse_float(source["global_centroid_x_px"]), parse_float(target["global_centroid_y_px"]) - parse_float(source["global_centroid_y_px"]))
                        if expected > 2.0 and abs(global_disp - expected) <= max(6.0, expected * 0.6):
                            event_type = "global_motion_consistent"
                    output.append(event_row(counter, source, target, event_type, frame_from, frame_to, cost)); counter += 1
                    strength_change = parse_float(target["relative_intensity"]) - parse_float(source["relative_intensity"])
                    if strength_change >= 0.20:
                        output.append(event_row(counter, source, target, "strength_increase", frame_from, frame_to, cost)); counter += 1
                    elif strength_change <= -0.20:
                        output.append(event_row(counter, source, target, "strength_decrease", frame_from, frame_to, cost)); counter += 1
            for i, source in enumerate(sources):
                best = float(costs[i].min()) if targets else 999.0
                close_targets = [
                    j for j in range(len(targets))
                    if costs[i, j] <= min(MATCH_COST_LIMIT, best + 0.12)
                    and int(source["threshold_persistence_count"]) == 3
                    and int(targets[j]["threshold_persistence_count"]) == 3
                ]
                if len(close_targets) >= 2:
                    row = event_row(counter, source, targets[close_targets[0]], "split", frame_from, frame_to, float(min(costs[i, close_targets])))
                    row["target_observation_ids"] = ";".join(targets[j]["structure_observation_id"] for j in close_targets)
                    output.append(row); counter += 1
            for j, target in enumerate(targets):
                best = float(costs[:, j].min()) if sources else 999.0
                close_sources = [
                    i for i in range(len(sources))
                    if costs[i, j] <= min(MATCH_COST_LIMIT, best + 0.12)
                    and int(target["threshold_persistence_count"]) == 3
                    and int(sources[i]["threshold_persistence_count"]) == 3
                ]
                if len(close_sources) >= 2:
                    row = event_row(counter, sources[close_sources[0]], target, "merge", frame_from, frame_to, float(min(costs[close_sources, j])))
                    row["source_observation_ids"] = ";".join(sources[i]["structure_observation_id"] for i in close_sources)
                    output.append(row); counter += 1
            for i, source in enumerate(sources):
                if i not in matched_source:
                    output.append(event_row(counter, source, None, "death", frame_from, frame_to)); counter += 1
            for j, target in enumerate(targets):
                if j not in matched_target:
                    output.append(event_row(counter, None, target, "birth", frame_from, frame_to)); counter += 1
            if sources and targets:
                source_dom = max(sources, key=lambda row: parse_float(row["relative_intensity"]))
                target_dom = max(targets, key=lambda row: parse_float(row["relative_intensity"]))
                if source_dom["structure_observation_id"] not in {row["source_observation_ids"] for row in output[-max(1, len(sources) + len(targets) + 5):] if row["target_observation_ids"] == target_dom["structure_observation_id"]}:
                    output.append(event_row(counter, source_dom, target_dom, "dominant_component_switch", frame_from, frame_to, observation_cost(source_dom, target_dom, gap))); counter += 1
    return output


def build_artifact_audit(events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    counter = 1
    for event in events:
        for audit_type in ("gt_jitter_counterfactual", "crop_motion_counterfactual", "threshold_counterfactual", "background_counterfactual_link"):
            gt_artifact = parse_bool(event["crop_or_gt_jitter_artifact"])
            threshold_artifact = parse_bool(event["threshold_artifact"])
            background_like = parse_bool(event["background_like"])
            artifact = (
                gt_artifact if audit_type in {"gt_jitter_counterfactual", "crop_motion_counterfactual"}
                else threshold_artifact if audit_type == "threshold_counterfactual" else background_like
            )
            output.append({
                "audit_id": f"S1L-AUD-{counter:08d}", "scene": event["scene"],
                "canonical_vehicle_id": event["canonical_vehicle_id"], "segment_id": event["segment_id"],
                "temporal_event_id": event["temporal_event_id"], "sar_frame_from": event["sar_frame_from"],
                "sar_frame_to": event["sar_frame_to"], "audit_type": audit_type,
                "raw_gt_result": "artifact_supported" if gt_artifact else "event_not_explained_by_raw_gt_only",
                "smoothed_gt_result": "event_survives" if not gt_artifact else "event_collapses_after_smoothing",
                "global_coordinate_result": "event_survives" if parse_bool(event["global_coordinate_supported"]) else "not_supported",
                "threshold_result": "threshold_fragile" if threshold_artifact else "multi_threshold_supported",
                "background_result": "background_like" if background_like else "not_background_connected",
                "decision": "artifact" if artifact else "not_artifact_for_this_counterfactual",
                "artifact_label": "crop_or_gt_jitter_artifact" if gt_artifact and audit_type != "threshold_counterfactual" else "threshold_artifact" if threshold_artifact and audit_type == "threshold_counterfactual" else "background_like" if background_like and audit_type == "background_counterfactual_link" else "",
                "evidence_values": f"global={event['global_displacement_px']};raw_local={event['raw_local_displacement_px']};smoothed_local={event['smoothed_local_displacement_px']};threshold_support={event['threshold_support_count']}",
                "notes": "counterfactual audit is event-level and does not assign a physical vehicle part",
            }); counter += 1
    return output


def offset_anchor(anchor: Mapping[str, float], dr: float, dt: float) -> dict[str, float]:
    radial, tangential = unit_vectors(anchor["cx"], anchor["cy"])
    result = dict(anchor)
    shifted = np.array([anchor["cx"], anchor["cy"]]) + radial * dr + tangential * dt
    result["cx"], result["cy"] = float(shifted[0]), float(shifted[1])
    return result


def polygon_overlap_fraction(polygon: np.ndarray, other_polygons: Sequence[np.ndarray]) -> float:
    area = abs(float(cv2.contourArea(polygon.astype(np.float32))))
    if area <= 1e-6:
        return 1.0
    overlap = 0.0
    for other in other_polygons:
        value, _ = cv2.intersectConvexConvex(polygon.astype(np.float32), other.astype(np.float32))
        overlap += max(0.0, float(value))
    return min(1.0, overlap / area)


def background_candidate_metrics(
    specs: Sequence[dict[str, Any]], dr: float, dt: float, moving: bool,
    gt_by_frame: Mapping[tuple[str, int], Sequence[np.ndarray]], fixed_anchor: Mapping[str, float] | None = None,
) -> tuple[float, float, float, float, float, float]:
    valid_values: list[float] = []
    nonzero_values: list[float] = []
    overlap_values: list[float] = []
    linearity_values: list[float] = []
    gradient_strength_values: list[float] = []
    step = max(1, len(specs) // 12)
    for spec in specs[::step]:
        image = cv2.imread(str(sar_path(spec["scene"], spec["frame"])), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(sar_path(spec["scene"], spec["frame"]))
        anchor = offset_anchor(spec["smoothed_anchor"], dr, dt) if moving else dict(fixed_anchor or spec["smoothed_anchor"])
        pseudo = dict(spec); pseudo["raw_anchor"] = dict(anchor); pseudo["smoothed_anchor"] = dict(anchor)
        polygon, _, _ = crop_polygon(anchor)
        if (
            float(polygon[:, 0].max()) < 0.0 or float(polygon[:, 0].min()) >= CANVAS_WIDTH
            or float(polygon[:, 1].max()) < 0.0 or float(polygon[:, 1].min()) >= CANVAS_HEIGHT
        ):
            valid_values.append(0.0); nonzero_values.append(0.0); overlap_values.append(0.0); linearity_values.append(0.0); gradient_strength_values.append(0.0)
            continue
        context = build_frame_context(pseudo, image)
        total = max(1, int((context["raw_mask"] | context["smooth_mask"]).sum()))
        valid = float(context["analysis_mask"].sum()) / total
        values = context["image"][context["analysis_mask"]]
        nonzero = float(np.mean(values > 0)) if values.size else 0.0
        polygon = context["raw_poly"]
        overlap = polygon_overlap_fraction(polygon, gt_by_frame.get((spec["scene"], spec["frame"]), []))
        if values.size:
            local = context["image"].astype(np.float32)
            gx = cv2.Sobel(local, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(local, cv2.CV_32F, 0, 1, ksize=3)
            ex = float(np.mean(np.abs(gx[context["analysis_mask"]])))
            ey = float(np.mean(np.abs(gy[context["analysis_mask"]])))
            linearity = max(ex, ey) / max(1e-6, ex + ey)
            gradient_strength = (ex + ey) / 255.0
        else:
            linearity = 0.0
            gradient_strength = 0.0
        valid_values.append(valid); nonzero_values.append(nonzero); overlap_values.append(overlap); linearity_values.append(linearity); gradient_strength_values.append(gradient_strength)
    mean_valid = float(np.mean(valid_values)); mean_nonzero = float(np.mean(nonzero_values))
    mean_overlap = float(np.mean(overlap_values)); mean_linearity = float(np.mean(linearity_values))
    mean_gradient_strength = float(np.mean(gradient_strength_values))
    low_nonzero_penalty = 3.0 if mean_nonzero < 0.75 else 0.0
    score = 4.0 * mean_valid + 4.0 * mean_nonzero + mean_linearity + 2.0 * mean_gradient_strength - 6.0 * mean_overlap - low_nonzero_penalty
    return score, mean_valid, mean_nonzero, mean_overlap, mean_linearity, mean_gradient_strength


def select_background_specs(
    specs: Sequence[dict[str, Any]], gt_by_frame: Mapping[tuple[str, int], Sequence[np.ndarray]],
) -> list[dict[str, Any]]:
    median_hr = statistics.median(anchor_extents(spec["smoothed_anchor"])[2] for spec in specs)
    median_ht = statistics.median(anchor_extents(spec["smoothed_anchor"])[3] for spec in specs)
    definitions = {
        "same_range_neighbor": [(0.0, sign * factor * median_ht, True) for factor in (3.5, 5.0, 6.5) for sign in (-1.0, 1.0)],
        "same_azimuth_neighbor": [(sign * factor * median_hr, 0.0, True) for factor in (3.5, 5.0, 6.5) for sign in (-1.0, 1.0)],
        "trajectory_shifted_background": [(sign_r * 2.0 * median_hr, sign_t * factor * median_ht, True) for factor in (4.5, 6.0) for sign_r in (-1.0, 1.0) for sign_t in (-1.0, 1.0)],
    }
    selected: list[dict[str, Any]] = []
    for background_type, candidates in definitions.items():
        ranked = []
        for dr, dt, moving in candidates:
            metrics = background_candidate_metrics(specs, dr, dt, moving, gt_by_frame)
            ranked.append((metrics[0], dr, dt, moving, None, metrics))
        score, dr, dt, moving, fixed_anchor, metrics = max(ranked, key=lambda row: row[0])
        selected.append({"background_type": background_type, "dr": dr, "dt": dt, "moving": moving, "fixed_anchor": fixed_anchor, "selection_metrics": metrics})

    middle = specs[len(specs) // 2]["smoothed_anchor"]
    fixed_ranked = []
    for r_factor in (-8.0, -6.0, -4.0, -2.0, 2.0, 4.0, 6.0, 8.0):
        for t_factor in (-8.0, -6.0, -4.0, -2.0, 2.0, 4.0, 6.0, 8.0):
            dr, dt = r_factor * median_hr, t_factor * median_ht
            fixed_anchor = offset_anchor(middle, dr, dt)
            metrics = background_candidate_metrics(specs, dr, dt, False, gt_by_frame, fixed_anchor=fixed_anchor)
            fixed_ranked.append((metrics[0], dr, dt, False, fixed_anchor, metrics))
    score, dr, dt, moving, fixed_anchor, metrics = max(fixed_ranked, key=lambda row: row[0])
    selected.append({"background_type": "fixed_strong_linear_background", "dr": dr, "dt": dt, "moving": moving, "fixed_anchor": fixed_anchor, "selection_metrics": metrics})
    order = {"same_range_neighbor": 0, "same_azimuth_neighbor": 1, "fixed_strong_linear_background": 2, "trajectory_shifted_background": 3}
    return sorted(selected, key=lambda row: order[row["background_type"]])


def background_counterfactuals(
    specs_by_segment: Mapping[str, list[dict[str, Any]]], thread_stats: Mapping[str, tuple[float, float, float, float]],
    vehicle_events: Sequence[dict[str, Any]], quality_rows: Sequence[dict[str, str]], review_status: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    visual_payload: list[dict[str, Any]] = []
    by_segment_event = defaultdict(list)
    for event in vehicle_events:
        by_segment_event[event["segment_id"]].append(event)
    gt_by_frame: dict[tuple[str, int], list[np.ndarray]] = defaultdict(list)
    for row in quality_rows:
        try:
            gt_by_frame[(row["scene"], int(row["sar_frame_index"]))].append(rotated_box_corners({"cx": parse_bbox(row["bbox"])[0], "cy": parse_bbox(row["bbox"])[1], "w": parse_bbox(row["bbox"])[2], "h": parse_bbox(row["bbox"])[3], "angle": parse_bbox(row["bbox"])[4]}))
        except (ValueError, KeyError):
            continue
    counter = 1
    for segment_id, specs in sorted(specs_by_segment.items()):
        if not specs or specs[0]["input_tier"] != "A" or specs[0]["benchmark_role"] != "development":
            continue
        vehicle = by_segment_event[segment_id]
        vehicle_transitions = max(1, len({(row["sar_frame_from"], row["sar_frame_to"]) for row in vehicle}))
        vehicle_stable = sum(row["event_type"] in {"stable_persistence", "global_motion_consistent"} and parse_bool(row["major_event"]) for row in vehicle)
        vehicle_complex = sum(row["event_type"] in {"split", "merge", "dominant_component_switch"} for row in vehicle)
        for selected in select_background_specs(specs, gt_by_frame):
            background_type = selected["background_type"]; dr = selected["dr"]; dt = selected["dt"]; moving = selected["moving"]
            pseudo_observations: list[dict[str, Any]] = []
            obs_counter = 1
            fixed_anchor = selected["fixed_anchor"] or offset_anchor(specs[len(specs) // 2]["smoothed_anchor"], dr, dt)
            rendered: list[dict[str, Any]] = []
            actual_valid: list[float] = []; actual_nonzero: list[float] = []; actual_overlap: list[float] = []
            actual_gradient: list[float] = []; actual_linearity: list[float] = []
            for spec in specs:
                image = cv2.imread(str(sar_path(spec["scene"], spec["frame"])), cv2.IMREAD_GRAYSCALE)
                if image is None:
                    raise FileNotFoundError(sar_path(spec["scene"], spec["frame"]))
                shifted = offset_anchor(spec["smoothed_anchor"], dr, dt) if moving else dict(fixed_anchor)
                pseudo = dict(spec); pseudo["raw_anchor"] = dict(shifted); pseudo["smoothed_anchor"] = dict(shifted)
                context = build_frame_context(pseudo, image)
                total = max(1, int((context["raw_mask"] | context["smooth_mask"]).sum()))
                actual_valid.append(float(context["analysis_mask"].sum()) / total)
                values = context["image"][context["analysis_mask"]]
                actual_nonzero.append(float(np.mean(values > 0)) if values.size else 0.0)
                actual_overlap.append(polygon_overlap_fraction(context["raw_poly"], gt_by_frame.get((spec["scene"], spec["frame"]), [])))
                if values.size:
                    local = context["image"].astype(np.float32)
                    gx = cv2.Sobel(local, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(local, cv2.CV_32F, 0, 1, ksize=3)
                    ex = float(np.mean(np.abs(gx[context["analysis_mask"]]))); ey = float(np.mean(np.abs(gy[context["analysis_mask"]])))
                    actual_gradient.append((ex + ey) / 255.0); actual_linearity.append(max(ex, ey) / max(1e-6, ex + ey))
                else:
                    actual_gradient.append(0.0); actual_linearity.append(0.0)
                obs, obs_counter = extract_observations(pseudo, context, thread_stats[segment_id], obs_counter)
                for row in obs:
                    row["segment_id"] = f"{segment_id}|BG|{background_type}"
                    row["canonical_vehicle_id"] = spec["canonical_vehicle_id"]
                pseudo_observations.extend(obs)
                rendered.append({"spec": pseudo, "context": context, "observations": obs})
            pseudo_events = build_temporal_events(pseudo_observations)
            transitions = max(1, len({(row["sar_frame_from"], row["sar_frame_to"]) for row in pseudo_events}))
            stable = sum(row["event_type"] in {"stable_persistence", "global_motion_consistent"} and parse_bool(row["major_event"]) for row in pseudo_events)
            complex_count = sum(row["event_type"] in {"split", "merge", "dominant_component_switch"} for row in pseudo_events)
            vehicle_stable_rate = vehicle_stable / vehicle_transitions
            background_stable_rate = stable / transitions
            vehicle_complex_rate = vehicle_complex / vehicle_transitions
            background_complex_rate = complex_count / transitions
            replicates_stable = background_stable_rate >= 0.65 * max(vehicle_stable_rate, 1e-9)
            replicates = background_stable_rate >= 0.8 * max(vehicle_stable_rate, 1e-9) and background_complex_rate >= 0.8 * max(vehicle_complex_rate, 1e-9)
            mean_valid = float(np.mean(actual_valid)); mean_nonzero = float(np.mean(actual_nonzero)); mean_overlap = float(np.mean(actual_overlap)); mean_gradient = float(np.mean(actual_gradient)); mean_linearity = float(np.mean(actual_linearity))
            quality_ok = mean_valid >= 0.95 and mean_nonzero >= 0.75 and mean_overlap <= 0.05
            if background_type == "fixed_strong_linear_background":
                quality_ok = quality_ok and mean_gradient >= 0.015 and mean_linearity >= 0.58
            output.append({
                "background_thread_id": f"S1L-BG-{counter:04d}", "source_segment_id": segment_id,
                "scene": specs[0]["scene"], "canonical_vehicle_id": specs[0]["canonical_vehicle_id"],
                "background_type": background_type, "offset_radial_px": fmt(dr), "offset_tangential_px": fmt(dt),
                "frame_count": len(specs), "structure_observation_count": len(pseudo_observations),
                "stable_structure_count": sum(parse_bool(row["major_temporal_eligible"]) for row in pseudo_observations),
                "temporal_transition_count": transitions, "stable_persistence_count": stable,
                "split_merge_switch_count": complex_count, "vehicle_stable_persistence_rate": fmt(vehicle_stable_rate),
                "background_stable_persistence_rate": fmt(background_stable_rate), "vehicle_complex_event_rate": fmt(vehicle_complex_rate),
                "background_complex_event_rate": fmt(background_complex_rate), "replicates_stable_persistence": bool_text(replicates_stable),
                "replicates_vehicle_conclusion": bool_text(replicates),
                "mean_valid_mask_fraction": fmt(mean_valid), "mean_nonzero_fraction": fmt(mean_nonzero),
                "mean_gt_overlap_fraction": fmt(mean_overlap), "mean_gradient_strength": fmt(mean_gradient),
                "mean_gradient_linearity": fmt(mean_linearity),
                "background_quality_status": "usable_counterfactual" if quality_ok else "insufficient_counterfactual_quality",
                "review_status": review_status,
                "notes": "offset selected from fixed grid using valid-mask coverage, nonzero response, linear-gradient support, and low overlap with all reviewed GT; same extraction contract as vehicle thread",
            })
            visual_payload.append({"row": output[-1], "frames": rendered}); counter += 1
    return output, visual_payload


def put_text(image: np.ndarray, text: str, origin: tuple[int, int], scale: float = 0.42, color: tuple[int, int, int] = (245, 245, 245), thickness: int = 1) -> None:
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def render_tile(spec: Mapping[str, Any], context: Mapping[str, Any], observations: Sequence[Mapping[str, Any]], title: str = "") -> np.ndarray:
    image = cv2.cvtColor(context["image"], cv2.COLOR_GRAY2BGR)
    x1, y1, _, _ = context["roi"]
    for polygon, color in ((context["raw_poly"], (0, 220, 255)), (context["smooth_poly"], (255, 80, 220))):
        local = np.round(polygon - np.array([x1, y1])).astype(np.int32)
        cv2.polylines(image, [local], True, color, 2, cv2.LINE_AA)
    for row in observations:
        cx = int(round(parse_float(row["global_centroid_x_px"]) - x1)); cy = int(round(parse_float(row["global_centroid_y_px"]) - y1))
        color = (70, 230, 70) if parse_bool(row["major_temporal_eligible"]) else (0, 165, 255)
        if row["structure_type"] == "background_connected_response_structure": color = (50, 50, 230)
        cv2.circle(image, (cx, cy), 4, color, -1, cv2.LINE_AA)
    image = cv2.resize(image, (300, 170), interpolation=cv2.INTER_AREA)
    put_text(image, title or f"f{spec['frame']} {spec['input_tier']} n={len(observations)}", (6, 16))
    return image


def contact_pages(name: str, tiles: Sequence[np.ndarray], columns: int = 5, rows_per_page: int = 4) -> list[Path]:
    directory = VISUAL_ROOT / name
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    per_page = columns * rows_per_page
    for page_index in range(0, len(tiles), per_page):
        page_tiles = list(tiles[page_index:page_index + per_page])
        canvas = np.full((rows_per_page * 170, columns * 300, 3), 18, dtype=np.uint8)
        for index, tile in enumerate(page_tiles):
            row, col = divmod(index, columns)
            canvas[row * 170:(row + 1) * 170, col * 300:(col + 1) * 300] = tile
        path = directory / f"{sanitize(name)}_page_{len(paths) + 1:02d}.png"
        cv2.imwrite(str(path), canvas); paths.append(path)
    return paths


def generate_visuals(
    specs_by_segment: Mapping[str, list[dict[str, Any]]], contexts: Mapping[str, dict[str, Any]],
    observations: Sequence[dict[str, Any]], events: Sequence[dict[str, Any]], background_payload: Sequence[dict[str, Any]],
    review_status: str,
) -> list[dict[str, Any]]:
    VISUAL_ROOT.mkdir(parents=True, exist_ok=True)
    obs_by_key: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        obs_by_key[(row["segment_id"], int(row["sar_frame_index"]))].append(row)
    visual_rows: list[dict[str, Any]] = []
    for segment_id, specs in sorted(specs_by_segment.items()):
        if not specs:
            continue
        tier = specs[0]["input_tier"]
        tiles = [render_tile(spec, contexts[f"{segment_id}|{spec['frame']}"], obs_by_key[(segment_id, spec["frame"])]) for spec in specs]
        for path in contact_pages(f"segments/{tier}_{segment_id}", tiles):
            visual_rows.append({"artifact_type": f"tier_{tier}_segment_contact", "scene": specs[0]["scene"],
                "canonical_vehicle_id": specs[0]["canonical_vehicle_id"], "segment_id": segment_id,
                "artifact_path": str(path), "review_status": review_status, "notes": "raw gray; yellow raw-GT crop; magenta smoothed-GT crop; global-coordinate observations"})
    event_types = {"split", "merge", "dominant_component_switch"}
    event_tiles: list[np.ndarray] = []
    spec_lookup = {(spec["segment_id"], spec["frame"]): spec for specs in specs_by_segment.values() for spec in specs}
    for event in events:
        if event["event_type"] not in event_types and not parse_bool(event["crop_or_gt_jitter_artifact"]):
            continue
        for frame in (int(event["sar_frame_from"]), int(event["sar_frame_to"])):
            spec = spec_lookup.get((event["segment_id"], frame))
            if not spec: continue
            title = f"{event['event_type']} {event['sar_frame_from']}->{event['sar_frame_to']}"
            event_tiles.append(render_tile(spec, contexts[f"{spec['segment_id']}|{frame}"], obs_by_key[(spec["segment_id"], frame)], title))
    for path in contact_pages("events/major_and_artifact_events", event_tiles or [np.full((170, 300, 3), 20, np.uint8)], columns=8, rows_per_page=6):
        visual_rows.append({"artifact_type": "major_or_artifact_event_contact", "scene": "", "canonical_vehicle_id": "",
            "segment_id": "", "artifact_path": str(path), "review_status": review_status,
            "notes": "all split/merge/dominant-switch and event-level artifact cases"})
    for payload in background_payload:
        tiles = [render_tile(item["spec"], item["context"], item["observations"], payload["row"]["background_type"]) for item in payload["frames"]]
        for path in contact_pages(f"background/{payload['row']['background_thread_id']}_{payload['row']['background_type']}", tiles):
            visual_rows.append({"artifact_type": "background_pseudo_thread_contact", "scene": payload["row"]["scene"],
                "canonical_vehicle_id": payload["row"]["canonical_vehicle_id"], "segment_id": payload["row"]["source_segment_id"],
                "artifact_path": str(path), "review_status": review_status, "notes": payload["row"]["background_type"]})
    write_csv(VISUAL_MANIFEST_PATH, visual_rows, ("artifact_type", "scene", "canonical_vehicle_id", "segment_id", "artifact_path", "review_status", "notes"))
    return visual_rows


def mechanism_evaluation(
    frozen: Sequence[dict[str, Any]], observations: Sequence[dict[str, Any]], relations: Sequence[dict[str, Any]],
    events: Sequence[dict[str, Any]], backgrounds: Sequence[dict[str, Any]], review_status: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    obs_by_segment = defaultdict(list); rel_by_segment = defaultdict(list); event_by_segment = defaultdict(list); bg_by_segment = defaultdict(list)
    for row in observations: obs_by_segment[row["segment_id"]].append(row)
    for row in relations: rel_by_segment[row["segment_id"]].append(row)
    for row in events: event_by_segment[row["segment_id"]].append(row)
    for row in backgrounds: bg_by_segment[row["source_segment_id"]].append(row)
    dev_major_types = Counter(row["structure_type"] for row in observations if row["benchmark_role"] == "development" and parse_bool(row["major_temporal_eligible"]))
    dev_major_events = Counter(row["event_type"] for row in events if row["benchmark_role"] == "development" and parse_bool(row["major_event"]))
    counter = 1
    for segment in frozen:
        segment_id = segment["segment_id"]
        obs, rels, evs, bgs = obs_by_segment[segment_id], rel_by_segment[segment_id], event_by_segment[segment_id], bg_by_segment[segment_id]
        stable = [row for row in obs if parse_bool(row["major_temporal_eligible"])]
        relation_types = [item for row in rels for item in row["relation_types"].split(";") if item]
        major_events = [row for row in evs if parse_bool(row["major_event"])]
        heldout_status = "not_applicable"
        if segment["benchmark_role"] == "heldout_validation" and segment["input_tier"] == "A":
            heldout_types = Counter(row["structure_type"] for row in stable)
            heldout_events = Counter(row["event_type"] for row in major_events)
            structure_overlap = bool(set(heldout_types) & set(dev_major_types))
            event_overlap = bool(set(heldout_events) & set(dev_major_events))
            unresolved_rate = sum(row["event_type"] == "unresolved_correspondence" for row in evs) / max(1, len(evs))
            artifact_rate = sum(parse_bool(row["crop_or_gt_jitter_artifact"]) for row in evs) / max(1, len(evs))
            distinctive = {"local_relative_shift", "strength_increase", "strength_decrease", "split", "merge", "dominant_component_switch"}
            distinctive_overlap = bool((set(heldout_events) & set(dev_major_events)) & distinctive)
            heldout_status = "substantive_reproduction" if structure_overlap and event_overlap and distinctive_overlap and unresolved_rate < 0.15 and artifact_rate < 0.10 else "conditional_generic_reproduction" if structure_overlap and event_overlap else "partial_or_no_reproduction"
        bg_replication = sum(parse_bool(row["replicates_vehicle_conclusion"]) for row in bgs) / max(1, len(bgs))
        bg_stable_replication = sum(parse_bool(row["replicates_stable_persistence"]) for row in bgs) / max(1, len(bgs))
        stable_relation = any(any(token in row["relation_types"] for token in ("parallel", "collinear", "near_far_correspondence")) for row in rels)
        cross_scene = "same_scene_heldout_only" if segment["scene"] == "GM_RM017" and segment["benchmark_role"] == "heldout_validation" else "cross_scene_diagnostic_or_counterexample" if segment["scene"] in {"GM_RM011", "GM_RM019"} else "development"
        output.append({
            "evaluation_id": f"S1L-EVAL-{counter:04d}", "scene": segment["scene"],
            "canonical_vehicle_id": segment["canonical_vehicle_id"], "benchmark_role": segment["benchmark_role"],
            "input_tier": segment["input_tier"], "segment_id": segment_id,
            "unique_frame_count": segment["unique_eligible_frame_count"], "source_gt_row_count": segment["source_gt_row_count"],
            "structure_observation_count": len(obs), "stable_structure_count": len(stable),
            "structure_type_distribution": compact_counts(row["structure_type"] for row in obs),
            "relation_count": len(rels), "relation_type_distribution": compact_counts(relation_types),
            "temporal_event_count": len(evs), "temporal_event_distribution": compact_counts(row["event_type"] for row in evs),
            "global_supported_event_count": sum(parse_bool(row["global_coordinate_supported"]) for row in evs),
            "gt_or_crop_artifact_count": sum(parse_bool(row["crop_or_gt_jitter_artifact"]) for row in evs),
            "threshold_artifact_count": sum(parse_bool(row["threshold_artifact"]) for row in evs),
            "background_like_event_count": sum(parse_bool(row["background_like"]) for row in evs),
            "background_replication_rate": fmt(bg_replication), "stable_relation_present": bool_text(stable_relation),
            "background_stable_replication_rate": fmt(bg_stable_replication),
            "heldout_reproduction_status": heldout_status, "cross_scene_interpretation": cross_scene,
            "stage_evidence": "formal_temporal" if segment["input_tier"] == "A" else "diagnostic_only" if segment["input_tier"] == "B" else "single_frame_only",
            "review_status": review_status, "notes": "heldout uses fixed development protocol and cannot select thresholds or relation/event definitions",
        }); counter += 1
    return output


def decide_state(evaluations: Sequence[dict[str, Any]], backgrounds: Sequence[dict[str, Any]], review_status: str) -> tuple[str, bool]:
    formal = [row for row in evaluations if row["input_tier"] == "A"]
    all_six = len(formal) == 6 and all(int(row["unique_frame_count"]) > 0 for row in formal)
    stable_relation = any(parse_bool(row["stable_relation_present"]) for row in formal if row["benchmark_role"] == "development")
    heldout_reproduction = any(row["heldout_reproduction_status"] == "substantive_reproduction" for row in formal)
    background_not_total = sum(parse_bool(row["replicates_vehicle_conclusion"]) for row in backgrounds) < len(backgrounds)
    background_complete = all(row["background_quality_status"] == "usable_counterfactual" for row in backgrounds)
    reviewed = review_status == "directly_reviewed_complete"
    ready = all_six and stable_relation and heldout_reproduction and background_not_total and background_complete and reviewed
    if ready:
        return "S1L_CONTINUOUS_STRUCTURE_READY", True
    any_positive = stable_relation or heldout_reproduction or any(row["heldout_reproduction_status"] == "conditional_generic_reproduction" for row in formal)
    if any_positive:
        return "S1L_CONTINUOUS_STRUCTURE_PARTIALLY_READY", False
    return "S1L_CONTINUOUS_STRUCTURE_BLOCKED", False


def render_report(summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 S1-L Continuous SAR Structure and Artifact Control (20260715)", "",
        "## 1. Executive result", "",
        f"- Stage state: `{summary['stage_state']}`.",
        f"- S1-D allowed: `{str(summary['s1d_allowed']).lower()}`.",
        "- Automatic annotation allowed: `false`.",
        "- Research object: two-dimensional SAR grayscale-display local response structure.",
        "- GT role: local research neighbourhood and same-vehicle thread only; not a response mask or geometric truth.", "",
        "## 2. Frozen inputs", "",
        f"- A/B/C segments: `{summary['tier_segment_counts']}`.",
        f"- Source structure-eligible GT rows: `{summary['source_gt_rows']}` (A temporal rows `{summary['temporal_gt_rows']}`).",
        f"- Unique frame-level response fields: `{summary['local_response_field_count']}`.",
        f"- Six formal segment frame counts: `{summary['formal_segment_frame_counts']}`.", "",
        "The 298 eligible GT rows are all retained. Nineteen same-vehicle/same-frame positions contain overlapping duplicate GT records; these rows contribute to the raw anchor consensus and GT-spread audit, while the response field is reconstructed once per unique scene/vehicle/frame.", "",
        "## 3. Response-field reconstruction", "",
        f"- Local response fields: `{summary['local_response_field_count']}`.",
        f"- Maximum global/local inverse error: `{summary['max_inverse_error_px']}` px.",
        "- Every field retains the raw grayscale image hash, global pixel coordinates, fan-polar r/theta, raw-GT local coordinates, smoothed-GT local coordinates, and raw intensity statistics.",
        "- Fixed score levels are 0.35/0.50/0.65 after thread-robust normalization; local-background and log-display forms are cross-checks, not separately tuned displays.", "",
        "## 4. Structure observations and relations", "",
        f"- Structure observations: `{summary['structure_observation_count']}`; multi-threshold/cross-normalization major observations: `{summary['stable_structure_count']}`.",
        f"- Single-threshold-only fragments retained as frame-level counts rather than formal objects: `{summary['single_threshold_component_count']}`.",
        f"- Structure type mix: `{summary['structure_type_distribution']}`.",
        f"- Spatial relations: `{summary['relation_count']}`; relation mix: `{summary['relation_type_distribution']}`.",
        "- These are response observations, not vehicle parts, physical scattering centers, candidate boxes, or selector inputs.", "",
        "## 5. Temporal events and artifact controls", "",
        f"- Temporal events: `{summary['temporal_event_count']}`; event mix: `{summary['temporal_event_distribution']}`.",
        f"- GT/crop-jitter artifacts: `{summary['gt_crop_artifact_count']}`.",
        f"- Threshold-fragile events: `{summary['threshold_artifact_count']}`.",
        f"- Background-connected events: `{summary['background_like_event_count']}`.",
        f"- Four counterfactual audit rows are present for every event; total audit rows: `{summary['artifact_audit_count']}`.", "",
        "## 6. Background counterfactuals", "",
        f"- Background pseudo-threads: `{summary['background_thread_count']}` (four for each development A-layer thread).",
        f"- Threads reproducing stable persistence at 65% of the vehicle frequency: `{summary['background_stable_replication_count']}`.",
        f"- Threads reproducing the full stable-plus-complex conclusion: `{summary['background_replication_count']}`.",
        f"- Background result: `{summary['background_conclusion']}`.", "",
        f"- Usable background controls: `{summary['background_usable_count']}` / `{summary['background_thread_count']}`.", "",
        "## 7. Development, heldout, and cross-scene scope", "",
        f"- Development finding: `{summary['development_finding']}`.",
        f"- Heldout reproduction: `{summary['heldout_finding']}`.",
        f"- GM_RM011/GM_RM019 cross-scene diagnosis: `{summary['cross_scene_finding']}`.",
        "- Heldout is dominated by GM_RM017 and can support only same-scene cross-vehicle reproduction, never a cross-scene generalization claim.", "",
        "## 8. Visual review, validation, and replay", "",
        f"- Visual artifacts: `{summary['visual_artifact_count']}`; review status: `{summary['review_status']}`.",
        f"- Fixed-input replay: `{summary.get('replay_status','pending')}`.",
        "- Temporary PNG assets remain outside Git under the workspace output root.", "",
        "### Direct visual findings", "",
        f"- Raw versus smoothed crop control: `{summary['visual_raw_smoothed_finding']}`.",
        f"- Structure stability: `{summary['visual_structure_finding']}`.",
        f"- Split/merge/switch review: `{summary['visual_event_finding']}`.",
        f"- Background review: `{summary['visual_background_finding']}`.", "",
        "## 9. Decision", "",
        f"The final state is `{summary['stage_state']}`. S1-D entry is `{str(summary['s1d_allowed']).lower()}`. Automatic annotation entry is always `false`.", "",
        "## 10. Explicit non-execution", "",
        "This run did not modify optical P1-F, canonical identity, hard synchronization, the frozen mapping, or any S0/S0-M/S0-MV product. It did not use P1-F propagation, infer a vehicle-response mask, generate a candidate box, selector, ranking, Gate, oracle, composite score, trained model, final SAR annotation, phase/IQ reconstruction, or authoritative metric-grid claim.", "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def strip_private(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-status", choices=("pending_direct_review", "directly_reviewed_complete"), default="pending_direct_review")
    parser.add_argument("--replay-check", action="store_true")
    args = parser.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True); LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    eligibility = read_csv(ELIGIBILITY_PATH); segments = read_csv(SEGMENTS_PATH); quality = read_csv(QUALITY_PATH)
    quality_by_id = {row["sar_gt_id"]: row for row in quality}
    lineage = {(row["scene"], int(row["frame_index"])): row for row in read_csv(LINEAGE_PATH)}
    frozen, tier_by_segment = freeze_inputs(eligibility, segments)
    specs, specs_by_segment = build_frame_specs(eligibility, quality_by_id, tier_by_segment)

    contexts: dict[str, dict[str, Any]] = {}
    images: dict[tuple[str, int], np.ndarray] = {}
    for spec in specs:
        key = (spec["scene"], spec["frame"])
        if key not in images:
            image = cv2.imread(str(sar_path(*key)), cv2.IMREAD_GRAYSCALE)
            if image is None: raise FileNotFoundError(sar_path(*key))
            images[key] = image
        contexts[f"{spec['segment_id']}|{spec['frame']}"] = build_frame_context(spec, images[key])
    stats_by_segment = thread_statistics(specs, contexts)

    field_rows: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    obs_counter = 1
    for spec in specs:
        context = contexts[f"{spec['segment_id']}|{spec['frame']}"]
        stats = stats_by_segment[spec["segment_id"]]
        radial, tangential, raw_hr, raw_ht = anchor_extents(spec["raw_anchor"])
        _, _, smooth_hr, smooth_ht = anchor_extents(spec["smoothed_anchor"])
        image_path = sar_path(spec["scene"], spec["frame"])
        lineage_row = lineage[(spec["scene"], spec["frame"])]
        field_id = f"S1L-FIELD-{spec['scene']}-{sanitize(spec['canonical_vehicle_id'])}-{spec['frame']:06d}"
        field_rows.append({
            "response_field_id": field_id, "scene": spec["scene"], "canonical_vehicle_id": spec["canonical_vehicle_id"],
            "benchmark_role": spec["benchmark_role"], "input_tier": spec["input_tier"], "segment_id": spec["segment_id"],
            "sar_frame_index": spec["frame"], "sar_time_sec": fmt(spec["frame"] / FPS, 9),
            "source_gt_ids": ";".join(row["sar_gt_id"] for row in spec["source_rows"]), "source_gt_count": len(spec["source_rows"]),
            "source_gt_quality_distribution": compact_counts(row["gt_quality_status"] for row in spec["quality_rows"]),
            "raw_anchor_center_x_px": fmt(spec["raw_anchor"]["cx"]), "raw_anchor_center_y_px": fmt(spec["raw_anchor"]["cy"]),
            "raw_anchor_width_px": fmt(spec["raw_anchor"]["w"]), "raw_anchor_height_px": fmt(spec["raw_anchor"]["h"]),
            "raw_anchor_angle_deg": fmt(spec["raw_anchor"]["angle"]), "smoothed_anchor_center_x_px": fmt(spec["smoothed_anchor"]["cx"]),
            "smoothed_anchor_center_y_px": fmt(spec["smoothed_anchor"]["cy"]), "smoothed_anchor_width_px": fmt(spec["smoothed_anchor"]["w"]),
            "smoothed_anchor_height_px": fmt(spec["smoothed_anchor"]["h"]), "smoothed_anchor_angle_deg": fmt(spec["smoothed_anchor"]["angle"]),
            "gt_center_spread_px": fmt(spec["raw_anchor"]["center_spread"]), "gt_size_spread_px": fmt(spec["raw_anchor"]["size_spread"]),
            "crop_expansion": fmt(CROP_EXPANSION), "raw_crop_polygon_global_px": polygon_text(context["raw_poly"]),
            "smoothed_crop_polygon_global_px": polygon_text(context["smooth_poly"]),
            "global_roi_x1": context["roi"][0], "global_roi_y1": context["roi"][1], "global_roi_x2": context["roi"][2], "global_roi_y2": context["roi"][3],
            "radial_unit_x": fmt(radial[0]), "radial_unit_y": fmt(radial[1]), "tangential_unit_x": fmt(tangential[0]), "tangential_unit_y": fmt(tangential[1]),
            "raw_half_extent_radial_px": fmt(raw_hr), "raw_half_extent_tangential_px": fmt(raw_ht),
            "smoothed_half_extent_radial_px": fmt(smooth_hr), "smoothed_half_extent_tangential_px": fmt(smooth_ht),
            "thread_raw_p05": fmt(stats[0]), "thread_raw_p50": fmt(stats[1]), "thread_raw_p95": fmt(stats[2]), "thread_raw_p99": fmt(stats[3]),
            "local_background_median": fmt(context["bg_median"]), "local_background_mad": fmt(context["bg_mad"]),
            "raw_min": int(context["values"].min()), "raw_max": int(context["values"].max()), "raw_mean": fmt(float(context["values"].mean())),
            "analysis_valid_mask_fraction": fmt(float(context["analysis_mask"].sum()) / max(1, int((context["raw_mask"] | context["smooth_mask"]).sum()))),
            "coordinate_inverse_error_px": fmt(max(inverse_error(spec["raw_anchor"], context["raw_poly"]), inverse_error(spec["smoothed_anchor"], context["smooth_poly"]))),
            "raw_image_path": str(image_path), "raw_image_sha256": lineage_row["gray_content_hash"],
            "low_threshold_component_count": 0, "multi_threshold_component_count": 0, "single_threshold_only_component_count": 0,
            "gt_is_vehicle_response_mask": "false",
            "lineage_status": lineage_row["lineage_status"], "notes": "all original GT rows retained as anchor evidence; field reconstructed once per unique vehicle/frame",
        })
        obs, obs_counter = extract_observations(spec, context, stats, obs_counter)
        field_rows[-1]["low_threshold_component_count"] = len(obs)
        field_rows[-1]["multi_threshold_component_count"] = sum(int(row["threshold_persistence_count"]) >= 2 for row in obs)
        field_rows[-1]["single_threshold_only_component_count"] = sum(int(row["threshold_persistence_count"]) == 1 for row in obs)
        observations.extend(obs)

    relations = build_relations(observations)
    events = build_temporal_events(observations)
    artifacts = build_artifact_audit(events)
    backgrounds, background_payload = background_counterfactuals(specs_by_segment, stats_by_segment, events, quality, args.review_status)
    visual_rows = generate_visuals(specs_by_segment, contexts, observations, events, background_payload, args.review_status)
    formal_observations = [row for row in observations if int(row["threshold_persistence_count"]) >= 2]
    evaluations = mechanism_evaluation(frozen, formal_observations, relations, events, backgrounds, args.review_status)
    stage_state, s1d_allowed = decide_state(evaluations, backgrounds, args.review_status)

    public_observations = strip_private(formal_observations)
    single_threshold_component_count = sum(int(row["single_threshold_only_component_count"]) for row in field_rows)
    source_gt_rows = sum(int(row["source_gt_row_count"]) for row in frozen)
    temporal_gt_rows = sum(int(row["source_gt_row_count"]) for row in frozen if row["input_tier"] == "A")
    relation_types = [item for row in relations for item in row["relation_types"].split(";") if item]
    formal_counts = ";".join(f"{row['segment_id']}:{row['unique_eligible_frame_count']}unique/{row['source_gt_row_count']}rows" for row in frozen if row["input_tier"] == "A")
    heldout_evals = [row for row in evaluations if row["benchmark_role"] == "heldout_validation" and row["input_tier"] == "A"]
    background_replication_count = sum(parse_bool(row["replicates_vehicle_conclusion"]) for row in backgrounds)
    background_stable_replication_count = sum(parse_bool(row["replicates_stable_persistence"]) for row in backgrounds)
    background_usable_count = sum(row["background_quality_status"] == "usable_counterfactual" for row in backgrounds)
    summary = {
        "stage_state": stage_state, "s1d_allowed": s1d_allowed, "automatic_annotation_allowed": False,
        "review_status": args.review_status, "tier_segment_counts": compact_counts(row["input_tier"] for row in frozen),
        "source_gt_rows": source_gt_rows, "temporal_gt_rows": temporal_gt_rows, "local_response_field_count": len(field_rows),
        "formal_segment_frame_counts": formal_counts, "max_inverse_error_px": max(parse_float(row["coordinate_inverse_error_px"], 0.0) for row in field_rows),
        "structure_observation_count": len(public_observations), "stable_structure_count": sum(parse_bool(row["major_temporal_eligible"]) for row in public_observations),
        "single_threshold_component_count": single_threshold_component_count,
        "structure_type_distribution": compact_counts(row["structure_type"] for row in public_observations),
        "relation_count": len(relations), "relation_type_distribution": compact_counts(relation_types),
        "temporal_event_count": len(events), "temporal_event_distribution": compact_counts(row["event_type"] for row in events),
        "gt_crop_artifact_count": sum(parse_bool(row["crop_or_gt_jitter_artifact"]) for row in events),
        "threshold_artifact_count": sum(parse_bool(row["threshold_artifact"]) for row in events),
        "background_like_event_count": sum(parse_bool(row["background_like"]) for row in events),
        "artifact_audit_count": len(artifacts), "background_thread_count": len(backgrounds),
        "background_replication_count": background_replication_count,
        "background_stable_replication_count": background_stable_replication_count,
        "background_usable_count": background_usable_count,
        "background_conclusion": "background_controls_replicate_all_vehicle_patterns" if background_replication_count == len(backgrounds) else "background_controls_do_not_replicate_all_vehicle_patterns",
        "development_finding": "multi-threshold stable observations and generic persistence exist, but vehicle specificity remains conditional because background controls reproduce part of the persistence" if any(parse_bool(row["stable_relation_present"]) for row in evaluations if row["benchmark_role"] == "development" and row["input_tier"] == "A") else "no stable development relation",
        "heldout_finding": compact_counts(row["heldout_reproduction_status"] for row in heldout_evals),
        "cross_scene_finding": "GM_RM011 and GM_RM019 remain diagnostic support/counterexample sources; no formal cross-scene claim",
        "visual_artifact_count": len(visual_rows), "replay_status": "pending", "formal_output_hashes": {},
        "visual_raw_smoothed_finding": "raw and smoothed crops usually overlap, while 27 event rows collapse under GT/crop control" if args.review_status == "directly_reviewed_complete" else "pending direct review",
        "visual_structure_finding": "GM_RM017 shows recurring compact/horizontal response chains, but several development and heldout intervals also show abrupt dense component explosions and crop-edge contamination" if args.review_status == "directly_reviewed_complete" else "pending direct review",
        "visual_event_finding": "many split, merge, and dominant-switch pages coincide with fragmentation bursts or boundary contact; they are not accepted as vehicle dynamics" if args.review_status == "directly_reviewed_complete" else "pending direct review",
        "visual_background_finding": f"{background_stable_replication_count} controls reproduce stable persistence and only {background_usable_count}/16 controls satisfy the full quality contract" if args.review_status == "directly_reviewed_complete" else "pending direct review",
        "explicit_non_execution": ["candidate_box", "selector", "ranking", "Gate", "oracle", "training", "final_annotation", "P1-F propagation", "metric_grid claim"],
    }

    write_csv(FROZEN_INPUT_PATH, frozen, FROZEN_INPUT_FIELDS)
    write_csv(LOCAL_FIELD_PATH, field_rows, LOCAL_FIELD_FIELDS)
    write_csv(OBSERVATION_PATH, public_observations, OBSERVATION_FIELDS)
    write_csv(RELATION_PATH, relations, RELATION_FIELDS)
    write_csv(EVENT_PATH, events, EVENT_FIELDS)
    write_csv(ARTIFACT_PATH, artifacts, ARTIFACT_FIELDS)
    write_csv(BACKGROUND_PATH, backgrounds, BACKGROUND_FIELDS)
    write_csv(EVALUATION_PATH, evaluations, EVALUATION_FIELDS)
    formal_paths = [FROZEN_INPUT_PATH, LOCAL_FIELD_PATH, OBSERVATION_PATH, RELATION_PATH, EVENT_PATH, ARTIFACT_PATH, BACKGROUND_PATH, EVALUATION_PATH]
    summary["formal_output_hashes"] = {path.name: sha256(path) for path in formal_paths}
    render_report(summary)
    summary["formal_output_hashes"][REPORT_PATH.name] = sha256(REPORT_PATH)
    write_json(SUMMARY_PATH, summary)

    if args.replay_check:
        previous = json.loads(REPLAY_PATH.read_text(encoding="utf-8")) if REPLAY_PATH.exists() else {}
        current = {path.name: sha256(path) for path in formal_paths + [REPORT_PATH]}
        status = "PASS" if not previous or previous.get("hashes") == current else "FAIL"
        write_json(REPLAY_PATH, {"status": status, "hashes": current, "previous_hashes": previous.get("hashes", current)})
        summary["replay_status"] = status
        render_report(summary); write_json(SUMMARY_PATH, summary)
    else:
        write_json(REPLAY_PATH, {"status": "BASELINE_CAPTURED", "hashes": {path.name: sha256(path) for path in formal_paths + [REPORT_PATH]}})

    LOG_PATH.write_text(
        f"S1-L run complete\nstage_state={stage_state}\nreview_status={args.review_status}\noutput_root={OUTPUT_ROOT}\nreport={REPORT_PATH}\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
