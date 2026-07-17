#!/usr/bin/env python3
from __future__ import annotations

"""Build target-reference-free lifecycle conditions and all-active-identity shells."""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from oty2_s1d0_common import (
    REPO_ROOT,
    build_condition_geometry,
    combined_visibility,
    interpolate_bbox,
    lifecycle_state,
    load_json,
    read_csv,
    require,
    resolve,
    sample_depth,
    sha256_file,
    verify_git_gate,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = REPO_ROOT / "configs" / "oty2" / "oty2_s1d0_dynamic_response.json"
CONDITION_PATH = REPO_ROOT / "manifests" / "oty2" / "oty2_s1d0_lifecycle_conditions.csv"
SUMMARY_PATH = REPO_ROOT / "reports" / "oty2" / "oty2_s1d0_lifecycle_condition_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def unique_cases(selection_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    cases: dict[str, dict[str, str]] = {}
    roles: dict[str, list[str]] = defaultdict(list)
    for row in selection_rows:
        cases[row["case_id"]] = row
        roles[row["case_id"]].append(row["role"])
    result = []
    for case_id in sorted(cases):
        row = dict(cases[case_id])
        row["roles"] = ";".join(sorted(roles[case_id]))
        result.append(row)
    return result


def main() -> None:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config
    config = load_json(config_path)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    sources = {name: resolve(path) for name, path in config["sources"].items() if name != "lifecycle_conditions"}
    scene_config = load_json(sources["scene_config"])
    inventory = read_csv(sources["inventory"])
    selections = read_csv(sources["selected_roles"])
    registry = read_csv(sources["canonical_vehicle_registry"])
    states = read_csv(sources["canonical_frame_states"])
    time_rows = read_csv(sources["sar_to_optical_time_map"])
    calibration = load_json(sources["calibration"])
    cases = unique_cases(selections)
    inventory_by_id = {row["canonical_vehicle_id"]: row for row in inventory}
    vehicles_by_scene: dict[str, list[str]] = defaultdict(list)
    for row in registry:
        vehicles_by_scene[row["scene"]].append(row["canonical_vehicle_id"])
    state_index = {(row["scene"], row["canonical_vehicle_id"], int(row["frame_index"])): row for row in states}
    time_index = {(row["scene"], int(row["sar_frame_index"])): row for row in time_rows}
    rows: list[dict[str, Any]] = []
    input_paths: set[Path] = {config_path, *sources.values()}
    for case in cases:
        case_id = case["case_id"]
        scene = case["scene"]
        target_id = case["canonical_vehicle_id"]
        target_inventory = inventory_by_id[target_id]
        frame_start = int(target_inventory["mapped_sar_pre_roll_start"])
        frame_end = int(target_inventory["mapped_sar_post_roll_end"])
        for sar_frame in range(frame_start, frame_end + 1):
            time_row = time_index[(scene, sar_frame)]
            left_frame = int(time_row["optical_left_frame"])
            right_frame = int(time_row["optical_right_frame"])
            ratio = float(time_row["optical_interpolation_ratio"])
            sar_path = Path(scene_config["scenes"][scene]["paths"]["sar_gray_frames_dir"]) / f"{sar_frame:06d}.png"
            require(sar_path.is_file(), f"missing SAR frame: {sar_path}")
            input_paths.add(sar_path)
            frame_records: list[dict[str, Any]] = []
            for vehicle_id in vehicles_by_scene[scene]:
                vehicle_inventory = inventory_by_id[vehicle_id]
                lifecycle_start = int(vehicle_inventory["mapped_sar_lifecycle_start"])
                lifecycle_end = int(vehicle_inventory["mapped_sar_lifecycle_end"])
                left_state = state_index[(scene, vehicle_id, left_frame)]
                right_state = state_index[(scene, vehicle_id, right_frame)]
                visibility = combined_visibility(left_state, right_state)
                state, reason = lifecycle_state(
                    sar_frame,
                    lifecycle_start,
                    lifecycle_end,
                    visibility,
                    int(config["lifecycle"]["entry_provisional_sar_frames"]),
                    int(config["lifecycle"]["exit_sar_frames"]),
                    int(config["lifecycle"]["closure_grace_sar_frames"]),
                )
                is_target = vehicle_id == target_id
                if not is_target and state in {"ABSENT", "CLOSED"}:
                    continue
                bbox, bbox_status, bbox_multiplier = interpolate_bbox(
                    state_index, scene, vehicle_id, left_frame, right_frame, ratio
                )
                active_for_shell = state not in {"ABSENT", "CLOSED"} and bbox is not None
                geometry: dict[str, Any] = {}
                depth_median = math.nan
                depth_mad = math.nan
                if bbox is not None:
                    depth_path = Path(scene_config["scenes"][scene]["paths"]["depth_dir"]) / f"{left_frame:06d}_depth.npy"
                    depth_median, depth_mad = sample_depth(depth_path, bbox)
                    input_paths.add(depth_path)
                    geometry = build_condition_geometry(
                        scene, bbox, depth_median, calibration, visibility, bbox_multiplier, config["uncertainty"]
                    )
                record: dict[str, Any] = {
                    "case_id": case_id,
                    "case_roles": case["roles"],
                    "scene": scene,
                    "target_canonical_vehicle_id": target_id,
                    "canonical_vehicle_id": vehicle_id,
                    "is_target_identity": str(is_target).lower(),
                    "sar_frame_index": sar_frame,
                    "sar_time_sec": time_row["sar_time_sec"],
                    "sar_gray_path": str(sar_path),
                    "sar_gray_sha256": sha256_file(sar_path),
                    "optical_left_frame": left_frame,
                    "optical_right_frame": right_frame,
                    "optical_interpolation_ratio": ratio,
                    "optical_visibility_state": visibility,
                    "optical_lifecycle_state": state,
                    "state_transition_reason": reason,
                    "active_for_shell": str(active_for_shell).lower(),
                    "bbox_source_status": bbox_status,
                    "optical_depth_median_proxy": depth_median,
                    "optical_depth_mad_proxy": depth_mad,
                    "target_sar_reference_dependency": "false",
                    "identity_owner": "P1E_OPTICAL_CANONICAL_THREAD",
                }
                if bbox is not None:
                    record.update({
                        "optical_bbox_x1": bbox[0],
                        "optical_bbox_y1": bbox[1],
                        "optical_bbox_x2": bbox[2],
                        "optical_bbox_y2": bbox[3],
                        **geometry,
                    })
                frame_records.append(record)
            active_count = sum(row["active_for_shell"] == "true" for row in frame_records)
            for record in frame_records:
                record["active_identity_count_in_scene"] = active_count
                rows.append(record)
    write_csv(CONDITION_PATH, rows)
    summary = {
        "version": config["version"],
        "git": git_state,
        "config_sha256": sha256_file(config_path),
        "source_hashes": {name: sha256_file(path) for name, path in sources.items()},
        "condition_output": str(CONDITION_PATH),
        "condition_sha256": sha256_file(CONDITION_PATH),
        "condition_row_count": len(rows),
        "case_target_frame_counts": dict(Counter(row["case_id"] for row in rows if row["is_target_identity"] == "true")),
        "active_shell_rows": sum(row["active_for_shell"] == "true" for row in rows),
        "target_reference_dependency_rows": sum(row["target_sar_reference_dependency"] != "false" for row in rows),
        "input_file_count": len(input_paths),
        "old_work_runtime_dependency": False,
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
