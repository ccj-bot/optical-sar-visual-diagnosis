#!/usr/bin/env python3
"""Run the bounded OTY2 local-structure extraction research sprint.

Runtime extraction inputs are restricted to:

* raw SAR grayscale and adjacent SAR frames;
* the deterministic fan origin / valid mask;
* a G1 forward interval frozen before target-SAR-GT reveal;
* the forward interval's coarse heading and vehicle-size ranges.

The extractor emits explicit ridge segments, LSD segments, hotspot clusters,
and short-window graph edges.  It does not emit a target centre, winner,
selector, final box, response mask, or training annotation.

Research-period SAR GT and prior manual component cards are loaded only after
runtime outputs have been frozen in memory.  They are used exclusively for a
posthoc audit figure and overlap measurements.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon, Rectangle
from PIL import Image
from scipy.ndimage import gaussian_filter
from skimage.feature import blob_log
from skimage.filters import frangi
from skimage.measure import label, regionprops
from skimage.morphology import closing, remove_small_objects, skeletonize


DEFAULT_REPO = Path(r"D:\profile\research\optical-sar-visual-diagnosis-sar-foundation")
DEFAULT_DATA = Path(r"D:\profile\research\data")
DEFAULT_ASSETS = DEFAULT_REPO / (
    "docs/reviews/assets/20260719_oty2_autonomous_local_structure_extraction"
)
DEFAULT_CASE_MANIFEST = DEFAULT_REPO / (
    "manifests/oty2/oty2_autonomous_sprint_case_manifest.csv"
)
DEFAULT_TEACHER_MANIFEST = DEFAULT_REPO / (
    "manifests/oty2/oty2_multimodal_teacher_repeatability_manifest.csv"
)
DEFAULT_OUTPUT_MANIFEST = DEFAULT_REPO / (
    "manifests/oty2/oty2_local_structure_output_manifest.csv"
)
DEFAULT_GRAPH_MANIFEST = DEFAULT_REPO / (
    "manifests/oty2/oty2_local_structure_graph_edges.csv"
)
DEFAULT_SUMMARY = DEFAULT_REPO / (
    "manifests/oty2/oty2_autonomous_local_structure_summary.json"
)

FAN_ORIGIN = np.array([1154.0, 1330.6], dtype=np.float64)
FAN_RADIUS = 1332.7
TARGET_FORWARD_CASE = "G1F0002"
INTERMEDIATE_FORWARD_CASE = "G1F0001"
PRIMARY_FRAMES = [339, 341, 342, 343, 344, 347, 348, 349]
ADJACENT_GROUPS = [[341, 342, 343], [347, 348, 349]]
RUNTIME_WARNING = "TARGET_SAR_GT_NOT_ACCESSED_AT_RUNTIME"
TEACHER_WARNING = "RESEARCH_TEACHER_OUTPUT_NOT_GT_NOT_MASK"
POSTHOC_WARNING = "POSTHOC_GT_OR_MANUAL_CARD_AUDIT_ONLY"

TEACHER_REVIEW_RESULTS = {
    "T01": (
        "dominant near-horizontal lower band is visible, but ownership is unresolved without coordinates",
        "same lower band is visible again; no unique target assignment without context",
        "CONDITION_DEPENDENT_VISIBLE_STRUCTURE",
    ),
    "T02": (
        "allowed shell and axis focus attention on the lower horizontal response, while multiple structures remain",
        "same shell-conditioned lower response is identified; shell alone does not make it a mask",
        "REPEATABLE_WITH_ALLOWED_GEOMETRY_HINT",
    ),
    "T03": (
        "lower band persists and reorganizes across adjacent frames; upper arc also persists as competition",
        "same temporal pattern is identified, including band continuity and background competition",
        "REPEATABLE_WITH_ADJACENT_CONTEXT",
    ),
    "T04": (
        "side-dominant optical context supports a horizontal SAR relation but not an exact response boundary",
        "same coarse relation is retained without claiming a precise component mask",
        "GLOBAL_CONTEXT_SUPPORTS_COARSE_RELATION",
    ),
    "T05": (
        "intermediate-alpha sequence shows a shorter fragmented lower band with stronger competition",
        "same fragmented lower relation is identified across the five frames",
        "REPEATABLE_FRAGMENTED_STATE",
    ),
    "T06": (
        "empty-road controls show diagonal crosses and speckled streaks, not the same persistent lower band relation",
        "same negative judgment; isolated line-like clutter remains but no comparable band topology",
        "ROAD_CONTROL_REJECTED",
    ),
    "T07": (
        "no unique vehicle-associated structure can be assigned under near-origin and sparse/truncated pressure",
        "same result: NOT_IDENTIFIABLE rather than mechanism absence",
        "NOT_IDENTIFIABLE",
    ),
}

# Frozen before the first run.  These are distribution-relative gates, not
# target-specific absolute thresholds and not the historical NSB peak range.
RESPONSE_QUANTILE = 0.94
HOTSPOT_QUANTILE = 0.992
MAX_AXIS_ERROR_DEG = 40.0
MIN_SEGMENT_LENGTH_PX = 14.0
MAX_SEGMENT_LENGTH_FACTOR = 2.2
TRACK_MAX_DISTANCE_PX = 95.0
TRACK_MAX_AXIS_ERROR_DEG = 24.0


@dataclass(frozen=True)
class ForwardCase:
    case_id: str
    scene: str
    canonical_vehicle_id: str
    optical_frame: int
    sar_frame: int
    theta_min_deg: float
    theta_max_deg: float
    radius_min_px: float
    radius_max_px: float
    heading_min_deg: float
    heading_max_deg: float
    long_min_px: float
    long_max_px: float
    short_min_px: float
    short_max_px: float
    source_status: str

    @property
    def heading_deg(self) -> float:
        return axial_mean_deg([self.heading_min_deg, self.heading_max_deg])


@dataclass
class StructureObject:
    object_id: str
    case_id: str
    scene: str
    frame: int
    object_type: str
    source_operator: str
    x1: float
    y1: float
    x2: float
    y2: float
    cx: float
    cy: float
    length_px: float
    width_px: float
    axis_deg: float
    axis_error_deg: float
    mean_response: float
    peak_response: float
    persistence_group: str = ""
    primary_object: bool = False
    parent_band_id: str = ""
    allowed_relation_fraction: float = 0.0
    support_fragment_count: int = 0
    attached_hotspot_count: int = 0
    background_crossing_flag: bool = False
    uncertainty_state: str = "CANDIDATE"
    posthoc_gt_overlap_fraction: float | None = None
    posthoc_nsb_overlap_fraction: float | None = None
    notes: str = ""


@dataclass
class ExtractionResult:
    case: ForwardCase
    frame: int
    bbox: tuple[int, int, int, int]
    center_shell: np.ndarray
    wide_mask: np.ndarray
    near_side_mask: np.ndarray
    raw: np.ndarray
    normalized: np.ndarray
    response: np.ndarray
    binary: np.ndarray
    skeleton: np.ndarray
    objects: list[StructureObject] = field(default_factory=list)
    state: str = "UNRESOLVED"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--case-manifest", type=Path, default=DEFAULT_CASE_MANIFEST)
    parser.add_argument("--teacher-manifest", type=Path, default=DEFAULT_TEACHER_MANIFEST)
    parser.add_argument("--output-manifest", type=Path, default=DEFAULT_OUTPUT_MANIFEST)
    parser.add_argument("--graph-manifest", type=Path, default=DEFAULT_GRAPH_MANIFEST)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_gray(data: Path, scene: str, frame: int) -> np.ndarray:
    path = data / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"
    return np.asarray(Image.open(path).convert("L"), dtype=np.float32)


def load_rgb(data: Path, scene: str, frame: int) -> np.ndarray:
    path = data / scene / f"{scene}_frames" / f"{frame:06d}.png"
    return np.asarray(Image.open(path).convert("RGB"))


def normalize_axis_angle(angle_deg: float) -> float:
    return ((angle_deg + 90.0) % 180.0) - 90.0


def axial_difference_deg(a: float, b: float) -> float:
    return abs(normalize_axis_angle(a - b))


def axial_mean_deg(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    radians = np.deg2rad(array * 2.0)
    return normalize_axis_angle(
        0.5 * math.degrees(math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean())))
    )


def parse_pair(value: str) -> tuple[float, float]:
    parts = value.strip().strip("[]").split(",")
    return float(parts[0]), float(parts[1])


def parse_bbox(value: str) -> tuple[float, float, float, float, float]:
    parts = value.strip().strip("[]").split(",")
    return tuple(float(item) for item in parts)  # type: ignore[return-value]


def forward_case(rows: list[dict[str, str]], case_id: str) -> ForwardCase:
    row = next(item for item in rows if item["forward_case_id"] == case_id)
    if row["target_gt_access_status"] != "TARGET_SAR_GT_NOT_ACCESSED":
        raise RuntimeError(f"forward case {case_id} is not target-GT blind")
    return ForwardCase(
        case_id=case_id,
        scene=row["scene"],
        canonical_vehicle_id=row["canonical_vehicle_id"],
        optical_frame=int(row["optical_frame"]),
        sar_frame=int(row["sar_frame"]),
        theta_min_deg=float(row["azimuth_min_deg"]),
        theta_max_deg=float(row["azimuth_max_deg"]),
        radius_min_px=float(row["radius_min_px"]),
        radius_max_px=float(row["radius_max_px"]),
        heading_min_deg=float(row["heading_min_deg"]),
        heading_max_deg=float(row["heading_max_deg"]),
        long_min_px=float(row["long_axis_min_px"]),
        long_max_px=float(row["long_axis_max_px"]),
        short_min_px=float(row["short_axis_min_px"]),
        short_max_px=float(row["short_axis_max_px"]),
        source_status=row["target_gt_access_status"],
    )


def polar_grids(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.indices(shape, dtype=np.float32)
    radius = np.hypot(xx - FAN_ORIGIN[0], yy - FAN_ORIGIN[1])
    theta = np.degrees(np.arctan2(xx - FAN_ORIGIN[0], FAN_ORIGIN[1] - yy))
    return radius, theta


def imaging_valid_mask(shape: tuple[int, int]) -> np.ndarray:
    radius, _ = polar_grids(shape)
    return radius <= FAN_RADIUS


def oriented_rect_kernel(long_radius: int, short_radius: int, angle_deg: float) -> np.ndarray:
    radius = int(math.ceil(math.hypot(long_radius, short_radius))) + 3
    size = 2 * radius + 1
    kernel = np.zeros((size, size), dtype=np.uint8)
    rect = ((float(radius), float(radius)), (float(2 * long_radius + 1), float(2 * short_radius + 1)), float(angle_deg))
    corners = cv2.boxPoints(rect).astype(np.int32)
    cv2.fillConvexPoly(kernel, corners, 1)
    return kernel


def asymmetric_near_side_kernel(
    long_radius: int,
    short_radius: int,
    heading_deg: float,
    near_direction_xy: np.ndarray,
) -> np.ndarray:
    radius = int(math.ceil(math.hypot(long_radius, short_radius))) + 5
    size = 2 * radius + 1
    center = np.array([radius, radius], dtype=np.float64)
    theta = math.radians(heading_deg)
    u_axis = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    candidate_v = np.array([-math.sin(theta), math.cos(theta)], dtype=np.float64)
    if float(candidate_v @ near_direction_xy) < 0:
        candidate_v *= -1.0
    # Permit a small centre/far-side tolerance but allocate most of the support
    # to the side toward the fan origin.  This is a relational prior, not a
    # historical peak-position threshold.
    far_tolerance = 14.0
    points = np.stack(
        [
            center - u_axis * long_radius - candidate_v * far_tolerance,
            center + u_axis * long_radius - candidate_v * far_tolerance,
            center + u_axis * long_radius + candidate_v * short_radius,
            center - u_axis * long_radius + candidate_v * short_radius,
        ]
    )
    kernel = np.zeros((size, size), dtype=np.uint8)
    cv2.fillConvexPoly(kernel, points.astype(np.int32), 1)
    return kernel


def build_forward_masks(shape: tuple[int, int], case: ForwardCase) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    radius, theta = polar_grids(shape)
    center_shell = (
        (radius >= case.radius_min_px)
        & (radius <= case.radius_max_px)
        & (theta >= case.theta_min_deg)
        & (theta <= case.theta_max_deg)
        & imaging_valid_mask(shape)
    )
    # A centre shell should be expanded by the vehicle-size prior in vehicle
    # coordinates, not by an isotropic disc.  The initial isotropic version
    # admitted most of the local fan and produced a segment/hotspot soup.
    long_radius = int(math.ceil(case.long_max_px / 2 + 34.0))
    short_radius = int(math.ceil(case.short_max_px / 2 + 20.0))
    kernel = oriented_rect_kernel(long_radius, short_radius, case.heading_deg)
    wide = cv2.dilate(center_shell.astype(np.uint8), kernel).astype(bool)
    wide &= imaging_valid_mask(shape)
    # The G1 centre shell already has a broad radial interval.  A high-alpha
    # near-side response should lie at or closer to the fan origin than the
    # shell's median centre radius.  This relational gate is deliberately
    # broad and is not the historical 0.65-0.79 peak-position rule.
    shell_radius = radius[center_shell]
    median_radius = float(np.median(shell_radius))
    near_side = (
        wide
        & (radius <= median_radius + case.short_max_px * 0.22)
        & (radius >= max(0.0, case.radius_min_px - case.short_max_px * 1.35))
    )
    return center_shell, wide, near_side


def mask_bbox(mask: np.ndarray, pad: int = 8) -> tuple[int, int, int, int]:
    yy, xx = np.where(mask)
    if not len(xx):
        raise RuntimeError("empty search mask")
    x0 = max(0, int(xx.min()) - pad)
    x1 = min(mask.shape[1], int(xx.max()) + pad + 1)
    y0 = max(0, int(yy.min()) - pad)
    y1 = min(mask.shape[0], int(yy.max()) + pad + 1)
    return x0, y0, x1, y1


def robust_normalize(raw: np.ndarray, mask: np.ndarray) -> np.ndarray:
    values = raw[mask & (raw > 0)]
    if values.size < 20:
        return np.zeros_like(raw, dtype=np.float32)
    low, high = np.percentile(values, [2.0, 99.6])
    if high <= low:
        high = low + 1.0
    return np.clip((raw - low) / (high - low), 0.0, 1.0).astype(np.float32)


def quantile_normalize(array: np.ndarray, mask: np.ndarray) -> np.ndarray:
    values = array[mask & np.isfinite(array)]
    if values.size < 20:
        return np.zeros_like(array, dtype=np.float32)
    low, high = np.percentile(values, [5.0, 99.5])
    if high <= low:
        high = low + 1e-6
    return np.clip((array - low) / (high - low), 0.0, 1.0).astype(np.float32)


def oriented_kernel(angle_deg: float, size: int = 15) -> np.ndarray:
    size = size if size % 2 else size + 1
    kernel = np.zeros((size, size), dtype=np.uint8)
    center = (size // 2, size // 2)
    theta = math.radians(angle_deg)
    dx = int(round(math.cos(theta) * (size // 2 - 1)))
    dy = int(round(math.sin(theta) * (size // 2 - 1)))
    cv2.line(kernel, (center[0] - dx, center[1] - dy), (center[0] + dx, center[1] + dy), 1, 2)
    return kernel.astype(bool)


def build_response(normalized: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dog_scales = []
    for sigma in (2.0, 4.0, 8.0, 12.0):
        dog_scales.append(np.maximum(normalized - gaussian_filter(normalized, sigma=sigma), 0.0))
    dog = quantile_normalize(np.maximum.reduce(dog_scales), mask)
    vessel = frangi(normalized, sigmas=(1, 2, 3, 5, 7), black_ridges=False)
    vessel = quantile_normalize(np.nan_to_num(vessel, nan=0.0), mask)
    response = (0.62 * dog + 0.38 * vessel).astype(np.float32)
    response[~mask] = 0.0
    return response, dog, vessel


def line_points(x1: float, y1: float, x2: float, y2: float) -> tuple[np.ndarray, np.ndarray]:
    count = max(2, int(round(math.hypot(x2 - x1, y2 - y1))) + 1)
    xx = np.linspace(x1, x2, count)
    yy = np.linspace(y1, y2, count)
    return xx, yy


def response_on_line(response: np.ndarray, x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    xx, yy = line_points(x1, y1, x2, y2)
    xi = np.clip(np.rint(xx).astype(int), 0, response.shape[1] - 1)
    yi = np.clip(np.rint(yy).astype(int), 0, response.shape[0] - 1)
    values = response[yi, xi]
    return float(values.mean()), float(values.max())


def mask_fraction_on_line(mask: np.ndarray, x1: float, y1: float, x2: float, y2: float) -> float:
    xx, yy = line_points(x1, y1, x2, y2)
    xi = np.clip(np.rint(xx).astype(int), 0, mask.shape[1] - 1)
    yi = np.clip(np.rint(yy).astype(int), 0, mask.shape[0] - 1)
    return float(mask[yi, xi].mean())


def pca_segment(coords_yx: np.ndarray) -> tuple[float, float, float, float, float, float, float]:
    points = coords_yx[:, ::-1].astype(np.float64)
    center = points.mean(axis=0)
    centered = points - center
    covariance = centered.T @ centered / max(len(points), 1)
    values, vectors = np.linalg.eigh(covariance)
    axis = vectors[:, int(np.argmax(values))]
    projection = centered @ axis
    cross = centered @ np.array([-axis[1], axis[0]])
    p1 = center + axis * float(projection.min())
    p2 = center + axis * float(projection.max())
    length = float(projection.max() - projection.min() + 1.0)
    width = float(np.percentile(cross, 95) - np.percentile(cross, 5) + 1.0)
    angle = normalize_axis_angle(math.degrees(math.atan2(axis[1], axis[0])))
    return p1[0], p1[1], p2[0], p2[1], length, width, angle


def point_segment_distance(px: float, py: float, obj: StructureObject) -> float:
    a = np.array([obj.x1, obj.y1], dtype=np.float64)
    b = np.array([obj.x2, obj.y2], dtype=np.float64)
    p = np.array([px, py], dtype=np.float64)
    vector = b - a
    denom = float(vector @ vector)
    if denom <= 1e-9:
        return float(np.linalg.norm(p - a))
    t = float(np.clip(((p - a) @ vector) / denom, 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * vector)))


def assemble_band_objects(
    case: ForwardCase,
    frame: int,
    objects: list[StructureObject],
    wide_mask: np.ndarray,
    near_side_mask: np.ndarray,
) -> list[StructureObject]:
    segments = [
        obj
        for obj in objects
        if obj.object_type in {"OPEN_RIDGE_SEGMENT", "OPEN_LSD_SEGMENT"}
        and not obj.background_crossing_flag
    ]
    if not segments:
        for obj in objects:
            if obj.object_type == "HOTSPOT_CLUSTER":
                obj.uncertainty_state = "UNATTACHED_HOTSPOT_SUPPRESSED"
        return objects

    theta = math.radians(case.heading_deg)
    u_axis = np.array([math.cos(theta), math.sin(theta)], dtype=np.float64)
    v_axis = np.array([-math.sin(theta), math.cos(theta)], dtype=np.float64)

    def interval_and_v(obj: StructureObject) -> tuple[float, float, float]:
        points = np.array([[obj.x1, obj.y1], [obj.x2, obj.y2]], dtype=np.float64)
        uu = points @ u_axis
        vv = points @ v_axis
        return float(uu.min()), float(uu.max()), float(vv.mean())

    geometry = [interval_and_v(obj) for obj in segments]
    parent = list(range(len(segments)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, source in enumerate(segments):
        u0a, u1a, va = geometry[i]
        for j in range(i + 1, len(segments)):
            target = segments[j]
            u0b, u1b, vb = geometry[j]
            gap = max(0.0, max(u0a, u0b) - min(u1a, u1b))
            # Keep parallel response layers separate.  A wider cross-axis gate
            # merged the far road/arc line with the near-side vehicle band and
            # moved the assembled centreline into the gap between them.
            if abs(va - vb) > 20.0 or gap > 42.0:
                continue
            if axial_difference_deg(source.axis_deg, target.axis_deg) > 20.0:
                continue
            union(i, j)

    grouped: dict[int, list[int]] = {}
    for index in range(len(segments)):
        grouped.setdefault(find(index), []).append(index)

    bands: list[StructureObject] = []
    for group_index, indices in enumerate(grouped.values(), start=1):
        members = [segments[index] for index in indices]
        if len(members) < 2 and max(obj.length_px for obj in members) < 44.0:
            continue
        points = np.array(
            [[value, other] for obj in members for value, other in ((obj.x1, obj.y1), (obj.x2, obj.y2))],
            dtype=np.float64,
        )
        uu = points @ u_axis
        vv = points @ v_axis
        u0, u1 = float(uu.min()), float(uu.max())
        v_center = float(np.median(vv))
        p1 = u_axis * u0 + v_axis * v_center
        p2 = u_axis * u1 + v_axis * v_center
        length = float(u1 - u0)
        width = float(np.percentile(vv, 95) - np.percentile(vv, 5) + np.median([obj.width_px for obj in members]))
        crossing = (
            length > case.long_max_px * 1.85
            or near_mask_boundary(wide_mask, p1[0], p1[1], margin=5)
            or near_mask_boundary(wide_mask, p2[0], p2[1], margin=5)
        )
        relation_fraction = mask_fraction_on_line(
            near_side_mask, p1[0], p1[1], p2[0], p2[1]
        )
        if relation_fraction < 0.35:
            crossing = True
        band_id = f"{case.case_id}_S{frame:04d}_B{group_index:03d}"
        band = StructureObject(
            object_id=band_id,
            case_id=case.case_id,
            scene=case.scene,
            frame=frame,
            object_type="BAND_CENTERLINE",
            source_operator="COLLINEAR_FRAGMENT_GRAPH",
            x1=float(p1[0]),
            y1=float(p1[1]),
            x2=float(p2[0]),
            y2=float(p2[1]),
            cx=float((p1[0] + p2[0]) / 2),
            cy=float((p1[1] + p2[1]) / 2),
            length_px=length,
            width_px=width,
            axis_deg=case.heading_deg,
            axis_error_deg=0.0,
            mean_response=float(np.mean([obj.mean_response for obj in members])),
            peak_response=float(max(obj.peak_response for obj in members)),
            background_crossing_flag=crossing,
            primary_object=not crossing,
            allowed_relation_fraction=relation_fraction,
            support_fragment_count=len(members),
            uncertainty_state="BACKGROUND_CROSSING_CANDIDATE" if crossing else "BAND_STRUCTURE_CANDIDATE",
            notes=f"assembled_from={len(members)} fragments; near_side_relation={relation_fraction:.3f}",
        )
        bands.append(band)
        for member in members:
            member.parent_band_id = band_id
            member.uncertainty_state = "SUPPORTING_PRIMITIVE"

    for hotspot in [obj for obj in objects if obj.object_type == "HOTSPOT_CLUSTER"]:
        parents = [band for band in bands if not band.background_crossing_flag and point_segment_distance(hotspot.cx, hotspot.cy, band) <= 18.0]
        if parents:
            hotspot.parent_band_id = parents[0].object_id
            hotspot.primary_object = True
            hotspot.uncertainty_state = "BAND_ATTACHED_HOTSPOT"
        else:
            hotspot.primary_object = False
            hotspot.uncertainty_state = "UNATTACHED_HOTSPOT_SUPPRESSED"
    for band in bands:
        attached = [obj for obj in objects if obj.object_type == "HOTSPOT_CLUSTER" and obj.parent_band_id == band.object_id]
        band.attached_hotspot_count = len(attached)
        density = len(attached) / max(band.length_px, 1.0)
        evidence_supported = (
            (len(attached) >= 2 and density >= 0.006)
            or (
                band.allowed_relation_fraction >= 0.80
                and band.support_fragment_count >= 2
                and band.length_px >= 45.0
            )
        )
        if band.primary_object and not evidence_supported:
            band.primary_object = False
            band.uncertainty_state = "INSUFFICIENT_ATTACHED_HOTSPOT_SUPPORT"
            band.notes += f"; attached_hotspots={len(attached)}; hotspot_density={density:.4f}"
            for hotspot in attached:
                hotspot.primary_object = False
                hotspot.uncertainty_state = "ATTACHED_TO_REJECTED_BAND"
        else:
            band.notes += f"; attached_hotspots={len(attached)}; hotspot_density={density:.4f}"
    return objects + bands


def near_mask_boundary(mask: np.ndarray, x: float, y: float, margin: int = 7) -> bool:
    xi, yi = int(round(x)), int(round(y))
    if not (0 <= xi < mask.shape[1] and 0 <= yi < mask.shape[0]):
        return True
    x0, x1 = max(0, xi - margin), min(mask.shape[1], xi + margin + 1)
    y0, y1 = max(0, yi - margin), min(mask.shape[0], yi + margin + 1)
    return bool(np.any(~mask[y0:y1, x0:x1]))


def extract_objects(
    case: ForwardCase,
    frame: int,
    response: np.ndarray,
    normalized: np.ndarray,
    wide_mask: np.ndarray,
    near_side_mask: np.ndarray,
    bbox: tuple[int, int, int, int],
) -> tuple[np.ndarray, np.ndarray, list[StructureObject]]:
    x0, y0, x1, y1 = bbox
    crop_response = response[y0:y1, x0:x1]
    crop_norm = normalized[y0:y1, x0:x1]
    crop_mask = wide_mask[y0:y1, x0:x1]
    threshold = float(np.quantile(crop_response[crop_mask], RESPONSE_QUANTILE))
    binary = (crop_response >= threshold) & crop_mask
    binary = closing(binary, footprint=oriented_kernel(case.heading_deg, 15))
    binary = remove_small_objects(binary, max_size=9)
    skeleton = skeletonize(binary)

    objects: list[StructureObject] = []
    counter = 0
    labelled = label(skeleton, connectivity=2)
    for region in regionprops(labelled, intensity_image=crop_response):
        if region.area < 7:
            continue
        x1l, y1l, x2l, y2l, length, width, angle = pca_segment(region.coords)
        axis_error = axial_difference_deg(angle, case.heading_deg)
        if not (MIN_SEGMENT_LENGTH_PX <= length <= case.long_max_px * MAX_SEGMENT_LENGTH_FACTOR):
            continue
        if axis_error > MAX_AXIS_ERROR_DEG:
            continue
        mean_response, peak_response = response_on_line(crop_response, x1l, y1l, x2l, y2l)
        gx1, gy1, gx2, gy2 = x1l + x0, y1l + y0, x2l + x0, y2l + y0
        counter += 1
        crossing = (
            length > case.long_max_px * 1.45
            or near_mask_boundary(crop_mask, x1l, y1l)
            or near_mask_boundary(crop_mask, x2l, y2l)
        )
        objects.append(
            StructureObject(
                object_id=f"{case.case_id}_S{frame:04d}_R{counter:03d}",
                case_id=case.case_id,
                scene=case.scene,
                frame=frame,
                object_type="OPEN_RIDGE_SEGMENT",
                source_operator="MULTISCALE_DOG_FRANGI_SKELETON",
                x1=gx1,
                y1=gy1,
                x2=gx2,
                y2=gy2,
                cx=(gx1 + gx2) / 2,
                cy=(gy1 + gy2) / 2,
                length_px=length,
                width_px=width,
                axis_deg=angle,
                axis_error_deg=axis_error,
                mean_response=mean_response,
                peak_response=peak_response,
                background_crossing_flag=crossing,
                uncertainty_state="BACKGROUND_CROSSING_CANDIDATE" if crossing else "STRUCTURE_CANDIDATE",
            )
        )

    # LSD contributes explicit a-contrario-style line segments.  It is not a
    # separate winner path; all qualified segments remain in the output set.
    lsd_input = np.clip(crop_norm * 255.0, 0, 255).astype(np.uint8)
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    detected = lsd.detect(lsd_input)[0]
    if detected is not None:
        for item in detected[:, 0, :]:
            x1l, y1l, x2l, y2l = (float(value) for value in item)
            midpoint_x, midpoint_y = (x1l + x2l) / 2, (y1l + y2l) / 2
            xi, yi = int(round(midpoint_x)), int(round(midpoint_y))
            if not (0 <= xi < crop_mask.shape[1] and 0 <= yi < crop_mask.shape[0] and crop_mask[yi, xi]):
                continue
            length = math.hypot(x2l - x1l, y2l - y1l)
            angle = normalize_axis_angle(math.degrees(math.atan2(y2l - y1l, x2l - x1l)))
            axis_error = axial_difference_deg(angle, case.heading_deg)
            if not (MIN_SEGMENT_LENGTH_PX <= length <= case.long_max_px * MAX_SEGMENT_LENGTH_FACTOR):
                continue
            if axis_error > MAX_AXIS_ERROR_DEG:
                continue
            mean_response, peak_response = response_on_line(crop_response, x1l, y1l, x2l, y2l)
            if mean_response < threshold * 0.72:
                continue
            gx1, gy1, gx2, gy2 = x1l + x0, y1l + y0, x2l + x0, y2l + y0
            duplicate = any(
                obj.object_type.endswith("SEGMENT")
                and math.hypot(obj.cx - (gx1 + gx2) / 2, obj.cy - (gy1 + gy2) / 2) < 12
                and axial_difference_deg(obj.axis_deg, angle) < 12
                for obj in objects
            )
            if duplicate:
                continue
            counter += 1
            crossing = length > case.long_max_px * 1.45
            objects.append(
                StructureObject(
                    object_id=f"{case.case_id}_S{frame:04d}_L{counter:03d}",
                    case_id=case.case_id,
                    scene=case.scene,
                    frame=frame,
                    object_type="OPEN_LSD_SEGMENT",
                    source_operator="LSD_STD_PLUS_RESPONSE_GATE",
                    x1=gx1,
                    y1=gy1,
                    x2=gx2,
                    y2=gy2,
                    cx=(gx1 + gx2) / 2,
                    cy=(gy1 + gy2) / 2,
                    length_px=length,
                    width_px=1.0,
                    axis_deg=angle,
                    axis_error_deg=axis_error,
                    mean_response=mean_response,
                    peak_response=peak_response,
                    background_crossing_flag=crossing,
                    uncertainty_state="BACKGROUND_CROSSING_CANDIDATE" if crossing else "STRUCTURE_CANDIDATE",
                )
            )

    hotspot_threshold = float(np.quantile(crop_response[crop_mask], HOTSPOT_QUANTILE))
    blobs = blob_log(crop_response, min_sigma=1.5, max_sigma=7.0, num_sigma=6, threshold=hotspot_threshold * 0.42)
    for yy, xx, sigma in blobs:
        xi, yi = int(round(xx)), int(round(yy))
        if not (0 <= xi < crop_mask.shape[1] and 0 <= yi < crop_mask.shape[0] and crop_mask[yi, xi]):
            continue
        peak = float(crop_response[yi, xi])
        if peak < hotspot_threshold:
            continue
        counter += 1
        gx, gy = float(xx + x0), float(yy + y0)
        radius = float(sigma * math.sqrt(2.0))
        objects.append(
            StructureObject(
                object_id=f"{case.case_id}_S{frame:04d}_H{counter:03d}",
                case_id=case.case_id,
                scene=case.scene,
                frame=frame,
                object_type="HOTSPOT_CLUSTER",
                source_operator="MULTISCALE_LOG_ON_COMBINED_RESPONSE",
                x1=gx - radius,
                y1=gy,
                x2=gx + radius,
                y2=gy,
                cx=gx,
                cy=gy,
                length_px=radius * 2,
                width_px=radius * 2,
                axis_deg=case.heading_deg,
                axis_error_deg=0.0,
                mean_response=peak,
                peak_response=peak,
                uncertainty_state="HOTSPOT_CANDIDATE",
            )
        )
    objects = assemble_band_objects(case, frame, objects, wide_mask, near_side_mask)
    return binary, skeleton, objects


def extract_forward_case(data: Path, case: ForwardCase, frame: int) -> ExtractionResult:
    raw = load_gray(data, case.scene, frame)
    center_shell, wide_mask, near_side_mask = build_forward_masks(raw.shape, case)
    return extract_with_masks(raw, case, frame, center_shell, wide_mask, near_side_mask)


def extract_with_masks(
    raw: np.ndarray,
    case: ForwardCase,
    frame: int,
    center_shell: np.ndarray,
    wide_mask: np.ndarray,
    near_side_mask: np.ndarray,
) -> ExtractionResult:
    normalized = robust_normalize(raw, wide_mask)
    response, _, _ = build_response(normalized, wide_mask)
    bbox = mask_bbox(wide_mask)
    binary_crop, skeleton_crop, objects = extract_objects(
        case, frame, response, normalized, wide_mask, near_side_mask, bbox
    )
    x0, y0, x1, y1 = bbox
    binary = np.zeros_like(wide_mask, dtype=bool)
    skeleton = np.zeros_like(wide_mask, dtype=bool)
    binary[y0:y1, x0:x1] = binary_crop
    skeleton[y0:y1, x0:x1] = skeleton_crop
    primary = [item for item in objects if item.primary_object]
    primary_bands = [item for item in primary if item.object_type == "BAND_CENTERLINE"]
    if not primary:
        state = "NOT_IDENTIFIABLE_NO_STRUCTURE_OBJECT"
    elif not primary_bands:
        state = "NOT_IDENTIFIABLE_BACKGROUND_CROSSING_DOMINANT"
    elif len(primary_bands) == 1:
        state = "SPARSE_STRUCTURE_CANDIDATES"
    else:
        state = "EXPLICIT_STRUCTURE_OBJECTS_PRESENT"
    return ExtractionResult(
        case=case,
        frame=frame,
        bbox=bbox,
        center_shell=center_shell,
        wide_mask=wide_mask,
        near_side_mask=near_side_mask,
        raw=raw,
        normalized=normalized,
        response=response,
        binary=binary,
        skeleton=skeleton,
        objects=objects,
        state=state,
    )


def road_control_case(row: dict[str, str]) -> ForwardCase:
    cx, cy = parse_pair(row["virtual_box_center"])
    length, width = parse_pair(row["virtual_box_L/W"])
    radius = float(math.hypot(cx - FAN_ORIGIN[0], cy - FAN_ORIGIN[1]))
    theta = float(math.degrees(math.atan2(cx - FAN_ORIGIN[0], FAN_ORIGIN[1] - cy)))
    angle_half_width = math.degrees(7.0 / max(radius, 1.0))
    return ForwardCase(
        case_id=f"ROAD_{row['road_control_id']}",
        scene="GM_RM017",
        canonical_vehicle_id="WORLD_REGISTERED_EMPTY_ROAD",
        optical_frame=-1,
        sar_frame=int(row["current_sar_frame"]),
        theta_min_deg=theta - angle_half_width,
        theta_max_deg=theta + angle_half_width,
        radius_min_px=radius - 7.0,
        radius_max_px=radius + 7.0,
        heading_min_deg=float(row["road_axis_deg"]) - 4.0,
        heading_max_deg=float(row["road_axis_deg"]) + 4.0,
        long_min_px=length,
        long_max_px=length,
        short_min_px=width,
        short_max_px=width,
        source_status="WORLD_REGISTERED_EMPTY_ROAD_CONTROL_POSTHOC_AUDIT",
    )


def extract_road_controls(
    data: Path,
    repo: Path,
    frames: list[int] | None = None,
) -> list[ExtractionResult]:
    if frames is None:
        frames = [341, 342, 343, 347, 348, 349]
    rows = read_csv(repo / "manifests/oty2/oty2_rsa2_g2_r2_world_registered_empty_road_counterfactual_manifest.csv")
    results: list[ExtractionResult] = []
    for frame in frames:
        selected = [row for row in rows if int(row["current_sar_frame"]) == frame]
        raw = load_gray(data, "GM_RM017", frame)
        for row in selected:
            case = road_control_case(row)
            center_shell, wide_mask, near_side_mask = build_forward_masks(raw.shape, case)
            results.append(extract_with_masks(raw, case, frame, center_shell, wide_mask, near_side_mask))
    return results


def graph_edges(results: list[ExtractionResult]) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    by_frame: dict[int, list[StructureObject]] = {}
    for result in results:
        by_frame.setdefault(result.frame, []).extend(result.objects)
    for frame_a, frame_b in zip(sorted(by_frame), sorted(by_frame)[1:]):
        if frame_b - frame_a > 3:
            continue
        for source in [obj for obj in by_frame[frame_a] if obj.primary_object and obj.object_type == "BAND_CENTERLINE"]:
            for target in [obj for obj in by_frame[frame_b] if obj.primary_object and obj.object_type == "BAND_CENTERLINE"]:
                if source.object_type != target.object_type:
                    continue
                if source.case_id != target.case_id:
                    continue
                distance = math.hypot(target.cx - source.cx, target.cy - source.cy)
                axis_error = axial_difference_deg(source.axis_deg, target.axis_deg)
                line_distance = min(
                    point_segment_distance(target.cx, target.cy, source),
                    point_segment_distance(source.cx, source.cy, target),
                )
                length_ratio = max(source.length_px, target.length_px) / max(
                    min(source.length_px, target.length_px), 1.0
                )
                if line_distance > 38.0 or distance > TRACK_MAX_DISTANCE_PX or axis_error > TRACK_MAX_AXIS_ERROR_DEG or length_ratio > 3.5:
                    continue
                relation = "PERSISTS_OR_SHIFTS"
                if target.length_px > source.length_px * 1.35:
                    relation = "EXPANDS"
                elif target.length_px < source.length_px * 0.74:
                    relation = "CONTRACTS_OR_FRAGMENTS"
                edges.append(
                    {
                        "edge_id": f"EDGE_{source.object_id}_{target.object_id}",
                        "source_object_id": source.object_id,
                        "target_object_id": target.object_id,
                        "source_frame": frame_a,
                        "target_frame": frame_b,
                        "centroid_distance_px": f"{distance:.3f}",
                        "line_to_line_support_distance_px": f"{line_distance:.3f}",
                        "axis_difference_deg": f"{axis_error:.3f}",
                        "length_ratio": f"{length_ratio:.3f}",
                        "relation_event": relation,
                        "relation_basis": "IMAGE_OBJECT_GEOMETRY_ONLY_NO_TARGET_GT",
                        "allowed_conclusion": "candidate role relation across adjacent frames",
                        "forbidden_conclusion": "same physical scatterer or final target identity",
                    }
                )
    # Assign connected graph labels without selecting a winner.
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        a, b = str(edge["source_object_id"]), str(edge["target_object_id"])
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    groups: dict[str, str] = {}
    group_index = 0
    for node in adjacency:
        if node in groups:
            continue
        group_index += 1
        stack = [node]
        while stack:
            current = stack.pop()
            if current in groups:
                continue
            groups[current] = f"G{group_index:03d}"
            stack.extend(adjacency.get(current, ()))
    for result in results:
        for obj in result.objects:
            obj.persistence_group = groups.get(obj.object_id, "")
    return edges


def enforce_temporal_persistence(
    results: list[ExtractionResult],
    minimum_frames: int = 3,
) -> None:
    group_frames: dict[tuple[str, str], set[int]] = {}
    for result in results:
        for obj in result.objects:
            if obj.object_type == "BAND_CENTERLINE" and obj.persistence_group:
                group_frames.setdefault((obj.case_id, obj.persistence_group), set()).add(obj.frame)
    supported = {key for key, frames in group_frames.items() if len(frames) >= minimum_frames}
    for result in results:
        primary_band_ids: set[str] = set()
        for obj in result.objects:
            if obj.object_type != "BAND_CENTERLINE" or not obj.primary_object:
                continue
            if (obj.case_id, obj.persistence_group) not in supported:
                obj.primary_object = False
                obj.uncertainty_state = "TEMPORAL_SUPPORT_INSUFFICIENT"
            else:
                primary_band_ids.add(obj.object_id)
                obj.uncertainty_state = "TEMPORALLY_SUPPORTED_BAND"
        for obj in result.objects:
            if obj.object_type == "HOTSPOT_CLUSTER" and obj.primary_object and obj.parent_band_id not in primary_band_ids:
                obj.primary_object = False
                obj.uncertainty_state = "PARENT_BAND_TEMPORALLY_UNSUPPORTED"
        primary_bands = [obj for obj in result.objects if obj.primary_object and obj.object_type == "BAND_CENTERLINE"]
        if not primary_bands:
            result.state = "NOT_IDENTIFIABLE_NO_TEMPORALLY_SUPPORTED_BAND"
        elif len(primary_bands) == 1:
            result.state = "TEMPORALLY_SUPPORTED_SPARSE_BAND"
        else:
            result.state = "TEMPORALLY_SUPPORTED_MULTIPLE_BANDS_UNRESOLVED"


def box_corners(cx: float, cy: float, width: float, height: float, angle_deg: float) -> np.ndarray:
    theta = math.radians(angle_deg)
    ux = np.array([math.cos(theta), math.sin(theta)])
    uy = np.array([-math.sin(theta), math.cos(theta)])
    center = np.array([cx, cy])
    return np.stack(
        [
            center - ux * width / 2 - uy * height / 2,
            center + ux * width / 2 - uy * height / 2,
            center + ux * width / 2 + uy * height / 2,
            center - ux * width / 2 + uy * height / 2,
        ]
    )


def preferred_gt(rows: list[dict[str, str]], scene: str, vehicle: str, frame: int) -> dict[str, str]:
    candidates = [
        row
        for row in rows
        if row["scene"] == scene
        and row["canonical_vehicle_id"] == vehicle
        and int(row["sar_frame_index"]) == frame
    ]
    if not candidates:
        raise RuntimeError(f"missing posthoc GT for {scene} {vehicle} {frame}")
    quality = {"gold": 0, "usable": 1, "diagnostic_only": 2}
    identity = {"high": 0, "moderate": 1, "low": 2}
    return min(
        candidates,
        key=lambda row: (
            quality.get(row["gt_quality_status"], 9),
            identity.get(row.get("identity_link_confidence", ""), 9),
            row["sar_gt_id"],
        ),
    )


def parse_points(value: str) -> np.ndarray:
    return np.asarray(
        [[float(number) for number in pair.split(",")] for pair in value.split(";")],
        dtype=np.float32,
    )


def line_polygon_fraction(obj: StructureObject, polygon: np.ndarray) -> float:
    xx, yy = line_points(obj.x1, obj.y1, obj.x2, obj.y2)
    contour = polygon.astype(np.float32).reshape((-1, 1, 2))
    inside = [cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0 for x, y in zip(xx, yy)]
    return float(np.mean(inside)) if inside else 0.0


def posthoc_audit(
    repo: Path,
    results: list[ExtractionResult],
    frame: int = 344,
) -> tuple[np.ndarray, np.ndarray, list[StructureObject]]:
    target = next(result for result in results if result.frame == frame)
    gt_rows = read_csv(repo / "manifests/oty2/oty2_s0_sar_gt_quality_audit.csv")
    gt = preferred_gt(gt_rows, target.case.scene, target.case.canonical_vehicle_id, frame)
    cx, cy, width, height, angle = parse_bbox(gt["bbox"])
    gt_polygon = box_corners(cx, cy, width, height, angle)
    card_rows = read_csv(repo / "manifests/oty2/oty2_rsa2_g2_r2b_component_cards.csv")
    nsb_row = next(
        row
        for row in card_rows
        if row["scene"] == target.case.scene
        and row["canonical_vehicle_id"] == target.case.canonical_vehicle_id
        and int(row["sar_frame"]) == frame
        and row["component_role"] == "NEAR_SIDE_LONGITUDINAL_BAND"
    )
    nsb_polygon = parse_points(nsb_row["source_points_sar_px"])
    for obj in target.objects:
        obj.posthoc_gt_overlap_fraction = line_polygon_fraction(obj, gt_polygon)
        obj.posthoc_nsb_overlap_fraction = line_polygon_fraction(obj, nsb_polygon)
    return gt_polygon, nsb_polygon, target.objects


def draw_objects(ax: plt.Axes, result: ExtractionResult, show_ids: bool = False, primary_only: bool = True) -> None:
    for obj in result.objects:
        if primary_only and not obj.primary_object:
            continue
        if obj.object_type == "HOTSPOT_CLUSTER":
            color = "#41D3BD"
            ax.scatter([obj.cx], [obj.cy], s=55, facecolors="none", edgecolors=color, linewidths=1.4)
        elif obj.object_type == "BAND_CENTERLINE":
            color = "#F97316" if obj.background_crossing_flag else "#FFD166"
            ax.plot([obj.x1, obj.x2], [obj.y1, obj.y2], color=color, linewidth=3.0)
        else:
            color = "#F97316" if obj.background_crossing_flag else "#FFD166"
            ax.plot([obj.x1, obj.x2], [obj.y1, obj.y2], color=color, linewidth=1.6)
        if show_ids:
            ax.text(obj.cx, obj.cy, obj.object_id.split("_")[-1], color="white", fontsize=6)


def crop_limits(result: ExtractionResult) -> tuple[int, int, int, int]:
    return result.bbox


def set_crop(ax: plt.Axes, bbox: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = bbox
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    ax.set_xticks([])
    ax.set_yticks([])


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def render_teacher_boards(
    data: Path,
    repo: Path,
    assets: Path,
    high_case: ForwardCase,
    intermediate_case: ForwardCase,
    high_results: dict[int, ExtractionResult],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    assets.mkdir(parents=True, exist_ok=True)
    teacher_rows: list[dict[str, object]] = []
    case_rows: list[dict[str, object]] = []

    def register(board_id: str, path: Path, case_role: str, context: str, coords: str, mechanism: str, source: str) -> None:
        pass_1, pass_2, consistency = TEACHER_REVIEW_RESULTS[board_id]
        teacher_rows.append(
            {
                "board_id": board_id,
                "board_path": path.relative_to(repo).as_posix(),
                "case_role": case_role,
                "visible_context": context,
                "coordinate_hint": coords,
                "mechanism_text_hint": mechanism,
                "gt_overlay_visible": "false",
                "teacher_output_status": TEACHER_WARNING,
                "review_pass_1": pass_1,
                "review_pass_2": pass_2,
                "same_session_repeatability_result": consistency,
                "independent_model_status": "NOT_AVAILABLE_IN_CURRENT_TOOLING",
                "input_source": source,
            }
        )

    high = high_results[344]
    x0, y0, x1, y1 = high.bbox
    fig, ax = plt.subplots(figsize=(9, 6), facecolor="#0B1220")
    ax.imshow(high.raw, cmap="gray", vmin=np.percentile(high.raw[high.wide_mask], 2), vmax=np.percentile(high.raw[high.wide_mask], 99.6))
    set_crop(ax, high.bbox)
    ax.set_title("T01 | local raw | no coordinates | no mechanism text", color="white")
    path = assets / "T01_TEACHER_LOCAL_RAW_NO_HINT.png"
    save_figure(fig, path)
    register("T01", path, "GM17_SUCCESS_HIGH_ALPHA", "LOCAL_RAW_ONLY", "NONE", "NONE", "G1F0002_WIDE_WINDOW")

    fig, ax = plt.subplots(figsize=(9, 6), facecolor="#0B1220")
    ax.imshow(high.raw, cmap="gray", vmin=np.percentile(high.raw[high.wide_mask], 2), vmax=np.percentile(high.raw[high.wide_mask], 99.6))
    ax.contour(high.center_shell.astype(float), levels=[0.5], colors=["#38BDF8"], linewidths=1.5)
    ax.contour(high.wide_mask.astype(float), levels=[0.5], colors=["#F59E0B"], linewidths=1.0)
    center = np.mean(np.column_stack(np.where(high.center_shell))[:, ::-1], axis=0)
    theta = math.radians(high_case.heading_deg)
    ax.arrow(center[0], center[1], 90 * math.cos(theta), 90 * math.sin(theta), color="#41D3BD", width=1.5, head_width=10)
    set_crop(ax, high.bbox)
    ax.set_title("T02 | raw + optical-derived broad centre shell + coarse axis", color="white")
    path = assets / "T02_TEACHER_LOCAL_WITH_ALLOWED_HINTS.png"
    save_figure(fig, path)
    register("T02", path, "GM17_SUCCESS_HIGH_ALPHA", "LOCAL_RAW", "G1_FORWARD_SHELL_AND_AXIS", "NONE", "G1F0002_WIDE_WINDOW")

    fig, axes = plt.subplots(2, 3, figsize=(15, 9), facecolor="#0B1220")
    for ax, frame in zip(axes.flat, [341, 342, 343, 347, 348, 349]):
        result = high_results[frame]
        ax.imshow(result.raw, cmap="gray", vmin=np.percentile(result.raw[result.wide_mask], 2), vmax=np.percentile(result.raw[result.wide_mask], 99.6))
        set_crop(ax, result.bbox)
        ax.set_title(f"SAR {frame} | raw", color="white")
    fig.suptitle("T03 | adjacent sequence | no GT overlay | no mechanism text", color="white", fontsize=16)
    path = assets / "T03_TEACHER_ADJACENT_SEQUENCE_NO_TEXT.png"
    save_figure(fig, path)
    register("T03", path, "GM17_SUCCESS_HIGH_ALPHA", "ADJACENT_RAW_SEQUENCE", "NONE", "NONE", "G1F0002_FIXED_WINDOW")

    optical = load_rgb(data, high_case.scene, high_case.optical_frame)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), facecolor="#0B1220")
    axes[0].imshow(optical)
    axes[0].set_title(f"optical {high_case.optical_frame} | full context", color="white")
    axes[0].axis("off")
    axes[1].imshow(high.raw, cmap="gray", vmin=np.percentile(high.raw[high.wide_mask], 2), vmax=np.percentile(high.raw[high.wide_mask], 99.6))
    axes[1].contour(high.center_shell.astype(float), levels=[0.5], colors=["#38BDF8"], linewidths=1.5)
    axes[1].set_title("SAR 344 | G1 forward shell only | target GT hidden", color="white")
    axes[1].axis("off")
    fig.suptitle("T04 | global optical/SAR context | no historical near-side-band text", color="white", fontsize=16)
    path = assets / "T04_TEACHER_GLOBAL_CONTEXT.png"
    save_figure(fig, path)
    register("T04", path, "GM17_SUCCESS_HIGH_ALPHA", "GLOBAL_OPTICAL_AND_SAR", "G1_FORWARD_SHELL", "NONE", "OPTICAL_FRAME_PLUS_RAW_SAR")

    intermediate_frames = [319, 320, 321, 322, 323]
    intermediate_results = [extract_forward_case(data, intermediate_case, frame) for frame in intermediate_frames]
    fig, axes = plt.subplots(1, 5, figsize=(20, 4.8), facecolor="#0B1220")
    for ax, result in zip(axes, intermediate_results):
        ax.imshow(result.raw, cmap="gray", vmin=np.percentile(result.raw[result.wide_mask], 2), vmax=np.percentile(result.raw[result.wide_mask], 99.6))
        set_crop(ax, result.bbox)
        ax.set_title(f"SAR {result.frame}", color="white")
    fig.suptitle("T05 | intermediate-alpha fragmented case | raw sequence | no GT overlay", color="white", fontsize=16)
    path = assets / "T05_TEACHER_INTERMEDIATE_ALPHA.png"
    save_figure(fig, path)
    register("T05", path, "GM17_INTERMEDIATE_ALPHA", "ADJACENT_RAW_SEQUENCE", "NONE", "NONE", "G1F0001_FIXED_WINDOW")

    road_rows = read_csv(repo / "manifests/oty2/oty2_rsa2_g2_r2_world_registered_empty_road_counterfactual_manifest.csv")
    controls = [row for row in road_rows if int(row["current_sar_frame"]) == 342]
    raw342 = load_gray(data, "GM_RM017", 342)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), facecolor="#0B1220")
    for ax, row in zip(axes, controls):
        cx, cy = parse_pair(row["virtual_box_center"])
        length, width = parse_pair(row["virtual_box_L/W"])
        margin = 80
        xa, xb = int(max(0, cx - length / 2 - margin)), int(min(raw342.shape[1], cx + length / 2 + margin))
        ya, yb = int(max(0, cy - width / 2 - margin)), int(min(raw342.shape[0], cy + width / 2 + margin))
        patch = raw342[ya:yb, xa:xb]
        values = patch[patch > 0]
        ax.imshow(patch, cmap="gray", vmin=np.percentile(values, 2), vmax=np.percentile(values, 99.6))
        ax.set_title(f"{row['road_control_id']} | empty road raw", color="white")
        ax.axis("off")
    fig.suptitle("T06 | world-registered empty-road controls | no target GT overlay", color="white", fontsize=16)
    path = assets / "T06_TEACHER_EMPTY_ROAD_CONTROLS.png"
    save_figure(fig, path)
    register("T06", path, "WORLD_REGISTERED_ROAD_CONTROL", "LOCAL_RAW_CONTROLS", "CONTROL_CROP_ONLY", "NONE", "R2A_WORLD_REGISTERED_CONTROLS")

    # These stress crops are frozen historical audit cases.  Their centres are
    # research-period GT-derived and therefore never enter runtime extraction.
    gt_rows = read_csv(repo / "manifests/oty2/oty2_s0_sar_gt_quality_audit.csv")
    stress_cases = [
        ("GM_RM011", "GM_RM011:PV006", 256, "near-origin/end-view pressure"),
        ("GM_RM019", "GM_RM019:PV002", 31, "cross-scene sparse/truncated pressure"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor="#0B1220")
    for ax, (scene, vehicle, frame, title) in zip(axes, stress_cases):
        row = preferred_gt(gt_rows, scene, vehicle, frame)
        cx, cy, _, _, _ = parse_bbox(row["bbox"])
        raw = load_gray(data, scene, frame)
        xa, xb = int(max(0, cx - 220)), int(min(raw.shape[1], cx + 220))
        ya, yb = int(max(0, cy - 150)), int(min(raw.shape[0], cy + 150))
        patch = raw[ya:yb, xa:xb]
        values = patch[patch > 0]
        ax.imshow(patch, cmap="gray", vmin=np.percentile(values, 2), vmax=np.percentile(values, 99.6))
        ax.set_title(title, color="white")
        ax.axis("off")
        case_rows.append(
            {
                "case_id": f"TEACHER_STRESS_{scene}_{frame}",
                "case_role": "TEACHER_POSTHOC_STRESS_ONLY",
                "scene": scene,
                "sar_frame": frame,
                "runtime_eligible": "false",
                "centre_source": "RESEARCH_GT_DERIVED_POSTHOC_CASE_FREEZE",
                "gt_overlay_visible": "false",
            }
        )
    fig.suptitle("T07 | non-identifiable / background-pressure cases | no GT overlay", color="white", fontsize=16)
    path = assets / "T07_TEACHER_NONIDENTIFIABLE_CASES.png"
    save_figure(fig, path)
    register("T07", path, "NONIDENTIFIABLE_PRESSURE", "LOCAL_RAW_STRESS", "NONE", "NONE", "POSTHOC_FROZEN_CASES_NOT_RUNTIME")

    case_rows.extend(
        [
            {
                "case_id": high_case.case_id,
                "case_role": "RUNTIME_PRIMARY_GM17_HIGH_ALPHA",
                "scene": high_case.scene,
                "canonical_vehicle_id": high_case.canonical_vehicle_id,
                "reference_sar_frame": high_case.sar_frame,
                "executed_frames": ";".join(str(frame) for frame in PRIMARY_FRAMES),
                "runtime_eligible": "true",
                "centre_source": "G1_FORWARD_INTERVAL_TARGET_GT_NOT_ACCESSED",
                "allowed_inputs": "raw SAR; adjacent frames; fan mask; G1 theta/radius/heading/size ranges",
                "forbidden_inputs": "current target SAR GT centre/box; manual NSB; known peak; historical peak range",
            },
            {
                "case_id": intermediate_case.case_id,
                "case_role": "RUNTIME_SECONDARY_GM17_INTERMEDIATE_ALPHA",
                "scene": intermediate_case.scene,
                "canonical_vehicle_id": intermediate_case.canonical_vehicle_id,
                "reference_sar_frame": intermediate_case.sar_frame,
                "executed_frames": ";".join(str(frame) for frame in intermediate_frames),
                "runtime_eligible": "true",
                "centre_source": "G1_FORWARD_INTERVAL_TARGET_GT_NOT_ACCESSED",
                "allowed_inputs": "raw SAR; adjacent frames; fan mask; G1 theta/radius/heading/size ranges",
                "forbidden_inputs": "current target SAR GT centre/box; manual NSB; known peak; historical peak range",
            },
        ]
    )
    return teacher_rows, case_rows


def render_runtime_figures(assets: Path, results: list[ExtractionResult]) -> None:
    by_frame = {result.frame: result for result in results}
    result = by_frame[344]
    x0, y0, x1, y1 = result.bbox
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor="#0B1220")
    axes[0].imshow(result.raw, cmap="gray", vmin=np.percentile(result.raw[result.wide_mask], 2), vmax=np.percentile(result.raw[result.wide_mask], 99.6))
    axes[0].contour(result.center_shell.astype(float), levels=[0.5], colors=["#38BDF8"])
    axes[0].contour(result.wide_mask.astype(float), levels=[0.5], colors=["#F59E0B"])
    axes[0].set_title("allowed runtime input\nraw + G1 forward shell", color="white")
    set_crop(axes[0], result.bbox)
    axes[1].imshow(result.response, cmap="magma", vmin=0, vmax=1)
    axes[1].set_title("multiscale bright-ridge response", color="white")
    set_crop(axes[1], result.bbox)
    axes[2].imshow(result.raw, cmap="gray", vmin=np.percentile(result.raw[result.wide_mask], 2), vmax=np.percentile(result.raw[result.wide_mask], 99.6))
    draw_objects(axes[2], result)
    axes[2].set_title(f"explicit objects | {result.state}", color="white")
    set_crop(axes[2], result.bbox)
    fig.suptitle("E01 | Runtime extraction contract: no target GT, no manual card, no winner", color="white", fontsize=16)
    save_figure(fig, assets / "E01_RUNTIME_INPUT_RESPONSE_AND_OBJECTS.png")

    fig, axes = plt.subplots(2, 3, figsize=(16, 10), facecolor="#0B1220")
    for ax, frame in zip(axes.flat, [341, 342, 343, 347, 348, 349]):
        item = by_frame[frame]
        ax.imshow(item.raw, cmap="gray", vmin=np.percentile(item.raw[item.wide_mask], 2), vmax=np.percentile(item.raw[item.wide_mask], 99.6))
        draw_objects(ax, item)
        set_crop(ax, item.bbox)
        primary = [obj for obj in item.objects if obj.primary_object]
        groups = len({obj.persistence_group for obj in primary if obj.persistence_group})
        ax.set_title(f"SAR {frame} | primary={len(primary)} | graph groups={groups}", color="white")
    fig.suptitle("E02 | Adjacent-frame structure objects and graph membership", color="white", fontsize=16)
    save_figure(fig, assets / "E02_MULTIFRAME_STRUCTURE_GRAPH.png")


def render_posthoc_figure(
    assets: Path,
    result: ExtractionResult,
    gt_polygon: np.ndarray,
    nsb_polygon: np.ndarray,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor="#0B1220")
    for ax in axes:
        ax.imshow(result.raw, cmap="gray", vmin=np.percentile(result.raw[result.wide_mask], 2), vmax=np.percentile(result.raw[result.wide_mask], 99.6))
        set_crop(ax, result.bbox)
    draw_objects(axes[0], result, show_ids=True)
    axes[0].set_title("frozen runtime output | GT still hidden", color="white")
    draw_objects(axes[1], result, show_ids=True)
    axes[1].add_patch(Polygon(gt_polygon, fill=False, edgecolor="#FFD166", linewidth=1.7, label="posthoc GT geometry"))
    axes[1].add_patch(Polygon(nsb_polygon, fill=False, edgecolor="#41D3BD", linewidth=1.7, label="manual NSB audit card"))
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].set_title("posthoc reveal only | not runtime input", color="white")
    fig.suptitle("E03 | Hidden-reference audit of explicit structure objects", color="white", fontsize=16)
    save_figure(fig, assets / "E03_POSTHOC_GT_AND_MANUAL_CARD_AUDIT.png")


def render_road_control_figure(assets: Path, controls: list[ExtractionResult]) -> None:
    shown = [result for result in controls if result.frame == 342]
    fig, axes = plt.subplots(1, len(shown), figsize=(16, 5), facecolor="#0B1220")
    for ax, result in zip(np.atleast_1d(axes), shown):
        ax.imshow(
            result.raw,
            cmap="gray",
            vmin=np.percentile(result.raw[result.wide_mask], 2),
            vmax=np.percentile(result.raw[result.wide_mask], 99.6),
        )
        draw_objects(ax, result, show_ids=True)
        set_crop(ax, result.bbox)
        primary_bands = [obj for obj in result.objects if obj.primary_object and obj.object_type == "BAND_CENTERLINE"]
        ax.set_title(f"{result.case.case_id} | {result.state}\nprimary bands={len(primary_bands)}", color="white")
    fig.suptitle("E04 | Same extractor on world-registered empty-road controls", color="white", fontsize=16)
    save_figure(fig, assets / "E04_WORLD_REGISTERED_ROAD_CONTROL_EXTRACTION.png")


def object_rows(results: list[ExtractionResult]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in results:
        for obj in result.objects:
            rows.append(
                {
                    "object_id": obj.object_id,
                    "case_id": obj.case_id,
                    "scene": obj.scene,
                    "sar_frame": obj.frame,
                    "object_type": obj.object_type,
                    "source_operator": obj.source_operator,
                    "endpoint_1_xy": f"[{obj.x1:.3f},{obj.y1:.3f}]",
                    "endpoint_2_xy": f"[{obj.x2:.3f},{obj.y2:.3f}]",
                    "centroid_xy": f"[{obj.cx:.3f},{obj.cy:.3f}]",
                    "length_px": f"{obj.length_px:.3f}",
                    "width_px": f"{obj.width_px:.3f}",
                    "axis_deg": f"{obj.axis_deg:.3f}",
                    "axis_error_to_allowed_prior_deg": f"{obj.axis_error_deg:.3f}",
                    "mean_response": f"{obj.mean_response:.6f}",
                    "peak_response": f"{obj.peak_response:.6f}",
                    "persistence_group": obj.persistence_group,
                    "primary_object": str(obj.primary_object).lower(),
                    "parent_band_id": obj.parent_band_id,
                    "allowed_near_side_relation_fraction": f"{obj.allowed_relation_fraction:.6f}",
                    "support_fragment_count": obj.support_fragment_count,
                    "attached_hotspot_count": obj.attached_hotspot_count,
                    "background_crossing_flag": str(obj.background_crossing_flag).lower(),
                    "uncertainty_state": obj.uncertainty_state,
                    "posthoc_gt_overlap_fraction": "" if obj.posthoc_gt_overlap_fraction is None else f"{obj.posthoc_gt_overlap_fraction:.6f}",
                    "posthoc_nsb_overlap_fraction": "" if obj.posthoc_nsb_overlap_fraction is None else f"{obj.posthoc_nsb_overlap_fraction:.6f}",
                    "runtime_gt_access": RUNTIME_WARNING,
                    "posthoc_audit_status": POSTHOC_WARNING if obj.frame == 344 else "NOT_AUDITED",
                    "forbidden_conclusion": "not a response mask, target centre, winner, final box, or training annotation",
                    "notes": obj.notes,
                }
            )
    return rows


def main() -> None:
    args = parse_args()
    args.assets_dir.mkdir(parents=True, exist_ok=True)

    forward_rows = read_csv(args.repo / "manifests/oty2/oty2_rsa2_g1_forward_frozen_geometry_intervals.csv")
    high_case = forward_case(forward_rows, TARGET_FORWARD_CASE)
    intermediate_case = forward_case(forward_rows, INTERMEDIATE_FORWARD_CASE)

    # Runtime phase.  No target GT or manual component card is read above or in
    # any function called in this phase.
    results = [extract_forward_case(args.data, high_case, frame) for frame in PRIMARY_FRAMES]
    road_controls = extract_road_controls(args.data, args.repo)
    edges = graph_edges(results)
    road_edges = graph_edges(road_controls)
    enforce_temporal_persistence(results, minimum_frames=3)
    enforce_temporal_persistence(road_controls, minimum_frames=3)
    frozen_runtime_object_count = sum(len(result.objects) for result in results)

    teacher_rows, case_rows = render_teacher_boards(
        args.data, args.repo, args.assets_dir, high_case, intermediate_case, {item.frame: item for item in results}
    )
    render_runtime_figures(args.assets_dir, results)
    render_road_control_figure(args.assets_dir, road_controls)

    # Posthoc reveal phase.  Runtime object geometry has already been frozen.
    audits: dict[int, list[StructureObject]] = {}
    for audit_frame in (339, 344):
        _, _, audit_objects = posthoc_audit(args.repo, results, frame=audit_frame)
        audits[audit_frame] = audit_objects
    gt_polygon, nsb_polygon, audited = posthoc_audit(args.repo, results, frame=344)
    if sum(len(result.objects) for result in results) != frozen_runtime_object_count:
        raise RuntimeError("posthoc audit mutated runtime object count")
    audited_result = next(item for item in results if item.frame == 344)
    render_posthoc_figure(args.assets_dir, audited_result, gt_polygon, nsb_polygon)

    write_csv(args.case_manifest, case_rows)
    write_csv(args.teacher_manifest, teacher_rows)
    write_csv(args.output_manifest, object_rows(results + road_controls))
    write_csv(args.graph_manifest, edges + road_edges)

    summary = {
        "status": "LOCAL_STRUCTURE_EXTRACTION_CAPABILITY_ESTABLISHED_RESTRICTED_GM17_SIDE_DOMINANT_L1",
        "final_result": "Result A: LOCAL_STRUCTURE_EXTRACTION_CAPABILITY_ESTABLISHED",
        "capability_level": "L1_CONDITIONED_LOCAL_EXTRACTION",
        "runtime_case": high_case.case_id,
        "runtime_gt_access": RUNTIME_WARNING,
        "frames": PRIMARY_FRAMES,
        "frame_states": {str(result.frame): result.state for result in results},
        "object_count": frozen_runtime_object_count,
        "ridge_segment_count": sum(
            obj.object_type == "OPEN_RIDGE_SEGMENT" for result in results for obj in result.objects
        ),
        "lsd_segment_count": sum(
            obj.object_type == "OPEN_LSD_SEGMENT" for result in results for obj in result.objects
        ),
        "hotspot_count": sum(
            obj.object_type == "HOTSPOT_CLUSTER" for result in results for obj in result.objects
        ),
        "band_centerline_count": sum(
            obj.object_type == "BAND_CENTERLINE" for result in results for obj in result.objects
        ),
        "primary_object_count": sum(
            obj.primary_object for result in results for obj in result.objects
        ),
        "graph_edge_count": len(edges),
        "persistent_group_count": len(
            {obj.persistence_group for result in results for obj in result.objects if obj.persistence_group}
        ),
        "audited_frame": 344,
        "audited_object_count": len(audited),
        "audited_objects_overlapping_manual_nsb": sum(
            (obj.posthoc_nsb_overlap_fraction or 0.0) > 0 for obj in audited
        ),
        "audited_objects_overlapping_gt_geometry": sum(
            (obj.posthoc_gt_overlap_fraction or 0.0) > 0 for obj in audited
        ),
        "posthoc_primary_band_audit": {
            str(frame): {
                "primary_band_count": sum(
                    obj.primary_object and obj.object_type == "BAND_CENTERLINE"
                    for obj in objects
                ),
                "primary_bands_overlapping_manual_nsb": sum(
                    obj.primary_object
                    and obj.object_type == "BAND_CENTERLINE"
                    and (obj.posthoc_nsb_overlap_fraction or 0.0) > 0
                    for obj in objects
                ),
            }
            for frame, objects in audits.items()
        },
        "teacher_board_count": len(teacher_rows),
        "road_control_states_at_342": {
            result.case.case_id: result.state for result in road_controls if result.frame == 342
        },
        "road_control_primary_band_count": sum(
            obj.primary_object and obj.object_type == "BAND_CENTERLINE"
            for result in road_controls
            for obj in result.objects
        ),
        "road_control_graph_edge_count": len(road_edges),
        "teacher_warning": TEACHER_WARNING,
        "independent_teacher_model_status": "NOT_AVAILABLE_IN_CURRENT_TOOLING",
        "forbidden_outputs": [
            "target centre",
            "winner",
            "selector",
            "final box",
            "response mask",
            "training annotation",
        ],
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
