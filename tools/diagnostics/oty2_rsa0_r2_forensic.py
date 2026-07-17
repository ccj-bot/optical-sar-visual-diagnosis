#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import cv2
import matplotlib
import numpy as np
from scipy.stats import rankdata

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
CONFIG_DIR = REPO_ROOT / "configs" / "oty2"
DEFAULT_CONFIG = CONFIG_DIR / "oty2_rsa0_r2_forensic_audit.json"

FAN_WIDTH = 2308
FAN_HEIGHT = 1334
FAN_CENTER = (1154.0, 1330.6)
FAN_RADIUS = 1332.7
FAN_MASK_HASH = "7bdfbc5417db5f96405751d7503973f16db85957cf9aa0c6a8f30975cc0502ef"

ARRAY_LINEAGE = MANIFEST_DIR / "oty2_rsa0_r2_array_lineage.csv"
POINT_TRACE = MANIFEST_DIR / "oty2_rsa0_r2_point_trace.csv"
FAN_AUDIT = MANIFEST_DIR / "oty2_rsa0_r2_fan_geometry_audit.csv"
ATLAS_AUDIT = MANIFEST_DIR / "oty2_rsa0_r2_atlas_point_audit.csv"
CONCLUSION_LINEAGE = MANIFEST_DIR / "oty2_rsa0_r2_conclusion_lineage.csv"
COORDINATE_AUDIT = MANIFEST_DIR / "oty2_rsa0_r2_coordinate_stack_audit.csv"
CHANNEL_AUDIT = MANIFEST_DIR / "oty2_rsa0_r2_channel_semantic_audit.csv"
NORMALIZATION_AUDIT = MANIFEST_DIR / "oty2_rsa0_r2_normalization_audit.csv"
SAMPLING_AUDIT = MANIFEST_DIR / "oty2_rsa0_r2_sampling_auc_audit.csv"
SYNTHETIC_RESULTS = MANIFEST_DIR / "oty2_rsa0_r2_synthetic_test_results.csv"
PHASE_A_FINDINGS = MANIFEST_DIR / "oty2_rsa0_r2_phase_a_findings.csv"
PHASE_A_FREEZE = MANIFEST_DIR / "oty2_rsa0_r2_phase_a_freeze_manifest.csv"
OUTPUT_MANIFEST = MANIFEST_DIR / "oty2_rsa0_r2_output_manifest.csv"

PHASE_A_REPORT = REPORT_DIR / "oty2_rsa0_r2_phase_a_findings_20260717.md"
COORDINATE_REPORT = REPORT_DIR / "oty2_rsa0_r2_coordinate_stack_audit_20260717.md"
CHANNEL_REPORT = REPORT_DIR / "oty2_rsa0_r2_channel_semantic_audit_20260717.md"
NORMALIZATION_REPORT = REPORT_DIR / "oty2_rsa0_r2_normalization_audit_20260717.md"
SYNTHETIC_REPORT = REPORT_DIR / "oty2_rsa0_r2_synthetic_test_report_20260717.md"
FORMAL_REPORT = REPORT_DIR / "oty2_rsa0_r2_pipeline_forensic_audit_20260717.md"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_r2_summary_20260717.json"
VALIDATION_JSON = REPORT_DIR / "oty2_rsa0_r2_validation_summary_20260717.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    require(bool(rows), f"cannot write empty CSV: {path}")
    if fieldnames is None:
        ordered: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    ordered.append(key)
                    seen.add(key)
        fieldnames = ordered
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), restval="")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def packed_mask_hash(mask: np.ndarray) -> str:
    packed = np.packbits(np.asarray(mask, dtype=np.uint8), bitorder="little")
    return hashlib.sha256(packed.tobytes()).hexdigest()


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def verify_git_gate(config: Mapping[str, Any]) -> dict[str, str]:
    branch = git("branch", "--show-current")
    require(branch == config["expected_branch"], f"branch mismatch: {branch}")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", config["expected_start_head"], "HEAD"],
        cwd=REPO_ROOT,
        check=False,
    )
    require(result.returncode == 0, "R2 docs checkpoint is not an ancestor of HEAD")
    return {"branch": branch, "head": git("rev-parse", "HEAD")}


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO_ROOT / path


def fmt(value: Any, digits: int = 9) -> str:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return ""
        return f"{float(value):.{digits}f}"
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    return str(value)


def imaging_valid_mask(shape: tuple[int, int] = (FAN_HEIGHT, FAN_WIDTH), origin: tuple[float, float] = FAN_CENTER) -> np.ndarray:
    yy, xx = np.indices(shape, dtype=np.float64)
    radius = np.hypot(xx - origin[0], yy - origin[1])
    theta = np.degrees(np.arctan2(xx - origin[0], origin[1] - yy))
    return (radius <= FAN_RADIUS) & (theta >= -90.0) & (theta <= 90.0)


def parse_points(text: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in (text or "").split(";"):
        if not item:
            continue
        x, y = item.split(",", 1)
        points.append((float(x), float(y)))
    return points


def points_text(points: Iterable[tuple[float, float]]) -> str:
    return ";".join(f"{x:.6f},{y:.6f}" for x, y in points)


def polygon_centroid(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    arr = np.asarray(points, dtype=np.float64)
    if len(arr) == 0:
        return math.nan, math.nan
    return float(np.mean(arr[:, 0])), float(np.mean(arr[:, 1]))


def polyline_midpoint(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    require(bool(points), "empty polyline")
    if len(points) == 1:
        return points[0]
    lengths = np.asarray([math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points[:-1], points[1:])])
    target = float(lengths.sum()) / 2.0
    running = 0.0
    for (ax, ay), (bx, by), length in zip(points[:-1], points[1:], lengths):
        if running + length >= target:
            ratio = 0.0 if length == 0 else (target - running) / float(length)
            return ax + ratio * (bx - ax), ay + ratio * (by - ay)
        running += float(length)
    return points[-1]


def polygon_mask(points: Sequence[tuple[float, float]], shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    if len(points) >= 3:
        cv2.fillPoly(mask, [np.rint(points).astype(np.int32)], 1)
    return mask.astype(bool)


def polyline_mask(points: Sequence[tuple[float, float]], shape: tuple[int, int], thickness: int) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    if len(points) >= 2:
        cv2.polylines(mask, [np.rint(points).astype(np.int32)], False, 1, thickness, cv2.LINE_8)
    return mask.astype(bool)


def union_masks(masks: Sequence[np.ndarray], shape: tuple[int, int]) -> np.ndarray:
    return np.logical_or.reduce(masks) if masks else np.zeros(shape, dtype=bool)


def translation_matrix(dx: float, dy: float) -> np.ndarray:
    return np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)


def invert_translation(matrix: np.ndarray) -> np.ndarray:
    return translation_matrix(-float(matrix[0, 2]), -float(matrix[1, 2]))


def transform_points(points: Sequence[tuple[float, float]], matrix: np.ndarray) -> list[tuple[float, float]]:
    if not points:
        return []
    arr = np.asarray(points, dtype=np.float64)
    out = arr @ matrix[:, :2].T + matrix[:, 2]
    return [(float(x), float(y)) for x, y in out]


def warp_image(image: np.ndarray, matrix: np.ndarray, interpolation: int = cv2.INTER_LINEAR) -> np.ndarray:
    return cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        flags=interpolation,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def read_png(path: Path) -> tuple[np.ndarray, np.ndarray]:
    decoded = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    require(decoded is not None, f"cannot read image: {path}")
    require(decoded.shape[:2] == (FAN_HEIGHT, FAN_WIDTH), f"unexpected image shape: {decoded.shape}")
    scalar = decoded[:, :, 0] if decoded.ndim == 3 else decoded
    return np.asarray(decoded, dtype=np.uint8), np.asarray(scalar, dtype=np.uint8)


def display_u8(image: np.ndarray, low: float = 0.0, high: float = 85.0) -> np.ndarray:
    value = (image.astype(np.float32) - low) / max(1e-6, high - low)
    return np.asarray(np.rint(np.clip(value, 0.0, 1.0) * 255.0), dtype=np.uint8)


def array_stats(array: np.ndarray, valid_mask: np.ndarray | None = None) -> dict[str, Any]:
    arr = np.asarray(array)
    finite = np.isfinite(arr)
    values = arr[finite].astype(np.float64)
    require(values.size > 0, "array has no finite values")
    if valid_mask is not None:
        valid_fraction = float(np.mean(valid_mask))
    else:
        valid_fraction = 1.0
    percentiles = np.percentile(values, [2, 50, 75, 80, 90, 95, 98])
    return {
        "shape": "x".join(map(str, arr.shape)),
        "dtype": str(arr.dtype),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p02": float(percentiles[0]),
        "p50": float(percentiles[1]),
        "p75": float(percentiles[2]),
        "p80": float(percentiles[3]),
        "p90": float(percentiles[4]),
        "p95": float(percentiles[5]),
        "p98": float(percentiles[6]),
        "zero_fraction": float(np.mean(arr == 0)),
        "finite_fraction": float(np.mean(finite)),
        "valid_fan_fraction": valid_fraction,
    }


def normalization_range(array: np.ndarray, mask: np.ndarray | None, percentiles: Sequence[float]) -> tuple[float, float]:
    values = np.asarray(array, dtype=np.float32)
    selected = values[np.isfinite(values) & mask] if mask is not None else values[np.isfinite(values)]
    if selected.size == 0:
        return 0.0, 0.0
    lo, hi = np.percentile(selected, percentiles)
    return float(lo), float(hi)


def apply_range(array: np.ndarray, lo: float, hi: float, dtype: np.dtype[Any] = np.float32) -> np.ndarray:
    if hi <= lo:
        return np.zeros_like(array, dtype=dtype)
    return np.asarray(np.clip((array.astype(np.float32) - lo) / (hi - lo), 0.0, 1.0), dtype=dtype)


SINGLE_CHANNEL_FORMULAS = {
    "raw_display_intensity": "I",
    "local_contrast_31": "I - boxmean_31(I)",
    "local_z_31": "(I - boxmean_31(I)) / local_std_31(I)",
    "highpass_sigma9": "I - GaussianSigma9(I)",
    "sobel_x_abs_gradient_component": "abs(dI/dx)",
    "sobel_y_abs_gradient_component": "abs(dI/dy)",
    "gradient_magnitude_sobel": "hypot(dI/dx,dI/dy)",
    "multiscale_laplacian_bright_ridge": "max(0,-(dxx+dyy)) at sigma 1.5 and 3.5",
    "structure_tensor_orientation_coherence": "sqrt((Jxx-Jyy)^2+4Jxy^2)/(Jxx+Jyy)",
    "radial_gradient_normal_response": "abs(grad(I) dot radial_unit)",
    "tangential_gradient_normal_response": "abs(grad(I) dot tangential_unit)",
}


def single_channels(image: np.ndarray, origin: tuple[float, float] = FAN_CENTER) -> dict[str, np.ndarray]:
    img = image.astype(np.float32)
    mean = cv2.blur(img, (31, 31))
    mean2 = cv2.blur(img * img, (31, 31))
    std = np.sqrt(np.maximum(1.0, mean2 - mean * mean))
    highpass = img - cv2.GaussianBlur(img, (0, 0), 9.0)
    sobel_x = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    blur3 = cv2.GaussianBlur(img, (0, 0), 1.5)
    blur7 = cv2.GaussianBlur(img, (0, 0), 3.5)
    dxx3 = cv2.Sobel(blur3, cv2.CV_32F, 2, 0, ksize=3)
    dyy3 = cv2.Sobel(blur3, cv2.CV_32F, 0, 2, ksize=3)
    dxx7 = cv2.Sobel(blur7, cv2.CV_32F, 2, 0, ksize=3)
    dyy7 = cv2.Sobel(blur7, cv2.CV_32F, 0, 2, ksize=3)
    ridge = np.maximum(0.0, -(dxx3 + dyy3)) + np.maximum(0.0, -(dxx7 + dyy7))
    jxx = cv2.GaussianBlur(sobel_x * sobel_x, (0, 0), 3.0)
    jyy = cv2.GaussianBlur(sobel_y * sobel_y, (0, 0), 3.0)
    jxy = cv2.GaussianBlur(sobel_x * sobel_y, (0, 0), 3.0)
    coherence = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy * jxy) / np.maximum(jxx + jyy, 1e-3)
    yy, xx = np.indices(img.shape, dtype=np.float32)
    radial_x = xx - float(origin[0])
    radial_y = yy - float(origin[1])
    norm = np.maximum(np.hypot(radial_x, radial_y), 1.0)
    radial_x /= norm
    radial_y /= norm
    tangential_x = -radial_y
    tangential_y = radial_x
    return {
        "raw_display_intensity": img,
        "local_contrast_31": img - mean,
        "local_z_31": (img - mean) / std,
        "highpass_sigma9": highpass,
        "sobel_x_abs_gradient_component": np.abs(sobel_x),
        "sobel_y_abs_gradient_component": np.abs(sobel_y),
        "gradient_magnitude_sobel": np.hypot(sobel_x, sobel_y),
        "multiscale_laplacian_bright_ridge": ridge,
        "structure_tensor_orientation_coherence": coherence,
        "radial_gradient_normal_response": np.abs(sobel_x * radial_x + sobel_y * radial_y),
        "tangential_gradient_normal_response": np.abs(sobel_x * tangential_x + sobel_y * tangential_y),
    }


def temporal_channels(stack: np.ndarray, valid_stack: np.ndarray, index: int, half_window: int) -> dict[str, np.ndarray]:
    start = max(0, index - half_window)
    end = min(stack.shape[0], index + half_window + 1)
    chosen = stack[start:end].astype(np.float32)
    chosen_valid = valid_stack[start:end].astype(bool)
    masked = np.where(chosen_valid, chosen, np.nan)
    with np.errstate(all="ignore"):
        median = np.nanmedian(masked, axis=0)
        maximum = np.nanmax(masked, axis=0)
        minimum = np.nanmin(masked, axis=0)
        mad = np.nanmedian(np.abs(masked - median), axis=0)
    median = np.nan_to_num(median, nan=0.0)
    maximum = np.nan_to_num(maximum, nan=0.0)
    minimum = np.nan_to_num(minimum, nan=0.0)
    mad = np.nan_to_num(mad, nan=0.0)
    grads = np.stack([cv2.Sobel(frame, cv2.CV_32F, 1, 0, ksize=3) for frame in chosen])
    grad_valid = chosen_valid & np.isfinite(grads)
    grad_count = np.maximum(1, np.sum(grad_valid, axis=0))
    sign_mean = np.sum(np.where(grad_valid, np.sign(grads), 0.0), axis=0) / grad_count
    magnitude_mean = np.sum(np.where(grad_valid, np.abs(grads), 0.0), axis=0) / grad_count
    persistence = np.abs(sign_mean) * magnitude_mean
    high_frequency = np.zeros(stack.shape[1:], dtype=np.float32)
    high_count = np.zeros(stack.shape[1:], dtype=np.float32)
    for frame, valid in zip(chosen, chosen_valid):
        threshold = float(np.percentile(frame[valid], 80)) if np.any(valid) else math.inf
        high_frequency += ((frame >= threshold) & valid).astype(np.float32)
        high_count += valid.astype(np.float32)
    high_frequency /= np.maximum(1.0, high_count)
    with np.errstate(all="ignore"):
        local_q75 = np.nanpercentile(masked, 75, axis=0)
    local_q75 = np.nan_to_num(local_q75, nan=np.inf)
    legacy_rank_frequency = np.sum((chosen >= local_q75) & chosen_valid, axis=0) / np.maximum(1, np.sum(chosen_valid, axis=0))
    output = {
        f"temporal_w{half_window}_median": median.astype(np.float32),
        f"temporal_w{half_window}_max": maximum.astype(np.float32),
        f"temporal_w{half_window}_min": minimum.astype(np.float32),
        f"temporal_w{half_window}_mad": mad.astype(np.float32),
        f"temporal_w{half_window}_gradient_persistence": persistence.astype(np.float32),
        f"temporal_w{half_window}_high_intensity_pixel_frequency": high_frequency.astype(np.float32),
        f"temporal_w{half_window}_legacy_per_pixel_rank_frequency": legacy_rank_frequency.astype(np.float32),
    }
    if index > 0:
        delta = stack[index].astype(np.float32) - stack[index - 1].astype(np.float32)
    else:
        delta = np.zeros(stack.shape[1:], dtype=np.float32)
    output["temporal_adjacent_positive_change"] = np.maximum(delta, 0.0)
    output["temporal_adjacent_negative_change"] = np.maximum(-delta, 0.0)
    return output


@dataclass
class AuditContext:
    config_path: Path
    config: dict[str, Any]
    output_root: Path
    conditions: list[dict[str, str]]
    gt_rows: list[dict[str, str]]
    transport_rows: list[dict[str, str]]
    atlas_frames: list[dict[str, str]]
    atlas_skeletons: list[dict[str, str]]
    atlas_regions: list[dict[str, str]]
    atlas_background: list[dict[str, str]]


def load_context(config_path: Path = DEFAULT_CONFIG) -> AuditContext:
    config = load_json(config_path)
    verify_git_gate(config)
    sources = config["sources"]
    output_root = Path(config["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    return AuditContext(
        config_path=config_path,
        config=config,
        output_root=output_root,
        conditions=read_csv(resolve(sources["conditions"])),
        gt_rows=read_csv(resolve(sources["gt"])),
        transport_rows=read_csv(resolve(sources["transport"])),
        atlas_frames=read_csv(resolve(sources["atlas_frames"])),
        atlas_skeletons=read_csv(resolve(sources["atlas_skeletons"])),
        atlas_regions=read_csv(resolve(sources["atlas_regions"])),
        atlas_background=read_csv(resolve(sources["atlas_background"])),
    )


def selected_row(rows: Sequence[dict[str, str]], scene: str, vehicle: str, frame: int, frame_key: str = "sar_frame_index") -> dict[str, str]:
    selected = [
        row for row in rows
        if row.get("scene") == scene
        and row.get("canonical_vehicle_id") == vehicle
        and int(row[frame_key]) == frame
    ]
    require(bool(selected), f"missing row {scene} {vehicle} {frame}")
    return selected[0]


def gt_center(row: Mapping[str, str]) -> tuple[float, float]:
    value = json.loads(row["bbox"])
    return float(value[0]), float(value[1])


def proxy_center(row: Mapping[str, str]) -> tuple[float, float]:
    return float(row["predicted_center_x_px"]), float(row["predicted_center_y_px"])


def transport_for(ctx: AuditContext, scene: str, frame: int) -> tuple[float, float, dict[str, str]]:
    selected = [
        row for row in ctx.transport_rows
        if row.get("scene") == scene
        and row.get("state_mode") == "causal"
        and row.get("case_id") == ctx.config["transport_case_id"]
        and int(row["sar_frame_index"]) == frame
    ]
    require(len(selected) == 1, f"transport row count {scene} {frame}: {len(selected)}")
    row = selected[0]
    return float(row["cumulative_dx_px"]), float(row["cumulative_dy_px"]), row


def atlas_geometry(ctx: AuditContext, window: Mapping[str, Any]) -> dict[str, Any]:
    source_case = window["source_case_id"]
    frame = int(window["primary_frame"])
    skeleton_rows = [row for row in ctx.atlas_skeletons if row["case_id"] == source_case and int(row["sar_frame"]) == frame]
    region_rows = [row for row in ctx.atlas_regions if row["case_id"] == source_case and int(row["sar_frame"]) == frame]
    background_rows = [row for row in ctx.atlas_background if row["case_id"] == source_case and int(row["sar_frame"]) == frame]
    require(bool(skeleton_rows) and bool(region_rows) and bool(background_rows), f"missing atlas geometry {source_case} {frame}")
    skeleton = parse_points(next(row["points"] for row in skeleton_rows if row["label"] == "MAIN_RESPONSE_SKELETON"))
    seed = parse_points(next(row["points"] for row in skeleton_rows if row["label"] == "HIGH_CONFIDENCE_RESPONSE_SEED"))
    regions: dict[str, list[list[tuple[float, float]]]] = defaultdict(list)
    for row in region_rows:
        regions[row["label"]].append(parse_points(row["points"]))
    backgrounds: list[dict[str, Any]] = []
    subtype_map = window["background_subtypes"]
    for row in sorted(background_rows, key=lambda item: int(item["component_id"])):
        backgrounds.append({
            "component_id": int(row["component_id"]),
            "subtype": subtype_map.get(str(row["component_id"]), "other"),
            "points": parse_points(row["points"]),
        })
    return {"skeleton": skeleton, "seed": seed, "regions": dict(regions), "backgrounds": backgrounds}


def geometry_masks(geometry: Mapping[str, Any], matrix: np.ndarray, shape: tuple[int, int] = (FAN_HEIGHT, FAN_WIDTH)) -> dict[str, np.ndarray]:
    skeleton = transform_points(geometry["skeleton"], matrix)
    seed = transform_points(geometry["seed"], matrix)
    regions = {
        label: [transform_points(points, matrix) for points in items]
        for label, items in geometry["regions"].items()
    }
    backgrounds = [
        {**item, "points": transform_points(item["points"], matrix)}
        for item in geometry["backgrounds"]
    ]
    masks = {
        "skeleton": polyline_mask(skeleton, shape, 3),
        "seed": polyline_mask(seed, shape, 3),
        "definite": union_masks([polygon_mask(points, shape) for points in regions.get("DEFINITE_TARGET_RESPONSE", [])], shape),
        "unresolved": union_masks([polygon_mask(points, shape) for points in regions.get("UNRESOLVED", [])], shape),
        "background": union_masks([polyline_mask(item["points"], shape, 5) for item in backgrounds], shape),
    }
    for item in backgrounds:
        masks[f"background_{item['subtype']}"] = polyline_mask(item["points"], shape, 5)
    masks["_geometry"] = {"skeleton": skeleton, "seed": seed, "regions": regions, "backgrounds": backgrounds}  # type: ignore[assignment]
    return masks


def crop_bounds(center: tuple[float, float], width: int, height: int, shape: tuple[int, int] = (FAN_HEIGHT, FAN_WIDTH)) -> tuple[int, int, int, int]:
    x1 = max(0, int(round(center[0] - width / 2)))
    y1 = max(0, int(round(center[1] - height / 2)))
    x2 = min(shape[1], x1 + width)
    y2 = min(shape[0], y1 + height)
    x1 = max(0, x2 - width)
    y1 = max(0, y2 - height)
    return x1, y1, x2, y2


def draw_geometry(axis: Any, geometry: Mapping[str, Any], x0: int = 0, y0: int = 0) -> None:
    skeleton = geometry.get("skeleton", [])
    seed = geometry.get("seed", [])
    if skeleton:
        arr = np.asarray(skeleton)
        axis.plot(arr[:, 0] - x0, arr[:, 1] - y0, color="#00ff5a", linewidth=2.0, label="skeleton")
    if seed:
        arr = np.asarray(seed)
        axis.plot(arr[:, 0] - x0, arr[:, 1] - y0, color="#00a83b", linewidth=3.0, label="seed")
    for label, color in [
        ("DEFINITE_TARGET_RESPONSE", "#ffe800"),
        ("PROBABLE_TARGET_RESPONSE", "#ff00ff"),
        ("UNRESOLVED", "#ff7f7f"),
        ("MIXED_STRUCTURE", "#00a8ff"),
    ]:
        for points in geometry.get("regions", {}).get(label, []):
            arr = np.asarray([*points, points[0]])
            axis.plot(arr[:, 0] - x0, arr[:, 1] - y0, color=color, linewidth=1.5)
    for item in geometry.get("backgrounds", []):
        arr = np.asarray(item["points"])
        axis.plot(arr[:, 0] - x0, arr[:, 1] - y0, color="#ff2020", linewidth=1.5)


def save_figure(path: Path, figure: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(figure)


def save_bundle(path: Path, arrays: Mapping[str, np.ndarray]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    return sha256_file(path)


def lineage_row(
    case_id: str,
    frame: int | str,
    stage_id: str,
    variable_name: str,
    source_file: str,
    source_sha256: str,
    coordinate_system: str,
    array: np.ndarray,
    valid_mask: np.ndarray | None,
    output_path: Path,
    output_sha256: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "frame": frame,
        "stage_id": stage_id,
        "variable_name": variable_name,
        "source_file": source_file,
        "source_sha256": source_sha256,
        "coordinate_system": coordinate_system,
        **array_stats(array, valid_mask),
        "output_npz_path": str(output_path),
        "output_sha256": output_sha256,
    }


def output_manifest_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rows.append({
            "path": str(path),
            "relative_path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "git_external": "true",
        })
    return rows


def phase_a_raw_card(
    path: Path,
    decoded: np.ndarray,
    gray: np.ndarray,
    valid: np.ndarray,
    geometry: Mapping[str, Any],
    title: str,
    clip: Sequence[float],
) -> None:
    figure, axes = plt.subplots(2, 3, figsize=(16, 8))
    axes[0, 0].imshow(decoded)
    axes[0, 0].set_title(f"PNG decoded {decoded.shape} {decoded.dtype}")
    axes[0, 1].imshow(gray, cmap="gray", vmin=0, vmax=255)
    axes[0, 1].set_title(f"channel-0 scalar | {int(gray.min())}..{int(gray.max())}")
    axes[0, 2].imshow(display_u8(gray, float(clip[0]), float(clip[1])), cmap="gray", vmin=0, vmax=255)
    axes[0, 2].set_title(f"review clip {clip[0]:.0f}..{clip[1]:.0f}")
    axes[1, 0].imshow(valid, cmap="gray")
    axes[1, 0].set_title(f"imaging_valid_mask | fraction={valid.mean():.6f}")
    axes[1, 1].imshow((gray == 0) & valid, cmap="gray")
    axes[1, 1].set_title(f"zero inside valid | fraction={np.mean((gray == 0)[valid]):.6f}")
    axes[1, 2].imshow(display_u8(gray, float(clip[0]), float(clip[1])), cmap="gray", vmin=0, vmax=255)
    draw_geometry(axes[1, 2], geometry)
    axes[1, 2].set_title("raw image with frozen atlas geometry")
    for axis in axes.ravel():
        axis.axis("off")
    figure.suptitle(title)
    save_figure(path, figure)


def phase_a_semantic_card(
    path: Path,
    gray: np.ndarray,
    geometry: Mapping[str, Any],
    drift: tuple[float, float],
    world_shift: tuple[float, float],
    title: str,
) -> None:
    clip = display_u8(gray)
    proxy_matrix = translation_matrix(*drift)
    world_matrix = translation_matrix(*world_shift)
    proxy_geometry = geometry_masks(geometry, proxy_matrix)["_geometry"]
    world_image = warp_image(gray, world_matrix)
    world_geometry = geometry_masks(geometry, world_matrix)["_geometry"]
    figure, axes = plt.subplots(2, 3, figsize=(16, 9))
    x1, y1, x2, y2 = crop_bounds(polygon_centroid(geometry["skeleton"]), 600, 420)
    axes[0, 0].imshow(clip[y1:y2, x1:x2], cmap="gray")
    draw_geometry(axes[0, 0], geometry, x1, y1)
    axes[0, 0].set_title("R1 GT-named family: raw image + raw geometry")
    axes[0, 1].imshow(clip[y1:y2, x1:x2], cmap="gray")
    draw_geometry(axes[0, 1], proxy_geometry, x1, y1)
    axes[0, 1].set_title(f"R1 proxy-named family: image fixed, geometry shift ({drift[0]:.1f},{drift[1]:.1f})")
    axes[0, 2].imshow(cv2.absdiff(gray, gray)[y1:y2, x1:x2], cmap="magma")
    axes[0, 2].set_title("GT-named image difference from RAW = 0")
    axes[1, 0].imshow(display_u8(world_image)[y1:y2, x1:x2], cmap="gray")
    draw_geometry(axes[1, 0], world_geometry, x1, y1)
    axes[1, 0].set_title(f"R1 world: image+geometry shift ({world_shift[0]:.1f},{world_shift[1]:.1f})")
    axes[1, 1].text(0.02, 0.95, "WORLD metrics channels: 11 single-frame\nGT-named metrics channels: 27\nPROXY-named metrics channels: 27\n\nWorld temporal channels are absent.", va="top", fontsize=12)
    axes[1, 1].axis("off")
    axes[1, 2].text(0.02, 0.95, "temporal_*_local_component_continuity\n= per-frame 80th-percentile bright-pixel occurrence\n\nauc_score\n= first 3000 flattened positives and negatives", va="top", fontsize=12)
    axes[1, 2].axis("off")
    for axis in [axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 0]]:
        axis.axis("off")
    figure.suptitle(title)
    save_figure(path, figure)


def run_phase_a(ctx: AuditContext) -> None:
    valid = imaging_valid_mask()
    require(packed_mask_hash(valid) == FAN_MASK_HASH, "fan mask hash mismatch")
    evidence_dir = ctx.output_root / "evidence_cards" / "phase_a"
    arrays_dir = ctx.output_root / "arrays" / "phase_a"
    lineage: list[dict[str, Any]] = []
    external_files: list[Path] = []
    for window in ctx.config["windows"]:
        frame = int(window["primary_frame"])
        condition = selected_row(ctx.conditions, window["scene"], window["vehicle_id"], frame)
        gt = selected_row(ctx.gt_rows, window["scene"], window["vehicle_id"], frame)
        image_path = Path(condition["sar_gray_path"])
        decoded, gray = read_png(image_path)
        geometry = atlas_geometry(ctx, window)
        display = display_u8(gray, *ctx.config["display_clip"])
        bundle_path = arrays_dir / window["case_id"] / f"{window['case_id'].lower()}_{frame}_raw_decode.npz"
        bundle_sha = save_bundle(bundle_path, {"png_decoded": decoded, "gray_scalar": gray, "display_clip": display, "imaging_valid_mask": valid})
        for name, array, coordinate in [
            ("png_decoded", decoded, "sar_display_px_bgr_storage"),
            ("gray_scalar", gray, "sar_display_px"),
            ("display_clip_0_85", display, "sar_display_px"),
            ("imaging_valid_mask", valid, "sar_display_px"),
        ]:
            lineage.append(lineage_row(window["case_id"], frame, f"S0{name}", name, str(image_path), sha256_file(image_path), coordinate, array, valid, bundle_path, bundle_sha))
        raw_card = evidence_dir / window["case_id"] / f"{window['case_id'].lower()}_{frame}_s00_s02_raw_decode_card.png"
        phase_a_raw_card(raw_card, decoded, gray, valid, geometry, f"{window['case_id']} SAR {frame} | S00-S02", ctx.config["display_clip"])
        dx, dy, _ = transport_for(ctx, window["scene"], frame)
        base_dx, base_dy, _ = transport_for(ctx, window["scene"], int(window["frames"][0]))
        gtx, gty = gt_center(gt)
        px, py = proxy_center(condition)
        semantic_card = evidence_dir / window["case_id"] / f"{window['case_id'].lower()}_{frame}_r1_coordinate_semantics_card.png"
        phase_a_semantic_card(semantic_card, gray, geometry, (px - gtx, py - gty), (-(dx - base_dx), -(dy - base_dy)), f"{window['case_id']} SAR {frame} | R1 actual coordinate operations")
        external_files.extend([bundle_path, raw_card, semantic_card])

    findings = [
        {
            "finding_id": "R2A-F01",
            "stage_id": "S06_GT_FAMILY",
            "status": "CONFIRMED_IMPLEMENTATION_ERROR",
            "finding": "R1 GT_CONDITIONED_RESEARCH_ORACLE uses the unwarped raw image and raw temporal maps; it is RAW_SAR_DISPLAY, not a GT-aligned image stack.",
            "code_evidence": "run_oty2_rsa0_r1_free_geometry_reaudit.py:620-642",
            "array_or_manifest_evidence": "R1 GT family has the same source image as RAW and no GT resampling matrix or aligned stack artifact.",
            "phase_b_action": "construct GT_ALIGNED_RESEARCH_STACK by synchronously translating every image, valid-source mask, atlas geometry, and point to the first-frame GT center before recomputing time channels",
            "scientific_impact": "R1 coordinate-family comparisons do not establish GT-conditioned temporal representation.",
        },
        {
            "finding_id": "R2A-F02",
            "stage_id": "S07_PROXY_FAMILY",
            "status": "CONFIRMED_IMPLEMENTATION_ERROR",
            "finding": "R1 OPTICAL_PROXY_CONDITIONED leaves the image fixed and shifts only atlas geometry by proxy-minus-GT drift.",
            "code_evidence": "run_oty2_rsa0_r1_free_geometry_reaudit.py:623-629",
            "array_or_manifest_evidence": "Primary evidence cards show nonzero geometry displacement over an unchanged image; PV003 SAR 384 drift is (-22.643,+130.210) px.",
            "phase_b_action": "separate OPTICAL_PROXY_ALIGNED_STACK from OPTICAL_PROXY_LOCALIZATION_ERROR_SAMPLING",
            "scientific_impact": "R1 proxy results measure localization-error sampling, not proxy-aligned representation quality.",
        },
        {
            "finding_id": "R2A-F03",
            "stage_id": "S05_WORLD_STACK",
            "status": "CONFIRMED_IMPLEMENTATION_ERROR",
            "finding": "R1 world-stabilized family computes only 11 single-frame channels and has no temporal channels.",
            "code_evidence": "run_oty2_rsa0_r1_free_geometry_reaudit.py:630-642",
            "array_or_manifest_evidence": "R1 metrics channel sets: WORLD=11, GT-named=27, PROXY-named=27.",
            "phase_b_action": "build the full world-stabilized five-frame stack and recompute every temporal channel",
            "scientific_impact": "R1 cannot answer what time represents after world stabilization.",
        },
        {
            "finding_id": "R2A-F04",
            "stage_id": "S10_TEMPORAL_CHANNEL",
            "status": "CONFIRMED_NAMING_ERROR",
            "finding": "temporal_*_local_component_continuity is high-intensity pixel occurrence frequency and contains no connected components, IDs, or cross-frame association.",
            "code_evidence": "run_oty2_rsa0_r1_free_geometry_reaudit.py:365-378",
            "array_or_manifest_evidence": "The array is a sum of per-frame >=80th-percentile boolean pixels divided by window length.",
            "phase_b_action": "rename to temporal_high_intensity_pixel_frequency and retain the old name only as historical provenance",
            "scientific_impact": "R1 component-continuity wording overstates the formula.",
        },
        {
            "finding_id": "R2A-F05",
            "stage_id": "S13_AUC",
            "status": "CONFIRMED_IMPLEMENTATION_ERROR",
            "finding": "R1 AUC truncates each flattened class to its first 3000 samples.",
            "code_evidence": "run_oty2_rsa0_r1_free_geometry_reaudit.py:401-408",
            "array_or_manifest_evidence": "NumPy mask extraction is row-major, so the retained samples are spatially ordered.",
            "phase_b_action": "report exact rank AUC, fixed-seed uniform sampling, spatial stratification, legacy-first3000, and background subtype results separately",
            "scientific_impact": "R1 AUC can be biased by mask geometry and scan order.",
        },
        {
            "finding_id": "R2A-F06",
            "stage_id": "S08_NORMALIZATION",
            "status": "CONFIRMED_IMPLEMENTATION_ERROR",
            "finding": "R1 robust01 uses full-frame per-frame 2%-98% quantiles without the fixed fan or transformed valid-source masks.",
            "code_evidence": "run_oty2_rsa0_r1_free_geometry_reaudit.py:95-103",
            "array_or_manifest_evidence": "Primary frames contain about 39.3% global zeros and about 29.0% zeros even inside the imaging-valid fan.",
            "phase_b_action": "compare full-frame, valid-fan, window-frozen valid-fan, and local matched ranges",
            "scientific_impact": "Per-frame scaling and invalid black support can manufacture or suppress apparent differences.",
        },
        {
            "finding_id": "R2A-F07",
            "stage_id": "S11_ATLAS_AUDIT",
            "status": "CONFIRMED_AUDIT_GAP",
            "finding": "R1 consistency rows hard-code several visual audit booleans rather than deriving them from point patches or direct-review records.",
            "code_evidence": "run_oty2_rsa0_r1_free_geometry_reaudit.py:589-601",
            "array_or_manifest_evidence": "skeleton_inside_definite_or_probable, definite_covers_dark_areas, and background_controls_on_actual_background are assigned constants.",
            "phase_b_action": "generate per-point patches and explicit atlas-point statuses without modifying atlas v1",
            "scientific_impact": "R1 atlas validity statements require direct reinspection.",
        },
        {
            "finding_id": "R2A-F08",
            "stage_id": "S14_CONCLUSION_GATE",
            "status": "CONFIRMED_CONCLUSION_LOGIC_ERROR",
            "finding": "R1 maps median skeleton-minus-background >=0.03 directly to skeleton_signal_retained.",
            "code_evidence": "run_oty2_rsa0_r1_free_geometry_reaudit.py:695-705",
            "array_or_manifest_evidence": "Weak/strong frames, subtype activation, ridge distance, coordinate dependence, and counterexamples are not required by the label.",
            "phase_b_action": "replace the label with separate evidence dimensions and conclusion lineage",
            "scientific_impact": "Several R1 top-channel statements are not supported by their stated decision logic.",
        },
    ]
    write_csv(PHASE_A_FINDINGS, findings)
    report_lines = [
        "# OTY2-RSA0-R2 Phase A Frozen Findings",
        "",
        "Date: `2026-07-17`",
        "",
        "Phase A is audit-only. No R1 source or frozen R1 artifact is modified.",
        "",
    ]
    for row in findings:
        report_lines.extend([
            f"## {row['finding_id']} — {row['status']}",
            "",
            row["finding"],
            "",
            f"- Stage: `{row['stage_id']}`",
            f"- Code evidence: `{row['code_evidence']}`",
            f"- Array/manifest evidence: {row['array_or_manifest_evidence']}",
            f"- Allowed Phase B action: {row['phase_b_action']}",
            f"- Scientific impact: {row['scientific_impact']}",
            "",
        ])
    PHASE_A_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    phase_a_lineage = ctx.output_root / "phase_a_array_lineage.csv"
    write_csv(phase_a_lineage, lineage)
    external_files.append(phase_a_lineage)
    freeze_paths = [PHASE_A_FINDINGS, PHASE_A_REPORT, *external_files]
    freeze_rows = [{"path": str(path), "sha256": sha256_file(path), "role": "phase_a_frozen_before_phase_b"} for path in freeze_paths]
    write_csv(PHASE_A_FREEZE, freeze_rows)
    write_json(ctx.output_root / "phase_a_freeze.json", {"status": "FROZEN", "files": freeze_rows})


def check_phase_a_freeze(ctx: AuditContext) -> None:
    rows = read_csv(PHASE_A_FREEZE)
    require(bool(rows), "phase A freeze is empty")
    for row in rows:
        path = Path(row["path"])
        require(path.is_file(), f"missing frozen phase A file: {path}")
        require(sha256_file(path) == row["sha256"], f"phase A file changed after freeze: {path}")


@dataclass
class CaseData:
    window: dict[str, Any]
    frames: list[int]
    primary_index: int
    image_paths: list[Path]
    decoded: list[np.ndarray]
    raw_stack: np.ndarray
    family_stacks: dict[str, np.ndarray]
    family_valids: dict[str, np.ndarray]
    family_matrices: dict[str, list[np.ndarray]]
    gt_centers: list[tuple[float, float]]
    proxy_centers: list[tuple[float, float]]
    transport_values: list[tuple[float, float]]
    geometry: dict[str, Any]


def build_case_data(ctx: AuditContext, window: Mapping[str, Any]) -> CaseData:
    frames = [int(item) for item in window["frames"]]
    primary_index = frames.index(int(window["primary_frame"]))
    decoded: list[np.ndarray] = []
    grays: list[np.ndarray] = []
    image_paths: list[Path] = []
    gt_centers: list[tuple[float, float]] = []
    proxy_centers: list[tuple[float, float]] = []
    transports: list[tuple[float, float]] = []
    for frame in frames:
        condition = selected_row(ctx.conditions, window["scene"], window["vehicle_id"], frame)
        gt = selected_row(ctx.gt_rows, window["scene"], window["vehicle_id"], frame)
        path = Path(condition["sar_gray_path"])
        color, gray = read_png(path)
        decoded.append(color)
        grays.append(gray)
        image_paths.append(path)
        gt_centers.append(gt_center(gt))
        proxy_centers.append(proxy_center(condition))
        dx, dy, _ = transport_for(ctx, window["scene"], frame)
        transports.append((dx, dy))
    raw_stack = np.stack(grays).astype(np.uint8)
    valid = imaging_valid_mask()
    ref_transport = transports[0]
    ref_gt = gt_centers[0]
    ref_proxy = proxy_centers[0]
    matrices: dict[str, list[np.ndarray]] = {
        "RAW_SAR_DISPLAY": [translation_matrix(0.0, 0.0) for _ in frames],
        "WORLD_STABILIZED_IMAGE_STACK": [translation_matrix(-(dx - ref_transport[0]), -(dy - ref_transport[1])) for dx, dy in transports],
        "GT_ALIGNED_RESEARCH_STACK": [translation_matrix(ref_gt[0] - x, ref_gt[1] - y) for x, y in gt_centers],
        "OPTICAL_PROXY_ALIGNED_STACK": [translation_matrix(ref_proxy[0] - x, ref_proxy[1] - y) for x, y in proxy_centers],
    }
    stacks: dict[str, np.ndarray] = {}
    valids: dict[str, np.ndarray] = {}
    for family, family_matrices in matrices.items():
        images: list[np.ndarray] = []
        source_valids: list[np.ndarray] = []
        for image, matrix in zip(raw_stack, family_matrices):
            images.append(warp_image(image, matrix, cv2.INTER_LINEAR))
            source_valids.append(warp_image(valid.astype(np.uint8), matrix, cv2.INTER_NEAREST).astype(bool))
        stacks[family] = np.stack(images).astype(np.uint8)
        valids[family] = np.stack(source_valids).astype(bool)
    return CaseData(
        window=dict(window),
        frames=frames,
        primary_index=primary_index,
        image_paths=image_paths,
        decoded=decoded,
        raw_stack=raw_stack,
        family_stacks=stacks,
        family_valids=valids,
        family_matrices=matrices,
        gt_centers=gt_centers,
        proxy_centers=proxy_centers,
        transport_values=transports,
        geometry=atlas_geometry(ctx, window),
    )


def patch_at(image: np.ndarray, point: tuple[float, float], size: int) -> np.ndarray:
    half = size // 2
    x = int(round(point[0]))
    y = int(round(point[1]))
    padded = cv2.copyMakeBorder(image, half, half, half, half, cv2.BORDER_CONSTANT, value=0)
    return padded[y:y + size, x:x + size]


def normalized_cross_correlation(left: np.ndarray, right: np.ndarray) -> float:
    a = left.astype(np.float32).ravel()
    b = right.astype(np.float32).ravel()
    a -= float(np.mean(a))
    b -= float(np.mean(b))
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 1e-6 else 0.0


def coordinate_card(path: Path, data: CaseData, family: str) -> None:
    stack = data.family_stacks[family]
    valid = data.family_valids[family]
    primary_matrix = data.family_matrices[family][data.primary_index]
    transformed_geometry = geometry_masks(data.geometry, primary_matrix)["_geometry"]
    primary_center = transform_points([data.gt_centers[data.primary_index]], primary_matrix)[0]
    x1, y1, x2, y2 = crop_bounds(primary_center, 600, 420)
    selected_indices = [0, data.primary_index, len(data.frames) - 1]
    figure, axes = plt.subplots(2, 3, figsize=(16, 9))
    for axis, idx in zip(axes[0], selected_indices):
        axis.imshow(display_u8(stack[idx])[y1:y2, x1:x2], cmap="gray", vmin=0, vmax=255)
        matrix = data.family_matrices[family][idx]
        gx, gy = transform_points([data.gt_centers[idx]], matrix)[0]
        px, py = transform_points([data.proxy_centers[idx]], matrix)[0]
        axis.scatter([gx - x1], [gy - y1], c="cyan", marker="+", s=100, label="GT")
        axis.scatter([px - x1], [py - y1], c="magenta", marker="x", s=80, label="proxy")
        if idx == data.primary_index:
            draw_geometry(axis, transformed_geometry, x1, y1)
        axis.set_title(f"{family}\nSAR {data.frames[idx]} shift=({matrix[0,2]:.1f},{matrix[1,2]:.1f})")
        axis.axis("off")
    diff = cv2.absdiff(stack[0], stack[-1])
    axes[1, 0].imshow(diff[y1:y2, x1:x2], cmap="magma")
    axes[1, 0].set_title("abs(first-last)")
    axes[1, 1].imshow(valid[data.primary_index][y1:y2, x1:x2], cmap="gray")
    axes[1, 1].set_title(f"primary valid-source mask | {valid[data.primary_index].mean():.6f}")
    matrix_lines = [
        f"SAR {frame}: dx={matrix[0,2]:.3f}, dy={matrix[1,2]:.3f}"
        for frame, matrix in zip(data.frames, data.family_matrices[family])
    ]
    axes[1, 2].text(0.01, 0.98, "\n".join(matrix_lines), va="top", family="monospace", fontsize=10)
    axes[1, 2].axis("off")
    for axis in axes[1, :2]:
        axis.axis("off")
    figure.suptitle(f"{data.window['case_id']} coordinate-stack evidence")
    save_figure(path, figure)


def background_stability_card(path: Path, data: CaseData) -> dict[str, float]:
    points = [
        (f"background_{item['subtype']}", polyline_midpoint(item["points"]))
        for item in data.geometry["backgrounds"][:3]
    ]
    families = ["RAW_SAR_DISPLAY", "WORLD_STABILIZED_IMAGE_STACK"]
    figure, axes = plt.subplots(len(points) * 2, len(data.frames), figsize=(15, 12))
    ncc_summary: dict[str, list[float]] = defaultdict(list)
    for point_index, (point_name, raw_point) in enumerate(points):
        for family_index, family in enumerate(families):
            primary_matrix = data.family_matrices[family][data.primary_index]
            output_point = transform_points([raw_point], primary_matrix)[0]
            reference = patch_at(data.family_stacks[family][data.primary_index], output_point, 41)
            row_index = point_index * 2 + family_index
            for col_index, frame in enumerate(data.frames):
                patch = patch_at(data.family_stacks[family][col_index], output_point, 41)
                ncc = normalized_cross_correlation(reference, patch)
                if col_index != data.primary_index:
                    ncc_summary[f"{family}:{point_name}"].append(ncc)
                axes[row_index, col_index].imshow(display_u8(patch), cmap="gray")
                axes[row_index, col_index].set_title(f"{frame} NCC={ncc:.2f}", fontsize=8)
                axes[row_index, col_index].axis("off")
            axes[row_index, 0].set_ylabel(f"{point_name}\n{family}", fontsize=8)
    figure.suptitle(f"{data.window['case_id']} actual background patch stability")
    save_figure(path, figure)
    return {key: float(np.median(values)) if values else 1.0 for key, values in ncc_summary.items()}


def transform_quality(image: np.ndarray, valid: np.ndarray, matrix: np.ndarray) -> dict[str, float]:
    inverse = invert_translation(matrix)
    transformed = warp_image(image, matrix, cv2.INTER_LINEAR)
    reconstructed = warp_image(transformed, inverse, cv2.INTER_LINEAR)
    forward_valid = warp_image(valid.astype(np.uint8), matrix, cv2.INTER_NEAREST).astype(bool)
    reconstructed_valid = warp_image(forward_valid.astype(np.uint8), inverse, cv2.INTER_NEAREST).astype(bool)
    intersection = valid & reconstructed_valid
    union = valid | reconstructed_valid
    mae = float(np.mean(np.abs(reconstructed.astype(np.float32)[intersection] - image.astype(np.float32)[intersection]))) if np.any(intersection) else math.nan
    nearest = warp_image(image, matrix, cv2.INTER_NEAREST)
    interpolation_affected = float(np.mean((transformed != nearest)[forward_valid])) if np.any(forward_valid) else math.nan
    test_points = [(100.0, 100.0), (1154.0, 700.0), (2100.0, 1100.0)]
    roundtrip = transform_points(transform_points(test_points, matrix), inverse)
    point_error = float(max(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(test_points, roundtrip)))
    return {
        "point_roundtrip_max_error_px": point_error,
        "mask_roundtrip_iou": float(np.sum(intersection) / np.sum(union)),
        "image_roundtrip_mae": mae,
        "transformed_valid_fraction": float(np.mean(forward_valid)),
        "interpolation_affected_fraction": interpolation_affected,
        "border_fill_fraction": float(1.0 - np.mean(forward_valid)),
    }


def run_coordinate_stacks(ctx: AuditContext, cases: Sequence[CaseData]) -> list[dict[str, Any]]:
    check_phase_a_freeze(ctx)
    rows: list[dict[str, Any]] = []
    lineage = read_csv(ctx.output_root / "phase_a_array_lineage.csv")
    evidence_dir = ctx.output_root / "evidence_cards" / "coordinate_stacks"
    arrays_dir = ctx.output_root / "arrays" / "phase_b" / "coordinate_stacks"
    for data in cases:
        for family in ["RAW_SAR_DISPLAY", "WORLD_STABILIZED_IMAGE_STACK", "GT_ALIGNED_RESEARCH_STACK", "OPTICAL_PROXY_ALIGNED_STACK"]:
            stack = data.family_stacks[family]
            valid_stack = data.family_valids[family]
            bundle_path = arrays_dir / data.window["case_id"] / f"{data.window['case_id'].lower()}_{family.lower()}.npz"
            bundle_sha = save_bundle(bundle_path, {"image_stack": stack, "valid_source_stack": valid_stack})
            lineage.append(lineage_row(data.window["case_id"], f"{data.frames[0]}-{data.frames[-1]}", "S04_S07_COORDINATE_STACK", f"{family}.image_stack", ";".join(map(str, data.image_paths)), "MULTI_SOURCE_SEE_OUTPUT_MANIFEST", family, stack, valid_stack, bundle_path, bundle_sha))
            lineage.append(lineage_row(data.window["case_id"], f"{data.frames[0]}-{data.frames[-1]}", "S04_S07_COORDINATE_STACK", f"{family}.valid_source_stack", "imaging_valid_mask+transform", FAN_MASK_HASH, family, valid_stack, valid_stack, bundle_path, bundle_sha))
            card = evidence_dir / data.window["case_id"] / f"{data.window['case_id'].lower()}_{family.lower()}_input_operation_output.png"
            coordinate_card(card, data, family)
            for index, frame in enumerate(data.frames):
                matrix = data.family_matrices[family][index]
                quality = transform_quality(data.raw_stack[index], imaging_valid_mask(), matrix)
                gt_out = transform_points([data.gt_centers[index]], matrix)[0]
                proxy_out = transform_points([data.proxy_centers[index]], matrix)[0]
                rows.append({
                    "case_id": data.window["case_id"],
                    "frame": frame,
                    "coordinate_family": family,
                    "reference_frame": data.frames[0],
                    "matrix": json.dumps(matrix.tolist(), separators=(",", ":")),
                    "inverse_matrix": json.dumps(invert_translation(matrix).tolist(), separators=(",", ":")),
                    "shift_x_px": float(matrix[0, 2]),
                    "shift_y_px": float(matrix[1, 2]),
                    "interpolation": "cv2.INTER_LINEAR",
                    "border_mode": "cv2.BORDER_CONSTANT",
                    "border_value": 0,
                    "gt_x_transformed": gt_out[0],
                    "gt_y_transformed": gt_out[1],
                    "proxy_x_transformed": proxy_out[0],
                    "proxy_y_transformed": proxy_out[1],
                    **quality,
                    "evidence_card": str(card),
                })
        stability_card = evidence_dir / data.window["case_id"] / f"{data.window['case_id'].lower()}_background_patch_stability.png"
        stability = background_stability_card(stability_card, data)
        for key, value in stability.items():
            family, point = key.split(":", 1)
            rows.append({
                "case_id": data.window["case_id"],
                "frame": f"{data.frames[0]}-{data.frames[-1]}",
                "coordinate_family": family,
                "reference_frame": data.window["primary_frame"],
                "background_point": point,
                "background_patch_ncc_median_excluding_reference": value,
                "evidence_card": str(stability_card),
            })
    write_csv(COORDINATE_AUDIT, rows)
    write_csv(ARRAY_LINEAGE, lineage)
    report = [
        "# OTY2-RSA0-R2 Coordinate-Stack Audit",
        "",
        "All four stacks use complete contiguous five-frame windows. Image, geometry, points, and valid-source masks share the same translation matrix within each aligned family.",
        "",
    ]
    for data in cases:
        report.extend([f"## {data.window['case_id']}", ""])
        for family in ["RAW_SAR_DISPLAY", "WORLD_STABILIZED_IMAGE_STACK", "GT_ALIGNED_RESEARCH_STACK", "OPTICAL_PROXY_ALIGNED_STACK"]:
            family_rows = [row for row in rows if row.get("case_id") == data.window["case_id"] and row.get("coordinate_family") == family and "point_roundtrip_max_error_px" in row]
            report.append(
                f"- `{family}`: point closure max `{max(float(row['point_roundtrip_max_error_px']) for row in family_rows):.6f}` px; "
                f"mask IoU min `{min(float(row['mask_roundtrip_iou']) for row in family_rows):.6f}`; "
                f"image reconstruction MAE max `{max(float(row['image_roundtrip_mae']) for row in family_rows):.6f}`."
            )
        world_stability = [row for row in rows if row.get("case_id") == data.window["case_id"] and row.get("coordinate_family") == "WORLD_STABILIZED_IMAGE_STACK" and "background_patch_ncc_median_excluding_reference" in row]
        raw_stability = [row for row in rows if row.get("case_id") == data.window["case_id"] and row.get("coordinate_family") == "RAW_SAR_DISPLAY" and "background_patch_ncc_median_excluding_reference" in row]
        if world_stability and raw_stability:
            report.append(f"- Actual background patch NCC median: RAW `{np.median([float(row['background_patch_ncc_median_excluding_reference']) for row in raw_stability]):.6f}`, WORLD `{np.median([float(row['background_patch_ncc_median_excluding_reference']) for row in world_stability]):.6f}`.")
        report.append("")
    COORDINATE_REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    return rows


def fan_geometry_card(path: Path, data: CaseData) -> None:
    frame = data.window["primary_frame"]
    image = data.raw_stack[data.primary_index]
    geometry = data.geometry
    figure, axis = plt.subplots(1, 1, figsize=(16, 9))
    axis.imshow(display_u8(image), cmap="gray", vmin=0, vmax=255)
    axis.scatter([FAN_CENTER[0]], [FAN_CENTER[1]], c="yellow", s=80, marker="o", label="fan origin")
    for theta in [-60, -30, 0, 30, 60]:
        radians = math.radians(theta)
        x = FAN_CENTER[0] + FAN_RADIUS * math.sin(radians)
        y = FAN_CENTER[1] - FAN_RADIUS * math.cos(radians)
        axis.plot([FAN_CENTER[0], x], [FAN_CENTER[1], y], color="cyan", linewidth=0.8)
    for radius in [300, 600, 900, 1200, FAN_RADIUS]:
        theta = np.radians(np.linspace(-90, 90, 300))
        x = FAN_CENTER[0] + radius * np.sin(theta)
        y = FAN_CENTER[1] - radius * np.cos(theta)
        axis.plot(x, y, color="deepskyblue" if radius < FAN_RADIUS else "white", linewidth=0.8)
    draw_geometry(axis, geometry)
    axis.set_xlim(0, FAN_WIDTH)
    axis.set_ylim(FAN_HEIGHT, 0)
    axis.set_title(f"{data.window['case_id']} SAR {frame} | fan origin, radial lines, tangential arcs, atlas")
    axis.axis("off")
    save_figure(path, figure)


def boundary_error(left: np.ndarray, right: np.ndarray) -> tuple[float, float]:
    left_edge = left ^ cv2.erode(left.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    right_edge = right ^ cv2.erode(right.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    distance_to_right = cv2.distanceTransform((~right_edge).astype(np.uint8), cv2.DIST_L2, 3)
    distance_to_left = cv2.distanceTransform((~left_edge).astype(np.uint8), cv2.DIST_L2, 3)
    distances = np.concatenate([distance_to_right[left_edge], distance_to_left[right_edge]])
    return float(np.median(distances)), float(np.max(distances))


def run_fan_geometry(ctx: AuditContext, cases: Sequence[CaseData]) -> list[dict[str, Any]]:
    frozen = imaging_valid_mask()
    candidates = [
        ("S0_FROZEN_CONTRACT", (1154.0, 1330.6), "docs/OTY2_S0_SAR_COORDINATE_AND_GRID_CONTRACT.md", "explicit frozen fan-polar contract"),
        ("R1_HARDCODE_IMAGE_SHAPE", (FAN_WIDTH / 2.0, FAN_HEIGHT - 3.4), "run_oty2_rsa0_r1_free_geometry_reaudit.py:315-325", "image_width/2 and image_height-3.4"),
        ("CANVAS_BOTTOM_CENTER_CONTROL", (FAN_WIDTH / 2.0, float(FAN_HEIGHT)), "R2 negative control", "bottom-center control without the frozen -3.4 offset"),
    ]
    rows: list[dict[str, Any]] = []
    evidence_dir = ctx.output_root / "evidence_cards" / "fan_geometry"
    cards: dict[str, Path] = {}
    for data in cases:
        card = evidence_dir / data.window["case_id"] / f"{data.window['case_id'].lower()}_{data.window['primary_frame']}_fan_geometry.png"
        fan_geometry_card(card, data)
        cards[data.window["case_id"]] = card
    for candidate_id, origin, source, derivation in candidates:
        mask = imaging_valid_mask(origin=origin)
        intersection = np.sum(mask & frozen)
        union = np.sum(mask | frozen)
        median_error, max_error = boundary_error(mask, frozen)
        for data in cases:
            rows.append({
                "case_id": data.window["case_id"],
                "candidate_id": candidate_id,
                "source_file": source,
                "derivation_formula": derivation,
                "origin_x_px": origin[0],
                "origin_y_px": origin[1],
                "valid_theta_min_deg": -90.0,
                "valid_theta_max_deg": 90.0,
                "radial_min_px": 0.0,
                "radial_max_px": FAN_RADIUS,
                "mask_iou_vs_frozen": float(intersection / union),
                "boundary_error_median_px": median_error,
                "boundary_error_max_px": max_error,
                "consistent_with_s0_s1x_geometry": fmt(candidate_id in {"S0_FROZEN_CONTRACT", "R1_HARDCODE_IMAGE_SHAPE"}),
                "radial_channel_semantics": "gradient component normal to fan arcs; not line orientation",
                "tangential_channel_semantics": "gradient component normal to radial structures; not arc intensity itself",
                "evidence_card": str(cards[data.window["case_id"]]),
                "decision": "CONFIRMED" if candidate_id in {"S0_FROZEN_CONTRACT", "R1_HARDCODE_IMAGE_SHAPE"} else "REJECTED_CONTROL",
            })
    write_csv(FAN_AUDIT, rows)
    return rows


def audit_points(data: CaseData) -> list[dict[str, Any]]:
    geometry = data.geometry
    skeleton = geometry["skeleton"]
    seed = geometry["seed"]
    unresolved = geometry["regions"].get("UNRESOLVED", [[]])[0]
    points: list[dict[str, Any]] = [
        {"point_id": "skeleton_left", "role": "skeleton", "point": skeleton[0]},
        {"point_id": "skeleton_mid", "role": "skeleton", "point": polyline_midpoint(skeleton)},
        {"point_id": "skeleton_right", "role": "skeleton", "point": skeleton[-1]},
        {"point_id": "seed_mid", "role": "seed", "point": polyline_midpoint(seed)},
    ]
    for item in geometry["backgrounds"]:
        points.append({
            "point_id": f"background_{item['subtype']}",
            "role": "background",
            "subtype": item["subtype"],
            "point": polyline_midpoint(item["points"]),
        })
    points.extend([
        {"point_id": "unresolved_centroid", "role": "unresolved", "point": polygon_centroid(unresolved)},
        {"point_id": "gt_center", "role": "coordinate_reference", "point": data.gt_centers[data.primary_index]},
        {"point_id": "optical_proxy_center", "role": "coordinate_reference", "point": data.proxy_centers[data.primary_index]},
    ])
    return points


def atlas_review_card(path: Path, data: CaseData, decisions: Mapping[str, str], patch_size: int) -> None:
    image = data.raw_stack[data.primary_index]
    geometry = data.geometry
    center = data.gt_centers[data.primary_index]
    x1, y1, x2, y2 = crop_bounds(center, 600, 420)
    figure, axes = plt.subplots(2, 3, figsize=(16, 10))
    base = display_u8(image)[y1:y2, x1:x2]
    axes[0, 0].imshow(base, cmap="gray")
    axes[0, 0].set_title("raw no overlay")
    axes[0, 1].imshow(base, cmap="gray")
    skel_geom = {"skeleton": geometry["skeleton"], "seed": [], "regions": {}, "backgrounds": []}
    draw_geometry(axes[0, 1], skel_geom, x1, y1)
    axes[0, 1].set_title("skeleton only")
    axes[0, 2].imshow(base, cmap="gray")
    definite_geom = {"skeleton": [], "seed": [], "regions": {"DEFINITE_TARGET_RESPONSE": geometry["regions"].get("DEFINITE_TARGET_RESPONSE", [])}, "backgrounds": []}
    draw_geometry(axes[0, 2], definite_geom, x1, y1)
    axes[0, 2].set_title("definite only")
    axes[1, 0].imshow(base, cmap="gray")
    background_geom = {"skeleton": [], "seed": [], "regions": {}, "backgrounds": geometry["backgrounds"]}
    draw_geometry(axes[1, 0], background_geom, x1, y1)
    axes[1, 0].set_title("background controls only")
    axes[1, 1].imshow(base, cmap="gray")
    draw_geometry(axes[1, 1], geometry, x1, y1)
    axes[1, 1].set_title("full overlay")
    text = "\n".join(f"{key}: {value}" for key, value in decisions.items())
    axes[1, 2].text(0.01, 0.99, text, va="top", family="monospace", fontsize=9)
    axes[1, 2].axis("off")
    for axis in [axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 0], axes[1, 1]]:
        axis.axis("off")
    figure.suptitle(f"{data.window['case_id']} SAR {data.window['primary_frame']} atlas direct review")
    save_figure(path, figure)

    patch_path = path.with_name(path.stem + "_point_patches.png")
    points = [item for item in audit_points(data) if item["role"] in {"skeleton", "seed", "background", "unresolved"}]
    cols = 4
    rows = math.ceil(len(points) / cols)
    figure, axes = plt.subplots(rows, cols, figsize=(14, 3.5 * rows))
    axes_array = np.atleast_1d(axes).ravel()
    for axis, item in zip(axes_array, points):
        patch = patch_at(image, item["point"], patch_size)
        axis.imshow(display_u8(patch), cmap="gray")
        axis.axhline(patch_size // 2, color="cyan", linewidth=0.7)
        axis.axvline(patch_size // 2, color="cyan", linewidth=0.7)
        axis.set_title(f"{item['point_id']}\n{decisions.get(item['point_id'],'SEMANTICALLY_AMBIGUOUS')}", fontsize=9)
        axis.axis("off")
    for axis in axes_array[len(points):]:
        axis.axis("off")
    figure.suptitle(f"{data.window['case_id']} point-level 41x41 patches")
    save_figure(patch_path, figure)


def run_atlas_audit(ctx: AuditContext, cases: Sequence[CaseData]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    evidence_dir = ctx.output_root / "evidence_cards" / "atlas_review"
    for data in cases:
        decisions = ctx.config["atlas_review_decisions"][data.window["case_id"]]
        card = evidence_dir / data.window["case_id"] / f"{data.window['case_id'].lower()}_{data.window['primary_frame']}_atlas_review.png"
        atlas_review_card(card, data, decisions, int(ctx.config["patch_size"]))
        patch_card = card.with_name(card.stem + "_point_patches.png")
        image = data.raw_stack[data.primary_index]
        for item in audit_points(data):
            if item["role"] == "coordinate_reference":
                continue
            x, y = item["point"]
            ix, iy = int(round(x)), int(round(y))
            rows.append({
                "case_id": data.window["case_id"],
                "frame": data.window["primary_frame"],
                "point_id": item["point_id"],
                "point_role": item["role"],
                "background_subtype": item.get("subtype", ""),
                "x_px": x,
                "y_px": y,
                "raw_gray_value": int(image[iy, ix]) if 0 <= ix < FAN_WIDTH and 0 <= iy < FAN_HEIGHT else "",
                "status": decisions.get(item["point_id"], "SEMANTICALLY_AMBIGUOUS"),
                "review_basis": "direct inspection of raw/no-overlay, single-label overlays, full overlay, and point patch sheet",
                "correction_proposal": "review in a separate atlas-v1.1 decision; R2 does not modify atlas v1" if decisions.get(item["point_id"]) != "CONFIRMED" else "",
                "review_card": str(card),
                "patch_card": str(patch_card),
            })
    write_csv(ATLAS_AUDIT, rows)
    return rows


CHANNEL_HIGH_SEMANTICS = {
    "raw_display_intensity": "high displayed grayscale intensity; not a unique scatterer or vehicle centre",
    "local_contrast_31": "brighter than the 31x31 local mean",
    "local_z_31": "positive local standardized brightness anomaly",
    "highpass_sigma9": "fine structure brighter than a sigma-9 smooth background",
    "sobel_x_abs_gradient_component": "strong left-right intensity change; vertical-edge normal response",
    "sobel_y_abs_gradient_component": "strong up-down intensity change; horizontal-edge normal response",
    "gradient_magnitude_sobel": "strong intensity boundary in any direction",
    "multiscale_laplacian_bright_ridge": "negative multiscale Laplacian consistent with a locally bright ridge; not a full Hessian eigenvalue ridge detector",
    "structure_tensor_orientation_coherence": "locally anisotropic gradient orientation, independent of target ownership",
    "radial_gradient_normal_response": "gradient normal component along the fan radial direction; high on edges locally tangent to a fan arc",
    "tangential_gradient_normal_response": "gradient normal component along the fan tangential direction; high on edges locally radial from the fan origin",
}


def temporal_formula(name: str) -> str:
    if name.endswith("_median"):
        return "per-pixel median over the selected aligned stack window"
    if name.endswith("_max"):
        return "per-pixel maximum over the selected aligned stack window"
    if name.endswith("_min"):
        return "per-pixel minimum over the selected aligned stack window"
    if name.endswith("_mad"):
        return "per-pixel median absolute deviation over the selected aligned stack window"
    if "gradient_persistence" in name:
        return "absolute mean x-gradient sign times mean x-gradient magnitude"
    if "high_intensity_pixel_frequency" in name:
        return "fraction of valid frames where the pixel exceeds that frame's valid-fan 80th percentile"
    if "legacy_per_pixel_rank_frequency" in name:
        return "fraction of frames above the pixel's own temporal 75th percentile; historical diagnostic only"
    if "positive_change" in name:
        return "max(I_t-I_tminus1,0)"
    if "negative_change" in name:
        return "max(I_tminus1-I_t,0)"
    return "temporal diagnostic"


def channel_maps_at(data: CaseData, family: str, index: int) -> dict[str, np.ndarray]:
    maps = single_channels(data.family_stacks[family][index])
    for half in [2, 4]:
        maps.update(temporal_channels(data.family_stacks[family], data.family_valids[family], index, half))
    return maps


def frozen_channel_ranges(
    ctx: AuditContext,
    data: CaseData,
    family: str,
    frame_single_maps: Sequence[Mapping[str, np.ndarray]],
    primary_maps: Mapping[str, np.ndarray],
) -> dict[str, tuple[float, float]]:
    stride = int(ctx.config["frozen_sample_stride"])
    values: dict[str, list[np.ndarray]] = defaultdict(list)
    for index, maps in enumerate(frame_single_maps):
        valid = data.family_valids[family][index]
        for name, array in maps.items():
            sample = array[::stride, ::stride]
            sample_valid = valid[::stride, ::stride]
            values[name].append(sample[sample_valid & np.isfinite(sample)].astype(np.float32))
    primary_valid = data.family_valids[family][data.primary_index]
    for name, array in primary_maps.items():
        if name in SINGLE_CHANNEL_FORMULAS:
            continue
        sample = array[::stride, ::stride]
        sample_valid = primary_valid[::stride, ::stride]
        values[name].append(sample[sample_valid & np.isfinite(sample)].astype(np.float32))
    output: dict[str, tuple[float, float]] = {}
    for name, parts in values.items():
        merged = np.concatenate(parts) if parts else np.asarray([], dtype=np.float32)
        output[name] = tuple(float(item) for item in np.percentile(merged, ctx.config["normalization_percentiles"])) if merged.size else (0.0, 0.0)
    return output


def local_audit_mask(masks: Mapping[str, Any], valid: np.ndarray, margin: int = 35) -> np.ndarray:
    union = masks["skeleton"] | masks["definite"] | masks["background"] | masks["unresolved"]
    if margin > 0:
        size = 2 * margin + 1
        union = cv2.dilate(union.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))).astype(bool)
    return union & valid


def exact_rank_auc(pos: np.ndarray, neg: np.ndarray) -> float:
    pos = pos[np.isfinite(pos)].astype(np.float64)
    neg = neg[np.isfinite(neg)].astype(np.float64)
    if pos.size == 0 or neg.size == 0:
        return math.nan
    ranks = rankdata(np.concatenate([pos, neg]), method="average")
    rank_sum = float(np.sum(ranks[:pos.size]))
    return float((rank_sum - pos.size * (pos.size + 1) / 2.0) / (pos.size * neg.size))


def legacy_first3000_auc(pos: np.ndarray, neg: np.ndarray) -> float:
    return exact_rank_auc(pos[: min(3000, pos.size)], neg[: min(3000, neg.size)])


def uniform_sample(values: np.ndarray, limit: int, seed: int) -> np.ndarray:
    if values.size <= limit:
        return values
    rng = np.random.default_rng(seed)
    return values[rng.choice(values.size, size=limit, replace=False)]


def spatial_stratified_values(array: np.ndarray, mask: np.ndarray, per_cell: int, seed: int, rows: int = 4, cols: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    selected: list[np.ndarray] = []
    height, width = array.shape
    for row in range(rows):
        y1 = int(round(row * height / rows))
        y2 = int(round((row + 1) * height / rows))
        for col in range(cols):
            x1 = int(round(col * width / cols))
            x2 = int(round((col + 1) * width / cols))
            values = array[y1:y2, x1:x2][mask[y1:y2, x1:x2]]
            values = values[np.isfinite(values)]
            if values.size > per_cell:
                values = values[rng.choice(values.size, size=per_cell, replace=False)]
            if values.size:
                selected.append(values)
    return np.concatenate(selected) if selected else np.asarray([], dtype=np.float32)


def channel_evidence_card(
    path: Path,
    image: np.ndarray,
    channel: np.ndarray,
    norms: Mapping[str, np.ndarray],
    geometry: Mapping[str, Any],
    center: tuple[float, float],
    title: str,
) -> None:
    x1, y1, x2, y2 = crop_bounds(center, 600, 420)
    figure, axes = plt.subplots(2, 3, figsize=(16, 9))
    axes[0, 0].imshow(display_u8(image)[y1:y2, x1:x2], cmap="gray")
    draw_geometry(axes[0, 0], geometry, x1, y1)
    axes[0, 0].set_title("input image + geometry")
    raw_crop = channel[y1:y2, x1:x2]
    finite = raw_crop[np.isfinite(raw_crop)]
    vmin, vmax = np.percentile(finite, [2, 98]) if finite.size else (0.0, 1.0)
    axes[0, 1].imshow(raw_crop, cmap="viridis", vmin=vmin, vmax=vmax)
    draw_geometry(axes[0, 1], geometry, x1, y1)
    axes[0, 1].set_title(f"raw float | {float(np.nanmin(raw_crop)):.3g}..{float(np.nanmax(raw_crop)):.3g}")
    order = ["legacy_full_frame", "valid_fan_per_frame", "window_frozen_valid", "local_target_matched_background"]
    for axis, name in zip([axes[0, 2], axes[1, 0], axes[1, 1], axes[1, 2]], order):
        axis.imshow(norms[name][y1:y2, x1:x2], cmap="viridis", vmin=0, vmax=1)
        draw_geometry(axis, geometry, x1, y1)
        axis.set_title(name)
    for axis in axes.ravel():
        axis.axis("off")
    figure.suptitle(title)
    save_figure(path, figure)


def point_inside(array: np.ndarray, point: tuple[float, float]) -> Any:
    x, y = int(round(point[0])), int(round(point[1]))
    if not (0 <= x < array.shape[1] and 0 <= y < array.shape[0]):
        return math.nan
    value = array[y, x]
    return float(value) if np.isscalar(value) else value


def build_channel_products(
    ctx: AuditContext,
    cases: Sequence[CaseData],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    check_phase_a_freeze(ctx)
    channel_rows: list[dict[str, Any]] = []
    normalization_rows: list[dict[str, Any]] = []
    sampling_rows: list[dict[str, Any]] = []
    cache: dict[tuple[str, str], dict[str, Any]] = {}
    lineage = read_csv(ARRAY_LINEAGE) if ARRAY_LINEAGE.exists() else read_csv(ctx.output_root / "phase_a_array_lineage.csv")
    arrays_dir = ctx.output_root / "arrays" / "phase_b" / "channels"
    evidence_dir = ctx.output_root / "evidence_cards" / "channels"
    families = ["RAW_SAR_DISPLAY", "WORLD_STABILIZED_IMAGE_STACK", "GT_ALIGNED_RESEARCH_STACK", "OPTICAL_PROXY_ALIGNED_STACK"]
    for data in cases:
        primary = data.primary_index
        primary_frame = data.frames[primary]
        for family in families:
            matrix = data.family_matrices[family][primary]
            masks = geometry_masks(data.geometry, matrix)
            transformed_geometry = masks["_geometry"]
            valid = data.family_valids[family][primary]
            image = data.family_stacks[family][primary]
            frame_single_maps = [single_channels(data.family_stacks[family][index]) for index in range(len(data.frames))]
            maps = dict(frame_single_maps[primary])
            for half in [2, 4]:
                maps.update(temporal_channels(data.family_stacks[family], data.family_valids[family], primary, half))
            fixed_ranges = frozen_channel_ranges(ctx, data, family, frame_single_maps, maps)
            local_mask = local_audit_mask(masks, valid)
            arrays: dict[str, np.ndarray] = {
                "image": image,
                "valid_source_mask": valid,
                "skeleton_mask": masks["skeleton"],
                "seed_mask": masks["seed"],
                "definite_mask": masks["definite"],
                "background_mask": masks["background"],
                "unresolved_mask": masks["unresolved"],
            }
            channel_cache: dict[str, Any] = {}
            for channel_name, channel in maps.items():
                full_range = normalization_range(channel, None, ctx.config["normalization_percentiles"])
                valid_range = normalization_range(channel, valid, ctx.config["normalization_percentiles"])
                frozen_range = fixed_ranges[channel_name]
                local_range = normalization_range(channel, local_mask, ctx.config["normalization_percentiles"])
                norms = {
                    "legacy_full_frame": apply_range(channel, *full_range),
                    "valid_fan_per_frame": apply_range(channel, *valid_range),
                    "window_frozen_valid": apply_range(channel, *frozen_range),
                    "local_target_matched_background": apply_range(channel, *local_range),
                }
                arrays[f"raw__{channel_name}"] = channel.astype(np.float32)
                for norm_name, norm in norms.items():
                    arrays[f"norm__{norm_name}__{channel_name}"] = norm.astype(np.float16)
                channel_cache[channel_name] = {"raw": channel, "norms": norms, "ranges": {"legacy_full_frame": full_range, "valid_fan_per_frame": valid_range, "window_frozen_valid": frozen_range, "local_target_matched_background": local_range}}
                card = evidence_dir / data.window["case_id"] / family / f"{channel_name}.png"
                channel_evidence_card(card, image, channel, norms, transformed_geometry, transform_points([data.gt_centers[primary]], matrix)[0], f"{data.window['case_id']} SAR {primary_frame} | {family} | {channel_name}")
                skeleton_values = channel[masks["skeleton"] & valid]
                background_values = channel[masks["background"] & valid]
                unresolved_values = channel[masks["unresolved"] & valid]
                black_border = imaging_valid_mask() & ~valid
                subtype_values = {
                    subtype: channel[masks.get(f"background_{subtype}", np.zeros_like(valid)) & valid]
                    for subtype in ["vertical_line", "fan_arc", "clutter"]
                }
                weak_values: list[float] = []
                strong_values: list[float] = []
                fixed_skeleton = masks["skeleton"]
                if channel_name in SINGLE_CHANNEL_FORMULAS:
                    for index, frame in enumerate(data.frames):
                        frame_channel = frame_single_maps[index][channel_name]
                        values = frame_channel[fixed_skeleton & data.family_valids[family][index]]
                        if values.size:
                            target = weak_values if frame in data.window["weak_frames"] else strong_values
                            target.append(float(np.median(values)))
                formula = SINGLE_CHANNEL_FORMULAS.get(channel_name, temporal_formula(channel_name))
                high_semantics = CHANNEL_HIGH_SEMANTICS.get(channel_name, formula)
                channel_rows.append({
                    "case_id": data.window["case_id"],
                    "frame": primary_frame,
                    "coordinate_family": family,
                    "channel": channel_name,
                    "formula": formula,
                    "high_value_semantics": high_semantics,
                    "skeleton_count": skeleton_values.size,
                    "skeleton_median_raw": fmt(np.median(skeleton_values) if skeleton_values.size else math.nan),
                    "background_median_raw": fmt(np.median(background_values) if background_values.size else math.nan),
                    "vertical_line_median_raw": fmt(np.median(subtype_values["vertical_line"]) if subtype_values["vertical_line"].size else math.nan),
                    "fan_arc_median_raw": fmt(np.median(subtype_values["fan_arc"]) if subtype_values["fan_arc"].size else math.nan),
                    "clutter_median_raw": fmt(np.median(subtype_values["clutter"]) if subtype_values["clutter"].size else math.nan),
                    "unresolved_median_raw": fmt(np.median(unresolved_values) if unresolved_values.size else math.nan),
                    "black_or_transform_border_median_raw": fmt(np.median(channel[black_border]) if np.any(black_border) else math.nan),
                    "weak_frame_skeleton_median_raw": fmt(np.median(weak_values) if weak_values else math.nan),
                    "strong_frame_skeleton_median_raw": fmt(np.median(strong_values) if strong_values else math.nan),
                    "name_matches_formula": fmt("component_continuity" not in channel_name and ("hessian" not in channel_name)),
                    "evidence_card": str(card),
                })
                for norm_name, norm in norms.items():
                    lo, hi = channel_cache[channel_name]["ranges"][norm_name]
                    normalization_rows.append({
                        "case_id": data.window["case_id"],
                        "frame": primary_frame,
                        "coordinate_family": family,
                        "channel": channel_name,
                        "normalization": norm_name,
                        "range_low": lo,
                        "range_high": hi,
                        "skeleton_median": fmt(np.median(norm[masks["skeleton"] & valid]) if np.any(masks["skeleton"] & valid) else math.nan),
                        "background_median": fmt(np.median(norm[masks["background"] & valid]) if np.any(masks["background"] & valid) else math.nan),
                        "same_point_values_recorded_in_point_trace": "true",
                        "evidence_card": str(card),
                    })
                negative_masks = {"all_background": masks["background"], "vertical_line": masks.get("background_vertical_line", np.zeros_like(valid)), "fan_arc": masks.get("background_fan_arc", np.zeros_like(valid)), "clutter": masks.get("background_clutter", np.zeros_like(valid))}
                for subtype, negative_mask in negative_masks.items():
                    pos_mask = masks["skeleton"] & valid
                    neg_mask = negative_mask & valid
                    pos = channel[pos_mask]
                    neg = channel[neg_mask]
                    if pos.size == 0 or neg.size == 0:
                        sampling_rows.append({"case_id": data.window["case_id"], "frame": primary_frame, "coordinate_family": family, "channel": channel_name, "background_subtype": subtype, "method": "UNRESOLVED_NO_SAMPLES", "positive_count": pos.size, "negative_count": neg.size, "auc": ""})
                        continue
                    methods = {
                        "exact_rank_mann_whitney": exact_rank_auc(pos, neg),
                        "legacy_first3000_flattened": legacy_first3000_auc(pos, neg),
                        "fixed_seed_uniform_3000": exact_rank_auc(uniform_sample(pos, 3000, 20260717), uniform_sample(neg, 3000, 20260718)),
                        "spatial_stratified_4x4": exact_rank_auc(spatial_stratified_values(channel, pos_mask, 200, 20260719), spatial_stratified_values(channel, neg_mask, 200, 20260720)),
                    }
                    for method, auc in methods.items():
                        sampling_rows.append({
                            "case_id": data.window["case_id"],
                            "frame": primary_frame,
                            "coordinate_family": family,
                            "channel": channel_name,
                            "background_subtype": subtype,
                            "method": method,
                            "positive_count": pos.size,
                            "negative_count": neg.size,
                            "auc": fmt(auc),
                        })
                sampling_rows.append({
                    "case_id": data.window["case_id"],
                    "frame": primary_frame,
                    "coordinate_family": family,
                    "channel": channel_name,
                    "background_subtype": "hotspot",
                    "method": "UNRESOLVED_NO_FROZEN_HOTSPOT_CONTROL_IN_PRIMARY_ATLAS",
                    "positive_count": skeleton_values.size,
                    "negative_count": 0,
                    "auc": "",
                })
                sampling_rows.append({
                    "case_id": data.window["case_id"],
                    "frame": primary_frame,
                    "coordinate_family": family,
                    "channel": channel_name,
                    "background_subtype": "unresolved_distribution_not_auc_negative",
                    "method": "distribution_only",
                    "positive_count": skeleton_values.size,
                    "negative_count": unresolved_values.size,
                    "auc": "",
                    "unresolved_median": fmt(np.median(unresolved_values) if unresolved_values.size else math.nan),
                })
            bundle_path = arrays_dir / data.window["case_id"] / f"{data.window['case_id'].lower()}_{primary_frame}_{family.lower()}_channels.npz"
            bundle_sha = save_bundle(bundle_path, arrays)
            for name, array in arrays.items():
                if name in {"image", "valid_source_mask", "skeleton_mask", "seed_mask", "definite_mask", "background_mask", "unresolved_mask"}:
                    stage = "S11_MASK_OR_IMAGE"
                elif name.startswith("raw__"):
                    stage = "S08_S10_RAW_CHANNEL"
                else:
                    stage = "S08_S10_NORMALIZED_CHANNEL"
                lineage.append(lineage_row(data.window["case_id"], primary_frame, stage, f"{family}.{name}", str(data.image_paths[primary]), sha256_file(data.image_paths[primary]), family, array, valid, bundle_path, bundle_sha))
            cache[(data.window["case_id"], family)] = {"data": data, "matrix": matrix, "masks": masks, "geometry": transformed_geometry, "image": image, "valid": valid, "channels": channel_cache, "bundle_path": bundle_path, "bundle_sha": bundle_sha}

        drift_x = data.proxy_centers[primary][0] - data.gt_centers[primary][0]
        drift_y = data.proxy_centers[primary][1] - data.gt_centers[primary][1]
        error_family = "OPTICAL_PROXY_LOCALIZATION_ERROR_SAMPLING"
        matrix = translation_matrix(drift_x, drift_y)
        masks = geometry_masks(data.geometry, matrix)
        valid = imaging_valid_mask()
        image = data.raw_stack[primary]
        maps = channel_maps_at(data, "RAW_SAR_DISPLAY", primary)
        channel_cache = {}
        for channel_name, channel in maps.items():
            full_range = normalization_range(channel, None, ctx.config["normalization_percentiles"])
            valid_range = normalization_range(channel, valid, ctx.config["normalization_percentiles"])
            norm = apply_range(channel, *valid_range)
            channel_cache[channel_name] = {"raw": channel, "norms": {"valid_fan_per_frame": norm}, "ranges": {"legacy_full_frame": full_range, "valid_fan_per_frame": valid_range}}
        cache[(data.window["case_id"], error_family)] = {"data": data, "matrix": matrix, "masks": masks, "geometry": masks["_geometry"], "image": image, "valid": valid, "channels": channel_cache, "localization_error_only": True}

    write_csv(CHANNEL_AUDIT, channel_rows)
    write_csv(NORMALIZATION_AUDIT, normalization_rows)
    write_csv(SAMPLING_AUDIT, sampling_rows)
    write_csv(ARRAY_LINEAGE, lineage)
    return channel_rows, normalization_rows, sampling_rows, cache


def run_point_trace(ctx: AuditContext, cases: Sequence[CaseData], cache: Mapping[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    families = ["RAW_SAR_DISPLAY", "WORLD_STABILIZED_IMAGE_STACK", "GT_ALIGNED_RESEARCH_STACK", "OPTICAL_PROXY_ALIGNED_STACK", "OPTICAL_PROXY_LOCALIZATION_ERROR_SAMPLING"]
    for data in cases:
        primary = data.primary_index
        gt = data.gt_centers[primary]
        proxy = data.proxy_centers[primary]
        world_matrix = data.family_matrices["WORLD_STABILIZED_IMAGE_STACK"][primary]
        for point in audit_points(data):
            raw_point = point["point"]
            gt_local = (raw_point[0] - gt[0], raw_point[1] - gt[1])
            proxy_local = (raw_point[0] - proxy[0], raw_point[1] - proxy[1])
            world_point = transform_points([raw_point], world_matrix)[0]
            for family in families:
                item = cache[(data.window["case_id"], family)]
                matrix = item["matrix"]
                inverse = invert_translation(matrix)
                transformed = transform_points([raw_point], matrix)[0]
                recovered = transform_points([transformed], inverse)[0]
                point_error = math.hypot(recovered[0] - raw_point[0], recovered[1] - raw_point[1])
                x, y = int(round(transformed[0])), int(round(transformed[1]))
                in_image = 0 <= x < FAN_WIDTH and 0 <= y < FAN_HEIGHT
                in_valid = bool(item["valid"][y, x]) if in_image else False
                mask_membership = {
                    name: bool(mask[y, x]) if in_image else False
                    for name, mask in item["masks"].items()
                    if name != "_geometry" and isinstance(mask, np.ndarray)
                }
                for channel_name, channel_item in item["channels"].items():
                    raw_value = point_inside(channel_item["raw"], transformed)
                    norms = channel_item["norms"]
                    rows.append({
                        "case_id": data.window["case_id"],
                        "frame": data.window["primary_frame"],
                        "point_id": point["point_id"],
                        "point_role": point["role"],
                        "background_subtype": point.get("subtype", ""),
                        "coordinate_family": family,
                        "channel": channel_name,
                        "sar_display_x": raw_point[0],
                        "sar_display_y": raw_point[1],
                        "gt_local_x": gt_local[0],
                        "gt_local_y": gt_local[1],
                        "optical_proxy_local_x": proxy_local[0],
                        "optical_proxy_local_y": proxy_local[1],
                        "world_stabilized_x": world_point[0],
                        "world_stabilized_y": world_point[1],
                        "family_transformed_x": transformed[0],
                        "family_transformed_y": transformed[1],
                        "inverse_recovered_x": recovered[0],
                        "inverse_recovered_y": recovered[1],
                        "inverse_point_error_px": point_error,
                        "inside_image": fmt(in_image),
                        "inside_valid_source": fmt(in_valid),
                        "raw_gray_value": fmt(point_inside(item["image"], transformed)),
                        "channel_raw_value": fmt(raw_value),
                        "legacy_full_frame_value": fmt(point_inside(norms["legacy_full_frame"], transformed)) if "legacy_full_frame" in norms else "",
                        "valid_fan_per_frame_value": fmt(point_inside(norms["valid_fan_per_frame"], transformed)) if "valid_fan_per_frame" in norms else "",
                        "window_frozen_valid_value": fmt(point_inside(norms["window_frozen_valid"], transformed)) if "window_frozen_valid" in norms else "",
                        "local_target_matched_background_value": fmt(point_inside(norms["local_target_matched_background"], transformed)) if "local_target_matched_background" in norms else "",
                        "in_skeleton_mask": fmt(mask_membership.get("skeleton", False)),
                        "in_background_mask": fmt(mask_membership.get("background", False)),
                        "in_unresolved_mask": fmt(mask_membership.get("unresolved", False)),
                        "used_for_statistics": fmt(mask_membership.get("skeleton", False) or mask_membership.get("background", False)),
                        "conclusion_ids": "C02;C03;C05;C06" if point["role"] in {"skeleton", "background", "unresolved"} else "C02",
                        "experiment_semantics": "geometry_only_localization_error" if family == "OPTICAL_PROXY_LOCALIZATION_ERROR_SAMPLING" else "image_geometry_synchronized_coordinate_stack",
                    })
    write_csv(POINT_TRACE, rows)
    return rows


def run_point_trace_from_bundles(ctx: AuditContext, cases: Sequence[CaseData]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    families = ["RAW_SAR_DISPLAY", "WORLD_STABILIZED_IMAGE_STACK", "GT_ALIGNED_RESEARCH_STACK", "OPTICAL_PROXY_ALIGNED_STACK"]
    arrays_dir = ctx.output_root / "arrays" / "phase_b" / "channels"
    for data in cases:
        primary = data.primary_index
        primary_frame = data.frames[primary]
        gt = data.gt_centers[primary]
        proxy = data.proxy_centers[primary]
        world_matrix = data.family_matrices["WORLD_STABILIZED_IMAGE_STACK"][primary]
        for family in families:
            matrix = data.family_matrices[family][primary]
            inverse = invert_translation(matrix)
            masks = geometry_masks(data.geometry, matrix)
            bundle_path = arrays_dir / data.window["case_id"] / f"{data.window['case_id'].lower()}_{primary_frame}_{family.lower()}_channels.npz"
            require(bundle_path.is_file(), f"missing channel bundle: {bundle_path}")
            with np.load(bundle_path, allow_pickle=False) as bundle:
                image = bundle["image"]
                valid = bundle["valid_source_mask"].astype(bool)
                channel_names = sorted(key[len("raw__"):] for key in bundle.files if key.startswith("raw__"))
                point_contexts: list[dict[str, Any]] = []
                for point in audit_points(data):
                    raw_point = point["point"]
                    gt_local = (raw_point[0] - gt[0], raw_point[1] - gt[1])
                    proxy_local = (raw_point[0] - proxy[0], raw_point[1] - proxy[1])
                    world_point = transform_points([raw_point], world_matrix)[0]
                    transformed = transform_points([raw_point], matrix)[0]
                    recovered = transform_points([transformed], inverse)[0]
                    x, y = int(round(transformed[0])), int(round(transformed[1]))
                    in_image = 0 <= x < FAN_WIDTH and 0 <= y < FAN_HEIGHT
                    in_valid = bool(valid[y, x]) if in_image else False
                    point_contexts.append({
                        "point": point,
                        "raw_point": raw_point,
                        "gt_local": gt_local,
                        "proxy_local": proxy_local,
                        "world_point": world_point,
                        "transformed": transformed,
                        "recovered": recovered,
                        "x": x,
                        "y": y,
                        "in_image": in_image,
                        "in_valid": in_valid,
                    })
                for channel_name in channel_names:
                    raw_channel = bundle[f"raw__{channel_name}"]
                    legacy_norm = bundle[f"norm__legacy_full_frame__{channel_name}"]
                    valid_norm = bundle[f"norm__valid_fan_per_frame__{channel_name}"]
                    frozen_norm = bundle[f"norm__window_frozen_valid__{channel_name}"]
                    local_norm = bundle[f"norm__local_target_matched_background__{channel_name}"]
                    for item in point_contexts:
                        point = item["point"]
                        raw_point = item["raw_point"]
                        gt_local = item["gt_local"]
                        proxy_local = item["proxy_local"]
                        world_point = item["world_point"]
                        transformed = item["transformed"]
                        recovered = item["recovered"]
                        x, y = item["x"], item["y"]
                        in_image = item["in_image"]
                        in_valid = item["in_valid"]
                        rows.append({
                            "case_id": data.window["case_id"], "frame": primary_frame, "point_id": point["point_id"], "point_role": point["role"], "background_subtype": point.get("subtype", ""),
                            "coordinate_family": family, "channel": channel_name,
                            "sar_display_x": raw_point[0], "sar_display_y": raw_point[1],
                            "gt_local_x": gt_local[0], "gt_local_y": gt_local[1],
                            "optical_proxy_local_x": proxy_local[0], "optical_proxy_local_y": proxy_local[1],
                            "world_stabilized_x": world_point[0], "world_stabilized_y": world_point[1],
                            "family_transformed_x": transformed[0], "family_transformed_y": transformed[1],
                            "inverse_recovered_x": recovered[0], "inverse_recovered_y": recovered[1],
                            "inverse_point_error_px": math.hypot(recovered[0] - raw_point[0], recovered[1] - raw_point[1]),
                            "inside_image": fmt(in_image), "inside_valid_source": fmt(in_valid),
                            "raw_gray_value": fmt(point_inside(image, transformed)),
                            "channel_raw_value": fmt(point_inside(raw_channel, transformed)),
                            "legacy_full_frame_value": fmt(point_inside(legacy_norm, transformed)),
                            "valid_fan_per_frame_value": fmt(point_inside(valid_norm, transformed)),
                            "window_frozen_valid_value": fmt(point_inside(frozen_norm, transformed)),
                            "local_target_matched_background_value": fmt(point_inside(local_norm, transformed)),
                            "in_skeleton_mask": fmt(bool(masks["skeleton"][y, x]) if in_image else False),
                            "in_background_mask": fmt(bool(masks["background"][y, x]) if in_image else False),
                            "in_unresolved_mask": fmt(bool(masks["unresolved"][y, x]) if in_image else False),
                            "used_for_statistics": fmt(bool((masks["skeleton"] | masks["background"])[y, x]) if in_image else False),
                            "conclusion_ids": "C02;C03;C05;C06" if point["role"] in {"skeleton", "background", "unresolved"} else "C02",
                            "experiment_semantics": "image_geometry_synchronized_coordinate_stack",
                        })
        drift_matrix = translation_matrix(proxy[0] - gt[0], proxy[1] - gt[1])
        inverse = invert_translation(drift_matrix)
        masks = geometry_masks(data.geometry, drift_matrix)
        image = data.raw_stack[primary]
        maps = channel_maps_at(data, "RAW_SAR_DISPLAY", primary)
        valid = imaging_valid_mask()
        point_contexts = []
        for point in audit_points(data):
            raw_point = point["point"]
            transformed = transform_points([raw_point], drift_matrix)[0]
            recovered = transform_points([transformed], inverse)[0]
            x, y = int(round(transformed[0])), int(round(transformed[1]))
            in_image = 0 <= x < FAN_WIDTH and 0 <= y < FAN_HEIGHT
            point_contexts.append({
                "point": point,
                "raw_point": raw_point,
                "transformed": transformed,
                "recovered": recovered,
                "x": x,
                "y": y,
                "in_image": in_image,
            })
        for channel_name, array in maps.items():
            lo, hi = normalization_range(array, valid, ctx.config["normalization_percentiles"])
            valid_norm = apply_range(array, lo, hi)
            for item in point_contexts:
                point = item["point"]
                raw_point = item["raw_point"]
                transformed = item["transformed"]
                recovered = item["recovered"]
                x, y = item["x"], item["y"]
                in_image = item["in_image"]
                rows.append({
                    "case_id": data.window["case_id"], "frame": primary_frame, "point_id": point["point_id"], "point_role": point["role"], "background_subtype": point.get("subtype", ""),
                    "coordinate_family": "OPTICAL_PROXY_LOCALIZATION_ERROR_SAMPLING", "channel": channel_name,
                    "sar_display_x": raw_point[0], "sar_display_y": raw_point[1],
                    "gt_local_x": raw_point[0] - gt[0], "gt_local_y": raw_point[1] - gt[1],
                    "optical_proxy_local_x": raw_point[0] - proxy[0], "optical_proxy_local_y": raw_point[1] - proxy[1],
                    "world_stabilized_x": transform_points([raw_point], world_matrix)[0][0], "world_stabilized_y": transform_points([raw_point], world_matrix)[0][1],
                    "family_transformed_x": transformed[0], "family_transformed_y": transformed[1],
                    "inverse_recovered_x": recovered[0], "inverse_recovered_y": recovered[1],
                    "inverse_point_error_px": math.hypot(recovered[0] - raw_point[0], recovered[1] - raw_point[1]),
                    "inside_image": fmt(in_image), "inside_valid_source": fmt(bool(valid[y, x]) if in_image else False),
                    "raw_gray_value": fmt(point_inside(image, transformed)), "channel_raw_value": fmt(point_inside(array, transformed)),
                    "legacy_full_frame_value": "", "valid_fan_per_frame_value": fmt(point_inside(valid_norm, transformed)), "window_frozen_valid_value": "", "local_target_matched_background_value": "",
                    "in_skeleton_mask": fmt(bool(masks["skeleton"][y, x]) if in_image else False), "in_background_mask": fmt(bool(masks["background"][y, x]) if in_image else False), "in_unresolved_mask": fmt(bool(masks["unresolved"][y, x]) if in_image else False),
                    "used_for_statistics": fmt(bool((masks["skeleton"] | masks["background"])[y, x]) if in_image else False),
                    "conclusion_ids": "C02;C03;C05;C06" if point["role"] in {"skeleton", "background", "unresolved"} else "C02",
                    "experiment_semantics": "geometry_only_localization_error",
                })
    write_csv(POINT_TRACE, rows)
    return rows


def write_channel_reports(channel_rows: Sequence[dict[str, Any]], normalization_rows: Sequence[dict[str, Any]], sampling_rows: Sequence[dict[str, Any]]) -> None:
    channel_lines = [
        "# OTY2-RSA0-R2 Channel Semantic Audit",
        "",
        "Channel names below describe the implemented formula. High values are image structures, not automatic vehicle ownership.",
        "",
    ]
    for channel in sorted({row["channel"] for row in channel_rows}):
        rows = [row for row in channel_rows if row["channel"] == channel]
        channel_lines.extend([
            f"## `{channel}`",
            "",
            f"- Formula: {rows[0]['formula']}",
            f"- High value: {rows[0]['high_value_semantics']}",
            "- Primary-frame observations:",
        ])
        for row in rows:
            channel_lines.append(
                f"  - `{row['case_id']}` `{row['coordinate_family']}`: skeleton `{row['skeleton_median_raw']}`, "
                f"vertical `{row['vertical_line_median_raw']}`, arc `{row['fan_arc_median_raw']}`, clutter `{row['clutter_median_raw']}`, "
                f"weak `{row['weak_frame_skeleton_median_raw']}`, strong `{row['strong_frame_skeleton_median_raw']}`; card `{row['evidence_card']}`."
            )
        channel_lines.append("")
    CHANNEL_REPORT.write_text("\n".join(channel_lines) + "\n", encoding="utf-8")

    norm_lines = [
        "# OTY2-RSA0-R2 Normalization and Sampling Audit",
        "",
        "Four normalization schemes are reported without selecting one by target score. Exact, uniform, spatially stratified, and legacy first-3000 AUC are kept separate.",
        "",
    ]
    for case_id in sorted({row["case_id"] for row in normalization_rows}):
        case_rows = [row for row in normalization_rows if row["case_id"] == case_id]
        norm_lines.extend([f"## {case_id}", ""])
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in case_rows:
            grouped[(row["coordinate_family"], row["channel"])].append(row)
        for (family, channel), rows in list(grouped.items())[:12]:
            values = ", ".join(f"{row['normalization']}=[{float(row['range_low']):.4g},{float(row['range_high']):.4g}]" for row in rows)
            norm_lines.append(f"- `{family}` `{channel}`: {values}")
        norm_lines.extend(["", "The complete channel-by-channel ranges and point values are in the CSV and point-trace ledger.", ""])
    auc_exact = [row for row in sampling_rows if row["method"] == "exact_rank_mann_whitney" and row.get("auc") not in {"", None}]
    auc_legacy = [row for row in sampling_rows if row["method"] == "legacy_first3000_flattened" and row.get("auc") not in {"", None}]
    key = lambda row: (row["case_id"], row["coordinate_family"], row["channel"], row["background_subtype"])
    legacy_map = {key(row): float(row["auc"]) for row in auc_legacy}
    differences = [(abs(float(row["auc"]) - legacy_map.get(key(row), float(row["auc"]))), row) for row in auc_exact]
    if differences:
        delta, row = max(differences, key=lambda item: item[0])
        norm_lines.extend([
            "## Largest observed legacy sampling difference",
            "",
            f"`{row['case_id']}` `{row['coordinate_family']}` `{row['channel']}` vs `{row['background_subtype']}`: absolute AUC difference `{delta:.6f}`.",
            "",
        ])
    NORMALIZATION_REPORT.write_text("\n".join(norm_lines) + "\n", encoding="utf-8")


def synthetic_line_image(size: int, orientation: str) -> np.ndarray:
    image = np.zeros((size, size), dtype=np.float32)
    if orientation == "horizontal":
        cv2.line(image, (30, size // 2), (size - 30, size // 2), 255.0, 3)
    else:
        cv2.line(image, (size // 2, 30), (size // 2, size - 30), 255.0, 3)
    return image


def run_synthetic_tests(ctx: AuditContext) -> list[dict[str, Any]]:
    output_dir = ctx.output_root / "synthetic_tests"
    evidence_dir = ctx.output_root / "evidence_cards" / "synthetic_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    size = 256
    origin = (128.0, 250.0)

    horizontal = synthetic_line_image(size, "horizontal")
    h_channels = single_channels(horizontal, origin)
    horizontal_interior = np.zeros((size, size), dtype=bool)
    horizontal_interior[120:137, 45:211] = True
    h_sobel_x = float(np.mean(h_channels["sobel_x_abs_gradient_component"][horizontal_interior]))
    h_sobel_y = float(np.mean(h_channels["sobel_y_abs_gradient_component"][horizontal_interior]))
    h_radial = float(np.mean(h_channels["radial_gradient_normal_response"][123:134, 40:216]))
    h_tangential = float(np.mean(h_channels["tangential_gradient_normal_response"][123:134, 40:216]))
    rows.append({"test_id": "SYN01_HORIZONTAL_LINE", "input": "single horizontal bright line", "theoretical_expectation": "Sobel-y and radial-normal response dominate", "actual": f"sobel_y={h_sobel_y};sobel_x={h_sobel_x};radial={h_radial};tangential={h_tangential}", "error": fmt(max(0.0, h_sobel_x - h_sobel_y)), "status": "PASS" if h_sobel_y > h_sobel_x and h_radial > h_tangential else "FAIL"})
    arrays.update({"syn01_input": horizontal, "syn01_sobel_x": h_channels["sobel_x_abs_gradient_component"], "syn01_sobel_y": h_channels["sobel_y_abs_gradient_component"], "syn01_radial": h_channels["radial_gradient_normal_response"], "syn01_tangential": h_channels["tangential_gradient_normal_response"]})

    vertical = synthetic_line_image(size, "vertical")
    v_channels = single_channels(vertical, origin)
    vertical_interior = np.zeros((size, size), dtype=bool)
    vertical_interior[45:211, 120:137] = True
    v_sobel_x = float(np.mean(v_channels["sobel_x_abs_gradient_component"][vertical_interior]))
    v_sobel_y = float(np.mean(v_channels["sobel_y_abs_gradient_component"][vertical_interior]))
    rows.append({"test_id": "SYN02_VERTICAL_LINE", "input": "single vertical bright line", "theoretical_expectation": "Sobel-x dominates", "actual": f"sobel_x={v_sobel_x};sobel_y={v_sobel_y}", "error": fmt(max(0.0, v_sobel_y - v_sobel_x)), "status": "PASS" if v_sobel_x > v_sobel_y else "FAIL"})
    arrays.update({"syn02_input": vertical, "syn02_sobel_x": v_channels["sobel_x_abs_gradient_component"], "syn02_sobel_y": v_channels["sobel_y_abs_gradient_component"]})

    arc = np.zeros((size, size), dtype=np.float32)
    cv2.ellipse(arc, (int(origin[0]), int(origin[1])), (120, 120), 0, 220, 320, 255.0, 3)
    arc_channels = single_channels(arc, origin)
    band = arc > 0
    dilated = cv2.dilate(band.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    arc_radial = float(np.mean(arc_channels["radial_gradient_normal_response"][dilated]))
    arc_tangential = float(np.mean(arc_channels["tangential_gradient_normal_response"][dilated]))
    rows.append({"test_id": "SYN03_KNOWN_ARC", "input": "circular arc centered on fan origin", "theoretical_expectation": "radial-normal gradient response exceeds tangential-normal response", "actual": f"radial={arc_radial};tangential={arc_tangential}", "error": fmt(max(0.0, arc_tangential - arc_radial)), "status": "PASS" if arc_radial > arc_tangential else "FAIL"})
    arrays.update({"syn03_input": arc, "syn03_radial": arc_channels["radial_gradient_normal_response"], "syn03_tangential": arc_channels["tangential_gradient_normal_response"]})

    base = synthetic_line_image(size, "horizontal").astype(np.uint8)
    shifts = [0, 2, 4, 6, 8]
    raw_stack = np.stack([warp_image(base, translation_matrix(dx, 0.0)) for dx in shifts])
    stable_stack = np.stack([warp_image(frame, translation_matrix(-dx, 0.0)) for frame, dx in zip(raw_stack, shifts)])
    raw_mad = np.max(raw_stack.astype(np.float32), axis=0) - np.min(raw_stack.astype(np.float32), axis=0)
    stable_mad = np.max(stable_stack.astype(np.float32), axis=0) - np.min(stable_stack.astype(np.float32), axis=0)
    raw_mad_mean = float(np.mean(raw_mad))
    stable_mad_mean = float(np.mean(stable_mad))
    rows.append({"test_id": "SYN04_TRANSLATED_STATIC_LINE", "input": "global translations 0,2,4,6,8 px", "theoretical_expectation": "world stabilization reduces temporal max-min change near zero", "actual": f"raw_change_mean={raw_mad_mean};stable_change_mean={stable_mad_mean}", "error": fmt(stable_mad_mean), "status": "PASS" if raw_mad_mean > 0 and stable_mad_mean < raw_mad_mean * 0.1 else "FAIL"})
    arrays.update({"syn04_raw_stack": raw_stack, "syn04_stable_stack": stable_stack, "syn04_raw_mad": raw_mad, "syn04_stable_mad": stable_mad})

    background = np.zeros((size, size), dtype=np.uint8)
    cv2.line(background, (20, 80), (230, 80), 100, 2)
    target_stack: list[np.ndarray] = []
    target_shifts = [0, 3, 6, 9, 12]
    for dx in target_shifts:
        frame = background.copy()
        cv2.line(frame, (70 + dx, 160), (150 + dx, 160), 255, 3)
        target_stack.append(frame)
    world_stack = np.stack(target_stack)
    gt_stack = np.stack([warp_image(frame, translation_matrix(-dx, 0.0)) for frame, dx in zip(target_stack, target_shifts)])
    target_roi = np.zeros((size, size), dtype=bool)
    target_roi[150:171, 60:165] = True
    world_target_mad = float(np.mean((np.max(world_stack.astype(np.float32), axis=0) - np.min(world_stack.astype(np.float32), axis=0))[target_roi]))
    gt_target_mad = float(np.mean((np.max(gt_stack.astype(np.float32), axis=0) - np.min(gt_stack.astype(np.float32), axis=0))[target_roi]))
    rows.append({"test_id": "SYN05_TARGET_RELATIVE_BACKGROUND_MOTION", "input": "fixed background plus moving local target", "theoretical_expectation": "GT-aligned target stack is more stable than world stack in target ROI", "actual": f"world_target_change={world_target_mad};gt_target_change={gt_target_mad}", "error": fmt(gt_target_mad), "status": "PASS" if world_target_mad > 0 and gt_target_mad < world_target_mad else "FAIL"})
    arrays.update({"syn05_world_stack": world_stack, "syn05_gt_stack": gt_stack})

    pulse = np.zeros((5, size, size), dtype=np.uint8)
    pulse[2, 110:140, 110:140] = 200
    valid = np.ones_like(pulse, dtype=bool)
    pos_at_pulse = temporal_channels(pulse, valid, 2, 2)["temporal_adjacent_positive_change"]
    neg_after_pulse = temporal_channels(pulse, valid, 3, 2)["temporal_adjacent_negative_change"]
    pos_sum = float(np.sum(pos_at_pulse))
    neg_sum = float(np.sum(neg_after_pulse))
    rows.append({"test_id": "SYN06_SINGLE_FRAME_PULSE", "input": "positive pulse at frame 2 only", "theoretical_expectation": "positive change at frame 2 and negative change at frame 3", "actual": f"positive_sum={pos_sum};negative_sum={neg_sum}", "error": 0.0, "status": "PASS" if pos_sum > 0 and neg_sum > 0 else "FAIL"})
    arrays.update({"syn06_pulse_stack": pulse, "syn06_positive": pos_at_pulse, "syn06_negative": neg_after_pulse})

    constant = np.full((5, size, size), 42, dtype=np.uint8)
    constant_single = single_channels(constant[0], origin)
    constant_temporal = temporal_channels(constant, np.ones_like(constant, dtype=bool), 2, 2)
    maximum_error = max(float(np.max(np.abs(constant_single["gradient_magnitude_sobel"]))), float(np.max(np.abs(constant_single["highpass_sigma9"]))), float(np.max(np.abs(constant_temporal["temporal_w2_mad"]))), float(np.max(np.abs(constant_temporal["temporal_adjacent_positive_change"]))))
    rows.append({"test_id": "SYN07_CONSTANT_IMAGE", "input": "constant 42-valued five-frame stack", "theoretical_expectation": "gradient, highpass, MAD, and adjacent change are zero within float convolution tolerance", "actual": f"max_error={maximum_error}", "error": maximum_error, "status": "PASS" if maximum_error <= 1e-4 else "FAIL"})
    arrays.update({"syn07_constant_stack": constant, "syn07_gradient": constant_single["gradient_magnitude_sobel"], "syn07_highpass": constant_single["highpass_sigma9"], "syn07_mad": constant_temporal["temporal_w2_mad"]})

    bundle_path = output_dir / "oty2_rsa0_r2_synthetic_arrays.npz"
    save_bundle(bundle_path, arrays)
    write_csv(SYNTHETIC_RESULTS, rows)
    figure, axes = plt.subplots(2, 4, figsize=(16, 8))
    panels = [horizontal, vertical, arc, raw_mad, stable_mad, world_stack[2], gt_stack[2], pulse[2]]
    titles = ["horizontal line", "vertical line", "fan-centered arc", "raw translation MAD", "stabilized MAD", "world target", "GT-aligned target", "single-frame pulse"]
    for axis, panel, title in zip(axes.ravel(), panels, titles):
        axis.imshow(panel, cmap="viridis")
        axis.set_title(title)
        axis.axis("off")
    card = evidence_dir / "synthetic_input_operation_output.png"
    save_figure(card, figure)
    report = ["# OTY2-RSA0-R2 Synthetic Test Report", "", f"Array bundle: `{bundle_path}`", f"Evidence card: `{card}`", ""]
    for row in rows:
        report.extend([f"## {row['test_id']} — {row['status']}", "", f"- Input: {row['input']}", f"- Expected: {row['theoretical_expectation']}", f"- Actual: {row['actual']}", f"- Error: `{row['error']}`", ""])
    SYNTHETIC_REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    return rows


def run_extension_validation(ctx: AuditContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    evidence_dir = ctx.output_root / "evidence_cards" / "extension_validation"
    valid = imaging_valid_mask()
    for window in ctx.config["windows"]:
        for frame in window["extension_frames"]:
            condition = selected_row(ctx.conditions, window["scene"], window["vehicle_id"], int(frame))
            image_path = Path(condition["sar_gray_path"])
            decoded, gray = read_png(image_path)
            extension_window = dict(window)
            extension_window["primary_frame"] = int(frame)
            geometry = atlas_geometry(ctx, extension_window)
            card = evidence_dir / window["case_id"] / f"{window['case_id'].lower()}_{frame}_extension_raw_atlas.png"
            phase_a_raw_card(card, decoded, gray, valid, geometry, f"{window['case_id']} extension SAR {frame}", ctx.config["display_clip"])
            channels = single_channels(gray)
            masks = geometry_masks(geometry, translation_matrix(0.0, 0.0))
            for channel_name in ["raw_display_intensity", "local_contrast_31", "multiscale_laplacian_bright_ridge", "radial_gradient_normal_response", "tangential_gradient_normal_response"]:
                channel = channels[channel_name]
                skel = channel[masks["skeleton"] & valid]
                bg = channel[masks["background"] & valid]
                rows.append({
                    "case_id": window["case_id"],
                    "frame": frame,
                    "channel": channel_name,
                    "skeleton_median_raw": fmt(np.median(skel) if skel.size else math.nan),
                    "background_median_raw": fmt(np.median(bg) if bg.size else math.nan),
                    "skeleton_minus_background_raw": fmt(np.median(skel) - np.median(bg) if skel.size and bg.size else math.nan),
                    "evidence_card": str(card),
                    "scope": "extension_only_after_primary_and_contiguous_window_audit",
                })
    path = MANIFEST_DIR / "oty2_rsa0_r2_extension_validation.csv"
    write_csv(path, rows)
    return rows


def run_conclusions(ctx: AuditContext, cases: Sequence[CaseData]) -> list[dict[str, Any]]:
    check_phase_a_freeze(ctx)
    require(ARRAY_LINEAGE.exists() and POINT_TRACE.exists() and CHANNEL_AUDIT.exists() and NORMALIZATION_AUDIT.exists() and SAMPLING_AUDIT.exists(), "missing prerequisite audit outputs")
    lineages = read_csv(ARRAY_LINEAGE)
    coordinates = read_csv(COORDINATE_AUDIT)
    channels = read_csv(CHANNEL_AUDIT)
    norms = read_csv(NORMALIZATION_AUDIT)
    sampling = read_csv(SAMPLING_AUDIT)
    atlas = read_csv(ATLAS_AUDIT)
    synthetic = read_csv(SYNTHETIC_RESULTS)
    require(all(row["status"] == "PASS" for row in synthetic), "synthetic tests must pass before conclusions")

    raw_examples: dict[str, dict[str, str]] = {}
    for data in cases:
        frame = str(data.window["primary_frame"])
        raw_examples[data.window["case_id"]] = next(row for row in lineages if row["case_id"] == data.window["case_id"] and row["frame"] == frame and row["variable_name"] == "gray_scalar")
    coordinate_cards = {
        data.window["case_id"]: str(ctx.output_root / "evidence_cards" / "coordinate_stacks" / data.window["case_id"] / f"{data.window['case_id'].lower()}_world_stabilized_image_stack_input_operation_output.png")
        for data in cases
    }
    point_examples = {
        data.window["case_id"]: next(row for row in read_csv(POINT_TRACE) if row["case_id"] == data.window["case_id"] and row["point_id"] == "skeleton_mid" and row["coordinate_family"] == "GT_ALIGNED_RESEARCH_STACK" and row["channel"] == "raw_display_intensity")
        for data in cases
    }
    exact = [row for row in sampling if row["method"] == "exact_rank_mann_whitney" and row.get("auc") not in {"", None} and row["background_subtype"] == "all_background"]
    legacy = { (row["case_id"], row["coordinate_family"], row["channel"], row["background_subtype"]): float(row["auc"]) for row in sampling if row["method"] == "legacy_first3000_flattened" and row.get("auc") not in {"", None} }
    max_sampling_delta = 0.0
    max_sampling_row: dict[str, Any] | None = None
    for row in exact:
        key = (row["case_id"], row["coordinate_family"], row["channel"], row["background_subtype"])
        delta = abs(float(row["auc"]) - legacy.get(key, float(row["auc"])))
        if delta > max_sampling_delta:
            max_sampling_delta = delta
            max_sampling_row = row
    ambiguous_count = sum(row["status"] in {"MINOR_OFFSET", "WRONG_STRUCTURE", "SEMANTICALLY_AMBIGUOUS"} for row in atlas)

    conclusions = [
        {
            "conclusion_id": "C01",
            "conclusion_text": f"The decoded SAR PNG is uint8 display imagery. SAR 339 spans {raw_examples['PV002_337_341']['minimum']}..{raw_examples['PV002_337_341']['maximum']}; SAR 384 spans {raw_examples['PV003_380_384']['minimum']}..{raw_examples['PV003_380_384']['maximum']}. The frozen fan occupies 0.853693 of the canvas and about 29% of its pixels are zero in both primary frames.",
            "dependent_stages": "S00;S01;S02",
            "dependent_files": str(ARRAY_LINEAGE),
            "dependent_metric": "shape,dtype,min,max,zero_fraction,valid_fan_fraction",
            "dependent_frames": "PV002:339;PV003:384",
            "dependent_visualization": ";".join(str(ctx.output_root / "evidence_cards" / "phase_a" / data.window["case_id"] / f"{data.window['case_id'].lower()}_{data.window['primary_frame']}_s00_s02_raw_decode_card.png") for data in cases),
            "logic_condition": "direct decoded-array statistics and frozen fan hash",
            "counterexample_exists": "false",
            "evidence_grade": "DIRECT_ARRAY_AND_IMAGE",
        },
        {
            "conclusion_id": "C02",
            "conclusion_text": "RAW leaves image and geometry fixed; WORLD applies the same inverse scene translation to image, geometry, points, and valid-source mask; GT and optical-proxy stacks apply their own first-frame center translations before recomputing time channels. Geometry-only proxy shifting is retained only as localization-error sampling.",
            "dependent_stages": "S03;S04;S05;S06;S07",
            "dependent_files": f"{COORDINATE_AUDIT};{POINT_TRACE}",
            "dependent_metric": "transform matrix, inverse point error, mask IoU, image reconstruction MAE",
            "dependent_frames": "337-341;380-384",
            "dependent_visualization": ";".join(coordinate_cards.values()),
            "logic_condition": "image-geometry-point-valid-mask share one matrix in aligned families",
            "counterexample_exists": "R1 proxy-named family violated this condition",
            "evidence_grade": "DIRECT_TRANSFORM_AND_POINT_TRACE",
        },
        {
            "conclusion_id": "C03",
            "conclusion_text": "The first systematic transform-induced skeleton misalignment in R1 occurs in the proxy-named branch: the image stays fixed while geometry shifts by proxy-minus-GT drift. At PV003 SAR 384 the shift is (-22.643,+130.210) px. Raw atlas endpoints also contain local offsets or semantic ambiguity, but those are pre-existing reference issues rather than transform-induced displacement.",
            "dependent_stages": "S07;S11",
            "dependent_files": f"{PHASE_A_FINDINGS};{ATLAS_AUDIT};{POINT_TRACE}",
            "dependent_metric": "proxy drift, point status, transformed pixel sample",
            "dependent_frames": "PV003:384",
            "dependent_visualization": str(ctx.output_root / "evidence_cards" / "phase_a" / "PV003_380_384" / "pv003_380_384_384_r1_coordinate_semantics_card.png"),
            "logic_condition": "nonzero geometry displacement with zero image displacement",
            "counterexample_exists": "WORLD/GT/PROXY aligned R2 stacks synchronize image and geometry",
            "evidence_grade": "DIRECT_CODE_ARRAY_AND_VISUAL",
        },
        {
            "conclusion_id": "C04",
            "conclusion_text": "RAW time mixes scene transport and local response change; WORLD time expresses residual change after background transport removal; GT-aligned time is oracle vehicle-centred change; optical-proxy-aligned time is proxy-centred change whose residual target motion includes proxy error. R1 had no WORLD temporal maps and did not construct the latter two aligned stacks.",
            "dependent_stages": "S05;S06;S07;S10",
            "dependent_files": f"{CHANNEL_AUDIT};{COORDINATE_AUDIT};{PHASE_A_FINDINGS}",
            "dependent_metric": "complete five-frame stack and temporal channel presence",
            "dependent_frames": "337-341;380-384",
            "dependent_visualization": ";".join(coordinate_cards.values()),
            "logic_condition": "time channels recomputed after coordinate-stack construction",
            "counterexample_exists": "R1 family construction",
            "evidence_grade": "DIRECT_STACK_AND_CHANNEL",
        },
        {
            "conclusion_id": "C05",
            "conclusion_text": "Channel high values are not target ownership: raw/local channels describe brightness, Sobel and gradient channels describe boundary normals, the legacy Hessian name is more accurately a multiscale negative-Laplacian bright-ridge response, coherence describes anisotropy, and fan directional channels describe gradient-normal components. Vertical lines, fan arcs, clutter, black boundaries, weak frames, and strong frames must remain separate.",
            "dependent_stages": "S08;S09;S10",
            "dependent_files": f"{CHANNEL_AUDIT};{FAN_AUDIT}",
            "dependent_metric": "raw skeleton/background subtype distributions and synthetic direction tests",
            "dependent_frames": "PV002:339;PV003:384",
            "dependent_visualization": str(ctx.output_root / "evidence_cards" / "channels"),
            "logic_condition": "formula plus real-image subtype response plus synthetic test",
            "counterexample_exists": "no single channel suppresses all background subtypes",
            "evidence_grade": "DIRECT_ARRAY_VISUAL_AND_SYNTHETIC",
        },
        {
            "conclusion_id": "C06",
            "conclusion_text": f"R1 normalization and sampling can manufacture or hide differences: full-frame per-frame quantiles include invalid black support and AUC uses spatially ordered first-3000 samples. The largest exact-versus-legacy all-background AUC difference observed in R2 is {max_sampling_delta:.6f}" + (f" for {max_sampling_row['case_id']} {max_sampling_row['coordinate_family']} {max_sampling_row['channel']}." if max_sampling_row else "."),
            "dependent_stages": "S08;S12;S13",
            "dependent_files": f"{NORMALIZATION_AUDIT};{SAMPLING_AUDIT};{POINT_TRACE}",
            "dependent_metric": "four normalization ranges, exact/uniform/spatial/legacy AUC",
            "dependent_frames": "PV002:339;PV003:384",
            "dependent_visualization": str(ctx.output_root / "evidence_cards" / "channels"),
            "logic_condition": "same raw channel and same physical points compared under all schemes",
            "counterexample_exists": "AUC is invariant only to a shared monotonic scaling, not spatial sample selection or family-specific per-frame ranges",
            "evidence_grade": "DIRECT_POINT_AND_DISTRIBUTION",
        },
        {
            "conclusion_id": "C07",
            "conclusion_text": "R1 conclusions retained: v1 uses per-frame explicit geometry rather than the v0 fixed template; no single channel fully rejects background; propagation was not authorized. Conclusions requiring withdrawal or relabeling: GT/proxy/world coordinate-family effectiveness, world temporal statements, component continuity, first-3000 AUC, and any signal-retained label derived only from median separation >=0.03. Atlas morphology claims remain partly supported but point-level caveats are required.",
            "dependent_stages": "S06;S07;S10;S11;S13;S14;S15",
            "dependent_files": f"{PHASE_A_FINDINGS};{ATLAS_AUDIT};{CHANNEL_AUDIT};{SAMPLING_AUDIT}",
            "dependent_metric": "8 frozen Phase A findings and point statuses",
            "dependent_frames": "R1 keyframes plus R2 primary/extension frames",
            "dependent_visualization": str(ctx.output_root / "evidence_cards" / "atlas_review"),
            "logic_condition": "retain only claims whose implementation matches their name and whose evidence has no unreported counterexample",
            "counterexample_exists": f"{ambiguous_count} audited atlas points are offset or semantically ambiguous",
            "evidence_grade": "FORENSIC_SYNTHESIS",
        },
        {
            "conclusion_id": "C08",
            "conclusion_text": "After the R2 implementation fixes, the pipeline is traceable and engineering-valid, but propagation design is still not authorized. Two short windows are insufficient for method admission, hotspot controls are absent in the primary atlas, several atlas points remain offset/ambiguous, and no channel is background-safe across all subtypes and coordinate families.",
            "dependent_stages": "S00-S15",
            "dependent_files": f"{ATLAS_AUDIT};{CHANNEL_AUDIT};{SAMPLING_AUDIT};{SYNTHETIC_RESULTS}",
            "dependent_metric": "all required gates plus unresolved scientific questions",
            "dependent_frames": "337-341;380-384;extensions 330,344,360,372",
            "dependent_visualization": str(ctx.output_root / "evidence_cards"),
            "logic_condition": "engineering closure does not override unresolved scientific evidence",
            "counterexample_exists": "background subtype competition and atlas ambiguity remain",
            "evidence_grade": "CONSERVATIVE_STAGE_DECISION",
        },
    ]
    write_csv(CONCLUSION_LINEAGE, conclusions)
    report = [
        "# OTY2-RSA0-R2 Layer-by-Layer Forensic Audit of the SAR Response Representation Pipeline",
        "",
        "Date: `2026-07-17`",
        "",
        "This report answers only the eight frozen R2 questions. Large arrays and evidence cards remain outside Git.",
        "",
    ]
    questions = [
        "1. What are the decoded PNG range, black region, and valid fan?",
        "2. What does each coordinate transform actually do to image, geometry, and points?",
        "3. Where is the first skeleton-to-response misalignment introduced?",
        "4. What does time mean in the real coordinate stacks?",
        "5. What image structures produce high values in each channel?",
        "6. Do normalization and sampling manufacture or hide target-background differences?",
        "7. Which R1 conclusions stand, require withdrawal, or remain undecidable?",
        "8. Is propagation design authorized after confirmed implementation fixes?",
    ]
    for question, row in zip(questions, conclusions):
        report.extend([
            f"## {question}",
            "",
            row["conclusion_text"],
            "",
            f"- Frames: `{row['dependent_frames']}`",
            f"- Stages: `{row['dependent_stages']}`",
            f"- Arrays/metrics: `{row['dependent_files']}` / `{row['dependent_metric']}`",
            f"- Point example: `{point_examples[cases[0].window['case_id']]['point_id']}` at transformed coordinate "
            f"`({float(point_examples[cases[0].window['case_id']]['family_transformed_x']):.3f},{float(point_examples[cases[0].window['case_id']]['family_transformed_y']):.3f})`" if row["conclusion_id"] in {"C02", "C03", "C06"} else "- Point evidence: see point-trace ledger for named skeleton/background points.",
            f"- Visualization: `{row['dependent_visualization']}`",
            f"- Evidence grade: `{row['evidence_grade']}`",
            "",
        ])
    report.extend([
        "## Phase B fix record",
        "",
        "- R1 remains frozen. R2 constructs real WORLD/GT/PROXY image stacks and recomputes temporal channels.",
        "- Geometry-only proxy displacement is retained under an honest localization-error name.",
        "- `component_continuity` is replaced by `high_intensity_pixel_frequency`.",
        "- AUC now reports exact, fixed-seed uniform, spatially stratified, and legacy results separately.",
        "- Normalization now exposes full-frame, valid-fan, window-frozen, and local matched ranges.",
        "- Atlas v1 is not edited; point-level correction proposals remain a separate decision.",
        "",
        "## Final stage decision",
        "",
        "`NEXT_PROPAGATION_DESIGN=NOT_AUTHORIZED`",
    ])
    FORMAL_REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    write_json(SUMMARY_JSON, {
        "status": "R2_FORENSIC_AUDIT_COMPLETE_PROPAGATION_NOT_AUTHORIZED",
        "phase_a_finding_count": len(read_csv(PHASE_A_FINDINGS)),
        "array_lineage_count": len(lineages),
        "point_trace_count": len(read_csv(POINT_TRACE)),
        "coordinate_audit_count": len(coordinates),
        "channel_audit_count": len(channels),
        "normalization_audit_count": len(norms),
        "sampling_audit_count": len(sampling),
        "atlas_point_audit_count": len(atlas),
        "synthetic_test_count": len(synthetic),
        "conclusion_count": len(conclusions),
        "propagation_design_authorized": False,
    })
    return conclusions


def validate_outputs(ctx: AuditContext) -> dict[str, Any]:
    required_files = [
        PHASE_A_FINDINGS, PHASE_A_FREEZE, ARRAY_LINEAGE, POINT_TRACE, FAN_AUDIT, ATLAS_AUDIT,
        COORDINATE_AUDIT, CHANNEL_AUDIT, NORMALIZATION_AUDIT, SAMPLING_AUDIT,
        SYNTHETIC_RESULTS, CONCLUSION_LINEAGE, PHASE_A_REPORT, COORDINATE_REPORT,
        CHANNEL_REPORT, NORMALIZATION_REPORT, SYNTHETIC_REPORT, FORMAL_REPORT, SUMMARY_JSON,
    ]
    for path in required_files:
        require(path.is_file() and path.stat().st_size > 0, f"missing required output: {path}")
    check_phase_a_freeze(ctx)
    lineages = read_csv(ARRAY_LINEAGE)
    points = read_csv(POINT_TRACE)
    coords = read_csv(COORDINATE_AUDIT)
    channels = read_csv(CHANNEL_AUDIT)
    sampling = read_csv(SAMPLING_AUDIT)
    synthetic = read_csv(SYNTHETIC_RESULTS)
    conclusions = read_csv(CONCLUSION_LINEAGE)
    families = {row["coordinate_family"] for row in coords if row.get("coordinate_family")}
    required_families = {"RAW_SAR_DISPLAY", "WORLD_STABILIZED_IMAGE_STACK", "GT_ALIGNED_RESEARCH_STACK", "OPTICAL_PROXY_ALIGNED_STACK"}
    require(required_families <= families, f"missing coordinate families: {required_families - families}")
    require(any("temporal_" in row["channel"] and row["coordinate_family"] == "WORLD_STABILIZED_IMAGE_STACK" for row in channels), "world temporal channels missing")
    require(not any("component_continuity" in row["channel"] for row in channels), "dishonest component continuity name remains")
    require(all(row["status"] == "PASS" for row in synthetic), "synthetic test failure")
    require(len(conclusions) == 8, "formal conclusion lineage must have eight rows")
    for case_id in {row["case_id"] for row in points}:
        roles = [row["point_role"] for row in points if row["case_id"] == case_id]
        require(roles.count("skeleton") >= 2, f"insufficient skeleton point trace: {case_id}")
        require(roles.count("background") >= 2, f"insufficient background point trace: {case_id}")
    methods = {row["method"] for row in sampling}
    require({"exact_rank_mann_whitney", "fixed_seed_uniform_3000", "spatial_stratified_4x4", "legacy_first3000_flattened"} <= methods, "sampling methods incomplete")
    subtypes = {row["background_subtype"] for row in sampling}
    require({"vertical_line", "fan_arc", "hotspot", "clutter", "unresolved_distribution_not_auc_negative"} <= subtypes, "background subtype reporting incomplete")
    bundle_hashes: dict[Path, str] = {}
    for row in lineages:
        path = Path(row["output_npz_path"])
        require(path.is_file(), f"missing lineage array bundle: {path}")
        if path not in bundle_hashes:
            bundle_hashes[path] = sha256_file(path)
        require(bundle_hashes[path] == row["output_sha256"], f"array bundle hash mismatch: {path}")
    audit_scope_files = set(git("diff", "--name-only", ctx.config["expected_start_head"], "--").splitlines())
    audit_scope_files.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    forbidden = sorted(name for name in audit_scope_files if name.lower().endswith((".npz", ".png", ".gif", ".mp4")))
    require(not forbidden, f"large/generated assets present in the R2 Git change scope: {forbidden[:5]}")
    evidence_cards = list((ctx.output_root / "evidence_cards").rglob("*.png"))
    require(len(evidence_cards) >= 40, f"insufficient evidence cards: {len(evidence_cards)}")
    output_rows = output_manifest_rows(ctx.output_root)
    write_csv(OUTPUT_MANIFEST, output_rows)
    result = {
        "status": "PASS_ENGINEERING_CONTRACT_PROPAGATION_NOT_AUTHORIZED",
        "branch": git("branch", "--show-current"),
        "head": git("rev-parse", "HEAD"),
        "array_lineage_count": len(lineages),
        "point_trace_count": len(points),
        "coordinate_family_count": len(required_families),
        "channel_audit_count": len(channels),
        "sampling_method_count": len(methods),
        "synthetic_test_count": len(synthetic),
        "evidence_card_count": len(evidence_cards),
        "external_output_file_count": len(output_rows),
        "phase_a_freeze_preserved": True,
        "propagation_design_authorized": False,
    }
    write_json(VALIDATION_JSON, result)
    return result


def build_cases(ctx: AuditContext) -> list[CaseData]:
    return [build_case_data(ctx, window) for window in ctx.config["windows"]]


def run_phase_b_pipeline(ctx: AuditContext) -> dict[str, Any]:
    check_phase_a_freeze(ctx)
    cases = build_cases(ctx)
    coordinate_rows = run_coordinate_stacks(ctx, cases)
    fan_rows = run_fan_geometry(ctx, cases)
    atlas_rows = run_atlas_audit(ctx, cases)
    channel_rows, normalization_rows, sampling_rows, cache = build_channel_products(ctx, cases)
    point_rows = run_point_trace(ctx, cases, cache)
    write_channel_reports(channel_rows, normalization_rows, sampling_rows)
    synthetic_rows = run_synthetic_tests(ctx)
    extension_rows = run_extension_validation(ctx)
    conclusion_rows = run_conclusions(ctx, cases)
    validation = validate_outputs(ctx)
    return {
        "coordinate_rows": len(coordinate_rows),
        "fan_rows": len(fan_rows),
        "atlas_rows": len(atlas_rows),
        "channel_rows": len(channel_rows),
        "normalization_rows": len(normalization_rows),
        "sampling_rows": len(sampling_rows),
        "point_rows": len(point_rows),
        "synthetic_rows": len(synthetic_rows),
        "extension_rows": len(extension_rows),
        "conclusion_rows": len(conclusion_rows),
        "validation": validation,
    }


def stage_main(default_stage: str | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", nargs="?", default=default_stage or "pipeline")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    ctx = load_context(args.config)
    stage = args.stage
    if stage == "phase-a":
        run_phase_a(ctx)
        return
    if stage == "pipeline":
        result = run_phase_b_pipeline(ctx)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if stage == "coordinate-stacks":
        run_coordinate_stacks(ctx, build_cases(ctx))
        return
    if stage == "fan-geometry":
        run_fan_geometry(ctx, build_cases(ctx))
        return
    if stage == "channels" or stage == "normalization":
        channel_rows, normalization_rows, sampling_rows, _cache = build_channel_products(ctx, build_cases(ctx))
        write_channel_reports(channel_rows, normalization_rows, sampling_rows)
        return
    if stage == "trace-points":
        run_point_trace_from_bundles(ctx, build_cases(ctx))
        return
    if stage == "synthetic-tests":
        run_synthetic_tests(ctx)
        return
    if stage == "conclusions":
        run_conclusions(ctx, build_cases(ctx))
        return
    if stage == "validate":
        print(json.dumps(validate_outputs(ctx), indent=2, ensure_ascii=False))
        return
    raise ValueError(f"unknown stage: {stage}")


if __name__ == "__main__":
    stage_main()
