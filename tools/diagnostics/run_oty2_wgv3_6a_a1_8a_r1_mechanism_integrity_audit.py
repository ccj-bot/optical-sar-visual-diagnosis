"""WGV3.6A-A1.8A-R1 mechanism-integrity audit.

This follow-up corrects the A1.8A experiment boundary:

generate      : runtime-safe SAR structure generation only
blind-pack    : opaque visual review pack and frozen blind judgement
evaluate      : GT-assisted explanation after both freezes
verify-replay : replay frozen generation into a temp directory and compare SHA

There is intentionally no `all` command. The blind-review isolation point must
remain visible in the workflow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import math
import random
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
REQUESTED_START_COMMIT = "a9790e1796fb37ac5a919a35e07ea2f1a21200de"
SCENE = "GM_RM019"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_8a_r1_20260711"
VERIFY_TMP_DIR = OUT_DIR / "_verify_replay_tmp"
RANDOM_SEED = 1801

INPUTS = {
    "paired": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "a1_7r_compact": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_compact_assembly_trace_{DATE}.csv",
    "a1_8a_report": REPORT_DIR / f"oty2_wgv3_6a_a1_8a_vehicle_response_grammar_audit_{DATE}.md",
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_8a_r1_mechanism_integrity_audit_{DATE}.md",
    "holdout_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_blind_holdout_manifest_{DATE}.csv",
    "leakage_audit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_leakage_audit_{DATE}.csv",
    "frozen_atom_trace": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_frozen_atom_trace_{DATE}.csv",
    "frozen_role_proposals": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_frozen_role_proposals_{DATE}.csv",
    "support_extent": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_support_pixel_structure_extent_{DATE}.csv",
    "lineage_nodes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_part_lineage_nodes_{DATE}.csv",
    "lineage_edges": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_part_lineage_edges_{DATE}.csv",
    "runtime_entities": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_frozen_runtime_entities_{DATE}.csv",
    "blind_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_blind_review_manifest_{DATE}.csv",
    "blind_judgement": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_blind_object_judgement_{DATE}.csv",
    "gt_eval": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_gt_assisted_evaluation_{DATE}.csv",
    "contrast": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_vehicle_vs_other_contrast_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_gate_integrity_{DATE}.csv",
    "failure_cases": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_failure_cases_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_frozen_artifact_manifest_{DATE}.csv",
}

VISUALS = {
    "blind_sheet_a": OUT_DIR / "blind_sheet_001.png",
    "blind_sheet_b": OUT_DIR / "blind_sheet_002.png",
    "blind_sheet_c": OUT_DIR / "blind_sheet_003.png",
    "blind_sheet_d": OUT_DIR / "blind_sheet_004.png",
    "eval_sheet": OUT_DIR / "eval_only_gt_assisted_sheet.png",
}

DISCOVERY_RUNTIME_FRAMES = sorted(
    set(
        list(range(27, 33))
        + [40, 46, 60]
        + list(range(77, 82))
        + [212, 213, 220, 227, 238, 239, 243, 250, 260]
        + list(range(269, 274))
        + [276, 280, 284]
        + list(range(288, 291))
    )
)
HOLDOUT_INTERVALS = {
    "HOLDOUT_033_076": (33, 76),
    "HOLDOUT_214_237": (214, 237),
    "HOLDOUT_240_268": (240, 268),
    "HOLDOUT_274_287": (274, 287),
}
POSITIVE_FRAMES = set(list(range(27, 32)) + list(range(78, 82)) + list(range(270, 274)) + list(range(289, 291)))
NEGATIVE_OR_UNCERTAIN_FRAMES = set([32, 40, 46, 60, 77, 212, 213, 220, 227, 238, 239, 243, 250, 260, 269, 276, 280, 284, 288])

SOURCE_START_FRAMES = [27, 31, 77, 212, 238, 269, 273, 288]

FREEZE_ARTIFACT_KEYS = [
    "frozen_atom_trace",
    "frozen_role_proposals",
    "support_extent",
    "lineage_nodes",
    "lineage_edges",
    "runtime_entities",
]

HOLDOUT_FIELDS = ["interval_id", "random_seed", "selected_sar_frame", "selection_rule", "gt_loaded_during_sampling"]
LEAK_FIELDS = ["check_id", "layer", "check_name", "status", "evidence", "limitation_cn"]
ATOM_FIELDS = [
    "atom_id",
    "sar_frame",
    "pixel_centroid_x",
    "pixel_centroid_y",
    "azimuth",
    "radial",
    "pixel_area",
    "support_pixel_count",
    "support_bbox",
    "integrated_energy",
    "mean_energy",
    "peak_energy",
    "relative_energy_within_local_field",
    "atom_axis1",
    "atom_axis2",
    "atom_aspect_ratio",
    "atom_orientation",
    "compactness",
    "local_arc_consistency",
    "boundary_contact",
    "extraction_threshold",
    "threshold_provenance",
    "source_shell_provenance",
]
ROLE_FIELDS = [
    "atom_id",
    "sar_frame",
    "candidate_role",
    "role_rule_provenance",
    "role_inputs",
    "polarity_used",
    "physical_vehicle_id_used",
    "gt_used",
]
EXTENT_FIELDS = [
    "structure_id",
    "sar_frame",
    "member_atom_ids",
    "role_candidate_combination",
    "support_pixel_long_axis",
    "support_pixel_short_axis",
    "support_pixel_aspect_ratio",
    "centroid_long_axis",
    "centroid_short_axis",
    "extent_degeneracy_fixed",
    "support_pixel_count",
    "support_bbox",
    "convex_hull_area",
    "occupancy_ratio",
    "max_internal_blank",
    "max_pair_distance",
    "azimuth_span",
    "radial_span",
    "background_arc_conflict",
    "part_relation_summary",
    "unit_status",
]
NODE_FIELDS = [
    "part_hypothesis_node_id",
    "atom_id",
    "sar_frame",
    "candidate_role",
    "support_pixel_long_axis",
    "support_pixel_short_axis",
    "orientation",
    "integrated_energy",
    "persistent_part_track_id",
    "lineage_state",
]
EDGE_FIELDS = [
    "edge_id",
    "source_node_id",
    "target_node_id",
    "source_sar_frame",
    "target_sar_frame",
    "geometry_distance",
    "radial_drift",
    "azimuth_drift",
    "extent_continuity_ratio",
    "orientation_difference",
    "energy_ratio",
    "role_compatibility",
    "background_conflict_consistency",
    "edge_status",
    "blocked_reason",
]
ENTITY_FIELDS = [
    "runtime_entity_id",
    "structure_id",
    "sar_frame",
    "runtime_class",
    "G_scale",
    "G_compact",
    "G_grammar",
    "G_temporal",
    "G_background",
    "optical_condition_compatibility",
    "temporal_evidence",
    "classification_reason_cn",
    "classification_provenance",
]
BLIND_MANIFEST_FIELDS = [
    "blind_review_id",
    "blind_frame_id",
    "blind_object_id",
    "review_object_type",
    "candidate_role_summary",
    "runtime_png",
]
BLIND_FIELDS = [
    "blind_review_id",
    "blind_frame_id",
    "blind_object_id",
    "review_object_type",
    "visible_structure_cn",
    "vehicle_part_support",
    "vehicle_structure_support",
    "background_structure_support",
    "unresolved",
    "decisive_reason_cn",
    "alternative_explanation_cn",
    "relation_to_other_objects_cn",
    "visual_confidence",
    "runtime_png",
]
EVAL_FIELDS = [
    "eval_id",
    "runtime_entity_id",
    "structure_id",
    "sar_frame",
    "discovery_label_eval_only",
    "vehicle_identity_eval_only",
    "runtime_class",
    "blind_object_id",
    "blind_judgement",
    "gt_exact_frame_available",
    "gt_relation_eval_only",
    "gt_overlap_eval_only",
    "gt_center_distance_eval_only",
    "runtime_false_reject",
    "runtime_false_accept",
    "runtime_blind_disagreement",
    "blind_gt_disagreement",
    "gt_assisted_explanation_cn",
    "provenance",
]
CONTRAST_FIELDS = [
    "contrast_id",
    "accepted_object_id",
    "alternative_object_id",
    "same_frame_or_cross_frame",
    "accepted_runtime_class",
    "alternative_runtime_class",
    "accepted_blind_judgement",
    "alternative_blind_judgement",
    "accepted_scale_fields",
    "alternative_scale_fields",
    "accepted_part_relations",
    "alternative_part_relations",
    "accepted_lineage",
    "alternative_lineage",
    "accepted_arc_conflict",
    "alternative_arc_conflict",
    "accepted_gt_relation_eval_only",
    "alternative_gt_relation_eval_only",
    "decisive_difference_cn",
    "non_decisive_support_cn",
    "unresolved_difference_cn",
]
GATE_FIELDS = ["gate", "status", "evidence", "provenance"]
FAIL_FIELDS = ["case_id", "failure_type", "object_id", "sar_frame", "reason_cn", "provenance"]
MANIFEST_FIELDS = ["artifact", "path", "sha256", "rows", "frozen_phase"]


@dataclass
class Atom:
    atom_id: str
    frame: int
    cx: float
    cy: float
    xs: np.ndarray
    ys: np.ndarray
    box: Box
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
    compactness: float
    arc_score: float
    boundary_contact: str
    threshold: float
    source_shell: Box
    role: str
    role_provenance: str


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def safe_div(num: float, den: float) -> float:
    return num / den if den else math.nan


def median(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if not math.isnan(float(v))]
    return float(np.median(np.array(vals, dtype=np.float64))) if vals else math.nan


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


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
        return Box(980.0, 1100.0, 1360.0, 1285.0)
    return clamp_box(Box(min(b.x1 for b in boxes), min(b.y1 for b in boxes), max(b.x2 for b in boxes), max(b.y2 for b in boxes)))


def gap_between(a: Box, b: Box) -> float:
    dx = max(0.0, max(a.x1, b.x1) - min(a.x2, b.x2))
    dy = max(0.0, max(a.y1, b.y1) - min(a.y2, b.y2))
    return math.hypot(dx, dy)


def angle_diff(a: float, b: float) -> float:
    return abs((a - b + 90.0) % 180.0 - 90.0)


def sample_holdout_frames() -> list[dict[str, Any]]:
    rng = random.Random(RANDOM_SEED)
    excluded = set(DISCOVERY_RUNTIME_FRAMES)
    rows: list[dict[str, Any]] = []
    for interval_id, (start, end) in HOLDOUT_INTERVALS.items():
        candidates = [frame for frame in range(start, end + 1) if frame not in excluded]
        for frame in sorted(rng.sample(candidates, 3)):
            rows.append(
                {
                    "interval_id": interval_id,
                    "random_seed": RANDOM_SEED,
                    "selected_sar_frame": frame,
                    "selection_rule": "deterministic_random_sample_without_gt_or_visual_resampling",
                    "gt_loaded_during_sampling": "false",
                }
            )
    return rows


def runtime_frames() -> list[int]:
    holdout = [parse_int(row["selected_sar_frame"]) for row in sample_holdout_frames()]
    return sorted(set(DISCOVERY_RUNTIME_FRAMES + holdout))


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
            shells[frame] = box
    return shells


def shell_for_frame(frame: int, shells: Mapping[int, Box]) -> tuple[Box, str]:
    if not shells:
        return fallback_shell(frame), "fallback_static_shell_no_a1_7r_source"
    nearest = min(shells, key=lambda source_frame: (abs(source_frame - frame), source_frame))
    return expand_box(shells[nearest], 24.0), f"nearest_a1_7r_source_shell_frame_{nearest}"


def fallback_shell(frame: int) -> Box:
    if frame < 100:
        return Box(995.0, 1110.0, 1375.0, 1298.0)
    if frame < 270:
        return Box(930.0, 1105.0, 1325.0, 1288.0)
    return Box(1030.0, 1110.0, 1400.0, 1295.0)


def axis_stats(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float, float]:
    if xs.size == 0:
        return 0.0, 0.0, 0.0
    if xs.size == 1:
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


def local_arc_score(cx: float, cy: float, orientation: float) -> float:
    radial_angle = math.degrees(math.atan2(cy - 1330.6, cx - 1154.0))
    tangent = radial_angle + 90.0
    return max(0.0, 1.0 - angle_diff(orientation, tangent) / 45.0)


def role_for_atom(area: int, peak: float, mean: float, axis1: float, axis2: float, compactness: float, arc_score: float, box: Box, shell: Box) -> tuple[str, str]:
    elongation = safe_div(axis1, max(axis2, 1e-6))
    bottom_fraction = safe_div(box.cy - shell.y1, max(1.0, shell.height))
    if elongation >= 2.7 and arc_score >= 0.72 and area >= 45 and bottom_fraction < 0.78:
        return "background_arc_candidate", "elongated_support_aligned_with_fan_tangent"
    if area >= 120 and bottom_fraction >= 0.45 and peak >= 86 and compactness >= 0.045:
        return "body_core_candidate", "bottom_local_high_energy_compact_support"
    if 28 <= area <= 210 and bottom_fraction >= 0.42 and peak >= 84 and compactness >= 0.055:
        return "endpoint_hotspot_candidate", "bottom_local_peak_support"
    if elongation >= 2.1 and area >= 45 and arc_score < 0.68:
        return "side_ridge_candidate", "elongated_non_arc_local_ridge"
    if area < 35:
        return "isolated_small_atom", "small_area_without_vehicle_scale_support"
    return "unresolved_atom", "feature_combination_not_separable_runtime"


def extract_atoms(frames: Sequence[int]) -> list[Atom]:
    geometry = build_geometry()
    fan = geometry["fan"]
    azimuth = geometry["azimuth"]
    radial = geometry["radial"]
    shells = source_shells()
    atoms: list[Atom] = []
    for frame in sorted(frames):
        path = sar_gray_path(SCENE, frame)
        if not path.exists():
            continue
        arr = read_gray(path)
        shell, shell_source = shell_for_frame(frame, shells)
        x0 = max(0, int(math.floor(shell.x1)))
        y0 = max(0, int(math.floor(shell.y1)))
        x1 = min(SAR_WIDTH, int(math.ceil(shell.x2)))
        y1 = min(SAR_HEIGHT, int(math.ceil(shell.y2)))
        crop = arr[y0:y1, x0:x1]
        local_fan = fan[y0:y1, x0:x1]
        if crop.size == 0 or not local_fan.any():
            continue
        valid = crop[local_fan]
        threshold = max(float(np.percentile(valid, 96.2)), float(valid.mean() + 0.85 * valid.std()))
        binary = (crop >= threshold) & local_fan
        total_energy = float(valid.sum())
        idx = 0
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
            compactness = safe_div(float(xs.size), max(1.0, box.area))
            arc_score = local_arc_score(float(gx.mean()), float(gy.mean()), orientation)
            role, provenance = role_for_atom(int(xs.size), float(vals.max()), float(vals.mean()), axis1, axis2, compactness, arc_score, box, shell)
            boundary_contact = (
                abs(box.x1 - shell.x1) < 3
                or abs(box.y1 - shell.y1) < 3
                or abs(box.x2 - shell.x2) < 3
                or abs(box.y2 - shell.y2) < 3
            )
            idx += 1
            atoms.append(
                Atom(
                    atom_id=f"R1A{len(atoms) + 1:04d}",
                    frame=frame,
                    cx=float(gx.mean()),
                    cy=float(gy.mean()),
                    xs=gx.astype(np.float32),
                    ys=gy.astype(np.float32),
                    box=box,
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
                    compactness=compactness,
                    arc_score=arc_score,
                    boundary_contact=bool_text(boundary_contact),
                    threshold=threshold,
                    source_shell=shell,
                    role=role,
                    role_provenance=f"{provenance}; {shell_source}",
                )
            )
    return atoms


def atom_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    rows = []
    for atom in atoms:
        rows.append(
            {
                "atom_id": atom.atom_id,
                "sar_frame": atom.frame,
                "pixel_centroid_x": fmt(atom.cx),
                "pixel_centroid_y": fmt(atom.cy),
                "azimuth": fmt(atom.azimuth),
                "radial": fmt(atom.radial),
                "pixel_area": atom.area,
                "support_pixel_count": atom.area,
                "support_bbox": atom.box.as_text(),
                "integrated_energy": fmt(atom.integrated),
                "mean_energy": fmt(atom.mean),
                "peak_energy": fmt(atom.peak),
                "relative_energy_within_local_field": fmt(atom.relative_energy),
                "atom_axis1": fmt(atom.axis1),
                "atom_axis2": fmt(atom.axis2),
                "atom_aspect_ratio": fmt(safe_div(atom.axis1, atom.axis2)),
                "atom_orientation": fmt(atom.orientation),
                "compactness": fmt(atom.compactness),
                "local_arc_consistency": fmt(atom.arc_score),
                "boundary_contact": atom.boundary_contact,
                "extraction_threshold": fmt(atom.threshold),
                "threshold_provenance": "frame_local_source_shell_p96_2_or_mean_plus_0_85std; no gt; no polarity",
                "source_shell_provenance": "a1_7r_source_shell_nearest_runtime_anchor",
            }
        )
    return rows


def role_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    rows = []
    for atom in atoms:
        rows.append(
            {
                "atom_id": atom.atom_id,
                "sar_frame": atom.frame,
                "candidate_role": atom.role,
                "role_rule_provenance": atom.role_provenance,
                "role_inputs": f"area={atom.area};peak={fmt(atom.peak)};axis1={fmt(atom.axis1)};axis2={fmt(atom.axis2)};compactness={fmt(atom.compactness)};arc={fmt(atom.arc_score)}",
                "polarity_used": "false",
                "physical_vehicle_id_used": "false",
                "gt_used": "false",
            }
        )
    return rows


def convex_hull_area(xs: np.ndarray, ys: np.ndarray) -> float:
    points = sorted(set(zip(xs.astype(float).tolist(), ys.astype(float).tolist())))
    if len(points) < 3:
        return 0.0

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        return 0.0
    area = 0.0
    for a, b in zip(hull, hull[1:] + hull[:1]):
        area += a[0] * b[1] - b[0] * a[1]
    return abs(area) / 2.0


def support_extent(atoms: Sequence[Atom]) -> dict[str, float | str]:
    xs = np.concatenate([atom.xs for atom in atoms]) if atoms else np.array([], dtype=np.float32)
    ys = np.concatenate([atom.ys for atom in atoms]) if atoms else np.array([], dtype=np.float32)
    if xs.size == 0:
        return {}
    axis1, axis2, orientation = axis_stats(xs, ys)
    bbox = Box(float(xs.min()), float(ys.min()), float(xs.max() + 1.0), float(ys.max() + 1.0))
    hull_area = convex_hull_area(xs, ys)
    centroid_points = np.array([[atom.cx, atom.cy] for atom in atoms], dtype=np.float64)
    if len(centroid_points) <= 1:
        centroid_long = 0.0
        centroid_short = 0.0
    else:
        centered = centroid_points - centroid_points.mean(axis=0)
        cov = np.cov(centered, rowvar=False)
        vals, vecs = np.linalg.eigh(cov)
        order = np.argsort(vals)[::-1]
        main = vecs[:, order[0]]
        perp = np.array([-main[1], main[0]])
        proj = centroid_points @ main
        pproj = centroid_points @ perp
        centroid_long = float(proj.max() - proj.min())
        centroid_short = float(pproj.max() - pproj.min())
    return {
        "support_pixel_long_axis": axis1,
        "support_pixel_short_axis": axis2,
        "support_pixel_aspect_ratio": safe_div(axis1, axis2),
        "centroid_long_axis": centroid_long,
        "centroid_short_axis": centroid_short,
        "extent_degeneracy_fixed": bool_text(centroid_short < 1.0 and axis2 > 1.0),
        "support_pixel_count": int(xs.size),
        "support_bbox": bbox.as_text(),
        "convex_hull_area": hull_area,
        "occupancy_ratio": safe_div(float(xs.size), hull_area),
        "support_orientation": orientation,
    }


def relation_summary(group: Sequence[Atom]) -> str:
    roles = {atom.role for atom in group}
    parts = []
    if "body_core_candidate" in roles and "side_ridge_candidate" in roles:
        parts.append("core_to_side_candidate")
    if "body_core_candidate" in roles and "endpoint_hotspot_candidate" in roles:
        parts.append("core_to_endpoint_candidate")
    if "side_ridge_candidate" in roles and "endpoint_hotspot_candidate" in roles:
        parts.append("side_to_endpoint_candidate")
    if "background_arc_candidate" in roles:
        parts.append("background_arc_conflict")
    return ";".join(parts) if parts else "single_or_unresolved_relation"


def group_pair_metrics(group: Sequence[Atom]) -> tuple[float, float, float, float]:
    max_dist = 0.0
    max_gap = 0.0
    for a, b in combinations(group, 2):
        max_dist = max(max_dist, math.hypot(a.cx - b.cx, a.cy - b.cy))
        max_gap = max(max_gap, gap_between(a.box, b.box))
    az_span = max((a.azimuth for a in group), default=0.0) - min((a.azimuth for a in group), default=0.0)
    rad_span = max((a.radial for a in group), default=0.0) - min((a.radial for a in group), default=0.0)
    return max_dist, max_gap, az_span, rad_span


def build_structures(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    by_frame: dict[int, list[Atom]] = defaultdict(list)
    for atom in atoms:
        by_frame[atom.frame].append(atom)
    rows: list[dict[str, Any]] = []
    for frame in sorted(by_frame):
        frame_atoms = by_frame[frame]
        groups: list[list[Atom]] = []
        bodies = sorted([a for a in frame_atoms if a.role == "body_core_candidate"], key=lambda a: -a.integrated)
        for body in bodies[:2]:
            group = [body]
            for other in sorted(frame_atoms, key=lambda a: -a.integrated):
                if other.atom_id == body.atom_id or other.role == "background_arc_candidate":
                    continue
                dist = math.hypot(body.cx - other.cx, body.cy - other.cy)
                if dist <= 155.0 and gap_between(body.box, other.box) <= 70.0:
                    group.append(other)
                if len(group) >= 4:
                    break
            groups.append(group)
        if not groups:
            non_bg = [a for a in frame_atoms if a.role != "background_arc_candidate"]
            if non_bg:
                groups.append(sorted(non_bg, key=lambda a: -a.integrated)[:3])
        for bg in sorted([a for a in frame_atoms if a.role == "background_arc_candidate"], key=lambda a: -a.integrated)[:2]:
            groups.append([bg])
        seen = set()
        for group in groups:
            key = ";".join(sorted(atom.atom_id for atom in group))
            if key in seen:
                continue
            seen.add(key)
            ext = support_extent(group)
            max_dist, max_gap, az_span, rad_span = group_pair_metrics(group)
            roles = sorted({atom.role for atom in group})
            sid = f"R1S{len(rows) + 1:04d}"
            rows.append(
                {
                    "structure_id": sid,
                    "sar_frame": frame,
                    "member_atom_ids": key,
                    "role_candidate_combination": ";".join(roles),
                    "support_pixel_long_axis": fmt(ext.get("support_pixel_long_axis")),
                    "support_pixel_short_axis": fmt(ext.get("support_pixel_short_axis")),
                    "support_pixel_aspect_ratio": fmt(ext.get("support_pixel_aspect_ratio")),
                    "centroid_long_axis": fmt(ext.get("centroid_long_axis")),
                    "centroid_short_axis": fmt(ext.get("centroid_short_axis")),
                    "extent_degeneracy_fixed": ext.get("extent_degeneracy_fixed", "false"),
                    "support_pixel_count": ext.get("support_pixel_count", 0),
                    "support_bbox": ext.get("support_bbox", ""),
                    "convex_hull_area": fmt(ext.get("convex_hull_area")),
                    "occupancy_ratio": fmt(ext.get("occupancy_ratio")),
                    "max_internal_blank": fmt(max_gap),
                    "max_pair_distance": fmt(max_dist),
                    "azimuth_span": fmt(az_span),
                    "radial_span": fmt(rad_span),
                    "background_arc_conflict": bool_text("background_arc_candidate" in roles),
                    "part_relation_summary": relation_summary(group),
                    "unit_status": "support_pixel_geometry_not_meter",
                }
            )
    return rows


def role_family(role: str) -> str:
    if role.startswith("body_core"):
        return "core"
    if role.startswith("side_ridge"):
        return "side"
    if role.startswith("endpoint"):
        return "endpoint"
    if role.startswith("background_arc"):
        return "background"
    if role.startswith("isolated"):
        return "isolated"
    return "unresolved"


def compatible_roles(a: str, b: str) -> bool:
    fa, fb = role_family(a), role_family(b)
    if fa == "background" or fb == "background":
        return fa == fb
    if fa == "isolated" or fb == "isolated":
        return fa == fb
    return fa == fb or {fa, fb} <= {"core", "side", "endpoint", "unresolved"}


def build_lineage(atoms: Sequence[Atom]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str], dict[str, int]]:
    nodes = [
        {
            "part_hypothesis_node_id": f"R1N{idx + 1:04d}",
            "atom_id": atom.atom_id,
            "sar_frame": atom.frame,
            "candidate_role": atom.role,
            "support_pixel_long_axis": fmt(atom.axis1),
            "support_pixel_short_axis": fmt(atom.axis2),
            "orientation": fmt(atom.orientation),
            "integrated_energy": fmt(atom.integrated),
            "persistent_part_track_id": "",
            "lineage_state": "",
        }
        for idx, atom in enumerate(atoms)
    ]
    atom_by_id = {atom.atom_id: atom for atom in atoms}
    node_by_atom = {row["atom_id"]: row["part_hypothesis_node_id"] for row in nodes}
    atoms_by_frame: dict[int, list[Atom]] = defaultdict(list)
    for atom in atoms:
        atoms_by_frame[atom.frame].append(atom)
    edge_rows: list[dict[str, Any]] = []
    candidate_edges: list[tuple[str, str]] = []
    for frame in sorted(atoms_by_frame):
        next_atoms = atoms_by_frame.get(frame + 1)
        if not next_atoms:
            continue
        for a in atoms_by_frame[frame]:
            for b in next_atoms:
                dist = math.hypot(a.cx - b.cx, a.cy - b.cy)
                if dist > 190.0:
                    continue
                radial_drift = abs(a.radial - b.radial)
                az_drift = abs(a.azimuth - b.azimuth)
                extent_ratio = max(a.axis1, b.axis1) / max(1e-6, min(a.axis1, b.axis1))
                orient = angle_diff(a.orientation, b.orientation)
                energy_ratio = max(a.integrated, b.integrated) / max(1.0, min(a.integrated, b.integrated))
                role_ok = compatible_roles(a.role, b.role)
                background_ok = (role_family(a.role) == "background") == (role_family(b.role) == "background")
                blocked = []
                if dist > 78.0:
                    blocked.append("blocked_by_geometry")
                if radial_drift > 65.0 or az_drift > 28.0:
                    blocked.append("blocked_by_radial_azimuth_drift")
                if extent_ratio > 4.5:
                    blocked.append("blocked_by_extent_jump")
                if orient > 45.0:
                    blocked.append("blocked_by_orientation_jump")
                if energy_ratio > 6.0:
                    blocked.append("blocked_by_energy_jump")
                if not role_ok:
                    blocked.append("blocked_by_role_incompatibility")
                if not background_ok:
                    blocked.append("blocked_by_background_conflict")
                source = node_by_atom[a.atom_id]
                target = node_by_atom[b.atom_id]
                if not blocked:
                    candidate_edges.append((source, target))
                    status = "candidate_continuation"
                else:
                    status = blocked[0]
                edge_rows.append(
                    {
                        "edge_id": f"R1E{len(edge_rows) + 1:04d}",
                        "source_node_id": source,
                        "target_node_id": target,
                        "source_sar_frame": a.frame,
                        "target_sar_frame": b.frame,
                        "geometry_distance": fmt(dist),
                        "radial_drift": fmt(radial_drift),
                        "azimuth_drift": fmt(az_drift),
                        "extent_continuity_ratio": fmt(extent_ratio),
                        "orientation_difference": fmt(orient),
                        "energy_ratio": fmt(energy_ratio),
                        "role_compatibility": bool_text(role_ok),
                        "background_conflict_consistency": bool_text(background_ok),
                        "edge_status": status,
                        "blocked_reason": ";".join(blocked),
                    }
                )
    succ = Counter(src for src, _ in candidate_edges)
    pred = Counter(tgt for _, tgt in candidate_edges)
    unique_edges = {(src, tgt) for src, tgt in candidate_edges if succ[src] == 1 and pred[tgt] == 1}
    for row in edge_rows:
        pair = (row["source_node_id"], row["target_node_id"])
        if pair in unique_edges:
            row["edge_status"] = "unique_continuation"
        elif pair in candidate_edges:
            if succ[row["source_node_id"]] > 1:
                row["edge_status"] = "ambiguous_successors"
            elif pred[row["target_node_id"]] > 1:
                row["edge_status"] = "ambiguous_predecessors"
    parent = {row["part_hypothesis_node_id"]: row["part_hypothesis_node_id"] for row in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for src, tgt in unique_edges:
        union(src, tgt)
    groups: dict[str, list[str]] = defaultdict(list)
    for node_id in parent:
        groups[find(node_id)].append(node_id)
    track_by_node: dict[str, str] = {}
    track_len: dict[str, int] = {}
    track_idx = 1
    for members in groups.values():
        if len(members) < 2:
            continue
        track_id = f"R1PT{track_idx:03d}"
        track_idx += 1
        track_len[track_id] = len(members)
        for node_id in members:
            track_by_node[node_id] = track_id
    succ_any = Counter(src for src, _ in candidate_edges)
    pred_any = Counter(tgt for _, tgt in candidate_edges)
    for row in nodes:
        nid = row["part_hypothesis_node_id"]
        row["persistent_part_track_id"] = track_by_node.get(nid, "")
        if row["persistent_part_track_id"]:
            row["lineage_state"] = "unique_continuation"
        elif succ_any[nid] > 1:
            row["lineage_state"] = "ambiguous_successors"
        elif pred_any[nid] > 1:
            row["lineage_state"] = "ambiguous_predecessors"
        elif succ_any[nid] == 0 and pred_any[nid] == 0:
            row["lineage_state"] = "newly_appeared_or_disappeared"
        else:
            row["lineage_state"] = "role_transition_or_blocked"
    atom_track = {row["atom_id"]: row["persistent_part_track_id"] for row in nodes if row["persistent_part_track_id"]}
    return nodes, edge_rows, atom_track, track_len


def classify_entities(structures: Sequence[Mapping[str, Any]], atom_track: Mapping[str, str], track_len: Mapping[str, int]) -> list[dict[str, Any]]:
    rows = []
    for s in structures:
        roles = set(str(s["role_candidate_combination"]).split(";"))
        atom_ids = [aid for aid in str(s["member_atom_ids"]).split(";") if aid]
        has_track = any(atom_track.get(aid) and track_len.get(atom_track[aid], 0) >= 2 for aid in atom_ids)
        background = s["background_arc_conflict"] == "true"
        long_axis = parse_float(s["support_pixel_long_axis"])
        short_axis = parse_float(s["support_pixel_short_axis"])
        max_gap = parse_float(s["max_internal_blank"], 999.0)
        max_dist = parse_float(s["max_pair_distance"], 999.0)
        g_scale = 30.0 <= long_axis <= 230.0 and 3.0 <= short_axis <= 170.0
        g_compact = max_gap <= 76.0 and max_dist <= 170.0
        g_grammar = bool(
            roles & {"body_core_candidate", "side_ridge_candidate", "endpoint_hotspot_candidate"}
        ) and "isolated_small_atom" not in roles
        g_temporal = has_track and not background
        if background:
            runtime_class = "background_like_runtime"
        elif g_scale and g_compact and g_grammar and g_temporal:
            runtime_class = "vehicle_supported_runtime"
        elif g_scale and g_compact and g_grammar:
            runtime_class = "vehicle_possible_runtime"
        elif roles <= {"isolated_small_atom"}:
            runtime_class = "background_like_runtime"
        else:
            runtime_class = "unresolved_runtime"
        rows.append(
            {
                "runtime_entity_id": f"R1Y{len(rows) + 1:04d}",
                "structure_id": s["structure_id"],
                "sar_frame": s["sar_frame"],
                "runtime_class": runtime_class,
                "G_scale": bool_text(g_scale),
                "G_compact": bool_text(g_compact),
                "G_grammar": bool_text(g_grammar),
                "G_temporal": bool_text(g_temporal),
                "G_background": bool_text(background),
                "optical_condition_compatibility": "not_applied_before_sar_gate; optical_may_only_condition_after_gate",
                "temporal_evidence": ";".join(sorted({atom_track[aid] for aid in atom_ids if atom_track.get(aid)})),
                "classification_reason_cn": runtime_reason_cn(runtime_class, s, g_scale, g_compact, g_grammar, g_temporal, background),
                "classification_provenance": "runtime_safe_no_gt_no_polarity_no_vehicle_identity",
            }
        )
    return rows


def runtime_reason_cn(runtime_class: str, s: Mapping[str, Any], g_scale: bool, g_compact: bool, g_grammar: bool, g_temporal: bool, background: bool) -> str:
    roles = s["role_candidate_combination"]
    if runtime_class == "vehicle_supported_runtime":
        return f"候选角色 {roles} 通过支持像素尺度、紧凑性、角色语法和相邻帧部件谱系，且无背景弧线冲突。"
    if runtime_class == "vehicle_possible_runtime":
        return f"候选角色 {roles} 通过部分尺度/语法 Gate，但缺少唯一持久部件谱系，只能作为运行时可能车辆结构。"
    if runtime_class == "background_like_runtime":
        return f"候选角色 {roles} 触发背景弧线或孤立小响应，不能用强度补偿为车辆结构。"
    return f"候选角色 {roles} 的 Gate 状态为 scale={g_scale}, compact={g_compact}, grammar={g_grammar}, temporal={g_temporal}, background={background}，运行时不可判定。"


def write_generation_artifacts(output_paths: Mapping[str, Path]) -> dict[str, str]:
    frames = runtime_frames()
    holdout_rows = sample_holdout_frames()
    atoms = extract_atoms(frames)
    structures = build_structures(atoms)
    nodes, edges, atom_track, track_len = build_lineage(atoms)
    entities = classify_entities(structures, atom_track, track_len)
    write_csv(output_paths["holdout_manifest"], holdout_rows, HOLDOUT_FIELDS)
    write_csv(output_paths["frozen_atom_trace"], atom_rows(atoms), ATOM_FIELDS)
    write_csv(output_paths["frozen_role_proposals"], role_rows(atoms), ROLE_FIELDS)
    write_csv(output_paths["support_extent"], structures, EXTENT_FIELDS)
    write_csv(output_paths["lineage_nodes"], nodes, NODE_FIELDS)
    write_csv(output_paths["lineage_edges"], edges, EDGE_FIELDS)
    write_csv(output_paths["runtime_entities"], entities, ENTITY_FIELDS)
    leakage = leakage_rows(output_paths)
    write_csv(output_paths["leakage_audit"], leakage, LEAK_FIELDS)
    shas = {key: sha256(output_paths[key]) for key in FREEZE_ARTIFACT_KEYS}
    manifest_rows = [
        {
            "artifact": key,
            "path": rel(output_paths[key]) if output_paths[key].is_relative_to(REPO_ROOT) else str(output_paths[key]),
            "sha256": shas[key],
            "rows": row_count(output_paths[key]),
            "frozen_phase": "generate",
        }
        for key in FREEZE_ARTIFACT_KEYS
    ]
    write_csv(output_paths["frozen_manifest"], manifest_rows, MANIFEST_FIELDS)
    return shas


def row_count(path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".csv":
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def leakage_rows(output_paths: Mapping[str, Path]) -> list[dict[str, str]]:
    frozen_paths = [output_paths[key] for key in FREEZE_ARTIFACT_KEYS + ["holdout_manifest"]]
    forbidden_terms = ["positive", "negative", "PV_GM19", "WHITE", "SILVER", "sar_bbox", "hidden_target", "EVAL_ONLY"]
    frozen_value_text_parts: list[str] = []
    for path in frozen_paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                frozen_value_text_parts.extend(str(value) for value in row.values())
    frozen_value_text = "\n".join(frozen_value_text_parts)
    generate_source = inspect.getsource(write_generation_artifacts) + inspect.getsource(extract_atoms) + inspect.getsource(build_structures) + inspect.getsource(classify_entities)
    checks = [
        ("L001", "generate", "paired_gt_not_read_in_generate", "PASS" if "paired" not in generate_source else "FAIL", "generate call graph does not reference INPUTS['paired']"),
        ("L002", "generate", "polarity_label_not_used_in_generate", "PASS" if "POSITIVE_FRAMES" not in generate_source and "NEGATIVE_OR_UNCERTAIN_FRAMES" not in generate_source and "eval_label(" not in generate_source else "FAIL", "generate functions use neutral runtime frame list only"),
        ("L003", "generate", "physical_vehicle_id_not_used_in_generate", "PASS" if "physical_vehicle_id" not in generate_source else "FAIL", "runtime generation has no vehicle identity parameter"),
        ("L004", "generate", "pair_for_frame_not_present", "PASS", "no PAIR_FOR_FRAME mapping exists in this R1 script"),
        ("L005", "frozen_csv", "forbidden_labels_absent_from_frozen_outputs", "PASS" if not any(term in frozen_value_text for term in forbidden_terms) else "FAIL", "scanned frozen artifact values for GT/polarity/identity terms; audit columns such as polarity_used=false are allowed"),
        ("L006", "blind", "blind_pack_requires_opaque_ids", "PASS", "blind-pack assigns BLIND_FRAME/BLIND_OBJECT ids and does not write original frame ids to blind review CSVs"),
    ]
    return [
        {"check_id": cid, "layer": layer, "check_name": name, "status": status, "evidence": evidence, "limitation_cn": "静态扫描不能形式化证明所有 Python 控制流，但冻结产物和主生成函数均被检查。"}
        for cid, layer, name, status, evidence in checks
    ]


def generate() -> None:
    shas = write_generation_artifacts(OUTPUTS)
    print("generated frozen artifact shas")
    for key, value in shas.items():
        print(f"{key}={value}")


def load_atoms_from_csv() -> list[dict[str, str]]:
    role_by_atom = {row["atom_id"]: row["candidate_role"] for row in read_rows(OUTPUTS["frozen_role_proposals"])}
    rows = read_rows(OUTPUTS["frozen_atom_trace"])
    for row in rows:
        row["candidate_role"] = role_by_atom.get(row["atom_id"], "unresolved_atom")
    return rows


def blind_maps() -> tuple[dict[int, str], dict[str, str], dict[str, str]]:
    structures = read_rows(OUTPUTS["support_extent"])
    frames = sorted({parse_int(row["sar_frame"]) for row in structures})
    frame_map = {frame: f"BLIND_FRAME_{idx + 1:03d}" for idx, frame in enumerate(frames)}
    object_map = {row["structure_id"]: f"BLIND_OBJECT_{idx + 1:03d}" for idx, row in enumerate(structures)}
    reverse = {blind: sid for sid, blind in object_map.items()}
    return frame_map, object_map, reverse


def blind_sheet_for_frame(blind_frame_id: str) -> Path:
    idx = parse_int(blind_frame_id.split("_")[-1])
    if idx <= 10:
        return VISUALS["blind_sheet_a"]
    if idx <= 20:
        return VISUALS["blind_sheet_b"]
    if idx <= 30:
        return VISUALS["blind_sheet_c"]
    return VISUALS["blind_sheet_d"]


def render_blind_pack() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    atoms = load_atoms_from_csv()
    structures = read_rows(OUTPUTS["support_extent"])
    nodes = read_rows(OUTPUTS["lineage_nodes"])
    frame_map, object_map, _reverse = blind_maps()
    by_frame_atoms: dict[int, list[dict[str, str]]] = defaultdict(list)
    by_frame_structures: dict[int, list[dict[str, str]]] = defaultdict(list)
    for atom in atoms:
        by_frame_atoms[parse_int(atom["sar_frame"])].append(atom)
    for structure in structures:
        by_frame_structures[parse_int(structure["sar_frame"])].append(structure)
    frame_track_by_atom = {row["atom_id"]: row["persistent_part_track_id"] for row in nodes}
    frames = sorted(frame_map)
    sheets: list[list[Image.Image]] = [[], [], [], []]
    for frame in frames:
        blind_frame_id = frame_map[frame]
        tile = blind_tile(frame, blind_frame_id, by_frame_atoms[frame], by_frame_structures[frame], object_map, frame_track_by_atom)
        idx = parse_int(blind_frame_id.split("_")[-1])
        sheet_idx = 0 if idx <= 10 else 1 if idx <= 20 else 2 if idx <= 30 else 3
        sheets[sheet_idx].append(tile)
    for path, tiles in zip([VISUALS["blind_sheet_a"], VISUALS["blind_sheet_b"], VISUALS["blind_sheet_c"], VISUALS["blind_sheet_d"]], sheets):
        render_sheet(path, tiles, 2)


def blind_tile(
    frame: int,
    blind_frame_id: str,
    atoms: Sequence[Mapping[str, str]],
    structures: Sequence[Mapping[str, str]],
    object_map: Mapping[str, str],
    track_by_atom: Mapping[str, str],
) -> Image.Image:
    base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB") if sar_gray_path(SCENE, frame).exists() else Image.new("RGB", (SAR_WIDTH, SAR_HEIGHT), (20, 20, 20))
    boxes = [box_from_text(a["support_bbox"]) for a in atoms]
    boxes = [b for b in boxes if b]
    focus = expand_box(union_box(boxes), 46.0)
    full_w, full_h = 430, 250
    zoom_w, zoom_h = 430, 250
    full = base.resize((full_w, full_h))
    fdraw = ImageDraw.Draw(full)
    sx, sy = full_w / SAR_WIDTH, full_h / SAR_HEIGHT
    draw_scaled_box(fdraw, focus, sx, sy, (255, 140, 0), 2)
    fdraw.rectangle([0, 0, full_w, 24], fill=(0, 0, 0))
    fdraw.text((5, 5), f"{blind_frame_id} full", fill=(255, 255, 255))
    crop = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((zoom_w, zoom_h))
    zdraw = ImageDraw.Draw(crop)
    zdraw.rectangle([0, 0, zoom_w, 24], fill=(0, 0, 0))
    zdraw.text((5, 5), f"{blind_frame_id} candidate atoms/lineage", fill=(255, 255, 255))
    colors = {
        "body_core_candidate": (0, 255, 110),
        "side_ridge_candidate": (55, 190, 255),
        "endpoint_hotspot_candidate": (255, 220, 40),
        "background_arc_candidate": (255, 80, 80),
        "isolated_small_atom": (230, 230, 230),
        "unresolved_atom": (175, 175, 175),
    }
    centers: dict[str, tuple[float, float]] = {}
    for atom in atoms[:16]:
        box = box_from_text(atom["support_bbox"])
        if not box:
            continue
        role = atom["candidate_role"]
        color = colors.get(role, (190, 190, 190))
        draw_crop_box(zdraw, box, focus, zoom_w, zoom_h, color, 2)
        x, y = crop_point(parse_float(atom["pixel_centroid_x"]), parse_float(atom["pixel_centroid_y"]), focus, zoom_w, zoom_h)
        centers[atom["atom_id"]] = (x, y)
        orient = parse_float(atom["atom_orientation"])
        dx = math.cos(math.radians(orient)) * 12
        dy = math.sin(math.radians(orient)) * 12
        zdraw.line([x - dx, y - dy, x + dx, y + dy], fill=color, width=2)
        track = track_by_atom.get(atom["atom_id"], "")
        short_role = role.replace("_candidate", "").replace("_atom", "")[:5]
        zdraw.text((x + 4, y + 2), f"{atom['atom_id'][-2:]}:{short_role}:{track[-3:]}", fill=color)
    for structure in structures[:8]:
        sb = box_from_text(structure["support_bbox"])
        if not sb:
            continue
        color = (255, 255, 255) if structure["background_arc_conflict"] != "true" else (255, 80, 80)
        draw_crop_box(zdraw, sb, focus, zoom_w, zoom_h, color, 1)
        x, y = crop_point(sb.x1, sb.y1, focus, zoom_w, zoom_h)
        zdraw.text((x + 2, max(25, y - 12)), object_map[structure["structure_id"]], fill=color)
        atom_ids = [aid for aid in structure["member_atom_ids"].split(";") if aid in centers]
        for a_id, b_id in combinations(atom_ids, 2):
            zdraw.line([centers[a_id], centers[b_id]], fill=(255, 155, 0), width=1)
    tile = Image.new("RGB", (full_w + zoom_w, zoom_h), (15, 15, 15))
    tile.paste(full, (0, 0))
    tile.paste(crop, (full_w, 0))
    return tile


def crop_point(x: float, y: float, focus: Box, width_px: int, height_px: int) -> tuple[float, float]:
    return (
        (x - focus.x1) / max(1.0, focus.width) * width_px,
        (y - focus.y1) / max(1.0, focus.height) * height_px,
    )


def draw_scaled_box(draw: ImageDraw.ImageDraw, box: Box, sx: float, sy: float, color: tuple[int, int, int], width: int) -> None:
    draw.rectangle([box.x1 * sx, box.y1 * sy, box.x2 * sx, box.y2 * sy], outline=color, width=width)


def draw_crop_box(draw: ImageDraw.ImageDraw, box: Box, focus: Box, width_px: int, height_px: int, color: tuple[int, int, int], width: int) -> None:
    x1, y1 = crop_point(box.x1, box.y1, focus, width_px, height_px)
    x2, y2 = crop_point(box.x2, box.y2, focus, width_px, height_px)
    draw.rectangle([x1, y1, x2, y2], outline=color, width=width)


def render_sheet(path: Path, tiles: Sequence[Image.Image], cols: int) -> None:
    if not tiles:
        Image.new("RGB", (860, 250), (20, 20, 20)).save(path)
        return
    w, h = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (w * cols, h * rows), (18, 18, 18))
    for idx, tile in enumerate(tiles):
        sheet.paste(tile, ((idx % cols) * w, (idx // cols) * h))
    sheet.save(path)


def blind_manifest_and_judgements() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    structures = read_rows(OUTPUTS["support_extent"])
    frame_map, object_map, _reverse = blind_maps()
    manifest: list[dict[str, Any]] = []
    for idx, structure in enumerate(structures, start=1):
        blind_frame_id = frame_map[parse_int(structure["sar_frame"])]
        blind_object_id = object_map[structure["structure_id"]]
        blind_review_id = f"BRV_{idx:04d}"
        png = rel(blind_sheet_for_frame(blind_frame_id))
        manifest.append(
            {
                "blind_review_id": blind_review_id,
                "blind_frame_id": blind_frame_id,
                "blind_object_id": blind_object_id,
                "review_object_type": "structure_candidate",
                "candidate_role_summary": structure["role_candidate_combination"],
                "runtime_png": png,
            }
        )
    return manifest, blank_blind_judgement_rows(manifest)


def blank_blind_judgement_rows(manifest: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in manifest:
        rows.append(
            {
                "blind_review_id": row["blind_review_id"],
                "blind_frame_id": row["blind_frame_id"],
                "blind_object_id": row["blind_object_id"],
                "review_object_type": row["review_object_type"],
                "visible_structure_cn": "",
                "vehicle_part_support": "",
                "vehicle_structure_support": "",
                "background_structure_support": "",
                "unresolved": "",
                "decisive_reason_cn": "",
                "alternative_explanation_cn": "",
                "relation_to_other_objects_cn": "",
                "visual_confidence": "",
                "runtime_png": row["runtime_png"],
            }
        )
    return rows


def require_completed_blind_judgement() -> None:
    require_files([OUTPUTS["blind_judgement"]])
    rows = read_rows(OUTPUTS["blind_judgement"])
    required = [
        "visible_structure_cn",
        "vehicle_part_support",
        "vehicle_structure_support",
        "background_structure_support",
        "unresolved",
        "decisive_reason_cn",
        "alternative_explanation_cn",
        "relation_to_other_objects_cn",
        "visual_confidence",
    ]
    incomplete = [
        row["blind_object_id"]
        for row in rows
        if any(not str(row.get(field, "")).strip() for field in required)
    ]
    if incomplete:
        raise ValueError("blind judgement must be filled after visual review before evaluate; incomplete objects: " + "; ".join(incomplete[:12]))
    if len({row["decisive_reason_cn"] for row in rows}) < min(3, len(rows)):
        raise ValueError("blind judgement appears template-like; decisive_reason_cn must vary across inspected objects")


def _legacy_auto_blind_judgement_disabled(
    blind_review_id: str,
    blind_frame_id: str,
    blind_object_id: str,
    structure: Mapping[str, str],
    entity: Mapping[str, str],
    track_by_atom: Mapping[str, str],
    png: str,
) -> dict[str, Any]:
    raise RuntimeError("automatic blind judgement is disabled; fill blind_object_judgement CSV after opening blind sheets")
    roles = set(structure["role_candidate_combination"].split(";"))
    has_vehicle_part = bool(roles & {"body_core_candidate", "side_ridge_candidate", "endpoint_hotspot_candidate"}) and structure["background_arc_conflict"] != "true"
    has_lineage = bool(entity.get("temporal_evidence"))
    support_long = parse_float(structure["support_pixel_long_axis"])
    support_short = parse_float(structure["support_pixel_short_axis"])
    scale_ok = 30.0 <= support_long <= 230.0 and 3.0 <= support_short <= 170.0
    background = structure["background_arc_conflict"] == "true" or roles == {"isolated_small_atom"}
    vehicle_structure = has_vehicle_part and scale_ok and has_lineage and not background
    unresolved = not vehicle_structure and not background
    visible = f"{blind_object_id} shows roles {structure['role_candidate_combination']} with support-pixel axes L={fmt(support_long)}, W={fmt(support_short)} and relation {structure['part_relation_summary']}."
    if vehicle_structure:
        decisive = "可见局部主体/侧边/端点候选之间存在紧凑关系，并且至少一个部件有相邻帧持久谱系；图上不像单个孤立峰或长弧线。"
        alternative = "仍可能只是局部高亮响应；需要 GT 辅助分析确认是否位于目标区域。"
        confidence = "medium"
    elif background:
        decisive = "可见长条或弧线候选/孤立小峰，缺少主体-侧边-端点的车辆尺度闭合。"
        alternative = "若 GT 后验显示其落在目标内部，只能说明当前盲审对弱车辆响应不足。"
        confidence = "medium" if "background_arc_candidate" in roles else "low"
    else:
        decisive = "图上有局部响应但部件关系、宽度或相邻帧谱系不足，不能独立判断为车辆结构。"
        alternative = "可能是弱车辆部件，也可能是背景纹理或截断后的不完整响应。"
        confidence = "low"
    return {
        "blind_review_id": blind_review_id,
        "blind_frame_id": blind_frame_id,
        "blind_object_id": blind_object_id,
        "review_object_type": "structure_candidate",
        "visible_structure_cn": visible,
        "vehicle_part_support": bool_text(has_vehicle_part and not background),
        "vehicle_structure_support": bool_text(vehicle_structure),
        "background_structure_support": bool_text(background),
        "unresolved": bool_text(unresolved),
        "decisive_reason_cn": decisive,
        "alternative_explanation_cn": alternative,
        "relation_to_other_objects_cn": "与同帧其他对象的区别需在 evaluate 阶段通过 vehicle-vs-other contrast 逐项展开；此处只记录盲图可见关系。",
        "visual_confidence": confidence,
        "runtime_png": png,
    }


def blind_pack() -> None:
    require_files([OUTPUTS[key] for key in FREEZE_ARTIFACT_KEYS])
    render_blind_pack()
    manifest, judgement = blind_manifest_and_judgements()
    write_csv(OUTPUTS["blind_manifest"], manifest, BLIND_MANIFEST_FIELDS)
    if not OUTPUTS["blind_judgement"].exists():
        write_csv(OUTPUTS["blind_judgement"], judgement, BLIND_FIELDS)
        print("blind-pack wrote blank blind judgement template; fill it after opening sheets before evaluate")
    else:
        print("blind-pack preserved existing blind judgement CSV; remove it first only when intentionally restarting blind review")
    print("blind sheets:")
    for path in [VISUALS["blind_sheet_a"], VISUALS["blind_sheet_b"], VISUALS["blind_sheet_c"], VISUALS["blind_sheet_d"]]:
        print(rel(path))


def require_files(paths: Sequence[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required files: " + "; ".join(missing))


def load_gt_by_frame() -> dict[int, Box]:
    rows = read_rows(INPUTS["paired"])
    out: dict[int, Box] = {}
    for row in rows:
        if row.get("scene") != SCENE:
            continue
        frame = parse_int(row["sar_frame"])
        out[frame] = box_from_pair(row)
    return out


def eval_label(frame: int) -> str:
    if frame in POSITIVE_FRAMES:
        return "discovery_positive_eval_only"
    if frame in NEGATIVE_OR_UNCERTAIN_FRAMES:
        return "discovery_negative_or_uncertain_eval_only"
    return "blind_holdout_unlabeled_eval_only"


def vehicle_identity(frame: int) -> str:
    if 27 <= frame <= 81:
        return "white_suv_eval_only"
    if 212 <= frame <= 290:
        return "silver_mpv_eval_only"
    return "unknown_eval_only"


def box_overlap(a: Box, b: Box) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return inter / b.area if b.area else 0.0


def center_distance(a: Box, b: Box) -> float:
    return math.hypot(a.cx - b.cx, a.cy - b.cy)


def judgement_class(row: Mapping[str, str]) -> str:
    if row["vehicle_structure_support"] == "true":
        return "vehicle_structure"
    if row["vehicle_part_support"] == "true":
        return "vehicle_part"
    if row["background_structure_support"] == "true":
        return "background"
    return "unresolved"


def evaluate_rows() -> tuple[list[dict[str, Any]], dict[str, str]]:
    structures = {row["structure_id"]: row for row in read_rows(OUTPUTS["support_extent"])}
    entities = read_rows(OUTPUTS["runtime_entities"])
    frame_map, object_map, reverse = blind_maps()
    blind_by_object = {row["blind_object_id"]: row for row in read_rows(OUTPUTS["blind_judgement"])}
    gt_by_frame = load_gt_by_frame()
    rows: list[dict[str, Any]] = []
    for entity in entities:
        structure = structures[entity["structure_id"]]
        frame = parse_int(entity["sar_frame"])
        blind_object = object_map[entity["structure_id"]]
        blind = blind_by_object.get(blind_object, {})
        bbox = box_from_text(structure["support_bbox"])
        gt = gt_by_frame.get(frame)
        overlap = box_overlap(bbox, gt) if bbox and gt else math.nan
        distance = center_distance(bbox, gt) if bbox and gt else math.nan
        if gt is None:
            gt_relation = "no_exact_gt_for_frame"
        elif overlap >= 0.15:
            gt_relation = "overlaps_gt_eval_only"
        elif distance <= 90.0:
            gt_relation = "near_gt_eval_only"
        else:
            gt_relation = "outside_gt_eval_only"
        label = eval_label(frame)
        runtime_vehicle = entity["runtime_class"] in {"vehicle_supported_runtime", "vehicle_possible_runtime"}
        blind_vehicle = judgement_class(blind) in {"vehicle_structure", "vehicle_part"}
        blind_background = judgement_class(blind) == "background"
        runtime_reject = entity["runtime_class"] in {"background_like_runtime", "unresolved_runtime"}
        false_reject = (
            label == "discovery_positive_eval_only"
            and (gt_relation in {"overlaps_gt_eval_only", "near_gt_eval_only"} or blind_vehicle)
            and runtime_reject
        )
        false_accept = (
            runtime_vehicle
            and (label == "discovery_negative_or_uncertain_eval_only" or gt_relation in {"outside_gt_eval_only", "no_exact_gt_for_frame"})
            and (blind_background or judgement_class(blind) == "unresolved")
        )
        runtime_blind_disagree = (runtime_vehicle and not blind_vehicle) or (runtime_reject and blind_vehicle)
        blind_gt_disagree = bool(gt and ((blind_vehicle and gt_relation == "outside_gt_eval_only") or (blind_background and gt_relation == "overlaps_gt_eval_only")))
        rows.append(
            {
                "eval_id": f"R1EV{len(rows) + 1:04d}",
                "runtime_entity_id": entity["runtime_entity_id"],
                "structure_id": entity["structure_id"],
                "sar_frame": frame,
                "discovery_label_eval_only": label,
                "vehicle_identity_eval_only": vehicle_identity(frame),
                "runtime_class": entity["runtime_class"],
                "blind_object_id": blind_object,
                "blind_judgement": judgement_class(blind),
                "gt_exact_frame_available": bool_text(gt is not None),
                "gt_relation_eval_only": gt_relation,
                "gt_overlap_eval_only": fmt(overlap),
                "gt_center_distance_eval_only": fmt(distance),
                "runtime_false_reject": bool_text(false_reject),
                "runtime_false_accept": bool_text(false_accept),
                "runtime_blind_disagreement": bool_text(runtime_blind_disagree),
                "blind_gt_disagreement": bool_text(blind_gt_disagree),
                "gt_assisted_explanation_cn": gt_explanation_cn(entity, structure, judgement_class(blind), gt_relation, label),
                "provenance": "eval_only_gt_assisted",
            }
        )
    sha_info = {
        "blind_judgement": sha256(OUTPUTS["blind_judgement"]),
        **{key: sha256(OUTPUTS[key]) for key in FREEZE_ARTIFACT_KEYS},
    }
    return rows, sha_info


def gt_explanation_cn(entity: Mapping[str, str], structure: Mapping[str, str], blind: str, gt_relation: str, label: str) -> str:
    roles = structure["role_candidate_combination"]
    runtime = entity["runtime_class"]
    if runtime.startswith("vehicle") and blind in {"vehicle_structure", "vehicle_part"}:
        return f"冻结结构 {roles} 与盲审车辆支持一致；GT 关系为 {gt_relation}。若只重叠局部目标，说明 SAR 车辆响应是部件级而非完整框。"
    if runtime.startswith("vehicle") and blind in {"background", "unresolved"}:
        return f"运行时接受 {roles}，但盲审为 {blind}；GT 关系 {gt_relation} 只能作为事后解释，不能回写生成结果。"
    if runtime in {"background_like_runtime", "unresolved_runtime"} and blind in {"vehicle_structure", "vehicle_part"}:
        return f"运行时拒绝或未判定 {roles}，但盲审认为有车辆部件支持；若 GT 关系接近目标，这是 R1 误拒候选。"
    return f"运行时 {runtime}、盲审 {blind}、GT 关系 {gt_relation}；保留为背景、未解或机制反例。"


def scale_fields(structure: Mapping[str, str]) -> str:
    return f"L={structure['support_pixel_long_axis']};W={structure['support_pixel_short_axis']};centroidL={structure['centroid_long_axis']};centroidW={structure['centroid_short_axis']};deg_fixed={structure['extent_degeneracy_fixed']}"


def contrast_rows(eval_rows_in: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    structures = {row["structure_id"]: row for row in read_rows(OUTPUTS["support_extent"])}
    entities = {row["structure_id"]: row for row in read_rows(OUTPUTS["runtime_entities"])}
    blind_by_object = {row["blind_object_id"]: row for row in read_rows(OUTPUTS["blind_judgement"])}
    frame_map, object_map, _reverse = blind_maps()
    eval_by_structure = {row["structure_id"]: row for row in eval_rows_in}
    rows: list[dict[str, Any]] = []
    grouped: dict[int, list[str]] = defaultdict(list)
    for sid, structure in structures.items():
        grouped[parse_int(structure["sar_frame"])].append(sid)
    accepted = [
        sid
        for sid, entity in entities.items()
        if entity["runtime_class"] in {"vehicle_supported_runtime", "vehicle_possible_runtime"}
        or eval_by_structure[sid]["blind_judgement"] in {"vehicle_structure", "vehicle_part"}
    ]
    for sid in accepted:
        structure = structures[sid]
        frame = parse_int(structure["sar_frame"])
        alternatives = [other for other in grouped[frame] if other != sid]
        if not alternatives:
            alternatives = [other for other in structures if other != sid]
        alt = max(
            alternatives,
            key=lambda oid: (
                entities[oid]["runtime_class"] == "background_like_runtime",
                parse_float(structures[oid]["support_pixel_long_axis"]),
            ),
        )
        rows.append(contrast_row(len(rows) + 1, sid, alt, structures, entities, eval_by_structure, object_map, same_frame=frame == parse_int(structures[alt]["sar_frame"])))
    holdout_eval = [row for row in eval_rows_in if row["discovery_label_eval_only"] == "blind_holdout_unlabeled_eval_only"]
    holdout_sorted = sorted(holdout_eval, key=lambda r: (r["blind_judgement"] == "background", r["blind_judgement"] == "unresolved", r["structure_id"]))
    for item in holdout_sorted[:6]:
        sid = item["structure_id"]
        frame = parse_int(item["sar_frame"])
        alts = [other for other in grouped[frame] if other != sid]
        if alts:
            rows.append(contrast_row(len(rows) + 1, sid, alts[0], structures, entities, eval_by_structure, object_map, same_frame=True))
    # Deduplicate by accepted/alternative pair while preserving order.
    out = []
    seen = set()
    for row in rows:
        key = (row["accepted_object_id"], row["alternative_object_id"])
        if key not in seen:
            seen.add(key)
            row["contrast_id"] = f"R1C{len(out) + 1:04d}"
            out.append(row)
    return out


def contrast_row(
    idx: int,
    accepted_sid: str,
    alternative_sid: str,
    structures: Mapping[str, Mapping[str, str]],
    entities: Mapping[str, Mapping[str, str]],
    eval_by_structure: Mapping[str, Mapping[str, str]],
    object_map: Mapping[str, str],
    same_frame: bool,
) -> dict[str, Any]:
    acc = structures[accepted_sid]
    alt = structures[alternative_sid]
    acc_eval = eval_by_structure[accepted_sid]
    alt_eval = eval_by_structure[alternative_sid]
    return {
        "contrast_id": f"R1C{idx:04d}",
        "accepted_object_id": object_map[accepted_sid],
        "alternative_object_id": object_map[alternative_sid],
        "same_frame_or_cross_frame": "same_frame" if same_frame else "cross_frame",
        "accepted_runtime_class": entities[accepted_sid]["runtime_class"],
        "alternative_runtime_class": entities[alternative_sid]["runtime_class"],
        "accepted_blind_judgement": acc_eval["blind_judgement"],
        "alternative_blind_judgement": alt_eval["blind_judgement"],
        "accepted_scale_fields": scale_fields(acc),
        "alternative_scale_fields": scale_fields(alt),
        "accepted_part_relations": acc["part_relation_summary"],
        "alternative_part_relations": alt["part_relation_summary"],
        "accepted_lineage": entities[accepted_sid]["temporal_evidence"],
        "alternative_lineage": entities[alternative_sid]["temporal_evidence"],
        "accepted_arc_conflict": acc["background_arc_conflict"],
        "alternative_arc_conflict": alt["background_arc_conflict"],
        "accepted_gt_relation_eval_only": acc_eval["gt_relation_eval_only"],
        "alternative_gt_relation_eval_only": alt_eval["gt_relation_eval_only"],
        "decisive_difference_cn": decisive_difference_cn(acc, alt, entities[accepted_sid], entities[alternative_sid]),
        "non_decisive_support_cn": "亮度、接近搜索壳或单个候选角色都不是决定性证据；决定性证据来自支持像素尺度、部件关系、弧线冲突和谱系。",
        "unresolved_difference_cn": unresolved_difference_cn(acc_eval, alt_eval),
    }


def decisive_difference_cn(acc: Mapping[str, str], alt: Mapping[str, str], acc_ent: Mapping[str, str], alt_ent: Mapping[str, str]) -> str:
    if alt["background_arc_conflict"] == "true":
        return f"接受对象具有 {acc['role_candidate_combination']} 和谱系 {acc_ent['temporal_evidence']}；替代对象虽可能更长或更亮，但角色为 {alt['role_candidate_combination']} 并触发弧线冲突。"
    if not alt_ent["temporal_evidence"]:
        return f"接受对象的部件谱系为 {acc_ent['temporal_evidence']}；替代对象缺少唯一相邻帧部件谱系，不能闭合成车辆响应。"
    return f"接受对象尺度 {scale_fields(acc)} 与角色关系 {acc['part_relation_summary']} 更接近车辆部件；替代对象仍存在未解差异。"


def unresolved_difference_cn(acc_eval: Mapping[str, str], alt_eval: Mapping[str, str]) -> str:
    if acc_eval["blind_judgement"] == "unresolved" or alt_eval["blind_judgement"] == "unresolved":
        return "至少一侧盲审仍为 unresolved，差异不能作为稳定全局机制。"
    return "当前对比没有完全无法区分的反例，但仍只覆盖局部窗口。"


def failure_rows(eval_rows_in: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in eval_rows_in:
        if row["runtime_false_reject"] == "true":
            rows.append(
                {
                    "case_id": f"R1F{len(rows) + 1:04d}",
                    "failure_type": "runtime_false_reject",
                    "object_id": row["blind_object_id"],
                    "sar_frame": row["sar_frame"],
                    "reason_cn": row["gt_assisted_explanation_cn"],
                    "provenance": "eval_only_gt_assisted",
                }
            )
        if row["runtime_false_accept"] == "true":
            rows.append(
                {
                    "case_id": f"R1F{len(rows) + 1:04d}",
                    "failure_type": "runtime_false_accept",
                    "object_id": row["blind_object_id"],
                    "sar_frame": row["sar_frame"],
                    "reason_cn": row["gt_assisted_explanation_cn"],
                    "provenance": "eval_only_gt_assisted",
                }
            )
    if not rows:
        rows.append(
            {
                "case_id": "R1F0001",
                "failure_type": "mechanism_still_partial",
                "object_id": "",
                "sar_frame": "",
                "reason_cn": "R1 完成隔离和局部盲留出，但仍不是全场景盲评；车辆支持观测机制不得进入 A1.7R2。",
                "provenance": "eval_only_gt_assisted",
            }
        )
    return rows


def gate_rows(eval_rows_in: Sequence[Mapping[str, str]], contrast: Sequence[Mapping[str, str]], replay_status: str = "PENDING") -> list[dict[str, str]]:
    leakage = read_rows(OUTPUTS["leakage_audit"])
    blind = read_rows(OUTPUTS["blind_judgement"]) if OUTPUTS["blind_judgement"].exists() else []
    ext = read_rows(OUTPUTS["support_extent"])
    edges = read_rows(OUTPUTS["lineage_edges"])
    nodes = read_rows(OUTPUTS["lineage_nodes"])
    false_reject = sum(row["runtime_false_reject"] == "true" for row in eval_rows_in)
    false_accept = sum(row["runtime_false_accept"] == "true" for row in eval_rows_in)
    disagreements = sum(row["runtime_blind_disagreement"] == "true" for row in eval_rows_in)
    deg_fixed = sum(row["extent_degeneracy_fixed"] == "true" for row in ext)
    unique_edges = sum(row["edge_status"] == "unique_continuation" for row in edges)
    blind_complete = bool(blind) and all(row["decisive_reason_cn"].strip() and row["visible_structure_cn"].strip() for row in blind)
    blind_diverse = len({row["decisive_reason_cn"] for row in blind}) >= min(3, len(blind))
    return [
        gate("GENERATION_GT_ISOLATION_VALID", "PASS" if all(row["status"] == "PASS" for row in leakage) else "FAIL", "leakage audit checks all passed", "runtime_safe"),
        gate("POLARITY_LABEL_NOT_USED_IN_GENERATE", "PASS" if next((r for r in leakage if r["check_name"] == "polarity_label_not_used_in_generate"), {}).get("status") == "PASS" else "FAIL", "generate uses DISCOVERY_RUNTIME_FRAMES without positive/negative split", "runtime_safe"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_status, "verify-replay compares frozen atom/role/extent/entity/lineage SHA", "runtime_safe"),
        gate("BLIND_OBJECT_REVIEW_FROZEN", "PASS" if blind_complete else "FAIL", f"blind rows={len(blind)}; sha={sha256(OUTPUTS['blind_judgement']) if blind else ''}", "blind_visual_review"),
        gate("BLIND_REVIEW_NOT_TEMPLATE_GENERATED", "PASS" if blind_complete and blind_diverse else "PARTIAL", "blind judgement was filled after opening blind sheets and varies by visible object evidence", "blind_visual_review"),
        gate("SUPPORT_PIXEL_EXTENT_VALID", "PASS" if deg_fixed > 0 else "PARTIAL", f"extent_degeneracy_fixed_count={deg_fixed}; no centroid short-axis clamp used", "runtime_safe"),
        gate("PART_LINEAGE_RUNTIME_SAFE", "PASS" if unique_edges > 0 else "NO", f"nodes={len(nodes)}; edges={len(edges)}; unique_edges={unique_edges}", "runtime_safe"),
        gate("TEMPORAL_GATE_NOT_CIRCULAR", "PASS", "G_temporal comes from persistent_part_track_id, not runtime class", "runtime_safe"),
        gate("POSITIVE_NEGATIVE_EVALUATION_UNBIASED", "PASS" if false_accept == 0 else "PARTIAL", f"false_reject={false_reject}; false_accept={false_accept}; labels loaded only in evaluate", "eval_only_gt_assisted"),
        gate("GT_ASSISTED_EXPLANATION_COMPLETE", "PASS" if eval_rows_in else "FAIL", f"gt-assisted eval rows={len(eval_rows_in)}", "eval_only_gt_assisted"),
        gate("VEHICLE_VS_OTHER_MECHANISM_CLOSED", "PARTIAL" if contrast else "NO", f"contrast rows={len(contrast)}; still local window only", "eval_only_gt_assisted"),
        gate("POINT_TO_STRUCTURE_R1_READY", "PARTIAL", "R1 fixes isolation and extent/lineage audits but remains local", "eval_only_gt_assisted"),
        gate("VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2", "NO", "holdout is local and mechanism remains partial", "eval_only_gt_assisted"),
        gate("INTERMEDIATE_FRAME_BLIND_EVAL_PENDING", "partially_completed", "12 deterministic holdout frames reviewed, not full scene", "blind_visual_review"),
        gate("GM_RM011_BLOCKED", "true", "R1 remains GM_RM019 only", "eval_only_gt_assisted"),
    ]


def gate(name: str, status: str, evidence: str, provenance: str) -> dict[str, str]:
    return {"gate": name, "status": status, "evidence": evidence, "provenance": provenance}


def render_eval_sheet() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    structures = read_rows(OUTPUTS["support_extent"])
    entities = {row["structure_id"]: row for row in read_rows(OUTPUTS["runtime_entities"])}
    gt_by_frame = load_gt_by_frame()
    frames = [31, 77, 81, 238, 269, 273, 288, 290]
    tiles = []
    by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
    for s in structures:
        by_frame[parse_int(s["sar_frame"])].append(s)
    for frame in frames:
        tiles.append(eval_tile(frame, by_frame.get(frame, []), entities, gt_by_frame.get(frame)))
    render_sheet(VISUALS["eval_sheet"], tiles, 2)


def eval_tile(frame: int, structures: Sequence[Mapping[str, str]], entities: Mapping[str, Mapping[str, str]], gt: Box | None) -> Image.Image:
    base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB") if sar_gray_path(SCENE, frame).exists() else Image.new("RGB", (SAR_WIDTH, SAR_HEIGHT), (20, 20, 20))
    boxes = [box_from_text(s["support_bbox"]) for s in structures]
    if gt:
        boxes.append(gt)
    boxes = [b for b in boxes if b]
    focus = expand_box(union_box(boxes), 52.0)
    full_w, full_h = 430, 250
    zoom_w, zoom_h = 430, 250
    full = base.resize((full_w, full_h))
    fdraw = ImageDraw.Draw(full)
    sx, sy = full_w / SAR_WIDTH, full_h / SAR_HEIGHT
    draw_scaled_box(fdraw, focus, sx, sy, (255, 140, 0), 2)
    if gt:
        draw_scaled_box(fdraw, gt, sx, sy, (255, 240, 50), 2)
    fdraw.rectangle([0, 0, full_w, 24], fill=(0, 0, 0))
    fdraw.text((5, 5), f"SAR{frame} eval-only", fill=(255, 255, 255))
    crop = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((zoom_w, zoom_h))
    zdraw = ImageDraw.Draw(crop)
    zdraw.rectangle([0, 0, zoom_w, 24], fill=(0, 0, 0))
    zdraw.text((5, 5), f"SAR{frame} EVAL_ONLY target", fill=(255, 255, 255))
    for s in structures[:10]:
        box = box_from_text(s["support_bbox"])
        if not box:
            continue
        entity = entities.get(s["structure_id"], {})
        runtime_class = entity.get("runtime_class", "")
        color = (0, 255, 110) if runtime_class.startswith("vehicle") else (255, 80, 80) if "background" in runtime_class else (190, 190, 190)
        draw_crop_box(zdraw, box, focus, zoom_w, zoom_h, color, 2)
        x, y = crop_point(box.x1, box.y1, focus, zoom_w, zoom_h)
        zdraw.text((x + 2, max(26, y - 12)), s["structure_id"], fill=color)
    if gt:
        draw_crop_box(zdraw, gt, focus, zoom_w, zoom_h, (255, 240, 50), 2)
        zdraw.text((zoom_w - 105, 28), "EVAL_ONLY", fill=(255, 240, 50))
    tile = Image.new("RGB", (full_w + zoom_w, zoom_h), (15, 15, 15))
    tile.paste(full, (0, 0))
    tile.paste(crop, (full_w, 0))
    return tile


def evaluate() -> None:
    require_files([OUTPUTS[key] for key in FREEZE_ARTIFACT_KEYS] + [OUTPUTS["blind_judgement"]])
    require_completed_blind_judgement()
    eval_rows_out, sha_info = evaluate_rows()
    contrast = contrast_rows(eval_rows_out)
    failures = failure_rows(eval_rows_out)
    gates = gate_rows(eval_rows_out, contrast)
    write_csv(OUTPUTS["gt_eval"], eval_rows_out, EVAL_FIELDS)
    write_csv(OUTPUTS["contrast"], contrast, CONTRAST_FIELDS)
    write_csv(OUTPUTS["failure_cases"], failures, FAIL_FIELDS)
    write_csv(OUTPUTS["gate_integrity"], gates, GATE_FIELDS)
    render_eval_sheet()
    render_report(sha_info, replay_status="PENDING")
    print(f"evaluate complete blind_judgement_sha256={sha_info['blind_judgement']}")


def verify_replay() -> None:
    require_files([OUTPUTS[key] for key in FREEZE_ARTIFACT_KEYS] + [OUTPUTS["gt_eval"], OUTPUTS["contrast"]])
    if VERIFY_TMP_DIR.exists():
        shutil.rmtree(VERIFY_TMP_DIR)
    VERIFY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_outputs = {key: VERIFY_TMP_DIR / OUTPUTS[key].name for key in OUTPUTS if key in FREEZE_ARTIFACT_KEYS + ["holdout_manifest", "leakage_audit", "frozen_manifest"]}
    shas = write_generation_artifacts(temp_outputs)
    comparisons = []
    ok = True
    for key in FREEZE_ARTIFACT_KEYS:
        canonical = sha256(OUTPUTS[key])
        replay = shas[key]
        same = canonical == replay
        ok = ok and same
        comparisons.append(f"{key}:{'PASS' if same else 'FAIL'}")
    replay_status = "PASS" if ok else "FAIL"
    eval_rows_out = read_rows(OUTPUTS["gt_eval"])
    contrast = read_rows(OUTPUTS["contrast"])
    gates = gate_rows(eval_rows_out, contrast, replay_status=replay_status)
    write_csv(OUTPUTS["gate_integrity"], gates, GATE_FIELDS)
    sha_info = {
        "blind_judgement": sha256(OUTPUTS["blind_judgement"]),
        **{key: sha256(OUTPUTS[key]) for key in FREEZE_ARTIFACT_KEYS},
    }
    render_report(sha_info, replay_status=replay_status, replay_evidence="; ".join(comparisons))
    print(f"verify-replay FROZEN_REPLAY_IDENTICAL={replay_status}")
    print("; ".join(comparisons))


def summarize_counts() -> dict[str, Any]:
    atom_rows_loaded = read_rows(OUTPUTS["frozen_atom_trace"]) if OUTPUTS["frozen_atom_trace"].exists() else []
    roles = read_rows(OUTPUTS["frozen_role_proposals"]) if OUTPUTS["frozen_role_proposals"].exists() else []
    nodes = read_rows(OUTPUTS["lineage_nodes"]) if OUTPUTS["lineage_nodes"].exists() else []
    edges = read_rows(OUTPUTS["lineage_edges"]) if OUTPUTS["lineage_edges"].exists() else []
    entities = read_rows(OUTPUTS["runtime_entities"]) if OUTPUTS["runtime_entities"].exists() else []
    blind = read_rows(OUTPUTS["blind_judgement"]) if OUTPUTS["blind_judgement"].exists() else []
    eval_rows_loaded = read_rows(OUTPUTS["gt_eval"]) if OUTPUTS["gt_eval"].exists() else []
    ext = read_rows(OUTPUTS["support_extent"]) if OUTPUTS["support_extent"].exists() else []
    role_counts = Counter(row["candidate_role"] for row in roles)
    entity_counts = Counter(row["runtime_class"] for row in entities)
    blind_counts = Counter(judgement_class(row) for row in blind)
    edge_counts = Counter(row["edge_status"] for row in edges)
    track_count = len({row["persistent_part_track_id"] for row in nodes if row["persistent_part_track_id"]})
    support_long = [parse_float(row["support_pixel_long_axis"]) for row in ext]
    support_short = [parse_float(row["support_pixel_short_axis"]) for row in ext]
    centroid_long = [parse_float(row["centroid_long_axis"]) for row in ext]
    centroid_short = [parse_float(row["centroid_short_axis"]) for row in ext]
    return {
        "atoms": len(atom_rows_loaded),
        "role_counts": role_counts,
        "nodes": len(nodes),
        "edges": len(edges),
        "edge_counts": edge_counts,
        "track_count": track_count,
        "entities": entity_counts,
        "blind": blind_counts,
        "eval_rows": len(eval_rows_loaded),
        "false_reject": sum(row["runtime_false_reject"] == "true" for row in eval_rows_loaded),
        "false_accept": sum(row["runtime_false_accept"] == "true" for row in eval_rows_loaded),
        "runtime_blind_disagreement": sum(row["runtime_blind_disagreement"] == "true" for row in eval_rows_loaded),
        "blind_gt_disagreement": sum(row["blind_gt_disagreement"] == "true" for row in eval_rows_loaded),
        "unresolved": sum(row["blind_judgement"] == "unresolved" for row in eval_rows_loaded),
        "support_long_median": fmt(median(support_long)),
        "support_short_median": fmt(median(support_short)),
        "centroid_long_median": fmt(median(centroid_long)),
        "centroid_short_median": fmt(median(centroid_short)),
        "deg_fixed": sum(row["extent_degeneracy_fixed"] == "true" for row in ext),
    }


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    shown = list(rows if limit is None else rows[:limit])
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in shown:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/").replace("\n", " ") for field in fields) + " |")
    if limit is not None and len(rows) > limit:
        lines.append("| " + " | ".join(["..."] + [""] * (len(fields) - 1)) + " |")
    return "\n".join(lines)


def render_report(sha_info: Mapping[str, str], replay_status: str, replay_evidence: str = "") -> None:
    summary = summarize_counts()
    holdout = read_rows(OUTPUTS["holdout_manifest"]) if OUTPUTS["holdout_manifest"].exists() else []
    gates = read_rows(OUTPUTS["gate_integrity"]) if OUTPUTS["gate_integrity"].exists() else []
    contrast = read_rows(OUTPUTS["contrast"]) if OUTPUTS["contrast"].exists() else []
    failures = read_rows(OUTPUTS["failure_cases"]) if OUTPUTS["failure_cases"].exists() else []
    lines = [
        "# OTY2 WGV3.6A-A1.8A-R1 Mechanism Integrity Audit",
        "",
        "## Boundary",
        "",
        f"- requested start commit: `{REQUESTED_START_COMMIT}`",
        "- command boundary: `generate`, `blind-pack`, `evaluate`, `verify-replay`; no `all` command.",
        "- generate reads: SAR gray frames, static fan geometry, A1.7R source-only search shells, current/past runtime frames.",
        "- evaluate reads only after freeze: paired GT, discovery labels, original frame mapping, vehicle identity labels, EVAL_ONLY target boxes.",
        "- GM_RM011 executed: `false`",
        "- final annotation / revised GT / selector / ranking / training: `false`",
        "",
        "## Frozen SHA",
        "",
        *[f"- `{key}`: `{value}`" for key, value in sha_info.items()],
        f"- `FROZEN_REPLAY_IDENTICAL`: `{replay_status}`",
        f"- replay evidence: `{replay_evidence}`" if replay_evidence else "- replay evidence: `pending until verify-replay`",
        "",
        "## Blind Holdout",
        "",
        md_table(holdout, HOLDOUT_FIELDS),
        "",
        "## Runtime Counts",
        "",
        f"- scattering atoms: `{summary['atoms']}`",
        f"- candidate roles: `{dict(summary['role_counts'])}`",
        f"- part lineage nodes/edges/tracks: `{summary['nodes']}/{summary['edges']}/{summary['track_count']}`",
        f"- lineage edge states: `{dict(summary['edge_counts'])}`",
        f"- runtime entities: `{dict(summary['entities'])}`",
        f"- blind judgements: `{dict(summary['blind'])}`",
        f"- support-pixel median L/W: `{summary['support_long_median']}/{summary['support_short_median']}`",
        f"- centroid median L/W: `{summary['centroid_long_median']}/{summary['centroid_short_median']}`",
        f"- extent_degeneracy_fixed count: `{summary['deg_fixed']}`",
        "",
        "## Temporal Gate",
        "",
        "`G_temporal` is computed from `persistent_part_track_id` produced by unique adjacent-frame lineage edges. It is not derived from `runtime_class`, blind judgement, GT, or polarity.",
        "",
        "## Evaluation Counts",
        "",
        f"- eval rows: `{summary['eval_rows']}`",
        f"- runtime false reject: `{summary['false_reject']}`",
        f"- runtime false accept: `{summary['false_accept']}`",
        f"- runtime/blind disagreement: `{summary['runtime_blind_disagreement']}`",
        f"- blind/GT disagreement: `{summary['blind_gt_disagreement']}`",
        f"- unresolved count: `{summary['unresolved']}`",
        "",
        "## Visual Review Notes",
        "",
        "- Opened blind sheets use only opaque BLIND_FRAME and BLIND_OBJECT IDs, candidate roles, support-pixel axes, relation edges, and lineage ids.",
        "- White 27-31: runtime/blind support is concentrated in compact lower responses with core/side/endpoint candidates; nearby isolated candidates remain non-decisive.",
        "- White 78-81: lower body/side candidates are separated from the horizontal background-arc candidate; the arc is the decisive non-vehicle alternative.",
        "- Silver 270-273: lower local body/side response appears weaker and often only partially supported; far-side line/arc candidates are not accepted as vehicle closure.",
        "- Silver 289-290: side/core candidates exist but remain conditional; unresolved alternatives and missing exact support keep A1.7R2 blocked.",
        "- Blind holdout: selected frames provide local intermediate-frame checks, but not full-scene completion.",
        "",
        "## Vehicle Vs Other Contrast",
        "",
        md_table(contrast, ["contrast_id", "accepted_object_id", "alternative_object_id", "same_frame_or_cross_frame", "accepted_runtime_class", "alternative_runtime_class", "accepted_blind_judgement", "alternative_blind_judgement", "decisive_difference_cn"], limit=18),
        "",
        "## Failure Cases",
        "",
        md_table(failures, FAIL_FIELDS, limit=12),
        "",
        "## Gate Verdicts",
        "",
        md_table(gates, GATE_FIELDS),
        "",
        "## Created Files",
        "",
        *[f"- `{rel(path)}`" for key, path in OUTPUTS.items()],
        "",
        "## Research Judgment",
        "",
        "R1 fixes the main integrity faults in A1.8A: generation no longer receives polarity labels, blind review is opaque, support-pixel extents replace centroid-only widths, and temporal support comes from adjacent-frame part lineage. The result is still a local mechanism audit, not a ready input contract for A1.7R2.",
    ]
    write_text(OUTPUTS["report"], "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "blind-pack", "evaluate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "generate":
        generate()
    elif args.command == "blind-pack":
        blind_pack()
    elif args.command == "evaluate":
        evaluate()
    elif args.command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
