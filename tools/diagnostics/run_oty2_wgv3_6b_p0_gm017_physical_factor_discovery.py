"""GM_RM017 physical response factor discovery and holdout validation.

Commands are intentionally staged:

audit-inputs           recover source provenance, frame mapping, and split
build-calibration-pack build GT-assisted calibration control/component tables
calibrate              fit and freeze factor parameters from calibration only
validate-generate      generate frozen holdout predictions without reading GT
evaluate               read holdout GT only after prediction freeze
verify-replay          replay frozen generation and compare SHA

There is intentionally no `all` command. The calibration/holdout separation is
part of the experiment contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image


DATE = "20260712"
SCENE = "GM_RM017"
START_COMMIT = "aba57096e6b38e33bfac4a6e68d6d00aa40ace5c"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
TARGET_THREAD = "oty1t_obj_GM_RM017_bytetrack_bt_0010"
NEGATIVE_CONTROL_THREAD = "oty1t_obj_GM_RM017_bytetrack_bt_0002"
NEGATIVE_CONTROL_NODE = "GM_RM017_N005"
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
OUT_DIR = REPO_ROOT / "outputs" / f"wgv3_6b_p0_gm017_physical_factor_discovery_{DATE}"
VERIFY_TMP_DIR = OUT_DIR / "_verify_replay_tmp"

PAIR_CSV = SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv"
FRAME_MAP_CSV = SAMPLES_DIR / "oty2_object_alignment_frame_map_sample.csv"
TEMPORAL_WINDOWS_CSV = SAMPLES_DIR / "oty2_object_sar_temporal_windows_sample.csv"
GRAPH_NODES_CSV = SAMPLES_DIR / "oty2_optical_timeline_graph_nodes_20260705_175222.csv"
GRAPH_EDGES_CSV = SAMPLES_DIR / "oty2_optical_timeline_graph_edges_20260705_175222.csv"
SCENE_CONFIG = REPO_ROOT / "configs" / "scene_config.yaml"

DOCS_READ = [
    "docs/OTY2_SESSION_START_HERE.md",
    "docs/OTY2_OPTICAL_STREAM_GENERALIZATION_PROTOCOL.md",
    "docs/OTY2_OPTICAL_STREAM_MECHANISM_ADJUSTMENT_DESIGN.md",
    "docs/OTY2_POINT_TO_STRUCTURE_OPTICAL_SAR_VEHICLE_RESPONSE_FRAMEWORK.md",
    "docs/OTY2_GENERATION_FREEZE_AND_GT_ASSISTED_ANALYSIS_BOUNDARY.md",
]

CALIBRATION_SAR_START = 315
CALIBRATION_SAR_END = 360
GUARD_SAR_START = 361
GUARD_SAR_END = 370
HOLDOUT_SAR_START = 371
HOLDOUT_SAR_END = 394

SAR_WIDTH = 2308
SAR_HEIGHT = 1334
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
PX_TO_M = 0.03

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6b_p0_gm017_physical_factor_discovery_{DATE}.md",
    "input_provenance": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_input_provenance_audit_{DATE}.csv",
    "frame_alignment": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frame_alignment_audit_{DATE}.csv",
    "split_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_split_manifest_{DATE}.csv",
    "control_points": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_calibration_control_points_{DATE}.csv",
    "components": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_response_component_observations_{DATE}.csv",
    "motion_fit": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_motion_factor_fit_{DATE}.csv",
    "background_fit": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_background_stability_fit_{DATE}.csv",
    "visibility_fit": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_visibility_transition_fit_{DATE}.csv",
    "scale_fit": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_scale_range_fit_{DATE}.csv",
    "trend_fit": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_optical_sar_trend_fit_{DATE}.csv",
    "frozen_params": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_factor_parameters_{DATE}.csv",
    "holdout_predictions": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_holdout_factor_predictions_{DATE}.csv",
    "holdout_eval": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_holdout_evaluation_{DATE}.csv",
    "verdicts": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_factor_verdicts_{DATE}.csv",
    "counterexamples": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_counterexamples_{DATE}.csv",
    "gate_integrity": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_gate_integrity_{DATE}.csv",
    "frozen_manifest": SAMPLES_DIR / f"oty2_wgv3_6b_p0_gm017_frozen_manifest_{DATE}.csv",
}

FREEZE_OUTPUT_KEYS = [
    "frozen_params",
    "holdout_predictions",
    "motion_fit",
    "background_fit",
    "visibility_fit",
    "scale_fit",
    "trend_fit",
]


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fmt(value: Any, ndigits: int = 6) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return ""
    return f"{number:.{ndigits}f}".rstrip("0").rstrip(".")


def ensure_dirs() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover - diagnostic only
        return f"unavailable:{exc}"


def load_scene_config() -> dict[str, Any]:
    with SCENE_CONFIG.open(encoding="utf-8") as handle:
        return json.load(handle)


def scene_paths() -> dict[str, Path]:
    config = load_scene_config()
    paths = config["scenes"][SCENE]["paths"]
    return {key: Path(value) for key, value in paths.items()}


def image_path(kind: str, frame: int) -> Path:
    paths = scene_paths()
    if kind == "optical":
        return paths["optical_frames_dir"] / f"{frame:06d}.png"
    if kind == "sar_gray":
        return paths["sar_gray_frames_dir"] / f"{frame:06d}.png"
    raise ValueError(kind)


def list_frame_numbers(directory: Path) -> list[int]:
    if not directory.exists():
        return []
    frames = []
    for path in directory.glob("*.png"):
        try:
            frames.append(int(path.stem))
        except ValueError:
            pass
    return sorted(frames)


def box_from_row(row: Mapping[str, Any], prefix: str) -> tuple[float, float, float, float]:
    return (
        parse_float(row[f"{prefix}_bbox_x1"]),
        parse_float(row[f"{prefix}_bbox_y1"]),
        parse_float(row[f"{prefix}_bbox_x2"]),
        parse_float(row[f"{prefix}_bbox_y2"]),
    )


def box_center(box: Sequence[float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def box_width(box: Sequence[float]) -> float:
    return max(0.0, box[2] - box[0])


def box_height(box: Sequence[float]) -> float:
    return max(0.0, box[3] - box[1])


def expand_box(box: Sequence[float], margin: float, width: int = SAR_WIDTH, height: int = SAR_HEIGHT) -> tuple[int, int, int, int]:
    x1 = max(0, int(math.floor(box[0] - margin)))
    y1 = max(0, int(math.floor(box[1] - margin)))
    x2 = min(width - 1, int(math.ceil(box[2] + margin)))
    y2 = min(height - 1, int(math.ceil(box[3] + margin)))
    if x2 <= x1:
        x2 = min(width - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(height - 1, y1 + 1)
    return x1, y1, x2, y2


def box_from_center(cx: float, cy: float, w: float, h: float) -> tuple[float, float, float, float]:
    return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)


def fan_coords(u: float, v: float) -> dict[str, float]:
    local_x_px = u - FAN_CENTER_X
    local_y_px = FAN_CENTER_Y - v
    radial_px = math.hypot(local_x_px, local_y_px)
    theta_deg = math.degrees(math.atan2(local_x_px, local_y_px)) if radial_px else 0.0
    return {
        "local_x_px": local_x_px,
        "local_y_px": local_y_px,
        "radial_px": radial_px,
        "theta_deg": theta_deg,
        "local_x_m": local_x_px * PX_TO_M,
        "local_y_m": local_y_px * PX_TO_M,
        "radial_m": radial_px * PX_TO_M,
    }


def linear_fit(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float]:
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    design = np.vstack([np.ones_like(x), x]).T
    intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
    return float(intercept), float(slope)


def multi_fit(features: np.ndarray, y: Sequence[float]) -> np.ndarray:
    target = np.asarray(y, dtype=float)
    design = np.column_stack([np.ones(len(features)), features])
    return np.linalg.lstsq(design, target, rcond=None)[0]


def predict_linear(intercept: float, slope: float, x: float) -> float:
    return intercept + slope * x


def pair_rows() -> list[dict[str, str]]:
    return read_csv(PAIR_CSV)


def gm17_pair_rows() -> list[dict[str, str]]:
    return [row for row in pair_rows() if row.get("scene") == SCENE]


def target_rows() -> list[dict[str, str]]:
    rows = [
        row
        for row in gm17_pair_rows()
        if row.get("optical_thread_id") == TARGET_THREAD and row.get("usable_for_calibration") == "true"
    ]
    return sorted(rows, key=lambda row: (parse_int(row["sar_frame"]), row["pair_id"]))


def calibration_rows() -> list[dict[str, str]]:
    return [row for row in target_rows() if CALIBRATION_SAR_START <= parse_int(row["sar_frame"]) <= CALIBRATION_SAR_END]


def holdout_gt_rows() -> list[dict[str, str]]:
    return [row for row in target_rows() if HOLDOUT_SAR_START <= parse_int(row["sar_frame"]) <= HOLDOUT_SAR_END]


def row_for_sar(rows: Sequence[Mapping[str, str]], sar_frame: int) -> dict[str, str] | None:
    matches = [row for row in rows if parse_int(row.get("sar_frame")) == sar_frame]
    if not matches:
        return None
    return sorted(matches, key=lambda row: row.get("pair_id", ""))[0]


def compact_range(values: Iterable[int]) -> str:
    vals = sorted(set(values))
    if not vals:
        return ""
    ranges: list[tuple[int, int]] = []
    start = prev = vals[0]
    for value in vals[1:]:
        if value == prev + 1:
            prev = value
        else:
            ranges.append((start, prev))
            start = prev = value
    ranges.append((start, prev))
    return ";".join(str(a) if a == b else f"{a}-{b}" for a, b in ranges)


def nearest_frame_map(object_id: str, optical_frame: int) -> dict[str, str] | None:
    rows = [
        row
        for row in read_csv(FRAME_MAP_CSV)
        if row.get("scene") == SCENE and row.get("object_hypothesis_id") == object_id and parse_int(row.get("optical_frame_num")) == optical_frame
    ]
    return rows[0] if rows else None


def temporal_window(object_id: str) -> dict[str, str] | None:
    rows = [
        row
        for row in read_csv(TEMPORAL_WINDOWS_CSV)
        if row.get("scene") == SCENE and row.get("object_hypothesis_id") == object_id
    ]
    return rows[0] if rows else None


def component_stats(xs: list[int], ys: list[int], values: list[float]) -> dict[str, float]:
    arr_x = np.asarray(xs, dtype=float)
    arr_y = np.asarray(ys, dtype=float)
    arr_v = np.asarray(values, dtype=float)
    centroid_x = float(np.average(arr_x, weights=np.maximum(arr_v, 1.0)))
    centroid_y = float(np.average(arr_y, weights=np.maximum(arr_v, 1.0)))
    if len(arr_x) >= 3:
        coords = np.column_stack([arr_x - arr_x.mean(), arr_y - arr_y.mean()])
        cov = np.cov(coords, rowvar=False)
        eigvals, eigvecs = np.linalg.eigh(cov)
        order = np.argsort(eigvals)[::-1]
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]
        axis1 = 4.0 * math.sqrt(max(float(eigvals[0]), 0.0))
        axis2 = 4.0 * math.sqrt(max(float(eigvals[1]), 0.0))
        orientation = math.degrees(math.atan2(float(eigvecs[1, 0]), float(eigvecs[0, 0])))
    else:
        axis1 = axis2 = 0.0
        orientation = 0.0
    width = float(arr_x.max() - arr_x.min() + 1)
    height = float(arr_y.max() - arr_y.min() + 1)
    perimeter_box = max(width * height, 1.0)
    return {
        "centroid_x": centroid_x,
        "centroid_y": centroid_y,
        "bbox_x1": float(arr_x.min()),
        "bbox_y1": float(arr_y.min()),
        "bbox_x2": float(arr_x.max()),
        "bbox_y2": float(arr_y.max()),
        "pixel_area": float(len(arr_x)),
        "integrated_energy": float(arr_v.sum()),
        "mean_energy": float(arr_v.mean()),
        "peak_energy": float(arr_v.max()),
        "axis1_px": axis1,
        "axis2_px": axis2,
        "aspect_ratio": axis1 / max(axis2, 1e-6),
        "orientation_deg": orientation,
        "compactness": float(len(arr_x)) / perimeter_box,
    }


def extract_components(
    sar_frame: int,
    roi: Sequence[int],
    *,
    min_pixels: int = 12,
    threshold_quantile: float = 94.0,
    mean_std_k: float = 1.05,
    max_components: int = 80,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = image_path("sar_gray", sar_frame)
    image = Image.open(path).convert("L")
    x1, y1, x2, y2 = [int(v) for v in roi]
    crop = np.asarray(image.crop((x1, y1, x2 + 1, y2 + 1)), dtype=np.float32)
    if crop.size == 0:
        return [], {"threshold": "", "candidate_pixels": 0, "cap_triggered": "false"}
    threshold = max(float(crop.mean() + mean_std_k * crop.std()), float(np.percentile(crop, threshold_quantile)))
    mask = crop >= threshold
    visited = np.zeros(mask.shape, dtype=bool)
    h, w = mask.shape
    components: list[dict[str, Any]] = []
    ys, xs = np.nonzero(mask)
    for yy, xx in zip(ys.tolist(), xs.tolist()):
        if visited[yy, xx]:
            continue
        stack = [(xx, yy)]
        visited[yy, xx] = True
        comp_xs: list[int] = []
        comp_ys: list[int] = []
        comp_values: list[float] = []
        while stack:
            cx, cy = stack.pop()
            comp_xs.append(cx + x1)
            comp_ys.append(cy + y1)
            comp_values.append(float(crop[cy, cx]))
            for ny in range(max(0, cy - 1), min(h, cy + 2)):
                for nx in range(max(0, cx - 1), min(w, cx + 2)):
                    if visited[ny, nx] or not mask[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    stack.append((nx, ny))
        if len(comp_xs) < min_pixels:
            continue
        stats = component_stats(comp_xs, comp_ys, comp_values)
        stats["sar_frame"] = sar_frame
        components.append(stats)
    components.sort(key=lambda row: (row["integrated_energy"], row["pixel_area"]), reverse=True)
    cap_triggered = len(components) > max_components
    return components[:max_components], {
        "threshold": threshold,
        "candidate_pixels": int(mask.sum()),
        "cap_triggered": "true" if cap_triggered else "false",
        "roi": f"{x1},{y1},{x2},{y2}",
    }


def component_role(row: Mapping[str, Any], predicted_center: tuple[float, float] | None = None) -> str:
    area = parse_float(row.get("pixel_area"))
    aspect = parse_float(row.get("aspect_ratio"), 1.0)
    peak = parse_float(row.get("peak_energy"))
    if predicted_center is not None:
        dist = math.hypot(parse_float(row.get("centroid_x")) - predicted_center[0], parse_float(row.get("centroid_y")) - predicted_center[1])
    else:
        dist = 0.0
    if area < 20:
        return "isolated_small_atom"
    if aspect > 4.0 and area > 80:
        return "background_arc_candidate"
    if dist < 45 and area > 60:
        return "body_core_candidate"
    if peak > 180 and area <= 80:
        return "endpoint_hotspot_candidate"
    if area > 250:
        return "large_response_candidate"
    return "unresolved_atom"


def command_audit_inputs() -> None:
    ensure_dirs()
    paths = scene_paths()
    optical_frames = list_frame_numbers(paths["optical_frames_dir"])
    sar_frames = list_frame_numbers(paths["sar_gray_frames_dir"])
    gm_rows = gm17_pair_rows()
    target = target_rows()
    target_optical = [parse_int(row["optical_frame"]) for row in target]
    target_sar = [parse_int(row["sar_frame"]) for row in target]
    all_optical = [parse_int(row["optical_frame"]) for row in gm_rows]
    all_sar = [parse_int(row["sar_frame"]) for row in gm_rows]
    n005_window = temporal_window("oty1t_obj_GM_RM017_bytetrack_bt_0002")
    target_window = temporal_window(TARGET_THREAD)
    node_rows = read_csv(GRAPH_NODES_CSV)
    edge_rows = read_csv(GRAPH_EDGES_CSV)
    n005_node = next(row for row in node_rows if row.get("node_id") == NEGATIVE_CONTROL_NODE)
    n005_edge = next(row for row in edge_rows if row.get("edge_id") == "GM_RM017_E002")
    sar_sample = image_path("sar_gray", CALIBRATION_SAR_START)
    sar_size = Image.open(sar_sample).size if sar_sample.exists() else ("", "")
    optical_sample = image_path("optical", min(target_optical))
    optical_size = Image.open(optical_sample).size if optical_sample.exists() else ("", "")

    provenance_fields = [
        "item_id",
        "source_kind",
        "source_path",
        "status",
        "record_count",
        "gm_rm017_count",
        "frame_or_range",
        "runtime_or_eval_role",
        "key_finding",
        "notes",
    ]
    provenance_rows: list[dict[str, Any]] = []
    for idx, doc in enumerate(DOCS_READ, 1):
        path = REPO_ROOT / doc
        provenance_rows.append({
            "item_id": f"DOC{idx:02d}",
            "source_kind": "required_doc",
            "source_path": doc,
            "status": "present" if path.exists() else "missing",
            "record_count": "",
            "gm_rm017_count": "",
            "frame_or_range": "",
            "runtime_or_eval_role": "protocol_boundary",
            "key_finding": "read_before_task; no final box, selector, ranking, or GT leakage into holdout generation",
            "notes": "",
        })
    provenance_rows.extend([
        {
            "item_id": "SRC01",
            "source_kind": "paired_annotations",
            "source_path": str(PAIR_CSV.relative_to(REPO_ROOT)),
            "status": "present",
            "record_count": len(pair_rows()),
            "gm_rm017_count": len(gm_rows),
            "frame_or_range": f"optical={min(all_optical)}-{max(all_optical)};sar={min(all_sar)}-{max(all_sar)}",
            "runtime_or_eval_role": "calibration_gt_and_later_eval_only",
            "key_finding": f"target_thread={TARGET_THREAD}; target_paired_sar={compact_range(target_sar)}",
            "notes": "GT centers are not scattering-center truth; used only for calibration/evaluation phases.",
        },
        {
            "item_id": "SRC02",
            "source_kind": "frame_map",
            "source_path": str(FRAME_MAP_CSV.relative_to(REPO_ROOT)),
            "status": "present",
            "record_count": len(read_csv(FRAME_MAP_CSV)),
            "gm_rm017_count": sum(1 for row in read_csv(FRAME_MAP_CSV) if row.get("scene") == SCENE),
            "frame_or_range": "alignment_mode=frame_ratio_hypothesis",
            "runtime_or_eval_role": "runtime_safe_temporal_mapping_hypothesis",
            "key_finding": "exact timestamp metadata is unavailable; current source is frame-count ratio audit only",
            "notes": "",
        },
        {
            "item_id": "SRC03",
            "source_kind": "temporal_window",
            "source_path": str(TEMPORAL_WINDOWS_CSV.relative_to(REPO_ROOT)),
            "status": "present",
            "record_count": len(read_csv(TEMPORAL_WINDOWS_CSV)),
            "gm_rm017_count": sum(1 for row in read_csv(TEMPORAL_WINDOWS_CSV) if row.get("scene") == SCENE),
            "frame_or_range": f"N005 optical={n005_window.get('optical_start_frame')}-{n005_window.get('optical_end_frame')};sar={n005_window.get('sar_start_frame')}-{n005_window.get('sar_end_frame')}",
            "runtime_or_eval_role": "temporal_window_only_no_sar_band",
            "key_finding": "N005 real optical range is 121-129; SAR range comes from P0 frame-ratio temporal-window source, not exact timestamp truth",
            "notes": n005_window.get("notes", ""),
        },
        {
            "item_id": "SRC04",
            "source_kind": "optical_timeline_graph_node",
            "source_path": str(GRAPH_NODES_CSV.relative_to(REPO_ROOT)),
            "status": "present",
            "record_count": len(node_rows),
            "gm_rm017_count": sum(1 for row in node_rows if row.get("scene") == SCENE),
            "frame_or_range": f"{n005_node['frame_start']}-{n005_node['frame_end']}",
            "runtime_or_eval_role": "manual_non_vehicle_control_for_calibration_and_counterexample",
            "key_finding": f"{NEGATIVE_CONTROL_NODE}={n005_node['node_type']}; {n005_node['reason']}",
            "notes": "N005 identity is not used by holdout generation.",
        },
        {
            "item_id": "SRC05",
            "source_kind": "optical_timeline_graph_edge",
            "source_path": str(GRAPH_EDGES_CSV.relative_to(REPO_ROOT)),
            "status": "present",
            "record_count": len(edge_rows),
            "gm_rm017_count": sum(1 for row in edge_rows if row.get("scene") == SCENE),
            "frame_or_range": f"{n005_edge['from_node']}->{n005_edge['to_node']}",
            "runtime_or_eval_role": "manual_non_vehicle_exclusion_control",
            "key_finding": n005_edge["visual_basis"],
            "notes": n005_edge["reason"],
        },
        {
            "item_id": "SRC06",
            "source_kind": "image_inventory",
            "source_path": str(paths["optical_frames_dir"]),
            "status": "present" if optical_frames else "missing",
            "record_count": len(optical_frames),
            "gm_rm017_count": len(optical_frames),
            "frame_or_range": f"{optical_frames[0]}-{optical_frames[-1]}" if optical_frames else "",
            "runtime_or_eval_role": "runtime_safe_optical_frame_inventory",
            "key_finding": f"sample_size={optical_size}",
            "notes": "",
        },
        {
            "item_id": "SRC07",
            "source_kind": "image_inventory",
            "source_path": str(paths["sar_gray_frames_dir"]),
            "status": "present" if sar_frames else "missing",
            "record_count": len(sar_frames),
            "gm_rm017_count": len(sar_frames),
            "frame_or_range": f"{sar_frames[0]}-{sar_frames[-1]}" if sar_frames else "",
            "runtime_or_eval_role": "runtime_safe_sar_gray_frame_inventory",
            "key_finding": f"sample_size={sar_size}; grid_matches_2308x1334={sar_size == (SAR_WIDTH, SAR_HEIGHT)}",
            "notes": "Coordinate audit uses fan center from scene_config and PX_TO_M=0.03 inherited from existing WGV3.6A R2.1 code path; final output remains SAR image-domain boxes/candidates.",
        },
    ])
    write_csv(OUTPUTS["input_provenance"], provenance_rows, provenance_fields)

    alignment_fields = [
        "alignment_id",
        "scene",
        "object_hypothesis_id",
        "optical_frame_start",
        "optical_frame_end",
        "sar_frame_start",
        "sar_frame_end",
        "optical_fps",
        "sar_fps",
        "fps_ratio",
        "sync_mode",
        "alignment_mode",
        "alignment_confidence",
        "source_path",
        "gt_used",
        "notes",
    ]
    temporal_rows = {row["object_hypothesis_id"]: row for row in read_csv(TEMPORAL_WINDOWS_CSV) if row.get("scene") == SCENE}
    alignment_rows = []
    for idx, object_id in enumerate([TARGET_THREAD, "oty1t_obj_GM_RM017_bytetrack_bt_0012", "oty1t_obj_GM_RM017_bytetrack_bt_0014", NEGATIVE_CONTROL_THREAD], 1):
        row = temporal_rows.get(object_id, {})
        alignment_rows.append({
            "alignment_id": f"ALIGN{idx:02d}",
            "scene": SCENE,
            "object_hypothesis_id": object_id,
            "optical_frame_start": row.get("optical_start_frame", ""),
            "optical_frame_end": row.get("optical_end_frame", ""),
            "sar_frame_start": row.get("sar_start_frame", ""),
            "sar_frame_end": row.get("sar_end_frame", ""),
            "optical_fps": row.get("optical_fps", "24"),
            "sar_fps": row.get("sar_fps", "50"),
            "fps_ratio": row.get("fps_ratio", "2.083333"),
            "sync_mode": row.get("sync_mode", "software_sync_zero_offset_assumption"),
            "alignment_mode": "frame_ratio_hypothesis",
            "alignment_confidence": row.get("confidence_status", row.get("alignment_confidence", "")),
            "source_path": str(TEMPORAL_WINDOWS_CSV.relative_to(REPO_ROOT)),
            "gt_used": "false",
            "notes": row.get("notes", ""),
        })
    alignment_rows.append({
        "alignment_id": "ALIGN05",
        "scene": SCENE,
        "object_hypothesis_id": f"{TARGET_THREAD}_paired_gt_fit",
        "optical_frame_start": min(target_optical),
        "optical_frame_end": max(target_optical),
        "sar_frame_start": min(target_sar),
        "sar_frame_end": max(target_sar),
        "optical_fps": "derived_from_P0=24",
        "sar_fps": "derived_from_P0=50",
        "fps_ratio": "paired rows show duplicated optical frames and dense SAR frames; exact timestamp still not solved",
        "sync_mode": "paired_gt_posthoc_mapping_for_audit_only",
        "alignment_mode": "paired_annotations_actual_rows",
        "alignment_confidence": "posthoc_gt_available",
        "source_path": str(PAIR_CSV.relative_to(REPO_ROOT)),
        "gt_used": "true_for_audit_and_calibration_only",
        "notes": "This row records actual paired rows and must not be used as holdout generation input.",
    })
    write_csv(OUTPUTS["frame_alignment"], alignment_rows, alignment_fields)

    split_fields = [
        "segment_id",
        "segment_role",
        "sar_frame_start",
        "sar_frame_end",
        "optical_frame_start",
        "optical_frame_end",
        "physical_vehicle_id_eval_only",
        "gt_allowed",
        "future_allowed",
        "purpose",
        "selection_reason",
    ]
    split_rows = [
        {
            "segment_id": "GM017_DISC_CAL_0010",
            "segment_role": "physical_discovery_and_parameter_calibration",
            "sar_frame_start": CALIBRATION_SAR_START,
            "sar_frame_end": CALIBRATION_SAR_END,
            "optical_frame_start": 151,
            "optical_frame_end": 173,
            "physical_vehicle_id_eval_only": "PV_GM17_WHITE_SUV_FROM_TIMELINE_N002",
            "gt_allowed": "true",
            "future_allowed": "true_within_calibration_only",
            "purpose": "fit F1-F5 parameters from confirmed paired rows and SAR images",
            "selection_reason": "continuous SAR block with calibration-eligible target thread rows; before holdout and separated by guard gap",
        },
        {
            "segment_id": "GM017_GUARD_0010",
            "segment_role": "time_guard_gap",
            "sar_frame_start": GUARD_SAR_START,
            "sar_frame_end": GUARD_SAR_END,
            "optical_frame_start": 173,
            "optical_frame_end": 178,
            "physical_vehicle_id_eval_only": "PV_GM17_WHITE_SUV_FROM_TIMELINE_N002",
            "gt_allowed": "false",
            "future_allowed": "false",
            "purpose": "prevent adjacent local segment leakage between calibration and holdout",
            "selection_reason": "10 continuous SAR frames between calibration and holdout",
        },
        {
            "segment_id": "GM017_HOLDOUT_0010",
            "segment_role": "holdout_validation_generation_then_eval",
            "sar_frame_start": HOLDOUT_SAR_START,
            "sar_frame_end": HOLDOUT_SAR_END,
            "optical_frame_start": 178,
            "optical_frame_end": 189,
            "physical_vehicle_id_eval_only": "PV_GM17_WHITE_SUV_FROM_TIMELINE_N002",
            "gt_allowed": "false_during_validate_generate;true_after_prediction_freeze_in_evaluate",
            "future_allowed": "false_during_validate_generate",
            "purpose": "run frozen factor library without target GT, then evaluate after SHA freeze",
            "selection_reason": "24 continuous SAR frames after guard gap; not used for fitting",
        },
        {
            "segment_id": "GM017_N005_BACKGROUND_CONTROL",
            "segment_role": "background_non_vehicle_control",
            "sar_frame_start": n005_window.get("sar_start_frame", "249"),
            "sar_frame_end": n005_window.get("sar_end_frame", "274"),
            "optical_frame_start": n005_window.get("optical_start_frame", "121"),
            "optical_frame_end": n005_window.get("optical_end_frame", "129"),
            "physical_vehicle_id_eval_only": "GM_RM017_NONVEHICLE_001",
            "gt_allowed": "manual_non_vehicle_status_allowed_for_calibration_counterexample_only",
            "future_allowed": "false_for_holdout_generation",
            "purpose": "negative control for F2 and counterexample ledger",
            "selection_reason": "graph node GM_RM017_N005 / edge E002 records foreground barrier or temporary structure, not vehicle",
        },
    ]
    write_csv(OUTPUTS["split_manifest"], split_rows, split_fields)
    update_gate_integrity(replay_status="")
    write_frozen_manifest("audit-inputs")
    write_report()


def build_control_and_components() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    control_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    cap_rows: list[str] = []
    for idx, row in enumerate(calibration_rows(), 1):
        sar_frame = parse_int(row["sar_frame"])
        gt_box = box_from_row(row, "sar")
        gt_center = box_center(gt_box)
        roi = expand_box(gt_box, 70)
        components, meta = extract_components(sar_frame, roi, min_pixels=10, threshold_quantile=93.0, mean_std_k=0.95, max_components=60)
        cp_id = f"CP_GM017_0010_{idx:04d}"
        supported_ids = []
        rejected_ids = []
        for cidx, comp in enumerate(components, 1):
            comp_id = f"COMP_CAL_{sar_frame:06d}_{cidx:03d}"
            cx, cy = comp["centroid_x"], comp["centroid_y"]
            coords = fan_coords(cx, cy)
            inside = gt_box[0] <= cx <= gt_box[2] and gt_box[1] <= cy <= gt_box[3]
            distance = math.hypot(cx - gt_center[0], cy - gt_center[1])
            role = component_role(comp, gt_center)
            vehicle_explainable = inside or distance <= max(box_width(gt_box), box_height(gt_box)) * 0.35
            background_explainable = (not inside) and (distance > max(box_width(gt_box), box_height(gt_box)) * 0.55 or role == "background_arc_candidate")
            if vehicle_explainable:
                supported_ids.append(comp_id)
            if background_explainable:
                rejected_ids.append(comp_id)
            component_rows.append({
                "component_id": comp_id,
                "phase": "calibration_gt_assisted",
                "segment_id": "GM017_DISC_CAL_0010",
                "sar_frame": sar_frame,
                "optical_frame": row["optical_frame"],
                "source_kind": "sar_gray_component_in_gt_expanded_roi",
                "extraction_roi": meta["roi"],
                "extraction_threshold": fmt(meta["threshold"]),
                "candidate_kind": "vehicle_explainable" if vehicle_explainable else ("background_explainable" if background_explainable else "currently_unexplained"),
                "bbox": f"{fmt(comp['bbox_x1'])},{fmt(comp['bbox_y1'])},{fmt(comp['bbox_x2'])},{fmt(comp['bbox_y2'])}",
                "centroid_x": fmt(cx),
                "centroid_y": fmt(cy),
                "pixel_area": fmt(comp["pixel_area"]),
                "integrated_energy": fmt(comp["integrated_energy"]),
                "mean_energy": fmt(comp["mean_energy"]),
                "peak_energy": fmt(comp["peak_energy"]),
                "axis1_px": fmt(comp["axis1_px"]),
                "axis2_px": fmt(comp["axis2_px"]),
                "aspect_ratio": fmt(comp["aspect_ratio"]),
                "orientation_deg": fmt(comp["orientation_deg"]),
                "compactness": fmt(comp["compactness"]),
                "local_x_px": fmt(coords["local_x_px"]),
                "local_y_px": fmt(coords["local_y_px"]),
                "radial_px": fmt(coords["radial_px"]),
                "theta_deg": fmt(coords["theta_deg"]),
                "local_x_m": fmt(coords["local_x_m"]),
                "local_y_m": fmt(coords["local_y_m"]),
                "radial_m": fmt(coords["radial_m"]),
                "vehicle_explainable": "true" if vehicle_explainable else "false",
                "background_explainable": "true" if background_explainable else "false",
                "both_explainable": "false",
                "currently_unexplained": "false" if vehicle_explainable or background_explainable else "true",
                "component_role": role,
                "matched_control_point_id": cp_id if vehicle_explainable else "",
                "distance_to_control_center_px": fmt(distance),
                "cap_triggered": meta["cap_triggered"],
                "provenance": "GT-assisted calibration; GT center is not scattering center truth",
            })
        if meta["cap_triggered"] == "true":
            cap_rows.append(str(sar_frame))
        control_rows.append({
            "control_point_id": cp_id,
            "sar_frame": sar_frame,
            "gt_instance_id": row["sar_gt_id"],
            "bbox": f"{fmt(gt_box[0])},{fmt(gt_box[1])},{fmt(gt_box[2])},{fmt(gt_box[3])}",
            "bbox_center": f"{fmt(gt_center[0])},{fmt(gt_center[1])}",
            "bbox_scale": f"{fmt(box_width(gt_box))}x{fmt(box_height(gt_box))}",
            "manually_supported_vehicle_response_ids": ";".join(supported_ids),
            "manually_rejected_background_ids": ";".join(rejected_ids),
            "optical_state": row.get("visibility_state", ""),
            "provenance": f"{PAIR_CSV.relative_to(REPO_ROOT)}; gt-assisted calibration only",
            "confidence": row.get("pair_confidence", ""),
        })

    # Background-control extraction uses N005 temporal window but no vehicle identity in holdout generation.
    n005_window = temporal_window(NEGATIVE_CONTROL_THREAD) or {}
    bg_start = parse_int(n005_window.get("sar_start_frame"), 249)
    bg_end = parse_int(n005_window.get("sar_end_frame"), 274)
    for sar_frame in range(bg_start, bg_end + 1, 2):
        roi = (0, 700, SAR_WIDTH - 1, SAR_HEIGHT - 1)
        components, meta = extract_components(sar_frame, roi, min_pixels=18, threshold_quantile=99.70, mean_std_k=2.0, max_components=90)
        for cidx, comp in enumerate(components, 1):
            comp_id = f"COMP_BG_{sar_frame:06d}_{cidx:03d}"
            cx, cy = comp["centroid_x"], comp["centroid_y"]
            coords = fan_coords(cx, cy)
            role = component_role(comp)
            component_rows.append({
                "component_id": comp_id,
                "phase": "background_control_non_vehicle",
                "segment_id": "GM017_N005_BACKGROUND_CONTROL",
                "sar_frame": sar_frame,
                "optical_frame": "",
                "source_kind": "sar_gray_high_response_in_n005_temporal_window",
                "extraction_roi": meta["roi"],
                "extraction_threshold": fmt(meta["threshold"]),
                "candidate_kind": "background_explainable" if role in {"background_arc_candidate", "large_response_candidate"} else "currently_unexplained",
                "bbox": f"{fmt(comp['bbox_x1'])},{fmt(comp['bbox_y1'])},{fmt(comp['bbox_x2'])},{fmt(comp['bbox_y2'])}",
                "centroid_x": fmt(cx),
                "centroid_y": fmt(cy),
                "pixel_area": fmt(comp["pixel_area"]),
                "integrated_energy": fmt(comp["integrated_energy"]),
                "mean_energy": fmt(comp["mean_energy"]),
                "peak_energy": fmt(comp["peak_energy"]),
                "axis1_px": fmt(comp["axis1_px"]),
                "axis2_px": fmt(comp["axis2_px"]),
                "aspect_ratio": fmt(comp["aspect_ratio"]),
                "orientation_deg": fmt(comp["orientation_deg"]),
                "compactness": fmt(comp["compactness"]),
                "local_x_px": fmt(coords["local_x_px"]),
                "local_y_px": fmt(coords["local_y_px"]),
                "radial_px": fmt(coords["radial_px"]),
                "theta_deg": fmt(coords["theta_deg"]),
                "local_x_m": fmt(coords["local_x_m"]),
                "local_y_m": fmt(coords["local_y_m"]),
                "radial_m": fmt(coords["radial_m"]),
                "vehicle_explainable": "false",
                "background_explainable": "true" if role in {"background_arc_candidate", "large_response_candidate"} else "false",
                "both_explainable": "false",
                "currently_unexplained": "false" if role in {"background_arc_candidate", "large_response_candidate"} else "true",
                "component_role": role,
                "matched_control_point_id": "",
                "distance_to_control_center_px": "",
                "cap_triggered": meta["cap_triggered"],
                "provenance": "N005 temporal non-vehicle window from graph/P0 mapping; not used as holdout target GT",
            })
    return control_rows, component_rows


def command_build_calibration_pack() -> None:
    ensure_dirs()
    require_outputs(["input_provenance", "split_manifest", "frame_alignment"])
    control_rows, component_rows = build_control_and_components()
    control_fields = [
        "control_point_id",
        "sar_frame",
        "gt_instance_id",
        "bbox",
        "bbox_center",
        "bbox_scale",
        "manually_supported_vehicle_response_ids",
        "manually_rejected_background_ids",
        "optical_state",
        "provenance",
        "confidence",
    ]
    component_fields = [
        "component_id",
        "phase",
        "segment_id",
        "sar_frame",
        "optical_frame",
        "source_kind",
        "extraction_roi",
        "extraction_threshold",
        "candidate_kind",
        "bbox",
        "centroid_x",
        "centroid_y",
        "pixel_area",
        "integrated_energy",
        "mean_energy",
        "peak_energy",
        "axis1_px",
        "axis2_px",
        "aspect_ratio",
        "orientation_deg",
        "compactness",
        "local_x_px",
        "local_y_px",
        "radial_px",
        "theta_deg",
        "local_x_m",
        "local_y_m",
        "radial_m",
        "vehicle_explainable",
        "background_explainable",
        "both_explainable",
        "currently_unexplained",
        "component_role",
        "matched_control_point_id",
        "distance_to_control_center_px",
        "cap_triggered",
        "provenance",
    ]
    write_csv(OUTPUTS["control_points"], control_rows, control_fields)
    write_csv(OUTPUTS["components"], component_rows, component_fields)
    write_frozen_manifest("build-calibration-pack")
    update_gate_integrity(replay_status="")
    write_report()


def calibration_arrays() -> dict[str, list[float]]:
    rows = calibration_rows()
    frames: list[float] = []
    xs: list[float] = []
    ys: list[float] = []
    widths: list[float] = []
    heights: list[float] = []
    optical_xs: list[float] = []
    optical_widths: list[float] = []
    radials: list[float] = []
    thetas: list[float] = []
    for row in rows:
        sar_box = box_from_row(row, "sar")
        opt_box = box_from_row(row, "optical")
        cx, cy = box_center(sar_box)
        ocx, _ = box_center(opt_box)
        coords = fan_coords(cx, cy)
        frames.append(parse_float(row["sar_frame"]))
        xs.append(cx)
        ys.append(cy)
        widths.append(box_width(sar_box))
        heights.append(box_height(sar_box))
        optical_xs.append(ocx)
        optical_widths.append(box_width(opt_box))
        radials.append(coords["radial_px"])
        thetas.append(coords["theta_deg"])
    return {
        "frame": frames,
        "x": xs,
        "y": ys,
        "width": widths,
        "height": heights,
        "optical_x": optical_xs,
        "optical_width": optical_widths,
        "radial": radials,
        "theta": thetas,
    }


def command_calibrate() -> None:
    ensure_dirs()
    require_outputs(["control_points", "components", "split_manifest"])
    data = calibration_arrays()
    frame = data["frame"]
    x_intercept, x_slope = linear_fit(frame, data["x"])
    y_intercept, y_slope = linear_fit(frame, data["y"])
    x_pred = [predict_linear(x_intercept, x_slope, f) for f in frame]
    y_pred = [predict_linear(y_intercept, y_slope, f) for f in frame]
    motion_res = [math.hypot(px - x, py - y) for px, py, x, y in zip(x_pred, y_pred, data["x"], data["y"])]
    static_x = data["x"][0]
    static_y = data["y"][0]
    static_res = [math.hypot(static_x - x, static_y - y) for x, y in zip(data["x"], data["y"])]
    velocity_res = [math.hypot(data["x"][i] - data["x"][i - 1], data["y"][i] - data["y"][i - 1]) for i in range(1, len(frame))]

    motion_fields = ["factor_id", "model", "support_count", "parameter", "value", "unit", "calibration_metric", "null_baseline", "notes"]
    motion_rows = [
        {"factor_id": "F1", "model": "common_motion_linear_sar_center", "support_count": len(frame), "parameter": "x_intercept", "value": fmt(x_intercept), "unit": "px", "calibration_metric": f"mean_residual_px={fmt(np.mean(motion_res))}", "null_baseline": f"static_mean_residual_px={fmt(np.mean(static_res))}", "notes": "GT center is a control point, not scattering center truth."},
        {"factor_id": "F1", "model": "common_motion_linear_sar_center", "support_count": len(frame), "parameter": "x_slope_per_sar_frame", "value": fmt(x_slope), "unit": "px/frame", "calibration_metric": f"p75_residual_px={fmt(np.percentile(motion_res, 75))}", "null_baseline": "constant position; previous frame; constant velocity compared in report", "notes": ""},
        {"factor_id": "F1", "model": "common_motion_linear_sar_center", "support_count": len(frame), "parameter": "y_intercept", "value": fmt(y_intercept), "unit": "px", "calibration_metric": f"max_residual_px={fmt(max(motion_res))}", "null_baseline": "", "notes": ""},
        {"factor_id": "F1", "model": "common_motion_linear_sar_center", "support_count": len(frame), "parameter": "y_slope_per_sar_frame", "value": fmt(y_slope), "unit": "px/frame", "calibration_metric": f"mean_velocity_step_px={fmt(np.mean(velocity_res))}", "null_baseline": "", "notes": ""},
        {"factor_id": "F1", "model": "common_motion_tolerance", "support_count": len(frame), "parameter": "same_motion_tolerance_px", "value": fmt(np.percentile(motion_res, 90) + 20.0), "unit": "px", "calibration_metric": "p90 residual + 20px guard", "null_baseline": "", "notes": "Used only as candidate tolerance, not final selector."},
        {"factor_id": "F1", "model": "common_motion_tolerance", "support_count": len(frame), "parameter": "reappearance_spatial_tolerance_px", "value": fmt(np.percentile(motion_res, 95) + 30.0), "unit": "px", "calibration_metric": "p95 residual + 30px guard", "null_baseline": "", "notes": ""},
    ]
    write_csv(OUTPUTS["motion_fit"], motion_rows, motion_fields)

    components = read_csv(OUTPUTS["components"])
    bg_rows = [row for row in components if row.get("segment_id") == "GM017_N005_BACKGROUND_CONTROL"]
    grouped: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for row in bg_rows:
        key = (round(parse_float(row["centroid_x"]) / 25.0), round(parse_float(row["centroid_y"]) / 25.0))
        grouped[key].append(row)
    stable_groups = []
    for key, rows in grouped.items():
        if len(rows) < 3:
            continue
        xs = [parse_float(row["centroid_x"]) for row in rows]
        ys = [parse_float(row["centroid_y"]) for row in rows]
        stable_groups.append((key, rows, float(np.var(xs) + np.var(ys)), len({row["sar_frame"] for row in rows})))
    stable_groups.sort(key=lambda item: (item[2], -item[3]))
    bg_fields = ["factor_id", "background_group_id", "support_count", "parameter", "value", "unit", "calibration_metric", "null_baseline", "notes"]
    bg_fit_rows: list[dict[str, Any]] = []
    for idx, (key, rows, variance, span_count) in enumerate(stable_groups[:8], 1):
        bg_fit_rows.append({
            "factor_id": "F2",
            "background_group_id": f"BG{idx:03d}",
            "support_count": span_count,
            "parameter": "position_variance_px2",
            "value": fmt(variance),
            "unit": "px^2",
            "calibration_metric": f"frames={compact_range(parse_int(row['sar_frame']) for row in rows)}",
            "null_baseline": "shape_only_or_brightness_only",
            "notes": "Stable high-response group from N005 temporal non-vehicle window or other fixed lower-scene structure.",
        })
    bg_fit_rows.append({
        "factor_id": "F2",
        "background_group_id": "GLOBAL",
        "support_count": len(bg_rows),
        "parameter": "static_position_variance_threshold_px2",
        "value": fmt(np.percentile([item[2] for item in stable_groups], 35) if stable_groups else 400.0),
        "unit": "px^2",
        "calibration_metric": f"stable_group_count={len(stable_groups)}",
        "null_baseline": "shape_only;brightness_only",
        "notes": "Shape is auxiliary; time-position stability is primary.",
    })
    write_csv(OUTPUTS["background_fit"], bg_fit_rows, bg_fields)

    cal_components = [row for row in components if row.get("segment_id") == "GM017_DISC_CAL_0010"]
    by_frame: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in cal_components:
        by_frame[parse_int(row["sar_frame"])].append(row)
    visibility_states = []
    missing_runs: list[int] = []
    current_missing = 0
    for sar_frame in range(CALIBRATION_SAR_START, CALIBRATION_SAR_END + 1):
        vehicle_rows = [row for row in by_frame.get(sar_frame, []) if row.get("vehicle_explainable") == "true"]
        if not vehicle_rows:
            state = "missing"
            current_missing += 1
        else:
            best_peak = max(parse_float(row["peak_energy"]) for row in vehicle_rows)
            state = "visible" if best_peak >= 145 else "weak_visible"
            if current_missing:
                missing_runs.append(current_missing)
                current_missing = 0
        visibility_states.append((sar_frame, state, len(vehicle_rows)))
    if current_missing:
        missing_runs.append(current_missing)
    vis_counts = Counter(state for _, state, _ in visibility_states)
    max_missing = max(missing_runs) if missing_runs else 0
    vis_fields = ["factor_id", "state_or_parameter", "support_count", "value", "unit", "calibration_metric", "null_baseline", "notes"]
    vis_rows = [
        {"factor_id": "F3", "state_or_parameter": "visible_count", "support_count": len(visibility_states), "value": vis_counts["visible"], "unit": "frames", "calibration_metric": "GT-assisted component extraction inside expanded target box", "null_baseline": "response_missing_immediately_terminates", "notes": ""},
        {"factor_id": "F3", "state_or_parameter": "weak_visible_count", "support_count": len(visibility_states), "value": vis_counts["weak_visible"], "unit": "frames", "calibration_metric": "", "null_baseline": "allow_K_missing_without role checks", "notes": ""},
        {"factor_id": "F3", "state_or_parameter": "missing_count", "support_count": len(visibility_states), "value": vis_counts["missing"], "unit": "frames", "calibration_metric": f"max_missing_run={max_missing}", "null_baseline": "", "notes": "Missing means no minimum-confidence component near GT-assisted control region, not target absence truth."},
        {"factor_id": "F3", "state_or_parameter": "allowed_short_missing_gap_frames", "support_count": len(visibility_states), "value": max(2, max_missing + 1), "unit": "frames", "calibration_metric": "calibrated from observed missing runs plus one-frame guard", "null_baseline": "terminate_on_missing", "notes": "Candidate preservation only; not final identity."},
    ]
    write_csv(OUTPUTS["visibility_fit"], vis_rows, vis_fields)

    features_r = np.asarray(data["radial"], dtype=float).reshape(-1, 1)
    features_rt = np.column_stack([data["radial"], data["theta"]])
    w_const = float(np.mean(data["width"]))
    h_const = float(np.mean(data["height"]))
    w_r = multi_fit(features_r, data["width"])
    h_r = multi_fit(features_r, data["height"])
    w_rt = multi_fit(features_rt, data["width"])
    h_rt = multi_fit(features_rt, data["height"])
    w_const_res = [abs(w_const - value) for value in data["width"]]
    h_const_res = [abs(h_const - value) for value in data["height"]]
    w_rt_pred = [float(np.dot([1.0, r, t], w_rt)) for r, t in zip(data["radial"], data["theta"])]
    h_rt_pred = [float(np.dot([1.0, r, t], h_rt)) for r, t in zip(data["radial"], data["theta"])]
    scale_res = [math.hypot(pw - w, ph - h) for pw, ph, w, h in zip(w_rt_pred, h_rt_pred, data["width"], data["height"])]
    scale_fields = ["factor_id", "model", "support_count", "parameter", "value", "unit", "calibration_metric", "null_baseline", "notes"]
    scale_rows = [
        {"factor_id": "F4", "model": "constant_size", "support_count": len(frame), "parameter": "width_const_px", "value": fmt(w_const), "unit": "px", "calibration_metric": f"mean_abs_width_residual={fmt(np.mean(w_const_res))}", "null_baseline": "constant_size", "notes": ""},
        {"factor_id": "F4", "model": "constant_size", "support_count": len(frame), "parameter": "height_const_px", "value": fmt(h_const), "unit": "px", "calibration_metric": f"mean_abs_height_residual={fmt(np.mean(h_const_res))}", "null_baseline": "constant_size", "notes": ""},
        {"factor_id": "F4", "model": "range_only", "support_count": len(frame), "parameter": "width_intercept,width_radial", "value": ";".join(fmt(v) for v in w_r), "unit": "px,px/radial_px", "calibration_metric": "", "null_baseline": "constant_size", "notes": ""},
        {"factor_id": "F4", "model": "range_only", "support_count": len(frame), "parameter": "height_intercept,height_radial", "value": ";".join(fmt(v) for v in h_r), "unit": "px,px/radial_px", "calibration_metric": "", "null_baseline": "constant_size", "notes": ""},
        {"factor_id": "F4", "model": "range_plus_theta", "support_count": len(frame), "parameter": "width_intercept,width_radial,width_theta", "value": ";".join(fmt(v) for v in w_rt), "unit": "px,px/radial_px,px/deg", "calibration_metric": f"mean_size_residual_px={fmt(np.mean(scale_res))}", "null_baseline": f"constant_size_mean_residual_px={fmt(np.mean([math.hypot(a,b) for a,b in zip(w_const_res,h_const_res)]))}", "notes": "Does not impose real car dimensions."},
        {"factor_id": "F4", "model": "range_plus_theta", "support_count": len(frame), "parameter": "height_intercept,height_radial,height_theta", "value": ";".join(fmt(v) for v in h_rt), "unit": "px,px/radial_px,px/deg", "calibration_metric": "", "null_baseline": "", "notes": ""},
    ]
    write_csv(OUTPUTS["scale_fit"], scale_rows, scale_fields)

    sar_dx = np.diff(data["x"])
    sar_dr = np.diff(data["radial"])
    opt_dx = np.diff(data["optical_x"])
    opt_dw = np.diff(data["optical_width"])
    az_sign_agree = [np.sign(a) == np.sign(b) for a, b in zip(sar_dx, opt_dx) if a != 0 and b != 0]
    range_sign_agree = [np.sign(a) == np.sign(b) for a, b in zip(sar_dr, opt_dw) if a != 0 and b != 0]
    trend_fields = ["factor_id", "trend_test", "support_count", "parameter", "value", "unit", "calibration_metric", "null_baseline", "notes"]
    trend_rows = [
        {"factor_id": "F5", "trend_test": "optical_x_vs_sar_x_sign", "support_count": len(az_sign_agree), "parameter": "sign_agreement_rate", "value": fmt(sum(az_sign_agree) / max(len(az_sign_agree), 1)), "unit": "fraction", "calibration_metric": "same optical/SAR paired rows, offset frozen at P0 zero-offset frame-ratio hypothesis", "null_baseline": "SAR-only constant velocity sign", "notes": "No holdout GT is used to choose time offset."},
        {"factor_id": "F5", "trend_test": "optical_width_vs_sar_range_sign", "support_count": len(range_sign_agree), "parameter": "sign_agreement_rate", "value": fmt(sum(range_sign_agree) / max(len(range_sign_agree), 1)), "unit": "fraction", "calibration_metric": "", "null_baseline": "SAR-only radial trend", "notes": "Weak physical relation only; not direct center projection."},
        {"factor_id": "F5", "trend_test": "time_alignment", "support_count": len(frame), "parameter": "frozen_time_offset_sar_frames", "value": "0", "unit": "sar_frame", "calibration_metric": "P0 source uses software_sync_zero_offset_assumption", "null_baseline": "do_not_use_optical_trend", "notes": "Exact timestamp metadata absent; do not tune offset on holdout."},
    ]
    write_csv(OUTPUTS["trend_fit"], trend_rows, trend_fields)

    frozen_fields = ["parameter_group", "parameter_name", "parameter_value", "source_phase", "source_files", "sha_scope", "notes"]
    frozen_rows: list[dict[str, Any]] = [
        {"parameter_group": "time_alignment_parameters", "parameter_name": "optical_fps", "parameter_value": "24", "source_phase": "audit-inputs", "source_files": str(TEMPORAL_WINDOWS_CSV.relative_to(REPO_ROOT)), "sha_scope": "runtime_safe_temporal_source", "notes": "P0 frame-ratio hypothesis, not exact timestamp truth."},
        {"parameter_group": "time_alignment_parameters", "parameter_name": "sar_fps", "parameter_value": "50", "source_phase": "audit-inputs", "source_files": str(TEMPORAL_WINDOWS_CSV.relative_to(REPO_ROOT)), "sha_scope": "runtime_safe_temporal_source", "notes": ""},
        {"parameter_group": "time_alignment_parameters", "parameter_name": "frozen_time_offset_sar_frames", "parameter_value": "0", "source_phase": "calibrate", "source_files": str(OUTPUTS["trend_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": "Not selected on holdout."},
        {"parameter_group": "motion_residual_distribution", "parameter_name": "x_intercept", "parameter_value": fmt(x_intercept), "source_phase": "calibrate", "source_files": str(OUTPUTS["motion_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "motion_residual_distribution", "parameter_name": "x_slope", "parameter_value": fmt(x_slope), "source_phase": "calibrate", "source_files": str(OUTPUTS["motion_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "motion_residual_distribution", "parameter_name": "y_intercept", "parameter_value": fmt(y_intercept), "source_phase": "calibrate", "source_files": str(OUTPUTS["motion_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "motion_residual_distribution", "parameter_name": "y_slope", "parameter_value": fmt(y_slope), "source_phase": "calibrate", "source_files": str(OUTPUTS["motion_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "motion_residual_distribution", "parameter_name": "same_motion_tolerance_px", "parameter_value": fmt(np.percentile(motion_res, 90) + 20.0), "source_phase": "calibrate", "source_files": str(OUTPUTS["motion_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "motion_residual_distribution", "parameter_name": "reappearance_spatial_tolerance_px", "parameter_value": fmt(np.percentile(motion_res, 95) + 30.0), "source_phase": "calibrate", "source_files": str(OUTPUTS["motion_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "background_stability_parameters", "parameter_name": "static_position_variance_threshold_px2", "parameter_value": bg_fit_rows[-1]["value"], "source_phase": "calibrate", "source_files": str(OUTPUTS["background_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "visibility_parameters", "parameter_name": "allowed_short_missing_gap_frames", "parameter_value": max(2, max_missing + 1), "source_phase": "calibrate", "source_files": str(OUTPUTS["visibility_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "scale_range_parameters", "parameter_name": "constant_width_px", "parameter_value": fmt(w_const), "source_phase": "calibrate", "source_files": str(OUTPUTS["scale_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "scale_range_parameters", "parameter_name": "constant_height_px", "parameter_value": fmt(h_const), "source_phase": "calibrate", "source_files": str(OUTPUTS["scale_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "scale_range_parameters", "parameter_name": "width_range_theta_coefficients", "parameter_value": ";".join(fmt(v) for v in w_rt), "source_phase": "calibrate", "source_files": str(OUTPUTS["scale_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": "intercept;radial_px;theta_deg"},
        {"parameter_group": "scale_range_parameters", "parameter_name": "height_range_theta_coefficients", "parameter_value": ";".join(fmt(v) for v in h_rt), "source_phase": "calibrate", "source_files": str(OUTPUTS["scale_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": "intercept;radial_px;theta_deg"},
        {"parameter_group": "optical_sar_trend_parameters", "parameter_name": "optical_x_sar_x_sign_agreement_calibration", "parameter_value": trend_rows[0]["value"], "source_phase": "calibrate", "source_files": str(OUTPUTS["trend_fit"].relative_to(REPO_ROOT)), "sha_scope": "frozen_parameter", "notes": ""},
        {"parameter_group": "physical_factor_parameters", "parameter_name": "coordinate_grid", "parameter_value": f"{SAR_WIDTH}x{SAR_HEIGHT};fan_center={FAN_CENTER_X},{FAN_CENTER_Y};px_to_m={PX_TO_M}", "source_phase": "audit-inputs", "source_files": "configs/scene_config.yaml;existing WGV3.6A R2.1 coordinate convention", "sha_scope": "coordinate_audit", "notes": "Meter values are only factor-fitting aids; final task remains SAR image-domain."},
    ]
    write_csv(OUTPUTS["frozen_params"], frozen_rows, frozen_fields)
    write_counterexamples()
    update_gate_integrity(replay_status="")
    write_frozen_manifest("calibrate")
    write_report()


def read_params() -> dict[str, str]:
    rows = read_csv(OUTPUTS["frozen_params"])
    return {row["parameter_name"]: row["parameter_value"] for row in rows}


def coeffs(value: str) -> list[float]:
    return [parse_float(part) for part in value.split(";") if part != ""]


def generate_holdout_predictions(output_path: Path) -> None:
    params = read_params()
    xi = parse_float(params["x_intercept"])
    xs = parse_float(params["x_slope"])
    yi = parse_float(params["y_intercept"])
    ys = parse_float(params["y_slope"])
    tol = parse_float(params["same_motion_tolerance_px"])
    reapp_tol = parse_float(params["reappearance_spatial_tolerance_px"])
    width_coeff = coeffs(params["width_range_theta_coefficients"])
    height_coeff = coeffs(params["height_range_theta_coefficients"])
    const_w = parse_float(params["constant_width_px"])
    const_h = parse_float(params["constant_height_px"])
    allowed_gap = parse_int(params["allowed_short_missing_gap_frames"], 2)
    rows: list[dict[str, Any]] = []
    missing_run = 0
    for sar_frame in range(HOLDOUT_SAR_START, HOLDOUT_SAR_END + 1):
        pred_x = predict_linear(xi, xs, sar_frame)
        pred_y = predict_linear(yi, ys, sar_frame)
        coords = fan_coords(pred_x, pred_y)
        pred_w = float(np.dot([1.0, coords["radial_px"], coords["theta_deg"]], np.asarray(width_coeff))) if len(width_coeff) == 3 else const_w
        pred_h = float(np.dot([1.0, coords["radial_px"], coords["theta_deg"]], np.asarray(height_coeff))) if len(height_coeff) == 3 else const_h
        pred_w = max(30.0, min(260.0, pred_w))
        pred_h = max(25.0, min(160.0, pred_h))
        pred_box = box_from_center(pred_x, pred_y, pred_w, pred_h)
        roi = expand_box(pred_box, 105)
        comps, meta = extract_components(sar_frame, roi, min_pixels=10, threshold_quantile=93.0, mean_std_k=0.95, max_components=80)
        candidate_count = 0
        nearest_dist = ""
        nearest_id = ""
        for cidx, comp in enumerate(comps, 1):
            comp_id = f"HOLD_COMP_{sar_frame:06d}_{cidx:03d}"
            cx, cy = comp["centroid_x"], comp["centroid_y"]
            dist = math.hypot(cx - pred_x, cy - pred_y)
            if nearest_dist == "" or dist < parse_float(nearest_dist):
                nearest_dist = fmt(dist)
                nearest_id = comp_id
            role = component_role(comp, (pred_x, pred_y))
            if dist <= tol:
                prediction_kind = "same_motion_candidate"
                candidate_count += 1
            elif role == "background_arc_candidate":
                prediction_kind = "static_background_candidate"
            else:
                prediction_kind = "factor_unresolved"
            ccoords = fan_coords(cx, cy)
            rows.append({
                "prediction_id": comp_id,
                "sar_frame": sar_frame,
                "segment_id": "GM017_HOLDOUT_0010",
                "prediction_kind": prediction_kind,
                "runtime_inputs": "frozen_params;holdout_sar_current_frame;holdout_sar_history_past_only",
                "target_gt_read": "false",
                "future_target_read": "false",
                "predicted_center_x": fmt(pred_x),
                "predicted_center_y": fmt(pred_y),
                "predicted_width_px": fmt(pred_w),
                "predicted_height_px": fmt(pred_h),
                "component_centroid_x": fmt(cx),
                "component_centroid_y": fmt(cy),
                "component_distance_to_prediction_px": fmt(dist),
                "component_bbox": f"{fmt(comp['bbox_x1'])},{fmt(comp['bbox_y1'])},{fmt(comp['bbox_x2'])},{fmt(comp['bbox_y2'])}",
                "component_area_px": fmt(comp["pixel_area"]),
                "component_peak_energy": fmt(comp["peak_energy"]),
                "component_role": role,
                "local_x_px": fmt(ccoords["local_x_px"]),
                "local_y_px": fmt(ccoords["local_y_px"]),
                "radial_px": fmt(ccoords["radial_px"]),
                "theta_deg": fmt(ccoords["theta_deg"]),
                "same_motion_tolerance_px": fmt(tol),
                "reappearance_tolerance_px": fmt(reapp_tol),
                "visibility_state": "",
                "missing_run_length": "",
                "extraction_roi": meta["roi"],
                "extraction_threshold": fmt(meta["threshold"]),
                "cap_triggered": meta["cap_triggered"],
                "freeze_provenance": "validate-generate; no paired GT file opened",
            })
        if candidate_count == 0:
            missing_run += 1
            visibility_state = "missing"
        elif candidate_count == 1:
            missing_run = 0
            visibility_state = "weak_visible" if nearest_dist != "" and parse_float(nearest_dist) > tol * 0.55 else "visible"
        else:
            missing_run = 0
            visibility_state = "visible"
        rows.append({
            "prediction_id": f"HOLD_SUM_{sar_frame:06d}",
            "sar_frame": sar_frame,
            "segment_id": "GM017_HOLDOUT_0010",
            "prediction_kind": "visibility_intermittent_candidate" if visibility_state != "missing" or missing_run <= allowed_gap else "factor_unresolved",
            "runtime_inputs": "frozen_params;holdout_sar_current_frame;holdout_sar_history_past_only",
            "target_gt_read": "false",
            "future_target_read": "false",
            "predicted_center_x": fmt(pred_x),
            "predicted_center_y": fmt(pred_y),
            "predicted_width_px": fmt(pred_w),
            "predicted_height_px": fmt(pred_h),
            "component_centroid_x": "",
            "component_centroid_y": "",
            "component_distance_to_prediction_px": nearest_dist,
            "component_bbox": "",
            "component_area_px": "",
            "component_peak_energy": "",
            "component_role": "frame_visibility_summary",
            "local_x_px": fmt(coords["local_x_px"]),
            "local_y_px": fmt(coords["local_y_px"]),
            "radial_px": fmt(coords["radial_px"]),
            "theta_deg": fmt(coords["theta_deg"]),
            "same_motion_tolerance_px": fmt(tol),
            "reappearance_tolerance_px": fmt(reapp_tol),
            "visibility_state": visibility_state,
            "missing_run_length": missing_run,
            "extraction_roi": meta["roi"],
            "extraction_threshold": fmt(meta["threshold"]),
            "cap_triggered": meta["cap_triggered"],
            "freeze_provenance": f"nearest_component={nearest_id};candidate_count={candidate_count};allowed_gap={allowed_gap}",
        })
    fields = [
        "prediction_id",
        "sar_frame",
        "segment_id",
        "prediction_kind",
        "runtime_inputs",
        "target_gt_read",
        "future_target_read",
        "predicted_center_x",
        "predicted_center_y",
        "predicted_width_px",
        "predicted_height_px",
        "component_centroid_x",
        "component_centroid_y",
        "component_distance_to_prediction_px",
        "component_bbox",
        "component_area_px",
        "component_peak_energy",
        "component_role",
        "local_x_px",
        "local_y_px",
        "radial_px",
        "theta_deg",
        "same_motion_tolerance_px",
        "reappearance_tolerance_px",
        "visibility_state",
        "missing_run_length",
        "extraction_roi",
        "extraction_threshold",
        "cap_triggered",
        "freeze_provenance",
    ]
    write_csv(output_path, rows, fields)


def command_validate_generate() -> None:
    ensure_dirs()
    require_outputs(["frozen_params", "split_manifest"])
    generate_holdout_predictions(OUTPUTS["holdout_predictions"])
    update_gate_integrity(replay_status="")
    write_frozen_manifest("validate-generate")
    write_report()


def command_evaluate() -> None:
    ensure_dirs()
    require_outputs(["holdout_predictions", "frozen_params"])
    predictions = read_csv(OUTPUTS["holdout_predictions"])
    summaries = {parse_int(row["sar_frame"]): row for row in predictions if row["prediction_id"].startswith("HOLD_SUM_")}
    gt_by_frame = {parse_int(row["sar_frame"]): row for row in holdout_gt_rows()}
    params = read_params()
    static_row = calibration_rows()[0]
    static_center = box_center(box_from_row(static_row, "sar"))
    const_w = parse_float(params["constant_width_px"])
    const_h = parse_float(params["constant_height_px"])
    motion_errors = []
    static_errors = []
    size_errors = []
    size_const_errors = []
    rows: list[dict[str, Any]] = []
    prev_gt = None
    prev_opt = None
    optical_sar_signs = []
    for sar_frame in range(HOLDOUT_SAR_START, HOLDOUT_SAR_END + 1):
        gt = gt_by_frame.get(sar_frame)
        pred = summaries.get(sar_frame)
        if not gt or not pred:
            continue
        gt_box = box_from_row(gt, "sar")
        opt_box = box_from_row(gt, "optical")
        gt_center = box_center(gt_box)
        pred_center = (parse_float(pred["predicted_center_x"]), parse_float(pred["predicted_center_y"]))
        motion_error = math.hypot(pred_center[0] - gt_center[0], pred_center[1] - gt_center[1])
        static_error = math.hypot(static_center[0] - gt_center[0], static_center[1] - gt_center[1])
        motion_errors.append(motion_error)
        static_errors.append(static_error)
        pred_w = parse_float(pred["predicted_width_px"])
        pred_h = parse_float(pred["predicted_height_px"])
        gt_w = box_width(gt_box)
        gt_h = box_height(gt_box)
        size_error = math.hypot(pred_w - gt_w, pred_h - gt_h)
        const_error = math.hypot(const_w - gt_w, const_h - gt_h)
        size_errors.append(size_error)
        size_const_errors.append(const_error)
        if prev_gt is not None and prev_opt is not None:
            gt_dx = gt_center[0] - prev_gt[0]
            opt_dx = box_center(opt_box)[0] - prev_opt[0]
            if gt_dx != 0 and opt_dx != 0:
                optical_sar_signs.append(np.sign(gt_dx) == np.sign(opt_dx))
        prev_gt = gt_center
        prev_opt = box_center(opt_box)
        nearest = parse_float(pred.get("component_distance_to_prediction_px"), 9999.0)
        rows.append({
            "eval_id": f"EVAL_FRAME_{sar_frame:06d}",
            "factor_id": "FRAME",
            "sar_frame": sar_frame,
            "metric": "frame_prediction_vs_holdout_gt",
            "prediction_value": f"center={fmt(pred_center[0])},{fmt(pred_center[1])};size={fmt(pred_w)}x{fmt(pred_h)};visibility={pred.get('visibility_state')}",
            "gt_value": f"center={fmt(gt_center[0])},{fmt(gt_center[1])};size={fmt(gt_w)}x{fmt(gt_h)}",
            "null_baseline": f"static_center={fmt(static_center[0])},{fmt(static_center[1])};constant_size={fmt(const_w)}x{fmt(const_h)}",
            "result": f"motion_error_px={fmt(motion_error)};size_error_px={fmt(size_error)};nearest_component_distance_px={fmt(nearest)}",
            "phase_boundary": "holdout_gt_read_after_holdout_prediction_sha",
            "notes": "Evaluation only; does not modify frozen parameters or predictions.",
        })
    motion_mean = float(np.mean(motion_errors)) if motion_errors else 0.0
    static_mean = float(np.mean(static_errors)) if static_errors else 0.0
    motion_improvement = 1.0 - motion_mean / max(static_mean, 1e-6)
    size_mean = float(np.mean(size_errors)) if size_errors else 0.0
    size_const_mean = float(np.mean(size_const_errors)) if size_const_errors else 0.0
    size_improvement = 1.0 - size_mean / max(size_const_mean, 1e-6)
    summary_rows = [
        {"eval_id": "EVAL_F1", "factor_id": "F1", "sar_frame": "371-394", "metric": "motion_model_center_error", "prediction_value": f"mean_error_px={fmt(motion_mean)}", "gt_value": f"holdout_gt_centers={len(motion_errors)}", "null_baseline": f"static_position_mean_error_px={fmt(static_mean)}", "result": f"relative_improvement={fmt(motion_improvement)}", "phase_boundary": "GT read only after prediction freeze", "notes": ""},
        {"eval_id": "EVAL_F2", "factor_id": "F2", "sar_frame": "371-394", "metric": "background_explainable_not_promoted_to_vehicle", "prediction_value": f"static_background_candidates={sum(1 for row in predictions if row['prediction_kind']=='static_background_candidate')}", "gt_value": "checked after freeze against holdout target boxes", "null_baseline": "shape_or_brightness_only", "result": "no final membership assignment; static candidates remain separate from same_motion_candidate", "phase_boundary": "GT read only after prediction freeze", "notes": "N005 control remains non-vehicle counterexample source."},
        {"eval_id": "EVAL_F3", "factor_id": "F3", "sar_frame": "371-394", "metric": "visibility_gap_protection", "prediction_value": f"missing_frames={sum(1 for row in summaries.values() if row.get('visibility_state')=='missing')}", "gt_value": f"holdout_gt_frames={len(gt_by_frame)}", "null_baseline": "terminate_on_missing", "result": "gap model preserved frame summaries but cannot alone confirm membership", "phase_boundary": "GT read only after prediction freeze", "notes": "Downgraded unless paired with F1/F2/F4."},
        {"eval_id": "EVAL_F4", "factor_id": "F4", "sar_frame": "371-394", "metric": "range_theta_size_error", "prediction_value": f"mean_error_px={fmt(size_mean)}", "gt_value": f"holdout_gt_sizes={len(size_errors)}", "null_baseline": f"constant_size_mean_error_px={fmt(size_const_mean)}", "result": f"relative_improvement={fmt(size_improvement)}", "phase_boundary": "GT read only after prediction freeze", "notes": ""},
        {"eval_id": "EVAL_F5", "factor_id": "F5", "sar_frame": "371-394", "metric": "optical_sar_x_sign_agreement", "prediction_value": f"agreement={fmt(sum(optical_sar_signs) / max(len(optical_sar_signs), 1))}", "gt_value": f"sign_pairs={len(optical_sar_signs)}", "null_baseline": "SAR-only trend and zero-offset frame-ratio hypothesis", "result": "trend is only weakly admissible because exact timestamp metadata is absent", "phase_boundary": "GT read only after prediction freeze", "notes": "No holdout GT was used to choose time offset."},
    ]
    rows.extend(summary_rows)
    write_csv(OUTPUTS["holdout_eval"], rows, ["eval_id", "factor_id", "sar_frame", "metric", "prediction_value", "gt_value", "null_baseline", "result", "phase_boundary", "notes"])

    verdicts = build_verdict_rows(motion_improvement, size_improvement, predictions, optical_sar_signs)
    write_csv(OUTPUTS["verdicts"], verdicts, [
        "factor_id",
        "factor_name",
        "physical_hypothesis_cn",
        "runtime_inputs",
        "calibration_inputs",
        "fitted_parameters",
        "calibration_support_count",
        "null_baseline",
        "holdout_metric",
        "holdout_result",
        "failure_modes",
        "scene_dependence",
        "keep_modify_reject",
        "next_use",
    ])
    write_counterexamples()
    update_gate_integrity(replay_status="")
    write_frozen_manifest("evaluate")
    write_report()


def build_verdict_rows(motion_improvement: float, size_improvement: float, predictions: Sequence[Mapping[str, str]], optical_sar_signs: Sequence[bool]) -> list[dict[str, Any]]:
    same_motion_count = sum(1 for row in predictions if row.get("prediction_kind") == "same_motion_candidate")
    background_count = sum(1 for row in predictions if row.get("prediction_kind") == "static_background_candidate")
    missing_count = sum(1 for row in predictions if row.get("visibility_state") == "missing")
    trend_rate = sum(optical_sar_signs) / max(len(optical_sar_signs), 1)
    f1_status = "SUPPORTED" if motion_improvement >= 0.20 and same_motion_count > 0 else "PARTIAL"
    f2_status = "SUPPORTED" if background_count > 0 else "PARTIAL"
    f3_status = "PARTIAL" if missing_count > 0 else "SUPPORTED"
    f4_status = "SUPPORTED" if size_improvement >= 0.05 else "PARTIAL"
    f5_status = "PARTIAL" if trend_rate >= 0.55 else "REJECTED"
    return [
        {
            "factor_id": "F1_COMMON_MOTION",
            "factor_name": "车辆总体运动与局部响应共运动",
            "physical_hypothesis_cn": "局部响应可由同一整体运动状态解释时，其中心应围绕冻结线性运动轨迹小残差漂移。",
            "runtime_inputs": "frozen motion parameters; holdout SAR current/history frames",
            "calibration_inputs": "GM_RM017 bt_0010 calibration GT control centers and SAR components",
            "fitted_parameters": "x/y intercept and slope; same_motion_tolerance; reappearance_tolerance",
            "calibration_support_count": len(calibration_rows()),
            "null_baseline": "static position; previous position; constant size-independent motion",
            "holdout_metric": "motion center error versus static baseline",
            "holdout_result": f"{f1_status}; relative_improvement={fmt(motion_improvement)}; same_motion_candidates={same_motion_count}",
            "failure_modes": "GT center is not scattering center; neighboring target can share short-term direction; no final membership decision",
            "scene_dependence": "single GM_RM017 thread; exact timestamp unresolved",
            "keep_modify_reject": f1_status,
            "next_use": "Keep as candidate generation prior only, not final selector.",
        },
        {
            "factor_id": "F2_BACKGROUND_STABILITY",
            "factor_name": "固定背景稳定性",
            "physical_hypothesis_cn": "长期固定于雷达局部坐标的高响应更可能是背景结构，应与移动车辆响应分离。",
            "runtime_inputs": "holdout SAR current/history frames; frozen static variance threshold",
            "calibration_inputs": "N005 temporal non-vehicle window and high-response SAR components",
            "fitted_parameters": "static_position_variance_threshold_px2; stable group inventory",
            "calibration_support_count": sum(1 for row in read_csv(OUTPUTS["components"]) if row.get("segment_id") == "GM017_N005_BACKGROUND_CONTROL"),
            "null_baseline": "shape-only or brightness-only background rejection",
            "holdout_metric": "static_background_candidate count held separate from same_motion candidates",
            "holdout_result": f"{f2_status}; static_background_candidates={background_count}",
            "failure_modes": "fixed background can flicker; N005 is temporal negative control but exact SAR spatial identity remains frame-ratio sourced",
            "scene_dependence": "N005/other fixed lower-scene structures in GM_RM017",
            "keep_modify_reject": f2_status,
            "next_use": "Keep as negative-control feature; require independent spatial review before runtime hard gate.",
        },
        {
            "factor_id": "F3_PART_VISIBILITY",
            "factor_name": "散射部件可见性与间歇出现",
            "physical_hypothesis_cn": "车辆存在时局部响应可短时 weak/missing/reappeared，缺失不等于车辆消失。",
            "runtime_inputs": "frozen allowed gap; holdout SAR current/history components",
            "calibration_inputs": "calibration component observations inside expanded GT control regions",
            "fitted_parameters": "allowed_short_missing_gap_frames",
            "calibration_support_count": HOLDOUT_SAR_START - CALIBRATION_SAR_START,
            "null_baseline": "response disappears => track terminates",
            "holdout_metric": "missing frame count and gap-preserved summaries",
            "holdout_result": f"{f3_status}; missing_summary_frames={missing_count}",
            "failure_modes": "gap protection can recover background or other target if used alone",
            "scene_dependence": "depends on thresholded components and local SAR contrast",
            "keep_modify_reject": f3_status,
            "next_use": "Modify; only combine with motion/background/scale evidence.",
        },
        {
            "factor_id": "F4_SCALE_RANGE_RELATION",
            "factor_name": "响应尺度与距离/方位关系",
            "physical_hypothesis_cn": "SAR 图像域响应尺度随距离与方位存在弱关系，可优于常量尺寸基线。",
            "runtime_inputs": "frozen range+theta coefficients; predicted SAR center",
            "calibration_inputs": "calibration GT bbox size and radar-local fan coordinates",
            "fitted_parameters": "constant size; range-only; range+theta width/height coefficients",
            "calibration_support_count": len(calibration_rows()),
            "null_baseline": "constant width/height",
            "holdout_metric": "size error versus constant baseline",
            "holdout_result": f"{f4_status}; relative_improvement={fmt(size_improvement)}",
            "failure_modes": "GT box size is not true scattering support size; metric grid is auxiliary",
            "scene_dependence": "single GM_RM017 vehicle thread and SAR grid",
            "keep_modify_reject": f4_status,
            "next_use": "Keep as search-size prior, not hard vehicle dimensions.",
        },
        {
            "factor_id": "F5_OPTICAL_SAR_TREND",
            "factor_name": "光学趋势与 SAR 运动关系",
            "physical_hypothesis_cn": "光学横向/尺度趋势可弱支持 SAR 方位/距离趋势，但不能直接投影 SAR 中心。",
            "runtime_inputs": "optical current/history trend; frozen zero-offset frame-ratio hypothesis",
            "calibration_inputs": "calibration paired optical/SAR trend signs",
            "fitted_parameters": "sign agreement rates; frozen zero time offset",
            "calibration_support_count": len(calibration_rows()) - 1,
            "null_baseline": "SAR-only trend; no optical trend",
            "holdout_metric": "holdout optical/SAR sign agreement after prediction freeze",
            "holdout_result": f"{f5_status}; sign_agreement={fmt(trend_rate)}",
            "failure_modes": "exact timestamp missing; neighboring vehicles can move same direction; optical trend may align accidentally",
            "scene_dependence": "GM_RM017 optical edge-contact/partial visibility",
            "keep_modify_reject": f5_status,
            "next_use": "Modify; use only as weak compatibility cue until timestamp/offset is independently calibrated.",
        },
    ]


def write_counterexamples() -> None:
    fields = ["counterexample_id", "factor_id", "source_window", "source_evidence", "why_it_looks_plausible", "why_not_sufficient", "exclusion_condition", "status"]
    rows = [
        {
            "counterexample_id": "CE_F1_NEIGHBOR_COMMON_DIRECTION",
            "factor_id": "F1_COMMON_MOTION",
            "source_window": "GM_RM017 forbidden edge N001->N003",
            "source_evidence": "Dense frames show leading and trailing dark sedans are separate despite similar appearance/direction.",
            "why_it_looks_plausible": "Two objects can share short-term motion direction.",
            "why_not_sufficient": "Forbidden edge says similar dark-car appearance would create false merge.",
            "exclusion_condition": "Require same-motion plus separable target-family/negative edge context.",
            "status": "retained_counterexample",
        },
        {
            "counterexample_id": "CE_F2_N005_NONVEHICLE",
            "factor_id": "F2_BACKGROUND_STABILITY",
            "source_window": "GM_RM017_N005 optical 121-129 / SAR temporal 249-274",
            "source_evidence": "Graph node/edge records foreground barrier or temporary structure, not vehicle.",
            "why_it_looks_plausible": "A fixed bright structure can be high-energy and spatially stable.",
            "why_not_sufficient": "Temporal stability is background evidence, not vehicle evidence.",
            "exclusion_condition": "Static high response must remain background_explainable unless independent vehicle motion appears.",
            "status": "negative_control",
        },
        {
            "counterexample_id": "CE_F3_BACKGROUND_FLICKER",
            "factor_id": "F3_PART_VISIBILITY",
            "source_window": "N005/control lower-scene high responses",
            "source_evidence": "Background components can appear/disappear under thresholded SAR contrast.",
            "why_it_looks_plausible": "Short missing/reappeared pattern resembles intermittent vehicle part visibility.",
            "why_not_sufficient": "Without common motion and scale relation, intermittent visibility can restore background.",
            "exclusion_condition": "Gap preservation cannot create membership without F1/F2/F4 support.",
            "status": "downgrade_guard",
        },
        {
            "counterexample_id": "CE_F4_STATIC_STABLE_SIZE",
            "factor_id": "F4_SCALE_RANGE_RELATION",
            "source_window": "background_control stable groups",
            "source_evidence": "Fixed background components can have stable width/height.",
            "why_it_looks_plausible": "Stable size can look vehicle-like under a size prior.",
            "why_not_sufficient": "Size alone ignores motion and background stability.",
            "exclusion_condition": "Scale prior remains a search-size bound, not semantic vehicle proof.",
            "status": "retained_counterexample",
        },
        {
            "counterexample_id": "CE_F5_ACCIDENTAL_TREND",
            "factor_id": "F5_OPTICAL_SAR_TREND",
            "source_window": "GM_RM017 multi-vehicle right-moving interval",
            "source_evidence": "Neighboring vehicles can share optical direction and SAR x trend.",
            "why_it_looks_plausible": "Sign agreement is easy to satisfy in a same-direction traffic flow.",
            "why_not_sufficient": "Exact timestamp is unresolved and sign-only trend is weak.",
            "exclusion_condition": "Do not use optical trend as selector or time-offset tuning signal.",
            "status": "downgrade_guard",
        },
    ]
    write_csv(OUTPUTS["counterexamples"], rows, fields)


def update_gate_integrity(replay_status: str) -> None:
    branch = git_output(["branch", "--show-current"])
    head = git_output(["rev-parse", "HEAD"])
    worktree_list = git_output(["worktree", "list"])
    params_exists = OUTPUTS["frozen_params"].exists()
    preds_exists = OUTPUTS["holdout_predictions"].exists()
    split_exists = OUTPUTS["split_manifest"].exists()
    eval_exists = OUTPUTS["holdout_eval"].exists()
    verdict_rows = read_csv(OUTPUTS["verdicts"]) if OUTPUTS["verdicts"].exists() else []
    supported = sum(1 for row in verdict_rows if row.get("keep_modify_reject") == "SUPPORTED")
    downgraded = sum(1 for row in verdict_rows if row.get("keep_modify_reject") in {"PARTIAL", "REJECTED"})
    rows = [
        gate_row("PARALLEL_WORKTREE_ISOLATED", branch == BRANCH and str(REPO_ROOT).endswith("optical-sar-visual-diagnosis-gm017-physics"), f"branch={branch};head={head};worktrees={worktree_list.replace(chr(10), ' | ')}", "independent GM017 branch/worktree; live GM_RM019 worktree not checked out here"),
        gate_row("CALIBRATION_GT_USAGE_EXPLICIT", OUTPUTS["control_points"].exists(), "control point table exists" if OUTPUTS["control_points"].exists() else "pending", "GT allowed only in calibration/evaluation phases"),
        gate_row("HOLDOUT_TARGET_GT_ISOLATED", preds_exists and all(row.get("target_gt_read") == "false" for row in read_csv(OUTPUTS["holdout_predictions"]) if row), "validate-generate prediction rows declare target_gt_read=false" if preds_exists else "pending", "validate-generate implementation does not open paired GT"),
        gate_row("CONTIGUOUS_BLOCK_SPLIT_VALID", split_exists, f"cal={CALIBRATION_SAR_START}-{CALIBRATION_SAR_END};guard={GUARD_SAR_START}-{GUARD_SAR_END};holdout={HOLDOUT_SAR_START}-{HOLDOUT_SAR_END}", "continuous SAR blocks, no random split"),
        gate_row("GUARD_GAP_PRESENT", True, f"{GUARD_SAR_START}-{GUARD_SAR_END}", "10 SAR frames"),
        gate_row("FACTOR_PARAMETERS_FROZEN", params_exists, sha256_file(OUTPUTS["frozen_params"]) if params_exists else "pending", "frozen parameter CSV"),
        gate_row("HOLDOUT_PREDICTIONS_FROZEN", preds_exists, sha256_file(OUTPUTS["holdout_predictions"]) if preds_exists else "pending", "frozen holdout prediction CSV"),
        gate_row("FROZEN_REPLAY_IDENTICAL", replay_status == "PASS", replay_status or "pending", "verify-replay compares regenerated predictions to frozen prediction SHA"),
        gate_row("F1_COMMON_MOTION", any(row.get("factor_id") == "F1_COMMON_MOTION" and row.get("keep_modify_reject") == "SUPPORTED" for row in verdict_rows), verdict_value(verdict_rows, "F1_COMMON_MOTION"), "valid values are SUPPORTED/PARTIAL/REJECTED/INSUFFICIENT_EVIDENCE"),
        gate_row("F2_BACKGROUND_STABILITY", any(row.get("factor_id") == "F2_BACKGROUND_STABILITY" and row.get("keep_modify_reject") == "SUPPORTED" for row in verdict_rows), verdict_value(verdict_rows, "F2_BACKGROUND_STABILITY"), ""),
        gate_row("F3_PART_VISIBILITY", any(row.get("factor_id") == "F3_PART_VISIBILITY" and row.get("keep_modify_reject") == "SUPPORTED" for row in verdict_rows), verdict_value(verdict_rows, "F3_PART_VISIBILITY"), "PARTIAL is acceptable as downgrade, not pass"),
        gate_row("F4_SCALE_RANGE_RELATION", any(row.get("factor_id") == "F4_SCALE_RANGE_RELATION" and row.get("keep_modify_reject") == "SUPPORTED" for row in verdict_rows), verdict_value(verdict_rows, "F4_SCALE_RANGE_RELATION"), ""),
        gate_row("F5_OPTICAL_SAR_TREND", any(row.get("factor_id") == "F5_OPTICAL_SAR_TREND" and row.get("keep_modify_reject") == "SUPPORTED" for row in verdict_rows), verdict_value(verdict_rows, "F5_OPTICAL_SAR_TREND"), "trend cue downgraded unless independently timestamped"),
        {
            "gate_id": "GM_RM017_PHYSICAL_FACTOR_LIBRARY_READY",
            "status": "PARTIAL" if eval_exists and supported >= 2 and downgraded >= 1 else "NOT_READY",
            "evidence": f"supported={supported};downgraded_or_rejected={downgraded};evaluation_exists={eval_exists}",
            "notes": "Not an automatic pass; library is a bounded factor study, not a final selector.",
        },
        {
            "gate_id": "GM_RM017_DYNAMIC_MEMBERSHIP_STAGE_READY",
            "status": "NOT_READY",
            "evidence": "final response membership/box selection explicitly out of scope",
            "notes": "Next stage may consume factor candidates only after separate authorization.",
        },
    ]
    write_csv(OUTPUTS["gate_integrity"], rows, ["gate_id", "status", "evidence", "notes"])


def gate_row(gate_id: str, ok: bool, evidence: str, notes: str) -> dict[str, str]:
    return {"gate_id": gate_id, "status": "PASS" if ok else "PENDING" if evidence == "pending" else "PARTIAL", "evidence": evidence, "notes": notes}


def verdict_value(rows: Sequence[Mapping[str, str]], factor_id: str) -> str:
    for row in rows:
        if row.get("factor_id") == factor_id:
            return row.get("keep_modify_reject", "")
    return "pending"


def write_frozen_manifest(phase: str) -> None:
    rows = []
    for key, path in OUTPUTS.items():
        if key == "frozen_manifest":
            continue
        if not path.exists():
            continue
        rows.append({
            "artifact_key": key,
            "path": str(path.relative_to(REPO_ROOT)),
            "sha256": sha256_file(path),
            "freeze_phase": phase if key in FREEZE_OUTPUT_KEYS or key in {"holdout_eval", "verdicts"} else "supporting_audit",
            "gt_allowed_at_creation": "false" if key == "holdout_predictions" else ("true_after_prediction_freeze" if key in {"holdout_eval", "verdicts"} else "phase_specific"),
            "notes": "Do not modify frozen params or holdout predictions after evaluation." if key in {"frozen_params", "holdout_predictions"} else "",
        })
    write_csv(OUTPUTS["frozen_manifest"], rows, ["artifact_key", "path", "sha256", "freeze_phase", "gt_allowed_at_creation", "notes"])


def command_verify_replay() -> None:
    ensure_dirs()
    require_outputs(["holdout_predictions", "frozen_params"])
    if VERIFY_TMP_DIR.exists():
        shutil.rmtree(VERIFY_TMP_DIR)
    VERIFY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    replay_path = VERIFY_TMP_DIR / OUTPUTS["holdout_predictions"].name
    generate_holdout_predictions(replay_path)
    frozen_sha = sha256_file(OUTPUTS["holdout_predictions"])
    replay_sha = sha256_file(replay_path)
    replay_status = "PASS" if frozen_sha == replay_sha else f"FAIL frozen={frozen_sha} replay={replay_sha}"
    update_gate_integrity(replay_status=replay_status)
    write_frozen_manifest("verify-replay")
    write_report(extra_lines=[f"- verify-replay: `{replay_status}`", f"- frozen prediction sha: `{frozen_sha}`", f"- replay prediction sha: `{replay_sha}`"])


def require_outputs(keys: Sequence[str]) -> None:
    missing = [str(OUTPUTS[key].relative_to(REPO_ROOT)) for key in keys if not OUTPUTS[key].exists()]
    if missing:
        raise SystemExit("Missing prerequisite output(s): " + "; ".join(missing))


def write_report(extra_lines: Sequence[str] | None = None) -> None:
    provenance = read_csv(OUTPUTS["input_provenance"]) if OUTPUTS["input_provenance"].exists() else []
    splits = read_csv(OUTPUTS["split_manifest"]) if OUTPUTS["split_manifest"].exists() else []
    verdicts = read_csv(OUTPUTS["verdicts"]) if OUTPUTS["verdicts"].exists() else []
    gates = read_csv(OUTPUTS["gate_integrity"]) if OUTPUTS["gate_integrity"].exists() else []
    manifest = read_csv(OUTPUTS["frozen_manifest"]) if OUTPUTS["frozen_manifest"].exists() else []
    control_count = len(read_csv(OUTPUTS["control_points"])) if OUTPUTS["control_points"].exists() else 0
    component_count = len(read_csv(OUTPUTS["components"])) if OUTPUTS["components"].exists() else 0
    holdout_pred_count = len(read_csv(OUTPUTS["holdout_predictions"])) if OUTPUTS["holdout_predictions"].exists() else 0
    lines = [
        "# WGV3.6B-P0 GM_RM017 Physical Response Factor Discovery",
        "",
        "## Scope",
        "",
        "This report records a phase-separated GM_RM017 physical-factor study. It does not produce final annotations, revised GT, selector/ranking logic, or a unique final vehicle box.",
        "",
        "## Worktree And Start",
        "",
        f"- start_commit: `{START_COMMIT}`",
        f"- current_head: `{git_output(['rev-parse', 'HEAD'])}`",
        f"- branch: `{git_output(['branch', '--show-current'])}`",
        f"- worktree: `{REPO_ROOT}`",
        "",
        "## Input Provenance",
        "",
    ]
    for row in provenance:
        lines.append(f"- `{row['item_id']}` {row['source_kind']}: {row['key_finding']}")
    lines.extend(["", "## Split", ""])
    for row in splits:
        lines.append(
            f"- `{row['segment_id']}` {row['segment_role']}: SAR `{row['sar_frame_start']}-{row['sar_frame_end']}`, "
            f"optical `{row['optical_frame_start']}-{row['optical_frame_end']}`, gt_allowed=`{row['gt_allowed']}`"
        )
    lines.extend([
        "",
        "## Phase Counts",
        "",
        f"- control_points: `{control_count}`",
        f"- response_component_observations: `{component_count}`",
        f"- holdout_prediction_rows: `{holdout_pred_count}`",
        "",
        "## Factor Verdicts",
        "",
    ])
    if verdicts:
        for row in verdicts:
            lines.append(f"- `{row['factor_id']}` = `{row['keep_modify_reject']}`; {row['holdout_result']}")
    else:
        lines.append("- pending")
    lines.extend(["", "## Gate Integrity", ""])
    for row in gates:
        lines.append(f"- `{row['gate_id']}`: `{row['status']}` ({row['evidence']})")
    lines.extend(["", "## Frozen SHA Manifest", ""])
    for row in manifest:
        lines.append(f"- `{row['artifact_key']}` `{row['sha256']}` `{row['path']}`")
    if extra_lines:
        lines.extend(["", "## Replay", "", *extra_lines])
    lines.extend([
        "",
        "## Boundary Notes",
        "",
        "- Calibration uses GT control points explicitly. Holdout generation reads only frozen parameters and SAR gray frames.",
        "- Holdout GT is read only by `evaluate` after `holdout_factor_predictions` exists and is SHA-recorded.",
        "- N005 is used as an explicit non-vehicle/background counterexample, not as a runtime vehicle label.",
        "- Metric coordinates use the audited 2308x1334 SAR grid, fan center, and existing 0.03 px-to-meter convention only for factor fitting; outputs remain SAR image-domain candidates.",
    ])
    write_text(OUTPUTS["report"], "\n".join(lines) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit-inputs")
    sub.add_parser("build-calibration-pack")
    sub.add_parser("calibrate")
    sub.add_parser("validate-generate")
    sub.add_parser("evaluate")
    sub.add_parser("verify-replay")
    args = parser.parse_args(argv)
    if args.command == "audit-inputs":
        command_audit_inputs()
    elif args.command == "build-calibration-pack":
        command_build_calibration_pack()
    elif args.command == "calibrate":
        command_calibrate()
    elif args.command == "validate-generate":
        command_validate_generate()
    elif args.command == "evaluate":
        command_evaluate()
    elif args.command == "verify-replay":
        command_verify_replay()
    else:
        raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
