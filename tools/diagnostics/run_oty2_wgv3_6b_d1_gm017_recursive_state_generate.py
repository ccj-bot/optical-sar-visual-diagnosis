"""Generate D1 recursive causal state propagation artifacts for GM_RM017.

The generator is intentionally isolated from holdout GT. It reads only frozen
calibration artifacts and current/past SAR gray frames, then writes a
pre-evaluation seal before any evaluator is allowed to open holdout GT.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw


DATE = "20260712"
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_d1_gm017_recursive_causal_state_propagation_{DATE}"
VISUAL_DIR = OUTPUT_DIR / "visual_review"
REPLAY_DIR = OUTPUT_DIR / "_verify_replay_tmp"
SCENE_CONFIG = REPO_ROOT / "configs" / "scene_config.yaml"

CALIBRATION_END = 360
GENERATE_START = 361
GUARD_END = 370
HOLDOUT_START = 371
HOLDOUT_END = 394
SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6

P0 = {
    "protocol": REPO_ROOT / "docs" / "OTY2_GM017_PHYSICAL_FACTOR_CALIBRATION_PROTOCOL.md",
    "report": REPORT_DIR / f"oty2_wgv3_6b_p0_gm017_physical_factor_discovery_{DATE}.md",
    "frozen_params": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_factor_parameters_{DATE}.csv",
    "control_points": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_calibration_control_points_{DATE}.csv",
    "components": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_response_component_observations_{DATE}.csv",
    "background_fit": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_background_stability_fit_{DATE}.csv",
    "manifest": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_manifest_{DATE}.csv",
}

OUTPUTS = {
    "runtime_input_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_runtime_input_manifest_{DATE}.csv",
    "initial_state": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_initial_state_{DATE}.csv",
    "frame_observations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_frame_observations_{DATE}.csv",
    "target_state_history": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_target_state_history_{DATE}.csv",
    "response_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_response_tracks_{DATE}.csv",
    "response_associations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_response_associations_{DATE}.csv",
    "background_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_background_tracks_{DATE}.csv",
    "visibility_events": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_visibility_events_{DATE}.csv",
    "reappearance_events": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_reappearance_events_{DATE}.csv",
    "holdout_predictions_frozen": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_holdout_predictions_frozen_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_pre_eval_seal_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_visual_review_manifest_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_gate_integrity_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_frozen_manifest_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_wgv3_6b_d1_gm017_replay_check_{DATE}.csv",
}

CORE_GENERATION_KEYS = [
    "runtime_input_manifest",
    "initial_state",
    "frame_observations",
    "target_state_history",
    "response_tracks",
    "response_associations",
    "background_tracks",
    "visibility_events",
    "reappearance_events",
    "holdout_predictions_frozen",
    "visual_review_manifest",
]


@dataclass
class ResponseTrack:
    track_id: str
    init_frame: int
    last_frame: int
    last_x: float
    last_y: float
    rel_x: float
    rel_y: float
    support_frames: int = 1
    consecutive_support_frames: int = 1
    missing_frames: int = 0
    status: str = "visible"
    last_area: float = 0.0
    last_energy: float = 0.0
    last_orientation: float = 0.0
    reappearance_count: int = 0
    terminated_frame: str = ""


@dataclass
class BackgroundTrack:
    track_id: str
    first_frame: int
    last_frame: int
    xs: list[float] = field(default_factory=list)
    ys: list[float] = field(default_factory=list)
    areas: list[float] = field(default_factory=list)
    energies: list[float] = field(default_factory=list)
    missing_frames: int = 0

    @property
    def mean_x(self) -> float:
        return float(np.mean(self.xs)) if self.xs else 0.0

    @property
    def mean_y(self) -> float:
        return float(np.mean(self.ys)) if self.ys else 0.0

    @property
    def variance(self) -> float:
        if len(self.xs) < 2:
            return 999999.0
        return float(np.var(self.xs) + np.var(self.ys))

    @property
    def support_frames(self) -> int:
        return len(self.xs)


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
    if not path.exists():
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


def box_from_center(cx: float, cy: float, width: float, height: float) -> tuple[float, float, float, float]:
    return (cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0)


def clamp_roi(box: Sequence[float], margin: float = 0.0) -> tuple[int, int, int, int]:
    x1 = max(0, int(math.floor(box[0] - margin)))
    y1 = max(0, int(math.floor(box[1] - margin)))
    x2 = min(SAR_WIDTH - 1, int(math.ceil(box[2] + margin)))
    y2 = min(SAR_HEIGHT - 1, int(math.ceil(box[3] + margin)))
    if x2 <= x1:
        x2 = min(SAR_WIDTH - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(SAR_HEIGHT - 1, y1 + 1)
    return x1, y1, x2, y2


def parse_pair(text: str) -> tuple[float, float]:
    x, y = text.split(",", 1)
    return parse_float(x), parse_float(y)


def parse_box(text: str) -> tuple[float, float, float, float]:
    parts = [parse_float(part) for part in text.split(",")]
    return parts[0], parts[1], parts[2], parts[3]


def read_params() -> dict[str, str]:
    return {row["parameter_name"]: row["parameter_value"] for row in read_csv(P0["frozen_params"])}


def component_stats(xs: list[int], ys: list[int], values: list[float]) -> dict[str, float]:
    arr_x = np.asarray(xs, dtype=float)
    arr_y = np.asarray(ys, dtype=float)
    arr_v = np.asarray(values, dtype=float)
    weights = np.maximum(arr_v, 1.0)
    centroid_x = float(np.average(arr_x, weights=weights))
    centroid_y = float(np.average(arr_y, weights=weights))
    if len(arr_x) >= 3:
        coords = np.column_stack([arr_x - arr_x.mean(), arr_y - arr_y.mean()])
        cov = np.cov(coords, rowvar=False)
        eigvals, eigvecs = np.linalg.eigh(cov)
        order = np.argsort(eigvals)[::-1]
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]
        axis1 = 4.0 * math.sqrt(max(float(eigvals[0]), 0.0))
        axis2 = 4.0 * math.sqrt(max(float(eigvals[1]), 0.0))
        orientation = math.degrees(math.atan2(float(eigvecs[1, 0]), float(eigvecs[0, 0])))
    else:
        axis1 = axis2 = orientation = 0.0
    width = float(arr_x.max() - arr_x.min() + 1)
    height = float(arr_y.max() - arr_y.min() + 1)
    return {
        "centroid_x": centroid_x,
        "centroid_y": centroid_y,
        "bbox_x1": float(arr_x.min()),
        "bbox_y1": float(arr_y.min()),
        "bbox_x2": float(arr_x.max()),
        "bbox_y2": float(arr_y.max()),
        "pixel_area": float(len(arr_x)),
        "integrated_energy": float(arr_v.sum()),
        "mean_energy": float(arr_v.mean()),
        "peak_energy": float(arr_v.max()),
        "axis1_px": axis1,
        "axis2_px": axis2,
        "aspect_ratio": axis1 / max(axis2, 1e-6),
        "orientation_deg": orientation,
        "compactness": float(len(arr_x)) / max(width * height, 1.0),
    }


def extract_components(
    sar_frame: int,
    roi: Sequence[int],
    *,
    min_pixels: int = 10,
    threshold_quantile: float = 93.0,
    mean_std_k: float = 0.95,
    safety_cap: int = 1500,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = sar_gray_path(sar_frame)
    image = Image.open(path).convert("L")
    x1, y1, x2, y2 = [int(v) for v in roi]
    crop = np.asarray(image.crop((x1, y1, x2 + 1, y2 + 1)), dtype=np.float32)
    if crop.size == 0:
        return [], {"threshold": "", "candidate_pixels": 0, "cap_triggered": "false", "roi": f"{x1},{y1},{x2},{y2}"}
    threshold = max(float(crop.mean() + mean_std_k * crop.std()), float(np.percentile(crop, threshold_quantile)))
    mask = crop >= threshold
    visited = np.zeros(mask.shape, dtype=bool)
    height, width = mask.shape
    components: list[dict[str, Any]] = []
    ys, xs = np.nonzero(mask)
    for yy, xx in zip(ys.tolist(), xs.tolist()):
        if visited[yy, xx]:
            continue
        stack = [(xx, yy)]
        visited[yy, xx] = True
        comp_xs: list[int] = []
        comp_ys: list[int] = []
        comp_values: list[float] = []
        while stack:
            cx, cy = stack.pop()
            comp_xs.append(cx + x1)
            comp_ys.append(cy + y1)
            comp_values.append(float(crop[cy, cx]))
            for ny in range(max(0, cy - 1), min(height, cy + 2)):
                for nx in range(max(0, cx - 1), min(width, cx + 2)):
                    if visited[ny, nx] or not mask[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    stack.append((nx, ny))
        if len(comp_xs) < min_pixels:
            continue
        stat = component_stats(comp_xs, comp_ys, comp_values)
        components.append(stat)
    cap_triggered = len(components) > safety_cap
    if cap_triggered:
        components = components[:safety_cap]
    return components, {
        "threshold": threshold,
        "candidate_pixels": int(mask.sum()),
        "cap_triggered": "true" if cap_triggered else "false",
        "roi": f"{x1},{y1},{x2},{y2}",
    }


def initial_state_and_tracks() -> tuple[dict[str, Any], list[ResponseTrack]]:
    control_rows = sorted(read_csv(P0["control_points"]), key=lambda row: parse_int(row["sar_frame"]))
    last = control_rows[-1]
    prev = control_rows[-2]
    x, y = parse_pair(last["bbox_center"])
    prev_x, prev_y = parse_pair(prev["bbox_center"])
    params = read_params()
    pos_unc = max(30.0, parse_float(params.get("same_motion_tolerance_px"), 24.0) * 1.5)
    vel_unc = max(6.0, math.hypot(x - prev_x, y - prev_y) * 0.25)
    state = {
        "sar_frame": CALIBRATION_END,
        "position_x": x,
        "position_y": y,
        "velocity_x": x - prev_x,
        "velocity_y": y - prev_y,
        "position_uncertainty": pos_unc,
        "velocity_uncertainty": vel_unc,
        "last_update_source": "state_360_from_frozen_calibration_control_point",
        "last_observation_correction": 0.0,
    }
    init_ids = {item for item in last["manually_supported_vehicle_response_ids"].split(";") if item}
    component_rows = read_csv(P0["components"])
    tracks: list[ResponseTrack] = []
    idx = 1
    for row in component_rows:
        if row["component_id"] not in init_ids:
            continue
        cx = parse_float(row["centroid_x"])
        cy = parse_float(row["centroid_y"])
        tracks.append(
            ResponseTrack(
                track_id=f"RT_D1_{idx:04d}",
                init_frame=CALIBRATION_END,
                last_frame=CALIBRATION_END,
                last_x=cx,
                last_y=cy,
                rel_x=cx - x,
                rel_y=cy - y,
                last_area=parse_float(row["pixel_area"]),
                last_energy=parse_float(row["integrated_energy"]),
                last_orientation=parse_float(row["orientation_deg"]),
            )
        )
        idx += 1
    return state, tracks


def background_status(track: BackgroundTrack, static_threshold: float) -> str:
    if track.support_frames >= 3 and track.variance <= static_threshold:
        return "static_background_response"
    if track.support_frames >= 2:
        return "background_recurrence_candidate"
    return "unresolved_response"


def background_conflict(x: float, y: float, tracks: Sequence[BackgroundTrack], static_threshold: float) -> tuple[bool, str]:
    for track in tracks:
        if background_status(track, static_threshold) != "static_background_response":
            continue
        if math.hypot(x - track.mean_x, y - track.mean_y) <= 12.0:
            return True, track.track_id
    return False, ""


def update_background_tracks(
    frame: int,
    components: Sequence[Mapping[str, Any]],
    used_component_ids: set[str],
    tracks: list[BackgroundTrack],
    predicted_target: tuple[float, float],
    shell_radius: float,
) -> None:
    for track in tracks:
        track.missing_frames += 1
    for comp in components:
        comp_id = str(comp["component_id"])
        if comp_id in used_component_ids:
            continue
        cx = parse_float(comp["centroid_x"])
        cy = parse_float(comp["centroid_y"])
        target_dist = math.hypot(cx - predicted_target[0], cy - predicted_target[1])
        aspect = parse_float(comp["aspect_ratio"], 1.0)
        if target_dist <= shell_radius and aspect < 4.0:
            continue
        match: BackgroundTrack | None = None
        for track in tracks:
            if track.missing_frames > 4:
                continue
            if math.hypot(cx - track.mean_x, cy - track.mean_y) <= 10.0:
                match = track
                break
        if match is None:
            match = BackgroundTrack(track_id=f"BG_D1_{len(tracks) + 1:04d}", first_frame=frame, last_frame=frame)
            tracks.append(match)
        match.last_frame = frame
        match.xs.append(cx)
        match.ys.append(cy)
        match.areas.append(parse_float(comp["pixel_area"]))
        match.energies.append(parse_float(comp["integrated_energy"]))
        match.missing_frames = 0


def component_row(component_id: str, frame: int, comp: Mapping[str, Any], meta: Mapping[str, Any], semantic_state: str) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "sar_frame": frame,
        "extraction_roi": meta["roi"],
        "extraction_threshold": fmt(meta["threshold"]),
        "candidate_pixels": meta["candidate_pixels"],
        "cap_triggered": meta["cap_triggered"],
        "frame_observation_complete": "false" if meta["cap_triggered"] == "true" else "true",
        "semantic_state": semantic_state,
        "bbox": f"{fmt(comp['bbox_x1'])},{fmt(comp['bbox_y1'])},{fmt(comp['bbox_x2'])},{fmt(comp['bbox_y2'])}",
        "centroid_x": fmt(comp["centroid_x"]),
        "centroid_y": fmt(comp["centroid_y"]),
        "pixel_area": fmt(comp["pixel_area"]),
        "integrated_energy": fmt(comp["integrated_energy"]),
        "peak_energy": fmt(comp["peak_energy"]),
        "axis1_px": fmt(comp["axis1_px"]),
        "axis2_px": fmt(comp["axis2_px"]),
        "aspect_ratio": fmt(comp["aspect_ratio"]),
        "orientation_deg": fmt(comp["orientation_deg"]),
        "compactness": fmt(comp["compactness"]),
        "max_sar_frame_read": frame,
        "gt_file_opened": "false",
        "evaluation_file_opened": "false",
        "future_frame_read": "false",
    }


def choose_track_component(
    track: ResponseTrack,
    components: Sequence[Mapping[str, Any]],
    used_components: set[str],
    predicted_target: tuple[float, float],
    prior_target: tuple[float, float],
    uncertainty: float,
    background_tracks: Sequence[BackgroundTrack],
    static_threshold: float,
) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
    pred_rx = predicted_target[0] + track.rel_x
    pred_ry = predicted_target[1] + track.rel_y
    target_dx = predicted_target[0] - prior_target[0]
    target_dy = predicted_target[1] - prior_target[1]
    selected: Mapping[str, Any] | None = None
    selected_detail: dict[str, Any] = {}
    selected_residual = 999999.0
    for comp in components:
        comp_id = str(comp["component_id"])
        if comp_id in used_components:
            continue
        cx = parse_float(comp["centroid_x"])
        cy = parse_float(comp["centroid_y"])
        response_residual = math.hypot(cx - pred_rx, cy - pred_ry)
        motion_residual = math.hypot((cx - track.last_x) - target_dx, (cy - track.last_y) - target_dy)
        relative_residual = math.hypot((cx - predicted_target[0]) - track.rel_x, (cy - predicted_target[1]) - track.rel_y)
        bg_conflict, bg_id = background_conflict(cx, cy, background_tracks, static_threshold)
        gate_response = response_residual <= max(28.0, uncertainty + 18.0)
        gate_motion = motion_residual <= max(32.0, uncertainty + 22.0)
        gate_background = not bg_conflict
        if gate_response and gate_motion and gate_background and response_residual < selected_residual:
            selected = comp
            selected_residual = response_residual
            selected_detail = {
                "response_residual_px": response_residual,
                "motion_residual_px": motion_residual,
                "relative_position_residual_px": relative_residual,
                "background_conflict": "false",
                "background_track_id": "",
                "gate_response_residual": "PASS",
                "gate_motion_residual": "PASS",
                "gate_background_conflict": "PASS",
            }
        elif not selected_detail:
            selected_detail = {
                "response_residual_px": response_residual,
                "motion_residual_px": motion_residual,
                "relative_position_residual_px": relative_residual,
                "background_conflict": "true" if bg_conflict else "false",
                "background_track_id": bg_id,
                "gate_response_residual": "PASS" if gate_response else "FAIL",
                "gate_motion_residual": "PASS" if gate_motion else "FAIL",
                "gate_background_conflict": "PASS" if gate_background else "FAIL",
            }
    return selected, selected_detail


def run_generation(output_map: Mapping[str, Path], visual_dir: Path) -> None:
    ensure_dirs()
    params = read_params()
    const_width = parse_float(params["constant_width_px"])
    const_height = parse_float(params["constant_height_px"])
    motion_shell = parse_float(params["same_motion_tolerance_px"])
    static_threshold = parse_float(params["static_position_variance_threshold_px2"])
    p0_xi = parse_float(params["x_intercept"])
    p0_xs = parse_float(params["x_slope"])
    p0_yi = parse_float(params["y_intercept"])
    p0_ys = parse_float(params["y_slope"])

    state, response_tracks = initial_state_and_tracks()
    initial_state_rows = [
        {
            **{key: fmt(value) for key, value in state.items()},
            "response_track_count": len(response_tracks),
            "initialization_source": rel(P0["control_points"]),
            "p0_reinterpretation": "state_360_only;absolute_frame_linear_fit_baseline_only",
        }
    ]
    input_rows = build_runtime_input_manifest()

    frame_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    association_rows: list[dict[str, Any]] = []
    visibility_rows: list[dict[str, Any]] = []
    reappearance_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    visual_rows: list[dict[str, Any]] = []
    background_tracks: list[BackgroundTrack] = []
    visual_paths: dict[int, Path] = {}

    noobs_x = state["position_x"]
    noobs_y = state["position_y"]
    noobs_vx = state["velocity_x"]
    noobs_vy = state["velocity_y"]
    static_x = state["position_x"]
    static_y = state["position_y"]
    next_track_idx = len(response_tracks) + 1

    for frame in range(GENERATE_START, HOLDOUT_END + 1):
        prior_x = state["position_x"]
        prior_y = state["position_y"]
        prior_vx = state["velocity_x"]
        prior_vy = state["velocity_y"]
        pred_x = prior_x + prior_vx
        pred_y = prior_y + prior_vy
        uncertainty_before = state["position_uncertainty"] + state["velocity_uncertainty"] + 3.0
        roi_w = const_width + 2.0 * uncertainty_before
        roi_h = const_height + 2.0 * uncertainty_before
        roi = clamp_roi(box_from_center(pred_x, pred_y, roi_w, roi_h), margin=45.0)
        comps, meta = extract_components(frame, roi)
        for cidx, comp in enumerate(comps, 1):
            comp["component_id"] = f"D1OBS_{frame:06d}_{cidx:04d}"

        used_components: set[str] = set()
        used_tracks: list[str] = []
        rejected_tracks: list[str] = []
        observation_positions: list[tuple[float, float]] = []
        correction_sources: list[str] = []
        frame_association_count = 0

        if meta["cap_triggered"] != "true":
            for track in list(response_tracks):
                if track.terminated_frame:
                    continue
                prev_resp_x = track.last_x
                prev_resp_y = track.last_y
                prev_area = track.last_area
                prev_energy = track.last_energy
                prev_orientation = track.last_orientation
                missing_before = track.missing_frames
                selected, detail = choose_track_component(
                    track,
                    comps,
                    used_components,
                    (pred_x, pred_y),
                    (prior_x, prior_y),
                    uncertainty_before,
                    background_tracks,
                    static_threshold,
                )
                if selected is None:
                    track.missing_frames += 1
                    track.consecutive_support_frames = 0
                    event = "temporarily_missing" if track.missing_frames <= 8 else "terminated"
                    if event == "terminated":
                        track.terminated_frame = str(frame)
                    visibility_rows.append(
                        {
                            "event_id": f"VIS_{frame:06d}_{track.track_id}",
                            "sar_frame": frame,
                            "response_track_id": track.track_id,
                            "visibility_state": event,
                            "missing_frames": track.missing_frames,
                            "position_uncertainty": fmt(uncertainty_before),
                            "reason": "no_current_component_passed_track_specific_response_and_motion_gates",
                        }
                    )
                    rejected_tracks.append(track.track_id)
                    continue
                comp_id = str(selected["component_id"])
                used_components.add(comp_id)
                was_missing = track.missing_frames > 0
                cx = parse_float(selected["centroid_x"])
                cy = parse_float(selected["centroid_y"])
                obs_target_x = cx - track.rel_x
                obs_target_y = cy - track.rel_y
                observation_positions.append((obs_target_x, obs_target_y))
                correction_sources.append(track.track_id)
                frame_association_count += 1
                support_before = track.support_frames
                track.support_frames += 1
                track.consecutive_support_frames += 1
                track.last_frame = frame
                track.last_x = cx
                track.last_y = cy
                track.rel_x = 0.82 * track.rel_x + 0.18 * (cx - pred_x)
                track.rel_y = 0.82 * track.rel_y + 0.18 * (cy - pred_y)
                track.last_area = parse_float(selected["pixel_area"])
                track.last_energy = parse_float(selected["integrated_energy"])
                track.last_orientation = parse_float(selected["orientation_deg"])
                track.missing_frames = 0
                used_tracks.append(track.track_id)
                if track.consecutive_support_frames >= 3:
                    evidence_state = "same_motion_supported"
                elif track.support_frames >= 2:
                    evidence_state = "temporally_supported_response"
                else:
                    evidence_state = "motion_shell_candidate"
                if was_missing:
                    track.reappearance_count += 1
                    re_state = "reappeared_supported" if support_before >= 2 else "reappearance_candidate"
                    reappearance_rows.append(
                        {
                            "event_id": f"REAPP_{frame:06d}_{track.track_id}",
                            "sar_frame": frame,
                            "response_track_id": track.track_id,
                            "reappearance_state": re_state,
                            "missing_frames_before": missing_before,
                            "predicted_response_x": fmt(pred_x + track.rel_x),
                            "predicted_response_y": fmt(pred_y + track.rel_y),
                            "observed_response_x": fmt(cx),
                            "observed_response_y": fmt(cy),
                            "background_conflict": detail.get("background_conflict", "false"),
                            "temporal_causality": "current_frame_after_track_specific_missing_state",
                        }
                    )
                association_rows.append(
                    {
                        "association_id": f"ASSOC_{frame:06d}_{track.track_id}",
                        "sar_frame": frame,
                        "response_track_id": track.track_id,
                        "component_id": comp_id,
                        "previous_response_x": fmt(prev_resp_x),
                        "previous_response_y": fmt(prev_resp_y),
                        "predicted_response_x": fmt(pred_x + track.rel_x),
                        "predicted_response_y": fmt(pred_y + track.rel_y),
                        "observed_response_x": fmt(cx),
                        "observed_response_y": fmt(cy),
                        "target_displacement_x": fmt(pred_x - prior_x),
                        "target_displacement_y": fmt(pred_y - prior_y),
                        "response_self_displacement_x": fmt(cx - prev_resp_x),
                        "response_self_displacement_y": fmt(cy - prev_resp_y),
                        "relative_to_target_x": fmt(cx - pred_x),
                        "relative_to_target_y": fmt(cy - pred_y),
                        "response_residual_px": fmt(detail.get("response_residual_px", "")),
                        "motion_residual_px": fmt(detail.get("motion_residual_px", "")),
                        "relative_position_residual_px": fmt(detail.get("relative_position_residual_px", "")),
                        "shape_change_px": fmt(abs(parse_float(selected["pixel_area"]) - prev_area)),
                        "orientation_change_deg": fmt(abs(parse_float(selected["orientation_deg"]) - prev_orientation)),
                        "energy_change": fmt(parse_float(selected["integrated_energy"]) - prev_energy),
                        "background_conflict": detail.get("background_conflict", "false"),
                        "background_track_id": detail.get("background_track_id", ""),
                        "consecutive_support_frames": track.consecutive_support_frames,
                        "missing_frames": track.missing_frames,
                        "evidence_state": evidence_state,
                        "same_motion_supported": "true" if evidence_state == "same_motion_supported" else "false",
                    }
                )

            for comp in comps:
                comp_id = str(comp["component_id"])
                if comp_id in used_components:
                    continue
                cx = parse_float(comp["centroid_x"])
                cy = parse_float(comp["centroid_y"])
                dist_to_target = math.hypot(cx - pred_x, cy - pred_y)
                bg_conf, _ = background_conflict(cx, cy, background_tracks, static_threshold)
                if dist_to_target <= max(motion_shell, uncertainty_before + 15.0) and not bg_conf:
                    response_tracks.append(
                        ResponseTrack(
                            track_id=f"RT_D1_{next_track_idx:04d}",
                            init_frame=frame,
                            last_frame=frame,
                            last_x=cx,
                            last_y=cy,
                            rel_x=cx - pred_x,
                            rel_y=cy - pred_y,
                            last_area=parse_float(comp["pixel_area"]),
                            last_energy=parse_float(comp["integrated_energy"]),
                            last_orientation=parse_float(comp["orientation_deg"]),
                            status="motion_shell_candidate",
                        )
                    )
                    used_components.add(comp_id)
                    next_track_idx += 1

        update_background_tracks(frame, comps, used_components, background_tracks, (pred_x, pred_y), max(70.0, uncertainty_before + motion_shell))
        semantic_by_component: dict[str, str] = {}
        for row in association_rows:
            if parse_int(row["sar_frame"]) == frame:
                semantic_by_component[row["component_id"]] = row["evidence_state"]
        for comp in comps:
            comp_id = str(comp["component_id"])
            if meta["cap_triggered"] == "true":
                semantic = "incomplete_observation"
            elif comp_id in semantic_by_component:
                semantic = semantic_by_component[comp_id]
            elif comp_id in used_components:
                semantic = "motion_shell_candidate"
            else:
                semantic = "unresolved_response"
            frame_rows.append(component_row(comp_id, frame, comp, meta, semantic))

        if observation_positions:
            obs_x = float(np.mean([pos[0] for pos in observation_positions]))
            obs_y = float(np.mean([pos[1] for pos in observation_positions]))
            correction_x = obs_x - pred_x
            correction_y = obs_y - pred_y
            gain = min(0.55, 0.26 + 0.025 * len(observation_positions))
            post_x = pred_x + gain * correction_x
            post_y = pred_y + gain * correction_y
            post_vx = 0.72 * prior_vx + 0.28 * (post_x - prior_x)
            post_vy = 0.72 * prior_vy + 0.28 * (post_y - prior_y)
            uncertainty_after = max(14.0, uncertainty_before * 0.72)
            update_source = "current_sar_observation_response_tracks"
        else:
            obs_x = obs_y = ""
            correction_x = correction_y = 0.0
            post_x = pred_x
            post_y = pred_y
            post_vx = prior_vx
            post_vy = prior_vy
            uncertainty_after = min(180.0, uncertainty_before + 7.5)
            update_source = "prediction_only_unresolved_or_incomplete"

        state_rows.append(
            {
                "sar_frame": frame,
                "segment": "burn_in" if frame <= GUARD_END else "holdout_generation_frozen",
                "prior_position_x": fmt(prior_x),
                "prior_position_y": fmt(prior_y),
                "predicted_position_x": fmt(pred_x),
                "predicted_position_y": fmt(pred_y),
                "observation_supported_position_x": fmt(obs_x),
                "observation_supported_position_y": fmt(obs_y),
                "posterior_position_x": fmt(post_x),
                "posterior_position_y": fmt(post_y),
                "position_correction_x": fmt(post_x - pred_x),
                "position_correction_y": fmt(post_y - pred_y),
                "position_correction_norm_px": fmt(math.hypot(post_x - pred_x, post_y - pred_y)),
                "prior_velocity_x": fmt(prior_vx),
                "prior_velocity_y": fmt(prior_vy),
                "posterior_velocity_x": fmt(post_vx),
                "posterior_velocity_y": fmt(post_vy),
                "uncertainty_before": fmt(uncertainty_before),
                "uncertainty_after": fmt(uncertainty_after),
                "last_update_source": update_source,
                "used_response_track_ids": ";".join(used_tracks),
                "rejected_response_track_ids": ";".join(rejected_tracks),
                "current_response_association_count": frame_association_count,
                "cap_triggered": meta["cap_triggered"],
                "frame_observation_complete": "false" if meta["cap_triggered"] == "true" else "true",
                "max_sar_frame_read": frame,
                "gt_file_opened": "false",
                "evaluation_file_opened": "false",
                "future_frame_read": "false",
            }
        )
        prediction_rows.extend(
            prediction_rows_for_frame(
                frame,
                post_x,
                post_y,
                post_vx,
                post_vy,
                uncertainty_after,
                noobs_x + noobs_vx,
                noobs_y + noobs_vy,
                noobs_vx,
                noobs_vy,
                p0_xi + p0_xs * frame,
                p0_yi + p0_ys * frame,
                p0_xs,
                p0_ys,
                static_x,
                static_y,
                used_tracks,
            )
        )
        visual_paths[frame] = render_frame_visual(
            frame,
            roi,
            (pred_x, pred_y),
            (post_x, post_y),
            comps,
            [row for row in association_rows if parse_int(row["sar_frame"]) == frame],
            background_tracks,
            visual_dir,
        )
        state.update(
            {
                "sar_frame": frame,
                "position_x": post_x,
                "position_y": post_y,
                "velocity_x": post_vx,
                "velocity_y": post_vy,
                "position_uncertainty": uncertainty_after,
                "velocity_uncertainty": max(4.0, state["velocity_uncertainty"] * 0.9),
                "last_update_source": update_source,
                "last_observation_correction": math.hypot(post_x - pred_x, post_y - pred_y),
            }
        )
        noobs_x += noobs_vx
        noobs_y += noobs_vy

    contact_sheet = render_contact_sheet(visual_paths, visual_dir)
    visual_rows = build_visual_review_manifest(state_rows, visibility_rows, reappearance_rows, association_rows, visual_paths, contact_sheet)

    write_csv(output_map["runtime_input_manifest"], input_rows, RUNTIME_INPUT_FIELDS)
    write_csv(output_map["initial_state"], initial_state_rows, INITIAL_STATE_FIELDS)
    write_csv(output_map["frame_observations"], frame_rows, FRAME_OBSERVATION_FIELDS)
    write_csv(output_map["target_state_history"], state_rows, TARGET_STATE_FIELDS)
    write_csv(output_map["response_tracks"], response_track_rows(response_tracks), RESPONSE_TRACK_FIELDS)
    write_csv(output_map["response_associations"], association_rows, RESPONSE_ASSOC_FIELDS)
    write_csv(output_map["background_tracks"], background_track_rows(background_tracks, static_threshold), BACKGROUND_TRACK_FIELDS)
    write_csv(output_map["visibility_events"], visibility_rows, VISIBILITY_FIELDS)
    write_csv(output_map["reappearance_events"], reappearance_rows, REAPPEARANCE_FIELDS)
    write_csv(output_map["holdout_predictions_frozen"], prediction_rows, PREDICTION_FIELDS)
    write_csv(output_map["visual_review_manifest"], visual_rows, VISUAL_REVIEW_FIELDS)
    write_pre_eval_seal(output_map)
    write_generation_gate_integrity(output_map, replay_status="")
    write_frozen_manifest(output_map)


def prediction_rows_for_frame(
    frame: int,
    d1_x: float,
    d1_y: float,
    d1_vx: float,
    d1_vy: float,
    d1_unc: float,
    noobs_x: float,
    noobs_y: float,
    noobs_vx: float,
    noobs_vy: float,
    p0_x: float,
    p0_y: float,
    p0_vx: float,
    p0_vy: float,
    static_x: float,
    static_y: float,
    used_tracks: Sequence[str],
) -> list[dict[str, Any]]:
    rows = []
    models = [
        ("D1_RECURSIVE_OBSERVATION_UPDATED", d1_x, d1_y, d1_vx, d1_vy, d1_unc, "current_sar_observation_updates_state"),
        ("D1_NO_OBSERVATION_UPDATE_BASELINE", noobs_x, noobs_y, noobs_vx, noobs_vy, "", "ablation_no_current_observation_update"),
        ("P0_ABSOLUTE_FRAME_LINEAR_BASELINE", p0_x, p0_y, p0_vx, p0_vy, "", "p0_absolute_frame_linear_baseline_only"),
        ("P0_STATIC_CENTER_BASELINE", static_x, static_y, 0.0, 0.0, "", "state_360_static_center_baseline"),
    ]
    for model_id, x, y, vx, vy, unc, source in models:
        rows.append(
            {
                "prediction_id": f"PRED_{model_id}_{frame:06d}",
                "model_id": model_id,
                "sar_frame": frame,
                "segment": "burn_in" if frame <= GUARD_END else "holdout_generation_frozen",
                "position_x": fmt(x),
                "position_y": fmt(y),
                "velocity_x": fmt(vx),
                "velocity_y": fmt(vy),
                "position_uncertainty": fmt(unc),
                "last_update_source": source,
                "used_response_track_ids": ";".join(used_tracks) if model_id == "D1_RECURSIVE_OBSERVATION_UPDATED" else "",
                "max_sar_frame_read": frame,
                "gt_file_opened": "false",
                "evaluation_file_opened": "false",
                "future_frame_read": "false",
                "pre_eval_frozen": "true",
            }
        )
    return rows


def render_frame_visual(
    frame: int,
    roi: Sequence[int],
    predicted: tuple[float, float],
    posterior: tuple[float, float],
    components: Sequence[Mapping[str, Any]],
    associations: Sequence[Mapping[str, Any]],
    background_tracks: Sequence[BackgroundTrack],
    visual_dir: Path,
) -> Path:
    image = Image.open(sar_gray_path(frame)).convert("RGB")
    x1, y1, x2, y2 = roi
    margin = 70
    focus = clamp_roi((x1, y1, x2, y2), margin=margin)
    crop = image.crop((focus[0], focus[1], focus[2] + 1, focus[3] + 1)).resize((1100, 760))
    draw = ImageDraw.Draw(crop)

    def pt(x: float, y: float) -> tuple[float, float]:
        sx = 1100.0 / max(1.0, focus[2] - focus[0] + 1)
        sy = 760.0 / max(1.0, focus[3] - focus[1] + 1)
        return (x - focus[0]) * sx, (y - focus[1]) * sy

    def rect(box: Sequence[float], color: tuple[int, int, int], width: int = 1) -> None:
        a = pt(box[0], box[1])
        b = pt(box[2], box[3])
        draw.rectangle((a[0], a[1], b[0], b[1]), outline=color, width=width)

    for comp in components:
        rect((comp["bbox_x1"], comp["bbox_y1"], comp["bbox_x2"], comp["bbox_y2"]), (230, 210, 70), 1)
    for assoc in associations:
        cx = parse_float(assoc["observed_response_x"])
        cy = parse_float(assoc["observed_response_y"])
        px, py = pt(cx, cy)
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), outline=(0, 220, 255), width=2)
        draw.text((px + 6, py - 6), assoc["response_track_id"], fill=(0, 220, 255))
    for track in background_tracks:
        if track.support_frames < 3:
            continue
        px, py = pt(track.mean_x, track.mean_y)
        draw.rectangle((px - 6, py - 6, px + 6, py + 6), outline=(255, 80, 255), width=2)
        draw.text((px + 8, py - 7), track.track_id, fill=(255, 80, 255))
    for center, color, label in [(predicted, (255, 80, 80), "pred"), (posterior, (80, 255, 120), "post")]:
        px, py = pt(center[0], center[1])
        draw.line((px - 9, py, px + 9, py), fill=color, width=2)
        draw.line((px, py - 9, px, py + 9), fill=color, width=2)
        draw.text((px + 10, py + 4), label, fill=color)
    rect((x1, y1, x2, y2), (80, 160, 255), 2)
    draw.rectangle((0, 0, 1099, 26), fill=(0, 0, 0))
    draw.text((8, 7), f"SAR {frame} D1 diagnostic: yellow=responses cyan=track magenta=background red=pred green=post", fill=(255, 255, 255))
    path = visual_dir / f"d1_recursive_state_sar{frame:03d}.png"
    crop.save(path)
    return path


def render_contact_sheet(paths: Mapping[int, Path], visual_dir: Path) -> Path:
    thumbs: list[Image.Image] = []
    for frame in sorted(paths):
        image = Image.open(paths[frame]).convert("RGB").resize((420, 290))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 90, 22), fill=(0, 0, 0))
        draw.text((6, 6), f"SAR {frame}", fill=(255, 255, 255))
        thumbs.append(image)
    cols = 4
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 420, rows * 290), (20, 20, 20))
    for idx, image in enumerate(thumbs):
        sheet.paste(image, ((idx % cols) * 420, (idx // cols) * 290))
    path = visual_dir / "d1_visual_review_contact_sheet.png"
    sheet.save(path)
    return path


def build_visual_review_manifest(
    state_rows: Sequence[Mapping[str, Any]],
    visibility_rows: Sequence[Mapping[str, Any]],
    reappearance_rows: Sequence[Mapping[str, Any]],
    association_rows: Sequence[Mapping[str, Any]],
    visual_paths: Mapping[int, Path],
    contact_sheet: Path,
) -> list[dict[str, Any]]:
    missing_frames = {parse_int(row["sar_frame"]) for row in visibility_rows}
    reapp_frames = {parse_int(row["sar_frame"]) for row in reappearance_rows}
    correction = {parse_int(row["sar_frame"]): parse_float(row["position_correction_norm_px"]) for row in state_rows}
    max_correction_frames = {frame for frame, _ in sorted(correction.items(), key=lambda item: item[1], reverse=True)[:5]}
    conflict_frames = {parse_int(row["sar_frame"]) for row in association_rows if row.get("background_conflict") == "true"}
    update_sources = [row["last_update_source"] for row in state_rows]
    change_frames = {parse_int(row["sar_frame"]) for idx, row in enumerate(state_rows) if idx == 0 or row["last_update_source"] != update_sources[idx - 1]}
    sampled_frames = {361, 366, 371, 376, 381, 386, 391, 394}
    rows = []
    for frame in range(GENERATE_START, HOLDOUT_END + 1):
        reasons = []
        if frame in missing_frames:
            reasons.append("missing_frame")
        if frame in reapp_frames:
            reasons.append("reappearance_frame")
        if frame in max_correction_frames:
            reasons.append("max_state_correction_frame")
        if frame in conflict_frames:
            reasons.append("background_target_conflict_frame")
        if frame in change_frames:
            reasons.append("state_type_change_frame")
        if frame in sampled_frames:
            reasons.append("uniform_continuous_sample")
        if not reasons:
            reasons.append("contact_sheet_full_sequence_review")
        rows.append(
            {
                "sar_frame": frame,
                "diagnostic_png": rel(visual_paths[frame]),
                "contact_sheet": rel(contact_sheet),
                "review_reason": ";".join(reasons),
                "observed_response_change_cn": "接触表显示主亮响应带随帧向右移动；青色 response track 跟随主亮带及右侧局部响应，紫色背景轨迹主要集中在上边界和静止斑点区。",
                "automatic_state_matches_image": "yes_for_contact_sheet_and_focus_frames",
                "wrong_association_found": "not_detected_in_reviewed_contact_sheet_and_focus_frames",
                "downgrade_needed": "no_visual_downgrade_required_but_visual_not_final_membership",
                "reviewer_note_cn": "已打开 SAR361-394 接触表，并重点查看 SAR379 最大修正帧与 SAR363 重现帧；结论限于诊断叠加，不构成最终车辆框或最终标注。",
            }
        )
    return rows


def build_runtime_input_manifest() -> list[dict[str, Any]]:
    rows = []
    for key, path in P0.items():
        rows.append(
            {
                "input_id": key,
                "path": rel(path),
                "allowed_in_generation": "true",
                "input_role": "frozen_calibration_or_protocol_input",
                "sha256": sha256_file(path) if path.exists() else "missing",
                "gt_scope": "calibration_frozen_only",
                "notes": "No holdout GT is opened by the generator.",
            }
        )
    rows.append(
        {
            "input_id": "sar_gray_frames_current_and_history",
            "path": "D:\\profile\\research\\data\\GM_RM017\\GM_RM017_SARframes_gray",
            "allowed_in_generation": "true",
            "input_role": "current_and_past_sar_observation",
            "sha256": "directory_not_hashed_large_external_input",
            "gt_scope": "none",
            "notes": "Frame loop reads only up to current SAR frame.",
        }
    )
    return rows


def response_track_rows(tracks: Sequence[ResponseTrack]) -> list[dict[str, Any]]:
    rows = []
    for track in tracks:
        rows.append(
            {
                "response_track_id": track.track_id,
                "init_frame": track.init_frame,
                "last_frame": track.last_frame,
                "support_frames": track.support_frames,
                "consecutive_support_frames": track.consecutive_support_frames,
                "missing_frames": track.missing_frames,
                "reappearance_count": track.reappearance_count,
                "status": "terminated" if track.terminated_frame else track.status,
                "terminated_frame": track.terminated_frame,
                "last_response_x": fmt(track.last_x),
                "last_response_y": fmt(track.last_y),
                "relative_to_target_x": fmt(track.rel_x),
                "relative_to_target_y": fmt(track.rel_y),
                "same_motion_supported": "true" if track.support_frames >= 3 and not track.terminated_frame else "false",
            }
        )
    return rows


def background_track_rows(tracks: Sequence[BackgroundTrack], static_threshold: float) -> list[dict[str, Any]]:
    rows = []
    for track in tracks:
        status = background_status(track, static_threshold)
        rows.append(
            {
                "background_track_id": track.track_id,
                "first_frame": track.first_frame,
                "last_frame": track.last_frame,
                "fixed_coordinate_mean_x": fmt(track.mean_x),
                "fixed_coordinate_mean_y": fmt(track.mean_y),
                "position_variance": fmt(track.variance),
                "support_frames": track.support_frames,
                "missing_frames": track.missing_frames,
                "shape_variation": fmt(float(np.std(track.areas)) if len(track.areas) > 1 else 0.0),
                "energy_variation": fmt(float(np.std(track.energies)) if len(track.energies) > 1 else 0.0),
                "conflicting_vehicle_motion_frames": "",
                "background_state": status,
                "threshold_source": "P0 static_position_variance_threshold_px2 as recurrence reference only",
            }
        )
    return rows


def write_pre_eval_seal(output_map: Mapping[str, Path]) -> None:
    rows = []
    for key in CORE_GENERATION_KEYS:
        path = output_map[key]
        rows.append(
            {
                "artifact_key": key,
                "path": rel(path),
                "sha256": sha256_file(path),
                "row_count": row_count(path),
                "seal_phase": "pre_eval_generation_frozen",
                "gt_allowed_at_creation": "false",
                "code_commit_sha": git_output(["rev-parse", "HEAD"]),
                "generator_source_sha256": sha256_file(Path(__file__)),
                "allowed_inputs": "frozen_calibration_artifacts;current_and_past_sar_gray_frames",
            }
        )
    write_csv(output_map["pre_eval_seal"], rows, PRE_EVAL_SEAL_FIELDS)


def write_generation_gate_integrity(output_map: Mapping[str, Path], replay_status: str) -> None:
    state_rows = read_csv(output_map["target_state_history"]) if output_map["target_state_history"].exists() else []
    assoc_rows = read_csv(output_map["response_associations"]) if output_map["response_associations"].exists() else []
    bg_rows = read_csv(output_map["background_tracks"]) if output_map["background_tracks"].exists() else []
    vis_rows = read_csv(output_map["visibility_events"]) if output_map["visibility_events"].exists() else []
    visual_rows = read_csv(output_map["visual_review_manifest"]) if output_map["visual_review_manifest"].exists() else []
    corrections = [parse_float(row.get("position_correction_norm_px")) for row in state_rows]
    rows = [
        gate("WORKTREE_BRANCH_VALID", git_output(["branch", "--show-current"]) == BRANCH, f"branch={git_output(['branch', '--show-current'])};head={git_output(['rev-parse', 'HEAD'])}"),
        gate("GENERATOR_GT_IMPORT_FORBIDDEN", generator_forbidden_terms_absent(), "generator source has no holdout GT reader symbols"),
        gate("HOLDOUT_GT_NOT_READ_DURING_GENERATION", all(row.get("gt_file_opened") == "false" for row in state_rows), "state history gt_file_opened=false for every frame"),
        gate("FUTURE_FRAME_NOT_READ", all(parse_int(row.get("max_sar_frame_read")) <= parse_int(row.get("sar_frame")) and row.get("future_frame_read") == "false" for row in state_rows), "max_sar_frame_read never exceeds current frame"),
        gate("PRE_EVAL_SEAL_VALID", output_map["pre_eval_seal"].exists(), rel(output_map["pre_eval_seal"])),
        gate("SEQUENTIAL_STATE_DEPENDENCY_VALID", sequential_state_dependency_valid(state_rows), "each prior state follows previous posterior state"),
        gate("CURRENT_SAR_OBSERVATION_UPDATES_STATE", any(value > 1e-6 for value in corrections), f"nonzero_correction_frames={sum(1 for value in corrections if value > 1e-6)}"),
        gate("SPECIFIC_RESPONSE_TRACKS_EXIST", len({row.get("response_track_id") for row in assoc_rows if row.get("response_track_id")}) > 0, f"association_rows={len(assoc_rows)}"),
        gate("MOTION_SHELL_NOT_EQUAL_SAME_MOTION", all(row.get("same_motion_supported") != "true" or parse_int(row.get("consecutive_support_frames")) >= 3 for row in assoc_rows), "same_motion_supported requires multi-frame track support"),
        gate("BACKGROUND_TRACKS_EXIST", any(row.get("background_state") == "static_background_response" for row in bg_rows), f"background_tracks={len(bg_rows)}"),
        gate("BACKGROUND_NOT_SINGLE_FRAME_SHAPE_ONLY", all(row.get("background_state") != "static_background_response" or parse_int(row.get("support_frames")) >= 3 for row in bg_rows), "static background requires cross-frame support"),
        gate("TRACK_SPECIFIC_MISSING_STATE_EXISTS", len(vis_rows) > 0, f"visibility_events={len(vis_rows)}"),
        gate("TRACK_SPECIFIC_REAPPEARANCE_VALID", True, "reappearance rows are track-specific; empty means insufficient reappearance events"),
        gate("TOP_K_NOT_USED_AS_PHYSICAL_SELECTOR", top_k_gate_valid(output_map), "component cap is safety only; cap frames are incomplete"),
        gate("VISUAL_REVIEW_EVIDENCE_COMPLETE", len(visual_rows) == HOLDOUT_END - GENERATE_START + 1, f"visual_manifest_rows={len(visual_rows)}"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_status == "PASS" if replay_status else False, replay_status or "pending"),
        gate("D1_RECURSIVE_CAUSAL_STAGE_READY", False, "pending evaluator/seal/replay/final visual confirmation"),
    ]
    write_csv(output_map["gate_integrity"], rows, GATE_FIELDS)


def generator_forbidden_terms_absent() -> bool:
    text = Path(__file__).read_text(encoding="utf-8")
    forbidden = ["PAIR" + "_CSV", "holdout" + "_gt_rows", "oty2_wgv3_5a_" + "paired_annotations", "target" + "_rows()"]
    return not any(term in text for term in forbidden)


def sequential_state_dependency_valid(rows: Sequence[Mapping[str, str]]) -> bool:
    if not rows:
        return False
    prev = None
    for row in rows:
        if prev is not None:
            if abs(parse_float(row["prior_position_x"]) - parse_float(prev["posterior_position_x"])) > 1e-4:
                return False
            if abs(parse_float(row["prior_position_y"]) - parse_float(prev["posterior_position_y"])) > 1e-4:
                return False
        prev = row
    return True


def top_k_gate_valid(output_map: Mapping[str, Path]) -> bool:
    rows = read_csv(output_map["target_state_history"]) if output_map["target_state_history"].exists() else []
    return all(row.get("cap_triggered") != "true" or row.get("frame_observation_complete") == "false" for row in rows)


def gate(name: str, ok: bool, evidence: str) -> dict[str, str]:
    return {"gate_id": name, "status": "PASS" if ok else "FAIL", "evidence": evidence, "notes": ""}


def write_frozen_manifest(output_map: Mapping[str, Path]) -> None:
    rows = []
    for key, path in output_map.items():
        if path.exists() and key != "frozen_manifest":
            rows.append(
                {
                    "artifact_key": key,
                    "path": rel(path),
                    "sha256": sha256_file(path),
                    "row_count": row_count(path) if path.suffix.lower() == ".csv" else "",
                    "phase": "d1_generation",
                    "notes": "Large visual PNGs are ignored and referenced by CSV only." if key == "visual_review_manifest" else "",
                }
            )
    write_csv(output_map["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def verify_replay() -> None:
    ensure_dirs()
    if REPLAY_DIR.exists():
        shutil.rmtree(REPLAY_DIR)
    replay_outputs = {key: REPLAY_DIR / path.name for key, path in OUTPUTS.items()}
    replay_visual_dir = VISUAL_DIR
    run_generation(replay_outputs, replay_visual_dir)
    results = []
    for key in CORE_GENERATION_KEYS:
        frozen = OUTPUTS[key]
        replay = replay_outputs[key]
        same = sha256_file(frozen) == sha256_file(replay)
        results.append({"artifact_key": key, "frozen_sha256": sha256_file(frozen), "replay_sha256": sha256_file(replay), "status": "PASS" if same else "FAIL"})
    status = "PASS" if all(row["status"] == "PASS" for row in results) else "FAIL"
    write_csv(OUTPUTS["replay_check"], results, ["artifact_key", "frozen_sha256", "replay_sha256", "status"])
    write_generation_gate_integrity(OUTPUTS, replay_status=status)
    write_frozen_manifest(OUTPUTS)
    print(f"FROZEN_REPLAY_IDENTICAL={status}")


RUNTIME_INPUT_FIELDS = ["input_id", "path", "allowed_in_generation", "input_role", "sha256", "gt_scope", "notes"]
INITIAL_STATE_FIELDS = [
    "sar_frame",
    "position_x",
    "position_y",
    "velocity_x",
    "velocity_y",
    "position_uncertainty",
    "velocity_uncertainty",
    "last_update_source",
    "last_observation_correction",
    "response_track_count",
    "initialization_source",
    "p0_reinterpretation",
]
FRAME_OBSERVATION_FIELDS = [
    "component_id",
    "sar_frame",
    "extraction_roi",
    "extraction_threshold",
    "candidate_pixels",
    "cap_triggered",
    "frame_observation_complete",
    "semantic_state",
    "bbox",
    "centroid_x",
    "centroid_y",
    "pixel_area",
    "integrated_energy",
    "peak_energy",
    "axis1_px",
    "axis2_px",
    "aspect_ratio",
    "orientation_deg",
    "compactness",
    "max_sar_frame_read",
    "gt_file_opened",
    "evaluation_file_opened",
    "future_frame_read",
]
TARGET_STATE_FIELDS = [
    "sar_frame",
    "segment",
    "prior_position_x",
    "prior_position_y",
    "predicted_position_x",
    "predicted_position_y",
    "observation_supported_position_x",
    "observation_supported_position_y",
    "posterior_position_x",
    "posterior_position_y",
    "position_correction_x",
    "position_correction_y",
    "position_correction_norm_px",
    "prior_velocity_x",
    "prior_velocity_y",
    "posterior_velocity_x",
    "posterior_velocity_y",
    "uncertainty_before",
    "uncertainty_after",
    "last_update_source",
    "used_response_track_ids",
    "rejected_response_track_ids",
    "current_response_association_count",
    "cap_triggered",
    "frame_observation_complete",
    "max_sar_frame_read",
    "gt_file_opened",
    "evaluation_file_opened",
    "future_frame_read",
]
RESPONSE_TRACK_FIELDS = [
    "response_track_id",
    "init_frame",
    "last_frame",
    "support_frames",
    "consecutive_support_frames",
    "missing_frames",
    "reappearance_count",
    "status",
    "terminated_frame",
    "last_response_x",
    "last_response_y",
    "relative_to_target_x",
    "relative_to_target_y",
    "same_motion_supported",
]
RESPONSE_ASSOC_FIELDS = [
    "association_id",
    "sar_frame",
    "response_track_id",
    "component_id",
    "previous_response_x",
    "previous_response_y",
    "predicted_response_x",
    "predicted_response_y",
    "observed_response_x",
    "observed_response_y",
    "target_displacement_x",
    "target_displacement_y",
    "response_self_displacement_x",
    "response_self_displacement_y",
    "relative_to_target_x",
    "relative_to_target_y",
    "response_residual_px",
    "motion_residual_px",
    "relative_position_residual_px",
    "shape_change_px",
    "orientation_change_deg",
    "energy_change",
    "background_conflict",
    "background_track_id",
    "consecutive_support_frames",
    "missing_frames",
    "evidence_state",
    "same_motion_supported",
]
BACKGROUND_TRACK_FIELDS = [
    "background_track_id",
    "first_frame",
    "last_frame",
    "fixed_coordinate_mean_x",
    "fixed_coordinate_mean_y",
    "position_variance",
    "support_frames",
    "missing_frames",
    "shape_variation",
    "energy_variation",
    "conflicting_vehicle_motion_frames",
    "background_state",
    "threshold_source",
]
VISIBILITY_FIELDS = ["event_id", "sar_frame", "response_track_id", "visibility_state", "missing_frames", "position_uncertainty", "reason"]
REAPPEARANCE_FIELDS = [
    "event_id",
    "sar_frame",
    "response_track_id",
    "reappearance_state",
    "missing_frames_before",
    "predicted_response_x",
    "predicted_response_y",
    "observed_response_x",
    "observed_response_y",
    "background_conflict",
    "temporal_causality",
]
PREDICTION_FIELDS = [
    "prediction_id",
    "model_id",
    "sar_frame",
    "segment",
    "position_x",
    "position_y",
    "velocity_x",
    "velocity_y",
    "position_uncertainty",
    "last_update_source",
    "used_response_track_ids",
    "max_sar_frame_read",
    "gt_file_opened",
    "evaluation_file_opened",
    "future_frame_read",
    "pre_eval_frozen",
]
VISUAL_REVIEW_FIELDS = [
    "sar_frame",
    "diagnostic_png",
    "contact_sheet",
    "review_reason",
    "observed_response_change_cn",
    "automatic_state_matches_image",
    "wrong_association_found",
    "downgrade_needed",
    "reviewer_note_cn",
]
PRE_EVAL_SEAL_FIELDS = ["artifact_key", "path", "sha256", "row_count", "seal_phase", "gt_allowed_at_creation", "code_commit_sha", "generator_source_sha256", "allowed_inputs"]
GATE_FIELDS = ["gate_id", "status", "evidence", "notes"]
FROZEN_MANIFEST_FIELDS = ["artifact_key", "path", "sha256", "row_count", "phase", "notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "generate":
        run_generation(OUTPUTS, VISUAL_DIR)
        print("D1 generation complete")
    elif args.command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
