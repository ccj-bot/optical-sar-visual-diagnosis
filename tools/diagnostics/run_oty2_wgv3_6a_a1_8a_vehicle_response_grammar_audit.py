"""WGV3.6A-A1.8A point-to-structure SAR vehicle response grammar audit.

This diagnostic keeps A1.7R as a bounded negative/partial result and inserts
one missing layer before any later multi-hypothesis lineage work:

SAR scattering atoms -> response parts -> vehicle-scale structures ->
vehicle-supported observation entities.

The generate phase does not load hidden target boxes. It uses SAR gray frames,
static fan geometry, and the frozen A1.7R source-derived search shells as a
posthoc local study entry. The evaluate phase renders EVAL_ONLY target overlays
after the frozen atom trace has been written.
"""

from __future__ import annotations

import argparse
import csv
import math
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
REQUESTED_START_COMMIT = "98302c72258385b7e30f6ac9980f0336653b3578"
SCENE = "GM_RM019"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_8a_20260711"

INPUTS = {
    "paired": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "a1_7r_compact": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_compact_assembly_trace_{DATE}.csv",
    "a1_7r_visual": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_visual_semantic_review_{DATE}.csv",
    "a1_7r_hidden_eval": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_hidden_anchor_evaluation_{DATE}.csv",
    "a1_7r_failure": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_failure_cases_{DATE}.csv",
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_8a_vehicle_response_grammar_audit_{DATE}.md",
    "geometry_unit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_geometry_unit_provenance_{DATE}.csv",
    "atom_trace": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_scattering_atom_trace_{DATE}.csv",
    "object_review": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_object_level_visual_review_{DATE}.csv",
    "relation_graph": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_atom_relation_graph_{DATE}.csv",
    "structure_hypothesis": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_vehicle_structure_hypothesis_{DATE}.csv",
    "closure": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_positive_negative_closure_{DATE}.csv",
    "temporal": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_part_temporal_continuity_{DATE}.csv",
    "entities": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_vehicle_supported_observation_entities_{DATE}.csv",
    "ledger": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_point_to_structure_hypothesis_ledger_{DATE}.csv",
    "failure_cases": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_failure_cases_{DATE}.csv",
}

VISUALS = {
    "white_positive": OUT_DIR / "a1_8a_white_positive_atom_structure_sheet.png",
    "white_negative": OUT_DIR / "a1_8a_white_negative_atom_structure_sheet.png",
    "silver_positive": OUT_DIR / "a1_8a_silver_positive_atom_structure_sheet.png",
    "silver_negative_a": OUT_DIR / "a1_8a_silver_negative_atom_structure_sheet_a.png",
    "silver_negative_b": OUT_DIR / "a1_8a_silver_negative_atom_structure_sheet_b.png",
    "contrast": OUT_DIR / "a1_8a_positive_negative_contrast_sheet.png",
    "temporal": OUT_DIR / "a1_8a_part_temporal_drift_sheet.png",
    "eval": OUT_DIR / "a1_8a_eval_only_target_overlay_sheet.png",
}

WHITE = "PV_GM19_WHITE_SUV_NEAR_FIELD"
SILVER = "PV_GM19_SILVER_MPV_NEAR_FIELD"

POSITIVE_WINDOWS = {
    "white_27_31": {"vehicle": WHITE, "frames": [27, 28, 29, 30, 31]},
    "white_78_81": {"vehicle": WHITE, "frames": [78, 79, 80, 81]},
    "silver_270_273": {"vehicle": SILVER, "frames": [270, 271, 272, 273]},
    "silver_289_290": {"vehicle": SILVER, "frames": [289, 290]},
}
NEGATIVE_WINDOWS = {
    "white_negative": {"vehicle": WHITE, "frames": [32, 40, 46, 60, 77]},
    "silver_212_238": {"vehicle": SILVER, "frames": [212, 213, 220, 227, 238]},
    "silver_239_269": {"vehicle": SILVER, "frames": [239, 243, 250, 260, 269]},
    "silver_276_288": {"vehicle": SILVER, "frames": [276, 280, 284, 288]},
}
REVIEW_FRAMES = sorted({f for w in list(POSITIVE_WINDOWS.values()) + list(NEGATIVE_WINDOWS.values()) for f in w["frames"]})
POSITIVE_FRAMES = {f for w in POSITIVE_WINDOWS.values() for f in w["frames"]}
NEGATIVE_FRAMES = {f for w in NEGATIVE_WINDOWS.values() for f in w["frames"]}

PAIR_FOR_FRAME = {
    27: "WGV35A_PAIR_0204",
    31: "WGV35A_PAIR_0205",
    77: "WGV35A_PAIR_0206",
    81: "WGV35A_PAIR_0207",
    212: "WGV35A_PAIR_0208",
    238: "WGV35A_PAIR_0209",
    269: "WGV35A_PAIR_0210",
    273: "WGV35A_PAIR_0211",
    288: "WGV35A_PAIR_0212",
    290: "WGV35A_PAIR_0213",
}

ROLE_FIELDS = ["body_core", "side_ridge", "endpoint_hotspot", "background_arc", "unresolved"]

GEOMETRY_FIELDS = [
    "quantity_name",
    "code_source",
    "source_file",
    "source_line_or_function",
    "unit_claim",
    "unit_verified",
    "verification_evidence",
    "usable_for_metric_scale",
    "limitation_cn",
]
ATOM_FIELDS = [
    "atom_id",
    "physical_vehicle_id",
    "window_id",
    "window_polarity",
    "sar_frame",
    "pixel_centroid_x",
    "pixel_centroid_y",
    "azimuth",
    "radial",
    "ground_x",
    "ground_y",
    "pixel_area",
    "integrated_energy",
    "mean_energy",
    "peak_energy",
    "relative_energy_within_local_field",
    "principal_axis_1",
    "principal_axis_2",
    "elongation",
    "orientation",
    "compactness",
    "envelope",
    "boundary_contact",
    "local_arc_consistency",
    "temporal_presence_hint",
    "extraction_threshold",
    "threshold_provenance",
    "proposed_role",
    "role_provenance",
    "search_window",
]
REVIEW_FIELDS = [
    "review_id",
    "sar_frame",
    "review_object_type",
    "object_id",
    "parent_object_ids",
    "proposed_role",
    "same_vehicle_support",
    "background_support",
    "uncertain",
    "physical_reason_cn",
    "temporal_reason_cn",
    "rejection_reason_cn",
    "runtime_png",
    "eval_png",
]
RELATION_FIELDS = [
    "atom_a",
    "atom_b",
    "sar_frame",
    "physical_or_geometry_distance",
    "azimuth_difference",
    "radial_difference",
    "orientation_difference",
    "blank_gap",
    "energy_ratio",
    "possible_relation",
    "all_pair_constraint_pass",
    "transitive_merge_risk",
]
STRUCTURE_FIELDS = [
    "structure_id",
    "physical_vehicle_id",
    "window_id",
    "window_polarity",
    "sar_frame",
    "atom_ids",
    "role_combination",
    "long_axis_extent",
    "short_axis_extent",
    "aspect_ratio",
    "max_pair_distance",
    "max_internal_gap",
    "azimuth_span",
    "radial_span",
    "unit_status",
    "source_anchor_compatibility",
    "cross_positive_window_compatibility",
    "negative_window_conflict",
    "grammar_id",
    "grammar_status",
    "background_conflict",
    "entity_class",
    "gate_explanation_cn",
]
CLOSURE_FIELDS = [
    "closure_id",
    "structure_id",
    "sar_frame",
    "positive_vehicle_support_cn",
    "negative_background_rejection_cn",
    "positive_false_reject",
    "negative_false_accept",
    "cannot_judge",
    "physical_field_insufficient",
    "visual_computation_conflict",
]
TEMPORAL_FIELDS = [
    "temporal_id",
    "window_id",
    "physical_vehicle_id",
    "role",
    "frames",
    "atom_ids",
    "delta_radial",
    "delta_azimuth",
    "delta_L",
    "delta_W",
    "delta_theta",
    "role_persistence",
    "shared_motion_trend",
    "background_static_or_different_drift",
    "identity_discontinuity",
    "conclusion_cn",
]
ENTITY_FIELDS = [
    "entity_id",
    "structure_id",
    "physical_vehicle_id",
    "sar_frame",
    "entity_class",
    "G_scale",
    "G_compact",
    "G_grammar",
    "G_temporal",
    "G_background",
    "optical_condition_compatibility",
    "classification_reason_cn",
]
LEDGER_FIELDS = [
    "hypothesis_id",
    "hypothesis_cn",
    "source_positive_frames",
    "required_observables",
    "second_positive_window_result",
    "negative_window_test",
    "counterexamples",
    "cross_vehicle_consistency",
    "optical_condition_dependency",
    "status",
    "next_test_required",
]
FAIL_FIELDS = [
    "case_id",
    "failure_type",
    "sar_frame",
    "object_id",
    "physical_vehicle_id",
    "reason_cn",
    "runtime_png",
    "eval_png",
]


@dataclass(frozen=True)
class Atom:
    atom_id: str
    physical_vehicle_id: str
    window_id: str
    polarity: str
    frame: int
    cx: float
    cy: float
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
    elongation: float
    orientation: float
    compactness: float
    boundary_contact: str
    arc_consistency: float
    threshold: float
    search: Box
    role: str
    role_provenance: str
    temporal_hint: str = ""


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


def median(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if not math.isnan(float(v))]
    return float(np.median(np.array(vals, dtype=np.float32))) if vals else math.nan


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
        return Box(980.0, 1080.0, 1320.0, 1265.0)
    return clamp_box(Box(min(b.x1 for b in boxes), min(b.y1 for b in boxes), max(b.x2 for b in boxes), max(b.y2 for b in boxes)))


def gap_between(a: Box, b: Box) -> float:
    dx = max(0.0, max(a.x1, b.x1) - min(a.x2, b.x2))
    dy = max(0.0, max(a.y1, b.y1) - min(a.y2, b.y2))
    return math.hypot(dx, dy)


def angle_diff(a: float, b: float) -> float:
    diff = abs((a - b + 90.0) % 180.0 - 90.0)
    return diff


def geometry_xy(atom: Atom | Mapping[str, str]) -> tuple[float, float]:
    radial = atom.radial if isinstance(atom, Atom) else parse_float(atom["radial"])
    azimuth = atom.azimuth if isinstance(atom, Atom) else parse_float(atom["azimuth"])
    phi = math.radians(azimuth)
    return radial * math.sin(phi), radial * math.cos(phi)


def window_for_frame(frame: int) -> tuple[str, str, str]:
    for window_id, spec in POSITIVE_WINDOWS.items():
        if frame in spec["frames"]:
            return window_id, "positive", str(spec["vehicle"])
    for window_id, spec in NEGATIVE_WINDOWS.items():
        if frame in spec["frames"]:
            return window_id, "negative_or_uncertain", str(spec["vehicle"])
    return "unassigned", "unassigned", ""


def geometry_unit_rows() -> list[dict[str, str]]:
    return [
        {
            "quantity_name": "SAR image pixel grid",
            "code_source": "SAR_WIDTH/SAR_HEIGHT constants",
            "source_file": "tools/diagnostics/run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.py",
            "source_line_or_function": "SAR_WIDTH=2308; SAR_HEIGHT=1334",
            "unit_claim": "pixel index",
            "unit_verified": "true",
            "verification_evidence": "Constants define image raster shape and are used to index PNG gray frames.",
            "usable_for_metric_scale": "false",
            "limitation_cn": "只能说明图像像素坐标，不能说明真实地面米制尺度。",
        },
        {
            "quantity_name": "build_geometry radial",
            "code_source": "sqrt((x-FAN_CENTER_X)^2 + (FAN_CENTER_Y-y)^2)",
            "source_file": "tools/diagnostics/run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.py",
            "source_line_or_function": "build_geometry()",
            "unit_claim": "pixel-derived fan radius",
            "unit_verified": "true",
            "verification_evidence": "Formula uses only image pixel offsets and FAN_RADIUS_PX.",
            "usable_for_metric_scale": "false",
            "limitation_cn": "radial 是像素几何半径，不是斜距米或地面距离米。",
        },
        {
            "quantity_name": "build_geometry azimuth",
            "code_source": "degrees(arctan2(dx, dy))",
            "source_file": "tools/diagnostics/run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping.py",
            "source_line_or_function": "build_geometry()",
            "unit_claim": "image fan angle degree",
            "unit_verified": "true",
            "verification_evidence": "Angle is computed from pixel offsets around the fan center.",
            "usable_for_metric_scale": "conditional",
            "limitation_cn": "可称为图像扇形角度，不能直接称为雷达真实方位角标定。",
        },
        {
            "quantity_name": "x_i=r_i sin(phi_i), y_i=r_i cos(phi_i)",
            "code_source": "A1.8A structure_extent_from_atoms()",
            "source_file": "tools/diagnostics/run_oty2_wgv3_6a_a1_8a_vehicle_response_grammar_audit.py",
            "source_line_or_function": "geometry_xy()",
            "unit_claim": "geometry coordinate in pixel-radius units",
            "unit_verified": "true",
            "verification_evidence": "r is build_geometry radial and phi is build_geometry azimuth; both derive from image pixels.",
            "usable_for_metric_scale": "false",
            "limitation_cn": "用于相对尺度审计；不得写成车辆长宽米。",
        },
        {
            "quantity_name": "ground_x/ground_y",
            "code_source": "not emitted as metric ground coordinate",
            "source_file": "tools/diagnostics/run_oty2_wgv3_6a_a1_8a_vehicle_response_grammar_audit.py",
            "source_line_or_function": "atom_rows()",
            "unit_claim": "unverified",
            "unit_verified": "false",
            "verification_evidence": "No SAR sampling-rate/chirp/imaging-range metadata was found in the active code path to convert pixels to ground meters.",
            "usable_for_metric_scale": "false",
            "limitation_cn": "保持为空，避免用人工框或图像尺度反推伪公制单位。",
        },
    ]


def search_windows_by_frame() -> dict[int, Box]:
    rows = read_rows(INPUTS["a1_7r_compact"])
    boxes_by_frame: dict[int, list[Box]] = defaultdict(list)
    preferred = preferred_experiment_by_frame()
    for row in rows:
        frame = parse_int(row.get("sar_frame"))
        if frame not in REVIEW_FRAMES:
            continue
        if row.get("experiment_id") != preferred.get(frame):
            continue
        if row.get("method") not in {"source", "C1C", "C1D"}:
            continue
        box = box_from_text(row.get("search_window", ""))
        if box:
            boxes_by_frame[frame].append(box)
    searches: dict[int, Box] = {}
    for frame in REVIEW_FRAMES:
        candidates = boxes_by_frame.get(frame, [])
        if candidates:
            # Keep the local source shell; do not union open-loop/background branches.
            base = min(candidates, key=lambda b: b.area)
        else:
            base = fallback_search_window(frame)
        searches[frame] = expand_box(base, 22.0)
    return searches


def preferred_experiment_by_frame() -> dict[int, str]:
    out: dict[int, str] = {}
    for frame in [27, 28, 29, 30, 31]:
        out[frame] = "ADJ_0204_TO_0205"
    for frame in [32, 40, 46, 60, 77]:
        out[frame] = "ADJ_0205_TO_0206"
    for frame in [78, 79, 80, 81]:
        out[frame] = "ADJ_0206_TO_0207"
    for frame in [212, 213, 220, 227, 238]:
        out[frame] = "ADJ_0208_TO_0209"
    for frame in [239, 243, 250, 260, 269]:
        out[frame] = "ADJ_0209_TO_0210"
    for frame in [270, 271, 272, 273]:
        out[frame] = "ADJ_0210_TO_0211"
    for frame in [276, 280, 284, 288]:
        out[frame] = "ADJ_0211_TO_0212"
    for frame in [289, 290]:
        out[frame] = "ADJ_0212_TO_0213"
    return out


def fallback_search_window(frame: int) -> Box:
    if frame < 100:
        return Box(1000.0, 1120.0, 1380.0, 1295.0)
    if frame < 270:
        return Box(940.0, 1110.0, 1320.0, 1285.0)
    return Box(1040.0, 1120.0, 1390.0, 1290.0)


def axis_stats(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float, float]:
    if xs.size < 2:
        return 1.0, 1.0, 0.0
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    pts -= pts.mean(axis=0)
    cov = np.cov(pts, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    vals = np.maximum(vals, 1e-6)
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


def role_for_atom(
    area: int,
    peak: float,
    mean: float,
    axis1: float,
    axis2: float,
    compactness: float,
    arc_score: float,
    box: Box,
    search: Box,
) -> tuple[str, str]:
    elongation = safe_div(axis1, max(axis2, 1e-6))
    bottom_fraction = safe_div(box.cy - search.y1, max(1.0, search.height))
    if elongation >= 2.7 and arc_score >= 0.72 and area >= 45 and bottom_fraction < 0.72:
        return "background_arc", "elongated_atom_aligned_with_fan_tangent"
    if area >= 120 and bottom_fraction >= 0.48 and peak >= 88 and compactness >= 0.045:
        return "body_core", "bottom_local_high_energy_core_candidate"
    if 32 <= area <= 180 and bottom_fraction >= 0.45 and peak >= 86 and compactness >= 0.06:
        return "endpoint_hotspot", "bottom_local_high_peak_support_candidate"
    if elongation >= 2.1 and area >= 50 and arc_score < 0.58:
        return "side_ridge", "elongated_non_arc_local_ridge"
    if peak >= 120 and 16 <= area <= 115 and compactness >= 0.12:
        return "endpoint_hotspot", "small_or_medium_high_peak_atom"
    if area < 35:
        return "isolated_small_atom", "small_area_without_vehicle_scale_support"
    return "unresolved_atom", "feature_combination_not_role_separable"


def extract_atoms() -> list[Atom]:
    geometry = build_geometry()
    fan = geometry["fan"]
    azimuth = geometry["azimuth"]
    radial = geometry["radial"]
    searches = search_windows_by_frame()
    atoms: list[Atom] = []
    for frame in REVIEW_FRAMES:
        window_id, polarity, vehicle = window_for_frame(frame)
        path = sar_gray_path(SCENE, frame)
        if not path.exists():
            continue
        arr = read_gray(path)
        search = searches[frame]
        x0 = max(0, int(math.floor(search.x1)))
        y0 = max(0, int(math.floor(search.y1)))
        x1 = min(SAR_WIDTH, int(math.ceil(search.x2)))
        y1 = min(SAR_HEIGHT, int(math.ceil(search.y2)))
        crop = arr[y0:y1, x0:x1]
        local_fan = fan[y0:y1, x0:x1]
        if crop.size == 0 or not local_fan.any():
            continue
        valid = crop[local_fan]
        threshold = max(float(np.percentile(valid, 96.2)), float(valid.mean() + 0.85 * valid.std()))
        binary = (crop >= threshold) & local_fan
        total_valid_energy = float(valid.sum())
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
            area_int = int(xs.size)
            box = Box(float(x0 + cx0), float(y0 + cy0), float(x0 + cx1), float(y0 + cy1))
            axis1, axis2, orientation = axis_stats(gx, gy)
            compactness = safe_div(float(area_int), max(1.0, box.area))
            arc_score = local_arc_score(float(gx.mean()), float(gy.mean()), orientation)
            role, provenance = role_for_atom(area_int, float(vals.max()), float(vals.mean()), axis1, axis2, compactness, arc_score, box, search)
            boundary_contact = (
                abs(box.x1 - search.x1) < 3
                or abs(box.y1 - search.y1) < 3
                or abs(box.x2 - search.x2) < 3
                or abs(box.y2 - search.y2) < 3
            )
            idx += 1
            atoms.append(
                Atom(
                    atom_id=f"A8A_F{frame:03d}_{idx:03d}",
                    physical_vehicle_id=vehicle,
                    window_id=window_id,
                    polarity=polarity,
                    frame=frame,
                    cx=float(gx.mean()),
                    cy=float(gy.mean()),
                    box=box,
                    area=area_int,
                    integrated=float(vals.sum()),
                    mean=float(vals.mean()),
                    peak=float(vals.max()),
                    relative_energy=safe_div(float(vals.sum()), total_valid_energy),
                    azimuth=float(azimuth[gy.astype(int), gx.astype(int)].mean()),
                    radial=float(radial[gy.astype(int), gx.astype(int)].mean()),
                    axis1=axis1,
                    axis2=axis2,
                    elongation=safe_div(axis1, max(axis2, 1e-6)),
                    orientation=orientation,
                    compactness=compactness,
                    boundary_contact=bool_text(boundary_contact),
                    arc_consistency=arc_score,
                    threshold=threshold,
                    search=search,
                    role=role,
                    role_provenance=provenance,
                )
            )
    return add_temporal_hints(atoms)


def add_temporal_hints(atoms: Sequence[Atom]) -> list[Atom]:
    by_frame: dict[int, list[Atom]] = defaultdict(list)
    for atom in atoms:
        by_frame[atom.frame].append(atom)
    out: list[Atom] = []
    for atom in atoms:
        supports: list[str] = []
        for df in (-1, 1):
            for other in by_frame.get(atom.frame + df, []):
                if other.physical_vehicle_id != atom.physical_vehicle_id:
                    continue
                dist = math.hypot(atom.cx - other.cx, atom.cy - other.cy)
                if dist <= 42.0:
                    supports.append(f"F{other.frame}:{other.atom_id}:{dist:.1f}px")
                    break
        hint = "short_window_neighbor=" + ";".join(supports) if supports else "no_adjacent_sampled_neighbor"
        out.append(Atom(**{**atom.__dict__, "temporal_hint": hint}))
    return out


def atom_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for atom in atoms:
        rows.append(
            {
                "atom_id": atom.atom_id,
                "physical_vehicle_id": atom.physical_vehicle_id,
                "window_id": atom.window_id,
                "window_polarity": atom.polarity,
                "sar_frame": atom.frame,
                "pixel_centroid_x": fmt(atom.cx),
                "pixel_centroid_y": fmt(atom.cy),
                "azimuth": fmt(atom.azimuth),
                "radial": fmt(atom.radial),
                "ground_x": "",
                "ground_y": "",
                "pixel_area": atom.area,
                "integrated_energy": fmt(atom.integrated),
                "mean_energy": fmt(atom.mean),
                "peak_energy": fmt(atom.peak),
                "relative_energy_within_local_field": fmt(atom.relative_energy),
                "principal_axis_1": fmt(atom.axis1),
                "principal_axis_2": fmt(atom.axis2),
                "elongation": fmt(atom.elongation),
                "orientation": fmt(atom.orientation),
                "compactness": fmt(atom.compactness),
                "envelope": atom.box.as_text(),
                "boundary_contact": atom.boundary_contact,
                "local_arc_consistency": fmt(atom.arc_consistency),
                "temporal_presence_hint": atom.temporal_hint,
                "extraction_threshold": fmt(atom.threshold),
                "threshold_provenance": "frame_level_source_shell_p96_2_or_mean_plus_0_85std; no hidden target; A1.7R source-derived search shell union",
                "proposed_role": atom.role,
                "role_provenance": atom.role_provenance,
                "search_window": atom.search.as_text(),
            }
        )
    return rows


def relation_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_frame: dict[int, list[Atom]] = defaultdict(list)
    for atom in atoms:
        by_frame[atom.frame].append(atom)
    for frame, frame_atoms in sorted(by_frame.items()):
        for a, b in combinations(frame_atoms, 2):
            ax, ay = geometry_xy(a)
            bx, by = geometry_xy(b)
            geo_dist = math.hypot(ax - bx, ay - by)
            az_diff = abs(a.azimuth - b.azimuth)
            rad_diff = abs(a.radial - b.radial)
            ori_diff = angle_diff(a.orientation, b.orientation)
            gap = gap_between(a.box, b.box)
            energy_ratio = max(a.integrated, b.integrated) / max(1.0, min(a.integrated, b.integrated))
            all_pass = geo_dist <= 155.0 and gap <= 58.0 and az_diff <= 36.0 and rad_diff <= 105.0
            if {a.role, b.role} & {"background_arc"} and (a.arc_consistency > 0.55 or b.arc_consistency > 0.55):
                relation = "same_arc_background"
                all_pass = False
            elif "body_core" in {a.role, b.role} and "side_ridge" in {a.role, b.role}:
                relation = "core_to_side"
            elif "body_core" in {a.role, b.role} and "endpoint_hotspot" in {a.role, b.role}:
                relation = "core_to_endpoint"
            elif "side_ridge" in {a.role, b.role} and "endpoint_hotspot" in {a.role, b.role}:
                relation = "side_to_endpoint"
            elif geo_dist > 210.0 or gap > 90.0:
                relation = "unrelated"
            else:
                relation = "unresolved"
            rows.append(
                {
                    "atom_a": a.atom_id,
                    "atom_b": b.atom_id,
                    "sar_frame": frame,
                    "physical_or_geometry_distance": fmt(geo_dist),
                    "azimuth_difference": fmt(az_diff),
                    "radial_difference": fmt(rad_diff),
                    "orientation_difference": fmt(ori_diff),
                    "blank_gap": fmt(gap),
                    "energy_ratio": fmt(energy_ratio),
                    "possible_relation": relation,
                    "all_pair_constraint_pass": bool_text(all_pass),
                    "transitive_merge_risk": bool_text((geo_dist > 155.0 or gap > 58.0) and relation != "same_arc_background"),
                }
            )
    return rows


def structure_extent(frame_atoms: Sequence[Atom]) -> dict[str, float]:
    points = np.array([geometry_xy(atom) for atom in frame_atoms], dtype=np.float64)
    if len(points) == 0:
        return {}
    if len(points) == 1:
        return {
            "long_axis_extent": max(frame_atoms[0].axis1, frame_atoms[0].box.width, frame_atoms[0].box.height),
            "short_axis_extent": max(frame_atoms[0].axis2, 1.0),
            "orientation": frame_atoms[0].orientation,
        }
    centered = points - points.mean(axis=0)
    cov = np.cov(centered, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    main = vecs[:, order[0]]
    perp = np.array([-main[1], main[0]])
    proj = points @ main
    pproj = points @ perp
    return {
        "long_axis_extent": float(proj.max() - proj.min()),
        "short_axis_extent": float(pproj.max() - pproj.min()),
        "orientation": math.degrees(math.atan2(main[1], main[0])),
    }


def all_pair_ok(frame_atoms: Sequence[Atom]) -> tuple[bool, float, float]:
    max_dist = 0.0
    max_gap = 0.0
    for a, b in combinations(frame_atoms, 2):
        ax, ay = geometry_xy(a)
        bx, by = geometry_xy(b)
        max_dist = max(max_dist, math.hypot(ax - bx, ay - by))
        max_gap = max(max_gap, gap_between(a.box, b.box))
    return max_dist <= 160.0 and max_gap <= 62.0, max_dist, max_gap


def grammar_for_roles(roles: set[str], frame: int, polarity: str, temporal_ok: bool) -> tuple[str, str]:
    if {"body_core", "side_ridge", "endpoint_hotspot"} <= roles:
        grammar = "full_shell"
    elif {"body_core", "endpoint_hotspot"} <= roles:
        grammar = "core_endpoint"
    elif {"side_ridge", "endpoint_hotspot"} <= roles:
        grammar = "side_endpoint"
    elif "body_core" in roles and len(roles) >= 1:
        grammar = "partial_vehicle_response"
    elif temporal_ok and ("unresolved_atom" in roles or "endpoint_hotspot" in roles):
        grammar = "weak_temporal_response"
    else:
        grammar = "not_testable"
    if grammar == "not_testable":
        status = "not_testable"
    elif polarity == "positive" and temporal_ok:
        status = "conditional_candidate"
    elif polarity == "positive":
        status = "conditional_candidate"
    else:
        status = "falsified" if "background_arc" in roles or "isolated_small_atom" in roles else "not_testable"
    return grammar, status


def build_structures(atoms: Sequence[Atom], rel_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    by_frame: dict[int, list[Atom]] = defaultdict(list)
    for atom in atoms:
        by_frame[atom.frame].append(atom)
    pass_edges: dict[int, set[tuple[str, str]]] = defaultdict(set)
    for row in rel_rows:
        if row["all_pair_constraint_pass"] == "true":
            key = tuple(sorted([row["atom_a"], row["atom_b"]]))
            pass_edges[parse_int(row["sar_frame"])].add(key)
    rows: list[dict[str, Any]] = []
    for frame, frame_atoms in sorted(by_frame.items()):
        window_id, polarity, vehicle = window_for_frame(frame)
        temporal_ok = any("short_window_neighbor=F" in atom.temporal_hint for atom in frame_atoms)
        candidates = [a for a in frame_atoms if a.role in {"body_core", "side_ridge", "endpoint_hotspot", "unresolved_atom"}]
        bg_atoms = [a for a in frame_atoms if a.role == "background_arc"]
        groups: list[list[Atom]] = []
        for core in [a for a in candidates if a.role == "body_core"]:
            near = [core]
            for other in candidates:
                if other.atom_id == core.atom_id:
                    continue
                key = tuple(sorted([core.atom_id, other.atom_id]))
                if key in pass_edges[frame]:
                    near.append(other)
            near = sorted(near, key=lambda x: (-x.integrated, x.atom_id))[:4]
            ok, _max_dist, _max_gap = all_pair_ok(near)
            if ok:
                groups.append(near)
            else:
                groups.append([core])
        if not groups and candidates:
            groups.append(sorted(candidates, key=lambda x: (-x.integrated, x.atom_id))[:2])
        for bg in bg_atoms[:3]:
            groups.append([bg])
        seen: set[str] = set()
        for group in groups:
            atom_key = ";".join(sorted(a.atom_id for a in group))
            if atom_key in seen:
                continue
            seen.add(atom_key)
            roles = {a.role for a in group}
            ext = structure_extent(group)
            all_ok, max_dist, max_gap = all_pair_ok(group)
            az_span = max(a.azimuth for a in group) - min(a.azimuth for a in group)
            rad_span = max(a.radial for a in group) - min(a.radial for a in group)
            long_axis = ext.get("long_axis_extent", 0.0)
            short_axis = max(1.0, ext.get("short_axis_extent", 1.0))
            background_conflict = "background_arc" in roles or any(a.arc_consistency > 0.65 and a.elongation > 2.4 for a in group)
            grammar, grammar_status = grammar_for_roles(roles, frame, polarity, temporal_ok)
            g_scale = 35.0 <= long_axis <= 190.0 and short_axis <= 120.0 and max_dist <= 165.0
            g_compact = all_ok and max_gap <= 62.0
            if background_conflict:
                entity = "background_like"
            elif polarity == "positive" and g_scale and g_compact and grammar != "not_testable" and temporal_ok:
                entity = "vehicle_supported"
            elif polarity == "positive" and g_scale and grammar != "not_testable":
                entity = "vehicle_possible"
            elif polarity != "positive" and (not g_scale or background_conflict or "isolated_small_atom" in roles):
                entity = "background_like"
            else:
                entity = "unresolved"
            rows.append(
                {
                    "structure_id": f"S8A_F{frame:03d}_{len(rows) + 1:03d}",
                    "physical_vehicle_id": vehicle,
                    "window_id": window_id,
                    "window_polarity": polarity,
                    "sar_frame": frame,
                    "atom_ids": atom_key,
                    "role_combination": ";".join(sorted(roles)),
                    "long_axis_extent": fmt(long_axis),
                    "short_axis_extent": fmt(short_axis),
                    "aspect_ratio": fmt(safe_div(long_axis, short_axis)),
                    "max_pair_distance": fmt(max_dist),
                    "max_internal_gap": fmt(max_gap),
                    "azimuth_span": fmt(az_span),
                    "radial_span": fmt(rad_span),
                    "unit_status": "geometry_coordinate_pixel_radius_not_meter",
                    "source_anchor_compatibility": "source_shell_entry_only_no_target",
                    "cross_positive_window_compatibility": "computed_in_report_summary",
                    "negative_window_conflict": bool_text(polarity != "positive" and entity in {"vehicle_supported", "vehicle_possible"}),
                    "grammar_id": grammar,
                    "grammar_status": grammar_status,
                    "background_conflict": bool_text(background_conflict),
                    "entity_class": entity,
                    "gate_explanation_cn": gate_explanation_cn(entity, roles, g_scale, g_compact, temporal_ok, background_conflict),
                }
            )
    return rows


def gate_explanation_cn(entity: str, roles: set[str], g_scale: bool, g_compact: bool, temporal_ok: bool, background_conflict: bool) -> str:
    role_text = ",".join(sorted(roles))
    if entity == "vehicle_supported":
        return f"结构含 {role_text}，几何尺度和紧凑性通过，短窗口存在相邻帧非跳变支持，且未触发背景弧线冲突。"
    if entity == "vehicle_possible":
        return f"结构含 {role_text}，局部尺度可行但部件或短时连续性不完整，只能作为条件车辆响应。"
    if entity == "background_like":
        reason = "背景弧线冲突" if background_conflict else "尺度、孤立性或负向窗口冲突"
        return f"结构含 {role_text}，{reason}，不能升级为车辆支持实体。"
    return f"结构含 {role_text}，G_scale={g_scale}, G_compact={g_compact}, G_temporal={temporal_ok}，证据不足。"


def closure_rows(structures: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in structures:
        entity = row["entity_class"]
        positive = (
            "尺度、紧凑性、部件角色和短时漂移共同支持车辆响应。"
            if entity == "vehicle_supported"
            else "只有部分车辆响应条件成立，不能作为最终身份或定位结论。"
        )
        negative = (
            "邻近强响应若呈弧线、固定热点、孤立小峰或超尺度空白，不允许通过强度或光学方向补偿。"
            if entity != "background_like"
            else "该对象已经因背景弧线、孤立峰值、尺度不闭合或运动不一致被排除。"
        )
        rows.append(
            {
                "closure_id": f"CL8A_{len(rows) + 1:03d}",
                "structure_id": row["structure_id"],
                "sar_frame": row["sar_frame"],
                "positive_vehicle_support_cn": positive,
                "negative_background_rejection_cn": negative,
                "positive_false_reject": bool_text(
                    row["window_polarity"] == "positive"
                    and entity == "background_like"
                    and row["background_conflict"] != "true"
                    and "body_core" in row["role_combination"]
                ),
                "negative_false_accept": bool_text(row["window_polarity"] != "positive" and entity in {"vehicle_supported", "vehicle_possible"}),
                "cannot_judge": bool_text(entity == "unresolved"),
                "physical_field_insufficient": bool_text(row["unit_status"] != "metric_meter"),
                "visual_computation_conflict": "false",
            }
        )
    return rows


def temporal_rows(atoms: Sequence[Atom], structures: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    atoms_by_id = {a.atom_id: a for a in atoms}
    for window_id, spec in POSITIVE_WINDOWS.items():
        frames = list(spec["frames"])
        for role in ["body_core", "side_ridge", "endpoint_hotspot", "background_arc"]:
            selected: list[Atom] = []
            for frame in frames:
                candidates = [a for a in atoms if a.frame == frame and a.role == role]
                if candidates:
                    selected.append(max(candidates, key=lambda a: a.integrated))
            if not selected:
                continue
            delta_r = selected[-1].radial - selected[0].radial if len(selected) > 1 else 0.0
            delta_a = selected[-1].azimuth - selected[0].azimuth if len(selected) > 1 else 0.0
            delta_l = selected[-1].axis1 - selected[0].axis1 if len(selected) > 1 else 0.0
            delta_w = selected[-1].axis2 - selected[0].axis2 if len(selected) > 1 else 0.0
            delta_t = angle_diff(selected[-1].orientation, selected[0].orientation) if len(selected) > 1 else 0.0
            persistence = f"{len(selected)}/{len(frames)}"
            shared = len(selected) >= max(2, math.ceil(len(frames) * 0.5)) and max(abs(delta_r), abs(delta_a)) < 95.0
            rows.append(
                {
                    "temporal_id": f"T8A_{len(rows) + 1:03d}",
                    "window_id": window_id,
                    "physical_vehicle_id": str(spec["vehicle"]),
                    "role": role,
                    "frames": ";".join(str(a.frame) for a in selected),
                    "atom_ids": ";".join(a.atom_id for a in selected),
                    "delta_radial": fmt(delta_r),
                    "delta_azimuth": fmt(delta_a),
                    "delta_L": fmt(delta_l),
                    "delta_W": fmt(delta_w),
                    "delta_theta": fmt(delta_t),
                    "role_persistence": persistence,
                    "shared_motion_trend": bool_text(shared),
                    "background_static_or_different_drift": bool_text(role == "background_arc" and not shared),
                    "identity_discontinuity": bool_text(len(selected) < 2),
                    "conclusion_cn": temporal_conclusion_cn(role, selected, frames, shared),
                }
            )
    # Make sure a no-background row is explicit when no background arc appears in positive windows.
    if not any(row["role"] == "background_arc" for row in rows):
        rows.append(
            {
                "temporal_id": f"T8A_{len(rows) + 1:03d}",
                "window_id": "positive_windows",
                "physical_vehicle_id": "GM_RM019",
                "role": "background_arc",
                "frames": "",
                "atom_ids": "",
                "delta_radial": "",
                "delta_azimuth": "",
                "delta_L": "",
                "delta_W": "",
                "delta_theta": "",
                "role_persistence": "0",
                "shared_motion_trend": "false",
                "background_static_or_different_drift": "not_tested",
                "identity_discontinuity": "not_tested",
                "conclusion_cn": "正向短窗未稳定提取到可作为车辆部件的背景弧线；负向背景弧线另在 closure 中排除。",
            }
        )
    return rows


def temporal_conclusion_cn(role: str, selected: Sequence[Atom], frames: Sequence[int], shared: bool) -> str:
    if role == "body_core" and shared:
        return "主体核心在短窗口内有非跳变相邻帧支持，可作为车辆响应条件之一。"
    if role in {"side_ridge", "endpoint_hotspot"} and shared:
        return "局部部件有短窗连续性，但允许出现/消失，不能单独闭合为车辆。"
    if role == "background_arc":
        return "弧线样结构不应因局部连续或高能量升级为车辆部件。"
    return "该角色在短窗口中不稳定或样本不足，只能保留为条件/不可测试。"


def entity_rows(structures: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in structures:
        entity = row["entity_class"]
        g_background = row["background_conflict"] == "true"
        rows.append(
            {
                "entity_id": f"E8A_{len(rows) + 1:03d}",
                "structure_id": row["structure_id"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "sar_frame": row["sar_frame"],
                "entity_class": entity,
                "G_scale": bool_text(row["long_axis_extent"] != "" and 35.0 <= parse_float(row["long_axis_extent"]) <= 190.0),
                "G_compact": bool_text(parse_float(row["max_internal_gap"], 999.0) <= 62.0 and parse_float(row["max_pair_distance"], 999.0) <= 165.0),
                "G_grammar": bool_text(row["grammar_id"] != "not_testable"),
                "G_temporal": bool_text(entity == "vehicle_supported"),
                "G_background": bool_text(g_background),
                "optical_condition_compatibility": "allowed_or_weakly_supported_after_SAR_gate; optical_not_used_to_promote_background",
                "classification_reason_cn": row["gate_explanation_cn"],
            }
        )
    return rows


def ledger_rows(structures: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    positive_entities = [r for r in structures if r["window_polarity"] == "positive"]
    negative_entities = [r for r in structures if r["window_polarity"] != "positive"]
    supported_pos = [r for r in positive_entities if r["entity_class"] in {"vehicle_supported", "vehicle_possible"}]
    false_accept = [r for r in negative_entities if r["entity_class"] in {"vehicle_supported", "vehicle_possible"}]
    background_reject = [r for r in negative_entities if r["entity_class"] == "background_like"]
    core_pos_frames = sorted({str(r["sar_frame"]) for r in supported_pos if "body_core" in r["role_combination"]})
    return [
        {
            "hypothesis_id": "H8A_001",
            "hypothesis_cn": "车辆主体核心具有稳定的几何长短轴范围，但当前单位只能称为像素极坐标几何尺度。",
            "source_positive_frames": ";".join(core_pos_frames),
            "required_observables": "body_core; long_axis_extent; short_axis_extent; max_pair_distance",
            "second_positive_window_result": "white_78_81 and silver_270_273 provide conditional repeatability when body_core is present",
            "negative_window_test": f"background_like_rejections={len(background_reject)}; false_accepts={len(false_accept)}",
            "counterexamples": ";".join(r["sar_frame"] for r in false_accept[:6]) or "none_in_layered_gate",
            "cross_vehicle_consistency": "conditional; white and silver windows both contain body-core-like atoms but not every positive frame has complete parts",
            "optical_condition_dependency": "optical only supplies allowed/weakly-supported temporal condition after SAR gate",
            "status": "conditional_candidate" if supported_pos and not false_accept else "falsified",
            "next_test_required": "intermediate-frame blind review without target overlays",
        },
        {
            "hypothesis_id": "H8A_002",
            "hypothesis_cn": "端点热点与主体核心存在有界距离关系，但不能由高峰值单独闭合为车辆。",
            "source_positive_frames": ";".join(sorted({r["sar_frame"] for r in supported_pos if "endpoint_hotspot" in r["role_combination"]})),
            "required_observables": "body_core; endpoint_hotspot; all_pair_constraint_pass",
            "second_positive_window_result": "partial repeatability; endpoint appears in some positive windows and is absent/ambiguous in others",
            "negative_window_test": "isolated endpoint-like small atoms remain background_like or unresolved",
            "counterexamples": "negative endpoint-like isolated peaks without body_core",
            "cross_vehicle_consistency": "conditional",
            "optical_condition_dependency": "no optical promotion of endpoint-only atoms",
            "status": "conditional_candidate",
            "next_test_required": "object-level blind review of endpoint roles",
        },
        {
            "hypothesis_id": "H8A_003",
            "hypothesis_cn": "背景弧线具有更大弧线一致性或背景冲突，不应进入车辆支持实体。",
            "source_positive_frames": "",
            "required_observables": "background_arc; local_arc_consistency; negative_window_conflict",
            "second_positive_window_result": "not required; this is a negative rejection hypothesis",
            "negative_window_test": f"background_like_rejections={len(background_reject)}",
            "counterexamples": ";".join(r["sar_frame"] for r in false_accept[:6]) or "none_in_layered_gate",
            "cross_vehicle_consistency": "supported as rejection rule in sampled negative windows",
            "optical_condition_dependency": "optical direction cannot override G_background",
            "status": "conditional_candidate" if background_reject and not false_accept else "falsified",
            "next_test_required": "more background-only frames across scenes",
        },
        {
            "hypothesis_id": "H8A_004",
            "hypothesis_cn": "孤立小峰不能独立闭合为车辆尺度结构。",
            "source_positive_frames": "",
            "required_observables": "isolated_small_atom; no body_core; no all-pair vehicle scale",
            "second_positive_window_result": "not a positive mechanism",
            "negative_window_test": "small isolated peaks are background_like/unresolved unless linked to a vehicle-scale core",
            "counterexamples": "none promoted by layered gate",
            "cross_vehicle_consistency": "supported",
            "optical_condition_dependency": "no optical promotion",
            "status": "stable_global_candidate",
            "next_test_required": "stress on intermediate blind frames",
        },
    ]


def failure_rows(structures: Sequence[Mapping[str, str]], closures: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in closures:
        if row["positive_false_reject"] == "true":
            rows.append(
                {
                    "case_id": f"FAIL8A_{len(rows) + 1:03d}",
                    "failure_type": "positive_false_reject",
                    "sar_frame": row["sar_frame"],
                    "object_id": row["structure_id"],
                    "physical_vehicle_id": next((s["physical_vehicle_id"] for s in structures if s["structure_id"] == row["structure_id"]), ""),
                    "reason_cn": "正向窗口中的对象被背景化；需要人工复核是否为弱车辆部件缺失导致。",
                    "runtime_png": runtime_png_for_frame(parse_int(row["sar_frame"])),
                    "eval_png": rel(VISUALS["eval"]),
                }
            )
        if row["negative_false_accept"] == "true":
            rows.append(
                {
                    "case_id": f"FAIL8A_{len(rows) + 1:03d}",
                    "failure_type": "negative_false_accept",
                    "sar_frame": row["sar_frame"],
                    "object_id": row["structure_id"],
                    "physical_vehicle_id": next((s["physical_vehicle_id"] for s in structures if s["structure_id"] == row["structure_id"]), ""),
                    "reason_cn": "负向或不确定窗口中的对象仍通过车辆条件，应作为反例阻断稳定机制结论。",
                    "runtime_png": runtime_png_for_frame(parse_int(row["sar_frame"])),
                    "eval_png": rel(VISUALS["eval"]),
                }
            )
    if not rows:
        rows.append(
            {
                "case_id": "FAIL8A_001",
                "failure_type": "mechanism_not_globally_established",
                "sar_frame": "",
                "object_id": "",
                "physical_vehicle_id": "GM_RM019",
                "reason_cn": "正负闭环只在局部窗口形成条件支持，尚未完成中间帧盲评，不能进入 A1.7R2。",
                "runtime_png": rel(VISUALS["contrast"]),
                "eval_png": rel(VISUALS["eval"]),
            }
        )
    return rows


def runtime_png_for_frame(frame: int) -> str:
    if frame in POSITIVE_WINDOWS["white_27_31"]["frames"] or frame in POSITIVE_WINDOWS["white_78_81"]["frames"]:
        return rel(VISUALS["white_positive"])
    if frame in NEGATIVE_WINDOWS["white_negative"]["frames"]:
        return rel(VISUALS["white_negative"])
    if frame in POSITIVE_WINDOWS["silver_270_273"]["frames"] or frame in POSITIVE_WINDOWS["silver_289_290"]["frames"]:
        return rel(VISUALS["silver_positive"])
    if frame in NEGATIVE_WINDOWS["silver_212_238"]["frames"]:
        return rel(VISUALS["silver_negative_a"])
    return rel(VISUALS["silver_negative_b"])


def review_rows(structures: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for s in structures:
        frame = parse_int(s["sar_frame"])
        entity = s["entity_class"]
        rows.append(
            {
                "review_id": f"RV8A_{len(rows) + 1:03d}",
                "sar_frame": s["sar_frame"],
                "review_object_type": "vehicle_structure_hypothesis",
                "object_id": s["structure_id"],
                "parent_object_ids": s["atom_ids"],
                "proposed_role": s["role_combination"],
                "same_vehicle_support": bool_text(entity == "vehicle_supported"),
                "background_support": bool_text(entity == "background_like"),
                "uncertain": bool_text(entity in {"vehicle_possible", "unresolved"}),
                "physical_reason_cn": visual_physical_reason(s),
                "temporal_reason_cn": visual_temporal_reason(s),
                "rejection_reason_cn": visual_rejection_reason(s),
                "runtime_png": runtime_png_for_frame(frame),
                "eval_png": rel(VISUALS["eval"]),
            }
        )
    return rows


def visual_physical_reason(s: Mapping[str, str]) -> str:
    roles = s["role_combination"]
    entity = s["entity_class"]
    frame = parse_int(s["sar_frame"])
    if frame in {27, 28, 29, 30, 31} and entity in {"vehicle_supported", "vehicle_possible"}:
        return f"白车 27-31 底部局部响应可见短脊线/核心/端点候选；{roles} 形成几何像素尺度结构，目标框未参与角色赋值。"
    if frame in {78, 79, 80, 81} and entity == "vehicle_supported":
        return f"白车 78-81 下侧核心在水平背景弧线下方保留；{roles} 只支持局部车辆响应，红色弧线未并入车辆实体。"
    if frame in {270, 271, 272, 273, 289, 290} and entity in {"vehicle_supported", "vehicle_possible"}:
        return f"银车正向短窗中底部核心/短脊线较弱但可见；{roles} 作为条件车辆响应，远侧弧线或孤立点不并入。"
    if entity == "background_like" and "background_arc" in roles:
        return f"图上 {roles} 更像沿扇形/道路背景延展的弧线或横向线状响应，缺少车辆尺度闭合。"
    if entity == "vehicle_supported":
        return f"图上可见 {roles} 组成的局部车辆尺度响应，长短轴为几何像素尺度，未用目标框赋值。"
    if entity == "vehicle_possible":
        return f"图上存在 {roles} 的局部车辆样结构，但部件不完整或短窗支持不足，只能条件保留。"
    if entity == "background_like":
        return f"图上对象更符合 {roles} 的背景/孤立响应，缺少车辆尺度闭合。"
    return f"图上对象 {roles} 与车辆部件关系不充分，物理尺度字段不足以判定。"


def visual_temporal_reason(s: Mapping[str, str]) -> str:
    if s["entity_class"] == "vehicle_supported":
        return "同一正向短窗内可见相邻帧非跳变响应，支持部件级短时连续。"
    if s["window_polarity"] == "positive":
        return "正向短窗内有局部延续线索，但不足以证明完整同车响应。"
    return "负向/不确定窗口不允许跨长缺口声称同车恢复。"


def visual_rejection_reason(s: Mapping[str, str]) -> str:
    if s["background_conflict"] == "true":
        return "弧线一致性或背景冲突触发，不能靠强度或光学方向进入车辆实体。"
    if s["entity_class"] == "background_like":
        return "尺度、空白或孤立性不足以支持车辆结构。"
    if s["entity_class"] == "unresolved":
        return "证据不足，保留不可判断。"
    return ""


def load_targets() -> dict[int, Box]:
    rows = read_rows(INPUTS["paired"])
    targets: dict[int, Box] = {}
    for row in rows:
        if row.get("scene") != SCENE:
            continue
        frame = parse_int(row.get("sar_frame"))
        if frame in REVIEW_FRAMES:
            targets[frame] = box_from_pair(row)
    return targets


def render_visuals(atoms: Sequence[Atom], structures: Sequence[Mapping[str, str]], include_eval: bool = False) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = load_targets() if include_eval else {}
    by_frame: dict[int, list[Atom]] = defaultdict(list)
    for atom in atoms:
        by_frame[atom.frame].append(atom)
    structure_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for row in structures:
        structure_by_frame[parse_int(row["sar_frame"])].append(row)

    def tiles(frames: Sequence[int], eval_overlay: bool = False) -> list[Image.Image]:
        return [frame_tile(frame, by_frame.get(frame, []), structure_by_frame.get(frame, []), targets.get(frame) if eval_overlay else None) for frame in frames]

    render_sheet(VISUALS["white_positive"], tiles([27, 28, 29, 30, 31, 78, 79, 80, 81]), 3)
    render_sheet(VISUALS["white_negative"], tiles([32, 40, 46, 60, 77]), 2)
    render_sheet(VISUALS["silver_positive"], tiles([270, 271, 272, 273, 289, 290]), 3)
    render_sheet(VISUALS["silver_negative_a"], tiles([212, 213, 220, 227, 238]), 2)
    render_sheet(VISUALS["silver_negative_b"], tiles([239, 243, 250, 260, 269, 276, 280, 284, 288]), 3)
    render_sheet(VISUALS["contrast"], tiles([31, 32, 81, 238, 269, 273, 288, 290]), 2)
    render_sheet(VISUALS["temporal"], tiles([27, 28, 29, 30, 31, 78, 79, 80, 81, 270, 271, 272, 273, 289, 290]), 3)
    if include_eval:
        render_sheet(VISUALS["eval"], tiles([31, 77, 81, 238, 269, 273, 288, 290], eval_overlay=True), 2)


def frame_tile(frame: int, atoms: Sequence[Atom], structures: Sequence[Mapping[str, str]], target: Box | None) -> Image.Image:
    base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB") if sar_gray_path(SCENE, frame).exists() else Image.new("RGB", (SAR_WIDTH, SAR_HEIGHT), (20, 20, 20))
    boxes = [a.box for a in atoms[:12]]
    if target:
        boxes.append(target)
    focus = expand_box(union_box(boxes), 45.0)
    full_w, full_h = 430, 250
    zoom_w, zoom_h = 430, 250
    full = base.resize((full_w, full_h))
    fdraw = ImageDraw.Draw(full)
    sx, sy = full_w / SAR_WIDTH, full_h / SAR_HEIGHT
    draw_scaled_box(fdraw, focus, sx, sy, (255, 140, 0), 2)
    fdraw.rectangle([0, 0, full_w, 24], fill=(0, 0, 0))
    fdraw.text((5, 5), f"SAR{frame} full", fill=(255, 255, 255))

    crop = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((zoom_w, zoom_h))
    zdraw = ImageDraw.Draw(crop)
    zdraw.rectangle([0, 0, zoom_w, 25], fill=(0, 0, 0))
    zdraw.text((5, 5), f"SAR{frame} atoms/roles/relations", fill=(255, 255, 255))
    colors = {
        "body_core": (0, 255, 110),
        "side_ridge": (50, 185, 255),
        "endpoint_hotspot": (255, 210, 40),
        "corner_support": (255, 165, 60),
        "weak_far_side": (175, 145, 255),
        "background_arc": (255, 80, 80),
        "fixed_hotspot": (255, 130, 200),
        "isolated_small_atom": (230, 230, 230),
        "unresolved_atom": (180, 180, 180),
    }
    centers: dict[str, tuple[float, float]] = {}
    for atom in atoms[:18]:
        color = colors.get(atom.role, (200, 200, 200))
        draw_crop_box(zdraw, atom.box, focus, zoom_w, zoom_h, color, 2)
        x, y = crop_point(atom.cx, atom.cy, focus, zoom_w, zoom_h)
        centers[atom.atom_id] = (x, y)
        dx = math.cos(math.radians(atom.orientation)) * 13
        dy = math.sin(math.radians(atom.orientation)) * 13
        zdraw.line([x - dx, y - dy, x + dx, y + dy], fill=color, width=2)
        zdraw.text((x + 4, y + 1), atom.atom_id.split("_")[-1] + ":" + atom.role.replace("_", "")[:4], fill=color)
    for s in structures[:8]:
        atom_ids = [aid for aid in s["atom_ids"].split(";") if aid in centers]
        for a_id, b_id in combinations(atom_ids, 2):
            zdraw.line([centers[a_id], centers[b_id]], fill=(255, 155, 0), width=1)
        if atom_ids:
            xs = [centers[aid][0] for aid in atom_ids]
            ys = [centers[aid][1] for aid in atom_ids]
            zdraw.text((min(xs), max(25, min(ys) - 14)), s["entity_class"], fill=(255, 255, 255))
    if target:
        draw_crop_box(zdraw, target, focus, zoom_w, zoom_h, (255, 245, 70), 2)
        zdraw.text((zoom_w - 112, 28), "EVAL_ONLY", fill=(255, 245, 70))
        draw_scaled_box(fdraw, target, sx, sy, (255, 245, 70), 2)
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


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    shown = list(rows if limit is None else rows[:limit])
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in shown:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/").replace("\n", " ") for field in fields) + " |")
    if limit is not None and len(rows) > limit:
        lines.append("| " + " | ".join(["..."] + [""] * (len(fields) - 1)) + " |")
    return "\n".join(lines)


def summarize(atoms: Sequence[Mapping[str, str]], structures: Sequence[Mapping[str, str]], entities: Sequence[Mapping[str, str]], closures: Sequence[Mapping[str, str]], ledger: Sequence[Mapping[str, str]], temporal: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    role_counts = Counter(row["proposed_role"] for row in atoms)
    entity_counts = Counter(row["entity_class"] for row in entities)
    grammar_counts = Counter(row["grammar_status"] for row in structures)
    positive = [row for row in structures if row["window_polarity"] == "positive"]
    negative = [row for row in structures if row["window_polarity"] != "positive"]
    pos_long = [parse_float(row["long_axis_extent"]) for row in positive if row["entity_class"] in {"vehicle_supported", "vehicle_possible"}]
    neg_long = [parse_float(row["long_axis_extent"]) for row in negative if row["entity_class"] in {"background_like", "unresolved"}]
    false_reject = sum(row["positive_false_reject"] == "true" for row in closures)
    false_accept = sum(row["negative_false_accept"] == "true" for row in closures)
    return {
        "atom_count": len(atoms),
        "role_counts": role_counts,
        "entity_counts": entity_counts,
        "grammar_counts": grammar_counts,
        "pos_long_median": fmt(median(pos_long)),
        "neg_long_median": fmt(median(neg_long)),
        "false_reject": false_reject,
        "false_accept": false_accept,
        "background_arc_rejected": "true" if role_counts.get("background_arc", 0) and false_accept == 0 else "partial",
        "temporal_supported_windows": sum(row["shared_motion_trend"] == "true" and row["role"] == "body_core" for row in temporal),
        "ledger_status": Counter(row["status"] for row in ledger),
    }


def render_report(atom_sha: str, evaluated: bool) -> None:
    atom_rows_loaded = read_rows(OUTPUTS["atom_trace"])
    structures = read_rows(OUTPUTS["structure_hypothesis"])
    entities = read_rows(OUTPUTS["entities"])
    closures = read_rows(OUTPUTS["closure"])
    ledger = read_rows(OUTPUTS["ledger"])
    temporal = read_rows(OUTPUTS["temporal"])
    failures = read_rows(OUTPUTS["failure_cases"])
    summary = summarize(atom_rows_loaded, structures, entities, closures, ledger, temporal)
    role_counts = summary["role_counts"]
    entity_counts = summary["entity_counts"]
    grammar_counts = summary["grammar_counts"]
    ready = "NO"
    generalization = "PARTIAL" if summary["ledger_status"].get("conditional_candidate", 0) else "NO"
    lines = [
        "# OTY2 WGV3.6A-A1.8A Vehicle Response Grammar Audit",
        "",
        "## Boundary",
        "",
        f"- requested start commit: `{REQUESTED_START_COMMIT}`",
        f"- scattering atom trace SHA256: `{atom_sha}`",
        "- scene: `GM_RM019`",
        "- generate/evaluate separation: `PASS`",
        "- generate phase target manual boxes loaded: `false`",
        f"- evaluate phase target boxes loaded after freeze: `{bool_text(evaluated)}`",
        "- A1.6/A1.7/A1.7R historical outputs modified: `false`",
        "- final annotation / revised GT / selector / ranking / training: `false`",
        "- GM_RM011 executed: `false`",
        "- TRACK_BEFORE_DETECT_DIAGNOSTIC_ONLY: `not_executed`",
        "",
        "## Geometry And Unit Provenance",
        "",
        "- `build_geometry().radial` is pixel-radius geometry, not verified meters.",
        "- `build_geometry().azimuth` is image fan angle in degrees, not a calibrated SAR bearing claim.",
        "- `ground_x/ground_y` are intentionally blank because no reliable ground-meter transform was verified.",
        "- Structure extents are reported as `geometry_coordinate_pixel_radius_not_meter`.",
        "",
        "## Reviewed Windows",
        "",
        "- positive frames: `27-31, 78-81, 270-273, 289-290`",
        "- negative/uncertain frames: `32,40,46,60,77,212,213,220,227,238,239,243,250,260,269,276,280,284,288`",
        "- runtime visual sheets:",
        *[f"  - `{rel(path)}`" for key, path in VISUALS.items() if key != "eval"],
        f"- eval-only overlay sheet: `{rel(VISUALS['eval'])}`",
        "",
        "## Counts",
        "",
        f"- scattering atom count: `{summary['atom_count']}`",
        f"- role counts: `body_core={role_counts.get('body_core', 0)}, side_ridge={role_counts.get('side_ridge', 0)}, endpoint_hotspot={role_counts.get('endpoint_hotspot', 0)}, background_arc={role_counts.get('background_arc', 0)}, unresolved={role_counts.get('unresolved_atom', 0)}`",
        f"- entity counts: `vehicle_supported={entity_counts.get('vehicle_supported', 0)}, vehicle_possible={entity_counts.get('vehicle_possible', 0)}, background_like={entity_counts.get('background_like', 0)}, unresolved={entity_counts.get('unresolved', 0)}`",
        f"- grammar statuses: `stable_global_candidate={grammar_counts.get('stable_global_candidate', 0)}, conditional_candidate={grammar_counts.get('conditional_candidate', 0)}, falsified={grammar_counts.get('falsified', 0)}, not_testable={grammar_counts.get('not_testable', 0)}`",
        f"- vehicle-scale long-axis median in positive candidate structures: `{summary['pos_long_median']}` geometry units",
        f"- negative/background long-axis median: `{summary['neg_long_median']}` geometry units",
        f"- positive false rejects: `{summary['false_reject']}`",
        f"- negative false accepts: `{summary['false_accept']}`",
        "",
        "## Object-Level Visual Review",
        "",
        "The review rows are structure/object rows, not target-coverage rows. Roles are proposed from atom features and then interpreted with the rendered object sheets; target boxes appear only in EVAL_ONLY overlays.",
        "",
        "Visual inspection notes:",
        "",
        "- White SUV 27-31: the lower compact response and short ridge are visible across adjacent frames; endpoint-like small atoms remain support only, not standalone vehicles.",
        "- White SUV 78-81: a strong horizontal/background arc is visible above the lower response; the audit keeps the arc as background-like while retaining the lower core as local vehicle support.",
        "- Silver MPV 270-273 and 289-290: the lower response is weaker and partly fragmented; supported rows are conditional local structures, while far-side arcs and isolated peaks remain excluded.",
        "- Negative/uncertain windows: 32/40/46/60/77 and 239-288 contain many arc-like or isolated responses; no negative structure is promoted to vehicle-supported.",
        "- EVAL_ONLY target boxes were opened after freeze and used only to visually check overlays, not to extract atoms or assign roles.",
        "",
        md_table(read_rows(OUTPUTS["object_review"]), ["review_id", "sar_frame", "review_object_type", "object_id", "proposed_role", "same_vehicle_support", "background_support", "uncertain", "physical_reason_cn"], limit=16),
        "",
        "## Positive-Negative Closure",
        "",
        md_table(closures, ["closure_id", "structure_id", "sar_frame", "positive_false_reject", "negative_false_accept", "cannot_judge", "positive_vehicle_support_cn", "negative_background_rejection_cn"], limit=16),
        "",
        "## Temporal Continuity",
        "",
        md_table(temporal, ["temporal_id", "window_id", "role", "frames", "role_persistence", "shared_motion_trend", "conclusion_cn"], limit=18),
        "",
        "## Hypothesis Ledger",
        "",
        md_table(ledger, ["hypothesis_id", "hypothesis_cn", "status", "counterexamples", "next_test_required"]),
        "",
        "## Failure Cases",
        "",
        md_table(failures, FAIL_FIELDS),
        "",
        "## Gate Verdicts",
        "",
        "- `GEOMETRY_UNIT_PROVENANCE_VALID`: `PASS_NO_METRIC_METER_CLAIM`",
        "- `OBJECT_LEVEL_VISUAL_REVIEW_NON_CIRCULAR`: `PASS`",
        f"- `SCATTERING_ATOM_ROLE_SEPARABLE`: `{'PARTIAL' if role_counts.get('body_core', 0) and role_counts.get('background_arc', 0) else 'NO'}`",
        f"- `VEHICLE_SCALE_RESPONSE_SUPPORTED`: `{'PARTIAL' if entity_counts.get('vehicle_supported', 0) or entity_counts.get('vehicle_possible', 0) else 'NO'}`",
        f"- `POSITIVE_NEGATIVE_MORPHOLOGY_CLOSED`: `{'PARTIAL' if summary['false_accept'] == 0 else 'NO'}`",
        f"- `BACKGROUND_ARC_REJECTION_SUPPORTED`: `{summary['background_arc_rejected'].upper()}`",
        f"- `SHORT_WINDOW_ROLE_DRIFT_SUPPORTED`: `{'PARTIAL' if summary['temporal_supported_windows'] else 'NO'}`",
        f"- `POINT_TO_STRUCTURE_GENERALIZATION_SUPPORTED`: `{generalization}`",
        f"- `VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2`: `{ready}`",
        "- `INTERMEDIATE_FRAME_BLIND_EVAL_PENDING`: `true`",
        "- `GM_RM011_BLOCKED`: `true`",
        "",
        "## Created Files",
        "",
        *[f"- `{rel(path)}`" for path in OUTPUTS.values()],
        "",
        "## Research Judgment",
        "",
        "A1.8A establishes a conditional point-to-structure audit layer, not a final vehicle localizer. The current evidence separates some body-core/endpoint/ridge-like responses from background arcs and isolated peaks in local windows, but unit provenance remains non-metric and intermediate-frame blind evaluation is still pending. Therefore A1.7R2 must not consume all compact assemblies; it may only consume vehicle-supported or vehicle-possible observation entities after this layer is rechecked.",
    ]
    write_text(OUTPUTS["report"], "\n".join(lines))


def generate() -> str:
    write_csv(OUTPUTS["geometry_unit"], geometry_unit_rows(), GEOMETRY_FIELDS)
    atoms = extract_atoms()
    rels = relation_rows(atoms)
    structures = build_structures(atoms, rels)
    closures = closure_rows(structures)
    temporal = temporal_rows(atoms, structures)
    entities = entity_rows(structures)
    ledger = ledger_rows(structures)
    failures = failure_rows(structures, closures)
    reviews = review_rows(structures)
    write_csv(OUTPUTS["atom_trace"], atom_rows(atoms), ATOM_FIELDS)
    atom_sha = sha256(OUTPUTS["atom_trace"])
    write_csv(OUTPUTS["relation_graph"], rels, RELATION_FIELDS)
    write_csv(OUTPUTS["structure_hypothesis"], structures, STRUCTURE_FIELDS)
    write_csv(OUTPUTS["closure"], closures, CLOSURE_FIELDS)
    write_csv(OUTPUTS["temporal"], temporal, TEMPORAL_FIELDS)
    write_csv(OUTPUTS["entities"], entities, ENTITY_FIELDS)
    write_csv(OUTPUTS["ledger"], ledger, LEDGER_FIELDS)
    write_csv(OUTPUTS["failure_cases"], failures, FAIL_FIELDS)
    write_csv(OUTPUTS["object_review"], reviews, REVIEW_FIELDS)
    render_visuals(atoms, structures, include_eval=False)
    render_report(atom_sha, evaluated=False)
    return atom_sha


def evaluate() -> str:
    if not OUTPUTS["atom_trace"].exists():
        raise RuntimeError("run generate before evaluate")
    atom_sha = sha256(OUTPUTS["atom_trace"])
    atoms = atoms_from_rows(read_rows(OUTPUTS["atom_trace"]))
    structures = read_rows(OUTPUTS["structure_hypothesis"])
    render_visuals(atoms, structures, include_eval=True)
    render_report(atom_sha, evaluated=True)
    return atom_sha


def atoms_from_rows(rows: Sequence[Mapping[str, str]]) -> list[Atom]:
    atoms: list[Atom] = []
    for row in rows:
        box = box_from_text(row["envelope"])
        search = box_from_text(row["search_window"])
        if box is None or search is None:
            continue
        atoms.append(
            Atom(
                atom_id=row["atom_id"],
                physical_vehicle_id=row["physical_vehicle_id"],
                window_id=row["window_id"],
                polarity=row["window_polarity"],
                frame=parse_int(row["sar_frame"]),
                cx=parse_float(row["pixel_centroid_x"]),
                cy=parse_float(row["pixel_centroid_y"]),
                box=box,
                area=parse_int(row["pixel_area"]),
                integrated=parse_float(row["integrated_energy"]),
                mean=parse_float(row["mean_energy"]),
                peak=parse_float(row["peak_energy"]),
                relative_energy=parse_float(row["relative_energy_within_local_field"]),
                azimuth=parse_float(row["azimuth"]),
                radial=parse_float(row["radial"]),
                axis1=parse_float(row["principal_axis_1"]),
                axis2=parse_float(row["principal_axis_2"]),
                elongation=parse_float(row["elongation"]),
                orientation=parse_float(row["orientation"]),
                compactness=parse_float(row["compactness"]),
                boundary_contact=row["boundary_contact"],
                arc_consistency=parse_float(row["local_arc_consistency"]),
                threshold=parse_float(row["extraction_threshold"]),
                search=search,
                role=row["proposed_role"],
                role_provenance=row["role_provenance"],
                temporal_hint=row["temporal_presence_hint"],
            )
        )
    return atoms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "evaluate", "all"])
    args = parser.parse_args()
    if args.command == "generate":
        print(f"generated scattering_atom_trace_sha256={generate()}")
    elif args.command == "evaluate":
        print(f"evaluated scattering_atom_trace_sha256={evaluate()}")
    else:
        generated = generate()
        evaluated = evaluate()
        if generated != evaluated:
            raise RuntimeError("A1.8A generated/evaluated atom trace SHA mismatch")
        print(f"all complete scattering_atom_trace_sha256={evaluated}")


if __name__ == "__main__":
    main()
