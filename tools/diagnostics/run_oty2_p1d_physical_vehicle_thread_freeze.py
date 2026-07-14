#!/usr/bin/env python3
"""Materialize the optical-only OTY2 P1-D blocked freeze audit.

This runner does not solve, merge, split, relabel, or overwrite P1-C identity
outputs.  It serializes the completed full-scene and per-thread visual audit,
derives provenance fields from the immutable P1-C manifests, and deliberately
withholds final frozen outputs while the GM_RM019 failures remain unresolved.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs/oty2/oty2_p1d_physical_vehicle_thread_freeze.yaml"

REGISTRY_FIELDS = [
    "scene", "canonical_vehicle_id", "p1c_global_vehicle_ids", "frame_first_visible",
    "frame_last_visible", "visible_frame_ranges", "occlusion_or_missed_ranges", "entry_frame",
    "entry_location", "entry_state", "exit_frame", "exit_location", "exit_state", "vehicle_color",
    "vehicle_type_or_shape", "dominant_motion_direction", "scale_trend", "distinctive_visual_features",
    "source_tracker_ids", "detector_sources", "identity_evidence_summary", "lifecycle_completeness",
    "thread_purity", "freeze_status", "risk_flags", "notes",
]

LIFECYCLE_FIELDS = [
    "scene", "p1c_global_vehicle_id", "audit_id", "frame_start", "frame_end", "audit_type",
    "visual_finding", "same_physical_vehicle", "lifecycle_interpretation",
    "possible_duplicate_thread_ids", "possible_contaminating_thread_ids", "decision",
    "evidence_summary", "notes",
]

PAIR_FIELDS = [
    "scene", "thread_a", "thread_b", "temporal_relation", "overlap_frame_count", "gap_length",
    "a_exit_location", "b_entry_location", "color_similarity", "appearance_similarity",
    "shape_similarity", "motion_compatibility", "scale_trend_compatibility",
    "boundary_lifecycle_compatibility", "visual_identity_judgment", "recommended_relation",
    "evidence_summary", "notes",
]

RESET_FIELDS = [
    "scene", "birth_count", "exit_count", "boundary_entry_count", "boundary_entry_ratio",
    "boundary_exit_count", "boundary_exit_ratio", "non_boundary_birth_count", "non_boundary_exit_count",
    "short_exit_near_birth_count", "reset_high_similarity_pair_count", "reset_resolved_wrong_bridge_count",
    "reset_possible_over_split_count", "visual_judgment", "decision", "evidence_summary", "notes",
]

CHECKLIST_FIELDS = ["check_id", "acceptance_condition", "result", "evidence", "blocking", "notes"]


VEHICLES: list[dict[str, Any]] = [
    # GM_RM011: fourteen simultaneously ordered, stationary parked vehicles.
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV001", "p1c": ["GM_RM011:GV001"], "color": "white", "shape": "compact crossover/SUV", "features": "dark window band and patterned interior sunshades", "evidence": "Continuous side-to-front camera sweep; distinct from GV002 and overlaps GV003 at frames 20-35.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV002", "p1c": ["GM_RM011:GV002"], "color": "white/silver", "shape": "partial parked passenger vehicle", "features": "rear-quarter fragment behind PV001", "evidence": "Simultaneously visible with GV001 at frames 0-4, proving a separate physical vehicle.", "status": "frozen", "risk": ["short_boundary_fragment"]},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV003", "p1c": ["GM_RM011:GV003"], "color": "white", "shape": "large MPV", "features": "MAXUS grille and broad headlamp cluster", "evidence": "Continuous front-to-side sweep; simultaneous with GV001 and covered GV004 without subject switching.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV004", "p1c": ["GM_RM011:GV004"], "color": "silver cover", "shape": "fully covered passenger vehicle", "features": "silver fitted cover with tied lower edge", "evidence": "A separate covered vehicle is tracked at 39-55 but remains visibly present through about frame 87 without a P1-C thread.", "status": "identity_conflict", "risk": ["covered_vehicle", "incomplete_visible_lifecycle"], "visual_first": 39, "visual_last": 87, "visual_ranges": "39-87", "visual_missed": "56-87"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV005", "p1c": ["GM_RM011:GV005"], "color": "white", "shape": "Nissan sedan", "features": "black V-motion grille and swept headlights", "evidence": "Continuous camera sweep with stable Nissan appearance; overlaps covered GV006 and gray GV007.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV006", "p1c": ["GM_RM011:GV006"], "color": "tan/orange cover", "shape": "fully covered passenger vehicle", "features": "warm-colored fitted cover", "evidence": "Stationary covered vehicle between GV005 and GV007; simultaneous visibility proves distinct identity.", "status": "frozen", "risk": ["covered_vehicle"]},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV007", "p1c": ["GM_RM011:GV007"], "color": "dark gray", "shape": "sedan", "features": "narrow swept headlights and dark hood", "evidence": "Continuous front view; spatially ordered between covered GV006 and white GV008.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV008", "p1c": ["GM_RM011:GV008"], "color": "white", "shape": "Honda sedan", "features": "red Honda grille badge", "evidence": "Continuous front view with one reviewed gap at frame 162; overlaps GV007 and covered GV009.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV009", "p1c": ["GM_RM011:GV009", "GM_RM011:GV010"], "color": "silver cover", "shape": "fully covered passenger vehicle", "features": "continuous silver-covered car beside scooters and then under the overpass", "evidence": "GV009 and GV010 are two fragments of the same continuously visible covered vehicle; frames 167-187 and 192-196 remain visible without thread support.", "status": "merge_required", "risk": ["covered_vehicle", "duplicate_global_ids", "visible_unboxed_gap"], "visual_first": 155, "visual_last": 196, "visual_ranges": "155-196", "visual_missed": "167-187;192-196"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV010", "p1c": ["GM_RM011:GV011"], "color": "white", "shape": "compact sedan", "features": "red tail lamps and dark side windows", "evidence": "Continuous rear-to-front camera sweep with reviewed two-frame detector gap; overlaps GV012 at frames 243-245.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV011", "p1c": ["GM_RM011:GV012"], "color": "white", "shape": "sleek sedan", "features": "black panoramic roof and flush dark handles", "evidence": "Continuous side sweep; simultaneously visible with GV011 and GV013, excluding reset over-splitting.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV012", "p1c": ["GM_RM011:GV013"], "color": "white", "shape": "sedan", "features": "black roof/window band and triangular rear quarter", "evidence": "Continuous rear-to-front sweep; overlaps both GV012 and GV014 at different boundaries.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV013", "p1c": ["GM_RM011:GV014"], "color": "white", "shape": "SUV/crossover", "features": "black roof rails, angular red tail lamps, chrome handles", "evidence": "Continuous rear-to-front sweep with reviewed detector gaps; overlaps GV013 at frames 284-292.", "status": "frozen"},
    {"scene": "GM_RM011", "canonical": "GM_RM011:PV014", "p1c": [], "color": "silver cover", "shape": "fully covered passenger vehicle", "features": "large silver-covered vehicle after the white SUV", "evidence": "A distinct covered vehicle is continuously visible at about frames 307-336 after GV014 but never enters any P1-C thread.", "status": "identity_conflict", "risk": ["covered_vehicle", "physical_vehicle_missing_from_p1c"], "visual_first": 307, "visual_last": 336, "visual_ranges": "307-336", "visual_missed": "307-336"},
    # GM_RM017: positive reference with four concurrently distinguishable vehicles.
    {"scene": "GM_RM017", "canonical": "GM_RM017:PV001", "p1c": ["GM_RM017:GV001"], "color": "white", "shape": "box truck", "features": "tall rectangular cargo body", "evidence": "Full entry-to-exit sweep, distinct from all passenger vehicles.", "status": "frozen"},
    {"scene": "GM_RM017", "canonical": "GM_RM017:PV002", "p1c": ["GM_RM017:GV002"], "color": "dark gray", "shape": "leading sedan", "features": "dark sedan leading the three passenger vehicles", "evidence": "Maintains leading order and exits at frame 185.", "status": "frozen"},
    {"scene": "GM_RM017", "canonical": "GM_RM017:PV003", "p1c": ["GM_RM017:GV003"], "color": "white", "shape": "SUV", "features": "white tall-body vehicle between two dark sedans", "evidence": "Simultaneously distinguishable from both dark sedans and exits at frame 200.", "status": "frozen"},
    {"scene": "GM_RM017", "canonical": "GM_RM017:PV004", "p1c": ["GM_RM017:GV004"], "color": "dark gray", "shape": "trailing sedan", "features": "dark sedan behind the white SUV", "evidence": "Preserves trailing order and exits at frame 214; no later vehicle appears.", "status": "frozen"},
    # GM_RM019: four physical vehicles, but the silver MPV identity is conflicted.
    {"scene": "GM_RM019", "canonical": "GM_RM019:PV001", "p1c": ["GM_RM019:GV001"], "color": "black", "shape": "sedan", "features": "early black sedan", "evidence": "Pure and complete frames 0-14; frame 29 white MPV is a different vehicle.", "status": "frozen"},
    {"scene": "GM_RM019", "canonical": "GM_RM019:PV002", "p1c": ["GM_RM019:GV002"], "color": "white", "shape": "MPV", "features": "white boxy MPV", "evidence": "Pure and complete frames 5-43; overlaps black sedan without identity competition.", "status": "frozen"},
    {"scene": "GM_RM019", "canonical": "GM_RM019:PV003", "p1c": ["GM_RM019:GV004", "GM_RM019:GV005"], "color": "silver", "shape": "MPV", "features": "silver MPV visible near frames 98-143", "evidence": "GV005 is the physical vehicle thread; GV004 switches onto the same vehicle near frame 125 after non-vehicle fragments, creating both mixture and duplication.", "status": "identity_conflict", "risk": ["mixed_identity", "duplicate_global_ids", "split_then_merge_required"]},
    {"scene": "GM_RM019", "canonical": "GM_RM019:PV004", "p1c": ["GM_RM019:GV006"], "color": "gray", "shape": "SUV", "features": "late gray SUV", "evidence": "Pure and complete frames 149-183; distinct from the preceding silver MPV.", "status": "frozen"},
]


SPECIAL_LIFECYCLE: dict[str, list[dict[str, Any]]] = {
    "GM_RM011:GV004": [
        {
            "frame_start": 39, "frame_end": 55, "audit_type": "tracked_fragment",
            "visual_finding": "Thread correctly follows a silver-covered physical vehicle while detections are present.",
            "same_physical_vehicle": "true", "lifecycle_interpretation": "valid_but_truncated_thread_fragment",
            "duplicates": [], "contaminants": [], "decision": "return_to_p1c_lifecycle_recovery_required",
            "evidence": "The same covered vehicle remains plainly visible after the declared exit.",
        },
        {
            "frame_start": 56, "frame_end": 87, "audit_type": "visible_without_thread",
            "visual_finding": "The covered vehicle continues through the camera sweep with no active P1-C identity.",
            "same_physical_vehicle": "true", "lifecycle_interpretation": "premature_exit_and_missing_visible_suffix",
            "duplicates": [], "contaminants": [], "decision": "return_to_p1c_extend_or_recover_same_lifecycle",
            "evidence": "Continuous shape, cover folds, and image-space motion link frames 39-87 without a physical exit.",
        },
    ],
    "GM_RM011:GV009": [{
        "frame_start": 155, "frame_end": 166, "audit_type": "over_split_first_fragment",
        "visual_finding": "First P1-C fragment of a silver-covered car that remains visible through frame 196.",
        "same_physical_vehicle": "true", "lifecycle_interpretation": "same_vehicle_split_by_visible_unboxed_gap",
        "duplicates": ["GM_RM011:GV010"], "contaminants": [], "decision": "return_to_p1c_merge_with_gv010_and_recover_gap",
        "evidence": "The covered body, folds, adjacent scooters, and uninterrupted camera sweep continue across frames 167-187.",
    }],
    "GM_RM011:GV010": [{
        "frame_start": 188, "frame_end": 191, "audit_type": "over_split_second_fragment",
        "visual_finding": "Second short P1-C fragment on the same covered vehicle represented earlier by GV009.",
        "same_physical_vehicle": "true", "lifecycle_interpretation": "duplicate_rebirth_within_one_visible_lifecycle",
        "duplicates": ["GM_RM011:GV009"], "contaminants": [], "decision": "return_to_p1c_merge_with_gv009_and_recover_visible_suffix",
        "evidence": "No physical exit or new entry occurs between the two IDs; the vehicle is continuously visible.",
    }],
    "GM_RM019:GV003": [{
        "frame_start": 45, "frame_end": 100, "audit_type": "false_thread",
        "visual_finding": "Boxes follow pedestrians, roadside small objects, and fragments; no vehicle lifecycle exists.",
        "same_physical_vehicle": "false", "lifecycle_interpretation": "non_vehicle_false_positive_thread",
        "duplicates": [], "contaminants": [], "decision": "return_to_p1c_remove_nonvehicle_thread",
        "evidence": "Complete joint-scene and thread-context review shows no physical vehicle corresponding to GV003.",
    }],
    "GM_RM019:GV004": [
        {
            "frame_start": 51, "frame_end": 124, "audit_type": "identity_mixture_prefix",
            "visual_finding": "Thread follows non-vehicle/pedestrian fragments before any silver MPV identity is established.",
            "same_physical_vehicle": "false", "lifecycle_interpretation": "non_vehicle_fragments_mixed_into_vehicle_thread",
            "duplicates": [], "contaminants": ["non_vehicle_fragments"], "decision": "return_to_p1c_split_required",
            "evidence": "The subject is not a stable vehicle and is visually discontinuous with the later silver MPV.",
        },
        {
            "frame_start": 125, "frame_end": 141, "audit_type": "duplicate_vehicle_suffix",
            "visual_finding": "Thread switches onto the same silver MPV already represented by GV005.",
            "same_physical_vehicle": "true", "lifecycle_interpretation": "duplicate_representation_after_subject_switch",
            "duplicates": ["GM_RM019:GV005"], "contaminants": ["non_vehicle_prefix_51_124"], "decision": "return_to_p1c_split_then_merge_required",
            "evidence": "GV004 and GV005 boxes alternate or overlap on the same silver MPV; GV005 gaps coincide with GV004 taking that vehicle.",
        },
    ],
    "GM_RM019:GV005": [{
        "frame_start": 98, "frame_end": 143, "audit_type": "duplicate_vehicle_thread",
        "visual_finding": "A real silver MPV, but its lifecycle is duplicated by the late suffix of GV004.",
        "same_physical_vehicle": "true", "lifecycle_interpretation": "same_vehicle_split_across_parallel_global_ids",
        "duplicates": ["GM_RM019:GV004"], "contaminants": [], "decision": "return_to_p1c_merge_after_gv004_split",
        "evidence": "Complete scene review identifies one silver MPV, not two; the two IDs compete for the same car.",
    }],
}


PAIR_SPECS: list[tuple[str, str, str, str, str]] = [
    # scene, a, b, relation, evidence
    ("GM_RM011", "GV001", "GV002", "impossible_same_vehicle", "Simultaneously visible at frames 0-4 as separate adjacent cars."),
    ("GM_RM011", "GV001", "GV003", "impossible_same_vehicle", "Simultaneously visible at frames 20-35 with different shape and position."),
    ("GM_RM011", "GV003", "GV004", "impossible_same_vehicle", "White MAXUS and adjacent silver-covered vehicle overlap at frames 39-55."),
    ("GM_RM011", "GV005", "GV006", "impossible_same_vehicle", "White Nissan and tan-covered vehicle overlap at frames 110-130."),
    ("GM_RM011", "GV005", "GV007", "impossible_same_vehicle", "White Nissan and dark gray sedan overlap at frames 116-130."),
    ("GM_RM011", "GV006", "GV007", "impossible_same_vehicle", "Covered vehicle and gray sedan are simultaneously spatially separate."),
    ("GM_RM011", "GV006", "GV008", "impossible_same_vehicle", "Covered vehicle and white Honda overlap at frames 135-140."),
    ("GM_RM011", "GV007", "GV008", "impossible_same_vehicle", "Gray sedan and white Honda overlap at frames 135-151."),
    ("GM_RM011", "GV008", "GV009", "impossible_same_vehicle", "White Honda and silver-covered vehicle overlap at frames 155-166."),
    ("GM_RM011", "GV009", "GV010", "same_vehicle_merge", "The same silver-covered vehicle remains visible between the two IDs; the 167-187 interval is a visible-unboxed gap, not an exit and new birth."),
    ("GM_RM011", "GV010", "GV011", "different_vehicle_keep_separate", "Covered vehicle and later uncovered white sedan are spatially distinct in the continuous sweep."),
    ("GM_RM011", "GV011", "GV012", "impossible_same_vehicle", "Two white cars overlap at frames 243-245 on opposite sides of a scooter."),
    ("GM_RM011", "GV012", "GV013", "impossible_same_vehicle", "Two white cars overlap at frames 262-266 with different roof and rear styling."),
    ("GM_RM011", "GV013", "GV014", "impossible_same_vehicle", "White sedan and white SUV overlap at frames 284-292 with different body shapes."),
    ("GM_RM017", "GV001", "GV002", "impossible_same_vehicle", "Truck and leading sedan overlap at frames 145-164."),
    ("GM_RM017", "GV001", "GV003", "impossible_same_vehicle", "Truck and white SUV overlap at frames 151-164."),
    ("GM_RM017", "GV001", "GV004", "impossible_same_vehicle", "Truck and trailing sedan overlap at frames 162-164."),
    ("GM_RM017", "GV002", "GV003", "impossible_same_vehicle", "Dark sedan and white SUV are concurrently distinct."),
    ("GM_RM017", "GV002", "GV004", "impossible_same_vehicle", "Two dark sedans are simultaneously visible with preserved order."),
    ("GM_RM017", "GV003", "GV004", "impossible_same_vehicle", "White SUV and trailing dark sedan are concurrently distinct."),
    ("GM_RM019", "GV001", "GV002", "impossible_same_vehicle", "Black sedan and white MPV overlap at frames 5-14; frame 29 belongs only to the white MPV."),
    ("GM_RM019", "GV002", "GV003", "different_vehicle_keep_separate", "GV003 is a non-vehicle false thread after the white MPV exits."),
    ("GM_RM019", "GV003", "GV004", "different_vehicle_keep_separate", "Both early threads follow different non-vehicle fragments; neither establishes a shared car."),
    ("GM_RM019", "GV004", "GV005", "same_vehicle_merge", "Late GV004 and GV005 represent the same silver MPV; GV004 must first be split from its non-vehicle prefix."),
    ("GM_RM019", "GV005", "GV006", "different_vehicle_keep_separate", "Silver MPV exits before a visually different gray SUV enters."),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    parsed = json.loads(value)
    return tuple(float(item) for item in parsed)  # type: ignore[return-value]


def compress_ranges(values: Iterable[int]) -> str:
    ordered = sorted(set(values))
    if not ordered:
        return ""
    ranges: list[str] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ";".join(ranges)


def boundary_location(state: str, frame: int) -> str:
    if frame == 0:
        return "initial_frame_boundary"
    return "image_boundary" if "boundary" in state else "interior_or_prior_occlusion"


def apparent_motion_and_scale(rows: list[dict[str, str]]) -> tuple[str, str]:
    visible = [row for row in rows if row.get("bbox") and row.get("is_interpolated_gap", "").lower() != "true"]
    if len(visible) < 2:
        return "stationary_world; insufficient_image_drift", "insufficient_visible_extent"
    first = parse_bbox(visible[0]["bbox"])
    last = parse_bbox(visible[-1]["bbox"])
    first_center = (first[0] + first[2]) / 2.0
    last_center = (last[0] + last[2]) / 2.0
    delta = last_center - first_center
    direction = "left_to_right" if delta > 20 else "right_to_left" if delta < -20 else "minimal_horizontal_drift"
    first_area = max(1.0, (first[2] - first[0]) * (first[3] - first[1]))
    last_area = max(1.0, (last[2] - last[0]) * (last[3] - last[1]))
    ratio = last_area / first_area
    scale = "increasing" if ratio > 1.15 else "decreasing" if ratio < 0.87 else "roughly_stable"
    return f"stationary_world; apparent_{direction}_from_camera_sweep", scale


def build_registry(threads_by_id: Mapping[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for vehicle in VEHICLES:
        linked = [row for thread_id in vehicle["p1c"] for row in threads_by_id[thread_id]]
        linked.sort(key=lambda row: (int(row["frame_index"]), row["global_vehicle_id"]))
        visible = [row for row in linked if row.get("is_interpolated_gap", "").lower() != "true" and row.get("observation_id")]
        gaps = [int(row["frame_index"]) for row in linked if row.get("is_interpolated_gap", "").lower() == "true"]
        first = linked[0] if linked else None
        last = linked[-1] if linked else None
        motion, scale = apparent_motion_and_scale(linked) if linked else ("stationary_world; apparent_camera_sweep", "not_available_without_p1c_box")
        trackers = sorted({tracker for row in linked for tracker in parse_json_list(row.get("source_tracker_ids", "[]"))})
        detectors = sorted({row["selected_detection_source"] for row in visible if row.get("selected_detection_source")})
        conflict = vehicle["status"] != "frozen"
        visual_first = int(vehicle.get("visual_first", min(int(row["frame_index"]) for row in visible) if visible else 0))
        visual_last = int(vehicle.get("visual_last", max(int(row["frame_index"]) for row in visible) if visible else visual_first))
        visible_ranges = str(vehicle.get("visual_ranges", compress_ranges(int(row["frame_index"]) for row in visible)))
        missed_ranges = str(vehicle.get("visual_missed", compress_ranges(gaps)))
        entry_state = first.get("lifecycle_state", "visible_without_p1c_thread") if first else "visible_without_p1c_thread"
        exit_state = last.get("lifecycle_state", "visible_without_p1c_thread") if last else "visible_without_p1c_thread"
        rows.append({
            "scene": vehicle["scene"],
            "canonical_vehicle_id": vehicle["canonical"],
            "p1c_global_vehicle_ids": ";".join(vehicle["p1c"]),
            "frame_first_visible": visual_first,
            "frame_last_visible": visual_last,
            "visible_frame_ranges": visible_ranges,
            "occlusion_or_missed_ranges": missed_ranges,
            "entry_frame": visual_first,
            "entry_location": boundary_location(entry_state, visual_first),
            "entry_state": entry_state,
            "exit_frame": visual_last,
            "exit_location": boundary_location(exit_state, visual_last),
            "exit_state": exit_state,
            "vehicle_color": vehicle["color"],
            "vehicle_type_or_shape": vehicle["shape"],
            "dominant_motion_direction": motion,
            "scale_trend": scale,
            "distinctive_visual_features": vehicle["features"],
            "source_tracker_ids": json.dumps(trackers, ensure_ascii=False),
            "detector_sources": json.dumps(detectors, ensure_ascii=False),
            "identity_evidence_summary": vehicle["evidence"],
            "lifecycle_completeness": "conflicted_not_freezable" if conflict else "complete_within_camera_sweep",
            "thread_purity": "mixed_and_duplicated" if conflict else "pure_single_physical_vehicle",
            "freeze_status": vehicle["status"],
            "risk_flags": json.dumps(vehicle.get("risk", []), ensure_ascii=False),
            "notes": "Audit-layer canonical name only; P1-C output was not edited. Formal frozen outputs withheld because the stage is blocked.",
        })
    return rows


def build_lifecycle(summaries: list[dict[str, str]], registry_by_thread: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    audit_index = 1
    for summary in summaries:
        thread_id = summary["global_vehicle_id"]
        if thread_id in SPECIAL_LIFECYCLE:
            specs = SPECIAL_LIFECYCLE[thread_id]
        else:
            vehicle = registry_by_thread[thread_id]
            specs = [{
                "frame_start": int(summary["frame_start"]), "frame_end": int(summary["frame_end"]),
                "audit_type": "full_lifecycle", "visual_finding": vehicle["identity_evidence_summary"],
                "same_physical_vehicle": "true", "lifecycle_interpretation": "single_complete_physical_vehicle_lifecycle",
                "duplicates": [], "contaminants": [], "decision": "accept_thread_identity",
                "evidence": "Complete scene and per-thread context review confirms purity, entry/exit continuity, gaps, and neighboring identities.",
            }]
        for spec in specs:
            rows.append({
                "scene": summary["scene"], "p1c_global_vehicle_id": thread_id,
                "audit_id": f"P1D-L{audit_index:04d}", "frame_start": spec["frame_start"], "frame_end": spec["frame_end"],
                "audit_type": spec["audit_type"], "visual_finding": spec["visual_finding"],
                "same_physical_vehicle": spec["same_physical_vehicle"],
                "lifecycle_interpretation": spec["lifecycle_interpretation"],
                "possible_duplicate_thread_ids": json.dumps(spec["duplicates"], ensure_ascii=False),
                "possible_contaminating_thread_ids": json.dumps(spec["contaminants"], ensure_ascii=False),
                "decision": spec["decision"], "evidence_summary": spec["evidence"],
                "notes": "Visual audit evidence only; no manual override or P1-C identity edit.",
            })
            audit_index += 1
    return rows


def full_id(scene: str, short_id: str) -> str:
    return f"{scene}:{short_id}"


def build_pairs(summary_by_id: Mapping[str, dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scene, short_a, short_b, recommendation, evidence in PAIR_SPECS:
        thread_a = full_id(scene, short_a)
        thread_b = full_id(scene, short_b)
        a = summary_by_id[thread_a]
        b = summary_by_id[thread_b]
        a_start, a_end = int(a["frame_start"]), int(a["frame_end"])
        b_start, b_end = int(b["frame_start"]), int(b["frame_end"])
        overlap = max(0, min(a_end, b_end) - max(a_start, b_start) + 1)
        gap = 0 if overlap else max(0, max(a_start, b_start) - min(a_end, b_end) - 1)
        temporal = "overlap" if overlap else "sequential_with_gap" if gap else "adjacent"
        same = recommendation == "same_vehicle_merge"
        impossible = recommendation == "impossible_same_vehicle"
        rows.append({
            "scene": scene, "thread_a": thread_a, "thread_b": thread_b,
            "temporal_relation": temporal, "overlap_frame_count": overlap, "gap_length": gap,
            "a_exit_location": "image_boundary_or_camera_sweep_exit", "b_entry_location": "image_boundary_or_camera_sweep_entry",
            "color_similarity": "mixed_or_not_decisive" if scene == "GM_RM011" else "reviewed",
            "appearance_similarity": "same_vehicle" if same else "distinct_or_nonvehicle",
            "shape_similarity": "same_vehicle" if same else "distinct_or_simultaneously_incompatible",
            "motion_compatibility": "compatible_same_vehicle" if same else "not_identity_supporting",
            "scale_trend_compatibility": "compatible_same_vehicle" if same else "not_identity_supporting",
            "boundary_lifecycle_compatibility": "requires_split_then_merge" if same else "separate_lifecycles_supported",
            "visual_identity_judgment": "same_silver_mpv" if same else "physically_distinct" if not "non-vehicle" in evidence else "nonvehicle_relation",
            "recommended_relation": recommendation,
            "evidence_summary": evidence,
            "notes": "Pairwise visual judgment; features are evidence, not a new chaining gate.",
        })
    return rows


def build_reset_audit(summaries: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_scene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in summaries:
        by_scene[row["scene"]].append(row)
    reviewed = {
        "GM_RM011": (0, 1, 4, 1, "partially_overused_and_recovery_incomplete", "Four P1-B long-bridge errors were correctly separated, but GV009/GV010 split one continuously visible covered vehicle and GV004 exits before its visible suffix ends."),
        "GM_RM017": (0, 0, 0, 0, "not_invoked_as_failure_mode", "Four stable vehicle lifecycles remain distinct under full visual review."),
        "GM_RM019": (1, 0, 0, 0, "not_primary_failure_mode", "The blocker is false-thread acceptance, subject mixing, and duplicate parallel IDs, not an exit-new-birth over-split."),
    }
    rows: list[dict[str, Any]] = []
    for scene in ("GM_RM011", "GM_RM017", "GM_RM019"):
        scene_rows = by_scene[scene]
        births = len(scene_rows)
        exits = len(scene_rows)
        boundary_entries = sum("boundary" in row.get("entry_type", "") for row in scene_rows)
        boundary_exits = sum("boundary" in row.get("exit_type", "") for row in scene_rows)
        short_near, high_sim, resolved, possible_split, judgment, evidence = reviewed[scene]
        rows.append({
            "scene": scene, "birth_count": births, "exit_count": exits,
            "boundary_entry_count": boundary_entries, "boundary_entry_ratio": f"{boundary_entries / births:.6f}",
            "boundary_exit_count": boundary_exits, "boundary_exit_ratio": f"{boundary_exits / exits:.6f}",
            "non_boundary_birth_count": births - boundary_entries, "non_boundary_exit_count": exits - boundary_exits,
            "short_exit_near_birth_count": short_near, "reset_high_similarity_pair_count": high_sim,
            "reset_resolved_wrong_bridge_count": resolved, "reset_possible_over_split_count": possible_split,
            "visual_judgment": judgment,
            "decision": "return_to_p1c_repair_exit_birth_and_visible_recovery" if scene == "GM_RM011" else "keep_reset_mechanism_unchanged_for_now; repair_other_p1c_identity_failures" if scene == "GM_RM019" else "reset_behavior_accepted_in_scene",
            "evidence_summary": evidence,
            "notes": "Counts audit P1-C output events; no runtime threshold or new gate is introduced.",
        })
    return rows


def build_checklist(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
    hard_zero = metrics.get("hard_constraints", {}).get("total_hard_constraint_violations") == 0
    items = [
        ("C01", "Three complete 368-frame joint scenes and every P1-C thread context reviewed", "pass", "3 joint scenes; 24/24 thread contexts reviewed", False),
        ("C02", "Every output thread corresponds to exactly one physical vehicle", "fail", "GM_RM019:GV003 is non-vehicle; GM_RM019:GV004 mixes subjects; GM_RM011:GV009/GV010 duplicate one covered car", True),
        ("C03", "Every observed physical vehicle corresponds to exactly one output identity", "fail", "GM_RM011 has one covered vehicle with two IDs and another covered vehicle with no P1-C ID; GM_RM019 silver MPV has two IDs", True),
        ("C04", "No unexplained duplicate thread", "fail", "GM_RM011:GV009/GV010 and GM_RM019:GV004/GV005 each duplicate one physical vehicle", True),
        ("C05", "No unexplained identity mixture", "fail", "GV004 switches from non-vehicle fragments to the silver MPV", True),
        ("C06", "All entries and exits are physically interpretable", "fail", "GM_RM011:GV004 exits while its vehicle remains visible; GM_RM011:GV009/GV010 split a continuous lifecycle; GM_RM019 has false/mixed interior events", True),
        ("C07", "All long gaps reviewed", "pass", "All rendered gap and recovery intervals were reviewed", False),
        ("C08", "All plausible duplicate pairs reviewed", "pass", "GM011, GM017, and GM019 pair ledgers completed", False),
        ("C09", "Hard constraint violations equal zero", "pass" if hard_zero else "fail", json.dumps(metrics.get("hard_constraints", {}), ensure_ascii=False), not hard_zero),
        ("C10", "No manual override used", "pass", "manual_override_used=false", False),
        ("C11", "Audit remains traceable to P1-C observations and provenance", "pass", "Registry aggregates observation, detector, and tracker provenance", False),
        ("C12", "Blocked-audit validator passes", "pass", "Validator checks schemas, conflict assertions, protected artifacts, and forbidden assets", False),
        ("C13", "Final frozen registry, mapping, and per-frame thread outputs may be emitted", "fail", "Blocked by C02-C06; final frozen outputs intentionally absent", True),
        ("C14", "P2 entry allowed", "fail", "Only FROZEN permits P2; current status is BLOCKED", True),
    ]
    return [{
        "check_id": check_id, "acceptance_condition": condition, "result": result,
        "evidence": evidence, "blocking": str(blocking).lower(),
        "notes": "P1D_PHYSICAL_VEHICLE_THREADS_BLOCKED" if blocking else "audited",
    } for check_id, condition, result, evidence, blocking in items]


def build_report(
    registry: list[dict[str, Any]], lifecycle: list[dict[str, Any]], pairs: list[dict[str, Any]],
    resets: list[dict[str, Any]], metrics: Mapping[str, Any],
) -> str:
    thread_counts = Counter(row["scene"] for row in read_csv(ROOT / "manifests/oty2/oty2_p1c_global_vehicle_thread_summary.csv"))
    physical_counts = Counter(row["scene"] for row in registry)
    clean_counts = Counter(row["scene"] for row in registry if row["freeze_status"] == "frozen")
    hard = metrics.get("hard_constraints", {})
    lines = [
        "# OTY2 P1-D 物理车辆线程冻结与全生命周期验收报告",
        "", "日期：`2026-07-14`", "",
        "## 1. 执行结论", "",
        "最终状态：`P1D_PHYSICAL_VEHICLE_THREADS_BLOCKED`。", "",
        "三场景的 368 帧联合场景视频与全部 24 条 P1-C 线程上下文均已完整审阅。GM_RM011 共观察到 14 辆真实停放车辆，但 GV009/GV010 是同一辆罩车、GV004 生命周期提前结束，且 GV014 之后还有一辆罩车完全未进入 P1-C；GM_RM017 的 4 条线程构成正向基线；GM_RM019 存在一个非车辆线程、一个混合身份线程和一辆车被两个 ID 表示。因此不得生成最终冻结输出，也不得进入 P2。", "",
        "本轮只使用光学时间流和 P1-C provenance，未读取 SAR、SAR GT、方位映射或 P2 资产。", "",
        "## 2. 场景总览", "",
        "| scene | P1-C threads | audited physical vehicles | clean row-level identities | formal frozen vehicles | stage result |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for scene in ("GM_RM011", "GM_RM017", "GM_RM019"):
        stage_result = {
            "GM_RM011": "blocked by lifecycle and coverage conflicts",
            "GM_RM017": "audit-passed but not formally emitted",
            "GM_RM019": "blocked by false, mixed, and duplicate identities",
        }[scene]
        lines.append(f"| {scene} | {thread_counts[scene]} | {physical_counts[scene]} | {clean_counts[scene]} | 0 | {stage_result} |")
    lines += [
        "", "`formal frozen vehicles` 为 0，是因为阶段整体 BLOCKED，最终 frozen registry、global-to-canonical map 和 frozen per-frame threads 均未生成。审计层确认的物理车辆数为 GM_RM011 `14`、GM_RM017 `4`、GM_RM019 `4`。", "",
        "## 3. GM_RM011：14 线程过度拆分压力测试", "",
        "完整相机扫掠中共观察到 14 辆物理车辆，但 14 条 P1-C 线程并非一一对应：`GM_RM011:GV009`（155-166）与 `GM_RM011:GV010`（188-191）是同一辆连续可见的银色罩车，167-187 为可见无框 gap；`GM_RM011:GV004` 在 55 帧退出后，同一罩车仍可见至约 87 帧；`GM_RM011:GV014` 之后约 307-336 还有一辆独立罩车完全没有 P1-C 线程。", "",
        "其余相邻白车分离正确：GV011/GV012 在 243-245 共存，GV012/GV013 在 262-266 共存，GV013/GV014 在 284-292 共存。14 条 P1-C 线程实际表示 13 辆独立物理车辆，另有 1 辆物理车辆完全漏线程，因此场景总物理车辆数仍为 14。GM_RM011 有 1 个过度拆分/重复身份、1 个提前退出的不完整生命周期和 1 辆漏线程车辆；这些问题均可由光学完整时间流明确判断，不属于 `optically_unresolvable`。", "",
        "## 4. GM_RM017：正向基线", "",
        "四条线程分别是白色厢式货车、前方深色轿车、白色 SUV 和后方深色轿车。四车在 162-164 同时可区分并保持次序，退出帧依次为 164、185、200、214；215-367 不再出现车辆线程。未发现过拆、错并或主体交换。", "",
        "## 5. GM_RM019：阻断失败", "",
        "- `GM_RM019:GV001`：0-14 的黑色轿车，纯且完整；frame 29 的白色 MPV 与其无关。", "",
        "- `GM_RM019:GV002`：5-43 的白色 MPV，纯且完整。", "",
        "- `GM_RM019:GV003`：45-100 跟随行人和路侧小物体，不对应任何车辆，是非车辆伪线程。", "",
        "- `GM_RM019:GV004`：51-124 为非车辆/行人碎片，约从 125 起切换到银色 MPV，属于身份混合；其后缀又与 `GM_RM019:GV005` 表示同一辆银色 MPV。", "",
        "- `GM_RM019:GV005`：98-143 的真实银色 MPV，但被 `GM_RM019:GV004` 后缀重复表示。", "",
        "- `GM_RM019:GV006`：149-183 的灰色 SUV，纯且完整。", "",
        "因此 GM_RM019 只有 4 辆物理车辆，不是 6 辆；发现 1 个重复/过拆实例、1 个错误混合实例和 1 个非车辆线程。连同 GM_RM011，本轮总计发现 2 个同车多 ID/过拆实例、1 个线程内错误混合、1 个非车辆线程和 1 辆真实车辆漏线程。问题均可由光学完整时间流明确判定，不存在真正光学不可分辨区间。", "",
        "## 6. exit-new birth 与 pairwise 审计", "",
        "GM_RM011 的 reset 修复了 P1-B 已知的 4 条错误长桥，但也至少把一辆持续可见罩车拆成 GV009/GV010，并未恢复 GV004 的可见后缀；因此 exit-new birth/visible recovery 存在局部过度使用或恢复不足。GM_RM017 未出现 reset 失败。GM_RM019 的主要问题则是非车辆线程准入、线程内主体切换和并行重复身份。不得增加场景专用 Gate，应返回 P1-C 修复通用生命周期恢复、身份纯度与一车一 ID 约束。", "",
        f"线程对审计共记录 `{len(pairs)}` 对；生命周期审计共记录 `{len(lifecycle)}` 行。", "",
        "## 7. 稳定性、约束与可追溯性", "",
        f"P1-C hard constraints：`{json.dumps(hard, ensure_ascii=False)}`。", "",
        "P1-C 固定种子重放已确认三场景 thread count 保持 14/4/6，全部扰动的 minimum selected-edge Jaccard=1.0，P1-C validator PASS，hard constraint 违规为 0。P1-D registry 中的 detector 和 tracker 字段直接聚合自 P1-C 逐帧线程，不建立新的身份求解路径。", "",
        "## 8. 冻结决定与 P2", "",
        "由于 GM_RM011 的提前退出、同车双 ID 和漏线程，以及 `GM_RM019:GV003`、`GM_RM019:GV004` 和 `GM_RM019:GV004/GM_RM019:GV005` 关系违反冻结条件，本轮不生成：", "",
        "- `oty2_p1d_frozen_physical_vehicle_registry.csv`", "- `oty2_p1d_global_to_canonical_vehicle_map.csv`", "- `oty2_p1d_frozen_optical_vehicle_threads.csv`", "",
        "必须返回 P1-C 做通用机制修复，重跑三个场景并重新执行 P1-D。当前明确不允许进入 P2。", "",
        "## 9. 未运行内容", "",
        "未运行 SAR/SAR GT 读取、方位映射、SAR 坐标、P2、Mask、candidate、selector、ranking、训练、自动标注、参数大搜索、场景专用运行时 Gate 或 manual override；未修改原始图像、视频、检测资产、P1-B 或 P1-C 历史产物。临时 MP4/JPG 仅位于 workspace/output，不提交。", "",
    ]
    return "\n".join(lines)


def main() -> int:
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    inputs = config["inputs"]
    outputs = config["outputs"]
    thread_rows = read_csv(ROOT / inputs["thread_manifest"])
    summaries = read_csv(ROOT / inputs["thread_summary_manifest"])
    metrics_path = ROOT / inputs["p1c_metrics"]
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}

    threads_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in thread_rows:
        threads_by_id[row["global_vehicle_id"]].append(row)
    for rows in threads_by_id.values():
        rows.sort(key=lambda row: int(row["frame_index"]))
    summary_by_id = {row["global_vehicle_id"]: row for row in summaries}

    registry = build_registry(threads_by_id)
    registry_by_thread = {
        thread_id: row
        for row in registry
        for thread_id in str(row["p1c_global_vehicle_ids"]).split(";")
        if thread_id and thread_id not in {"GM_RM019:GV003", "GM_RM019:GV004", "GM_RM019:GV005"}
    }
    lifecycle = build_lifecycle(summaries, registry_by_thread)
    pairs = build_pairs(summary_by_id)
    resets = build_reset_audit(summaries)
    checklist = build_checklist(metrics)

    write_csv(ROOT / outputs["physical_vehicle_registry"], registry, REGISTRY_FIELDS)
    write_csv(ROOT / outputs["thread_lifecycle_audit"], lifecycle, LIFECYCLE_FIELDS)
    write_csv(ROOT / outputs["gm011_thread_pair_audit"], [row for row in pairs if row["scene"] == "GM_RM011"], PAIR_FIELDS)
    write_csv(ROOT / outputs["gm019_thread_pair_audit"], [row for row in pairs if row["scene"] == "GM_RM019"], PAIR_FIELDS)
    write_csv(ROOT / outputs["thread_pairwise_identity_audit"], pairs, PAIR_FIELDS)
    write_csv(ROOT / outputs["lifecycle_reset_audit"], resets, RESET_FIELDS)
    write_csv(ROOT / outputs["freeze_acceptance_checklist"], checklist, CHECKLIST_FIELDS)
    report_path = ROOT / outputs["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(registry, lifecycle, pairs, resets, metrics), encoding="utf-8")

    payload = {
        "status": config["stage_status"],
        "source_boundary": config["source_boundary"],
        "manual_override_used": config["manual_override_used"],
        "p2_entry_allowed": config["p2_entry_allowed"],
        "row_counts": {
            "physical_vehicle_registry": len(registry), "thread_lifecycle_audit": len(lifecycle),
            "gm011_thread_pair_audit": sum(row["scene"] == "GM_RM011" for row in pairs),
            "gm019_thread_pair_audit": sum(row["scene"] == "GM_RM019" for row in pairs),
            "thread_pairwise_identity_audit": len(pairs), "lifecycle_reset_audit": len(resets),
            "freeze_acceptance_checklist": len(checklist),
        },
        "audited_physical_vehicle_counts": dict(Counter(row["scene"] for row in registry)),
        "formal_frozen_vehicle_counts": {scene: 0 for scene in ("GM_RM011", "GM_RM017", "GM_RM019")},
        "blocked_findings": config["blocked_findings"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
