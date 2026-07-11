"""Generate D1-R1 semantic-integrity artifacts for GM_RM017.

D1-R1 keeps the original D1 outputs as a control and creates a separate
recursive-state repair line. The generator reads frozen P0 calibration artifacts
and current/past SAR gray frames only. It does not read paired annotations,
evaluation tables, future frames, selectors, rankings, or final annotation
outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import math
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw


DATE = "20260712"
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
OUTPUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_d1_r1_gm017_semantic_integrity_{DATE}"
VISUAL_DIR = OUTPUT_DIR / "visual_review"
REPLAY_DIR = OUTPUT_DIR / "_verify_replay_tmp"

CALIBRATION_END = 360
GENERATE_START = 361
GUARD_END = 370
DIAGNOSIS_START = 371
DIAGNOSIS_END = 394
SAR_WIDTH = 2308
SAR_HEIGHT = 1334

P0 = {
    "protocol": REPO_ROOT / "docs" / "OTY2_GM017_PHYSICAL_FACTOR_CALIBRATION_PROTOCOL.md",
    "report": REPORT_DIR / f"oty2_wgv3_6b_p0_gm017_physical_factor_discovery_{DATE}.md",
    "frozen_params": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_factor_parameters_{DATE}.csv",
    "control_points": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_calibration_control_points_{DATE}.csv",
    "components": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_response_component_observations_{DATE}.csv",
    "background_fit": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_background_stability_fit_{DATE}.csv",
    "manifest": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_manifest_{DATE}.csv",
}

D1_SOURCE = REPO_ROOT / "tools" / "diagnostics" / "run_oty2_wgv3_6b_d1_gm017_recursive_state_generate.py"

OUTPUTS = {
    "runtime_input_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_runtime_input_manifest_{DATE}.csv",
    "frozen_runtime_parameters": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frozen_runtime_parameters_{DATE}.csv",
    "initial_state": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_initial_state_{DATE}.csv",
    "frame_observations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frame_observations_{DATE}.csv",
    "response_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_response_tracks_{DATE}.csv",
    "response_associations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_response_associations_{DATE}.csv",
    "response_state_transitions": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_response_state_transitions_{DATE}.csv",
    "background_tracks": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_background_tracks_{DATE}.csv",
    "background_associations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_background_associations_{DATE}.csv",
    "visibility_events": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_visibility_events_{DATE}.csv",
    "reappearance_candidates": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_reappearance_candidates_{DATE}.csv",
    "reappearance_confirmations": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_reappearance_confirmations_{DATE}.csv",
    "admission_policy_state_history": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_admission_policy_state_history_{DATE}.csv",
    "holdout_predictions_frozen": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_holdout_predictions_frozen_{DATE}.csv",
    "pre_eval_seal": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_pre_eval_seal_{DATE}.csv",
    "visual_review_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_visual_review_manifest_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_gate_integrity_{DATE}.csv",
    "replay_check": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_replay_check_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_d1_r1_gm017_frozen_manifest_{DATE}.csv",
}

CORE_GENERATION_KEYS = [
    "runtime_input_manifest",
    "frozen_runtime_parameters",
    "initial_state",
    "frame_observations",
    "response_tracks",
    "response_associations",
    "response_state_transitions",
    "background_tracks",
    "background_associations",
    "visibility_events",
    "reappearance_candidates",
    "reappearance_confirmations",
    "admission_policy_state_history",
    "holdout_predictions_frozen",
    "visual_review_manifest",
]

POLICIES = [
    "ALL_ASSOCIATED_TRACKS",
    "TEMPORALLY_SUPPORTED_ONLY",
    "STRUCTURE_CONSISTENT_ONLY",
]

STATE_ORDER = {
    "motion_shell_candidate": 1,
    "temporally_supported_response": 2,
    "same_motion_candidate": 3,
    "same_motion_supported": 4,
    "temporarily_missing": 1,
    "reappearance_candidate": 2,
    "reappearance_provisionally_supported": 3,
    "reappeared_supported": 4,
    "terminated": 0,
}


def load_d1_base() -> Any:
    spec = importlib.util.spec_from_file_location("d1_base_helpers", D1_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load D1 helper source: {D1_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


D1_BASE = load_d1_base()


@dataclass
class ResponseTrack:
    track_id: str
    init_frame: int
    last_frame: int
    last_x: float
    last_y: float
    rel_x: float
    rel_y: float
    last_area: float = 0.0
    last_energy: float = 0.0
    last_orientation: float = 0.0
    support_observation_count: int = 1
    support_frame_ids: set[int] = field(default_factory=set)
    current_consecutive_support_frames: int = 1
    current_missing_frames: int = 0
    reappearance_count: int = 0
    terminated_frame: str = ""
    current_evidence_state: str = "motion_shell_candidate"
    highest_evidence_state_reached: str = "motion_shell_candidate"
    pending_reappearance: bool = False
    reappearance_support_frames: int = 0
    last_reliable_state_before_missing: str = "motion_shell_candidate"

    @property
    def support_unique_frame_count(self) -> int:
        return len(self.support_frame_ids)

    def remember_highest(self, state: str) -> None:
        if STATE_ORDER.get(state, 0) > STATE_ORDER.get(self.highest_evidence_state_reached, 0):
            self.highest_evidence_state_reached = state


@dataclass
class BackgroundTrack:
    track_id: str
    first_frame: int
    last_frame: int
    xs: list[float] = field(default_factory=list)
    ys: list[float] = field(default_factory=list)
    areas: list[float] = field(default_factory=list)
    energies: list[float] = field(default_factory=list)
    component_by_frame: dict[int, str] = field(default_factory=dict)
    missing_frames: int = 0
    conflict_frames: set[int] = field(default_factory=set)

    @property
    def mean_x(self) -> float:
        return float(np.mean(self.xs)) if self.xs else 0.0

    @property
    def mean_y(self) -> float:
        return float(np.mean(self.ys)) if self.ys else 0.0

    @property
    def variance(self) -> float:
        if len(self.component_by_frame) < 2:
            return 999999.0
        return float(np.var(self.xs) + np.var(self.ys))

    @property
    def support_observation_count(self) -> int:
        return len(self.xs)

    @property
    def support_unique_frame_count(self) -> int:
        return len(self.component_by_frame)

    @property
    def support_frame_ids(self) -> str:
        return ";".join(str(frame) for frame in sorted(self.component_by_frame))


@dataclass
class PolicyState:
    position_x: float
    position_y: float
    velocity_x: float
    velocity_y: float
    position_uncertainty: float
    velocity_uncertainty: float


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
    return len(read_csv(path))


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


def parse_pair(text: str) -> tuple[float, float]:
    x, y = text.split(",", 1)
    return parse_float(x), parse_float(y)


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


def p0_params() -> dict[str, str]:
    return {row["parameter_name"]: row["parameter_value"] for row in read_csv(P0["frozen_params"])}


def derive_runtime_parameter_rows() -> list[dict[str, Any]]:
    params = p0_params()
    same_motion = parse_float(params["same_motion_tolerance_px"])
    static_var = parse_float(params["static_position_variance_threshold_px2"])
    rows = [
        ("constant_width_px", params["constant_width_px"], "P0 frozen scale parameter reused only for ROI size"),
        ("constant_height_px", params["constant_height_px"], "P0 frozen scale parameter reused only for ROI size"),
        ("x_intercept", params["x_intercept"], "P0 absolute-frame linear baseline only"),
        ("x_slope", params["x_slope"], "P0 absolute-frame linear baseline only"),
        ("y_intercept", params["y_intercept"], "P0 absolute-frame linear baseline only"),
        ("y_slope", params["y_slope"], "P0 absolute-frame linear baseline only"),
        ("same_motion_tolerance_px", params["same_motion_tolerance_px"], "P0 loose motion-shell tolerance; not proof"),
        ("response_prediction_tolerance_px", fmt(max(32.0, same_motion + 12.0)), "D1-R1 runtime constant before diagnosis-window evaluation"),
        ("motion_consistency_tolerance_px", fmt(max(34.0, same_motion + 14.0)), "D1-R1 runtime constant before diagnosis-window evaluation"),
        ("relative_structure_tolerance_px", fmt(same_motion), "P0 same-motion tolerance reused as strict relative-structure gate"),
        ("background_match_tolerance_px", "10.0", "Conservative fixed-coordinate background association radius"),
        ("background_conflict_tolerance_px", "12.0", "Conservative response/background conflict radius"),
        ("static_position_variance_threshold_px2", fmt(static_var), "P0 background variance threshold reused as audit reference"),
        ("background_recurrence_min_unique_frames", "2", "Two different SAR frames only support recurrence"),
        ("static_background_candidate_min_unique_frames", "3", "Static candidate requires at least three unique frames"),
        ("static_background_supported_min_unique_frames", "5", "Supported static background requires longer unique-frame support"),
        ("temporal_support_min_unique_frames", "2", "Temporal support requires more than one SAR frame"),
        ("same_motion_min_consecutive_frames", "3", "Same-motion support requires three current consecutive support frames"),
        ("reappearance_provisional_support_frames", "2", "First post-missing hit cannot become supported in the same frame"),
        ("reappearance_confirm_support_frames", "3", "Confirmed reappearance requires consecutive post-hit support"),
        ("allowed_missing_gap_frames", "8", "D1-R1 track-specific termination gap"),
        ("target_gain_all_base", "0.24", "A policy gain fixed before evaluation"),
        ("target_gain_temporal_base", "0.20", "B policy gain fixed before evaluation"),
        ("target_gain_structure_base", "0.16", "C policy gain fixed before evaluation"),
        ("target_gain_per_track", "0.02", "Small per-track gain increment fixed before evaluation"),
        ("target_gain_max", "0.45", "Maximum correction gain fixed before evaluation"),
    ]
    return [
        {
            "parameter_name": name,
            "parameter_value": value,
            "source": source,
            "frozen_before_eval": "true",
            "gt_tuned": "false",
        }
        for name, value, source in rows
    ]


def write_runtime_parameters(path: Path) -> dict[str, str]:
    rows = derive_runtime_parameter_rows()
    write_csv(path, rows, RUNTIME_PARAMETER_FIELDS)
    return {row["parameter_name"]: row["parameter_value"] for row in rows}


def initial_state_and_tracks(params: Mapping[str, str]) -> tuple[PolicyState, list[ResponseTrack], list[dict[str, Any]]]:
    control_rows = sorted(read_csv(P0["control_points"]), key=lambda row: parse_int(row["sar_frame"]))
    last = control_rows[-1]
    prev = control_rows[-2]
    x, y = parse_pair(last["bbox_center"])
    prev_x, prev_y = parse_pair(prev["bbox_center"])
    pos_unc = max(30.0, parse_float(params["same_motion_tolerance_px"]) * 1.5)
    vel_unc = max(6.0, math.hypot(x - prev_x, y - prev_y) * 0.25)
    state = PolicyState(x, y, x - prev_x, y - prev_y, pos_unc, vel_unc)

    supported_ids = {item for item in last["manually_supported_vehicle_response_ids"].split(";") if item}
    component_rows = read_csv(P0["components"])
    tracks: list[ResponseTrack] = []
    transition_rows: list[dict[str, Any]] = []
    idx = 1
    for row in component_rows:
        if row["component_id"] not in supported_ids:
            continue
        cx = parse_float(row["centroid_x"])
        cy = parse_float(row["centroid_y"])
        track = ResponseTrack(
            track_id=f"RT_D1_R1_{idx:04d}",
            init_frame=CALIBRATION_END,
            last_frame=CALIBRATION_END,
            last_x=cx,
            last_y=cy,
            rel_x=cx - x,
            rel_y=cy - y,
            last_area=parse_float(row["pixel_area"]),
            last_energy=parse_float(row["integrated_energy"]),
            last_orientation=parse_float(row["orientation_deg"]),
            support_frame_ids={CALIBRATION_END},
        )
        tracks.append(track)
        transition_rows.append(
            transition_row(
                CALIBRATION_END,
                track,
                "",
                track.current_evidence_state,
                "initialized_from_p0_state_360_supported_response_component",
            )
        )
        idx += 1
    return state, tracks, transition_rows


def background_state(track: BackgroundTrack, params: Mapping[str, str]) -> str:
    unique_count = track.support_unique_frame_count
    variance = track.variance
    static_var = parse_float(params["static_position_variance_threshold_px2"])
    if unique_count >= parse_int(params["static_background_supported_min_unique_frames"]) and variance <= static_var and not track.conflict_frames:
        return "static_background_supported"
    if unique_count >= parse_int(params["static_background_candidate_min_unique_frames"]) and variance <= static_var:
        return "static_background_candidate"
    if unique_count >= parse_int(params["background_recurrence_min_unique_frames"]):
        return "background_recurrence_candidate"
    return "unresolved_response"


def background_conflict(
    x: float,
    y: float,
    tracks: Sequence[BackgroundTrack],
    params: Mapping[str, str],
) -> tuple[bool, str]:
    radius = parse_float(params["background_conflict_tolerance_px"])
    for track in tracks:
        if background_state(track, params) not in {"static_background_candidate", "static_background_supported"}:
            continue
        if math.hypot(x - track.mean_x, y - track.mean_y) <= radius:
            return True, track.track_id
    return False, ""


def should_enter_background(
    comp: Mapping[str, Any],
    used_component_ids: set[str],
    predicted_target: tuple[float, float],
    shell_radius: float,
) -> bool:
    comp_id = str(comp["component_id"])
    if comp_id in used_component_ids:
        return False
    cx = parse_float(comp["centroid_x"])
    cy = parse_float(comp["centroid_y"])
    target_dist = math.hypot(cx - predicted_target[0], cy - predicted_target[1])
    aspect = parse_float(comp["aspect_ratio"], 1.0)
    return target_dist > shell_radius or aspect >= 4.0


def update_background_tracks(
    frame: int,
    components: Sequence[Mapping[str, Any]],
    used_component_ids: set[str],
    tracks: list[BackgroundTrack],
    predicted_target: tuple[float, float],
    shell_radius: float,
    params: Mapping[str, str],
    vehicle_component_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    for track in tracks:
        track.missing_frames += 1

    match_radius = parse_float(params["background_match_tolerance_px"])
    candidate_pairs: list[tuple[float, BackgroundTrack, Mapping[str, Any]]] = []
    new_components: list[Mapping[str, Any]] = []
    for comp in components:
        if not should_enter_background(comp, used_component_ids, predicted_target, shell_radius):
            continue
        cx = parse_float(comp["centroid_x"])
        cy = parse_float(comp["centroid_y"])
        best_pairs = []
        for track in tracks:
            if track.missing_frames > 4 or frame in track.component_by_frame:
                continue
            distance = math.hypot(cx - track.mean_x, cy - track.mean_y)
            if distance <= match_radius:
                best_pairs.append((distance, track, comp))
        if best_pairs:
            candidate_pairs.append(min(best_pairs, key=lambda item: item[0]))
        else:
            new_components.append(comp)

    rows: list[dict[str, Any]] = []
    semantic_by_component: dict[str, str] = {}
    assigned_tracks: set[str] = set()
    assigned_components: set[str] = set()
    for distance, track, comp in sorted(candidate_pairs, key=lambda item: item[0]):
        comp_id = str(comp["component_id"])
        if track.track_id in assigned_tracks or comp_id in assigned_components:
            continue
        rows.append(assign_background(frame, track, comp, distance, params, vehicle_component_ids))
        semantic_by_component[comp_id] = background_state(track, params)
        assigned_tracks.add(track.track_id)
        assigned_components.add(comp_id)

    for comp in new_components:
        comp_id = str(comp["component_id"])
        if comp_id in assigned_components:
            continue
        track = BackgroundTrack(track_id=f"BG_D1_R1_{len(tracks) + 1:04d}", first_frame=frame, last_frame=frame)
        tracks.append(track)
        rows.append(assign_background(frame, track, comp, 0.0, params, vehicle_component_ids, new_track=True))
        semantic_by_component[comp_id] = background_state(track, params)
        assigned_components.add(comp_id)

    return rows, semantic_by_component


def assign_background(
    frame: int,
    track: BackgroundTrack,
    comp: Mapping[str, Any],
    distance: float,
    params: Mapping[str, str],
    vehicle_component_ids: set[str],
    *,
    new_track: bool = False,
) -> dict[str, Any]:
    comp_id = str(comp["component_id"])
    cx = parse_float(comp["centroid_x"])
    cy = parse_float(comp["centroid_y"])
    conflict = comp_id in vehicle_component_ids
    if conflict:
        track.conflict_frames.add(frame)
    track.last_frame = frame
    track.component_by_frame[frame] = comp_id
    track.xs.append(cx)
    track.ys.append(cy)
    track.areas.append(parse_float(comp["pixel_area"]))
    track.energies.append(parse_float(comp["integrated_energy"]))
    track.missing_frames = 0
    return {
        "background_association_id": f"BGASSOC_{frame:06d}_{track.track_id}",
        "sar_frame": frame,
        "background_track_id": track.track_id,
        "component_id": comp_id,
        "association_result": "new_track" if new_track else "matched_existing_track",
        "match_distance_px": fmt(distance),
        "support_observation_count_after": track.support_observation_count,
        "support_unique_frame_count_after": track.support_unique_frame_count,
        "track_component_count_this_frame": 1,
        "component_track_count_this_frame": 1,
        "background_state_after": background_state(track, params),
        "vehicle_motion_conflict": "true" if conflict else "false",
        "conflict_reason": "component_already_used_by_response_track" if conflict else "",
    }


def association_candidates(
    track: ResponseTrack,
    components: Sequence[Mapping[str, Any]],
    used_components: set[str],
    predicted_target: tuple[float, float],
    prior_target: tuple[float, float],
    uncertainty: float,
    background_tracks: Sequence[BackgroundTrack],
    params: Mapping[str, str],
) -> tuple[Mapping[str, Any] | None, dict[str, Any], list[dict[str, Any]]]:
    prior_rel_x = track.rel_x
    prior_rel_y = track.rel_y
    prior_pred_x = predicted_target[0] + prior_rel_x
    prior_pred_y = predicted_target[1] + prior_rel_y
    target_dx = predicted_target[0] - prior_target[0]
    target_dy = predicted_target[1] - prior_target[1]
    response_tol = max(parse_float(params["response_prediction_tolerance_px"]), min(70.0, uncertainty + 18.0))
    motion_tol = max(parse_float(params["motion_consistency_tolerance_px"]), min(74.0, uncertainty + 22.0))
    relative_tol = parse_float(params["relative_structure_tolerance_px"])
    temporal_min = parse_int(params["temporal_support_min_unique_frames"])

    selected: Mapping[str, Any] | None = None
    selected_detail: dict[str, Any] = {}
    selected_residual = 999999.0
    candidates: list[dict[str, Any]] = []
    for comp in components:
        comp_id = str(comp["component_id"])
        if comp_id in used_components:
            continue
        cx = parse_float(comp["centroid_x"])
        cy = parse_float(comp["centroid_y"])
        response_residual = math.hypot(cx - prior_pred_x, cy - prior_pred_y)
        motion_residual = math.hypot((cx - track.last_x) - target_dx, (cy - track.last_y) - target_dy)
        relative_x = cx - predicted_target[0]
        relative_y = cy - predicted_target[1]
        relative_residual = math.hypot(relative_x - prior_rel_x, relative_y - prior_rel_y)
        bg_conflict, bg_id = background_conflict(cx, cy, background_tracks, params)
        gate_response = response_residual <= response_tol
        gate_motion = motion_residual <= motion_tol
        gate_relative = relative_residual <= relative_tol
        gate_background = not bg_conflict
        gate_temporal = track.support_unique_frame_count >= temporal_min
        near_enough_to_audit = gate_response or gate_motion or response_residual <= response_tol * 1.8 or relative_residual <= relative_tol * 2.0
        if not near_enough_to_audit:
            continue
        failed = []
        if not gate_response:
            failed.append("response_prediction")
        if not gate_motion:
            failed.append("motion_consistency")
        if not gate_relative:
            failed.append("relative_structure")
        if not gate_background:
            failed.append("background_conflict")
        detail = {
            "component_id": comp_id,
            "previous_response_x": track.last_x,
            "previous_response_y": track.last_y,
            "prior_track_relative_x": prior_rel_x,
            "prior_track_relative_y": prior_rel_y,
            "prior_predicted_response_x": prior_pred_x,
            "prior_predicted_response_y": prior_pred_y,
            "observed_response_x": cx,
            "observed_response_y": cy,
            "target_displacement_x": target_dx,
            "target_displacement_y": target_dy,
            "response_self_displacement_x": cx - track.last_x,
            "response_self_displacement_y": cy - track.last_y,
            "observed_relative_to_target_x": relative_x,
            "observed_relative_to_target_y": relative_y,
            "response_prediction_residual_px": response_residual,
            "motion_residual_px": motion_residual,
            "relative_position_residual_px": relative_residual,
            "shape_change_px": abs(parse_float(comp["pixel_area"]) - track.last_area),
            "orientation_change_deg": abs(parse_float(comp["orientation_deg"]) - track.last_orientation),
            "energy_change": parse_float(comp["integrated_energy"]) - track.last_energy,
            "background_conflict": "true" if bg_conflict else "false",
            "background_track_id": bg_id,
            "gate_response_prediction": "PASS" if gate_response else "FAIL",
            "gate_motion_consistency": "PASS" if gate_motion else "FAIL",
            "gate_relative_structure": "PASS" if gate_relative else "FAIL",
            "gate_background_conflict": "PASS" if gate_background else "FAIL",
            "gate_temporal_support": "PASS" if gate_temporal else "FAIL",
            "rejection_reason": ";".join(failed),
        }
        candidates.append(detail)
        if gate_response and gate_motion and gate_relative and gate_background and response_residual < selected_residual:
            selected = comp
            selected_detail = detail
            selected_residual = response_residual
    return selected, selected_detail, candidates


def classify_reappearance_gap(missing_frames: int) -> str:
    if missing_frames <= 1:
        return "one_frame_reassociation"
    if missing_frames <= 4:
        return "short_gap_reappearance"
    return "long_gap_reappearance"


def update_track_state_after_hit(
    track: ResponseTrack,
    frame: int,
    was_missing: bool,
    missing_before: int,
    detail: Mapping[str, Any],
    params: Mapping[str, str],
) -> tuple[str, str]:
    previous = track.current_evidence_state
    temporal_min = parse_int(params["temporal_support_min_unique_frames"])
    same_motion_min = parse_int(params["same_motion_min_consecutive_frames"])
    provisional_min = parse_int(params["reappearance_provisional_support_frames"])
    confirm_min = parse_int(params["reappearance_confirm_support_frames"])
    all_gates_pass = all(
        detail.get(gate_name) == "PASS"
        for gate_name in [
            "gate_response_prediction",
            "gate_motion_consistency",
            "gate_relative_structure",
            "gate_background_conflict",
        ]
    )

    if was_missing:
        track.reappearance_count += 1
        track.pending_reappearance = True
        track.reappearance_support_frames = 1
        new_state = "reappearance_candidate"
        reason = f"first_hit_after_missing_gap={missing_before};not_auto_supported"
    elif track.pending_reappearance:
        track.reappearance_support_frames += 1
        if track.reappearance_support_frames >= confirm_min and all_gates_pass:
            new_state = "reappeared_supported"
            track.pending_reappearance = False
            reason = "confirmed_reappearance_after_consecutive_support"
        elif track.reappearance_support_frames >= provisional_min and all_gates_pass:
            new_state = "reappearance_provisionally_supported"
            reason = "provisional_reappearance_after_later_support"
        else:
            new_state = "reappearance_candidate"
            reason = "pending_reappearance_confirmation"
    elif (
        track.support_unique_frame_count >= temporal_min
        and track.current_consecutive_support_frames >= same_motion_min
        and all_gates_pass
        and detail.get("gate_temporal_support") == "PASS"
    ):
        new_state = "same_motion_supported"
        reason = "unique_frames_consecutive_support_and_all_structure_gates_pass"
    elif track.support_unique_frame_count >= temporal_min and all_gates_pass:
        new_state = "same_motion_candidate"
        reason = "temporal_and_structure_supported_but_consecutive_support_not_yet_confirmed"
    elif track.support_unique_frame_count >= temporal_min:
        new_state = "temporally_supported_response"
        reason = "multi_frame_support_without_full_structure_confirmation"
    else:
        new_state = "motion_shell_candidate"
        reason = "single_frame_or_low_support_motion_shell_candidate"

    track.current_evidence_state = new_state
    track.remember_highest(new_state)
    return previous, reason


def policy_allows(policy: str, track: ResponseTrack, assoc: Mapping[str, Any]) -> tuple[bool, str]:
    state = track.current_evidence_state
    if policy == "ALL_ASSOCIATED_TRACKS":
        return True, ""
    if policy == "TEMPORALLY_SUPPORTED_ONLY":
        if state in {
            "temporally_supported_response",
            "same_motion_candidate",
            "same_motion_supported",
            "reappearance_provisionally_supported",
            "reappeared_supported",
        }:
            return True, ""
        return False, f"{track.track_id}:state={state}"
    if policy == "STRUCTURE_CONSISTENT_ONLY":
        gates_ok = all(
            assoc.get(name) == "PASS"
            for name in [
                "gate_response_prediction",
                "gate_motion_consistency",
                "gate_relative_structure",
                "gate_background_conflict",
                "gate_temporal_support",
            ]
        )
        if state in {"same_motion_supported", "reappeared_supported"} and gates_ok:
            return True, ""
        reasons = []
        if state not in {"same_motion_supported", "reappeared_supported"}:
            reasons.append(f"state={state}")
        if not gates_ok:
            reasons.append("strict_gate_fail")
        return False, f"{track.track_id}:{'+'.join(reasons)}"
    raise ValueError(policy)


def run_generation(output_map: Mapping[str, Path], visual_dir: Path) -> None:
    ensure_dirs()
    params = write_runtime_parameters(output_map["frozen_runtime_parameters"])
    const_width = parse_float(params["constant_width_px"])
    const_height = parse_float(params["constant_height_px"])
    motion_shell = parse_float(params["same_motion_tolerance_px"])
    p0_xi = parse_float(params["x_intercept"])
    p0_xs = parse_float(params["x_slope"])
    p0_yi = parse_float(params["y_intercept"])
    p0_ys = parse_float(params["y_slope"])

    init_state, response_tracks, transition_rows = initial_state_and_tracks(params)
    policy_states = {
        policy: PolicyState(
            init_state.position_x,
            init_state.position_y,
            init_state.velocity_x,
            init_state.velocity_y,
            init_state.position_uncertainty,
            init_state.velocity_uncertainty,
        )
        for policy in POLICIES
    }
    primary_state = policy_states["ALL_ASSOCIATED_TRACKS"]
    noobs_x = init_state.position_x
    noobs_y = init_state.position_y
    noobs_vx = init_state.velocity_x
    noobs_vy = init_state.velocity_y
    static_x = init_state.position_x
    static_y = init_state.position_y

    initial_state_rows = [
        {
            "sar_frame": CALIBRATION_END,
            "position_x": fmt(init_state.position_x),
            "position_y": fmt(init_state.position_y),
            "velocity_x": fmt(init_state.velocity_x),
            "velocity_y": fmt(init_state.velocity_y),
            "position_uncertainty": fmt(init_state.position_uncertainty),
            "velocity_uncertainty": fmt(init_state.velocity_uncertainty),
            "response_track_count": len(response_tracks),
            "initialization_source": rel(P0["control_points"]),
            "p0_reinterpretation": "state_360_initialization_only;p0_absolute_linear_is_baseline_only",
        }
    ]

    frame_rows: list[dict[str, Any]] = []
    association_rows: list[dict[str, Any]] = []
    background_tracks: list[BackgroundTrack] = []
    background_assoc_rows: list[dict[str, Any]] = []
    visibility_rows: list[dict[str, Any]] = []
    reappearance_candidate_rows: list[dict[str, Any]] = []
    reappearance_confirmation_rows: list[dict[str, Any]] = []
    policy_state_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    visual_paths: dict[int, Path] = {}
    visual_context: dict[int, dict[str, Any]] = {}
    assoc_counter = 1
    next_track_idx = len(response_tracks) + 1

    for frame in range(GENERATE_START, DIAGNOSIS_END + 1):
        prior_primary_x = primary_state.position_x
        prior_primary_y = primary_state.position_y
        prior_primary_vx = primary_state.velocity_x
        prior_primary_vy = primary_state.velocity_y
        pred_primary_x = prior_primary_x + prior_primary_vx
        pred_primary_y = prior_primary_y + prior_primary_vy
        uncertainty_before = primary_state.position_uncertainty + primary_state.velocity_uncertainty + 3.0
        roi = clamp_roi(
            box_from_center(
                pred_primary_x,
                pred_primary_y,
                const_width + 2.0 * uncertainty_before,
                const_height + 2.0 * uncertainty_before,
            ),
            margin=45.0,
        )
        comps, meta = D1_BASE.extract_components(frame, roi)
        for cidx, comp in enumerate(comps, 1):
            comp["component_id"] = f"D1R1OBS_{frame:06d}_{cidx:04d}"

        used_components: set[str] = set()
        selected_assocs: list[dict[str, Any]] = []
        rejected_tracks: list[str] = []
        selected_track_ids: set[str] = set()
        relative_reject_count = 0
        gate_failure_counts: Counter[str] = Counter()

        if meta["cap_triggered"] != "true":
            for track in list(response_tracks):
                if track.terminated_frame:
                    continue
                prev_state = track.current_evidence_state
                previous_response_x = track.last_x
                previous_response_y = track.last_y
                previous_area = track.last_area
                previous_energy = track.last_energy
                previous_orientation = track.last_orientation
                missing_before = track.current_missing_frames
                selected, detail, candidates = association_candidates(
                    track,
                    comps,
                    used_components,
                    (pred_primary_x, pred_primary_y),
                    (prior_primary_x, prior_primary_y),
                    uncertainty_before,
                    background_tracks,
                    params,
                )
                selected_component_id = str(selected["component_id"]) if selected is not None else ""
                for candidate in candidates:
                    if candidate["component_id"] == selected_component_id:
                        continue
                    if candidate.get("gate_relative_structure") == "FAIL":
                        relative_reject_count += 1
                    for gate_name in [
                        "gate_response_prediction",
                        "gate_motion_consistency",
                        "gate_relative_structure",
                        "gate_background_conflict",
                        "gate_temporal_support",
                    ]:
                        if candidate.get(gate_name) == "FAIL":
                            gate_failure_counts[gate_name] += 1
                    association_rows.append(
                        association_row(
                            assoc_counter,
                            frame,
                            track,
                            candidate,
                            "rejected",
                            track.current_evidence_state,
                            previous_response_x,
                            previous_response_y,
                            previous_area,
                            previous_energy,
                            previous_orientation,
                        )
                    )
                    assoc_counter += 1

                if selected is None:
                    track.current_missing_frames += 1
                    track.current_consecutive_support_frames = 0
                    if track.current_evidence_state not in {"temporarily_missing", "terminated"}:
                        track.last_reliable_state_before_missing = track.current_evidence_state
                    if track.current_missing_frames > parse_int(params["allowed_missing_gap_frames"]):
                        new_state = "terminated"
                        track.terminated_frame = str(frame)
                    else:
                        new_state = "temporarily_missing"
                    track.current_evidence_state = new_state
                    visibility_rows.append(
                        {
                            "event_id": f"VIS_D1_R1_{frame:06d}_{track.track_id}",
                            "sar_frame": frame,
                            "response_track_id": track.track_id,
                            "visibility_state": new_state,
                            "missing_frames": track.current_missing_frames,
                            "last_reliable_state_before_missing": track.last_reliable_state_before_missing,
                            "position_uncertainty": fmt(uncertainty_before),
                            "reason": "no_current_component_passed_response_motion_relative_and_background_gates",
                        }
                    )
                    if prev_state != new_state:
                        transition_rows.append(transition_row(frame, track, prev_state, new_state, "track_missing_or_terminated"))
                    rejected_tracks.append(track.track_id)
                    continue

                comp_id = selected_component_id
                used_components.add(comp_id)
                selected_track_ids.add(track.track_id)
                was_missing = track.current_missing_frames > 0
                cx = parse_float(selected["centroid_x"])
                cy = parse_float(selected["centroid_y"])
                track.support_observation_count += 1
                track.support_frame_ids.add(frame)
                track.current_consecutive_support_frames = 1 if was_missing else track.current_consecutive_support_frames + 1
                track.last_frame = frame
                track.last_x = cx
                track.last_y = cy
                track.last_area = parse_float(selected["pixel_area"])
                track.last_energy = parse_float(selected["integrated_energy"])
                track.last_orientation = parse_float(selected["orientation_deg"])
                track.current_missing_frames = 0
                previous_state, reason = update_track_state_after_hit(track, frame, was_missing, missing_before, detail, params)
                posterior_rel_x = 0.82 * detail["prior_track_relative_x"] + 0.18 * (cx - pred_primary_x)
                posterior_rel_y = 0.82 * detail["prior_track_relative_y"] + 0.18 * (cy - pred_primary_y)
                detail = dict(detail)
                detail["posterior_track_relative_x"] = posterior_rel_x
                detail["posterior_track_relative_y"] = posterior_rel_y
                detail["target_position_from_response_x"] = cx - detail["prior_track_relative_x"]
                detail["target_position_from_response_y"] = cy - detail["prior_track_relative_y"]
                selected_row = association_row(
                    assoc_counter,
                    frame,
                    track,
                    detail,
                    "selected",
                    track.current_evidence_state,
                    previous_response_x,
                    previous_response_y,
                    previous_area,
                    previous_energy,
                    previous_orientation,
                )
                association_rows.append(selected_row)
                selected_assocs.append(selected_row)
                assoc_counter += 1
                if previous_state != track.current_evidence_state:
                    transition_rows.append(transition_row(frame, track, previous_state, track.current_evidence_state, reason))
                if was_missing:
                    reappearance_candidate_rows.append(
                        {
                            "event_id": f"REAPP_CAND_{frame:06d}_{track.track_id}",
                            "sar_frame": frame,
                            "response_track_id": track.track_id,
                            "gap_class": classify_reappearance_gap(missing_before),
                            "missing_frames_before": missing_before,
                            "last_reliable_state_before_missing": track.last_reliable_state_before_missing,
                            "prior_predicted_response_x": fmt(detail["prior_predicted_response_x"]),
                            "prior_predicted_response_y": fmt(detail["prior_predicted_response_y"]),
                            "first_reassociated_response_x": fmt(cx),
                            "first_reassociated_response_y": fmt(cy),
                            "relative_structure_residual_px": fmt(detail["relative_position_residual_px"]),
                            "background_conflict": detail["background_conflict"],
                            "final_confirmation_state": "candidate_only_at_first_hit",
                        }
                    )
                if track.current_evidence_state in {"reappearance_provisionally_supported", "reappeared_supported"}:
                    reappearance_confirmation_rows.append(
                        {
                            "event_id": f"REAPP_CONF_{frame:06d}_{track.track_id}",
                            "sar_frame": frame,
                            "response_track_id": track.track_id,
                            "confirmation_state": track.current_evidence_state,
                            "post_reappearance_support_frames": track.reappearance_support_frames,
                            "relative_structure_residual_px": fmt(detail["relative_position_residual_px"]),
                            "background_conflict": detail["background_conflict"],
                            "confirmed": "true" if track.current_evidence_state == "reappeared_supported" else "false",
                        }
                    )
                track.rel_x = posterior_rel_x
                track.rel_y = posterior_rel_y

            for comp in comps:
                comp_id = str(comp["component_id"])
                if comp_id in used_components:
                    continue
                cx = parse_float(comp["centroid_x"])
                cy = parse_float(comp["centroid_y"])
                dist_to_target = math.hypot(cx - pred_primary_x, cy - pred_primary_y)
                bg_conf, _ = background_conflict(cx, cy, background_tracks, params)
                if dist_to_target <= max(motion_shell, uncertainty_before + 15.0) and not bg_conf:
                    track = ResponseTrack(
                        track_id=f"RT_D1_R1_{next_track_idx:04d}",
                        init_frame=frame,
                        last_frame=frame,
                        last_x=cx,
                        last_y=cy,
                        rel_x=cx - pred_primary_x,
                        rel_y=cy - pred_primary_y,
                        last_area=parse_float(comp["pixel_area"]),
                        last_energy=parse_float(comp["integrated_energy"]),
                        last_orientation=parse_float(comp["orientation_deg"]),
                        support_frame_ids={frame},
                    )
                    response_tracks.append(track)
                    transition_rows.append(transition_row(frame, track, "", track.current_evidence_state, "new_motion_shell_candidate_created"))
                    used_components.add(comp_id)
                    next_track_idx += 1

        bg_rows, background_semantic = update_background_tracks(
            frame,
            comps,
            used_components,
            background_tracks,
            (pred_primary_x, pred_primary_y),
            max(70.0, uncertainty_before + motion_shell),
            params,
            {row["component_id"] for row in selected_assocs},
        )
        background_assoc_rows.extend(bg_rows)

        semantic_by_component = {row["component_id"]: row["current_evidence_state"] for row in selected_assocs}
        for comp in comps:
            comp_id = str(comp["component_id"])
            if meta["cap_triggered"] == "true":
                semantic = "incomplete_observation"
            elif comp_id in semantic_by_component:
                semantic = semantic_by_component[comp_id]
            elif comp_id in used_components:
                semantic = "motion_shell_candidate"
            elif comp_id in background_semantic:
                semantic = background_semantic[comp_id]
            else:
                semantic = "unresolved_response"
            frame_rows.append(component_row(comp_id, frame, comp, meta, semantic))

        policy_centers: dict[str, tuple[float, float]] = {}
        policy_corrections: dict[str, float] = {}
        for policy in POLICIES:
            state = policy_states[policy]
            prior_x = state.position_x
            prior_y = state.position_y
            prior_vx = state.velocity_x
            prior_vy = state.velocity_y
            pred_x = prior_x + prior_vx
            pred_y = prior_y + prior_vy
            eligible: list[dict[str, Any]] = []
            excluded: list[str] = []
            for assoc in selected_assocs:
                track = next(track for track in response_tracks if track.track_id == assoc["response_track_id"])
                ok, reason = policy_allows(policy, track, assoc)
                if ok:
                    eligible.append(assoc)
                elif reason:
                    excluded.append(reason)
            if eligible:
                obs_x = float(np.mean([parse_float(row["target_position_from_response_x"]) for row in eligible]))
                obs_y = float(np.mean([parse_float(row["target_position_from_response_y"]) for row in eligible]))
                corr_x = obs_x - pred_x
                corr_y = obs_y - pred_y
                if policy == "ALL_ASSOCIATED_TRACKS":
                    gain = parse_float(params["target_gain_all_base"])
                elif policy == "TEMPORALLY_SUPPORTED_ONLY":
                    gain = parse_float(params["target_gain_temporal_base"])
                else:
                    gain = parse_float(params["target_gain_structure_base"])
                gain = min(parse_float(params["target_gain_max"]), gain + parse_float(params["target_gain_per_track"]) * len(eligible))
                post_x = pred_x + gain * corr_x
                post_y = pred_y + gain * corr_y
                post_vx = 0.72 * prior_vx + 0.28 * (post_x - prior_x)
                post_vy = 0.72 * prior_vy + 0.28 * (post_y - prior_y)
                uncertainty_after = max(14.0, state.position_uncertainty * 0.72 + state.velocity_uncertainty * 0.25)
                source = "current_sar_observation_admitted_response_tracks"
                fallback = "false"
            else:
                obs_x = obs_y = ""
                corr_x = corr_y = 0.0
                post_x = pred_x
                post_y = pred_y
                post_vx = prior_vx
                post_vy = prior_vy
                uncertainty_after = min(180.0, state.position_uncertainty + state.velocity_uncertainty + 7.5)
                source = "prediction_only_no_admissible_tracks"
                fallback = "true"
            state.position_x = post_x
            state.position_y = post_y
            state.velocity_x = post_vx
            state.velocity_y = post_vy
            state.position_uncertainty = uncertainty_after
            state.velocity_uncertainty = max(4.0, state.velocity_uncertainty * 0.9)
            policy_centers[policy] = (post_x, post_y)
            policy_corrections[policy] = math.hypot(post_x - pred_x, post_y - pred_y)
            policy_state_rows.append(
                {
                    "sar_frame": frame,
                    "segment": segment_for_frame(frame),
                    "admission_policy": policy,
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
                    "eligible_track_ids": ";".join(row["response_track_id"] for row in eligible),
                    "excluded_track_ids": ";".join(item.split(":", 1)[0] for item in excluded),
                    "exclusion_reasons": ";".join(excluded),
                    "observation_supported_position": f"{fmt(obs_x)},{fmt(obs_y)}" if eligible else "",
                    "posterior_correction": fmt(math.hypot(post_x - pred_x, post_y - pred_y)),
                    "current_response_association_count": len(selected_assocs),
                    "eligible_track_count": len(eligible),
                    "no_observation_fallback": fallback,
                    "last_update_source": source,
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
                policy_states,
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
            )
        )

        visual_paths[frame] = render_frame_visual(
            frame,
            roi,
            (pred_primary_x, pred_primary_y),
            policy_centers,
            comps,
            selected_assocs,
            [row for row in association_rows if parse_int(row["sar_frame"]) == frame and row["association_result"] == "rejected"],
            background_tracks,
            visual_dir,
        )
        visual_context[frame] = {
            "selected_count": len(selected_assocs),
            "relative_reject_count": relative_reject_count,
            "missing_count": len([row for row in visibility_rows if parse_int(row["sar_frame"]) == frame]),
            "reappearance_candidate_count": len([row for row in reappearance_candidate_rows if parse_int(row["sar_frame"]) == frame]),
            "reappearance_confirm_count": len([row for row in reappearance_confirmation_rows if parse_int(row["sar_frame"]) == frame]),
            "background_association_count": len(bg_rows),
            "background_conflict_count": len([row for row in bg_rows if row["vehicle_motion_conflict"] == "true"]),
            "policy_divergence_px": policy_divergence(policy_centers),
            "max_policy_correction_px": max(policy_corrections.values()) if policy_corrections else 0.0,
            "gate_failure_summary": ";".join(f"{key}={value}" for key, value in sorted(gate_failure_counts.items())),
        }

        noobs_x += noobs_vx
        noobs_y += noobs_vy
        primary_state = policy_states["ALL_ASSOCIATED_TRACKS"]

    contact_sheet = render_contact_sheet(visual_paths, visual_dir)
    visual_rows = build_visual_review_manifest(visual_paths, contact_sheet, visual_context)

    write_csv(output_map["runtime_input_manifest"], build_runtime_input_manifest(), RUNTIME_INPUT_FIELDS)
    write_csv(output_map["initial_state"], initial_state_rows, INITIAL_STATE_FIELDS)
    write_csv(output_map["frame_observations"], frame_rows, FRAME_OBSERVATION_FIELDS)
    write_csv(output_map["response_tracks"], response_track_rows(response_tracks), RESPONSE_TRACK_FIELDS)
    write_csv(output_map["response_associations"], association_rows, RESPONSE_ASSOC_FIELDS)
    write_csv(output_map["response_state_transitions"], transition_rows, RESPONSE_TRANSITION_FIELDS)
    write_csv(output_map["background_tracks"], background_track_rows(background_tracks, params), BACKGROUND_TRACK_FIELDS)
    write_csv(output_map["background_associations"], background_assoc_rows, BACKGROUND_ASSOC_FIELDS)
    write_csv(output_map["visibility_events"], visibility_rows, VISIBILITY_FIELDS)
    write_csv(output_map["reappearance_candidates"], reappearance_candidate_rows, REAPPEARANCE_CANDIDATE_FIELDS)
    write_csv(output_map["reappearance_confirmations"], reappearance_confirmation_rows, REAPPEARANCE_CONFIRMATION_FIELDS)
    write_csv(output_map["admission_policy_state_history"], policy_state_rows, ADMISSION_STATE_FIELDS)
    write_csv(output_map["holdout_predictions_frozen"], prediction_rows, PREDICTION_FIELDS)
    write_csv(output_map["visual_review_manifest"], visual_rows, VISUAL_REVIEW_FIELDS)
    write_pre_eval_seal(output_map)
    write_generation_gate_integrity(output_map, replay_status="")
    write_frozen_manifest(output_map)


def segment_for_frame(frame: int) -> str:
    return "burn_in" if frame <= GUARD_END else "regression_mechanism_diagnosis_window"


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


def association_row(
    counter: int,
    frame: int,
    track: ResponseTrack,
    detail: Mapping[str, Any],
    result: str,
    evidence_state: str,
    previous_response_x: float,
    previous_response_y: float,
    previous_area: float,
    previous_energy: float,
    previous_orientation: float,
) -> dict[str, Any]:
    del previous_response_x, previous_response_y, previous_area, previous_energy, previous_orientation
    same_motion = evidence_state in {"same_motion_supported", "reappeared_supported"} and result == "selected"
    return {
        "association_id": f"ASSOC_D1_R1_{counter:06d}",
        "sar_frame": frame,
        "response_track_id": track.track_id,
        "component_id": detail["component_id"],
        "association_result": result,
        "previous_response_x": fmt(detail["previous_response_x"]),
        "previous_response_y": fmt(detail["previous_response_y"]),
        "prior_track_relative_x": fmt(detail["prior_track_relative_x"]),
        "prior_track_relative_y": fmt(detail["prior_track_relative_y"]),
        "prior_predicted_response_x": fmt(detail["prior_predicted_response_x"]),
        "prior_predicted_response_y": fmt(detail["prior_predicted_response_y"]),
        "observed_response_x": fmt(detail["observed_response_x"]),
        "observed_response_y": fmt(detail["observed_response_y"]),
        "target_displacement_x": fmt(detail["target_displacement_x"]),
        "target_displacement_y": fmt(detail["target_displacement_y"]),
        "response_self_displacement_x": fmt(detail["response_self_displacement_x"]),
        "response_self_displacement_y": fmt(detail["response_self_displacement_y"]),
        "observed_relative_to_target_x": fmt(detail["observed_relative_to_target_x"]),
        "observed_relative_to_target_y": fmt(detail["observed_relative_to_target_y"]),
        "posterior_track_relative_x": fmt(detail.get("posterior_track_relative_x", "")),
        "posterior_track_relative_y": fmt(detail.get("posterior_track_relative_y", "")),
        "target_position_from_response_x": fmt(detail.get("target_position_from_response_x", "")),
        "target_position_from_response_y": fmt(detail.get("target_position_from_response_y", "")),
        "response_prediction_residual_px": fmt(detail["response_prediction_residual_px"]),
        "motion_residual_px": fmt(detail["motion_residual_px"]),
        "relative_position_residual_px": fmt(detail["relative_position_residual_px"]),
        "shape_change_px": fmt(detail["shape_change_px"]),
        "orientation_change_deg": fmt(detail["orientation_change_deg"]),
        "energy_change": fmt(detail["energy_change"]),
        "background_conflict": detail["background_conflict"],
        "background_track_id": detail["background_track_id"],
        "gate_response_prediction": detail["gate_response_prediction"],
        "gate_motion_consistency": detail["gate_motion_consistency"],
        "gate_relative_structure": detail["gate_relative_structure"],
        "gate_background_conflict": detail["gate_background_conflict"],
        "gate_temporal_support": detail["gate_temporal_support"],
        "rejection_reason": "" if result == "selected" else detail.get("rejection_reason", ""),
        "support_observation_count": track.support_observation_count,
        "support_unique_frame_count": track.support_unique_frame_count,
        "current_consecutive_support_frames": track.current_consecutive_support_frames,
        "current_missing_frames": track.current_missing_frames,
        "current_evidence_state": evidence_state,
        "highest_evidence_state_reached": track.highest_evidence_state_reached,
        "same_motion_supported": "true" if same_motion else "false",
    }


def transition_row(frame: int, track: ResponseTrack, previous: str, new: str, reason: str) -> dict[str, Any]:
    return {
        "transition_id": f"TRANS_D1_R1_{frame:06d}_{track.track_id}_{len(track.support_frame_ids):03d}",
        "sar_frame": frame,
        "response_track_id": track.track_id,
        "previous_evidence_state": previous,
        "current_evidence_state": new,
        "highest_evidence_state_reached": track.highest_evidence_state_reached,
        "support_observation_count": track.support_observation_count,
        "support_unique_frame_count": track.support_unique_frame_count,
        "current_consecutive_support_frames": track.current_consecutive_support_frames,
        "current_missing_frames": track.current_missing_frames,
        "transition_reason": reason,
    }


def response_track_rows(tracks: Sequence[ResponseTrack]) -> list[dict[str, Any]]:
    rows = []
    for track in tracks:
        current_state = "terminated" if track.terminated_frame else track.current_evidence_state
        rows.append(
            {
                "response_track_id": track.track_id,
                "init_frame": track.init_frame,
                "last_frame": track.last_frame,
                "current_evidence_state": current_state,
                "highest_evidence_state_reached": track.highest_evidence_state_reached,
                "support_observation_count": track.support_observation_count,
                "support_unique_frame_count": track.support_unique_frame_count,
                "support_frame_ids": ";".join(str(frame) for frame in sorted(track.support_frame_ids)),
                "current_consecutive_support_frames": track.current_consecutive_support_frames,
                "current_missing_frames": track.current_missing_frames,
                "reappearance_count": track.reappearance_count,
                "terminated_frame": track.terminated_frame,
                "last_response_x": fmt(track.last_x),
                "last_response_y": fmt(track.last_y),
                "relative_to_target_x": fmt(track.rel_x),
                "relative_to_target_y": fmt(track.rel_y),
                "same_motion_supported": "true" if current_state == "same_motion_supported" else "false",
            }
        )
    return rows


def background_track_rows(tracks: Sequence[BackgroundTrack], params: Mapping[str, str]) -> list[dict[str, Any]]:
    rows = []
    for track in tracks:
        rows.append(
            {
                "background_track_id": track.track_id,
                "first_frame": track.first_frame,
                "last_frame": track.last_frame,
                "fixed_coordinate_mean_x": fmt(track.mean_x),
                "fixed_coordinate_mean_y": fmt(track.mean_y),
                "position_variance": fmt(track.variance),
                "support_observation_count": track.support_observation_count,
                "support_unique_frame_count": track.support_unique_frame_count,
                "support_frame_ids": track.support_frame_ids,
                "missing_frames": track.missing_frames,
                "shape_variation": fmt(float(np.std(track.areas)) if len(track.areas) > 1 else 0.0),
                "energy_variation": fmt(float(np.std(track.energies)) if len(track.energies) > 1 else 0.0),
                "conflicting_vehicle_motion_frames": ";".join(str(frame) for frame in sorted(track.conflict_frames)),
                "background_state": background_state(track, params),
                "threshold_source": "P0 static_position_variance_threshold_px2 plus D1-R1 unique-frame support rules",
            }
        )
    return rows


def prediction_rows_for_frame(
    frame: int,
    policy_states: Mapping[str, PolicyState],
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
) -> list[dict[str, Any]]:
    rows = []
    for policy in POLICIES:
        state = policy_states[policy]
        rows.append(
            prediction_row(
                f"D1_R1_{policy}",
                frame,
                state.position_x,
                state.position_y,
                state.velocity_x,
                state.velocity_y,
                state.position_uncertainty,
                "d1_r1_admission_policy_state",
                policy,
            )
        )
    rows.append(prediction_row("D1_NO_OBSERVATION_UPDATE_BASELINE", frame, noobs_x, noobs_y, noobs_vx, noobs_vy, "", "no_current_observation_update_ablation", ""))
    rows.append(prediction_row("P0_ABSOLUTE_FRAME_LINEAR_BASELINE", frame, p0_x, p0_y, p0_vx, p0_vy, "", "p0_absolute_frame_baseline", ""))
    rows.append(prediction_row("P0_STATIC_CENTER_BASELINE", frame, static_x, static_y, 0.0, 0.0, "", "state_360_static_center_baseline", ""))
    return rows


def prediction_row(
    model_id: str,
    frame: int,
    x: Any,
    y: Any,
    vx: Any,
    vy: Any,
    uncertainty: Any,
    source: str,
    policy: str,
) -> dict[str, Any]:
    return {
        "prediction_id": f"PRED_{model_id}_{frame:06d}",
        "model_id": model_id,
        "sar_frame": frame,
        "segment": segment_for_frame(frame),
        "position_x": fmt(x),
        "position_y": fmt(y),
        "velocity_x": fmt(vx),
        "velocity_y": fmt(vy),
        "position_uncertainty": fmt(uncertainty),
        "last_update_source": source,
        "admission_policy": policy,
        "max_sar_frame_read": frame,
        "gt_file_opened": "false",
        "evaluation_file_opened": "false",
        "future_frame_read": "false",
        "pre_eval_frozen": "true",
    }


def render_frame_visual(
    frame: int,
    roi: Sequence[int],
    predicted: tuple[float, float],
    policy_centers: Mapping[str, tuple[float, float]],
    components: Sequence[Mapping[str, Any]],
    selected_assocs: Sequence[Mapping[str, Any]],
    rejected_assocs: Sequence[Mapping[str, Any]],
    background_tracks: Sequence[BackgroundTrack],
    visual_dir: Path,
) -> Path:
    visual_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(D1_BASE.sar_gray_path(frame)).convert("RGB")
    x1, y1, x2, y2 = roi
    focus = clamp_roi((x1, y1, x2, y2), margin=70)
    crop = image.crop((focus[0], focus[1], focus[2] + 1, focus[3] + 1)).resize((1180, 800))
    draw = ImageDraw.Draw(crop)

    def pt(x: float, y: float) -> tuple[float, float]:
        sx = 1180.0 / max(1.0, focus[2] - focus[0] + 1)
        sy = 800.0 / max(1.0, focus[3] - focus[1] + 1)
        return (x - focus[0]) * sx, (y - focus[1]) * sy

    def rect(box: Sequence[float], color: tuple[int, int, int], width: int = 1) -> None:
        a = pt(box[0], box[1])
        b = pt(box[2], box[3])
        draw.rectangle((a[0], a[1], b[0], b[1]), outline=color, width=width)

    for comp in components:
        rect((comp["bbox_x1"], comp["bbox_y1"], comp["bbox_x2"], comp["bbox_y2"]), (225, 210, 80), 1)
    for assoc in rejected_assocs:
        if assoc.get("gate_relative_structure") != "FAIL":
            continue
        px, py = pt(parse_float(assoc["observed_response_x"]), parse_float(assoc["observed_response_y"]))
        draw.line((px - 6, py - 6, px + 6, py + 6), fill=(255, 150, 40), width=2)
        draw.line((px - 6, py + 6, px + 6, py - 6), fill=(255, 150, 40), width=2)
    for assoc in selected_assocs:
        px, py = pt(parse_float(assoc["observed_response_x"]), parse_float(assoc["observed_response_y"]))
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), outline=(0, 230, 255), width=2)
        draw.text((px + 6, py - 6), assoc["response_track_id"], fill=(0, 230, 255))
    for track in background_tracks:
        if track.support_unique_frame_count < 3:
            continue
        px, py = pt(track.mean_x, track.mean_y)
        draw.rectangle((px - 6, py - 6, px + 6, py + 6), outline=(255, 80, 255), width=2)
        draw.text((px + 8, py - 7), track.track_id, fill=(255, 80, 255))

    center_specs = [
        (predicted, (255, 80, 80), "prior"),
        (policy_centers.get("ALL_ASSOCIATED_TRACKS"), (80, 255, 120), "A"),
        (policy_centers.get("TEMPORALLY_SUPPORTED_ONLY"), (80, 170, 255), "B"),
        (policy_centers.get("STRUCTURE_CONSISTENT_ONLY"), (210, 120, 255), "C"),
    ]
    for center, color, label in center_specs:
        if not center:
            continue
        px, py = pt(center[0], center[1])
        draw.line((px - 9, py, px + 9, py), fill=color, width=2)
        draw.line((px, py - 9, px, py + 9), fill=color, width=2)
        draw.text((px + 10, py + 4), label, fill=color)
    rect((x1, y1, x2, y2), (80, 160, 255), 2)
    draw.rectangle((0, 0, 1179, 30), fill=(0, 0, 0))
    draw.text((8, 8), f"SAR {frame} D1-R1: cyan=selected orange=relative reject magenta=background red=prior green/blue/purple=A/B/C", fill=(255, 255, 255))
    path = visual_dir / f"d1_r1_semantic_integrity_sar{frame:03d}.png"
    crop.save(path)
    return path


def render_contact_sheet(paths: Mapping[int, Path], visual_dir: Path) -> Path:
    thumbs: list[Image.Image] = []
    for frame in sorted(paths):
        image = Image.open(paths[frame]).convert("RGB").resize((420, 285))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 96, 23), fill=(0, 0, 0))
        draw.text((6, 6), f"SAR {frame}", fill=(255, 255, 255))
        thumbs.append(image)
    cols = 4
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 420, rows * 285), (20, 20, 20))
    for idx, image in enumerate(thumbs):
        sheet.paste(image, ((idx % cols) * 420, (idx // cols) * 285))
    path = visual_dir / "d1_r1_visual_review_contact_sheet.png"
    sheet.save(path)
    return path


def policy_divergence(centers: Mapping[str, tuple[float, float]]) -> float:
    values = list(centers.values())
    if len(values) < 2:
        return 0.0
    return max(math.hypot(a[0] - b[0], a[1] - b[1]) for a in values for b in values)


def build_visual_review_manifest(
    visual_paths: Mapping[int, Path],
    contact_sheet: Path,
    context: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    max_div_frame = max(context, key=lambda frame: parse_float(context[frame]["policy_divergence_px"]))
    max_correction_frame = max(context, key=lambda frame: parse_float(context[frame]["max_policy_correction_px"]))
    max_relative_reject_frame = max(context, key=lambda frame: parse_int(context[frame]["relative_reject_count"]))
    sampled_frames = {361, 366, 371, 376, 381, 386, 391, 394}
    rows = []
    for frame in range(GENERATE_START, DIAGNOSIS_END + 1):
        item = context[frame]
        reasons = []
        if frame == max_div_frame:
            reasons.append("max_admission_policy_divergence_frame")
        if frame == max_correction_frame:
            reasons.append("max_state_correction_frame")
        if frame == max_relative_reject_frame:
            reasons.append("relative_structure_reject_max_frame")
        if parse_int(item["missing_count"]):
            reasons.append("missing_frame")
        if parse_int(item["reappearance_candidate_count"]):
            reasons.append("reappearance_first_hit_frame")
        if parse_int(item["reappearance_confirm_count"]):
            reasons.append("reappearance_confirmed_frame")
        if parse_int(item["background_association_count"]):
            reasons.append("background_association_frame")
        if frame in sampled_frames:
            reasons.append("uniform_sequence_sample")
        if not reasons:
            reasons.append("contact_sheet_sequence_review")
        note = (
            f"SAR{frame}: 选中响应{item['selected_count']}条, relative结构拒绝{item['relative_reject_count']}条, "
            f"A/B/C中心分歧{fmt(item['policy_divergence_px'])}px, 背景关联{item['background_association_count']}条。"
        )
        if parse_int(item["reappearance_candidate_count"]):
            note += " 本帧含缺失后的首次重新关联, 只记为candidate。"
        if parse_int(item["reappearance_confirm_count"]):
            note += " 本帧出现后续连续支持的重现确认。"
        if parse_int(item["relative_reject_count"]):
            note += " 橙色叉号显示relative structure gate实际拒绝了候选。"
        if parse_float(item["policy_divergence_px"]) > 1.0:
            note += " 准入策略改变了递归中心, 不是selector或ranking。"
        rows.append(
            {
                "sar_frame": frame,
                "diagnostic_png": rel(visual_paths[frame]),
                "contact_sheet": rel(contact_sheet),
                "review_reason": ";".join(reasons),
                "selected_response_count": item["selected_count"],
                "relative_structure_reject_count": item["relative_reject_count"],
                "background_association_count": item["background_association_count"],
                "policy_divergence_px": fmt(item["policy_divergence_px"]),
                "max_policy_correction_px": fmt(item["max_policy_correction_px"]),
                "visual_judgment_cn": note,
                "automatic_state_matches_image": "review_required_for_focus_frames",
                "wrong_association_found": "not_declared_without_manual_focus_review",
                "downgrade_needed": "visual_review_limits_membership_claims",
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
                "input_role": "frozen_p0_calibration_or_protocol_input",
                "sha256": sha256_file(path) if path.exists() else "missing",
                "gt_scope": "calibration_frozen_only",
                "notes": "No diagnosis-window reference labels are opened by the generator.",
            }
        )
    rows.append(
        {
            "input_id": "d1_helper_source_for_component_extraction_only",
            "path": rel(D1_SOURCE),
            "allowed_in_generation": "true",
            "input_role": "implementation_helper_no_d1_outputs_read",
            "sha256": sha256_file(D1_SOURCE),
            "gt_scope": "none",
            "notes": "D1-R1 reuses extraction helper code only; D1 generated CSV outputs are not runtime inputs.",
        }
    )
    rows.append(
        {
            "input_id": "sar_gray_frames_current_and_history",
            "path": r"D:\profile\research\data\GM_RM017\GM_RM017_SARframes_gray",
            "allowed_in_generation": "true",
            "input_role": "current_and_past_sar_observation",
            "sha256": "directory_not_hashed_large_external_input",
            "gt_scope": "none",
            "notes": "Frame loop reads only the current SAR frame in sequential order.",
        }
    )
    return rows


def write_pre_eval_seal(output_map: Mapping[str, Path]) -> None:
    rows = []
    generator_sha = sha256_file(Path(__file__))
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
                "generator_source_sha256": generator_sha,
                "runtime_parameters_sha256": sha256_file(output_map["frozen_runtime_parameters"]),
                "allowed_inputs": "frozen_p0_calibration_artifacts;current_and_past_sar_gray_frames;d1_extraction_helper_source",
            }
        )
    write_csv(output_map["pre_eval_seal"], rows, PRE_EVAL_SEAL_FIELDS)


def generator_forbidden_terms_absent() -> bool:
    text = Path(__file__).read_text(encoding="utf-8")
    forbidden = ["PAIR" + "_CSV", "holdout" + "_gt_rows", "oty2_wgv3_5a_" + "paired_annotations", "target" + "_rows()"]
    return not any(term in text for term in forbidden)


def write_generation_gate_integrity(output_map: Mapping[str, Path], replay_status: str) -> None:
    assoc_rows = read_csv(output_map["response_associations"]) if output_map["response_associations"].exists() else []
    bg_rows = read_csv(output_map["background_tracks"]) if output_map["background_tracks"].exists() else []
    bg_assoc = read_csv(output_map["background_associations"]) if output_map["background_associations"].exists() else []
    track_rows = read_csv(output_map["response_tracks"]) if output_map["response_tracks"].exists() else []
    state_rows = read_csv(output_map["admission_policy_state_history"]) if output_map["admission_policy_state_history"].exists() else []
    visual_rows = read_csv(output_map["visual_review_manifest"]) if output_map["visual_review_manifest"].exists() else []
    selected_assoc = [row for row in assoc_rows if row.get("association_result") == "selected"]
    rows = [
        gate("WORKTREE_BRANCH_VALID", git_output(["branch", "--show-current"]) == BRANCH, f"branch={git_output(['branch', '--show-current'])};head={git_output(['rev-parse', 'HEAD'])}"),
        gate("GENERATOR_HOLDOUT_GT_IMPORT_FORBIDDEN", generator_forbidden_terms_absent(), "generator source scanned for forbidden reference-label readers"),
        gate("HOLDOUT_GT_NOT_READ_DURING_GENERATION", all(row.get("gt_file_opened") == "false" for row in state_rows), "state history gt_file_opened=false"),
        gate("FUTURE_FRAME_NOT_READ", all(parse_int(row.get("max_sar_frame_read")) <= parse_int(row.get("sar_frame")) and row.get("future_frame_read") == "false" for row in state_rows), "max_sar_frame_read never exceeds current frame"),
        gate("BACKGROUND_ONE_COMPONENT_PER_TRACK_PER_FRAME", no_duplicate(bg_assoc, ["background_track_id", "sar_frame"]), "background association unique by track/frame"),
        gate("BACKGROUND_ONE_TRACK_PER_COMPONENT_PER_FRAME", no_duplicate(bg_assoc, ["component_id", "sar_frame"]), "background association unique by component/frame"),
        gate("BACKGROUND_UNIQUE_FRAME_SUPPORT_VALID", background_unique_support_valid(bg_rows), "background states use support_unique_frame_count and support_frame_ids"),
        gate("RESPONSE_STATE_MACHINE_CONSISTENT", response_state_machine_valid(track_rows, selected_assoc), "current state is single and same_motion flag matches current state"),
        gate("RELATIVE_STRUCTURE_GATE_ACTIVE", any(row.get("gate_relative_structure") == "FAIL" for row in assoc_rows), "relative structure gate produces explicit rejected rows"),
        gate("PRIOR_RESPONSE_PREDICTION_UNCONTAMINATED", prior_prediction_valid(assoc_rows), "prior_predicted_response uses prior relative offset before current observation update"),
        gate("ADMISSION_POLICY_ABLATION_COMPLETE", len(state_rows) == len(POLICIES) * (DIAGNOSIS_END - GENERATE_START + 1), "A/B/C state histories exist for every generated frame"),
        gate("VISUAL_REVIEW_GROUNDED", len(visual_rows) == DIAGNOSIS_END - GENERATE_START + 1 and len({row.get('visual_judgment_cn') for row in visual_rows}) > 5, f"visual_rows={len(visual_rows)}"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_status == "PASS" if replay_status else False, replay_status or "pending"),
        gate("D1_R1_SEMANTIC_INTEGRITY_READY", False, "pending evaluator, replay, and post-eval gate consolidation"),
        gate("D1_R1_PHYSICAL_DYNAMIC_MEMBERSHIP_READY", False, "not asserted by generator"),
    ]
    write_csv(output_map["gate_integrity"], rows, GATE_FIELDS)


def no_duplicate(rows: Sequence[Mapping[str, str]], fields: Sequence[str]) -> bool:
    keys = [tuple(row.get(field, "") for field in fields) for row in rows]
    return len(keys) == len(set(keys))


def background_unique_support_valid(rows: Sequence[Mapping[str, str]]) -> bool:
    for row in rows:
        frame_ids = [item for item in row.get("support_frame_ids", "").split(";") if item]
        unique_count = parse_int(row.get("support_unique_frame_count"))
        obs_count = parse_int(row.get("support_observation_count"))
        state = row.get("background_state", "")
        if unique_count != len(set(frame_ids)):
            return False
        if obs_count < unique_count:
            return False
        if state in {"static_background_candidate", "static_background_supported"} and unique_count < 3:
            return False
        if state == "static_background_supported" and unique_count < 5:
            return False
    return bool(rows)


def response_state_machine_valid(track_rows: Sequence[Mapping[str, str]], selected_rows: Sequence[Mapping[str, str]]) -> bool:
    valid_states = set(STATE_ORDER) | {"terminated"}
    for row in track_rows:
        current = row.get("current_evidence_state", "")
        if current not in valid_states:
            return False
        if row.get("same_motion_supported") == "true" and current != "same_motion_supported":
            return False
    for row in selected_rows:
        current = row.get("current_evidence_state", "")
        if row.get("same_motion_supported") == "true" and current not in {"same_motion_supported", "reappeared_supported"}:
            return False
        if current == "same_motion_supported" and parse_int(row.get("support_unique_frame_count")) < 2:
            return False
    return bool(track_rows)


def prior_prediction_valid(rows: Sequence[Mapping[str, str]]) -> bool:
    checked = 0
    for row in rows:
        prior_rel_x = parse_float(row.get("prior_track_relative_x"))
        prior_rel_y = parse_float(row.get("prior_track_relative_y"))
        target_dx = parse_float(row.get("target_displacement_x"))
        target_dy = parse_float(row.get("target_displacement_y"))
        previous_x = parse_float(row.get("previous_response_x"))
        previous_y = parse_float(row.get("previous_response_y"))
        expected_x = previous_x + target_dx
        expected_y = previous_y + target_dy
        actual_x = parse_float(row.get("prior_predicted_response_x"))
        actual_y = parse_float(row.get("prior_predicted_response_y"))
        observed_rel_x = parse_float(row.get("observed_relative_to_target_x"))
        observed_rel_y = parse_float(row.get("observed_relative_to_target_y"))
        residual = parse_float(row.get("relative_position_residual_px"))
        if abs(actual_x - expected_x) > 80.0 or abs(actual_y - expected_y) > 80.0:
            # The track relative offset can drift from previous response, so this
            # wide check only catches current-observation contamination.
            return False
        if abs(math.hypot(observed_rel_x - prior_rel_x, observed_rel_y - prior_rel_y) - residual) > 1e-3:
            return False
        checked += 1
    return checked > 0


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
                    "row_count": row_count(path),
                    "phase": "d1_r1_generation",
                    "notes": "Visual PNGs remain ignored under outputs and are referenced by CSV only." if key == "visual_review_manifest" else "",
                }
            )
    write_csv(output_map["frozen_manifest"], rows, FROZEN_MANIFEST_FIELDS)


def verify_replay() -> None:
    ensure_dirs()
    resolved_replay = REPLAY_DIR.resolve()
    resolved_output = OUTPUT_DIR.resolve()
    if REPLAY_DIR.exists():
        if not resolved_replay.is_relative_to(resolved_output):
            raise RuntimeError(f"refusing to remove replay path outside output dir: {REPLAY_DIR}")
        shutil.rmtree(REPLAY_DIR)
    replay_outputs = {key: REPLAY_DIR / path.name for key, path in OUTPUTS.items()}
    run_generation(replay_outputs, VISUAL_DIR)
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
    write_generation_gate_integrity(OUTPUTS, replay_status=status)
    write_frozen_manifest(OUTPUTS)
    print(f"FROZEN_REPLAY_IDENTICAL={status}")


RUNTIME_INPUT_FIELDS = ["input_id", "path", "allowed_in_generation", "input_role", "sha256", "gt_scope", "notes"]
RUNTIME_PARAMETER_FIELDS = ["parameter_name", "parameter_value", "source", "frozen_before_eval", "gt_tuned"]
INITIAL_STATE_FIELDS = [
    "sar_frame",
    "position_x",
    "position_y",
    "velocity_x",
    "velocity_y",
    "position_uncertainty",
    "velocity_uncertainty",
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
RESPONSE_TRACK_FIELDS = [
    "response_track_id",
    "init_frame",
    "last_frame",
    "current_evidence_state",
    "highest_evidence_state_reached",
    "support_observation_count",
    "support_unique_frame_count",
    "support_frame_ids",
    "current_consecutive_support_frames",
    "current_missing_frames",
    "reappearance_count",
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
    "association_result",
    "previous_response_x",
    "previous_response_y",
    "prior_track_relative_x",
    "prior_track_relative_y",
    "prior_predicted_response_x",
    "prior_predicted_response_y",
    "observed_response_x",
    "observed_response_y",
    "target_displacement_x",
    "target_displacement_y",
    "response_self_displacement_x",
    "response_self_displacement_y",
    "observed_relative_to_target_x",
    "observed_relative_to_target_y",
    "posterior_track_relative_x",
    "posterior_track_relative_y",
    "target_position_from_response_x",
    "target_position_from_response_y",
    "response_prediction_residual_px",
    "motion_residual_px",
    "relative_position_residual_px",
    "shape_change_px",
    "orientation_change_deg",
    "energy_change",
    "background_conflict",
    "background_track_id",
    "gate_response_prediction",
    "gate_motion_consistency",
    "gate_relative_structure",
    "gate_background_conflict",
    "gate_temporal_support",
    "rejection_reason",
    "support_observation_count",
    "support_unique_frame_count",
    "current_consecutive_support_frames",
    "current_missing_frames",
    "current_evidence_state",
    "highest_evidence_state_reached",
    "same_motion_supported",
]
RESPONSE_TRANSITION_FIELDS = [
    "transition_id",
    "sar_frame",
    "response_track_id",
    "previous_evidence_state",
    "current_evidence_state",
    "highest_evidence_state_reached",
    "support_observation_count",
    "support_unique_frame_count",
    "current_consecutive_support_frames",
    "current_missing_frames",
    "transition_reason",
]
BACKGROUND_TRACK_FIELDS = [
    "background_track_id",
    "first_frame",
    "last_frame",
    "fixed_coordinate_mean_x",
    "fixed_coordinate_mean_y",
    "position_variance",
    "support_observation_count",
    "support_unique_frame_count",
    "support_frame_ids",
    "missing_frames",
    "shape_variation",
    "energy_variation",
    "conflicting_vehicle_motion_frames",
    "background_state",
    "threshold_source",
]
BACKGROUND_ASSOC_FIELDS = [
    "background_association_id",
    "sar_frame",
    "background_track_id",
    "component_id",
    "association_result",
    "match_distance_px",
    "support_observation_count_after",
    "support_unique_frame_count_after",
    "track_component_count_this_frame",
    "component_track_count_this_frame",
    "background_state_after",
    "vehicle_motion_conflict",
    "conflict_reason",
]
VISIBILITY_FIELDS = [
    "event_id",
    "sar_frame",
    "response_track_id",
    "visibility_state",
    "missing_frames",
    "last_reliable_state_before_missing",
    "position_uncertainty",
    "reason",
]
REAPPEARANCE_CANDIDATE_FIELDS = [
    "event_id",
    "sar_frame",
    "response_track_id",
    "gap_class",
    "missing_frames_before",
    "last_reliable_state_before_missing",
    "prior_predicted_response_x",
    "prior_predicted_response_y",
    "first_reassociated_response_x",
    "first_reassociated_response_y",
    "relative_structure_residual_px",
    "background_conflict",
    "final_confirmation_state",
]
REAPPEARANCE_CONFIRMATION_FIELDS = [
    "event_id",
    "sar_frame",
    "response_track_id",
    "confirmation_state",
    "post_reappearance_support_frames",
    "relative_structure_residual_px",
    "background_conflict",
    "confirmed",
]
ADMISSION_STATE_FIELDS = [
    "sar_frame",
    "segment",
    "admission_policy",
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
    "eligible_track_ids",
    "excluded_track_ids",
    "exclusion_reasons",
    "observation_supported_position",
    "posterior_correction",
    "current_response_association_count",
    "eligible_track_count",
    "no_observation_fallback",
    "last_update_source",
    "cap_triggered",
    "frame_observation_complete",
    "max_sar_frame_read",
    "gt_file_opened",
    "evaluation_file_opened",
    "future_frame_read",
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
    "admission_policy",
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
    "selected_response_count",
    "relative_structure_reject_count",
    "background_association_count",
    "policy_divergence_px",
    "max_policy_correction_px",
    "visual_judgment_cn",
    "automatic_state_matches_image",
    "wrong_association_found",
    "downgrade_needed",
]
PRE_EVAL_SEAL_FIELDS = [
    "artifact_key",
    "path",
    "sha256",
    "row_count",
    "seal_phase",
    "gt_allowed_at_creation",
    "code_commit_sha",
    "generator_source_sha256",
    "runtime_parameters_sha256",
    "allowed_inputs",
]
GATE_FIELDS = ["gate_id", "status", "evidence", "notes"]
REPLAY_FIELDS = ["artifact_key", "frozen_sha256", "replay_sha256", "status"]
FROZEN_MANIFEST_FIELDS = ["artifact_key", "path", "sha256", "row_count", "phase", "notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["generate", "verify-replay"])
    parser.add_argument("--verify-replay", action="store_true", dest="verify_replay_flag")
    args = parser.parse_args()
    if args.verify_replay_flag and args.command and args.command != "verify-replay":
        parser.error("--verify-replay cannot be combined with generate")
    command = "verify-replay" if args.verify_replay_flag else args.command
    if command is None:
        parser.error("one of generate, verify-replay, or --verify-replay is required")
    if command == "generate":
        run_generation(OUTPUTS, VISUAL_DIR)
        print("D1-R1 generation complete")
    elif command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
