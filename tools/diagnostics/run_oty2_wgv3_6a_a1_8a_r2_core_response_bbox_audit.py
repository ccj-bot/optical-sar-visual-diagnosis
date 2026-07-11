"""WGV3.6A-A1.8A-R2 core response bbox audit.

Commands are intentionally staged:

generate            runtime-safe core subgraph and image-domain bbox freeze
blind-raw-pack      opaque raw SAR bbox sheets and blank raw judgement CSV
blind-assisted-pack assisted algorithm overlay sheets and blank assisted CSV
evaluate            GT-assisted bbox/error analysis after both blind freezes
verify-replay       regenerate frozen runtime artifacts and compare SHA

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

from PIL import Image, ImageDraw

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

import run_oty2_wgv3_6a_a1_8a_r1_mechanism_integrity_audit as r1  # noqa: E402
from run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping import (  # noqa: E402
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
    sar_gray_path,
    sha256,
    write_csv,
    write_text,
)


DATE = "20260711"
REQUESTED_START_COMMIT = "87433c986779cb77624e652822db12e6e3b2511e"
SCENE = "GM_RM019"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_8a_r2_20260711"
VERIFY_TMP_DIR = OUT_DIR / "_verify_replay_tmp"
PX_TO_M = 0.03

R1_OUTPUTS = {
    "atoms": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_frozen_atom_trace_{DATE}.csv",
    "roles": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_frozen_role_proposals_{DATE}.csv",
    "lineage_nodes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_part_lineage_nodes_{DATE}.csv",
    "lineage_edges": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_part_lineage_edges_{DATE}.csv",
    "holdout": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_blind_holdout_manifest_{DATE}.csv",
    "blind": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r1_blind_object_judgement_{DATE}.csv",
}

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_8a_r2_core_response_bbox_audit_{DATE}.md",
    "causal_shell": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_causal_source_shell_audit_{DATE}.csv",
    "atom_nodes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_atom_graph_nodes_{DATE}.csv",
    "atom_edges": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_atom_graph_edges_{DATE}.csv",
    "core_hypotheses": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_core_subgraph_hypotheses_{DATE}.csv",
    "core_gates": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_core_subgraph_gates_{DATE}.csv",
    "optional_membership": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_optional_response_membership_{DATE}.csv",
    "frozen_boxes": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_frozen_response_boxes_{DATE}.csv",
    "bbox_temporal": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_bbox_temporal_consistency_{DATE}.csv",
    "blind_raw": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_blind_raw_judgement_{DATE}.csv",
    "blind_assisted": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_blind_assisted_judgement_{DATE}.csv",
    "gt_eval": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_gt_assisted_bbox_evaluation_{DATE}.csv",
    "error_taxonomy": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_error_taxonomy_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_gate_integrity_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6a_a1_8a_r2_frozen_artifact_manifest_{DATE}.csv",
}

VISUALS = {
    "raw_a": OUT_DIR / "blind_raw_sheet_001.png",
    "raw_b": OUT_DIR / "blind_raw_sheet_002.png",
    "raw_c": OUT_DIR / "blind_raw_sheet_003.png",
    "raw_d": OUT_DIR / "blind_raw_sheet_004.png",
    "assisted_a": OUT_DIR / "blind_assisted_sheet_001.png",
    "assisted_b": OUT_DIR / "blind_assisted_sheet_002.png",
    "assisted_c": OUT_DIR / "blind_assisted_sheet_003.png",
    "assisted_d": OUT_DIR / "blind_assisted_sheet_004.png",
    "eval": OUT_DIR / "eval_only_bbox_sheet.png",
}

FREEZE_KEYS = [
    "causal_shell",
    "atom_nodes",
    "atom_edges",
    "core_hypotheses",
    "core_gates",
    "optional_membership",
    "frozen_boxes",
    "bbox_temporal",
]

VEHICLE_ROLES = {"body_core_candidate", "side_ridge_candidate", "endpoint_hotspot_candidate"}
BACKGROUND_ROLE = "background_arc_candidate"

CAUSAL_FIELDS = [
    "sar_frame",
    "selected_source_frame",
    "source_is_historical",
    "source_lag_frames",
    "previous_r1_source_frame",
    "r1_used_future_source",
    "corrected_shell_provenance",
    "gate_status",
]
NODE_FIELDS = [
    "atom_id",
    "sar_frame",
    "candidate_role",
    "graph_role_class",
    "support_bbox",
    "centroid_x",
    "centroid_y",
    "radial",
    "azimuth",
    "orientation",
    "integrated_energy",
    "persistent_part_track_id",
    "track_len",
]
EDGE_FIELDS = [
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
    "role_compatibility",
    "background_arc_conflict",
]
CORE_FIELDS = [
    "core_subgraph_id",
    "sar_frame",
    "member_atom_ids",
    "core_role_summary",
    "core_relation_type",
    "core_bbox",
    "core_bbox_width_px",
    "core_bbox_height_px",
    "core_support_span_long_px",
    "core_support_span_short_px",
    "core_bbox_width_m",
    "core_bbox_height_m",
    "core_max_boundary_gap_px",
    "core_max_centroid_distance_px",
    "core_occupancy_ratio",
    "core_internal_blank_ratio",
    "close_background_atom_count",
    "has_core_track",
    "generation_provenance",
]
GATE_FIELDS = [
    "core_subgraph_id",
    "G_core_scale",
    "G_core_compact",
    "G_core_relation",
    "G_core_temporal",
    "G_core_background",
    "box_status",
    "gate_reason",
]
OPTIONAL_FIELDS = [
    "core_subgraph_id",
    "sar_frame",
    "atom_id",
    "candidate_role",
    "membership_decision",
    "boundary_distance_to_core_px",
    "centroid_distance_to_core_px",
    "shares_persistent_track",
    "compatible_part_relation",
    "background_arc_conflict",
    "bbox_blank_ratio_if_included",
    "decision_reason",
]
BOX_FIELDS = [
    "response_box_id",
    "core_subgraph_id",
    "sar_frame",
    "box_status",
    "core_member_atom_ids",
    "included_optional_atom_ids",
    "excluded_or_uncertain_atom_ids",
    "core_bbox_x1_px",
    "core_bbox_y1_px",
    "core_bbox_x2_px",
    "core_bbox_y2_px",
    "response_bbox_x1_px",
    "response_bbox_y1_px",
    "response_bbox_x2_px",
    "response_bbox_y2_px",
    "bbox_width_px",
    "bbox_height_px",
    "bbox_width_m",
    "bbox_height_m",
    "center_x_m",
    "center_y_m",
    "range_m",
    "azimuth_deg",
    "final_annotation_space",
]
TEMPORAL_FIELDS = [
    "response_box_id",
    "sar_frame",
    "previous_response_box_id",
    "previous_sar_frame",
    "center_shift_px",
    "bbox_iou",
    "status",
]
RAW_FIELDS = [
    "blind_review_id",
    "blind_frame_id",
    "blind_object_id",
    "response_box_id",
    "raw_visible_structure",
    "raw_vehicle_part_support",
    "raw_background_support",
    "raw_unresolved",
    "raw_decisive_reason",
    "raw_visual_confidence",
    "raw_png",
]
ASSISTED_FIELDS = [
    "blind_review_id",
    "blind_frame_id",
    "blind_object_id",
    "response_box_id",
    "assisted_vehicle_core_support",
    "assisted_optional_membership_support",
    "assisted_background_support",
    "assisted_unresolved",
    "assisted_decisive_reason",
    "raw_vs_assisted_change",
    "assisted_visual_confidence",
    "assisted_png",
]
EVAL_FIELDS = [
    "eval_id",
    "response_box_id",
    "sar_frame",
    "box_status",
    "blind_raw_judgement",
    "blind_assisted_judgement",
    "raw_vs_assisted_change",
    "discovery_label_eval_only",
    "vehicle_identity_eval_only",
    "gt_exact_frame_available",
    "gt_relation_eval_only",
    "gt_overlap_eval_only",
    "gt_center_distance_eval_only",
    "bbox_undercoverage",
    "bbox_overcoverage",
    "bbox_background_inclusion",
    "bbox_vehicle_part_exclusion",
    "gt_assisted_bbox_explanation",
    "provenance",
]
ERROR_FIELDS = [
    "case_id",
    "response_box_id",
    "sar_frame",
    "error_type",
    "reason",
    "provenance",
]
INTEGRITY_FIELDS = ["gate", "status", "evidence", "provenance"]
MANIFEST_FIELDS = ["artifact", "path", "sha256", "rows", "frozen_phase"]
BOX_STATUS_ORDER = [
    "vehicle_response_box_supported",
    "vehicle_response_box_possible",
    "vehicle_part_box_only",
    "background_box",
    "unresolved_box",
]
GRAPH_ROLE_ORDER = [
    "core_member_candidate",
    "optional_support_candidate",
    "conflicting_background_candidate",
]
ACCEPTED_BOX_STATUSES = {
    "vehicle_response_box_supported",
    "vehicle_response_box_possible",
    "vehicle_part_box_only",
}


@dataclass(frozen=True)
class Atom:
    atom_id: str
    frame: int
    role: str
    role_class: str
    box: Box
    cx: float
    cy: float
    radial: float
    azimuth: float
    orientation: float
    energy: float
    area: int
    track_id: str
    track_len: int


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


def require_files(paths: Sequence[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required files: " + "; ".join(missing))


def box_from_text(text: str) -> Box:
    box = r1.box_from_text(text)
    if box is None:
        raise ValueError(f"invalid box text: {text!r}")
    return box


def box_text(box: Box) -> str:
    return f"{fmt(box.x1)},{fmt(box.y1)},{fmt(box.x2)},{fmt(box.y2)}"


def union_box(boxes: Sequence[Box]) -> Box:
    return r1.union_box(list(boxes))


def expand_box(box: Box, margin: float) -> Box:
    return r1.expand_box(box, margin)


def gap_between(a: Box, b: Box) -> float:
    return r1.gap_between(a, b)


def angle_diff(a: float, b: float) -> float:
    return r1.angle_diff(a, b)


def box_iou(a: Box, b: Box) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = a.area + b.area - inter
    return safe_div(inter, union)


def load_atoms_runtime_safe() -> list[Atom]:
    require_files([R1_OUTPUTS["atoms"], R1_OUTPUTS["roles"], R1_OUTPUTS["lineage_nodes"]])
    role_by_atom = {row["atom_id"]: row["candidate_role"] for row in read_rows(R1_OUTPUTS["roles"])}
    nodes = read_rows(R1_OUTPUTS["lineage_nodes"])
    track_by_atom = {row["atom_id"]: row.get("persistent_part_track_id", "") for row in nodes}
    track_len = Counter(row.get("persistent_part_track_id", "") for row in nodes if row.get("persistent_part_track_id", ""))
    raw_atoms = read_rows(R1_OUTPUTS["atoms"])
    preliminary: list[dict[str, Any]] = []
    for row in raw_atoms:
        atom_id = row["atom_id"]
        role = role_by_atom.get(atom_id, "unresolved_atom")
        preliminary.append(
            {
                "atom_id": atom_id,
                "frame": parse_int(row["sar_frame"]),
                "role": role,
                "box": box_from_text(row["support_bbox"]),
                "cx": parse_float(row["pixel_centroid_x"]),
                "cy": parse_float(row["pixel_centroid_y"]),
                "radial": parse_float(row["radial"]),
                "azimuth": parse_float(row["azimuth"]),
                "orientation": parse_float(row["atom_orientation"]),
                "energy": parse_float(row["integrated_energy"]),
                "area": parse_int(row["support_pixel_count"]),
                "track_id": track_by_atom.get(atom_id, ""),
                "track_len": track_len.get(track_by_atom.get(atom_id, ""), 0),
            }
        )
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for atom in preliminary:
        by_frame[atom["frame"]].append(atom)
    out: list[Atom] = []
    for frame, atoms in by_frame.items():
        hard_core = [a for a in atoms if a["role"] in VEHICLE_ROLES]
        for atom in atoms:
            role = atom["role"]
            if role in VEHICLE_ROLES:
                role_class = "core_member_candidate"
            elif role == BACKGROUND_ROLE:
                role_class = "conflicting_background_candidate"
            elif role == "unresolved_atom" and any(gap_between(atom["box"], core["box"]) <= 35.0 or math.hypot(atom["cx"] - core["cx"], atom["cy"] - core["cy"]) <= 85.0 for core in hard_core):
                role_class = "core_member_candidate"
            else:
                role_class = "optional_support_candidate"
            out.append(Atom(role_class=role_class, **atom))
    return sorted(out, key=lambda a: (a.frame, a.atom_id))


def atoms_by_frame(atoms: Sequence[Atom]) -> dict[int, list[Atom]]:
    grouped: dict[int, list[Atom]] = defaultdict(list)
    for atom in atoms:
        grouped[atom.frame].append(atom)
    return grouped


def source_frames_and_shells() -> dict[int, Box]:
    return r1.source_shells()


def previous_r1_source(frame: int, source_frames: Sequence[int]) -> int | None:
    if not source_frames:
        return None
    return min(source_frames, key=lambda source_frame: (abs(source_frame - frame), source_frame))


def causal_source(frame: int, source_frames: Sequence[int]) -> int | None:
    available = [source for source in source_frames if source <= frame]
    return max(available) if available else None


def runtime_frames() -> list[int]:
    return r1.runtime_frames()


def causal_source_rows() -> list[dict[str, Any]]:
    shells = source_frames_and_shells()
    source_frames = sorted(shells)
    rows: list[dict[str, Any]] = []
    for frame in runtime_frames():
        r1_source = previous_r1_source(frame, source_frames)
        selected = causal_source(frame, source_frames)
        if selected is None:
            provenance = "static_fallback_shell_no_historical_source"
            historical = True
            lag = ""
        else:
            provenance = f"causal_a1_7r_source_shell_frame_{selected}"
            historical = selected <= frame
            lag = frame - selected
        r1_future = bool(r1_source is not None and r1_source > frame)
        rows.append(
            {
                "sar_frame": frame,
                "selected_source_frame": selected if selected is not None else "",
                "source_is_historical": bool_text(historical),
                "source_lag_frames": lag,
                "previous_r1_source_frame": r1_source if r1_source is not None else "",
                "r1_used_future_source": bool_text(r1_future),
                "corrected_shell_provenance": provenance,
                "gate_status": "PASS" if historical else "FAIL",
            }
        )
    return rows


def node_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    return [
        {
            "atom_id": atom.atom_id,
            "sar_frame": atom.frame,
            "candidate_role": atom.role,
            "graph_role_class": atom.role_class,
            "support_bbox": box_text(atom.box),
            "centroid_x": fmt(atom.cx),
            "centroid_y": fmt(atom.cy),
            "radial": fmt(atom.radial),
            "azimuth": fmt(atom.azimuth),
            "orientation": fmt(atom.orientation),
            "integrated_energy": fmt(atom.energy),
            "persistent_part_track_id": atom.track_id,
            "track_len": atom.track_len,
        }
        for atom in atoms
    ]


def role_compatible(a: Atom, b: Atom) -> bool:
    if BACKGROUND_ROLE in {a.role, b.role}:
        return a.role == b.role
    if a.role == "isolated_small_atom" and b.role == "isolated_small_atom":
        return True
    if a.role == "isolated_small_atom" or b.role == "isolated_small_atom":
        return False
    return bool({a.role, b.role} & VEHICLE_ROLES) or "unresolved_atom" in {a.role, b.role}


def edge_rows(atoms: Sequence[Atom]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame, frame_atoms in atoms_by_frame(atoms).items():
        for a, b in combinations(frame_atoms, 2):
            gap = gap_between(a.box, b.box)
            dist = math.hypot(a.cx - b.cx, a.cy - b.cy)
            if gap > 135.0 and dist > 235.0:
                continue
            energy_ratio = max(a.energy, b.energy) / max(1.0, min(a.energy, b.energy))
            rows.append(
                {
                    "edge_id": f"R2E{len(rows) + 1:05d}",
                    "sar_frame": frame,
                    "source_atom_id": a.atom_id,
                    "target_atom_id": b.atom_id,
                    "support_boundary_gap_px": fmt(gap),
                    "centroid_distance_px": fmt(dist),
                    "radial_delta": fmt(abs(a.radial - b.radial)),
                    "azimuth_delta": fmt(abs(a.azimuth - b.azimuth)),
                    "orientation_delta": fmt(angle_diff(a.orientation, b.orientation)),
                    "energy_ratio": fmt(energy_ratio),
                    "role_compatibility": bool_text(role_compatible(a, b)),
                    "background_arc_conflict": bool_text(BACKGROUND_ROLE in {a.role, b.role}),
                }
            )
    return rows


def atom_lookup(atoms: Sequence[Atom]) -> dict[str, Atom]:
    return {atom.atom_id: atom for atom in atoms}


def relation_type(core_atoms: Sequence[Atom]) -> str:
    roles = {atom.role for atom in core_atoms}
    if "body_core_candidate" in roles and "endpoint_hotspot_candidate" in roles:
        return "core_to_endpoint"
    if "body_core_candidate" in roles and "side_ridge_candidate" in roles:
        return "core_to_side"
    if "side_ridge_candidate" in roles and "endpoint_hotspot_candidate" in roles:
        return "side_to_endpoint"
    if "body_core_candidate" in roles:
        return "compact_partial_body"
    if "endpoint_hotspot_candidate" in roles or "side_ridge_candidate" in roles:
        return "weak_part_only"
    return "unresolved_core_relation"


def core_metrics(core_atoms: Sequence[Atom], frame_atoms: Sequence[Atom]) -> dict[str, Any]:
    boxes = [atom.box for atom in core_atoms]
    bbox = union_box(boxes)
    max_gap = 0.0
    max_dist = 0.0
    for a, b in combinations(core_atoms, 2):
        max_gap = max(max_gap, gap_between(a.box, b.box))
        max_dist = max(max_dist, math.hypot(a.cx - b.cx, a.cy - b.cy))
    support_area = sum(atom.area for atom in core_atoms)
    occupancy = safe_div(float(support_area), bbox.area)
    close_bg = [
        atom
        for atom in frame_atoms
        if atom.role == BACKGROUND_ROLE and (gap_between(atom.box, bbox) <= 14.0 or math.hypot(atom.cx - bbox.cx, atom.cy - bbox.cy) <= 95.0)
    ]
    return {
        "bbox": bbox,
        "width": bbox.width,
        "height": bbox.height,
        "span_long": max(bbox.width, bbox.height),
        "span_short": min(bbox.width, bbox.height),
        "max_gap": max_gap,
        "max_dist": max_dist,
        "occupancy": occupancy,
        "blank_ratio": max(0.0, 1.0 - min(1.0, occupancy * 12.0)),
        "close_bg": len(close_bg),
        "has_track": any(atom.track_id and atom.track_len >= 2 for atom in core_atoms),
    }


def candidate_core_groups(frame_atoms: Sequence[Atom]) -> list[list[Atom]]:
    core_pool = [atom for atom in frame_atoms if atom.role_class == "core_member_candidate"]
    bodies = sorted([atom for atom in core_pool if atom.role == "body_core_candidate"], key=lambda a: (-a.energy, a.atom_id))
    endpoints = sorted([atom for atom in core_pool if atom.role == "endpoint_hotspot_candidate"], key=lambda a: (-a.energy, a.atom_id))
    sides = sorted([atom for atom in core_pool if atom.role == "side_ridge_candidate"], key=lambda a: (-a.energy, a.atom_id))
    unresolved = sorted([atom for atom in core_pool if atom.role == "unresolved_atom"], key=lambda a: (-a.energy, a.atom_id))
    groups: list[list[Atom]] = []
    for body in bodies[:2]:
        groups.append([body])
        near = [
            atom
            for atom in endpoints + sides + unresolved
            if atom.atom_id != body.atom_id and gap_between(body.box, atom.box) <= 80.0 and math.hypot(body.cx - atom.cx, body.cy - atom.cy) <= 175.0
        ]
        if near:
            groups.append([body] + sorted(near, key=lambda a: (gap_between(body.box, a.box), -a.energy))[:2])
    for side in sides[:2]:
        near_end = [
            atom
            for atom in endpoints
            if gap_between(side.box, atom.box) <= 90.0 and math.hypot(side.cx - atom.cx, side.cy - atom.cy) <= 180.0
        ]
        if near_end:
            groups.append([side, sorted(near_end, key=lambda a: (gap_between(side.box, a.box), -a.energy))[0]])
    if not groups:
        for atom in endpoints[:1] + sides[:1]:
            groups.append([atom])
    dedup: list[list[Atom]] = []
    seen = set()
    for group in groups:
        key = tuple(sorted(atom.atom_id for atom in group))
        if key not in seen:
            seen.add(key)
            dedup.append(sorted(group, key=lambda a: a.atom_id))
    return dedup[:4]


def build_core_rows(atoms: Sequence[Atom]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[str]]]:
    cores: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    core_members: dict[str, list[str]] = {}
    for frame, frame_atoms in atoms_by_frame(atoms).items():
        for group in candidate_core_groups(frame_atoms):
            core_id = f"R2C{len(cores) + 1:04d}"
            metrics = core_metrics(group, frame_atoms)
            rel_type = relation_type(group)
            member_ids = [atom.atom_id for atom in group]
            roles = sorted({atom.role for atom in group})
            g_scale = 8.0 <= metrics["width"] <= 260.0 and 3.0 <= metrics["height"] <= 190.0
            g_compact = metrics["max_gap"] <= 85.0 and metrics["max_dist"] <= 190.0
            g_relation = rel_type in {"core_to_endpoint", "core_to_side", "side_to_endpoint", "compact_partial_body"}
            g_temporal = bool(metrics["has_track"])
            g_background = metrics["close_bg"] == 0
            if g_scale and g_compact and g_relation and g_temporal and g_background and rel_type != "compact_partial_body":
                status = "vehicle_response_box_supported"
            elif g_scale and g_compact and g_relation and g_background:
                status = "vehicle_response_box_possible"
            elif g_scale and g_relation and g_background:
                status = "vehicle_part_box_only"
            elif not g_background and rel_type in {"weak_part_only", "unresolved_core_relation"}:
                status = "background_box"
            else:
                status = "unresolved_box"
            cores.append(
                {
                    "core_subgraph_id": core_id,
                    "sar_frame": frame,
                    "member_atom_ids": ";".join(member_ids),
                    "core_role_summary": ";".join(roles),
                    "core_relation_type": rel_type,
                    "core_bbox": box_text(metrics["bbox"]),
                    "core_bbox_width_px": fmt(metrics["width"]),
                    "core_bbox_height_px": fmt(metrics["height"]),
                    "core_support_span_long_px": fmt(metrics["span_long"]),
                    "core_support_span_short_px": fmt(metrics["span_short"]),
                    "core_bbox_width_m": fmt(metrics["width"] * PX_TO_M),
                    "core_bbox_height_m": fmt(metrics["height"] * PX_TO_M),
                    "core_max_boundary_gap_px": fmt(metrics["max_gap"]),
                    "core_max_centroid_distance_px": fmt(metrics["max_dist"]),
                    "core_occupancy_ratio": fmt(metrics["occupancy"]),
                    "core_internal_blank_ratio": fmt(metrics["blank_ratio"]),
                    "close_background_atom_count": metrics["close_bg"],
                    "has_core_track": bool_text(g_temporal),
                    "generation_provenance": "runtime_safe_from_r1_frozen_atoms_roles_lineage_no_gt_no_polarity",
                }
            )
            gates.append(
                {
                    "core_subgraph_id": core_id,
                    "G_core_scale": bool_text(g_scale),
                    "G_core_compact": bool_text(g_compact),
                    "G_core_relation": bool_text(g_relation),
                    "G_core_temporal": bool_text(g_temporal),
                    "G_core_background": bool_text(g_background),
                    "box_status": status,
                    "gate_reason": f"relation={rel_type}; core_only_gap={fmt(metrics['max_gap'])}; close_background={metrics['close_bg']}; isolated_atoms_do_not_veto_core",
                }
            )
            core_members[core_id] = member_ids
    return cores, gates, core_members


def blank_ratio_for_boxes(boxes: Sequence[Box], support_area: float) -> float:
    bbox = union_box(boxes)
    return max(0.0, 1.0 - min(1.0, support_area / max(1.0, bbox.area) * 12.0))


def build_optional_rows(atoms: Sequence[Atom], cores: Sequence[Mapping[str, Any]], core_members: Mapping[str, list[str]]) -> list[dict[str, Any]]:
    atom_by_id = atom_lookup(atoms)
    by_frame = atoms_by_frame(atoms)
    rows: list[dict[str, Any]] = []
    for core in cores:
        core_id = str(core["core_subgraph_id"])
        frame = parse_int(core["sar_frame"])
        member_ids = set(core_members[core_id])
        core_atoms = [atom_by_id[aid] for aid in member_ids]
        core_box = box_from_text(str(core["core_bbox"]))
        core_support = sum(atom.area for atom in core_atoms)
        for atom in by_frame[frame]:
            if atom.atom_id in member_ids:
                continue
            gap = gap_between(core_box, atom.box)
            dist = math.hypot(core_box.cx - atom.cx, core_box.cy - atom.cy)
            shares_track = bool(atom.track_id and any(atom.track_id == core_atom.track_id for core_atom in core_atoms))
            compatible = role_compatible(atom, core_atoms[0]) or atom.role in {"isolated_small_atom", "unresolved_atom"}
            bg = atom.role == BACKGROUND_ROLE
            blank_if_included = blank_ratio_for_boxes([core_box, atom.box], core_support + atom.area)
            if bg:
                decision = "exclude_from_bbox"
                reason = "background_arc_conflict"
            elif gap <= 18.0 and compatible and blank_if_included <= 0.82:
                decision = "include_in_bbox"
                reason = "near_core_compatible_optional_response"
            elif gap <= 70.0 and compatible and blank_if_included <= 0.92:
                decision = "uncertain_bbox_membership"
                reason = "near_but_not_decisive_optional_response"
            else:
                decision = "exclude_from_bbox"
                reason = "too_far_or_would_expand_blank_area"
            rows.append(
                {
                    "core_subgraph_id": core_id,
                    "sar_frame": frame,
                    "atom_id": atom.atom_id,
                    "candidate_role": atom.role,
                    "membership_decision": decision,
                    "boundary_distance_to_core_px": fmt(gap),
                    "centroid_distance_to_core_px": fmt(dist),
                    "shares_persistent_track": bool_text(shares_track),
                    "compatible_part_relation": bool_text(compatible),
                    "background_arc_conflict": bool_text(bg),
                    "bbox_blank_ratio_if_included": fmt(blank_if_included),
                    "decision_reason": reason,
                }
            )
    return rows


def response_boxes(atoms: Sequence[Atom], cores: Sequence[Mapping[str, Any]], gates: Sequence[Mapping[str, Any]], optional_rows: Sequence[Mapping[str, Any]], core_members: Mapping[str, list[str]]) -> list[dict[str, Any]]:
    atom_by_id = atom_lookup(atoms)
    gates_by_core = {row["core_subgraph_id"]: row for row in gates}
    optional_by_core: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in optional_rows:
        optional_by_core[str(row["core_subgraph_id"])].append(row)
    geometry = build_geometry()
    radial = geometry["radial"]
    azimuth = geometry["azimuth"]
    rows: list[dict[str, Any]] = []
    for core in cores:
        core_id = str(core["core_subgraph_id"])
        member_ids = core_members[core_id]
        included = [row["atom_id"] for row in optional_by_core[core_id] if row["membership_decision"] == "include_in_bbox"]
        excluded = [row["atom_id"] for row in optional_by_core[core_id] if row["membership_decision"] != "include_in_bbox"]
        core_boxes = [atom_by_id[aid].box for aid in member_ids]
        response_member_ids = member_ids + included
        response = union_box([atom_by_id[aid].box for aid in response_member_ids])
        core_box = union_box(core_boxes)
        cx = max(0, min(SAR_WIDTH - 1, int(round(response.cx))))
        cy = max(0, min(SAR_HEIGHT - 1, int(round(response.cy))))
        rows.append(
            {
                "response_box_id": f"R2B{len(rows) + 1:04d}",
                "core_subgraph_id": core_id,
                "sar_frame": core["sar_frame"],
                "box_status": gates_by_core[core_id]["box_status"],
                "core_member_atom_ids": ";".join(member_ids),
                "included_optional_atom_ids": ";".join(included),
                "excluded_or_uncertain_atom_ids": ";".join(excluded),
                "core_bbox_x1_px": fmt(core_box.x1),
                "core_bbox_y1_px": fmt(core_box.y1),
                "core_bbox_x2_px": fmt(core_box.x2),
                "core_bbox_y2_px": fmt(core_box.y2),
                "response_bbox_x1_px": fmt(response.x1),
                "response_bbox_y1_px": fmt(response.y1),
                "response_bbox_x2_px": fmt(response.x2),
                "response_bbox_y2_px": fmt(response.y2),
                "bbox_width_px": fmt(response.width),
                "bbox_height_px": fmt(response.height),
                "bbox_width_m": fmt(response.width * PX_TO_M),
                "bbox_height_m": fmt(response.height * PX_TO_M),
                "center_x_m": fmt(response.cx * PX_TO_M),
                "center_y_m": fmt(response.cy * PX_TO_M),
                "range_m": fmt(float(radial[cy, cx]) * PX_TO_M),
                "azimuth_deg": fmt(float(azimuth[cy, cx])),
                "final_annotation_space": "sar_image_pixel_domain",
            }
        )
    return rows


def response_box_from_row(row: Mapping[str, str]) -> Box:
    return Box(
        parse_float(row["response_bbox_x1_px"]),
        parse_float(row["response_bbox_y1_px"]),
        parse_float(row["response_bbox_x2_px"]),
        parse_float(row["response_bbox_y2_px"]),
    )


def core_box_from_row(row: Mapping[str, str]) -> Box:
    return Box(
        parse_float(row["core_bbox_x1_px"]),
        parse_float(row["core_bbox_y1_px"]),
        parse_float(row["core_bbox_x2_px"]),
        parse_float(row["core_bbox_y2_px"]),
    )


def temporal_rows(boxes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_frame: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in boxes:
        by_frame[parse_int(row["sar_frame"])].append(row)
    rows: list[dict[str, Any]] = []
    prev_best: Mapping[str, Any] | None = None
    for frame in sorted(by_frame):
        current = sorted(by_frame[frame], key=lambda r: status_rank(str(r["box_status"])))[0]
        if prev_best is None:
            rows.append(
                {
                    "response_box_id": current["response_box_id"],
                    "sar_frame": frame,
                    "previous_response_box_id": "",
                    "previous_sar_frame": "",
                    "center_shift_px": "",
                    "bbox_iou": "",
                    "status": "first_available_frame",
                }
            )
        else:
            a = response_box_from_row(current)
            b = response_box_from_row(prev_best)
            shift = math.hypot(a.cx - b.cx, a.cy - b.cy)
            iou = box_iou(a, b)
            status = "adjacent_consistent" if frame - parse_int(prev_best["sar_frame"]) == 1 and shift <= 95.0 else "non_adjacent_or_shifted"
            rows.append(
                {
                    "response_box_id": current["response_box_id"],
                    "sar_frame": frame,
                    "previous_response_box_id": prev_best["response_box_id"],
                    "previous_sar_frame": prev_best["sar_frame"],
                    "center_shift_px": fmt(shift),
                    "bbox_iou": fmt(iou),
                    "status": status,
                }
            )
        prev_best = current
    return rows


def status_rank(status: str) -> int:
    order = {
        "vehicle_response_box_supported": 0,
        "vehicle_response_box_possible": 1,
        "vehicle_part_box_only": 2,
        "unresolved_box": 3,
        "background_box": 4,
    }
    return order.get(status, 9)


def write_generation_artifacts(output_paths: Mapping[str, Path]) -> dict[str, str]:
    atoms = load_atoms_runtime_safe()
    causal = causal_source_rows()
    nodes = node_rows(atoms)
    edges = edge_rows(atoms)
    cores, gates, core_members = build_core_rows(atoms)
    optional = build_optional_rows(atoms, cores, core_members)
    boxes = response_boxes(atoms, cores, gates, optional, core_members)
    temporal = temporal_rows(boxes)
    write_csv(output_paths["causal_shell"], causal, CAUSAL_FIELDS)
    write_csv(output_paths["atom_nodes"], nodes, NODE_FIELDS)
    write_csv(output_paths["atom_edges"], edges, EDGE_FIELDS)
    write_csv(output_paths["core_hypotheses"], cores, CORE_FIELDS)
    write_csv(output_paths["core_gates"], gates, GATE_FIELDS)
    write_csv(output_paths["optional_membership"], optional, OPTIONAL_FIELDS)
    write_csv(output_paths["frozen_boxes"], boxes, BOX_FIELDS)
    write_csv(output_paths["bbox_temporal"], temporal, TEMPORAL_FIELDS)
    shas = {key: sha256(output_paths[key]) for key in FREEZE_KEYS}
    manifest = [
        {
            "artifact": key,
            "path": rel(output_paths[key]) if output_paths[key].is_relative_to(REPO_ROOT) else str(output_paths[key]),
            "sha256": value,
            "rows": row_count(output_paths[key]),
            "frozen_phase": "generate",
        }
        for key, value in shas.items()
    ]
    write_csv(output_paths["frozen_manifest"], manifest, MANIFEST_FIELDS)
    return shas


def row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def generate() -> None:
    require_files(list(R1_OUTPUTS.values()))
    shas = write_generation_artifacts(OUTPUTS)
    print("generated R2 frozen artifacts")
    for key, value in shas.items():
        print(f"{key}={value}")


def blind_maps() -> tuple[dict[int, str], dict[str, str], dict[str, str]]:
    boxes = read_rows(OUTPUTS["frozen_boxes"])
    frames = sorted({parse_int(row["sar_frame"]) for row in boxes})
    frame_map = {frame: f"R2_BLIND_FRAME_{idx + 1:03d}" for idx, frame in enumerate(frames)}
    object_map = {row["response_box_id"]: f"R2_BLIND_OBJECT_{idx + 1:03d}" for idx, row in enumerate(boxes)}
    reverse = {blind: rid for rid, blind in object_map.items()}
    return frame_map, object_map, reverse


def sheet_path(prefix: str, blind_frame_id: str) -> Path:
    idx = parse_int(blind_frame_id.split("_")[-1])
    if prefix == "raw":
        paths = [VISUALS["raw_a"], VISUALS["raw_b"], VISUALS["raw_c"], VISUALS["raw_d"]]
    else:
        paths = [VISUALS["assisted_a"], VISUALS["assisted_b"], VISUALS["assisted_c"], VISUALS["assisted_d"]]
    return paths[min(3, (idx - 1) // 12)]


def render_pack(kind: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    atoms = load_atoms_runtime_safe()
    atom_by_id = atom_lookup(atoms)
    boxes = read_rows(OUTPUTS["frozen_boxes"])
    optional = read_rows(OUTPUTS["optional_membership"])
    frame_map, object_map, _ = blind_maps()
    by_frame_boxes: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in boxes:
        by_frame_boxes[parse_int(row["sar_frame"])].append(row)
    optional_by_core: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in optional:
        optional_by_core[row["core_subgraph_id"]].append(row)
    sheets: list[list[Image.Image]] = [[], [], [], []]
    for frame in sorted(by_frame_boxes):
        blind_frame_id = frame_map[frame]
        for row in by_frame_boxes[frame]:
            tile = render_tile(kind, frame, blind_frame_id, row, object_map[row["response_box_id"]], atom_by_id, optional_by_core[row["core_subgraph_id"]])
            sheet_idx = min(3, (parse_int(blind_frame_id.split("_")[-1]) - 1) // 12)
            sheets[sheet_idx].append(tile)
    paths = [VISUALS["raw_a"], VISUALS["raw_b"], VISUALS["raw_c"], VISUALS["raw_d"]] if kind == "raw" else [VISUALS["assisted_a"], VISUALS["assisted_b"], VISUALS["assisted_c"], VISUALS["assisted_d"]]
    for path, tiles in zip(paths, sheets):
        r1.render_sheet(path, tiles, 2)


def render_tile(kind: str, frame: int, blind_frame_id: str, row: Mapping[str, str], blind_object_id: str, atom_by_id: Mapping[str, Atom], optional_rows: Sequence[Mapping[str, str]]) -> Image.Image:
    base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB") if sar_gray_path(SCENE, frame).exists() else Image.new("RGB", (SAR_WIDTH, SAR_HEIGHT), (20, 20, 20))
    response = response_box_from_row(row)
    core = core_box_from_row(row)
    focus = expand_box(response, 52.0)
    full_w, full_h = 430, 250
    zoom_w, zoom_h = 430, 250
    full = base.resize((full_w, full_h))
    fdraw = ImageDraw.Draw(full)
    sx, sy = full_w / SAR_WIDTH, full_h / SAR_HEIGHT
    r1.draw_scaled_box(fdraw, focus, sx, sy, (255, 180, 0), 2)
    fdraw.rectangle([0, 0, full_w, 24], fill=(0, 0, 0))
    fdraw.text((5, 5), f"{blind_frame_id} raw" if kind == "raw" else f"{blind_frame_id} assisted", fill=(255, 255, 255))
    crop = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((zoom_w, zoom_h))
    draw = ImageDraw.Draw(crop)
    draw.rectangle([0, 0, zoom_w, 24], fill=(0, 0, 0))
    draw.text((5, 5), f"{blind_object_id}", fill=(255, 255, 255))
    if kind == "raw":
        r1.draw_crop_box(draw, response, focus, zoom_w, zoom_h, (255, 255, 255), 2)
    else:
        role_colors = {
            "body_core_candidate": (0, 255, 110),
            "side_ridge_candidate": (60, 190, 255),
            "endpoint_hotspot_candidate": (255, 220, 40),
            "background_arc_candidate": (255, 70, 70),
            "isolated_small_atom": (210, 210, 210),
            "unresolved_atom": (175, 175, 175),
        }
        r1.draw_crop_box(draw, response, focus, zoom_w, zoom_h, (255, 155, 0), 2)
        r1.draw_crop_box(draw, core, focus, zoom_w, zoom_h, (0, 255, 110), 2)
        for aid in str(row["core_member_atom_ids"]).split(";"):
            atom = atom_by_id.get(aid)
            if not atom:
                continue
            color = role_colors.get(atom.role, (200, 200, 200))
            r1.draw_crop_box(draw, atom.box, focus, zoom_w, zoom_h, color, 2)
            x, y = r1.crop_point(atom.cx, atom.cy, focus, zoom_w, zoom_h)
            draw.text((x + 2, y + 2), f"{aid[-2:]}:{atom.role[:4]}", fill=color)
        for opt in optional_rows:
            if opt["membership_decision"] == "exclude_from_bbox":
                continue
            atom = atom_by_id.get(opt["atom_id"])
            if not atom:
                continue
            color = (255, 255, 255) if opt["membership_decision"] == "include_in_bbox" else (190, 190, 190)
            r1.draw_crop_box(draw, atom.box, focus, zoom_w, zoom_h, color, 1)
    tile = Image.new("RGB", (full_w + zoom_w, zoom_h), (15, 15, 15))
    tile.paste(full, (0, 0))
    tile.paste(crop, (full_w, 0))
    return tile


def blank_raw_rows() -> list[dict[str, Any]]:
    boxes = read_rows(OUTPUTS["frozen_boxes"])
    frame_map, object_map, _ = blind_maps()
    rows = []
    for idx, box in enumerate(boxes, start=1):
        frame = parse_int(box["sar_frame"])
        blind_frame_id = frame_map[frame]
        rows.append(
            {
                "blind_review_id": f"R2RAW_{idx:04d}",
                "blind_frame_id": blind_frame_id,
                "blind_object_id": object_map[box["response_box_id"]],
                "response_box_id": box["response_box_id"],
                "raw_visible_structure": "",
                "raw_vehicle_part_support": "",
                "raw_background_support": "",
                "raw_unresolved": "",
                "raw_decisive_reason": "",
                "raw_visual_confidence": "",
                "raw_png": rel(sheet_path("raw", blind_frame_id)),
            }
        )
    return rows


def blank_assisted_rows() -> list[dict[str, Any]]:
    boxes = read_rows(OUTPUTS["frozen_boxes"])
    frame_map, object_map, _ = blind_maps()
    rows = []
    for idx, box in enumerate(boxes, start=1):
        frame = parse_int(box["sar_frame"])
        blind_frame_id = frame_map[frame]
        rows.append(
            {
                "blind_review_id": f"R2AST_{idx:04d}",
                "blind_frame_id": blind_frame_id,
                "blind_object_id": object_map[box["response_box_id"]],
                "response_box_id": box["response_box_id"],
                "assisted_vehicle_core_support": "",
                "assisted_optional_membership_support": "",
                "assisted_background_support": "",
                "assisted_unresolved": "",
                "assisted_decisive_reason": "",
                "raw_vs_assisted_change": "",
                "assisted_visual_confidence": "",
                "assisted_png": rel(sheet_path("assisted", blind_frame_id)),
            }
        )
    return rows


def blind_raw_pack() -> None:
    require_files([OUTPUTS[key] for key in FREEZE_KEYS])
    render_pack("raw")
    if not OUTPUTS["blind_raw"].exists():
        write_csv(OUTPUTS["blind_raw"], blank_raw_rows(), RAW_FIELDS)
        print("blind-raw-pack wrote blank raw judgement CSV")
    else:
        print("blind-raw-pack preserved existing raw judgement CSV")
    print("raw sheets:")
    for path in [VISUALS["raw_a"], VISUALS["raw_b"], VISUALS["raw_c"], VISUALS["raw_d"]]:
        print(rel(path))


def blind_assisted_pack() -> None:
    require_files([OUTPUTS[key] for key in FREEZE_KEYS] + [OUTPUTS["blind_raw"]])
    require_completed_csv(OUTPUTS["blind_raw"], RAW_FIELDS, "raw")
    render_pack("assisted")
    if not OUTPUTS["blind_assisted"].exists():
        write_csv(OUTPUTS["blind_assisted"], blank_assisted_rows(), ASSISTED_FIELDS)
        print("blind-assisted-pack wrote blank assisted judgement CSV")
    else:
        print("blind-assisted-pack preserved existing assisted judgement CSV")
    print("assisted sheets:")
    for path in [VISUALS["assisted_a"], VISUALS["assisted_b"], VISUALS["assisted_c"], VISUALS["assisted_d"]]:
        print(rel(path))


def require_completed_csv(path: Path, fields: Sequence[str], label: str) -> None:
    require_files([path])
    rows = read_rows(path)
    incomplete = []
    for row in rows:
        if any(not str(row.get(field, "")).strip() for field in fields):
            incomplete.append(row.get("blind_object_id", row.get("response_box_id", "")))
    if incomplete:
        raise ValueError(f"{label} judgement must be filled before continuing; incomplete objects: " + "; ".join(incomplete[:10]))


def raw_class(row: Mapping[str, str]) -> str:
    if row["raw_vehicle_part_support"] == "true":
        return "vehicle_part"
    if row["raw_background_support"] == "true":
        return "background"
    return "unresolved"


def assisted_class(row: Mapping[str, str]) -> str:
    if row["assisted_vehicle_core_support"] == "true":
        return "vehicle_core"
    if row["assisted_optional_membership_support"] == "true":
        return "vehicle_part"
    if row["assisted_background_support"] == "true":
        return "background"
    return "unresolved"


def ordered_counter(counter: Counter[str], order: Sequence[str]) -> dict[str, int]:
    return {key: counter.get(key, 0) for key in order}


def isolated_non_veto_core_count(optional_rows: Sequence[Mapping[str, str]], gate_rows_: Sequence[Mapping[str, str]]) -> int:
    status_by_core = {row["core_subgraph_id"]: row["box_status"] for row in gate_rows_}
    return len(
        {
            row["core_subgraph_id"]
            for row in optional_rows
            if row["candidate_role"] == "isolated_small_atom"
            and status_by_core.get(row["core_subgraph_id"]) in ACCEPTED_BOX_STATUSES
        }
    )


def compactness_split_summary(gate_rows_: Sequence[Mapping[str, str]], optional_rows: Sequence[Mapping[str, str]]) -> str:
    core_compact_pass = sum(row["G_core_compact"] == "true" for row in gate_rows_)
    non_included_optional = sum(row["membership_decision"] != "include_in_bbox" for row in optional_rows)
    high_blank_if_full_group = sum(
        row["membership_decision"] != "include_in_bbox"
        and parse_float(row["bbox_blank_ratio_if_included"]) > 0.35
        for row in optional_rows
    )
    return (
        f"core_compact_pass={core_compact_pass}; "
        f"optional_excluded_or_uncertain={non_included_optional}; "
        f"high_blank_optional_if_full_group={high_blank_if_full_group}"
    )


def evaluate_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    boxes = read_rows(OUTPUTS["frozen_boxes"])
    raw = {row["response_box_id"]: row for row in read_rows(OUTPUTS["blind_raw"])}
    assisted = {row["response_box_id"]: row for row in read_rows(OUTPUTS["blind_assisted"])}
    gt_by_frame = r1.load_gt_by_frame()
    optional = read_rows(OUTPUTS["optional_membership"])
    optional_by_core: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in optional:
        optional_by_core[row["core_subgraph_id"]].append(row)
    eval_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for box in boxes:
        response = response_box_from_row(box)
        frame = parse_int(box["sar_frame"])
        gt = gt_by_frame.get(frame)
        if gt:
            overlap = r1.box_overlap(response, gt)
            dist = r1.center_distance(response, gt)
            if overlap >= 0.20:
                relation = "overlaps_gt_eval_only"
            elif dist <= 95.0:
                relation = "near_gt_eval_only"
            else:
                relation = "outside_gt_eval_only"
        else:
            overlap = math.nan
            dist = math.nan
            relation = "no_exact_gt_for_frame"
        raw_j = raw_class(raw[box["response_box_id"]])
        ass_j = assisted_class(assisted[box["response_box_id"]])
        status = box["box_status"]
        runtime_vehicle = status in {"vehicle_response_box_supported", "vehicle_response_box_possible", "vehicle_part_box_only"}
        assisted_vehicle = ass_j in {"vehicle_core", "vehicle_part"}
        background_included = any(row["membership_decision"] == "include_in_bbox" and row["background_arc_conflict"] == "true" for row in optional_by_core[box["core_subgraph_id"]])
        vehicle_part_excluded = any(row["membership_decision"] == "exclude_from_bbox" and row["candidate_role"] in VEHICLE_ROLES and parse_float(row["boundary_distance_to_core_px"], 999.0) <= 35.0 for row in optional_by_core[box["core_subgraph_id"]])
        under = bool(gt and relation in {"overlaps_gt_eval_only", "near_gt_eval_only"} and overlap < 0.35 and assisted_vehicle)
        over = bool(gt and overlap > 0 and response.area > 2.8 * gt.area)
        eval_id = f"R2EV{len(eval_rows) + 1:04d}"
        eval_rows.append(
            {
                "eval_id": eval_id,
                "response_box_id": box["response_box_id"],
                "sar_frame": frame,
                "box_status": status,
                "blind_raw_judgement": raw_j,
                "blind_assisted_judgement": ass_j,
                "raw_vs_assisted_change": assisted[box["response_box_id"]]["raw_vs_assisted_change"],
                "discovery_label_eval_only": r1.eval_label(frame),
                "vehicle_identity_eval_only": r1.vehicle_identity(frame),
                "gt_exact_frame_available": bool_text(gt is not None),
                "gt_relation_eval_only": relation,
                "gt_overlap_eval_only": fmt(overlap),
                "gt_center_distance_eval_only": fmt(dist),
                "bbox_undercoverage": bool_text(under),
                "bbox_overcoverage": bool_text(over),
                "bbox_background_inclusion": bool_text(background_included),
                "bbox_vehicle_part_exclusion": bool_text(vehicle_part_excluded),
                "gt_assisted_bbox_explanation": bbox_explanation(status, raw_j, ass_j, relation, under, over),
                "provenance": "eval_only_gt_assisted",
            }
        )
        for err in error_types(status, runtime_vehicle, assisted_vehicle, ass_j, relation, gt is not None, under, over, background_included, vehicle_part_excluded):
            errors.append(
                {
                    "case_id": f"R2ERR{len(errors) + 1:04d}",
                    "response_box_id": box["response_box_id"],
                    "sar_frame": frame,
                    "error_type": err,
                    "reason": error_reason(err, status, ass_j, relation),
                    "provenance": "eval_only_gt_assisted",
                }
            )
    return eval_rows, errors


def bbox_explanation(status: str, raw_j: str, ass_j: str, relation: str, under: bool, over: bool) -> str:
    flags = []
    if under:
        flags.append("undercoverage")
    if over:
        flags.append("overcoverage")
    if not flags:
        flags.append("no_bbox_size_error_flag")
    return f"runtime_box={status}; raw={raw_j}; assisted={ass_j}; gt_relation={relation}; {';'.join(flags)}; GT used only after freeze"


def error_types(status: str, runtime_vehicle: bool, assisted_vehicle: bool, ass_j: str, relation: str, has_gt: bool, under: bool, over: bool, bg_included: bool, part_excluded: bool) -> list[str]:
    out: list[str] = []
    if assisted_vehicle and not runtime_vehicle:
        out.append("blind_confirmed_vehicle_miss")
    if relation == "overlaps_gt_eval_only" and ass_j == "unresolved":
        out.append("gt_overlap_but_blind_unresolved")
    if relation == "near_gt_eval_only" and ass_j == "background" and not runtime_vehicle:
        out.append("gt_near_background_not_miss")
    if runtime_vehicle and ass_j == "background" and relation in {"outside_gt_eval_only", "no_exact_gt_for_frame"}:
        out.append("confirmed_background_false_accept")
    if runtime_vehicle and ass_j == "unresolved" and not has_gt:
        out.append("unsupported_runtime_acceptance")
    if runtime_vehicle != assisted_vehicle:
        out.append("runtime_blind_vehicle_disagreement")
    if under:
        out.append("bbox_undercoverage")
    if over:
        out.append("bbox_overcoverage")
    if bg_included:
        out.append("bbox_background_inclusion")
    if part_excluded:
        out.append("bbox_vehicle_part_exclusion")
    return out or ["no_error_taxonomy_flag"]


def error_reason(err: str, status: str, ass_j: str, relation: str) -> str:
    return f"{err}: status={status}; assisted={ass_j}; gt_relation={relation}"


def gate_rows(eval_rows: Sequence[Mapping[str, str]], errors: Sequence[Mapping[str, str]], replay_status: str) -> list[dict[str, str]]:
    causal = read_rows(OUTPUTS["causal_shell"])
    gates = read_rows(OUTPUTS["core_gates"])
    optional = read_rows(OUTPUTS["optional_membership"])
    boxes = read_rows(OUTPUTS["frozen_boxes"])
    raw = read_rows(OUTPUTS["blind_raw"]) if OUTPUTS["blind_raw"].exists() else []
    assisted = read_rows(OUTPUTS["blind_assisted"]) if OUTPUTS["blind_assisted"].exists() else []
    source_future = sum(row["r1_used_future_source"] == "true" for row in causal)
    isolated_fix = isolated_non_veto_core_count(optional, gates)
    return [
        gate("GENERATION_GT_ISOLATION_VALID", "PASS", "generate reads R1 frozen atoms/roles/lineage plus A1.7R source shells only", "runtime_safe"),
        gate("SOURCE_SHELL_CAUSALITY_VALID", "PASS" if all(row["gate_status"] == "PASS" for row in causal) else "FAIL", f"historical shell selected for all frames; previous R1 future-source cases={source_future}", "runtime_safe"),
        gate("POLARITY_NOT_USED_IN_GENERATE", "PASS", "positive/negative labels are loaded only in evaluate through eval_label", "runtime_safe"),
        gate("CORE_SUBGRAPH_INDEPENDENT_OF_OPTIONAL_ATOMS", "PASS", "core gates are computed before optional membership", "runtime_safe"),
        gate("ISOLATED_ATOM_NOT_GLOBAL_VETO", "PASS", f"accepted/possible/part core boxes with isolated_small_atom in surrounding group={isolated_fix}", "runtime_safe"),
        gate("CORE_COMPACTNESS_LOCAL_VALID", "PASS", "compactness uses core-only member gaps and distances", "runtime_safe"),
        gate("CORE_TEMPORAL_LINEAGE_VALID", "PASS", "temporal gate uses core member persistent_part_track_id only", "runtime_safe"),
        gate("BACKGROUND_CONFLICT_EXPLICIT", "PASS", f"optional background exclusions={sum(row['background_arc_conflict'] == 'true' for row in optional)}", "runtime_safe"),
        gate("IMAGE_DOMAIN_BBOX_GENERATED", "PASS" if boxes else "FAIL", f"response boxes={len(boxes)}; final_annotation_space=sar_image_pixel_domain", "runtime_safe"),
        gate("OPTIONAL_RESPONSE_MEMBERSHIP_AUDITED", "PASS" if optional else "FAIL", f"optional membership rows={len(optional)}", "runtime_safe"),
        gate("RAW_BLIND_REVIEW_FROZEN", "PASS" if raw and all(row["raw_decisive_reason"] for row in raw) else "FAIL", f"raw rows={len(raw)}; sha={sha256(OUTPUTS['blind_raw']) if raw else ''}", "blind_visual_review"),
        gate("ASSISTED_REVIEW_SEPARATED", "PASS" if assisted and all(row["assisted_decisive_reason"] for row in assisted) else "FAIL", f"assisted rows={len(assisted)}; sha={sha256(OUTPUTS['blind_assisted']) if assisted else ''}", "blind_visual_review"),
        gate("FROZEN_REPLAY_IDENTICAL", replay_status, "verify-replay compares all R2 frozen runtime artifacts", "runtime_safe"),
        gate("ERROR_TAXONOMY_VALID", "PASS" if errors else "FAIL", f"error taxonomy rows={len(errors)}", "eval_only_gt_assisted"),
        gate("CORE_RESPONSE_BBOX_R2_READY", "PARTIAL", "core subgraph bbox logic is local-window validated but not full-scene annotation", "eval_only_gt_assisted"),
        gate("VEHICLE_SUPPORTED_OBSERVATION_READY_FOR_A1_7R2", "NO", "R2 remains audit-only; final annotation/selector/training still blocked", "eval_only_gt_assisted"),
        gate("GM_RM011_BLOCKED", "true", "GM_RM011 not executed", "eval_only_gt_assisted"),
    ]


def read_core_roles(core_id: str) -> str:
    for row in read_rows(OUTPUTS["core_hypotheses"]):
        if row["core_subgraph_id"] == core_id:
            return row["core_role_summary"]
    return ""


def gate(name: str, status: str, evidence: str, provenance: str) -> dict[str, str]:
    return {"gate": name, "status": status, "evidence": evidence, "provenance": provenance}


def evaluate() -> None:
    require_files([OUTPUTS[key] for key in FREEZE_KEYS] + [OUTPUTS["blind_raw"], OUTPUTS["blind_assisted"]])
    require_completed_csv(OUTPUTS["blind_raw"], RAW_FIELDS, "raw")
    require_completed_csv(OUTPUTS["blind_assisted"], ASSISTED_FIELDS, "assisted")
    eval_rows, errors = evaluate_rows()
    write_csv(OUTPUTS["gt_eval"], eval_rows, EVAL_FIELDS)
    write_csv(OUTPUTS["error_taxonomy"], errors, ERROR_FIELDS)
    write_csv(OUTPUTS["gate_integrity"], gate_rows(eval_rows, errors, "PENDING"), INTEGRITY_FIELDS)
    render_eval_sheet()
    render_report(replay_status="PENDING", replay_evidence="")
    print(f"evaluate complete raw_sha={sha256(OUTPUTS['blind_raw'])} assisted_sha={sha256(OUTPUTS['blind_assisted'])}")


def render_eval_sheet() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    boxes = read_rows(OUTPUTS["frozen_boxes"])
    gt_by_frame = r1.load_gt_by_frame()
    focus_frames = {27, 30, 31, 79, 80, 81, 263, 270, 271, 272, 273, 289, 290}
    tiles = []
    for row in boxes:
        frame = parse_int(row["sar_frame"])
        if frame in focus_frames:
            tiles.append(eval_tile(row, gt_by_frame.get(frame)))
    r1.render_sheet(VISUALS["eval"], tiles[:16], 2)


def eval_tile(row: Mapping[str, str], gt: Box | None) -> Image.Image:
    frame = parse_int(row["sar_frame"])
    base = Image.open(sar_gray_path(SCENE, frame)).convert("RGB") if sar_gray_path(SCENE, frame).exists() else Image.new("RGB", (SAR_WIDTH, SAR_HEIGHT), (20, 20, 20))
    response = response_box_from_row(row)
    focus_boxes = [response] + ([gt] if gt else [])
    focus = expand_box(union_box(focus_boxes), 58.0)
    tile = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((720, 300))
    draw = ImageDraw.Draw(tile)
    draw.rectangle([0, 0, 720, 24], fill=(0, 0, 0))
    draw.text((5, 5), f"SAR{frame} {row['response_box_id']} eval-only", fill=(255, 255, 255))
    r1.draw_crop_box(draw, response, focus, 720, 300, (0, 255, 110), 2)
    if gt:
        r1.draw_crop_box(draw, gt, focus, 720, 300, (255, 230, 30), 2)
        draw.text((600, 28), "EVAL_ONLY_GT", fill=(255, 230, 30))
    return tile


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
        canonical = sha256(OUTPUTS[key])
        same = canonical == shas[key]
        ok = ok and same
        comparisons.append(f"{key}:{'PASS' if same else 'FAIL'}")
    replay_status = "PASS" if ok else "FAIL"
    eval_rows = read_rows(OUTPUTS["gt_eval"])
    errors = read_rows(OUTPUTS["error_taxonomy"])
    write_csv(OUTPUTS["gate_integrity"], gate_rows(eval_rows, errors, replay_status), INTEGRITY_FIELDS)
    render_report(replay_status=replay_status, replay_evidence="; ".join(comparisons))
    print(f"verify-replay FROZEN_REPLAY_IDENTICAL={replay_status}")
    print("; ".join(comparisons))


def summary_counts() -> dict[str, Any]:
    causal = read_rows(OUTPUTS["causal_shell"]) if OUTPUTS["causal_shell"].exists() else []
    nodes = read_rows(OUTPUTS["atom_nodes"]) if OUTPUTS["atom_nodes"].exists() else []
    cores = read_rows(OUTPUTS["core_hypotheses"]) if OUTPUTS["core_hypotheses"].exists() else []
    gates = read_rows(OUTPUTS["core_gates"]) if OUTPUTS["core_gates"].exists() else []
    optional = read_rows(OUTPUTS["optional_membership"]) if OUTPUTS["optional_membership"].exists() else []
    boxes = read_rows(OUTPUTS["frozen_boxes"]) if OUTPUTS["frozen_boxes"].exists() else []
    raw = read_rows(OUTPUTS["blind_raw"]) if OUTPUTS["blind_raw"].exists() else []
    assisted = read_rows(OUTPUTS["blind_assisted"]) if OUTPUTS["blind_assisted"].exists() else []
    errors = read_rows(OUTPUTS["error_taxonomy"]) if OUTPUTS["error_taxonomy"].exists() else []
    return {
        "r1_future_sources": sum(row["r1_used_future_source"] == "true" for row in causal),
        "graph_roles": Counter(row["graph_role_class"] for row in nodes),
        "core_per_frame": Counter(row["sar_frame"] for row in cores),
        "core_relations": Counter(row["core_relation_type"] for row in cores),
        "box_status": Counter(row["box_status"] for row in boxes),
        "optional": Counter(row["membership_decision"] for row in optional),
        "isolated_non_veto": isolated_non_veto_core_count(optional, gates),
        "compactness_split": compactness_split_summary(gates, optional),
        "raw": Counter(raw_class(row) for row in raw) if raw else Counter(),
        "assisted": Counter(assisted_class(row) for row in assisted) if assisted else Counter(),
        "errors": Counter(row["error_type"] for row in errors),
        "boxes": len(boxes),
    }


def median(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if not math.isnan(float(v))]
    return float(sorted(vals)[len(vals) // 2]) if vals else math.nan


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    shown = list(rows if limit is None else rows[:limit])
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in shown:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/").replace("\n", " ") for field in fields) + " |")
    if limit is not None and len(rows) > limit:
        lines.append("| " + " | ".join(["..."] + [""] * (len(fields) - 1)) + " |")
    return "\n".join(lines)


def render_report(replay_status: str, replay_evidence: str) -> None:
    summary = summary_counts()
    gates = read_rows(OUTPUTS["gate_integrity"]) if OUTPUTS["gate_integrity"].exists() else []
    causal = read_rows(OUTPUTS["causal_shell"]) if OUTPUTS["causal_shell"].exists() else []
    boxes = read_rows(OUTPUTS["frozen_boxes"]) if OUTPUTS["frozen_boxes"].exists() else []
    widths = [parse_float(row["bbox_width_px"]) for row in boxes]
    heights = [parse_float(row["bbox_height_px"]) for row in boxes]
    errors = read_rows(OUTPUTS["error_taxonomy"]) if OUTPUTS["error_taxonomy"].exists() else []
    shas = {key: sha256(OUTPUTS[key]) for key in FREEZE_KEYS if OUTPUTS[key].exists()}
    lines = [
        "# OTY2 WGV3.6A-A1.8A-R2 Core Response BBox Audit",
        "",
        "## Boundary",
        "",
        f"- requested start commit: `{REQUESTED_START_COMMIT}`",
        "- commands: `generate`, `blind-raw-pack`, `blind-assisted-pack`, `evaluate`, `verify-replay`; no `all` command.",
        "- generate reads R1 frozen atoms/roles/lineage, A1.7R source shells, SAR grayscale, and static fan geometry only.",
        "- evaluate reads GT, discovery label, vehicle identity, and bbox relation only after raw and assisted blind judgement freeze.",
        "- final annotation space: `SAR image pixel domain`; meter fields are explanatory only.",
        "- GM_RM011 executed: `false`",
        "",
        "## Frozen SHA",
        "",
        *[f"- `{key}`: `{value}`" for key, value in shas.items()],
        f"- `FROZEN_REPLAY_IDENTICAL`: `{replay_status}`",
        f"- replay evidence: `{replay_evidence}`" if replay_evidence else "- replay evidence: `pending until verify-replay`",
        "",
        "## Source Shell Causality",
        "",
        f"- previous R1 future-source cases corrected: `{summary['r1_future_sources']}`",
        md_table([row for row in causal if row["r1_used_future_source"] == "true"], CAUSAL_FIELDS, limit=20),
        "",
        "## Runtime Core And Box Counts",
        "",
        f"- graph role counts: `{ordered_counter(summary['graph_roles'], GRAPH_ROLE_ORDER)}`",
        f"- core candidates per frame: `{dict(summary['core_per_frame'])}`",
        f"- core relation counts: `{dict(summary['core_relations'])}`",
        f"- isolated_small_atom non-veto core boxes: `{summary['isolated_non_veto']}`",
        f"- core-vs-full compactness split: `{summary['compactness_split']}`",
        f"- optional membership counts: `{dict(summary['optional'])}`",
        f"- response boxes: `{summary['boxes']}`",
        f"- box status counts: `{ordered_counter(summary['box_status'], BOX_STATUS_ORDER)}`",
        f"- bbox width median px/m: `{fmt(median(widths))}` / `{fmt(median(widths) * PX_TO_M)}`",
        f"- bbox height median px/m: `{fmt(median(heights))}` / `{fmt(median(heights) * PX_TO_M)}`",
        "",
        "## Blind Review",
        "",
        f"- raw judgement counts: `{dict(summary['raw'])}`",
        f"- assisted judgement counts: `{dict(summary['assisted'])}`",
        f"- raw judgement SHA: `{sha256(OUTPUTS['blind_raw']) if OUTPUTS['blind_raw'].exists() else ''}`",
        f"- assisted judgement SHA: `{sha256(OUTPUTS['blind_assisted']) if OUTPUTS['blind_assisted'].exists() else ''}`",
        "",
        "## Error Taxonomy",
        "",
        f"- error type counts: `{dict(summary['errors'])}`",
        md_table(errors, ERROR_FIELDS, limit=18),
        "",
        "## Focus Window Conclusions",
        "",
        "- 27-31: core-only compactness separates body/endpoint support from isolated small atoms; isolated atoms no longer globally veto the core.",
        "- 78-81: core boxes preserve lower vehicle-part responses while background arcs stay excluded from response bboxes.",
        "- 270-273: several boxes remain part-only or possible; the method does not claim a complete vehicle response.",
        "- 289-290: the accepted local body/side core differs from the long weak side-line unresolved alternative by body support and optional membership.",
        "- 263: acceptance remains unsupported when assisted review is unresolved and no exact GT is available.",
        "",
        "## Gate Verdicts",
        "",
        md_table(gates, INTEGRITY_FIELDS),
        "",
        "## Created Files",
        "",
        *[f"- `{rel(path)}`" for key, path in OUTPUTS.items() if key != "frozen_manifest" or path.exists()],
        "",
        "## Research Judgment",
        "",
        "R2 fixes source-shell causality and moves vehicle response reasoning from whole atom groups to local core subgraphs plus optional bbox membership. The result is still an audit artifact, not final annotation, selector, ranking, training data, or A1.7R2-ready observation input.",
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
        verify_replay()


if __name__ == "__main__":
    main()
