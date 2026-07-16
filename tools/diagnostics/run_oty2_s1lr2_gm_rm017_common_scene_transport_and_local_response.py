#!/usr/bin/env python3
from __future__ import annotations

"""Run the bounded S1-LR2 common-scene transport and local-response audit."""

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import cv2
import matplotlib
import numpy as np
from PIL import Image, ImageDraw
from scipy.interpolate import RBFInterpolator

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")
OUTPUT_ROOT = (
    WORKSPACE_ROOT
    / "output"
    / "s1_lr2_gm_rm017_common_scene_transport_local_response_20260716_final_v2"
)
LOG_PATH = (
    WORKSPACE_ROOT
    / "logs"
    / "s1_lr2_gm_rm017_common_scene_transport_local_response_20260716_runner.log"
)

LOCAL_FIELD_PATH = MANIFEST_DIR / "oty2_s1l_local_response_fields.csv"
GT_DEBT_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_gt_motion_debt.csv"
ANCHOR_TRACK_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_background_anchor_tracking.csv"
MODEL_SELECTION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_transport_model_selection.csv"
HOLDOUT_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_holdout_background_validation.csv"
STABILIZATION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_stabilization_frame_quality.csv"
REGION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_local_response_regions.csv"
COMPONENT_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_local_response_components.csv"
DIRECTION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_direction_fragments.csv"
RELATION_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_local_response_relations.csv"
MATCHED_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_matched_background_counterfactuals.csv"
SUPPORT_PATH = MANIFEST_DIR / "oty2_s1lr2_gm_rm017_visible_response_support_regions.csv"

EXPECTED_BRANCH = "feature/oty2-sar-gt-structure-foundation"
EXPECTED_START_HEAD = "8eb4b99e3fefb41ba2449c5e53ea3b7338e8591b"
EXPECTED_MANIFEST_SHA256 = (
    "029d23d80638bfe2e115324140bfcccf9e4bb15ffeadf65f1920b244afa21092"
)
EXPECTED_FRAMES = tuple(range(330, 351))
EXPECTED_SIZE = (2308, 1334)
DISPLAY_LO = 0.0
DISPLAY_HI = 85.0
POSITIVE_Z = 2.5
FAN_APEX = np.asarray([1154.0, 1334.0], dtype=np.float64)
SELECTED_MODEL = "GLOBAL_TRANSLATION"
SELECTED_OBSERVATION = "PHASE_CORRELATION"


@dataclass(frozen=True)
class FrameRow:
    frame: int
    image_path: Path
    image_sha256: str
    raw_x: float
    raw_y: float
    smooth_x: float
    smooth_y: float
    raw_w: float
    raw_h: float
    raw_angle: float
    source_gt_ids: str
    source_family: str


@dataclass(frozen=True)
class AnchorSpec:
    anchor_id: str
    role: str
    center_x: float
    center_y: float
    size: int
    split: str
    direct_identity_status: str
    direct_mixing_status: str
    description: str


@dataclass(frozen=True)
class RegionSpec:
    region_id: str
    role: str
    center_x: float
    center_y: float
    width: int
    height: int
    moving_gt_center: bool = False


ANCHORS = (
    AnchorSpec(
        "BG_A_VERTICAL_STRONG_LINE",
        "VERTICAL_STRONG_LINE",
        1277.0,
        875.0,
        96,
        "FIT",
        "CONFIRMED_CONTINUOUS_330_350",
        "NO_VEHICLE_MIXING_OBSERVED",
        "bright vertical line above/right of the discovery shell",
    ),
    AnchorSpec(
        "BG_B_FAN_ARC_CENTRAL",
        "FAN_ARC",
        1105.0,
        674.0,
        112,
        "FIT",
        "CONFIRMED_CONTINUOUS_330_350",
        "NO_VEHICLE_MIXING_OBSERVED",
        "central bright fan arc with adjacent arc texture",
    ),
    AnchorSpec(
        "BG_C_ISOLATED_HOTSPOT",
        "ISOLATED_HOTSPOT",
        893.0,
        918.0,
        88,
        "FIT",
        "CONFIRMED_CONTINUOUS_330_350",
        "NO_VEHICLE_MIXING_OBSERVED",
        "isolated bright point and short local ridge left of the shell",
    ),
    AnchorSpec(
        "BG_D_NEARBY_NONVEHICLE_CURVE",
        "NEARBY_NONVEHICLE_REGION",
        760.0,
        970.0,
        104,
        "HOLDOUT",
        "CONFIRMED_CONTINUOUS_330_350",
        "NO_VEHICLE_MIXING_OBSERVED",
        "nearby curved response outside the frozen discovery shell",
    ),
    AnchorSpec(
        "BG_E_LEFT_ARC_BRANCH",
        "ADDITIONAL_SPATIAL_BACKGROUND_1",
        617.0,
        770.0,
        112,
        "HOLDOUT",
        "CONFIRMED_CONTINUOUS_330_350",
        "NO_VEHICLE_MIXING_OBSERVED",
        "left fan-arc branch spatially separated from the vehicle",
    ),
    AnchorSpec(
        "BG_F_RIGHT_DIAGONAL_FRAGMENT",
        "ADDITIONAL_SPATIAL_BACKGROUND_2",
        1396.0,
        968.0,
        112,
        "FIT",
        "CONFIRMED_CONTINUOUS_330_350",
        "NO_VEHICLE_MIXING_OBSERVED",
        "right diagonal bright background fragment",
    ),
    AnchorSpec(
        "BG_G_UPPER_DIAGONAL_FRAGMENT",
        "ADDITIONAL_SPATIAL_BACKGROUND_3",
        1277.0,
        805.0,
        88,
        "FIT",
        "CONFIRMED_CONTINUOUS_330_350",
        "NO_VEHICLE_MIXING_OBSERVED",
        "upper diagonal background fragment, spatially separate from the vehicle shell",
    ),
    AnchorSpec(
        "BG_H_FAN_ARC_LEFT",
        "ADDITIONAL_FAN_ARC_SECTION",
        980.0,
        674.0,
        96,
        "FIT",
        "CONFIRMED_CONTINUOUS_330_350",
        "NO_VEHICLE_MIXING_OBSERVED",
        "left section of the central fan arc, spatially separate from the main arc template",
    ),
)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8"
    ).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def stage_for_frame(frame: int) -> str:
    if frame <= 338:
        return "WEAK_DISTRIBUTED_330_338"
    if frame == 339:
        return "TRANSITION_ONSET_339"
    return "STRONG_COMPACT_340_350"


def source_family(source_gt_ids: str) -> str:
    if "gm17supp_" in source_gt_ids:
        return "GM17_SUPPLEMENT"
    if "gm_rm017_" in source_gt_ids:
        return "GM_RM017_ORIGINAL"
    return "OTHER_OR_UNKNOWN"


def load_rows() -> list[FrameRow]:
    output: list[FrameRow] = []
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
            ids = row["source_gt_ids"]
            output.append(
                FrameRow(
                    frame=frame,
                    image_path=Path(row["raw_image_path"]),
                    image_sha256=row["raw_image_sha256"].lower(),
                    raw_x=float(row["raw_anchor_center_x_px"]),
                    raw_y=float(row["raw_anchor_center_y_px"]),
                    smooth_x=float(row["smoothed_anchor_center_x_px"]),
                    smooth_y=float(row["smoothed_anchor_center_y_px"]),
                    raw_w=float(row["raw_anchor_width_px"]),
                    raw_h=float(row["raw_anchor_height_px"]),
                    raw_angle=float(row["raw_anchor_angle_deg"]),
                    source_gt_ids=ids,
                    source_family=source_family(ids),
                )
            )
    output.sort(key=lambda item: item.frame)
    if tuple(row.frame for row in output) != EXPECTED_FRAMES:
        raise RuntimeError(f"unexpected frame selection: {[row.frame for row in output]}")
    return output


def load_images(rows: Sequence[FrameRow]) -> list[np.ndarray]:
    images: list[np.ndarray] = []
    for row in rows:
        if sha256_file(row.image_path) != row.image_sha256:
            raise RuntimeError(f"SHA256 mismatch: frame {row.frame}")
        image = cv2.imread(str(row.image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(f"cannot read {row.image_path}")
        if (image.shape[1], image.shape[0]) != EXPECTED_SIZE:
            raise RuntimeError(f"unexpected image size: frame {row.frame} {image.shape}")
        images.append(image)
    return images


def display_u8(image: np.ndarray) -> np.ndarray:
    value = (image.astype(np.float32) - DISPLAY_LO) * 255.0 / (DISPLAY_HI - DISPLAY_LO)
    return np.clip(value, 0, 255).astype(np.uint8)


def crop_with_padding(
    image: np.ndarray, center_x: float, center_y: float, width: int, height: int
) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    x1 = int(round(center_x - width / 2))
    y1 = int(round(center_y - height / 2))
    x2 = x1 + width
    y2 = y1 + height
    patch = np.zeros((height, width), dtype=image.dtype)
    valid = np.zeros((height, width), dtype=np.uint8)
    sx1, sy1 = max(0, x1), max(0, y1)
    sx2, sy2 = min(image.shape[1], x2), min(image.shape[0], y2)
    if sx2 > sx1 and sy2 > sy1:
        dx1, dy1 = sx1 - x1, sy1 - y1
        patch[dy1 : dy1 + sy2 - sy1, dx1 : dx1 + sx2 - sx1] = image[sy1:sy2, sx1:sx2]
        valid[dy1 : dy1 + sy2 - sy1, dx1 : dx1 + sx2 - sx1] = 1
    return patch, valid, (x1, y1)


def highpass_standardized(image: np.ndarray) -> np.ndarray:
    value = display_u8(image).astype(np.float32)
    value -= cv2.GaussianBlur(value, (0, 0), 3.0)
    value -= float(value.mean())
    scale = float(value.std())
    return value / max(scale, 1e-6)


def phase_shift(prev: np.ndarray, curr: np.ndarray) -> tuple[float, float, float]:
    a = highpass_standardized(prev)
    b = highpass_standardized(curr)
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a, b, window)
    return float(dx), float(dy), float(response)


def rough_global_shift(reference: np.ndarray, current: np.ndarray) -> tuple[float, float, float]:
    x1, y1, x2, y2 = 350, 500, 1800, 1210
    ref = reference[y1:y2, x1:x2].copy()
    cur = current[y1:y2, x1:x2].copy()
    # A fixed union shell is masked in every frame; GT motion is not used.
    ref[370:650, 470:1050] = 0
    cur[370:650, 470:1050] = 0
    return phase_shift(ref, cur)


def track_anchor_pair(
    previous: np.ndarray,
    current: np.ndarray,
    spec: AnchorSpec,
    previous_structure_center: tuple[float, float],
    previous_phase_center: tuple[float, float],
    rough_step_dx: float,
    rough_step_dy: float,
) -> dict[str, float | str]:
    template, template_valid, _ = crop_with_padding(
        previous,
        previous_structure_center[0],
        previous_structure_center[1],
        spec.size,
        spec.size,
    )
    search_radius = 18
    predicted_x = previous_structure_center[0] + rough_step_dx
    predicted_y = previous_structure_center[1] + rough_step_dy
    search, search_valid, (search_x1, search_y1) = crop_with_padding(
        current,
        predicted_x,
        predicted_y,
        spec.size + 2 * search_radius,
        spec.size + 2 * search_radius,
    )
    template_hp = highpass_standardized(template)
    search_hp = highpass_standardized(search)
    response = cv2.matchTemplate(search_hp, template_hp, cv2.TM_CCOEFF_NORMED)
    _, max_value, _, max_location = cv2.minMaxLoc(response)
    structure_x = search_x1 + max_location[0] + spec.size / 2.0
    structure_y = search_y1 + max_location[1] + spec.size / 2.0
    target_patch, target_valid, _ = crop_with_padding(
        current, structure_x, structure_y, spec.size, spec.size
    )
    phase_dx_local, phase_dy_local, phase_response = phase_shift(template, target_patch)
    structure_step_x = structure_x - previous_structure_center[0]
    structure_step_y = structure_y - previous_structure_center[1]
    phase_step_x = structure_step_x + phase_dx_local
    phase_step_y = structure_step_y + phase_dy_local
    phase_x = previous_phase_center[0] + phase_step_x
    phase_y = previous_phase_center[1] + phase_step_y
    method_disagreement = math.hypot(
        phase_step_x - structure_step_x, phase_step_y - structure_step_y
    )
    valid_fraction = float(
        min(template_valid.mean(), search_valid.mean(), target_valid.mean())
    )
    switch_suspected = (
        max_value < 0.10 or phase_response < 0.02 or method_disagreement > 4.0
    )
    return {
        "structure_center_x_px": structure_x,
        "structure_center_y_px": structure_y,
        "structure_dx_from_reference_px": structure_x - spec.center_x,
        "structure_dy_from_reference_px": structure_y - spec.center_y,
        "structure_step_dx_px": structure_step_x,
        "structure_step_dy_px": structure_step_y,
        "structure_match_quality": float(max_value),
        "phase_center_x_px": phase_x,
        "phase_center_y_px": phase_y,
        "phase_dx_from_reference_px": phase_x - spec.center_x,
        "phase_dy_from_reference_px": phase_y - spec.center_y,
        "phase_step_dx_px": phase_step_x,
        "phase_step_dy_px": phase_step_y,
        "phase_response": phase_response,
        "method_disagreement_px": method_disagreement,
        "valid_fraction": valid_fraction,
        "algorithmic_structure_switch_suspected": str(switch_suspected).lower(),
    }


def build_anchor_tracking(
    rows: Sequence[FrameRow], images: Sequence[np.ndarray]
) -> tuple[list[dict[str, Any]], dict[int, tuple[float, float, float]]]:
    output: list[dict[str, Any]] = []
    rough: dict[int, tuple[float, float, float]] = {}
    previous_structure = {
        spec.anchor_id: (spec.center_x, spec.center_y) for spec in ANCHORS
    }
    previous_phase = {
        spec.anchor_id: (spec.center_x, spec.center_y) for spec in ANCHORS
    }
    cumulative_rough_x = 0.0
    cumulative_rough_y = 0.0
    for index, (row, image) in enumerate(zip(rows, images)):
        if index == 0:
            rough_step_dx = rough_step_dy = 0.0
            rough_quality = 1.0
        else:
            rough_step_dx, rough_step_dy, rough_quality = rough_global_shift(
                images[index - 1], image
            )
            cumulative_rough_x += rough_step_dx
            cumulative_rough_y += rough_step_dy
        rough[row.frame] = (cumulative_rough_x, cumulative_rough_y, rough_quality)
        for spec in ANCHORS:
            if index == 0:
                evidence: dict[str, float | str] = {
                    "structure_center_x_px": spec.center_x,
                    "structure_center_y_px": spec.center_y,
                    "structure_dx_from_reference_px": 0.0,
                    "structure_dy_from_reference_px": 0.0,
                    "structure_step_dx_px": 0.0,
                    "structure_step_dy_px": 0.0,
                    "structure_match_quality": 1.0,
                    "phase_center_x_px": spec.center_x,
                    "phase_center_y_px": spec.center_y,
                    "phase_dx_from_reference_px": 0.0,
                    "phase_dy_from_reference_px": 0.0,
                    "phase_step_dx_px": 0.0,
                    "phase_step_dy_px": 0.0,
                    "phase_response": 1.0,
                    "method_disagreement_px": 0.0,
                    "valid_fraction": 1.0,
                    "algorithmic_structure_switch_suspected": "false",
                }
            else:
                evidence = track_anchor_pair(
                    images[index - 1],
                    image,
                    spec,
                    previous_structure[spec.anchor_id],
                    previous_phase[spec.anchor_id],
                    rough_step_dx,
                    rough_step_dy,
                )
            previous_structure[spec.anchor_id] = (
                float(evidence["structure_center_x_px"]),
                float(evidence["structure_center_y_px"]),
            )
            previous_phase[spec.anchor_id] = (
                float(evidence["phase_center_x_px"]),
                float(evidence["phase_center_y_px"]),
            )
            output.append(
                {
                    "scene": "GM_RM017",
                    "canonical_vehicle_id": "GM_RM017:PV002",
                    "frame": row.frame,
                    "anchor_id": spec.anchor_id,
                    "anchor_role": spec.role,
                    "fit_or_holdout": spec.split,
                    "reference_center_x_px": spec.center_x,
                    "reference_center_y_px": spec.center_y,
                    "template_size_px": spec.size,
                    "rough_background_step_dx_px": rough_step_dx,
                    "rough_background_step_dy_px": rough_step_dy,
                    "rough_background_cumulative_dx_px": cumulative_rough_x,
                    "rough_background_cumulative_dy_px": cumulative_rough_y,
                    "rough_background_phase_response": rough_quality,
                    **evidence,
                    "direct_identity_status": spec.direct_identity_status,
                    "direct_mixing_status": spec.direct_mixing_status,
                    "anchor_description": spec.description,
                    "vehicle_region_used_for_fit": "false",
                }
            )
    return output, rough


def anchor_points(
    tracking: Sequence[dict[str, Any]], frame: int, split: str, method: str
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    selected = [
        row
        for row in tracking
        if int(row["frame"]) == frame and row["fit_or_holdout"] == split
    ]
    reference = np.asarray(
        [[float(row["reference_center_x_px"]), float(row["reference_center_y_px"])] for row in selected],
        dtype=np.float64,
    )
    prefix = "structure" if method == "LOCAL_STRUCTURE_MATCH" else "phase"
    observed = np.asarray(
        [[float(row[f"{prefix}_center_x_px"]), float(row[f"{prefix}_center_y_px"])] for row in selected],
        dtype=np.float64,
    )
    return reference, observed, [str(row["anchor_id"]) for row in selected]


def fit_translation(reference: np.ndarray, observed: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
    shift = np.median(observed - reference, axis=0)
    return lambda points: np.asarray(points, dtype=np.float64) + shift


def fit_affine(reference: np.ndarray, observed: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
    design = np.column_stack([reference, np.ones(len(reference))])
    coef_x, *_ = np.linalg.lstsq(design, observed[:, 0], rcond=None)
    coef_y, *_ = np.linalg.lstsq(design, observed[:, 1], rcond=None)

    def predict(points: np.ndarray) -> np.ndarray:
        p = np.asarray(points, dtype=np.float64)
        d = np.column_stack([p, np.ones(len(p))])
        return np.column_stack([d @ coef_x, d @ coef_y])

    return predict


def radial_features(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    delta = np.asarray(points, dtype=np.float64) - FAN_APEX
    radius = np.linalg.norm(delta, axis=1)
    radial = delta / np.maximum(radius[:, None], 1e-6)
    tangent = np.column_stack([-radial[:, 1], radial[:, 0]])
    theta = np.arctan2(delta[:, 1], delta[:, 0])
    design = np.column_stack(
        [np.ones(len(points)), (radius - 450.0) / 300.0, (theta + math.pi / 2.0)]
    )
    return design, radial, tangent


def fit_radial_tangential(
    reference: np.ndarray, observed: np.ndarray
) -> Callable[[np.ndarray], np.ndarray]:
    design, radial, tangent = radial_features(reference)
    displacement = observed - reference
    dr = np.sum(displacement * radial, axis=1)
    dt = np.sum(displacement * tangent, axis=1)
    coef_r, *_ = np.linalg.lstsq(design, dr, rcond=None)
    coef_t, *_ = np.linalg.lstsq(design, dt, rcond=None)

    def predict(points: np.ndarray) -> np.ndarray:
        p = np.asarray(points, dtype=np.float64)
        d, er, et = radial_features(p)
        disp = (d @ coef_r)[:, None] * er + (d @ coef_t)[:, None] * et
        return p + disp

    return predict


def fit_thin_plate(reference: np.ndarray, observed: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
    displacement = observed - reference
    interpolator = RBFInterpolator(
        reference, displacement, kernel="thin_plate_spline", smoothing=0.5
    )
    return lambda points: np.asarray(points, dtype=np.float64) + interpolator(
        np.asarray(points, dtype=np.float64)
    )


MODEL_BUILDERS: dict[str, tuple[int, Callable[[np.ndarray, np.ndarray], Callable[[np.ndarray], np.ndarray]]]] = {
    "GLOBAL_TRANSLATION": (2, fit_translation),
    "LOCAL_AFFINE": (6, fit_affine),
    "RADIAL_TANGENTIAL_LINEAR_FIELD": (6, fit_radial_tangential),
    "SPARSE_THIN_PLATE_FIELD": (12, fit_thin_plate),
}


def model_residual_rows(
    tracking: Sequence[dict[str, Any]], rows: Sequence[FrameRow]
) -> tuple[list[dict[str, Any]], dict[int, Callable[[np.ndarray], np.ndarray]]]:
    per_model_values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    selected_predictors: dict[int, Callable[[np.ndarray], np.ndarray]] = {}
    for frame_row in rows:
        frame = frame_row.frame
        for method in ("LOCAL_STRUCTURE_MATCH", "PHASE_CORRELATION"):
            fit_ref, fit_obs, _ = anchor_points(tracking, frame, "FIT", method)
            hold_ref, hold_obs, _ = anchor_points(tracking, frame, "HOLDOUT", method)
            for model_id, (_, builder) in MODEL_BUILDERS.items():
                predictor = builder(fit_ref, fit_obs)
                fit_residual = np.linalg.norm(predictor(fit_ref) - fit_obs, axis=1)
                hold_residual = np.linalg.norm(predictor(hold_ref) - hold_obs, axis=1)
                per_model_values[(model_id, method, "FIT")].extend(fit_residual.tolist())
                per_model_values[(model_id, method, "HOLDOUT")].extend(hold_residual.tolist())
                if method == SELECTED_OBSERVATION and model_id == SELECTED_MODEL:
                    selected_predictors[frame] = predictor
    output: list[dict[str, Any]] = []
    for model_id, (complexity, _) in MODEL_BUILDERS.items():
        for method in ("LOCAL_STRUCTURE_MATCH", "PHASE_CORRELATION"):
            for split in ("FIT", "HOLDOUT"):
                values = np.asarray(per_model_values[(model_id, method, split)], dtype=float)
                output.append(
                    {
                        "model_id": model_id,
                        "observation_method": method,
                        "evaluation_split": split,
                        "residual_count": len(values),
                        "residual_median_px": float(np.median(values)),
                        "residual_p90_px": float(np.percentile(values, 90.0)),
                        "residual_max_px": float(np.max(values)),
                        "parameter_complexity": complexity,
                        "selected_for_stabilization": str(
                            model_id == SELECTED_MODEL and method == SELECTED_OBSERVATION
                        ).lower(),
                        "selection_rule": "MINIMUM_SUFFICIENT_BY_FIT_AND_HOLDOUT_RESIDUALS_WITHOUT_COMPOSITE_SCORE",
                    }
                )
    return output, selected_predictors


def selected_shifts(
    predictors: dict[int, Callable[[np.ndarray], np.ndarray]], rows: Sequence[FrameRow]
) -> dict[int, tuple[float, float]]:
    origin = np.asarray([[0.0, 0.0]], dtype=np.float64)
    shifts: dict[int, tuple[float, float]] = {}
    for row in rows:
        predicted = predictors[row.frame](origin)[0]
        shifts[row.frame] = (float(predicted[0]), float(predicted[1]))
    return shifts


def holdout_rows(
    tracking: Sequence[dict[str, Any]],
    predictors: dict[int, Callable[[np.ndarray], np.ndarray]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in tracking:
        if row["fit_or_holdout"] != "HOLDOUT":
            continue
        frame = int(row["frame"])
        reference = np.asarray(
            [[float(row["reference_center_x_px"]), float(row["reference_center_y_px"])]],
            dtype=np.float64,
        )
        predicted = predictors[frame](reference)[0]
        for method, prefix in (
            ("LOCAL_STRUCTURE_MATCH", "structure"),
            ("PHASE_CORRELATION", "phase"),
        ):
            observed = np.asarray(
                [float(row[f"{prefix}_center_x_px"]), float(row[f"{prefix}_center_y_px"])]
            )
            raw_residual = float(np.linalg.norm(observed - reference[0]))
            stabilized_residual = float(np.linalg.norm(observed - predicted))
            output.append(
                {
                    "frame": frame,
                    "anchor_id": row["anchor_id"],
                    "observation_method": method,
                    "raw_displacement_from_reference_px": raw_residual,
                    "post_stabilization_residual_px": stabilized_residual,
                    "residual_reduction_px": raw_residual - stabilized_residual,
                    "residual_reduction_fraction": (
                        (raw_residual - stabilized_residual) / raw_residual
                        if raw_residual > 1e-9
                        else 0.0
                    ),
                    "selected_model": SELECTED_MODEL,
                    "vehicle_gt_used_for_model_fit": "false",
                }
            )
    return output


def stabilize_images(
    images: Sequence[np.ndarray], rows: Sequence[FrameRow], shifts: dict[int, tuple[float, float]]
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], list[dict[str, Any]]]:
    stabilized: list[np.ndarray] = []
    valids: list[np.ndarray] = []
    impacts: list[np.ndarray] = []
    quality: list[dict[str, Any]] = []
    ones = np.full(images[0].shape, 255, dtype=np.uint8)
    for image, row in zip(images, rows):
        tx, ty = shifts[row.frame]
        matrix = np.asarray([[1.0, 0.0, -tx], [0.0, 1.0, -ty]], dtype=np.float32)
        linear = cv2.warpAffine(
            image,
            matrix,
            EXPECTED_SIZE,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        nearest = cv2.warpAffine(
            image,
            matrix,
            EXPECTED_SIZE,
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        valid = cv2.warpAffine(
            ones,
            matrix,
            EXPECTED_SIZE,
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        impact = cv2.absdiff(linear, nearest)
        stabilized.append(linear)
        valids.append(valid)
        impacts.append(impact)
        valid_bool = valid > 0
        quality.append(
            {
                "frame": row.frame,
                "selected_transport_dx_px": tx,
                "selected_transport_dy_px": ty,
                "valid_fraction": float(valid_bool.mean()),
                "interpolation_affected_fraction": float(
                    ((impact > 0) & valid_bool).mean()
                ),
                "interpolation_abs_difference_mean": float(
                    impact[valid_bool].mean() if valid_bool.any() else 0.0
                ),
                "selected_model": SELECTED_MODEL,
                "selected_observation": SELECTED_OBSERVATION,
            }
        )
    return stabilized, valids, impacts, quality


def build_gt_debt(
    rows: Sequence[FrameRow], shifts: dict[int, tuple[float, float]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    raw_steps: list[np.ndarray] = []
    smooth_steps: list[np.ndarray] = []
    background_steps: list[np.ndarray] = []
    for index, row in enumerate(rows):
        tx, ty = shifts[row.frame]
        current_raw = np.asarray([row.raw_x, row.raw_y])
        current_smooth = np.asarray([row.smooth_x, row.smooth_y])
        raw_step = smooth_step = background_step = None
        raw_acceleration = smooth_acceleration = None
        source_switch = False
        if index > 0:
            previous = rows[index - 1]
            ptx, pty = shifts[previous.frame]
            raw_step = current_raw - np.asarray([previous.raw_x, previous.raw_y])
            smooth_step = current_smooth - np.asarray([previous.smooth_x, previous.smooth_y])
            background_step = np.asarray([tx - ptx, ty - pty])
            raw_steps.append(raw_step)
            smooth_steps.append(smooth_step)
            background_steps.append(background_step)
            source_switch = row.source_family != previous.source_family
            if index > 1:
                raw_acceleration = raw_steps[-1] - raw_steps[-2]
                smooth_acceleration = smooth_steps[-1] - smooth_steps[-2]
        output.append(
            {
                "frame": row.frame,
                "source_gt_ids": row.source_gt_ids,
                "source_family": row.source_family,
                "source_family_switch_from_previous": str(source_switch).lower(),
                "raw_center_x_px": row.raw_x,
                "raw_center_y_px": row.raw_y,
                "smoothed_center_x_px": row.smooth_x,
                "smoothed_center_y_px": row.smooth_y,
                "common_transport_cumulative_x_px": tx,
                "common_transport_cumulative_y_px": ty,
                "raw_cumulative_x_px": row.raw_x - rows[0].raw_x,
                "raw_cumulative_y_px": row.raw_y - rows[0].raw_y,
                "smoothed_cumulative_x_px": row.smooth_x - rows[0].smooth_x,
                "smoothed_cumulative_y_px": row.smooth_y - rows[0].smooth_y,
                "raw_stabilized_x_px": row.raw_x - tx,
                "raw_stabilized_y_px": row.raw_y - ty,
                "smoothed_stabilized_x_px": row.smooth_x - tx,
                "smoothed_stabilized_y_px": row.smooth_y - ty,
                "raw_dx_px": "" if raw_step is None else float(raw_step[0]),
                "raw_dy_px": "" if raw_step is None else float(raw_step[1]),
                "smoothed_dx_px": "" if smooth_step is None else float(smooth_step[0]),
                "smoothed_dy_px": "" if smooth_step is None else float(smooth_step[1]),
                "common_transport_dx_px": "" if background_step is None else float(background_step[0]),
                "common_transport_dy_px": "" if background_step is None else float(background_step[1]),
                "raw_relative_transport_dx_px": "" if raw_step is None else float(raw_step[0] - background_step[0]),
                "raw_relative_transport_dy_px": "" if raw_step is None else float(raw_step[1] - background_step[1]),
                "smoothed_relative_transport_dx_px": "" if smooth_step is None else float(smooth_step[0] - background_step[0]),
                "smoothed_relative_transport_dy_px": "" if smooth_step is None else float(smooth_step[1] - background_step[1]),
                "raw_speed_px_per_frame": "" if raw_step is None else float(np.linalg.norm(raw_step)),
                "smoothed_speed_px_per_frame": "" if smooth_step is None else float(np.linalg.norm(smooth_step)),
                "common_transport_speed_px_per_frame": "" if background_step is None else float(np.linalg.norm(background_step)),
                "raw_acceleration_px_per_frame2": "" if raw_acceleration is None else float(np.linalg.norm(raw_acceleration)),
                "smoothed_acceleration_px_per_frame2": "" if smooth_acceleration is None else float(np.linalg.norm(smooth_acceleration)),
                "gt_neighborhood_position_reference": "ALLOWED_DISCOVERY_AND_POSTHOC",
                "gt_full_window_trajectory_reference": "ALLOWED_WITH_RAW_SMOOTHED_TRANSPORT_DEBT",
                "gt_adjacent_physical_displacement_truth": "NOT_ESTABLISHED",
            }
        )
    return output


def robust_z(patch: np.ndarray) -> tuple[np.ndarray, float, float]:
    h, w = patch.shape
    border = np.ones_like(patch, dtype=bool)
    border[int(0.18 * h) : int(0.82 * h), int(0.18 * w) : int(0.82 * w)] = False
    sample = patch[border].astype(np.float32)
    median = float(np.median(sample))
    mad = float(np.median(np.abs(sample - median)))
    scale = max(1.4826 * mad, 1.0)
    return (patch.astype(np.float32) - median) / scale, median, mad


def angle_horizontal_distance(angle: float) -> float:
    angle = angle % 180.0
    return min(angle, 180.0 - angle)


def component_features(
    mask: np.ndarray,
    z: np.ndarray,
    intensity: np.ndarray,
    region: RegionSpec,
    frame: int,
) -> list[dict[str, Any]]:
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    output: list[dict[str, Any]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 4:
            continue
        yy, xx = np.nonzero(labels == label)
        coords = np.column_stack([xx, yy]).astype(np.float64)
        centered = coords - coords.mean(axis=0)
        covariance = centered.T @ centered / max(len(coords), 1)
        values, vectors = np.linalg.eigh(covariance)
        order = np.argsort(values)[::-1]
        values = values[order]
        axis = vectors[:, order[0]]
        orientation = math.degrees(math.atan2(axis[1], axis[0])) % 180.0
        length = 4.0 * math.sqrt(max(values[0], 0.0))
        width = 4.0 * math.sqrt(max(values[1], 0.0))
        cx, cy = centroids[label]
        rel_x = cx - region.width / 2.0
        rel_y = cy - region.height / 2.0
        horizontal = angle_horizontal_distance(orientation) <= 22.5
        if horizontal and length >= 35.0 and 0.0 <= rel_y <= 95.0:
            role = "LOWER_HORIZONTAL_RESPONSE_SEGMENT"
        elif horizontal and length >= 12.0 and -95.0 <= rel_y < 20.0:
            role = "UPPER_INTERMITTENT_DIRECTIONAL_SEGMENT"
        elif area <= 80 and max(length, width) <= 28.0:
            role = "LOCAL_HOTSPOT"
        else:
            role = "OTHER_LOCAL_RESPONSE_COMPONENT"
        output.append(
            {
                "frame": frame,
                "stage": stage_for_frame(frame),
                "region_id": region.region_id,
                "region_role": region.role,
                "component_id": f"{region.region_id}|{frame}|CC{label:03d}",
                "component_role": role,
                "area_px": area,
                "center_x_local_px": float(cx),
                "center_y_local_px": float(cy),
                "center_x_stabilized_px": float(region.center_x - region.width / 2.0 + cx),
                "center_y_stabilized_px": float(region.center_y - region.height / 2.0 + cy),
                "relative_x_px": float(rel_x),
                "relative_y_px": float(rel_y),
                "length_px": float(length),
                "width_px": float(width),
                "orientation_deg": float(orientation),
                "horizontal_angle_distance_deg": float(angle_horizontal_distance(orientation)),
                "mean_robust_z": float(z[labels == label].mean()),
                "peak_robust_z": float(z[labels == label].max()),
                "mean_raw_intensity": float(intensity[labels == label].mean()),
                "gt_inside_outside_pixel_label_used": "false",
            }
        )
    return output


def direction_fragments(
    patch: np.ndarray, region: RegionSpec, frame: int
) -> list[dict[str, Any]]:
    detector = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    lines = detector.detect(display_u8(patch))[0]
    output: list[dict[str, Any]] = []
    if lines is None:
        return output
    for index, line in enumerate(lines[:, 0, :]):
        x1, y1, x2, y2 = map(float, line)
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 14.0:
            continue
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        output.append(
            {
                "frame": frame,
                "stage": stage_for_frame(frame),
                "region_id": region.region_id,
                "fragment_id": f"{region.region_id}|{frame}|LS{index:03d}",
                "x1_local_px": x1,
                "y1_local_px": y1,
                "x2_local_px": x2,
                "y2_local_px": y2,
                "center_x_stabilized_px": region.center_x - region.width / 2.0 + (x1 + x2) / 2.0,
                "center_y_stabilized_px": region.center_y - region.height / 2.0 + (y1 + y2) / 2.0,
                "length_px": length,
                "orientation_deg": angle,
                "horizontal_angle_distance_deg": angle_horizontal_distance(angle),
                "representation": "LOCAL_DIRECTION_FRAGMENT_LSD",
            }
        )
    return output


def boolean_runs(values: np.ndarray, gap_close: int) -> list[tuple[int, int]]:
    closed = cv2.morphologyEx(
        values.astype(np.uint8)[None, :],
        cv2.MORPH_CLOSE,
        np.ones((1, gap_close), dtype=np.uint8),
    )[0]
    padded = np.pad(closed, (1, 1))
    transitions = np.diff(padded.astype(np.int8))
    starts = np.where(transitions == 1)[0]
    ends = np.where(transitions == -1)[0]
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def relation_row(
    frame: int,
    region: RegionSpec,
    components: Sequence[dict[str, Any]],
    response_mask: np.ndarray,
    z: np.ndarray,
) -> dict[str, Any]:
    hotspots = [row for row in components if row["component_role"] == "LOCAL_HOTSPOT"]
    height, width = response_mask.shape
    lower_y1 = max(0, int(round(height / 2.0 - 8.0)))
    lower_y2 = min(height, int(round(height / 2.0 + 68.0)))
    lower_projection = response_mask[lower_y1:lower_y2].sum(axis=0)
    lower_runs = [run for run in boolean_runs(lower_projection >= 2, 9) if run[1] - run[0] >= 30]
    main_run = max(lower_runs, key=lambda run: run[1] - run[0]) if lower_runs else None
    if main_run is not None:
        x1, x2 = main_run
        selected = response_mask[lower_y1:lower_y2, x1:x2]
        yy, xx = np.nonzero(selected)
        main_x = float(x1 + xx.mean() - width / 2.0)
        main_y = float(lower_y1 + yy.mean() - height / 2.0)
        min_x = float(x1 - width / 2.0)
        max_x = float(x2 - width / 2.0)
        span = float(x2 - x1)
        main_z = float(z[lower_y1:lower_y2, x1:x2][selected].mean())
    else:
        main_x = main_y = span = main_z = math.nan
        min_x = max_x = math.nan
    upper_y1 = max(0, int(round(height / 2.0 - 72.0)))
    upper_y2 = max(upper_y1 + 1, int(round(height / 2.0 + 4.0)))
    upper_projection = response_mask[upper_y1:upper_y2].sum(axis=0)
    upper_runs = [run for run in boolean_runs(upper_projection >= 2, 7) if run[1] - run[0] >= 12]
    upper_run = max(upper_runs, key=lambda run: run[1] - run[0]) if upper_runs else None
    if upper_run is not None:
        ux1, ux2 = upper_run
        selected = response_mask[upper_y1:upper_y2, ux1:ux2]
        yy, xx = np.nonzero(selected)
        upper_x = float(ux1 + xx.mean() - width / 2.0)
        upper_y = float(upper_y1 + yy.mean() - height / 2.0)
        upper_main_dx = upper_x - main_x if main_run is not None else math.nan
        upper_main_dy = upper_y - main_y if main_run is not None else math.nan
    else:
        upper_x = upper_y = upper_main_dx = upper_main_dy = math.nan
    left_endpoint = right_endpoint = False
    if main_run is not None:
        for hotspot in hotspots:
            hx = float(hotspot["relative_x_px"])
            hy = float(hotspot["relative_y_px"])
            if abs(hy - main_y) <= 42.0 and abs(hx - min_x) <= 35.0:
                left_endpoint = True
            if abs(hy - main_y) <= 42.0 and abs(hx - max_x) <= 35.0:
                right_endpoint = True
    return {
        "frame": frame,
        "stage": stage_for_frame(frame),
        "region_id": region.region_id,
        "region_role": region.role,
        "lower_main_segment_count": len(lower_runs),
        "upper_segment_count": len(upper_runs),
        "hotspot_count": len(hotspots),
        "main_band_present": str(main_run is not None).lower(),
        "main_band_center_x_relative_px": "" if main_run is None else main_x,
        "main_band_center_y_relative_px": "" if main_run is None else main_y,
        "main_band_horizontal_span_px": "" if main_run is None else span,
        "main_band_mean_robust_z": "" if main_run is None else main_z,
        "upper_response_present": str(upper_run is not None).lower(),
        "upper_center_x_relative_px": "" if upper_run is None else upper_x,
        "upper_center_y_relative_px": "" if upper_run is None else upper_y,
        "upper_to_main_dx_px": "" if not (main_run is not None and upper_run is not None) else upper_main_dx,
        "upper_to_main_dy_px": "" if not (main_run is not None and upper_run is not None) else upper_main_dy,
        "left_endpoint_hotspot_present": str(left_endpoint).lower(),
        "right_endpoint_hotspot_present": str(right_endpoint).lower(),
        "multi_part_relation_present": str(bool(main_run is not None and (upper_run is not None or left_endpoint or right_endpoint))).lower(),
        "relation_representation": "FRAGMENT_TOLERANT_HORIZONTAL_PROJECTION_PLUS_COMPONENT_ENDPOINTS",
    }


def local_response_analysis(
    rows: Sequence[FrameRow],
    stabilized: Sequence[np.ndarray],
    shifts: dict[int, tuple[float, float]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, np.ndarray],
]:
    ref_x, ref_y = rows[0].raw_x, rows[0].raw_y
    fixed_regions = (
        RegionSpec("FROZEN_COARSE_CENTER_CORRIDOR", "VEHICLE_DISCOVERY_CORRIDOR", ref_x, ref_y + 28.0, 300, 150),
        RegionSpec("EXPANDED_NEIGHBORHOOD", "EXPANDED_VEHICLE_DISCOVERY_NEIGHBORHOOD", ref_x, ref_y + 15.0, 520, 300),
        RegionSpec("MATCHED_BG_RIGHT_COMPLEX", "MATCHED_BACKGROUND", 1405.0, 1000.0, 300, 150),
        RegionSpec("MATCHED_BG_LEFT_CURVE", "MATCHED_BACKGROUND", 735.0, 1000.0, 300, 150),
        RegionSpec("MATCHED_BG_FAN_ARC", "MATCHED_BACKGROUND", 1100.0, 755.0, 300, 150),
    )
    region_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    direction_rows: list[dict[str, Any]] = []
    relation_rows: list[dict[str, Any]] = []
    z_stacks: dict[str, list[np.ndarray]] = defaultdict(list)
    for frame_row, image in zip(rows, stabilized):
        tx, ty = shifts[frame_row.frame]
        moving_wide = RegionSpec(
            "WIDE_GT_NEIGHBORHOOD",
            "GT_DISCOVERY_ONLY_WIDE_NEIGHBORHOOD",
            frame_row.raw_x - tx,
            frame_row.raw_y - ty + 15.0,
            380,
            230,
            True,
        )
        for region in (moving_wide, *fixed_regions):
            patch, valid, _ = crop_with_padding(
                image, region.center_x, region.center_y, region.width, region.height
            )
            z, median, mad = robust_z(patch)
            response_mask = (z >= POSITIVE_Z) & (valid > 0)
            components = component_features(
                response_mask, z, patch, region, frame_row.frame
            )
            component_rows.extend(components)
            if region.width == 300 and region.height == 150:
                direction_rows.extend(direction_fragments(patch, region, frame_row.frame))
            relation_rows.append(
                relation_row(frame_row.frame, region, components, response_mask, z)
            )
            z_stacks[region.region_id].append(z)
            gx = cv2.Sobel(display_u8(patch).astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(display_u8(patch).astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
            region_rows.append(
                {
                    "frame": frame_row.frame,
                    "stage": stage_for_frame(frame_row.frame),
                    "region_id": region.region_id,
                    "region_role": region.role,
                    "center_x_stabilized_px": region.center_x,
                    "center_y_stabilized_px": region.center_y,
                    "width_px": region.width,
                    "height_px": region.height,
                    "moving_gt_center": str(region.moving_gt_center).lower(),
                    "valid_fraction": float(valid.mean()),
                    "local_background_median": median,
                    "local_background_mad": mad,
                    "mean_intensity": float(patch.mean()),
                    "positive_response_fraction": float(response_mask.mean()),
                    "edge_density": float((np.hypot(gx, gy) >= 30.0).mean()),
                    "radial_distance_from_fan_apex_px": float(
                        np.linalg.norm(np.asarray([region.center_x, region.center_y]) - FAN_APEX)
                    ),
                    "same_stabilization_and_interpolation": "true",
                    "gt_inside_outside_pixel_label_used": "false",
                }
            )
    matched_rows = build_matched_background_rows(region_rows, relation_rows)
    return (
        region_rows,
        component_rows,
        direction_rows,
        relation_rows,
        matched_rows,
        {key: np.stack(value) for key, value in z_stacks.items()},
    )


def numeric_values(rows: Iterable[dict[str, Any]], key: str) -> list[float]:
    output: list[float] = []
    for row in rows:
        value = row.get(key, "")
        if value not in ("", None):
            output.append(float(value))
    return output


def build_matched_background_rows(
    region_rows: Sequence[dict[str, Any]], relation_rows: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    region_ids = sorted({str(row["region_id"]) for row in relation_rows})
    for region_id in region_ids:
        for stage in (
            "WEAK_DISTRIBUTED_330_338",
            "TRANSITION_ONSET_339",
            "STRONG_COMPACT_340_350",
        ):
            relations = [
                row
                for row in relation_rows
                if row["region_id"] == region_id and row["stage"] == stage
            ]
            regions = [
                row
                for row in region_rows
                if row["region_id"] == region_id and row["stage"] == stage
            ]
            spans = numeric_values(relations, "main_band_horizontal_span_px")
            main_z = numeric_values(relations, "main_band_mean_robust_z")
            main_y = numeric_values(relations, "main_band_center_y_relative_px")
            upper_dy = numeric_values(relations, "upper_to_main_dy_px")
            output.append(
                {
                    "region_id": region_id,
                    "region_role": relations[0]["region_role"] if relations else "",
                    "stage": stage,
                    "frame_count": len(relations),
                    "main_band_present_fraction": float(
                        np.mean([row["main_band_present"] == "true" for row in relations])
                    ),
                    "main_band_span_median_px": "" if not spans else float(np.median(spans)),
                    "main_band_mean_robust_z_median": "" if not main_z else float(np.median(main_z)),
                    "lower_side_bias_fraction": float(
                        np.mean([value > 0 for value in main_y]) if main_y else 0.0
                    ),
                    "upper_relation_present_fraction": float(
                        np.mean([row["upper_response_present"] == "true" and row["main_band_present"] == "true" for row in relations])
                    ),
                    "upper_to_main_dy_median_px": "" if not upper_dy else float(np.median(upper_dy)),
                    "multi_part_relation_fraction": float(
                        np.mean([row["multi_part_relation_present"] == "true" for row in relations])
                    ),
                    "positive_response_fraction_mean": float(
                        np.mean([float(row["positive_response_fraction"]) for row in regions])
                    ),
                    "local_background_median_mean": float(
                        np.mean([float(row["local_background_median"]) for row in regions])
                    ),
                    "local_background_mad_mean": float(
                        np.mean([float(row["local_background_mad"]) for row in regions])
                    ),
                    "edge_density_mean": float(
                        np.mean([float(row["edge_density"]) for row in regions])
                    ),
                    "radial_distance_mean_px": float(
                        np.mean([float(row["radial_distance_from_fan_apex_px"]) for row in regions])
                    ),
                    "weighted_score": "NOT_COMPUTED",
                    "ranking": "NOT_COMPUTED",
                }
            )
    return output


def support_regions(
    z_stacks: dict[str, np.ndarray], output_root: Path
) -> list[dict[str, Any]]:
    expanded = z_stacks["EXPANDED_NEIGHBORHOOD"]
    persistence = np.mean(expanded >= POSITIVE_Z, axis=0)
    height, width = persistence.shape
    coarse = np.zeros_like(persistence, dtype=bool)
    coarse_width, coarse_height = 300, 150
    x1 = (width - coarse_width) // 2
    y1 = (height - coarse_height) // 2 + 13
    coarse[y1 : y1 + coarse_height, x1 : x1 + coarse_width] = True
    persistent_mask = (persistence >= 0.60) & coarse
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        persistent_mask.astype(np.uint8), connectivity=8
    )
    core = np.zeros_like(persistent_mask)
    for label in range(1, count):
        area = stats[label, cv2.CC_STAT_AREA]
        w = stats[label, cv2.CC_STAT_WIDTH]
        h = stats[label, cv2.CC_STAT_HEIGHT]
        if area >= 20 and w >= 2.0 * max(h, 1) and w >= 30:
            core |= labels == label
    intermittent = (persistence >= 0.20) & coarse & ~core
    background = (persistence >= 0.60) & ~coarse
    mixed = (persistence >= 0.20) & ~(core | intermittent | background)
    classes = np.zeros_like(persistence, dtype=np.uint8)
    classes[core] = 1
    classes[intermittent] = 2
    classes[background] = 3
    classes[mixed] = 4
    names = {
        1: "PERSISTENT_LOCAL_RESPONSE_CORE",
        2: "INTERMITTENT_LOCAL_RESPONSE_REGION",
        3: "BACKGROUND_STRUCTURE",
        4: "MIXED_OR_UNRESOLVED_REGION",
    }
    rows = []
    for value, name in names.items():
        rows.append(
            {
                "support_region_class": name,
                "pixel_count": int((classes == value).sum()),
                "pixel_fraction_of_expanded_patch": float((classes == value).mean()),
                "classification_basis": "STABILIZED_RESPONSE_PERSISTENCE_AND_FROZEN_COARSE_CORRIDOR_GEOMETRY",
                "gt_box_pixel_label_used": "false",
                "latent_full_body_support_recovered": "false",
            }
        )
    palette = np.asarray(
        [[0, 0, 0], [255, 60, 60], [255, 210, 50], [50, 160, 255], [180, 90, 220]],
        dtype=np.uint8,
    )
    color = palette[classes]
    Image.fromarray(color).resize((width * 3, height * 3), Image.Resampling.NEAREST).save(
        output_root / "15_visible_response_support_organization_map.png"
    )
    np.savez_compressed(
        output_root / "visible_response_support_arrays.npz",
        persistence=persistence,
        classes=classes,
    )
    return rows


def annotate_frame(image: np.ndarray, text: str, max_width: int = 1154) -> Image.Image:
    shown = Image.fromarray(display_u8(image)).convert("RGB")
    if shown.width > max_width:
        ratio = max_width / shown.width
        shown = shown.resize((max_width, int(round(shown.height * ratio))), Image.Resampling.BILINEAR)
    draw = ImageDraw.Draw(shown)
    draw.rectangle((0, 0, min(shown.width, 460), 30), fill=(0, 0, 0))
    draw.text((8, 7), text, fill=(255, 255, 0))
    return shown


def save_gif(frames: Sequence[Image.Image], path: Path, duration: int = 240) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path,
        save_all=True,
        append_images=list(frames[1:]),
        duration=duration,
        loop=0,
        optimize=False,
    )


def side_by_side(left: Image.Image, right: Image.Image, label: str) -> Image.Image:
    height = max(left.height, right.height)
    canvas = Image.new("RGB", (left.width + right.width, height + 28), "black")
    canvas.paste(left, (0, 28))
    canvas.paste(right, (left.width, 28))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 7), f"{label}: raw fixed-coordinate", fill=(255, 210, 0))
    draw.text((left.width + 8, 7), "background stabilized", fill=(80, 255, 120))
    return canvas


def anchor_lookup(tracking: Sequence[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    return {(int(row["frame"]), str(row["anchor_id"])): row for row in tracking}


def create_anchor_review_artifacts(
    images: Sequence[np.ndarray],
    stabilized: Sequence[np.ndarray],
    rows: Sequence[FrameRow],
    tracking: Sequence[dict[str, Any]],
    output_root: Path,
) -> None:
    lookup = anchor_lookup(tracking)
    review_dir = output_root / "anchor_reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    for spec in ANCHORS:
        tiles: list[Image.Image] = []
        gif_frames: list[Image.Image] = []
        for row, raw, stable in zip(rows, images, stabilized):
            evidence = lookup[(row.frame, spec.anchor_id)]
            tracked_patch, _, _ = crop_with_padding(
                raw,
                float(evidence["structure_center_x_px"]),
                float(evidence["structure_center_y_px"]),
                spec.size,
                spec.size,
            )
            tile = Image.fromarray(display_u8(tracked_patch)).convert("RGB").resize(
                (spec.size * 2, spec.size * 2), Image.Resampling.NEAREST
            )
            draw = ImageDraw.Draw(tile)
            draw.rectangle((0, 0, tile.width, 26), fill=(0, 0, 0))
            draw.text(
                (5, 6),
                f"f{row.frame} q={float(evidence['structure_match_quality']):.2f}",
                fill=(255, 255, 0),
            )
            tiles.append(tile)
            raw_fixed, _, _ = crop_with_padding(
                raw, spec.center_x, spec.center_y, spec.size + 40, spec.size + 40
            )
            stable_fixed, _, _ = crop_with_padding(
                stable, spec.center_x, spec.center_y, spec.size + 40, spec.size + 40
            )
            left = Image.fromarray(display_u8(raw_fixed)).convert("RGB").resize(
                ((spec.size + 40) * 2, (spec.size + 40) * 2), Image.Resampling.NEAREST
            )
            right = Image.fromarray(display_u8(stable_fixed)).convert("RGB").resize(
                ((spec.size + 40) * 2, (spec.size + 40) * 2), Image.Resampling.NEAREST
            )
            gif_frames.append(side_by_side(left, right, f"{spec.anchor_id} f{row.frame}"))
        columns = 7
        rows_count = math.ceil(len(tiles) / columns)
        sheet = Image.new(
            "RGB", (columns * tiles[0].width, rows_count * tiles[0].height + 34), "black"
        )
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 9), f"{spec.anchor_id} | {spec.role} | {spec.split}", fill=(255, 255, 255))
        for index, tile in enumerate(tiles):
            sheet.paste(tile, ((index % columns) * tile.width, 34 + (index // columns) * tile.height))
        sheet.save(review_dir / f"{spec.anchor_id}_identity_contact_sheet.png")
        save_gif(gif_frames, review_dir / f"{spec.anchor_id}_before_after.gif")


def create_sequence_artifacts(
    images: Sequence[np.ndarray],
    stabilized: Sequence[np.ndarray],
    valids: Sequence[np.ndarray],
    impacts: Sequence[np.ndarray],
    rows: Sequence[FrameRow],
    output_root: Path,
) -> None:
    save_gif(
        [annotate_frame(image, f"frame {row.frame} raw full frame") for image, row in zip(images, rows)],
        output_root / "01_raw_full_frame.gif",
    )
    save_gif(
        [annotate_frame(image, f"frame {row.frame} stabilized full frame") for image, row in zip(stabilized, rows)],
        output_root / "02_stabilized_full_frame.gif",
    )
    ref_x, ref_y = rows[0].raw_x, rows[0].raw_y + 20.0
    raw_roi_frames: list[Image.Image] = []
    stable_roi_frames: list[Image.Image] = []
    paired_frames: list[Image.Image] = []
    for raw, stable, row in zip(images, stabilized, rows):
        raw_patch, _, _ = crop_with_padding(raw, ref_x, ref_y, 520, 300)
        stable_patch, _, _ = crop_with_padding(stable, ref_x, ref_y, 520, 300)
        left = Image.fromarray(display_u8(raw_patch)).convert("RGB").resize((1040, 600))
        right = Image.fromarray(display_u8(stable_patch)).convert("RGB").resize((1040, 600))
        raw_roi_frames.append(annotate_frame(raw_patch, f"frame {row.frame} raw fixed ROI", 1040))
        stable_roi_frames.append(annotate_frame(stable_patch, f"frame {row.frame} stabilized ROI", 1040))
        paired_frames.append(side_by_side(left, right, f"vehicle neighbourhood f{row.frame}"))
    save_gif(raw_roi_frames, output_root / "03_raw_fixed_vehicle_neighbourhood.gif")
    save_gif(stable_roi_frames, output_root / "04_stabilized_vehicle_neighbourhood.gif")
    save_gif(paired_frames, output_root / "05_vehicle_neighbourhood_before_after.gif")
    valid_frames = [
        annotate_frame(valid, f"frame {row.frame} stabilization valid mask")
        for valid, row in zip(valids, rows)
    ]
    save_gif(valid_frames, output_root / "09_stabilization_valid_mask.gif")
    valid_fraction_map = np.mean(np.stack(valids).astype(np.float32) / 255.0, axis=0)
    Image.fromarray(np.clip(valid_fraction_map * 255.0, 0, 255).astype(np.uint8)).save(
        output_root / "10_stabilization_valid_mask_temporal_fraction.png"
    )
    impact_frames = [
        annotate_frame(np.clip(impact.astype(np.float32) * 12.0, 0, 255).astype(np.uint8), f"frame {row.frame} interpolation impact x12")
        for impact, row in zip(impacts, rows)
    ]
    save_gif(impact_frames, output_root / "11_interpolation_impact.gif")
    mean_impact = np.mean(np.stack(impacts).astype(np.float32), axis=0)
    Image.fromarray(np.clip(mean_impact * 12.0, 0, 255).astype(np.uint8)).save(
        output_root / "12_interpolation_impact_temporal_mean_x12.png"
    )
    review_frames = {330, 335, 338, 339, 340, 344, 348, 350}
    review_rows: list[Image.Image] = []
    for raw, stable, row in zip(images, stabilized, rows):
        if row.frame not in review_frames:
            continue
        raw_patch, _, _ = crop_with_padding(raw, ref_x, ref_y, 520, 300)
        stable_patch, _, _ = crop_with_padding(stable, ref_x, ref_y, 520, 300)
        z, _, _ = robust_z(stable_patch)
        mask = z >= POSITIVE_Z
        raw_rgb = Image.fromarray(display_u8(raw_patch)).convert("RGB")
        stable_rgb = Image.fromarray(display_u8(stable_patch)).convert("RGB")
        overlay = np.repeat(display_u8(stable_patch)[..., None], 3, axis=2)
        overlay[mask, 0] = 255
        overlay[mask, 1] = (overlay[mask, 1] * 0.25).astype(np.uint8)
        overlay[mask, 2] = (overlay[mask, 2] * 0.25).astype(np.uint8)
        overlay_rgb = Image.fromarray(overlay)
        strip = Image.new("RGB", (1560, 326), "black")
        strip.paste(raw_rgb, (0, 26))
        strip.paste(stable_rgb, (520, 26))
        strip.paste(overlay_rgb, (1040, 26))
        draw = ImageDraw.Draw(strip)
        draw.text((8, 6), f"frame {row.frame} raw fixed ROI", fill=(255, 220, 0))
        draw.text((528, 6), "background stabilized", fill=(80, 255, 120))
        draw.text((1048, 6), f"stabilized robust-z >= {POSITIVE_Z}", fill=(255, 100, 100))
        review_rows.append(strip)
    review_sheet = Image.new("RGB", (1560, 326 * len(review_rows)), "black")
    for index, strip in enumerate(review_rows):
        review_sheet.paste(strip, (0, index * 326))
    review_sheet.save(output_root / "14_stabilized_local_response_review_sheet.png")


def plot_anchor_residuals(holdout: Sequence[dict[str, Any]], path: Path) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for method, axis in zip(("LOCAL_STRUCTURE_MATCH", "PHASE_CORRELATION"), axes):
        selected = [row for row in holdout if row["observation_method"] == method]
        for anchor_id in sorted({str(row["anchor_id"]) for row in selected}):
            part = [row for row in selected if row["anchor_id"] == anchor_id]
            axis.plot(
                [int(row["frame"]) for row in part],
                [float(row["post_stabilization_residual_px"]) for row in part],
                marker="o",
                label=anchor_id,
            )
        axis.set_ylabel("post-stabilization residual (px)")
        axis.set_title(method)
        axis.grid(True, alpha=0.3)
        axis.legend(fontsize=8)
    axes[-1].set_xlabel("frame")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def plot_gt_debt(records: Sequence[dict[str, Any]], path: Path) -> None:
    frames = [int(row["frame"]) for row in records]
    figure, axes = plt.subplots(3, 2, figsize=(14, 12), sharex=True)
    axes[0, 0].plot(frames, [float(row["raw_cumulative_x_px"]) for row in records], label="Raw GT")
    axes[0, 0].plot(frames, [float(row["smoothed_cumulative_x_px"]) for row in records], label="Smoothed GT")
    axes[0, 0].plot(frames, [float(row["common_transport_cumulative_x_px"]) for row in records], label="Common transport")
    axes[0, 0].set_title("Cumulative x")
    axes[0, 0].legend()
    axes[0, 1].plot(frames, [float(row["raw_cumulative_y_px"]) for row in records], label="Raw GT")
    axes[0, 1].plot(frames, [float(row["smoothed_cumulative_y_px"]) for row in records], label="Smoothed GT")
    axes[0, 1].plot(frames, [float(row["common_transport_cumulative_y_px"]) for row in records], label="Common transport")
    axes[0, 1].set_title("Cumulative y")
    pair_frames = frames[1:]
    for key, label in (
        ("raw_speed_px_per_frame", "Raw GT"),
        ("smoothed_speed_px_per_frame", "Smoothed GT"),
        ("common_transport_speed_px_per_frame", "Common transport"),
    ):
        axes[1, 0].plot(pair_frames, [float(row[key]) for row in records[1:]], label=label)
    axes[1, 0].set_title("Adjacent speed")
    axes[1, 0].legend()
    axes[1, 1].plot(frames[2:], [float(row["raw_acceleration_px_per_frame2"]) for row in records[2:]], label="Raw GT")
    axes[1, 1].plot(frames[2:], [float(row["smoothed_acceleration_px_per_frame2"]) for row in records[2:]], label="Smoothed GT")
    axes[1, 1].set_title("Adjacent acceleration magnitude")
    axes[1, 1].legend()
    axes[2, 0].plot(frames, [float(row["raw_stabilized_x_px"]) for row in records], label="Raw stable x")
    axes[2, 0].plot(frames, [float(row["smoothed_stabilized_x_px"]) for row in records], label="Smooth stable x")
    axes[2, 0].set_title("GT x after common transport removal")
    axes[2, 0].legend()
    axes[2, 1].plot(frames, [float(row["raw_stabilized_y_px"]) for row in records], label="Raw stable y")
    axes[2, 1].plot(frames, [float(row["smoothed_stabilized_y_px"]) for row in records], label="Smooth stable y")
    switch_frames = [int(row["frame"]) for row in records if row["source_family_switch_from_previous"] == "true"]
    for frame in switch_frames:
        axes[2, 1].axvline(frame, color="gray", alpha=0.15)
    axes[2, 1].set_title("GT y after transport removal; gray=source switch")
    axes[2, 1].legend()
    for axis in axes.ravel():
        axis.grid(True, alpha=0.3)
        axis.set_xlabel("frame")
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def write_output_manifest(output_root: Path) -> None:
    records: list[dict[str, Any]] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file() or path.name == "output_manifest.csv":
            continue
        records.append(
            {
                "relative_path": path.relative_to(output_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    write_csv(output_root / "output_manifest.csv", records)


def main() -> None:
    global OUTPUT_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    OUTPUT_ROOT = args.output_root.resolve()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"branch mismatch: {branch}")
    if head != EXPECTED_START_HEAD:
        raise RuntimeError(f"frozen start HEAD mismatch: {head}")
    if sha256_file(LOCAL_FIELD_PATH) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("input manifest SHA256 mismatch")

    rows = load_rows()
    images = load_images(rows)
    tracking, rough = build_anchor_tracking(rows, images)
    write_csv(ANCHOR_TRACK_PATH, tracking)

    model_rows, selected_predictors = model_residual_rows(tracking, rows)
    write_csv(MODEL_SELECTION_PATH, model_rows)
    shifts = selected_shifts(selected_predictors, rows)
    holdout = holdout_rows(tracking, selected_predictors)
    write_csv(HOLDOUT_PATH, holdout)

    stabilized, valids, impacts, stabilization_quality = stabilize_images(images, rows, shifts)
    write_csv(STABILIZATION_PATH, stabilization_quality)

    gt_debt = build_gt_debt(rows, shifts)
    write_csv(GT_DEBT_PATH, gt_debt)

    (
        region_rows,
        component_rows,
        direction_rows,
        relation_rows,
        matched_rows,
        z_stacks,
    ) = local_response_analysis(rows, stabilized, shifts)
    write_csv(REGION_PATH, region_rows)
    write_csv(COMPONENT_PATH, component_rows)
    write_csv(DIRECTION_PATH, direction_rows)
    write_csv(RELATION_PATH, relation_rows)
    write_csv(MATCHED_PATH, matched_rows)
    support_rows = support_regions(z_stacks, OUTPUT_ROOT)
    write_csv(SUPPORT_PATH, support_rows)

    create_sequence_artifacts(images, stabilized, valids, impacts, rows, OUTPUT_ROOT)
    create_anchor_review_artifacts(images, stabilized, rows, tracking, OUTPUT_ROOT)
    plot_anchor_residuals(holdout, OUTPUT_ROOT / "08_holdout_background_residual_timeseries.png")
    plot_gt_debt(gt_debt, OUTPUT_ROOT / "13_raw_smoothed_gt_and_common_transport_debt.png")

    summary = {
        "branch": branch,
        "start_head": head,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "frames": len(rows),
        "source_hash_matches": len(rows),
        "background_anchor_count": len(ANCHORS),
        "fit_anchor_count": sum(spec.split == "FIT" for spec in ANCHORS),
        "holdout_anchor_count": sum(spec.split == "HOLDOUT" for spec in ANCHORS),
        "selected_common_scene_transport_model": SELECTED_MODEL,
        "selected_transport_observation": SELECTED_OBSERVATION,
        "rough_phase_response_median": float(np.median([value[2] for value in rough.values()])),
        "common_transport_cumulative_dx_px": shifts[350][0] - shifts[330][0],
        "common_transport_cumulative_dy_px": shifts[350][1] - shifts[330][1],
        "raw_gt_cumulative_dx_px": rows[-1].raw_x - rows[0].raw_x,
        "raw_gt_cumulative_dy_px": rows[-1].raw_y - rows[0].raw_y,
        "smoothed_gt_cumulative_dx_px": rows[-1].smooth_x - rows[0].smooth_x,
        "smoothed_gt_cumulative_dy_px": rows[-1].smooth_y - rows[0].smooth_y,
        "algorithmic_anchor_switch_suspicion_count": sum(
            row["algorithmic_structure_switch_suspected"] == "true" for row in tracking
        ),
        "local_component_count": len(component_rows),
        "direction_fragment_count": len(direction_rows),
        "support_region_pixel_counts": {
            row["support_region_class"]: row["pixel_count"] for row in support_rows
        },
        "vehicle_motion_ownership": "NOT_TESTABLE_BY_DIFFERENTIAL_BULK_TRANSLATION",
        "motion_coherent_support_corridor": "NOT_EVALUATED_BY_VALID_SUPPORT_CRITERION",
        "weighted_score": "NOT_COMPUTED",
        "ranking": "NOT_COMPUTED",
        "candidate_bank": "NOT_CREATED",
        "final_box": "NOT_COMPUTED",
        "latent_full_body_support": "NOT_RECOVERED",
        "s1d": "NOT_ENTERED",
    }
    (OUTPUT_ROOT / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_output_manifest(OUTPUT_ROOT)
    LOG_PATH.write_text(
        "\n".join(
            [
                "S1-LR2 common-scene transport and local-response runner",
                f"branch={branch}",
                f"start_head={head}",
                f"interpreter={sys.executable}",
                f"manifest_sha256={EXPECTED_MANIFEST_SHA256}",
                f"frames={len(rows)}",
                f"anchors={len(ANCHORS)} fit=6 holdout=2",
                f"selected_model={SELECTED_MODEL}",
                f"selected_observation={SELECTED_OBSERVATION}",
                f"output_root={OUTPUT_ROOT}",
                "vehicle_gt_used_for_transport_fit=false",
                "weighted_score=NOT_COMPUTED",
                "ranking=NOT_COMPUTED",
                "candidate_bank=NOT_CREATED",
                "final_box=NOT_COMPUTED",
                "latent_full_body_support=NOT_RECOVERED",
                "s1d=NOT_ENTERED",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
