"""Freeze GM_RM019 S2-A GT-region counterfactual evaluation plan.

The plan command is intentionally geometry-only. It reads GT linkage, mask context,
local response geometry, and the S1-R1 independent-geometry map. It does not read
SAR gray intensities or S1-R1 measurement outcomes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
WORKSPACE_TASK_DIR = Path("D:/profile/research/workspace/tasks/oty2_gm019_s2a_gt_region_counterfactual_identifiability")
WORKSPACE_LOG = Path("D:/profile/research/workspace/logs/oty2_gm019_s2a_gt_region_counterfactual_identifiability_20260712.md")

DATE = "20260712"
SCENE = "GM_RM019"
CALIBRATION_STATUS = "PROJECT_CONFIRMED"
MAX_RANGE_M = 40.0
M_PER_PX = 0.03
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_RADIUS_PX = 1332.7

INPUTS = {
    "paired_annotations": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "response_unit_gt_matrix": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_20260711.csv",
    "mask_observation_audit": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv",
    "gt_mask_visible_geometry": SAMPLES_DIR / "oty2_gm_rm019_gt_mask_visible_geometry_20260712.csv",
    "local_response_units": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv",
    "s1_r1_independent_geometry_map": SAMPLES_DIR / "oty2_gm_rm019_s1_r1_independent_geometry_map_20260712.csv",
    "s1_r1_report": REPORT_DIR / "oty2_gm_rm019_static_axis_rotation_s1_r1_20260712.md",
    "protocol": REPO_ROOT / "docs" / "OTY2_GM019_GT_REGION_COUNTERFACTUAL_IDENTIFIABILITY_S2_A_PROTOCOL.md",
}

OUTPUTS = {
    "evaluation_instance_manifest": SAMPLES_DIR / f"oty2_gm_rm019_s2a_evaluation_instance_manifest_{DATE}.csv",
    "gt_geometry_semantics": SAMPLES_DIR / f"oty2_gm_rm019_s2a_gt_geometry_semantics_{DATE}.csv",
    "counterfactual_plan": SAMPLES_DIR / f"oty2_gm_rm019_s2a_counterfactual_plan_{DATE}.csv",
    "plan_seal": SAMPLES_DIR / f"oty2_gm_rm019_s2a_plan_seal_{DATE}.csv",
}

GENERATED_KEYS = ["evaluation_instance_manifest", "gt_geometry_semantics", "counterfactual_plan", "plan_seal"]
VERIFY_TMP = SAMPLES_DIR / "_s2a_plan_verify_tmp"

MANIFEST_FIELDS = [
    "gt_pair_id",
    "gt_instance_id",
    "scene",
    "sar_frame",
    "physical_vehicle_id",
    "evaluation_pool",
    "pool_reason",
    "identity_conflict",
    "linked_response_unit_ids",
    "linked_independent_geometry_ids",
    "linked_independent_geometry_count",
    "pair_confidence",
    "identity_confidence",
    "mask_class",
    "mask_context",
]

GT_FIELDS = [
    "gt_pair_id",
    "gt_instance_id",
    "sar_frame",
    "source_geometry_type",
    "final_heading_deg",
    "gt_width_axis_image_deg",
    "gt_long_axis_image_deg",
    "gt_long_axis_to_range_signed_deg",
    "gt_long_axis_to_range_acute_deg",
    "final_w_px",
    "final_h_px",
    "gt_center_x",
    "gt_center_y",
    "gt_polygon_xy",
    "gt_semantic_note_cn",
]

PLAN_FIELDS = [
    "plan_region_id",
    "gt_pair_id",
    "gt_instance_id",
    "physical_vehicle_id",
    "evaluation_pool",
    "sar_frame",
    "region_role",
    "template_family",
    "template_axis",
    "template_operation",
    "delta_m",
    "rotation_deg",
    "center_shift_range_m",
    "center_shift_azimuth_m",
    "edge_name",
    "scale_axis",
    "matched_background_offset_order",
    "geometry_source",
    "region_center_x",
    "region_center_y",
    "region_polygon_xy",
    "gt_width_axis_image_deg",
    "gt_long_axis_image_deg",
    "mask_class",
    "mask_context",
    "linked_independent_geometry_ids",
    "plan_stage_intensity_read",
    "plan_stage_s1_r1_measurement_outcomes_read",
    "background_selection_rule",
]

SEAL_FIELDS = ["seal_key", "seal_value", "source_file", "sha256", "row_count"]


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def w(self) -> float:
        return self.x2 - self.x1

    @property
    def h(self) -> float:
        return self.y2 - self.y1


def fmt(value: Any, ndigits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(f) or math.isinf(f):
        return ""
    text = f"{f:.{ndigits}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(str(value).strip())
    except ValueError:
        return default


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".csv":
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def parse_box_text(text: str) -> Box | None:
    if not text:
        return None
    vals = [parse_float(p) for p in str(text).replace(";", ",").split(",")]
    if len(vals) != 4 or any(math.isnan(v) for v in vals):
        return None
    x1, y1, x2, y2 = vals
    return Box(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def paired_box(row: Mapping[str, str]) -> Box:
    return Box(
        parse_float(row["sar_bbox_x1"]),
        parse_float(row["sar_bbox_y1"]),
        parse_float(row["sar_bbox_x2"]),
        parse_float(row["sar_bbox_y2"]),
    )


def box_from_polygon(poly: Sequence[tuple[float, float]]) -> Box:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return Box(min(xs), min(ys), max(xs), max(ys))


def bbox_iou(a: Box, b: Box) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a.w) * max(0.0, a.h)
    area_b = max(0.0, b.w) * max(0.0, b.h)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def polygon_text(poly: Sequence[tuple[float, float]]) -> str:
    return ";".join(f"{fmt(x, 3)},{fmt(y, 3)}" for x, y in poly)


def parse_polygon(text: str) -> list[tuple[float, float]]:
    pts = []
    for item in str(text).split(";"):
        if not item:
            continue
        x, y = item.split(",")
        pts.append((float(x), float(y)))
    return pts


def rect_polygon(cx: float, cy: float, w: float, h: float, heading_deg: float) -> list[tuple[float, float]]:
    rad = math.radians(heading_deg)
    ux, uy = math.cos(rad), math.sin(rad)
    vx, vy = -math.sin(rad), math.cos(rad)
    pts = []
    for sx, sy in [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]:
        pts.append((cx + sx * w * ux + sy * h * vx, cy + sx * w * uy + sy * h * vy))
    return pts


def unit_vectors(cx: float, cy: float) -> tuple[float, float, float, float]:
    dx = cx - FAN_CENTER_X
    dy = cy - FAN_CENTER_Y
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return 0.0, -1.0, 1.0, 0.0
    rx = dx / norm
    ry = dy / norm
    return rx, ry, -ry, rx


def signed_axis_to_ref_deg(vx: float, vy: float, ux: float, uy: float) -> float:
    beta = math.degrees(math.atan2(ux * vy - uy * vx, ux * vx + uy * vy))
    while beta < -90.0:
        beta += 180.0
    while beta >= 90.0:
        beta -= 180.0
    return beta


def fan_valid_point(x: float, y: float) -> bool:
    r = math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)
    a = math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))
    return 0 <= x < SAR_WIDTH and 0 <= y < SAR_HEIGHT and r <= FAN_RADIUS_PX and -90.0 <= a <= 90.0


def translate(poly: Sequence[tuple[float, float]], dx: float, dy: float) -> list[tuple[float, float]]:
    return [(x + dx, y + dy) for x, y in poly]


def rotate(poly: Sequence[tuple[float, float]], cx: float, cy: float, deg: float) -> list[tuple[float, float]]:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    out = []
    for x, y in poly:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * c - dy * s, cy + dx * s + dy * c))
    return out


def radar_bounds(poly: Sequence[tuple[float, float]], cx: float, cy: float, rx: float, ry: float, ax: float, ay: float) -> tuple[float, float, float, float]:
    pr = [(x - cx) * rx + (y - cy) * ry for x, y in poly]
    pa = [(x - cx) * ax + (y - cy) * ay for x, y in poly]
    return min(pr), max(pr), min(pa), max(pa)


def radar_rect_polygon(cx: float, cy: float, rx: float, ry: float, ax: float, ay: float, bounds: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    rmin, rmax, amin, amax = bounds
    pts = []
    for rr, aa in [(rmin, amin), (rmax, amin), (rmax, amax), (rmin, amax)]:
        pts.append((cx + rr * rx + aa * ax, cy + rr * ry + aa * ay))
    return pts


def plan_rows_for_instance(
    manifest: Mapping[str, str],
    gt: Mapping[str, str],
    all_gt_boxes_by_frame: Mapping[str, Sequence[Box]],
    response_boxes_by_frame: Mapping[str, Sequence[Box]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    pair_id = manifest["gt_pair_id"]
    frame = manifest["sar_frame"]
    cx = parse_float(gt["gt_center_x"])
    cy = parse_float(gt["gt_center_y"])
    base_poly = parse_polygon(gt["gt_polygon_xy"])
    rx, ry, ax, ay = unit_vectors(cx, cy)

    def add(
        role: str,
        family: str,
        axis: str,
        op: str,
        poly: Sequence[tuple[float, float]],
        delta_m: float = 0.0,
        rotation_deg: float = 0.0,
        shift_r_m: float = 0.0,
        shift_a_m: float = 0.0,
        edge_name: str = "",
        scale_axis: str = "",
        bg_order: str = "",
    ) -> None:
        idx = len(rows) + 1
        pcx = sum(p[0] for p in poly) / len(poly)
        pcy = sum(p[1] for p in poly) / len(poly)
        rows.append(
            {
                "plan_region_id": f"{pair_id}_S2A_{idx:03d}",
                "gt_pair_id": pair_id,
                "gt_instance_id": manifest["gt_instance_id"],
                "physical_vehicle_id": manifest["physical_vehicle_id"],
                "evaluation_pool": manifest["evaluation_pool"],
                "sar_frame": frame,
                "region_role": role,
                "template_family": family,
                "template_axis": axis,
                "template_operation": op,
                "delta_m": fmt(delta_m),
                "rotation_deg": fmt(rotation_deg),
                "center_shift_range_m": fmt(shift_r_m),
                "center_shift_azimuth_m": fmt(shift_a_m),
                "edge_name": edge_name,
                "scale_axis": scale_axis,
                "matched_background_offset_order": bg_order,
                "geometry_source": "PLAN_STAGE_GEOMETRY_ONLY",
                "region_center_x": fmt(pcx, 3),
                "region_center_y": fmt(pcy, 3),
                "region_polygon_xy": polygon_text(poly),
                "gt_width_axis_image_deg": gt["gt_width_axis_image_deg"],
                "gt_long_axis_image_deg": gt["gt_long_axis_image_deg"],
                "mask_class": manifest["mask_class"],
                "mask_context": manifest["mask_context"],
                "linked_independent_geometry_ids": manifest["linked_independent_geometry_ids"],
                "plan_stage_intensity_read": "false",
                "plan_stage_s1_r1_measurement_outcomes_read": "false",
                "background_selection_rule": "not_intensity_selected_fixed_order_offsets" if family == "matched_background" else "",
            }
        )

    add("gt_original", "gt_original", "gt", "original", base_poly)
    for delta in [0.15, 0.30, 0.45]:
        for axis_name, ux, uy in [("range", rx, ry), ("azimuth", ax, ay)]:
            for sign in [-1, 1]:
                shift_m = sign * delta
                add("counterfactual", "center_shift", axis_name, "shift", translate(base_poly, ux * shift_m / M_PER_PX, uy * shift_m / M_PER_PX), delta_m=shift_m, shift_r_m=shift_m if axis_name == "range" else 0.0, shift_a_m=shift_m if axis_name == "azimuth" else 0.0)
    for delta in [0.15, 0.30]:
        for sr in [-1, 1]:
            for sa in [-1, 1]:
                add("counterfactual", "diagonal_center_shift", "range+azimuth", "shift", translate(base_poly, (sr * delta * rx + sa * delta * ax) / M_PER_PX, (sr * delta * ry + sa * delta * ay) / M_PER_PX), delta_m=delta, shift_r_m=sr * delta, shift_a_m=sa * delta)

    bounds = list(radar_bounds(base_poly, cx, cy, rx, ry, ax, ay))
    for delta in [0.15, 0.30]:
        for side, idx, sign_name in [("range_near", 0, "near"), ("range_far", 1, "far"), ("azimuth_left", 2, "left"), ("azimuth_right", 3, "right")]:
            for sign in [-1, 1]:
                b = bounds.copy()
                b[idx] += sign * delta / M_PER_PX
                if b[1] < b[0]:
                    mid = (b[0] + b[1]) / 2.0
                    b[0] = b[1] = mid
                if b[3] < b[2]:
                    mid = (b[2] + b[3]) / 2.0
                    b[2] = b[3] = mid
                outward = (idx in (0, 2) and sign < 0) or (idx in (1, 3) and sign > 0)
                add("counterfactual", "single_boundary_shift", side, f"{sign_name}_{'outward' if outward else 'inward'}", radar_rect_polygon(cx, cy, rx, ry, ax, ay, tuple(b)), delta_m=sign * delta, edge_name=side)
    for delta in [0.15, 0.30]:
        for axis_name in ["range", "azimuth"]:
            for sign in [-1, 1]:
                b = bounds.copy()
                if axis_name == "range":
                    b[0] -= sign * delta / (2 * M_PER_PX)
                    b[1] += sign * delta / (2 * M_PER_PX)
                else:
                    b[2] -= sign * delta / (2 * M_PER_PX)
                    b[3] += sign * delta / (2 * M_PER_PX)
                if b[1] < b[0] or b[3] < b[2]:
                    continue
                add("counterfactual", "scale_resize", axis_name, "resize", radar_rect_polygon(cx, cy, rx, ry, ax, ay, tuple(b)), delta_m=sign * delta, scale_axis=axis_name)
    for deg in [-30, -15, -10, -5, 0, 5, 10, 15, 30, 90]:
        add("counterfactual", "local_region_rotation", "gt_region", "rotate", rotate(base_poly, cx, cy, deg), rotation_deg=deg)

    offsets = [
        ("azimuth_plus_0.60", 0.0, 0.60),
        ("azimuth_minus_0.60", 0.0, -0.60),
        ("azimuth_plus_0.90", 0.0, 0.90),
        ("azimuth_minus_0.90", 0.0, -0.90),
        ("range_plus_0.60", 0.60, 0.0),
        ("range_minus_0.60", -0.60, 0.0),
        ("range_plus_0.90", 0.90, 0.0),
        ("range_minus_0.90", -0.90, 0.0),
        ("azimuth_plus_1.20", 0.0, 1.20),
        ("azimuth_minus_1.20", 0.0, -1.20),
        ("azimuth_plus_1.50", 0.0, 1.50),
        ("azimuth_minus_1.50", 0.0, -1.50),
        ("azimuth_plus_1.80", 0.0, 1.80),
        ("azimuth_minus_1.80", 0.0, -1.80),
        ("azimuth_plus_2.40", 0.0, 2.40),
        ("azimuth_minus_2.40", 0.0, -2.40),
        ("range_plus_1.20", 1.20, 0.0),
        ("range_minus_1.20", -1.20, 0.0),
        ("range_plus_1.50", 1.50, 0.0),
        ("range_minus_1.50", -1.50, 0.0),
        ("range_plus_1.80", 1.80, 0.0),
        ("range_minus_1.80", -1.80, 0.0),
        ("range_plus_2.40", 2.40, 0.0),
        ("range_minus_2.40", -2.40, 0.0),
        ("diag_range_plus_1.20_azimuth_plus_1.20", 1.20, 1.20),
        ("diag_range_plus_1.20_azimuth_minus_1.20", 1.20, -1.20),
        ("diag_range_minus_1.20_azimuth_plus_1.20", -1.20, 1.20),
        ("diag_range_minus_1.20_azimuth_minus_1.20", -1.20, -1.20),
        ("diag_range_plus_1.80_azimuth_plus_1.80", 1.80, 1.80),
        ("diag_range_plus_1.80_azimuth_minus_1.80", 1.80, -1.80),
        ("diag_range_minus_1.80_azimuth_plus_1.80", -1.80, 1.80),
        ("diag_range_minus_1.80_azimuth_minus_1.80", -1.80, -1.80),
        ("azimuth_plus_3.00", 0.0, 3.00),
        ("azimuth_minus_3.00", 0.0, -3.00),
        ("range_plus_3.00", 3.00, 0.0),
        ("range_minus_3.00", -3.00, 0.0),
        ("azimuth_plus_3.60", 0.0, 3.60),
        ("azimuth_minus_3.60", 0.0, -3.60),
        ("range_plus_3.60", 3.60, 0.0),
        ("range_minus_3.60", -3.60, 0.0),
        ("azimuth_plus_4.50", 0.0, 4.50),
        ("azimuth_minus_4.50", 0.0, -4.50),
        ("range_plus_4.50", 4.50, 0.0),
        ("range_minus_4.50", -4.50, 0.0),
        ("azimuth_plus_6.00", 0.0, 6.00),
        ("azimuth_minus_6.00", 0.0, -6.00),
        ("range_plus_6.00", 6.00, 0.0),
        ("range_minus_6.00", -6.00, 0.0),
    ]
    gt_boxes = list(all_gt_boxes_by_frame.get(frame, []))
    response_boxes = list(response_boxes_by_frame.get(frame, []))
    for order, dr, da in offsets:
        cand = translate(base_poly, (dr * rx + da * ax) / M_PER_PX, (dr * ry + da * ay) / M_PER_PX)
        box = box_from_polygon(cand)
        if not all(fan_valid_point(x, y) for x, y in cand):
            continue
        if any(bbox_iou(box, other) > 0 for other in gt_boxes):
            continue
        if any(bbox_iou(box, other) > 0 for other in response_boxes):
            continue
        add("matched_background", "matched_background", "deterministic_offset", "control", cand, shift_r_m=dr, shift_a_m=da, bg_order=order)
        break
    return rows


def build_plan() -> dict[str, list[dict[str, str]]]:
    paired = [r for r in read_rows(INPUTS["paired_annotations"]) if r["scene"] == SCENE]
    matrix = read_rows(INPUTS["response_unit_gt_matrix"])
    mask_rows = {r["pair_id"]: r for r in read_rows(INPUTS["mask_observation_audit"])}
    local_units = read_rows(INPUTS["local_response_units"])
    geom_map = read_rows(INPUTS["s1_r1_independent_geometry_map"])

    ru_to_gid: dict[str, str] = {}
    for row in geom_map:
        for rid in row["member_response_unit_ids"].split(";"):
            if rid:
                ru_to_gid[rid] = row["independent_geometry_id"]

    matrix_by_pair: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in matrix:
        matrix_by_pair[row["gt_pair_id"]].append(row)

    all_gt_boxes_by_frame: dict[str, list[Box]] = defaultdict(list)
    for row in paired:
        all_gt_boxes_by_frame[row["sar_frame"]].append(paired_box(row))
    response_boxes_by_frame: dict[str, list[Box]] = defaultdict(list)
    for row in local_units:
        box = parse_box_text(row.get("conservative_bbox", ""))
        if box:
            response_boxes_by_frame[row["sar_frame"]].append(box)

    manifest_rows: list[dict[str, str]] = []
    gt_rows: list[dict[str, str]] = []
    for row in sorted(paired, key=lambda r: int(float(r["sar_frame"]))):
        pair_id = row["pair_id"]
        gt_instance_id = row["sar_gt_id"]
        mask = mask_rows.get(pair_id, {})
        rows_for_pair = matrix_by_pair.get(pair_id, [])
        positive = [m for m in rows_for_pair if parse_float(m.get("iou"), 0.0) > 0]
        gids = sorted({ru_to_gid.get(m["object_id"], "") for m in positive if ru_to_gid.get(m["object_id"], "")})
        ru_ids = sorted({m["object_id"] for m in positive})
        is_primary = row["pair_confidence"] == "high_confidence_pair" and bool(gids)
        pool = "PRIMARY_EXACT_LINK" if is_primary else "PAIRING_REVIEW_ONLY"
        reason = "high_confidence_pair_with_positive_response_unit_gt_links" if is_primary else "not_primary_exact_link_or_missing_positive_geometry_link"
        box = paired_box(row)
        width_axis = 0.0
        long_axis = width_axis if box.w >= box.h else (width_axis + 90.0) % 180.0
        rx, ry, _, _ = unit_vectors(box.cx, box.cy)
        vx, vy = math.cos(math.radians(long_axis)), math.sin(math.radians(long_axis))
        signed = signed_axis_to_ref_deg(vx, vy, rx, ry)
        poly = rect_polygon(box.cx, box.cy, box.w, box.h, width_axis)
        mask_context = ";".join(
            part for part in [
                mask.get("sar_mask_observation_class", ""),
                mask.get("sar_response_truncation_direction", ""),
                mask.get("blocked_reason", ""),
            ] if part
        )
        manifest = {
            "gt_pair_id": pair_id,
            "gt_instance_id": gt_instance_id,
            "scene": SCENE,
            "sar_frame": row["sar_frame"],
            "physical_vehicle_id": mask.get("physical_vehicle_id", ""),
            "evaluation_pool": pool,
            "pool_reason": reason,
            "identity_conflict": "false" if is_primary else "review_required",
            "linked_response_unit_ids": ";".join(ru_ids),
            "linked_independent_geometry_ids": ";".join(gids),
            "linked_independent_geometry_count": str(len(gids)),
            "pair_confidence": row["pair_confidence"],
            "identity_confidence": row["identity_confidence"],
            "mask_class": mask.get("sar_mask_observation_class", ""),
            "mask_context": mask_context,
        }
        manifest_rows.append(manifest)
        gt = {
            "gt_pair_id": pair_id,
            "gt_instance_id": gt_instance_id,
            "sar_frame": row["sar_frame"],
            "source_geometry_type": "axis_aligned_sar_bbox_no_rotation_heading_in_source",
            "final_heading_deg": fmt(width_axis),
            "gt_width_axis_image_deg": fmt(width_axis),
            "gt_long_axis_image_deg": fmt(long_axis),
            "gt_long_axis_to_range_signed_deg": fmt(signed),
            "gt_long_axis_to_range_acute_deg": fmt(abs(signed)),
            "final_w_px": fmt(box.w),
            "final_h_px": fmt(box.h),
            "gt_center_x": fmt(box.cx, 3),
            "gt_center_y": fmt(box.cy, 3),
            "gt_polygon_xy": polygon_text(poly),
            "gt_semantic_note_cn": "GT为SAR可见响应框或MASK偏置响应框；当前源表仅含轴对齐sar_bbox，final_w存储轴取0度，不解释为车辆yaw。",
        }
        gt_rows.append(gt)

    gt_by_pair = {r["gt_pair_id"]: r for r in gt_rows}
    plan_rows: list[dict[str, str]] = []
    for manifest in manifest_rows:
        if manifest["evaluation_pool"] != "PRIMARY_EXACT_LINK":
            continue
        plan_rows.extend(plan_rows_for_instance(manifest, gt_by_pair[manifest["gt_pair_id"]], all_gt_boxes_by_frame, response_boxes_by_frame))

    seal = plan_seal_rows(manifest_rows, gt_rows, plan_rows)
    return {
        "evaluation_instance_manifest": manifest_rows,
        "gt_geometry_semantics": gt_rows,
        "counterfactual_plan": plan_rows,
        "plan_seal": seal,
    }


def plan_seal_rows(manifest: Sequence[Mapping[str, str]], gt_rows: Sequence[Mapping[str, str]], plan_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    primary = [r for r in manifest if r["evaluation_pool"] == "PRIMARY_EXACT_LINK"]
    review = [r for r in manifest if r["evaluation_pool"] == "PAIRING_REVIEW_ONLY"]
    physical = sorted({r["physical_vehicle_id"] for r in primary if r["physical_vehicle_id"]})
    rows = [
        {"seal_key": "plan_stage_intensity_read", "seal_value": "false", "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "plan_stage_s1_r1_measurement_outcomes_read", "seal_value": "false", "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "plan_stage_gt_access_explicit", "seal_value": "true", "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "calibration_status", "seal_value": CALIBRATION_STATUS, "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "max_range_m", "seal_value": fmt(MAX_RANGE_M), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "radial_grid_spacing_m_per_px", "seal_value": fmt(M_PER_PX), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "sar_fan_center", "seal_value": f"{fmt(FAN_CENTER_X)},{fmt(FAN_CENTER_Y)}", "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "primary_exact_link_count", "seal_value": str(len(primary)), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "pairing_review_only_count", "seal_value": str(len(review)), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "gt_instance_count", "seal_value": str(len(primary)), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "physical_vehicle_count", "seal_value": str(len(physical)), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "counterfactual_plan_rows", "seal_value": str(len(plan_rows)), "source_file": "", "sha256": "", "row_count": ""},
        {"seal_key": "plan_source_sha256", "seal_value": sha256(Path(__file__)), "source_file": rel(Path(__file__)), "sha256": sha256(Path(__file__)), "row_count": ""},
    ]
    for key, path in INPUTS.items():
        rows.append({"seal_key": f"input_hash_{key}", "seal_value": "opened" if path.exists() else "missing", "source_file": rel(path), "sha256": sha256(path) if path.exists() else "", "row_count": str(row_count(path)) if path.exists() else ""})
    return rows


def write_outputs(rows_by_key: Mapping[str, Sequence[Mapping[str, Any]]], outputs: Mapping[str, Path]) -> None:
    field_map = {
        "evaluation_instance_manifest": MANIFEST_FIELDS,
        "gt_geometry_semantics": GT_FIELDS,
        "counterfactual_plan": PLAN_FIELDS,
        "plan_seal": SEAL_FIELDS,
    }
    for key, fields in field_map.items():
        write_csv(outputs[key], rows_by_key.get(key, []), fields)


def write_workspace_note(stage: str, status: str) -> None:
    WORKSPACE_TASK_DIR.mkdir(parents=True, exist_ok=True)
    readme = WORKSPACE_TASK_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# OTY2 GM_RM019 S2-A GT region counterfactual identifiability\n\n"
            "- Active repo: D:/profile/research/optical-sar-visual-diagnosis\n"
            "- Interpreter: D:/MINICONDA/envs/py311/python.exe\n"
            "- Boundary: S2-A posthoc GT-region evaluation only; no GT fitting, no final box, no selector/ranking.\n",
            encoding="utf-8",
        )
    WORKSPACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WORKSPACE_LOG.open("a", encoding="utf-8") as f:
        f.write(f"- plan:{stage}: {status}\n")


def output_hashes(outputs: Mapping[str, Path]) -> dict[str, str]:
    return {key: sha256(path) for key, path in outputs.items() if path.exists()}


def plan() -> None:
    rows = build_plan()
    write_outputs(rows, OUTPUTS)
    write_workspace_note("plan", "S2_A_PLAN_READY")
    print("plan: S2_A_PLAN_READY")


def verify_plan() -> None:
    missing = [key for key, path in OUTPUTS.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing plan outputs: " + ", ".join(missing))
    current = output_hashes(OUTPUTS)
    if VERIFY_TMP.exists():
        shutil.rmtree(VERIFY_TMP)
    VERIFY_TMP.mkdir(parents=True, exist_ok=True)
    tmp_outputs = {key: VERIFY_TMP / path.name for key, path in OUTPUTS.items()}
    rows = build_plan()
    write_outputs(rows, tmp_outputs)
    replay = output_hashes(tmp_outputs)
    mismatched = [key for key in current if current[key] != replay.get(key)]
    shutil.rmtree(VERIFY_TMP)
    if mismatched:
        raise RuntimeError("plan replay mismatch: " + ", ".join(mismatched))
    write_workspace_note("verify-plan", "PASS")
    print("verify-plan: PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "verify-plan"])
    args = parser.parse_args()
    if args.command == "plan":
        plan()
    elif args.command == "verify-plan":
        verify_plan()


if __name__ == "__main__":
    main()
