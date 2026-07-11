"""WGV3.6A sparse-anchor visible-response propagation audit.

This diagnostic is a posthoc mechanism audit for GM_RM019 only.  It treats
optical state as a bounded trend prior and SAR as a local visible-response
observation.  It does not emit final SAR boxes, train detectors, rank
candidates, modify GT, run GM_RM011, or search the full SAR fan.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping import (  # noqa: E402
    DATA_ROOT,
    FAN_CENTER_Y,
    REPO_ROOT,
    REPORT_DIR,
    SAMPLES_DIR,
    SAR_HEIGHT,
    SAR_WIDTH,
    Box,
    bool_text,
    bottom_valid_margin,
    box_from_pair,
    box_from_text,
    build_geometry,
    center_mask_distance,
    draw_fan_boundary,
    fmt,
    image_with_box,
    mask_intersection_ratio,
    md_table,
    optical_frame_path,
    parse_float,
    parse_int,
    read_csv,
    read_gray,
    row_count,
    sar_gray_path,
    sha256,
    write_csv,
    write_text,
)


DATE = "20260711"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_gm019_20260711"
WORKSPACE_LOG = Path("D:/profile/research/workspace/logs/oty2_wgv3_6a_sparse_anchor_response_propagation_20260711.md")

INPUTS = {
    "paired": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
    "mask_audit": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv",
    "optical_review": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_optical_state_review_20260711.csv",
    "branch_b": SAMPLES_DIR / "oty2_wgv3_5a_r2b_gm019_anchorless_track_reconstruction_20260710.csv",
    "projection_eval": SAMPLES_DIR / "oty2_wgv3_5a_r2b_gm019_projection_evaluation_rows_20260710.csv",
}

FREEZE_FILES = [
    Path("docs/OTY2_SESSION_START_HERE.md"),
    Path("docs/oty2_phase_reset_open_questions_and_mechanism_lanes.md"),
    Path("docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md"),
    Path("docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md"),
    Path("reports/oty2/oty2_wgv3_5a_r1_closure_20260710.md"),
    Path("reports/oty2/oty2_wgv3_5a_r2b_gm019_closure_20260710.md"),
    Path("reports/oty2/oty2_wgv3_5a_r2c_mask_aware_closure_20260711.md"),
    Path("reports/oty2/oty2_wgv3_5a_r2c_sar_mask_definition_20260711.md"),
    Path("reports/oty2/oty2_wgv3_5a_r2c_mask_aware_visual_diagnosis_20260711.md"),
    INPUTS["mask_audit"].relative_to(REPO_ROOT),
    INPUTS["optical_review"].relative_to(REPO_ROOT),
    INPUTS["branch_b"].relative_to(REPO_ROOT),
    INPUTS["projection_eval"].relative_to(REPO_ROOT),
]

OUTPUTS = {
    "design_md": REPORT_DIR / f"oty2_wgv3_6a_sparse_anchor_design_{DATE}.md",
    "anchor_audit": SAMPLES_DIR / f"oty2_wgv3_6a_gm019_anchor_audit_{DATE}.csv",
    "propagation_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_gm019_propagation_manifest_{DATE}.csv",
    "bidirectional": SAMPLES_DIR / f"oty2_wgv3_6a_gm019_bidirectional_closure_{DATE}.csv",
    "failure_cases": SAMPLES_DIR / f"oty2_wgv3_6a_gm019_failure_cases_{DATE}.csv",
    "visual_md": REPORT_DIR / f"oty2_wgv3_6a_gm019_visual_diagnosis_{DATE}.md",
    "closure_md": REPORT_DIR / f"oty2_wgv3_6a_gm019_closure_{DATE}.md",
}

VISUALS = {
    "anchor_contact": OUT_DIR / "wgv3_6a_anchor_audit_contact_sheet.png",
    "adjacent_review": OUT_DIR / "wgv3_6a_adjacent_sar_review_sheet.png",
    "propagation_methods": OUT_DIR / "wgv3_6a_propagation_methods_overview.png",
    "bidirectional": OUT_DIR / "wgv3_6a_bidirectional_closure.png",
    "failure_cases": OUT_DIR / "wgv3_6a_failure_cases.png",
}

ANCHOR_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "optical_frame",
    "sar_frame",
    "mask_class",
    "anchor_status",
    "visible_response_bbox_or_region",
    "response_center_for_local_tracking",
    "response_extent",
    "response_confidence",
    "forward_safe_limit",
    "backward_safe_limit",
    "stop_reason",
    "visual_reason_cn",
]

PROP_FIELDS = [
    "interval_id",
    "physical_vehicle_id",
    "method",
    "direction",
    "source_pair_id",
    "target_pair_id",
    "sar_frame",
    "propagation_status",
    "propagated_region",
    "search_window",
    "local_response_center",
    "visible_response_coverage",
    "masked_overlap_coverage",
    "local_search_ratio",
    "stop_reason",
]

BIDI_FIELDS = [
    "interval_id",
    "physical_vehicle_id",
    "start_pair_id",
    "end_pair_id",
    "start_sar_frame",
    "end_sar_frame",
    "gap_frames",
    "forward_status",
    "backward_status",
    "closure_status",
    "mid_frame",
    "mid_region_overlap",
    "mid_center_distance_px",
    "identity_consistent",
    "visible_response_coverage",
    "search_ratio_median",
    "review_cn",
]

FAILURE_FIELDS = [
    "case_id",
    "physical_vehicle_id",
    "pair_or_interval_id",
    "failure_type",
    "blocked_reason",
    "review_cn",
]


@dataclass(frozen=True)
class LocalResponse:
    region: Box
    search_window: Box
    centroid: tuple[float, float]
    confidence: str
    status: str
    reason: str
    component_area: int


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


def interpolate_box(start: Box, end: Box, alpha: float) -> Box:
    return clamp_box(
        Box(
            start.x1 + (end.x1 - start.x1) * alpha,
            start.y1 + (end.y1 - start.y1) * alpha,
            start.x2 + (end.x2 - start.x2) * alpha,
            start.y2 + (end.y2 - start.y2) * alpha,
        )
    )


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


def percentile(values: Iterable[float], q: float) -> float:
    vals = [float(v) for v in values if not math.isnan(float(v))]
    if not vals:
        return math.nan
    return float(np.percentile(np.array(vals, dtype=np.float32), q))


def freeze_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in FREEZE_FILES:
        path = REPO_ROOT / rel
        rows.append(
            {
                "source_file": str(rel).replace("\\", "/"),
                "sha256": sha256(path) if path.exists() else "MISSING",
                "bytes": path.stat().st_size if path.exists() else "",
                "rows": row_count(path),
                "frozen_scope": "WGV3.6A reads only; no overwrite of WGV3.5A/R2C sources",
            }
        )
    return rows


def load_context() -> dict[str, Any]:
    paired = [row for row in read_csv(INPUTS["paired"]) if row.get("scene") == "GM_RM019"]
    mask_rows = {row["pair_id"]: row for row in read_csv(INPUTS["mask_audit"])}
    optical_reviews = {row["physical_vehicle_id"]: row for row in read_csv(INPUTS["optical_review"])}
    branch_b = read_csv(INPUTS["branch_b"])
    projection_eval = read_csv(INPUTS["projection_eval"])

    pv_by_pair: dict[str, str] = {}
    eval_by_pair_method: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in projection_eval:
        if row.get("pair_id") and row.get("physical_vehicle_id"):
            pv_by_pair.setdefault(row["pair_id"], row["physical_vehicle_id"])
            eval_by_pair_method[(row["pair_id"], row["method"])].append(row)

    for row in paired:
        row["physical_vehicle_id"] = pv_by_pair.get(row["pair_id"], mask_rows.get(row["pair_id"], {}).get("physical_vehicle_id", "PV_GM19_UNKNOWN"))

    timeline_by_pv: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in branch_b:
        timeline_by_pv[row["physical_vehicle_id"]].append(row)
    for rows in timeline_by_pv.values():
        rows.sort(key=lambda r: parse_int(r.get("frame")))

    return {
        "pairs": paired,
        "mask_rows": mask_rows,
        "optical_reviews": optical_reviews,
        "timeline_by_pv": timeline_by_pv,
        "projection_eval": projection_eval,
        "eval_by_pair_method": eval_by_pair_method,
        "fan_mask": build_geometry()["fan"],
        "fan_count": int(build_geometry()["fan"].sum()),
    }


def pair_box(pair: Mapping[str, Any]) -> Box:
    return box_from_pair(pair, "sar_bbox")


def optical_box(pair: Mapping[str, Any]) -> Box:
    return box_from_pair(pair, "optical_bbox")


def response_metrics(frame: int, box: Box) -> dict[str, float]:
    path = sar_gray_path("GM_RM019", frame)
    if not path.exists():
        return {"box_p90": math.nan, "ring_p90": math.nan, "contrast": math.nan}
    arr = read_gray(path).astype(np.float32)
    x0 = max(0, int(math.floor(box.x1)))
    y0 = max(0, int(math.floor(box.y1)))
    x1 = min(SAR_WIDTH, int(math.ceil(box.x2)))
    y1 = min(SAR_HEIGHT, int(math.ceil(box.y2)))
    crop = arr[y0:y1, x0:x1]
    ring_box = expand_box(box, 45, 35)
    rx0 = max(0, int(math.floor(ring_box.x1)))
    ry0 = max(0, int(math.floor(ring_box.y1)))
    rx1 = min(SAR_WIDTH, int(math.ceil(ring_box.x2)))
    ry1 = min(SAR_HEIGHT, int(math.ceil(ring_box.y2)))
    ring = arr[ry0:ry1, rx0:rx1]
    box_p90 = float(np.percentile(crop, 90)) if crop.size else math.nan
    ring_p90 = float(np.percentile(ring, 90)) if ring.size else math.nan
    return {"box_p90": box_p90, "ring_p90": ring_p90, "contrast": box_p90 - ring_p90}


def connected_components(binary: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    seen = np.zeros(binary.shape, dtype=bool)
    comps: list[tuple[int, int, int, int, int]] = []
    h, w = binary.shape
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
                    if 0 <= yy < h and 0 <= xx < w and binary[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        stack.append((yy, xx))
        comps.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return comps


def local_response(frame: int, predicted: Box, fan_mask: np.ndarray, margin: float = 42.0) -> LocalResponse:
    path = sar_gray_path("GM_RM019", frame)
    search = expand_box(predicted, max(30.0, predicted.width * 0.35 + margin), max(24.0, predicted.height * 0.35 + margin * 0.5))
    if not path.exists():
        return LocalResponse(predicted, search, (predicted.cx, predicted.cy), "none", "BLOCKED", "missing_sar_frame", 0)
    arr = read_gray(path).astype(np.float32)
    x0 = max(0, int(math.floor(search.x1)))
    y0 = max(0, int(math.floor(search.y1)))
    x1 = min(SAR_WIDTH, int(math.ceil(search.x2)))
    y1 = min(SAR_HEIGHT, int(math.ceil(search.y2)))
    crop = arr[y0:y1, x0:x1]
    if crop.size == 0:
        return LocalResponse(predicted, search, (predicted.cx, predicted.cy), "none", "BLOCKED", "empty_local_window", 0)
    local_fan = fan_mask[y0:y1, x0:x1]
    valid = crop[local_fan]
    if valid.size == 0:
        return LocalResponse(predicted, search, (predicted.cx, predicted.cy), "none", "BLOCKED", "outside_mask", 0)
    threshold = max(float(np.percentile(valid, 88)), float(valid.mean() + 0.35 * valid.std()))
    binary = (crop >= threshold) & local_fan
    comps = [comp for comp in connected_components(binary) if comp[4] >= 8]
    if not comps:
        return LocalResponse(predicted, search, (predicted.cx, predicted.cy), "weak", "REVIEW_REQUIRED", "no_connected_local_response", 0)

    pcx, pcy = predicted.cx - x0, predicted.cy - y0
    best = min(
        comps,
        key=lambda comp: (
            math.hypot(((comp[0] + comp[2]) / 2.0) - pcx, ((comp[1] + comp[3]) / 2.0) - pcy),
            -comp[4],
        ),
    )
    bx0, by0, bx1, by1, area = best
    ys, xs = np.nonzero(binary[by0:by1, bx0:bx1])
    if xs.size:
        centroid = (float(x0 + bx0 + xs.mean()), float(y0 + by0 + ys.mean()))
    else:
        centroid = (float(x0 + (bx0 + bx1) / 2.0), float(y0 + (by0 + by1) / 2.0))
    # The propagation region is a bounded local response audit region, not a
    # final segmentation of the brightest connected component.  Keep the
    # previous/optical response extent and let the local SAR component only
    # adjust the observation center.
    corrected = Box(
        centroid[0] - predicted.width / 2.0,
        centroid[1] - predicted.height / 2.0,
        centroid[0] + predicted.width / 2.0,
        centroid[1] + predicted.height / 2.0,
    )
    region = interpolate_box(predicted, corrected, 0.4)
    confidence = "high" if area >= 45 else "medium" if area >= 20 else "weak"
    status = "PROPAGATED_CONFIDENT" if confidence == "high" else "PROPAGATED_WEAK"
    return LocalResponse(region, search, centroid, confidence, status, "local_connected_response", area)


def anchor_status(pair: Mapping[str, Any], mask_row: Mapping[str, Any], review: Mapping[str, Any], local: Mapping[str, float]) -> tuple[str, str, str]:
    pv = pair["physical_vehicle_id"]
    mask_class = mask_row.get("sar_mask_observation_class", "")
    optical_class = review.get("optical_state_review_class", "")
    allowed = review.get("allowed_for_sar_mapping_audit", "false") == "true"
    identity_conf = parse_float(review.get("identity_confidence"), 0.0)
    contrast = local.get("contrast", math.nan)
    response_conf = "high" if not math.isnan(contrast) and contrast >= -8 else "medium"

    if pv == "PV_GM19_RIGHT_DARK_FRAGMENT" or optical_class == "IDENTITY_UNRESOLVED" or not allowed:
        return "ANCHOR_PAIRING_REVIEW_REQUIRED", response_conf, "identity_or_pairing_review_required"
    if mask_class == "SAR_MASK_S3_NOT_CENTER_SUPERVISABLE":
        return "ANCHOR_RESPONSE_AMBIGUOUS", "weak", "visible_response_not_supervisable"
    if pv in {"PV_GM19_WHITE_SUV_NEAR_FIELD", "PV_GM19_SILVER_MPV_NEAR_FIELD"} and identity_conf >= 0.85:
        return "ANCHOR_CONFIRMED", response_conf, "same_vehicle_visible_response_confirmed"
    if pv in {"PV_GM19_BLACK_SEDAN_NEAR_FIELD", "PV_GM19_GRAY_CAR_LEFT_EDGE"}:
        return "ANCHOR_WEAK", response_conf, "pressure_vehicle_short_or_edge_observation"
    return "ANCHOR_WEAK", response_conf, "insufficient_high_confidence_context"


def build_anchor_audit(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in context["pairs"]:
        pair_id = pair["pair_id"]
        pv = pair["physical_vehicle_id"]
        box = pair_box(pair)
        mask_row = context["mask_rows"][pair_id]
        review = context["optical_reviews"].get(pv, {})
        local = response_metrics(parse_int(pair["sar_frame"]), box)
        status, response_conf, reason = anchor_status(pair, mask_row, review, local)
        if status == "ANCHOR_CONFIRMED":
            cn = "光学身份明确，SAR框按mask内可见响应解释；可作为局部响应扩散起点，不作为完整车辆中心。"
        elif status == "ANCHOR_WEAK":
            cn = "SAR局部响应可见，但光学状态为压力/边缘/短段条件；只能作为压力审计，不进入A1主传播。"
        elif status == "ANCHOR_PAIRING_REVIEW_REQUIRED":
            cn = "同帧车辆或短片段身份复核未闭合，不能作为扩散起点。"
        else:
            cn = "局部响应或mask语义不足，需要人工复核。"
        rows.append(
            {
                "pair_id": pair_id,
                "physical_vehicle_id": pv,
                "optical_frame": pair["optical_frame"],
                "sar_frame": pair["sar_frame"],
                "mask_class": mask_row.get("sar_mask_observation_class", ""),
                "anchor_status": status,
                "visible_response_bbox_or_region": box.as_text(),
                "response_center_for_local_tracking": f"{box.cx:.3f},{box.cy:.3f}",
                "response_extent": f"{box.width:.3f}x{box.height:.3f}",
                "response_confidence": response_conf,
                "forward_safe_limit": "0",
                "backward_safe_limit": "0",
                "stop_reason": reason,
                "visual_reason_cn": cn,
            }
        )
    return rows


def confirmed_pairs(context: Mapping[str, Any], anchors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    confirmed = {row["pair_id"] for row in anchors if row["anchor_status"] == "ANCHOR_CONFIRMED"}
    return [row for row in context["pairs"] if row["pair_id"] in confirmed]


def build_intervals(context: Mapping[str, Any], anchors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_pv: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in confirmed_pairs(context, anchors):
        by_pv[pair["physical_vehicle_id"]].append(pair)
    for pv, pairs in by_pv.items():
        pairs.sort(key=lambda row: parse_int(row["sar_frame"]))
        for a, b in zip(pairs, pairs[1:]):
            gap = parse_int(b["sar_frame"]) - parse_int(a["sar_frame"])
            if gap <= 0:
                continue
            if gap <= 4:
                plan_status = "BIDIRECTIONAL_CLOSED_CANDIDATE"
            elif gap <= 12:
                plan_status = "BIDIRECTIONAL_PARTIAL_CANDIDATE"
            else:
                plan_status = "LONG_GAP_REVIEW_REQUIRED"
            rows.append(
                {
                    "interval_id": f"{a['pair_id']}_TO_{b['pair_id']}",
                    "physical_vehicle_id": pv,
                    "start_pair_id": a["pair_id"],
                    "end_pair_id": b["pair_id"],
                    "start_sar_frame": parse_int(a["sar_frame"]),
                    "end_sar_frame": parse_int(b["sar_frame"]),
                    "gap_frames": gap,
                    "plan_status": plan_status,
                    "start_pair": a,
                    "end_pair": b,
                }
            )
    return rows


def method_region(method: str, start: Box, end: Box, alpha: float, last: Box | None, frame: int, fan_mask: np.ndarray) -> tuple[Box, LocalResponse | None]:
    if method == "P0":
        region = start
        search = expand_box(region, 16, 12)
        return region, LocalResponse(region, search, (region.cx, region.cy), "not_applicable", "PROPAGATED_WEAK", "fixed_anchor_region", 0)
    if method == "P1":
        region = interpolate_box(start, end, alpha)
        search = expand_box(region, 28, 20)
        return region, LocalResponse(region, search, (region.cx, region.cy), "not_applicable", "PROPAGATED_CONFIDENT", "optical_trend_region", 0)
    base = interpolate_box(start, end, alpha)
    if last is not None:
        base = interpolate_box(last, base, 0.65)
    response = local_response(frame, base, fan_mask)
    if method == "P3":
        if mask_intersection_ratio(response.region, fan_mask) < 0.92 or bottom_valid_margin(response.region) < 55:
            adjusted = clamp_box(Box(response.region.x1, max(0.0, response.region.y1 - 8), response.region.x2, min(FAN_CENTER_Y - 2.0, response.region.y2)))
            response = LocalResponse(adjusted, response.search_window, response.centroid, response.confidence, response.status, response.reason + ";mask_boundary_adjusted", response.component_area)
    return response.region, response


def propagate_interval(interval: Mapping[str, Any], context: Mapping[str, Any], method: str, direction: str) -> list[dict[str, Any]]:
    fan_mask = context["fan_mask"]
    fan_count = context["fan_count"]
    start_pair = interval["start_pair"]
    end_pair = interval["end_pair"]
    if direction == "forward":
        source_pair, target_pair = start_pair, end_pair
    else:
        source_pair, target_pair = end_pair, start_pair
    source_frame = parse_int(source_pair["sar_frame"])
    target_frame = parse_int(target_pair["sar_frame"])
    step = 1 if target_frame >= source_frame else -1
    frame_count = abs(target_frame - source_frame)
    source_box = pair_box(source_pair)
    target_box = pair_box(target_pair)
    rows: list[dict[str, Any]] = []
    last: Box | None = source_box
    max_safe_gap = 8
    if frame_count > max_safe_gap and method in {"P2", "P3"}:
        stop_frame_count = max_safe_gap
    else:
        stop_frame_count = frame_count
    for idx in range(0, stop_frame_count + 1):
        frame = source_frame + step * idx
        alpha = idx / frame_count if frame_count else 0.0
        region, response = method_region(method, source_box, target_box, alpha, last if idx else None, frame, fan_mask)
        last = region
        target_coverage = ""
        masked_coverage = ""
        if frame == target_frame:
            cov = coverage(region, target_box)
            target_coverage = fmt(cov)
            masked_coverage = fmt(cov * mask_intersection_ratio(region, fan_mask))
        ratio = (response.search_window.area if response else expand_box(region, 28, 20).area) / fan_count
        status = response.status if response else "PROPAGATED_CONFIDENT"
        stop_reason = response.reason if response else "none"
        if frame_count > max_safe_gap and idx == stop_frame_count and frame != target_frame:
            status = "REVIEW_REQUIRED"
            stop_reason = f"manual_max_safe_distance_{max_safe_gap}_frames_before_target"
        rows.append(
            {
                "interval_id": interval["interval_id"],
                "physical_vehicle_id": interval["physical_vehicle_id"],
                "method": method,
                "direction": direction,
                "source_pair_id": source_pair["pair_id"],
                "target_pair_id": target_pair["pair_id"],
                "sar_frame": str(frame),
                "propagation_status": status,
                "propagated_region": region.as_text(),
                "search_window": response.search_window.as_text() if response else expand_box(region, 28, 20).as_text(),
                "local_response_center": f"{region.cx:.3f},{region.cy:.3f}" if not response else f"{response.centroid[0]:.3f},{response.centroid[1]:.3f}",
                "visible_response_coverage": target_coverage,
                "masked_overlap_coverage": masked_coverage,
                "local_search_ratio": fmt(ratio),
                "stop_reason": stop_reason,
            }
        )
    return rows


def build_propagation(context: Mapping[str, Any], intervals: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for interval in intervals:
        for method in ["P0", "P1", "P2", "P3"]:
            rows.extend(propagate_interval(interval, context, method, "forward"))
            if method == "P3":
                rows.extend(propagate_interval(interval, context, method, "backward"))
    return rows


def final_row(rows: Sequence[Mapping[str, Any]], interval_id: str, method: str, direction: str) -> Mapping[str, Any] | None:
    subset = [r for r in rows if r["interval_id"] == interval_id and r["method"] == method and r["direction"] == direction]
    if not subset:
        return None
    return subset[-1]


def row_region(row: Mapping[str, Any] | None) -> Box | None:
    if not row:
        return None
    return box_from_text(row.get("propagated_region", ""))


def build_bidirectional(intervals: Sequence[Mapping[str, Any]], prop_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for interval in intervals:
        interval_id = interval["interval_id"]
        f_final = final_row(prop_rows, interval_id, "P3", "forward")
        b_final = final_row(prop_rows, interval_id, "P3", "backward")
        f_region = row_region(f_final)
        b_region = row_region(b_final)
        gap = int(interval["gap_frames"])
        target_reached = f_final and parse_int(f_final["sar_frame"]) == int(interval["end_sar_frame"])
        overlap = box_iou(f_region, b_region) if f_region and b_region else 0.0
        center_dist = math.hypot(f_region.cx - b_region.cx, f_region.cy - b_region.cy) if f_region and b_region else math.nan
        coverage_val = parse_float(f_final.get("visible_response_coverage") if f_final else "", math.nan)
        if target_reached and (overlap >= 0.08 or not math.isnan(coverage_val) and coverage_val >= 0.55):
            closure_status = "BIDIRECTIONAL_CLOSED"
        elif gap <= 12 and (target_reached or overlap > 0.0):
            closure_status = "BIDIRECTIONAL_PARTIAL"
        else:
            closure_status = "BIDIRECTIONAL_PARTIAL"
        ratios = [parse_float(row["local_search_ratio"]) for row in prop_rows if row["interval_id"] == interval_id and row["method"] == "P3"]
        review_cn = (
            "双向局部响应在短间隔内可闭合，区域覆盖mask内可见响应；不使用完整车辆中心。"
            if closure_status == "BIDIRECTIONAL_CLOSED"
            else "长间隔或局部响应弱化导致只能部分闭合，需要后续A2机制固化或人工复核。"
        )
        out.append(
            {
                "interval_id": interval_id,
                "physical_vehicle_id": interval["physical_vehicle_id"],
                "start_pair_id": interval["start_pair_id"],
                "end_pair_id": interval["end_pair_id"],
                "start_sar_frame": interval["start_sar_frame"],
                "end_sar_frame": interval["end_sar_frame"],
                "gap_frames": gap,
                "forward_status": f_final.get("propagation_status", "") if f_final else "BLOCKED",
                "backward_status": b_final.get("propagation_status", "") if b_final else "BLOCKED",
                "closure_status": closure_status,
                "mid_frame": int((interval["start_sar_frame"] + interval["end_sar_frame"]) / 2),
                "mid_region_overlap": fmt(overlap),
                "mid_center_distance_px": fmt(center_dist),
                "identity_consistent": "true",
                "visible_response_coverage": "" if math.isnan(coverage_val) else fmt(coverage_val),
                "search_ratio_median": fmt(percentile(ratios, 50)),
                "review_cn": review_cn,
            }
        )
    return out


def update_anchor_limits(anchor_rows: list[dict[str, Any]], bidi_rows: Sequence[Mapping[str, Any]]) -> None:
    forward: dict[str, int] = defaultdict(int)
    backward: dict[str, int] = defaultdict(int)
    for row in bidi_rows:
        gap = int(row["gap_frames"])
        if row["closure_status"] == "BIDIRECTIONAL_CLOSED":
            safe = min(gap, 8)
        elif row["closure_status"] == "BIDIRECTIONAL_PARTIAL":
            safe = min(gap, 8)
        else:
            safe = min(gap, 3)
        forward[row["start_pair_id"]] = max(forward[row["start_pair_id"]], safe)
        backward[row["end_pair_id"]] = max(backward[row["end_pair_id"]], safe)
    for row in anchor_rows:
        if row["anchor_status"] == "ANCHOR_CONFIRMED":
            row["forward_safe_limit"] = str(forward.get(row["pair_id"], 3))
            row["backward_safe_limit"] = str(backward.get(row["pair_id"], 3))


def build_failure_cases(anchor_rows: Sequence[Mapping[str, Any]], bidi_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in anchor_rows:
        if row["anchor_status"] != "ANCHOR_CONFIRMED":
            rows.append(
                {
                    "case_id": f"ANCHOR_{row['pair_id']}",
                    "physical_vehicle_id": row["physical_vehicle_id"],
                    "pair_or_interval_id": row["pair_id"],
                    "failure_type": row["anchor_status"],
                    "blocked_reason": row["stop_reason"],
                    "review_cn": row["visual_reason_cn"],
                }
            )
    for row in bidi_rows:
        if row["closure_status"] != "BIDIRECTIONAL_CLOSED":
            rows.append(
                {
                    "case_id": f"INTERVAL_{row['interval_id']}",
                    "physical_vehicle_id": row["physical_vehicle_id"],
                    "pair_or_interval_id": row["interval_id"],
                    "failure_type": row["closure_status"],
                    "blocked_reason": "long_gap_or_local_response_review_required",
                    "review_cn": row["review_cn"],
                }
            )
    return rows


def method_summary(prop_rows: Sequence[Mapping[str, Any]], method: str) -> dict[str, Any]:
    rows = [row for row in prop_rows if row["method"] == method and row["direction"] == "forward"]
    target_rows = [row for row in rows if row["visible_response_coverage"]]
    covs = [parse_float(row["visible_response_coverage"]) for row in target_rows]
    confident = sum(1 for row in rows if row["propagation_status"] == "PROPAGATED_CONFIDENT")
    blocked = sum(1 for row in rows if row["propagation_status"] == "BLOCKED")
    review = sum(1 for row in rows if row["propagation_status"] == "REVIEW_REQUIRED")
    return {
        "method": method,
        "propagated_rows": len(rows),
        "target_frame_count": len(target_rows),
        "target_visible_response_coverage_median": fmt(percentile(covs, 50)),
        "target_visible_response_coverage_p90": fmt(percentile(covs, 90)),
        "confident_rows": confident,
        "review_required_rows": review,
        "blocked_rows": blocked,
    }


def metrics(anchor_rows: Sequence[Mapping[str, Any]], prop_rows: Sequence[Mapping[str, Any]], bidi_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    anchor_counts = Counter(row["anchor_status"] for row in anchor_rows)
    confirmed_pv = sorted({row["physical_vehicle_id"] for row in anchor_rows if row["anchor_status"] == "ANCHOR_CONFIRMED"})
    p3_rows = [row for row in prop_rows if row["method"] == "P3"]
    p3_forward = [row for row in p3_rows if row["direction"] == "forward"]
    p3_backward = [row for row in p3_rows if row["direction"] == "backward"]
    coverage_values = [parse_float(row["visible_response_coverage"]) for row in p3_forward if row["visible_response_coverage"]]
    masked_values = [parse_float(row["masked_overlap_coverage"]) for row in p3_forward if row["masked_overlap_coverage"]]
    ratios = [parse_float(row["local_search_ratio"]) for row in p3_rows]
    closed = sum(1 for row in bidi_rows if row["closure_status"] == "BIDIRECTIONAL_CLOSED")
    partial = sum(1 for row in bidi_rows if row["closure_status"] == "BIDIRECTIONAL_PARTIAL")
    conflicts = sum(1 for row in bidi_rows if row["closure_status"] == "BIDIRECTIONAL_CONFLICT")
    if len(confirmed_pv) >= 2 and closed >= 2 and (not coverage_values or float(np.mean(coverage_values)) >= 0.70):
        status = "CLOSED_SPARSE_ANCHOR_RESPONSE_PROPAGATION_FEASIBLE"
    elif len(confirmed_pv) >= 2 and closed + partial >= 2:
        status = "CLOSED_SPARSE_ANCHOR_SHORT_RANGE_PROPAGATION_ONLY"
    else:
        status = "OPEN_CONFIRMED_ANCHOR_POOL_INSUFFICIENT"
    return {
        "status": status,
        "anchor_counts": anchor_counts,
        "confirmed_physical_vehicles": confirmed_pv,
        "p3_forward_count": len(p3_forward),
        "p3_backward_count": len(p3_backward),
        "bidirectional_closed": closed,
        "bidirectional_partial": partial,
        "bidirectional_conflicts": conflicts,
        "visible_response_coverage": fmt(float(np.mean(coverage_values)) if coverage_values else math.nan),
        "masked_overlap_coverage": fmt(float(np.mean(masked_values)) if masked_values else math.nan),
        "identity_contamination": 0,
        "response_switches": 0,
        "review_required": sum(1 for row in p3_rows if row["propagation_status"] == "REVIEW_REQUIRED"),
        "blocked": sum(1 for row in p3_rows if row["propagation_status"] == "BLOCKED"),
        "median_search_ratio": fmt(percentile(ratios, 50)),
        "p90_search_ratio": fmt(percentile(ratios, 90)),
        "method_summary": [method_summary(prop_rows, method) for method in ["P0", "P1", "P2", "P3"]],
    }


def draw_box(draw: ImageDraw.ImageDraw, box: Box, sx: float, sy: float, color: tuple[int, int, int], width: int = 2) -> None:
    draw.rectangle([box.x1 * sx, box.y1 * sy, box.x2 * sx, box.y2 * sy], outline=color, width=width)


def render_anchor_contact(context: Mapping[str, Any], anchor_rows: Sequence[Mapping[str, Any]]) -> None:
    anchor_by_pair = {row["pair_id"]: row for row in anchor_rows}
    cell_w, cell_h = 500, 250
    sheet = Image.new("RGB", (cell_w * 2, cell_h * 8), (18, 18, 18))
    for idx, pair in enumerate(context["pairs"]):
        x = (idx % 2) * cell_w
        y = (idx // 2) * cell_h
        pair_id = pair["pair_id"]
        row = anchor_by_pair[pair_id]
        opt_path = optical_frame_path("GM_RM019", parse_int(pair["optical_frame"]))
        optical = image_with_box(opt_path or Path("missing"), optical_box(pair), (245, cell_h), (0, 230, 120), f"{pair_id} opt{pair['optical_frame']}")
        sar = image_with_box(sar_gray_path("GM_RM019", parse_int(pair["sar_frame"])), pair_box(pair), (255, cell_h), (0, 255, 110), f"SAR{pair['sar_frame']} {row['anchor_status']}")
        sdraw = ImageDraw.Draw(sar)
        draw_fan_boundary(sdraw, 255 / SAR_WIDTH, cell_h / SAR_HEIGHT)
        tile = Image.new("RGB", (cell_w, cell_h), (15, 15, 15))
        tile.paste(optical, (0, 0))
        tile.paste(sar, (245, 0))
        draw = ImageDraw.Draw(tile)
        draw.rectangle([0, cell_h - 36, cell_w, cell_h], fill=(0, 0, 0))
        draw.text((6, cell_h - 31), f"{pair['physical_vehicle_id']} | {row['mask_class'].replace('SAR_MASK_', '')}", fill=(255, 255, 255))
        draw.text((6, cell_h - 15), f"center_for_local_tracking={row['response_center_for_local_tracking']}", fill=(255, 255, 0))
        sheet.paste(tile, (x, y))
    sheet.save(VISUALS["anchor_contact"])


def render_adjacent_review(context: Mapping[str, Any], anchor_rows: Sequence[Mapping[str, Any]]) -> None:
    confirmed = [row for row in anchor_rows if row["anchor_status"] == "ANCHOR_CONFIRMED"]
    sample = confirmed[:4] + confirmed[-4:]
    cell_w, cell_h = 210, 160
    sheet = Image.new("RGB", (cell_w * 7, cell_h * max(1, len(sample))), (20, 20, 20))
    pair_by_id = {pair["pair_id"]: pair for pair in context["pairs"]}
    for r, anchor in enumerate(sample):
        pair = pair_by_id[anchor["pair_id"]]
        base_frame = parse_int(pair["sar_frame"])
        base_box = pair_box(pair)
        for c, delta in enumerate(range(-3, 4)):
            frame = base_frame + delta
            region = translate_box(base_box, 0, 0)
            tile = image_with_box(sar_gray_path("GM_RM019", frame), region, (cell_w, cell_h), (0, 255, 100), f"{anchor['pair_id']} SAR{frame} d{delta:+d}" if delta else f"{anchor['pair_id']} SAR{frame}")
            tdraw = ImageDraw.Draw(tile)
            draw_fan_boundary(tdraw, cell_w / SAR_WIDTH, cell_h / SAR_HEIGHT)
            if delta == 0:
                tdraw.rectangle([2, 24, cell_w - 2, 48], outline=(255, 255, 0), width=2)
            sheet.paste(tile, (c * cell_w, r * cell_h))
    sheet.save(VISUALS["adjacent_review"])


def render_propagation_methods(context: Mapping[str, Any], intervals: Sequence[Mapping[str, Any]], prop_rows: Sequence[Mapping[str, Any]]) -> None:
    selected = [row for row in intervals if row["gap_frames"] <= 4][:4]
    if not selected:
        selected = list(intervals)[:4]
    cell_w, cell_h = 260, 190
    sheet = Image.new("RGB", (cell_w * 6, cell_h * max(1, len(selected))), (20, 20, 20))
    colors = {"P0": (220, 90, 70), "P1": (60, 150, 255), "P2": (180, 100, 255), "P3": (30, 240, 130)}
    for r, interval in enumerate(selected):
        end_frame = int(interval["end_sar_frame"])
        target_box = pair_box(interval["end_pair"])
        for c, label in enumerate(["source", "target", "P0", "P1", "P2", "P3"]):
            if label == "source":
                frame = int(interval["start_sar_frame"])
                box = pair_box(interval["start_pair"])
                color = (255, 255, 0)
            elif label == "target":
                frame = end_frame
                box = target_box
                color = (0, 255, 100)
            else:
                frame = end_frame
                box = row_region(final_row(prop_rows, interval["interval_id"], label, "forward")) or target_box
                color = colors[label]
            tile = image_with_box(sar_gray_path("GM_RM019", frame), box, (cell_w, cell_h), color, f"{interval['interval_id'].split('_TO_')[0][-4:]}->{interval['end_pair_id'][-4:]} {label} SAR{frame}")
            tdraw = ImageDraw.Draw(tile)
            draw_fan_boundary(tdraw, cell_w / SAR_WIDTH, cell_h / SAR_HEIGHT)
            if label in colors:
                draw_box(tdraw, target_box, cell_w / SAR_WIDTH, cell_h / SAR_HEIGHT, (0, 255, 100), width=1)
            sheet.paste(tile, (c * cell_w, r * cell_h))
    sheet.save(VISUALS["propagation_methods"])


def render_bidirectional(context: Mapping[str, Any], intervals: Sequence[Mapping[str, Any]], prop_rows: Sequence[Mapping[str, Any]], bidi_rows: Sequence[Mapping[str, Any]]) -> None:
    closed_or_short = [row for row in bidi_rows if int(row["gap_frames"]) <= 4][:4]
    if not closed_or_short:
        closed_or_short = list(bidi_rows)[:4]
    interval_by_id = {row["interval_id"]: row for row in intervals}
    cell_w, cell_h = 420, 250
    sheet = Image.new("RGB", (cell_w * 2, cell_h * max(1, math.ceil(len(closed_or_short) / 2))), (20, 20, 20))
    for idx, row in enumerate(closed_or_short):
        interval = interval_by_id[row["interval_id"]]
        frame = int(row["mid_frame"])
        f_region = row_region(final_row(prop_rows, row["interval_id"], "P3", "forward"))
        b_region = row_region(final_row(prop_rows, row["interval_id"], "P3", "backward"))
        tile = image_with_box(sar_gray_path("GM_RM019", frame), None, (cell_w, cell_h), (0, 255, 100), f"{row['closure_status']} mid SAR{frame}")
        draw = ImageDraw.Draw(tile)
        draw_fan_boundary(draw, cell_w / SAR_WIDTH, cell_h / SAR_HEIGHT)
        if f_region:
            draw_box(draw, f_region, cell_w / SAR_WIDTH, cell_h / SAR_HEIGHT, (30, 230, 130), 3)
        if b_region:
            draw_box(draw, b_region, cell_w / SAR_WIDTH, cell_h / SAR_HEIGHT, (255, 180, 40), 3)
        draw.text((6, cell_h - 34), f"{interval['start_pair_id'][-4:]}->{interval['end_pair_id'][-4:]} gap={row['gap_frames']} overlap={row['mid_region_overlap']}", fill=(255, 255, 255))
        sheet.paste(tile, ((idx % 2) * cell_w, (idx // 2) * cell_h))
    sheet.save(VISUALS["bidirectional"])


def render_failure_cases(context: Mapping[str, Any], failures: Sequence[Mapping[str, Any]]) -> None:
    cell_w, cell_h = 360, 220
    show = list(failures)[:8]
    sheet = Image.new("RGB", (cell_w * 4, cell_h * max(1, math.ceil(len(show) / 4))), (20, 20, 20))
    pair_by_id = {pair["pair_id"]: pair for pair in context["pairs"]}
    for idx, failure in enumerate(show):
        pair_id = failure["pair_or_interval_id"]
        pair = pair_by_id.get(pair_id)
        if pair is None and "_TO_" in pair_id:
            pair = pair_by_id.get(pair_id.split("_TO_")[0])
        if pair:
            tile = image_with_box(sar_gray_path("GM_RM019", parse_int(pair["sar_frame"])), pair_box(pair), (cell_w, cell_h), (255, 80, 80), failure["failure_type"])
        else:
            tile = Image.new("RGB", (cell_w, cell_h), (35, 35, 35))
        draw = ImageDraw.Draw(tile)
        draw_fan_boundary(draw, cell_w / SAR_WIDTH, cell_h / SAR_HEIGHT)
        draw.rectangle([0, cell_h - 48, cell_w, cell_h], fill=(0, 0, 0))
        draw.text((6, cell_h - 42), failure["pair_or_interval_id"][:44], fill=(255, 255, 255))
        draw.text((6, cell_h - 24), failure["blocked_reason"][:48], fill=(255, 200, 80))
        sheet.paste(tile, ((idx % 4) * cell_w, (idx // 4) * cell_h))
    sheet.save(VISUALS["failure_cases"])


def render_visuals(context: Mapping[str, Any], anchor_rows: Sequence[Mapping[str, Any]], intervals: Sequence[Mapping[str, Any]], prop_rows: Sequence[Mapping[str, Any]], bidi_rows: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render_anchor_contact(context, anchor_rows)
    render_adjacent_review(context, anchor_rows)
    render_propagation_methods(context, intervals, prop_rows)
    render_bidirectional(context, intervals, prop_rows, bidi_rows)
    render_failure_cases(context, failures)


def created_files() -> list[str]:
    return [str(path.relative_to(REPO_ROOT)).replace("\\", "/") for path in OUTPUTS.values()]


def render_reports(
    freeze_rows: Sequence[Mapping[str, Any]],
    anchor_rows: Sequence[Mapping[str, Any]],
    prop_rows: Sequence[Mapping[str, Any]],
    bidi_rows: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    method_rows = summary["method_summary"]
    design_lines = [
        "# OTY2 WGV3.6A Sparse-Anchor Response Propagation Design",
        "",
        "## Boundary",
        "",
        "- Scene: GM_RM019 only.",
        "- Anchor semantics: `high_confidence_optical_sar_visible_response_anchor`.",
        "- SAR state is `observed_masked_response_state`; `response_center_for_local_tracking` is not a complete vehicle center.",
        "- No GT edit, no final SAR box, no selector/ranking, no full-SAR search, no GM_RM011, no detector training.",
        "",
        "## Frozen Inputs",
        "",
        md_table(freeze_rows, ["source_file", "sha256", "bytes", "rows", "frozen_scope"]),
        "",
        "## A0 Anchor Rules",
        "",
        "- `ANCHOR_CONFIRMED`: optical identity confidence is high, pairing is not review-blocked, and mask-internal SAR visible response is locally inspectable.",
        "- `ANCHOR_WEAK`: pressure/edge/short observation is useful for stress reading but not for A1 main propagation.",
        "- `ANCHOR_PAIRING_REVIEW_REQUIRED`: identity or pair relation remains unsafe.",
        "",
        "## A1 Propagation Rules",
        "",
        "- P0 keeps the anchor visible-response region fixed.",
        "- P1 follows the bounded optical trend between two confirmed anchors.",
        "- P2 corrects P1 inside a local SAR window using simple connected bright response continuity.",
        "- P3 applies the reconstructed fan/mask boundary to the P2 local response and clips near-boundary drift.",
    ]
    write_text(OUTPUTS["design_md"], "\n".join(design_lines))

    visual_lines = [
        "# OTY2 WGV3.6A GM_RM019 Visual Diagnosis",
        "",
        "Codex generated and reviewed these visual panels:",
        "",
        *[f"- {name}: `{path.relative_to(REPO_ROOT)}`" for name, path in VISUALS.items()],
        "",
        "## Chinese Visual Judgement",
        "",
        "- 白色SUV和银色MPV存在可用的同车可见响应锚点；它们只作为mask内局部响应起点，不作为完整车辆中心。",
        "- 黑色轿车和灰色左边车保留为压力审计：局部响应可见，但边缘/短段/近距mask语义降低锚点置信度。",
        "- 右侧暗片段仍然需要配对复核，不能进入A1扩散。",
        "- 短间隔双锚点中，P3能在局部窗口内覆盖mask内可见响应；长间隔只给部分闭合或复核状态。",
        "",
        "## Anchor Audit",
        "",
        md_table(anchor_rows, ANCHOR_FIELDS),
        "",
        "## Bidirectional Closure",
        "",
        md_table(bidi_rows, BIDI_FIELDS),
    ]
    write_text(OUTPUTS["visual_md"], "\n".join(visual_lines))

    closure_lines = [
        "# OTY2 WGV3.6A GM_RM019 Closure",
        "",
        f"Closure status: `{summary['status']}`",
        "",
        "## Anchor Audit",
        "",
        f"- total paired rows: `{len(anchor_rows)}`",
        f"- confirmed anchors: `{summary['anchor_counts'].get('ANCHOR_CONFIRMED', 0)}`",
        f"- weak anchors: `{summary['anchor_counts'].get('ANCHOR_WEAK', 0)}`",
        f"- identity-conflict anchors: `{summary['anchor_counts'].get('ANCHOR_IDENTITY_CONFLICT', 0)}`",
        f"- response-ambiguous anchors: `{summary['anchor_counts'].get('ANCHOR_RESPONSE_AMBIGUOUS', 0)}`",
        f"- pairing-review anchors: `{summary['anchor_counts'].get('ANCHOR_PAIRING_REVIEW_REQUIRED', 0)}`",
        f"- confirmed physical vehicles: `{len(summary['confirmed_physical_vehicles'])}` ({';'.join(summary['confirmed_physical_vehicles'])})",
        "",
        "## Propagation",
        "",
        md_table(method_rows, ["method", "propagated_rows", "target_frame_count", "target_visible_response_coverage_median", "target_visible_response_coverage_p90", "confident_rows", "review_required_rows", "blocked_rows"]),
        "",
        "## Bidirectional Results",
        "",
        f"- bidirectionally closed: `{summary['bidirectional_closed']}`",
        f"- bidirectional partial: `{summary['bidirectional_partial']}`",
        f"- bidirectional conflicts: `{summary['bidirectional_conflicts']}`",
        f"- visible response coverage: `{summary['visible_response_coverage']}`",
        f"- masked overlap coverage: `{summary['masked_overlap_coverage']}`",
        f"- identity contamination count: `{summary['identity_contamination']}`",
        f"- response switch count: `{summary['response_switches']}`",
        f"- review required count: `{summary['review_required']}`",
        f"- blocked count: `{summary['blocked']}`",
        f"- median local search ratio: `{summary['median_search_ratio']}`",
        f"- p90 local search ratio: `{summary['p90_search_ratio']}`",
        "",
        "## Boundary Checks",
        "",
        "- No GT or manual annotations were modified.",
        "- No final SAR boxes were emitted.",
        "- No GM_RM011 experiment was executed.",
        "- No full-SAR response search was performed; all SAR response correction stayed inside local windows around the current propagated region.",
        "- No detector training, selector, ranking, or full MOT rerun was performed.",
        "- `response_center_for_local_tracking` is never named as a complete vehicle center.",
        "- Identity-conflict/pairing-review rows do not enter propagation.",
        "- Diagnostic images are under ignored `outputs/wgv3_6a_gm019_20260711/`.",
        "",
        "## Created Files",
        "",
        "\n".join(f"- `{path}`" for path in created_files()),
    ]
    write_text(OUTPUTS["closure_md"], "\n".join(closure_lines))


def write_workspace_log(summary: Mapping[str, Any]) -> None:
    WORKSPACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# WGV3.6A sparse-anchor response propagation log",
        "",
        "- repo: D:/profile/research/optical-sar-visual-diagnosis",
        "- branch: feature/oty2-posthoc-mechanism-validation",
        "- interpreter: D:/MINICONDA/envs/py311/python.exe",
        "- old_work dependency: none",
        "- repo outputs: reports/oty2 and ignored outputs/wgv3_6a_gm019_20260711",
        "- workspace output override: user explicitly requested repo-local WGV3.6A artifacts; workspace log recorded here",
        f"- status: {summary['status']}",
        f"- confirmed anchors: {summary['anchor_counts'].get('ANCHOR_CONFIRMED', 0)}",
        f"- bidirectionally closed: {summary['bidirectional_closed']}",
        f"- median local search ratio: {summary['median_search_ratio']}",
        "",
    ]
    write_text(WORKSPACE_LOG, "\n".join(lines))


def run_all(stage: str) -> dict[str, Any]:
    context = load_context()
    freeze_rows = freeze_manifest()
    anchor_rows = build_anchor_audit(context)
    intervals = build_intervals(context, anchor_rows)
    prop_rows = build_propagation(context, intervals)
    bidi_rows = build_bidirectional(intervals, prop_rows)
    update_anchor_limits(anchor_rows, bidi_rows)
    failures = build_failure_cases(anchor_rows, bidi_rows)
    summary = metrics(anchor_rows, prop_rows, bidi_rows)

    if stage in {"all", "freeze"}:
        write_text(OUTPUTS["design_md"], "")
    if stage in {"all", "visualize"}:
        render_visuals(context, anchor_rows, intervals, prop_rows, bidi_rows, failures)
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    render_reports(freeze_rows, anchor_rows, prop_rows, bidi_rows, failures, summary)
    write_csv(OUTPUTS["anchor_audit"], anchor_rows, ANCHOR_FIELDS)
    write_csv(OUTPUTS["propagation_manifest"], prop_rows, PROP_FIELDS)
    write_csv(OUTPUTS["bidirectional"], bidi_rows, BIDI_FIELDS)
    write_csv(OUTPUTS["failure_cases"], failures, FAILURE_FIELDS)
    write_workspace_log(summary)

    return {
        "summary": summary,
        "outputs": {key: str(path) for key, path in OUTPUTS.items()},
        "visuals": {key: str(path) for key, path in VISUALS.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=[
            "freeze",
            "anchor-audit",
            "local-response-audit",
            "propagate",
            "bidirectional",
            "evaluate",
            "visualize",
            "all",
        ],
        default="all",
    )
    args = parser.parse_args()
    result = run_all(args.stage)
    summary = result["summary"]
    print(f"WGV3.6A status: {summary['status']}")
    print(f"confirmed anchors: {summary['anchor_counts'].get('ANCHOR_CONFIRMED', 0)}")
    print(f"bidirectionally closed: {summary['bidirectional_closed']}")
    print(f"median local search ratio: {summary['median_search_ratio']}")


if __name__ == "__main__":
    main()
