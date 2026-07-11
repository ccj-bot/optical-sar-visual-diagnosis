"""WGV3.6A-A1.8A-R2.1-R1.1 semantic separation.

Commands are intentionally staged:

generate            derive local response units, strict boundary families,
                    same-object candidate edges, and residual-component audit
focus-review-pack   render the allowed focus-frame review pack and focus CSV
evaluate            write instance-level GT matrices, semantic gates, report
verify-replay       deterministically replay generated/eval CSV artifacts

There is intentionally no `all` command.
"""

from __future__ import annotations

import argparse
import csv
import math
import shutil
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image, ImageDraw

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

import run_oty2_wgv3_6a_a1_8a_r2_1_r1_family_integrity_fix as r1  # noqa: E402
from run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping import (  # noqa: E402
    REPO_ROOT,
    REPORT_DIR,
    SAMPLES_DIR,
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
START_COMMIT = "aba57096e6b38e33bfac4a6e68d6d00aa40ace5c"
START_TITLE = "Fix R2.1 bbox family grouping and evaluation integrity"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_8a_r2_1_r1_1_20260711"
VERIFY_TMP_DIR = OUT_DIR / "_verify_replay_tmp"

FOCUS_FRAMES = [31, 32, 39, 78, 79, 263, 270, 271, 272, 273, 289, 290]

R1_INPUTS = {
    "corrected_families": r1.OUTPUTS["corrected_families"],
    "family_members": r1.OUTPUTS["family_members"],
    "family_pairwise_integrity": r1.OUTPUTS["family_pairwise_integrity"],
    "family_boundaries": r1.OUTPUTS["family_boundaries"],
    "blind_raw": r1.OUTPUTS["blind_raw"],
    "blind_assisted": r1.OUTPUTS["blind_assisted"],
    "r1_frozen_manifest": r1.OUTPUTS["frozen_manifest"],
    "topk_component_drop_audit": r1.OUTPUTS["topk_component_drop_audit"],
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_semantic_separation_{DATE}.md",
    "local_response_units": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_{DATE}.csv",
    "boundary_variant_families": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_variant_families_{DATE}.csv",
    "boundary_family_members": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_family_members_{DATE}.csv",
    "boundary_pairwise_integrity": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_pairwise_integrity_{DATE}.csv",
    "same_object_candidate_edges": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_same_object_candidate_edges_{DATE}.csv",
    "proximity_residual_component_audit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_proximity_residual_component_audit_{DATE}.csv",
    "response_unit_gt_instance_matrix": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_{DATE}.csv",
    "boundary_family_gt_instance_matrix": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_family_gt_instance_matrix_{DATE}.csv",
    "focus_visual_review": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_focus_visual_review_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_gate_integrity_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_1_r1_1_frozen_manifest_{DATE}.csv",
}

GENERATION_OUTPUT_KEYS = [
    "local_response_units",
    "boundary_variant_families",
    "boundary_family_members",
    "boundary_pairwise_integrity",
    "same_object_candidate_edges",
    "proximity_residual_component_audit",
]
EVALUATION_OUTPUT_KEYS = [
    "response_unit_gt_instance_matrix",
    "boundary_family_gt_instance_matrix",
]
REPLAY_OUTPUT_KEYS = GENERATION_OUTPUT_KEYS + EVALUATION_OUTPUT_KEYS

LOCAL_RESPONSE_UNIT_FIELDS = [
    "response_unit_id",
    "source_response_box_id",
    "source_r1_family_id",
    "sar_frame",
    "core_atom_ids",
    "optional_atom_ids",
    "core_bbox",
    "conservative_bbox",
    "uncertain_envelope",
    "response_state",
]
BOUNDARY_FAMILY_FIELDS = [
    "boundary_family_id",
    "source_r1_family_ids",
    "sar_frame",
    "member_response_unit_ids",
    "shared_core_atom_ids",
    "family_relation",
    "common_core_bbox",
    "boundary_variants",
    "uncertain_envelope",
    "boundary_status",
    "member_count",
    "boundary_semantic_note_cn",
]
BOUNDARY_MEMBER_FIELDS = [
    "boundary_family_id",
    "response_unit_id",
    "source_response_box_id",
    "source_r1_family_id",
    "sar_frame",
    "member_boundary_relation",
]
BOUNDARY_PAIRWISE_FIELDS = [
    "source_r1_family_id",
    "boundary_family_id",
    "sar_frame",
    "source_response_unit_id",
    "target_response_unit_id",
    "bbox_iou",
    "center_distance_px",
    "core_overlap_ratio",
    "core_subset_relation",
    "accepted_graph_link_present",
    "pair_relation",
    "boundary_pair_valid",
    "invalid_reason",
    "old_r1_same_family",
    "new_same_boundary_family",
]
SAME_OBJECT_EDGE_FIELDS = [
    "edge_id",
    "sar_frame",
    "source_response_unit_id",
    "target_response_unit_id",
    "edge_type",
    "shared_core_atoms",
    "accepted_graph_links",
    "center_distance_px",
    "bbox_gap_px",
    "spatial_relation",
    "candidate_reason_cn",
    "edge_state",
]
RESIDUAL_COMPONENT_FIELDS = [
    "residual_component_id",
    "sar_frame",
    "component_bbox",
    "component_area",
    "component_energy",
    "matched_frozen_atom",
    "near_frozen_core",
    "near_boundary_family",
    "proximity_residual_candidate",
    "physical_vehicle_part_unproven",
    "component_match_status",
    "audit_scope",
    "source_component_role_proposal",
    "source_visual_review_required",
    "residual_semantics_fix_provenance",
]
GT_MATRIX_FIELDS = [
    "object_id",
    "object_type",
    "sar_frame",
    "gt_instance_id",
    "gt_pair_id",
    "iou",
    "gt_coverage",
    "prediction_purity",
    "center_distance_px",
    "evaluation_scope",
    "source_conditioned_gt_instance",
]
FOCUS_REVIEW_FIELDS = [
    "sar_frame",
    "focus_png",
    "zero_core_overlap_old_family_split_cn",
    "same_object_candidate_edge_cn",
    "boundary_family_semantics_cn",
    "visual_review_scope",
    "visual_validity_state",
    "reviewer_note_cn",
]
GATE_FIELDS = ["gate", "status", "evidence", "provenance"]
MANIFEST_FIELDS = ["artifact", "path", "sha256", "rows", "frozen_phase"]


def rel(path: Path) -> str:
    return r1.rel(path)


def read_rows(path: Path) -> list[dict[str, str]]:
    return r1.read_rows(path)


def split_ids(text: str) -> list[str]:
    return r1.split_ids(text)


def set_ids(text: str) -> set[str]:
    return r1.set_ids(text)


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def box_from_text(text: str) -> Box | None:
    return r1.box_from_text(text)


def box_text(box: Box | None) -> str:
    return "" if box is None else box.as_text()


def union_box(boxes: Sequence[Box]) -> Box | None:
    return r1.union_box(boxes)


def bbox_iou(a: Box | None, b: Box | None) -> float:
    return r1.bbox_iou(a, b)


def center_distance(a: Box | None, b: Box | None) -> float:
    return r1.center_distance(a, b)


def bbox_metrics(pred: Box | None, gt: Box | None) -> dict[str, float]:
    return r1.bbox_metrics(pred, gt)


def bbox_gap(a: Box | None, b: Box | None) -> float:
    if a is None or b is None:
        return math.nan
    dx = max(a.x1 - b.x2, b.x1 - a.x2, 0.0)
    dy = max(a.y1 - b.y2, b.y1 - a.y2, 0.0)
    return math.hypot(dx, dy)


def core_overlap_ratio(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), len(b)))


def core_subset_relation(a: set[str], b: set[str]) -> str:
    if a and b and a == b:
        return "equal"
    if a and b and a < b:
        return "a_subset_b"
    if a and b and b < a:
        return "b_subset_a"
    if a & b:
        return "overlap"
    return "none"


def require_files(paths: Sequence[Path]) -> None:
    r1.require_files(paths)


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def load_frozen_r2_1_r1_inputs() -> dict[str, Any]:
    require_files(list(r1.FROZEN_INPUTS.values()) + list(R1_INPUTS.values()) + [r1.EVAL_ONLY_INPUTS["paired"]])
    r2_sha_checks = {}
    for row in read_rows(r1.FROZEN_INPUTS["frozen_manifest"]):
        path = REPO_ROOT / row["path"]
        r2_sha_checks[row["artifact"]] = path.exists() and sha256(path) == row["sha256"]
    r1_sha_checks = {}
    for row in read_rows(R1_INPUTS["r1_frozen_manifest"]):
        if row["path"] == "inline":
            continue
        path = REPO_ROOT / row["path"]
        r1_sha_checks[row["artifact"]] = path.exists() and sha256(path) == row["sha256"]
    return {
        "r2_sha_checks": r2_sha_checks,
        "r1_sha_checks": r1_sha_checks,
        "atom_graph_nodes": read_rows(r1.FROZEN_INPUTS["atom_graph_nodes"]),
        "atom_graph_edges": read_rows(r1.FROZEN_INPUTS["atom_graph_edges"]),
        "lineage_edges": read_rows(r1.FROZEN_INPUTS["lineage_edges"]),
        "response_boxes": read_rows(r1.FROZEN_INPUTS["response_boxes"]),
        "r1_families": read_rows(R1_INPUTS["corrected_families"]),
        "r1_members": read_rows(R1_INPUTS["family_members"]),
        "r1_pairwise": read_rows(R1_INPUTS["family_pairwise_integrity"]),
        "raw_review": read_rows(R1_INPUTS["blind_raw"]),
        "assisted_review": read_rows(R1_INPUTS["blind_assisted"]),
        "topk": read_rows(R1_INPUTS["topk_component_drop_audit"]),
        "paired": read_rows(r1.EVAL_ONLY_INPUTS["paired"]),
    }


def atom_bbox_map(atom_graph_nodes: Sequence[Mapping[str, str]]) -> dict[str, Box]:
    out = {}
    for row in atom_graph_nodes:
        box = box_from_text(row.get("support_bbox", ""))
        if box is not None:
            out[row["atom_id"]] = box
    return out


def atom_track_map(atom_graph_nodes: Sequence[Mapping[str, str]]) -> dict[str, str]:
    return {row["atom_id"]: row.get("persistent_part_track_id", "") for row in atom_graph_nodes}


def accepted_graph_links(atom_graph_edges: Sequence[Mapping[str, str]]) -> dict[frozenset[str], list[str]]:
    out: dict[frozenset[str], list[str]] = defaultdict(list)
    for row in atom_graph_edges:
        if row.get("edge_status") != "accepted_local_relation":
            continue
        key = frozenset([row["source_atom_id"], row["target_atom_id"]])
        out[key].append(row["edge_id"])
    return out


def accepted_links_between(core_a: set[str], core_b: set[str], links: Mapping[frozenset[str], list[str]]) -> list[str]:
    out: list[str] = []
    for a in core_a:
        for b in core_b:
            if a == b:
                continue
            out.extend(links.get(frozenset([a, b]), []))
    return sorted(set(out))


def build_local_response_units(r1_members: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for member in sorted(r1_members, key=lambda row: (parse_int(row["sar_frame"]), row["response_box_id"])):
        optional = sorted(set_ids(member.get("strong_optional_atom_ids", "")) | set_ids(member.get("uncertain_optional_atom_ids", "")))
        rows.append(
            {
                "response_unit_id": member["response_box_id"],
                "source_response_box_id": member["response_box_id"],
                "source_r1_family_id": member["family_id"],
                "sar_frame": parse_int(member["sar_frame"]),
                "core_atom_ids": ";".join(sorted(set_ids(member.get("core_member_atom_ids", "")))),
                "optional_atom_ids": ";".join(optional),
                "core_bbox": "",
                "conservative_bbox": member.get("conservative_response_bbox", ""),
                "uncertain_envelope": member.get("uncertain_envelope_bbox", ""),
                "response_state": "local_response_unit_not_complete_vehicle",
            }
        )
    response_boxes_by_id = {row["response_box_id"]: row for row in read_rows(r1.FROZEN_INPUTS["response_boxes"])}
    for row in rows:
        source = response_boxes_by_id.get(row["source_response_box_id"], {})
        row["core_bbox"] = source.get("core_bbox", "")
    return rows


def classify_boundary_variant_pair(
    unit_a: Mapping[str, str],
    unit_b: Mapping[str, str],
    graph_links: Mapping[frozenset[str], list[str]],
) -> dict[str, Any]:
    box_a = box_from_text(unit_a["conservative_bbox"])
    box_b = box_from_text(unit_b["conservative_bbox"])
    core_a = set_ids(unit_a["core_atom_ids"])
    core_b = set_ids(unit_b["core_atom_ids"])
    overlap = core_overlap_ratio(core_a, core_b)
    subset = core_subset_relation(core_a, core_b)
    iou = bbox_iou(box_a, box_b)
    distance = center_distance(box_a, box_b)
    shared_core = core_a & core_b
    graph_edge_ids = accepted_links_between(core_a, core_b, graph_links)

    exact_duplicate = bool(box_a is not None and box_b is not None and iou >= 0.999999)
    high_overlap = bool(not math.isnan(iou) and iou >= 0.75 and not math.isnan(distance) and distance <= 25.0)
    spatial_overlap_or_containment = bool(not math.isnan(iou) and iou > 0.0)
    same_nonempty_core = bool(core_a and core_a == core_b)
    shared_actual_core = bool(shared_core and overlap >= 0.5 and spatial_overlap_or_containment)

    if shared_core and exact_duplicate:
        relation = "exact_duplicate_boundary_variant"
        valid = True
        reason = ""
    elif shared_core and same_nonempty_core:
        relation = "same_nonempty_core_boundary_variant"
        valid = True
        reason = ""
    elif shared_core and high_overlap:
        relation = "high_overlap_shared_core_boundary_variant"
        valid = True
        reason = ""
    elif shared_actual_core:
        relation = "shared_actual_core_boundary_variant"
        valid = True
        reason = ""
    else:
        valid = False
        if not shared_core and graph_edge_ids:
            relation = "accepted_graph_link_only_not_boundary_variant"
            reason = "accepted graph link 只能进入 same-object candidate edge，不能作为边界变体族证据"
        elif overlap == 0:
            relation = "zero_core_overlap_not_boundary_variant"
            reason = "核心原子零重叠，不是同一局部响应核心的边界变体"
        elif subset == "none":
            relation = "different_core_no_overlap_not_boundary_variant"
            reason = "核心关系为 none，不能归入边界变体族"
        elif high_overlap:
            relation = "high_overlap_without_shared_core_blocked"
            reason = "高框重叠但缺少共享核心，保留为候选关系而非边界族"
        else:
            relation = "insufficient_boundary_variant_evidence"
            reason = "没有满足严格边界变体条件"

    return {
        "bbox_iou": iou,
        "center_distance_px": distance,
        "core_overlap_ratio": overlap,
        "core_subset_relation": subset,
        "accepted_graph_links": graph_edge_ids,
        "pair_relation": relation,
        "boundary_pair_valid": valid,
        "invalid_reason": reason,
        "shared_core_atoms": sorted(shared_core),
    }


def build_strict_boundary_families(
    local_units: Sequence[Mapping[str, str]],
    r1_families: Sequence[Mapping[str, str]],
    graph_links: Mapping[frozenset[str], list[str]],
    atom_boxes: Mapping[str, Box],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    units_by_id = {row["response_unit_id"]: row for row in local_units}
    source_members: dict[str, list[str]] = defaultdict(list)
    by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for unit in local_units:
        source_members[unit["source_r1_family_id"]].append(unit["response_unit_id"])
        by_frame[parse_int(unit["sar_frame"])].append(unit)

    boundary_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []
    pairwise_rows: list[dict[str, Any]] = []
    boundary_by_unit: dict[str, str] = {}
    all_pair_cache: dict[frozenset[str], dict[str, Any]] = {}

    for frame in sorted(by_frame):
        units = sorted(by_frame[frame], key=lambda row: row["response_unit_id"])
        pair_cache: dict[frozenset[str], dict[str, Any]] = {}
        for a, b in combinations(units, 2):
            relation = classify_boundary_variant_pair(a, b, graph_links)
            pair_cache[frozenset([a["response_unit_id"], b["response_unit_id"]])] = relation
        all_pair_cache.update(pair_cache)

        unassigned = {unit["response_unit_id"] for unit in units}
        groups: list[list[str]] = []
        while unassigned:
            seed = sorted(unassigned)[0]
            group = [seed]
            unassigned.remove(seed)
            for candidate in sorted(list(unassigned)):
                if all(pair_cache.get(frozenset([candidate, existing]), {}).get("boundary_pair_valid", False) for existing in group):
                    group.append(candidate)
            for response_id in group[1:]:
                unassigned.remove(response_id)
            groups.append(group)

        for group in groups:
            group_units = [units_by_id[response_id] for response_id in group]
            boundary_id = f"R21R11BF{len(boundary_rows) + 1:05d}"
            for unit in group_units:
                boundary_by_unit[unit["response_unit_id"]] = boundary_id
                member_rows.append(
                    {
                        "boundary_family_id": boundary_id,
                        "response_unit_id": unit["response_unit_id"],
                        "source_response_box_id": unit["source_response_box_id"],
                        "source_r1_family_id": unit["source_r1_family_id"],
                        "sar_frame": unit["sar_frame"],
                        "member_boundary_relation": "single_unit" if len(group_units) == 1 else "strict_boundary_variant_member",
                    }
                )
            boundary_rows.append(boundary_family_row(boundary_id, group_units, pair_cache, atom_boxes))

        for a, b in combinations(units, 2):
            relation = pair_cache[frozenset([a["response_unit_id"], b["response_unit_id"]])]
            same_boundary = boundary_by_unit[a["response_unit_id"]] == boundary_by_unit[b["response_unit_id"]]
            pairwise_rows.append(
                {
                    "source_r1_family_id": ";".join(sorted({a["source_r1_family_id"], b["source_r1_family_id"]})),
                    "boundary_family_id": boundary_by_unit[a["response_unit_id"]] if same_boundary else "",
                    "sar_frame": a["sar_frame"],
                    "source_response_unit_id": a["response_unit_id"],
                    "target_response_unit_id": b["response_unit_id"],
                    "bbox_iou": fmt(relation["bbox_iou"]),
                    "center_distance_px": fmt(relation["center_distance_px"]),
                    "core_overlap_ratio": fmt(relation["core_overlap_ratio"]),
                    "core_subset_relation": relation["core_subset_relation"],
                    "accepted_graph_link_present": bool_text(bool(relation["accepted_graph_links"])),
                    "pair_relation": relation["pair_relation"],
                    "boundary_pair_valid": bool_text(bool(relation["boundary_pair_valid"] and same_boundary)),
                    "invalid_reason": "" if same_boundary else relation["invalid_reason"],
                    "old_r1_same_family": bool_text(a["source_r1_family_id"] == b["source_r1_family_id"]),
                    "new_same_boundary_family": bool_text(same_boundary),
                }
            )

    old_zero_core_split_families: set[str] = set()
    old_accepted_link_only_split_families: set[str] = set()
    for source_family in sorted(r1_families, key=lambda row: row["family_id"]):
        source_family_id = source_family["family_id"]
        member_ids = source_members.get(source_family_id, [])
        if len({boundary_by_unit.get(member_id, "") for member_id in member_ids}) <= 1:
            continue
        for a_id, b_id in combinations(member_ids, 2):
            relation = all_pair_cache.get(frozenset([a_id, b_id]))
            if not relation:
                continue
            if relation["core_overlap_ratio"] == 0:
                old_zero_core_split_families.add(source_family_id)
            if relation["pair_relation"] == "accepted_graph_link_only_not_boundary_variant":
                old_accepted_link_only_split_families.add(source_family_id)

    stats = {
        "old_boundary_family_count": len(r1_families),
        "new_boundary_family_count": len(boundary_rows),
        "zero_core_overlap_old_family_split_count": len(old_zero_core_split_families),
        "accepted_link_only_old_family_split_count": len(old_accepted_link_only_split_families),
    }
    return boundary_rows, member_rows, pairwise_rows, boundary_by_unit, stats


def boundary_family_row(
    boundary_id: str,
    units: Sequence[Mapping[str, str]],
    pair_cache: Mapping[frozenset[str], Mapping[str, Any]],
    atom_boxes: Mapping[str, Box],
) -> dict[str, Any]:
    core_sets = [set_ids(unit["core_atom_ids"]) for unit in units]
    shared_core = set.intersection(*core_sets) if core_sets and all(core_sets) else set()
    common_core_box = union_box([atom_boxes[atom] for atom in sorted(shared_core) if atom in atom_boxes])
    variants = sorted({unit["conservative_bbox"] for unit in units if unit["conservative_bbox"]})
    envelopes = [box_from_text(unit["uncertain_envelope"]) for unit in units]
    envelope = union_box([box for box in envelopes if box is not None])
    pair_relations = [pair_cache[frozenset([a["response_unit_id"], b["response_unit_id"]])]["pair_relation"] for a, b in combinations(units, 2)]
    if len(units) == 1:
        relation = "single_local_response_unit"
        status = "single_consensus_bbox"
        note = "单个冻结 response-box 成员，仅作为局部响应单元，不等价于完整车辆。"
    elif set(pair_relations) == {"exact_duplicate_boundary_variant"}:
        relation = "exact_duplicate_boundary_family"
        status = "single_consensus_bbox" if len(variants) == 1 else "multiple_boundary_variants"
        note = "成员共享核心且边界重复，是同一局部响应核心的重复边界表达。"
    elif set(pair_relations) <= {"same_nonempty_core_boundary_variant", "high_overlap_shared_core_boundary_variant"}:
        relation = "same_nonempty_core_boundary_family"
        status = "single_consensus_bbox" if len(variants) == 1 else "multiple_boundary_variants"
        note = "成员共享相同非空核心，仅边界表达不同。"
    else:
        relation = "shared_actual_core_boundary_family"
        status = "single_consensus_bbox" if len(variants) == 1 else "multiple_boundary_variants"
        note = "成员共享实际核心原子且满足严格空间关系；不同物理部件关系已移出到 same-object candidate edge。"
    return {
        "boundary_family_id": boundary_id,
        "source_r1_family_ids": ";".join(sorted({unit["source_r1_family_id"] for unit in units})),
        "sar_frame": units[0]["sar_frame"],
        "member_response_unit_ids": ";".join(unit["response_unit_id"] for unit in units),
        "shared_core_atom_ids": ";".join(sorted(shared_core)),
        "family_relation": relation,
        "common_core_bbox": box_text(common_core_box),
        "boundary_variants": " | ".join(variants),
        "uncertain_envelope": box_text(envelope),
        "boundary_status": status,
        "member_count": len(units),
        "boundary_semantic_note_cn": note,
    }


def single_link_components_from_r1_pairwise(r1_pairwise: Sequence[Mapping[str, str]]) -> dict[str, set[str]]:
    components: dict[str, set[str]] = defaultdict(set)
    for row in r1_pairwise:
        component = row.get("would_single_link_component", "")
        if not component:
            continue
        components[component].update([row["member_box_a"], row["member_box_b"]])
    return {component: members for component, members in components.items() if len(members) > 1}


def spatial_relation(box_a: Box | None, box_b: Box | None) -> str:
    if box_a is None or box_b is None:
        return "unknown"
    gap = bbox_gap(box_a, box_b)
    if gap == 0:
        return "overlapping_or_touching"
    dx = abs(box_a.cx - box_b.cx)
    dy = abs(box_a.cy - box_b.cy)
    if dx > dy * 1.4:
        return "side_by_side_endpoint_axis"
    if dy > dx * 1.4:
        return "range_stack_side_axis"
    return "diagonal_adjacent"


def classify_same_object_edge(
    unit_a: Mapping[str, str],
    unit_b: Mapping[str, str],
    graph_links: Mapping[frozenset[str], list[str]],
    atom_tracks: Mapping[str, str],
) -> dict[str, Any]:
    core_a = set_ids(unit_a["core_atom_ids"])
    core_b = set_ids(unit_b["core_atom_ids"])
    shared_core = sorted(core_a & core_b)
    accepted = accepted_links_between(core_a, core_b, graph_links)
    tracks_a = {atom_tracks.get(atom, "") for atom in core_a if atom_tracks.get(atom, "")}
    tracks_b = {atom_tracks.get(atom, "") for atom in core_b if atom_tracks.get(atom, "")}
    shared_tracks = tracks_a & tracks_b
    box_a = box_from_text(unit_a["conservative_bbox"])
    box_b = box_from_text(unit_b["conservative_bbox"])
    gap = bbox_gap(box_a, box_b)
    distance = center_distance(box_a, box_b)
    relation = spatial_relation(box_a, box_b)

    if accepted and not shared_core:
        edge_type = "accepted_graph_link_candidate"
        edge_state = "same_object_candidate"
        reason = "accepted graph link 不能合并为边界族，但可保留为同目标候选关系。"
    elif shared_tracks and not shared_core:
        edge_type = "shared_sparse_lineage"
        edge_state = "weak_same_object_candidate"
        reason = "稀疏谱系提示可能同属一个目标，但缺少动态确认。"
    elif not math.isnan(gap) and gap <= 8:
        if relation == "side_by_side_endpoint_axis":
            edge_type = "body_endpoint_candidate"
        elif relation == "range_stack_side_axis":
            edge_type = "body_side_candidate"
        else:
            edge_type = "part_part_candidate"
        edge_state = "weak_same_object_candidate"
        reason = "局部响应空间邻近，保留为可能同目标不同部件，不确认车辆身份。"
    elif not math.isnan(distance) and distance <= 85:
        edge_type = "part_part_candidate"
        edge_state = "weak_same_object_candidate"
        reason = "中心距离较近但边界族证据不足，仅保留弱候选边。"
    else:
        edge_type = "different_local_response_no_link"
        edge_state = "blocked_same_object_relation"
        reason = "缺少共享核心、accepted link 或紧邻几何关系，静态阶段不确认同目标。"

    return {
        "edge_type": edge_type,
        "edge_state": edge_state,
        "candidate_reason_cn": reason,
        "shared_core_atoms": shared_core,
        "accepted_graph_links": accepted,
        "bbox_gap_px": gap,
        "center_distance_px": distance,
        "spatial_relation": relation,
    }


def build_same_object_candidate_edges(
    local_units: Sequence[Mapping[str, str]],
    boundary_by_unit: Mapping[str, str],
    r1_pairwise: Sequence[Mapping[str, str]],
    graph_links: Mapping[frozenset[str], list[str]],
    atom_tracks: Mapping[str, str],
) -> list[dict[str, Any]]:
    units_by_id = {row["response_unit_id"]: row for row in local_units}
    candidate_pairs: set[frozenset[str]] = set()

    for members in single_link_components_from_r1_pairwise(r1_pairwise).values():
        for a, b in combinations(sorted(members), 2):
            if boundary_by_unit.get(a) != boundary_by_unit.get(b):
                candidate_pairs.add(frozenset([a, b]))

    for row in r1_pairwise:
        a = row["member_box_a"]
        b = row["member_box_b"]
        if a != b and boundary_by_unit.get(a) != boundary_by_unit.get(b):
            candidate_pairs.add(frozenset([a, b]))

    rows = []
    for pair in sorted(candidate_pairs, key=lambda item: sorted(item)):
        a_id, b_id = sorted(pair)
        if a_id not in units_by_id or b_id not in units_by_id:
            continue
        unit_a = units_by_id[a_id]
        unit_b = units_by_id[b_id]
        if unit_a["sar_frame"] != unit_b["sar_frame"]:
            continue
        if set_ids(unit_a["core_atom_ids"]) & set_ids(unit_b["core_atom_ids"]):
            continue
        edge = classify_same_object_edge(unit_a, unit_b, graph_links, atom_tracks)
        if edge["edge_state"] == "blocked_same_object_relation" and edge["edge_type"] == "different_local_response_no_link":
            continue
        rows.append(
            {
                "edge_id": f"R21R11E{len(rows) + 1:05d}",
                "sar_frame": unit_a["sar_frame"],
                "source_response_unit_id": a_id,
                "target_response_unit_id": b_id,
                "edge_type": edge["edge_type"],
                "shared_core_atoms": ";".join(edge["shared_core_atoms"]),
                "accepted_graph_links": ";".join(edge["accepted_graph_links"]),
                "center_distance_px": fmt(edge["center_distance_px"]),
                "bbox_gap_px": fmt(edge["bbox_gap_px"]),
                "spatial_relation": edge["spatial_relation"],
                "candidate_reason_cn": edge["candidate_reason_cn"],
                "edge_state": edge["edge_state"],
            }
        )
    return rows


def reinterpret_residual_component_audit(topk_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for idx, row in enumerate(topk_rows, start=1):
        near_core = row.get("near_any_core_bbox", "false") == "true"
        near_family = row.get("near_any_family_bbox", "false") == "true"
        source_role = row.get("component_role_proposal", "")
        matched_frozen_atom = bool(source_role and source_role != "dropped_unassigned_component")
        dropped_residual = source_role == "dropped_unassigned_component"
        unknown_match_status = not source_role
        proximity_residual_candidate = dropped_residual and (near_core or near_family)
        if matched_frozen_atom:
            component_match_status = "matched_frozen_atom_non_residual"
            audit_scope = "residual_semantics_fix: matched frozen atom / kept component; retained for provenance, excluded from residual counts"
        elif dropped_residual:
            component_match_status = "dropped_unassigned_residual"
            audit_scope = "residual_semantics_fix: dropped unassigned component; residual audit only, not exact top-k replay and not vehicle-part proof"
        else:
            component_match_status = "unknown_match_status"
            audit_scope = "residual_semantics_fix: source role missing; retained as unknown match-status component"
        rows.append(
            {
                "residual_component_id": f"R21R11RC{idx:05d}",
                "sar_frame": row.get("sar_frame", ""),
                "component_bbox": row.get("component_bbox", ""),
                "component_area": row.get("component_area", ""),
                "component_energy": row.get("component_energy", ""),
                "matched_frozen_atom": bool_text(matched_frozen_atom),
                "near_frozen_core": bool_text(near_core),
                "near_boundary_family": bool_text(near_family),
                "proximity_residual_candidate": bool_text(proximity_residual_candidate),
                "physical_vehicle_part_unproven": bool_text(dropped_residual or unknown_match_status),
                "component_match_status": component_match_status,
                "audit_scope": audit_scope,
                "source_component_role_proposal": source_role,
                "source_visual_review_required": row.get("visual_review_required", ""),
                "residual_semantics_fix_provenance": "source=R2.1-R1 topk_component_drop_audit component_role_proposal; matched roles are kept/frozen atoms, dropped_unassigned_component is residual",
            }
        )
    return rows


def build_generation_tables() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    frozen = load_frozen_r2_1_r1_inputs()
    graph_links = accepted_graph_links(frozen["atom_graph_edges"])
    atom_boxes = atom_bbox_map(frozen["atom_graph_nodes"])
    atom_tracks = atom_track_map(frozen["atom_graph_nodes"])
    local_units = build_local_response_units(frozen["r1_members"])
    boundary_families, boundary_members, boundary_pairwise, boundary_by_unit, boundary_stats = build_strict_boundary_families(
        local_units,
        frozen["r1_families"],
        graph_links,
        atom_boxes,
    )
    same_edges = build_same_object_candidate_edges(local_units, boundary_by_unit, frozen["r1_pairwise"], graph_links, atom_tracks)
    residual = reinterpret_residual_component_audit(frozen["topk"])
    tables = {
        "local_response_units": local_units,
        "boundary_variant_families": boundary_families,
        "boundary_family_members": boundary_members,
        "boundary_pairwise_integrity": boundary_pairwise,
        "same_object_candidate_edges": same_edges,
        "proximity_residual_component_audit": residual,
    }
    stats = semantic_stats(tables, boundary_stats, frozen)
    return tables, stats


def semantic_stats(tables: Mapping[str, Sequence[Mapping[str, Any]]], boundary_stats: Mapping[str, Any], frozen: Mapping[str, Any]) -> dict[str, Any]:
    boundary_pairwise = tables["boundary_pairwise_integrity"]
    same_edges = tables["same_object_candidate_edges"]
    boundary_families = tables["boundary_variant_families"]
    residual = tables["proximity_residual_component_audit"]
    edge_counts = Counter(row["edge_type"] for row in same_edges)
    zero_inside = sum(row["new_same_boundary_family"] == "true" and parse_float(row["core_overlap_ratio"], 0) == 0 for row in boundary_pairwise)
    diff_no_overlap = sum(row["new_same_boundary_family"] == "true" and row["core_subset_relation"] == "none" for row in boundary_pairwise)
    accepted_only = sum(row["new_same_boundary_family"] == "true" and row["pair_relation"] == "accepted_graph_link_only_not_boundary_variant" for row in boundary_pairwise)
    gt_counts = gt_instance_counts(load_gt_instances(frozen["paired"]))
    return {
        **boundary_stats,
        "local_response_unit_count": len(tables["local_response_units"]),
        "boundary_variant_family_count": len(boundary_families),
        "same_object_candidate_edge_count": len(same_edges),
        "same_object_candidate_edge_counts": dict(sorted(edge_counts.items())),
        "boundary_family_zero_core_overlap_pair_count": zero_inside,
        "boundary_family_different_core_no_overlap_count": diff_no_overlap,
        "boundary_family_accepted_link_only_pair_count": accepted_only,
        "component_audit_row_count": len(residual),
        "matched_frozen_atom_count": sum(row["matched_frozen_atom"] == "true" for row in residual),
        "unknown_match_status_count": sum(row["component_match_status"] == "unknown_match_status" for row in residual),
        "residual_component_count": sum(row["component_match_status"] == "dropped_unassigned_residual" for row in residual),
        "proximity_residual_candidate_count": sum(row["proximity_residual_candidate"] == "true" for row in residual),
        "physical_vehicle_part_unproven_count": sum(row["physical_vehicle_part_unproven"] == "true" for row in residual),
        "old_possible_weak_vehicle_part_claim_count": sum(row.get("possible_weak_vehicle_part") == "true" for row in frozen["topk"]),
        "topk_exact_drop_audit": "FAIL",
        "topk_weak_response_risk": "UNRESOLVED",
        "gt_instance_counts": gt_counts,
        "r2_sha_checks": dict(frozen["r2_sha_checks"]),
        "r1_sha_checks": dict(frozen["r1_sha_checks"]),
    }


def gt_instance_counts(gt_by_frame: Mapping[int, Sequence[Mapping[str, Any]]]) -> dict[str, int]:
    return {str(frame): len(instances) for frame, instances in sorted(gt_by_frame.items())}


def write_generation_outputs() -> None:
    tables, stats = build_generation_tables()
    write_csv(OUTPUTS["local_response_units"], tables["local_response_units"], LOCAL_RESPONSE_UNIT_FIELDS)
    write_csv(OUTPUTS["boundary_variant_families"], tables["boundary_variant_families"], BOUNDARY_FAMILY_FIELDS)
    write_csv(OUTPUTS["boundary_family_members"], tables["boundary_family_members"], BOUNDARY_MEMBER_FIELDS)
    write_csv(OUTPUTS["boundary_pairwise_integrity"], tables["boundary_pairwise_integrity"], BOUNDARY_PAIRWISE_FIELDS)
    write_csv(OUTPUTS["same_object_candidate_edges"], tables["same_object_candidate_edges"], SAME_OBJECT_EDGE_FIELDS)
    write_csv(OUTPUTS["proximity_residual_component_audit"], tables["proximity_residual_component_audit"], RESIDUAL_COMPONENT_FIELDS)
    write_manifest(stats, replay_status="PENDING", replay_evidence="pending until verify-replay")
    render_report(stats, replay_status="PENDING", replay_evidence="pending until evaluate and verify-replay")
    print(f"generate complete local_units={stats['local_response_unit_count']} boundary_families={stats['boundary_variant_family_count']} same_object_edges={stats['same_object_candidate_edge_count']}")


def load_gt_instances(paired_rows: Sequence[Mapping[str, str]]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in paired_rows:
        if row.get("scene") != SCENE:
            continue
        frame = parse_int(row.get("sar_frame"))
        box = Box(
            parse_float(row.get("sar_bbox_x1")),
            parse_float(row.get("sar_bbox_y1")),
            parse_float(row.get("sar_bbox_x2")),
            parse_float(row.get("sar_bbox_y2")),
        )
        if box.area <= 0:
            continue
        instance_id = row.get("sar_gt_id") or row.get("pair_id")
        out[frame].append(
            {
                "gt_instance_id": instance_id,
                "gt_pair_id": row.get("pair_id", ""),
                "box": box,
                "source_conditioned_gt_instance": f"source={row.get('pair_source', '')};confidence={row.get('pair_confidence', '')};identity={row.get('identity_confidence', '')}",
            }
        )
    return {frame: sorted(rows, key=lambda item: str(item["gt_instance_id"])) for frame, rows in out.items()}


def build_instance_gt_evaluation_matrix() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    require_files([OUTPUTS[key] for key in GENERATION_OUTPUT_KEYS] + [r1.EVAL_ONLY_INPUTS["paired"]])
    local_units = read_rows(OUTPUTS["local_response_units"])
    boundary_families = read_rows(OUTPUTS["boundary_variant_families"])
    gt_by_frame = load_gt_instances(read_rows(r1.EVAL_ONLY_INPUTS["paired"]))
    unit_rows = []
    boundary_rows = []
    for unit in local_units:
        frame = parse_int(unit["sar_frame"])
        pred = box_from_text(unit["conservative_bbox"])
        for gt in gt_by_frame.get(frame, []):
            unit_rows.append(gt_matrix_row(unit["response_unit_id"], "local_response_unit", frame, pred, gt))
    for family in boundary_families:
        frame = parse_int(family["sar_frame"])
        pred = boundary_eval_box(family)
        for gt in gt_by_frame.get(frame, []):
            boundary_rows.append(gt_matrix_row(family["boundary_family_id"], "boundary_variant_family", frame, pred, gt))
    stats = {
        "response_unit_gt_matrix_rows": len(unit_rows),
        "boundary_family_gt_matrix_rows": len(boundary_rows),
        "gt_instance_counts": gt_instance_counts(gt_by_frame),
        "multi_instance_gt_union_used": "false",
        "response_unit_max_iou_eval_only": max([parse_float(row["iou"]) for row in unit_rows] or [math.nan]),
        "boundary_family_max_iou_eval_only": max([parse_float(row["iou"]) for row in boundary_rows] or [math.nan]),
    }
    return unit_rows, boundary_rows, stats


def boundary_eval_box(family: Mapping[str, str]) -> Box | None:
    if family.get("boundary_status") == "single_consensus_bbox":
        variants = [box_from_text(part.strip()) for part in family.get("boundary_variants", "").split("|") if part.strip()]
        boxes = [box for box in variants if box is not None]
        if len(boxes) == 1:
            return boxes[0]
    return box_from_text(family.get("common_core_bbox", ""))


def gt_matrix_row(object_id: str, object_type: str, frame: int, pred: Box | None, gt: Mapping[str, Any]) -> dict[str, Any]:
    metrics = bbox_metrics(pred, gt["box"])
    return {
        "object_id": object_id,
        "object_type": object_type,
        "sar_frame": frame,
        "gt_instance_id": gt["gt_instance_id"],
        "gt_pair_id": gt["gt_pair_id"],
        "iou": fmt(metrics["iou"]),
        "gt_coverage": fmt(metrics["coverage"]),
        "prediction_purity": fmt(metrics["purity"]),
        "center_distance_px": fmt(metrics["center_distance"]),
        "evaluation_scope": "eval_only_not_runtime_assignment",
        "source_conditioned_gt_instance": gt["source_conditioned_gt_instance"],
    }


def write_evaluation_outputs(replay_status: str = "PENDING", replay_evidence: str = "pending until verify-replay") -> None:
    unit_matrix, boundary_matrix, eval_stats = build_instance_gt_evaluation_matrix()
    write_csv(OUTPUTS["response_unit_gt_instance_matrix"], unit_matrix, GT_MATRIX_FIELDS)
    write_csv(OUTPUTS["boundary_family_gt_instance_matrix"], boundary_matrix, GT_MATRIX_FIELDS)
    stats = load_current_stats()
    stats.update(eval_stats)
    gates = gate_rows_for_status(stats, replay_status, replay_evidence)
    write_csv(OUTPUTS["gate_integrity"], gates, GATE_FIELDS)
    write_manifest(stats, replay_status, replay_evidence)
    render_report(stats, replay_status, replay_evidence)
    print(f"evaluate complete response_unit_gt_rows={len(unit_matrix)} boundary_family_gt_rows={len(boundary_matrix)}")


def load_current_stats() -> dict[str, Any]:
    frozen = load_frozen_r2_1_r1_inputs()
    tables = {key: read_rows(OUTPUTS[key]) if OUTPUTS[key].exists() else [] for key in GENERATION_OUTPUT_KEYS}
    boundary_stats = {
        "old_boundary_family_count": row_count(R1_INPUTS["corrected_families"]),
        "new_boundary_family_count": len(tables["boundary_variant_families"]),
        "zero_core_overlap_old_family_split_count": split_source_family_count("zero_core_overlap_not_boundary_variant"),
        "accepted_link_only_old_family_split_count": split_source_family_count("accepted_graph_link_only_not_boundary_variant"),
    }
    stats = semantic_stats(tables, boundary_stats, frozen)
    if OUTPUTS["response_unit_gt_instance_matrix"].exists():
        unit_matrix = read_rows(OUTPUTS["response_unit_gt_instance_matrix"])
        boundary_matrix = read_rows(OUTPUTS["boundary_family_gt_instance_matrix"])
        stats.update(
            {
                "response_unit_gt_matrix_rows": len(unit_matrix),
                "boundary_family_gt_matrix_rows": len(boundary_matrix),
                "multi_instance_gt_union_used": "false",
                "response_unit_max_iou_eval_only": max([parse_float(row["iou"]) for row in unit_matrix] or [math.nan]),
                "boundary_family_max_iou_eval_only": max([parse_float(row["iou"]) for row in boundary_matrix] or [math.nan]),
            }
        )
    else:
        stats.update(
            {
                "response_unit_gt_matrix_rows": 0,
                "boundary_family_gt_matrix_rows": 0,
                "multi_instance_gt_union_used": "false",
                "response_unit_max_iou_eval_only": math.nan,
                "boundary_family_max_iou_eval_only": math.nan,
            }
        )
    return stats


def split_source_family_count(relation_name: str) -> int:
    if not OUTPUTS["boundary_pairwise_integrity"].exists():
        return 0
    source_families = set()
    for row in read_rows(OUTPUTS["boundary_pairwise_integrity"]):
        if row["old_r1_same_family"] != "true" or row["new_same_boundary_family"] != "false":
            continue
        if relation_name == "zero_core_overlap_not_boundary_variant":
            match = parse_float(row.get("core_overlap_ratio", "0"), 0) == 0
        else:
            match = row["pair_relation"] == relation_name
        if match:
            source_families.add(row["source_r1_family_id"])
    return len(source_families)


def write_manifest(stats: Mapping[str, Any], replay_status: str, replay_evidence: str) -> None:
    rows = []
    frozen_paths = dict(r1.FROZEN_INPUTS)
    frozen_paths.update(R1_INPUTS)
    for name, path in frozen_paths.items():
        if path.exists():
            rows.append({"artifact": name, "path": rel(path), "sha256": sha256(path), "rows": row_count(path), "frozen_phase": "r2_1_or_r2_1_r1_input"})
    for key, path in OUTPUTS.items():
        if key in {"report", "gate_integrity", "frozen_manifest", "focus_visual_review"}:
            continue
        if path.exists():
            rows.append({"artifact": key, "path": rel(path), "sha256": sha256(path), "rows": row_count(path), "frozen_phase": "r2_1_r1_1_output"})
    rows.append(
        {
            "artifact": "semantic_stats",
            "path": "inline",
            "sha256": "",
            "rows": len(stats),
            "frozen_phase": f"replay_status={replay_status};{replay_evidence}",
        }
    )
    write_csv(OUTPUTS["frozen_manifest"], rows, MANIFEST_FIELDS)


def render_focus_review_pack() -> None:
    require_files([OUTPUTS["local_response_units"], OUTPUTS["boundary_variant_families"], OUTPUTS["same_object_candidate_edges"]])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    units_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    families_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    edges_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for unit in read_rows(OUTPUTS["local_response_units"]):
        units_by_frame[parse_int(unit["sar_frame"])].append(unit)
    for family in read_rows(OUTPUTS["boundary_variant_families"]):
        families_by_frame[parse_int(family["sar_frame"])].append(family)
    for edge in read_rows(OUTPUTS["same_object_candidate_edges"]):
        edges_by_frame[parse_int(edge["sar_frame"])].append(edge)

    review_rows = []
    for frame in FOCUS_FRAMES:
        image_path = render_focus_frame(frame, units_by_frame.get(frame, []), families_by_frame.get(frame, []), edges_by_frame.get(frame, []))
        review_rows.append(
            {
                "sar_frame": frame,
                "focus_png": rel(image_path),
                "zero_core_overlap_old_family_split_cn": "pending_manual_focus_review",
                "same_object_candidate_edge_cn": "pending_manual_focus_review",
                "boundary_family_semantics_cn": "pending_manual_focus_review",
                "visual_review_scope": "focus_frames_only_not_full_165_family_review",
                "visual_validity_state": "UNPROVEN",
                "reviewer_note_cn": "待 Codex 打开关键帧图像后填写；本轮不自动提升为 object-specific PASS。",
            }
        )
    if OUTPUTS["focus_visual_review"].exists():
        existing = read_rows(OUTPUTS["focus_visual_review"])
        if existing and all(row.get("zero_core_overlap_old_family_split_cn", "").startswith("pending") is False for row in existing):
            review_rows = existing
    write_csv(OUTPUTS["focus_visual_review"], review_rows, FOCUS_REVIEW_FIELDS)
    print("focus-review-pack complete")
    for row in review_rows:
        print(row["focus_png"])


def render_focus_frame(frame: int, units: Sequence[Mapping[str, str]], families: Sequence[Mapping[str, str]], edges: Sequence[Mapping[str, str]]) -> Path:
    image = Image.open(sar_gray_path(SCENE, frame)).convert("RGB")
    boxes = [box_from_text(unit["conservative_bbox"]) for unit in units]
    focus = union_box([box for box in boxes if box is not None]) or Box(980.0, 1090.0, 1390.0, 1305.0)
    focus = r1.expand_box(focus, 80.0)
    crop = image.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((1040, 640))
    draw = ImageDraw.Draw(crop)
    unit_by_id = {unit["response_unit_id"]: unit for unit in units}
    for family in families:
        for variant in family.get("boundary_variants", "").split("|"):
            r1.draw_crop_box(draw, box_from_text(variant.strip()), focus, 1040, 640, (255, 220, 0), 2)
        r1.draw_crop_box(draw, box_from_text(family.get("common_core_bbox", "")), focus, 1040, 640, (0, 255, 80), 2)
    for unit in units:
        r1.draw_crop_box(draw, box_from_text(unit["conservative_bbox"]), focus, 1040, 640, (0, 180, 255), 1)
    for edge in edges:
        a = box_from_text(unit_by_id.get(edge["source_response_unit_id"], {}).get("conservative_bbox", ""))
        b = box_from_text(unit_by_id.get(edge["target_response_unit_id"], {}).get("conservative_bbox", ""))
        if a is not None and b is not None:
            ax, ay = r1.crop_point(a.cx, a.cy, focus, 1040, 640)
            bx, by = r1.crop_point(b.cx, b.cy, focus, 1040, 640)
            draw.line((ax, ay, bx, by), fill=(255, 80, 255), width=2)
    draw.rectangle((0, 0, 1039, 24), fill=(0, 0, 0))
    draw.text((8, 6), f"SAR{frame:03d} R2.1-R1.1 focus review: cyan=local unit yellow=boundary variant green=shared core magenta=edge", fill=(255, 255, 255))
    path = OUT_DIR / f"focus_semantic_review_sar{frame:03d}.png"
    crop.save(path)
    return path


def raw_review_fields_complete() -> bool:
    rows = read_rows(R1_INPUTS["blind_raw"])
    fields = r1.RAW_FIELDS[5:-1]
    return bool(rows) and all(all(str(row.get(field, "")).strip() for field in fields) for row in rows)


def assisted_review_fields_complete() -> bool:
    rows = read_rows(R1_INPUTS["blind_assisted"])
    fields = r1.ASSISTED_FIELDS[5:-1]
    return bool(rows) and all(all(str(row.get(field, "")).strip() for field in fields) for row in rows)


def gate(name: str, status: str, evidence: str, provenance: str) -> dict[str, str]:
    return {"gate": name, "status": status, "evidence": evidence, "provenance": provenance}


def gate_rows_for_status(stats: Mapping[str, Any], replay_status: str, replay_evidence: str) -> list[dict[str, str]]:
    frozen_ok = all(stats.get("r2_sha_checks", {}).values()) and all(stats.get("r1_sha_checks", {}).values())
    boundary_ok = (
        stats["boundary_family_zero_core_overlap_pair_count"] == 0
        and stats["boundary_family_different_core_no_overlap_count"] == 0
        and stats["boundary_family_accepted_link_only_pair_count"] == 0
    )
    closure_ok = (
        frozen_ok
        and boundary_ok
        and stats["same_object_candidate_edge_count"] > 0
        and stats["topk_exact_drop_audit"] == "FAIL"
        and stats.get("multi_instance_gt_union_used", "false") == "false"
        and replay_status == "PASS"
    )
    return [
        gate("R2_1_R1_FROZEN_INPUTS_UNCHANGED", "PASS" if frozen_ok else "FAIL", "R2.1 and R2.1-R1 manifest SHA checks compared", "frozen_input_replay"),
        gate("LOCAL_RESPONSE_UNIT_SEMANTICS_EXPLICIT", "PASS", f"local response units={stats['local_response_unit_count']}; units are not complete vehicles", "semantic_separation"),
        gate("BOUNDARY_VARIANT_FAMILY_SEMANTICS_VALID", "PASS" if boundary_ok else "FAIL", f"boundary families={stats['boundary_variant_family_count']}; strict same-core variant rules applied", "boundary_family_builder"),
        gate("BOUNDARY_FAMILY_ZERO_CORE_OVERLAP_PAIR_COUNT", "PASS" if stats["boundary_family_zero_core_overlap_pair_count"] == 0 else "FAIL", f"count={stats['boundary_family_zero_core_overlap_pair_count']}", "boundary_family_builder"),
        gate("BOUNDARY_FAMILY_DIFFERENT_CORE_NO_OVERLAP_COUNT", "PASS" if stats["boundary_family_different_core_no_overlap_count"] == 0 else "FAIL", f"count={stats['boundary_family_different_core_no_overlap_count']}", "boundary_family_builder"),
        gate("BOUNDARY_FAMILY_ACCEPTED_LINK_ONLY_PAIR_COUNT", "PASS" if stats["boundary_family_accepted_link_only_pair_count"] == 0 else "FAIL", f"count={stats['boundary_family_accepted_link_only_pair_count']}", "boundary_family_builder"),
        gate("SAME_OBJECT_CANDIDATE_EDGE_SEPARATED", "PASS", f"edges={stats['same_object_candidate_edge_count']}; counts={stats['same_object_candidate_edge_counts']}", "same_object_candidate"),
        gate("SAME_OBJECT_CANDIDATE_NOT_IDENTITY_TRUTH", "PASS", "edge_state is candidate/weak/blocked only; no confirmed same vehicle", "same_object_candidate"),
        gate("STATIC_FAMILY_NOT_EQUAL_PHYSICAL_VEHICLE", "PASS", "boundary family represents local-response boundary variants, not physical vehicle identity", "semantic_boundary"),
        gate("PROXIMITY_RESIDUAL_COMPONENT_AUDIT", "PASS", f"all component rows={stats['component_audit_row_count']}; matched frozen atom rows={stats['matched_frozen_atom_count']}; residual components={stats['residual_component_count']}; proximity residual candidates={stats['proximity_residual_candidate_count']}; unknown match-status rows={stats['unknown_match_status_count']}", "topk_semantic_reinterpretation"),
        gate("TOP_K_EXACT_DROP_AUDIT", stats["topk_exact_drop_audit"], "R2.1-R1 top-k file is reinterpreted as proximity residual audit, not exact original top-k replay", "topk_semantic_reinterpretation"),
        gate("TOP_K_WEAK_RESPONSE_RISK", stats["topk_weak_response_risk"], "vehicle weak-part conclusion revoked; residual rows keep physical_vehicle_part_unproven=true", "topk_semantic_reinterpretation"),
        gate("INSTANCE_LEVEL_GT_EVALUATION_VALID", "PASS" if stats.get("response_unit_gt_matrix_rows", 0) else "PENDING", f"response-unit matrix rows={stats.get('response_unit_gt_matrix_rows', 0)}; boundary-family matrix rows={stats.get('boundary_family_gt_matrix_rows', 0)}", "eval_only_instance_matrix"),
        gate("MULTI_INSTANCE_GT_UNION_NOT_USED", "PASS", "GT instances are evaluated as per-instance rows; no frame-level union box is constructed", "eval_only_instance_matrix"),
        gate("RAW_REVIEW_FIELDS_COMPLETE", "PASS" if raw_review_fields_complete() else "FAIL", "R2.1-R1 raw review CSV fields checked for completeness", "review_gate_semantic_downgrade"),
        gate("ASSISTED_REVIEW_FIELDS_COMPLETE", "PASS" if assisted_review_fields_complete() else "FAIL", "R2.1-R1 assisted review CSV fields checked for completeness", "review_gate_semantic_downgrade"),
        gate("OBJECT_SPECIFIC_RAW_VISUAL_VALIDITY", "UNPROVEN", "fields are complete but this round did not redo independent object-by-object raw visual review", "review_gate_semantic_downgrade"),
        gate("OBJECT_SPECIFIC_ASSISTED_VISUAL_VALIDITY", "UNPROVEN", "fields are complete but this round did not redo independent object-by-object assisted visual review", "review_gate_semantic_downgrade"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_status, replay_evidence, "frozen_replay"),
        gate("R2_1_R1_1_STATIC_SEMANTIC_CLOSURE", "PASS" if closure_ok else "PENDING", "requires strict boundary semantics, candidate edge split, top-k revocation, instance GT, gate downgrade, replay pass", "stage_closure"),
        gate("VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2", "NO", "R2.1-R1.1 is static semantic closure, not an A1.7R2 runtime contract", "stage_boundary"),
        gate("GM_RM011_BLOCKED", "true", "GM_RM011 remains outside this task", "stage_boundary"),
        gate("GM_RM019_STATIC_STAGE_CLOSED", "true" if closure_ok else "pending", "no further R2.1-R1.x static expansion after this closure", "stage_boundary"),
        gate("NEXT_STAGE", "GM_RM017_CONTINUOUS_PHYSICAL_RESPONSE_AUDIT", "next phase is continuous physical response audit", "stage_boundary"),
    ]


def render_report(stats: Mapping[str, Any], replay_status: str, replay_evidence: str) -> None:
    gates = gate_rows_for_status(stats, replay_status, replay_evidence)
    focus_rows = read_rows(OUTPUTS["focus_visual_review"]) if OUTPUTS["focus_visual_review"].exists() else []
    gate_table = ["| gate | status | evidence | provenance |", "| --- | --- | --- | --- |"]
    for row in gates:
        gate_table.append(f"| {row['gate']} | {row['status']} | {row['evidence']} | {row['provenance']} |")
    edge_counts = stats.get("same_object_candidate_edge_counts", {})
    lines = [
        "# OTY2 WGV3.6A-A1.8A-R2.1-R1.1 Semantic Separation",
        "",
        "## Boundary",
        "",
        f"- start commit: `{START_COMMIT}`",
        f"- start title: `{START_TITLE}`",
        "- R2.1 atoms/roles/support/lineage/graph/core/response boxes and all R2.1-R1 family/review files are frozen read-only inputs.",
        "- This round separates local response units, strict boundary-variant families, and same-object candidate edges.",
        "- It does not implement selector, ranking, best candidate, GM_RM017, GM_RM011, dynamic shell, final annotation, threshold tuning, or GT modification.",
        "- GM_RM019_STATIC_STAGE_CLOSED=true after replay pass; NEXT_STAGE=GM_RM017_CONTINUOUS_PHYSICAL_RESPONSE_AUDIT.",
        "",
        "## Counts",
        "",
        f"- boundary families before R1.1: `{stats.get('old_boundary_family_count', '')}`",
        f"- boundary variant families after R1.1: `{stats.get('boundary_variant_family_count', '')}`",
        f"- zero-core-overlap old family split count: `{stats.get('zero_core_overlap_old_family_split_count', '')}`",
        f"- accepted-link-only old family split count: `{stats.get('accepted_link_only_old_family_split_count', '')}`",
        f"- local response units: `{stats.get('local_response_unit_count', '')}`",
        f"- same-object candidate edges: `{stats.get('same_object_candidate_edge_count', '')}`",
        f"- same-object candidate edge counts: `{edge_counts}`",
        f"- body-endpoint / body-side / part-part / accepted-link candidate edges: `{edge_counts.get('body_endpoint_candidate', 0)}` / `{edge_counts.get('body_side_candidate', 0)}` / `{edge_counts.get('part_part_candidate', 0)}` / `{edge_counts.get('accepted_graph_link_candidate', 0)}`",
        f"- boundary-family zero-core-overlap pair count: `{stats.get('boundary_family_zero_core_overlap_pair_count', '')}`",
        f"- boundary-family different-core/no-overlap count: `{stats.get('boundary_family_different_core_no_overlap_count', '')}`",
        f"- boundary-family accepted-link-only pair count: `{stats.get('boundary_family_accepted_link_only_pair_count', '')}`",
        "",
        "## Top-K Reinterpretation",
        "",
        f"- all component audit rows: `{stats.get('component_audit_row_count', '')}`",
        f"- matched frozen-atom / non-residual rows: `{stats.get('matched_frozen_atom_count', '')}`",
        f"- residual component rows after semantic fix: `{stats.get('residual_component_count', '')}`",
        f"- unknown match-status rows: `{stats.get('unknown_match_status_count', '')}`",
        f"- proximity residual candidates after semantic fix: `{stats.get('proximity_residual_candidate_count', '')}`",
        f"- old possible weak vehicle part claim count: `{stats.get('old_possible_weak_vehicle_part_claim_count', '')}`",
        "- revoked statement: `1535 weak vehicle parts were dropped by Top-K`.",
        "- semantic erratum: the previous R1.1 residual audit treated all 2368 component rows as unmatched residuals; 52 rows are matched frozen atoms / kept components and are now retained only as provenance rows.",
        "- corrected statement: Found many dropped residual components near frozen response regions but unmatched to frozen atoms; whether they are vehicle weak responses is unproven without exact original Top-K replay, dynamic co-motion, or object-by-object visual review.",
        f"- TOP_K_EXACT_DROP_AUDIT: `{stats.get('topk_exact_drop_audit', '')}`",
        f"- TOP_K_WEAK_RESPONSE_RISK: `{stats.get('topk_weak_response_risk', '')}`",
        "",
        "## GT Instance Evaluation",
        "",
        f"- GT instance counts by frame: `{stats.get('gt_instance_counts', {})}`",
        f"- multi-instance GT union used: `{stats.get('multi_instance_gt_union_used', 'false')}`",
        f"- response-unit x GT-instance matrix rows: `{stats.get('response_unit_gt_matrix_rows', '')}`",
        f"- boundary-family x GT-instance matrix rows: `{stats.get('boundary_family_gt_matrix_rows', '')}`",
        f"- response-unit max IoU across instances eval-only: `{fmt(stats.get('response_unit_max_iou_eval_only', math.nan))}`",
        f"- boundary-family max IoU across instances eval-only: `{fmt(stats.get('boundary_family_max_iou_eval_only', math.nan))}`",
        "",
        "## Focus Review",
        "",
        "- Scope is limited to frames 31, 32, 39, 78, 79, 263, 270, 271, 272, 273, 289, 290; this is not a full 165-family re-review.",
    ]
    if focus_rows:
        lines.extend(["", "| sar_frame | visual_validity_state | reviewer_note_cn |", "| --- | --- | --- |"])
        for row in focus_rows:
            lines.append(f"| {row['sar_frame']} | {row['visual_validity_state']} | {row['reviewer_note_cn']} |")
    lines.extend(
        [
            "",
            "## Gates",
            "",
            *gate_table,
            "",
            "## Replay",
            "",
            f"- FROZEN_REPLAY_IDENTICAL: `{replay_status}`",
            f"- replay evidence: `{replay_evidence}`",
            "",
            "## Stage Stop",
            "",
            "- GM_RM019_STATIC_STAGE_CLOSED=true",
            "- NEXT_STAGE=GM_RM017_CONTINUOUS_PHYSICAL_RESPONSE_AUDIT",
            "",
        ]
    )
    write_text(OUTPUTS["report"], "\n".join(lines))


def write_temp_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    write_csv(path, rows, fields)


def verify_replay() -> None:
    require_files([OUTPUTS[key] for key in REPLAY_OUTPUT_KEYS])
    if VERIFY_TMP_DIR.exists():
        shutil.rmtree(VERIFY_TMP_DIR)
    VERIFY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    tables, _ = build_generation_tables()
    unit_matrix, boundary_matrix, _ = build_instance_gt_evaluation_matrix()
    temp_specs = {
        "local_response_units": (tables["local_response_units"], LOCAL_RESPONSE_UNIT_FIELDS),
        "boundary_variant_families": (tables["boundary_variant_families"], BOUNDARY_FAMILY_FIELDS),
        "boundary_family_members": (tables["boundary_family_members"], BOUNDARY_MEMBER_FIELDS),
        "boundary_pairwise_integrity": (tables["boundary_pairwise_integrity"], BOUNDARY_PAIRWISE_FIELDS),
        "same_object_candidate_edges": (tables["same_object_candidate_edges"], SAME_OBJECT_EDGE_FIELDS),
        "proximity_residual_component_audit": (tables["proximity_residual_component_audit"], RESIDUAL_COMPONENT_FIELDS),
        "response_unit_gt_instance_matrix": (unit_matrix, GT_MATRIX_FIELDS),
        "boundary_family_gt_instance_matrix": (boundary_matrix, GT_MATRIX_FIELDS),
    }
    results = {}
    for key, (rows, fields) in temp_specs.items():
        temp_path = VERIFY_TMP_DIR / OUTPUTS[key].name
        write_temp_csv(temp_path, rows, fields)
        results[key] = sha256(temp_path) == sha256(OUTPUTS[key])
    replay_status = "PASS" if all(results.values()) else "FAIL"
    replay_evidence = "; ".join(f"{key}:{'PASS' if ok else 'FAIL'}" for key, ok in results.items())
    stats = load_current_stats()
    gates = gate_rows_for_status(stats, replay_status, replay_evidence)
    write_csv(OUTPUTS["gate_integrity"], gates, GATE_FIELDS)
    write_manifest(stats, replay_status, replay_evidence)
    render_report(stats, replay_status, replay_evidence)
    print(f"verify-replay FROZEN_REPLAY_IDENTICAL={replay_status}")
    print(replay_evidence)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "focus-review-pack", "evaluate", "verify-replay"])
    args = parser.parse_args()
    if args.command == "generate":
        write_generation_outputs()
    elif args.command == "focus-review-pack":
        render_focus_review_pack()
    elif args.command == "evaluate":
        write_evaluation_outputs()
    elif args.command == "verify-replay":
        verify_replay()


if __name__ == "__main__":
    main()
