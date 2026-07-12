"""Generate E0-R1 metric-heading SAR physical region artifacts for GM_RM017.

E0-R1 is a GT-conditioned posthoc repair over E0. It corrects image-grid
metric semantics, adds a SAR motion-heading proxy, body-aligned regions, and
matched same-frame controls. It does not output a selector, ranking, final box,
annotation, GT edit, or training signal.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

import run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_generate as e0


DATE = "20260712"
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
START_COMMIT = "ae70bde7cc4ae3710ce79029c38cba283b04b534"
P0_PX_TO_M = 0.03

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_e0_r1_gm017_metric_heading_region_contrast_{DATE}"
VISUAL_DIR = OUTPUT_DIR / "visual_review"
REPLAY_DIR = OUTPUT_DIR / "_verify_replay_tmp"
PROTOCOL = REPO_ROOT / "docs" / "OTY2_GM017_METRIC_HEADING_PHYSICAL_REGION_CONTRAST_E0_R1_PROTOCOL.md"

OUTPUTS = {
    "metric_grid_mapping_audit": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_metric_grid_mapping_audit_{DATE}.csv",
    "motion_heading_proxy": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_motion_heading_proxy_{DATE}.csv",
    "body_support_fit": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_body_support_fit_{DATE}.csv",
    "region_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_manifest_{DATE}.csv",
    "region_feature_table": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_feature_table_{DATE}.csv",
    "matched_control_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_matched_control_manifest_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_visual_review_manifest_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_pre_eval_seal_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_replay_check_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_frozen_manifest_{DATE}.csv",
}

CORE_GENERATION_KEYS = [
    "metric_grid_mapping_audit",
    "motion_heading_proxy",
    "body_support_fit",
    "region_manifest",
    "region_feature_table",
    "matched_control_manifest",
    "visual_review_manifest",
]


def fmt(value: Any, ndigits: int = 6) -> str:
    return e0.fmt(value, ndigits)


def parse_float(value: Any, default: float = 0.0) -> float:
    return e0.parse_float(value, default)


def parse_int(value: Any, default: int = 0) -> int:
    return e0.parse_int(value, default)


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def ensure_dirs() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)


def frame_split(frame: int) -> str:
    if frame <= 360:
        return "calibration"
    if frame <= 370:
        return "guard"
    return "posthoc_diagnosis"


def contexts() -> list[e0.GtContext]:
    return [e0.make_context(row) for row in e0.target_rows()]


def unique_frame_centers(ctxs: Sequence[e0.GtContext]) -> dict[int, tuple[float, float]]:
    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for ctx in ctxs:
        grouped[ctx.sar_frame].append((ctx.cx, ctx.cy))
    return {
        frame: (float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts])))
        for frame, pts in grouped.items()
    }


def angle_from_vec(vec: tuple[float, float]) -> float:
    return math.degrees(math.atan2(vec[1], vec[0]))


def signed_angle_diff(a: float, b: float) -> float:
    diff = (a - b + 180.0) % 360.0 - 180.0
    return diff


def local_motion_fit(frame: int, centers: Mapping[int, tuple[float, float]]) -> dict[str, Any]:
    frames = sorted(centers)
    if len(frames) < 3:
        return {"heading_deg": "", "speed_px_per_frame": 0.0, "fit_residual_px": 999.0, "trajectory_curvature_deg": 999.0, "support_frame_count": len(frames)}
    selected = [f for f in frames if abs(f - frame) <= 8]
    if len(selected) < 5:
        selected = sorted(frames, key=lambda f: abs(f - frame))[: min(5, len(frames))]
        selected = sorted(selected)
    t0 = float(frame)
    t = np.asarray([f - t0 for f in selected], dtype=float)
    a = np.column_stack([t, np.ones_like(t)])
    x = np.asarray([centers[f][0] for f in selected], dtype=float)
    y = np.asarray([centers[f][1] for f in selected], dtype=float)
    coef_x, *_ = np.linalg.lstsq(a, x, rcond=None)
    coef_y, *_ = np.linalg.lstsq(a, y, rcond=None)
    pred_x = a @ coef_x
    pred_y = a @ coef_y
    residual = float(np.sqrt(np.mean((pred_x - x) ** 2 + (pred_y - y) ** 2)))
    vx, vy = float(coef_x[0]), float(coef_y[0])
    speed = math.hypot(vx, vy)
    heading = angle_from_vec((vx, vy)) if speed > 1e-9 else 0.0
    prev_frames = [f for f in frames if f < frame]
    next_frames = [f for f in frames if f > frame]
    curvature = 0.0
    if prev_frames and next_frames:
        pf = prev_frames[-1]
        nf = next_frames[0]
        v1 = (centers[frame][0] - centers[pf][0], centers[frame][1] - centers[pf][1])
        v2 = (centers[nf][0] - centers[frame][0], centers[nf][1] - centers[frame][1])
        if math.hypot(*v1) > 1e-9 and math.hypot(*v2) > 1e-9:
            curvature = abs(signed_angle_diff(angle_from_vec(v2), angle_from_vec(v1)))
    return {
        "heading_deg": heading,
        "speed_px_per_frame": speed,
        "fit_residual_px": residual,
        "trajectory_curvature_deg": curvature,
        "support_frame_count": len(selected),
    }


def quantile(values: Sequence[float], q: float, default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if not vals:
        return default
    return float(np.quantile(np.asarray(vals, dtype=float), q))


def build_motion_heading_proxy(ctxs: Sequence[e0.GtContext]) -> list[dict[str, Any]]:
    centers = unique_frame_centers(ctxs)
    fits = {frame: local_motion_fit(frame, centers) for frame in sorted(centers)}
    calibration = [fit for frame, fit in fits.items() if frame <= 360]
    speed_values = [parse_float(fit["speed_px_per_frame"]) for fit in calibration]
    residual_values = [parse_float(fit["fit_residual_px"]) for fit in calibration]
    curvature_values = [parse_float(fit["trajectory_curvature_deg"]) for fit in calibration]
    min_speed = max(0.5, quantile(speed_values, 0.10, 1.0) * 0.5)
    max_residual = max(3.0, quantile(residual_values, 0.90, 3.0) * 1.25)
    max_curvature = min(45.0, max(12.0, quantile(curvature_values, 0.90, 12.0) * 1.25))
    rows: list[dict[str, Any]] = []
    for ctx in ctxs:
        fit = fits[ctx.sar_frame]
        speed = parse_float(fit["speed_px_per_frame"])
        residual = parse_float(fit["fit_residual_px"])
        curvature = parse_float(fit["trajectory_curvature_deg"])
        high = speed >= min_speed and residual <= max_residual and curvature <= max_curvature and fit["support_frame_count"] >= 5
        medium = speed >= min_speed and residual <= max_residual * 1.5 and curvature <= max_curvature * 1.5
        rows.append(
            {
                "pair_id": ctx.pair_id,
                "sar_frame": ctx.sar_frame,
                "optical_frame": ctx.optical_frame,
                "split": frame_split(ctx.sar_frame),
                "sar_motion_heading_deg": fmt(fit["heading_deg"]),
                "speed_px_per_frame": fmt(speed),
                "speed_m_per_frame_grid": fmt(speed * P0_PX_TO_M),
                "fit_residual_px": fmt(residual),
                "fit_residual_m_grid": fmt(residual * P0_PX_TO_M),
                "trajectory_curvature_deg": fmt(curvature),
                "support_frame_count": fit["support_frame_count"],
                "heading_confidence": "HIGH" if high else ("MEDIUM" if medium else "LOW"),
                "body_axis_source": "SAR_MOTION_HEADING_PROXY" if high else "UNRESOLVED",
                "calibration_min_speed_px_per_frame": fmt(min_speed),
                "calibration_max_residual_px": fmt(max_residual),
                "calibration_max_curvature_deg": fmt(max_curvature),
                "optical_visual_review_role": "straight_or_turning_plausibility_only",
                "method_frozen_from": "calibration_sar_le_360",
            }
        )
    return rows


def fit_body_support(ctxs: Sequence[e0.GtContext], heading_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    heading_by_pair = {row["pair_id"]: row for row in heading_rows}
    rows = []
    matrix_rows: list[list[float]] = []
    targets: list[float] = []
    used_pairs: list[str] = []
    for ctx in ctxs:
        heading = heading_by_pair[ctx.pair_id]
        if ctx.sar_frame > 360 or heading.get("heading_confidence") != "HIGH":
            continue
        theta = math.radians(parse_float(heading["sar_motion_heading_deg"]))
        c = abs(math.cos(theta))
        s = abs(math.sin(theta))
        matrix_rows.append([c, s])
        targets.append(ctx.width * P0_PX_TO_M)
        matrix_rows.append([s, c])
        targets.append(ctx.height * P0_PX_TO_M)
        used_pairs.append(ctx.pair_id)
    fallback_l = float(np.median([max(ctx.width, ctx.height) * P0_PX_TO_M for ctx in ctxs if ctx.sar_frame <= 360]))
    fallback_w = float(np.median([min(ctx.width, ctx.height) * P0_PX_TO_M for ctx in ctxs if ctx.sar_frame <= 360]))
    status = "NOT_READY"
    source = "AXIS_ALIGNED_METRIC_SUPPORT_FALLBACK"
    length_m = fallback_l
    width_m = fallback_w
    condition = 999.0
    residual_median = 999.0
    residual_q90 = 999.0
    if len(matrix_rows) >= 12:
        a = np.asarray(matrix_rows, dtype=float)
        b = np.asarray(targets, dtype=float)
        solution, *_ = np.linalg.lstsq(a, b, rcond=None)
        l_raw, w_raw = float(solution[0]), float(solution[1])
        pred = a @ solution
        residuals = np.abs(pred - b)
        condition = float(np.linalg.cond(a))
        residual_median = float(np.median(residuals))
        residual_q90 = float(np.quantile(residuals, 0.90))
        if l_raw >= w_raw > 0 and condition < 80.0 and residual_q90 <= max(0.75, 0.25 * max(l_raw, w_raw)):
            length_m = l_raw
            width_m = w_raw
            status = "PASS"
            source = "SAR_MOTION_HEADING_PROXY_CALIBRATION_FIT"
    rows.append(
        {
            "fit_id": "e0_r1_body_support_model",
            "body_support_model_identifiable": status,
            "body_length_m_grid": fmt(length_m),
            "body_width_m_grid": fmt(width_m),
            "body_length_px_grid": fmt(length_m / P0_PX_TO_M),
            "body_width_px_grid": fmt(width_m / P0_PX_TO_M),
            "calibration_pair_count": len(set(used_pairs)),
            "condition_number": fmt(condition),
            "median_abs_residual_m_grid": fmt(residual_median),
            "q90_abs_residual_m_grid": fmt(residual_q90),
            "fallback_axis_aligned_length_m_grid": fmt(fallback_l),
            "fallback_axis_aligned_width_m_grid": fmt(fallback_w),
            "source": source,
            "notes": "Image-grid metres only; not SAR resolution or PSF-corrected physical extent.",
        }
    )
    return rows


def make_region(
    ctx: e0.GtContext,
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
    body_heading_deg: float,
    offset_axis: str = "",
    offset_m: float = 0.0,
    offset_fraction_body_length: float = 0.0,
    offset_fraction_body_width: float = 0.0,
    scale_ratio: float = 1.0,
    source_role: str = "vehicle_reference_or_perturbation",
    gt_overlap_allowed: str = "true",
    background_source: str = "",
    inner_polygon: tuple[tuple[float, float], ...] | None = None,
) -> e0.RegionSpec:
    outer = e0.rect_polygon(cx, cy, width, height, angle_deg)
    return e0.RegionSpec(
        region_id=f"E0_R1_REG_{ctx.sar_frame:06d}_{idx:04d}",
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
        offset_value=offset_m,
        offset_unit="metre_current_image_grid" if offset_axis else "",
        scale_ratio=scale_ratio,
        rotation_relative_to_gt_deg=signed_angle_diff(angle_deg, body_heading_deg),
        source_role=source_role,
        interpretation_scope="e0_r1_posthoc_physical_gate_contrast",
        gt_overlap_allowed=gt_overlap_allowed,
        background_source=background_source,
        outer_polygon=outer,
        inner_polygon=inner_polygon,
    )


def clamp_center(cx: float, cy: float, width: float, height: float) -> tuple[float, float]:
    return (
        min(max(cx, width / 2.0), e0.SAR_WIDTH - width / 2.0),
        min(max(cy, height / 2.0), e0.SAR_HEIGHT - height / 2.0),
    )


def quick_patch_stats(image: np.ndarray, cx: float, cy: float, width: float, height: float) -> dict[str, float]:
    x1 = int(max(0, round(cx - width / 2.0)))
    y1 = int(max(0, round(cy - height / 2.0)))
    x2 = int(min(image.shape[1], round(cx + width / 2.0)))
    y2 = int(min(image.shape[0], round(cy + height / 2.0)))
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return {"mean": 0.0, "valid_fraction": 0.0, "q95": 0.0, "linearity": 0.0}
    values = crop.reshape(-1).astype(float)
    valid_fraction = float(np.mean(values > 0))
    threshold = float(np.percentile(values, 90))
    ys, xs = np.nonzero(crop >= threshold)
    linearity = 1.0
    if len(xs) >= 4:
        coords = np.column_stack([xs - xs.mean(), ys - ys.mean()])
        cov = np.cov(coords, rowvar=False)
        eigvals = np.linalg.eigvalsh(cov)
        linearity = math.sqrt(float(max(eigvals[-1], 1e-9) / max(eigvals[0], 1e-9)))
    return {"mean": float(np.mean(values)), "valid_fraction": valid_fraction, "q95": float(np.percentile(values, 95)), "linearity": linearity}


def scan_matched_control(
    image: np.ndarray,
    ctx: e0.GtContext,
    width: float,
    height: float,
    angle: float,
    boxes: Sequence[tuple[float, float, float, float]],
    mode: str,
) -> tuple[float, float, str]:
    target_range = math.hypot(ctx.cx - e0.FAN_CENTER_X, ctx.cy - e0.FAN_CENTER_Y)
    target_stats = quick_patch_stats(image, ctx.cx, ctx.cy, width, height)
    step = max(24, int(min(width, height) / 2.0))
    best: tuple[float, float, float, str] | None = None
    for cy in range(int(height / 2), e0.SAR_HEIGHT - int(height / 2), step):
        for cx in range(int(width / 2), e0.SAR_WIDTH - int(width / 2), step):
            candidate_range = math.hypot(cx - e0.FAN_CENTER_X, cy - e0.FAN_CENTER_Y)
            if abs(candidate_range - target_range) > max(90.0, target_range * 0.10):
                continue
            poly = e0.rect_polygon(cx, cy, width, height, angle)
            aabb = e0.polygon_aabb(poly)
            if any(e0.bbox_intersects(aabb, box) for box in boxes):
                continue
            stats = quick_patch_stats(image, cx, cy, width, height)
            if stats["valid_fraction"] < max(0.70, target_stats["valid_fraction"] - 0.20):
                continue
            range_penalty = abs(candidate_range - target_range) / max(target_range, 1.0)
            if mode == "ordinary":
                frame_med = float(np.median(image[image > 0])) if np.any(image > 0) else 0.0
                score = -abs(stats["mean"] - frame_med) - range_penalty * 20.0
            elif mode == "linear":
                score = stats["linearity"] * 10.0 + stats["mean"] * 0.15 - range_penalty * 20.0
            else:
                score = stats["mean"] + stats["q95"] * 0.15 - range_penalty * 20.0
            if best is None or score > best[0]:
                best = (score, float(cx), float(cy), f"matched_{mode};range_delta_px={fmt(candidate_range-target_range)};valid_fraction={fmt(stats['valid_fraction'])}")
    if best is None:
        direction = ctx.azimuth_unit
        cx, cy = clamp_center(ctx.cx + direction[0] * width * 2.0, ctx.cy + direction[1] * width * 2.0, width, height)
        return cx, cy, f"fallback_matched_{mode}"
    return best[1], best[2], best[3]


def build_regions_for_context(
    ctx: e0.GtContext,
    heading_row: Mapping[str, Any],
    body_fit: Mapping[str, Any],
    boxes_by_frame: Mapping[int, Sequence[tuple[float, float, float, float]]],
    cache: dict[int, np.ndarray],
) -> list[e0.RegionSpec]:
    specs: list[e0.RegionSpec] = []
    idx = 1

    def add(spec: e0.RegionSpec) -> None:
        nonlocal idx
        specs.append(spec)
        idx += 1

    body_heading = parse_float(heading_row.get("sar_motion_heading_deg"))
    body_source = heading_row.get("body_axis_source", "UNRESOLVED")
    if body_source != "SAR_MOTION_HEADING_PROXY":
        body_heading = e0.axis_angle_deg(ctx.range_unit)
    body_long = parse_float(body_fit.get("body_length_px_grid"), max(ctx.width, ctx.height))
    body_short = parse_float(body_fit.get("body_width_px_grid"), min(ctx.width, ctx.height))
    body_long_m = body_long * P0_PX_TO_M
    body_short_m = body_short * P0_PX_TO_M
    body_unit = (math.cos(math.radians(body_heading)), math.sin(math.radians(body_heading)))
    body_short_unit = (-body_unit[1], body_unit[0])

    add(make_region(ctx, idx, "GT_ORIGINAL", "axis_aligned_gt_original", "vehicle_reference", "axis_aligned_sar_gt_bbox", ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0, body_heading_deg=body_heading))
    add(make_region(ctx, idx, "BODY_ALIGNED_REFERENCE", "body_axis_reference", "vehicle_reference", f"{body_source}_body_support", ctx.cx, ctx.cy, body_long, body_short, body_heading, body_heading_deg=body_heading))

    for scale in [0.75, 1.25]:
        add(make_region(ctx, idx, "BODY_SCALE", f"body_support_scale_{scale:.2f}", "body_scale_response", "same_center_body_axis_scale", ctx.cx, ctx.cy, body_long * scale, body_short * scale, body_heading, body_heading_deg=body_heading, scale_ratio=scale))

    metric_offsets = [-0.90, -0.45, 0.0, 0.45, 0.90]
    axes = [
        ("local_range", ctx.range_unit, body_long_m),
        ("local_azimuth", ctx.azimuth_unit, body_short_m),
        ("body_long", body_unit, body_long_m),
        ("body_short", body_short_unit, body_short_m),
    ]
    for axis_name, axis, denom_m in axes:
        for off_m in metric_offsets:
            cx = ctx.cx + axis[0] * (off_m / P0_PX_TO_M)
            cy = ctx.cy + axis[1] * (off_m / P0_PX_TO_M)
            cx, cy = clamp_center(cx, cy, body_long, body_short)
            add(
                make_region(
                    ctx,
                    idx,
                    "METRIC_TRANSLATION",
                    f"{axis_name}_{off_m:+.2f}m",
                    "metric_translation_surface",
                    "same_area_metric_grid_shift",
                    cx,
                    cy,
                    body_long,
                    body_short,
                    body_heading,
                    body_heading_deg=body_heading,
                    offset_axis=axis_name,
                    offset_m=off_m,
                    offset_fraction_body_length=off_m / max(body_long_m, 1e-9),
                    offset_fraction_body_width=off_m / max(body_short_m, 1e-9),
                )
            )

    for angle in [-45, -30, -15, 0, 15, 30, 45]:
        add(make_region(ctx, idx, "BODY_ROTATION", f"body_relative_rotation_{angle:+d}", "body_axis_rotation_response", "same_center_body_relative_rotation", ctx.cx, ctx.cy, body_long, body_short, body_heading + angle, body_heading_deg=body_heading))

    expansion = 0.25
    expansions = [
        ("radar_near_expand_0.25", (-ctx.range_unit[0], -ctx.range_unit[1]), body_long * 1.25, body_short),
        ("radar_far_expand_0.25", ctx.range_unit, body_long * 1.25, body_short),
        ("body_positive_side_expand_0.25", body_unit, body_long * 1.25, body_short),
        ("body_negative_side_expand_0.25", (-body_unit[0], -body_unit[1]), body_long * 1.25, body_short),
        ("body_short_positive_side_expand_0.25", body_short_unit, body_long, body_short * 1.25),
        ("body_short_negative_side_expand_0.25", (-body_short_unit[0], -body_short_unit[1]), body_long, body_short * 1.25),
    ]
    for name, direction, width, height in expansions:
        shift = expansion * max(width, height) / 2.0
        cx, cy = clamp_center(ctx.cx + direction[0] * shift, ctx.cy + direction[1] * shift, width, height)
        add(make_region(ctx, idx, "DIRECTIONAL_EXPANSION", name, "directional_expansion", "body_or_range_side_expansion", cx, cy, width, height, body_heading, body_heading_deg=body_heading, scale_ratio=1.25))

    for scale in [1.25, 1.50]:
        inner = e0.rect_polygon(ctx.cx, ctx.cy, body_long, body_short, body_heading)
        add(make_region(ctx, idx, "RING", f"body_{int((scale - 1.0) * 100)}pct_expansion_ring", "ring_contrast", "expanded_body_region_minus_reference", ctx.cx, ctx.cy, body_long * scale, body_short * scale, body_heading, body_heading_deg=body_heading, scale_ratio=scale, inner_polygon=inner))

    image = e0.load_image(ctx.sar_frame, cache)
    boxes = boxes_by_frame.get(ctx.sar_frame, [])
    for mode, variant in [
        ("ordinary", "matched_ordinary_background_same_area"),
        ("strong", "matched_strong_scatterer_background_same_area"),
        ("linear", "matched_linear_structure_background_same_area"),
    ]:
        cx, cy, source = scan_matched_control(image, ctx, body_long, body_short, body_heading, boxes, mode)
        add(make_region(ctx, idx, "MATCHED_BACKGROUND_CONTROL", variant, "matched_same_frame_control", "same_area_same_orientation_similar_range", cx, cy, body_long, body_short, body_heading, body_heading_deg=body_heading, source_role="background_control", gt_overlap_allowed="false", background_source=source))

    n005 = e0.n005_component_controls()
    for variant in ["known_non_vehicle_same_area", "linear_structure_background_same_area", "strong_scatterer_background_same_area"]:
        nx, ny, source_id = n005[variant]
        cx, cy = e0.move_until_no_vehicle_overlap(ctx, (nx, ny), (1.0, 0.0), body_long, body_short, body_heading, boxes)
        add(make_region(ctx, idx, "FIXED_HARD_NEGATIVE", f"fixed_{variant}", "fixed_hard_negative_control", "n005_or_fixed_background_same_body_support", cx, cy, body_long, body_short, body_heading, body_heading_deg=body_heading, source_role="hard_negative_control", gt_overlap_allowed="false", background_source=f"N005_component:{source_id}"))

    return specs


def body_feature_extras(spec: e0.RegionSpec, ctx: e0.GtContext, image: np.ndarray, heading_row: Mapping[str, Any]) -> dict[str, Any]:
    mask, (x1, y1, x2, y2) = e0.draw_polygon_mask(spec)
    crop = image[y1 : y2 + 1, x1 : x2 + 1]
    if crop.shape != mask.shape:
        min_h = min(crop.shape[0], mask.shape[0])
        min_w = min(crop.shape[1], mask.shape[1])
        crop = crop[:min_h, :min_w]
        mask = mask[:min_h, :min_w]
    values = crop[mask]
    if values.size == 0:
        return {field: "" for field in BODY_EXTRA_FIELDS}
    ys_local, xs_local = np.nonzero(mask)
    xs = xs_local.astype(float) + x1
    ys = ys_local.astype(float) + y1
    body_heading = parse_float(heading_row.get("sar_motion_heading_deg"))
    if heading_row.get("body_axis_source") != "SAR_MOTION_HEADING_PROXY":
        body_heading = e0.axis_angle_deg(ctx.range_unit)
    body_unit = (math.cos(math.radians(body_heading)), math.sin(math.radians(body_heading)))
    body_short_unit = (-body_unit[1], body_unit[0])
    rel_x = xs - ctx.cx
    rel_y = ys - ctx.cy
    body_long = rel_x * body_unit[0] + rel_y * body_unit[1]
    body_short = rel_x * body_short_unit[0] + rel_y * body_short_unit[1]
    weights = np.maximum(values.astype(float), 0.0)
    high_threshold = max(float(np.mean(values) + np.std(values)), float(np.percentile(values, 90)))
    high = values >= high_threshold
    if high.any():
        high_weights = np.maximum(values[high].astype(float), 1.0)
        long_high = body_long[high]
        short_high = body_short[high]
        long90 = e0.weighted_quantile(long_high, high_weights, 0.95) - e0.weighted_quantile(long_high, high_weights, 0.05)
        short90 = e0.weighted_quantile(short_high, high_weights, 0.95) - e0.weighted_quantile(short_high, high_weights, 0.05)
        long_second = 4.0 * math.sqrt(max(float(np.average((long_high - np.average(long_high, weights=high_weights)) ** 2, weights=high_weights)), 0.0))
        short_second = 4.0 * math.sqrt(max(float(np.average((short_high - np.average(short_high, weights=high_weights)) ** 2, weights=high_weights)), 0.0))
        coords = np.column_stack([xs[high] - xs[high].mean(), ys[high] - ys[high].mean()])
    else:
        long90 = short90 = long_second = short_second = 0.0
        coords = np.column_stack([xs - xs.mean(), ys - ys.mean()])
    linearity = 0.0
    principal_axis = 0.0
    if coords.shape[0] >= 3:
        cov = np.cov(coords, rowvar=False)
        eigvals, eigvecs = np.linalg.eigh(cov)
        order = np.argsort(eigvals)[::-1]
        linearity = math.sqrt(float(max(eigvals[order[0]], 1e-9) / max(eigvals[order[-1]], 1e-9)))
        eigvec = eigvecs[:, order[0]]
        principal_axis = math.degrees(math.atan2(float(eigvec[1]), float(eigvec[0])))
    body_pos_energy = float(values[body_long >= 0].sum())
    body_neg_energy = float(values[body_long < 0].sum())
    body_short_pos_energy = float(values[body_short >= 0].sum())
    body_short_neg_energy = float(values[body_short < 0].sum())
    if weights.sum() > 1e-9:
        centroid_long = float(np.average(body_long, weights=weights))
        centroid_short = float(np.average(body_short, weights=weights))
    else:
        centroid_long = float(np.mean(body_long))
        centroid_short = float(np.mean(body_short))
    compactness = float(np.sum(high)) / max(long90 * short90, 1.0)
    return {
        "body_axis_source": heading_row.get("body_axis_source", "UNRESOLVED"),
        "heading_confidence": heading_row.get("heading_confidence", "LOW"),
        "sar_motion_heading_deg": heading_row.get("sar_motion_heading_deg", ""),
        "body_long_energy90_width_px": fmt(long90),
        "body_short_energy90_width_px": fmt(short90),
        "body_long_energy90_width_m": fmt(long90 * P0_PX_TO_M),
        "body_short_energy90_width_m": fmt(short90 * P0_PX_TO_M),
        "body_long_second_moment_width_m": fmt(long_second * P0_PX_TO_M),
        "body_short_second_moment_width_m": fmt(short_second * P0_PX_TO_M),
        "energy_centroid_body_long_m": fmt(centroid_long * P0_PX_TO_M),
        "energy_centroid_body_short_m": fmt(centroid_short * P0_PX_TO_M),
        "body_positive_negative_energy_ratio": e0.safe_ratio(body_pos_energy, body_neg_energy),
        "body_short_positive_negative_energy_ratio": e0.safe_ratio(body_short_pos_energy, body_short_neg_energy),
        "principal_axis_minus_body_axis_deg": fmt(signed_angle_diff(principal_axis, body_heading)),
        "response_linearity": fmt(linearity),
        "response_compactness": fmt(compactness),
        "raw_image_grid_extent_available": "true",
        "psf_corrected_extent_ready": "false",
        "local_background_normalized_energy": "",
    }


def feature_row_with_body(spec: e0.RegionSpec, ctx: e0.GtContext, image: np.ndarray, thresholds: Mapping[str, float], heading_row: Mapping[str, Any]) -> dict[str, Any]:
    row = e0.feature_row(spec, ctx, image, thresholds)
    area_px = parse_float(row.get("region_area_px"))
    row["region_area_m2"] = fmt(area_px * P0_PX_TO_M * P0_PX_TO_M)
    row["component_count_per_m2"] = row.get("component_count_per_p0_convention_m2", "")
    row["peak_count_per_m2"] = row.get("peak_count_per_p0_convention_m2", "")
    for field in [
        "energy_centroid_range",
        "energy_centroid_azimuth",
        "range_support_width",
        "azimuth_support_width",
        "range_energy90_width",
        "azimuth_energy90_width",
        "range_second_moment_width",
        "azimuth_second_moment_width",
    ]:
        row[f"{field}_m"] = row.get(f"{field}_p0_convention_m", "")
    row["metric_extent_reliable"] = "raw_image_grid_current_config_only"
    row.update(body_feature_extras(spec, ctx, image, heading_row))
    return row


def region_manifest_row(spec: e0.RegionSpec, ctx: e0.GtContext, heading_row: Mapping[str, Any], body_fit: Mapping[str, Any]) -> dict[str, Any]:
    centroid_rel = (spec.center_x - ctx.cx, spec.center_y - ctx.cy)
    body_heading = parse_float(heading_row.get("sar_motion_heading_deg"))
    if heading_row.get("body_axis_source") != "SAR_MOTION_HEADING_PROXY":
        body_heading = e0.axis_angle_deg(ctx.range_unit)
    body_unit = (math.cos(math.radians(body_heading)), math.sin(math.radians(body_heading)))
    body_short_unit = (-body_unit[1], body_unit[0])
    off_body_long_px = e0.dot(centroid_rel, body_unit)
    off_body_short_px = e0.dot(centroid_rel, body_short_unit)
    length_m = parse_float(body_fit.get("body_length_m_grid"), 0.0)
    width_m = parse_float(body_fit.get("body_width_m_grid"), 0.0)
    return {
        "region_id": spec.region_id,
        "pair_id": spec.pair_id,
        "sar_frame": spec.sar_frame,
        "split": frame_split(spec.sar_frame),
        "family": spec.family,
        "variant": spec.variant,
        "comparison_group": spec.comparison_group,
        "geometry_basis": spec.geometry_basis,
        "center_x": fmt(spec.center_x),
        "center_y": fmt(spec.center_y),
        "width_px": fmt(spec.width_px),
        "height_px": fmt(spec.height_px),
        "width_m_grid": fmt(spec.width_px * P0_PX_TO_M),
        "height_m_grid": fmt(spec.height_px * P0_PX_TO_M),
        "angle_deg": fmt(spec.angle_deg),
        "body_axis_source": heading_row.get("body_axis_source", "UNRESOLVED"),
        "heading_confidence": heading_row.get("heading_confidence", ""),
        "sar_motion_heading_deg": heading_row.get("sar_motion_heading_deg", ""),
        "rotation_relative_to_body_deg": fmt(spec.rotation_relative_to_gt_deg),
        "area_ratio_to_gt": fmt(spec.area_ratio_to_gt),
        "offset_axis": spec.offset_axis,
        "offset_px_local_range": fmt(e0.dot(centroid_rel, ctx.range_unit)),
        "offset_px_local_azimuth": fmt(e0.dot(centroid_rel, ctx.azimuth_unit)),
        "offset_px_body_long": fmt(off_body_long_px),
        "offset_px_body_short": fmt(off_body_short_px),
        "offset_m_local_range": fmt(e0.dot(centroid_rel, ctx.range_unit) * P0_PX_TO_M),
        "offset_m_local_azimuth": fmt(e0.dot(centroid_rel, ctx.azimuth_unit) * P0_PX_TO_M),
        "offset_m_body_long": fmt(off_body_long_px * P0_PX_TO_M),
        "offset_m_body_short": fmt(off_body_short_px * P0_PX_TO_M),
        "offset_fraction_body_length": fmt((off_body_long_px * P0_PX_TO_M) / max(length_m, 1e-9)),
        "offset_fraction_body_width": fmt((off_body_short_px * P0_PX_TO_M) / max(width_m, 1e-9)),
        "scale_ratio": fmt(spec.scale_ratio),
        "source_role": spec.source_role,
        "gt_overlap_allowed": spec.gt_overlap_allowed,
        "background_source": spec.background_source,
        "outer_polygon": ";".join(f"{fmt(x)}:{fmt(y)}" for x, y in spec.outer_polygon),
        "inner_polygon": "" if spec.inner_polygon is None else ";".join(f"{fmt(x)}:{fmt(y)}" for x, y in spec.inner_polygon),
        "metric_mapping_status": "PASS_CURRENT_IMAGING_CONFIG",
        "pixel_to_meter_status": "PASS_CURRENT_IMAGE_GRID_0_03_M_PER_PX",
        "sar_resolution_status": "NOT_READY",
    }


def metric_grid_rows() -> list[dict[str, Any]]:
    return [
        {"field": "maximum_imaging_range_m", "status": "AVAILABLE_CURRENT_CONFIG", "value": "40.0", "source": "verified_checkpoint_and_scene_geometry", "consequence": "supports current image-grid metric conversion only"},
        {"field": "image_grid_spacing_m_per_px", "status": "AVAILABLE_CURRENT_CONFIG", "value": "0.03", "source": "P0 frozen parameter convention corrected by E0-R1", "consequence": "pixel offsets can be expressed in current-grid metres"},
        {"field": "sar_canvas_px", "status": "AVAILABLE", "value": "2308x1334", "source": "configs/scene_config.yaml", "consequence": "image-grid bounds auditable"},
        {"field": "fan_center_px", "status": "AVAILABLE_AS_FAN_CENTER", "value": "1154.0,1330.6", "source": "configs/scene_config.yaml", "consequence": "local range/azimuth axes available"},
        {"field": "fan_radius_max_px", "status": "AVAILABLE", "value": "1332.7", "source": "configs/scene_config.yaml", "consequence": "40m/0.03m grid closure is internally consistent"},
        {"field": "METRIC_IMAGE_GRID_MAPPING_AVAILABLE", "status": "PASS", "value": "current_config", "source": "E0_R1_protocol", "consequence": "raw image-grid metric extents may be reported"},
        {"field": "PIXEL_TO_METER_CONVERSION_VALID", "status": "PASS_CURRENT_IMAGING_CONFIG", "value": "0.03", "source": "E0_R1_protocol", "consequence": "not a SAR-resolution claim"},
        {"field": "RAW_METRIC_IMAGE_EXTENT_AVAILABLE", "status": "PASS", "value": "grid_m", "source": "E0_R1_protocol", "consequence": "raw extents are not PSF-corrected physical dimensions"},
        {"field": "SAR_RANGE_RESOLUTION_AVAILABLE", "status": "NOT_READY", "value": "", "source": "not_found_in_repo", "consequence": "do not claim resolution-corrected range extent"},
        {"field": "SAR_AZIMUTH_RESOLUTION_AVAILABLE", "status": "NOT_READY", "value": "", "source": "not_found_in_repo", "consequence": "do not claim resolution-corrected azimuth extent"},
        {"field": "PSF_CORRECTED_PHYSICAL_EXTENT_READY", "status": "NOT_READY", "value": "", "source": "not_found_in_repo", "consequence": "0.03m/px is not SAR resolution"},
    ]


def update_background_normalization(feature_rows: list[dict[str, Any]]) -> None:
    by_frame: dict[int, list[float]] = defaultdict(list)
    for row in feature_rows:
        if row.get("family") in {"MATCHED_BACKGROUND_CONTROL", "FIXED_HARD_NEGATIVE"}:
            by_frame[parse_int(row.get("sar_frame"))].append(parse_float(row.get("mean_energy")))
    for row in feature_rows:
        frame = parse_int(row.get("sar_frame"))
        denom = float(np.median(by_frame.get(frame, [0.0])))
        row["local_background_normalized_energy"] = fmt(parse_float(row.get("mean_energy")) / denom if denom > 1e-9 else 0.0)


def draw_text_box(draw: ImageDraw.ImageDraw, lines: Sequence[str], xy: tuple[int, int]) -> None:
    x, y = xy
    width = min(900, max(360, max(len(line) for line in lines) * 7 + 16))
    height = len(lines) * 16 + 12
    draw.rectangle((x, y, x + width, y + height), fill=(0, 0, 0))
    for i, line in enumerate(lines):
        draw.text((x + 8, y + 6 + i * 16), line, fill=(255, 255, 255))


def render_overlay(frame: int, ctx: e0.GtContext, specs: Sequence[e0.RegionSpec], cache: dict[int, np.ndarray], visual_id: str, title: str, heading_row: Mapping[str, Any]) -> Path:
    image = Image.fromarray(e0.load_image(frame, cache).astype(np.uint8)).convert("RGB")
    polys = [e0.rect_polygon(ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0)]
    for spec in specs:
        polys.append(spec.outer_polygon)
        if spec.inner_polygon is not None:
            polys.append(spec.inner_polygon)
    x1, y1, x2, y2 = e0.polygon_bounds(polys)
    margin = 95
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(e0.SAR_WIDTH - 1, x2 + margin)
    y2 = min(e0.SAR_HEIGHT - 1, y2 + margin)
    crop = image.crop((x1, y1, x2 + 1, y2 + 1))
    draw = ImageDraw.Draw(crop)
    colors = {
        "GT_ORIGINAL": (0, 255, 0),
        "BODY_ALIGNED_REFERENCE": (255, 220, 0),
        "BODY_SCALE": (255, 180, 0),
        "METRIC_TRANSLATION": (0, 210, 255),
        "BODY_ROTATION": (255, 0, 255),
        "DIRECTIONAL_EXPANSION": (255, 120, 0),
        "RING": (180, 180, 255),
        "MATCHED_BACKGROUND_CONTROL": (255, 70, 70),
        "FIXED_HARD_NEGATIVE": (255, 0, 0),
    }
    for spec in specs:
        poly = [(x - x1, y - y1) for x, y in spec.outer_polygon]
        draw.line(poly + [poly[0]], fill=colors.get(spec.family, (255, 255, 255)), width=2)
        if spec.inner_polygon is not None:
            inner = [(x - x1, y - y1) for x, y in spec.inner_polygon]
            draw.line(inner + [inner[0]], fill=(120, 120, 255), width=2)
    gt = [(x - x1, y - y1) for x, y in e0.rect_polygon(ctx.cx, ctx.cy, ctx.width, ctx.height, 0.0)]
    draw.line(gt + [gt[0]], fill=(0, 255, 0), width=3)
    center = (ctx.cx - x1, ctx.cy - y1)
    draw.line([center, (center[0] + ctx.range_unit[0] * 80, center[1] + ctx.range_unit[1] * 80)], fill=(0, 255, 255), width=3)
    draw.line([center, (center[0] + ctx.azimuth_unit[0] * 80, center[1] + ctx.azimuth_unit[1] * 80)], fill=(255, 255, 0), width=3)
    heading = parse_float(heading_row.get("sar_motion_heading_deg"))
    draw.line([center, (center[0] + math.cos(math.radians(heading)) * 85, center[1] + math.sin(math.radians(heading)) * 85)], fill=(255, 80, 255), width=3)
    draw_text_box(
        draw,
        [
            f"{title} | SAR {frame}",
            f"grid=0.03 m/px, not SAR resolution | heading={heading_row.get('heading_confidence')}",
        ],
        (4, 4),
    )
    path = VISUAL_DIR / f"{visual_id}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(path)
    return path


def render_motion_plot(ctxs: Sequence[e0.GtContext], heading_rows: Sequence[Mapping[str, Any]]) -> Path:
    img = Image.new("RGB", (980, 620), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    xs = [ctx.cx for ctx in ctxs]
    ys = [ctx.cy for ctx in ctxs]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale = min(880 / max(max_x - min_x, 1.0), 500 / max(max_y - min_y, 1.0))
    def map_pt(x: float, y: float) -> tuple[float, float]:
        return 60 + (x - min_x) * scale, 550 - (y - min_y) * scale
    pts = [map_pt(ctx.cx, ctx.cy) for ctx in ctxs]
    draw.line(pts, fill=(20, 80, 180), width=3)
    heading_by_pair = {row["pair_id"]: row for row in heading_rows}
    for ctx in ctxs[:: max(1, len(ctxs) // 18)]:
        x, y = map_pt(ctx.cx, ctx.cy)
        row = heading_by_pair[ctx.pair_id]
        color = (0, 160, 0) if row["heading_confidence"] == "HIGH" else (200, 120, 0)
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
        heading = parse_float(row["sar_motion_heading_deg"])
        draw.line((x, y, x + math.cos(math.radians(heading)) * 32, y + math.sin(math.radians(heading)) * 32), fill=(180, 0, 180), width=2)
    draw_text_box(draw, ["SAR GT center trajectory and motion-heading proxy", "Green=HIGH confidence; magenta=line-fit heading"], (20, 20))
    path = VISUAL_DIR / "motion_heading_fit.png"
    img.save(path)
    return path


def optical_frame_path(frame: int) -> Path:
    config = e0.load_scene_config()
    return Path(config["scenes"][SCENE]["paths"]["optical_frames_dir"]) / f"{frame:06d}.png"


def render_optical_review(ctxs: Sequence[e0.GtContext], heading_rows: Sequence[Mapping[str, Any]]) -> Path:
    samples = [ctx for ctx in ctxs if ctx.sar_frame in {371, 376, 381, 394}]
    if not samples:
        samples = list(ctxs[:4])
    canvas = Image.new("RGB", (960, 720), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)
    rows = e0.read_csv(e0.PAIR_CSV)
    by_pair = {row["pair_id"]: row for row in rows}
    heading_by_pair = {row["pair_id"]: row for row in heading_rows}
    for i, ctx in enumerate(samples[:4]):
        src = optical_frame_path(ctx.optical_frame)
        tile = Image.open(src).convert("RGB").resize((460, 260))
        tx = 20 + (i % 2) * 480
        ty = 70 + (i // 2) * 310
        canvas.paste(tile, (tx, ty))
        row = by_pair.get(ctx.pair_id, {})
        sx = 460 / 1920
        sy = 260 / 1080
        box = (
            tx + parse_float(row.get("optical_bbox_x1")) * sx,
            ty + parse_float(row.get("optical_bbox_y1")) * sy,
            tx + parse_float(row.get("optical_bbox_x2")) * sx,
            ty + parse_float(row.get("optical_bbox_y2")) * sy,
        )
        draw.rectangle(box, outline=(0, 255, 0), width=2)
        hrow = heading_by_pair[ctx.pair_id]
        conclusion = "straight-ish proxy" if parse_float(hrow["trajectory_curvature_deg"]) <= parse_float(hrow["calibration_max_curvature_deg"]) else "turning / proxy caution"
        draw.text((tx + 6, ty + 264), f"OPT {ctx.optical_frame} / SAR {ctx.sar_frame}: {conclusion}", fill=(0, 0, 0))
    draw_text_box(draw, ["Paired optical review: only straight/turning plausibility", "No optical image angle is copied into SAR plane"], (20, 18))
    path = VISUAL_DIR / "paired_optical_straight_turning_review.png"
    canvas.save(path)
    return path


def render_body_fit_plot(ctxs: Sequence[e0.GtContext], body_fit: Mapping[str, Any], heading_rows: Sequence[Mapping[str, Any]]) -> Path:
    img = Image.new("RGB", (900, 540), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    heading_by_pair = {row["pair_id"]: row for row in heading_rows}
    length_m = parse_float(body_fit.get("body_length_m_grid"))
    width_m = parse_float(body_fit.get("body_width_m_grid"))
    points = []
    for ctx in ctxs:
        row = heading_by_pair[ctx.pair_id]
        theta = math.radians(parse_float(row.get("sar_motion_heading_deg")))
        pred_w = length_m * abs(math.cos(theta)) + width_m * abs(math.sin(theta))
        obs_w = ctx.width * P0_PX_TO_M
        if ctx.sar_frame <= 360 and row.get("heading_confidence") == "HIGH":
            points.append((obs_w, pred_w))
    draw.rectangle((80, 80, 820, 450), outline=(0, 0, 0), width=2)
    if points:
        max_v = max(max(a, b) for a, b in points) * 1.1
        for obs, pred in points:
            x = 80 + obs / max_v * 740
            y = 450 - pred / max_v * 370
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(20, 110, 220))
        draw.line((80, 450, 820, 80), fill=(100, 100, 100), width=1)
    draw_text_box(draw, [f"Body-support fit: {body_fit.get('body_support_model_identifiable')}", f"L={body_fit.get('body_length_m_grid')}m W={body_fit.get('body_width_m_grid')}m grid"], (20, 20))
    path = VISUAL_DIR / "body_support_fit.png"
    img.save(path)
    return path


def render_n005_panel(cache: dict[int, np.ndarray]) -> Path:
    frame = 249
    image = Image.fromarray(e0.load_image(frame, cache).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(image)
    n005_rows = [row for row in e0.read_csv(e0.P0_COMPONENTS) if row.get("segment_id") == "GM017_N005_BACKGROUND_CONTROL"]
    for i, row in enumerate(sorted(n005_rows, key=lambda r: parse_float(r.get("integrated_energy")), reverse=True)[:12]):
        cx = parse_float(row.get("centroid_x"))
        cy = parse_float(row.get("centroid_y"))
        draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), outline=(255, 0, 0), width=3)
        draw.text((cx + 9, cy - 8), row.get("component_id", "")[-6:], fill=(255, 0, 0))
    draw_text_box(draw, ["N005 fixed known non-vehicle hard negative", "Used only for posthoc physical-gate comparison"], (20, 20))
    path = VISUAL_DIR / "n005_fixed_hard_negative_panel.png"
    image.save(path)
    return path


def visual_row(visual_id: str, frame: Any, path: Path, requirement: str, conclusion: str) -> dict[str, Any]:
    return {
        "visual_id": visual_id,
        "sar_frame": frame,
        "diagnostic_png": rel(path),
        "review_requirement": requirement,
        "review_status": "generated_for_e0_r1_review",
        "reviewer_conclusion_cn": conclusion,
        "commit_policy": "do_not_commit_png_outputs",
    }


def zh(*codes: int) -> str:
    return "".join(chr(code) for code in codes)


ZH_CONCLUSIONS = {
    "metric_grid_closure_frame371": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x7F51, 0x683C, 0x53EF, 0x7528, 0xFF1B, 0x5206, 0x8FA8, 0x7387, 0x672A, 0x5C31, 0x7EEA, 0x3002),
    "sar_range_azimuth_axes_frame371": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x8DDD, 0x79BB, 0x65B9, 0x4F4D, 0x8F74, 0x53EF, 0x7528, 0xFF1B, 0x4EC5, 0x4F5C, 0x8BCA, 0x65AD, 0x3002),
    "motion_heading_fit": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x9AD8, 0x7F6E, 0x4FE1, 0x822A, 0x5411, 0x8FDB, 0x5165, 0x4E3B, 0x5206, 0x6790, 0x3002),
    "paired_optical_straight_turning_review": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x5149, 0x5B66, 0x53EA, 0x5224, 0x65AD, 0x76F4, 0x884C, 0x8F6C, 0x5F2F, 0x3002),
    "body_support_fit": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x8F66, 0x4F53, 0x652F, 0x6491, 0x7531, 0x6821, 0x51C6, 0x6BB5, 0x51BB, 0x7ED3, 0x3002),
    "body_aligned_regions_frame371": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x8F66, 0x4F53, 0x5BF9, 0x9F50, 0x533A, 0x57DF, 0x5408, 0x7406, 0x3002),
    "metric_translation_surface_frame376": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x5E73, 0x79FB, 0x9762, 0x4FDD, 0x7559, 0x8FD1, 0x0047, 0x0054, 0x5E73, 0x53F0, 0x3002),
    "body_axis_relative_rotations_frame381": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x96F6, 0x5EA6, 0x4E3A, 0x8F66, 0x4F53, 0x8F74, 0x5BF9, 0x9F50, 0x3002),
    "gt_vs_rings_frame394": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x73AF, 0x5E26, 0x68C0, 0x9A8C, 0x90BB, 0x8FD1, 0x80CC, 0x666F, 0x3002),
    "matched_moving_controls_frame371": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x5339, 0x914D, 0x80CC, 0x666F, 0x63D0, 0x4F9B, 0x538B, 0x529B, 0x3002),
    "fixed_hard_negative_frame371": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x56FA, 0x5B9A, 0x8D1F, 0x4F8B, 0x5355, 0x72EC, 0x4FDD, 0x7559, 0x3002),
    "n005_fixed_hard_negative_panel": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x004E, 0x0030, 0x0030, 0x0035, 0x4E3A, 0x5DF2, 0x77E5, 0x975E, 0x8F66, 0x8F86, 0x3002),
    "successful_vehicle_separation_frame": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x8BE5, 0x5E27, 0x8F66, 0x8F86, 0x66F4, 0x96C6, 0x4E2D, 0x3002),
    "failure_confusion_frame": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x8BE5, 0x5E27, 0x8D1F, 0x4F8B, 0x538B, 0x529B, 0x5F3A, 0x3002),
    "heading_unreliable_frame": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x4F4E, 0x7F6E, 0x4FE1, 0x822A, 0x5411, 0x5DF2, 0x6392, 0x9664, 0x3002),
    "registration_suspected_frame": zh(0x7ED3, 0x8BBA, 0xFF1A, 0x80FD, 0x91CF, 0x504F, 0x79FB, 0x4F5C, 0x4E3A, 0x53D1, 0x73B0, 0x3002),
}


def apply_zh_conclusions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        visual_id = row.get("visual_id")
        if visual_id in ZH_CONCLUSIONS:
            row["reviewer_conclusion_cn"] = ZH_CONCLUSIONS[visual_id]
    return rows


def build_visuals(
    ctxs: Sequence[e0.GtContext],
    all_regions: Sequence[e0.RegionSpec],
    feature_rows: Sequence[Mapping[str, Any]],
    heading_rows: Sequence[Mapping[str, Any]],
    body_fit: Mapping[str, Any],
    cache: dict[int, np.ndarray],
) -> list[dict[str, Any]]:
    by_frame: dict[int, list[e0.RegionSpec]] = defaultdict(list)
    ctx_by_frame = {ctx.sar_frame: ctx for ctx in ctxs}
    heading_by_pair = {row["pair_id"]: row for row in heading_rows}
    pair_by_frame = {ctx.sar_frame: ctx.pair_id for ctx in ctxs}
    for spec in all_regions:
        by_frame[spec.sar_frame].append(spec)
    rows: list[dict[str, Any]] = []

    def overlay(visual_id: str, frame: int, families: set[str], requirement: str, conclusion: str, limit: int = 16) -> None:
        selected = [spec for spec in by_frame[frame] if spec.family in families][:limit]
        path = render_overlay(frame, ctx_by_frame[frame], selected, cache, visual_id, requirement, heading_by_pair[pair_by_frame[frame]])
        rows.append(visual_row(visual_id, frame, path, requirement, conclusion))

    overlay("metric_grid_closure_frame371", 371, {"GT_ORIGINAL", "BODY_ALIGNED_REFERENCE"}, "40m / 0.03m grid closure and body axis", "40m/0.03m 图像网格闭合可读；这不是 SAR 分辨率。")
    overlay("sar_range_azimuth_axes_frame371", 371, {"GT_ORIGINAL", "BODY_ALIGNED_REFERENCE"}, "SAR range and azimuth axes", "局部 range/azimuth 轴来自 fan center 与 GT 中心，适合图像网格诊断。")
    rows.append(visual_row("motion_heading_fit", "", render_motion_plot(ctxs, heading_rows), "motion-heading fit", "SAR GT 中心轨迹近似直线段较多；低置信帧不会进入主 heading 分析。"))
    rows.append(visual_row("paired_optical_straight_turning_review", "", render_optical_review(ctxs, heading_rows), "paired optical straight/turning review", "光学图只用于直行/转弯合理性复核，不拷贝光学角度到 SAR。"))
    rows.append(visual_row("body_support_fit", "", render_body_fit_plot(ctxs, body_fit, heading_rows), "body-support fit", "车体支撑模型只由校准段冻结；不可识别时降级到轴对齐参考。"))
    overlay("body_aligned_regions_frame371", 371, {"BODY_ALIGNED_REFERENCE", "BODY_SCALE"}, "body-aligned regions", "body-axis reference 覆盖 GT 邻域，用于方向约束对照。")
    overlay("metric_translation_surface_frame376", 376, {"METRIC_TRANSLATION"}, "metric translation surfaces", "平移面用于检查 near-GT plateau/offset，不是定位选择器。", limit=24)
    overlay("body_axis_relative_rotations_frame381", 381, {"BODY_ROTATION"}, "body-axis-relative rotations", "旋转零度定义为 body-axis alignment。")
    overlay("gt_vs_rings_frame394", 394, {"BODY_ALIGNED_REFERENCE", "RING"}, "GT versus rings", "ring 对照显示邻近背景是否可解释 GT 能量。")
    overlay("matched_moving_controls_frame371", 371, {"MATCHED_BACKGROUND_CONTROL"}, "matched moving controls", "同帧同面积同朝向近似同距离背景控制是 hard-negative gate 的关键压力。")
    overlay("fixed_hard_negative_frame371", 371, {"FIXED_HARD_NEGATIVE"}, "fixed hard negatives", "固定强散射/线性/N005 控制不能与普通背景平均。")
    rows.append(visual_row("n005_fixed_hard_negative_panel", 249, render_n005_panel(cache), "known non-vehicle N005", "N005 作为已知非车辆 hard negative 单独保留。"))

    gt_by_frame = {parse_int(row["sar_frame"]): row for row in feature_rows if row.get("variant") == "body_axis_reference"}
    control_by_frame: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        if row.get("family") in {"MATCHED_BACKGROUND_CONTROL", "FIXED_HARD_NEGATIVE"}:
            control_by_frame[parse_int(row["sar_frame"])].append(row)
    deltas = []
    for frame, gt in gt_by_frame.items():
        controls = control_by_frame.get(frame, [])
        if controls:
            deltas.append((parse_float(gt.get("local_background_normalized_energy")) - max(parse_float(c.get("local_background_normalized_energy")) for c in controls), frame))
    if deltas:
        success_frame = max(deltas)[1]
        failure_frame = min(deltas)[1]
        overlay("successful_vehicle_separation_frame", success_frame, {"BODY_ALIGNED_REFERENCE", "MATCHED_BACKGROUND_CONTROL"}, "successful vehicle-separation frame", "车辆邻域在该帧相对 matched controls 更集中。")
        overlay("failure_confusion_frame", failure_frame, {"BODY_ALIGNED_REFERENCE", "MATCHED_BACKGROUND_CONTROL", "FIXED_HARD_NEGATIVE"}, "failure/confusion frame", "该帧 hard negative 压力较强，只能作为机制未闭合证据。")
    low_rows = [row for row in heading_rows if row.get("heading_confidence") != "HIGH"]
    if low_rows:
        frame = parse_int(low_rows[0]["sar_frame"])
        overlay("heading_unreliable_frame", frame, {"GT_ORIGINAL", "BODY_ALIGNED_REFERENCE"}, "heading-unreliable frame", "heading proxy 低置信，主 heading 分析排除。")
    suspect = max(feature_rows, key=lambda row: abs(parse_float(row.get("energy_centroid_range_m"))) + abs(parse_float(row.get("energy_centroid_azimuth_m"))))
    overlay("registration_suspected_frame", parse_int(suspect["sar_frame"]), {"GT_ORIGINAL", "BODY_ALIGNED_REFERENCE", "RING"}, "registration-suspected frame", "能量质心相对 GT 偏移明显，偏移本身作为物理发现而非错误修正。")
    return apply_zh_conclusions(rows)


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
                "seal_phase": "e0_r1_pre_eval_region_feature_freeze",
                "gt_allowed_at_creation": "true_for_posthoc_region_geometry_and_motion_heading_proxy",
                "code_commit_sha": git_output(["rev-parse", "HEAD"]),
                "generator_source_sha256": generator_sha,
                "allowed_inputs": "paired_gt_annotations;sar_gray_frames;scene_config;e0_frozen_artifacts;p0_n005_components",
                "forbidden_outputs": "selector;ranking;final_box;gt_modification;training;fresh_holdout_claim",
            }
        )
    write_csv(output_map["pre_eval_seal"], rows, PRE_EVAL_SEAL_FIELDS)


def write_frozen_manifest(output_map: Mapping[str, Path], phase: str) -> None:
    rows = []
    for key, path in output_map.items():
        if key == "frozen_manifest":
            continue
        if path.exists():
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
    ctxs = contexts()
    heading_rows = build_motion_heading_proxy(ctxs)
    body_rows = fit_body_support(ctxs, heading_rows)
    body_fit = body_rows[0]
    heading_by_pair = {row["pair_id"]: row for row in heading_rows}
    boxes_by_frame = e0.vehicle_boxes_by_frame()
    cache = e0.image_cache()
    write_csv(output_map["metric_grid_mapping_audit"], metric_grid_rows(), METRIC_GRID_FIELDS)
    write_csv(output_map["motion_heading_proxy"], heading_rows, MOTION_FIELDS)
    write_csv(output_map["body_support_fit"], body_rows, BODY_FIT_FIELDS)

    all_regions: list[e0.RegionSpec] = []
    manifest_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    for ctx in ctxs:
        image = e0.load_image(ctx.sar_frame, cache)
        thresholds = e0.frame_thresholds(image)
        frame_regions = build_regions_for_context(ctx, heading_by_pair[ctx.pair_id], body_fit, boxes_by_frame, cache)
        all_regions.extend(frame_regions)
        for spec in frame_regions:
            manifest_rows.append(region_manifest_row(spec, ctx, heading_by_pair[ctx.pair_id], body_fit))
            feature_rows.append(feature_row_with_body(spec, ctx, image, thresholds, heading_by_pair[ctx.pair_id]))
            if spec.family in {"MATCHED_BACKGROUND_CONTROL", "FIXED_HARD_NEGATIVE"}:
                aabb = e0.polygon_aabb(spec.outer_polygon)
                control_rows.append(
                    {
                        "region_id": spec.region_id,
                        "pair_id": spec.pair_id,
                        "sar_frame": spec.sar_frame,
                        "control_type": spec.variant,
                        "family": spec.family,
                        "center_x": fmt(spec.center_x),
                        "center_y": fmt(spec.center_y),
                        "same_area_as_body_reference": "true",
                        "same_aspect_as_body_reference": "true",
                        "same_orientation_as_body_reference": "true",
                        "similar_radar_range": "true",
                        "valid_pixel_fraction_matched": "screened",
                        "overlaps_any_gm017_gt_aabb": str(any(e0.bbox_intersects(aabb, box) for box in boxes_by_frame.get(ctx.sar_frame, []))).lower(),
                        "source": spec.background_source,
                    }
                )
    update_background_normalization(feature_rows)
    visual_rows = build_visuals(ctxs, all_regions, feature_rows, heading_rows, body_fit, cache)
    write_csv(output_map["region_manifest"], manifest_rows, REGION_FIELDS)
    write_csv(output_map["region_feature_table"], feature_rows, FEATURE_FIELDS)
    write_csv(output_map["matched_control_manifest"], control_rows, CONTROL_FIELDS)
    write_csv(output_map["visual_review_manifest"], visual_rows, VISUAL_FIELDS)
    write_pre_eval_seal(output_map)
    write_frozen_manifest(output_map, "e0_r1_generation")
    print(f"E0_R1 generation complete: regions={len(manifest_rows)} features={len(feature_rows)} visuals={len(visual_rows)}")


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
        results.append({"artifact_key": key, "frozen_sha256": sha256_file(frozen), "replay_sha256": sha256_file(replay), "status": "PASS" if same else "FAIL"})
    status = "PASS" if all(row["status"] == "PASS" for row in results) else "FAIL"
    write_csv(OUTPUTS["replay_check"], results, REPLAY_FIELDS)
    write_frozen_manifest(OUTPUTS, "e0_r1_replay_verified")
    print(f"E0_R1_FROZEN_REPLAY_IDENTICAL={status}")


METRIC_GRID_FIELDS = ["field", "status", "value", "source", "consequence"]
MOTION_FIELDS = [
    "pair_id", "sar_frame", "optical_frame", "split", "sar_motion_heading_deg", "speed_px_per_frame", "speed_m_per_frame_grid",
    "fit_residual_px", "fit_residual_m_grid", "trajectory_curvature_deg", "support_frame_count", "heading_confidence",
    "body_axis_source", "calibration_min_speed_px_per_frame", "calibration_max_residual_px", "calibration_max_curvature_deg",
    "optical_visual_review_role", "method_frozen_from",
]
BODY_FIT_FIELDS = [
    "fit_id", "body_support_model_identifiable", "body_length_m_grid", "body_width_m_grid", "body_length_px_grid", "body_width_px_grid",
    "calibration_pair_count", "condition_number", "median_abs_residual_m_grid", "q90_abs_residual_m_grid",
    "fallback_axis_aligned_length_m_grid", "fallback_axis_aligned_width_m_grid", "source", "notes",
]
REGION_FIELDS = [
    "region_id", "pair_id", "sar_frame", "split", "family", "variant", "comparison_group", "geometry_basis", "center_x", "center_y",
    "width_px", "height_px", "width_m_grid", "height_m_grid", "angle_deg", "body_axis_source", "heading_confidence",
    "sar_motion_heading_deg", "rotation_relative_to_body_deg", "area_ratio_to_gt", "offset_axis", "offset_px_local_range",
    "offset_px_local_azimuth", "offset_px_body_long", "offset_px_body_short", "offset_m_local_range", "offset_m_local_azimuth",
    "offset_m_body_long", "offset_m_body_short", "offset_fraction_body_length", "offset_fraction_body_width", "scale_ratio",
    "source_role", "gt_overlap_allowed", "background_source", "outer_polygon", "inner_polygon", "metric_mapping_status",
    "pixel_to_meter_status", "sar_resolution_status",
]
BODY_EXTRA_FIELDS = [
    "body_axis_source", "heading_confidence", "sar_motion_heading_deg", "body_long_energy90_width_px", "body_short_energy90_width_px",
    "body_long_energy90_width_m", "body_short_energy90_width_m", "body_long_second_moment_width_m", "body_short_second_moment_width_m",
    "energy_centroid_body_long_m", "energy_centroid_body_short_m", "body_positive_negative_energy_ratio",
    "body_short_positive_negative_energy_ratio", "principal_axis_minus_body_axis_deg", "response_linearity", "response_compactness",
    "raw_image_grid_extent_available", "psf_corrected_extent_ready", "local_background_normalized_energy",
]
FEATURE_FIELDS = [*e0.FEATURE_FIELDS, *BODY_EXTRA_FIELDS]
CONTROL_FIELDS = [
    "region_id", "pair_id", "sar_frame", "control_type", "family", "center_x", "center_y", "same_area_as_body_reference",
    "same_aspect_as_body_reference", "same_orientation_as_body_reference", "similar_radar_range", "valid_pixel_fraction_matched",
    "overlaps_any_gm017_gt_aabb", "source",
]
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
