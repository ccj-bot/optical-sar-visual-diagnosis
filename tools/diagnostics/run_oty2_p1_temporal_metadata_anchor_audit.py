"""Run OTY2-P1 temporal metadata and anchor audit.

OTY2-P1 inventories timing evidence that is visible from repository metadata,
configured local paths, manifests, prior audit outputs, and explicitly declared
acquisition FPS scale. FPS is scale metadata only; it is not per-frame timestamp
truth and does not imply optical frame 0 aligns to SAR frame 0. This audit does
not read SAR image pixels, use SAR GT, enter SAR bands, run selectors, train
thresholds, or produce annotation proposals.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

INVENTORY_FIELDS = [
    "scene",
    "source_kind",
    "source_path",
    "source_exists",
    "source_status",
    "frame_count",
    "frame_index_min",
    "frame_index_max",
    "has_per_frame_timestamp",
    "timestamp_field_names",
    "timestamp_count",
    "timestamp_parse_status",
    "has_scene_start_time",
    "has_scene_end_time",
    "has_fps",
    "fps_value",
    "has_timebase",
    "timebase_value",
    "has_manual_anchor",
    "manual_anchor_count",
    "metadata_strength",
    "blockers",
    "notes",
]

ANCHOR_FIELDS = [
    "scene",
    "anchor_id",
    "anchor_source",
    "anchor_type",
    "optical_frame_num",
    "sar_frame_num",
    "optical_time",
    "sar_time",
    "time_delta_ms",
    "evidence_strength",
    "uses_image_content",
    "uses_sar_gt",
    "uses_manual_declaration",
    "allowed_for_oty2_p1",
    "blockers",
    "notes",
]

DECISION_FIELDS = [
    "scene",
    "optical_frame_count",
    "sar_frame_count",
    "frame_count_ratio",
    "known_optical_fps",
    "known_sar_fps",
    "known_fps_scale_ratio",
    "sync_mode",
    "offset_seconds",
    "software_sync_jitter_ms",
    "has_known_fps_scale",
    "has_scene_timing_record",
    "offset_status",
    "frame0_alignment_assumption",
    "manual_anchor_candidate_count",
    "allowed_manual_anchor_count",
    "has_allowed_manual_anchor",
    "best_available_alignment_mode",
    "can_upgrade_from_frame_ratio_hypothesis",
    "upgrade_target_mode",
    "decision_confidence",
    "alignment_confidence_status",
    "required_missing_metadata",
    "blockers",
    "allowed_next_action",
]

BOUNDARY_FLAGS = {
    "sar_image_content_used": False,
    "sar_gt_used": False,
    "sar_band_entered": False,
    "selector_used": False,
    "annotation_proposal_entered": False,
    "identity_truth_claimed": False,
}

OTY2_P1_ARTIFACT_PREFIXES = (
    "oty2_temporal_metadata_inventory_",
    "oty2_scene_alignment_anchor_candidates_",
    "oty2_alignment_mode_decision_report_",
    "oty2_temporal_alignment_anchor_summary_",
    "oty2_alignment_mode_decision_summary_",
)

OTY2_P1_SAMPLE_NAMES = {
    "oty2_temporal_metadata_inventory_sample.csv",
    "oty2_scene_alignment_anchor_candidates_sample.csv",
    "oty2_alignment_mode_decision_summary_sample.csv",
}

TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt", ".yaml", ".yml", ".tsv", ".log", ".xml"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
SAR_IMAGE_SUFFIXES = IMAGE_SUFFIXES

TIMESTAMP_FIELD_RE = re.compile(r"(timestamp|time_stamp|time|utc|epoch|datetime|date_time)", re.IGNORECASE)
FPS_FIELD_RE = re.compile(r"(^|_)(fps|frame_rate|frame_period|period_ms|hz)($|_)", re.IGNORECASE)
START_FIELD_RE = re.compile(r"(start_time|scene_start|capture_start|begin_time)", re.IGNORECASE)
END_FIELD_RE = re.compile(r"(end_time|scene_end|capture_end|stop_time)", re.IGNORECASE)
TIMEBASE_FIELD_RE = re.compile(r"(timebase|time_base|clock|timezone|utc_offset)", re.IGNORECASE)
ANCHOR_FIELD_RE = re.compile(r"(anchor|sync|correspondence|alignment_pair|manual_pair)", re.IGNORECASE)
SELECTOR_FIELD_RE = re.compile(r"(selector|g2|a008|rank|ranking)", re.IGNORECASE)
GT_FIELD_RE = re.compile(r"(final_gt|sar_gt|ground_truth|gt_|final_box|oracle|posthoc)", re.IGNORECASE)

ISO_LIKE_RE = re.compile(
    r"(\d{4}[-_]\d{2}[-_]\d{2}[T_\- ]\d{2}[-_]\d{2}[-_]\d{2}"
    r"|\d{4}\d{2}\d{2}[T_]\d{2}\d{2}\d{2}"
    r"|\d{13})"
)
INTEGER_RE = re.compile(r"\d+")


def bool_text(value: Any) -> str:
    return "true" if boolish(value) else "false"


def boolish(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"true", "1", "yes"}


def safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def join_values(values: Iterable[Any]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return ";".join(out)


def split_path_values(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.replace(",", ";").split(";") if part.strip()]


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def rel(path: str | Path) -> str:
    path = Path(path)
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def read_json_like(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_csv_rows(path: str | Path, max_rows: int | None = None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for index, row in enumerate(reader):
                if max_rows is not None and index >= max_rows:
                    break
                rows.append({str(key): str(value or "") for key, value in row.items() if key is not None})
    except OSError:
        return []
    return rows


def read_csv_header(path: str | Path) -> list[str]:
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            return [str(item or "") for item in next(reader, [])]
    except OSError:
        return []


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def find_nested_keys(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_prefix = f"{prefix}.{key_text}" if prefix else key_text
            found.append((child_prefix, child))
            found.extend(find_nested_keys(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            found.extend(find_nested_keys(child, child_prefix))
    return found


def temporal_field_summary(fields: Sequence[str], row_values: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    timestamp_fields = [field for field in fields if TIMESTAMP_FIELD_RE.search(field)]
    fps_fields = [field for field in fields if FPS_FIELD_RE.search(field)]
    start_fields = [field for field in fields if START_FIELD_RE.search(field)]
    end_fields = [field for field in fields if END_FIELD_RE.search(field)]
    timebase_fields = [field for field in fields if TIMEBASE_FIELD_RE.search(field)]
    anchor_fields = [field for field in fields if ANCHOR_FIELD_RE.search(field)]

    timestamp_count = 0
    timestamp_parseable = 0
    fps_values: list[str] = []
    timebase_values: list[str] = []
    for row in row_values:
        for field in timestamp_fields:
            value = str(row.get(field, "") or "").strip()
            if value:
                timestamp_count += 1
                if parse_timestamp_text(value):
                    timestamp_parseable += 1
        for field in fps_fields:
            value = str(row.get(field, "") or "").strip()
            if value and safe_float(value) is not None:
                fps_values.append(value)
        for field in timebase_fields:
            value = str(row.get(field, "") or "").strip()
            if value:
                timebase_values.append(value)

    if timestamp_fields and not row_values:
        timestamp_parse_status = "timestamp_fields_present_not_row_validated"
    elif timestamp_count and timestamp_parseable == timestamp_count:
        timestamp_parse_status = "parseable_timestamp_values"
    elif timestamp_count:
        timestamp_parse_status = "timestamp_fields_present_unparseable_or_partial"
    else:
        timestamp_parse_status = "no_timestamp_fields"

    return {
        "timestamp_field_names": join_values(timestamp_fields),
        "timestamp_count": timestamp_count,
        "timestamp_parse_status": timestamp_parse_status,
        "has_per_frame_timestamp": bool(timestamp_fields and timestamp_count and timestamp_parseable == timestamp_count),
        "has_scene_start_time": bool(start_fields),
        "has_scene_end_time": bool(end_fields),
        "has_fps": bool(fps_values),
        "fps_value": join_values(fps_values),
        "has_timebase": bool(timebase_values),
        "timebase_value": join_values(timebase_values),
        "has_manual_anchor": bool(anchor_fields),
        "manual_anchor_count": 0,
    }


def parse_timestamp_text(text: str) -> bool:
    text = str(text or "").strip()
    if not text:
        return False
    if ISO_LIKE_RE.search(text):
        return True
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def parse_frame_index_from_name(path: Path) -> int | None:
    groups = INTEGER_RE.findall(path.stem)
    if not groups:
        return None
    if ISO_LIKE_RE.search(path.stem):
        return None
    return int(groups[0])


def filename_has_timestamp(path: Path) -> bool:
    return bool(ISO_LIKE_RE.search(path.stem))


def stat_mtime_text(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return ""


def path_sort_key(path: Path) -> tuple[str, str]:
    return (str(path.parent).lower(), path.name.lower())


def inventory_row(
    *,
    scene: str,
    source_kind: str,
    source_path: str | Path,
    source_exists: bool,
    source_status: str,
    frame_count: Any = "",
    frame_index_min: Any = "",
    frame_index_max: Any = "",
    has_per_frame_timestamp: Any = False,
    timestamp_field_names: Any = "",
    timestamp_count: Any = "",
    timestamp_parse_status: str = "",
    has_scene_start_time: Any = False,
    has_scene_end_time: Any = False,
    has_fps: Any = False,
    fps_value: Any = "",
    has_timebase: Any = False,
    timebase_value: Any = "",
    has_manual_anchor: Any = False,
    manual_anchor_count: Any = "",
    metadata_strength: str = "",
    blockers: Any = "",
    notes: Any = "",
) -> dict[str, Any]:
    return {
        "scene": scene,
        "source_kind": source_kind,
        "source_path": rel(source_path),
        "source_exists": bool_text(source_exists),
        "source_status": source_status,
        "frame_count": frame_count,
        "frame_index_min": frame_index_min,
        "frame_index_max": frame_index_max,
        "has_per_frame_timestamp": bool_text(has_per_frame_timestamp),
        "timestamp_field_names": timestamp_field_names,
        "timestamp_count": timestamp_count,
        "timestamp_parse_status": timestamp_parse_status,
        "has_scene_start_time": bool_text(has_scene_start_time),
        "has_scene_end_time": bool_text(has_scene_end_time),
        "has_fps": bool_text(has_fps),
        "fps_value": fps_value,
        "has_timebase": bool_text(has_timebase),
        "timebase_value": timebase_value,
        "has_manual_anchor": bool_text(has_manual_anchor),
        "manual_anchor_count": manual_anchor_count,
        "metadata_strength": metadata_strength,
        "blockers": join_values(split_path_values(blockers) if isinstance(blockers, str) else blockers),
        "notes": notes,
    }


def inspect_declared_object(scene: str, source_kind: str, source_path: str | Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    fields = [key for key, _ in find_nested_keys(payload)]
    row_values = [{key: value for key, value in find_nested_keys(payload) if not isinstance(value, (dict, list))}]
    temporal = temporal_field_summary(fields, row_values)
    blockers: list[str] = []
    if not temporal["timestamp_field_names"]:
        blockers.append("no_declared_timestamp_fields")
    else:
        blockers.append("declared_timestamp_fields_not_per_frame_alignment_metadata")
    if not temporal["has_fps"]:
        blockers.append("no_declared_fps_or_frame_period")
    if not temporal["has_timebase"]:
        blockers.append("no_declared_timebase")
    if not temporal["has_manual_anchor"]:
        blockers.append("no_declared_manual_anchor")
    has_offset_or_anchor_metadata = bool(
        temporal["has_scene_start_time"]
        or temporal["has_scene_end_time"]
        or temporal["has_fps"]
        or temporal["has_timebase"]
        or temporal["has_manual_anchor"]
    )
    strength = "declared_temporal_metadata" if has_offset_or_anchor_metadata else "config_present_no_strong_temporal_metadata"
    timestamp_parse_status = temporal["timestamp_parse_status"]
    if temporal["timestamp_field_names"] and temporal["timestamp_count"]:
        timestamp_parse_status = "declared_timestamp_values_not_per_frame_alignment_metadata"
    elif temporal["timestamp_field_names"]:
        timestamp_parse_status = "declared_timestamp_fields_not_per_frame_validated"
    notes = ""
    if payload.get("alignment_unknown") is True:
        notes = "alignment_unknown=true"
        blockers.append("alignment_declared_unknown")
    return inventory_row(
        scene=scene,
        source_kind=source_kind,
        source_path=source_path,
        source_exists=True,
        source_status="declared_metadata_scan",
        has_per_frame_timestamp=False,
        timestamp_field_names=temporal["timestamp_field_names"],
        timestamp_count=temporal["timestamp_count"],
        timestamp_parse_status=timestamp_parse_status,
        has_scene_start_time=temporal["has_scene_start_time"],
        has_scene_end_time=temporal["has_scene_end_time"],
        has_fps=temporal["has_fps"],
        fps_value=temporal["fps_value"],
        has_timebase=temporal["has_timebase"],
        timebase_value=temporal["timebase_value"],
        has_manual_anchor=temporal["has_manual_anchor"],
        manual_anchor_count=temporal["manual_anchor_count"],
        metadata_strength=strength,
        blockers=blockers,
        notes=notes,
    )


def inspect_frame_directory(scene: str, source_kind: str, path_text: str | Path) -> dict[str, Any]:
    path = Path(path_text)
    if not str(path_text).strip():
        return inventory_row(
            scene=scene,
            source_kind=source_kind,
            source_path="",
            source_exists=False,
            source_status="missing_configured_path_value",
            metadata_strength="missing",
            blockers="missing_configured_path_value",
        )
    if not path.exists():
        return inventory_row(
            scene=scene,
            source_kind=source_kind,
            source_path=path,
            source_exists=False,
            source_status="configured_path_missing",
            metadata_strength="missing",
            blockers="configured_path_missing",
        )
    if not path.is_dir():
        return inventory_row(
            scene=scene,
            source_kind=source_kind,
            source_path=path,
            source_exists=True,
            source_status="configured_path_not_directory",
            metadata_strength="missing",
            blockers="configured_path_not_directory",
        )

    files = sorted([item for item in path.iterdir() if item.is_file()], key=path_sort_key)
    indexes = [index for index in (parse_frame_index_from_name(item) for item in files) if index is not None]
    timestamp_files = [item for item in files if filename_has_timestamp(item)]
    mtimes = [stat_mtime_text(item) for item in files[:1] + files[-1:] if files]
    notes = [
        "filename_numeric_order_is_frame_index_only" if indexes else "no_numeric_frame_indexes_in_filenames",
        "filesystem_mtime_weak_not_acquisition_truth",
    ]
    if mtimes:
        notes.append(f"mtime_sample={join_values(mtimes)}")
    if timestamp_files:
        notes.append("timestamp_like_filename_pattern_unverified")
    blockers = [
        "no_documented_per_frame_timestamp",
        "no_scene_start_end_or_fps",
        "filesystem_mtime_not_acquisition_truth",
    ]
    if source_kind.startswith("sar"):
        blockers.append("sar_image_content_not_read")
    return inventory_row(
        scene=scene,
        source_kind=source_kind,
        source_path=path,
        source_exists=True,
        source_status="directory_metadata_only",
        frame_count=len(files),
        frame_index_min="" if not indexes else min(indexes),
        frame_index_max="" if not indexes else max(indexes),
        has_per_frame_timestamp=bool(timestamp_files),
        timestamp_field_names="filename" if timestamp_files else "",
        timestamp_count=len(timestamp_files),
        timestamp_parse_status="timestamp_like_filename_pattern_unverified" if timestamp_files else "numeric_filename_order_only",
        metadata_strength="weak_filename_timestamp_unverified" if timestamp_files else "weak_frame_inventory_only",
        blockers=blockers,
        notes=join_values(notes),
    )


def known_fps_scale_inventory_row(
    scene: str,
    optical_fps: float | None,
    sar_fps: float | None,
    *,
    sync_mode: str,
    offset_seconds: float,
    software_sync_jitter_ms: float,
) -> dict[str, Any]:
    has_known_scale = bool(optical_fps and sar_fps and optical_fps > 0 and sar_fps > 0)
    fps_value = ""
    notes = (
        "known_acquisition_fps_is_scale_metadata_not_per_frame_timestamp_truth;"
        f"sync_mode={sync_mode};offset_seconds={offset_seconds:g};"
        f"software_sync_jitter_ms={software_sync_jitter_ms:g};"
        "software_sync_not_hardware_exact_sync"
    )
    blockers = [
        "not_timestamp_exact",
        "not_hardware_synchronization",
        "millisecond_sync_jitter_margin_required",
    ]
    if has_known_scale:
        fps_value = f"optical_fps={optical_fps:g};sar_fps={sar_fps:g};sar_per_optical_scale={sar_fps / optical_fps:.6f}"
        strength = "known_fps_scale_with_software_sync_zero_offset"
    else:
        blockers.append("missing_known_optical_or_sar_fps")
        strength = "missing"
    return inventory_row(
        scene=scene,
        source_kind="known_acquisition_fps_scale",
        source_path="user_declared_oty2_p1_parameters",
        source_exists=has_known_scale,
        source_status="known_scale_metadata_with_software_sync_zero_offset" if has_known_scale else "known_scale_metadata_missing",
        has_per_frame_timestamp=False,
        timestamp_parse_status="not_per_frame_timestamp_truth",
        has_fps=has_known_scale,
        fps_value=fps_value,
        has_timebase=False,
        has_manual_anchor=False,
        manual_anchor_count=0,
        metadata_strength=strength,
        blockers=blockers,
        notes=notes,
    )


def candidate_sidecar_files(scene_paths: Mapping[str, Any]) -> list[Path]:
    roots: list[Path] = []
    for value in scene_paths.values():
        path_text = str(value or "").strip()
        if not path_text:
            continue
        path = Path(path_text)
        if path.exists():
            roots.append(path if path.is_dir() else path.parent)
            if path.parent.exists():
                roots.append(path.parent)
    scene_roots = sorted({root for root in roots if root.exists()}, key=lambda path: str(path).lower())
    candidates: list[Path] = []
    for root in scene_roots:
        try:
            iterator = root.rglob("*")
            for item in iterator:
                if not item.is_file():
                    continue
                suffix = item.suffix.lower()
                name = item.name.lower()
                if suffix in IMAGE_SUFFIXES or suffix in {".npy", ".npz", ".pyc"}:
                    continue
                if suffix in TEXT_SUFFIXES | VIDEO_SUFFIXES or any(
                    token in name for token in ("time", "timestamp", "fps", "sync", "anchor", "capture", "metadata", "video", "log")
                ):
                    candidates.append(item)
        except OSError:
            continue
    return sorted(set(candidates), key=path_sort_key)


def inspect_sidecar_search(scene: str, scene_paths: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidates = candidate_sidecar_files(scene_paths)
    if not candidates:
        search_roots = join_values(Path(str(value)).parent for value in scene_paths.values() if str(value or "").strip())
        rows.append(
            inventory_row(
                scene=scene,
                source_kind="local_sidecar_temporal_metadata_search",
                source_path=search_roots,
                source_exists=True,
                source_status="no_sidecar_timestamp_video_or_capture_logs_found",
                metadata_strength="missing",
                blockers="missing_sidecar_timestamp_files;missing_video_metadata_files;missing_capture_logs;missing_manual_anchor_files",
                notes="searched_configured_scene_directories_without_opening_image_pixels",
            )
        )
        return rows

    for candidate in candidates:
        rows.append(inspect_text_metadata_file(scene, candidate, "local_sidecar_temporal_metadata_file"))
    return rows


def inspect_manifest_file(path: Path, scenes: Sequence[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_csv_rows(path)
    header = read_csv_header(path)
    inventory: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    rows_by_scene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        scene = str(row.get("scene", "") or "").strip()
        if scene:
            rows_by_scene[scene].append(row)
    if not rows_by_scene:
        for scene in scenes:
            rows_by_scene[scene] = []

    for scene in sorted(rows_by_scene):
        scene_rows = rows_by_scene[scene]
        temporal = temporal_field_summary(header, scene_rows)
        frame_indexes: list[int] = []
        for row in scene_rows:
            for key in ("frame_range_start", "frame_range_end", "optical_frame_num", "sar_frame_num"):
                value = safe_int(row.get(key))
                if value is not None:
                    frame_indexes.append(value)
            for key in ("optical_frame_path", "sar_frame_path"):
                frame_path = str(row.get(key, "") or "").strip()
                if frame_path:
                    parsed = parse_frame_index_from_name(Path(frame_path))
                    if parsed is not None:
                        frame_indexes.append(parsed)
        manual_anchor_count = sum(1 for row in scene_rows if row_has_manifest_pair(row))
        blockers = ["manifest_has_no_real_timestamp_fields"]
        if manual_anchor_count:
            blockers.append("manifest_pairs_are_sample_or_visual_context_not_declared_temporal_anchors")
        inventory.append(
            inventory_row(
                scene=scene,
                source_kind=f"manifest_{path.stem}",
                source_path=path,
                source_exists=True,
                source_status="manifest_metadata_scan",
                frame_count=len(scene_rows),
                frame_index_min="" if not frame_indexes else min(frame_indexes),
                frame_index_max="" if not frame_indexes else max(frame_indexes),
                has_per_frame_timestamp=temporal["has_per_frame_timestamp"],
                timestamp_field_names=temporal["timestamp_field_names"],
                timestamp_count=temporal["timestamp_count"],
                timestamp_parse_status=temporal["timestamp_parse_status"],
                has_scene_start_time=temporal["has_scene_start_time"],
                has_scene_end_time=temporal["has_scene_end_time"],
                has_fps=temporal["has_fps"],
                fps_value=temporal["fps_value"],
                has_timebase=temporal["has_timebase"],
                timebase_value=temporal["timebase_value"],
                has_manual_anchor=manual_anchor_count > 0 or temporal["has_manual_anchor"],
                manual_anchor_count=manual_anchor_count,
                metadata_strength="weak_manual_or_sample_manifest" if manual_anchor_count else "weak_manifest_frame_inventory",
                blockers=blockers,
                notes=f"rows_for_scene={len(scene_rows)}",
            )
        )
        anchors.extend(anchor_candidates_from_manifest(path, scene, scene_rows, explicit_anchor_source=manifest_is_anchor_source(path, header)))
    return inventory, anchors


def manifest_is_anchor_source(path: Path, header: Sequence[str]) -> bool:
    text = f"{path.name} {' '.join(header)}"
    return bool(ANCHOR_FIELD_RE.search(text))


def row_has_manifest_pair(row: Mapping[str, Any]) -> bool:
    optical_frame = str(row.get("optical_frame_num", "") or "").strip()
    sar_frame = str(row.get("sar_frame_num", "") or "").strip()
    optical_path = str(row.get("optical_frame_path", "") or "").strip()
    sar_path = str(row.get("sar_frame_path", "") or "").strip()
    optical_time = str(row.get("optical_time", "") or row.get("optical_timestamp", "") or "").strip()
    sar_time = str(row.get("sar_time", "") or row.get("sar_timestamp", "") or "").strip()
    return bool((optical_frame or optical_path or optical_time) and (sar_frame or sar_path or sar_time))


def anchor_candidates_from_manifest(
    path: Path,
    scene: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    explicit_anchor_source: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not row_has_manifest_pair(row):
            continue
        optical_frame = first_nonempty(
            row.get("optical_frame_num"),
            parse_frame_index_from_name(Path(str(row.get("optical_frame_path", "") or "")))
            if str(row.get("optical_frame_path", "") or "").strip()
            else "",
        )
        sar_frame = first_nonempty(
            row.get("sar_frame_num"),
            parse_frame_index_from_name(Path(str(row.get("sar_frame_path", "") or "")))
            if str(row.get("sar_frame_path", "") or "").strip()
            else "",
        )
        optical_time = first_nonempty(row.get("optical_time"), row.get("optical_timestamp"))
        sar_time = first_nonempty(row.get("sar_time"), row.get("sar_timestamp"))
        source_text = " ".join(str(value or "") for value in row.values()) + " " + path.name
        uses_sar_gt = bool(GT_FIELD_RE.search(source_text))
        uses_selector = bool(SELECTOR_FIELD_RE.search(source_text))
        has_anchor_word = explicit_anchor_source or bool(ANCHOR_FIELD_RE.search(source_text))
        enough_pair = bool((str(optical_frame).strip() or str(optical_time).strip()) and (str(sar_frame).strip() or str(sar_time).strip()))
        allowed = bool(has_anchor_word and enough_pair and not uses_sar_gt and not uses_selector)
        blockers: list[str] = []
        if not has_anchor_word:
            blockers.append("not_declared_as_temporal_alignment_anchor")
        if uses_sar_gt:
            blockers.append("candidate_source_contains_gt_or_posthoc_fields")
        if uses_selector:
            blockers.append("candidate_source_contains_selector_or_ranking_fields")
        if not enough_pair:
            blockers.append("missing_optical_or_sar_frame_or_time")
        if not allowed and not blockers:
            blockers.append("not_allowed_for_oty2_p1")
        out.append(
            {
                "scene": scene,
                "anchor_id": f"{path.stem}_{scene}_{index:04d}",
                "anchor_source": rel(path),
                "anchor_type": "declared_manual_anchor" if has_anchor_word else "manifest_sample_pair",
                "optical_frame_num": optical_frame,
                "sar_frame_num": sar_frame,
                "optical_time": optical_time,
                "sar_time": sar_time,
                "time_delta_ms": "",
                "evidence_strength": "manual_anchor_candidate" if allowed else "weak_sample_or_posthoc_context",
                "uses_image_content": "false",
                "uses_sar_gt": bool_text(uses_sar_gt),
                "uses_manual_declaration": "true",
                "allowed_for_oty2_p1": bool_text(allowed),
                "blockers": join_values(blockers),
                "notes": "manifest row inspected as metadata only; image pixels not opened",
            }
        )
    return out


def first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value if value is not None else "").strip()
        if text:
            return text
    return ""


def inspect_text_metadata_file(scene: str, path: Path, source_kind: str) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        return inventory_row(
            scene=scene,
            source_kind=source_kind,
            source_path=path,
            source_exists=True,
            source_status="video_file_present_metadata_not_decoded",
            metadata_strength="potential_video_metadata_unread",
            blockers="video_metadata_not_extracted;requires_explicit_video_metadata_decode",
            notes="file existence only; video content not decoded",
        )
    if suffix == ".csv" or suffix == ".tsv":
        delimiter = "\t" if suffix == ".tsv" else ","
        header = read_csv_header(path)
        rows = read_csv_rows(path, max_rows=500)
        if delimiter == "\t" and len(header) <= 1:
            header = read_text_header(path)
            rows = []
        temporal = temporal_field_summary(header, rows)
        frame_indexes = frame_indexes_from_rows(rows)
        scenes_in_rows = join_values(row.get("scene") for row in rows)
        return inventory_row(
            scene=scene,
            source_kind=source_kind,
            source_path=path,
            source_exists=True,
            source_status="text_metadata_scan",
            frame_count=len(rows),
            frame_index_min="" if not frame_indexes else min(frame_indexes),
            frame_index_max="" if not frame_indexes else max(frame_indexes),
            has_per_frame_timestamp=temporal["has_per_frame_timestamp"],
            timestamp_field_names=temporal["timestamp_field_names"],
            timestamp_count=temporal["timestamp_count"],
            timestamp_parse_status=temporal["timestamp_parse_status"],
            has_scene_start_time=temporal["has_scene_start_time"],
            has_scene_end_time=temporal["has_scene_end_time"],
            has_fps=temporal["has_fps"],
            fps_value=temporal["fps_value"],
            has_timebase=temporal["has_timebase"],
            timebase_value=temporal["timebase_value"],
            has_manual_anchor=temporal["has_manual_anchor"],
            manual_anchor_count=temporal["manual_anchor_count"],
            metadata_strength=metadata_strength_from_temporal(temporal),
            blockers=blockers_from_temporal(temporal),
            notes=f"scenes_seen={scenes_in_rows}",
        )
    if suffix == ".json":
        payload = read_json_like(path)
        return inspect_declared_object(scene, source_kind, path, payload)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    fields = keyword_fields_from_text(text)
    temporal = temporal_field_summary(fields, [])
    source_status = "text_metadata_scan" if text else "text_unreadable_or_empty"
    return inventory_row(
        scene=scene,
        source_kind=source_kind,
        source_path=path,
        source_exists=path.exists(),
        source_status=source_status,
        has_per_frame_timestamp=False,
        timestamp_field_names=temporal["timestamp_field_names"],
        timestamp_count=0,
        timestamp_parse_status="keyword_only_no_per_frame_values" if temporal["timestamp_field_names"] else "no_timestamp_fields",
        has_scene_start_time=temporal["has_scene_start_time"],
        has_scene_end_time=temporal["has_scene_end_time"],
        has_fps=False,
        has_timebase=False,
        has_manual_anchor=temporal["has_manual_anchor"],
        manual_anchor_count=0,
        metadata_strength="documentation_mentions_temporal_concepts" if fields else "no_temporal_metadata_found",
        blockers=blockers_from_temporal(temporal),
        notes="documentation keyword scan only",
    )


def read_text_header(path: Path) -> list[str]:
    try:
        first = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except (OSError, IndexError):
        return []
    return [item.strip() for item in re.split(r"[\t,|]", first) if item.strip()]


def frame_indexes_from_rows(rows: Sequence[Mapping[str, Any]]) -> list[int]:
    indexes: list[int] = []
    frame_keys = (
        "frame",
        "frame_num",
        "frame_number",
        "optical_frame_num",
        "sar_frame_num",
        "frame_range_start",
        "frame_range_end",
    )
    for row in rows:
        for key in frame_keys:
            value = safe_int(row.get(key))
            if value is not None:
                indexes.append(value)
    return indexes


def metadata_strength_from_temporal(temporal: Mapping[str, Any]) -> str:
    if boolish(temporal.get("has_per_frame_timestamp")) and boolish(temporal.get("has_timebase")):
        return "strong_per_frame_timestamp_metadata"
    if boolish(temporal.get("has_per_frame_timestamp")):
        return "candidate_per_frame_timestamp_without_confirmed_common_timebase"
    if boolish(temporal.get("has_scene_start_time")) or boolish(temporal.get("has_scene_end_time")) or boolish(temporal.get("has_fps")):
        return "candidate_scene_timing_metadata_incomplete"
    if boolish(temporal.get("has_manual_anchor")):
        return "candidate_anchor_metadata_incomplete"
    return "no_strong_temporal_metadata"


def blockers_from_temporal(temporal: Mapping[str, Any]) -> str:
    blockers: list[str] = []
    if not boolish(temporal.get("has_per_frame_timestamp")):
        blockers.append("missing_parseable_per_frame_timestamp")
    if not (boolish(temporal.get("has_scene_start_time")) and boolish(temporal.get("has_scene_end_time"))) and not boolish(
        temporal.get("has_fps")
    ):
        blockers.append("missing_scene_start_end_or_fps")
    if not boolish(temporal.get("has_timebase")):
        blockers.append("missing_common_timebase")
    if not boolish(temporal.get("has_manual_anchor")):
        blockers.append("missing_declared_manual_anchor")
    return join_values(blockers)


def keyword_fields_from_text(text: str) -> list[str]:
    fields: list[str] = []
    lowered = text.lower()
    for token in (
        "timestamp",
        "timebase",
        "fps",
        "frame_rate",
        "start_time",
        "end_time",
        "manual_anchor",
        "anchor",
        "frame_ratio_hypothesis",
        "timestamp_exact",
        "timestamp_offset_scale",
    ):
        if token in lowered:
            fields.append(token)
    return fields


def collect_repo_text_files(paths: Sequence[Path], max_size_bytes: int) -> list[Path]:
    out: list[Path] = []
    for root in paths:
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() in TEXT_SUFFIXES:
            out.append(root)
            continue
        if not root.is_dir():
            continue
        for item in root.rglob("*"):
            if not item.is_file():
                continue
            if item.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                if item.stat().st_size > max_size_bytes:
                    continue
            except OSError:
                continue
            out.append(item)
    return sorted(set(out), key=path_sort_key)


def source_kind_for_repo_file(path: Path) -> str:
    try:
        relative = path.relative_to(REPO_ROOT)
    except ValueError:
        relative = path
    parts = relative.parts
    if not parts:
        return "repo_text_file"
    if parts[0] == "docs":
        return "repo_doc_temporal_metadata_scan"
    if parts[0] == "reports":
        return "repo_report_temporal_metadata_scan"
    if parts[0] == "outputs":
        return "repo_output_temporal_metadata_scan"
    if parts[0] == "manifests":
        return "repo_manifest_temporal_metadata_scan"
    if parts[0] == "configs":
        return "repo_config_temporal_metadata_scan"
    return "repo_text_temporal_metadata_scan"


def is_oty2_p1_generated_artifact(path: Path) -> bool:
    name = path.name
    return name in OTY2_P1_SAMPLE_NAMES or any(name.startswith(prefix) for prefix in OTY2_P1_ARTIFACT_PREFIXES)


def scenes_from_text_file(path: Path, known_scenes: Sequence[str]) -> list[str]:
    if path.suffix.lower() == ".csv":
        rows = read_csv_rows(path, max_rows=500)
        scenes = join_values(row.get("scene") for row in rows)
        out = [scene for scene in split_path_values(scenes) if scene in known_scenes]
        if out:
            return out
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    out = [scene for scene in known_scenes if scene in text or scene.lower() in str(path).lower()]
    return out or list(known_scenes)


def collect_stage_status(scenes: Sequence[str], output_root: Path) -> dict[str, dict[str, Any]]:
    status = {scene: {"p4g_available": False, "p4g_object_count": 0, "p4g_frame_rows": 0, "oty2_p0_available": False} for scene in scenes}
    p4g_dirs = sorted(output_root.glob("oty1t_object_hypothesis_generalization_audit_*"), key=lambda path: path.name, reverse=True)
    for p4g_dir in p4g_dirs:
        object_file = p4g_dir / "oty1t_object_hypotheses_generalized.csv"
        frame_file = p4g_dir / "oty1t_object_frame_state_timeseries_generalized.csv"
        if not object_file.exists() or not frame_file.exists():
            continue
        object_rows = read_csv_rows(object_file)
        frame_rows = read_csv_rows(frame_file)
        for scene in scenes:
            object_count = sum(1 for row in object_rows if row.get("scene") == scene)
            frame_count = sum(1 for row in frame_rows if row.get("scene") == scene)
            if object_count or frame_count:
                status[scene]["p4g_available"] = True
                status[scene]["p4g_object_count"] = object_count
                status[scene]["p4g_frame_rows"] = frame_count
                status[scene]["p4g_output_dir"] = str(p4g_dir)
        break
    p0_dirs = sorted(output_root.glob("oty2_object_temporal_alignment_audit_*"), key=lambda path: path.name, reverse=True)
    for p0_dir in p0_dirs:
        summary = read_json_like(p0_dir / "oty2_object_temporal_alignment_summary.json")
        for row in summary.get("per_scene", []):
            if not isinstance(row, Mapping):
                continue
            scene = str(row.get("scene", "") or "")
            if scene in status:
                status[scene]["oty2_p0_available"] = True
                status[scene]["oty2_p0_input_status"] = row.get("input_status", "")
                status[scene]["oty2_p0_blockers"] = row.get("top_blockers", "")
        break
    return status


def decide_alignment_modes(
    scenes: Sequence[str],
    inventory_rows: Sequence[Mapping[str, Any]],
    anchor_rows: Sequence[Mapping[str, Any]],
    stage_status: Mapping[str, Mapping[str, Any]],
    *,
    optical_fps: float | None,
    sar_fps: float | None,
    sync_mode: str,
    offset_seconds: float,
    software_sync_jitter_ms: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_scene = defaultdict(list)
    for row in inventory_rows:
        by_scene[str(row.get("scene", "") or "")].append(row)
    anchors_by_scene = defaultdict(list)
    for row in anchor_rows:
        anchors_by_scene[str(row.get("scene", "") or "")].append(row)

    for scene in scenes:
        scene_inventory = by_scene.get(scene, [])
        optical_count = max_count(scene_inventory, "optical_frame_inventory")
        sar_count = max_count(scene_inventory, "sar_frame_inventory")
        real_optical_ts = has_strong_timestamp(scene_inventory, "optical")
        real_sar_ts = has_strong_timestamp(scene_inventory, "sar_frame_inventory")
        common_timebase = any(boolish(row.get("has_timebase")) for row in scene_inventory)
        has_scene_timing_record = has_scene_start_end_metadata(scene_inventory)
        has_known_fps_scale = bool(optical_fps and sar_fps and optical_fps > 0 and sar_fps > 0)
        known_fps_scale_ratio = ""
        if has_known_fps_scale:
            known_fps_scale_ratio = f"{sar_fps / optical_fps:.6f}"
        allowed_anchors = [row for row in anchors_by_scene.get(scene, []) if boolish(row.get("allowed_for_oty2_p1"))]
        anchor_candidates = anchors_by_scene.get(scene, [])
        has_software_sync_zero_offset = bool(sync_mode and abs(offset_seconds) < 1e-12)
        if has_software_sync_zero_offset:
            offset_status = "software_sync_zero_offset_assumed"
            frame0_alignment_assumption = "software_sync_same_start_not_hardware_exact"
        elif has_scene_timing_record or allowed_anchors:
            offset_status = "known_from_scene_timing_or_manual_anchor"
            frame0_alignment_assumption = "declared_by_timing_or_anchor"
        else:
            offset_status = "unknown"
            frame0_alignment_assumption = "unverified_not_assumed"
        alignment_confidence_status = ""
        frame_ratio = ""
        if optical_count and sar_count:
            frame_ratio = f"{sar_count / optical_count:.6f}"

        missing: list[str] = []
        blockers: list[str] = []
        if not real_optical_ts:
            missing.append("real_optical_per_frame_timestamps")
        if not real_sar_ts:
            missing.append("real_sar_per_frame_timestamps")
        if not common_timebase:
            missing.append("common_or_convertible_timebase")
        if not has_known_fps_scale:
            missing.append("known_optical_sar_fps_scale")
        if not has_scene_timing_record:
            missing.append("scene_start_end_timing_record")
        if offset_status == "unknown":
            missing.append("optical_sar_start_offset_or_frame0_anchor")
        elif has_software_sync_zero_offset:
            missing.append("hardware_exact_synchronization")
        if not allowed_anchors:
            missing.append("allowed_manual_optical_sar_anchor")
        if not optical_count:
            blockers.append("missing_optical_frame_inventory")
        if not sar_count:
            blockers.append("missing_sar_frame_inventory")
        if not boolish(stage_status.get(scene, {}).get("p4g_available")):
            blockers.append("missing_p4g_object_level_inputs")

        if real_optical_ts and real_sar_ts and common_timebase:
            mode = "timestamp_exact"
            can_upgrade = True
            upgrade = "timestamp_exact"
            confidence = "high"
            alignment_confidence_status = "real_per_frame_timestamps_available"
            allowed_next_action = "use_timestamp_exact_in_future_oty2_refinement"
        elif has_known_fps_scale and optical_count and sar_count:
            mode = "timestamp_offset_scale_hypothesis"
            can_upgrade = True
            upgrade = "timestamp_offset_scale_hypothesis"
            if has_software_sync_zero_offset:
                confidence = "medium"
                alignment_confidence_status = "software_sync_zero_offset_with_jitter_margin"
                blockers.extend(["non_hardware_sync_jitter_margin_required"])
                allowed_next_action = "generate_sar_temporal_windows_with_software_sync_jitter_margin"
            elif offset_status == "unknown":
                confidence = "low"
                alignment_confidence_status = "known_fps_ratio_missing_start_offset"
                blockers.extend(
                    [
                        "missing_start_offset_or_manual_anchor",
                        "frame0_alignment_unverified_not_assumed",
                    ]
                )
                allowed_next_action = "collect_start_offset_scene_timing_record_or_manual_anchor_before_oty2_p2_or_oty3"
            else:
                confidence = "medium"
                alignment_confidence_status = "known_fps_ratio_with_start_or_anchor"
                allowed_next_action = "validate_timestamp_offset_scale_hypothesis_before_future_oty2_refinement"
        elif allowed_anchors:
            mode = "manual_anchor_hypothesis"
            can_upgrade = True
            upgrade = "manual_anchor_hypothesis"
            confidence = "medium"
            alignment_confidence_status = "manual_anchor_available_missing_known_fps_scale"
            allowed_next_action = "use_allowed_manual_anchor_hypothesis_in_future_oty2_refinement"
        elif optical_count and sar_count:
            mode = "frame_ratio_hypothesis"
            can_upgrade = False
            upgrade = ""
            confidence = "low"
            alignment_confidence_status = "frame_inventory_only"
            blockers.extend(
                [
                    "frame_inventory_only_not_timestamp_truth",
                    "missing_known_fps_scale_real_timestamps_or_allowed_anchor",
                ]
            )
            allowed_next_action = "collect_real_timestamps_scene_timing_or_allowed_manual_anchor_before_oty2_p2_or_oty3"
        else:
            mode = "unknown_alignment"
            can_upgrade = False
            upgrade = ""
            confidence = "blocked"
            alignment_confidence_status = "insufficient_frame_inventory"
            blockers.append("insufficient_frame_inventory_for_ratio_hypothesis")
            allowed_next_action = "repair_frame_inventory_and_object_level_inputs_before_alignment"

        rows.append(
            {
                "scene": scene,
                "optical_frame_count": optical_count or "",
                "sar_frame_count": sar_count or "",
                "frame_count_ratio": frame_ratio,
                "known_optical_fps": "" if not optical_fps else f"{optical_fps:g}",
                "known_sar_fps": "" if not sar_fps else f"{sar_fps:g}",
                "known_fps_scale_ratio": known_fps_scale_ratio,
                "has_known_fps_scale": bool_text(has_known_fps_scale),
                "has_scene_timing_record": bool_text(has_scene_timing_record),
                "offset_status": offset_status,
                "frame0_alignment_assumption": frame0_alignment_assumption,
                "manual_anchor_candidate_count": len(anchor_candidates),
                "allowed_manual_anchor_count": len(allowed_anchors),
                "has_allowed_manual_anchor": bool_text(bool(allowed_anchors)),
                "best_available_alignment_mode": mode,
                "can_upgrade_from_frame_ratio_hypothesis": bool_text(can_upgrade),
                "upgrade_target_mode": upgrade,
                "decision_confidence": confidence,
                "alignment_confidence_status": alignment_confidence_status,
                "sync_mode": sync_mode,
                "offset_seconds": f"{offset_seconds:g}",
                "software_sync_jitter_ms": f"{software_sync_jitter_ms:g}",
                "required_missing_metadata": join_values(missing),
                "blockers": join_values(blockers),
                "allowed_next_action": allowed_next_action,
            }
        )
    return rows


def max_count(rows: Sequence[Mapping[str, Any]], source_kind_prefix: str) -> int:
    counts: list[int] = []
    for row in rows:
        if not str(row.get("source_kind", "") or "").startswith(source_kind_prefix):
            continue
        value = safe_int(row.get("frame_count"), default=0)
        if value:
            counts.append(value)
    return max(counts) if counts else 0


def has_strong_timestamp(rows: Sequence[Mapping[str, Any]], source_kind_part: str) -> bool:
    for row in rows:
        source_kind = str(row.get("source_kind", "") or "")
        if source_kind_part not in source_kind:
            continue
        strength = str(row.get("metadata_strength", "") or "")
        if boolish(row.get("has_per_frame_timestamp")) and "weak" not in strength and "unverified" not in strength:
            return True
    return False


def has_offset_scale_metadata(rows: Sequence[Mapping[str, Any]]) -> bool:
    has_fps = any(boolish(row.get("has_fps")) for row in rows)
    has_start_end = any(boolish(row.get("has_scene_start_time")) for row in rows) and any(
        boolish(row.get("has_scene_end_time")) for row in rows
    )
    return bool(has_fps or has_start_end)


def has_scene_start_end_metadata(rows: Sequence[Mapping[str, Any]]) -> bool:
    return any(boolish(row.get("has_scene_start_time")) for row in rows) and any(
        boolish(row.get("has_scene_end_time")) for row in rows
    )


def render_decision_report(summary: Mapping[str, Any], decision_rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# OTY2-P1 Temporal Metadata and Anchor Audit",
        "",
        "OTY2-P1 audits temporal metadata and anchor availability only. It does not enter SAR spatial search, read SAR image content, use SAR GT, use selectors, train thresholds, or create annotation proposals.",
        "",
        "## Direct Answers",
        "",
    ]
    for row in decision_rows:
        scene = row.get("scene", "")
        mode = row.get("best_available_alignment_mode", "")
        missing = row.get("required_missing_metadata", "")
        blockers = row.get("blockers", "")
        lines.extend(
            [
                f"### {scene}",
                "",
                f"1. Optical real timestamps: `{answer_has('real_optical_per_frame_timestamps', missing)}`",
                f"2. SAR real timestamps: `{answer_has('real_sar_per_frame_timestamps', missing)}`",
                f"3. Known FPS scale: `optical_fps={row.get('known_optical_fps', '')}`, `sar_fps={row.get('known_sar_fps', '')}`, scale=`{row.get('known_fps_scale_ratio', '')}`",
                f"4. Software sync contract: `{row.get('sync_mode', '')}`, offset_seconds=`{row.get('offset_seconds', '')}`, jitter_ms=`{row.get('software_sync_jitter_ms', '')}`",
                f"5. Scene start/end timing record: `{row.get('has_scene_timing_record', '')}`",
                f"6. Manual optical/SAR anchor present: `{row.get('has_allowed_manual_anchor', '')}` allowed, `{row.get('manual_anchor_candidate_count', '')}` candidate rows inspected",
                f"7. Start offset status: `{row.get('offset_status', '')}`; frame 0 alignment: `{row.get('frame0_alignment_assumption', '')}`",
                f"8. Upgrade beyond frame_ratio_hypothesis: `{row.get('can_upgrade_from_frame_ratio_hypothesis', '')}` -> `{row.get('upgrade_target_mode', '')}`",
                f"9. Remaining caveat/blocker: `{blockers or missing}`",
                "",
                f"Decision: `{mode}` with confidence `{row.get('decision_confidence', '')}` / `{row.get('alignment_confidence_status', '')}`.",
                "",
            ]
        )

    lines.extend(
        [
            "## Per-Scene Decision Table",
            "",
            "| scene | optical frames | SAR frames | frame count ratio | known fps scale | sync mode | offset status | manual anchor | decision | confidence status | can upgrade | caveat/blocker |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in decision_rows:
        lines.append(
            f"| `{row.get('scene', '')}` | {row.get('optical_frame_count', '')} | {row.get('sar_frame_count', '')} | "
            f"{row.get('frame_count_ratio', '')} | {row.get('known_fps_scale_ratio', '')} | `{row.get('sync_mode', '')}` | `{row.get('offset_status', '')}` | "
            f"`{row.get('has_allowed_manual_anchor', '')}` | `{row.get('best_available_alignment_mode', '')}` | "
            f"`{row.get('alignment_confidence_status', '')}` | `{row.get('can_upgrade_from_frame_ratio_hypothesis', '')}` | "
            f"`{row.get('blockers', '')}` |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Numeric frame filenames and frame counts define inventory/order only; they do not prove acquisition FPS or synchronization.",
            "- The known acquisition FPS values are scale metadata only: optical_fps=24 and sar_fps=50. They are not per-frame timestamp truth.",
            "- The acquisition contract uses a software-synchronized zero-offset start assumption, not hardware-grade exact synchronization.",
            "- `timestamp_offset_scale_hypothesis` uses sar_frame = optical_frame * 50 / 24, not sar_frame = optical_frame * 2, and keeps a millisecond-level jitter margin for future window generation.",
            "- Filesystem modification time is recorded as weak filesystem metadata only and never upgrades the alignment mode.",
            "- Visual-diagnosis sample pairs are treated as candidate context, not temporal anchors, unless a source explicitly declares an optical/SAR timing or frame correspondence anchor and avoids GT/selector/posthoc authority.",
            "- OTY2-P1 leaves object_hypothesis_id, readiness gates, primary/secondary observation logic, and identity status unchanged.",
            "",
            "## Boundary Flags",
            "",
        ]
    )
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
        ]
    )
    for key, value in summary.get("artifacts", {}).items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def answer_has(missing_key: str, missing_text: Any) -> str:
    return "no" if missing_key in str(missing_text or "") else "yes"


def sample_rows(rows: Sequence[Mapping[str, Any]], max_rows: int, scene_key: str = "scene") -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(scene_key, "") or "")].append(row)
    out: list[dict[str, Any]] = []
    per_scene = max(1, max_rows // max(1, len(grouped)))
    for scene in sorted(grouped):
        priority = sorted(grouped[scene], key=lambda row: (str(row.get("source_kind", row.get("anchor_type", ""))), str(row.get("source_path", row.get("anchor_id", "")))))
        out.extend(dict(row) for row in priority[:per_scene])
    return out[:max_rows]


def build_summary(
    *,
    timestamp: str,
    generated_at: str,
    scenes: Sequence[str],
    inventory_rows: Sequence[Mapping[str, Any]],
    anchor_rows: Sequence[Mapping[str, Any]],
    decision_rows: Sequence[Mapping[str, Any]],
    artifacts: Mapping[str, str],
    stage_status: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    mode_counts = Counter(str(row.get("best_available_alignment_mode", "") or "unknown") for row in decision_rows)
    confidence_status_counts = Counter(str(row.get("alignment_confidence_status", "") or "unknown") for row in decision_rows)
    offset_status_counts = Counter(str(row.get("offset_status", "") or "unknown") for row in decision_rows)
    upgraded = [row.get("scene", "") for row in decision_rows if boolish(row.get("can_upgrade_from_frame_ratio_hypothesis"))]
    first_decision = decision_rows[0] if decision_rows else {}
    return {
        "generated_at": generated_at,
        "timestamp": timestamp,
        "stage": "OTY2-P1",
        "scenes_audited": join_values(scenes),
        "known_optical_fps": first_decision.get("known_optical_fps", ""),
        "known_sar_fps": first_decision.get("known_sar_fps", ""),
        "known_fps_scale_ratio": first_decision.get("known_fps_scale_ratio", ""),
        "known_fps_is_per_frame_timestamp_truth": False,
        "sync_mode": first_decision.get("sync_mode", ""),
        "offset_seconds": first_decision.get("offset_seconds", ""),
        "software_sync_jitter_ms": first_decision.get("software_sync_jitter_ms", ""),
        "hardware_exact_sync_claimed": False,
        "frame0_alignment_assumed": first_decision.get("offset_status", "") == "software_sync_zero_offset_assumed",
        "frame0_alignment_assumption": first_decision.get("frame0_alignment_assumption", ""),
        "inventory_row_count": len(inventory_rows),
        "anchor_candidate_count": len(anchor_rows),
        "allowed_anchor_candidate_count": sum(1 for row in anchor_rows if boolish(row.get("allowed_for_oty2_p1"))),
        "alignment_mode_counts": {key: mode_counts[key] for key in sorted(mode_counts)},
        "alignment_confidence_status_counts": {key: confidence_status_counts[key] for key in sorted(confidence_status_counts)},
        "offset_status_counts": {key: offset_status_counts[key] for key in sorted(offset_status_counts)},
        "scenes_upgraded_beyond_frame_ratio_hypothesis": join_values(upgraded),
        "any_scene_upgraded_beyond_frame_ratio_hypothesis": bool(upgraded),
        **BOUNDARY_FLAGS,
        "stage_status_by_scene": stage_status,
        "per_scene_decisions": [dict(row) for row in decision_rows],
        "artifacts": dict(artifacts),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_at = datetime.now().isoformat(timespec="seconds")
    scene_config_path = resolve_repo_path(args.scene_config)
    yolo_config_path = resolve_repo_path(args.oty_yolo_config)
    manifest_dir = resolve_repo_path(args.manifest_dir)
    output_root = resolve_repo_path(args.output_root)
    report_dir = REPO_ROOT / "reports" / "oty2"
    sample_dir = report_dir / "samples"

    scene_config = read_json_like(scene_config_path)
    yolo_config = read_json_like(yolo_config_path)
    scenes = select_scenes(args, scene_config, yolo_config)
    stage_status = collect_stage_status(scenes, output_root)
    optical_fps = safe_float(args.optical_fps)
    sar_fps = safe_float(args.sar_fps)
    software_sync_jitter_ms = safe_float(args.software_sync_jitter_ms, default=20.0) or 20.0
    offset_seconds = safe_float(args.offset_seconds, default=0.0) or 0.0
    sync_mode = str(args.sync_mode or "software_sync_zero_offset_assumption").strip()

    inventory_rows: list[dict[str, Any]] = []
    anchor_rows: list[dict[str, Any]] = []

    scene_items = scene_config.get("scenes", {}) if isinstance(scene_config.get("scenes", {}), Mapping) else {}
    yolo_scenes = yolo_config.get("scenes", {}) if isinstance(yolo_config.get("scenes", {}), Mapping) else {}
    for scene in scenes:
        scene_item = scene_items.get(scene, {}) if isinstance(scene_items.get(scene, {}), Mapping) else {}
        scene_paths = scene_item.get("paths", {}) if isinstance(scene_item.get("paths", {}), Mapping) else {}
        yolo_scene_item = yolo_scenes.get(scene, {}) if isinstance(yolo_scenes.get(scene, {}), Mapping) else {}

        inventory_rows.append(inspect_declared_object(scene, "scene_config_scene_fields", scene_config_path, scene_item))
        inventory_rows.append(inspect_declared_object(scene, "oty_yolo_scene_fields", yolo_config_path, yolo_scene_item))
        alignment_payload = yolo_config.get("alignment", {}) if isinstance(yolo_config.get("alignment", {}), Mapping) else {}
        inventory_rows.append(inspect_declared_object(scene, "oty_yolo_alignment_fields", yolo_config_path, alignment_payload))
        inventory_rows.append(
            known_fps_scale_inventory_row(
                scene,
                optical_fps,
                sar_fps,
                sync_mode=sync_mode,
                offset_seconds=offset_seconds,
                software_sync_jitter_ms=software_sync_jitter_ms,
            )
        )

        for key, source_kind in (
            ("optical_frames_dir", "optical_frame_inventory"),
            ("sar_frames_dir", "sar_frame_inventory"),
            ("sar_gray_frames_dir", "sar_gray_frame_inventory"),
            ("depth_dir", "depth_frame_inventory"),
        ):
            path_value = first_nonempty(scene_paths.get(key), yolo_scene_item.get(key))
            inventory_rows.append(inspect_frame_directory(scene, source_kind, path_value))
        inventory_rows.extend(inspect_sidecar_search(scene, scene_paths))

    if manifest_dir.exists():
        for manifest in sorted(manifest_dir.glob("*.csv"), key=path_sort_key):
            manifest_inventory, manifest_anchors = inspect_manifest_file(manifest, scenes)
            inventory_rows.extend(manifest_inventory)
            anchor_rows.extend(manifest_anchors)
    else:
        for scene in scenes:
            inventory_rows.append(
                inventory_row(
                    scene=scene,
                    source_kind="manifest_directory",
                    source_path=manifest_dir,
                    source_exists=False,
                    source_status="manifest_directory_missing",
                    metadata_strength="missing",
                    blockers="missing_manifest_directory",
                )
            )

    repo_text_roots = [REPO_ROOT / "docs", REPO_ROOT / "reports", REPO_ROOT / "outputs"]
    for path in collect_repo_text_files(repo_text_roots, args.max_text_scan_bytes):
        if path.is_relative_to(manifest_dir):
            continue
        if is_oty2_p1_generated_artifact(path):
            continue
        scenes_for_file = scenes_from_text_file(path, scenes)
        for scene in scenes_for_file:
            inventory_rows.append(inspect_text_metadata_file(scene, path, source_kind_for_repo_file(path)))

    inventory_rows = sorted(inventory_rows, key=lambda row: (str(row.get("scene", "")), str(row.get("source_kind", "")), str(row.get("source_path", ""))))
    anchor_rows = sorted(anchor_rows, key=lambda row: (str(row.get("scene", "")), str(row.get("anchor_source", "")), str(row.get("anchor_id", ""))))
    decision_rows = decide_alignment_modes(
        scenes,
        inventory_rows,
        anchor_rows,
        stage_status,
        optical_fps=optical_fps,
        sar_fps=sar_fps,
        sync_mode=sync_mode,
        offset_seconds=offset_seconds,
        software_sync_jitter_ms=software_sync_jitter_ms,
    )

    report_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)
    inventory_csv = report_dir / f"oty2_temporal_metadata_inventory_{timestamp}.csv"
    anchor_csv = report_dir / f"oty2_scene_alignment_anchor_candidates_{timestamp}.csv"
    decision_report_md = report_dir / f"oty2_alignment_mode_decision_report_{timestamp}.md"
    summary_json = report_dir / f"oty2_temporal_alignment_anchor_summary_{timestamp}.json"
    decision_csv = report_dir / f"oty2_alignment_mode_decision_summary_{timestamp}.csv"

    inventory_sample_csv = sample_dir / "oty2_temporal_metadata_inventory_sample.csv"
    anchor_sample_csv = sample_dir / "oty2_scene_alignment_anchor_candidates_sample.csv"
    decision_sample_csv = sample_dir / "oty2_alignment_mode_decision_summary_sample.csv"

    artifacts = {
        "temporal_metadata_inventory": str(inventory_csv),
        "scene_alignment_anchor_candidates": str(anchor_csv),
        "alignment_mode_decision_report": str(decision_report_md),
        "temporal_alignment_anchor_summary": str(summary_json),
        "alignment_mode_decision_summary": str(decision_csv),
        "temporal_metadata_inventory_sample": str(inventory_sample_csv),
        "scene_alignment_anchor_candidates_sample": str(anchor_sample_csv),
        "alignment_mode_decision_summary_sample": str(decision_sample_csv),
    }
    summary = build_summary(
        timestamp=timestamp,
        generated_at=generated_at,
        scenes=scenes,
        inventory_rows=inventory_rows,
        anchor_rows=anchor_rows,
        decision_rows=decision_rows,
        artifacts=artifacts,
        stage_status=stage_status,
    )

    write_csv(inventory_csv, inventory_rows, INVENTORY_FIELDS)
    write_csv(anchor_csv, anchor_rows, ANCHOR_FIELDS)
    write_csv(decision_csv, decision_rows, DECISION_FIELDS)
    write_csv(inventory_sample_csv, sample_rows(inventory_rows, args.max_sample_rows), INVENTORY_FIELDS)
    write_csv(anchor_sample_csv, sample_rows(anchor_rows, args.max_sample_rows), ANCHOR_FIELDS)
    write_csv(decision_sample_csv, decision_rows, DECISION_FIELDS)
    write_json(summary_json, summary)
    decision_report_md.write_text(render_decision_report(summary, decision_rows), encoding="utf-8")
    return summary


def select_scenes(args: argparse.Namespace, scene_config: Mapping[str, Any], yolo_config: Mapping[str, Any]) -> list[str]:
    if args.scenes:
        return split_path_values(args.scenes)
    scenes: list[str] = []
    scene_items = scene_config.get("scenes", {})
    if isinstance(scene_items, Mapping):
        scenes.extend(str(scene) for scene in scene_items)
    yolo_scene_items = yolo_config.get("scenes", {})
    if isinstance(yolo_scene_items, Mapping):
        scenes.extend(str(scene) for scene in yolo_scene_items)
    return sorted(set(scene for scene in scenes if scene))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-config", default="configs/scene_config.yaml")
    parser.add_argument("--oty-yolo-config", default="configs/oty_yolo_stream_config.yaml")
    parser.add_argument("--manifest-dir", default="manifests")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--scenes", default="")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--optical-fps", default="24")
    parser.add_argument("--sar-fps", default="50")
    parser.add_argument("--sync-mode", default="software_sync_zero_offset_assumption")
    parser.add_argument("--offset-seconds", default="0")
    parser.add_argument("--software-sync-jitter-ms", default="20")
    parser.add_argument("--max-sample-rows", type=int, default=80)
    parser.add_argument("--max-text-scan-bytes", type=int, default=5_000_000)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
