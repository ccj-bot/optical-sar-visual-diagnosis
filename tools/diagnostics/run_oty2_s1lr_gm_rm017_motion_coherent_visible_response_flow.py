#!/usr/bin/env python3
from __future__ import annotations

"""Run the bounded S1-LR GM_RM017 visible-response motion audit."""

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")
OUTPUT_ROOT = (
    WORKSPACE_ROOT
    / "output"
    / "s1_lr_gm_rm017_motion_coherent_response_flow_20260716"
)
ANALYSIS_ROOT = OUTPUT_ROOT / "analysis"
LOG_PATH = (
    WORKSPACE_ROOT
    / "logs"
    / "s1_lr_gm_rm017_motion_coherent_response_flow_20260716_runner.log"
)

LOCAL_FIELD_PATH = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
PAIR_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_motion_pair_evidence.csv"
BACKGROUND_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_background_motion_reference.csv"
OFFSET_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_offset_field_evidence.csv"
SPATIAL_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_spatial_counterfactuals.csv"
TRAJECTORY_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_trajectory_counterfactuals.csv"
STATE_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_response_state_evidence.csv"
ATTRIBUTION_OUTPUT_PATH = MANIFEST_DIR / "oty2_s1lr_gm_rm017_response_attribution_summary.csv"

EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "938dd8e37b54592bc153f5518843c4f7479cfe24"
EXPECTED_MANIFEST_SHA256 = (
    "029d23d80638bfe2e115324140bfcccf9e4bb15ffeadf65f1920b244afa21092"
)
EXPECTED_FRAMES = tuple(range(330, 351))
EXPECTED_SIZE = (2308, 1334)

DISPLAY_LO = 0.0
DISPLAY_HI = 85.0
MOTION_PATCH_WIDTH = 280
MOTION_PATCH_HEIGHT = 120
MOTION_PATCH_Y_OFFSET = 35.0
FIELD_PATCH_WIDTH = 320
FIELD_PATCH_HEIGHT = 200
ATTR_PATCH_WIDTH = 360
ATTR_PATCH_HEIGHT = 220
POSITIVE_Z = 2.5
SHUFFLE_SEED = 1702

PHASE_RESPONSE_USABLE = 0.03
FLOW_SUPPORT_USABLE = 0.08
VALID_REGION_FRACTION = 0.95

BACKGROUND_REFERENCE_OFFSETS = (
    ("NEARBY_NONOVERLAP_BACKGROUND", -400.0, -240.0),
    ("VERTICAL_STRONG_LINE", 180.0, -20.0),
    ("FAN_ARC", 0.0, -220.0),
    ("ISOLATED_HOTSPOT", -350.0, -100.0),
)

CATEGORY_ORDER = (
    "PERSISTENT_VEHICLE_ASSOCIATED_RESPONSE",
    "INTERMITTENT_VEHICLE_ASSOCIATED_RESPONSE",
    "WORLD_FIXED_BACKGROUND",
    "CROP_OR_RESAMPLING_ARTIFACT",
    "UNRESOLVED_MIXED_RESPONSE",
    "CURRENTLY_DARK_LATENT_BODY_REGION",
)


@dataclass(frozen=True)
class FrameRow:
    frame: int
    image_path: Path
    image_sha256: str
    center_x: float
    center_y: float
    width: float
    height: float
    angle: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8"
    ).strip()


def finite_or_blank(value: float | None) -> float | str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return float(value)


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)


def load_rows() -> list[FrameRow]:
    rows: list[FrameRow] = []
    with LOCAL_FIELD_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            frame = int(row["sar_frame_index"])
            if not (
                row["scene"] == "GM_RM017"
                and row["canonical_vehicle_id"] == "GM_RM017:PV002"
                and row["segment_id"] == "S0MV-GM_RM017-PV002-SEG02"
                and 330 <= frame <= 350
            ):
                continue
            rows.append(
                FrameRow(
                    frame=frame,
                    image_path=Path(row["raw_image_path"]),
                    image_sha256=row["raw_image_sha256"].lower(),
                    center_x=float(row["raw_anchor_center_x_px"]),
                    center_y=float(row["raw_anchor_center_y_px"]),
                    width=float(row["raw_anchor_width_px"]),
                    height=float(row["raw_anchor_height_px"]),
                    angle=float(row["raw_anchor_angle_deg"]),
                )
            )
    rows.sort(key=lambda item: item.frame)
    if tuple(item.frame for item in rows) != EXPECTED_FRAMES:
        raise RuntimeError(f"unexpected discovery rows: {[item.frame for item in rows]}")
    return rows


def load_images(rows: Sequence[FrameRow]) -> list[np.ndarray]:
    images: list[np.ndarray] = []
    for row in rows:
        if sha256_file(row.image_path) != row.image_sha256:
            raise RuntimeError(f"SHA256 mismatch for frame {row.frame}")
        image = cv2.imread(str(row.image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(f"cannot read {row.image_path}")
        if (image.shape[1], image.shape[0]) != EXPECTED_SIZE:
            raise RuntimeError(f"unexpected image size at frame {row.frame}: {image.shape}")
        images.append(image)
    return images


def crop_with_padding(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    width: int,
    height: int,
) -> tuple[np.ndarray, np.ndarray]:
    x1 = int(round(center_x - width / 2))
    y1 = int(round(center_y - height / 2))
    x2 = x1 + width
    y2 = y1 + height
    patch = np.zeros((height, width), dtype=image.dtype)
    valid = np.zeros((height, width), dtype=np.uint8)
    sx1, sy1 = max(0, x1), max(0, y1)
    sx2, sy2 = min(image.shape[1], x2), min(image.shape[0], y2)
    if sx2 <= sx1 or sy2 <= sy1:
        return patch, valid
    dx1, dy1 = sx1 - x1, sy1 - y1
    patch[dy1 : dy1 + sy2 - sy1, dx1 : dx1 + sx2 - sx1] = image[sy1:sy2, sx1:sx2]
    valid[dy1 : dy1 + sy2 - sy1, dx1 : dx1 + sx2 - sx1] = 1
    return patch, valid


def normalize_display(image: np.ndarray) -> np.ndarray:
    scaled = (image.astype(np.float32) - DISPLAY_LO) * (
        255.0 / (DISPLAY_HI - DISPLAY_LO)
    )
    return np.clip(scaled, 0, 255).astype(np.uint8)


def phase_shift(prev: np.ndarray, curr: np.ndarray) -> dict[str, float]:
    a = normalize_display(prev).astype(np.float32)
    b = normalize_display(curr).astype(np.float32)
    a -= cv2.GaussianBlur(a, (0, 0), 3.0)
    b -= cv2.GaussianBlur(b, (0, 0), 3.0)
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a, b, window)
    return {"dx": float(dx), "dy": float(dy), "response": float(response)}


def dense_flow_shift(prev: np.ndarray, curr: np.ndarray) -> dict[str, float]:
    a = cv2.GaussianBlur(normalize_display(prev), (5, 5), 0)
    b = cv2.GaussianBlur(normalize_display(curr), (5, 5), 0)
    flow = cv2.calcOpticalFlowFarneback(
        a,
        b,
        None,
        pyr_scale=0.5,
        levels=3,
        winsize=21,
        iterations=5,
        poly_n=7,
        poly_sigma=1.5,
        flags=0,
    )
    gx = cv2.Sobel(a.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(a.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    gradient = np.hypot(gx, gy)
    central = np.zeros_like(a, dtype=bool)
    central[10:-10, 12:-12] = True
    intensity_floor = float(np.percentile(np.maximum(a, b)[central], 65.0))
    gradient_floor = float(np.percentile(gradient[central], 60.0))
    mask = central & (
        (np.maximum(a, b) >= intensity_floor) | (gradient >= gradient_floor)
    )
    if int(mask.sum()) < 32:
        mask = central
    fx = flow[..., 0][mask]
    fy = flow[..., 1][mask]
    dx = float(np.median(fx))
    dy = float(np.median(fy))
    residual = np.hypot(fx - dx, fy - dy)
    return {
        "dx": dx,
        "dy": dy,
        "support_fraction": float(mask.mean()),
        "dispersion_median_px": float(np.median(residual)),
        "dispersion_p90_px": float(np.percentile(residual, 90.0)),
    }


def norm2(dx: float, dy: float) -> float:
    return float(math.hypot(dx, dy))


def residuals(
    estimated_dx: float,
    estimated_dy: float,
    gt_dx: float,
    gt_dy: float,
    background_dx: float,
    background_dy: float,
    shifted_gt: tuple[float, float] | None = None,
) -> dict[str, float | str]:
    relative_gt_dx = gt_dx - background_dx
    relative_gt_dy = gt_dy - background_dy
    wrong_dx = background_dx - relative_gt_dx
    wrong_dy = background_dy - relative_gt_dy
    result: dict[str, float | str] = {
        "world_residual_motion_px": norm2(
            estimated_dx - background_dx, estimated_dy - background_dy
        ),
        "vehicle_residual_motion_px": norm2(
            estimated_dx - gt_dx, estimated_dy - gt_dy
        ),
        "wrong_track_residual_motion_px": norm2(
            estimated_dx - wrong_dx, estimated_dy - wrong_dy
        ),
    }
    if shifted_gt is None:
        result["time_shift_plus4_residual_motion_px"] = ""
    else:
        shifted_relative_dx = shifted_gt[0] - background_dx
        shifted_relative_dy = shifted_gt[1] - background_dy
        shifted_raw_dx = background_dx + shifted_relative_dx
        shifted_raw_dy = background_dy + shifted_relative_dy
        result["time_shift_plus4_residual_motion_px"] = norm2(
            estimated_dx - shifted_raw_dx, estimated_dy - shifted_raw_dy
        )
    return result


def estimate_world_pair(
    prev: np.ndarray,
    curr: np.ndarray,
    prev_center: tuple[float, float],
    curr_center: tuple[float, float],
) -> dict[str, dict[str, float]]:
    center_x = (prev_center[0] + curr_center[0]) / 2.0
    center_y = (prev_center[1] + curr_center[1]) / 2.0 + MOTION_PATCH_Y_OFFSET
    prev_patch, prev_valid = crop_with_padding(
        prev, center_x, center_y, MOTION_PATCH_WIDTH, MOTION_PATCH_HEIGHT
    )
    curr_patch, curr_valid = crop_with_padding(
        curr, center_x, center_y, MOTION_PATCH_WIDTH, MOTION_PATCH_HEIGHT
    )
    valid_fraction = float(np.minimum(prev_valid, curr_valid).mean())
    if valid_fraction < VALID_REGION_FRACTION:
        return {
            "phase": {"dx": math.nan, "dy": math.nan, "response": 0.0},
            "flow": {
                "dx": math.nan,
                "dy": math.nan,
                "support_fraction": 0.0,
                "dispersion_median_px": math.nan,
                "dispersion_p90_px": math.nan,
            },
            "meta": {"valid_fraction": valid_fraction},
        }
    return {
        "phase": phase_shift(prev_patch, curr_patch),
        "flow": dense_flow_shift(prev_patch, curr_patch),
        "meta": {"valid_fraction": valid_fraction},
    }


def build_background_reference_rows(
    rows: Sequence[FrameRow], images: Sequence[np.ndarray]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index in range(len(rows) - 1):
        phase_dx_values: list[float] = []
        phase_dy_values: list[float] = []
        phase_responses: list[float] = []
        flow_dx_values: list[float] = []
        flow_dy_values: list[float] = []
        flow_supports: list[float] = []
        control_details: list[str] = []
        for name, dx, dy in BACKGROUND_REFERENCE_OFFSETS:
            prev_center = (rows[index].center_x + dx, rows[index].center_y + dy)
            curr_center = (rows[index + 1].center_x + dx, rows[index + 1].center_y + dy)
            evidence = estimate_world_pair(
                images[index], images[index + 1], prev_center, curr_center
            )
            phase = evidence["phase"]
            flow = evidence["flow"]
            if math.isfinite(phase["dx"]) and math.isfinite(phase["dy"]):
                phase_dx_values.append(float(phase["dx"]))
                phase_dy_values.append(float(phase["dy"]))
                phase_responses.append(float(phase["response"]))
            if math.isfinite(flow["dx"]) and math.isfinite(flow["dy"]):
                flow_dx_values.append(float(flow["dx"]))
                flow_dy_values.append(float(flow["dy"]))
                flow_supports.append(float(flow["support_fraction"]))
            control_details.append(
                f"{name}:phase=({phase['dx']:.6f},{phase['dy']:.6f});"
                f"flow=({flow['dx']:.6f},{flow['dy']:.6f})"
            )
        phase_bg_dx = float(np.median(phase_dx_values))
        phase_bg_dy = float(np.median(phase_dy_values))
        flow_bg_dx = float(np.median(flow_dx_values))
        flow_bg_dy = float(np.median(flow_dy_values))
        gt_dx = rows[index + 1].center_x - rows[index].center_x
        gt_dy = rows[index + 1].center_y - rows[index].center_y
        output.append(
            {
                "scene": "GM_RM017",
                "canonical_vehicle_id": "GM_RM017:PV002",
                "segment_id": "S0MV-GM_RM017-PV002-SEG02",
                "frame_prev": rows[index].frame,
                "frame_curr": rows[index + 1].frame,
                "gt_dx_px": gt_dx,
                "gt_dy_px": gt_dy,
                "phase_background_dx_px": phase_bg_dx,
                "phase_background_dy_px": phase_bg_dy,
                "phase_background_response_median": float(np.median(phase_responses)),
                "phase_background_dx_mad_px": float(
                    np.median(np.abs(np.asarray(phase_dx_values) - phase_bg_dx))
                ),
                "phase_background_dy_mad_px": float(
                    np.median(np.abs(np.asarray(phase_dy_values) - phase_bg_dy))
                ),
                "flow_background_dx_px": flow_bg_dx,
                "flow_background_dy_px": flow_bg_dy,
                "flow_background_support_median": float(np.median(flow_supports)),
                "flow_background_dx_mad_px": float(
                    np.median(np.abs(np.asarray(flow_dx_values) - flow_bg_dx))
                ),
                "flow_background_dy_mad_px": float(
                    np.median(np.abs(np.asarray(flow_dy_values) - flow_bg_dy))
                ),
                "phase_gt_motion_relative_to_background_dx_px": gt_dx - phase_bg_dx,
                "phase_gt_motion_relative_to_background_dy_px": gt_dy - phase_bg_dy,
                "flow_gt_motion_relative_to_background_dx_px": gt_dx - flow_bg_dx,
                "flow_gt_motion_relative_to_background_dy_px": gt_dy - flow_bg_dy,
                "background_control_count": len(BACKGROUND_REFERENCE_OFFSETS),
                "background_control_details": "|".join(control_details),
                "world_coordinate_definition": "LOCAL_DISPLACEMENT_MINUS_MULTI_BACKGROUND_REFERENCE_DISPLACEMENT",
            }
        )
    return output


def stage_for_frame(frame: int) -> str:
    if frame <= 338:
        return "WEAK_DISTRIBUTED_330_338"
    if frame == 339:
        return "TRANSITION_ONSET_339"
    return "STRONG_COMPACT_340_350"


def build_pair_rows(
    rows: Sequence[FrameRow],
    images: Sequence[np.ndarray],
    background_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index in range(len(rows) - 1):
        prev_row, curr_row = rows[index], rows[index + 1]
        gt_dx = curr_row.center_x - prev_row.center_x
        gt_dy = curr_row.center_y - prev_row.center_y
        shifted_gt: tuple[float, float] | None = None
        if index + 4 < len(rows) - 1:
            shifted_gt = (
                rows[index + 5].center_x - rows[index + 4].center_x,
                rows[index + 5].center_y - rows[index + 4].center_y,
            )
        evidence = estimate_world_pair(
            images[index],
            images[index + 1],
            (prev_row.center_x, prev_row.center_y),
            (curr_row.center_x, curr_row.center_y),
        )
        phase = evidence["phase"]
        flow = evidence["flow"]
        background = background_rows[index]
        record: dict[str, Any] = {
            "scene": "GM_RM017",
            "canonical_vehicle_id": "GM_RM017:PV002",
            "segment_id": "S0MV-GM_RM017-PV002-SEG02",
            "frame_prev": prev_row.frame,
            "frame_curr": curr_row.frame,
            "stage_prev": stage_for_frame(prev_row.frame),
            "stage_curr": stage_for_frame(curr_row.frame),
            "gt_dx_px": gt_dx,
            "gt_dy_px": gt_dy,
            "phase_background_dx_px": background["phase_background_dx_px"],
            "phase_background_dy_px": background["phase_background_dy_px"],
            "flow_background_dx_px": background["flow_background_dx_px"],
            "flow_background_dy_px": background["flow_background_dy_px"],
            "phase_gt_motion_relative_to_background_dx_px": background[
                "phase_gt_motion_relative_to_background_dx_px"
            ],
            "phase_gt_motion_relative_to_background_dy_px": background[
                "phase_gt_motion_relative_to_background_dy_px"
            ],
            "flow_gt_motion_relative_to_background_dx_px": background[
                "flow_gt_motion_relative_to_background_dx_px"
            ],
            "flow_gt_motion_relative_to_background_dy_px": background[
                "flow_gt_motion_relative_to_background_dy_px"
            ],
            "patch_valid_fraction": evidence["meta"]["valid_fraction"],
            "phase_dx_px": finite_or_blank(phase["dx"]),
            "phase_dy_px": finite_or_blank(phase["dy"]),
            "phase_response": phase["response"],
        }
        record.update(
            {
                f"phase_{key}": value
                for key, value in residuals(
                    phase["dx"],
                    phase["dy"],
                    gt_dx,
                    gt_dy,
                    float(background["phase_background_dx_px"]),
                    float(background["phase_background_dy_px"]),
                    shifted_gt,
                ).items()
            }
        )
        record.update(
            {
                "flow_dx_px": finite_or_blank(flow["dx"]),
                "flow_dy_px": finite_or_blank(flow["dy"]),
                "flow_support_fraction": flow["support_fraction"],
                "flow_dispersion_median_px": finite_or_blank(
                    flow["dispersion_median_px"]
                ),
                "flow_dispersion_p90_px": finite_or_blank(
                    flow["dispersion_p90_px"]
                ),
            }
        )
        record.update(
            {
                f"flow_{key}": value
                for key, value in residuals(
                    flow["dx"],
                    flow["dy"],
                    gt_dx,
                    gt_dy,
                    float(background["flow_background_dx_px"]),
                    float(background["flow_background_dy_px"]),
                    shifted_gt,
                ).items()
            }
        )
        record["method_displacement_disagreement_px"] = norm2(
            phase["dx"] - flow["dx"], phase["dy"] - flow["dy"]
        )
        record["phase_quality_status"] = (
            "USABLE" if phase["response"] >= PHASE_RESPONSE_USABLE else "WEAK"
        )
        record["flow_quality_status"] = (
            "USABLE"
            if flow["support_fraction"] >= FLOW_SUPPORT_USABLE
            else "WEAK"
        )
        output.append(record)
    return output


def local_normalized_stack(
    patches: Sequence[np.ndarray], valids: Sequence[np.ndarray]
) -> tuple[np.ndarray, list[float], list[float]]:
    normalized = []
    backgrounds = []
    background_mads = []
    height, width = patches[0].shape
    ring = np.ones((height, width), dtype=bool)
    ring[24:-24, 24:-24] = False
    for patch, valid in zip(patches, valids):
        sample_mask = ring & (valid > 0)
        sample = patch[sample_mask].astype(np.float32)
        background = float(np.median(sample))
        mad = float(np.median(np.abs(sample - background)))
        robust_scale = max(1.4826 * mad, 1.0)
        normalized.append((patch.astype(np.float32) - background) / robust_scale)
        backgrounds.append(background)
        background_mads.append(mad)
    return np.stack(normalized), backgrounds, background_mads


def max_horizontal_run(mask: np.ndarray) -> int:
    best = 0
    for row in mask:
        current = 0
        for value in row:
            if bool(value):
                current += 1
                best = max(best, current)
            else:
                current = 0
    return int(best)


def clarity(image: np.ndarray) -> float:
    normalized = normalize_display(image)
    gx = cv2.Sobel(normalized.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(normalized.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    return float(np.mean(np.hypot(gx, gy)))


def stack_for_centers(
    images: Sequence[np.ndarray],
    centers: Sequence[tuple[float, float] | None],
    width: int = FIELD_PATCH_WIDTH,
    height: int = FIELD_PATCH_HEIGHT,
) -> tuple[list[np.ndarray], list[np.ndarray], list[int]]:
    patches: list[np.ndarray] = []
    valids: list[np.ndarray] = []
    indices: list[int] = []
    for index, center in enumerate(centers):
        if center is None:
            continue
        patch, valid = crop_with_padding(
            images[index], center[0], center[1], width, height
        )
        patches.append(patch)
        valids.append(valid)
        indices.append(index)
    return patches, valids, indices


def summarize_stack(
    patches: Sequence[np.ndarray], valids: Sequence[np.ndarray]
) -> tuple[dict[str, float], dict[str, np.ndarray]]:
    normalized, backgrounds, background_mads = local_normalized_stack(patches, valids)
    raw_stack = np.stack(patches).astype(np.float32)
    mean_image = raw_stack.mean(axis=0)
    median_image = np.median(raw_stack, axis=0)
    mad_image = np.median(
        np.abs(raw_stack - np.median(raw_stack, axis=0)[None, ...]), axis=0
    )
    persistence = np.mean(normalized >= POSITIVE_Z, axis=0)
    median_z = np.median(normalized, axis=0)
    structure_mask = (persistence >= 0.5) & (median_z >= 1.0)
    summary = {
        "frame_count": float(len(patches)),
        "mean_valid_fraction": float(np.mean([valid.mean() for valid in valids])),
        "mean_clarity": clarity(mean_image),
        "median_clarity": clarity(median_image),
        "temporal_mad_mean": float(mad_image.mean()),
        "temporal_mad_median": float(np.median(mad_image)),
        "positive_persistence_mean": float(persistence.mean()),
        "positive_persistence_p90": float(np.percentile(persistence, 90.0)),
        "positive_persistence_fraction_ge_0_5": float((persistence >= 0.5).mean()),
        "vehicle_scale_horizontal_run_px": float(max_horizontal_run(structure_mask)),
        "background_median_mean": float(np.mean(backgrounds)),
        "background_mad_mean": float(np.mean(background_mads)),
    }
    arrays = {
        "mean": mean_image.astype(np.float32),
        "median": median_image.astype(np.float32),
        "mad": mad_image.astype(np.float32),
        "persistence": persistence.astype(np.float32),
        "median_z": median_z.astype(np.float32),
    }
    return summary, arrays


def pair_motion_for_centers(
    images: Sequence[np.ndarray],
    rows: Sequence[FrameRow],
    centers: Sequence[tuple[float, float]],
    background_rows: Sequence[dict[str, Any]],
) -> dict[str, float]:
    phase_world: list[float] = []
    phase_vehicle: list[float] = []
    phase_wrong: list[float] = []
    phase_quality: list[float] = []
    flow_world: list[float] = []
    flow_vehicle: list[float] = []
    flow_wrong: list[float] = []
    flow_support: list[float] = []
    for index in range(len(rows) - 1):
        gt_dx = rows[index + 1].center_x - rows[index].center_x
        gt_dy = rows[index + 1].center_y - rows[index].center_y
        evidence = estimate_world_pair(
            images[index], images[index + 1], centers[index], centers[index + 1]
        )
        phase = evidence["phase"]
        flow = evidence["flow"]
        background = background_rows[index]
        if math.isfinite(phase["dx"]) and math.isfinite(phase["dy"]):
            res = residuals(
                phase["dx"],
                phase["dy"],
                gt_dx,
                gt_dy,
                float(background["phase_background_dx_px"]),
                float(background["phase_background_dy_px"]),
            )
            phase_world.append(float(res["world_residual_motion_px"]))
            phase_vehicle.append(float(res["vehicle_residual_motion_px"]))
            phase_wrong.append(float(res["wrong_track_residual_motion_px"]))
            phase_quality.append(float(phase["response"]))
        if math.isfinite(flow["dx"]) and math.isfinite(flow["dy"]):
            res = residuals(
                flow["dx"],
                flow["dy"],
                gt_dx,
                gt_dy,
                float(background["flow_background_dx_px"]),
                float(background["flow_background_dy_px"]),
            )
            flow_world.append(float(res["world_residual_motion_px"]))
            flow_vehicle.append(float(res["vehicle_residual_motion_px"]))
            flow_wrong.append(float(res["wrong_track_residual_motion_px"]))
            flow_support.append(float(flow["support_fraction"]))
    return {
        "phase_world_residual_median_px": float(np.median(phase_world)),
        "phase_vehicle_residual_median_px": float(np.median(phase_vehicle)),
        "phase_wrong_residual_median_px": float(np.median(phase_wrong)),
        "phase_response_median": float(np.median(phase_quality)),
        "flow_world_residual_median_px": float(np.median(flow_world)),
        "flow_vehicle_residual_median_px": float(np.median(flow_vehicle)),
        "flow_wrong_residual_median_px": float(np.median(flow_wrong)),
        "flow_support_fraction_median": float(np.median(flow_support)),
    }


def offset_grid() -> list[tuple[int, int, str]]:
    membership: dict[tuple[int, int], set[str]] = {}
    for dx in range(-400, 401, 100):
        for dy in range(-240, 241, 80):
            membership.setdefault((dx, dy), set()).add("COARSE")
    for dx in range(-160, 161, 40):
        for dy in range(-120, 121, 40):
            membership.setdefault((dx, dy), set()).add("FINE")
    return [
        (dx, dy, "+".join(sorted(levels)))
        for (dx, dy), levels in sorted(membership.items(), key=lambda item: (item[0][1], item[0][0]))
    ]


def offset_category(summary: dict[str, float], motion: dict[str, float]) -> str:
    if summary["mean_valid_fraction"] < VALID_REGION_FRACTION:
        return "OUTSIDE_VALID_REGION"
    phase_usable = motion["phase_response_median"] >= PHASE_RESPONSE_USABLE
    flow_usable = motion["flow_support_fraction_median"] >= FLOW_SUPPORT_USABLE
    if not (phase_usable and flow_usable):
        return "AMBIGUOUS_OVERLAP_REGION"
    phase_vehicle = (
        motion["phase_vehicle_residual_median_px"]
        < motion["phase_world_residual_median_px"]
        and motion["phase_vehicle_residual_median_px"]
        < motion["phase_wrong_residual_median_px"]
    )
    flow_vehicle = (
        motion["flow_vehicle_residual_median_px"]
        < motion["flow_world_residual_median_px"]
        and motion["flow_vehicle_residual_median_px"]
        < motion["flow_wrong_residual_median_px"]
    )
    phase_world = (
        motion["phase_world_residual_median_px"]
        < motion["phase_vehicle_residual_median_px"]
    )
    flow_world = (
        motion["flow_world_residual_median_px"]
        < motion["flow_vehicle_residual_median_px"]
    )
    if phase_vehicle and flow_vehicle:
        return "MOTION_COHERENT_SUPPORT_CORRIDOR"
    if phase_world and flow_world:
        return "BACKGROUND_DOMINATED_REGION"
    return "AMBIGUOUS_OVERLAP_REGION"


def build_offset_field(
    rows: Sequence[FrameRow],
    images: Sequence[np.ndarray],
    background_rows: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    records: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    median_center = (
        float(np.median([row.center_x for row in rows])),
        float(np.median([row.center_y for row in rows])),
    )
    for dx, dy, grid_level in offset_grid():
        centers = [(row.center_x + dx, row.center_y + dy) for row in rows]
        patches, valids, _ = stack_for_centers(images, centers)
        summary, field_arrays = summarize_stack(patches, valids)
        fixed_centers = [(median_center[0] + dx, median_center[1] + dy)] * len(rows)
        fixed_patches, fixed_valids, _ = stack_for_centers(images, fixed_centers)
        fixed_summary, _ = summarize_stack(fixed_patches, fixed_valids)
        motion = pair_motion_for_centers(images, rows, centers, background_rows)
        category = offset_category(summary, motion)
        key = f"dx_{dx:+04d}_dy_{dy:+04d}".replace("+", "p").replace("-", "m")
        for array_name, array_value in field_arrays.items():
            arrays[f"{key}_{array_name}"] = array_value
        record: dict[str, Any] = {
            "scene": "GM_RM017",
            "canonical_vehicle_id": "GM_RM017:PV002",
            "segment_id": "S0MV-GM_RM017-PV002-SEG02",
            "dx_px": dx,
            "dy_px": dy,
            "grid_level": grid_level,
            "offset_category": category,
            **summary,
            "fixed_world_mean_clarity": fixed_summary["mean_clarity"],
            "fixed_world_minus_track_mean_clarity": fixed_summary["mean_clarity"]
            - summary["mean_clarity"],
            **motion,
            "weighted_score": "NOT_COMPUTED",
            "rank": "NOT_COMPUTED",
            "winner": "NOT_COMPUTED",
        }
        records.append(record)
    return records, arrays


def residual_after_alignment(
    patches: Sequence[np.ndarray], valids: Sequence[np.ndarray]
) -> dict[str, float]:
    phase_residuals: list[float] = []
    phase_quality: list[float] = []
    flow_residuals: list[float] = []
    flow_support: list[float] = []
    for index in range(len(patches) - 1):
        valid_fraction = float(np.minimum(valids[index], valids[index + 1]).mean())
        if valid_fraction < VALID_REGION_FRACTION:
            continue
        phase = phase_shift(patches[index], patches[index + 1])
        flow = dense_flow_shift(patches[index], patches[index + 1])
        phase_residuals.append(norm2(phase["dx"], phase["dy"]))
        phase_quality.append(phase["response"])
        flow_residuals.append(norm2(flow["dx"], flow["dy"]))
        flow_support.append(flow["support_fraction"])
    return {
        "phase_aligned_residual_median_px": float(np.median(phase_residuals)),
        "phase_response_median": float(np.median(phase_quality)),
        "flow_aligned_residual_median_px": float(np.median(flow_residuals)),
        "flow_support_fraction_median": float(np.median(flow_support)),
    }


def summarize_trajectory(
    name: str,
    role: str,
    centers: Sequence[tuple[float, float] | None],
    images: Sequence[np.ndarray],
    extra: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    patches, valids, indices = stack_for_centers(images, centers)
    summary, arrays = summarize_stack(patches, valids)
    aligned_residual = residual_after_alignment(patches, valids)
    record: dict[str, Any] = {
        "counterfactual_id": name,
        "counterfactual_role": role,
        "valid_frame_count": len(indices),
        "source_frame_indices": ";".join(str(330 + index) for index in indices),
        **extra,
        **summary,
        **aligned_residual,
        "weighted_score": "NOT_COMPUTED",
        "rank": "NOT_COMPUTED",
        "winner": "NOT_COMPUTED",
    }
    return record, arrays


def spatial_counterfactuals(
    rows: Sequence[FrameRow], images: Sequence[np.ndarray]
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    configs = (
        ("CORRECT_TRACK", "VEHICLE_REFERENCE", 0, 0, "reference trajectory"),
        ("NEAR_LEFT_OVERLAP", "NEAR_OFFSET_STILL_SAME_VEHICLE", -60, 0, "not a true negative"),
        ("NEAR_RIGHT_OVERLAP", "NEAR_OFFSET_STILL_SAME_VEHICLE", 60, 0, "not a true negative"),
        ("NEAR_ABOVE_PARTIAL", "PARTIAL_OVERLAP_NEIGHBOR", 0, -60, "may retain vehicle response"),
        ("NEARBY_NONOVERLAP_BACKGROUND", "BACKGROUND_DIAGNOSTIC", -400, -240, "visually frozen nearby background role"),
        ("VERTICAL_STRONG_LINE", "WORLD_FIXED_STRONG_LINE_DIAGNOSTIC", 180, -20, "fixed-line role; may be mixed across time"),
        ("FAN_ARC", "WORLD_FIXED_FAN_ARC_DIAGNOSTIC", 0, -220, "fan-arc role"),
        ("ISOLATED_HOTSPOT", "WORLD_FIXED_HOTSPOT_DIAGNOSTIC", -350, -100, "isolated-hotspot role"),
    )
    records: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    for name, role, dx, dy, note in configs:
        centers = [(row.center_x + dx, row.center_y + dy) for row in rows]
        record, cf_arrays = summarize_trajectory(
            name,
            role,
            centers,
            images,
            {
                "dx_px": dx,
                "dy_px": dy,
                "overlap_semantics": note,
                "same_source_frames_and_processing": True,
            },
        )
        records.append(record)
        for array_name, value in cf_arrays.items():
            arrays[f"{name}_{array_name}"] = value
    return records, arrays


def shifted_centers(
    base: Sequence[tuple[float, float]], shift: int
) -> list[tuple[float, float] | None]:
    output: list[tuple[float, float] | None] = []
    for index in range(len(base)):
        source = index + shift
        output.append(base[source] if 0 <= source < len(base) else None)
    return output


def trajectory_counterfactuals(
    rows: Sequence[FrameRow], images: Sequence[np.ndarray]
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    base = [(row.center_x, row.center_y) for row in rows]
    first_x = base[0][0]
    median_center = (
        float(np.median([point[0] for point in base])),
        float(np.median([point[1] for point in base])),
    )
    rng = np.random.default_rng(SHUFFLE_SEED)
    order = rng.permutation(len(base)).tolist()
    configs: list[tuple[str, str, list[tuple[float, float] | None], dict[str, Any]]] = [
        ("CORRECT_TRACK", "REFERENCE", list(base), {"transform": "none"}),
        ("CENTER_ORDER_SHUFFLE", "TEMPORAL_CORRESPONDENCE", [base[index] for index in order], {"transform": "deterministic permutation", "seed": SHUFFLE_SEED}),
        ("CENTER_ORDER_REVERSE", "TEMPORAL_CORRESPONDENCE_ONLY", list(reversed(base)), {"transform": "reverse centre correspondence; not arrow of time"}),
    ]
    for shift in (-12, -8, -4, 4, 8, 12):
        configs.append(
            (
                f"TIME_SHIFT_{shift:+d}",
                "TEMPORAL_SHIFT",
                shifted_centers(base, shift),
                {"transform": "non-circular exact frame shift", "shift_frames": shift},
            )
        )
    for scale in (0.5, 1.5):
        centers = [(first_x + scale * (x - first_x), y) for x, y in base]
        configs.append(
            (
                f"HORIZONTAL_SPEED_SCALE_{scale:.1f}",
                "MOTION_SPEED",
                centers,
                {"transform": "horizontal displacement scale", "horizontal_speed_scale": scale},
            )
        )
    wrong_direction = [(first_x - (x - first_x), y) for x, y in base]
    configs.append(
        (
            "WRONG_HORIZONTAL_DIRECTION",
            "MOTION_DIRECTION",
            wrong_direction,
            {"transform": "constant-speed opposite horizontal direction"},
        )
    )
    configs.append(
        (
            "FIXED_MEDIAN_CENTER",
            "FIXED_CENTER",
            [median_center] * len(base),
            {"transform": "fixed coordinate-wise median centre"},
        )
    )
    records: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    for name, role, centers, extra in configs:
        record, cf_arrays = summarize_trajectory(
            name,
            role,
            centers,
            images,
            {"same_source_frames_and_processing": True, **extra},
        )
        records.append(record)
        for array_name, value in cf_arrays.items():
            arrays[f"{name}_{array_name}"] = value
    return records, arrays


def structure_orientation_deg(image: np.ndarray) -> tuple[float, float]:
    normalized = normalize_display(image).astype(np.float32)
    gx = cv2.Sobel(normalized, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(normalized, cv2.CV_32F, 0, 1, ksize=3)
    jxx = float(np.mean(gx * gx))
    jyy = float(np.mean(gy * gy))
    jxy = float(np.mean(gx * gy))
    angle = 0.5 * math.degrees(math.atan2(2.0 * jxy, jxx - jyy))
    eigen_gap = math.hypot(jxx - jyy, 2.0 * jxy)
    anisotropy = eigen_gap / max(jxx + jyy, 1e-6)
    long_axis = (angle + 90.0) % 180.0
    return float(long_axis), float(anisotropy)


def build_state_rows(
    rows: Sequence[FrameRow], images: Sequence[np.ndarray]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row, image in zip(rows, images):
        patch, valid = crop_with_padding(
            image,
            row.center_x,
            row.center_y,
            FIELD_PATCH_WIDTH,
            FIELD_PATCH_HEIGHT,
        )
        height, width = patch.shape
        response_slice = np.s_[height // 2 - 30 : height // 2 + 91, width // 2 - 140 : width // 2 + 141]
        upper_slice = np.s_[height // 2 - 91 : height // 2, width // 2 - 140 : width // 2 + 141]
        ring = np.ones_like(patch, dtype=bool)
        ring[24:-24, 24:-24] = False
        sample = patch[ring & (valid > 0)].astype(np.float32)
        background = float(np.median(sample))
        background_mad = float(np.median(np.abs(sample - background)))
        scale = max(1.4826 * background_mad, 1.0)
        z = (patch.astype(np.float32) - background) / scale
        response = patch[response_slice]
        response_z = z[response_slice]
        upper_z = z[upper_slice]
        positive = response_z >= POSITIVE_Z
        weights = np.clip(response_z - 1.0, 0, None)
        yy, xx = np.indices(response_z.shape)
        if float(weights.sum()) > 0:
            centroid_x = float((weights * xx).sum() / weights.sum() - response_z.shape[1] / 2)
            centroid_y = float((weights * yy).sum() / weights.sum() - 30)
        else:
            centroid_x = math.nan
            centroid_y = math.nan
        orientation, anisotropy = structure_orientation_deg(response)
        output.append(
            {
                "scene": "GM_RM017",
                "canonical_vehicle_id": "GM_RM017:PV002",
                "segment_id": "S0MV-GM_RM017-PV002-SEG02",
                "sar_frame_index": row.frame,
                "direct_review_stage": stage_for_frame(row.frame),
                "raw_anchor_center_x_px": row.center_x,
                "raw_anchor_center_y_px": row.center_y,
                "raw_anchor_width_px": row.width,
                "raw_anchor_height_px": row.height,
                "raw_anchor_angle_deg": row.angle,
                "response_raw_mean": float(np.mean(response)),
                "response_raw_p95": float(np.percentile(response, 95.0)),
                "local_background_median": background,
                "local_background_mad": background_mad,
                "response_z_mean": float(np.mean(response_z)),
                "response_z_p95": float(np.percentile(response_z, 95.0)),
                "response_positive_fraction": float(positive.mean()),
                "response_horizontal_run_px": max_horizontal_run(positive),
                "response_weighted_centroid_x_rel_px": finite_or_blank(centroid_x),
                "response_weighted_centroid_y_rel_px": finite_or_blank(centroid_y),
                "response_long_axis_deg": orientation,
                "response_structure_anisotropy": anisotropy,
                "upper_band_z_mean": float(np.mean(upper_z)),
                "gt_inside_used_as_vehicle_label": False,
                "stage_boundary_reselected_by_metric": False,
            }
        )
    return output


def normalized_stack_for_centers(
    images: Sequence[np.ndarray],
    centers: Sequence[tuple[float, float]],
) -> tuple[np.ndarray, np.ndarray]:
    patches, valids, _ = stack_for_centers(
        images, centers, ATTR_PATCH_WIDTH, ATTR_PATCH_HEIGHT
    )
    normalized, _, _ = local_normalized_stack(patches, valids)
    return normalized, np.stack(valids)


def build_attribution(
    rows: Sequence[FrameRow],
    images: Sequence[np.ndarray],
    background_rows: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    correct = [(row.center_x, row.center_y) for row in rows]
    fixed: list[tuple[float, float]] = [correct[0]]
    for background in background_rows:
        consensus_dx = float(
            np.median(
                [
                    background["phase_background_dx_px"],
                    background["flow_background_dx_px"],
                ]
            )
        )
        consensus_dy = float(
            np.median(
                [
                    background["phase_background_dy_px"],
                    background["flow_background_dy_px"],
                ]
            )
        )
        fixed.append((fixed[-1][0] + consensus_dx, fixed[-1][1] + consensus_dy))
    wrong = [
        (2.0 * world_x - vehicle_x, 2.0 * world_y - vehicle_y)
        for (vehicle_x, vehicle_y), (world_x, world_y) in zip(correct, fixed)
    ]
    correct_stack, correct_valid = normalized_stack_for_centers(images, correct)
    fixed_stack, fixed_valid = normalized_stack_for_centers(images, fixed)
    wrong_stack, wrong_valid = normalized_stack_for_centers(images, wrong)

    correct_persistence = np.mean(correct_stack >= POSITIVE_Z, axis=0)
    fixed_persistence = np.mean(fixed_stack >= POSITIVE_Z, axis=0)
    correct_median = np.median(correct_stack, axis=0)
    fixed_median = np.median(fixed_stack, axis=0)
    correct_mad = np.median(
        np.abs(correct_stack - np.median(correct_stack, axis=0)[None, ...]), axis=0
    )
    fixed_mad = np.median(
        np.abs(fixed_stack - np.median(fixed_stack, axis=0)[None, ...]), axis=0
    )
    wrong_mad = np.median(
        np.abs(wrong_stack - np.median(wrong_stack, axis=0)[None, ...]), axis=0
    )
    common_valid = (
        np.mean(correct_valid, axis=0) >= VALID_REGION_FRACTION
    ) & (np.mean(fixed_valid, axis=0) >= VALID_REGION_FRACTION) & (
        np.mean(wrong_valid, axis=0) >= VALID_REGION_FRACTION
    )

    category = np.full(correct_median.shape, 4, dtype=np.uint8)
    boundary = np.zeros_like(category, dtype=bool)
    boundary[:8, :] = True
    boundary[-8:, :] = True
    boundary[:, :8] = True
    boundary[:, -8:] = True
    boundary |= ~common_valid

    persistent = (
        (correct_persistence >= 0.60)
        & (correct_median >= 1.0)
        & (correct_mad < fixed_mad)
        & (correct_mad < wrong_mad)
    )
    world_fixed = (
        (fixed_persistence >= 0.50)
        & (fixed_median >= 1.0)
        & (fixed_mad < correct_mad)
        & (fixed_mad < wrong_mad)
    )
    intermittent = (
        (correct_persistence >= 0.20)
        & (correct_median >= 0.5)
        & (correct_mad < wrong_mad)
        & ~persistent
    )
    category[world_fixed] = 2
    category[intermittent] = 1
    category[persistent] = 0
    category[boundary] = 3

    counts = Counter(category.ravel().tolist())
    records = []
    for index, label in enumerate(CATEGORY_ORDER):
        pixel_count = int(counts.get(index, 0)) if index < 5 else 0
        records.append(
            {
                "scene": "GM_RM017",
                "canonical_vehicle_id": "GM_RM017:PV002",
                "segment_id": "S0MV-GM_RM017-PV002-SEG02",
                "response_category": label,
                "pixel_count": pixel_count,
                "pixel_fraction": pixel_count / float(category.size),
                "assignment_mode": (
                    "CONSERVATIVE_MULTI_EVIDENCE_EXPLORATORY"
                    if index < 5
                    else "NOT_AUTO_ASSIGNED_DESCRIPTIVE_DEBT_ONLY"
                ),
                "gt_box_inside_outside_used": False,
                "runtime_or_annotation_status": "RESEARCH_ONLY_NOT_RUNTIME_NOT_ANNOTATION",
            }
        )
    arrays = {
        "category": category,
        "correct_persistence": correct_persistence.astype(np.float32),
        "fixed_persistence": fixed_persistence.astype(np.float32),
        "correct_median_z": correct_median.astype(np.float32),
        "fixed_median_z": fixed_median.astype(np.float32),
        "correct_mad_z": correct_mad.astype(np.float32),
        "fixed_mad_z": fixed_mad.astype(np.float32),
        "wrong_mad_z": wrong_mad.astype(np.float32),
    }
    return records, arrays


def plot_offset_field(records: Sequence[dict[str, Any]], path: Path) -> None:
    fine = [record for record in records if "FINE" in record["grid_level"]]
    dx_values = sorted({int(record["dx_px"]) for record in fine})
    dy_values = sorted({int(record["dy_px"]) for record in fine})
    category_names = (
        "MOTION_COHERENT_SUPPORT_CORRIDOR",
        "BACKGROUND_DOMINATED_REGION",
        "AMBIGUOUS_OVERLAP_REGION",
        "OUTSIDE_VALID_REGION",
    )
    category_to_int = {name: index for index, name in enumerate(category_names)}
    category_grid = np.full((len(dy_values), len(dx_values)), 2, dtype=int)
    phase_delta = np.full_like(category_grid, np.nan, dtype=float)
    flow_delta = np.full_like(category_grid, np.nan, dtype=float)
    lookup_x = {value: index for index, value in enumerate(dx_values)}
    lookup_y = {value: index for index, value in enumerate(dy_values)}
    for record in fine:
        iy, ix = lookup_y[int(record["dy_px"])], lookup_x[int(record["dx_px"])]
        category_grid[iy, ix] = category_to_int[record["offset_category"]]
        phase_delta[iy, ix] = (
            float(record["phase_world_residual_median_px"])
            - float(record["phase_vehicle_residual_median_px"])
        )
        flow_delta[iy, ix] = (
            float(record["flow_world_residual_median_px"])
            - float(record["flow_vehicle_residual_median_px"])
        )
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    cmap = ListedColormap(["#2ca25f", "#756bb1", "#fdae6b", "#bdbdbd"])
    axes[0].imshow(category_grid, cmap=cmap, vmin=-0.5, vmax=3.5, origin="lower")
    axes[0].set_title("Fine-grid relational category (no winner)")
    for ax in axes:
        ax.set_xticks(range(len(dx_values)))
        ax.set_xticklabels(dx_values, rotation=45, fontsize=7)
        ax.set_yticks(range(len(dy_values)))
        ax.set_yticklabels(dy_values, fontsize=7)
        ax.set_xlabel("dx px")
        ax.set_ylabel("dy px")
    im1 = axes[1].imshow(phase_delta, cmap="coolwarm", origin="lower")
    axes[1].set_title("Phase: world residual - vehicle residual")
    fig.colorbar(im1, ax=axes[1], fraction=0.046)
    im2 = axes[2].imshow(flow_delta, cmap="coolwarm", origin="lower")
    axes[2].set_title("Flow: world residual - vehicle residual")
    fig.colorbar(im2, ax=axes[2], fraction=0.046)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_counterfactual_medians(
    records: Sequence[dict[str, Any]], arrays: dict[str, np.ndarray], path: Path
) -> None:
    cols = 4
    rows = math.ceil(len(records) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(16, 3.6 * rows), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for ax, record in zip(axes.ravel(), records):
        key = f"{record['counterfactual_id']}_median"
        ax.imshow(arrays[key], cmap="gray", vmin=DISPLAY_LO, vmax=DISPLAY_HI)
        ax.set_title(
            f"{record['counterfactual_id']}\nphase residual={float(record['phase_aligned_residual_median_px']):.2f}px, "
            f"flow={float(record['flow_aligned_residual_median_px']):.2f}px",
            fontsize=8,
        )
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_state_evidence(records: Sequence[dict[str, Any]], path: Path) -> None:
    frames = [int(record["sar_frame_index"]) for record in records]
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    axes[0].plot(frames, [float(record["response_z_mean"]) for record in records], marker="o", label="response z mean")
    axes[0].plot(frames, [float(record["upper_band_z_mean"]) for record in records], marker=".", label="upper-band z mean")
    axes[0].legend()
    axes[0].set_ylabel("robust z")
    axes[1].plot(frames, [float(record["response_positive_fraction"]) for record in records], marker="o")
    axes[1].set_ylabel("positive fraction")
    axes[2].plot(frames, [float(record["response_horizontal_run_px"]) for record in records], marker="o", label="horizontal run")
    axes[2].plot(frames, [float(record["response_structure_anisotropy"]) * 100 for record in records], marker=".", label="anisotropy x100")
    axes[2].legend()
    axes[2].set_ylabel("px / scaled proxy")
    axes[2].set_xlabel("SAR frame")
    for ax in axes:
        ax.axvline(338.5, color="gray", linestyle="--")
        ax.axvline(339.5, color="gray", linestyle=":")
        ax.grid(alpha=0.25)
    fig.suptitle("Frozen direct-review stages; metrics do not reselect the boundary")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_attribution(arrays: dict[str, np.ndarray], path: Path) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(18, 9))
    cmap = ListedColormap(["#1b9e77", "#66c2a5", "#7570b3", "#bdbdbd", "#e6ab02"])
    axes[0, 0].imshow(arrays["category"], cmap=cmap, vmin=-0.5, vmax=4.5)
    axes[0, 0].set_title("Exploratory multi-evidence category")
    keys = (
        ("correct_persistence", "Correct-track positive persistence"),
        ("fixed_persistence", "Fixed-world positive persistence"),
        ("correct_median_z", "Correct-track median z"),
        ("correct_mad_z", "Correct-track temporal MAD z"),
        ("fixed_mad_z", "Fixed-world temporal MAD z"),
        ("wrong_mad_z", "Wrong-track temporal MAD z"),
        ("fixed_median_z", "Fixed-world median z"),
    )
    for ax, (key, title) in zip(axes.ravel()[1:], keys):
        image = ax.imshow(arrays[key], cmap="viridis")
        ax.set_title(title)
        fig.colorbar(image, ax=ax, fraction=0.046)
    for ax in axes.ravel():
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_analysis_manifest(path: Path) -> None:
    records = []
    for file_path in sorted(ANALYSIS_ROOT.rglob("*")):
        if not file_path.is_file() or file_path.name == path.name:
            continue
        records.append(
            {
                "relative_path": file_path.relative_to(ANALYSIS_ROOT).as_posix(),
                "bytes": file_path.stat().st_size,
                "sha256": sha256_file(file_path),
            }
        )
    write_csv(path, records)


def main() -> None:
    global OUTPUT_ROOT, ANALYSIS_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root", type=Path, default=OUTPUT_ROOT, help="large Git-external root"
    )
    args = parser.parse_args()
    OUTPUT_ROOT = args.output_root.resolve()
    ANALYSIS_ROOT = OUTPUT_ROOT / "analysis"
    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"branch mismatch: {branch}")
    if head != EXPECTED_START_HEAD:
        raise RuntimeError(f"start HEAD mismatch: {head}")
    if sha256_file(LOCAL_FIELD_PATH) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("local-response manifest SHA256 mismatch")

    rows = load_rows()
    images = load_images(rows)

    background_rows = build_background_reference_rows(rows, images)
    write_csv(BACKGROUND_OUTPUT_PATH, background_rows)

    pair_rows = build_pair_rows(rows, images, background_rows)
    write_csv(PAIR_OUTPUT_PATH, pair_rows)

    offset_rows, offset_arrays = build_offset_field(rows, images, background_rows)
    write_csv(OFFSET_OUTPUT_PATH, offset_rows)
    np.savez_compressed(ANALYSIS_ROOT / "offset_field_arrays.npz", **offset_arrays)
    plot_offset_field(offset_rows, ANALYSIS_ROOT / "offset_field_overview.png")

    spatial_rows, spatial_arrays = spatial_counterfactuals(rows, images)
    write_csv(SPATIAL_OUTPUT_PATH, spatial_rows)
    np.savez_compressed(ANALYSIS_ROOT / "spatial_counterfactual_arrays.npz", **spatial_arrays)
    plot_counterfactual_medians(
        spatial_rows,
        spatial_arrays,
        ANALYSIS_ROOT / "spatial_counterfactual_medians.png",
    )

    trajectory_rows, trajectory_arrays = trajectory_counterfactuals(rows, images)
    write_csv(TRAJECTORY_OUTPUT_PATH, trajectory_rows)
    np.savez_compressed(
        ANALYSIS_ROOT / "trajectory_counterfactual_arrays.npz", **trajectory_arrays
    )
    plot_counterfactual_medians(
        trajectory_rows,
        trajectory_arrays,
        ANALYSIS_ROOT / "trajectory_counterfactual_medians.png",
    )

    state_rows = build_state_rows(rows, images)
    write_csv(STATE_OUTPUT_PATH, state_rows)
    plot_state_evidence(state_rows, ANALYSIS_ROOT / "response_state_evidence.png")

    attribution_rows, attribution_arrays = build_attribution(
        rows, images, background_rows
    )
    write_csv(ATTRIBUTION_OUTPUT_PATH, attribution_rows)
    np.savez_compressed(
        ANALYSIS_ROOT / "response_attribution_evidence.npz", **attribution_arrays
    )
    plot_attribution(
        attribution_arrays, ANALYSIS_ROOT / "response_attribution_evidence.png"
    )

    summary = {
        "branch": branch,
        "start_head": head,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "source_hash_match_count": len(rows),
        "frame_count": len(rows),
        "pair_count": len(pair_rows),
        "background_reference_pair_count": len(background_rows),
        "phase_background_dx_median_px": float(
            np.median([row["phase_background_dx_px"] for row in background_rows])
        ),
        "flow_background_dx_median_px": float(
            np.median([row["flow_background_dx_px"] for row in background_rows])
        ),
        "phase_gt_motion_relative_to_background_dx_median_px": float(
            np.median(
                [
                    row["phase_gt_motion_relative_to_background_dx_px"]
                    for row in background_rows
                ]
            )
        ),
        "flow_gt_motion_relative_to_background_dx_median_px": float(
            np.median(
                [
                    row["flow_gt_motion_relative_to_background_dx_px"]
                    for row in background_rows
                ]
            )
        ),
        "offset_count": len(offset_rows),
        "offset_category_counts": dict(Counter(row["offset_category"] for row in offset_rows)),
        "spatial_counterfactual_count": len(spatial_rows),
        "trajectory_counterfactual_count": len(trajectory_rows),
        "response_state_count": len(state_rows),
        "attribution_pixel_counts": {
            row["response_category"]: row["pixel_count"] for row in attribution_rows
        },
        "weighted_score": "NOT_COMPUTED",
        "rank": "NOT_COMPUTED",
        "winner": "NOT_COMPUTED",
        "final_box": "NOT_COMPUTED",
        "s1d": "NOT_ENTERED",
    }
    (ANALYSIS_ROOT / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_analysis_manifest(ANALYSIS_ROOT / "analysis_output_manifest.csv")

    log_lines = [
        "S1-LR GM_RM017 motion-coherent visible response flow runner",
        f"branch={branch}",
        f"start_head={head}",
        f"manifest_sha256={EXPECTED_MANIFEST_SHA256}",
        f"frames={len(rows)}",
        f"pairs={len(pair_rows)}",
        f"background_reference_pairs={len(background_rows)}",
        f"offsets={len(offset_rows)}",
        f"offset_categories={summary['offset_category_counts']}",
        f"analysis_root={ANALYSIS_ROOT}",
        "weighted_score=NOT_COMPUTED",
        "rank=NOT_COMPUTED",
        "winner=NOT_COMPUTED",
        "final_box=NOT_COMPUTED",
        "s1d=NOT_ENTERED",
    ]
    LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
