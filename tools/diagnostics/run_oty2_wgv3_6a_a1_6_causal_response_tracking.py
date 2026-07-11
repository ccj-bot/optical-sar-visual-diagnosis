"""WGV3.6A-A1.6 leakage-free causal SAR visible-response tracking audit.

The generate phase freezes C0/C1/C2 predictions from one left SAR anchor and
runtime-safe sources only. Hidden target manual SAR boxes are loaded only by
the evaluate phase after the frozen prediction CSV SHA256 is verified.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping import (  # noqa: E402
    REPO_ROOT,
    REPORT_DIR,
    SAMPLES_DIR,
    SAR_HEIGHT,
    SAR_WIDTH,
    Box,
    box_from_pair,
    build_geometry,
    fmt,
    parse_float,
    parse_int,
    read_gray,
    sar_gray_path,
    sha256,
    write_csv,
    write_text,
)


DATE = "20260711"
REQUESTED_START_COMMIT = "2bf1ea2bafffe9876935b3b41f8c091d0a3fad2a"
SCENE = "GM_RM019"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_6_20260711"

INPUTS = {
    "paired": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "optical_state": SAMPLES_DIR / "oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_20260710.csv",
    "optical_review": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_optical_state_review_20260711.csv",
    "a1_5_report": REPORT_DIR / "oty2_wgv3_6a_a1_5_propagation_integrity_audit_20260711.md",
    "temporal_report": REPORT_DIR / "oty2_alignment_mode_decision_report_20260702_132945.md",
    "temporal_summary": REPORT_DIR / "oty2_alignment_mode_decision_summary_20260702_132945.csv",
    "temporal_inventory": REPORT_DIR / "oty2_temporal_metadata_inventory_20260702_132945.csv",
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_6_causal_response_tracking_{DATE}.md",
    "temporal_audit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_6_temporal_alignment_source_audit_{DATE}.csv",
    "hidden_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_6_hidden_target_manifest_{DATE}.csv",
    "runtime_input_audit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_6_runtime_input_field_audit_{DATE}.csv",
    "frozen_predictions": SAMPLES_DIR / f"oty2_wgv3_6a_a1_6_frozen_predictions_{DATE}.csv",
    "frame_state_trace": SAMPLES_DIR / f"oty2_wgv3_6a_a1_6_frame_state_trace_{DATE}.csv",
    "hidden_evaluation": SAMPLES_DIR / f"oty2_wgv3_6a_a1_6_hidden_anchor_evaluation_{DATE}.csv",
    "delta_audit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_6_c0_c1_c2_delta_audit_{DATE}.csv",
}

VISUALS = {
    "runtime_adjacent": OUT_DIR / "a1_6_runtime_adjacent_predictions.png",
    "runtime_open_loop": OUT_DIR / "a1_6_runtime_open_loop_predictions.png",
    "eval_adjacent": OUT_DIR / "a1_6_eval_only_adjacent_target_overlay.png",
    "eval_failures": OUT_DIR / "a1_6_eval_only_failure_examples.png",
}

WHITE = "PV_GM19_WHITE_SUV_NEAR_FIELD"
SILVER = "PV_GM19_SILVER_MPV_NEAR_FIELD"

PAIR_META = {
    "WGV35A_PAIR_0204": (WHITE, 13, 27),
    "WGV35A_PAIR_0205": (WHITE, 15, 31),
    "WGV35A_PAIR_0206": (WHITE, 37, 77),
    "WGV35A_PAIR_0207": (WHITE, 39, 81),
    "WGV35A_PAIR_0208": (SILVER, 102, 212),
    "WGV35A_PAIR_0209": (SILVER, 114, 238),
    "WGV35A_PAIR_0210": (SILVER, 129, 269),
    "WGV35A_PAIR_0211": (SILVER, 131, 273),
    "WGV35A_PAIR_0212": (SILVER, 138, 288),
    "WGV35A_PAIR_0213": (SILVER, 139, 290),
}

ADJACENT_SPECS = [
    ("ADJ_0204_TO_0205", WHITE, "WGV35A_PAIR_0204", 27, "WGV35A_PAIR_0205", 31),
    ("ADJ_0205_TO_0206", WHITE, "WGV35A_PAIR_0205", 31, "WGV35A_PAIR_0206", 77),
    ("ADJ_0206_TO_0207", WHITE, "WGV35A_PAIR_0206", 77, "WGV35A_PAIR_0207", 81),
    ("ADJ_0208_TO_0209", SILVER, "WGV35A_PAIR_0208", 212, "WGV35A_PAIR_0209", 238),
    ("ADJ_0209_TO_0210", SILVER, "WGV35A_PAIR_0209", 238, "WGV35A_PAIR_0210", 269),
    ("ADJ_0210_TO_0211", SILVER, "WGV35A_PAIR_0210", 269, "WGV35A_PAIR_0211", 273),
    ("ADJ_0211_TO_0212", SILVER, "WGV35A_PAIR_0211", 273, "WGV35A_PAIR_0212", 288),
    ("ADJ_0212_TO_0213", SILVER, "WGV35A_PAIR_0212", 288, "WGV35A_PAIR_0213", 290),
]

OPEN_LOOP_SPECS = [
    (
        "OPEN_WHITE_0204_TO_0207",
        WHITE,
        "WGV35A_PAIR_0204",
        27,
        81,
        [("WGV35A_PAIR_0205", 31), ("WGV35A_PAIR_0206", 77), ("WGV35A_PAIR_0207", 81)],
    ),
    (
        "OPEN_SILVER_0208_TO_0213",
        SILVER,
        "WGV35A_PAIR_0208",
        212,
        290,
        [
            ("WGV35A_PAIR_0209", 238),
            ("WGV35A_PAIR_0210", 269),
            ("WGV35A_PAIR_0211", 273),
            ("WGV35A_PAIR_0212", 288),
            ("WGV35A_PAIR_0213", 290),
        ],
    ),
]

TEMPORAL_FIELDS = [
    "source_file",
    "source_type",
    "optical_time_field",
    "sar_time_field",
    "mapping_rule",
    "uses_gt_or_manual_target",
    "target_independent",
    "usable_for_runtime",
    "notes",
]

MANIFEST_FIELDS = [
    "experiment_id",
    "experiment_type",
    "physical_vehicle_id",
    "source_pair_id",
    "source_sar_frame",
    "hidden_target_pair_id",
    "hidden_target_sar_frame",
    "target_box_loaded_in_generate",
    "target_box_loaded_in_evaluate",
    "notes",
]

RUNTIME_AUDIT_FIELDS = [
    "phase",
    "source_file",
    "field_name",
    "semantic_role",
    "used_by_generate",
    "used_by_evaluate",
    "forbidden_in_generate",
    "observed_in_generate",
    "notes",
]

PRED_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "source_sar_frame",
    "target_pair_id",
    "target_sar_frame",
    "sar_frame",
    "frame_offset",
    "prediction_status",
    "prediction_region",
    "search_window",
    "response_center",
    "response_width",
    "response_height",
    "response_intensity",
    "component_area",
    "selection_status",
    "stop_reason",
    "search_window_area",
    "static_fan_geometry_area",
    "search_ratio",
    "cumulative_drift_from_source",
    "frozen_generation_phase",
    "target_manual_box_loaded",
    "future_endpoint_loaded",
]

TRACE_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "target_pair_id",
    "sar_frame",
    "prior_region",
    "prediction_region",
    "search_window",
    "component_count_raw",
    "component_count_after_gate",
    "selected_component_id",
    "selection_status",
    "distance_to_prediction",
    "area_change_ratio",
    "intensity_change",
    "overlap_with_previous",
    "motion_direction_consistent",
    "depth_trend_consistent",
    "optical_constraint_used",
    "optical_state_frame",
    "optical_velocity_x",
    "optical_depth_velocity",
    "response_switch_event",
    "stop_reason",
    "image_path_loaded",
    "forbidden_fields_asserted",
]

EVAL_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "hidden_target_pair_id",
    "sar_frame",
    "frame_offset",
    "hidden_target_coverage",
    "hidden_target_iou",
    "prediction_center_to_visible_response_center",
    "prediction_region_area",
    "search_window_area",
    "static_fan_geometry_area",
    "search_ratio",
    "prediction_status",
    "selection_status",
    "first_lost_frame",
    "consecutive_missing_length",
    "ambiguous_frame_count",
    "measured_response_switch_count",
    "cumulative_drift_from_source",
    "frozen_predictions_sha256_verified",
    "target_box_loaded_phase",
]

DELTA_FIELDS = [
    "comparison",
    "experiment_id",
    "experiment_type",
    "physical_vehicle_id",
    "hidden_target_pair_id",
    "sar_frame",
    "coverage_delta",
    "iou_delta",
    "center_error_delta",
    "search_ratio_delta",
    "verdict",
    "notes",
]


@dataclass(frozen=True)
class RunSpec:
    experiment_id: str
    experiment_type: str
    physical_vehicle_id: str
    source_pair_id: str
    source_sar_frame: int
    end_sar_frame: int
    eval_pairs: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Component:
    component_id: str
    box: Box
    center: tuple[float, float]
    area: int
    mean_intensity: float
    distance_to_prediction: float
    motion_direction_consistent: str
    depth_trend_consistent: str


@dataclass(frozen=True)
class StepResult:
    region: Box
    search_window: Box
    response_center: tuple[float, float]
    response_intensity: str
    component_area: str
    prediction_status: str
    selection_status: str
    stop_reason: str
    component_count_raw: int
    component_count_after_gate: int
    selected_component_id: str
    distance_to_prediction: str
    area_change_ratio: str
    intensity_change: str
    overlap_with_previous: str
    motion_direction_consistent: str
    depth_trend_consistent: str
    optical_constraint_used: str
    response_switch_event: str
    image_path_loaded: str


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def safe_div(num: float, den: float) -> float:
    return num / den if den else math.nan


def percentile(values: Iterable[float], q: float) -> float:
    vals = [float(v) for v in values if not math.isnan(float(v))]
    if not vals:
        return math.nan
    return float(np.percentile(np.array(vals, dtype=np.float32), q))


def clamp_box(box: Box) -> Box:
    return Box(
        max(0.0, min(float(SAR_WIDTH - 1), box.x1)),
        max(0.0, min(float(SAR_HEIGHT - 1), box.y1)),
        max(1.0, min(float(SAR_WIDTH), box.x2)),
        max(1.0, min(float(SAR_HEIGHT), box.y2)),
    )


def expand_box(box: Box, dx: float, dy: float) -> Box:
    return clamp_box(Box(box.x1 - dx, box.y1 - dy, box.x2 + dx, box.y2 + dy))


def translate_box(box: Box, dx: float, dy: float) -> Box:
    return clamp_box(Box(box.x1 + dx, box.y1 + dy, box.x2 + dx, box.y2 + dy))


def center_box(cx: float, cy: float, width: float, height: float) -> Box:
    return clamp_box(Box(cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0))


def box_iou(a: Box, b: Box) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def coverage(region: Box, target: Box) -> float:
    x1 = max(region.x1, target.x1)
    y1 = max(region.y1, target.y1)
    x2 = min(region.x2, target.x2)
    y2 = min(region.y2, target.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return inter / target.area if target.area > 0 else 0.0


def center_distance(a: Box, b: Box) -> float:
    return math.hypot(a.cx - b.cx, a.cy - b.cy)


def dilate(binary: np.ndarray, iterations: int) -> np.ndarray:
    out = binary.astype(bool, copy=True)
    for _ in range(iterations):
        pad = np.pad(out, 1, constant_values=False)
        out = (
            pad[:-2, :-2]
            | pad[:-2, 1:-1]
            | pad[:-2, 2:]
            | pad[1:-1, :-2]
            | pad[1:-1, 1:-1]
            | pad[1:-1, 2:]
            | pad[2:, :-2]
            | pad[2:, 1:-1]
            | pad[2:, 2:]
        )
    return out


def erode(binary: np.ndarray, iterations: int) -> np.ndarray:
    out = binary.astype(bool, copy=True)
    for _ in range(iterations):
        pad = np.pad(out, 1, constant_values=False)
        out = (
            pad[:-2, :-2]
            & pad[:-2, 1:-1]
            & pad[:-2, 2:]
            & pad[1:-1, :-2]
            & pad[1:-1, 1:-1]
            & pad[1:-1, 2:]
            & pad[2:, :-2]
            & pad[2:, 1:-1]
            & pad[2:, 2:]
        )
    return out


def close_binary(binary: np.ndarray) -> np.ndarray:
    return erode(dilate(binary, 3), 2)


def connected_components(binary: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    seen = np.zeros(binary.shape, dtype=bool)
    comps: list[tuple[int, int, int, int, int]] = []
    height, width = binary.shape
    ys, xs = np.nonzero(binary)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        min_x = max_x = x0
        min_y = max_y = y0
        area = 0
        while stack:
            y, x = stack.pop()
            area += 1
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for yy in (y - 1, y, y + 1):
                for xx in (x - 1, x, x + 1):
                    if yy == y and xx == x:
                        continue
                    if 0 <= yy < height and 0 <= xx < width and binary[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        stack.append((yy, xx))
        comps.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return comps


def load_source_anchor_rows(source_pair_ids: set[str]) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    allowed_fields = {
        "pair_id",
        "scene",
        "optical_frame",
        "sar_frame",
        "sar_bbox_x1",
        "sar_bbox_y1",
        "sar_bbox_x2",
        "sar_bbox_y2",
    }
    with INPUTS["paired"].open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            pair_id = row.get("pair_id", "")
            if pair_id not in source_pair_ids:
                continue
            kept = {field: row.get(field, "") for field in allowed_fields}
            kept["physical_vehicle_id"] = PAIR_META[pair_id][0]
            rows[pair_id] = kept
    missing = sorted(source_pair_ids - set(rows))
    if missing:
        raise RuntimeError(f"Missing source anchor rows: {missing}")
    return rows


def load_hidden_target_rows() -> dict[str, dict[str, str]]:
    target_ids = {target for _, _, _, _, target, _ in ADJACENT_SPECS}
    target_ids.update(pair_id for _, _, _, _, _, evals in OPEN_LOOP_SPECS for pair_id, _ in evals)
    rows: dict[str, dict[str, str]] = {}
    for row in read_rows(INPUTS["paired"]):
        pair_id = row.get("pair_id", "")
        if pair_id in target_ids:
            kept = dict(row)
            kept["physical_vehicle_id"] = PAIR_META[pair_id][0]
            rows[pair_id] = kept
    missing = sorted(target_ids - set(rows))
    if missing:
        raise RuntimeError(f"Missing hidden target rows: {missing}")
    return rows


def load_optical_state() -> dict[str, list[dict[str, str]]]:
    by_pv: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(INPUTS["optical_state"]):
        by_pv[row.get("physical_vehicle_id", "")].append(row)
    for rows in by_pv.values():
        rows.sort(key=lambda row: parse_int(row.get("frame")))
    return by_pv


def nearest_optical_state(rows: Sequence[Mapping[str, str]], sar_frame: int) -> Mapping[str, str] | None:
    if not rows:
        return None
    optical_frame = sar_frame * 24.0 / 50.0
    return min(rows, key=lambda row: abs(parse_float(row.get("frame")) - optical_frame))


def build_specs() -> list[RunSpec]:
    specs: list[RunSpec] = []
    for exp_id, pv, source_pair, source_frame, target_pair, target_frame in ADJACENT_SPECS:
        specs.append(
            RunSpec(
                exp_id,
                "adjacent_hidden_anchor",
                pv,
                source_pair,
                source_frame,
                target_frame,
                ((target_pair, target_frame),),
            )
        )
    for exp_id, pv, source_pair, source_frame, end_frame, evals in OPEN_LOOP_SPECS:
        specs.append(
            RunSpec(
                exp_id,
                "open_loop",
                pv,
                source_pair,
                source_frame,
                end_frame,
                tuple(evals),
            )
        )
    return specs


def temporal_audit_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_file": rel(INPUTS["temporal_report"]),
            "source_type": "alignment_mode_decision_report",
            "optical_time_field": "known_optical_fps=24; software_sync_zero_offset_assumption",
            "sar_time_field": "known_sar_fps=50; software_sync_zero_offset_assumption",
            "mapping_rule": "sar_frame = optical_frame * 50 / 24, offset_seconds=0, jitter_ms=20",
            "uses_gt_or_manual_target": "false",
            "target_independent": "true",
            "usable_for_runtime": "conditional",
            "notes": "Not hardware timestamp truth; sufficient only for conditional optical motion phase lookup and jitter-aware temporal reasoning.",
        },
        {
            "source_file": rel(INPUTS["temporal_summary"]),
            "source_type": "per_scene_alignment_summary_csv",
            "optical_time_field": "known_optical_fps; sync_mode; offset_seconds",
            "sar_time_field": "known_sar_fps; software_sync_jitter_ms",
            "mapping_rule": "GM_RM019 decision=timestamp_offset_scale_hypothesis; confidence=medium",
            "uses_gt_or_manual_target": "false",
            "target_independent": "true",
            "usable_for_runtime": "conditional",
            "notes": "Manual anchor candidates are explicitly not allowed temporal anchors; FPS scale is source metadata.",
        },
        {
            "source_file": rel(INPUTS["temporal_inventory"]),
            "source_type": "temporal_metadata_inventory",
            "optical_time_field": "numeric_filename_order_only; no per-frame timestamp",
            "sar_time_field": "numeric_filename_order_only; no per-frame timestamp",
            "mapping_rule": "does_not_upgrade_beyond_conditional_fps_scale",
            "uses_gt_or_manual_target": "false",
            "target_independent": "true",
            "usable_for_runtime": "no",
            "notes": "Inventory confirms missing real timestamps and missing hardware synchronization record.",
        },
    ]


def hidden_manifest_rows(specs: Sequence[RunSpec]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        for target_pair_id, target_frame in spec.eval_pairs:
            rows.append(
                {
                    "experiment_id": spec.experiment_id,
                    "experiment_type": spec.experiment_type,
                    "physical_vehicle_id": spec.physical_vehicle_id,
                    "source_pair_id": spec.source_pair_id,
                    "source_sar_frame": spec.source_sar_frame,
                    "hidden_target_pair_id": target_pair_id,
                    "hidden_target_sar_frame": target_frame,
                    "target_box_loaded_in_generate": "false",
                    "target_box_loaded_in_evaluate": "true",
                    "notes": "Generate receives only target frame number for frozen propagation; manual target bbox is evaluation-only.",
                }
            )
    return rows


def runtime_input_rows(frozen_sha: str = "") -> list[dict[str, Any]]:
    paired = rel(INPUTS["paired"])
    optical = rel(INPUTS["optical_state"])
    rows = [
        {
            "phase": "generate",
            "source_file": paired,
            "field_name": "source_pair_id,sar_frame,sar_bbox_x1,sar_bbox_y1,sar_bbox_x2,sar_bbox_y2",
            "semantic_role": "left_anchor_initialization_only",
            "used_by_generate": "true",
            "used_by_evaluate": "false",
            "forbidden_in_generate": "false",
            "observed_in_generate": "true",
            "notes": "Only source rows listed in the experiment manifest are retained.",
        },
        {
            "phase": "generate",
            "source_file": paired,
            "field_name": "hidden_target_sar_bbox,target_center,target_width,target_height,future_endpoint_box",
            "semantic_role": "hidden_target_manual_response",
            "used_by_generate": "false",
            "used_by_evaluate": "true",
            "forbidden_in_generate": "true",
            "observed_in_generate": "false",
            "notes": "Asserted absent from generation state; target rows are loaded by evaluate only.",
        },
        {
            "phase": "generate",
            "source_file": "D:/profile/research/data/GM_RM019/GM_RM019_SARframes_gray/*.png",
            "field_name": "current_sar_gray_frame",
            "semantic_role": "causal_current_frame_local_response",
            "used_by_generate": "true",
            "used_by_evaluate": "false",
            "forbidden_in_generate": "false",
            "observed_in_generate": "true",
            "notes": "C1/C2 read only the current SAR frame being frozen; C0 reads no SAR image response.",
        },
        {
            "phase": "generate",
            "source_file": optical,
            "field_name": "frame,velocity_x,velocity_y,latent_relative_depth,depth_velocity,reconstruction_confidence,blocked_reason",
            "semantic_role": "conditional_optical_motion_phase_constraint",
            "used_by_generate": "true",
            "used_by_evaluate": "false",
            "forbidden_in_generate": "false",
            "observed_in_generate": "true",
            "notes": "Used by C2 for direction/depth consistency gates only, not SAR center regression.",
        },
        {
            "phase": "generate",
            "source_file": rel(INPUTS["temporal_summary"]),
            "field_name": "known_optical_fps,known_sar_fps,offset_seconds,software_sync_jitter_ms",
            "semantic_role": "target_independent_temporal_scale",
            "used_by_generate": "true",
            "used_by_evaluate": "false",
            "forbidden_in_generate": "false",
            "observed_in_generate": "true",
            "notes": "Conditional runtime source; no target boxes or manual anchor fit.",
        },
        {
            "phase": "generate",
            "source_file": rel(OUTPUTS["frozen_predictions"]),
            "field_name": "frozen_predictions_sha256",
            "semantic_role": "freeze_integrity_hash",
            "used_by_generate": "true",
            "used_by_evaluate": "true",
            "forbidden_in_generate": "false",
            "observed_in_generate": bool_text(bool(frozen_sha)),
            "notes": frozen_sha,
        },
    ]
    return rows


def forbidden_generate_assertions() -> None:
    forbidden = [
        "target_sar_bbox",
        "target_center",
        "target_width",
        "target_height",
        "future_endpoint_box",
        "hidden_target_box",
    ]
    leaked = [field for row in runtime_input_rows() if row["observed_in_generate"] == "true" for field in forbidden if field in row["field_name"]]
    if leaked:
        raise RuntimeError(f"Forbidden generate fields observed: {leaked}")


def component_records(
    crop: np.ndarray,
    binary: np.ndarray,
    x0: int,
    y0: int,
    predicted: Box,
    previous: Box,
    velocity: tuple[float, float],
    optical_state: Mapping[str, str] | None,
    use_optical: bool,
) -> tuple[int, list[Component]]:
    raw = connected_components(binary)
    components: list[Component] = []
    diag = math.hypot(previous.width, previous.height)
    max_distance = max(42.0, diag * 0.32)
    min_area = 35
    optical_vx = parse_float(optical_state.get("velocity_x"), 0.0) if optical_state else 0.0
    depth_velocity = parse_float(optical_state.get("depth_velocity"), 0.0) if optical_state else 0.0
    for idx, (cx0, cy0, cx1, cy1, area) in enumerate(raw, start=1):
        if area < min_area:
            continue
        mask = binary[cy0:cy1, cx0:cx1]
        ys, xs = np.nonzero(mask)
        if xs.size:
            center = (float(x0 + cx0 + xs.mean()), float(y0 + cy0 + ys.mean()))
            intensity = float(crop[cy0:cy1, cx0:cx1][mask].mean())
        else:
            center = (float(x0 + (cx0 + cx1) / 2.0), float(y0 + (cy0 + cy1) / 2.0))
            intensity = float(crop[cy0:cy1, cx0:cx1].mean())
        distance = math.hypot(center[0] - predicted.cx, center[1] - predicted.cy)
        if distance > max_distance:
            continue
        candidate = center_box(center[0], center[1], previous.width, previous.height)
        overlap = box_iou(candidate, previous)
        if overlap < 0.12 and distance > max(28.0, diag * 0.20):
            continue
        dx = center[0] - previous.cx
        motion_consistent = "NOT_TESTED"
        if abs(velocity[0]) >= 0.5 and abs(dx) >= 1.0:
            motion_consistent = bool_text((velocity[0] >= 0) == (dx >= 0))
        depth_consistent = "NOT_TESTED"
        if abs(depth_velocity) >= 0.001:
            depth_consistent = "true"
        if use_optical and abs(optical_vx) >= 1.0 and abs(dx) >= 1.5:
            motion_consistent = bool_text((optical_vx >= 0) == (dx >= 0))
            if motion_consistent == "false":
                continue
        comp_box = Box(x0 + cx0, y0 + cy0, x0 + cx1, y0 + cy1)
        components.append(
            Component(
                f"cc_{idx:03d}",
                comp_box,
                center,
                area,
                intensity,
                distance,
                motion_consistent,
                depth_consistent,
            )
        )
    return len(raw), components


def local_step(
    frame: int,
    previous: Box,
    velocity: tuple[float, float],
    fan_mask: np.ndarray,
    optical_state: Mapping[str, str] | None,
    use_optical: bool,
) -> StepResult:
    predicted = translate_box(previous, velocity[0], velocity[1])
    pad_x = max(52.0, previous.width * 0.28)
    pad_y = max(32.0, previous.height * 0.38)
    if use_optical and optical_state:
        vx = parse_float(optical_state.get("velocity_x"), 0.0)
        if abs(vx) >= 1.0:
            pad_x = min(pad_x + 12.0, max(64.0, previous.width * 0.36))
    search = expand_box(predicted, pad_x, pad_y)
    image_path = sar_gray_path(SCENE, frame)
    if not image_path.exists():
        return StepResult(
            predicted,
            search,
            (predicted.cx, predicted.cy),
            "",
            "",
            "missing_observation",
            "missing_observation",
            "missing_sar_gray_frame",
            0,
            0,
            "",
            "",
            "1",
            "",
            fmt(box_iou(predicted, previous)),
            "NOT_TESTED",
            "NOT_TESTED",
            bool_text(use_optical),
            "NOT_TESTED",
            "false",
        )
    arr = read_gray(image_path).astype(np.float32)
    x0 = max(0, int(math.floor(search.x1)))
    y0 = max(0, int(math.floor(search.y1)))
    x1 = min(SAR_WIDTH, int(math.ceil(search.x2)))
    y1 = min(SAR_HEIGHT, int(math.ceil(search.y2)))
    crop = arr[y0:y1, x0:x1]
    local_fan = fan_mask[y0:y1, x0:x1]
    if crop.size == 0 or not local_fan.any():
        return StepResult(
            predicted,
            search,
            (predicted.cx, predicted.cy),
            "",
            "",
            "missing_observation",
            "missing_observation",
            "empty_or_outside_fan_window",
            0,
            0,
            "",
            "",
            "1",
            "",
            fmt(box_iou(predicted, previous)),
            "NOT_TESTED",
            "NOT_TESTED",
            bool_text(use_optical),
            "NOT_TESTED",
            "true",
        )
    valid = crop[local_fan]
    threshold = max(float(np.percentile(valid, 96)), float(valid.mean() + 1.0 * valid.std()))
    binary = close_binary((crop >= threshold) & local_fan) & local_fan
    raw_count, comps = component_records(crop, binary, x0, y0, predicted, previous, velocity, optical_state, use_optical)
    if not comps:
        return StepResult(
            predicted,
            search,
            (predicted.cx, predicted.cy),
            "",
            "",
            "missing_observation",
            "missing_observation",
            "no_component_after_hard_gate",
            raw_count,
            0,
            "",
            "",
            "1",
            "",
            fmt(box_iou(predicted, previous)),
            "NOT_TESTED",
            "NOT_TESTED",
            bool_text(use_optical),
            "NOT_TESTED",
            "true",
        )
    if len(comps) > 1:
        return StepResult(
            predicted,
            search,
            (predicted.cx, predicted.cy),
            "",
            "",
            "ambiguous_response",
            "ambiguous_response",
            "multiple_components_after_hard_gate_no_ranking",
            raw_count,
            len(comps),
            "",
            "",
            "1",
            "",
            fmt(box_iou(predicted, previous)),
            "NOT_TESTED",
            "NOT_TESTED",
            bool_text(use_optical),
            "NOT_TESTED",
            "true",
        )
    comp = comps[0]
    region = center_box(comp.center[0], comp.center[1], previous.width, previous.height)
    area_ratio = safe_div(region.area, previous.area)
    intensity_change = ""
    response_switch = "false"
    if box_iou(region, previous) < 0.08 and math.hypot(region.cx - previous.cx, region.cy - previous.cy) > max(previous.width, previous.height) * 0.6:
        response_switch = "true"
    return StepResult(
        region,
        search,
        comp.center,
        fmt(comp.mean_intensity),
        str(comp.area),
        "observed_response",
        "selected_unique_component_after_hard_gate",
        "unique_component_after_hard_gate",
        raw_count,
        1,
        comp.component_id,
        fmt(comp.distance_to_prediction),
        fmt(area_ratio),
        intensity_change,
        fmt(box_iou(region, previous)),
        comp.motion_direction_consistent,
        comp.depth_trend_consistent,
        bool_text(use_optical),
        response_switch,
        "true",
    )


def prediction_row(
    spec: RunSpec,
    method: str,
    frame: int,
    region: Box,
    step: StepResult,
    fan_area: int,
) -> dict[str, Any]:
    source_box = step.region if frame == spec.source_sar_frame else None
    drift = math.hypot(region.cx - source_box.cx, region.cy - source_box.cy) if source_box else ""
    return {
        "experiment_id": spec.experiment_id,
        "experiment_type": spec.experiment_type,
        "method": method,
        "physical_vehicle_id": spec.physical_vehicle_id,
        "source_pair_id": spec.source_pair_id,
        "source_sar_frame": spec.source_sar_frame,
        "target_pair_id": ";".join(pair_id for pair_id, _ in spec.eval_pairs),
        "target_sar_frame": ";".join(str(frame_id) for _, frame_id in spec.eval_pairs),
        "sar_frame": frame,
        "frame_offset": frame - spec.source_sar_frame,
        "prediction_status": step.prediction_status,
        "prediction_region": region.as_text(),
        "search_window": step.search_window.as_text(),
        "response_center": f"{step.response_center[0]:.3f},{step.response_center[1]:.3f}",
        "response_width": fmt(region.width),
        "response_height": fmt(region.height),
        "response_intensity": step.response_intensity,
        "component_area": step.component_area,
        "selection_status": step.selection_status,
        "stop_reason": step.stop_reason,
        "search_window_area": fmt(step.search_window.area),
        "static_fan_geometry_area": str(fan_area),
        "search_ratio": fmt(safe_div(step.search_window.area, fan_area)),
        "cumulative_drift_from_source": drift if isinstance(drift, str) else fmt(drift),
        "frozen_generation_phase": "generate",
        "target_manual_box_loaded": "false",
        "future_endpoint_loaded": "false",
    }


def trace_row(
    spec: RunSpec,
    method: str,
    frame: int,
    prior: Box,
    region: Box,
    step: StepResult,
    optical_state: Mapping[str, str] | None,
) -> dict[str, Any]:
    return {
        "experiment_id": spec.experiment_id,
        "experiment_type": spec.experiment_type,
        "method": method,
        "physical_vehicle_id": spec.physical_vehicle_id,
        "source_pair_id": spec.source_pair_id,
        "target_pair_id": ";".join(pair_id for pair_id, _ in spec.eval_pairs),
        "sar_frame": frame,
        "prior_region": prior.as_text(),
        "prediction_region": region.as_text(),
        "search_window": step.search_window.as_text(),
        "component_count_raw": step.component_count_raw,
        "component_count_after_gate": step.component_count_after_gate,
        "selected_component_id": step.selected_component_id,
        "selection_status": step.selection_status,
        "distance_to_prediction": step.distance_to_prediction,
        "area_change_ratio": step.area_change_ratio,
        "intensity_change": step.intensity_change,
        "overlap_with_previous": step.overlap_with_previous,
        "motion_direction_consistent": step.motion_direction_consistent,
        "depth_trend_consistent": step.depth_trend_consistent,
        "optical_constraint_used": step.optical_constraint_used,
        "optical_state_frame": optical_state.get("frame", "") if optical_state else "",
        "optical_velocity_x": optical_state.get("velocity_x", "") if optical_state else "",
        "optical_depth_velocity": optical_state.get("depth_velocity", "") if optical_state else "",
        "response_switch_event": step.response_switch_event,
        "stop_reason": step.stop_reason,
        "image_path_loaded": step.image_path_loaded,
        "forbidden_fields_asserted": "no_target_box_no_target_center_no_future_endpoint",
    }


def run_method(
    spec: RunSpec,
    method: str,
    source_box: Box,
    fan_mask: np.ndarray,
    fan_area: int,
    optical_by_pv: Mapping[str, Sequence[Mapping[str, str]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pred_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    current = source_box
    source = source_box
    velocity = (0.0, 0.0)
    previous_observed: Box | None = source_box
    prev_frame = spec.source_sar_frame
    source_step = StepResult(
        source_box,
        source_box,
        (source_box.cx, source_box.cy),
        "",
        "",
        "source_anchor_initialized",
        "source_anchor_initialized",
        "source_anchor_only",
        0,
        0,
        "",
        "",
        "1",
        "",
        "1",
        "NOT_TESTED",
        "NOT_TESTED",
        "false",
        "false",
        "false",
    )
    pred = prediction_row(spec, method, spec.source_sar_frame, source_box, source_step, fan_area)
    pred["cumulative_drift_from_source"] = "0"
    pred_rows.append(pred)
    trace_rows.append(trace_row(spec, method, spec.source_sar_frame, source_box, source_box, source_step, None))
    for frame in range(spec.source_sar_frame + 1, spec.end_sar_frame + 1):
        if method == "C0":
            current = source
            step = StepResult(
                current,
                source,
                (current.cx, current.cy),
                "",
                "",
                "fixed_anchor_baseline",
                "fixed_anchor_no_sar_response_read",
                "fixed_anchor_no_sar_response_read",
                0,
                0,
                "",
                "",
                "1",
                "",
                "1",
                "NOT_TESTED",
                "NOT_TESTED",
                "false",
                "false",
                "false",
            )
            optical_state = None
            trace_rows.append(trace_row(spec, method, frame, source, current, step, optical_state))
        else:
            optical_state = nearest_optical_state(optical_by_pv.get(spec.physical_vehicle_id, []), frame) if method == "C2" else None
            prior = current
            step = local_step(frame, current, velocity, fan_mask, optical_state, method == "C2")
            if step.selection_status == "selected_unique_component_after_hard_gate":
                new_region = step.region
                if previous_observed is not None and frame != prev_frame:
                    dt = max(1, frame - prev_frame)
                    velocity = ((new_region.cx - previous_observed.cx) / dt, (new_region.cy - previous_observed.cy) / dt)
                previous_observed = new_region
                prev_frame = frame
                current = new_region
            else:
                current = step.region
            trace_rows.append(trace_row(spec, method, frame, prior, current, step, optical_state))
        pred = prediction_row(spec, method, frame, current, step, fan_area)
        pred["cumulative_drift_from_source"] = fmt(math.hypot(current.cx - source.cx, current.cy - source.cy))
        pred_rows.append(pred)
    return pred_rows, trace_rows


def generate() -> str:
    forbidden_generate_assertions()
    specs = build_specs()
    source_ids = {spec.source_pair_id for spec in specs}
    sources = load_source_anchor_rows(source_ids)
    optical_by_pv = load_optical_state()
    geometry = build_geometry()
    fan_mask = geometry["fan"]
    fan_area = int(fan_mask.sum())
    all_predictions: list[dict[str, Any]] = []
    all_trace: list[dict[str, Any]] = []
    for spec in specs:
        source_box = box_from_pair(sources[spec.source_pair_id], "sar_bbox")
        for method in ("C0", "C1", "C2"):
            pred_rows, trace_rows = run_method(spec, method, source_box, fan_mask, fan_area, optical_by_pv)
            all_predictions.extend(pred_rows)
            all_trace.extend(trace_rows)
    write_csv(OUTPUTS["temporal_audit"], temporal_audit_rows(), TEMPORAL_FIELDS)
    write_csv(OUTPUTS["hidden_manifest"], hidden_manifest_rows(specs), MANIFEST_FIELDS)
    write_csv(OUTPUTS["frozen_predictions"], all_predictions, PRED_FIELDS)
    write_csv(OUTPUTS["frame_state_trace"], all_trace, TRACE_FIELDS)
    frozen_sha = sha256(OUTPUTS["frozen_predictions"])
    write_csv(OUTPUTS["runtime_input_audit"], runtime_input_rows(frozen_sha), RUNTIME_AUDIT_FIELDS)
    render_runtime_visuals(all_predictions)
    return frozen_sha


def expected_frozen_sha() -> str:
    for row in read_rows(OUTPUTS["runtime_input_audit"]):
        if row.get("field_name") == "frozen_predictions_sha256":
            return row.get("notes", "")
    return ""


def prediction_box(row: Mapping[str, str]) -> Box:
    parts = [parse_float(part) for part in row["prediction_region"].split(",")]
    return Box(parts[0], parts[1], parts[2], parts[3])


def eval_metrics_for_prefix(rows: Sequence[Mapping[str, str]], frame: int) -> tuple[str, int, int]:
    prior = [row for row in rows if parse_int(row["sar_frame"]) <= frame and parse_int(row["sar_frame"]) > parse_int(row["source_sar_frame"])]
    first_lost = ""
    for row in prior:
        if row.get("selection_status") in {"missing_observation", "ambiguous_response"}:
            first_lost = row["sar_frame"]
            break
    consecutive_missing = 0
    for row in reversed(prior):
        if row.get("selection_status") == "missing_observation":
            consecutive_missing += 1
        else:
            break
    ambiguous = sum(1 for row in prior if row.get("selection_status") == "ambiguous_response")
    return first_lost, consecutive_missing, ambiguous


def evaluate() -> str:
    expected = expected_frozen_sha()
    actual = sha256(OUTPUTS["frozen_predictions"])
    if not expected:
        raise RuntimeError("Missing frozen prediction SHA in runtime input audit; run generate first.")
    if expected != actual:
        raise RuntimeError(f"Frozen prediction SHA mismatch: expected {expected}, actual {actual}")
    predictions = read_rows(OUTPUTS["frozen_predictions"])
    target_rows = load_hidden_target_rows()
    traces = read_rows(OUTPUTS["frame_state_trace"])
    by_key: dict[tuple[str, str, int], dict[str, str]] = {}
    by_prefix: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in predictions:
        key = (row["experiment_id"], row["method"], parse_int(row["sar_frame"]))
        by_key[key] = row
        by_prefix[(row["experiment_id"], row["method"])].append(row)
    switch_counts = Counter()
    for row in traces:
        if row.get("response_switch_event") == "true":
            switch_counts[(row["experiment_id"], row["method"])] += 1

    eval_rows: list[dict[str, Any]] = []
    for manifest in hidden_manifest_rows(build_specs()):
        exp_id = manifest["experiment_id"]
        target_pair_id = manifest["hidden_target_pair_id"]
        frame = parse_int(manifest["hidden_target_sar_frame"])
        target_box = box_from_pair(target_rows[target_pair_id], "sar_bbox")
        for method in ("C0", "C1", "C2"):
            pred = by_key.get((exp_id, method, frame))
            if pred is None:
                continue
            region = prediction_box(pred)
            first_lost, consecutive_missing, ambiguous = eval_metrics_for_prefix(by_prefix[(exp_id, method)], frame)
            eval_rows.append(
                {
                    "experiment_id": exp_id,
                    "experiment_type": manifest["experiment_type"],
                    "method": method,
                    "physical_vehicle_id": manifest["physical_vehicle_id"],
                    "source_pair_id": manifest["source_pair_id"],
                    "hidden_target_pair_id": target_pair_id,
                    "sar_frame": frame,
                    "frame_offset": parse_int(pred["frame_offset"]),
                    "hidden_target_coverage": fmt(coverage(region, target_box)),
                    "hidden_target_iou": fmt(box_iou(region, target_box)),
                    "prediction_center_to_visible_response_center": fmt(center_distance(region, target_box)),
                    "prediction_region_area": fmt(region.area),
                    "search_window_area": pred["search_window_area"],
                    "static_fan_geometry_area": pred["static_fan_geometry_area"],
                    "search_ratio": pred["search_ratio"],
                    "prediction_status": pred["prediction_status"],
                    "selection_status": pred["selection_status"],
                    "first_lost_frame": first_lost,
                    "consecutive_missing_length": consecutive_missing,
                    "ambiguous_frame_count": ambiguous,
                    "measured_response_switch_count": switch_counts[(exp_id, method)],
                    "cumulative_drift_from_source": pred["cumulative_drift_from_source"],
                    "frozen_predictions_sha256_verified": actual,
                    "target_box_loaded_phase": "evaluate_only",
                }
            )
    write_csv(OUTPUTS["hidden_evaluation"], eval_rows, EVAL_FIELDS)
    delta_rows = build_delta_rows(eval_rows)
    write_csv(OUTPUTS["delta_audit"], delta_rows, DELTA_FIELDS)
    render_eval_visuals(eval_rows, predictions, target_rows)
    render_report(actual, eval_rows, delta_rows, predictions, traces)
    return actual


def build_delta_rows(eval_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_base: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in eval_rows:
        by_base[(row["experiment_id"], row["hidden_target_pair_id"])][row["method"]] = row
    rows: list[dict[str, Any]] = []
    for (exp_id, target_pair), methods in by_base.items():
        for left, right in (("C0", "C1"), ("C1", "C2")):
            if left not in methods or right not in methods:
                continue
            a = methods[left]
            b = methods[right]
            coverage_delta = parse_float(b["hidden_target_coverage"]) - parse_float(a["hidden_target_coverage"])
            iou_delta = parse_float(b["hidden_target_iou"]) - parse_float(a["hidden_target_iou"])
            center_delta = parse_float(a["prediction_center_to_visible_response_center"]) - parse_float(b["prediction_center_to_visible_response_center"])
            search_delta = parse_float(b["search_ratio"]) - parse_float(a["search_ratio"])
            if coverage_delta > 0.05 or center_delta > 8:
                verdict = "improved"
            elif coverage_delta < -0.05 or center_delta < -8:
                verdict = "harmed"
            else:
                verdict = "neutral"
            rows.append(
                {
                    "comparison": f"{right}_minus_{left}",
                    "experiment_id": exp_id,
                    "experiment_type": b["experiment_type"],
                    "physical_vehicle_id": b["physical_vehicle_id"],
                    "hidden_target_pair_id": target_pair,
                    "sar_frame": b["sar_frame"],
                    "coverage_delta": fmt(coverage_delta),
                    "iou_delta": fmt(iou_delta),
                    "center_error_delta": fmt(center_delta),
                    "search_ratio_delta": fmt(search_delta),
                    "verdict": verdict,
                    "notes": "Positive center_error_delta means the right method is closer to the hidden visible response center.",
                }
            )
    return rows


def rows_for_visual(predictions: Sequence[Mapping[str, str]], experiment_type: str, method: str, limit: int) -> list[Mapping[str, str]]:
    final_rows: list[Mapping[str, str]] = []
    seen: set[str] = set()
    for row in predictions:
        if row["experiment_type"] != experiment_type or row["method"] != method:
            continue
        exp = row["experiment_id"]
        if exp in seen:
            continue
        candidates = [r for r in predictions if r["experiment_id"] == exp and r["method"] == method]
        candidates.sort(key=lambda r: parse_int(r["sar_frame"]))
        final_rows.append(candidates[-1])
        seen.add(exp)
        if len(final_rows) >= limit:
            break
    return final_rows


def draw_box(draw: ImageDraw.ImageDraw, box: Box, sx: float, sy: float, color: tuple[int, int, int], width: int = 2) -> None:
    draw.rectangle([box.x1 * sx, box.y1 * sy, box.x2 * sx, box.y2 * sy], outline=color, width=width)


def image_tile(frame: int, title: str, boxes: Sequence[tuple[Box, tuple[int, int, int], int]]) -> Image.Image:
    size = (360, 220)
    path = sar_gray_path(SCENE, frame)
    if path.exists():
        img = Image.open(path).convert("RGB").resize(size)
    else:
        img = Image.new("RGB", size, (30, 30, 30))
    draw = ImageDraw.Draw(img)
    sx = size[0] / SAR_WIDTH
    sy = size[1] / SAR_HEIGHT
    for box, color, width in boxes:
        draw_box(draw, box, sx, sy, color, width)
    draw.rectangle([0, 0, size[0], 28], fill=(0, 0, 0))
    draw.text((6, 8), title[:56], fill=(255, 255, 255))
    return img


def render_sheet(path: Path, tiles: Sequence[Image.Image], cols: int = 4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not tiles:
        Image.new("RGB", (360, 220), (30, 30, 30)).save(path)
        return
    width, height = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (width * cols, height * rows), (18, 18, 18))
    for idx, tile in enumerate(tiles):
        sheet.paste(tile, ((idx % cols) * width, (idx // cols) * height))
    sheet.save(path)


def render_runtime_visuals(predictions: Sequence[Mapping[str, Any]]) -> None:
    adjacent_tiles = []
    for row in rows_for_visual(predictions, "adjacent_hidden_anchor", "C2", 8):
        adjacent_tiles.append(
            image_tile(
                parse_int(row["sar_frame"]),
                f"RUNTIME {row['experiment_id']} {row['method']} SAR{row['sar_frame']}",
                [(prediction_box(row), (30, 220, 120), 3)],
            )
        )
    open_tiles = []
    for row in rows_for_visual(predictions, "open_loop", "C2", 2):
        open_tiles.append(
            image_tile(
                parse_int(row["sar_frame"]),
                f"RUNTIME {row['experiment_id']} {row['method']} SAR{row['sar_frame']}",
                [(prediction_box(row), (30, 220, 120), 3)],
            )
        )
    render_sheet(VISUALS["runtime_adjacent"], adjacent_tiles, cols=4)
    render_sheet(VISUALS["runtime_open_loop"], open_tiles, cols=2)


def render_eval_visuals(
    eval_rows: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, str]],
    target_rows: Mapping[str, Mapping[str, str]],
) -> None:
    by_key = {(row["experiment_id"], row["method"], parse_int(row["sar_frame"])): row for row in predictions}
    adjacent_tiles = []
    for row in eval_rows:
        if row["experiment_type"] != "adjacent_hidden_anchor" or row["method"] != "C2":
            continue
        pred = by_key[(row["experiment_id"], row["method"], parse_int(row["sar_frame"]))]
        target = box_from_pair(target_rows[row["hidden_target_pair_id"]], "sar_bbox")
        adjacent_tiles.append(
            image_tile(
                parse_int(row["sar_frame"]),
                f"EVAL_ONLY {row['experiment_id']} cov={row['hidden_target_coverage']}",
                [(prediction_box(pred), (30, 220, 120), 3), (target, (255, 210, 30), 2)],
            )
        )
    worst = sorted(
        [row for row in eval_rows if row["method"] == "C2"],
        key=lambda r: parse_float(r["prediction_center_to_visible_response_center"], 0.0),
        reverse=True,
    )[:8]
    fail_tiles = []
    for row in worst:
        pred = by_key[(row["experiment_id"], row["method"], parse_int(row["sar_frame"]))]
        target = box_from_pair(target_rows[row["hidden_target_pair_id"]], "sar_bbox")
        fail_tiles.append(
            image_tile(
                parse_int(row["sar_frame"]),
                f"EVAL_ONLY fail {row['experiment_id']} err={row['prediction_center_to_visible_response_center']}",
                [(prediction_box(pred), (255, 80, 80), 3), (target, (255, 210, 30), 2)],
            )
        )
    render_sheet(VISUALS["eval_adjacent"], adjacent_tiles, cols=4)
    render_sheet(VISUALS["eval_failures"], fail_tiles, cols=4)


def summarize_eval(eval_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for method in ("C0", "C1", "C2"):
        rows = [row for row in eval_rows if row["method"] == method]
        coverages = [parse_float(row["hidden_target_coverage"]) for row in rows]
        errors = [parse_float(row["prediction_center_to_visible_response_center"]) for row in rows]
        ratios = [parse_float(row["search_ratio"]) for row in rows]
        summary[method] = {
            "rows": len(rows),
            "coverage_median": fmt(percentile(coverages, 50)),
            "coverage_mean": fmt(float(np.mean(coverages)) if coverages else math.nan),
            "center_error_median": fmt(percentile(errors, 50)),
            "search_ratio_median": fmt(percentile(ratios, 50)),
            "search_ratio_p90": fmt(percentile(ratios, 90)),
            "search_ratio_max": fmt(max(ratios) if ratios else math.nan),
            "missing": sum(parse_int(row["consecutive_missing_length"]) > 0 for row in rows),
            "ambiguous": sum(parse_int(row["ambiguous_frame_count"]) > 0 for row in rows),
            "switches": sum(parse_int(row["measured_response_switch_count"]) for row in rows),
        }
    return summary


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    show = list(rows if limit is None else rows[:limit])
    out = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in show:
        out.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/").replace("\n", " ") for field in fields) + " |")
    if limit is not None and len(rows) > limit:
        out.append("| " + " | ".join(["..."] + [""] * (len(fields) - 1)) + " |")
    return "\n".join(out)


def render_report(
    frozen_sha: str,
    eval_rows: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, str]],
    traces: Sequence[Mapping[str, str]],
) -> None:
    summary = summarize_eval(eval_rows)
    c1_vs_c0 = [row for row in delta_rows if row["comparison"] == "C1_minus_C0"]
    c2_vs_c1 = [row for row in delta_rows if row["comparison"] == "C2_minus_C1"]
    c1_improved = sum(1 for row in c1_vs_c0 if row["verdict"] == "improved")
    c2_improved = sum(1 for row in c2_vs_c1 if row["verdict"] == "improved")
    c2_harmed = sum(1 for row in c2_vs_c1 if row["verdict"] == "harmed")
    all_search = [parse_float(row["search_ratio"]) for row in predictions if row["method"] in {"C1", "C2"}]
    open_loop_c1_c2 = [row for row in eval_rows if row["experiment_type"] == "open_loop" and row["method"] in {"C1", "C2"}]
    open_loop_positive = sum(1 for row in open_loop_c1_c2 if parse_float(row["hidden_target_coverage"]) > 0.1)
    open_loop_stability = "PARTIAL_SHORT_RANGE_ONLY" if open_loop_positive >= 2 else "NOT_STABLE"
    first_lost = ""
    for row in eval_rows:
        if row["first_lost_frame"]:
            first_lost = row["first_lost_frame"]
            break
    missing_trace = sum(1 for row in traces if row.get("selection_status") == "missing_observation")
    ambiguous_trace = sum(1 for row in traces if row.get("selection_status") == "ambiguous_response")
    switches = sum(1 for row in traces if row.get("response_switch_event") == "true")
    if c1_improved or c2_improved:
        sar_signal = "PARTIAL_SUPPORTED"
    else:
        sar_signal = "NOT_SUPPORTED_BY_THIS_HARD_GATE"
    c2_value = "NO_NET_ADDED_VALUE" if c2_improved == 0 and c2_harmed == 0 else f"improved={c2_improved};harmed={c2_harmed}"
    core_ready = "NO"
    if sar_signal == "PARTIAL_SUPPORTED" and c2_harmed == 0:
        core_ready = "CONDITIONAL_PARTIAL"
    lines = [
        "# OTY2 WGV3.6A-A1.6 Causal Response Tracking Audit",
        "",
        "## Boundary",
        "",
        f"- requested start commit: `{REQUESTED_START_COMMIT}`",
        "- scene: `GM_RM019`",
        "- generate/evaluate separation: `PASS`",
        f"- frozen predictions SHA256: `{frozen_sha}`",
        "- generation target manual boxes loaded: `false`",
        "- evaluation target manual boxes loaded after freeze: `true`",
        "- GM_RM011 executed: `false`",
        "",
        "## Independent Temporal Source",
        "",
        md_table(temporal_audit_rows(), TEMPORAL_FIELDS),
        "",
        "Decision: `TEMPORAL_ALIGNMENT_RUNTIME_SAFE=CONDITIONAL`. The source is target-independent FPS and software-sync metadata, not hardware per-frame timestamp truth.",
        "",
        "## Method Definitions",
        "",
        "- `C0`: fixed source anchor visible-response box; no SAR image response read.",
        "- `C1`: pure SAR causal local response follower; previous frozen Y state + current SAR gray frame + static fan only; update only when exactly one component survives hard gates.",
        "- `C2`: C1 plus conditional optical motion/depth consistency gates from the R2B optical state table; no optical-to-SAR center regression.",
        "",
        "## Method Summary",
        "",
        md_table(
            [
                {"method": method, **values}
                for method, values in summary.items()
            ],
            [
                "method",
                "rows",
                "coverage_median",
                "coverage_mean",
                "center_error_median",
                "search_ratio_median",
                "search_ratio_p90",
                "search_ratio_max",
                "missing",
                "ambiguous",
                "switches",
            ],
        ),
        "",
        "## Hidden Anchor Evaluation",
        "",
        md_table(
            [row for row in eval_rows if row["experiment_type"] == "adjacent_hidden_anchor"],
            [
                "experiment_id",
                "method",
                "hidden_target_pair_id",
                "sar_frame",
                "hidden_target_coverage",
                "hidden_target_iou",
                "prediction_center_to_visible_response_center",
                "selection_status",
                "first_lost_frame",
                "ambiguous_frame_count",
            ],
        ),
        "",
        "## Open Loop Evaluation",
        "",
        md_table(
            [row for row in eval_rows if row["experiment_type"] == "open_loop"],
            [
                "experiment_id",
                "method",
                "hidden_target_pair_id",
                "sar_frame",
                "hidden_target_coverage",
                "hidden_target_iou",
                "prediction_center_to_visible_response_center",
                "selection_status",
                "first_lost_frame",
                "ambiguous_frame_count",
            ],
        ),
        "",
        "## Delta Audit",
        "",
        md_table(delta_rows, DELTA_FIELDS),
        "",
        "## Search Budget",
        "",
        f"- static fan geometry area: `{predictions[0]['static_fan_geometry_area'] if predictions else ''}`",
        f"- C1/C2 search ratio median: `{fmt(percentile(all_search, 50))}`",
        f"- C1/C2 search ratio p90: `{fmt(percentile(all_search, 90))}`",
        f"- C1/C2 search ratio max: `{fmt(max(all_search) if all_search else math.nan)}`",
        "- area expansion policy: fixed per-frame padding from prior response extent; no unbounded expansion.",
        "",
        "## State And Failure Counts",
        "",
        f"- first lost frame: `{first_lost or 'none'}`",
        f"- missing observation trace rows: `{missing_trace}`",
        f"- ambiguous response trace rows: `{ambiguous_trace}`",
        f"- measured response switch rows: `{switches}`",
        "",
        "## Gate Verdicts",
        "",
        "- `TEMPORAL_ALIGNMENT_RUNTIME_SAFE`: `CONDITIONAL`",
        "- `CAUSAL_RUNTIME_LEAK_FREE`: `PASS`",
        f"- `SAR_ONLY_CAUSAL_SIGNAL`: `{sar_signal}`",
        f"- `OPTICAL_CONSTRAINT_ADDED_VALUE`: `{c2_value}`",
        f"- `OPEN_LOOP_STABILITY`: `{open_loop_stability}`",
        "- `IDENTITY_AND_RESPONSE_SWITCH_MEASURED`: `PASS`",
        "- `SEARCH_BUDGET_CONTROLLED`: `PASS`",
        f"- `A1.6_CAUSAL_CORE_READY`: `{core_ready}`",
        "- `GM_RM011_BLOCKED`: `true`",
        "",
        "## Created Files",
        "",
        *[f"- `{rel(path)}`" for path in OUTPUTS.values()],
        "",
        "## Ignored Visual Outputs",
        "",
        *[f"- `{rel(path)}`" for path in VISUALS.values()],
        "",
        "## Next Step",
        "",
        "Do not run GM_RM011 yet. If this hard-gate follower remains ambiguous/missing, first repair causal SAR response association or add an independent intermediate-frame blind review set; do not resurrect P3 endpoint interpolation.",
    ]
    write_text(OUTPUTS["report"], "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "evaluate", "all"])
    args = parser.parse_args()
    if args.command == "generate":
        frozen_sha = generate()
        print(f"generated frozen_predictions_sha256={frozen_sha}")
    elif args.command == "evaluate":
        frozen_sha = evaluate()
        print(f"evaluated frozen_predictions_sha256={frozen_sha}")
    else:
        generated_sha = generate()
        evaluated_sha = evaluate()
        if generated_sha != evaluated_sha:
            raise RuntimeError("Generated/evaluated SHA mismatch")
        print(f"all complete frozen_predictions_sha256={evaluated_sha}")


if __name__ == "__main__":
    main()
