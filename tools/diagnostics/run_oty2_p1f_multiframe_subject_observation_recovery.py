#!/usr/bin/env python3
"""Build optical runtime observations, local subjects, unique selections, and flow recoveries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any

import cv2
import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs/oty2/oty2_p1f_multiframe_subject_observation.yaml"
SCENES = ("GM_RM011", "GM_RM017", "GM_RM019")
FRAME_COUNT = 368
IMAGE_WIDTH = 800
IMAGE_HEIGHT = 600

RUNTIME_FIELDS = [
    "scene", "frame_index", "runtime_observation_id", "detector_source", "source_detection_id",
    "bbox", "confidence", "class", "source_tracker_ids", "appearance_feature_reference",
    "color_feature_reference", "boundary_contact", "runtime_quality_features", "provenance", "notes",
]
CLUSTER_FIELDS = [
    "scene", "frame_index", "runtime_observation_cluster_id", "runtime_local_subject_id",
    "observation_ids", "detector_sources", "source_tracker_ids", "cluster_bbox", "consensus_bbox",
    "source_support_count", "mutual_iou_min", "union_expansion_ratio", "color_distance_max",
    "temporal_support_previous", "temporal_support_next", "multiple_motion_subject_risk",
    "partial_subject_risk", "possible_non_vehicle_risk", "baseline_b_selected_observation_id",
    "final_selected_observation_id", "cluster_quality_evidence", "notes",
]
SELECTED_FIELDS = [
    "scene", "frame_index", "runtime_local_subject_id", "selected_observation_id", "selection_status",
    "selection_evidence", "alternative_observation_ids", "detector_source", "bbox",
    "subject_quality_state", "runtime_confidence", "review_flags", "usable_for_motion",
    "usable_for_color", "usable_for_identity_appearance", "usable_for_shape", "diagnostic_only",
    "baseline_b_included", "baseline_c_included", "baseline_d_included", "notes",
]
RECOVERY_FIELDS = [
    "scene", "frame_index", "runtime_local_subject_id", "recovered_observation_id", "bbox",
    "recovery_method", "forward_seed_frame", "backward_seed_frame", "propagation_length",
    "forward_bbox", "backward_bbox", "bidirectional_consistency", "image_support_evidence",
    "motion_consistency", "scale_consistency", "conflict_with_other_subject",
    "runtime_recovery_confidence", "acceptance_status", "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def parse_json_list(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return [item for item in value.split(";") if item]


def bbox_json(box: tuple[float, float, float, float] | None) -> str:
    return "" if box is None else json.dumps([round(float(v), 3) for v in box], separators=(",", ":"))


def area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def intersection(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    inter = intersection(a, b)
    return inter / max(1e-9, area(a) + area(b) - inter)


def iom(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    return intersection(a, b) / max(1e-9, min(area(a), area(b)))


def center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return (0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3]))


def center_distance(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay = center(a)
    bx, by = center(b)
    scale = max(8.0, 0.5 * (math.sqrt(area(a)) + math.sqrt(area(b))))
    return math.hypot(ax - bx, ay - by) / scale


def clip_box(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x1 = min(float(IMAGE_WIDTH), max(0.0, box[0]))
    y1 = min(float(IMAGE_HEIGHT), max(0.0, box[1]))
    x2 = min(float(IMAGE_WIDTH), max(x1 + 1.0, box[2]))
    y2 = min(float(IMAGE_HEIGHT), max(y1 + 1.0, box[3]))
    return x1, y1, x2, y2


def union_box(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def boundary_contact(box: tuple[float, float, float, float]) -> str:
    contacts = []
    if box[0] <= 3:
        contacts.append("left")
    if box[2] >= IMAGE_WIDTH - 3:
        contacts.append("right")
    if box[1] <= 3:
        contacts.append("top")
    if box[3] >= IMAGE_HEIGHT - 3:
        contacts.append("bottom")
    return "+".join(contacts) if contacts else "none"


def color_distance(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 1.0
    hue = min(abs(a[0] - b[0]), 1.0 - abs(a[0] - b[0]))
    return min(1.0, math.sqrt((1.7 * hue) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) / 1.5)


def sha256_rows(rows: list[dict[str, Any]], fields: list[str]) -> str:
    payload = "\n".join("|".join(str(row.get(field, "")) for field in fields) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cv2.setRNGSeed(0)
    runtime_inputs = config["runtime_inputs"]
    outputs = config["outputs"]
    params = config["parameters"]
    frame_root = Path(runtime_inputs["optical_frame_root"])

    @lru_cache(maxsize=64)
    def load_frame(scene: str, frame: int) -> tuple[np.ndarray, np.ndarray]:
        path = frame_root / scene / f"{scene}_frames" / f"{frame:06d}.png"
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(path)
        return image, cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    p1c_rows = read_csv(ROOT / runtime_inputs["p1c_observation_manifest"])
    tracker_lookup: dict[tuple[str, str, str], list[str]] = {}
    p1c_cluster_lookup: dict[tuple[str, str, str], str] = {}
    for row in p1c_rows:
        key = (row["scene"], row["detector_source"], row["source_detection_id"])
        tracker_lookup[key] = sorted(parse_json_list(row.get("existing_tracker_ids", "")))
        p1c_cluster_lookup[key] = row.get("observation_alternative_cluster", "")

    quality = params["quality_evidence"]
    observations: list[dict[str, Any]] = []
    by_frame: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    observation_lookup: dict[str, dict[str, Any]] = {}

    for scene in SCENES:
        for source, path_value in runtime_inputs["normalized_detection_tables"][scene].items():
            for row in read_csv(Path(path_value)):
                frame = int(row["optical_frame_num"])
                box = clip_box(tuple(float(row[key]) for key in ("bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2")))
                image, gray = load_frame(scene, frame)
                x1, y1, x2, y2 = (int(round(v)) for v in box)
                patch = image[max(0, y1):min(IMAGE_HEIGHT, y2), max(0, x1):min(IMAGE_WIDTH, x2)]
                gray_patch = gray[max(0, y1):min(IMAGE_HEIGHT, y2), max(0, x1):min(IMAGE_WIDTH, x2)]
                if patch.size:
                    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
                    mean = hsv.reshape(-1, 3).mean(axis=0)
                    color = [float(mean[0] / 180.0), float(mean[1] / 255.0), float(mean[2] / 255.0)]
                    edges = cv2.Canny(gray_patch, 60, 150)
                    edge_density = float(np.count_nonzero(edges) / max(1, edges.size))
                    hist = cv2.calcHist([gray_patch], [0], None, [8], [0, 256]).reshape(-1)
                    hist = (hist / max(1.0, hist.sum())).tolist()
                else:
                    color, edge_density, hist = [0.0, 0.0, 0.0], 0.0, [0.0] * 8
                area_ratio = area(box) / float(IMAGE_WIDTH * IMAGE_HEIGHT)
                aspect = (box[2] - box[0]) / max(1.0, box[3] - box[1])
                area_plausibility = min(1.0, area_ratio / quality["minimum_vehicle_area_ratio"])
                if area_ratio > quality["maximum_vehicle_area_ratio"]:
                    area_plausibility *= quality["maximum_vehicle_area_ratio"] / area_ratio
                aspect_plausibility = 1.0 if quality["minimum_aspect_ratio"] <= aspect <= quality["maximum_aspect_ratio"] else 0.25
                structure_support = min(1.0, edge_density / 0.08)
                trackers = tracker_lookup.get((scene, source, row["det_id"]), [])
                tracker_support = min(1.0, len(trackers) / 2.0)
                confidence = float(row["confidence"])
                vehicle_likeness = min(1.0, 0.34 * confidence + 0.22 * area_plausibility + 0.14 * aspect_plausibility + 0.12 * structure_support + 0.18 * tracker_support)
                runtime_id = f"{scene}:{source}:{row['det_id']}"
                features = {
                    "area_ratio": round(area_ratio, 7), "aspect_ratio": round(aspect, 5),
                    "color_hsv_mean": [round(v, 6) for v in color], "gray_histogram_8": [round(float(v), 6) for v in hist],
                    "edge_density": round(edge_density, 6), "area_plausibility": round(area_plausibility, 6),
                    "aspect_plausibility": round(aspect_plausibility, 6), "structure_support": round(structure_support, 6),
                    "tracker_support": round(tracker_support, 6), "vehicle_likeness": round(vehicle_likeness, 6),
                }
                item = {
                    "scene": scene, "frame": frame, "id": runtime_id, "source": source, "source_id": row["det_id"],
                    "bbox_value": box, "confidence_value": confidence, "class": row.get("class_name", "car"),
                    "trackers": set(trackers), "color": color, "hist": hist, "edge_density": edge_density,
                    "area_ratio": area_ratio, "aspect": aspect, "vehicle_likeness": vehicle_likeness,
                    "boundary": boundary_contact(box), "active": truth(row.get("active_for_tracking", "false")),
                    "p1c_cluster": p1c_cluster_lookup.get((scene, source, row["det_id"]), ""),
                    "features": features, "normalization_action": row.get("normalization_action", ""),
                    "suppression_reason": row.get("suppression_reason", ""),
                }
                observations.append(item)
                by_frame[(scene, frame)].append(item)
                observation_lookup[runtime_id] = item

    runtime_rows = [{
        "scene": item["scene"], "frame_index": item["frame"], "runtime_observation_id": item["id"],
        "detector_source": item["source"], "source_detection_id": item["source_id"],
        "bbox": bbox_json(item["bbox_value"]), "confidence": f"{item['confidence_value']:.6f}", "class": item["class"],
        "source_tracker_ids": ";".join(sorted(item["trackers"])),
        "appearance_feature_reference": f"{item['id']}:gray_histogram_8+edge_density",
        "color_feature_reference": f"{item['id']}:color_hsv_mean", "boundary_contact": item["boundary"],
        "runtime_quality_features": json.dumps(item["features"], separators=(",", ":")),
        "provenance": f"normalized_detection:{item['source']}:{item['source_id']}",
        "notes": f"p1c_local_cluster={item['p1c_cluster']};normalization_action={item['normalization_action']};suppression_reason={item['suppression_reason']};no_benchmark_input=true",
    } for item in sorted(observations, key=lambda x: (x["scene"], x["frame"], x["source"], x["source_id"]))]

    cluster_params = params["same_frame_cluster"]
    clusters: list[dict[str, Any]] = []
    clusters_by_frame: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for scene in SCENES:
        cluster_index = 1
        for frame in range(FRAME_COUNT):
            items = sorted(by_frame.get((scene, frame), []), key=lambda x: (x["source"], x["source_id"]))
            parent = list(range(len(items)))

            def find(index: int) -> int:
                while parent[index] != index:
                    parent[index] = parent[parent[index]]
                    index = parent[index]
                return index

            def union(a: int, b: int) -> None:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra

            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    box_i, box_j = items[i]["bbox_value"], items[j]["bbox_value"]
                    pair_iou, pair_iom, distance = iou(box_i, box_j), iom(box_i, box_j), center_distance(box_i, box_j)
                    shared_tracker = bool(items[i]["trackers"] & items[j]["trackers"])
                    same_p1c_cluster = bool(items[i]["p1c_cluster"] and items[i]["p1c_cluster"] == items[j]["p1c_cluster"])
                    if pair_iou >= cluster_params["iou_min"] or (
                        pair_iom >= cluster_params["intersection_over_min_min"] and distance <= cluster_params["normalized_center_distance_max"]
                    ) or (same_p1c_cluster and (pair_iom >= 0.40 or shared_tracker)):
                        union(i, j)
            groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for index, item in enumerate(items):
                groups[find(index)].append(item)
            for group in groups.values():
                boxes = [item["bbox_value"] for item in group]
                pair_ious = [iou(boxes[i], boxes[j]) for i in range(len(boxes)) for j in range(i + 1, len(boxes))]
                pair_colors = [color_distance(group[i]["color"], group[j]["color"]) for i in range(len(group)) for j in range(i + 1, len(group))]
                mutual_iou = min(pair_ious) if pair_ious else 1.0
                union_bbox = union_box(boxes)
                expansion = area(union_bbox) / max(1.0, max(area(box) for box in boxes))
                color_max = max(pair_colors) if pair_colors else 0.0
                trackers = set().union(*(item["trackers"] for item in group))
                sources = {item["source"] for item in group}
                mixed_risk = len(group) > 1 and mutual_iou < quality["mixed_internal_iou_max"] and expansion >= quality["mixed_union_expansion_min"]
                partial_risk = any(item["boundary"] != "none" for item in group)
                nonvehicle_risk = max(item["vehicle_likeness"] for item in group) < quality["reliable_vehicle_likeness"]
                max_area = max(area(item["bbox_value"]) for item in group)
                for item in group:
                    completeness = area(item["bbox_value"]) / max(1.0, max_area)
                    item["cluster_selection_score"] = 0.38 * item["confidence_value"] + 0.26 * completeness + 0.18 * item["vehicle_likeness"] + 0.10 * min(1.0, len(item["trackers"]) / 2.0) + 0.08 * (1.0 if item["source"] == "YOLO26l" else 0.0)
                baseline_choice = max(group, key=lambda item: (item["cluster_selection_score"], item["source"] == "YOLO26l", item["id"]))
                weights = np.asarray([max(0.05, item["cluster_selection_score"]) for item in group], dtype=np.float64)
                coords = np.asarray([item["bbox_value"] for item in group], dtype=np.float64)
                consensus = tuple(float(v) for v in np.average(coords, axis=0, weights=weights))
                cluster = {
                    "scene": scene, "frame": frame, "id": f"{scene}:RC{cluster_index:05d}", "items": group,
                    "bbox_value": consensus, "union_bbox": union_bbox, "trackers": trackers, "sources": sources,
                    "color": baseline_choice["color"], "vehicle_likeness": max(item["vehicle_likeness"] for item in group),
                    "mutual_iou": mutual_iou, "expansion": expansion, "color_max": color_max,
                    "mixed_risk": mixed_risk, "partial_risk": partial_risk, "nonvehicle_risk": nonvehicle_risk,
                    "baseline_choice": baseline_choice, "final_choice": None, "subject_id": "", "prev_support": 0.0,
                    "next_support": 0.0, "track_median_likeness": 0.0,
                }
                cluster_index += 1
                clusters.append(cluster)
                clusters_by_frame[(scene, frame)].append(cluster)

    link_params = params["local_subject_linking"]
    tracks: list[dict[str, Any]] = []
    scene_tracks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scene in SCENES:
        active_tracks: list[dict[str, Any]] = []
        next_subject = 1
        for frame in range(FRAME_COUNT):
            frame_clusters = sorted(clusters_by_frame.get((scene, frame), []), key=lambda c: (center(c["bbox_value"])[0], c["id"]))
            candidates: list[tuple[float, int, int]] = []
            for ti, track in enumerate(active_tracks):
                gap = frame - track["last_frame"]
                if gap < 1 or gap > link_params["max_frame_gap"]:
                    continue
                previous = track["clusters"][-1]
                for ci, cluster in enumerate(frame_clusters):
                    shared = bool(previous["trackers"] & cluster["trackers"])
                    distance = center_distance(previous["bbox_value"], cluster["bbox_value"])
                    color_gap = color_distance(previous["color"], cluster["color"])
                    if not shared and (distance > link_params["subject_switch_normalized_jump"] or color_gap > link_params["subject_switch_color_distance"]):
                        continue
                    geometry_support = math.exp(-0.85 * distance)
                    score = (link_params["shared_tracker_bonus"] if shared else 0.0) + link_params["geometry_weight"] * geometry_support + link_params["color_weight"] * (1.0 - color_gap) + link_params["source_support_weight"] * min(1.0, len(cluster["sources"]) / 2.0)
                    if score >= link_params["minimum_link_score"]:
                        candidates.append((score, ti, ci))
            used_tracks, used_clusters = set(), set()
            for score, ti, ci in sorted(candidates, reverse=True):
                if ti in used_tracks or ci in used_clusters:
                    continue
                track, cluster = active_tracks[ti], frame_clusters[ci]
                previous = track["clusters"][-1]
                previous["next_support"] = max(previous["next_support"], score)
                cluster["prev_support"] = score
                cluster["subject_id"] = track["id"]
                track["clusters"].append(cluster)
                track["last_frame"] = frame
                used_tracks.add(ti)
                used_clusters.add(ci)
            for ci, cluster in enumerate(frame_clusters):
                if ci in used_clusters:
                    continue
                subject_id = f"{scene}:RS{next_subject:04d}"
                next_subject += 1
                cluster["subject_id"] = subject_id
                track = {"scene": scene, "id": subject_id, "clusters": [cluster], "last_frame": frame}
                active_tracks.append(track)
                tracks.append(track)
                scene_tracks[scene].append(track)
            active_tracks = [track for track in active_tracks if frame - track["last_frame"] <= link_params["max_frame_gap"]]

    reliable = quality["reliable_vehicle_likeness"]
    selected_detector: dict[tuple[str, int], dict[str, Any]] = {}
    for track in tracks:
        likeness_values = [cluster["vehicle_likeness"] for cluster in track["clusters"]]
        track_median = median(likeness_values) if likeness_values else 0.0
        track_area = median([area(cluster["bbox_value"]) / (IMAGE_WIDTH * IMAGE_HEIGHT) for cluster in track["clusters"]]) if track["clusters"] else 0.0
        stable_nonvehicle = track_median < reliable or (len(track["clusters"]) <= 2 and track_area < quality["minimum_vehicle_area_ratio"] * 1.35)
        for cluster in track["clusters"]:
            cluster["track_median_likeness"] = track_median
            cluster["nonvehicle_risk"] = cluster["nonvehicle_risk"] or stable_nonvehicle
            if not cluster["mixed_risk"] and not cluster["nonvehicle_risk"]:
                candidates = sorted(cluster["items"], key=lambda item: (item["cluster_selection_score"], item["source"] == "YOLO26l"), reverse=True)
                cluster["final_choice"] = candidates[0]
                selected_detector[(track["id"], cluster["frame"])] = candidates[0]

    def outward_exit(selected: list[tuple[int, dict[str, Any]]], at_end: bool) -> bool:
        if len(selected) < 2:
            return False
        pair = selected[-2:] if at_end else selected[:2]
        if not at_end:
            pair = pair[::-1]
        first_box, second_box = pair[0][1]["bbox_value"], pair[1][1]["bbox_value"]
        dx = center(second_box)[0] - center(first_box)[0]
        dy = center(second_box)[1] - center(first_box)[1]
        contact = boundary_contact(second_box)
        return ("left" in contact and dx < 0) or ("right" in contact and dx > 0) or ("top" in contact and dy < 0) or ("bottom" in contact and dy > 0)

    recovery_params = params["recovery"]

    def propagate_step(scene: str, frame_a: int, frame_b: int, box: tuple[float, float, float, float]) -> dict[str, Any] | None:
        _, gray_a = load_frame(scene, frame_a)
        _, gray_b = load_frame(scene, frame_b)
        x1, y1, x2, y2 = (int(round(v)) for v in clip_box(box))
        mask = np.zeros_like(gray_a)
        margin_x = max(2, int(0.05 * (x2 - x1)))
        margin_y = max(2, int(0.05 * (y2 - y1)))
        mask[min(IMAGE_HEIGHT - 1, y1 + margin_y):max(y1 + margin_y + 1, y2 - margin_y), min(IMAGE_WIDTH - 1, x1 + margin_x):max(x1 + margin_x + 1, x2 - margin_x)] = 255
        points = cv2.goodFeaturesToTrack(
            gray_a, maxCorners=int(recovery_params["lk_max_corners"]),
            qualityLevel=float(recovery_params["lk_quality_level"]),
            minDistance=float(recovery_params["lk_min_distance"]), mask=mask,
        )
        if points is None or len(points) < recovery_params["lk_min_good_points"]:
            return None
        next_points, status, error = cv2.calcOpticalFlowPyrLK(
            gray_a, gray_b, points, None, winSize=(21, 21), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )
        if next_points is None or status is None:
            return None
        good = status.reshape(-1).astype(bool)
        if error is not None:
            good &= error.reshape(-1) < 35.0
        source_points = points.reshape(-1, 2)[good]
        target_points = next_points.reshape(-1, 2)[good]
        if len(source_points) < recovery_params["lk_min_good_points"]:
            return None
        matrix, inliers = cv2.estimateAffinePartial2D(source_points, target_points, method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if matrix is None:
            return None
        corners = np.asarray([[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]], dtype=np.float32).reshape(-1, 1, 2)
        transformed = cv2.transform(corners, matrix).reshape(-1, 2)
        predicted = clip_box((float(transformed[:, 0].min()), float(transformed[:, 1].min()), float(transformed[:, 0].max()), float(transformed[:, 1].max())))
        scale = math.sqrt(max(1e-9, abs(float(np.linalg.det(matrix[:, :2])))))
        inlier_ratio = float(np.mean(inliers)) if inliers is not None else 0.0
        px1, py1, px2, py2 = (int(round(v)) for v in predicted)
        patch_a = gray_a[max(0, y1):min(IMAGE_HEIGHT, y2), max(0, x1):min(IMAGE_WIDTH, x2)]
        patch_b = gray_b[max(0, py1):min(IMAGE_HEIGHT, py2), max(0, px1):min(IMAGE_WIDTH, px2)]
        if patch_a.size and patch_b.size and min(patch_b.shape) >= 4:
            resized = cv2.resize(patch_a, (patch_b.shape[1], patch_b.shape[0]), interpolation=cv2.INTER_AREA)
            ncc = float(cv2.matchTemplate(patch_b, resized, cv2.TM_CCOEFF_NORMED)[0, 0])
            if not math.isfinite(ncc):
                ncc = 0.0
        else:
            ncc = 0.0
        valid = (
            inlier_ratio >= recovery_params["affine_min_inlier_ratio"]
            and recovery_params["step_scale_min"] <= scale <= recovery_params["step_scale_max"]
        )
        return {"bbox": predicted, "good_points": len(source_points), "inlier_ratio": inlier_ratio, "scale": scale, "ncc": ncc, "valid": valid}

    def propagate(scene: str, seed_frame: int, target_frame: int, seed_box: tuple[float, float, float, float]) -> dict[int, dict[str, Any]]:
        direction = 1 if target_frame > seed_frame else -1
        current_box = seed_box
        output: dict[int, dict[str, Any]] = {}
        cumulative: list[dict[str, Any]] = []
        for frame in range(seed_frame + direction, target_frame + direction, direction):
            step = propagate_step(scene, frame - direction, frame, current_box)
            if not step:
                break
            cumulative.append(step)
            current_box = step["bbox"]
            output[frame] = {
                "bbox": current_box,
                "mean_points": float(np.mean([item["good_points"] for item in cumulative])),
                "mean_inlier": float(np.mean([item["inlier_ratio"] for item in cumulative])),
                "mean_ncc": float(np.mean([item["ncc"] for item in cumulative])),
                "scale_min": min(item["scale"] for item in cumulative),
                "scale_max": max(item["scale"] for item in cumulative),
                "all_valid": all(item["valid"] for item in cumulative),
                "steps": len(cumulative),
            }
            if not step["valid"] or step["ncc"] < recovery_params["template_ncc_min"] - 0.10:
                break
        return output

    selected_by_frame: dict[tuple[str, int], list[tuple[str, tuple[float, float, float, float]]]] = defaultdict(list)
    for (subject_id, frame), item in selected_detector.items():
        selected_by_frame[(item["scene"], frame)].append((subject_id, item["bbox_value"]))

    recovery_candidates: list[dict[str, Any]] = []
    candidate_keys: set[tuple[str, int, str]] = set()

    def add_candidate(track: dict[str, Any], frame: int, method: str, forward_seed: int | None, backward_seed: int | None,
                      forward: dict[str, Any] | None, backward: dict[str, Any] | None) -> None:
        key = (track["id"], frame, method)
        if key in candidate_keys:
            return
        candidate_keys.add(key)
        if forward and backward:
            consistency = iou(forward["bbox"], backward["bbox"])
            weight_f = max(0.05, forward["mean_inlier"] * max(0.05, forward["mean_ncc"] + 0.2))
            weight_b = max(0.05, backward["mean_inlier"] * max(0.05, backward["mean_ncc"] + 0.2))
            coords = np.average(np.asarray([forward["bbox"], backward["bbox"]]), axis=0, weights=np.asarray([weight_f, weight_b]))
            box = clip_box(tuple(float(v) for v in coords))
            image_support = 0.5 * (forward["mean_ncc"] + backward["mean_ncc"])
            motion_support = 0.5 * (forward["mean_inlier"] + backward["mean_inlier"])
            point_support = min(1.0, 0.5 * (forward["mean_points"] + backward["mean_points"]) / 30.0)
            scale_ok = forward["all_valid"] and backward["all_valid"]
            span = min(forward["steps"], backward["steps"])
        else:
            evidence = forward or backward
            if evidence is None:
                return
            consistency = 0.55
            box = evidence["bbox"]
            image_support = evidence["mean_ncc"]
            motion_support = evidence["mean_inlier"]
            point_support = min(1.0, evidence["mean_points"] / 30.0)
            scale_ok = evidence["all_valid"]
            span = evidence["steps"]
        conflicts = [iom(box, other_box) for other_subject, other_box in selected_by_frame.get((track["scene"], frame), []) if other_subject != track["id"]]
        conflict_value = max(conflicts, default=0.0)
        seed_quality = median([cluster["track_median_likeness"] for cluster in track["clusters"]])
        confidence = 0.28 * max(0.0, min(1.0, (image_support + 0.1) / 0.9)) + 0.24 * motion_support + 0.16 * point_support + 0.18 * consistency + 0.14 * seed_quality
        confidence *= max(0.72, 0.992 ** max(0, span - 1))
        accepted = (
            image_support >= recovery_params["template_ncc_min"] and scale_ok
            and consistency >= (recovery_params["bidirectional_iou_min"] if forward and backward else 0.0)
            and conflict_value < recovery_params["conflict_iom_max"]
            and confidence >= recovery_params["accepted_runtime_confidence_min"]
        )
        recovery_candidates.append({
            "scene": track["scene"], "frame": frame, "subject_id": track["id"], "method": method,
            "forward_seed": forward_seed, "backward_seed": backward_seed, "forward": forward, "backward": backward,
            "bbox_value": box, "consistency": consistency, "image_support": image_support,
            "motion_support": motion_support, "scale_ok": scale_ok, "conflict": conflict_value,
            "confidence": confidence, "accepted": accepted,
            "acceptance_status": "accepted" if accepted else "rejected_evidence_or_conflict",
        })

    for track in tracks:
        seeds = sorted((frame, item) for (subject_id, frame), item in selected_detector.items() if subject_id == track["id"])
        if not seeds:
            continue
        for (left_frame, left_item), (right_frame, right_item) in zip(seeds, seeds[1:]):
            gap = right_frame - left_frame - 1
            if gap <= 0 or gap > recovery_params["maximum_bridge_span"]:
                continue
            forward_all = propagate(track["scene"], left_frame, right_frame - 1, left_item["bbox_value"])
            backward_all = propagate(track["scene"], right_frame, left_frame + 1, right_item["bbox_value"])
            for frame in range(left_frame + 1, right_frame):
                add_candidate(track, frame, "bidirectional_lk_affine_template", left_frame, right_frame, forward_all.get(frame), backward_all.get(frame))
        if not outward_exit(seeds, at_end=True):
            last_frame, last_item = seeds[-1]
            target = min(FRAME_COUNT - 1, last_frame + recovery_params["maximum_forward_span"])
            forward_all = propagate(track["scene"], last_frame, target, last_item["bbox_value"])
            for frame in range(last_frame + 1, target + 1):
                if any(subject == track["id"] for subject, _ in selected_by_frame.get((track["scene"], frame), [])):
                    continue
                evidence = forward_all.get(frame)
                if not evidence:
                    break
                add_candidate(track, frame, "forward_lk_affine_template", last_frame, None, evidence, None)
                if recovery_candidates[-1]["acceptance_status"] != "accepted":
                    break
        if not outward_exit(seeds, at_end=False):
            first_frame, first_item = seeds[0]
            target = max(0, first_frame - recovery_params["maximum_backward_span"])
            backward_all = propagate(track["scene"], first_frame, target, first_item["bbox_value"])
            for frame in range(first_frame - 1, target - 1, -1):
                if any(subject == track["id"] for subject, _ in selected_by_frame.get((track["scene"], frame), [])):
                    continue
                evidence = backward_all.get(frame)
                if not evidence:
                    break
                add_candidate(track, frame, "backward_lk_affine_template", None, first_frame, None, evidence)
                if recovery_candidates[-1]["acceptance_status"] != "accepted":
                    break

    accepted_by_frame: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for candidate in recovery_candidates:
        if candidate["accepted"]:
            accepted_by_frame[(candidate["scene"], candidate["frame"])].append(candidate)
    for key, candidates in accepted_by_frame.items():
        kept: list[dict[str, Any]] = []
        for candidate in sorted(candidates, key=lambda item: item["confidence"], reverse=True):
            if any(iom(candidate["bbox_value"], other["bbox_value"]) >= recovery_params["conflict_iom_max"] and candidate["subject_id"] != other["subject_id"] for other in kept):
                candidate["accepted"] = False
                candidate["acceptance_status"] = "rejected_cross_subject_conflict"
            else:
                kept.append(candidate)

    recovery_rows: list[dict[str, Any]] = []
    accepted_recovery: dict[tuple[str, int], dict[str, Any]] = {}
    for index, candidate in enumerate(sorted(recovery_candidates, key=lambda item: (item["scene"], item["frame"], item["subject_id"], item["method"])), 1):
        forward, backward = candidate["forward"], candidate["backward"]
        recovery_id = f"{candidate['scene']}:RR{index:05d}"
        if candidate["accepted"]:
            accepted_recovery[(candidate["subject_id"], candidate["frame"])] = {**candidate, "id": recovery_id}
        recovery_rows.append({
            "scene": candidate["scene"], "frame_index": candidate["frame"],
            "runtime_local_subject_id": candidate["subject_id"], "recovered_observation_id": recovery_id,
            "bbox": bbox_json(candidate["bbox_value"]), "recovery_method": candidate["method"],
            "forward_seed_frame": "" if candidate["forward_seed"] is None else candidate["forward_seed"],
            "backward_seed_frame": "" if candidate["backward_seed"] is None else candidate["backward_seed"],
            "propagation_length": max(forward["steps"] if forward else 0, backward["steps"] if backward else 0),
            "forward_bbox": bbox_json(forward["bbox"] if forward else None), "backward_bbox": bbox_json(backward["bbox"] if backward else None),
            "bidirectional_consistency": f"{candidate['consistency']:.6f}",
            "image_support_evidence": json.dumps({"mean_ncc": round(candidate["image_support"], 6), "forward_mean_points": round(forward["mean_points"], 3) if forward else None, "backward_mean_points": round(backward["mean_points"], 3) if backward else None}, separators=(",", ":")),
            "motion_consistency": f"{candidate['motion_support']:.6f}", "scale_consistency": str(candidate["scale_ok"]).lower(),
            "conflict_with_other_subject": f"{candidate['conflict']:.6f}", "runtime_recovery_confidence": f"{candidate['confidence']:.6f}",
            "acceptance_status": candidate["acceptance_status"], "notes": "optical_flow_and_image_support_only;no_linear_final_interpolation;no_benchmark_input=true",
        })

    selected_rows: list[dict[str, Any]] = []
    for cluster in sorted(clusters, key=lambda c: (c["scene"], c["frame"], c["subject_id"], c["id"])):
        item = cluster["final_choice"]
        recovery = accepted_recovery.get((cluster["subject_id"], cluster["frame"]))
        if item:
            partial = item["boundary"] != "none"
            state = "partial_subject_candidate" if partial else "complete_subject_candidate"
            status = "selected_detector_observation"
            selected_id, source, box = item["id"], item["source"], item["bbox_value"]
            runtime_confidence = item["cluster_selection_score"]
            flags = []
        elif recovery:
            state, status = "complete_subject_candidate", "selected_recovered_observation"
            selected_id, source, box = recovery["id"], "recovered", recovery["bbox_value"]
            runtime_confidence = recovery["confidence"]
            flags = ["recovered_replaces_unresolved_cluster"]
        else:
            state = "mixed_subject_candidate" if cluster["mixed_risk"] else "possible_non_vehicle" if cluster["nonvehicle_risk"] else "unresolved_runtime_observation"
            status = "runtime_unresolved"
            selected_id, source, box, runtime_confidence = "", "", None, 0.0
            flags = [state]
        alternatives = [entry["id"] for entry in cluster["items"] if entry["id"] != selected_id]
        identity_usable = state == "complete_subject_candidate" and runtime_confidence >= quality["identity_appearance_min"] and status != "runtime_unresolved"
        selected_rows.append({
            "scene": cluster["scene"], "frame_index": cluster["frame"], "runtime_local_subject_id": cluster["subject_id"],
            "selected_observation_id": selected_id, "selection_status": status,
            "selection_evidence": json.dumps({"track_median_vehicle_likeness": round(cluster["track_median_likeness"], 6), "previous_temporal_support": round(cluster["prev_support"], 6), "next_temporal_support": round(cluster["next_support"], 6), "mixed_risk": cluster["mixed_risk"], "possible_non_vehicle_risk": cluster["nonvehicle_risk"]}, separators=(",", ":")),
            "alternative_observation_ids": ";".join(alternatives), "detector_source": source, "bbox": bbox_json(box),
            "subject_quality_state": state, "runtime_confidence": f"{runtime_confidence:.6f}", "review_flags": ";".join(flags),
            "usable_for_motion": str(status != "runtime_unresolved" and state != "possible_non_vehicle").lower(),
            "usable_for_color": str(status != "runtime_unresolved" and state not in {"mixed_subject_candidate", "possible_non_vehicle"}).lower(),
            "usable_for_identity_appearance": str(identity_usable).lower(), "usable_for_shape": str(identity_usable).lower(),
            "diagnostic_only": str(state in {"mixed_subject_candidate", "possible_non_vehicle", "unresolved_runtime_observation"}).lower(),
            "baseline_b_included": str(bool(cluster["baseline_choice"])).lower(), "baseline_c_included": str(item is not None or (recovery is not None and recovery["method"].startswith("forward"))).lower(),
            "baseline_d_included": str(status != "runtime_unresolved").lower(), "notes": f"cluster={cluster['id']};runtime_local_subject_only=true;no_benchmark_input=true",
        })

    existing_selected_keys = {(row["runtime_local_subject_id"], int(row["frame_index"])) for row in selected_rows}
    for (subject_id, frame), recovery in sorted(accepted_recovery.items(), key=lambda item: (item[0][0], item[0][1])):
        if (subject_id, frame) in existing_selected_keys:
            continue
        selected_rows.append({
            "scene": recovery["scene"], "frame_index": frame, "runtime_local_subject_id": subject_id,
            "selected_observation_id": recovery["id"], "selection_status": "selected_recovered_observation",
            "selection_evidence": json.dumps({"recovery_method": recovery["method"], "bidirectional_consistency": round(recovery["consistency"], 6), "image_support": round(recovery["image_support"], 6)}, separators=(",", ":")),
            "alternative_observation_ids": "", "detector_source": "recovered", "bbox": bbox_json(recovery["bbox_value"]),
            "subject_quality_state": "complete_subject_candidate", "runtime_confidence": f"{recovery['confidence']:.6f}",
            "review_flags": "recovered_without_detector_cluster", "usable_for_motion": "true", "usable_for_color": "true",
            "usable_for_identity_appearance": str(recovery["confidence"] >= quality["identity_appearance_min"]).lower(),
            "usable_for_shape": str(recovery["confidence"] >= quality["identity_appearance_min"]).lower(), "diagnostic_only": "false",
            "baseline_b_included": "false", "baseline_c_included": str(recovery["method"].startswith("forward")).lower(),
            "baseline_d_included": "true", "notes": "runtime_flow_recovery;no_benchmark_input=true",
        })
    selected_rows.sort(key=lambda row: (row["scene"], int(row["frame_index"]), row["runtime_local_subject_id"]))

    cluster_rows = []
    for cluster in sorted(clusters, key=lambda c: (c["scene"], c["frame"], c["id"])):
        cluster_rows.append({
            "scene": cluster["scene"], "frame_index": cluster["frame"], "runtime_observation_cluster_id": cluster["id"],
            "runtime_local_subject_id": cluster["subject_id"], "observation_ids": ";".join(item["id"] for item in cluster["items"]),
            "detector_sources": ";".join(sorted(cluster["sources"])), "source_tracker_ids": ";".join(sorted(cluster["trackers"])),
            "cluster_bbox": bbox_json(cluster["union_bbox"]), "consensus_bbox": bbox_json(cluster["bbox_value"]),
            "source_support_count": len(cluster["sources"]), "mutual_iou_min": f"{cluster['mutual_iou']:.6f}",
            "union_expansion_ratio": f"{cluster['expansion']:.6f}", "color_distance_max": f"{cluster['color_max']:.6f}",
            "temporal_support_previous": f"{cluster['prev_support']:.6f}", "temporal_support_next": f"{cluster['next_support']:.6f}",
            "multiple_motion_subject_risk": str(cluster["mixed_risk"]).lower(), "partial_subject_risk": str(cluster["partial_risk"]).lower(),
            "possible_non_vehicle_risk": str(cluster["nonvehicle_risk"]).lower(),
            "baseline_b_selected_observation_id": cluster["baseline_choice"]["id"],
            "final_selected_observation_id": cluster["final_choice"]["id"] if cluster["final_choice"] else "",
            "cluster_quality_evidence": json.dumps({"vehicle_likeness": round(cluster["vehicle_likeness"], 6), "track_median_vehicle_likeness": round(cluster["track_median_likeness"], 6), "mixed_risk": cluster["mixed_risk"], "partial_risk": cluster["partial_risk"], "possible_non_vehicle_risk": cluster["nonvehicle_risk"]}, separators=(",", ":")),
            "notes": "same_frame_alternatives_preserved;runtime_local_subject_not_physical_identity=true",
        })

    write_csv(ROOT / outputs["runtime_observations"], RUNTIME_FIELDS, runtime_rows)
    write_csv(ROOT / outputs["runtime_clusters"], CLUSTER_FIELDS, cluster_rows)
    write_csv(ROOT / outputs["selected_observations"], SELECTED_FIELDS, selected_rows)
    write_csv(ROOT / outputs["recovered_observations"], RECOVERY_FIELDS, recovery_rows)

    metrics = {
        "status": "RUNTIME_OUTPUTS_GENERATED",
        "source_boundary": config["source_boundary"],
        "runtime_observation_count": len(runtime_rows), "runtime_cluster_count": len(cluster_rows),
        "runtime_local_subject_count": len(tracks), "selected_row_count": len(selected_rows),
        "selected_detector_count": sum(row["selection_status"] == "selected_detector_observation" for row in selected_rows),
        "selected_recovered_count": sum(row["selection_status"] == "selected_recovered_observation" for row in selected_rows),
        "runtime_unresolved_count": sum(row["selection_status"] == "runtime_unresolved" for row in selected_rows),
        "recovery_candidate_count": len(recovery_rows),
        "accepted_recovery_count": sum(row["acceptance_status"] == "accepted" for row in recovery_rows),
        "hashes": {
            "runtime_observations": sha256_rows(runtime_rows, RUNTIME_FIELDS),
            "runtime_clusters": sha256_rows(cluster_rows, CLUSTER_FIELDS),
            "selected_observations": sha256_rows(selected_rows, SELECTED_FIELDS),
            "recovered_observations": sha256_rows(recovery_rows, RECOVERY_FIELDS),
        },
        "runtime_benchmark_separation": True, "p2_entry_allowed": False,
    }
    metrics_path = ROOT / outputs["metrics"]
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
