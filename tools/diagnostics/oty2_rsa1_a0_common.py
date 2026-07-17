from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

from oty2_rsa0_r2_forensic import single_channels


REPO = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO / "configs" / "oty2" / "oty2_rsa1_a0_seed_object_extension.json"
RULE_FREEZE_MANIFEST = REPO / "manifests" / "oty2" / "oty2_rsa1_a0_rule_freeze_manifest.csv"

FAMILY_SLUGS = {
    "RAW_SAR_DISPLAY": "raw_sar_display",
    "WORLD_STABILIZED_IMAGE_STACK": "world_stabilized_image_stack",
    "GT_ALIGNED_RESEARCH_STACK": "gt_aligned_research_stack",
    "OPTICAL_PROXY_ALIGNED_STACK": "optical_proxy_aligned_stack",
}

PRIMITIVE_FIELDS = [
    "case_id",
    "frame",
    "coordinate_family",
    "propagation_mode",
    "primitive_id",
    "direction",
    "ordinal",
    "geometry",
    "geometry_raw",
    "length",
    "width",
    "mean_intensity",
    "median_intensity",
    "local_contrast",
    "ridge_response",
    "local_orientation",
    "fan_radial_relation",
    "fan_tangential_relation",
    "temporal_support",
    "world_stable_recurrence",
    "shortest_seed_path",
    "crosses_confirmed_background",
    "enters_ambiguity_zone",
    "state",
    "state_reason",
]

TRACE_FIELDS = [
    "case_id",
    "frame",
    "coordinate_family",
    "propagation_mode",
    "expansion_step",
    "source_primitive",
    "destination_primitive",
    "spatial_connected",
    "distance",
    "orientation_difference",
    "ridge_relation",
    "contrast_relation",
    "intensity_relation",
    "width_relation",
    "temporal_support",
    "world_background_recurrence",
    "crosses_confirmed_background",
    "enters_ambiguity_zone",
    "first_failed_gate",
    "state_before",
    "state_after",
    "decision_reason",
    "evidence_card",
    "evidence_sha256",
]


@dataclass
class CaseData:
    spec: dict[str, Any]
    frames: list[int]
    primary_index: int
    stacks: dict[str, np.ndarray]
    matrices: dict[str, list[np.ndarray]]
    seed_raw_primary: np.ndarray
    seed_aligned: np.ndarray
    axis: np.ndarray
    vertical_aligned: list[np.ndarray]
    endpoint_ambiguity_aligned: np.ndarray
    arc_clutter_ambiguity_aligned: np.ndarray


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def check_repository_gate(config: dict[str, Any]) -> None:
    branch = run_git("branch", "--show-current")
    if branch != config["expected_branch"]:
        raise RuntimeError(f"unexpected branch: {branch}")
    required_commit = config["required_docs_commit"]
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", required_commit, "HEAD"],
        cwd=REPO,
        check=True,
        capture_output=True,
    )


def verify_rule_freeze() -> str:
    if not RULE_FREEZE_MANIFEST.is_file():
        raise FileNotFoundError(RULE_FREEZE_MANIFEST)
    rows = read_csv(RULE_FREEZE_MANIFEST)
    source_rows = [row for row in rows if row["entry_role"] == "frozen_rule_source"]
    if not source_rows:
        raise RuntimeError("rule freeze manifest has no frozen rule sources")
    expected_aggregate = source_rows[0]["aggregate_rule_sha256"]
    pieces = []
    for row in source_rows:
        path = REPO / row["path"]
        digest = sha256_file(path)
        if digest != row["sha256"]:
            raise RuntimeError(f"frozen rule source changed after freeze: {path}")
        pieces.append(f"{row['path']}:{digest}")
        if row["aggregate_rule_sha256"] != expected_aggregate:
            raise RuntimeError("inconsistent aggregate rule hash")
    actual_aggregate = hashlib.sha256("\n".join(sorted(pieces)).encode("utf-8")).hexdigest()
    if actual_aggregate != expected_aggregate:
        raise RuntimeError("aggregate rule hash mismatch")
    return expected_aggregate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_points(text: str) -> np.ndarray:
    points = []
    for token in text.split(";"):
        x_text, y_text = token.split(",")
        points.append((float(x_text), float(y_text)))
    return np.asarray(points, dtype=np.float64)


def format_points(points: np.ndarray) -> str:
    return ";".join(f"{float(x):.3f},{float(y):.3f}" for x, y in points)


def parse_matrix(text: str) -> np.ndarray:
    return np.asarray(json.loads(text), dtype=np.float64)


def transform_points(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    homogeneous = np.column_stack([points, np.ones(len(points), dtype=np.float64)])
    return homogeneous @ matrix.T


def invert_matrix(matrix: np.ndarray) -> np.ndarray:
    full = np.vstack([matrix, np.array([0.0, 0.0, 1.0])])
    return np.linalg.inv(full)[:2, :]


def normalize_axis(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise ValueError("zero-length axis")
    axis = vector / norm
    if axis[0] < 0:
        axis = -axis
    return axis


def family_bundle_path(config: dict[str, Any], case_id: str, family: str) -> Path:
    slug = FAMILY_SLUGS[family]
    return (
        Path(config["r2_output_root"])
        / "arrays"
        / "phase_b"
        / "coordinate_stacks"
        / case_id
        / f"{case_id.lower()}_{slug}.npz"
    )


def load_matrices(config: dict[str, Any], case_id: str, frames: Sequence[int]) -> dict[str, list[np.ndarray]]:
    rows = read_csv(REPO / config["sources"]["coordinate_audit"])
    output: dict[str, list[np.ndarray]] = {}
    for family in FAMILY_SLUGS:
        family_rows = {
            int(row["frame"]): parse_matrix(row["matrix"])
            for row in rows
            if row["case_id"] == case_id and row["coordinate_family"] == family and row["frame"].isdigit()
        }
        if set(family_rows) >= set(frames):
            output[family] = [family_rows[frame] for frame in frames]
    return output


def load_case(config: dict[str, Any], case_id: str, family: str) -> CaseData:
    spec = next(item for item in config["cases"] if item["case_id"] == case_id)
    frames = [int(frame) for frame in spec["frames"]]
    primary_index = frames.index(int(spec["primary_frame"]))
    matrices = load_matrices(config, case_id, frames)
    required_families = {"RAW_SAR_DISPLAY", "WORLD_STABILIZED_IMAGE_STACK", family}
    if not required_families <= set(matrices):
        raise RuntimeError(f"missing coordinate matrices for {case_id}: {required_families - set(matrices)}")

    stacks: dict[str, np.ndarray] = {}
    for stack_family in required_families:
        bundle_path = family_bundle_path(config, case_id, stack_family)
        if not bundle_path.is_file():
            raise FileNotFoundError(bundle_path)
        with np.load(bundle_path, allow_pickle=False) as bundle:
            stacks[stack_family] = bundle["image_stack"]

    point_rows = read_csv(REPO / config["sources"]["atlas_point_audit"])
    seed_row = next(
        row
        for row in point_rows
        if row["case_id"] == case_id
        and int(row["frame"]) == int(spec["primary_frame"])
        and row["point_id"] == "seed_mid"
        and row["status"] == "CONFIRMED"
    )
    seed_point = np.array([float(seed_row["x_px"]), float(seed_row["y_px"])], dtype=np.float64)

    skeleton_rows = read_csv(REPO / config["sources"]["atlas_skeletons"])
    source_seed = next(
        row
        for row in skeleton_rows
        if row["case_id"] == spec["source_case_id"]
        and int(row["sar_frame"]) == int(spec["primary_frame"])
        and row["label"] == "HIGH_CONFIDENCE_RESPONSE_SEED"
    )
    source_seed_points = parse_points(source_seed["points"])
    axis = normalize_axis(source_seed_points[-1] - source_seed_points[0])
    seed_length = float(config["primitive_definition"]["seed_length_px"])
    seed_raw_primary = np.vstack([seed_point, seed_point + axis * seed_length])
    seed_aligned = transform_points(seed_raw_primary, matrices[family][primary_index])

    background_rows = read_csv(REPO / config["sources"]["atlas_background"])
    primary_vertical_raw = parse_points(
        next(
            row
            for row in background_rows
            if row["case_id"] == spec["source_case_id"]
            and int(row["sar_frame"]) == int(spec["primary_frame"])
            and row["component_id"] == "0"
        )["points"]
    )
    primary_vertical_world = transform_points(
        primary_vertical_raw, matrices["WORLD_STABILIZED_IMAGE_STACK"][primary_index]
    )
    vertical_aligned: list[np.ndarray] = []
    for index in range(len(frames)):
        vertical_raw = transform_points(
            primary_vertical_world,
            invert_matrix(matrices["WORLD_STABILIZED_IMAGE_STACK"][index]),
        )
        vertical_aligned.append(transform_points(vertical_raw, matrices[family][index]))

    endpoint_ambiguity_aligned = transform_points(
        parse_points(spec["endpoint_ambiguity_primary_raw"]), matrices[family][primary_index]
    )
    arc_clutter_ambiguity_aligned = transform_points(
        parse_points(spec["arc_clutter_ambiguity_primary_raw"]), matrices[family][primary_index]
    )
    return CaseData(
        spec=spec,
        frames=frames,
        primary_index=primary_index,
        stacks=stacks,
        matrices=matrices,
        seed_raw_primary=seed_raw_primary,
        seed_aligned=seed_aligned,
        axis=axis,
        vertical_aligned=vertical_aligned,
        endpoint_ambiguity_aligned=endpoint_ambiguity_aligned,
        arc_clutter_ambiguity_aligned=arc_clutter_ambiguity_aligned,
    )


def polyline_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def line_mask(shape: tuple[int, int], points: np.ndarray, width: int) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    integer_points = np.rint(points).astype(np.int32)
    cv2.polylines(mask, [integer_points], False, 1, thickness=max(1, int(width)), lineType=cv2.LINE_8)
    return mask.astype(bool)


def polygon_contains_samples(polygon: np.ndarray, segment: np.ndarray) -> bool:
    contour = polygon.astype(np.float32)
    for t in np.linspace(0.0, 1.0, 33):
        point = segment[0] * (1.0 - t) + segment[-1] * t
        if cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False) >= 0:
            return True
    return False


def orientation_difference_deg(a_deg: float, b_deg: float) -> float:
    delta = abs(a_deg - b_deg) % 180.0
    return min(delta, 180.0 - delta)


def estimate_orientation(image: np.ndarray, mask: np.ndarray) -> float:
    image32 = image.astype(np.float32)
    gx = cv2.Sobel(image32, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(image32, cv2.CV_32F, 0, 1, ksize=3)
    weights = mask.astype(np.float32)
    jxx = float(np.sum(weights * gx * gx))
    jyy = float(np.sum(weights * gy * gy))
    jxy = float(np.sum(weights * gx * gy))
    gradient_angle = 0.5 * math.degrees(math.atan2(2.0 * jxy, jxx - jyy + 1e-12))
    return (gradient_angle + 90.0) % 180.0


def sample_response_width(image: np.ndarray, segment: np.ndarray, max_offset: int = 8) -> float:
    axis = normalize_axis(segment[-1] - segment[0])
    normal = np.array([-axis[1], axis[0]], dtype=np.float64)
    along = np.linspace(0.0, 1.0, 17)
    offsets = np.arange(-max_offset, max_offset + 1, dtype=np.float64)
    values = []
    for offset in offsets:
        points = segment[0][None, :] * (1.0 - along[:, None]) + segment[-1][None, :] * along[:, None]
        points = points + normal[None, :] * offset
        sampled = cv2.remap(
            image.astype(np.float32),
            points[:, 0].astype(np.float32).reshape(1, -1),
            points[:, 1].astype(np.float32).reshape(1, -1),
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        values.append(float(np.mean(sampled)))
    profile = np.asarray(values, dtype=np.float64)
    baseline = float(np.percentile(profile, 25.0))
    peak = float(np.max(profile))
    threshold = baseline + 0.35 * max(peak - baseline, 0.0)
    active = profile >= threshold
    peak_index = int(np.argmax(profile))
    left = peak_index
    right = peak_index
    while left > 0 and active[left - 1]:
        left -= 1
    while right + 1 < len(active) and active[right + 1]:
        right += 1
    return float(right - left + 1)


def patch(image: np.ndarray, point: np.ndarray, radius: int) -> np.ndarray:
    size = 2 * radius + 1
    return cv2.getRectSubPix(image.astype(np.float32), (size, size), (float(point[0]), float(point[1])))


def ncc(first: np.ndarray, second: np.ndarray) -> float:
    a = first.astype(np.float64).ravel()
    b = second.astype(np.float64).ravel()
    a -= float(np.mean(a))
    b -= float(np.mean(b))
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= 1e-12:
        return 0.0
    return float(np.dot(a, b) / denominator)


def stack_recurrence(stack: np.ndarray, point: np.ndarray, radius: int) -> float:
    patches = [patch(frame, point, radius) for frame in stack]
    values = [ncc(patches[index], patches[index + 1]) for index in range(len(patches) - 1)]
    return float(np.median(values)) if values else 0.0


def local_metrics(
    image: np.ndarray,
    channels: dict[str, np.ndarray],
    segment: np.ndarray,
    half_width: int,
) -> dict[str, float]:
    mask = line_mask(image.shape, segment, 2 * half_width + 1)
    raw_values = image[mask].astype(np.float64)
    contrast_values = channels["local_contrast_31"][mask].astype(np.float64)
    ridge_values = channels["multiscale_laplacian_bright_ridge"][mask].astype(np.float64)
    coherence_values = channels["structure_tensor_orientation_coherence"][mask].astype(np.float64)
    radial_values = channels["radial_gradient_normal_response"][mask].astype(np.float64)
    tangential_values = channels["tangential_gradient_normal_response"][mask].astype(np.float64)
    return {
        "mean_intensity": float(np.mean(raw_values)),
        "median_intensity": float(np.median(raw_values)),
        "local_contrast": float(np.median(np.abs(contrast_values))),
        "ridge_response": float(np.percentile(ridge_values, 75.0)),
        "coherence": float(np.median(coherence_values)),
        "radial_relation": float(np.median(radial_values)),
        "tangential_relation": float(np.median(tangential_values)),
        "orientation": estimate_orientation(image, mask),
        "width": sample_response_width(image, segment),
    }


def safe_ratio(value: float, reference: float) -> float:
    return float(value / max(abs(reference), 1e-6))


def segment_distance(first: np.ndarray, second: np.ndarray) -> float:
    def orientation(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        return float(np.cross(b - a, c - a))

    o1 = orientation(first[0], first[-1], second[0])
    o2 = orientation(first[0], first[-1], second[-1])
    o3 = orientation(second[0], second[-1], first[0])
    o4 = orientation(second[0], second[-1], first[-1])
    if o1 * o2 <= 0.0 and o3 * o4 <= 0.0:
        return 0.0

    def point_segment(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
        delta = end - start
        denominator = float(np.dot(delta, delta))
        if denominator <= 1e-12:
            return float(np.linalg.norm(point - start))
        t = float(np.clip(np.dot(point - start, delta) / denominator, 0.0, 1.0))
        return float(np.linalg.norm(point - (start + t * delta)))

    return min(
        point_segment(first[0], second[0], second[-1]),
        point_segment(first[-1], second[0], second[-1]),
        point_segment(second[0], first[0], first[-1]),
        point_segment(second[-1], first[0], first[-1]),
    )


def build_segments(case: CaseData, config: dict[str, Any]) -> list[dict[str, Any]]:
    segment_length = float(config["primitive_definition"]["segment_length_px"])
    seed = case.seed_aligned
    axis = normalize_axis(seed[-1] - seed[0])
    segments: list[dict[str, Any]] = [
        {"direction": "seed", "ordinal": 0, "points": seed.copy(), "source_ordinal": 0}
    ]
    for direction, sign, anchor, max_steps in [
        ("left", -1.0, seed[0], int(config["primitive_definition"]["max_steps_left"])),
        ("right", 1.0, seed[-1], int(config["primitive_definition"]["max_steps_right"])),
    ]:
        for ordinal in range(1, max_steps + 1):
            near = anchor + sign * axis * segment_length * (ordinal - 1)
            far = anchor + sign * axis * segment_length * ordinal
            points = np.vstack([near, far]) if direction == "right" else np.vstack([near, far])
            segments.append(
                {
                    "direction": direction,
                    "ordinal": ordinal,
                    "points": points,
                    "source_ordinal": ordinal - 1,
                }
            )
    return segments


def primitive_id(case_id: str, frame: int, family: str, direction: str, ordinal: int) -> str:
    short_family = {
        "GT_ALIGNED_RESEARCH_STACK": "GT",
        "OPTICAL_PROXY_ALIGNED_STACK": "PROXY",
    }.get(family, family[:5])
    suffix = "SEED" if direction == "seed" else f"{direction.upper()}{ordinal:02d}"
    return f"{case_id}_{frame}_{short_family}_{suffix}"


def aligned_to_raw(case: CaseData, family: str, frame_index: int, points: np.ndarray) -> np.ndarray:
    return transform_points(points, invert_matrix(case.matrices[family][frame_index]))


def world_recurrence_for_segment(
    case: CaseData,
    family: str,
    frame_index: int,
    segment: np.ndarray,
    radius: int,
) -> float:
    midpoint = np.mean(segment, axis=0, keepdims=True)
    raw_point = transform_points(midpoint, invert_matrix(case.matrices[family][frame_index]))
    world_point = transform_points(raw_point, case.matrices["WORLD_STABILIZED_IMAGE_STACK"][frame_index])[0]
    return stack_recurrence(case.stacks["WORLD_STABILIZED_IMAGE_STACK"], world_point, radius)


def evidence_card(
    path: Path,
    case: CaseData,
    family: str,
    frame_index: int,
    segment: np.ndarray,
    supported_before: list[np.ndarray],
    trace: dict[str, Any],
    channels: dict[str, np.ndarray],
) -> None:
    image = case.stacks[family][frame_index]
    raw_image = case.stacks["RAW_SAR_DISPLAY"][frame_index]
    world_image = case.stacks["WORLD_STABILIZED_IMAGE_STACK"][frame_index]
    seed = case.seed_aligned
    vertical = case.vertical_aligned[frame_index]
    endpoint = case.endpoint_ambiguity_aligned
    arc = case.arc_clutter_ambiguity_aligned
    all_points = np.concatenate([segment, seed, vertical, endpoint, arc], axis=0)
    x0 = max(0, int(np.floor(all_points[:, 0].min() - 60)))
    x1 = min(image.shape[1], int(np.ceil(all_points[:, 0].max() + 60)))
    y0 = max(0, int(np.floor(all_points[:, 1].min() - 60)))
    y1 = min(image.shape[0], int(np.ceil(all_points[:, 1].max() + 60)))

    raw_segment = aligned_to_raw(case, family, frame_index, segment)
    raw_seed = aligned_to_raw(case, family, frame_index, seed)
    raw_vertical = aligned_to_raw(case, family, frame_index, vertical)
    raw_endpoint = aligned_to_raw(case, family, frame_index, endpoint)
    raw_arc = aligned_to_raw(case, family, frame_index, arc)
    raw_all = np.concatenate([raw_segment, raw_seed, raw_vertical, raw_endpoint, raw_arc], axis=0)
    rx0 = max(0, int(np.floor(raw_all[:, 0].min() - 60)))
    rx1 = min(raw_image.shape[1], int(np.ceil(raw_all[:, 0].max() + 60)))
    ry0 = max(0, int(np.floor(raw_all[:, 1].min() - 60)))
    ry1 = min(raw_image.shape[0], int(np.ceil(raw_all[:, 1].max() + 60)))

    figure, axes = plt.subplots(2, 4, figsize=(18, 9), constrained_layout=True)

    def draw_geometry(axis: plt.Axes, offset: np.ndarray, current: np.ndarray, current_seed: np.ndarray, current_vertical: np.ndarray, current_endpoint: np.ndarray, current_arc: np.ndarray, prior: list[np.ndarray]) -> None:
        for item in prior:
            points = item - offset
            axis.plot(points[:, 0], points[:, 1], color="lime", linewidth=2.0)
        points = current_seed - offset
        axis.plot(points[:, 0], points[:, 1], color="yellow", linewidth=4.0)
        points = current - offset
        axis.plot(points[:, 0], points[:, 1], color="cyan", linewidth=3.0)
        points = current_vertical - offset
        axis.plot(points[:, 0], points[:, 1], color="red", linewidth=2.5)
        axis.add_patch(Polygon(current_endpoint - offset, closed=True, fill=False, edgecolor="magenta", linewidth=1.6))
        axis.add_patch(Polygon(current_arc - offset, closed=True, fill=False, edgecolor="orange", linewidth=1.6))

    axes[0, 0].imshow(raw_image[ry0:ry1, rx0:rx1], cmap="gray", vmin=0.0, vmax=85.0)
    raw_prior = [aligned_to_raw(case, family, frame_index, item) for item in supported_before]
    draw_geometry(
        axes[0, 0],
        np.array([rx0, ry0]),
        raw_segment,
        raw_seed,
        raw_vertical,
        raw_endpoint,
        raw_arc,
        raw_prior,
    )
    axes[0, 0].set_title("raw SAR + seed/path/barrier/ambiguity")

    axes[0, 1].imshow(image[y0:y1, x0:x1], cmap="gray", vmin=0.0, vmax=85.0)
    draw_geometry(
        axes[0, 1],
        np.array([x0, y0]),
        segment,
        seed,
        vertical,
        endpoint,
        arc,
        supported_before,
    )
    axes[0, 1].set_title(family)

    axes[0, 2].imshow(channels["local_contrast_31"][y0:y1, x0:x1], cmap="coolwarm")
    axes[0, 2].set_title("local contrast")
    axes[0, 3].imshow(channels["multiscale_laplacian_bright_ridge"][y0:y1, x0:x1], cmap="magma")
    axes[0, 3].set_title("bright-ridge response")

    axes[1, 0].imshow(world_image[y0:y1, x0:x1], cmap="gray", vmin=0.0, vmax=85.0)
    axes[1, 0].set_title("world-stabilized current frame")
    previous = max(0, frame_index - 1)
    following = min(len(case.frames) - 1, frame_index + 1)
    axes[1, 1].imshow(case.stacks[family][previous][y0:y1, x0:x1], cmap="gray", vmin=0.0, vmax=85.0)
    axes[1, 1].set_title(f"previous SAR {case.frames[previous]}")
    axes[1, 2].imshow(case.stacks[family][following][y0:y1, x0:x1], cmap="gray", vmin=0.0, vmax=85.0)
    axes[1, 2].set_title(f"next SAR {case.frames[following]}")
    axes[1, 3].axis("off")
    text_lines = [
        f"source={trace['source_primitive']}",
        f"destination={trace['destination_primitive']}",
        f"distance={trace['distance']}",
        f"orientation_difference={trace['orientation_difference']}",
        f"ridge_relation={trace['ridge_relation']}",
        f"contrast_relation={trace['contrast_relation']}",
        f"intensity_relation={trace['intensity_relation']}",
        f"width_relation={trace['width_relation']}",
        f"temporal_support={trace['temporal_support']}",
        f"world_recurrence={trace['world_background_recurrence']}",
        f"first_failed_gate={trace['first_failed_gate']}",
        f"state={trace['state_after']}",
        f"reason={trace['decision_reason']}",
    ]
    axes[1, 3].text(0.0, 1.0, "\n".join(text_lines), va="top", ha="left", family="monospace", fontsize=9)
    for axis in axes.ravel()[:-1]:
        axis.set_xticks([])
        axis.set_yticks([])
    figure.suptitle(
        f"{case.spec['case_id']} SAR {case.frames[frame_index]} | {trace['destination_primitive']} | {trace['state_after']}",
        fontsize=14,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def evaluate_frame(
    case: CaseData,
    config: dict[str, Any],
    family: str,
    frame_index: int,
    evidence_dir: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    image = case.stacks[family][frame_index]
    channels = single_channels(image)
    half_width = int(config["primitive_definition"]["segment_half_width_px"])
    patch_radius = int(config["primitive_definition"]["patch_radius_px"])
    gates = config["gates"]
    axis_angle = math.degrees(math.atan2(case.axis[1], case.axis[0])) % 180.0
    segments = build_segments(case, config)
    seed_segment = segments[0]["points"]
    seed_metrics = local_metrics(image, channels, seed_segment, half_width)
    seed_id = primitive_id(case.spec["case_id"], case.frames[frame_index], family, "seed", 0)
    seed_raw = aligned_to_raw(case, family, frame_index, seed_segment)
    seed_temporal = stack_recurrence(case.stacks[family], np.mean(seed_segment, axis=0), patch_radius)
    seed_world = world_recurrence_for_segment(case, family, frame_index, seed_segment, patch_radius)
    primitive_rows: list[dict[str, Any]] = [
        {
            "case_id": case.spec["case_id"],
            "frame": case.frames[frame_index],
            "coordinate_family": family,
            "propagation_mode": "SINGLE_FRAME_SPATIAL",
            "primitive_id": seed_id,
            "direction": "seed",
            "ordinal": 0,
            "geometry": format_points(seed_segment),
            "geometry_raw": format_points(seed_raw),
            "length": f"{polyline_length(seed_segment):.6f}",
            "width": f"{seed_metrics['width']:.6f}",
            "mean_intensity": f"{seed_metrics['mean_intensity']:.6f}",
            "median_intensity": f"{seed_metrics['median_intensity']:.6f}",
            "local_contrast": f"{seed_metrics['local_contrast']:.6f}",
            "ridge_response": f"{seed_metrics['ridge_response']:.6f}",
            "local_orientation": f"{seed_metrics['orientation']:.6f}",
            "fan_radial_relation": f"{seed_metrics['radial_relation']:.6f}",
            "fan_tangential_relation": f"{seed_metrics['tangential_relation']:.6f}",
            "temporal_support": f"{seed_temporal:.6f}",
            "world_stable_recurrence": f"{seed_world:.6f}",
            "shortest_seed_path": seed_id,
            "crosses_confirmed_background": "false",
            "enters_ambiguity_zone": "false",
            "state": "CONFIRMED_SEED",
            "state_reason": "R2 confirmed seed point expanded only along the frozen local seed tangent",
        }
    ]
    trace_rows: list[dict[str, Any]] = []
    supported_by_direction: dict[str, list[np.ndarray]] = {"left": [seed_segment], "right": [seed_segment]}
    source_ids = {"left": seed_id, "right": seed_id}
    source_states = {"left": "CONFIRMED_SEED", "right": "CONFIRMED_SEED"}
    path_ids = {"left": [seed_id], "right": [seed_id]}
    stopped = {"left": False, "right": False}
    expansion_step = 0

    for ordinal in range(1, max(int(config["primitive_definition"]["max_steps_left"]), int(config["primitive_definition"]["max_steps_right"])) + 1):
        for direction in ("left", "right"):
            max_steps = int(config["primitive_definition"][f"max_steps_{direction}"])
            if ordinal > max_steps or stopped[direction]:
                continue
            item = next(row for row in segments if row["direction"] == direction and row["ordinal"] == ordinal)
            segment = item["points"]
            expansion_step += 1
            destination_id = primitive_id(case.spec["case_id"], case.frames[frame_index], family, direction, ordinal)
            source_segment = supported_by_direction[direction][-1]
            distance = segment_distance(segment, source_segment)
            metrics = local_metrics(image, channels, segment, half_width)
            orientation_diff = orientation_difference_deg(metrics["orientation"], axis_angle)
            ridge_relation = safe_ratio(metrics["ridge_response"], seed_metrics["ridge_response"])
            contrast_relation = safe_ratio(metrics["local_contrast"], seed_metrics["local_contrast"])
            intensity_relation = safe_ratio(metrics["median_intensity"], seed_metrics["median_intensity"])
            width_relation = safe_ratio(metrics["width"], seed_metrics["width"])
            temporal_ncc = stack_recurrence(case.stacks[family], np.mean(segment, axis=0), patch_radius)
            world_ncc = world_recurrence_for_segment(case, family, frame_index, segment, patch_radius)
            background_distance = segment_distance(segment, case.vertical_aligned[frame_index])
            crosses_background = background_distance <= float(gates["background_barrier_buffer_px"])
            enters_ambiguity = polygon_contains_samples(case.endpoint_ambiguity_aligned, segment) or polygon_contains_samples(
                case.arc_clutter_ambiguity_aligned, segment
            )
            connected = distance <= float(gates["spatial_gap_max_px"])
            orientation_ok = orientation_diff <= float(gates["orientation_difference_max_deg"])
            width_ok = float(gates["width_ratio_min"]) <= width_relation <= float(gates["width_ratio_max"])
            ridge_ok = ridge_relation >= float(gates["ridge_relation_min"])
            contrast_ok = contrast_relation >= float(gates["contrast_relation_min"])
            structure_ok = orientation_ok and width_ok and (ridge_ok or contrast_ok)
            temporal_ok = temporal_ncc >= float(gates["temporal_ncc_min"])
            world_suspect = (
                world_ncc >= float(gates["world_background_ncc_min"])
                and world_ncc >= temporal_ncc + float(gates["world_minus_target_ncc_margin"])
                and not structure_ok
            )

            if crosses_background:
                state = "BACKGROUND_BLOCKED"
                failed = "CONFIRMED_VERTICAL_BACKGROUND"
                reason = "candidate segment touches or crosses the frozen vertical-background barrier"
            elif not connected:
                state = "NOT_CONNECTED_TO_SEED"
                failed = "SPATIAL_CONNECTED"
                reason = "candidate has no continuous path from the supported structure"
            elif enters_ambiguity:
                state = "UNRESOLVED_AT_ARC_OR_CLUTTER"
                failed = "AMBIGUITY_STOP"
                reason = "candidate enters the frozen endpoint or arc/clutter ambiguity zone"
            elif world_suspect:
                state = "BACKGROUND_SUSPECT_WORLD_STABLE"
                failed = "WORLD_BACKGROUND_COUNTERFACTUAL"
                reason = "world-stable recurrence exceeds target-aligned recurrence by the frozen margin"
            elif structure_ok and temporal_ok:
                state = "SUPPORTED_EXTENSION"
                failed = ""
                reason = "connected local structure passes independent structure and temporal/background gates"
            elif connected and orientation_ok and width_ok and (ridge_ok or contrast_ok or temporal_ok):
                state = "PROBABLE_EXTENSION"
                failed = "TEMPORAL_OR_STRUCTURE_SUPPORT_INCOMPLETE"
                reason = "connected structure is plausible but does not satisfy both independent support families"
            else:
                state = "TEMPORALLY_UNSUPPORTED"
                failed = "LOCAL_STRUCTURE_OR_TEMPORAL_SUPPORT"
                reason = "candidate lacks the frozen combination of structural continuity and temporal support"

            raw_segment = aligned_to_raw(case, family, frame_index, segment)
            candidate_path = path_ids[direction] + [destination_id]
            primitive_rows.append(
                {
                    "case_id": case.spec["case_id"],
                    "frame": case.frames[frame_index],
                    "coordinate_family": family,
                    "propagation_mode": "SINGLE_FRAME_SPATIAL",
                    "primitive_id": destination_id,
                    "direction": direction,
                    "ordinal": ordinal,
                    "geometry": format_points(segment),
                    "geometry_raw": format_points(raw_segment),
                    "length": f"{polyline_length(segment):.6f}",
                    "width": f"{metrics['width']:.6f}",
                    "mean_intensity": f"{metrics['mean_intensity']:.6f}",
                    "median_intensity": f"{metrics['median_intensity']:.6f}",
                    "local_contrast": f"{metrics['local_contrast']:.6f}",
                    "ridge_response": f"{metrics['ridge_response']:.6f}",
                    "local_orientation": f"{metrics['orientation']:.6f}",
                    "fan_radial_relation": f"{metrics['radial_relation']:.6f}",
                    "fan_tangential_relation": f"{metrics['tangential_relation']:.6f}",
                    "temporal_support": f"{temporal_ncc:.6f}",
                    "world_stable_recurrence": f"{world_ncc:.6f}",
                    "shortest_seed_path": ">".join(candidate_path),
                    "crosses_confirmed_background": str(crosses_background).lower(),
                    "enters_ambiguity_zone": str(enters_ambiguity).lower(),
                    "state": state,
                    "state_reason": reason,
                }
            )
            trace = {
                "case_id": case.spec["case_id"],
                "frame": case.frames[frame_index],
                "coordinate_family": family,
                "propagation_mode": "SINGLE_FRAME_SPATIAL",
                "expansion_step": expansion_step,
                "source_primitive": source_ids[direction],
                "destination_primitive": destination_id,
                "spatial_connected": str(connected).lower(),
                "distance": f"{distance:.6f}",
                "orientation_difference": f"{orientation_diff:.6f}",
                "ridge_relation": f"{ridge_relation:.6f}",
                "contrast_relation": f"{contrast_relation:.6f}",
                "intensity_relation": f"{intensity_relation:.6f}",
                "width_relation": f"{width_relation:.6f}",
                "temporal_support": f"{temporal_ncc:.6f}",
                "world_background_recurrence": f"{world_ncc:.6f}",
                "crosses_confirmed_background": str(crosses_background).lower(),
                "enters_ambiguity_zone": str(enters_ambiguity).lower(),
                "first_failed_gate": failed,
                "state_before": source_states[direction],
                "state_after": state,
                "decision_reason": reason,
                "evidence_card": "",
                "evidence_sha256": "",
            }
            if evidence_dir is not None:
                card = evidence_dir / case.spec["case_id"] / str(case.frames[frame_index]) / f"{destination_id}.png"
                evidence_card(card, case, family, frame_index, segment, supported_by_direction[direction], trace, channels)
                trace["evidence_card"] = str(card)
                trace["evidence_sha256"] = sha256_file(card)
            trace_rows.append(trace)

            if state == "SUPPORTED_EXTENSION":
                supported_by_direction[direction].append(segment)
                source_ids[direction] = destination_id
                source_states[direction] = state
                path_ids[direction].append(destination_id)
            else:
                stopped[direction] = True

    return primitive_rows, trace_rows


def run_case_frames(
    case_id: str,
    family: str,
    frame_selector: Sequence[int],
    output_dir: Path,
    render_cards: bool = True,
) -> tuple[Path, Path]:
    config = load_config()
    check_repository_gate(config)
    case = load_case(config, case_id, family)
    primitive_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    evidence_dir = output_dir / "evidence_cards" if render_cards else None
    for frame in frame_selector:
        frame_index = case.frames.index(int(frame))
        frame_primitives, frame_trace = evaluate_frame(case, config, family, frame_index, evidence_dir)
        primitive_rows.extend(frame_primitives)
        trace_rows.extend(frame_trace)
    primitive_path = output_dir / "structure_primitives.csv"
    trace_path = output_dir / "expansion_trace.csv"
    write_csv(primitive_path, primitive_rows, PRIMITIVE_FIELDS)
    write_csv(trace_path, trace_rows, TRACE_FIELDS)
    return primitive_path, trace_path


def pair_ncc_for_geometry(
    case: CaseData,
    family: str,
    geometry: np.ndarray,
    first_index: int,
    second_index: int,
    radius: int,
) -> float:
    midpoint = np.mean(geometry, axis=0)
    first_patch = patch(case.stacks[family][first_index], midpoint, radius)
    second_patch = patch(case.stacks[family][second_index], midpoint, radius)
    return ncc(first_patch, second_patch)


def temporal_structure_ok(trace: dict[str, str], config: dict[str, Any]) -> bool:
    gates = config["gates"]
    orientation_ok = float(trace["orientation_difference"]) <= float(gates["orientation_difference_max_deg"])
    width_ratio = float(trace["width_relation"])
    width_ok = float(gates["width_ratio_min"]) <= width_ratio <= float(gates["width_ratio_max"])
    ridge_ok = float(trace["ridge_relation"]) >= float(gates["ridge_relation_min"])
    contrast_ok = float(trace["contrast_relation"]) >= float(gates["contrast_relation_min"])
    return orientation_ok and width_ok and (ridge_ok or contrast_ok)


def run_temporal_case(
    case_id: str,
    family: str,
    output_dir: Path,
    render_cards: bool = True,
) -> tuple[Path, Path, Path, Path]:
    config = load_config()
    check_repository_gate(config)
    case = load_case(config, case_id, family)
    spatial_primitive_rows: list[dict[str, Any]] = []
    spatial_trace_rows: list[dict[str, Any]] = []
    evidence_dir = output_dir / "evidence_cards" if render_cards else None
    for frame_index in range(len(case.frames)):
        primitives, traces = evaluate_frame(case, config, family, frame_index, evidence_dir)
        spatial_primitive_rows.extend(primitives)
        spatial_trace_rows.extend(traces)

    spatial_primitive_path = output_dir / "spatial_structure_primitives.csv"
    spatial_trace_path = output_dir / "spatial_expansion_trace.csv"
    write_csv(spatial_primitive_path, spatial_primitive_rows, PRIMITIVE_FIELDS)
    write_csv(spatial_trace_path, spatial_trace_rows, TRACE_FIELDS)

    primitive_map = {
        (int(row["frame"]), row["direction"], int(row["ordinal"])): row for row in spatial_primitive_rows
    }
    trace_map: dict[tuple[int, str, int], dict[str, Any]] = {}
    for row in spatial_trace_rows:
        destination = primitive_map_key_from_id(row["destination_primitive"])
        trace_map[(int(row["frame"]), destination[0], destination[1])] = row

    temporal_primitive_rows: list[dict[str, Any]] = []
    temporal_trace_rows: list[dict[str, Any]] = []
    radius = int(config["primitive_definition"]["patch_radius_px"])
    temporal_threshold = float(config["gates"]["temporal_ncc_min"])

    for mode in ("FORWARD_CAUSAL_MICROPILOT", "OFFLINE_BIDIRECTIONAL_MICROPILOT"):
        mode_states: dict[tuple[int, str, int], str] = {}
        for frame in case.frames:
            seed_row = dict(primitive_map[(frame, "seed", 0)])
            seed_row["propagation_mode"] = mode
            seed_row["state"] = "CONFIRMED_SEED"
            seed_row["state_reason"] = "frozen primary seed transported only by the allowed research coordinate stack"
            temporal_primitive_rows.append(seed_row)
            mode_states[(frame, "seed", 0)] = "CONFIRMED_SEED"

        for frame_index, frame in enumerate(case.frames):
            if mode == "FORWARD_CAUSAL_MICROPILOT" and frame_index < case.primary_index:
                continue
            for direction in ("left", "right"):
                source_state = "CONFIRMED_SEED"
                source_id = primitive_map[(frame, "seed", 0)]["primitive_id"]
                for ordinal in range(1, int(config["primitive_definition"][f"max_steps_{direction}"]) + 1):
                    key = (frame, direction, ordinal)
                    if key not in primitive_map or key not in trace_map:
                        break
                    base_primitive = primitive_map[key]
                    base_trace = trace_map[key]
                    geometry = parse_points(base_primitive["geometry"])
                    hard_state = base_primitive["state"] in {
                        "BACKGROUND_BLOCKED",
                        "BACKGROUND_SUSPECT_WORLD_STABLE",
                        "UNRESOLVED_AT_ARC_OR_CLUTTER",
                        "NOT_CONNECTED_TO_SEED",
                    }
                    path_ok = source_state in {"CONFIRMED_SEED", "SUPPORTED_EXTENSION"}
                    structure_ok = temporal_structure_ok(base_trace, config)
                    neighbor_links: list[tuple[int, float]] = []
                    if frame_index > 0:
                        neighbor_links.append(
                            (
                                frame_index - 1,
                                pair_ncc_for_geometry(case, family, geometry, frame_index - 1, frame_index, radius),
                            )
                        )
                    if mode == "OFFLINE_BIDIRECTIONAL_MICROPILOT" and frame_index + 1 < len(case.frames):
                        neighbor_links.append(
                            (
                                frame_index + 1,
                                pair_ncc_for_geometry(case, family, geometry, frame_index, frame_index + 1, radius),
                            )
                        )
                    if mode == "FORWARD_CAUSAL_MICROPILOT":
                        neighbor_links = [item for item in neighbor_links if item[0] < frame_index]

                    valid_links: list[tuple[int, float]] = []
                    for neighbor_index, link_ncc in neighbor_links:
                        neighbor_frame = case.frames[neighbor_index]
                        neighbor_trace = trace_map.get((neighbor_frame, direction, ordinal))
                        if neighbor_trace is None or not temporal_structure_ok(neighbor_trace, config):
                            continue
                        if link_ncc >= temporal_threshold:
                            valid_links.append((neighbor_index, link_ncc))
                    temporal_link = max((value for _, value in valid_links), default=-1.0)

                    if hard_state:
                        state = base_primitive["state"]
                        failed = base_trace["first_failed_gate"]
                        reason = base_primitive["state_reason"]
                    elif not path_ok:
                        state = "NOT_CONNECTED_TO_SEED"
                        failed = "CURRENT_FRAME_SUPPORTED_PATH"
                        reason = "temporal relation cannot bypass a non-supported current-frame path"
                    elif structure_ok and valid_links:
                        state = "SUPPORTED_EXTENSION"
                        failed = ""
                        reason = "current-frame structure passes and a frozen cross-frame relation supplies temporal support"
                    elif structure_ok:
                        state = "PROBABLE_EXTENSION"
                        failed = "CROSS_FRAME_TEMPORAL_SUPPORT"
                        reason = "current-frame structure is plausible but no allowed temporal neighbor passes"
                    else:
                        state = "TEMPORALLY_UNSUPPORTED"
                        failed = "LOCAL_STRUCTURE_CONTINUITY"
                        reason = "current-frame structure fails before temporal support can be used"

                    output_primitive = dict(base_primitive)
                    output_primitive["propagation_mode"] = mode
                    output_primitive["state"] = state
                    output_primitive["state_reason"] = reason
                    output_primitive["temporal_support"] = f"{temporal_link:.6f}" if valid_links else ""
                    temporal_primitive_rows.append(output_primitive)
                    mode_states[key] = state

                    temporal_source_id = source_id
                    if valid_links:
                        best_index, _ = max(valid_links, key=lambda item: item[1])
                        temporal_source_id = primitive_map[(case.frames[best_index], direction, ordinal)]["primitive_id"]
                    temporal_trace = dict(base_trace)
                    temporal_trace["propagation_mode"] = mode
                    temporal_trace["source_primitive"] = temporal_source_id
                    temporal_trace["state_before"] = source_state
                    temporal_trace["state_after"] = state
                    temporal_trace["first_failed_gate"] = failed
                    temporal_trace["decision_reason"] = reason
                    temporal_trace["temporal_support"] = f"{temporal_link:.6f}" if valid_links else ""
                    temporal_trace_rows.append(temporal_trace)

                    if state == "SUPPORTED_EXTENSION":
                        source_state = state
                        source_id = base_primitive["primitive_id"]
                    else:
                        break

    temporal_primitive_path = output_dir / "temporal_structure_primitives.csv"
    temporal_trace_path = output_dir / "temporal_expansion_trace.csv"
    write_csv(temporal_primitive_path, temporal_primitive_rows, PRIMITIVE_FIELDS)
    write_csv(temporal_trace_path, temporal_trace_rows, TRACE_FIELDS)
    return spatial_primitive_path, spatial_trace_path, temporal_primitive_path, temporal_trace_path


def primitive_map_key_from_id(identifier: str) -> tuple[str, int]:
    suffix = identifier.rsplit("_", 1)[-1]
    if suffix == "SEED":
        return "seed", 0
    if suffix.startswith("LEFT"):
        return "left", int(suffix[-2:])
    if suffix.startswith("RIGHT"):
        return "right", int(suffix[-2:])
    raise ValueError(f"unexpected primitive id: {identifier}")


def summarize_stage(primitive_path: Path, trace_path: Path) -> dict[str, Any]:
    primitives = read_csv(primitive_path)
    traces = read_csv(trace_path)
    state_counts: dict[str, int] = {}
    for row in primitives:
        state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1
    return {
        "primitive_count": len(primitives),
        "trace_count": len(traces),
        "state_counts": state_counts,
        "background_blocked_count": state_counts.get("BACKGROUND_BLOCKED", 0),
        "ambiguity_stop_count": state_counts.get("UNRESOLVED_AT_ARC_OR_CLUTTER", 0),
        "primitive_path": str(primitive_path),
        "trace_path": str(trace_path),
    }
