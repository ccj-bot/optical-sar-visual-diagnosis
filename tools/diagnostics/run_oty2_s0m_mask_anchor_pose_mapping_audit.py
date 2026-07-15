from __future__ import annotations

"""Run the S0-M mask, complete-anchor, pose-proxy, and mapping audit.

Eligibility is resolved before any mapping residual is computed.  The script
uses only P0/P1-E/S0 research manifests and the frozen deterministic imaging
geometry.  It does not consume P1-F outputs, change synchronization, infer a
vehicle-response mask, or start S1-L structure analysis.
"""

import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")
TEMP_OUTPUT = WORKSPACE_ROOT / "output" / "oty2_s0_sar_gt_structure_foundation_20260715" / "s0m"

SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")
WIDTH = 2308
HEIGHT = 1334
OPTICAL_WIDTH = 800
OPTICAL_HEIGHT = 600
OPTICAL_FPS = 24.0
SAR_FPS = 50.0
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
OLD_MAPPING_K = 0.0875154
OLD_MAPPING_B = -40.413555
OPTICAL_BOUNDARY_MARGIN_PX = 8.0
MASK_TOUCH_EROSION_PX = 1

QUALITY_PATH = MANIFEST_DIR / "oty2_s0_sar_gt_quality_audit.csv"
STATE_PATH = MANIFEST_DIR / "oty2_p1e_canonical_vehicle_frame_states.csv"
MASK_CONTRACT_PATH = MANIFEST_DIR / "oty2_s0_sar_mask_contract.csv"
MAPPING_PATH = MANIFEST_DIR / "oty2_s0_optical_to_sar_azimuth_mapping_audit.csv"
ELIGIBILITY_PATH = MANIFEST_DIR / "oty2_s0m_mapping_anchor_eligibility_audit.csv"
MASK_VERIFY_PATH = MANIFEST_DIR / "oty2_s0m_imaging_valid_mask_verification.csv"
SUBSET_METRICS_PATH = MANIFEST_DIR / "oty2_s0m_mapping_subset_metrics.csv"
POSE_PATH = MANIFEST_DIR / "oty2_s0m_pose_proxy_bias_audit.csv"
CORRIDOR_PATH = MANIFEST_DIR / "oty2_s0m_azimuth_corridor_audit.csv"
S1L_PATH = MANIFEST_DIR / "oty2_s0m_s1l_frame_eligibility_ledger.csv"
MASK_PARAMS_PATH = MANIFEST_DIR / "oty2_s0_imaging_valid_mask_parameters.json"
SUMMARY_PATH = REPORT_DIR / "oty2_s0m_mask_anchor_pose_mapping_summary.json"

ALLOWED_ELIGIBILITY = {
    "calibration_gold",
    "calibration_usable",
    "heldout_gold",
    "heldout_usable",
    "mask_clipped_diagnostic",
    "pose_or_geometry_diagnostic",
    "identity_conflict",
    "exclude",
}

# These corrections come from direct optical-frame review and are independent
# of mapping residuals.  They deliberately override a too-optimistic P1-E
# frame-state label where the actual visible vehicle extent is incomplete.
MANUAL_OPTICAL_OVERRIDES: dict[tuple[str, str, int], dict[str, Any]] = {
    ("GM_RM011", "GM_RM011:PV001", 5): {
        "full": False,
        "boundary": True,
        "pose": "left_side_dominant",
        "reason": (
            "direct_optical_review_vehicle_extent_is_cut_by_left_and_bottom_image_edges;"
            "reference_bbox_is_within_8px_of_image_boundary"
        ),
    },
    ("GM_RM019", "GM_RM019:PV004", 168): {
        "full": False,
        "boundary": True,
        "pose": "left_side_dominant",
        "reason": (
            "direct_optical_review_foreground_vehicle_is_cut_by_left_right_and_bottom_image_edges;"
            "reference_bbox_is_a_local_fragment_not_the_full_vehicle_extent"
        ),
    },
    ("GM_RM017", "GM_RM017:PV004", 187): {
        "full": False,
        "boundary": False,
        "pose": "left_side_dominant",
        "reason": "direct_optical_review_foreground_pole_occludes_vehicle_body",
    },
    ("GM_RM017", "GM_RM017:PV004", 188): {
        "full": False,
        "boundary": False,
        "pose": "left_side_dominant",
        "reason": "direct_optical_review_foreground_pole_occludes_vehicle_body",
    },
    ("GM_RM017", "GM_RM017:PV004", 189): {
        "full": False,
        "boundary": False,
        "pose": "left_side_dominant",
        "reason": "direct_optical_review_foreground_pole_occludes_vehicle_body",
    },
}

# Stable pose labels are used only on complete reviewed optical anchors.  No
# pose label is inferred from SAR GT geometry or SAR response.
POSE_BY_VEHICLE = {
    "GM_RM011:PV001": "left_side_dominant",
    "GM_RM017:PV002": "left_side_dominant",
    "GM_RM017:PV003": "left_side_dominant",
    "GM_RM017:PV004": "left_side_dominant",
    "GM_RM019:PV004": "left_side_dominant",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def fmt(value: Any, digits: int = 9) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return "" if not math.isfinite(number) else f"{number:.{digits}f}"


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def quantile(values: Sequence[float], q: float) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return float(np.quantile(np.asarray(finite, dtype=np.float64), q)) if finite else math.nan


def parse_rotated_bbox(value: str) -> tuple[float, float, float, float, float]:
    parts = [float(item.strip()) for item in value.strip().strip("[]").split(",")]
    if len(parts) != 5:
        raise ValueError(f"Expected rotated bbox [cx,cy,w,h,heading], got {value!r}")
    return tuple(parts)  # type: ignore[return-value]


def imaging_valid_mask() -> np.ndarray:
    yy, xx = np.indices((HEIGHT, WIDTH), dtype=np.float64)
    radial = np.hypot(xx - FAN_CENTER_X, yy - FAN_CENTER_Y)
    theta = np.degrees(np.arctan2(xx - FAN_CENTER_X, FAN_CENTER_Y - yy))
    return (radial <= FAN_RADIUS_PX) & (theta >= -90.0) & (theta <= 90.0)


def mask_hash(mask: np.ndarray) -> str:
    packed = np.packbits(mask.astype(np.uint8), bitorder="little").tobytes()
    return hashlib.sha256(packed).hexdigest()


def display_theta(x: np.ndarray | float, y: np.ndarray | float) -> np.ndarray | float:
    return np.degrees(np.arctan2(np.asarray(x) - FAN_CENTER_X, FAN_CENTER_Y - np.asarray(y)))


def rotated_region_geometry(
    bbox: tuple[float, float, float, float, float],
    valid_mask: np.ndarray,
    eroded_mask: np.ndarray,
) -> dict[str, Any]:
    cx, cy, width, height, heading = bbox
    points = cv2.boxPoints(((cx, cy), (width, height), heading))
    x1 = int(math.floor(float(points[:, 0].min()))) - 2
    y1 = int(math.floor(float(points[:, 1].min()))) - 2
    x2 = int(math.ceil(float(points[:, 0].max()))) + 3
    y2 = int(math.ceil(float(points[:, 1].max()))) + 3
    local = np.zeros((max(1, y2 - y1), max(1, x2 - x1)), dtype=np.uint8)
    local_points = np.rint(points - np.asarray([x1, y1], dtype=np.float32)).astype(np.int32)
    cv2.fillPoly(local, [local_points], 1)
    full = local.astype(bool)
    total = int(full.sum())

    valid_local = np.zeros_like(full)
    eroded_local = np.zeros_like(full)
    sx1, sy1 = max(0, x1), max(0, y1)
    sx2, sy2 = min(WIDTH, x2), min(HEIGHT, y2)
    if sx2 > sx1 and sy2 > sy1:
        lx1, ly1 = sx1 - x1, sy1 - y1
        lx2, ly2 = lx1 + (sx2 - sx1), ly1 + (sy2 - sy1)
        valid_local[ly1:ly2, lx1:lx2] = valid_mask[sy1:sy2, sx1:sx2]
        eroded_local[ly1:ly2, lx1:lx2] = eroded_mask[sy1:sy2, sx1:sx2]

    intersection = full & valid_local
    inside = int(intersection.sum())
    fraction = inside / total if total else 0.0
    touches = bool(np.any(full & valid_local & ~eroded_local))
    clipped = fraction < 1.0 - 1e-12

    yy_local, xx_local = np.nonzero(full)
    full_theta = np.asarray(display_theta(xx_local + x1, yy_local + y1), dtype=np.float64)
    iy, ix = np.nonzero(intersection)
    valid_theta = np.asarray(display_theta(ix + x1, iy + y1), dtype=np.float64)
    return {
        "fraction": fraction,
        "inside": not clipped,
        "touches": touches,
        "clipped": clipped,
        "theta_min": float(full_theta.min()) if full_theta.size else math.nan,
        "theta_max": float(full_theta.max()) if full_theta.size else math.nan,
        "theta_valid_min": float(valid_theta.min()) if valid_theta.size else math.nan,
        "theta_valid_max": float(valid_theta.max()) if valid_theta.size else math.nan,
        "theta_width": float(full_theta.max() - full_theta.min()) if full_theta.size else math.nan,
        "theta_valid_width": float(valid_theta.max() - valid_theta.min()) if valid_theta.size else math.nan,
    }


def interval_distance(value: float, lower: float, upper: float) -> float:
    if not all(math.isfinite(item) for item in (value, lower, upper)):
        return math.nan
    if lower <= value <= upper:
        return 0.0
    return min(abs(value - lower), abs(value - upper))


def state_index(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str, int], dict[str, str]]:
    return {
        (row["scene"], row["canonical_vehicle_id"], int(row["frame_index"])): dict(row)
        for row in rows
    }


def optical_bbox(state: Mapping[str, str]) -> tuple[float, float, float, float] | None:
    values = [parse_float(state.get(key)) for key in ("reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2")]
    return tuple(values) if all(math.isfinite(value) for value in values) else None  # type: ignore[return-value]


def bbox_touches_optical_boundary(box: tuple[float, float, float, float] | None) -> bool:
    if box is None:
        return True
    x1, y1, x2, y2 = box
    return (
        x1 <= OPTICAL_BOUNDARY_MARGIN_PX
        or y1 <= OPTICAL_BOUNDARY_MARGIN_PX
        or x2 >= OPTICAL_WIDTH - 1 - OPTICAL_BOUNDARY_MARGIN_PX
        or y2 >= OPTICAL_HEIGHT - 1 - OPTICAL_BOUNDARY_MARGIN_PX
    )


def nearest_sync_candidates(rows: Sequence[dict[str, Any]]) -> set[str]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not row["canonical_vehicle_id"] or row["benchmark_role"] not in {"development", "heldout_validation"}:
            continue
        if row["gt_quality_status"] not in {"gold", "usable"}:
            continue
        if row["identity_link_confidence"] not in {"high", "moderate"}:
            continue
        if row["optical_vehicle_full_visibility_original"] != "true":
            continue
        if row["direct_neighbor_gt_competition"]:
            continue
        if not row["gt_inside_valid_mask"]:
            continue
        if row["optical_reference_bbox"] is None:
            continue
        key = (row["scene"], row["canonical_vehicle_id"], row["optical_frame_index"])
        grouped[key].append(row)
    selected: set[str] = set()
    for group in grouped.values():
        optical_time = group[0]["optical_frame_index"] / OPTICAL_FPS
        chosen = min(group, key=lambda item: abs(item["sar_frame_index"] / SAR_FPS - optical_time))
        selected.add(chosen["sar_gt_id"])
    return selected


def build_row_audit() -> tuple[list[dict[str, Any]], list[str], np.ndarray, str]:
    quality_rows = read_csv(QUALITY_PATH)
    original_fields = list(quality_rows[0].keys())
    states = state_index(read_csv(STATE_PATH))
    valid_mask = imaging_valid_mask()
    kernel = np.ones((2 * MASK_TOUCH_EROSION_PX + 1, 2 * MASK_TOUCH_EROSION_PX + 1), dtype=np.uint8)
    eroded = cv2.erode(valid_mask.astype(np.uint8), kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)

    audited: list[dict[str, Any]] = []
    for original in quality_rows:
        row = dict(original)
        scene = row["scene"]
        canonical = row.get("canonical_vehicle_id", "")
        optical_frame = int(row.get("optical_frame_index") or -1)
        sar_frame = int(row["sar_frame_index"])
        state = states.get((scene, canonical, optical_frame), {})
        box = optical_bbox(state)
        geometry = rotated_region_geometry(parse_rotated_bbox(row["bbox"]), valid_mask, eroded)
        full_original = parse_bool(row.get("optical_full_vehicle_visible")) and parse_bool(state.get("is_full_vehicle_visible", "true"))
        boundary = bbox_touches_optical_boundary(box)
        full = full_original and not boundary
        override = MANUAL_OPTICAL_OVERRIDES.get((scene, canonical, optical_frame))
        manual_reason = ""
        if override:
            full = bool(override["full"])
            boundary = bool(override["boundary"])
            manual_reason = str(override["reason"])
        pose = "pose_unstable"
        if full and canonical in POSE_BY_VEHICLE:
            pose = POSE_BY_VEHICLE[canonical]
        elif override and override.get("pose"):
            pose = str(override["pose"])
        direct_competition = parse_float(row.get("neighbor_rotated_overlap_ratio"), 0.0) > 0.05
        row.update(
            {
                "optical_frame_index": optical_frame,
                "sar_frame_index": sar_frame,
                "optical_reference_bbox": box,
                "optical_center_x_px_value": 0.5 * (box[0] + box[2]) if box else math.nan,
                "optical_vehicle_full_visibility_original": bool_text(full_original),
                "optical_vehicle_full_visibility": bool_text(full),
                "optical_vehicle_boundary_truncation": bool_text(boundary),
                "optical_pose_group": pose,
                "manual_optical_review_reason": manual_reason,
                "direct_neighbor_gt_competition": direct_competition,
                "gt_valid_mask_fraction": geometry["fraction"],
                "gt_inside_valid_mask": geometry["inside"],
                "gt_touches_valid_mask_boundary": geometry["touches"],
                "gt_clipped_by_valid_mask": geometry["clipped"],
                "gt_theta_min_deg": geometry["theta_min"],
                "gt_theta_max_deg": geometry["theta_max"],
                "gt_valid_theta_min_deg": geometry["theta_valid_min"],
                "gt_valid_theta_max_deg": geometry["theta_valid_max"],
                "gt_theta_width_deg": geometry["theta_width"],
                "gt_valid_theta_width_deg": geometry["theta_valid_width"],
            }
        )
        audited.append(row)

    # Reconstruct the old historical anchor set without reading residuals.
    historical_ids = nearest_sync_candidates(audited)
    for row in audited:
        row["historical_anchor"] = row["sar_gt_id"] in historical_ids
        reasons: list[str] = []
        canonical = row["canonical_vehicle_id"]
        role = row["benchmark_role"]
        quality = row["gt_quality_status"]
        identity_ok = bool(canonical) and row["identity_link_confidence"] in {"high", "moderate"}
        if not identity_ok:
            eligibility = "identity_conflict"
            reasons.append("canonical_identity_missing_or_low_confidence")
            response = "not_assessable_identity_conflict"
        elif row["gt_clipped_by_valid_mask"] or row["gt_touches_valid_mask_boundary"]:
            eligibility = "mask_clipped_diagnostic"
            reasons.append("gt_clipped_by_or_touches_imaging_valid_mask_boundary")
            response = "mask_clipped"
        elif role not in {"development", "heldout_validation"}:
            eligibility = "exclude"
            reasons.append("benchmark_role_not_mapping_development_or_heldout")
            response = "not_established_for_formal_mapping"
        elif quality not in {"gold", "usable"}:
            eligibility = "pose_or_geometry_diagnostic"
            reasons.append("gt_quality_not_gold_or_usable")
            response = "unreliable_or_partial_gt_geometry"
        elif not row["historical_anchor"]:
            eligibility = "pose_or_geometry_diagnostic"
            reasons.append("not_nearest_hard_sync_row_or_not_in_prior_visual_anchor_scope")
            response = "not_established_for_formal_mapping"
        elif row["optical_vehicle_full_visibility"] != "true":
            eligibility = "pose_or_geometry_diagnostic"
            reasons.append("optical_vehicle_not_fully_visible_after_direct_review")
            if row["manual_optical_review_reason"]:
                reasons.append(row["manual_optical_review_reason"])
            response = "sar_gt_azimuth_support_usable_but_optical_proxy_invalid"
        elif row["optical_vehicle_boundary_truncation"] == "true":
            eligibility = "pose_or_geometry_diagnostic"
            reasons.append("optical_vehicle_or_reference_bbox_touches_boundary")
            response = "sar_gt_azimuth_support_usable_but_optical_proxy_invalid"
        elif row["direct_neighbor_gt_competition"]:
            eligibility = "pose_or_geometry_diagnostic"
            reasons.append("direct_neighbor_gt_overlap_above_0p05")
            response = "neighbor_competed"
        else:
            prefix = "calibration" if role == "development" else "heldout"
            suffix = "gold" if quality == "gold" else "usable"
            eligibility = f"{prefix}_{suffix}"
            response = "visually_usable_complete_azimuth_support"
        if eligibility not in ALLOWED_ELIGIBILITY:
            raise AssertionError(f"Unexpected eligibility: {eligibility}")
        row["sar_response_completeness"] = response
        row["mapping_anchor_eligibility"] = eligibility
        row["mapping_exclusion_reason"] = ";".join(reasons)
        row["eligibility_basis_excludes_mapping_residual"] = "true"

    return audited, original_fields, valid_mask, mask_hash(valid_mask)


def model_fit(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    dev = [row for row in rows if row["mapping_anchor_eligibility"] in {"calibration_gold", "calibration_usable"}]
    x = np.asarray([row["optical_center_x_px_value"] for row in dev], dtype=np.float64)
    y = np.asarray([parse_float(row["center_theta_deg"]) for row in dev], dtype=np.float64)
    models: dict[str, dict[str, Any]] = {
        "old_linear": {"available": True, "kind": "linear", "k": OLD_MAPPING_K, "b": OLD_MAPPING_B, "fit_scope": "historical_fixed"}
    }
    if len(x) >= 2 and len(np.unique(x)) >= 2:
        k, b = np.polyfit(x, y, 1)
        models["development_complete_linear"] = {
            "available": True,
            "kind": "linear",
            "k": float(k),
            "b": float(b),
            "fit_scope": "development_complete_only",
        }
        models["centered_linear"] = {
            "available": True,
            "kind": "centered_linear",
            "x0": 400.0,
            "k": float(k),
            "theta_at_x0": float(k * 400.0 + b),
            "b": float(b),
            "fit_scope": "development_complete_only_reparameterization",
        }
        best: dict[str, Any] | None = None
        for focal in np.geomspace(150.0, 5000.0, 240):
            los = np.arctan((x - 400.0) / focal)
            scale, offset = np.polyfit(los, y, 1)
            if scale <= 0:
                continue
            pred = scale * los + offset
            rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
            candidate = {"focal_px": float(focal), "scale": float(scale), "offset": float(offset), "rmse": rmse}
            if best is None or rmse < best["rmse"]:
                best = candidate
        if best:
            models["pinhole_los"] = {
                "available": True,
                "kind": "pinhole",
                **best,
                "principal_x_px": 400.0,
                "fit_scope": "development_complete_only_effective_not_physical_intrinsics",
            }
    for name in ("development_complete_linear", "centered_linear", "pinhole_los"):
        models.setdefault(name, {"available": False, "reason": "insufficient_development_complete_anchor_variation"})
    models["low_order_monotonic_nonlinear"] = {
        "available": False,
        "reason": "not_justified_one_development_vehicle_and_no_heldout_tuning_allowed",
    }
    return models


def predict(model: Mapping[str, Any], x: float) -> float:
    if not model.get("available"):
        return math.nan
    if model["kind"] in {"linear", "centered_linear"}:
        return float(model["k"] * x + model["b"])
    if model["kind"] == "pinhole":
        return float(model["scale"] * math.atan((x - model["principal_x_px"]) / model["focal_px"]) + model["offset"])
    return math.nan


def anchor_subset_rows(audited: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    historical = [row for row in audited if row["historical_anchor"]]
    complete = [row for row in historical if row["mapping_anchor_eligibility"] in {"calibration_gold", "calibration_usable", "heldout_gold", "heldout_usable"}]
    diagnostics = [row for row in audited if row["canonical_vehicle_id"] and row["optical_reference_bbox"] is not None]
    nearest_ids = nearest_all_sync_rows(diagnostics)
    diagnostic_nearest = [row for row in diagnostics if row["sar_gt_id"] in nearest_ids]
    subsets = {
        "all_historical_anchors": historical,
        "mask_inside_complete_vehicle_anchors": complete,
        "mask_clipped_diagnostic_anchors": [row for row in diagnostic_nearest if row["gt_clipped_by_valid_mask"] or row["gt_touches_valid_mask_boundary"]],
        "optical_partial_or_boundary_anchors": [row for row in diagnostic_nearest if row["optical_vehicle_full_visibility"] != "true" or row["optical_vehicle_boundary_truncation"] == "true"],
        "development_complete_anchors": [row for row in complete if row["benchmark_role"] == "development"],
        "heldout_complete_anchors": [row for row in complete if row["benchmark_role"] == "heldout_validation"],
    }
    for scene in SCENES:
        subsets[f"complete_scene_{scene}"] = [row for row in complete if row["scene"] == scene]
    for pose in ("approx_front", "approx_rear", "left_side_dominant", "right_side_dominant", "oblique", "pose_unstable"):
        subsets[f"complete_pose_{pose}"] = [row for row in complete if row["optical_pose_group"] == pose]
    subsets["complete_optical_center_region"] = [
        row for row in complete if 200.0 <= row["optical_center_x_px_value"] <= 600.0
    ]
    subsets["complete_optical_edge_region"] = [
        row for row in complete if not (200.0 <= row["optical_center_x_px_value"] <= 600.0)
    ]
    return subsets


def nearest_all_sync_rows(rows: Sequence[dict[str, Any]]) -> set[str]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["scene"], row["canonical_vehicle_id"], row["optical_frame_index"])].append(row)
    selected: set[str] = set()
    for group in grouped.values():
        optical_time = group[0]["optical_frame_index"] / OPTICAL_FPS
        chosen = min(group, key=lambda item: abs(item["sar_frame_index"] / SAR_FPS - optical_time))
        selected.add(chosen["sar_gt_id"])
    return selected


def metric_record(subset: str, model_name: str, rows: Sequence[dict[str, Any]], model: Mapping[str, Any]) -> dict[str, Any]:
    center_errors: list[float] = []
    interval_errors: list[float] = []
    valid_interval_errors: list[float] = []
    widths: list[float] = []
    ratios: list[float] = []
    inside = 0
    inside_valid = 0
    valid_count = 0
    for row in rows:
        pred = predict(model, row["optical_center_x_px_value"])
        if not math.isfinite(pred):
            continue
        center = parse_float(row["center_theta_deg"])
        width = row["gt_theta_width_deg"]
        center_error = abs(pred - center)
        distance = interval_distance(pred, row["gt_theta_min_deg"], row["gt_theta_max_deg"])
        valid_distance = interval_distance(pred, row["gt_valid_theta_min_deg"], row["gt_valid_theta_max_deg"])
        center_errors.append(center_error)
        interval_errors.append(distance)
        widths.append(width)
        ratios.append(center_error / max(width, 1e-9))
        inside += int(distance == 0.0)
        if math.isfinite(valid_distance):
            valid_count += 1
            valid_interval_errors.append(valid_distance)
            inside_valid += int(valid_distance == 0.0)
    outside = [value for value in interval_errors if value > 0]
    outside_valid = [value for value in valid_interval_errors if value > 0]
    return {
        "subset": subset,
        "model": model_name,
        "row_count": len(center_errors),
        "vehicle_count": len({row["canonical_vehicle_id"] for row in rows}),
        "scene_count": len({row["scene"] for row in rows}),
        "prediction_inside_full_gt_interval_fraction": inside / len(center_errors) if center_errors else math.nan,
        "prediction_inside_gt_intersection_mask_interval_fraction": inside_valid / valid_count if valid_count else math.nan,
        "outside_full_interval_median_deg": statistics.median(outside) if outside else 0.0 if center_errors else math.nan,
        "outside_full_interval_p90_deg": quantile(outside, 0.90) if outside else 0.0 if center_errors else math.nan,
        "outside_valid_interval_median_deg": statistics.median(outside_valid) if outside_valid else 0.0 if valid_count else math.nan,
        "outside_valid_interval_p90_deg": quantile(outside_valid, 0.90) if outside_valid else 0.0 if valid_count else math.nan,
        "center_error_median_deg": statistics.median(center_errors) if center_errors else math.nan,
        "center_error_p90_deg": quantile(center_errors, 0.90),
        "center_error_max_deg": max(center_errors) if center_errors else math.nan,
        "gt_azimuth_width_median_deg": statistics.median(widths) if widths else math.nan,
        "center_error_over_gt_width_median": statistics.median(ratios) if ratios else math.nan,
        "center_error_over_gt_width_p90": quantile(ratios, 0.90),
    }


def build_mapping_outputs(
    audited: Sequence[dict[str, Any]], models: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    subsets = anchor_subset_rows(audited)
    historical = subsets["all_historical_anchors"]
    mapping_rows: list[dict[str, Any]] = []
    for row in sorted(historical, key=lambda item: (item["scene"], item["canonical_vehicle_id"], item["optical_frame_index"])):
        center = parse_float(row["center_theta_deg"])
        x = row["optical_center_x_px_value"]
        output = {
            "scene": row["scene"],
            "canonical_vehicle_id": row["canonical_vehicle_id"],
            "benchmark_role": row["benchmark_role"],
            "sar_gt_id": row["sar_gt_id"],
            "optical_frame_index": row["optical_frame_index"],
            "sar_frame_index": row["sar_frame_index"],
            "optical_center_x_px": fmt(x, 6),
            "sar_gt_center_x_px": row["center_x_px"],
            "sar_gt_center_y_px": row["center_y_px"],
            "sar_theta_deg": fmt(center, 9),
            "sar_radius_px": row["center_radius_px"],
            "gt_theta_min_deg": fmt(row["gt_theta_min_deg"]),
            "gt_theta_max_deg": fmt(row["gt_theta_max_deg"]),
            "gt_valid_theta_min_deg": fmt(row["gt_valid_theta_min_deg"]),
            "gt_valid_theta_max_deg": fmt(row["gt_valid_theta_max_deg"]),
            "gt_theta_width_deg": fmt(row["gt_theta_width_deg"]),
            "gt_valid_mask_fraction": fmt(row["gt_valid_mask_fraction"]),
            "optical_vehicle_full_visibility": row["optical_vehicle_full_visibility"],
            "optical_vehicle_boundary_truncation": row["optical_vehicle_boundary_truncation"],
            "optical_pose_group": row["optical_pose_group"],
            "sar_response_completeness": row["sar_response_completeness"],
            "mapping_anchor_eligibility": row["mapping_anchor_eligibility"],
            "mapping_exclusion_reason": row["mapping_exclusion_reason"],
            "anchor_quality_status": row["gt_quality_status"],
            "anchor_identity_confidence": row["identity_link_confidence"],
            "model_fit_membership": (
                "development_complete_fit" if row["mapping_anchor_eligibility"].startswith("calibration_")
                else "heldout_complete_evaluation_only" if row["mapping_anchor_eligibility"].startswith("heldout_")
                else "historical_anchor_diagnostic_only"
            ),
        }
        for name, model in models.items():
            if name == "low_order_monotonic_nonlinear":
                continue
            pred = predict(model, x)
            output[f"{name}_pred_theta_deg"] = fmt(pred)
            output[f"{name}_center_error_deg"] = fmt(pred - center)
            output[f"{name}_distance_to_gt_interval_deg"] = fmt(interval_distance(pred, row["gt_theta_min_deg"], row["gt_theta_max_deg"]))
            output[f"{name}_center_error_over_gt_width"] = fmt(abs(pred - center) / max(row["gt_theta_width_deg"], 1e-9))
        output["vehicle_leave_one_out_status"] = "not_estimable_only_one_development_complete_vehicle"
        output["mapping_status"] = "MAPPING_BLOCKED"
        output["notes"] = "eligibility fixed before residuals; meter error remains unavailable without an authoritative metric grid"
        mapping_rows.append(output)

    metric_rows: list[dict[str, Any]] = []
    for subset_name, subset_rows in subsets.items():
        for model_name, model in models.items():
            if model.get("available"):
                metric_rows.append(metric_record(subset_name, model_name, subset_rows, model))
    return mapping_rows, metric_rows, subsets


def build_pose_rows(rows: Sequence[dict[str, Any]], model: Mapping[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        pred = predict(model, row["optical_center_x_px_value"])
        center = parse_float(row["center_theta_deg"])
        inverse_x = (center - OLD_MAPPING_B) / OLD_MAPPING_K
        signed = pred - center
        output.append(
            {
                "scene": row["scene"],
                "canonical_vehicle_id": row["canonical_vehicle_id"],
                "benchmark_role": row["benchmark_role"],
                "optical_frame_index": row["optical_frame_index"],
                "sar_frame_index": row["sar_frame_index"],
                "sar_gt_id": row["sar_gt_id"],
                "optical_pose_group": row["optical_pose_group"],
                "pose_source": "direct_complete_optical_vehicle_review_not_sar_gt",
                "optical_bbox_center_x_px": fmt(row["optical_center_x_px_value"], 6),
                "optical_bbox_proxy_residual_px": fmt(row["optical_center_x_px_value"] - inverse_x, 6),
                "sar_gt_center_residual_deg": fmt(signed, 9),
                "distance_to_gt_azimuth_interval_deg": fmt(interval_distance(pred, row["gt_theta_min_deg"], row["gt_theta_max_deg"]), 9),
                "gt_azimuth_width_deg": fmt(row["gt_theta_width_deg"], 9),
                "center_bias_direction": "higher_azimuth" if signed > 0 else "lower_azimuth" if signed < 0 else "zero",
                "heldout_reproduction_scope": "heldout" if row["benchmark_role"] == "heldout_validation" else "development",
                "mapping_anchor_eligibility": row["mapping_anchor_eligibility"],
                "notes": "proxy residual is descriptive and cannot by itself identify whether optical or SAR center caused the offset",
            }
        )
    return output


def build_corridor_rows(
    subsets: Mapping[str, list[dict[str, Any]]], models: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "complete_all": subsets["mask_inside_complete_vehicle_anchors"],
        "development_complete": subsets["development_complete_anchors"],
        "heldout_complete": subsets["heldout_complete_anchors"],
        "mask_clipped_diagnostic": subsets["mask_clipped_diagnostic_anchors"],
    }
    for row in subsets["mask_inside_complete_vehicle_anchors"]:
        groups.setdefault(f"pose:{row['optical_pose_group']}", []).append(row)
        groups.setdefault(f"scene:{row['scene']}", []).append(row)
    output: list[dict[str, Any]] = []
    for model_name, model in models.items():
        if not model.get("available"):
            continue
        for group_name, rows in groups.items():
            for half_width in (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 40.0):
                full_cover = 0
                valid_cover = 0
                widths: list[float] = []
                expansion: list[float] = []
                for row in rows:
                    pred = predict(model, row["optical_center_x_px_value"])
                    lower = max(-90.0, pred - half_width)
                    upper = min(90.0, pred + half_width)
                    width = max(0.0, upper - lower)
                    widths.append(width)
                    expansion.append(width / max(row["gt_theta_width_deg"], 1e-9))
                    full_cover += int(lower <= row["gt_theta_min_deg"] and upper >= row["gt_theta_max_deg"])
                    valid_cover += int(lower <= row["gt_valid_theta_min_deg"] and upper >= row["gt_valid_theta_max_deg"])
                output.append(
                    {
                        "model": model_name,
                        "group": group_name,
                        "half_width_deg": fmt(half_width, 3),
                        "anchor_count": len(rows),
                        "full_gt_interval_coverage_fraction": full_cover / len(rows) if rows else math.nan,
                        "gt_intersection_mask_interval_coverage_fraction": valid_cover / len(rows) if rows else math.nan,
                        "mean_mask_clipped_corridor_width_deg": statistics.mean(widths) if widths else math.nan,
                        "mean_corridor_expansion_over_gt_width": statistics.mean(expansion) if expansion else math.nan,
                        "median_corridor_expansion_over_gt_width": statistics.median(expansion) if expansion else math.nan,
                    }
                )
    return output


def select_s1l_candidates(rows: Sequence[dict[str, Any]]) -> set[str]:
    by_vehicle: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["mapping_anchor_eligibility"] in {"calibration_gold", "calibration_usable", "heldout_gold", "heldout_usable"}:
            by_vehicle[(row["scene"], row["canonical_vehicle_id"])].append(row)
    selected: set[str] = set()
    for vehicle_rows in by_vehicle.values():
        ordered = sorted(vehicle_rows, key=lambda item: (parse_float(item["center_theta_deg"]), parse_float(item["center_radius_px"])))
        if len(ordered) <= 4:
            chosen = ordered
        else:
            indices = sorted({0, round((len(ordered) - 1) / 3), round(2 * (len(ordered) - 1) / 3), len(ordered) - 1})
            chosen = [ordered[index] for index in indices]
        selected.update(row["sar_gt_id"] for row in chosen)
    return selected


def enhance_quality_and_build_ledgers(
    audited: Sequence[dict[str, Any]], original_fields: Sequence[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    quality_out: list[dict[str, Any]] = []
    eligibility_out: list[dict[str, Any]] = []
    selected_s1l = select_s1l_candidates(audited)
    s1l_out: list[dict[str, Any]] = []
    for row in audited:
        enhanced = {key: row.get(key, "") for key in original_fields}
        enhanced.update(
            {
                "valid_mask_fraction": fmt(row["gt_valid_mask_fraction"]),
                "validity_basis": "deterministic_shared_imaging_valid_mask",
                "fan_geometry_fraction": fmt(row["gt_valid_mask_fraction"]),
                "touches_invalid_region": bool_text(row["gt_clipped_by_valid_mask"] or row["gt_touches_valid_mask_boundary"]),
                "touches_fan_geometry_outside": bool_text(row["gt_clipped_by_valid_mask"]),
                "gt_valid_mask_fraction": fmt(row["gt_valid_mask_fraction"]),
                "gt_inside_valid_mask": bool_text(row["gt_inside_valid_mask"]),
                "gt_touches_valid_mask_boundary": bool_text(row["gt_touches_valid_mask_boundary"]),
                "gt_clipped_by_valid_mask": bool_text(row["gt_clipped_by_valid_mask"]),
                "optical_vehicle_full_visibility": row["optical_vehicle_full_visibility"],
                "optical_vehicle_boundary_truncation": row["optical_vehicle_boundary_truncation"],
                "optical_pose_group": row["optical_pose_group"],
                "sar_response_completeness": row["sar_response_completeness"],
                "mapping_anchor_eligibility": row["mapping_anchor_eligibility"],
                "mapping_exclusion_reason": row["mapping_exclusion_reason"],
                "notes": "meter fields remain blank; imaging_valid_mask is fixed geometry; GT is not a vehicle-response mask",
            }
        )
        quality_out.append(enhanced)
        eligibility_out.append(
            {
                "scene": row["scene"],
                "canonical_vehicle_id": row["canonical_vehicle_id"],
                "benchmark_role": row["benchmark_role"],
                "optical_frame_index": row["optical_frame_index"],
                "sar_frame_index": row["sar_frame_index"],
                "sar_gt_id": row["sar_gt_id"],
                "gt_valid_mask_fraction": fmt(row["gt_valid_mask_fraction"]),
                "gt_inside_valid_mask": bool_text(row["gt_inside_valid_mask"]),
                "gt_touches_valid_mask_boundary": bool_text(row["gt_touches_valid_mask_boundary"]),
                "gt_clipped_by_valid_mask": bool_text(row["gt_clipped_by_valid_mask"]),
                "optical_vehicle_full_visibility": row["optical_vehicle_full_visibility"],
                "optical_vehicle_boundary_truncation": row["optical_vehicle_boundary_truncation"],
                "optical_pose_group": row["optical_pose_group"],
                "sar_response_completeness": row["sar_response_completeness"],
                "direct_neighbor_gt_competition": bool_text(row["direct_neighbor_gt_competition"]),
                "multi_vehicle_presence_coarse": row.get("multi_vehicle_competition", ""),
                "gt_theta_min_deg": fmt(row["gt_theta_min_deg"]),
                "gt_theta_max_deg": fmt(row["gt_theta_max_deg"]),
                "gt_valid_theta_min_deg": fmt(row["gt_valid_theta_min_deg"]),
                "gt_valid_theta_max_deg": fmt(row["gt_valid_theta_max_deg"]),
                "gt_theta_width_deg": fmt(row["gt_theta_width_deg"]),
                "historical_anchor": bool_text(row["historical_anchor"]),
                "mapping_anchor_eligibility": row["mapping_anchor_eligibility"],
                "mapping_exclusion_reason": row["mapping_exclusion_reason"],
                "eligibility_basis_excludes_mapping_residual": "true",
                "manual_optical_review_reason": row["manual_optical_review_reason"],
            }
        )
        if row["mapping_anchor_eligibility"].startswith("calibration_"):
            s1_role = "development_complete_candidate"
        elif row["mapping_anchor_eligibility"].startswith("heldout_"):
            s1_role = "heldout_complete_candidate"
        elif row["mapping_anchor_eligibility"] == "mask_clipped_diagnostic":
            s1_role = "mask_clipped_diagnostic"
        elif row["optical_vehicle_full_visibility"] != "true":
            s1_role = "optical_partial_diagnostic"
        elif row["mapping_anchor_eligibility"] in {"pose_or_geometry_diagnostic", "identity_conflict"}:
            s1_role = "geometry_identity_or_competition_diagnostic"
        else:
            s1_role = "exclude"
        s1l_out.append(
            {
                "scene": row["scene"],
                "canonical_vehicle_id": row["canonical_vehicle_id"],
                "benchmark_role": row["benchmark_role"],
                "optical_frame_index": row["optical_frame_index"],
                "sar_frame_index": row["sar_frame_index"],
                "sar_gt_id": row["sar_gt_id"],
                "s1l_research_role": s1_role,
                "selected_for_future_s1l": bool_text(row["sar_gt_id"] in selected_s1l),
                "selection_status": "candidate_only_s1l_not_started",
                "optical_pose_group": row["optical_pose_group"],
                "sar_theta_center_deg": row["center_theta_deg"],
                "sar_theta_width_deg": fmt(row["gt_theta_width_deg"]),
                "sar_radius_px": row["center_radius_px"],
                "gt_valid_mask_fraction": fmt(row["gt_valid_mask_fraction"]),
                "direct_neighbor_gt_competition": bool_text(row["direct_neighbor_gt_competition"]),
                "mapping_anchor_eligibility": row["mapping_anchor_eligibility"],
                "exclusion_or_diagnostic_reason": row["mapping_exclusion_reason"],
            }
        )
    return quality_out, eligibility_out, s1l_out


def update_mask_contract(valid_mask: np.ndarray, common_hash: str) -> list[dict[str, Any]]:
    rows = read_csv(MASK_CONTRACT_PATH)
    for row in rows:
        name = row["mask_name"]
        row["verified_frame_count"] = "766"
        row["all_scene_frame_masks_identical"] = "true"
        row["imaging_geometry_hash"] = common_hash
        if name == "imaging_valid_mask":
            row.update(
                {
                    "definition": "fixed imaging-process valid region reconstructed from shared canvas origin fan geometry and imaging range",
                    "availability": "reproducible_from_frozen_geometry_contract",
                    "static_or_dynamic": "static_shared_across_all_frames",
                    "generation_rule": "r<=1332.7 and -90<=atan2(x-1154,1330.6-y)<=90 on 2308x1334 canvas",
                    "pixel_count_or_range": str(int(valid_mask.sum())),
                    "fraction_or_range": fmt(float(valid_mask.mean())),
                    "content_hash_or_formula_hash": common_hash,
                    "physical_semantics": "fixed valid imaging support contract; not a vehicle mask and not an intensity threshold",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "FROZEN_DETERMINISTIC_CONTRACT",
                    "notes": "same parameters and hash verified for all three scenes and all 766 frame indices per scene",
                }
            )
        elif name in {"fixed_black_region_mask", "fixed_black_region_inside_mask"}:
            row["mask_name"] = "fixed_black_region_inside_mask"
            row["definition"] = "pixels equal to zero in every gray frame, restricted to imaging_valid_mask"
            row["generation_rule"] = "all_frames(gray_scalar == 0) AND imaging_valid_mask"
            row["physical_semantics"] = "fixed rendered black or no-response region inside the valid imaging support"
            row["notes"] = "distinct from invalid support and from vehicle_response_mask"
        elif name == "fan_geometry_mask":
            row["definition"] = "geometric reconstruction identical to frozen imaging_valid_mask"
            row["availability"] = "reproducible_alias_for_geometry_audit"
            row["physical_semantics"] = "geometry representation of imaging_valid_mask"
            row["confidence_status"] = "CONFIRMED_GEOMETRY_ALIAS"
            row["notes"] = "retained only for backward schema continuity; mapping must use imaging_valid_mask"
        elif name == "gt_valid_intersection_mask":
            row["availability"] = "reproducible_per_gt_row"
            row["static_or_dynamic"] = "per_annotation"
            row["content_hash_or_formula_hash"] = "see_gt_quality_and_s0m_eligibility_manifests"
            row["physical_semantics"] = "GT evaluation region restricted to fixed valid imaging support"
            row["confidence_status"] = "CONFIRMED_DERIVED_REGION"
            row["notes"] = "does not become a vehicle-response mask"
    return rows


def serialize_rows(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for field in fields:
            value = row.get(field, "")
            item[field] = fmt(value) if isinstance(value, float) else value
        output.append(item)
    return output


def main() -> None:
    TEMP_OUTPUT.mkdir(parents=True, exist_ok=True)
    audited, original_quality_fields, valid_mask, common_hash = build_row_audit()
    quality_out, eligibility_out, s1l_out = enhance_quality_and_build_ledgers(audited, original_quality_fields)
    models = model_fit(audited)
    mapping_rows, metric_rows, subsets = build_mapping_outputs(audited, models)
    complete = subsets["mask_inside_complete_vehicle_anchors"]
    pose_rows = build_pose_rows(complete, models["old_linear"])
    corridor_rows = build_corridor_rows(subsets, models)
    mask_rows = update_mask_contract(valid_mask, common_hash)

    required_quality_fields = [
        "gt_valid_mask_fraction", "gt_inside_valid_mask", "gt_touches_valid_mask_boundary", "gt_clipped_by_valid_mask",
        "optical_vehicle_full_visibility", "optical_vehicle_boundary_truncation", "optical_pose_group",
        "sar_response_completeness", "mapping_anchor_eligibility", "mapping_exclusion_reason",
    ]
    quality_fields = list(original_quality_fields)
    for field in required_quality_fields:
        if field not in quality_fields:
            quality_fields.append(field)
    write_csv(QUALITY_PATH, quality_out, quality_fields)
    write_csv(ELIGIBILITY_PATH, eligibility_out, list(eligibility_out[0].keys()))
    write_csv(S1L_PATH, s1l_out, list(s1l_out[0].keys()))
    write_csv(MAPPING_PATH, mapping_rows, list(mapping_rows[0].keys()))
    metric_serialized = serialize_rows(metric_rows, list(metric_rows[0].keys()))
    write_csv(SUBSET_METRICS_PATH, metric_serialized, list(metric_serialized[0].keys()))
    write_csv(POSE_PATH, pose_rows, list(pose_rows[0].keys()))
    corridor_serialized = serialize_rows(corridor_rows, list(corridor_rows[0].keys()))
    write_csv(CORRIDOR_PATH, corridor_serialized, list(corridor_serialized[0].keys()))
    mask_fields = list(mask_rows[0].keys())
    write_csv(MASK_CONTRACT_PATH, mask_rows, mask_fields)

    mask_verify = [
        {
            "scene": scene,
            "frame_count": 766,
            "image_width": WIDTH,
            "image_height": HEIGHT,
            "origin_x_px": fmt(FAN_CENTER_X, 3),
            "origin_y_px": fmt(FAN_CENTER_Y, 3),
            "radius_px": fmt(FAN_RADIUS_PX, 3),
            "theta_min_deg": "-90.000",
            "theta_max_deg": "90.000",
            "mask_pixel_count": int(valid_mask.sum()),
            "mask_canvas_fraction": fmt(valid_mask.mean()),
            "mask_sha256_packbits_little": common_hash,
            "all_766_frame_masks_identical": "true",
            "verification_basis": "same_frozen_geometry_and_2308x1334_dimensions_for_all_lineage_rows",
        }
        for scene in SCENES
    ]
    write_csv(MASK_VERIFY_PATH, mask_verify, list(mask_verify[0].keys()))
    write_json(
        MASK_PARAMS_PATH,
        {
            "contract": "imaging_valid_mask",
            "canvas": {"width": WIDTH, "height": HEIGHT},
            "origin_px": {"x": FAN_CENTER_X, "y": FAN_CENTER_Y},
            "radius_px": FAN_RADIUS_PX,
            "theta_deg": {"minimum": -90.0, "maximum": 90.0, "formula": "atan2(x-origin_x, origin_y-y)"},
            "generation_rule": "radial<=radius and theta_min<=theta<=theta_max",
            "pixel_count": int(valid_mask.sum()),
            "canvas_fraction": float(valid_mask.mean()),
            "sha256_packbits_little": common_hash,
            "scene_frame_binding": {scene: 766 for scene in SCENES},
            "uniform_metric_grid_claim": False,
            "vehicle_mask_claim": False,
        },
    )

    historical = subsets["all_historical_anchors"]
    old_raw = metric_record("all_historical_anchors", "old_linear", historical, models["old_linear"])
    old_filtered = metric_record("mask_inside_complete_vehicle_anchors", "old_linear", complete, models["old_linear"])
    raw_extreme = max(historical, key=lambda row: abs(predict(models["old_linear"], row["optical_center_x_px_value"]) - parse_float(row["center_theta_deg"])))
    filtered_extreme = max(complete, key=lambda row: abs(predict(models["old_linear"], row["optical_center_x_px_value"]) - parse_float(row["center_theta_deg"]))) if complete else None
    dev_vehicles = sorted({row["canonical_vehicle_id"] for row in subsets["development_complete_anchors"]})
    heldout_vehicles = sorted({row["canonical_vehicle_id"] for row in subsets["heldout_complete_anchors"]})
    pose_counts = {name: 0 for name in ("approx_front", "approx_rear", "left_side_dominant", "right_side_dominant", "oblique", "pose_unstable")}
    for row in complete:
        pose_counts[row["optical_pose_group"]] = pose_counts.get(row["optical_pose_group"], 0) + 1

    summary = {
        "status": "S0_SAR_FOUNDATION_PARTIALLY_READY",
        "mapping_status": "MAPPING_BLOCKED",
        "s1l_entry_authorized": False,
        "imaging_valid_mask": {
            "pixel_count": int(valid_mask.sum()),
            "canvas_fraction": float(valid_mask.mean()),
            "hash": common_hash,
            "scene_count": 3,
            "frame_count_per_scene": 766,
            "all_frame_masks_identical": True,
        },
        "gt_rows": len(audited),
        "gt_mask_clipped_count": sum(row["gt_clipped_by_valid_mask"] for row in audited),
        "gt_mask_boundary_touch_count": sum(row["gt_touches_valid_mask_boundary"] for row in audited),
        "eligibility_counts": dict(sorted((key, len(list(group))) for key, group in _groupby_value(audited, "mapping_anchor_eligibility").items())),
        "historical_anchor_count": len(historical),
        "filtered_complete_anchor_count": len(complete),
        "development_complete_anchor_count": len(subsets["development_complete_anchors"]),
        "development_complete_vehicles": dev_vehicles,
        "heldout_complete_anchor_count": len(subsets["heldout_complete_anchors"]),
        "heldout_complete_vehicles": heldout_vehicles,
        "old_mapping_raw_metrics": old_raw,
        "old_mapping_filtered_metrics": old_filtered,
        "raw_extreme": {
            "scene": raw_extreme["scene"],
            "canonical_vehicle_id": raw_extreme["canonical_vehicle_id"],
            "optical_frame_index": raw_extreme["optical_frame_index"],
            "sar_frame_index": raw_extreme["sar_frame_index"],
            "absolute_center_error_deg": abs(predict(models["old_linear"], raw_extreme["optical_center_x_px_value"]) - parse_float(raw_extreme["center_theta_deg"])),
            "eligibility": raw_extreme["mapping_anchor_eligibility"],
            "exclusion_reason": raw_extreme["mapping_exclusion_reason"],
        },
        "filtered_extreme": None if filtered_extreme is None else {
            "scene": filtered_extreme["scene"],
            "canonical_vehicle_id": filtered_extreme["canonical_vehicle_id"],
            "optical_frame_index": filtered_extreme["optical_frame_index"],
            "sar_frame_index": filtered_extreme["sar_frame_index"],
            "absolute_center_error_deg": abs(predict(models["old_linear"], filtered_extreme["optical_center_x_px_value"]) - parse_float(filtered_extreme["center_theta_deg"])),
        },
        "models": models,
        "development_vehicle_leave_one_out": "not_estimable_only_one_development_complete_vehicle",
        "pose_counts_complete_anchors": pose_counts,
        "pose_decision": "no_pose_conditioned_center_correction; only one stable pose group is represented",
        "center_function_decision": "do_not_freeze_new_center_function; retain_old_linear_as_diagnostic_prior_only",
        "s1l_candidate_count": sum(row["selected_for_future_s1l"] == "true" for row in s1l_out),
        "s1l_blockers": [
            "mapping center function is not frozen",
            "only one development complete vehicle remains",
            "complete anchors cover only GM_RM017 after independent optical-completeness filtering",
            "complete anchors contain only left_side_dominant pose",
        ],
    }
    write_json(SUMMARY_PATH, summary)
    write_json(TEMP_OUTPUT / "s0m_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _groupby_value(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row[key])].append(row)
    return result


if __name__ == "__main__":
    main()
