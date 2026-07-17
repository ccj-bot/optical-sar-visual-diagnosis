#!/usr/bin/env python3
from __future__ import annotations

"""Run target-reference-free optical/SAR S1X inference.

The entry consumes only frozen optical-condition rows, SAR grayscale images,
and fixed fan geometry. It has no reference/evaluation manifest argument.
"""

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from oty2_s1x_common import (
    CONFIG_DIR,
    FAN_HEIGHT,
    FAN_WIDTH,
    MANIFEST_DIR,
    REPO_ROOT,
    REPORT_DIR,
    annular_sector_mask,
    connected_component_rows,
    fmt,
    imaging_valid_mask,
    load_json,
    mask_bbox,
    read_csv,
    read_gray,
    remove_small_components,
    require,
    robust_median_mad,
    sha256_file,
    verify_git_gate,
    warp_translation,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = CONFIG_DIR / "oty2_s1x_joint_temporal_support.json"
FRAME_OUTPUT = MANIFEST_DIR / "oty2_s1x_temporal_support_frame_states.csv"
SAR_ONLY_OUTPUT = MANIFEST_DIR / "oty2_s1x_sar_only_temporal_objects.csv"
BLIND_REVIEW_OUTPUT = MANIFEST_DIR / "oty2_s1x_blind_visual_review_manifest.csv"
FREEZE_OUTPUT = MANIFEST_DIR / "oty2_s1x_inference_freeze_manifest.csv"
SUMMARY_OUTPUT = REPORT_DIR / "oty2_s1x_inference_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO_ROOT / path


def leakage_guard(config_path: Path, condition_path: Path) -> dict[str, Any]:
    config_text = config_path.read_text(encoding="utf-8").lower()
    forbidden_path_fragments = (
        "sar_gt",
        "final_gt",
        "local_response_fields",
        "gt_quality_audit",
        "iou",
        "oracle_box",
        "manual_box",
        "final_box",
    )
    hits = [fragment for fragment in forbidden_path_fragments if fragment in config_text]
    require(not hits, f"forbidden inference-config fragments: {hits}")
    rows = read_csv(condition_path)
    require(rows, "empty optical-condition input")
    forbidden_columns = []
    for name in rows[0]:
        lowered = name.lower()
        tokens = lowered.replace("-", "_").split("_")
        if (
            lowered.startswith("gt_")
            or "iou" in tokens
            or lowered.startswith("final_")
            or lowered.startswith("manual_")
            or lowered.startswith("oracle_")
        ):
            forbidden_columns.append(name)
    require(not forbidden_columns, f"forbidden condition columns: {forbidden_columns}")
    require(all(row["depends_on_target_reference"] == "false" for row in rows), "target dependency flag found")
    return {
        "config_forbidden_fragment_hits": hits,
        "condition_forbidden_columns": forbidden_columns,
        "target_dependency_rows": 0,
    }


def highpass(image: np.ndarray, sigma: float) -> np.ndarray:
    source = np.asarray(image, dtype=np.float32)
    return source - cv2.GaussianBlur(source, (0, 0), sigma)


def phase_shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    shift, response = cv2.phaseCorrelate(np.asarray(a, np.float32), np.asarray(b, np.float32), window)
    return float(shift[0]), float(shift[1]), float(response)


def estimate_pair_transport(
    previous: np.ndarray,
    current: np.ndarray,
    valid_mask: np.ndarray,
    settings: dict[str, Any],
) -> dict[str, Any]:
    scale = float(settings["downsample"])
    width = max(64, int(round(previous.shape[1] * scale)))
    height = max(64, int(round(previous.shape[0] * scale)))
    prev_small = cv2.resize(previous, (width, height), interpolation=cv2.INTER_AREA)
    curr_small = cv2.resize(current, (width, height), interpolation=cv2.INTER_AREA)
    mask_small = cv2.resize(valid_mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)
    prev_hp = highpass(prev_small, float(settings["highpass_sigma_px_at_downsampled_scale"]))
    curr_hp = highpass(curr_small, float(settings["highpass_sigma_px_at_downsampled_scale"]))
    rows = int(settings["tile_rows"])
    cols = int(settings["tile_cols"])
    minimum_response = float(settings["minimum_tile_response"])
    maximum_shift = float(settings["maximum_pair_shift_px"])
    candidates: list[tuple[float, float, float, int, int]] = []
    for row_index in range(rows):
        y1 = int(round(row_index * height / rows))
        y2 = int(round((row_index + 1) * height / rows))
        for col_index in range(cols):
            x1 = int(round(col_index * width / cols))
            x2 = int(round((col_index + 1) * width / cols))
            tile_mask = mask_small[y1:y2, x1:x2]
            if tile_mask.size == 0 or float(np.mean(tile_mask)) < 0.55:
                continue
            a = prev_hp[y1:y2, x1:x2].copy()
            b = curr_hp[y1:y2, x1:x2].copy()
            a[~tile_mask] = 0.0
            b[~tile_mask] = 0.0
            if float(np.std(a[tile_mask])) < 0.5 or float(np.std(b[tile_mask])) < 0.5:
                continue
            dx_small, dy_small, response = phase_shift(a, b)
            dx = dx_small / scale
            dy = dy_small / scale
            if response < minimum_response or math.hypot(dx, dy) > maximum_shift:
                continue
            candidates.append((dx, dy, response, row_index, col_index))
    if candidates:
        dx = float(np.median([item[0] for item in candidates]))
        dy = float(np.median([item[1] for item in candidates]))
        response = float(np.median([item[2] for item in candidates]))
        method = "MULTI_TILE_PHASE_MEDIAN"
    else:
        full_mask = mask_small
        a = prev_hp.copy()
        b = curr_hp.copy()
        a[~full_mask] = 0.0
        b[~full_mask] = 0.0
        dx_small, dy_small, response = phase_shift(a, b)
        dx, dy = dx_small / scale, dy_small / scale
        require(math.hypot(dx, dy) <= maximum_shift * 1.5, "transport fallback shift too large")
        method = "FULL_VALID_FAN_PHASE_FALLBACK"
    return {
        "dx": dx,
        "dy": dy,
        "response": response,
        "method": method,
        "usable_tile_count": len(candidates),
        "tile_dx_mad": float(np.median(np.abs(np.asarray([item[0] for item in candidates]) - dx))) if candidates else math.nan,
        "tile_dy_mad": float(np.median(np.abs(np.asarray([item[1] for item in candidates]) - dy))) if candidates else math.nan,
    }


def build_transports(images: list[np.ndarray], valid_mask: np.ndarray, settings: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "pair_dx": 0.0,
            "pair_dy": 0.0,
            "cumulative_dx": 0.0,
            "cumulative_dy": 0.0,
            "response": 1.0,
            "method": "REFERENCE_FRAME",
            "usable_tile_count": 0,
            "tile_dx_mad": 0.0,
            "tile_dy_mad": 0.0,
        }
    ]
    cumulative_x = 0.0
    cumulative_y = 0.0
    for previous, current in zip(images[:-1], images[1:]):
        pair = estimate_pair_transport(previous, current, valid_mask, settings)
        cumulative_x += float(pair["dx"])
        cumulative_y += float(pair["dy"])
        rows.append(
            {
                "pair_dx": float(pair["dx"]),
                "pair_dy": float(pair["dy"]),
                "cumulative_dx": cumulative_x,
                "cumulative_dy": cumulative_y,
                "response": float(pair["response"]),
                "method": pair["method"],
                "usable_tile_count": int(pair["usable_tile_count"]),
                "tile_dx_mad": float(pair["tile_dx_mad"]),
                "tile_dy_mad": float(pair["tile_dy_mad"]),
            }
        )
    return rows


def condition_shell(row: dict[str, str], context_expansion: float = 0.0) -> np.ndarray:
    theta_half = float(row["theta_half_width_deg"])
    radius_center = float(row["predicted_radius_px"])
    radius_half = float(row["radial_half_width_px"])
    extra_theta = math.degrees(context_expansion / max(radius_center, 80.0))
    return annular_sector_mask(
        float(row["predicted_theta_deg"]),
        theta_half + extra_theta,
        radius_center,
        radius_half + context_expansion,
    )


def determine_roi(
    condition_rows: list[dict[str, str]],
    transports: list[dict[str, Any]],
    context_expansion: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = FAN_WIDTH, FAN_HEIGHT, 0, 0
    for row, transport in zip(condition_rows, transports):
        context = condition_shell(row, float(context_expansion))
        warped = warp_translation(
            context.astype(np.uint8),
            -float(transport["cumulative_dx"]),
            -float(transport["cumulative_dy"]),
            cv2.INTER_NEAREST,
        ).astype(bool)
        bx1, by1, bx2, by2 = mask_bbox(warped, padding=8)
        x1, y1, x2, y2 = min(x1, bx1), min(y1, by1), max(x2, bx2), max(y2, by2)
    require(x2 > x1 and y2 > y1, "invalid union ROI")
    return x1, y1, x2, y2


def frame_response_components(
    positive: np.ndarray,
    shell: np.ndarray,
    minimum_area: int,
    outside_fraction: float,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    source = positive.astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(source, connectivity=8)
    kept = np.zeros_like(source)
    background = np.zeros_like(source)
    kept_count = 0
    background_count = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < minimum_area:
            continue
        component = labels == label
        inside = int(np.count_nonzero(component & shell))
        outside = area - inside
        if inside == 0:
            continue
        if outside / max(area, 1) >= outside_fraction:
            background[component] = 1
            background_count += 1
        else:
            kept[component & shell] = 1
            kept_count += 1
    return kept.astype(bool), background.astype(bool), kept_count, background_count


def temporal_joint_support(
    stabilized: np.ndarray,
    shells: np.ndarray,
    contexts: np.ndarray,
    valid_masks: np.ndarray,
    settings: dict[str, Any],
) -> dict[str, Any]:
    frame_count, height, width = stabilized.shape
    z_stack = np.zeros((frame_count, height, width), dtype=np.float32)
    positive_stack = np.zeros((frame_count, height, width), dtype=bool)
    independent_stack = np.zeros((frame_count, height, width), dtype=bool)
    background_stack = np.zeros((frame_count, height, width), dtype=bool)
    medians: list[float] = []
    mads: list[float] = []
    component_counts: list[int] = []
    background_component_counts: list[int] = []
    for index in range(frame_count):
        shell = shells[index] & valid_masks[index]
        context = contexts[index] & valid_masks[index]
        ring = context & ~shell
        sample = stabilized[index][ring]
        if sample.size < 500:
            sample = stabilized[index][context]
        median, mad = robust_median_mad(sample)
        scale = max(1.0, 1.4826 * mad)
        z = (stabilized[index].astype(np.float32) - median) / scale
        z[~context] = -20.0
        positive = (z >= float(settings["local_positive_robust_z"])) & context
        independent, background, component_count, background_count = frame_response_components(
            positive,
            shell,
            int(settings["minimum_component_area_px"]),
            float(settings["background_outside_shell_fraction"]),
        )
        z_stack[index] = z
        positive_stack[index] = positive
        independent_stack[index] = independent
        background_stack[index] = background
        medians.append(median)
        mads.append(mad)
        component_counts.append(component_count)
        background_component_counts.append(background_count)
    shell_presence = np.sum(shells & valid_masks, axis=0)
    positive_frequency = np.divide(
        np.sum(positive_stack & shells, axis=0),
        np.maximum(shell_presence, 1),
        dtype=np.float32,
    )
    background_frequency = np.divide(
        np.sum(background_stack, axis=0),
        np.maximum(np.sum(contexts & valid_masks, axis=0), 1),
        dtype=np.float32,
    )
    presence_ok = shell_presence >= math.ceil(frame_count * float(settings["minimum_shell_presence_fraction"]))
    persistent_core = (
        (positive_frequency >= float(settings["persistent_frequency"]))
        & (background_frequency < float(settings["background_temporal_frequency"]))
        & presence_ok
    )
    persistent_core = remove_small_components(persistent_core, int(settings["minimum_component_area_px"]))
    radius = int(settings["support_neighbourhood_px"])
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    core_neighbourhood = cv2.dilate(persistent_core.astype(np.uint8), kernel).astype(bool)
    intermittent = (
        (positive_frequency >= float(settings["intermittent_frequency"]))
        & (positive_frequency < float(settings["persistent_frequency"]))
        & (background_frequency < float(settings["background_temporal_frequency"]))
        & core_neighbourhood
        & presence_ok
    )
    intermittent = remove_small_components(intermittent, int(settings["minimum_component_area_px"]))
    background_region = (
        (background_frequency >= float(settings["background_temporal_frequency"]))
        & presence_ok
    )
    background_region = remove_small_components(background_region, int(settings["minimum_component_area_px"]))
    mixed = (
        (positive_frequency >= float(settings["intermittent_frequency"]))
        & presence_ok
        & ~persistent_core
        & ~intermittent
        & ~background_region
    )
    mixed = remove_small_components(mixed, int(settings["minimum_component_area_px"]))
    weak_stack = np.zeros_like(independent_stack)
    joint_stack = np.zeros_like(independent_stack)
    temporal_radius = int(settings["temporal_maintenance_radius_frames"])
    for index in range(frame_count):
        start = max(0, index - temporal_radius)
        end = min(frame_count, index + temporal_radius + 1)
        neighbour = np.any(independent_stack[start:end], axis=0)
        weak = (
            persistent_core
            & shells[index]
            & ~independent_stack[index]
            & neighbour
            & (z_stack[index] >= float(settings["weak_response_robust_z"]))
        )
        weak_stack[index] = weak
        current = independent_stack[index] | weak | (intermittent & positive_stack[index])
        current &= shells[index] & ~background_region
        joint_stack[index] = remove_small_components(current, int(settings["minimum_component_area_px"]))
    return {
        "z_stack": z_stack,
        "positive_stack": positive_stack,
        "independent_stack": independent_stack,
        "background_stack": background_stack,
        "weak_stack": weak_stack,
        "joint_stack": joint_stack,
        "persistent_core": persistent_core,
        "intermittent": intermittent,
        "background_region": background_region,
        "mixed": mixed,
        "positive_frequency": positive_frequency,
        "background_frequency": background_frequency,
        "frame_background_median": medians,
        "frame_background_mad": mads,
        "component_counts": component_counts,
        "background_component_counts": background_component_counts,
    }


def sar_only_baseline(
    images: list[np.ndarray],
    transports: list[dict[str, Any]],
    valid_mask: np.ndarray,
    settings: dict[str, Any],
) -> dict[str, Any]:
    frame_count = len(images)
    positive_stack = np.zeros((frame_count, FAN_HEIGHT, FAN_WIDTH), dtype=np.uint8)
    valid_count = np.zeros((FAN_HEIGHT, FAN_WIDTH), dtype=np.uint16)
    threshold = float(settings["local_positive_robust_z"])
    for index, (image, transport) in enumerate(zip(images, transports)):
        dx = -float(transport["cumulative_dx"])
        dy = -float(transport["cumulative_dy"])
        stabilized = warp_translation(image, dx, dy, cv2.INTER_LINEAR)
        valid = warp_translation(valid_mask.astype(np.uint8), dx, dy, cv2.INTER_NEAREST).astype(bool)
        sample = stabilized[valid]
        median, mad = robust_median_mad(sample)
        z = (stabilized.astype(np.float32) - median) / max(1.0, 1.4826 * mad)
        positive = (z >= threshold) & valid
        positive = cv2.morphologyEx(positive.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        positive_stack[index] = positive
        valid_count += valid.astype(np.uint16)
    frequency = np.sum(positive_stack, axis=0) / np.maximum(valid_count, 1)
    persistent = frequency >= float(settings["sar_only_persistent_frequency"])
    persistent = remove_small_components(persistent, max(32, int(settings["minimum_component_area_px"])))
    support_stack = np.zeros_like(positive_stack)
    temporal_radius = int(settings["temporal_maintenance_radius_frames"])
    for index in range(frame_count):
        start = max(0, index - temporal_radius)
        end = min(frame_count, index + temporal_radius + 1)
        neighbour = np.any(positive_stack[start:end].astype(bool), axis=0)
        support_stack[index] = (persistent & (positive_stack[index].astype(bool) | neighbour)).astype(np.uint8)
    return {
        "positive_stack": positive_stack,
        "persistent": persistent,
        "support_stack": support_stack,
        "frequency": frequency.astype(np.float32),
    }


def display_rgb(gray: np.ndarray, low: float, high: float) -> np.ndarray:
    normalized = np.clip((gray.astype(np.float32) - low) / max(high - low, 1.0), 0.0, 1.0)
    image = (normalized * 255.0).astype(np.uint8)
    return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)


def contour_overlay(image: np.ndarray, mask: np.ndarray, color: tuple[int, int, int], thickness: int = 2) -> None:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, color, thickness)


def class_overlay(
    gray: np.ndarray,
    shell: np.ndarray,
    joint: np.ndarray,
    weak: np.ndarray,
    background: np.ndarray,
    mixed: np.ndarray,
    low: float,
    high: float,
) -> np.ndarray:
    image = display_rgb(gray, low, high)
    contour_overlay(image, shell, (0, 180, 255), 2)
    alpha = 0.50
    layers = [
        (background, np.asarray([255, 70, 70], dtype=np.float32)),
        (mixed, np.asarray([220, 60, 220], dtype=np.float32)),
        (joint, np.asarray([40, 220, 80], dtype=np.float32)),
        (weak, np.asarray([40, 220, 240], dtype=np.float32)),
    ]
    output = image.astype(np.float32)
    for mask, color in layers:
        output[mask] = (1.0 - alpha) * output[mask] + alpha * color
    return np.clip(output, 0, 255).astype(np.uint8)


def representative_indices(count: int, requested: int) -> list[int]:
    selected = np.linspace(0, count - 1, num=min(requested, count), dtype=int)
    return sorted(set(int(value) for value in selected))


def create_review_pages(
    window_id: str,
    output_dir: Path,
    rows: list[dict[str, str]],
    raw_images: list[np.ndarray],
    stabilized_roi: np.ndarray,
    shells: np.ndarray,
    joint: dict[str, Any],
    roi: tuple[int, int, int, int],
    visualization: dict[str, Any],
    sar_only: dict[str, Any],
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    low = float(visualization["display_min"])
    high = float(visualization["display_max"])
    indices = representative_indices(len(rows), int(visualization["representative_frame_count"]))
    page_paths: list[Path] = []
    for page_index, start in enumerate(range(0, len(indices), 4), start=1):
        selected = indices[start : start + 4]
        figure, axes = plt.subplots(len(selected), 3, figsize=(15, 4 * len(selected)), squeeze=False)
        for axis_row, index in enumerate(selected):
            row = rows[index]
            optical = cv2.imread(row["optical_left_path"], cv2.IMREAD_COLOR)
            require(optical is not None, f"missing optical review image: {row['optical_left_path']}")
            x1 = int(round(float(row["optical_bbox_x1"])))
            y1 = int(round(float(row["optical_bbox_y1"])))
            x2 = int(round(float(row["optical_bbox_x2"])))
            y2 = int(round(float(row["optical_bbox_y2"])))
            cv2.rectangle(optical, (x1, y1), (x2, y2), (0, 255, 255), 3)
            axes[axis_row, 0].imshow(cv2.cvtColor(optical, cv2.COLOR_BGR2RGB))
            axes[axis_row, 0].set_title(
                f"optical {row['optical_left_frame']} | {row['optical_visibility_state']}\n"
                f"identity={row['canonical_vehicle_id']}"
            )
            raw_rgb = display_rgb(raw_images[index], low, high)
            raw_shell = condition_shell(row)
            contour_overlay(raw_rgb, raw_shell, (0, 180, 255), 3)
            axes[axis_row, 1].imshow(raw_rgb)
            axes[axis_row, 1].set_title(
                f"SAR {row['sar_frame_index']} optical-only shell\n"
                f"theta={float(row['predicted_theta_deg']):.1f}±{float(row['theta_half_width_deg']):.1f} deg"
            )
            overlay = class_overlay(
                stabilized_roi[index],
                shells[index],
                joint["joint_stack"][index],
                joint["weak_stack"][index],
                joint["background_region"],
                joint["mixed"],
                low,
                high,
            )
            axes[axis_row, 2].imshow(overlay)
            axes[axis_row, 2].set_title("stabilized joint state | green support cyan maintained red background")
            for axis in axes[axis_row]:
                axis.axis("off")
        figure.suptitle(f"{window_id} blind transfer review page {page_index} (no target reference)", fontsize=14)
        figure.tight_layout()
        path = output_dir / f"blind_transfer_review_page_{page_index:02d}.png"
        figure.savefig(path, dpi=150)
        plt.close(figure)
        page_paths.append(path)
    x1, y1, x2, y2 = roi
    median_roi = np.median(stabilized_roi, axis=0).astype(np.uint8)
    summary_overlay = display_rgb(median_roi, low, high)
    layers = [
        (joint["background_region"], np.asarray([255, 60, 60], np.float32)),
        (joint["mixed"], np.asarray([220, 60, 220], np.float32)),
        (joint["intermittent"], np.asarray([255, 210, 40], np.float32)),
        (joint["persistent_core"], np.asarray([40, 230, 80], np.float32)),
    ]
    output = summary_overlay.astype(np.float32)
    for mask, color in layers:
        output[mask] = 0.45 * output[mask] + 0.55 * color
    figure, axes = plt.subplots(1, 3, figsize=(18, 6))
    axes[0].imshow(np.clip(output, 0, 255).astype(np.uint8))
    axes[0].set_title("temporal classes: core green / intermittent yellow / background red / mixed magenta")
    axes[1].imshow(joint["positive_frequency"], cmap="viridis", vmin=0, vmax=1)
    axes[1].set_title("optical-shell positive-response frequency")
    axes[2].imshow(sar_only["frequency"][y1:y2, x1:x2], cmap="magma", vmin=0, vmax=1)
    axes[2].set_title("SAR-only full-fan response frequency (same ROI view)")
    for axis in axes:
        axis.axis("off")
    figure.suptitle(f"{window_id} blind temporal summary (no target reference)")
    figure.tight_layout()
    summary_path = output_dir / "blind_temporal_summary.png"
    figure.savefig(summary_path, dpi=160)
    plt.close(figure)
    page_paths.append(summary_path)
    return page_paths


def process_window(
    config: dict[str, Any],
    window_rows: list[dict[str, str]],
    output_root: Path,
) -> dict[str, Any]:
    window_id = window_rows[0]["window_id"]
    output_dir = output_root / window_id
    output_dir.mkdir(parents=True, exist_ok=True)
    images = [read_gray(Path(row["sar_gray_path"])) for row in window_rows]
    valid_mask = imaging_valid_mask()
    transports = build_transports(images, valid_mask, config["transport"])
    context_expansion = int(config["response"]["context_expansion_px"])
    roi = determine_roi(window_rows, transports, context_expansion)
    x1, y1, x2, y2 = roi
    stabilized_roi: list[np.ndarray] = []
    shell_stack: list[np.ndarray] = []
    context_stack: list[np.ndarray] = []
    valid_stack: list[np.ndarray] = []
    for row, image, transport in zip(window_rows, images, transports):
        dx = -float(transport["cumulative_dx"])
        dy = -float(transport["cumulative_dy"])
        stabilized = warp_translation(image, dx, dy, cv2.INTER_LINEAR)
        shell = warp_translation(condition_shell(row).astype(np.uint8), dx, dy, cv2.INTER_NEAREST).astype(bool)
        context = warp_translation(
            condition_shell(row, float(context_expansion)).astype(np.uint8),
            dx,
            dy,
            cv2.INTER_NEAREST,
        ).astype(bool)
        valid = warp_translation(valid_mask.astype(np.uint8), dx, dy, cv2.INTER_NEAREST).astype(bool)
        stabilized_roi.append(stabilized[y1:y2, x1:x2])
        shell_stack.append(shell[y1:y2, x1:x2])
        context_stack.append(context[y1:y2, x1:x2])
        valid_stack.append(valid[y1:y2, x1:x2])
    stabilized_array = np.asarray(stabilized_roi, dtype=np.uint8)
    shells = np.asarray(shell_stack, dtype=bool)
    contexts = np.asarray(context_stack, dtype=bool)
    valid_masks = np.asarray(valid_stack, dtype=bool)
    joint = temporal_joint_support(stabilized_array, shells, contexts, valid_masks, config["response"])
    sar_only = sar_only_baseline(images, transports, valid_mask, config["response"])
    frames = np.asarray([int(row["sar_frame_index"]) for row in window_rows], dtype=np.int32)
    transport_array = np.asarray(
        [[float(row["cumulative_dx"]), float(row["cumulative_dy"])] for row in transports],
        dtype=np.float32,
    )
    npz_path = output_dir / "frozen_inference_masks.npz"
    np.savez_compressed(
        npz_path,
        frames=frames,
        roi=np.asarray(roi, dtype=np.int32),
        cumulative_transport=transport_array,
        optical_shell=shells.astype(np.uint8),
        independent_support=joint["independent_stack"].astype(np.uint8),
        joint_support=joint["joint_stack"].astype(np.uint8),
        temporally_maintained_weak=joint["weak_stack"].astype(np.uint8),
        background_excluded=joint["background_region"].astype(np.uint8),
        mixed_or_unresolved=joint["mixed"].astype(np.uint8),
        persistent_core=joint["persistent_core"].astype(np.uint8),
        intermittent_region=joint["intermittent"].astype(np.uint8),
        positive_frequency=joint["positive_frequency"].astype(np.float32),
        background_frequency=joint["background_frequency"].astype(np.float32),
        sar_only_support=sar_only["support_stack"].astype(np.uint8),
        sar_only_persistent=sar_only["persistent"].astype(np.uint8),
        sar_only_frequency=sar_only["frequency"].astype(np.float32),
    )
    sar_only_objects = connected_component_rows(
        sar_only["persistent"], f"S1X-SARONLY-{window_id}"
    )
    for row in sar_only_objects:
        row["window_id"] = window_id
        row["window_role"] = window_rows[0]["window_role"]
        row["object_semantics"] = "BLIND_SAR_TEMPORAL_RESPONSE_OBJECT_NOT_VEHICLE_IDENTITY"
    frame_rows: list[dict[str, Any]] = []
    for index, (condition, transport) in enumerate(zip(window_rows, transports)):
        shell_area = int(np.count_nonzero(shells[index]))
        independent_area = int(np.count_nonzero(joint["independent_stack"][index]))
        joint_area = int(np.count_nonzero(joint["joint_stack"][index]))
        weak_area = int(np.count_nonzero(joint["weak_stack"][index]))
        background_area = int(np.count_nonzero(joint["background_region"] & shells[index]))
        mixed_area = int(np.count_nonzero(joint["mixed"] & shells[index]))
        if joint_area == 0:
            state = "NO_VISIBLE_RESPONSE_IN_CONDITION_SHELL"
        elif weak_area > 0 and weak_area >= max(1, joint_area // 2):
            state = "TEMPORALLY_MAINTAINED_WEAK_RESPONSE"
        elif int(np.count_nonzero(joint["persistent_core"] & joint["joint_stack"][index])) > 0:
            state = "PERSISTENT_VISIBLE_RESPONSE"
        else:
            state = "INTERMITTENT_VISIBLE_RESPONSE"
        frame_rows.append(
            {
                "window_id": window_id,
                "window_role": condition["window_role"],
                "scene": condition["scene"],
                "canonical_vehicle_id": condition["canonical_vehicle_id"],
                "sar_frame_index": condition["sar_frame_index"],
                "optical_left_frame": condition["optical_left_frame"],
                "optical_right_frame": condition["optical_right_frame"],
                "optical_visibility_state": condition["optical_visibility_state"],
                "transport_pair_dx_px": fmt(transport["pair_dx"]),
                "transport_pair_dy_px": fmt(transport["pair_dy"]),
                "transport_cumulative_dx_px": fmt(transport["cumulative_dx"]),
                "transport_cumulative_dy_px": fmt(transport["cumulative_dy"]),
                "transport_response": fmt(transport["response"]),
                "transport_method": transport["method"],
                "transport_usable_tile_count": transport["usable_tile_count"],
                "optical_only_condition_shell_area_px": shell_area,
                "per_frame_independent_support_area_px": independent_area,
                "joint_temporal_support_area_px": joint_area,
                "temporally_maintained_weak_area_px": weak_area,
                "background_excluded_area_px": background_area,
                "mixed_or_unresolved_area_px": mixed_area,
                "frame_background_median": fmt(joint["frame_background_median"][index]),
                "frame_background_mad": fmt(joint["frame_background_mad"][index]),
                "accepted_local_component_count": joint["component_counts"][index],
                "background_connected_component_count": joint["background_component_counts"][index],
                "per_frame_response_state": state,
                "target_reference_used_for_inference": "false",
                "candidate_bank_generated": "false",
                "ranking_or_weighted_score_used": "false",
                "unique_box_generated": "false",
                "frozen_npz_path": str(npz_path),
            }
        )
    review_paths = create_review_pages(
        window_id,
        output_dir / "blind_review",
        window_rows,
        images,
        stabilized_array,
        shells,
        joint,
        roi,
        config["visualization"],
        sar_only,
    )
    summary = {
        "window_id": window_id,
        "window_role": window_rows[0]["window_role"],
        "scene": window_rows[0]["scene"],
        "canonical_vehicle_id": window_rows[0]["canonical_vehicle_id"],
        "frame_count": len(window_rows),
        "frame_range": [int(window_rows[0]["sar_frame_index"]), int(window_rows[-1]["sar_frame_index"])],
        "roi": list(roi),
        "transport_cumulative_dx_px": float(transports[-1]["cumulative_dx"]),
        "transport_cumulative_dy_px": float(transports[-1]["cumulative_dy"]),
        "transport_pair_dx_median_px": float(np.median([float(row["pair_dx"]) for row in transports[1:]])),
        "transport_pair_dy_median_px": float(np.median([float(row["pair_dy"]) for row in transports[1:]])),
        "persistent_core_area_px": int(np.count_nonzero(joint["persistent_core"])),
        "intermittent_region_area_px": int(np.count_nonzero(joint["intermittent"])),
        "background_region_area_px": int(np.count_nonzero(joint["background_region"])),
        "mixed_region_area_px": int(np.count_nonzero(joint["mixed"])),
        "mean_optical_shell_area_px": float(np.mean([np.count_nonzero(mask) for mask in shells])),
        "mean_joint_support_area_px": float(np.mean([np.count_nonzero(mask) for mask in joint["joint_stack"]])),
        "mean_independent_support_area_px": float(np.mean([np.count_nonzero(mask) for mask in joint["independent_stack"]])),
        "weak_maintained_frame_count": int(sum(np.count_nonzero(mask) > 0 for mask in joint["weak_stack"])),
        "empty_joint_frame_count": int(sum(np.count_nonzero(mask) == 0 for mask in joint["joint_stack"])),
        "empty_independent_frame_count": int(sum(np.count_nonzero(mask) == 0 for mask in joint["independent_stack"])),
        "sar_only_temporal_object_count": len(sar_only_objects),
        "npz_path": str(npz_path),
        "review_paths": [str(path) for path in review_paths],
    }
    summary_path = output_dir / "inference_summary.json"
    write_json(summary_path, summary)
    return {
        "frame_rows": frame_rows,
        "sar_only_objects": sar_only_objects,
        "review_paths": review_paths,
        "npz_path": npz_path,
        "summary_path": summary_path,
        "summary": summary,
    }


def main() -> None:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config
    config = load_json(config_path)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    condition_path = resolve(config["optical_condition_frames"])
    leak_audit = leakage_guard(config_path, condition_path)
    condition_rows = read_csv(condition_path)
    selected_windows = list(config["windows"])
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in condition_rows:
        if row["window_id"] in selected_windows:
            grouped.setdefault(row["window_id"], []).append(row)
    require(set(grouped) == set(selected_windows), "missing configured window")
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row["sar_frame_index"]))
    output_root = Path(config["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    config_sha = sha256_file(config_path)
    condition_sha = sha256_file(condition_path)
    all_frame_rows: list[dict[str, Any]] = []
    all_sar_only_objects: list[dict[str, Any]] = []
    all_review_rows: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []
    for window_id in selected_windows:
        result = process_window(config, grouped[window_id], output_root)
        all_results.append(result)
        all_frame_rows.extend(result["frame_rows"])
        all_sar_only_objects.extend(result["sar_only_objects"])
        for path in result["review_paths"]:
            all_review_rows.append(
                {
                    "window_id": window_id,
                    "artifact_path": str(path),
                    "artifact_sha256": sha256_file(path),
                    "contains_target_reference": "false",
                    "selection_basis": "uniform_frame_sampling_or_full_window_temporal_summary",
                    "review_status": "pending_direct_review",
                    "review_language": "Chinese_required_after_direct_inspection",
                }
            )
    write_csv(FRAME_OUTPUT, all_frame_rows)
    if all_sar_only_objects:
        write_csv(SAR_ONLY_OUTPUT, all_sar_only_objects)
    else:
        write_csv(
            SAR_ONLY_OUTPUT,
            [
                {
                    "window_id": window_id,
                    "object_id": "NONE",
                    "object_semantics": "NO_PERSISTENT_BLIND_SAR_OBJECT_AT_FROZEN_RULE",
                }
                for window_id in selected_windows
            ],
        )
    write_csv(BLIND_REVIEW_OUTPUT, all_review_rows)
    summary = {
        "version": "OTY2-S1X-inference-summary-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state,
        "inference_config": str(config_path),
        "inference_config_sha256": config_sha,
        "optical_condition_sha256": condition_sha,
        "leakage_audit": leak_audit,
        "windows": [result["summary"] for result in all_results],
        "target_reference_used_for_inference": False,
        "candidate_bank_generated": False,
        "weighted_score_or_ranking_used": False,
        "unique_box_generated": False,
    }
    write_json(SUMMARY_OUTPUT, summary)
    frozen_paths: list[Path] = [
        config_path,
        condition_path,
        FRAME_OUTPUT,
        SAR_ONLY_OUTPUT,
        BLIND_REVIEW_OUTPUT,
        SUMMARY_OUTPUT,
    ]
    for result in all_results:
        frozen_paths.extend([result["npz_path"], result["summary_path"], *result["review_paths"]])
    freeze_rows: list[dict[str, Any]] = []
    for path in frozen_paths:
        freeze_rows.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "freeze_role": (
                    "INFERENCE_CONFIG"
                    if path == config_path
                    else "OPTICAL_CONDITION_INPUT"
                    if path == condition_path
                    else "FROZEN_INFERENCE_OUTPUT"
                ),
                "frozen_before_evaluation": "true",
                "target_reference_content": "false",
            }
        )
    write_csv(FREEZE_OUTPUT, freeze_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
