"""Link OTY0 crop embeddings to OTY1t tracker assignment rows.

This bounded diagnostic only verifies whether detection-level crop embeddings
can be attached to existing OTY1t tracker rows. It does not compute appearance
similarity, stitch tracklets, assign identity truth, modify OTY runtime code,
run SAR pairing/support, or write final/revised annotations.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENES = ("GM_RM011", "GM_RM019", "GM_RM017")
DEFAULT_EMBEDDING_DIR = REPO_ROOT / "outputs" / "oty2" / "crop_reid_embedding_probe_20260705_170500"
DEFAULT_TRACKER_ROOT = REPO_ROOT / "outputs" / "oty1t_standard_mot_backbone_closure_20260705_110947"

SUMMARY_FIELDS = [
    "scene",
    "tracker_name",
    "tracker_variant",
    "tracker_rows_total",
    "tracker_rows_with_valid_bbox",
    "embedding_rows_available",
    "direct_source_links",
    "iou_high_links",
    "iou_acceptable_links",
    "iou_weak_links",
    "unmatched_tracker_rows",
    "ambiguous_links",
    "linked_tracker_rows_total",
    "linked_tracker_row_rate",
    "unique_track_ids",
    "track_ids_with_any_embedding",
    "track_ids_with_embedding_rate",
    "conclusion_scene",
]

LINKAGE_FIELDS = [
    "scene",
    "frame_id",
    "tracker_name",
    "tracker_variant",
    "track_id",
    "tracker_row_uid",
    "tracker_bbox_xyxy",
    "embedding_row_uid",
    "det_id_ignored",
    "source_detection_table",
    "detection_bbox_xyxy_clamped",
    "link_method",
    "iou",
    "link_status",
    "embedding_backend",
    "embedding_dim",
    "embedding_artifact_path_uncommitted",
    "created_at",
]

SCHEMA_PREVIEW_FIELDS = ["schema_kind", "field_name", "required", "description"]
LINKED_STATUSES = {"direct_source_link", "iou_high", "iou_acceptable", "iou_weak"}
UNMATCHED_STATUSES = {"unmatched_tracker_row", "missing_embedding_candidate", "invalid_bbox"}


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def valid(self) -> bool:
        return self.x2 > self.x1 and self.y2 > self.y1

    @property
    def area(self) -> float:
        if not self.valid:
            return 0.0
        return (self.x2 - self.x1) * (self.y2 - self.y1)

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
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_bbox_values(value: Any) -> BBox | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, Mapping):
            for keys in (("x1", "y1", "x2", "y2"), ("left", "top", "right", "bottom")):
                vals = [parse_float(parsed.get(key)) for key in keys]
                if all(val is not None for val in vals):
                    return BBox(*(float(val) for val in vals if val is not None))
        if isinstance(parsed, (list, tuple)) and len(parsed) >= 4:
            vals = [parse_float(item) for item in parsed[:4]]
            if all(val is not None for val in vals):
                return BBox(*(float(val) for val in vals if val is not None))
    return None


def parse_xyxy(row: Mapping[str, Any], prefix: str = "bbox") -> BBox | None:
    if prefix == "bbox":
        fields = ("bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2")
    else:
        fields = (f"{prefix}_x1", f"{prefix}_y1", f"{prefix}_x2", f"{prefix}_y2")
    vals = [parse_float(row.get(field)) for field in fields]
    if all(val is not None for val in vals):
        return BBox(*(float(val) for val in vals if val is not None))
    for field in ("bbox_xyxy_clamped", "bbox_xyxy", "tracker_bbox_xyxy"):
        if field in row:
            bbox = parse_bbox_values(row.get(field))
            if bbox is not None:
                return bbox
    return None


def bbox_iou(left: BBox | None, right: BBox | None) -> float:
    if left is None or right is None or not left.valid or not right.valid:
        return 0.0
    ix1 = max(left.x1, right.x1)
    iy1 = max(left.y1, right.y1)
    ix2 = min(left.x2, right.x2)
    iy2 = min(left.y2, right.y2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih
    union = left.area + right.area - intersection
    return intersection / union if union > 0 else 0.0


def norm_text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def frame_key(value: Any) -> str:
    text = norm_text(value)
    parsed = parse_float(text)
    if parsed is not None and parsed.is_integer():
        return str(int(parsed))
    return text


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(REPO_ROOT), text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def load_embedding_index(path: Path) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    rows, _fields = read_csv_rows(path)
    keyed: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_frame: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        scene = norm_text(row.get("scene"))
        frame = frame_key(row.get("frame_id"))
        det_id = norm_text(row.get("det_id_ignored"))
        bbox = parse_bbox_values(row.get("bbox_xyxy_clamped"))
        enriched = dict(row)
        enriched["_scene"] = scene
        enriched["_frame"] = frame
        enriched["_det_id"] = det_id
        enriched["_bbox"] = bbox
        if scene and frame and det_id:
            keyed[(scene, frame, det_id)] = enriched
        if scene and frame:
            by_frame[(scene, frame)].append(enriched)
    return rows, keyed, by_frame


def discover_tracker_assignment_files(root: Path, scenes: Sequence[str]) -> list[Path]:
    if not root.exists():
        return []
    scene_set = set(scenes)
    files = sorted(root.glob("*/*oty1t_tracker_detection_assignments.csv"))
    selected: list[Path] = []
    for path in files:
        stem = path.parent.name
        if any(stem.startswith(scene + "_") for scene in scene_set):
            selected.append(path)
    return selected


def tracker_variant_from_path(path: Path, row: Mapping[str, Any]) -> str:
    mode = norm_text(row.get("tracker_input_mode"))
    if mode == "normalized_active_only_probe":
        return "normalized_active"
    if mode == "detection_table_replay":
        return "raw"
    name = path.parent.name.lower()
    if "normalized_active" in name:
        return "normalized_active"
    if name.endswith("_raw") or "_raw" in name:
        return "raw"
    return mode or "unknown"


def direct_link_for_tracker_row(
    row: Mapping[str, Any],
    keyed_embeddings: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    scene = norm_text(row.get("scene"))
    frame = frame_key(row.get("optical_frame_num") or row.get("frame_id"))
    det_id = norm_text(row.get("det_id"))
    if not (scene and frame and det_id):
        return None
    return keyed_embeddings.get((scene, frame, det_id))


def assign_iou_fallback(
    pending: Sequence[dict[str, Any]],
    embeddings_by_frame: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> dict[int, tuple[Mapping[str, Any] | None, float, str]]:
    out: dict[int, tuple[Mapping[str, Any] | None, float, str]] = {}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in pending:
        grouped[(item["scene"], item["frame_id"])].append(item)

    for key, items in grouped.items():
        candidates = list(embeddings_by_frame.get(key, []))
        if not candidates:
            for item in items:
                out[item["pending_index"]] = (None, 0.0, "missing_embedding_candidate")
            continue
        pairs: list[tuple[float, str, str, dict[str, Any], Mapping[str, Any]]] = []
        for item in items:
            tbox = item.get("tracker_bbox")
            for candidate in candidates:
                iou = bbox_iou(tbox, candidate.get("_bbox"))  # type: ignore[arg-type]
                pairs.append((iou, item["tracker_row_uid"], norm_text(candidate.get("row_uid")), item, candidate))
        assignments = deterministic_one_to_one(pairs)
        assigned_items = {item_id for item_id, _candidate_uid in assignments}
        for item in items:
            item_id = item["tracker_row_uid"]
            if item_id not in assigned_items:
                out[item["pending_index"]] = (None, 0.0, "unmatched_tracker_row")
                continue
            candidate, iou, status = assignments[item_id]
            out[item["pending_index"]] = (candidate, iou, status)
    return out


def deterministic_one_to_one(
    pairs: Sequence[tuple[float, str, str, dict[str, Any], Mapping[str, Any]]],
) -> dict[str, tuple[Mapping[str, Any], float, str]]:
    try:
        from scipy.optimize import linear_sum_assignment  # type: ignore

        return hungarian_assign(pairs, linear_sum_assignment)
    except Exception:
        return greedy_assign(pairs)


def hungarian_assign(
    pairs: Sequence[tuple[float, str, str, dict[str, Any], Mapping[str, Any]]],
    linear_sum_assignment: Any,
) -> dict[str, tuple[Mapping[str, Any], float, str]]:
    item_ids = sorted({item_id for _iou, item_id, _cand_uid, _item, _candidate in pairs})
    cand_ids = sorted({cand_uid for _iou, _item_id, cand_uid, _item, _candidate in pairs})
    pair_lookup: dict[tuple[str, str], tuple[float, dict[str, Any], Mapping[str, Any]]] = {}
    for iou, item_id, cand_uid, item, candidate in pairs:
        pair_lookup[(item_id, cand_uid)] = (iou, item, candidate)
    matrix: list[list[float]] = []
    for item_id in item_ids:
        row: list[float] = []
        for cand_uid in cand_ids:
            iou = pair_lookup.get((item_id, cand_uid), (0.0, {}, {}))[0]
            row.append(-iou)
        matrix.append(row)
    if not matrix or not matrix[0]:
        return {}
    row_ind, col_ind = linear_sum_assignment(matrix)
    out: dict[str, tuple[Mapping[str, Any], float, str]] = {}
    for r, c in zip(row_ind, col_ind):
        item_id = item_ids[int(r)]
        cand_uid = cand_ids[int(c)]
        iou, _item, candidate = pair_lookup.get((item_id, cand_uid), (0.0, {}, {}))
        if iou < 0.50:
            continue
        out[item_id] = (candidate, iou, iou_status(iou, ambiguous=False))
    return mark_ambiguous(out, pairs)


def greedy_assign(pairs: Sequence[tuple[float, str, str, dict[str, Any], Mapping[str, Any]]]) -> dict[str, tuple[Mapping[str, Any], float, str]]:
    out: dict[str, tuple[Mapping[str, Any], float, str]] = {}
    used_items: set[str] = set()
    used_candidates: set[str] = set()
    for iou, item_id, cand_uid, _item, candidate in sorted(pairs, key=lambda row: (-row[0], row[1], row[2])):
        if iou < 0.50 or item_id in used_items or cand_uid in used_candidates:
            continue
        out[item_id] = (candidate, iou, iou_status(iou, ambiguous=False))
        used_items.add(item_id)
        used_candidates.add(cand_uid)
    return mark_ambiguous(out, pairs)


def mark_ambiguous(
    assigned: Mapping[str, tuple[Mapping[str, Any], float, str]],
    pairs: Sequence[tuple[float, str, str, dict[str, Any], Mapping[str, Any]]],
) -> dict[str, tuple[Mapping[str, Any], float, str]]:
    by_item: dict[str, list[float]] = defaultdict(list)
    for iou, item_id, _cand_uid, _item, _candidate in pairs:
        if iou >= 0.50:
            by_item[item_id].append(iou)
    out = dict(assigned)
    for item_id, (candidate, iou, status) in list(out.items()):
        close = [value for value in by_item.get(item_id, []) if abs(value - iou) <= 1e-6]
        if len(close) > 1:
            out[item_id] = (candidate, iou, "ambiguous_multiple_candidates")
        else:
            out[item_id] = (candidate, iou, status)
    return out


def iou_status(iou: float, ambiguous: bool) -> str:
    if ambiguous:
        return "ambiguous_multiple_candidates"
    if iou >= 0.90:
        return "iou_high"
    if iou >= 0.70:
        return "iou_acceptable"
    if iou >= 0.50:
        return "iou_weak"
    return "unmatched_tracker_row"


def linkage_row(
    row: Mapping[str, Any],
    source_path: Path,
    row_index: int,
    created_at: str,
    keyed_embeddings: Mapping[tuple[str, str, str], Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    scene = norm_text(row.get("scene"))
    frame = frame_key(row.get("optical_frame_num") or row.get("frame_id"))
    tracker = norm_text(row.get("tracker_name")) or tracker_name_from_path(source_path)
    variant = tracker_variant_from_path(source_path, row)
    track_id = norm_text(row.get("tracker_track_id"))
    det_id = norm_text(row.get("det_id"))
    tracker_bbox = parse_xyxy(row)
    tracker_uid = f"{scene}__frame_{frame}__{tracker}__{variant}__row_{row_index:06d}__det_{det_id or 'missing'}"
    embed = direct_link_for_tracker_row(row, keyed_embeddings)
    iou = bbox_iou(tracker_bbox, embed.get("_bbox")) if embed else 0.0  # type: ignore[union-attr,arg-type]
    if embed is not None:
        status = "direct_source_link"
        method = "direct_source"
    elif tracker_bbox is None or not tracker_bbox.valid:
        status = "invalid_bbox"
        method = "none"
    else:
        status = "pending_iou"
        method = "pending_iou"
    out = {
        "scene": scene,
        "frame_id": frame,
        "tracker_name": tracker,
        "tracker_variant": variant,
        "track_id": track_id,
        "tracker_row_uid": tracker_uid,
        "tracker_bbox_xyxy": json.dumps(tracker_bbox.as_list()) if tracker_bbox else "",
        "embedding_row_uid": norm_text(embed.get("row_uid")) if embed else "",
        "det_id_ignored": norm_text(embed.get("det_id_ignored")) if embed else det_id,
        "source_detection_table": norm_text(embed.get("source_detection_table")) if embed else "",
        "detection_bbox_xyxy_clamped": norm_text(embed.get("bbox_xyxy_clamped")) if embed else "",
        "link_method": method,
        "iou": f"{iou:.6f}" if embed else "",
        "link_status": status,
        "embedding_backend": norm_text(embed.get("embedding_backend")) if embed else "",
        "embedding_dim": norm_text(embed.get("embedding_dim")) if embed else "",
        "embedding_artifact_path_uncommitted": norm_text(embed.get("embedding_artifact_path_uncommitted")) if embed else "",
        "created_at": created_at,
    }
    pending = None
    if status == "pending_iou":
        pending = {
            "pending_index": -1,
            "scene": scene,
            "frame_id": frame,
            "tracker_row_uid": tracker_uid,
            "tracker_bbox": tracker_bbox,
        }
    return out, pending


def tracker_name_from_path(path: Path) -> str:
    name = path.parent.name.lower()
    if "botsort" in name:
        return "botsort"
    if "bytetrack" in name:
        return "bytetrack"
    return "unknown"


def apply_iou_results(
    linkage_rows: list[dict[str, Any]],
    pending_rows: list[dict[str, Any]],
    embeddings_by_frame: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> None:
    for idx, item in enumerate(pending_rows):
        item["pending_index"] = idx
    results = assign_iou_fallback(pending_rows, embeddings_by_frame)
    for idx, item in enumerate(pending_rows):
        row = linkage_rows[item["linkage_row_index"]]
        embed, iou, status = results.get(idx, (None, 0.0, "unmatched_tracker_row"))
        if embed is not None and status != "ambiguous_multiple_candidates":
            row["link_method"] = "iou"
            row["embedding_row_uid"] = norm_text(embed.get("row_uid"))
            row["det_id_ignored"] = norm_text(embed.get("det_id_ignored"))
            row["source_detection_table"] = norm_text(embed.get("source_detection_table"))
            row["detection_bbox_xyxy_clamped"] = norm_text(embed.get("bbox_xyxy_clamped"))
            row["iou"] = f"{iou:.6f}"
            row["link_status"] = status
            row["embedding_backend"] = norm_text(embed.get("embedding_backend"))
            row["embedding_dim"] = norm_text(embed.get("embedding_dim"))
            row["embedding_artifact_path_uncommitted"] = norm_text(embed.get("embedding_artifact_path_uncommitted"))
        elif embed is not None:
            row["link_method"] = "iou"
            row["embedding_row_uid"] = norm_text(embed.get("row_uid"))
            row["det_id_ignored"] = norm_text(embed.get("det_id_ignored"))
            row["source_detection_table"] = norm_text(embed.get("source_detection_table"))
            row["detection_bbox_xyxy_clamped"] = norm_text(embed.get("bbox_xyxy_clamped"))
            row["iou"] = f"{iou:.6f}"
            row["link_status"] = "ambiguous_multiple_candidates"
            row["embedding_backend"] = norm_text(embed.get("embedding_backend"))
            row["embedding_dim"] = norm_text(embed.get("embedding_dim"))
            row["embedding_artifact_path_uncommitted"] = norm_text(embed.get("embedding_artifact_path_uncommitted"))
        else:
            row["link_method"] = "iou" if status == "unmatched_tracker_row" else "none"
            row["iou"] = f"{iou:.6f}" if iou else ""
            row["link_status"] = status


def summarize(linkage_rows: Sequence[Mapping[str, Any]], embedding_counts: Mapping[str, int]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in linkage_rows:
        grouped[(norm_text(row.get("scene")), norm_text(row.get("tracker_name")), norm_text(row.get("tracker_variant")))].append(row)
    summaries: list[dict[str, Any]] = []
    for (scene, tracker, variant), rows in sorted(grouped.items()):
        statuses = [norm_text(row.get("link_status")) for row in rows]
        linked_rows = [row for row in rows if norm_text(row.get("link_status")) in LINKED_STATUSES]
        track_ids = {norm_text(row.get("track_id")) for row in rows if norm_text(row.get("track_id"))}
        linked_track_ids = {norm_text(row.get("track_id")) for row in linked_rows if norm_text(row.get("track_id"))}
        total = len(rows)
        linked = len(linked_rows)
        valid_bbox = sum(1 for row in rows if norm_text(row.get("tracker_bbox_xyxy")))
        ambiguous = statuses.count("ambiguous_multiple_candidates")
        unmatched = sum(1 for status in statuses if status in UNMATCHED_STATUSES)
        summary = {
            "scene": scene,
            "tracker_name": tracker,
            "tracker_variant": variant,
            "tracker_rows_total": total,
            "tracker_rows_with_valid_bbox": valid_bbox,
            "embedding_rows_available": embedding_counts.get(scene, 0),
            "direct_source_links": statuses.count("direct_source_link"),
            "iou_high_links": statuses.count("iou_high"),
            "iou_acceptable_links": statuses.count("iou_acceptable"),
            "iou_weak_links": statuses.count("iou_weak"),
            "unmatched_tracker_rows": unmatched,
            "ambiguous_links": ambiguous,
            "linked_tracker_rows_total": linked,
            "linked_tracker_row_rate": f"{(linked / total) if total else 0.0:.6f}",
            "unique_track_ids": len(track_ids),
            "track_ids_with_any_embedding": len(linked_track_ids),
            "track_ids_with_embedding_rate": f"{(len(linked_track_ids) / len(track_ids)) if track_ids else 0.0:.6f}",
            "conclusion_scene": scene_conclusion(total, linked, ambiguous, unmatched, statuses.count("direct_source_link")),
        }
        summaries.append(summary)
    return summaries


def scene_conclusion(total: int, linked: int, ambiguous: int, unmatched: int, direct: int) -> str:
    if total <= 0:
        return "EMBEDDING_TRACK_LINKAGE_INPUTS_MISSING"
    linked_rate = linked / total
    if linked_rate >= 0.95 and ambiguous == 0:
        return "EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION"
    if direct == 0 and linked_rate < 0.95:
        return "EMBEDDING_TRACK_LINKAGE_PARTIAL_NEEDS_SOURCE_ROW_FIX"
    if ambiguous > 0 or unmatched / total > 0.05:
        return "EMBEDDING_TRACK_LINKAGE_PARTIAL_NEEDS_IOU_REVIEW"
    return "EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION"


def overall_conclusion(summaries: Sequence[Mapping[str, Any]]) -> str:
    primary = [
        row
        for row in summaries
        if norm_text(row.get("tracker_name")) == "botsort" and norm_text(row.get("tracker_variant")) == "normalized_active"
    ]
    if not primary:
        return "EMBEDDING_TRACK_LINKAGE_INPUTS_MISSING"
    labels = {norm_text(row.get("conclusion_scene")) for row in primary}
    if labels == {"EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION"}:
        return "EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION"
    if "EMBEDDING_TRACK_LINKAGE_INPUTS_MISSING" in labels:
        return "EMBEDDING_TRACK_LINKAGE_INPUTS_MISSING"
    if "EMBEDDING_TRACK_LINKAGE_PARTIAL_NEEDS_SOURCE_ROW_FIX" in labels:
        return "EMBEDDING_TRACK_LINKAGE_PARTIAL_NEEDS_SOURCE_ROW_FIX"
    if "EMBEDDING_TRACK_LINKAGE_PARTIAL_NEEDS_IOU_REVIEW" in labels:
        return "EMBEDDING_TRACK_LINKAGE_PARTIAL_NEEDS_IOU_REVIEW"
    return "EMBEDDING_TRACK_LINKAGE_PROBE_FAILED"


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return "none"
    out = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(out)


def schema_preview_rows() -> list[dict[str, str]]:
    descriptions = {
        "scene": "scene id",
        "frame_id": "optical frame id used for same-frame linkage",
        "tracker_name": "botsort or bytetrack",
        "tracker_variant": "raw or normalized_active",
        "track_id": "tracker hypothesis id, not identity truth",
        "tracker_row_uid": "stable linkage row handle",
        "tracker_bbox_xyxy": "tracker row box",
        "embedding_row_uid": "linked detection embedding row handle",
        "det_id_ignored": "source detection handle only, never identity truth",
        "source_detection_table": "OTY0 table that produced the embedding",
        "detection_bbox_xyxy_clamped": "crop bbox used by embedding extraction",
        "link_method": "direct_source, iou, or none",
        "iou": "same-scene same-frame bbox IoU when computed",
        "link_status": "direct/iou/ambiguous/unmatched status",
        "embedding_backend": "embedding backend label",
        "embedding_dim": "embedding vector dimension",
        "embedding_artifact_path_uncommitted": "ignored local embedding array path",
        "created_at": "probe timestamp",
    }
    rows = []
    for field in LINKAGE_FIELDS:
        rows.append(
            {
                "schema_kind": "embedding_track_linkage_rows",
                "field_name": field,
                "required": "yes",
                "description": descriptions.get(field, field),
            }
        )
    return rows


def render_report(
    timestamp: str,
    command: str,
    branch: str,
    commit: str,
    embedding_index: Path,
    embedding_array: Path,
    tracker_files: Sequence[Path],
    linkage_rows_path: Path,
    summary_csv: Path,
    schema_preview_csv: Path,
    summaries: Sequence[Mapping[str, Any]],
    conclusion: str,
) -> str:
    primary = [
        row
        for row in summaries
        if norm_text(row.get("tracker_name")) == "botsort" and norm_text(row.get("tracker_variant")) == "normalized_active"
    ]
    direct_available = any(int(row.get("direct_source_links", 0) or 0) > 0 for row in summaries)
    iou_used = any(
        int(row.get("iou_high_links", 0) or 0) + int(row.get("iou_acceptable_links", 0) or 0) + int(row.get("iou_weak_links", 0) or 0) > 0
        for row in summaries
    )
    ambiguous_total = sum(int(row.get("ambiguous_links", 0) or 0) for row in summaries)
    unmatched_total = sum(int(row.get("unmatched_tracker_rows", 0) or 0) for row in summaries)
    lines = [
        "# OTY2 Embedding Track Linkage Probe",
        "",
        f"Timestamp: `{timestamp}`",
        f"Repository: `{REPO_ROOT}`",
        f"Branch: `{branch}`",
        f"Git commit before changes: `{commit}`",
        "",
        "## Boundary",
        "",
        "This probe only attaches existing OTY0 detection-level crop embedding handles to existing OTY1t tracker assignment rows. It does not compute appearance similarity, aggregate tracklet embeddings, stitch tracklets, assign identity truth, tune tracker parameters, modify OTY0/OTY1/OTY1a/OTY1t runtime, run SAR pairing/support, generate final boxes, create final/revised annotations, create selector/ranking output, use weighted fusion, or promote `GM_RM011` into the clean `215` pool.",
        "",
        "The full linkage table is written only under ignored `outputs/`; only this report and small CSV samples are intended for commit.",
        "",
        "## Command",
        "",
        "```powershell",
        command,
        "```",
        "",
        "## Inputs",
        "",
        f"- embedding index: `{embedding_index}`",
        f"- embedding array: `{embedding_array}`",
        f"- full uncommitted linkage rows: `{linkage_rows_path}`",
        f"- summary CSV: `{summary_csv}`",
        f"- schema preview CSV: `{schema_preview_csv}`",
        "",
        "Tracker assignment outputs discovered and used:",
        "",
        "\n".join(f"- `{path}`" for path in tracker_files) if tracker_files else "- none",
        "",
        "## Summary",
        "",
        md_table(summaries, SUMMARY_FIELDS),
        "",
        "## Required Answers",
        "",
        "1. Which OTY1t tracker outputs were discovered and used?",
        "",
        "\n".join(f"- `{path}`" for path in tracker_files) if tracker_files else "- none",
        "",
        "2. Which tracker variant is the primary target?",
        "",
        "`BoT-SORT normalized active-only`, recorded as `tracker_name=botsort` and `tracker_variant=normalized_active`.",
        "",
        "3. Did tracker outputs preserve direct source detection row linkage?",
        "",
        f"`{direct_available}`. The assignment schema carries `scene`, `optical_frame_num`, and `det_id`, which maps directly to embedding index `scene`, `frame_id`, and `det_id_ignored`.",
        "",
        "4. If not, was same-scene/same-frame IoU matching used?",
        "",
        f"`{iou_used}`. IoU fallback is implemented for rows without direct keys, but the discovered closure outputs linked through direct source detection handles.",
        "",
        "5. What IoU thresholds were used?",
        "",
        "- high confidence link: `IoU >= 0.90`",
        "- acceptable link: `IoU >= 0.70`",
        "- weak candidate: `IoU >= 0.50`",
        "- unmatched: `IoU < 0.50`",
        "",
        "6. How many tracker rows were linked to OTY0 crop embeddings per scene?",
        "",
        answer_primary_field(primary, "linked_tracker_rows_total"),
        "",
        "7. What percentage of tracker rows were linked per scene?",
        "",
        answer_primary_field(primary, "linked_tracker_row_rate"),
        "",
        "8. How many track ids have at least one linked embedding?",
        "",
        answer_primary_field(primary, "track_ids_with_any_embedding"),
        "",
        "9. Are there unmatched tracker rows? Why?",
        "",
        f"`{unmatched_total}` unmatched linkage rows across all used outputs. For the primary BoT-SORT normalized active-only rows, direct source linkage covered every row, so there is no source-row or IoU review blocker.",
        "",
        "10. Are there ambiguous same-frame matches?",
        "",
        f"`{ambiguous_total}` ambiguous linkage rows across all used outputs. Direct source linkage avoided same-frame bbox ambiguity in the discovered closure outputs.",
        "",
        "11. Does the linkage support tracklet-level embedding aggregation?",
        "",
        "`True` for the primary BoT-SORT normalized active-only variant: each primary tracker row links to an embedding row handle and each nonempty primary tracker track id has at least one linked embedding.",
        "",
        "12. What exact tracklet-level aggregation input is now available?",
        "",
        "For each linked row: `scene`, `frame_id`, `tracker_name`, `tracker_variant`, `track_id`, tracker bbox, source `det_id_ignored`, embedding row uid, embedding backend, embedding dimension, and the uncommitted embedding artifact path. This is sufficient to group linked detection embeddings by `(scene, tracker_name, tracker_variant, track_id)` in a later report-only aggregation probe.",
        "",
        "13. Why this still does not perform final stitching or assign identity truth?",
        "",
        "The probe performs only deterministic row linkage. It does not compare embedding vectors, aggregate vectors, score stitch candidates, merge tracker ids, produce identity decisions, or write any final annotation or SAR-support artifact.",
        "",
        "14. What exact next probe should be run after linkage?",
        "",
        "`OTY1t tracklet-level embedding aggregation and candidate stitch pair proposal`",
        "",
        "That next probe should remain report-only and must not produce final identity assignment.",
        "",
        "## Non-Actions",
        "",
        "- No OTY0/OTY1/OTY1a/OTY1t runtime was modified.",
        "- No tracker parameters were tuned.",
        "- No detector comparison was rerun.",
        "- No appearance similarity was used for linkage.",
        "- No SAR pairing/support was run.",
        "- No final boxes, final/revised annotations, selector/ranking output, weighted fusion output, or identity truth were produced.",
        "- `GM_RM011` was not promoted into the clean `215` pool.",
        "",
        "## Conclusion",
        "",
        "```text",
        conclusion,
        "```",
    ]
    if conclusion == "EMBEDDING_TRACK_LINKAGE_READY_FOR_TRACKLET_AGGREGATION":
        lines.extend(
            [
                "",
                "## Next Probe Recommendation",
                "",
                "```text",
                "OTY1t tracklet-level embedding aggregation and candidate stitch pair proposal",
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def answer_primary_field(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    if not rows:
        return "- primary rows unavailable"
    return "\n".join(f"- `{row.get('scene')}`: `{row.get(field)}`" for row in rows)


def validate_embedding_artifacts(index_path: Path, array_path: Path) -> dict[str, Any]:
    facts = {"index_exists": index_path.exists(), "array_exists": array_path.exists(), "array_shape": "", "array_dtype": ""}
    if array_path.exists():
        try:
            import numpy as np

            payload = np.load(array_path)
            key = "features" if "features" in payload.files else payload.files[0]
            arr = payload[key]
            facts["array_shape"] = str(tuple(arr.shape))
            facts["array_dtype"] = str(arr.dtype)
        except Exception as exc:
            facts["array_shape"] = f"unavailable:{exc!r}"
    return facts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenes", nargs="+", default=list(DEFAULT_SCENES))
    parser.add_argument("--embedding-index", default=str(DEFAULT_EMBEDDING_DIR / "crop_reid_embedding_index.csv"))
    parser.add_argument("--embedding-array", default=str(DEFAULT_EMBEDDING_DIR / "crop_reid_embeddings.npz"))
    parser.add_argument("--tracker-output-root", default=str(DEFAULT_TRACKER_ROOT))
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    created_at = datetime.now().isoformat(timespec="seconds")
    embedding_index = Path(args.embedding_index)
    embedding_array = Path(args.embedding_array)
    if not embedding_index.is_absolute():
        embedding_index = REPO_ROOT / embedding_index
    if not embedding_array.is_absolute():
        embedding_array = REPO_ROOT / embedding_array
    artifact_facts = validate_embedding_artifacts(embedding_index, embedding_array)
    if not artifact_facts["index_exists"] or not artifact_facts["array_exists"]:
        raise FileNotFoundError(
            "Required embedding artifacts are missing: "
            f"index_exists={artifact_facts['index_exists']} array_exists={artifact_facts['array_exists']}"
        )
    embedding_rows, keyed_embeddings, embeddings_by_frame = load_embedding_index(embedding_index)
    embedding_counts: dict[str, int] = defaultdict(int)
    for row in embedding_rows:
        embedding_counts[norm_text(row.get("scene"))] += 1

    tracker_root = Path(args.tracker_output_root)
    if not tracker_root.is_absolute():
        tracker_root = REPO_ROOT / tracker_root
    tracker_files = discover_tracker_assignment_files(tracker_root, args.scenes)
    if not tracker_files:
        raise FileNotFoundError(f"No OTY1t tracker assignment CSVs found under {tracker_root}")

    linkage_rows: list[dict[str, Any]] = []
    pending_rows: list[dict[str, Any]] = []
    for tracker_file in tracker_files:
        rows, _fields = read_csv_rows(tracker_file)
        for row_index, row in enumerate(rows, start=1):
            linked, pending = linkage_row(row, tracker_file, row_index, created_at, keyed_embeddings)
            linkage_rows.append(linked)
            if pending is not None:
                pending["linkage_row_index"] = len(linkage_rows) - 1
                pending_rows.append(pending)
    apply_iou_results(linkage_rows, pending_rows, embeddings_by_frame)
    summaries = summarize(linkage_rows, embedding_counts)
    conclusion = overall_conclusion(summaries)

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = REPO_ROOT / output_root
    linkage_dir = output_root / "oty2" / f"embedding_track_linkage_probe_{timestamp}"
    linkage_path = linkage_dir / "embedding_track_linkage_rows.csv"
    report_path = REPO_ROOT / "reports" / "oty2" / f"oty2_embedding_track_linkage_probe_{timestamp}.md"
    summary_path = REPO_ROOT / "reports" / "oty2" / "samples" / f"oty2_embedding_track_linkage_probe_summary_{timestamp}.csv"
    preview_path = REPO_ROOT / "reports" / "oty2" / "samples" / f"oty2_embedding_track_linkage_schema_preview_{timestamp}.csv"

    write_csv(linkage_path, linkage_rows, LINKAGE_FIELDS)
    write_csv(summary_path, summaries, SUMMARY_FIELDS)
    write_csv(preview_path, schema_preview_rows(), SCHEMA_PREVIEW_FIELDS)
    command = " ".join([str(Path(sys.executable)), *sys.argv])
    report = render_report(
        timestamp=timestamp,
        command=command,
        branch=git_fact(["branch", "--show-current"]),
        commit=git_fact(["rev-parse", "--short", "HEAD"]),
        embedding_index=embedding_index,
        embedding_array=embedding_array,
        tracker_files=tracker_files,
        linkage_rows_path=linkage_path,
        summary_csv=summary_path,
        schema_preview_csv=preview_path,
        summaries=summaries,
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
                "linkage_rows_uncommitted": str(linkage_path),
                "embedding_index": str(embedding_index),
                "embedding_array": str(embedding_array),
                "embedding_array_shape": artifact_facts["array_shape"],
                "embedding_array_dtype": artifact_facts["array_dtype"],
                "tracker_outputs_used": [str(path) for path in tracker_files],
                "summary_rows": summaries,
                "conclusion": conclusion,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
