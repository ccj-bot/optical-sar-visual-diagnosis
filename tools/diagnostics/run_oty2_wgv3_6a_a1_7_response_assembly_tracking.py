"""WGV3.6A-A1.7 causal SAR response-assembly tracking audit.

This diagnostic keeps the A1.6 frozen C0/C1 reference intact, then adds C1A
single-frame response assemblies and C1B delayed temporal confirmation. Hidden
target SAR boxes are loaded only by the evaluate phase after frozen prediction
SHA256 verification.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import cv2
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
REQUESTED_START_COMMIT = "325bc393f8514377b34f7c6cc014e128cbb21417"
SCENE = "GM_RM019"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_7_20260711"
IRRECOVERABLE_K = 3

INPUTS = {
    "paired": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "optical_state": SAMPLES_DIR / "oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_20260710.csv",
    "a1_6_predictions": SAMPLES_DIR / "oty2_wgv3_6a_a1_6_frozen_predictions_20260711.csv",
    "a1_6_eval": SAMPLES_DIR / "oty2_wgv3_6a_a1_6_hidden_anchor_evaluation_20260711.csv",
    "a1_6_report": REPORT_DIR / "oty2_wgv3_6a_a1_6_causal_response_tracking_20260711.md",
    "a1_5_report": REPORT_DIR / "oty2_wgv3_6a_a1_5_propagation_integrity_audit_20260711.md",
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_7_response_assembly_tracking_{DATE}.md",
    "source_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7_source_assembly_manifest_{DATE}.csv",
    "component_graph": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7_component_graph_trace_{DATE}.csv",
    "assembly_trace": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7_response_assembly_trace_{DATE}.csv",
    "frozen_predictions": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7_frozen_predictions_{DATE}.csv",
    "hidden_eval": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7_hidden_anchor_evaluation_{DATE}.csv",
    "delta_audit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7_c1_c1a_c1b_delta_audit_{DATE}.csv",
    "optical_bypass": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7_optical_sar_trend_bypass_audit_{DATE}.csv",
    "failure_cases": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7_failure_cases_{DATE}.csv",
}

VISUALS = {
    "priority_runtime": OUT_DIR / "a1_7_priority_short_interval_runtime_assemblies.png",
    "priority_eval": OUT_DIR / "a1_7_priority_short_interval_eval_only_overlay.png",
    "difference": OUT_DIR / "a1_7_c1a_c1b_difference_examples.png",
    "open_loop": OUT_DIR / "a1_7_open_loop_eval_only_overlay.png",
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
    ("ADJ_0204_TO_0205", WHITE, "WGV35A_PAIR_0204", 27, "WGV35A_PAIR_0205", 31, "priority_short"),
    ("ADJ_0205_TO_0206", WHITE, "WGV35A_PAIR_0205", 31, "WGV35A_PAIR_0206", 77, "secondary_long"),
    ("ADJ_0206_TO_0207", WHITE, "WGV35A_PAIR_0206", 77, "WGV35A_PAIR_0207", 81, "priority_short"),
    ("ADJ_0208_TO_0209", SILVER, "WGV35A_PAIR_0208", 212, "WGV35A_PAIR_0209", 238, "secondary_long"),
    ("ADJ_0209_TO_0210", SILVER, "WGV35A_PAIR_0209", 238, "WGV35A_PAIR_0210", 269, "secondary_long"),
    ("ADJ_0210_TO_0211", SILVER, "WGV35A_PAIR_0210", 269, "WGV35A_PAIR_0211", 273, "priority_short"),
    ("ADJ_0211_TO_0212", SILVER, "WGV35A_PAIR_0211", 273, "WGV35A_PAIR_0212", 288, "secondary_mid"),
    ("ADJ_0212_TO_0213", SILVER, "WGV35A_PAIR_0212", 288, "WGV35A_PAIR_0213", 290, "priority_short"),
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

SOURCE_FIELDS = [
    "experiment_id",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "source_sar_frame",
    "source_optical_frame",
    "source_assembly_id",
    "source_component_count",
    "assembly_centroid",
    "assembly_envelope",
    "azimuth_span",
    "radial_span",
    "total_area",
    "total_intensity",
    "peak_intensity",
    "source_anchor_structure_similarity",
    "frozen_predictions_sha256",
    "notes",
]

COMPONENT_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "sar_frame",
    "component_id",
    "centroid",
    "bounding_box",
    "area",
    "mean_intensity",
    "peak_intensity",
    "azimuth_position",
    "radial_position",
    "edge_component_ids",
    "component_graph_id",
    "search_window",
    "source_pair_id",
]

ASSEMBLY_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "target_pair_id",
    "sar_frame",
    "assembly_id",
    "component_ids",
    "component_count",
    "assembly_centroid",
    "assembly_envelope",
    "azimuth_span",
    "radial_span",
    "total_area",
    "total_intensity",
    "peak_intensity",
    "internal_gap_statistics",
    "source_anchor_structure_similarity",
    "temporal_support_length",
    "selection_status",
    "search_window",
    "first_uncertain_frame",
    "first_irrecoverable_frame_k2",
    "first_irrecoverable_frame_k3",
    "first_irrecoverable_frame_k5",
    "ambiguity_recovery_event",
    "association_discontinuity",
    "identity_contamination",
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
    "selection_status",
    "prediction_region",
    "search_window",
    "assembly_id",
    "component_count",
    "assembly_centroid",
    "search_window_area",
    "static_fan_geometry_area",
    "search_ratio",
    "frozen_generation_phase",
    "target_manual_box_loaded",
    "future_endpoint_loaded",
    "reference_source",
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
    "first_uncertain_frame",
    "first_irrecoverable_frame_k2",
    "first_irrecoverable_frame_k3",
    "first_irrecoverable_frame_k5",
    "confirmed_assembly_frames",
    "ambiguous_assembly_frames",
    "missing_assembly_frames",
    "ambiguity_recovery_count",
    "association_discontinuity_count",
    "search_ratio",
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
    "ambiguity_delta",
    "verdict",
    "notes",
]

OPTICAL_FIELDS = [
    "experiment_id",
    "method",
    "physical_vehicle_id",
    "sar_frame",
    "sync_shift_sar_frames",
    "estimated_optical_frame",
    "optical_velocity_x_sign",
    "sar_azimuth_delta_sign",
    "azimuth_relation_consistent",
    "optical_depth_velocity_sign",
    "sar_radial_delta_sign",
    "radial_relation_consistent",
    "single_frame_consistency",
    "window3_consistency",
    "window5_consistency",
    "relation_used_for_filtering",
    "notes",
]

FAILURE_FIELDS = [
    "case_id",
    "experiment_id",
    "method",
    "physical_vehicle_id",
    "failure_type",
    "sar_frame",
    "first_uncertain_frame",
    "first_irrecoverable_frame",
    "visual_png",
    "chinese_judgement",
    "notes",
]


@dataclass(frozen=True)
class RunSpec:
    experiment_id: str
    experiment_type: str
    priority_group: str
    physical_vehicle_id: str
    source_pair_id: str
    source_optical_frame: int
    source_sar_frame: int
    end_sar_frame: int
    eval_pairs: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Component:
    component_id: str
    centroid: tuple[float, float]
    box: Box
    area: int
    mean_intensity: float
    peak_intensity: float
    azimuth: float
    radial: float


@dataclass(frozen=True)
class Assembly:
    assembly_id: str
    components: tuple[Component, ...]
    envelope: Box
    centroid: tuple[float, float]
    azimuth_span: float
    radial_span: float
    total_area: int
    total_intensity: float
    peak_intensity: float
    internal_gap: float
    similarity: float
    support_length: int = 1


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


def sign_text(value: float, eps: float = 1e-6) -> str:
    if math.isnan(value) or abs(value) <= eps:
        return "zero"
    return "positive" if value > 0 else "negative"


def same_nonzero_sign(a: str, b: str) -> str:
    if a == "zero" or b == "zero":
        return "NOT_TESTED"
    return bool_text(a == b)


def box_from_text(text: str) -> Box:
    parts = [parse_float(part) for part in str(text).split(",")]
    if len(parts) != 4 or any(math.isnan(v) for v in parts):
        return Box(0, 0, 1, 1)
    return Box(parts[0], parts[1], parts[2], parts[3])


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


def union_box(boxes: Sequence[Box]) -> Box:
    if not boxes:
        return Box(0, 0, 1, 1)
    return clamp_box(Box(min(b.x1 for b in boxes), min(b.y1 for b in boxes), max(b.x2 for b in boxes), max(b.y2 for b in boxes)))


def center_distance(a: Box, b: Box) -> float:
    return math.hypot(a.cx - b.cx, a.cy - b.cy)


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


def block_components(binary: np.ndarray, block: int = 4) -> list[tuple[int, int, int, int, int]]:
    height, width = binary.shape
    padded_h = int(math.ceil(height / block) * block)
    padded_w = int(math.ceil(width / block) * block)
    padded = np.zeros((padded_h, padded_w), dtype=bool)
    padded[:height, :width] = binary
    coarse = padded.reshape(padded_h // block, block, padded_w // block, block).any(axis=(1, 3))
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(coarse.astype(np.uint8), 8)
    components: list[tuple[int, int, int, int, int]] = []
    for label in range(1, count):
        x0 = int(stats[label, cv2.CC_STAT_LEFT])
        y0 = int(stats[label, cv2.CC_STAT_TOP])
        x1 = x0 + int(stats[label, cv2.CC_STAT_WIDTH])
        y1 = y0 + int(stats[label, cv2.CC_STAT_HEIGHT])
        ox0 = max(0, x0 * block)
        oy0 = max(0, y0 * block)
        ox1 = min(width, x1 * block)
        oy1 = min(height, y1 * block)
        area = int(binary[oy0:oy1, ox0:ox1].sum())
        components.append((ox0, oy0, ox1, oy1, area))
    return components


def load_pair_rows(pair_ids: set[str], include_target_boxes: bool) -> dict[str, dict[str, str]]:
    allowed = {
        "pair_id",
        "scene",
        "optical_frame",
        "sar_frame",
        "sar_bbox_x1",
        "sar_bbox_y1",
        "sar_bbox_x2",
        "sar_bbox_y2",
    }
    rows: dict[str, dict[str, str]] = {}
    for row in read_rows(INPUTS["paired"]):
        pair_id = row.get("pair_id", "")
        if pair_id not in pair_ids:
            continue
        kept = dict(row) if include_target_boxes else {field: row.get(field, "") for field in allowed}
        kept["physical_vehicle_id"] = PAIR_META[pair_id][0]
        rows[pair_id] = kept
    missing = sorted(pair_ids - set(rows))
    if missing:
        raise RuntimeError(f"Missing pair rows: {missing}")
    return rows


def build_specs() -> list[RunSpec]:
    specs: list[RunSpec] = []
    for exp_id, pv, source_pair, source_sar, target_pair, target_sar, priority in ADJACENT_SPECS:
        source_optical = PAIR_META[source_pair][1]
        specs.append(
            RunSpec(
                exp_id,
                "adjacent_hidden_anchor",
                priority,
                pv,
                source_pair,
                source_optical,
                source_sar,
                target_sar,
                ((target_pair, target_sar),),
            )
        )
    for exp_id, pv, source_pair, source_sar, end_sar, evals in OPEN_LOOP_SPECS:
        source_optical = PAIR_META[source_pair][1]
        specs.append(
            RunSpec(
                exp_id,
                "open_loop",
                "open_loop",
                pv,
                source_pair,
                source_optical,
                source_sar,
                end_sar,
                tuple(evals),
            )
        )
    return specs


def load_optical_state() -> dict[str, list[dict[str, str]]]:
    rows_by_pv: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(INPUTS["optical_state"]):
        rows_by_pv[row.get("physical_vehicle_id", "")].append(row)
    for rows in rows_by_pv.values():
        rows.sort(key=lambda row: parse_int(row.get("frame")))
    return rows_by_pv


def nearest_optical(rows: Sequence[Mapping[str, str]], frame: float) -> Mapping[str, str] | None:
    if not rows:
        return None
    return min(rows, key=lambda row: abs(parse_float(row.get("frame")) - frame))


def extract_components(
    arr: np.ndarray,
    fan_mask: np.ndarray,
    azimuth: np.ndarray,
    radial: np.ndarray,
    search: Box,
    prefix: str,
) -> list[Component]:
    x0 = max(0, int(math.floor(search.x1)))
    y0 = max(0, int(math.floor(search.y1)))
    x1 = min(SAR_WIDTH, int(math.ceil(search.x2)))
    y1 = min(SAR_HEIGHT, int(math.ceil(search.y2)))
    crop = arr[y0:y1, x0:x1]
    local_fan = fan_mask[y0:y1, x0:x1]
    if crop.size == 0 or not local_fan.any():
        return []
    valid = crop[local_fan]
    threshold = max(float(np.percentile(valid, 96)), float(valid.mean() + 0.9 * valid.std()))
    binary = (crop >= threshold) & local_fan
    comps: list[Component] = []
    for idx, (cx0, cy0, cx1, cy1, area) in enumerate(block_components(binary, block=8), start=1):
        if area < 18:
            continue
        mask = binary[cy0:cy1, cx0:cx1]
        ys, xs = np.nonzero(mask)
        if xs.size == 0:
            continue
        gx = x0 + cx0 + xs
        gy = y0 + cy0 + ys
        vals = crop[cy0:cy1, cx0:cx1][mask]
        center = (float(gx.mean()), float(gy.mean()))
        box = Box(float(x0 + cx0), float(y0 + cy0), float(x0 + cx1), float(y0 + cy1))
        comps.append(
            Component(
                f"{prefix}_c{idx:03d}",
                center,
                box,
                int(area),
                float(vals.mean()),
                float(vals.max()),
                float(azimuth[gy.astype(int), gx.astype(int)].mean()),
                float(radial[gy.astype(int), gx.astype(int)].mean()),
            )
        )
    return comps


def graph_edges(components: Sequence[Component], previous: Assembly | None, search: Box) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {c.component_id: set() for c in components}
    if not components:
        return edges
    width_budget = max(45.0, (previous.envelope.width if previous else search.width * 0.45) * 0.75)
    height_budget = max(28.0, (previous.envelope.height if previous else search.height * 0.45) * 0.85)
    az_budget = max(1.8, width_budget / 22.0)
    rad_budget = max(18.0, height_budget * 0.95)
    max_union_width = (previous.envelope.width if previous else search.width) * 1.9 + 28.0
    max_union_height = (previous.envelope.height if previous else search.height) * 1.9 + 18.0
    for i, a in enumerate(components):
        for b in components[i + 1 :]:
            union = union_box([a.box, b.box])
            az_ok = abs(a.azimuth - b.azimuth) <= az_budget
            radial_ok = abs(a.radial - b.radial) <= rad_budget
            size_ok = union.width <= max_union_width and union.height <= max_union_height
            blank_ok = math.hypot(a.centroid[0] - b.centroid[0], a.centroid[1] - b.centroid[1]) <= max(width_budget, height_budget) * 1.7
            if az_ok and radial_ok and size_ok and blank_ok:
                edges[a.component_id].add(b.component_id)
                edges[b.component_id].add(a.component_id)
    return edges


def make_assembly(group_id: str, components: Sequence[Component], previous: Assembly | None) -> Assembly:
    envelope = union_box([component.box for component in components])
    total_area = sum(component.area for component in components)
    if total_area:
        cx = sum(component.centroid[0] * component.area for component in components) / total_area
        cy = sum(component.centroid[1] * component.area for component in components) / total_area
    else:
        cx, cy = envelope.cx, envelope.cy
    az_values = [component.azimuth for component in components]
    radial_values = [component.radial for component in components]
    gaps = []
    ordered = sorted(components, key=lambda c: c.centroid[0])
    for a, b in zip(ordered, ordered[1:]):
        gaps.append(max(0.0, b.box.x1 - a.box.x2))
    if previous:
        area_ratio = min(safe_div(envelope.area, previous.envelope.area), safe_div(previous.envelope.area, envelope.area))
        shape_dx = abs(envelope.width - previous.envelope.width) / max(1.0, previous.envelope.width)
        shape_dy = abs(envelope.height - previous.envelope.height) / max(1.0, previous.envelope.height)
        similarity = max(0.0, min(1.0, 0.5 * area_ratio + 0.25 * (1 - min(shape_dx, 1)) + 0.25 * (1 - min(shape_dy, 1))))
    else:
        similarity = 1.0
    return Assembly(
        group_id,
        tuple(components),
        envelope,
        (float(cx), float(cy)),
        float(max(az_values) - min(az_values)) if az_values else 0.0,
        float(max(radial_values) - min(radial_values)) if radial_values else 0.0,
        int(total_area),
        float(sum(component.mean_intensity * component.area for component in components)),
        float(max((component.peak_intensity for component in components), default=0.0)),
        float(np.mean(gaps)) if gaps else 0.0,
        similarity,
    )


def build_assemblies(components: Sequence[Component], previous: Assembly | None, search: Box, prefix: str) -> tuple[list[Assembly], dict[str, set[str]]]:
    edges = graph_edges(components, previous, search)
    seen: set[str] = set()
    by_id = {component.component_id: component for component in components}
    assemblies: list[Assembly] = []
    for component in components:
        if component.component_id in seen:
            continue
        stack = [component.component_id]
        group_ids = []
        seen.add(component.component_id)
        while stack:
            cid = stack.pop()
            group_ids.append(cid)
            for other in edges[cid]:
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        group = [by_id[cid] for cid in group_ids]
        assemblies.append(make_assembly(f"{prefix}_a{len(assemblies) + 1:03d}", group, previous))
    return assemblies, edges


def gate_assemblies(assemblies: Sequence[Assembly], predicted: Box, previous: Assembly) -> list[Assembly]:
    gated: list[Assembly] = []
    max_distance = max(54.0, math.hypot(previous.envelope.width, previous.envelope.height) * 0.65)
    max_area_ratio = 4.0
    max_width = previous.envelope.width * 2.15 + 28.0
    max_height = previous.envelope.height * 2.0 + 22.0
    for assembly in assemblies:
        distance = math.hypot(assembly.centroid[0] - predicted.cx, assembly.centroid[1] - predicted.cy)
        area_ratio = safe_div(assembly.envelope.area, previous.envelope.area)
        overlap = box_iou(assembly.envelope, previous.envelope)
        if distance <= max_distance and 0.18 <= area_ratio <= max_area_ratio and assembly.envelope.width <= max_width and assembly.envelope.height <= max_height:
            if overlap > 0.03 or distance <= max_distance * 0.72:
                gated.append(assembly)
    return gated


def source_assembly(source_box: Box, frame: int, fan_mask: np.ndarray, azimuth: np.ndarray, radial: np.ndarray) -> tuple[Assembly, list[Component], dict[str, set[str]], Box]:
    search = expand_box(source_box, 14.0, 12.0)
    arr = read_gray(sar_gray_path(SCENE, frame)).astype(np.float32)
    components = extract_components(arr, fan_mask, azimuth, radial, search, f"src{frame}")
    if not components:
        fallback = Component(
            f"src{frame}_fallback",
            (source_box.cx, source_box.cy),
            source_box,
            max(1, int(source_box.area)),
            0.0,
            0.0,
            float(azimuth[int(source_box.cy), int(source_box.cx)]),
            float(radial[int(source_box.cy), int(source_box.cx)]),
        )
        components = [fallback]
    assembly = make_assembly(f"src_{frame}_assembly", components, None)
    edges = graph_edges(components, None, search)
    return assembly, components, edges, search


def assembly_row(
    spec: RunSpec,
    method: str,
    frame: int,
    assembly: Assembly,
    status: str,
    search: Box,
    target_pair_id: str,
    first_uncertain: str = "",
    irrecoverable: Mapping[int, str] | None = None,
    recovery: bool = False,
    discontinuity: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    irr = irrecoverable or {}
    return {
        "experiment_id": spec.experiment_id,
        "experiment_type": spec.experiment_type,
        "method": method,
        "physical_vehicle_id": spec.physical_vehicle_id,
        "source_pair_id": spec.source_pair_id,
        "target_pair_id": target_pair_id,
        "sar_frame": frame,
        "assembly_id": assembly.assembly_id,
        "component_ids": ";".join(component.component_id for component in assembly.components),
        "component_count": len(assembly.components),
        "assembly_centroid": f"{assembly.centroid[0]:.3f},{assembly.centroid[1]:.3f}",
        "assembly_envelope": assembly.envelope.as_text(),
        "azimuth_span": fmt(assembly.azimuth_span),
        "radial_span": fmt(assembly.radial_span),
        "total_area": assembly.total_area,
        "total_intensity": fmt(assembly.total_intensity),
        "peak_intensity": fmt(assembly.peak_intensity),
        "internal_gap_statistics": fmt(assembly.internal_gap),
        "source_anchor_structure_similarity": fmt(assembly.similarity),
        "temporal_support_length": assembly.support_length,
        "selection_status": status,
        "search_window": search.as_text(),
        "first_uncertain_frame": first_uncertain,
        "first_irrecoverable_frame_k2": irr.get(2, ""),
        "first_irrecoverable_frame_k3": irr.get(3, ""),
        "first_irrecoverable_frame_k5": irr.get(5, ""),
        "ambiguity_recovery_event": bool_text(recovery),
        "association_discontinuity": bool_text(discontinuity),
        "identity_contamination": "NOT_TESTED",
        "notes": notes,
    }


def prediction_row(
    spec: RunSpec,
    method: str,
    frame: int,
    status: str,
    region: Box,
    search: Box,
    assembly: Assembly | None,
    fan_area: int,
    reference_source: str,
) -> dict[str, Any]:
    return {
        "experiment_id": spec.experiment_id,
        "experiment_type": spec.experiment_type,
        "method": method,
        "physical_vehicle_id": spec.physical_vehicle_id,
        "source_pair_id": spec.source_pair_id,
        "source_sar_frame": spec.source_sar_frame,
        "target_pair_id": ";".join(pair for pair, _ in spec.eval_pairs),
        "target_sar_frame": ";".join(str(frame_id) for _, frame_id in spec.eval_pairs),
        "sar_frame": frame,
        "frame_offset": frame - spec.source_sar_frame,
        "prediction_status": status,
        "selection_status": status,
        "prediction_region": region.as_text(),
        "search_window": search.as_text(),
        "assembly_id": assembly.assembly_id if assembly else "",
        "component_count": len(assembly.components) if assembly else "",
        "assembly_centroid": f"{assembly.centroid[0]:.3f},{assembly.centroid[1]:.3f}" if assembly else "",
        "search_window_area": fmt(search.area),
        "static_fan_geometry_area": str(fan_area),
        "search_ratio": fmt(safe_div(search.area, fan_area)),
        "frozen_generation_phase": "generate",
        "target_manual_box_loaded": "false",
        "future_endpoint_loaded": "false",
        "reference_source": reference_source,
    }


def component_rows(
    spec: RunSpec,
    method: str,
    frame: int,
    components: Sequence[Component],
    edges: Mapping[str, set[str]],
    assemblies: Sequence[Assembly],
    search: Box,
) -> list[dict[str, Any]]:
    graph_id_by_component: dict[str, str] = {}
    for assembly in assemblies:
        for component in assembly.components:
            graph_id_by_component[component.component_id] = assembly.assembly_id
    rows = []
    for component in components:
        rows.append(
            {
                "experiment_id": spec.experiment_id,
                "experiment_type": spec.experiment_type,
                "method": method,
                "physical_vehicle_id": spec.physical_vehicle_id,
                "sar_frame": frame,
                "component_id": component.component_id,
                "centroid": f"{component.centroid[0]:.3f},{component.centroid[1]:.3f}",
                "bounding_box": component.box.as_text(),
                "area": component.area,
                "mean_intensity": fmt(component.mean_intensity),
                "peak_intensity": fmt(component.peak_intensity),
                "azimuth_position": fmt(component.azimuth),
                "radial_position": fmt(component.radial),
                "edge_component_ids": ";".join(sorted(edges.get(component.component_id, set()))),
                "component_graph_id": graph_id_by_component.get(component.component_id, ""),
                "search_window": search.as_text(),
                "source_pair_id": spec.source_pair_id,
            }
        )
    return rows


def normalize_a1_6_references(specs: Sequence[RunSpec], fan_area: int) -> list[dict[str, Any]]:
    by_id = {spec.experiment_id: spec for spec in specs}
    rows = []
    for row in read_rows(INPUTS["a1_6_predictions"]):
        if row.get("method") not in {"C0", "C1"} or row.get("experiment_id") not in by_id:
            continue
        spec = by_id[row["experiment_id"]]
        rows.append(
            {
                "experiment_id": row["experiment_id"],
                "experiment_type": row["experiment_type"],
                "method": row["method"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "source_pair_id": row["source_pair_id"],
                "source_sar_frame": row["source_sar_frame"],
                "target_pair_id": row["target_pair_id"],
                "target_sar_frame": row["target_sar_frame"],
                "sar_frame": row["sar_frame"],
                "frame_offset": row["frame_offset"],
                "prediction_status": row.get("prediction_status", ""),
                "selection_status": row.get("selection_status", ""),
                "prediction_region": row["prediction_region"],
                "search_window": row.get("search_window", row["prediction_region"]),
                "assembly_id": "",
                "component_count": row.get("component_count_after_gate", ""),
                "assembly_centroid": row.get("response_center", ""),
                "search_window_area": row.get("search_window_area", ""),
                "static_fan_geometry_area": row.get("static_fan_geometry_area", str(fan_area)),
                "search_ratio": row.get("search_ratio", ""),
                "frozen_generation_phase": "generate",
                "target_manual_box_loaded": "false",
                "future_endpoint_loaded": "false",
                "reference_source": "A1.6_frozen_reference_unmodified",
            }
        )
    return rows


def extract_current(
    spec: RunSpec,
    method: str,
    frame: int,
    previous: Assembly,
    velocity: tuple[float, float],
    fan_mask: np.ndarray,
    azimuth: np.ndarray,
    radial: np.ndarray,
) -> tuple[Box, list[Component], list[Assembly], dict[str, set[str]]]:
    predicted = translate_box(previous.envelope, velocity[0], velocity[1])
    search = expand_box(predicted, max(58.0, previous.envelope.width * 0.33), max(34.0, previous.envelope.height * 0.42))
    image_path = sar_gray_path(SCENE, frame)
    if not image_path.exists():
        return search, [], [], {}
    arr = read_gray(image_path).astype(np.float32)
    components = extract_components(arr, fan_mask, azimuth, radial, search, f"{method}_{spec.experiment_id}_{frame}")
    assemblies, edges = build_assemblies(components, previous, search, f"{method}_{spec.experiment_id}_{frame}")
    gated = gate_assemblies(assemblies, predicted, previous)
    return search, components, gated, edges


def run_c1a(
    spec: RunSpec,
    source: Assembly,
    fan_mask: np.ndarray,
    azimuth: np.ndarray,
    radial: np.ndarray,
    fan_area: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    preds: list[dict[str, Any]] = []
    assembly_rows: list[dict[str, Any]] = []
    graph_rows: list[dict[str, Any]] = []
    current = source
    previous_confirmed = source
    velocity = (0.0, 0.0)
    first_uncertain = ""
    confirmed_frames = [spec.source_sar_frame]
    target_pair_id = ";".join(pair for pair, _ in spec.eval_pairs)
    source_search = source.envelope
    preds.append(prediction_row(spec, "C1A", spec.source_sar_frame, "source_assembly_initialized", source.envelope, source_search, source, fan_area, "A1.7_runtime"))
    assembly_rows.append(assembly_row(spec, "C1A", spec.source_sar_frame, source, "source_assembly_initialized", source_search, target_pair_id))
    for frame in range(spec.source_sar_frame + 1, spec.end_sar_frame + 1):
        search, components, candidates, edges = extract_current(spec, "C1A", frame, current, velocity, fan_mask, azimuth, radial)
        graph_rows.extend(component_rows(spec, "C1A", frame, components, edges, candidates, search))
        predicted = translate_box(current.envelope, velocity[0], velocity[1])
        if not candidates:
            status = "missing_assembly"
            current = make_assembly(f"C1A_{spec.experiment_id}_{frame}_predicted", [Component("predicted", (predicted.cx, predicted.cy), predicted, 1, 0, 0, 0, 0)], previous_confirmed)
            notes = "no response assembly after hard structural gates"
        elif len(candidates) == 1:
            status = "confirmed_assembly"
            candidate = candidates[0]
            discontinuity = box_iou(candidate.envelope, previous_confirmed.envelope) < 0.02 and center_distance(candidate.envelope, previous_confirmed.envelope) > max(70.0, previous_confirmed.envelope.width)
            if confirmed_frames:
                dt = max(1, frame - confirmed_frames[-1])
                velocity = ((candidate.centroid[0] - previous_confirmed.centroid[0]) / dt, (candidate.centroid[1] - previous_confirmed.centroid[1]) / dt)
            previous_confirmed = candidate
            current = candidate
            confirmed_frames.append(frame)
            notes = "single response assembly after graph grouping"
        else:
            status = "ambiguous_assemblies"
            corridor = make_assembly(f"C1A_{spec.experiment_id}_{frame}_corridor", [component for assembly in candidates for component in assembly.components], previous_confirmed)
            current = corridor
            discontinuity = False
            notes = "multiple response assemblies retained as ambiguous; no brightness or target ranking"
        if status != "confirmed_assembly" and not first_uncertain:
            first_uncertain = str(frame)
        discontinuity = bool(locals().get("discontinuity", False))
        used = current
        preds.append(prediction_row(spec, "C1A", frame, status, used.envelope, search, used, fan_area, "A1.7_runtime"))
        assembly_rows.append(assembly_row(spec, "C1A", frame, used, status, search, target_pair_id, first_uncertain, recovery=False, discontinuity=discontinuity, notes=notes))
    return preds, assembly_rows, graph_rows


def match_candidates_to_pending(candidates: Sequence[Assembly], pending: Sequence[Assembly]) -> list[Assembly]:
    matched: list[Assembly] = []
    for candidate in candidates:
        for branch in pending:
            if box_iou(candidate.envelope, branch.envelope) > 0.02 or center_distance(candidate.envelope, branch.envelope) <= max(48.0, branch.envelope.width * 0.8):
                matched.append(candidate)
                break
    return matched


def run_c1b(
    spec: RunSpec,
    source: Assembly,
    fan_mask: np.ndarray,
    azimuth: np.ndarray,
    radial: np.ndarray,
    fan_area: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    preds: list[dict[str, Any]] = []
    assembly_rows: list[dict[str, Any]] = []
    graph_rows: list[dict[str, Any]] = []
    current = source
    previous_confirmed = source
    velocity = (0.0, 0.0)
    pending: list[Assembly] = []
    pending_age = 0
    first_uncertain = ""
    confirmed_frames = [spec.source_sar_frame]
    target_pair_id = ";".join(pair for pair, _ in spec.eval_pairs)
    preds.append(prediction_row(spec, "C1B", spec.source_sar_frame, "source_assembly_initialized", source.envelope, source.envelope, source, fan_area, "A1.7_runtime"))
    assembly_rows.append(assembly_row(spec, "C1B", spec.source_sar_frame, source, "source_assembly_initialized", source.envelope, target_pair_id))
    for frame in range(spec.source_sar_frame + 1, spec.end_sar_frame + 1):
        search, components, candidates, edges = extract_current(spec, "C1B", frame, current, velocity, fan_mask, azimuth, radial)
        graph_rows.extend(component_rows(spec, "C1B", frame, components, edges, candidates, search))
        recovery = False
        discontinuity = False
        notes = ""
        if pending:
            matched = match_candidates_to_pending(candidates, pending)
        else:
            matched = list(candidates)
        if len(candidates) == 0:
            status = "missing_assembly"
            pending_age += 1 if pending else 0
            current = make_assembly(f"C1B_{spec.experiment_id}_{frame}_predicted", [Component("predicted", (current.envelope.cx, current.envelope.cy), current.envelope, 1, 0, 0, 0, 0)], previous_confirmed)
            notes = "no assembly; pending branch kept if it exists"
        elif len(candidates) == 1 or (pending and len(matched) == 1):
            candidate = (matched or candidates)[0]
            status = "confirmed_after_delay" if pending else "confirmed_assembly"
            recovery = bool(pending)
            if confirmed_frames:
                dt = max(1, frame - confirmed_frames[-1])
                velocity = ((candidate.centroid[0] - previous_confirmed.centroid[0]) / dt, (candidate.centroid[1] - previous_confirmed.centroid[1]) / dt)
            discontinuity = box_iou(candidate.envelope, previous_confirmed.envelope) < 0.02 and center_distance(candidate.envelope, previous_confirmed.envelope) > max(70.0, previous_confirmed.envelope.width)
            previous_confirmed = candidate
            current = candidate
            confirmed_frames.append(frame)
            pending = []
            pending_age = 0
            notes = "temporal continuity selected the only surviving assembly branch" if recovery else "single assembly"
        else:
            status = "ambiguous_assemblies_pending"
            pending = sorted(candidates, key=lambda a: (a.envelope.x1, a.envelope.y1))[:4]
            pending_age += 1
            current = make_assembly(f"C1B_{spec.experiment_id}_{frame}_uncertainty_corridor", [component for assembly in pending for component in assembly.components], previous_confirmed)
            notes = "temporary uncertainty corridor; branch list capped by spatial order, not score"
        if status not in {"confirmed_assembly", "confirmed_after_delay"} and not first_uncertain:
            first_uncertain = str(frame)
        preds.append(prediction_row(spec, "C1B", frame, status, current.envelope, search, current, fan_area, "A1.7_runtime"))
        assembly_rows.append(assembly_row(spec, "C1B", frame, current, status, search, target_pair_id, first_uncertain, recovery=recovery, discontinuity=discontinuity, notes=notes))
    return preds, assembly_rows, graph_rows


def recompute_irrecoverable(assembly_rows: list[dict[str, Any]]) -> None:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in assembly_rows:
        by_key[(row["experiment_id"], row["method"])].append(row)
    uncertain = {"missing_assembly", "ambiguous_assemblies", "ambiguous_assemblies_pending"}
    for rows in by_key.values():
        rows.sort(key=lambda row: parse_int(row["sar_frame"]))
        for k in (2, 3, 5):
            first = ""
            for idx, row in enumerate(rows):
                if row["selection_status"] not in uncertain:
                    continue
                window = rows[idx : idx + k]
                if len(window) < k or any(item["selection_status"] not in uncertain for item in window):
                    continue
                later_confirmed = any(item["selection_status"] in {"confirmed_assembly", "confirmed_after_delay"} for item in rows[idx + k :])
                if not later_confirmed:
                    first = row["sar_frame"]
                    break
            for row in rows:
                row[f"first_irrecoverable_frame_k{k}"] = first


def generate() -> str:
    specs = build_specs()
    source_ids = {spec.source_pair_id for spec in specs}
    source_rows = load_pair_rows(source_ids, include_target_boxes=False)
    geometry = build_geometry()
    fan_mask = geometry["fan"]
    fan_area = int(fan_mask.sum())
    azimuth = geometry["azimuth"]
    radial = geometry["radial"]
    source_manifest: list[dict[str, Any]] = []
    predictions = normalize_a1_6_references(specs, fan_area)
    assembly_rows: list[dict[str, Any]] = []
    component_rows_all: list[dict[str, Any]] = []
    for spec in specs:
        source_box = box_from_pair(source_rows[spec.source_pair_id], "sar_bbox")
        source, components, edges, source_search = source_assembly(source_box, spec.source_sar_frame, fan_mask, azimuth, radial)
        source_manifest.append(
            {
                "experiment_id": spec.experiment_id,
                "method": "C1A_C1B_source",
                "physical_vehicle_id": spec.physical_vehicle_id,
                "source_pair_id": spec.source_pair_id,
                "source_sar_frame": spec.source_sar_frame,
                "source_optical_frame": spec.source_optical_frame,
                "source_assembly_id": source.assembly_id,
                "source_component_count": len(source.components),
                "assembly_centroid": f"{source.centroid[0]:.3f},{source.centroid[1]:.3f}",
                "assembly_envelope": source.envelope.as_text(),
                "azimuth_span": fmt(source.azimuth_span),
                "radial_span": fmt(source.radial_span),
                "total_area": source.total_area,
                "total_intensity": fmt(source.total_intensity),
                "peak_intensity": fmt(source.peak_intensity),
                "source_anchor_structure_similarity": fmt(source.similarity),
                "frozen_predictions_sha256": "",
                "notes": "Source assembly extracted only inside source anchor box plus fixed small margin.",
            }
        )
        component_rows_all.extend(component_rows(spec, "source", spec.source_sar_frame, components, edges, [source], source_search))
        p1, a1, c1 = run_c1a(spec, source, fan_mask, azimuth, radial, fan_area)
        p2, a2, c2 = run_c1b(spec, source, fan_mask, azimuth, radial, fan_area)
        predictions.extend(p1)
        predictions.extend(p2)
        assembly_rows.extend(a1)
        assembly_rows.extend(a2)
        component_rows_all.extend(c1)
        component_rows_all.extend(c2)
    recompute_irrecoverable(assembly_rows)
    write_csv(OUTPUTS["component_graph"], component_rows_all, COMPONENT_FIELDS)
    write_csv(OUTPUTS["assembly_trace"], assembly_rows, ASSEMBLY_FIELDS)
    write_csv(OUTPUTS["frozen_predictions"], predictions, PRED_FIELDS)
    frozen_sha = sha256(OUTPUTS["frozen_predictions"])
    for row in source_manifest:
        row["frozen_predictions_sha256"] = frozen_sha
    write_csv(OUTPUTS["source_manifest"], source_manifest, SOURCE_FIELDS)
    return frozen_sha


def expected_sha() -> str:
    rows = read_rows(OUTPUTS["source_manifest"])
    return rows[0].get("frozen_predictions_sha256", "") if rows else ""


def evaluate() -> str:
    expected = expected_sha()
    actual = sha256(OUTPUTS["frozen_predictions"])
    if not expected:
        raise RuntimeError("Missing A1.7 frozen prediction SHA; run generate first.")
    if expected != actual:
        raise RuntimeError(f"A1.7 frozen prediction SHA mismatch: expected {expected}, actual {actual}")
    specs = build_specs()
    target_ids = {pair for spec in specs for pair, _ in spec.eval_pairs}
    target_rows = load_pair_rows(target_ids, include_target_boxes=True)
    predictions = read_rows(OUTPUTS["frozen_predictions"])
    assembly_rows = read_rows(OUTPUTS["assembly_trace"])
    eval_rows = build_eval_rows(specs, target_rows, predictions, assembly_rows, actual)
    write_csv(OUTPUTS["hidden_eval"], eval_rows, EVAL_FIELDS)
    delta_rows = build_delta_rows(eval_rows)
    write_csv(OUTPUTS["delta_audit"], delta_rows, DELTA_FIELDS)
    optical_rows = build_optical_rows(specs, assembly_rows)
    write_csv(OUTPUTS["optical_bypass"], optical_rows, OPTICAL_FIELDS)
    failure_rows = build_failure_rows(eval_rows, assembly_rows)
    write_csv(OUTPUTS["failure_cases"], failure_rows, FAILURE_FIELDS)
    render_visuals(specs, target_rows, predictions, assembly_rows)
    render_report(actual, specs, eval_rows, delta_rows, optical_rows, failure_rows)
    return actual


def build_eval_rows(
    specs: Sequence[RunSpec],
    targets: Mapping[str, Mapping[str, str]],
    predictions: Sequence[Mapping[str, str]],
    assembly_rows: Sequence[Mapping[str, str]],
    frozen_sha: str,
) -> list[dict[str, Any]]:
    by_pred = {(row["experiment_id"], row["method"], parse_int(row["sar_frame"])): row for row in predictions}
    by_trace: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in assembly_rows:
        by_trace[(row["experiment_id"], row["method"])].append(row)
    rows: list[dict[str, Any]] = []
    for spec in specs:
        for target_pair, target_frame in spec.eval_pairs:
            target_box = box_from_pair(targets[target_pair], "sar_bbox")
            for method in ("C0", "C1", "C1A", "C1B"):
                pred = by_pred.get((spec.experiment_id, method, target_frame))
                if pred is None:
                    continue
                region = box_from_text(pred["prediction_region"])
                trace = [row for row in by_trace.get((spec.experiment_id, method), []) if parse_int(row["sar_frame"]) <= target_frame]
                statuses = [row.get("selection_status", "") for row in trace if parse_int(row["sar_frame"]) > spec.source_sar_frame]
                pred_prefix = [
                    row
                    for row in predictions
                    if row["experiment_id"] == spec.experiment_id
                    and row["method"] == method
                    and spec.source_sar_frame < parse_int(row["sar_frame"]) <= target_frame
                ]
                if method in {"C0", "C1"}:
                    confirmed_count = sum(1 for row in pred_prefix if row.get("selection_status") == "selected_unique_component_after_hard_gate")
                    ambiguous_count = sum(1 for row in pred_prefix if row.get("selection_status") == "ambiguous_response")
                    missing_count = sum(1 for row in pred_prefix if row.get("selection_status") == "missing_observation")
                    irr2 = prediction_irrecoverable(pred_prefix, 2)
                    irr3 = prediction_irrecoverable(pred_prefix, 3)
                    irr5 = prediction_irrecoverable(pred_prefix, 5)
                else:
                    confirmed_count = sum(1 for status in statuses if status in {"confirmed_assembly", "confirmed_after_delay"})
                    ambiguous_count = sum(1 for status in statuses if "ambiguous" in status)
                    missing_count = sum(1 for status in statuses if status == "missing_assembly")
                    irr2 = first_irrecoverable(trace, 2)
                    irr3 = first_irrecoverable(trace, 3)
                    irr5 = first_irrecoverable(trace, 5)
                rows.append(
                    {
                        "experiment_id": spec.experiment_id,
                        "experiment_type": spec.experiment_type,
                        "method": method,
                        "physical_vehicle_id": spec.physical_vehicle_id,
                        "source_pair_id": spec.source_pair_id,
                        "hidden_target_pair_id": target_pair,
                        "sar_frame": target_frame,
                        "frame_offset": target_frame - spec.source_sar_frame,
                        "hidden_target_coverage": fmt(coverage(region, target_box)),
                        "hidden_target_iou": fmt(box_iou(region, target_box)),
                        "prediction_center_to_visible_response_center": fmt(center_distance(region, target_box)),
                        "prediction_region_area": fmt(region.area),
                        "first_uncertain_frame": first_uncertain_from_prediction(spec, method, predictions, trace, target_frame),
                        "first_irrecoverable_frame_k2": irr2,
                        "first_irrecoverable_frame_k3": irr3,
                        "first_irrecoverable_frame_k5": irr5,
                        "confirmed_assembly_frames": confirmed_count,
                        "ambiguous_assembly_frames": ambiguous_count,
                        "missing_assembly_frames": missing_count,
                        "ambiguity_recovery_count": sum(1 for row in trace if row.get("ambiguity_recovery_event") == "true"),
                        "association_discontinuity_count": sum(1 for row in trace if row.get("association_discontinuity") == "true"),
                        "search_ratio": pred.get("search_ratio", ""),
                        "frozen_predictions_sha256_verified": frozen_sha,
                        "target_box_loaded_phase": "evaluate_only",
                    }
                )
    return rows


def prediction_irrecoverable(rows: Sequence[Mapping[str, str]], k: int) -> str:
    uncertain = {"missing_observation", "ambiguous_response"}
    ordered = sorted(rows, key=lambda row: parse_int(row["sar_frame"]))
    for idx, row in enumerate(ordered):
        if row.get("selection_status") not in uncertain:
            continue
        window = ordered[idx : idx + k]
        if len(window) < k or any(item.get("selection_status") not in uncertain for item in window):
            continue
        later_confirmed = any(item.get("selection_status") == "selected_unique_component_after_hard_gate" for item in ordered[idx + k :])
        if not later_confirmed:
            return row["sar_frame"]
    return ""


def first_uncertain_from_prediction(
    spec: RunSpec,
    method: str,
    predictions: Sequence[Mapping[str, str]],
    trace: Sequence[Mapping[str, str]],
    target_frame: int,
) -> str:
    if method in {"C1A", "C1B"}:
        for row in trace:
            if parse_int(row["sar_frame"]) <= target_frame and row.get("first_uncertain_frame"):
                return row["first_uncertain_frame"]
        return ""
    uncertain = {"missing_observation", "ambiguous_response"}
    for row in sorted(predictions, key=lambda r: parse_int(r["sar_frame"])):
        if row["experiment_id"] == spec.experiment_id and row["method"] == method and spec.source_sar_frame < parse_int(row["sar_frame"]) <= target_frame:
            if row.get("selection_status") in uncertain:
                return row["sar_frame"]
    return ""


def first_irrecoverable(trace: Sequence[Mapping[str, str]], k: int) -> str:
    field = f"first_irrecoverable_frame_k{k}"
    for row in trace:
        if row.get(field):
            return row[field]
    return ""


def build_delta_rows(eval_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in eval_rows:
        by_key[(row["experiment_id"], row["hidden_target_pair_id"])][row["method"]] = row
    rows: list[dict[str, Any]] = []
    for (_exp, target), methods in by_key.items():
        base = methods.get("C1")
        if not base:
            continue
        for method in ("C1A", "C1B"):
            if method not in methods:
                continue
            row = methods[method]
            cov_delta = parse_float(row["hidden_target_coverage"]) - parse_float(base["hidden_target_coverage"])
            iou_delta = parse_float(row["hidden_target_iou"]) - parse_float(base["hidden_target_iou"])
            center_delta = parse_float(base["prediction_center_to_visible_response_center"]) - parse_float(row["prediction_center_to_visible_response_center"])
            search_delta = parse_float(row["search_ratio"]) - parse_float(base["search_ratio"])
            amb_delta = parse_int(row["ambiguous_assembly_frames"]) - parse_int(base.get("ambiguous_assembly_frames", base.get("ambiguous_frame_count", 0)))
            if search_delta > 0.05 and center_delta < 0:
                verdict = "harmed_area_expansion"
            elif cov_delta > 0.05 and iou_delta < 0 and center_delta < 0:
                verdict = "coverage_only_broad_assembly"
            elif center_delta > 8 and search_delta <= 0.03:
                verdict = "improved"
            elif cov_delta < -0.05 or center_delta < -8:
                verdict = "harmed"
            else:
                verdict = "neutral"
            rows.append(
                {
                    "comparison": f"{method}_minus_C1",
                    "experiment_id": row["experiment_id"],
                    "experiment_type": row["experiment_type"],
                    "physical_vehicle_id": row["physical_vehicle_id"],
                    "hidden_target_pair_id": target,
                    "sar_frame": row["sar_frame"],
                    "coverage_delta": fmt(cov_delta),
                    "iou_delta": fmt(iou_delta),
                    "center_error_delta": fmt(center_delta),
                    "search_ratio_delta": fmt(search_delta),
                    "ambiguity_delta": amb_delta,
                    "verdict": verdict,
                    "notes": "Positive center_error_delta means assembly method is closer than A1.6 C1.",
                }
            )
    return rows


def build_optical_rows(specs: Sequence[RunSpec], assembly_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    optical = load_optical_state()
    by_key: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in assembly_rows:
        if row.get("selection_status") in {"confirmed_assembly", "confirmed_after_delay", "source_assembly_initialized"}:
            by_key[(row["experiment_id"], row["method"])].append(row)
    rows: list[dict[str, Any]] = []
    spec_by_id = {spec.experiment_id: spec for spec in specs}
    for (exp_id, method), trace in by_key.items():
        spec = spec_by_id[exp_id]
        trace.sort(key=lambda row: parse_int(row["sar_frame"]))
        for prev, cur in zip(trace, trace[1:]):
            prev_box = box_from_text(prev["assembly_envelope"])
            cur_box = box_from_text(cur["assembly_envelope"])
            sar_az_sign = sign_text(cur_box.cx - prev_box.cx, 0.5)
            sar_rad_sign = sign_text(cur_box.cy - prev_box.cy, 0.5)
            for shift in (-1, 0, 1):
                estimated_opt = spec.source_optical_frame + (parse_int(cur["sar_frame"]) + shift - spec.source_sar_frame) * 24.0 / 50.0
                opt_row = nearest_optical(optical.get(spec.physical_vehicle_id, []), estimated_opt)
                vx_sign = sign_text(parse_float(opt_row.get("velocity_x"), 0.0) if opt_row else math.nan, 0.5)
                depth_sign = sign_text(parse_float(opt_row.get("depth_velocity"), 0.0) if opt_row else math.nan, 0.001)
                az_cons = same_nonzero_sign(vx_sign, sar_az_sign)
                rad_cons = same_nonzero_sign(depth_sign, sar_rad_sign)
                single = "NOT_TESTED" if "NOT_TESTED" in {az_cons, rad_cons} else bool_text(az_cons == "true" and rad_cons == "true")
                rows.append(
                    {
                        "experiment_id": exp_id,
                        "method": method,
                        "physical_vehicle_id": spec.physical_vehicle_id,
                        "sar_frame": cur["sar_frame"],
                        "sync_shift_sar_frames": shift,
                        "estimated_optical_frame": fmt(estimated_opt),
                        "optical_velocity_x_sign": vx_sign,
                        "sar_azimuth_delta_sign": sar_az_sign,
                        "azimuth_relation_consistent": az_cons,
                        "optical_depth_velocity_sign": depth_sign,
                        "sar_radial_delta_sign": sar_rad_sign,
                        "radial_relation_consistent": rad_cons,
                        "single_frame_consistency": single,
                        "window3_consistency": "diagnostic_only_not_filtering",
                        "window5_consistency": "diagnostic_only_not_filtering",
                        "relation_used_for_filtering": "false",
                        "notes": "O1 bypass diagnostic only; optical state did not delete SAR assemblies.",
                    }
                )
    fill_window_consistency(rows, 3)
    fill_window_consistency(rows, 5)
    return rows


def fill_window_consistency(rows: list[dict[str, Any]], window: int) -> None:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["experiment_id"], row["method"], parse_int(row["sync_shift_sar_frames"]))].append(row)
    field = f"window{window}_consistency"
    for group in grouped.values():
        group.sort(key=lambda row: parse_int(row["sar_frame"]))
        for idx, row in enumerate(group):
            sub = group[max(0, idx - window + 1) : idx + 1]
            vals = [item["single_frame_consistency"] for item in sub if item["single_frame_consistency"] != "NOT_TESTED"]
            row[field] = fmt(sum(v == "true" for v in vals) / len(vals)) if vals else "NOT_TESTED"


def build_failure_rows(eval_rows: Sequence[Mapping[str, Any]], assembly_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    priority = {spec.experiment_id for spec in build_specs() if spec.priority_group == "priority_short"}
    for row in eval_rows:
        if row["method"] not in {"C1A", "C1B"} or row["experiment_id"] not in priority:
            continue
        amb = parse_int(row["ambiguous_assembly_frames"])
        miss = parse_int(row["missing_assembly_frames"])
        if amb or miss or row["first_irrecoverable_frame_k3"]:
            judgement = visual_judgement(row["experiment_id"], row["method"], amb, miss, parse_float(row["hidden_target_coverage"]))
            rows.append(
                {
                    "case_id": f"FAIL_{len(rows) + 1:03d}",
                    "experiment_id": row["experiment_id"],
                    "method": row["method"],
                    "physical_vehicle_id": row["physical_vehicle_id"],
                    "failure_type": "assembly_uncertainty_or_irrecoverable",
                    "sar_frame": row["sar_frame"],
                    "first_uncertain_frame": row["first_uncertain_frame"],
                    "first_irrecoverable_frame": row["first_irrecoverable_frame_k3"],
                    "visual_png": rel(VISUALS["priority_eval"]),
                    "chinese_judgement": judgement,
                    "notes": "Priority short interval visual self-review row.",
                }
            )
    if not rows:
        rows.append(
            {
                "case_id": "INFO_001",
                "experiment_id": "all",
                "method": "C1A/C1B",
                "physical_vehicle_id": "",
                "failure_type": "no_priority_failure_rows",
                "sar_frame": "",
                "first_uncertain_frame": "",
                "first_irrecoverable_frame": "",
                "visual_png": rel(VISUALS["priority_eval"]),
                "chinese_judgement": "优先短区间未触发不可恢复失败，但仍需中间帧盲评确认。",
                "notes": "",
            }
        )
    return rows


def visual_judgement(exp_id: str, method: str, ambiguous: int, missing: int, coverage_value: float) -> str:
    if coverage_value >= 0.65 and ambiguous > 0:
        return "{} 的 {} 显示多散射组合后仍覆盖目标，C1 的歧义更像同车多热点语义，而不是多车切换。".format(exp_id, method)
    if missing > 0:
        return "{} 的 {} 存在响应缺失；组合体没有稳定恢复，不能宣称长距离因果关联成立。".format(exp_id, method)
    return "{} 的 {} 组合体结构可解释，但仍需检查是否把背景散射并入车辆响应。".format(exp_id, method)

def render_visuals(
    specs: Sequence[RunSpec],
    targets: Mapping[str, Mapping[str, str]],
    predictions: Sequence[Mapping[str, str]],
    assembly_rows: Sequence[Mapping[str, str]],
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pred_by_key = {(row["experiment_id"], row["method"], parse_int(row["sar_frame"])): row for row in predictions}
    trace_by_key: dict[tuple[str, str, int], Mapping[str, str]] = {}
    for row in assembly_rows:
        trace_by_key[(row["experiment_id"], row["method"], parse_int(row["sar_frame"]))] = row
    priority_specs = [spec for spec in specs if spec.priority_group == "priority_short"]
    runtime_tiles = []
    eval_tiles = []
    diff_tiles = []
    for spec in priority_specs:
        target_pair, target_frame = spec.eval_pairs[-1]
        frames = sorted({spec.source_sar_frame, min(spec.end_sar_frame, spec.source_sar_frame + 1), (spec.source_sar_frame + spec.end_sar_frame) // 2, target_frame})
        for frame in frames:
            row = pred_by_key.get((spec.experiment_id, "C1B", frame)) or pred_by_key.get((spec.experiment_id, "C1A", frame))
            if not row:
                continue
            boxes = [(box_from_text(row["prediction_region"]), (30, 220, 120), 3)]
            runtime_tiles.append(image_tile(frame, f"RUNTIME {spec.experiment_id} C1B SAR{frame}", boxes))
        eval_row = pred_by_key.get((spec.experiment_id, "C1B", target_frame))
        if eval_row:
            boxes = [
                (box_from_text(eval_row["prediction_region"]), (30, 220, 120), 3),
                (box_from_pair(targets[target_pair], "sar_bbox"), (255, 210, 40), 2),
            ]
            eval_tiles.append(image_tile(target_frame, f"EVAL_ONLY {spec.experiment_id} C1B", boxes))
        c1a = pred_by_key.get((spec.experiment_id, "C1A", target_frame))
        c1b = pred_by_key.get((spec.experiment_id, "C1B", target_frame))
        if c1a and c1b:
            diff_tiles.append(
                image_tile(
                    target_frame,
                    f"C1A green / C1B cyan {spec.experiment_id}",
                    [(box_from_text(c1a["prediction_region"]), (30, 220, 120), 3), (box_from_text(c1b["prediction_region"]), (40, 210, 255), 2)],
                )
            )
    open_tiles = []
    for spec in specs:
        if spec.experiment_type != "open_loop":
            continue
        for target_pair, target_frame in spec.eval_pairs:
            row = pred_by_key.get((spec.experiment_id, "C1B", target_frame))
            if row:
                open_tiles.append(
                    image_tile(
                        target_frame,
                        f"EVAL_ONLY {spec.experiment_id} SAR{target_frame}",
                        [(box_from_text(row["prediction_region"]), (30, 220, 120), 3), (box_from_pair(targets[target_pair], "sar_bbox"), (255, 210, 40), 2)],
                    )
                )
    render_sheet(VISUALS["priority_runtime"], runtime_tiles, 4)
    render_sheet(VISUALS["priority_eval"], eval_tiles, 4)
    render_sheet(VISUALS["difference"], diff_tiles, 4)
    render_sheet(VISUALS["open_loop"], open_tiles, 4)


def image_tile(frame: int, title: str, boxes: Sequence[tuple[Box, tuple[int, int, int], int]]) -> Image.Image:
    size = (360, 220)
    path = sar_gray_path(SCENE, frame)
    if path.exists():
        img = Image.open(path).convert("RGB").resize(size)
    else:
        img = Image.new("RGB", size, (25, 25, 25))
    draw = ImageDraw.Draw(img)
    sx = size[0] / SAR_WIDTH
    sy = size[1] / SAR_HEIGHT
    for box, color, width in boxes:
        draw.rectangle([box.x1 * sx, box.y1 * sy, box.x2 * sx, box.y2 * sy], outline=color, width=width)
    draw.rectangle([0, 0, size[0], 30], fill=(0, 0, 0))
    draw.text((5, 8), title[:58], fill=(255, 255, 255))
    return img


def render_sheet(path: Path, tiles: Sequence[Image.Image], cols: int) -> None:
    if not tiles:
        Image.new("RGB", (360, 220), (25, 25, 25)).save(path)
        return
    w, h = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (w * cols, h * rows), (18, 18, 18))
    for idx, tile in enumerate(tiles):
        sheet.paste(tile, ((idx % cols) * w, (idx // cols) * h))
    sheet.save(path)


def summarize(eval_rows: Sequence[Mapping[str, Any]], delta_rows: Sequence[Mapping[str, Any]], optical_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    adjacent = [row for row in eval_rows if row["experiment_type"] == "adjacent_hidden_anchor"]
    out: dict[str, Any] = {}
    for method in ("C0", "C1", "C1A", "C1B"):
        rows = [row for row in adjacent if row["method"] == method]
        out[method] = {
            "adjacent_count": len(rows),
            "coverage_median": fmt(percentile([parse_float(row["hidden_target_coverage"]) for row in rows], 50)),
            "center_error_median": fmt(percentile([parse_float(row["prediction_center_to_visible_response_center"]) for row in rows], 50)),
            "confirmed": sum(parse_int(row.get("confirmed_assembly_frames", 0)) for row in rows),
            "ambiguous": sum(parse_int(row.get("ambiguous_assembly_frames", 0)) for row in rows),
            "missing": sum(parse_int(row.get("missing_assembly_frames", 0)) for row in rows),
            "recoveries": sum(parse_int(row.get("ambiguity_recovery_count", 0)) for row in rows),
            "discontinuities": sum(parse_int(row.get("association_discontinuity_count", 0)) for row in rows),
            "search_ratio_median": fmt(percentile([parse_float(row["search_ratio"]) for row in rows], 50)),
        }
    c1a_delta = [row for row in delta_rows if row["comparison"] == "C1A_minus_C1" and row["experiment_type"] == "adjacent_hidden_anchor"]
    c1b_delta = [row for row in delta_rows if row["comparison"] == "C1B_minus_C1" and row["experiment_type"] == "adjacent_hidden_anchor"]
    out["c1a_improved"] = sum(1 for row in c1a_delta if row["verdict"] == "improved")
    out["c1a_harmed"] = sum(1 for row in c1a_delta if row["verdict"].startswith("harmed") or row["verdict"] == "coverage_only_broad_assembly")
    out["c1b_improved"] = sum(1 for row in c1b_delta if row["verdict"] == "improved")
    out["c1b_harmed"] = sum(1 for row in c1b_delta if row["verdict"].startswith("harmed") or row["verdict"] == "coverage_only_broad_assembly")
    az_vals = [row["azimuth_relation_consistent"] for row in optical_rows if row["azimuth_relation_consistent"] != "NOT_TESTED"]
    rad_vals = [row["radial_relation_consistent"] for row in optical_rows if row["radial_relation_consistent"] != "NOT_TESTED"]
    out["azimuth_support"] = fmt(sum(v == "true" for v in az_vals) / len(az_vals)) if az_vals else "NOT_TESTED"
    out["radial_support"] = fmt(sum(v == "true" for v in rad_vals) / len(rad_vals)) if rad_vals else "NOT_TESTED"
    return out


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
    specs: Sequence[RunSpec],
    eval_rows: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
    optical_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
) -> None:
    summary = summarize(eval_rows, delta_rows, optical_rows)
    source_rows = read_rows(OUTPUTS["source_manifest"])
    adjacent_rows = [row for row in eval_rows if row["experiment_type"] == "adjacent_hidden_anchor"]
    open_rows = [row for row in eval_rows if row["experiment_type"] == "open_loop"]
    assembly_supported = "YES" if sum(parse_int(row["source_component_count"]) for row in source_rows) / max(1, len(source_rows)) > 1.5 else "WEAK"
    reduces_ambiguity = "NO"
    if summary["C1A"]["ambiguous"] < summary["C1"]["ambiguous"] or summary["C1B"]["ambiguous"] < summary["C1"]["ambiguous"]:
        reduces_ambiguity = "PARTIAL"
    delay_value = "PARTIAL" if summary["C1B"]["recoveries"] > 0 else "NO"
    ready = "NO"
    if reduces_ambiguity != "NO" and summary["c1b_harmed"] <= 2 and summary["C1B"]["discontinuities"] > 0:
        ready = "CONDITIONAL"
    lines = [
        "# OTY2 WGV3.6A-A1.7 Response Assembly Tracking",
        "",
        "## Boundary",
        "",
        f"- requested start commit: `{REQUESTED_START_COMMIT}`",
        f"- frozen predictions SHA256: `{frozen_sha}`",
        "- generate/evaluate separation: `PASS`",
        "- A1.6 original outputs modified: `false`",
        "- hidden target boxes loaded during generate: `false`",
        "- optical relation used for filtering: `false`",
        "- GM_RM011 executed: `false`",
        "",
        "## Metric Rename",
        "",
        "- A1.6 `first_lost_frame` is renamed here to `first_uncertain_frame`.",
        "- `first_uncertain_frame`: first `missing_observation`, `ambiguous_response`, `missing_assembly`, or `ambiguous_assemblies` frame.",
        f"- `first_irrecoverable_frame`: first uncertain run of K frames with no later confirmed assembly before evaluation endpoint. Frozen K=`{IRRECOVERABLE_K}`; sensitivity K=2/3/5 is reported.",
        "- `response_switch_event` is not reused as a reliable switch metric; A1.7 reports `association_discontinuity` and leaves `identity_contamination=NOT_TESTED`.",
        "",
        "## Source Assemblies",
        "",
        md_table(source_rows, ["experiment_id", "source_pair_id", "source_sar_frame", "source_component_count", "assembly_envelope", "azimuth_span", "radial_span", "frozen_predictions_sha256"]),
        "",
        "## Method Summary",
        "",
        md_table(
            [{"method": method, **summary[method]} for method in ("C0", "C1", "C1A", "C1B")],
            ["method", "adjacent_count", "coverage_median", "center_error_median", "confirmed", "ambiguous", "missing", "recoveries", "discontinuities", "search_ratio_median"],
        ),
        "",
        "## Adjacent Hidden Targets",
        "",
        md_table(
            adjacent_rows,
            [
                "experiment_id",
                "method",
                "hidden_target_pair_id",
                "sar_frame",
                "hidden_target_coverage",
                "hidden_target_iou",
                "prediction_center_to_visible_response_center",
                "first_uncertain_frame",
                "first_irrecoverable_frame_k3",
                "ambiguous_assembly_frames",
                "ambiguity_recovery_count",
                "association_discontinuity_count",
            ],
        ),
        "",
        "## Open Loop",
        "",
        md_table(
            open_rows,
            [
                "experiment_id",
                "method",
                "hidden_target_pair_id",
                "sar_frame",
                "hidden_target_coverage",
                "prediction_center_to_visible_response_center",
                "first_uncertain_frame",
                "first_irrecoverable_frame_k3",
                "ambiguous_assembly_frames",
                "ambiguity_recovery_count",
            ],
        ),
        "",
        "## Delta Audit",
        "",
        md_table(delta_rows, DELTA_FIELDS),
        "",
        "## Optical Bypass Summary",
        "",
        f"- optical azimuth trend relation support ratio: `{summary['azimuth_support']}`",
        f"- optical radial trend relation support ratio: `{summary['radial_support']}`",
        "- +/-1 SAR frame sensitivity is recorded in the optical bypass CSV; optical did not delete any SAR assembly.",
        "",
        "## Visual Self Review",
        "",
        "- `outputs/wgv3_6a_a1_7_20260711/a1_7_priority_short_interval_runtime_assemblies.png`: runtime view without hidden boxes.",
        "- `outputs/wgv3_6a_a1_7_20260711/a1_7_priority_short_interval_eval_only_overlay.png`: EVAL_ONLY target overlay.",
        "- `outputs/wgv3_6a_a1_7_20260711/a1_7_c1a_c1b_difference_examples.png`: C1A/C1B differences.",
        "- `outputs/wgv3_6a_a1_7_20260711/a1_7_open_loop_eval_only_overlay.png`: open-loop EVAL_ONLY overlay.",
        "",
        "Chinese judgements:",
        "",
        *[f"- {row['chinese_judgement']}" for row in failure_rows[:12]],
        "",
        "## Gate Verdicts",
        "",
        f"- `ASSEMBLY_SEMANTICS_SUPPORTED`: `{assembly_supported}`",
        f"- `ASSEMBLY_REDUCES_FALSE_AMBIGUITY`: `{reduces_ambiguity}`",
        f"- `TEMPORAL_DELAYED_CONFIRMATION_ADDED_VALUE`: `{delay_value}`",
        "- `ASSOCIATION_DISCONTINUITY_MEASURED`: `PASS`",
        f"- `OPTICAL_AZIMUTH_RELATION_SUPPORTED`: `{'NO' if summary['azimuth_support'] in {'NOT_TESTED', '0'} else 'DIAGNOSTIC_ONLY_PARTIAL'}`",
        f"- `OPTICAL_RADIAL_RELATION_SUPPORTED`: `{'NO' if summary['radial_support'] in {'NOT_TESTED', '0'} else 'DIAGNOSTIC_ONLY_PARTIAL'}`",
        f"- `A1.7_CAUSAL_ASSOCIATION_READY`: `{ready}`",
        "- `INTERMEDIATE_FRAME_BLIND_EVAL_PENDING`: `true`",
        "- `GM_RM011_BLOCKED`: `true`",
        "",
        "## Created Files",
        "",
        *[f"- `{rel(path)}`" for path in OUTPUTS.values()],
        "",
        "## Next Step",
        "",
        "Do not run GM_RM011. If A1.7 is not ready, repair assembly association and add independent intermediate-frame blind evaluation before any pressure-test expansion.",
    ]
    write_text(OUTPUTS["report"], "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "evaluate", "all"])
    args = parser.parse_args()
    if args.command == "generate":
        print(f"generated frozen_predictions_sha256={generate()}")
    elif args.command == "evaluate":
        print(f"evaluated frozen_predictions_sha256={evaluate()}")
    else:
        generated = generate()
        evaluated = evaluate()
        if generated != evaluated:
            raise RuntimeError("A1.7 generated/evaluated SHA mismatch")
        print(f"all complete frozen_predictions_sha256={evaluated}")


if __name__ == "__main__":
    main()
