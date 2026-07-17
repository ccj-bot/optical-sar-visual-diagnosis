#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "oty2"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
CONFIG_DIR = REPO_ROOT / "configs" / "oty2"
WORKSPACE_ROOT = Path(r"D:\profile\research\workspace")

FAN_WIDTH = 2308
FAN_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
FAN_THETA_MIN = -90.0
FAN_THETA_MAX = 90.0
FAN_MASK_SHA256 = "7bdfbc5417db5f96405751d7503973f16db85957cf9aa0c6a8f30975cc0502ef"


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
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def aggregate_file_hash(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted((Path(path) for path in paths), key=lambda item: str(item).lower()):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


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


def verify_git_gate(expected_branch: str, expected_start_head: str) -> dict[str, str]:
    branch = git("branch", "--show-current")
    require(branch == expected_branch, f"branch mismatch: {branch}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", expected_start_head, "HEAD"],
        cwd=REPO_ROOT,
        check=False,
    )
    require(ancestor.returncode == 0, "frozen start HEAD is not an ancestor of HEAD")
    return {"branch": branch, "head": git("rev-parse", "HEAD")}


def fmt(value: Any, digits: int = 9) -> str:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return ""
        return f"{float(value):.{digits}f}"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def robust_median_mad(values: np.ndarray) -> tuple[float, float]:
    selected = np.asarray(values, dtype=np.float64)
    selected = selected[np.isfinite(selected)]
    if selected.size == 0:
        return math.nan, math.nan
    median = float(np.median(selected))
    mad = float(np.median(np.abs(selected - median)))
    return median, mad


def fan_radius_theta(x: np.ndarray | float, y: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    xx = np.asarray(x, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    radius = np.hypot(xx - FAN_CENTER_X, yy - FAN_CENTER_Y)
    theta = np.degrees(np.arctan2(xx - FAN_CENTER_X, FAN_CENTER_Y - yy))
    return radius, theta


def fan_xy(radius: np.ndarray | float, theta_deg: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    radius_array = np.asarray(radius, dtype=np.float64)
    theta = np.radians(np.asarray(theta_deg, dtype=np.float64))
    x = FAN_CENTER_X + radius_array * np.sin(theta)
    y = FAN_CENTER_Y - radius_array * np.cos(theta)
    return x, y


def imaging_valid_mask(shape: tuple[int, int] = (FAN_HEIGHT, FAN_WIDTH)) -> np.ndarray:
    height, width = shape
    yy, xx = np.indices((height, width), dtype=np.float64)
    radius, theta = fan_radius_theta(xx, yy)
    return (
        (radius <= FAN_RADIUS_PX)
        & (theta >= FAN_THETA_MIN)
        & (theta <= FAN_THETA_MAX)
    )


def packed_mask_hash(mask: np.ndarray) -> str:
    packed = np.packbits(np.asarray(mask, dtype=np.uint8), bitorder="little")
    return hashlib.sha256(packed.tobytes()).hexdigest()


def annular_sector_mask(
    theta_center_deg: float,
    theta_half_width_deg: float,
    radius_center_px: float,
    radius_half_width_px: float,
    shape: tuple[int, int] = (FAN_HEIGHT, FAN_WIDTH),
) -> np.ndarray:
    height, width = shape
    yy, xx = np.indices((height, width), dtype=np.float64)
    radius, theta = fan_radius_theta(xx, yy)
    angular = np.abs(((theta - theta_center_deg + 180.0) % 360.0) - 180.0)
    mask = (
        (angular <= theta_half_width_deg)
        & (radius >= max(0.0, radius_center_px - radius_half_width_px))
        & (radius <= min(FAN_RADIUS_PX, radius_center_px + radius_half_width_px))
    )
    return mask & imaging_valid_mask(shape)


def mask_bbox(mask: np.ndarray, padding: int = 0) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    require(xs.size > 0, "empty mask has no bounding box")
    x1 = max(0, int(xs.min()) - padding)
    y1 = max(0, int(ys.min()) - padding)
    x2 = min(mask.shape[1], int(xs.max()) + 1 + padding)
    y2 = min(mask.shape[0], int(ys.max()) + 1 + padding)
    return x1, y1, x2, y2


def warp_translation(image: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        flags=interpolation,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    require(image is not None, f"cannot read image: {path}")
    if image.ndim == 3:
        image = image[:, :, 0]
    require(image.shape == (FAN_HEIGHT, FAN_WIDTH), f"unexpected SAR shape {image.shape}: {path}")
    return np.asarray(image, dtype=np.uint8)


def parse_rotated_bbox(text: str) -> tuple[float, float, float, float, float]:
    value = json.loads(text)
    require(isinstance(value, list) and len(value) == 5, f"invalid rotated bbox: {text}")
    return tuple(float(item) for item in value)  # type: ignore[return-value]


def rotated_bbox_mask(
    bbox: tuple[float, float, float, float, float],
    shape: tuple[int, int] = (FAN_HEIGHT, FAN_WIDTH),
) -> np.ndarray:
    cx, cy, width, height, angle = bbox
    points = cv2.boxPoints(((cx, cy), (width, height), angle))
    polygon = np.rint(points).astype(np.int32)
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillConvexPoly(mask, polygon, 1)
    return mask.astype(bool)


def remove_small_components(mask: np.ndarray, minimum_area: int) -> np.ndarray:
    source = np.asarray(mask, dtype=np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(source, connectivity=8)
    output = np.zeros_like(source)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= minimum_area:
            output[labels == label] = 1
    return output.astype(bool)


def connected_component_rows(mask: np.ndarray, prefix: str) -> list[dict[str, Any]]:
    source = np.asarray(mask, dtype=np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(source, connectivity=8)
    rows: list[dict[str, Any]] = []
    for label in range(1, count):
        x, y, width, height, area = [int(value) for value in stats[label]]
        rows.append(
            {
                "object_id": f"{prefix}-{label:04d}",
                "area_px": area,
                "bbox_x1": x,
                "bbox_y1": y,
                "bbox_x2": x + width,
                "bbox_y2": y + height,
                "centroid_x": float(centroids[label, 0]),
                "centroid_y": float(centroids[label, 1]),
            }
        )
    return rows


def row_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(list(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)
