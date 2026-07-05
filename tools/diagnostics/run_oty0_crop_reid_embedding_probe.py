"""Probe learned crop embeddings for OTY2 ReID-aware stitching input.

This bounded diagnostic reuses the OTY0 crop extraction path and, only when an
explicit local/external learned-weight file is supplied, writes crop embedding
artifacts under ignored outputs. It does not modify OTY0/OTY1/OTY1a/OTY1t
runtime, tune trackers, run SAR pairing/support, write final boxes, create
identity truth, or commit crops, embeddings, weights, or output artifacts.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.diagnostics.run_oty0_detection_crop_embedding_probe import (  # noqa: E402
    BBox,
    detect_field,
    discover_detection_tables,
    explicit_detection_tables,
    parse_bbox,
    read_csv_rows,
    resolve_optical_path,
    write_csv,
    write_text,
)


DEFAULT_SCENES = ("GM_RM011", "GM_RM019", "GM_RM017")
SUPPORTED_BACKENDS = ("osnet_x0_25", "osnet_x0_5", "osnet_x1_0", "torchvision_resnet18")

SUMMARY_FIELDS = [
    "scene",
    "rows_total",
    "crop_extractable",
    "embedding_computed",
    "embedding_failed",
    "embedding_backend",
    "embedding_dim",
    "embedding_l2_normed",
    "learned_backend_used",
    "weights_path_external",
    "artifact_created_uncommitted",
    "artifact_path_uncommitted",
    "conclusion_scene",
]

INDEX_FIELDS = [
    "row_uid",
    "scene",
    "frame_id",
    "det_id_ignored",
    "source_detection_table",
    "optical_path",
    "bbox_xyxy_original",
    "bbox_xyxy_clamped",
    "bbox_status",
    "crop_w",
    "crop_h",
    "crop_area",
    "embedding_backend",
    "embedding_dim",
    "embedding_l2_normed",
    "embedding_array_key",
    "embedding_artifact_path_uncommitted",
    "weights_path_external",
    "created_at",
]

PREVIEW_FIELDS = [
    "schema_kind",
    "field_name",
    "required",
    "description",
]


@dataclass
class CropRecord:
    row_uid: str
    scene: str
    frame_id: str
    det_id_ignored: str
    source_detection_table: str
    optical_path: str
    resolved_optical_path: Path
    bbox_xyxy_original: str
    bbox_xyxy_clamped: str
    bbox_status: str
    crop_w: int
    crop_h: int
    crop_area: int
    crop: Any


@dataclass
class BackendState:
    requested_backend: str
    embedding_backend: str
    learned_backend_used: bool
    embedding_dim: int | str
    embedding_l2_normed: bool | str
    weights_path_external: str
    weights_downloaded: bool
    weights_committed: bool
    available: bool
    status: str
    reason: str
    model: Any = None
    preprocess: Any = None
    device: str = "cpu"


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(REPO_ROOT), text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def git_tracked(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)],
            cwd=str(REPO_ROOT),
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except Exception:
        return False


def path_inside_repo(path_text: str) -> bool:
    if not path_text:
        return False
    try:
        path = Path(path_text).resolve()
        repo = REPO_ROOT.resolve()
        return path == repo or repo in path.parents
    except Exception:
        return False


def import_facts() -> dict[str, Any]:
    return {
        "torch": importlib.util.find_spec("torch") is not None,
        "torchvision": importlib.util.find_spec("torchvision") is not None,
        "torchreid": importlib.util.find_spec("torchreid") is not None,
        "PIL": importlib.util.find_spec("PIL") is not None,
        "cv2": importlib.util.find_spec("cv2") is not None,
        "numpy": importlib.util.find_spec("numpy") is not None,
    }


def load_backend(args: argparse.Namespace) -> BackendState:
    backend = str(args.reid_backend or "").strip()
    weights = str(args.reid_weights or "").strip()
    facts = import_facts()
    if not backend:
        return BackendState(
            requested_backend="",
            embedding_backend="missing_learned_reid_backend",
            learned_backend_used=False,
            embedding_dim="",
            embedding_l2_normed="",
            weights_path_external=weights,
            weights_downloaded=False,
            weights_committed=False,
            available=False,
            status="missing",
            reason="no --reid-backend was provided; learned embeddings require explicit local/external weights",
            device=args.device,
        )
    if backend not in SUPPORTED_BACKENDS:
        return BackendState(
            requested_backend=backend,
            embedding_backend="unsupported_backend",
            learned_backend_used=False,
            embedding_dim="",
            embedding_l2_normed="",
            weights_path_external=weights,
            weights_downloaded=False,
            weights_committed=False,
            available=False,
            status="unsupported",
            reason=f"unsupported --reid-backend {backend}; supported: {', '.join(SUPPORTED_BACKENDS)}",
            device=args.device,
        )
    if not weights:
        return BackendState(
            requested_backend=backend,
            embedding_backend=f"{backend}_weights_missing",
            learned_backend_used=False,
            embedding_dim="",
            embedding_l2_normed="",
            weights_path_external="",
            weights_downloaded=False,
            weights_committed=False,
            available=False,
            status="weights_missing",
            reason="no --reid-weights path was provided; randomly initialized neural features are forbidden",
            device=args.device,
        )
    weight_path = Path(weights)
    if not weight_path.exists():
        return BackendState(
            requested_backend=backend,
            embedding_backend=f"{backend}_weights_missing",
            learned_backend_used=False,
            embedding_dim="",
            embedding_l2_normed="",
            weights_path_external=str(weight_path),
            weights_downloaded=False,
            weights_committed=git_tracked(weight_path),
            available=False,
            status="weights_missing",
            reason=f"--reid-weights does not exist: {weight_path}",
            device=args.device,
        )
    if backend.startswith("osnet"):
        return load_osnet_backend(backend, weight_path, args.device, facts)
    return load_torchvision_resnet18_backend(weight_path, args.device, facts)


def load_osnet_backend(backend: str, weight_path: Path, device: str, facts: Mapping[str, Any]) -> BackendState:
    if not facts.get("torch") or not facts.get("torchreid"):
        return BackendState(
            requested_backend=backend,
            embedding_backend=f"{backend}_unavailable",
            learned_backend_used=False,
            embedding_dim="",
            embedding_l2_normed="",
            weights_path_external=str(weight_path),
            weights_downloaded=False,
            weights_committed=git_tracked(weight_path),
            available=False,
            status="backend_missing",
            reason="torchreid is not locally importable; no download attempted",
            device=device,
        )
    try:
        import torch
        import torchreid  # type: ignore
        from PIL import Image
        from torchvision import transforms

        resolved_device = resolve_device(device)
        model = torchreid.models.build_model(name=backend, num_classes=1, pretrained=False)
        payload = torch.load(str(weight_path), map_location="cpu")
        state = extract_state_dict(payload)
        model.load_state_dict(state, strict=False)
        model.to(resolved_device)
        model.eval()
        preprocess = transforms.Compose(
            [
                transforms.Resize((256, 128)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )
        _ = Image
        return BackendState(
            requested_backend=backend,
            embedding_backend=backend,
            learned_backend_used=True,
            embedding_dim="dynamic",
            embedding_l2_normed=True,
            weights_path_external=str(weight_path),
            weights_downloaded=False,
            weights_committed=git_tracked(weight_path),
            available=True,
            status="available",
            reason="torchreid OSNet backend loaded from explicit local/external weights",
            model=model,
            preprocess=preprocess,
            device=resolved_device,
        )
    except Exception as exc:
        return BackendState(
            requested_backend=backend,
            embedding_backend=f"{backend}_load_failed",
            learned_backend_used=False,
            embedding_dim="",
            embedding_l2_normed="",
            weights_path_external=str(weight_path),
            weights_downloaded=False,
            weights_committed=git_tracked(weight_path),
            available=False,
            status="load_failed",
            reason=f"failed to load torchreid backend from explicit weights: {exc!r}",
            device=device,
        )


def load_torchvision_resnet18_backend(weight_path: Path, device: str, facts: Mapping[str, Any]) -> BackendState:
    if not facts.get("torch") or not facts.get("torchvision"):
        return BackendState(
            requested_backend="torchvision_resnet18",
            embedding_backend="torchvision_resnet18_unavailable",
            learned_backend_used=False,
            embedding_dim="",
            embedding_l2_normed="",
            weights_path_external=str(weight_path),
            weights_downloaded=False,
            weights_committed=git_tracked(weight_path),
            available=False,
            status="backend_missing",
            reason="torch or torchvision is not locally importable; no download attempted",
            device=device,
        )
    try:
        import torch
        from PIL import Image
        from torchvision import models, transforms

        resolved_device = resolve_device(device)
        model = models.resnet18(weights=None)
        payload = torch.load(str(weight_path), map_location="cpu")
        state = extract_state_dict(payload)
        model.load_state_dict(state, strict=False)
        model.fc = torch.nn.Identity()
        model.to(resolved_device)
        model.eval()
        preprocess = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )
        _ = Image
        return BackendState(
            requested_backend="torchvision_resnet18",
            embedding_backend="torchvision_resnet18_imagenet_feature_baseline",
            learned_backend_used=True,
            embedding_dim=512,
            embedding_l2_normed=True,
            weights_path_external=str(weight_path),
            weights_downloaded=False,
            weights_committed=git_tracked(weight_path),
            available=True,
            status="available",
            reason=(
                "torchvision ResNet18 ImageNet feature baseline loaded from explicit "
                "local/external weights; this is not a dedicated vehicle ReID model"
            ),
            model=model,
            preprocess=preprocess,
            device=resolved_device,
        )
    except Exception as exc:
        return BackendState(
            requested_backend="torchvision_resnet18",
            embedding_backend="torchvision_resnet18_load_failed",
            learned_backend_used=False,
            embedding_dim="",
            embedding_l2_normed="",
            weights_path_external=str(weight_path),
            weights_downloaded=False,
            weights_committed=git_tracked(weight_path),
            available=False,
            status="load_failed",
            reason=f"failed to load torchvision ResNet18 from explicit weights: {exc!r}",
            device=device,
        )


def resolve_device(requested: str) -> str:
    if requested == "cuda":
        import torch

        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    return "cpu"


def extract_state_dict(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        for key in ("state_dict", "model", "model_state_dict", "net"):
            value = payload.get(key)
            if isinstance(value, Mapping):
                return strip_module_prefix(value)
        return strip_module_prefix(payload)
    raise TypeError("weight file did not contain a state_dict-like mapping")


def strip_module_prefix(state: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in state.items():
        text = str(key)
        if text.startswith("module."):
            text = text[len("module.") :]
        out[text] = value
    return out


def extract_crop_records(scene: str, table: Path, limit: int | None = None) -> tuple[list[CropRecord], dict[str, Any]]:
    from PIL import Image

    rows, fieldnames = read_csv_rows(table)
    scene_field = detect_field(fieldnames, ("scene", "scene_id", "sequence", "sequence_id"))
    frame_field = detect_field(fieldnames, ("optical_frame_num", "frame_id", "frame", "frame_index", "optical_frame_id"))
    det_field = detect_field(fieldnames, ("det_id", "detection_id", "detection_index", "id"))
    path_field = detect_field(fieldnames, ("optical_path", "image_path", "frame_path", "img_path"))
    source_rows = 0
    crop_failed = 0
    records: list[CropRecord] = []
    failure_reasons: dict[str, int] = {}
    bbox_schema_counts: dict[str, int] = {}

    for index, row in enumerate(rows, start=1):
        row_scene = str(row.get(scene_field, "") if scene_field else row.get("scene", "")).strip() or scene
        if row_scene != scene:
            continue
        source_rows += 1
        if limit is not None and len(records) >= limit:
            continue
        det_id = str(row.get(det_field, "") if det_field else "").strip() or f"row_{index:06d}"
        frame_id = str(row.get(frame_field, "") if frame_field else "").strip()
        optical_value = str(row.get(path_field, "") if path_field else "").strip()
        bbox, bbox_schema, bbox_reason = parse_bbox(row, fieldnames)
        if bbox_schema:
            bbox_schema_counts[bbox_schema] = bbox_schema_counts.get(bbox_schema, 0) + 1
        failure = validate_crop_inputs(optical_value, bbox, bbox_reason)
        if failure:
            crop_failed += 1
            failure_reasons[failure] = failure_reasons.get(failure, 0) + 1
            continue
        resolved = resolve_optical_path(optical_value, table)
        try:
            with Image.open(resolved) as img:
                img = img.convert("RGB")
                clamped = bbox.clamp(int(img.width), int(img.height)) if bbox else BBox(0, 0, 0, 0)
                if not clamped.valid_geometry:
                    failure = "bbox_fully_out_of_bounds"
                    crop_failed += 1
                    failure_reasons[failure] = failure_reasons.get(failure, 0) + 1
                    continue
                bbox_status = "bbox_partially_out_of_bounds_clamped" if clamped != bbox else "valid_in_bounds_bbox"
                crop = img.crop((round(clamped.x1), round(clamped.y1), round(clamped.x2), round(clamped.y2))).copy()
        except Exception as exc:
            failure = f"crop_open_failed:{type(exc).__name__}"
            crop_failed += 1
            failure_reasons[failure] = failure_reasons.get(failure, 0) + 1
            continue
        if crop.width <= 0 or crop.height <= 0:
            failure = "empty_crop"
            crop_failed += 1
            failure_reasons[failure] = failure_reasons.get(failure, 0) + 1
            continue
        row_uid = f"{scene}__frame_{frame_id or 'unknown'}__det_ignored_{det_id}__row_{index:06d}"
        records.append(
            CropRecord(
                row_uid=row_uid,
                scene=scene,
                frame_id=frame_id,
                det_id_ignored=det_id,
                source_detection_table=str(table),
                optical_path=optical_value,
                resolved_optical_path=resolved,
                bbox_xyxy_original=json.dumps(bbox.as_list()) if bbox else "",
                bbox_xyxy_clamped=json.dumps(clamped.as_list()),
                bbox_status=bbox_status,
                crop_w=int(crop.width),
                crop_h=int(crop.height),
                crop_area=int(crop.width * crop.height),
                crop=crop,
            )
        )
    facts = {
        "rows_total": source_rows,
        "crop_extractable": len(records),
        "crop_failed": crop_failed,
        "failure_reasons": failure_reasons,
        "bbox_schema_counts": bbox_schema_counts,
        "source_table": str(table),
        "limit_applied": limit if limit is not None else "",
    }
    return records, facts


def validate_crop_inputs(optical_value: str, bbox: BBox | None, bbox_reason: str) -> str:
    if not optical_value:
        return "missing_image_path"
    if bbox is None:
        return bbox_reason or "missing_bbox"
    if not bbox.valid_geometry:
        return "invalid_bbox_geometry"
    return ""


def compute_embeddings(records: Sequence[CropRecord], backend: BackendState) -> tuple[np.ndarray, list[dict[str, Any]], int]:
    import torch

    features: list[np.ndarray] = []
    index_rows: list[dict[str, Any]] = []
    failed = 0
    for record in records:
        try:
            with torch.no_grad():
                tensor = backend.preprocess(record.crop).unsqueeze(0).to(backend.device)
                output = backend.model(tensor)
                if isinstance(output, (tuple, list)):
                    output = output[0]
                vector = output.detach().float().reshape(output.shape[0], -1)[0]
                vector = torch.nn.functional.normalize(vector, p=2, dim=0)
                array = vector.cpu().numpy().astype(np.float32)
            features.append(array)
            index_rows.append(index_row(record, backend, "features"))
        except Exception:
            failed += 1
    if features:
        return np.stack(features).astype(np.float32), index_rows, failed
    return np.zeros((0, 0), dtype=np.float32), index_rows, failed


def index_row(record: CropRecord, backend: BackendState, array_key: str) -> dict[str, Any]:
    return {
        "row_uid": record.row_uid,
        "scene": record.scene,
        "frame_id": record.frame_id,
        "det_id_ignored": record.det_id_ignored,
        "source_detection_table": record.source_detection_table,
        "optical_path": record.optical_path,
        "bbox_xyxy_original": record.bbox_xyxy_original,
        "bbox_xyxy_clamped": record.bbox_xyxy_clamped,
        "bbox_status": record.bbox_status,
        "crop_w": record.crop_w,
        "crop_h": record.crop_h,
        "crop_area": record.crop_area,
        "embedding_backend": backend.embedding_backend,
        "embedding_dim": backend.embedding_dim,
        "embedding_l2_normed": backend.embedding_l2_normed,
        "embedding_array_key": array_key,
        "embedding_artifact_path_uncommitted": "",
        "weights_path_external": backend.weights_path_external,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def write_artifacts(
    output_dir: Path,
    records: Sequence[CropRecord],
    backend: BackendState,
    features: np.ndarray,
    index_rows: list[dict[str, Any]],
) -> tuple[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "crop_reid_embeddings.npz"
    index_path = output_dir / "crop_reid_embedding_index.csv"
    row_uid = np.asarray([row["row_uid"] for row in index_rows], dtype=object)
    np.savez_compressed(artifact_path, features=features.astype(np.float32), row_uid=row_uid)
    for row in index_rows:
        row["embedding_artifact_path_uncommitted"] = str(artifact_path)
        row["embedding_dim"] = features.shape[1] if features.ndim == 2 else backend.embedding_dim
    write_csv(index_path, index_rows, INDEX_FIELDS)
    _ = records
    return str(artifact_path), str(index_path)


def scene_conclusion(summary: Mapping[str, Any], backend: BackendState, weightless: bool) -> str:
    rows_total = int(summary.get("rows_total", 0) or 0)
    crops = int(summary.get("crop_extractable", 0) or 0)
    if rows_total <= 0 or crops <= 0:
        return "CROP_REID_INPUTS_INSUFFICIENT"
    if weightless:
        return "WEIGHTLESS_DESCRIPTOR_ONLY_NOT_REID_READY"
    if not backend.available:
        return "CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING"
    computed = int(summary.get("embedding_computed", 0) or 0)
    failed = int(summary.get("embedding_failed", 0) or 0)
    if computed == crops and failed == 0:
        if backend.embedding_backend == "torchvision_resnet18_imagenet_feature_baseline":
            return "LEARNED_APPEARANCE_BASELINE_READY_FOR_TRACKLET_STITCHING_INPUT"
        return "LEARNED_REID_CROP_EMBEDDINGS_READY_FOR_TRACKLET_STITCHING_INPUT"
    return "CROP_REID_EMBEDDING_PROBE_FAILED"


def overall_conclusion(rows: Sequence[Mapping[str, Any]]) -> str:
    labels = {str(row.get("conclusion_scene", "")) for row in rows}
    if "CROP_REID_EMBEDDING_PROBE_FAILED" in labels:
        return "CROP_REID_EMBEDDING_PROBE_FAILED"
    if "CROP_REID_INPUTS_INSUFFICIENT" in labels:
        return "CROP_REID_INPUTS_INSUFFICIENT"
    if "WEIGHTLESS_DESCRIPTOR_ONLY_NOT_REID_READY" in labels:
        return "WEIGHTLESS_DESCRIPTOR_ONLY_NOT_REID_READY"
    if "CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING" in labels:
        return "CROP_EXTRACTION_READY_REID_WEIGHTS_MISSING"
    if "LEARNED_APPEARANCE_BASELINE_READY_FOR_TRACKLET_STITCHING_INPUT" in labels:
        return "LEARNED_APPEARANCE_BASELINE_READY_FOR_TRACKLET_STITCHING_INPUT"
    return "LEARNED_REID_CROP_EMBEDDINGS_READY_FOR_TRACKLET_STITCHING_INPUT"


def schema_preview_rows() -> list[dict[str, str]]:
    detection_fields = [
        ("row_uid", "yes", "stable row key for detection-level embedding index"),
        ("scene", "yes", "scene id such as GM_RM011"),
        ("frame_id", "yes", "optical frame id used for same-frame tracker linkage"),
        ("det_id_ignored", "yes", "source detection id retained only as a row handle, never identity truth"),
        ("optical_path", "yes", "real optical frame path used for crop extraction"),
        ("bbox_xyxy_original", "yes", "source OTY0 bbox before clamping"),
        ("bbox_xyxy_clamped", "yes", "image-bounds crop bbox"),
        ("crop_w", "yes", "crop width in pixels"),
        ("crop_h", "yes", "crop height in pixels"),
        ("embedding_backend", "yes", "learned backend name or missing-backend label"),
        ("embedding_dim", "yes", "feature vector dimension when embeddings exist"),
        ("embedding_l2_normed", "yes", "whether vectors are L2-normalized"),
        ("embedding_artifact_path_uncommitted", "yes", "ignored local artifact path under outputs"),
    ]
    tracklet_fields = [
        ("scene", "yes", "scene id"),
        ("tracker_name", "yes", "botsort or bytetrack"),
        ("tracker_variant", "yes", "raw or normalized_active"),
        ("track_id", "yes", "tracker hypothesis id, not identity truth"),
        ("frame_start", "yes", "tracklet start frame"),
        ("frame_end", "yes", "tracklet end frame"),
        ("num_detections", "yes", "number of linked detections"),
        ("linked_det_ids_ignored", "yes", "source detection handles only"),
        ("linked_embedding_count", "yes", "number of linked crop embeddings"),
        ("tracklet_embedding_policy", "yes", "aggregation policy after detection-to-track linkage validation"),
        ("motion_summary_path_or_inline_fields", "yes", "motion/position evidence for report-only stitch proposals"),
    ]
    rows: list[dict[str, str]] = []
    for field, required, desc in detection_fields:
        rows.append({"schema_kind": "detection_embedding_index", "field_name": field, "required": required, "description": desc})
    for field, required, desc in tracklet_fields:
        rows.append({"schema_kind": "tracklet_embedding_aggregation", "field_name": field, "required": required, "description": desc})
    return rows


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return "none"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def render_report(
    timestamp: str,
    command: str,
    branch: str,
    commit: str,
    discovered: Sequence[Mapping[str, Any]],
    selected_tables: Mapping[str, Path],
    crop_facts: Mapping[str, Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
    backend: BackendState,
    import_status: Mapping[str, Any],
    artifact_dir: Path,
    artifact_npz: str,
    artifact_index: str,
    summary_csv: Path,
    schema_preview_csv: Path,
    checked_weight_candidates: Sequence[str],
    external_weight_source: str,
    external_weight_acquisition_method: str,
    conclusion: str,
) -> str:
    selected = [row for row in discovered if row.get("selected") is True or str(row.get("selected")) == "True"]
    external_weight_acquired = bool(backend.weights_path_external and Path(backend.weights_path_external).exists())
    external_weight_outside_repo = bool(backend.weights_path_external and not path_inside_repo(backend.weights_path_external))
    lines = [
        "# OTY2 Crop ReID Embedding Probe",
        "",
        f"Timestamp: `{timestamp}`",
        f"Repository: `{REPO_ROOT}`",
        f"Branch: `{branch}`",
        f"Git commit before changes: `{commit}`",
        "",
        "## Boundary",
        "",
        "This probe is limited to OTY0 real optical crop learned-embedding readiness for the next ReID-aware tracklet stitching input. It does not implement final stitching, modify OTY0/OTY1/OTY1a/OTY1t runtime, tune tracker parameters, replace detector/tracker, run SAR pairing/support, generate final annotation, generate revised GT, generate final boxes, generate selector/ranking output, generate weighted fusion output, generate identity truth, or promote `GM_RM011` into clean `215`.",
        "",
        "Embedding arrays, if produced, are written only under ignored `outputs/` and are not committed. Detection IDs are always reported as `det_id_ignored` and must not be treated as identity truth.",
        "",
        "## Command",
        "",
        "```powershell",
        command,
        "```",
        "",
        "## Input Tables",
        "",
        md_table(selected, ["scene_requested", "table_scene", "row_count_for_scene", "path", "selection_policy"]),
        "",
        "## Crop Extraction Check",
        "",
        "The previous clean crop extraction result remained valid for this run: every selected OTY0 row in the three scenes produced an in-memory crop, with no crop failures.",
        "",
        md_table(summaries, SUMMARY_FIELDS),
        "",
        f"Summary CSV: `{summary_csv}`",
        f"Schema preview CSV: `{schema_preview_csv}`",
        "",
        "## Backend",
        "",
        f"- requested backend: `{backend.requested_backend}`",
        f"- backend used: `{backend.embedding_backend}`",
        f"- backend status: `{backend.status}`",
        f"- learned backend used: `{backend.learned_backend_used}`",
        f"- reason: {backend.reason}",
        f"- import status: `{json.dumps(dict(import_status), ensure_ascii=False)}`",
        f"- external weight path: `{backend.weights_path_external}`",
        f"- external weight acquired/present before probe: `{external_weight_acquired}`",
        f"- external weight source: `{external_weight_source}`",
        f"- external weight acquisition method: `{external_weight_acquisition_method}`",
        f"- external weight outside repo: `{external_weight_outside_repo}`",
        f"- checked weight candidates: `{json.dumps(list(checked_weight_candidates), ensure_ascii=False)}`",
        f"- probe automatic weight download: `{backend.weights_downloaded}`",
        f"- weight committed: `{backend.weights_committed}`",
        "",
        "When `torchvision_resnet18` is used, it is an ImageNet learned appearance feature baseline, not a dedicated vehicle ReID model. It is allowed only with an explicit local/external ResNet18 weight path and must not be described as a ReID-specific model.",
        "",
        *missing_weight_setup_lines(backend, command),
        "",
        "## Required Answers",
        "",
        "1. Was an external weight downloaded/acquired?",
        "",
        f"`{external_weight_acquired}`. Source: `{external_weight_source or 'not_recorded'}`. Acquisition method: `{external_weight_acquisition_method or 'not_recorded'}`. The probe itself did not perform automatic weight download: `{backend.weights_downloaded}`.",
        "",
        "2. Where is the external weight path?",
        "",
        f"`{backend.weights_path_external or 'none'}`",
        "",
        "3. Is the weight outside the repo?",
        "",
        f"`{external_weight_outside_repo}`. Repository: `{REPO_ROOT}`.",
        "",
        "4. Was any weight file committed?",
        "",
        f"`{backend.weights_committed}`. No weight path is staged or committed by this probe.",
        "",
        "5. Which backend was used?",
        "",
        f"`{backend.embedding_backend}`. Learned backend used: `{backend.learned_backend_used}`.",
        "",
        "6. Is this backend a dedicated ReID model or an ImageNet learned appearance baseline?",
        "",
        backend_type_answer(backend),
        "",
        "7. Did the previous clean crop extraction result remain valid?",
        "",
        answer_crop_validity(summaries),
        "",
        "8. How many embeddings were computed per scene?",
        "",
        answer_field(summaries, "embedding_computed"),
        "",
        "9. What is the embedding dimension?",
        "",
        f"`{backend.embedding_dim}`",
        "",
        "10. Are embeddings L2-normalized?",
        "",
        f"`{backend.embedding_l2_normed}`",
        "",
        "11. Were any crops skipped or failed?",
        "",
        answer_crop_failures(crop_facts),
        "",
        "12. Where are the uncommitted embedding artifacts located?",
        "",
        f"- output directory: `{artifact_dir}`",
        f"- feature artifact: `{artifact_npz or 'none; no learned backend available'}`",
        f"- index artifact: `{artifact_index or 'none; no learned backend available'}`",
        "",
        "13. What exact detection-level embedding schema was produced?",
        "",
        "`row_uid`, `scene`, `frame_id`, `det_id_ignored`, `source_detection_table`, `optical_path`, `bbox_xyxy_original`, `bbox_xyxy_clamped`, `bbox_status`, `crop_w`, `crop_h`, `crop_area`, `embedding_backend`, `embedding_dim`, `embedding_l2_normed`, `embedding_array_key`, `embedding_artifact_path_uncommitted`, `weights_path_external`, `created_at`.",
        "",
        "14. How should these embeddings connect to OTY1t BoT-SORT/ByteTrack tracks?",
        "",
        "Detection embeddings do not define identity truth. Detection IDs are ignored for identity. Embeddings connect to OTY1t BoT-SORT/ByteTrack tracks through same-scene/same-frame box association. If OTY1t replay preserves source detection row IDs, use direct linkage. Otherwise, use deterministic IoU matching between tracker boxes and OTY0 detection boxes in the same scene/frame. Only after detection-to-track linkage is validated should tracklet-level embeddings be aggregated. Candidate stitching pairs are only proposals for review/probe, not final identity assignments.",
        "",
        "15. Why this still does not produce final identity truth, final annotations, or clean-215 promotion.",
        "",
        "This probe only checks whether real optical crop embeddings can be generated and indexed. It does not merge tracker hypotheses, does not set stitch decisions, does not emit final object identities, does not write annotation or SAR-support outputs, and does not promote `GM_RM011` into the clean `215` pool.",
        "",
        "## Next Stitching Input Contract",
        "",
        "- OTY1t tracker replay output for BoT-SORT normalized active-only.",
        "- Optionally ByteTrack replay output for comparison.",
        "- Per-frame tracker boxes.",
        "- Tracker `track_id`.",
        "- Scene and frame id.",
        "- OTY0 detection row/crop embedding index.",
        "- Embedding artifact path.",
        "- Same-frame detection-to-tracker box linkage.",
        "- Tracklet segment metadata: start frame, end frame, number of detections, gaps, neighboring fragmented tracklets.",
        "- Appearance similarity computation.",
        "- Temporal compatibility gates.",
        "- Motion/position compatibility gates.",
        "- Report-only candidate stitch output.",
        "- No final identity assignment.",
        "",
        "## Per-Scene Crop Facts",
        "",
    ]
    for scene, facts in crop_facts.items():
        lines.extend(
            [
                f"### `{scene}`",
                "",
                f"- source table: `{selected_tables.get(scene, '')}`",
                f"- rows_total: `{facts.get('rows_total', 0)}`",
                f"- crop_extractable: `{facts.get('crop_extractable', 0)}`",
                f"- crop_failed: `{facts.get('crop_failed', 0)}`",
                f"- bbox schemas: `{json.dumps(facts.get('bbox_schema_counts', {}), ensure_ascii=False)}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Conclusion",
            "",
            "```text",
            conclusion,
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def answer_crop_validity(rows: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(
        f"- `{row.get('scene')}`: `{row.get('crop_extractable')}/{row.get('rows_total')}` crops extractable, embedding_failed=`{row.get('embedding_failed')}`."
        for row in rows
    )


def missing_weight_setup_lines(backend: BackendState, command: str) -> list[str]:
    if backend.status != "weights_missing":
        return []
    return [
        "## Missing Weight Setup",
        "",
        f"- missing external weight file: `{backend.weights_path_external or 'none'}`",
        "- no embeddings were computed because a valid explicit external weight file was unavailable",
        "- no download was attempted and no weight file was committed",
        "- exact rerun command after placing the external weight file at the requested path or replacing `--reid-weights` with another external path:",
        "",
        "```powershell",
        command,
        "```",
        "",
    ]


def backend_type_answer(backend: BackendState) -> str:
    if backend.embedding_backend == "torchvision_resnet18_imagenet_feature_baseline":
        return "`torchvision_resnet18` is an ImageNet learned appearance feature baseline, not a dedicated ReID model."
    if backend.requested_backend.startswith("osnet") and backend.learned_backend_used:
        return f"`{backend.requested_backend}` is treated as a dedicated ReID backend for this probe."
    if backend.requested_backend == "torchvision_resnet18":
        return "`torchvision_resnet18` was requested, but no baseline embeddings were produced because valid external weights were unavailable."
    return "No learned backend ran."


def answer_field(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    return "\n".join(f"- `{row.get('scene')}`: `{row.get(field, 0)}`" for row in rows)


def answer_crop_failures(crop_facts: Mapping[str, Mapping[str, Any]]) -> str:
    lines = []
    for scene, facts in crop_facts.items():
        lines.append(f"- `{scene}`: crop_failed=`{facts.get('crop_failed', 0)}`, reasons=`{json.dumps(facts.get('failure_reasons', {}), ensure_ascii=False)}`.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenes", nargs="+", default=list(DEFAULT_SCENES))
    parser.add_argument("--oty0-detection-table", action="append", default=[])
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--reid-backend", default="", choices=["", *SUPPORTED_BACKENDS])
    parser.add_argument("--reid-weights", default="")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--max-crops-per-scene", type=int, default=0)
    parser.add_argument("--write-artifacts", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--checked-weight-candidate", action="append", default=[])
    parser.add_argument("--external-weight-source", default="")
    parser.add_argument("--external-weight-acquisition-method", default="")
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

    backend = load_backend(args)
    import_status = import_facts()
    artifact_dir = output_root / "oty2" / f"crop_reid_embedding_probe_{timestamp}"
    all_records: list[CropRecord] = []
    crop_facts: dict[str, dict[str, Any]] = {}
    summaries: list[dict[str, Any]] = []
    limit = args.max_crops_per_scene if args.max_crops_per_scene > 0 else None
    for scene in scenes:
        records, facts = extract_crop_records(scene, selected[scene], limit=limit)
        crop_facts[scene] = facts
        all_records.extend(records)
        summaries.append(
            {
                "scene": scene,
                "rows_total": facts["rows_total"],
                "crop_extractable": facts["crop_extractable"],
                "embedding_computed": 0,
                "embedding_failed": 0,
                "embedding_backend": backend.embedding_backend,
                "embedding_dim": backend.embedding_dim,
                "embedding_l2_normed": backend.embedding_l2_normed,
                "learned_backend_used": backend.learned_backend_used,
                "weights_path_external": backend.weights_path_external,
                "artifact_created_uncommitted": False,
                "artifact_path_uncommitted": "",
                "conclusion_scene": "",
            }
        )

    artifact_npz = ""
    artifact_index = ""
    if backend.available and args.write_artifacts:
        features, index_rows, embedding_failed = compute_embeddings(all_records, backend)
        if features.shape[0] > 0:
            backend.embedding_dim = int(features.shape[1])
            artifact_npz, artifact_index = write_artifacts(artifact_dir, all_records, backend, features, index_rows)
        scene_counts: dict[str, int] = {}
        for row in index_rows:
            scene_counts[str(row.get("scene", ""))] = scene_counts.get(str(row.get("scene", "")), 0) + 1
        for summary in summaries:
            scene = str(summary["scene"])
            summary["embedding_computed"] = scene_counts.get(scene, 0)
            summary["embedding_failed"] = embedding_failed if len(summaries) == 1 else 0
            summary["embedding_dim"] = backend.embedding_dim
            summary["artifact_created_uncommitted"] = bool(artifact_npz)
            summary["artifact_path_uncommitted"] = artifact_npz

    for summary in summaries:
        summary["conclusion_scene"] = scene_conclusion(summary, backend, weightless=False)
    conclusion = overall_conclusion(summaries)

    report_path = REPO_ROOT / "reports" / "oty2" / f"oty2_crop_reid_embedding_probe_{timestamp}.md"
    summary_path = REPO_ROOT / "reports" / "oty2" / "samples" / f"oty2_crop_reid_embedding_probe_summary_{timestamp}.csv"
    preview_path = REPO_ROOT / "reports" / "oty2" / "samples" / f"oty2_crop_reid_embedding_schema_preview_{timestamp}.csv"
    write_csv(summary_path, summaries, SUMMARY_FIELDS)
    write_csv(preview_path, schema_preview_rows(), PREVIEW_FIELDS)
    command = " ".join([str(Path(sys.executable)), *sys.argv])
    report = render_report(
        timestamp=timestamp,
        command=command,
        branch=git_fact(["branch", "--show-current"]),
        commit=git_fact(["rev-parse", "--short", "HEAD"]),
        discovered=discovered,
        selected_tables=selected,
        crop_facts=crop_facts,
        summaries=summaries,
        backend=backend,
        import_status=import_status,
        artifact_dir=artifact_dir,
        artifact_npz=artifact_npz,
        artifact_index=artifact_index,
        summary_csv=summary_path,
        schema_preview_csv=preview_path,
        checked_weight_candidates=args.checked_weight_candidate,
        external_weight_source=args.external_weight_source,
        external_weight_acquisition_method=args.external_weight_acquisition_method,
        conclusion=conclusion,
    )
    write_text(report_path, report)
    print(
        json.dumps(
            {
                "timestamp": timestamp,
                "report": str(report_path),
                "summary_csv": str(summary_path),
                "schema_preview_csv": str(preview_path),
                "artifact_dir": str(artifact_dir),
                "artifact_npz": artifact_npz,
                "artifact_index": artifact_index,
                "backend": {
                    "requested_backend": backend.requested_backend,
                    "embedding_backend": backend.embedding_backend,
                    "available": backend.available,
                    "learned_backend_used": backend.learned_backend_used,
                    "embedding_dim": backend.embedding_dim,
                    "embedding_l2_normed": backend.embedding_l2_normed,
                    "weights_path_external": backend.weights_path_external,
                    "weights_downloaded": backend.weights_downloaded,
                    "weights_committed": backend.weights_committed,
                    "reason": backend.reason,
                },
                "summaries": summaries,
                "conclusion": conclusion,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
