#!/usr/bin/env python3
from __future__ import annotations

"""Replay S1X inference into a separate Git-outside directory and compare outputs."""

import json
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np

from oty2_s1x_common import CONFIG_DIR, MANIFEST_DIR, REPO_ROOT, REPORT_DIR, load_json, read_csv, sha256_file, verify_git_gate, write_json
from run_oty2_s1x_joint_temporal_support import process_window


CONFIG_PATH = CONFIG_DIR / "oty2_s1x_joint_temporal_support.json"
REPORT_PATH = REPORT_DIR / "oty2_s1x_fixed_input_replay_summary_20260717.json"
REPLAY_ROOT = Path(r"D:\profile\research\workspace\output\oty2_s1x_20260717_replay_check")


def normalized_row(row: Mapping[str, Any], drop: set[str] | None = None) -> dict[str, str]:
    drop = drop or set()
    return {key: str(value) for key, value in row.items() if key not in drop}


def compare_npz(left_path: Path, right_path: Path) -> dict[str, Any]:
    left = np.load(left_path)
    right = np.load(right_path)
    keys_equal = set(left.files) == set(right.files)
    mismatches: list[str] = []
    if keys_equal:
        for key in left.files:
            if not np.array_equal(left[key], right[key], equal_nan=True):
                mismatches.append(key)
    return {
        "keys_equal": keys_equal,
        "array_mismatches": mismatches,
        "all_arrays_equal": keys_equal and not mismatches,
        "frozen_sha256": sha256_file(left_path),
        "replay_sha256": sha256_file(right_path),
        "file_sha_equal": sha256_file(left_path) == sha256_file(right_path),
    }


def compare_image_pixels(left_path: Path, right_path: Path) -> bool:
    left = cv2.imread(str(left_path), cv2.IMREAD_UNCHANGED)
    right = cv2.imread(str(right_path), cv2.IMREAD_UNCHANGED)
    return left is not None and right is not None and np.array_equal(left, right)


def main() -> None:
    config = load_json(CONFIG_PATH)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    condition_path = REPO_ROOT / config["optical_condition_frames"]
    condition_rows = read_csv(condition_path)
    expected_frame_rows = read_csv(MANIFEST_DIR / "oty2_s1x_temporal_support_frame_states.csv")
    expected_sar_objects = read_csv(MANIFEST_DIR / "oty2_s1x_sar_only_temporal_objects.csv")
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in condition_rows:
        if row["window_id"] in set(config["windows"]):
            grouped.setdefault(row["window_id"], []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row["sar_frame_index"]))
    replay_results: list[dict[str, Any]] = []
    all_frame_rows: list[dict[str, Any]] = []
    all_sar_objects: list[dict[str, Any]] = []
    for window_id in config["windows"]:
        result = process_window(config, grouped[window_id], REPLAY_ROOT)
        all_frame_rows.extend(result["frame_rows"])
        all_sar_objects.extend(result["sar_only_objects"])
        frozen_dir = Path(config["output_root"]) / window_id
        replay_dir = REPLAY_ROOT / window_id
        npz_comparison = compare_npz(frozen_dir / "frozen_inference_masks.npz", replay_dir / "frozen_inference_masks.npz")
        frozen_reviews = sorted((frozen_dir / "blind_review").glob("*.png"))
        replay_reviews = sorted((replay_dir / "blind_review").glob("*.png"))
        review_names_equal = [path.name for path in frozen_reviews] == [path.name for path in replay_reviews]
        pixel_equal = review_names_equal and all(
            compare_image_pixels(left, right) for left, right in zip(frozen_reviews, replay_reviews)
        )
        replay_results.append(
            {
                "window_id": window_id,
                "npz": npz_comparison,
                "review_names_equal": review_names_equal,
                "review_pixels_equal": pixel_equal,
            }
        )
    expected_frames_normalized = sorted(
        [normalized_row(row, {"frozen_npz_path"}) for row in expected_frame_rows],
        key=lambda row: (row["window_id"], int(row["sar_frame_index"])),
    )
    replay_frames_normalized = sorted(
        [normalized_row(row, {"frozen_npz_path"}) for row in all_frame_rows],
        key=lambda row: (row["window_id"], int(row["sar_frame_index"])),
    )
    expected_objects_normalized = sorted(
        [normalized_row(row) for row in expected_sar_objects],
        key=lambda row: (row.get("window_id", ""), row.get("object_id", "")),
    )
    replay_objects_normalized = sorted(
        [normalized_row(row) for row in all_sar_objects],
        key=lambda row: (row.get("window_id", ""), row.get("object_id", "")),
    )
    summary = {
        "version": "OTY2-S1X-fixed-input-replay-v1",
        "git": git_state,
        "config_sha256": sha256_file(CONFIG_PATH),
        "condition_sha256": sha256_file(condition_path),
        "replay_root": str(REPLAY_ROOT),
        "windows": replay_results,
        "frame_rows_equal_excluding_output_path": expected_frames_normalized == replay_frames_normalized,
        "sar_only_object_rows_equal": expected_objects_normalized == replay_objects_normalized,
    }
    summary["status"] = "PASS" if (
        all(row["npz"]["all_arrays_equal"] and row["review_pixels_equal"] for row in replay_results)
        and summary["frame_rows_equal_excluding_output_path"]
        and summary["sar_only_object_rows_equal"]
    ) else "FAIL"
    write_json(REPORT_PATH, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
