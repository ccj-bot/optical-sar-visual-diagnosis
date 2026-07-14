#!/usr/bin/env python3
"""Validate the optical-only OTY2 P1-E identity benchmark and replay it deterministically."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/oty2/oty2_p1e_optical_identity_benchmark.yaml"
RUNNER = ROOT / "tools/diagnostics/run_oty2_p1e_optical_identity_benchmark.py"
SCENES = {"GM_RM011", "GM_RM017", "GM_RM019"}
EXPECTED_VEHICLES = Counter({"GM_RM011": 14, "GM_RM017": 4, "GM_RM019": 4})
FORBIDDEN_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".avi", ".mov", ".npz", ".npy",
    ".pt", ".pth", ".onnx", ".ckpt", ".zip", ".7z", ".rar", ".docx",
}

SCHEMAS = {
    "canonical_registry": [
        "scene", "canonical_vehicle_id", "frame_first_visible", "frame_last_visible",
        "visible_frame_ranges", "partial_visibility_ranges", "full_occlusion_ranges",
        "visible_but_unboxed_ranges", "entry_frame", "entry_location", "entry_direction",
        "exit_frame", "exit_location", "exit_direction", "vehicle_color", "vehicle_type_or_shape",
        "dominant_motion_direction", "scale_trend", "distinctive_visual_features",
        "occluding_vehicle_ids", "p1c_global_vehicle_ids", "source_tracker_ids",
        "identity_evidence_summary", "benchmark_confidence", "notes",
    ],
    "frame_states": [
        "scene", "canonical_vehicle_id", "frame_index", "lifecycle_state", "visibility_state",
        "is_vehicle_in_scene", "is_vehicle_visible", "is_full_vehicle_visible",
        "is_partially_visible", "is_fully_occluded", "is_visible_but_unboxed",
        "occlusion_source", "entry_or_exit_state", "reference_bbox_available",
        "reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2",
        "reference_bbox_origin", "reference_subject_description", "benchmark_evidence", "notes",
    ],
    "detection_map": [
        "scene", "frame_index", "detector_source", "source_detection_id", "bbox", "confidence",
        "assigned_canonical_vehicle_id", "assignment_status", "observation_role",
        "vehicle_completeness", "subject_purity", "overlapping_vehicle_ids",
        "p1c_observation_id", "source_tracker_ids", "benchmark_evidence", "notes",
    ],
    "failure_inventory": [
        "scene", "failure_id", "canonical_vehicle_id", "frame_start", "frame_end", "failure_type",
        "detector_sources", "tracker_ids", "p1c_global_vehicle_ids", "visual_ground_truth",
        "current_observation_behavior", "identity_consequence", "root_cause_layer",
        "recommended_future_mechanism", "severity", "notes",
    ],
    "fragmentation_attribution": [
        "scene", "atomic_tracklet_id", "frame_start", "frame_end", "frame_count",
        "assigned_canonical_vehicle_ids", "p1c_global_vehicle_ids", "source_track_ids",
        "detector_sources", "split_reason", "primary_fragmentation_cause", "secondary_causes",
        "identity_purity_necessity", "benchmark_evidence", "recommended_future_mechanism", "notes",
    ],
    "benchmark_roles": [
        "scene", "canonical_vehicle_id", "benchmark_role", "role_reason", "permitted_use",
        "prohibited_use", "notes",
    ],
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def main() -> int:
    failures: list[str] = []
    if not CONFIG.exists():
        print(json.dumps({"status": "FAIL", "failures": [f"missing:{CONFIG}"]}, ensure_ascii=False, indent=2))
        return 1

    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if config.get("source_boundary") != "optical_only_no_sar_no_gt":
        failures.append("source_boundary")
    if config.get("stage_status") != "P1E_OPTICAL_IDENTITY_BENCHMARK_READY":
        failures.append(f"stage_status:{config.get('stage_status')}")
    if config.get("visual_review_complete") is not True:
        failures.append("visual_review_complete")
    if config.get("benchmark_runtime_separation") is not True:
        failures.append("benchmark_runtime_separation")
    if config.get("p1f_entry_allowed") is not True:
        failures.append("p1f_entry_allowed")
    if config.get("p2_entry_allowed") is not False:
        failures.append("p2_entry_allowed")

    forbidden_actions = set(config.get("forbidden_actions", []))
    required_forbidden = {
        "read_sar", "read_sar_gt", "start_p2", "modify_p1c_solver",
        "runtime_manual_override", "train_detector_or_reid", "use_benchmark_as_runtime_prediction",
    }
    if forbidden_actions != required_forbidden:
        failures.append(f"forbidden_actions:{sorted(forbidden_actions)}")

    loaded: dict[str, list[dict[str, str]]] = {}
    output_paths: dict[str, Path] = {}
    for key, expected_schema in SCHEMAS.items():
        relative = config.get("outputs", {}).get(key)
        if not relative:
            failures.append(f"missing_output_config:{key}")
            continue
        path = ROOT / relative
        output_paths[key] = path
        if not path.exists():
            failures.append(f"missing:{relative}")
            continue
        fields, rows = read_csv(path)
        if fields != expected_schema:
            failures.append(f"schema:{relative}:actual={fields}")
        loaded[key] = rows

    report_relative = config.get("outputs", {}).get("report", "")
    report_path = ROOT / report_relative if report_relative else ROOT / "__missing_report__"
    if not report_path.exists():
        failures.append(f"missing_report:{report_relative}")

    registry = loaded.get("canonical_registry", [])
    frame_states = loaded.get("frame_states", [])
    detections = loaded.get("detection_map", [])
    failures_rows = loaded.get("failure_inventory", [])
    fragments = loaded.get("fragmentation_attribution", [])
    roles = loaded.get("benchmark_roles", [])

    vehicle_counts = Counter(row.get("scene") for row in registry)
    if vehicle_counts != EXPECTED_VEHICLES:
        failures.append(f"canonical_vehicle_counts:{dict(vehicle_counts)}")
    canonical_ids = [row.get("canonical_vehicle_id", "") for row in registry]
    canonical_set = set(canonical_ids)
    if len(canonical_set) != len(canonical_ids) or "" in canonical_set:
        failures.append("canonical_id_uniqueness")
    confidence_domain = {"confirmed", "confirmed_with_partial_visibility", "requires_benchmark_recheck"}
    invalid_confidence = sorted({row.get("benchmark_confidence", "") for row in registry} - confidence_domain)
    if invalid_confidence:
        failures.append(f"benchmark_confidence_domain:{invalid_confidence}")
    for row in registry:
        canonical = row.get("canonical_vehicle_id", "")
        first, last = int(row["frame_first_visible"]), int(row["frame_last_visible"])
        if not (0 <= first <= last < 368):
            failures.append(f"lifecycle_order:{canonical}:{first}-{last}")
        if int(row["entry_frame"]) != first or int(row["exit_frame"]) != last:
            failures.append(f"entry_exit_registry:{canonical}")

    state_by_vehicle: dict[str, list[dict[str, str]]] = defaultdict(list)
    state_keys: set[tuple[str, int]] = set()
    for row in frame_states:
        canonical = row.get("canonical_vehicle_id", "")
        frame = int(row.get("frame_index", -1))
        key = (canonical, frame)
        if key in state_keys:
            failures.append(f"duplicate_frame_state:{canonical}:{frame}")
        state_keys.add(key)
        state_by_vehicle[canonical].append(row)
        if canonical not in canonical_set:
            failures.append(f"unknown_frame_state_vehicle:{canonical}")
    registry_by_id = {row["canonical_vehicle_id"]: row for row in registry}
    for canonical in sorted(canonical_set):
        rows = sorted(state_by_vehicle.get(canonical, []), key=lambda row: int(row["frame_index"]))
        frames = [int(row["frame_index"]) for row in rows]
        if frames != list(range(368)):
            failures.append(f"frame_state_coverage:{canonical}:{len(rows)}")
            continue
        first = int(registry_by_id[canonical]["frame_first_visible"])
        last = int(registry_by_id[canonical]["frame_last_visible"])
        for row in rows:
            frame = int(row["frame_index"])
            inside = first <= frame <= last
            if truth(row["is_vehicle_in_scene"]) != inside or truth(row["is_vehicle_visible"]) != inside:
                failures.append(f"visibility_lifecycle:{canonical}:{frame}")
            expected_entry_exit = "entry" if frame == first else "exit" if frame == last else "none"
            if row["entry_or_exit_state"] != expected_entry_exit:
                failures.append(f"entry_exit_state:{canonical}:{frame}")
            if frame < first and row["lifecycle_state"] != "outside_before_entry":
                failures.append(f"outside_before:{canonical}:{frame}")
            if frame > last and row["lifecycle_state"] != "outside_after_exit":
                failures.append(f"outside_after:{canonical}:{frame}")
            if truth(row["is_fully_occluded"]) and truth(row["reference_bbox_available"]):
                failures.append(f"occluded_bbox:{canonical}:{frame}")
            if truth(row["is_visible_but_unboxed"]) and row["lifecycle_state"] != "visible_but_unboxed":
                failures.append(f"unboxed_state:{canonical}:{frame}")

    detection_keys: set[tuple[str, str, str]] = set()
    preferred_counts: Counter[tuple[str, int]] = Counter()
    preferred_keys: set[tuple[str, int]] = set()
    assignment_domain = {
        "correct_vehicle_observation", "duplicate_observation_same_vehicle", "partial_vehicle_observation",
        "mixed_subject_observation", "wrong_vehicle_assignment", "non_vehicle",
        "ambiguous_detection_geometry", "unassigned",
    }
    role_domain = {
        "preferred_subject_observation", "usable_auxiliary_observation", "diagnostic_only",
        "exclude_from_vehicle_identity",
    }
    for row in detections:
        key = (row["scene"], row["detector_source"], row["source_detection_id"])
        if key in detection_keys:
            failures.append(f"duplicate_detection:{key}")
        detection_keys.add(key)
        canonical = row["assigned_canonical_vehicle_id"]
        frame = int(row["frame_index"])
        if canonical and canonical not in canonical_set:
            failures.append(f"unknown_detection_vehicle:{key}:{canonical}")
        if row["assignment_status"] not in assignment_domain:
            failures.append(f"assignment_status_domain:{key}:{row['assignment_status']}")
        if row["observation_role"] not in role_domain:
            failures.append(f"observation_role_domain:{key}:{row['observation_role']}")
        if row["assignment_status"] == "non_vehicle" and canonical:
            failures.append(f"non_vehicle_bound:{key}:{canonical}")
        if row["observation_role"] == "preferred_subject_observation":
            preferred_counts[(canonical, frame)] += 1
            preferred_keys.add((canonical, frame))
    for key, count in preferred_counts.items():
        if not key[0] or count > 1:
            failures.append(f"preferred_observation_count:{key}:{count}")
    for row in frame_states:
        if truth(row["is_visible_but_unboxed"]):
            key = (row["canonical_vehicle_id"], int(row["frame_index"]))
            if key in preferred_keys:
                failures.append(f"unboxed_has_preferred:{key}")

    input_detection_keys: set[tuple[str, str, str]] = set()
    for scene, sources in config.get("inputs", {}).get("normalized_detection_tables", {}).items():
        if scene not in SCENES:
            failures.append(f"input_scene:{scene}")
        for source, path_value in sources.items():
            path = Path(path_value)
            if source not in {"YOLO11l", "YOLO26l"} or not path.exists():
                failures.append(f"detection_input:{scene}:{source}:{path}")
                continue
            fields, rows = read_csv(path)
            required = {"scene", "optical_frame_num", "det_id", "confidence", "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2"}
            if not required <= set(fields):
                failures.append(f"detection_input_schema:{path}")
            input_detection_keys.update((scene, source, row["det_id"]) for row in rows)
    if detection_keys != input_detection_keys:
        failures.append(
            f"detection_provenance:missing={len(input_detection_keys - detection_keys)}:extra={len(detection_keys - input_detection_keys)}"
        )

    role_by_vehicle = {row.get("canonical_vehicle_id", ""): row.get("benchmark_role", "") for row in roles}
    if len(roles) != len(canonical_set) or set(role_by_vehicle) != canonical_set:
        failures.append("benchmark_role_vehicle_coverage")
    if set(role_by_vehicle.values()) - {"development", "heldout_validation", "diagnostic_only"}:
        failures.append("benchmark_role_domain")
    config_role_lookup: dict[str, str] = {}
    for role, vehicles in config.get("benchmark_roles", {}).items():
        for canonical in vehicles:
            if canonical in config_role_lookup:
                failures.append(f"benchmark_role_duplicate:{canonical}")
            config_role_lookup[canonical] = role
    if config_role_lookup != role_by_vehicle:
        failures.append("benchmark_role_config_mismatch")
    heldout_scenes = {registry_by_id[canonical]["scene"] for canonical, role in role_by_vehicle.items() if role == "heldout_validation"}
    if heldout_scenes != SCENES:
        failures.append(f"heldout_scene_coverage:{sorted(heldout_scenes)}")
    if all(role_by_vehicle.get(f"GM_RM017:PV{index:03d}") == "development" for index in range(1, 5)):
        failures.append("gm017_all_development")

    known_cases = {
        ("GM_RM011:PV009", "same_vehicle_multiple_global_ids"),
        ("GM_RM011:PV014", "vehicle_missing_from_all_threads"),
        ("GM_RM011:PV004", "occlusion_recovery_failure"),
        ("", "false_vehicle_thread"),
        ("GM_RM019:PV003", "different_vehicles_one_global_id"),
        ("GM_RM019:PV003", "same_vehicle_multiple_global_ids"),
    }
    actual_cases = {(row.get("canonical_vehicle_id", ""), row.get("failure_type", "")) for row in failures_rows}
    missing_cases = sorted(known_cases - actual_cases)
    if missing_cases:
        failures.append(f"p1d_failure_closure:{missing_cases}")
    if len({row.get("failure_id", "") for row in failures_rows}) != len(failures_rows):
        failures.append("failure_id_uniqueness")

    _, p1c_atomic = read_csv(ROOT / config["inputs"]["p1c_atomic_tracklets"])
    if len(fragments) != len(p1c_atomic):
        failures.append(f"fragmentation_coverage:{len(fragments)}!={len(p1c_atomic)}")
    if {row.get("atomic_tracklet_id", "") for row in fragments} != {row.get("atomic_tracklet_id", "") for row in p1c_atomic}:
        failures.append("fragmentation_id_coverage")

    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    for required_text in (
        "P1E_OPTICAL_IDENTITY_BENCHMARK_READY", "14", "GM_RM011", "GM_RM017", "GM_RM019",
        "visible-but-unboxed", "GV009/GV010", "GV003", "GV004/GV005", "heldout_validation",
        "P1-F entry allowed: `true`", "P2 entry allowed: `false`", "未读取 SAR",
    ):
        if required_text not in report:
            failures.append(f"report_missing:{required_text}")

    status = git("status", "--porcelain")
    status_paths = [line[3:].strip().strip('"').replace("\\", "/") for line in status.stdout.splitlines() if line]
    for path in status_paths:
        if Path(path).suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden_asset_in_worktree:{path}")
    changed = set(git("diff", "--name-only").stdout.splitlines()) | set(git("diff", "--cached", "--name-only").stdout.splitlines())
    protected = sorted(
        path for path in changed
        if any(token in path.lower() for token in ("oty2_p1b_", "oty2_p1c_", "oty2_p1d_"))
    )
    if protected:
        failures.append(f"protected_history_modified:{protected}")
    expected_prefixes = {
        "configs/oty2/oty2_p1e_", "docs/OTY2_P1E_", "manifests/oty2/oty2_p1e_",
        "reports/oty2/oty2_p1e_", "tools/diagnostics/run_oty2_p1e_",
        "tools/diagnostics/validate_oty2_p1e_",
    }
    unexpected = sorted(path for path in status_paths if not any(path.startswith(prefix) for prefix in expected_prefixes))
    if unexpected:
        failures.append(f"unexpected_worktree_paths:{unexpected}")

    formal_paths = list(output_paths.values()) + [report_path]
    before_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in formal_paths if path.exists()}
    replay = subprocess.run(
        [sys.executable, str(RUNNER)], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    replay_payload: dict[str, Any] = {}
    if replay.returncode != 0:
        failures.append(f"fixed_input_replay_exit:{replay.returncode}:{replay.stderr[-500:]}")
    else:
        try:
            replay_payload = json.loads(replay.stdout)
        except json.JSONDecodeError:
            failures.append("fixed_input_replay_json")
    after_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in formal_paths if path.exists()}
    if before_hashes != after_hashes:
        changed_hashes = sorted(path for path in set(before_hashes) | set(after_hashes) if before_hashes.get(path) != after_hashes.get(path))
        failures.append(f"fixed_input_replay_hash_mismatch:{changed_hashes}")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "stage_status": config.get("stage_status"),
        "failures": failures,
        "canonical_vehicle_counts": dict(vehicle_counts),
        "frame_state_counts": dict(Counter(row.get("scene") for row in frame_states)),
        "detection_row_count": len(detections),
        "failure_row_count": len(failures_rows),
        "fragmentation_row_count": len(fragments),
        "benchmark_role_counts": dict(Counter(role_by_vehicle.values())),
        "visual_review_complete": config.get("visual_review_complete"),
        "fixed_input_replay": "PASS" if before_hashes == after_hashes and replay.returncode == 0 else "FAIL",
        "formal_output_sha256": after_hashes,
        "runner_summary": replay_payload,
        "p1f_entry_allowed": config.get("p1f_entry_allowed"),
        "p2_entry_allowed": config.get("p2_entry_allowed"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
