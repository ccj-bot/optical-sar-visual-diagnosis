#!/usr/bin/env python3
"""Materialize the optical-only P1-E canonical identity benchmark.

The output is a research reference.  It never edits or replaces P1-C runtime
predictions and it does not read SAR, SAR GT, mapping, or P2 assets.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/oty2/oty2_p1e_optical_identity_benchmark.yaml"
SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")
FRAME_COUNT = 368
IMAGE_W, IMAGE_H = 800, 600

REGISTRY_FIELDS = [
    "scene", "canonical_vehicle_id", "frame_first_visible", "frame_last_visible",
    "visible_frame_ranges", "partial_visibility_ranges", "full_occlusion_ranges",
    "visible_but_unboxed_ranges", "entry_frame", "entry_location", "entry_direction",
    "exit_frame", "exit_location", "exit_direction", "vehicle_color", "vehicle_type_or_shape",
    "dominant_motion_direction", "scale_trend", "distinctive_visual_features",
    "occluding_vehicle_ids", "p1c_global_vehicle_ids", "source_tracker_ids",
    "identity_evidence_summary", "benchmark_confidence", "notes",
]
FRAME_FIELDS = [
    "scene", "canonical_vehicle_id", "frame_index", "lifecycle_state", "visibility_state",
    "is_vehicle_in_scene", "is_vehicle_visible", "is_full_vehicle_visible", "is_partially_visible",
    "is_fully_occluded", "is_visible_but_unboxed", "occlusion_source", "entry_or_exit_state",
    "reference_bbox_available", "reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2",
    "reference_bbox_y2", "reference_bbox_origin", "reference_subject_description",
    "benchmark_evidence", "notes",
]
DETECTION_FIELDS = [
    "scene", "frame_index", "detector_source", "source_detection_id", "bbox", "confidence",
    "assigned_canonical_vehicle_id", "assignment_status", "observation_role", "vehicle_completeness",
    "subject_purity", "overlapping_vehicle_ids", "p1c_observation_id", "source_tracker_ids",
    "benchmark_evidence", "notes",
]
FAILURE_FIELDS = [
    "scene", "failure_id", "canonical_vehicle_id", "frame_start", "frame_end", "failure_type",
    "detector_sources", "tracker_ids", "p1c_global_vehicle_ids", "visual_ground_truth",
    "current_observation_behavior", "identity_consequence", "root_cause_layer",
    "recommended_future_mechanism", "severity", "notes",
]
FRAGMENT_FIELDS = [
    "scene", "atomic_tracklet_id", "frame_start", "frame_end", "frame_count",
    "assigned_canonical_vehicle_ids", "p1c_global_vehicle_ids", "source_track_ids",
    "detector_sources", "split_reason", "primary_fragmentation_cause", "secondary_causes",
    "identity_purity_necessity", "benchmark_evidence", "recommended_future_mechanism", "notes",
]
ROLE_FIELDS = [
    "scene", "canonical_vehicle_id", "benchmark_role", "role_reason", "permitted_use",
    "prohibited_use", "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def bbox_from_json(value: str) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    data = json.loads(value)
    return tuple(float(v) for v in data) if data else None


def bbox_from_detection(row: dict[str, str]) -> tuple[float, float, float, float]:
    return tuple(float(row[key]) for key in ("bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2"))


def bbox_json(box: tuple[float, float, float, float] | None) -> str:
    return json.dumps([round(v, 3) for v in box], separators=(",", ":")) if box else ""


def area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def intersection(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    return max(0.0, min(box_a[2], box_b[2]) - max(box_a[0], box_b[0])) * max(0.0, min(box_a[3], box_b[3]) - max(box_a[1], box_b[1]))


def iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    inter = intersection(box_a, box_b)
    return inter / max(1.0, area(box_a) + area(box_b) - inter)


def iom(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    return intersection(box_a, box_b) / max(1.0, min(area(box_a), area(box_b)))


def center_inside(box: tuple[float, float, float, float], ref: tuple[float, float, float, float]) -> bool:
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    return ref[0] <= cx <= ref[2] and ref[1] <= cy <= ref[3]


def touches_border(box: tuple[float, float, float, float], margin: float = 4.0) -> bool:
    return box[0] <= margin or box[1] <= margin or box[2] >= IMAGE_W - margin or box[3] >= IMAGE_H - margin


def parse_ranges(value: str) -> set[int]:
    frames: set[int] = set()
    for token in str(value or "").split(";"):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start, end = (int(part) for part in token.split("-", 1))
            frames.update(range(start, end + 1))
        else:
            frames.add(int(token))
    return frames


def ranges_text(frames: Iterable[int]) -> str:
    values = sorted(set(int(frame) for frame in frames))
    if not values:
        return ""
    groups: list[str] = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            groups.append(str(start) if start == previous else f"{start}-{previous}")
            start = value
        previous = value
    groups.append(str(start) if start == previous else f"{start}-{previous}")
    return ";".join(groups)


def split_list(value: str) -> list[str]:
    value = str(value or "").strip()
    if not value:
        return []
    if value.startswith("["):
        return [str(item) for item in json.loads(value)]
    return [item for item in value.split(";") if item]


def interpolate_keyframes(keyframes: dict[int, tuple[float, float, float, float]], frame: int) -> tuple[float, float, float, float] | None:
    if not keyframes:
        return None
    if frame in keyframes:
        return keyframes[frame]
    keys = sorted(keyframes)
    before = max((key for key in keys if key < frame), default=None)
    after = min((key for key in keys if key > frame), default=None)
    if before is None:
        return keyframes[after] if after is not None else None
    if after is None:
        return keyframes[before]
    ratio = (frame - before) / (after - before)
    return tuple(keyframes[before][i] + ratio * (keyframes[after][i] - keyframes[before][i]) for i in range(4))


def sha256_rows(rows: Iterable[dict[str, Any]], fields: list[str]) -> str:
    payload = "\n".join("|".join(str(row.get(field, "")) for field in fields) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def global_to_canonical(global_id: str, frame: int, registry: dict[str, dict[str, Any]]) -> str:
    if global_id == "GM_RM019:GV003":
        return ""
    if global_id == "GM_RM019:GV004" and frame < 125:
        return ""
    for canonical, spec in registry.items():
        if global_id in spec["p1c_ids"]:
            return canonical
    return ""


def failure_row(scene: str, index: int, canonical: str, start: int, end: int, failure_type: str,
                detectors: str, trackers: str, globals_: str, visual: str, behavior: str,
                consequence: str, root: str, mechanism: str, severity: str, notes: str = "") -> dict[str, Any]:
    return {
        "scene": scene, "failure_id": f"{scene}:P1E_F{index:04d}", "canonical_vehicle_id": canonical,
        "frame_start": start, "frame_end": end, "failure_type": failure_type,
        "detector_sources": detectors, "tracker_ids": trackers, "p1c_global_vehicle_ids": globals_,
        "visual_ground_truth": visual, "current_observation_behavior": behavior,
        "identity_consequence": consequence, "root_cause_layer": root,
        "recommended_future_mechanism": mechanism, "severity": severity, "notes": notes,
    }


def main() -> int:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    p1d_rows = read_csv(ROOT / config["inputs"]["p1d_registry"])
    thread_rows = read_csv(ROOT / config["inputs"]["p1c_threads"])
    atomic_rows = read_csv(ROOT / config["inputs"]["p1c_atomic_tracklets"])
    active_observations = read_csv(ROOT / config["inputs"]["p1c_observations"])

    registry: dict[str, dict[str, Any]] = {}
    for row in p1d_rows:
        canonical = row["canonical_vehicle_id"]
        override = config.get("canonical_overrides", {}).get(canonical, {})
        first = int(override.get("frame_first_visible", row["frame_first_visible"]))
        last = int(override.get("frame_last_visible", row["frame_last_visible"]))
        registry[canonical] = {
            "row": row, "scene": row["scene"], "first": first, "last": last,
            "visible_frames": set(range(first, last + 1)),
            "p1c_ids": split_list(row.get("p1c_global_vehicle_ids", "")),
            "evidence": override.get("identity_evidence_summary", row["identity_evidence_summary"]),
        }

    active_by_key = {(row["scene"], row["detector_source"], row["source_detection_id"]): row for row in active_observations}
    selected_by_observation: dict[str, dict[str, str]] = {}
    thread_by_atomic: dict[str, list[dict[str, str]]] = defaultdict(list)
    anchor_candidates: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in thread_rows:
        thread_by_atomic[row["atomic_tracklet_id"]].append(row)
        if truth(row["is_interpolated_gap"]) or not row.get("bbox"):
            continue
        canonical = global_to_canonical(row["global_vehicle_id"], int(row["frame_index"]), registry)
        if not canonical:
            continue
        selected_by_observation[row["observation_id"]] = row
        anchor_candidates[(canonical, int(row["frame_index"]))].append({
            "bbox": bbox_from_json(row["bbox"]), "source": row["selected_detection_source"],
            "observation_id": row["observation_id"], "global_id": row["global_vehicle_id"],
        })

    manual: dict[str, dict[int, tuple[float, float, float, float]]] = {}
    for canonical, values in config.get("direct_reference_keyframes", {}).items():
        manual[canonical] = {int(frame): tuple(float(v) for v in box) for frame, box in values.items()}

    anchors: dict[tuple[str, int], dict[str, Any]] = {}
    for key, candidates in anchor_candidates.items():
        candidates.sort(key=lambda item: (item["global_id"] == "GM_RM019:GV005", item["source"] == "YOLO26l"), reverse=True)
        anchors[key] = candidates[0]

    def predicted_box(canonical: str, frame: int) -> tuple[float, float, float, float] | None:
        if (canonical, frame) in anchors:
            return anchors[(canonical, frame)]["bbox"]
        if canonical in manual and min(manual[canonical]) <= frame <= max(manual[canonical]):
            return interpolate_keyframes(manual[canonical], frame)
        keys = sorted(key_frame for (key_canonical, key_frame) in anchors if key_canonical == canonical)
        before = max((key for key in keys if key < frame), default=None)
        after = min((key for key in keys if key > frame), default=None)
        if before is not None and after is not None:
            return interpolate_keyframes({before: anchors[(canonical, before)]["bbox"], after: anchors[(canonical, after)]["bbox"]}, frame)
        return None

    detections: list[dict[str, Any]] = []
    detection_rows_by_frame: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for scene in SCENES:
        for source, path_value in config["inputs"]["normalized_detection_tables"][scene].items():
            for row in read_csv(Path(path_value)):
                frame = int(row["optical_frame_num"])
                detection_id = row["det_id"]
                active = active_by_key.get((scene, source, detection_id), {})
                item = {
                    "scene": scene, "frame": frame, "source": source, "id": detection_id,
                    "bbox_value": bbox_from_detection(row), "confidence_value": float(row["confidence"]),
                    "active": truth(row.get("active_for_tracking", "false")),
                    "tracker_ids": split_list(active.get("existing_tracker_ids", "")),
                    "normalization_action": row.get("normalization_action", ""),
                    "suppression_reason": row.get("suppression_reason", ""),
                }
                detections.append(item)
                detection_rows_by_frame[(scene, frame)].append(item)

    visible_specs_by_frame: dict[tuple[str, int], list[str]] = defaultdict(list)
    for canonical, spec in registry.items():
        for frame in spec["visible_frames"]:
            visible_specs_by_frame[(spec["scene"], frame)].append(canonical)

    for item in detections:
        p1c_key = f"{item['scene']}:{item['source']}:{item['id']}"
        selected_row = selected_by_observation.get(p1c_key)
        forced_canonical = ""
        if selected_row:
            forced_canonical = global_to_canonical(
                selected_row["global_vehicle_id"], int(selected_row["frame_index"]), registry
            )
        candidates: list[tuple[float, str, float, float]] = []
        for canonical in visible_specs_by_frame[(item["scene"], item["frame"])]:
            ref = predicted_box(canonical, item["frame"])
            if ref is None:
                continue
            overlap_iou = iou(item["bbox_value"], ref)
            overlap_iom = iom(item["bbox_value"], ref)
            score = max(overlap_iou, 0.82 * overlap_iom, 0.45 if center_inside(item["bbox_value"], ref) and overlap_iom > 0.25 else 0.0)
            if score >= 0.16:
                candidates.append((score, canonical, overlap_iou, overlap_iom))
        candidates.sort(reverse=True)
        if forced_canonical:
            ref = predicted_box(forced_canonical, item["frame"])
            item["assigned"] = forced_canonical
            item["match_iou"] = iou(item["bbox_value"], ref) if ref else 1.0
            item["match_iom"] = iom(item["bbox_value"], ref) if ref else 1.0
            item["overlapping"] = [forced_canonical]
            item["mixed"] = False
        else:
            item["assigned"] = candidates[0][1] if candidates else ""
            item["match_iou"] = candidates[0][2] if candidates else 0.0
            item["match_iom"] = candidates[0][3] if candidates else 0.0
            item["overlapping"] = [canonical for score, canonical, _iou, _iom in candidates if score >= 0.45]
            item["mixed"] = len(item["overlapping"]) > 1

    assigned_by_vehicle_frame: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for item in detections:
        if item["assigned"]:
            assigned_by_vehicle_frame[(item["assigned"], item["frame"])].append(item)

    preferred: dict[tuple[str, int], dict[str, Any]] = {}
    for key, rows in assigned_by_vehicle_frame.items():
        canonical, frame = key
        ref = predicted_box(canonical, frame)
        for item in rows:
            coverage = intersection(item["bbox_value"], ref) / max(1.0, area(ref)) if ref else 0.0
            item["coverage"] = coverage
            item["complete"] = coverage >= 0.72 or item["match_iom"] >= 0.86
        rows.sort(key=lambda item: (
            not item["mixed"], item["complete"], item["active"], item["source"] == "YOLO26l",
            item["match_iom"], item["confidence_value"],
        ), reverse=True)
        preferred[key] = rows[0]

    detection_output: list[dict[str, Any]] = []
    detection_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in sorted(detections, key=lambda row: (row["scene"], row["frame"], row["source"], row["id"])):
        canonical = item["assigned"]
        selected = preferred.get((canonical, item["frame"])) is item if canonical else False
        if not canonical:
            status, role, completeness, purity = "non_vehicle", "exclude_from_vehicle_identity", "not_vehicle", "non_vehicle"
            evidence = "No overlap with any visually confirmed canonical vehicle in this frame; retained as a detector false-positive reference."
        elif item["mixed"]:
            status, role, completeness, purity = "mixed_subject_observation", "diagnostic_only", "mixed_or_overwide", "mixed_subjects"
            evidence = f"Detection overlaps multiple canonical subjects: {';'.join(item['overlapping'])}."
        elif not item.get("complete", False):
            status = "partial_vehicle_observation"
            role = "preferred_subject_observation" if selected else "usable_auxiliary_observation"
            completeness, purity = "partial_visible_subject", "single_vehicle"
            evidence = "Detection matches one canonical vehicle but covers only a partial visible subject region."
        elif selected:
            status, role, completeness, purity = "correct_vehicle_observation", "preferred_subject_observation", "complete_visible_subject", "single_vehicle"
            evidence = "Highest-quality provenance-preserving observation for this canonical vehicle and frame."
        else:
            status, role, completeness, purity = "duplicate_observation_same_vehicle", "usable_auxiliary_observation", "complete_visible_subject", "single_vehicle"
            evidence = "Additional same-frame observation of the same canonical vehicle; preserved but not preferred."
        p1c_id = f"{item['scene']}:{item['source']}:{item['id']}"
        p1c_row = selected_by_observation.get(p1c_id)
        output = {
            "scene": item["scene"], "frame_index": item["frame"], "detector_source": item["source"],
            "source_detection_id": item["id"], "bbox": bbox_json(item["bbox_value"]),
            "confidence": f"{item['confidence_value']:.6f}", "assigned_canonical_vehicle_id": canonical,
            "assignment_status": status, "observation_role": role, "vehicle_completeness": completeness,
            "subject_purity": purity, "overlapping_vehicle_ids": ";".join(item["overlapping"]),
            "p1c_observation_id": p1c_id if p1c_row else "", "source_tracker_ids": ";".join(sorted(item["tracker_ids"])),
            "benchmark_evidence": evidence,
            "notes": f"normalization_action={item['normalization_action']};suppression_reason={item['suppression_reason']};benchmark_only=true",
        }
        detection_output.append(output)
        detection_lookup[(item["scene"], item["source"], item["id"])] = output

    frame_output: list[dict[str, Any]] = []
    frame_lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for canonical in sorted(registry):
        spec = registry[canonical]
        row = spec["row"]
        subject = f"{row['vehicle_color']} {row['vehicle_type_or_shape']}; {row['distinctive_visual_features']}"
        for frame in range(FRAME_COUNT):
            in_scene = spec["first"] <= frame <= spec["last"]
            box: tuple[float, float, float, float] | None = None
            origin = ""
            visible_but_unboxed = False
            partial = False
            if in_scene:
                chosen = preferred.get((canonical, frame))
                if chosen and not chosen["mixed"]:
                    box = chosen["bbox_value"]
                    origin = "existing_yolo26l_detection" if chosen["source"] == "YOLO26l" else "existing_yolo11l_detection"
                else:
                    box = predicted_box(canonical, frame)
                    origin = "direct_visual_reference" if box else "not_available"
                    visible_but_unboxed = True
                partial = bool(box and touches_border(box))
            if frame < spec["first"]:
                lifecycle = "outside_before_entry"
            elif frame > spec["last"]:
                lifecycle = "outside_after_exit"
            elif visible_but_unboxed:
                lifecycle = "visible_but_unboxed"
            elif frame == spec["first"]:
                lifecycle = "entering"
            elif frame == spec["last"]:
                lifecycle = "exiting"
            else:
                lifecycle = "active_visible"
            visibility = "outside" if not in_scene else "visible_but_unboxed" if visible_but_unboxed else "partial_visible" if partial else "full_visible"
            entry_exit = "entry" if frame == spec["first"] else "exit" if frame == spec["last"] else "none"
            output = {
                "scene": spec["scene"], "canonical_vehicle_id": canonical, "frame_index": frame,
                "lifecycle_state": lifecycle, "visibility_state": visibility,
                "is_vehicle_in_scene": str(in_scene).lower(), "is_vehicle_visible": str(in_scene).lower(),
                "is_full_vehicle_visible": str(in_scene and not partial).lower(),
                "is_partially_visible": str(in_scene and partial).lower(), "is_fully_occluded": "false",
                "is_visible_but_unboxed": str(visible_but_unboxed).lower(), "occlusion_source": "none",
                "entry_or_exit_state": entry_exit, "reference_bbox_available": str(box is not None).lower(),
                "reference_bbox_x1": f"{box[0]:.3f}" if box else "", "reference_bbox_y1": f"{box[1]:.3f}" if box else "",
                "reference_bbox_x2": f"{box[2]:.3f}" if box else "", "reference_bbox_y2": f"{box[3]:.3f}" if box else "",
                "reference_bbox_origin": origin if in_scene else "not_applicable_fully_occluded",
                "reference_subject_description": subject if in_scene else "",
                "benchmark_evidence": spec["evidence"] if in_scene else "Outside visually confirmed lifecycle.",
                "notes": "benchmark_only=true;not_runtime_input=true",
            }
            frame_output.append(output)
            frame_lookup[(canonical, frame)] = output

    registry_output: list[dict[str, Any]] = []
    for canonical in sorted(registry):
        spec = registry[canonical]
        source = spec["row"]
        states = [frame_lookup[(canonical, frame)] for frame in range(FRAME_COUNT)]
        visible = [int(row["frame_index"]) for row in states if truth(row["is_vehicle_visible"])]
        partial = [int(row["frame_index"]) for row in states if truth(row["is_partially_visible"])]
        unboxed = [int(row["frame_index"]) for row in states if truth(row["is_visible_but_unboxed"])]
        trackers = sorted({tracker for row in detection_output if row["assigned_canonical_vehicle_id"] == canonical for tracker in row["source_tracker_ids"].split(";") if tracker})
        first_box = tuple(float(frame_lookup[(canonical, spec["first"])][key]) for key in ("reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2"))
        last_box = tuple(float(frame_lookup[(canonical, spec["last"])][key]) for key in ("reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2"))
        entry_location = "left_boundary" if first_box[0] <= 4 else "right_boundary" if first_box[2] >= 796 else "initial_frame_or_interior"
        exit_location = "left_boundary" if last_box[0] <= 4 else "right_boundary" if last_box[2] >= 796 else "interior_or_camera_sweep_end"
        registry_output.append({
            "scene": spec["scene"], "canonical_vehicle_id": canonical,
            "frame_first_visible": spec["first"], "frame_last_visible": spec["last"],
            "visible_frame_ranges": ranges_text(visible), "partial_visibility_ranges": ranges_text(partial),
            "full_occlusion_ranges": "", "visible_but_unboxed_ranges": ranges_text(unboxed),
            "entry_frame": spec["first"], "entry_location": entry_location, "entry_direction": "camera_sweep_reveal_or_scene_entry",
            "exit_frame": spec["last"], "exit_location": exit_location, "exit_direction": "camera_sweep_hide_or_scene_exit",
            "vehicle_color": source["vehicle_color"], "vehicle_type_or_shape": source["vehicle_type_or_shape"],
            "dominant_motion_direction": source["dominant_motion_direction"], "scale_trend": source["scale_trend"],
            "distinctive_visual_features": source["distinctive_visual_features"], "occluding_vehicle_ids": "",
            "p1c_global_vehicle_ids": ";".join(spec["p1c_ids"]), "source_tracker_ids": ";".join(trackers),
            "identity_evidence_summary": spec["evidence"],
            "benchmark_confidence": "confirmed_with_partial_visibility" if partial else "confirmed",
            "notes": "Canonical benchmark identity; not a repaired P1-C runtime prediction.",
        })

    failures: list[dict[str, Any]] = []
    failure_index = 1
    for canonical in sorted(registry):
        spec = registry[canonical]
        unboxed = [frame for frame in range(FRAME_COUNT) if truth(frame_lookup[(canonical, frame)]["is_visible_but_unboxed"])]
        for token in ranges_text(unboxed).split(";") if unboxed else []:
            start, end = (int(v) for v in token.split("-", 1)) if "-" in token else (int(token), int(token))
            failures.append(failure_row(spec["scene"], failure_index, canonical, start, end, "visible_but_no_detection", "YOLO11l;YOLO26l", "", ";".join(spec["p1c_ids"]), "Vehicle remains visually identifiable in the complete optical timeline.", "Neither detector supplies a usable canonical observation.", "Observation gap can fragment or terminate the vehicle identity.", "detector_observation", "Adjacent-frame propagation with vehicle-shape and visibility-state support.", "high" if end - start >= 4 else "medium"))
            failure_index += 1

    status_to_type = {
        "partial_vehicle_observation": "only_partial_vehicle_box",
        "duplicate_observation_same_vehicle": "same_vehicle_multiple_boxes",
        "mixed_subject_observation": "mixed_subject_box",
        "non_vehicle": "non_vehicle_detection",
    }
    grouped_detection_failures: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for row in detection_output:
        failure_type = status_to_type.get(row["assignment_status"])
        if failure_type:
            grouped_detection_failures[(row["scene"], row["assigned_canonical_vehicle_id"], failure_type, row["detector_source"])].append(int(row["frame_index"]))
    for (scene, canonical, failure_type, source), frames in sorted(grouped_detection_failures.items()):
        for token in ranges_text(frames).split(";"):
            start, end = (int(v) for v in token.split("-", 1)) if "-" in token else (int(token), int(token))
            consequence = {
                "only_partial_vehicle_box": "Appearance and shape prototypes are contaminated by truncation.",
                "same_vehicle_multiple_boxes": "Parallel observations can create redundant tracklets or source competition.",
                "mixed_subject_box": "One crop contains competing subjects and can cause identity mixture.",
                "non_vehicle_detection": "Stable false observations can create a false vehicle thread.",
            }[failure_type]
            mechanism = {
                "only_partial_vehicle_box": "Visibility-conditioned prototype admission and part-aware aggregation.",
                "same_vehicle_multiple_boxes": "Same-frame observation grouping with one preferred subject observation.",
                "mixed_subject_box": "Multi-subject purity filtering before tracklet construction.",
                "non_vehicle_detection": "Vehicle-specific multi-frame objectness and background rejection.",
            }[failure_type]
            failures.append(failure_row(scene, failure_index, canonical, start, end, failure_type, source, "", ";".join(registry[canonical]["p1c_ids"]) if canonical else "", "Canonical frame state and full optical context.", f"{source} produced {failure_type} observations.", consequence, "observation_entity", mechanism, "medium" if failure_type != "non_vehicle_detection" else "high"))
            failure_index += 1

    known = [
        ("GM_RM011", "GM_RM011:PV009", 155, 196, "same_vehicle_multiple_global_ids", "GV009 and GV010 split one continuously visible covered vehicle.", "One physical vehicle becomes two global identities.", "lifecycle_recovery", "Longer identity-pure local fragments plus visible-unboxed propagation."),
        ("GM_RM011", "GM_RM011:PV014", 307, 336, "vehicle_missing_from_all_threads", "A covered vehicle is visible but absent from every P1-C thread.", "A real physical vehicle is omitted from runtime identity output.", "observation_admission", "Recover vehicle-supported observations before global identity solving."),
        ("GM_RM011", "GM_RM011:PV004", 56, 87, "occlusion_recovery_failure", "The covered vehicle remains visible after GV004 terminates.", "Premature exit truncates the physical lifecycle.", "lifecycle_recovery", "Visibility-aware continuation across detector gaps."),
        ("GM_RM019", "", 45, 100, "false_vehicle_thread", "GV003 follows pedestrians and roadside objects, not a vehicle.", "A non-vehicle observation chain becomes a global vehicle thread.", "observation_admission", "Vehicle-specific multi-frame subject validation."),
        ("GM_RM019", "GM_RM019:PV003", 51, 143, "different_vehicles_one_global_id", "GV004 changes from non-vehicle fragments to the silver MPV near frame 125.", "A single global ID mixes unrelated subjects.", "subject_purity", "Prototype admission that rejects non-vehicle and subject-switch crops."),
        ("GM_RM019", "GM_RM019:PV003", 98, 143, "same_vehicle_multiple_global_ids", "GV004 suffix and GV005 represent the same silver MPV.", "One physical vehicle is represented twice in parallel.", "same_frame_exclusivity", "Canonical observation grouping before tracklet association."),
    ]
    for scene, canonical, start, end, failure_type, visual, consequence, root, mechanism in known:
        globals_ = ";".join(registry[canonical]["p1c_ids"]) if canonical else "GM_RM019:GV003"
        failures.append(failure_row(scene, failure_index, canonical, start, end, failure_type, "YOLO11l;YOLO26l", "", globals_, visual, visual, consequence, root, mechanism, "critical", "P1-D blocking case closed in the P1-E reference benchmark."))
        failure_index += 1

    atomic_to_globals: dict[str, set[str]] = defaultdict(set)
    atomic_to_canonicals: dict[str, set[str]] = defaultdict(set)
    for atomic_id, rows in thread_by_atomic.items():
        for row in rows:
            atomic_to_globals[atomic_id].add(row["global_vehicle_id"])
            canonical = global_to_canonical(row["global_vehicle_id"], int(row["frame_index"]), registry)
            if canonical:
                atomic_to_canonicals[atomic_id].add(canonical)
    canonical_atomic_counts = Counter(canonical for values in atomic_to_canonicals.values() for canonical in values)
    fragmentation_output: list[dict[str, Any]] = []
    for row in atomic_rows:
        atomic_id = row["atomic_tracklet_id"]
        canonicals = sorted(atomic_to_canonicals.get(atomic_id, set()))
        globals_ = sorted(atomic_to_globals.get(atomic_id, set()))
        reason = row["split_reason"]
        if not canonicals:
            primary = "non_vehicle_contamination"
        elif len(canonicals) > 1 or "subject_switch" in reason:
            primary = "subject_switch_protection"
        elif reason.startswith("frame_gap"):
            primary = "actual_detection_missing"
        elif reason == "local_overlap_fragment_union":
            primary = "same_frame_multiple_box_competition"
        elif reason == "supplement_singleton":
            primary = "detector_source_switch_or_missing_tracker_support"
        elif reason == "tracker_seed_start":
            primary = "tracker_local_break"
        else:
            primary = "local_continuity_only"
        unnecessary = bool(canonicals and all(canonical_atomic_counts[canonical] > 4 for canonical in canonicals) and primary not in {"subject_switch_protection", "non_vehicle_contamination"})
        necessity = "necessary_for_identity_purity" if primary in {"subject_switch_protection", "non_vehicle_contamination"} else "observation_layer_fragmentation_not_intrinsically_required"
        fragmentation_output.append({
            "scene": row["scene"], "atomic_tracklet_id": atomic_id, "frame_start": row["frame_start"],
            "frame_end": row["frame_end"], "frame_count": row["frame_count"],
            "assigned_canonical_vehicle_ids": ";".join(canonicals), "p1c_global_vehicle_ids": ";".join(globals_),
            "source_track_ids": ";".join(split_list(row["source_track_ids"])),
            "detector_sources": ";".join(split_list(row["detector_sources"])), "split_reason": reason,
            "primary_fragmentation_cause": primary,
            "secondary_causes": "over_fragmentation" if unnecessary else "",
            "identity_purity_necessity": necessity,
            "benchmark_evidence": f"Canonical assignment from all selected observations in {atomic_id}; P1-D lifecycle context retained.",
            "recommended_future_mechanism": "Build longer identity-pure multi-frame observation entities before global association.",
            "notes": "Benchmark attribution; not a runtime split rule.",
        })

    role_lookup = {canonical: role for role, values in config["benchmark_roles"].items() for canonical in values}
    role_output: list[dict[str, Any]] = []
    for canonical in sorted(registry):
        role = role_lookup[canonical]
        if role == "heldout_validation":
            reason = "Held out as a complete physical-vehicle lifecycle; no frame from this vehicle may select features or thresholds."
        elif role == "diagnostic_only":
            reason = "Contains a P1-D blocking observation or identity failure and is reserved for mechanism diagnosis."
        else:
            reason = "Representative development lifecycle for observation recovery and multi-frame representation design."
        role_output.append({
            "scene": registry[canonical]["scene"], "canonical_vehicle_id": canonical, "benchmark_role": role,
            "role_reason": reason, "permitted_use": "evaluation_only" if role == "heldout_validation" else "failure_analysis_only" if role == "diagnostic_only" else "mechanism_development",
            "prohibited_use": "feature_or_threshold_selection" if role == "heldout_validation" else "claiming_runtime_accuracy" if role == "diagnostic_only" else "heldout_claims",
            "notes": "All 368 frame-state rows for this vehicle inherit the same role.",
        })

    outputs = config["outputs"]
    write_csv(ROOT / outputs["canonical_registry"], REGISTRY_FIELDS, registry_output)
    write_csv(ROOT / outputs["frame_states"], FRAME_FIELDS, frame_output)
    write_csv(ROOT / outputs["detection_map"], DETECTION_FIELDS, detection_output)
    write_csv(ROOT / outputs["failure_inventory"], FAILURE_FIELDS, failures)
    write_csv(ROOT / outputs["fragmentation_attribution"], FRAGMENT_FIELDS, fragmentation_output)
    write_csv(ROOT / outputs["benchmark_roles"], ROLE_FIELDS, role_output)

    visible_counts = Counter(row["scene"] for row in frame_output if truth(row["is_vehicle_visible"]))
    unboxed_counts = Counter(row["scene"] for row in frame_output if truth(row["is_visible_but_unboxed"]))
    assignment_counts = Counter((row["detector_source"], row["assignment_status"]) for row in detection_output)
    complete_box_rows = sum(
        count for (source, status), count in assignment_counts.items()
        if status in {"correct_vehicle_observation", "duplicate_observation_same_vehicle"}
    )
    partial_box_rows = sum(count for (source, status), count in assignment_counts.items() if status == "partial_vehicle_observation")
    mixed_box_rows = sum(count for (source, status), count in assignment_counts.items() if status == "mixed_subject_observation")
    non_vehicle_rows = sum(count for (source, status), count in assignment_counts.items() if status == "non_vehicle")
    multi_box_competition_frames = {
        (row["scene"], row["assigned_canonical_vehicle_id"], int(row["frame_index"]))
        for row in detection_output if row["assignment_status"] == "duplicate_observation_same_vehicle"
    }
    source_metrics: dict[str, Any] = {}
    for source in ("YOLO26l", "YOLO11l", "P1C_adopted", "YOLO26l+YOLO11l"):
        correct_frames: set[tuple[str, str, int]] = set()
        for row in detection_output:
            if not row["assigned_canonical_vehicle_id"]:
                continue
            if row["assignment_status"] not in {"correct_vehicle_observation", "duplicate_observation_same_vehicle", "partial_vehicle_observation"}:
                continue
            if source == "P1C_adopted" and not row["p1c_observation_id"]:
                continue
            if source not in {"P1C_adopted", "YOLO26l+YOLO11l"} and row["detector_source"] != source:
                continue
            correct_frames.add((row["scene"], row["assigned_canonical_vehicle_id"], int(row["frame_index"])))
        total_visible = sum(visible_counts.values())
        source_metrics[source] = {"correct_visible_vehicle_frames": len(correct_frames), "visible_vehicle_frames": total_visible, "recall": round(len(correct_frames) / max(1, total_visible), 6)}

    report_lines = [
        "# OTY2 P1-E 光学车辆身份基准与观察层缺口闭合审计报告", "", "日期：`2026-07-14`", "",
        "## 1. 执行结论", "", f"阶段状态：`{config['stage_status']}`。", "",
        "本轮建立的是 optical-only 研究基准，不是 P1-C 修复结果，也不允许作为运行时身份输入。未读取 SAR、SAR GT、方位映射或 P2 资产。", "",
        "## 2. Canonical 车辆与逐帧状态", "",
        "| scene | canonical vehicles | frame-state rows | visible vehicle frames | visible-but-unboxed |", "| --- | ---: | ---: | ---: | ---: |",
    ]
    vehicle_counts = Counter(row["scene"] for row in registry_output)
    frame_counts = Counter(row["scene"] for row in frame_output)
    for scene in SCENES:
        report_lines.append(f"| {scene} | {vehicle_counts[scene]} | {frame_counts[scene]} | {visible_counts[scene]} | {unboxed_counts[scene]} |")
    report_lines += ["", "## 3. 检测源可见车辆观察召回", "", "| source | correct visible vehicle frames | visible vehicle frames | recall |", "| --- | ---: | ---: | ---: |"]
    for source, metric in source_metrics.items():
        report_lines.append(f"| {source} | {metric['correct_visible_vehicle_frames']} | {metric['visible_vehicle_frames']} | {metric['recall']:.4f} |")
    report_lines += ["", "## 4. 观察纯度与框状态", ""]
    for (source, status), count in sorted(assignment_counts.items()):
        report_lines.append(f"- `{source}` / `{status}`: `{count}`")
    cause_counts = Counter(row["primary_fragmentation_cause"] for row in fragmentation_output)
    report_lines += ["", "## 5. 原子短轨迹碎片化归因", ""]
    for cause, count in cause_counts.most_common():
        report_lines.append(f"- `{cause}`: `{count}`")
    report_lines += [
        "", "保护身份纯度所必需的切分主要是 subject-switch 与 non-vehicle 排除；其余大量碎片来自检测缺失、无 tracker 补充单例、局部 tracker 断裂和同帧多框竞争，不能再依靠全局权重恢复成稳定主体。", "",
        "## 6. P1-D 阻断案例闭合", "",
        "- GM_RM011 GV009/GV010：同一持续可见罩车被拆为两个 global ID；中间存在可见但无稳定主体观察的区间。",
        "- GM_RM011 PV014：307-336 的罩车没有进入任何 P1-C 线程。",
        "- GM_RM019 GV003：行人和路侧物体的 vehicle-class 误检形成非车辆线程。",
        "- GM_RM019 GV004：非车辆碎片在约 frame 125 切换到银色 MPV，形成线程内主体混合。",
        "- GM_RM019 GV004/GV005：同一银色 MPV 被并行重复表示。", "",
        "## 7. P1-F 设计输入", "",
        "1. 保存多帧颜色分区、车窗/车灯/格栅局部结构、尺度、姿态、边界接触、可见部位和 detector/tracker provenance。",
        "2. 只允许完整、单主体、无遮挡或轻度截断帧进入可靠外观原型。",
        "3. 局部框、混合框、非车辆框和严重边界截断框只能进入诊断，不得污染原型。",
        "4. 车辆专用 ReID 可作为候选，但必须与颜色、结构、姿态和时间一致性联合验证，不能预先认定必然有效。",
        "5. visible-but-unboxed 应通过相邻帧主体传播与显式 visibility state 恢复，不伪造完全遮挡帧 bbox。",
        "6. 先形成较长、身份纯净的局部车辆观察片段，再进入全局一车一 ID 分配。",
        "7. 可复用成熟的多目标跟踪、轨迹片段图、车辆 ReID 和时序特征聚合，但 observation entity、非车辆稳定短轨抑制和 partial/full 主体统一需针对本数据自行设计。", "",
        "## 8. Benchmark roles", "",
    ]
    for role in ("development", "heldout_validation", "diagnostic_only"):
        vehicles = [row["canonical_vehicle_id"] for row in role_output if row["benchmark_role"] == role]
        report_lines.append(f"- `{role}` ({len(vehicles)}): " + ", ".join(vehicles))
    report_lines += [
        "", "## 9. 完整审阅与关键量化结论", "",
        f"完整视觉审阅已完成：`{str(config['visual_review_complete']).lower()}`。三场景各 368 帧，共 1104 帧；联合检查原始光学帧、YOLO26l、YOLO11l、P1-C 线程和 P1-D 上下文。临时 review pages 仅保存在 workspace/output，未进入仓库。", "",
        f"- 可见车辆帧：GM_RM011={visible_counts['GM_RM011']}，GM_RM017={visible_counts['GM_RM017']}，GM_RM019={visible_counts['GM_RM019']}，合计={sum(visible_counts.values())}。",
        f"- visible-but-unboxed：GM_RM011={unboxed_counts['GM_RM011']}，其余场景为 0。",
        f"- 检测观察行：完整主体={complete_box_rows}，局部主体={partial_box_rows}，混合主体={mixed_box_rows}，非车辆={non_vehicle_rows}。",
        f"- 出现同车重复观察的多框竞争帧={len(multi_box_competition_frames)}；重复框保留 provenance，但每帧每车只选一个 preferred observation。", "",
        "GM_RM011 真实车辆漏线程的直接原因是：车辆在完整时间流中可见，但检测器长期无可用主体框或观察未进入 P1-C；PV014 完全缺席，PV004 和 PV009 则在生命周期中存在观察恢复缺口。GM_RM019 虚假线程的直接原因是行人、路侧物体和小型非车辆区域被 vehicle-class 检测并形成稳定短轨。", "",
        "本轮视觉复核另确认 GM_RM011:PV005 在 frame 87 已从左边界局部进入；两路检测均应归属该白色 Nissan，而同帧右边界的 PV004 仍在离场。", "",
        "## 10. 对 P1-F 的明确要求", "",
        "现有 ResNet18 外观表示缺少车辆专用的细粒度颜色分区、车窗/车灯/格栅局部结构、姿态与尺度条件化、可见部位对齐、多帧原型聚合，以及对局部框、混合框和非车辆污染的显式抑制；单帧通用 embedding 不能承担完整身份恢复。", "",
        "可继续复用的资产包括：完整光学时间流、两路 detector 的全部 normalized observations、tracker provenance、P1-C 原子短轨迹与观察节点、P1-D 14/4/4 物理车辆视觉账本。必须由多帧机制恢复的内容包括 visible-but-unboxed、检测 gap 后重现、partial/full 主体统一、主体切换后的纯度保护和长生命周期外观原型。", "",
        "P1-E benchmark 已具备车辆级 development/heldout 划分、完整逐帧状态和失败账本，可支撑 P1-F 机制设计与留出验证；它本身不是运行时输出。", "",
        "## 11. 阶段边界", "",
        f"P1-F entry allowed: `{str(config['p1f_entry_allowed']).lower()}`。P2 entry allowed: `false`。", "",
        "未修改 P1-C ILP、birth/exit 成本、身份边权重或历史 P1-B/P1-C/P1-D 产物；未训练 detector、ReID 或其他网络；未运行候选、Gate、selector、ranking、SAR 标注或 P2。", "",
        "## 12. 固定输入摘要", "",
        f"- registry rows hash: `{sha256_rows(registry_output, REGISTRY_FIELDS)}`",
        f"- frame-state rows hash: `{sha256_rows(frame_output, FRAME_FIELDS)}`",
        f"- detection-map rows hash: `{sha256_rows(detection_output, DETECTION_FIELDS)}`",
    ]
    report_path = ROOT / outputs["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")

    result = {
        "status": config["stage_status"], "source_boundary": config["source_boundary"],
        "canonical_vehicle_counts": dict(vehicle_counts), "frame_state_counts": dict(frame_counts),
        "visible_vehicle_frame_counts": dict(visible_counts), "visible_but_unboxed_counts": dict(unboxed_counts),
        "detection_row_count": len(detection_output), "failure_row_count": len(failures),
        "fragmentation_row_count": len(fragmentation_output), "source_metrics": source_metrics,
        "p1f_entry_allowed": config["p1f_entry_allowed"], "p2_entry_allowed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
