#!/usr/bin/env python3
from __future__ import annotations

"""Run lifecycle-gated S1D0 visible-response dynamics without target references."""

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from oty2_s1d0_common import (
    FAN_HEIGHT,
    FAN_WIDTH,
    REPO_ROOT,
    angular_distance_mod180,
    component_orientation,
    condition_shell,
    imaging_valid_mask,
    load_json,
    read_csv,
    require,
    resolve,
    robust_median_mad,
    sha256_file,
    verify_git_gate,
    warp_translation,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = REPO_ROOT / "configs" / "oty2" / "oty2_s1d0_dynamic_response.json"
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"


def parse_args(default_mode: str | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", choices=("causal", "bidirectional"), default=default_mode or "causal")
    return parser.parse_args()


def leakage_guard(config_path: Path, condition_path: Path) -> dict[str, Any]:
    text = config_path.read_text(encoding="utf-8").lower()
    forbidden = ("sar_gt", "final_gt", "gt_quality", "manual_box", "oracle_box", "reference_manifest", "target_iou", "gt_iou")
    hits = [token for token in forbidden if token in text]
    require(not hits, f"forbidden config fragments: {hits}")
    rows = read_csv(condition_path)
    require(rows, "empty lifecycle conditions")
    forbidden_columns = []
    for name in rows[0]:
        lower = name.lower()
        if lower.startswith(("gt_", "manual_", "oracle_", "final_")) or "iou" in lower.split("_"):
            forbidden_columns.append(name)
    require(not forbidden_columns, f"forbidden condition columns: {forbidden_columns}")
    require(all(row["target_sar_reference_dependency"] == "false" for row in rows), "target reference dependency row")
    return {"config_forbidden_hits": [], "condition_forbidden_columns": [], "target_dependency_rows": 0}


def highpass(image: np.ndarray, sigma: float) -> np.ndarray:
    value = np.asarray(image, dtype=np.float32)
    return value - cv2.GaussianBlur(value, (0, 0), sigma)


def phase_shift(left: np.ndarray, right: np.ndarray) -> tuple[float, float, float]:
    window = cv2.createHanningWindow((left.shape[1], left.shape[0]), cv2.CV_32F)
    shift, response = cv2.phaseCorrelate(np.asarray(left, np.float32), np.asarray(right, np.float32), window)
    return float(shift[0]), float(shift[1]), float(response)


def geometry_from_row(row: dict[str, str]) -> dict[str, float]:
    keys = (
        "predicted_theta_deg", "theta_half_width_deg", "predicted_radius_px", "radial_half_width_px",
        "predicted_center_x_px", "predicted_center_y_px", "unsigned_axis_center_deg", "unsigned_axis_half_width_deg",
        "response_length_min_px", "response_length_max_px", "response_width_min_px", "response_width_max_px",
    )
    return {key: float(row[key]) for key in keys}


def active_union(frame_rows: list[dict[str, str]], dilation_px: int) -> np.ndarray:
    union = np.zeros((FAN_HEIGHT, FAN_WIDTH), dtype=np.uint8)
    for row in frame_rows:
        if row["active_for_shell"] != "true":
            continue
        union |= condition_shell(geometry_from_row(row)).astype(np.uint8)
    if dilation_px > 0 and np.any(union):
        size = 2 * dilation_px + 1
        union = cv2.dilate(union, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))
    return union.astype(bool)


def estimate_pair_transport(
    previous: np.ndarray,
    current: np.ndarray,
    valid_mask: np.ndarray,
    excluded: np.ndarray,
    settings: dict[str, Any],
) -> dict[str, Any]:
    scale = float(settings["downsample"])
    width = max(64, int(round(previous.shape[1] * scale)))
    height = max(64, int(round(previous.shape[0] * scale)))
    previous_small = cv2.resize(previous, (width, height), interpolation=cv2.INTER_AREA)
    current_small = cv2.resize(current, (width, height), interpolation=cv2.INTER_AREA)
    valid_small = cv2.resize((valid_mask & ~excluded).astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)
    previous_hp = highpass(previous_small, float(settings["highpass_sigma_px_at_downsampled_scale"]))
    current_hp = highpass(current_small, float(settings["highpass_sigma_px_at_downsampled_scale"]))
    tile_rows = int(settings["tile_rows"])
    tile_cols = int(settings["tile_cols"])
    candidates: list[dict[str, Any]] = []
    for row_index in range(tile_rows):
        y1 = int(round(row_index * height / tile_rows))
        y2 = int(round((row_index + 1) * height / tile_rows))
        for col_index in range(tile_cols):
            x1 = int(round(col_index * width / tile_cols))
            x2 = int(round((col_index + 1) * width / tile_cols))
            tile_mask = valid_small[y1:y2, x1:x2]
            if tile_mask.size == 0 or float(np.mean(tile_mask)) < 0.55:
                continue
            left = previous_hp[y1:y2, x1:x2].copy()
            right = current_hp[y1:y2, x1:x2].copy()
            left[~tile_mask] = 0.0
            right[~tile_mask] = 0.0
            if float(np.std(left[tile_mask])) < 0.5 or float(np.std(right[tile_mask])) < 0.5:
                continue
            dx_small, dy_small, response = phase_shift(left, right)
            dx = dx_small / scale
            dy = dy_small / scale
            if response < float(settings["minimum_tile_response"]) or math.hypot(dx, dy) > float(settings["maximum_pair_shift_px"]):
                continue
            candidates.append({
                "dx": dx,
                "dy": dy,
                "response": response,
                "row": row_index,
                "col": col_index,
                "holdout": (row_index * tile_cols + col_index) % int(settings["holdout_tile_modulus"]) == 0,
            })
    fit = [item for item in candidates if not item["holdout"]]
    holdout = [item for item in candidates if item["holdout"]]
    fallback = False
    if len(fit) < int(settings["minimum_fit_tile_count"]):
        fit = candidates
        fallback = True
    if fit:
        dx = float(np.median([item["dx"] for item in fit]))
        dy = float(np.median([item["dy"] for item in fit]))
        response = float(np.median([item["response"] for item in fit]))
        method = "FROZEN_GRID_BACKGROUND_PHASE_MEDIAN_FALLBACK" if fallback else "ACTIVE_SHELL_EXCLUDED_BACKGROUND_PHASE_MEDIAN"
    else:
        full_mask = valid_small
        left = previous_hp.copy()
        right = current_hp.copy()
        left[~full_mask] = 0.0
        right[~full_mask] = 0.0
        dx_small, dy_small, response = phase_shift(left, right)
        dx = dx_small / scale
        dy = dy_small / scale
        require(math.hypot(dx, dy) <= float(settings["maximum_pair_shift_px"]) * 1.5, "transport fallback shift too large")
        method = "FROZEN_FULL_BACKGROUND_MASK_FALLBACK"
        fallback = True
    fit_dx_mad = float(np.median(np.abs(np.asarray([item["dx"] for item in fit]) - dx))) if fit else math.nan
    fit_dy_mad = float(np.median(np.abs(np.asarray([item["dy"] for item in fit]) - dy))) if fit else math.nan
    holdout_residuals = [math.hypot(item["dx"] - dx, item["dy"] - dy) for item in holdout]
    return {
        "dx": dx, "dy": dy, "response": response, "method": method,
        "eligible_tile_count": len(candidates), "fit_tile_count": len(fit), "holdout_tile_count": len(holdout),
        "fit_dx_mad_px": fit_dx_mad, "fit_dy_mad_px": fit_dy_mad,
        "holdout_residual_median_px": float(np.median(holdout_residuals)) if holdout_residuals else math.nan,
        "holdout_residual_max_px": float(np.max(holdout_residuals)) if holdout_residuals else math.nan,
        "fallback_used": fallback,
    }


def build_transports(
    images: list[np.ndarray],
    rows_by_frame: dict[int, list[dict[str, str]]],
    frames: list[int],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    valid = imaging_valid_mask()
    transports: list[dict[str, Any]] = [{
        "dx": 0.0, "dy": 0.0, "cumulative_dx": 0.0, "cumulative_dy": 0.0,
        "response": 1.0, "method": "REFERENCE_FRAME", "eligible_tile_count": 0,
        "fit_tile_count": 0, "holdout_tile_count": 0, "fit_dx_mad_px": 0.0,
        "fit_dy_mad_px": 0.0, "holdout_residual_median_px": 0.0,
        "holdout_residual_max_px": 0.0, "fallback_used": False,
    }]
    cumulative_x = cumulative_y = 0.0
    previous_excluded = active_union(rows_by_frame[frames[0]], int(settings["active_shell_exclusion_dilation_px"]))
    for index in range(1, len(frames)):
        current_excluded = active_union(rows_by_frame[frames[index]], int(settings["active_shell_exclusion_dilation_px"]))
        pair = estimate_pair_transport(images[index - 1], images[index], valid, previous_excluded | current_excluded, settings)
        cumulative_x += float(pair["dx"])
        cumulative_y += float(pair["dy"])
        pair["cumulative_dx"] = cumulative_x
        pair["cumulative_dy"] = cumulative_y
        transports.append(pair)
        previous_excluded = current_excluded
    return transports


def mask_bbox(mask: np.ndarray, padding: int = 8) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return 0, 0, FAN_WIDTH, FAN_HEIGHT
    return (
        max(0, int(xs.min()) - padding), max(0, int(ys.min()) - padding),
        min(FAN_WIDTH, int(xs.max()) + padding + 1), min(FAN_HEIGHT, int(ys.max()) + padding + 1),
    )


def determine_roi(target_rows: list[dict[str, str]], transports: list[dict[str, Any]], context_expansion: int) -> tuple[int, int, int, int]:
    union = np.zeros((FAN_HEIGHT, FAN_WIDTH), dtype=np.uint8)
    for row, transport in zip(target_rows, transports):
        geometry = geometry_from_row(row)
        shell = condition_shell(geometry, float(context_expansion)).astype(np.uint8)
        stable = warp_translation(shell, -float(transport["cumulative_dx"]), -float(transport["cumulative_dy"]), cv2.INTER_NEAREST)
        union |= stable
    return mask_bbox(union.astype(bool), padding=8)


def remove_small(mask: np.ndarray, minimum_area: int) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    output = np.zeros_like(mask, dtype=bool)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= minimum_area:
            output[labels == label] = True
    return output


def component_rows_for_frame(
    case_id: str,
    mode: str,
    frame: int,
    z: np.ndarray,
    positive: np.ndarray,
    geometric_shell: np.ndarray,
    other_shell: np.ndarray,
    geometry: dict[str, float],
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(positive.astype(np.uint8), connectivity=8)
    nodes: list[dict[str, Any]] = []
    retained = np.zeros_like(positive, dtype=bool)
    crossing = np.zeros_like(positive, dtype=bool)
    ambiguous = np.zeros_like(positive, dtype=bool)
    unresolved = np.zeros_like(positive, dtype=bool)
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < int(settings["minimum_component_area_px"]):
            continue
        component = labels == label
        target_inside = component & geometric_shell
        target_area = int(np.count_nonzero(target_inside))
        if target_area == 0:
            continue
        outside_fraction = 1.0 - target_area / max(area, 1)
        other_overlap = int(np.count_nonzero(component & other_shell))
        angle, length, width, centroid_x, centroid_y = component_orientation(target_inside)
        if not math.isfinite(angle) or length < 10.0 or length / max(width, 1.0) < 1.35:
            axis_compatibility = "DIRECTION_UNRESOLVED"
        elif angular_distance_mod180(angle, float(geometry["unsigned_axis_center_deg"])) <= float(geometry["unsigned_axis_half_width_deg"]):
            axis_compatibility = "DIRECTION_COMPATIBLE"
        else:
            axis_compatibility = "CLEARLY_INCOMPATIBLE_BACKGROUND_STRUCTURE"
        if length <= 0 or width <= 0:
            scale_compatibility = "SCALE_UNRESOLVED"
        elif float(geometry["response_length_min_px"]) <= length <= float(geometry["response_length_max_px"]) and float(geometry["response_width_min_px"]) <= width <= float(geometry["response_width_max_px"]):
            scale_compatibility = "SCALE_COMPATIBLE"
        elif length < 8.0 or width < 2.0:
            scale_compatibility = "SCALE_UNRESOLVED"
        else:
            scale_compatibility = "CLEARLY_INCOMPATIBLE_BACKGROUND_STRUCTURE"
        if outside_fraction >= float(settings["shell_crossing_background_fraction"]):
            classification = "SHELL_CROSSING_BACKGROUND"
            crossing |= component
        elif other_overlap > 0:
            classification = "IDENTITY_AMBIGUOUS_OVERLAP"
            ambiguous |= target_inside
            retained |= target_inside
        elif axis_compatibility == "CLEARLY_INCOMPATIBLE_BACKGROUND_STRUCTURE" and scale_compatibility == "CLEARLY_INCOMPATIBLE_BACKGROUND_STRUCTURE":
            classification = "CLEARLY_INCOMPATIBLE_BACKGROUND_STRUCTURE"
            unresolved |= target_inside
        elif "UNRESOLVED" in axis_compatibility or "UNRESOLVED" in scale_compatibility:
            classification = "UNRESOLVED_RESPONSE"
            unresolved |= target_inside
            retained |= target_inside
        else:
            classification = "CURRENT_STRONG_RESPONSE"
            retained |= target_inside
        node_id = f"S1D0-{mode.upper()}-{case_id}-{frame:06d}-{label:04d}"
        indices = np.flatnonzero(target_inside)
        nodes.append({
            "node_id": node_id, "case_id": case_id, "state_mode": mode, "sar_frame_index": frame,
            "component_label": label, "component_area_px": area, "target_shell_intersection_px": target_area,
            "shell_outside_fraction": outside_fraction, "other_identity_shell_overlap_px": other_overlap,
            "centroid_x_roi": centroid_x, "centroid_y_roi": centroid_y, "axis_deg": angle,
            "length_px": length, "width_px": width, "mean_robust_z": float(np.mean(z[component])),
            "max_robust_z": float(np.max(z[component])), "axis_compatibility": axis_compatibility,
            "length_compatibility": scale_compatibility, "width_compatibility": scale_compatibility,
            "shell_membership": "TARGET_SHELL_INTERSECTING", "temporal_continuity": "PENDING_GRAPH",
            "background_connectivity": "SHELL_CROSSING" if outside_fraction >= float(settings["shell_crossing_background_fraction"]) else "NOT_SHELL_CROSSING",
            "identity_overlap_status": "AMBIGUOUS_WITH_OTHER_ACTIVE_SHELL" if other_overlap > 0 else "NO_OTHER_ACTIVE_SHELL_OVERLAP",
            "response_class": classification, "weighted_score": "NOT_COMPUTED", "ranking": "NOT_COMPUTED",
            "_indices": indices,
        })
    return nodes, retained, crossing, ambiguous, unresolved


def sliding_frequency(stack: np.ndarray, index: int, window: int, mode: str) -> np.ndarray:
    if mode == "causal":
        start, end = max(0, index - window + 1), index + 1
    else:
        half = window // 2
        start, end = max(0, index - half), min(len(stack), index + half + 1)
    return np.mean(stack[start:end], axis=0)


def equal_area_baselines(shell: np.ndarray, geometry: dict[str, float], area: int, roi: tuple[int, int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    axis_strip = np.zeros_like(shell, dtype=bool)
    center_region = np.zeros_like(shell, dtype=bool)
    available = np.flatnonzero(shell)
    if area <= 0 or available.size == 0:
        return axis_strip, center_region
    count = min(area, available.size)
    y, x = np.indices(shell.shape)
    x1, y1, _, _ = roi
    center_x = float(geometry["predicted_center_x_px"]) - x1
    center_y = float(geometry["predicted_center_y_px"]) - y1
    angle = math.radians(float(geometry["unsigned_axis_center_deg"]))
    dx = x - center_x
    dy = y - center_y
    perpendicular = np.abs(-math.sin(angle) * dx + math.cos(angle) * dy)
    along = np.abs(math.cos(angle) * dx + math.sin(angle) * dy)
    axis_cost = perpendicular + 0.002 * along
    center_cost = (dx / max(float(geometry["response_length_max_px"]), 1.0)) ** 2 + (dy / max(float(geometry["response_width_max_px"]), 1.0)) ** 2
    axis_order = available[np.argpartition(axis_cost.flat[available], count - 1)[:count]]
    center_order = available[np.argpartition(center_cost.flat[available], count - 1)[:count]]
    axis_strip.flat[axis_order] = True
    center_region.flat[center_order] = True
    return axis_strip, center_region


def mask_iou(left_indices: np.ndarray, right_indices: np.ndarray) -> tuple[float, int]:
    intersection = int(np.intersect1d(left_indices, right_indices, assume_unique=True).size)
    union = int(left_indices.size + right_indices.size - intersection)
    return intersection / max(union, 1), intersection


def build_graph(nodes_by_frame: list[list[dict[str, Any]]], frames: list[int], relation: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    edges: list[dict[str, Any]] = []
    for index in range(len(frames) - 1):
        for left in nodes_by_frame[index]:
            if left["optical_lifecycle_state"] in {"ABSENT", "CLOSED"} or left["response_class"] in {"SHELL_CROSSING_BACKGROUND", "CLEARLY_INCOMPATIBLE_BACKGROUND_STRUCTURE"}:
                continue
            for right in nodes_by_frame[index + 1]:
                if right["optical_lifecycle_state"] in {"ABSENT", "CLOSED"} or right["response_class"] in {"SHELL_CROSSING_BACKGROUND", "CLEARLY_INCOMPATIBLE_BACKGROUND_STRUCTURE"}:
                    continue
                distance = math.hypot(float(right["centroid_x_roi"]) - float(left["centroid_x_roi"]), float(right["centroid_y_roi"]) - float(left["centroid_y_roi"]))
                iou, intersection = mask_iou(left["_indices"], right["_indices"])
                if distance > float(relation["maximum_centroid_distance_px"]) and iou < float(relation["minimum_mask_iou"]):
                    continue
                if iou < float(relation["minimum_mask_iou"]):
                    left_angle = float(left["axis_deg"])
                    right_angle = float(right["axis_deg"])
                    if math.isfinite(left_angle) and math.isfinite(right_angle) and angular_distance_mod180(left_angle, right_angle) > 45.0:
                        continue
                    length_ratio = max(float(left["length_px"]), float(right["length_px"])) / max(min(float(left["length_px"]), float(right["length_px"])), 1.0)
                    if length_ratio > 2.5:
                        continue
                edges.append({
                    "edge_id": f"S1D0-E-{left['node_id']}--{right['node_id']}",
                    "case_id": left["case_id"], "state_mode": left["state_mode"],
                    "from_node_id": left["node_id"], "to_node_id": right["node_id"],
                    "from_sar_frame": left["sar_frame_index"], "to_sar_frame": right["sar_frame_index"],
                    "stabilized_centroid_distance_px": distance, "mask_iou": iou, "mask_intersection_px": intersection,
                    "axis_change_deg": angular_distance_mod180(float(left["axis_deg"]), float(right["axis_deg"])) if math.isfinite(float(left["axis_deg"])) and math.isfinite(float(right["axis_deg"])) else math.nan,
                    "length_change_px": float(right["length_px"]) - float(left["length_px"]),
                    "width_change_px": float(right["width_px"]) - float(left["width_px"]),
                    "mean_robust_z_change": float(right["mean_robust_z"]) - float(left["mean_robust_z"]),
                    "from_axis_compatibility": left["axis_compatibility"], "to_axis_compatibility": right["axis_compatibility"],
                    "from_scale_compatibility": left["length_compatibility"], "to_scale_compatibility": right["length_compatibility"],
                    "from_identity_overlap": left["identity_overlap_status"], "to_identity_overlap": right["identity_overlap_status"],
                    "relation_semantics": "ADJACENT_FRAME_RELATION_NOT_WEIGHTED_SCORE",
                })
    incoming = Counter(edge["to_node_id"] for edge in edges)
    outgoing = Counter(edge["from_node_id"] for edge in edges)
    node_rows = []
    for frame_nodes in nodes_by_frame:
        for node in frame_nodes:
            item = {key: value for key, value in node.items() if not key.startswith("_")}
            item["temporal_continuity"] = (
                "SPLIT_OR_MERGE_RELATION" if incoming[node["node_id"]] > 1 or outgoing[node["node_id"]] > 1
                else "ADJACENT_RELATION" if incoming[node["node_id"]] + outgoing[node["node_id"]] > 0
                else "ISOLATED_OR_BIRTH_DEATH"
            )
            node_rows.append(item)
    return node_rows, edges


def build_events(
    case_id: str,
    mode: str,
    node_rows: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    frame_rows: list[dict[str, Any]],
    relation: dict[str, Any],
) -> list[dict[str, Any]]:
    nodes = {row["node_id"]: row for row in node_rows}
    incoming = Counter(edge["to_node_id"] for edge in edges)
    outgoing = Counter(edge["from_node_id"] for edge in edges)
    events: list[dict[str, Any]] = []
    event_counter = 0

    def add(event_type: str, frame: int, before: str, after: str, evidence: str, review: bool = True) -> None:
        nonlocal event_counter
        event_counter += 1
        state = next(row for row in frame_rows if int(row["sar_frame_index"]) == frame)
        events.append({
            "event_id": f"S1D0-EVENT-{mode.upper()}-{case_id}-{event_counter:04d}",
            "case_id": case_id, "state_mode": mode, "scene": state["scene"],
            "canonical_vehicle_id": state["canonical_vehicle_id"], "sar_frame_index": frame,
            "optical_left_frame": state["optical_left_frame"], "lifecycle_state": state["optical_lifecycle_state"],
            "event_type": event_type, "before_component_ids": before, "after_component_ids": after,
            "optical_theta_radius_scale_depth_trend": state["optical_condition_trend"],
            "matched_background_change": state["transport_holdout_and_background_change"],
            "global_gain_change": state["global_gain_change"], "evidence_status": evidence,
            "requires_manual_review": str(review).lower(), "unique_physical_mechanism_claimed": "false",
        })

    for node_id, node in nodes.items():
        if incoming[node_id] == 0 and node["response_class"] not in {"SHELL_CROSSING_BACKGROUND", "CLEARLY_INCOMPATIBLE_BACKGROUND_STRUCTURE"}:
            add("RESPONSE_BIRTH", int(node["sar_frame_index"]), "", node_id, "GRAPH_BIRTH_CANDIDATE")
        if outgoing[node_id] > 1:
            targets = ";".join(edge["to_node_id"] for edge in edges if edge["from_node_id"] == node_id)
            add("RESPONSE_SPLIT", int(node["sar_frame_index"]) + 1, node_id, targets, "ONE_TO_MANY_GRAPH_RELATION")
        if incoming[node_id] > 1:
            sources = ";".join(edge["from_node_id"] for edge in edges if edge["to_node_id"] == node_id)
            add("RESPONSE_MERGE", int(node["sar_frame_index"]), sources, node_id, "MANY_TO_ONE_GRAPH_RELATION")
    for edge in edges:
        left = nodes[edge["from_node_id"]]
        right = nodes[edge["to_node_id"]]
        if outgoing[left["node_id"]] != 1 or incoming[right["node_id"]] != 1:
            continue
        ratio = float(right["mean_robust_z"]) / max(float(left["mean_robust_z"]), 1e-6)
        if ratio >= float(relation["strength_change_ratio"]):
            add("RESPONSE_STRENGTHENING", int(right["sar_frame_index"]), left["node_id"], right["node_id"], "LOCAL_Z_INCREASE_WITH_GLOBAL_GAIN_RECORDED")
        elif ratio <= 1.0 / float(relation["strength_change_ratio"]):
            add("RESPONSE_WEAKENING", int(right["sar_frame_index"]), left["node_id"], right["node_id"], "LOCAL_Z_DECREASE_WITH_GLOBAL_GAIN_RECORDED")
        if float(edge["stabilized_centroid_distance_px"]) >= float(relation["migration_distance_px"]):
            add("RESPONSE_MIGRATION", int(right["sar_frame_index"]), left["node_id"], right["node_id"], "STABILIZED_CENTROID_CHANGE")
    nonempty = [int(row["joint_support_area_px"]) > 0 for row in frame_rows]
    for index in range(1, len(nonempty) - 1):
        if not nonempty[index] and nonempty[index - 1] and nonempty[index + 1]:
            add("TEMPORARY_LOSS", int(frame_rows[index]["sar_frame_index"]), "", "", "BOUNDED_SINGLE_FRAME_LOSS")
            add("REAPPEARANCE", int(frame_rows[index + 1]["sar_frame_index"]), "", "", "SUPPORT_REAPPEARS_AFTER_BOUNDED_LOSS")
    previous_ambiguous = False
    for row in frame_rows:
        ambiguous = int(row["identity_ambiguous_overlap_area_px"]) > 0
        if ambiguous and not previous_ambiguous:
            add("IDENTITY_OVERLAP_ONSET", int(row["sar_frame_index"]), "", "", "MULTI_IDENTITY_SHELL_OVERLAP_NO_WINNER")
        if previous_ambiguous and not ambiguous:
            add("IDENTITY_OVERLAP_RESOLUTION", int(row["sar_frame_index"]), "", "", "SHELL_OVERLAP_RESOLVED_BY_OPTICAL_LIFECYCLE")
        previous_ambiguous = ambiguous
        if row["optical_lifecycle_state"] == "EXITING" and int(row["joint_support_area_px"]) > 0:
            add("EXIT_DECAY", int(row["sar_frame_index"]), "", "", "EXIT_GATED_SUPPORT_RETAINED_WITH_BOUNDED_DECAY")
    return events


def display_rgb(gray: np.ndarray, low: float, high: float) -> np.ndarray:
    value = np.clip((gray.astype(np.float32) - low) / max(high - low, 1.0), 0.0, 1.0)
    return cv2.cvtColor((value * 255).astype(np.uint8), cv2.COLOR_GRAY2RGB)


def contour(image: np.ndarray, mask: np.ndarray, color: tuple[int, int, int], thickness: int = 2) -> None:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, color, thickness)


def create_review(
    case_id: str,
    mode: str,
    target_rows: list[dict[str, str]],
    stabilized: np.ndarray,
    shells: np.ndarray,
    joint: np.ndarray,
    maintenance: np.ndarray,
    ambiguous: np.ndarray,
    background: np.ndarray,
    output_dir: Path,
    visualization: dict[str, Any],
) -> list[Path]:
    indices = sorted(set(int(value) for value in np.linspace(0, len(target_rows) - 1, min(int(visualization["representative_frame_count"]), len(target_rows)))))
    paths: list[Path] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for page_index, start in enumerate(range(0, len(indices), 4), start=1):
        selected = indices[start : start + 4]
        figure, axes = plt.subplots(len(selected), 2, figsize=(12, 4 * len(selected)), squeeze=False)
        for axis_row, index in enumerate(selected):
            row = target_rows[index]
            optical_path = Path(row["sar_gray_path"]).parents[1]  # provenance only; optical path is reconstructed below
            view = display_rgb(stabilized[index], float(visualization["display_min"]), float(visualization["display_max"]))
            contour(view, shells[index], (0, 190, 255), 2)
            axes[axis_row, 0].imshow(view)
            axes[axis_row, 0].set_title(f"SAR {row['sar_frame_index']} stabilized | shell cyan | {row['optical_lifecycle_state']}")
            overlay = view.astype(np.float32)
            overlay[background] = 0.5 * overlay[background] + 0.5 * np.asarray([255, 60, 60])
            overlay[ambiguous[index]] = 0.4 * overlay[ambiguous[index]] + 0.6 * np.asarray([220, 60, 220])
            overlay[joint[index]] = 0.4 * overlay[joint[index]] + 0.6 * np.asarray([40, 230, 80])
            overlay[maintenance[index]] = 0.3 * overlay[maintenance[index]] + 0.7 * np.asarray([40, 220, 240])
            axes[axis_row, 1].imshow(np.clip(overlay, 0, 255).astype(np.uint8))
            axes[axis_row, 1].set_title(f"{mode}: joint green / maintained cyan / ambiguous magenta / background red")
            for axis in axes[axis_row]:
                axis.axis("off")
        figure.suptitle(f"{case_id} {mode} blind dynamic review (no target reference)")
        figure.tight_layout()
        path = output_dir / f"blind_dynamic_review_page_{page_index:02d}.png"
        figure.savefig(path, dpi=140)
        plt.close(figure)
        paths.append(path)
    return paths


def process_case(
    case_id: str,
    mode: str,
    case_rows: list[dict[str, str]],
    config: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    rows_by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in case_rows:
        rows_by_frame[int(row["sar_frame_index"])].append(row)
    frames = sorted(rows_by_frame)
    target_rows = [next(row for row in rows_by_frame[frame] if row["is_target_identity"] == "true") for frame in frames]
    images = [cv2.imread(row["sar_gray_path"], cv2.IMREAD_GRAYSCALE) for row in target_rows]
    require(all(image is not None for image in images), f"missing SAR image in {case_id}")
    images = [np.asarray(image, dtype=np.uint8) for image in images]
    transports = build_transports(images, rows_by_frame, frames, config["transport"])
    roi = determine_roi(target_rows, transports, int(config["response"]["context_expansion_px"]))
    x1, y1, x2, y2 = roi
    frame_count = len(frames)
    shape = (frame_count, y2 - y1, x2 - x1)
    stabilized = np.zeros(shape, dtype=np.uint8)
    geometric_shells = np.zeros(shape, dtype=bool)
    active_shells = np.zeros(shape, dtype=bool)
    contexts = np.zeros(shape, dtype=bool)
    valid_masks = np.zeros(shape, dtype=bool)
    other_shells = np.zeros(shape, dtype=bool)
    global_medians = np.zeros(frame_count, dtype=np.float32)
    valid_full = imaging_valid_mask()
    for index, (frame, row, image, transport) in enumerate(zip(frames, target_rows, images, transports)):
        dx = -float(transport["cumulative_dx"])
        dy = -float(transport["cumulative_dy"])
        geometry = geometry_from_row(row)
        geometric_full = condition_shell(geometry)
        context_full = condition_shell(geometry, float(config["response"]["context_expansion_px"]))
        active_full = geometric_full if row["active_for_shell"] == "true" else np.zeros_like(geometric_full)
        others_full = np.zeros_like(geometric_full, dtype=np.uint8)
        for other in rows_by_frame[frame]:
            if other["is_target_identity"] == "false" and other["active_for_shell"] == "true":
                others_full |= condition_shell(geometry_from_row(other)).astype(np.uint8)
        excluded = active_union(rows_by_frame[frame], int(config["transport"]["active_shell_exclusion_dilation_px"]))
        sample = image[valid_full & ~excluded]
        global_medians[index] = float(np.median(sample)) if sample.size else float(np.median(image[valid_full]))
        stabilized_full = warp_translation(image, dx, dy, cv2.INTER_LINEAR)
        stabilized[index] = stabilized_full[y1:y2, x1:x2]
        geometric_shells[index] = warp_translation(geometric_full.astype(np.uint8), dx, dy, cv2.INTER_NEAREST)[y1:y2, x1:x2].astype(bool)
        active_shells[index] = warp_translation(active_full.astype(np.uint8), dx, dy, cv2.INTER_NEAREST)[y1:y2, x1:x2].astype(bool)
        contexts[index] = warp_translation(context_full.astype(np.uint8), dx, dy, cv2.INTER_NEAREST)[y1:y2, x1:x2].astype(bool)
        valid_masks[index] = warp_translation(valid_full.astype(np.uint8), dx, dy, cv2.INTER_NEAREST)[y1:y2, x1:x2].astype(bool)
        other_shells[index] = warp_translation(others_full, dx, dy, cv2.INTER_NEAREST)[y1:y2, x1:x2].astype(bool)
    strong_positive = np.zeros(shape, dtype=bool)
    context_positive = np.zeros(shape, dtype=bool)
    weak_positive = np.zeros(shape, dtype=bool)
    retained_prelim = np.zeros(shape, dtype=bool)
    crossing_stack = np.zeros(shape, dtype=bool)
    ambiguous_stack = np.zeros(shape, dtype=bool)
    unresolved_stack = np.zeros(shape, dtype=bool)
    frame_medians: list[float] = []
    frame_mads: list[float] = []
    nodes_by_frame: list[list[dict[str, Any]]] = []
    for index, row in enumerate(target_rows):
        shell = geometric_shells[index] & valid_masks[index]
        context = contexts[index] & valid_masks[index]
        ring = context & ~shell
        sample = stabilized[index][ring]
        if sample.size < 500:
            sample = stabilized[index][context]
        median, mad = robust_median_mad(sample)
        z = (stabilized[index].astype(np.float32) - median) / max(1.0, 1.4826 * mad)
        z[~context] = -20.0
        positive = (z >= float(config["response"]["strong_response_robust_z"])) & context
        weak = (z >= float(config["response"]["weak_response_robust_z"])) & context
        nodes, retained, crossing, ambiguous, unresolved = component_rows_for_frame(
            case_id, mode, frames[index], z, positive, shell, other_shells[index], geometry_from_row(row), config["response"]
        )
        strong_positive[index] = positive & shell
        context_positive[index] = positive
        weak_positive[index] = weak & shell
        retained_prelim[index] = retained
        crossing_stack[index] = crossing
        ambiguous_stack[index] = ambiguous
        unresolved_stack[index] = unresolved
        frame_medians.append(median)
        frame_mads.append(mad)
        for node in nodes:
            node["optical_lifecycle_state"] = row["optical_lifecycle_state"]
        nodes_by_frame.append(nodes)
    inactive_indices = [index for index, row in enumerate(target_rows) if row["optical_lifecycle_state"] in {"ABSENT", "CLOSED"}]
    if inactive_indices:
        inactive_positive = np.sum(context_positive[inactive_indices], axis=0)
        inactive_presence = np.sum(contexts[inactive_indices] & valid_masks[inactive_indices], axis=0)
        prepost_frequency = inactive_positive / np.maximum(inactive_presence, 1)
    else:
        prepost_frequency = np.zeros(shape[1:], dtype=np.float32)
    crossing_frequency = np.mean(crossing_stack, axis=0)
    inside_background = remove_small(
        prepost_frequency >= float(config["response"]["background_pre_or_post_frequency"]),
        int(config["response"]["minimum_component_area_px"]),
    )
    shell_crossing_background = remove_small(
        crossing_frequency >= float(config["response"]["background_pre_or_post_frequency"]),
        int(config["response"]["minimum_component_area_px"]),
    )
    background_static = inside_background | shell_crossing_background
    independent = retained_prelim & active_shells & ~background_static
    sliding = np.zeros_like(independent)
    lifecycle_persistent = np.zeros_like(independent)
    intermittent = np.zeros_like(independent)
    maintenance = np.zeros_like(independent)
    joint = np.zeros_like(independent)
    maintenance_age = np.zeros(frame_count, dtype=np.int32)
    active_indices: list[int] = []
    previous_support = np.zeros(shape[1:], dtype=bool)
    previous_age = 0
    radius = int(config["response"]["maintenance_neighbourhood_px"])
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    full_active_frequency = np.mean(independent[[i for i, row in enumerate(target_rows) if row["active_for_shell"] == "true"]], axis=0)
    for index, row in enumerate(target_rows):
        state = row["optical_lifecycle_state"]
        if row["active_for_shell"] == "true":
            active_indices.append(index)
        frequency = sliding_frequency(independent, index, int(config["response"]["sliding_window_frames"]), mode)
        sliding[index] = (frequency >= float(config["response"]["sliding_persistent_frequency"])) & active_shells[index]
        if mode == "causal":
            lifecycle_frequency = np.mean(independent[active_indices], axis=0) if active_indices else np.zeros(shape[1:], dtype=np.float32)
        else:
            lifecycle_frequency = full_active_frequency
        lifecycle_persistent[index] = (lifecycle_frequency >= float(config["response"]["lifecycle_persistent_frequency"])) & active_shells[index]
        intermittent[index] = (frequency >= 0.20) & ~sliding[index] & active_shells[index]
        if state in {"ABSENT", "CLOSED"}:
            previous_support[:] = False
            previous_age = 0
            continue
        if mode == "causal":
            previous_neighbourhood = cv2.dilate(previous_support.astype(np.uint8), kernel).astype(bool)
            persistence_prior = sliding[index] | lifecycle_persistent[index]
            maintained = previous_neighbourhood & persistence_prior & weak_positive[index] & ~independent[index] & active_shells[index]
            if np.any(maintained) and previous_age < int(config["response"]["maximum_maintenance_age_frames"]):
                maintenance[index] = maintained
                previous_age += 1
            else:
                previous_age = 0
        else:
            temporal_radius = int(config["response"]["maintenance_radius_frames"])
            start, end = max(0, index - temporal_radius), min(frame_count, index + temporal_radius + 1)
            neighbour = np.any(independent[start:end], axis=0)
            neighbour = cv2.dilate(neighbour.astype(np.uint8), kernel).astype(bool)
            persistence_prior = sliding[index] | lifecycle_persistent[index]
            maintenance[index] = neighbour & persistence_prior & weak_positive[index] & ~independent[index] & active_shells[index]
            previous_age = 1 if np.any(maintenance[index]) else 0
        maintenance_age[index] = previous_age
        current = independent[index] | maintenance[index] | (sliding[index] & weak_positive[index])
        if state == "EXITING" and np.any(previous_support):
            allowed = cv2.dilate(previous_support.astype(np.uint8), kernel).astype(bool)
            current &= allowed
        current &= active_shells[index] & ~background_static
        joint[index] = remove_small(current, int(config["response"]["minimum_component_area_px"]))
        previous_support = joint[index].copy()
    axis_baseline = np.zeros_like(joint)
    center_baseline = np.zeros_like(joint)
    for index, row in enumerate(target_rows):
        axis_baseline[index], center_baseline[index] = equal_area_baselines(
            active_shells[index], geometry_from_row(row), int(np.count_nonzero(joint[index])), roi
        )
    node_rows, edges = build_graph(nodes_by_frame, frames, config["relation"])
    transport_rows = []
    frame_rows = []
    for index, (frame, row, transport) in enumerate(zip(frames, target_rows, transports)):
        global_change = float(global_medians[index] - global_medians[index - 1]) if index else 0.0
        condition_trend = (
            f"theta={float(row['predicted_theta_deg']):.3f};radius={float(row['predicted_radius_px']):.3f};"
            f"height={float(row['optical_height_px']):.3f};depth={float(row['optical_depth_median_proxy']):.3f}"
        )
        transport_rows.append({
            "case_id": case_id, "state_mode": mode, "scene": row["scene"], "sar_frame_index": frame,
            "pair_dx_px": transport["dx"], "pair_dy_px": transport["dy"],
            "cumulative_dx_px": transport["cumulative_dx"], "cumulative_dy_px": transport["cumulative_dy"],
            "transport_response": transport["response"], "transport_method": transport["method"],
            "eligible_background_tile_count": transport["eligible_tile_count"], "fit_background_tile_count": transport["fit_tile_count"],
            "holdout_background_tile_count": transport["holdout_tile_count"], "fit_dx_mad_px": transport["fit_dx_mad_px"],
            "fit_dy_mad_px": transport["fit_dy_mad_px"], "holdout_residual_median_px": transport["holdout_residual_median_px"],
            "holdout_residual_max_px": transport["holdout_residual_max_px"], "fallback_used": str(transport["fallback_used"]).lower(),
            "active_identity_count": row["active_identity_count_in_scene"], "active_shells_excluded": "true",
        })
        if row["optical_lifecycle_state"] in {"ABSENT", "CLOSED"}:
            sar_state = "NO_IDENTITY_SUPPORT"
        elif np.count_nonzero(joint[index]) == 0:
            sar_state = "NO_VISIBLE_RESPONSE"
        elif np.count_nonzero(maintenance[index]) >= max(1, np.count_nonzero(joint[index]) // 2):
            sar_state = "TEMPORALLY_MAINTAINED_WEAK_RESPONSE"
        else:
            sar_state = "VISIBLE_RESPONSE_ACTIVE"
        frame_rows.append({
            "case_id": case_id, "case_roles": row["case_roles"], "state_mode": mode,
            "scene": row["scene"], "canonical_vehicle_id": row["target_canonical_vehicle_id"],
            "sar_frame_index": frame, "optical_left_frame": row["optical_left_frame"],
            "optical_lifecycle_state": row["optical_lifecycle_state"], "sar_response_state": sar_state,
            "state_transition_reason": row["state_transition_reason"], "active_identity_count": row["active_identity_count_in_scene"],
            "maintenance_age_frames": int(maintenance_age[index]),
            "uncertainty_expansion": float(row["theta_half_width_deg"]) / 8.0,
            "closure_reason": row["state_transition_reason"] if row["optical_lifecycle_state"] == "CLOSED" else "",
            "current_strong_response_area_px": int(np.count_nonzero(independent[index])),
            "current_weak_response_area_px": int(np.count_nonzero(weak_positive[index] & active_shells[index] & ~independent[index])),
            "sliding_persistent_response_area_px": int(np.count_nonzero(sliding[index])),
            "lifecycle_persistent_response_area_px": int(np.count_nonzero(lifecycle_persistent[index])),
            "intermittent_response_area_px": int(np.count_nonzero(intermittent[index])),
            "temporally_maintained_response_area_px": int(np.count_nonzero(maintenance[index])),
            "inside_shell_persistent_background_area_px": int(np.count_nonzero(inside_background & geometric_shells[index])),
            "shell_crossing_background_area_px": int(np.count_nonzero(shell_crossing_background & geometric_shells[index])),
            "identity_ambiguous_overlap_area_px": int(np.count_nonzero(ambiguous_stack[index])),
            "unresolved_response_area_px": int(np.count_nonzero(unresolved_stack[index])),
            "joint_support_area_px": int(np.count_nonzero(joint[index])),
            "equal_area_axis_strip_area_px": int(np.count_nonzero(axis_baseline[index])),
            "equal_area_center_region_area_px": int(np.count_nonzero(center_baseline[index])),
            "global_gain_median": float(global_medians[index]), "global_gain_change": global_change,
            "local_background_median": frame_medians[index], "local_background_mad": frame_mads[index],
            "optical_condition_trend": condition_trend,
            "transport_holdout_and_background_change": f"holdout={transport['holdout_residual_median_px']};local_median={frame_medians[index]}",
            "target_reference_used_for_inference": "false", "candidate_bank_generated": "false",
            "weighted_score_or_ranking_used": "false", "forced_component_winner": "false", "unique_box_generated": "false",
        })
    events = build_events(case_id, mode, node_rows, edges, frame_rows, config["relation"])
    case_dir = output_root / case_id / mode
    case_dir.mkdir(parents=True, exist_ok=True)
    npz_path = case_dir / "dynamic_state_masks.npz"
    np.savez_compressed(
        npz_path, frames=np.asarray(frames, np.int32), roi=np.asarray(roi, np.int32),
        cumulative_transport=np.asarray([[row["cumulative_dx"], row["cumulative_dy"]] for row in transports], np.float32),
        geometric_shell=geometric_shells.astype(np.uint8), active_shell=active_shells.astype(np.uint8),
        current_strong_response=independent.astype(np.uint8), current_weak_response=(weak_positive & active_shells & ~independent).astype(np.uint8),
        sliding_persistent_response=sliding.astype(np.uint8), lifecycle_persistent_response=lifecycle_persistent.astype(np.uint8),
        intermittent_response=intermittent.astype(np.uint8), temporally_maintained_response=maintenance.astype(np.uint8),
        inside_shell_persistent_background=inside_background.astype(np.uint8), shell_crossing_background=shell_crossing_background.astype(np.uint8),
        identity_ambiguous_overlap=ambiguous_stack.astype(np.uint8), unresolved_response=unresolved_stack.astype(np.uint8),
        joint_support=joint.astype(np.uint8), equal_area_axis_strip=axis_baseline.astype(np.uint8),
        equal_area_center_region=center_baseline.astype(np.uint8), global_gain_median=global_medians,
    )
    review_paths = create_review(
        case_id, mode, target_rows, stabilized, geometric_shells, joint, maintenance, ambiguous_stack,
        background_static, case_dir / "blind_review", config["visualization"],
    )
    summary = {
        "case_id": case_id, "state_mode": mode, "scene": target_rows[0]["scene"],
        "canonical_vehicle_id": target_rows[0]["target_canonical_vehicle_id"], "frame_count": frame_count,
        "frame_range": [frames[0], frames[-1]], "roi": list(roi),
        "active_frame_count": sum(row["active_for_shell"] == "true" for row in target_rows),
        "joint_nonempty_frame_count": sum(np.count_nonzero(mask) > 0 for mask in joint),
        "closed_support_nonzero_frame_count": sum(np.count_nonzero(joint[index]) > 0 for index, row in enumerate(target_rows) if row["optical_lifecycle_state"] == "CLOSED"),
        "fallback_transport_frame_count": sum(bool(row["fallback_used"]) for row in transports),
        "transport_holdout_residual_median_px": float(np.nanmedian([row["holdout_residual_median_px"] for row in transports])),
        "mean_joint_support_area_px": float(np.mean([np.count_nonzero(mask) for mask in joint])),
        "mean_axis_baseline_area_px": float(np.mean([np.count_nonzero(mask) for mask in axis_baseline])),
        "mean_center_baseline_area_px": float(np.mean([np.count_nonzero(mask) for mask in center_baseline])),
        "ambiguous_frame_count": sum(np.count_nonzero(mask) > 0 for mask in ambiguous_stack),
        "node_count": len(node_rows), "edge_count": len(edges), "event_count": len(events),
        "npz_path": str(npz_path), "review_paths": [str(path) for path in review_paths],
        "target_reference_used_for_inference": False, "weighted_score_or_ranking_used": False,
        "forced_component_winner": False, "unique_box_generated": False,
    }
    write_json(case_dir / "inference_summary.json", summary)
    return {
        "transport_rows": transport_rows, "frame_rows": frame_rows, "node_rows": node_rows,
        "edges": edges, "events": events, "review_paths": review_paths, "npz_path": npz_path,
        "summary_path": case_dir / "inference_summary.json", "summary": summary,
    }


def run(mode: str, config_path: Path) -> None:
    config = load_json(config_path)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    condition_path = resolve(config["sources"]["lifecycle_conditions"])
    leak_audit = leakage_guard(config_path, condition_path)
    conditions = read_csv(condition_path)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in conditions:
        grouped[row["case_id"]].append(row)
    output_root = Path(config["output_root"])
    all_transport: list[dict[str, Any]] = []
    all_frames: list[dict[str, Any]] = []
    all_nodes: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for case_id in sorted(grouped):
        result = process_case(case_id, mode, grouped[case_id], config, output_root)
        results.append(result)
        all_transport.extend(result["transport_rows"])
        all_frames.extend(result["frame_rows"])
        all_nodes.extend(result["node_rows"])
        all_edges.extend(result["edges"])
        all_events.extend(result["events"])
        for path in result["review_paths"]:
            review_rows.append({
                "case_id": case_id, "state_mode": mode, "artifact_path": str(path),
                "artifact_sha256": sha256_file(path), "contains_target_reference": "false",
                "review_status": "pending_direct_review", "selection_basis": "uniform_lifecycle_sampling",
            })
    write_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_transport_diagnostics.csv", all_transport)
    write_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_frame_states.csv", all_frames)
    write_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_response_graph_nodes.csv", all_nodes)
    write_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_response_graph_edges.csv", all_edges)
    write_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_response_events.csv", all_events)
    write_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_blind_review_manifest.csv", review_rows)
    summary = {
        "version": config["version"], "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state, "state_mode": "CAUSAL_FORWARD_STATE" if mode == "causal" else "OFFLINE_BIDIRECTIONAL_STATE",
        "config_sha256": sha256_file(config_path), "condition_sha256": sha256_file(condition_path),
        "leakage_audit": leak_audit, "cases": [result["summary"] for result in results],
        "target_reference_used_for_inference": False, "candidate_bank_generated": False,
        "weighted_score_or_ranking_used": False, "forced_component_winner": False, "unique_box_generated": False,
    }
    write_json(REPORT_DIR / f"oty2_s1d0_{mode}_inference_summary_20260717.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main(default_mode: str | None = None) -> None:
    args = parse_args(default_mode)
    config_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config
    run(args.mode, config_path)


if __name__ == "__main__":
    main()
