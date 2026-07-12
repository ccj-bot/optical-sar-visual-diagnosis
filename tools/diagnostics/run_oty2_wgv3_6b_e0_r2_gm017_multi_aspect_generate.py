"""Generate E0-R2 temporal multi-aspect response audit artifacts.

This script continues from frozen E0-R1-R1 outputs. It estimates bounded
relative-aspect observability, attaches vehicle/counterfactual response
descriptors, and generates visual review PNGs under ignored outputs/. It does
not create a detector, selector, ranker, final box, GT edit, training signal,
fixed scatterer ID tracker, or cross-scene validation claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw


DATE = "20260712"
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
START_COMMIT = "4ec662b36d0dc203dde5e165b94c786798ee0bde"
P0_PX_TO_M = 0.03

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_e0_r2_gm017_multi_aspect_{DATE}"
VISUAL_DIR = OUTPUT_DIR / "visual_review"
REPLAY_DIR = OUTPUT_DIR / "_verify_replay_tmp"

R1_UNIQUE_GT = SAMPLES_DIR / f"e0_r1_r1_unique_gt_center_sequence_{DATE}.csv"
R1_AXIAL_HEADING = SAMPLES_DIR / f"e0_r1_r1_axial_body_heading_{DATE}.csv"
R1_SUBJECT_MANIFEST = SAMPLES_DIR / f"e0_r1_r1_subject_manifest_{DATE}.csv"
R1_SUBJECT_TEMPORAL = SAMPLES_DIR / f"e0_r1_r1_subject_temporal_features_{DATE}.csv"
R1_GATE_INTEGRITY = SAMPLES_DIR / f"e0_r1_r1_gate_integrity_{DATE}.csv"
E0_R1_FEATURES = SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_feature_table_{DATE}.csv"
E0_R1_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_manifest_{DATE}.csv"

OUTPUTS = {
    "heading_observability": SAMPLES_DIR / f"e0_r2_heading_observability_{DATE}.csv",
    "heading_uncertainty_ablation": SAMPLES_DIR / f"e0_r2_heading_uncertainty_ablation_{DATE}.csv",
    "relative_aspect_timeline": SAMPLES_DIR / f"e0_r2_relative_aspect_timeline_{DATE}.csv",
    "vehicle_response_descriptors": SAMPLES_DIR / f"e0_r2_vehicle_response_descriptors_{DATE}.csv",
    "gt_attached_background_corridors": SAMPLES_DIR / f"e0_r2_gt_attached_background_corridors_{DATE}.csv",
    "persistent_strong_counterfactual": SAMPLES_DIR / f"e0_r2_persistent_strong_counterfactual_{DATE}.csv",
    "fixed_background_aspect_control": SAMPLES_DIR / f"e0_r2_fixed_background_aspect_control_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"e0_r2_visual_review_manifest_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"e0_r2_pre_eval_seal_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"e0_r2_replay_check_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"e0_r2_frozen_manifest_{DATE}.csv",
}

GENERATION_KEYS = [
    "heading_observability",
    "heading_uncertainty_ablation",
    "relative_aspect_timeline",
    "vehicle_response_descriptors",
    "gt_attached_background_corridors",
    "persistent_strong_counterfactual",
    "fixed_background_aspect_control",
    "visual_review_manifest",
]

DESCRIPTOR_FIELDS = [
    "total_energy",
    "mean_energy",
    "local_background_normalized_energy",
    "high_energy_pixel_fraction",
    "response_occupancy_ratio",
    "inside_vs_ring_contrast",
    "energy_entropy_proxy",
    "range_energy90_width_m",
    "azimuth_energy90_width_m",
    "body_long_energy90_width_m",
    "body_short_energy90_width_m",
    "range_second_moment_width_m",
    "azimuth_second_moment_width_m",
    "body_long_second_moment_width_m",
    "body_short_second_moment_width_m",
    "energy_centroid_range_offset_m",
    "energy_centroid_azimuth_offset_m",
    "energy_centroid_body_long_offset_m",
    "energy_centroid_body_short_offset_m",
    "response_principal_axis_deg",
    "principal_minus_body_axial_deg",
    "principal_minus_range_axial_deg",
    "response_compactness",
    "response_linearity",
    "response_fragment_count",
    "response_fragmentation_index",
    "radar_near_half_energy",
    "radar_far_half_energy",
    "near_far_energy_ratio",
]


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
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
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return ""
    text = f"{number:.{ndigits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def frame_split(frame: int) -> str:
    if frame <= 360:
        return "calibration"
    if frame <= 370:
        return "guard"
    return "posthoc_diagnosis"


def wrap180(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def axis_angle_deg(angle: float) -> float:
    return angle % 180.0


def directed_angle_deg(vec: tuple[float, float]) -> float:
    if math.hypot(vec[0], vec[1]) <= 1e-12:
        return 0.0
    return wrap180(math.degrees(math.atan2(vec[1], vec[0])))


def axial_diff_deg(a: float, b: float) -> float:
    return abs(((axis_angle_deg(a) - axis_angle_deg(b) + 90.0) % 180.0) - 90.0)


def axis_unit(angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return math.cos(rad), math.sin(rad)


def axial_mean_deg(angles: Sequence[float], default: float = 0.0) -> float:
    vals = [axis_angle_deg(v) for v in angles if math.isfinite(float(v))]
    if not vals:
        return default
    x = sum(math.cos(math.radians(2.0 * v)) for v in vals)
    y = sum(math.sin(math.radians(2.0 * v)) for v in vals)
    return axis_angle_deg(math.degrees(math.atan2(y, x)) / 2.0)


def median(values: Sequence[float], default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.median(vals)) if vals else default


def quantile(values: Sequence[float], q: float, default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.quantile(np.asarray(vals, dtype=float), q)) if vals else default


def ensure_dirs() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)


def load_centers() -> tuple[list[dict[str, str]], dict[int, tuple[float, float]], dict[int, str], dict[int, str], dict[int, str]]:
    rows = read_csv(R1_UNIQUE_GT)
    centers: dict[int, tuple[float, float]] = {}
    pair_by_frame: dict[int, str] = {}
    status_by_frame: dict[int, str] = {}
    identity_by_frame: dict[int, str] = {}
    for row in rows:
        frame = parse_int(row["sar_frame"])
        if row.get("selected_center_x") == "" or row.get("included_in_heading_main_analysis") == "false":
            continue
        centers[frame] = (parse_float(row["selected_center_x"]), parse_float(row["selected_center_y"]))
        pair_by_frame[frame] = row.get("selected_pair_id", "")
        status_by_frame[frame] = row.get("center_selection_status", "")
        identity_by_frame[frame] = row.get("identity_consistency_status", "")
    return rows, centers, pair_by_frame, status_by_frame, identity_by_frame


def select_window(frame: int, centers: Mapping[int, tuple[float, float]], radius: int, causal: bool = False) -> list[int]:
    frames = sorted(centers)
    if causal:
        selected = [f for f in frames if 0 <= frame - f <= radius]
        if len(selected) < 3:
            selected = [f for f in frames if f <= frame][-5:]
    else:
        selected = [f for f in frames if abs(f - frame) <= radius]
        if len(selected) < 3:
            selected = sorted(frames, key=lambda f: abs(f - frame))[: min(5, len(frames))]
            selected = sorted(selected)
    return selected


def residual_components(
    observed_x: np.ndarray,
    observed_y: np.ndarray,
    pred_x: np.ndarray,
    pred_y: np.ndarray,
    heading_deg: float,
) -> tuple[float, float, float]:
    axis = axis_unit(heading_deg)
    perp = (-axis[1], axis[0])
    rx = observed_x - pred_x
    ry = observed_y - pred_y
    along = rx * axis[0] + ry * axis[1]
    cross = rx * perp[0] + ry * perp[1]
    total = np.sqrt(rx**2 + ry**2)
    return float(np.sqrt(np.mean(along**2))), float(np.sqrt(np.mean(cross**2))), float(np.sqrt(np.mean(total**2)))


def fit_line(
    frame: int,
    centers: Mapping[int, tuple[float, float]],
    *,
    radius: int = 8,
    causal: bool = False,
    omit_frame: int | None = None,
) -> dict[str, Any]:
    selected = [f for f in select_window(frame, centers, radius, causal) if f != omit_frame]
    if len(selected) < 2:
        return {
            "method": "history_only_line_tangent" if causal else "symmetric_local_line_tangent",
            "heading_deg": "",
            "speed_px_per_sar_frame": 0.0,
            "support_frame_count": len(selected),
            "support_frames": ";".join(str(f) for f in selected),
            "along_track_residual_px": 999.0,
            "cross_track_residual_px": 999.0,
            "total_residual_px": 999.0,
        }
    t = np.asarray([f - frame for f in selected], dtype=float)
    x = np.asarray([centers[f][0] for f in selected], dtype=float)
    y = np.asarray([centers[f][1] for f in selected], dtype=float)
    a = np.column_stack([t, np.ones_like(t)])
    coef_x, *_ = np.linalg.lstsq(a, x, rcond=None)
    coef_y, *_ = np.linalg.lstsq(a, y, rcond=None)
    vx, vy = float(coef_x[0]), float(coef_y[0])
    heading = directed_angle_deg((vx, vy))
    along, cross, total = residual_components(x, y, a @ coef_x, a @ coef_y, heading)
    return {
        "method": "history_only_line_tangent" if causal else "symmetric_local_line_tangent",
        "heading_deg": heading,
        "speed_px_per_sar_frame": math.hypot(vx, vy),
        "support_frame_count": len(selected),
        "support_frames": ";".join(str(f) for f in selected),
        "along_track_residual_px": along,
        "cross_track_residual_px": cross,
        "total_residual_px": total,
    }


def fit_quadratic(frame: int, centers: Mapping[int, tuple[float, float]], radius: int = 8) -> dict[str, Any]:
    selected = select_window(frame, centers, radius, causal=False)
    if len(selected) < 5:
        row = fit_line(frame, centers, radius=radius, causal=False)
        row["method"] = "local_quadratic_tangent_line_fallback"
        return row
    t = np.asarray([f - frame for f in selected], dtype=float)
    x = np.asarray([centers[f][0] for f in selected], dtype=float)
    y = np.asarray([centers[f][1] for f in selected], dtype=float)
    px = np.polyfit(t, x, 2)
    py = np.polyfit(t, y, 2)
    vx, vy = float(px[1]), float(py[1])
    heading = directed_angle_deg((vx, vy))
    along, cross, total = residual_components(x, y, np.polyval(px, t), np.polyval(py, t), heading)
    return {
        "method": "local_quadratic_tangent",
        "heading_deg": heading,
        "speed_px_per_sar_frame": math.hypot(vx, vy),
        "support_frame_count": len(selected),
        "support_frames": ";".join(str(f) for f in selected),
        "along_track_residual_px": along,
        "cross_track_residual_px": cross,
        "total_residual_px": total,
    }


def fit_median_displacement(frame: int, centers: Mapping[int, tuple[float, float]], radius: int = 8) -> dict[str, Any]:
    selected = select_window(frame, centers, radius, causal=False)
    disps: list[tuple[float, float]] = []
    for a, b in zip(selected, selected[1:]):
        delta = max(b - a, 1)
        disps.append(((centers[b][0] - centers[a][0]) / delta, (centers[b][1] - centers[a][1]) / delta))
    if not disps:
        return {
            "method": "robust_median_displacement_direction",
            "heading_deg": "",
            "speed_px_per_sar_frame": 0.0,
            "support_frame_count": len(selected),
            "support_frames": ";".join(str(f) for f in selected),
            "along_track_residual_px": 999.0,
            "cross_track_residual_px": 999.0,
            "total_residual_px": 999.0,
        }
    vx = median([v[0] for v in disps])
    vy = median([v[1] for v in disps])
    heading = directed_angle_deg((vx, vy))
    axis = axis_unit(heading)
    perp = (-axis[1], axis[0])
    along = [(dx - vx) * axis[0] + (dy - vy) * axis[1] for dx, dy in disps]
    cross = [(dx - vx) * perp[0] + (dy - vy) * perp[1] for dx, dy in disps]
    total = [math.hypot(dx - vx, dy - vy) for dx, dy in disps]
    return {
        "method": "robust_median_displacement_direction",
        "heading_deg": heading,
        "speed_px_per_sar_frame": math.hypot(vx, vy),
        "support_frame_count": len(selected),
        "support_frames": ";".join(str(f) for f in selected),
        "along_track_residual_px": float(np.sqrt(np.mean(np.asarray(along) ** 2))),
        "cross_track_residual_px": float(np.sqrt(np.mean(np.asarray(cross) ** 2))),
        "total_residual_px": float(np.sqrt(np.mean(np.asarray(total) ** 2))),
    }


def local_sign_stability(frame: int, centers: Mapping[int, tuple[float, float]], heading_deg: float, radius: int = 8) -> float:
    selected = select_window(frame, centers, radius, causal=False)
    axis = axis_unit(heading_deg)
    signs: list[int] = []
    for a, b in zip(selected, selected[1:]):
        dx = centers[b][0] - centers[a][0]
        dy = centers[b][1] - centers[a][1]
        signs.append(1 if dx * axis[0] + dy * axis[1] >= 0 else 0)
    if not signs:
        return 0.0
    pos = sum(signs) / len(signs)
    return max(pos, 1.0 - pos)


def nearest_gap(frame: int, centers: Mapping[int, tuple[float, float]]) -> int:
    frames = sorted(centers)
    prevs = [f for f in frames if f < frame]
    nexts = [f for f in frames if f > frame]
    gaps = []
    if prevs:
        gaps.append(frame - prevs[-1])
    if nexts:
        gaps.append(nexts[0] - frame)
    return max(gaps) if gaps else 0


def uncertainty_angles(frame: int, centers: Mapping[int, tuple[float, float]]) -> list[float]:
    angles: list[float] = []
    selected = select_window(frame, centers, 8, causal=False)
    for omit in selected:
        row = fit_line(frame, centers, radius=8, causal=False, omit_frame=omit)
        if row["heading_deg"] != "":
            angles.append(axis_angle_deg(parse_float(row["heading_deg"])))
    for seed in range(8):
        perturbed = dict(centers)
        local = dict(perturbed)
        for idx, f in enumerate(selected):
            amp = 0.35
            local[f] = (
                centers[f][0] + amp * math.sin((idx + 1) * (seed + 2)),
                centers[f][1] + amp * math.cos((idx + 3) * (seed + 1)),
            )
        row = fit_line(frame, local, radius=8, causal=False)
        if row["heading_deg"] != "":
            angles.append(axis_angle_deg(parse_float(row["heading_deg"])))
    return angles


def classify_observability(row: Mapping[str, Any], thresholds: Mapping[str, float]) -> str:
    if row["duplicate_conflict_status"] == "UNRESOLVED":
        return "UNRESOLVED"
    if parse_float(row["speed_px_per_sar_frame"]) < thresholds["min_speed_medium"]:
        return "UNRESOLVED"
    if parse_int(row["support_frame_count"]) < thresholds["min_support_medium"]:
        return "UNRESOLVED"
    if parse_float(row["trajectory_gap_size"]) > thresholds["max_gap_medium"]:
        return "UNRESOLVED"
    if parse_float(row["body_axis_axial_ci_width_deg"]) <= thresholds["max_ci_high"] and parse_float(row["method_consensus_axial_mad_deg"]) <= thresholds["max_mad_high"] and parse_float(row["cross_track_residual_px"]) <= thresholds["max_cross_high"] and parse_float(row["total_residual_px"]) <= thresholds["max_total_high"] and parse_int(row["support_frame_count"]) >= thresholds["min_support_high"] and parse_float(row["local_displacement_sign_stability"]) >= thresholds["min_sign_high"]:
        return "OBSERVABLE_HIGH"
    if parse_float(row["body_axis_axial_ci_width_deg"]) <= thresholds["max_ci_medium"] and parse_float(row["method_consensus_axial_mad_deg"]) <= thresholds["max_mad_medium"] and parse_float(row["total_residual_px"]) <= thresholds["max_total_medium"] and parse_float(row["local_displacement_sign_stability"]) >= thresholds["min_sign_medium"]:
        return "OBSERVABLE_MEDIUM"
    return "UNRESOLVED"


def build_heading_observability() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _, centers, pair_by_frame, status_by_frame, identity_by_frame = load_centers()
    base_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    for frame in sorted(centers):
        methods = [
            fit_line(frame, centers, radius=8, causal=False),
            fit_quadratic(frame, centers, radius=8),
            fit_line(frame, centers, radius=10, causal=True),
            fit_median_displacement(frame, centers, radius=8),
        ]
        method_angles = [axis_angle_deg(parse_float(row["heading_deg"])) for row in methods if row["heading_deg"] != ""]
        body_axis = axial_mean_deg(method_angles, default=0.0)
        symmetric = methods[0]
        ci_angles = uncertainty_angles(frame, centers) + method_angles
        ci_center = axial_mean_deg(ci_angles, default=body_axis)
        diffs = [axial_diff_deg(a, ci_center) for a in ci_angles]
        ci_width = min(90.0, 2.0 * quantile(diffs, 0.90, 45.0))
        ci_low = axis_angle_deg(ci_center - ci_width / 2.0)
        ci_high = axis_angle_deg(ci_center + ci_width / 2.0)
        method_mad = median([axial_diff_deg(a, body_axis) for a in method_angles], default=90.0)
        sign_stability = local_sign_stability(frame, centers, body_axis)
        row = {
            "pair_id": pair_by_frame.get(frame, ""),
            "sar_frame": frame,
            "split": frame_split(frame),
            "selected_center_x": fmt(centers[frame][0]),
            "selected_center_y": fmt(centers[frame][1]),
            "body_axis_proxy_deg": fmt(body_axis),
            "body_axis_axial_ci_low_deg": fmt(ci_low),
            "body_axis_axial_ci_high_deg": fmt(ci_high),
            "body_axis_axial_ci_width_deg": fmt(ci_width),
            "method_consensus_axial_mad_deg": fmt(method_mad),
            "speed_px_per_sar_frame": fmt(symmetric["speed_px_per_sar_frame"]),
            "along_track_residual_px": fmt(symmetric["along_track_residual_px"]),
            "cross_track_residual_px": fmt(symmetric["cross_track_residual_px"]),
            "total_residual_px": fmt(symmetric["total_residual_px"]),
            "support_frame_count": symmetric["support_frame_count"],
            "support_frames": symmetric["support_frames"],
            "trajectory_gap_size": nearest_gap(frame, centers),
            "local_displacement_sign_stability": fmt(sign_stability),
            "duplicate_conflict_status": status_by_frame.get(frame, ""),
            "identity_consistency_status": identity_by_frame.get(frame, ""),
            "heading_observability_status": "",
            "threshold_source": "calibration_sar_le_360",
            "diagnostic_scope": "posthoc_two_sided_tangent_audit_not_runtime_state",
        }
        base_rows.append(row)
        for method in methods:
            ablation_rows.append(
                {
                    "pair_id": pair_by_frame.get(frame, ""),
                    "sar_frame": frame,
                    "split": frame_split(frame),
                    "method": method["method"],
                    "body_axis_proxy_deg": fmt(axis_angle_deg(parse_float(method["heading_deg"])) if method["heading_deg"] != "" else ""),
                    "motion_heading_directed_deg": fmt(method["heading_deg"]),
                    "speed_px_per_sar_frame": fmt(method["speed_px_per_sar_frame"]),
                    "along_track_residual_px": fmt(method["along_track_residual_px"]),
                    "cross_track_residual_px": fmt(method["cross_track_residual_px"]),
                    "total_residual_px": fmt(method["total_residual_px"]),
                    "support_frame_count": method["support_frame_count"],
                    "support_frames": method["support_frames"],
                    "posthoc_or_runtime": "posthoc_diagnostic",
                    "used_for_main_body_axis_proxy": str(method["method"] == "symmetric_local_line_tangent").lower(),
                }
            )
        ablation_rows.append(
            {
                "pair_id": pair_by_frame.get(frame, ""),
                "sar_frame": frame,
                "split": frame_split(frame),
                "method": "leave_one_frame_out_plus_center_perturbation_uncertainty",
                "body_axis_proxy_deg": fmt(ci_center),
                "motion_heading_directed_deg": "",
                "speed_px_per_sar_frame": "",
                "along_track_residual_px": "",
                "cross_track_residual_px": "",
                "total_residual_px": "",
                "support_frame_count": len(ci_angles),
                "support_frames": "uncertainty_samples",
                "posthoc_or_runtime": "posthoc_uncertainty_audit",
                "used_for_main_body_axis_proxy": "false",
            }
        )

    cal = [row for row in base_rows if row["split"] == "calibration"]
    thresholds = {
        "max_ci_high": min(18.0, max(6.0, quantile([parse_float(r["body_axis_axial_ci_width_deg"]) for r in cal], 0.60, 10.0) * 1.20)),
        "max_mad_high": min(8.0, max(2.5, quantile([parse_float(r["method_consensus_axial_mad_deg"]) for r in cal], 0.60, 4.0) * 1.20)),
        "max_cross_high": min(4.5, max(1.5, quantile([parse_float(r["cross_track_residual_px"]) for r in cal], 0.60, 2.0) * 1.25)),
        "max_total_high": min(7.0, max(2.0, quantile([parse_float(r["total_residual_px"]) for r in cal], 0.60, 3.0) * 1.25)),
        "min_support_high": 7,
        "min_sign_high": 0.70,
        "max_ci_medium": 30.0,
        "max_mad_medium": 16.0,
        "max_total_medium": 11.0,
        "min_support_medium": 4,
        "min_speed_medium": max(0.75, quantile([parse_float(r["speed_px_per_sar_frame"]) for r in cal], 0.05, 1.0) * 0.50),
        "max_gap_medium": 4,
        "min_sign_medium": 0.58,
    }
    for row in base_rows:
        row["heading_observability_status"] = classify_observability(row, thresholds)
        row["observability_thresholds"] = ";".join(f"{k}={fmt(v)}" for k, v in thresholds.items())
    return base_rows, ablation_rows


def feature_indexes() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    feature_rows = read_csv(E0_R1_FEATURES)
    manifest_rows = read_csv(E0_R1_MANIFEST)
    return {row["region_id"]: row for row in feature_rows}, {row["region_id"]: row for row in manifest_rows}


def build_aspect_timeline(heading_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    subject_rows = read_csv(R1_SUBJECT_MANIFEST)
    vehicle_by_frame = {
        parse_int(row["sar_frame"]): row
        for row in subject_rows
        if row["subject_name"] == "vehicle_body_axis_reference"
    }
    rows: list[dict[str, Any]] = []
    for heading in heading_rows:
        frame = parse_int(heading["sar_frame"])
        subject = vehicle_by_frame.get(frame)
        if subject is None:
            continue
        body_axis = parse_float(heading["body_axis_proxy_deg"])
        local_range = parse_float(subject["local_range_axis_deg"])
        aspect = axial_diff_deg(body_axis, local_range)
        cx = parse_float(subject["center_x"])
        cy = parse_float(subject["center_y"])
        rows.append(
            {
                "pair_id": heading["pair_id"],
                "sar_frame": frame,
                "split": heading["split"],
                "body_axis_proxy_deg": fmt(body_axis),
                "local_range_axis_deg": fmt(local_range),
                "relative_aspect_angle_deg": fmt(aspect),
                "aspect_angle_ci_width_deg": heading["body_axis_axial_ci_width_deg"],
                "absolute_range_m_grid": fmt(math.hypot(cx, cy) * P0_PX_TO_M),
                "aspect_observability_status": heading["heading_observability_status"],
                "center_selection_status": subject["center_selection_status"],
                "diagnostic_scope": "2d_image_grid_relative_aspect_proxy",
            }
        )
    return rows


def descriptor_from_rows(subject: Mapping[str, str], feature: Mapping[str, str]) -> dict[str, Any]:
    mean_energy = parse_float(feature.get("mean_energy", subject.get("mean_energy", "")))
    energy_std = parse_float(feature.get("energy_std", ""))
    area_m2 = parse_float(feature.get("region_area_m2", ""))
    component_count = parse_float(feature.get("component_count", ""))
    near_far = parse_float(feature.get("near_far_energy_ratio", "1"))
    total = parse_float(feature.get("total_energy", ""))
    near = total * near_far / max(1.0 + near_far, 1e-9)
    far = total / max(1.0 + near_far, 1e-9)
    return {
        "total_energy": fmt(total),
        "mean_energy": fmt(mean_energy),
        "local_background_normalized_energy": fmt(parse_float(feature.get("local_background_normalized_energy", subject.get("local_background_normalized_energy", "")))),
        "high_energy_pixel_fraction": fmt(parse_float(feature.get("high_energy_pixel_fraction", subject.get("high_energy_pixel_fraction", "")))),
        "response_occupancy_ratio": fmt(parse_float(feature.get("response_occupancy_ratio", ""))),
        "inside_vs_ring_contrast": fmt(parse_float(feature.get("inside_ring_energy_ratio", ""))),
        "energy_entropy_proxy": fmt(1.0 / (1.0 + energy_std / max(abs(mean_energy), 1e-9))),
        "range_energy90_width_m": fmt(parse_float(feature.get("range_energy90_width_m", ""))),
        "azimuth_energy90_width_m": fmt(parse_float(feature.get("azimuth_energy90_width_m", ""))),
        "body_long_energy90_width_m": fmt(parse_float(feature.get("body_long_energy90_width_m", subject.get("body_long_energy90_width_m", "")))),
        "body_short_energy90_width_m": fmt(parse_float(feature.get("body_short_energy90_width_m", subject.get("body_short_energy90_width_m", "")))),
        "range_second_moment_width_m": fmt(parse_float(feature.get("range_second_moment_width_m", ""))),
        "azimuth_second_moment_width_m": fmt(parse_float(feature.get("azimuth_second_moment_width_m", ""))),
        "body_long_second_moment_width_m": fmt(parse_float(feature.get("body_long_second_moment_width_m", ""))),
        "body_short_second_moment_width_m": fmt(parse_float(feature.get("body_short_second_moment_width_m", ""))),
        "energy_centroid_range_offset_m": fmt(parse_float(feature.get("energy_centroid_range_m", subject.get("energy_centroid_range_m", "")))),
        "energy_centroid_azimuth_offset_m": fmt(parse_float(feature.get("energy_centroid_azimuth_m", subject.get("energy_centroid_azimuth_m", "")))),
        "energy_centroid_body_long_offset_m": fmt(parse_float(feature.get("energy_centroid_body_long_m", ""))),
        "energy_centroid_body_short_offset_m": fmt(parse_float(feature.get("energy_centroid_body_short_m", ""))),
        "response_principal_axis_deg": fmt(parse_float(feature.get("principal_axis_deg", subject.get("subject_principal_axis_deg", "")))),
        "principal_minus_body_axial_deg": fmt(parse_float(subject.get("principal_minus_body_axial_deg", feature.get("principal_axis_minus_body_axis_deg", "")))),
        "principal_minus_range_axial_deg": fmt(parse_float(subject.get("principal_minus_range_axial_deg", feature.get("principal_axis_minus_local_range_axis_deg", "")))),
        "response_compactness": fmt(parse_float(feature.get("response_compactness", subject.get("response_compactness", "")))),
        "response_linearity": fmt(parse_float(feature.get("response_linearity", subject.get("response_linearity", "")))),
        "response_fragment_count": fmt(component_count),
        "response_fragmentation_index": fmt(component_count / max(area_m2, 1e-9)),
        "radar_near_half_energy": fmt(near),
        "radar_far_half_energy": fmt(far),
        "near_far_energy_ratio": fmt(near_far),
    }


def build_response_descriptors(aspect_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    subject_rows = read_csv(R1_SUBJECT_MANIFEST)
    feature_index, manifest_index = feature_indexes()
    aspect_by_frame = {parse_int(row["sar_frame"]): row for row in aspect_rows}
    descriptor_rows: list[dict[str, Any]] = []
    for subject in subject_rows:
        feature = feature_index.get(subject["source_region_id"], {})
        aspect = aspect_by_frame.get(parse_int(subject["sar_frame"]), {})
        descriptor = descriptor_from_rows(subject, feature)
        descriptor_rows.append(
            {
                "subject_frame_id": subject["subject_frame_id"],
                "subject_name": subject["subject_name"],
                "pair_id": subject["pair_id"],
                "sar_frame": subject["sar_frame"],
                "split": subject["split"],
                "source_region_id": subject["source_region_id"],
                "posthoc_evaluation_label": subject["posthoc_evaluation_label"],
                "subject_motion_model": subject["subject_motion_model"],
                "persistent_subject_status": subject["persistent_subject_status"],
                "relative_aspect_angle_deg": aspect.get("relative_aspect_angle_deg", ""),
                "aspect_angle_ci_width_deg": aspect.get("aspect_angle_ci_width_deg", ""),
                "aspect_observability_status": aspect.get("aspect_observability_status", "UNRESOLVED"),
                "absolute_range_m_grid": aspect.get("absolute_range_m_grid", ""),
                "center_x": subject["center_x"],
                "center_y": subject["center_y"],
                **descriptor,
            }
        )

    corridor_rows: list[dict[str, Any]] = []
    for manifest in read_csv(E0_R1_MANIFEST):
        if manifest.get("family") != "METRIC_TRANSLATION":
            continue
        offset_axis = manifest.get("offset_axis", "")
        if offset_axis not in {"local_range", "local_azimuth", "body_long", "body_short"}:
            continue
        offset_m = parse_float(manifest.get(f"offset_m_{offset_axis}", manifest.get("offset_value", "")))
        if abs(offset_m) < 1e-9:
            continue
        frame = parse_int(manifest["sar_frame"])
        aspect = aspect_by_frame.get(frame, {})
        feature = feature_index.get(manifest["region_id"], {})
        pseudo_subject = {
            "mean_energy": feature.get("mean_energy", ""),
            "local_background_normalized_energy": feature.get("local_background_normalized_energy", ""),
            "high_energy_pixel_fraction": feature.get("high_energy_pixel_fraction", ""),
            "body_long_energy90_width_m": feature.get("body_long_energy90_width_m", ""),
            "body_short_energy90_width_m": feature.get("body_short_energy90_width_m", ""),
            "response_compactness": feature.get("response_compactness", ""),
            "response_linearity": feature.get("response_linearity", ""),
            "principal_minus_body_axial_deg": feature.get("principal_axis_minus_body_axis_deg", ""),
            "principal_minus_range_axial_deg": feature.get("principal_axis_minus_local_range_axis_deg", ""),
        }
        descriptor = descriptor_from_rows(pseudo_subject, feature)
        extent = max(parse_float(manifest.get("width_m_grid", "")), parse_float(manifest.get("height_m_grid", "")))
        overlap_status = "GT_ATTACHED_OFFSET_HAS_OVERLAP_RISK" if abs(offset_m) < extent / 2.0 else "GT_ATTACHED_OUTER_CORRIDOR_PROXY"
        corridor_rows.append(
            {
                "corridor_region_id": manifest["region_id"],
                "pair_id": manifest["pair_id"],
                "sar_frame": manifest["sar_frame"],
                "split": manifest["split"],
                "offset_axis": offset_axis,
                "offset_m": fmt(offset_m),
                "relative_aspect_angle_deg": aspect.get("relative_aspect_angle_deg", ""),
                "aspect_observability_status": aspect.get("aspect_observability_status", "UNRESOLVED"),
                "absolute_range_m_grid": aspect.get("absolute_range_m_grid", ""),
                "corridor_validity_status": overlap_status,
                "vehicle_overlap_policy": "not_claimed_clean_background_when_offset_smaller_than_subject_extent",
                **descriptor,
            }
        )

    persistent_strong = [
        {**row, "counterfactual_role": "persistent_world_fixed_strong_scatterer"}
        for row in descriptor_rows
        if row["subject_name"] == "fixed_strong_scatterer"
    ]
    fixed_controls = [
        {**row, "counterfactual_role": "world_fixed_background_aspect_control"}
        for row in descriptor_rows
        if row["subject_name"] in {"fixed_known_non_vehicle_N005", "fixed_strong_scatterer", "fixed_linear_structure"}
    ]
    return descriptor_rows, corridor_rows, persistent_strong, fixed_controls


def plot_points(
    path: Path,
    title: str,
    rows: Sequence[Mapping[str, Any]],
    x_field: str,
    y_field: str,
    *,
    group_field: str | None = None,
    width: int = 1100,
    height: int = 620,
) -> None:
    img = Image.new("RGB", (width, height), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    draw.text((28, 22), title, fill=(0, 0, 0))
    margin_l, margin_t, margin_r, margin_b = 86, 72, 36, 70
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    vals = []
    for row in rows:
        x = parse_float(row.get(x_field, ""), float("nan"))
        y = parse_float(row.get(y_field, ""), float("nan"))
        if math.isfinite(x) and math.isfinite(y):
            vals.append((x, y, str(row.get(group_field, "")) if group_field else ""))
    if not vals:
        draw.text((80, 180), "No finite data for this diagnostic.", fill=(160, 0, 0))
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        return
    xs = [v[0] for v in vals]
    ys = [v[1] for v in vals]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmax - xmin < 1e-9:
        xmax += 1.0
        xmin -= 1.0
    if ymax - ymin < 1e-9:
        ymax += 1.0
        ymin -= 1.0
    draw.rectangle((margin_l, margin_t, margin_l + plot_w, margin_t + plot_h), outline=(50, 50, 50))
    palette = {
        "calibration": (30, 110, 200),
        "guard": (230, 150, 0),
        "posthoc_diagnosis": (190, 40, 40),
        "OBSERVABLE_HIGH": (20, 150, 40),
        "OBSERVABLE_MEDIUM": (230, 150, 0),
        "UNRESOLVED": (170, 40, 40),
        "vehicle_body_axis_reference": (30, 110, 200),
        "fixed_strong_scatterer": (180, 60, 160),
        "fixed_linear_structure": (120, 120, 40),
        "fixed_known_non_vehicle_N005": (170, 80, 30),
    }
    for x, y, group in vals:
        px = margin_l + int((x - xmin) / (xmax - xmin) * plot_w)
        py = margin_t + plot_h - int((y - ymin) / (ymax - ymin) * plot_h)
        color = palette.get(group, (60, 60, 60))
        draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=color)
    draw.text((margin_l, height - 48), f"{x_field}: {fmt(xmin)} to {fmt(xmax)}", fill=(0, 0, 0))
    draw.text((margin_l + 360, height - 48), f"{y_field}: {fmt(ymin)} to {fmt(ymax)}", fill=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def render_text_visual(path: Path, title: str, lines: Sequence[str]) -> None:
    img = Image.new("RGB", (1100, 620), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    draw.text((30, 24), title, fill=(0, 0, 0))
    y = 78
    for line in lines:
        draw.text((48, y), line, fill=(0, 0, 0))
        y += 34
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def visual_row(visual_id: str, frame: Any, path: Path, requirement: str, conclusion_cn: str) -> dict[str, Any]:
    return {
        "visual_id": visual_id,
        "sar_frame": frame,
        "diagnostic_png": rel(path),
        "review_requirement": requirement,
        "review_status": "generated_for_e0_r2_review",
        "reviewer_conclusion_cn": conclusion_cn,
        "commit_policy": "do_not_commit_png_outputs",
    }


def build_visuals(
    heading_rows: Sequence[Mapping[str, Any]],
    aspect_rows: Sequence[Mapping[str, Any]],
    descriptor_rows: Sequence[Mapping[str, Any]],
    corridor_rows: Sequence[Mapping[str, Any]],
    persistent_strong: Sequence[Mapping[str, Any]],
    fixed_controls: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    vehicle = [row for row in descriptor_rows if row["subject_name"] == "vehicle_body_axis_reference"]
    paths = {
        "aspect_timeline": VISUAL_DIR / "aspect_timeline.png",
        "heading_observability_status": VISUAL_DIR / "heading_observability_status.png",
        "heading_ci_width": VISUAL_DIR / "heading_ci_width.png",
        "tangent_method_uncertainty": VISUAL_DIR / "tangent_method_uncertainty.png",
        "along_cross_residual": VISUAL_DIR / "along_cross_residual.png",
        "aspect_span_by_split": VISUAL_DIR / "aspect_span_by_split.png",
        "vehicle_energy_vs_aspect": VISUAL_DIR / "vehicle_energy_vs_aspect.png",
        "body_width_vs_aspect": VISUAL_DIR / "body_width_vs_aspect.png",
        "near_far_vs_aspect": VISUAL_DIR / "near_far_vs_aspect.png",
        "centroid_vs_aspect": VISUAL_DIR / "centroid_vs_aspect.png",
        "fragmentation_vs_aspect": VISUAL_DIR / "fragmentation_vs_aspect.png",
        "descriptor_trajectory": VISUAL_DIR / "descriptor_trajectory.png",
        "same_aspect_pair_candidates": VISUAL_DIR / "same_aspect_pair_candidates.png",
        "range_confounding_proxy": VISUAL_DIR / "range_confounding_proxy.png",
        "time_confounding_proxy": VISUAL_DIR / "time_confounding_proxy.png",
        "aspect_shuffle_control": VISUAL_DIR / "aspect_shuffle_control.png",
        "gt_attached_background_corridors": VISUAL_DIR / "gt_attached_background_corridors.png",
        "persistent_strong_counterfactual": VISUAL_DIR / "persistent_strong_counterfactual.png",
        "fixed_background_aspect_control": VISUAL_DIR / "fixed_background_aspect_control.png",
        "aspect_unobservable_cases": VISUAL_DIR / "aspect_unobservable_cases.png",
        "vehicle_vs_counterfactual_summary": VISUAL_DIR / "vehicle_vs_counterfactual_summary.png",
    }
    plot_points(paths["aspect_timeline"], "Relative aspect timeline", aspect_rows, "sar_frame", "relative_aspect_angle_deg", group_field="split")
    rows.append(visual_row("aspect_timeline", "", paths["aspect_timeline"], "relative aspect timeline", "相对观测角随帧号变化，但诊断段是否可用必须受可观测性状态和校准角域约束。"))
    plot_points(paths["heading_observability_status"], "Heading observability by frame", heading_rows, "sar_frame", "body_axis_proxy_deg", group_field="heading_observability_status")
    rows.append(visual_row("heading_observability_status", "", paths["heading_observability_status"], "heading observability states", "航向可观测性被分成高、中和未解析，不能把曲线轨迹本身等同于切线不可观测。"))
    plot_points(paths["heading_ci_width"], "Body-axis CI width", heading_rows, "sar_frame", "body_axis_axial_ci_width_deg", group_field="split")
    rows.append(visual_row("heading_ci_width", "", paths["heading_ci_width"], "body-axis uncertainty width", "轴向置信区间宽度直接限制 aspect 证据，宽区间帧只能作为弱诊断或未解析处理。"))
    plot_points(paths["tangent_method_uncertainty"], "Method consensus axial MAD", heading_rows, "sar_frame", "method_consensus_axial_mad_deg", group_field="split")
    rows.append(visual_row("tangent_method_uncertainty", "", paths["tangent_method_uncertainty"], "method consensus uncertainty", "四类切线方法的一致性用于约束航向代理，避免仅靠单一平滑器制造稳定方向。"))
    plot_points(paths["along_cross_residual"], "Cross-track residual", heading_rows, "sar_frame", "cross_track_residual_px", group_field="split")
    rows.append(visual_row("along_cross_residual", "", paths["along_cross_residual"], "along/cross residual audit", "横轨迹残差用于区分局部曲线运动和局部切线估计失败，残差高的帧不能支撑强 aspect 结论。"))
    plot_points(paths["aspect_span_by_split"], "Aspect angle by split", aspect_rows, "relative_aspect_angle_deg", "aspect_angle_ci_width_deg", group_field="split")
    rows.append(visual_row("aspect_span_by_split", "", paths["aspect_span_by_split"], "aspect span and uncertainty by split", "aspect 角域必须同时看跨度和不确定性；诊断段若落在校准外只能报告外推限制。"))
    plot_points(paths["vehicle_energy_vs_aspect"], "Vehicle normalized energy vs aspect", vehicle, "relative_aspect_angle_deg", "local_background_normalized_energy", group_field="split")
    rows.append(visual_row("vehicle_energy_vs_aspect", "", paths["vehicle_energy_vs_aspect"], "vehicle energy versus aspect", "车辆局部背景归一化能量可随 aspect 呈趋势，但需要被 range/time 反事实拆解后才能称为机制证据。"))
    plot_points(paths["body_width_vs_aspect"], "Vehicle body-long width vs aspect", vehicle, "relative_aspect_angle_deg", "body_long_energy90_width_m", group_field="split")
    rows.append(visual_row("body_width_vs_aspect", "", paths["body_width_vs_aspect"], "body-long/body-short width versus aspect", "车体轴向展宽随 aspect 的变化是多视角候选证据，但必须保持尺度支撑稳定。"))
    plot_points(paths["near_far_vs_aspect"], "Vehicle near/far energy ratio vs aspect", vehicle, "relative_aspect_angle_deg", "near_far_energy_ratio", group_field="split")
    rows.append(visual_row("near_far_vs_aspect", "", paths["near_far_vs_aspect"], "near/far response versus aspect", "近远侧能量比提供雷达向结构线索，但不单独等同于车头车尾语义。"))
    plot_points(paths["centroid_vs_aspect"], "Vehicle centroid body-long offset vs aspect", vehicle, "relative_aspect_angle_deg", "energy_centroid_body_long_offset_m", group_field="split")
    rows.append(visual_row("centroid_vs_aspect", "", paths["centroid_vs_aspect"], "centroid offset versus aspect", "能量质心沿车体轴的漂移用于检查响应场是否随视角发生内部重分布。"))
    plot_points(paths["fragmentation_vs_aspect"], "Vehicle fragmentation vs aspect", vehicle, "relative_aspect_angle_deg", "response_fragmentation_index", group_field="split")
    rows.append(visual_row("fragmentation_vs_aspect", "", paths["fragmentation_vs_aspect"], "fragmentation versus aspect", "碎裂度变化可以解释散射支撑分裂或合并，但需要与背景 corridor 对照。"))
    plot_points(paths["descriptor_trajectory"], "Descriptor trajectory over time", vehicle, "sar_frame", "body_long_energy90_width_m", group_field="split")
    rows.append(visual_row("descriptor_trajectory", "", paths["descriptor_trajectory"], "vehicle descriptor trajectory", "描述符随时间变化并不自动等于 aspect 规律，E0-R2 会单独审计时间顺序混杂。"))
    render_text_visual(paths["same_aspect_pair_candidates"], "Same-aspect repeatability candidate pairs", ["Pairs are selected later in evaluation:", "same aspect + similar range + separated time", "different aspect + similar range", "same aspect + different range", "This visual marks the audit design, not a fitted classifier."])
    rows.append(visual_row("same_aspect_pair_candidates", "", paths["same_aspect_pair_candidates"], "same-aspect repeatability pair design", "同 aspect 重复性只比较满足距离和时间间隔约束的帧对，不用总体趋势替代成对证据。"))
    plot_points(paths["range_confounding_proxy"], "Aspect and absolute range", aspect_rows, "relative_aspect_angle_deg", "absolute_range_m_grid", group_field="split")
    rows.append(visual_row("range_confounding_proxy", "", paths["range_confounding_proxy"], "range confounding visual audit", "若 aspect 与绝对距离强耦合，响应趋势不能直接解释为视角机制。"))
    plot_points(paths["time_confounding_proxy"], "Aspect over frame order", aspect_rows, "sar_frame", "relative_aspect_angle_deg", group_field="aspect_observability_status")
    rows.append(visual_row("time_confounding_proxy", "", paths["time_confounding_proxy"], "time-order confounding visual audit", "如果 aspect 基本随时间单调漂移，时间顺序本身就是必须剔除的混杂解释。"))
    render_text_visual(paths["aspect_shuffle_control"], "Aspect-shuffle control", ["Evaluation shuffles aspect order deterministically.", "Response descriptors remain fixed.", "If shuffled correlations match actual correlations,", "the aspect-response claim is not supported."])
    rows.append(visual_row("aspect_shuffle_control", "", paths["aspect_shuffle_control"], "aspect-shuffle control", "打乱 aspect 顺序的对照用于判断真实 aspect-response 对应是否强于随机时间配对。"))
    plot_points(paths["gt_attached_background_corridors"], "GT-attached corridor energy vs aspect", corridor_rows, "relative_aspect_angle_deg", "local_background_normalized_energy", group_field="offset_axis")
    rows.append(visual_row("gt_attached_background_corridors", "", paths["gt_attached_background_corridors"], "GT-attached background corridor counterfactual", "GT 附近随车移动的 corridor 若也呈同样趋势，会削弱车辆内部结构演化解释。"))
    plot_points(paths["persistent_strong_counterfactual"], "Persistent strong-scatterer counterfactual", persistent_strong, "relative_aspect_angle_deg", "local_background_normalized_energy", group_field="split")
    rows.append(visual_row("persistent_strong_counterfactual", "", paths["persistent_strong_counterfactual"], "persistent strong-scatterer counterfactual", "固定强散射体的响应若仅随车辆 aspect 代理变化，需判定为背景或时间混杂而非车辆机制。"))
    plot_points(paths["fixed_background_aspect_control"], "Fixed background controls", fixed_controls, "relative_aspect_angle_deg", "local_background_normalized_energy", group_field="subject_name")
    rows.append(visual_row("fixed_background_aspect_control", "", paths["fixed_background_aspect_control"], "fixed background aspect control", "N005、固定强散射和固定线性背景必须独立计算 aspect 耦合，不能继承车辆结论。"))
    unresolved = [row for row in heading_rows if row["heading_observability_status"] == "UNRESOLVED"]
    plot_points(paths["aspect_unobservable_cases"], "Aspect-unobservable cases", unresolved, "sar_frame", "body_axis_axial_ci_width_deg", group_field="split")
    rows.append(visual_row("aspect_unobservable_cases", "", paths["aspect_unobservable_cases"], "aspect-unobservable cases", "未解析帧被保留在账本中，不作为失败或通过来制造多视角结论。"))
    render_text_visual(paths["vehicle_vs_counterfactual_summary"], "Vehicle versus counterfactual audit summary", ["Vehicle response descriptors are compared against:", "1. GT-attached corridors", "2. persistent strong scatterer", "3. fixed N005 / strong / linear backgrounds", "4. aspect-shuffle, range, and time controls", "A positive claim requires all counterfactuals rejected."])
    rows.append(visual_row("vehicle_vs_counterfactual_summary", "", paths["vehicle_vs_counterfactual_summary"], "vehicle versus counterfactual summary", "车辆多视角机制必须同时压过 corridor、固定背景、强散射反事实和随机/距离/时间对照。"))
    return rows


def write_pre_eval_seal(output_map: Mapping[str, Path]) -> None:
    generator_sha = sha256_file(Path(__file__))
    input_paths = [R1_UNIQUE_GT, R1_AXIAL_HEADING, R1_SUBJECT_MANIFEST, R1_SUBJECT_TEMPORAL, R1_GATE_INTEGRITY, E0_R1_FEATURES, E0_R1_MANIFEST]
    input_digest = hashlib.sha256()
    for path in input_paths:
        input_digest.update(path.name.encode("utf-8"))
        input_digest.update(sha256_file(path).encode("utf-8"))
    rows = []
    for key in GENERATION_KEYS:
        path = output_map[key]
        rows.append(
            {
                "artifact_key": key,
                "path": rel(path),
                "sha256": sha256_file(path),
                "row_count": row_count(path),
                "seal_phase": "e0_r2_pre_eval_temporal_multi_aspect_freeze",
                "code_commit_sha": git_output(["rev-parse", "HEAD"]),
                "generator_source_sha256": generator_sha,
                "input_bundle_sha256": input_digest.hexdigest(),
                "allowed_inputs": "frozen_e0_r1_r1_csv;frozen_e0_r1_region_features;selected_gt_center_sequence",
                "forbidden_outputs": "detector;selector;ranking;final_box;gt_modification;training;cross_scene_claim",
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
                    "notes": "PNG files remain under ignored outputs/ and are not committed." if key == "visual_review_manifest" else "",
                }
            )
    write_csv(output_map["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def run_generation(output_map: Mapping[str, Path]) -> None:
    ensure_dirs()
    heading_rows, ablation_rows = build_heading_observability()
    aspect_rows = build_aspect_timeline(heading_rows)
    descriptor_rows, corridor_rows, persistent_strong, fixed_controls = build_response_descriptors(aspect_rows)
    visual_rows = build_visuals(heading_rows, aspect_rows, descriptor_rows, corridor_rows, persistent_strong, fixed_controls)
    write_csv(output_map["heading_observability"], heading_rows, HEADING_OBSERVABILITY_FIELDS)
    write_csv(output_map["heading_uncertainty_ablation"], ablation_rows, HEADING_ABLATION_FIELDS)
    write_csv(output_map["relative_aspect_timeline"], aspect_rows, ASPECT_TIMELINE_FIELDS)
    write_csv(output_map["vehicle_response_descriptors"], descriptor_rows, RESPONSE_DESCRIPTOR_FIELDS)
    write_csv(output_map["gt_attached_background_corridors"], corridor_rows, CORRIDOR_FIELDS)
    write_csv(output_map["persistent_strong_counterfactual"], persistent_strong, COUNTERFACTUAL_FIELDS)
    write_csv(output_map["fixed_background_aspect_control"], fixed_controls, COUNTERFACTUAL_FIELDS)
    write_csv(output_map["visual_review_manifest"], visual_rows, VISUAL_FIELDS)
    write_pre_eval_seal(output_map)
    write_frozen_manifest(output_map, "e0_r2_generation")
    counts = Counter(row["aspect_observability_status"] for row in aspect_rows)
    print(f"E0_R2 generation complete: aspect_frames={len(aspect_rows)} observability={dict(counts)} visuals={len(visual_rows)}")


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
    for key in GENERATION_KEYS:
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
    write_csv(OUTPUTS["replay_check"], results, REPLAY_FIELDS)
    write_frozen_manifest(OUTPUTS, "e0_r2_replay_verified")
    print(f"E0_R2_FROZEN_REPLAY_IDENTICAL={'PASS' if all(row['status'] == 'PASS' for row in results) else 'FAIL'}")


HEADING_OBSERVABILITY_FIELDS = [
    "pair_id",
    "sar_frame",
    "split",
    "selected_center_x",
    "selected_center_y",
    "body_axis_proxy_deg",
    "body_axis_axial_ci_low_deg",
    "body_axis_axial_ci_high_deg",
    "body_axis_axial_ci_width_deg",
    "method_consensus_axial_mad_deg",
    "speed_px_per_sar_frame",
    "along_track_residual_px",
    "cross_track_residual_px",
    "total_residual_px",
    "support_frame_count",
    "support_frames",
    "trajectory_gap_size",
    "local_displacement_sign_stability",
    "duplicate_conflict_status",
    "identity_consistency_status",
    "heading_observability_status",
    "observability_thresholds",
    "threshold_source",
    "diagnostic_scope",
]
HEADING_ABLATION_FIELDS = [
    "pair_id",
    "sar_frame",
    "split",
    "method",
    "body_axis_proxy_deg",
    "motion_heading_directed_deg",
    "speed_px_per_sar_frame",
    "along_track_residual_px",
    "cross_track_residual_px",
    "total_residual_px",
    "support_frame_count",
    "support_frames",
    "posthoc_or_runtime",
    "used_for_main_body_axis_proxy",
]
ASPECT_TIMELINE_FIELDS = [
    "pair_id",
    "sar_frame",
    "split",
    "body_axis_proxy_deg",
    "local_range_axis_deg",
    "relative_aspect_angle_deg",
    "aspect_angle_ci_width_deg",
    "absolute_range_m_grid",
    "aspect_observability_status",
    "center_selection_status",
    "diagnostic_scope",
]
RESPONSE_DESCRIPTOR_FIELDS = [
    "subject_frame_id",
    "subject_name",
    "pair_id",
    "sar_frame",
    "split",
    "source_region_id",
    "posthoc_evaluation_label",
    "subject_motion_model",
    "persistent_subject_status",
    "relative_aspect_angle_deg",
    "aspect_angle_ci_width_deg",
    "aspect_observability_status",
    "absolute_range_m_grid",
    "center_x",
    "center_y",
    *DESCRIPTOR_FIELDS,
]
CORRIDOR_FIELDS = [
    "corridor_region_id",
    "pair_id",
    "sar_frame",
    "split",
    "offset_axis",
    "offset_m",
    "relative_aspect_angle_deg",
    "aspect_observability_status",
    "absolute_range_m_grid",
    "corridor_validity_status",
    "vehicle_overlap_policy",
    *DESCRIPTOR_FIELDS,
]
COUNTERFACTUAL_FIELDS = [
    "subject_frame_id",
    "subject_name",
    "pair_id",
    "sar_frame",
    "split",
    "source_region_id",
    "posthoc_evaluation_label",
    "subject_motion_model",
    "persistent_subject_status",
    "relative_aspect_angle_deg",
    "aspect_angle_ci_width_deg",
    "aspect_observability_status",
    "absolute_range_m_grid",
    "center_x",
    "center_y",
    *DESCRIPTOR_FIELDS,
    "counterfactual_role",
]
VISUAL_FIELDS = ["visual_id", "sar_frame", "diagnostic_png", "review_requirement", "review_status", "reviewer_conclusion_cn", "commit_policy"]
PRE_EVAL_SEAL_FIELDS = ["artifact_key", "path", "sha256", "row_count", "seal_phase", "code_commit_sha", "generator_source_sha256", "input_bundle_sha256", "allowed_inputs", "forbidden_outputs"]
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
