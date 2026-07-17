#!/usr/bin/env python3
from __future__ import annotations

"""Evaluate frozen S1D0 outputs against a small direct visible-response reference."""

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

from oty2_s1d0_common import (
    FAN_HEIGHT,
    FAN_WIDTH,
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
FRAME_OUTPUT = MANIFEST_DIR / "oty2_s1d0_visible_response_frame_evaluation.csv"
CASE_OUTPUT = MANIFEST_DIR / "oty2_s1d0_case_evaluation.csv"
STAGE_OUTPUT = MANIFEST_DIR / "oty2_s1d0_stage_conclusions.csv"
QUESTION_OUTPUT = MANIFEST_DIR / "oty2_s1d0_project_question_answers.csv"
VISUAL_OUTPUT = MANIFEST_DIR / "oty2_s1d0_posthoc_evaluation_visual_manifest.csv"
SUMMARY_OUTPUT = REPORT_DIR / "oty2_s1d0_postfreeze_evaluation_summary_20260717.json"


def fmt(value: float | int | bool | str) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return f"{value:.9f}"
    return str(value)


def resolve(text: str) -> Path:
    path = Path(text)
    return path if path.is_absolute() else REPO_ROOT / path


def verify_freeze(path: Path) -> dict[str, Any]:
    rows = read_csv(path)
    require(rows, "empty S1D0 inference freeze")
    for row in rows:
        artifact = Path(row["path"])
        require(artifact.is_file(), f"missing frozen artifact: {artifact}")
        require(sha256_file(artifact) == row["sha256"].lower(), f"frozen hash mismatch: {artifact}")
        require(row["frozen_before_visible_response_review"] == "true", "artifact not frozen before review")
        require(row["target_reference_content"] == "false", "target reference content in inference freeze")
    return {"row_count": len(rows), "all_hashes_match": True, "manifest_sha256": sha256_file(path)}


def rectangle_mask(shape: tuple[int, int], text: str) -> np.ndarray:
    values = json.loads(text)
    require(isinstance(values, list) and len(values) == 4, f"invalid bbox: {text}")
    x1, y1, x2, y2 = [int(round(float(value))) for value in values]
    height, width = shape
    x1, x2 = sorted((max(0, min(width, x1)), max(0, min(width, x2))))
    y1, y2 = sorted((max(0, min(height, y1)), max(0, min(height, y2))))
    require(x2 > x1 and y2 > y1, f"empty bbox after clipping: {text}")
    mask = np.zeros(shape, dtype=bool)
    mask[y1:y2, x1:x2] = True
    return mask


def rotated_bbox_mask(text: str) -> np.ndarray:
    cx, cy, width, height, angle = [float(value) for value in json.loads(text)]
    points = cv2.boxPoints(((cx, cy), (width, height), angle))
    mask = np.zeros((FAN_HEIGHT, FAN_WIDTH), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.round(points).astype(np.int32), 1)
    return mask.astype(bool)


def safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / max(float(denominator), 1.0)


def f1(precision: float, recall: float) -> float:
    return 2.0 * precision * recall / max(precision + recall, 1e-12)


def mask_metrics(prediction: np.ndarray, main: np.ndarray, intermittent: np.ndarray, background: np.ndarray) -> dict[str, Any]:
    visible = main | intermittent
    evaluable = visible | background
    pred_eval = prediction & evaluable
    visible_hit = int(np.count_nonzero(prediction & visible))
    main_hit = int(np.count_nonzero(prediction & main))
    intermittent_hit = int(np.count_nonzero(prediction & intermittent))
    pred_eval_area = int(np.count_nonzero(pred_eval))
    precision = safe_ratio(visible_hit, pred_eval_area)
    recall = safe_ratio(visible_hit, np.count_nonzero(visible))
    return {
        "prediction_area_px": int(np.count_nonzero(prediction)),
        "prediction_area_in_evaluable_reference_px": pred_eval_area,
        "visible_reference_area_px": int(np.count_nonzero(visible)),
        "visible_hit_px": visible_hit,
        "visible_recall": recall,
        "visible_precision_in_reviewed_regions": precision,
        "visible_f1_in_reviewed_regions": f1(precision, recall),
        "main_recall": safe_ratio(main_hit, np.count_nonzero(main)),
        "intermittent_recall": safe_ratio(intermittent_hit, np.count_nonzero(intermittent)),
        "background_attachment_px": int(np.count_nonzero(prediction & background)),
        "background_attachment_fraction": safe_ratio(np.count_nonzero(prediction & background), np.count_nonzero(background)),
    }


def aggregate_metrics(items: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]) -> dict[str, Any]:
    pred_area = pred_eval_area = visible_area = visible_hit = 0
    main_area = main_hit = intermittent_area = intermittent_hit = background_area = background_hit = 0
    for prediction, main, intermittent, background in items:
        visible = main | intermittent
        evaluable = visible | background
        pred_area += int(np.count_nonzero(prediction))
        pred_eval_area += int(np.count_nonzero(prediction & evaluable))
        visible_area += int(np.count_nonzero(visible))
        visible_hit += int(np.count_nonzero(prediction & visible))
        main_area += int(np.count_nonzero(main))
        main_hit += int(np.count_nonzero(prediction & main))
        intermittent_area += int(np.count_nonzero(intermittent))
        intermittent_hit += int(np.count_nonzero(prediction & intermittent))
        background_area += int(np.count_nonzero(background))
        background_hit += int(np.count_nonzero(prediction & background))
    precision = safe_ratio(visible_hit, pred_eval_area)
    recall = safe_ratio(visible_hit, visible_area)
    return {
        "prediction_area_px": pred_area,
        "prediction_area_in_evaluable_reference_px": pred_eval_area,
        "visible_reference_area_px": visible_area,
        "visible_hit_px": visible_hit,
        "visible_recall": recall,
        "visible_precision_in_reviewed_regions": precision,
        "visible_f1_in_reviewed_regions": f1(precision, recall),
        "main_recall": safe_ratio(main_hit, main_area),
        "intermittent_recall": safe_ratio(intermittent_hit, intermittent_area),
        "background_attachment_px": background_hit,
        "background_attachment_fraction": safe_ratio(background_hit, background_area),
    }


def lifecycle_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row["sar_frame_index"]))
    active = [row for row in ordered if row["optical_lifecycle_state"] not in {"ABSENT", "CLOSED"}]
    absent = [row for row in ordered if row["optical_lifecycle_state"] == "ABSENT"]
    closed = [row for row in ordered if row["optical_lifecycle_state"] == "CLOSED"]
    nonempty_active = [row for row in active if int(row["joint_support_area_px"]) > 0]
    first_active = int(active[0]["sar_frame_index"]) if active else None
    first_support = int(nonempty_active[0]["sar_frame_index"]) if nonempty_active else None
    admission_delay = first_support - first_active if first_active is not None and first_support is not None else math.nan
    return {
        "active_frame_count": len(active),
        "active_state_coverage": safe_ratio(len(nonempty_active), len(active)),
        "admission_delay_sar_frames": admission_delay,
        "premature_pre_entry_support_frame_count": sum(int(row["joint_support_area_px"]) > 0 for row in absent),
        "closed_support_tail_frame_count": sum(int(row["joint_support_area_px"]) > 0 for row in closed),
        "closed_identity_reactivation_count": sum(
            int(ordered[index - 1]["joint_support_area_px"]) == 0 and int(row["joint_support_area_px"]) > 0
            for index, row in enumerate(ordered)
            if index > 0 and row["optical_lifecycle_state"] == "CLOSED"
        ),
        "weak_or_occluded_frame_count": sum(row["optical_lifecycle_state"] == "ACTIVE_WEAK_OR_OCCLUDED" for row in ordered),
        "maximum_maintenance_age_frames": max((int(row["maintenance_age_frames"]) for row in ordered), default=0),
    }


def display_rgb(gray: np.ndarray, low: float = 0.0, high: float = 85.0) -> np.ndarray:
    value = np.clip((gray.astype(np.float32) - low) / max(high - low, 1.0), 0.0, 1.0)
    return cv2.cvtColor((value * 255).astype(np.uint8), cv2.COLOR_GRAY2RGB)


def contour(image: np.ndarray, mask: np.ndarray, color: tuple[int, int, int], thickness: int = 2) -> None:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, color, thickness)


def create_posthoc_page(
    case_id: str,
    frame_records: list[dict[str, Any]],
    output_root: Path,
) -> Path:
    figure, axes = plt.subplots(len(frame_records), 2, figsize=(13, 4 * len(frame_records)), squeeze=False)
    for row_index, record in enumerate(frame_records):
        raw = cv2.imread(record["sar_gray_path"], cv2.IMREAD_GRAYSCALE)
        dx, dy = record["transport"]
        x1, y1, x2, y2 = record["roi"]
        stable = warp_translation(raw, -dx, -dy, cv2.INTER_LINEAR)[y1:y2, x1:x2]
        left = display_rgb(stable)
        contour(left, record["shell"], (0, 190, 255), 2)
        contour(left, record["main"], (255, 255, 0), 2)
        contour(left, record["intermittent"], (255, 170, 0), 2)
        contour(left, record["background"], (255, 60, 60), 2)
        axes[row_index, 0].imshow(left)
        axes[row_index, 0].set_title(f"SAR {record['frame']} shell cyan | main yellow | intermittent orange | clear background red")
        right = display_rgb(stable).astype(np.float32)
        right[record["causal_joint"]] = 0.4 * right[record["causal_joint"]] + 0.6 * np.asarray([40, 230, 80])
        right[record["bidirectional_joint"]] = 0.6 * right[record["bidirectional_joint"]] + 0.4 * np.asarray([40, 220, 240])
        right = np.clip(right, 0, 255).astype(np.uint8)
        contour(right, record["main"], (255, 255, 0), 2)
        contour(right, record["intermittent"], (255, 170, 0), 2)
        axes[row_index, 1].imshow(right)
        axes[row_index, 1].set_title("causal joint green | offline bidirectional increment cyan | reference contours")
        for axis in axes[row_index]:
            axis.axis("off")
    figure.suptitle(f"{case_id} post-freeze visible-response evaluation")
    figure.tight_layout()
    output_dir = output_root / case_id / "posthoc_visible_response_evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "posthoc_visible_response_evaluation.png"
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def main() -> None:
    config = load_json(CONFIG_PATH)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    freeze_path = resolve(config["inference_freeze_manifest"])
    freeze_audit = verify_freeze(freeze_path)
    queue_path = resolve(config["reference_review_queue"])
    queue_rows = read_csv(queue_path)
    require(queue_rows and all(row["review_status"] == "directly_reviewed_complete" for row in queue_rows), "reference queue direct review incomplete")
    reference_path = resolve(config["visible_response_reference_manifest"])
    reference_rows = read_csv(reference_path)
    require(reference_rows, "empty visible-response reference manifest")
    allowed_categories = {"VISIBLE_MAIN_RESPONSE", "VISIBLE_INTERMITTENT_RESPONSE", "CLEAR_BACKGROUND", "MIXED_OR_UNRESOLVED"}
    require(all(row["review_category"] in allowed_categories for row in reference_rows), "unknown visible-response category")
    require(all(row["review_status"] == "directly_reviewed_complete" for row in reference_rows), "reference row review incomplete")
    require(all(row["contains_target_reference"] == "false" for row in reference_rows), "target reference used for visible-response review")
    require(all(row["used_to_change_inference_rules"] == "false" for row in reference_rows), "reference used to change inference rules")
    require(all(row["inference_freeze_manifest_sha256_before_review"] == freeze_audit["manifest_sha256"] for row in reference_rows), "pre-review freeze hash mismatch")

    output_root = Path(config["output_root"])
    condition_rows = read_csv(MANIFEST_DIR / "oty2_s1d0_lifecycle_conditions.csv")
    target_condition = {
        (row["case_id"], int(row["sar_frame_index"])): row
        for row in condition_rows
        if row["is_target_identity"] == "true"
    }
    gt_rows = read_csv(resolve(config["full_gt_context_manifest"]))
    gt_by_key = defaultdict(list)
    for row in gt_rows:
        gt_by_key[(row["scene"], row["canonical_vehicle_id"], int(row["sar_frame_index"]))].append(row)
    reference_by_key = defaultdict(list)
    for row in reference_rows:
        reference_by_key[(row["case_id"], int(row["sar_frame_index"]))].append(row)

    frame_outputs: list[dict[str, Any]] = []
    case_outputs: list[dict[str, Any]] = []
    visual_rows: list[dict[str, Any]] = []
    case_evidence: dict[str, dict[str, Any]] = {}
    for case_id in config["reference_cases"]:
        causal_path = output_root / case_id / "causal" / "dynamic_state_masks.npz"
        bidirectional_path = output_root / case_id / "bidirectional" / "dynamic_state_masks.npz"
        causal = np.load(causal_path)
        bidirectional = np.load(bidirectional_path)
        require(np.array_equal(causal["frames"], bidirectional["frames"]), f"causal/bidirectional frame mismatch: {case_id}")
        require(np.array_equal(causal["roi"], bidirectional["roi"]), f"causal/bidirectional ROI mismatch: {case_id}")
        frames = [int(value) for value in causal["frames"]]
        frame_to_index = {frame: index for index, frame in enumerate(frames)}
        x1, y1, x2, y2 = [int(value) for value in causal["roi"]]
        shape = (y2 - y1, x2 - x1)
        case_items = defaultdict(list)
        posthoc_records: list[dict[str, Any]] = []
        gt_shell_intersection = gt_joint_intersection = gt_area_total = gt_available_frame_count = 0
        for frame in sorted(frame for key_case, frame in reference_by_key if key_case == case_id):
            index = frame_to_index[frame]
            categories = {category: np.zeros(shape, dtype=bool) for category in allowed_categories}
            for row in reference_by_key[(case_id, frame)]:
                categories[row["review_category"]] |= rectangle_mask(shape, row["region_bbox_xyxy"])
            main = categories["VISIBLE_MAIN_RESPONSE"]
            intermittent = categories["VISIBLE_INTERMITTENT_RESPONSE"]
            background = categories["CLEAR_BACKGROUND"]
            mixed = categories["MIXED_OR_UNRESOLVED"]
            require(not np.any((main | intermittent | background) & mixed), f"mixed reference overlaps evaluable labels: {case_id} {frame}")
            predictions = {
                "causal_joint": causal["joint_support"][index].astype(bool),
                "bidirectional_joint": bidirectional["joint_support"][index].astype(bool),
                "axis_baseline": causal["equal_area_axis_strip"][index].astype(bool),
                "center_baseline": causal["equal_area_center_region"][index].astype(bool),
                "shell": causal["geometric_shell"][index].astype(bool),
            }
            row_out: dict[str, Any] = {
                "case_id": case_id,
                "scene": target_condition[(case_id, frame)]["scene"],
                "canonical_vehicle_id": target_condition[(case_id, frame)]["target_canonical_vehicle_id"],
                "sar_frame_index": frame,
                "optical_lifecycle_state": target_condition[(case_id, frame)]["optical_lifecycle_state"],
                "visible_main_reference_area_px": int(np.count_nonzero(main)),
                "visible_intermittent_reference_area_px": int(np.count_nonzero(intermittent)),
                "clear_background_reference_area_px": int(np.count_nonzero(background)),
                "mixed_or_unresolved_reference_area_px": int(np.count_nonzero(mixed)),
            }
            for name, prediction in predictions.items():
                metrics = mask_metrics(prediction, main, intermittent, background)
                case_items[name].append((prediction, main, intermittent, background))
                for metric, value in metrics.items():
                    row_out[f"{name}_{metric}"] = fmt(value)

            condition = target_condition[(case_id, frame)]
            scene = condition["scene"]
            vehicle = condition["target_canonical_vehicle_id"]
            gt_full = np.zeros((FAN_HEIGHT, FAN_WIDTH), dtype=bool)
            for gt_row in gt_by_key.get((scene, vehicle, frame), []):
                gt_full |= rotated_bbox_mask(gt_row["bbox"])
            dx, dy = [float(value) for value in causal["cumulative_transport"][index]]
            gt_crop = warp_translation(gt_full.astype(np.uint8), -dx, -dy, cv2.INTER_NEAREST)[y1:y2, x1:x2].astype(bool)
            gt_area = int(np.count_nonzero(gt_crop))
            gt_available_frame_count += int(gt_area > 0)
            gt_area_total += gt_area
            gt_shell_intersection += int(np.count_nonzero(gt_crop & predictions["shell"]))
            gt_joint_intersection += int(np.count_nonzero(gt_crop & predictions["causal_joint"]))
            row_out.update(
                {
                    "posthoc_full_gt_available": fmt(gt_area > 0),
                    "posthoc_full_gt_area_px": gt_area,
                    "posthoc_shell_gt_coverage": fmt(safe_ratio(np.count_nonzero(gt_crop & predictions["shell"]), gt_area)),
                    "posthoc_causal_joint_gt_coverage": fmt(safe_ratio(np.count_nonzero(gt_crop & predictions["causal_joint"]), gt_area)),
                    "target_reference_used_for_inference": "false",
                    "evaluation_only": "true",
                }
            )
            frame_outputs.append(row_out)
            posthoc_records.append(
                {
                    "frame": frame,
                    "sar_gray_path": condition["sar_gray_path"],
                    "transport": (dx, dy),
                    "roi": (x1, y1, x2, y2),
                    "shell": predictions["shell"],
                    "causal_joint": predictions["causal_joint"],
                    "bidirectional_joint": predictions["bidirectional_joint"],
                    "main": main,
                    "intermittent": intermittent,
                    "background": background,
                }
            )

        aggregates = {name: aggregate_metrics(items) for name, items in case_items.items()}
        gate = config["gate"]
        reviewed_frames = len(posthoc_records)
        visible_pixels = int(aggregates["causal_joint"]["visible_reference_area_px"])
        causal_f1 = float(aggregates["causal_joint"]["visible_f1_in_reviewed_regions"])
        axis_f1 = float(aggregates["axis_baseline"]["visible_f1_in_reviewed_regions"])
        center_f1 = float(aggregates["center_baseline"]["visible_f1_in_reviewed_regions"])
        adequate_reference = (
            reviewed_frames >= int(gate["minimum_reviewed_frame_count_per_case"])
            and visible_pixels >= int(gate["minimum_visible_reference_pixels_per_case"])
        )
        beats_baselines = (
            causal_f1 - axis_f1 >= float(gate["minimum_f1_margin_over_each_equal_area_baseline"])
            and causal_f1 - center_f1 >= float(gate["minimum_f1_margin_over_each_equal_area_baseline"])
        )
        mapping_context = safe_ratio(gt_shell_intersection, gt_area_total) if gt_area_total > 0 else math.nan
        response_context = safe_ratio(gt_joint_intersection, gt_area_total) if gt_area_total > 0 else math.nan
        shell_visible_recall = float(aggregates["shell"]["visible_recall"])
        if not adequate_reference:
            failure_layer = "VISIBLE_RESPONSE_REFERENCE_INADEQUATE_FOR_MAPPING_RESPONSE_SEPARATION"
        elif shell_visible_recall < 0.5:
            failure_layer = "MAPPING_OR_SHELL_PLACEMENT_LIMITATION"
        elif not beats_baselines:
            failure_layer = "RESPONSE_EXTRACTION_OR_BACKGROUND_SEPARATION_LIMITATION"
        else:
            failure_layer = "NO_ENTRANCE_GATE_FAILURE_DETECTED"
        case_summary = {
            "case_id": case_id,
            "reviewed_frame_count": reviewed_frames,
            "visible_reference_pixel_count": visible_pixels,
            "reference_coverage_adequate": adequate_reference,
            "causal_visible_recall": aggregates["causal_joint"]["visible_recall"],
            "causal_visible_precision": aggregates["causal_joint"]["visible_precision_in_reviewed_regions"],
            "causal_visible_f1": causal_f1,
            "causal_main_response_recall": aggregates["causal_joint"]["main_recall"],
            "causal_intermittent_response_recall": aggregates["causal_joint"]["intermittent_recall"],
            "axis_baseline_visible_f1": axis_f1,
            "center_baseline_visible_f1": center_f1,
            "causal_f1_margin_over_axis": causal_f1 - axis_f1,
            "causal_f1_margin_over_center": causal_f1 - center_f1,
            "causal_beats_both_equal_area_baselines": beats_baselines,
            "bidirectional_visible_recall": aggregates["bidirectional_joint"]["visible_recall"],
            "bidirectional_visible_precision": aggregates["bidirectional_joint"]["visible_precision_in_reviewed_regions"],
            "bidirectional_visible_f1": aggregates["bidirectional_joint"]["visible_f1_in_reviewed_regions"],
            "bidirectional_main_response_recall": aggregates["bidirectional_joint"]["main_recall"],
            "bidirectional_intermittent_response_recall": aggregates["bidirectional_joint"]["intermittent_recall"],
            "bidirectional_f1_increment_over_causal": float(aggregates["bidirectional_joint"]["visible_f1_in_reviewed_regions"]) - causal_f1,
            "causal_background_attachment_fraction": aggregates["causal_joint"]["background_attachment_fraction"],
            "bidirectional_background_attachment_fraction": aggregates["bidirectional_joint"]["background_attachment_fraction"],
            "shell_visible_reference_recall": shell_visible_recall,
            "posthoc_full_gt_available_frame_count": gt_available_frame_count,
            "posthoc_full_gt_shell_coverage_context": mapping_context,
            "posthoc_full_gt_causal_joint_coverage_context": response_context,
            "diagnosed_failure_layer": failure_layer,
            "target_reference_used_for_inference": False,
            "rule_update_from_evaluation": False,
        }
        case_outputs.append({key: fmt(value) for key, value in case_summary.items()})
        case_evidence[case_id] = case_summary
        visual_path = create_posthoc_page(case_id, posthoc_records, output_root)
        visual_rows.append(
            {
                "case_id": case_id,
                "artifact_path": str(visual_path),
                "artifact_sha256": sha256_file(visual_path),
                "generated_after_inference_freeze": "true",
                "contains_posthoc_visible_response_reference": "true",
                "contains_posthoc_full_gt": "false",
                "review_status": "pending_posthoc_direct_review",
            }
        )

    causal_states = read_csv(MANIFEST_DIR / "oty2_s1d0_causal_frame_states.csv")
    bidirectional_states = read_csv(MANIFEST_DIR / "oty2_s1d0_bidirectional_frame_states.csv")
    lifecycle_by_case = {}
    for case_id in sorted(set(row["case_id"] for row in causal_states)):
        lifecycle_by_case[case_id] = {
            "causal": lifecycle_metrics([row for row in causal_states if row["case_id"] == case_id]),
            "bidirectional": lifecycle_metrics([row for row in bidirectional_states if row["case_id"] == case_id]),
        }

    event_recurrence = Counter()
    for mode in ("causal", "bidirectional"):
        rows = read_csv(MANIFEST_DIR / f"oty2_s1d0_{mode}_response_events.csv")
        cases_by_event = defaultdict(set)
        for row in rows:
            cases_by_event[row["event_type"]].add(row["case_id"])
        for event, cases in cases_by_event.items():
            if len(cases) >= 2:
                event_recurrence[f"{mode}:{event}"] = len(cases)

    discovery = case_evidence["S1D0-DISCOVERY-GM_RM017-PV002"]
    replay = case_evidence["S1D0-REPLAY-ENTRYEXIT-GM_RM019-PV003"]
    entrance_gate = all(
        evidence["reference_coverage_adequate"] and evidence["causal_beats_both_equal_area_baselines"]
        for evidence in (discovery, replay)
    )
    stress_lifecycle = lifecycle_by_case["S1D0-STRESS-GM_RM011-PV008"]["causal"]
    stages = [
        {
            "stage": "A_RECOVERY_MECHANISM_VALIDATION",
            "status": "PASSED" if entrance_gate else "NOT_PASSED",
            "finding": "joint support beats both equal-area optical baselines on discovery and cross-scene review" if entrance_gate else "at least one required case does not beat both equal-area optical baselines or lacks adequate visible-response reference coverage",
        },
        {
            "stage": "B_SMALL_SCALE_S1D_EVENT_INTERPRETATION",
            "status": "ALLOWED_CORRELATION_LEVEL_ONLY" if entrance_gate else "BLOCKED_BY_RECOVERY_ENTRANCE_GATE",
            "finding": "event vocabulary remains correlation-level; no unique physical scattering mechanism is claimed",
        },
        {
            "stage": "C_FROZEN_REPLAY_AND_STRESS_DIAGNOSIS",
            "status": "COMPLETED_DIAGNOSTIC",
            "finding": "cross-scene replay and GM_RM011 stress were executed with v1.1 frozen rules and no second repair",
        },
    ]
    questions = [
        {
            "question_id": "Q1_SAR_INCREMENT_OVER_EQUAL_AREA_OPTICAL_PRIOR",
            "direct_answer": "已证实" if entrance_gate else "未证实",
            "evidence": f"discovery causal/axis/center F1={discovery['causal_visible_f1']:.3f}/{discovery['axis_baseline_visible_f1']:.3f}/{discovery['center_baseline_visible_f1']:.3f}; replay={replay['causal_visible_f1']:.3f}/{replay['axis_baseline_visible_f1']:.3f}/{replay['center_baseline_visible_f1']:.3f}",
        },
        {
            "question_id": "Q2_VISIBLE_MAIN_AND_INTERMITTENT_RECOVERY",
            "direct_answer": "按直接可见响应参考分别报告，不以完整车体 GT 代替分母",
            "evidence": f"discovery recall/precision={discovery['causal_visible_recall']:.3f}/{discovery['causal_visible_precision']:.3f}; replay positive reference coverage is inadequate and its zero-valued recall/precision are not interpreted",
        },
        {
            "question_id": "Q3_NATURAL_LIFECYCLE_OPERATION",
            "direct_answer": "生命周期由光学 canonical thread 和硬同步自动驱动；关闭后支撑清零",
            "evidence": "; ".join(
                f"{case_id}: active_coverage={values['causal']['active_state_coverage']:.3f}, preentry={values['causal']['premature_pre_entry_support_frame_count']}, closed_tail={values['causal']['closed_support_tail_frame_count']}"
                for case_id, values in lifecycle_by_case.items()
            ),
        },
        {
            "question_id": "Q4_CAUSAL_VS_OFFLINE_BIDIRECTIONAL_INCREMENT",
            "direct_answer": "双向路径仅作为离线未来帧平滑增量单列，不视为可部署能力",
            "evidence": f"F1 increment discovery={discovery['bidirectional_f1_increment_over_causal']:.3f}; replay={replay['bidirectional_f1_increment_over_causal']:.3f}",
        },
        {
            "question_id": "Q5_RECURRENT_RESPONSE_EVENTS",
            "direct_answer": "仅保留相关性事件计数；入口门未通过时不作 S1-D 物理解释" if not entrance_gate else "事件可在相关性层面比较，但仍不声称唯一物理机理",
            "evidence": json.dumps(dict(event_recurrence), ensure_ascii=False, sort_keys=True),
        },
        {
            "question_id": "Q6_FROZEN_CROSS_SCENE_AND_STRESS_BEHAVIOR",
            "direct_answer": "跨场景与压力案例均完成冻结重放；失败层分别报告，不用第二次修复掩盖",
            "evidence": f"replay failure_layer={replay['diagnosed_failure_layer']}; stress active_coverage={stress_lifecycle['active_state_coverage']:.3f}, closed_tail={stress_lifecycle['closed_support_tail_frame_count']}",
        },
    ]
    write_csv(FRAME_OUTPUT, frame_outputs)
    write_csv(CASE_OUTPUT, case_outputs)
    write_csv(STAGE_OUTPUT, stages)
    write_csv(QUESTION_OUTPUT, questions)
    write_csv(VISUAL_OUTPUT, visual_rows)
    summary = {
        "version": "OTY2-S1D0-postfreeze-evaluation-summary-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state,
        "evaluation_config": str(CONFIG_PATH),
        "evaluation_config_sha256": sha256_file(CONFIG_PATH),
        "inference_freeze_audit": freeze_audit,
        "visible_response_reference_manifest": str(reference_path),
        "visible_response_reference_manifest_sha256": sha256_file(reference_path),
        "case_metrics": case_outputs,
        "lifecycle_metrics": lifecycle_by_case,
        "event_recurrence_in_at_least_two_cases": dict(event_recurrence),
        "recovery_entrance_gate_passed": entrance_gate,
        "physical_event_interpretation_allowed": entrance_gate,
        "project_questions": questions,
        "target_reference_used_for_inference": False,
        "inference_outputs_modified": False,
        "rule_update_from_evaluation": False,
        "second_repair_performed": False,
    }
    write_json(SUMMARY_OUTPUT, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
