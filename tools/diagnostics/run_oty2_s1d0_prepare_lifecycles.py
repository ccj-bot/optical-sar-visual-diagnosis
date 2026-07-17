#!/usr/bin/env python3
from __future__ import annotations

"""Inventory all three optical lifecycles without target SAR references."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from oty2_s1d0_common import (
    REPO_ROOT,
    SCENES,
    bbox_from_state,
    build_condition_geometry,
    combined_visibility,
    compact_ranges,
    condition_shell,
    imaging_valid_mask,
    interpolate_bbox,
    lifecycle_sar_bounds,
    load_json,
    parse_ranges,
    read_csv,
    require,
    resolve,
    sample_depth,
    sha256_file,
    verify_git_gate,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = REPO_ROOT / "configs" / "oty2" / "oty2_s1d0_inventory.json"
INVENTORY_PATH = REPO_ROOT / "manifests" / "oty2" / "oty2_s1d0_multiscene_lifecycle_inventory.csv"
REVIEW_MANIFEST_PATH = REPO_ROOT / "manifests" / "oty2" / "oty2_s1d0_inventory_blind_review_manifest.csv"
SELECTION_PATH = REPO_ROOT / "manifests" / "oty2" / "oty2_s1d0_selected_lifecycle_roles.csv"
SUMMARY_PATH = REPO_ROOT / "reports" / "oty2" / "oty2_s1d0_inventory_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def candidate_roles(row: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    duration = int(row["visible_duration_optical_frames"])
    bbox_fraction = float(row["optical_bbox_available_fraction"])
    shell_valid = float(row["sampled_shell_valid_fraction_mean"])
    if row["scene"] == "GM_RM017" and duration >= 35 and bbox_fraction >= 0.95 and shell_valid >= 0.35 and row["calibration_independence"] == "INDEPENDENT_TARGET_FROM_PV004_CALIBRATION":
        roles.append("MECHANISM_DISCOVERY_CANDIDATE")
    if row["scene"] == "GM_RM019" and duration >= 30 and bbox_fraction >= 0.95 and shell_valid >= 0.25:
        roles.append("CROSS_SCENE_FROZEN_REPLAY_CANDIDATE")
    if int(row["entry_frame"]) > 0 and int(row["exit_frame"]) < 367 and duration >= 25:
        roles.append("ENTRY_EXIT_LIFECYCLE_CANDIDATE")
    if row["scene"] == "GM_RM011" and (int(row["max_simultaneously_visible_vehicles"]) >= 2 or int(row["visible_but_unboxed_duration"]) > 0):
        roles.append("MULTI_VEHICLE_OR_OCCLUSION_STRESS_CANDIDATE")
    return roles


def make_review(
    row: dict[str, Any],
    registry_row: dict[str, str],
    scene_paths: dict[str, str],
    state_index: dict[tuple[str, str, int], dict[str, str]],
    time_index: dict[tuple[str, int], dict[str, str]],
    calibration: dict[str, Any],
    uncertainty: dict[str, Any],
    output_root: Path,
    requested: int,
) -> Path:
    scene = row["scene"]
    vehicle_id = row["canonical_vehicle_id"]
    sar_start = int(row["mapped_sar_lifecycle_start"])
    sar_end = int(row["mapped_sar_lifecycle_end"])
    frames = sorted(set(int(value) for value in np.linspace(sar_start, sar_end, min(requested, sar_end - sar_start + 1))))
    figure, axes = plt.subplots(len(frames), 2, figsize=(12, 4 * len(frames)), squeeze=False)
    for axis_row, sar_frame in enumerate(frames):
        time_row = time_index[(scene, sar_frame)]
        left_frame = int(time_row["optical_left_frame"])
        right_frame = int(time_row["optical_right_frame"])
        ratio = float(time_row["optical_interpolation_ratio"])
        left_state = state_index[(scene, vehicle_id, left_frame)]
        right_state = state_index[(scene, vehicle_id, right_frame)]
        bbox, bbox_status, bbox_multiplier = interpolate_bbox(state_index, scene, vehicle_id, left_frame, right_frame, ratio)
        require(bbox is not None, f"no review bbox for {vehicle_id} at SAR {sar_frame}")
        optical_path = Path(scene_paths["optical_frames_dir"]) / f"{left_frame:06d}.png"
        optical = cv2.imread(str(optical_path), cv2.IMREAD_COLOR)
        require(optical is not None, f"missing optical image: {optical_path}")
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        cv2.rectangle(optical, (x1, y1), (x2, y2), (0, 255, 255), 2)
        axes[axis_row, 0].imshow(cv2.cvtColor(optical, cv2.COLOR_BGR2RGB))
        axes[axis_row, 0].set_title(f"optical {left_frame} {left_state['visibility_state']} | {bbox_status}")
        depth_path = Path(scene_paths["depth_dir"]) / f"{left_frame:06d}_depth.npy"
        depth_median, _ = sample_depth(depth_path, bbox)
        visibility = combined_visibility(left_state, right_state)
        geometry = build_condition_geometry(scene, bbox, depth_median, calibration, visibility, bbox_multiplier, uncertainty)
        shell = condition_shell(geometry)
        sar_path = Path(scene_paths["sar_gray_frames_dir"]) / f"{sar_frame:06d}.png"
        sar = cv2.imread(str(sar_path), cv2.IMREAD_GRAYSCALE)
        require(sar is not None, f"missing SAR image: {sar_path}")
        view = cv2.cvtColor(np.clip(sar.astype(np.float32) / 85.0 * 255.0, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2RGB)
        contours, _ = cv2.findContours(shell.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(view, contours, -1, (0, 200, 255), 2)
        axes[axis_row, 1].imshow(view)
        axes[axis_row, 1].set_title(f"SAR {sar_frame} optical shell only | {geometry['mapping_status']}")
        for axis in axes[axis_row]:
            axis.axis("off")
    figure.suptitle(f"{vehicle_id} lifecycle blind inventory review (no target SAR reference)\n{registry_row['vehicle_color']} {registry_row['vehicle_type_or_shape']}")
    figure.tight_layout()
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"{vehicle_id.replace(':', '_')}_inventory_review.png"
    figure.savefig(path, dpi=130)
    plt.close(figure)
    return path


def main() -> None:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config
    config = load_json(config_path)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    sources = {name: resolve(path) for name, path in config["sources"].items()}
    scene_config = load_json(sources["scene_config"])
    registry = read_csv(sources["canonical_vehicle_registry"])
    states = read_csv(sources["canonical_frame_states"])
    time_rows = read_csv(sources["sar_to_optical_time_map"])
    calibration = load_json(sources["calibration"])
    require(set(row["scene"] for row in registry) == set(SCENES), "registry scene mismatch")
    state_index = {(row["scene"], row["canonical_vehicle_id"], int(row["frame_index"])): row for row in states}
    time_index = {(row["scene"], int(row["sar_frame_index"])): row for row in time_rows}
    visible_by_scene_frame: dict[tuple[str, int], set[str]] = defaultdict(set)
    for state in states:
        if state["is_vehicle_visible"].lower() == "true":
            visible_by_scene_frame[(state["scene"], int(state["frame_index"]))].add(state["canonical_vehicle_id"])
    valid_mask = imaging_valid_mask()
    inventory: list[dict[str, Any]] = []
    registry_by_id = {row["canonical_vehicle_id"]: row for row in registry}
    selected_by_vehicle = {case["vehicle_id"]: case for case in config["selected_cases"]}
    for vehicle in registry:
        scene = vehicle["scene"]
        vehicle_id = vehicle["canonical_vehicle_id"]
        vehicle_states = [state_index[(scene, vehicle_id, frame)] for frame in range(368)]
        visible_frames = {int(row["frame_index"]) for row in vehicle_states if row["is_vehicle_visible"].lower() == "true"}
        full_frames = {int(row["frame_index"]) for row in vehicle_states if row["is_full_vehicle_visible"].lower() == "true"}
        partial_frames = {int(row["frame_index"]) for row in vehicle_states if row["is_partially_visible"].lower() == "true"}
        occluded_frames = {int(row["frame_index"]) for row in vehicle_states if row["is_fully_occluded"].lower() == "true"}
        unboxed_frames = {int(row["frame_index"]) for row in vehicle_states if row["is_visible_but_unboxed"].lower() == "true"}
        bbox_frames = {int(row["frame_index"]) for row in vehicle_states if row["reference_bbox_available"].lower() == "true" and int(row["frame_index"]) in visible_frames}
        depth_frames = {frame for frame in bbox_frames if (Path(scene_config["scenes"][scene]["paths"]["depth_dir"]) / f"{frame:06d}_depth.npy").is_file()}
        overlap_frames = {frame for frame in visible_frames if len(visible_by_scene_frame[(scene, frame)]) > 1}
        max_visible = max((len(visible_by_scene_frame[(scene, frame)]) for frame in visible_frames), default=0)
        sar_start, sar_end = lifecycle_sar_bounds(int(vehicle["entry_frame"]), int(vehicle["exit_frame"]))
        sample_frames = sorted(set(int(value) for value in np.linspace(sar_start, sar_end, min(int(config["inventory_shell_sample_count"]), sar_end - sar_start + 1))))
        valid_fractions: list[float] = []
        mapping_statuses: set[str] = set()
        for sar_frame in sample_frames:
            time_row = time_index[(scene, sar_frame)]
            left_frame = int(time_row["optical_left_frame"])
            right_frame = int(time_row["optical_right_frame"])
            ratio = float(time_row["optical_interpolation_ratio"])
            bbox, _, bbox_multiplier = interpolate_bbox(state_index, scene, vehicle_id, left_frame, right_frame, ratio)
            if bbox is None:
                valid_fractions.append(0.0)
                continue
            left_state = state_index[(scene, vehicle_id, left_frame)]
            right_state = state_index[(scene, vehicle_id, right_frame)]
            visibility = combined_visibility(left_state, right_state)
            depth_path = Path(scene_config["scenes"][scene]["paths"]["depth_dir"]) / f"{left_frame:06d}_depth.npy"
            depth_median, _ = sample_depth(depth_path, bbox)
            geometry = build_condition_geometry(scene, bbox, depth_median, calibration, visibility, bbox_multiplier, config["uncertainty"])
            shell = condition_shell(geometry)
            valid_fractions.append(float(np.count_nonzero(shell & valid_mask) / max(np.count_nonzero(shell), 1)))
            mapping_statuses.add(str(geometry["mapping_status"]))
        calibration_independence = (
            "CALIBRATION_VEHICLE_NOT_INDEPENDENT"
            if vehicle_id == calibration["calibration_vehicle_id"]
            else "INDEPENDENT_TARGET_FROM_PV004_CALIBRATION"
            if scene == calibration["scene"]
            else "CROSS_SCENE_PROXY_TARGET_NOT_IN_CALIBRATION"
        )
        row: dict[str, Any] = {
            "scene": scene,
            "canonical_vehicle_id": vehicle_id,
            "optical_first_visible": min(visible_frames),
            "optical_last_visible": max(visible_frames),
            "visible_duration_optical_frames": len(visible_frames),
            "full_visible_duration": len(full_frames),
            "partial_visible_duration": len(partial_frames),
            "fully_occluded_duration": len(occluded_frames),
            "visible_but_unboxed_duration": len(unboxed_frames),
            "entry_frame": vehicle["entry_frame"],
            "entry_location": vehicle["entry_location"],
            "entry_direction": vehicle["entry_direction"],
            "exit_frame": vehicle["exit_frame"],
            "exit_location": vehicle["exit_location"],
            "exit_direction": vehicle["exit_direction"],
            "max_simultaneously_visible_vehicles": max_visible,
            "overlap_optical_frame_ranges": compact_ranges(overlap_frames),
            "vehicle_color": vehicle["vehicle_color"],
            "vehicle_type_or_shape": vehicle["vehicle_type_or_shape"],
            "scale_trend": vehicle["scale_trend"],
            "dominant_apparent_motion": vehicle["dominant_motion_direction"],
            "optical_bbox_available_fraction": len(bbox_frames) / max(len(visible_frames), 1),
            "depth_proxy_available_fraction": len(depth_frames) / max(len(bbox_frames), 1),
            "calibration_independence": calibration_independence,
            "mapping_uncertainty": ";".join(sorted(mapping_statuses)),
            "mapped_sar_lifecycle_start": sar_start,
            "mapped_sar_lifecycle_end": sar_end,
            "mapped_sar_pre_roll_start": max(0, sar_start - int(config["pre_roll_sar_frames"])),
            "mapped_sar_post_roll_end": min(765, sar_end + int(config["post_roll_sar_frames"])),
            "sampled_shell_valid_fraction_mean": float(np.mean(valid_fractions)) if valid_fractions else 0.0,
            "sampled_shell_valid_fraction_min": float(np.min(valid_fractions)) if valid_fractions else 0.0,
            "suitable_clear_mechanism_discovery": "false",
            "suitable_cross_scene_replay": "false",
            "suitable_entry_exit": "false",
            "suitable_multivehicle_occlusion_stress": "false",
            "selection_status": "INVENTORIED_NOT_SELECTED",
            "selection_reason": "pending target-reference-free direct review",
            "target_sar_reference_used_for_inventory_or_selection": "false",
        }
        roles = candidate_roles(row)
        row["suitable_clear_mechanism_discovery"] = str("MECHANISM_DISCOVERY_CANDIDATE" in roles).lower()
        row["suitable_cross_scene_replay"] = str("CROSS_SCENE_FROZEN_REPLAY_CANDIDATE" in roles).lower()
        row["suitable_entry_exit"] = str("ENTRY_EXIT_LIFECYCLE_CANDIDATE" in roles).lower()
        row["suitable_multivehicle_occlusion_stress"] = str("MULTI_VEHICLE_OR_OCCLUSION_STRESS_CANDIDATE" in roles).lower()
        row["candidate_roles"] = ";".join(roles)
        selected = selected_by_vehicle.get(vehicle_id)
        if selected is not None:
            row["selection_status"] = "SELECTED_" + ";".join(selected["roles"])
            row["selection_reason"] = selected["selection_reason"]
        elif roles:
            row["selection_status"] = "DIRECTLY_REVIEWED_NOT_SELECTED"
            row["selection_reason"] = "retained in complete inventory; selected set covers required roles with clearer separation or stronger prescribed stress"
        inventory.append(row)
    write_csv(INVENTORY_PATH, inventory)
    output_root = Path(config["output_root"])
    review_rows: list[dict[str, Any]] = []
    for row in inventory:
        if not row["candidate_roles"]:
            continue
        scene = row["scene"]
        path = make_review(
            row,
            registry_by_id[row["canonical_vehicle_id"]],
            scene_config["scenes"][scene]["paths"],
            state_index,
            time_index,
            calibration,
            config["uncertainty"],
            output_root,
            int(config["review_frame_count"]),
        )
        selected = selected_by_vehicle.get(row["canonical_vehicle_id"])
        review_rows.append({
            "canonical_vehicle_id": row["canonical_vehicle_id"],
            "scene": scene,
            "candidate_roles": row["candidate_roles"],
            "artifact_path": str(path),
            "artifact_sha256": sha256_file(path),
            "contains_target_sar_reference": "false",
            "selection_status": "selected" if selected is not None else "directly_reviewed_not_selected",
            "direct_review_finding": selected["direct_review_finding"] if selected is not None else "inventory-level blind review completed; not selected for the bounded four-role run",
        })
    write_csv(REVIEW_MANIFEST_PATH, review_rows)
    selection_rows = []
    for case in config["selected_cases"]:
        inventory_row = next(row for row in inventory if row["canonical_vehicle_id"] == case["vehicle_id"])
        for role in case["roles"]:
            selection_rows.append({
                "case_id": case["case_id"],
                "role": role,
                "scene": case["scene"],
                "canonical_vehicle_id": case["vehicle_id"],
                "optical_entry_frame": inventory_row["entry_frame"],
                "optical_exit_frame": inventory_row["exit_frame"],
                "mapped_sar_lifecycle_start": inventory_row["mapped_sar_lifecycle_start"],
                "mapped_sar_lifecycle_end": inventory_row["mapped_sar_lifecycle_end"],
                "pre_roll_start": inventory_row["mapped_sar_pre_roll_start"],
                "post_roll_end": inventory_row["mapped_sar_post_roll_end"],
                "selection_basis": case["selection_reason"],
                "direct_review_finding": case["direct_review_finding"],
                "target_sar_reference_used_for_selection": "false",
                "selection_frozen_before_inference": "true",
            })
    write_csv(SELECTION_PATH, selection_rows)
    p0_rows = read_csv(sources["p0_asset_manifest"])
    scene_input_hashes = {}
    for scene in SCENES:
        payload = json.dumps(
            [row for row in p0_rows if row.get("scene") == scene],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        scene_input_hashes[scene] = hashlib.sha256(payload).hexdigest()
    summary = {
        "version": config["version"],
        "git": git_state,
        "config_sha256": sha256_file(config_path),
        "source_hashes": {name: sha256_file(path) for name, path in sources.items()},
        "scene_input_manifest_hashes": scene_input_hashes,
        "inventory_rows": len(inventory),
        "scene_counts": dict(Counter(row["scene"] for row in inventory)),
        "candidate_role_counts": dict(Counter(role for row in inventory for role in row["candidate_roles"].split(";") if role)),
        "review_artifact_count": len(review_rows),
        "selected_case_count": len(config["selected_cases"]),
        "selected_role_count": len(selection_rows),
        "selected_roles_sha256": sha256_file(SELECTION_PATH),
        "target_sar_reference_used": False,
        "old_work_runtime_dependency": False,
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
