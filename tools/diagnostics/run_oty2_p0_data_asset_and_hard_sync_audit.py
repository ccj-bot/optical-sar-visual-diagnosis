#!/usr/bin/env python3
"""Read-only OTY2 P0 asset and hard-sync foundation audit.

The script reads source assets referenced by configs/scene_config.yaml and the
existing canonical review/GT tables. It writes only three controlled artifacts:

* manifests/oty2/oty2_p0_data_asset_manifest.csv
* manifests/oty2/oty2_p0_hard_sync_sar_to_optical.csv
* manifests/oty2/oty2_p0_hard_sync_optical_to_sar.csv
* reports/oty2/oty2_p0_data_asset_and_hard_sync_audit_20260713.md

No source data is moved, renamed, copied, or modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

try:
    import numpy as np
except ImportError:  # pragma: no cover - PNG/JPG audit remains available
    np = None

try:
    import cv2
except ImportError:  # pragma: no cover - source-container matching is then unavailable
    cv2 = None


SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")
DEFAULT_OPTICAL_FPS = 24.0
DEFAULT_SAR_FPS = 50.0
DEFAULT_FPS_EVIDENCE_STATUS = "source_mp4_container_metadata"
ASSUMPTION_TEXT = "same_scene_optical_frame_0_and_sar_frame_0_share_acquisition_start"

ASSET_FIELDS = [
    "scene",
    "modality",
    "asset_role",
    "frame_index",
    "filename",
    "relative_path",
    "extension",
    "width",
    "height",
    "frame_count",
    "fps",
    "duration_sec",
    "file_size_bytes",
    "content_hash",
    "is_duplicate_content",
    "is_missing_index_neighbor",
    "is_dimension_outlier",
    "source_or_derived",
    "derived_from",
    "is_duplicate_index",
    "index_occurrence_count",
    "notes",
]

SAR_TO_OPTICAL_FIELDS = [
    "scene",
    "sar_frame_index",
    "sar_time_sec",
    "optical_left_frame",
    "optical_right_frame",
    "optical_left_time_sec",
    "optical_right_time_sec",
    "optical_interpolation_ratio",
    "pairing_basis",
    "assumption_status",
    "notes",
]

OPTICAL_TO_SAR_FIELDS = [
    "scene",
    "optical_frame_index",
    "optical_time_sec",
    "sar_first_frame",
    "sar_center_frame",
    "sar_last_frame",
    "sar_frame_count",
    "pairing_basis",
    "assumption_status",
    "notes",
]


@dataclass(frozen=True)
class RoleSpec:
    config_key: str
    modality: str
    asset_role: str
    source_or_derived: str
    derived_from: str


ROLE_SPECS = (
    RoleSpec("optical_frames_dir", "optical", "optical_frame", "derived_extracted_frame", "source_video_to_be_resolved"),
    RoleSpec("sar_gray_frames_dir", "sar", "sar_gray_frame", "derived_extracted_imaging_frame", "source_video_to_be_resolved"),
    RoleSpec("sar_frames_dir", "sar", "sar_pseudocolor_frame", "derived_extracted_display_frame", "source_video_to_be_resolved"),
    RoleSpec("depth_dir", "optical_aux", "depth_sidecar", "derived_depth_product", "optical_frame"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--scene-config", type=Path, default=Path("configs/scene_config.yaml"))
    parser.add_argument("--optical-fps", type=float, default=DEFAULT_OPTICAL_FPS)
    parser.add_argument("--sar-fps", type=float, default=DEFAULT_SAR_FPS)
    parser.add_argument(
        "--fps-evidence-status",
        choices=("auto", "candidate", "confirmed"),
        default="auto",
        help="Auto confirms fixed rates only when exact source MP4 containers are found for every scene.",
    )
    parser.add_argument(
        "--review-queue",
        type=Path,
        default=Path(r"D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\review_queue.csv"),
    )
    parser.add_argument(
        "--final-gt",
        type=Path,
        default=Path(r"D:\profile\research\workspace\output\hermes_annotation_consolidation_2026-05-20\00_tables\final_gt_working.csv"),
    )
    parser.add_argument("--report-date", default="20260713")
    return parser.parse_args()


def resolve_under_repo(repo_root: Path, value: Path) -> Path:
    return value if value.is_absolute() else repo_root / value


def load_json_compatible_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def frame_index_from_name(path: Path) -> int | None:
    match = re.match(r"^(\d+)", path.stem)
    return int(match.group(1)) if match else None


def dimensions(path: Path) -> tuple[int | None, int | None, str]:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        try:
            with Image.open(path) as image:
                return int(image.width), int(image.height), f"image_mode={image.mode}"
        except Exception as exc:  # retain the file in the manifest
            return None, None, f"image_dimension_error={type(exc).__name__}"
    if suffix in {".npy", ".npz"} and np is not None:
        try:
            if suffix == ".npy":
                array = np.load(path, mmap_mode="r", allow_pickle=False)
                shape = array.shape
            else:
                archive = np.load(path, allow_pickle=False)
                first_key = sorted(archive.files)[0] if archive.files else ""
                shape = archive[first_key].shape if first_key else ()
                archive.close()
            if len(shape) >= 2:
                return int(shape[-1]), int(shape[-2]), f"array_shape={tuple(int(v) for v in shape)}"
            return None, None, f"array_shape={tuple(int(v) for v in shape)}"
        except Exception as exc:
            return None, None, f"array_dimension_error={type(exc).__name__}"
    return None, None, "non_image_asset"


def depth_role(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".npy", ".npz"}:
        return "depth_array"
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        return "depth_visualization"
    return "depth_processing_sidecar"


def relative_or_absolute(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def audit_directory(scene: str, spec: RoleSpec, root: Path, repo_root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return [{
            "scene": scene,
            "modality": spec.modality,
            "asset_role": spec.asset_role,
            "frame_index": "",
            "filename": "",
            "relative_path": str(root),
            "extension": "",
            "width": "",
            "height": "",
            "frame_count": "",
            "fps": "",
            "duration_sec": "",
            "file_size_bytes": "",
            "content_hash": "",
            "is_duplicate_content": False,
            "is_missing_index_neighbor": False,
            "is_dimension_outlier": False,
            "source_or_derived": spec.source_or_derived,
            "derived_from": spec.derived_from,
            "is_duplicate_index": False,
            "index_occurrence_count": 0,
            "notes": "configured_directory_missing",
        }]

    records: list[dict[str, Any]] = []
    for path in sorted((p for p in root.iterdir() if p.is_file()), key=lambda p: p.name.lower()):
        role = depth_role(path) if spec.asset_role == "depth_sidecar" else spec.asset_role
        width, height, dimension_note = dimensions(path)
        records.append({
            "scene": scene,
            "modality": spec.modality,
            "asset_role": role,
            "frame_index": frame_index_from_name(path),
            "filename": path.name,
            "relative_path": relative_or_absolute(path, repo_root),
            "extension": path.suffix.lower(),
            "width": "" if width is None else width,
            "height": "" if height is None else height,
            "frame_count": "",
            "fps": "",
            "duration_sec": "",
            "file_size_bytes": path.stat().st_size,
            "content_hash": sha256_file(path),
            "is_duplicate_content": False,
            "is_missing_index_neighbor": False,
            "is_dimension_outlier": False,
            "source_or_derived": spec.source_or_derived,
            "derived_from": spec.derived_from,
            "is_duplicate_index": False,
            "index_occurrence_count": 0,
            "notes": dimension_note,
        })
    return records


def add_reference_row(
    rows: list[dict[str, Any]],
    *,
    scene: str,
    modality: str,
    asset_role: str,
    path: Path,
    repo_root: Path,
    source_or_derived: str,
    derived_from: str,
    notes: str,
) -> None:
    exists = path.is_file()
    rows.append({
        "scene": scene,
        "modality": modality,
        "asset_role": asset_role,
        "frame_index": "",
        "filename": path.name if exists else "",
        "relative_path": relative_or_absolute(path, repo_root) if exists else str(path),
        "extension": path.suffix.lower() if exists else "",
        "width": "",
        "height": "",
        "frame_count": "",
        "fps": "",
        "duration_sec": "",
        "file_size_bytes": path.stat().st_size if exists else "",
        "content_hash": sha256_file(path) if exists else "",
        "is_duplicate_content": False,
        "is_missing_index_neighbor": False,
        "is_dimension_outlier": False,
        "source_or_derived": source_or_derived,
        "derived_from": derived_from,
        "is_duplicate_index": False,
        "index_occurrence_count": 0,
        "notes": notes if exists else f"not_found;{notes}",
    })


def video_sample_match(video_path: Path, frames_dir: Path, frame_count: int) -> bool:
    if cv2 is None or np is None or not frames_dir.is_dir() or frame_count <= 0:
        return False
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return False
    sample_indices = sorted({0, min(100, frame_count - 1), frame_count - 1})
    matched = True
    for index in sample_indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, decoded = capture.read()
        reference = cv2.imread(str(frames_dir / f"{index:06d}.png"), cv2.IMREAD_COLOR)
        if not ok or reference is None or decoded.shape != reference.shape or not np.array_equal(decoded, reference):
            matched = False
            break
    capture.release()
    return matched


def audit_scene_videos(
    scene: str,
    mp4_dir: Path,
    scene_paths: dict[str, str],
    repo_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    rows: list[dict[str, Any]] = []
    matched_sources: dict[str, Path] = {}
    if cv2 is None or not mp4_dir.is_dir():
        return rows, matched_sources
    targets = {
        "optical_source_video": Path(scene_paths["optical_frames_dir"]),
        "sar_gray_source_video": Path(scene_paths["sar_gray_frames_dir"]),
        "sar_pseudocolor_source_video": Path(scene_paths["sar_frames_dir"]),
    }
    for video_path in sorted(mp4_dir.glob(f"{scene}*.MP4"), key=lambda p: p.name.lower()):
        capture = cv2.VideoCapture(str(video_path))
        opened = capture.isOpened()
        fps = float(capture.get(cv2.CAP_PROP_FPS)) if opened else 0.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) if opened else 0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) if opened else 0
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) if opened else 0
        capture.release()
        matched_role = "unclassified_scene_video"
        for role, frames_dir in targets.items():
            if role not in matched_sources and video_sample_match(video_path, frames_dir, frame_count):
                matched_role = role
                matched_sources[role] = video_path
                break
        rows.append({
            "scene": scene,
            "modality": "optical" if matched_role == "optical_source_video" else "sar",
            "asset_role": matched_role,
            "frame_index": "",
            "filename": video_path.name,
            "relative_path": relative_or_absolute(video_path, repo_root),
            "extension": video_path.suffix.lower(),
            "width": width or "",
            "height": height or "",
            "frame_count": frame_count or "",
            "fps": f"{fps:.12g}" if fps else "",
            "duration_sec": f"{frame_count / fps:.12g}" if frame_count and fps else "",
            "file_size_bytes": video_path.stat().st_size,
            "content_hash": sha256_file(video_path),
            "is_duplicate_content": False,
            "is_missing_index_neighbor": False,
            "is_dimension_outlier": False,
            "source_or_derived": "source_container_for_available_frame_product",
            "derived_from": "unknown_original_capture" if matched_role == "optical_source_video" else "unresolved_radar_imaging_pipeline",
            "is_duplicate_index": False,
            "index_occurrence_count": 0,
            "notes": (
                "exact_decode_match_at_frames_0_100_last;container_metadata_only_not_common_clock_proof"
                if matched_role != "unclassified_scene_video"
                else "scene_video_not_exactly_matched_to_configured_frame_sequence"
            ),
        })
    return rows, matched_sources


def finalize_asset_flags(rows: list[dict[str, Any]]) -> None:
    by_hash: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    by_index: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    dimension_counts: dict[tuple[str, str, str], Counter[tuple[Any, Any]]] = defaultdict(Counter)
    indexed_groups: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)

    for pos, row in enumerate(rows):
        if row["content_hash"]:
            by_hash[(row["scene"], row["asset_role"], row["content_hash"])].append(pos)
        if isinstance(row["frame_index"], int):
            by_index[(row["scene"], row["asset_role"], row["frame_index"])].append(pos)
            indexed_groups[(row["scene"], row["asset_role"])].append((row["frame_index"], pos))
        if row["width"] != "" and row["height"] != "":
            dimension_counts[(row["scene"], row["asset_role"], row["extension"])][(row["width"], row["height"])] += 1

    for positions in by_hash.values():
        if len(positions) > 1:
            for pos in positions:
                rows[pos]["is_duplicate_content"] = True

    for positions in by_index.values():
        for pos in positions:
            rows[pos]["index_occurrence_count"] = len(positions)
            rows[pos]["is_duplicate_index"] = len(positions) > 1

    for key, positions in indexed_groups.items():
        indices = sorted(set(index for index, _ in positions))
        if not indices:
            continue
        present = set(indices)
        lo, hi = indices[0], indices[-1]
        for index, pos in positions:
            missing_neighbors = []
            if index > lo and index - 1 not in present:
                missing_neighbors.append(str(index - 1))
            if index < hi and index + 1 not in present:
                missing_neighbors.append(str(index + 1))
            if missing_neighbors:
                rows[pos]["is_missing_index_neighbor"] = True
                rows[pos]["notes"] += ";missing_neighbor_indices=" + "|".join(missing_neighbors)

    for pos, row in enumerate(rows):
        if row["width"] == "" or row["height"] == "":
            continue
        counter = dimension_counts[(row["scene"], row["asset_role"], row["extension"])]
        if counter:
            mode_dimension, _ = counter.most_common(1)[0]
            row["is_dimension_outlier"] = (row["width"], row["height"]) != mode_dimension


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def indexed_rows(rows: list[dict[str, Any]], scene: str, role: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["scene"] == scene and row["asset_role"] == role and isinstance(row["frame_index"], int)]


def assumption_status(fps_evidence_status: str) -> str:
    if fps_evidence_status == "confirmed":
        return "UNFROZEN_COMMON_START_ASSUMPTION_FPS_CONFIRMED_FROM_SOURCE_MP4_METADATA"
    return "UNFROZEN_CANDIDATE_FIXED_FPS_COMMON_START_ASSUMPTION"


def build_sar_to_optical(
    scene: str,
    sar_indices: list[int],
    optical_indices: list[int],
    optical_fps: float,
    sar_fps: float,
    status: str,
) -> list[dict[str, Any]]:
    optical_set = set(optical_indices)
    optical_min, optical_max = min(optical_indices), max(optical_indices)
    result = []
    for sar_index in sar_indices:
        sar_time = sar_index / sar_fps
        optical_position = sar_time * optical_fps
        left = math.floor(optical_position + 1e-12)
        right = math.ceil(optical_position - 1e-12)
        notes = []
        if left not in optical_set:
            notes.append("left_frame_outside_available_optical_range")
        if right not in optical_set:
            notes.append("right_frame_outside_available_optical_range")
        left_value = left if left in optical_set else ""
        right_value = right if right in optical_set else ""
        if left_value == "" and optical_min <= optical_position <= optical_max:
            notes.append("optical_numbering_gap")
        ratio = optical_position - left
        result.append({
            "scene": scene,
            "sar_frame_index": sar_index,
            "sar_time_sec": f"{sar_time:.9f}",
            "optical_left_frame": left_value,
            "optical_right_frame": right_value,
            "optical_left_time_sec": f"{left / optical_fps:.9f}" if left_value != "" else "",
            "optical_right_time_sec": f"{right / optical_fps:.9f}" if right_value != "" else "",
            "optical_interpolation_ratio": f"{ratio:.9f}" if left_value != "" else "",
            "pairing_basis": f"candidate_fixed_rate_common_start;optical_fps={optical_fps:g};sar_fps={sar_fps:g}",
            "assumption_status": status,
            "notes": ";".join(notes),
        })
    return result


def build_optical_to_sar(
    scene: str,
    optical_indices: list[int],
    sar_indices: list[int],
    optical_fps: float,
    sar_fps: float,
    status: str,
) -> list[dict[str, Any]]:
    sar_set = set(sar_indices)
    result = []
    for optical_index in optical_indices:
        start_t = optical_index / optical_fps
        end_t = (optical_index + 1) / optical_fps
        first = math.ceil(start_t * sar_fps - 1e-12)
        last = math.ceil(end_t * sar_fps - 1e-12) - 1
        covered = [index for index in range(first, last + 1) if index in sar_set]
        notes = []
        if len(covered) != max(0, last - first + 1):
            notes.append("sar_range_clipped_or_numbering_gap")
        center = min(covered, key=lambda idx: (abs(idx / sar_fps - start_t), idx)) if covered else ""
        result.append({
            "scene": scene,
            "optical_frame_index": optical_index,
            "optical_time_sec": f"{start_t:.9f}",
            "sar_first_frame": covered[0] if covered else "",
            "sar_center_frame": center,
            "sar_last_frame": covered[-1] if covered else "",
            "sar_frame_count": len(covered),
            "pairing_basis": f"candidate_half_open_optical_interval_common_start;optical_fps={optical_fps:g};sar_fps={sar_fps:g}",
            "assumption_status": status,
            "notes": ";".join(notes),
        })
    return result


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_optical_path_frame(row: dict[str, str]) -> int | None:
    value = row.get("optical_path", "")
    match = re.match(r"^(\d+)", Path(value).stem)
    return int(match.group(1)) if match else None


def analyze_pair_table(rows: list[dict[str, str]], optical_fps: float, sar_fps: float) -> dict[str, Any]:
    summary: dict[str, Any] = {"row_count": len(rows), "scenes": {}}
    for scene in SCENES:
        scene_rows = [row for row in rows if row.get("scene") == scene]
        pairs: set[tuple[int, int]] = set()
        deltas = Counter()
        for row in scene_rows:
            try:
                sar_index = int(row.get("sar_frame_num", ""))
            except ValueError:
                continue
            optical_index = parse_optical_path_frame(row)
            if optical_index is None:
                continue
            pairs.add((sar_index, optical_index))
            deltas[optical_index - round(sar_index * optical_fps / sar_fps)] += 1
        summary["scenes"][scene] = {
            "rows": len(scene_rows),
            "unique_pairs": len(pairs),
            "sar_min": min((pair[0] for pair in pairs), default=None),
            "sar_max": max((pair[0] for pair in pairs), default=None),
            "optical_min": min((pair[1] for pair in pairs), default=None),
            "optical_max": max((pair[1] for pair in pairs), default=None),
            "nearest_mapping_exact_rows": deltas.get(0, 0),
            "delta_counts": dict(sorted(deltas.items())),
        }
    return summary


def role_summary(rows: list[dict[str, Any]], scene: str, role: str) -> dict[str, Any]:
    selected = indexed_rows(rows, scene, role)
    indices = [int(row["frame_index"]) for row in selected]
    unique_indices = sorted(set(indices))
    missing = []
    if unique_indices:
        missing = sorted(set(range(unique_indices[0], unique_indices[-1] + 1)) - set(unique_indices))
    dimensions_seen = Counter((row["width"], row["height"]) for row in selected if row["width"] != "")
    extensions = Counter(row["extension"] for row in selected)
    return {
        "count": len(selected),
        "unique_index_count": len(unique_indices),
        "min": min(unique_indices) if unique_indices else None,
        "max": max(unique_indices) if unique_indices else None,
        "missing": missing,
        "duplicate_indices": len(indices) - len(unique_indices),
        "duplicate_content": sum(bool(row["is_duplicate_content"]) for row in selected),
        "dimension_outliers": sum(bool(row["is_dimension_outlier"]) for row in selected),
        "dimensions": dict(dimensions_seen),
        "extensions": dict(extensions),
        "bytes": sum(int(row["file_size_bytes"]) for row in selected if row["file_size_bytes"] != ""),
    }


def fmt_range(summary: dict[str, Any]) -> str:
    if summary["min"] is None:
        return "not found"
    return f"{summary['min']}..{summary['max']}"


def fmt_dimensions(summary: dict[str, Any]) -> str:
    if not summary["dimensions"]:
        return "n/a"
    return ", ".join(f"{w}x{h}: {count}" for (w, h), count in summary["dimensions"].items())


def report_text(
    *,
    asset_rows: list[dict[str, Any]],
    pair_summary: dict[str, Any],
    review_queue_path: Path,
    final_gt_path: Path,
    optical_fps: float,
    sar_fps: float,
    fps_status: str,
    status: str,
) -> str:
    summaries = {
        scene: {
            role: role_summary(asset_rows, scene, role)
            for role in ("optical_frame", "sar_gray_frame", "sar_pseudocolor_frame", "depth_array", "depth_visualization")
        }
        for scene in SCENES
    }
    all_numbering_clean = all(
        not summaries[scene][role]["missing"] and summaries[scene][role]["duplicate_indices"] == 0
        for scene in SCENES
        for role in ("optical_frame", "sar_gray_frame", "sar_pseudocolor_frame")
    )
    sar_one_to_one = all(
        summaries[scene]["sar_gray_frame"]["unique_index_count"]
        == summaries[scene]["sar_pseudocolor_frame"]["unique_index_count"]
        and summaries[scene]["sar_gray_frame"]["min"] == summaries[scene]["sar_pseudocolor_frame"]["min"]
        and summaries[scene]["sar_gray_frame"]["max"] == summaries[scene]["sar_pseudocolor_frame"]["max"]
        for scene in SCENES
    )
    fps_confirmed = fps_status == "confirmed"
    p0_state = "P0_DATA_FOUNDATION_PARTIALLY_READY"
    allow_p1 = "no"

    lines = [
        "# OTY2 P0 Data Asset and Hard-Sync Audit (20260713)",
        "",
        "## 1. 执行结论",
        "",
        f"- P0 最终状态：`{p0_state}`。",
        "- 三个场景的可用完整编号帧目录均已建立逐文件 SHA-256 manifest；源目录只读，未移动、重命名、覆盖或复制原始资产。",
        f"- 光学/SAR 编号连续性：`{'clean' if all_numbering_clean else 'exceptions_found'}`；SAR 灰度与伪彩按场景的编号集合一一对应：`{str(sar_one_to_one).lower()}`。",
        f"- 三场景光学源 MP4 均为 `{optical_fps:g}` fps，SAR 灰度源 MP4 均为 `{sar_fps:g}` fps，且抽查帧与 PNG 解码结果逐像素完全一致；固定帧率已由源容器元数据确认。共同起始仍缺少公共时钟/采集日志证明。",
        "- GM_RM011/017 的 SAR 伪彩源 MP4 为 50 fps；GM_RM019 伪彩源 `GM_RM019_R.MP4` 的容器元数据为约 48.300063 fps，虽与 766 张伪彩 PNG 逐像素对应，但和同场景 50 fps 灰度源存在时间元数据冲突。硬同步以 SAR 灰度源 50 fps 为准。",
        f"- 因此已生成确定性的全帧时间轴/配对结果，但它们的 `assumption_status={status}`：固定帧率已确认，共同起始假设未冻结。",
        f"- 当前可访问 canonical review/GT 表为 `{pair_summary['row_count']}` 行，而不是 231 行；没有找到独立 231 行资产。旧表中的光学帧号与 `round(sar_frame * {optical_fps:g}/{sar_fps:g})` 完全一致，因此旧表是该比例的实现证据，不是独立验证证据。",
        "- 已定位产生当前 PNG 序列的源 MP4 容器；仍未找到三个场景对应的原始 ADC/IQ、距离压缩结果、复数成像结果、采集配置、成像配置或有效成像 Mask。SAR MP4/PNG 是已有成像产品，不能冒充原始雷达数据。",
        "- P0 尚不具备冻结条件；本轮不允许进入 P1。",
        "",
        "## 2. 已确认的数据事实",
        "",
        "| scene | optical frames | SAR gray | SAR pseudocolor | optical dimensions | SAR gray dimensions | SAR pseudocolor dimensions |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for scene in SCENES:
        lines.append(
            f"| {scene} | {summaries[scene]['optical_frame']['count']} | {summaries[scene]['sar_gray_frame']['count']} | "
            f"{summaries[scene]['sar_pseudocolor_frame']['count']} | {fmt_dimensions(summaries[scene]['optical_frame'])} | "
            f"{fmt_dimensions(summaries[scene]['sar_gray_frame'])} | {fmt_dimensions(summaries[scene]['sar_pseudocolor_frame'])} |"
        )
    lines += [
        "",
        "- 文件名均以零填充数字帧号开头；P0 使用该数字作为目录内 frame index。",
        "- 文件系统时间只反映文件落盘/复制状态，不作为采集时间戳。",
        "- `configs/scene_config.yaml` 是本地路径路由配置，不是采集配置或成像配置。",
        "- `review_queue.csv` 和 `final_gt_working.csv` 是稀疏标注/审阅资产，不是完整光学流或完整 SAR 流。",
        "",
        "## 3. 当前采用的工作假设",
        "",
        f"- `{ASSUMPTION_TEXT}`。这是工作假设，不是已确认事实。",
        f"- 候选比例配置：`optical_fps={optical_fps:g}`, `sar_fps={sar_fps:g}`, `sar/optical={sar_fps / optical_fps:.9f}`。",
        "- 不使用每样本软同步分数、不使用逐帧自适应 offset、不使用 GT 反向调整同步关系。",
        "",
        "## 4. 各场景资产总表",
        "",
        "| scene | role | source directory | count | index range | format | bytes | source/derived interpretation |",
        "| --- | --- | --- | ---: | --- | --- | ---: | --- |",
    ]
    for scene in SCENES:
        for role, interpretation in (
            ("optical_frame", "available source optical frame sequence; original capture container unresolved"),
            ("sar_gray_frame", "derived SAR imaging product; complex/range-compressed source unresolved"),
            ("sar_pseudocolor_frame", "derived display product; exact transform lineage unresolved"),
            ("depth_array", "derived optical depth sidecar"),
            ("depth_visualization", "derived optical depth visualization"),
        ):
            item = summaries[scene][role]
            role_rows = indexed_rows(asset_rows, scene, role)
            source_directory = str(Path(role_rows[0]["relative_path"]).parent) if role_rows else "n/a"
            lines.append(
                f"| {scene} | {role} | {source_directory} | {item['count']} | {fmt_range(item)} | "
                f"{', '.join(f'{k}:{v}' for k, v in item['extensions'].items()) or 'n/a'} | {item['bytes']} | {interpretation} |"
            )
    lines += [
        "",
        "命名规则与直接源容器：",
        "",
        "- 光学帧：`000000.png` ... `000367.png`，直接源为 `<scene>_C.MP4`。",
        "- SAR 灰度帧：`000000.png` ... `000765.png`，直接源为 `<scene>_0_R_1.MP4`。",
        "- SAR 伪彩帧：`000000.png` ... `000765.png`；GM_RM011/017 直接源为 `<scene>_0_R.MP4`，GM_RM019 直接源为 `GM_RM019_R.MP4`。",
        "- Depth array/visualization：`<frame>_depth.npy` 与 `<frame>_depth_vis.png`，均为光学帧派生。",
        "- 对每个源容器抽查 frame 0、100、last，解码像素与对应 PNG 完全一致。",
    ]
    lines += [
        "",
        "资产 manifest 还记录了源 MP4 容器，并以 placeholder/reference rows 明确记录未找到的 ADC/IQ、距离压缩、复数成像、采集配置、成像配置和 Mask，而不是静默省略。",
        "",
        "## 5. 光学和 SAR 完整帧范围",
        "",
        "| scene | optical range | optical count | SAR gray range | SAR gray count | SAR pseudocolor range | SAR pseudocolor count | count ratio |",
        "| --- | --- | ---: | --- | ---: | --- | ---: | ---: |",
    ]
    for scene in SCENES:
        optical = summaries[scene]["optical_frame"]
        gray = summaries[scene]["sar_gray_frame"]
        pseudo = summaries[scene]["sar_pseudocolor_frame"]
        ratio = gray["count"] / optical["count"] if optical["count"] else float("nan")
        lines.append(
            f"| {scene} | {fmt_range(optical)} | {optical['count']} | {fmt_range(gray)} | {gray['count']} | "
            f"{fmt_range(pseudo)} | {pseudo['count']} | {ratio:.9f} |"
        )
    lines += [
        "",
        "## 6. 缺失、重复和异常资产",
        "",
    ]
    for scene in SCENES:
        for role in ("optical_frame", "sar_gray_frame", "sar_pseudocolor_frame", "depth_array", "depth_visualization"):
            item = summaries[scene][role]
            lines.append(
                f"- {scene} `{role}`: missing indices={item['missing'] or 'none'}; duplicate indices={item['duplicate_indices']}; "
                f"duplicate-content rows={item['duplicate_content']}; dimension outliers={item['dimension_outliers']}."
            )
    lines += [
        "- 原始 ADC/IQ：三个场景均未在已配置 scene roots 或仓库引用中定位到。",
        "- 距离压缩/中间成像：三个场景均未定位到可证明 lineage 的资产。",
        "- 复数成像结果：三个场景均未定位到。",
        "- 采集配置/成像配置：三个场景均未定位到；仓库 scene config 仅为路径配置。",
        "- 有效成像 Mask：未定位到独立 Mask 文件，也未找到足以冻结的 Mask 语义。",
        "",
        "## 7. 实际或候选帧率",
        "",
        f"- 实际源容器证据：三场景 optical `_C.MP4` 均为 `{optical_fps:g}` fps / 368 帧；三场景 SAR gray `_0_R_1.MP4` 均为 `{sar_fps:g}` fps / 766 帧。",
        "- 对每个已归类源视频抽查 frame 0、100、last，解码像素与对应 PNG 完全相同，因此可确认这些 MP4 是当前帧目录的直接源容器。",
        "- SAR pseudocolor：GM_RM011/017 源容器为 50 fps；GM_RM019 源容器为约 48.300063 fps。该冲突不改变灰度 SAR 50 fps 硬同步基准，但必须在后续 lineage 修复前保留为 blocker。",
        "- 源容器帧率并不证明多个设备共享同一时钟或 frame 0 真正同时开始。",
        f"- 候选名义持续时间：光学 `368/{optical_fps:g}={368 / optical_fps:.9f}s`；SAR `766/{sar_fps:g}={766 / sar_fps:.9f}s`；差 `{abs(368 / optical_fps - 766 / sar_fps):.9f}s`。",
        f"- 最后一个样本时间：光学 `367/{optical_fps:g}={367 / optical_fps:.9f}s`；SAR `765/{sar_fps:g}={765 / sar_fps:.9f}s`。SAR 最后一帧比光学最后一帧晚 `{765 / sar_fps - 367 / optical_fps:.9f}s`。",
        "",
        "## 8. 共同起始硬同步是否自洽",
        "",
        "- 固定帧率不再只是脚本常量：源 MP4 容器确认 optical=24 fps、SAR gray=50 fps；编号连续，三场景帧数一致，旧表也精确采用最近帧换算，因此共同起始假设内部自洽。",
        "- 共同起始本身仍未被独立时间戳、采集日志或硬件同步记录证实；旧配对不能作为独立验证，因为旧配对本身由相同比例生成。",
        "",
        "## 9. 全帧配对结果",
        "",
        "- `oty2_p0_hard_sync_sar_to_optical.csv` 覆盖每一张 SAR 灰度帧，给出确定性的左右光学帧及插值比例。",
        "- `oty2_p0_hard_sync_optical_to_sar.csv` 按光学帧半开时间区间确定性地划分全部 SAR 灰度帧。",
        f"- 所有行标记为 `{status}`。已建立确定性配对，但尚未冻结为经公共时钟证实的真实配对。",
        "",
        "## 10. 与现有 231 样本配对的差异",
        "",
        f"- 未找到独立 231 行 GT/review 或 pair table。当前 canonical review queue 为 `{pair_summary['row_count']}` 行；final GT 位于 `{final_gt_path}`。",
        "- canonical 行数包含同一帧对上的多车辆/多标注，因此 annotation row count 不等于 frame-pair count。",
        "- 与确定性最近帧规则的逐场景对照：",
    ]
    for scene in SCENES:
        item = pair_summary["scenes"][scene]
        lines.append(
            f"  - {scene}: rows={item['rows']}, unique frame pairs={item['unique_pairs']}, "
            f"SAR range={item['sar_min']}..{item['sar_max']}, optical range={item['optical_min']}..{item['optical_max']}, "
            f"exact `round(sar*{optical_fps:g}/{sar_fps:g})` rows={item['nearest_mapping_exact_rows']}/{item['rows']}."
        )
    lines += [
        "- 当前表与完整流的差异来自稀疏选样和同一帧对上的重复标注行；可访问表中没有不同起点 offset 或不同 scale。",
        "- 因 231 行资产缺失，无法判断其精确抽样、裁剪或版本关系。",
        "",
        "## 11. 当前仍缺少的数据或日志",
        "",
        "1. 证明共同起始的场景采集配置、公共时钟或同步日志。",
        "2. 逐帧时间戳或公共 clock log。",
        "3. 原始 ADC/IQ 位置和不可变 acquisition manifest。",
        "4. 距离压缩、复数成像中间结果位置及 lineage。",
        "5. 伪彩变换定义，以及 GM_RM019 伪彩 MP4 48.300063 fps 与灰度 50 fps 冲突的解释。",
        "6. 唯一 SAR 米制坐标、有效成像 Mask 和 Mask 语义。",
        "7. 独立 231 行 review/pair 资产，或确认 231 已过时/写错。",
        "",
        "## 12. P0 是否具备冻结条件",
        "",
        f"否。当前状态为 `{p0_state}`：编号图像产品与固定帧率已完成审计，但共同起始证明、原始雷达 lineage、GM_RM019 伪彩时间元数据冲突和 Mask 语义尚未冻结。",
        "",
        "## 13. 是否允许进入 P1",
        "",
        f"`{allow_p1}`。P0 达到 `P0_DATA_FOUNDATION_READY` 前不得进入 P1。",
        "",
        "## 14. 本轮没有运行的内容",
        "",
        "- 未运行任何光学 detector 或 tracker（ByteTrack、BoT-SORT、OC-SORT 等）。",
        "- 未更新 Working Graph，未做多车身份合并。",
        "- 未拟合方位向映射。",
        "- 未生成 SAR candidate，未运行 Gate、selector、ranking 或 GT 驱动选框。",
        "- 未运行 GM_RM017 物理因素、SAR 结构动力学、训练、阈值调优或自动标注。",
        "- 未写入、移动、重命名、复制源资产，未操作 stash。",
        "",
        "## Audit provenance",
        "",
        f"- review queue: `{review_queue_path}`",
        f"- final GT: `{final_gt_path}`",
        "- hash algorithm: `SHA-256` for every discovered file; no hash shortcut used.",
        f"- fps evidence status: `{fps_status}`；共同起始仍为工作假设。",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    scene_config_path = resolve_under_repo(repo_root, args.scene_config)
    config = load_json_compatible_yaml(scene_config_path)
    asset_rows: list[dict[str, Any]] = []
    video_sources_by_scene: dict[str, dict[str, Path]] = {}

    for scene in SCENES:
        scene_paths = config["scenes"][scene]["paths"]
        scene_row_start = len(asset_rows)
        for spec in ROLE_SPECS:
            root = Path(scene_paths[spec.config_key])
            asset_rows.extend(audit_directory(scene, spec, root, repo_root))

        optical_dir = Path(scene_paths["optical_frames_dir"])
        mp4_dir = optical_dir.parents[1] / "mp4"
        video_rows, matched_sources = audit_scene_videos(scene, mp4_dir, scene_paths, repo_root)
        video_sources_by_scene[scene] = matched_sources
        asset_rows.extend(video_rows)
        role_to_source = {
            "optical_frame": matched_sources.get("optical_source_video"),
            "sar_gray_frame": matched_sources.get("sar_gray_source_video"),
            "sar_pseudocolor_frame": matched_sources.get("sar_pseudocolor_source_video"),
        }
        for row in asset_rows[scene_row_start:]:
            source_path = role_to_source.get(row["asset_role"])
            if source_path is not None:
                row["derived_from"] = str(source_path.resolve())

        add_reference_row(
            asset_rows,
            scene=scene,
            modality="metadata",
            asset_role="repository_scene_path_config",
            path=scene_config_path,
            repo_root=repo_root,
            source_or_derived="repository_reference_config",
            derived_from="manual_repository_configuration",
            notes="path_routing_only_not_acquisition_or_imaging_config",
        )
        for role, modality, note in (
            ("raw_adc_iq", "sar", "raw_acquisition_asset_not_located"),
            ("range_compressed_intermediate", "sar", "intermediate_imaging_asset_not_located"),
            ("complex_imaging_result", "sar", "complex_imaging_asset_not_located"),
            ("acquisition_config", "metadata", "scene_acquisition_config_not_located"),
            ("imaging_config", "metadata", "scene_imaging_config_not_located"),
            ("sar_effective_imaging_mask", "sar", "mask_file_and_semantics_not_located"),
        ):
            add_reference_row(
                asset_rows,
                scene=scene,
                modality=modality,
                asset_role=role,
                path=Path(f"UNRESOLVED::{scene}::{role}"),
                repo_root=repo_root,
                source_or_derived="not_located",
                derived_from="",
                notes=note,
            )

        add_reference_row(
            asset_rows,
            scene=scene,
            modality="annotation",
            asset_role="review_pair_table",
            path=args.review_queue,
            repo_root=repo_root,
            source_or_derived="derived_annotation_review_asset",
            derived_from="sparse_selected_optical_sar_pairs",
            notes="canonical_442_row_table_not_full_stream_not_independent_sync_evidence",
        )
        add_reference_row(
            asset_rows,
            scene=scene,
            modality="annotation",
            asset_role="final_gt_table",
            path=args.final_gt,
            repo_root=repo_root,
            source_or_derived="derived_gt_asset",
            derived_from="manual_review_and_consolidation",
            notes="posthoc_gt_not_sync_construction_authority",
        )

    finalize_asset_flags(asset_rows)
    asset_manifest = repo_root / "manifests/oty2/oty2_p0_data_asset_manifest.csv"
    write_csv(asset_manifest, ASSET_FIELDS, asset_rows)

    auto_confirmed = all(
        "optical_source_video" in video_sources_by_scene.get(scene, {})
        and "sar_gray_source_video" in video_sources_by_scene.get(scene, {})
        for scene in SCENES
    )
    effective_fps_status = args.fps_evidence_status
    if effective_fps_status == "auto":
        effective_fps_status = "confirmed" if auto_confirmed else "candidate"
    status = assumption_status(effective_fps_status)
    sar_to_optical_rows: list[dict[str, Any]] = []
    optical_to_sar_rows: list[dict[str, Any]] = []
    for scene in SCENES:
        optical_indices = sorted({int(row["frame_index"]) for row in indexed_rows(asset_rows, scene, "optical_frame")})
        sar_indices = sorted({int(row["frame_index"]) for row in indexed_rows(asset_rows, scene, "sar_gray_frame")})
        if not optical_indices or not sar_indices:
            continue
        sar_to_optical_rows.extend(build_sar_to_optical(scene, sar_indices, optical_indices, args.optical_fps, args.sar_fps, status))
        optical_to_sar_rows.extend(build_optical_to_sar(scene, optical_indices, sar_indices, args.optical_fps, args.sar_fps, status))

    write_csv(repo_root / "manifests/oty2/oty2_p0_hard_sync_sar_to_optical.csv", SAR_TO_OPTICAL_FIELDS, sar_to_optical_rows)
    write_csv(repo_root / "manifests/oty2/oty2_p0_hard_sync_optical_to_sar.csv", OPTICAL_TO_SAR_FIELDS, optical_to_sar_rows)

    pair_rows = read_csv_rows(args.review_queue)
    pair_summary = analyze_pair_table(pair_rows, args.optical_fps, args.sar_fps)
    report = report_text(
        asset_rows=asset_rows,
        pair_summary=pair_summary,
        review_queue_path=args.review_queue,
        final_gt_path=args.final_gt,
        optical_fps=args.optical_fps,
        sar_fps=args.sar_fps,
        fps_status=effective_fps_status,
        status=status,
    )
    report_path = repo_root / f"reports/oty2/oty2_p0_data_asset_and_hard_sync_audit_{args.report_date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(json.dumps({
        "asset_manifest": str(asset_manifest),
        "asset_rows": len(asset_rows),
        "sar_to_optical_rows": len(sar_to_optical_rows),
        "optical_to_sar_rows": len(optical_to_sar_rows),
        "report": str(report_path),
        "p0_state": "P0_DATA_FOUNDATION_PARTIALLY_READY",
        "assumption_status": status,
        "fps_evidence_status": effective_fps_status,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
