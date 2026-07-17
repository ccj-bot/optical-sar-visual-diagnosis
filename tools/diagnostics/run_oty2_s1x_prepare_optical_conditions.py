#!/usr/bin/env python3
from __future__ import annotations

"""Prepare S1X optical conditions and a calibration-only geometry proxy.

This entry may read the explicitly isolated calibration vehicle reference rows.
The inference entry is separate and never imports or reads that reference source.
"""

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from oty2_s1x_common import (
    CONFIG_DIR,
    MANIFEST_DIR,
    REPO_ROOT,
    REPORT_DIR,
    aggregate_file_hash,
    fan_xy,
    fmt,
    load_json,
    read_csv,
    row_hash,
    sha256_file,
    verify_git_gate,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = CONFIG_DIR / "oty2_s1x_input_preparation.json"
CALIBRATION_OUTPUT = CONFIG_DIR / "oty2_s1x_optical_condition_calibration.json"
CONDITION_OUTPUT = MANIFEST_DIR / "oty2_s1x_optical_condition_frames.csv"
LINEAGE_OUTPUT = MANIFEST_DIR / "oty2_s1x_optical_condition_input_lineage.csv"
SUMMARY_OUTPUT = REPORT_DIR / "oty2_s1x_input_preparation_summary_20260717.json"
MISSING_REPORT = REPORT_DIR / "oty2_s1x_missing_inputs_and_boundaries_20260717.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO_ROOT / path


def fit_line(x: np.ndarray, y: np.ndarray) -> tuple[float, float, np.ndarray]:
    design = np.column_stack([x, np.ones_like(x)])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    prediction = design @ beta
    return float(beta[0]), float(beta[1]), prediction


def regression_summary(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    slope, intercept, prediction = fit_line(x, y)
    residual = prediction - y
    return {
        "slope": slope,
        "intercept": intercept,
        "median_abs_error": float(np.median(np.abs(residual))),
        "p90_abs_error": float(np.percentile(np.abs(residual), 90)),
        "p95_abs_error": float(np.percentile(np.abs(residual), 95)),
        "max_abs_error": float(np.max(np.abs(residual))),
        "residual_p05": float(np.percentile(residual, 5)),
        "residual_p95": float(np.percentile(residual, 95)),
        "pearson": float(np.corrcoef(x, y)[0, 1]),
    }


def positive_depth_values(depth: np.ndarray) -> np.ndarray:
    values = np.asarray(depth, dtype=np.float64).reshape(-1)
    return values[np.isfinite(values) & (values > 0)]


def sample_depth(depth_path: Path, bbox: tuple[float, float, float, float]) -> dict[str, float]:
    depth = np.load(depth_path)
    x1, y1, x2, y2 = bbox
    left = max(0, int(math.floor(x1)))
    top = max(0, int(math.floor(y1)))
    right = min(depth.shape[1], int(math.ceil(x2)))
    bottom = min(depth.shape[0], int(math.ceil(y2)))
    inset_x = max(1, int(round(0.15 * max(1, right - left))))
    inset_y = max(1, int(round(0.15 * max(1, bottom - top))))
    inner_left = min(right - 1, left + inset_x)
    inner_right = max(left + 1, right - inset_x)
    inner_top = min(bottom - 1, top + inset_y)
    inner_bottom = max(top + 1, bottom - inset_y)
    values = positive_depth_values(depth[inner_top:inner_bottom, inner_left:inner_right])
    if values.size == 0:
        return {"p25": math.nan, "median": math.nan, "p75": math.nan, "mad": math.nan, "count": 0}
    median = float(np.median(values))
    return {
        "p25": float(np.percentile(values, 25)),
        "median": median,
        "p75": float(np.percentile(values, 75)),
        "mad": float(np.median(np.abs(values - median))),
        "count": int(values.size),
    }


def bbox_from_state(row: dict[str, str]) -> tuple[float, float, float, float]:
    return (
        float(row["reference_bbox_x1"]),
        float(row["reference_bbox_y1"]),
        float(row["reference_bbox_x2"]),
        float(row["reference_bbox_y2"]),
    )


def build_calibration(
    config: dict[str, Any],
    scene_config: dict[str, Any],
    state_rows: list[dict[str, str]],
    reference_rows: list[dict[str, str]],
) -> tuple[dict[str, Any], list[Path]]:
    calibration = config["calibration"]
    scene = calibration["scene"]
    vehicle_id = calibration["vehicle_id"]
    forbidden = set(calibration["forbidden_target_vehicle_ids"])
    if vehicle_id in forbidden:
        raise RuntimeError("calibration vehicle overlaps a target vehicle")
    state_by_frame = {
        int(row["frame_index"]): row
        for row in state_rows
        if row["scene"] == scene
        and row["canonical_vehicle_id"] == vehicle_id
        and row["reference_bbox_available"].lower() == "true"
    }
    scene_paths = scene_config["scenes"][scene]["paths"]
    depth_dir = Path(scene_paths["depth_dir"])
    selected: list[dict[str, float | int | str]] = []
    depth_paths: set[Path] = set()
    target_ids_observed: set[str] = set()
    for row in reference_rows:
        row_vehicle = row.get("canonical_vehicle_id", "")
        if row_vehicle in forbidden:
            target_ids_observed.add(row_vehicle)
        if row_vehicle != vehicle_id or row.get("scene") != scene:
            continue
        sar_frame = int(row["sar_frame_index"])
        if not calibration["sar_frame_start"] <= sar_frame <= calibration["sar_frame_end"]:
            continue
        if row["gt_quality_status"] not in set(calibration["allowed_reference_quality"]):
            continue
        optical_frame = int(row["optical_frame_index"])
        state = state_by_frame.get(optical_frame)
        if state is None or state["visibility_state"] != calibration["required_optical_visibility"]:
            continue
        bbox = bbox_from_state(state)
        depth_path = depth_dir / f"{optical_frame:06d}_depth.npy"
        if not depth_path.is_file():
            raise RuntimeError(f"missing calibration depth: {depth_path}")
        depth = sample_depth(depth_path, bbox)
        depth_paths.add(depth_path)
        x1, y1, x2, y2 = bbox
        long_side = max(float(row["bbox_width_px"]), float(row["bbox_height_px"]))
        short_side = min(float(row["bbox_width_px"]), float(row["bbox_height_px"]))
        selected.append(
            {
                "sar_frame": sar_frame,
                "optical_frame": optical_frame,
                "optical_center_x": 0.5 * (x1 + x2),
                "optical_center_y": 0.5 * (y1 + y2),
                "optical_bottom_y": y2,
                "optical_width": x2 - x1,
                "optical_height": y2 - y1,
                "depth_median": depth["median"],
                "depth_mad": depth["mad"],
                "sar_theta": float(row["center_theta_deg"]),
                "sar_radius": float(row["center_radius_px"]),
                "sar_response_long_side": long_side,
                "sar_response_short_side": short_side,
            }
        )
    if len(selected) < 20:
        raise RuntimeError(f"insufficient calibration rows: {len(selected)}")
    numeric = {
        key: np.asarray([float(row[key]) for row in selected], dtype=np.float64)
        for key in selected[0]
        if key not in {"sar_frame", "optical_frame"}
    }
    theta_fit = regression_summary(numeric["optical_center_x"], numeric["sar_theta"])
    radius_fit = regression_summary(numeric["optical_height"], numeric["sar_radius"])
    depth_fit = regression_summary(numeric["depth_median"], numeric["sar_radius"])
    calibration_output = {
        "version": "OTY2-S1X-independent-calibration-v1",
        "scene": scene,
        "calibration_vehicle_id": vehicle_id,
        "calibration_role": "independent_calibration_only_not_discovery_or_replay",
        "forbidden_target_vehicle_ids": sorted(forbidden),
        "target_vehicle_rows_loaded_for_fit": 0,
        "target_vehicle_ids_present_in_source_but_excluded": sorted(target_ids_observed),
        "row_count": len(selected),
        "sar_frame_range": [min(int(row["sar_frame"]) for row in selected), max(int(row["sar_frame"]) for row in selected)],
        "optical_frame_range": [min(int(row["optical_frame"]) for row in selected), max(int(row["optical_frame"]) for row in selected)],
        "theta_from_optical_center_x": theta_fit,
        "radius_from_optical_bbox_height": radius_fit,
        "depth_to_radius_diagnostic_not_used_for_center": depth_fit,
        "response_size_reference": {
            "long_side_p10_px": float(np.percentile(numeric["sar_response_long_side"], 10)),
            "long_side_median_px": float(np.median(numeric["sar_response_long_side"])),
            "long_side_p90_px": float(np.percentile(numeric["sar_response_long_side"], 90)),
            "short_side_p10_px": float(np.percentile(numeric["sar_response_short_side"], 10)),
            "short_side_median_px": float(np.median(numeric["sar_response_short_side"])),
            "short_side_p90_px": float(np.percentile(numeric["sar_response_short_side"], 90)),
        },
        "uncertainty_interpretation": "single-scene single-vehicle research proxy; target shells use additional cross-vehicle allowances",
        "depth_lineage_status": "derived_optical_sidecar_generator_unresolved_research_proxy_only",
        "metric_grid_status": "display_fan_pixels_only_metric_grid_unresolved",
        "source_reference_hash": row_hash(selected),
    }
    return calibration_output, sorted(depth_paths)


def interpolate_number(left: float, right: float, ratio: float) -> float:
    return (1.0 - ratio) * left + ratio * right


def combined_visibility(left: dict[str, str], right: dict[str, str]) -> str:
    values = {left["visibility_state"], right["visibility_state"]}
    if values == {"full_visible"}:
        return "full_visible"
    if "partial_visible" in values:
        return "partial_visible"
    if "fully_occluded" in values:
        return "fully_occluded"
    return ";".join(sorted(values))


def build_conditions(
    config: dict[str, Any],
    scene_config: dict[str, Any],
    state_rows: list[dict[str, str]],
    time_rows: list[dict[str, str]],
    calibration: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[Path]]:
    state_index = {
        (row["scene"], row["canonical_vehicle_id"], int(row["frame_index"])): row
        for row in state_rows
    }
    time_index = {(row["scene"], int(row["sar_frame_index"])): row for row in time_rows}
    uncertainty = config["uncertainty"]
    theta_fit = calibration["theta_from_optical_center_x"]
    radius_fit = calibration["radius_from_optical_bbox_height"]
    depth_fit = calibration["depth_to_radius_diagnostic_not_used_for_center"]
    theta_half = max(
        float(uncertainty["theta_min_half_width_deg"]),
        float(theta_fit["p95_abs_error"]) + float(uncertainty["theta_cross_vehicle_allowance_deg"]),
    )
    radial_proxy_allowance = (
        max(float(radius_fit["p95_abs_error"]), float(depth_fit["p95_abs_error"]))
        + float(uncertainty["radial_cross_vehicle_allowance_px"])
    )
    condition_rows: list[dict[str, Any]] = []
    input_paths: set[Path] = set()
    previous_by_window: dict[str, tuple[float, float, float]] = {}
    for window in config["target_windows"]:
        scene = window["scene"]
        vehicle_id = window["vehicle_id"]
        if vehicle_id in {calibration["calibration_vehicle_id"]}:
            raise RuntimeError("target window overlaps calibration vehicle")
        scene_paths = scene_config["scenes"][scene]["paths"]
        optical_dir = Path(scene_paths["optical_frames_dir"])
        depth_dir = Path(scene_paths["depth_dir"])
        sar_dir = Path(scene_paths["sar_gray_frames_dir"])
        for sar_frame in range(int(window["sar_frame_start"]), int(window["sar_frame_end"]) + 1):
            time_row = time_index.get((scene, sar_frame))
            if time_row is None:
                raise RuntimeError(f"missing time map: {scene} {sar_frame}")
            left_frame = int(time_row["optical_left_frame"])
            right_frame = int(time_row["optical_right_frame"])
            ratio = float(time_row["optical_interpolation_ratio"])
            left = state_index.get((scene, vehicle_id, left_frame))
            right = state_index.get((scene, vehicle_id, right_frame))
            if left is None or right is None:
                raise RuntimeError(f"missing optical state: {scene} {vehicle_id} {left_frame}/{right_frame}")
            if left["reference_bbox_available"].lower() != "true" or right["reference_bbox_available"].lower() != "true":
                raise RuntimeError(f"missing optical bbox in target window: {scene} {vehicle_id} {sar_frame}")
            left_bbox = bbox_from_state(left)
            right_bbox = bbox_from_state(right)
            bbox = tuple(interpolate_number(a, b, ratio) for a, b in zip(left_bbox, right_bbox))
            x1, y1, x2, y2 = bbox
            optical_center_x = 0.5 * (x1 + x2)
            optical_center_y = 0.5 * (y1 + y2)
            optical_width = x2 - x1
            optical_height = y2 - y1
            left_depth_path = depth_dir / f"{left_frame:06d}_depth.npy"
            right_depth_path = depth_dir / f"{right_frame:06d}_depth.npy"
            left_depth = sample_depth(left_depth_path, left_bbox)
            right_depth = sample_depth(right_depth_path, right_bbox)
            depth_median = interpolate_number(left_depth["median"], right_depth["median"], ratio)
            depth_mad = interpolate_number(left_depth["mad"], right_depth["mad"], ratio)
            predicted_theta = float(theta_fit["slope"]) * optical_center_x + float(theta_fit["intercept"])
            predicted_radius_height = float(radius_fit["slope"]) * optical_height + float(radius_fit["intercept"])
            predicted_radius_depth = float(depth_fit["slope"]) * depth_median + float(depth_fit["intercept"])
            radial_lower = max(0.0, min(predicted_radius_height, predicted_radius_depth) - radial_proxy_allowance)
            radial_upper = min(1332.7, max(predicted_radius_height, predicted_radius_depth) + radial_proxy_allowance)
            predicted_radius = 0.5 * (radial_lower + radial_upper)
            radial_half = max(float(uncertainty["radial_min_half_width_px"]), 0.5 * (radial_upper - radial_lower))
            visibility = combined_visibility(left, right)
            multiplier = float(uncertainty["partial_visibility_multiplier"]) if visibility != "full_visible" else 1.0
            frame_theta_half = theta_half * multiplier
            frame_radial_half = radial_half * multiplier
            center_x, center_y = fan_xy(predicted_radius, predicted_theta)
            center_x_value, center_y_value = float(center_x), float(center_y)
            previous = previous_by_window.get(window["window_id"])
            if previous is None:
                theta_delta = 0.0
                radius_delta = 0.0
                depth_delta = 0.0
            else:
                theta_delta = predicted_theta - previous[0]
                radius_delta = predicted_radius - previous[1]
                depth_delta = depth_median - previous[2]
            previous_by_window[window["window_id"]] = (predicted_theta, predicted_radius, depth_median)
            optical_path_left = optical_dir / f"{left_frame:06d}.png"
            optical_path_right = optical_dir / f"{right_frame:06d}.png"
            sar_path = sar_dir / f"{sar_frame:06d}.png"
            for path in (left_depth_path, right_depth_path, optical_path_left, optical_path_right, sar_path):
                if not path.is_file():
                    raise RuntimeError(f"missing target input: {path}")
                input_paths.add(path)
            condition_rows.append(
                {
                    "condition_id": f"S1X-{window['window_id']}-{sar_frame:06d}",
                    "window_id": window["window_id"],
                    "window_role": window["role"],
                    "scene": scene,
                    "canonical_vehicle_id": vehicle_id,
                    "sar_frame_index": sar_frame,
                    "sar_time_sec": time_row["sar_time_sec"],
                    "sar_gray_path": str(sar_path),
                    "sar_gray_sha256": sha256_file(sar_path),
                    "optical_left_frame": left_frame,
                    "optical_right_frame": right_frame,
                    "optical_interpolation_ratio": fmt(ratio),
                    "optical_left_path": str(optical_path_left),
                    "optical_right_path": str(optical_path_right),
                    "optical_bbox_x1": fmt(x1),
                    "optical_bbox_y1": fmt(y1),
                    "optical_bbox_x2": fmt(x2),
                    "optical_bbox_y2": fmt(y2),
                    "optical_center_x_px": fmt(optical_center_x),
                    "optical_center_y_px": fmt(optical_center_y),
                    "optical_bottom_contact_y_px": fmt(y2),
                    "optical_width_px": fmt(optical_width),
                    "optical_height_px": fmt(optical_height),
                    "optical_visibility_state": visibility,
                    "optical_identity_source": "P1E_CANONICAL_OPTICAL_BENCHMARK_NOT_RUNTIME_OUTPUT",
                    "optical_depth_left_path": str(left_depth_path),
                    "optical_depth_right_path": str(right_depth_path),
                    "optical_depth_median_proxy": fmt(depth_median),
                    "optical_depth_mad_proxy": fmt(depth_mad),
                    "depth_generator_lineage": "UNRESOLVED_DERIVED_OPTICAL_SIDECAR",
                    "predicted_theta_deg": fmt(predicted_theta),
                    "theta_half_width_deg": fmt(frame_theta_half),
                    "predicted_radius_px": fmt(predicted_radius),
                    "radial_half_width_px": fmt(frame_radial_half),
                    "predicted_radius_from_optical_height_px": fmt(predicted_radius_height),
                    "predicted_radius_from_depth_proxy_px": fmt(predicted_radius_depth),
                    "radial_proxy_disagreement_px": fmt(abs(predicted_radius_height - predicted_radius_depth)),
                    "radial_interval_lower_px": fmt(max(0.0, predicted_radius - frame_radial_half)),
                    "radial_interval_upper_px": fmt(min(1332.7, predicted_radius + frame_radial_half)),
                    "predicted_center_x_px": fmt(center_x_value),
                    "predicted_center_y_px": fmt(center_y_value),
                    "unsigned_axis_center_deg": fmt(predicted_theta),
                    "unsigned_axis_half_width_deg": fmt(uncertainty["unsigned_axis_half_width_deg"]),
                    "response_length_min_px": fmt(uncertainty["response_length_min_px"]),
                    "response_length_max_px": fmt(uncertainty["response_length_max_px"]),
                    "response_width_min_px": fmt(uncertainty["response_width_min_px"]),
                    "response_width_max_px": fmt(uncertainty["response_width_max_px"]),
                    "theta_delta_from_previous_deg": fmt(theta_delta),
                    "radius_delta_from_previous_px": fmt(radius_delta),
                    "depth_delta_from_previous_proxy": fmt(depth_delta),
                    "time_mapping_status": time_row["assumption_status"],
                    "calibration_id": calibration["version"],
                    "calibration_vehicle_role": calibration["calibration_role"],
                    "depends_on_target_reference": "false",
                    "deployment_availability": "RESEARCH_PROXY_P1E_AND_SINGLE_VEHICLE_CALIBRATION",
                    "uncertainty_status": "EXPLICIT_INTERVAL_NOT_POINT_TRUTH",
                }
            )
    return condition_rows, sorted(input_paths)


def lineage_rows(config: dict[str, Any], source_hashes: dict[str, str]) -> list[dict[str, str]]:
    common = {
        "time_range": "GM_RM017 discovery 330-350; replay 338-391; calibration 352-394",
        "vehicle_identity_source": "P1-E canonical optical benchmark",
    }
    rows = [
        {
            "field_name": "canonical_vehicle_id",
            "source_file": config["sources"]["canonical_vehicle_registry"],
            "source_modality": "optical benchmark",
            "generation_script": "tools/diagnostics/run_oty2_p1e_optical_identity_benchmark.py",
            "deployable_available": "false",
            "depends_on_sar_gt": "false",
            "coordinate_system": "scene-local physical vehicle lifecycle",
            "unit": "identifier",
            "uncertainty": "benchmark identity; runtime automatic identity not ready",
            "current_availability_status": "AVAILABLE_RESEARCH_BENCHMARK_ONLY",
            "notes": "14/4/4 canonical optical vehicles; not a repaired runtime stream",
            **common,
        },
        {
            "field_name": "optical_bbox_and_visibility",
            "source_file": config["sources"]["canonical_frame_states"],
            "source_modality": "optical benchmark",
            "generation_script": "tools/diagnostics/run_oty2_p1e_optical_identity_benchmark.py",
            "deployable_available": "false",
            "depends_on_sar_gt": "false",
            "coordinate_system": "800x600 optical display pixels",
            "unit": "pixel",
            "uncertainty": "interpolated between 24 fps benchmark frames; partial states widen shell",
            "current_availability_status": "AVAILABLE_RESEARCH_BENCHMARK_ONLY",
            "notes": "Reference bbox uses optical evidence only but is benchmark_only",
            **common,
        },
        {
            "field_name": "optical_depth_trend",
            "source_file": "D:/profile/research/data/GM_RM017/GM_RM017_depth/*_depth.npy",
            "source_modality": "derived optical depth",
            "generation_script": "UNRESOLVED_NOT_FOUND_IN_REPOSITORY",
            "deployable_available": "unknown",
            "depends_on_sar_gt": "false",
            "coordinate_system": "optical bbox-local raster",
            "unit": "unverified depth proxy",
            "uncertainty": "absolute scale and generator unresolved; trend only",
            "current_availability_status": "AVAILABLE_RESEARCH_PROXY",
            "notes": "Used only as one edge of a conservative multi-proxy radial interval, never as precise distance truth",
            **common,
        },
        {
            "field_name": "sar_time_condition",
            "source_file": config["sources"]["sar_to_optical_time_map"],
            "source_modality": "optical and SAR container timing",
            "generation_script": "tools/diagnostics/run_oty2_p0_data_asset_and_hard_sync_audit.py",
            "deployable_available": "true",
            "depends_on_sar_gt": "false",
            "coordinate_system": "optical 24 fps and SAR gray 50 fps",
            "unit": "second/frame",
            "uncertainty": "common frame-0 is a project operational assumption, not hardware-clock proof",
            "current_availability_status": "AVAILABLE_FROZEN_OPERATIONAL_ASSUMPTION",
            "notes": "No per-target offset and no target-reference correction",
            **common,
        },
        {
            "field_name": "predicted_theta_interval",
            "source_file": "configs/oty2/oty2_s1x_optical_condition_calibration.json",
            "source_modality": "independent optical plus calibration reference",
            "generation_script": "tools/diagnostics/run_oty2_s1x_prepare_optical_conditions.py",
            "deployable_available": "false",
            "depends_on_sar_gt": "true_calibration_vehicle_only",
            "coordinate_system": "SAR display fan azimuth",
            "unit": "degree",
            "uncertainty": "PV004-only fit plus explicit cross-vehicle allowance and minimum 8-degree half-width",
            "current_availability_status": "AVAILABLE_RESEARCH_CALIBRATION_PROXY",
            "notes": "PV002/PV003 target reference rows are excluded from fitting",
            **common,
        },
        {
            "field_name": "predicted_radial_interval",
            "source_file": "configs/oty2/oty2_s1x_optical_condition_calibration.json",
            "source_modality": "optical bbox scale plus calibration reference",
            "generation_script": "tools/diagnostics/run_oty2_s1x_prepare_optical_conditions.py",
            "deployable_available": "false",
            "depends_on_sar_gt": "true_calibration_vehicle_only",
            "coordinate_system": "SAR display fan radius",
            "unit": "display pixel",
            "uncertainty": "union of bbox-height and depth-proxy predictions plus both calibration residuals; minimum 120-pixel half-width; metric grid unresolved",
            "current_availability_status": "AVAILABLE_RESEARCH_CALIBRATION_PROXY",
            "notes": "No target reference centre or target size enters construction; conflicting optical proxies widen the interval",
            **common,
        },
        {
            "field_name": "unsigned_axis_range",
            "source_file": config["sources"]["canonical_frame_states"],
            "source_modality": "optical bbox and fan geometry proxy",
            "generation_script": "tools/diagnostics/run_oty2_s1x_prepare_optical_conditions.py",
            "deployable_available": "partially",
            "depends_on_sar_gt": "false",
            "coordinate_system": "SAR display image axis modulo 180 degrees",
            "unit": "degree",
            "uncertainty": "broad plus/minus 35 degrees; no front/rear semantics",
            "current_availability_status": "AVAILABLE_BROAD_PROXY",
            "notes": "Not a hard template and not a target-box angle",
            **common,
        },
        {
            "field_name": "imaging_valid_mask",
            "source_file": "docs/OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md",
            "source_modality": "SAR imaging geometry",
            "generation_script": "tools/diagnostics/run_oty2_s0m_mask_anchor_pose_mapping_audit.py",
            "deployable_available": "true",
            "depends_on_sar_gt": "false",
            "coordinate_system": "2308x1334 SAR display fan",
            "unit": "pixel mask",
            "uncertainty": "deterministic fixed fan; physical metric grid unresolved",
            "current_availability_status": "FROZEN",
            "notes": "packed-bit SHA256 7bdfbc5417db5f96405751d7503973f16db85957cf9aa0c6a8f30975cc0502ef",
            **common,
        },
        {
            "field_name": "sar_gray_sequence",
            "source_file": "D:/profile/research/data/GM_RM017/GM_RM017_SARframes_gray",
            "source_modality": "8-bit SAR grayscale display product",
            "generation_script": "UNRESOLVED_UPSTREAM_IMAGING_PIPELINE",
            "deployable_available": "true_display_product",
            "depends_on_sar_gt": "false",
            "coordinate_system": "2308x1334 SAR display pixels",
            "unit": "uint8 display level",
            "uncertainty": "no phase; fixed grayscale mapping lineage unresolved",
            "current_availability_status": "AVAILABLE_DISPLAY_DOMAIN_ONLY",
            "notes": "SAR evidence source for inference",
            **common,
        },
    ]
    for row in rows:
        source = row["source_file"]
        row["source_sha256"] = source_hashes.get(source, "")
    return rows


def main() -> None:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config
    config = load_json(config_path)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    sources = {key: resolve(value) for key, value in config["sources"].items()}
    scene_config = load_json(sources["scene_config"])
    state_rows = read_csv(sources["canonical_frame_states"])
    time_rows = read_csv(sources["sar_to_optical_time_map"])
    reference_rows = read_csv(sources["calibration_reference_manifest"])
    calibration, calibration_depth_paths = build_calibration(config, scene_config, state_rows, reference_rows)
    calibration["preparation_config_sha256"] = sha256_file(config_path)
    calibration["source_manifest_sha256"] = sha256_file(sources["calibration_reference_manifest"])
    write_json(CALIBRATION_OUTPUT, calibration)
    conditions, target_paths = build_conditions(config, scene_config, state_rows, time_rows, calibration)
    write_csv(CONDITION_OUTPUT, conditions)
    source_hashes = {
        config["sources"][key]: sha256_file(path)
        for key, path in sources.items()
        if path.is_file()
    }
    lineage = lineage_rows(config, source_hashes)
    write_csv(LINEAGE_OUTPUT, lineage)
    calibration_input_bundle = aggregate_file_hash([*sources.values(), *calibration_depth_paths])
    target_input_bundle = aggregate_file_hash(target_paths)
    summary = {
        "version": "OTY2-S1X-input-preparation-summary-v1",
        "git": git_state,
        "preparation_config": str(config_path),
        "preparation_config_sha256": sha256_file(config_path),
        "calibration_output": str(CALIBRATION_OUTPUT),
        "calibration_output_sha256": sha256_file(CALIBRATION_OUTPUT),
        "condition_output": str(CONDITION_OUTPUT),
        "condition_output_sha256": sha256_file(CONDITION_OUTPUT),
        "lineage_output": str(LINEAGE_OUTPUT),
        "lineage_output_sha256": sha256_file(LINEAGE_OUTPUT),
        "calibration_input_bundle_sha256": calibration_input_bundle,
        "target_input_bundle_sha256": target_input_bundle,
        "condition_row_count": len(conditions),
        "condition_counts": dict(Counter(row["window_role"] for row in conditions)),
        "condition_row_hash": row_hash(conditions),
        "calibration_vehicle": calibration["calibration_vehicle_id"],
        "calibration_rows": calibration["row_count"],
        "target_reference_dependency": False,
        "old_work_runtime_dependency": False,
        "missing_or_unresolved": [
            "automatic runtime optical canonical identity stream",
            "depth sidecar generator and absolute scale lineage",
            "cross-scene and cross-pose mapping calibration",
            "authoritative SAR metric grid and raw amplitude/complex/IQ/ADC",
            "fixed grayscale display mapping lineage",
        ],
    }
    write_json(SUMMARY_OUTPUT, summary)
    missing_text = f"""# OTY2-S1X Missing Inputs and Boundary Report

Date: `2026-07-17`

## Available and used

- P1-E canonical optical benchmark and frame states: available, optical-only, research benchmark.
- P0 24/50 time map: available as a frozen project operational assumption.
- GM_RM017 optical frames, depth sidecars, and SAR gray frames: available.
- Fixed fan geometry and imaging-valid mask: available and frozen.
- Independent calibration vehicle: `{calibration['calibration_vehicle_id']}`, `{calibration['row_count']}` usable rows.

## Missing or unresolved

- Automatic deployment-time canonical optical identity output is not available; P1-E is benchmark-only.
- Depth sidecar generator, absolute unit, and deployment packaging are unresolved.
- The calibration is one vehicle in one scene and does not establish cross-scene or cross-pose mapping.
- SAR metric grid, raw amplitude, complex image, IQ/ADC, and fixed grayscale mapping are unresolved.

## Forward-use decision

The missing fields do not force a return to a target-reference neighbourhood. S1X continues with explicit azimuth/radial intervals, a minimum `8 deg` azimuth half-width, a minimum `120 px` radial half-width, and broad unsigned-axis/size ranges. No missing value is silently synthesized as precise truth.

## Isolation

- Calibration target: `{calibration['calibration_vehicle_id']}` only.
- Discovery/replay targets excluded from calibration fit: `{', '.join(calibration['forbidden_target_vehicle_ids'])}`.
- Target-reference rows used in inference: `0`.
- `old_work` runtime dependency: `none`.
"""
    MISSING_REPORT.parent.mkdir(parents=True, exist_ok=True)
    MISSING_REPORT.write_text(missing_text, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
