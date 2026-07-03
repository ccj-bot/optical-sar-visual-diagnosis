"""OTY2 GT-anchored SAR vehicle morphology and support coverage archive.

This diagnostic archives human visual review notes, defines GT-anchored SAR
vehicle morphology hypotheses, audits SAR GT-box energy distributions, and
audits optical-derived support coverage against GT area, GT energy, and GT
morphology proxy coverage. It is posthoc mechanism work only: no annotation
proposal, final box, selector/ranking, training, threshold tuning, best weight,
or identity-truth claim is produced.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from run_oty2_range_narrowing_peak_competition_audit import (
    EXPECTED_LEDGER,
    FAN_CENTER_X,
    FAN_CENTER_Y,
    REPORT_DIR,
    WORKSPACE_LOG_DIR,
    compact_counts,
    fmt,
    latest_path,
    read_csv,
    safe_float,
    write_csv,
    write_json,
)
from run_oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion import (
    PAIRED_POOL,
    box_available,
    gt_box_from_accounting,
    gt_box_from_correspondence,
    pool_type,
    rotated_corners,
    sanitize,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
VISUAL_DIR = REPORT_DIR / "visual_exemplars"
STATE_MODE = "state_conditioned_range_band"

BOUNDARY_FLAGS = {
    "human_visual_review_notes_archived": True,
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "gt_anchored_morphology_audit_entered": True,
    "support_coverage_hypothesis_audit_entered": True,
    "support_overlay_panels_generated": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "complete_object_80_85_hypothesis_written_as_runtime_rule": False,
    "state_conditioned_topk_written_as_runtime_rule": False,
    "annotation_proposal_entered": False,
    "final_candidate_box_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "best_weight_selected": False,
    "identity_truth_claimed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
    "matlab_zip_or_any_zip_committed": False,
}

MANUAL_NOTE_FIELDS = [
    "panel_id",
    "case_id",
    "scene",
    "sar_frame",
    "object_hypothesis_id",
    "gt_id",
    "prior_card_category",
    "human_observation_original",
    "morphology_insight",
    "mechanism_keywords",
    "association_or_support_note",
    "boundary_note",
]

MORPHOLOGY_PRIMITIVE_FIELDS = [
    "primitive_name",
    "human_interpretation",
    "possible_physical_meaning",
    "visible_in_panels",
    "expected_energy_distribution",
    "expected_temporal_behavior",
    "confounders",
    "runtime_safe_observable",
    "posthoc_only_fields",
    "next_computation_proxy",
]

ENERGY_FIELDS = [
    "gt_id",
    "scene",
    "sar_frame",
    "pool_type",
    "image_available",
    "gt_box_available",
    "gt_crop_energy_available",
    "near_side_direction_available",
    "near_side_proxy_method",
    "gt_energy_total",
    "gt_energy_mean",
    "gt_energy_peak",
    "near_side_energy_proxy",
    "far_side_energy_proxy",
    "near_far_asymmetry_proxy",
    "lower_side_strip_energy_proxy",
    "upper_side_strip_energy_proxy",
    "left_side_energy_proxy",
    "right_side_energy_proxy",
    "corner_hotspot_proxy",
    "edge_strip_continuity_proxy",
    "internal_energy_entropy_proxy",
    "dominant_energy_region",
    "boundary_affected",
    "valid_for_morphology_reference",
    "notes",
]

SUPPORT_FIELDS = [
    "case_id",
    "scene",
    "object_hypothesis_id",
    "sar_frame",
    "optical_state",
    "optical_complete_visible",
    "truncation_or_occlusion_state",
    "support_boundary_available",
    "support_source",
    "gt_area_coverage_ratio",
    "gt_energy_coverage_ratio",
    "morphology_primitive_coverage_proxy",
    "support_covers_most_gt_area",
    "support_covers_most_gt_energy",
    "support_covers_most_vehicle_structure",
    "support_too_broad_for_unique_association",
    "main_failure_reason",
    "posthoc_validation_only_fields",
    "notes",
]

COMPLETE_POOL_FIELDS = [
    "case_id",
    "scene",
    "object_hypothesis_id",
    "optical_state",
    "why_high_confidence",
    "expected_support_behavior",
    "gt_area_coverage_ratio",
    "gt_energy_coverage_ratio",
    "morphology_coverage_proxy",
    "whether_80_85_hypothesis_supported",
    "failure_reason",
    "notes",
]

COMPENSATION_FIELDS = [
    "case_id",
    "scene",
    "object_hypothesis_id",
    "optical_state",
    "incompleteness_type",
    "why_single_frame_support_may_fail",
    "expected_sar_structure_missing_or_shifted",
    "temporal_compensation_needed",
    "state_compensation_needed",
    "possible_sar_morphology_cue",
    "posthoc_sar_observation",
    "allowed_use",
    "not_allowed_use",
]

AVAILABILITY_FIELDS = [
    "case_id",
    "scene",
    "sar_frame",
    "object_hypothesis_id",
    "gt_id",
    "image_available",
    "gt_box_available",
    "support_boundary_available",
    "support_source",
    "support_mask_path_available",
    "support_render_method",
    "panel_generated",
    "panel_path",
    "reason",
]


def bool_text(value: bool | None) -> str:
    if value is None:
        return "uncertain"
    return "yes" if value else "no"


def is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def parse_center(text: str) -> tuple[float, float] | None:
    parts = [safe_float(part) for part in str(text or "").split(",")]
    if len(parts) >= 2 and parts[0] is not None and parts[1] is not None:
        return float(parts[0]), float(parts[1])
    return None


def case_id_from_corr(row: Mapping[str, Any]) -> str:
    scene = sanitize(row.get("scene", "scene"))
    opt = sanitize(row.get("optical_frame", "opt"))
    sar = sanitize(row.get("sar_frame", "sar"))
    obj = sanitize(row.get("object_hypothesis_id", "obj"))
    return f"PAIR_{scene}_o{opt}_s{sar}_{obj}"


def case_id_from_gt(row: Mapping[str, Any]) -> str:
    scene = sanitize(row.get("scene", "scene"))
    sar = sanitize(row.get("sar_frame", "sar"))
    gt_id = sanitize(row.get("sar_gt_id", row.get("gt_id", "gt")))
    return f"GTREF_{scene}_s{sar}_{gt_id}"


def fan_radius(x: np.ndarray | float, y: np.ndarray | float) -> np.ndarray | float:
    return np.hypot(np.asarray(x) - FAN_CENTER_X, np.asarray(y) - FAN_CENTER_Y)


def fan_azimuth(x: np.ndarray | float, y: np.ndarray | float) -> np.ndarray | float:
    return np.degrees(np.arctan2(np.asarray(x) - FAN_CENTER_X, FAN_CENTER_Y - np.asarray(y)))


def point_from_fan(radius: float, azimuth_deg: float) -> tuple[float, float]:
    angle = math.radians(azimuth_deg)
    return FAN_CENTER_X + radius * math.sin(angle), FAN_CENTER_Y - radius * math.cos(angle)


def angle_in_interval(values: np.ndarray, start: float, end: float) -> np.ndarray:
    wrapped = ((values + 180.0) % 360.0) - 180.0
    s = ((start + 180.0) % 360.0) - 180.0
    e = ((end + 180.0) % 360.0) - 180.0
    if s <= e:
        return (wrapped >= s) & (wrapped <= e)
    return (wrapped >= s) | (wrapped <= e)


def read_image_gray(path_text: str) -> np.ndarray | None:
    path = Path(str(path_text or ""))
    if not path.exists():
        return None
    try:
        with Image.open(path) as image:
            return np.asarray(image.convert("L"), dtype=np.float32)
    except OSError:
        return None


def read_image_rgb(path_text: str) -> Image.Image | None:
    path = Path(str(path_text or ""))
    if not path.exists():
        return None
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except OSError:
        return None


def gt_pixel_table(arr: np.ndarray, box: Mapping[str, float]) -> dict[str, np.ndarray] | None:
    if arr is None or not box_available(box):
        return None
    corners = rotated_corners(box)
    x0 = max(0, int(math.floor(min(x for x, _ in corners))) - 2)
    x1 = min(arr.shape[1], int(math.ceil(max(x for x, _ in corners))) + 2)
    y0 = max(0, int(math.floor(min(y for _, y in corners))) - 2)
    y1 = min(arr.shape[0], int(math.ceil(max(y for _, y in corners))) + 2)
    if x1 <= x0 or y1 <= y0:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    cx = float(box["cx"])
    cy = float(box["cy"])
    w = float(box["w"])
    h = float(box["h"])
    angle = math.radians(float(box.get("heading", 0.0)))
    ca = math.cos(angle)
    sa = math.sin(angle)
    dx = xx + 0.5 - cx
    dy = yy + 0.5 - cy
    local_x = ca * dx + sa * dy
    local_y = -sa * dx + ca * dy
    mask = (np.abs(local_x) <= w / 2.0) & (np.abs(local_y) <= h / 2.0)
    if not bool(mask.any()):
        return None
    return {
        "x": (xx + 0.5)[mask],
        "y": (yy + 0.5)[mask],
        "local_x": local_x[mask],
        "local_y": local_y[mask],
        "values": arr[y0:y1, x0:x1][mask],
        "w": np.asarray([w], dtype=np.float32),
        "h": np.asarray([h], dtype=np.float32),
    }


def mean_or_blank(values: np.ndarray) -> str:
    if values.size == 0:
        return ""
    return fmt(float(values.mean()), 4)


def energy_ratio(values: np.ndarray, mask: np.ndarray) -> float | None:
    if values.size == 0 or not bool(mask.any()):
        return None
    denom = float(values.sum())
    if denom <= 0:
        return None
    return float(values[mask].sum() / denom)


def normalized_entropy(values: np.ndarray) -> float | None:
    if values.size <= 1:
        return None
    shifted = values - float(values.min())
    weights = shifted + 1e-6
    total = float(weights.sum())
    if total <= 0:
        return None
    p = weights / total
    entropy = float(-(p * np.log(p)).sum() / math.log(len(p)))
    return entropy


def edge_continuity_proxy(table: Mapping[str, np.ndarray]) -> float | None:
    values = table["values"]
    if values.size < 16:
        return None
    lx = table["local_x"]
    ly = table["local_y"]
    w = float(table["w"][0])
    h = float(table["h"][0])
    edge_mask = (np.abs(ly) >= 0.35 * h) | (np.abs(lx) >= 0.35 * w)
    if not bool(edge_mask.any()):
        return None
    threshold = float(np.quantile(values, 0.75))
    bins = 12
    occupied = 0
    possible = 0
    for axis_name, full_axis in (("x", lx), ("y", ly)):
        axis_values = full_axis[edge_mask]
        if axis_values.size == 0:
            continue
        lo = float(axis_values.min())
        hi = float(axis_values.max())
        if hi <= lo:
            continue
        edges = np.linspace(lo, hi, bins + 1)
        for i in range(bins):
            if axis_name == "x":
                inside = edge_mask & (lx >= edges[i]) & (lx < edges[i + 1])
            else:
                inside = edge_mask & (ly >= edges[i]) & (ly < edges[i + 1])
            if not bool(inside.any()):
                continue
            possible += 1
            if float(values[inside].max()) >= threshold:
                occupied += 1
    if possible == 0:
        return None
    return occupied / possible


def dominant_region(table: Mapping[str, np.ndarray]) -> str:
    values = table["values"]
    lx = table["local_x"]
    ly = table["local_y"]
    w = float(table["w"][0])
    h = float(table["h"][0])
    masks = {
        "lower_side_strip_image_axis_proxy": ly >= 0.25 * h,
        "upper_side_strip_image_axis_proxy": ly <= -0.25 * h,
        "left_side_strip_image_axis_proxy": lx <= -0.25 * w,
        "right_side_strip_image_axis_proxy": lx >= 0.25 * w,
        "interior_body_proxy": (np.abs(lx) < 0.25 * w) & (np.abs(ly) < 0.25 * h),
    }
    scores: dict[str, float] = {}
    for name, mask in masks.items():
        if bool(mask.any()):
            scores[name] = float(values[mask].mean())
    return max(scores, key=scores.get) if scores else "unavailable"


def energy_stats(row: Mapping[str, Any], box: Mapping[str, float]) -> dict[str, Any]:
    image_path = str(row.get("sar_pseudocolor_path", row.get("sar_image_path", "")))
    arr = read_image_gray(image_path)
    pool = pool_type(row) if "match_status" in row else PAIRED_POOL
    gt_id = str(row.get("sar_gt_id", row.get("gt_id", "")))
    base = {
        "gt_id": gt_id,
        "scene": row.get("scene", ""),
        "sar_frame": row.get("sar_frame", ""),
        "pool_type": pool,
        "image_available": "yes" if arr is not None else "no",
        "gt_box_available": "yes" if box_available(box) else "no",
        "gt_crop_energy_available": "no",
        "near_side_direction_available": "no",
        "near_side_proxy_method": "not_computed_physical_near_side_direction_unavailable",
        "gt_energy_total": "",
        "gt_energy_mean": "",
        "gt_energy_peak": "",
        "near_side_energy_proxy": "",
        "far_side_energy_proxy": "",
        "near_far_asymmetry_proxy": "",
        "lower_side_strip_energy_proxy": "",
        "upper_side_strip_energy_proxy": "",
        "left_side_energy_proxy": "",
        "right_side_energy_proxy": "",
        "corner_hotspot_proxy": "",
        "edge_strip_continuity_proxy": "",
        "internal_energy_entropy_proxy": "",
        "dominant_energy_region": "unavailable",
        "boundary_affected": "uncertain",
        "valid_for_morphology_reference": "uncertain",
        "notes": "No physical near/far direction is inferred from display image alone.",
    }
    table = gt_pixel_table(arr, box) if arr is not None else None
    if table is None:
        base["notes"] = "Image or GT polygon unavailable; energy proxy not computed."
        return base
    values = table["values"]
    lx = table["local_x"]
    ly = table["local_y"]
    w = float(table["w"][0])
    h = float(table["h"][0])
    lower = ly >= 0.25 * h
    upper = ly <= -0.25 * h
    left = lx <= -0.25 * w
    right = lx >= 0.25 * w
    corner = (np.abs(lx) >= 0.28 * w) & (np.abs(ly) >= 0.28 * h)
    corner_proxy = None
    if bool(corner.any()) and float(values.mean()) > 0:
        corner_proxy = float(values[corner].max() / max(float(values.mean()), 1e-6))
    continuity = edge_continuity_proxy(table)
    entropy = normalized_entropy(values)
    base.update(
        {
            "gt_crop_energy_available": "yes",
            "gt_energy_total": fmt(float(values.sum()), 3),
            "gt_energy_mean": fmt(float(values.mean()), 4),
            "gt_energy_peak": fmt(float(values.max()), 4),
            "lower_side_strip_energy_proxy": mean_or_blank(values[lower]),
            "upper_side_strip_energy_proxy": mean_or_blank(values[upper]),
            "left_side_energy_proxy": mean_or_blank(values[left]),
            "right_side_energy_proxy": mean_or_blank(values[right]),
            "corner_hotspot_proxy": fmt(corner_proxy, 4),
            "edge_strip_continuity_proxy": fmt(continuity, 4),
            "internal_energy_entropy_proxy": fmt(entropy, 4),
            "dominant_energy_region": dominant_region(table),
            "boundary_affected": "no",
            "valid_for_morphology_reference": "yes" if pool in {PAIRED_POOL, "sar_only", "gm011_blocked"} else "special",
            "notes": "Display-grayscale SAR GT-crop energy proxy; physical near/far side is not inferred automatically.",
        }
    )
    if pool == "dropout_special":
        base["valid_for_morphology_reference"] = "uncertain"
        base["notes"] += " Dropout/no-match row is temporal continuation special pool, not clean morphology."
    return base


def support_mask_for_gt(table: Mapping[str, np.ndarray], support: Mapping[str, Any]) -> np.ndarray | None:
    rmin = safe_float(support.get("support_radius_min_px"))
    rmax = safe_float(support.get("support_radius_max_px"))
    amin = safe_float(support.get("support_azimuth_start_deg"))
    amax = safe_float(support.get("support_azimuth_end_deg"))
    if None in (rmin, rmax, amin, amax):
        return None
    radii = fan_radius(table["x"], table["y"])
    az = fan_azimuth(table["x"], table["y"])
    return (radii >= float(rmin)) & (radii <= float(rmax)) & angle_in_interval(az, float(amin), float(amax))


def support_available(row: Mapping[str, Any]) -> bool:
    return all(str(row.get(key, "")).strip() != "" for key in ("support_azimuth_start_deg", "support_azimuth_end_deg", "support_radius_min_px", "support_radius_max_px"))


def yes_no_uncertain_from_ratio(value: float | None, threshold: float = 0.80) -> str:
    if value is None:
        return "uncertain"
    return "yes" if value >= threshold else "no"


def build_manual_notes(cards: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    observations = [
        ("Panel 1", "能看出三辆车排列，中间车最明显。整体车架构边缘是高能结构。左边车靠近雷达侧边很明显，远离雷达侧稍弱。框内右边车辆因为较边缘，车体后部及远端高能区域不明显，但近端，即框左边和下边有明显轮廓。左下角最靠近雷达且直接面向雷达的区域是高能区域。肉眼可见高能区域能够直接导向车体轮廓。", "GT 框内存在可解释车体轮廓；近雷达/面向雷达侧更强，远侧较弱。", "near_side_high_energy_ridge;facing_side_hotspot;body_edge_strip"),
        ("Panel 2", "能看出两辆车和一个货车，货车不要求识别。框内车辆能看出车体轮廓，但不连贯。靠近雷达和面向雷达处是高能区域，尤其右下角。整体轮廓是断续片段，但框内仍呈现包裹状态。该样例说明车辆 SAR 结构可以是断续条带 + 高能角点 + 总体包裹结构，而不一定是连续闭合轮廓。", "断续条带和角点热点仍可形成包裹式车体结构。", "discontinuous_aligned_body_edges;corner_or_endpoint_strong_reflector;multi_peak_enclosed_body_structure"),
        ("Panel 3", "径向扩散主要在框上侧。人工假设可能与自身运动造成的逸散、支撑结构、车体逸散或环境影响有关，靠近路边栏杆可能影响结构。但上下两侧以及框右侧能量结构仍能形成车体轮廓。注意：运动逸散目前只是 hypothesis，不可写成确定结论。", "range spread 不能直接等于 diffuse/reject；仍可能保留车体 core。", "range_spread_with_vehicle_body_core;environment_affected_body_structure;motion_hypothesis_only"),
        ("Panel 4", "框下侧能量条带明显是车体结构，强度高且连续，不应简单解释为摊开或 diffuse spread。右下角面向雷达和近侧有高能区域，远侧能量较弱。该样例更应解释为 near-side continuous body ridge / strong body-side strip + near-side hotspot + far-side weak return。", "连续强侧边条带是 morphology anchor，不是简单 diffuse spread。", "near_side_high_energy_ridge;continuous_body_side_strip;far_side_weak_return"),
        ("Panel 5", "前后时序都能看到下侧条带。该车在时序中从雷达视场右侧走到左侧，下侧条带一般都明显，高能区域会随着时序面向雷达不断移动。该样例支持 temporal migration of vehicle high-energy region，而不是单帧亮点。", "高能区随时序迁移，应建 temporal morphology tube。", "temporal_migrating_hotspot;temporal_persistent_body_ridge"),
        ("Panel 6", "虽然原标签可能是 diffuse / reject，但人工仍能肉眼看出是车。一方面面向雷达有高能区域，且可能随时序变化；另一方面上侧和下侧能量虽然断续，但能看出车体轮廓，即车长两侧。靠近雷达的一端较完整。正式表述时不要直接断言车头/车尾，应写近雷达侧端部更完整。", "弱/散结构仍可能是车；不要用 diffuse 标签否定 GT 内 morphology。", "discontinuous_aligned_body_edges;facing_side_hotspot;near_side_endpoint"),
        ("Panel 7", "与 Panel 6 和 Panel 3 是同一辆车或同一类问题。结构断续，不是非常明显的车体结构，但可根据排列形状和高能区域看出车是横向的，并且随时序变化。说明断续结构不应直接归为无结构。", "断续结构需要 temporal/contextual morphology 判断。", "discontinuous_aligned_body_edges;temporal_migrating_hotspot"),
        ("Panel 8", "存在潜在混淆。光学中车屁股紧靠一个电动车，稍远左上还有一辆车。car 之间冲突不大，主要可能与后面的电动车有能量混淆。但车体本身是自洽的：下侧有一段断续条带，右侧近端/端部比左侧边界更明显，上侧比下侧条带弱很多。应标为 SAR structure strong but association may need review due to nearby non-target/e-bike interference。", "SAR morphology strong 与 association review 可以同时成立。", "nearby_non_target_confounder;discontinuous_body_strip;association_review_needed"),
        ("Panel 9", "人工不清楚 support 想表达什么，因为 panel 没有清楚说明 support。仅从图看，GT 框明显包裹了一辆车的轮廓。下侧条带很强且没有断裂，右下角最靠近且面向雷达的一侧高能，上侧能量稍弱。需要 Codex 明确画出 optical-derived support / azimuth fan，不能让人工猜 support。可能受光学截断/遮挡、方位映射裕量、support 过宽影响。", "support 没画出来时不能让人工判断 support coverage。", "support_overlay_required;continuous_body_side_strip;coverage_hypothesis"),
        ("Panel 10", "与 Panel 9 是同一时序中的同一辆车，具有同样结构特点。肉眼判断就是车，表现为近侧强条带、近侧/面向雷达高能区和远侧较弱回波。", "同一时序重复出现近侧条带和热点。", "temporal_persistent_body_ridge;facing_side_hotspot;far_side_weak_return"),
        ("Panel 11", "与 Panel 9/10 是同一车或同一时序。图中本身有三辆车排列，远近左右均可见。周围没有很靠近的其他结构。GT 框可以完整自洽地包裹车体结构。该样例说明 GT inside support / GT boxed structure clear 时，应承认 SAR morphology strong；association 是否强是另一层问题。", "GT boxed structure clear 时应承认 morphology strong；association 是另一层。", "gt_morphology_anchor;association_separate_layer"),
        ("Panel 12", "GT 框可能存在质量问题或边缘问题，因为目标太边缘、能量弱，可能不是理想样例。但仍有微弱能量点，像车身一侧的端部/角点。应标为 weak / boundary-affected morphology reference。", "边界/弱能量样例只能作为 weak morphology reference。", "boundary_weak_vehicle_structure;corner_or_endpoint_strong_reflector"),
        ("Panel 13", "整体还可以。光学是近场截断，目标很近，整体能量较强。车头/车尾相对弱，主要是车身两侧高能区域。不是典型连续条带，但明显像车两侧车身。正式表述中不要强断言车头/车尾，应写近侧/远侧或端部结构。", "近场截断下两侧强回波可作为 near-field truncated morphology。", "near_field_truncated_strong_body_sides;endpoint_structure_not_head_tail_truth"),
    ]
    rows: list[dict[str, Any]] = []
    for idx, (panel, text, insight, keywords) in enumerate(observations):
        card = cards[idx] if idx < len(cards) else {}
        rows.append(
            {
                "panel_id": panel,
                "case_id": card.get("case_id", ""),
                "scene": card.get("scene", ""),
                "sar_frame": card.get("sar_frame", ""),
                "object_hypothesis_id": card.get("object_hypothesis_id", ""),
                "gt_id": card.get("gt_id", ""),
                "prior_card_category": card.get("category", ""),
                "human_observation_original": text,
                "morphology_insight": insight,
                "mechanism_keywords": keywords,
                "association_or_support_note": "support coverage and optical-SAR association must be audited separately from GT-box SAR morphology",
                "boundary_note": "manual visual review anchor; not identity truth; not annotation proposal",
            }
        )
    return rows


def morphology_primitives() -> list[dict[str, Any]]:
    return [
        {
            "primitive_name": "near_side_high_energy_ridge",
            "human_interpretation": "近雷达侧或面向雷达侧形成高能车体边缘条带。",
            "possible_physical_meaning": "radar-facing body side / strong specular body-side return",
            "visible_in_panels": "1;4;9;10;11",
            "expected_energy_distribution": "one side strip has sustained energy above the opposite side",
            "expected_temporal_behavior": "ridge may persist while hotspot migrates with motion",
            "confounders": "guardrail;nearby vehicle/e-bike;sidelobe",
            "runtime_safe_observable": "yes",
            "posthoc_only_fields": "GT-box membership and manual panel label",
            "next_computation_proxy": "side-strip energy and continuity inside runtime support, then validate posthoc by GT",
        },
        {
            "primitive_name": "facing_side_hotspot",
            "human_interpretation": "面向雷达或近侧端部出现局部高能点。",
            "possible_physical_meaning": "corner/plate/end reflector facing radar",
            "visible_in_panels": "1;2;4;6;9;10",
            "expected_energy_distribution": "localized p95/p99 hotspot near a body side or endpoint",
            "expected_temporal_behavior": "may shift across frames as pose changes",
            "confounders": "sidelobe peak;neighboring object peak",
            "runtime_safe_observable": "yes",
            "posthoc_only_fields": "manual near/facing interpretation",
            "next_computation_proxy": "top local energy atoms constrained by body-side strip continuity",
        },
        {
            "primitive_name": "corner_or_endpoint_strong_reflector",
            "human_interpretation": "角点或端部强反射可提示车体端点，但不能断言车头/车尾。",
            "possible_physical_meaning": "vehicle endpoint/corner scatterer",
            "visible_in_panels": "2;6;8;12;13",
            "expected_energy_distribution": "corner zones have peak/mean ratio above body average",
            "expected_temporal_behavior": "endpoint reflector can appear/disappear with pose and occlusion",
            "confounders": "label edge;small roadside object;e-bike",
            "runtime_safe_observable": "yes",
            "posthoc_only_fields": "GT-corner relation",
            "next_computation_proxy": "corner hotspot proxy plus neighboring-object review flag",
        },
        {
            "primitive_name": "far_side_weak_return",
            "human_interpretation": "远雷达侧通常弱于近侧，弱回波不等于无车体。",
            "possible_physical_meaning": "shadowing or weaker non-facing body side",
            "visible_in_panels": "1;4;9;10;13",
            "expected_energy_distribution": "opposite side lower mean energy but still geometrically aligned",
            "expected_temporal_behavior": "weak side can strengthen or fade as pose changes",
            "confounders": "display transform;occlusion;annotation extent",
            "runtime_safe_observable": "uncertain",
            "posthoc_only_fields": "physical near/far side requires calibrated geometry or human label",
            "next_computation_proxy": "do not auto-compute near/far until radar-side direction is validated",
        },
        {
            "primitive_name": "continuous_body_side_strip",
            "human_interpretation": "连续车体侧边条带可直接形成 morphology anchor。",
            "possible_physical_meaning": "continuous side/body scattering strip",
            "visible_in_panels": "1;4;9;10;11",
            "expected_energy_distribution": "edge bins along one side repeatedly exceed local background",
            "expected_temporal_behavior": "often persists over adjacent frames",
            "confounders": "road lane/guardrail parallel edge",
            "runtime_safe_observable": "yes",
            "posthoc_only_fields": "GT-side confirmation",
            "next_computation_proxy": "edge-strip continuity proxy and support energy coverage",
        },
        {
            "primitive_name": "discontinuous_aligned_body_edges",
            "human_interpretation": "断续片段仍可能沿车身排列并构成车体，不应直接判为无结构。",
            "possible_physical_meaning": "multi-scatterer body edge with occlusion or pose-dependent gaps",
            "visible_in_panels": "2;6;7;8;13",
            "expected_energy_distribution": "multiple separated high-energy atoms aligned along two body sides",
            "expected_temporal_behavior": "fragments may link across frames",
            "confounders": "clutter;neighbor object;guardrail",
            "runtime_safe_observable": "yes",
            "posthoc_only_fields": "manual alignment interpretation",
            "next_computation_proxy": "fragment alignment bins plus temporal persistence",
        },
        {
            "primitive_name": "multi_peak_enclosed_body_structure",
            "human_interpretation": "多峰结构可形成包裹车体，而不是单个 top-k 点。",
            "possible_physical_meaning": "multiple vehicle scatter centers",
            "visible_in_panels": "2;8;11",
            "expected_energy_distribution": "several high atoms inside GT/support with body-like enclosure",
            "expected_temporal_behavior": "component ordering should remain plausible",
            "confounders": "neighboring vehicle;wrong-object support overlap",
            "runtime_safe_observable": "yes",
            "posthoc_only_fields": "GT enclosure validation",
            "next_computation_proxy": "connected high-energy atoms plus graph component count",
        },
        {
            "primitive_name": "range_spread_with_vehicle_body_core",
            "human_interpretation": "径向扩散若保留车体核心，不应直接归入 diffuse/reject。",
            "possible_physical_meaning": "motion/focusing/environment affected spread plus body core",
            "visible_in_panels": "3;7",
            "expected_energy_distribution": "spread in range direction with aligned body-side residual core",
            "expected_temporal_behavior": "spread may move with object or vary with environment",
            "confounders": "guardrail;roadside structures;motion hypothesis not confirmed",
            "runtime_safe_observable": "uncertain",
            "posthoc_only_fields": "motion explanation and GT relation",
            "next_computation_proxy": "range profile width plus body-core edge continuity",
        },
        {
            "primitive_name": "environment_affected_body_structure",
            "human_interpretation": "栏杆、路边、电动车等会影响结构解释，但不必否定车体结构。",
            "possible_physical_meaning": "vehicle return mixed with environment scatter",
            "visible_in_panels": "3;8",
            "expected_energy_distribution": "vehicle-like body atoms plus extra nearby clutter component",
            "expected_temporal_behavior": "background component may persist differently from vehicle",
            "confounders": "guardrail;e-bike;neighbor vehicle",
            "runtime_safe_observable": "uncertain",
            "posthoc_only_fields": "manual confounder category",
            "next_computation_proxy": "support graph competing components plus temporal drift mismatch",
        },
        {
            "primitive_name": "boundary_weak_vehicle_structure",
            "human_interpretation": "边界/弱目标仍可提供端点或微弱车身 morphology reference。",
            "possible_physical_meaning": "partial fan-edge/low-return vehicle observation",
            "visible_in_panels": "12",
            "expected_energy_distribution": "low energy with one or two endpoint atoms",
            "expected_temporal_behavior": "may need adjacent frames to confirm",
            "confounders": "bad GT quality;fan edge;weak display contrast",
            "runtime_safe_observable": "uncertain",
            "posthoc_only_fields": "GT quality and boundary review",
            "next_computation_proxy": "boundary flag plus weak endpoint atom persistence",
        },
        {
            "primitive_name": "temporal_migrating_hotspot",
            "human_interpretation": "高能区域可随车辆运动或姿态变化迁移。",
            "possible_physical_meaning": "pose-dependent radar-facing scatter migration",
            "visible_in_panels": "5;6;7;10",
            "expected_energy_distribution": "hotspot center shifts while body envelope remains plausible",
            "expected_temporal_behavior": "structured drift, not frame-independent wrong-frame persistence",
            "confounders": "background stable peak;wrong-frame support",
            "runtime_safe_observable": "yes",
            "posthoc_only_fields": "manual same-object temporal interpretation",
            "next_computation_proxy": "short-window hotspot drift and optical motion compatibility",
        },
        {
            "primitive_name": "temporal_persistent_body_ridge",
            "human_interpretation": "车体侧边条带可在前后帧持续存在。",
            "possible_physical_meaning": "stable vehicle body-side scatter tube",
            "visible_in_panels": "5;9;10;11",
            "expected_energy_distribution": "side-strip continuity remains high across frames",
            "expected_temporal_behavior": "persistent ridge with limited drift",
            "confounders": "guardrail/background ridge",
            "runtime_safe_observable": "yes",
            "posthoc_only_fields": "GT temporal anchor",
            "next_computation_proxy": "side-strip continuity tube with background-control comparison",
        },
        {
            "primitive_name": "near_field_truncated_strong_body_sides",
            "human_interpretation": "近场截断时车身两侧可强，端部相对弱；不要强断言车头/车尾。",
            "possible_physical_meaning": "near-field partial visibility and strong side returns",
            "visible_in_panels": "13",
            "expected_energy_distribution": "strong side regions, weaker endpoints",
            "expected_temporal_behavior": "requires state/temporal compensation",
            "confounders": "optical truncation;fan edge;display crop",
            "runtime_safe_observable": "uncertain",
            "posthoc_only_fields": "manual near-field truncation interpretation",
            "next_computation_proxy": "optical truncation flag plus side-energy asymmetry",
        },
    ]


def build_energy_audit(gt_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in gt_rows:
        rows.append(energy_stats(row, gt_box_from_accounting(row)))
    return rows


def lookup_by_key(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> dict[tuple[str, ...], Mapping[str, Any]]:
    result: dict[tuple[str, ...], Mapping[str, Any]] = {}
    for row in rows:
        key = tuple(str(row.get(k, "")) for k in keys)
        result[key] = row
    return result


def support_case_id(row: Mapping[str, Any]) -> str:
    scene = sanitize(row.get("scene", "scene"))
    opt = sanitize(row.get("optical_frame", "opt"))
    sar = sanitize(row.get("sar_frame", "sar"))
    obj = sanitize(row.get("object_hypothesis_id", "obj"))
    return f"PAIR_{scene}_o{opt}_s{sar}_{obj}"


def optical_state_from_corr(corr: Mapping[str, Any] | None, support: Mapping[str, Any]) -> str:
    if corr and corr.get("optical_object_state"):
        return str(corr.get("optical_object_state"))
    return str(support.get("state_condition", ""))


def truncation_state(corr: Mapping[str, Any] | None, support: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if support.get("state_condition"):
        parts.append(f"state_condition={support.get('state_condition')}")
    if corr:
        if corr.get("visibility_state"):
            parts.append(str(corr.get("visibility_state")))
        if corr.get("edge_partial_duplicate_handoff_ambiguity_flags"):
            parts.append(str(corr.get("edge_partial_duplicate_handoff_ambiguity_flags")))
    return ";".join(parts)


def build_support_coverage(
    support_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    corr_lookup = lookup_by_key(corr_rows, ["scene", "object_hypothesis_id", "optical_frame", "sar_frame"])
    rows: list[dict[str, Any]] = []
    for support in support_rows:
        if support.get("mode_name") != STATE_MODE or support.get("sample_pool") != "paired_optical_object_sar_gt":
            continue
        key = tuple(str(support.get(k, "")) for k in ("scene", "object_hypothesis_id", "optical_frame", "sar_frame"))
        corr = corr_lookup.get(key)
        image_path = str(support.get("sar_image_path", ""))
        arr = read_image_gray(image_path)
        box = gt_box_from_correspondence(corr) if corr else {}
        table = gt_pixel_table(arr, box) if arr is not None else None
        smask = support_mask_for_gt(table, support) if table is not None and support_available(support) else None
        area_cov: float | None = None
        energy_cov: float | None = None
        morph_cov: float | None = None
        if table is not None and smask is not None:
            values = table["values"]
            area_cov = float(smask.mean()) if smask.size else None
            denom = float(values.sum())
            energy_cov = float(values[smask].sum() / denom) if denom > 0 else None
            threshold = float(np.quantile(values, 0.85)) if values.size else math.inf
            high = values >= threshold
            morph_cov = float((smask & high).sum() / high.sum()) if bool(high.any()) else None
        optical_complete = str(support.get("state_condition", "")) == "complete"
        too_broad = "yes"
        if area_cov is not None and area_cov < 0.80:
            reason = "support misses part of GT area"
        elif energy_cov is not None and energy_cov < 0.80:
            reason = "support misses GT high/total energy"
        elif morph_cov is not None and morph_cov < 0.80:
            reason = "support misses high-energy morphology proxy"
        elif support.get("peak_competition_label") == "serious_peak_competition_or_clutter":
            reason = "coverage high but peak competition prevents unique association"
        else:
            reason = "coverage hypothesis supported for morphology, association remains separate"
        rows.append(
            {
                "case_id": support_case_id(support),
                "scene": support.get("scene", ""),
                "object_hypothesis_id": support.get("object_hypothesis_id", ""),
                "sar_frame": support.get("sar_frame", ""),
                "optical_state": optical_state_from_corr(corr, support),
                "optical_complete_visible": "yes" if optical_complete else "no",
                "truncation_or_occlusion_state": truncation_state(corr, support),
                "support_boundary_available": "yes" if support_available(support) else "no",
                "support_source": f"{support.get('mode_name', '')};{support.get('range_band_source', '')}",
                "gt_area_coverage_ratio": fmt(area_cov, 4),
                "gt_energy_coverage_ratio": fmt(energy_cov, 4),
                "morphology_primitive_coverage_proxy": fmt(morph_cov, 4),
                "support_covers_most_gt_area": yes_no_uncertain_from_ratio(area_cov),
                "support_covers_most_gt_energy": yes_no_uncertain_from_ratio(energy_cov),
                "support_covers_most_vehicle_structure": yes_no_uncertain_from_ratio(morph_cov),
                "support_too_broad_for_unique_association": too_broad,
                "main_failure_reason": reason,
                "posthoc_validation_only_fields": "SAR GT polygon;GT energy;GT area;coverage ratios",
                "notes": "80-85% coverage is audited separately for GT area, GT energy, and high-energy morphology proxy; not a runtime rule.",
            }
        )
    return rows


def build_complete_pool(coverage_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in coverage_rows:
        if row.get("optical_complete_visible") != "yes":
            continue
        ratios = [safe_float(row.get("gt_area_coverage_ratio")), safe_float(row.get("gt_energy_coverage_ratio")), safe_float(row.get("morphology_primitive_coverage_proxy"))]
        supported = all(value is not None and value >= 0.80 for value in ratios)
        rows.append(
            {
                "case_id": row.get("case_id", ""),
                "scene": row.get("scene", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "optical_state": row.get("optical_state", ""),
                "why_high_confidence": "state_condition=complete from support audit; identity ambiguity remains audit-only uncertainty",
                "expected_support_behavior": "optical-derived fan/range support should cover most GT area, GT energy, and morphology proxy if the 80-85% hypothesis is plausible",
                "gt_area_coverage_ratio": row.get("gt_area_coverage_ratio", ""),
                "gt_energy_coverage_ratio": row.get("gt_energy_coverage_ratio", ""),
                "morphology_coverage_proxy": row.get("morphology_primitive_coverage_proxy", ""),
                "whether_80_85_hypothesis_supported": "yes" if supported else "no",
                "failure_reason": "" if supported else row.get("main_failure_reason", ""),
                "notes": "Audit pool only; not selector/ranking and not final association.",
            }
        )
    return rows


def incompleteness_type(row: Mapping[str, Any]) -> str:
    state = str(row.get("state_condition", ""))
    if row.get("sample_pool") == "detection_dropout_temporal_continuation":
        return "dropout/no-match temporal continuation"
    if state == "edge_or_truncated":
        return "left/right or bottom truncation;edge contact"
    if state == "duplicate_or_handoff":
        return "identity ambiguity;handoff/duplicate"
    if state == "ambiguous_or_review_only":
        return "review-only ambiguity"
    return state or "uncertain"


def build_compensation_pool(support_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in support_rows:
        if row.get("mode_name") != STATE_MODE:
            continue
        if row.get("sample_pool") == "paired_optical_object_sar_gt" and row.get("state_condition") == "complete":
            continue
        allowed = "temporal/state compensation hypothesis audit"
        not_allowed = "clean paired morphology or final annotation"
        if row.get("sample_pool") == "detection_dropout_temporal_continuation":
            allowed = "existence support and temporal continuation only"
            not_allowed = "clean paired morphology;optical-SAR correspondence"
        rows.append(
            {
                "case_id": support_case_id(row),
                "scene": row.get("scene", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "optical_state": row.get("state_condition", ""),
                "incompleteness_type": incompleteness_type(row),
                "why_single_frame_support_may_fail": "single-frame optical bbox may be truncated, ambiguous, duplicated, or detector-dropped",
                "expected_sar_structure_missing_or_shifted": "near/facing hotspot or body strip may shift, fragment, or require adjacent-frame confirmation",
                "temporal_compensation_needed": "yes",
                "state_compensation_needed": "yes",
                "possible_sar_morphology_cue": "discontinuous body edges;temporal migrating hotspot;weak endpoint;body-side strip",
                "posthoc_sar_observation": f"gt_inside={row.get('gt_inside_support_posthoc', '')};peak_competition={row.get('peak_competition_label', '')};tube={row.get('tube_peak_continuity_label', '')}",
                "allowed_use": allowed,
                "not_allowed_use": not_allowed,
            }
        )
    return rows


def support_row_lookup(support_rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in support_rows:
        if row.get("mode_name") != STATE_MODE:
            continue
        key = (str(row.get("scene", "")), str(row.get("object_hypothesis_id", "")), str(row.get("sar_frame", "")))
        result[key] = row
    return result


def card_source(
    card: Mapping[str, Any],
    gt_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
    support_lookup: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> tuple[str, dict[str, float] | None, Mapping[str, Any] | None]:
    scene = str(card.get("scene", ""))
    sar_frame = str(card.get("sar_frame", ""))
    gt_id = str(card.get("gt_id", ""))
    obj = str(card.get("object_hypothesis_id", ""))
    support = support_lookup.get((scene, obj, sar_frame))
    if gt_id:
        for row in gt_rows:
            if str(row.get("scene")) == scene and str(row.get("sar_frame")) == sar_frame and str(row.get("sar_gt_id")) == gt_id:
                return str(row.get("sar_pseudocolor_path", "")), gt_box_from_accounting(row), support
    for row in corr_rows:
        if str(row.get("scene")) == scene and str(row.get("sar_frame")) == sar_frame and str(row.get("object_hypothesis_id")) == obj:
            image_path = str(support.get("sar_image_path", "")) if support else ""
            if not image_path:
                image_path = str(row.get("sar_pseudocolor_path", ""))
            return image_path, gt_box_from_correspondence(row), support
    return "", None, support


def crop_box_for(image: Image.Image, box: Mapping[str, float] | None, support: Mapping[str, Any] | None) -> tuple[int, int, int, int]:
    width, height = image.size
    points: list[tuple[float, float]] = []
    if box and box_available(box):
        points.extend(rotated_corners(box))
    if support and support_available(support):
        rmin = float(safe_float(support.get("support_radius_min_px")) or 0)
        rmax = float(safe_float(support.get("support_radius_max_px")) or rmin)
        amin = float(safe_float(support.get("support_azimuth_start_deg")) or 0)
        amax = float(safe_float(support.get("support_azimuth_end_deg")) or amin)
        for a in np.linspace(amin, amax, 24):
            points.append(point_from_fan(rmin, float(a)))
            points.append(point_from_fan(rmax, float(a)))
    if not points:
        return 0, 0, width, height
    x0 = max(0, int(math.floor(min(x for x, _ in points))) - 80)
    x1 = min(width, int(math.ceil(max(x for x, _ in points))) + 80)
    y0 = max(0, int(math.floor(min(y for _, y in points))) - 80)
    y1 = min(height, int(math.ceil(max(y for _, y in points))) + 80)
    if x1 - x0 < 240:
        pad = (240 - (x1 - x0)) // 2
        x0 = max(0, x0 - pad)
        x1 = min(width, x1 + pad)
    if y1 - y0 < 200:
        pad = (200 - (y1 - y0)) // 2
        y0 = max(0, y0 - pad)
        y1 = min(height, y1 + pad)
    return x0, y0, x1, y1


def draw_gt(draw: ImageDraw.ImageDraw, box: Mapping[str, float] | None, offset: tuple[int, int]) -> None:
    if not box or not box_available(box):
        return
    ox, oy = offset
    pts = [(x - ox, y - oy) for x, y in rotated_corners(box)]
    draw.line(pts + [pts[0]], fill=(255, 230, 0), width=3)


def support_boundary_points(support: Mapping[str, Any]) -> list[list[tuple[float, float]]]:
    rmin = float(safe_float(support.get("support_radius_min_px")) or 0)
    rmax = float(safe_float(support.get("support_radius_max_px")) or rmin)
    amin = float(safe_float(support.get("support_azimuth_start_deg")) or 0)
    amax = float(safe_float(support.get("support_azimuth_end_deg")) or amin)
    arc_angles = np.linspace(amin, amax, 80)
    inner = [point_from_fan(rmin, float(a)) for a in arc_angles]
    outer = [point_from_fan(rmax, float(a)) for a in arc_angles]
    side_a = [point_from_fan(r, amin) for r in np.linspace(rmin, rmax, 20)]
    side_b = [point_from_fan(r, amax) for r in np.linspace(rmin, rmax, 20)]
    return [inner, outer, side_a, side_b]


def draw_support(draw: ImageDraw.ImageDraw, support: Mapping[str, Any] | None, offset: tuple[int, int]) -> None:
    if not support or not support_available(support):
        return
    ox, oy = offset
    for line in support_boundary_points(support):
        pts = [(x - ox, y - oy) for x, y in line]
        draw.line(pts, fill=(255, 0, 255), width=2)


def draw_energy_atoms(draw: ImageDraw.ImageDraw, arr: np.ndarray | None, box: Mapping[str, float] | None, offset: tuple[int, int]) -> None:
    if arr is None or not box or not box_available(box):
        return
    table = gt_pixel_table(arr, box)
    if table is None:
        return
    values = table["values"]
    if values.size == 0:
        return
    threshold = float(np.quantile(values, 0.97))
    xs = table["x"][values >= threshold]
    ys = table["y"][values >= threshold]
    vals = values[values >= threshold]
    if vals.size == 0:
        return
    order = np.argsort(vals)[::-1]
    selected: list[tuple[float, float]] = []
    ox, oy = offset
    for idx in order:
        x = float(xs[idx])
        y = float(ys[idx])
        if all(math.hypot(x - px, y - py) >= 12 for px, py in selected):
            selected.append((x, y))
        if len(selected) >= 8:
            break
    for x, y in selected:
        draw.ellipse((x - ox - 4, y - oy - 4, x - ox + 4, y - oy + 4), outline=(255, 80, 0), width=2)


def add_label(draw: ImageDraw.ImageDraw, text: str, width: int) -> None:
    draw.rectangle((0, 0, width, 42), fill=(0, 0, 0))
    draw.text((8, 6), text[:130], fill=(255, 255, 255), font=ImageFont.load_default())


def panel_view(image: Image.Image, crop: tuple[int, int, int, int], label: str) -> Image.Image:
    view = image.crop(crop)
    if view.width > 520:
        ratio = 520.0 / view.width
        view = view.resize((520, max(1, int(view.height * ratio))))
    add_label(ImageDraw.Draw(view), label, view.width)
    return view


def draw_profile(draw: ImageDraw.ImageDraw, table: Mapping[str, np.ndarray] | None, y_base: int, width: int) -> None:
    if table is None:
        draw.text((8, y_base), "energy profile unavailable", fill=(255, 255, 255), font=ImageFont.load_default())
        return
    values = table["values"]
    lx = table["local_x"]
    ly = table["local_y"]
    w = float(table["w"][0])
    h = float(table["h"][0])
    masks = [
        ("lower", ly >= 0.25 * h),
        ("upper", ly <= -0.25 * h),
        ("left", lx <= -0.25 * w),
        ("right", lx >= 0.25 * w),
        ("corner", (np.abs(lx) >= 0.28 * w) & (np.abs(ly) >= 0.28 * h)),
    ]
    means = [(name, float(values[mask].mean()) if bool(mask.any()) else 0.0) for name, mask in masks]
    max_mean = max([m for _, m in means] + [1.0])
    x = 8
    for name, mean in means:
        bar_h = int(42 * mean / max_mean)
        draw.rectangle((x, y_base + 50 - bar_h, x + 44, y_base + 50), fill=(0, 220, 255))
        draw.text((x, y_base + 54), name, fill=(255, 255, 255), font=ImageFont.load_default())
        x += 58


def render_panel(
    card: Mapping[str, Any],
    image_path: str,
    box: Mapping[str, float] | None,
    support: Mapping[str, Any] | None,
    output_path: Path,
) -> bool:
    image = read_image_rgb(image_path)
    if image is None:
        return False
    gray = read_image_gray(image_path)
    crop = crop_box_for(image, box, support)
    gt_view = panel_view(image, crop, "GT only | GT=posthoc SAR annotation / morphology anchor")
    support_view = panel_view(image, crop, "support only | optical-derived feasible region if source is runtime-safe")
    combined = panel_view(image, crop, "GT + support + energy profile | association is not identity truth")
    gt_draw = ImageDraw.Draw(gt_view)
    support_draw = ImageDraw.Draw(support_view)
    combined_draw = ImageDraw.Draw(combined)
    offset = (crop[0], crop[1])
    draw_gt(gt_draw, box, offset)
    draw_support(support_draw, support, offset)
    draw_gt(combined_draw, box, offset)
    draw_support(combined_draw, support, offset)
    draw_energy_atoms(combined_draw, gray, box, offset)
    table = gt_pixel_table(gray, box) if gray is not None and box else None
    profile_h = 90
    combined_with_profile = Image.new("RGB", (combined.width, combined.height + profile_h), (0, 0, 0))
    combined_with_profile.paste(combined, (0, 0))
    profile_draw = ImageDraw.Draw(combined_with_profile)
    draw_profile(profile_draw, table, combined.height + 8, combined.width)
    if not support or not support_available(support):
        support_draw.text((8, 48), "support boundary unavailable for this card", fill=(255, 0, 255), font=ImageFont.load_default())
        profile_draw.text((8, combined.height + 2), "support unavailable; panel cannot support support-coverage judgment", fill=(255, 0, 255), font=ImageFont.load_default())
    h = max(gt_view.height, support_view.height, combined_with_profile.height)
    panel = Image.new("RGB", (gt_view.width + support_view.width + combined_with_profile.width, h), (20, 20, 20))
    panel.paste(gt_view, (0, 0))
    panel.paste(support_view, (gt_view.width, 0))
    panel.paste(combined_with_profile, (gt_view.width + support_view.width, 0))
    footer = Image.new("RGB", (panel.width, 46), (0, 0, 0))
    footer_draw = ImageDraw.Draw(footer)
    footer_draw.text((8, 6), f"{card.get('category', '')} | {card.get('case_id', '')}", fill=(255, 255, 255), font=ImageFont.load_default())
    footer_draw.text((8, 24), "Posthoc morphology/support review panel; no final box, selector, or identity-truth claim.", fill=(255, 255, 255), font=ImageFont.load_default())
    out = Image.new("RGB", (panel.width, panel.height + footer.height), (0, 0, 0))
    out.paste(panel, (0, 0))
    out.paste(footer, (0, panel.height))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path)
    return True


def generate_atlas(
    cards: Sequence[Mapping[str, Any]],
    gt_rows: Sequence[Mapping[str, Any]],
    corr_rows: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    timestamp: str,
) -> tuple[str, int, list[dict[str, Any]]]:
    support_lookup = support_row_lookup(support_rows)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    html_cards: list[str] = []
    availability: list[dict[str, Any]] = []
    generated = 0
    for idx, card in enumerate(cards, start=1):
        image_path, box, support = card_source(card, gt_rows, corr_rows, support_lookup)
        panel_name = f"{idx:02d}_{sanitize(card.get('category'))}_{sanitize(card.get('case_id'))}_gt_support_energy_panel.png"
        panel_path = VISUAL_DIR / panel_name
        ok = render_panel(card, image_path, box, support, panel_path)
        if ok:
            generated += 1
            image_html = f'<img src="{html.escape(panel_name)}" alt="{html.escape(str(card.get("case_id", "")))}" />'
        else:
            image_html = "<p><strong>panel unavailable</strong></p>"
        reason = "rendered from SAR image path and reconstructed sector support" if ok and support else "support unavailable or non-paired SAR morphology reference"
        availability.append(
            {
                "case_id": card.get("case_id", ""),
                "scene": card.get("scene", ""),
                "sar_frame": card.get("sar_frame", ""),
                "object_hypothesis_id": card.get("object_hypothesis_id", ""),
                "gt_id": card.get("gt_id", ""),
                "image_available": "yes" if Path(str(image_path)).exists() else "no",
                "gt_box_available": "yes" if box and box_available(box) else "no",
                "support_boundary_available": "yes" if support and support_available(support) else "no",
                "support_source": f"{support.get('mode_name', '')};{support.get('range_band_source', '')}" if support else "",
                "support_mask_path_available": "no",
                "support_render_method": "reconstructed_from_sector_radius_and_azimuth_fields" if support and support_available(support) else "not_renderable_for_support",
                "panel_generated": "yes" if ok else "no",
                "panel_path": str(panel_path) if ok else "",
                "reason": reason,
            }
        )
        html_cards.append(
            "<article>"
            f"<h2>{idx}. {html.escape(str(card.get('category', '')))}</h2>"
            f"<p><code>{html.escape(str(card.get('case_id', '')))}</code></p>"
            f"{image_html}"
            f"<p>{html.escape(str(card.get('why_selected', '')))}</p>"
            "</article>"
        )
    atlas_path = VISUAL_DIR / f"oty2_gt_support_energy_overlay_atlas_{timestamp}.html"
    html_doc = (
        "<!doctype html><html><head><meta charset='utf-8'><title>OTY2 GT support energy overlay atlas</title>"
        "<style>body{font-family:Arial,sans-serif;background:#111;color:#eee;margin:24px}article{margin-bottom:36px}"
        "img{max-width:100%;border:1px solid #555}code{color:#9cf}</style></head><body>"
        "<h1>OTY2 GT Support Energy Overlay Atlas</h1>"
        "<p>GT is posthoc SAR annotation / morphology anchor. Support is reconstructed from existing optical-derived sector/range fields when available. Energy profile is SAR observation diagnostic. Association state is not identity truth.</p>"
        + "\n".join(html_cards)
        + "</body></html>"
    )
    atlas_path.write_text(html_doc, encoding="utf-8")
    return str(atlas_path), generated, availability


def render_human_archive(path: Path, notes: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# OTY2 Human Visual Review Notes And SAR Morphology Insight Archive",
        "",
        "This archive preserves manual visual-review observations as mechanism anchors. It does not create annotation proposals, final boxes, selector/ranking outputs, or identity truth.",
        "",
        "## Core Manual Mechanism Insights",
        "",
        "1. GT 框内很多车辆确实存在肉眼可解释的 SAR 车体结构。",
        "2. 近雷达侧 / 面向雷达侧通常更强。",
        "3. 远雷达侧通常较弱。",
        "4. 车辆结构常表现为连续或断续的车体边缘强散射条带。",
        "5. 角点/端部/近侧区域常出现高能反射。",
        "6. 断续结构仍可能构成车体，不应直接判为无结构。",
        "7. 时序中高能区域可能随车辆运动迁移。",
        "8. 邻近电动车、栏杆、路边结构、边缘效应、近场截断会造成结构解释困难。",
        "9. support 如果没画出来，人工无法判断 support 是否过宽。",
        "10. support coverage / optical association ambiguity 不能反过来否定 GT 框内 SAR morphology。",
        "",
        "## Panel Notes",
        "",
    ]
    for row in notes:
        lines.extend(
            [
                f"### {row['panel_id']} - {row.get('prior_card_category', '')}",
                "",
                str(row["human_observation_original"]),
                "",
                f"- morphology insight: {row['morphology_insight']}",
                f"- mechanism keywords: `{row['mechanism_keywords']}`",
                f"- boundary: {row['boundary_note']}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def render_plan_doc(path: Path, timestamp: str, sources: Mapping[str, str]) -> None:
    lines = [
        "# OTY2 GT-Anchored SAR Vehicle Morphology And Support Coverage Plan",
        "",
        f"Updated: {timestamp}",
        "",
        "This plan redirects the mechanism line from generic compact/spread/diffuse descriptors toward GT-anchored SAR vehicle morphology and optical-support coverage hypotheses. It is not OTY3, not automatic annotation, not selector/ranking, not training, and not identity truth.",
        "",
        "## Purpose",
        "",
        "- Archive manual visual review as a durable mechanism source.",
        "- Treat the 442 SAR GT rows as the SAR-side morphology reference pool while preserving 215 / 195 / 20 / 12 pool semantics.",
        "- Audit 215 paired rows for optical-derived support coverage of GT area, GT energy, and high-energy morphology proxy.",
        "- Render support overlays only from existing sector/range support fields; do not fabricate support boundaries.",
        "",
        "## Coverage Semantics",
        "",
        "- GT area coverage: fraction of GT polygon pixels inside reconstructed support.",
        "- GT energy coverage: fraction of GT-box display-grayscale SAR energy inside reconstructed support.",
        "- Morphology primitive coverage: fraction of high-energy GT pixels inside reconstructed support.",
        "- The 80-85% hypothesis is a posthoc audit hypothesis and must be reported separately for the three coverage definitions.",
        "",
        "## Inputs",
        "",
    ]
    for name, source in sources.items():
        lines.append(f"- {name}: `{source}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_required_answers(summary: Mapping[str, Any]) -> list[str]:
    m = summary["key_metrics"]
    return [
        "Manual visual review shows SAR vehicles often have near/facing-side high energy, continuous or discontinuous body-edge strips, endpoint/corner reflectors, far-side weak return, and temporal hotspot migration.",
        "GT boxes should be accepted as SAR morphology anchors when the frame shows self-consistent vehicle structure; this is separate from optical-SAR association strength.",
        "Association ambiguity cannot negate GT-box SAR morphology because object-time identity and SAR vehicle body structure are different layers.",
        "near-side ridge = strong body-side strip on radar-facing/near side when validated by visual or calibrated geometry; facing hotspot = local high-energy atom on facing/near endpoint; far-side weak return = lower-energy opposite side; discontinuous body edges = aligned separated high-energy fragments that still form body structure.",
        f"442 SAR GT morphology audit: image_available={m['gt_image_available']}, energy_available={m['gt_energy_available']}, morphology_reference_or_special={m['gt_valid_for_morphology_or_special']}.",
        f"215 paired support boundary renderability: support_boundary_available={m['support_boundary_available_paired']} via reconstructed sector/range fields; explicit support mask/path files were not found.",
        f"Complete optical 80-85 coverage hypothesis: complete_pool={m['complete_pool_rows']}, supported_all_three_coverage={m['complete_80_85_supported']}, uncertain_or_failed={m['complete_80_85_not_supported']}.",
        "80-85% is reported separately as GT area coverage, GT energy coverage, and high-energy morphology proxy coverage; it is not a single scalar and not a runtime rule.",
        f"Truncated/occluded/edge/ambiguous/dropout compensation pool rows={m['compensation_pool_rows']}; these require temporal/state compensation because single-frame support can miss shifted or fragmented SAR body cues.",
        "Concepts still needing calibration: physical near/far side direction, support-mask file format if one exists, motion-drift compatibility, endpoint versus head/tail wording, and nearby e-bike/guardrail confounders.",
        "Next priority should be visual support overlay review, then motion/drift compatibility and GM_RM019 optical continuity; GM_RM011 recovery remains later scale expansion.",
        "Stage archive items: manual visual notes, morphology primitive definitions, coverage definitions, support availability audit, and posthoc-only boundary flags.",
    ]


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# OTY2 GT-Anchored SAR Vehicle Morphology And Support Coverage Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report archives manual visual review notes and audits GT-anchored SAR morphology plus optical-derived support coverage. It does not generate annotation proposals, final candidate boxes, selector/ranking outputs, training, threshold tuning, best weights, or identity truth.",
        "",
        "## Ledger Boundary",
        "",
        "- 442 = all SAR GT / SAR-side target reference pool",
        "- 215 = current frame-level posthoc optical-SAR paired subset",
        "- 195 = GM_RM011 blocked_missing_object_stream, not unannotated",
        "- 20 = SAR-only morphology reference only",
        "- 12 = dropout/no-match temporal continuation special pool",
        "",
        "## Key Metrics",
        "",
    ]
    for key, value in summary["key_metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Required Answers", ""])
    for idx, answer in enumerate(summary["required_answers"], start=1):
        lines.append(f"{idx}. {answer}")
    lines.extend(
        [
            "",
            "## Why This Is Not A Statistical Detour Or Local Selector Optimization",
            "",
            "1. No training, threshold tuning, final candidate box, selector, ranking, or best-weight search is performed.",
            "2. This is not another descriptor table: it archives manual morphology evidence and audits GT-area, GT-energy, and morphology-proxy support coverage.",
            "3. GT-box SAR body structure is explicitly acknowledged as morphology evidence; association ambiguity is kept as a separate layer.",
            "4. Coverage is split into GT area coverage, GT energy coverage, and high-energy morphology primitive proxy coverage.",
            "5. Support is not left to human guessing: panels render reconstructed support boundaries when source fields exist; otherwise availability rows say why not.",
            "6. The complete-object 80-85% coverage hypothesis is only a posthoc audit hypothesis, not a runtime rule.",
            "7. Next work should inspect support overlays visually, then add motion/drift compatibility, GM_RM019 continuity review, and later GM_RM011 scale expansion.",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in summary["boundary_flags"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Sources", ""])
    for key, value in summary["sources"].items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any]) -> Path:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = WORKSPACE_LOG_DIR / f"oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        "old_work_dependency=false",
        "repo_outputs_written=true",
        "selector_or_ranking_used=false",
        "annotation_proposal_entered=false",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"key_metrics={json.dumps(summary.get('key_metrics', {}), ensure_ascii=False)}",
        f"boundary_flags={json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_summary(
    timestamp: str,
    notes: Sequence[Mapping[str, Any]],
    energy_rows: Sequence[Mapping[str, Any]],
    coverage_rows: Sequence[Mapping[str, Any]],
    complete_rows: Sequence[Mapping[str, Any]],
    compensation_rows: Sequence[Mapping[str, Any]],
    availability_rows: Sequence[Mapping[str, Any]],
    atlas_path: str,
    panels_generated: int,
    sources: Mapping[str, str],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    gt_image_available = sum(1 for row in energy_rows if row.get("image_available") == "yes")
    gt_energy_available = sum(1 for row in energy_rows if row.get("gt_crop_energy_available") == "yes")
    morphology_ok = sum(1 for row in energy_rows if row.get("valid_for_morphology_reference") in {"yes", "special", "uncertain"})
    support_available_count = sum(1 for row in coverage_rows if row.get("support_boundary_available") == "yes")
    complete_supported = sum(1 for row in complete_rows if row.get("whether_80_85_hypothesis_supported") == "yes")
    complete_not = len(complete_rows) - complete_supported
    area_yes = sum(1 for row in coverage_rows if row.get("support_covers_most_gt_area") == "yes")
    energy_yes = sum(1 for row in coverage_rows if row.get("support_covers_most_gt_energy") == "yes")
    morph_yes = sum(1 for row in coverage_rows if row.get("support_covers_most_vehicle_structure") == "yes")
    compensation_mix = compact_counts(row.get("incompleteness_type", "") for row in compensation_rows)
    key_metrics = {
        "manual_visual_note_rows": len(notes),
        "gt_total": len(energy_rows),
        "gt_image_available": gt_image_available,
        "gt_energy_available": gt_energy_available,
        "gt_valid_for_morphology_or_special": morphology_ok,
        "support_coverage_paired_rows": len(coverage_rows),
        "support_boundary_available_paired": support_available_count,
        "support_gt_area_coverage_ge_0p80": area_yes,
        "support_gt_energy_coverage_ge_0p80": energy_yes,
        "support_morphology_proxy_coverage_ge_0p80": morph_yes,
        "complete_pool_rows": len(complete_rows),
        "complete_80_85_supported": complete_supported,
        "complete_80_85_not_supported": complete_not,
        "compensation_pool_rows": len(compensation_rows),
        "compensation_pool_mix": compensation_mix,
        "support_overlay_availability_rows": len(availability_rows),
        "support_overlay_panels_generated": panels_generated,
        "support_overlay_atlas_generated": "yes" if atlas_path else "no",
    }
    summary: dict[str, Any] = {
        "timestamp": timestamp,
        "sample_ledger": {"ledger_valid": True, "category_counts": EXPECTED_LEDGER},
        "key_metrics": key_metrics,
        "manual_visual_mechanism_claims": [
            "GT-box vehicle morphology is a SAR-side anchor.",
            "Near/facing-side stronger energy and far-side weaker return are manual morphology hypotheses.",
            "Discontinuous aligned body edges can still be vehicle structure.",
            "Support coverage and association ambiguity are separate layers.",
        ],
        "posthoc_hypotheses_only": [
            "GT area, GT energy, and GT morphology coverage ratios use SAR GT and SAR image observations.",
            "The 80-85% complete-object coverage hypothesis is audit-only.",
            "Support overlays reconstruct existing support sectors; they do not create final boxes.",
            "Manual visual notes are review anchors, not identity truth.",
        ],
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }
    summary["required_answers"] = summarize_required_answers(summary)
    return summary


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "gt_accounting_csv": Path(args.gt_accounting_csv) if args.gt_accounting_csv else latest_path("oty2_gt_sample_accounting_audit_*.csv"),
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
        "support_peak_competition_csv": Path(args.support_peak_competition_csv) if args.support_peak_competition_csv else latest_path("oty2_support_region_peak_competition_audit_*.csv"),
        "visual_review_cards_csv": Path(args.visual_review_cards_csv) if args.visual_review_cards_csv else latest_path("oty2_visual_review_candidate_cards_*.csv"),
    }
    gt_rows = read_csv(paths["gt_accounting_csv"])
    if len(gt_rows) != 442:
        raise RuntimeError(f"Expected 442 GT accounting rows; got {len(gt_rows)}")
    pool_counts = Counter(pool_type(row) for row in gt_rows)
    expected = {PAIRED_POOL: 215, "gm011_blocked": 195, "sar_only": 20, "dropout_special": 12}
    for key, value in expected.items():
        if pool_counts.get(key, 0) != value:
            raise RuntimeError(f"Ledger mismatch for {key}: expected {value}, got {pool_counts.get(key, 0)}")
    return {
        "paths": paths,
        "gt_rows": gt_rows,
        "corr_rows": read_csv(paths["correspondence_csv"]),
        "support_rows": read_csv(paths["support_peak_competition_csv"]),
        "cards": read_csv(paths["visual_review_cards_csv"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    sources = {name: str(path) for name, path in inputs["paths"].items()}

    notes = build_manual_notes(inputs["cards"])
    primitive_rows = morphology_primitives()
    energy_rows = build_energy_audit(inputs["gt_rows"])
    coverage_rows = build_support_coverage(inputs["support_rows"], inputs["corr_rows"])
    complete_rows = build_complete_pool(coverage_rows)
    compensation_rows = build_compensation_pool(inputs["support_rows"])
    atlas_path, panels_generated, availability_rows = generate_atlas(
        inputs["cards"],
        inputs["gt_rows"],
        inputs["corr_rows"],
        inputs["support_rows"],
        timestamp,
    )

    human_doc = DOCS_DIR / "oty2_human_visual_review_notes_and_sar_morphology_insight_archive.md"
    plan_doc = DOCS_DIR / "oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage_plan.md"
    manual_csv = REPORT_DIR / "oty2_human_visual_review_notes_20260703_manual.csv"
    morphology_csv = REPORT_DIR / f"oty2_sar_vehicle_morphology_primitives_gt_anchored_{timestamp}.csv"
    energy_csv = REPORT_DIR / f"oty2_gt_box_energy_distribution_audit_{timestamp}.csv"
    coverage_csv = REPORT_DIR / f"oty2_optical_support_coverage_hypothesis_audit_{timestamp}.csv"
    complete_csv = REPORT_DIR / f"oty2_complete_optical_high_confidence_coverage_pool_{timestamp}.csv"
    compensation_csv = REPORT_DIR / f"oty2_truncated_occluded_temporal_compensation_pool_{timestamp}.csv"
    availability_csv = REPORT_DIR / f"oty2_support_overlay_image_availability_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_gt_anchored_sar_vehicle_morphology_and_support_coverage_summary_{timestamp}.json"

    outputs = {
        "human_visual_review_archive_doc": str(human_doc),
        "plan_doc": str(plan_doc),
        "manual_visual_review_notes_csv": str(manual_csv),
        "sar_vehicle_morphology_primitives_gt_anchored_csv": str(morphology_csv),
        "gt_box_energy_distribution_audit_csv": str(energy_csv),
        "optical_support_coverage_hypothesis_audit_csv": str(coverage_csv),
        "complete_optical_high_confidence_coverage_pool_csv": str(complete_csv),
        "truncated_occluded_temporal_compensation_pool_csv": str(compensation_csv),
        "support_overlay_image_availability_csv": str(availability_csv),
        "gt_anchored_sar_vehicle_morphology_and_support_coverage_report_md": str(report_md),
        "gt_anchored_sar_vehicle_morphology_and_support_coverage_summary_json": str(summary_json),
        "support_overlay_atlas_html": atlas_path,
    }
    summary = build_summary(
        timestamp,
        notes,
        energy_rows,
        coverage_rows,
        complete_rows,
        compensation_rows,
        availability_rows,
        atlas_path,
        panels_generated,
        sources,
        outputs,
    )
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)

    render_human_archive(human_doc, notes)
    render_plan_doc(plan_doc, timestamp, sources)
    write_csv(manual_csv, notes, MANUAL_NOTE_FIELDS)
    write_csv(morphology_csv, primitive_rows, MORPHOLOGY_PRIMITIVE_FIELDS)
    write_csv(energy_csv, energy_rows, ENERGY_FIELDS)
    write_csv(coverage_csv, coverage_rows, SUPPORT_FIELDS)
    write_csv(complete_csv, complete_rows, COMPLETE_POOL_FIELDS)
    write_csv(compensation_csv, compensation_rows, COMPENSATION_FIELDS)
    write_csv(availability_csv, availability_rows, AVAILABILITY_FIELDS)
    render_report(report_md, summary)
    write_json(summary_json, summary)

    print(json.dumps({"outputs": summary["outputs"], "key_metrics": summary["key_metrics"], "boundary_flags": BOUNDARY_FLAGS}, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--gt-accounting-csv", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--support-peak-competition-csv", default="")
    parser.add_argument("--visual-review-cards-csv", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
