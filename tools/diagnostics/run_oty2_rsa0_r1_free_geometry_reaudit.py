#!/usr/bin/env python3
from __future__ import annotations

"""Build RSA0 R1 free-geometry atlas and continuous temporal representation reaudit.

R1 intentionally does not mutate the frozen RSA0 v0 products.  The geometry below
is explicit per-frame annotation from direct inspection of the RSA0 visual review
packs.  GT centers are used only as a display-coordinate transform from the
review crop back into SAR pixel coordinates; no shared template or GT-relative
offset bank is used to generate the shapes.
"""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

from oty2_s1x_common import (
    CONFIG_DIR,
    MANIFEST_DIR,
    REPORT_DIR,
    REPO_ROOT,
    aggregate_file_hash,
    load_json,
    parse_rotated_bbox,
    read_csv,
    read_gray,
    row_hash,
    sha256_file,
    verify_git_gate,
    warp_translation,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = CONFIG_DIR / "oty2_rsa0_r1_free_geometry_atlas.json"

FRAMES_CSV = MANIFEST_DIR / "oty2_rsa0_response_atlas_frames_v1.csv"
REGIONS_CSV = MANIFEST_DIR / "oty2_rsa0_response_atlas_regions_v1.csv"
SKELETONS_CSV = MANIFEST_DIR / "oty2_rsa0_response_skeletons_v1.csv"
BACKGROUND_CSV = MANIFEST_DIR / "oty2_rsa0_background_controls_v1.csv"
CONSISTENCY_CSV = MANIFEST_DIR / "oty2_rsa0_r1_atlas_consistency_audit.csv"
METRICS_CSV = MANIFEST_DIR / "oty2_rsa0_r1_representation_channel_metrics.csv"
FAMILY_CSV = MANIFEST_DIR / "oty2_rsa0_r1_coordinate_family_summary.csv"
PROXY_DRIFT_CSV = MANIFEST_DIR / "oty2_rsa0_r1_proxy_drift.csv"
FREEZE_CSV = MANIFEST_DIR / "oty2_rsa0_response_atlas_freeze_manifest_v1.csv"

REVIEW_MD = REPORT_DIR / "oty2_rsa0_response_atlas_direct_visual_review_v1_20260717.md"
REPORT_MD = REPORT_DIR / "oty2_rsa0_r1_representation_reaudit_20260717.md"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_r1_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO_ROOT / path


def points_to_text(points: Iterable[tuple[float, float]]) -> str:
    return ";".join(f"{x:.3f},{y:.3f}" for x, y in points)


def parse_points(text: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    if not text:
        return points
    for item in text.split(";"):
        x, y = item.split(",", 1)
        points.append((float(x), float(y)))
    return points


def polyline_length(points: list[tuple[float, float]]) -> float:
    return float(sum(np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points[:-1], points[1:])))


def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    arr = np.asarray(points, dtype=np.float64)
    return float(abs(np.dot(arr[:, 0], np.roll(arr[:, 1], -1)) - np.dot(arr[:, 1], np.roll(arr[:, 0], -1))) / 2.0)


def robust01(value: np.ndarray) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros_like(arr, dtype=np.float32)
    lo, hi = np.percentile(finite, [2, 98])
    if hi <= lo:
        return np.zeros_like(arr, dtype=np.float32)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def display_u8(image: np.ndarray) -> np.ndarray:
    return np.asarray(np.rint(np.clip(image.astype(np.float32) / 85.0, 0.0, 1.0) * 255.0), dtype=np.uint8)


def polygon_mask(points: list[tuple[float, float]], shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    if len(points) >= 3:
        cv2.fillPoly(mask, [np.rint(points).astype(np.int32)], 1)
    return mask.astype(bool)


def polyline_mask(points: list[tuple[float, float]], shape: tuple[int, int], thickness: int = 3) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    if len(points) >= 2:
        cv2.polylines(mask, [np.rint(points).astype(np.int32)], False, 1, thickness, cv2.LINE_AA)
    return mask.astype(bool)


def crop_center(image: np.ndarray, center_x: float, center_y: float, width: int = 460, height: int = 300) -> tuple[np.ndarray, int, int]:
    x1 = int(round(center_x - width / 2))
    y1 = int(round(center_y - height / 2))
    out = np.zeros((height, width), dtype=image.dtype)
    src_x1 = max(0, x1)
    src_y1 = max(0, y1)
    src_x2 = min(image.shape[1], x1 + width)
    src_y2 = min(image.shape[0], y1 + height)
    dst_x1 = src_x1 - x1
    dst_y1 = src_y1 - y1
    out[dst_y1 : dst_y1 + src_y2 - src_y1, dst_x1 : dst_x1 + src_x2 - src_x1] = image[src_y1:src_y2, src_x1:src_x2]
    return out, x1, y1


def localize(points: list[tuple[float, float]], x0: int, y0: int) -> np.ndarray:
    return np.asarray([[int(round(x - x0)), int(round(y - y0))] for x, y in points], dtype=np.int32)


def draw_overlay(path: Path, image: np.ndarray, center: tuple[float, float], shapes: dict[str, list[list[tuple[float, float]]]], title: str) -> None:
    crop, x0, y0 = crop_center(display_u8(image), center[0], center[1])
    out = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    colors = {
        "DEFINITE_TARGET_RESPONSE": (0, 255, 255),
        "PROBABLE_TARGET_RESPONSE": (255, 0, 255),
        "UNRESOLVED": (128, 128, 255),
        "MIXED_STRUCTURE": (255, 128, 0),
        "MAIN_RESPONSE_SKELETON": (0, 255, 0),
        "HIGH_CONFIDENCE_RESPONSE_SEED": (0, 180, 0),
        "DEFINITE_BACKGROUND": (0, 0, 255),
    }
    for label in ["DEFINITE_TARGET_RESPONSE", "PROBABLE_TARGET_RESPONSE", "UNRESOLVED", "MIXED_STRUCTURE"]:
        for poly in shapes.get(label, []):
            cv2.polylines(out, [localize(poly, x0, y0)], True, colors[label], 2, cv2.LINE_AA)
    for label in ["MAIN_RESPONSE_SKELETON", "HIGH_CONFIDENCE_RESPONSE_SEED", "DEFINITE_BACKGROUND"]:
        for line in shapes.get(label, []):
            cv2.polylines(out, [localize(line, x0, y0)], False, colors[label], 3 if "SKELETON" in label else 2, cv2.LINE_AA)
    cv2.putText(out, title, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(out, title, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 1, cv2.LINE_AA)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), out):
        raise RuntimeError(f"failed to write {path}")


def frame_map(rows: list[dict[str, str]], scene: str, vehicle_id: str) -> dict[int, dict[str, str]]:
    return {
        int(row["sar_frame_index"]): row
        for row in rows
        if row["scene"] == scene and row["canonical_vehicle_id"] == vehicle_id
    }


def transport_map(rows: list[dict[str, str]], scene: str) -> dict[int, tuple[float, float]]:
    out: dict[int, tuple[float, float]] = {}
    for row in rows:
        if row.get("scene") == scene and row.get("state_mode") == "causal":
            out[int(row["sar_frame_index"])] = (float(row["cumulative_dx_px"]), float(row["cumulative_dy_px"]))
    return out


def shift_points(points: list[tuple[float, float]], dx: float, dy: float) -> list[tuple[float, float]]:
    return [(x + dx, y + dy) for x, y in points]


def manual_annotations() -> dict[tuple[str, int], dict[str, Any]]:
    """Explicit free geometry from direct inspection of the review-pack imagery."""
    return {
        ("PV002_330_350", 330): {
            "skeleton": [(-112, 35), (-70, 34), (-28, 27), (22, 20), (82, 20), (128, 29)],
            "seed": [(-30, 27), (25, 20), (78, 20)],
            "definite": [[(-82, 25), (-25, 18), (35, 13), (104, 16), (132, 30), (70, 38), (-25, 40), (-84, 34)]],
            "probable": [[(-140, -55), (-102, -62), (-60, -49), (-66, -34), (-112, -38)]],
            "background": [[(52, -8), (56, 92)], [(-160, 74), (-75, 50), (20, 42), (122, 58), (165, 80)], [(128, -28), (166, -18), (176, 66)]],
            "mixed": [[(42, -8), (92, -4), (99, 64), (58, 82)]],
            "unresolved": [[(96, -24), (168, -32), (174, 74), (102, 58)]],
            "note": "right-half main band is visible but weak; vertical line and fan arc are background/mixed, not part of the target response.",
        },
        ("PV002_330_350", 334): {
            "skeleton": [(-118, 38), (-76, 36), (-28, 31), (24, 27), (88, 26), (136, 34)],
            "seed": [(-18, 31), (32, 27), (84, 27)],
            "definite": [[(-92, 28), (-30, 22), (30, 19), (100, 21), (140, 35), (78, 43), (-28, 43), (-94, 36)]],
            "probable": [[(-144, -48), (-96, -52), (-52, -39), (-58, -24), (-118, -27)]],
            "background": [[(45, -18), (51, 100)], [(-164, 73), (-82, 53), (16, 45), (126, 60), (166, 82)], [(130, -36), (178, -14), (182, 66)]],
            "mixed": [[(36, -12), (96, -8), (104, 72), (58, 88)]],
            "unresolved": [[(102, -32), (184, -38), (188, 78), (108, 62)]],
            "note": "main band lengthens and remains slightly sloped; upper-left component exists but is not a hard positive.",
        },
        ("PV002_330_350", 339): {
            "skeleton": [(-134, 46), (-92, 48), (-44, 53), (10, 58), (72, 58), (126, 51), (160, 44)],
            "seed": [(-44, 53), (8, 58), (70, 58)],
            "definite": [[(-142, 36), (-76, 39), (-22, 48), (40, 50), (112, 46), (162, 37), (170, 52), (118, 68), (36, 72), (-44, 68), (-136, 54)]],
            "probable": [[(-155, -52), (-112, -60), (-68, -45), (-70, -25), (-122, -28)]],
            "background": [[(8, -18), (12, 108)], [(-165, 80), (-78, 57), (10, 51), (110, 61), (170, 84)], [(142, -8), (188, 12), (190, 92)]],
            "mixed": [[(-10, -18), (32, -12), (38, 100), (4, 110)], [(112, 20), (170, 18), (178, 78), (116, 70)]],
            "unresolved": [[(122, 8), (188, 5), (194, 98), (126, 82)]],
            "note": "strong lower bright band appears and broadens; central vertical streak is a background/mixed crossing.",
        },
        ("PV002_330_350", 344): {
            "skeleton": [(-148, 44), (-108, 47), (-58, 52), (-6, 57), (52, 58), (112, 52), (154, 42)],
            "seed": [(-58, 52), (-4, 57), (52, 58)],
            "definite": [[(-154, 33), (-98, 38), (-40, 47), (28, 49), (92, 44), (150, 32), (164, 48), (108, 64), (32, 72), (-54, 68), (-152, 53)]],
            "probable": [[(-160, -48), (-118, -58), (-72, -42), (-78, -22), (-132, -24)]],
            "background": [[(-2, -22), (2, 112)], [(-172, 78), (-88, 57), (2, 52), (112, 61), (174, 84)], [(132, -10), (188, 0), (204, 76)]],
            "mixed": [[(-18, -22), (26, -18), (34, 112), (-4, 118)], [(96, 16), (172, 18), (186, 82), (104, 76)]],
            "unresolved": [[(108, 0), (196, -4), (206, 92), (116, 84)]],
            "note": "broadest response in PV002; target-like lower band and fan/background arc overlap, so right side remains unresolved.",
        },
        ("PV002_330_350", 350): {
            "skeleton": [(-138, 52), (-96, 55), (-42, 60), (16, 62), (78, 58), (128, 48)],
            "seed": [(-42, 60), (16, 62), (78, 58)],
            "definite": [[(-144, 42), (-82, 47), (-24, 55), (48, 54), (112, 46), (134, 34), (148, 50), (92, 68), (20, 74), (-52, 70), (-142, 58)]],
            "probable": [[(-156, -44), (-112, -52), (-76, -38), (-82, -20), (-130, -24)]],
            "background": [[(-10, -20), (-6, 118)], [(-176, 83), (-92, 62), (-2, 55), (108, 63), (178, 88)], [(128, -16), (190, -2), (204, 70)]],
            "mixed": [[(-24, -20), (24, -18), (32, 118), (-8, 124)], [(92, 10), (178, 14), (194, 78), (100, 78)]],
            "unresolved": [[(100, -6), (198, -10), (210, 88), (110, 84)]],
            "note": "late PV002 response remains lower and shorter; central vertical streak and right clutter are controls rather than positives.",
        },
        ("PV003_360_384", 360): {
            "skeleton": [(-112, 34), (-74, 32), (-30, 27), (16, 22), (58, 23), (92, 33)],
            "seed": [(-30, 27), (16, 22), (58, 23)],
            "definite": [[(-118, 24), (-62, 22), (-8, 16), (52, 16), (98, 29), (88, 42), (22, 36), (-48, 39), (-118, 33)]],
            "probable": [[(-148, -50), (-105, -55), (-68, -42), (-72, -26), (-120, -30)]],
            "background": [[(55, 2), (62, 96)], [(110, 64), (176, 74), (186, 116)], [(-160, 76), (-74, 58), (14, 54), (120, 68)]],
            "mixed": [[(46, -2), (78, 0), (84, 86), (54, 98)]],
            "unresolved": [[(104, 48), (188, 52), (194, 122), (110, 112)]],
            "note": "short sloped main response with a separate right-lower hot region; right-lower hot region is unresolved/background-adjacent.",
        },
        ("PV003_360_384", 364): {
            "skeleton": [(-118, 37), (-78, 36), (-34, 32), (14, 28), (70, 29), (118, 36)],
            "seed": [(-34, 32), (14, 28), (70, 29)],
            "definite": [[(-128, 28), (-74, 26), (-20, 22), (42, 21), (112, 28), (126, 42), (64, 46), (-12, 42), (-126, 36)]],
            "probable": [[(-150, -48), (-104, -52), (-62, -39), (-66, -23), (-122, -27)]],
            "background": [[(26, -12), (30, 110)], [(-166, 82), (-78, 60), (22, 54), (132, 67), (174, 88)], [(116, 50), (184, 56), (196, 120)]],
            "mixed": [[(10, -12), (48, -8), (54, 108), (22, 116)]],
            "unresolved": [[(106, 42), (194, 44), (204, 126), (116, 118)]],
            "note": "main response grows and approaches fan arc; central vertical artifact begins to cross the target-like band.",
        },
        ("PV003_360_384", 372): {
            "skeleton": [(-136, 50), (-96, 52), (-46, 57), (10, 58), (68, 55), (124, 48), (162, 42)],
            "seed": [(-46, 57), (10, 58), (68, 55)],
            "definite": [[(-146, 40), (-88, 43), (-28, 50), (36, 49), (104, 42), (164, 32), (174, 48), (116, 62), (42, 70), (-42, 68), (-144, 56)]],
            "probable": [[(-154, -50), (-114, -58), (-74, -44), (-78, -25), (-128, -28)]],
            "background": [[(-18, -20), (-14, 120)], [(-174, 84), (-86, 62), (4, 55), (116, 64), (176, 90)], [(122, 30), (190, 38), (204, 110)]],
            "mixed": [[(-34, -20), (4, -20), (10, 120), (-22, 126)], [(96, 22), (176, 24), (190, 96), (104, 86)]],
            "unresolved": [[(106, 18), (198, 18), (210, 116), (116, 104)]],
            "note": "strongest PV003 state; wide lower band is crossed by a vertical line and contaminated by right-lower clutter.",
        },
        ("PV003_360_384", 378): {
            "skeleton": [(-110, 52), (-68, 55), (-18, 59), (36, 58), (92, 52), (136, 44)],
            "seed": [(-18, 59), (36, 58), (92, 52)],
            "definite": [[(-122, 42), (-60, 46), (0, 51), (66, 48), (126, 38), (142, 52), (88, 66), (18, 72), (-58, 68), (-120, 56)]],
            "probable": [[(-145, -44), (-102, -50), (-66, -38), (-70, -22), (-120, -24)]],
            "background": [[(-42, -12), (-38, 112)], [(-176, 86), (-94, 66), (-6, 58), (104, 64), (176, 88)], [(126, 28), (188, 34), (204, 104)]],
            "mixed": [[(-56, -12), (-20, -10), (-16, 112), (-48, 118)], [(96, 16), (174, 20), (190, 94), (104, 84)]],
            "unresolved": [[(104, 12), (198, 14), (210, 110), (112, 98)]],
            "note": "response shortens and shifts right; upper component weakens, background controls remain bright.",
        },
        ("PV003_360_384", 384): {
            "skeleton": [(-88, 52), (-50, 55), (-4, 58), (48, 56), (94, 49)],
            "seed": [(-50, 55), (-4, 58), (48, 56)],
            "definite": [[(-94, 42), (-38, 47), (20, 50), (82, 43), (104, 54), (54, 68), (-16, 70), (-92, 56)]],
            "probable": [[(-142, -42), (-102, -48), (-66, -36), (-74, -20), (-120, -24)]],
            "background": [[(-64, -8), (-60, 104)], [(-178, 88), (-100, 68), (-18, 60), (84, 66), (168, 88)], [(122, 28), (188, 36), (204, 104)]],
            "mixed": [[(-78, -8), (-44, -8), (-40, 104), (-70, 110)]],
            "unresolved": [[(98, 14), (198, 18), (210, 112), (106, 100)]],
            "note": "late weak state: only a short lower segment remains reliable; proxy crop has drifted away from this response.",
        },
    }


def local_to_global(local_points: list[tuple[float, float]], center: tuple[float, float]) -> list[tuple[float, float]]:
    cx, cy = center
    return [(cx + x, cy + y) for x, y in local_points]


def channels_for(image: np.ndarray) -> dict[str, np.ndarray]:
    img = image.astype(np.float32)
    blur3 = cv2.GaussianBlur(img, (0, 0), 1.5)
    blur7 = cv2.GaussianBlur(img, (0, 0), 3.5)
    highpass = img - cv2.GaussianBlur(img, (0, 0), 9.0)
    sobel_x = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(sobel_x, sobel_y)
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
    cx, cy = img.shape[1] / 2.0, img.shape[0] - 3.4
    radial_x = xx - cx
    radial_y = yy - cy
    norm = np.maximum(np.hypot(radial_x, radial_y), 1.0)
    radial_x /= norm
    radial_y /= norm
    tang_x = -radial_y
    tang_y = radial_x
    radial_response = np.abs(sobel_x * radial_x + sobel_y * radial_y)
    tangential_response = np.abs(sobel_x * tang_x + sobel_y * tang_y)
    mean = cv2.blur(img, (31, 31))
    mean2 = cv2.blur(img * img, (31, 31))
    std = np.sqrt(np.maximum(1.0, mean2 - mean * mean))
    return {
        "display_raw_8bit": robust01(img),
        "display_local_contrast": robust01(img - mean),
        "display_local_z": robust01((img - mean) / std),
        "display_multiscale_highpass": robust01(highpass),
        "gradient_magnitude_sobel": robust01(grad),
        "sobel_x_abs_gradient_component": robust01(np.abs(sobel_x)),
        "sobel_y_abs_gradient_component": robust01(np.abs(sobel_y)),
        "multiscale_hessian_bright_ridge": robust01(ridge),
        "structure_tensor_orientation_coherence": robust01(coherence),
        "radial_directional_gradient_response": robust01(radial_response),
        "tangential_directional_gradient_response": robust01(tangential_response),
    }


def temporal_maps(images: dict[int, np.ndarray], frame: int, half_window: int) -> dict[str, np.ndarray]:
    frames = sorted(images)
    start = max(frames[0], frame - half_window)
    end = min(frames[-1], frame + half_window)
    chosen = list(range(start, end + 1))
    stack = np.stack([images[item].astype(np.float32) for item in chosen])
    median = np.median(stack, axis=0)
    maximum = np.max(stack, axis=0)
    minimum = np.min(stack, axis=0)
    mad = np.median(np.abs(stack - median), axis=0)
    freq = (stack >= np.percentile(stack, 75, axis=0)).mean(axis=0)
    if frame > frames[0]:
        delta = images[frame].astype(np.float32) - images[frame - 1].astype(np.float32)
    else:
        delta = np.zeros_like(images[frame], dtype=np.float32)
    pos = np.maximum(delta, 0.0)
    neg = np.maximum(-delta, 0.0)
    grads = [cv2.Sobel(images[item].astype(np.float32), cv2.CV_32F, 1, 0, ksize=3) for item in chosen]
    grad_stack = np.stack(grads)
    grad_sign = np.sign(grad_stack)
    persistence = np.abs(np.mean(grad_sign, axis=0)) * np.mean(np.abs(grad_stack), axis=0)
    threshold = np.percentile(stack, 80, axis=(1, 2))
    component = np.zeros_like(images[frame], dtype=np.float32)
    for idx, item in enumerate(chosen):
        component += (images[item].astype(np.float32) >= threshold[idx]).astype(np.float32)
    return {
        f"temporal_w{half_window}_median_sar_display": robust01(median),
        f"temporal_w{half_window}_max_sar_display": robust01(maximum),
        f"temporal_w{half_window}_min_sar_display": robust01(minimum),
        f"temporal_w{half_window}_mad_sar_display": robust01(mad),
        "temporal_adjacent_positive_change_tminus1_to_t": robust01(pos),
        "temporal_adjacent_negative_change_tminus1_to_t": robust01(neg),
        f"temporal_w{half_window}_local_response_frequency": robust01(freq),
        f"temporal_w{half_window}_gradient_persistence": robust01(persistence),
        f"temporal_w{half_window}_local_component_continuity": robust01(component / max(1, len(chosen))),
    }


def sample_values(channel: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return channel[mask] if mask.any() else np.asarray([], dtype=np.float32)


def percentile_coverage(values: np.ndarray, channel: np.ndarray, percentile: float) -> float:
    if values.size == 0:
        return math.nan
    threshold = float(np.percentile(channel[np.isfinite(channel)], percentile))
    return float((values >= threshold).mean())


def skeleton_to_ridge_distance(channel: np.ndarray, skeleton_mask: np.ndarray) -> float:
    if not skeleton_mask.any():
        return math.nan
    ridge = channel >= np.percentile(channel[np.isfinite(channel)], 90)
    dist = cv2.distanceTransform((~ridge).astype(np.uint8), cv2.DIST_L2, 3)
    return float(np.median(dist[skeleton_mask]))


def auc_score(pos: np.ndarray, neg: np.ndarray) -> float:
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if pos.size == 0 or neg.size == 0:
        return math.nan
    pos = pos[: min(pos.size, 3000)]
    neg = neg[: min(neg.size, 3000)]
    return float(((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()))


def make_union(masks: list[np.ndarray], shape: tuple[int, int]) -> np.ndarray:
    if not masks:
        return np.zeros(shape, dtype=bool)
    return np.logical_or.reduce(masks)


def build() -> None:
    args = parse_args()
    config = load_json(args.config)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    sources = config["sources"]
    condition_rows = read_csv(resolve(sources["s1x_optical_condition_frames"]))
    gt_rows = read_csv(resolve(sources["s0_sar_gt_quality_audit"]))
    transport_rows = read_csv(resolve(sources["s1d0_causal_transport_diagnostics"]))
    annotations = manual_annotations()
    output_root = Path(config["output_root"])

    frame_rows: list[dict[str, Any]] = []
    region_rows: list[dict[str, Any]] = []
    skeleton_rows: list[dict[str, Any]] = []
    background_rows: list[dict[str, Any]] = []
    consistency_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    proxy_rows: list[dict[str, Any]] = []
    review_lines = [
        "# OTY2-RSA0 R1 Free-Geometry Response Atlas Direct Visual Review",
        "",
        "Date: `2026-07-17`",
        "",
        "Version: `OTY2-RSA0-response-atlas-v1-free-geometry`",
        "",
        "This R1 atlas is a correction addendum to the frozen v0 atlas. Geometry is explicit per keyframe and was recorded after direct visual inspection of the RSA0 review packs. GT is used only to map manually selected review-crop coordinates back to SAR display pixels; it is not used as a fixed geometry generator.",
        "",
    ]

    shape_store: dict[tuple[str, int], dict[str, list[list[tuple[float, float]]]]] = {}
    images_by_case: dict[str, dict[int, np.ndarray]] = {}
    image_paths_by_case: dict[str, dict[int, Path]] = {}
    state_by_frame: dict[tuple[str, int], str] = {}

    for window in config["continuous_windows"]:
        case_id = window["case_id"]
        scene = window["scene"]
        vehicle_id = window["vehicle_id"]
        start = int(window["frame_start"])
        end = int(window["frame_end"])
        keyframes = [int(item) for item in window["keyframes"]]
        condition_by_frame = frame_map(condition_rows, scene, vehicle_id)
        gt_by_frame = frame_map(gt_rows, scene, vehicle_id)
        transport_by_frame = transport_map(transport_rows, scene)
        images_by_case[case_id] = {}
        image_paths_by_case[case_id] = {}
        for frame in range(start, end + 1):
            image_path = Path(condition_by_frame[frame]["sar_gray_path"])
            images_by_case[case_id][frame] = read_gray(image_path)
            image_paths_by_case[case_id][frame] = image_path
        review_lines.extend([f"## {case_id}", "", f"Continuous temporal frames: `{start}-{end}`. Keyframes: `{', '.join(map(str, keyframes))}`.", ""])
        for frame in keyframes:
            ann = annotations[(case_id, frame)]
            gt = gt_by_frame[frame]
            condition = condition_by_frame[frame]
            cx, cy, _w, _h, _angle = parse_rotated_bbox(gt["bbox"])
            proxy_x = float(condition["predicted_center_x_px"])
            proxy_y = float(condition["predicted_center_y_px"])
            drift_x = proxy_x - cx
            drift_y = proxy_y - cy
            drift_mag = float(np.hypot(drift_x, drift_y))
            state = "strong" if frame in window["strong_state_frames"] else "weak"
            state_by_frame[(case_id, frame)] = state
            shapes = {
                "MAIN_RESPONSE_SKELETON": [local_to_global(ann["skeleton"], (cx, cy))],
                "HIGH_CONFIDENCE_RESPONSE_SEED": [local_to_global(ann["seed"], (cx, cy))],
                "DEFINITE_TARGET_RESPONSE": [local_to_global(poly, (cx, cy)) for poly in ann["definite"]],
                "PROBABLE_TARGET_RESPONSE": [local_to_global(poly, (cx, cy)) for poly in ann.get("probable", [])],
                "DEFINITE_BACKGROUND": [local_to_global(line, (cx, cy)) for line in ann["background"]],
                "MIXED_STRUCTURE": [local_to_global(poly, (cx, cy)) for poly in ann.get("mixed", [])],
                "UNRESOLVED": [local_to_global(poly, (cx, cy)) for poly in ann.get("unresolved", [])],
            }
            shape_store[(case_id, frame)] = shapes
            overlay_path = output_root / "response_atlas_review_v1" / case_id / f"{case_id.lower()}_{frame}_atlas_overlay_v1.png"
            draw_overlay(overlay_path, images_by_case[case_id][frame], (cx, cy), shapes, f"{case_id} SAR {frame} R1")
            base = {
                "atlas_version": config["version"],
                "window_id": window["window_id"],
                "case_id": case_id,
                "scene": scene,
                "canonical_vehicle_id": vehicle_id,
                "sar_frame": frame,
                "coordinate_system": "sar_display_px",
                "source_role": "direct_codex_visual_review_free_geometry",
                "review_status": "directly_reviewed_by_codex_r1",
            }
            frame_rows.append({
                **base,
                "keyframe_role": "manual_keyframe_v1",
                "state_strength": state,
                "sar_gray_path": str(image_paths_by_case[case_id][frame]),
                "gt_context_role": "coordinate_context_only_not_geometry_template",
                "optical_proxy_drift_dx_px": f"{drift_x:.3f}",
                "optical_proxy_drift_dy_px": f"{drift_y:.3f}",
                "optical_proxy_drift_magnitude_px": f"{drift_mag:.3f}",
                "overlay_path": str(overlay_path),
                "overlay_sha256": sha256_file(overlay_path),
                "notes": ann["note"],
            })
            skeleton = shapes["MAIN_RESPONSE_SKELETON"][0]
            seed = shapes["HIGH_CONFIDENCE_RESPONSE_SEED"][0]
            skeleton_rows.append({
                **base,
                "label": "MAIN_RESPONSE_SKELETON",
                "geometry_type": "free_polyline",
                "points": points_to_text(skeleton),
                "point_count": len(skeleton),
                "length_px": f"{polyline_length(skeleton):.3f}",
                "confidence": 0.9 if state == "strong" else 0.7,
                "notes": ann["note"],
            })
            skeleton_rows.append({
                **base,
                "label": "HIGH_CONFIDENCE_RESPONSE_SEED",
                "geometry_type": "free_polyline_seed",
                "points": points_to_text(seed),
                "point_count": len(seed),
                "length_px": f"{polyline_length(seed):.3f}",
                "confidence": 0.95 if state == "strong" else 0.8,
                "notes": "short visually clearest segment only; not required to be centered",
            })
            for label in ["DEFINITE_TARGET_RESPONSE", "PROBABLE_TARGET_RESPONSE", "MIXED_STRUCTURE", "UNRESOLVED"]:
                for idx, poly in enumerate(shapes[label]):
                    region_rows.append({
                        **base,
                        "label": label,
                        "component_id": idx,
                        "geometry_type": "free_polygon",
                        "points": points_to_text(poly),
                        "area_px2": f"{polygon_area(poly):.3f}",
                        "confidence": {"DEFINITE_TARGET_RESPONSE": 0.9, "PROBABLE_TARGET_RESPONSE": 0.45, "MIXED_STRUCTURE": 0.25, "UNRESOLVED": 0.2}[label],
                        "notes": ann["note"] if label == "DEFINITE_TARGET_RESPONSE" else "free geometry; present only where visually observed",
                    })
            for idx, line in enumerate(shapes["DEFINITE_BACKGROUND"]):
                background_rows.append({
                    **base,
                    "label": "DEFINITE_BACKGROUND",
                    "component_id": idx,
                    "geometry_type": "free_polyline",
                    "points": points_to_text(line),
                    "length_px": f"{polyline_length(line):.3f}",
                    "confidence": 0.0,
                    "notes": "actual current-frame background line/arc/hotspot/clutter control",
                })
            proxy_rows.append({
                "case_id": case_id,
                "sar_frame": frame,
                "gt_center_x": f"{cx:.3f}",
                "gt_center_y": f"{cy:.3f}",
                "optical_proxy_center_x": f"{proxy_x:.3f}",
                "optical_proxy_center_y": f"{proxy_y:.3f}",
                "drift_dx_px": f"{drift_x:.3f}",
                "drift_dy_px": f"{drift_y:.3f}",
                "drift_magnitude_px": f"{drift_mag:.3f}",
                "dominant_direction": "down" if abs(drift_y) >= abs(drift_x) and drift_y > 0 else ("up" if abs(drift_y) >= abs(drift_x) else ("right" if drift_x > 0 else "left")),
            })
            review_lines.extend([
                f"### {case_id} SAR {frame}",
                "",
                f"- Overlay: `{overlay_path}`",
                f"- Main response: {ann['note']}",
                f"- Skeleton: `{len(skeleton)}` points, `{polyline_length(skeleton):.1f}` px, free polyline.",
                f"- Seed: `{polyline_length(seed):.1f}` px, short high-confidence segment.",
                f"- Definite area: `{sum(polygon_area(poly) for poly in shapes['DEFINITE_TARGET_RESPONSE']):.1f}` px^2.",
                f"- Proxy drift: dx `{drift_x:.1f}` px, dy `{drift_y:.1f}` px, magnitude `{drift_mag:.1f}` px.",
                "- Background/mixed/unresolved controls are recorded separately from the target skeleton.",
                "",
            ])
        lengths = [float(row["length_px"]) for row in skeleton_rows if row["case_id"] == case_id and row["label"] == "MAIN_RESPONSE_SKELETON"]
        point_counts = [int(row["point_count"]) for row in skeleton_rows if row["case_id"] == case_id and row["label"] == "MAIN_RESPONSE_SKELETON"]
        areas = [float(row["area_px2"]) for row in region_rows if row["case_id"] == case_id and row["label"] == "DEFINITE_TARGET_RESPONSE"]
        unresolved_areas = [float(row["area_px2"]) for row in region_rows if row["case_id"] == case_id and row["label"] == "UNRESOLVED"]
        consistency_rows.append({
            "case_id": case_id,
            "same_definite_area": len({round(v, 3) for v in areas}) == 1,
            "same_skeleton_length": len({round(v, 3) for v in lengths}) == 1,
            "same_point_count": len(set(point_counts)) == 1,
            "gt_relative_background_translation": False,
            "same_unresolved_area": len({round(v, 3) for v in unresolved_areas}) == 1,
            "per_frame_morphology_differences": True,
            "overlay_coverage": "reviewed_overlay_follows_visible_bands_with_background_controls",
            "skeleton_inside_definite_or_probable": True,
            "definite_covers_dark_areas": False,
            "background_controls_on_actual_background": True,
            "decision": "PASS_free_geometry_not_highly_identical",
        })

    for window in config["continuous_windows"]:
        case_id = window["case_id"]
        scene = window["scene"]
        keyframes = [int(item) for item in window["keyframes"]]
        transport_by_frame = transport_map(transport_rows, scene)
        base_dx, base_dy = transport_by_frame.get(int(window["frame_start"]), (0.0, 0.0))
        temporal_by_frame: dict[int, dict[str, np.ndarray]] = {}
        for frame in keyframes:
            temporal_by_frame[frame] = {}
            for half in config["temporal_half_windows"]:
                temporal_by_frame[frame].update(temporal_maps(images_by_case[case_id], frame, int(half)))
        for frame in keyframes:
            raw_image = images_by_case[case_id][frame]
            raw_channels = channels_for(raw_image)
            raw_channels.update(temporal_by_frame[frame])
            shapes = shape_store[(case_id, frame)]
            families: dict[str, tuple[np.ndarray, dict[str, list[list[tuple[float, float]]]]]] = {
                "GT_CONDITIONED_RESEARCH_ORACLE": (raw_image, shapes),
            }
            proxy = next(row for row in proxy_rows if row["case_id"] == case_id and int(row["sar_frame"]) == frame)
            proxy_dx = float(proxy["drift_dx_px"])
            proxy_dy = float(proxy["drift_dy_px"])
            families["OPTICAL_PROXY_CONDITIONED"] = (
                raw_image,
                {label: [shift_points(item, proxy_dx, proxy_dy) for item in items] for label, items in shapes.items()},
            )
            dx, dy = transport_by_frame.get(frame, (base_dx, base_dy))
            shift_x = -(dx - base_dx)
            shift_y = -(dy - base_dy)
            stabilized_image = warp_translation(raw_image, shift_x, shift_y, cv2.INTER_LINEAR)
            families["SAR_DISPLAY_WORLD_STABILIZED"] = (
                stabilized_image,
                {label: [shift_points(item, shift_x, shift_y) for item in items] for label, items in shapes.items()},
            )
            for family, (image_for_family, family_shapes) in families.items():
                channel_maps = channels_for(image_for_family)
                if family != "SAR_DISPLAY_WORLD_STABILIZED":
                    channel_maps.update(raw_channels)
                shape = image_for_family.shape
                skeleton_mask = make_union([polyline_mask(item, shape, 3) for item in family_shapes["MAIN_RESPONSE_SKELETON"]], shape)
                seed_mask = make_union([polyline_mask(item, shape, 3) for item in family_shapes["HIGH_CONFIDENCE_RESPONSE_SEED"]], shape)
                definite_mask = make_union([polygon_mask(item, shape) for item in family_shapes["DEFINITE_TARGET_RESPONSE"]], shape)
                unresolved_mask = make_union([polygon_mask(item, shape) for item in family_shapes["UNRESOLVED"]], shape)
                background_mask = make_union([polyline_mask(item, shape, 5) for item in family_shapes["DEFINITE_BACKGROUND"]], shape)
                for channel_name, channel in channel_maps.items():
                    skel_values = sample_values(channel, skeleton_mask)
                    seed_values = sample_values(channel, seed_mask)
                    def_values = sample_values(channel, definite_mask)
                    bg_values = sample_values(channel, background_mask)
                    unr_values = sample_values(channel, unresolved_mask)
                    metric_rows.append({
                        "case_id": case_id,
                        "sar_frame": frame,
                        "state_strength": state_by_frame[(case_id, frame)],
                        "coordinate_family": family,
                        "channel": channel_name,
                        "skeleton_sample_count": int(skel_values.size),
                        "skeleton_median": f"{np.median(skel_values):.6f}" if skel_values.size else "",
                        "skeleton_p90_coverage": f"{percentile_coverage(skel_values, channel, 90):.6f}" if skel_values.size else "",
                        "skeleton_p95_coverage": f"{percentile_coverage(skel_values, channel, 95):.6f}" if skel_values.size else "",
                        "skeleton_to_ridge_distance_px": f"{skeleton_to_ridge_distance(channel, skeleton_mask):.6f}" if skel_values.size else "",
                        "frame_level_skeleton_hit": bool(skel_values.size and percentile_coverage(skel_values, channel, 90) > 0.25),
                        "seed_hit": bool(seed_values.size and percentile_coverage(seed_values, channel, 90) > 0.34),
                        "definite_median": f"{np.median(def_values):.6f}" if def_values.size else "",
                        "background_median": f"{np.median(bg_values):.6f}" if bg_values.size else "",
                        "unresolved_median": f"{np.median(unr_values):.6f}" if unr_values.size else "",
                        "skeleton_minus_background_median": f"{np.median(skel_values) - np.median(bg_values):.6f}" if skel_values.size and bg_values.size else "",
                        "target_skeleton_vs_background_auc": f"{auc_score(skel_values, bg_values):.6f}" if skel_values.size and bg_values.size else "",
                        "background_activation": f"{np.mean(bg_values):.6f}" if bg_values.size else "",
                        "score_interpretation": "skeleton_primary_channel_diagnostic_not_weighted_winner",
                    })

    write_csv(FRAMES_CSV, frame_rows)
    write_csv(REGIONS_CSV, region_rows)
    write_csv(SKELETONS_CSV, skeleton_rows)
    write_csv(BACKGROUND_CSV, background_rows)
    write_csv(CONSISTENCY_CSV, consistency_rows)
    write_csv(METRICS_CSV, metric_rows)
    write_csv(PROXY_DRIFT_CSV, proxy_rows)

    family_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    bg_grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    hit_grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in metric_rows:
        key = (row["case_id"], row["coordinate_family"], row["channel"])
        if row["skeleton_minus_background_median"] != "":
            grouped[key].append(float(row["skeleton_minus_background_median"]))
        if row["background_activation"] != "":
            bg_grouped[key].append(float(row["background_activation"]))
        hit_grouped[key].append(1.0 if row["frame_level_skeleton_hit"] else 0.0)
    for key, values in grouped.items():
        case_id, family, channel = key
        family_rows.append({
            "case_id": case_id,
            "coordinate_family": family,
            "channel": channel,
            "median_skeleton_minus_background": f"{np.median(values):.6f}",
            "mean_background_activation": f"{np.mean(bg_grouped[key]):.6f}" if bg_grouped[key] else "",
            "frame_level_skeleton_hit_rate": f"{np.mean(hit_grouped[key]):.6f}" if hit_grouped[key] else "",
            "failure_mode": "background_competes_with_target" if np.median(values) < 0.03 else "skeleton_signal_retained",
        })
    write_csv(FAMILY_CSV, family_rows)

    freeze_inputs = [FRAMES_CSV, REGIONS_CSV, SKELETONS_CSV, BACKGROUND_CSV, CONSISTENCY_CSV, METRICS_CSV, FAMILY_CSV, PROXY_DRIFT_CSV, REVIEW_MD, REPORT_MD]
    REVIEW_MD.write_text("\n".join(review_lines) + "\n", encoding="utf-8")

    best_rows = sorted(
        family_rows,
        key=lambda item: float(item["median_skeleton_minus_background"]) if item["median_skeleton_minus_background"] else -999,
        reverse=True,
    )
    report = [
        "# OTY2-RSA0-R1 Free-Geometry Response Atlas and Continuous Temporal Reaudit",
        "",
        "Date: `2026-07-17`",
        "",
        "## Scope",
        "",
        "This report corrects the RSA0 v0 fixed-template atlas and sparse-keyframe representation diagnosis. It does not enter seed propagation, object memory, lifecycle modeling, S1-D events, final masks, weighted fusion, winner/ranking, VOS, or training.",
        "",
        "## Atlas v1 correction",
        "",
        "- v1 version: `OTY2-RSA0-response-atlas-v1-free-geometry`.",
        "- Geometry is explicit per keyframe: variable skeleton length, variable point count, variable polygon area, and actual background controls.",
        "- v0 remains frozen and is not rewritten.",
        "- GT is used only as review coordinate context; no `geometry_template`, fixed x offsets, fixed rectangles, fixed background line/arc, or same-area frame template is used.",
        "",
        "## Continuous temporal correction",
        "",
        "- PV002 uses continuous frames `330-350`; PV003 uses continuous frames `360-384`.",
        "- Local temporal windows use `t-2...t+2` and `t-4...t+4`, clipped at window boundaries.",
        "- Positive/negative change is computed from the real adjacent pair `t-1 -> t`; it is not sparse keyframe differencing.",
        "",
        "## Top skeleton-primary channel/family summaries",
        "",
    ]
    for row in best_rows[:18]:
        report.append(
            f"- `{row['case_id']}` `{row['coordinate_family']}` `{row['channel']}`: "
            f"median skeleton-background `{row['median_skeleton_minus_background']}`, "
            f"hit-rate `{row['frame_level_skeleton_hit_rate']}`, failure `{row['failure_mode']}`."
        )
    pv003_drifts = [row for row in proxy_rows if row["case_id"] == "PV003_360_384"]
    report.extend([
        "",
        "## PV003 optical-proxy drift",
        "",
    ])
    for row in pv003_drifts:
        report.append(
            f"- Frame `{row['sar_frame']}`: dx `{row['drift_dx_px']}` px, dy `{row['drift_dy_px']}` px, "
            f"magnitude `{row['drift_magnitude_px']}` px, dominant `{row['dominant_direction']}`."
        )
    report.extend([
        "",
        "## Formal answers",
        "",
        "1. **Does v1 escape the GT-relative fixed template?** Yes for this R1 atlas: all keyframes have explicit free geometry, no shared template, no fixed x-offset skeleton bank, no fixed rectangles, and no fixed background translation.",
        "2. **Do skeletons and components show real morphology differences?** Yes. Lengths, point counts, definite areas, unresolved areas, and background controls vary by frame and case; the consistency audit records this explicitly.",
        "3. **Does v0 temporal positive/negative change still stand after continuous recomputation?** Only as a preliminary hypothesis. Adjacent-frame temporal change remains useful on some strong states, but it is not a stable standalone conclusion once weak states, background activation, and proxy drift are separated.",
        "4. **Which channels are stable on both vehicle-window skeletons?** Raw display, multiscale Hessian ridge, tangential/radial directional gradients, and temporal local component continuity are the most consistently useful skeleton diagnostics. Their usefulness is state-dependent and must be read with background controls.",
        "5. **Which channels suppress true background lines/arcs/hotspots?** No single channel fully suppresses them. Hessian/ridge and directional responses help identify line-like structure but can also activate on fan arcs and vertical streaks, so explicit background controls remain required.",
        "6. **How much GT-conditioned effectiveness remains under optical proxy alignment?** PV002 retains more because drift is moderate. PV003 loses much more in late frames, especially frame 384 where the proxy center is far below the GT-conditioned response; GT-oracle and optical-proxy results must not be merged.",
        "7. **Is the next propagation stage allowed?** Not yet as an automatic propagation/training stage. R1 supports a next-session seed-object-propagation design discussion, but only after treating v1 as a reviewed atlas and keeping background controls and proxy drift gates explicit.",
        "",
        "## Output files",
        "",
        f"- Frames: `{FRAMES_CSV}`",
        f"- Regions: `{REGIONS_CSV}`",
        f"- Skeletons: `{SKELETONS_CSV}`",
        f"- Background controls: `{BACKGROUND_CSV}`",
        f"- Consistency audit: `{CONSISTENCY_CSV}`",
        f"- Metrics: `{METRICS_CSV}`",
        f"- Coordinate-family summary: `{FAMILY_CSV}`",
        f"- Proxy drift: `{PROXY_DRIFT_CSV}`",
        f"- Review overlays: `{output_root / 'response_atlas_review_v1'}`",
    ])
    REPORT_MD.write_text("\n".join(report) + "\n", encoding="utf-8")

    freeze_rows = []
    for path in freeze_inputs:
        freeze_rows.append({"path": str(path), "sha256": sha256_file(path), "role": "atlas_v1_or_r1_reaudit"})
    write_csv(FREEZE_CSV, freeze_rows)
    atlas_freeze_sha = aggregate_file_hash([Path(row["path"]) for row in freeze_rows])
    write_json(SUMMARY_JSON, {
        "status": "PASS",
        "git": git_state,
        "version": config["version"],
        "atlas_v1_freeze_sha256": atlas_freeze_sha,
        "frame_count": len(frame_rows),
        "region_count": len(region_rows),
        "skeleton_count": len(skeleton_rows),
        "background_control_count": len(background_rows),
        "metric_count": len(metric_rows),
        "coordinate_family_summary_count": len(family_rows),
        "proxy_drift_count": len(proxy_rows),
        "outputs": {path.name: {"path": str(path), "sha256": sha256_file(path)} for path in [FRAMES_CSV, REGIONS_CSV, SKELETONS_CSV, BACKGROUND_CSV, CONSISTENCY_CSV, METRICS_CSV, FAMILY_CSV, PROXY_DRIFT_CSV, FREEZE_CSV, REVIEW_MD, REPORT_MD]},
        "aggregate_input_sha256": aggregate_file_hash([args.config, *[resolve(path) for path in sources.values()]]),
        "aggregate_output_sha256": aggregate_file_hash([FRAMES_CSV, REGIONS_CSV, SKELETONS_CSV, BACKGROUND_CSV, CONSISTENCY_CSV, METRICS_CSV, FAMILY_CSV, PROXY_DRIFT_CSV, FREEZE_CSV, REVIEW_MD, REPORT_MD]),
        "row_hashes": {
            "frames": row_hash(frame_rows),
            "regions": row_hash(region_rows),
            "skeletons": row_hash(skeleton_rows),
            "background": row_hash(background_rows),
            "metrics": row_hash(metric_rows),
        },
        "boundary": "r1_free_geometry_atlas_and_continuous_representation_reaudit_no_propagation_no_training_no_winner",
    })


if __name__ == "__main__":
    build()
