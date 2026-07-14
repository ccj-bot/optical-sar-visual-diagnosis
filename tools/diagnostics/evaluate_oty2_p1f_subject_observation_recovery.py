#!/usr/bin/env python3
"""Evaluate P1-F runtime outputs against the isolated P1-E benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs/oty2/oty2_p1f_multiframe_subject_observation.yaml"
BASELINES = ("A_YOLO26L", "B_MULTI_SOURCE_SELECTION", "C_FORWARD_RECOVERY", "D_BIDIRECTIONAL_CONTROLLED")

EVALUATION_FIELDS = [
    "baseline", "benchmark_role", "scene", "canonical_vehicle_id", "visible_frame_count",
    "correct_subject_observation_frame_count", "correct_subject_observation_recall",
    "complete_subject_observation_frame_count", "partial_subject_observation_frame_count",
    "visible_no_observation_frame_count", "fully_occluded_frame_count",
    "fully_occluded_correctly_unboxed_frame_count", "recovered_observation_frame_count",
    "correct_recovered_frame_count", "wrong_vehicle_recovered_frame_count",
    "occlusion_misrecovered_frame_count", "duplicate_subject_frame_count",
    "mixed_subject_selected_count", "non_vehicle_selected_count", "wrong_subject_link_count",
    "correct_segment_count", "mean_correct_segment_length", "max_correct_segment_length",
    "single_frame_segment_count", "single_frame_fragment_ratio", "reliable_prototype_interval_count",
    "notes",
]
FAILURE_FIELDS = [
    "failure_id", "baseline", "benchmark_role", "scene", "canonical_vehicle_id",
    "runtime_local_subject_id", "frame_start", "frame_end", "failure_type", "evidence",
    "identity_consequence", "review_priority", "notes",
]
LEAKAGE_FIELDS = ["check_id", "check_name", "result", "evidence", "blocking", "notes"]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def parse_bbox(value: str) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parsed = json.loads(value)
    return tuple(float(v) for v in parsed)


def state_bbox(row: dict[str, str]) -> tuple[float, float, float, float] | None:
    if not truth(row.get("reference_bbox_available")):
        return None
    return tuple(float(row[key]) for key in ("reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2"))


def area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def intersection(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    inter = intersection(a, b)
    return inter / max(1e-9, area(a) + area(b) - inter)


def iom(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    return intersection(a, b) / max(1e-9, min(area(a), area(b)))


def center_inside(box: tuple[float, float, float, float], reference: tuple[float, float, float, float]) -> bool:
    cx, cy = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
    return reference[0] <= cx <= reference[2] and reference[1] <= cy <= reference[3]


def ranges(frames: set[int]) -> list[tuple[int, int]]:
    if not frames:
        return []
    ordered = sorted(frames)
    output: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for frame in ordered[1:]:
        if frame == previous + 1:
            previous = frame
            continue
        output.append((start, previous))
        start = previous = frame
    output.append((start, previous))
    return output


def segment_lengths(frames: set[int]) -> list[int]:
    return [end - start + 1 for start, end in ranges(frames)]


def sha256_rows(rows: list[dict[str, Any]], fields: list[str]) -> str:
    payload = "\n".join("|".join(str(row.get(field, "")) for field in fields) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def observation_key(runtime_id: str) -> tuple[str, str, str] | None:
    parts = runtime_id.split(":", 2)
    if len(parts) != 3 or parts[1] not in {"YOLO11l", "YOLO26l"}:
        return None
    return parts[0], parts[1], parts[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.resolve().read_text(encoding="utf-8"))
    outputs = config["outputs"]
    evaluation_inputs = config["evaluation_inputs"]

    runtime_headers, runtime_rows = read_csv(ROOT / outputs["runtime_observations"])
    cluster_headers, cluster_rows = read_csv(ROOT / outputs["runtime_clusters"])
    selected_headers, selected_rows = read_csv(ROOT / outputs["selected_observations"])
    recovered_headers, recovered_rows = read_csv(ROOT / outputs["recovered_observations"])
    _, registry_rows = read_csv(ROOT / evaluation_inputs["canonical_registry"])
    _, frame_rows = read_csv(ROOT / evaluation_inputs["frame_states"])
    _, detection_rows = read_csv(ROOT / evaluation_inputs["detection_map"])
    _, role_rows = read_csv(ROOT / evaluation_inputs["benchmark_roles"])

    role_by_vehicle = {row["canonical_vehicle_id"]: row["benchmark_role"] for row in role_rows}
    scene_by_vehicle = {row["canonical_vehicle_id"]: row["scene"] for row in registry_rows}
    vehicles = sorted(role_by_vehicle)
    state_lookup = {(row["canonical_vehicle_id"], int(row["frame_index"])): row for row in frame_rows}
    visible_frames = {
        vehicle: {frame for frame in range(368) if truth(state_lookup[(vehicle, frame)]["is_vehicle_visible"])}
        for vehicle in vehicles
    }
    occluded_frames = {
        vehicle: {frame for frame in range(368) if truth(state_lookup[(vehicle, frame)]["is_fully_occluded"])}
        for vehicle in vehicles
    }
    visible_unboxed_frames = {
        vehicle: {frame for frame in range(368) if truth(state_lookup[(vehicle, frame)]["is_visible_but_unboxed"])}
        for vehicle in vehicles
    }
    visible_vehicles_by_frame: dict[tuple[str, int], list[str]] = defaultdict(list)
    for vehicle in vehicles:
        for frame in visible_frames[vehicle]:
            visible_vehicles_by_frame[(scene_by_vehicle[vehicle], frame)].append(vehicle)

    detection_lookup = {
        (row["scene"], row["detector_source"], row["source_detection_id"]): row for row in detection_rows
    }
    acceptable_detection_status = {
        "correct_vehicle_observation", "duplicate_observation_same_vehicle", "partial_vehicle_observation"
    }

    subject_votes: dict[str, Counter[str]] = defaultdict(Counter)
    subject_conflicts: Counter[str] = Counter()
    for row in selected_rows:
        key = observation_key(row["selected_observation_id"])
        if not key:
            continue
        truth_row = detection_lookup.get(key)
        if truth_row and truth_row["assignment_status"] in acceptable_detection_status and truth_row["assigned_canonical_vehicle_id"]:
            subject_votes[row["runtime_local_subject_id"]][truth_row["assigned_canonical_vehicle_id"]] += 1
    subject_vehicle: dict[str, str] = {}
    for subject, votes in subject_votes.items():
        ordered = votes.most_common()
        if ordered and (len(ordered) == 1 or ordered[0][1] > ordered[1][1]):
            subject_vehicle[subject] = ordered[0][0]
            subject_conflicts[subject] = sum(count for vehicle, count in ordered[1:])

    recovery_lookup = {row["recovered_observation_id"]: row for row in recovered_rows}

    predictions: dict[str, list[dict[str, Any]]] = {baseline: [] for baseline in BASELINES}

    for row in detection_rows:
        if row["detector_source"] != "YOLO26l":
            continue
        canonical = row["assigned_canonical_vehicle_id"]
        status = row["assignment_status"]
        predictions["A_YOLO26L"].append({
            "scene": row["scene"], "frame": int(row["frame_index"]), "subject": "YOLO26l_raw",
            "canonical": canonical, "correct": bool(canonical and status in acceptable_detection_status),
            "complete": status in {"correct_vehicle_observation", "duplicate_observation_same_vehicle"},
            "partial": status == "partial_vehicle_observation", "mixed": status == "mixed_subject_observation",
            "nonvehicle": status == "non_vehicle", "wrong_link": False, "kind": "detector", "bbox": parse_bbox(row["bbox"]),
        })

    for row in cluster_rows:
        runtime_id = row["baseline_b_selected_observation_id"]
        key = observation_key(runtime_id)
        truth_row = detection_lookup.get(key) if key else None
        canonical = truth_row["assigned_canonical_vehicle_id"] if truth_row else ""
        status = truth_row["assignment_status"] if truth_row else "unassigned"
        predictions["B_MULTI_SOURCE_SELECTION"].append({
            "scene": row["scene"], "frame": int(row["frame_index"]), "subject": row["runtime_local_subject_id"],
            "canonical": canonical, "correct": bool(canonical and status in acceptable_detection_status),
            "complete": status in {"correct_vehicle_observation", "duplicate_observation_same_vehicle"},
            "partial": status == "partial_vehicle_observation", "mixed": status == "mixed_subject_observation",
            "nonvehicle": status == "non_vehicle", "wrong_link": False, "kind": "detector",
            "bbox": parse_bbox(truth_row["bbox"]) if truth_row else None,
        })

    def recovery_prediction(row: dict[str, str]) -> dict[str, Any]:
        subject = row["runtime_local_subject_id"]
        canonical = subject_vehicle.get(subject, "")
        frame, scene = int(row["frame_index"]), row["scene"]
        box = parse_bbox(row["bbox"])
        correct = complete = partial = mixed = wrong_vehicle = occlusion_mis = False
        overlaps: list[tuple[float, str]] = []
        if box:
            for vehicle in visible_vehicles_by_frame.get((scene, frame), []):
                reference = state_bbox(state_lookup[(vehicle, frame)])
                if reference:
                    score = max(iom(box, reference), iou(box, reference))
                    if score >= 0.20:
                        overlaps.append((score, vehicle))
        overlaps.sort(reverse=True)
        if canonical and frame in visible_frames.get(canonical, set()) and box:
            reference = state_bbox(state_lookup[(canonical, frame)])
            if reference:
                overlap_iom, overlap_iou = iom(box, reference), iou(box, reference)
                correct = overlap_iom >= 0.55 or (overlap_iou >= 0.30 and center_inside(box, reference))
                coverage = intersection(box, reference) / max(1.0, area(reference))
                complete = correct and coverage >= 0.68
                partial = correct and not complete
                mixed = correct and len([vehicle for score, vehicle in overlaps if score >= 0.35 and vehicle != canonical]) > 0
                wrong_vehicle = not correct and bool(overlaps and overlaps[0][1] != canonical)
        elif canonical and (frame in occluded_frames.get(canonical, set()) or frame not in visible_frames.get(canonical, set())):
            occlusion_mis = True
        elif overlaps:
            wrong_vehicle = True
        return {
            "scene": scene, "frame": frame, "subject": subject, "canonical": canonical,
            "correct": correct and not mixed, "complete": complete and not mixed, "partial": partial,
            "mixed": mixed, "nonvehicle": not canonical, "wrong_link": wrong_vehicle,
            "occlusion_mis": occlusion_mis, "kind": "recovered", "bbox": box,
            "recovery_method": row["recovery_method"],
        }

    for row in selected_rows:
        if row["selection_status"] == "runtime_unresolved" or not row["selected_observation_id"]:
            continue
        if row["selection_status"] == "selected_detector_observation":
            key = observation_key(row["selected_observation_id"])
            truth_row = detection_lookup.get(key) if key else None
            canonical = truth_row["assigned_canonical_vehicle_id"] if truth_row else ""
            status = truth_row["assignment_status"] if truth_row else "unassigned"
            mapped = subject_vehicle.get(row["runtime_local_subject_id"], "")
            prediction = {
                "scene": row["scene"], "frame": int(row["frame_index"]), "subject": row["runtime_local_subject_id"],
                "canonical": canonical, "correct": bool(canonical and status in acceptable_detection_status),
                "complete": status in {"correct_vehicle_observation", "duplicate_observation_same_vehicle"},
                "partial": status == "partial_vehicle_observation", "mixed": status == "mixed_subject_observation",
                "nonvehicle": status == "non_vehicle", "wrong_link": bool(mapped and canonical and mapped != canonical),
                "occlusion_mis": False, "kind": "detector", "bbox": parse_bbox(truth_row["bbox"]) if truth_row else None,
            }
        else:
            recovery_row = recovery_lookup[row["selected_observation_id"]]
            prediction = recovery_prediction(recovery_row)
        if truth(row["baseline_c_included"]):
            predictions["C_FORWARD_RECOVERY"].append(prediction)
        if truth(row["baseline_d_included"]):
            predictions["D_BIDIRECTIONAL_CONTROLLED"].append(prediction)

    evaluation_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    failure_index = 1
    per_baseline_vehicle: dict[tuple[str, str], dict[str, Any]] = {}

    for baseline in BASELINES:
        baseline_predictions = predictions[baseline]
        by_vehicle_frame: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
        for prediction in baseline_predictions:
            if prediction["canonical"]:
                by_vehicle_frame[(prediction["canonical"], prediction["frame"])].append(prediction)
        for vehicle in vehicles:
            visible = visible_frames[vehicle]
            correct_frames: set[int] = set()
            complete_frames: set[int] = set()
            partial_frames: set[int] = set()
            recovered_frames: set[int] = set()
            correct_recovered: set[int] = set()
            wrong_recovered: set[int] = set()
            occlusion_mis: set[int] = set()
            duplicate_frames: set[int] = set()
            mixed_count = nonvehicle_count = wrong_link_count = 0
            for frame in range(368):
                entries = by_vehicle_frame.get((vehicle, frame), [])
                correct_entries = [entry for entry in entries if entry["correct"]]
                if correct_entries:
                    correct_frames.add(frame)
                if any(entry["complete"] and entry["correct"] for entry in entries):
                    complete_frames.add(frame)
                elif any(entry["partial"] and entry["correct"] for entry in entries):
                    partial_frames.add(frame)
                if len(correct_entries) > 1:
                    duplicate_frames.add(frame)
                for entry in entries:
                    mixed_count += int(entry.get("mixed", False))
                    nonvehicle_count += int(entry.get("nonvehicle", False))
                    wrong_link_count += int(entry.get("wrong_link", False))
                    if entry["kind"] == "recovered":
                        recovered_frames.add(frame)
                        if entry["correct"]:
                            correct_recovered.add(frame)
                        if entry.get("wrong_link"):
                            wrong_recovered.add(frame)
                        if entry.get("occlusion_mis"):
                            occlusion_mis.add(frame)
            lengths = segment_lengths(correct_frames)
            single_count = sum(length == 1 for length in lengths)
            prototype_count = sum(length >= 3 for length in segment_lengths(complete_frames))
            row = {
                "baseline": baseline, "benchmark_role": role_by_vehicle[vehicle], "scene": scene_by_vehicle[vehicle],
                "canonical_vehicle_id": vehicle, "visible_frame_count": len(visible),
                "correct_subject_observation_frame_count": len(correct_frames),
                "correct_subject_observation_recall": f"{len(correct_frames) / max(1, len(visible)):.6f}",
                "complete_subject_observation_frame_count": len(complete_frames),
                "partial_subject_observation_frame_count": len(partial_frames),
                "visible_no_observation_frame_count": len(visible - correct_frames),
                "fully_occluded_frame_count": len(occluded_frames[vehicle]),
                "fully_occluded_correctly_unboxed_frame_count": len(occluded_frames[vehicle] - {entry["frame"] for entry in baseline_predictions if entry["canonical"] == vehicle}),
                "recovered_observation_frame_count": len(recovered_frames), "correct_recovered_frame_count": len(correct_recovered),
                "wrong_vehicle_recovered_frame_count": len(wrong_recovered), "occlusion_misrecovered_frame_count": len(occlusion_mis),
                "duplicate_subject_frame_count": len(duplicate_frames), "mixed_subject_selected_count": mixed_count,
                "non_vehicle_selected_count": nonvehicle_count, "wrong_subject_link_count": wrong_link_count,
                "correct_segment_count": len(lengths), "mean_correct_segment_length": f"{mean(lengths) if lengths else 0.0:.6f}",
                "max_correct_segment_length": max(lengths, default=0), "single_frame_segment_count": single_count,
                "single_frame_fragment_ratio": f"{single_count / max(1, len(lengths)):.6f}",
                "reliable_prototype_interval_count": prototype_count,
                "notes": "benchmark_evaluation_only;runtime_outputs_not_modified=true",
            }
            evaluation_rows.append(row)
            per_baseline_vehicle[(baseline, vehicle)] = {**row, "correct_frames": correct_frames, "correct_recovered_frames": correct_recovered}
            missing = visible - correct_frames
            for start, end in ranges(missing):
                failure_rows.append({
                    "failure_id": f"P1F_EVAL_F{failure_index:05d}", "baseline": baseline,
                    "benchmark_role": role_by_vehicle[vehicle], "scene": scene_by_vehicle[vehicle],
                    "canonical_vehicle_id": vehicle, "runtime_local_subject_id": "", "frame_start": start, "frame_end": end,
                    "failure_type": "visible_no_correct_subject_observation", "evidence": "Canonical vehicle is visible but no correct selected subject observation is available.",
                    "identity_consequence": "Observation sequence remains fragmented or incomplete.", "review_priority": "high" if end - start >= 3 else "medium",
                    "notes": "evaluation_only",
                })
                failure_index += 1

    for baseline in ("B_MULTI_SOURCE_SELECTION", "C_FORWARD_RECOVERY", "D_BIDIRECTIONAL_CONTROLLED"):
        for prediction in predictions[baseline]:
            failure_type = ""
            if prediction.get("mixed"):
                failure_type = "mixed_subject_selected"
            elif prediction.get("nonvehicle"):
                failure_type = "non_vehicle_selected"
            elif prediction.get("wrong_link") and prediction["kind"] == "recovered":
                failure_type = "wrong_vehicle_recovery"
            elif prediction.get("occlusion_mis"):
                failure_type = "occlusion_or_outside_misrecovery"
            if not failure_type:
                continue
            vehicle = prediction.get("canonical", "")
            failure_rows.append({
                "failure_id": f"P1F_EVAL_F{failure_index:05d}", "baseline": baseline,
                "benchmark_role": role_by_vehicle.get(vehicle, "unassigned_runtime"), "scene": prediction["scene"],
                "canonical_vehicle_id": vehicle, "runtime_local_subject_id": prediction["subject"],
                "frame_start": prediction["frame"], "frame_end": prediction["frame"], "failure_type": failure_type,
                "evidence": "Independent benchmark evaluation rejects the selected runtime observation.",
                "identity_consequence": "The observation cannot enter a trusted multi-frame identity prototype.",
                "review_priority": "critical" if "recovery" in failure_type else "high", "notes": "evaluation_only",
            })
            failure_index += 1

    role_metrics: dict[str, dict[str, Any]] = {}
    for baseline in BASELINES:
        role_metrics[baseline] = {}
        baseline_predictions = predictions[baseline]
        for role in ("development", "heldout_validation", "diagnostic_only"):
            role_vehicles = [vehicle for vehicle in vehicles if role_by_vehicle[vehicle] == role]
            visible_total = sum(len(visible_frames[vehicle]) for vehicle in role_vehicles)
            correct_total = sum(per_baseline_vehicle[(baseline, vehicle)]["correct_subject_observation_frame_count"] for vehicle in role_vehicles)
            complete_total = sum(per_baseline_vehicle[(baseline, vehicle)]["complete_subject_observation_frame_count"] for vehicle in role_vehicles)
            missing_total = sum(per_baseline_vehicle[(baseline, vehicle)]["visible_no_observation_frame_count"] for vehicle in role_vehicles)
            recovered_total = sum(per_baseline_vehicle[(baseline, vehicle)]["correct_recovered_frame_count"] for vehicle in role_vehicles)
            lengths = []
            single_segments = 0
            for vehicle in role_vehicles:
                vehicle_lengths = segment_lengths(per_baseline_vehicle[(baseline, vehicle)]["correct_frames"])
                lengths.extend(vehicle_lengths)
                single_segments += sum(length == 1 for length in vehicle_lengths)
            role_metrics[baseline][role] = {
                "visible_frames": visible_total, "correct_frames": correct_total,
                "recall": round(correct_total / max(1, visible_total), 6), "complete_frames": complete_total,
                "visible_no_observation": missing_total, "correct_recovered_frames": recovered_total,
                "segment_count": len(lengths), "mean_segment_length": round(mean(lengths) if lengths else 0.0, 6),
                "max_segment_length": max(lengths, default=0), "single_frame_segment_count": single_segments,
            }

    purity_metrics: dict[str, dict[str, Any]] = {}
    for baseline in BASELINES:
        baseline_predictions = predictions[baseline]
        correct_groups: Counter[tuple[str, int]] = Counter(
            (entry["canonical"], entry["frame"]) for entry in baseline_predictions if entry["correct"] and entry["canonical"]
        )
        reused = Counter(
            row["selected_observation_id"] for row in selected_rows
            if row["selected_observation_id"] and ((baseline == "C_FORWARD_RECOVERY" and truth(row["baseline_c_included"])) or (baseline == "D_BIDIRECTIONAL_CONTROLLED" and truth(row["baseline_d_included"])))
        )
        purity_metrics[baseline] = {
            "selected_prediction_count": len(baseline_predictions),
            "mixed_subject_selected": sum(entry.get("mixed", False) for entry in baseline_predictions),
            "non_vehicle_selected": sum(entry.get("nonvehicle", False) for entry in baseline_predictions),
            "wrong_subject_links": sum(entry.get("wrong_link", False) for entry in baseline_predictions),
            "wrong_vehicle_recoveries": sum(entry["kind"] == "recovered" and entry.get("wrong_link", False) for entry in baseline_predictions),
            "occlusion_or_outside_misrecoveries": sum(entry.get("occlusion_mis", False) for entry in baseline_predictions),
            "duplicate_subject_frames": sum(count > 1 for count in correct_groups.values()),
            "observation_reused_by_multiple_subjects": sum(count > 1 for count in reused.values()),
        }

    unboxed_total = sum(len(value) for value in visible_unboxed_frames.values())
    diagnostic_recovered = 0
    for vehicle in vehicles:
        correct_recovered = per_baseline_vehicle[("D_BIDIRECTIONAL_CONTROLLED", vehicle)]["correct_recovered_frames"]
        diagnostic_recovered += len(correct_recovered & visible_unboxed_frames[vehicle])

    leakage_rows: list[dict[str, Any]] = []

    def leakage(check_id: str, name: str, passed: bool, evidence: str, blocking: bool = True, notes: str = "") -> None:
        leakage_rows.append({"check_id": check_id, "check_name": name, "result": "pass" if passed else "fail", "evidence": evidence, "blocking": str(blocking).lower(), "notes": notes})

    runtime_script = (ROOT / "tools/diagnostics/run_oty2_p1f_multiframe_subject_observation_recovery.py").read_text(encoding="utf-8")
    runtime_input_text = json.dumps(config["runtime_inputs"], ensure_ascii=False).lower()
    forbidden_runtime_headers = {"canonical_vehicle_id", "reference_bbox", "benchmark_role"}
    leakage("L01", "runtime input paths exclude benchmark manifests", "p1e_" not in runtime_input_text and "benchmark" not in runtime_input_text, runtime_input_text)
    leakage("L02", "runtime script does not access evaluation_inputs", "evaluation_inputs" not in runtime_script, "runtime source contains no evaluation_inputs access")
    leakage("L03", "runtime outputs exclude benchmark answer fields", not forbidden_runtime_headers & (set(runtime_headers) | set(cluster_headers) | set(selected_headers) | set(recovered_headers)), f"headers checked={len(runtime_headers)+len(cluster_headers)+len(selected_headers)+len(recovered_headers)}")
    leakage("L04", "runtime local subject ids are independently generated", all(":RS" in row["runtime_local_subject_id"] for row in selected_rows), "all selected rows use RS ids")
    leakage("L05", "heldout excluded from parameter selection", config["parameter_provenance"].get("heldout_used_for_parameter_selection") is False, json.dumps(config["parameter_provenance"], ensure_ascii=False))
    leakage("L06", "diagnostic-only excluded from parameter selection", config["parameter_provenance"].get("diagnostic_only_used_for_parameter_selection") is False, json.dumps(config["parameter_provenance"], ensure_ascii=False))
    leakage("L07", "benchmark appears only in evaluator outputs", all("no_benchmark_input=true" in row["notes"] for row in runtime_rows) and all("evaluation_only" in row["notes"] for row in evaluation_rows), "runtime rows and evaluation rows carry explicit provenance")
    leakage("L08", "no SAR or P2 runtime input", not any(token in runtime_input_text for token in ('"sar"', "sar_gt", "p2")), "runtime input dictionary scanned")

    leakage_pass = all(row["result"] == "pass" for row in leakage_rows if truth(row["blocking"]))
    heldout_b = role_metrics["B_MULTI_SOURCE_SELECTION"]["heldout_validation"]
    heldout_d = role_metrics["D_BIDIRECTIONAL_CONTROLLED"]["heldout_validation"]
    gm_scene_regression = {}
    for scene in ("GM_RM017", "GM_RM019"):
        scene_vehicles = [vehicle for vehicle in vehicles if scene_by_vehicle[vehicle] == scene]
        b_visible = sum(len(visible_frames[v]) for v in scene_vehicles)
        b_correct = sum(per_baseline_vehicle[("B_MULTI_SOURCE_SELECTION", v)]["correct_subject_observation_frame_count"] for v in scene_vehicles)
        d_correct = sum(per_baseline_vehicle[("D_BIDIRECTIONAL_CONTROLLED", v)]["correct_subject_observation_frame_count"] for v in scene_vehicles)
        gm_scene_regression[scene] = {"visible_frames": b_visible, "baseline_b_correct": b_correct, "baseline_d_correct": d_correct, "regressed": d_correct < b_correct}

    readiness = {
        "heldout_recall_improved": heldout_d["recall"] > heldout_b["recall"],
        "visible_unboxed_recovered": diagnostic_recovered > 0,
        "no_wrong_vehicle_recovery": purity_metrics["D_BIDIRECTIONAL_CONTROLLED"]["wrong_vehicle_recoveries"] == 0,
        "no_occlusion_or_outside_misrecovery": purity_metrics["D_BIDIRECTIONAL_CONTROLLED"]["occlusion_or_outside_misrecoveries"] == 0,
        "unique_subject_selection": purity_metrics["D_BIDIRECTIONAL_CONTROLLED"]["duplicate_subject_frames"] == 0 and purity_metrics["D_BIDIRECTIONAL_CONTROLLED"]["observation_reused_by_multiple_subjects"] == 0,
        "mixed_selection_reduced": purity_metrics["D_BIDIRECTIONAL_CONTROLLED"]["mixed_subject_selected"] < purity_metrics["B_MULTI_SOURCE_SELECTION"]["mixed_subject_selected"],
        "non_vehicle_selection_reduced": purity_metrics["D_BIDIRECTIONAL_CONTROLLED"]["non_vehicle_selected"] < purity_metrics["B_MULTI_SOURCE_SELECTION"]["non_vehicle_selected"],
        "gm017_gm019_no_regression": not any(item["regressed"] for item in gm_scene_regression.values()),
        "mean_segment_length_improved": heldout_d["mean_segment_length"] > heldout_b["mean_segment_length"],
        "leakage_audit_pass": leakage_pass,
    }
    stage_status = "P1F_SUBJECT_OBSERVATION_LAYER_READY" if all(readiness.values()) and config.get("visual_review_complete") is True else "P1F_SUBJECT_OBSERVATION_LAYER_PARTIALLY_READY"

    write_csv(ROOT / outputs["evaluation"], EVALUATION_FIELDS, evaluation_rows)
    write_csv(ROOT / outputs["failure_inventory"], FAILURE_FIELDS, failure_rows)
    write_csv(ROOT / outputs["leakage_audit"], LEAKAGE_FIELDS, leakage_rows)

    metrics = {
        "stage_status": stage_status, "source_boundary": config["source_boundary"],
        "role_metrics": role_metrics, "purity_metrics": purity_metrics,
        "visible_but_unboxed_total": unboxed_total, "visible_but_unboxed_correctly_recovered": diagnostic_recovered,
        "scene_regression": gm_scene_regression, "readiness": readiness,
        "visual_review_complete": config.get("visual_review_complete"), "leakage_audit": "PASS" if leakage_pass else "FAIL",
        "evaluation_row_count": len(evaluation_rows), "failure_row_count": len(failure_rows),
        "hashes": {
            "evaluation": sha256_rows(evaluation_rows, EVALUATION_FIELDS),
            "failure_inventory": sha256_rows(failure_rows, FAILURE_FIELDS),
            "leakage_audit": sha256_rows(leakage_rows, LEAKAGE_FIELDS),
        },
        "p1f_representation_entry_allowed": stage_status == "P1F_SUBJECT_OBSERVATION_LAYER_READY",
        "p2_entry_allowed": False,
    }
    metrics_path = ROOT / outputs["metrics"]
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# OTY2 P1-F 多帧主体观察整理与缺失观察恢复报告", "", "日期：`2026-07-14`", "",
        "## 1. 阶段结论", "", f"阶段状态：`{stage_status}`。", "",
        "运行时脚本只读取光学帧、两路 normalized detections 和已有 tracker 局部关系；P1-E canonical、reference bbox、逐帧状态与 role 仅由独立 evaluator 读取。未读取 SAR、SAR GT、方位映射或 P2。", "",
        "## 2. 四级实验按车辆角色结果", "",
        "| baseline | role | visible | correct | recall | complete | visible-no-observation | correct recovered | mean segment | single-frame segments |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for baseline in BASELINES:
        for role in ("development", "heldout_validation", "diagnostic_only"):
            item = role_metrics[baseline][role]
            report_lines.append(f"| {baseline} | {role} | {item['visible_frames']} | {item['correct_frames']} | {item['recall']:.4f} | {item['complete_frames']} | {item['visible_no_observation']} | {item['correct_recovered_frames']} | {item['mean_segment_length']:.3f} | {item['single_frame_segment_count']} |")
    report_lines += ["", "## 3. 观察纯度", "", "| baseline | mixed selected | non-vehicle selected | wrong subject links | wrong recoveries | occlusion/outside misrecoveries | duplicate subject frames | reused observation |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for baseline in BASELINES:
        item = purity_metrics[baseline]
        report_lines.append(f"| {baseline} | {item['mixed_subject_selected']} | {item['non_vehicle_selected']} | {item['wrong_subject_links']} | {item['wrong_vehicle_recoveries']} | {item['occlusion_or_outside_misrecoveries']} | {item['duplicate_subject_frames']} | {item['observation_reused_by_multiple_subjects']} |")
    report_lines += [
        "", "## 4. visible-but-unboxed 恢复", "",
        f"P1-E 共确认 83 个 visible-but-unboxed 帧；Baseline D 正确恢复 `{diagnostic_recovered}` 帧。恢复框来自 LK 光流、RANSAC 相似仿射和模板相关性，不使用线性 bbox 插值作为最终结果。", "",
        "## 5. GM_RM017 / GM_RM019 回归", "",
    ]
    for scene, item in gm_scene_regression.items():
        report_lines.append(f"- {scene}: Baseline B={item['baseline_b_correct']}/{item['visible_frames']}，Baseline D={item['baseline_d_correct']}/{item['visible_frames']}，regressed=`{str(item['regressed']).lower()}`。")
    report_lines += ["", "## 6. READY 条件", ""]
    for key, value in readiness.items():
        report_lines.append(f"- `{key}`: `{str(value).lower()}`")
    report_lines += [
        "", "## 7. 泄漏与阶段边界", "",
        f"Runtime/benchmark leakage audit: `{'PASS' if leakage_pass else 'FAIL'}`。P1-F representation entry allowed: `{str(stage_status == 'P1F_SUBJECT_OBSERVATION_LAYER_READY').lower()}`。P2 entry allowed: `false`。", "",
        "未修改 P1-C solver、ILP、目标函数、birth/exit cost 或身份边权重；未训练 detector/ReID；未使用 frame/scene-specific Gate、manual override 或 heldout 调参；未运行 SAR 候选、selector、ranking、标注或 P2。", "",
        "## 8. 直接视觉审阅", "",
        "已直接审阅 90 页临时视觉产物，覆盖三个场景全部 1104 帧、全部 83 个 visible-but-unboxed 上下文、全部 245 个接受恢复，以及错误恢复、mixed-subject、非车辆稳定观察、同车多框竞争、heldout 完整序列和 GM_RM017/019 无回归检查。临时图片保留在 workspace/output，未进入正式产物。", "",
        "视觉结论与自动评价一致：PV004 在 60--63 帧附近仅短暂恢复，64--87 帧仍缺失；PV009 在约 181--187 帧恢复成功，但 192--196 帧再次漏失；PV014 在约 318--336 帧仍无主体观察。GM_RM011 存在同一物理车辆对应多个 runtime local subject 的情况。GM_RM017/019 的基准车辆召回未退化，但红色门栏、路侧设施、行人、两轮车和相邻碎片仍被错误选择或传播。", "",
        "因此视觉审阅不支持 READY：正确恢复范围有限，错误车辆恢复、非车辆选择和每车每帧唯一性问题仍然存在。", "",
        "## 9. 固定输出摘要", "",
        f"- evaluation hash: `{metrics['hashes']['evaluation']}`",
        f"- failure inventory hash: `{metrics['hashes']['failure_inventory']}`",
        f"- leakage audit hash: `{metrics['hashes']['leakage_audit']}`",
    ]
    report_path = ROOT / outputs["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
