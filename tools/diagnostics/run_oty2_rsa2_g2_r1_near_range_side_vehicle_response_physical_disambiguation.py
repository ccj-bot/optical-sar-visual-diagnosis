#!/usr/bin/env python3
"""Render the OTY2-RSA2-G2-R1 physical-disambiguation evidence pack.

Research-period SAR GT is used only for geometry coordinates, leave-one-frame-out
thread smoothing, and explicit matched controls.  It is never used as a response
mask.  This script does not generate response masks, candidates, rankings,
selectors, winners, automatic locations, final boxes, or training samples.
"""

from __future__ import annotations

import argparse
import csv
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
    "docs/reviews/assets/20260718_rsa2_g2_r1_near_range_physical_disambiguation"
)
DEFAULT_MANIFEST = DEFAULT_REPO / (
    "manifests/oty2/oty2_rsa2_g2_r1_near_range_physical_disambiguation_manifest.csv"
)
FAN_ORIGIN = np.array([1154.0, 1330.6], dtype=np.float64)
GRID_M_PER_PX = 0.03
PATCH_WIDTH = 360
PATCH_HEIGHT = 240
SIGMAS = (4.0, 10.0, 20.0)

COLORS = {
    "PV001": "#41D3BD",
    "PV002": "#FFD166",
    "PV003": "#F72585",
    "PV004": "#7B61FF",
    "PV007": "#FF6B6B",
    "PV008": "#9EF01A",
}

PV002_SEQUENCE = [
    (153, 319, "pre-bracket / left clipped"),
    (164, 342, "inside / approach"),
    (167, 348, "inside / near recorded minimum"),
    (173, 361, "inside / departure"),
    (181, 378, "post-bracket / right clipped"),
]
MULTIVEHICLE_WINDOWS = [(164, 342), (173, 361), (181, 378)]
GM17_VEHICLES = ["GM_RM017:PV004", "GM_RM017:PV003", "GM_RM017:PV002"]
HOLDOUT_WINDOWS = [(178, 370), (178, 371)]

CASE_META = {
    ("GM_RM017:PV002", 319): {
        "event_stage": "pre-bracket / left clipped",
        "optical_pose": "side-dominant; left image truncation",
        "background": "parked-road corridor; far-side arc/line competitive",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV002", 342): {
        "event_stage": "inside / approach",
        "optical_pose": "complete side view; front appears optical-left",
        "background": "parked-road corridor; road/curb axis approximately vehicle-parallel",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV002", 348): {
        "event_stage": "inside / near recorded minimum",
        "optical_pose": "complete side view; front appears optical-left",
        "background": "parked-road corridor; diagonal return at +u side",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV002", 361): {
        "event_stage": "inside / departure",
        "optical_pose": "complete side view; front appears optical-left",
        "background": "parked-road corridor; diagonal return at +u side",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV002", 378): {
        "event_stage": "post-bracket / right clipped",
        "optical_pose": "side-dominant; right image truncation",
        "background": "parked-road corridor; fan edge enters lower-right context",
        "boundary": "near valid-fan edge in local context",
    },
    ("GM_RM017:PV003", 342): {
        "event_stage": "shared platform window / approaching own minimum",
        "optical_pose": "complete side view; front appears optical-left",
        "background": "parked-road corridor; vehicle and road axes nearly parallel",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV003", 361): {
        "event_stage": "shared platform window / near own minimum",
        "optical_pose": "complete side view; front appears optical-left",
        "background": "parked-road corridor; fan-tangent line also present on far side",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV003", 378): {
        "event_stage": "shared platform window / near own minimum",
        "optical_pose": "complete side view with foreground-pole context",
        "background": "parked-road corridor; vehicle and road axes nearly parallel",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV004", 342): {
        "event_stage": "shared platform window / approach",
        "optical_pose": "side-dominant with left image truncation",
        "background": "parked-road corridor; fan tangent strongly oblique to vehicle axis",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV004", 361): {
        "event_stage": "shared platform window / approach",
        "optical_pose": "complete side-dominant view",
        "background": "parked-road corridor; fan tangent oblique to vehicle axis",
        "boundary": "valid fan interior",
    },
    ("GM_RM017:PV004", 378): {
        "event_stage": "shared platform window / late approach",
        "optical_pose": "complete side-dominant view",
        "background": "parked-road corridor; fan tangent separation is smaller",
        "boundary": "valid fan interior",
    },
}


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


def suffix(vehicle: str) -> str:
    return vehicle.split(":")[-1]


def normalize_axis_angle(angle_deg: float) -> float:
    return ((angle_deg + 90.0) % 180.0) - 90.0


def axial_difference_deg(a: float, b: float) -> float:
    return abs(normalize_axis_angle(a - b))


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


@dataclass(frozen=True)
class Geometry:
    cx: float
    cy: float
    long_px: float
    short_px: float
    axis_deg: float
    source: str


def longest_edge_geometry(row: dict[str, str], source: str = "PER_FRAME_GT") -> Geometry:
    cx, cy, width, height, raw_angle = parse_bbox(row)
    corners = box_corners(cx, cy, width, height, raw_angle)
    vectors = np.roll(corners, -1, axis=0) - corners
    lengths = np.linalg.norm(vectors, axis=1)
    vector = vectors[int(np.argmax(lengths))]
    angle = normalize_axis_angle(math.degrees(math.atan2(vector[1], vector[0])))
    ordered = np.sort(lengths)
    return Geometry(
        cx=cx,
        cy=cy,
        long_px=float(ordered[-1]),
        short_px=float(ordered[0]),
        axis_deg=angle,
        source=source,
    )


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


def choose_gt(
    rows: list[dict[str, str]], scene: str, vehicle: str, frame: int
) -> dict[str, str]:
    selected = best_gt_rows(rows, scene, vehicle)
    if frame not in selected:
        raise RuntimeError(f"missing GT: {scene} {vehicle} SAR {frame}")
    return selected[frame]


def axial_mean_deg(angles_deg: list[float]) -> float:
    radians = np.deg2rad(np.asarray(angles_deg, dtype=np.float64) * 2.0)
    value = 0.5 * math.degrees(
        math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean()))
    )
    return normalize_axis_angle(value)


def robust_poly_predict(x: np.ndarray, y: np.ndarray, x0: float) -> float:
    degree = min(2, max(1, len(x) - 1))
    center = float(np.median(x))
    xx = x - center
    mask = np.ones(len(x), dtype=bool)
    for _ in range(5):
        coeff = np.polyfit(xx[mask], y[mask], degree)
        residual = np.abs(y - np.polyval(coeff, xx))
        median = float(np.median(residual[mask]))
        mad = float(np.median(np.abs(residual[mask] - median)))
        threshold = max(2.5, median + 3.5 * 1.4826 * mad)
        updated = residual <= threshold
        if int(updated.sum()) < degree + 3 or np.array_equal(updated, mask):
            break
        mask = updated
    coeff = np.polyfit(xx[mask], y[mask], degree)
    return float(np.polyval(coeff, x0 - center))


def stable_geometry_loo(
    rows: list[dict[str, str]], scene: str, vehicle: str, target_frame: int
) -> Geometry:
    selected = best_gt_rows(rows, scene, vehicle)
    frames = sorted(selected)
    local_frames = [
        frame for frame in frames if frame != target_frame and abs(frame - target_frame) <= 48
    ]
    if len(local_frames) < 12:
        local_frames = [frame for frame in frames if frame != target_frame]
    geometries = [longest_edge_geometry(selected[frame]) for frame in local_frames]
    x = np.asarray(local_frames, dtype=np.float64)
    return Geometry(
        cx=robust_poly_predict(x, np.asarray([item.cx for item in geometries]), target_frame),
        cy=robust_poly_predict(x, np.asarray([item.cy for item in geometries]), target_frame),
        long_px=float(np.median([item.long_px for item in geometries])),
        short_px=float(np.median([item.short_px for item in geometries])),
        axis_deg=axial_mean_deg([item.axis_deg for item in geometries]),
        source="THREAD_STABLE_LOO",
    )


def sar_path(data: Path, scene: str, frame: int) -> Path:
    return data / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def optical_path(data: Path, scene: str, frame: int) -> Path:
    return data / scene / f"{scene}_frames" / f"{frame:06d}.png"


def load_gray(data: Path, scene: str, frame: int) -> np.ndarray:
    return np.asarray(Image.open(sar_path(data, scene, frame)).convert("L"), dtype=np.float32)


def load_rgb(data: Path, scene: str, frame: int) -> np.ndarray:
    return np.asarray(Image.open(optical_path(data, scene, frame)).convert("RGB"))


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


def fan_geometry(center: tuple[float, float]) -> tuple[float, float, float, np.ndarray, np.ndarray]:
    vector = np.asarray(center, dtype=np.float64) - FAN_ORIGIN
    radius = float(np.linalg.norm(vector))
    radial_away = vector / max(radius, 1e-9)
    near = -radial_away
    tangent = np.array([-radial_away[1], radial_away[0]], dtype=np.float64)
    radial_angle = math.degrees(math.atan2(radial_away[1], radial_away[0]))
    tangent_angle = normalize_axis_angle(radial_angle + 90.0)
    theta = math.degrees(math.atan2(vector[0], -vector[1]))
    return radius, theta, tangent_angle, near, tangent


def sample_signed_patch(
    image: np.ndarray,
    geometry: Geometry,
    center: tuple[float, float] | None = None,
    width: int = PATCH_WIDTH,
    height: int = PATCH_HEIGHT,
) -> np.ndarray:
    if center is not None:
        geometry = Geometry(
            center[0], center[1], geometry.long_px, geometry.short_px,
            geometry.axis_deg, geometry.source,
        )
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
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def local_contrast(patch: np.ndarray, sigma: float) -> np.ndarray:
    return patch - cv2.GaussianBlur(patch, (0, 0), sigmaX=sigma, sigmaY=sigma)


def common_raw_limits(patches: list[np.ndarray]) -> tuple[float, float]:
    values = np.concatenate([patch[patch > 0].ravel() for patch in patches])
    return float(np.percentile(values, 1.0)), float(np.percentile(values, 99.7))


def common_contrast_limit(patches: list[np.ndarray], sigma: float) -> float:
    values = np.concatenate(
        [np.abs(local_contrast(patch, sigma)[patch > 0]).ravel() for patch in patches]
    )
    return max(float(np.percentile(values, 99.2)), 1.0)


def extent() -> list[float]:
    return [
        -PATCH_WIDTH * GRID_M_PER_PX / 2,
        PATCH_WIDTH * GRID_M_PER_PX / 2,
        PATCH_HEIGHT * GRID_M_PER_PX / 2,
        -PATCH_HEIGHT * GRID_M_PER_PX / 2,
    ]


def draw_reference_box(
    ax: plt.Axes,
    geometry: Geometry,
    color: str,
    linestyle: str = "-",
    alpha: float = 1.0,
) -> None:
    long_m = geometry.long_px * GRID_M_PER_PX
    short_m = geometry.short_px * GRID_M_PER_PX
    ax.add_patch(
        Rectangle(
            (-long_m / 2, -short_m / 2),
            long_m,
            short_m,
            fill=False,
            edgecolor=color,
            linewidth=1.8,
            linestyle=linestyle,
            alpha=alpha,
        )
    )


def show_patch(
    ax: plt.Axes,
    patch: np.ndarray,
    geometry: Geometry,
    title: str,
    *,
    raw_limits: tuple[float, float] | None = None,
    sigma: float | None = None,
    contrast_limit: float | None = None,
    tangent_difference_deg: float | None = None,
    xlabel: bool = True,
    color: str | None = None,
) -> None:
    title_vehicle = title.split("|")[0].strip().split()[0]
    color = color or COLORS.get(title_vehicle, "#FFD166")
    if sigma is None:
        low, high = raw_limits or common_raw_limits([patch])
        ax.imshow(patch, cmap="gray", vmin=low, vmax=high, extent=extent())
    else:
        contrast = local_contrast(patch, sigma)
        limit = contrast_limit or common_contrast_limit([patch], sigma)
        ax.imshow(contrast, cmap="coolwarm", vmin=-limit, vmax=limit, extent=extent())
    draw_reference_box(ax, geometry, color)
    ax.axhline(0, color="#94A3B8", linewidth=0.45, alpha=0.55)
    ax.axvline(0, color="#94A3B8", linewidth=0.45, alpha=0.55)
    ax.annotate(
        "+v near range",
        xy=(-PATCH_WIDTH * GRID_M_PER_PX * 0.43, geometry.short_px * GRID_M_PER_PX * 0.75),
        xytext=(-PATCH_WIDTH * GRID_M_PER_PX * 0.43, geometry.short_px * GRID_M_PER_PX * 1.6),
        arrowprops={"arrowstyle": "->", "color": "#54E0FF", "lw": 1.2},
        color="#54E0FF",
        fontsize=6.5,
    )
    if tangent_difference_deg is not None:
        length = 2.5
        angle = math.radians(tangent_difference_deg)
        dx = length * math.cos(angle)
        dy = length * math.sin(angle)
        ax.plot([-dx, dx], [-dy, dy], color="#00E5FF", linewidth=1.0, linestyle="--")
        ax.text(
            0.98,
            0.04,
            f"fan tangent Δ={abs(tangent_difference_deg):.1f}°",
            transform=ax.transAxes,
            ha="right",
            color="#00E5FF",
            fontsize=6.5,
        )
    ax.set_title(title, color="white", fontsize=8)
    if xlabel:
        ax.set_xlabel("u: vehicle long axis (m-grid; undirected)", color="#CBD5E1", fontsize=6.5)
    ax.set_ylabel("v: + toward fan origin", color="#CBD5E1", fontsize=6.5)
    ax.tick_params(colors="#94A3B8", labelsize=5.5)
    ax.grid(color="#64748B", alpha=0.18, linewidth=0.35)


def show_optical_crop(
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
    if row and row["reference_bbox_available"] == "true":
        x1, y1, x2, y2 = (
            float(row[key])
            for key in (
                "reference_bbox_x1",
                "reference_bbox_y1",
                "reference_bbox_x2",
                "reference_bbox_y2",
            )
        )
        pad_x = max(55.0, (x2 - x1) * 0.22)
        pad_y = max(40.0, (y2 - y1) * 0.22)
        left, right = max(0, int(x1 - pad_x)), min(image.shape[1], int(x2 + pad_x))
        top, bottom = max(0, int(y1 - pad_y)), min(image.shape[0], int(y2 + pad_y))
        ax.imshow(image[top:bottom, left:right])
        ax.add_patch(
            Rectangle(
                (x1 - left, y1 - top),
                x2 - x1,
                y2 - y1,
                fill=False,
                edgecolor=COLORS[suffix(vehicle)],
                linewidth=1.8,
            )
        )
    else:
        ax.imshow(image)
    ax.set_title(title, color="white", fontsize=8)
    ax.axis("off")


def optical_state_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, int], dict[str, str]]:
    return {
        (row["scene"], row["canonical_vehicle_id"], int(row["frame_index"])): row
        for row in rows
    }


def control_center(
    geometry: Geometry, control_type: str, displacement_px: float
) -> tuple[float, float]:
    center = np.array([geometry.cx, geometry.cy], dtype=np.float64)
    radius, _, _, near, tangent = fan_geometry((geometry.cx, geometry.cy))
    u, _, _ = signed_axes(geometry)
    if control_type == "NEAR_RADIAL":
        point = center + near * displacement_px
    elif control_type == "FAR_RADIAL":
        point = center - near * displacement_px
    elif control_type in {"TANGENTIAL_PLUS", "TANGENTIAL_MINUS", "EMPTY_ROAD_TANGENTIAL"}:
        sign = 1.0 if control_type in {"TANGENTIAL_PLUS", "EMPTY_ROAD_TANGENTIAL"} else -1.0
        radial_away = (center - FAN_ORIGIN) / max(radius, 1e-9)
        angle = sign * displacement_px / max(radius, 1e-9)
        rotation = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        point = FAN_ORIGIN + rotation @ (radial_away * radius)
    elif control_type == "U_PLUS_EXTENSION":
        point = center + u * displacement_px
    elif control_type == "U_MINUS_EXTENSION":
        point = center - u * displacement_px
    elif control_type == "FAR_BACKGROUND":
        point = center - near * displacement_px
    else:
        point = center
    return float(point[0]), float(point[1])


def descriptive_measurements(patch: np.ndarray, geometry: Geometry) -> dict[str, float]:
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
    result = {"raw_near_minus_far_mean": raw_delta}
    for sigma in SIGMAS:
        contrast = local_contrast(patch, sigma)
        near_values = contrast[inside_near & valid]
        far_values = contrast[inside_far & valid]
        result[f"sigma{int(sigma)}_near_minus_far_mean"] = (
            float(near_values.mean() - far_values.mean())
            if near_values.size and far_values.size
            else float("nan")
        )
    profile_valid = inside_u & valid
    detrended = local_contrast(patch, 20.0)
    profile = np.full(PATCH_HEIGHT, np.nan, dtype=np.float64)
    for row_index in range(PATCH_HEIGHT):
        row_mask = profile_valid[row_index]
        if int(row_mask.sum()) > 20:
            profile[row_index] = float(detrended[row_index, row_mask].mean())
    start = max(0, int((PATCH_HEIGHT - 1) / 2 - geometry.short_px * 0.9))
    end = min(PATCH_HEIGHT, int((PATCH_HEIGHT - 1) / 2 + geometry.short_px * 1.4))
    local = profile[start:end]
    if local.size and np.isfinite(local).any():
        peak_row = start + int(np.nanargmax(local))
        peak_v = peak_row - (PATCH_HEIGHT - 1) / 2
        result["profile_peak_v_px"] = float(peak_v)
        result["profile_peak_v_over_halfwidth"] = float(
            peak_v / max(geometry.short_px / 2, 1e-9)
        )
    else:
        result["profile_peak_v_px"] = float("nan")
        result["profile_peak_v_over_halfwidth"] = float("nan")
    return result


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=135, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def add_manifest_row(
    rows: list[dict[str, object]],
    *,
    case_id: str,
    scene: str,
    vehicle: str,
    optical_frame: int,
    sar_frame: int,
    coordinate_scheme: str,
    geometry: Geometry,
    per_frame: Geometry,
    patch: np.ndarray,
    control_type: str = "TRUE_NEIGHBORHOOD",
    control_displacement_px: float = 0.0,
    observation_raw: str = "manual_review_in_report",
    observation_multiscale: str = "manual_review_in_report",
    interpretation_status: str = "NOT_IDENTIFIABLE",
    eliminated: str = "none_by_this_row_alone",
    not_eliminated: str = "vehicle-body; vehicle-ground; road/curb; imaging mixture",
    event_stage_override: str | None = None,
) -> None:
    radius, theta, tangent_deg, _, _ = fan_geometry((geometry.cx, geometry.cy))
    _, v, sign_dot = signed_axes(geometry)
    measurements = descriptive_measurements(patch, geometry)
    meta = CASE_META.get((vehicle, sar_frame), {})
    rows.append(
        {
            "case_id": case_id,
            "scene": scene,
            "canonical_vehicle_id": vehicle,
            "optical_frame": optical_frame,
            "sar_frame": sar_frame,
            "event_stage": event_stage_override or meta.get("event_stage", "shared or holdout window"),
            "coordinate_scheme": coordinate_scheme,
            "u_direction_status": "UNDIRECTED_HEAD_TAIL_NOT_TRANSFERRED",
            "u_axis_deg": f"{geometry.axis_deg:.3f}",
            "v_near_unit_x": f"{v[0]:.6f}",
            "v_near_unit_y": f"{v[1]:.6f}",
            "near_sign_dot_to_origin": f"{sign_dot:.6f}",
            "reference_center_x_px": f"{geometry.cx:.3f}",
            "reference_center_y_px": f"{geometry.cy:.3f}",
            "reference_long_axis_px": f"{geometry.long_px:.3f}",
            "reference_short_axis_px": f"{geometry.short_px:.3f}",
            "radius_px": f"{radius:.3f}",
            "fan_theta_deg": f"{theta:.3f}",
            "fan_tangent_deg": f"{tangent_deg:.3f}",
            "u_vs_fan_tangent_axial_difference_deg": f"{axial_difference_deg(geometry.axis_deg, tangent_deg):.3f}",
            "u_vs_radial_axial_difference_deg": f"{abs(90.0 - axial_difference_deg(geometry.axis_deg, tangent_deg)):.3f}",
            "perframe_to_stable_center_delta_px": f"{math.hypot(geometry.cx - per_frame.cx, geometry.cy - per_frame.cy):.3f}",
            "perframe_to_stable_axis_delta_deg": f"{axial_difference_deg(geometry.axis_deg, per_frame.axis_deg):.3f}",
            "boundary_state": meta.get("boundary", "valid fan interior"),
            "optical_pose": meta.get("optical_pose", "side-dominant parked vehicle; head-tail SAR transfer unresolved"),
            "optical_head_tail_status": "optical front/rear partly visible; mapping to SAR u sign not reliable",
            "local_background_type": meta.get("background", "parked-road corridor / static background"),
            "control_type": control_type,
            "control_displacement_px": f"{control_displacement_px:.3f}",
            "control_displacement_short_axes": f"{control_displacement_px / max(geometry.short_px, 1e-9):.3f}",
            "raw_near_minus_far_mean": f"{measurements['raw_near_minus_far_mean']:.6f}",
            "sigma4_near_minus_far_mean": f"{measurements['sigma4_near_minus_far_mean']:.6f}",
            "sigma10_near_minus_far_mean": f"{measurements['sigma10_near_minus_far_mean']:.6f}",
            "sigma20_near_minus_far_mean": f"{measurements['sigma20_near_minus_far_mean']:.6f}",
            "profile_peak_v_px": f"{measurements['profile_peak_v_px']:.3f}",
            "profile_peak_v_over_halfwidth": f"{measurements['profile_peak_v_over_halfwidth']:.3f}",
            "observation_raw_gray": observation_raw,
            "observation_multiscale": observation_multiscale,
            "physical_interpretation_status": interpretation_status,
            "this_control_eliminates_or_weakens": eliminated,
            "this_control_does_not_eliminate": not_eliminated,
            "gt_usage_boundary": (
                "research_geometry_and_leave_one_frame_out_alignment_only; "
                "not_response_mask_not_runtime_input"
            ),
        }
    )


def render_signed_context(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    states: dict[tuple[str, str, int], dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    patches: list[np.ndarray] = []
    records: list[tuple[int, int, str, Geometry, Geometry, np.ndarray]] = []
    for optical_frame, sar_frame in MULTIVEHICLE_WINDOWS:
        for vehicle in GM17_VEHICLES:
            per_frame = longest_edge_geometry(choose_gt(gt_rows, scene, vehicle, sar_frame))
            geometry = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
            patch = sample_signed_patch(load_gray(data, scene, sar_frame), geometry)
            patches.append(patch)
            records.append((optical_frame, sar_frame, vehicle, per_frame, geometry, patch))
    limits = common_raw_limits(patches)
    fig, axes = plt.subplots(3, 5, figsize=(18, 10.5), facecolor="#0E151D")
    by_window = {(o, s, v): (pf, g, p) for o, s, v, pf, g, p in records}
    for row_index, (optical_frame, sar_frame) in enumerate(MULTIVEHICLE_WINDOWS):
        optical = load_rgb(data, scene, optical_frame)
        axes[row_index, 0].imshow(optical)
        axes[row_index, 0].set_title(f"Optical {optical_frame} | all parked cars", color="white", fontsize=8)
        axes[row_index, 0].axis("off")
        image = load_gray(data, scene, sar_frame)
        low, high = np.percentile(image[image > 0], [1.0, 99.8])
        axes[row_index, 1].imshow(image, cmap="gray", vmin=low, vmax=high)
        for vehicle in GM17_VEHICLES:
            gt = choose_gt(gt_rows, scene, vehicle, sar_frame)
            corners = box_corners(*parse_bbox(gt))
            axes[row_index, 1].add_patch(
                Polygon(corners, closed=True, fill=False, edgecolor=COLORS[suffix(vehicle)], linewidth=1.3)
            )
            stable = by_window[(optical_frame, sar_frame, vehicle)][1]
            _, v, _ = signed_axes(stable)
            axes[row_index, 1].arrow(
                stable.cx,
                stable.cy,
                v[0] * 70,
                v[1] * 70,
                color="#54E0FF",
                width=1.2,
                head_width=14,
                length_includes_head=True,
            )
        axes[row_index, 1].set_xlim(650, 1500)
        axes[row_index, 1].set_ylim(1160, 760)
        axes[row_index, 1].set_title(
            f"Original SAR {sar_frame} | cyan arrows: +v to origin", color="white", fontsize=8
        )
        axes[row_index, 1].axis("off")
        for col, vehicle in enumerate(GM17_VEHICLES, start=2):
            per_frame, geometry, patch = by_window[(optical_frame, sar_frame, vehicle)]
            tangent = fan_geometry((geometry.cx, geometry.cy))[2]
            diff = normalize_axis_angle(tangent - geometry.axis_deg)
            show_patch(
                axes[row_index, col],
                patch,
                geometry,
                f"{suffix(vehicle)} | stable raw | SAR {sar_frame}",
                raw_limits=limits,
                tangent_difference_deg=diff,
            )
            add_manifest_row(
                manifest_rows,
                case_id="C01",
                scene=scene,
                vehicle=vehicle,
                optical_frame=optical_frame,
                sar_frame=sar_frame,
                coordinate_scheme="THREAD_STABLE_LOO",
                geometry=geometry,
                per_frame=per_frame,
                patch=patch,
                observation_raw=(
                    "vehicle-scale bright segments remain concentrated near +v; "
                    "continuity differs by vehicle and frame"
                ),
                observation_multiscale="raw grayscale is primary; multiscale audit is shown in C02/C04",
                interpretation_status="VEHICLE_GROUND_MIXED_PLAUSIBLE",
                eliminated="fixed image up/down sign and pure fan-tangent explanation in high-angle PV004 windows",
            )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C01 | Signed near-range coordinates in original optical/SAR context",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "All raw local panels share one grayscale range. +v is explicitly corrected toward the fan origin; u is undirected.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.95])
    save_figure(fig, assets / "C01_GM17_SIGNED_CONTEXT_AND_OPTICAL_POSE.png")


def render_pv002_alignment_display_audit(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    vehicle = "GM_RM017:PV002"
    records = []
    all_raw = []
    for optical_frame, sar_frame, phase in PV002_SEQUENCE:
        per_frame = longest_edge_geometry(choose_gt(gt_rows, scene, vehicle, sar_frame))
        stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
        image = load_gray(data, scene, sar_frame)
        per_patch = sample_signed_patch(image, per_frame)
        stable_patch = sample_signed_patch(image, stable)
        records.append((optical_frame, sar_frame, phase, per_frame, stable, per_patch, stable_patch))
        all_raw.extend([per_patch, stable_patch])
    raw_limits = common_raw_limits(all_raw)
    contrast_limits = {
        sigma: common_contrast_limit([item[-1] for item in records], sigma) for sigma in SIGMAS
    }
    fig, axes = plt.subplots(5, len(records), figsize=(18, 14.5), facecolor="#0E151D")
    for col, (optical_frame, sar_frame, phase, per_frame, stable, per_patch, stable_patch) in enumerate(records):
        show_patch(
            axes[0, col], per_patch, per_frame,
            f"PV002 | SAR {sar_frame} | per-frame GT raw", raw_limits=raw_limits,
        )
        show_patch(
            axes[1, col], stable_patch, stable,
            f"PV002 | SAR {sar_frame} | stable LOO raw", raw_limits=raw_limits,
        )
        for row_index, sigma in enumerate(SIGMAS, start=2):
            show_patch(
                axes[row_index, col],
                stable_patch,
                stable,
                f"PV002 | σ={sigma:g}px | {phase}",
                sigma=sigma,
                contrast_limit=contrast_limits[sigma],
            )
        add_manifest_row(
            manifest_rows,
            case_id="C02",
            scene=scene,
            vehicle=vehicle,
            optical_frame=optical_frame,
            sar_frame=sar_frame,
            coordinate_scheme="PER_FRAME_GT",
            geometry=per_frame,
            per_frame=per_frame,
            patch=per_patch,
            observation_raw="near-side bright band/segments visible in original grayscale; strength and continuity vary",
            observation_multiscale="same side bias persists; smaller sigma emphasizes edges and endpoints",
            interpretation_status="VEHICLE_GROUND_MIXED_PLAUSIBLE",
            eliminated="high-pass-only visual artifact",
        )
        add_manifest_row(
            manifest_rows,
            case_id="C02",
            scene=scene,
            vehicle=vehicle,
            optical_frame=optical_frame,
            sar_frame=sar_frame,
            coordinate_scheme="THREAD_STABLE_LOO",
            geometry=stable,
            per_frame=per_frame,
            patch=stable_patch,
            observation_raw="near-side band remains under leave-one-frame-out center/axis alignment",
            observation_multiscale="persistent across sigma 4/10/20; fragmentation is display-scale dependent",
            interpretation_status="VEHICLE_GROUND_MIXED_PLAUSIBLE",
            eliminated="per-frame GT micro-adjustment as sole cause",
        )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C02 | PV002 per-frame GT versus thread-stable LOO and display-scale audit",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "Raw rows share one sequence scale. Contrast rows share one scale per sigma. No threshold, mask, or candidate is produced.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.95])
    save_figure(fig, assets / "C02_PV002_PERFRAME_VS_THREAD_STABLE_MULTISCALE.png")


def render_pv002_adjacent_continuity(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    vehicle = "GM_RM017:PV002"
    groups = [(341, 342, 343), (347, 348, 349), (360, 361, 362), (377, 378, 379)]
    records = []
    patches = []
    for group_index, frames in enumerate(groups):
        for sar_frame in frames:
            gt = choose_gt(gt_rows, scene, vehicle, sar_frame)
            optical_frame = int(gt["optical_frame_index"])
            per_frame = longest_edge_geometry(gt)
            stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
            patch = sample_signed_patch(load_gray(data, scene, sar_frame), stable)
            records.append((group_index, optical_frame, sar_frame, per_frame, stable, patch))
            patches.append(patch)
    raw_limits = common_raw_limits(patches)
    fig, axes = plt.subplots(4, 3, figsize=(12, 12), facecolor="#0E151D")
    for group_index, optical_frame, sar_frame, per_frame, stable, patch in records:
        col = groups[group_index].index(sar_frame)
        show_patch(
            axes[group_index, col], patch, stable,
            f"PV002 | optical {optical_frame} / SAR {sar_frame}",
            raw_limits=raw_limits,
            color=COLORS["PV002"],
        )
        add_manifest_row(
            manifest_rows,
            case_id="C02B",
            scene=scene,
            vehicle=vehicle,
            optical_frame=optical_frame,
            sar_frame=sar_frame,
            coordinate_scheme="THREAD_STABLE_LOO",
            geometry=stable,
            per_frame=per_frame,
            patch=patch,
            observation_raw=(
                "adjacent raw frame shows continuous translation/reorganization of the same "
                "near-side strip and endpoints rather than an isolated selected-frame flash"
            ),
            observation_multiscale="not needed for this continuity responsibility; raw gray only",
            interpretation_status="VEHICLE_GROUND_MIXED_PLAUSIBLE",
            eliminated="representative-frame cherry-picking as the sole source of continuity",
            event_stage_override=f"adjacent continuity around SAR {groups[group_index][1]}",
        )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C02B | PV002 adjacent-frame raw continuity around key events",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "Each row is the frame before, key frame, and frame after. All panels share one grayscale range.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    save_figure(fig, assets / "C02B_PV002_ADJACENT_FRAME_RAW_CONTINUITY.png")


def render_matched_controls(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    cases = [
        ("GM_RM017:PV002", 164, 342),
        ("GM_RM017:PV004", 164, 342),
        ("GM_RM017:PV002", 173, 361),
    ]
    labels = [
        ("TRUE_NEIGHBORHOOD", 0.0),
        ("NEAR_RADIAL", 0.5),
        ("NEAR_RADIAL", 1.0),
        ("FAR_RADIAL", 0.5),
        ("FAR_RADIAL", 1.0),
        ("TANGENTIAL_PLUS", 1.0),
        ("TANGENTIAL_MINUS", 1.0),
        ("EMPTY_ROAD_TANGENTIAL", 1.0),
    ]
    records = []
    all_patches = []
    for vehicle, optical_frame, sar_frame in cases:
        per_frame = longest_edge_geometry(choose_gt(gt_rows, scene, vehicle, sar_frame))
        stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
        image = load_gray(data, scene, sar_frame)
        for control_type, scale in labels:
            if control_type == "TRUE_NEIGHBORHOOD":
                distance = 0.0
                center = (stable.cx, stable.cy)
            elif control_type == "EMPTY_ROAD_TANGENTIAL":
                distance = stable.long_px * scale
                direction = "TANGENTIAL_PLUS" if vehicle.endswith("PV002") else "TANGENTIAL_MINUS"
                center = control_center(stable, direction, distance)
            else:
                distance = stable.short_px * scale
                center = control_center(stable, control_type, distance)
            control_geometry = Geometry(
                center[0], center[1], stable.long_px, stable.short_px,
                stable.axis_deg, "CONTROL_THREAD_STABLE",
            )
            patch = sample_signed_patch(image, control_geometry)
            records.append(
                (vehicle, optical_frame, sar_frame, per_frame, stable, control_geometry, control_type, distance, patch)
            )
            all_patches.append(patch)
    raw_limits = common_raw_limits(all_patches)
    contrast_limit = common_contrast_limit(all_patches, 10.0)
    fig, axes = plt.subplots(len(cases) * 2, len(labels), figsize=(24, 15), facecolor="#0E151D")
    index = 0
    for case_index, (vehicle, optical_frame, sar_frame) in enumerate(cases):
        for col, (control_type, scale) in enumerate(labels):
            record = records[index]
            index += 1
            _, _, _, per_frame, stable, geometry, _, distance, patch = record
            short_units = distance / max(stable.short_px, 1e-9)
            title = f"{suffix(vehicle)} {sar_frame} | {control_type} | {short_units:.1f}W"
            show_patch(
                axes[case_index * 2, col], patch, geometry, title,
                raw_limits=raw_limits, xlabel=False, color=COLORS[suffix(vehicle)],
            )
            show_patch(
                axes[case_index * 2 + 1, col], patch, geometry, f"σ10 | {control_type}",
                sigma=10.0, contrast_limit=contrast_limit, color=COLORS[suffix(vehicle)],
            )
            if control_type == "TRUE_NEIGHBORHOOD":
                raw_note = "near-side band visible at the real vehicle geometry"
                status = "VEHICLE_GROUND_MIXED_PLAUSIBLE"
                weakened = "none by true row alone"
            elif control_type in {"NEAR_RADIAL", "FAR_RADIAL"}:
                side = "far half/outside" if control_type == "NEAR_RADIAL" else "near edge/outside"
                raw_note = (
                    f"the same physical strip moves to the control {side}; "
                    "no new strip relocks to the control +v boundary"
                )
                status = "CONTROL_NO_SIDE_LOCK_REPLICATION"
                weakened = "a generic local strip that would relock to every shifted control footprint"
            elif control_type.startswith("TANGENTIAL"):
                raw_note = (
                    "small same-radius 1W shift overlaps the local long-axis support; "
                    "continuation is expected and is not an independent empty-road negative"
                )
                status = "CONTROL_OVERLAPS_LOCAL_LENGTH_SUPPORT"
                weakened = "fan-radius or global brightness change as the only explanation"
            else:
                raw_note = (
                    "one-long-axis same-radius parked-corridor proxy contains background structure "
                    "but does not reproduce the target +v boundary lock"
                )
                status = "BACKGROUND_COMPETITIVE_NOT_SIDE_LOCKED"
                weakened = "pure vehicle-body ownership; exact road/curb attribution remains unresolved"
            add_manifest_row(
                manifest_rows,
                case_id="C03",
                scene=scene,
                vehicle=vehicle,
                optical_frame=optical_frame,
                sar_frame=sar_frame,
                coordinate_scheme="CONTROL_THREAD_STABLE",
                geometry=geometry,
                per_frame=per_frame,
                patch=patch,
                control_type=control_type,
                control_displacement_px=distance,
                observation_raw=raw_note,
                observation_multiscale="raw and sigma10 are shown side-by-side under common scales",
                interpretation_status=status,
                eliminated=weakened,
            )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C03 | Symmetric small radial and same-radius tangential controls",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "W means thread-stable vehicle short-axis width. Empty-road proxies use 1L same-radius tangential displacement.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.95])
    save_figure(fig, assets / "C03_MATCHED_RADIAL_TANGENTIAL_CONTROLS.png")


def render_pv004_axis_disambiguation(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
) -> None:
    scene = "GM_RM017"
    vehicle = "GM_RM017:PV004"
    frames = [(164, 342), (173, 361), (181, 378)]
    records = []
    patches = []
    for optical_frame, sar_frame in frames:
        per_frame = longest_edge_geometry(choose_gt(gt_rows, scene, vehicle, sar_frame))
        stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
        patch = sample_signed_patch(load_gray(data, scene, sar_frame), stable)
        records.append((optical_frame, sar_frame, per_frame, stable, patch))
        patches.append(patch)
    raw_limits = common_raw_limits(patches)
    contrast_limits = {sigma: common_contrast_limit(patches, sigma) for sigma in SIGMAS}
    fig, axes = plt.subplots(5, len(frames), figsize=(12, 15), facecolor="#0E151D")
    for col, (optical_frame, sar_frame, per_frame, stable, patch) in enumerate(records):
        image = load_gray(data, scene, sar_frame)
        low, high = np.percentile(image[image > 0], [1.0, 99.8])
        axes[0, col].imshow(image, cmap="gray", vmin=low, vmax=high)
        corners = box_corners(*parse_bbox(choose_gt(gt_rows, scene, vehicle, sar_frame)))
        axes[0, col].add_patch(
            Polygon(corners, closed=True, fill=False, edgecolor=COLORS["PV004"], linewidth=1.8)
        )
        u, v, _ = signed_axes(stable)
        _, _, _, _, tangent = fan_geometry((stable.cx, stable.cy))
        axes[0, col].arrow(stable.cx, stable.cy, u[0] * 120, u[1] * 120, color="#7B61FF", width=1.2)
        axes[0, col].arrow(stable.cx, stable.cy, v[0] * 85, v[1] * 85, color="#54E0FF", width=1.2)
        axes[0, col].arrow(
            stable.cx, stable.cy, tangent[0] * 120, tangent[1] * 120,
            color="#00E5FF", width=1.0, linestyle="--",
        )
        axes[0, col].set_xlim(stable.cx - 250, stable.cx + 250)
        axes[0, col].set_ylim(stable.cy + 210, stable.cy - 210)
        axes[0, col].set_title(
            f"PV004 SAR {sar_frame} | purple u, cyan tangent, blue +v", color="white", fontsize=8
        )
        axes[0, col].axis("off")
        tangent_deg = fan_geometry((stable.cx, stable.cy))[2]
        diff = normalize_axis_angle(tangent_deg - stable.axis_deg)
        show_patch(
            axes[1, col], patch, stable, f"PV004 | stable raw | Δ={abs(diff):.1f}°",
            raw_limits=raw_limits, tangent_difference_deg=diff,
        )
        for row_index, sigma in enumerate(SIGMAS, start=2):
            show_patch(
                axes[row_index, col], patch, stable, f"PV004 | σ={sigma:g}px | SAR {sar_frame}",
                sigma=sigma, contrast_limit=contrast_limits[sigma], tangent_difference_deg=diff,
            )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C04 | PV004 separates vehicle/road axis from fan tangent",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "PV004 is the key diagnostic: separation is about 37° at SAR342, 25° at SAR361, and 12° at SAR378.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.95])
    save_figure(fig, assets / "C04_PV004_VEHICLE_VS_FAN_AXIS_DISAMBIGUATION.png")


def render_pv004_adjacent_continuity(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    vehicle = "GM_RM017:PV004"
    groups = [(341, 342, 343), (360, 361, 362), (377, 378, 379)]
    records = []
    patches = []
    for group_index, frames in enumerate(groups):
        for sar_frame in frames:
            gt = choose_gt(gt_rows, scene, vehicle, sar_frame)
            optical_frame = int(gt["optical_frame_index"])
            per_frame = longest_edge_geometry(gt)
            stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
            patch = sample_signed_patch(load_gray(data, scene, sar_frame), stable)
            records.append((group_index, optical_frame, sar_frame, per_frame, stable, patch))
            patches.append(patch)
    raw_limits = common_raw_limits(patches)
    fig, axes = plt.subplots(3, 3, figsize=(12, 9.5), facecolor="#0E151D")
    for group_index, optical_frame, sar_frame, per_frame, stable, patch in records:
        col = groups[group_index].index(sar_frame)
        tangent_deg = fan_geometry((stable.cx, stable.cy))[2]
        diff = normalize_axis_angle(tangent_deg - stable.axis_deg)
        show_patch(
            axes[group_index, col], patch, stable,
            f"PV004 | optical {optical_frame} / SAR {sar_frame}",
            raw_limits=raw_limits,
            tangent_difference_deg=diff,
            color=COLORS["PV004"],
        )
        add_manifest_row(
            manifest_rows,
            case_id="C04B",
            scene=scene,
            vehicle=vehicle,
            optical_frame=optical_frame,
            sar_frame=sar_frame,
            coordinate_scheme="THREAD_STABLE_LOO",
            geometry=stable,
            per_frame=per_frame,
            patch=patch,
            observation_raw=(
                "adjacent PV004 raw frame retains short vehicle-axis segments near +v while "
                "fan-tangent structures cross at a different angle"
            ),
            observation_multiscale="raw gray only for temporal continuity; multiscale is C04",
            interpretation_status="VEHICLE_GROUND_MIXED_PLAUSIBLE",
            eliminated="a single-frame PV004 alignment coincidence",
            event_stage_override=f"adjacent continuity around SAR {groups[group_index][1]}",
        )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C04B | PV004 adjacent-frame raw continuity and fan-tangent separation",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "Each row is before/key/after. Dashed cyan is the local fan tangent expressed in the vehicle u/v frame.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.035, 1, 0.93])
    save_figure(fig, assets / "C04B_PV004_ADJACENT_FRAME_RAW_CONTINUITY.png")


def render_length_and_road_controls(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    cases = [
        ("GM_RM017:PV002", 164, 342),
        ("GM_RM017:PV004", 164, 342),
        ("GM_RM017:PV002", 173, 361),
    ]
    controls = [
        ("TRUE_NEIGHBORHOOD", 0.0),
        ("U_MINUS_EXTENSION", 0.90),
        ("U_PLUS_EXTENSION", 0.90),
        ("FAR_BACKGROUND", 1.50),
        ("EMPTY_ROAD_TANGENTIAL", 1.00),
    ]
    records = []
    patches = []
    for vehicle, optical_frame, sar_frame in cases:
        per_frame = longest_edge_geometry(choose_gt(gt_rows, scene, vehicle, sar_frame))
        stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
        image = load_gray(data, scene, sar_frame)
        for control_type, scale in controls:
            if control_type == "TRUE_NEIGHBORHOOD":
                distance = 0.0
                center = (stable.cx, stable.cy)
            elif control_type in {"U_MINUS_EXTENSION", "U_PLUS_EXTENSION"}:
                distance = stable.long_px * scale
                center = control_center(stable, control_type, distance)
            elif control_type == "FAR_BACKGROUND":
                distance = stable.short_px * scale
                center = control_center(stable, control_type, distance)
            else:
                distance = stable.long_px * scale
                direction = "TANGENTIAL_PLUS" if vehicle.endswith("PV002") else "TANGENTIAL_MINUS"
                center = control_center(stable, direction, distance)
            geometry = Geometry(
                center[0], center[1], stable.long_px, stable.short_px,
                stable.axis_deg, "CONTROL_THREAD_STABLE",
            )
            patch = sample_signed_patch(image, geometry)
            records.append(
                (vehicle, optical_frame, sar_frame, per_frame, geometry, control_type, distance, patch)
            )
            patches.append(patch)
    raw_limits = common_raw_limits(patches)
    contrast_limit = common_contrast_limit(patches, 10.0)
    fig, axes = plt.subplots(len(cases) * 2, len(controls), figsize=(17, 14), facecolor="#0E151D")
    index = 0
    for case_index, (vehicle, optical_frame, sar_frame) in enumerate(cases):
        for col, (control_type, scale) in enumerate(controls):
            _, _, _, per_frame, geometry, _, distance, patch = records[index]
            index += 1
            show_patch(
                axes[case_index * 2, col], patch, geometry,
                f"{suffix(vehicle)} {sar_frame} | {control_type}", raw_limits=raw_limits,
                color=COLORS[suffix(vehicle)],
            )
            show_patch(
                axes[case_index * 2 + 1, col], patch, geometry,
                f"σ10 | {control_type}", sigma=10.0, contrast_limit=contrast_limit,
                color=COLORS[suffix(vehicle)],
            )
            if control_type.startswith("U_"):
                note = (
                    "vehicle-axis exterior footprint; the bright strip stays near the adjacent edge "
                    "or outside rather than traversing the exterior control box"
                )
                weakened = "an infinitely extended vehicle-axis strip; approximate length termination is supported"
                control_status = "CONTROL_SUPPORTS_APPROX_LENGTH_TERMINATION"
            elif control_type == "EMPTY_ROAD_TANGENTIAL":
                note = (
                    "same-radius parked-corridor proxy one long axis away; background returns remain "
                    "without the same +v boundary placement"
                )
                weakened = "pure vehicle-body ownership; road/curb mixing remains competitive"
                control_status = "BACKGROUND_COMPETITIVE_NOT_SIDE_LOCKED"
            elif control_type == "FAR_BACKGROUND":
                note = "adjacent far-side proxy lacks an in-box replica of the target near-boundary strip"
                weakened = "near/far asymmetry as a generic fixed-offset background property"
                control_status = "BACKGROUND_PROXY_NOT_SIDE_LOCKED"
            else:
                note = "true neighborhood reference"
                weakened = "none by true row alone"
                control_status = "VEHICLE_GROUND_MIXED_PLAUSIBLE"
            add_manifest_row(
                manifest_rows,
                case_id="C05",
                scene=scene,
                vehicle=vehicle,
                optical_frame=optical_frame,
                sar_frame=sar_frame,
                coordinate_scheme="CONTROL_THREAD_STABLE",
                geometry=geometry,
                per_frame=per_frame,
                patch=patch,
                control_type=control_type,
                control_displacement_px=distance,
                observation_raw=note,
                observation_multiscale="raw and sigma10 shown with shared scales",
                interpretation_status=control_status,
                eliminated=weakened,
            )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C05 | Vehicle-length exterior, far-background, and empty-road controls",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "These controls test termination and road continuity; they are not candidate locations or negative training samples.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.95])
    save_figure(fig, assets / "C05_ROAD_AND_VEHICLE_LENGTH_EXTENSION_CONTROLS.png")


def render_holdout_stable_recheck(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    records = []
    patches = []
    for optical_frame, sar_frame in HOLDOUT_WINDOWS:
        for vehicle in GM17_VEHICLES:
            per_frame = longest_edge_geometry(choose_gt(gt_rows, scene, vehicle, sar_frame))
            stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
            image = load_gray(data, scene, sar_frame)
            true_patch = sample_signed_patch(image, stable)
            far_center = control_center(stable, "FAR_RADIAL", stable.short_px)
            far_geometry = Geometry(
                far_center[0], far_center[1], stable.long_px, stable.short_px,
                stable.axis_deg, "CONTROL_THREAD_STABLE",
            )
            far_patch = sample_signed_patch(image, far_geometry)
            records.append((optical_frame, sar_frame, vehicle, per_frame, stable, true_patch, far_geometry, far_patch))
            patches.extend([true_patch, far_patch])
    raw_limits = common_raw_limits(patches)
    fig, axes = plt.subplots(4, 3, figsize=(13, 12), facecolor="#0E151D")
    for block, (optical_frame, sar_frame) in enumerate(HOLDOUT_WINDOWS):
        current = [item for item in records if item[0] == optical_frame and item[1] == sar_frame]
        for col, (_, _, vehicle, per_frame, stable, true_patch, far_geometry, far_patch) in enumerate(current):
            show_patch(
                axes[block * 2, col], true_patch, stable,
                f"{suffix(vehicle)} | SAR {sar_frame} | stable true", raw_limits=raw_limits,
            )
            show_patch(
                axes[block * 2 + 1, col], far_patch, far_geometry,
                f"{suffix(vehicle)} | SAR {sar_frame} | far 1W", raw_limits=raw_limits,
            )
            add_manifest_row(
                manifest_rows,
                case_id="C06",
                scene=scene,
                vehicle=vehicle,
                optical_frame=optical_frame,
                sar_frame=sar_frame,
                coordinate_scheme="THREAD_STABLE_LOO",
                geometry=stable,
                per_frame=per_frame,
                patch=true_patch,
                observation_raw="held-out adjacent frame retains a near-side vehicle-scale band in raw gray",
                observation_multiscale="not required for ownership; raw gray is primary in this recheck",
                interpretation_status="VEHICLE_GROUND_MIXED_PLAUSIBLE",
                eliminated="dependence on the five originally selected PV002 sequence frames",
            )
            add_manifest_row(
                manifest_rows,
                case_id="C06",
                scene=scene,
                vehicle=vehicle,
                optical_frame=optical_frame,
                sar_frame=sar_frame,
                coordinate_scheme="CONTROL_THREAD_STABLE",
                geometry=far_geometry,
                per_frame=per_frame,
                patch=far_patch,
                control_type="FAR_RADIAL",
                control_displacement_px=stable.short_px,
                observation_raw="matched far-side control for held-out frame",
                observation_multiscale="raw gray comparison only",
                interpretation_status="CONTROL_NO_SIDE_LOCK_REPLICATION",
                eliminated="a generic band equally present one short-axis width on the far side when absent",
            )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C06 | SAR 370/371 thread-stable raw-gray recheck",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "B06 is one adjacent two-frame multicar window, not six independent replications.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.95])
    save_figure(fig, assets / "C06_HOLDOUT_THREAD_STABLE_RAW_RECHECK.png")


def render_gm11_stress_recheck(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
) -> None:
    cases = [
        ("GM_RM011", "GM_RM011:PV001", 8, 16, "near-origin / invalid-boundary stress"),
        ("GM_RM011", "GM_RM011:PV008", 151, 315, "near-origin paired-car stress"),
        ("GM_RM011", "GM_RM011:PV007", 151, 315, "near-origin paired-car stress"),
    ]
    records = []
    patches = []
    for scene, vehicle, optical_frame, sar_frame, label in cases:
        stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
        patch = sample_signed_patch(load_gray(data, scene, sar_frame), stable)
        records.append((scene, vehicle, optical_frame, sar_frame, label, stable, patch))
        patches.append(patch)
    raw_limits = common_raw_limits(patches)
    contrast_limits = {sigma: common_contrast_limit(patches, sigma) for sigma in SIGMAS}
    fig, axes = plt.subplots(4, 3, figsize=(13, 12), facecolor="#0E151D")
    for col, (scene, vehicle, optical_frame, sar_frame, label, stable, patch) in enumerate(records):
        show_patch(
            axes[0, col], patch, stable,
            f"{suffix(vehicle)} | SAR {sar_frame} | stable raw", raw_limits=raw_limits,
        )
        for row_index, sigma in enumerate(SIGMAS, start=1):
            show_patch(
                axes[row_index, col], patch, stable,
                f"{suffix(vehicle)} | σ={sigma:g}px | {label}",
                sigma=sigma, contrast_limit=contrast_limits[sigma],
            )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C07 | GM11 near-origin and invalid-boundary display stress recheck",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "GM11 demonstrates that fan arcs, radial lines, and invalid boundaries can imitate vehicle-scale bands under every display scale.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.95])
    save_figure(fig, assets / "C07_GM11_BOUNDARY_AND_BACKGROUND_STRESS_RECHECK.png")


def render_local_ring_controls(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    vehicle = "GM_RM017:PV002"
    optical_frame, sar_frame = 164, 342
    per_frame = longest_edge_geometry(choose_gt(gt_rows, scene, vehicle, sar_frame))
    stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
    image = load_gray(data, scene, sar_frame)
    u, v, _ = signed_axes(stable)
    radius = stable.short_px * 1.5
    records = []
    patches = []
    for angle_deg in range(0, 360, 45):
        angle = math.radians(angle_deg)
        offset = radius * (math.cos(angle) * u + math.sin(angle) * v)
        center = np.array([stable.cx, stable.cy]) + offset
        geometry = Geometry(
            float(center[0]),
            float(center[1]),
            stable.long_px,
            stable.short_px,
            stable.axis_deg,
            "CONTROL_THREAD_STABLE",
        )
        patch = sample_signed_patch(image, geometry)
        records.append((angle_deg, geometry, patch))
        patches.append(patch)
    raw_limits = common_raw_limits(patches)
    contrast_limit = common_contrast_limit(patches, 10.0)
    fig, axes = plt.subplots(2, 8, figsize=(23, 6.5), facecolor="#0E151D")
    for col, (angle_deg, geometry, patch) in enumerate(records):
        direction = (
            "+u" if angle_deg == 0 else "+v near" if angle_deg == 90
            else "-u" if angle_deg == 180 else "-v far" if angle_deg == 270
            else f"{angle_deg}°"
        )
        show_patch(
            axes[0, col],
            patch,
            geometry,
            f"ring {direction} | 1.5W",
            raw_limits=raw_limits,
            xlabel=False,
            color=COLORS["PV002"],
        )
        show_patch(
            axes[1, col],
            patch,
            geometry,
            f"σ10 | ring {direction}",
            sigma=10.0,
            contrast_limit=contrast_limit,
            color=COLORS["PV002"],
        )
        add_manifest_row(
            manifest_rows,
            case_id="C03B",
            scene=scene,
            vehicle=vehicle,
            optical_frame=optical_frame,
            sar_frame=sar_frame,
            coordinate_scheme="CONTROL_THREAD_STABLE",
            geometry=geometry,
            per_frame=per_frame,
            patch=patch,
            control_type=f"LOCAL_RING_{angle_deg:03d}DEG",
            control_displacement_px=radius,
            observation_raw=(
                "local 1.5W ring position; background lines occur at several angles, "
                "but the target-like +v boundary placement is not reproduced uniformly"
            ),
            observation_multiscale="raw and sigma10 shown under common ring scales",
            interpretation_status="BACKGROUND_COMPETITIVE_NOT_UNIFORMLY_SIDE_LOCKED",
            eliminated="a spatially uniform local-ring prevalence of the same side-locked band",
        )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C03B | PV002 SAR342 local 1.5W ring controls",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "Angles are defined in the target u/v frame. Ring patches are controls, not candidate or negative-sample locations.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.035, 1, 0.92])
    save_figure(fig, assets / "C03B_PV002_LOCAL_RING_CONTROLS.png")


def add_axis_center_mismatch_rows(
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    sar_frame, optical_frame = 342, 164
    pairs = [
        ("GM_RM017:PV004", "GM_RM017:PV002"),
        ("GM_RM017:PV002", "GM_RM017:PV004"),
    ]
    image = load_gray(data, scene, sar_frame)
    for target_vehicle, donor_vehicle in pairs:
        per_frame = longest_edge_geometry(
            choose_gt(gt_rows, scene, target_vehicle, sar_frame)
        )
        target = stable_geometry_loo(gt_rows, scene, target_vehicle, sar_frame)
        donor = stable_geometry_loo(gt_rows, scene, donor_vehicle, sar_frame)
        mismatch = Geometry(
            target.cx,
            target.cy,
            target.long_px,
            target.short_px,
            donor.axis_deg,
            "AXIS_CENTER_MISMATCH_LOW_POWER",
        )
        patch = sample_signed_patch(image, mismatch)
        difference = axial_difference_deg(target.axis_deg, donor.axis_deg)
        add_manifest_row(
            manifest_rows,
            case_id="C03M",
            scene=scene,
            vehicle=target_vehicle,
            optical_frame=optical_frame,
            sar_frame=sar_frame,
            coordinate_scheme="CONTROL_THREAD_STABLE",
            geometry=mismatch,
            per_frame=per_frame,
            patch=patch,
            control_type=f"AXIS_FROM_{suffix(donor_vehicle)}_AT_{suffix(target_vehicle)}_CENTER",
            observation_raw=(
                f"donor and target stable axes differ by only {difference:.3f} degrees; "
                "the control is intentionally recorded as low-power"
            ),
            observation_multiscale="not separately rendered because the road-aligned axes are nearly identical",
            interpretation_status="NOT_IDENTIFIABLE",
            eliminated="none; shared parked-road orientation makes this mismatch non-discriminating",
            not_eliminated="vehicle axis; road axis; vehicle-ground mixture; fan imaging",
        )


def render_crossframe_background_proxy(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, object]],
) -> None:
    scene = "GM_RM017"
    vehicle = "GM_RM017:PV002"
    records = []
    patches = []
    for optical_frame, sar_frame, phase in PV002_SEQUENCE:
        per_frame = longest_edge_geometry(choose_gt(gt_rows, scene, vehicle, sar_frame))
        stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
        image = load_gray(data, scene, sar_frame)
        true_patch = sample_signed_patch(image, stable)
        distance = stable.short_px * 1.5
        center = control_center(stable, "FAR_BACKGROUND", distance)
        background = Geometry(
            center[0], center[1], stable.long_px, stable.short_px,
            stable.axis_deg, "FIXED_VEHICLE_RELATIVE_BACKGROUND_PROXY",
        )
        background_patch = sample_signed_patch(image, background)
        records.append(
            (optical_frame, sar_frame, phase, per_frame, stable, true_patch, background, background_patch, distance)
        )
        patches.extend([true_patch, background_patch])
    raw_limits = common_raw_limits(patches)
    fig, axes = plt.subplots(2, 5, figsize=(18, 6.8), facecolor="#0E151D")
    for col, (optical_frame, sar_frame, phase, per_frame, stable, true_patch, background, background_patch, distance) in enumerate(records):
        show_patch(
            axes[0, col], true_patch, stable,
            f"PV002 | SAR {sar_frame} | true", raw_limits=raw_limits,
            color=COLORS["PV002"],
        )
        show_patch(
            axes[1, col], background_patch, background,
            f"far background 1.5W | {phase}", raw_limits=raw_limits,
            color="#94A3B8",
        )
        add_manifest_row(
            manifest_rows,
            case_id="C05B",
            scene=scene,
            vehicle=vehicle,
            optical_frame=optical_frame,
            sar_frame=sar_frame,
            coordinate_scheme="CONTROL_THREAD_STABLE",
            geometry=background,
            per_frame=per_frame,
            patch=background_patch,
            control_type="CROSSFRAME_FAR_BACKGROUND_PROXY_1P5W",
            control_displacement_px=distance,
            observation_raw=(
                "fixed vehicle-relative far-side background proxy changes across frames and "
                "does not retain the target's +v boundary placement"
            ),
            observation_multiscale="raw gray used; exact world-background registration is not claimed",
            interpretation_status="BACKGROUND_PROXY_NOT_SIDE_LOCKED",
            eliminated="a generic fixed-offset background strip as the full explanation",
            not_eliminated="road/curb continuity and vehicle-ground mixing without exact world registration",
        )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C05B | PV002 true neighborhoods versus cross-frame far-background proxy",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "The proxy keeps a 1.5W vehicle-relative offset. It is not an exact world-registered road point.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.92])
    save_figure(fig, assets / "C05B_PV002_CROSSFRAME_BACKGROUND_PROXY.png")


def render_optical_pose_sar_state(
    assets: Path,
    data: Path,
    gt_rows: list[dict[str, str]],
    states: dict[tuple[str, str, int], dict[str, str]],
) -> None:
    scene = "GM_RM017"
    vehicle = "GM_RM017:PV002"
    frames = [
        (153, 319, "left clipped"),
        (164, 342, "complete side"),
        (167, 348, "complete side"),
        (173, 361, "complete side"),
        (178, 370, "right clipping begins"),
        (181, 378, "right clipped"),
    ]
    records = []
    patches = []
    for optical_frame, sar_frame, pose in frames:
        stable = stable_geometry_loo(gt_rows, scene, vehicle, sar_frame)
        patch = sample_signed_patch(load_gray(data, scene, sar_frame), stable)
        records.append((optical_frame, sar_frame, pose, stable, patch))
        patches.append(patch)
    raw_limits = common_raw_limits(patches)
    fig, axes = plt.subplots(2, len(frames), figsize=(20, 7), facecolor="#0E151D")
    for col, (optical_frame, sar_frame, pose, stable, patch) in enumerate(records):
        show_optical_crop(
            axes[0, col],
            data,
            states,
            scene,
            vehicle,
            optical_frame,
            f"Optical {optical_frame} | {pose}",
        )
        show_patch(
            axes[1, col],
            patch,
            stable,
            f"PV002 stable raw | SAR {sar_frame}",
            raw_limits=raw_limits,
            color=COLORS["PV002"],
        )
    fig.suptitle(
        "OTY2-RSA2-G2-R1 C08 | Optical pose and SAR near-side state",
        color="white",
        fontsize=17,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.005,
        "The sedan front is visually optical-left, but that direction is not transferred to SAR u. Broad side pose persists while SAR endpoints and fragments reorganize.",
        color="#F8C15C",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.035, 1, 0.92])
    save_figure(fig, assets / "C08_PV002_OPTICAL_POSE_AND_SAR_STATE.png")


def main() -> None:
    args = parse_args()
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    gt_rows = read_csv(args.repo / "manifests/oty2/oty2_s0_sar_gt_quality_audit.csv")
    states = optical_state_map(
        read_csv(args.repo / "manifests/oty2/oty2_p1e_canonical_vehicle_frame_states.csv")
    )
    manifest_rows: list[dict[str, object]] = []
    render_signed_context(args.assets_dir, args.data, gt_rows, states, manifest_rows)
    render_pv002_alignment_display_audit(
        args.assets_dir, args.data, gt_rows, manifest_rows
    )
    render_pv002_adjacent_continuity(
        args.assets_dir, args.data, gt_rows, manifest_rows
    )
    render_matched_controls(args.assets_dir, args.data, gt_rows, manifest_rows)
    render_local_ring_controls(args.assets_dir, args.data, gt_rows, manifest_rows)
    add_axis_center_mismatch_rows(args.data, gt_rows, manifest_rows)
    render_pv004_axis_disambiguation(args.assets_dir, args.data, gt_rows)
    render_pv004_adjacent_continuity(
        args.assets_dir, args.data, gt_rows, manifest_rows
    )
    render_length_and_road_controls(args.assets_dir, args.data, gt_rows, manifest_rows)
    render_crossframe_background_proxy(
        args.assets_dir, args.data, gt_rows, manifest_rows
    )
    render_holdout_stable_recheck(args.assets_dir, args.data, gt_rows, manifest_rows)
    render_gm11_stress_recheck(args.assets_dir, args.data, gt_rows)
    render_optical_pose_sar_state(
        args.assets_dir, args.data, gt_rows, states
    )
    write_csv(args.manifest, manifest_rows)
    print(f"assets={args.assets_dir}")
    print(f"manifest={args.manifest}")
    print(f"rows={len(manifest_rows)}")


if __name__ == "__main__":
    main()
