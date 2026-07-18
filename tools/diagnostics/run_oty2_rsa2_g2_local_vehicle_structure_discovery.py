#!/usr/bin/env python3
"""Render the OTY2-RSA2-G2 constrained local-structure evidence pack.

This is an open-book, research-period visualization helper.  SAR GT is used
only to define a vehicle center, longest-edge orientation, physical-grid crop,
and explicit negative controls.  A GT box is not treated as a response mask.

The script does not detect responses, generate candidates, tune thresholds,
score/rank locations, select winners, or produce a deployable SAR position.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
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
GRID_M_PER_PX = 0.03
FAN_ORIGIN = np.array([1154.0, 1330.6], dtype=np.float64)
PATCH_WIDTH = 420
PATCH_HEIGHT = 280

COLORS = {
    "PV001": "#41D3BD",
    "PV002": "#FFD166",
    "PV003": "#F72585",
    "PV004": "#7B61FF",
    "PV007": "#FF6B6B",
    "PV008": "#9EF01A",
    "PV010": "#00B4D8",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=DEFAULT_REPO / "docs/reviews/assets/20260718_rsa2_g2_local_structure",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_REPO / "manifests/oty2/oty2_rsa2_g2_local_structure_case_manifest.csv",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def suffix(vehicle: str) -> str:
    return vehicle.split(":")[-1]


def parse_bbox(row: dict[str, str]) -> tuple[float, float, float, float, float]:
    values = row["bbox"].strip("[]").split(",")
    return tuple(float(value) for value in values)  # type: ignore[return-value]


def normalize_axis_angle(angle_deg: float) -> float:
    return ((angle_deg + 90.0) % 180.0) - 90.0


def axial_difference_deg(a: float, b: float) -> float:
    return abs(normalize_axis_angle(a - b))


def fan_tangent_angle_deg(center: tuple[float, float]) -> float:
    vector = np.array(center, dtype=np.float64) - FAN_ORIGIN
    radial_angle = math.degrees(math.atan2(vector[1], vector[0]))
    return normalize_axis_angle(radial_angle + 90.0)


def box_corners(
    cx: float, cy: float, width: float, height: float, angle_deg: float
) -> np.ndarray:
    theta = math.radians(angle_deg)
    width_axis = np.array([math.cos(theta), math.sin(theta)])
    height_axis = np.array([-math.sin(theta), math.cos(theta)])
    center = np.array([cx, cy])
    return np.stack(
        [
            center - width_axis * width / 2 - height_axis * height / 2,
            center + width_axis * width / 2 - height_axis * height / 2,
            center + width_axis * width / 2 + height_axis * height / 2,
            center - width_axis * width / 2 + height_axis * height / 2,
        ]
    )


def longest_edge_geometry(row: dict[str, str]) -> dict[str, float]:
    cx, cy, width, height, raw_angle = parse_bbox(row)
    corners = box_corners(cx, cy, width, height, raw_angle)
    vectors = np.roll(corners, -1, axis=0) - corners
    lengths = np.linalg.norm(vectors, axis=1)
    edge_index = int(np.argmax(lengths))
    vector = vectors[edge_index]
    angle = normalize_axis_angle(math.degrees(math.atan2(vector[1], vector[0])))
    ordered = np.sort(lengths)
    return {
        "cx": cx,
        "cy": cy,
        "long_px": float(ordered[-1]),
        "short_px": float(ordered[0]),
        "angle_deg": angle,
        "raw_angle_deg": raw_angle,
    }


def gt_rank(row: dict[str, str]) -> tuple[float, ...]:
    quality = {"gold": 0, "usable": 1, "diagnostic_only": 2}.get(
        row["gt_quality_status"], 9
    )
    identity = {"high": 0, "moderate": 1, "low": 2}.get(
        row.get("identity_link_confidence", ""), 9
    )
    stable_manual = 0 if "|gm_rm" in row["sar_gt_id"].lower() else 1
    _, _, width, height, _ = parse_bbox(row)
    return quality, identity, stable_manual, -(width * height), row["sar_gt_id"]


def choose_gt(
    rows: list[dict[str, str]], scene: str, vehicle: str, frame: int
) -> dict[str, str]:
    candidates = [
        row
        for row in rows
        if row["scene"] == scene
        and row["canonical_vehicle_id"] == vehicle
        and int(row["sar_frame_index"]) == frame
    ]
    if not candidates:
        raise RuntimeError(f"missing GT: {scene} {vehicle} SAR {frame}")
    return min(candidates, key=gt_rank)


def sar_path(data: Path, scene: str, frame: int) -> Path:
    return data / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def optical_path(data: Path, scene: str, frame: int) -> Path:
    return data / scene / f"{scene}_frames" / f"{frame:06d}.png"


def load_gray(data: Path, scene: str, frame: int) -> np.ndarray:
    return np.asarray(Image.open(sar_path(data, scene, frame)).convert("L"), dtype=np.float32)


def load_rgb(data: Path, scene: str, frame: int) -> np.ndarray:
    return np.asarray(Image.open(optical_path(data, scene, frame)).convert("RGB"))


def sample_patch(
    image: np.ndarray,
    center: tuple[float, float],
    axis_deg: float,
    width: int = PATCH_WIDTH,
    height: int = PATCH_HEIGHT,
) -> np.ndarray:
    """Sample a fixed-grid crop whose output x axis follows axis_deg."""
    theta = math.radians(axis_deg)
    long_axis = np.array([math.cos(theta), math.sin(theta)], dtype=np.float32)
    short_axis = np.array([-math.sin(theta), math.cos(theta)], dtype=np.float32)
    xx, yy = np.meshgrid(
        np.arange(width, dtype=np.float32) - (width - 1) / 2,
        np.arange(height, dtype=np.float32) - (height - 1) / 2,
    )
    map_x = center[0] + xx * long_axis[0] + yy * short_axis[0]
    map_y = center[1] + xx * long_axis[1] + yy * short_axis[1]
    return cv2.remap(
        image,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def local_contrast(patch: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(patch, (0, 0), sigmaX=10.0, sigmaY=10.0)
    return patch - blurred


def robust_limits(patch: np.ndarray) -> tuple[float, float]:
    valid = patch[patch > 0]
    if valid.size < 10:
        return 0.0, 255.0
    return float(np.percentile(valid, 2.0)), float(np.percentile(valid, 99.5))


def contrast_limit(contrast: np.ndarray, raw: np.ndarray) -> float:
    values = np.abs(contrast[raw > 0])
    if values.size < 10:
        return 1.0
    return max(float(np.percentile(values, 99.0)), 1.0)


def draw_metric_reference(
    ax: plt.Axes, geometry: dict[str, float], color: str, label: str = "GT geometry reference"
) -> None:
    long_m = geometry["long_px"] * GRID_M_PER_PX
    short_m = geometry["short_px"] * GRID_M_PER_PX
    ax.add_patch(
        Rectangle(
            (-long_m / 2, -short_m / 2),
            long_m,
            short_m,
            fill=False,
            edgecolor=color,
            linewidth=2.0,
        )
    )
    ax.text(
        -PATCH_WIDTH * GRID_M_PER_PX / 2 + 0.2,
        PATCH_HEIGHT * GRID_M_PER_PX / 2 - 0.35,
        label,
        color=color,
        fontsize=7,
        va="top",
        bbox={"facecolor": "#101720", "alpha": 0.78, "edgecolor": "none", "pad": 2},
    )


def show_canonical(
    ax: plt.Axes,
    patch: np.ndarray,
    geometry: dict[str, float],
    color: str,
    title: str,
    use_contrast: bool = False,
) -> None:
    extent = [
        -PATCH_WIDTH * GRID_M_PER_PX / 2,
        PATCH_WIDTH * GRID_M_PER_PX / 2,
        PATCH_HEIGHT * GRID_M_PER_PX / 2,
        -PATCH_HEIGHT * GRID_M_PER_PX / 2,
    ]
    if use_contrast:
        contrast = local_contrast(patch)
        limit = contrast_limit(contrast, patch)
        ax.imshow(contrast, cmap="coolwarm", vmin=-limit, vmax=limit, extent=extent)
    else:
        low, high = robust_limits(patch)
        ax.imshow(patch, cmap="gray", vmin=low, vmax=high, extent=extent)
    draw_metric_reference(ax, geometry, color)
    ax.axhline(0, color="#94A3B8", linewidth=0.5, alpha=0.5)
    ax.axvline(0, color="#94A3B8", linewidth=0.5, alpha=0.5)
    ax.set_title(title, color="white", fontsize=9)
    ax.set_xlabel("vehicle long-axis coordinate (m-grid)", color="#CBD5E1", fontsize=7)
    ax.set_ylabel("vehicle short-axis coordinate (m-grid)", color="#CBD5E1", fontsize=7)
    ax.tick_params(colors="#94A3B8", labelsize=6)
    ax.grid(color="#64748B", alpha=0.2, linewidth=0.4)


def show_raw_centered(
    ax: plt.Axes,
    patch: np.ndarray,
    geometry: dict[str, float],
    color: str,
    title: str,
) -> None:
    low, high = robust_limits(patch)
    ax.imshow(patch, cmap="gray", vmin=low, vmax=high)
    cx = (PATCH_WIDTH - 1) / 2
    cy = (PATCH_HEIGHT - 1) / 2
    corners = box_corners(
        cx,
        cy,
        geometry["long_px"],
        geometry["short_px"],
        geometry["angle_deg"],
    )
    ax.add_patch(Polygon(corners, closed=True, fill=False, edgecolor=color, linewidth=2.0))
    ax.set_title(title, color="white", fontsize=9)
    ax.axis("off")


def optical_state_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, int], dict[str, str]]:
    return {
        (row["scene"], row["canonical_vehicle_id"], int(row["frame_index"])): row
        for row in rows
    }


def show_optical(
    ax: plt.Axes,
    data: Path,
    states: dict[tuple[str, str, int], dict[str, str]],
    scene: str,
    vehicle: str,
    frame: int,
    title: str,
) -> None:
    image = load_rgb(data, scene, frame)
    row = states.get((scene, vehicle, frame))
    color = COLORS[suffix(vehicle)]
    if row and row["reference_bbox_available"] == "true":
        x1, y1, x2, y2 = (float(row[key]) for key in (
            "reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2"
        ))
        pad_x = max(45.0, (x2 - x1) * 0.15)
        pad_y = max(35.0, (y2 - y1) * 0.15)
        left, right = max(0, int(x1 - pad_x)), min(image.shape[1], int(x2 + pad_x))
        top, bottom = max(0, int(y1 - pad_y)), min(image.shape[0], int(y2 + pad_y))
        crop = image[top:bottom, left:right]
        ax.imshow(crop)
        ax.add_patch(
            Rectangle(
                (x1 - left, y1 - top), x2 - x1, y2 - y1,
                fill=False, edgecolor=color, linewidth=2.0,
            )
        )
    else:
        ax.imshow(image)
    ax.set_title(title, color="white", fontsize=9)
    ax.axis("off")


def correlation(a: np.ndarray, b: np.ndarray, raw_a: np.ndarray, raw_b: np.ndarray) -> float | None:
    mask = (raw_a > 0) & (raw_b > 0)
    if int(mask.sum()) < 100:
        return None
    x = a[mask].astype(np.float64)
    y = b[mask].astype(np.float64)
    x -= x.mean()
    y -= y.mean()
    denom = math.sqrt(float(np.dot(x, x) * np.dot(y, y)))
    if denom <= 1e-12:
        return None
    return float(np.dot(x, y) / denom)


def add_manifest_row(
    rows: list[dict[str, object]],
    case_id: str,
    scene: str,
    vehicle: str,
    optical_frame: int,
    sar_frame: int,
    phase: str,
    role: str,
    gt: dict[str, str],
    geometry: dict[str, float],
    center: tuple[float, float] | None = None,
    axis_deg: float | None = None,
    raw_corr: float | None = None,
    canonical_corr: float | None = None,
    note: str = "",
) -> None:
    center = center or (geometry["cx"], geometry["cy"])
    axis_deg = geometry["angle_deg"] if axis_deg is None else axis_deg
    tangent_deg = fan_tangent_angle_deg(center)
    rows.append(
        {
            "case_id": case_id,
            "scene": scene,
            "canonical_vehicle_id": vehicle,
            "optical_frame": optical_frame,
            "sar_frame": sar_frame,
            "event_phase": phase,
            "evidence_role": role,
            "sar_gt_id": gt["sar_gt_id"],
            "gt_quality_status": gt["gt_quality_status"],
            "identity_link_confidence": gt.get("identity_link_confidence", ""),
            "reference_center_x_px": f"{center[0]:.3f}",
            "reference_center_y_px": f"{center[1]:.3f}",
            "reference_long_axis_px": f"{geometry['long_px']:.3f}",
            "reference_short_axis_px": f"{geometry['short_px']:.3f}",
            "reference_long_axis_m_grid": f"{geometry['long_px'] * GRID_M_PER_PX:.3f}",
            "reference_short_axis_m_grid": f"{geometry['short_px'] * GRID_M_PER_PX:.3f}",
            "reference_axis_deg": f"{axis_deg:.3f}",
            "fan_tangent_angle_deg_at_reference_center": f"{tangent_deg:.3f}",
            "axis_vs_fan_tangent_axial_difference_deg": f"{axial_difference_deg(axis_deg, tangent_deg):.3f}",
            "raw_centered_contrast_corr_to_previous": "" if raw_corr is None else f"{raw_corr:.6f}",
            "vehicle_aligned_contrast_corr_to_previous": "" if canonical_corr is None else f"{canonical_corr:.6f}",
            "correlation_scope": "descriptive_only_not_a_detector_or_score",
            "gt_usage_boundary": "center_axis_scale_reference_only_not_response_mask",
            "note": note,
        }
    )


def render_sequence(
    *,
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    states: dict[tuple[str, str, int], dict[str, str]],
    manifest_rows: list[dict[str, object]],
    output_name: str,
    title: str,
    scene: str,
    vehicle: str,
    frames: list[tuple[int, int, str]],
) -> None:
    color = COLORS[suffix(vehicle)]
    fig, axes = plt.subplots(4, len(frames), figsize=(4.0 * len(frames), 12.5), facecolor="#0E151D")
    previous_raw_patch = previous_canonical_patch = None
    for col, (optical_frame, sar_frame, phase) in enumerate(frames):
        gt = choose_gt(gt_rows, scene, vehicle, sar_frame)
        geometry = longest_edge_geometry(gt)
        image = load_gray(data, scene, sar_frame)
        raw_patch = sample_patch(image, (geometry["cx"], geometry["cy"]), 0.0)
        canonical_patch = sample_patch(
            image, (geometry["cx"], geometry["cy"]), geometry["angle_deg"]
        )
        show_optical(
            axes[0, col], data, states, scene, vehicle, optical_frame,
            f"Optical {optical_frame} | {phase}",
        )
        show_raw_centered(
            axes[1, col], raw_patch, geometry, color,
            f"SAR {sar_frame} | display-centered crop",
        )
        show_canonical(
            axes[2, col], canonical_patch, geometry, color,
            f"SAR {sar_frame} | vehicle-axis grid",
        )
        show_canonical(
            axes[3, col], canonical_patch, geometry, color,
            f"SAR {sar_frame} | local contrast (descriptive)", use_contrast=True,
        )
        raw_corr = canonical_corr = None
        if previous_raw_patch is not None and previous_canonical_patch is not None:
            raw_corr = correlation(
                local_contrast(previous_raw_patch), local_contrast(raw_patch),
                previous_raw_patch, raw_patch,
            )
            canonical_corr = correlation(
                local_contrast(previous_canonical_patch), local_contrast(canonical_patch),
                previous_canonical_patch, canonical_patch,
            )
        add_manifest_row(
            manifest_rows, output_name[:3], scene, vehicle, optical_frame, sar_frame,
            phase, "true_gt_neighborhood", gt, geometry,
            raw_corr=raw_corr, canonical_corr=canonical_corr,
            note="Fixed-grid crop retains 0.03 m/px display/reconstruction-grid spacing; no size normalization.",
        )
        previous_raw_patch = raw_patch
        previous_canonical_patch = canonical_patch
    fig.suptitle(title, color="white", fontsize=20, x=0.01, ha="left")
    fig.text(
        0.01, 0.005,
        "GT is geometry reference only. Local contrast is Gaussian-background subtraction for viewing, not a response mask or thresholded detection.",
        color="#F8C15C", fontsize=10,
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.96])
    fig.savefig(assets / output_name, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def draw_full_sar_context(
    ax: plt.Axes,
    image: np.ndarray,
    rows: list[tuple[dict[str, str], dict[str, float]]],
    title: str,
    crop: tuple[int, int, int, int],
) -> None:
    x1, x2, y1, y2 = crop
    low, high = robust_limits(image[y1:y2, x1:x2])
    ax.imshow(image[y1:y2, x1:x2], cmap="gray", vmin=low, vmax=high)
    for gt, _ in rows:
        geometry = longest_edge_geometry(gt)
        vehicle = suffix(gt["canonical_vehicle_id"])
        corners = box_corners(*parse_bbox(gt)) - np.array([x1, y1])
        ax.add_patch(
            Polygon(corners, closed=True, fill=False, edgecolor=COLORS[vehicle], linewidth=2.0)
        )
        ax.text(
            geometry["cx"] - x1, geometry["cy"] - y1, vehicle,
            color=COLORS[vehicle], fontsize=8, weight="bold",
        )
    ax.set_title(title, color="white", fontsize=10)
    ax.axis("off")


def render_multivehicle(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    vehicles = ["GM_RM017:PV004", "GM_RM017:PV003", "GM_RM017:PV002"]
    frames = [(164, 342, "shared_inside"), (173, 361, "shared_inside_late"), (181, 378, "shared_post_for_pv002")]
    fig, axes = plt.subplots(3, 4, figsize=(17, 11.5), facecolor="#0E151D")
    for row_index, (optical_frame, sar_frame, phase) in enumerate(frames):
        image = load_gray(data, scene, sar_frame)
        selected = []
        for vehicle in vehicles:
            gt = choose_gt(gt_rows, scene, vehicle, sar_frame)
            selected.append((gt, longest_edge_geometry(gt)))
        draw_full_sar_context(
            axes[row_index, 0], image, selected,
            f"SAR {sar_frame} / optical {optical_frame} | same platform time",
            (620, 1500, 760, 1180),
        )
        for col, (gt, geometry) in enumerate(selected, start=1):
            vehicle = gt["canonical_vehicle_id"]
            patch = sample_patch(image, (geometry["cx"], geometry["cy"]), geometry["angle_deg"])
            show_canonical(
                axes[row_index, col], patch, geometry, COLORS[suffix(vehicle)],
                f"{suffix(vehicle)} | r={float(gt['center_radius_px']):.0f}px | local contrast",
                use_contrast=True,
            )
            add_manifest_row(
                manifest_rows, "B03", scene, vehicle, optical_frame, sar_frame, phase,
                "same_time_multivehicle_true_neighborhood", gt, geometry,
                note="Same SAR frame; pairwise azimuth order is the identity exclusion context.",
            )
    fig.suptitle(
        "OTY2-RSA2-G2 B03 | Same platform time, different vehicle-local SAR states",
        color="white", fontsize=20, x=0.01, ha="left",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(assets / "B03_GM17_MULTIVEHICLE_LOCAL_STATE_CONTRAST.png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_identity_pair(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM011"
    frames = [(135, 281), (151, 315)]
    vehicles = ["GM_RM011:PV008", "GM_RM011:PV007"]
    fig = plt.figure(figsize=(16, 11.5), facecolor="#0E151D")
    grid = fig.add_gridspec(3, 4)
    for block, (optical_frame, sar_frame) in enumerate(frames):
        image = load_gray(data, scene, sar_frame)
        selected = []
        for vehicle in vehicles:
            gt = choose_gt(gt_rows, scene, vehicle, sar_frame)
            selected.append((gt, longest_edge_geometry(gt)))
        context_ax = fig.add_subplot(grid[0, block * 2 : block * 2 + 2])
        draw_full_sar_context(
            context_ax, image, selected,
            f"SAR {sar_frame} / optical {optical_frame} | order: PV008 left of PV007",
            (960, 1420, 1000, 1334),
        )
        for local_col, (gt, geometry) in enumerate(selected):
            col = block * 2 + local_col
            vehicle = gt["canonical_vehicle_id"]
            patch = sample_patch(image, (geometry["cx"], geometry["cy"]), geometry["angle_deg"])
            show_canonical(
                fig.add_subplot(grid[1, col]), patch, geometry, COLORS[suffix(vehicle)],
                f"{suffix(vehicle)} | vehicle-axis raw",
            )
            show_canonical(
                fig.add_subplot(grid[2, col]), patch, geometry, COLORS[suffix(vehicle)],
                f"{suffix(vehicle)} | local contrast", use_contrast=True,
            )
            add_manifest_row(
                manifest_rows, "B04", scene, vehicle, optical_frame, sar_frame,
                "paired_identity_window", "pairwise_order_fixed_true_neighborhood",
                gt, geometry,
                note="Direction is nearly equal at SAR315; identity responsibility comes from pairwise azimuth order.",
            )
    fig.suptitle(
        "OTY2-RSA2-G2 B04 | PV007/PV008 after pairwise order excludes identity exchange",
        color="white", fontsize=20, x=0.01, ha="left",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(assets / "B04_GM11_PV007_PV008_LOCAL_STRUCTURE_PAIR.png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def radial_center(center: tuple[float, float], radius: float) -> tuple[float, float]:
    vector = np.array(center, dtype=np.float64) - FAN_ORIGIN
    norm = float(np.linalg.norm(vector))
    if norm < 1e-6:
        vector = np.array([0.0, -1.0])
        norm = 1.0
    point = FAN_ORIGIN + vector / norm * radius
    return float(point[0]), float(point[1])


def render_controls(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    cases = [
        ("GM_RM011", "GM_RM011:PV001", 8, 16),
        ("GM_RM017", "GM_RM017:PV002", 164, 342),
        ("GM_RM011", "GM_RM011:PV010", 225, 469),
    ]
    fig, axes = plt.subplots(3, 4, figsize=(17, 11.5), facecolor="#0E151D")
    for row_index, (scene, vehicle, optical_frame, sar_frame) in enumerate(cases):
        gt = choose_gt(gt_rows, scene, vehicle, sar_frame)
        geometry = longest_edge_geometry(gt)
        image = load_gray(data, scene, sar_frame)
        true_center = (geometry["cx"], geometry["cy"])
        true_radius = float(np.linalg.norm(np.array(true_center) - FAN_ORIGIN))
        shifted_center = radial_center(true_center, true_radius + max(geometry["long_px"] * 1.25, 150.0))
        if true_radius < 150:
            arc_radius = min(260.0, true_radius + 135.0)
        else:
            arc_radius = 120.0
        arc_center = radial_center(true_center, arc_radius)
        controls = [
            ("true GT neighborhood", true_center, geometry["angle_deg"], "true_gt_neighborhood"),
            ("same center +90°", true_center, normalize_axis_angle(geometry["angle_deg"] + 90.0), "wrong_orientation_control"),
            ("same-size radial shift", shifted_center, geometry["angle_deg"], "radial_shift_control"),
            ("near-origin arc sector", arc_center, geometry["angle_deg"], "fan_arc_background_control"),
        ]
        for col, (label, center, axis, role) in enumerate(controls):
            patch = sample_patch(image, center, axis)
            control_geometry = dict(geometry)
            control_geometry["cx"], control_geometry["cy"] = center
            control_geometry["angle_deg"] = axis
            show_canonical(
                axes[row_index, col], patch, control_geometry, COLORS[suffix(vehicle)],
                f"{suffix(vehicle)} SAR {sar_frame} | {label}", use_contrast=True,
            )
            add_manifest_row(
                manifest_rows, "B05", scene, vehicle, optical_frame, sar_frame,
                "control_comparison", role, gt, geometry,
                center=center, axis_deg=axis,
                note="All controls preserve the target long/short physical-grid size; controls are not candidates.",
            )
    fig.suptitle(
        "OTY2-RSA2-G2 B05 | True neighborhoods versus orientation, radial, and fan-arc controls",
        color="white", fontsize=20, x=0.01, ha="left",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(assets / "B05_LOCAL_STRUCTURE_NEGATIVE_CONTROLS.png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_holdout_recheck(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    """Frozen post-discovery recheck on frames not used by B01-B05."""
    scene = "GM_RM017"
    vehicles = ["GM_RM017:PV004", "GM_RM017:PV003", "GM_RM017:PV002"]
    frames = [(178, 370), (178, 371)]
    fig, axes = plt.subplots(4, 4, figsize=(17, 14.5), facecolor="#0E151D")
    for block, (optical_frame, sar_frame) in enumerate(frames):
        image = load_gray(data, scene, sar_frame)
        selected = []
        for vehicle in vehicles:
            gt = choose_gt(gt_rows, scene, vehicle, sar_frame)
            selected.append((gt, longest_edge_geometry(gt)))
        draw_full_sar_context(
            axes[block * 2, 0], image, selected,
            f"HOLDOUT SAR {sar_frame} / optical {optical_frame}",
            (760, 1500, 760, 1160),
        )
        axes[block * 2 + 1, 0].text(
            0.04, 0.80,
            "Frozen responsibility:\ntrue neighborhood should retain\nvehicle-scale long-axis fragments\nmore clearly than radial shift.\n\nNo threshold or winner.",
            transform=axes[block * 2 + 1, 0].transAxes,
            color="#F8C15C", fontsize=12, va="top",
        )
        axes[block * 2 + 1, 0].axis("off")
        for col, (gt, geometry) in enumerate(selected, start=1):
            vehicle = gt["canonical_vehicle_id"]
            true_center = (geometry["cx"], geometry["cy"])
            true_radius = float(np.linalg.norm(np.array(true_center) - FAN_ORIGIN))
            shifted_center = radial_center(
                true_center, true_radius + max(geometry["long_px"] * 1.25, 150.0)
            )
            true_patch = sample_patch(image, true_center, geometry["angle_deg"])
            shift_patch = sample_patch(image, shifted_center, geometry["angle_deg"])
            show_canonical(
                axes[block * 2, col], true_patch, geometry, COLORS[suffix(vehicle)],
                f"{suffix(vehicle)} | held-out true", use_contrast=True,
            )
            show_canonical(
                axes[block * 2 + 1, col], shift_patch, geometry, COLORS[suffix(vehicle)],
                f"{suffix(vehicle)} | held-out radial shift", use_contrast=True,
            )
            add_manifest_row(
                manifest_rows, "B06", scene, vehicle, optical_frame, sar_frame,
                "frozen_holdout_recheck", "heldout_true_neighborhood", gt, geometry,
                note="Selected after B01-B05 mechanism wording was frozen; no parameter adjustment.",
            )
            add_manifest_row(
                manifest_rows, "B06", scene, vehicle, optical_frame, sar_frame,
                "frozen_holdout_recheck", "heldout_radial_shift_control", gt, geometry,
                center=shifted_center,
                note="Same target size and axis; outward radial shift; not a candidate.",
            )
    fig.suptitle(
        "OTY2-RSA2-G2 B06 | Frozen small holdout recheck: GM17 SAR 370/371",
        color="white", fontsize=20, x=0.01, ha="left",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(assets / "B06_FROZEN_SMALL_HOLDOUT_RECHECK.png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    args = parse_args()
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    gt_rows = read_csv(args.repo / "manifests/oty2/oty2_s0_sar_gt_quality_audit.csv")
    states = optical_state_map(
        read_csv(args.repo / "manifests/oty2/oty2_p1e_canonical_vehicle_frame_states.csv")
    )
    manifest_rows: list[dict[str, object]] = []

    render_sequence(
        assets=args.assets_dir,
        data=args.data,
        gt_rows=gt_rows,
        states=states,
        manifest_rows=manifest_rows,
        output_name="B01_GM11_PV001_VEHICLE_COORDINATE_SEQUENCE.png",
        title="OTY2-RSA2-G2 B01 | GM11 PV001: display coordinates versus fixed-grid vehicle coordinates",
        scene="GM_RM011",
        vehicle="GM_RM011:PV001",
        frames=[
            (4, 8, "before bracket"),
            (6, 12, "bracket entry"),
            (8, 16, "near recorded minimum"),
            (10, 20, "inside bracket"),
            (12, 24, "inside / later view"),
        ],
    )
    render_sequence(
        assets=args.assets_dir,
        data=args.data,
        gt_rows=gt_rows,
        states=states,
        manifest_rows=manifest_rows,
        output_name="B02_GM17_PV002_EVENT_COMPLEMENTARITY.png",
        title="OTY2-RSA2-G2 B02 | GM17 PV002: event-stage local components are complementary, not one fixed template",
        scene="GM_RM017",
        vehicle="GM_RM017:PV002",
        frames=[
            (153, 319, "pre-bracket / left clipped"),
            (164, 342, "inside / approach"),
            (167, 348, "inside / near recorded minimum"),
            (173, 361, "inside / departure"),
            (181, 378, "post-bracket / right clipped"),
        ],
    )
    render_multivehicle(args.assets_dir, args.data, gt_rows, manifest_rows)
    render_identity_pair(args.assets_dir, args.data, gt_rows, manifest_rows)
    render_controls(args.assets_dir, args.data, gt_rows, manifest_rows)
    render_holdout_recheck(args.assets_dir, args.data, gt_rows, manifest_rows)
    write_csv(args.manifest, manifest_rows)
    print(f"assets={args.assets_dir}")
    print(f"manifest={args.manifest}")
    print(f"rows={len(manifest_rows)}")


if __name__ == "__main__":
    main()
