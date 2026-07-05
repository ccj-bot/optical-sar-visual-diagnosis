"""Aggregate linked detection embeddings into OTY1t tracklet-segment features.

This bounded diagnostic starts from the previous embedding-to-tracker linkage
table and aggregates only within short tracklet segments. It does not compare
different tracklets, generate stitch candidates, merge identities, tune tracker
parameters, modify OTY runtime code, run SAR pairing/support, or write final
annotation artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENES = ("GM_RM011", "GM_RM019", "GM_RM017")
DEFAULT_LINKAGE_ROWS = REPO_ROOT / "outputs" / "oty2" / "embedding_track_linkage_probe_20260705_183000" / "embedding_track_linkage_rows.csv"
DEFAULT_EMBEDDING_ARRAY = REPO_ROOT / "outputs" / "oty2" / "crop_reid_embedding_probe_20260705_170500" / "crop_reid_embeddings.npz"
DEFAULT_EMBEDDING_INDEX = REPO_ROOT / "outputs" / "oty2" / "crop_reid_embedding_probe_20260705_170500" / "crop_reid_embedding_index.csv"

INDEX_FIELDS = [
    "scene",
    "tracker_name",
    "tracker_variant",
    "track_id",
    "tracklet_segment_id",
    "frame_start",
    "frame_end",
    "frame_count",
    "linked_embedding_count",
    "missing_embedding_count",
    "embedding_coverage",
    "embedding_backend",
    "embedding_dim",
    "tracklet_embedding_policy",
    "tracklet_embedding_l2_normed",
    "intra_tracklet_cosine_mean",
    "intra_tracklet_cosine_min",
    "intra_tracklet_cosine_std",
    "bbox_center_x_mean",
    "bbox_center_y_mean",
    "bbox_w_mean",
    "bbox_h_mean",
    "bbox_center_x_start",
    "bbox_center_y_start",
    "bbox_center_x_end",
    "bbox_center_y_end",
    "bbox_motion_dx",
    "bbox_motion_dy",
    "source_linkage_table",
    "tracklet_embedding_artifact_path_uncommitted",
    "created_at",
]

SUMMARY_FIELDS = [
    "scene",
    "tracker_name",
    "tracker_variant",
    "track_ids_total",
    "tracklet_segments_total",
    "segments_with_embeddings",
    "segments_without_embeddings",
    "segments_embedding_coverage_mean",
    "segments_embedding_coverage_min",
    "embedding_dim",
    "intra_tracklet_cosine_mean",
    "intra_tracklet_cosine_min",
    "unstable_segments_count",
    "short_segments_count",
    "ready_segments_count",
    "conclusion_scene",
]

SCHEMA_PREVIEW_FIELDS = ["schema_kind", "field_name", "required", "description"]


@dataclass(frozen=True)
class LinkageRecord:
    scene: str
    tracker_name: str
    tracker_variant: str
    track_id: str
    frame_id: int
    embedding_row_uid: str
    link_status: str
    tracker_bbox_xyxy: tuple[float, float, float, float] | None
    embedding_backend: str
    embedding_dim: str


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


def norm_text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_int(value: Any) -> int | None:
    text = norm_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_bbox(value: Any) -> tuple[float, float, float, float] | None:
    text = norm_text(value)
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or len(parsed) < 4:
        return None
    try:
        x1, y1, x2, y2 = (float(item) for item in parsed[:4])
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def bbox_center(bbox: tuple[float, float, float, float] | None) -> tuple[float, float] | None:
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def bbox_size(bbox: tuple[float, float, float, float] | None) -> tuple[float, float] | None:
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    return x2 - x1, y2 - y1


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(REPO_ROOT), text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def load_embedding_uid_to_index(index_path: Path) -> dict[str, int]:
    rows, _fields = read_csv_rows(index_path)
    out: dict[str, int] = {}
    for idx, row in enumerate(rows):
        uid = norm_text(row.get("row_uid"))
        if uid:
            out[uid] = idx
    return out


def load_feature_array(array_path: Path) -> np.ndarray:
    payload = np.load(array_path)
    key = "features" if "features" in payload.files else payload.files[0]
    arr = payload[key]
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D feature array, got shape {arr.shape}")
    return arr.astype(np.float32, copy=False)


def load_linkage_records(
    linkage_path: Path,
    scenes: Sequence[str],
    primary_tracker: str,
    primary_variant: str,
) -> list[LinkageRecord]:
    scene_set = set(scenes)
    rows, _fields = read_csv_rows(linkage_path)
    records: list[LinkageRecord] = []
    for row in rows:
        scene = norm_text(row.get("scene"))
        tracker = norm_text(row.get("tracker_name"))
        variant = norm_text(row.get("tracker_variant"))
        if scene not in scene_set or tracker != primary_tracker or variant != primary_variant:
            continue
        frame = parse_int(row.get("frame_id"))
        track_id = norm_text(row.get("track_id"))
        if frame is None or not track_id:
            continue
        records.append(
            LinkageRecord(
                scene=scene,
                tracker_name=tracker,
                tracker_variant=variant,
                track_id=track_id,
                frame_id=frame,
                embedding_row_uid=norm_text(row.get("embedding_row_uid")),
                link_status=norm_text(row.get("link_status")),
                tracker_bbox_xyxy=parse_bbox(row.get("tracker_bbox_xyxy")),
                embedding_backend=norm_text(row.get("embedding_backend")),
                embedding_dim=norm_text(row.get("embedding_dim")),
            )
        )
    return sorted(records, key=lambda rec: (rec.scene, rec.track_id, rec.frame_id, rec.embedding_row_uid))


def split_segments(records: Sequence[LinkageRecord], max_frame_gap: int) -> list[list[LinkageRecord]]:
    grouped: dict[tuple[str, str, str, str], list[LinkageRecord]] = defaultdict(list)
    for rec in records:
        grouped[(rec.scene, rec.tracker_name, rec.tracker_variant, rec.track_id)].append(rec)
    segments: list[list[LinkageRecord]] = []
    for key in sorted(grouped):
        current: list[LinkageRecord] = []
        previous_frame: int | None = None
        for rec in sorted(grouped[key], key=lambda item: (item.frame_id, item.embedding_row_uid)):
            if previous_frame is not None and rec.frame_id - previous_frame > max_frame_gap:
                if current:
                    segments.append(current)
                current = []
            current.append(rec)
            previous_frame = rec.frame_id
        if current:
            segments.append(current)
    return segments


def l2_normalize(vector: np.ndarray) -> tuple[np.ndarray, bool]:
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0 or not math.isfinite(norm):
        return vector.astype(np.float32, copy=False), False
    return (vector / norm).astype(np.float32, copy=False), True


def safe_mean(values: Sequence[float]) -> str:
    return f"{statistics.fmean(values):.6f}" if values else ""


def safe_min(values: Sequence[float]) -> str:
    return f"{min(values):.6f}" if values else ""


def safe_std(values: Sequence[float]) -> str:
    return f"{statistics.pstdev(values):.6f}" if len(values) > 1 else ("0.000000" if values else "")


def aggregate_segments(
    segments: Sequence[Sequence[LinkageRecord]],
    uid_to_index: Mapping[str, int],
    features: np.ndarray,
    linkage_path: Path,
    artifact_npz_path: Path,
    created_at: str,
    min_ready_embeddings: int,
    unstable_cosine_min_threshold: float,
) -> tuple[list[dict[str, Any]], np.ndarray, dict[str, str]]:
    index_rows: list[dict[str, Any]] = []
    vectors: list[np.ndarray] = []
    segment_status: dict[str, str] = {}
    for segment in segments:
        first = segment[0]
        frames = [rec.frame_id for rec in segment]
        vector_rows: list[np.ndarray] = []
        linked_count = 0
        missing_count = 0
        for rec in segment:
            idx = uid_to_index.get(rec.embedding_row_uid)
            if rec.embedding_row_uid and idx is not None and 0 <= idx < features.shape[0]:
                vector_rows.append(features[idx])
                linked_count += 1
            else:
                missing_count += 1
        frame_count = len(segment)
        coverage = linked_count / frame_count if frame_count else 0.0
        centers = [bbox_center(rec.tracker_bbox_xyxy) for rec in segment]
        centers = [center for center in centers if center is not None]
        sizes = [bbox_size(rec.tracker_bbox_xyxy) for rec in segment]
        sizes = [size for size in sizes if size is not None]
        embedding_dim = int(features.shape[1]) if features.ndim == 2 else 0
        aggregate = np.zeros((embedding_dim,), dtype=np.float32)
        l2_normed = False
        cosines: list[float] = []
        if vector_rows:
            mean_vector = np.mean(np.stack(vector_rows).astype(np.float32), axis=0)
            aggregate, l2_normed = l2_normalize(mean_vector)
            cosines = [float(np.dot(row, aggregate)) for row in vector_rows]
        segment_index = sum(
            1
            for row in index_rows
            if row["scene"] == first.scene
            and row["tracker_name"] == first.tracker_name
            and row["tracker_variant"] == first.tracker_variant
            and row["track_id"] == first.track_id
        ) + 1
        segment_id = f"{first.scene}__{first.tracker_name}__{first.tracker_variant}__{first.track_id}__seg_{segment_index:03d}"
        is_short = linked_count < min_ready_embeddings
        is_unstable = bool(cosines) and min(cosines) < unstable_cosine_min_threshold
        if linked_count <= 0:
            status = "no_embedding"
        elif is_short:
            status = "short_segment"
        elif is_unstable:
            status = "unstable_appearance"
        else:
            status = "ready_for_candidate_stitching_input"
        segment_status[segment_id] = status
        if vector_rows:
            vectors.append(aggregate)
        bbox_start = centers[0] if centers else ("", "")
        bbox_end = centers[-1] if centers else ("", "")
        mean_w = safe_mean([size[0] for size in sizes])
        mean_h = safe_mean([size[1] for size in sizes])
        index_rows.append(
            {
                "scene": first.scene,
                "tracker_name": first.tracker_name,
                "tracker_variant": first.tracker_variant,
                "track_id": first.track_id,
                "tracklet_segment_id": segment_id,
                "frame_start": min(frames),
                "frame_end": max(frames),
                "frame_count": frame_count,
                "linked_embedding_count": linked_count,
                "missing_embedding_count": missing_count,
                "embedding_coverage": f"{coverage:.6f}",
                "embedding_backend": first.embedding_backend or "unknown",
                "embedding_dim": embedding_dim,
                "tracklet_embedding_policy": "mean_detection_embedding_then_l2_normalize",
                "tracklet_embedding_l2_normed": l2_normed,
                "intra_tracklet_cosine_mean": safe_mean(cosines),
                "intra_tracklet_cosine_min": safe_min(cosines),
                "intra_tracklet_cosine_std": safe_std(cosines),
                "bbox_center_x_mean": safe_mean([center[0] for center in centers]),
                "bbox_center_y_mean": safe_mean([center[1] for center in centers]),
                "bbox_w_mean": mean_w,
                "bbox_h_mean": mean_h,
                "bbox_center_x_start": f"{bbox_start[0]:.6f}" if isinstance(bbox_start[0], float) else "",
                "bbox_center_y_start": f"{bbox_start[1]:.6f}" if isinstance(bbox_start[1], float) else "",
                "bbox_center_x_end": f"{bbox_end[0]:.6f}" if isinstance(bbox_end[0], float) else "",
                "bbox_center_y_end": f"{bbox_end[1]:.6f}" if isinstance(bbox_end[1], float) else "",
                "bbox_motion_dx": f"{(bbox_end[0] - bbox_start[0]):.6f}" if isinstance(bbox_start[0], float) and isinstance(bbox_end[0], float) else "",
                "bbox_motion_dy": f"{(bbox_end[1] - bbox_start[1]):.6f}" if isinstance(bbox_start[1], float) and isinstance(bbox_end[1], float) else "",
                "source_linkage_table": str(linkage_path),
                "tracklet_embedding_artifact_path_uncommitted": str(artifact_npz_path) if vector_rows else "",
                "created_at": created_at,
            }
        )
    if vectors:
        return index_rows, np.stack(vectors).astype(np.float32), segment_status
    return index_rows, np.zeros((0, features.shape[1] if features.ndim == 2 else 0), dtype=np.float32), segment_status


def summarize(index_rows: Sequence[Mapping[str, Any]], segment_status: Mapping[str, str], unstable_threshold: float) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in index_rows:
        grouped[(norm_text(row.get("scene")), norm_text(row.get("tracker_name")), norm_text(row.get("tracker_variant")))].append(row)
    summaries: list[dict[str, Any]] = []
    for (scene, tracker, variant), rows in sorted(grouped.items()):
        track_ids = {norm_text(row.get("track_id")) for row in rows if norm_text(row.get("track_id"))}
        coverages = [float(row.get("embedding_coverage", 0) or 0) for row in rows]
        cosine_means = [float(row.get("intra_tracklet_cosine_mean")) for row in rows if norm_text(row.get("intra_tracklet_cosine_mean"))]
        cosine_mins = [float(row.get("intra_tracklet_cosine_min")) for row in rows if norm_text(row.get("intra_tracklet_cosine_min"))]
        statuses = [segment_status.get(norm_text(row.get("tracklet_segment_id")), "") for row in rows]
        with_embeddings = sum(1 for row in rows if int(row.get("linked_embedding_count", 0) or 0) > 0)
        without_embeddings = len(rows) - with_embeddings
        unstable = sum(1 for status in statuses if status == "unstable_appearance")
        short = sum(1 for status in statuses if status == "short_segment")
        ready = sum(1 for status in statuses if status == "ready_for_candidate_stitching_input")
        summary = {
            "scene": scene,
            "tracker_name": tracker,
            "tracker_variant": variant,
            "track_ids_total": len(track_ids),
            "tracklet_segments_total": len(rows),
            "segments_with_embeddings": with_embeddings,
            "segments_without_embeddings": without_embeddings,
            "segments_embedding_coverage_mean": safe_mean(coverages),
            "segments_embedding_coverage_min": safe_min(coverages),
            "embedding_dim": rows[0].get("embedding_dim", "") if rows else "",
            "intra_tracklet_cosine_mean": safe_mean(cosine_means),
            "intra_tracklet_cosine_min": safe_min(cosine_mins),
            "unstable_segments_count": unstable,
            "short_segments_count": short,
            "ready_segments_count": ready,
            "conclusion_scene": scene_conclusion(len(rows), with_embeddings, without_embeddings, unstable, short, ready),
        }
        _ = unstable_threshold
        summaries.append(summary)
    return summaries


def scene_conclusion(total: int, with_embeddings: int, without_embeddings: int, unstable: int, short: int, ready: int) -> str:
    if total <= 0 or with_embeddings <= 0:
        return "TRACKLET_EMBEDDING_AGGREGATION_INPUTS_MISSING"
    if without_embeddings > 0:
        return "TRACKLET_EMBEDDING_AGGREGATION_PARTIAL_SHORT_OR_UNSTABLE"
    short_or_unstable_rate = (short + unstable) / total
    if ready > 0 and short_or_unstable_rate <= 0.50:
        return "TRACKLET_EMBEDDING_AGGREGATION_READY_FOR_CANDIDATE_STITCHING"
    return "TRACKLET_EMBEDDING_AGGREGATION_PARTIAL_SHORT_OR_UNSTABLE"


def overall_conclusion(summaries: Sequence[Mapping[str, Any]]) -> str:
    labels = {norm_text(row.get("conclusion_scene")) for row in summaries}
    if not labels or "TRACKLET_EMBEDDING_AGGREGATION_INPUTS_MISSING" in labels:
        return "TRACKLET_EMBEDDING_AGGREGATION_INPUTS_MISSING"
    if labels == {"TRACKLET_EMBEDDING_AGGREGATION_READY_FOR_CANDIDATE_STITCHING"}:
        return "TRACKLET_EMBEDDING_AGGREGATION_READY_FOR_CANDIDATE_STITCHING"
    if "TRACKLET_EMBEDDING_AGGREGATION_PARTIAL_SHORT_OR_UNSTABLE" in labels:
        return "TRACKLET_EMBEDDING_AGGREGATION_PARTIAL_SHORT_OR_UNSTABLE"
    return "TRACKLET_EMBEDDING_AGGREGATION_PROBE_FAILED"


def write_npz(path: Path, embeddings: np.ndarray, segment_ids: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, tracklet_embeddings=embeddings.astype(np.float32), tracklet_segment_ids=np.array(list(segment_ids)))


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return "none"
    out = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(out)


def schema_preview_rows() -> list[dict[str, str]]:
    descriptions = {
        "tracklet_segment_id": "short tracklet segment handle after frame-gap splitting",
        "linked_embedding_count": "number of detection embeddings used in the segment aggregate",
        "missing_embedding_count": "segment rows without an attached embedding vector",
        "embedding_coverage": "linked_embedding_count / frame_count",
        "tracklet_embedding_policy": "mean detection feature followed by L2 normalization",
        "intra_tracklet_cosine_mean": "mean cosine from detection vectors to aggregate vector",
        "intra_tracklet_cosine_min": "minimum cosine from detection vectors to aggregate vector",
        "intra_tracklet_cosine_std": "population standard deviation of those cosines",
        "bbox_center_x_mean": "mean tracker bbox center x for the segment",
        "bbox_center_y_mean": "mean tracker bbox center y for the segment",
        "bbox_w_mean": "mean tracker bbox width for the segment",
        "bbox_h_mean": "mean tracker bbox height for the segment",
        "tracklet_embedding_artifact_path_uncommitted": "ignored local npz path under outputs",
    }
    return [
        {
            "schema_kind": "tracklet_embedding_index",
            "field_name": field,
            "required": "yes",
            "description": descriptions.get(field, field),
        }
        for field in INDEX_FIELDS
    ]


def answer_scene_field(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    if not rows:
        return "- none"
    return "\n".join(f"- `{row.get('scene')}`: `{row.get(field)}`" for row in rows)


def count_gm011_track_eligibility(index_rows: Sequence[Mapping[str, Any]], segment_status: Mapping[str, str]) -> tuple[int, int]:
    by_track: dict[str, list[str]] = defaultdict(list)
    for row in index_rows:
        if row.get("scene") == "GM_RM011":
            by_track[norm_text(row.get("track_id"))].append(segment_status.get(norm_text(row.get("tracklet_segment_id")), ""))
    eligible = sum(1 for statuses in by_track.values() if any(status == "ready_for_candidate_stitching_input" for status in statuses))
    return eligible, len(by_track)


def unsuitable_segments(index_rows: Sequence[Mapping[str, Any]], segment_status: Mapping[str, str]) -> list[Mapping[str, Any]]:
    rows = []
    for row in index_rows:
        status = segment_status.get(norm_text(row.get("tracklet_segment_id")), "")
        if status in {"short_segment", "unstable_appearance", "no_embedding"}:
            rows.append(row)
    return rows


def render_report(
    timestamp: str,
    command: str,
    branch: str,
    commit: str,
    linkage_rows: Path,
    embedding_array: Path,
    embedding_index: Path,
    tracklet_index: Path,
    tracklet_npz: Path,
    summary_csv: Path,
    schema_preview_csv: Path,
    summaries: Sequence[Mapping[str, Any]],
    index_rows: Sequence[Mapping[str, Any]],
    segment_status: Mapping[str, str],
    max_frame_gap: int,
    min_ready_embeddings: int,
    unstable_threshold: float,
    conclusion: str,
) -> str:
    eligible_gm011, total_gm011 = count_gm011_track_eligibility(index_rows, segment_status)
    unsuitable = unsuitable_segments(index_rows, segment_status)
    lines = [
        "# OTY2 Tracklet Embedding Aggregation Probe",
        "",
        f"Timestamp: `{timestamp}`",
        f"Repository: `{REPO_ROOT}`",
        f"Branch: `{branch}`",
        f"Git commit before changes: `{commit}`",
        "",
        "## Boundary",
        "",
        "This probe aggregates already-linked detection embeddings inside OTY1t short tracklet segments only. It does not compare different tracklets, generate candidate stitch pairs, merge tracker ids, assign identity truth, tune tracker parameters, modify OTY0/OTY1/OTY1a/OTY1t runtime, run SAR pairing/support, generate final boxes, create final/revised annotation artifacts, create selector/ranking output, or promote `GM_RM011` into the clean `215` pool.",
        "",
        "The full tracklet embedding index and embedding array are written only under ignored `outputs/`; only this report and small CSV samples are intended for commit.",
        "",
        "## Command",
        "",
        "```powershell",
        command,
        "```",
        "",
        "## Inputs And Outputs",
        "",
        f"- input linkage rows: `{linkage_rows}`",
        f"- input embedding array: `{embedding_array}`",
        f"- input embedding index: `{embedding_index}`",
        f"- uncommitted tracklet index: `{tracklet_index}`",
        f"- uncommitted tracklet embeddings: `{tracklet_npz}`",
        f"- committed summary CSV: `{summary_csv}`",
        f"- committed schema preview CSV: `{schema_preview_csv}`",
        "",
        "## Segment Rule",
        "",
        f"Rows are grouped by `scene + tracker_name + tracker_variant + track_id`, sorted by frame, and split into a new short tracklet segment whenever adjacent linked tracker rows have frame gap `> {max_frame_gap}`. This run uses the primary tracker version only: `botsort / normalized_active`.",
        "",
        "## Aggregation Rule",
        "",
        "For each segment, all linked detection feature vectors are averaged, then the aggregate vector is L2-normalized. Stability is audited by cosine similarity from each detection vector in the segment to the aggregate vector. The audit records mean, minimum, and population standard deviation. This is an internal segment-quality audit only, not an identity decision.",
        "",
        f"Ready-segment policy for this report: at least `{min_ready_embeddings}` linked embeddings, full usable aggregate, and intra-segment minimum cosine `>= {unstable_threshold:.2f}`. Short or unstable segments are retained in the uncommitted index but should not be used as confident candidate-stitch evidence without review.",
        "",
        "## Summary",
        "",
        md_table(summaries, SUMMARY_FIELDS),
        "",
        "## Required Answers",
        "",
        "1. Which tracker version was used as the primary version?",
        "",
        "`botsort / normalized_active`.",
        "",
        "2. Did this use the previous direct source linkage result?",
        "",
        f"`True`. The input was the previous linkage table `{linkage_rows}`; no detector, tracker, or linkage rerun was needed.",
        "",
        "3. How were short tracklet segments defined?",
        "",
        f"By grouping on `scene + tracker_name + tracker_variant + track_id`, sorting by `frame_id`, and cutting a new segment at adjacent frame gaps greater than `{max_frame_gap}`.",
        "",
        "4. How many track ids are present per scene?",
        "",
        answer_scene_field(summaries, "track_ids_total"),
        "",
        "5. How many short tracklet segments were cut per scene?",
        "",
        answer_scene_field(summaries, "tracklet_segments_total"),
        "",
        "6. What is the embedding coverage of each scene's segments?",
        "",
        answer_scene_field(summaries, "segments_embedding_coverage_mean"),
        "",
        "7. How many short tracklet segments can form tracklet-level appearance features?",
        "",
        answer_scene_field(summaries, "segments_with_embeddings"),
        "",
        "8. How many segments are too short or appearance-unstable?",
        "",
        answer_scene_field(summaries, "short_segments_count"),
        "",
        "Unstable segment counts:",
        "",
        answer_scene_field(summaries, "unstable_segments_count"),
        "",
        "9. What is the appearance aggregation method?",
        "",
        "`mean_detection_embedding_then_l2_normalize`.",
        "",
        "10. How is appearance stability measured?",
        "",
        "By cosine similarity between each detection feature vector in the segment and the segment's L2-normalized aggregate vector; the report records mean, minimum, and standard deviation.",
        "",
        "11. Can all 17 `GM_RM011` tracks enter later candidate-stitch analysis?",
        "",
        f"`{eligible_gm011}/{total_gm011}` `GM_RM011` track ids have at least one ready segment under this audit policy. Tracks with only short segments remain available as weak context but should not be treated as confident stitch evidence.",
        "",
        "12. Which segments are not suitable for the next candidate-stitch probe?",
        "",
        unsuitable_answer(unsuitable),
        "",
        "13. Why this still does not perform final tracklet stitching?",
        "",
        "This run only creates per-segment aggregate appearance vectors and internal quality metrics. It does not compute inter-segment similarity, propose stitch pairs, merge track ids, assign identity truth, or write any annotation/SAR-support artifact.",
        "",
        "14. What inputs does the next candidate-stitch probe need?",
        "",
        "- this run's uncommitted `tracklet_embedding_index.csv`",
        "- this run's uncommitted `tracklet_embeddings.npz`",
        "- OTY1t tracker row/track timing metadata",
        "- segment endpoint frames and bbox motion summaries",
        "- later component/window evidence only as post-MOT blockers or context",
        "- an explicit report-only candidate-pair policy with no final identity assignment",
        "",
        "## Next Recommendation",
        "",
        "If this run is accepted as ready, the next bounded probe is:",
        "",
        "```text",
        "short tracklet candidate stitch-pair generation probe",
        "```",
        "",
        "The next probe must still output candidate evidence only, not final identity or final annotation.",
        "",
        "## Non-Actions",
        "",
        "- No OTY0/OTY1/OTY1a/OTY1t runtime was modified.",
        "- No tracker parameters were tuned.",
        "- No detector comparison was rerun.",
        "- No inter-tracklet appearance similarity was computed.",
        "- No candidate stitch pairs were generated.",
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
    return "\n".join(lines) + "\n"


def unsuitable_answer(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "- none"
    shown = rows[:20]
    lines = [
        f"- `{row.get('tracklet_segment_id')}`: scene=`{row.get('scene')}`, track=`{row.get('track_id')}`, frames=`{row.get('frame_start')}-{row.get('frame_end')}`, linked=`{row.get('linked_embedding_count')}`, min_cosine=`{row.get('intra_tracklet_cosine_min')}`"
        for row in shown
    ]
    if len(rows) > len(shown):
        lines.append(f"- plus `{len(rows) - len(shown)}` additional short/unstable segments in the uncommitted index")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenes", nargs="+", default=list(DEFAULT_SCENES))
    parser.add_argument("--linkage-rows", default=str(DEFAULT_LINKAGE_ROWS))
    parser.add_argument("--embedding-array", default=str(DEFAULT_EMBEDDING_ARRAY))
    parser.add_argument("--embedding-index", default=str(DEFAULT_EMBEDDING_INDEX))
    parser.add_argument("--primary-tracker", default="botsort")
    parser.add_argument("--primary-variant", default="normalized_active")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--max-frame-gap", type=int, default=1)
    parser.add_argument("--min-ready-embeddings", type=int, default=2)
    parser.add_argument("--unstable-cosine-min-threshold", type=float, default=0.70)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    created_at = datetime.now().isoformat(timespec="seconds")
    linkage_path = resolve_repo_path(args.linkage_rows)
    embedding_array_path = resolve_repo_path(args.embedding_array)
    embedding_index_path = resolve_repo_path(args.embedding_index)
    missing = [str(path) for path in (linkage_path, embedding_array_path, embedding_index_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("TRACKLET_EMBEDDING_AGGREGATION_INPUTS_MISSING: " + "; ".join(missing))

    features = load_feature_array(embedding_array_path)
    uid_to_index = load_embedding_uid_to_index(embedding_index_path)
    records = load_linkage_records(linkage_path, args.scenes, args.primary_tracker, args.primary_variant)
    if not records:
        raise FileNotFoundError("TRACKLET_EMBEDDING_AGGREGATION_INPUTS_MISSING: no primary linkage rows")
    segments = split_segments(records, max_frame_gap=args.max_frame_gap)

    output_root = resolve_repo_path(args.output_root)
    artifact_dir = output_root / "oty2" / f"tracklet_embedding_aggregation_probe_{timestamp}"
    tracklet_index_path = artifact_dir / "tracklet_embedding_index.csv"
    tracklet_npz_path = artifact_dir / "tracklet_embeddings.npz"
    index_rows, tracklet_embeddings, segment_status = aggregate_segments(
        segments=segments,
        uid_to_index=uid_to_index,
        features=features,
        linkage_path=linkage_path,
        artifact_npz_path=tracklet_npz_path,
        created_at=created_at,
        min_ready_embeddings=args.min_ready_embeddings,
        unstable_cosine_min_threshold=args.unstable_cosine_min_threshold,
    )
    segment_ids = [str(row["tracklet_segment_id"]) for row in index_rows if str(row.get("tracklet_embedding_artifact_path_uncommitted", ""))]
    write_csv(tracklet_index_path, index_rows, INDEX_FIELDS)
    write_npz(tracklet_npz_path, tracklet_embeddings, segment_ids)

    summaries = summarize(index_rows, segment_status, args.unstable_cosine_min_threshold)
    conclusion = overall_conclusion(summaries)
    report_path = REPO_ROOT / "reports" / "oty2" / f"oty2_tracklet_embedding_aggregation_probe_{timestamp}.md"
    summary_path = REPO_ROOT / "reports" / "oty2" / "samples" / f"oty2_tracklet_embedding_aggregation_probe_summary_{timestamp}.csv"
    preview_path = REPO_ROOT / "reports" / "oty2" / "samples" / f"oty2_tracklet_embedding_aggregation_schema_preview_{timestamp}.csv"
    write_csv(summary_path, summaries, SUMMARY_FIELDS)
    write_csv(preview_path, schema_preview_rows(), SCHEMA_PREVIEW_FIELDS)
    command = " ".join([str(Path(sys.executable)), *sys.argv])
    report = render_report(
        timestamp=timestamp,
        command=command,
        branch=git_fact(["branch", "--show-current"]),
        commit=git_fact(["rev-parse", "--short", "HEAD"]),
        linkage_rows=linkage_path,
        embedding_array=embedding_array_path,
        embedding_index=embedding_index_path,
        tracklet_index=tracklet_index_path,
        tracklet_npz=tracklet_npz_path,
        summary_csv=summary_path,
        schema_preview_csv=preview_path,
        summaries=summaries,
        index_rows=index_rows,
        segment_status=segment_status,
        max_frame_gap=args.max_frame_gap,
        min_ready_embeddings=args.min_ready_embeddings,
        unstable_threshold=args.unstable_cosine_min_threshold,
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
                "tracklet_index_uncommitted": str(tracklet_index_path),
                "tracklet_embeddings_uncommitted": str(tracklet_npz_path),
                "linkage_rows": str(linkage_path),
                "embedding_array": str(embedding_array_path),
                "embedding_index": str(embedding_index_path),
                "primary_tracker": args.primary_tracker,
                "primary_variant": args.primary_variant,
                "tracklet_embedding_shape": str(tuple(tracklet_embeddings.shape)),
                "summaries": summaries,
                "conclusion": conclusion,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
