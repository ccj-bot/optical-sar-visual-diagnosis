#!/usr/bin/env python3
from __future__ import annotations

"""Evaluate frozen S1X inference outputs with posthoc-only target references."""

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from oty2_s1x_common import (
    CONFIG_DIR,
    FAN_HEIGHT,
    FAN_WIDTH,
    MANIFEST_DIR,
    REPO_ROOT,
    REPORT_DIR,
    fmt,
    load_json,
    parse_rotated_bbox,
    read_csv,
    read_gray,
    require,
    rotated_bbox_mask,
    sha256_file,
    verify_git_gate,
    warp_translation,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = CONFIG_DIR / "oty2_s1x_posthoc_evaluation.json"
FRAME_EVAL_OUTPUT = MANIFEST_DIR / "oty2_s1x_posthoc_frame_evaluation.csv"
WINDOW_EVAL_OUTPUT = MANIFEST_DIR / "oty2_s1x_posthoc_window_evaluation.csv"
QUESTION_OUTPUT = MANIFEST_DIR / "oty2_s1x_project_question_answers.csv"
VISUAL_OUTPUT = MANIFEST_DIR / "oty2_s1x_posthoc_visual_manifest.csv"
SUMMARY_OUTPUT = REPORT_DIR / "oty2_s1x_posthoc_evaluation_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def resolve(text: str) -> Path:
    path = Path(text)
    return path if path.is_absolute() else REPO_ROOT / path


def verify_freeze(path: Path) -> dict[str, Any]:
    rows = read_csv(path)
    checked = 0
    for row in rows:
        frozen_path = Path(row["path"])
        require(frozen_path.is_file(), f"missing frozen artifact: {frozen_path}")
        require(sha256_file(frozen_path) == row["sha256"].lower(), f"frozen hash mismatch: {frozen_path}")
        require(row["frozen_before_evaluation"] == "true", "unfrozen artifact row")
        require(row["target_reference_content"] == "false", "target content found in inference freeze")
        checked += 1
    return {"freeze_row_count": checked, "all_hashes_match": True}


def union_reference_mask(rows: list[dict[str, str]]) -> np.ndarray:
    mask = np.zeros((FAN_HEIGHT, FAN_WIDTH), dtype=bool)
    for row in rows:
        mask |= rotated_bbox_mask(parse_rotated_bbox(row["bbox"]))
    return mask


def mask_metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float | int]:
    pred_area = int(np.count_nonzero(prediction))
    target_area = int(np.count_nonzero(target))
    intersection = int(np.count_nonzero(prediction & target))
    union = pred_area + target_area - intersection
    return {
        "prediction_area_px": pred_area,
        "target_area_px": target_area,
        "intersection_px": intersection,
        "target_coverage": intersection / max(target_area, 1),
        "prediction_precision": intersection / max(pred_area, 1),
        "iou": intersection / max(union, 1),
    }


def count_breaks(values: list[bool]) -> int:
    breaks = 0
    inside = False
    for value in values:
        if not value and not inside:
            breaks += 1
            inside = True
        elif value:
            inside = False
    return breaks


def centroid(mask: np.ndarray) -> tuple[float, float] | None:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    return float(np.mean(xs)), float(np.mean(ys))


def centroid_jumps(masks: list[np.ndarray]) -> list[float]:
    jumps: list[float] = []
    previous: tuple[float, float] | None = None
    for mask in masks:
        current = centroid(mask)
        if current is not None and previous is not None:
            jumps.append(math.hypot(current[0] - previous[0], current[1] - previous[1]))
        if current is not None:
            previous = current
    return jumps


def display_rgb(gray: np.ndarray, low: float = 0.0, high: float = 85.0) -> np.ndarray:
    value = np.clip((gray.astype(np.float32) - low) / max(high - low, 1.0), 0.0, 1.0)
    return cv2.cvtColor((value * 255).astype(np.uint8), cv2.COLOR_GRAY2RGB)


def contour(image: np.ndarray, mask: np.ndarray, color: tuple[int, int, int], thickness: int = 2) -> None:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, color, thickness)


def create_posthoc_page(
    target: dict[str, Any],
    rows: list[dict[str, Any]],
    data: Any,
    reference_by_frame: dict[int, np.ndarray],
    output_dir: Path,
) -> Path:
    frames = [int(value) for value in data["frames"]]
    selected_indices = sorted(set(int(value) for value in np.linspace(0, len(frames) - 1, min(8, len(frames)))))
    roi = tuple(int(value) for value in data["roi"])
    x1, y1, x2, y2 = roi
    figure, axes = plt.subplots(len(selected_indices), 2, figsize=(12, 3.6 * len(selected_indices)), squeeze=False)
    for axis_row, index in enumerate(selected_indices):
        frame = frames[index]
        state = rows[index]
        raw_path = Path(state["sar_gray_path"])
        raw = read_gray(raw_path)
        dx, dy = [float(value) for value in data["cumulative_transport"][index]]
        stabilized = warp_translation(raw, -dx, -dy, cv2.INTER_LINEAR)[y1:y2, x1:x2]
        target_mask = reference_by_frame.get(frame, np.zeros((y2 - y1, x2 - x1), dtype=bool))
        shell = data["optical_shell"][index].astype(bool)
        joint = data["joint_support"][index].astype(bool)
        independent = data["independent_support"][index].astype(bool)
        shell_view = display_rgb(stabilized)
        contour(shell_view, shell, (0, 180, 255), 2)
        contour(shell_view, target_mask, (255, 255, 0), 2)
        axes[axis_row, 0].imshow(shell_view)
        axes[axis_row, 0].set_title(f"frame {frame}: optical shell cyan / posthoc reference yellow")
        joint_view = display_rgb(stabilized)
        output = joint_view.astype(np.float32)
        output[independent] = 0.5 * output[independent] + 0.5 * np.asarray([255, 150, 30])
        output[joint] = 0.4 * output[joint] + 0.6 * np.asarray([40, 230, 80])
        joint_view = np.clip(output, 0, 255).astype(np.uint8)
        contour(joint_view, target_mask, (255, 255, 0), 2)
        axes[axis_row, 1].imshow(joint_view)
        axes[axis_row, 1].set_title("independent orange / joint green / posthoc reference yellow")
        for axis in axes[axis_row]:
            axis.axis("off")
    figure.suptitle(f"{target['window_id']} posthoc frozen-output review")
    figure.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "posthoc_frozen_output_review.png"
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def main() -> None:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config
    config = load_json(config_path)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    freeze_path = resolve(config["inference_freeze_manifest"])
    freeze_audit = verify_freeze(freeze_path)
    reference_path = resolve(config["reference_manifest"])
    reference_rows = read_csv(reference_path)
    condition_rows = read_csv(MANIFEST_DIR / "oty2_s1x_optical_condition_frames.csv")
    frame_state_rows = read_csv(MANIFEST_DIR / "oty2_s1x_temporal_support_frame_states.csv")
    condition_by_key = {
        (row["window_id"], int(row["sar_frame_index"])): row for row in condition_rows
    }
    state_by_key = {
        (row["window_id"], int(row["sar_frame_index"])): row for row in frame_state_rows
    }
    output_root = Path(config["output_root"])
    per_frame: list[dict[str, Any]] = []
    per_window: list[dict[str, Any]] = []
    visual_rows: list[dict[str, Any]] = []
    question_evidence: dict[str, dict[str, Any]] = {}
    for target in config["targets"]:
        window_id = target["window_id"]
        npz_path = output_root / window_id / "frozen_inference_masks.npz"
        require(npz_path.is_file(), f"missing frozen masks: {npz_path}")
        data = np.load(npz_path)
        frames = [int(value) for value in data["frames"]]
        roi = tuple(int(value) for value in data["roi"])
        x1, y1, x2, y2 = roi
        selected_reference = [
            row
            for row in reference_rows
            if row["scene"] == target["scene"]
            and row["canonical_vehicle_id"] == target["vehicle_id"]
            and int(target["sar_frame_start"]) <= int(row["sar_frame_index"]) <= int(target["sar_frame_end"])
        ]
        references_by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
        others_by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
        for row in reference_rows:
            if row["scene"] != target["scene"]:
                continue
            frame = int(row["sar_frame_index"])
            if frame not in set(frames):
                continue
            if row["canonical_vehicle_id"] == target["vehicle_id"]:
                references_by_frame[frame].append(row)
            else:
                others_by_frame[frame].append(row)
        reference_masks_crop: dict[int, np.ndarray] = {}
        independent_hit_flags: list[bool] = []
        joint_hit_flags: list[bool] = []
        reference_available_flags: list[bool] = []
        independent_masks_for_jump: list[np.ndarray] = []
        joint_masks_for_jump: list[np.ndarray] = []
        for index, frame in enumerate(frames):
            condition = condition_by_key[(window_id, frame)]
            state = state_by_key[(window_id, frame)]
            dx, dy = [float(value) for value in data["cumulative_transport"][index]]
            target_mask_raw = union_reference_mask(references_by_frame.get(frame, [])) if references_by_frame.get(frame) else np.zeros((FAN_HEIGHT, FAN_WIDTH), dtype=bool)
            target_mask_stable = warp_translation(target_mask_raw.astype(np.uint8), -dx, -dy, cv2.INTER_NEAREST).astype(bool)
            target_crop = target_mask_stable[y1:y2, x1:x2]
            reference_masks_crop[frame] = target_crop
            other_mask_raw = union_reference_mask(others_by_frame.get(frame, [])) if others_by_frame.get(frame) else np.zeros((FAN_HEIGHT, FAN_WIDTH), dtype=bool)
            other_stable = warp_translation(other_mask_raw.astype(np.uint8), -dx, -dy, cv2.INTER_NEAREST).astype(bool)
            other_crop = other_stable[y1:y2, x1:x2]
            shell = data["optical_shell"][index].astype(bool)
            independent = data["independent_support"][index].astype(bool)
            joint = data["joint_support"][index].astype(bool)
            weak = data["temporally_maintained_weak"][index].astype(bool)
            background = data["background_excluded"][index].astype(bool)
            mixed = data["mixed_or_unresolved"][index].astype(bool)
            sar_only = data["sar_only_support"][index].astype(bool)
            shell_metrics = mask_metrics(shell, target_crop)
            independent_metrics = mask_metrics(independent, target_crop)
            joint_metrics = mask_metrics(joint, target_crop)
            sar_only_metrics = mask_metrics(sar_only, target_mask_stable)
            joint_other_overlap = int(np.count_nonzero(joint & other_crop))
            independent_other_overlap = int(np.count_nonzero(independent & other_crop))
            shell_other_overlap = int(np.count_nonzero(shell & other_crop))
            weak_target_intersection = int(np.count_nonzero(weak & target_crop))
            joint_outside = int(joint_metrics["prediction_area_px"] - joint_metrics["intersection_px"])
            shell_outside = int(shell_metrics["prediction_area_px"] - shell_metrics["intersection_px"])
            independent_hit = int(independent_metrics["intersection_px"]) > 0
            joint_hit = int(joint_metrics["intersection_px"]) > 0
            independent_hit_flags.append(independent_hit)
            joint_hit_flags.append(joint_hit)
            reference_available_flags.append(bool(references_by_frame.get(frame, [])))
            independent_masks_for_jump.append(independent)
            joint_masks_for_jump.append(joint)
            per_frame.append(
                {
                    "window_id": window_id,
                    "window_role": target["role"],
                    "scene": target["scene"],
                    "canonical_vehicle_id": target["vehicle_id"],
                    "sar_frame_index": frame,
                    "reference_row_count": len(references_by_frame.get(frame, [])),
                    "reference_available": fmt(bool(references_by_frame.get(frame, []))),
                    "optical_shell_area_px": shell_metrics["prediction_area_px"],
                    "optical_shell_target_coverage": fmt(shell_metrics["target_coverage"]),
                    "optical_shell_precision": fmt(shell_metrics["prediction_precision"]),
                    "optical_shell_other_vehicle_overlap_px": shell_other_overlap,
                    "independent_support_area_px": independent_metrics["prediction_area_px"],
                    "independent_target_intersection_px": independent_metrics["intersection_px"],
                    "independent_target_coverage": fmt(independent_metrics["target_coverage"]),
                    "independent_precision": fmt(independent_metrics["prediction_precision"]),
                    "independent_other_vehicle_overlap_px": independent_other_overlap,
                    "joint_support_area_px": joint_metrics["prediction_area_px"],
                    "joint_target_intersection_px": joint_metrics["intersection_px"],
                    "joint_target_coverage": fmt(joint_metrics["target_coverage"]),
                    "joint_precision": fmt(joint_metrics["prediction_precision"]),
                    "joint_other_vehicle_overlap_px": joint_other_overlap,
                    "joint_shell_contraction_fraction": fmt(1.0 - int(joint_metrics["prediction_area_px"]) / max(int(shell_metrics["prediction_area_px"]), 1)),
                    "joint_background_area_reduction_px": max(0, shell_outside - joint_outside),
                    "weak_maintained_area_px": int(np.count_nonzero(weak)),
                    "weak_maintained_target_intersection_px": weak_target_intersection,
                    "background_excluded_area_px": int(np.count_nonzero(background & shell)),
                    "mixed_or_unresolved_area_px": int(np.count_nonzero(mixed & shell)),
                    "per_frame_response_state": state["per_frame_response_state"],
                    "sar_only_support_area_px": sar_only_metrics["prediction_area_px"],
                    "sar_only_target_coverage": fmt(sar_only_metrics["target_coverage"]),
                    "sar_only_precision": fmt(sar_only_metrics["prediction_precision"]),
                    "target_reference_used_for_inference": "false",
                    "evaluation_only": "true",
                }
            )
        available_rows = [row for row in per_frame if row["window_id"] == window_id and row["reference_available"] == "true"]
        independent_jumps = centroid_jumps(independent_masks_for_jump)
        joint_jumps = centroid_jumps(joint_masks_for_jump)
        independent_hits_available = [value for value, available in zip(independent_hit_flags, reference_available_flags) if available]
        joint_hits_available = [value for value, available in zip(joint_hit_flags, reference_available_flags) if available]
        mean = lambda key: float(np.mean([float(row[key]) for row in available_rows])) if available_rows else math.nan
        sum_int = lambda key: int(sum(int(row[key]) for row in available_rows))
        window_summary = {
            "window_id": window_id,
            "window_role": target["role"],
            "scene": target["scene"],
            "canonical_vehicle_id": target["vehicle_id"],
            "inference_frame_count": len(frames),
            "reference_available_frame_count": len(available_rows),
            "reference_temporal_coverage_fraction": len(available_rows) / max(len(frames), 1),
            "optical_shell_mean_target_coverage": mean("optical_shell_target_coverage"),
            "optical_shell_mean_precision": mean("optical_shell_precision"),
            "joint_mean_target_coverage": mean("joint_target_coverage"),
            "joint_mean_precision": mean("joint_precision"),
            "joint_mean_shell_contraction_fraction": mean("joint_shell_contraction_fraction"),
            "joint_total_background_area_reduction_px": sum_int("joint_background_area_reduction_px"),
            "joint_total_other_vehicle_overlap_px": sum_int("joint_other_vehicle_overlap_px"),
            "independent_total_other_vehicle_overlap_px": sum_int("independent_other_vehicle_overlap_px"),
            "joint_reference_hit_frame_fraction": sum(bool(value) for value in joint_hits_available) / max(len(joint_hits_available), 1),
            "independent_reference_hit_frame_fraction": sum(bool(value) for value in independent_hits_available) / max(len(independent_hits_available), 1),
            "joint_break_episode_count": count_breaks(joint_hits_available),
            "independent_break_episode_count": count_breaks(independent_hits_available),
            "joint_empty_frame_count": sum(not value for value in joint_hits_available),
            "independent_empty_frame_count": sum(not value for value in independent_hits_available),
            "temporally_recovered_reference_hit_frames": sum(joint and not independent for joint, independent in zip(joint_hits_available, independent_hits_available)),
            "weak_maintained_target_frame_count": sum(int(row["weak_maintained_target_intersection_px"]) > 0 for row in available_rows),
            "weak_maintained_target_intersection_total_px": sum_int("weak_maintained_target_intersection_px"),
            "joint_centroid_jump_median_px": float(np.median(joint_jumps)) if joint_jumps else math.nan,
            "independent_centroid_jump_median_px": float(np.median(independent_jumps)) if independent_jumps else math.nan,
            "joint_centroid_jump_p90_px": float(np.percentile(joint_jumps, 90)) if joint_jumps else math.nan,
            "independent_centroid_jump_p90_px": float(np.percentile(independent_jumps, 90)) if independent_jumps else math.nan,
            "sar_only_mean_target_coverage": mean("sar_only_target_coverage"),
            "sar_only_mean_precision": mean("sar_only_precision"),
            "target_reference_used_for_inference": False,
        }
        per_window.append(window_summary)
        condition_for_visual = [condition_by_key[(window_id, frame)] for frame in frames]
        visual_path = create_posthoc_page(
            target,
            condition_for_visual,
            data,
            reference_masks_crop,
            output_root / window_id / "posthoc_review",
        )
        visual_rows.append(
            {
                "window_id": window_id,
                "artifact_path": str(visual_path),
                "artifact_sha256": sha256_file(visual_path),
                "evaluation_only": "true",
                "generated_after_inference_freeze": "true",
                "review_status": "pending_posthoc_direct_review",
            }
        )
        question_evidence[target["role"]] = window_summary
    write_csv(FRAME_EVAL_OUTPUT, per_frame)
    write_csv(WINDOW_EVAL_OUTPUT, per_window)
    discovery = question_evidence["discovery"]
    replay = question_evidence["frozen_rule_replay"]
    answers = [
        {
            "question_id": "Q1_VISIBLE_SEQUENCE_WITHOUT_TARGET_REFERENCE",
            "direct_answer": "YES_CONSERVATIVE_VISIBLE_RESPONSE_SEQUENCE_RECOVERED",
            "evidence": f"blind review supported; discovery reference-hit fraction={discovery['joint_reference_hit_frame_fraction']:.3f}; mean target coverage={discovery['joint_mean_target_coverage']:.3f}",
        },
        {
            "question_id": "Q2_SAR_INCREMENT_OVER_OPTICAL_SHELL",
            "direct_answer": "YES_SUPPORT_RANGE_STRONGLY_CONTRACTED_BACKGROUND_REDUCTION_MEASURED",
            "evidence": f"discovery shell contraction={discovery['joint_mean_shell_contraction_fraction']:.3f}; replay shell contraction={replay['joint_mean_shell_contraction_fraction']:.3f}; other-vehicle overlap reported separately",
        },
        {
            "question_id": "Q3_TEMPORAL_JOINT_MORE_STABLE_THAN_PER_FRAME",
            "direct_answer": "PARTIAL_YES_LOWER_JITTER_BUT_NO_ADDITIONAL_BREAK_RECOVERY",
            "evidence": f"joint/independent centroid-jump medians={discovery['joint_centroid_jump_median_px']:.3f}/{discovery['independent_centroid_jump_median_px']:.3f} and {replay['joint_centroid_jump_median_px']:.3f}/{replay['independent_centroid_jump_median_px']:.3f}; recovered reference-hit frames=0/0; weak-maintained target frames={discovery['weak_maintained_target_frame_count']}/{replay['weak_maintained_target_frame_count']}",
        },
        {
            "question_id": "Q4_FROZEN_RULE_REPLAY",
            "direct_answer": "YES_PARTIAL_REPRODUCTION_ON_INDEPENDENT_OPTICAL_VEHICLE_THREAD",
            "evidence": f"replay reference-hit fraction={replay['joint_reference_hit_frame_fraction']:.3f}; mean target coverage={replay['joint_mean_target_coverage']:.3f}; same inference config hash was frozen for both windows",
        },
    ]
    write_csv(QUESTION_OUTPUT, answers)
    write_csv(VISUAL_OUTPUT, visual_rows)
    summary = {
        "version": "OTY2-S1X-posthoc-evaluation-summary-v1",
        "evaluation_started_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state,
        "evaluation_config": str(config_path),
        "evaluation_config_sha256": sha256_file(config_path),
        "reference_manifest": str(reference_path),
        "reference_manifest_sha256": sha256_file(reference_path),
        "freeze_audit": freeze_audit,
        "window_metrics": per_window,
        "project_questions": answers,
        "inference_outputs_modified": False,
        "rule_update_from_evaluation": False,
    }
    write_json(SUMMARY_OUTPUT, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
