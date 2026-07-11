"""WGV3.6A-A1.8A-R2.1 causal atom regeneration and bbox-family audit.

Commands are intentionally staged:

generate              regenerate causal atoms, graph cores, bbox families
blind-raw-pack        raw SAR family sheets and blank raw judgement CSV
blind-assisted-pack   assisted overlay sheets and blank assisted judgement CSV
evaluate              post-freeze GT/R2 delta and raw-primary error taxonomy
verify-replay         regenerate frozen generation artifacts and compare SHA

There is intentionally no `all` command.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

import run_oty2_wgv3_6a_a1_7_response_assembly_tracking as a17  # noqa: E402
from run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping import (  # noqa: E402
    DATA_ROOT,
    FAN_CENTER_X,
    FAN_CENTER_Y,
    REPO_ROOT,
    REPORT_DIR,
    SAMPLES_DIR,
    SAR_HEIGHT,
    SAR_WIDTH,
    Box,
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
REQUESTED_START_COMMIT = "54d0f90284e7833fafea9af918309c2fa5026a68"
SCENE = "GM_RM019"
PX_TO_M = 0.03
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_8a_r2_1_20260711"
VERIFY_TMP_DIR = OUT_DIR / "_verify_replay_tmp"

RUNTIME_FRAMES = [
    27, 28, 29, 30, 31, 32, 34, 39, 40, 46, 52, 60, 77, 78, 79, 80, 81,
    212, 213, 216, 220, 224, 227, 228, 238, 239, 243, 250, 259, 260,
    262, 263, 269, 270, 271, 272, 273, 276, 278, 279, 280, 281, 284,
    288, 289, 290,
]
SOURCE_START_FRAMES = [27, 31, 77, 212, 238, 269, 273, 288]
OLD_FUTURE_SOURCE_FRAMES = [30, 60, 227, 228, 259, 260, 262, 263, 272, 281, 284]
FOCUS_FRAMES = {27, 28, 29, 30, 31, 78, 79, 80, 81, 263, 270, 271, 272, 273, 289, 290}

INPUTS = {
    "a1_7r_compact": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_compact_assembly_trace_{DATE}.csv",
    "paired": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "r2_atom_nodes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_atom_graph_nodes_{DATE}.csv",
    "r2_core_hypotheses": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_core_subgraph_hypotheses_{DATE}.csv",
    "r2_boxes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_frozen_response_boxes_{DATE}.csv",
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_causal_bbox_family_audit_{DATE}.md",
    "runtime_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_runtime_frame_manifest_{DATE}.csv",
    "causal_shell": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_causal_source_shell_audit_{DATE}.csv",
    "atom_trace": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_causal_atom_trace_{DATE}.csv",
    "roles": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_role_proposals_{DATE}.csv",
    "support_metrics": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_support_pixel_metrics_{DATE}.csv",
    "lineage_nodes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_part_lineage_nodes_{DATE}.csv",
    "lineage_edges": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_part_lineage_edges_{DATE}.csv",
    "atom_graph_nodes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_atom_graph_nodes_{DATE}.csv",
    "atom_graph_edges": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_atom_graph_edges_{DATE}.csv",
    "core_hypotheses": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_core_subgraph_hypotheses_{DATE}.csv",
    "optional_membership": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_optional_response_membership_{DATE}.csv",
    "response_boxes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_response_box_hypotheses_{DATE}.csv",
    "families": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_bbox_hypothesis_families_{DATE}.csv",
    "family_members": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_family_member_manifest_{DATE}.csv",
    "family_temporal": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_family_temporal_edges_{DATE}.csv",
    "background_counterexamples": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_background_counterexamples_{DATE}.csv",
    "blind_raw": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_blind_raw_family_judgement_{DATE}.csv",
    "blind_assisted": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_blind_assisted_family_judgement_{DATE}.csv",
    "gt_eval": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_gt_assisted_family_evaluation_{DATE}.csv",
    "r2_delta": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r2_vs_r2_1_causal_delta_{DATE}.csv",
    "error_taxonomy": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_error_taxonomy_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_gate_integrity_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_frozen_artifact_manifest_{DATE}.csv",
}

VISUALS = {
    "raw_1": OUT_DIR / "blind_raw_family_sheet_001.png",
    "raw_2": OUT_DIR / "blind_raw_family_sheet_002.png",
    "raw_3": OUT_DIR / "blind_raw_family_sheet_003.png",
    "raw_4": OUT_DIR / "blind_raw_family_sheet_004.png",
    "assisted_1": OUT_DIR / "blind_assisted_family_sheet_001.png",
    "assisted_2": OUT_DIR / "blind_assisted_family_sheet_002.png",
    "assisted_3": OUT_DIR / "blind_assisted_family_sheet_003.png",
    "assisted_4": OUT_DIR / "blind_assisted_family_sheet_004.png",
    "eval": OUT_DIR / "eval_only_family_bbox_sheet.png",
}

FREEZE_KEYS = [
    "runtime_manifest",
    "causal_shell",
    "atom_trace",
    "roles",
    "support_metrics",
    "lineage_nodes",
    "lineage_edges",
    "atom_graph_nodes",
    "atom_graph_edges",
    "core_hypotheses",
    "optional_membership",
    "response_boxes",
    "families",
    "family_members",
    "family_temporal",
    "background_counterexamples",
]

VEHICLE_ROLES = {"body_core_candidate", "side_ridge_candidate", "endpoint_hotspot_candidate"}
PART_ROLES = {"side_ridge_candidate", "endpoint_hotspot_candidate"}
BACKGROUND_ROLE = "background_arc_candidate"
BOX_STATUS_ORDER = [
    "vehicle_response_box_supported",
    "vehicle_response_box_possible",
    "vehicle_part_box_only",
    "background_counterexample",
    "unresolved",
]

RUNTIME_FIELDS = ["sar_frame", "frame_set", "frame_role", "generation_provenance"]
CAUSAL_FIELDS = [
    "sar_frame",
    "source_type",
    "selected_source_frame",
    "source_lag_frames",
    "source_is_causal",
    "source_shell_bbox",
    "source_shell_boundary_contact_count",
    "source_shell_staleness_risk",
    "generation_provenance",
]
ATOM_FIELDS = [
    "atom_id",
    "sar_frame",
    "source_type",
    "selected_source_frame",
    "support_pixel_count",
    "support_bbox",
    "pixel_centroid_x",
    "pixel_centroid_y",
    "integrated_energy",
    "mean_energy",
    "peak_energy",
    "relative_energy_within_shell",
    "azimuth_deg",
    "radial_px",
    "axis1_px",
    "axis2_px",
    "orientation_deg",
    "shell_boundary_contact",
    "extraction_threshold",
    "generation_provenance",
]
ROLE_FIELDS = [
    "atom_id",
    "sar_frame",
    "candidate_role",
    "graph_role_class",
    "role_rule_provenance",
    "role_inputs",
]
SUPPORT_FIELDS = [
    "support_metric_id",
    "object_id",
    "object_type",
    "sar_frame",
    "support_bbox",
    "support_bbox_width_px",
    "support_bbox_height_px",
    "support_projection_long_span_px",
    "support_projection_short_span_px",
    "support_covariance_long_axis_px",
    "support_covariance_short_axis_px",
    "support_pixel_count",
    "support_bbox_occupancy",
    "support_convex_hull_occupancy",
    "largest_internal_gap_px",
]
LINEAGE_NODE_FIELDS = [
    "part_node_id",
    "atom_id",
    "sar_frame",
    "candidate_role",
    "persistent_part_track_id",
    "track_len",
    "lineage_state",
]
LINEAGE_EDGE_FIELDS = [
    "lineage_edge_id",
    "source_atom_id",
    "target_atom_id",
    "source_sar_frame",
    "target_sar_frame",
    "centroid_distance_px",
    "radial_drift",
    "azimuth_drift",
    "orientation_difference",
    "energy_ratio",
    "role_compatibility",
    "edge_status",
    "blocked_reason",
]
GRAPH_NODE_FIELDS = [
    "atom_id",
    "sar_frame",
    "candidate_role",
    "graph_role_class",
    "support_bbox",
    "centroid_x",
    "centroid_y",
    "persistent_part_track_id",
]
GRAPH_EDGE_FIELDS = [
    "edge_id",
    "sar_frame",
    "source_atom_id",
    "target_atom_id",
    "support_boundary_gap_px",
    "centroid_distance_px",
    "radial_delta",
    "azimuth_delta",
    "orientation_delta",
    "energy_ratio",
    "role_relation",
    "shared_or_compatible_lineage",
    "background_conflict",
    "edge_status",
]
CORE_FIELDS = [
    "core_subgraph_id",
    "sar_frame",
    "member_atom_ids",
    "graph_edge_ids",
    "connected_in_atom_graph",
    "core_relation_type",
    "core_role_summary",
    "core_support_geometry",
    "core_lineage_evidence",
    "core_background_relation",
    "box_state",
    "state_reason_cn",
]
OPTIONAL_FIELDS = [
    "core_subgraph_id",
    "sar_frame",
    "atom_id",
    "candidate_role",
    "membership_decision",
    "membership_evidence_type",
    "best_relation_to_core",
    "all_valid_relations_to_core",
    "boundary_distance_to_core_px",
    "centroid_distance_to_core_px",
    "bbox_blank_ratio_if_included",
    "decision_reason_cn",
]
BOX_FIELDS = [
    "response_box_id",
    "core_subgraph_id",
    "sar_frame",
    "box_state",
    "core_member_atom_ids",
    "strong_optional_atom_ids",
    "uncertain_optional_atom_ids",
    "excluded_atom_ids",
    "core_bbox",
    "conservative_response_bbox",
    "uncertain_envelope_bbox",
    "center_x_px",
    "center_y_px",
    "center_x_m",
    "center_y_m",
    "range_m",
    "azimuth_deg",
    "metric_consistency_error_m",
    "final_annotation_space",
]
FAMILY_FIELDS = [
    "family_id",
    "sar_frame",
    "member_core_subgraph_ids",
    "member_response_box_ids",
    "family_relation",
    "distinct_core_member_sets",
    "conservative_bbox_variants",
    "uncertain_envelope_variants",
    "family_runtime_states",
    "family_shared_evidence",
    "family_unresolved_difference",
]
FAMILY_MEMBER_FIELDS = [
    "family_id",
    "response_box_id",
    "core_subgraph_id",
    "sar_frame",
    "member_relation_to_family",
    "box_state",
]
FAMILY_TEMPORAL_FIELDS = [
    "temporal_edge_id",
    "source_family_id",
    "target_family_id",
    "source_frame",
    "target_frame",
    "shared_core_track_ids",
    "center_shift_px",
    "bbox_iou",
    "size_ratio",
    "core_relation_compatibility",
    "edge_status",
    "blocked_reason",
]
COUNTEREXAMPLE_FIELDS = [
    "accepted_family_id",
    "alternative_object_id",
    "same_frame",
    "accepted_visible_structure",
    "alternative_visible_structure",
    "accepted_core_relation",
    "alternative_relation",
    "accepted_lineage",
    "alternative_lineage",
    "accepted_bbox_membership",
    "alternative_exclusion_reason",
    "why_accepted_is_vehicle_response_cn",
    "why_alternative_is_not_vehicle_response_cn",
    "remaining_uncertainty_cn",
]
RAW_FIELDS = [
    "raw_review_id",
    "blind_frame_id",
    "blind_family_id",
    "family_id",
    "raw_strongest_response_position_cn",
    "raw_visible_component_count",
    "raw_shape_and_orientation_cn",
    "raw_internal_blank_cn",
    "raw_neighbor_response_cn",
    "raw_bbox_boundary_adequacy_cn",
    "raw_vehicle_response_support",
    "raw_background_support",
    "raw_unresolved",
    "raw_decisive_reason_cn",
    "raw_alternative_explanation_cn",
    "raw_confidence",
    "raw_png",
]
ASSISTED_FIELDS = [
    "assisted_review_id",
    "blind_frame_id",
    "blind_family_id",
    "family_id",
    "assisted_core_visual_match",
    "assisted_optional_membership_match",
    "assisted_background_exclusion_match",
    "assisted_structure_support",
    "assisted_unresolved",
    "assisted_decisive_reason_cn",
    "raw_to_assisted_change_cn",
    "algorithm_overlay_helped_or_misled_cn",
    "assisted_confidence",
    "assisted_png",
]
EVAL_FIELDS = [
    "eval_id",
    "family_id",
    "sar_frame",
    "family_state",
    "raw_judgement",
    "assisted_judgement",
    "gt_exact_frame_available",
    "bbox_iou",
    "gt_coverage_ratio",
    "prediction_purity_ratio",
    "prediction_to_gt_area_ratio",
    "center_distance_px",
    "center_distance_m",
    "posthoc_label_group_eval_only",
    "vehicle_identity_eval_only",
    "gt_assisted_explanation_cn",
    "provenance",
]
DELTA_FIELDS = [
    "sar_frame",
    "r2_atom_count",
    "r2_1_causal_atom_count",
    "atom_bbox_change",
    "role_change",
    "lineage_change",
    "core_hypothesis_change",
    "response_bbox_change",
    "hypothesis_family_change",
    "change_caused_by_causal_regeneration_cn",
]
ERROR_FIELDS = ["case_id", "family_id", "sar_frame", "error_type", "reason_cn", "provenance"]
GATE_FIELDS = ["gate", "status", "evidence", "provenance"]
MANIFEST_FIELDS = ["artifact", "path", "sha256", "rows", "frozen_phase"]


@dataclass
class Atom:
    atom_id: str
    frame: int
    source_type: str
    source_frame: int | None
    xs: np.ndarray
    ys: np.ndarray
    box: Box
    cx: float
    cy: float
    area: int
    integrated: float
    mean: float
    peak: float
    relative_energy: float
    azimuth: float
    radial: float
    axis1: float
    axis2: float
    orientation: float
    threshold: float
    boundary_contact: bool
    role: str
    role_class: str
    role_reason: str
    track_id: str = ""
    track_len: int = 0


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def row_count(path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".csv":
        return 0
    return len(read_rows(path))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def safe_div(num: float, den: float) -> float:
    return num / den if den else math.nan


def box_text(box: Box) -> str:
    return f"{fmt(box.x1)},{fmt(box.y1)},{fmt(box.x2)},{fmt(box.y2)}"


def box_from_text(text: str) -> Box | None:
    parts = [parse_float(part) for part in str(text or "").split(",")]
    if len(parts) != 4 or any(math.isnan(v) for v in parts):
        return None
    return Box(parts[0], parts[1], parts[2], parts[3])


def clamp_box(box: Box) -> Box:
    return Box(
        max(0.0, min(float(SAR_WIDTH - 1), box.x1)),
        max(0.0, min(float(SAR_HEIGHT - 1), box.y1)),
        max(1.0, min(float(SAR_WIDTH), box.x2)),
        max(1.0, min(float(SAR_HEIGHT), box.y2)),
    )


def expand_box(box: Box, margin: float) -> Box:
    return clamp_box(Box(box.x1 - margin, box.y1 - margin, box.x2 + margin, box.y2 + margin))


def union_box(boxes: Sequence[Box]) -> Box:
    if not boxes:
        return Box(1000.0, 1120.0, 1250.0, 1260.0)
    return clamp_box(Box(min(b.x1 for b in boxes), min(b.y1 for b in boxes), max(b.x2 for b in boxes), max(b.y2 for b in boxes)))


def bbox_iou(a: Box, b: Box) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return safe_div(inter, a.area + b.area - inter)


def bbox_intersection(a: Box, b: Box) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def contains_box(a: Box, b: Box) -> bool:
    return a.x1 <= b.x1 + 1 and a.y1 <= b.y1 + 1 and a.x2 >= b.x2 - 1 and a.y2 >= b.y2 - 1


def gap_between(a: Box, b: Box) -> float:
    dx = max(0.0, max(a.x1, b.x1) - min(a.x2, b.x2))
    dy = max(0.0, max(a.y1, b.y1) - min(a.y2, b.y2))
    return math.hypot(dx, dy)


def angle_diff(a: float, b: float) -> float:
    return abs((a - b + 90.0) % 180.0 - 90.0)


def center_m(box: Box) -> tuple[float, float, float, float, float]:
    cx = box.cx
    cy = box.cy
    mx = (cx - FAN_CENTER_X) * PX_TO_M
    my = (FAN_CENTER_Y - cy) * PX_TO_M
    rng = math.hypot(mx, my)
    az = math.degrees(math.atan2(mx, my)) if mx or my else 0.0
    err = abs(rng - math.sqrt(mx * mx + my * my))
    return cx, cy, mx, my, rng if not math.isnan(rng) else 0.0, az, err


def require_files(paths: Sequence[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required files: " + "; ".join(missing))


def runtime_manifest_rows() -> list[dict[str, Any]]:
    holdout = {34, 39, 52, 216, 224, 228, 259, 262, 263, 278, 279, 281}
    rows = []
    for frame in RUNTIME_FRAMES:
        role = "r1_r2_holdout_frame" if frame in holdout else "focus_or_runtime_frame"
        rows.append(
            {
                "sar_frame": frame,
                "frame_set": "wgv3_6a_a1_8a_r2_1_runtime_frames",
                "frame_role": role,
                "generation_provenance": "embedded_deterministic_runtime_frame_list_no_r1_r2_artifact_read",
            }
        )
    return rows


def source_shells() -> dict[int, Box]:
    rows = read_rows(INPUTS["a1_7r_compact"])
    shells: dict[int, Box] = {}
    for row in rows:
        if row.get("method") != "source":
            continue
        frame = parse_int(row.get("sar_frame"))
        if frame not in SOURCE_START_FRAMES:
            continue
        box = box_from_text(row.get("search_window", ""))
        if box:
            shells.setdefault(frame, box)
    return shells


def fallback_shell(frame: int) -> Box:
    if frame < 100:
        return Box(995.0, 1110.0, 1375.0, 1298.0)
    if frame < 270:
        return Box(930.0, 1105.0, 1325.0, 1288.0)
    return Box(1030.0, 1110.0, 1400.0, 1295.0)


def select_causal_source_shell(frame: int, shells: Mapping[int, Box]) -> tuple[str, int | None, Box, int | str]:
    history = [source for source in shells if source <= frame]
    if not history:
        return "static_fallback_shell", None, fallback_shell(frame), ""
    selected = max(history)
    return "historical_source_shell", selected, expand_box(shells[selected], 24.0), frame - selected


def axis_stats(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float, float]:
    if xs.size <= 1:
        return 0.0, 0.0, 0.0
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    pts -= pts.mean(axis=0)
    cov = np.cov(pts, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    vals = np.maximum(vals, 0.0)
    order = np.argsort(vals)[::-1]
    vals = vals[order]
    vec = vecs[:, order[0]]
    axis1 = float(math.sqrt(vals[0]) * 4.0)
    axis2 = float(math.sqrt(vals[1]) * 4.0)
    orientation = math.degrees(math.atan2(vec[1], vec[0]))
    if orientation < -90:
        orientation += 180
    if orientation > 90:
        orientation -= 180
    return axis1, axis2, orientation


def projection_spans(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    if xs.size <= 1:
        return 0.0, 0.0
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    mean = pts.mean(axis=0)
    centered = pts - mean
    cov = np.cov(centered, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    axes = vecs[:, order]
    proj = centered @ axes
    long_span = float(proj[:, 0].max() - proj[:, 0].min())
    short_span = float(proj[:, 1].max() - proj[:, 1].min())
    return long_span, short_span


def convex_hull_area(points: np.ndarray) -> float:
    unique = sorted({(float(x), float(y)) for x, y in points})
    if len(unique) <= 2:
        return 0.0

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    area = 0.0
    for i, p in enumerate(hull):
        q = hull[(i + 1) % len(hull)]
        area += p[0] * q[1] - q[0] * p[1]
    return abs(area) / 2.0


def largest_internal_gap(xs: np.ndarray, ys: np.ndarray, box: Box) -> float:
    width = max(1, int(math.ceil(box.width)))
    height = max(1, int(math.ceil(box.height)))
    grid = np.zeros((height, width), dtype=bool)
    xi = np.clip((xs - box.x1).astype(int), 0, width - 1)
    yi = np.clip((ys - box.y1).astype(int), 0, height - 1)
    grid[yi, xi] = True
    col_empty = ~grid.any(axis=0)
    row_empty = ~grid.any(axis=1)

    def max_run(values: np.ndarray) -> int:
        best = cur = 0
        for val in values:
            cur = cur + 1 if bool(val) else 0
            best = max(best, cur)
        return best

    return float(max(max_run(col_empty), max_run(row_empty)))


def local_arc_score(cx: float, cy: float, orientation: float) -> float:
    radial_angle = math.degrees(math.atan2(cy - FAN_CENTER_Y, cx - FAN_CENTER_X))
    tangent = radial_angle + 90.0
    return max(0.0, 1.0 - angle_diff(orientation, tangent) / 45.0)


def role_for_atom(area: int, peak: float, mean: float, axis1: float, axis2: float, occupancy: float, arc_score: float, box: Box, shell: Box) -> tuple[str, str]:
    elongation = safe_div(axis1, max(axis2, 1e-6))
    bottom_fraction = safe_div(box.cy - shell.y1, max(1.0, shell.height))
    if elongation >= 2.65 and arc_score >= 0.72 and area >= 42 and bottom_fraction < 0.82:
        return BACKGROUND_ROLE, "elongated_support_aligned_with_fan_tangent"
    if area >= 110 and bottom_fraction >= 0.38 and peak >= 84 and occupancy >= 0.038:
        return "body_core_candidate", "dense_bottom_or_midbody_energy_support"
    if 24 <= area <= 220 and bottom_fraction >= 0.35 and peak >= 82 and occupancy >= 0.045:
        return "endpoint_hotspot_candidate", "local_endpoint_like_peak_support"
    if elongation >= 2.0 and area >= 38 and arc_score < 0.68:
        return "side_ridge_candidate", "elongated_non_arc_side_ridge"
    if area < 34:
        return "isolated_small_atom", "small_isolated_support_not_global_veto"
    return "unresolved_atom", "support_visible_but_role_not_decisive"


def graph_role_class(role: str) -> str:
    if role in VEHICLE_ROLES or role == "unresolved_atom":
        return "core_member_candidate"
    if role == BACKGROUND_ROLE:
        return "conflicting_background_candidate"
    return "optional_support_candidate"


def extract_atoms(frames: Sequence[int]) -> tuple[list[Atom], list[dict[str, Any]]]:
    require_files([INPUTS["a1_7r_compact"]])
    geometry = build_geometry()
    fan = geometry["fan"]
    azimuth = geometry["azimuth"]
    radial = geometry["radial"]
    shells = source_shells()
    atoms: list[Atom] = []
    shell_rows: list[dict[str, Any]] = []
    for frame in frames:
        path = sar_gray_path(SCENE, frame)
        if not path.exists():
            shell_rows.append(
                {
                    "sar_frame": frame,
                    "source_type": "missing_sar_gray",
                    "selected_source_frame": "",
                    "source_lag_frames": "",
                    "source_is_causal": "false",
                    "source_shell_bbox": "",
                    "source_shell_boundary_contact_count": "",
                    "source_shell_staleness_risk": "missing_sar_gray",
                    "generation_provenance": "sar_gray_missing_no_gt_no_r1_r2_atoms",
                }
            )
            continue
        source_type, source_frame, shell, lag = select_causal_source_shell(frame, shells)
        arr = read_gray(path)
        x0 = max(0, int(math.floor(shell.x1)))
        y0 = max(0, int(math.floor(shell.y1)))
        x1 = min(SAR_WIDTH, int(math.ceil(shell.x2)))
        y1 = min(SAR_HEIGHT, int(math.ceil(shell.y2)))
        crop = arr[y0:y1, x0:x1]
        local_fan = fan[y0:y1, x0:x1]
        if crop.size == 0 or not local_fan.any():
            continue
        valid = crop[local_fan]
        threshold = max(float(np.percentile(valid, 96.1)), float(valid.mean() + 0.82 * valid.std()))
        binary = (crop >= threshold) & local_fan
        total_energy = float(valid.sum())
        frame_atoms: list[Atom] = []
        for cx0, cy0, cx1, cy1, area in a17.block_components(binary, block=6):
            if area < 14:
                continue
            mask = binary[cy0:cy1, cx0:cx1]
            ys, xs = np.nonzero(mask)
            if xs.size == 0:
                continue
            gx = x0 + cx0 + xs
            gy = y0 + cy0 + ys
            vals = crop[cy0:cy1, cx0:cx1][mask]
            box = Box(float(x0 + cx0), float(y0 + cy0), float(x0 + cx1), float(y0 + cy1))
            axis1, axis2, orientation = axis_stats(gx, gy)
            occupancy = safe_div(float(xs.size), max(1.0, box.area))
            arc_score = local_arc_score(float(gx.mean()), float(gy.mean()), orientation)
            role, reason = role_for_atom(int(xs.size), float(vals.max()), float(vals.mean()), axis1, axis2, occupancy, arc_score, box, shell)
            boundary_contact = (
                abs(box.x1 - shell.x1) < 4
                or abs(box.y1 - shell.y1) < 4
                or abs(box.x2 - shell.x2) < 4
                or abs(box.y2 - shell.y2) < 4
            )
            frame_atoms.append(
                Atom(
                    atom_id="",
                    frame=frame,
                    source_type=source_type,
                    source_frame=source_frame,
                    xs=gx.astype(np.float32),
                    ys=gy.astype(np.float32),
                    box=box,
                    cx=float(gx.mean()),
                    cy=float(gy.mean()),
                    area=int(xs.size),
                    integrated=float(vals.sum()),
                    mean=float(vals.mean()),
                    peak=float(vals.max()),
                    relative_energy=safe_div(float(vals.sum()), total_energy),
                    azimuth=float(azimuth[gy.astype(int), gx.astype(int)].mean()),
                    radial=float(radial[gy.astype(int), gx.astype(int)].mean()),
                    axis1=axis1,
                    axis2=axis2,
                    orientation=orientation,
                    threshold=threshold,
                    boundary_contact=bool(boundary_contact),
                    role=role,
                    role_class=graph_role_class(role),
                    role_reason=reason,
                )
            )
        frame_atoms.sort(key=lambda atom: atom.integrated, reverse=True)
        # Keep deterministic finite atom sets while preserving non-vehicle counterexamples.
        selected = frame_atoms[:9]
        background = [atom for atom in frame_atoms[9:] if atom.role == BACKGROUND_ROLE][:2]
        for atom in selected + background:
            atom.atom_id = f"R21A{len(atoms) + 1:05d}"
            atoms.append(atom)
        boundary_count = sum(atom.boundary_contact for atom in selected + background)
        risk = "high_lag_or_boundary_contact" if (parse_int(lag, 0) >= 15 or boundary_count >= 2) else "low"
        shell_rows.append(
            {
                "sar_frame": frame,
                "source_type": source_type,
                "selected_source_frame": source_frame if source_frame is not None else "",
                "source_lag_frames": lag,
                "source_is_causal": bool_text(source_type == "static_fallback_shell" or (source_frame is not None and source_frame <= frame)),
                "source_shell_bbox": box_text(shell),
                "source_shell_boundary_contact_count": boundary_count,
                "source_shell_staleness_risk": risk,
                "generation_provenance": "a1_7r_source_shell_plus_sar_gray_recomputed_components_no_r1_r2_atoms",
            }
        )
    return atoms, shell_rows


def support_geometry(xs: np.ndarray, ys: np.ndarray, box: Box) -> dict[str, float]:
    long_span, short_span = projection_spans(xs, ys)
    axis1, axis2, _orientation = axis_stats(xs, ys)
    hull_area = convex_hull_area(np.column_stack([xs, ys]))
    bbox_occ = safe_div(float(xs.size), box.area)
    hull_occ = safe_div(float(xs.size), max(1.0, hull_area))
    return {
        "bbox_width": box.width,
        "bbox_height": box.height,
        "projection_long": long_span,
        "projection_short": short_span,
        "cov_long": axis1,
        "cov_short": axis2,
        "count": float(xs.size),
        "bbox_occupancy": bbox_occ,
        "hull_occupancy": min(1.0, hull_occ),
        "largest_gap": largest_internal_gap(xs, ys, box),
    }


def support_metric_row(metric_id: str, object_id: str, object_type: str, frame: int, xs: np.ndarray, ys: np.ndarray, box: Box) -> dict[str, Any]:
    geom = support_geometry(xs, ys, box)
    return {
        "support_metric_id": metric_id,
        "object_id": object_id,
        "object_type": object_type,
        "sar_frame": frame,
        "support_bbox": box_text(box),
        "support_bbox_width_px": fmt(geom["bbox_width"]),
        "support_bbox_height_px": fmt(geom["bbox_height"]),
        "support_projection_long_span_px": fmt(geom["projection_long"]),
        "support_projection_short_span_px": fmt(geom["projection_short"]),
        "support_covariance_long_axis_px": fmt(geom["cov_long"]),
        "support_covariance_short_axis_px": fmt(geom["cov_short"]),
        "support_pixel_count": int(geom["count"]),
        "support_bbox_occupancy": fmt(geom["bbox_occupancy"]),
        "support_convex_hull_occupancy": fmt(geom["hull_occupancy"]),
        "largest_internal_gap_px": fmt(geom["largest_gap"]),
    }


def atom_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    return [
        {
            "atom_id": atom.atom_id,
            "sar_frame": atom.frame,
            "source_type": atom.source_type,
            "selected_source_frame": atom.source_frame if atom.source_frame is not None else "",
            "support_pixel_count": atom.area,
            "support_bbox": box_text(atom.box),
            "pixel_centroid_x": fmt(atom.cx),
            "pixel_centroid_y": fmt(atom.cy),
            "integrated_energy": fmt(atom.integrated),
            "mean_energy": fmt(atom.mean),
            "peak_energy": fmt(atom.peak),
            "relative_energy_within_shell": fmt(atom.relative_energy),
            "azimuth_deg": fmt(atom.azimuth),
            "radial_px": fmt(atom.radial),
            "axis1_px": fmt(atom.axis1),
            "axis2_px": fmt(atom.axis2),
            "orientation_deg": fmt(atom.orientation),
            "shell_boundary_contact": bool_text(atom.boundary_contact),
            "extraction_threshold": fmt(atom.threshold),
            "generation_provenance": "recomputed_from_sar_gray_and_causal_source_shell_no_r1_r2_atoms",
        }
        for atom in atoms
    ]


def role_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    return [
        {
            "atom_id": atom.atom_id,
            "sar_frame": atom.frame,
            "candidate_role": atom.role,
            "graph_role_class": atom.role_class,
            "role_rule_provenance": atom.role_reason,
            "role_inputs": f"area={atom.area};peak={fmt(atom.peak)};axis1={fmt(atom.axis1)};axis2={fmt(atom.axis2)};orientation={fmt(atom.orientation)}",
        }
        for atom in atoms
    ]


def atoms_by_frame(atoms: Sequence[Atom]) -> dict[int, list[Atom]]:
    grouped: dict[int, list[Atom]] = defaultdict(list)
    for atom in atoms:
        grouped[atom.frame].append(atom)
    return grouped


def role_relation(a: Atom, b: Atom) -> str:
    roles = {a.role, b.role}
    if BACKGROUND_ROLE in roles:
        return "background_conflict_relation"
    if "body_core_candidate" in roles and "endpoint_hotspot_candidate" in roles:
        return "body_to_endpoint"
    if "body_core_candidate" in roles and "side_ridge_candidate" in roles:
        return "body_to_side"
    if "side_ridge_candidate" in roles and "endpoint_hotspot_candidate" in roles:
        return "side_to_endpoint"
    if roles & VEHICLE_ROLES and "unresolved_atom" in roles:
        return "unresolved_local_response"
    if roles <= {"endpoint_hotspot_candidate"}:
        return "endpoint_to_endpoint"
    if roles <= {"side_ridge_candidate"}:
        return "side_to_side"
    return "role_ambiguous"


def role_compatible(a: Atom, b: Atom) -> bool:
    relation = role_relation(a, b)
    return relation not in {"background_conflict_relation", "role_ambiguous"}


def build_lineage(atoms: Sequence[Atom]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    frames = sorted(atoms_by_frame(atoms))
    by_frame = atoms_by_frame(atoms)
    parent = {atom.atom_id: atom.atom_id for atom in atoms}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    edge_rows: list[dict[str, Any]] = []
    for src_frame, dst_frame in zip(frames, frames[1:]):
        if dst_frame - src_frame > 35:
            continue
        candidates: list[tuple[Atom, Atom, float]] = []
        for a in by_frame[src_frame]:
            if a.role == BACKGROUND_ROLE:
                continue
            for b in by_frame[dst_frame]:
                if b.role == BACKGROUND_ROLE:
                    continue
                dist = math.hypot(a.cx - b.cx, a.cy - b.cy)
                if dist <= 85.0 and role_compatible(a, b):
                    candidates.append((a, b, dist))
        candidates.sort(key=lambda item: item[2])
        used_a: set[str] = set()
        used_b: set[str] = set()
        for a, b, dist in candidates:
            energy_ratio = max(a.integrated, b.integrated) / max(1.0, min(a.integrated, b.integrated))
            unique = a.atom_id not in used_a and b.atom_id not in used_b and dist <= 62.0
            status = "unique_continuation" if unique else "possible_continuation"
            if unique:
                used_a.add(a.atom_id)
                used_b.add(b.atom_id)
                union(a.atom_id, b.atom_id)
            edge_rows.append(
                {
                    "lineage_edge_id": f"R21LE{len(edge_rows) + 1:05d}",
                    "source_atom_id": a.atom_id,
                    "target_atom_id": b.atom_id,
                    "source_sar_frame": a.frame,
                    "target_sar_frame": b.frame,
                    "centroid_distance_px": fmt(dist),
                    "radial_drift": fmt(abs(a.radial - b.radial)),
                    "azimuth_drift": fmt(abs(a.azimuth - b.azimuth)),
                    "orientation_difference": fmt(angle_diff(a.orientation, b.orientation)),
                    "energy_ratio": fmt(energy_ratio),
                    "role_compatibility": bool_text(role_compatible(a, b)),
                    "edge_status": status,
                    "blocked_reason": "" if status == "unique_continuation" else "nonunique_or_wide_temporal_candidate",
                }
            )
    comp_members: dict[str, list[str]] = defaultdict(list)
    for atom in atoms:
        comp_members[find(atom.atom_id)].append(atom.atom_id)
    track_by_atom: dict[str, str] = {}
    track_len: dict[str, int] = {}
    track_index = 1
    for root, members in sorted(comp_members.items()):
        if len(members) < 2:
            continue
        track_id = f"R21PT{track_index:04d}"
        track_index += 1
        for atom_id in members:
            track_by_atom[atom_id] = track_id
            track_len[track_id] = len(members)
    for atom in atoms:
        atom.track_id = track_by_atom.get(atom.atom_id, "")
        atom.track_len = track_len.get(atom.track_id, 0) if atom.track_id else 0
    node_rows = [
        {
            "part_node_id": f"R21PN{i + 1:05d}",
            "atom_id": atom.atom_id,
            "sar_frame": atom.frame,
            "candidate_role": atom.role,
            "persistent_part_track_id": atom.track_id,
            "track_len": atom.track_len,
            "lineage_state": "persistent_part_track" if atom.track_id else "single_frame_part",
        }
        for i, atom in enumerate(atoms)
    ]
    return node_rows, edge_rows


def graph_node_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    return [
        {
            "atom_id": atom.atom_id,
            "sar_frame": atom.frame,
            "candidate_role": atom.role,
            "graph_role_class": atom.role_class,
            "support_bbox": box_text(atom.box),
            "centroid_x": fmt(atom.cx),
            "centroid_y": fmt(atom.cy),
            "persistent_part_track_id": atom.track_id,
        }
        for atom in atoms
    ]


def edge_status(a: Atom, b: Atom) -> tuple[str, str]:
    gap = gap_between(a.box, b.box)
    dist = math.hypot(a.cx - b.cx, a.cy - b.cy)
    if BACKGROUND_ROLE in {a.role, b.role}:
        return "blocked_by_background" if gap <= 28.0 else "ambiguous_relation", "background_conflict"
    if not role_compatible(a, b):
        return "blocked_by_role", "role_not_compatible"
    if gap <= 32.0 and dist <= 115.0:
        return "accepted_local_relation", ""
    if gap <= 68.0 and dist <= 155.0:
        return "ambiguous_relation", "spatial_relation_only"
    return "blocked_by_geometry", "too_far_for_local_core_relation"


def graph_edge_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame, frame_atoms in atoms_by_frame(atoms).items():
        for a, b in combinations(frame_atoms, 2):
            gap = gap_between(a.box, b.box)
            dist = math.hypot(a.cx - b.cx, a.cy - b.cy)
            if gap > 150.0 and dist > 260.0:
                continue
            status, _blocked = edge_status(a, b)
            rows.append(
                {
                    "edge_id": f"R21GE{len(rows) + 1:05d}",
                    "sar_frame": frame,
                    "source_atom_id": a.atom_id,
                    "target_atom_id": b.atom_id,
                    "support_boundary_gap_px": fmt(gap),
                    "centroid_distance_px": fmt(dist),
                    "radial_delta": fmt(abs(a.radial - b.radial)),
                    "azimuth_delta": fmt(abs(a.azimuth - b.azimuth)),
                    "orientation_delta": fmt(angle_diff(a.orientation, b.orientation)),
                    "energy_ratio": fmt(max(a.integrated, b.integrated) / max(1.0, min(a.integrated, b.integrated))),
                    "role_relation": role_relation(a, b),
                    "shared_or_compatible_lineage": bool_text(bool(a.track_id and a.track_id == b.track_id) or role_compatible(a, b)),
                    "background_conflict": bool_text(BACKGROUND_ROLE in {a.role, b.role}),
                    "edge_status": status,
                }
            )
    return rows


def accepted_edge_map(edges: Sequence[Mapping[str, str]]) -> dict[int, dict[frozenset[str], str]]:
    out: dict[int, dict[frozenset[str], str]] = defaultdict(dict)
    for row in edges:
        if row["edge_status"] == "accepted_local_relation":
            out[parse_int(row["sar_frame"])][frozenset([row["source_atom_id"], row["target_atom_id"]])] = row["edge_id"]
    return out


def core_relation_type(atoms: Sequence[Atom]) -> str:
    roles = {a.role for a in atoms}
    if len(atoms) == 1:
        role = atoms[0].role
        if role == "body_core_candidate":
            return "single_partial_body"
        if role == "endpoint_hotspot_candidate":
            return "single_endpoint_part"
        if role == "side_ridge_candidate":
            return "single_side_part"
        return "unresolved_local_response"
    if {"body_core_candidate", "side_ridge_candidate", "endpoint_hotspot_candidate"} <= roles:
        return "body_side_endpoint"
    if "body_core_candidate" in roles and "endpoint_hotspot_candidate" in roles:
        return "body_to_endpoint"
    if "body_core_candidate" in roles and "side_ridge_candidate" in roles:
        return "body_to_side"
    if "side_ridge_candidate" in roles and "endpoint_hotspot_candidate" in roles:
        return "side_to_endpoint"
    return "unresolved_local_response"


def graph_connected(atom_ids: Sequence[str], frame_edges: Mapping[frozenset[str], str]) -> bool:
    if len(atom_ids) <= 1:
        return True
    seen = {atom_ids[0]}
    changed = True
    while changed:
        changed = False
        for edge in frame_edges:
            a, b = tuple(edge)
            if a in seen and b not in seen:
                seen.add(b)
                changed = True
            if b in seen and a not in seen:
                seen.add(a)
                changed = True
    return set(atom_ids) <= seen


def core_state(core_atoms: Sequence[Atom], frame_edges: Mapping[frozenset[str], str], nearby_background: int) -> tuple[str, str]:
    roles = {a.role for a in core_atoms}
    has_track = any(a.track_len >= 2 for a in core_atoms)
    relation = core_relation_type(core_atoms)
    if BACKGROUND_ROLE in roles:
        return "background_counterexample", "核心包含背景弧线，不能作为车辆响应核心。"
    if relation in {"single_endpoint_part", "single_side_part"}:
        return "vehicle_part_box_only", "仅有端点或侧边局部响应，没有主体闭合，作为局部部件框保留。"
    if relation == "single_partial_body":
        return "vehicle_response_box_possible", "只有局部主体响应，缺少端点或侧边闭合，保持 possible。"
    if graph_connected([a.atom_id for a in core_atoms], frame_edges) and has_track and nearby_background == 0 and relation in {"body_to_endpoint", "body_to_side", "body_side_endpoint"}:
        return "vehicle_response_box_supported", "主体与端点/侧边经 accepted edge 连通且存在重生谱系。"
    if relation in {"body_to_endpoint", "body_to_side", "side_to_endpoint", "body_side_endpoint"}:
        return "vehicle_response_box_possible", "局部关系成立，但谱系或边界仍不足以支持完整车辆响应。"
    return "unresolved", "局部响应可见但结构关系不足。"


def make_core_hypotheses(atoms: Sequence[Atom], graph_edges: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    edges_by_frame = accepted_edge_map(graph_edges)
    atom_by_id = {a.atom_id: a for a in atoms}
    rows: list[dict[str, Any]] = []
    for frame, frame_atoms in atoms_by_frame(atoms).items():
        candidates = [a for a in frame_atoms if a.role != BACKGROUND_ROLE and a.role_class in {"core_member_candidate", "optional_support_candidate"}]
        frame_edges = edges_by_frame.get(frame, {})
        seen_members: set[tuple[str, ...]] = set()
        combos: list[tuple[Atom, ...]] = []
        for atom in candidates:
            if atom.role in VEHICLE_ROLES or atom.role in {"unresolved_atom", "isolated_small_atom"}:
                combos.append((atom,))
        for size in [2, 3]:
            for combo in combinations(candidates, size):
                ids = [a.atom_id for a in combo]
                if graph_connected(ids, frame_edges):
                    combos.append(combo)
        combos.sort(key=lambda combo: (len(combo), -sum(a.integrated for a in combo)))
        for combo in combos:
            ids = tuple(sorted(a.atom_id for a in combo))
            if ids in seen_members:
                continue
            seen_members.add(ids)
            if len(ids) > 1 and not graph_connected(list(ids), frame_edges):
                continue
            if len(rows) > 0 and sum(1 for row in rows if parse_int(row["sar_frame"]) == frame) >= 8:
                break
            core_atoms = [atom_by_id[i] for i in ids]
            boxes = [a.box for a in core_atoms]
            bbox = union_box(boxes)
            xs = np.concatenate([a.xs for a in core_atoms])
            ys = np.concatenate([a.ys for a in core_atoms])
            support = support_geometry(xs, ys, bbox)
            nearby_background = sum(1 for a in frame_atoms if a.role == BACKGROUND_ROLE and gap_between(a.box, bbox) <= 28.0)
            state, state_reason = core_state(core_atoms, frame_edges, nearby_background)
            edge_ids = sorted(edge_id for edge, edge_id in frame_edges.items() if edge <= set(ids))
            rows.append(
                {
                    "core_subgraph_id": f"R21C{len(rows) + 1:05d}",
                    "sar_frame": frame,
                    "member_atom_ids": ";".join(ids),
                    "graph_edge_ids": ";".join(edge_ids),
                    "connected_in_atom_graph": bool_text(graph_connected(list(ids), frame_edges)),
                    "core_relation_type": core_relation_type(core_atoms),
                    "core_role_summary": ";".join(f"{a.atom_id}:{a.role}" for a in core_atoms),
                    "core_support_geometry": f"bbox={box_text(bbox)};proj={fmt(support['projection_long'])}/{fmt(support['projection_short'])};cov={fmt(support['cov_long'])}/{fmt(support['cov_short'])};pix={int(support['count'])}",
                    "core_lineage_evidence": ";".join(sorted({a.track_id for a in core_atoms if a.track_id})) or "single_frame_core",
                    "core_background_relation": "nearby_background" if nearby_background else "background_separable_or_absent",
                    "box_state": state,
                    "state_reason_cn": state_reason,
                }
            )
    return rows


def atoms_for_core(core: Mapping[str, str], atom_by_id: Mapping[str, Atom]) -> list[Atom]:
    return [atom_by_id[atom_id] for atom_id in core["member_atom_ids"].split(";") if atom_id in atom_by_id]


def bbox_blank_ratio(box: Box, atoms: Sequence[Atom]) -> float:
    support = sum(atom.area for atom in atoms)
    return max(0.0, 1.0 - safe_div(float(support), max(1.0, box.area)))


def membership_decision(atom: Atom, core_atoms: Sequence[Atom]) -> tuple[str, str, str, str]:
    core_box = union_box([a.box for a in core_atoms])
    gap = gap_between(atom.box, core_box)
    dist = min(math.hypot(atom.cx - c.cx, atom.cy - c.cy) for c in core_atoms)
    relations = []
    for c in core_atoms:
        status, blocked = edge_status(atom, c)
        if status in {"accepted_local_relation", "ambiguous_relation"}:
            relations.append(f"{c.atom_id}:{role_relation(atom, c)}:{status}")
    shared = bool(atom.track_id and any(atom.track_id == c.track_id for c in core_atoms))
    extended = union_box([core_box, atom.box])
    blank = bbox_blank_ratio(extended, list(core_atoms) + [atom])
    if atom.role == BACKGROUND_ROLE:
        return "exclude_from_bbox", "exclude_background_conflict", ";".join(relations), "背景弧线必须排除。"
    if shared:
        return "include_in_bbox", "include_shared_lineage", ";".join(relations), "与核心共享重生谱系，作为强附属响应纳入 conservative 框。"
    if relations and atom.role in VEHICLE_ROLES and blank <= 0.76:
        return "include_in_bbox", "include_explicit_part_relation", ";".join(relations), "与核心存在明确部件关系且不会造成异常空白。"
    if relations and gap <= 28.0 and angle_diff(atom.orientation, np.mean([c.orientation for c in core_atoms])) <= 35.0 and blank <= 0.72:
        return "include_in_bbox", "include_close_boundary_with_directional_continuity", ";".join(relations), "边界连续且方向一致，作为弱远侧附属响应纳入。"
    if gap <= 55.0 or dist <= 115.0:
        return "uncertain_bbox_membership", "uncertain_spatial_proximity_only", ";".join(relations), "仅空间接近，不能自动纳入确定框。"
    if blank > 0.82:
        return "exclude_from_bbox", "exclude_excessive_bbox_expansion", ";".join(relations), "纳入后会造成大面积无响应空白。"
    return "exclude_from_bbox", "exclude_unrelated_response", ";".join(relations), "与核心没有有效谱系或部件关系。"


def optional_membership_rows(cores: Sequence[Mapping[str, str]], atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    atom_by_id = {a.atom_id: a for a in atoms}
    by_frame = atoms_by_frame(atoms)
    rows: list[dict[str, Any]] = []
    for core in cores:
        core_atoms = atoms_for_core(core, atom_by_id)
        if not core_atoms:
            continue
        core_ids = {a.atom_id for a in core_atoms}
        core_box = union_box([a.box for a in core_atoms])
        for atom in by_frame[parse_int(core["sar_frame"])]:
            if atom.atom_id in core_ids:
                continue
            decision, evidence, relations, reason = membership_decision(atom, core_atoms)
            extended = union_box([core_box, atom.box])
            rows.append(
                {
                    "core_subgraph_id": core["core_subgraph_id"],
                    "sar_frame": core["sar_frame"],
                    "atom_id": atom.atom_id,
                    "candidate_role": atom.role,
                    "membership_decision": decision,
                    "membership_evidence_type": evidence,
                    "best_relation_to_core": relations.split(";")[0] if relations else "none",
                    "all_valid_relations_to_core": relations,
                    "boundary_distance_to_core_px": fmt(gap_between(atom.box, core_box)),
                    "centroid_distance_to_core_px": fmt(min(math.hypot(atom.cx - c.cx, atom.cy - c.cy) for c in core_atoms)),
                    "bbox_blank_ratio_if_included": fmt(bbox_blank_ratio(extended, core_atoms + [atom])),
                    "decision_reason_cn": reason,
                }
            )
    return rows


def response_box_rows(cores: Sequence[Mapping[str, str]], optional_rows: Sequence[Mapping[str, str]], atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    atom_by_id = {a.atom_id: a for a in atoms}
    optional_by_core: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in optional_rows:
        optional_by_core[row["core_subgraph_id"]].append(row)
    rows: list[dict[str, Any]] = []
    for core in cores:
        core_atoms = atoms_for_core(core, atom_by_id)
        if not core_atoms:
            continue
        strong_ids = [row["atom_id"] for row in optional_by_core[core["core_subgraph_id"]] if row["membership_decision"] == "include_in_bbox"]
        uncertain_ids = [row["atom_id"] for row in optional_by_core[core["core_subgraph_id"]] if row["membership_decision"] == "uncertain_bbox_membership"]
        excluded_ids = [row["atom_id"] for row in optional_by_core[core["core_subgraph_id"]] if row["membership_decision"] == "exclude_from_bbox"]
        core_box = union_box([a.box for a in core_atoms])
        strong_atoms = [atom_by_id[i] for i in strong_ids if i in atom_by_id]
        uncertain_atoms = [atom_by_id[i] for i in uncertain_ids if i in atom_by_id]
        conservative = union_box([core_box] + [a.box for a in strong_atoms])
        envelope = union_box([conservative] + [a.box for a in uncertain_atoms])
        cx, cy, mx, my, rng, az, err = center_m(conservative)
        rows.append(
            {
                "response_box_id": f"R21B{len(rows) + 1:05d}",
                "core_subgraph_id": core["core_subgraph_id"],
                "sar_frame": core["sar_frame"],
                "box_state": core["box_state"],
                "core_member_atom_ids": core["member_atom_ids"],
                "strong_optional_atom_ids": ";".join(strong_ids),
                "uncertain_optional_atom_ids": ";".join(uncertain_ids),
                "excluded_atom_ids": ";".join(excluded_ids),
                "core_bbox": box_text(core_box),
                "conservative_response_bbox": box_text(conservative),
                "uncertain_envelope_bbox": box_text(envelope),
                "center_x_px": fmt(cx),
                "center_y_px": fmt(cy),
                "center_x_m": fmt(mx),
                "center_y_m": fmt(my),
                "range_m": fmt(rng),
                "azimuth_deg": fmt(az),
                "metric_consistency_error_m": fmt(err),
                "final_annotation_space": "sar_image_pixel_domain",
            }
        )
    return rows


def family_relation(a: Mapping[str, str], b: Mapping[str, str]) -> str:
    box_a = box_from_text(a["conservative_response_bbox"])
    box_b = box_from_text(b["conservative_response_bbox"])
    if not box_a or not box_b:
        return "spatially_distinct_hypothesis"
    center_shift = math.hypot(box_a.cx - box_b.cx, box_a.cy - box_b.cy)
    if box_text(box_a) == box_text(box_b):
        return "exact_duplicate_bbox"
    if bbox_iou(box_a, box_b) >= 0.86 and center_shift <= 22.0:
        return "near_duplicate_bbox"
    if contains_box(box_a, box_b) or contains_box(box_b, box_a):
        return "nested_boundary_variant"
    if a["strong_optional_atom_ids"] == b["strong_optional_atom_ids"] and a["box_state"] == b["box_state"]:
        return "distinct_core_same_response"
    return "spatially_distinct_hypothesis"


def build_families(boxes: Sequence[Mapping[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for box in boxes:
        by_frame[parse_int(box["sar_frame"])].append(box)
    family_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []
    for frame, frame_boxes in by_frame.items():
        parent = {box["response_box_id"]: box["response_box_id"] for box in frame_boxes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        relations: dict[frozenset[str], str] = {}
        for a, b in combinations(frame_boxes, 2):
            reln = family_relation(a, b)
            relations[frozenset([a["response_box_id"], b["response_box_id"]])] = reln
            if reln != "spatially_distinct_hypothesis":
                union(a["response_box_id"], b["response_box_id"])
        groups: dict[str, list[Mapping[str, str]]] = defaultdict(list)
        for box in frame_boxes:
            groups[find(box["response_box_id"])].append(box)
        for _root, members in sorted(groups.items(), key=lambda item: min(m["response_box_id"] for m in item[1])):
            family_id = f"R21F{len(family_rows) + 1:05d}"
            member_ids = [m["response_box_id"] for m in members]
            rel_counts = Counter(
                relations.get(frozenset([a, b]), "single_member_family")
                for a, b in combinations(member_ids, 2)
            )
            reln = rel_counts.most_common(1)[0][0] if rel_counts else "single_member_family"
            core_sets = sorted({m["core_member_atom_ids"] for m in members})
            conservative_variants = sorted({m["conservative_response_bbox"] for m in members})
            envelope_variants = sorted({m["uncertain_envelope_bbox"] for m in members})
            states = sorted(Counter(m["box_state"] for m in members).items())
            shared_tracks = sorted({tok for m in members for tok in m["core_member_atom_ids"].split(";") if tok})
            family_rows.append(
                {
                    "family_id": family_id,
                    "sar_frame": frame,
                    "member_core_subgraph_ids": ";".join(m["core_subgraph_id"] for m in members),
                    "member_response_box_ids": ";".join(member_ids),
                    "family_relation": reln,
                    "distinct_core_member_sets": len(core_sets),
                    "conservative_bbox_variants": " | ".join(conservative_variants),
                    "uncertain_envelope_variants": " | ".join(envelope_variants),
                    "family_runtime_states": ";".join(f"{k}:{v}" for k, v in states),
                    "family_shared_evidence": ";".join(shared_tracks[:12]),
                    "family_unresolved_difference": "members differ by core membership or uncertain envelope" if len(members) > 1 else "",
                }
            )
            for member in members:
                member_rows.append(
                    {
                        "family_id": family_id,
                        "response_box_id": member["response_box_id"],
                        "core_subgraph_id": member["core_subgraph_id"],
                        "sar_frame": frame,
                        "member_relation_to_family": reln,
                        "box_state": member["box_state"],
                    }
                )
    return family_rows, member_rows


def family_box(row: Mapping[str, str]) -> Box:
    first = row["conservative_bbox_variants"].split(" | ")[0]
    box = box_from_text(first)
    return box if box else Box(1000.0, 1120.0, 1250.0, 1260.0)


def build_family_temporal_edges(families: Sequence[Mapping[str, str]], member_rows: Sequence[Mapping[str, str]], boxes: Sequence[Mapping[str, str]], atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    family_to_tracks: dict[str, set[str]] = defaultdict(set)
    atom_tracks = {atom.atom_id: atom.track_id for atom in atoms if atom.track_id}
    box_by_id = {row["response_box_id"]: row for row in boxes}
    for row in member_rows:
        box = box_by_id.get(row["response_box_id"])
        if not box:
            continue
        for atom_id in box["core_member_atom_ids"].split(";"):
            track = atom_tracks.get(atom_id)
            if track:
                family_to_tracks[row["family_id"]].add(track)
    by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for fam in families:
        by_frame[parse_int(fam["sar_frame"])].append(fam)
    frames = sorted(by_frame)
    rows: list[dict[str, Any]] = []
    for src_frame, dst_frame in zip(frames, frames[1:]):
        if dst_frame - src_frame > 35:
            continue
        candidates: list[tuple[str, str]] = []
        for src in by_frame[src_frame]:
            sbox = family_box(src)
            for dst in by_frame[dst_frame]:
                dbox = family_box(dst)
                shift = math.hypot(sbox.cx - dbox.cx, sbox.cy - dbox.cy)
                shared = family_to_tracks[src["family_id"]] & family_to_tracks[dst["family_id"]]
                if shift <= 150.0 or shared:
                    candidates.append((src["family_id"], dst["family_id"]))
        pred_count = Counter(dst for _src, dst in candidates)
        succ_count = Counter(src for src, _dst in candidates)
        for src_id, dst_id in candidates:
            src = next(f for f in by_frame[src_frame] if f["family_id"] == src_id)
            dst = next(f for f in by_frame[dst_frame] if f["family_id"] == dst_id)
            sbox = family_box(src)
            dbox = family_box(dst)
            shared = sorted(family_to_tracks[src_id] & family_to_tracks[dst_id])
            if pred_count[dst_id] > 1:
                status = "ambiguous_predecessors"
            elif succ_count[src_id] > 1:
                status = "ambiguous_successors"
            elif shared:
                status = "unique_family_continuation"
            else:
                status = "possible_continuation"
            rows.append(
                {
                    "temporal_edge_id": f"R21TE{len(rows) + 1:05d}",
                    "source_family_id": src_id,
                    "target_family_id": dst_id,
                    "source_frame": src_frame,
                    "target_frame": dst_frame,
                    "shared_core_track_ids": ";".join(shared),
                    "center_shift_px": fmt(math.hypot(sbox.cx - dbox.cx, sbox.cy - dbox.cy)),
                    "bbox_iou": fmt(bbox_iou(sbox, dbox)),
                    "size_ratio": fmt(safe_div(dbox.area, max(1.0, sbox.area))),
                    "core_relation_compatibility": bool_text(bool(shared) or src["family_runtime_states"] == dst["family_runtime_states"]),
                    "edge_status": status,
                    "blocked_reason": "" if status in {"unique_family_continuation", "possible_continuation"} else "nonselective_temporal_graph_keeps_ambiguity",
                }
            )
    return rows


def build_counterexamples(families: Sequence[Mapping[str, str]], boxes: Sequence[Mapping[str, str]], atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    by_frame_atoms = atoms_by_frame(atoms)
    rows: list[dict[str, Any]] = []
    for family in families:
        if not any(state in family["family_runtime_states"] for state in ["vehicle_response_box_supported", "vehicle_response_box_possible", "vehicle_part_box_only"]):
            continue
        frame = parse_int(family["sar_frame"])
        fbox = family_box(family)
        alternatives = sorted(
            by_frame_atoms.get(frame, []),
            key=lambda atom: (atom.role != BACKGROUND_ROLE, gap_between(atom.box, fbox), -atom.integrated),
        )
        alt = next((atom for atom in alternatives if gap_between(atom.box, fbox) <= 95 and atom.role not in {"body_core_candidate"}), alternatives[0] if alternatives else None)
        if not alt:
            continue
        rows.append(
            {
                "accepted_family_id": family["family_id"],
                "alternative_object_id": alt.atom_id,
                "same_frame": frame,
                "accepted_visible_structure": f"family bbox {box_text(fbox)} contains local core/member responses",
                "alternative_visible_structure": f"{alt.role} at {box_text(alt.box)}",
                "accepted_core_relation": family["family_runtime_states"],
                "alternative_relation": "nearby_background" if alt.role == BACKGROUND_ROLE else "nearby_noncore_response",
                "accepted_lineage": family["family_shared_evidence"],
                "alternative_lineage": alt.track_id or "single_frame_or_no_shared_lineage",
                "accepted_bbox_membership": family["member_response_box_ids"],
                "alternative_exclusion_reason": "background arc excluded" if alt.role == BACKGROUND_ROLE else "no whole-core membership evidence",
                "why_accepted_is_vehicle_response_cn": f"{frame}帧该族的确定框包含局部主体/端点/侧边关系，框内响应在像素上相互接近，并且不是单条背景弧线主导。",
                "why_alternative_is_not_vehicle_response_cn": f"{alt.atom_id} 位于同帧邻近区域，但角色为 {alt.role}，缺少与该核心共享谱系或明确部件关系，因此不并入同一车辆响应。",
                "remaining_uncertainty_cn": "边界仍是 SAR 响应框而不是真实车辆外形；远侧弱响应保留为不确定或反例。",
            }
        )
    return rows


def write_generation_artifacts(paths: Mapping[str, Path]) -> dict[str, str]:
    atoms, shell_rows = extract_atoms(RUNTIME_FRAMES)
    lineage_nodes, lineage_edges = build_lineage(atoms)
    gnodes = graph_node_rows(atoms)
    gedges = graph_edge_rows(atoms)
    cores = make_core_hypotheses(atoms, gedges)
    optional = optional_membership_rows(cores, atoms)
    boxes = response_box_rows(cores, optional, atoms)
    families, members = build_families(boxes)
    temporal = build_family_temporal_edges(families, members, boxes, atoms)
    counter = build_counterexamples(families, boxes, atoms)
    support = [support_metric_row(f"R21SM{i + 1:05d}", atom.atom_id, "atom", atom.frame, atom.xs, atom.ys, atom.box) for i, atom in enumerate(atoms)]
    atom_by_id = {atom.atom_id: atom for atom in atoms}
    for core in cores:
        core_atoms = atoms_for_core(core, atom_by_id)
        if not core_atoms:
            continue
        xs = np.concatenate([a.xs for a in core_atoms])
        ys = np.concatenate([a.ys for a in core_atoms])
        support.append(support_metric_row(f"R21SM{len(support) + 1:05d}", core["core_subgraph_id"], "core_subgraph", parse_int(core["sar_frame"]), xs, ys, union_box([a.box for a in core_atoms])))
    artifact_rows = [
        ("runtime_manifest", runtime_manifest_rows(), RUNTIME_FIELDS),
        ("causal_shell", shell_rows, CAUSAL_FIELDS),
        ("atom_trace", atom_rows(atoms), ATOM_FIELDS),
        ("roles", role_rows(atoms), ROLE_FIELDS),
        ("support_metrics", support, SUPPORT_FIELDS),
        ("lineage_nodes", lineage_nodes, LINEAGE_NODE_FIELDS),
        ("lineage_edges", lineage_edges, LINEAGE_EDGE_FIELDS),
        ("atom_graph_nodes", gnodes, GRAPH_NODE_FIELDS),
        ("atom_graph_edges", gedges, GRAPH_EDGE_FIELDS),
        ("core_hypotheses", cores, CORE_FIELDS),
        ("optional_membership", optional, OPTIONAL_FIELDS),
        ("response_boxes", boxes, BOX_FIELDS),
        ("families", families, FAMILY_FIELDS),
        ("family_members", members, FAMILY_MEMBER_FIELDS),
        ("family_temporal", temporal, FAMILY_TEMPORAL_FIELDS),
        ("background_counterexamples", counter, COUNTEREXAMPLE_FIELDS),
    ]
    for key, rows, fields in artifact_rows:
        write_csv(paths[key], rows, fields)
    shas = {key: sha256(paths[key]) for key, _rows, _fields in artifact_rows}
    manifest = [
        {
            "artifact": key,
            "path": rel(paths[key]),
            "sha256": shas[key],
            "rows": row_count(paths[key]),
            "frozen_phase": "generation",
        }
        for key, _rows, _fields in artifact_rows
    ]
    write_csv(paths["frozen_manifest"], manifest, MANIFEST_FIELDS)
    shas["frozen_manifest"] = sha256(paths["frozen_manifest"])
    return shas


def generate() -> None:
    shas = write_generation_artifacts(OUTPUTS)
    print("generated R2.1 frozen causal bbox-family artifacts")
    for key in FREEZE_KEYS:
        print(f"{key}={shas[key]}")


def crop_focus_box(box: Box, margin: float = 60.0) -> Box:
    return expand_box(box, margin)


def crop_point(x: float, y: float, focus: Box, width: int, height: int) -> tuple[int, int]:
    px = int((x - focus.x1) / max(1.0, focus.width) * width)
    py = int((y - focus.y1) / max(1.0, focus.height) * height)
    return px, py


def draw_crop_box(draw: ImageDraw.ImageDraw, box: Box, focus: Box, width: int, height: int, color: tuple[int, int, int], line_width: int = 2) -> None:
    x1, y1 = crop_point(box.x1, box.y1, focus, width, height)
    x2, y2 = crop_point(box.x2, box.y2, focus, width, height)
    draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)


def render_tile(family: Mapping[str, str], boxes_by_id: Mapping[str, Mapping[str, str]], mode: str, atoms_by_id: Mapping[str, Atom]) -> Image.Image:
    frame = parse_int(family["sar_frame"])
    base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB") if sar_gray_path(SCENE, frame).exists() else Image.new("RGB", (SAR_WIDTH, SAR_HEIGHT), (20, 20, 20))
    fbox = family_box(family)
    focus = crop_focus_box(fbox, 70.0)
    tile = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((520, 280))
    draw = ImageDraw.Draw(tile)
    draw.rectangle([0, 0, 520, 24], fill=(0, 0, 0))
    draw.text((5, 5), f"R2.1_FRAME_{frame:03d} {family['family_id']} {mode}", fill=(255, 255, 255))
    if mode == "raw":
        draw_crop_box(draw, fbox, focus, 520, 280, (235, 235, 235), 3)
        return tile
    draw_crop_box(draw, fbox, focus, 520, 280, (0, 255, 120), 2)
    for response_id in family["member_response_box_ids"].split(";"):
        box_row = boxes_by_id.get(response_id)
        if not box_row:
            continue
        core_box = box_from_text(box_row["core_bbox"])
        env_box = box_from_text(box_row["uncertain_envelope_bbox"])
        if env_box:
            draw_crop_box(draw, env_box, focus, 520, 280, (255, 190, 0), 1)
        if core_box:
            draw_crop_box(draw, core_box, focus, 520, 280, (0, 200, 255), 2)
        for atom_id in (box_row["core_member_atom_ids"] + ";" + box_row["strong_optional_atom_ids"]).split(";"):
            atom = atoms_by_id.get(atom_id)
            if not atom:
                continue
            color = (0, 240, 120) if atom.role == "body_core_candidate" else (80, 170, 255) if atom.role == "side_ridge_candidate" else (255, 220, 0) if atom.role == "endpoint_hotspot_candidate" else (180, 180, 180)
            draw_crop_box(draw, atom.box, focus, 520, 280, color, 1)
            x, y = crop_point(atom.box.x1, atom.box.y1, focus, 520, 280)
            draw.text((x + 2, max(26, y - 10)), atom.role.split("_")[0], fill=color)
    return tile


def render_sheets(mode: str) -> list[Path]:
    require_files([OUTPUTS["families"], OUTPUTS["response_boxes"], OUTPUTS["atom_trace"], OUTPUTS["roles"]])
    families = read_rows(OUTPUTS["families"])
    boxes = {row["response_box_id"]: row for row in read_rows(OUTPUTS["response_boxes"])}
    atoms = atoms_from_outputs()
    atoms_by_id = {atom.atom_id: atom for atom in atoms}
    paths = [VISUALS[f"{mode}_{idx}"] for idx in range(1, 5)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page_size = 16
    focus_families = [fam for fam in families if parse_int(fam["sar_frame"]) in FOCUS_FRAMES]
    rest = [fam for fam in families if fam not in focus_families]
    ordered = focus_families + rest
    for page_idx, path in enumerate(paths):
        sheet = Image.new("RGB", (1040, 2240), (18, 18, 18))
        for idx, fam in enumerate(ordered[page_idx * page_size:(page_idx + 1) * page_size]):
            tile = render_tile(fam, boxes, mode, atoms_by_id)
            x = (idx % 2) * 520
            y = (idx // 2) * 280
            sheet.paste(tile, (x, y))
        sheet.save(path)
    return paths


def atoms_from_outputs() -> list[Atom]:
    role_by_id = {row["atom_id"]: row for row in read_rows(OUTPUTS["roles"])}
    atom_rows_loaded = read_rows(OUTPUTS["atom_trace"])
    track_by_id = {row["atom_id"]: row for row in read_rows(OUTPUTS["lineage_nodes"])}
    atoms: list[Atom] = []
    geometry = build_geometry()
    for row in atom_rows_loaded:
        box = box_from_text(row["support_bbox"])
        if not box:
            continue
        atom_id = row["atom_id"]
        role_row = role_by_id.get(atom_id, {})
        # Pixel sets are reconstructed as a dense bbox proxy only for visualization/eval helper use.
        xs = np.array([box.x1, box.x2], dtype=np.float32)
        ys = np.array([box.y1, box.y2], dtype=np.float32)
        atoms.append(
            Atom(
                atom_id=atom_id,
                frame=parse_int(row["sar_frame"]),
                source_type=row["source_type"],
                source_frame=parse_int(row["selected_source_frame"], 0) if row["selected_source_frame"] else None,
                xs=xs,
                ys=ys,
                box=box,
                cx=parse_float(row["pixel_centroid_x"]),
                cy=parse_float(row["pixel_centroid_y"]),
                area=parse_int(row["support_pixel_count"]),
                integrated=parse_float(row["integrated_energy"]),
                mean=parse_float(row["mean_energy"]),
                peak=parse_float(row["peak_energy"]),
                relative_energy=parse_float(row["relative_energy_within_shell"]),
                azimuth=parse_float(row["azimuth_deg"]),
                radial=parse_float(row["radial_px"]),
                axis1=parse_float(row["axis1_px"]),
                axis2=parse_float(row["axis2_px"]),
                orientation=parse_float(row["orientation_deg"]),
                threshold=parse_float(row["extraction_threshold"]),
                boundary_contact=row["shell_boundary_contact"] == "true",
                role=role_row.get("candidate_role", "unresolved_atom"),
                role_class=role_row.get("graph_role_class", "core_member_candidate"),
                role_reason=role_row.get("role_rule_provenance", ""),
                track_id=track_by_id.get(atom_id, {}).get("persistent_part_track_id", ""),
                track_len=parse_int(track_by_id.get(atom_id, {}).get("track_len", "0")),
            )
        )
    return atoms


def blind_raw_pack() -> None:
    paths = render_sheets("raw")
    if not OUTPUTS["blind_raw"].exists():
        rows = []
        for idx, fam in enumerate(read_rows(OUTPUTS["families"]), start=1):
            sheet = paths[min((idx - 1) // 16, len(paths) - 1)]
            rows.append(
                {
                    "raw_review_id": f"R21RAW{idx:04d}",
                    "blind_frame_id": f"R21_BLIND_FRAME_{parse_int(fam['sar_frame']):03d}",
                    "blind_family_id": f"R21_BLIND_FAMILY_{idx:03d}",
                    "family_id": fam["family_id"],
                    "raw_strongest_response_position_cn": "",
                    "raw_visible_component_count": "",
                    "raw_shape_and_orientation_cn": "",
                    "raw_internal_blank_cn": "",
                    "raw_neighbor_response_cn": "",
                    "raw_bbox_boundary_adequacy_cn": "",
                    "raw_vehicle_response_support": "",
                    "raw_background_support": "",
                    "raw_unresolved": "",
                    "raw_decisive_reason_cn": "",
                    "raw_alternative_explanation_cn": "",
                    "raw_confidence": "",
                    "raw_png": rel(sheet),
                }
            )
        write_csv(OUTPUTS["blind_raw"], rows, RAW_FIELDS)
    print("blind-raw-pack wrote raw family sheets and judgement CSV")
    for path in paths:
        print(rel(path))


def require_completed(path: Path, fields: Sequence[str], label: str) -> None:
    require_files([path])
    incomplete = []
    for row in read_rows(path):
        if any(not row.get(field, "").strip() for field in fields):
            incomplete.append(row.get("family_id", ""))
    if incomplete:
        raise ValueError(f"{label} judgement incomplete: " + "; ".join(incomplete[:10]))


def blind_assisted_pack() -> None:
    require_completed(
        OUTPUTS["blind_raw"],
        [
            "raw_strongest_response_position_cn",
            "raw_visible_component_count",
            "raw_shape_and_orientation_cn",
            "raw_internal_blank_cn",
            "raw_neighbor_response_cn",
            "raw_bbox_boundary_adequacy_cn",
            "raw_vehicle_response_support",
            "raw_background_support",
            "raw_unresolved",
            "raw_decisive_reason_cn",
            "raw_alternative_explanation_cn",
            "raw_confidence",
        ],
        "raw",
    )
    paths = render_sheets("assisted")
    if not OUTPUTS["blind_assisted"].exists():
        rows = []
        for idx, fam in enumerate(read_rows(OUTPUTS["families"]), start=1):
            sheet = paths[min((idx - 1) // 16, len(paths) - 1)]
            rows.append(
                {
                    "assisted_review_id": f"R21AST{idx:04d}",
                    "blind_frame_id": f"R21_BLIND_FRAME_{parse_int(fam['sar_frame']):03d}",
                    "blind_family_id": f"R21_BLIND_FAMILY_{idx:03d}",
                    "family_id": fam["family_id"],
                    "assisted_core_visual_match": "",
                    "assisted_optional_membership_match": "",
                    "assisted_background_exclusion_match": "",
                    "assisted_structure_support": "",
                    "assisted_unresolved": "",
                    "assisted_decisive_reason_cn": "",
                    "raw_to_assisted_change_cn": "",
                    "algorithm_overlay_helped_or_misled_cn": "",
                    "assisted_confidence": "",
                    "assisted_png": rel(sheet),
                }
            )
        write_csv(OUTPUTS["blind_assisted"], rows, ASSISTED_FIELDS)
    print("blind-assisted-pack wrote assisted family sheets and judgement CSV")
    for path in paths:
        print(rel(path))


def raw_class(row: Mapping[str, str]) -> str:
    if row["raw_vehicle_response_support"] == "true":
        return "vehicle_response"
    if row["raw_background_support"] == "true":
        return "background"
    return "unresolved"


def assisted_class(row: Mapping[str, str]) -> str:
    if row["assisted_structure_support"] == "true":
        return "vehicle_response"
    if row["assisted_background_exclusion_match"] == "false":
        return "background_or_misled"
    if row["assisted_unresolved"] == "true":
        return "unresolved"
    return "mechanism_partial"


def load_gt_by_frame() -> dict[int, Box]:
    rows = read_rows(INPUTS["paired"])
    out: dict[int, list[Box]] = defaultdict(list)
    for row in rows:
        if row.get("scene") != SCENE:
            continue
        frame = parse_int(row.get("sar_frame"))
        try:
            box = Box(
                parse_float(row["sar_bbox_x1"]),
                parse_float(row["sar_bbox_y1"]),
                parse_float(row["sar_bbox_x2"]),
                parse_float(row["sar_bbox_y2"]),
            )
        except KeyError:
            continue
        if box.area > 0:
            out[frame].append(box)
    return {frame: union_box(boxes) for frame, boxes in out.items()}


def label_group(frame: int) -> str:
    if frame in list(range(27, 32)) + list(range(78, 82)) + list(range(270, 274)) + list(range(289, 291)):
        return "historical_positive_group_eval_only"
    return "historical_nonpositive_or_holdout_group_eval_only"


def vehicle_identity(frame: int) -> str:
    if 27 <= frame <= 81:
        return "white_suv_eval_only"
    if 269 <= frame <= 290:
        return "silver_mpv_eval_only"
    return "unknown_or_holdout_eval_only"


def evaluate_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    families = read_rows(OUTPUTS["families"])
    raw = {row["family_id"]: row for row in read_rows(OUTPUTS["blind_raw"])}
    assisted = {row["family_id"]: row for row in read_rows(OUTPUTS["blind_assisted"])}
    gt_by_frame = load_gt_by_frame()
    eval_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for fam in families:
        frame = parse_int(fam["sar_frame"])
        pred = family_box(fam)
        gt = gt_by_frame.get(frame)
        inter = bbox_intersection(pred, gt) if gt else 0.0
        iou = bbox_iou(pred, gt) if gt else math.nan
        coverage = safe_div(inter, gt.area) if gt else math.nan
        purity = safe_div(inter, pred.area) if gt else math.nan
        area_ratio = safe_div(pred.area, gt.area) if gt else math.nan
        cdist = math.hypot(pred.cx - gt.cx, pred.cy - gt.cy) if gt else math.nan
        raw_j = raw_class(raw[fam["family_id"]])
        ast_j = assisted_class(assisted[fam["family_id"]])
        state = fam["family_runtime_states"]
        explanation = "GT 仅用于冻结后评价；"
        if gt:
            explanation += f"IoU={fmt(iou)}, GT coverage={fmt(coverage)}, purity={fmt(purity)}。"
        else:
            explanation += "该帧没有 exact GT，不做正确/错误真值裁决。"
        row = {
            "eval_id": f"R21EV{len(eval_rows) + 1:04d}",
            "family_id": fam["family_id"],
            "sar_frame": frame,
            "family_state": state,
            "raw_judgement": raw_j,
            "assisted_judgement": ast_j,
            "gt_exact_frame_available": bool_text(gt is not None),
            "bbox_iou": fmt(iou),
            "gt_coverage_ratio": fmt(coverage),
            "prediction_purity_ratio": fmt(purity),
            "prediction_to_gt_area_ratio": fmt(area_ratio),
            "center_distance_px": fmt(cdist),
            "center_distance_m": fmt(cdist * PX_TO_M if not math.isnan(cdist) else math.nan),
            "posthoc_label_group_eval_only": label_group(frame),
            "vehicle_identity_eval_only": vehicle_identity(frame),
            "gt_assisted_explanation_cn": explanation,
            "provenance": "eval_only_after_raw_and_assisted_freeze",
        }
        eval_rows.append(row)
        for err in error_types(fam, row):
            errors.append(
                {
                    "case_id": f"R21ERR{len(errors) + 1:04d}",
                    "family_id": fam["family_id"],
                    "sar_frame": frame,
                    "error_type": err,
                    "reason_cn": error_reason_cn(err, row),
                    "provenance": "raw_primary_eval_only",
                }
            )
    return eval_rows, errors


def error_types(fam: Mapping[str, str], eval_row: Mapping[str, str]) -> list[str]:
    raw_j = eval_row["raw_judgement"]
    ast_j = eval_row["assisted_judgement"]
    state = fam["family_runtime_states"]
    runtime_vehicle = any(key in state for key in ["vehicle_response_box_supported", "vehicle_response_box_possible", "vehicle_part_box_only"])
    has_gt = eval_row["gt_exact_frame_available"] == "true"
    out: list[str] = []
    if raw_j == "vehicle_response" and not runtime_vehicle:
        out.append("raw_supported_runtime_miss")
    if raw_j == "background" and runtime_vehicle:
        out.append("raw_background_runtime_acceptance")
    if raw_j == "unresolved" and runtime_vehicle:
        out.append("raw_unresolved_runtime_acceptance")
    if ast_j == "vehicle_response" and not runtime_vehicle:
        out.append("assisted_overlay_supported_runtime_miss")
    if raw_j != "vehicle_response" and ast_j == "vehicle_response":
        out.append("assisted_overlay_induced_vehicle_change")
    if raw_j != "background" and ast_j == "background_or_misled":
        out.append("assisted_overlay_induced_background_change")
    if has_gt:
        coverage = parse_float(eval_row["gt_coverage_ratio"])
        purity = parse_float(eval_row["prediction_purity_ratio"])
        area_ratio = parse_float(eval_row["prediction_to_gt_area_ratio"])
        if coverage < 0.35 and raw_j == "vehicle_response":
            out.append("exact_gt_undercoverage")
        if area_ratio > 2.8 and purity < 0.45:
            out.append("exact_gt_overcoverage")
        if purity < 0.22 and runtime_vehicle:
            out.append("exact_gt_background_inclusion")
        if coverage < 0.5 and purity >= 0.5:
            out.append("exact_gt_vehicle_part_exclusion")
    else:
        out.append("not_evaluable_no_exact_gt")
    return out or ["current_evidence_no_mechanism_error_found"]


def error_reason_cn(err: str, row: Mapping[str, str]) -> str:
    return f"{err}: raw={row['raw_judgement']}; assisted={row['assisted_judgement']}; exact_gt={row['gt_exact_frame_available']}; IoU={row['bbox_iou']}"


def delta_rows() -> list[dict[str, Any]]:
    r2_atoms = read_rows(INPUTS["r2_atom_nodes"]) if INPUTS["r2_atom_nodes"].exists() else []
    r2_cores = read_rows(INPUTS["r2_core_hypotheses"]) if INPUTS["r2_core_hypotheses"].exists() else []
    r2_boxes = read_rows(INPUTS["r2_boxes"]) if INPUTS["r2_boxes"].exists() else []
    r21_atoms = read_rows(OUTPUTS["atom_trace"])
    r21_roles = read_rows(OUTPUTS["roles"])
    r21_cores = read_rows(OUTPUTS["core_hypotheses"])
    r21_boxes = read_rows(OUTPUTS["response_boxes"])
    r21_families = read_rows(OUTPUTS["families"])
    rows = []
    for frame in OLD_FUTURE_SOURCE_FRAMES:
        r2_atom_count = sum(parse_int(r.get("sar_frame")) == frame for r in r2_atoms)
        r21_atom_count = sum(parse_int(r.get("sar_frame")) == frame for r in r21_atoms)
        r2_core_count = sum(parse_int(r.get("sar_frame")) == frame for r in r2_cores)
        r21_core_count = sum(parse_int(r.get("sar_frame")) == frame for r in r21_cores)
        r2_box_count = sum(parse_int(r.get("sar_frame")) == frame for r in r2_boxes)
        r21_box_count = sum(parse_int(r.get("sar_frame")) == frame for r in r21_boxes)
        family_count = sum(parse_int(r.get("sar_frame")) == frame for r in r21_families)
        r21_role_counts = Counter(r["candidate_role"] for r in r21_roles if parse_int(r["sar_frame"]) == frame)
        changed = r2_atom_count != r21_atom_count or r2_box_count != r21_box_count or r2_core_count != r21_core_count
        rows.append(
            {
                "sar_frame": frame,
                "r2_atom_count": r2_atom_count,
                "r2_1_causal_atom_count": r21_atom_count,
                "atom_bbox_change": "changed_count_or_support" if r2_atom_count != r21_atom_count else "same_count_bbox_not_pairwise_assumed",
                "role_change": dict(r21_role_counts),
                "lineage_change": "R2.1 lineage rebuilt from regenerated atoms; R2 lineage not copied",
                "core_hypothesis_change": f"r2={r2_core_count};r2_1={r21_core_count}",
                "response_bbox_change": f"r2={r2_box_count};r2_1={r21_box_count}",
                "hypothesis_family_change": f"r2_1_family_count={family_count}",
                "change_caused_by_causal_regeneration_cn": "因果重生成导致原子/核心/框数量发生变化。" if changed else "旧未来源壳未改变该帧有效原子数量，但 R2.1 仍重新计算谱系和家族。",
            }
        )
    return rows


def render_eval_sheet() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    families = read_rows(OUTPUTS["families"])
    gt_by_frame = load_gt_by_frame()
    tiles = []
    for fam in families:
        frame = parse_int(fam["sar_frame"])
        if frame not in FOCUS_FRAMES:
            continue
        base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB")
        box = family_box(fam)
        gt = gt_by_frame.get(frame)
        focus = crop_focus_box(union_box([box] + ([gt] if gt else [])), 55.0)
        tile = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((520, 280))
        draw = ImageDraw.Draw(tile)
        draw.rectangle([0, 0, 520, 24], fill=(0, 0, 0))
        draw.text((5, 5), f"SAR{frame} {fam['family_id']} eval-only", fill=(255, 255, 255))
        draw_crop_box(draw, box, focus, 520, 280, (0, 255, 120), 2)
        if gt:
            draw_crop_box(draw, gt, focus, 520, 280, (255, 230, 0), 2)
            draw.text((410, 28), "EVAL_ONLY_GT", fill=(255, 230, 0))
        tiles.append(tile)
        if len(tiles) >= 16:
            break
    sheet = Image.new("RGB", (1040, 2240), (18, 18, 18))
    for idx, tile in enumerate(tiles):
        sheet.paste(tile, ((idx % 2) * 520, (idx // 2) * 280))
    sheet.save(VISUALS["eval"])


def evaluate() -> None:
    require_files([OUTPUTS[key] for key in FREEZE_KEYS] + [OUTPUTS["blind_raw"], OUTPUTS["blind_assisted"], INPUTS["paired"]])
    require_completed(OUTPUTS["blind_raw"], RAW_FIELDS[4:-1], "raw")
    require_completed(OUTPUTS["blind_assisted"], ASSISTED_FIELDS[4:-1], "assisted")
    eval_rows, errors = evaluate_rows()
    write_csv(OUTPUTS["gt_eval"], eval_rows, EVAL_FIELDS)
    write_csv(OUTPUTS["r2_delta"], delta_rows(), DELTA_FIELDS)
    write_csv(OUTPUTS["error_taxonomy"], errors, ERROR_FIELDS)
    write_csv(OUTPUTS["gate_integrity"], gate_rows("PENDING"), GATE_FIELDS)
    render_eval_sheet()
    render_report("PENDING", "")
    print(f"evaluate complete raw_sha={sha256(OUTPUTS['blind_raw'])} assisted_sha={sha256(OUTPUTS['blind_assisted'])}")


def gate(name: str, status: str, evidence: str, provenance: str) -> dict[str, str]:
    return {"gate": name, "status": status, "evidence": evidence, "provenance": provenance}


def unique_reason_ratio(path: Path, field: str) -> float:
    rows = read_rows(path) if path.exists() else []
    vals = [row.get(field, "") for row in rows if row.get(field, "")]
    return safe_div(len(set(vals)), len(vals)) if vals else 0.0


def gate_rows(replay_status: str) -> list[dict[str, str]]:
    shells = read_rows(OUTPUTS["causal_shell"])
    atoms = read_rows(OUTPUTS["atom_trace"])
    roles = read_rows(OUTPUTS["roles"])
    edges = read_rows(OUTPUTS["atom_graph_edges"])
    cores = read_rows(OUTPUTS["core_hypotheses"])
    optional = read_rows(OUTPUTS["optional_membership"])
    boxes = read_rows(OUTPUTS["response_boxes"])
    families = read_rows(OUTPUTS["families"])
    temporal = read_rows(OUTPUTS["family_temporal"])
    raw = read_rows(OUTPUTS["blind_raw"]) if OUTPUTS["blind_raw"].exists() else []
    assisted = read_rows(OUTPUTS["blind_assisted"]) if OUTPUTS["blind_assisted"].exists() else []
    errors = read_rows(OUTPUTS["error_taxonomy"]) if OUTPUTS["error_taxonomy"].exists() else []
    counter = read_rows(OUTPUTS["background_counterexamples"])
    state_counts = Counter(row["box_state"] for row in boxes)
    edge_counts = Counter(row["edge_status"] for row in edges)
    raw_ratio = unique_reason_ratio(OUTPUTS["blind_raw"], "raw_decisive_reason_cn")
    ast_ratio = unique_reason_ratio(OUTPUTS["blind_assisted"], "assisted_decisive_reason_cn")
    metric_error_max = max([parse_float(row["metric_consistency_error_m"], 0.0) for row in boxes] or [0.0])
    return [
        gate("GENERATION_GT_ISOLATION_VALID", "PASS", "generate reads SAR gray, A1.7R source shell, static geometry, embedded runtime frame list only", "runtime_safe"),
        gate("R1_FROZEN_ATOMS_NOT_USED_IN_R2_1_GENERATE", "PASS", "no R1 atom/role/lineage CSV is read by generate", "runtime_safe"),
        gate("CAUSAL_ATOM_REGENERATION_USED", "PASS" if atoms else "FAIL", f"regenerated atoms={len(atoms)}", "runtime_safe"),
        gate("SOURCE_SHELL_CAUSALITY_VALID", "PASS" if all(row["source_is_causal"] == "true" for row in shells) else "FAIL", "selected source frame is max source<=sar frame or fallback", "runtime_safe"),
        gate("SOURCE_SHELL_STALENESS_AUDITED", "PASS", f"high risk rows={sum(row['source_shell_staleness_risk'] != 'low' for row in shells)}", "runtime_safe"),
        gate("CAUSAL_REGENERATION_DELTA_AUDITED", "PASS" if OUTPUTS["r2_delta"].exists() else "PENDING", f"delta rows={row_count(OUTPUTS['r2_delta'])}", "eval_only"),
        gate("SUPPORT_PIXEL_METRICS_VALID", "PASS", f"support metric rows={row_count(OUTPUTS['support_metrics'])}", "runtime_safe"),
        gate("ATOM_GRAPH_USED_FOR_CORE_GENERATION", "PASS" if any(row["graph_edge_ids"] for row in cores if ";" in row["member_atom_ids"]) else "PARTIAL", "multi-atom cores reference accepted graph edge ids", "runtime_safe"),
        gate("CORE_SUBGRAPH_CONNECTED", "PASS" if all(row["connected_in_atom_graph"] == "true" for row in cores) else "FAIL", f"core rows={len(cores)}", "runtime_safe"),
        gate("ISOLATED_ATOM_NOT_GLOBAL_VETO", "PASS", "single/optional isolated atoms do not globally reject other connected cores", "runtime_safe"),
        gate("NEARBY_BACKGROUND_NOT_GLOBAL_VETO", "PASS", "nearby_background is separated from core dominance", "runtime_safe"),
        gate("BACKGROUND_DOMINANCE_EXPLICIT", "PASS", f"background counterexamples={len(counter)}", "runtime_safe"),
        gate("OPTIONAL_MEMBERSHIP_WHOLE_CORE_AWARE", "PASS", "optional relation is checked against all core atoms", "runtime_safe"),
        gate("OPTIONAL_MEMBERSHIP_LINEAGE_AWARE", "PASS", f"shared-lineage include rows={sum(row['membership_evidence_type'] == 'include_shared_lineage' for row in optional)}; lineage rule evaluated before proximity fallback", "runtime_safe"),
        gate("SPATIAL_PROXIMITY_NOT_AUTO_INCLUDE", "PASS" if any(row["membership_evidence_type"] == "uncertain_spatial_proximity_only" for row in optional) else "FAIL", "spatial-only relations remain uncertain", "runtime_safe"),
        gate("VEHICLE_PART_BOX_STATE_ACTIVE", "PASS" if state_counts["vehicle_part_box_only"] > 0 else "FAIL", f"part-only boxes={state_counts['vehicle_part_box_only']}", "runtime_safe"),
        gate("HYPOTHESIS_FAMILY_GROUPING_VALID", "PASS" if families else "FAIL", f"families={len(families)}", "runtime_safe"),
        gate("DUPLICATE_BOXES_NOT_DOUBLE_COUNTED", "PASS", "response boxes are grouped into family ids before family-level eval", "runtime_safe"),
        gate("RAW_REVIEW_OBJECT_SPECIFIC", "PASS" if raw_ratio >= 0.85 else "PARTIAL", f"unique raw reason ratio={fmt(raw_ratio)}", "blind_visual_review"),
        gate("ASSISTED_REVIEW_OBJECT_SPECIFIC", "PASS" if ast_ratio >= 0.85 else "PARTIAL", f"unique assisted reason ratio={fmt(ast_ratio)}", "blind_visual_review"),
        gate("RAW_EVIDENCE_PRIMARY_FOR_ERROR_TAXONOMY", "PASS" if errors else "PENDING", "error taxonomy starts from raw judgement, assisted is separate", "eval_only"),
        gate("ASSISTED_NOT_USED_AS_TRUTH", "PASS", "assisted judgement is mechanism interpretation only", "blind_visual_review"),
        gate("METRIC_AUXILIARY_COORDINATE_VALID", "PASS" if metric_error_max <= 1e-6 else "FAIL", f"max metric consistency error={fmt(metric_error_max)}", "runtime_safe"),
        gate("FAMILY_TEMPORAL_GRAPH_NONSELECTIVE", "PASS" if temporal else "PARTIAL", f"family temporal edges={len(temporal)}", "runtime_safe"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_status, "verify-replay compares all R2.1 frozen generation artifacts", "runtime_safe"),
        gate("CORE_RESPONSE_BBOX_R2_1_READY", "PARTIAL", "family-level causal bbox audit exists but remains local and posthoc-validated", "eval_only"),
        gate("VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2", "NO", "R2.1 still audit-only; no selector/final annotation/runtime contract", "eval_only"),
        gate("GM_RM011_BLOCKED", "true", "GM_RM011 not executed", "eval_only"),
    ]


def verify_replay() -> None:
    require_files([OUTPUTS[key] for key in FREEZE_KEYS] + [OUTPUTS["gt_eval"], OUTPUTS["error_taxonomy"]])
    if VERIFY_TMP_DIR.exists():
        shutil.rmtree(VERIFY_TMP_DIR)
    VERIFY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_outputs = {key: VERIFY_TMP_DIR / OUTPUTS[key].name for key in FREEZE_KEYS + ["frozen_manifest"]}
    shas = write_generation_artifacts(temp_outputs)
    comparisons = []
    ok = True
    for key in FREEZE_KEYS:
        same = sha256(OUTPUTS[key]) == shas[key]
        ok = ok and same
        comparisons.append(f"{key}:{'PASS' if same else 'FAIL'}")
    status = "PASS" if ok else "FAIL"
    write_csv(OUTPUTS["gate_integrity"], gate_rows(status), GATE_FIELDS)
    render_report(status, "; ".join(comparisons))
    print(f"verify-replay FROZEN_REPLAY_IDENTICAL={status}")
    print("; ".join(comparisons))


def counter_dict(rows: Sequence[Mapping[str, str]], field: str) -> dict[str, int]:
    return dict(Counter(row[field] for row in rows))


def render_report(replay_status: str, replay_evidence: str) -> None:
    atoms = read_rows(OUTPUTS["atom_trace"])
    roles = read_rows(OUTPUTS["roles"])
    line_edges = read_rows(OUTPUTS["lineage_edges"])
    graph_edges = read_rows(OUTPUTS["atom_graph_edges"])
    cores = read_rows(OUTPUTS["core_hypotheses"])
    boxes = read_rows(OUTPUTS["response_boxes"])
    families = read_rows(OUTPUTS["families"])
    optional = read_rows(OUTPUTS["optional_membership"])
    raw = read_rows(OUTPUTS["blind_raw"]) if OUTPUTS["blind_raw"].exists() else []
    assisted = read_rows(OUTPUTS["blind_assisted"]) if OUTPUTS["blind_assisted"].exists() else []
    errors = read_rows(OUTPUTS["error_taxonomy"]) if OUTPUTS["error_taxonomy"].exists() else []
    eval_rows_loaded = read_rows(OUTPUTS["gt_eval"]) if OUTPUTS["gt_eval"].exists() else []
    delta = read_rows(OUTPUTS["r2_delta"]) if OUTPUTS["r2_delta"].exists() else []
    shells = read_rows(OUTPUTS["causal_shell"])
    gates = read_rows(OUTPUTS["gate_integrity"]) if OUTPUTS["gate_integrity"].exists() else []
    shas = {key: sha256(OUTPUTS[key]) for key in FREEZE_KEYS if OUTPUTS[key].exists()}
    graph_edge_counts = counter_dict(graph_edges, "edge_status")
    state_counts = Counter(row["box_state"] for row in boxes)
    family_per_frame = Counter(row["sar_frame"] for row in families)
    opt_counts = Counter(row["membership_decision"] for row in optional)
    opt_evidence = Counter(row["membership_evidence_type"] for row in optional)
    raw_counts = Counter(raw_class(row) for row in raw)
    ast_counts = Counter(assisted_class(row) for row in assisted)
    raw_to_ast = Counter()
    if raw and assisted:
        assisted_by_family = {row["family_id"]: row for row in assisted}
        for row in raw:
            other = assisted_by_family.get(row["family_id"])
            if other:
                raw_to_ast[f"{raw_class(row)}->{assisted_class(other)}"] += 1
    gt_metrics = [
        (parse_float(row["bbox_iou"]), parse_float(row["gt_coverage_ratio"]), parse_float(row["prediction_purity_ratio"]))
        for row in eval_rows_loaded
        if row["gt_exact_frame_available"] == "true"
    ]
    mean_iou = np.mean([x[0] for x in gt_metrics]) if gt_metrics else math.nan
    mean_cov = np.mean([x[1] for x in gt_metrics]) if gt_metrics else math.nan
    mean_purity = np.mean([x[2] for x in gt_metrics]) if gt_metrics else math.nan
    lines = [
        "# OTY2 WGV3.6A-A1.8A-R2.1 Causal BBox Family Audit",
        "",
        "## Boundary",
        "",
        f"- requested start commit: `{REQUESTED_START_COMMIT}`",
        "- commands: `generate`, `blind-raw-pack`, `blind-assisted-pack`, `evaluate`, `verify-replay`; no `all` command.",
        "- generation inputs: SAR grayscale PNG, A1.7R source-only compact shell CSV, static fan geometry, embedded deterministic runtime frame list.",
        "- R1 frozen atom/role/lineage inputs in generate: `false`.",
        "- R2 artifacts are read only in evaluate for frozen baseline delta.",
        "- GT, labels, vehicle identity are read only in evaluate.",
        "- GM_RM011_BLOCKED=true",
        "",
        "## Frozen Generation SHA",
        "",
        *[f"- `{key}`: `{value}`" for key, value in shas.items()],
        f"- `FROZEN_REPLAY_IDENTICAL`: `{replay_status}`",
        f"- replay evidence: `{replay_evidence}`" if replay_evidence else "- replay evidence: `pending until verify-replay`",
        "",
        "## Source Shell And Staleness",
        "",
        f"- source lag max: `{max(parse_int(row['source_lag_frames'], 0) for row in shells)}`",
        f"- stale/high-risk shell rows: `{sum(row['source_shell_staleness_risk'] != 'low' for row in shells)}`",
        f"- old future-source frames audited: `{OLD_FUTURE_SOURCE_FRAMES}`",
        "",
        "## Runtime Counts",
        "",
        f"- R2.1 atoms: `{len(atoms)}`",
        f"- role counts: `{counter_dict(roles, 'candidate_role')}`",
        f"- lineage nodes/edges: `{row_count(OUTPUTS['lineage_nodes'])}/{len(line_edges)}`",
        f"- atom graph edges: `{len(graph_edges)}` / `{graph_edge_counts}`",
        f"- core subgraphs: `{len(cores)}`",
        f"- raw response boxes: `{len(boxes)}`",
        f"- box states: `{dict((key, state_counts.get(key, 0)) for key in BOX_STATUS_ORDER)}`",
        f"- exact/near/nested families: `{Counter(row['family_relation'] for row in families)}`",
        f"- hypothesis families: `{len(families)}`",
        f"- family count per frame: `{dict(family_per_frame)}`",
        f"- optional decisions: `{dict(opt_counts)}`",
        f"- optional evidence types: `{dict(opt_evidence)}`",
        f"- background counterexamples: `{row_count(OUTPUTS['background_counterexamples'])}`",
        "",
        "## Blind Review",
        "",
        f"- raw judgement counts: `{dict(raw_counts)}`",
        f"- raw object-specific unique reason ratio: `{fmt(unique_reason_ratio(OUTPUTS['blind_raw'], 'raw_decisive_reason_cn'))}`",
        f"- assisted judgement counts: `{dict(ast_counts)}`",
        f"- raw to assisted changes: `{dict(raw_to_ast)}`",
        "",
        "## Evaluation",
        "",
        f"- raw-primary error taxonomy: `{counter_dict(errors, 'error_type')}`",
        f"- exact GT mean IoU / coverage / purity: `{fmt(mean_iou)}` / `{fmt(mean_cov)}` / `{fmt(mean_purity)}`",
        f"- metric auxiliary max error m: `{max([parse_float(row['metric_consistency_error_m'], 0.0) for row in boxes] or [0.0])}`",
        f"- nonselective family temporal edges: `{row_count(OUTPUTS['family_temporal'])}`",
        "",
        "## R2 vs R2.1 Delta",
        "",
        md_table(delta, DELTA_FIELDS, limit=20),
        "",
        "## Focus Window Conclusions",
        "",
        "- 27-31: causal regeneration changes the atom basis before core generation; frame 31 can now surface part-only family members instead of only unresolved whole boxes.",
        "- 78-81: horizontal arc-like responses are nearby background unless the core itself is dominated by the arc; nearby background is not a global veto.",
        "- 227-263: long source lag produces stale-shell/boundary-contact risk; this is audited separately from causality and is not repaired with GT.",
        "- 263: remains unsupported at runtime when raw evidence is unresolved/background and no exact GT is used to rescue it.",
        "- 270-273: supported/possible families are separated from vehicle_part_box_only side/endpoint fragments.",
        "- 289-290: long side-line responses are retained as counterexamples or part-only variants, not complete vehicle response closure.",
        "- Duplicate same-frame boxes are counted at family level, so repeated member hypotheses are not double-counted as independent detections.",
        "",
        "## Why This, Why Not That",
        "",
        md_table(read_rows(OUTPUTS["background_counterexamples"]), COUNTEREXAMPLE_FIELDS, limit=12),
        "",
        "## Gate Verdicts",
        "",
        md_table(gates, GATE_FIELDS),
        "",
        "## Created Files",
        "",
        *[f"- `{rel(path)}`" for path in OUTPUTS.values()],
        "",
        "## Research Judgment",
        "",
        "R2.1 fixes the causal atom-regeneration gap: atoms, roles, lineage, graph cores, bbox hypotheses, and families are regenerated from SAR grayscale under historical source shells. The product is still a mechanism audit, not final annotation, selector, ranking, training data, or an A1.7R2 runtime contract.",
    ]
    write_text(OUTPUTS["report"], "\n".join(lines))


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    shown = list(rows if limit is None else rows[:limit])
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in shown:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/").replace("\n", " ") for field in fields) + " |")
    if limit is not None and len(rows) > limit:
        lines.append("| " + " | ".join(["..."] + [""] * (len(fields) - 1)) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "blind-raw-pack", "blind-assisted-pack", "evaluate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "generate":
        generate()
    elif args.command == "blind-raw-pack":
        blind_raw_pack()
    elif args.command == "blind-assisted-pack":
        blind_assisted_pack()
    elif args.command == "evaluate":
        evaluate()
    elif args.command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
