"""Generate E0 GT-conditioned SAR physical region contrast artifacts.

E0 is posthoc and GT-conditioned by design. It uses GT to generate controlled
regions and extract physical contrast features, but it does not create a
selector, ranking score, final vehicle box, final annotation, or GT edit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw


DATE = "20260712"
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
START_COMMIT = "593f89894d36dfcf8da1a7a2d97c1d24355ef39f"
TARGET_THREAD = "oty1t_obj_GM_RM017_bytetrack_bt_0010"
N005_THREAD = "oty1t_obj_GM_RM017_bytetrack_bt_0002"

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_e0_gm017_metric_region_contrast_{DATE}"
VISUAL_DIR = OUTPUT_DIR / "visual_review"
REPLAY_DIR = OUTPUT_DIR / "_verify_replay_tmp"

PAIR_CSV = SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv"
P0_COMPONENTS = SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_response_component_observations_{DATE}.csv"
P0_PARAMS = SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_factor_parameters_{DATE}.csv"
SCENE_CONFIG = REPO_ROOT / "configs" / "scene_config.yaml"
PROTOCOL = REPO_ROOT / "docs" / "OTY2_GM017_GT_CONDITIONED_METRIC_PHYSICAL_REGION_CONTRAST_E0_PROTOCOL.md"

SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
P0_PX_TO_M = 0.03

OUTPUTS = {
    "metric_coordinate_mapping": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_metric_coordinate_mapping_{DATE}.csv",
    "vehicle_body_size_reference": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_vehicle_body_size_reference_{DATE}.csv",
    "gt_metric_geometry": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_gt_metric_geometry_{DATE}.csv",
    "region_perturbation_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_region_perturbation_manifest_{DATE}.csv",
    "region_feature_table": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_region_feature_table_{DATE}.csv",
    "background_control_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_background_control_manifest_{DATE}.csv",
    "mask_censoring_audit": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_mask_censoring_audit_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_visual_review_manifest_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_pre_eval_seal_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_replay_check_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_frozen_manifest_{DATE}.csv",
}

CORE_GENERATION_KEYS = [
    "metric_coordinate_mapping",
    "vehicle_body_size_reference",
    "gt_metric_geometry",
    "region_perturbation_manifest",
    "region_feature_table",
    "background_control_manifest",
    "mask_censoring_audit",
    "visual_review_manifest",
]


@dataclass(frozen=True)
class GtContext:
    pair_id: str
    sar_frame: int
    optical_frame: int
    sar_gt_id: str
    bbox: tuple[float, float, float, float]
    cx: float
    cy: float
    width: float
    height: float
    area: float
    range_unit: tuple[float, float]
    azimuth_unit: tuple[float, float]
    range_extent_px: float
    azimuth_extent_px: float
    long_unit: tuple[float, float]
    short_unit: tuple[float, float]
    long_extent_px: float
    short_extent_px: float
    visibility_state: str
    usable_for_calibration: str
    blocked_reason: str


@dataclass(frozen=True)
class RegionSpec:
    region_id: str
    pair_id: str
    sar_frame: int
    family: str
    variant: str
    comparison_group: str
    geometry_basis: str
    center_x: float
    center_y: float
    width_px: float
    height_px: float
    angle_deg: float
    area_ratio_to_gt: float
    offset_axis: str
    offset_value: float
    offset_unit: str
    scale_ratio: float
    rotation_relative_to_gt_deg: float
    source_role: str
    interpretation_scope: str
    gt_overlap_allowed: str
    background_source: str
    outer_polygon: tuple[tuple[float, float], ...]
    inner_polygon: tuple[tuple[float, float], ...] | None = None


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fmt(value: Any, ndigits: int = 6) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return ""
    return f"{number:.{ndigits}f}".rstrip("0").rstrip(".")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".csv":
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def ensure_dirs() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)


def load_scene_config() -> dict[str, Any]:
    with SCENE_CONFIG.open(encoding="utf-8") as handle:
        return json.load(handle)


def sar_gray_path(frame: int) -> Path:
    config = load_scene_config()
    return Path(config["scenes"][SCENE]["paths"]["sar_gray_frames_dir"]) / f"{frame:06d}.png"


def unit(vec: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(vec[0], vec[1])
    if length <= 1e-9:
        return (1.0, 0.0)
    return (vec[0] / length, vec[1] / length)


def dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def axis_angle_deg(axis: tuple[float, float]) -> float:
    return math.degrees(math.atan2(axis[1], axis[0]))


def angle_diff_deg(a: float, b: float) -> float:
    diff = (a - b + 180.0) % 360.0 - 180.0
    if diff <= -180.0:
        diff += 360.0
    return diff


def box_from_row(row: Mapping[str, Any], prefix: str = "sar") -> tuple[float, float, float, float]:
    return (
        parse_float(row[f"{prefix}_bbox_x1"]),
        parse_float(row[f"{prefix}_bbox_y1"]),
        parse_float(row[f"{prefix}_bbox_x2"]),
        parse_float(row[f"{prefix}_bbox_y2"]),
    )


def box_center(box: Sequence[float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def box_width(box: Sequence[float]) -> float:
    return max(0.0, box[2] - box[0])


def box_height(box: Sequence[float]) -> float:
    return max(0.0, box[3] - box[1])


def projected_extent(width: float, height: float, axis: tuple[float, float]) -> float:
    return abs(axis[0]) * width + abs(axis[1]) * height


def rect_polygon(cx: float, cy: float, width: float, height: float, angle_deg: float) -> tuple[tuple[float, float], ...]:
    rad = math.radians(angle_deg)
    u = (math.cos(rad), math.sin(rad))
    v = (-math.sin(rad), math.cos(rad))
    hw = width / 2.0
    hh = height / 2.0
    return (
        (cx - hw * u[0] - hh * v[0], cy - hw * u[1] - hh * v[1]),
        (cx + hw * u[0] - hh * v[0], cy + hw * u[1] - hh * v[1]),
        (cx + hw * u[0] + hh * v[0], cy + hw * u[1] + hh * v[1]),
        (cx - hw * u[0] + hh * v[0], cy - hw * u[1] + hh * v[1]),
    )


def polygon_bounds(polygons: Iterable[Sequence[tuple[float, float]]]) -> tuple[int, int, int, int]:
    xs: list[float] = []
    ys: list[float] = []
    for poly in polygons:
        for x, y in poly:
            xs.append(x)
            ys.append(y)
    if not xs:
        return (0, 0, 1, 1)
    x1 = max(0, int(math.floor(min(xs))) - 2)
    y1 = max(0, int(math.floor(min(ys))) - 2)
    x2 = min(SAR_WIDTH - 1, int(math.ceil(max(xs))) + 2)
    y2 = min(SAR_HEIGHT - 1, int(math.ceil(max(ys))) + 2)
    if x2 <= x1:
        x2 = min(SAR_WIDTH - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(SAR_HEIGHT - 1, y1 + 1)
    return x1, y1, x2, y2


def bbox_intersects(a: Sequence[float], b: Sequence[float]) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def polygon_aabb(poly: Sequence[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def target_rows() -> list[dict[str, str]]:
    rows = [
        row
        for row in read_csv(PAIR_CSV)
        if row.get("scene") == SCENE
        and row.get("optical_thread_id") == TARGET_THREAD
    ]
    return sorted(rows, key=lambda row: (parse_int(row["sar_frame"]), row["pair_id"]))


def vehicle_boxes_by_frame() -> dict[int, list[tuple[float, float, float, float]]]:
    boxes: dict[int, list[tuple[float, float, float, float]]] = {}
    for row in read_csv(PAIR_CSV):
        if row.get("scene") != SCENE:
            continue
        frame = parse_int(row.get("sar_frame"))
        boxes.setdefault(frame, []).append(box_from_row(row, "sar"))
    return boxes


def make_context(row: Mapping[str, str]) -> GtContext:
    bbox = box_from_row(row, "sar")
    cx, cy = box_center(bbox)
    width = box_width(bbox)
    height = box_height(bbox)
    range_unit = unit((cx - FAN_CENTER_X, cy - FAN_CENTER_Y))
    azimuth_unit = (-range_unit[1], range_unit[0])
    range_extent = projected_extent(width, height, range_unit)
    az_extent = projected_extent(width, height, azimuth_unit)
    if width >= height:
        long_unit = (1.0, 0.0)
        short_unit = (0.0, 1.0)
        long_extent = width
        short_extent = height
    else:
        long_unit = (0.0, 1.0)
        short_unit = (1.0, 0.0)
        long_extent = height
        short_extent = width
    return GtContext(
        pair_id=row["pair_id"],
        sar_frame=parse_int(row["sar_frame"]),
        optical_frame=parse_int(row["optical_frame"]),
        sar_gt_id=row.get("sar_gt_id", ""),
        bbox=bbox,
        cx=cx,
        cy=cy,
        width=width,
        height=height,
        area=width * height,
        range_unit=range_unit,
        azimuth_unit=azimuth_unit,
        range_extent_px=range_extent,
        azimuth_extent_px=az_extent,
        long_unit=long_unit,
        short_unit=short_unit,
        long_extent_px=long_extent,
        short_extent_px=short_extent,
        visibility_state=row.get("visibility_state", ""),
        usable_for_calibration=row.get("usable_for_calibration", ""),
        blocked_reason=row.get("blocked_reason", ""),
    )


def region(
    ctx: GtContext,
    idx: int,
    family: str,
    variant: str,
    comparison_group: str,
    geometry_basis: str,
    cx: float,
    cy: float,
    width: float,
    height: float,
    angle_deg: float,
    *,
    offset_axis: str = "",
    offset_value: float = 0.0,
    offset_unit: str = "",
    scale_ratio: float = 1.0,
    source_role: str = "vehicle_reference_or_perturbation",
    interpretation_scope: str = "posthoc_physical_contrast",
    gt_overlap_allowed: str = "true",
    background_source: str = "",
    inner_scale: float | None = None,
    inner_polygon: tuple[tuple[float, float], ...] | None = None,
) -> RegionSpec:
    outer = rect_polygon(cx, cy, width, height, angle_deg)
    inner = inner_polygon
    if inner_scale is not None:
        inner = rect_polygon(cx, cy, width * inner_scale, height * inner_scale, angle_deg)
    return RegionSpec(
        region_id=f"E0_REG_{ctx.sar_frame:06d}_{idx:04d}",
        pair_id=ctx.pair_id,
        sar_frame=ctx.sar_frame,
        family=family,
        variant=variant,
        comparison_group=comparison_group,
        geometry_basis=geometry_basis,
        center_x=cx,
        center_y=cy,
        width_px=width,
        height_px=height,
        angle_deg=angle_deg,
        area_ratio_to_gt=(width * height) / max(ctx.area, 1e-9),
        offset_axis=offset_axis,
        offset_value=offset_value,
        offset_unit=offset_unit,
        scale_ratio=scale_ratio,
        rotation_relative_to_gt_deg=angle_diff_deg(angle_deg, 0.0),
        source_role=source_role,
        interpretation_scope=interpretation_scope,
        gt_overlap_allowed=gt_overlap_allowed,
        background_source=background_source,
        outer_polygon=outer,
        inner_polygon=inner,
    )


def move_until_no_vehicle_overlap(
    ctx: GtContext,
    center: tuple[float, float],
    direction: tuple[float, float],
    width: float,
    height: float,
    angle: float,
    boxes: Sequence[tuple[float, float, float, float]],
) -> tuple[float, float]:
    cx, cy = center
    step = max(width, height) * 0.75
    d = unit(direction)
    for _ in range(8):
        poly = rect_polygon(cx, cy, width, height, angle)
        aabb = polygon_aabb(poly)
        if not any(bbox_intersects(aabb, box) for box in boxes):
            return cx, cy
        cx += d[0] * step
        cy += d[1] * step
        cx = min(max(cx, width / 2.0), SAR_WIDTH - width / 2.0)
        cy = min(max(cy, height / 2.0), SAR_HEIGHT - height / 2.0)
    return cx, cy


def n005_component_controls() -> dict[str, tuple[float, float, str]]:
    rows = [
        row
        for row in read_csv(P0_COMPONENTS)
        if row.get("segment_id") == "GM017_N005_BACKGROUND_CONTROL"
    ]
    if not rows:
        return {
            "known_non_vehicle_same_area": (1108.5, 1159.3, "fallback_n005_component_coordinate"),
            "linear_structure_background_same_area": (1710.0, 861.5, "fallback_n005_linear_coordinate"),
            "strong_scatterer_background_same_area": (1108.5, 1159.3, "fallback_n005_strong_coordinate"),
        }
    by_energy = sorted(rows, key=lambda row: parse_float(row.get("integrated_energy")), reverse=True)
    by_aspect = sorted(rows, key=lambda row: parse_float(row.get("aspect_ratio")), reverse=True)
    by_peak = sorted(rows, key=lambda row: parse_float(row.get("peak_energy")), reverse=True)
    return {
        "known_non_vehicle_same_area": (
            parse_float(by_energy[0]["centroid_x"]),
            parse_float(by_energy[0]["centroid_y"]),
            by_energy[0]["component_id"],
        ),
        "linear_structure_background_same_area": (
            parse_float(by_aspect[0]["centroid_x"]),
            parse_float(by_aspect[0]["centroid_y"]),
            by_aspect[0]["component_id"],
        ),
        "strong_scatterer_background_same_area": (
            parse_float(by_peak[0]["centroid_x"]),
            parse_float(by_peak[0]["centroid_y"]),
            by_peak[0]["component_id"],
        ),
    }


def image_cache() -> dict[int, np.ndarray]:
    return {}


def load_image(frame: int, cache: dict[int, np.ndarray]) -> np.ndarray:
    if frame not in cache:
        cache[frame] = np.asarray(Image.open(sar_gray_path(frame)).convert("L"), dtype=np.float32)
    return cache[frame]


def scan_background_candidate(
    image: np.ndarray,
    width: float,
    height: float,
    boxes: Sequence[tuple[float, float, float, float]],
    mode: str,
) -> tuple[float, float, str]:
    w = max(10, int(round(width)))
    h = max(10, int(round(height)))
    stride_x = max(35, w // 2)
    stride_y = max(35, h // 2)
    best: tuple[float, float, float, str] | None = None
    for y1 in range(720, max(721, SAR_HEIGHT - h), stride_y):
        for x1 in range(0, max(1, SAR_WIDTH - w), stride_x):
            box = (float(x1), float(y1), float(x1 + w), float(y1 + h))
            if any(bbox_intersects(box, gt_box) for gt_box in boxes):
                continue
            crop = image[y1 : y1 + h, x1 : x1 + w]
            if crop.size == 0:
                continue
            zero_frac = float(np.mean(crop <= 0))
            mean = float(np.mean(crop))
            q95 = float(np.percentile(crop, 95))
            if mode == "mask_edge":
                score = zero_frac * 80.0 + mean * 0.2 - abs(zero_frac - 0.35) * 25.0
                source = f"zero_proxy_scan_zero_fraction={fmt(zero_frac)}"
            else:
                score = q95 + mean * 0.2 - zero_frac * 20.0
                source = f"frame_scan_q95={fmt(q95)}"
            if best is None or score > best[0]:
                best = (score, x1 + w / 2.0, y1 + h / 2.0, source)
    if best is None:
        return (width / 2.0, 760 + height / 2.0, f"{mode}_fallback")
    return best[1], best[2], best[3]


def build_regions_for_context(
    ctx: GtContext,
    boxes_by_frame: Mapping[int, Sequence[tuple[float, float, float, float]]],
    n005: Mapping[str, tuple[float, float, str]],
    cache: dict[int, np.ndarray],
) -> list[RegionSpec]:
    specs: list[RegionSpec] = []
    idx = 1

    def add(spec: RegionSpec) -> None:
        nonlocal idx
        specs.append(spec)
        idx += 1

    add(region(ctx, idx, "GT_ORIGINAL", "gt_original", "vehicle_reference", "axis_aligned_sar_gt_bbox", ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0, scale_ratio=1.0))

    scales = [0.50, 0.75, 1.00, 1.25, 1.50, 2.00]
    for scale in scales:
        add(region(ctx, idx, "SCALE", f"uniform_scale_{scale:.2f}", "scale_response", "axis_aligned_sar_gt_bbox", ctx.cx, ctx.cy, ctx.width * scale, ctx.height * scale, 0.0, scale_ratio=scale))
        add(region(ctx, idx, "SCALE", f"range_only_scale_{scale:.2f}", "scale_response", "local_range_azimuth_axes", ctx.cx, ctx.cy, ctx.range_extent_px * scale, ctx.azimuth_extent_px, axis_angle_deg(ctx.range_unit), scale_ratio=scale))
        add(region(ctx, idx, "SCALE", f"azimuth_only_scale_{scale:.2f}", "scale_response", "local_range_azimuth_axes", ctx.cx, ctx.cy, ctx.range_extent_px, ctx.azimuth_extent_px * scale, axis_angle_deg(ctx.range_unit), scale_ratio=scale))
        long_w = ctx.width * scale if ctx.width >= ctx.height else ctx.width
        long_h = ctx.height if ctx.width >= ctx.height else ctx.height * scale
        short_w = ctx.width if ctx.width >= ctx.height else ctx.width * scale
        short_h = ctx.height * scale if ctx.width >= ctx.height else ctx.height
        add(region(ctx, idx, "SCALE", f"storage_long_axis_only_scale_{scale:.2f}", "scale_response", "axis_aligned_storage_long_short", ctx.cx, ctx.cy, long_w, long_h, 0.0, scale_ratio=scale))
        add(region(ctx, idx, "SCALE", f"storage_short_axis_only_scale_{scale:.2f}", "scale_response", "axis_aligned_storage_long_short", ctx.cx, ctx.cy, short_w, short_h, 0.0, scale_ratio=scale))

    expansion = 0.25
    add(region(ctx, idx, "DIRECTIONAL_EXPANSION", "symmetric_expand_0.25", "directional_expansion", "axis_aligned_sar_gt_bbox", ctx.cx, ctx.cy, ctx.width * (1 + expansion), ctx.height * (1 + expansion), 0.0, scale_ratio=1 + expansion))
    for name, direction, basis, angle, width, height in [
        ("near_range_side_expand_0.25", (-ctx.range_unit[0], -ctx.range_unit[1]), "local_range_azimuth_axes", axis_angle_deg(ctx.range_unit), ctx.range_extent_px * 1.25, ctx.azimuth_extent_px),
        ("far_range_side_expand_0.25", ctx.range_unit, "local_range_azimuth_axes", axis_angle_deg(ctx.range_unit), ctx.range_extent_px * 1.25, ctx.azimuth_extent_px),
        ("positive_azimuth_side_expand_0.25", ctx.azimuth_unit, "local_range_azimuth_axes", axis_angle_deg(ctx.range_unit), ctx.range_extent_px, ctx.azimuth_extent_px * 1.25),
        ("negative_azimuth_side_expand_0.25", (-ctx.azimuth_unit[0], -ctx.azimuth_unit[1]), "local_range_azimuth_axes", axis_angle_deg(ctx.range_unit), ctx.range_extent_px, ctx.azimuth_extent_px * 1.25),
        ("storage_front_expand_0.25", ctx.long_unit, "axis_aligned_storage_long_short_unoriented", 0.0, ctx.width * 1.25 if ctx.width >= ctx.height else ctx.width, ctx.height if ctx.width >= ctx.height else ctx.height * 1.25),
        ("storage_rear_expand_0.25", (-ctx.long_unit[0], -ctx.long_unit[1]), "axis_aligned_storage_long_short_unoriented", 0.0, ctx.width * 1.25 if ctx.width >= ctx.height else ctx.width, ctx.height if ctx.width >= ctx.height else ctx.height * 1.25),
    ]:
        shift = expansion * max(width, height) / 2.0
        add(region(ctx, idx, "DIRECTIONAL_EXPANSION", name, "directional_expansion", basis, ctx.cx + direction[0] * shift, ctx.cy + direction[1] * shift, width, height, angle, scale_ratio=1.25))

    for name, direction in [("near_side_half", (-ctx.range_unit[0], -ctx.range_unit[1])), ("far_side_half", ctx.range_unit)]:
        add(region(ctx, idx, "INTERNAL_CROP", name, "internal_response_distribution", "local_range_azimuth_axes", ctx.cx + direction[0] * ctx.range_extent_px / 4.0, ctx.cy + direction[1] * ctx.range_extent_px / 4.0, ctx.range_extent_px / 2.0, ctx.azimuth_extent_px, axis_angle_deg(ctx.range_unit), scale_ratio=0.5))
    for name, direction in [("storage_front_half", ctx.long_unit), ("storage_rear_half", (-ctx.long_unit[0], -ctx.long_unit[1]))]:
        if ctx.width >= ctx.height:
            add(region(ctx, idx, "INTERNAL_CROP", name, "internal_response_distribution", "axis_aligned_storage_long_short_unoriented", ctx.cx + direction[0] * ctx.width / 4.0, ctx.cy, ctx.width / 2.0, ctx.height, 0.0, scale_ratio=0.5))
        else:
            add(region(ctx, idx, "INTERNAL_CROP", name, "internal_response_distribution", "axis_aligned_storage_long_short_unoriented", ctx.cx, ctx.cy + direction[1] * ctx.height / 4.0, ctx.width, ctx.height / 2.0, 0.0, scale_ratio=0.5))
    add(region(ctx, idx, "INTERNAL_CROP", "center_core_0.50", "internal_response_distribution", "axis_aligned_sar_gt_bbox", ctx.cx, ctx.cy, ctx.width * 0.5, ctx.height * 0.5, 0.0, scale_ratio=0.25))
    add(region(ctx, idx, "INTERNAL_CROP", "boundary_band_inner_0.75", "internal_response_distribution", "axis_aligned_sar_gt_bbox", ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0, inner_scale=0.75))

    offsets = [-1.00, -0.50, -0.25, 0.25, 0.50, 1.00]
    translation_axes = [
        ("image_x", (1.0, 0.0), ctx.width),
        ("image_y", (0.0, 1.0), ctx.height),
        ("local_range", ctx.range_unit, ctx.range_extent_px),
        ("local_azimuth", ctx.azimuth_unit, ctx.azimuth_extent_px),
        ("storage_long_axis", ctx.long_unit, ctx.long_extent_px),
        ("storage_short_axis", ctx.short_unit, ctx.short_extent_px),
    ]
    for axis_name, axis, extent in translation_axes:
        for off in offsets:
            add(
                region(
                    ctx,
                    idx,
                    "TRANSLATION",
                    f"{axis_name}_{off:+.2f}_gt_extent",
                    "translation_response_surface",
                    "same_area_axis_aligned_or_local_shift",
                    ctx.cx + axis[0] * extent * off,
                    ctx.cy + axis[1] * extent * off,
                    ctx.width,
                    ctx.height,
                    0.0,
                    offset_axis=axis_name,
                    offset_value=off,
                    offset_unit="gt_axis_extent",
                )
            )

    for angle in [-90, -60, -45, -30, -15, 0, 15, 30, 45, 60, 90]:
        add(region(ctx, idx, "ROTATION", f"image_axis_rotation_{angle:+d}", "rotation_response_curve", "same_center_axis_rotation", ctx.cx, ctx.cy, ctx.width, ctx.height, float(angle)))

    for scale in [1.10, 1.25, 1.50, 2.00]:
        add(region(ctx, idx, "RING", f"{int((scale - 1.0) * 100)}pct_expansion_ring", "ring_contrast", "expanded_region_minus_original_gt", ctx.cx, ctx.cy, ctx.width * scale, ctx.height * scale, 0.0, scale_ratio=scale, inner_polygon=rect_polygon(ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0)))

    boxes = boxes_by_frame.get(ctx.sar_frame, [])
    background_specs = [
        ("near_background_same_area", (-ctx.range_unit[0], -ctx.range_unit[1]), "local_range_background"),
        ("far_background_same_area", ctx.range_unit, "local_range_background"),
    ]
    for name, direction, source in background_specs:
        center = (ctx.cx + direction[0] * ctx.range_extent_px * 1.8, ctx.cy + direction[1] * ctx.range_extent_px * 1.8)
        cx, cy = move_until_no_vehicle_overlap(ctx, center, direction, ctx.width, ctx.height, 0.0, boxes)
        add(region(ctx, idx, "BACKGROUND_CONTROL", name, "same_area_background_control", "same_area_axis_aligned_background", cx, cy, ctx.width, ctx.height, 0.0, source_role="background_control", gt_overlap_allowed="false", background_source=source))

    image = load_image(ctx.sar_frame, cache)
    sx, sy, source = scan_background_candidate(image, ctx.width, ctx.height, boxes, "strong")
    add(region(ctx, idx, "BACKGROUND_CONTROL", "strong_scatterer_background_same_area", "same_area_background_control", "same_area_axis_aligned_background", sx, sy, ctx.width, ctx.height, 0.0, source_role="background_control", gt_overlap_allowed="false", background_source=source))
    mx, my, source = scan_background_candidate(image, ctx.width, ctx.height, boxes, "mask_edge")
    add(region(ctx, idx, "BACKGROUND_CONTROL", "mask_edge_background_same_area", "same_area_background_control", "same_area_axis_aligned_background", mx, my, ctx.width, ctx.height, 0.0, source_role="background_control", gt_overlap_allowed="false", background_source=source))

    for name in ["linear_structure_background_same_area", "known_non_vehicle_same_area"]:
        nx, ny, source_id = n005[name]
        cx, cy = move_until_no_vehicle_overlap(ctx, (nx, ny), (1.0, 0.0), ctx.width, ctx.height, 0.0, boxes)
        add(region(ctx, idx, "BACKGROUND_CONTROL", name, "same_area_background_control", "same_area_n005_coordinate_control", cx, cy, ctx.width, ctx.height, 0.0, source_role="background_control", gt_overlap_allowed="false", background_source=f"N005_component:{source_id}"))

    return specs


def draw_polygon_mask(spec: RegionSpec) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    polys = [spec.outer_polygon]
    if spec.inner_polygon is not None:
        polys.append(spec.inner_polygon)
    x1, y1, x2, y2 = polygon_bounds(polys)
    w = x2 - x1 + 1
    h = y2 - y1 + 1
    mask_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask_img)
    outer = [(x - x1, y - y1) for x, y in spec.outer_polygon]
    draw.polygon(outer, fill=255)
    if spec.inner_polygon is not None:
        inner = [(x - x1, y - y1) for x, y in spec.inner_polygon]
        draw.polygon(inner, fill=0)
    return np.asarray(mask_img, dtype=bool), (x1, y1, x2, y2)


def connected_component_count(mask: np.ndarray, values: np.ndarray, peak_threshold: float) -> tuple[int, int]:
    if mask.size == 0 or not bool(mask.any()):
        return 0, 0
    visited = np.zeros(mask.shape, dtype=bool)
    ys, xs = np.nonzero(mask)
    component_count = 0
    peak_count = 0
    height, width = mask.shape
    for start_y, start_x in zip(ys.tolist(), xs.tolist()):
        if visited[start_y, start_x]:
            continue
        component_count += 1
        stack = [(start_x, start_y)]
        visited[start_y, start_x] = True
        local_peak = 0.0
        while stack:
            x, y = stack.pop()
            local_peak = max(local_peak, float(values[y, x]))
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if visited[ny, nx] or not mask[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    stack.append((nx, ny))
        if local_peak >= peak_threshold:
            peak_count += 1
    return component_count, peak_count


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    order = np.argsort(values)
    ordered_values = values[order]
    ordered_weights = weights[order]
    total = float(ordered_weights.sum())
    if total <= 1e-9:
        return float(np.quantile(values, q))
    cum = np.cumsum(ordered_weights)
    idx = int(np.searchsorted(cum, q * total, side="left"))
    idx = min(max(idx, 0), len(ordered_values) - 1)
    return float(ordered_values[idx])


def safe_ratio(a: float, b: float) -> str:
    if abs(b) <= 1e-9:
        return ""
    return fmt(a / b)


def feature_row(spec: RegionSpec, ctx: GtContext, image: np.ndarray, frame_thresholds: Mapping[str, float]) -> dict[str, Any]:
    mask, (x1, y1, x2, y2) = draw_polygon_mask(spec)
    crop = image[y1 : y2 + 1, x1 : x2 + 1]
    if crop.shape != mask.shape:
        min_h = min(crop.shape[0], mask.shape[0])
        min_w = min(crop.shape[1], mask.shape[1])
        crop = crop[:min_h, :min_w]
        mask = mask[:min_h, :min_w]
    values = crop[mask]
    area = int(values.size)
    if area == 0:
        return empty_feature_row(spec, ctx, x1, y1, x2, y2)

    ys_local, xs_local = np.nonzero(mask)
    xs = xs_local.astype(float) + x1
    ys = ys_local.astype(float) + y1
    weights = np.maximum(values.astype(float), 0.0)
    weight_sum = float(weights.sum())
    if weight_sum <= 1e-9:
        centroid_x = float(xs.mean())
        centroid_y = float(ys.mean())
    else:
        centroid_x = float(np.average(xs, weights=weights))
        centroid_y = float(np.average(ys, weights=weights))

    rel_x = xs - ctx.cx
    rel_y = ys - ctx.cy
    range_offsets = rel_x * ctx.range_unit[0] + rel_y * ctx.range_unit[1]
    az_offsets = rel_x * ctx.azimuth_unit[0] + rel_y * ctx.azimuth_unit[1]
    long_offsets = rel_x * ctx.long_unit[0] + rel_y * ctx.long_unit[1]

    high_threshold = frame_thresholds["high_energy_threshold"]
    peak_threshold = frame_thresholds["peak_threshold"]
    high = values >= high_threshold
    high_mask = np.zeros(mask.shape, dtype=bool)
    high_mask[ys_local[high], xs_local[high]] = True
    component_count, peak_count = connected_component_count(high_mask, crop, peak_threshold)
    high_count = int(high.sum())
    high_values = values[high].astype(float)
    high_range = range_offsets[high]
    high_az = az_offsets[high]
    high_weights = np.maximum(high_values, 1.0)
    if high_count > 0:
        range_support = float(high_range.max() - high_range.min())
        az_support = float(high_az.max() - high_az.min())
        range_energy90 = weighted_quantile(high_range, high_weights, 0.95) - weighted_quantile(high_range, high_weights, 0.05)
        az_energy90 = weighted_quantile(high_az, high_weights, 0.95) - weighted_quantile(high_az, high_weights, 0.05)
        range_second = 4.0 * math.sqrt(max(float(np.average((high_range - np.average(high_range, weights=high_weights)) ** 2, weights=high_weights)), 0.0))
        az_second = 4.0 * math.sqrt(max(float(np.average((high_az - np.average(high_az, weights=high_weights)) ** 2, weights=high_weights)), 0.0))
        coords = np.column_stack([xs[high] - xs[high].mean(), ys[high] - ys[high].mean()])
    else:
        range_support = az_support = range_energy90 = az_energy90 = range_second = az_second = 0.0
        coords = np.column_stack([xs - xs.mean(), ys - ys.mean()])
    if coords.shape[0] >= 3:
        cov = np.cov(coords, rowvar=False)
        eigvals, eigvecs = np.linalg.eigh(cov)
        order = np.argsort(eigvals)[::-1]
        eigvec = eigvecs[:, order[0]]
        principal_axis = math.degrees(math.atan2(float(eigvec[1]), float(eigvec[0])))
    else:
        principal_axis = 0.0

    near_energy = float(values[range_offsets < 0].sum())
    far_energy = float(values[range_offsets >= 0].sum())
    rear_energy = float(values[long_offsets < 0].sum())
    front_energy = float(values[long_offsets >= 0].sum())
    inside_gt = (xs >= ctx.bbox[0]) & (xs <= ctx.bbox[2]) & (ys >= ctx.bbox[1]) & (ys <= ctx.bbox[3])
    inside_energy = float(values[inside_gt].sum())
    outside_energy = float(values[~inside_gt].sum())
    zero_count = int(np.sum(values <= 0))
    boundary_pixels = int(np.sum((xs <= 0) | (xs >= SAR_WIDTH - 1) | (ys <= 0) | (ys >= SAR_HEIGHT - 1)))
    area_p0 = area * P0_PX_TO_M * P0_PX_TO_M
    centroid_rel = (centroid_x - ctx.cx, centroid_y - ctx.cy)
    centroid_range = dot(centroid_rel, ctx.range_unit)
    centroid_az = dot(centroid_rel, ctx.azimuth_unit)
    observation_status = "fully_observed"
    if boundary_pixels > 0:
        observation_status = "image_boundary_censored"
    if zero_count / area > 0.15:
        observation_status = "mask_censored"

    return {
        "region_id": spec.region_id,
        "pair_id": spec.pair_id,
        "sar_frame": spec.sar_frame,
        "family": spec.family,
        "variant": spec.variant,
        "comparison_group": spec.comparison_group,
        "area_ratio_to_gt": fmt(spec.area_ratio_to_gt),
        "offset_axis": spec.offset_axis,
        "offset_value": fmt(spec.offset_value),
        "offset_unit": spec.offset_unit,
        "scale_ratio": fmt(spec.scale_ratio),
        "rotation_relative_to_gt_deg": fmt(spec.rotation_relative_to_gt_deg),
        "region_area_px": area,
        "region_area_m2": "",
        "region_area_p0_convention_m2": fmt(area_p0),
        "total_energy": fmt(float(values.sum())),
        "mean_energy": fmt(float(values.mean())),
        "median_energy": fmt(float(np.median(values))),
        "energy_std": fmt(float(values.std())),
        "peak_energy": fmt(float(values.max())),
        "energy_quantile_90": fmt(float(np.percentile(values, 90))),
        "energy_quantile_95": fmt(float(np.percentile(values, 95))),
        "energy_quantile_99": fmt(float(np.percentile(values, 99))),
        "high_energy_threshold": fmt(high_threshold),
        "high_energy_pixel_count": high_count,
        "high_energy_pixel_fraction": fmt(high_count / area),
        "response_occupancy_ratio": fmt(high_count / area),
        "component_count": component_count,
        "component_count_per_m2": "",
        "component_count_per_p0_convention_m2": fmt(component_count / area_p0 if area_p0 > 0 else 0.0),
        "peak_count": peak_count,
        "peak_count_per_m2": "",
        "peak_count_per_p0_convention_m2": fmt(peak_count / area_p0 if area_p0 > 0 else 0.0),
        "energy_centroid_x": fmt(centroid_x),
        "energy_centroid_y": fmt(centroid_y),
        "energy_centroid_range_px": fmt(centroid_range),
        "energy_centroid_azimuth_px": fmt(centroid_az),
        "energy_centroid_range_m": "",
        "energy_centroid_azimuth_m": "",
        "energy_centroid_range_p0_convention_m": fmt(centroid_range * P0_PX_TO_M),
        "energy_centroid_azimuth_p0_convention_m": fmt(centroid_az * P0_PX_TO_M),
        "principal_axis_deg": fmt(principal_axis),
        "principal_axis_minus_gt_storage_axis_deg": fmt(angle_diff_deg(principal_axis, 0.0)),
        "principal_axis_minus_local_range_axis_deg": fmt(angle_diff_deg(principal_axis, axis_angle_deg(ctx.range_unit))),
        "range_support_width_px": fmt(range_support),
        "azimuth_support_width_px": fmt(az_support),
        "range_energy90_width_px": fmt(range_energy90),
        "azimuth_energy90_width_px": fmt(az_energy90),
        "range_second_moment_width_px": fmt(range_second),
        "azimuth_second_moment_width_px": fmt(az_second),
        "range_support_width_m": "",
        "azimuth_support_width_m": "",
        "range_energy90_width_m": "",
        "azimuth_energy90_width_m": "",
        "range_second_moment_width_m": "",
        "azimuth_second_moment_width_m": "",
        "range_support_width_p0_convention_m": fmt(range_support * P0_PX_TO_M),
        "azimuth_support_width_p0_convention_m": fmt(az_support * P0_PX_TO_M),
        "range_energy90_width_p0_convention_m": fmt(range_energy90 * P0_PX_TO_M),
        "azimuth_energy90_width_p0_convention_m": fmt(az_energy90 * P0_PX_TO_M),
        "near_far_energy_ratio": safe_ratio(near_energy, far_energy),
        "front_rear_energy_ratio": safe_ratio(front_energy, rear_energy),
        "inside_gt_pixel_fraction": fmt(float(inside_gt.sum()) / area),
        "inside_gt_energy_fraction": fmt(inside_energy / max(float(values.sum()), 1e-9)),
        "inside_ring_energy_ratio": safe_ratio(inside_energy, outside_energy),
        "boundary_contact_ratio": fmt(boundary_pixels / area),
        "mask_contact_ratio": fmt(zero_count / area),
        "visible_fraction": fmt(1.0 - zero_count / area),
        "metric_extent_reliable": "false",
        "observation_status": observation_status,
        "crop_bbox": f"{x1},{y1},{x2},{y2}",
        "mask_definition": "zero_value_proxy_only",
        "gt_file_opened_for_region_generation": "true",
        "final_detection_label": "",
    }


def empty_feature_row(spec: RegionSpec, ctx: GtContext, x1: int, y1: int, x2: int, y2: int) -> dict[str, Any]:
    row = {field: "" for field in FEATURE_FIELDS}
    row.update(
        {
            "region_id": spec.region_id,
            "pair_id": spec.pair_id,
            "sar_frame": spec.sar_frame,
            "family": spec.family,
            "variant": spec.variant,
            "comparison_group": spec.comparison_group,
            "region_area_px": 0,
            "metric_extent_reliable": "false",
            "observation_status": "unknown_incomplete",
            "crop_bbox": f"{x1},{y1},{x2},{y2}",
            "mask_definition": "zero_value_proxy_only",
            "gt_file_opened_for_region_generation": "true",
        }
    )
    return row


def metric_coordinate_mapping_rows() -> list[dict[str, Any]]:
    return [
        {"field": "radar_origin_in_image", "status": "AVAILABLE_AS_FAN_CENTER", "value": f"{FAN_CENTER_X},{FAN_CENTER_Y}", "source": rel(SCENE_CONFIG), "consequence": "local pixel range axis can be defined from fan center to GT center"},
        {"field": "pixel_to_range_meter_mapping", "status": "UNRESOLVED", "value": "", "source": "not_found_in_repo_or_config", "consequence": "true range_m fields are NOT_EVALUABLE"},
        {"field": "pixel_to_azimuth_meter_mapping", "status": "UNRESOLVED", "value": "", "source": "not_found_in_repo_or_config", "consequence": "true azimuth_m fields are NOT_EVALUABLE"},
        {"field": "range_axis_direction", "status": "AVAILABLE_AS_LOCAL_PIXEL_AXIS", "value": "fan_center_to_gt_center_per_frame", "source": rel(SCENE_CONFIG), "consequence": "pixel-domain local range offsets are available"},
        {"field": "azimuth_axis_direction", "status": "AVAILABLE_AS_LOCAL_PIXEL_AXIS", "value": "perpendicular_to_local_range_axis", "source": rel(SCENE_CONFIG), "consequence": "pixel-domain local azimuth offsets are available"},
        {"field": "image_projection_type", "status": "UNRESOLVED", "value": "", "source": "not_found_in_repo_or_config", "consequence": "absolute metric physical claims blocked"},
        {"field": "sar_resolution_range_m", "status": "UNRESOLVED", "value": "", "source": "not_found_in_repo_or_config", "consequence": "resolution-corrected extent is NOT_EVALUABLE"},
        {"field": "sar_resolution_azimuth_m", "status": "UNRESOLVED", "value": "", "source": "not_found_in_repo_or_config", "consequence": "resolution-corrected extent is NOT_EVALUABLE"},
        {"field": "mask_definition", "status": "UNRESOLVED_ZERO_VALUE_PROXY_ONLY", "value": "image_pixel_value==0", "source": "SAR PNG observation", "consequence": "mask censoring is proxy-only"},
        {"field": "gt_orientation_source", "status": "UNRESOLVED_AXIS_ALIGNED_BBOX_ONLY", "value": "no_vehicle_heading_field", "source": rel(PAIR_CSV), "consequence": "front/rear and long/short axes are storage-axis tests"},
        {"field": "vehicle_dimension_metadata", "status": "UNRESOLVED_DATASET_CONDITIONED_GT_STATS_ONLY", "value": "", "source": rel(PAIR_CSV), "consequence": "vehicle body size reference is dataset-conditioned"},
        {"field": "p0_px_to_m_convention", "status": "P0_CONVENTION_ONLY_NOT_VALIDATED_METRIC_MAPPING", "value": P0_PX_TO_M, "source": rel(P0_PARAMS), "consequence": "p0_convention_m columns are not true meters"},
    ]


def quantiles(values: Sequence[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    return {
        "count": float(len(arr)),
        "min": float(np.min(arr)),
        "q10": float(np.quantile(arr, 0.10)),
        "median": float(np.quantile(arr, 0.50)),
        "q90": float(np.quantile(arr, 0.90)),
        "max": float(np.max(arr)),
    }


def body_size_rows(contexts: Sequence[GtContext]) -> list[dict[str, Any]]:
    metrics = {
        "gt_width_px": [ctx.width for ctx in contexts],
        "gt_height_px": [ctx.height for ctx in contexts],
        "gt_area_px2": [ctx.area for ctx in contexts],
        "gt_aspect_ratio": [ctx.width / max(ctx.height, 1e-9) for ctx in contexts],
        "gt_projected_range_extent_px": [ctx.range_extent_px for ctx in contexts],
        "gt_projected_azimuth_extent_px": [ctx.azimuth_extent_px for ctx in contexts],
    }
    rows = []
    for name, values in metrics.items():
        q = quantiles(values)
        rows.append(
            {
                "reference_id": name,
                "source": "dataset_conditioned_gt_statistics",
                "count": int(q["count"]),
                "min_px": fmt(q["min"]),
                "q10_px": fmt(q["q10"]),
                "median_px": fmt(q["median"]),
                "q90_px": fmt(q["q90"]),
                "max_px": fmt(q["max"]),
                "median_m": "",
                "median_p0_convention_m": fmt(q["median"] * P0_PX_TO_M) if "area" not in name and "ratio" not in name else "",
                "median_p0_convention_m2": fmt(q["median"] * P0_PX_TO_M * P0_PX_TO_M) if "area" in name else "",
                "metric_status": "NOT_EVALUABLE_TRUE_METERS",
                "notes": "GT axis-aligned bbox statistics; not external vehicle dimension metadata.",
            }
        )
    return rows


def gt_geometry_rows(contexts: Sequence[GtContext]) -> list[dict[str, Any]]:
    rows = []
    for ctx in contexts:
        rows.append(
            {
                "pair_id": ctx.pair_id,
                "sar_frame": ctx.sar_frame,
                "optical_frame": ctx.optical_frame,
                "sar_gt_id": ctx.sar_gt_id,
                "bbox": ",".join(fmt(v) for v in ctx.bbox),
                "center_x": fmt(ctx.cx),
                "center_y": fmt(ctx.cy),
                "gt_width_px": fmt(ctx.width),
                "gt_height_px": fmt(ctx.height),
                "gt_area_px2": fmt(ctx.area),
                "gt_aspect_ratio": fmt(ctx.width / max(ctx.height, 1e-9)),
                "local_range_unit_x": fmt(ctx.range_unit[0]),
                "local_range_unit_y": fmt(ctx.range_unit[1]),
                "local_azimuth_unit_x": fmt(ctx.azimuth_unit[0]),
                "local_azimuth_unit_y": fmt(ctx.azimuth_unit[1]),
                "local_range_axis_angle_deg": fmt(axis_angle_deg(ctx.range_unit)),
                "gt_projected_range_extent_px": fmt(ctx.range_extent_px),
                "gt_projected_azimuth_extent_px": fmt(ctx.azimuth_extent_px),
                "gt_body_length_m": "",
                "gt_body_width_m": "",
                "gt_body_area_m2": "",
                "gt_body_length_p0_convention_m": fmt(max(ctx.width, ctx.height) * P0_PX_TO_M),
                "gt_body_width_p0_convention_m": fmt(min(ctx.width, ctx.height) * P0_PX_TO_M),
                "gt_body_area_p0_convention_m2": fmt(ctx.area * P0_PX_TO_M * P0_PX_TO_M),
                "gt_orientation_deg": "",
                "gt_orientation_source": "UNRESOLVED_AXIS_ALIGNED_BBOX_ONLY",
                "visibility_state": ctx.visibility_state,
                "usable_for_calibration": ctx.usable_for_calibration,
                "blocked_reason": ctx.blocked_reason,
            }
        )
    return rows


def region_manifest_row(spec: RegionSpec, ctx: GtContext) -> dict[str, Any]:
    centroid_rel = (spec.center_x - ctx.cx, spec.center_y - ctx.cy)
    return {
        "region_id": spec.region_id,
        "pair_id": spec.pair_id,
        "sar_frame": spec.sar_frame,
        "family": spec.family,
        "variant": spec.variant,
        "comparison_group": spec.comparison_group,
        "geometry_basis": spec.geometry_basis,
        "center_x": fmt(spec.center_x),
        "center_y": fmt(spec.center_y),
        "width_px": fmt(spec.width_px),
        "height_px": fmt(spec.height_px),
        "angle_deg": fmt(spec.angle_deg),
        "area_ratio_to_gt": fmt(spec.area_ratio_to_gt),
        "offset_axis": spec.offset_axis,
        "offset_value": fmt(spec.offset_value),
        "offset_unit": spec.offset_unit,
        "offset_px_local_range": fmt(dot(centroid_rel, ctx.range_unit)),
        "offset_px_local_azimuth": fmt(dot(centroid_rel, ctx.azimuth_unit)),
        "offset_p0_convention_m_local_range": fmt(dot(centroid_rel, ctx.range_unit) * P0_PX_TO_M),
        "offset_p0_convention_m_local_azimuth": fmt(dot(centroid_rel, ctx.azimuth_unit) * P0_PX_TO_M),
        "scale_ratio": fmt(spec.scale_ratio),
        "rotation_relative_to_gt_deg": fmt(spec.rotation_relative_to_gt_deg),
        "source_role": spec.source_role,
        "interpretation_scope": spec.interpretation_scope,
        "gt_overlap_allowed": spec.gt_overlap_allowed,
        "background_source": spec.background_source,
        "outer_polygon": ";".join(f"{fmt(x)}:{fmt(y)}" for x, y in spec.outer_polygon),
        "inner_polygon": "" if spec.inner_polygon is None else ";".join(f"{fmt(x)}:{fmt(y)}" for x, y in spec.inner_polygon),
        "metric_mapping_status": "NOT_READY",
        "pixel_to_meter_status": "P0_CONVENTION_ONLY",
    }


def frame_thresholds(image: np.ndarray) -> dict[str, float]:
    nonzero = image[image > 0]
    source = nonzero if nonzero.size else image.reshape(-1)
    return {
        "high_energy_threshold": float(max(np.mean(source) + np.std(source), np.percentile(source, 95))),
        "peak_threshold": float(np.percentile(source, 99)),
    }


def build_visuals(
    contexts_by_frame: Mapping[int, GtContext],
    regions: Sequence[RegionSpec],
    feature_rows: Sequence[Mapping[str, Any]],
    cache: dict[int, np.ndarray],
) -> list[dict[str, Any]]:
    by_frame: dict[int, list[RegionSpec]] = {}
    for spec in regions:
        by_frame.setdefault(spec.sar_frame, []).append(spec)
    visual_rows: list[dict[str, Any]] = []

    visual_defs = [
        ("axes_gt_frame371", 371, ["GT_ORIGINAL"], "GT and local range/azimuth axes", "坐标方向可见；米制比例未被验证，只能读作局部像素轴。"),
        ("scale_regions_frame371", 371, ["SCALE"], "same-center scale regions", "缩放区域覆盖合理，但响应随面积扩大也会纳入背景，不能直接当作车辆尺度证明。"),
        ("translation_regions_frame376", 376, ["TRANSLATION"], "range/azimuth/image translations", "平移网格显示高响应并非只在 GT 中心；需用衰减曲面而非单点峰值解释。"),
        ("rotation_regions_frame381", 381, ["ROTATION"], "rotation perturbations", "旋转扰动可见，但 GT 未提供真实车头方向，角度只能解释为图像轴扰动。"),
        ("directional_expansion_frame386", 386, ["DIRECTIONAL_EXPANSION"], "near/far/azimuth/storage expansion", "非对称扩展可见，新增区域含背景响应，不能自动解释为车体扩散。"),
        ("ring_frame394", 394, ["RING"], "GT expansion rings", "外环包含明显邻近背景，环带对照是必要的负证据。"),
        ("background_controls_frame371", 371, ["BACKGROUND_CONTROL"], "same-area background controls", "同面积背景控制能产生可观能量，是物理可分性 gate 的主要压力。"),
        ("mask_contact_frame371", 371, ["BACKGROUND_CONTROL"], "zero-valued proxy mask contact", "mask-edge 控制只说明 zero-valued proxy 接触，不能作为官方 mask 结论。"),
    ]
    for visual_id, frame, families, title, conclusion in visual_defs:
        selected = [spec for spec in by_frame.get(frame, []) if spec.family in families]
        if families == ["SCALE"]:
            selected = [spec for spec in selected if "uniform_scale" in spec.variant][:6]
        if families == ["TRANSLATION"]:
            selected = [spec for spec in selected if spec.offset_axis in {"local_range", "local_azimuth"} and abs(spec.offset_value) in {0.25, 0.5, 1.0}]
        if families == ["ROTATION"]:
            selected = [spec for spec in selected if spec.variant in {"image_axis_rotation_-45", "image_axis_rotation_+0", "image_axis_rotation_+45", "image_axis_rotation_+90"}]
        if families == ["BACKGROUND_CONTROL"] and visual_id == "mask_contact_frame371":
            selected = [spec for spec in selected if spec.variant == "mask_edge_background_same_area"]
        path = render_overlay(frame, contexts_by_frame[frame], selected, cache, visual_id, title)
        visual_rows.append(visual_row(visual_id, frame, path, title, conclusion))

    plot_path = render_scale_plot(feature_rows)
    visual_rows.append(visual_row("scale_curve_mean_energy", "", plot_path, "scale response curve", "尺度曲线显示总能量随区域变大容易增加；必须优先看单位面积和环带对照。"))
    heat_path = render_translation_heatmap(feature_rows)
    visual_rows.append(visual_row("translation_heatmap_mean_energy", "", heat_path, "translation response heatmap", "平移热图用于检查峰值是否偏离 GT；不能作为选择器。"))
    rot_path = render_rotation_plot(feature_rows)
    visual_rows.append(visual_row("rotation_curve_principal_axis", "", rot_path, "rotation/principal-axis curve", "主轴角与 GT 存储轴不稳定一致，真实车辆方向仍未解析。"))
    n005_path = render_n005_panel(cache)
    visual_rows.append(visual_row("n005_hard_negative_panel", 249, n005_path, "N005 known non-vehicle hard negative", "N005 强散射/线性结构能形成车辆尺度相近的局部响应，是 hard negative。"))
    bg_bar_path = render_background_bar_plot(feature_rows)
    visual_rows.append(visual_row("gt_vs_background_hard_negative_bar", "", bg_bar_path, "GT versus same-area hard-negative/background contrast", "强散射背景的平均能量可达到或超过 GT 区域，不能宣称车辆区域稳定可分。"))
    axis_path = render_principal_axis_panel(feature_rows, contexts_by_frame, cache)
    visual_rows.append(visual_row("principal_axis_vs_gt_direction_frame394", 394, axis_path, "principal axis versus GT storage axis", "SAR 主轴与 GT 存储轴存在明显差异；不能预设二者一致。"))
    return visual_rows


def visual_row(visual_id: str, frame: Any, path: Path, requirement: str, conclusion: str) -> dict[str, Any]:
    return {
        "visual_id": visual_id,
        "sar_frame": frame,
        "diagnostic_png": rel(path),
        "review_requirement": requirement,
        "review_status": "generated_and_opened_for_e0_review",
        "reviewer_conclusion_cn": conclusion,
        "commit_policy": "do_not_commit_png_outputs",
    }


def render_overlay(frame: int, ctx: GtContext, specs: Sequence[RegionSpec], cache: dict[int, np.ndarray], visual_id: str, title: str) -> Path:
    image = Image.fromarray(load_image(frame, cache).astype(np.uint8)).convert("RGB")
    polys = [rect_polygon(ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0)]
    for spec in specs:
        polys.append(spec.outer_polygon)
        if spec.inner_polygon is not None:
            polys.append(spec.inner_polygon)
    x1, y1, x2, y2 = polygon_bounds(polys)
    margin = 90
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(SAR_WIDTH - 1, x2 + margin)
    y2 = min(SAR_HEIGHT - 1, y2 + margin)
    crop = image.crop((x1, y1, x2 + 1, y2 + 1))
    draw = ImageDraw.Draw(crop)
    colors = {
        "GT_ORIGINAL": (0, 255, 0),
        "SCALE": (255, 190, 0),
        "TRANSLATION": (0, 200, 255),
        "ROTATION": (255, 0, 255),
        "DIRECTIONAL_EXPANSION": (255, 120, 0),
        "RING": (200, 200, 255),
        "BACKGROUND_CONTROL": (255, 60, 60),
    }
    for spec in specs:
        color = colors.get(spec.family, (255, 255, 255))
        poly = [(x - x1, y - y1) for x, y in spec.outer_polygon]
        draw.line(poly + [poly[0]], fill=color, width=2)
        if spec.inner_polygon is not None:
            inner = [(x - x1, y - y1) for x, y in spec.inner_polygon]
            draw.line(inner + [inner[0]], fill=(120, 120, 255), width=2)
    gt = [(x - x1, y - y1) for x, y in rect_polygon(ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0)]
    draw.line(gt + [gt[0]], fill=(0, 255, 0), width=3)
    center = (ctx.cx - x1, ctx.cy - y1)
    draw.line([center, (center[0] + ctx.range_unit[0] * 70, center[1] + ctx.range_unit[1] * 70)], fill=(0, 255, 255), width=3)
    draw.line([center, (center[0] + ctx.azimuth_unit[0] * 70, center[1] + ctx.azimuth_unit[1] * 70)], fill=(255, 255, 0), width=3)
    draw.rectangle((0, 0, min(crop.width, 700), 46), fill=(0, 0, 0))
    draw.text((6, 6), f"{title} | SAR {frame} | GT {fmt(ctx.width)}x{fmt(ctx.height)} px | p0 {fmt(ctx.width*P0_PX_TO_M)}x{fmt(ctx.height*P0_PX_TO_M)} convention m", fill=(255, 255, 255))
    path = VISUAL_DIR / f"{visual_id}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(path)
    return path


def render_scale_plot(feature_rows: Sequence[Mapping[str, Any]]) -> Path:
    rows = [row for row in feature_rows if row.get("family") == "SCALE" and str(row.get("variant", "")).startswith("uniform_scale")]
    grouped: dict[float, list[float]] = {}
    for row in rows:
        try:
            scale = float(str(row["variant"]).rsplit("_", 1)[1])
        except Exception:
            continue
        grouped.setdefault(scale, []).append(parse_float(row.get("mean_energy")))
    points = [(scale, float(np.mean(vals))) for scale, vals in sorted(grouped.items())]
    return render_line_plot(points, VISUAL_DIR / "e0_scale_curve_mean_energy.png", "uniform scale", "mean energy")


def render_rotation_plot(feature_rows: Sequence[Mapping[str, Any]]) -> Path:
    rows = [row for row in feature_rows if row.get("family") == "ROTATION"]
    grouped: dict[float, list[float]] = {}
    for row in rows:
        variant = str(row.get("variant", ""))
        try:
            angle = float(variant.rsplit("_", 1)[1])
        except Exception:
            continue
        grouped.setdefault(angle, []).append(abs(parse_float(row.get("principal_axis_minus_gt_storage_axis_deg"))))
    points = [(angle, float(np.mean(vals))) for angle, vals in sorted(grouped.items())]
    return render_line_plot(points, VISUAL_DIR / "e0_rotation_principal_axis_curve.png", "rotation angle", "abs principal-axis delta")


def render_line_plot(points: Sequence[tuple[float, float]], path: Path, x_label: str, y_label: str) -> Path:
    width, height = 900, 520
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((70, 40, width - 40, height - 70), outline=(0, 0, 0), width=2)
    if points:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        if abs(xmax - xmin) < 1e-9:
            xmax += 1
        if abs(ymax - ymin) < 1e-9:
            ymax += 1
        coords = []
        for x, y in points:
            px = 70 + (x - xmin) / (xmax - xmin) * (width - 110)
            py = height - 70 - (y - ymin) / (ymax - ymin) * (height - 110)
            coords.append((px, py))
        if len(coords) >= 2:
            draw.line(coords, fill=(20, 90, 200), width=3)
        for px, py in coords:
            draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(20, 90, 200))
    draw.text((80, 10), f"{x_label} vs {y_label}", fill=(0, 0, 0))
    draw.text((width // 2 - 60, height - 35), x_label, fill=(0, 0, 0))
    draw.text((8, height // 2), y_label, fill=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def render_translation_heatmap(feature_rows: Sequence[Mapping[str, Any]]) -> Path:
    rows = [
        row
        for row in feature_rows
        if row.get("family") == "TRANSLATION" and row.get("offset_axis") in {"local_range", "local_azimuth"}
    ]
    values: dict[tuple[str, float], list[float]] = {}
    for row in rows:
        key = (str(row.get("offset_axis")), parse_float(row.get("offset_value")))
        values.setdefault(key, []).append(parse_float(row.get("mean_energy")))
    offsets = [-1.0, -0.5, -0.25, 0.25, 0.5, 1.0]
    axes = ["local_range", "local_azimuth"]
    matrix = np.zeros((len(axes), len(offsets)), dtype=float)
    for i, axis in enumerate(axes):
        for j, offset in enumerate(offsets):
            vals = values.get((axis, offset), [0.0])
            matrix[i, j] = float(np.mean(vals))
    vmax = float(matrix.max()) if matrix.size else 1.0
    vmin = float(matrix.min()) if matrix.size else 0.0
    cell_w, cell_h = 120, 110
    img = Image.new("RGB", (cell_w * len(offsets) + 180, cell_h * len(axes) + 120), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 15), "Translation mean-energy heatmap (pixel/GT-normalized control, not selector)", fill=(0, 0, 0))
    for i, axis in enumerate(axes):
        draw.text((15, 70 + i * cell_h + 35), axis, fill=(0, 0, 0))
        for j, offset in enumerate(offsets):
            value = matrix[i, j]
            t = 0.0 if vmax == vmin else (value - vmin) / (vmax - vmin)
            color = (int(255 * t), int(60 + 120 * (1 - t)), int(255 * (1 - t)))
            x = 150 + j * cell_w
            y = 60 + i * cell_h
            draw.rectangle((x, y, x + cell_w - 5, y + cell_h - 5), fill=color, outline=(0, 0, 0))
            draw.text((x + 8, y + 8), f"{offset:+.2f}", fill=(0, 0, 0))
            draw.text((x + 8, y + 38), fmt(value, 3), fill=(0, 0, 0))
    path = VISUAL_DIR / "e0_translation_mean_energy_heatmap.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def render_n005_panel(cache: dict[int, np.ndarray]) -> Path:
    frame = 249
    image = Image.fromarray(load_image(frame, cache).astype(np.uint8)).convert("RGB")
    rows = [row for row in read_csv(P0_COMPONENTS) if row.get("segment_id") == "GM017_N005_BACKGROUND_CONTROL"]
    rows = sorted(rows, key=lambda row: parse_float(row.get("integrated_energy")), reverse=True)[:20]
    draw = ImageDraw.Draw(image)
    for row in rows:
        parts = [parse_float(v) for v in row["bbox"].split(",")]
        color = (255, 80, 80) if parse_float(row.get("aspect_ratio")) < 4 else (255, 180, 0)
        draw.rectangle(tuple(parts), outline=color, width=2)
    crop = image.crop((0, 700, SAR_WIDTH, SAR_HEIGHT))
    crop = crop.resize((1200, int(1200 * crop.height / crop.width)))
    draw = ImageDraw.Draw(crop)
    draw.rectangle((0, 0, 760, 38), fill=(0, 0, 0))
    draw.text((6, 6), "N005 non-vehicle temporal window, SAR249, high-response components", fill=(255, 255, 255))
    path = VISUAL_DIR / "e0_n005_hard_negative_panel.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(path)
    return path


def render_background_bar_plot(feature_rows: Sequence[Mapping[str, Any]]) -> Path:
    classes = [
        ("GT", [row for row in feature_rows if row.get("family") == "GT_ORIGINAL"]),
        ("N005", [row for row in feature_rows if row.get("variant") == "known_non_vehicle_same_area"]),
        ("linear", [row for row in feature_rows if row.get("variant") == "linear_structure_background_same_area"]),
        ("strong", [row for row in feature_rows if row.get("variant") == "strong_scatterer_background_same_area"]),
        ("far_bg", [row for row in feature_rows if row.get("variant") == "far_background_same_area"]),
    ]
    values = [(name, float(np.mean([parse_float(row.get("mean_energy")) for row in rows])) if rows else 0.0) for name, rows in classes]
    width, height = 900, 520
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 18), "GT vs same-area hard-negative/background mean energy", fill=(0, 0, 0))
    x0, y0, plot_w, plot_h = 90, 70, 760, 360
    draw.rectangle((x0, y0, x0 + plot_w, y0 + plot_h), outline=(0, 0, 0), width=2)
    vmax = max([value for _, value in values] + [1.0])
    bar_w = plot_w // max(len(values), 1) - 24
    for idx, (name, value) in enumerate(values):
        x = x0 + 18 + idx * (plot_w // len(values))
        bar_h = int((value / vmax) * (plot_h - 30))
        y = y0 + plot_h - bar_h
        color = (30, 150, 80) if name == "GT" else (210, 80, 60)
        draw.rectangle((x, y, x + bar_w, y0 + plot_h), fill=color, outline=(0, 0, 0))
        draw.text((x, y0 + plot_h + 12), name, fill=(0, 0, 0))
        draw.text((x, max(y0 + 5, y - 22)), fmt(value, 2), fill=(0, 0, 0))
    draw.text((30, height - 45), "Bar chart is review evidence only; no ranking or selector is produced.", fill=(0, 0, 0))
    path = VISUAL_DIR / "e0_gt_vs_background_hard_negative_bar.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def render_principal_axis_panel(
    feature_rows: Sequence[Mapping[str, Any]],
    contexts_by_frame: Mapping[int, GtContext],
    cache: dict[int, np.ndarray],
) -> Path:
    gt_rows = [row for row in feature_rows if row.get("family") == "GT_ORIGINAL"]
    row = max(gt_rows, key=lambda item: abs(parse_float(item.get("principal_axis_minus_gt_storage_axis_deg"))))
    frame = parse_int(row["sar_frame"])
    ctx = contexts_by_frame[frame]
    image = Image.fromarray(load_image(frame, cache).astype(np.uint8)).convert("RGB")
    x1 = max(0, int(ctx.cx - 240))
    y1 = max(0, int(ctx.cy - 170))
    x2 = min(SAR_WIDTH - 1, int(ctx.cx + 240))
    y2 = min(SAR_HEIGHT - 1, int(ctx.cy + 170))
    crop = image.crop((x1, y1, x2 + 1, y2 + 1))
    draw = ImageDraw.Draw(crop)
    gt = [(x - x1, y - y1) for x, y in rect_polygon(ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0)]
    draw.line(gt + [gt[0]], fill=(0, 255, 0), width=3)
    principal = parse_float(row.get("principal_axis_deg"))
    rad = math.radians(principal)
    center = (parse_float(row.get("energy_centroid_x")) - x1, parse_float(row.get("energy_centroid_y")) - y1)
    draw.line([center, (center[0] + math.cos(rad) * 140, center[1] + math.sin(rad) * 140)], fill=(255, 0, 255), width=3)
    draw.line([center, (center[0] - math.cos(rad) * 140, center[1] - math.sin(rad) * 140)], fill=(255, 0, 255), width=3)
    draw.rectangle((0, 0, 760, 42), fill=(0, 0, 0))
    draw.text((6, 6), f"SAR {frame}: principal axis {fmt(principal)} deg, delta to GT storage {row.get('principal_axis_minus_gt_storage_axis_deg')} deg", fill=(255, 255, 255))
    path = VISUAL_DIR / "e0_principal_axis_vs_gt_storage_axis.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(path)
    return path


def write_pre_eval_seal(output_map: Mapping[str, Path]) -> None:
    generator_sha = sha256_file(Path(__file__))
    rows = []
    for key in CORE_GENERATION_KEYS:
        path = output_map[key]
        rows.append(
            {
                "artifact_key": key,
                "path": rel(path),
                "sha256": sha256_file(path),
                "row_count": row_count(path),
                "seal_phase": "e0_pre_eval_region_and_feature_freeze",
                "gt_allowed_at_creation": "true_for_region_geometry_generation",
                "code_commit_sha": git_output(["rev-parse", "HEAD"]),
                "generator_source_sha256": generator_sha,
                "allowed_inputs": "paired_gt_annotations;scene_config;sar_gray_frames;p0_n005_components",
                "forbidden_outputs": "selector;ranking;final_box;gt_modification;training",
            }
        )
    write_csv(output_map["pre_eval_seal"], rows, PRE_EVAL_SEAL_FIELDS)


def write_frozen_manifest(output_map: Mapping[str, Path], phase: str) -> None:
    rows = []
    for key, path in output_map.items():
        if path.exists() and key != "frozen_manifest":
            rows.append(
                {
                    "artifact_key": key,
                    "path": rel(path),
                    "sha256": sha256_file(path),
                    "row_count": row_count(path),
                    "phase": phase,
                    "notes": "PNG visuals are under ignored outputs/ and are not committed." if key == "visual_review_manifest" else "",
                }
            )
    write_csv(output_map["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def run_generation(output_map: Mapping[str, Path]) -> None:
    ensure_dirs()
    rows = target_rows()
    contexts = [make_context(row) for row in rows]
    contexts_by_frame = {ctx.sar_frame: ctx for ctx in contexts}
    boxes_by_frame = vehicle_boxes_by_frame()
    n005 = n005_component_controls()
    cache = image_cache()

    mapping_rows = metric_coordinate_mapping_rows()
    size_rows = body_size_rows(contexts)
    geometry_rows = gt_geometry_rows(contexts)
    write_csv(output_map["metric_coordinate_mapping"], mapping_rows, MAPPING_FIELDS)
    write_csv(output_map["vehicle_body_size_reference"], size_rows, BODY_SIZE_FIELDS)
    write_csv(output_map["gt_metric_geometry"], geometry_rows, GT_GEOMETRY_FIELDS)

    all_regions: list[RegionSpec] = []
    manifest_rows: list[dict[str, Any]] = []
    background_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    mask_audit_by_frame: dict[int, dict[str, Any]] = {}

    for ctx in contexts:
        image = load_image(ctx.sar_frame, cache)
        thresholds = frame_thresholds(image)
        frame_regions = build_regions_for_context(ctx, boxes_by_frame, n005, cache)
        all_regions.extend(frame_regions)
        for spec in frame_regions:
            manifest_rows.append(region_manifest_row(spec, ctx))
            if spec.family == "BACKGROUND_CONTROL":
                background_rows.append(
                    {
                        "region_id": spec.region_id,
                        "sar_frame": spec.sar_frame,
                        "background_type": spec.variant,
                        "center_x": fmt(spec.center_x),
                        "center_y": fmt(spec.center_y),
                        "same_area_as_gt": "true",
                        "overlaps_any_gm017_gt_aabb": str(any(bbox_intersects(polygon_aabb(spec.outer_polygon), box) for box in boxes_by_frame.get(ctx.sar_frame, []))).lower(),
                        "source": spec.background_source,
                        "gt_role": "negative_or_background_control",
                    }
                )
            feature_rows.append(feature_row(spec, ctx, image, thresholds))

        gt_feature = next(row for row in feature_rows if row["sar_frame"] == ctx.sar_frame and row["family"] == "GT_ORIGINAL")
        frame_zero_fraction = float(np.mean(image <= 0))
        censored = [row for row in feature_rows if row["sar_frame"] == ctx.sar_frame and row.get("observation_status") != "fully_observed"]
        mask_audit_by_frame[ctx.sar_frame] = {
            "sar_frame": ctx.sar_frame,
            "image_zero_fraction": fmt(frame_zero_fraction),
            "gt_visible_fraction": gt_feature["visible_fraction"],
            "gt_mask_contact_ratio": gt_feature["mask_contact_ratio"],
            "gt_boundary_contact_ratio": gt_feature["boundary_contact_ratio"],
            "censored_region_count": len(censored),
            "mask_definition": "UNRESOLVED_ZERO_VALUE_PROXY_ONLY",
            "metric_extent_reliable": "false",
            "notes": "Zero-valued pixels are an observed proxy only; no official SAR mask definition found.",
        }

    write_csv(output_map["region_perturbation_manifest"], manifest_rows, REGION_MANIFEST_FIELDS)
    write_csv(output_map["region_feature_table"], feature_rows, FEATURE_FIELDS)
    write_csv(output_map["background_control_manifest"], background_rows, BACKGROUND_FIELDS)
    write_csv(output_map["mask_censoring_audit"], list(mask_audit_by_frame.values()), MASK_AUDIT_FIELDS)
    visual_rows = build_visuals(contexts_by_frame, all_regions, feature_rows, cache)
    write_csv(output_map["visual_review_manifest"], visual_rows, VISUAL_FIELDS)
    write_pre_eval_seal(output_map)
    write_frozen_manifest(output_map, "e0_generation")
    print(f"E0 generation complete: regions={len(manifest_rows)} features={len(feature_rows)} visuals={len(visual_rows)}")


def verify_replay() -> None:
    ensure_dirs()
    resolved_replay = REPLAY_DIR.resolve()
    resolved_output = OUTPUT_DIR.resolve()
    if REPLAY_DIR.exists():
        if not resolved_replay.is_relative_to(resolved_output):
            raise RuntimeError(f"refusing to remove replay path outside output dir: {REPLAY_DIR}")
        shutil.rmtree(REPLAY_DIR)
    replay_outputs = {key: REPLAY_DIR / path.name for key, path in OUTPUTS.items()}
    run_generation(replay_outputs)
    results = []
    for key in CORE_GENERATION_KEYS:
        frozen = OUTPUTS[key]
        replay = replay_outputs[key]
        same = sha256_file(frozen) == sha256_file(replay)
        results.append(
            {
                "artifact_key": key,
                "frozen_sha256": sha256_file(frozen),
                "replay_sha256": sha256_file(replay),
                "status": "PASS" if same else "FAIL",
            }
        )
    status = "PASS" if all(row["status"] == "PASS" for row in results) else "FAIL"
    write_csv(OUTPUTS["replay_check"], results, REPLAY_FIELDS)
    write_frozen_manifest(OUTPUTS, "e0_replay_verified")
    print(f"FROZEN_REPLAY_IDENTICAL={status}")


MAPPING_FIELDS = ["field", "status", "value", "source", "consequence"]
BODY_SIZE_FIELDS = ["reference_id", "source", "count", "min_px", "q10_px", "median_px", "q90_px", "max_px", "median_m", "median_p0_convention_m", "median_p0_convention_m2", "metric_status", "notes"]
GT_GEOMETRY_FIELDS = [
    "pair_id", "sar_frame", "optical_frame", "sar_gt_id", "bbox", "center_x", "center_y", "gt_width_px", "gt_height_px", "gt_area_px2", "gt_aspect_ratio",
    "local_range_unit_x", "local_range_unit_y", "local_azimuth_unit_x", "local_azimuth_unit_y", "local_range_axis_angle_deg",
    "gt_projected_range_extent_px", "gt_projected_azimuth_extent_px", "gt_body_length_m", "gt_body_width_m", "gt_body_area_m2",
    "gt_body_length_p0_convention_m", "gt_body_width_p0_convention_m", "gt_body_area_p0_convention_m2", "gt_orientation_deg", "gt_orientation_source", "visibility_state", "usable_for_calibration", "blocked_reason",
]
REGION_MANIFEST_FIELDS = [
    "region_id", "pair_id", "sar_frame", "family", "variant", "comparison_group", "geometry_basis", "center_x", "center_y", "width_px", "height_px", "angle_deg", "area_ratio_to_gt",
    "offset_axis", "offset_value", "offset_unit", "offset_px_local_range", "offset_px_local_azimuth", "offset_p0_convention_m_local_range", "offset_p0_convention_m_local_azimuth",
    "scale_ratio", "rotation_relative_to_gt_deg", "source_role", "interpretation_scope", "gt_overlap_allowed", "background_source", "outer_polygon", "inner_polygon",
    "metric_mapping_status", "pixel_to_meter_status",
]
FEATURE_FIELDS = [
    "region_id", "pair_id", "sar_frame", "family", "variant", "comparison_group", "area_ratio_to_gt", "offset_axis", "offset_value", "offset_unit", "scale_ratio", "rotation_relative_to_gt_deg",
    "region_area_px", "region_area_m2", "region_area_p0_convention_m2",
    "total_energy", "mean_energy", "median_energy", "energy_std", "peak_energy", "energy_quantile_90", "energy_quantile_95", "energy_quantile_99",
    "high_energy_threshold", "high_energy_pixel_count", "high_energy_pixel_fraction", "response_occupancy_ratio", "component_count", "component_count_per_m2", "component_count_per_p0_convention_m2",
    "peak_count", "peak_count_per_m2", "peak_count_per_p0_convention_m2", "energy_centroid_x", "energy_centroid_y", "energy_centroid_range_px", "energy_centroid_azimuth_px",
    "energy_centroid_range_m", "energy_centroid_azimuth_m", "energy_centroid_range_p0_convention_m", "energy_centroid_azimuth_p0_convention_m",
    "principal_axis_deg", "principal_axis_minus_gt_storage_axis_deg", "principal_axis_minus_local_range_axis_deg",
    "range_support_width_px", "azimuth_support_width_px", "range_energy90_width_px", "azimuth_energy90_width_px", "range_second_moment_width_px", "azimuth_second_moment_width_px",
    "range_support_width_m", "azimuth_support_width_m", "range_energy90_width_m", "azimuth_energy90_width_m", "range_second_moment_width_m", "azimuth_second_moment_width_m",
    "range_support_width_p0_convention_m", "azimuth_support_width_p0_convention_m", "range_energy90_width_p0_convention_m", "azimuth_energy90_width_p0_convention_m",
    "near_far_energy_ratio", "front_rear_energy_ratio", "inside_gt_pixel_fraction", "inside_gt_energy_fraction", "inside_ring_energy_ratio",
    "boundary_contact_ratio", "mask_contact_ratio", "visible_fraction", "metric_extent_reliable", "observation_status", "crop_bbox", "mask_definition", "gt_file_opened_for_region_generation", "final_detection_label",
]
BACKGROUND_FIELDS = ["region_id", "sar_frame", "background_type", "center_x", "center_y", "same_area_as_gt", "overlaps_any_gm017_gt_aabb", "source", "gt_role"]
MASK_AUDIT_FIELDS = ["sar_frame", "image_zero_fraction", "gt_visible_fraction", "gt_mask_contact_ratio", "gt_boundary_contact_ratio", "censored_region_count", "mask_definition", "metric_extent_reliable", "notes"]
VISUAL_FIELDS = ["visual_id", "sar_frame", "diagnostic_png", "review_requirement", "review_status", "reviewer_conclusion_cn", "commit_policy"]
PRE_EVAL_SEAL_FIELDS = ["artifact_key", "path", "sha256", "row_count", "seal_phase", "gt_allowed_at_creation", "code_commit_sha", "generator_source_sha256", "allowed_inputs", "forbidden_outputs"]
REPLAY_FIELDS = ["artifact_key", "frozen_sha256", "replay_sha256", "status"]
FROZEN_MANIFEST_FIELDS = ["artifact_key", "path", "sha256", "row_count", "phase", "notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "generate":
        run_generation(OUTPUTS)
    elif args.command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
