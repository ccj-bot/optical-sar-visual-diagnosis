#!/usr/bin/env python3
"""Build the OTY2-RSA2-G2-R2B aspect-conditioned response grammar pack.

This is an open-book, research-period diagnostic. SAR GT is used only to
define per-frame vehicle geometry, the undirected long axis, alpha/beta, and
research interpretation coordinates. Prior manually reviewed free-geometry
regions are reused only as interpretation overlays and are always labelled:

    RESEARCH_INTERPRETATION_OVERLAY_NOT_MASK_NOT_GT

The script does not rerun the R2A road experiment, perform GT-blind search,
extract automatic components, generate candidates, tune thresholds, score or
rank locations, select winners, recover centres, produce response masks/final
boxes, or create training annotations.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import textwrap
from collections import defaultdict
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
    "docs/reviews/assets/20260719_rsa2_g2_r2b_aspect_conditioned_response_grammar"
)
DEFAULT_ELIGIBILITY = DEFAULT_REPO / (
    "manifests/oty2/oty2_rsa2_g2_r2b_aspect_eligibility_manifest.csv"
)
DEFAULT_COMPONENTS = DEFAULT_REPO / (
    "manifests/oty2/oty2_rsa2_g2_r2b_component_cards.csv"
)
DEFAULT_LINEAGE = DEFAULT_REPO / (
    "manifests/oty2/oty2_rsa2_g2_r2b_component_lineage.csv"
)
DEFAULT_SUMMARY = DEFAULT_REPO / "manifests/oty2/oty2_rsa2_g2_r2b_summary.json"

FAN_ORIGIN = np.array([1154.0, 1330.6], dtype=np.float64)
FAN_RADIUS = 1332.7
GRID_M_PER_PX = 0.03
PATCH_WIDTH = 360
PATCH_HEIGHT = 240
SIGMAS = (4.0, 10.0, 20.0)
PAIRING_BASIS = "24/50fps_common_frame0_operational_mapping"
PAIRING_ASSUMPTION = "UNFROZEN_COMMON_START_ASSUMPTION"
OVERLAY_WARNING = "RESEARCH_INTERPRETATION_OVERLAY_NOT_MASK_NOT_GT"

TARGET_VEHICLES = [
    "GM_RM017:PV002",
    "GM_RM017:PV003",
    "GM_RM017:PV004",
    "GM_RM011:PV001",
    "GM_RM011:PV006",
    "GM_RM011:PV007",
    "GM_RM011:PV008",
    "GM_RM011:PV010",
    "GM_RM019:PV001",
    "GM_RM019:PV002",
    "GM_RM019:PV004",
]

SCENE_COLORS = {
    "GM_RM011": "#38BDF8",
    "GM_RM017": "#F59E0B",
    "GM_RM019": "#A78BFA",
}
VEHICLE_COLORS = {
    "PV001": "#41D3BD",
    "PV002": "#FFD166",
    "PV003": "#F72585",
    "PV004": "#7B61FF",
    "PV006": "#00B4D8",
    "PV007": "#FF6B6B",
    "PV008": "#9EF01A",
    "PV010": "#22D3EE",
}
ROLE_COLORS = {
    "NEAR_SIDE_LONGITUDINAL_BAND": "#FFD166",
    "OFFSET_HOTSPOT_OR_SHORT_SEGMENT": "#41D3BD",
    "RADIAL_TANGENTIAL_BACKGROUND_CROSSING": "#F97316",
    "ENDPOINT_EXTERNAL_CLUTTER_CLUSTER": "#A78BFA",
    "UNRESOLVED_MIXED_STRUCTURE": "#94A3B8",
    "FRAGMENTED_NEAR_SIDE_BAND": "#FACC15",
    "NEAR_END_WIDTH_SCALE_CLUSTER_UNRESOLVED": "#38BDF8",
    "RADIAL_STRONG_LINE_COMPETITION": "#FB7185",
    "SPARSE_COMPACT_CLUSTER_UNRESOLVED": "#C084FC",
}

PV002_SEQUENCE = [319, 330, 339, 344, 350, 361, 378]
PV002_CARD_FRAMES = [330, 334, 339, 344, 350]
PV003_CARD_FRAMES = [360, 364, 372, 378, 384]
FORMAL_CASES = [
    ("GM_RM017", "GM_RM017:PV002", 344, "near-side/high-alpha formal case"),
    ("GM_RM017", "GM_RM017:PV002", 319, "intermediate-alpha formal case"),
    ("GM_RM011", "GM_RM011:PV006", 256, "near-end pressure case"),
    ("GM_RM019", "GM_RM019:PV002", 31, "cross-scene sparse oblique pressure case"),
]


ELIGIBILITY_FIELDS = [
    "case_id", "scene", "canonical_vehicle_id", "benchmark_role",
    "optical_frame", "sar_frame", "pairing_basis", "pairing_assumption_status",
    "alpha_deg", "beta_deg", "radius_px", "theta_deg", "u_axis_deg",
    "rho_axis_deg", "tau_axis_deg", "gt_quality_status",
    "identity_link_confidence", "optical_pose_review", "optical_pose_source",
    "optical_visibility_state", "optical_truncation", "optical_occlusion",
    "sar_gt_valid_fraction", "local_patch_valid_fraction", "near_origin_state",
    "fan_or_invalid_boundary_state", "background_competition",
    "continuous_window_id", "grammar_eligibility", "lineage_eligibility",
    "identifiability_status", "ineligibility_reason", "sar_gray_path",
    "optical_path", "evidence_role", "gt_usage_boundary",
]

COMPONENT_FIELDS = [
    "component_card_id", "case_id", "scene", "canonical_vehicle_id",
    "optical_frame", "sar_frame", "alpha_deg", "beta_deg", "radius_px",
    "theta_deg", "optical_pose_review", "identifiability_status",
    "component_role", "component_instance_label", "source_role",
    "source_geometry_type", "source_points_sar_px", "overlay_status",
    "raw_gray_visibility", "display_dependency", "vehicle_uv_centroid_px",
    "vehicle_uv_range_px", "radar_rhotau_centroid_px", "main_orientation_to_u_deg",
    "approx_length_px", "approx_width_px", "approx_length_m_grid",
    "approx_width_m_grid", "touches_gt_boundary", "crosses_gt_boundary",
    "extends_beyond_vehicle_length", "cross_frame_correspondence",
    "vehicle_body_explanation", "vehicle_ground_explanation",
    "background_explanation", "responsibility_status", "evidence_figure",
    "source_note", "gt_usage_boundary",
]

LINEAGE_FIELDS = [
    "lineage_relation_id", "scene", "canonical_vehicle_id", "component_role",
    "source_component_card_id", "target_component_card_id", "source_sar_frame",
    "target_sar_frame", "source_alpha_deg", "target_alpha_deg", "delta_alpha_deg",
    "relation_event", "u_extent_change", "v_position_change", "endpoint_change",
    "background_interaction", "relation_basis", "counterevidence",
    "uncertainty_state", "allowed_conclusion", "forbidden_conclusion",
    "evidence_figure", "overlay_status",
]


@dataclass(frozen=True)
class Geometry:
    cx: float
    cy: float
    long_px: float
    short_px: float
    axis_deg: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--eligibility-manifest", type=Path, default=DEFAULT_ELIGIBILITY)
    parser.add_argument("--component-manifest", type=Path, default=DEFAULT_COMPONENTS)
    parser.add_argument("--lineage-manifest", type=Path, default=DEFAULT_LINEAGE)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def suffix(vehicle: str) -> str:
    return vehicle.split(":")[-1]


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def normalize_axis_angle(angle_deg: float) -> float:
    return ((angle_deg + 90.0) % 180.0) - 90.0


def axial_difference_deg(a: float, b: float) -> float:
    return abs(normalize_axis_angle(a - b))


def parse_bbox(row: dict[str, str]) -> tuple[float, float, float, float, float]:
    return tuple(float(value) for value in row["bbox"].strip("[]").split(","))  # type: ignore[return-value]


def box_corners(cx: float, cy: float, width: float, height: float, angle_deg: float) -> np.ndarray:
    theta = math.radians(angle_deg)
    width_axis = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    height_axis = np.array([-math.sin(theta), math.cos(theta)], dtype=np.float64)
    center = np.array([cx, cy], dtype=np.float64)
    return np.stack([
        center - width_axis * width / 2 - height_axis * height / 2,
        center + width_axis * width / 2 - height_axis * height / 2,
        center + width_axis * width / 2 + height_axis * height / 2,
        center - width_axis * width / 2 + height_axis * height / 2,
    ])


def longest_edge_geometry(row: dict[str, str]) -> Geometry:
    cx, cy, width, height, raw_angle = parse_bbox(row)
    corners = box_corners(cx, cy, width, height, raw_angle)
    vectors = np.roll(corners, -1, axis=0) - corners
    lengths = np.linalg.norm(vectors, axis=1)
    vector = vectors[int(np.argmax(lengths))]
    ordered = np.sort(lengths)
    return Geometry(
        cx=cx,
        cy=cy,
        long_px=float(ordered[-1]),
        short_px=float(ordered[0]),
        axis_deg=normalize_axis_angle(math.degrees(math.atan2(vector[1], vector[0]))),
    )


def gt_rank(row: dict[str, str]) -> tuple[object, ...]:
    quality = {"gold": 0, "usable": 1, "diagnostic_only": 2,
               "identity_or_geometry_conflict": 3,
               "exclude_from_structure_discovery": 4}.get(row["gt_quality_status"], 9)
    identity = {"high": 0, "moderate": 1, "low": 2, "none": 3}.get(
        row.get("identity_link_confidence", ""), 9
    )
    stable_manual = 0 if "|gm_rm" in row["sar_gt_id"].lower() else 1
    _, _, width, height, _ = parse_bbox(row)
    return quality, identity, stable_manual, -(width * height), row["sar_gt_id"]


def preferred_gt_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, int], dict[str, str]]:
    grouped: dict[tuple[str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        vehicle = row.get("canonical_vehicle_id", "")
        if vehicle not in TARGET_VEHICLES:
            continue
        grouped[(row["scene"], vehicle, int(row["sar_frame_index"]))].append(row)
    return {key: min(items, key=gt_rank) for key, items in grouped.items()}


def optical_state_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, int], dict[str, str]]:
    return {
        (row["scene"], row["canonical_vehicle_id"], int(row["frame_index"])): row
        for row in rows
    }


def signed_axes(geometry: Geometry) -> tuple[np.ndarray, np.ndarray, float]:
    theta = math.radians(geometry.axis_deg)
    u = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    if u[0] < 0 or (abs(u[0]) < 1e-9 and u[1] < 0):
        u = -u
    v = np.array([-u[1], u[0]], dtype=np.float64)
    near = FAN_ORIGIN - np.array([geometry.cx, geometry.cy], dtype=np.float64)
    near /= max(float(np.linalg.norm(near)), 1e-9)
    if float(np.dot(v, near)) < 0:
        v = -v
    return u, v, float(np.dot(v, near))


def fan_geometry(geometry: Geometry) -> tuple[float, float, float, float, np.ndarray, np.ndarray]:
    center = np.array([geometry.cx, geometry.cy], dtype=np.float64)
    near = FAN_ORIGIN - center
    radius = float(np.linalg.norm(near))
    near /= max(radius, 1e-9)
    tau = np.array([-near[1], near[0]], dtype=np.float64)
    rho_axis = normalize_axis_angle(math.degrees(math.atan2(near[1], near[0])))
    tau_axis = normalize_axis_angle(math.degrees(math.atan2(tau[1], tau[0])))
    theta = math.degrees(math.atan2(center[0] - FAN_ORIGIN[0], FAN_ORIGIN[1] - center[1]))
    return radius, theta, rho_axis, tau_axis, near, tau


def aspect_values(geometry: Geometry) -> tuple[float, float, float, float, float, float]:
    radius, theta, rho_axis, tau_axis, _, _ = fan_geometry(geometry)
    alpha = axial_difference_deg(geometry.axis_deg, rho_axis)
    beta = axial_difference_deg(geometry.axis_deg, tau_axis)
    return alpha, beta, radius, theta, rho_axis, tau_axis


def sar_path(data: Path, scene: str, frame: int) -> Path:
    return data / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def optical_path(data: Path, scene: str, frame: int) -> Path:
    return data / scene / f"{scene}_frames" / f"{frame:06d}.png"


def load_gray(data: Path, scene: str, frame: int) -> np.ndarray:
    path = sar_path(data, scene, frame)
    if not path.exists():
        raise FileNotFoundError(path)
    return np.asarray(Image.open(path).convert("L"), dtype=np.float32)


def load_rgb(data: Path, scene: str, frame: int) -> np.ndarray:
    path = optical_path(data, scene, frame)
    if not path.exists():
        raise FileNotFoundError(path)
    return np.asarray(Image.open(path).convert("RGB"))


def imaging_valid_mask(shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    yy, xx = np.mgrid[0:height, 0:width]
    dx = xx - FAN_ORIGIN[0]
    dy = FAN_ORIGIN[1] - yy
    radius = np.hypot(dx, dy)
    theta = np.degrees(np.arctan2(dx, dy))
    return ((radius <= FAN_RADIUS) & (theta >= -90.0) & (theta <= 90.0)).astype(np.float32)


def sample_signed_patch(
    image: np.ndarray,
    geometry: Geometry,
    *,
    width: int = PATCH_WIDTH,
    height: int = PATCH_HEIGHT,
    interpolation: int = cv2.INTER_LINEAR,
) -> np.ndarray:
    u, v, _ = signed_axes(geometry)
    xx, yy = np.meshgrid(
        np.arange(width, dtype=np.float32) - (width - 1) / 2,
        np.arange(height, dtype=np.float32) - (height - 1) / 2,
    )
    map_x = geometry.cx + xx * u[0] + yy * v[0]
    map_y = geometry.cy + xx * u[1] + yy * v[1]
    return cv2.remap(
        image,
        map_x.astype(np.float32),
        map_y.astype(np.float32),
        interpolation=interpolation,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def local_contrast(patch: np.ndarray, sigma: float) -> np.ndarray:
    return patch - cv2.GaussianBlur(patch, (0, 0), sigmaX=sigma, sigmaY=sigma)


def common_raw_limits(pairs: list[tuple[np.ndarray, np.ndarray]]) -> tuple[float, float]:
    values = [patch[mask > 0.5] for patch, mask in pairs if np.any(mask > 0.5)]
    if not values:
        return 0.0, 255.0
    merged = np.concatenate(values)
    return float(np.percentile(merged, 1.0)), float(np.percentile(merged, 99.7))


def common_contrast_limit(pairs: list[tuple[np.ndarray, np.ndarray]], sigma: float) -> float:
    values = [
        np.abs(local_contrast(patch, sigma))[mask > 0.5]
        for patch, mask in pairs
        if np.any(mask > 0.5)
    ]
    if not values:
        return 1.0
    return max(float(np.percentile(np.concatenate(values), 99.2)), 1.0)


def patch_extent(width: int = PATCH_WIDTH, height: int = PATCH_HEIGHT) -> list[float]:
    return [
        -width * GRID_M_PER_PX / 2,
        width * GRID_M_PER_PX / 2,
        height * GRID_M_PER_PX / 2,
        -height * GRID_M_PER_PX / 2,
    ]


def draw_reference_box(ax: plt.Axes, geometry: Geometry, color: str) -> None:
    long_m = geometry.long_px * GRID_M_PER_PX
    short_m = geometry.short_px * GRID_M_PER_PX
    ax.add_patch(Rectangle(
        (-long_m / 2, -short_m / 2), long_m, short_m,
        fill=False, edgecolor=color, linewidth=1.6,
    ))


def draw_local_radar_axes(ax: plt.Axes, geometry: Geometry) -> None:
    u, v, _ = signed_axes(geometry)
    _, _, _, _, near, tau = fan_geometry(geometry)
    rho_local = np.array([float(np.dot(near, u)), float(np.dot(near, v))])
    tau_local = np.array([float(np.dot(tau, u)), float(np.dot(tau, v))])
    length = 1.55
    ax.arrow(0, 0, rho_local[0] * length, rho_local[1] * length,
             color="#F472B6", width=0.015, head_width=0.16, length_includes_head=True)
    ax.arrow(0, 0, tau_local[0] * length, tau_local[1] * length,
             color="#34D399", width=0.012, head_width=0.14, length_includes_head=True)
    ax.text(rho_local[0] * 1.8, rho_local[1] * 1.8, "ρ", color="#F472B6", fontsize=8)
    ax.text(tau_local[0] * 1.8, tau_local[1] * 1.8, "τ", color="#34D399", fontsize=8)


def show_patch(
    ax: plt.Axes,
    patch: np.ndarray,
    mask: np.ndarray,
    geometry: Geometry,
    title: str,
    *,
    raw_limits: tuple[float, float] | None = None,
    sigma: float | None = None,
    contrast_limit: float | None = None,
    draw_radar_axes: bool = False,
) -> None:
    display = patch.copy()
    display[mask <= 0.5] = np.nan
    if sigma is None:
        cmap = plt.cm.gray.copy()
        cmap.set_bad("black")
        low, high = raw_limits or common_raw_limits([(patch, mask)])
        ax.imshow(display, cmap=cmap, vmin=low, vmax=high, extent=patch_extent())
    else:
        contrast = local_contrast(patch, sigma)
        contrast[mask <= 0.5] = np.nan
        cmap = plt.cm.coolwarm.copy()
        cmap.set_bad("#ECEFF4")
        limit = contrast_limit or common_contrast_limit([(patch, mask)], sigma)
        ax.imshow(contrast, cmap=cmap, vmin=-limit, vmax=limit, extent=patch_extent())
    draw_reference_box(ax, geometry, VEHICLE_COLORS.get(suffix(title.split()[0]), "#FFD166"))
    ax.axhline(0, color="#94A3B8", linewidth=0.4, alpha=0.55)
    ax.axvline(0, color="#94A3B8", linewidth=0.4, alpha=0.55)
    if draw_radar_axes:
        draw_local_radar_axes(ax, geometry)
    ax.set_title(title, color="white", fontsize=7.5)
    ax.set_xlabel("u: vehicle long axis (m-grid; undirected)", color="#CBD5E1", fontsize=6)
    ax.set_ylabel("v: + toward fan origin", color="#CBD5E1", fontsize=6)
    ax.tick_params(colors="#94A3B8", labelsize=5)
    ax.grid(color="#64748B", alpha=0.16, linewidth=0.35)


def draw_full_context(
    ax: plt.Axes,
    image: np.ndarray,
    geometry: Geometry,
    title: str,
) -> None:
    valid = imaging_valid_mask(image.shape)
    values = image[valid > 0.5]
    low, high = np.percentile(values, [1.0, 99.8])
    display = image.copy()
    display[valid <= 0.5] = np.nan
    cmap = plt.cm.gray.copy()
    cmap.set_bad("black")
    ax.imshow(display, cmap=cmap, vmin=low, vmax=high)
    corners = box_corners(geometry.cx, geometry.cy, geometry.long_px, geometry.short_px, geometry.axis_deg)
    color = VEHICLE_COLORS.get(suffix(title.split()[0]), "#FFD166")
    ax.add_patch(Polygon(corners, fill=False, edgecolor=color, linewidth=1.5))
    u, v, _ = signed_axes(geometry)
    _, _, _, _, near, tau = fan_geometry(geometry)
    center = np.array([geometry.cx, geometry.cy])
    scale = max(geometry.long_px * 0.65, 95.0)
    for vector, axis_color, label in [
        (u, "#FFD166", "u"), (v, "#22D3EE", "v"),
        (near, "#F472B6", "ρ"), (tau, "#34D399", "τ"),
    ]:
        end = center + vector * scale
        ax.plot([center[0], end[0]], [center[1], end[1]], color=axis_color, linewidth=1.2)
        ax.text(end[0], end[1], label, color=axis_color, fontsize=7)
    ax.scatter([geometry.cx], [geometry.cy], s=10, c="white")
    ax.set_title(title, color="white", fontsize=7.5)
    ax.axis("off")


def crop_bounds_from_state(
    state: dict[str, str] | None,
    shape: tuple[int, int, int],
) -> tuple[int, int, int, int]:
    height, width = shape[:2]
    if not state or not as_bool(state.get("reference_bbox_available", "false")):
        return 0, 0, width, height
    x1, y1, x2, y2 = (
        float(state[key]) for key in (
            "reference_bbox_x1", "reference_bbox_y1",
            "reference_bbox_x2", "reference_bbox_y2",
        )
    )
    pad_x = max(55.0, (x2 - x1) * 0.22)
    pad_y = max(40.0, (y2 - y1) * 0.22)
    return (
        max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y)),
        min(width, int(x2 + pad_x)), min(height, int(y2 + pad_y)),
    )


def show_optical_triplet(
    ax: plt.Axes,
    data: Path,
    states: dict[tuple[str, str, int], dict[str, str]],
    scene: str,
    vehicle: str,
    frame: int,
    title: str,
) -> None:
    current = load_rgb(data, scene, frame)
    bounds = crop_bounds_from_state(states.get((scene, vehicle, frame)), current.shape)
    crops = []
    for candidate in [max(0, frame - 1), frame, frame + 1]:
        image = load_rgb(data, scene, candidate)
        x1, y1, x2, y2 = bounds
        crop = image[y1:y2, x1:x2]
        target_h = 180
        target_w = max(1, int(crop.shape[1] * target_h / max(crop.shape[0], 1)))
        crop = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_AREA)
        crops.append(crop)
    separator = np.full((180, 4, 3), 24, dtype=np.uint8)
    strip = np.concatenate([crops[0], separator, crops[1], separator, crops[2]], axis=1)
    ax.imshow(strip)
    ax.set_title(title + f" | optical {frame-1}/{frame}/{frame+1}", color="white", fontsize=7.5)
    ax.axis("off")


def pose_review(vehicle: str, optical_frame: int) -> tuple[str, str]:
    if vehicle.startswith("GM_RM017"):
        return "SIDE_DOMINANT", "direct G1-R1/G2 image review; truncation recorded separately"
    if vehicle == "GM_RM011:PV001":
        return "SIDE_DOMINANT_BUT_TRUNCATED", "direct continuous optical review"
    if vehicle == "GM_RM011:PV006":
        return "NEAR_END_TO_OBLIQUE_FRONT", "direct G1-R1 optical review"
    if vehicle == "GM_RM011:PV007":
        return "NEAR_END_TO_OBLIQUE_FRONT", "direct G1-R1 optical review"
    if vehicle == "GM_RM011:PV008":
        return "NEAR_END_DOMINANT", "direct paired optical review"
    if vehicle == "GM_RM011:PV010":
        return "SIDE_DOMINANT_BUT_BOUNDARY_TRUNCATED", "direct G1-R1 optical review"
    if vehicle == "GM_RM019:PV001":
        return "SIDE_TO_OBLIQUE_UNCERTAIN_TRUNCATED", "direct G1-R1 optical review"
    if vehicle == "GM_RM019:PV002":
        return "OBLIQUE_TO_SIDE_TRUNCATED", "direct G1-R1 optical review"
    if vehicle == "GM_RM019:PV004":
        return "OBLIQUE_TO_SIDE_TRUNCATED", "direct G1-R1 optical review"
    return "POSE_UNCERTAIN", "no direct pose review"


def background_review(vehicle: str) -> str:
    if vehicle.startswith("GM_RM017"):
        return "parked-road corridor; road/curb axis, fan arcs and radial crossings compete"
    if vehicle in {"GM_RM011:PV001", "GM_RM011:PV006", "GM_RM011:PV007", "GM_RM011:PV008"}:
        return "near-origin fan arcs, radial strong lines and invalid-boundary competition"
    if vehicle == "GM_RM011:PV010":
        return "near-origin/boundary fan arcs and sparse GT competition"
    return "cross-scene fan arcs, fixed lines and truncation-related background competition"


def eligibility_review(row: dict[str, str], local_valid: float) -> tuple[str, str, str, str, str]:
    vehicle = row["canonical_vehicle_id"]
    frame = int(row["sar_frame_index"])
    quality = row["gt_quality_status"]
    identity = row.get("identity_link_confidence", "")
    if vehicle == "GM_RM017:PV002" and 315 <= frame <= 386 and quality in {"gold", "usable"} and identity == "high":
        return "GM17_PV002_CONTINUOUS", "DEVELOPMENT_COMPONENT_GRAMMAR", "MANUAL_LINEAGE_ELIGIBLE", "IDENTIFIABLE_WITH_BACKGROUND_MIXING", ""
    if vehicle == "GM_RM017:PV003" and 315 <= frame <= 394 and quality in {"gold", "usable"} and identity == "high":
        return "GM17_PV003_CONTINUOUS", "HOLDOUT_COMPONENT_GRAMMAR_VALIDATION", "MANUAL_LINEAGE_VALIDATION_ELIGIBLE", "IDENTIFIABLE_WITH_BACKGROUND_MIXING", ""
    if vehicle == "GM_RM017:PV004" and 337 <= frame <= 394 and quality in {"gold", "usable"} and identity == "high":
        return "GM17_PV004_CONTINUOUS", "HOLDOUT_COMPONENT_GRAMMAR_VALIDATION", "MANUAL_LINEAGE_VALIDATION_ELIGIBLE", "IDENTIFIABLE_WITH_BACKGROUND_MIXING", ""
    if vehicle == "GM_RM011:PV001":
        return "GM11_PV001_NEAR_ORIGIN", "IDENTIFIABILITY_PRESSURE_ONLY", "LINEAGE_NOT_ESTABLISHED", "NOT_IDENTIFIABLE_NEAR_ORIGIN_BOUNDARY", "near-origin fan/invalid-boundary structures dominate"
    if vehicle in {"GM_RM011:PV006", "GM_RM011:PV007", "GM_RM011:PV008"}:
        reason = "near-end candidate is dominated by radial/fan background"
        if quality not in {"gold", "usable"}:
            reason += "; GT is diagnostic-only"
        if identity not in {"high", "moderate"}:
            reason += "; identity is insufficient"
        return "GM11_NEAR_END_PRESSURE", "IDENTIFIABILITY_PRESSURE_ONLY", "LINEAGE_NOT_ESTABLISHED", "NOT_IDENTIFIABLE_NEAR_END_BACKGROUND_COMPETITION", reason
    if vehicle == "GM_RM011:PV010":
        return "GM11_PV010_SPARSE_BOUNDARY", "IDENTIFIABILITY_PRESSURE_ONLY", "LINEAGE_NOT_ESTABLISHED", "NOT_IDENTIFIABLE_SPARSE_BOUNDARY", "five sparse GT anchors and strong fan/boundary competition"
    if vehicle.startswith("GM_RM019"):
        return "GM19_SPARSE_TRUNCATED", "CROSS_SCENE_PRESSURE_ONLY", "LINEAGE_NOT_ESTABLISHED", "NOT_IDENTIFIABLE_SPARSE_TRUNCATED", "usable identity exists but GT is sparse and optical vehicle is truncated"
    reason = "local valid fraction too low" if local_valid < 0.70 else "outside selected responsibility"
    return "OTHER", "NOT_ELIGIBLE", "LINEAGE_NOT_ESTABLISHED", "NOT_IDENTIFIABLE", reason


def build_eligibility_rows(
    gt_map: dict[tuple[str, str, int], dict[str, str]],
    states: dict[tuple[str, str, int], dict[str, str]],
    data: Path,
) -> tuple[list[dict[str, object]], dict[tuple[str, str, int], dict[str, object]]]:
    rows: list[dict[str, object]] = []
    records: dict[tuple[str, str, int], dict[str, object]] = {}
    mask = imaging_valid_mask((1334, 2308))
    for key in sorted(gt_map):
        scene, vehicle, frame = key
        row = gt_map[key]
        geometry = longest_edge_geometry(row)
        alpha, beta, radius, theta, rho_axis, tau_axis = aspect_values(geometry)
        local_mask = sample_signed_patch(mask, geometry, interpolation=cv2.INTER_NEAREST)
        local_valid = float((local_mask > 0.5).mean())
        optical_frame = int(row.get("optical_frame_index", "0") or 0)
        pose, pose_source = pose_review(vehicle, optical_frame)
        state = states.get((scene, vehicle, optical_frame), {})
        window, grammar, lineage, identifiability, reason = eligibility_review(row, local_valid)
        near_origin = "NEAR_ORIGIN" if radius < 180.0 else "NOT_NEAR_ORIGIN"
        boundary = "LOCAL_PATCH_BOUNDARY_AFFECTED" if local_valid < 0.97 else "LOCAL_PATCH_VALID_INTERIOR"
        if as_bool(row.get("gt_touches_valid_mask_boundary", "false")) or as_bool(row.get("gt_clipped_by_valid_mask", "false")):
            boundary = "GT_TOUCHES_OR_CLIPPED_BY_VALID_BOUNDARY"
        case_id = f"ELIG_{scene}_{suffix(vehicle)}_S{frame:04d}"
        item: dict[str, object] = {
            "case_id": case_id,
            "scene": scene,
            "canonical_vehicle_id": vehicle,
            "benchmark_role": row.get("benchmark_role", ""),
            "optical_frame": optical_frame,
            "sar_frame": frame,
            "pairing_basis": PAIRING_BASIS,
            "pairing_assumption_status": PAIRING_ASSUMPTION,
            "alpha_deg": f"{alpha:.6f}",
            "beta_deg": f"{beta:.6f}",
            "radius_px": f"{radius:.6f}",
            "theta_deg": f"{theta:.6f}",
            "u_axis_deg": f"{geometry.axis_deg:.6f}",
            "rho_axis_deg": f"{rho_axis:.6f}",
            "tau_axis_deg": f"{tau_axis:.6f}",
            "gt_quality_status": row.get("gt_quality_status", ""),
            "identity_link_confidence": row.get("identity_link_confidence", ""),
            "optical_pose_review": pose,
            "optical_pose_source": pose_source,
            "optical_visibility_state": state.get("visibility_state", row.get("optical_visibility_state", "")),
            "optical_truncation": row.get("optical_vehicle_boundary_truncation", ""),
            "optical_occlusion": state.get("occlusion_source", ""),
            "sar_gt_valid_fraction": row.get("gt_valid_mask_fraction", row.get("valid_mask_fraction", "")),
            "local_patch_valid_fraction": f"{local_valid:.6f}",
            "near_origin_state": near_origin,
            "fan_or_invalid_boundary_state": boundary,
            "background_competition": background_review(vehicle),
            "continuous_window_id": window,
            "grammar_eligibility": grammar,
            "lineage_eligibility": lineage,
            "identifiability_status": identifiability,
            "ineligibility_reason": reason,
            "sar_gray_path": str(sar_path(data, scene, frame)),
            "optical_path": str(optical_path(data, scene, optical_frame)),
            "evidence_role": "research-period aspect and identifiability audit",
            "gt_usage_boundary": "research geometry only; not response mask and not runtime input",
        }
        rows.append(item)
        records[key] = {**item, "geometry": geometry, "gt_row": row, "local_mask": local_mask}
    return rows, records


def parse_points(value: str) -> np.ndarray:
    return np.asarray([
        [float(part.split(",")[0]), float(part.split(",")[1])]
        for part in value.split(";") if part.strip()
    ], dtype=np.float64)


def project_to_vehicle(points: np.ndarray, geometry: Geometry) -> np.ndarray:
    u, v, _ = signed_axes(geometry)
    centered = points - np.array([geometry.cx, geometry.cy], dtype=np.float64)
    return np.stack([centered @ u, centered @ v], axis=1)


def project_to_radar(points: np.ndarray, geometry: Geometry) -> np.ndarray:
    _, _, _, _, near, tau = fan_geometry(geometry)
    centered = points - np.array([geometry.cx, geometry.cy], dtype=np.float64)
    return np.stack([centered @ near, centered @ tau], axis=1)


def pca_orientation_to_u(local_points: np.ndarray) -> float:
    if len(local_points) < 2:
        return float("nan")
    centered = local_points - local_points.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    vector = vh[0]
    return axial_difference_deg(math.degrees(math.atan2(vector[1], vector[0])), 0.0)


def role_from_region(row: dict[str, str]) -> tuple[str, str]:
    label = row["label"]
    component = row.get("component_id", "0")
    if label == "DEFINITE_TARGET_RESPONSE":
        return "NEAR_SIDE_LONGITUDINAL_BAND", "NSB"
    if label == "PROBABLE_TARGET_RESPONSE":
        return "OFFSET_HOTSPOT_OR_SHORT_SEGMENT", "OHS"
    if label == "MIXED_STRUCTURE" and component == "0":
        return "RADIAL_TANGENTIAL_BACKGROUND_CROSSING", "RBC"
    if label == "MIXED_STRUCTURE":
        return "ENDPOINT_EXTERNAL_CLUTTER_CLUSTER", "ECC"
    return "UNRESOLVED_MIXED_STRUCTURE", "UMS"


def interpretations(role: str) -> tuple[str, str, str, str, str]:
    if role == "NEAR_SIDE_LONGITUDINAL_BAND":
        return (
            "vehicle body contribution plausible but not separable",
            "vehicle-ground interaction remains equally plausible",
            "pure road weakened by R2A; local road/fan mixing remains",
            "VEHICLE_ASSOCIATED_BODY_GROUND_MIXED",
            "manual relation across selected frames; not tracked scatterer",
        )
    if role == "OFFSET_HOTSPOT_OR_SHORT_SEGMENT":
        return (
            "endpoint/internal vehicle contribution possible",
            "ground/multipath contribution possible",
            "background-adjacent and intermittently visible",
            "CANDIDATE_RELATION_UNRESOLVED",
            "bounded manual correspondence only",
        )
    if role == "RADIAL_TANGENTIAL_BACKGROUND_CROSSING":
        return (
            "vehicle contribution low",
            "mixed interaction cannot be excluded where crossing enters GT",
            "radial/tangential scene structure is the leading explanation",
            "BACKGROUND_OR_MIXED",
            "persistent background crossing; not a vehicle component lineage",
        )
    if role == "ENDPOINT_EXTERNAL_CLUTTER_CLUSTER":
        return (
            "vehicle endpoint attribution weak",
            "ground interaction possible",
            "external clutter/background is competitive",
            "MIXED_UNRESOLVED",
            "intermittent external cluster; no physical identity claim",
        )
    return (
        "not identifiable", "not identifiable", "background/mixed explanations remain",
        "UNRESOLVED", "no reliable correspondence",
    )


def build_component_cards(
    repo: Path,
    records: dict[tuple[str, str, int], dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, np.ndarray]]:
    source = read_csv(repo / "manifests/oty2/oty2_rsa0_response_atlas_regions_v1.csv")
    cards: list[dict[str, object]] = []
    overlays: dict[str, np.ndarray] = {}
    for row in source:
        scene = row["scene"]
        vehicle = row["canonical_vehicle_id"]
        frame = int(row["sar_frame"])
        key = (scene, vehicle, frame)
        if key not in records:
            continue
        record = records[key]
        geometry = record["geometry"]
        assert isinstance(geometry, Geometry)
        points = parse_points(row["points"])
        local = project_to_vehicle(points, geometry)
        radar = project_to_radar(points, geometry)
        role, code = role_from_region(row)
        card_id = f"CC_{scene}_{suffix(vehicle)}_S{frame:04d}_{code}_{row.get('component_id','0')}"
        overlays[card_id] = local
        local_min, local_max = local.min(axis=0), local.max(axis=0)
        radar_centroid = radar.mean(axis=0)
        centroid = local.mean(axis=0)
        length = float(local_max[0] - local_min[0])
        width = float(local_max[1] - local_min[1])
        inside = (
            (np.abs(local[:, 0]) <= geometry.long_px / 2) &
            (np.abs(local[:, 1]) <= geometry.short_px / 2)
        )
        distance_to_edges = np.minimum(
            geometry.long_px / 2 - np.abs(local[:, 0]),
            geometry.short_px / 2 - np.abs(local[:, 1]),
        )
        touches = bool(np.any(np.abs(distance_to_edges) <= 5.0))
        crosses = bool(np.any(inside) and np.any(~inside))
        extends = bool(np.any(np.abs(local[:, 0]) > geometry.long_px / 2))
        body, ground, background, responsibility, correspondence = interpretations(role)
        alpha = float(record["alpha_deg"])
        beta = float(record["beta_deg"])
        cards.append({
            "component_card_id": card_id,
            "case_id": record["case_id"],
            "scene": scene,
            "canonical_vehicle_id": vehicle,
            "optical_frame": record["optical_frame"],
            "sar_frame": frame,
            "alpha_deg": f"{alpha:.6f}",
            "beta_deg": f"{beta:.6f}",
            "radius_px": record["radius_px"],
            "theta_deg": record["theta_deg"],
            "optical_pose_review": record["optical_pose_review"],
            "identifiability_status": record["identifiability_status"],
            "component_role": role,
            "component_instance_label": row["label"],
            "source_role": row["source_role"],
            "source_geometry_type": row["geometry_type"],
            "source_points_sar_px": row["points"],
            "overlay_status": OVERLAY_WARNING,
            "raw_gray_visibility": "YES_DIRECT_MANUAL_RAW_REVIEW" if role != "OFFSET_HOTSPOT_OR_SHORT_SEGMENT" else "WEAK_YES_DIRECT_MANUAL_RAW_REVIEW",
            "display_dependency": "RAW_VISIBLE; sigma 4/10/20 descriptive aid only" if role == "NEAR_SIDE_LONGITUDINAL_BAND" else "RAW_WEAK_OR_MIXED; contrast aids interpretation only",
            "vehicle_uv_centroid_px": f"[{centroid[0]:.3f},{centroid[1]:.3f}]",
            "vehicle_uv_range_px": f"u[{local_min[0]:.3f},{local_max[0]:.3f}];v[{local_min[1]:.3f},{local_max[1]:.3f}]",
            "radar_rhotau_centroid_px": f"[{radar_centroid[0]:.3f},{radar_centroid[1]:.3f}]",
            "main_orientation_to_u_deg": f"{pca_orientation_to_u(local):.3f}",
            "approx_length_px": f"{length:.3f}",
            "approx_width_px": f"{width:.3f}",
            "approx_length_m_grid": f"{length * GRID_M_PER_PX:.3f}",
            "approx_width_m_grid": f"{width * GRID_M_PER_PX:.3f}",
            "touches_gt_boundary": str(touches).lower(),
            "crosses_gt_boundary": str(crosses).lower(),
            "extends_beyond_vehicle_length": str(extends).lower(),
            "cross_frame_correspondence": correspondence,
            "vehicle_body_explanation": body,
            "vehicle_ground_explanation": ground,
            "background_explanation": background,
            "responsibility_status": responsibility,
            "evidence_figure": "D03_RAW_GRAYSCALE_COMPONENT_CARDS.png;D05_PV002_COMPONENT_LINEAGE.png",
            "source_note": row["notes"],
            "gt_usage_boundary": "research geometry/interpretation only; not mask, GT revision, or runtime input",
        })

    stress_specs = [
        ("GM_RM017", "GM_RM017:PV002", 319, "FRAGMENTED_NEAR_SIDE_BAND", "raw-visible fragmented band; weaker than high-alpha card states", "VEHICLE_ASSOCIATED_BODY_GROUND_MIXED"),
        ("GM_RM017", "GM_RM017:PV002", 361, "FRAGMENTED_NEAR_SIDE_BAND", "band splits and endpoint balance changes", "VEHICLE_ASSOCIATED_BODY_GROUND_MIXED"),
        ("GM_RM017", "GM_RM017:PV002", 378, "FRAGMENTED_NEAR_SIDE_BAND", "shortened weak fragments persist at lower alpha", "VEHICLE_ASSOCIATED_BODY_GROUND_MIXED"),
        ("GM_RM011", "GM_RM011:PV006", 256, "NEAR_END_WIDTH_SCALE_CLUSTER_UNRESOLVED", "near-end candidate is inseparable from radial/fan structure", "NOT_IDENTIFIABLE"),
        ("GM_RM011", "GM_RM011:PV007", 281, "RADIAL_STRONG_LINE_COMPETITION", "radial strong line and fan arcs dominate the GT neighbourhood", "BACKGROUND_DOMINANT_UNRESOLVED"),
        ("GM_RM019", "GM_RM019:PV002", 31, "SPARSE_COMPACT_CLUSTER_UNRESOLVED", "compact cluster is raw-visible but sparse/truncated anchors prevent lineage", "CROSS_SCENE_PRESSURE_UNRESOLVED"),
    ]
    for scene, vehicle, frame, role, note, status in stress_specs:
        record = records[(scene, vehicle, frame)]
        code = {
            "FRAGMENTED_NEAR_SIDE_BAND": "FNSB",
            "NEAR_END_WIDTH_SCALE_CLUSTER_UNRESOLVED": "NEWC",
            "RADIAL_STRONG_LINE_COMPETITION": "RSLC",
            "SPARSE_COMPACT_CLUSTER_UNRESOLVED": "SCCU",
        }[role]
        card_id = f"CC_{scene}_{suffix(vehicle)}_S{frame:04d}_{code}"
        cards.append({
            "component_card_id": card_id,
            "case_id": record["case_id"],
            "scene": scene,
            "canonical_vehicle_id": vehicle,
            "optical_frame": record["optical_frame"],
            "sar_frame": frame,
            "alpha_deg": record["alpha_deg"],
            "beta_deg": record["beta_deg"],
            "radius_px": record["radius_px"],
            "theta_deg": record["theta_deg"],
            "optical_pose_review": record["optical_pose_review"],
            "identifiability_status": record["identifiability_status"],
            "component_role": role,
            "component_instance_label": "DESCRIPTIVE_OPEN_INTERPRETATION",
            "source_role": "direct current raw-gray review; no closed geometry",
            "source_geometry_type": "descriptive_no_closed_geometry",
            "source_points_sar_px": "",
            "overlay_status": OVERLAY_WARNING,
            "raw_gray_visibility": "YES_BUT_ATTRIBUTION_UNRESOLVED",
            "display_dependency": "raw gray primary; sigma 4/10/20 descriptive only",
            "vehicle_uv_centroid_px": "NOT_RELIABLY_LOCALIZABLE",
            "vehicle_uv_range_px": "NOT_RELIABLY_LOCALIZABLE",
            "radar_rhotau_centroid_px": "NOT_RELIABLY_LOCALIZABLE",
            "main_orientation_to_u_deg": "NOT_RELIABLY_ESTIMABLE",
            "approx_length_px": "NOT_RELIABLY_ESTIMABLE",
            "approx_width_px": "NOT_RELIABLY_ESTIMABLE",
            "approx_length_m_grid": "NOT_RELIABLY_ESTIMABLE",
            "approx_width_m_grid": "NOT_RELIABLY_ESTIMABLE",
            "touches_gt_boundary": "unresolved",
            "crosses_gt_boundary": "unresolved",
            "extends_beyond_vehicle_length": "unresolved",
            "cross_frame_correspondence": "bounded descriptive relation only" if vehicle.startswith("GM_RM017") else "LINEAGE_NOT_ESTABLISHED",
            "vehicle_body_explanation": "possible" if vehicle.startswith("GM_RM017") else "not identifiable",
            "vehicle_ground_explanation": "possible" if vehicle.startswith("GM_RM017") else "not identifiable",
            "background_explanation": "competitive" if vehicle.startswith("GM_RM017") else "leading or inseparable explanation",
            "responsibility_status": status,
            "evidence_figure": "D02_PV002_CONTINUOUS_ALPHA_WINDOW.png;D06_ASPECT_CASE_COMPARISON.png;D07_BACKGROUND_AND_UNIDENTIFIABLE_CASES.png",
            "source_note": note,
            "gt_usage_boundary": "research geometry/interpretation only; not mask, GT revision, or runtime input",
        })
    return cards, overlays


def card_index(cards: list[dict[str, object]]) -> dict[tuple[str, int, str], dict[str, object]]:
    return {
        (str(row["canonical_vehicle_id"]), int(row["sar_frame"]), str(row["component_role"])): row
        for row in cards
    }


def build_lineage_rows(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    index = card_index(cards)
    rows: list[dict[str, object]] = []
    sequences = [
        ("GM_RM017:PV002", "NEAR_SIDE_LONGITUDINAL_BAND", PV002_CARD_FRAMES,
         ["PERSIST_EXPAND_ALONG_U", "PERSIST_STRENGTHEN_AND_BROADEN", "PERSIST_EXPAND_WITH_BACKGROUND_CROSSING", "PERSIST_CONTRACT_ALONG_U"]),
        ("GM_RM017:PV002", "OFFSET_HOTSPOT_OR_SHORT_SEGMENT", PV002_CARD_FRAMES,
         ["PERSIST_WEAK_RELOCATE", "PERSIST_STRENGTHEN", "PERSIST_WITH_ENDPOINT_IMBALANCE", "WEAKEN"]),
        ("GM_RM017:PV002", "RADIAL_TANGENTIAL_BACKGROUND_CROSSING", PV002_CARD_FRAMES,
         ["BACKGROUND_PERSIST", "BACKGROUND_PERSIST_CROSS", "BACKGROUND_PERSIST_CROSS", "BACKGROUND_PERSIST"]),
        ("GM_RM017:PV002", "ENDPOINT_EXTERNAL_CLUTTER_CLUSTER", [339, 344, 350],
         ["APPEAR_AND_PERSIST", "PERSIST_EXTERNAL_MIXED"]),
        ("GM_RM017:PV003", "NEAR_SIDE_LONGITUDINAL_BAND", PV003_CARD_FRAMES,
         ["PERSIST_EXPAND", "PERSIST_STRENGTHEN_AND_BROADEN", "PERSIST_CONTRACT_SHIFT_U", "PERSIST_WEAKEN_SHORTEN"]),
        ("GM_RM017:PV003", "OFFSET_HOTSPOT_OR_SHORT_SEGMENT", PV003_CARD_FRAMES,
         ["PERSIST_WEAK", "PERSIST_INTERMITTENT", "PERSIST_WEAKEN", "PERSIST_WEAK"]),
        ("GM_RM017:PV003", "RADIAL_TANGENTIAL_BACKGROUND_CROSSING", PV003_CARD_FRAMES,
         ["BACKGROUND_PERSIST", "BACKGROUND_CROSS_STRENGTHEN", "BACKGROUND_CROSS_PERSIST", "BACKGROUND_PERSIST"]),
        ("GM_RM017:PV003", "ENDPOINT_EXTERNAL_CLUTTER_CLUSTER", [372, 378],
         ["PERSIST_EXTERNAL_MIXED"]),
    ]
    relation_count = 0
    for vehicle, role, frames, events in sequences:
        for source_frame, target_frame, event in zip(frames[:-1], frames[1:], events):
            source = index[(vehicle, source_frame, role)]
            target = index[(vehicle, target_frame, role)]
            relation_count += 1
            source_alpha = float(source["alpha_deg"])
            target_alpha = float(target["alpha_deg"])
            rows.append({
                "lineage_relation_id": f"LR{relation_count:03d}",
                "scene": source["scene"],
                "canonical_vehicle_id": vehicle,
                "component_role": role,
                "source_component_card_id": source["component_card_id"],
                "target_component_card_id": target["component_card_id"],
                "source_sar_frame": source_frame,
                "target_sar_frame": target_frame,
                "source_alpha_deg": f"{source_alpha:.6f}",
                "target_alpha_deg": f"{target_alpha:.6f}",
                "delta_alpha_deg": f"{target_alpha - source_alpha:.6f}",
                "relation_event": event,
                "u_extent_change": "manual polygon extent comparison; see cards",
                "v_position_change": "near-side relation retained for NSB; role-specific otherwise",
                "endpoint_change": "endpoint strength/balance may change; no head-tail identity assigned",
                "background_interaction": "radial/fan/road crossing retained as competing relation",
                "relation_basis": "manual raw-gray interpretation overlays in consecutive selected states",
                "counterevidence": "not pixel-identical; background crossings and intermittent hotspots remain",
                "uncertainty_state": "BOUNDED_MANUAL_COMPONENT_RELATION_NOT_TRACKED_SCATTERER",
                "allowed_conclusion": "the response role persists/reorganizes across selected frames",
                "forbidden_conclusion": "same physical scatterer, fixed mask, tracked atom, or runtime rule",
                "evidence_figure": "D05_PV002_COMPONENT_LINEAGE.png" if "PV002" in vehicle else "D08_GM17_VALIDATION_THREADS.png",
                "overlay_status": OVERLAY_WARNING,
            })
    return rows


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def set_dark(fig: plt.Figure) -> None:
    fig.patch.set_facecolor("#0E151D")


def record_for(records: dict[tuple[str, str, int], dict[str, object]], scene: str, vehicle: str, frame: int) -> dict[str, object]:
    key = (scene, vehicle, frame)
    if key not in records:
        raise KeyError(key)
    return records[key]


def load_patch_pair(data: Path, scene: str, frame: int, geometry: Geometry) -> tuple[np.ndarray, np.ndarray]:
    image = load_gray(data, scene, frame)
    mask = imaging_valid_mask(image.shape)
    return sample_signed_patch(image, geometry), sample_signed_patch(mask, geometry, interpolation=cv2.INTER_NEAREST)


def render_alpha_overview(assets: Path, rows: list[dict[str, object]]) -> None:
    fig = plt.figure(figsize=(18, 13))
    set_dark(fig)
    grid = fig.add_gridspec(3, 3, height_ratios=[1.1, 1.0, 1.1])
    ax = fig.add_subplot(grid[0, :])
    for scene in ["GM_RM011", "GM_RM017", "GM_RM019"]:
        selected = [row for row in rows if row["scene"] == scene]
        x = [float(row["alpha_deg"]) for row in selected]
        y = [float(row["radius_px"]) for row in selected]
        ax.scatter(x, y, s=18, alpha=0.72, c=SCENE_COLORS[scene], label=scene)
    ax.set_xlabel("alpha: acute undirected angle between u and ρ (deg)", color="white")
    ax.set_ylabel("radius (px)", color="white")
    ax.set_title("D01 | Actual alpha coverage and identifiability audit", color="white", fontsize=16)
    ax.tick_params(colors="#CBD5E1")
    ax.grid(alpha=0.2)
    ax.legend(facecolor="#111827", labelcolor="white")
    for col, vehicle in enumerate(["GM_RM017:PV002", "GM_RM017:PV003", "GM_RM017:PV004"]):
        axis = fig.add_subplot(grid[1, col])
        selected = sorted([row for row in rows if row["canonical_vehicle_id"] == vehicle], key=lambda item: int(item["sar_frame"]))
        axis.plot([int(row["sar_frame"]) for row in selected], [float(row["alpha_deg"]) for row in selected], color=VEHICLE_COLORS[suffix(vehicle)], linewidth=1.4)
        axis.set_title(f"{vehicle} reliable continuum", color="white", fontsize=10)
        axis.set_xlabel("SAR frame", color="#CBD5E1", fontsize=8)
        axis.set_ylabel("alpha (deg)", color="#CBD5E1", fontsize=8)
        axis.tick_params(colors="#94A3B8", labelsize=7)
        axis.grid(alpha=0.18)
        axis.set_ylim(0, 92)
    axis = fig.add_subplot(grid[2, :])
    ordered = TARGET_VEHICLES
    for index, vehicle in enumerate(ordered):
        selected = [row for row in rows if row["canonical_vehicle_id"] == vehicle]
        values = [float(row["alpha_deg"]) for row in selected]
        if not values:
            continue
        color = SCENE_COLORS[str(selected[0]["scene"])]
        axis.plot([min(values), max(values)], [index, index], color=color, linewidth=5, solid_capstyle="round")
        axis.scatter([min(values), max(values)], [index, index], c=color, s=28)
        axis.text(max(values) + 1.0, index, f"n={len(values)}", color="#CBD5E1", va="center", fontsize=7)
    axis.set_yticks(range(len(ordered)), [vehicle.replace("GM_RM0", "GM") for vehicle in ordered])
    axis.set_xlim(0, 96)
    axis.set_xlabel("observed alpha range (deg); line is coverage, not a class threshold", color="white")
    axis.tick_params(colors="#CBD5E1", labelsize=8)
    axis.grid(axis="x", alpha=0.2)
    axis.text(0.01, -0.22, "ASPECT_RANGE_INSUFFICIENT_FOR_FULL_TRANSITION: no high-quality identifiable single-vehicle thread spans 0–90°.", transform=axis.transAxes, color="#F8C15C", fontsize=10)
    fig.tight_layout()
    save_figure(fig, assets / "D01_ALPHA_IDENTIFIABILITY_OVERVIEW.png")


def render_pv002_continuous(
    assets: Path,
    data: Path,
    states: dict[tuple[str, str, int], dict[str, str]],
    records: dict[tuple[str, str, int], dict[str, object]],
) -> None:
    scene, vehicle = "GM_RM017", "GM_RM017:PV002"
    prepared = []
    for frame in PV002_SEQUENCE:
        record = record_for(records, scene, vehicle, frame)
        geometry = record["geometry"]
        assert isinstance(geometry, Geometry)
        patch, mask = load_patch_pair(data, scene, frame, geometry)
        prepared.append((frame, record, geometry, patch, mask))
    limits = common_raw_limits([(item[3], item[4]) for item in prepared])
    fig, axes = plt.subplots(3, len(prepared), figsize=(22, 9.5), facecolor="#0E151D")
    for col, (frame, record, geometry, patch, mask) in enumerate(prepared):
        optical_frame = int(record["optical_frame"])
        show_optical_triplet(axes[0, col], data, states, scene, vehicle, optical_frame, f"alpha={float(record['alpha_deg']):.1f}°")
        show_patch(axes[1, col], patch, mask, geometry, f"PV002 SAR {frame} | raw", raw_limits=limits, draw_radar_axes=True)
        axes[2, col].axis("off")
    trend = axes[2, 0]
    for col in range(1, len(prepared)):
        axes[2, col].remove()
    trend = fig.add_subplot(axes[2, 0].get_subplotspec().get_gridspec()[2, :])
    all_rows = sorted([row for row in records.values() if row["canonical_vehicle_id"] == vehicle], key=lambda item: int(item["sar_frame"]))
    trend.plot([int(row["sar_frame"]) for row in all_rows], [float(row["alpha_deg"]) for row in all_rows], color="#FFD166", linewidth=1.5)
    trend.scatter([item[0] for item in prepared], [float(item[1]["alpha_deg"]) for item in prepared], c="#F72585", s=35, zorder=3)
    trend.set_xlabel("SAR frame", color="white")
    trend.set_ylabel("alpha (deg)", color="white")
    trend.tick_params(colors="#CBD5E1")
    trend.grid(alpha=0.2)
    trend.set_ylim(45, 92)
    trend.text(0.01, 0.05, "Same static vehicle: high-alpha states broaden/strengthen the near-side band; intermediate-alpha states retain weaker fragments. No average/union mask is used.", transform=trend.transAxes, color="#F8C15C", fontsize=9)
    fig.suptitle("OTY2-RSA2-G2-R2B D02 | GM17 PV002 same-vehicle continuous alpha window", color="white", fontsize=18, x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save_figure(fig, assets / "D02_PV002_CONTINUOUS_ALPHA_WINDOW.png")


def overlay_local_cards(ax: plt.Axes, cards: list[dict[str, object]], overlays: dict[str, np.ndarray]) -> None:
    for card in cards:
        card_id = str(card["component_card_id"])
        if card_id not in overlays:
            continue
        local = overlays[card_id] * GRID_M_PER_PX
        role = str(card["component_role"])
        ax.add_patch(Polygon(local, fill=False, edgecolor=ROLE_COLORS.get(role, "white"), linewidth=1.4))


def render_component_cards(
    assets: Path,
    data: Path,
    records: dict[tuple[str, str, int], dict[str, object]],
    cards: list[dict[str, object]],
    overlays: dict[str, np.ndarray],
) -> None:
    scene, vehicle = "GM_RM017", "GM_RM017:PV002"
    prepared = []
    for frame in PV002_CARD_FRAMES:
        record = record_for(records, scene, vehicle, frame)
        geometry = record["geometry"]
        assert isinstance(geometry, Geometry)
        patch, mask = load_patch_pair(data, scene, frame, geometry)
        frame_cards = [card for card in cards if card["canonical_vehicle_id"] == vehicle and int(card["sar_frame"]) == frame]
        prepared.append((frame, record, geometry, patch, mask, frame_cards))
    raw_limits = common_raw_limits([(item[3], item[4]) for item in prepared])
    sigma_limit = common_contrast_limit([(item[3], item[4]) for item in prepared], 10.0)
    fig, axes = plt.subplots(3, len(prepared), figsize=(20, 11), facecolor="#0E151D")
    for col, (frame, record, geometry, patch, mask, frame_cards) in enumerate(prepared):
        show_patch(axes[0, col], patch, mask, geometry, f"PV002 S{frame} raw | alpha={float(record['alpha_deg']):.1f}°", raw_limits=raw_limits)
        show_patch(axes[1, col], patch, mask, geometry, f"research overlays | {len(frame_cards)} roles", raw_limits=raw_limits)
        overlay_local_cards(axes[1, col], frame_cards, overlays)
        show_patch(axes[2, col], patch, mask, geometry, "sigma=10 descriptive aid", sigma=10.0, contrast_limit=sigma_limit)
    legend = " | ".join(f"{role}: {color}" for role, color in list(ROLE_COLORS.items())[:5])
    fig.text(0.01, 0.01, OVERLAY_WARNING + "\n" + legend, color="#F8C15C", fontsize=8)
    fig.suptitle("OTY2-RSA2-G2-R2B D03 | Raw-grayscale component cards across the PV002 high-alpha state", color="white", fontsize=17, x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0.045, 1, 0.95])
    save_figure(fig, assets / "D03_RAW_GRAYSCALE_COMPONENT_CARDS.png")


def render_coordinate_comparison(
    assets: Path,
    data: Path,
    records: dict[tuple[str, str, int], dict[str, object]],
) -> None:
    cases = [
        ("GM_RM017", "GM_RM017:PV002", 344),
        ("GM_RM017", "GM_RM017:PV002", 319),
        ("GM_RM011", "GM_RM011:PV006", 256),
        ("GM_RM019", "GM_RM019:PV002", 31),
    ]
    fig, axes = plt.subplots(2, len(cases), figsize=(19, 8), facecolor="#0E151D")
    for col, (scene, vehicle, frame) in enumerate(cases):
        record = record_for(records, scene, vehicle, frame)
        geometry = record["geometry"]
        assert isinstance(geometry, Geometry)
        image = load_gray(data, scene, frame)
        patch, mask = load_patch_pair(data, scene, frame, geometry)
        draw_full_context(axes[0, col], image, geometry, f"{suffix(vehicle)} S{frame} | alpha={float(record['alpha_deg']):.1f}°")
        show_patch(axes[1, col], patch, mask, geometry, f"u/v with ρ/τ | {record['identifiability_status']}", draw_radar_axes=True)
    fig.text(0.01, 0.01, "u is undirected. ρ is the centre-to-fan-origin axis; τ is its local tangent. Alpha is never the raw box angle or image-horizontal angle.", color="#F8C15C", fontsize=9)
    fig.suptitle("OTY2-RSA2-G2-R2B D04 | Vehicle coordinates versus radar radial/tangential coordinates", color="white", fontsize=17, x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    save_figure(fig, assets / "D04_VEHICLE_AND_RADAR_COORDINATES.png")


def render_lineage(
    assets: Path,
    data: Path,
    records: dict[tuple[str, str, int], dict[str, object]],
    cards: list[dict[str, object]],
    overlays: dict[str, np.ndarray],
    lineage: list[dict[str, object]],
) -> None:
    scene, vehicle = "GM_RM017", "GM_RM017:PV002"
    prepared = []
    for frame in PV002_CARD_FRAMES:
        record = record_for(records, scene, vehicle, frame)
        geometry = record["geometry"]
        assert isinstance(geometry, Geometry)
        patch, mask = load_patch_pair(data, scene, frame, geometry)
        band_cards = [card for card in cards if card["canonical_vehicle_id"] == vehicle and int(card["sar_frame"]) == frame and card["component_role"] == "NEAR_SIDE_LONGITUDINAL_BAND"]
        prepared.append((frame, record, geometry, patch, mask, band_cards))
    limits = common_raw_limits([(item[3], item[4]) for item in prepared])
    fig = plt.figure(figsize=(20, 8.5))
    set_dark(fig)
    grid = fig.add_gridspec(2, len(prepared), height_ratios=[1.5, 1.0])
    for col, (frame, record, geometry, patch, mask, band_cards) in enumerate(prepared):
        ax = fig.add_subplot(grid[0, col])
        show_patch(ax, patch, mask, geometry, f"S{frame} alpha={float(record['alpha_deg']):.1f}°", raw_limits=limits)
        overlay_local_cards(ax, band_cards, overlays)
    timeline = fig.add_subplot(grid[1, :])
    timeline.axis("off")
    nsb_edges = [row for row in lineage if row["canonical_vehicle_id"] == vehicle and row["component_role"] == "NEAR_SIDE_LONGITUDINAL_BAND"]
    x_positions = np.linspace(0.08, 0.92, len(PV002_CARD_FRAMES))
    for index, (x, frame) in enumerate(zip(x_positions, PV002_CARD_FRAMES)):
        timeline.add_patch(Rectangle((x - 0.055, 0.54), 0.11, 0.22, transform=timeline.transAxes, facecolor="#1F2937", edgecolor="#FFD166", linewidth=1.5))
        timeline.text(x, 0.65, f"SAR {frame}", transform=timeline.transAxes, ha="center", va="center", color="white", fontsize=9)
        if index < len(nsb_edges):
            target_x = x_positions[index + 1]
            timeline.annotate("", xy=(target_x - 0.06, 0.65), xytext=(x + 0.06, 0.65), xycoords=timeline.transAxes, arrowprops={"arrowstyle": "->", "color": "#41D3BD", "lw": 1.5})
            timeline.text((x + target_x) / 2, 0.81, str(nsb_edges[index]["relation_event"]).replace("_", "\n"), transform=timeline.transAxes, ha="center", va="center", color="#41D3BD", fontsize=7)
    timeline.text(0.02, 0.24, "Persistent role: near-side longitudinal band. Observed transitions: expansion, strengthening/broadening, background crossing, then contraction. This is a bounded role relation, not a tracked physical scatterer.", transform=timeline.transAxes, color="#F8C15C", fontsize=10)
    timeline.text(0.02, 0.08, OVERLAY_WARNING, transform=timeline.transAxes, color="#F8C15C", fontsize=9)
    fig.suptitle("OTY2-RSA2-G2-R2B D05 | PV002 cross-frame component lineage", color="white", fontsize=17, x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save_figure(fig, assets / "D05_PV002_COMPONENT_LINEAGE.png")


def render_aspect_cases(
    assets: Path,
    data: Path,
    states: dict[tuple[str, str, int], dict[str, str]],
    records: dict[tuple[str, str, int], dict[str, object]],
) -> None:
    fig, axes = plt.subplots(len(FORMAL_CASES), 6, figsize=(22, 15), facecolor="#0E151D")
    for row_index, (scene, vehicle, frame, label) in enumerate(FORMAL_CASES):
        record = record_for(records, scene, vehicle, frame)
        geometry = record["geometry"]
        assert isinstance(geometry, Geometry)
        image = load_gray(data, scene, frame)
        patch, mask = load_patch_pair(data, scene, frame, geometry)
        optical_frame = int(record["optical_frame"])
        show_optical_triplet(axes[row_index, 0], data, states, scene, vehicle, optical_frame, f"{suffix(vehicle)} | {label}")
        draw_full_context(axes[row_index, 1], image, geometry, f"global raw SAR {frame}")
        raw_limits = common_raw_limits([(patch, mask)])
        show_patch(axes[row_index, 2], patch, mask, geometry, f"local raw | alpha={float(record['alpha_deg']):.1f}°", raw_limits=raw_limits, draw_radar_axes=True)
        for offset, sigma in enumerate(SIGMAS, start=3):
            show_patch(axes[row_index, offset], patch, mask, geometry, f"sigma={int(sigma)} descriptive", sigma=sigma)
        axes[row_index, 5].text(0.02, -0.22, str(record["identifiability_status"]), transform=axes[row_index, 5].transAxes, color="#F8C15C", fontsize=7)
    fig.text(0.01, 0.01, "Enhancement never substitutes for raw grayscale. A structure visible only under one sigma is not admitted as a stable physical component.", color="#F8C15C", fontsize=9)
    fig.suptitle("OTY2-RSA2-G2-R2B D06 | Near-side, intermediate-alpha, near-end and cross-scene aspect cases", color="white", fontsize=17, x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0.035, 1, 0.96])
    save_figure(fig, assets / "D06_ASPECT_CASE_COMPARISON.png")


def render_unidentifiable(
    assets: Path,
    data: Path,
    records: dict[tuple[str, str, int], dict[str, object]],
) -> None:
    cases = [
        ("GM_RM011", "GM_RM011:PV001", 16),
        ("GM_RM011", "GM_RM011:PV006", 256),
        ("GM_RM011", "GM_RM011:PV007", 281),
        ("GM_RM011", "GM_RM011:PV008", 315),
        ("GM_RM019", "GM_RM019:PV001", 27),
        ("GM_RM019", "GM_RM019:PV004", 350),
    ]
    fig, axes = plt.subplots(2, len(cases), figsize=(21, 9.5), facecolor="#0E151D")
    for col, (scene, vehicle, frame) in enumerate(cases):
        record = record_for(records, scene, vehicle, frame)
        geometry = record["geometry"]
        assert isinstance(geometry, Geometry)
        patch, mask = load_patch_pair(data, scene, frame, geometry)
        show_patch(axes[0, col], patch, mask, geometry, f"{scene[-2:]} {suffix(vehicle)} S{frame} raw | a={float(record['alpha_deg']):.1f}°", draw_radar_axes=True)
        show_patch(axes[1, col], patch, mask, geometry, "sigma=10 + boundary/background pressure", sigma=10.0)
        reason = textwrap.fill(
            str(record["ineligibility_reason"]).replace("_", " "),
            width=32,
        )
        axes[1, col].text(
            0.5,
            -0.18,
            reason,
            transform=axes[1, col].transAxes,
            color="#F8C15C",
            fontsize=6.2,
            ha="center",
            va="top",
            linespacing=1.15,
        )
    fig.text(
        0.01,
        0.012,
        "These cases cannot support the statement 'end-view vehicles have no response'. "
        "They support only: current image position/GT/identity/background makes the response unidentifiable.",
        color="#F8C15C",
        fontsize=9,
    )
    fig.suptitle("OTY2-RSA2-G2-R2B D07 | Background competition and non-identifiable cases", color="white", fontsize=17, x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0.10, 1, 0.95], h_pad=2.8, w_pad=1.0)
    save_figure(fig, assets / "D07_BACKGROUND_AND_UNIDENTIFIABLE_CASES.png")


def render_gm17_validation(
    assets: Path,
    data: Path,
    records: dict[tuple[str, str, int], dict[str, object]],
) -> None:
    sequences = [
        ("GM_RM017:PV003", [319, 342, 364, 378, 394]),
        ("GM_RM017:PV004", [338, 361, 390, 394, 446]),
    ]
    fig, axes = plt.subplots(2, 5, figsize=(20, 8), facecolor="#0E151D")
    for row_index, (vehicle, frames) in enumerate(sequences):
        prepared = []
        for frame in frames:
            record = record_for(records, "GM_RM017", vehicle, frame)
            geometry = record["geometry"]
            assert isinstance(geometry, Geometry)
            patch, mask = load_patch_pair(data, "GM_RM017", frame, geometry)
            prepared.append((frame, record, geometry, patch, mask))
        limits = common_raw_limits([(item[3], item[4]) for item in prepared])
        for col, (frame, record, geometry, patch, mask) in enumerate(prepared):
            show_patch(axes[row_index, col], patch, mask, geometry, f"{suffix(vehicle)} S{frame} | alpha={float(record['alpha_deg']):.1f}°", raw_limits=limits, draw_radar_axes=True)
    fig.text(0.01, 0.01, "PV003/PV004 validate role-level near-side fragments and background crossings within GM17; they do not establish cross-scene or near-end grammar.", color="#F8C15C", fontsize=9)
    fig.suptitle("OTY2-RSA2-G2-R2B D08 | GM17 validation threads across alpha", color="white", fontsize=17, x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    save_figure(fig, assets / "D08_GM17_VALIDATION_THREADS.png")


def render_grammar_summary(assets: Path) -> None:
    fig, ax = plt.subplots(figsize=(19, 10.5), facecolor="#0E151D")
    ax.axis("off")
    ax.set_title("OTY2-RSA2-G2-R2B D09 | First aspect-conditioned SAR response grammar", color="white", fontsize=18, loc="left")
    columns = [
        (0.03, "Shared high-level relations", [
            "vehicle-scale neighbourhood and undirected u axis",
            "near/far and endpoint/interior relations",
            "raw-gray first; enhancement is descriptive only",
            "cross-frame persistence may include split/merge/contract/shift",
            "background, road, fan and invalid-boundary competition remain explicit",
        ], "#38BDF8"),
        (0.35, "Upper observed alpha / near-side state", [
            "near-side longitudinal band is most continuous and strongest",
            "offset hotspot/short segment may co-occur",
            "band can touch/cross GT boundary",
            "body versus vehicle-ground remains unresolved",
            "manual card support: alpha 73.145°–89.972°",
        ], "#FFD166"),
        (0.67, "Intermediate alpha", [
            "near-side band shortens or fragments",
            "endpoint imbalance and local hotspots increase",
            "background crossings become more competitive",
            "role-level continuity exists in GM17, not a fixed template",
            "no universal peak interval is frozen",
        ], "#F59E0B"),
    ]
    for x, title, lines, color in columns:
        ax.add_patch(Rectangle((x, 0.46), 0.28, 0.43, transform=ax.transAxes, facecolor="#111827", edgecolor=color, linewidth=2))
        wrapped_title = textwrap.fill(title, width=31)
        wrapped_lines = "\n".join(
            "• " + textwrap.fill(line, width=38, subsequent_indent="  ")
            for line in lines
        )
        ax.text(
            x + 0.015,
            0.84,
            wrapped_title,
            transform=ax.transAxes,
            color=color,
            fontsize=11.5,
            weight="bold",
            va="top",
            linespacing=1.1,
        )
        ax.text(
            x + 0.02,
            0.77,
            wrapped_lines,
            transform=ax.transAxes,
            color="#E5E7EB",
            fontsize=9.3,
            va="top",
            linespacing=1.35,
        )
    ax.add_patch(Rectangle((0.03, 0.08), 0.92, 0.29, transform=ax.transAxes, facecolor="#1F2937", edgecolor="#FB7185", linewidth=2))
    ax.text(0.05, 0.33, "Near-end / cross-scene status", transform=ax.transAxes, color="#FB7185", fontsize=12, weight="bold")
    near_end_status = textwrap.fill(
        "GM11 near-end candidates are dominated by radial strong lines, fan arcs and invalid-boundary structure; "
        "GM19 anchors are sparse and truncated. Therefore the correct conclusion is NOT_IDENTIFIABLE, not "
        "'no vehicle response'. Full 0–90° transition grammar is not established.",
        width=145,
    )
    next_stage_status = textwrap.fill(
        "Conditional next-stage status: only a GM17, side-dominant, raw-visible, valid-interior micro-pilot "
        "within the actually card-supported alpha envelope may be considered after this round. This envelope "
        "is evidence scope, not a runtime threshold.",
        width=145,
    )
    ax.text(0.05, 0.285, near_end_status, transform=ax.transAxes, color="#E5E7EB", fontsize=10, va="top", linespacing=1.25)
    ax.text(0.05, 0.16, next_stage_status, transform=ax.transAxes, color="#F8C15C", fontsize=10, va="top", linespacing=1.25)
    save_figure(fig, assets / "D09_ASPECT_CONDITIONED_GRAMMAR_SUMMARY.png")


def main() -> None:
    args = parse_args()
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    required = [
        args.repo / "manifests/oty2/oty2_s0_sar_gt_quality_audit.csv",
        args.repo / "manifests/oty2/oty2_p1e_canonical_vehicle_frame_states.csv",
        args.repo / "manifests/oty2/oty2_rsa0_response_atlas_regions_v1.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required inputs: " + "; ".join(missing))

    gt_rows = read_csv(required[0])
    state_rows = read_csv(required[1])
    gt_map = preferred_gt_map(gt_rows)
    states = optical_state_map(state_rows)
    eligibility, records = build_eligibility_rows(gt_map, states, args.data)
    cards, overlays = build_component_cards(args.repo, records)
    lineage = build_lineage_rows(cards)

    write_csv(args.eligibility_manifest, ELIGIBILITY_FIELDS, eligibility)
    write_csv(args.component_manifest, COMPONENT_FIELDS, cards)
    write_csv(args.lineage_manifest, LINEAGE_FIELDS, lineage)

    render_alpha_overview(args.assets_dir, eligibility)
    render_pv002_continuous(args.assets_dir, args.data, states, records)
    render_component_cards(args.assets_dir, args.data, records, cards, overlays)
    render_coordinate_comparison(args.assets_dir, args.data, records)
    render_lineage(args.assets_dir, args.data, records, cards, overlays, lineage)
    render_aspect_cases(args.assets_dir, args.data, states, records)
    render_unidentifiable(args.assets_dir, args.data, records)
    render_gm17_validation(args.assets_dir, args.data, records)
    render_grammar_summary(args.assets_dir)

    identifiable = [row for row in eligibility if str(row["grammar_eligibility"]).startswith(("DEVELOPMENT", "HOLDOUT"))]
    card_supported = [row for row in cards if row["component_role"] == "NEAR_SIDE_LONGITUDINAL_BAND"]
    reliable_alpha = [float(row["alpha_deg"]) for row in identifiable]
    card_alpha = [float(row["alpha_deg"]) for row in card_supported]
    summary: dict[str, object] = {
        "task": "OTY2-RSA2-G2-R2B",
        "status": "ASPECT_CONDITIONED_RESPONSE_GRAMMAR_V1_PARTIALLY_ESTABLISHED",
        "full_transition_status": "ASPECT_RANGE_INSUFFICIENT_FOR_FULL_TRANSITION",
        "eligibility_rows": len(eligibility),
        "component_cards": len(cards),
        "lineage_relations": len(lineage),
        "actual_alpha_range_all_selected_deg": [
            min(float(row["alpha_deg"]) for row in eligibility),
            max(float(row["alpha_deg"]) for row in eligibility),
        ],
        "reliable_identifiable_gm17_alpha_range_deg": [min(reliable_alpha), max(reliable_alpha)],
        "manual_component_card_alpha_range_deg": [min(card_alpha), max(card_alpha)],
        "manual_component_card_alpha_scope": (
            "NEAR_SIDE_LONGITUDINAL_BAND role only; this is not the alpha range of all 51 cards"
        ),
        "same_vehicle_reliable_windows": [
            "GM_RM017:PV002 source responsibility span SAR315-386; grammar-eligible selected frames SAR317-386 (n=64)",
            "GM_RM017:PV003 source thread SAR315-394; grammar-eligible selected frames n=67 with 6 diagnostic-only gaps",
            "GM_RM017:PV004 source thread SAR337-394; grammar-eligible selected frames n=58",
        ],
        "same_vehicle_window_scope": (
            "thread-level identity/trajectory continuity; eligibility remains per selected row and does not imply "
            "that every integer frame in each span is admitted"
        ),
        "near_end_status": "NOT_IDENTIFIABLE_IN_CURRENT_GM11_BACKGROUND_AND_GT_CONDITIONS",
        "gm17_near_band_judgment": (
            "primarily upper-observed-alpha / near-side conditioned; weaker fragments persist "
            "into intermediate alpha; not demonstrated for near-end"
        ),
        "gt_blind_joint_qualification": "CONDITIONALLY_QUALIFIED_FOR_GM17_SIDE_DOMINANT_CARD_SUPPORTED_SCOPE_ONLY",
        "gt_blind_scope_note": (
            "Only GM17 side-dominant, high-identity, valid-interior, raw-visible windows inside the "
            "observed manual-card alpha envelope; this is evidence scope, not a runtime threshold."
        ),
        "forbidden": [
            "R2A rerun", "GT-blind execution", "candidate generation", "score/rank/selector/winner",
            "centre recovery formula", "response mask", "final box", "training annotation",
        ],
        "inputs": [str(path) for path in required],
        "missing_paths": [],
        "assets": [str(path) for path in sorted(args.assets_dir.glob("D*.png"))],
        "manifests": [str(args.eligibility_manifest), str(args.component_manifest), str(args.lineage_manifest)],
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
