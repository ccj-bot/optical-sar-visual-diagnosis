"""OTY2 gated association and scatter-cluster audit.

This diagnostic follows the OTY2 range-narrowing/peak-competition audit and
asks a narrower question: when top1 peak competition is severe, what does the
top-k SAR scatter structure say about the optical-derived support region?

The output is a posthoc observation audit. It does not generate annotation
proposals, selector/ranking outputs, training products, tuned thresholds, or
identity-truth claims. SAR GT is used only to diagnose top-k peak relationships
after support-region extraction.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from run_oty2_range_narrowing_peak_competition_audit import (
    EXTRACTION_STRIDE,
    EXPECTED_LEDGER,
    FAN_CENTER_X,
    FAN_CENTER_Y,
    FAN_RADIUS_PX,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    SarImageCache,
    bool_text,
    compact_counts,
    fmt,
    groupby_key,
    latest_path,
    mean_clean,
    median_clean,
    point_from_polar,
    point_to_azimuth_deg,
    point_to_radius_px,
    read_csv,
    safe_float,
    safe_int,
    sar_path,
    write_csv,
    write_json,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "topk_peak_gt_distance_used_for_posthoc_diagnosis": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "gt_peak_or_residual_written_to_runtime_prior": False,
    "annotation_proposal_entered": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
    "matlab_zip_or_any_zip_committed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
}

TOPK_FIELDS = [
    "diagnosis_id",
    "mode_name",
    "scene",
    "object_hypothesis_id",
    "sample_pool",
    "clean_morphology_inclusion",
    "state_condition",
    "optical_frame",
    "sar_frame",
    "gt_center_x_posthoc",
    "gt_center_y_posthoc",
    "gt_size_proxy_px_posthoc",
    "near_gt_threshold_px_posthoc",
    "extended_gt_threshold_px_posthoc",
    "topk_peak_count",
    "topk_peaks_xy_value_distance",
    "top1_distance_to_gt_px_posthoc",
    "top2_distance_to_gt_px_posthoc",
    "top3_distance_to_gt_px_posthoc",
    "best_topk_rank_to_gt_posthoc",
    "best_topk_distance_to_gt_px_posthoc",
    "top1_near_gt_posthoc",
    "top2_or_top3_nearer_than_top1_posthoc",
    "topk_contains_peak_near_gt_posthoc",
    "multiple_topk_peaks_near_gt_posthoc",
    "all_topk_far_from_gt_posthoc",
    "topk_gt_relationship_label",
    "provenance_labels",
    "notes",
]

CLUSTER_FIELDS = [
    "cluster_probe_id",
    "mode_name",
    "relationship_type",
    "sample_pool",
    "clean_morphology_inclusion",
    "scene",
    "object_hypothesis_id",
    "state_condition",
    "optical_frame",
    "sar_frame",
    "support_area_px",
    "area_ratio_vs_broad",
    "radius_band_width_px",
    "top1_background_ratio",
    "top1_top2_ratio",
    "topk_peak_count",
    "local_peak_count_above_bg_p95",
    "cluster_centroid_x",
    "cluster_centroid_y",
    "cluster_compactness_px",
    "cluster_peak_spread_px",
    "cluster_range_spread_px",
    "cluster_azimuth_spread_deg",
    "scatter_cov_xx",
    "scatter_cov_xy",
    "scatter_cov_yy",
    "profile_sharpness_proxy",
    "vehicle_footprint_fit_posthoc",
    "scatter_cluster_type",
    "temporal_cluster_label",
    "optical_state_gate",
    "range_uncertainty_gate",
    "gated_association_status",
    "provenance_labels",
    "notes",
]

TEMPORAL_FIELDS = [
    "temporal_probe_id",
    "mode_name",
    "sample_pool",
    "scene",
    "object_hypothesis_id",
    "state_mix",
    "n_frames",
    "sar_frame_span",
    "centroid_step_mean_px",
    "top1_step_mean_px",
    "best_peak_step_mean_px",
    "cluster_persistence_rate",
    "topk_contains_peak_near_gt_rate_posthoc",
    "top2_or_top3_nearer_than_top1_rate_posthoc",
    "scatter_cluster_type_mix",
    "range_tube_continuity_label_input",
    "temporal_cluster_label",
    "provenance_labels",
    "notes",
]

STATE_GATE_FIELDS = [
    "state_gate_probe_id",
    "mode_name",
    "state_condition",
    "sample_pool",
    "n_rows",
    "optical_state_gate",
    "range_uncertainty_gate",
    "topk_contains_peak_near_gt_rate_posthoc",
    "multiple_topk_peaks_near_gt_rate_posthoc",
    "all_topk_far_from_gt_rate_posthoc",
    "scatter_cluster_type_mix",
    "gated_association_status_mix",
    "recommended_gate_treatment",
    "provenance_labels",
    "notes",
]


def rate(num: int, den: int) -> str:
    return fmt(num / den if den else None, 4)


def parse_metric_blob(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for part in str(text or "").replace(",", ";").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        number = safe_float(value)
        if number is not None:
            result[key.strip()] = float(number)
    return result


def parse_center(text: str) -> tuple[float, float] | None:
    parts = [safe_float(part) for part in str(text or "").split(",")]
    if len(parts) < 2 or parts[0] is None or parts[1] is None:
        return None
    return float(parts[0]), float(parts[1])


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def distance_steps(rows: Sequence[Mapping[str, Any]], x_key: str, y_key: str) -> list[float]:
    steps: list[float] = []
    last: tuple[float, float] | None = None
    for row in rows:
        x = safe_float(row.get(x_key))
        y = safe_float(row.get(y_key))
        if x is None or y is None:
            continue
        current = (float(x), float(y))
        if last is not None:
            steps.append(distance(current, last))
        last = current
    return steps


def support_from_row(row: Mapping[str, Any]) -> dict[str, float]:
    return {
        "support_azimuth_start_deg": safe_float(row.get("support_azimuth_start_deg"), -89.0) or -89.0,
        "support_azimuth_end_deg": safe_float(row.get("support_azimuth_end_deg"), 89.0) or 89.0,
        "support_radius_min_px": safe_float(row.get("support_radius_min_px"), 0.0) or 0.0,
        "support_radius_max_px": safe_float(row.get("support_radius_max_px"), FAN_RADIUS_PX) or FAN_RADIUS_PX,
    }


def corr_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("scene", "")),
        str(row.get("object_hypothesis_id", "")),
        str(row.get("optical_frame", "")),
        str(row.get("sar_frame", "")),
    )


def gt_context(row: Mapping[str, Any], corr_by_key: Mapping[tuple[str, str, str, str], Mapping[str, Any]]) -> dict[str, Any]:
    corr = corr_by_key.get(corr_key(row), {})
    center = parse_center(str(corr.get("sar_gt_center", "")))
    radius = safe_float(row.get("gt_radius_px_posthoc"))
    azimuth = safe_float(row.get("gt_azimuth_deg_posthoc"))
    if center is None and radius is not None and azimuth is not None:
        center = point_from_polar(float(radius), float(azimuth))
    size = parse_metric_blob(str(corr.get("sar_gt_width_height_or_rotated_box", "")))
    size_proxy = max(size.get("w", 0.0), size.get("h", 0.0), 80.0)
    near = max(60.0, 0.75 * size_proxy)
    extended = max(120.0, 1.50 * size_proxy)
    return {
        "gt_center": center,
        "gt_size_proxy_px": size_proxy,
        "near_gt_threshold_px": near,
        "extended_gt_threshold_px": extended,
    }


def extract_topk_cluster(
    cache: SarImageCache,
    scene: str,
    sar_frame: int,
    support: Mapping[str, float],
    k: int = 5,
) -> dict[str, Any]:
    image_path = sar_path(scene, sar_frame)
    arr_full = cache.image(image_path)
    if arr_full is None:
        return {"status": "sar_image_missing", "sar_image_path": str(image_path), "peaks": []}
    radius_full, azimuth_full, fan_mask_full = cache.grids(arr_full.shape)
    stride = EXTRACTION_STRIDE
    arr = arr_full[::stride, ::stride]
    radius = radius_full[::stride, ::stride]
    azimuth = azimuth_full[::stride, ::stride]
    fan_mask = fan_mask_full[::stride, ::stride]
    mask = (
        (azimuth >= float(support["support_azimuth_start_deg"]))
        & (azimuth <= float(support["support_azimuth_end_deg"]))
        & (radius >= float(support["support_radius_min_px"]))
        & (radius <= float(support["support_radius_max_px"]))
        & fan_mask
    )
    support_area = int(mask.sum()) * stride * stride
    if support_area <= 0:
        return {
            "status": "empty_support_region",
            "sar_image_path": str(image_path),
            "support_area_px": 0,
            "peaks": [],
        }
    values = arr[mask]
    background = arr[fan_mask & ~mask]
    if background.size == 0:
        background = arr[fan_mask]
    background_mean = float(background.mean()) if background.size else 1.0
    background_p95 = float(np.quantile(background, 0.95)) if background.size else float(values.mean())
    support_p75 = float(np.quantile(values, 0.75)) if values.size else 0.0
    threshold = max(background_p95, support_p75)
    flat = np.flatnonzero(mask & (arr >= threshold))
    if flat.size == 0:
        flat = np.flatnonzero(mask)
    if flat.size == 0:
        return {
            "status": "no_peak_in_support_region",
            "sar_image_path": str(image_path),
            "support_area_px": support_area,
            "peaks": [],
        }
    scores = arr.ravel()[flat]
    n_pick = min(flat.size, 600)
    if n_pick < flat.size:
        candidate_pos = np.argpartition(scores, -n_pick)[-n_pick:]
        ordered = flat[candidate_pos[np.argsort(scores[candidate_pos])[::-1]]]
    else:
        ordered = flat[np.argsort(scores)[::-1]]
    peaks: list[dict[str, float]] = []
    min_distance = 20.0 / stride
    width = arr.shape[1]
    for idx in ordered:
        y = int(idx // width)
        x = int(idx % width)
        if all(math.hypot(x - item["x_stride"], y - item["y_stride"]) >= min_distance for item in peaks):
            peaks.append(
                {
                    "x": float(x * stride),
                    "y": float(y * stride),
                    "x_stride": float(x),
                    "y_stride": float(y),
                    "value": float(arr[y, x]) / 255.0,
                }
            )
        if len(peaks) >= k:
            break
    if not peaks:
        return {
            "status": "no_separated_peak_in_support_region",
            "sar_image_path": str(image_path),
            "support_area_px": support_area,
            "peaks": [],
        }
    local_count = min(int(flat.size), 9999)
    xs = np.array([item["x"] for item in peaks], dtype=np.float64)
    ys = np.array([item["y"] for item in peaks], dtype=np.float64)
    weights = np.array([max(item["value"], 1e-6) for item in peaks], dtype=np.float64)
    centroid_x = float(np.average(xs, weights=weights))
    centroid_y = float(np.average(ys, weights=weights))
    dists = np.hypot(xs - centroid_x, ys - centroid_y)
    compactness = float(np.average(dists, weights=weights))
    peak_spread = float(dists.max()) if dists.size else 0.0
    radii = np.array([point_to_radius_px(float(x), float(y)) for x, y in zip(xs, ys)], dtype=np.float64)
    azimuths = np.array([point_to_azimuth_deg(float(x), float(y)) for x, y in zip(xs, ys)], dtype=np.float64)
    range_spread = float(radii.max() - radii.min()) if radii.size else 0.0
    az_spread = float(azimuths.max() - azimuths.min()) if azimuths.size else 0.0
    cov_xx = cov_xy = cov_yy = 0.0
    if len(peaks) >= 2:
        norm_w = weights / weights.sum()
        dx = xs - centroid_x
        dy = ys - centroid_y
        cov_xx = float((norm_w * dx * dx).sum())
        cov_xy = float((norm_w * dx * dy).sum())
        cov_yy = float((norm_w * dy * dy).sum())
    profile_sharpness = float(peaks[0]["value"] / max(sum(item["value"] for item in peaks), 1e-6))
    return {
        "status": "topk_scatter_cluster_extracted",
        "sar_image_path": str(image_path),
        "support_area_px": support_area,
        "background_mean": background_mean / 255.0,
        "background_p95": background_p95 / 255.0,
        "local_peak_count_above_bg_p95": local_count,
        "peaks": peaks,
        "cluster_centroid_x": centroid_x,
        "cluster_centroid_y": centroid_y,
        "cluster_compactness_px": compactness,
        "cluster_peak_spread_px": peak_spread,
        "cluster_range_spread_px": range_spread,
        "cluster_azimuth_spread_deg": az_spread,
        "scatter_cov_xx": cov_xx,
        "scatter_cov_xy": cov_xy,
        "scatter_cov_yy": cov_yy,
        "profile_sharpness_proxy": profile_sharpness,
    }


def diagnose_topk_gt(row: Mapping[str, Any], cluster: Mapping[str, Any], gt: Mapping[str, Any]) -> dict[str, Any]:
    center = gt.get("gt_center")
    peaks = list(cluster.get("peaks", []))
    if center is None or not peaks:
        return {
            "topk_distances": [],
            "topk_peak_count": len(peaks),
            "topk_gt_relationship_label": "insufficient_gt_or_peak_reference",
        }
    gt_xy = (float(center[0]), float(center[1]))
    distances = [distance((float(item["x"]), float(item["y"])), gt_xy) for item in peaks]
    near = float(gt["near_gt_threshold_px"])
    extended = float(gt["extended_gt_threshold_px"])
    best_idx = min(range(len(distances)), key=lambda idx: distances[idx])
    top1_distance = distances[0]
    top2_or_top3_nearer = any(dist < top1_distance for dist in distances[1:3])
    near_count = sum(1 for dist in distances if dist <= near)
    extended_count = sum(1 for dist in distances if dist <= extended)
    top1_near = top1_distance <= near
    contains_near = near_count > 0
    all_far = min(distances) > extended
    if top1_near:
        label = "top1_peak_near_gt_posthoc"
    elif best_idx > 0 and contains_near:
        label = "later_topk_peak_nearer_to_gt_posthoc"
    elif extended_count >= 2:
        label = "multiple_topk_peaks_near_gt_extended_scatter_posthoc"
    elif all_far:
        label = "all_topk_peaks_far_from_gt_posthoc"
    else:
        label = "topk_peak_group_partially_near_gt_posthoc"
    return {
        "topk_distances": distances,
        "topk_peak_count": len(peaks),
        "top1_distance_to_gt_px_posthoc": top1_distance,
        "top2_distance_to_gt_px_posthoc": distances[1] if len(distances) > 1 else None,
        "top3_distance_to_gt_px_posthoc": distances[2] if len(distances) > 2 else None,
        "best_topk_rank_to_gt_posthoc": best_idx + 1,
        "best_topk_distance_to_gt_px_posthoc": distances[best_idx],
        "top1_near_gt_posthoc": top1_near,
        "top2_or_top3_nearer_than_top1_posthoc": top2_or_top3_nearer,
        "topk_contains_peak_near_gt_posthoc": contains_near,
        "multiple_topk_peaks_near_gt_posthoc": extended_count >= 2,
        "all_topk_far_from_gt_posthoc": all_far,
        "topk_gt_relationship_label": label,
    }


def classify_cluster(row: Mapping[str, Any], cluster: Mapping[str, Any], gt_diag: Mapping[str, Any]) -> str:
    peaks = list(cluster.get("peaks", []))
    if not peaks:
        return "weak_no_structure"
    top1_bg = safe_float(row.get("top1_background_ratio"), safe_float(row.get("top1_background_ratio"), 0.0)) or 0.0
    compactness = safe_float(cluster.get("cluster_compactness_px"), 999.0) or 999.0
    peak_spread = safe_float(cluster.get("cluster_peak_spread_px"), 999.0) or 999.0
    range_spread = safe_float(cluster.get("cluster_range_spread_px"), 0.0) or 0.0
    az_spread = safe_float(cluster.get("cluster_azimuth_spread_deg"), 0.0) or 0.0
    local_count = safe_int(cluster.get("local_peak_count_above_bg_p95"), 0) or 0
    contains_near = bool(gt_diag.get("topk_contains_peak_near_gt_posthoc"))
    multiple_near = bool(gt_diag.get("multiple_topk_peaks_near_gt_posthoc"))
    all_far = bool(gt_diag.get("all_topk_far_from_gt_posthoc"))
    if top1_bg < 1.2 and local_count < 3:
        return "weak_no_structure"
    if all_far and (local_count > 200 or peak_spread > 260):
        return "diffuse_clutter"
    if range_spread >= 180 and range_spread >= 12.0 * max(az_spread, 1.0):
        return "range_spread_cluster"
    if az_spread >= 9.0 and range_spread <= 220:
        return "azimuth_spread_cluster"
    if compactness <= 65 and contains_near:
        return "compact_cluster"
    if compactness <= 135 and (multiple_near or len(peaks) >= 3):
        return "multi_peak_nearby_cluster"
    if peak_spread > 220 or local_count > 200:
        return "diffuse_clutter"
    return "multi_peak_nearby_cluster" if contains_near else "weak_no_structure"


def vehicle_footprint_fit(gt_diag: Mapping[str, Any], cluster: Mapping[str, Any]) -> str:
    best = safe_float(gt_diag.get("best_topk_distance_to_gt_px_posthoc"))
    extended = safe_float(gt_diag.get("extended_gt_threshold_px_posthoc")) or safe_float(gt_diag.get("extended_gt_threshold_px"))
    spread = safe_float(cluster.get("cluster_peak_spread_px"))
    if best is None or extended is None or spread is None:
        return "insufficient_or_not_supported"
    if best <= extended and spread <= 1.5 * extended:
        return "posthoc_compatible_with_vehicle_footprint"
    if best <= extended:
        return "posthoc_near_gt_but_scatter_extent_large"
    return "posthoc_not_compatible_with_gt_footprint"


def optical_state_gate(state: str, sample_pool: str) -> str:
    if sample_pool != "paired_optical_object_sar_gt":
        return "dropout_existence_only_gate"
    if state == "complete":
        return "optical_state_strong_gate"
    if state == "edge_or_truncated":
        return "optical_state_relaxed_gate"
    if state in {"duplicate_or_handoff", "ambiguous_or_review_only"}:
        return "optical_state_review_gate"
    return "optical_state_weak_gate"


def range_gate(row: Mapping[str, Any]) -> str:
    width = safe_float(row.get("radius_band_width_px"))
    area_ratio = safe_float(row.get("area_ratio_vs_broad"))
    mode = str(row.get("mode_name", ""))
    if mode == "broad_fan_baseline":
        return "range_too_broad_for_strong_association"
    if width is None or area_ratio is None:
        return "range_uncertainty_unknown"
    if area_ratio <= 0.20 and width <= 450:
        return "range_band_compact_posthoc"
    if area_ratio <= 0.35:
        return "range_band_moderate_posthoc"
    return "range_band_broad_or_uncertain"


def gated_status(row: Mapping[str, Any]) -> str:
    sample_pool = str(row.get("sample_pool", ""))
    state = str(row.get("state_condition", ""))
    cluster_type = str(row.get("scatter_cluster_type", ""))
    temporal_label = str(row.get("temporal_cluster_label", ""))
    contains_near = row.get("topk_contains_peak_near_gt_posthoc") == "true"
    all_far = row.get("all_topk_far_from_gt_posthoc") == "true"
    if sample_pool != "paired_optical_object_sar_gt":
        return "dropout_existence_support_only"
    if state in {"duplicate_or_handoff", "ambiguous_or_review_only"}:
        return "sar_structure_present_but_optical_ambiguous" if contains_near else "review_required"
    if temporal_label in {"jumping_peak", "diffuse_or_unstable_cluster_tube"} and not contains_near:
        return "rejected_for_temporal_instability"
    if all_far and cluster_type in {"diffuse_clutter", "weak_no_structure"}:
        return "rejected_for_peak_competition"
    if not contains_near:
        return "optical_support_present_but_sar_ambiguous"
    if state == "complete" and cluster_type in {"compact_cluster", "multi_peak_nearby_cluster"} and temporal_label in {"stable_cluster_tube", "centroid_smooth_but_peak_jumps"}:
        return "associated_posthoc_strong"
    if state == "edge_or_truncated" and contains_near:
        return "associated_posthoc_weak"
    if contains_near:
        return "associated_posthoc_weak"
    return "optical_support_present_but_sar_ambiguous"


def build_topk_and_cluster_rows(
    peak_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
    cache: SarImageCache,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corr_by_key = {
        (row.get("scene", ""), row.get("object_hypothesis_id", ""), row.get("optical_frame", ""), row.get("sar_frame", "")): row
        for row in corr_rows
    }
    topk_rows: list[dict[str, Any]] = []
    cluster_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(peak_rows, start=1):
        scene = str(row.get("scene", ""))
        sar_frame = safe_int(row.get("sar_frame"))
        if sar_frame is None:
            continue
        support = support_from_row(row)
        cluster = extract_topk_cluster(cache, scene, sar_frame, support)
        gt = gt_context(row, corr_by_key)
        gt_diag = diagnose_topk_gt(row, cluster, gt)
        peaks = list(cluster.get("peaks", []))
        gt_center = gt.get("gt_center")
        distances = list(gt_diag.get("topk_distances", []))
        peak_summary_parts = []
        for rank, peak in enumerate(peaks, start=1):
            dist = distances[rank - 1] if rank - 1 < len(distances) else None
            peak_summary_parts.append(
                f"{rank}:{fmt(peak.get('x'), 1)},{fmt(peak.get('y'), 1)},v={fmt(peak.get('value'), 4)},d_gt={fmt(dist, 2)}"
            )
        topk_row = {
            "diagnosis_id": f"K{idx:05d}",
            "mode_name": row.get("mode_name", ""),
            "scene": scene,
            "object_hypothesis_id": row.get("object_hypothesis_id", ""),
            "sample_pool": row.get("sample_pool", ""),
            "clean_morphology_inclusion": row.get("clean_morphology_inclusion", ""),
            "state_condition": row.get("state_condition", ""),
            "optical_frame": row.get("optical_frame", ""),
            "sar_frame": row.get("sar_frame", ""),
            "gt_center_x_posthoc": fmt(gt_center[0], 3) if gt_center else "",
            "gt_center_y_posthoc": fmt(gt_center[1], 3) if gt_center else "",
            "gt_size_proxy_px_posthoc": fmt(gt.get("gt_size_proxy_px"), 3),
            "near_gt_threshold_px_posthoc": fmt(gt.get("near_gt_threshold_px"), 3),
            "extended_gt_threshold_px_posthoc": fmt(gt.get("extended_gt_threshold_px"), 3),
            "topk_peak_count": gt_diag.get("topk_peak_count", len(peaks)),
            "topk_peaks_xy_value_distance": ";".join(peak_summary_parts),
            "top1_distance_to_gt_px_posthoc": fmt(gt_diag.get("top1_distance_to_gt_px_posthoc"), 3),
            "top2_distance_to_gt_px_posthoc": fmt(gt_diag.get("top2_distance_to_gt_px_posthoc"), 3),
            "top3_distance_to_gt_px_posthoc": fmt(gt_diag.get("top3_distance_to_gt_px_posthoc"), 3),
            "best_topk_rank_to_gt_posthoc": gt_diag.get("best_topk_rank_to_gt_posthoc", ""),
            "best_topk_distance_to_gt_px_posthoc": fmt(gt_diag.get("best_topk_distance_to_gt_px_posthoc"), 3),
            "top1_near_gt_posthoc": bool_text(gt_diag.get("top1_near_gt_posthoc")),
            "top2_or_top3_nearer_than_top1_posthoc": bool_text(gt_diag.get("top2_or_top3_nearer_than_top1_posthoc")),
            "topk_contains_peak_near_gt_posthoc": bool_text(gt_diag.get("topk_contains_peak_near_gt_posthoc")),
            "multiple_topk_peaks_near_gt_posthoc": bool_text(gt_diag.get("multiple_topk_peaks_near_gt_posthoc")),
            "all_topk_far_from_gt_posthoc": bool_text(gt_diag.get("all_topk_far_from_gt_posthoc")),
            "topk_gt_relationship_label": gt_diag.get("topk_gt_relationship_label", ""),
            "provenance_labels": "SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "notes": "Top-k distances to GT are posthoc diagnostics only; no peak is promoted to a final target center.",
        }
        cluster_type = classify_cluster(row, cluster, gt_diag)
        cluster_row = {
            "cluster_probe_id": f"C{idx:05d}",
            "mode_name": row.get("mode_name", ""),
            "relationship_type": "gated_association_scatter_cluster_diagnostic",
            "sample_pool": row.get("sample_pool", ""),
            "clean_morphology_inclusion": row.get("clean_morphology_inclusion", ""),
            "scene": scene,
            "object_hypothesis_id": row.get("object_hypothesis_id", ""),
            "state_condition": row.get("state_condition", ""),
            "optical_frame": row.get("optical_frame", ""),
            "sar_frame": row.get("sar_frame", ""),
            "support_area_px": row.get("support_area_px", cluster.get("support_area_px", "")),
            "area_ratio_vs_broad": row.get("area_ratio_vs_broad", ""),
            "radius_band_width_px": row.get("radius_band_width_px", ""),
            "top1_background_ratio": row.get("top1_background_ratio", ""),
            "top1_top2_ratio": row.get("top1_top2_ratio", ""),
            "topk_peak_count": gt_diag.get("topk_peak_count", len(peaks)),
            "local_peak_count_above_bg_p95": cluster.get("local_peak_count_above_bg_p95", row.get("local_peak_count_above_bg_p95", "")),
            "cluster_centroid_x": fmt(cluster.get("cluster_centroid_x"), 3),
            "cluster_centroid_y": fmt(cluster.get("cluster_centroid_y"), 3),
            "cluster_compactness_px": fmt(cluster.get("cluster_compactness_px"), 3),
            "cluster_peak_spread_px": fmt(cluster.get("cluster_peak_spread_px"), 3),
            "cluster_range_spread_px": fmt(cluster.get("cluster_range_spread_px"), 3),
            "cluster_azimuth_spread_deg": fmt(cluster.get("cluster_azimuth_spread_deg"), 4),
            "scatter_cov_xx": fmt(cluster.get("scatter_cov_xx"), 3),
            "scatter_cov_xy": fmt(cluster.get("scatter_cov_xy"), 3),
            "scatter_cov_yy": fmt(cluster.get("scatter_cov_yy"), 3),
            "profile_sharpness_proxy": fmt(cluster.get("profile_sharpness_proxy"), 4),
            "vehicle_footprint_fit_posthoc": vehicle_footprint_fit({**gt_diag, **gt}, cluster),
            "scatter_cluster_type": cluster_type,
            "temporal_cluster_label": "",
            "optical_state_gate": optical_state_gate(str(row.get("state_condition", "")), str(row.get("sample_pool", ""))),
            "range_uncertainty_gate": range_gate(row),
            "gated_association_status": "",
            "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "notes": "Cluster classification is an observation diagnostic, not a selector or final annotation.",
        }
        cluster_row.update(
            {
                "topk_contains_peak_near_gt_posthoc": topk_row["topk_contains_peak_near_gt_posthoc"],
                "multiple_topk_peaks_near_gt_posthoc": topk_row["multiple_topk_peaks_near_gt_posthoc"],
                "all_topk_far_from_gt_posthoc": topk_row["all_topk_far_from_gt_posthoc"],
                "top2_or_top3_nearer_than_top1_posthoc": topk_row["top2_or_top3_nearer_than_top1_posthoc"],
                "best_topk_distance_to_gt_px_posthoc": topk_row["best_topk_distance_to_gt_px_posthoc"],
            }
        )
        topk_rows.append(topk_row)
        cluster_rows.append(cluster_row)
    return topk_rows, cluster_rows


def temporal_label_for_group(rows: Sequence[Mapping[str, Any]]) -> str:
    if len(rows) < 2:
        return "insufficient_temporal_samples"
    centroid_step = mean_clean(distance_steps(rows, "cluster_centroid_x", "cluster_centroid_y"))
    top1_step = mean_clean(distance_steps(rows, "top1_x", "top1_y"))
    persistence = cluster_persistence_rate(rows)
    if centroid_step is not None and centroid_step <= 70.0 and persistence >= 0.60:
        return "stable_cluster_tube"
    if centroid_step is not None and centroid_step <= 90.0 and top1_step is not None and top1_step > 150.0:
        return "centroid_smooth_but_peak_jumps"
    if top1_step is not None and top1_step > 180.0 and (centroid_step is None or centroid_step > 120.0):
        return "jumping_peak"
    return "diffuse_or_unstable_cluster_tube"


def cluster_persistence_rate(rows: Sequence[Mapping[str, Any]]) -> float:
    if len(rows) < 2:
        return 0.0
    hits = 0
    total = 0
    last: tuple[float, float] | None = None
    for row in rows:
        x = safe_float(row.get("cluster_centroid_x"))
        y = safe_float(row.get("cluster_centroid_y"))
        if x is None or y is None:
            continue
        current = (float(x), float(y))
        if last is not None:
            total += 1
            if distance(current, last) <= 85.0:
                hits += 1
        last = current
    return hits / total if total else 0.0


def build_temporal_rows(
    cluster_rows: list[dict[str, Any]],
    peak_rows: Sequence[Mapping[str, Any]],
    range_tube_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    peak_lookup = {
        (
            row.get("mode_name", ""),
            row.get("scene", ""),
            row.get("object_hypothesis_id", ""),
            row.get("optical_frame", ""),
            row.get("sar_frame", ""),
        ): row
        for row in peak_rows
    }
    for row in cluster_rows:
        source = peak_lookup.get(
            (
                row.get("mode_name", ""),
                row.get("scene", ""),
                row.get("object_hypothesis_id", ""),
                row.get("optical_frame", ""),
                row.get("sar_frame", ""),
            ),
            {},
        )
        row["top1_x"] = source.get("top1_x", "")
        row["top1_y"] = source.get("top1_y", "")
    range_tube_by_key = {
        (row.get("mode_name", ""), row.get("scene", ""), row.get("object_hypothesis_id", "")): row
        for row in range_tube_rows
    }
    temporal_rows: list[dict[str, Any]] = []
    groups = groupby_key(
        cluster_rows,
        lambda row: (str(row.get("mode_name", "")), str(row.get("sample_pool", "")), str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))),
    )
    labels: dict[tuple[str, str, str], str] = {}
    for idx, ((mode, sample_pool, scene, object_id), rows) in enumerate(sorted(groups.items()), start=1):
        rows = sorted(rows, key=lambda row: safe_int(row.get("sar_frame"), 0) or 0)
        label = temporal_label_for_group(rows)
        labels[(mode, scene, object_id)] = label
        frames = [safe_int(row.get("sar_frame")) for row in rows if safe_int(row.get("sar_frame")) is not None]
        range_tube = range_tube_by_key.get((mode, scene, object_id), {})
        temporal_rows.append(
            {
                "temporal_probe_id": f"T{idx:04d}",
                "mode_name": mode,
                "sample_pool": sample_pool,
                "scene": scene,
                "object_hypothesis_id": object_id,
                "state_mix": compact_counts(row.get("state_condition", "") for row in rows),
                "n_frames": len(rows),
                "sar_frame_span": f"{min(frames)}-{max(frames)}" if frames else "",
                "centroid_step_mean_px": fmt(mean_clean(distance_steps(rows, "cluster_centroid_x", "cluster_centroid_y")), 3),
                "top1_step_mean_px": fmt(mean_clean(distance_steps(rows, "top1_x", "top1_y")), 3),
                "best_peak_step_mean_px": fmt(mean_clean(distance_steps(rows, "cluster_centroid_x", "cluster_centroid_y")), 3),
                "cluster_persistence_rate": fmt(cluster_persistence_rate(rows), 4),
                "topk_contains_peak_near_gt_rate_posthoc": rate(sum(1 for row in rows if row.get("topk_contains_peak_near_gt_posthoc") == "true"), len(rows)),
                "top2_or_top3_nearer_than_top1_rate_posthoc": rate(sum(1 for row in rows if row.get("top2_or_top3_nearer_than_top1_posthoc") == "true"), len(rows)),
                "scatter_cluster_type_mix": compact_counts(row.get("scatter_cluster_type", "") for row in rows),
                "range_tube_continuity_label_input": range_tube.get("tube_peak_continuity_label", ""),
                "temporal_cluster_label": label,
                "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
                "notes": "Temporal row links SAR scatter-cluster diagnostics across the tube; it does not establish identity truth.",
            }
        )
    for row in cluster_rows:
        label = labels.get((str(row.get("mode_name", "")), str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))), "insufficient_temporal_samples")
        row["temporal_cluster_label"] = label
        row["gated_association_status"] = gated_status(row)
    for row in cluster_rows:
        row.pop("top1_x", None)
        row.pop("top1_y", None)
    return temporal_rows


def build_state_gate_rows(cluster_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups = groupby_key(
        cluster_rows,
        lambda row: (str(row.get("mode_name", "")), str(row.get("state_condition", "")), str(row.get("sample_pool", ""))),
    )
    for idx, ((mode, state, sample_pool), group) in enumerate(sorted(groups.items()), start=1):
        rows.append(
            {
                "state_gate_probe_id": f"G{idx:04d}",
                "mode_name": mode,
                "state_condition": state,
                "sample_pool": sample_pool,
                "n_rows": len(group),
                "optical_state_gate": optical_state_gate(state, sample_pool),
                "range_uncertainty_gate": compact_counts(row.get("range_uncertainty_gate", "") for row in group),
                "topk_contains_peak_near_gt_rate_posthoc": rate(sum(1 for row in group if row.get("topk_contains_peak_near_gt_posthoc") == "true"), len(group)),
                "multiple_topk_peaks_near_gt_rate_posthoc": rate(sum(1 for row in group if row.get("multiple_topk_peaks_near_gt_posthoc") == "true"), len(group)),
                "all_topk_far_from_gt_rate_posthoc": rate(sum(1 for row in group if row.get("all_topk_far_from_gt_posthoc") == "true"), len(group)),
                "scatter_cluster_type_mix": compact_counts(row.get("scatter_cluster_type", "") for row in group),
                "gated_association_status_mix": compact_counts(row.get("gated_association_status", "") for row in group),
                "recommended_gate_treatment": state_gate_treatment(state, sample_pool),
                "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
                "notes": "State gate preserves dropout/no-match outside clean morphology and does not declare identity truth.",
            }
        )
    return rows


def state_gate_treatment(state: str, sample_pool: str) -> str:
    if sample_pool != "paired_optical_object_sar_gt":
        return "dropout rows provide temporal existence support only; do not use for clean morphology"
    if state == "complete":
        return "allow strongest posthoc association when SAR cluster and temporal gates pass"
    if state == "edge_or_truncated":
        return "allow weak or relaxed association; keep range and footprint uncertainty wider"
    if state == "duplicate_or_handoff":
        return "manual review required before strong association"
    if state == "ambiguous_or_review_only":
        return "review required; SAR structure can support but not settle optical ambiguity"
    return "weak optical-state gate; keep as hypothesis to validate"


def build_summary(
    timestamp: str,
    topk_rows: Sequence[Mapping[str, Any]],
    cluster_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
    state_rows: Sequence[Mapping[str, Any]],
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    paired = [row for row in topk_rows if row.get("sample_pool") == "paired_optical_object_sar_gt"]
    clean = [row for row in paired if row.get("clean_morphology_inclusion") == "true"]
    broad = [row for row in topk_rows if row.get("mode_name") == "broad_fan_baseline" and row.get("sample_pool") == "paired_optical_object_sar_gt"]
    broad_dropout = [row for row in topk_rows if row.get("mode_name") == "broad_fan_baseline" and row.get("sample_pool") != "paired_optical_object_sar_gt"]
    state_conditioned = [row for row in topk_rows if row.get("mode_name") == "state_conditioned_range_band" and row.get("sample_pool") == "paired_optical_object_sar_gt"]
    cluster_counts = dict(Counter(row.get("scatter_cluster_type", "") for row in cluster_rows))
    temporal_counts = dict(Counter(row.get("temporal_cluster_label", "") for row in temporal_rows))
    association_counts = dict(Counter(row.get("gated_association_status", "") for row in cluster_rows))

    def true_count(rows: Sequence[Mapping[str, Any]], key: str) -> int:
        return sum(1 for row in rows if row.get(key) == "true")

    answers = {
        "1_topk_vs_gt": (
            f"On broad paired rows, top1-near-GT rate is {rate(true_count(broad, 'top1_near_gt_posthoc'), len(broad))}, "
            f"top-k contains a near-GT peak at {rate(true_count(broad, 'topk_contains_peak_near_gt_posthoc'), len(broad))}, "
            f"and top2/top3 is nearer than top1 at {rate(true_count(broad, 'top2_or_top3_nearer_than_top1_posthoc'), len(broad))}. "
            "This confirms that top1 alone is not a reliable center diagnostic."
        ),
        "2_structure_types": (
            f"Scatter structure mix is {json.dumps(cluster_counts, ensure_ascii=False)}. "
            "The classes are SAR observation diagnostics inside support regions, not selector outcomes."
        ),
        "3_temporal_stability": (
            f"Temporal cluster labels are {json.dumps(temporal_counts, ensure_ascii=False)}. "
            "Stable cluster tubes are separated from jumping or diffuse tubes before any association status is assigned."
        ),
        "4_optical_state_gate": (
            "Complete rows can accept the strongest posthoc association only when cluster and temporal gates pass. "
            "Edge/truncated rows stay weak or relaxed, duplicate/handoff and review-only rows require review, and dropout rows are existence support only."
        ),
        "5_association_status": (
            f"Gated association status counts are {json.dumps(association_counts, ensure_ascii=False)}. "
            "These are posthoc association states, not final annotations and not identity truth."
        ),
    }
    return {
        "timestamp": timestamp,
        "sample_ledger": {
            "ledger_valid": True,
            "category_counts": EXPECTED_LEDGER,
            "note": "The audit preserves 215 paired, 195 GM_RM011 blocked missing object stream, 20 SAR-only, and 12 dropout/no-match continuation pool.",
        },
        "row_expansion_note": (
            "CSV rows are support-mode-expanded diagnostics. The underlying sample pools remain 215 paired rows "
            "and 12 dropout/no-match rows; repeated rows across broad/state/object/scene modes are not new samples."
        ),
        "row_counts": {
            "topk_peak_gt_posthoc_diagnosis": len(topk_rows),
            "scatter_cluster_structure_probe": len(cluster_rows),
            "temporal_cluster_association_probe": len(temporal_rows),
            "optical_state_gate_probe": len(state_rows),
        },
        "key_metrics": {
            "broad_mode_paired_source_rows": len(broad),
            "broad_mode_dropout_source_rows": len(broad_dropout),
            "broad_paired_top1_near_gt_rate_posthoc": rate(true_count(broad, "top1_near_gt_posthoc"), len(broad)),
            "broad_paired_topk_contains_near_gt_rate_posthoc": rate(true_count(broad, "topk_contains_peak_near_gt_posthoc"), len(broad)),
            "broad_paired_top2_or_top3_nearer_rate_posthoc": rate(true_count(broad, "top2_or_top3_nearer_than_top1_posthoc"), len(broad)),
            "state_conditioned_topk_contains_near_gt_rate_posthoc": rate(true_count(state_conditioned, "topk_contains_peak_near_gt_posthoc"), len(state_conditioned)),
            "clean_topk_contains_near_gt_rate_posthoc": rate(true_count(clean, "topk_contains_peak_near_gt_posthoc"), len(clean)),
            "paired_multiple_topk_peaks_near_gt_rate_posthoc": rate(true_count(paired, "multiple_topk_peaks_near_gt_posthoc"), len(paired)),
        },
        "scatter_cluster_type_counts": cluster_counts,
        "temporal_cluster_label_counts": temporal_counts,
        "gated_association_status_counts": association_counts,
        "question_answers": answers,
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 Gated Association And Scatter-Cluster Audit Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report audits top-k SAR scatter clusters, temporal cluster stability, optical-state gates, and posthoc gated association states. It does not generate final annotations, selector/ranking output, training, tuned thresholds, or identity truth.",
        "",
        "## Ledger Boundary",
        "",
        "- paired_optical_object_sar_gt = 215",
        "- blocked_missing_gm011_object_stream = 195",
        "- sar_only_gt = 20",
        "- dropout/no_oty_iou_match/temporal continuation pool = 12",
        "",
        "GM_RM011 remains blocked by missing current OTY object stream. SAR-only rows are not mixed into optical-SAR correspondence. Dropout/no-match rows remain outside clean paired morphology.",
        "",
        "## Key Metrics",
        "",
    ]
    for key, value in summary["key_metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Row Expansion Note",
            "",
            summary["row_expansion_note"],
        ]
    )
    lines.extend(["", "## Required Answers", ""])
    for idx, key in enumerate(["1_topk_vs_gt", "2_structure_types", "3_temporal_stability", "4_optical_state_gate", "5_association_status"], start=1):
        lines.append(f"{idx}. {summary['question_answers'][key]}")
    lines.extend(
        [
            "",
            "## Provenance Boundary",
            "",
            "Conclusions use these provenance labels: `runtime_safe_optical_evidence`, `runtime_safe_temporal_evidence`, `SAR_image_observation`, `SAR_temporal_observation`, `SAR_GT_posthoc_evidence`, `manual_or_review_anchor`, `hypothesis_to_validate`, and `insufficient_or_not_supported`.",
            "",
            "Top-k peak distances to GT are posthoc diagnostics. They are not written into runtime prior construction and do not select a final target center.",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Outputs", ""])
    for name, output_path in summary["outputs"].items():
        lines.append(f"- {name}: `{output_path}`")
    lines.extend(["", "## Sources", ""])
    for name, source_path in summary["sources"].items():
        lines.append(f"- {name}: `{source_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any]) -> Path:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORKSPACE_LOG_DIR / f"oty2_gated_association_scatter_cluster_audit_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_gated_association_scatter_cluster_audit",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_dependency=false",
        "repo_outputs_written=true",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "peak_competition_csv": Path(args.peak_competition_csv) if args.peak_competition_csv else latest_path("oty2_support_region_peak_competition_audit_*.csv"),
        "range_tube_csv": Path(args.range_tube_csv) if args.range_tube_csv else latest_path("oty2_range_narrowing_tube_continuity_probe_*.csv"),
        "range_summary_json": Path(args.range_summary_json) if args.range_summary_json else latest_path("oty2_range_narrowing_peak_competition_summary_*.json"),
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
    }
    summary = json.loads(paths["range_summary_json"].read_text(encoding="utf-8"))
    ledger = summary.get("sample_ledger", {}).get("category_counts", {})
    if any(int(ledger.get(key, -1)) != expected for key, expected in EXPECTED_LEDGER.items()):
        raise RuntimeError(f"Ledger changed; refusing gated association audit: {json.dumps(ledger, ensure_ascii=False)}")
    return {
        "paths": paths,
        "range_summary": summary,
        "peak_rows": read_csv(paths["peak_competition_csv"]),
        "range_tube_rows": read_csv(paths["range_tube_csv"]),
        "corr_rows": read_csv(paths["correspondence_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    cache = SarImageCache(max_images=args.image_cache_size)
    peak_rows = inputs["peak_rows"]
    topk_rows, cluster_rows = build_topk_and_cluster_rows(peak_rows, inputs["corr_rows"], cache)
    temporal_rows = build_temporal_rows(cluster_rows, peak_rows, inputs["range_tube_rows"])
    state_rows = build_state_gate_rows(cluster_rows)

    topk_csv = REPORT_DIR / f"oty2_topk_peak_gt_posthoc_diagnosis_{timestamp}.csv"
    cluster_csv = REPORT_DIR / f"oty2_scatter_cluster_structure_probe_{timestamp}.csv"
    temporal_csv = REPORT_DIR / f"oty2_temporal_cluster_association_probe_{timestamp}.csv"
    state_csv = REPORT_DIR / f"oty2_optical_state_gate_probe_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_gated_association_scatter_cluster_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_gated_association_scatter_cluster_summary_{timestamp}.json"
    idea_doc = DOCS_DIR / "oty2_gated_association_scatter_cluster_exploration_idea.md"
    outputs = {
        "idea_doc": str(idea_doc),
        "topk_peak_gt_posthoc_diagnosis_csv": str(topk_csv),
        "scatter_cluster_structure_probe_csv": str(cluster_csv),
        "temporal_cluster_association_probe_csv": str(temporal_csv),
        "optical_state_gate_probe_csv": str(state_csv),
        "gated_association_scatter_cluster_report_md": str(report_md),
        "gated_association_scatter_cluster_summary_json": str(summary_json),
    }
    sources = {name: str(path) for name, path in inputs["paths"].items()}
    summary = build_summary(timestamp, topk_rows, cluster_rows, temporal_rows, state_rows, sources, outputs)
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)

    write_csv(topk_csv, topk_rows, TOPK_FIELDS)
    write_csv(cluster_csv, cluster_rows, CLUSTER_FIELDS)
    write_csv(temporal_csv, temporal_rows, TEMPORAL_FIELDS)
    write_csv(state_csv, state_rows, STATE_GATE_FIELDS)
    render_report(report_md, summary)
    write_json(summary_json, summary)

    print(
        json.dumps(
            {
                "outputs": summary["outputs"],
                "row_counts": summary["row_counts"],
                "key_metrics": summary["key_metrics"],
                "boundary_flags": summary["boundary_flags"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--peak-competition-csv", default="")
    parser.add_argument("--range-tube-csv", default="")
    parser.add_argument("--range-summary-json", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--image-cache-size", type=int, default=64)
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
