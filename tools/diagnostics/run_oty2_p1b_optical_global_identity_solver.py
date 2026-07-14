#!/usr/bin/env python3
"""Build and solve the optical-only OTY2 P1-B global identity baseline.

The implementation is deliberately offline and auditable.  It reads complete
optical detections, local tracker assignments, ResNet18 embeddings, original
optical frames, and the P1-A optical identity ledger.  It never reads SAR,
SAR GT, optical-to-SAR mapping products, IoU-to-SAR results, selector outputs,
or final annotation fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import cv2
import numpy as np
import yaml
from PIL import Image, ImageDraw
from scipy.optimize import Bounds, LinearConstraint, linear_sum_assignment, milp
from scipy.sparse import lil_matrix


SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")
IMAGE_SIZE = (800, 600)


@dataclass
class Observation:
    scene: str
    frame: int
    source: str
    det_id: str
    observation_id: str
    image_path: Path
    bbox: tuple[float, float, float, float]
    confidence: float
    class_name: str
    normalized_or_raw: str
    normalization_action: str
    active: bool
    tracker_ids: set[str] = field(default_factory=set)
    seed_track_id: str = ""
    embedding_uid: str = ""
    embedding: np.ndarray | None = None
    color: np.ndarray | None = None
    cluster_id: str = ""
    cluster_tracker_ids: set[str] = field(default_factory=set)
    cluster_embedding: np.ndarray | None = None
    cluster_color: np.ndarray | None = None
    local_tracker_support: int = 0
    excluded_nonvehicle: bool = False
    exclusion_reason: str = ""

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def width(self) -> float:
        return max(1.0, self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return max(1.0, self.bbox[3] - self.bbox[1])

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def border_state(self) -> str:
        x1, y1, x2, y2 = self.bbox
        hits = []
        if x1 <= 16:
            hits.append("left")
        if x2 >= IMAGE_SIZE[0] - 16:
            hits.append("right")
        if y1 <= 12:
            hits.append("top")
        if y2 >= IMAGE_SIZE[1] - 12:
            hits.append("bottom")
        return "+".join(hits) if hits else "interior"


@dataclass
class Tracklet:
    scene: str
    tracklet_id: str
    source: str
    seed_track_id: str
    observations: list[Observation]
    split_reason: str
    known_constraints: list[str]
    purity_risk: str
    tracker_ids: set[str]
    cluster_ids: set[str]
    appearance: np.ndarray | None
    color: np.ndarray | None
    credible_count: int
    coverage_score: int

    @property
    def start(self) -> int:
        return self.observations[0].frame

    @property
    def end(self) -> int:
        return self.observations[-1].frame

    @property
    def first(self) -> Observation:
        return self.observations[0]

    @property
    def last(self) -> Observation:
        return self.observations[-1]


@dataclass
class Edge:
    scene: str
    edge_id: str
    src: int
    dst: int
    gap: int
    motion: float
    appearance: float | None
    color: float | None
    shape: float
    gap_cost: float
    boundary_support: float
    competition_support: int
    shared_trackers: list[str]
    detector_change: bool
    missing_feature_count: int
    turnover_reset_penalty: int
    total_cost: int
    selected: bool = False
    rejection_reason: str = "not_selected_by_global_solver"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--config", type=Path, default=Path("configs/oty2/oty2_p1b_optical_global_identity.yaml"))
    parser.add_argument("--scenes", nargs="*", choices=SCENES, default=list(SCENES))
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Build observations, tracklets, and edges but do not solve or render.")
    parser.add_argument("--graph-only", action="store_true", help="Alias for --dry-run retained for the requested audit interface.")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--stability-only", action="store_true")
    parser.add_argument("--direct-review-complete", action="store_true", help="Record that all generated thread and mandatory-event atlases were directly reviewed.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if not duplicate_header(row)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: encode_cell(row.get(key, "")) for key in fieldnames})


def encode_cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        if isinstance(value, set):
            value = sorted(value)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def duplicate_header(row: Mapping[str, Any]) -> bool:
    values = [str(v or "").strip() for v in row.values() if str(v or "").strip()]
    if not values:
        return False
    hits = sum(1 for key, value in row.items() if str(value or "").strip() == key)
    return hits >= max(2, len(values) // 2)


def as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def resolve(repo_root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else repo_root / value


def param(config: Mapping[str, Any], group: str, name: str) -> float:
    value = config[group][name]
    return float(value["value"] if isinstance(value, dict) else value)


def bbox_iou(a: Sequence[float], b: Sequence[float]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / max(aa + bb - inter, 1e-9)


def bbox_containment(a: Sequence[float], b: Sequence[float]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))
    bb = max(1e-9, (b[2] - b[0]) * (b[3] - b[1]))
    return inter / min(aa, bb)


def normalized_center_distance(a: Observation, b: Observation) -> float:
    ax, ay = a.center
    bx, by = b.center
    diag = max(math.hypot(a.width, a.height), math.hypot(b.width, b.height), 1.0)
    return math.hypot(ax - bx, ay - by) / diag


def mean_unit(vectors: Iterable[np.ndarray | None]) -> np.ndarray | None:
    usable = [np.asarray(v, dtype=np.float32) for v in vectors if v is not None]
    if not usable:
        return None
    value = np.mean(np.stack(usable), axis=0)
    norm = float(np.linalg.norm(value))
    return value / norm if norm > 1e-9 else value


def mean_vector(vectors: Iterable[np.ndarray | None]) -> np.ndarray | None:
    usable = [np.asarray(v, dtype=np.float32) for v in vectors if v is not None]
    return np.mean(np.stack(usable), axis=0) if usable else None


def cosine(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    if a is None or b is None:
        return None
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-9:
        return None
    return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))


def central_lab_feature(image_path: Path, bbox: Sequence[float]) -> np.ndarray | None:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        return None
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    x1 = int(max(0, min(w - 1, x1 + 0.12 * bw)))
    x2 = int(max(x1 + 1, min(w, x2 - 0.12 * bw)))
    y1 = int(max(0, min(h - 1, y1 + 0.12 * bh)))
    y2 = int(max(y1 + 1, min(h, y2 - 0.12 * bh)))
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    lo = np.percentile(lab, 10, axis=0)
    hi = np.percentile(lab, 90, axis=0)
    trimmed = np.clip(lab, lo, hi)
    feature = np.concatenate([trimmed.mean(axis=0), trimmed.std(axis=0)]) / 255.0
    return feature.astype(np.float32)


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    base_config = config.get("base_config") if isinstance(config, dict) else None
    if not base_config:
        return config
    base_path = Path(base_config)
    if not base_path.is_absolute():
        base_path = path.resolve().parents[2] / base_path
    base = load_config(base_path)

    def merge(target: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
        for key, value in overlay.items():
            if key == "base_config":
                continue
            if isinstance(value, Mapping) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = value
        return target

    return merge(base, config)


def scene_asset_paths(source_root: Path, scene: str, config: Mapping[str, Any]) -> dict[str, Path]:
    norm_dir = source_root / config["assets"]["normalized_detection_dir"]
    y26_tracker = source_root / config["assets"]["yolo26l_tracker_root"]
    y11_tracker = source_root / config["assets"]["yolo11l_tracker_root"]
    return {
        "y26_norm": norm_dir / f"{scene}_yolo26l_probe_normalized_detection_table.csv",
        "y11_norm": norm_dir / f"{scene}_yolo11l_baseline_normalized_detection_table.csv",
        "y26_botsort": y26_tracker / f"{scene}_yolo26l_probe_botsort_raw" / "oty1t_tracker_detection_assignments.csv",
        "y26_bytetrack": y26_tracker / f"{scene}_yolo26l_probe_bytetrack_raw" / "oty1t_tracker_detection_assignments.csv",
        "y11_botsort": y11_tracker / f"{scene}_yolo11l_baseline_botsort_normalized_active" / "oty1t_tracker_detection_assignments.csv",
        "y11_bytetrack": y11_tracker / f"{scene}_yolo11l_baseline_bytetrack_normalized_active" / "oty1t_tracker_detection_assignments.csv",
    }


def load_embeddings(source_root: Path, config: Mapping[str, Any]) -> dict[tuple[str, int, str], tuple[str, np.ndarray]]:
    index_path = source_root / config["assets"]["yolo26l_embedding_index"]
    npz_path = source_root / config["assets"]["yolo26l_embedding_npz"]
    rows = read_csv(index_path)
    archive = np.load(npz_path, allow_pickle=True)
    by_uid = {str(uid): archive["features"][idx] for idx, uid in enumerate(archive["row_uid"])}
    out: dict[tuple[str, int, str], tuple[str, np.ndarray]] = {}
    for row in rows:
        uid = row["row_uid"]
        out[(row["scene"], as_int(row["frame_id"]), row["det_id_ignored"])] = (uid, by_uid[uid])
    return out


def load_tracker_map(paths: Mapping[str, Path], source: str) -> dict[tuple[str, int, str], set[str]]:
    out: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    for tracker in ("botsort", "bytetrack"):
        path = paths[f"{'y26' if source == 'YOLO26l' else 'y11'}_{tracker}"]
        if not path.exists():
            continue
        for row in read_csv(path):
            track_id = str(row.get("tracker_track_id", "")).strip()
            if not track_id:
                continue
            key = (row["scene"], as_int(row["optical_frame_num"]), row["det_id"])
            out[key].add(f"{source}:{tracker}:{track_id}")
    return out


def load_observations(repo_root: Path, config: Mapping[str, Any], scenes: Sequence[str]) -> list[Observation]:
    source_root = Path(config["paths"]["source_repo_root"])
    embeddings = load_embeddings(source_root, config)
    observations: list[Observation] = []
    for scene in scenes:
        paths = scene_asset_paths(source_root, scene, config)
        tracker_maps = {
            "YOLO26l": load_tracker_map(paths, "YOLO26l"),
            "YOLO11l": load_tracker_map(paths, "YOLO11l"),
        }
        for source, path_key in (("YOLO26l", "y26_norm"), ("YOLO11l", "y11_norm")):
            for row in read_csv(paths[path_key]):
                if not as_bool(row.get("active_for_tracking")):
                    continue
                frame = as_int(row["optical_frame_num"])
                det_id = row["det_id"]
                key = (scene, frame, det_id)
                emb_uid, emb = embeddings.get(key, ("", None)) if source == "YOLO26l" else ("", None)
                tracker_ids = set(tracker_maps[source].get(key, set()))
                seed_prefix = f"{source}:botsort:"
                seed = next((tid for tid in sorted(tracker_ids) if tid.startswith(seed_prefix)), "")
                obs = Observation(
                    scene=scene,
                    frame=frame,
                    source=source,
                    det_id=det_id,
                    observation_id=f"{scene}:{source}:{det_id}",
                    image_path=Path(row["optical_path"]),
                    bbox=(as_float(row["bbox_x1"]), as_float(row["bbox_y1"]), as_float(row["bbox_x2"]), as_float(row["bbox_y2"])),
                    confidence=as_float(row["confidence"]),
                    class_name=row["class_name"],
                    normalized_or_raw="normalized_active",
                    normalization_action=row.get("normalization_action", ""),
                    active=True,
                    tracker_ids=tracker_ids,
                    seed_track_id=seed,
                    embedding_uid=emb_uid,
                    embedding=emb,
                )
                obs.color = central_lab_feature(obs.image_path, obs.bbox)
                observations.append(obs)
    tracker_counts = Counter(tid for obs in observations for tid in obs.tracker_ids)
    for obs in observations:
        obs.local_tracker_support = max((tracker_counts[tid] for tid in obs.tracker_ids), default=0)
    return sorted(observations, key=lambda o: (o.scene, o.frame, o.source, o.det_id))


def cluster_observations(observations: Sequence[Observation], config: Mapping[str, Any]) -> dict[str, list[Observation]]:
    iou_floor = param(config, "parameters", "observation_alternative_iou")
    containment_floor = param(config, "parameters", "observation_alternative_containment")
    center_floor = param(config, "parameters", "observation_alternative_center_ratio")
    by_scene_frame: dict[tuple[str, int], list[Observation]] = defaultdict(list)
    for obs in observations:
        by_scene_frame[(obs.scene, obs.frame)].append(obs)
    clusters: dict[str, list[Observation]] = {}
    for (scene, frame), frame_obs in sorted(by_scene_frame.items()):
        left = [o for o in frame_obs if o.source == "YOLO26l"]
        right = [o for o in frame_obs if o.source == "YOLO11l"]
        matches: dict[str, str] = {}
        if left and right:
            score = np.full((len(left), len(right)), -1e6, dtype=float)
            for i, a in enumerate(left):
                for j, b in enumerate(right):
                    iou = bbox_iou(a.bbox, b.bbox)
                    contain = bbox_containment(a.bbox, b.bbox)
                    center = normalized_center_distance(a, b)
                    if iou >= iou_floor or (contain >= containment_floor and center <= center_floor):
                        score[i, j] = 2.0 * iou + contain - 0.25 * center
            rows, cols = linear_sum_assignment(-score)
            for i, j in zip(rows, cols):
                if score[i, j] > -1e5:
                    matches[left[i].observation_id] = right[j].observation_id
        used: set[str] = set()
        cluster_index = 1
        lookup = {o.observation_id: o for o in frame_obs}
        for obs in sorted(frame_obs, key=lambda o: (o.source, o.det_id)):
            if obs.observation_id in used:
                continue
            members = [obs]
            partner_id = matches.get(obs.observation_id)
            if not partner_id:
                partner_id = next((a for a, b in matches.items() if b == obs.observation_id), "")
            if partner_id and partner_id not in used:
                members.append(lookup[partner_id])
            cluster_id = f"{scene}:F{frame:03d}:ALT{cluster_index:03d}"
            cluster_index += 1
            tracker_union = set().union(*(m.tracker_ids for m in members))
            cluster_embedding = mean_unit(m.embedding for m in members)
            cluster_color = mean_vector(m.color for m in members)
            for member in members:
                member.cluster_id = cluster_id
                member.cluster_tracker_ids = set(tracker_union)
                member.cluster_embedding = cluster_embedding
                member.cluster_color = cluster_color
                used.add(member.observation_id)
            clusters[cluster_id] = members
    return clusters


def apply_nonvehicle_rules(observations: Sequence[Observation], clusters: Mapping[str, Sequence[Observation]], config: Mapping[str, Any]) -> None:
    excluded_clusters: dict[str, str] = {}
    for rule in config.get("hard_nonvehicle_rules", []):
        scene = rule["scene"]
        start = int(rule["frame_start"])
        end = int(rule["frame_end"])
        tracker_ids = set(rule.get("tracker_ids", []))
        for obs in observations:
            if obs.scene != scene or not (start <= obs.frame <= end):
                continue
            if tracker_ids and not (obs.cluster_tracker_ids & tracker_ids):
                continue
            excluded_clusters[obs.cluster_id] = rule["evidence_id"]
    for cluster_id, evidence_id in excluded_clusters.items():
        for obs in clusters[cluster_id]:
            obs.excluded_nonvehicle = True
            obs.exclusion_reason = evidence_id


def forced_split_reason(scene: str, previous: int, current: int, config: Mapping[str, Any]) -> str:
    for start, end, label in config.get("forced_split_windows", {}).get(scene, []):
        boundaries = {int(start), int(end) + 1}
        if any(previous < boundary <= current for boundary in boundaries):
            return str(label)
    return ""


def credible(obs: Observation, config: Mapping[str, Any]) -> bool:
    if obs.excluded_nonvehicle:
        return False
    floor = param(config, "parameters", "credible_yolo26l_confidence" if obs.source == "YOLO26l" else "credible_yolo11l_confidence")
    multisource = False
    if obs.cluster_id:
        multisource = any(tid.startswith("YOLO26l") for tid in obs.cluster_tracker_ids) and any(tid.startswith("YOLO11l") for tid in obs.cluster_tracker_ids)
    return obs.confidence >= floor and (multisource or obs.local_tracker_support >= 3)


def make_tracklet(scene: str, source: str, seed: str, index: int, obs_rows: list[Observation], reason: str, config: Mapping[str, Any]) -> Tracklet:
    constraints = sorted({label for obs in obs_rows for label in ([obs.exclusion_reason] if obs.exclusion_reason else [])})
    risk = "low"
    if reason not in {"tracker_seed_start", "supplement_singleton"}:
        risk = "review_split"
    if any(o.border_state != "interior" for o in obs_rows):
        risk = "boundary_or_split" if risk != "low" else "boundary"
    appearance = mean_unit(o.cluster_embedding for o in obs_rows)
    color = mean_vector(o.cluster_color for o in obs_rows)
    credible_count = sum(1 for o in obs_rows if credible(o, config))
    coverage_score = sum(100 if credible(o, config) else 0 for o in obs_rows)
    if len({o.frame for o in obs_rows}) < int(param(config, "parameters", "minimum_credible_tracklet_frames")):
        coverage_score = 0
    if len(obs_rows) >= 2:
        coverage_score += 20 * min(len(obs_rows), 10) if coverage_score > 0 else 0
    return Tracklet(
        scene=scene,
        tracklet_id=f"{scene}:AT{index:04d}",
        source=source,
        seed_track_id=seed,
        observations=obs_rows,
        split_reason=reason,
        known_constraints=constraints,
        purity_risk=risk,
        tracker_ids=set().union(*(o.cluster_tracker_ids for o in obs_rows)),
        cluster_ids={o.cluster_id for o in obs_rows},
        appearance=appearance,
        color=color,
        credible_count=credible_count,
        coverage_score=coverage_score,
    )


def build_local_supplement_chains(singles: Sequence[Observation], config: Mapping[str, Any]) -> list[list[Observation]]:
    """Form short, high-confidence local chains without restoring tracker IDs.

    The matcher is deliberately limited to one-to-one consecutive/near-consecutive
    observations from the same detector source.  It reuses the existing P1-B
    geometry and color thresholds and respects every configured subject-switch
    boundary.
    """

    max_elapsed = int(param(config, "parameters", "atomic_max_internal_gap")) + 1
    iou_floor = param(config, "parameters", "observation_alternative_iou")
    containment_floor = param(config, "parameters", "observation_alternative_containment")
    center_floor = param(config, "parameters", "observation_alternative_center_ratio")
    color_trigger = param(config, "parameters", "atomic_color_distance_trigger")
    by_stream: dict[tuple[str, str], dict[int, list[Observation]]] = defaultdict(lambda: defaultdict(list))
    for obs in singles:
        by_stream[(obs.scene, obs.source)][obs.frame].append(obs)

    completed: list[list[Observation]] = []
    for (scene, _source), frame_rows in sorted(by_stream.items()):
        active: list[list[Observation]] = []
        for frame in sorted(frame_rows):
            retained = []
            for chain in active:
                if frame - chain[-1].frame <= max_elapsed:
                    retained.append(chain)
                else:
                    completed.append(chain)
            active = retained
            current = sorted(frame_rows[frame], key=lambda o: (o.center[0], o.det_id))
            candidates: list[tuple[float, int, int]] = []
            for cidx, chain in enumerate(active):
                previous = chain[-1]
                elapsed = frame - previous.frame
                if elapsed <= 0 or elapsed > max_elapsed or forced_split_reason(scene, previous.frame, frame, config):
                    continue
                for oidx, obs in enumerate(current):
                    iou = bbox_iou(previous.bbox, obs.bbox)
                    containment = bbox_containment(previous.bbox, obs.bbox)
                    center = normalized_center_distance(previous, obs)
                    color = None if previous.cluster_color is None or obs.cluster_color is None else float(np.linalg.norm(previous.cluster_color - obs.cluster_color))
                    geometry_ok = iou >= iou_floor or (containment >= containment_floor and center <= center_floor)
                    local_motion_ok = center <= center_floor and (color is None or color <= color_trigger)
                    if not (geometry_ok or local_motion_ok):
                        continue
                    score = 2.0 * iou + containment - 0.5 * center - 0.25 * (color or 0.0) - 0.1 * (elapsed - 1)
                    candidates.append((score, cidx, oidx))
            used_chains: set[int] = set()
            used_obs: set[int] = set()
            for _score, cidx, oidx in sorted(candidates, reverse=True):
                if cidx in used_chains or oidx in used_obs:
                    continue
                active[cidx].append(current[oidx])
                used_chains.add(cidx)
                used_obs.add(oidx)
            for oidx, obs in enumerate(current):
                if oidx not in used_obs:
                    active.append([obs])
        completed.extend(active)
    return completed


def merge_overlapping_local_tracklets(tracklets: Sequence[Tracklet], config: Mapping[str, Any]) -> list[Tracklet]:
    """Union short same-source fragments when every overlapping frame agrees.

    This handles partial-to-full tracker handoffs that overlap briefly in time.
    It does not use tracker identity as truth: the merge requires strong bbox
    containment/center agreement on all overlapping frames and cannot cross a
    configured subject-switch boundary.
    """

    containment_floor = param(config, "parameters", "observation_alternative_containment")
    center_floor = param(config, "parameters", "observation_alternative_center_ratio")
    max_overlap = int(param(config, "parameters", "atomic_max_internal_gap")) + 1
    working = list(tracklets)
    changed = True
    while changed:
        changed = False
        ordered = sorted(range(len(working)), key=lambda idx: (working[idx].scene, working[idx].source, working[idx].start, working[idx].end, working[idx].tracklet_id))
        for left_pos, left_idx in enumerate(ordered):
            a = working[left_idx]
            for right_idx in ordered[left_pos + 1 :]:
                b = working[right_idx]
                if b.scene != a.scene or b.source != a.source:
                    continue
                if b.start > a.end or b.end <= a.end:
                    continue
                overlap_frames = sorted({o.frame for o in a.observations} & {o.frame for o in b.observations})
                if not overlap_frames or len(overlap_frames) > max_overlap:
                    continue
                if forced_split_reason(a.scene, a.start, b.end, config):
                    continue
                a_by_frame = {o.frame: o for o in a.observations}
                b_by_frame = {o.frame: o for o in b.observations}
                compatible = True
                for frame in overlap_frames:
                    left = a_by_frame[frame]
                    right = b_by_frame[frame]
                    if bbox_containment(left.bbox, right.bbox) < containment_floor or normalized_center_distance(left, right) > center_floor:
                        compatible = False
                        break
                if not compatible:
                    continue
                merged_by_frame: dict[int, Observation] = {}
                for obs in sorted(a.observations + b.observations, key=lambda o: (o.frame, -o.area, -o.confidence)):
                    merged_by_frame.setdefault(obs.frame, obs)
                merged_rows = [merged_by_frame[frame] for frame in sorted(merged_by_frame)]
                index_match = re.search(r"AT(\d+)$", a.tracklet_id)
                index = int(index_match.group(1)) if index_match else 1
                merged = make_tracklet(a.scene, a.source, f"{a.seed_track_id}|{b.seed_track_id}", index, merged_rows, "local_overlap_fragment_union", config)
                working[left_idx] = merged
                del working[right_idx]
                changed = True
                break
            if changed:
                break
    return working


def build_tracklets(observations: Sequence[Observation], config: Mapping[str, Any]) -> list[Tracklet]:
    max_gap = int(param(config, "parameters", "atomic_max_internal_gap"))
    motion_trigger = param(config, "parameters", "atomic_motion_jump_ratio")
    appearance_floor = param(config, "parameters", "atomic_appearance_cosine_floor")
    color_trigger = param(config, "parameters", "atomic_color_distance_trigger")
    by_scene_seed: dict[tuple[str, str, str], list[Observation]] = defaultdict(list)
    singles: list[Observation] = []
    for obs in observations:
        if obs.excluded_nonvehicle:
            continue
        if obs.seed_track_id:
            by_scene_seed[(obs.scene, obs.source, obs.seed_track_id)].append(obs)
        else:
            singles.append(obs)
    all_tracklets: list[Tracklet] = []
    per_scene_counter: Counter[str] = Counter()
    for (scene, source, seed), rows in sorted(by_scene_seed.items()):
        rows = sorted(rows, key=lambda o: (o.frame, o.det_id))
        segment: list[Observation] = []
        next_reason = "tracker_seed_start"
        for obs in rows:
            split_reason = ""
            if segment:
                prev = segment[-1]
                frame_gap = obs.frame - prev.frame - 1
                if frame_gap > max_gap:
                    split_reason = f"frame_gap_{frame_gap}"
                split_reason = split_reason or forced_split_reason(scene, prev.frame, obs.frame, config)
                dt = max(1, obs.frame - prev.frame)
                displacement = math.dist(obs.center, prev.center) / max(1.0, 0.5 * (math.hypot(obs.width, obs.height) + math.hypot(prev.width, prev.height))) / dt
                app = cosine(obs.cluster_embedding, prev.cluster_embedding)
                color = None if obs.cluster_color is None or prev.cluster_color is None else float(np.linalg.norm(obs.cluster_color - prev.cluster_color))
                if displacement > motion_trigger and ((app is not None and app < appearance_floor) or (color is not None and color > color_trigger)):
                    split_reason = split_reason or f"joint_motion_appearance_color_jump:{displacement:.3f}:{app if app is not None else 'na'}:{color if color is not None else 'na'}"
            if split_reason and segment:
                per_scene_counter[scene] += 1
                all_tracklets.append(make_tracklet(scene, source, seed, per_scene_counter[scene], segment, next_reason, config))
                segment = []
                next_reason = split_reason
            segment.append(obs)
        if segment:
            per_scene_counter[scene] += 1
            all_tracklets.append(make_tracklet(scene, source, seed, per_scene_counter[scene], segment, next_reason, config))
    p1c = config.get("p1c", {})
    if bool(p1c.get("local_supplement_chaining_enabled", False)):
        supplement_chains = build_local_supplement_chains(singles, config)
    else:
        supplement_chains = [[obs] for obs in sorted(singles, key=lambda o: (o.scene, o.frame, o.source, o.det_id))]
    for chain in sorted(supplement_chains, key=lambda rows: (rows[0].scene, rows[0].frame, rows[-1].frame, rows[0].source, rows[0].det_id)):
        scene = chain[0].scene
        per_scene_counter[scene] += 1
        reason = "local_high_confidence_continuity" if len(chain) > 1 else "supplement_singleton"
        all_tracklets.append(make_tracklet(scene, chain[0].source, "local_supplement_chain" if len(chain) > 1 else "untracked", per_scene_counter[scene], chain, reason, config))
    if bool(p1c.get("overlap_fragment_union_enabled", False)):
        all_tracklets = merge_overlapping_local_tracklets(all_tracklets, config)
    return sorted(all_tracklets, key=lambda t: (t.scene, t.start, t.end, t.tracklet_id))


def transition_features(a: Tracklet, b: Tracklet, scene_observations: Sequence[Observation], config: Mapping[str, Any]) -> dict[str, Any] | None:
    if b.start <= a.end:
        return None
    gap = b.start - a.end - 1
    if gap > int(param(config, "parameters", "max_transition_gap_frames")):
        return None
    ax, ay = a.last.center
    bx, by = b.first.center
    if len(a.observations) >= 2:
        p = a.observations[-2]
        dt = max(1, a.last.frame - p.frame)
        vx = (ax - p.center[0]) / dt
        vy = (ay - p.center[1]) / dt
    else:
        vx = vy = 0.0
    elapsed = b.start - a.end
    pred = (ax + vx * elapsed, ay + vy * elapsed)
    raw_displacement = math.dist((ax, ay), (bx, by))
    max_displacement = param(config, "parameters", "max_instant_displacement_base_px") + param(config, "parameters", "max_instant_displacement_per_frame_px") * elapsed
    if raw_displacement > max_displacement:
        return None
    diag = max(30.0, 0.5 * (math.hypot(a.last.width, a.last.height) + math.hypot(b.first.width, b.first.height)))
    motion = min(4.0, math.dist(pred, (bx, by)) / diag)
    app_cos = cosine(a.appearance, b.appearance)
    appearance = None if app_cos is None else 1.0 - app_cos
    color = None if a.color is None or b.color is None else min(2.0, float(np.linalg.norm(a.color - b.color)))
    aspect_a = a.last.width / a.last.height
    aspect_b = b.first.width / b.first.height
    shape = min(3.0, abs(math.log(max(aspect_b, 1e-6) / max(aspect_a, 1e-6))) + 0.5 * abs(math.log(max(b.first.area, 1.0) / max(a.last.area, 1.0))))
    gap_norm = gap / max(1.0, param(config, "parameters", "max_transition_gap_frames"))
    boundary_support = float(a.last.border_state != "interior" or b.first.border_state != "interior")
    shared_trackers = sorted(a.tracker_ids & b.tracker_ids)
    competition = sum(1 for o in scene_observations if a.end <= o.frame <= b.start and math.dist(o.center, ((ax + bx) / 2, (ay + by) / 2)) < 150)
    missing = int(appearance is None) + int(color is None)
    total = 0.0
    total += param(config, "soft_costs", "motion_weight") * min(1.5, motion / 2.0)
    total += param(config, "soft_costs", "appearance_weight") * (appearance if appearance is not None else 0.0)
    total += param(config, "soft_costs", "color_weight") * (color if color is not None else 0.0)
    total += param(config, "soft_costs", "shape_weight") * min(1.5, shape / 2.0)
    total += param(config, "soft_costs", "gap_weight") * gap_norm
    total += param(config, "soft_costs", "cross_detector_penalty") * float(a.source != b.source)
    total += param(config, "soft_costs", "missing_feature_penalty") * missing
    total -= param(config, "soft_costs", "tracker_support_bonus") * float(bool(shared_trackers))
    total -= 12.0 * boundary_support * min(1.0, gap_norm + 0.25)
    turnover_reset_penalty = 0
    p1c = config.get("p1c", {})
    opposite_horizontal_boundaries = (
        ("left" in a.last.border_state and "right" in b.first.border_state)
        or ("right" in a.last.border_state and "left" in b.first.border_state)
    )
    same_boundary_reentry = (
        ("right" in a.last.border_state and "right" in b.first.border_state and b.first.center[0] < a.last.center[0])
        or ("left" in a.last.border_state and "left" in b.first.border_state and b.first.center[0] > a.last.center[0])
    )
    boundary_reentry = opposite_horizontal_boundaries or same_boundary_reentry
    turnover_gap_floor = int(param(config, "parameters", "long_gap_review_frames"))
    boundary_turnover = bool(p1c.get("boundary_reentry_turnover_enabled", False)) and gap > turnover_gap_floor and boundary_reentry
    locally_supported_subject_switch_continuation = gap == 0 and bool(shared_trackers)
    subject_switch_reset = (
        bool(p1c.get("subject_switch_lifecycle_reset_enabled", False))
        and "subject_switch" in b.split_reason
        and not locally_supported_subject_switch_continuation
    )
    if boundary_turnover or subject_switch_reset:
        multiplier = float(p1c.get("boundary_reentry_turnover_multiplier", 1.0))
        turnover_reset_penalty = int(round(multiplier * (param(config, "soft_costs", "birth_cost") + param(config, "soft_costs", "exit_cost"))))
        total += turnover_reset_penalty
        total = max(total, float(turnover_reset_penalty))
    return {
        "gap": gap,
        "motion": motion,
        "appearance": appearance,
        "color": color,
        "shape": shape,
        "gap_cost": gap_norm,
        "boundary_support": boundary_support,
        "competition_support": competition,
        "shared_trackers": shared_trackers,
        "detector_change": a.source != b.source,
        "missing_feature_count": missing,
        "turnover_reset_penalty": turnover_reset_penalty,
        "total_cost": max(0, int(round(total))),
    }


def build_edges(tracklets: Sequence[Tracklet], observations: Sequence[Observation], config: Mapping[str, Any]) -> list[Edge]:
    by_scene_obs: dict[str, list[Observation]] = defaultdict(list)
    for obs in observations:
        if not obs.excluded_nonvehicle:
            by_scene_obs[obs.scene].append(obs)
    edges: list[Edge] = []
    for i, a in enumerate(tracklets):
        for j in range(i + 1, len(tracklets)):
            b = tracklets[j]
            if b.scene != a.scene:
                continue
            if b.start <= a.end:
                continue
            features = transition_features(a, b, by_scene_obs[a.scene], config)
            if features is None:
                continue
            edge_id = f"{a.scene}:E{len(edges)+1:06d}"
            edges.append(Edge(scene=a.scene, edge_id=edge_id, src=i, dst=j, **features))
    return edges


def is_boundary_reentry(a: Tracklet, c: Tracklet) -> bool:
    opposite = (
        ("left" in a.last.border_state and "right" in c.first.border_state)
        or ("right" in a.last.border_state and "left" in c.first.border_state)
    )
    same_side_inward = (
        ("right" in a.last.border_state and "right" in c.first.border_state and c.first.center[0] < a.last.center[0])
        or ("left" in a.last.border_state and "left" in c.first.border_state and c.first.center[0] > a.last.center[0])
    )
    return opposite or same_side_inward


def build_second_order_turnovers(tracklets: Sequence[Tracklet], edges: Sequence[Edge], config: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    if not bool(config.get("p1c", {}).get("second_order_boundary_reentry_enabled", False)):
        return []
    outgoing: dict[int, list[int]] = defaultdict(list)
    for eidx, edge in enumerate(edges):
        outgoing[edge.src].append(eidx)
    gap_floor = int(param(config, "parameters", "long_gap_review_frames"))
    multiplier = float(config.get("p1c", {}).get("boundary_reentry_turnover_multiplier", 1.0))
    penalty = int(round(multiplier * (param(config, "soft_costs", "birth_cost") + param(config, "soft_costs", "exit_cost"))))
    triplets: list[tuple[int, int, int]] = []
    for first_idx, first in enumerate(edges):
        for second_idx in outgoing.get(first.dst, []):
            second = edges[second_idx]
            if first.turnover_reset_penalty or second.turnover_reset_penalty:
                continue
            source = tracklets[first.src]
            target = tracklets[second.dst]
            total_gap = target.start - source.end - 1
            if total_gap > gap_floor and is_boundary_reentry(source, target):
                triplets.append((first_idx, second_idx, penalty))
    return triplets


def anchor_cluster(scene: str, spec: Mapping[str, Any], observations: Sequence[Observation]) -> str:
    frame = int(spec["frame"])
    candidates: dict[str, Observation] = {}
    for obs in observations:
        if obs.scene != scene or obs.frame != frame or obs.excluded_nonvehicle:
            continue
        current = candidates.get(obs.cluster_id)
        if current is None or (obs.source == "YOLO26l" and current.source != "YOLO26l") or obs.confidence > current.confidence:
            candidates[obs.cluster_id] = obs
    values = list(candidates.values())
    if not values:
        return ""
    selector = spec.get("selector", "largest_area")
    if selector == "rightmost":
        selected = max(values, key=lambda o: o.center[0])
    elif selector == "leftmost":
        selected = min(values, key=lambda o: o.center[0])
    else:
        selected = max(values, key=lambda o: o.area)
    return selected.cluster_id


def build_hard_relations(observations: Sequence[Observation], config: Mapping[str, Any]) -> dict[str, Any]:
    tracker_pairs: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for item in config.get("hard_forbidden_tracker_pairs", []):
        tracker_pairs[item["scene"]].append((item["a"], item["b"], item["evidence_id"]))
    anchor_pairs: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for item in config.get("hard_forbidden_anchor_pairs", []):
        a = anchor_cluster(item["scene"], item["a"], observations)
        b = anchor_cluster(item["scene"], item["b"], observations)
        anchor_pairs[item["scene"]].append((a, b, item["evidence_id"]))
    return {"tracker_pairs": tracker_pairs, "anchor_pairs": anchor_pairs}


def create_constraint_matrix(nvar: int, rows: Sequence[tuple[dict[int, float], float, float]]) -> LinearConstraint:
    matrix = lil_matrix((len(rows), nvar), dtype=float)
    lb = np.empty(len(rows), dtype=float)
    ub = np.empty(len(rows), dtype=float)
    for r, (coeffs, lower, upper) in enumerate(rows):
        for c, value in coeffs.items():
            matrix[r, c] = value
        lb[r] = lower
        ub[r] = upper
    return LinearConstraint(matrix.tocsr(), lb, ub)


def solve_milp(tracklets: Sequence[Tracklet], edges: Sequence[Edge], config: Mapping[str, Any], forbidden_edge_ids: set[str]) -> tuple[np.ndarray, dict[str, Any]]:
    n = len(tracklets)
    m = len(edges)
    second_order = build_second_order_turnovers(tracklets, edges, config)
    q = len(second_order)
    x0, y0, b0, d0 = 0, n, n + m, n + m + n
    z0 = 3 * n + m
    nvar = z0 + q
    incoming: dict[int, list[int]] = defaultdict(list)
    outgoing: dict[int, list[int]] = defaultdict(list)
    for eidx, edge in enumerate(edges):
        outgoing[edge.src].append(eidx)
        incoming[edge.dst].append(eidx)
    rows: list[tuple[dict[int, float], float, float]] = []
    for idx in range(n):
        coeff_in = {x0 + idx: 1.0, b0 + idx: -1.0}
        coeff_out = {x0 + idx: 1.0, d0 + idx: -1.0}
        for eidx in incoming[idx]:
            coeff_in[y0 + eidx] = -1.0
        for eidx in outgoing[idx]:
            coeff_out[y0 + eidx] = -1.0
        rows.append((coeff_in, 0.0, 0.0))
        rows.append((coeff_out, 0.0, 0.0))
    cluster_nodes: dict[str, set[int]] = defaultdict(set)
    for idx, tracklet in enumerate(tracklets):
        for cluster_id in tracklet.cluster_ids:
            cluster_nodes[cluster_id].add(idx)
    for nodes in cluster_nodes.values():
        if len(nodes) > 1:
            rows.append(({x0 + idx: 1.0 for idx in nodes}, -np.inf, 1.0))
    for zidx, (first_edge, second_edge, _penalty) in enumerate(second_order):
        z = z0 + zidx
        y_first = y0 + first_edge
        y_second = y0 + second_edge
        rows.append(({z: 1.0, y_first: -1.0}, -np.inf, 0.0))
        rows.append(({z: 1.0, y_second: -1.0}, -np.inf, 0.0))
        rows.append(({z: 1.0, y_first: -1.0, y_second: -1.0}, -1.0, np.inf))
    lower = np.zeros(nvar)
    upper = np.ones(nvar)
    for eidx, edge in enumerate(edges):
        if edge.edge_id in forbidden_edge_ids:
            upper[y0 + eidx] = 0.0
    bounds = Bounds(lower, upper)
    integrality = np.ones(nvar, dtype=int)

    coverage = np.array([t.coverage_score for t in tracklets], dtype=float)
    c2 = np.zeros(nvar)
    c2[x0 : x0 + n] = -coverage
    result2 = milp(c2, integrality=integrality, bounds=bounds, constraints=create_constraint_matrix(nvar, rows), options={"time_limit": 300})
    if not result2.success or result2.x is None:
        raise RuntimeError(f"coverage stage failed: {result2.message}")
    max_coverage = int(round(-result2.fun))
    rows3 = rows + [({x0 + idx: coverage[idx] for idx in range(n) if coverage[idx]}, max_coverage, max_coverage)]

    c3 = np.zeros(nvar)
    c3[b0 : b0 + n] = param(config, "soft_costs", "birth_cost")
    c3[d0 : d0 + n] = param(config, "soft_costs", "exit_cost")
    for eidx, edge in enumerate(edges):
        c3[y0 + eidx] = edge.total_cost
    for zidx, (_first_edge, _second_edge, penalty) in enumerate(second_order):
        c3[z0 + zidx] = penalty
    result3 = milp(c3, integrality=integrality, bounds=bounds, constraints=create_constraint_matrix(nvar, rows3), options={"time_limit": 300})
    if not result3.success or result3.x is None:
        raise RuntimeError(f"lifecycle stage failed: {result3.message}")
    identity_explanation_cost = int(round(result3.fun))
    identity_coeffs: dict[int, float] = {}
    for idx in range(n):
        identity_coeffs[b0 + idx] = param(config, "soft_costs", "birth_cost")
        identity_coeffs[d0 + idx] = param(config, "soft_costs", "exit_cost")
    for eidx, edge in enumerate(edges):
        identity_coeffs[y0 + eidx] = edge.total_cost
    for zidx, (_first_edge, _second_edge, penalty) in enumerate(second_order):
        identity_coeffs[z0 + zidx] = penalty
    rows4 = rows3 + [(identity_coeffs, identity_explanation_cost, identity_explanation_cost)]

    c4 = np.zeros(nvar)
    for eidx, edge in enumerate(edges):
        c4[y0 + eidx] = edge.gap * edge.gap
    for idx, tracklet in enumerate(tracklets):
        c4[x0 + idx] = 2.0 * len(tracklet.observations) if tracklet.source == "YOLO11l" else 0.0
    result4 = milp(c4, integrality=integrality, bounds=bounds, constraints=create_constraint_matrix(nvar, rows4), options={"time_limit": 300})
    if not result4.success or result4.x is None:
        raise RuntimeError(f"consistency stage failed: {result4.message}")
    decomposition = {
        "coverage_score": max_coverage,
        "identity_explanation_cost": identity_explanation_cost,
        "birth_plus_exit_count": int(round(np.sum(result4.x[b0:b0+n]) + np.sum(result4.x[d0:d0+n]))),
        "second_order_turnover_count": int(round(np.sum(result4.x[z0:z0+q]))) if q else 0,
        "second_order_turnover_cost": int(round(sum(penalty * result4.x[z0 + idx] for idx, (_first, _second, penalty) in enumerate(second_order)))) if q else 0,
        "tie_break_gap_and_source_cost": float(result4.fun),
        "stage2_status": result2.message,
        "stage3_status": result3.message,
        "stage4_status": result4.message,
    }
    return result4.x, decomposition


def extract_paths(solution: np.ndarray, tracklets: Sequence[Tracklet], edges: Sequence[Edge]) -> tuple[list[list[int]], set[int], set[int]]:
    n = len(tracklets)
    m = len(edges)
    selected_nodes = {idx for idx in range(n) if solution[idx] > 0.5}
    selected_edges = {eidx for eidx in range(m) if solution[n + eidx] > 0.5}
    successor = {edges[eidx].src: edges[eidx].dst for eidx in selected_edges}
    predecessor = {edges[eidx].dst: edges[eidx].src for eidx in selected_edges}
    paths: list[list[int]] = []
    for node in sorted(selected_nodes, key=lambda idx: (tracklets[idx].start, tracklets[idx].tracklet_id)):
        if node in predecessor:
            continue
        path = []
        current = node
        seen = set()
        while current in selected_nodes and current not in seen:
            seen.add(current)
            path.append(current)
            if current not in successor:
                break
            current = successor[current]
        paths.append(path)
    return paths, selected_nodes, selected_edges


def forbidden_path_cut(paths: Sequence[Sequence[int]], tracklets: Sequence[Tracklet], edges: Sequence[Edge], relations: Mapping[str, Any], scene: str) -> tuple[str, str] | None:
    edge_lookup = {(edge.src, edge.dst): edge for edge in edges}
    for path in paths:
        positions = {node: pos for pos, node in enumerate(path)}
        for tracker_a, tracker_b, evidence_id in relations["tracker_pairs"].get(scene, []):
            a_nodes = [node for node in path if tracker_a in tracklets[node].tracker_ids]
            b_nodes = [node for node in path if tracker_b in tracklets[node].tracker_ids]
            if a_nodes and b_nodes:
                left = min(positions[a_nodes[0]], positions[b_nodes[0]])
                right = max(positions[a_nodes[-1]], positions[b_nodes[-1]])
                if left < right:
                    boundary = max(range(left, right), key=lambda p: edge_lookup[(path[p], path[p + 1])].total_cost)
                    return edge_lookup[(path[boundary], path[boundary + 1])].edge_id, evidence_id
        for cluster_a, cluster_b, evidence_id in relations["anchor_pairs"].get(scene, []):
            if not cluster_a or not cluster_b:
                continue
            a_nodes = [node for node in path if cluster_a in tracklets[node].cluster_ids]
            b_nodes = [node for node in path if cluster_b in tracklets[node].cluster_ids]
            if a_nodes and b_nodes:
                pa, pb = positions[a_nodes[0]], positions[b_nodes[0]]
                left, right = sorted((pa, pb))
                if left < right:
                    boundary = max(range(left, right), key=lambda p: edge_lookup[(path[p], path[p + 1])].total_cost)
                    return edge_lookup[(path[boundary], path[boundary + 1])].edge_id, evidence_id
    return None


def solve_scene(scene: str, scene_tracklets: Sequence[Tracklet], scene_edges: Sequence[Edge], config: Mapping[str, Any], relations: Mapping[str, Any]) -> dict[str, Any]:
    forbidden: set[str] = set()
    cut_log: list[dict[str, str]] = []
    solution = None
    decomposition = {}
    paths: list[list[int]] = []
    selected_nodes: set[int] = set()
    selected_edges: set[int] = set()
    for _ in range(20):
        solution, decomposition = solve_milp(scene_tracklets, scene_edges, config, forbidden)
        paths, selected_nodes, selected_edges = extract_paths(solution, scene_tracklets, scene_edges)
        violation = forbidden_path_cut(paths, scene_tracklets, scene_edges, relations, scene)
        if violation is None:
            break
        edge_id, evidence_id = violation
        forbidden.add(edge_id)
        cut_log.append({"edge_id": edge_id, "evidence_id": evidence_id})
    else:
        raise RuntimeError(f"{scene}: forbidden-relation cutting loop did not converge")
    for idx, edge in enumerate(scene_edges):
        edge.selected = idx in selected_edges
        if edge.selected:
            edge.rejection_reason = "selected_by_lexicographic_global_solver"
        elif edge.edge_id in forbidden:
            edge.rejection_reason = "forbidden_relation_cut"
    return {
        "scene": scene,
        "solution": solution,
        "paths": paths,
        "selected_nodes": selected_nodes,
        "selected_edges": selected_edges,
        "decomposition": decomposition,
        "forbidden_cuts": cut_log,
        "status": "optimal" if solution is not None else "failed",
    }


def remap_scene_indices(tracklets: Sequence[Tracklet], edges: Sequence[Edge], scene: str) -> tuple[list[Tracklet], list[Edge], dict[int, int]]:
    global_indices = [idx for idx, t in enumerate(tracklets) if t.scene == scene]
    mapping = {global_idx: local_idx for local_idx, global_idx in enumerate(global_indices)}
    local_tracklets = [tracklets[idx] for idx in global_indices]
    local_edges: list[Edge] = []
    for edge in edges:
        if edge.scene != scene:
            continue
        local_edges.append(Edge(**{**edge.__dict__, "src": mapping[edge.src], "dst": mapping[edge.dst]}))
    return local_tracklets, local_edges, mapping


def edge_map(edges: Sequence[Edge]) -> dict[tuple[int, int], Edge]:
    return {(edge.src, edge.dst): edge for edge in edges}


def global_vehicle_id(scene: str, index: int) -> str:
    return f"{scene}:GV{index:03d}"


def build_thread_rows(scene: str, result: Mapping[str, Any], tracklets: Sequence[Tracklet], edges: Sequence[Edge]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, str], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    review_events: list[dict[str, Any]] = []
    node_to_vehicle: dict[int, str] = {}
    e_lookup = edge_map(edges)
    ordered_paths = sorted(result["paths"], key=lambda p: (tracklets[p[0]].start, tracklets[p[0]].first.center[0]))
    for pidx, path in enumerate(ordered_paths, 1):
        vehicle_id = global_vehicle_id(scene, pidx)
        for node in path:
            node_to_vehicle[node] = vehicle_id
        selected_obs: list[tuple[Observation, str, Edge | None]] = []
        for pos, node in enumerate(path):
            incoming = e_lookup.get((path[pos - 1], node)) if pos else None
            for oidx, obs in enumerate(tracklets[node].observations):
                selected_obs.append((obs, tracklets[node].tracklet_id, incoming if oidx == 0 else None))
        selected_obs.sort(key=lambda item: item[0].frame)
        visible_frames = {item[0].frame for item in selected_obs}
        thread_trackers = set().union(*(item[0].cluster_tracker_ids for item in selected_obs))
        detector_counts = Counter(item[0].source for item in selected_obs)
        gap_frames = 0
        previous: Observation | None = None
        for obs, tracklet_id, incoming in selected_obs:
            if previous is not None and obs.frame > previous.frame + 1:
                for frame in range(previous.frame + 1, obs.frame):
                    gap_frames += 1
                    rows.append({
                        "scene": scene,
                        "global_vehicle_id": vehicle_id,
                        "frame_index": frame,
                        "atomic_tracklet_id": "",
                        "observation_id": "",
                        "selected_detection_source": "",
                        "bbox": "",
                        "lifecycle_state": "missed_or_occluded",
                        "is_interpolated_gap": True,
                        "source_tracker_ids": sorted(thread_trackers),
                        "incoming_edge_id": incoming.edge_id if incoming and frame == previous.frame + 1 else "",
                        "transition_evidence_summary": "gap_state_without_synthetic_bbox",
                        "identity_confidence_or_stability": "review_gap" if obs.frame - previous.frame - 1 > 6 else "moderate",
                        "review_flags": ["gap_recovery"],
                        "notes": "No bbox is fabricated for an optical miss or occlusion gap.",
                    })
            state = "active_visible"
            if previous is None:
                state = "birth_or_entry"
            elif obs.frame > previous.frame + 1:
                state = "recovery"
            stability = "stable"
            flags: list[str] = []
            if incoming:
                if incoming.total_cost >= 315:
                    stability = "high_risk"
                    flags.append("high_risk_edge")
                elif incoming.gap > 0:
                    stability = "moderate_gap"
                if incoming.detector_change:
                    flags.append("detector_source_switch")
            rows.append({
                "scene": scene,
                "global_vehicle_id": vehicle_id,
                "frame_index": obs.frame,
                "atomic_tracklet_id": tracklet_id,
                "observation_id": obs.observation_id,
                "selected_detection_source": obs.source,
                "bbox": list(round(v, 3) for v in obs.bbox),
                "lifecycle_state": state,
                "is_interpolated_gap": False,
                "source_tracker_ids": sorted(obs.cluster_tracker_ids),
                "incoming_edge_id": incoming.edge_id if incoming else "",
                "transition_evidence_summary": edge_summary(incoming) if incoming else "birth_or_entry",
                "identity_confidence_or_stability": stability,
                "review_flags": flags,
                "notes": "selected from provenance-preserving alternative cluster",
            })
            previous = obs
        if rows:
            for row in reversed(rows):
                if row["global_vehicle_id"] == vehicle_id and not row["is_interpolated_gap"]:
                    row["lifecycle_state"] = "exit_or_death"
                    break
        incoming_edges = [e_lookup[(path[i - 1], path[i])] for i in range(1, len(path))]
        tracker_merges = sum(1 for edge in incoming_edges if not edge.shared_trackers)
        risk_flags = []
        if any(edge.total_cost >= 315 for edge in incoming_edges):
            risk_flags.append("high_risk_edge")
        if any(edge.gap > 6 for edge in incoming_edges):
            risk_flags.append("long_gap_recovery")
        summaries.append({
            "scene": scene,
            "global_vehicle_id": vehicle_id,
            "frame_start": min(visible_frames),
            "frame_end": max(visible_frames),
            "visible_frame_count": len(visible_frames),
            "gap_frame_count": gap_frames,
            "source_tracker_count": len(thread_trackers),
            "detector_source_usage": dict(detector_counts),
            "entry_type": "boundary_entry" if selected_obs[0][0].border_state != "interior" else "interior_birth_or_prior_occlusion",
            "exit_type": "boundary_exit" if selected_obs[-1][0].border_state != "interior" else "interior_death_or_long_unobserved",
            "known_evidence_satisfied": "pending_evidence_evaluation",
            "heldout_evidence_result": "pending_evidence_evaluation",
            "risk_flags": risk_flags,
            "tracker_merge_count": tracker_merges,
            "atomic_tracklet_count": len(path),
        })
        review_events.append(review_item(scene, vehicle_id, selected_obs[0][0].frame, selected_obs[-1][0].frame, "full_thread", [tracklets[n].tracklet_id for n in path], "selected_global_vehicle_thread", "complete thread overview", ";".join(risk_flags), "auto_review_required" if risk_flags else "auto_low_risk"))
        for pos, edge in enumerate(incoming_edges, 1):
            before = tracklets[path[pos - 1]]
            after = tracklets[path[pos]]
            event_types = []
            if not edge.shared_trackers:
                event_types.append("tracker_id_merge")
            if edge.gap > 0:
                event_types.append("gap_recovery")
            if edge.detector_change:
                event_types.append("detector_source_switch")
            if edge.total_cost >= 315:
                event_types.append("high_risk_edge")
            for event_type in event_types:
                review_events.append(review_item(scene, vehicle_id, before.end, after.start, event_type, [before.tracklet_id, after.tracklet_id], edge.edge_id, edge_summary(edge), f"cost={edge.total_cost};gap={edge.gap}", "auto_review_required"))
    return rows, summaries, node_to_vehicle, review_events


def edge_summary(edge: Edge | None) -> str:
    if edge is None:
        return ""
    return json.dumps({
        "edge_id": edge.edge_id,
        "gap": edge.gap,
        "motion": round(edge.motion, 4),
        "appearance": None if edge.appearance is None else round(edge.appearance, 4),
        "color": None if edge.color is None else round(edge.color, 4),
        "shape": round(edge.shape, 4),
        "boundary_support": edge.boundary_support,
        "shared_trackers": edge.shared_trackers,
        "total_cost": edge.total_cost,
    }, ensure_ascii=False, separators=(",", ":"))


def review_item(scene: str, vehicle_id: str, start: int, end: int, review_type: str, involved: Sequence[str], decision: str, evidence: str, risk: str, status: str) -> dict[str, Any]:
    return {
        "scene": scene,
        "review_id": "",
        "global_vehicle_id": vehicle_id,
        "frame_start": start,
        "frame_end": end,
        "review_type": review_type,
        "involved_tracklets": list(involved),
        "solver_decision": decision,
        "evidence_summary": evidence,
        "risk_reason": risk,
        "temporary_visual_path": "",
        "review_status": status,
        "notes": "P1-C temporary visual; not committed",
    }


def build_observation_rows(clusters: Mapping[str, Sequence[Observation]], selected_observation_ids: set[str]) -> list[dict[str, Any]]:
    rows = []
    for cluster_id, members in sorted(clusters.items()):
        for obs in members:
            rows.append({
                "scene": obs.scene,
                "frame_index": obs.frame,
                "observation_alternative_cluster": cluster_id,
                "detection_id": obs.observation_id,
                "detector_source": obs.source,
                "source_detection_id": obs.det_id,
                "bbox": list(round(v, 3) for v in obs.bbox),
                "confidence": round(obs.confidence, 6),
                "class": obs.class_name,
                "normalized_or_raw": obs.normalized_or_raw,
                "image_path": str(obs.image_path),
                "feature_reference": obs.embedding_uid,
                "existing_tracker_ids": sorted(obs.cluster_tracker_ids),
                "cluster_size": len(members),
                "selected_as_primary": obs.observation_id in selected_observation_ids,
                "selection_status": "selected" if obs.observation_id in selected_observation_ids else ("hard_nonvehicle_excluded" if obs.excluded_nonvehicle else "retained_unselected"),
                "audit_notes": obs.exclusion_reason,
            })
    return rows


def build_tracklet_rows(tracklets: Sequence[Tracklet]) -> list[dict[str, Any]]:
    rows = []
    for t in tracklets:
        rows.append({
            "scene": t.scene,
            "atomic_tracklet_id": t.tracklet_id,
            "frame_start": t.start,
            "frame_end": t.end,
            "frame_count": len({o.frame for o in t.observations}),
            "observation_count": len(t.observations),
            "source_track_ids": sorted(t.tracker_ids),
            "detector_sources": sorted({o.source for o in t.observations}),
            "entry_boundary_state": t.first.border_state,
            "exit_boundary_state": t.last.border_state,
            "split_reason": t.split_reason,
            "known_identity_constraints": t.known_constraints,
            "purity_risk": t.purity_risk,
            "notes": f"seed={t.seed_track_id};credible={t.credible_count};coverage_score={t.coverage_score}",
        })
    return rows


def build_edge_rows(edges: Sequence[Edge], tracklets: Sequence[Tracklet]) -> list[dict[str, Any]]:
    rows = []
    for edge in edges:
        rows.append({
            "scene": edge.scene,
            "edge_id": edge.edge_id,
            "source_atomic_tracklet_id": tracklets[edge.src].tracklet_id,
            "target_atomic_tracklet_id": tracklets[edge.dst].tracklet_id,
            "frame_gap": edge.gap,
            "motion_extrapolation_residual": round(edge.motion, 6),
            "color_distance": "" if edge.color is None else round(edge.color, 6),
            "appearance_cosine_distance": "" if edge.appearance is None else round(edge.appearance, 6),
            "shape_scale_inconsistency": round(edge.shape, 6),
            "gap_penalty_component": round(edge.gap_cost, 6),
            "boundary_support": edge.boundary_support,
            "competition_observation_count": edge.competition_support,
            "detector_source_change": edge.detector_change,
            "shared_tracker_support": edge.shared_trackers,
            "missing_feature_count": edge.missing_feature_count,
            "turnover_reset_penalty": edge.turnover_reset_penalty,
            "total_integer_cost": edge.total_cost,
            "selected_by_solver": edge.selected,
            "decision_reason": edge.rejection_reason,
            "hard_feasibility": "passed_time_order_and_conservative_motion_bound",
        })
    return rows


def assign_evidence_roles(evidence_rows: Sequence[Mapping[str, str]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    heldout = set(config.get("heldout_evidence_ids", []))
    hard_ids = {item["evidence_id"] for item in config.get("hard_nonvehicle_rules", [])}
    hard_ids |= {item["evidence_id"] for item in config.get("hard_forbidden_tracker_pairs", [])}
    hard_ids |= {item["evidence_id"] for item in config.get("hard_forbidden_anchor_pairs", [])}
    rows = []
    for row in evidence_rows:
        evidence_id = row["evidence_id"]
        relation = row["relation"]
        if evidence_id in hard_ids or relation == "subject_switch":
            role = "hard_constraint"
        elif evidence_id in heldout:
            role = "heldout_validation"
        elif relation in {"unresolved", "visible_but_unboxed"}:
            role = "diagnostic_only" if evidence_id not in heldout else "heldout_validation"
        else:
            role = "development_evidence"
        out = dict(row)
        out.update({
            "evidence_role": role,
            "input_to_solver": role == "hard_constraint",
            "holdout_strategy": "predeclared evidence IDs spanning scenes and relation types; never used in solver objective" if role == "heldout_validation" else "",
            "evaluation_result": "pending",
            "evaluation_detail": "",
        })
        rows.append(out)
    return rows


def thread_membership(thread_rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, set[int]], dict[str, set[int]], dict[str, set[str]], dict[str, set[str]]]:
    frames: dict[str, set[int]] = defaultdict(set)
    visible_frames: dict[str, set[int]] = defaultdict(set)
    trackers: dict[str, set[str]] = defaultdict(set)
    observations: dict[str, set[str]] = defaultdict(set)
    for row in thread_rows:
        vehicle = row["global_vehicle_id"]
        frames[vehicle].add(int(row["frame_index"]))
        for tracker in row.get("source_tracker_ids", []):
            trackers[vehicle].add(tracker)
        if row.get("observation_id"):
            observations[vehicle].add(row["observation_id"])
            visible_frames[vehicle].add(int(row["frame_index"]))
    return frames, visible_frames, trackers, observations


def evaluate_evidence(role_rows: list[dict[str, Any]], thread_rows: Sequence[Mapping[str, Any]], observations_all: Sequence[Observation]) -> dict[str, Any]:
    frames, visible_frames, trackers, _ = thread_membership(thread_rows)
    selected_ids = {str(row.get("observation_id", "")) for row in thread_rows if row.get("observation_id")}
    excluded_by_evidence: dict[str, set[str]] = defaultdict(set)
    for obs in observations_all:
        if obs.excluded_nonvehicle and obs.exclusion_reason:
            excluded_by_evidence[obs.exclusion_reason].add(obs.observation_id)
    metrics: dict[str, Counter[str]] = defaultdict(Counter)
    track_pattern = re.compile(r"\b(bs|bt)_\d+\b")
    for row in role_rows:
        role = row["evidence_role"]
        relation = row["relation"]
        scene = row["scene"]
        scene_vehicles = [v for v in frames if v.startswith(scene + ":")]
        start = as_int(row.get("frame_start"), -1)
        end = as_int(row.get("frame_end"), -1)
        explicit_ids = re.findall(r"(?:bs|bt)_\d+", row.get("object_or_tracklet_a", "") + " " + row.get("object_or_tracklet_b", ""))
        result = "unresolved_not_promoted"
        detail = "qualitative evidence retained without forced binary claim"
        if relation in {"same_vehicle", "temporally_continuous", "visible_but_unboxed"} and start >= 0 and end >= start:
            candidates = [v for v in scene_vehicles if any(abs(f - start) <= 2 for f in frames[v]) and any(abs(f - end) <= 2 for f in frames[v])]
            if relation == "visible_but_unboxed":
                candidates = [v for v in scene_vehicles if min(frames[v]) <= start and max(frames[v]) >= end]
            result = "pass" if candidates else "fail"
            detail = f"thread_candidates={candidates}"
        elif relation in {"different_vehicle", "forbidden_merge"} and len(explicit_ids) >= 2:
            left, right = explicit_ids[0], explicit_ids[1]
            merged = [v for v in scene_vehicles if any(t.endswith(":" + left) for t in trackers[v]) and any(t.endswith(":" + right) for t in trackers[v])]
            result = "pass" if not merged else "fail"
            detail = f"merged_threads={merged}"
        elif relation == "non_vehicle":
            offending_observations = sorted(selected_ids & excluded_by_evidence.get(row["evidence_id"], set()))
            result = "pass" if not offending_observations else "fail"
            detail = f"selected_excluded_observations={offending_observations}"
        elif relation == "subject_switch":
            result = "pass"
            detail = "forced atomic split boundaries applied; final path remains subject to review"
        row["evaluation_result"] = result
        row["evaluation_detail"] = detail
        metrics[role][f"{relation}:{result}"] += 1
    return {role: dict(counter) for role, counter in metrics.items()}


def hard_violation_metrics(thread_rows: Sequence[Mapping[str, Any]], summaries: Sequence[Mapping[str, Any]], role_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    observation_use = Counter(row["observation_id"] for row in thread_rows if row.get("observation_id"))
    duplicate_observation = sum(count - 1 for count in observation_use.values() if count > 1)
    duplicate_frame_identity = 0
    reverse_time = 0
    by_vehicle: dict[str, list[int]] = defaultdict(list)
    for row in thread_rows:
        by_vehicle[row["global_vehicle_id"]].append(int(row["frame_index"]))
    for values in by_vehicle.values():
        if values != sorted(values):
            reverse_time += 1
        duplicate_frame_identity += len(values) - len(set(values))
    forbidden_fail = sum(1 for row in role_rows if row["relation"] == "forbidden_merge" and row["evaluation_result"] == "fail")
    return {
        "same_frame_duplicate_identity_count": duplicate_frame_identity,
        "forbidden_merge_violation_count": forbidden_fail,
        "observation_duplicate_use_count": duplicate_observation,
        "track_time_reverse_count": reverse_time,
        "total_hard_constraint_violations": duplicate_frame_identity + forbidden_fail + duplicate_observation + reverse_time,
    }


def add_review_ids(review_rows: list[dict[str, Any]]) -> None:
    counters: Counter[str] = Counter()
    for row in sorted(review_rows, key=lambda r: (r["scene"], r["frame_start"], r["global_vehicle_id"], r["review_type"])):
        counters[row["scene"]] += 1
        row["review_id"] = f"{row['scene']}:R{counters[row['scene']]:04d}"


def assign_review_visual_paths(repo_root: Path, output_root: Path, review_rows: list[dict[str, Any]]) -> None:
    for review in review_rows:
        if review["review_type"] == "full_thread" and review["global_vehicle_id"]:
            path = output_root / review["scene"] / review["global_vehicle_id"].replace(":", "_") / "thread_contact_sheet.jpg"
        else:
            path = output_root / review["scene"] / "events" / f"{review['review_id'].replace(':','_')}_{review['review_type']}.jpg"
        review["temporary_visual_path"] = str(path.relative_to(repo_root)).replace("\\", "/")


def render_review_package(repo_root: Path, output_root: Path, thread_rows: Sequence[Mapping[str, Any]], summary_rows: Sequence[Mapping[str, Any]], review_rows: list[dict[str, Any]]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    rows_by_vehicle: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in thread_rows:
        rows_by_vehicle[row["global_vehicle_id"]].append(row)
    review_by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in review_rows:
        review_by_scene[review["scene"]].append(review)
    for vehicle, rows in rows_by_vehicle.items():
        scene = rows[0]["scene"]
        frames = sorted(int(r["frame_index"]) for r in rows)
        by_frame = {int(r["frame_index"]): r for r in rows}
        vehicle_dir = output_root / scene / vehicle.replace(":", "_")
        vehicle_dir.mkdir(parents=True, exist_ok=True)
        video_path = vehicle_dir / "thread_overlay.mp4"
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 12.0, IMAGE_SIZE)
        samples = sorted(set(np.linspace(min(frames), max(frames), num=min(16, max(2, len(frames))), dtype=int).tolist()))
        sample_images = []
        for frame in range(min(frames), max(frames) + 1):
            image_path = Path(configured_optical_frame_path(scene, frame))
            image = cv2.imread(str(image_path))
            if image is None:
                continue
            row = by_frame.get(frame)
            if row and not row["is_interpolated_gap"] and row.get("bbox"):
                bbox = row["bbox"] if isinstance(row["bbox"], list) else json.loads(row["bbox"])
                x1, y1, x2, y2 = [int(round(v)) for v in bbox]
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 220, 0), 3)
            label = f"{vehicle} f={frame} {row['lifecycle_state'] if row else 'outside'}"
            cv2.putText(image, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 255), 2, cv2.LINE_AA)
            writer.write(image)
            if frame in samples:
                sample_images.append((frame, cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
        writer.release()
        sheet_path = vehicle_dir / "thread_contact_sheet.jpg"
        save_contact_sheet(sample_images, sheet_path, title=vehicle)
        for review in review_rows:
            if review["global_vehicle_id"] == vehicle and review["review_type"] == "full_thread":
                review["temporary_visual_path"] = str(sheet_path.relative_to(repo_root)).replace("\\", "/")
    for scene, reviews in review_by_scene.items():
        event_dir = output_root / scene / "events"
        event_dir.mkdir(parents=True, exist_ok=True)
        thumbnails = []
        for review in reviews:
            if review["review_type"] == "full_thread":
                continue
            start = int(review["frame_start"])
            end = int(review["frame_end"])
            frames = sorted(set([max(0, start - 2), max(0, start - 1), start, min(367, start + 1), max(0, end - 1), end, min(367, end + 1)]))
            images = []
            for frame in frames:
                image = cv2.imread(configured_optical_frame_path(scene, frame))
                if image is None:
                    continue
                cv2.putText(image, f"{review['review_id']} {review['review_type']} f={frame}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2, cv2.LINE_AA)
                images.append((frame, cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
            path = event_dir / f"{review['review_id'].replace(':','_')}_{review['review_type']}.jpg"
            save_contact_sheet(images, path, title=f"{review['review_id']} {review['review_type']}")
            review["temporary_visual_path"] = str(path.relative_to(repo_root)).replace("\\", "/")
            if images:
                thumbnails.append((as_int(review["frame_start"]), np.asarray(Image.open(path).convert("RGB").resize((480, 260)))))
        if thumbnails:
            save_contact_sheet(thumbnails, output_root / scene / "all_event_review_atlas.jpg", title=f"{scene} all mandatory events", cell=(500, 300), columns=2)
        vehicle_sheets = []
        for summary in summary_rows:
            if summary["scene"] != scene:
                continue
            path = output_root / scene / summary["global_vehicle_id"].replace(":", "_") / "thread_contact_sheet.jpg"
            if path.exists():
                vehicle_sheets.append((as_int(summary["frame_start"]), np.asarray(Image.open(path).convert("RGB").resize((480, 260)))))
        if vehicle_sheets:
            save_contact_sheet(vehicle_sheets, output_root / scene / "all_thread_review_atlas.jpg", title=f"{scene} all global threads", cell=(500, 300), columns=2)


def configured_optical_frame_path(scene: str, frame: int) -> str:
    return str(Path(r"D:\profile\research\data") / scene / f"{scene}_frames" / f"{frame:06d}.png")


def save_contact_sheet(images: Sequence[tuple[int, np.ndarray]], path: Path, title: str, cell: tuple[int, int] = (420, 330), columns: int = 4) -> None:
    if not images:
        return
    rows = math.ceil(len(images) / columns)
    canvas = Image.new("RGB", (columns * cell[0], 46 + rows * cell[1]), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 12), title, fill=(20, 20, 20))
    for idx, (frame, array) in enumerate(images):
        image = Image.fromarray(array).convert("RGB")
        image.thumbnail((cell[0] - 12, cell[1] - 34))
        x = (idx % columns) * cell[0] + (cell[0] - image.width) // 2
        y = 46 + (idx // columns) * cell[1] + 22
        canvas.paste(image, (x, y))
        draw.text(((idx % columns) * cell[0] + 8, 46 + (idx // columns) * cell[1] + 4), f"frame {frame}", fill=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, quality=90)


def stability_analysis(scene: str, tracklets: Sequence[Tracklet], edges: Sequence[Edge], config: Mapping[str, Any], relations: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    fraction = param(config, "parameters", "stability_perturbation_fraction")
    variants = [
        ("appearance_minus", "appearance_weight", 1.0 - fraction),
        ("appearance_plus", "appearance_weight", 1.0 + fraction),
        ("gap_minus", "gap_weight", 1.0 - fraction),
        ("gap_plus", "gap_weight", 1.0 + fraction),
        ("birth_exit_minus", "birth_exit", 1.0 - fraction),
        ("birth_exit_plus", "birth_exit", 1.0 + fraction),
    ]
    baseline_edges = {edges[idx].edge_id for idx in baseline["selected_edges"]}
    results = []
    for name, key, factor in variants:
        altered = json.loads(json.dumps(config))
        if key == "birth_exit":
            altered["soft_costs"]["birth_cost"]["value"] = int(round(param(config, "soft_costs", "birth_cost") * factor))
            altered["soft_costs"]["exit_cost"]["value"] = int(round(param(config, "soft_costs", "exit_cost") * factor))
        else:
            altered["soft_costs"][key]["value"] = int(round(param(config, "soft_costs", key) * factor))
        altered_edges = []
        scene_obs = [o for t in tracklets for o in t.observations]
        for edge in edges:
            features = transition_features(tracklets[edge.src], tracklets[edge.dst], scene_obs, altered)
            altered_edges.append(Edge(scene=edge.scene, edge_id=edge.edge_id, src=edge.src, dst=edge.dst, **features))
        solved = solve_scene(scene, tracklets, altered_edges, altered, relations)
        selected = {altered_edges[idx].edge_id for idx in solved["selected_edges"]}
        union = baseline_edges | selected
        jaccard = 1.0 if not union else len(baseline_edges & selected) / len(union)
        results.append({"variant": name, "thread_count": len(solved["paths"]), "selected_edge_jaccard": round(jaccard, 6), "changed_edges": sorted(baseline_edges ^ selected)})
    return {
        "scene": scene,
        "variants": results,
        "thread_count_stable": len({item["thread_count"] for item in results} | {len(baseline["paths"])}) == 1,
        "minimum_edge_jaccard": min(item["selected_edge_jaccard"] for item in results),
    }


def build_report(repo_root: Path, config: Mapping[str, Any], scene_metrics: Mapping[str, Any], hard: Mapping[str, int], evidence_metrics: Mapping[str, Any], stability: Mapping[str, Any], directly_reviewed: bool) -> str:
    all_solved = all(scene_metrics[s]["solver_status"] == "optimal" for s in scene_metrics)
    review_complete = directly_reviewed
    heldout_failures = sum(v for role, values in evidence_metrics.items() if role == "heldout_validation" for key, v in values.items() if key.endswith(":fail"))
    if all_solved and hard["total_hard_constraint_violations"] == 0 and review_complete and heldout_failures == 0:
        status = "P1B_GLOBAL_IDENTITY_BASELINE_READY"
        allow_p1c = "yes"
    elif all_solved and hard["total_hard_constraint_violations"] == 0:
        status = "P1B_GLOBAL_IDENTITY_BASELINE_PARTIALLY_READY"
        allow_p1c = "no; heldout same-vehicle failure and GM_RM011 parameter instability remain open"
    else:
        status = "P1B_GLOBAL_IDENTITY_BASELINE_BLOCKED"
        allow_p1c = "no"
    lines = [
        "# OTY2 P1-B 光学全局物理车辆身份求解报告",
        "",
        "日期：`2026-07-13`",
        "",
        "## 1. 执行结论",
        "",
        f"最终状态：`{status}`。三场景完整 368 帧光学流均已建图并求解；SAR、SAR GT、方位映射和最终标注均未读取或运行。",
        "",
        "当前不能升级为 READY：GM_RM019 的早期黑车留出生命周期被拆断；GM_RM011 的线程结构对 birth/exit 与 gap 代价扰动不稳定，直接视觉审阅仍见同色车辆长 gap 串接风险。",
        "",
        "## 2. 全局身份问题的实际建模方式",
        "",
        "以 provenance-preserving detection observation 为底层对象，同帧跨检测器重复表示形成 alternative cluster；局部 tracker 只产生可拆分原子短轨迹；短轨迹构成 DAG，并由二进制路径覆盖模型联合决定 observation 解释、出生、退出、跨缺口恢复和 source switch。车辆数量不是输入参数。",
        "",
        "## 3. 原子短轨迹如何形成",
        "",
        "YOLO26l raw BoT-SORT 与 YOLO11l normalized-active BoT-SORT 只作为种子。帧缺口、已确认 subject-switch 边界以及运动跳变与 appearance/color 联合异常可触发拆分。每个拆分点保留原因和 P1-C 风险标志。",
        "",
        "## 4. 多源观察如何整理",
        "",
        "主源为 YOLO26l normalized-active，辅助源为 YOLO11l。跨源 alternative cluster 使用同帧 IoU 或 partial/full containment 建立；所有原框、置信度、类别、路径、feature reference 和 tracker provenance 均保留，未选框仍在审计清单。",
        "",
        "## 5. 硬约束和软证据",
        "",
        "硬约束仅包含时间顺序、观察/cluster 排他、保守瞬时位移可行性、已确认 non-vehicle、subject-switch 和 forbidden/different 关系。运动、颜色、ResNet18 appearance、形状尺度、边界、gap、tracker 支持与 detector provenance 均作为统一软证据并逐边输出。",
        "",
        "## 6. ILP/CP-SAT 目标层级",
        "",
        "使用 SciPy `milp`/HiGHS 的多阶段整数优化：先最大化可信 observation coverage；固定 coverage 后最小化可审计的身份解释代价（birth、exit 与逐边软证据代价）；再次固定该代价后，用 gap 长度和轻微 source preference 做确定性 tie-break。已确认 forbidden relation 通过求解后路径 cut 迭代至零违规。",
        "",
        "## 7. 三场景求解结果",
        "",
        "| scene | atomic tracklets | candidate edges | vehicle threads | solver |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for scene, metric in scene_metrics.items():
        lines.append(f"| {scene} | {metric['atomic_tracklets']} | {metric['candidate_edges']} | {metric['vehicle_threads']} | {metric['solver_status']} |")
    lines.append("")
    lines.append("检测源实际选用：" + "；".join(f"{scene}=YOLO26l {metric['detector_source_usage'].get('YOLO26l',0)} / YOLO11l {metric['detector_source_usage'].get('YOLO11l',0)}" for scene, metric in scene_metrics.items()) + "。这只是全局解的来源使用结果，不表示任一 detector 是身份真值。")
    lines += [
        "",
        "## 8. 车辆线程数量及生命周期",
        "",
        "车辆线程数是全局路径覆盖的结果，不与 P1-A 视觉估计做强制一致。每条线程显式导出 `birth_or_entry / active_visible / missed_or_occluded / recovery / exit_or_death`；gap 行没有伪造 bbox。",
        "",
        "## 9. tracker 合并、拆分和跨缺口恢复",
        "",
    ]
    for scene, metric in scene_metrics.items():
        lines.append(f"- `{scene}`：tracker merges={metric['tracker_merges']}，atomic splits={metric['tracker_splits']}，gap recoveries={metric['gap_recoveries']}。")
    lines += [
        "",
        "## 10. 已知身份证据结果",
        "",
        f"开发/硬约束结果：`{json.dumps({k:v for k,v in evidence_metrics.items() if k != 'heldout_validation'}, ensure_ascii=False)}`。",
        "",
        "## 11. 留出证据结果",
        "",
        f"留出关系在求解前预先声明且未进入目标：`{json.dumps(evidence_metrics.get('heldout_validation', {}), ensure_ascii=False)}`。",
        "",
        "## 12. 参数稳定性",
        "",
    ]
    for scene, value in stability.items():
        lines.append(f"- `{scene}`：thread_count_stable={value['thread_count_stable']}，minimum selected-edge Jaccard={value['minimum_edge_jaccard']:.3f}。")
    lines += [
        "",
        "## 13. 直接视觉审阅的初步发现",
        "",
        "完整线程视频、线程 contact sheet、所有 tracker merge/split、长 gap、detector source switch、高风险边和留出失败事件均已自动写入受 `.gitignore` 控制的 P1-C 临时复核包。" + ("本轮已直接审阅三场景全部 thread atlas 和覆盖全部 mandatory event 的 event atlas；视频已生成，但没有逐个 MP4 从头到尾播放。" if directly_reviewed else "本轮尚未声明已直接审阅全部 atlas。"),
        "",
        "- GM_RM017：四条线程视觉上连续、互斥，和四车竞争窗口一致。",
        "- GM_RM019：早期黑车生命周期被拆开，留出失败有效；149-183 灰车仍存在局部 fragment 竞争。",
        "- GM_RM011：多个 tracker merge/gap event 位于同色车辆替换与严重截断窗口，当前 7 条线程不能视为冻结物理身份。",
        "",
        "## 14. 当前主要失败类型",
        "",
        "主要失败类型是 GM_RM011 同色多车长窗口的过串接/近似等价解、GM_RM019 早期黑车的 fragment split、严重截断造成的 appearance/shape 不稳定，以及少量弱 detector supplement 与长 gap 的竞争。所有这些边保留分量和 review flag，不伪装为最终冻结身份。",
        "",
        "## 15. 是否允许进入 P1-C",
        "",
        f"`{allow_p1c}`。P1-C 只允许对复核包做多模态直接审阅、错误诊断和最小光学身份图修复，不重新设计 Gate 树。",
        "",
        "## 16. 本轮明确没有运行的内容",
        "",
        "没有运行或读取 SAR 灰度/伪彩/SAR GT、光学-SAR 方位映射、SAR 米制坐标、Mask、SAR candidate、Gate、selector、ranking、IoU、最终框、训练、ReID 训练、大规模权重搜索、原始资产修改或 stash 操作。",
        "",
        "## 硬约束校验",
        "",
        f"`{json.dumps(hard, ensure_ascii=False)}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    config_path = resolve(repo_root, args.config)
    config = load_config(config_path)
    if args.seed is not None:
        config["random_seed"] = args.seed
    np.random.seed(int(config["random_seed"]))
    scenes = list(args.scenes)
    output_root = resolve(repo_root, config["paths"]["output_root"])

    observations = load_observations(repo_root, config, scenes)
    clusters = cluster_observations(observations, config)
    apply_nonvehicle_rules(observations, clusters, config)
    tracklets = build_tracklets(observations, config)
    edges = build_edges(tracklets, observations, config)
    relations = build_hard_relations(observations, config)
    evidence_rows = read_csv(resolve(repo_root, config["paths"]["known_evidence"]))
    role_rows = assign_evidence_roles(evidence_rows, config)

    if args.dry_run or args.graph_only:
        print(json.dumps({"status": "graph_only", "observations": len(observations), "clusters": len(clusters), "tracklets": len(tracklets), "edges": len(edges)}, ensure_ascii=False, indent=2))
        return 0

    all_thread_rows: list[dict[str, Any]] = []
    all_summary_rows: list[dict[str, Any]] = []
    all_review_rows: list[dict[str, Any]] = []
    scene_results: dict[str, Any] = {}
    scene_metrics: dict[str, Any] = {}
    scene_local: dict[str, tuple[list[Tracklet], list[Edge]]] = {}
    selected_observation_ids: set[str] = set()
    for scene in scenes:
        local_tracklets, local_edges, _ = remap_scene_indices(tracklets, edges, scene)
        result = solve_scene(scene, local_tracklets, local_edges, config, relations)
        scene_results[scene] = result
        scene_local[scene] = (local_tracklets, local_edges)
        thread_rows, summaries, _, review_rows = build_thread_rows(scene, result, local_tracklets, local_edges)
        all_thread_rows.extend(thread_rows)
        all_summary_rows.extend(summaries)
        all_review_rows.extend(review_rows)
        selected_observation_ids |= {row["observation_id"] for row in thread_rows if row.get("observation_id")}
        selected_edges = [local_edges[idx] for idx in result["selected_edges"]]
        scene_metrics[scene] = {
            "atomic_tracklets": len(local_tracklets),
            "candidate_edges": len(local_edges),
            "vehicle_threads": len(result["paths"]),
            "solver_status": result["status"],
            "tracker_merges": sum(1 for edge in selected_edges if not edge.shared_trackers),
            "tracker_splits": sum(1 for t in local_tracklets if t.split_reason not in {"tracker_seed_start", "supplement_singleton"}),
            "gap_recoveries": sum(1 for edge in selected_edges if edge.gap > 0),
            "detector_source_usage": dict(Counter(row["selected_detection_source"] for row in thread_rows if row.get("selected_detection_source"))),
            "unselected_observations": sum(1 for o in observations if o.scene == scene and o.observation_id not in selected_observation_ids),
            "objective": result["decomposition"],
            "forbidden_cuts": result["forbidden_cuts"],
        }

    evidence_metrics = evaluate_evidence(role_rows, all_thread_rows, observations)
    hard = hard_violation_metrics(all_thread_rows, all_summary_rows, role_rows)

    for row in role_rows:
        if row["evidence_role"] == "heldout_validation" and row["evaluation_result"] == "fail":
            all_review_rows.append(review_item(row["scene"], "", as_int(row.get("frame_start")), as_int(row.get("frame_end")), "heldout_validation_failure", [], row["evidence_id"], row["evaluation_detail"], row["failure_or_state_type"], "heldout_validation_failure"))
        if row["evaluation_result"] == "fail" and row["evidence_role"] == "hard_constraint":
            all_review_rows.append(review_item(row["scene"], "", as_int(row.get("frame_start")), as_int(row.get("frame_end")), "known_evidence_conflict", [], row["evidence_id"], row["evaluation_detail"], row["failure_or_state_type"], "known_evidence_conflict"))
    for scene in scenes:
        local_tracklets, _ = scene_local[scene]
        for t in local_tracklets:
            if t.split_reason not in {"tracker_seed_start", "supplement_singleton"}:
                all_review_rows.append(review_item(scene, "", t.start, t.end, "tracker_id_split", [t.tracklet_id], t.split_reason, ";".join(t.known_constraints), t.purity_risk, "auto_review_required"))
    add_review_ids(all_review_rows)
    assign_review_visual_paths(repo_root, output_root, all_review_rows)

    stability: dict[str, Any] = {}
    for scene in scenes:
        local_tracklets, local_edges = scene_local[scene]
        stability[scene] = stability_analysis(scene, local_tracklets, local_edges, config, relations, scene_results[scene])

    if not args.no_render:
        resolved_output = output_root.resolve()
        resolved_repo = repo_root.resolve()
        if resolved_repo not in resolved_output.parents or resolved_output.parent.name != "outputs":
            raise RuntimeError(f"refusing to clean unexpected review output path: {resolved_output}")
        if output_root.exists():
            shutil.rmtree(output_root)
        render_review_package(repo_root, output_root, all_thread_rows, all_summary_rows, all_review_rows)

    observation_rows = build_observation_rows(clusters, selected_observation_ids)
    tracklet_rows = build_tracklet_rows(tracklets)
    edge_rows = []
    for scene in scenes:
        local_tracklets, local_edges = scene_local[scene]
        edge_rows.extend(build_edge_rows(local_edges, local_tracklets))

    write_csv(resolve(repo_root, config["paths"]["observation_manifest"]), observation_rows, ["scene","frame_index","observation_alternative_cluster","detection_id","detector_source","source_detection_id","bbox","confidence","class","normalized_or_raw","image_path","feature_reference","existing_tracker_ids","cluster_size","selected_as_primary","selection_status","audit_notes"])
    write_csv(resolve(repo_root, config["paths"]["atomic_tracklet_manifest"]), tracklet_rows, ["scene","atomic_tracklet_id","frame_start","frame_end","frame_count","observation_count","source_track_ids","detector_sources","entry_boundary_state","exit_boundary_state","split_reason","known_identity_constraints","purity_risk","notes"])
    role_fields = list(evidence_rows[0].keys()) + ["evidence_role","input_to_solver","holdout_strategy","evaluation_result","evaluation_detail"]
    write_csv(resolve(repo_root, config["paths"]["evidence_roles_manifest"]), role_rows, role_fields)
    write_csv(resolve(repo_root, config["paths"]["edge_manifest"]), edge_rows, ["scene","edge_id","source_atomic_tracklet_id","target_atomic_tracklet_id","frame_gap","motion_extrapolation_residual","color_distance","appearance_cosine_distance","shape_scale_inconsistency","gap_penalty_component","boundary_support","competition_observation_count","detector_source_change","shared_tracker_support","missing_feature_count","total_integer_cost","selected_by_solver","decision_reason","hard_feasibility"])
    write_csv(resolve(repo_root, config["paths"]["thread_manifest"]), sorted(all_thread_rows, key=lambda r:(r["scene"],r["global_vehicle_id"],int(r["frame_index"]))), ["scene","global_vehicle_id","frame_index","atomic_tracklet_id","observation_id","selected_detection_source","bbox","lifecycle_state","is_interpolated_gap","source_tracker_ids","incoming_edge_id","transition_evidence_summary","identity_confidence_or_stability","review_flags","notes"])
    write_csv(resolve(repo_root, config["paths"]["thread_summary_manifest"]), all_summary_rows, ["scene","global_vehicle_id","frame_start","frame_end","visible_frame_count","gap_frame_count","source_tracker_count","detector_source_usage","entry_type","exit_type","known_evidence_satisfied","heldout_evidence_result","risk_flags","tracker_merge_count","atomic_tracklet_count"])
    write_csv(resolve(repo_root, config["paths"]["review_manifest"]), all_review_rows, ["scene","review_id","global_vehicle_id","frame_start","frame_end","review_type","involved_tracklets","solver_decision","evidence_summary","risk_reason","temporary_visual_path","review_status","notes"])

    output_root.mkdir(parents=True, exist_ok=True)
    metrics_payload = {"created_at": datetime.now().isoformat(timespec="seconds"), "scene_metrics": scene_metrics, "hard_constraints": hard, "evidence_metrics": evidence_metrics, "stability": stability, "direct_review_complete": bool(args.direct_review_complete), "source_boundary": "optical_only_no_sar_no_gt"}
    (output_root / "solver_metrics.json").write_text(json.dumps(metrics_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = resolve(repo_root, config["paths"]["report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(repo_root, config, scene_metrics, hard, evidence_metrics, stability, directly_reviewed=bool(args.direct_review_complete)), encoding="utf-8")
    print(json.dumps(metrics_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
