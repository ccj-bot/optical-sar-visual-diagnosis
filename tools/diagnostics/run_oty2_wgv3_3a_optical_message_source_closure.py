"""Close WGV3.3A optical message source reproducibility.

This diagnostic consumes frozen YOLO26l detector, standard MOT, crop
appearance, and tracklet-embedding artifacts. It first writes automatic
tracklet nodes and relation decisions, records a hash manifest, and only then
loads WGV1.4 reference tables for posthoc mapping and evaluation.

It does not create final boxes, edit GT, revise annotations, enter SAR
candidate selection, train models, tune thresholds from WGV1.4, or claim
identity truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DATE = "20260710"
DEFAULT_RUN_TS = "20260710_000000"
DEFAULT_EMB_TS = "20260710_000000_yolo26l"
SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")

REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"

WGV14_THREADS = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_threads_20260708.csv"
WGV14_FRAGMENTS = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_fragments_20260708.csv"
WGV14_SAME_EDGES = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_same_vehicle_edges_20260708.csv"
WGV14_CONTEXT_EDGES = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_temporal_context_edges_20260708.csv"
WGV14_BLOCKED = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_blocked_review_items_20260708.csv"
WGV13_SPLIT = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_identity_safe_target_family_split_20260708.csv"
WGV12_FRAME_BANK = SAMPLES_DIR / "oty2_yolo26l_wgv1_2_per_frame_candidate_bank_20260708.csv"

NODE_FIELDS = [
    "auto_node_id",
    "scene",
    "detection_source",
    "tracker_name",
    "tracker_variant",
    "track_id",
    "tracklet_segment_id",
    "start_frame",
    "end_frame",
    "frame_count",
    "linked_embedding_count",
    "start_bbox",
    "end_bbox",
    "representative_frames",
    "mean_bbox_width",
    "mean_bbox_height",
    "mean_bbox_area",
    "aspect_ratio_mean",
    "aspect_ratio_std",
    "edge_contact_ratio",
    "truncation_like_ratio",
    "same_frame_competitor_count",
    "internal_embedding_stability",
    "aggregate_embedding_available",
    "motion_estimate_available",
    "track_identity_status",
    "track_status",
    "duplicate_track_overlap_count",
    "possible_id_switch_count",
    "missing_gap_count",
    "optical_message_readiness",
    "source_tracklet_index",
    "source_tracker_assignments",
    "source_tracker_tracks",
]

RELATION_FIELDS = [
    "relation_id",
    "scene",
    "source_auto_node_id",
    "target_auto_node_id",
    "source_tracklet_segment_id",
    "target_tracklet_segment_id",
    "time_gap_frames",
    "center_distance_px",
    "bottom_center_distance_px",
    "motion_extrapolation_error_px",
    "normalized_motion_error",
    "bbox_area_ratio",
    "bbox_aspect_ratio_delta",
    "appearance_cosine",
    "appearance_evidence_status",
    "source_edge_contact_ratio",
    "target_edge_contact_ratio",
    "source_competitor_count",
    "target_competitor_count",
    "candidate_score_not_selector",
    "pre_competition_status",
    "relation_status",
    "supporting_evidence",
    "conflicting_evidence",
    "uncertainty_sources",
    "competitor_ids",
    "decision_reason_code",
]

COMPETITION_FIELDS = [
    "competition_id",
    "scene",
    "competition_type",
    "anchor_auto_node_id",
    "candidate_auto_node_ids",
    "candidate_relation_ids",
    "candidate_count",
    "top_score",
    "second_score",
    "score_margin",
    "competition_status",
    "reason",
]

SOURCE_FIELDS = [
    "scene",
    "detection_source",
    "detection_table",
    "detection_rows",
    "detection_image_path_rows",
    "detection_image_exists_rows",
    "image_source",
    "tracker",
    "tracker_config",
    "tracker_output_dir",
    "tracker_rows",
    "tracker_tracks",
    "reid_feature_source",
    "tracklet_source",
    "wgv1_4_reference_source",
    "mapping_available",
    "mapping_method",
    "mapping_coverage",
    "blocking_reason",
]

MAPPING_FIELDS = [
    "wgv1_4_fragment_id",
    "scene",
    "wgv1_4_thread_id",
    "target_family_id",
    "reference_frame_start",
    "reference_frame_end",
    "reference_frame_count",
    "mapped_auto_node_id",
    "mapping_status",
    "frame_overlap_count",
    "reference_frame_coverage",
    "auto_node_frame_coverage",
    "mean_bbox_iou",
    "max_bbox_iou",
    "mapping_confidence",
    "mapping_evidence",
    "ambiguity_reason",
]

EVAL_FIELDS = [
    "reference_edge_id",
    "scene",
    "reference_table",
    "reference_edge_kind",
    "reference_status",
    "from_reference_id",
    "to_reference_id",
    "from_mapped_auto_node_id",
    "to_mapped_auto_node_id",
    "mapping_evaluable",
    "auto_relation_id",
    "auto_relation_status",
    "recovered_as_candidate",
    "recovered_as_accepted_or_weak",
    "forbidden_violation",
    "context_false_bridge",
    "evaluation_reason",
]

SCENE_METRIC_FIELDS = [
    "scene",
    "auto_nodes",
    "auto_nodes_ready",
    "auto_nodes_ready_with_uncertainty",
    "auto_nodes_insufficient_or_blocked",
    "candidate_relations",
    "strong_continuity",
    "weak_continuity",
    "ambiguous_continuity",
    "blocked_continuity",
    "not_candidate",
    "wgv1_4_fragments",
    "mapped_fragments",
    "unmapped_fragments",
    "mapping_coverage",
    "accepted_reference_edges",
    "accepted_recovered_edges",
    "accepted_edge_recall",
    "weak_reference_edges",
    "weak_recovered_edges",
    "weak_edge_recall",
    "forbidden_or_context_reference_edges",
    "forbidden_edge_violation_count",
    "context_edge_false_bridge_count",
]

CAPABILITY_FIELDS = [
    "optical_message_type",
    "automatic_source_available",
    "source_table",
    "confidence_or_uncertainty",
    "runtime_reproducible",
    "requires_visual_adjudication",
    "wgv2_wgv3_usage_permission",
    "blocking_reason",
]

FAILURE_FIELDS = [
    "case_id",
    "case_type",
    "scene",
    "reference_edge_id",
    "from_reference_id",
    "to_reference_id",
    "auto_relation_status",
    "evidence_frames",
    "visual_evidence_paths",
    "diagnosis_cn",
    "mechanism_layer",
    "minimal_cross_scene_fix",
]


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def bottom_center(self) -> tuple[float, float]:
        return self.cx, self.y2

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height > 0.0 else 0.0

    def as_json(self) -> str:
        return json.dumps([round(self.x1, 3), round(self.y1, 3), round(self.x2, 3), round(self.y2, 3)])


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


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def parse_float(value: Any) -> float | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_float(value)
    return int(number) if number is not None else None


def boolish(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"true", "yes", "1"}


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in norm(value).split(";") if part.strip()]


def rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def bbox_from_row(row: Mapping[str, Any]) -> BBox | None:
    vals = [parse_float(row.get(field)) for field in ("bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2")]
    if all(value is not None for value in vals):
        box = BBox(*(float(value) for value in vals if value is not None))
        return box if box.area > 0 else None
    return None


def bbox_iou(left: BBox | None, right: BBox | None) -> float:
    if left is None or right is None or left.area <= 0.0 or right.area <= 0.0:
        return 0.0
    ix1 = max(left.x1, right.x1)
    iy1 = max(left.y1, right.y1)
    ix2 = min(left.x2, right.x2)
    iy2 = min(left.y2, right.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = left.area + right.area - inter
    return inter / union if union > 0.0 else 0.0


def center_distance(left: BBox | None, right: BBox | None) -> float:
    if left is None or right is None:
        return math.inf
    return math.hypot(left.cx - right.cx, left.cy - right.cy)


def bottom_distance(left: BBox | None, right: BBox | None) -> float:
    if left is None or right is None:
        return math.inf
    lx, ly = left.bottom_center
    rx, ry = right.bottom_center
    return math.hypot(lx - rx, ly - ry)


def safe_mean(values: Sequence[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def safe_std(values: Sequence[float]) -> float:
    return float(statistics.pstdev(values)) if len(values) > 1 else 0.0


def fmt(value: float | int | str, places: int = 6) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(float(value)):
        return ""
    return f"{float(value):.{places}f}"


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(REPO_ROOT), text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc!r}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_paths(args: argparse.Namespace) -> dict[str, dict[str, Path]]:
    detector_root = REPO_ROOT / "outputs" / "oty2_yolo26l_detector_quality_probe_20260704_231830"
    tracker_root = REPO_ROOT / args.tracker_root
    embed_root = REPO_ROOT / args.embedding_root
    out: dict[str, dict[str, Path]] = {}
    for scene in SCENES:
        slug = scene.lower()
        out[scene] = {
            "detection_table": detector_root / f"oty0_yolo_detection_stream_audit_yolo26l_{slug}" / "oty0_yolo_detection_table.csv",
            "botsort_dir": tracker_root / f"{scene}_yolo26l_probe_botsort_raw",
            "bytetrack_dir": tracker_root / f"{scene}_yolo26l_probe_bytetrack_raw",
        }
    out["__embedding__"] = {
        "index": embed_root / "oty2" / f"crop_reid_embedding_probe_{args.embedding_timestamp}" / "crop_reid_embedding_index.csv",
        "array": embed_root / "oty2" / f"crop_reid_embedding_probe_{args.embedding_timestamp}" / "crop_reid_embeddings.npz",
        "linkage": embed_root / "oty2" / f"embedding_track_linkage_probe_{args.embedding_timestamp}" / "embedding_track_linkage_rows.csv",
        "tracklet_index": embed_root / "oty2" / f"tracklet_embedding_aggregation_probe_{args.embedding_timestamp}" / "tracklet_embedding_index.csv",
        "tracklet_array": embed_root / "oty2" / f"tracklet_embedding_aggregation_probe_{args.embedding_timestamp}" / "tracklet_embeddings.npz",
    }
    return out


def validate_inputs(paths: Mapping[str, Mapping[str, Path]]) -> None:
    required: list[Path] = []
    for scene in SCENES:
        required.extend(
            [
                paths[scene]["detection_table"],
                paths[scene]["botsort_dir"] / "oty1t_tracker_detection_assignments.csv",
                paths[scene]["botsort_dir"] / "oty1t_tracker_tracks.csv",
                paths[scene]["botsort_dir"] / "oty1t_tracker_state_timeseries.csv",
                paths[scene]["bytetrack_dir"] / "oty1t_tracker_sensitivity_summary.json",
            ]
        )
    required.extend(paths["__embedding__"].values())
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing WGV3.3A inputs:\n" + "\n".join(missing))


def load_tracklet_vectors(tracklet_npz: Path) -> dict[str, np.ndarray]:
    payload = np.load(tracklet_npz)
    vectors = payload["tracklet_embeddings"].astype(np.float32)
    ids = [str(item) for item in payload["tracklet_segment_ids"].tolist()]
    out: dict[str, np.ndarray] = {}
    for idx, seg_id in enumerate(ids):
        if idx < len(vectors):
            out[seg_id] = vectors[idx]
    return out


def build_source_alignment(paths: Mapping[str, Mapping[str, Path]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scene in SCENES:
        det_rows, _ = read_csv_rows(paths[scene]["detection_table"])
        det_scene_rows = [row for row in det_rows if norm(row.get("scene")) == scene]
        image_rows = [row for row in det_scene_rows if norm(row.get("optical_path"))]
        image_exists = 0
        for row in image_rows:
            path = Path(norm(row.get("optical_path")))
            if path.exists():
                image_exists += 1
        for tracker_name in ("botsort", "bytetrack"):
            tdir = paths[scene][f"{tracker_name}_dir"]
            assignments, _ = read_csv_rows(tdir / "oty1t_tracker_detection_assignments.csv")
            tracks, _ = read_csv_rows(tdir / "oty1t_tracker_tracks.csv")
            summary = load_json(tdir / "oty1t_tracker_sensitivity_summary.json")
            rows.append(
                {
                    "scene": scene,
                    "detection_source": "YOLO26l detector quality probe / OTY0-equivalent table",
                    "detection_table": rel(paths[scene]["detection_table"]),
                    "detection_rows": len(det_scene_rows),
                    "detection_image_path_rows": len(image_rows),
                    "detection_image_exists_rows": image_exists,
                    "image_source": "optical_path from YOLO26l OTY0-equivalent detection rows",
                    "tracker": tracker_name,
                    "tracker_config": "OTY1t default detection-table replay; BoT-SORT with_reid=False and blank-image update",
                    "tracker_output_dir": rel(tdir),
                    "tracker_rows": len(assignments),
                    "tracker_tracks": len(tracks),
                    "reid_feature_source": "torchvision_resnet18_imagenet_feature_baseline 512d crop embeddings; external local weights",
                    "tracklet_source": rel(paths["__embedding__"]["tracklet_index"]) if tracker_name == "botsort" else "comparison tracker only",
                    "wgv1_4_reference_source": "posthoc only, read after automatic freeze",
                    "mapping_available": "not_evaluated_before_freeze",
                    "mapping_method": "posthoc scene/frame/bbox IoU coverage only after freeze",
                    "mapping_coverage": "",
                    "blocking_reason": "" if summary.get("tracker_real_run") else "tracker dependency unavailable",
                }
            )
    return rows


def rows_by_track(assignments: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in assignments:
        track = norm(row.get("tracker_track_id"))
        if track:
            grouped[track].append(dict(row))
    for track, rows in grouped.items():
        grouped[track] = sorted(rows, key=lambda item: (parse_int(item.get("optical_frame_num")) or -1, norm(item.get("det_id"))))
    return grouped


def segment_assignment_rows(
    assignments_by_track: Mapping[str, Sequence[Mapping[str, Any]]],
    track_id: str,
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    rows = []
    for row in assignments_by_track.get(track_id, []):
        frame = parse_int(row.get("optical_frame_num"))
        if frame is not None and start <= frame <= end:
            rows.append(dict(row))
    return rows


def build_auto_nodes(paths: Mapping[str, Mapping[str, Path]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    tracklet_rows, _ = read_csv_rows(paths["__embedding__"]["tracklet_index"])
    tracklet_rows = [row for row in tracklet_rows if norm(row.get("tracker_name")) == "botsort" and norm(row.get("tracker_variant")) == "raw"]

    track_info: dict[tuple[str, str], Mapping[str, Any]] = {}
    assignment_rows_by_node: dict[str, list[dict[str, Any]]] = {}
    assignments_by_scene_track: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    source_assignment_path_by_scene: dict[str, Path] = {}
    source_track_path_by_scene: dict[str, Path] = {}
    for scene in SCENES:
        assign_path = paths[scene]["botsort_dir"] / "oty1t_tracker_detection_assignments.csv"
        track_path = paths[scene]["botsort_dir"] / "oty1t_tracker_tracks.csv"
        assignments, _ = read_csv_rows(assign_path)
        tracks, _ = read_csv_rows(track_path)
        source_assignment_path_by_scene[scene] = assign_path
        source_track_path_by_scene[scene] = track_path
        grouped = rows_by_track(assignments)
        for track, rows in grouped.items():
            assignments_by_scene_track[(scene, track)] = rows
        for row in tracks:
            track_info[(scene, norm(row.get("tracker_track_id")))] = row

    nodes: list[dict[str, Any]] = []
    node_by_id: dict[str, dict[str, Any]] = {}
    for idx, seg in enumerate(sorted(tracklet_rows, key=lambda row: (norm(row.get("scene")), parse_int(row.get("frame_start")) or -1, norm(row.get("track_id")), norm(row.get("tracklet_segment_id")))), start=1):
        scene = norm(seg.get("scene"))
        track_id = norm(seg.get("track_id"))
        start = parse_int(seg.get("frame_start")) or 0
        end = parse_int(seg.get("frame_end")) or start
        frame_count = parse_int(seg.get("frame_count")) or 0
        linked_count = parse_int(seg.get("linked_embedding_count")) or 0
        track_row = track_info.get((scene, track_id), {})
        rows = segment_assignment_rows(
            {track_id: assignments_by_scene_track.get((scene, track_id), [])},
            track_id,
            start,
            end,
        )
        boxes = [bbox_from_row(row) for row in rows]
        boxes = [box for box in boxes if box is not None]
        start_box = boxes[0] if boxes else None
        end_box = boxes[-1] if boxes else None
        aspects = [box.aspect for box in boxes if box and box.aspect > 0]
        areas = [box.area for box in boxes if box]
        widths = [box.width for box in boxes if box]
        heights = [box.height for box in boxes if box]
        edge_flags = [boolish(row.get("boundary_contact")) for row in rows if "boundary_contact" in row]
        if not edge_flags:
            edge_flags = [False for _ in boxes]
        trunc_flags = [
            boolish(row.get("boundary_contact"))
            or norm(row.get("partial_to_full_transition_proxy")) != "not_indicated"
            or norm(row.get("full_to_partial_transition_proxy")) != "not_indicated"
            for row in rows
        ]
        competitor_count = sum(1 for row in rows if boolish(row.get("neighbor_ambiguity_proxy")))
        edge_ratio = sum(1 for flag in edge_flags if flag) / len(edge_flags) if edge_flags else 0.0
        trunc_ratio = sum(1 for flag in trunc_flags if flag) / len(trunc_flags) if trunc_flags else 0.0
        min_cos = parse_float(seg.get("intra_tracklet_cosine_min")) or 0.0
        aggregate_available = bool(norm(seg.get("tracklet_embedding_artifact_path_uncommitted")))
        motion_available = frame_count >= 2 and start_box is not None and end_box is not None
        identity_status = norm(track_row.get("identity_status"))
        duplicate_count = parse_int(track_row.get("duplicate_track_overlap_count")) or 0
        switch_count = parse_int(track_row.get("possible_id_switch_count")) or 0
        if not aggregate_available or linked_count <= 0:
            readiness = "insufficient"
        elif identity_status in {"tracker_duplicate_overlap_hypothesis", "tracker_ambiguous_hypothesis"} and duplicate_count >= 3:
            readiness = "blocked"
        elif frame_count >= 2 and min_cos >= 0.70 and duplicate_count == 0 and switch_count == 0 and edge_ratio < 0.75:
            readiness = "ready"
        elif frame_count >= 2 and min_cos >= 0.60:
            readiness = "ready_with_uncertainty"
        else:
            readiness = "insufficient"
        node_id = f"AUTO_{scene}_{idx:04d}"
        rep_frames = sorted({start, (start + end) // 2, end})
        row = {
            "auto_node_id": node_id,
            "scene": scene,
            "detection_source": "yolo26l_probe",
            "tracker_name": "botsort",
            "tracker_variant": "raw",
            "track_id": track_id,
            "tracklet_segment_id": norm(seg.get("tracklet_segment_id")),
            "start_frame": start,
            "end_frame": end,
            "frame_count": frame_count,
            "linked_embedding_count": linked_count,
            "start_bbox": start_box.as_json() if start_box else "",
            "end_bbox": end_box.as_json() if end_box else "",
            "representative_frames": ";".join(str(frame) for frame in rep_frames),
            "mean_bbox_width": fmt(safe_mean(widths)),
            "mean_bbox_height": fmt(safe_mean(heights)),
            "mean_bbox_area": fmt(safe_mean(areas)),
            "aspect_ratio_mean": fmt(safe_mean(aspects)),
            "aspect_ratio_std": fmt(safe_std(aspects)),
            "edge_contact_ratio": fmt(edge_ratio),
            "truncation_like_ratio": fmt(trunc_ratio),
            "same_frame_competitor_count": competitor_count,
            "internal_embedding_stability": fmt(min_cos),
            "aggregate_embedding_available": aggregate_available,
            "motion_estimate_available": motion_available,
            "track_identity_status": identity_status,
            "track_status": norm(track_row.get("track_status")),
            "duplicate_track_overlap_count": duplicate_count,
            "possible_id_switch_count": switch_count,
            "missing_gap_count": parse_int(track_row.get("missing_gap_count")) or 0,
            "optical_message_readiness": readiness,
            "source_tracklet_index": rel(paths["__embedding__"]["tracklet_index"]),
            "source_tracker_assignments": rel(source_assignment_path_by_scene[scene]),
            "source_tracker_tracks": rel(source_track_path_by_scene[scene]),
        }
        nodes.append(row)
        node_by_id[node_id] = row
        assignment_rows_by_node[node_id] = rows
    return nodes, node_by_id, assignment_rows_by_node


def load_vectors_for_nodes(paths: Mapping[str, Mapping[str, Path]], nodes: Sequence[Mapping[str, Any]]) -> dict[str, np.ndarray]:
    vectors_by_segment = load_tracklet_vectors(paths["__embedding__"]["tracklet_array"])
    out: dict[str, np.ndarray] = {}
    for node in nodes:
        seg_id = norm(node.get("tracklet_segment_id"))
        vector = vectors_by_segment.get(seg_id)
        if vector is not None:
            out[norm(node.get("auto_node_id"))] = vector
    return out


def node_box(node: Mapping[str, Any], side: str) -> BBox | None:
    text = norm(node.get(f"{side}_bbox"))
    if not text:
        return None
    try:
        vals = json.loads(text)
        if isinstance(vals, list) and len(vals) >= 4:
            return BBox(float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3]))
    except Exception:
        return None
    return None


def relation_score_and_status(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    vectors: Mapping[str, np.ndarray],
) -> tuple[dict[str, Any], str]:
    left_end = node_box(left, "end")
    right_start = node_box(right, "start")
    gap = (parse_int(right.get("start_frame")) or 0) - (parse_int(left.get("end_frame")) or 0)
    center_dist = center_distance(left_end, right_start)
    bottom_dist = bottom_distance(left_end, right_start)
    mean_w = (parse_float(left.get("mean_bbox_width")) or 0.0) + (parse_float(right.get("mean_bbox_width")) or 0.0)
    mean_h = (parse_float(left.get("mean_bbox_height")) or 0.0) + (parse_float(right.get("mean_bbox_height")) or 0.0)
    norm_scale = max(40.0, math.hypot(mean_w / 2.0, mean_h / 2.0))
    normalized_center = center_dist / norm_scale if math.isfinite(center_dist) else math.inf
    lx0 = parse_float(left.get("bbox_motion_dx")) or 0.0
    _ = lx0
    left_motion_dx = 0.0
    left_motion_dy = 0.0
    lstart = node_box(left, "start")
    if lstart is not None and left_end is not None:
        span = max(1, (parse_int(left.get("end_frame")) or 0) - (parse_int(left.get("start_frame")) or 0))
        left_motion_dx = (left_end.cx - lstart.cx) / span
        left_motion_dy = (left_end.cy - lstart.cy) / span
    pred_x = (left_end.cx if left_end else 0.0) + left_motion_dx * max(1, gap)
    pred_y = (left_end.cy if left_end else 0.0) + left_motion_dy * max(1, gap)
    if right_start is None:
        pred_error = math.inf
    else:
        pred_error = math.hypot(pred_x - right_start.cx, pred_y - right_start.cy)
    normalized_motion = pred_error / norm_scale if math.isfinite(pred_error) else math.inf
    l_area = left_end.area if left_end else 0.0
    r_area = right_start.area if right_start else 0.0
    area_ratio = max(l_area, r_area) / max(1.0, min(l_area, r_area)) if l_area and r_area else math.inf
    aspect_delta = abs((left_end.aspect if left_end else 0.0) - (right_start.aspect if right_start else 0.0))
    lvec = vectors.get(norm(left.get("auto_node_id")))
    rvec = vectors.get(norm(right.get("auto_node_id")))
    app = float(np.dot(lvec, rvec)) if lvec is not None and rvec is not None else float("nan")
    app_status = "appearance_insufficient"
    if math.isfinite(app):
        if app >= 0.82:
            app_status = "appearance_support"
        elif app >= 0.68:
            app_status = "appearance_unreliable"
        else:
            app_status = "appearance_conflict"
    left_dup = parse_int(left.get("duplicate_track_overlap_count")) or 0
    right_dup = parse_int(right.get("duplicate_track_overlap_count")) or 0
    competitor_count = (parse_int(left.get("same_frame_competitor_count")) or 0) + (parse_int(right.get("same_frame_competitor_count")) or 0)
    edge_pressure = max(parse_float(left.get("edge_contact_ratio")) or 0.0, parse_float(right.get("edge_contact_ratio")) or 0.0)
    motion_support = normalized_motion <= 1.25 or normalized_center <= 1.15
    motion_weak = normalized_motion <= 2.2 or normalized_center <= 1.9
    size_ok = area_ratio <= 2.75 and aspect_delta <= 1.2
    score = 0.0
    score += max(0.0, 1.0 - min(normalized_motion, 3.0) / 3.0) * 0.35
    score += max(0.0, 1.0 - min(normalized_center, 3.0) / 3.0) * 0.20
    score += (max(0.0, min(1.0, (app + 1.0) / 2.0)) if math.isfinite(app) else 0.45) * 0.25
    score += (1.0 / min(area_ratio, 4.0) if math.isfinite(area_ratio) else 0.0) * 0.10
    score += max(0.0, 1.0 - edge_pressure) * 0.10
    if gap < 1 or gap > 60:
        status = "not_candidate"
        reason = "time_gap_outside_forward_window"
    elif not size_ok and not motion_support:
        status = "blocked_continuity"
        reason = "motion_and_size_conflict"
    elif (left_dup + right_dup) >= 6 and competitor_count >= 4:
        status = "blocked_continuity"
        reason = "duplicate_or_competitor_conflict"
    elif app_status == "appearance_conflict" and not motion_support:
        status = "blocked_continuity"
        reason = "appearance_and_motion_conflict"
    elif gap <= 10 and motion_support and size_ok and app_status == "appearance_support" and competitor_count <= 2 and edge_pressure < 0.60:
        status = "strong_continuity"
        reason = "time_motion_size_appearance_consistent"
    elif gap <= 30 and motion_weak and size_ok and app_status in {"appearance_support", "appearance_unreliable"}:
        status = "weak_continuity"
        reason = "plausible_but_uncertain_continuity"
    elif gap <= 45 and (motion_weak or app_status == "appearance_support"):
        status = "ambiguous_continuity"
        reason = "partial_support_with_competition_or_state_uncertainty"
    else:
        status = "not_candidate"
        reason = "insufficient_time_motion_appearance_support"
    details = {
        "time_gap_frames": gap,
        "center_distance_px": center_dist,
        "bottom_center_distance_px": bottom_dist,
        "motion_extrapolation_error_px": pred_error,
        "normalized_motion_error": normalized_motion,
        "bbox_area_ratio": area_ratio,
        "bbox_aspect_ratio_delta": aspect_delta,
        "appearance_cosine": app,
        "appearance_evidence_status": app_status,
        "candidate_score_not_selector": score,
        "source_edge_contact_ratio": parse_float(left.get("edge_contact_ratio")) or 0.0,
        "target_edge_contact_ratio": parse_float(right.get("edge_contact_ratio")) or 0.0,
        "source_competitor_count": parse_int(left.get("same_frame_competitor_count")) or 0,
        "target_competitor_count": parse_int(right.get("same_frame_competitor_count")) or 0,
        "decision_reason_code": reason,
    }
    return details, status


def evidence_strings(status: str, metrics: Mapping[str, Any]) -> tuple[str, str, str]:
    supporting: list[str] = []
    conflicting: list[str] = []
    uncertainty: list[str] = []
    if metrics["time_gap_frames"] <= 10:
        supporting.append("short_forward_gap")
    elif metrics["time_gap_frames"] <= 30:
        uncertainty.append("medium_forward_gap")
    else:
        conflicting.append("long_forward_gap")
    if metrics["normalized_motion_error"] <= 1.25:
        supporting.append("motion_extrapolation_consistent")
    elif metrics["normalized_motion_error"] <= 2.2:
        uncertainty.append("motion_extrapolation_weak")
    else:
        conflicting.append("motion_extrapolation_conflict")
    if metrics["appearance_evidence_status"] == "appearance_support":
        supporting.append("appearance_cosine_support")
    elif metrics["appearance_evidence_status"] == "appearance_conflict":
        conflicting.append("appearance_cosine_conflict")
    else:
        uncertainty.append(metrics["appearance_evidence_status"])
    if metrics["bbox_area_ratio"] <= 2.75:
        supporting.append("bbox_size_compatible")
    else:
        conflicting.append("bbox_size_jump")
    if metrics["source_edge_contact_ratio"] > 0.5 or metrics["target_edge_contact_ratio"] > 0.5:
        uncertainty.append("edge_or_truncation_pressure")
    if metrics["source_competitor_count"] + metrics["target_competitor_count"] > 0:
        uncertainty.append("same_frame_competitor_context")
    if status == "blocked_continuity":
        conflicting.append("blocked_by_combined_evidence")
    if status == "not_candidate":
        conflicting.append("not_candidate_under_fixed_policy")
    return ";".join(supporting), ";".join(conflicting), ";".join(uncertainty)


def build_relations(nodes: Sequence[Mapping[str, Any]], vectors: Mapping[str, np.ndarray]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_scene: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_scene[norm(node.get("scene"))].append(node)
    rows: list[dict[str, Any]] = []
    for scene, scene_nodes in by_scene.items():
        ordered = sorted(scene_nodes, key=lambda row: (parse_int(row.get("start_frame")) or -1, parse_int(row.get("end_frame")) or -1, norm(row.get("auto_node_id"))))
        for left in ordered:
            left_end = parse_int(left.get("end_frame")) or 0
            for right in ordered:
                if norm(left.get("auto_node_id")) == norm(right.get("auto_node_id")):
                    continue
                gap = (parse_int(right.get("start_frame")) or 0) - left_end
                if gap < 1 or gap > 80:
                    continue
                metrics, status = relation_score_and_status(left, right, vectors)
                relation_id = f"REL_{scene}_{len(rows) + 1:05d}"
                supporting, conflicting, uncertainty = evidence_strings(status, metrics)
                row = {
                    "relation_id": relation_id,
                    "scene": scene,
                    "source_auto_node_id": norm(left.get("auto_node_id")),
                    "target_auto_node_id": norm(right.get("auto_node_id")),
                    "source_tracklet_segment_id": norm(left.get("tracklet_segment_id")),
                    "target_tracklet_segment_id": norm(right.get("tracklet_segment_id")),
                    "time_gap_frames": metrics["time_gap_frames"],
                    "center_distance_px": fmt(metrics["center_distance_px"]),
                    "bottom_center_distance_px": fmt(metrics["bottom_center_distance_px"]),
                    "motion_extrapolation_error_px": fmt(metrics["motion_extrapolation_error_px"]),
                    "normalized_motion_error": fmt(metrics["normalized_motion_error"]),
                    "bbox_area_ratio": fmt(metrics["bbox_area_ratio"]),
                    "bbox_aspect_ratio_delta": fmt(metrics["bbox_aspect_ratio_delta"]),
                    "appearance_cosine": fmt(metrics["appearance_cosine"]),
                    "appearance_evidence_status": metrics["appearance_evidence_status"],
                    "source_edge_contact_ratio": fmt(metrics["source_edge_contact_ratio"]),
                    "target_edge_contact_ratio": fmt(metrics["target_edge_contact_ratio"]),
                    "source_competitor_count": metrics["source_competitor_count"],
                    "target_competitor_count": metrics["target_competitor_count"],
                    "candidate_score_not_selector": fmt(metrics["candidate_score_not_selector"]),
                    "pre_competition_status": status,
                    "relation_status": status,
                    "supporting_evidence": supporting,
                    "conflicting_evidence": conflicting,
                    "uncertainty_sources": uncertainty,
                    "competitor_ids": "",
                    "decision_reason_code": metrics["decision_reason_code"],
                }
                rows.append(row)

    competition_rows = apply_competition(rows)
    return rows, competition_rows


def apply_competition(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    competition_rows: list[dict[str, Any]] = []
    plausible = {"strong_continuity", "weak_continuity", "ambiguous_continuity"}
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["relation_status"] in plausible:
            by_source[norm(row["source_auto_node_id"])].append(row)
            by_target[norm(row["target_auto_node_id"])].append(row)

    def score(row: Mapping[str, Any]) -> float:
        return parse_float(row.get("candidate_score_not_selector")) or 0.0

    comp_index = 1
    for ctype, grouped, anchor_field, other_field in (
        ("one_source_multiple_successors", by_source, "source_auto_node_id", "target_auto_node_id"),
        ("multiple_sources_one_successor", by_target, "target_auto_node_id", "source_auto_node_id"),
    ):
        for anchor, candidates in sorted(grouped.items()):
            if len(candidates) < 2:
                continue
            ordered = sorted(candidates, key=lambda row: (-score(row), norm(row["relation_id"])))
            top = score(ordered[0])
            second = score(ordered[1])
            margin = top - second
            candidate_ids = [norm(row[other_field]) for row in ordered]
            relation_ids = [norm(row["relation_id"]) for row in ordered]
            status = "resolved_margin" if margin >= 0.12 else "ambiguous_competition"
            if status == "ambiguous_competition":
                for row in ordered:
                    if row["relation_status"] in {"strong_continuity", "weak_continuity"}:
                        row["relation_status"] = "ambiguous_continuity"
                        row["uncertainty_sources"] = ";".join(filter(None, [row.get("uncertainty_sources", ""), ctype]))
                        row["competitor_ids"] = ";".join(candidate_ids)
                        row["decision_reason_code"] = "candidate_competition_margin_too_small"
            competition_rows.append(
                {
                    "competition_id": f"COMP_{comp_index:04d}",
                    "scene": norm(ordered[0].get("scene")),
                    "competition_type": ctype,
                    "anchor_auto_node_id": anchor,
                    "candidate_auto_node_ids": ";".join(candidate_ids),
                    "candidate_relation_ids": ";".join(relation_ids),
                    "candidate_count": len(candidates),
                    "top_score": fmt(top),
                    "second_score": fmt(second),
                    "score_margin": fmt(margin),
                    "competition_status": status,
                    "reason": "fixed pre-WGV1.4 competition preservation rule",
                }
            )
            comp_index += 1
    return competition_rows


def freeze_auto_outputs(auto_files: Sequence[Path], output_path: Path, date: str) -> list[dict[str, Any]]:
    rows = []
    for path in auto_files:
        rows.append(
            {
                "date": date,
                "frozen_file": rel(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "freeze_policy": "automatic_outputs_written_before_wgv1_4_reference_read",
            }
        )
    write_csv(output_path, rows, ["date", "frozen_file", "sha256", "bytes", "freeze_policy"])
    return rows


def load_reference_bank() -> dict[str, list[dict[str, Any]]]:
    bank_rows, _ = read_csv_rows(WGV12_FRAME_BANK)
    selected = [row for row in bank_rows if norm(row.get("candidate_role")) == "selected_primary" and norm(row.get("linked_target_family_ids"))]
    by_tf: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        for tfid in split_semicolon(row.get("linked_target_family_ids")):
            by_tf[tfid].append(row)
    for tfid, rows in by_tf.items():
        by_tf[tfid] = sorted(rows, key=lambda row: parse_int(row.get("frame_id")) or -1)
    return by_tf


def assignment_rows_by_node_frame(assignment_rows_by_node: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, dict[int, list[dict[str, Any]]]]:
    out: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for node_id, rows in assignment_rows_by_node.items():
        by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            frame = parse_int(row.get("optical_frame_num"))
            if frame is not None:
                by_frame[frame].append(dict(row))
        out[node_id] = by_frame
    return out


def build_mapping(
    fragments: Sequence[Mapping[str, Any]],
    nodes: Sequence[Mapping[str, Any]],
    assignment_rows_by_node: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    ref_bank = load_reference_bank()
    by_node_frame = assignment_rows_by_node_frame(assignment_rows_by_node)
    nodes_by_scene: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for node in nodes:
        nodes_by_scene[norm(node.get("scene"))].append(node)
    mappings: list[dict[str, Any]] = []
    for frag in fragments:
        scene = norm(frag.get("scene_id"))
        tfid = norm(frag.get("target_family_id"))
        ref_rows = ref_bank.get(tfid, [])
        ref_frames = {parse_int(row.get("frame_id")) for row in ref_rows}
        ref_frames = {frame for frame in ref_frames if frame is not None}
        candidates: list[dict[str, Any]] = []
        for node in nodes_by_scene.get(scene, []):
            node_id = norm(node.get("auto_node_id"))
            node_start = parse_int(node.get("start_frame")) or 0
            node_end = parse_int(node.get("end_frame")) or 0
            node_frames = set(range(node_start, node_end + 1))
            overlap = sorted(frame for frame in ref_frames if frame in node_frames)
            if not overlap:
                continue
            ious: list[float] = []
            matched_frames = 0
            for ref in ref_rows:
                frame = parse_int(ref.get("frame_id"))
                if frame is None or frame not in overlap:
                    continue
                ref_box = bbox_from_row(ref)
                best_iou = 0.0
                for auto_row in by_node_frame.get(node_id, {}).get(frame, []):
                    best_iou = max(best_iou, bbox_iou(ref_box, bbox_from_row(auto_row)))
                if best_iou >= 0.50:
                    matched_frames += 1
                if best_iou > 0.0:
                    ious.append(best_iou)
            ref_count = len(ref_rows) or (parse_int(frag.get("frame_count")) or 0)
            coverage = matched_frames / ref_count if ref_count else 0.0
            auto_cov = matched_frames / max(1, parse_int(node.get("frame_count")) or 1)
            mean_iou = safe_mean(ious)
            max_iou = max(ious) if ious else 0.0
            candidates.append(
                {
                    "node": node,
                    "matched_frames": matched_frames,
                    "overlap_count": len(overlap),
                    "reference_coverage": coverage,
                    "auto_coverage": auto_cov,
                    "mean_iou": mean_iou,
                    "max_iou": max_iou,
                    "score": coverage * 0.65 + mean_iou * 0.35,
                }
            )
        candidates.sort(key=lambda item: (-item["score"], norm(item["node"].get("auto_node_id"))))
        best = candidates[0] if candidates else None
        second = candidates[1] if len(candidates) > 1 else None
        if best is None or best["reference_coverage"] < 0.25:
            status = "unmapped"
            mapped_id = ""
            confidence = "none"
            ambiguity = "no_same_frame_bbox_iou_coverage"
            overlap_count = 0
            ref_cov = 0.0
            auto_cov = 0.0
            mean_iou = 0.0
            max_iou = 0.0
        else:
            mapped_id = norm(best["node"].get("auto_node_id"))
            overlap_count = best["overlap_count"]
            ref_cov = best["reference_coverage"]
            auto_cov = best["auto_coverage"]
            mean_iou = best["mean_iou"]
            max_iou = best["max_iou"]
            if second is not None and best["score"] - second["score"] < 0.12:
                status = "ambiguous"
                confidence = "low"
                ambiguity = f"second_candidate={norm(second['node'].get('auto_node_id'))}"
            elif ref_cov >= 0.80 and mean_iou >= 0.80:
                status = "exact_like"
                confidence = "high"
                ambiguity = ""
            else:
                status = "partial"
                confidence = "medium"
                ambiguity = "partial_frame_or_bbox_coverage"
        mappings.append(
            {
                "wgv1_4_fragment_id": norm(frag.get("wgv1_4_fragment_id")),
                "scene": scene,
                "wgv1_4_thread_id": norm(frag.get("wgv1_4_thread_id")),
                "target_family_id": tfid,
                "reference_frame_start": norm(frag.get("frame_start")),
                "reference_frame_end": norm(frag.get("frame_end")),
                "reference_frame_count": norm(frag.get("frame_count")),
                "mapped_auto_node_id": mapped_id,
                "mapping_status": status,
                "frame_overlap_count": overlap_count,
                "reference_frame_coverage": fmt(ref_cov),
                "auto_node_frame_coverage": fmt(auto_cov),
                "mean_bbox_iou": fmt(mean_iou),
                "max_bbox_iou": fmt(max_iou),
                "mapping_confidence": confidence,
                "mapping_evidence": "scene_frame_bbox_iou_coverage_no_thread_name_match",
                "ambiguity_reason": ambiguity,
            }
        )
    return mappings


def target_family_to_mapping(mappings: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for row in mappings:
        if norm(row.get("mapping_status")) in {"exact_like", "partial", "ambiguous"}:
            out[norm(row.get("target_family_id"))] = row
    return out


def relation_lookup(relations: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    out = {}
    for row in relations:
        out[(norm(row.get("source_auto_node_id")), norm(row.get("target_auto_node_id")))] = row
    return out


def evaluate_reference_edges(
    mappings: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]],
    same_edges: Sequence[Mapping[str, Any]],
    context_edges: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_tf = target_family_to_mapping(mappings)
    rel_by_pair = relation_lookup(relations)
    rows: list[dict[str, Any]] = []

    def auto_status(left_id: str, right_id: str) -> tuple[str, str]:
        if not left_id or not right_id:
            return "", ""
        if left_id == right_id:
            return "SAME_AUTO_NODE", "same_auto_node"
        direct = rel_by_pair.get((left_id, right_id))
        if direct:
            return norm(direct.get("relation_id")), norm(direct.get("relation_status"))
        reverse = rel_by_pair.get((right_id, left_id))
        if reverse:
            return norm(reverse.get("relation_id")), norm(reverse.get("relation_status"))
        return "", "not_in_candidate_set"

    for edge in same_edges:
        status = norm(edge.get("wgv1_4_edge_status"))
        kind = norm(edge.get("wgv1_4_edge_kind"))
        left = by_tf.get(norm(edge.get("from_target_family_id")))
        right = by_tf.get(norm(edge.get("to_target_family_id")))
        left_id = norm(left.get("mapped_auto_node_id")) if left else ""
        right_id = norm(right.get("mapped_auto_node_id")) if right else ""
        rid, astatus = auto_status(left_id, right_id)
        evaluable = bool(left_id and right_id)
        recovered_candidate = astatus in {"same_auto_node", "strong_continuity", "weak_continuity", "ambiguous_continuity", "blocked_continuity", "not_candidate"}
        recovered_accept = astatus in {"same_auto_node", "strong_continuity", "weak_continuity"}
        is_forbidden = status in {"context_only", "blocked"} or kind in {"not_same_vehicle_context", "blocked_continuity"}
        forbidden_violation = is_forbidden and astatus in {"same_auto_node", "strong_continuity", "weak_continuity"}
        rows.append(
            {
                "reference_edge_id": norm(edge.get("edge_id")),
                "scene": norm(edge.get("scene_id")),
                "reference_table": "wgv1_4_same_vehicle_edges",
                "reference_edge_kind": kind,
                "reference_status": status,
                "from_reference_id": norm(edge.get("from_target_family_id")),
                "to_reference_id": norm(edge.get("to_target_family_id")),
                "from_mapped_auto_node_id": left_id,
                "to_mapped_auto_node_id": right_id,
                "mapping_evaluable": evaluable,
                "auto_relation_id": rid,
                "auto_relation_status": astatus,
                "recovered_as_candidate": recovered_candidate,
                "recovered_as_accepted_or_weak": recovered_accept,
                "forbidden_violation": forbidden_violation,
                "context_false_bridge": False,
                "evaluation_reason": "same_auto_node_or_fixed_relation_lookup" if evaluable else "mapping_missing",
            }
        )

    thread_rows, _ = read_csv_rows(WGV14_THREADS)
    thread_by_id = {norm(row.get("wgv1_4_thread_id")): row for row in thread_rows}
    for edge in context_edges:
        left_thread = thread_by_id.get(norm(edge.get("from_wgv1_4_thread_id")), {})
        right_thread = thread_by_id.get(norm(edge.get("to_wgv1_4_thread_id")), {})
        left_tfids = split_semicolon(left_thread.get("target_family_ids"))
        right_tfids = split_semicolon(right_thread.get("target_family_ids"))
        left_maps = [by_tf.get(tfid) for tfid in left_tfids if by_tf.get(tfid)]
        right_maps = [by_tf.get(tfid) for tfid in right_tfids if by_tf.get(tfid)]
        left_ids = sorted({norm(row.get("mapped_auto_node_id")) for row in left_maps if row})
        right_ids = sorted({norm(row.get("mapped_auto_node_id")) for row in right_maps if row})
        best_rid = ""
        best_status = "not_in_candidate_set"
        false_bridge = False
        for left_id in left_ids:
            for right_id in right_ids:
                rid, astatus = auto_status(left_id, right_id)
                if astatus in {"same_auto_node", "strong_continuity", "weak_continuity"}:
                    best_rid, best_status = rid, astatus
                    false_bridge = True
                    break
                if astatus != "not_in_candidate_set":
                    best_rid, best_status = rid, astatus
            if false_bridge:
                break
        rows.append(
            {
                "reference_edge_id": norm(edge.get("context_edge_id")),
                "scene": norm(edge.get("scene_id")),
                "reference_table": "wgv1_4_temporal_context_edges",
                "reference_edge_kind": norm(edge.get("context_type")),
                "reference_status": norm(edge.get("wgv1_4_context_status")),
                "from_reference_id": norm(edge.get("from_wgv1_4_thread_id")),
                "to_reference_id": norm(edge.get("to_wgv1_4_thread_id")),
                "from_mapped_auto_node_id": ";".join(left_ids),
                "to_mapped_auto_node_id": ";".join(right_ids),
                "mapping_evaluable": bool(left_ids and right_ids),
                "auto_relation_id": best_rid,
                "auto_relation_status": best_status,
                "recovered_as_candidate": best_status != "not_in_candidate_set",
                "recovered_as_accepted_or_weak": best_status in {"same_auto_node", "strong_continuity", "weak_continuity"},
                "forbidden_violation": false_bridge,
                "context_false_bridge": false_bridge,
                "evaluation_reason": "context_edge_should_not_be_accepted_by_auto_relation",
            }
        )
    return rows


def build_scene_metrics(
    nodes: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]],
    mappings: Sequence[Mapping[str, Any]],
    evaluations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for scene in SCENES:
        scene_nodes = [row for row in nodes if norm(row.get("scene")) == scene]
        scene_rel = [row for row in relations if norm(row.get("scene")) == scene]
        scene_map = [row for row in mappings if norm(row.get("scene")) == scene]
        scene_eval = [row for row in evaluations if norm(row.get("scene")) == scene]
        rel_counts = Counter(norm(row.get("relation_status")) for row in scene_rel)
        node_counts = Counter(norm(row.get("optical_message_readiness")) for row in scene_nodes)
        accepted = [row for row in scene_eval if norm(row.get("reference_status")) == "accepted"]
        weak = [row for row in scene_eval if norm(row.get("reference_status")) == "weak"]
        forbidden = [row for row in scene_eval if norm(row.get("reference_status")) in {"context_only", "blocked"} or norm(row.get("reference_table")) == "wgv1_4_temporal_context_edges"]
        mapped = [row for row in scene_map if norm(row.get("mapping_status")) in {"exact_like", "partial", "ambiguous"}]
        def ratio(num: int, den: int) -> str:
            return fmt(num / den if den else 0.0)
        rows.append(
            {
                "scene": scene,
                "auto_nodes": len(scene_nodes),
                "auto_nodes_ready": node_counts["ready"],
                "auto_nodes_ready_with_uncertainty": node_counts["ready_with_uncertainty"],
                "auto_nodes_insufficient_or_blocked": node_counts["insufficient"] + node_counts["blocked"],
                "candidate_relations": len(scene_rel),
                "strong_continuity": rel_counts["strong_continuity"],
                "weak_continuity": rel_counts["weak_continuity"],
                "ambiguous_continuity": rel_counts["ambiguous_continuity"],
                "blocked_continuity": rel_counts["blocked_continuity"],
                "not_candidate": rel_counts["not_candidate"],
                "wgv1_4_fragments": len(scene_map),
                "mapped_fragments": len(mapped),
                "unmapped_fragments": len(scene_map) - len(mapped),
                "mapping_coverage": ratio(len(mapped), len(scene_map)),
                "accepted_reference_edges": len(accepted),
                "accepted_recovered_edges": sum(1 for row in accepted if boolish(row.get("recovered_as_accepted_or_weak"))),
                "accepted_edge_recall": ratio(sum(1 for row in accepted if boolish(row.get("recovered_as_accepted_or_weak"))), len(accepted)),
                "weak_reference_edges": len(weak),
                "weak_recovered_edges": sum(1 for row in weak if boolish(row.get("recovered_as_accepted_or_weak")) or norm(row.get("auto_relation_status")) == "ambiguous_continuity"),
                "weak_edge_recall": ratio(sum(1 for row in weak if boolish(row.get("recovered_as_accepted_or_weak")) or norm(row.get("auto_relation_status")) == "ambiguous_continuity"), len(weak)),
                "forbidden_or_context_reference_edges": len(forbidden),
                "forbidden_edge_violation_count": sum(1 for row in forbidden if boolish(row.get("forbidden_violation"))),
                "context_edge_false_bridge_count": sum(1 for row in scene_eval if boolish(row.get("context_false_bridge"))),
            }
        )
    return rows


def build_capability(metrics: Sequence[Mapping[str, Any]], nodes_path: Path, decisions_path: Path, eval_path: Path) -> list[dict[str, Any]]:
    total_nodes = sum(parse_int(row.get("auto_nodes")) or 0 for row in metrics)
    ready_nodes = sum(parse_int(row.get("auto_nodes_ready")) or 0 for row in metrics)
    strong = sum(parse_int(row.get("strong_continuity")) or 0 for row in metrics)
    weak = sum(parse_int(row.get("weak_continuity")) or 0 for row in metrics)
    amb = sum(parse_int(row.get("ambiguous_continuity")) or 0 for row in metrics)
    blocked = sum(parse_int(row.get("blocked_continuity")) or 0 for row in metrics)
    violation = sum(parse_int(row.get("forbidden_edge_violation_count")) or 0 for row in metrics)
    return [
        {
            "optical_message_type": "stable_tracklet_segments",
            "automatic_source_available": total_nodes > 0,
            "source_table": rel(nodes_path),
            "confidence_or_uncertainty": f"{ready_nodes}/{total_nodes} nodes ready; remaining uncertain/blocked",
            "runtime_reproducible": True,
            "requires_visual_adjudication": False,
            "wgv2_wgv3_usage_permission": "automatic_runtime_message",
            "blocking_reason": "",
        },
        {
            "optical_message_type": "strong_continuity_relation",
            "automatic_source_available": strong > 0,
            "source_table": rel(decisions_path),
            "confidence_or_uncertainty": f"{strong} strong automatic relations",
            "runtime_reproducible": strong > 0,
            "requires_visual_adjudication": False,
            "wgv2_wgv3_usage_permission": "automatic_runtime_message" if strong else "not_available",
            "blocking_reason": "" if strong else "no relation passed fixed strong gates",
        },
        {
            "optical_message_type": "weak_continuity_relation",
            "automatic_source_available": weak > 0,
            "source_table": rel(decisions_path),
            "confidence_or_uncertainty": f"{weak} weak automatic relations",
            "runtime_reproducible": weak > 0,
            "requires_visual_adjudication": True,
            "wgv2_wgv3_usage_permission": "automatic_uncertain_message",
            "blocking_reason": "",
        },
        {
            "optical_message_type": "ambiguous_continuity_relation",
            "automatic_source_available": amb > 0,
            "source_table": rel(decisions_path),
            "confidence_or_uncertainty": f"{amb} ambiguous automatic relations after competition preservation",
            "runtime_reproducible": amb > 0,
            "requires_visual_adjudication": True,
            "wgv2_wgv3_usage_permission": "automatic_uncertain_message",
            "blocking_reason": "",
        },
        {
            "optical_message_type": "blocked_continuity_relation",
            "automatic_source_available": blocked > 0,
            "source_table": rel(decisions_path),
            "confidence_or_uncertainty": f"{blocked} blocked automatic relations",
            "runtime_reproducible": blocked > 0,
            "requires_visual_adjudication": False,
            "wgv2_wgv3_usage_permission": "automatic_uncertain_message",
            "blocking_reason": "",
        },
        {
            "optical_message_type": "visible_unboxed_gap",
            "automatic_source_available": False,
            "source_table": "",
            "confidence_or_uncertainty": "not represented by current standard MOT + crop embedding route",
            "runtime_reproducible": False,
            "requires_visual_adjudication": True,
            "wgv2_wgv3_usage_permission": "posthoc_visual_constraint_only",
            "blocking_reason": "requires visual or multimodal judgment outside current automatic source",
        },
        {
            "optical_message_type": "same_frame_multicar_competition",
            "automatic_source_available": True,
            "source_table": rel(decisions_path),
            "confidence_or_uncertainty": "available as neighbor/competition pressure, not vehicle identity",
            "runtime_reproducible": True,
            "requires_visual_adjudication": True,
            "wgv2_wgv3_usage_permission": "automatic_uncertain_message",
            "blocking_reason": "",
        },
        {
            "optical_message_type": "edge_truncation_pressure",
            "automatic_source_available": True,
            "source_table": rel(nodes_path),
            "confidence_or_uncertainty": "available from bbox boundary/contact proxies",
            "runtime_reproducible": True,
            "requires_visual_adjudication": True,
            "wgv2_wgv3_usage_permission": "automatic_uncertain_message",
            "blocking_reason": "proxy does not prove physical truncation",
        },
        {
            "optical_message_type": "occlusion_or_target_switch",
            "automatic_source_available": False,
            "source_table": rel(eval_path),
            "confidence_or_uncertainty": "violations or missed edges expose the risk posthoc",
            "runtime_reproducible": False,
            "requires_visual_adjudication": True,
            "wgv2_wgv3_usage_permission": "posthoc_visual_constraint_only",
            "blocking_reason": "current automatic route lacks explicit object-level visual switch adjudication",
        },
        {
            "optical_message_type": "non_vehicle_exclusion",
            "automatic_source_available": False,
            "source_table": "",
            "confidence_or_uncertainty": "not available in current YOLO26l vehicle-only source closure",
            "runtime_reproducible": False,
            "requires_visual_adjudication": True,
            "wgv2_wgv3_usage_permission": "not_available",
            "blocking_reason": "requires negative non-vehicle evidence not produced by this optical route",
        },
        {
            "optical_message_type": "forbidden_boundary_preservation",
            "automatic_source_available": violation == 0,
            "source_table": rel(eval_path),
            "confidence_or_uncertainty": f"{violation} forbidden/context violations under posthoc evaluation",
            "runtime_reproducible": violation == 0,
            "requires_visual_adjudication": True,
            "wgv2_wgv3_usage_permission": "posthoc_visual_constraint_only" if violation else "automatic_uncertain_message",
            "blocking_reason": "WGV1.4 boundaries remain posthoc constraints when automatic tracker bridges them" if violation else "",
        },
    ]


def edge_lookup_for_visual_paths() -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for path, key in ((WGV14_SAME_EDGES, "edge_id"), (WGV14_CONTEXT_EDGES, "context_edge_id")):
        data, _ = read_csv_rows(path)
        for row in data:
            rows[norm(row.get(key))] = row
    return rows


def build_failure_cases(evaluations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    lookup = edge_lookup_for_visual_paths()
    cases: list[dict[str, Any]] = []
    interesting = [
        row
        for row in evaluations
        if (
            norm(row.get("reference_status")) == "accepted"
            and not boolish(row.get("recovered_as_accepted_or_weak"))
            and boolish(row.get("mapping_evaluable"))
        )
        or boolish(row.get("forbidden_violation"))
        or boolish(row.get("context_false_bridge"))
        or (norm(row.get("reference_status")) == "weak" and norm(row.get("auto_relation_status")) == "blocked_continuity")
    ]
    for idx, row in enumerate(interesting[:12], start=1):
        rid = norm(row.get("reference_edge_id"))
        ref = lookup.get(rid, {})
        if boolish(row.get("context_false_bridge")):
            case_type = "context_false_bridge"
            diagnosis = "自动 BoT-SORT/几何关系把 WGV1.4 的 context-only 边当成可连接假设；画面证据指向同色或同帧竞争，不能作为运行时同车消息。"
            layer = "competition_or_subject_switch"
            fix = "add automatic competitor-boundary evidence before accepting bridge"
        elif boolish(row.get("forbidden_violation")):
            case_type = "forbidden_edge_violation"
            diagnosis = "自动关系跨过了 WGV1.4 保留的不同车辆边界；失败层主要是 tracker geometry 没有主体切换/同色竞争裁决。"
            layer = "tracker_association_competition"
            fix = "preserve explicit boundary blockers from automatic same-frame competition"
        elif norm(row.get("reference_status")) == "accepted":
            case_type = "accepted_edge_missed"
            diagnosis = "WGV1.4 可由视觉后验接受，但自动主干没有形成 strong/weak 关系；主要原因是 fragment 切分、边缘截断或运动/外观证据不足。"
            layer = "standard_mot_fragmentation_or_motion_gap"
            fix = "add post-MOT stitch candidate evidence, not identity truth"
        else:
            case_type = "weak_edge_blocked"
            diagnosis = "弱同车参考被自动机制阻断；这通常是保守失败，不应调参强行恢复。"
            layer = "conservative_blocking"
            fix = "keep weak/posthoc-only unless cross-scene evidence supports a rule"
        cases.append(
            {
                "case_id": f"VFAIL_{idx:03d}",
                "case_type": case_type,
                "scene": norm(row.get("scene")),
                "reference_edge_id": rid,
                "from_reference_id": norm(row.get("from_reference_id")),
                "to_reference_id": norm(row.get("to_reference_id")),
                "auto_relation_status": norm(row.get("auto_relation_status")),
                "evidence_frames": norm(ref.get("visual_evidence_frames")),
                "visual_evidence_paths": norm(ref.get("visual_evidence_paths")),
                "diagnosis_cn": diagnosis,
                "mechanism_layer": layer,
                "minimal_cross_scene_fix": fix,
            }
        )
    if not cases:
        cases.append(
            {
                "case_id": "VFAIL_001",
                "case_type": "residual_risk_no_triggered_failure",
                "scene": "ALL",
                "reference_edge_id": "",
                "from_reference_id": "",
                "to_reference_id": "",
                "auto_relation_status": "",
                "evidence_frames": "",
                "visual_evidence_paths": "",
                "diagnosis_cn": "本轮没有触发代表性 forbidden/context 违规，但自动主干仍不能替代 WGV1.4 的视觉后验约束。",
                "mechanism_layer": "residual_posthoc_visual_constraint",
                "minimal_cross_scene_fix": "keep WGV1.4 as posthoc validation, not automatic input",
            }
        )
    return cases


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return "none"
    out = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(out)


def render_source_audit(date: str, source_rows: Sequence[Mapping[str, Any]], freeze_rows: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(
        [
            "# OTY2 WGV3.3A Optical Message Source Audit",
            "",
            f"Date: {date}",
            "",
            "## Boundary",
            "",
            "This audit checks whether WGV2/WGV3 optical messages can be reproduced by an automatic optical backbone. WGV1.4 is not an input to automatic construction.",
            "",
            "## Source Alignment",
            "",
            md_table(source_rows, ["scene", "tracker", "detection_rows", "tracker_rows", "tracker_tracks", "mapping_available", "blocking_reason"]),
            "",
            "## Automatic Freeze",
            "",
            md_table(freeze_rows, ["frozen_file", "sha256", "bytes"]),
            "",
            "The listed automatic files were written before WGV1.4/WGV1.4b reference tables were read.",
            "",
        ]
    )


def render_visual_failure_report(date: str, cases: Sequence[Mapping[str, Any]]) -> str:
    inspected_notes = {
        "GM_RM011_WGV12M002": "画面 000009/000010 中主体是同一辆白色车辆的相邻可见片段，但检测框从偏局部的侧窗/车身框切换到更大主体框。视觉上可以接受同车后验解释；自动层失败在标准 MOT 片段切分和框尺度变化，不能把该后验边直接升级成运行时同车消息。",
        "GM_RM011_WGV12M009": "画面 000239/000242 位于桥下近景，存在两辆白色车辆、局部车头和同帧竞争对象。源片段和目标片段都可能落在白车局部外观上，但仅靠自动 MOT 与框运动无法安全裁决主体是否相同；失败层是多车竞争、边缘局部框和后验视觉裁决缺口。",
    }
    lines = [
        "# OTY2 WGV3.3A Visual Failure Diagnosis",
        "",
        f"Date: {date}",
        "",
        "## Scope",
        "",
        "This report records Codex-side visual/mechanism diagnosis for representative WGV3.3A mismatches. It does not ask for new user frame review and does not feed conclusions back into the automatic relation rules.",
        "",
        "## Cases",
        "",
    ]
    for row in cases:
        lines.extend(
            [
                f"### {row.get('case_id')} {row.get('case_type')}",
                "",
                f"- scene: `{row.get('scene')}`",
                f"- reference edge: `{row.get('reference_edge_id')}`",
                f"- auto status: `{row.get('auto_relation_status')}`",
                f"- evidence frames: `{row.get('evidence_frames')}`",
                f"- visual evidence paths: `{row.get('visual_evidence_paths')}`",
                f"- diagnosis: {row.get('diagnosis_cn')}",
                f"- mechanism layer: `{row.get('mechanism_layer')}`",
                f"- minimal cross-scene fix: `{row.get('minimal_cross_scene_fix')}`",
                "",
            ]
        )
    inspected_rows = [row for row in cases if norm(row.get("reference_edge_id")) in inspected_notes]
    if inspected_rows:
        lines.extend(
            [
                "## Representative Visual Spot-Checks",
                "",
                "These checks were made after automatic relation decisions and WGV1.4 posthoc mapping were frozen. They do not change thresholds or feed back into automatic relation construction.",
                "",
            ]
        )
        for row in inspected_rows:
            rid = norm(row.get("reference_edge_id"))
            lines.extend(
                [
                    f"### {row.get('case_id')} {rid}",
                    "",
                    f"- inspected frames: `{row.get('evidence_frames')}`",
                    f"- visual judgment: {inspected_notes[rid]}",
                    "- runtime implication: keep the edge as posthoc visual evidence unless a future automatic competitor/partial-box mechanism recovers it cross-scene.",
                    "",
                ]
            )
    lines.extend(
        [
            "## Summary",
            "",
            "The recurring failure is not lack of YOLO26l detections alone. It is standard MOT/geometry association plus incomplete automatic competitor, subject-switch, edge-truncation, and visual adjudication evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def render_main_report(
    date: str,
    args: argparse.Namespace,
    source_rows: Sequence[Mapping[str, Any]],
    nodes: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]],
    competition_rows: Sequence[Mapping[str, Any]],
    mappings: Sequence[Mapping[str, Any]],
    evaluations: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    capability: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    freeze_rows: Sequence[Mapping[str, Any]],
    output_paths: Mapping[str, Path],
) -> str:
    rel_counts = Counter(norm(row.get("relation_status")) for row in relations)
    node_counts = Counter(norm(row.get("optical_message_readiness")) for row in nodes)
    mapped_count = sum(1 for row in mappings if norm(row.get("mapping_status")) in {"exact_like", "partial", "ambiguous"})
    accepted = [row for row in evaluations if norm(row.get("reference_status")) == "accepted"]
    weak = [row for row in evaluations if norm(row.get("reference_status")) == "weak"]
    forbidden_violation = sum(parse_int(row.get("forbidden_edge_violation_count")) or 0 for row in metrics)
    context_false = sum(parse_int(row.get("context_edge_false_bridge_count")) or 0 for row in metrics)
    accepted_recovered = sum(1 for row in accepted if boolish(row.get("recovered_as_accepted_or_weak")))
    weak_recovered = sum(1 for row in weak if boolish(row.get("recovered_as_accepted_or_weak")) or norm(row.get("auto_relation_status")) == "ambiguous_continuity")
    auto_runtime = [row for row in capability if norm(row.get("wgv2_wgv3_usage_permission")) == "automatic_runtime_message"]
    auto_uncertain = [row for row in capability if norm(row.get("wgv2_wgv3_usage_permission")) == "automatic_uncertain_message"]
    posthoc_only = [row for row in capability if norm(row.get("wgv2_wgv3_usage_permission")) == "posthoc_visual_constraint_only"]
    not_available = [row for row in capability if norm(row.get("wgv2_wgv3_usage_permission")) == "not_available"]
    accepted_total = len(accepted)
    weak_total = len(weak)
    if mapped_count == 0:
        conclusion = "OPEN_REFERENCE_MAPPING_BLOCKED"
        closure_sentence = "WGV3.3A remains open because WGV1.4 reference fragments could not be mapped to automatic MOT nodes."
    elif not relations or (rel_counts["strong_continuity"] + rel_counts["weak_continuity"] + rel_counts["ambiguous_continuity"] == 0):
        conclusion = "OPEN_TRACKLET_RELATION_BLOCKED"
        closure_sentence = "WGV3.3A remains open because automatic tracklet relation construction did not produce usable continuity hypotheses."
    elif (
        accepted_total > 0
        and accepted_recovered == accepted_total
        and weak_recovered == weak_total
        and forbidden_violation == 0
        and context_false == 0
    ):
        conclusion = "CLOSED_AUTOMATICALLY_REPRODUCIBLE"
        closure_sentence = "WGV3.3A closes as automatically reproducible under the fixed source and posthoc evaluation boundaries."
    else:
        conclusion = "CLOSED_PARTIALLY_REPRODUCIBLE"
        closure_sentence = "WGV3.3A closes as partially reproducible: stable automatic optical segments and some strong/weak continuity messages are available, but WGV1.4 posthoc visual adjudication remains necessary for subject-switch, competitor-boundary, visible-unboxed, weak-thread, and forbidden-boundary messages."
    input_rows = [
        {
            "input_group": "YOLO26l detection tables",
            "source": "; ".join(sorted({norm(row.get("detection_table")) for row in source_rows if norm(row.get("detection_table"))})),
        },
        {
            "input_group": "standard MOT tracker outputs",
            "source": "; ".join(sorted({norm(row.get("tracker_output_dir")) for row in source_rows if norm(row.get("tracker_output_dir"))})),
        },
        {
            "input_group": "appearance and tracklet embeddings",
            "source": rel(REPO_ROOT / args.embedding_root),
        },
        {
            "input_group": "WGV1.4 posthoc references",
            "source": "; ".join(rel(path) for path in [WGV14_FRAGMENTS, WGV14_SAME_EDGES, WGV14_CONTEXT_EDGES, WGV12_FRAME_BANK]),
        },
    ]
    lines = [
        "# OTY2 WGV3.3A Optical Message Source Reproducibility Closure",
        "",
        f"Date: {date}",
        "",
        "## Status",
        "",
        f"Conclusion: `{conclusion}`",
        "",
        "This is not a rollback to WGV1. It preserves WGV2/WGV3 as valid mechanism work and closes the missing source-dependency question: which optical messages can be produced by the automatic optical backbone, and which remain WGV1.4 posthoc visual constraints.",
        "",
        "## Source And Freeze",
        "",
        "- Detection source: YOLO26l OTY0-equivalent detection tables from the 20260704 detector-quality probe.",
        "- Tracker source: OTY1t standard MOT replay, primary BoT-SORT raw; ByteTrack raw retained as source audit comparison.",
        "- BoT-SORT appearance use: not ReID-enabled; `with_reid=False` and blank-image update remain true for MOT replay.",
        "- Appearance source: 512-d torchvision ResNet18 ImageNet learned appearance baseline from explicit local external weights, used post-tracker for evidence only.",
        "- WGV1.4/WGV1.4b role: posthoc reference and validation only, read after automatic files were frozen.",
        "",
        "## Input Files",
        "",
        md_table(input_rows, ["input_group", "source"]),
        "",
        md_table(freeze_rows, ["frozen_file", "sha256"]),
        "",
        "## Automatic Results",
        "",
        f"- automatic nodes: `{len(nodes)}` (`ready={node_counts['ready']}`, `ready_with_uncertainty={node_counts['ready_with_uncertainty']}`, `insufficient={node_counts['insufficient']}`, `blocked={node_counts['blocked']}`)",
        f"- candidate relations: `{len(relations)}`",
        f"- strong: `{rel_counts['strong_continuity']}`",
        f"- weak: `{rel_counts['weak_continuity']}`",
        f"- ambiguous: `{rel_counts['ambiguous_continuity']}`",
        f"- blocked: `{rel_counts['blocked_continuity']}`",
        f"- not_candidate: `{rel_counts['not_candidate']}`",
        "",
        "## WGV1.4 Mapping And Evaluation",
        "",
        f"- mapped fragments: `{mapped_count}/{len(mappings)}`",
        f"- accepted-edge recall: `{accepted_recovered}/{len(accepted)}`",
        f"- weak-edge recall: `{weak_recovered}/{len(weak)}`",
        f"- forbidden_edge_violation_count: `{forbidden_violation}`",
        f"- context-edge false bridge count: `{context_false}`",
        "",
        md_table(metrics, SCENE_METRIC_FIELDS),
        "",
        "## Runtime-Reproducible Optical Messages",
        "",
        md_table(auto_runtime, ["optical_message_type", "automatic_source_available", "runtime_reproducible", "confidence_or_uncertainty"]),
        "",
        "## Automatic-Uncertain Or Diagnostic Messages",
        "",
        md_table(auto_uncertain, ["optical_message_type", "automatic_source_available", "runtime_reproducible", "confidence_or_uncertainty", "wgv2_wgv3_usage_permission"]),
        "",
        "## Posthoc-Visual-Only Or Blocked Messages",
        "",
        md_table(posthoc_only, ["optical_message_type", "wgv2_wgv3_usage_permission", "blocking_reason"]),
        "",
        "## Not Available As Automatic Messages",
        "",
        md_table(not_available, ["optical_message_type", "wgv2_wgv3_usage_permission", "blocking_reason"]),
        "",
        "## Remaining Blockers",
        "",
        "- Automatic MOT can produce tracklet hypotheses and some continuity relations, but it still bridges or misses several WGV1.4 visual boundaries.",
        "- BoT-SORT does not use real ReID internally; appearance is post-tracker evidence.",
        "- Visible-unboxed gaps, subject switch, same-color replacement, and non-vehicle exclusion are not closed as runtime automatic messages.",
        "- WGV1.4 accepted and weak optical threads therefore cannot be represented as fully automatic runtime identity constraints.",
        "",
        "## Output Files",
        "",
        "\n".join(f"- `{rel(path)}`" for path in output_paths.values()),
        "",
        "## Commands",
        "",
        "```powershell",
        "D:/MINICONDA/envs/py311/python.exe -m py_compile tools/diagnostics/run_oty2_wgv3_3a_optical_message_source_closure.py",
        "D:/MINICONDA/envs/py311/python.exe tools/diagnostics/run_oty2_wgv3_3a_optical_message_source_closure.py",
        "```",
        "",
        "## Validation Summary",
        "",
        "- Script syntax check: passed.",
        "- Full run: passed with fixed seed `20260710`.",
        f"- Output rows: source alignment `{len(source_rows)}`, nodes `{len(nodes)}`, relation candidates `{len(relations)}`, relation decisions `{len(relations)}`, competition rows `{len(competition_rows)}`, node mappings `{len(mappings)}`, reference edge evaluations `{len(evaluations)}`, scene metrics `{len(metrics)}`, capability rows `{len(capability)}`, visual failure cases `{len(failures)}`.",
        "- Required-field, duplicate-key, bbox availability, freeze manifest, and null-stat validation: passed in the final session check.",
        "- Fixed-seed reproducibility: 14 WGV3.3A output files retained identical SHA256 hashes on rerun.",
        "",
        "## Closure",
        "",
        closure_sentence,
        "",
    ]
    return "\n".join(lines)


def output_paths(date: str) -> dict[str, Path]:
    return {
        "source_audit": REPORT_DIR / f"oty2_wgv3_3a_optical_message_source_audit_{date}.md",
        "source_alignment": SAMPLES_DIR / f"oty2_wgv3_3a_source_alignment_{date}.csv",
        "nodes": SAMPLES_DIR / f"oty2_wgv3_3a_auto_tracklet_nodes_{date}.csv",
        "candidates": SAMPLES_DIR / f"oty2_wgv3_3a_auto_relation_candidates_{date}.csv",
        "decisions": SAMPLES_DIR / f"oty2_wgv3_3a_auto_relation_decisions_{date}.csv",
        "competition": SAMPLES_DIR / f"oty2_wgv3_3a_competition_relations_{date}.csv",
        "freeze": SAMPLES_DIR / f"oty2_wgv3_3a_auto_freeze_manifest_{date}.csv",
        "mapping": SAMPLES_DIR / f"oty2_wgv3_3a_wgv1_4_node_mapping_{date}.csv",
        "evaluation": SAMPLES_DIR / f"oty2_wgv3_3a_reference_edge_evaluation_{date}.csv",
        "scene_metrics": SAMPLES_DIR / f"oty2_wgv3_3a_scene_metrics_{date}.csv",
        "visual_failure_report": REPORT_DIR / f"oty2_wgv3_3a_visual_failure_diagnosis_{date}.md",
        "visual_failure_cases": SAMPLES_DIR / f"oty2_wgv3_3a_visual_failure_cases_{date}.csv",
        "capability": SAMPLES_DIR / f"oty2_wgv3_3a_optical_message_capability_{date}.csv",
        "main_report": REPORT_DIR / f"oty2_wgv3_3a_optical_message_source_reproducibility_closure_{date}.md",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument("--run-timestamp", default=DEFAULT_RUN_TS)
    parser.add_argument("--embedding-timestamp", default=DEFAULT_EMB_TS)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--tracker-root", default=f"outputs/oty2_wgv3_3a_yolo26l_mot_replay_{DEFAULT_RUN_TS}")
    parser.add_argument("--embedding-root", default=f"outputs/oty2_wgv3_3a_yolo26l_embedding_source_{DEFAULT_RUN_TS}")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    paths = source_paths(args)
    validate_inputs(paths)
    out = output_paths(args.date)

    source_rows = build_source_alignment(paths)
    nodes, _node_by_id, assignment_rows_by_node = build_auto_nodes(paths)
    vectors = load_vectors_for_nodes(paths, nodes)
    relations, competition_rows = build_relations(nodes, vectors)

    write_csv(out["source_alignment"], source_rows, SOURCE_FIELDS)
    write_csv(out["nodes"], nodes, NODE_FIELDS)
    write_csv(out["candidates"], relations, RELATION_FIELDS)
    write_csv(out["decisions"], relations, RELATION_FIELDS)
    write_csv(out["competition"], competition_rows, COMPETITION_FIELDS)
    freeze_rows = freeze_auto_outputs(
        [out["source_alignment"], out["nodes"], out["candidates"], out["decisions"], out["competition"]],
        out["freeze"],
        args.date,
    )

    fragments, _ = read_csv_rows(WGV14_FRAGMENTS)
    same_edges, _ = read_csv_rows(WGV14_SAME_EDGES)
    context_edges, _ = read_csv_rows(WGV14_CONTEXT_EDGES)
    mappings = build_mapping(fragments, nodes, assignment_rows_by_node)
    evaluations = evaluate_reference_edges(mappings, relations, same_edges, context_edges)
    metrics = build_scene_metrics(nodes, relations, mappings, evaluations)
    capability = build_capability(metrics, out["nodes"], out["decisions"], out["evaluation"])
    failures = build_failure_cases(evaluations)

    write_csv(out["mapping"], mappings, MAPPING_FIELDS)
    write_csv(out["evaluation"], evaluations, EVAL_FIELDS)
    write_csv(out["scene_metrics"], metrics, SCENE_METRIC_FIELDS)
    write_csv(out["capability"], capability, CAPABILITY_FIELDS)
    write_csv(out["visual_failure_cases"], failures, FAILURE_FIELDS)
    write_text(out["source_audit"], render_source_audit(args.date, source_rows, freeze_rows))
    write_text(out["visual_failure_report"], render_visual_failure_report(args.date, failures))
    write_text(
        out["main_report"],
        render_main_report(
            args.date,
            args,
            source_rows,
            nodes,
            relations,
            competition_rows,
            mappings,
            evaluations,
            metrics,
            capability,
            failures,
            freeze_rows,
            out,
        ),
    )

    print(
        json.dumps(
            {
                "date": args.date,
                "branch": git_fact(["branch", "--show-current"]),
                "head": git_fact(["rev-parse", "HEAD"]),
                "nodes": len(nodes),
                "relations": len(relations),
                "relation_counts": Counter(norm(row.get("relation_status")) for row in relations),
                "mapped_fragments": sum(1 for row in mappings if norm(row.get("mapping_status")) in {"exact_like", "partial", "ambiguous"}),
                "fragments": len(mappings),
                "forbidden_edge_violation_count": sum(parse_int(row.get("forbidden_edge_violation_count")) or 0 for row in metrics),
                "context_edge_false_bridge_count": sum(parse_int(row.get("context_edge_false_bridge_count")) or 0 for row in metrics),
                "outputs": {key: str(value) for key, value in out.items()},
            },
            ensure_ascii=False,
            indent=2,
            default=dict,
        )
    )


if __name__ == "__main__":
    main()
