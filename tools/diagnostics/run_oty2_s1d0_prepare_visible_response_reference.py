#!/usr/bin/env python3
from __future__ import annotations

"""Create a post-freeze, prediction-blind visible-response review queue."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from oty2_s1d0_common import (
    REPO_ROOT,
    load_json,
    read_csv,
    require,
    sha256_file,
    verify_git_gate,
    warp_translation,
    write_csv,
    write_json,
)


CONFIG_PATH = REPO_ROOT / "configs" / "oty2" / "oty2_s1d0_evaluation.json"
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
CONDITION_PATH = MANIFEST_DIR / "oty2_s1d0_lifecycle_conditions.csv"
QUEUE_PATH = MANIFEST_DIR / "oty2_s1d0_visible_response_reference_review_queue.csv"
SUMMARY_PATH = REPORT_DIR / "oty2_s1d0_visible_response_reference_queue_summary_20260717.json"


def verify_freeze(path: Path) -> dict[str, Any]:
    rows = read_csv(path)
    require(rows, "empty S1D0 inference freeze")
    for row in rows:
        artifact = Path(row["path"])
        require(artifact.is_file(), f"missing frozen artifact: {artifact}")
        require(sha256_file(artifact) == row["sha256"].lower(), f"frozen hash mismatch: {artifact}")
        require(row["frozen_before_visible_response_review"] == "true", "unfrozen inference artifact")
        require(row["target_reference_content"] == "false", "target content in inference freeze")
    return {"artifact_count": len(rows), "all_hashes_match": True, "manifest_sha256": sha256_file(path)}


def display_rgb(gray: np.ndarray, low: float = 0.0, high: float = 85.0) -> np.ndarray:
    value = np.clip((gray.astype(np.float32) - low) / max(high - low, 1.0), 0.0, 1.0)
    return cv2.cvtColor((value * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def draw_review_image(gray: np.ndarray, shell: np.ndarray, frame: int, case_id: str) -> np.ndarray:
    image = display_rgb(gray)
    contours, _ = cv2.findContours(shell.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, (255, 190, 0), 2)
    height, width = image.shape[:2]
    for x in range(0, width, 100):
        cv2.line(image, (x, 0), (x, height - 1), (80, 80, 80), 1)
        cv2.putText(image, str(x), (x + 3, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1, cv2.LINE_AA)
    for y in range(0, height, 100):
        cv2.line(image, (0, y), (width - 1, y), (80, 80, 80), 1)
        cv2.putText(image, str(y), (3, max(18, y + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1, cv2.LINE_AA)
    cv2.putText(
        image,
        f"{case_id} SAR {frame} | stabilized ROI | shell cyan | no inference/GT",
        (15, height - 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return image


def main() -> None:
    config = load_json(CONFIG_PATH)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    freeze_path = REPO_ROOT / config["inference_freeze_manifest"]
    freeze_audit = verify_freeze(freeze_path)
    output_root = Path(config["output_root"])
    review_root = Path(config["reference_review_output"])
    review_root.mkdir(parents=True, exist_ok=True)
    condition_rows = read_csv(CONDITION_PATH)
    by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in condition_rows:
        if row["is_target_identity"] == "true":
            by_case[row["case_id"]].append(row)

    queue: list[dict[str, Any]] = []
    for case_id in config["reference_cases"]:
        rows = sorted(by_case[case_id], key=lambda row: int(row["sar_frame_index"]))
        active_indices = [
            index
            for index, row in enumerate(rows)
            if row["optical_lifecycle_state"] not in {"ABSENT", "CLOSED"}
        ]
        require(active_indices, f"no active lifecycle frames for {case_id}")
        count = min(int(config["reference_frame_count_per_case"]), len(active_indices))
        selected_positions = sorted(
            set(int(value) for value in np.linspace(0, len(active_indices) - 1, count))
        )
        selected_indices = [active_indices[position] for position in selected_positions]
        causal_path = output_root / case_id / "causal" / "dynamic_state_masks.npz"
        bidirectional_path = output_root / case_id / "bidirectional" / "dynamic_state_masks.npz"
        causal = np.load(causal_path)
        causal_frames = [int(value) for value in causal["frames"]]
        require(causal_frames == [int(row["sar_frame_index"]) for row in rows], f"frame mismatch: {case_id}")
        x1, y1, x2, y2 = [int(value) for value in causal["roi"]]
        case_review_dir = review_root / case_id
        case_review_dir.mkdir(parents=True, exist_ok=True)
        for index in selected_indices:
            row = rows[index]
            frame = int(row["sar_frame_index"])
            raw = cv2.imread(row["sar_gray_path"], cv2.IMREAD_GRAYSCALE)
            require(raw is not None, f"missing SAR frame: {row['sar_gray_path']}")
            dx, dy = [float(value) for value in causal["cumulative_transport"][index]]
            stable = warp_translation(raw, -dx, -dy, cv2.INTER_LINEAR)[y1:y2, x1:x2]
            shell = causal["geometric_shell"][index].astype(bool)
            review = draw_review_image(stable, shell, frame, case_id)
            review_path = case_review_dir / f"visible_response_reference_review_sar_{frame:06d}.png"
            require(cv2.imwrite(str(review_path), review), f"failed to write {review_path}")
            queue.append(
                {
                    "case_id": case_id,
                    "scene": row["scene"],
                    "canonical_vehicle_id": row["target_canonical_vehicle_id"],
                    "sar_frame_index": frame,
                    "optical_lifecycle_state": row["optical_lifecycle_state"],
                    "roi_xyxy": json.dumps([x1, y1, x2, y2], separators=(",", ":")),
                    "review_coordinate_system": "stabilized_roi_xy",
                    "review_artifact_path": str(review_path),
                    "review_artifact_sha256": sha256_file(review_path),
                    "inference_freeze_manifest_sha256_before_review": freeze_audit["manifest_sha256"],
                    "causal_npz_sha256_before_review": sha256_file(causal_path),
                    "bidirectional_npz_sha256_before_review": sha256_file(bidirectional_path),
                    "contains_inference_overlay": "false",
                    "contains_target_reference": "false",
                    "selection_basis": "uniform_active_lifecycle_sampling_after_inference_freeze",
                    "review_status": "pending_direct_visible_response_review",
                }
            )
    write_csv(QUEUE_PATH, queue)
    summary = {
        "version": "OTY2-S1D0-visible-response-reference-queue-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state,
        "freeze_audit": freeze_audit,
        "review_frame_count": len(queue),
        "case_counts": {case_id: sum(row["case_id"] == case_id for row in queue) for case_id in config["reference_cases"]},
        "target_reference_used_for_sampling": False,
        "inference_overlay_visible_to_reviewer": False,
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
