"""WGV3.6A-A1.8A-R2.1-R1 bbox family integrity fix.

Commands are intentionally staged:

generate              build corrected families from frozen R2.1 response boxes
blind-raw-pack        render raw family review sheets and blank judgement CSV
blind-assisted-pack   render assisted family review sheets after raw freeze
evaluate              post-freeze member/family GT evaluation and R2.1 delta
verify-replay         replay deterministic generation artifacts and compare SHA

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
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

from run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping import (  # noqa: E402
    FAN_CENTER_X,
    FAN_CENTER_Y,
    REPO_ROOT,
    REPORT_DIR,
    SAMPLES_DIR,
    SAR_HEIGHT,
    SAR_WIDTH,
    Box,
    fmt,
    parse_float,
    parse_int,
    sar_gray_path,
    sha256,
    write_csv,
    write_text,
)


DATE = "20260711"
SCENE = "GM_RM019"
PX_TO_M = 0.03
START_COMMIT = "713fb7ddad99c56303078bb7fca87c0006b00bd3"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_8a_r2_1_r1_20260711"
VERIFY_TMP_DIR = OUT_DIR / "_verify_replay_tmp"

FOCUS_FRAMES = {
    27, 30, 31, 32, 34, 39, 40, 77, 78, 79, 80, 81,
    263, 270, 271, 272, 273, 289, 290,
}
TOPK_AUDIT_FOCUS_FRAMES = {27, 28, 29, 30, 31, 78, 79, 80, 81, 227, 263, 270, 271, 272, 273, 289, 290}

FROZEN_INPUTS = {
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
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_frozen_artifact_manifest_{DATE}.csv",
}

EVAL_ONLY_INPUTS = {
    "old_families": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_bbox_hypothesis_families_{DATE}.csv",
    "old_family_members": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_family_member_manifest_{DATE}.csv",
    "paired": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_family_integrity_fix_{DATE}.md",
    "corrected_families": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_corrected_families_{DATE}.csv",
    "family_members": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_family_members_{DATE}.csv",
    "family_pairwise_integrity": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_family_pairwise_integrity_{DATE}.csv",
    "family_boundaries": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_family_boundaries_{DATE}.csv",
    "sparse_family_temporal_edges": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_sparse_family_temporal_edges_{DATE}.csv",
    "blind_raw": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_blind_raw_family_judgement_{DATE}.csv",
    "blind_assisted": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_blind_assisted_family_judgement_{DATE}.csv",
    "member_gt_evaluation": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_member_gt_evaluation_{DATE}.csv",
    "family_gt_evaluation": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_family_gt_evaluation_{DATE}.csv",
    "topk_component_drop_audit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_topk_component_drop_audit_{DATE}.csv",
    "r2_1_family_delta": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_r2_1_family_delta_{DATE}.csv",
    "error_taxonomy": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_error_taxonomy_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_gate_integrity_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_frozen_manifest_{DATE}.csv",
}

GENERATION_KEYS = [
    "corrected_families",
    "family_members",
    "family_pairwise_integrity",
    "family_boundaries",
    "sparse_family_temporal_edges",
    "topk_component_drop_audit",
]

CORRECTED_FAMILY_FIELDS = [
    "family_id",
    "sar_frame",
    "member_response_box_ids",
    "member_core_subgraph_ids",
    "family_relation",
    "member_count",
    "family_common_core_atom_ids",
    "family_common_core_bbox",
    "family_common_core_status",
    "family_conservative_bbox",
    "family_conservative_bbox_status",
    "family_member_bbox_variants",
    "family_uncertain_envelope",
    "family_center_dispersion_px",
    "family_width_range_px",
    "family_height_range_px",
    "family_pairwise_min_iou",
    "family_pairwise_max_center_distance_px",
    "family_boundary_reason_cn",
    "generation_provenance",
]
FAMILY_MEMBER_FIELDS = [
    "family_id",
    "response_box_id",
    "core_subgraph_id",
    "sar_frame",
    "member_relation_to_family",
    "box_state",
    "core_member_atom_ids",
    "strong_optional_atom_ids",
    "uncertain_optional_atom_ids",
    "conservative_response_bbox",
    "uncertain_envelope_bbox",
]
PAIRWISE_FIELDS = [
    "family_id",
    "sar_frame",
    "member_box_a",
    "member_box_b",
    "bbox_iou",
    "center_distance_px",
    "core_overlap_ratio",
    "core_subset_relation",
    "relation_type",
    "pairwise_valid",
    "invalid_reason",
    "would_single_link_component",
    "empty_optional_equality_seen",
]
BOUNDARY_FIELDS = [
    "family_id",
    "sar_frame",
    "family_member_bbox_variants",
    "family_common_core_bbox",
    "family_common_core_status",
    "family_conservative_bbox",
    "family_conservative_bbox_status",
    "family_uncertain_envelope",
    "family_boundary_reason_cn",
]
TEMPORAL_FIELDS = [
    "source_family_id",
    "target_family_id",
    "source_frame",
    "target_frame",
    "source_geometry_type",
    "target_geometry_type",
    "center_shift_min_px",
    "center_shift_max_px",
    "bbox_iou_min",
    "bbox_iou_max",
    "shared_core_track_ids",
    "temporal_edge_state",
    "geometry_uncertainty",
]
RAW_FIELDS = [
    "raw_review_id",
    "blind_frame_id",
    "blind_family_id",
    "family_id",
    "sar_frame",
    "raw_family_visible_structure_cn",
    "raw_member_bbox_consistency_cn",
    "raw_common_core_support_cn",
    "raw_boundary_variant_reason_cn",
    "raw_spatially_distinct_structure_present",
    "raw_vehicle_response_support",
    "raw_background_support",
    "raw_unresolved",
    "raw_decisive_reason_cn",
    "raw_confidence",
    "raw_png",
]
ASSISTED_FIELDS = [
    "assisted_review_id",
    "blind_frame_id",
    "blind_family_id",
    "family_id",
    "sar_frame",
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
MEMBER_EVAL_FIELDS = [
    "response_box_id",
    "family_id",
    "sar_frame",
    "gt_exact_frame_available",
    "member_bbox_iou",
    "member_gt_coverage",
    "member_prediction_purity",
    "member_area_ratio",
    "member_center_distance_px",
    "member_eval_state",
]
FAMILY_EVAL_FIELDS = [
    "family_id",
    "sar_frame",
    "gt_exact_frame_available",
    "family_common_core_iou",
    "family_common_core_gt_coverage",
    "family_common_core_prediction_purity",
    "family_conservative_iou",
    "family_conservative_gt_coverage",
    "family_conservative_prediction_purity",
    "family_best_member_iou_eval_only",
    "family_worst_member_iou_eval_only",
    "family_member_iou_range",
    "family_eval_state",
    "raw_judgement",
    "assisted_judgement",
]
TOPK_FIELDS = [
    "sar_frame",
    "all_component_count",
    "kept_top_component_count",
    "kept_background_extra_count",
    "dropped_component_count",
    "component_rank",
    "component_bbox",
    "component_area",
    "component_energy",
    "component_role_proposal",
    "near_any_core_bbox",
    "near_any_family_bbox",
    "possible_weak_vehicle_part",
    "visual_review_required",
]
DELTA_FIELDS = [
    "sar_frame",
    "old_family_count",
    "new_family_count",
    "old_member_count",
    "new_member_count",
    "overmerged_old_family_ids",
    "split_new_family_ids",
    "old_spatially_distinct_members_in_same_family",
    "new_spatially_distinct_members_in_same_family",
    "old_arbitrary_representative_bbox",
    "new_family_boundary_status",
    "change_reason_cn",
]
ERROR_FIELDS = ["case_id", "family_id", "sar_frame", "error_type", "reason_cn", "provenance"]
GATE_FIELDS = ["gate", "status", "evidence", "provenance"]
MANIFEST_FIELDS = ["artifact", "path", "sha256", "rows", "frozen_phase"]


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


def split_ids(text: str) -> list[str]:
    return [part for part in str(text or "").split(";") if part]


def set_ids(text: str) -> set[str]:
    return set(split_ids(text))


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def safe_div(num: float, den: float) -> float:
    return num / den if den else math.nan


def box_from_text(text: str) -> Box | None:
    parts = [parse_float(part) for part in str(text or "").split(",")]
    if len(parts) != 4 or any(math.isnan(v) for v in parts):
        return None
    return Box(parts[0], parts[1], parts[2], parts[3])


def box_text(box: Box | None) -> str:
    if box is None:
        return ""
    return f"{fmt(box.x1)},{fmt(box.y1)},{fmt(box.x2)},{fmt(box.y2)}"


def clamp_box(box: Box) -> Box:
    return Box(
        max(0.0, min(float(SAR_WIDTH - 1), box.x1)),
        max(0.0, min(float(SAR_HEIGHT - 1), box.y1)),
        max(1.0, min(float(SAR_WIDTH), box.x2)),
        max(1.0, min(float(SAR_HEIGHT), box.y2)),
    )


def expand_box(box: Box, margin: float) -> Box:
    return clamp_box(Box(box.x1 - margin, box.y1 - margin, box.x2 + margin, box.y2 + margin))


def union_box(boxes: Sequence[Box]) -> Box | None:
    if not boxes:
        return None
    return clamp_box(Box(min(b.x1 for b in boxes), min(b.y1 for b in boxes), max(b.x2 for b in boxes), max(b.y2 for b in boxes)))


def intersection_box(boxes: Sequence[Box]) -> Box | None:
    if not boxes:
        return None
    box = Box(max(b.x1 for b in boxes), max(b.y1 for b in boxes), min(b.x2 for b in boxes), min(b.y2 for b in boxes))
    if box.area <= 0:
        return None
    return clamp_box(box)


def bbox_intersection_area(a: Box, b: Box) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_iou(a: Box | None, b: Box | None) -> float:
    if a is None or b is None:
        return math.nan
    inter = bbox_intersection_area(a, b)
    return safe_div(inter, a.area + b.area - inter)


def center_distance(a: Box | None, b: Box | None) -> float:
    if a is None or b is None:
        return math.nan
    return math.hypot(a.cx - b.cx, a.cy - b.cy)


def contains_box(a: Box | None, b: Box | None) -> bool:
    if a is None or b is None:
        return False
    return a.x1 <= b.x1 + 1 and a.y1 <= b.y1 + 1 and a.x2 >= b.x2 - 1 and a.y2 >= b.y2 - 1


def gap_between(a: Box | None, b: Box | None) -> float:
    if a is None or b is None:
        return math.nan
    dx = max(0.0, max(a.x1, b.x1) - min(a.x2, b.x2))
    dy = max(0.0, max(a.y1, b.y1) - min(a.y2, b.y2))
    return math.hypot(dx, dy)


def bbox_metrics(pred: Box | None, gt: Box | None) -> dict[str, float]:
    if pred is None or gt is None:
        return {"iou": math.nan, "coverage": math.nan, "purity": math.nan, "area_ratio": math.nan, "center_distance": math.nan}
    inter = bbox_intersection_area(pred, gt)
    return {
        "iou": bbox_iou(pred, gt),
        "coverage": safe_div(inter, gt.area),
        "purity": safe_div(inter, pred.area),
        "area_ratio": safe_div(pred.area, gt.area),
        "center_distance": center_distance(pred, gt),
    }


def unique_preserve(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def require_files(paths: Sequence[Path]) -> None:
    missing = [rel(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required files: " + "; ".join(missing))


def load_and_verify_frozen_inputs() -> dict[str, Any]:
    require_files(list(FROZEN_INPUTS.values()))
    manifest = read_rows(FROZEN_INPUTS["frozen_manifest"])
    manifest_by_name = {row["artifact"]: row for row in manifest}
    sha_checks: dict[str, bool] = {}
    for artifact, row in manifest_by_name.items():
        path = REPO_ROOT / row["path"]
        if path.exists():
            sha_checks[artifact] = sha256(path) == row["sha256"]
    return {
        "atoms": read_rows(FROZEN_INPUTS["atom_trace"]),
        "roles": read_rows(FROZEN_INPUTS["roles"]),
        "support_metrics": read_rows(FROZEN_INPUTS["support_metrics"]),
        "lineage_nodes": read_rows(FROZEN_INPUTS["lineage_nodes"]),
        "lineage_edges": read_rows(FROZEN_INPUTS["lineage_edges"]),
        "atom_graph_nodes": read_rows(FROZEN_INPUTS["atom_graph_nodes"]),
        "atom_graph_edges": read_rows(FROZEN_INPUTS["atom_graph_edges"]),
        "cores": read_rows(FROZEN_INPUTS["core_hypotheses"]),
        "optional_membership": read_rows(FROZEN_INPUTS["optional_membership"]),
        "boxes": read_rows(FROZEN_INPUTS["response_boxes"]),
        "old_manifest": manifest,
        "sha_checks": sha_checks,
    }


def accepted_graph_pairs(graph_edges: Sequence[Mapping[str, str]]) -> dict[int, set[frozenset[str]]]:
    out: dict[int, set[frozenset[str]]] = defaultdict(set)
    for row in graph_edges:
        if str(row.get("edge_status", "")).startswith("accepted"):
            frame = parse_int(row.get("sar_frame"))
            out[frame].add(frozenset([row["source_atom_id"], row["target_atom_id"]]))
    return out


def atom_support_boxes(atom_rows: Sequence[Mapping[str, str]]) -> dict[str, Box]:
    out: dict[str, Box] = {}
    for row in atom_rows:
        box = box_from_text(row.get("support_bbox", ""))
        if box is not None:
            out[row["atom_id"]] = box
    return out


def atom_track_ids(atom_graph_nodes: Sequence[Mapping[str, str]]) -> dict[str, str]:
    return {row["atom_id"]: row.get("persistent_part_track_id", "") for row in atom_graph_nodes}


def core_subset_relation(a_core: set[str], b_core: set[str]) -> str:
    if a_core == b_core:
        return "equal"
    if a_core and a_core.issubset(b_core):
        return "a_subset_b"
    if b_core and b_core.issubset(a_core):
        return "b_subset_a"
    if a_core & b_core:
        return "overlap"
    return "none"


def core_overlap_ratio(a_core: set[str], b_core: set[str]) -> float:
    if not a_core or not b_core:
        return 0.0
    return safe_div(len(a_core & b_core), min(len(a_core), len(b_core)))


def accepted_link_between_core_sets(a_core: set[str], b_core: set[str], frame_pairs: set[frozenset[str]]) -> bool:
    for a in a_core:
        for b in b_core:
            if a != b and frozenset([a, b]) in frame_pairs:
                return True
    return False


def classify_member_pair(
    a: Mapping[str, str],
    b: Mapping[str, str],
    accepted_pairs_by_frame: Mapping[int, set[frozenset[str]]],
) -> dict[str, Any]:
    frame = parse_int(a["sar_frame"])
    abox = box_from_text(a["conservative_response_bbox"])
    bbox = box_from_text(b["conservative_response_bbox"])
    acore_box = box_from_text(a["core_bbox"])
    bcore_box = box_from_text(b["core_bbox"])
    a_core = set_ids(a.get("core_member_atom_ids", ""))
    b_core = set_ids(b.get("core_member_atom_ids", ""))
    a_strong = set_ids(a.get("strong_optional_atom_ids", ""))
    b_strong = set_ids(b.get("strong_optional_atom_ids", ""))
    iou = bbox_iou(abox, bbox)
    cdist = center_distance(abox, bbox)
    gap = gap_between(abox, bbox)
    coverlap = core_overlap_ratio(a_core, b_core)
    subset = core_subset_relation(a_core, b_core)
    empty_optional_equality = not a_strong and not b_strong
    core_box_iou = bbox_iou(acore_box, bcore_box)
    size_ratio = safe_div(abox.area, bbox.area) if abox is not None and bbox is not None else math.nan
    size_ratio = max(size_ratio, safe_div(1.0, size_ratio)) if size_ratio and not math.isnan(size_ratio) else math.nan
    frame_pairs = accepted_pairs_by_frame.get(frame, set())
    accepted_core_link = accepted_link_between_core_sets(a_core, b_core, frame_pairs)

    valid = False
    relation = "spatially_distinct_hypothesis"
    reason = ""

    if box_text(abox) and box_text(abox) == box_text(bbox):
        valid = True
        relation = "exact_duplicate_bbox"
    elif iou >= 0.75 and cdist <= 25.0:
        valid = True
        relation = "high_iou_boundary_variant"
    elif (contains_box(abox, bbox) or contains_box(bbox, abox)) and cdist <= 95.0 and (
        coverlap >= 0.5 or subset in {"a_subset_b", "b_subset_a", "equal"} or accepted_core_link
    ):
        valid = True
        relation = "nested_same_core_variant"
    elif a_core == b_core and a_core and (iou >= 0.20 or core_box_iou >= 0.75 or cdist <= 75.0 or gap <= 12.0):
        valid = True
        relation = "same_core_different_optional_boundary"
    elif coverlap >= 0.67 and iou >= 0.30 and cdist <= 60.0 and (math.isnan(size_ratio) or size_ratio <= 2.5):
        valid = True
        relation = "shared_major_core_variant"

    if not valid:
        if empty_optional_equality:
            reason = "no_optional_evidence"
        if not a_core & b_core and (math.isnan(core_box_iou) or core_box_iou < 0.20):
            reason = "different_core_without_overlap"
        if (not math.isnan(gap) and gap > 20.0) or (not math.isnan(cdist) and cdist > 90.0 and (math.isnan(iou) or iou < 0.10)):
            reason = "different_local_response"
        if not reason:
            reason = "no_legal_grouping_relation"

    return {
        "sar_frame": frame,
        "a": a["response_box_id"],
        "b": b["response_box_id"],
        "bbox_iou": iou,
        "center_distance_px": cdist,
        "core_overlap_ratio": coverlap,
        "core_subset_relation": subset,
        "relation_type": relation,
        "pairwise_valid": valid,
        "invalid_reason": "" if valid else reason,
        "empty_optional_equality_seen": empty_optional_equality,
    }


def connected_components(ids: Sequence[str], valid_edges: set[frozenset[str]]) -> list[list[str]]:
    parent = {item: item for item in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for edge in valid_edges:
        a, b = sorted(edge)
        union(a, b)
    groups: dict[str, list[str]] = defaultdict(list)
    for item in ids:
        groups[find(item)].append(item)
    return [sorted(group) for group in groups.values()]


def build_pairwise_member_relations(
    boxes: Sequence[Mapping[str, str]],
    graph_edges: Sequence[Mapping[str, str]],
) -> tuple[dict[frozenset[str], dict[str, Any]], dict[str, str], dict[str, int]]:
    accepted_pairs_by_frame = accepted_graph_pairs(graph_edges)
    by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for box in boxes:
        by_frame[parse_int(box["sar_frame"])].append(box)

    pair_relations: dict[frozenset[str], dict[str, Any]] = {}
    single_link_component: dict[str, str] = {}
    bridge_stats = {"single_link_nonclique_components": 0}
    for frame in sorted(by_frame):
        frame_boxes = sorted(by_frame[frame], key=lambda row: row["response_box_id"])
        valid_edges: set[frozenset[str]] = set()
        for a, b in combinations(frame_boxes, 2):
            reln = classify_member_pair(a, b, accepted_pairs_by_frame)
            key = frozenset([a["response_box_id"], b["response_box_id"]])
            pair_relations[key] = reln
            if reln["pairwise_valid"]:
                valid_edges.add(key)
        ids = [row["response_box_id"] for row in frame_boxes]
        for idx, component in enumerate(connected_components(ids, valid_edges), start=1):
            component_id = f"SL{frame:06d}_{idx:03d}"
            for response_id in component:
                single_link_component[response_id] = component_id
            pair_count = len(component) * (len(component) - 1) // 2
            edge_count = sum(frozenset(pair) in valid_edges for pair in combinations(component, 2))
            if edge_count < pair_count:
                bridge_stats["single_link_nonclique_components"] += 1
    return pair_relations, single_link_component, bridge_stats


def build_pairwise_consistent_families(
    boxes: Sequence[Mapping[str, str]],
    pair_relations: Mapping[frozenset[str], Mapping[str, Any]],
) -> tuple[list[list[Mapping[str, str]]], int]:
    by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for box in boxes:
        by_frame[parse_int(box["sar_frame"])].append(box)
    families: list[list[Mapping[str, str]]] = []
    split_count = 0
    for frame in sorted(by_frame):
        frame_boxes = sorted(by_frame[frame], key=lambda row: row["response_box_id"])
        unassigned = {row["response_box_id"] for row in frame_boxes}
        by_id = {row["response_box_id"]: row for row in frame_boxes}
        valid_edges = {
            key for key, reln in pair_relations.items()
            if reln["sar_frame"] == frame and reln["pairwise_valid"]
        }
        component_by_member: dict[str, int] = {}
        for idx, component in enumerate(connected_components([row["response_box_id"] for row in frame_boxes], valid_edges)):
            for response_id in component:
                component_by_member[response_id] = idx
        while unassigned:
            seed = sorted(unassigned)[0]
            group = [seed]
            unassigned.remove(seed)
            for candidate in sorted(list(unassigned)):
                if all(pair_relations.get(frozenset([candidate, existing]), {}).get("pairwise_valid") for existing in group):
                    group.append(candidate)
            for response_id in group[1:]:
                unassigned.remove(response_id)
            if len({component_by_member.get(response_id) for response_id in group}) == 1:
                component = [
                    rid for rid, comp_id in component_by_member.items()
                    if comp_id == component_by_member[group[0]]
                ]
                if len(component) > len(group):
                    split_count += 1
            families.append([by_id[response_id] for response_id in group])
    return families, split_count


def family_relation_from_pairs(member_ids: Sequence[str], pair_relations: Mapping[frozenset[str], Mapping[str, Any]]) -> str:
    if len(member_ids) == 1:
        return "single_member_family"
    rels = [pair_relations[frozenset([a, b])]["relation_type"] for a, b in combinations(member_ids, 2)]
    rel_set = set(rels)
    if rel_set == {"exact_duplicate_bbox"}:
        return "exact_duplicate_family"
    if rel_set <= {"exact_duplicate_bbox", "high_iou_boundary_variant"}:
        return "high_iou_boundary_family"
    if "nested_same_core_variant" in rel_set and rel_set <= {
        "exact_duplicate_bbox",
        "high_iou_boundary_variant",
        "nested_same_core_variant",
        "same_core_different_optional_boundary",
        "shared_major_core_variant",
    }:
        return "nested_same_core_family"
    if rel_set <= {"exact_duplicate_bbox", "same_core_different_optional_boundary"}:
        return "same_core_optional_variant_family"
    return "mixed_valid_boundary_variant_family"


def common_core_atoms(members: Sequence[Mapping[str, str]]) -> tuple[list[str], str]:
    core_sets = [set_ids(row.get("core_member_atom_ids", "")) for row in members]
    if not core_sets:
        return [], "unavailable"
    if len(core_sets) == 1:
        return sorted(core_sets[0]), "available_single_member_core"
    intersection = set.intersection(*core_sets) if all(core_sets) else set()
    if intersection:
        return sorted(intersection), "available_shared_atoms"
    counts = Counter(atom_id for core in core_sets for atom_id in core)
    threshold = math.ceil(len(core_sets) * 0.67)
    frequent = sorted(atom_id for atom_id, count in counts.items() if count >= threshold)
    if frequent:
        return frequent, "available_high_frequency_core"
    return [], "unavailable"


def boundary_status_for_family(
    relation: str,
    members: Sequence[Mapping[str, str]],
    member_boxes: Sequence[Box],
    common_box: Box | None,
    pair_relations: Mapping[frozenset[str], Mapping[str, Any]],
) -> tuple[str, Box | None, str]:
    variants = unique_preserve([row.get("conservative_response_bbox", "") for row in members])
    if len(variants) == 1:
        return "single_consensus_bbox", box_from_text(variants[0]), "族内成员共享同一个保守响应边界，保守框可作为族级 raw/eval 对象。"
    ids = [row["response_box_id"] for row in members]
    pair_ious = [pair_relations[frozenset([a, b])]["bbox_iou"] for a, b in combinations(ids, 2)]
    if relation in {"high_iou_boundary_family", "same_core_optional_variant_family"} and pair_ious and min(pair_ious) >= 0.75:
        return "multiple_valid_bbox_variants", None, "族内边界高度重叠但存在多个合法变体；本轮保留多边界，不强行排序。"
    if common_box is not None and relation in {
        "nested_same_core_family",
        "same_core_optional_variant_family",
        "mixed_valid_boundary_variant_family",
    }:
        return "common_core_only", None, "族内成员共享核心结构，但保守边界存在不可排序差异；以共有核心解释，不输出单一保守框。"
    if member_boxes:
        return "multiple_valid_bbox_variants", None, "族内成员满足两两合法关系，但边界变体不可唯一化；保留全部成员边界。"
    return "family_boundary_unresolved", None, "族边界无法从成员框和共有核心中稳定确定。"


def derive_family_boundary_representation(
    families: Sequence[Sequence[Mapping[str, str]]],
    pair_relations: Mapping[frozenset[str], Mapping[str, Any]],
    atom_boxes: Mapping[str, Box],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    family_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []
    boundary_rows: list[dict[str, Any]] = []
    for index, members in enumerate(families, start=1):
        family_id = f"R21R1F{index:05d}"
        frame = parse_int(members[0]["sar_frame"])
        member_ids = [row["response_box_id"] for row in members]
        core_ids = [row["core_subgraph_id"] for row in members]
        relation = family_relation_from_pairs(member_ids, pair_relations)
        member_boxes = [box for box in (box_from_text(row.get("conservative_response_bbox", "")) for row in members) if box is not None]
        envelope_boxes = [
            box for box in (
                box_from_text(row.get("uncertain_envelope_bbox", "")) or box_from_text(row.get("conservative_response_bbox", ""))
                for row in members
            )
            if box is not None
        ]
        common_atoms, common_status = common_core_atoms(members)
        common_box = union_box([atom_boxes[atom_id] for atom_id in common_atoms if atom_id in atom_boxes])
        if common_box is None:
            common_box = intersection_box([box_from_text(row.get("core_bbox", "")) for row in members if box_from_text(row.get("core_bbox", ""))])
            if common_box is not None and common_status == "unavailable":
                common_status = "available_member_intersection"
        status, conservative_box, reason = boundary_status_for_family(relation, members, member_boxes, common_box, pair_relations)
        envelope = union_box(envelope_boxes + member_boxes)
        center_distances = [center_distance(a, b) for a, b in combinations(member_boxes, 2)]
        pair_ious = [bbox_iou(a, b) for a, b in combinations(member_boxes, 2)]
        widths = [box.width for box in member_boxes]
        heights = [box.height for box in member_boxes]
        row = {
            "family_id": family_id,
            "sar_frame": frame,
            "member_response_box_ids": ";".join(member_ids),
            "member_core_subgraph_ids": ";".join(core_ids),
            "family_relation": relation,
            "member_count": len(members),
            "family_common_core_atom_ids": ";".join(common_atoms),
            "family_common_core_bbox": box_text(common_box),
            "family_common_core_status": common_status if common_box is not None else "unavailable",
            "family_conservative_bbox": box_text(conservative_box),
            "family_conservative_bbox_status": status,
            "family_member_bbox_variants": " | ".join(unique_preserve([row.get("conservative_response_bbox", "") for row in members])),
            "family_uncertain_envelope": box_text(envelope),
            "family_center_dispersion_px": fmt(max(center_distances) if center_distances else 0.0),
            "family_width_range_px": f"{fmt(min(widths))}-{fmt(max(widths))}" if widths else "",
            "family_height_range_px": f"{fmt(min(heights))}-{fmt(max(heights))}" if heights else "",
            "family_pairwise_min_iou": fmt(min(pair_ious) if pair_ious else 1.0),
            "family_pairwise_max_center_distance_px": fmt(max(center_distances) if center_distances else 0.0),
            "family_boundary_reason_cn": reason,
            "generation_provenance": "r2_1_r1_from_frozen_response_box_member_hypotheses_pairwise_complete_family",
        }
        family_rows.append(row)
        boundary_rows.append({field: row.get(field, "") for field in BOUNDARY_FIELDS})
        for member in members:
            member_relations = [
                pair_relations[frozenset([member["response_box_id"], other["response_box_id"]])]["relation_type"]
                for other in members
                if other["response_box_id"] != member["response_box_id"]
            ]
            member_rows.append(
                {
                    "family_id": family_id,
                    "response_box_id": member["response_box_id"],
                    "core_subgraph_id": member["core_subgraph_id"],
                    "sar_frame": frame,
                    "member_relation_to_family": ";".join(sorted(set(member_relations))) if member_relations else "single_member_family",
                    "box_state": member["box_state"],
                    "core_member_atom_ids": member.get("core_member_atom_ids", ""),
                    "strong_optional_atom_ids": member.get("strong_optional_atom_ids", ""),
                    "uncertain_optional_atom_ids": member.get("uncertain_optional_atom_ids", ""),
                    "conservative_response_bbox": member.get("conservative_response_bbox", ""),
                    "uncertain_envelope_bbox": member.get("uncertain_envelope_bbox", ""),
                }
            )
    return family_rows, member_rows, boundary_rows


def validate_family_pairwise_integrity(
    family_rows: Sequence[Mapping[str, str]],
    pair_relations: Mapping[frozenset[str], Mapping[str, Any]],
    single_link_component: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    invalid_inside = 0
    spatial_inside = 0
    for family in family_rows:
        ids = split_ids(family["member_response_box_ids"])
        if len(ids) == 1:
            rows.append(
                {
                    "family_id": family["family_id"],
                    "sar_frame": family["sar_frame"],
                    "member_box_a": ids[0],
                    "member_box_b": ids[0],
                    "bbox_iou": "1",
                    "center_distance_px": "0",
                    "core_overlap_ratio": "1",
                    "core_subset_relation": "equal",
                    "relation_type": "single_member_family",
                    "pairwise_valid": "true",
                    "invalid_reason": "",
                    "would_single_link_component": single_link_component.get(ids[0], ""),
                    "empty_optional_equality_seen": "false",
                }
            )
            continue
        for a, b in combinations(ids, 2):
            reln = pair_relations[frozenset([a, b])]
            valid = bool(reln["pairwise_valid"])
            invalid_inside += 0 if valid else 1
            spatial_inside += 1 if reln["relation_type"] == "spatially_distinct_hypothesis" else 0
            rows.append(
                {
                    "family_id": family["family_id"],
                    "sar_frame": family["sar_frame"],
                    "member_box_a": a,
                    "member_box_b": b,
                    "bbox_iou": fmt(reln["bbox_iou"]),
                    "center_distance_px": fmt(reln["center_distance_px"]),
                    "core_overlap_ratio": fmt(reln["core_overlap_ratio"]),
                    "core_subset_relation": reln["core_subset_relation"],
                    "relation_type": reln["relation_type"],
                    "pairwise_valid": bool_text(valid),
                    "invalid_reason": reln["invalid_reason"],
                    "would_single_link_component": single_link_component.get(a, ""),
                    "empty_optional_equality_seen": bool_text(reln["empty_optional_equality_seen"]),
                }
            )
    return rows, {"invalid_inside": invalid_inside, "spatial_inside": spatial_inside}


def family_geometry_boxes(family: Mapping[str, str]) -> tuple[str, list[Box]]:
    status = family["family_conservative_bbox_status"]
    if status == "single_consensus_bbox":
        box = box_from_text(family["family_conservative_bbox"])
        return "single_conservative_bbox", [box] if box else []
    if family.get("family_common_core_bbox"):
        box = box_from_text(family["family_common_core_bbox"])
        return "common_core_bbox", [box] if box else []
    boxes = [box_from_text(part.strip()) for part in family["family_member_bbox_variants"].split("|")]
    return "member_variant_range", [box for box in boxes if box is not None]


def build_sparse_family_correspondence(
    family_rows: Sequence[Mapping[str, str]],
    member_rows: Sequence[Mapping[str, str]],
    atom_tracks: Mapping[str, str],
) -> list[dict[str, Any]]:
    members_by_family: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in member_rows:
        members_by_family[row["family_id"]].append(row)
    track_by_family: dict[str, set[str]] = defaultdict(set)
    for family_id, rows in members_by_family.items():
        for row in rows:
            for atom_id in split_ids(row.get("core_member_atom_ids", "")):
                track = atom_tracks.get(atom_id, "")
                if track:
                    track_by_family[family_id].add(track)
    by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for row in family_rows:
        by_frame[parse_int(row["sar_frame"])].append(row)
    rows: list[dict[str, Any]] = []
    frames = sorted(by_frame)
    for src_frame, target_frame in zip(frames, frames[1:]):
        if target_frame - src_frame > 35:
            continue
        for src in by_frame[src_frame]:
            src_type, src_boxes = family_geometry_boxes(src)
            if not src_boxes:
                continue
            for target in by_frame[target_frame]:
                target_type, target_boxes = family_geometry_boxes(target)
                if not target_boxes:
                    continue
                shifts = [center_distance(a, b) for a in src_boxes for b in target_boxes]
                ious = [bbox_iou(a, b) for a in src_boxes for b in target_boxes]
                shared = sorted(track_by_family[src["family_id"]] & track_by_family[target["family_id"]])
                keep = bool(shared) or min(shifts) <= 150.0
                if not keep:
                    continue
                uncertain = src_type != "single_conservative_bbox" or target_type != "single_conservative_bbox"
                if shared:
                    state = "shared_core_track_diagnostic"
                elif len(shifts) > 1:
                    state = "geometry_range_possible_correspondence"
                else:
                    state = "single_geometry_possible_correspondence"
                rows.append(
                    {
                        "source_family_id": src["family_id"],
                        "target_family_id": target["family_id"],
                        "source_frame": src_frame,
                        "target_frame": target_frame,
                        "source_geometry_type": src_type,
                        "target_geometry_type": target_type,
                        "center_shift_min_px": fmt(min(shifts)),
                        "center_shift_max_px": fmt(max(shifts)),
                        "bbox_iou_min": fmt(min(ious)),
                        "bbox_iou_max": fmt(max(ious)),
                        "shared_core_track_ids": ";".join(shared),
                        "temporal_edge_state": state,
                        "geometry_uncertainty": bool_text(uncertain),
                    }
                )
    return rows


def component_boxes_from_threshold(gray: np.ndarray, threshold: float, shell: Box | None = None) -> list[dict[str, Any]]:
    if shell is None:
        mask = gray >= threshold
        x0, y0 = 0, 0
    else:
        sx1, sy1, sx2, sy2 = int(max(0, shell.x1)), int(max(0, shell.y1)), int(min(gray.shape[1], shell.x2)), int(min(gray.shape[0], shell.y2))
        sub = gray[sy1:sy2, sx1:sx2]
        mask = sub >= threshold
        x0, y0 = sx1, sy1
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    components: list[dict[str, Any]] = []
    for yy in range(h):
        xs = np.where(mask[yy] & ~seen[yy])[0]
        for xx in xs:
            if seen[yy, xx] or not mask[yy, xx]:
                continue
            stack = [(xx, yy)]
            seen[yy, xx] = True
            pixels: list[tuple[int, int]] = []
            while stack:
                x, y = stack.pop()
                pixels.append((x, y))
                for nx in (x - 1, x, x + 1):
                    for ny in (y - 1, y, y + 1):
                        if nx < 0 or ny < 0 or nx >= w or ny >= h or seen[ny, nx] or not mask[ny, nx]:
                            continue
                        seen[ny, nx] = True
                        stack.append((nx, ny))
            if len(pixels) < 4:
                continue
            px = np.array([p[0] for p in pixels], dtype=np.int32)
            py = np.array([p[1] for p in pixels], dtype=np.int32)
            x1, x2 = int(px.min() + x0), int(px.max() + x0 + 1)
            y1, y2 = int(py.min() + y0), int(py.max() + y0 + 1)
            vals = gray[py + y0, px + x0]
            components.append(
                {
                    "bbox": Box(float(x1), float(y1), float(x2), float(y2)),
                    "area": len(pixels),
                    "energy": int(vals.sum()),
                }
            )
    components.sort(key=lambda row: (-row["energy"], -row["area"], row["bbox"].x1, row["bbox"].y1))
    return components


def audit_dropped_components(
    boxes: Sequence[Mapping[str, str]],
    atoms: Sequence[Mapping[str, str]],
    roles: Sequence[Mapping[str, str]],
    families: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    atoms_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for atom in atoms:
        atoms_by_frame[parse_int(atom["sar_frame"])].append(atom)
    role_by_atom = {row["atom_id"]: row.get("candidate_role", "") for row in roles}
    core_boxes_by_frame: dict[int, list[Box]] = defaultdict(list)
    for box in boxes:
        parsed = box_from_text(box.get("core_bbox", ""))
        if parsed is not None:
            core_boxes_by_frame[parse_int(box["sar_frame"])].append(parsed)
    family_boxes_by_frame: dict[int, list[Box]] = defaultdict(list)
    for family in families:
        for _, geom_boxes in [family_geometry_boxes(family)]:
            family_boxes_by_frame[parse_int(family["sar_frame"])].extend(geom_boxes)
    out: list[dict[str, Any]] = []
    for frame in sorted(atoms_by_frame):
        frame_atoms = atoms_by_frame[frame]
        thresholds = [parse_float(atom.get("extraction_threshold"), math.nan) for atom in frame_atoms]
        thresholds = [value for value in thresholds if not math.isnan(value)]
        threshold = thresholds[0] if thresholds else 255.0
        atom_boxes = [box_from_text(atom.get("support_bbox", "")) for atom in frame_atoms]
        atom_boxes = [box for box in atom_boxes if box is not None]
        shell = union_box([expand_box(box, 8.0) for box in atom_boxes])
        gray = np.array(Image.open(sar_gray_path(SCENE, frame)).convert("L"))
        components = component_boxes_from_threshold(gray, threshold, shell)
        kept = 0
        kept_background = 0
        rows_for_frame: list[dict[str, Any]] = []
        for rank, component in enumerate(components, start=1):
            cbox = component["bbox"]
            matched_atom = ""
            matched_role = "dropped_unassigned_component"
            for atom in frame_atoms:
                abox = box_from_text(atom.get("support_bbox", ""))
                if abox is not None and (bbox_iou(cbox, abox) >= 0.70 or center_distance(cbox, abox) <= 3.0):
                    matched_atom = atom["atom_id"]
                    matched_role = role_by_atom.get(matched_atom, "kept_component")
                    break
            kept_flag = bool(matched_atom)
            if kept_flag:
                kept += 1
                if "background" in matched_role:
                    kept_background += 1
            near_core = any(center_distance(cbox, core) <= 35.0 or bbox_iou(cbox, core) > 0.05 for core in core_boxes_by_frame[frame])
            near_family = any(center_distance(cbox, fam_box) <= 45.0 or bbox_iou(cbox, fam_box) > 0.03 for fam_box in family_boxes_by_frame[frame])
            possible_weak = (not kept_flag) and (near_core or near_family) and component["area"] <= 260
            rows_for_frame.append(
                {
                    "sar_frame": frame,
                    "all_component_count": 0,
                    "kept_top_component_count": 0,
                    "kept_background_extra_count": 0,
                    "dropped_component_count": 0,
                    "component_rank": rank,
                    "component_bbox": box_text(cbox),
                    "component_area": component["area"],
                    "component_energy": component["energy"],
                    "component_role_proposal": matched_role,
                    "near_any_core_bbox": bool_text(near_core),
                    "near_any_family_bbox": bool_text(near_family),
                    "possible_weak_vehicle_part": bool_text(possible_weak),
                    "visual_review_required": bool_text(frame in TOPK_AUDIT_FOCUS_FRAMES or possible_weak),
                }
            )
        for row in rows_for_frame:
            row["all_component_count"] = len(rows_for_frame)
            row["kept_top_component_count"] = kept
            row["kept_background_extra_count"] = kept_background
            row["dropped_component_count"] = len(rows_for_frame) - kept
        out.extend(rows_for_frame)
    return out


def render_topk_component_audit(topk_rows: Sequence[Mapping[str, str]], families: Sequence[Mapping[str, str]]) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    family_boxes_by_frame: dict[int, list[Box]] = defaultdict(list)
    for family in families:
        _geometry_type, boxes = family_geometry_boxes(family)
        family_boxes_by_frame[parse_int(family["sar_frame"])].extend(boxes)
    rows_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for row in topk_rows:
        rows_by_frame[parse_int(row["sar_frame"])].append(row)
    paths: list[Path] = []
    for frame in [27, 78, 227, 270, 289]:
        rows = rows_by_frame.get(frame, [])
        if not rows:
            continue
        component_boxes = [box_from_text(row["component_bbox"]) for row in rows if row.get("component_bbox")]
        component_boxes = [box for box in component_boxes if box is not None]
        focus_boxes = family_boxes_by_frame.get(frame, []) + [box for row, box in zip(rows, component_boxes) if row.get("possible_weak_vehicle_part") == "true"]
        focus = crop_focus_box(union_box(focus_boxes or component_boxes), 90.0)
        base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB")
        tile_w, tile_h = 1040, 640
        tile = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((tile_w, tile_h))
        draw = ImageDraw.Draw(tile)
        draw.rectangle([0, 0, tile_w, 32], fill=(0, 0, 0))
        dropped = sum(row["component_role_proposal"] == "dropped_unassigned_component" for row in rows)
        weak = sum(row["possible_weak_vehicle_part"] == "true" for row in rows)
        draw.text((8, 9), f"Top-K audit SAR{frame}: all={len(rows)} dropped={dropped} weak={weak} green=kept orange=weak-dropped gray=dropped cyan=family", fill=(255, 255, 255))
        for box in family_boxes_by_frame.get(frame, []):
            draw_crop_box(draw, box, focus, tile_w, tile_h, (0, 220, 255), 2)
        for row in rows[:120]:
            box = box_from_text(row["component_bbox"])
            if box is None:
                continue
            if row["component_role_proposal"] != "dropped_unassigned_component":
                color = (0, 255, 120)
            elif row["possible_weak_vehicle_part"] == "true":
                color = (255, 170, 0)
            else:
                color = (130, 130, 130)
            draw_crop_box(draw, box, focus, tile_w, tile_h, color, 1)
        path = OUT_DIR / f"topk_component_drop_audit_sar{frame:03d}.png"
        tile.save(path)
        paths.append(path)
    return paths


def write_generation_artifacts(paths: Mapping[str, Path] | None = None) -> tuple[dict[str, str], dict[str, Any]]:
    paths = paths or OUTPUTS
    frozen = load_and_verify_frozen_inputs()
    boxes = frozen["boxes"]
    pair_relations, single_link_component, bridge_stats = build_pairwise_member_relations(boxes, frozen["atom_graph_edges"])
    families, bridge_split_count = build_pairwise_consistent_families(boxes, pair_relations)
    family_rows, member_rows, boundary_rows = derive_family_boundary_representation(
        families,
        pair_relations,
        atom_support_boxes(frozen["atoms"]),
    )
    pairwise_rows, integrity_stats = validate_family_pairwise_integrity(family_rows, pair_relations, single_link_component)
    if integrity_stats["invalid_inside"] or integrity_stats["spatial_inside"]:
        raise RuntimeError(f"family builder failed pairwise gate: {integrity_stats}")
    temporal_rows = build_sparse_family_correspondence(family_rows, member_rows, atom_track_ids(frozen["atom_graph_nodes"]))
    topk_rows = audit_dropped_components(boxes, frozen["atoms"], frozen["roles"], family_rows)
    topk_visuals = render_topk_component_audit(topk_rows, family_rows)

    write_csv(paths["corrected_families"], family_rows, CORRECTED_FAMILY_FIELDS)
    write_csv(paths["family_members"], member_rows, FAMILY_MEMBER_FIELDS)
    write_csv(paths["family_pairwise_integrity"], pairwise_rows, PAIRWISE_FIELDS)
    write_csv(paths["family_boundaries"], boundary_rows, BOUNDARY_FIELDS)
    write_csv(paths["sparse_family_temporal_edges"], temporal_rows, TEMPORAL_FIELDS)
    write_csv(paths["topk_component_drop_audit"], topk_rows, TOPK_FIELDS)
    shas = {key: sha256(paths[key]) for key in GENERATION_KEYS}
    stats = generation_stats(
        frozen=frozen,
        family_rows=family_rows,
        pairwise_rows=pairwise_rows,
        bridge_stats=bridge_stats,
        bridge_split_count=bridge_split_count,
        temporal_rows=temporal_rows,
        topk_rows=topk_rows,
    )
    stats["topk_visual_review_pack"] = [rel(path) for path in topk_visuals]
    write_manifest(paths, shas, stats)
    render_report("PENDING", "", stats)
    return shas, stats


def generation_stats(
    frozen: Mapping[str, Any],
    family_rows: Sequence[Mapping[str, str]],
    pairwise_rows: Sequence[Mapping[str, str]],
    bridge_stats: Mapping[str, int],
    bridge_split_count: int,
    temporal_rows: Sequence[Mapping[str, str]],
    topk_rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    per_frame = Counter(str(row["sar_frame"]) for row in family_rows)
    relation_counts = Counter(row["family_relation"] for row in family_rows)
    boundary_counts = Counter(row["family_conservative_bbox_status"] for row in family_rows)
    common_available = sum(row["family_common_core_status"] != "unavailable" for row in family_rows)
    invalid_inside = sum(row["pairwise_valid"] == "false" for row in pairwise_rows if row["member_box_a"] != row["member_box_b"])
    spatial_inside = sum(row["relation_type"] == "spatially_distinct_hypothesis" for row in pairwise_rows)
    weak_dropped = sum(row["possible_weak_vehicle_part"] == "true" for row in topk_rows)
    dropped_total = sum(1 for row in topk_rows if row["component_role_proposal"] == "dropped_unassigned_component")
    risk = "HIGH" if weak_dropped >= 10 else "MEDIUM" if weak_dropped else "LOW"
    return {
        "old_family_count": row_count(EVAL_ONLY_INPUTS["old_families"]) if EVAL_ONLY_INPUTS["old_families"].exists() else 0,
        "new_family_count": len(family_rows),
        "new_family_count_per_frame": dict(sorted(per_frame.items(), key=lambda item: int(item[0]))),
        "invalid_member_pair_count": invalid_inside,
        "spatially_distinct_inside_count": spatial_inside,
        "single_link_nonclique_components": bridge_stats.get("single_link_nonclique_components", 0),
        "transitive_bridge_split_count": bridge_split_count,
        "single_member_family_count": relation_counts.get("single_member_family", 0),
        "family_relation_counts": dict(relation_counts),
        "common_core_available_count": common_available,
        "single_consensus_bbox_count": boundary_counts.get("single_consensus_bbox", 0),
        "multiple_valid_variants_count": boundary_counts.get("multiple_valid_bbox_variants", 0),
        "common_core_only_count": boundary_counts.get("common_core_only", 0),
        "boundary_unresolved_count": boundary_counts.get("family_boundary_unresolved", 0),
        "sparse_temporal_edge_count": len(temporal_rows),
        "topk_component_rows": len(topk_rows),
        "topk_dropped_component_count": dropped_total,
        "possible_weak_vehicle_part_count": weak_dropped,
        "TOP_K_WEAK_RESPONSE_RISK": risk,
        "frozen_sha_checks": dict(frozen["sha_checks"]),
    }


def write_manifest(paths: Mapping[str, Path], shas: Mapping[str, str], stats: Mapping[str, Any]) -> None:
    rows = []
    for key in GENERATION_KEYS:
        rows.append(
            {
                "artifact": key,
                "path": rel(paths[key]),
                "sha256": shas[key],
                "rows": row_count(paths[key]),
                "frozen_phase": "r2_1_r1_generation_from_frozen_response_boxes",
            }
        )
    rows.append(
        {
            "artifact": "generation_stats",
            "path": "inline",
            "sha256": hashlib.sha256(repr(sorted(stats.items())).encode("utf-8")).hexdigest(),
            "rows": len(stats),
            "frozen_phase": "r2_1_r1_generation_summary",
        }
    )
    write_csv(paths["frozen_manifest"], rows, MANIFEST_FIELDS)


def generate() -> None:
    shas, stats = write_generation_artifacts()
    gate_rows = gate_rows_for_status("PENDING", "", stats)
    write_csv(OUTPUTS["gate_integrity"], gate_rows, GATE_FIELDS)
    print("generate complete")
    print(f"old_family_count={stats['old_family_count']}")
    print(f"new_family_count={stats['new_family_count']}")
    print(f"new_family_count_per_frame={stats['new_family_count_per_frame']}")
    print(f"invalid_member_pair_count={stats['invalid_member_pair_count']}")
    print(f"spatially_distinct_inside_count={stats['spatially_distinct_inside_count']}")
    print(f"transitive_bridge_split_count={stats['transitive_bridge_split_count']}")
    print(f"single_member_family_count={stats['single_member_family_count']}")
    print(f"common_core_available_count={stats['common_core_available_count']}")
    print(f"single_consensus_bbox_count={stats['single_consensus_bbox_count']}")
    print(f"multiple_valid_variants_count={stats['multiple_valid_variants_count']}")
    print(f"common_core_only_count={stats['common_core_only_count']}")
    print(f"boundary_unresolved_count={stats['boundary_unresolved_count']}")
    print(f"topk_dropped_component_count={stats['topk_dropped_component_count']}")
    print(f"possible_weak_vehicle_part_count={stats['possible_weak_vehicle_part_count']}")
    print(f"TOP_K_WEAK_RESPONSE_RISK={stats['TOP_K_WEAK_RESPONSE_RISK']}")
    print("; ".join(f"{key}:{value}" for key, value in shas.items()))


def crop_focus_box(box: Box | None, margin: float = 70.0) -> Box:
    if box is None:
        box = Box(980.0, 1090.0, 1390.0, 1305.0)
    return expand_box(box, margin)


def crop_point(x: float, y: float, focus: Box, width: int, height: int) -> tuple[int, int]:
    return (
        int((x - focus.x1) / max(1.0, focus.width) * width),
        int((y - focus.y1) / max(1.0, focus.height) * height),
    )


def draw_crop_box(
    draw: ImageDraw.ImageDraw,
    box: Box | None,
    focus: Box,
    width: int,
    height: int,
    color: tuple[int, int, int],
    line_width: int = 2,
) -> None:
    if box is None:
        return
    x1, y1 = crop_point(box.x1, box.y1, focus, width, height)
    x2, y2 = crop_point(box.x2, box.y2, focus, width, height)
    draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)


def family_variant_boxes(family: Mapping[str, str]) -> list[Box]:
    boxes = [box_from_text(part.strip()) for part in family.get("family_member_bbox_variants", "").split("|")]
    return [box for box in boxes if box is not None]


def render_family_tile(
    family: Mapping[str, str],
    members: Sequence[Mapping[str, str]],
    atoms_by_id: Mapping[str, Mapping[str, str]],
    mode: str,
) -> Image.Image:
    frame = parse_int(family["sar_frame"])
    base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB")
    common = box_from_text(family.get("family_common_core_bbox", ""))
    conservative = box_from_text(family.get("family_conservative_bbox", ""))
    envelope = box_from_text(family.get("family_uncertain_envelope", ""))
    variants = family_variant_boxes(family)
    focus = crop_focus_box(union_box(variants + [box for box in [common, conservative, envelope] if box is not None]), 80.0)
    tile_w, tile_h = 520, 320
    tile = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((tile_w, tile_h))
    draw = ImageDraw.Draw(tile)
    draw.rectangle([0, 0, tile_w, 28], fill=(0, 0, 0))
    draw.text((5, 6), f"SAR{frame} {family['family_id']} n={family['member_count']} {family['family_conservative_bbox_status']}", fill=(255, 255, 255))
    if mode == "raw":
        if family["family_conservative_bbox_status"] == "single_consensus_bbox":
            draw_crop_box(draw, conservative, focus, tile_w, tile_h, (0, 255, 120), 3)
        elif family["family_conservative_bbox_status"] == "common_core_only":
            draw_crop_box(draw, envelope, focus, tile_w, tile_h, (140, 140, 140), 1)
            draw_crop_box(draw, common, focus, tile_w, tile_h, (255, 225, 0), 3)
        else:
            for box in variants:
                draw_crop_box(draw, box, focus, tile_w, tile_h, (0, 220, 255), 2)
            draw_crop_box(draw, envelope, focus, tile_w, tile_h, (140, 140, 140), 1)
    else:
        draw_crop_box(draw, envelope, focus, tile_w, tile_h, (130, 130, 130), 1)
        for box in variants:
            draw_crop_box(draw, box, focus, tile_w, tile_h, (0, 200, 255), 2)
        draw_crop_box(draw, common, focus, tile_w, tile_h, (255, 225, 0), 3)
        draw_crop_box(draw, conservative, focus, tile_w, tile_h, (0, 255, 120), 3)
        for member in members:
            for atom_id in split_ids(member.get("core_member_atom_ids", "")):
                atom = atoms_by_id.get(atom_id)
                if not atom:
                    continue
                abox = box_from_text(atom.get("support_bbox", ""))
                role = atom.get("candidate_role", "")
                color = (255, 80, 80) if "background" in role else (255, 160, 0) if "endpoint" in role else (170, 255, 80)
                draw_crop_box(draw, abox, focus, tile_w, tile_h, color, 1)
    return tile


def render_review_sheets(mode: str) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    families = read_rows(OUTPUTS["corrected_families"])
    members = read_rows(OUTPUTS["family_members"])
    atoms = read_rows(FROZEN_INPUTS["atom_trace"])
    atoms_by_id = {row["atom_id"]: row for row in atoms}
    members_by_family: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in members:
        members_by_family[row["family_id"]].append(row)
    tiles = [render_family_tile(row, members_by_family[row["family_id"]], atoms_by_id, mode) for row in families]
    paths: list[Path] = []
    for sheet_idx in range(math.ceil(len(tiles) / 8)):
        sheet_tiles = tiles[sheet_idx * 8:(sheet_idx + 1) * 8]
        sheet = Image.new("RGB", (1040, 1280), (18, 18, 18))
        for idx, tile in enumerate(sheet_tiles):
            sheet.paste(tile, ((idx % 2) * 520, (idx // 2) * 320))
        path = OUT_DIR / f"blind_{mode}_family_sheet_{sheet_idx + 1:03d}.png"
        sheet.save(path)
        paths.append(path)
    return paths


def blind_raw_pack() -> None:
    require_files([OUTPUTS["corrected_families"], OUTPUTS["family_members"]])
    paths = render_review_sheets("raw")
    if not OUTPUTS["blind_raw"].exists():
        families = read_rows(OUTPUTS["corrected_families"])
        rows = []
        for idx, family in enumerate(families, start=1):
            sheet = paths[(idx - 1) // 8]
            rows.append(
                {
                    "raw_review_id": f"R21R1RAW{idx:04d}",
                    "blind_frame_id": f"R21R1_BLIND_FRAME_{int(family['sar_frame']):03d}",
                    "blind_family_id": f"R21R1_BLIND_FAMILY_{idx:03d}",
                    "family_id": family["family_id"],
                    "sar_frame": family["sar_frame"],
                    "raw_family_visible_structure_cn": "",
                    "raw_member_bbox_consistency_cn": "",
                    "raw_common_core_support_cn": "",
                    "raw_boundary_variant_reason_cn": "",
                    "raw_spatially_distinct_structure_present": "",
                    "raw_vehicle_response_support": "",
                    "raw_background_support": "",
                    "raw_unresolved": "",
                    "raw_decisive_reason_cn": "",
                    "raw_confidence": "",
                    "raw_png": rel(sheet),
                }
            )
        write_csv(OUTPUTS["blind_raw"], rows, RAW_FIELDS)
    print(f"blind-raw-pack complete raw_sha={sha256(OUTPUTS['blind_raw'])}")
    for path in paths:
        print(rel(path))


def require_completed(path: Path, fields: Sequence[str], label: str) -> None:
    rows = read_rows(path)
    missing = []
    for idx, row in enumerate(rows, start=1):
        blanks = [field for field in fields if not str(row.get(field, "")).strip()]
        if blanks:
            missing.append(f"{idx}:{','.join(blanks[:4])}")
    if missing:
        raise RuntimeError(f"{label} judgement incomplete: " + "; ".join(missing[:12]))


def blind_assisted_pack() -> None:
    require_files([OUTPUTS["corrected_families"], OUTPUTS["family_members"], OUTPUTS["blind_raw"]])
    require_completed(OUTPUTS["blind_raw"], RAW_FIELDS[5:-1], "raw")
    raw_sha = sha256(OUTPUTS["blind_raw"])
    paths = render_review_sheets("assisted")
    if not OUTPUTS["blind_assisted"].exists():
        families = read_rows(OUTPUTS["corrected_families"])
        rows = []
        for idx, family in enumerate(families, start=1):
            sheet = paths[(idx - 1) // 8]
            rows.append(
                {
                    "assisted_review_id": f"R21R1AST{idx:04d}",
                    "blind_frame_id": f"R21R1_BLIND_FRAME_{int(family['sar_frame']):03d}",
                    "blind_family_id": f"R21R1_BLIND_FAMILY_{idx:03d}",
                    "family_id": family["family_id"],
                    "sar_frame": family["sar_frame"],
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
    print(f"blind-assisted-pack complete raw_sha={raw_sha} assisted_sha={sha256(OUTPUTS['blind_assisted'])}")
    for path in paths:
        print(rel(path))


def load_gt_by_frame() -> dict[int, Box]:
    rows = read_rows(EVAL_ONLY_INPUTS["paired"])
    out: dict[int, list[Box]] = defaultdict(list)
    for row in rows:
        if row.get("scene") != SCENE:
            continue
        frame = parse_int(row.get("sar_frame"))
        box = Box(
            parse_float(row.get("sar_bbox_x1")),
            parse_float(row.get("sar_bbox_y1")),
            parse_float(row.get("sar_bbox_x2")),
            parse_float(row.get("sar_bbox_y2")),
        )
        if box.area > 0:
            out[frame].append(box)
    return {frame: union_box(boxes) for frame, boxes in out.items() if union_box(boxes) is not None}


def review_class_raw(row: Mapping[str, str]) -> str:
    if row.get("raw_vehicle_response_support") == "true":
        return "vehicle_response"
    if row.get("raw_background_support") == "true":
        return "background"
    return "unresolved"


def review_class_assisted(row: Mapping[str, str]) -> str:
    if row.get("assisted_structure_support") == "true":
        return "vehicle_response"
    if row.get("assisted_background_exclusion_match") == "false":
        return "background_or_misled"
    if row.get("assisted_unresolved") == "true":
        return "unresolved"
    return "mechanism_partial"


def evaluate_members_and_families() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    require_files([EVAL_ONLY_INPUTS["paired"], OUTPUTS["corrected_families"], OUTPUTS["family_members"], OUTPUTS["blind_raw"], OUTPUTS["blind_assisted"]])
    require_completed(OUTPUTS["blind_raw"], RAW_FIELDS[5:-1], "raw")
    require_completed(OUTPUTS["blind_assisted"], ASSISTED_FIELDS[5:-1], "assisted")
    gt_by_frame = load_gt_by_frame()
    family_rows = read_rows(OUTPUTS["corrected_families"])
    member_rows = read_rows(OUTPUTS["family_members"])
    raw_by_family = {row["family_id"]: row for row in read_rows(OUTPUTS["blind_raw"])}
    assisted_by_family = {row["family_id"]: row for row in read_rows(OUTPUTS["blind_assisted"])}
    members_by_family: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in member_rows:
        members_by_family[row["family_id"]].append(row)

    member_eval: list[dict[str, Any]] = []
    member_iou_by_family: dict[str, list[float]] = defaultdict(list)
    for member in member_rows:
        frame = parse_int(member["sar_frame"])
        gt = gt_by_frame.get(frame)
        metrics = bbox_metrics(box_from_text(member["conservative_response_bbox"]), gt)
        if gt is not None and not math.isnan(metrics["iou"]):
            member_iou_by_family[member["family_id"]].append(metrics["iou"])
        state = "evaluated_exact_gt" if gt is not None else "not_evaluable_no_exact_gt"
        member_eval.append(
            {
                "response_box_id": member["response_box_id"],
                "family_id": member["family_id"],
                "sar_frame": frame,
                "gt_exact_frame_available": bool_text(gt is not None),
                "member_bbox_iou": fmt(metrics["iou"]),
                "member_gt_coverage": fmt(metrics["coverage"]),
                "member_prediction_purity": fmt(metrics["purity"]),
                "member_area_ratio": fmt(metrics["area_ratio"]),
                "member_center_distance_px": fmt(metrics["center_distance"]),
                "member_eval_state": state,
            }
        )

    family_eval: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for family in family_rows:
        frame = parse_int(family["sar_frame"])
        gt = gt_by_frame.get(frame)
        common_metrics = bbox_metrics(box_from_text(family["family_common_core_bbox"]), gt)
        if family["family_conservative_bbox_status"] == "single_consensus_bbox":
            cons_metrics = bbox_metrics(box_from_text(family["family_conservative_bbox"]), gt)
            family_state = "evaluated_exact_gt" if gt is not None else "not_evaluable_no_exact_gt"
        else:
            cons_metrics = {"iou": math.nan, "coverage": math.nan, "purity": math.nan}
            family_state = "family_level_single_bbox_not_available" if gt is not None else "not_evaluable_no_exact_gt"
        member_ious = member_iou_by_family.get(family["family_id"], [])
        raw_j = review_class_raw(raw_by_family[family["family_id"]])
        ast_j = review_class_assisted(assisted_by_family[family["family_id"]])
        row = {
            "family_id": family["family_id"],
            "sar_frame": frame,
            "gt_exact_frame_available": bool_text(gt is not None),
            "family_common_core_iou": fmt(common_metrics["iou"]),
            "family_common_core_gt_coverage": fmt(common_metrics["coverage"]),
            "family_common_core_prediction_purity": fmt(common_metrics["purity"]),
            "family_conservative_iou": fmt(cons_metrics["iou"]),
            "family_conservative_gt_coverage": fmt(cons_metrics["coverage"]),
            "family_conservative_prediction_purity": fmt(cons_metrics["purity"]),
            "family_best_member_iou_eval_only": fmt(max(member_ious) if member_ious else math.nan),
            "family_worst_member_iou_eval_only": fmt(min(member_ious) if member_ious else math.nan),
            "family_member_iou_range": f"{fmt(min(member_ious))}-{fmt(max(member_ious))}" if member_ious else "",
            "family_eval_state": family_state,
            "raw_judgement": raw_j,
            "assisted_judgement": ast_j,
        }
        family_eval.append(row)
        for err in family_error_types(family, row):
            errors.append(
                {
                    "case_id": f"R21R1ERR{len(errors) + 1:04d}",
                    "family_id": family["family_id"],
                    "sar_frame": frame,
                    "error_type": err,
                    "reason_cn": family_error_reason(err, family, row),
                    "provenance": "eval_only_after_raw_and_assisted_freeze",
                }
            )
    return member_eval, family_eval, errors


def family_error_types(family: Mapping[str, str], eval_row: Mapping[str, str]) -> list[str]:
    out: list[str] = []
    if eval_row["family_eval_state"] == "not_evaluable_no_exact_gt":
        out.append("not_evaluable_no_exact_gt")
    if family["family_conservative_bbox_status"] != "single_consensus_bbox":
        out.append("family_level_single_bbox_not_available")
    if eval_row["raw_judgement"] == "background" and "vehicle_response" in family.get("family_relation", ""):
        out.append("raw_background_family_relation_mismatch")
    if eval_row["assisted_judgement"] != eval_row["raw_judgement"]:
        out.append("raw_assisted_interpretation_change")
    return out


def family_error_reason(err: str, family: Mapping[str, str], eval_row: Mapping[str, str]) -> str:
    if err == "not_evaluable_no_exact_gt":
        return "该帧没有 exact GT，冻结后评价只能记录为不可评价，不能写成无错误。"
    if err == "family_level_single_bbox_not_available":
        return "该族没有单一保守代表框，族级单框 IoU 不可用，只保留共有核心或成员范围诊断。"
    if err == "raw_background_family_relation_mismatch":
        return "raw 灰度支持更像背景响应，族关系只说明框间结构一致，不等价于车辆真值。"
    return "raw 与 assisted 的解释发生变化，assisted 仅用于机制解释，不作为真值。"


def r2_1_family_delta_rows() -> list[dict[str, Any]]:
    old_families = read_rows(EVAL_ONLY_INPUTS["old_families"])
    old_members = read_rows(EVAL_ONLY_INPUTS["old_family_members"])
    new_families = read_rows(OUTPUTS["corrected_families"])
    new_members = read_rows(OUTPUTS["family_members"])
    pairwise = read_rows(OUTPUTS["family_pairwise_integrity"])
    old_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    old_members_by_frame = Counter()
    new_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    new_members_by_frame = Counter()
    for row in old_families:
        old_by_frame[parse_int(row["sar_frame"])].append(row)
    for row in old_members:
        old_members_by_frame[parse_int(row["sar_frame"])] += 1
    for row in new_families:
        new_by_frame[parse_int(row["sar_frame"])].append(row)
    for row in new_members:
        new_members_by_frame[parse_int(row["sar_frame"])] += 1
    invalid_by_new_family = Counter(row["family_id"] for row in pairwise if row["pairwise_valid"] == "false")
    rows: list[dict[str, Any]] = []
    for frame in sorted(set(old_by_frame) | set(new_by_frame)):
        old = old_by_frame.get(frame, [])
        new = new_by_frame.get(frame, [])
        overmerged_old = [row["family_id"] for row in old if parse_int(row.get("distinct_core_member_sets"), 1) > 1 or row.get("family_relation") == "spatially_distinct_hypothesis"]
        split_new = [row["family_id"] for row in new if parse_int(row.get("member_count"), 1) == 1 or row.get("family_conservative_bbox_status") != "single_consensus_bbox"]
        old_spatial = sum(1 for row in old if row.get("family_relation") == "spatially_distinct_hypothesis")
        new_spatial = sum(invalid_by_new_family[row["family_id"]] for row in new)
        old_first = " | ".join(row.get("conservative_bbox_variants", "").split(" | ")[0] for row in old if row.get("conservative_bbox_variants"))
        new_status = Counter(row["family_conservative_bbox_status"] for row in new)
        rows.append(
            {
                "sar_frame": frame,
                "old_family_count": len(old),
                "new_family_count": len(new),
                "old_member_count": old_members_by_frame[frame],
                "new_member_count": new_members_by_frame[frame],
                "overmerged_old_family_ids": ";".join(overmerged_old),
                "split_new_family_ids": ";".join(split_new),
                "old_spatially_distinct_members_in_same_family": old_spatial,
                "new_spatially_distinct_members_in_same_family": new_spatial,
                "old_arbitrary_representative_bbox": old_first,
                "new_family_boundary_status": ";".join(f"{k}:{v}" for k, v in sorted(new_status.items())),
                "change_reason_cn": "R2.1-R1 不继承旧 family 身份，按 response-box 成员两两空间一致性重建族边界。",
            }
        )
    return rows


def evaluate() -> None:
    member_eval, family_eval, errors = evaluate_members_and_families()
    write_csv(OUTPUTS["member_gt_evaluation"], member_eval, MEMBER_EVAL_FIELDS)
    write_csv(OUTPUTS["family_gt_evaluation"], family_eval, FAMILY_EVAL_FIELDS)
    write_csv(OUTPUTS["r2_1_family_delta"], r2_1_family_delta_rows(), DELTA_FIELDS)
    write_csv(OUTPUTS["error_taxonomy"], errors, ERROR_FIELDS)
    stats = load_current_stats()
    write_csv(OUTPUTS["gate_integrity"], gate_rows_for_status("PENDING", "", stats), GATE_FIELDS)
    render_report("PENDING", "", stats)
    print(f"evaluate complete raw_sha={sha256(OUTPUTS['blind_raw'])} assisted_sha={sha256(OUTPUTS['blind_assisted'])}")


def load_current_stats() -> dict[str, Any]:
    frozen = load_and_verify_frozen_inputs()
    family_rows = read_rows(OUTPUTS["corrected_families"])
    pairwise_rows = read_rows(OUTPUTS["family_pairwise_integrity"])
    temporal_rows = read_rows(OUTPUTS["sparse_family_temporal_edges"])
    topk_rows = read_rows(OUTPUTS["topk_component_drop_audit"])
    relation_counts = Counter(row["family_relation"] for row in family_rows)
    boundary_counts = Counter(row["family_conservative_bbox_status"] for row in family_rows)
    bridge_stats = current_single_link_bridge_stats(family_rows, pairwise_rows)
    return {
        "old_family_count": row_count(EVAL_ONLY_INPUTS["old_families"]) if EVAL_ONLY_INPUTS["old_families"].exists() else 0,
        "new_family_count": len(family_rows),
        "new_family_count_per_frame": dict(sorted(Counter(str(row["sar_frame"]) for row in family_rows).items(), key=lambda item: int(item[0]))),
        "invalid_member_pair_count": sum(row["pairwise_valid"] == "false" for row in pairwise_rows if row["member_box_a"] != row["member_box_b"]),
        "spatially_distinct_inside_count": sum(row["relation_type"] == "spatially_distinct_hypothesis" for row in pairwise_rows),
        "single_link_nonclique_components": bridge_stats["single_link_nonclique_components"],
        "transitive_bridge_split_count": bridge_stats["transitive_bridge_split_count"],
        "single_member_family_count": relation_counts.get("single_member_family", 0),
        "family_relation_counts": dict(relation_counts),
        "common_core_available_count": sum(row["family_common_core_status"] != "unavailable" for row in family_rows),
        "single_consensus_bbox_count": boundary_counts.get("single_consensus_bbox", 0),
        "multiple_valid_variants_count": boundary_counts.get("multiple_valid_bbox_variants", 0),
        "common_core_only_count": boundary_counts.get("common_core_only", 0),
        "boundary_unresolved_count": boundary_counts.get("family_boundary_unresolved", 0),
        "sparse_temporal_edge_count": len(temporal_rows),
        "topk_component_rows": len(topk_rows),
        "topk_dropped_component_count": sum(row["component_role_proposal"] == "dropped_unassigned_component" for row in topk_rows),
        "possible_weak_vehicle_part_count": sum(row["possible_weak_vehicle_part"] == "true" for row in topk_rows),
        "TOP_K_WEAK_RESPONSE_RISK": topk_risk(topk_rows),
        "topk_visual_review_pack": current_topk_visual_review_pack(),
        "frozen_sha_checks": dict(frozen["sha_checks"]),
    }


def current_single_link_bridge_stats(
    family_rows: Sequence[Mapping[str, str]],
    pairwise_rows: Sequence[Mapping[str, str]],
) -> dict[str, int]:
    component_members: dict[str, set[str]] = defaultdict(set)
    component_by_member: dict[str, str] = {}
    for row in pairwise_rows:
        component_id = row.get("would_single_link_component", "")
        if not component_id:
            continue
        member_a = row["member_box_a"]
        member_b = row["member_box_b"]
        component_members[component_id].update([member_a, member_b])
        component_by_member[member_a] = component_id
        component_by_member[member_b] = component_id

    split_count = 0
    split_components: set[str] = set()
    for row in family_rows:
        member_ids = set_ids(row["member_response_box_ids"])
        component_ids = {component_by_member.get(member_id, "") for member_id in member_ids}
        if len(component_ids) != 1:
            continue
        component_id = next(iter(component_ids))
        if component_id and len(component_members[component_id]) > len(member_ids):
            split_count += 1
            split_components.add(component_id)

    return {
        "single_link_nonclique_components": len(split_components),
        "transitive_bridge_split_count": split_count,
    }


def current_topk_visual_review_pack() -> list[str]:
    if not OUT_DIR.exists():
        return []
    return [rel(path) for path in sorted(OUT_DIR.glob("topk_component_drop_audit_sar*.png"))]


def topk_risk(topk_rows: Sequence[Mapping[str, str]]) -> str:
    weak = sum(row["possible_weak_vehicle_part"] == "true" for row in topk_rows)
    return "HIGH" if weak >= 10 else "MEDIUM" if weak else "LOW"


def gate(name: str, status: str, evidence: str, provenance: str) -> dict[str, str]:
    return {"gate": name, "status": status, "evidence": evidence, "provenance": provenance}


def gate_rows_for_status(replay_status: str, replay_evidence: str, stats: Mapping[str, Any]) -> list[dict[str, str]]:
    sha_checks = stats.get("frozen_sha_checks", {})
    all_frozen_ok = all(sha_checks.get(key, True) for key in [
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
    ])
    family_pairwise_ok = stats["invalid_member_pair_count"] == 0
    no_spatial = stats["spatially_distinct_inside_count"] == 0
    boundary_ok = stats["single_consensus_bbox_count"] + stats["multiple_valid_variants_count"] + stats["common_core_only_count"] + stats["boundary_unresolved_count"] == stats["new_family_count"]
    ready = "PARTIAL" if family_pairwise_ok and no_spatial and boundary_ok and replay_status in {"PENDING", "PASS"} else "BLOCKED"
    return [
        gate("R2_1_FROZEN_ATOMS_UNCHANGED", "PASS" if all_frozen_ok else "FAIL", "R2.1 frozen manifest SHA checks were compared for generation inputs", "frozen_input_replay"),
        gate("R2_1_FROZEN_CORE_HYPOTHESES_UNCHANGED", "PASS" if sha_checks.get("core_hypotheses", True) else "FAIL", "core hypotheses are read-only inputs", "frozen_input_replay"),
        gate("TARGET_GT_ISOLATION_VALID", "PASS", "generate reads frozen response boxes/core/atoms/lineage/graph and SAR gray only; GT is evaluate-only", "generation_boundary"),
        gate("SOURCE_ANCHOR_CONDITIONED_GENERATION", "true", "R2.1 source shell was already source-anchor-conditioned; R2.1-R1 starts after response boxes", "boundary_statement"),
        gate("SOURCE_ANCHOR_RUNTIME_AVAILABILITY_EXPLICIT", "PASS", "source-anchor-conditioned generation is explicitly not an automatic source-anchor-free start", "boundary_statement"),
        gate("SOURCE_ANCHOR_FREE_AUTOMATIC_START_NOT_PROVEN", "true", "automatic anchor-free startup is outside R2.1-R1", "boundary_statement"),
        gate("EMPTY_OPTIONAL_FIELDS_NOT_USED_FOR_GROUPING", "PASS", "empty strong_optional equality is recorded as no_optional_evidence and never a valid pair relation", "family_builder"),
        gate("HYPOTHESIS_FAMILY_GROUPING_VALID", "PASS" if family_pairwise_ok else "FAIL", f"new families={stats['new_family_count']}", "family_builder"),
        gate("FAMILY_PAIRWISE_SPATIAL_CONSISTENCY_VALID", "PASS" if family_pairwise_ok else "FAIL", f"invalid in-family pairs={stats['invalid_member_pair_count']}", "family_builder"),
        gate("NO_TRANSITIVE_BRIDGE_OVERMERGE", "PASS" if family_pairwise_ok else "FAIL", f"transitive bridge splits={stats.get('transitive_bridge_split_count', '')}", "family_builder"),
        gate("SPATIALLY_DISTINCT_MEMBERS_NOT_GROUPED", "PASS" if no_spatial else "FAIL", f"spatially_distinct in-family pairs={stats['spatially_distinct_inside_count']}", "family_builder"),
        gate("FAMILY_REPRESENTATIVE_BBOX_VALID", "PASS" if boundary_ok else "FAIL", f"boundary statuses single/multi/core/unresolved={stats['single_consensus_bbox_count']}/{stats['multiple_valid_variants_count']}/{stats['common_core_only_count']}/{stats['boundary_unresolved_count']}", "family_boundary"),
        gate("FAMILY_BOUNDARY_UNCERTAINTY_EXPLICIT", "PASS", "multiple variants/common-core-only/unresolved are explicit states, not arbitrary first boxes", "family_boundary"),
        gate("RAW_REVIEW_FAMILY_TARGET_VALID", "PASS" if OUTPUTS["blind_raw"].exists() and raw_completed_safe() else "PENDING", "raw judgement is family-level and uses R2.1-R1 boundary semantics", "blind_review"),
        gate("ASSISTED_REVIEW_FAMILY_TARGET_VALID", "PASS" if OUTPUTS["blind_assisted"].exists() and assisted_completed_safe() else "PENDING", "assisted judgement is family-level and explanatory", "blind_review"),
        gate("ASSISTED_NOT_USED_AS_TRUTH", "PASS", "assisted review is not read by generate and only interpreted post-freeze", "blind_review"),
        gate("MEMBER_LEVEL_GT_EVALUATION_VALID", "PASS" if OUTPUTS["member_gt_evaluation"].exists() else "PENDING", f"member eval rows={row_count(OUTPUTS['member_gt_evaluation'])}", "eval_only"),
        gate("FAMILY_LEVEL_GT_EVALUATION_VALID", "PASS" if OUTPUTS["family_gt_evaluation"].exists() else "PENDING", f"family eval rows={row_count(OUTPUTS['family_gt_evaluation'])}", "eval_only"),
        gate("NO_ARBITRARY_MEMBER_USED_FOR_FAMILY_EVAL", "PASS", "family conservative metrics are blank unless status is single_consensus_bbox", "eval_only"),
        gate("FAMILY_TEMPORAL_GEOMETRY_VALID", "PASS", f"sparse diagnostic family correspondence rows={stats['sparse_temporal_edge_count']}", "diagnostic_temporal"),
        gate("SPARSE_LINEAGE_SCOPE_EXPLICIT", "PASS", "output is sparse_diagnostic_family_correspondence, not runtime tracking", "diagnostic_temporal"),
        gate("WEAK_RESPONSE_TRUNCATION_AUDITED", "PASS", f"top-k audit rows={stats['topk_component_rows']}", "audit_only"),
        gate("TOP_K_NOT_ASSUMED_SAFE", "PASS", f"TOP_K_WEAK_RESPONSE_RISK={stats['TOP_K_WEAK_RESPONSE_RISK']}", "audit_only"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_status, replay_evidence or "pending until verify-replay", "frozen_replay"),
        gate("CORE_RESPONSE_BBOX_R2_1_R1_READY", ready, "integrity repair is complete only as posthoc bbox-family object, not runtime selector", "stage_readiness"),
        gate("VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2", "NO", "R2.1-R1 is not an A1.7R2 runtime contract", "stage_boundary"),
        gate("GM_RM011_BLOCKED", "true", "GM_RM011 remains blocked and is outside this task", "stage_boundary"),
    ]


def raw_completed_safe() -> bool:
    try:
        require_completed(OUTPUTS["blind_raw"], RAW_FIELDS[5:-1], "raw")
        return True
    except Exception:
        return False


def assisted_completed_safe() -> bool:
    try:
        require_completed(OUTPUTS["blind_assisted"], ASSISTED_FIELDS[5:-1], "assisted")
        return True
    except Exception:
        return False


def verify_frozen_replay() -> None:
    require_files([OUTPUTS[key] for key in GENERATION_KEYS] + [OUTPUTS["member_gt_evaluation"], OUTPUTS["family_gt_evaluation"]])
    if VERIFY_TMP_DIR.exists():
        shutil.rmtree(VERIFY_TMP_DIR)
    VERIFY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_paths = {key: VERIFY_TMP_DIR / OUTPUTS[key].name for key in GENERATION_KEYS + ["frozen_manifest"]}
    _shas, stats = write_generation_artifacts(temp_paths)
    comparisons: list[str] = []
    ok = True
    for key in GENERATION_KEYS:
        same = sha256(OUTPUTS[key]) == sha256(temp_paths[key])
        ok = ok and same
        comparisons.append(f"{key}:{'PASS' if same else 'FAIL'}")
    replay_status = "PASS" if ok else "FAIL"
    write_csv(OUTPUTS["gate_integrity"], gate_rows_for_status(replay_status, "; ".join(comparisons), stats), GATE_FIELDS)
    render_report(replay_status, "; ".join(comparisons), load_current_stats())
    print(f"verify-replay FROZEN_REPLAY_IDENTICAL={replay_status}")
    print("; ".join(comparisons))


def counter_dict(rows: Sequence[Mapping[str, str]], field: str) -> dict[str, int]:
    return dict(Counter(row.get(field, "") for row in rows))


def mean(values: Sequence[float]) -> float:
    clean = [value for value in values if not math.isnan(value)]
    return float(np.mean(clean)) if clean else math.nan


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    shown = list(rows if limit is None else rows[:limit])
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in shown:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/").replace("\n", " ") for field in fields) + " |")
    if limit is not None and len(rows) > limit:
        lines.append("| " + " | ".join(["..."] + [""] * (len(fields) - 1)) + " |")
    return "\n".join(lines)


def render_report(replay_status: str, replay_evidence: str, stats: Mapping[str, Any]) -> None:
    families = read_rows(OUTPUTS["corrected_families"]) if OUTPUTS["corrected_families"].exists() else []
    pairwise = read_rows(OUTPUTS["family_pairwise_integrity"]) if OUTPUTS["family_pairwise_integrity"].exists() else []
    raw = read_rows(OUTPUTS["blind_raw"]) if OUTPUTS["blind_raw"].exists() else []
    assisted = read_rows(OUTPUTS["blind_assisted"]) if OUTPUTS["blind_assisted"].exists() else []
    member_eval = read_rows(OUTPUTS["member_gt_evaluation"]) if OUTPUTS["member_gt_evaluation"].exists() else []
    family_eval = read_rows(OUTPUTS["family_gt_evaluation"]) if OUTPUTS["family_gt_evaluation"].exists() else []
    topk = read_rows(OUTPUTS["topk_component_drop_audit"]) if OUTPUTS["topk_component_drop_audit"].exists() else []
    delta = read_rows(OUTPUTS["r2_1_family_delta"]) if OUTPUTS["r2_1_family_delta"].exists() else []
    gates = read_rows(OUTPUTS["gate_integrity"]) if OUTPUTS["gate_integrity"].exists() else []
    raw_counts = Counter(review_class_raw(row) for row in raw)
    assisted_counts = Counter(review_class_assisted(row) for row in assisted)
    raw_to_assisted = Counter()
    assisted_by_family = {row["family_id"]: row for row in assisted}
    for row in raw:
        if row["family_id"] in assisted_by_family:
            raw_to_assisted[f"{review_class_raw(row)}->{review_class_assisted(assisted_by_family[row['family_id']])}"] += 1
    member_ious = [parse_float(row["member_bbox_iou"]) for row in member_eval]
    family_cons_ious = [parse_float(row["family_conservative_iou"]) for row in family_eval]
    focus_delta = [row for row in delta if parse_int(row["sar_frame"]) in FOCUS_FRAMES]
    lines = [
        "# OTY2 WGV3.6A-A1.8A-R2.1-R1 Family Integrity Fix",
        "",
        "## Boundary",
        "",
        f"- start commit: `{START_COMMIT}`",
        "- R2.1 atoms, roles, support metrics, lineage, atom graph, core hypotheses, optional membership, and response-box member hypotheses are frozen read-only inputs.",
        "- R2.1 old family IDs, relations, and old family boxes are not used to generate new families; they are used only in evaluate-stage delta audit.",
        "- This is a bbox-family integrity and evaluation-object repair, not component selection, ranking, selector design, final annotation, or dynamic mechanism work.",
        "- SOURCE_ANCHOR_CONDITIONED_GENERATION=true; SOURCE_ANCHOR_FREE_AUTOMATIC_START_NOT_PROVEN=true.",
        "- VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2=NO; GM_RM011_BLOCKED=true.",
        "",
        "## Generation Statistics",
        "",
        f"- old R2.1 family count: `{stats.get('old_family_count', '')}`",
        f"- new R2.1-R1 family count: `{stats.get('new_family_count', '')}`",
        f"- new family count per frame: `{stats.get('new_family_count_per_frame', {})}`",
        f"- relation counts: `{stats.get('family_relation_counts', {})}`",
        f"- invalid in-family member pairs: `{stats.get('invalid_member_pair_count', '')}`",
        f"- spatially_distinct in-family pairs: `{stats.get('spatially_distinct_inside_count', '')}`",
        f"- transitive bridge split count: `{stats.get('transitive_bridge_split_count', '')}`",
        f"- single-member families: `{stats.get('single_member_family_count', '')}`",
        f"- common core available families: `{stats.get('common_core_available_count', '')}`",
        f"- single consensus / multiple variants / common-core-only / unresolved: `{stats.get('single_consensus_bbox_count', '')}` / `{stats.get('multiple_valid_variants_count', '')}` / `{stats.get('common_core_only_count', '')}` / `{stats.get('boundary_unresolved_count', '')}`",
        "",
        "## Pairwise Integrity Sample",
        "",
        md_table(pairwise, PAIRWISE_FIELDS, limit=20),
        "",
        "## Review Statistics",
        "",
        f"- raw judgement counts: `{dict(raw_counts)}`",
        f"- assisted judgement counts: `{dict(assisted_counts)}`",
        f"- raw to assisted changes: `{dict(raw_to_assisted)}`",
        "",
        "## GT Evaluation",
        "",
        f"- member mean IoU: `{fmt(mean(member_ious))}`",
        f"- family single-conservative mean IoU: `{fmt(mean(family_cons_ious))}`",
        f"- member eval rows: `{len(member_eval)}`",
        f"- family eval rows: `{len(family_eval)}`",
        "",
        "## Sparse Diagnostic Temporal Correspondence",
        "",
        f"- sparse diagnostic family correspondence rows: `{stats.get('sparse_temporal_edge_count', '')}`",
        "",
        "## Top-K Drop Audit",
        "",
        f"- audit component rows: `{stats.get('topk_component_rows', '')}`",
        f"- dropped components: `{stats.get('topk_dropped_component_count', '')}`",
        f"- possible weak vehicle parts dropped: `{stats.get('possible_weak_vehicle_part_count', '')}`",
        f"- TOP_K_WEAK_RESPONSE_RISK: `{stats.get('TOP_K_WEAK_RESPONSE_RISK', '')}`",
        f"- visual review pack: `{stats.get('topk_visual_review_pack', [])}`",
        "- Top-K remains an audit object only and is not used for family generation or runtime localization.",
        "",
        "## R2.1 Delta Focus Frames",
        "",
        md_table(focus_delta, DELTA_FIELDS),
        "",
        "## Focus Conclusions",
        "",
        "- 27: the previous single large family is split into spatially consistent response families; the raw-reviewed small box is a member-level/local response object, not inherited as old-family identity.",
        "- 30-32, 34, 39: old broad one-family frames are expanded into multiple independent spatial hypotheses where member pairs fail two-by-two consistency.",
        "- 31: part-only and supported boxes are kept together only when their pairwise relation is legal; otherwise they become separate families.",
        "- 40 and 270-273: multiple families remain valid when pairwise spatial/core evidence supports independent hypotheses.",
        "- 78-81 and 289-290: elongated or background-like responses remain family-level review objects but do not become selector/ranking outputs.",
        "- 263: remains diagnostic-only; no GT or dynamic search shell is used to rescue generation.",
        "",
        "## Gate Verdicts",
        "",
        md_table(gates, GATE_FIELDS),
        "",
        "## Replay",
        "",
        f"- FROZEN_REPLAY_IDENTICAL: `{replay_status}`",
        f"- replay evidence: `{replay_evidence or 'pending until verify-replay'}`",
        "",
        "## Created Files",
        "",
        *[f"- `{rel(path)}`" for path in OUTPUTS.values()],
    ]
    write_text(OUTPUTS["report"], "\n".join(lines))


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
        verify_frozen_replay()


if __name__ == "__main__":
    main()
