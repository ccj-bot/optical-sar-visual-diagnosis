#!/usr/bin/env python3
"""Build the OTY2 S0 SAR coordinate, mask, GT-thread, and mapping audit.

The script is intentionally read-only with respect to source optical/SAR assets.
It consumes the frozen P0/P1-E manifests plus the canonical 442-row reviewed SAR
GT table. It does not consume P1-F outputs and does not generate candidates,
selectors, rankings, or automatic annotations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import cv2
import numpy as np


BASE_COMMIT = "1ea130fdc91683dd1f6d45bf44fe6bf00b1cecb5"
EXECUTION_DATE = "2026-07-15"
SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")
WIDTH = 2308
HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
OLD_MAPPING_K = 0.0875154
OLD_MAPPING_B = -40.413555
OPTICAL_FPS = 24.0
SAR_FPS = 50.0

REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = Path(r"D:\profile\research")
WORKSPACE_ROOT = RESEARCH_ROOT / "workspace"
DATA_ROOT = RESEARCH_ROOT / "data"
TEMP_OUTPUT = WORKSPACE_ROOT / "output" / "oty2_s0_sar_gt_structure_foundation_20260715"
VISUAL_OUTPUT = TEMP_OUTPUT / "visual_review"
GT_ROOT = WORKSPACE_ROOT / "output" / "hermes_annotation_consolidation_2026-05-20" / "00_tables"
REVIEW_QUEUE = GT_ROOT / "review_queue.csv"
FINAL_GT = GT_ROOT / "final_gt_working.csv"

MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = REPO_ROOT / "reports" / "oty2"

FORMAL_OUTPUTS = (
    DOCS_DIR / "OTY2_S0_SAR_GT_STRUCTURE_FOUNDATION_PROTOCOL.md",
    DOCS_DIR / "OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md",
    DOCS_DIR / "OTY2_S0_OPTICAL_TO_SAR_AZIMUTH_MAPPING_CONTRACT.md",
    MANIFEST_DIR / "oty2_s0_sar_coordinate_contract.csv",
    MANIFEST_DIR / "oty2_s0_sar_mask_contract.csv",
    MANIFEST_DIR / "oty2_s0_sar_gray_pseudocolor_lineage.csv",
    MANIFEST_DIR / "oty2_s0_canonical_vehicle_sar_gt_threads.csv",
    MANIFEST_DIR / "oty2_s0_sar_gt_quality_audit.csv",
    MANIFEST_DIR / "oty2_s0_sar_golden_vehicle_threads.csv",
    MANIFEST_DIR / "oty2_s0_optical_to_sar_azimuth_mapping_audit.csv",
    REPORTS_DIR / "oty2_s0_sar_gt_structure_foundation_audit_20260715.md",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def fmt(value: float | int | None, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    return f"{float(value):.{digits}f}"


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() == "true"


def parse_float(value: str | float | int | None, default: float = math.nan) -> float:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def parse_frame_from_path(value: str) -> int:
    return int(Path(value).stem)


def fan_mask() -> np.ndarray:
    yy, xx = np.indices((HEIGHT, WIDTH), dtype=np.float64)
    radial = np.hypot(xx - FAN_CENTER_X, yy - FAN_CENTER_Y)
    theta = np.degrees(np.arctan2(xx - FAN_CENTER_X, FAN_CENTER_Y - yy))
    return (radial <= FAN_RADIUS_PX) & (theta >= -90.0) & (theta <= 90.0)


def mask_hash(mask: np.ndarray) -> str:
    return sha256_bytes(np.packbits(mask.astype(np.uint8), bitorder="little").tobytes())


def display_xy_to_polar(x: float, y: float) -> tuple[float, float]:
    radius = math.hypot(x - FAN_CENTER_X, y - FAN_CENTER_Y)
    theta = math.degrees(math.atan2(x - FAN_CENTER_X, FAN_CENTER_Y - y))
    return radius, theta


def bbox_iou(a: Sequence[float], b: Sequence[float]) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(a[2]) - float(a[0])) * max(0.0, float(a[3]) - float(a[1]))
    area_b = max(0.0, float(b[2]) - float(b[0])) * max(0.0, float(b[3]) - float(b[1]))
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def parse_list_bbox(value: str) -> tuple[float, float, float, float] | None:
    try:
        parts = [float(item.strip()) for item in value.strip().strip("[]").split(",")]
        return tuple(parts) if len(parts) == 4 else None
    except (AttributeError, TypeError, ValueError):
        return None


def rotated_points(cx: float, cy: float, width: float, height: float, heading: float) -> np.ndarray:
    return cv2.boxPoints(((float(cx), float(cy)), (float(width), float(height)), float(heading)))


def rotated_mask_fraction(box: Sequence[float], valid_mask: np.ndarray) -> float:
    cx, cy, width, height, heading = [float(item) for item in box]
    points = rotated_points(cx, cy, width, height, heading)
    x1 = max(0, int(math.floor(points[:, 0].min())) - 2)
    y1 = max(0, int(math.floor(points[:, 1].min())) - 2)
    x2 = min(WIDTH, int(math.ceil(points[:, 0].max())) + 3)
    y2 = min(HEIGHT, int(math.ceil(points[:, 1].max())) + 3)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    local = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
    local_points = np.rint(points - np.array([x1, y1], dtype=np.float32)).astype(np.int32)
    cv2.fillPoly(local, [local_points], 1)
    total = int(local.sum())
    if total <= 0:
        return 0.0
    inside = int((local.astype(bool) & valid_mask[y1:y2, x1:x2]).sum())
    return inside / total


def rotated_overlap_ratio(a: Sequence[float], b: Sequence[float]) -> float:
    rect_a = ((float(a[0]), float(a[1])), (float(a[2]), float(a[3])), float(a[4]))
    rect_b = ((float(b[0]), float(b[1])), (float(b[2]), float(b[3])), float(b[4]))
    status, points = cv2.rotatedRectangleIntersection(rect_a, rect_b)
    if status == cv2.INTERSECT_NONE or points is None:
        return 0.0
    inter = abs(float(cv2.contourArea(points)))
    area_a = max(1e-9, float(a[2]) * float(a[3]))
    area_b = max(1e-9, float(b[2]) * float(b[3]))
    return inter / max(1e-9, min(area_a, area_b))


def quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return math.nan
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def median_abs_deviation(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    med = statistics.median(values)
    return statistics.median(abs(value - med) for value in values)


def asset_manifest_index() -> dict[tuple[str, str], dict[str, str]]:
    rows = read_csv(MANIFEST_DIR / "oty2_p0_data_asset_manifest.csv")
    result: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["scene"], row["asset_role"])
        if row.get("frame_index", "") == "" or key not in result:
            result[key] = row
    return result


def frame_hash_index() -> dict[tuple[str, str, int], str]:
    rows = read_csv(MANIFEST_DIR / "oty2_p0_data_asset_manifest.csv")
    result: dict[tuple[str, str, int], str] = {}
    for row in rows:
        if row.get("frame_index", "").strip() == "":
            continue
        if row["asset_role"] not in {"sar_gray_frame", "sar_pseudocolor_frame"}:
            continue
        result[(row["scene"], row["asset_role"], int(row["frame_index"]))] = row["content_hash"]
    return result


def gray_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes_gray" / f"{frame:06d}.png"


def pseudo_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes" / f"{frame:06d}.png"


def gradient_alignment(gray: np.ndarray, pseudo: np.ndarray) -> float:
    target_size = (WIDTH // 6, HEIGHT // 6)
    gray_small = cv2.resize(gray, target_size, interpolation=cv2.INTER_AREA)
    pseudo_small = cv2.resize(pseudo, target_size, interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(pseudo_small, cv2.COLOR_BGR2LAB)

    def grad(array: np.ndarray) -> np.ndarray:
        arr = array.astype(np.float32)
        gx = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
        return cv2.magnitude(gx, gy)

    base = grad(gray_small)
    mask = gray_small > 0
    if int(mask.sum()) < 100:
        return math.nan
    correlations: list[float] = []
    for channel in range(3):
        other = grad(lab[:, :, channel])
        x = base[mask].ravel()
        y = other[mask].ravel()
        if float(x.std()) <= 1e-9 or float(y.std()) <= 1e-9:
            continue
        correlations.append(float(np.corrcoef(x, y)[0, 1]))
    return max(correlations) if correlations else math.nan


def draw_label(image: np.ndarray, text: str, origin: tuple[int, int] = (4, 16)) -> None:
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)


def audit_streams(valid_fan: np.ndarray) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Read every gray/pseudocolor frame and build lineage plus mask summaries."""

    VISUAL_OUTPUT.mkdir(parents=True, exist_ok=True)
    frame_hashes = frame_hash_index()
    asset_index = asset_manifest_index()
    lineage_rows: list[dict[str, Any]] = []
    mask_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    common_fan_hash = mask_hash(valid_fan)

    for scene in SCENES:
        print(f"[stream] {scene}: reading 766 gray+pseudocolor frame pairs", flush=True)
        zero_all = np.ones((HEIGHT, WIDTH), dtype=bool)
        nonzero_all = np.ones((HEIGHT, WIDTH), dtype=bool)
        nonzero_counts = np.zeros((HEIGHT, WIDTH), dtype=np.uint16)
        per_frame_nonzero: list[int] = []
        gradient_values: list[float] = []
        channel_equal_count = 0

        tile_w, tile_h, columns = 150, 88, 16
        rows_count = math.ceil(766 / columns)
        sheet = np.full((rows_count * tile_h, columns * tile_w, 3), 28, dtype=np.uint8)

        pseudo_asset = asset_index[(scene, "sar_pseudocolor_source_video")]
        pseudo_fps = parse_float(pseudo_asset.get("fps"))
        for frame in range(766):
            gray_file = gray_path(scene, frame)
            pseudo_file = pseudo_path(scene, frame)
            gray_bgr = cv2.imread(str(gray_file), cv2.IMREAD_COLOR)
            pseudo_bgr = cv2.imread(str(pseudo_file), cv2.IMREAD_COLOR)
            if gray_bgr is None or pseudo_bgr is None:
                raise FileNotFoundError(f"Unreadable SAR frame pair: {gray_file} / {pseudo_file}")
            if gray_bgr.shape[:2] != (HEIGHT, WIDTH) or pseudo_bgr.shape[:2] != (HEIGHT, WIDTH):
                raise ValueError(f"Unexpected SAR dimensions in {scene} frame {frame}")
            gray_scalar = gray_bgr[:, :, 0]
            channel_equal = bool(np.array_equal(gray_bgr[:, :, 0], gray_bgr[:, :, 1]) and np.array_equal(gray_bgr[:, :, 0], gray_bgr[:, :, 2]))
            channel_equal_count += int(channel_equal)
            nonzero = gray_scalar > 0
            zero_all &= ~nonzero
            nonzero_all &= nonzero
            nonzero_counts += nonzero.astype(np.uint16)
            per_frame_nonzero.append(int(nonzero.sum()))
            alignment = gradient_alignment(gray_scalar, pseudo_bgr)
            gradient_values.append(alignment)

            lineage_rows.append(
                {
                    "scene": scene,
                    "frame_index": frame,
                    "gray_filename": gray_file.name,
                    "pseudocolor_filename": pseudo_file.name,
                    "gray_content_hash": frame_hashes[(scene, "sar_gray_frame", frame)],
                    "pseudocolor_content_hash": frame_hashes[(scene, "sar_pseudocolor_frame", frame)],
                    "index_aligned": "true",
                    "dimensions_aligned": "true",
                    "gray_channel_semantics": "8bit_RGB_container_with_identical_channels" if channel_equal else "8bit_RGB_gray_display_nonidentical_channels",
                    "pseudocolor_semantics": "8bit_RGB_display_transform_same_spatial_frame",
                    "spatial_gradient_alignment": fmt(alignment),
                    "gray_authoritative_fps": fmt(SAR_FPS, 6),
                    "pseudocolor_container_fps": fmt(pseudo_fps, 9),
                    "authoritative_time_sec": fmt(frame / SAR_FPS, 9),
                    "pseudocolor_inherited_time_sec": fmt(frame / SAR_FPS, 9),
                    "lineage_status": "INDEX_ALIGNED_DISPLAY_DERIVATION_SUPPORTED" if alignment >= 0.55 else "INDEX_ALIGNED_TRANSFORM_REVIEWED_LOW_ALIGNMENT",
                    "retains_phase": "false",
                    "adds_independent_physical_observation": "false",
                    "notes": "gray 50 fps is authoritative; pseudocolor inherits same-index gray time; no source video was re-encoded",
                }
            )

            gray_thumb = cv2.resize(gray_bgr, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
            pseudo_thumb = cv2.resize(pseudo_bgr, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
            split = gray_thumb.copy()
            split[:, tile_w // 2 :] = pseudo_thumb[:, tile_w // 2 :]
            draw_label(split, f"{frame:03d}")
            row_i, col_i = divmod(frame, columns)
            sheet[row_i * tile_h : (row_i + 1) * tile_h, col_i * tile_w : (col_i + 1) * tile_w] = split

            if frame % 100 == 0:
                print(f"[stream] {scene}: frame {frame}/765", flush=True)

        fixed_black_inside_fan = zero_all & valid_fan
        stable_nonzero = (nonzero_counts >= math.ceil(0.95 * 766)) & valid_fan
        fixed_black_hash = mask_hash(fixed_black_inside_fan)
        stable_hash = mask_hash(stable_nonzero)
        cv2.imwrite(str(VISUAL_OUTPUT / f"{scene}_full_stream_gray_left_pseudocolor_right.png"), sheet)

        scene_summary = {
            "frame_count": 766,
            "gray_channels_identical_count": channel_equal_count,
            "fan_geometry_pixel_count": int(valid_fan.sum()),
            "fan_geometry_fraction": float(valid_fan.mean()),
            "fixed_black_inside_fan_pixel_count": int(fixed_black_inside_fan.sum()),
            "fixed_black_inside_fan_fraction_of_fan": float(fixed_black_inside_fan.sum() / max(1, valid_fan.sum())),
            "fixed_black_inside_fan_hash": fixed_black_hash,
            "stable_nonzero_inside_fan_pixel_count": int(stable_nonzero.sum()),
            "stable_nonzero_inside_fan_hash": stable_hash,
            "per_frame_nonzero_min": min(per_frame_nonzero),
            "per_frame_nonzero_max": max(per_frame_nonzero),
            "gradient_alignment_min": min(gradient_values),
            "gradient_alignment_median": statistics.median(gradient_values),
            "gradient_alignment_p90": quantile(gradient_values, 0.90),
        }
        summary[scene] = scene_summary

        common = {
            "scene": scene,
            "image_width": WIDTH,
            "image_height": HEIGHT,
        }
        mask_rows.extend(
            [
                {
                    **common,
                    "mask_name": "imaging_valid_mask",
                    "definition": "fixed imaging-process valid region reconstructed from shared fan geometry",
                    "availability": "reproducible_from_frozen_geometry_contract",
                    "static_or_dynamic": "static_shared_across_all_frames",
                    "generation_rule": "r<=1332.7 and -90<=atan2(x-1154,1330.6-y)<=90",
                    "pixel_count_or_range": int(valid_fan.sum()),
                    "fraction_or_range": fmt(valid_fan.mean(), 9),
                    "content_hash_or_formula_hash": common_fan_hash,
                    "physical_semantics": "fixed valid imaging support contract; not a vehicle mask or display threshold",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "FROZEN_DETERMINISTIC_CONTRACT",
                    "notes": "shared by all three scenes and all 766 frame indices per scene",
                },
                {
                    **common,
                    "mask_name": "display_nonzero_mask",
                    "definition": "per-frame gray PNG pixels with intensity > 0",
                    "availability": "reproducible_from_gray_png",
                    "static_or_dynamic": "dynamic_per_frame",
                    "generation_rule": "gray_scalar > 0",
                    "pixel_count_or_range": f"{min(per_frame_nonzero)}..{max(per_frame_nonzero)}",
                    "fraction_or_range": f"{min(per_frame_nonzero)/(WIDTH*HEIGHT):.9f}..{max(per_frame_nonzero)/(WIDTH*HEIGHT):.9f}",
                    "content_hash_or_formula_hash": "per_frame_not_single_hash",
                    "physical_semantics": "rendered nonzero support only",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "CONFIRMED_DISPLAY_ONLY",
                    "notes": "threshold mask; zeros do not distinguish un-imaged, invalid, clipped, or true zero return",
                },
                {
                    **common,
                    "mask_name": "fixed_black_region_inside_mask",
                    "definition": "pixels equal to zero in every one of 766 gray PNG frames, restricted to imaging_valid_mask",
                    "availability": "reproducible_from_full_gray_stream",
                    "static_or_dynamic": "static_empirical",
                    "generation_rule": "all_frames(gray_scalar == 0) AND imaging_valid_mask",
                    "pixel_count_or_range": int(fixed_black_inside_fan.sum()),
                    "fraction_or_range": fmt(fixed_black_inside_fan.sum() / max(1, valid_fan.sum()), 9),
                    "content_hash_or_formula_hash": fixed_black_hash,
                    "physical_semantics": "fixed rendered black or no-response region inside valid imaging support",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "CONFIRMED_EMPIRICAL_DISPLAY_MASK",
                    "notes": "distinct from invalid support and from vehicle_response_mask",
                },
                {
                    **common,
                    "mask_name": "fan_geometry_mask",
                    "definition": "geometric reconstruction identical to frozen imaging_valid_mask",
                    "availability": "reproducible_alias_for_geometry_audit",
                    "static_or_dynamic": "static_shared_formula",
                    "generation_rule": "r<=1332.7 and -90<=atan2(x-1154,1330.6-y)<=90",
                    "pixel_count_or_range": int(valid_fan.sum()),
                    "fraction_or_range": fmt(valid_fan.mean(), 9),
                    "content_hash_or_formula_hash": common_fan_hash,
                    "physical_semantics": "geometry representation of imaging_valid_mask",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "CONFIRMED_GEOMETRY_ALIAS",
                    "notes": "retained for backward schema continuity; mapping must use imaging_valid_mask",
                },
                {
                    **common,
                    "mask_name": "gt_box_region",
                    "definition": "reviewed rotated SAR GT rectangle",
                    "availability": "available_per_gt_row",
                    "static_or_dynamic": "per_annotation",
                    "generation_rule": "cv2 rotated rectangle from cx,cy,w,h,heading",
                    "pixel_count_or_range": "per_gt_row",
                    "fraction_or_range": "per_gt_row",
                    "content_hash_or_formula_hash": "see_gt_quality_manifest",
                    "physical_semantics": "research/evaluation region anchor, not scattering support truth",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "CONFIRMED_ANNOTATION_REGION",
                    "notes": "GT is not a vehicle-response mask",
                },
                {
                    **common,
                    "mask_name": "gt_valid_intersection_mask",
                    "definition": "GT rectangle intersected with authoritative imaging_valid_mask",
                    "availability": "reproducible_per_gt_row",
                    "static_or_dynamic": "per_annotation",
                    "generation_rule": "gt_box_region AND imaging_valid_mask",
                    "pixel_count_or_range": "",
                    "fraction_or_range": "",
                    "content_hash_or_formula_hash": "",
                    "physical_semantics": "GT evaluation region restricted to fixed valid imaging support",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "CONFIRMED_DERIVED_REGION",
                    "notes": "does not become a vehicle-response mask",
                },
                {
                    **common,
                    "mask_name": "intensity_threshold_mask",
                    "definition": "temporary intensity-selected pixels",
                    "availability": "semantic_contract_only",
                    "static_or_dynamic": "dynamic",
                    "generation_rule": "threshold chosen by a declared diagnostic only",
                    "pixel_count_or_range": "",
                    "fraction_or_range": "",
                    "content_hash_or_formula_hash": "",
                    "physical_semantics": "display/diagnostic threshold support",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "DEFINED_NOT_INSTANTIATED",
                    "notes": "no threshold is frozen in S0",
                },
                {
                    **common,
                    "mask_name": "vehicle_response_mask",
                    "definition": "future inferred support of vehicle SAR response",
                    "availability": "not_available_in_S0",
                    "static_or_dynamic": "future_model_output",
                    "generation_rule": "undefined_in_S0",
                    "pixel_count_or_range": "",
                    "fraction_or_range": "",
                    "content_hash_or_formula_hash": "",
                    "physical_semantics": "future vehicle-response support",
                    "may_be_used_as_vehicle_mask": "not_in_S0",
                    "confidence_status": "SEMANTIC_ONLY",
                    "notes": "must not be replaced by GT area or bright pixels",
                },
                {
                    **common,
                    "mask_name": "registration_valid_mask",
                    "definition": "future valid pixels after body-frame normalization",
                    "availability": "not_available_in_S0",
                    "static_or_dynamic": "future_per_frame",
                    "generation_rule": "undefined_in_S0",
                    "pixel_count_or_range": "",
                    "fraction_or_range": "",
                    "content_hash_or_formula_hash": "",
                    "physical_semantics": "future registration support",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "SEMANTIC_ONLY",
                    "notes": "defined only to prevent later semantic mixing",
                },
                {
                    **common,
                    "mask_name": "occlusion_or_boundary_missing_mask",
                    "definition": "future unavailable body region due to occlusion or image/fan boundary",
                    "availability": "not_available_in_S0",
                    "static_or_dynamic": "future_per_frame",
                    "generation_rule": "undefined_in_S0",
                    "pixel_count_or_range": "",
                    "fraction_or_range": "",
                    "content_hash_or_formula_hash": "",
                    "physical_semantics": "future missing-data semantics",
                    "may_be_used_as_vehicle_mask": "false",
                    "confidence_status": "SEMANTIC_ONLY",
                    "notes": "must remain distinct from zero intensity",
                },
            ]
        )

    return lineage_rows, mask_rows, summary


def load_identity_context() -> dict[str, Any]:
    registry = read_csv(MANIFEST_DIR / "oty2_p1e_canonical_optical_vehicle_registry.csv")
    states = read_csv(MANIFEST_DIR / "oty2_p1e_canonical_vehicle_frame_states.csv")
    roles = read_csv(MANIFEST_DIR / "oty2_p1e_identity_benchmark_roles.csv")
    detections = read_csv(MANIFEST_DIR / "oty2_p1e_detection_to_canonical_identity_map.csv")

    role_by_vehicle = {(row["scene"], row["canonical_vehicle_id"]): row["benchmark_role"] for row in roles}
    state_by_key: dict[tuple[str, str, int], dict[str, str]] = {}
    visible_by_frame: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in states:
        key = (row["scene"], row["canonical_vehicle_id"], int(row["frame_index"]))
        state_by_key[key] = row
        if parse_bool(row.get("is_vehicle_visible")):
            visible_by_frame[(row["scene"], int(row["frame_index"]))].append(row)

    detection_by_frame: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in detections:
        box = parse_list_bbox(row.get("bbox", ""))
        if box is None:
            continue
        detection_by_frame[(row["scene"], int(row["frame_index"]))].append({**row, "parsed_bbox": box})

    return {
        "registry": registry,
        "roles": roles,
        "role_by_vehicle": role_by_vehicle,
        "state_by_key": state_by_key,
        "visible_by_frame": visible_by_frame,
        "detection_by_frame": detection_by_frame,
    }


def link_gt_to_canonical(
    gt_rows: Sequence[dict[str, str]],
    queue_rows: Sequence[dict[str, str]],
    identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    queue_by_target = {row["target_identity"]: row for row in queue_rows}
    role_by_vehicle = identity["role_by_vehicle"]
    visible_by_frame = identity["visible_by_frame"]
    detection_by_frame = identity["detection_by_frame"]
    state_by_key = identity["state_by_key"]

    sar_frame_counts = Counter((row["scene"], int(row["sar_frame_num"])) for row in gt_rows)
    linked: list[dict[str, Any]] = []

    for gt in gt_rows:
        queue = queue_by_target.get(gt["target_identity"])
        if queue is None:
            raise KeyError(f"GT row missing from review queue: {gt['target_identity']}")
        scene = gt["scene"]
        optical_frame = parse_frame_from_path(gt["optical_path"])
        sar_frame = int(gt["sar_frame_num"])
        visible_states = list(visible_by_frame.get((scene, optical_frame), []))
        source_box: tuple[float, float, float, float] | None = None
        if queue.get("opt_x1", "").strip():
            source_box = tuple(parse_float(queue[name]) for name in ("opt_x1", "opt_y1", "opt_x2", "opt_y2"))

        candidates: list[tuple[float, dict[str, Any]]] = []
        overall: list[tuple[float, dict[str, Any]]] = []
        if source_box is not None:
            for detection in detection_by_frame.get((scene, optical_frame), []):
                overlap = bbox_iou(source_box, detection["parsed_bbox"])
                overall.append((overlap, detection))
                if detection.get("assigned_canonical_vehicle_id", ""):
                    candidates.append((overlap, detection))
        candidates.sort(key=lambda item: item[0], reverse=True)
        overall.sort(key=lambda item: item[0], reverse=True)

        canonical_id = ""
        link_status = "unresolved_identity"
        link_confidence = "none"
        evidence = ""
        best_iou = candidates[0][0] if candidates else 0.0
        best_detection = candidates[0][1] if candidates else None
        best_overall = overall[0] if overall else None

        if source_box is None:
            if len(visible_states) == 1:
                canonical_id = visible_states[0]["canonical_vehicle_id"]
                link_status = "linked_unique_visible_vehicle_without_source_bbox"
                link_confidence = "low"
                evidence = "SAR-only/supplement row; exactly one P1-E canonical vehicle visible at synchronized optical frame"
            elif len(visible_states) > 1:
                evidence = f"source optical bbox absent; {len(visible_states)} canonical vehicles visible"
            else:
                evidence = "source optical bbox absent; no canonical visible vehicle at synchronized frame"
        else:
            overall_is_nonvehicle = bool(best_overall and not best_overall[1].get("assigned_canonical_vehicle_id", ""))
            overall_iou = best_overall[0] if best_overall else 0.0
            close_canonical_to_overall = best_iou >= max(0.0, overall_iou - 0.035)
            if best_detection is not None and best_iou >= 0.70:
                canonical_id = best_detection["assigned_canonical_vehicle_id"]
                link_status = "linked_detection_overlap_high"
                link_confidence = "high" if not overall_is_nonvehicle or close_canonical_to_overall else "moderate"
            elif best_detection is not None and best_iou >= 0.40:
                canonical_id = best_detection["assigned_canonical_vehicle_id"]
                link_status = "linked_detection_overlap_moderate"
                link_confidence = "moderate"
            elif best_detection is not None and best_iou >= 0.10 and not (overall_is_nonvehicle and not close_canonical_to_overall):
                canonical_id = best_detection["assigned_canonical_vehicle_id"]
                link_status = "linked_detection_overlap_low"
                link_confidence = "low"
            elif best_detection is not None and best_iou > 0 and len(visible_states) == 1 and not (overall_is_nonvehicle and overall_iou > 0.70):
                canonical_id = best_detection["assigned_canonical_vehicle_id"]
                link_status = "linked_unique_visible_vehicle_low_geometry_overlap"
                link_confidence = "low"
            elif overall_is_nonvehicle and overall_iou >= 0.70 and not close_canonical_to_overall:
                link_status = "nonvehicle_optical_source_conflict"
                link_confidence = "none"
            elif len(visible_states) == 1:
                canonical_id = visible_states[0]["canonical_vehicle_id"]
                link_status = "linked_unique_visible_vehicle_without_detection_overlap"
                link_confidence = "low"

            if canonical_id and best_detection is not None:
                evidence = (
                    f"P1-E detection overlap={best_iou:.3f}; assignment={best_detection['assignment_status']}; "
                    f"observation_role={best_detection['observation_role']}; source={best_detection['detector_source']}"
                )
                if overall_is_nonvehicle and close_canonical_to_overall:
                    evidence += "; near-tied nonvehicle/mixed observation retained as identity-geometry caution"
            elif not evidence:
                evidence = f"no defensible canonical assignment; best canonical overlap={best_iou:.3f}"

        state = state_by_key.get((scene, canonical_id, optical_frame)) if canonical_id else None
        reference_bbox = ""
        if state and parse_bool(state.get("reference_bbox_available")):
            reference_bbox = "[" + ",".join(
                fmt(parse_float(state[name]), 3)
                for name in ("reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2")
            ) + "]"
        optical_visibility = state["visibility_state"] if state else "unresolved"
        full_visible = parse_bool(state.get("is_full_vehicle_visible")) if state else False
        role = role_by_vehicle.get((scene, canonical_id), "unlinked")
        box = [parse_float(gt[name]) for name in ("final_cx", "final_cy", "final_w", "final_h", "final_heading_deg")]

        linked.append(
            {
                "scene": scene,
                "canonical_vehicle_id": canonical_id,
                "benchmark_role": role,
                "optical_frame_index": optical_frame,
                "optical_time_sec": fmt(optical_frame / OPTICAL_FPS, 9),
                "sar_frame_index": sar_frame,
                "sar_time_sec": fmt(sar_frame / SAR_FPS, 9),
                "sar_gt_available": "true",
                "sar_gt_id": f"{scene}|{sar_frame:06d}|{gt['target_identity']}",
                "sar_gt_bbox": "[" + ",".join(fmt(value, 3) for value in box) + "]",
                "optical_visibility_state": optical_visibility,
                "optical_full_vehicle_visible": bool_text(full_visible),
                "optical_reference_bbox": reference_bbox,
                "mapping_basis": "P0 fixed 24/50 common-start operational assumption; P1-E benchmark identity only",
                "identity_link_evidence": evidence,
                "identity_link_status": link_status,
                "identity_link_confidence": link_confidence,
                "source_optical_bbox": "" if source_box is None else "[" + ",".join(fmt(value, 3) for value in source_box) + "]",
                "source_optical_bbox_best_canonical_iou": fmt(best_iou),
                "multi_vehicle_competition": bool_text(len(visible_states) > 1 or sar_frame_counts[(scene, sar_frame)] > 1),
                "thread_quality_status": "linked" if canonical_id else "unresolved",
                "notes": "GT absence is not interpreted as no SAR response; no sparse interpolation was performed",
                "_gt": gt,
                "_queue": queue,
                "_state": state or {},
                "_box": box,
            }
        )

    return linked


def build_quality_audit(linked_rows: list[dict[str, Any]], valid_fan: np.ndarray) -> list[dict[str, Any]]:
    by_sar_frame: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in linked_rows:
        by_sar_frame[(row["scene"], int(row["sar_frame_index"]))].append(row)

    base: list[dict[str, Any]] = []
    for row in linked_rows:
        cx, cy, width, height, heading = row["_box"]
        fan_fraction = rotated_mask_fraction(row["_box"], valid_fan)
        points = rotated_points(cx, cy, width, height, heading)
        touches_image = bool(points[:, 0].min() <= 0 or points[:, 1].min() <= 0 or points[:, 0].max() >= WIDTH - 1 or points[:, 1].max() >= HEIGHT - 1)
        overlaps: list[float] = []
        center_distances: list[float] = []
        for other in by_sar_frame[(row["scene"], int(row["sar_frame_index"]))]:
            if other is row:
                continue
            overlaps.append(rotated_overlap_ratio(row["_box"], other["_box"]))
            center_distances.append(math.hypot(cx - other["_box"][0], cy - other["_box"][1]))
        neighbor_overlap = max(overlaps, default=0.0)
        neighbor_near = bool(center_distances and min(center_distances) < 1.5 * max(width, height))
        radius, theta = display_xy_to_polar(cx, cy)
        gt = row["_gt"]
        base.append(
            {
                **row,
                "bbox_width_px": width,
                "bbox_height_px": height,
                "bbox_width_meter": "",
                "bbox_height_meter": "",
                "center_x_px": cx,
                "center_y_px": cy,
                "center_x_meter": "",
                "center_y_meter": "",
                "center_radius_px": radius,
                "center_theta_deg": theta,
                "valid_mask_fraction": fan_fraction,
                "fan_geometry_fraction": fan_fraction,
                "touches_invalid_region": fan_fraction < 0.999,
                "touches_fan_geometry_outside": fan_fraction < 0.999,
                "touches_image_boundary": touches_image,
                "neighbor_vehicle_overlap_risk": neighbor_overlap > 0.05 or neighbor_near,
                "neighbor_rotated_overlap_ratio": neighbor_overlap,
                "center_jump_from_previous": math.nan,
                "center_jump_per_sar_frame": math.nan,
                "size_jump_from_previous": math.nan,
                "aspect_jump_from_previous": math.nan,
                "center_jump_outlier": False,
                "size_jump_outlier": False,
                "aspect_jump_outlier": False,
                "gt_visibility_status": gt.get("visibility_status", ""),
            }
        )

    by_thread: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in base:
        if row["canonical_vehicle_id"]:
            by_thread[(row["scene"], row["canonical_vehicle_id"])].append(row)
    for rows in by_thread.values():
        rows.sort(key=lambda item: (int(item["sar_frame_index"]), item["sar_gt_id"]))
        speeds: list[float] = []
        area_changes: list[float] = []
        aspect_changes: list[float] = []
        previous: dict[str, Any] | None = None
        for row in rows:
            if previous is not None:
                delta = max(1, int(row["sar_frame_index"]) - int(previous["sar_frame_index"]))
                jump = math.hypot(row["center_x_px"] - previous["center_x_px"], row["center_y_px"] - previous["center_y_px"])
                speed = jump / delta
                area_prev = max(1e-9, previous["bbox_width_px"] * previous["bbox_height_px"])
                area_now = max(1e-9, row["bbox_width_px"] * row["bbox_height_px"])
                area_change = abs(math.log(area_now / area_prev))
                aspect_prev = max(1e-9, previous["bbox_width_px"] / max(1e-9, previous["bbox_height_px"]))
                aspect_now = max(1e-9, row["bbox_width_px"] / max(1e-9, row["bbox_height_px"]))
                aspect_change = abs(math.log(aspect_now / aspect_prev))
                row["center_jump_from_previous"] = jump
                row["center_jump_per_sar_frame"] = speed
                row["size_jump_from_previous"] = area_change
                row["aspect_jump_from_previous"] = aspect_change
                speeds.append(speed)
                area_changes.append(area_change)
                aspect_changes.append(aspect_change)
            previous = row
        speed_limit = statistics.median(speeds) + 5.0 * max(1.0, median_abs_deviation(speeds)) if speeds else math.inf
        size_limit = statistics.median(area_changes) + 5.0 * max(0.05, median_abs_deviation(area_changes)) if area_changes else math.inf
        aspect_limit = statistics.median(aspect_changes) + 5.0 * max(0.05, median_abs_deviation(aspect_changes)) if aspect_changes else math.inf
        for row in rows:
            row["center_jump_outlier"] = bool(row["center_jump_per_sar_frame"] == row["center_jump_per_sar_frame"] and row["center_jump_per_sar_frame"] > max(18.0, speed_limit))
            row["size_jump_outlier"] = bool(row["size_jump_from_previous"] == row["size_jump_from_previous"] and row["size_jump_from_previous"] > max(0.75, size_limit))
            row["aspect_jump_outlier"] = bool(row["aspect_jump_from_previous"] == row["aspect_jump_from_previous"] and row["aspect_jump_from_previous"] > max(0.75, aspect_limit))

    output: list[dict[str, Any]] = []
    for row in base:
        canonical = row["canonical_vehicle_id"]
        role = row["benchmark_role"]
        visibility = row["gt_visibility_status"]
        link_conf = row["identity_link_confidence"]
        if not canonical:
            status = "exclude_from_structure_discovery" if row["identity_link_status"] == "nonvehicle_optical_source_conflict" else "identity_or_geometry_conflict"
        elif role == "diagnostic_only":
            status = "diagnostic_only"
        elif row["fan_geometry_fraction"] < 0.90 or row["touches_image_boundary"]:
            status = "exclude_from_structure_discovery"
        elif visibility in {"uncertain", "not_visible"} or link_conf in {"none", "low"}:
            status = "diagnostic_only"
        elif visibility == "truncated_visible" or row["touches_fan_geometry_outside"]:
            status = "diagnostic_only"
        elif row["center_jump_outlier"] or row["size_jump_outlier"] or row["aspect_jump_outlier"]:
            status = "diagnostic_only"
        elif row["neighbor_vehicle_overlap_risk"]:
            status = "usable"
        elif row["optical_full_vehicle_visible"] == "true" and link_conf in {"high", "moderate"} and row["fan_geometry_fraction"] >= 0.999:
            status = "gold"
        else:
            status = "usable"

        evidence_parts = [
            f"identity={row['identity_link_status']}:{link_conf}",
            f"optical_visibility={row['optical_visibility_state']}",
            f"fan_fraction={row['fan_geometry_fraction']:.6f}",
            f"neighbor_risk={bool_text(row['neighbor_vehicle_overlap_risk'])}",
            f"jump_outlier={bool_text(row['center_jump_outlier'] or row['size_jump_outlier'] or row['aspect_jump_outlier'])}",
            "visual_review=direct_contact_sheet_and_case_atlas",
        ]
        output.append(
            {
                "scene": row["scene"],
                "canonical_vehicle_id": canonical,
                "benchmark_role": role,
                "sar_frame_index": row["sar_frame_index"],
                "sar_gt_id": row["sar_gt_id"],
                "bbox": row["sar_gt_bbox"],
                "bbox_width_px": fmt(row["bbox_width_px"], 3),
                "bbox_height_px": fmt(row["bbox_height_px"], 3),
                "bbox_width_meter": "",
                "bbox_height_meter": "",
                "center_x_px": fmt(row["center_x_px"], 3),
                "center_y_px": fmt(row["center_y_px"], 3),
                "center_x_meter": "",
                "center_y_meter": "",
                "center_radius_px": fmt(row["center_radius_px"], 3),
                "center_theta_deg": fmt(row["center_theta_deg"], 6),
                "valid_mask_fraction": fmt(row["fan_geometry_fraction"], 9),
                "validity_basis": "deterministic_shared_imaging_valid_mask",
                "fan_geometry_fraction": fmt(row["fan_geometry_fraction"], 9),
                "touches_invalid_region": bool_text(row["touches_fan_geometry_outside"]),
                "touches_fan_geometry_outside": bool_text(row["touches_fan_geometry_outside"]),
                "touches_image_boundary": bool_text(row["touches_image_boundary"]),
                "neighbor_vehicle_overlap_risk": bool_text(row["neighbor_vehicle_overlap_risk"]),
                "neighbor_rotated_overlap_ratio": fmt(row["neighbor_rotated_overlap_ratio"]),
                "center_jump_from_previous": fmt(row["center_jump_from_previous"], 3),
                "center_jump_per_sar_frame": fmt(row["center_jump_per_sar_frame"], 3),
                "size_jump_from_previous": fmt(row["size_jump_from_previous"], 6),
                "aspect_jump_from_previous": fmt(row["aspect_jump_from_previous"], 6),
                "gt_quality_status": status,
                "quality_evidence": ";".join(evidence_parts),
                "identity_link_status": row["identity_link_status"],
                "identity_link_confidence": link_conf,
                "optical_frame_index": row["optical_frame_index"],
                "optical_visibility_state": row["optical_visibility_state"],
                "optical_full_vehicle_visible": row["optical_full_vehicle_visible"],
                "multi_vehicle_competition": row["multi_vehicle_competition"],
                "notes": "meter fields intentionally blank: no authoritative metric imaging grid; GT is a research/evaluation anchor, not a scattering mask",
                "_linked": row,
            }
        )
    return output


def build_golden_threads(quality_rows: Sequence[dict[str, Any]], identity: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_vehicle: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in quality_rows:
        if row["canonical_vehicle_id"]:
            by_vehicle[(row["scene"], row["canonical_vehicle_id"])].append(row)

    result: list[dict[str, Any]] = []
    for registry in identity["registry"]:
        scene = registry["scene"]
        canonical = registry["canonical_vehicle_id"]
        role = identity["role_by_vehicle"][(scene, canonical)]
        rows = sorted(by_vehicle.get((scene, canonical), []), key=lambda item: int(item["sar_frame_index"]))
        frames = sorted({int(row["sar_frame_index"]) for row in rows})
        gold_count = sum(row["gt_quality_status"] == "gold" for row in rows)
        usable_count = sum(row["gt_quality_status"] in {"gold", "usable"} for row in rows)
        full_fraction = (
            sum(row["optical_full_vehicle_visible"] == "true" for row in rows) / len(rows) if rows else 0.0
        )
        theta_values = [parse_float(row["center_theta_deg"]) for row in rows]
        radius_values = [parse_float(row["center_radius_px"]) for row in rows]
        theta_span = max(theta_values) - min(theta_values) if theta_values else 0.0
        radius_span = max(radius_values) - min(radius_values) if radius_values else 0.0
        if theta_span >= 20:
            viewpoint = "high"
        elif theta_span >= 8:
            viewpoint = "moderate"
        elif theta_span > 0:
            viewpoint = "low"
        else:
            viewpoint = "none"
        if radius_span >= 180:
            distance_diversity = "high"
        elif radius_span >= 60:
            distance_diversity = "moderate"
        elif radius_span > 0:
            distance_diversity = "low"
        else:
            distance_diversity = "none"
        competition_fraction = (
            sum(row["multi_vehicle_competition"] == "true" for row in rows) / len(rows) if rows else 0.0
        )
        if competition_fraction >= 0.5:
            competition = "high"
        elif competition_fraction > 0:
            competition = "moderate"
        else:
            competition = "low"
        gaps = [b - a for a, b in zip(frames, frames[1:])]
        if not frames:
            continuity = "no_sar_gt"
        elif max(gaps, default=1) <= 3:
            continuity = "dense_continuous"
        elif statistics.median(gaps) <= 5:
            continuity = "sparse_but_trackable"
        else:
            continuity = "sparse_discontinuous"
        min_fan = min((parse_float(row["fan_geometry_fraction"], 0.0) for row in rows), default=0.0)
        mask_validity = "inside_display_fan" if rows and min_fan >= 0.999 else ("fan_boundary_risk" if rows else "no_gt")

        exclusion_reason = ""
        if not rows:
            recommended = "exclude"
            exclusion_reason = "no canonical-linked SAR GT row"
        elif role == "diagnostic_only":
            recommended = "diagnostic_only"
            exclusion_reason = "P1-E physical-vehicle role is diagnostic_only and is preserved"
        elif usable_count < 3:
            recommended = "diagnostic_only"
            exclusion_reason = "fewer than three gold/usable GT rows"
        elif role == "heldout_validation":
            recommended = "structure_heldout_validation"
        elif gold_count >= 3 and full_fraction >= 0.5 and competition_fraction < 0.5:
            recommended = "mapping_calibration"
        else:
            recommended = "structure_development"

        result.append(
            {
                "scene": scene,
                "canonical_vehicle_id": canonical,
                "benchmark_role": role,
                "sar_frame_start": frames[0] if frames else "",
                "sar_frame_end": frames[-1] if frames else "",
                "gt_frame_count": len(frames),
                "gt_row_count": len(rows),
                "gold_frame_count": gold_count,
                "usable_frame_count": usable_count,
                "optical_full_vehicle_visible_fraction": fmt(full_fraction, 6),
                "viewpoint_or_pose_diversity": viewpoint,
                "sar_theta_span_deg": fmt(theta_span, 6),
                "distance_or_scale_diversity": distance_diversity,
                "sar_radius_span_px": fmt(radius_span, 3),
                "multi_vehicle_competition_level": competition,
                "gt_continuity": continuity,
                "max_sar_frame_gap": max(gaps, default=0),
                "mask_validity": mask_validity,
                "recommended_research_role": recommended,
                "exclusion_reason": exclusion_reason,
                "notes": "P1-E vehicle-level role is inherited without frame-level leakage; no GT interpolation",
            }
        )
    return result


def fit_poly(x: Sequence[float], y: Sequence[float], degree: int) -> np.ndarray:
    if len(x) <= degree:
        return np.full(degree + 1, math.nan, dtype=np.float64)
    return np.polyfit(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64), degree)


def predict_poly(coefficients: np.ndarray, x: float) -> float:
    return float(np.polyval(coefficients, float(x)))


def mapping_metrics(errors: Sequence[float]) -> dict[str, float]:
    values = [abs(value) for value in errors if value == value]
    return {
        "count": len(values),
        "median": statistics.median(values) if values else math.nan,
        "p90": quantile(values, 0.90),
        "maximum": max(values) if values else math.nan,
    }


def build_mapping_audit(quality_rows: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_by_optical_frame: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for quality in quality_rows:
        linked = quality["_linked"]
        if not quality["canonical_vehicle_id"]:
            continue
        if quality["benchmark_role"] not in {"development", "heldout_validation"}:
            continue
        if quality["gt_quality_status"] not in {"gold", "usable"}:
            continue
        if quality["optical_full_vehicle_visible"] != "true":
            continue
        # Multiple vehicles may be present in the frame without making this
        # anchor ambiguous. Exclude only direct GT-region competition here;
        # the identity-link and full-vehicle requirements remain mandatory.
        if parse_float(quality["neighbor_rotated_overlap_ratio"], 0.0) > 0.05:
            continue
        if quality["identity_link_confidence"] not in {"high", "moderate"}:
            continue
        if parse_float(quality["fan_geometry_fraction"]) < 0.999:
            continue
        state = linked["_state"]
        if not parse_bool(state.get("reference_bbox_available")):
            continue
        key = (quality["scene"], quality["canonical_vehicle_id"], int(quality["optical_frame_index"]))
        candidate_by_optical_frame[key].append(quality)

    anchors: list[dict[str, Any]] = []
    for key, rows in candidate_by_optical_frame.items():
        optical_time = int(rows[0]["optical_frame_index"]) / OPTICAL_FPS
        chosen = min(rows, key=lambda row: abs(int(row["sar_frame_index"]) / SAR_FPS - optical_time))
        linked = chosen["_linked"]
        state = linked["_state"]
        optical_center = 0.5 * (parse_float(state["reference_bbox_x1"]) + parse_float(state["reference_bbox_x2"]))
        sar_theta = parse_float(chosen["center_theta_deg"])
        radius = parse_float(chosen["center_radius_px"])
        typical_width = max(parse_float(chosen["bbox_width_px"]), parse_float(chosen["bbox_height_px"]))
        anchors.append(
            {
                "quality": chosen,
                "scene": chosen["scene"],
                "canonical_vehicle_id": chosen["canonical_vehicle_id"],
                "benchmark_role": chosen["benchmark_role"],
                "optical_frame_index": int(chosen["optical_frame_index"]),
                "sar_frame_index": int(chosen["sar_frame_index"]),
                "optical_center_x_px": optical_center,
                "sar_theta_deg": sar_theta,
                "sar_radius_px": radius,
                "typical_vehicle_width_px": typical_width,
            }
        )
    anchors.sort(key=lambda row: (row["scene"], row["canonical_vehicle_id"], row["optical_frame_index"]))

    development = [row for row in anchors if row["benchmark_role"] == "development"]
    heldout = [row for row in anchors if row["benchmark_role"] == "heldout_validation"]
    dev_x = [row["optical_center_x_px"] for row in development]
    dev_y = [row["sar_theta_deg"] for row in development]
    linear = fit_poly(dev_x, dev_y, 1)
    quadratic = fit_poly(dev_x, dev_y, 2)

    dev_vehicle_ids = sorted({row["canonical_vehicle_id"] for row in development})
    loo_linear: dict[tuple[str, str, int], float] = {}
    loo_quadratic: dict[tuple[str, str, int], float] = {}
    for vehicle in dev_vehicle_ids:
        train = [row for row in development if row["canonical_vehicle_id"] != vehicle]
        test = [row for row in development if row["canonical_vehicle_id"] == vehicle]
        coeff_linear = fit_poly([row["optical_center_x_px"] for row in train], [row["sar_theta_deg"] for row in train], 1)
        coeff_quad = fit_poly([row["optical_center_x_px"] for row in train], [row["sar_theta_deg"] for row in train], 2)
        for row in test:
            key = (row["scene"], row["canonical_vehicle_id"], row["optical_frame_index"])
            loo_linear[key] = predict_poly(coeff_linear, row["optical_center_x_px"])
            loo_quadratic[key] = predict_poly(coeff_quad, row["optical_center_x_px"])

    old_dev_errors: list[float] = []
    old_held_errors: list[float] = []
    refit_dev_errors: list[float] = []
    refit_held_errors: list[float] = []
    loo_linear_errors: list[float] = []
    loo_quadratic_errors: list[float] = []
    rows_out: list[dict[str, Any]] = []
    for anchor in anchors:
        x = anchor["optical_center_x_px"]
        truth = anchor["sar_theta_deg"]
        old_pred = OLD_MAPPING_K * x + OLD_MAPPING_B
        refit_pred = predict_poly(linear, x)
        key = (anchor["scene"], anchor["canonical_vehicle_id"], anchor["optical_frame_index"])
        holdout_pred = loo_linear.get(key, refit_pred)
        old_err = old_pred - truth
        refit_err = refit_pred - truth
        holdout_err = holdout_pred - truth
        tangential_px = abs(math.radians(holdout_err) * anchor["sar_radius_px"])
        ratio = tangential_px / max(1e-9, anchor["typical_vehicle_width_px"])
        if anchor["benchmark_role"] == "development":
            old_dev_errors.append(old_err)
            refit_dev_errors.append(refit_err)
            loo_linear_errors.append(holdout_err)
            if key in loo_quadratic:
                loo_quadratic_errors.append(loo_quadratic[key] - truth)
            fit_membership = "development_vehicle_leave_one_out_evaluation"
        else:
            old_held_errors.append(old_err)
            refit_held_errors.append(refit_err)
            fit_membership = "heldout_evaluation_only_no_fit"
        rows_out.append(
            {
                "scene": anchor["scene"],
                "canonical_vehicle_id": anchor["canonical_vehicle_id"],
                "benchmark_role": anchor["benchmark_role"],
                "sar_gt_id": anchor["quality"]["sar_gt_id"],
                "optical_frame_index": anchor["optical_frame_index"],
                "sar_frame_index": anchor["sar_frame_index"],
                "optical_center_x_px": fmt(x, 6),
                "sar_gt_center_x_px": anchor["quality"]["center_x_px"],
                "sar_gt_center_y_px": anchor["quality"]["center_y_px"],
                "sar_theta_deg": fmt(truth, 9),
                "sar_radius_px": fmt(anchor["sar_radius_px"], 6),
                "anchor_quality_status": anchor["quality"]["gt_quality_status"],
                "anchor_identity_confidence": anchor["quality"]["identity_link_confidence"],
                "model_fit_membership": fit_membership,
                "old_mapping_pred_theta_deg": fmt(old_pred, 9),
                "old_mapping_error_deg": fmt(old_err, 9),
                "refit_linear_pred_theta_deg": fmt(refit_pred, 9),
                "refit_linear_error_deg": fmt(refit_err, 9),
                "vehicle_holdout_pred_theta_deg": fmt(holdout_pred, 9),
                "vehicle_holdout_error_deg": fmt(holdout_err, 9),
                "vehicle_holdout_tangential_error_px": fmt(tangential_px, 6),
                "vehicle_holdout_tangential_error_meter": "",
                "error_to_typical_vehicle_width_ratio": fmt(ratio, 6),
                "mapping_coordinate_domain": "display_fan_azimuth_deg",
                "mapping_status": "PENDING_FINAL_AUDIT_DECISION",
                "notes": "meter error intentionally blank because the upstream metric imaging grid is unresolved",
            }
        )

    loo_linear_metric = mapping_metrics(loo_linear_errors)
    loo_quad_metric = mapping_metrics(loo_quadratic_errors)
    selected_model = "linear_center_x_diagnostic_only"
    if (
        loo_quad_metric["count"] >= 10
        and loo_quad_metric["median"] == loo_quad_metric["median"]
        and loo_linear_metric["median"] == loo_linear_metric["median"]
        and loo_quad_metric["median"] < 0.80 * loo_linear_metric["median"]
    ):
        selected_model = "quadratic_center_x_diagnostic_only"

    per_scene_bias: dict[str, float] = {}
    for scene in SCENES:
        values = [
            parse_float(row["vehicle_holdout_error_deg"])
            for row in rows_out
            if row["scene"] == scene and row["vehicle_holdout_error_deg"]
        ]
        per_scene_bias[scene] = statistics.median(values) if values else math.nan

    loo_coverage_complete = loo_linear_metric["count"] == len(development)
    cross_scene_extreme = any(abs(value) > 8.0 for value in per_scene_bias.values() if value == value)
    mapping_status = "MAPPING_PARTIALLY_READY"
    if not loo_coverage_complete or cross_scene_extreme or mapping_metrics(refit_held_errors)["maximum"] > 10.0:
        mapping_status = "MAPPING_BLOCKED"
        selected_model = "no_model_frozen"
    for row in rows_out:
        row["mapping_status"] = mapping_status

    summary = {
        "status": mapping_status,
        "selected_model": selected_model,
        "linear_coefficients": {"k": float(linear[0]), "b": float(linear[1])},
        "quadratic_coefficients": [float(value) for value in quadratic],
        "development_anchor_count": len(development),
        "development_vehicle_count": len(dev_vehicle_ids),
        "heldout_anchor_count": len(heldout),
        "heldout_vehicle_count": len({row["canonical_vehicle_id"] for row in heldout}),
        "old_development": mapping_metrics(old_dev_errors),
        "old_heldout": mapping_metrics(old_held_errors),
        "refit_development_in_sample": mapping_metrics(refit_dev_errors),
        "refit_heldout": mapping_metrics(refit_held_errors),
        "development_vehicle_leave_one_out_linear": loo_linear_metric,
        "development_vehicle_leave_one_out_quadratic": loo_quad_metric,
        "scene_median_holdout_residual_deg": per_scene_bias,
        "development_loo_anchor_coverage_complete": loo_coverage_complete,
        "cross_scene_extreme_residual_detected": cross_scene_extreme,
        "freeze_decision": "mapping_not_frozen; old and refit models remain diagnostic only until development vehicle coverage and scene consistency are repaired",
    }
    return rows_out, summary


def crop_with_margin(image: np.ndarray, box: Sequence[float], margin: float = 0.65) -> np.ndarray:
    x1, y1, x2, y2 = [float(value) for value in box]
    width = max(8.0, x2 - x1)
    height = max(8.0, y2 - y1)
    x1 = int(max(0, math.floor(x1 - margin * width)))
    y1 = int(max(0, math.floor(y1 - margin * height)))
    x2 = int(min(image.shape[1], math.ceil(x2 + margin * width)))
    y2 = int(min(image.shape[0], math.ceil(y2 + margin * height)))
    if x2 <= x1 or y2 <= y1:
        return image
    return image[y1:y2, x1:x2]


def build_case_tile(row: dict[str, Any], width: int = 480, height: int = 230) -> np.ndarray:
    linked = row["_linked"]
    queue = linked["_queue"]
    optical = cv2.imread(str(linked["_gt"]["optical_path"]), cv2.IMREAD_COLOR)
    sar = cv2.imread(str(gray_path(row["scene"], int(row["sar_frame_index"]))), cv2.IMREAD_COLOR)
    if optical is None or sar is None:
        raise FileNotFoundError(f"visual source missing for {row['sar_gt_id']}")

    optical_box: tuple[float, float, float, float] | None = None
    if queue.get("opt_x1", "").strip():
        optical_box = tuple(parse_float(queue[name]) for name in ("opt_x1", "opt_y1", "opt_x2", "opt_y2"))
        cv2.rectangle(
            optical,
            (int(round(optical_box[0])), int(round(optical_box[1]))),
            (int(round(optical_box[2])), int(round(optical_box[3]))),
            (0, 255, 0),
            3,
        )
    state = linked["_state"]
    if parse_bool(state.get("reference_bbox_available")):
        reference_box = tuple(parse_float(state[name]) for name in ("reference_bbox_x1", "reference_bbox_y1", "reference_bbox_x2", "reference_bbox_y2"))
        cv2.rectangle(
            optical,
            (int(round(reference_box[0])), int(round(reference_box[1]))),
            (int(round(reference_box[2])), int(round(reference_box[3]))),
            (255, 255, 0),
            2,
        )
        crop_box = reference_box if optical_box is None else optical_box
    else:
        crop_box = optical_box
    optical_crop = crop_with_margin(optical, crop_box, 0.45) if crop_box is not None else optical

    cx = parse_float(row["center_x_px"])
    cy = parse_float(row["center_y_px"])
    bw = parse_float(row["bbox_width_px"])
    bh = parse_float(row["bbox_height_px"])
    heading = parse_float(linked["_gt"]["final_heading_deg"])
    points = np.rint(rotated_points(cx, cy, bw, bh, heading)).astype(np.int32)
    cv2.polylines(sar, [points], True, (0, 0, 255), 4, cv2.LINE_AA)
    axis_box = (cx - 0.5 * max(bw, bh), cy - 0.5 * max(bw, bh), cx + 0.5 * max(bw, bh), cy + 0.5 * max(bw, bh))
    sar_crop = crop_with_margin(sar, axis_box, 1.2)

    panel_h = height - 38
    left = cv2.resize(optical_crop, (width // 2, panel_h), interpolation=cv2.INTER_AREA)
    right = cv2.resize(sar_crop, (width - width // 2, panel_h), interpolation=cv2.INTER_AREA)
    tile = np.full((height, width, 3), 22, dtype=np.uint8)
    tile[:panel_h, : width // 2] = left
    tile[:panel_h, width // 2 :] = right
    cid = row["canonical_vehicle_id"] or "UNLINKED"
    line1 = f"{row['scene']} o{row['optical_frame_index']} s{row['sar_frame_index']} {cid}"
    line2 = f"{row['gt_quality_status']} link={row['identity_link_confidence']} fan={parse_float(row['fan_geometry_fraction']):.3f}"
    draw_label(tile, line1, (4, panel_h + 15))
    draw_label(tile, line2, (4, panel_h + 32))
    return tile


def save_case_pages(rows: Sequence[dict[str, Any]], prefix: str, per_page: int = 32) -> list[str]:
    paths: list[str] = []
    columns = 4
    tile_w, tile_h = 480, 230
    for page_index, start in enumerate(range(0, len(rows), per_page), start=1):
        page_rows = rows[start : start + per_page]
        page_grid_rows = math.ceil(len(page_rows) / columns)
        page = np.full((page_grid_rows * tile_h, columns * tile_w, 3), 36, dtype=np.uint8)
        for index, row in enumerate(page_rows):
            tile = build_case_tile(row, tile_w, tile_h)
            grid_row, grid_col = divmod(index, columns)
            page[grid_row * tile_h : (grid_row + 1) * tile_h, grid_col * tile_w : (grid_col + 1) * tile_w] = tile
        path = VISUAL_OUTPUT / f"{prefix}_{page_index:02d}.png"
        cv2.imwrite(str(path), page)
        paths.append(str(path))
    return paths


def build_visual_review_assets(quality_rows: Sequence[dict[str, Any]], mapping_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    print("[visual] generating complete GT case atlas", flush=True)
    all_rows = sorted(quality_rows, key=lambda row: (row["scene"], int(row["sar_frame_index"]), row["sar_gt_id"]))
    all_pages = save_case_pages(all_rows, "gt_all_cases")

    anomaly_rows = [
        row
        for row in all_rows
        if row["gt_quality_status"] not in {"gold", "usable"}
        or row["touches_fan_geometry_outside"] == "true"
        or row["neighbor_vehicle_overlap_risk"] == "true"
        or parse_float(row["center_jump_per_sar_frame"], 0.0) > 18.0
    ]
    anomaly_pages = save_case_pages(anomaly_rows, "gt_anomaly_mask_competition_jump") if anomaly_rows else []

    anchor_ids = {row["sar_gt_id"] for row in mapping_rows}
    anchor_rows = [row for row in all_rows if row["sar_gt_id"] in anchor_ids]
    anchor_pages = save_case_pages(anchor_rows, "mapping_anchor_cases") if anchor_rows else []

    by_vehicle: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        if row["canonical_vehicle_id"] and row["gt_quality_status"] in {"gold", "usable"}:
            by_vehicle[(row["scene"], row["canonical_vehicle_id"])].append(row)
    representatives: list[dict[str, Any]] = []
    for rows in by_vehicle.values():
        rows.sort(key=lambda row: int(row["sar_frame_index"]))
        indices = sorted({0, len(rows) // 2, len(rows) - 1})
        representatives.extend(rows[index] for index in indices)
    representative_pages = save_case_pages(representatives, "golden_thread_representatives") if representatives else []

    manifest = {
        "full_stream_contact_sheets": [
            str(VISUAL_OUTPUT / f"{scene}_full_stream_gray_left_pseudocolor_right.png") for scene in SCENES
        ],
        "all_gt_case_pages": all_pages,
        "anomaly_case_pages": anomaly_pages,
        "mapping_anchor_pages": anchor_pages,
        "golden_thread_representative_pages": representative_pages,
        "all_gt_case_count": len(all_rows),
        "anomaly_case_count": len(anomaly_rows),
        "mapping_anchor_case_count": len(anchor_rows),
        "representative_case_count": len(representatives),
        "review_scope": "all 2298 gray frames; all 2298 same-index pseudocolor frames; all 442 reviewed GT rows; dedicated anomalies and mapping anchors",
    }
    write_json(TEMP_OUTPUT / "visual_review_manifest.json", manifest)
    return manifest


def build_coordinate_contract() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scene in SCENES:
        for asset_type in ("sar_gray_frame", "sar_pseudocolor_frame"):
            rows.append(
                {
                    "scene": scene,
                    "sar_asset_type": asset_type,
                    "image_width": WIDTH,
                    "image_height": HEIGHT,
                    "grid_type": "cartesian_display_pixel_canvas_with_reconstructed_fan_polar_interpretation;upstream_imaging_grid_unresolved",
                    "x_axis_physical_meaning": "display horizontal pixel; fan tangential direction varies with radius/azimuth",
                    "y_axis_physical_meaning": "display vertical pixel; physical range is radial distance from fan origin, not uniform image y",
                    "x_axis_direction": "positive_right_in_display",
                    "y_axis_direction": "positive_down_in_display;radial_range_increases_away_from_origin",
                    "radar_origin_pixel_x": fmt(FAN_CENTER_X, 3),
                    "radar_origin_pixel_y": fmt(FAN_CENTER_Y, 3),
                    "x_min_meter": "",
                    "x_max_meter": "",
                    "y_min_meter": "",
                    "y_max_meter": "",
                    "x_meter_per_pixel_or_formula": "UNRESOLVED_NO_UNIFORM_METRIC_X; historical display formula x=cx+r_px*sin(theta)",
                    "y_meter_per_pixel_or_formula": "UNRESOLVED_NO_UNIFORM_METRIC_Y; historical display formula y=cy-r_px*cos(theta)",
                    "radial_pixel_formula": "r_px=hypot(x-1154.0,y-1330.6)",
                    "azimuth_formula": "theta_deg=atan2(x-1154.0,1330.6-y)",
                    "historical_radial_grid_spacing_claim": "0.03 m/pixel",
                    "historical_claim_interpretation": "project/local evaluation radial grid-spacing hypothesis; not independently traced to current upstream imaging code or resolution evidence",
                    "coordinate_source": "src/geometry/fan_polar.py;historical workspace fan fallback;WGV3.5A mask reconstruction;P0 missing-imaging-config audit",
                    "is_cartesian": "true_as_display_canvas;false_or_unresolved_as_authoritative_physical_metric_grid",
                    "is_resampled": "display_fan_raster_confirmed;upstream_resampling_chain_unresolved",
                    "resolution_interpretation": "pixel sampling is not range resolution, azimuth resolution, PSF width, or vehicle-structure resolving power",
                    "confidence_status": "PARTIAL_DISPLAY_COORDINATE_CONFIRMED_METRIC_GRID_BLOCKED",
                    "notes": "pseudocolor shares the same display grid and is not a new physical measurement",
                }
            )
    return rows


def asset_summary() -> dict[str, Any]:
    index = asset_manifest_index()
    result: dict[str, Any] = {}
    for scene in SCENES:
        result[scene] = {}
        for role in (
            "sar_gray_frame",
            "sar_pseudocolor_frame",
            "sar_gray_source_video",
            "sar_pseudocolor_source_video",
            "raw_adc_iq",
            "range_compressed_intermediate",
            "complex_imaging_result",
            "sar_effective_imaging_mask",
            "acquisition_config",
            "imaging_config",
            "final_gt_table",
        ):
            row = index[(scene, role)]
            result[scene][role] = {
                "path": row["relative_path"],
                "status": row["source_or_derived"],
                "dimensions": f"{row.get('width','')}x{row.get('height','')}" if row.get("width") else "",
                "frame_count": row.get("frame_count", ""),
                "fps": row.get("fps", ""),
                "notes": row.get("notes", ""),
            }
    return result


def formal_hashes() -> dict[str, str]:
    return {str(path.relative_to(REPO_ROOT)).replace("\\", "/"): sha256_file(path) for path in FORMAL_OUTPUTS if path.exists()}


def count_by(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "")) for row in rows).items()))


def write_protocol() -> None:
    # S0-M owns the revised protocol and prevents the base S0 replay from
    # restoring the superseded unknown-mask interpretation.
    return
    write_text(
        DOCS_DIR / "OTY2_S0_SAR_GT_STRUCTURE_FOUNDATION_PROTOCOL.md",
        f"""# OTY2 S0 SAR GT Structure Foundation Protocol

Date: `{EXECUTION_DATE}`
Frozen base: `{BASE_COMMIT}`
Branch: `feature/oty2-sar-gt-structure-foundation`

## Purpose

S0 audits the available SAR display products, their coordinate and mask semantics, gray-to-pseudocolor lineage, P1-E canonical-vehicle links to reviewed SAR GT, GT quality, vehicle-level research roles, and the optical-center to SAR display-azimuth mapping.

This stage does not repair optical P1-F identity, consume P1-F propagation/recovery outputs, change P0 hard synchronization, change the P1-E canonical benchmark, infer a vehicle-response mask, generate candidates, run a Gate/selector/ranking/oracle, train a model, or start S1 structure dynamics.

## Authoritative inputs

- P0 asset manifest and fixed 24/50 hard-sync manifests from `{BASE_COMMIT}`.
- P1-E canonical registry, 8,096 frame-state rows, vehicle-level roles, and detection-to-canonical provenance from `{BASE_COMMIT}`.
- Three complete optical streams, three complete SAR gray streams, and three complete SAR pseudocolor streams under `D:\\profile\\research\\data`.
- The reviewed 442-row `final_gt_working.csv` and aligned `review_queue.csv`.

The project common-start relation remains an operational frozen assumption, not shared-hardware-clock evidence. SAR gray at 50 fps is authoritative. Pseudocolor inherits the timestamp of the same-index gray frame.

## Coordinate rule

S0 freezes only the reproducible display coordinate:

```text
r_px = hypot(x - 1154.0, y - 1330.6)
theta_deg = atan2(x - 1154.0, 1330.6 - y)
x = 1154.0 + r_px * sin(theta)
y = 1330.6 - r_px * cos(theta)
```

The upstream acquisition/imaging grid, maximum metric range, range/azimuth resolution, PSF, and an authoritative pixel-to-meter transform remain unresolved. `0.03 m/pixel` is retained only as a historical/project-local radial grid-spacing claim, not as proven full-image metric scale or actual resolution.

## Mask rule

`imaging_valid_mask` is the fixed shared fan geometry. `display_nonzero_mask` and `fixed_black_region_inside_mask` remain separate rendered-pixel masks. GT boxes are research/evaluation regions and are never vehicle-scattering masks.

## Vehicle and split rule

Canonical links use P1-E benchmark provenance only. The P1-E vehicle-level role is inherited intact; a single canonical vehicle is never split by frame between development and heldout claims. Sparse GT is not interpolated.

## Mapping rule

Mapping is evaluated in `display_fan_azimuth_deg`. Development vehicles fit the model; development validation is leave-one-vehicle-out; heldout vehicles are evaluation-only. No heldout row participates in fitting. Metric error remains blank until the physical grid is resolved.

## Reproducibility and visual review

Run:

```powershell
D:\\MINICONDA\\envs\\py311\\python.exe tools\\diagnostics\\run_oty2_s0_sar_gt_structure_foundation_audit.py
D:\\MINICONDA\\envs\\py311\\python.exe tools\\diagnostics\\validate_oty2_s0_sar_foundation_outputs.py
```

Temporary contact sheets and case atlases are written only to `{VISUAL_OUTPUT}` and are not committed.

## Stage boundary

The only valid S0 status produced by the current evidence is `S0_SAR_FOUNDATION_PARTIALLY_READY`: the imaging-valid mask, display geometry, lineage, GT threads, and quality audit are reproducible, while authoritative metric coordinates and mapping freeze remain blocked. S1 entry is therefore not authorized.
""",
    )


def write_coordinate_doc(mask_summary: Mapping[str, Any]) -> None:
    # The S0-M contract is maintained by the follow-up audit.
    return
    scene_lines = []
    for scene in SCENES:
        item = mask_summary[scene]
        scene_lines.append(
            f"| {scene} | {item['fan_geometry_pixel_count']} | {item['fixed_black_inside_fan_pixel_count']} | "
            f"{item['fixed_black_inside_fan_fraction_of_fan']:.6f} | {item['per_frame_nonzero_min']}..{item['per_frame_nonzero_max']} |"
        )
    write_text(
        DOCS_DIR / "OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md",
        f"""# OTY2 S0 SAR Coordinate and Grid Contract

Date: `{EXECUTION_DATE}`
Status: `PARTIAL_DISPLAY_COORDINATE_CONFIRMED_METRIC_GRID_BLOCKED`

## Frozen conclusion

The `2308×1334` files are a Cartesian **display pixel canvas** containing a fan-shaped raster. The display canvas supports a reproducible fan-polar interpretation with origin `(1154.0, 1330.6)` and radius `1332.7 px`. This does not prove the upstream SAR imager produced a Cartesian metric grid, nor does it prove a uniform metric scale in either display axis.

The only frozen transforms are:

```text
r_px = hypot(x - 1154.0, y - 1330.6)
theta_deg = atan2(x - 1154.0, 1330.6 - y)
x = 1154.0 + r_px * sin(theta)
y = 1330.6 - r_px * cos(theta)
```

- display `x` increases right;
- display `y` increases down;
- radial distance increases away from the bottom-center origin;
- local tangential direction changes with `theta` and range;
- no uniform full-image `m/px` is allowed.

## Why metric coordinates are not frozen

No current-scene ADC/IQ, range-compressed array, complex image matrix, acquisition configuration, imaging configuration, grid-generation code, maximum physical range, PRF/aperture definition, or independent imaging-time mask was found. The checked MATLAB toolbox is only a similar-imaging reference and is not the OTY2 pipeline.

The historical `0.03 m/pixel` value is therefore classified as a project/local evaluation radial grid-spacing claim. It is not independently traceable to the current imaging pipeline and must not be described as:

- uniform Cartesian scale over the full image;
- range resolution;
- azimuth resolution;
- PSF/main-lobe width;
- actual vehicle-structure resolving power.

Metric `x/y`, metric GT width/height, and metric mapping error are intentionally blank in S0 manifests.

## Raster operations

No S0 evidence proves the upstream crop/flip/rotation/resampling chain. The current display formula itself is reproducible and uses no additional flip or rotation after loading the PNG. Pseudocolor and gray use the same `2308×1334` display grid.

## Mask separation

- `imaging_valid_mask`: fixed shared fan, `r<=1332.7` and `-90<=theta<=90`.
- `fan_geometry_mask`: backward-compatible geometry alias of `imaging_valid_mask`.
- `display_nonzero_mask`: per-frame gray intensity `>0`.
- `fixed_black_region_inside_mask`: zero in every gray frame while inside `imaging_valid_mask`.
- `gt_box_region`: reviewed rotated GT region, not scattering truth.
- `gt_valid_intersection_mask`: reproducible intersection of each GT region and `imaging_valid_mask`.
- `vehicle_response_mask`, `registration_valid_mask`, and `occlusion_or_boundary_missing_mask`: semantic contracts only in S0.

| scene | fan pixels | fixed black inside fan | fixed-black/fan | per-frame nonzero pixels |
| --- | ---: | ---: | ---: | ---: |
{os.linesep.join(scene_lines)}

The empirical black region is a rendered-pixel fact. It does not distinguish physical non-imaging, invalid samples, clipping, display masking, or true zero return.

## Permitted use

The display `(x,y)`, `r_px`, `theta_deg`, fan geometry, and display-only masks may be used for S0 research indexing and display-angle mapping audit. They may not be promoted to a solved physical calibration. S1 remains blocked until the authoritative metric imaging grid and physical valid-mask semantics are supplied or independently reconstructed from the true imager.
""",
    )


def metric_line(label: str, values: Mapping[str, Any]) -> str:
    return f"| {label} | {values['count']} | {fmt(values['median'], 6)} | {fmt(values['p90'], 6)} | {fmt(values['maximum'], 6)} |"


def write_mapping_doc(mapping: Mapping[str, Any]) -> None:
    # The S0-M mapping contract is maintained by the follow-up audit.
    return
    k = mapping["linear_coefficients"]["k"]
    b = mapping["linear_coefficients"]["b"]
    metrics = [
        metric_line("old mapping / development", mapping["old_development"]),
        metric_line("old mapping / heldout", mapping["old_heldout"]),
        metric_line("refit linear / development in-sample", mapping["refit_development_in_sample"]),
        metric_line("refit linear / development vehicle LOO", mapping["development_vehicle_leave_one_out_linear"]),
        metric_line("refit quadratic / development vehicle LOO", mapping["development_vehicle_leave_one_out_quadratic"]),
        metric_line("refit linear / heldout", mapping["refit_heldout"]),
    ]
    scene_bias = "\n".join(f"- {scene}: `{fmt(value, 6)} deg` median residual" for scene, value in mapping["scene_median_holdout_residual_deg"].items())
    write_text(
        DOCS_DIR / "OTY2_S0_OPTICAL_TO_SAR_AZIMUTH_MAPPING_CONTRACT.md",
        f"""# OTY2 S0 Optical-to-SAR Azimuth Mapping Contract

Date: `{EXECUTION_DATE}`
Status: `{mapping['status']}`

## Domain and anchors

The mapping target is SAR **display-fan azimuth**, not metric cross-range:

```text
x_optical_reference_center_px -> theta_SAR_display_deg
```

Anchors require a P1-E canonical link, `gold` or `usable` reviewed GT, full optical vehicle visibility, no explicit multi-vehicle competition, and high/moderate identity-link confidence. Development vehicles fit models. Development validation leaves one whole vehicle out. Heldout vehicles are evaluated once and never enter fitting.

- development anchors: `{mapping['development_anchor_count']}` from `{mapping['development_vehicle_count']}` vehicles;
- heldout anchors: `{mapping['heldout_anchor_count']}` from `{mapping['heldout_vehicle_count']}` vehicles.

## Models

Historical fallback:

```text
theta = {OLD_MAPPING_K} * x_optical + ({OLD_MAPPING_B})
```

Current development-only linear refit:

```text
theta = {k:.12f} * x_optical + ({b:.12f})
```

The audited selection remains linear. A quadratic comparison is reported only to detect edge nonlinearity; it is not promoted from a small improvement without stable whole-vehicle validation.

## Absolute angular error

| evaluation | n | median deg | P90 deg | max deg |
| --- | ---: | ---: | ---: | ---: |
{os.linesep.join(metrics)}

Scene residual check:

{scene_bias}

Per-anchor tangential pixel error is approximated as `abs(error_rad) * r_px` and is also reported relative to the GT box's typical pixel width. Metric error is blank because the physical imaging grid is unresolved.

## Freeze decision

`{mapping['status']}`.

No mapping model is frozen. Development vehicle leave-one-out coverage is complete: `{str(mapping['development_loo_anchor_coverage_complete']).lower()}`. Cross-scene extreme residual detected: `{str(mapping['cross_scene_extreme_residual_detected']).lower()}`. The old and development-only refit remain diagnostic comparisons; they must not be retuned per frame, per GT, or from heldout vehicles. No GT-driven time offset or hard-sync modification was performed.
""",
    )


def write_main_report(
    assets: Mapping[str, Any],
    stream_summary: Mapping[str, Any],
    linked_rows: Sequence[dict[str, Any]],
    quality_rows: Sequence[dict[str, Any]],
    golden_rows: Sequence[dict[str, Any]],
    mapping: Mapping[str, Any],
    visual_manifest: Mapping[str, Any],
) -> None:
    # The S0-M report supersedes the base S0 report generator.
    return
    linked_counts = Counter(row["scene"] for row in linked_rows if row["canonical_vehicle_id"])
    linked_vehicle_counts = {
        scene: len({row["canonical_vehicle_id"] for row in linked_rows if row["scene"] == scene and row["canonical_vehicle_id"]})
        for scene in SCENES
    }
    unresolved_counts = Counter(row["scene"] for row in linked_rows if not row["canonical_vehicle_id"])
    quality_counts = Counter(row["gt_quality_status"] for row in quality_rows)
    recommended_counts = Counter(row["recommended_research_role"] for row in golden_rows)
    research_threads = [
        row
        for row in golden_rows
        if row["recommended_research_role"] in {"mapping_calibration", "structure_development", "structure_heldout_validation"}
    ]
    canonical_with_gt = len({(row["scene"], row["canonical_vehicle_id"]) for row in linked_rows if row["canonical_vehicle_id"]})

    asset_lines = []
    for scene in SCENES:
        scene_assets = assets[scene]
        asset_lines.append(
            f"| {scene} | 766 gray PNG + 50 fps gray MP4 | 766 pseudocolor PNG + "
            f"{scene_assets['sar_pseudocolor_source_video']['fps']} fps container | reviewed GT table | "
            "ADC/IQ no; range-compressed no; complex image no; imaging config no |"
        )
    stream_lines = []
    for scene in SCENES:
        item = stream_summary[scene]
        stream_lines.append(
            f"| {scene} | {item['gradient_alignment_min']:.4f} | {item['gradient_alignment_median']:.4f} | "
            f"{item['fixed_black_inside_fan_fraction_of_fan']:.6f} |"
        )
    thread_lines = []
    for scene in SCENES:
        thread_lines.append(
            f"| {scene} | {linked_vehicle_counts[scene]} | {linked_counts[scene]} | {unresolved_counts[scene]} |"
        )

    mapping_metrics_lines = [
        metric_line("development vehicle LOO linear", mapping["development_vehicle_leave_one_out_linear"]),
        metric_line("heldout linear", mapping["refit_heldout"]),
        metric_line("old mapping development", mapping["old_development"]),
        metric_line("old mapping heldout", mapping["old_heldout"]),
    ]

    write_text(
        REPORTS_DIR / "oty2_s0_sar_gt_structure_foundation_audit_20260715.md",
        f"""# OTY2 S0 SAR GT Structure Foundation Audit (20260715)

## 1. Executive result

- Execution mode: independent parallel worktree.
- Frozen SAR base/start HEAD: `{BASE_COMMIT}`.
- Worktree: `D:\\profile\\research\\optical-sar-visual-diagnosis-sar-foundation`.
- Branch: `feature/oty2-sar-gt-structure-foundation`.
- S0 state: `S0_SAR_FOUNDATION_PARTIALLY_READY`.
- Mapping state: `{mapping['status']}`.
- S1 entry allowed: `false`.

The display fan coordinate, fixed imaging-valid mask, full gray/pseudocolor index lineage, canonical-to-GT research links, per-GT quality audit, vehicle-level research-role preservation, and display-angle mapping evaluation are reproducible. S0 cannot be `READY` because the current-scene acquisition/imaging configuration, complex or intermediate matrices, authoritative metric grid, and mapping freeze remain unavailable.

## 2. SAR asset lineage

| scene | gray asset | pseudocolor asset | GT | unavailable upstream assets |
| --- | --- | --- | --- | --- |
{os.linesep.join(asset_lines)}

No current-scene raw ADC/IQ, range-compressed result, slow-time/aperture matrix, complex SAR image, amplitude/power matrix prior to 8-bit display conversion, current-pipeline MATLAB `.mat`, authoritative acquisition configuration, authoritative imaging configuration, or independent physical valid mask was located. The available gray PNG is an 8-bit three-channel container with identical channels; it does not retain phase. Pseudocolor is an 8-bit display derivative and does not add a physical observation dimension.

## 3. Coordinate and `0.03 m/pixel`

The unique reproducible coordinate is a Cartesian display canvas with fan-polar interpretation:

```text
r_px = hypot(x - 1154.0, y - 1330.6)
theta_deg = atan2(x - 1154.0, 1330.6 - y)
```

The display origin is near the bottom center. Range-like behavior is radial, not uniform image `y`; tangential metric width depends on range and angle. `0.03 m/pixel` is retained as a historical/project-local radial grid-spacing claim only. It is not proven full-image Cartesian scale and is not range resolution, azimuth resolution, PSF width, or actual vehicle-structure resolving power. Meter fields are intentionally blank.

## 4. Mask audit

`imaging_valid_mask` is reproducible from the shared fan formula. `display_nonzero_mask` and the full-stream `fixed_black_region_inside_mask` remain separate rendered-pixel facts. GT/valid-mask intersection is reported directly and is never treated as vehicle-response support.

| scene | min gray-pseudo gradient alignment | median alignment | fixed black / fan |
| --- | ---: | ---: | ---: |
{os.linesep.join(stream_lines)}

The three scenes use the same fan formula, but their empirical always-black and stable-nonzero masks are scene-derived. Black pixels may reflect display masking, clipping, un-imaged regions, invalid samples, or true zero return; S0 cannot uniquely distinguish them.

## 5. Gray/pseudocolor lineage and GM_RM019 timebase

All three scenes have exactly 766 gray and 766 same-index pseudocolor PNGs with identical dimensions. Full-stream gradient structure remains aligned in every pair. P0 already verified source-video decoding against frame 0, 100, and last PNG.

GM_RM019's pseudocolor MP4 reports about `48.300063 fps`, while the gray source is `50 fps`. Because the indexed PNG streams remain one-to-one and pseudocolor is a display derivative, the conflict is classified as container/encoding timebase metadata, not a second sensor clock. Gray `50 fps` is authoritative; pseudocolor frame `j` inherits `j/50` seconds. No video was re-encoded.

## 6. Canonical vehicle to SAR GT threads

| scene | canonical vehicles with linked GT | linked GT rows | unresolved/nonvehicle-conflict rows |
| --- | ---: | ---: | ---: |
{os.linesep.join(thread_lines)}

Across the 22 P1-E canonical vehicles, `{canonical_with_gt}` have at least one defensible SAR GT link. The 442 reviewed rows remain sparse research anchors; missing GT never means missing SAR response, and no missing row is interpolated into GT. Optical full occlusion, partial visibility, and multi-vehicle competition are carried explicitly.

## 7. GT quality

- `gold`: `{quality_counts['gold']}`
- `usable`: `{quality_counts['usable']}`
- `diagnostic_only`: `{quality_counts['diagnostic_only']}`
- `identity_or_geometry_conflict`: `{quality_counts['identity_or_geometry_conflict']}`
- `exclude_from_structure_discovery`: `{quality_counts['exclude_from_structure_discovery']}`

Quality combines P1-E identity provenance, optical visibility, reviewed GT geometry, reconstructed fan contact, image boundary, same-frame vehicle competition, center/size/aspect continuity, and direct atlas review. It is not an area-only or IoU-only score. Meter dimensions are not fabricated.

## 8. Golden vehicle threads

`{len(research_threads)}` vehicle-level threads are admitted for mapping development, structure development, or heldout structure validation. Role counts are `{dict(sorted(recommended_counts.items()))}`. Every vehicle inherits one P1-E role for all frames; no vehicle is split between discovery and heldout claims.

## 9. Azimuth mapping

Current development-only refit:

```text
theta_display_deg = {mapping['linear_coefficients']['k']:.12f} * x_optical_center_px + ({mapping['linear_coefficients']['b']:.12f})
```

| evaluation | n | median deg | P90 deg | max deg |
| --- | ---: | ---: | ---: | ---: |
{os.linesep.join(mapping_metrics_lines)}

The audit uses `{mapping['development_anchor_count']}` development anchors from `{mapping['development_vehicle_count']}` vehicles and `{mapping['heldout_anchor_count']}` heldout anchors from `{mapping['heldout_vehicle_count']}` heldout vehicles. Development validation is whole-vehicle leave-one-out; heldout anchors do not fit any coefficient. Tangential pixel error and error/vehicle-width ratio are reported per anchor. Metric error is blocked.

Freeze decision: no model is frozen. Development vehicle leave-one-out coverage is incomplete and scene-extreme residuals remain large; both the old and refit formulas are diagnostic only. Status is `{mapping['status']}`.

## 10. Complete visual review

Direct visual artifacts were generated for:

- all 2,298 gray frames and all 2,298 same-index pseudocolor frames in three full-stream contact sheets;
- all `{visual_manifest['all_gt_case_count']}` reviewed GT rows;
- all `{visual_manifest['anomaly_case_count']}` automatic anomaly/mask/competition/jump cases;
- all `{visual_manifest['mapping_anchor_case_count']}` mapping anchors;
- `{visual_manifest['representative_case_count']}` golden-thread representative cases.

These assets are temporary and live only under `{VISUAL_OUTPUT}`. They are excluded from Git.

## 11. Remaining blockers

1. True current-scene acquisition/imaging code and configuration.
2. Raw or intermediate complex/amplitude/power matrices with lineage.
3. Authoritative maximum range and pixel-to-meter grid generation.
4. Physical range and azimuth resolution/PSF evidence.
5. Independent physical metric-grid and resolution evidence beyond the frozen imaging-support geometry.
6. Manual resolution for the remaining unresolved or identity-conflict GT rows.
7. Physical metric validation of the display-angle mapping.

Because blockers 1-5 directly violate S0 READY conditions, S1 is not authorized.

## 12. Explicit non-execution

This run did not use P1-C global IDs as physical truth, did not consume P1-F propagation/recovery outputs, did not change the P1-E canonical benchmark, did not change hard synchronization, did not tune a time offset from GT, did not treat pseudocolor as independent physics, did not infer a vehicle-response mask, did not generate candidates, did not run a Gate/selector/ranking/oracle, did not train a model, did not run an optical tracker, did not start high-energy sliding/scatterer tracking/structure dynamics, and did not produce automatic annotations.
""",
    )


COORDINATE_FIELDS = [
    "scene", "sar_asset_type", "image_width", "image_height", "grid_type",
    "x_axis_physical_meaning", "y_axis_physical_meaning", "x_axis_direction", "y_axis_direction",
    "radar_origin_pixel_x", "radar_origin_pixel_y", "x_min_meter", "x_max_meter", "y_min_meter", "y_max_meter",
    "x_meter_per_pixel_or_formula", "y_meter_per_pixel_or_formula", "radial_pixel_formula", "azimuth_formula",
    "historical_radial_grid_spacing_claim", "historical_claim_interpretation", "coordinate_source", "is_cartesian",
    "is_resampled", "resolution_interpretation", "confidence_status", "notes",
]

MASK_FIELDS = [
    "scene", "image_width", "image_height", "mask_name", "definition", "availability", "static_or_dynamic",
    "generation_rule", "pixel_count_or_range", "fraction_or_range", "content_hash_or_formula_hash", "physical_semantics",
    "may_be_used_as_vehicle_mask", "confidence_status", "notes",
]

LINEAGE_FIELDS = [
    "scene", "frame_index", "gray_filename", "pseudocolor_filename", "gray_content_hash", "pseudocolor_content_hash",
    "index_aligned", "dimensions_aligned", "gray_channel_semantics", "pseudocolor_semantics", "spatial_gradient_alignment",
    "gray_authoritative_fps", "pseudocolor_container_fps", "authoritative_time_sec", "pseudocolor_inherited_time_sec",
    "lineage_status", "retains_phase", "adds_independent_physical_observation", "notes",
]

THREAD_FIELDS = [
    "scene", "canonical_vehicle_id", "benchmark_role", "optical_frame_index", "optical_time_sec", "sar_frame_index",
    "sar_time_sec", "sar_gt_available", "sar_gt_id", "sar_gt_bbox", "optical_visibility_state", "optical_full_vehicle_visible",
    "optical_reference_bbox", "mapping_basis", "identity_link_evidence", "identity_link_status", "identity_link_confidence",
    "source_optical_bbox", "source_optical_bbox_best_canonical_iou", "multi_vehicle_competition", "thread_quality_status", "notes",
]

QUALITY_FIELDS = [
    "scene", "canonical_vehicle_id", "benchmark_role", "sar_frame_index", "sar_gt_id", "bbox", "bbox_width_px",
    "bbox_height_px", "bbox_width_meter", "bbox_height_meter", "center_x_px", "center_y_px", "center_x_meter",
    "center_y_meter", "center_radius_px", "center_theta_deg", "valid_mask_fraction", "validity_basis", "fan_geometry_fraction",
    "touches_invalid_region", "touches_fan_geometry_outside", "touches_image_boundary", "neighbor_vehicle_overlap_risk",
    "neighbor_rotated_overlap_ratio", "center_jump_from_previous", "center_jump_per_sar_frame", "size_jump_from_previous",
    "aspect_jump_from_previous", "gt_quality_status", "quality_evidence", "identity_link_status", "identity_link_confidence",
    "optical_frame_index", "optical_visibility_state", "optical_full_vehicle_visible", "multi_vehicle_competition", "notes",
]

GOLDEN_FIELDS = [
    "scene", "canonical_vehicle_id", "benchmark_role", "sar_frame_start", "sar_frame_end", "gt_frame_count", "gt_row_count",
    "gold_frame_count", "usable_frame_count", "optical_full_vehicle_visible_fraction", "viewpoint_or_pose_diversity",
    "sar_theta_span_deg", "distance_or_scale_diversity", "sar_radius_span_px", "multi_vehicle_competition_level", "gt_continuity",
    "max_sar_frame_gap", "mask_validity", "recommended_research_role", "exclusion_reason", "notes",
]

MAPPING_FIELDS = [
    "scene", "canonical_vehicle_id", "benchmark_role", "sar_gt_id", "optical_frame_index", "sar_frame_index",
    "optical_center_x_px", "sar_gt_center_x_px", "sar_gt_center_y_px", "sar_theta_deg", "sar_radius_px",
    "anchor_quality_status", "anchor_identity_confidence", "model_fit_membership", "old_mapping_pred_theta_deg",
    "old_mapping_error_deg", "refit_linear_pred_theta_deg", "refit_linear_error_deg", "vehicle_holdout_pred_theta_deg",
    "vehicle_holdout_error_deg", "vehicle_holdout_tangential_error_px", "vehicle_holdout_tangential_error_meter",
    "error_to_typical_vehicle_width_ratio", "mapping_coordinate_domain", "mapping_status", "notes",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-visuals", action="store_true", help="Do not regenerate temporary contact sheets/case atlases")
    parser.add_argument("--reuse-stream-cache", action="store_true", help="Reuse already audited stream lineage/mask summaries for a non-final iteration")
    args = parser.parse_args()

    print(f"[S0] repo={REPO_ROOT}", flush=True)
    print("[S0] interpreter contract=D:\\MINICONDA\\envs\\py311\\python.exe", flush=True)
    print(f"[S0] source GT={FINAL_GT}", flush=True)
    TEMP_OUTPUT.mkdir(parents=True, exist_ok=True)

    valid_fan = fan_mask()
    coordinate_rows = build_coordinate_contract()
    if args.reuse_stream_cache and (TEMP_OUTPUT / "s0_summary.json").exists():
        print("[stream] reusing existing full-stream audit cache for this iteration", flush=True)
        lineage_rows = read_csv(MANIFEST_DIR / "oty2_s0_sar_gray_pseudocolor_lineage.csv")
        mask_rows = read_csv(MANIFEST_DIR / "oty2_s0_sar_mask_contract.csv")
        stream_summary = json.loads((TEMP_OUTPUT / "s0_summary.json").read_text(encoding="utf-8"))["stream_summary"]
    else:
        lineage_rows, mask_rows, stream_summary = audit_streams(valid_fan)
    identity = load_identity_context()
    gt_rows = read_csv(FINAL_GT)
    queue_rows = read_csv(REVIEW_QUEUE)
    linked_rows = link_gt_to_canonical(gt_rows, queue_rows, identity)
    quality_rows = build_quality_audit(linked_rows, valid_fan)
    golden_rows = build_golden_threads(quality_rows, identity)
    mapping_rows, mapping_summary = build_mapping_audit(quality_rows)

    write_csv(MANIFEST_DIR / "oty2_s0_sar_coordinate_contract.csv", coordinate_rows, COORDINATE_FIELDS)
    write_csv(MANIFEST_DIR / "oty2_s0_sar_mask_contract.csv", mask_rows, MASK_FIELDS)
    write_csv(MANIFEST_DIR / "oty2_s0_sar_gray_pseudocolor_lineage.csv", lineage_rows, LINEAGE_FIELDS)
    write_csv(MANIFEST_DIR / "oty2_s0_canonical_vehicle_sar_gt_threads.csv", linked_rows, THREAD_FIELDS)
    write_csv(MANIFEST_DIR / "oty2_s0_sar_gt_quality_audit.csv", quality_rows, QUALITY_FIELDS)
    write_csv(MANIFEST_DIR / "oty2_s0_sar_golden_vehicle_threads.csv", golden_rows, GOLDEN_FIELDS)
    write_csv(MANIFEST_DIR / "oty2_s0_optical_to_sar_azimuth_mapping_audit.csv", mapping_rows, MAPPING_FIELDS)

    write_protocol()
    write_coordinate_doc(stream_summary)
    write_mapping_doc(mapping_summary)

    if args.skip_visuals:
        visual_manifest_path = TEMP_OUTPUT / "visual_review_manifest.json"
        visual_manifest = json.loads(visual_manifest_path.read_text(encoding="utf-8")) if visual_manifest_path.exists() else {
            "all_gt_case_count": 442,
            "anomaly_case_count": 0,
            "mapping_anchor_case_count": len(mapping_rows),
            "representative_case_count": 0,
        }
    else:
        visual_manifest = build_visual_review_assets(quality_rows, mapping_rows)

    assets = asset_summary()
    write_main_report(assets, stream_summary, linked_rows, quality_rows, golden_rows, mapping_summary, visual_manifest)

    summary = {
        "execution_date": EXECUTION_DATE,
        "base_commit": BASE_COMMIT,
        "stage_status": "S0_SAR_FOUNDATION_PARTIALLY_READY",
        "s1_entry_allowed": False,
        "coordinate_status": "PARTIAL_DISPLAY_COORDINATE_CONFIRMED_METRIC_GRID_BLOCKED",
        "mapping": mapping_summary,
        "stream_summary": stream_summary,
        "thread_rows": len(linked_rows),
        "canonical_linked_rows": sum(bool(row["canonical_vehicle_id"]) for row in linked_rows),
        "canonical_unresolved_rows": sum(not bool(row["canonical_vehicle_id"]) for row in linked_rows),
        "canonical_vehicles_with_gt": len({(row["scene"], row["canonical_vehicle_id"]) for row in linked_rows if row["canonical_vehicle_id"]}),
        "quality_counts": count_by(quality_rows, "gt_quality_status"),
        "golden_role_counts": count_by(golden_rows, "recommended_research_role"),
        "visual_review": visual_manifest,
        "input_provenance": [
            str(MANIFEST_DIR / "oty2_p0_data_asset_manifest.csv"),
            str(MANIFEST_DIR / "oty2_p0_hard_sync_sar_to_optical.csv"),
            str(MANIFEST_DIR / "oty2_p0_hard_sync_optical_to_sar.csv"),
            str(MANIFEST_DIR / "oty2_p1e_canonical_optical_vehicle_registry.csv"),
            str(MANIFEST_DIR / "oty2_p1e_canonical_vehicle_frame_states.csv"),
            str(MANIFEST_DIR / "oty2_p1e_identity_benchmark_roles.csv"),
            str(MANIFEST_DIR / "oty2_p1e_detection_to_canonical_identity_map.csv"),
            str(REVIEW_QUEUE),
            str(FINAL_GT),
            str(DATA_ROOT),
        ],
    }
    write_json(TEMP_OUTPUT / "s0_summary.json", summary)
    write_json(TEMP_OUTPUT / "formal_output_hashes.json", formal_hashes())
    print(json.dumps({key: summary[key] for key in ("stage_status", "thread_rows", "canonical_linked_rows", "canonical_unresolved_rows", "quality_counts", "golden_role_counts")}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
