"""Probe OTY0 detection crop readiness for ReID-aware stitching.

This diagnostic only validates real optical crop extraction and local
embedding-backend availability. It does not write crops, embeddings, tracker
outputs, SAR pairing/support artifacts, final boxes, revised GT, selectors, or
identity truth.
"""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENES = ("GM_RM011", "GM_RM019", "GM_RM017")
SUMMARY_FIELDS = [
    "scene",
    "rows_total",
    "rows_with_optical_path",
    "image_exists",
    "image_missing",
    "image_unreadable",
    "bbox_present",
    "bbox_parse_failed",
    "bbox_invalid_geometry",
    "bbox_fully_out_of_bounds",
    "bbox_partially_out_of_bounds_clamped",
    "crop_extractable",
    "crop_failed",
    "embedding_backend",
    "embedding_available",
    "embedded_count",
    "conclusion_scene",
]


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def valid_geometry(self) -> bool:
        return self.x2 > self.x1 and self.y2 > self.y1

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    def clamp(self, width: int, height: int) -> "BBox":
        return BBox(
            min(max(self.x1, 0.0), float(width)),
            min(max(self.y1, 0.0), float(height)),
            min(max(self.x2, 0.0), float(width)),
            min(max(self.y2, 0.0), float(height)),
        )

    def as_list(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [row for row in reader if not duplicate_header_row(row)]
        return rows, list(reader.fieldnames or [])


def duplicate_header_row(row: Mapping[str, Any]) -> bool:
    values = [str(value or "").strip() for value in row.values() if str(value or "").strip()]
    if not values:
        return False
    hits = sum(1 for key, value in row.items() if str(value or "").strip() == key)
    return hits >= max(2, len(values) // 2)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first_present(row: Mapping[str, Any], names: Sequence[str]) -> tuple[str, str]:
    for name in names:
        value = str(row.get(name, "") or "").strip()
        if value:
            return name, value
    return "", ""


def detect_field(fieldnames: Sequence[str], candidates: Sequence[str]) -> str:
    lower_to_name = {name.lower(): name for name in fieldnames}
    for candidate in candidates:
        if candidate.lower() in lower_to_name:
            return lower_to_name[candidate.lower()]
    return ""


def parse_bbox(row: Mapping[str, Any], fieldnames: Sequence[str]) -> tuple[BBox | None, str, str]:
    schemas = [
        ("bbox_x1,bbox_y1,bbox_x2,bbox_y2", ("bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2")),
        ("x1,y1,x2,y2", ("x1", "y1", "x2", "y2")),
        ("xmin,ymin,xmax,ymax", ("xmin", "ymin", "xmax", "ymax")),
        ("left,top,right,bottom", ("left", "top", "right", "bottom")),
    ]
    lower_to_name = {name.lower(): name for name in fieldnames}
    for label, names in schemas:
        actual = [lower_to_name.get(name.lower(), "") for name in names]
        if all(actual):
            values = [parse_float(row.get(name)) for name in actual]
            if all(value is not None for value in values):
                return BBox(*(float(value) for value in values if value is not None)), label, ""
            return None, label, "bbox_parse_failed"

    serialized_fields = (
        "bbox",
        "box",
        "xyxy",
        "bbox_xyxy",
        "bbox_xyxy_original",
        "bbox_original",
        "bbox_json",
    )
    for field in serialized_fields:
        actual = lower_to_name.get(field.lower())
        if not actual:
            continue
        text = str(row.get(actual, "") or "").strip()
        if not text:
            continue
        values = parse_serialized_bbox(text)
        if values is None:
            return None, actual, "bbox_parse_failed"
        return BBox(*values), actual, ""
    return None, "", "missing_bbox"


def parse_serialized_bbox(text: str) -> tuple[float, float, float, float] | None:
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        values = values_from_serialized(parsed)
        if values is not None:
            return values
    numbers = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", text)]
    if len(numbers) >= 4:
        return tuple(numbers[:4])  # type: ignore[return-value]
    return None


def values_from_serialized(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, Mapping):
        for keys in (("x1", "y1", "x2", "y2"), ("xmin", "ymin", "xmax", "ymax"), ("left", "top", "right", "bottom")):
            if all(key in value for key in keys):
                parsed = [parse_float(value.get(key)) for key in keys]
                if all(item is not None for item in parsed):
                    return tuple(float(item) for item in parsed if item is not None)  # type: ignore[return-value]
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        parsed = [parse_float(item) for item in value[:4]]
        if all(item is not None for item in parsed):
            return tuple(float(item) for item in parsed if item is not None)  # type: ignore[return-value]
    return None


def resolve_optical_path(value: str, source_table: Path) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw
    candidates = [
        source_table.parent / raw,
        REPO_ROOT / raw,
        Path.cwd() / raw,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def image_size(path: Path) -> tuple[int, int, str]:
    try:
        from PIL import Image

        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            return int(img.width), int(img.height), "pil"
    except Exception as pil_exc:
        try:
            import cv2  # type: ignore

            img = cv2.imread(str(path))
            if img is None:
                return 0, 0, f"unreadable_pil_cv2:{pil_exc!r}"
            height, width = img.shape[:2]
            return int(width), int(height), "cv2"
        except Exception as cv_exc:
            return 0, 0, f"unreadable_pil_cv2:{pil_exc!r};{cv_exc!r}"


def crop_in_memory(path: Path, bbox: BBox) -> tuple[int, int, str]:
    try:
        from PIL import Image

        with Image.open(path) as img:
            crop = img.crop((round(bbox.x1), round(bbox.y1), round(bbox.x2), round(bbox.y2)))
            return int(crop.width), int(crop.height), "pil"
    except Exception as pil_exc:
        try:
            import cv2  # type: ignore

            img = cv2.imread(str(path))
            if img is None:
                return 0, 0, f"crop_failed_pil_cv2:{pil_exc!r}"
            y1, y2 = round(bbox.y1), round(bbox.y2)
            x1, x2 = round(bbox.x1), round(bbox.x2)
            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                return 0, 0, "empty_cv2_crop"
            return int(crop.shape[1]), int(crop.shape[0]), "cv2"
        except Exception as cv_exc:
            return 0, 0, f"crop_failed_pil_cv2:{pil_exc!r};{cv_exc!r}"


def scene_for_table(path: Path) -> str:
    summary = path.parent / "oty0_summary.json"
    if summary.exists():
        try:
            payload = json.loads(summary.read_text(encoding="utf-8"))
            scene = str(payload.get("scene", "") or "").strip()
            if scene:
                return scene
        except Exception:
            pass
    rows, _ = read_csv_rows(path)
    for row in rows:
        scene = str(row.get("scene", "") or "").strip()
        if scene:
            return scene
    return ""


def discover_detection_tables(output_root: Path, scenes: Sequence[str]) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    discovered: list[dict[str, Any]] = []
    selected: dict[str, Path] = {}
    direct_dirs = sorted(output_root.glob("oty0_yolo_detection_stream_audit_*"), key=lambda path: path.name, reverse=True)
    for scene in scenes:
        for output_dir in direct_dirs:
            table = output_dir / "oty0_yolo_detection_table.csv"
            if not table.exists():
                continue
            table_scene = scene_for_table(table)
            rows, fields = read_csv_rows(table)
            row_count = sum(1 for row in rows if str(row.get("scene", "") or table_scene).strip() == scene)
            discovered.append(
                {
                    "scene_requested": scene,
                    "table_scene": table_scene,
                    "path": str(table),
                    "row_count_for_scene": row_count,
                    "fieldnames": ",".join(fields),
                    "selected": False,
                    "selection_policy": "direct_oty0_output_latest_scene_match",
                }
            )
            if row_count and scene not in selected:
                selected[scene] = table
                discovered[-1]["selected"] = True
                break

    if len(selected) == len(scenes):
        return selected, discovered

    for table in sorted(output_root.rglob("oty0_yolo_detection_table.csv"), key=lambda path: str(path), reverse=True):
        rows, fields = read_csv_rows(table)
        table_scene = scene_for_table(table)
        for scene in scenes:
            if scene in selected:
                continue
            row_count = sum(1 for row in rows if str(row.get("scene", "") or table_scene).strip() == scene)
            if not row_count:
                continue
            selected[scene] = table
            discovered.append(
                {
                    "scene_requested": scene,
                    "table_scene": table_scene,
                    "path": str(table),
                    "row_count_for_scene": row_count,
                    "fieldnames": ",".join(fields),
                    "selected": True,
                    "selection_policy": "recursive_fallback_scene_match",
                }
            )
    return selected, discovered


def explicit_detection_tables(paths: Sequence[str], scenes: Sequence[str]) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    selected: dict[str, Path] = {}
    discovered: list[dict[str, Any]] = []
    for raw in paths:
        table = Path(raw)
        if not table.exists():
            raise FileNotFoundError(f"OTY0 detection table not found: {table}")
        rows, fields = read_csv_rows(table)
        table_scene = scene_for_table(table)
        for scene in scenes:
            row_count = sum(1 for row in rows if str(row.get("scene", "") or table_scene).strip() == scene)
            discovered.append(
                {
                    "scene_requested": scene,
                    "table_scene": table_scene,
                    "path": str(table),
                    "row_count_for_scene": row_count,
                    "fieldnames": ",".join(fields),
                    "selected": False,
                    "selection_policy": "explicit_cli_table",
                }
            )
            if row_count and scene not in selected:
                selected[scene] = table
                discovered[-1]["selected"] = True
    missing = [scene for scene in scenes if scene not in selected]
    if missing:
        raise FileNotFoundError(f"Explicit tables did not cover scenes: {', '.join(missing)}")
    return selected, discovered


def backend_probe() -> dict[str, Any]:
    facts: dict[str, Any] = {
        "torch_available": False,
        "torchvision_available": False,
        "pil_available": importlib.util.find_spec("PIL") is not None,
        "cv2_available": importlib.util.find_spec("cv2") is not None,
        "repo_local_reid_utility": "",
        "embedding_backend": "missing_local_embedding_backend",
        "embedding_available": False,
        "embedding_dim": "",
        "embedding_l2_normed": "",
        "backend_reason": "no cached pretrained torchvision embedding weights or repo-local ReID utility found",
    }
    if importlib.util.find_spec("torch") is None:
        facts["backend_reason"] = "torch import not available"
        maybe_add_repo_local_embedding_utility(facts)
        return facts
    facts["torch_available"] = True
    if importlib.util.find_spec("torchvision") is None:
        facts["backend_reason"] = "torch available but torchvision import not available"
        maybe_add_repo_local_embedding_utility(facts)
        return facts
    facts["torchvision_available"] = True
    try:
        import torch
        from torchvision.models import ResNet18_Weights

        checkpoints = [Path(torch.hub.get_dir()) / "checkpoints"]
        torch_home = os.environ.get("TORCH_HOME", "")
        if torch_home:
            checkpoints.append(Path(torch_home) / "hub" / "checkpoints")
        weight_name = Path(ResNet18_Weights.DEFAULT.url).name
        for directory in checkpoints:
            cached = directory / weight_name
            if cached.exists():
                facts["embedding_backend"] = "torchvision_resnet18_imagenet_cached"
                facts["embedding_available"] = True
                facts["embedding_dim"] = 512
                facts["embedding_l2_normed"] = True
                facts["backend_reason"] = f"cached local weights found at {cached}"
                return facts
        facts["backend_reason"] = f"torch/torchvision importable but cached {weight_name} not found"
    except Exception as exc:
        facts["backend_reason"] = f"torchvision cached-weight probe failed: {exc!r}"
    maybe_add_repo_local_embedding_utility(facts)
    return facts


def maybe_add_repo_local_embedding_utility(facts: dict[str, Any]) -> None:
    this_file = Path(__file__).resolve()
    for root in (REPO_ROOT / "src", REPO_ROOT / "tools"):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path.resolve() == this_file:
                continue
            name = path.name.lower()
            if "reid" in name or "embedding" in name:
                facts["repo_local_reid_utility"] = str(path)
                if not facts.get("embedding_available"):
                    facts["backend_reason"] = (
                        facts.get("backend_reason", "")
                        + f"; repo-local embedding/ReID utility candidate detected at {path}"
                    )
                return


def evaluate_table(scene: str, table: Path, backend: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    rows, fieldnames = read_csv_rows(table)
    scene_field = detect_field(fieldnames, ("scene", "scene_id", "sequence", "sequence_id"))
    frame_field = detect_field(fieldnames, ("optical_frame_num", "frame_id", "frame", "frame_index", "optical_frame_id"))
    det_field = detect_field(fieldnames, ("det_id", "detection_id", "detection_index", "id"))
    path_field = detect_field(fieldnames, ("optical_path", "image_path", "frame_path", "img_path"))
    confidence_field = detect_field(fieldnames, ("confidence", "conf", "score"))
    class_field = detect_field(fieldnames, ("class_name", "class_id", "category", "label"))
    summary = {field: 0 for field in SUMMARY_FIELDS}
    summary["scene"] = scene
    summary["embedding_backend"] = backend.get("embedding_backend", "missing_local_embedding_backend")
    summary["embedding_available"] = bool(backend.get("embedding_available"))

    metadata: list[dict[str, Any]] = []
    bbox_schema_counts: dict[str, int] = defaultdict(int)
    for index, row in enumerate(rows, start=1):
        row_scene = str(row.get(scene_field, "") if scene_field else row.get("scene", "")).strip() or scene
        if row_scene != scene:
            continue
        summary["rows_total"] += 1
        det_id = str(row.get(det_field, "") if det_field else "").strip() or f"row_{index:06d}"
        frame_key = str(row.get(frame_field, "") if frame_field else "").strip()
        optical_value = str(row.get(path_field, "") if path_field else "").strip()
        bbox, bbox_schema, bbox_reason = parse_bbox(row, fieldnames)
        if bbox_schema:
            bbox_schema_counts[bbox_schema] += 1
        if bbox is not None:
            summary["bbox_present"] += 1
        elif bbox_reason == "bbox_parse_failed":
            summary["bbox_parse_failed"] += 1

        item = {
            "det_id_ignored": det_id,
            "scene": scene,
            "frame_key": frame_key,
            "source_table": str(table),
            "optical_path": optical_value,
            "image_width": "",
            "image_height": "",
            "bbox_xyxy_original": json.dumps(bbox.as_list()) if bbox else "",
            "bbox_xyxy_clamped": "",
            "bbox_schema_used": bbox_schema,
            "bbox_status": "",
            "crop_width": "",
            "crop_height": "",
            "crop_area": "",
            "failure_reason": "",
            "confidence_field": confidence_field,
            "class_field": class_field,
        }
        if not optical_value:
            item["failure_reason"] = "missing_image_path"
            item["bbox_status"] = bbox_reason or "not_checked_missing_image_path"
            summary["crop_failed"] += 1
            metadata.append(item)
            continue
        summary["rows_with_optical_path"] += 1
        optical_path = resolve_optical_path(optical_value, table)
        if not optical_path.exists():
            item["failure_reason"] = "non_existing_image_file"
            item["bbox_status"] = bbox_reason or "not_checked_missing_image_file"
            summary["image_missing"] += 1
            summary["crop_failed"] += 1
            metadata.append(item)
            continue
        summary["image_exists"] += 1
        width, height, reader = image_size(optical_path)
        if width <= 0 or height <= 0:
            item["failure_reason"] = reader
            item["bbox_status"] = bbox_reason or "not_checked_unreadable_image"
            summary["image_unreadable"] += 1
            summary["crop_failed"] += 1
            metadata.append(item)
            continue
        item["image_width"] = width
        item["image_height"] = height
        if bbox is None:
            item["failure_reason"] = bbox_reason
            item["bbox_status"] = bbox_reason
            summary["crop_failed"] += 1
            metadata.append(item)
            continue
        if not bbox.valid_geometry:
            item["failure_reason"] = "invalid_bbox_geometry"
            item["bbox_status"] = "invalid_bbox_geometry"
            summary["bbox_invalid_geometry"] += 1
            summary["crop_failed"] += 1
            metadata.append(item)
            continue
        clamped = bbox.clamp(width, height)
        item["bbox_xyxy_clamped"] = json.dumps(clamped.as_list())
        if not clamped.valid_geometry:
            item["failure_reason"] = "bbox_fully_out_of_bounds"
            item["bbox_status"] = "bbox_fully_out_of_bounds"
            summary["bbox_fully_out_of_bounds"] += 1
            summary["crop_failed"] += 1
            metadata.append(item)
            continue
        if clamped != bbox:
            item["bbox_status"] = "bbox_partially_out_of_bounds_clamped"
            summary["bbox_partially_out_of_bounds_clamped"] += 1
        else:
            item["bbox_status"] = "valid_in_bounds_bbox"
        crop_w, crop_h, crop_reader = crop_in_memory(optical_path, clamped)
        if crop_w <= 0 or crop_h <= 0:
            item["failure_reason"] = crop_reader
            summary["crop_failed"] += 1
            metadata.append(item)
            continue
        item["crop_width"] = crop_w
        item["crop_height"] = crop_h
        item["crop_area"] = crop_w * crop_h
        summary["crop_extractable"] += 1
        metadata.append(item)

    summary["embedded_count"] = 0
    summary["conclusion_scene"] = scene_conclusion(summary, backend)
    facts = {
        "fieldnames": fieldnames,
        "scene_field": scene_field,
        "frame_field": frame_field,
        "det_id_field_ignored": det_field,
        "path_field": path_field,
        "bbox_schema_counts": dict(sorted(bbox_schema_counts.items())),
        "source_table": str(table),
    }
    return summary, metadata, facts


def scene_conclusion(summary: Mapping[str, Any], backend: Mapping[str, Any]) -> str:
    rows = int(summary.get("rows_total", 0) or 0)
    crops = int(summary.get("crop_extractable", 0) or 0)
    if rows <= 0:
        return "DETECTION_CROP_INPUTS_INSUFFICIENT"
    if crops <= 0:
        return "DETECTION_CROP_INPUTS_INSUFFICIENT"
    image_problem = int(summary.get("image_missing", 0) or 0) + int(summary.get("image_unreadable", 0) or 0)
    bbox_problem = (
        int(summary.get("bbox_parse_failed", 0) or 0)
        + int(summary.get("bbox_invalid_geometry", 0) or 0)
        + int(summary.get("bbox_fully_out_of_bounds", 0) or 0)
    )
    if image_problem or bbox_problem:
        return "DETECTION_CROP_INPUTS_INSUFFICIENT"
    if backend.get("embedding_available"):
        return "DETECTION_CROP_EMBEDDING_READY_FOR_REID_STITCHING"
    return "DETECTION_CROP_EXTRACTION_READY_EMBEDDING_BACKEND_MISSING"


def overall_conclusion(rows: Sequence[Mapping[str, Any]]) -> str:
    scene_labels = {str(row.get("conclusion_scene", "")) for row in rows}
    if "PROBE_FAILED" in scene_labels:
        return "PROBE_FAILED"
    if "DETECTION_CROP_INPUTS_INSUFFICIENT" in scene_labels:
        return "DETECTION_CROP_INPUTS_INSUFFICIENT"
    if "DETECTION_CROP_EXTRACTION_READY_EMBEDDING_BACKEND_MISSING" in scene_labels:
        return "DETECTION_CROP_EXTRACTION_READY_EMBEDDING_BACKEND_MISSING"
    return "DETECTION_CROP_EMBEDDING_READY_FOR_REID_STITCHING"


def git_fact(args: Sequence[str]) -> str:
    import subprocess

    try:
        return subprocess.check_output(["git", *args], cwd=str(REPO_ROOT), text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return "none"
    out = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(out)


def render_report(
    timestamp: str,
    command: str,
    branch: str,
    commit: str,
    discovered: Sequence[Mapping[str, Any]],
    source_facts: Mapping[str, Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
    backend: Mapping[str, Any],
    conclusion: str,
    summary_path: Path,
) -> str:
    selected = [row for row in discovered if str(row.get("selected", "")) == "True" or row.get("selected") is True]
    lines = [
        "# OTY2 Detection Crop Embedding Probe",
        "",
        f"Timestamp: `{timestamp}`",
        f"Repository: `{REPO_ROOT}`",
        f"Branch: `{branch}`",
        f"Git commit before changes: `{commit}`",
        "",
        "## Boundary",
        "",
        "This diagnostic validates OTY0 detection crop extraction from real optical images and checks local embedding-backend availability. It does not modify OTY0/OTY1/OTY1a/OTY1t runtime, tune tracker parameters, replace detector/tracker, run SAR pairing/support, generate final boxes, generate identity truth, or promote `GM_RM011` into clean `215`.",
        "",
        "No crop images, embedding arrays, model weights, atlas outputs, final annotations, revised GT, runtime predictions, selector/ranking outputs, weighted fusion artifacts, or SAR pairing/support outputs were written by the script.",
        "",
        "## Command",
        "",
        "```powershell",
        command,
        "```",
        "",
        "## Data Tables Discovered And Used",
        "",
        md_table(selected, ["scene_requested", "table_scene", "row_count_for_scene", "path", "selection_policy"]),
        "",
        "## Identifier And BBox Schema",
        "",
    ]
    for scene, facts in source_facts.items():
        lines.extend(
            [
                f"### `{scene}`",
                "",
                f"- source table: `{facts.get('source_table', '')}`",
                f"- scene id field: `{facts.get('scene_field', '')}`",
                f"- frame id field: `{facts.get('frame_field', '')}`",
                f"- detection id field, intentionally ignored as identity: `{facts.get('det_id_field_ignored', '')}`",
                f"- optical path field: `{facts.get('path_field', '')}`",
                f"- bbox schema counts: `{json.dumps(facts.get('bbox_schema_counts', {}), ensure_ascii=False)}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Per-Scene Summary",
            "",
            md_table(summaries, SUMMARY_FIELDS),
            "",
            f"Small summary CSV: `{summary_path}`",
            "",
            "## Required Answers",
            "",
            "1. Are `optical_path` values valid for `GM_RM011`, `GM_RM019`, and `GM_RM017`?",
            "",
            answer_paths(summaries),
            "",
            "2. Are bbox coordinates sufficient and in image bounds?",
            "",
            answer_bboxes(summaries, source_facts),
            "",
            "3. How many detection crops can be extracted per scene?",
            "",
            answer_count_field(summaries, "crop_extractable"),
            "",
            "4. How many fail due to missing image / invalid bbox / out-of-bounds box?",
            "",
            answer_failures(summaries),
            "",
            "5. Which embedding backend is available locally without adding heavy committed assets?",
            "",
            f"`{backend.get('embedding_backend')}`. Availability: `{backend.get('embedding_available')}`. Reason: {backend.get('backend_reason')}. Import facts: torch=`{backend.get('torch_available')}`, torchvision=`{backend.get('torchvision_available')}`, PIL=`{backend.get('pil_available')}`, cv2=`{backend.get('cv2_available')}`.",
            "",
            "6. What embedding schema should be used for ReID stitching?",
            "",
            "- Detection-level embedding table fields: `scene`, `frame_id`, `det_id_ignored`, `optical_path`, `bbox_xyxy_original`, `bbox_xyxy_clamped`, `crop_w`, `crop_h`, `crop_status`, `embedding_backend`, `embedding_dim`, `embedding_l2_normed`, `embedding_artifact_path_uncommitted`, `source_detection_table`, `created_by_probe`, `created_at`.",
            "- `det_id_ignored` must remain a source-row handle only; it must not be treated as identity truth.",
            "- `embedding_artifact_path_uncommitted` should point to ignored/uncommitted local artifacts generated by a later embedding job, not to committed arrays.",
            "",
            "7. How should embeddings connect to OTY1t BoT-SORT/ByteTrack tracks?",
            "",
            "Embeddings connect to OTY1t BoT-SORT/ByteTrack tracks by frame-level detection association. The next probe should match tracker boxes and OTY0 detection boxes within the same `scene` and `frame_id` using exact source-row linkage if preserved, otherwise a deterministic IoU rule. It must not assume OTY0 detection id is identity.",
            "",
            "8. What exact inputs will the next ReID-aware tracklet stitching probe need?",
            "",
            "- OTY1t tracker replay output for BoT-SORT/ByteTrack, especially normalized active-only variants.",
            "- Per-frame tracker boxes and track ids.",
            "- OTY0 detection rows with `optical_path` and bbox.",
            "- A deterministic same-scene/same-frame matching rule between tracker boxes and OTY0 detections, such as IoU or exact source-row linkage if already preserved.",
            "- Detection crop embeddings generated from real optical images.",
            "- Tracklet segmentation metadata: start/end frame, gaps, neighboring fragmented tracklets.",
            "- Conservative thresholds for candidate stitch proposal only, not final identity truth.",
            "- Review/report output showing candidate stitch pairs and evidence, without producing final annotation.",
            "",
            "## Proposed ReID Stitching Schemas",
            "",
            "Detection-level embedding table:",
            "",
            "```text",
            "scene",
            "frame_id",
            "det_id_ignored",
            "optical_path",
            "bbox_xyxy_original",
            "bbox_xyxy_clamped",
            "crop_w",
            "crop_h",
            "crop_status",
            "embedding_backend",
            "embedding_dim",
            "embedding_l2_normed",
            "embedding_artifact_path_uncommitted",
            "source_detection_table",
            "created_by_probe",
            "created_at",
            "```",
            "",
            "Tracklet-level aggregation table:",
            "",
            "```text",
            "scene",
            "tracker_name",
            "tracker_variant",
            "track_id",
            "frame_start",
            "frame_end",
            "num_detections",
            "linked_det_ids_ignored",
            "linked_embedding_count",
            "tracklet_embedding_policy",
            "tracklet_embedding_artifact_path_uncommitted",
            "motion_summary_path_or_inline_fields",
            "source_tracker_replay",
            "created_at",
            "```",
            "",
            "## Conclusion",
            "",
            "```text",
            conclusion,
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def answer_paths(rows: Sequence[Mapping[str, Any]]) -> str:
    parts = []
    for row in rows:
        scene = row.get("scene", "")
        total = int(row.get("rows_total", 0) or 0)
        with_path = int(row.get("rows_with_optical_path", 0) or 0)
        exists = int(row.get("image_exists", 0) or 0)
        missing = int(row.get("image_missing", 0) or 0)
        unreadable = int(row.get("image_unreadable", 0) or 0)
        parts.append(f"- `{scene}`: `{with_path}/{total}` rows have `optical_path`; `{exists}` images exist; `{missing}` missing; `{unreadable}` unreadable.")
    return "\n".join(parts)


def answer_bboxes(rows: Sequence[Mapping[str, Any]], source_facts: Mapping[str, Mapping[str, Any]]) -> str:
    parts = []
    for row in rows:
        scene = str(row.get("scene", ""))
        total = int(row.get("rows_total", 0) or 0)
        present = int(row.get("bbox_present", 0) or 0)
        parse_failed = int(row.get("bbox_parse_failed", 0) or 0)
        invalid = int(row.get("bbox_invalid_geometry", 0) or 0)
        fully_oob = int(row.get("bbox_fully_out_of_bounds", 0) or 0)
        partial = int(row.get("bbox_partially_out_of_bounds_clamped", 0) or 0)
        schema = json.dumps(source_facts.get(scene, {}).get("bbox_schema_counts", {}), ensure_ascii=False)
        parts.append(f"- `{scene}`: `{present}/{total}` bboxes present using `{schema}`; parse_failed=`{parse_failed}`, invalid_geometry=`{invalid}`, fully_out_of_bounds=`{fully_oob}`, partially_clamped=`{partial}`.")
    return "\n".join(parts)


def answer_count_field(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    return "\n".join(f"- `{row.get('scene', '')}`: `{row.get(field, 0)}`" for row in rows)


def answer_failures(rows: Sequence[Mapping[str, Any]]) -> str:
    parts = []
    for row in rows:
        invalid_bbox = int(row.get("bbox_parse_failed", 0) or 0) + int(row.get("bbox_invalid_geometry", 0) or 0)
        oob = int(row.get("bbox_fully_out_of_bounds", 0) or 0) + int(row.get("bbox_partially_out_of_bounds_clamped", 0) or 0)
        parts.append(f"- `{row.get('scene', '')}`: missing_image=`{row.get('image_missing', 0)}`, invalid_bbox=`{invalid_bbox}`, out_of_bounds_or_clamped=`{oob}`, crop_failed=`{row.get('crop_failed', 0)}`.")
    return "\n".join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenes", nargs="+", default=list(DEFAULT_SCENES))
    parser.add_argument("--oty0-detection-table", action="append", default=[])
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    scenes = list(args.scenes)
    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = REPO_ROOT / output_root
    if args.oty0_detection_table:
        selected, discovered = explicit_detection_tables(args.oty0_detection_table, scenes)
    else:
        selected, discovered = discover_detection_tables(output_root, scenes)
    missing = [scene for scene in scenes if scene not in selected]
    if missing:
        raise FileNotFoundError(f"No OTY0 detection table found for scenes: {', '.join(missing)}")

    backend = backend_probe()
    summaries: list[dict[str, Any]] = []
    source_facts: dict[str, dict[str, Any]] = {}
    for scene in scenes:
        summary, _metadata, facts = evaluate_table(scene, selected[scene], backend)
        summaries.append(summary)
        source_facts[scene] = facts
    conclusion = overall_conclusion(summaries)
    summary_path = REPO_ROOT / "reports" / "oty2" / "samples" / f"oty2_detection_crop_embedding_probe_summary_{timestamp}.csv"
    report_path = REPO_ROOT / "reports" / "oty2" / f"oty2_detection_crop_embedding_probe_{timestamp}.md"
    write_csv(summary_path, summaries, SUMMARY_FIELDS)
    command = " ".join([str(Path(sys.executable)), *sys.argv])
    report = render_report(
        timestamp=timestamp,
        command=command,
        branch=git_fact(["branch", "--show-current"]),
        commit=git_fact(["rev-parse", "--short", "HEAD"]),
        discovered=discovered,
        source_facts=source_facts,
        summaries=summaries,
        backend=backend,
        conclusion=conclusion,
        summary_path=summary_path,
    )
    write_text(report_path, report)
    payload = {
        "timestamp": timestamp,
        "report": str(report_path),
        "summary_csv": str(summary_path),
        "conclusion": conclusion,
        "summaries": summaries,
        "backend": backend,
        "selected_tables": {scene: str(path) for scene, path in selected.items()},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
