"""Generate E0-R1-R1 symmetric hard-negative and axial-heading artifacts.

This is a local correction over frozen E0-R1 outputs. It audits duplicate GT
centers, separates directed motion from 180-degree body-axis semantics, and
generates subject-specific translation surfaces for vehicles and hard
negatives with the same metric grid. It does not create a selector, ranker,
final box, annotation, GT edit, training signal, or cross-scene claim.
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

import run_oty2_wgv3_6b_e0_gm017_metric_region_contrast_generate as e0


DATE = "20260712"
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
START_COMMIT = "76029c558a7706bd6c460b8eb31749cce75406af"
P0_PX_TO_M = 0.03
OFFSET_GRID_M = [-1.00, -0.75, -0.45, 0.00, 0.45, 0.75, 1.00]

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_e0_r1_r1_gm017_symmetric_gate_{DATE}"
VISUAL_DIR = OUTPUT_DIR / "visual_review"
REPLAY_DIR = OUTPUT_DIR / "_verify_replay_tmp"

E0_R1_FEATURES = SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_feature_table_{DATE}.csv"
E0_R1_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_manifest_{DATE}.csv"

OUTPUTS = {
    "correction_audit": SAMPLES_DIR / f"e0_r1_r1_e0_r1_correction_audit_{DATE}.csv",
    "unique_gt_center_sequence": SAMPLES_DIR / f"e0_r1_r1_unique_gt_center_sequence_{DATE}.csv",
    "gt_conflict_audit": SAMPLES_DIR / f"e0_r1_r1_gt_conflict_audit_{DATE}.csv",
    "directed_motion_heading": SAMPLES_DIR / f"e0_r1_r1_directed_motion_heading_{DATE}.csv",
    "axial_body_heading": SAMPLES_DIR / f"e0_r1_r1_axial_body_heading_{DATE}.csv",
    "heading_method_ablation": SAMPLES_DIR / f"e0_r1_r1_heading_method_ablation_{DATE}.csv",
    "subject_manifest": SAMPLES_DIR / f"e0_r1_r1_subject_manifest_{DATE}.csv",
    "subject_translation_surfaces": SAMPLES_DIR / f"e0_r1_r1_subject_translation_surfaces_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"e0_r1_r1_visual_review_manifest_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"e0_r1_r1_pre_eval_seal_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"e0_r1_r1_replay_check_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"e0_r1_r1_frozen_manifest_{DATE}.csv",
}

GENERATION_KEYS = [
    "correction_audit",
    "unique_gt_center_sequence",
    "gt_conflict_audit",
    "directed_motion_heading",
    "axial_body_heading",
    "heading_method_ablation",
    "subject_manifest",
    "subject_translation_surfaces",
]

SUBJECTS = [
    {
        "subject_name": "vehicle_body_axis_reference",
        "short": "veh",
        "variant": "body_axis_reference",
        "motion_model": "GT_ATTACHED_MOVING_SUBJECT",
        "persistent_subject_status": "PERSISTENT_MOVING_GT_ATTACHED",
        "posthoc_evaluation_label": "vehicle",
    },
    {
        "subject_name": "matched_ordinary_background",
        "short": "mob",
        "variant": "matched_ordinary_background_same_area",
        "motion_model": "FRAMEWISE_MATCHED_CONTROL_NO_TRACK",
        "persistent_subject_status": "FRAMEWISE_MATCHED_CONTROL_NO_TRACK",
        "posthoc_evaluation_label": "negative",
    },
    {
        "subject_name": "matched_strong_scatterer_background",
        "short": "mss",
        "variant": "matched_strong_scatterer_background_same_area",
        "motion_model": "FRAMEWISE_MATCHED_CONTROL_NO_TRACK",
        "persistent_subject_status": "FRAMEWISE_MATCHED_CONTROL_NO_TRACK",
        "posthoc_evaluation_label": "negative",
    },
    {
        "subject_name": "matched_linear_structure_background",
        "short": "mls",
        "variant": "matched_linear_structure_background_same_area",
        "motion_model": "FRAMEWISE_MATCHED_CONTROL_NO_TRACK",
        "persistent_subject_status": "FRAMEWISE_MATCHED_CONTROL_NO_TRACK",
        "posthoc_evaluation_label": "negative",
    },
    {
        "subject_name": "fixed_known_non_vehicle_N005",
        "short": "n005",
        "variant": "fixed_known_non_vehicle_same_area",
        "motion_model": "WORLD_FIXED_SUBJECT",
        "persistent_subject_status": "PERSISTENT_WORLD_FIXED",
        "posthoc_evaluation_label": "negative",
    },
    {
        "subject_name": "fixed_strong_scatterer",
        "short": "fss",
        "variant": "fixed_strong_scatterer_background_same_area",
        "motion_model": "WORLD_FIXED_SUBJECT",
        "persistent_subject_status": "PERSISTENT_WORLD_FIXED",
        "posthoc_evaluation_label": "negative",
    },
    {
        "subject_name": "fixed_linear_structure",
        "short": "fls",
        "variant": "fixed_linear_structure_background_same_area",
        "motion_model": "WORLD_FIXED_SUBJECT",
        "persistent_subject_status": "PERSISTENT_WORLD_FIXED",
        "posthoc_evaluation_label": "negative",
    },
]


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


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


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
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def ensure_dirs() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)


def wrap180(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def directed_angle_deg(vec: tuple[float, float]) -> float:
    if math.hypot(vec[0], vec[1]) <= 1e-9:
        return 0.0
    return wrap180(math.degrees(math.atan2(vec[1], vec[0])))


def axis_angle_deg(angle: float) -> float:
    return angle % 180.0


def axial_diff_deg(a: float, b: float) -> float:
    return abs(((axis_angle_deg(a) - axis_angle_deg(b) + 90.0) % 180.0) - 90.0)


def unit_from_angle(angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return math.cos(rad), math.sin(rad)


def unit(vec: tuple[float, float]) -> tuple[float, float]:
    norm = math.hypot(vec[0], vec[1])
    if norm <= 1e-9:
        return 1.0, 0.0
    return vec[0] / norm, vec[1] / norm


def median(values: Sequence[float], default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.median(vals)) if vals else default


def quantile(values: Sequence[float], q: float, default: float = 0.0) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.quantile(np.asarray(vals, dtype=float), q)) if vals else default


def center_from_context(ctx: e0.GtContext) -> tuple[float, float]:
    return ctx.cx, ctx.cy


def weak_correspondence(row: Mapping[str, str]) -> bool:
    text = ";".join(str(row.get(field, "")) for field in ["blocked_reason", "visibility_state", "notes", "review_status"])
    return "weak" in text.lower()


def build_center_audit() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[e0.GtContext], dict[int, str]]:
    rows = e0.target_rows()
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[parse_int(row.get("sar_frame"))].append(row)

    sequence_rows: list[dict[str, Any]] = []
    conflict_rows: list[dict[str, Any]] = []
    selected_contexts: list[e0.GtContext] = []
    selected_pair_by_frame: dict[int, str] = {}

    previous_center: tuple[float, float] | None = None
    for frame in sorted(grouped):
        candidates = sorted(grouped[frame], key=lambda row: row.get("pair_id", ""))
        ctxs = [e0.make_context(row) for row in candidates]
        candidate_centers = [f"{ctx.pair_id}:{ctx.sar_gt_id}@({fmt(ctx.cx, 3)},{fmt(ctx.cy, 3)})" for ctx in ctxs]
        selected: e0.GtContext | None = None
        status = "UNRESOLVED"
        identity_status = "UNRESOLVED"

        if len(ctxs) == 1:
            selected = ctxs[0]
            status = "UNIQUE_GT_CENTER"
            identity_status = "single_pair_single_gt"
        else:
            non_weak = [(row, ctx) for row, ctx in zip(candidates, ctxs) if not weak_correspondence(row)]
            max_pairwise_delta = 0.0
            for i, ctx_a in enumerate(ctxs):
                for ctx_b in ctxs[i + 1 :]:
                    max_pairwise_delta = max(max_pairwise_delta, math.hypot(ctx_a.cx - ctx_b.cx, ctx_a.cy - ctx_b.cy))
            if len(non_weak) == 1:
                selected = non_weak[0][1]
                status = "WEAK_CORRESPONDENCE_EXCLUDED"
                identity_status = "duplicate_frame_primary_thread_selected_weak_correspondence_excluded"
            elif max_pairwise_delta <= 2.0:
                selected = ctxs[0]
                status = "DUPLICATE_SAME_OBJECT_CONSISTENT"
                identity_status = "duplicate_centers_within_2px_first_pair_retained"
            elif previous_center is not None:
                selected = min(ctxs, key=lambda ctx: math.hypot(ctx.cx - previous_center[0], ctx.cy - previous_center[1]))
                status = "MULTI_GT_IDENTITY_CONFLICT"
                identity_status = "nearest_temporal_continuity_candidate_selected_for_audit_only"
            else:
                selected = None
                status = "MULTI_GT_IDENTITY_CONFLICT"
                identity_status = "unresolved_no_prior_continuity"

        if selected is not None:
            previous_center = center_from_context(selected)
            selected_contexts.append(selected)
            selected_pair_by_frame[frame] = selected.pair_id

        sequence_rows.append(
            {
                "sar_frame": frame,
                "gt_row_count": len(ctxs),
                "candidate_pair_ids": ";".join(ctx.pair_id for ctx in ctxs),
                "candidate_centers": ";".join(candidate_centers),
                "center_selection_status": status,
                "selected_pair_id": selected.pair_id if selected else "",
                "selected_sar_gt_id": selected.sar_gt_id if selected else "",
                "selected_center_x": fmt(selected.cx if selected else ""),
                "selected_center_y": fmt(selected.cy if selected else ""),
                "identity_consistency_status": identity_status,
                "included_in_heading_main_analysis": str(selected is not None and status != "UNRESOLVED").lower(),
                "selection_inputs": "pair_identity;existing_physical_thread;time_continuity;weak_correspondence_flag;visual_review",
                "gt_modification": "false",
            }
        )

        for row, ctx in zip(candidates, ctxs):
            selected_flag = selected is not None and ctx.pair_id == selected.pair_id
            conflict_rows.append(
                {
                    "sar_frame": frame,
                    "pair_id": ctx.pair_id,
                    "sar_gt_id": ctx.sar_gt_id,
                    "center_x": fmt(ctx.cx),
                    "center_y": fmt(ctx.cy),
                    "weak_correspondence": str(weak_correspondence(row)).lower(),
                    "frame_selection_status": status,
                    "candidate_decision": "SELECTED" if selected_flag else ("EXCLUDED_WEAK_CORRESPONDENCE" if weak_correspondence(row) else "EXCLUDED_DUPLICATE_CONFLICT"),
                    "identity_consistency_status": identity_status,
                    "visual_review_required": str(frame == 336 or len(ctxs) > 1).lower(),
                }
            )

    return sequence_rows, conflict_rows, selected_contexts, selected_pair_by_frame


def local_line_fit(
    frame: int,
    centers: Mapping[int, tuple[float, float]],
    *,
    radius: int = 8,
    causal: bool = False,
) -> dict[str, Any]:
    frames = sorted(centers)
    if causal:
        selected = [f for f in frames if 0 <= frame - f <= radius]
    else:
        selected = [f for f in frames if abs(f - frame) <= radius]
    if len(selected) < 3:
        selected = sorted(frames, key=lambda f: abs(f - frame))[: min(5, len(frames))]
        selected = sorted(selected)
    if causal and len(selected) < 3:
        selected = [f for f in frames if f <= frame][-5:]
    if len(selected) < 2:
        return {"heading": "", "speed": 0.0, "residual": 999.0, "support": len(selected), "method": "line_fit"}

    t0 = float(frame)
    t = np.asarray([f - t0 for f in selected], dtype=float)
    x = np.asarray([centers[f][0] for f in selected], dtype=float)
    y = np.asarray([centers[f][1] for f in selected], dtype=float)
    a = np.column_stack([t, np.ones_like(t)])
    coef_x, *_ = np.linalg.lstsq(a, x, rcond=None)
    coef_y, *_ = np.linalg.lstsq(a, y, rcond=None)
    pred_x = a @ coef_x
    pred_y = a @ coef_y
    residual = float(np.sqrt(np.mean((pred_x - x) ** 2 + (pred_y - y) ** 2)))
    vx, vy = float(coef_x[0]), float(coef_y[0])
    return {
        "heading": directed_angle_deg((vx, vy)),
        "speed": math.hypot(vx, vy),
        "residual": residual,
        "support": len(selected),
        "support_frames": ";".join(str(f) for f in selected),
        "method": "history_only_line_fit" if causal else "symmetric_line_fit",
    }


def local_quadratic_fit(frame: int, centers: Mapping[int, tuple[float, float]], radius: int = 8) -> dict[str, Any]:
    selected = [f for f in sorted(centers) if abs(f - frame) <= radius]
    if len(selected) < 5:
        return local_line_fit(frame, centers, radius=radius, causal=False) | {"method": "line_fallback_for_quadratic"}
    t = np.asarray([f - frame for f in selected], dtype=float)
    x = np.asarray([centers[f][0] for f in selected], dtype=float)
    y = np.asarray([centers[f][1] for f in selected], dtype=float)
    px = np.polyfit(t, x, 2)
    py = np.polyfit(t, y, 2)
    pred_x = np.polyval(px, t)
    pred_y = np.polyval(py, t)
    residual = float(np.sqrt(np.mean((pred_x - x) ** 2 + (pred_y - y) ** 2)))
    vx, vy = float(px[1]), float(py[1])
    return {
        "heading": directed_angle_deg((vx, vy)),
        "speed": math.hypot(vx, vy),
        "residual": residual,
        "support": len(selected),
        "support_frames": ";".join(str(f) for f in selected),
        "method": "local_quadratic_fit",
    }


def median_displacement_heading(frame: int, centers: Mapping[int, tuple[float, float]], radius: int = 8) -> dict[str, Any]:
    frames = [f for f in sorted(centers) if abs(f - frame) <= radius]
    disps: list[tuple[float, float]] = []
    for a, b in zip(frames, frames[1:]):
        delta = max(b - a, 1)
        disps.append(((centers[b][0] - centers[a][0]) / delta, (centers[b][1] - centers[a][1]) / delta))
    if not disps:
        return {"heading": "", "speed": 0.0, "residual": 999.0, "support": 0, "support_frames": "", "method": "median_displacement_direction"}
    vx = median([d[0] for d in disps])
    vy = median([d[1] for d in disps])
    residual = median([math.hypot(d[0] - vx, d[1] - vy) for d in disps])
    return {
        "heading": directed_angle_deg((vx, vy)),
        "speed": math.hypot(vx, vy),
        "residual": residual,
        "support": len(frames),
        "support_frames": ";".join(str(f) for f in frames),
        "method": "robust_median_displacement_direction",
    }


def displacement_sign_stability(frame: int, centers: Mapping[int, tuple[float, float]], heading: float, radius: int = 8) -> float:
    axis = unit_from_angle(heading)
    frames = [f for f in sorted(centers) if abs(f - frame) <= radius]
    signs = []
    for a, b in zip(frames, frames[1:]):
        dx = centers[b][0] - centers[a][0]
        dy = centers[b][1] - centers[a][1]
        signs.append(1.0 if dx * axis[0] + dy * axis[1] >= 0 else 0.0)
    if not signs:
        return 0.0
    return max(float(np.mean(signs)), 1.0 - float(np.mean(signs)))


def curvature_for_frame(frame: int, centers: Mapping[int, tuple[float, float]]) -> tuple[float, float]:
    frames = sorted(centers)
    prevs = [f for f in frames if f < frame]
    nexts = [f for f in frames if f > frame]
    if not prevs or not nexts:
        return 0.0, 0.0
    pf, nf = prevs[-1], nexts[0]
    v1 = ((centers[frame][0] - centers[pf][0]) / max(frame - pf, 1), (centers[frame][1] - centers[pf][1]) / max(frame - pf, 1))
    v2 = ((centers[nf][0] - centers[frame][0]) / max(nf - frame, 1), (centers[nf][1] - centers[frame][1]) / max(nf - frame, 1))
    h1 = directed_angle_deg(v1)
    h2 = directed_angle_deg(v2)
    return abs(wrap180(h2 - h1)), axial_diff_deg(h2, h1)


def build_heading_rows(
    sequence_rows: Sequence[Mapping[str, Any]],
    selected_contexts: Sequence[e0.GtContext],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    centers = {ctx.sar_frame: (ctx.cx, ctx.cy) for ctx in selected_contexts}
    ctx_by_frame = {ctx.sar_frame: ctx for ctx in selected_contexts}
    status_by_frame = {parse_int(row["sar_frame"]): row for row in sequence_rows}
    frames = sorted(centers)

    raw_stats: dict[int, dict[str, Any]] = {}
    for idx, frame in enumerate(frames):
        if idx == 0:
            raw_stats[frame] = {"delta_frame": "", "raw_heading": "", "raw_speed": 0.0, "gap": 0}
            continue
        prev = frames[idx - 1]
        delta = max(frame - prev, 1)
        vx = (centers[frame][0] - centers[prev][0]) / delta
        vy = (centers[frame][1] - centers[prev][1]) / delta
        raw_stats[frame] = {"delta_frame": delta, "raw_heading": directed_angle_deg((vx, vy)), "raw_speed": math.hypot(vx, vy), "gap": delta}

    method_by_frame: dict[int, dict[str, dict[str, Any]]] = {}
    for frame in frames:
        method_by_frame[frame] = {
            "raw_selected_gt_delta": {
                "method": "raw_selected_gt_delta",
                "heading": raw_stats[frame]["raw_heading"],
                "speed": raw_stats[frame]["raw_speed"],
                "residual": 0.0,
                "support": 2 if raw_stats[frame]["delta_frame"] != "" else 1,
                "support_frames": "",
            },
            "symmetric_line_fit": local_line_fit(frame, centers, causal=False),
            "local_quadratic_fit": local_quadratic_fit(frame, centers),
            "history_only_line_fit": local_line_fit(frame, centers, causal=True),
            "robust_median_displacement_direction": median_displacement_heading(frame, centers),
        }

    calibration_frames = [frame for frame in frames if frame <= 360]
    symmetric_cal = [method_by_frame[frame]["symmetric_line_fit"] for frame in calibration_frames]
    min_speed = max(0.5, quantile([parse_float(row["speed"]) for row in symmetric_cal], 0.10, 1.0) * 0.50)
    max_residual = max(3.0, quantile([parse_float(row["residual"]) for row in symmetric_cal], 0.90, 3.0) * 1.25)
    axial_curvatures = [curvature_for_frame(frame, centers)[1] for frame in calibration_frames]
    max_axial_curvature = min(45.0, max(10.0, quantile(axial_curvatures, 0.90, 12.0) * 1.25))
    max_raw_smooth = 45.0

    directed_rows: list[dict[str, Any]] = []
    axial_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []

    for frame in frames:
        ctx = ctx_by_frame[frame]
        seq = status_by_frame[frame]
        sym = method_by_frame[frame]["symmetric_line_fit"]
        hist = method_by_frame[frame]["history_only_line_fit"]
        raw = method_by_frame[frame]["raw_selected_gt_delta"]
        directed_heading = parse_float(sym["heading"])
        directed_curvature, axial_curvature = curvature_for_frame(frame, centers)
        raw_vs_smooth = axial_diff_deg(parse_float(raw["heading"], directed_heading), directed_heading) if raw["heading"] != "" else 0.0
        history_vs_symmetric = axial_diff_deg(parse_float(hist["heading"], directed_heading), directed_heading) if hist["heading"] != "" else 0.0
        sign_stability = displacement_sign_stability(frame, centers, directed_heading)
        gap = parse_int(raw_stats[frame]["gap"], 0)

        high = (
            parse_float(sym["speed"]) >= min_speed
            and parse_float(sym["residual"]) <= max_residual
            and parse_int(sym["support"]) >= 5
            and axial_curvature <= max_axial_curvature
            and raw_vs_smooth <= max_raw_smooth
            and gap <= 3
            and sign_stability >= 0.70
            and seq["center_selection_status"] != "UNRESOLVED"
        )
        medium = (
            parse_float(sym["speed"]) >= min_speed * 0.75
            and parse_float(sym["residual"]) <= max_residual * 1.75
            and parse_int(sym["support"]) >= 4
            and axial_curvature <= max_axial_curvature * 1.75
            and seq["center_selection_status"] != "UNRESOLVED"
        )
        confidence = "HIGH" if high else ("MEDIUM" if medium else "LOW")

        directed_rows.append(
            {
                "pair_id": ctx.pair_id,
                "sar_frame": frame,
                "split": frame_split(frame),
                "selected_center_x": fmt(ctx.cx),
                "selected_center_y": fmt(ctx.cy),
                "center_selection_status": seq["center_selection_status"],
                "delta_frame": raw_stats[frame]["delta_frame"],
                "velocity_px_per_sar_frame": fmt(parse_float(sym["speed"])),
                "raw_delta_heading_directed_deg": fmt(raw["heading"]),
                "motion_heading_directed_deg": fmt(directed_heading),
                "history_only_heading_directed_deg": fmt(hist["heading"]),
                "local_quadratic_heading_directed_deg": fmt(method_by_frame[frame]["local_quadratic_fit"]["heading"]),
                "median_displacement_heading_directed_deg": fmt(method_by_frame[frame]["robust_median_displacement_direction"]["heading"]),
                "fit_residual_px": fmt(sym["residual"]),
                "support_frame_count": sym["support"],
                "trajectory_gap_size": gap,
                "local_displacement_sign_stability": fmt(sign_stability),
                "heading_confidence": confidence,
                "threshold_source": "calibration_sar_le_360",
                "diagnostic_scope": "posthoc_not_causal_runtime_state",
            }
        )

        axial_rows.append(
            {
                "pair_id": ctx.pair_id,
                "sar_frame": frame,
                "split": frame_split(frame),
                "body_axis_proxy_deg": fmt(axis_angle_deg(directed_heading)),
                "motion_heading_directed_deg": fmt(directed_heading),
                "raw_directed_curvature_deg": fmt(directed_curvature),
                "axial_curvature_deg": fmt(axial_curvature),
                "raw_vs_smoothed_axial_difference_deg": fmt(raw_vs_smooth),
                "history_vs_symmetric_axial_difference_deg": fmt(history_vs_symmetric),
                "speed_px_per_sar_frame": fmt(parse_float(sym["speed"])),
                "fit_residual_px": fmt(sym["residual"]),
                "support_frame_count": sym["support"],
                "duplicate_conflict_status": seq["center_selection_status"],
                "trajectory_gap_size": gap,
                "local_displacement_sign_stability": fmt(sign_stability),
                "heading_confidence": confidence,
                "confidence_rule_version": "e0_r1_r1_axial_confidence_v1_calibration_frozen",
                "calibration_min_speed_px_per_sar_frame": fmt(min_speed),
                "calibration_max_fit_residual_px": fmt(max_residual),
                "calibration_max_axial_curvature_deg": fmt(max_axial_curvature),
                "axis_semantics": "body_axis_180_degree_period",
            }
        )

        for method_name, method in method_by_frame[frame].items():
            heading = method.get("heading", "")
            ablation_rows.append(
                {
                    "pair_id": ctx.pair_id,
                    "sar_frame": frame,
                    "split": frame_split(frame),
                    "method": method_name,
                    "motion_heading_directed_deg": fmt(heading),
                    "body_axis_proxy_deg": fmt(axis_angle_deg(parse_float(heading))) if heading != "" else "",
                    "speed_px_per_sar_frame": fmt(method.get("speed")),
                    "fit_residual_px": fmt(method.get("residual")),
                    "support_frame_count": method.get("support"),
                    "support_frames": method.get("support_frames", ""),
                    "posthoc_or_runtime": "posthoc_diagnostic" if "symmetric" in method_name or "quadratic" in method_name else "history_only_sensitivity" if "history" in method_name else "raw_measurement",
                    "used_for_main_body_axis_proxy": str(method_name == "symmetric_line_fit").lower(),
                }
            )

    return directed_rows, axial_rows, ablation_rows


def old_feature_indexes() -> tuple[dict[tuple[str, str], dict[str, str]], dict[tuple[str, str], dict[str, str]]]:
    features = read_csv(E0_R1_FEATURES)
    manifest = read_csv(E0_R1_MANIFEST)
    feature_by_pair_variant = {(row["pair_id"], row["variant"]): row for row in features}
    manifest_by_pair_variant = {(row["pair_id"], row["variant"]): row for row in manifest}
    return feature_by_pair_variant, manifest_by_pair_variant


def frame_background_denominators(
    selected_contexts: Sequence[e0.GtContext],
    feature_by_pair_variant: Mapping[tuple[str, str], Mapping[str, str]],
) -> dict[int, float]:
    denominators: dict[int, float] = {}
    negative_variants = [subject["variant"] for subject in SUBJECTS if subject["posthoc_evaluation_label"] == "negative"]
    for ctx in selected_contexts:
        values = [
            parse_float(feature_by_pair_variant.get((ctx.pair_id, variant), {}).get("mean_energy"))
            for variant in negative_variants
            if (ctx.pair_id, variant) in feature_by_pair_variant
        ]
        denominators[ctx.sar_frame] = max(median(values, 1.0), 1e-9)
    return denominators


def build_subject_manifest(
    selected_contexts: Sequence[e0.GtContext],
    axial_rows: Sequence[Mapping[str, Any]],
    feature_by_pair_variant: Mapping[tuple[str, str], Mapping[str, str]],
    manifest_by_pair_variant: Mapping[tuple[str, str], Mapping[str, str]],
    sequence_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    axial_by_frame = {parse_int(row["sar_frame"]): row for row in axial_rows}
    seq_by_frame = {parse_int(row["sar_frame"]): row for row in sequence_rows}
    rows: list[dict[str, Any]] = []
    for ctx in selected_contexts:
        axial = axial_by_frame[ctx.sar_frame]
        body_axis = parse_float(axial.get("body_axis_proxy_deg"))
        motion_heading = parse_float(axial.get("motion_heading_directed_deg"))
        for subject in SUBJECTS:
            feature = feature_by_pair_variant.get((ctx.pair_id, subject["variant"]))
            manifest = manifest_by_pair_variant.get((ctx.pair_id, subject["variant"]))
            if feature is None or manifest is None:
                continue
            center_x = parse_float(manifest.get("center_x"))
            center_y = parse_float(manifest.get("center_y"))
            width = parse_float(manifest.get("width_px"))
            height = parse_float(manifest.get("height_px"))
            angle = parse_float(manifest.get("angle_deg"))
            range_unit = unit((center_x - e0.FAN_CENTER_X, center_y - e0.FAN_CENTER_Y))
            local_range_axis = axis_angle_deg(directed_angle_deg(range_unit))
            principal_axis = axis_angle_deg(parse_float(feature.get("principal_axis_deg"), angle))
            principal_minus_body = axial_diff_deg(principal_axis, body_axis)
            principal_minus_range = axial_diff_deg(principal_axis, local_range_axis)
            body_minus_range = axial_diff_deg(body_axis, local_range_axis)
            rows.append(
                {
                    "subject_frame_id": f"{subject['subject_name']}_sar{ctx.sar_frame:06d}",
                    "subject_name": subject["subject_name"],
                    "subject_short": subject["short"],
                    "pair_id": ctx.pair_id,
                    "sar_frame": ctx.sar_frame,
                    "split": frame_split(ctx.sar_frame),
                    "source_region_id": feature.get("region_id", ""),
                    "source_variant": subject["variant"],
                    "posthoc_evaluation_label": subject["posthoc_evaluation_label"],
                    "gate_label_used_for_status": "false",
                    "subject_motion_model": subject["motion_model"],
                    "persistent_subject_status": subject["persistent_subject_status"],
                    "center_x": fmt(center_x),
                    "center_y": fmt(center_y),
                    "width_px": fmt(width),
                    "height_px": fmt(height),
                    "width_m_grid": fmt(width * P0_PX_TO_M),
                    "height_m_grid": fmt(height * P0_PX_TO_M),
                    "angle_deg": fmt(angle),
                    "subject_principal_axis_deg": fmt(principal_axis),
                    "local_range_axis_deg": fmt(local_range_axis),
                    "local_azimuth_axis_deg": fmt(axis_angle_deg(local_range_axis + 90.0)),
                    "body_axis_proxy_deg": fmt(body_axis),
                    "motion_heading_directed_deg": fmt(motion_heading),
                    "heading_confidence": axial.get("heading_confidence", ""),
                    "principal_minus_body_axial_deg": fmt(principal_minus_body),
                    "principal_minus_range_axial_deg": fmt(principal_minus_range),
                    "body_minus_range_axial_deg": fmt(body_minus_range),
                    "principal_minus_motion_axial_deg": fmt(axial_diff_deg(principal_axis, motion_heading)),
                    "center_selection_status": seq_by_frame[ctx.sar_frame]["center_selection_status"],
                    "mean_energy": feature.get("mean_energy", ""),
                    "high_energy_pixel_fraction": feature.get("high_energy_pixel_fraction", ""),
                    "local_background_normalized_energy": feature.get("local_background_normalized_energy", ""),
                    "body_long_energy90_width_m": feature.get("body_long_energy90_width_m", ""),
                    "body_short_energy90_width_m": feature.get("body_short_energy90_width_m", ""),
                    "response_compactness": feature.get("response_compactness", ""),
                    "response_linearity": feature.get("response_linearity", ""),
                    "energy_centroid_range_m": feature.get("energy_centroid_range_m", ""),
                    "energy_centroid_azimuth_m": feature.get("energy_centroid_azimuth_m", ""),
                    "observation_status": feature.get("observation_status", ""),
                    "visible_fraction": feature.get("visible_fraction", ""),
                    "surface_generation_status": "zero_offset_source_from_frozen_e0_r1_plus_new_symmetric_offsets",
                }
            )
    return rows


def make_surface_spec(
    subject_row: Mapping[str, Any],
    ctx: e0.GtContext,
    axis_name: str,
    axis: tuple[float, float],
    offset_m: float,
    index: int,
) -> e0.RegionSpec:
    width = parse_float(subject_row.get("width_px"))
    height = parse_float(subject_row.get("height_px"))
    angle = parse_float(subject_row.get("angle_deg"))
    base_x = parse_float(subject_row.get("center_x"))
    base_y = parse_float(subject_row.get("center_y"))
    cx = base_x + axis[0] * (offset_m / P0_PX_TO_M)
    cy = base_y + axis[1] * (offset_m / P0_PX_TO_M)
    cx = min(max(cx, width / 2.0), e0.SAR_WIDTH - width / 2.0)
    cy = min(max(cy, height / 2.0), e0.SAR_HEIGHT - height / 2.0)
    return e0.RegionSpec(
        region_id=f"E0_R1_R1_SURF_{parse_int(subject_row['sar_frame']):06d}_{subject_row['subject_short']}_{axis_name[:3]}_{index:03d}",
        pair_id=str(subject_row["pair_id"]),
        sar_frame=parse_int(subject_row["sar_frame"]),
        family="E0_R1_R1_SUBJECT_TRANSLATION_SURFACE",
        variant=str(subject_row["subject_name"]),
        comparison_group="subject_specific_translation_surface",
        geometry_basis="same_size_same_orientation_subject_axis_shift",
        center_x=cx,
        center_y=cy,
        width_px=width,
        height_px=height,
        angle_deg=angle,
        area_ratio_to_gt=(width * height) / max(ctx.area, 1e-9),
        offset_axis=axis_name,
        offset_value=offset_m,
        offset_unit="metre_current_image_grid",
        scale_ratio=1.0,
        rotation_relative_to_gt_deg=0.0,
        source_role="symmetric_gate_surface_probe",
        interpretation_scope="e0_r1_r1_posthoc_symmetric_hard_negative_gate",
        gt_overlap_allowed="true" if subject_row["posthoc_evaluation_label"] == "vehicle" else "false",
        background_source=str(subject_row["subject_motion_model"]),
        outer_polygon=e0.rect_polygon(cx, cy, width, height, angle),
        inner_polygon=None,
    )


def build_translation_surfaces(
    selected_contexts: Sequence[e0.GtContext],
    subject_rows: Sequence[Mapping[str, Any]],
    frame_denominators: Mapping[int, float],
) -> list[dict[str, Any]]:
    ctx_by_pair = {ctx.pair_id: ctx for ctx in selected_contexts}
    cache = e0.image_cache()
    rows: list[dict[str, Any]] = []
    index = 0
    for subject in subject_rows:
        ctx = ctx_by_pair[str(subject["pair_id"])]
        frame = parse_int(subject["sar_frame"])
        image = e0.load_image(frame, cache)
        thresholds = e0.frame_thresholds(image)
        principal = parse_float(subject.get("subject_principal_axis_deg"))
        local_range = parse_float(subject.get("local_range_axis_deg"))
        body_axis = parse_float(subject.get("body_axis_proxy_deg"))
        axes = [
            ("local_range", unit_from_angle(local_range), "true"),
            ("local_azimuth", unit_from_angle(local_range + 90.0), "true"),
            ("subject_principal_axis", unit_from_angle(principal), "true"),
            ("subject_principal_axis_perpendicular", unit_from_angle(principal + 90.0), "true"),
        ]
        if subject["subject_name"] == "vehicle_body_axis_reference":
            axes.extend(
                [
                    ("body_long", unit_from_angle(body_axis), "false"),
                    ("body_short", unit_from_angle(body_axis + 90.0), "false"),
                ]
            )
        for axis_name, axis, symmetric_core_axis in axes:
            for offset_m in OFFSET_GRID_M:
                index += 1
                spec = make_surface_spec(subject, ctx, axis_name, axis, offset_m, index)
                feature = e0.feature_row(spec, ctx, image, thresholds)
                denom = max(frame_denominators.get(frame, 1.0), 1e-9)
                mean_energy = parse_float(feature.get("mean_energy"))
                rows.append(
                    {
                        "surface_region_id": spec.region_id,
                        "subject_frame_id": subject["subject_frame_id"],
                        "subject_name": subject["subject_name"],
                        "pair_id": subject["pair_id"],
                        "sar_frame": frame,
                        "split": frame_split(frame),
                        "posthoc_evaluation_label": subject["posthoc_evaluation_label"],
                        "gate_label_used_for_status": "false",
                        "subject_motion_model": subject["subject_motion_model"],
                        "persistent_subject_status": subject["persistent_subject_status"],
                        "axis_name": axis_name,
                        "symmetric_core_axis": symmetric_core_axis,
                        "offset_m": fmt(offset_m),
                        "offset_px": fmt(offset_m / P0_PX_TO_M),
                        "surface_center_x": fmt(spec.center_x),
                        "surface_center_y": fmt(spec.center_y),
                        "subject_zero_center_x": subject["center_x"],
                        "subject_zero_center_y": subject["center_y"],
                        "width_m_grid": subject["width_m_grid"],
                        "height_m_grid": subject["height_m_grid"],
                        "subject_principal_axis_deg": subject["subject_principal_axis_deg"],
                        "local_range_axis_deg": subject["local_range_axis_deg"],
                        "body_axis_proxy_deg": subject["body_axis_proxy_deg"],
                        "mean_energy": fmt(mean_energy),
                        "high_energy_pixel_fraction": feature.get("high_energy_pixel_fraction", ""),
                        "response_compactness": feature.get("response_compactness", ""),
                        "response_linearity": feature.get("response_linearity", ""),
                        "principal_axis_deg": feature.get("principal_axis_deg", ""),
                        "local_background_normalized_energy": fmt(mean_energy / denom),
                        "frame_background_median_mean_energy": fmt(denom),
                        "observation_status": feature.get("observation_status", ""),
                        "surface_grid_source": "frozen_e0_r1_r1_grid_-1_-0p75_-0p45_0_0p45_0p75_1m",
                    }
                )
    return rows


def draw_text_box(draw: ImageDraw.ImageDraw, lines: Sequence[str], xy: tuple[int, int]) -> None:
    x, y = xy
    width = min(1120, max(420, max(len(line) for line in lines) * 7 + 16))
    height = len(lines) * 16 + 12
    draw.rectangle((x, y, x + width, y + height), fill=(0, 0, 0))
    for idx, line in enumerate(lines):
        draw.text((x + 8, y + 6 + idx * 16), line, fill=(255, 255, 255))


def map_points(points: Sequence[tuple[float, float]], width: int = 920, height: int = 560) -> tuple[list[tuple[float, float]], tuple[float, float, float]]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale = min((width - 120) / max(max_x - min_x, 1.0), (height - 100) / max(max_y - min_y, 1.0))
    mapped = [(60 + (x - min_x) * scale, height - 50 - (y - min_y) * scale) for x, y in points]
    return mapped, (min_x, min_y, scale)


def render_center_trajectory(
    visual_id: str,
    title: str,
    points: Sequence[tuple[int, float, float]],
    color_by_frame: Mapping[int, tuple[int, int, int]] | None = None,
) -> Path:
    img = Image.new("RGB", (980, 620), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    mapped, _ = map_points([(x, y) for _, x, y in points])
    draw.line(mapped, fill=(30, 90, 190), width=3)
    for (frame, _, _), (x, y) in zip(points, mapped):
        color = color_by_frame.get(frame, (20, 150, 40)) if color_by_frame else (20, 150, 40)
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
        if frame in {315, 336, 371, 394}:
            draw.text((x + 6, y - 6), str(frame), fill=(0, 0, 0))
    draw_text_box(draw, [title, "Frame labels mark 315, 336, 371, 394 when present."], (18, 18))
    path = VISUAL_DIR / f"{visual_id}.png"
    img.save(path)
    return path


def render_heading_vectors(visual_id: str, title: str, heading_rows: Sequence[Mapping[str, Any]], centers: Mapping[int, tuple[float, float]], axial: bool) -> Path:
    img = Image.new("RGB", (980, 620), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    ordered = sorted((parse_int(row["sar_frame"]), centers[parse_int(row["sar_frame"])], row) for row in heading_rows if parse_int(row["sar_frame"]) in centers)
    mapped, _ = map_points([pt for _, pt, _ in ordered])
    draw.line(mapped, fill=(120, 120, 120), width=2)
    for (frame, _, row), (x, y) in zip(ordered[:: max(1, len(ordered) // 24)], mapped[:: max(1, len(mapped) // 24)]):
        confidence = row.get("heading_confidence", "")
        color = (0, 150, 40) if confidence == "HIGH" else (220, 150, 0) if confidence == "MEDIUM" else (190, 40, 40)
        angle = parse_float(row.get("body_axis_proxy_deg" if axial else "motion_heading_directed_deg"))
        dx = math.cos(math.radians(angle)) * 34
        dy = -math.sin(math.radians(angle)) * 34
        if axial:
            draw.line((x - dx, y + dy, x + dx, y - dy), fill=color, width=2)
        else:
            draw.line((x, y, x + dx, y - dy), fill=color, width=2)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=color)
        if frame in {336, 371, 394}:
            draw.text((x + 5, y + 5), str(frame), fill=(0, 0, 0))
    draw_text_box(draw, [title, "Green=HIGH, amber=MEDIUM, red=LOW."], (18, 18))
    path = VISUAL_DIR / f"{visual_id}.png"
    img.save(path)
    return path


def render_curvature_plot(axial_rows: Sequence[Mapping[str, Any]]) -> Path:
    img = Image.new("RGB", (980, 620), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    rows = sorted(axial_rows, key=lambda row: parse_int(row["sar_frame"]))
    frames = [parse_int(row["sar_frame"]) for row in rows]
    if not frames:
        path = VISUAL_DIR / "directed_vs_axial_curvature.png"
        img.save(path)
        return path
    min_f, max_f = min(frames), max(frames)
    def xy(frame: int, value: float) -> tuple[float, float]:
        x = 60 + (frame - min_f) / max(max_f - min_f, 1) * 850
        y = 550 - min(value, 180.0) / 180.0 * 470
        return x, y
    directed = [xy(parse_int(row["sar_frame"]), parse_float(row["raw_directed_curvature_deg"])) for row in rows]
    axial = [xy(parse_int(row["sar_frame"]), parse_float(row["axial_curvature_deg"])) for row in rows]
    draw.line(directed, fill=(190, 40, 40), width=2)
    draw.line(axial, fill=(30, 120, 200), width=3)
    draw.line((60, 550 - 90 / 180 * 470, 910, 550 - 90 / 180 * 470), fill=(180, 180, 180), width=1)
    draw_text_box(draw, ["Directed curvature (red) versus 180-degree axial curvature (blue)", "Axial body continuity is judged on [0,90] differences."], (18, 18))
    path = VISUAL_DIR / "directed_vs_axial_curvature.png"
    img.save(path)
    return path


def render_surface_plot(visual_id: str, title: str, surface_rows: Sequence[Mapping[str, Any]], subject_name: str, frame: int) -> Path:
    img = Image.new("RGB", (980, 620), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    selected = [
        row
        for row in surface_rows
        if row["subject_name"] == subject_name
        and parse_int(row["sar_frame"]) == frame
        and row["symmetric_core_axis"] == "true"
    ]
    values = [parse_float(row["local_background_normalized_energy"]) for row in selected]
    ymin = min(values) if values else 0.0
    ymax = max(values) if values else 1.0
    pad = max((ymax - ymin) * 0.15, 0.02)
    ymin -= pad
    ymax += pad
    colors = {
        "local_range": (30, 120, 200),
        "local_azimuth": (20, 150, 40),
        "subject_principal_axis": (190, 80, 30),
        "subject_principal_axis_perpendicular": (130, 60, 180),
    }
    for axis_name, color in colors.items():
        axis_rows = sorted([row for row in selected if row["axis_name"] == axis_name], key=lambda row: parse_float(row["offset_m"]))
        pts = []
        for row in axis_rows:
            x = 90 + (parse_float(row["offset_m"]) + 1.0) / 2.0 * 780
            y = 540 - (parse_float(row["local_background_normalized_energy"]) - ymin) / max(ymax - ymin, 1e-9) * 450
            pts.append((x, y))
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=color)
        if len(pts) >= 2:
            draw.line(pts, fill=color, width=2)
    draw.line((480, 90, 480, 540), fill=(0, 0, 0), width=1)
    draw_text_box(draw, [title, f"Subject={subject_name} SAR={frame}; x offset -1m..+1m; y local-bg-normalized energy."], (18, 18))
    path = VISUAL_DIR / f"{visual_id}.png"
    img.save(path)
    return path


def render_temporal_plot(visual_id: str, title: str, subject_rows: Sequence[Mapping[str, Any]], subject_name: str) -> Path:
    img = Image.new("RGB", (980, 620), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    rows = sorted([row for row in subject_rows if row["subject_name"] == subject_name], key=lambda row: parse_int(row["sar_frame"]))
    frames = [parse_int(row["sar_frame"]) for row in rows]
    values = [parse_float(row["local_background_normalized_energy"]) for row in rows]
    if frames and values:
        min_f, max_f = min(frames), max(frames)
        ymin, ymax = min(values), max(values)
        pad = max((ymax - ymin) * 0.15, 0.02)
        pts = [
            (70 + (f - min_f) / max(max_f - min_f, 1) * 830, 540 - (v - ymin + pad) / max((ymax - ymin + 2 * pad), 1e-9) * 450)
            for f, v in zip(frames, values)
        ]
        draw.line(pts, fill=(30, 120, 200), width=3)
        for x, y in pts[:: max(1, len(pts) // 24)]:
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(30, 120, 200))
    draw_text_box(draw, [title, f"Subject={subject_name}; framewise local-bg-normalized energy."], (18, 18))
    path = VISUAL_DIR / f"{visual_id}.png"
    img.save(path)
    return path


def render_sar336_conflict(conflict_rows: Sequence[Mapping[str, Any]], cache: dict[int, np.ndarray]) -> Path:
    frame = 336
    image = Image.fromarray(e0.load_image(frame, cache).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(image)
    rows = [row for row in conflict_rows if parse_int(row["sar_frame"]) == frame]
    centers = []
    for row in rows:
        x = parse_float(row["center_x"])
        y = parse_float(row["center_y"])
        centers.append((x, y))
        color = (0, 220, 0) if row["candidate_decision"] == "SELECTED" else (240, 50, 50)
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), outline=color, width=4)
        draw.text((x + 14, y - 8), f"{row['pair_id']} {row['candidate_decision']}", fill=color)
    if centers:
        x1 = max(0, int(min(x for x, _ in centers) - 180))
        y1 = max(0, int(min(y for _, y in centers) - 180))
        x2 = min(e0.SAR_WIDTH - 1, int(max(x for x, _ in centers) + 180))
        y2 = min(e0.SAR_HEIGHT - 1, int(max(y for _, y in centers) + 180))
        image = image.crop((x1, y1, x2 + 1, y2 + 1))
        draw = ImageDraw.Draw(image)
    draw_text_box(draw, ["SAR336 duplicate GT audit", "Green selected; red excluded weak/conflict candidate."], (12, 12))
    path = VISUAL_DIR / "sar336_multi_gt_weak_correspondence_conflict.png"
    image.save(path)
    return path


def render_text_schematic(visual_id: str, lines: Sequence[str]) -> Path:
    img = Image.new("RGB", (980, 620), (246, 246, 246))
    draw = ImageDraw.Draw(img)
    y = 42
    for line in lines:
        draw.text((42, y), line, fill=(20, 20, 20))
        y += 28
    path = VISUAL_DIR / f"{visual_id}.png"
    img.save(path)
    return path


def render_frame_overlay(visual_id: str, title: str, frame: int, subject_rows: Sequence[Mapping[str, Any]], cache: dict[int, np.ndarray]) -> Path:
    image = Image.fromarray(e0.load_image(frame, cache).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(image)
    rows = [row for row in subject_rows if parse_int(row["sar_frame"]) == frame and row["subject_name"] in {"vehicle_body_axis_reference", "matched_strong_scatterer_background", "matched_linear_structure_background", "fixed_known_non_vehicle_N005"}]
    polys = []
    for row in rows:
        poly = e0.rect_polygon(parse_float(row["center_x"]), parse_float(row["center_y"]), parse_float(row["width_px"]), parse_float(row["height_px"]), parse_float(row["angle_deg"]))
        polys.append(poly)
    if polys:
        x1, y1, x2, y2 = e0.polygon_bounds(polys)
        margin = 120
        x1 = max(0, x1 - margin)
        y1 = max(0, y1 - margin)
        x2 = min(e0.SAR_WIDTH - 1, x2 + margin)
        y2 = min(e0.SAR_HEIGHT - 1, y2 + margin)
        image = image.crop((x1, y1, x2 + 1, y2 + 1))
        draw = ImageDraw.Draw(image)
        colors = {
            "vehicle_body_axis_reference": (0, 240, 0),
            "matched_strong_scatterer_background": (240, 60, 60),
            "matched_linear_structure_background": (255, 160, 0),
            "fixed_known_non_vehicle_N005": (160, 80, 255),
        }
        for row in rows:
            poly = e0.rect_polygon(parse_float(row["center_x"]), parse_float(row["center_y"]), parse_float(row["width_px"]), parse_float(row["height_px"]), parse_float(row["angle_deg"]))
            shifted = [(x - x1, y - y1) for x, y in poly]
            color = colors.get(row["subject_name"], (255, 255, 255))
            draw.line(shifted + [shifted[0]], fill=color, width=3)
            draw.text((shifted[0][0], shifted[0][1]), row["subject_name"][:10], fill=color)
    draw_text_box(draw, [title, "Green=vehicle; red/orange/purple=hard negatives."], (12, 12))
    path = VISUAL_DIR / f"{visual_id}.png"
    image.save(path)
    return path


def visual_row(visual_id: str, frame: Any, path: Path, requirement: str, conclusion_cn: str) -> dict[str, Any]:
    return {
        "visual_id": visual_id,
        "sar_frame": frame,
        "diagnostic_png": rel(path),
        "review_requirement": requirement,
        "review_status": "generated_for_e0_r1_r1_review",
        "reviewer_conclusion_cn": conclusion_cn,
        "commit_policy": "do_not_commit_png_outputs",
    }


def build_visuals(
    sequence_rows: Sequence[Mapping[str, Any]],
    conflict_rows: Sequence[Mapping[str, Any]],
    directed_rows: Sequence[Mapping[str, Any]],
    axial_rows: Sequence[Mapping[str, Any]],
    subject_rows: Sequence[Mapping[str, Any]],
    surface_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    cache = e0.image_cache()
    rows: list[dict[str, Any]] = []
    centers = {
        parse_int(row["sar_frame"]): (parse_float(row["selected_center_x"]), parse_float(row["selected_center_y"]))
        for row in sequence_rows
        if row.get("selected_center_x") != ""
    }
    raw_points = []
    for target in e0.target_rows():
        ctx = e0.make_context(target)
        raw_points.append((ctx.sar_frame, ctx.cx, ctx.cy))
    selected_points = [(frame, x, y) for frame, (x, y) in centers.items()]
    status_colors = {
        parse_int(row["sar_frame"]): (20, 150, 40)
        if row["center_selection_status"] == "UNIQUE_GT_CENTER"
        else (230, 150, 0)
        if row["center_selection_status"] != "UNRESOLVED"
        else (190, 40, 40)
        for row in sequence_rows
    }
    rows.append(visual_row("sar336_multi_gt_weak_correspondence_conflict", 336, render_sar336_conflict(conflict_rows, cache), "SAR336 multi-GT / weak correspondence conflict", "SAR336 双 GT 被单独审阅：主线程中心保留，弱对应候选排除，原 GT 未修改。"))
    rows.append(visual_row("raw_gt_center_trajectory", "", render_center_trajectory("raw_gt_center_trajectory", "Raw target-row GT center trajectory", raw_points), "raw center trajectory", "原始轨迹显示 SAR336 同帧多行会造成轨迹歧义，不能直接按同帧平均。"))
    rows.append(visual_row("selected_unique_center_trajectory", "", render_center_trajectory("selected_unique_center_trajectory", "Selected unique physical center trajectory", selected_points, status_colors), "cleaned unique center trajectory", "清洗后的中心序列保留唯一物理线程，重复/弱对应帧被显式标注。"))
    rows.append(visual_row("directed_motion_heading_vectors", "", render_heading_vectors("directed_motion_heading_vectors", "Directed motion heading", directed_rows, centers, axial=False), "directed motion vectors", "有向运动箭头仅解释运动趋势，不再当作车体长轴的有向角。"))
    rows.append(visual_row("axial_body_axis_proxy_vectors", "", render_heading_vectors("axial_body_axis_proxy_vectors", "180-degree axial body-axis proxy", axial_rows, centers, axial=True), "180-degree body-axis proxy", "车体轴用 180 度周期显示，前后方向等价，避免把掉头角误判为轴向断裂。"))
    rows.append(visual_row("directed_vs_axial_curvature", "", render_curvature_plot(axial_rows), "directed curvature versus axial curvature", "原有大角度一步曲率在轴向语义下明显收缩，说明 E0-R1 航向代理确有有向/轴向混用风险。"))
    conf_colors = {
        parse_int(row["sar_frame"]): (0, 150, 40)
        if row["heading_confidence"] == "HIGH"
        else (220, 150, 0)
        if row["heading_confidence"] == "MEDIUM"
        else (190, 40, 40)
        for row in axial_rows
    }
    rows.append(visual_row("heading_confidence_frames", "", render_center_trajectory("heading_confidence_frames", "Heading confidence along selected trajectory", selected_points, conf_colors), "high/medium/low heading confidence frames", "高/中/低置信度沿轨迹分布不均，诊断段方向结论必须受高置信帧数量约束。"))
    review_frame = 376 if any(parse_int(row["sar_frame"]) == 376 for row in surface_rows) else parse_int(surface_rows[0]["sar_frame"])
    rows.append(visual_row("vehicle_translation_surface", review_frame, render_surface_plot("vehicle_translation_surface", "Vehicle subject translation surface", surface_rows, "vehicle_body_axis_reference", review_frame), "vehicle translation response surface", "车辆平移面在零点附近保留局部峰/平台，但需与每类负样本同轴同网格比较。"))
    rows.append(visual_row("matched_strong_scatterer_translation_surface", review_frame, render_surface_plot("matched_strong_scatterer_translation_surface", "Matched strong-scatterer translation surface", surface_rows, "matched_strong_scatterer_background", review_frame), "matched strong scatterer translation surface", "匹配强散射背景被单独成面评估，不再借用车辆 near-GT 平移结果。"))
    rows.append(visual_row("matched_linear_structure_translation_surface", review_frame, render_surface_plot("matched_linear_structure_translation_surface", "Matched linear-structure translation surface", surface_rows, "matched_linear_structure_background", review_frame), "matched linear structure translation surface", "匹配线性结构有自己的主轴和垂轴扰动面，不能与普通背景合并。"))
    rows.append(visual_row("n005_translation_surface", review_frame, render_surface_plot("n005_translation_surface", "N005 translation surface", surface_rows, "fixed_known_non_vehicle_N005", review_frame), "N005 translation surface", "N005 固定非车辆区域按同一网格生成平移面，G7 不再因标签直接失败。"))
    rows.append(visual_row("fixed_strong_scatterer_temporal", "", render_temporal_plot("fixed_strong_scatterer_temporal", "Fixed strong-scatterer temporal trace", subject_rows, "fixed_strong_scatterer"), "fixed strong scatterer temporal trace", "固定强散射背景的能量稳定性被作为 G9/G10 输入，而不是作为车辆证据继承。"))
    rows.append(visual_row("fixed_linear_structure_temporal", "", render_temporal_plot("fixed_linear_structure_temporal", "Fixed linear-structure temporal trace", subject_rows, "fixed_linear_structure"), "fixed linear temporal trace", "固定线性背景具有图像坐标持久性，需由 G10 判断固定背景解释是否充分。"))
    rows.append(visual_row("e0_r1_false_zero_confusion_logic", "", render_text_schematic("e0_r1_false_zero_confusion_logic", ["E0-R1 invalid logic:", "if is_vehicle: evaluate near-GT translation", "else: G7 = FAIL_NON_GT_REGION", "", "static_rejected = is_vehicle and paired_higher >= 0.60", "", "physical_confusion = not is_vehicle and G10 == PASS", "", "Result: non-vehicle cannot pass by construction."]), "old false-zero-confusion schematic", "旧零混淆来自标签依赖 G10 的恒假结构，不是数据证明。"))

    vehicle_by_frame = {parse_int(row["sar_frame"]): row for row in subject_rows if row["subject_name"] == "vehicle_body_axis_reference"}
    hard_by_frame: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in subject_rows:
        if row["posthoc_evaluation_label"] == "negative":
            hard_by_frame[parse_int(row["sar_frame"])].append(row)
    deltas = []
    for frame, vehicle in vehicle_by_frame.items():
        controls = hard_by_frame.get(frame, [])
        if controls:
            max_control = max(parse_float(row["local_background_normalized_energy"]) for row in controls)
            deltas.append((parse_float(vehicle["local_background_normalized_energy"]) - max_control, frame))
    if deltas:
        sep_frame = max(deltas)[1]
        conf_frame = min(deltas)[1]
        rows.append(visual_row("typical_separable_frame", sep_frame, render_frame_overlay("typical_separable_frame", "Typical separable frame", sep_frame, subject_rows, cache), "typical separable frame", "典型可分帧中车辆邻域相对最强负样本更集中，空间面仍需同构 Gate 约束。"))
        rows.append(visual_row("typical_confusion_frame", conf_frame, render_frame_overlay("typical_confusion_frame", "Typical confusing frame", conf_frame, subject_rows, cache), "typical confusing frame", "典型混淆帧显示强负样本压力真实存在，不能再用旧恒假 G10 抹掉。"))
    rows.append(visual_row("g9_g10_no_persistent_subject_case", review_frame, render_text_schematic("g9_g10_no_persistent_subject_case", ["Framewise matched controls are not tracks.", "G9/G10 state: NOT_EVALUABLE", "Reason: FRAMEWISE_MATCHED_CONTROL_NO_TRACK", "", "NOT_EVALUABLE is neither PASS nor FAIL."]), "G9/G10 not-evaluable matched-control case", "逐帧匹配背景不是持续主体，G9/G10 只能标记不可评价，不能被算作失败制造零混淆。"))
    return rows


def build_correction_audit() -> list[dict[str, Any]]:
    return [
        {
            "audit_id": "E0_R1_LABEL_DEPENDENT_G7",
            "prior_logic": "if is_vehicle evaluate near-GT translation else G7=FAIL_NON_GT_REGION",
            "defect": "label_dependent_gate",
            "r1_r1_correction": "G7_LOCAL_CENTERED_RESPONSE_STRUCTURE uses subject-specific translation surfaces for every subject",
            "status": "REPAIRED_IN_E0_R1_R1",
        },
        {
            "audit_id": "E0_R1_LABEL_DEPENDENT_G10",
            "prior_logic": "static_rejected = is_vehicle and paired_higher_median >= 0.60",
            "defect": "non_vehicle_could_not_pass_G10_by_construction",
            "r1_r1_correction": "G10_BACKGROUND_FIXEDNESS_EXPLANATION_REJECTED uses subject motion and image-coordinate fixedness inputs",
            "status": "REPAIRED_IN_E0_R1_R1",
        },
        {
            "audit_id": "E0_R1_DIRECTED_HEADING_AS_BODY_AXIS",
            "prior_logic": "ordinary directed heading difference used for body-axis continuity",
            "defect": "360_degree_direction_mixed_with_180_degree_body_axis",
            "r1_r1_correction": "directed motion and axial body-axis proxy are separate outputs; body differences are [0,90]",
            "status": "REPAIRED_IN_E0_R1_R1",
        },
        {
            "audit_id": "E0_R1_ZERO_CONFUSION_WITHDRAWAL",
            "prior_logic": "multi_gate_physical_confusions=0",
            "defect": "constant_zero_from_gate_logic_not_scientific_evidence",
            "r1_r1_correction": "observable and full physical confusion are recomputed after symmetric Gates",
            "status": "WITHDRAWN_AND_REEVALUATED",
        },
    ]


def write_pre_eval_seal(output_map: Mapping[str, Path]) -> None:
    generator_sha = sha256_file(Path(__file__))
    rows = []
    for key in GENERATION_KEYS:
        path = output_map[key]
        rows.append(
            {
                "artifact_key": key,
                "path": rel(path),
                "sha256": sha256_file(path),
                "row_count": row_count(path),
                "seal_phase": "e0_r1_r1_pre_eval_symmetric_subject_surface_freeze",
                "code_commit_sha": git_output(["rev-parse", "HEAD"]),
                "generator_source_sha256": generator_sha,
                "allowed_inputs": "frozen_e0_r1_csv;paired_gt_annotations;sar_gray_frames;p0_n005_components",
                "forbidden_outputs": "selector;ranking;final_box;gt_modification;training;cross_scene_claim",
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
    sequence_rows, conflict_rows, selected_contexts, _ = build_center_audit()
    directed_rows, axial_rows, ablation_rows = build_heading_rows(sequence_rows, selected_contexts)
    feature_index, manifest_index = old_feature_indexes()
    subject_rows = build_subject_manifest(selected_contexts, axial_rows, feature_index, manifest_index, sequence_rows)
    denominators = frame_background_denominators(selected_contexts, feature_index)
    surface_rows = build_translation_surfaces(selected_contexts, subject_rows, denominators)
    visual_rows = build_visuals(sequence_rows, conflict_rows, directed_rows, axial_rows, subject_rows, surface_rows)

    write_csv(output_map["correction_audit"], build_correction_audit(), CORRECTION_AUDIT_FIELDS)
    write_csv(output_map["unique_gt_center_sequence"], sequence_rows, UNIQUE_GT_CENTER_FIELDS)
    write_csv(output_map["gt_conflict_audit"], conflict_rows, GT_CONFLICT_FIELDS)
    write_csv(output_map["directed_motion_heading"], directed_rows, DIRECTED_HEADING_FIELDS)
    write_csv(output_map["axial_body_heading"], axial_rows, AXIAL_HEADING_FIELDS)
    write_csv(output_map["heading_method_ablation"], ablation_rows, HEADING_ABLATION_FIELDS)
    write_csv(output_map["subject_manifest"], subject_rows, SUBJECT_MANIFEST_FIELDS)
    write_csv(output_map["subject_translation_surfaces"], surface_rows, TRANSLATION_SURFACE_FIELDS)
    write_csv(output_map["visual_review_manifest"], visual_rows, VISUAL_FIELDS)
    write_pre_eval_seal(output_map)
    write_frozen_manifest(output_map, "e0_r1_r1_generation")
    print(f"E0_R1_R1 generation complete: subjects={len(subject_rows)} surfaces={len(surface_rows)} visuals={len(visual_rows)}")


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
        results.append({"artifact_key": key, "frozen_sha256": sha256_file(frozen), "replay_sha256": sha256_file(replay), "status": "PASS" if same else "FAIL"})
    write_csv(OUTPUTS["replay_check"], results, REPLAY_FIELDS)
    write_frozen_manifest(OUTPUTS, "e0_r1_r1_replay_verified")
    print(f"E0_R1_R1_FROZEN_REPLAY_IDENTICAL={'PASS' if all(row['status'] == 'PASS' for row in results) else 'FAIL'}")


CORRECTION_AUDIT_FIELDS = ["audit_id", "prior_logic", "defect", "r1_r1_correction", "status"]
UNIQUE_GT_CENTER_FIELDS = [
    "sar_frame", "gt_row_count", "candidate_pair_ids", "candidate_centers", "center_selection_status",
    "selected_pair_id", "selected_sar_gt_id", "selected_center_x", "selected_center_y",
    "identity_consistency_status", "included_in_heading_main_analysis", "selection_inputs", "gt_modification",
]
GT_CONFLICT_FIELDS = [
    "sar_frame", "pair_id", "sar_gt_id", "center_x", "center_y", "weak_correspondence", "frame_selection_status",
    "candidate_decision", "identity_consistency_status", "visual_review_required",
]
DIRECTED_HEADING_FIELDS = [
    "pair_id", "sar_frame", "split", "selected_center_x", "selected_center_y", "center_selection_status",
    "delta_frame", "velocity_px_per_sar_frame", "raw_delta_heading_directed_deg", "motion_heading_directed_deg",
    "history_only_heading_directed_deg", "local_quadratic_heading_directed_deg", "median_displacement_heading_directed_deg",
    "fit_residual_px", "support_frame_count", "trajectory_gap_size", "local_displacement_sign_stability",
    "heading_confidence", "threshold_source", "diagnostic_scope",
]
AXIAL_HEADING_FIELDS = [
    "pair_id", "sar_frame", "split", "body_axis_proxy_deg", "motion_heading_directed_deg", "raw_directed_curvature_deg",
    "axial_curvature_deg", "raw_vs_smoothed_axial_difference_deg", "history_vs_symmetric_axial_difference_deg",
    "speed_px_per_sar_frame", "fit_residual_px", "support_frame_count", "duplicate_conflict_status",
    "trajectory_gap_size", "local_displacement_sign_stability", "heading_confidence", "confidence_rule_version",
    "calibration_min_speed_px_per_sar_frame", "calibration_max_fit_residual_px", "calibration_max_axial_curvature_deg",
    "axis_semantics",
]
HEADING_ABLATION_FIELDS = [
    "pair_id", "sar_frame", "split", "method", "motion_heading_directed_deg", "body_axis_proxy_deg",
    "speed_px_per_sar_frame", "fit_residual_px", "support_frame_count", "support_frames",
    "posthoc_or_runtime", "used_for_main_body_axis_proxy",
]
SUBJECT_MANIFEST_FIELDS = [
    "subject_frame_id", "subject_name", "subject_short", "pair_id", "sar_frame", "split", "source_region_id",
    "source_variant", "posthoc_evaluation_label", "gate_label_used_for_status", "subject_motion_model",
    "persistent_subject_status", "center_x", "center_y", "width_px", "height_px", "width_m_grid", "height_m_grid",
    "angle_deg", "subject_principal_axis_deg", "local_range_axis_deg", "local_azimuth_axis_deg", "body_axis_proxy_deg",
    "motion_heading_directed_deg", "heading_confidence", "principal_minus_body_axial_deg", "principal_minus_range_axial_deg",
    "body_minus_range_axial_deg", "principal_minus_motion_axial_deg", "center_selection_status", "mean_energy",
    "high_energy_pixel_fraction", "local_background_normalized_energy", "body_long_energy90_width_m",
    "body_short_energy90_width_m", "response_compactness", "response_linearity", "energy_centroid_range_m",
    "energy_centroid_azimuth_m", "observation_status", "visible_fraction", "surface_generation_status",
]
TRANSLATION_SURFACE_FIELDS = [
    "surface_region_id", "subject_frame_id", "subject_name", "pair_id", "sar_frame", "split", "posthoc_evaluation_label",
    "gate_label_used_for_status", "subject_motion_model", "persistent_subject_status", "axis_name", "symmetric_core_axis",
    "offset_m", "offset_px", "surface_center_x", "surface_center_y", "subject_zero_center_x", "subject_zero_center_y",
    "width_m_grid", "height_m_grid", "subject_principal_axis_deg", "local_range_axis_deg", "body_axis_proxy_deg",
    "mean_energy", "high_energy_pixel_fraction", "response_compactness", "response_linearity", "principal_axis_deg",
    "local_background_normalized_energy", "frame_background_median_mean_energy", "observation_status", "surface_grid_source",
]
VISUAL_FIELDS = ["visual_id", "sar_frame", "diagnostic_png", "review_requirement", "review_status", "reviewer_conclusion_cn", "commit_policy"]
PRE_EVAL_SEAL_FIELDS = ["artifact_key", "path", "sha256", "row_count", "seal_phase", "code_commit_sha", "generator_source_sha256", "allowed_inputs", "forbidden_outputs"]
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
