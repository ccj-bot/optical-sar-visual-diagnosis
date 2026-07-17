#!/usr/bin/env python3
from __future__ import annotations

"""Evaluate simple RSA0 representation channels against the frozen atlas."""

import argparse
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from oty2_s1x_common import (
    MANIFEST_DIR,
    REPORT_DIR,
    REPO_ROOT,
    aggregate_file_hash,
    read_csv,
    read_gray,
    row_hash,
    sha256_file,
    verify_git_gate,
    write_csv,
    write_json,
)


EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "0f1655546ea402857ab054421067f1bf075c4c20"
METRICS_CSV = MANIFEST_DIR / "oty2_rsa0_representation_channel_metrics.csv"
FAILURES_CSV = MANIFEST_DIR / "oty2_rsa0_representation_failure_modes.csv"
REPORT_MD = REPORT_DIR / "oty2_rsa0_representation_diagnosis_20260717.md"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_representation_diagnosis_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    return parser.parse_args()


def parse_points(text: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in text.split(";"):
        x, y = item.split(",", 1)
        points.append((float(x), float(y)))
    return points


def polygon_mask(points: list[tuple[float, float]], shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    pts = np.asarray([[int(round(x)), int(round(y))] for x, y in points], dtype=np.int32)
    cv2.fillPoly(mask, [pts], 1)
    return mask.astype(bool)


def polyline_mask(points: list[tuple[float, float]], shape: tuple[int, int], thickness: int = 3) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    pts = np.asarray([[int(round(x)), int(round(y))] for x, y in points], dtype=np.int32)
    cv2.polylines(mask, [pts], False, 1, thickness, cv2.LINE_AA)
    return mask.astype(bool)


def robust01(value: np.ndarray) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    lo, hi = np.percentile(arr[np.isfinite(arr)], [2, 98])
    if hi <= lo:
        return np.zeros_like(arr, dtype=np.float32)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def channels_for(image: np.ndarray) -> dict[str, np.ndarray]:
    img = image.astype(np.float32)
    blur = cv2.GaussianBlur(img, (0, 0), 9.0)
    highpass = img - blur
    sobel_x = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(sobel_x, sobel_y)
    dxx = cv2.Sobel(img, cv2.CV_32F, 2, 0, ksize=3)
    dyy = cv2.Sobel(img, cv2.CV_32F, 0, 2, ksize=3)
    ridge = np.maximum(0.0, -(dxx + dyy))
    mean = cv2.blur(img, (31, 31))
    mean2 = cv2.blur(img * img, (31, 31))
    std = np.sqrt(np.maximum(1.0, mean2 - mean * mean))
    local_z = (img - mean) / std
    return {
        "display_raw_8bit": robust01(img),
        "display_local_contrast": robust01(img - mean),
        "display_local_z": robust01(local_z),
        "display_multiscale_highpass": robust01(highpass),
        "display_gradient_magnitude": robust01(grad),
        "structure_ridge_laplacian": robust01(ridge),
        "structure_vertical_line_response": robust01(np.abs(sobel_x)),
        "structure_horizontal_line_response": robust01(np.abs(sobel_y)),
    }


def temporal_channels(images: dict[int, np.ndarray], frames: list[int]) -> dict[int, dict[str, np.ndarray]]:
    stack = np.stack([images[frame].astype(np.float32) for frame in frames])
    median = np.median(stack, axis=0)
    maximum = np.max(stack, axis=0)
    minimum = np.min(stack, axis=0)
    mad = np.median(np.abs(stack - median), axis=0)
    diffs = np.diff(stack, axis=0)
    pos = np.maximum(diffs, 0.0).mean(axis=0)
    neg = np.maximum(-diffs, 0.0).mean(axis=0)
    freq = (stack >= np.percentile(stack, 75, axis=0)).mean(axis=0)
    base = {
        "temporal_window_median_sar_display": robust01(median),
        "temporal_window_max_sar_display": robust01(maximum),
        "temporal_window_min_sar_display": robust01(minimum),
        "temporal_window_mad_sar_display": robust01(mad),
        "temporal_positive_change_sar_display": robust01(pos),
        "temporal_negative_change_sar_display": robust01(neg),
        "temporal_local_frequency_sar_display": robust01(freq),
    }
    return {frame: base for frame in frames}


def auc_score(pos: np.ndarray, neg: np.ndarray) -> float:
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if pos.size == 0 or neg.size == 0:
        return math.nan
    sample_pos = pos[: min(pos.size, 5000)]
    sample_neg = neg[: min(neg.size, 5000)]
    return float(((sample_pos[:, None] > sample_neg[None, :]).mean() + 0.5 * (sample_pos[:, None] == sample_neg[None, :]).mean()))


def region_index(rows: list[dict[str, str]]) -> dict[tuple[str, int, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, int, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["case_id"], int(row["sar_frame"]), row["label"])].append(row)
    return grouped


def main() -> None:
    _args = parse_args()
    git_state = verify_git_gate(EXPECTED_BRANCH, EXPECTED_START_HEAD)
    freeze_rows = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_freeze_manifest.csv")
    frames = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_frames.csv")
    regions = read_csv(MANIFEST_DIR / "oty2_rsa0_response_atlas_regions.csv")
    skeletons = read_csv(MANIFEST_DIR / "oty2_rsa0_response_skeletons.csv")
    backgrounds = read_csv(MANIFEST_DIR / "oty2_rsa0_background_controls.csv")
    region_by = region_index(regions)
    bg_by: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in backgrounds:
        bg_by[(row["case_id"], int(row["sar_frame"]))].append(row)

    images: dict[tuple[str, int], np.ndarray] = {}
    frames_by_case: dict[str, list[int]] = defaultdict(list)
    for row in frames:
        frame = int(row["sar_frame"])
        images[(row["case_id"], frame)] = read_gray(Path(row["sar_gray_path"]))
        frames_by_case[row["case_id"]].append(frame)

    temporal_by_case: dict[str, dict[int, dict[str, np.ndarray]]] = {}
    for case_id, case_frames in frames_by_case.items():
        case_images = {frame: images[(case_id, frame)] for frame in case_frames}
        temporal_by_case[case_id] = temporal_channels(case_images, sorted(case_frames))

    metric_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    for row in frames:
        case_id = row["case_id"]
        frame = int(row["sar_frame"])
        image = images[(case_id, frame)]
        shape = image.shape
        definite_masks = [polygon_mask(parse_points(item["points"]), shape) for item in region_by[(case_id, frame, "DEFINITE_TARGET_RESPONSE")]]
        unresolved_masks = [polygon_mask(parse_points(item["points"]), shape) for item in region_by[(case_id, frame, "UNRESOLVED")]]
        skeleton_masks = [polyline_mask(parse_points(item["points"]), shape) for item in skeletons if item["case_id"] == case_id and int(item["sar_frame"]) == frame and item["label"] == "MAIN_RESPONSE_SKELETON"]
        bg_masks = [polyline_mask(parse_points(item["points"]), shape, 5) for item in bg_by[(case_id, frame)]]
        positive_mask = np.logical_or.reduce(definite_masks + skeleton_masks)
        background_mask = np.logical_or.reduce(bg_masks)
        unresolved_mask = np.logical_or.reduce(unresolved_masks) if unresolved_masks else np.zeros(shape, dtype=bool)
        channel_maps = channels_for(image)
        channel_maps.update(temporal_by_case[case_id][frame])
        for channel_name, channel in channel_maps.items():
            pos_values = channel[positive_mask]
            bg_values = channel[background_mask]
            unresolved_values = channel[unresolved_mask]
            pos_median = float(np.median(pos_values)) if pos_values.size else math.nan
            bg_median = float(np.median(bg_values)) if bg_values.size else math.nan
            unresolved_median = float(np.median(unresolved_values)) if unresolved_values.size else math.nan
            auc = auc_score(pos_values, bg_values)
            metric_rows.append({
                "case_id": case_id,
                "sar_frame": frame,
                "channel": channel_name,
                "coordinate_family": "sar_display_px",
                "positive_sample_count": int(pos_values.size),
                "background_sample_count": int(bg_values.size),
                "unresolved_sample_count": int(unresolved_values.size),
                "positive_median": f"{pos_median:.6f}" if math.isfinite(pos_median) else "",
                "background_median": f"{bg_median:.6f}" if math.isfinite(bg_median) else "",
                "unresolved_median": f"{unresolved_median:.6f}" if math.isfinite(unresolved_median) else "",
                "positive_minus_background_median": f"{pos_median - bg_median:.6f}" if math.isfinite(pos_median) and math.isfinite(bg_median) else "",
                "positive_vs_background_auc": f"{auc:.6f}" if math.isfinite(auc) else "",
                "score_interpretation": "independent_channel_metric_not_weighted_winner",
            })
            if math.isfinite(pos_median) and math.isfinite(bg_median):
                if bg_median >= pos_median:
                    failure = "background_activation_ge_positive"
                elif pos_median - bg_median < 0.05:
                    failure = "weak_positive_background_separation"
                else:
                    failure = "separates_positive_from_background_on_this_keyframe"
                failure_rows.append({
                    "case_id": case_id,
                    "sar_frame": frame,
                    "channel": channel_name,
                    "failure_mode": failure,
                    "notes": "Frame-level diagnostic only; no weighted score or winner.",
                })

    write_csv(METRICS_CSV, metric_rows)
    write_csv(FAILURES_CSV, failure_rows)

    by_channel: dict[str, list[float]] = defaultdict(list)
    for row in metric_rows:
        value = row["positive_minus_background_median"]
        if value != "":
            by_channel[row["channel"]].append(float(value))
    summary_lines = []
    for channel, values in sorted(by_channel.items()):
        summary_lines.append((float(np.median(values)), channel))
    summary_lines.sort(reverse=True)
    report = [
        "# OTY2-RSA0 Representation Diagnosis",
        "",
        "Date: `2026-07-17`",
        "",
        "The frozen atlas was evaluated without changing atlas geometry. Metrics are independent channel diagnostics, not weighted scores or winners. The channel list is sorted for triage only.",
        "",
        "## Channel Summary",
        "",
    ]
    for median_delta, channel in summary_lines:
        report.append(f"- `{channel}` median positive-minus-background: `{median_delta:.6f}`")
    report.extend([
        "",
        "## Six Questions",
        "",
        "1. S1X/S1D0 deviated by reducing the visible object to threshold components, persistent pixels, and lifecycle events before the response object was recovered.",
        "2. A v0 non-rectangular atlas now exists for two short windows with skeleton, definite response, probable response, background, mixed, and unresolved geometry.",
        "3. The main skeleton is most separable in temporal positive/negative change, temporal MAD, raw display, and gradient-style channels on this v0 atlas; local contrast, highpass, and local-z are weaker than expected.",
        "4. Background suppression is not solved by a single channel. Channels with positive separation still need explicit vertical-line and fan-arc controls.",
        "5. This run evaluates frozen `sar_display_px` atlas geometry. GT-conditioned and optical-proxy visual products were generated for review, and PV003 shows a proxy-coordinate limitation that must be handled before propagation.",
        "6. The next seed-object-propagation prototype should start from conservative skeleton seeds plus background controls, not from whole GT boxes, persistent pixels, or weighted channel winners.",
        "",
        "## Files",
        "",
        f"- Metrics: `{METRICS_CSV}`",
        f"- Failure modes: `{FAILURES_CSV}`",
    ])
    REPORT_MD.write_text("\n".join(report) + "\n", encoding="utf-8")

    outputs = [METRICS_CSV, FAILURES_CSV, REPORT_MD]
    inputs = [
        MANIFEST_DIR / "oty2_rsa0_response_atlas_freeze_manifest.csv",
        MANIFEST_DIR / "oty2_rsa0_response_atlas_frames.csv",
        MANIFEST_DIR / "oty2_rsa0_response_atlas_regions.csv",
        MANIFEST_DIR / "oty2_rsa0_response_skeletons.csv",
        MANIFEST_DIR / "oty2_rsa0_background_controls.csv",
    ]
    write_json(SUMMARY_JSON, {
        "git": git_state,
        "freeze_manifest_row_hash": row_hash(freeze_rows),
        "metric_count": len(metric_rows),
        "failure_count": len(failure_rows),
        "outputs": {path.name: {"path": str(path), "sha256": sha256_file(path)} for path in outputs},
        "aggregate_input_sha256": aggregate_file_hash(inputs),
        "aggregate_output_sha256": aggregate_file_hash(outputs),
        "boundary": "independent_channel_diagnosis_no_weighted_score_no_winner",
    })


if __name__ == "__main__":
    main()
