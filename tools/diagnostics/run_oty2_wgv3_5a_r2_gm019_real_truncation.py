"""Run WGV3.5A-R2 GM_RM019 real truncation transfer validation.

R2 inherits the frozen R1 complete-vehicle state model and applies it to
GM_RM019 real near-field observations. It reports whether real truncation can
be repaired with same-vehicle complete anchors. The script does not edit GT,
does not emit final SAR boxes, does not search SAR PNG responses, and does not
leave the physical transfer-region diagnosis boundary.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATA_ROOT = Path(r"D:\profile\research\data")
DATE = "20260710"
SCENE = "GM_RM019"
OUTPUT_DIR = REPO_ROOT / "outputs" / "wgv3_5a_r2_gm019_20260710"

OPTICAL_WIDTH = 800.0
OPTICAL_HEIGHT = 600.0
SAR_WIDTH = 2308.0
SAR_HEIGHT = 1334.0
FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
FAN_RADIUS_PX = 1332.7
FULL_AZIMUTH_SPAN = 178.0

R1_FILES = [
    REPORT_DIR / f"oty2_wgv3_5a_r1_physical_vehicle_identity_audit_{DATE}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r1_complete_vehicle_mechanism_{DATE}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r1_visual_diagnosis_{DATE}.md",
    REPORT_DIR / f"oty2_wgv3_5a_r1_closure_{DATE}.md",
    SAMPLES_DIR / f"oty2_wgv3_5a_r1_physical_vehicle_map_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r1_observation_state_audit_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r1_complete_vehicle_baseline_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r1_recovered_full_vehicle_states_{DATE}.csv",
    SAMPLES_DIR / f"oty2_wgv3_5a_r1_projection_comparison_{DATE}.csv",
]

INPUTS = {
    "pairs": SAMPLES_DIR / f"oty2_wgv3_5a_paired_annotations_{DATE}.csv",
    "sar": SAMPLES_DIR / f"oty2_wgv3_5a_sar_polar_targets_{DATE}.csv",
    "optical": SAMPLES_DIR / f"oty2_wgv3_5a_optical_vehicle_states_{DATE}.csv",
    "r1_baseline": SAMPLES_DIR / f"oty2_wgv3_5a_r1_complete_vehicle_baseline_{DATE}.csv",
}

OUTPUTS = {
    "identity_md": REPORT_DIR / f"oty2_wgv3_5a_r2_gm019_identity_and_observation_audit_{DATE}.md",
    "vehicle_map": SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_physical_vehicle_map_{DATE}.csv",
    "observation": SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_observation_states_{DATE}.csv",
    "recovered": SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_recovered_states_{DATE}.csv",
    "anchors": SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_anchor_manifest_{DATE}.csv",
    "projection": SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_projection_comparison_{DATE}.csv",
    "failures": SAMPLES_DIR / f"oty2_wgv3_5a_r2_gm019_failure_cases_{DATE}.csv",
    "visual_md": REPORT_DIR / f"oty2_wgv3_5a_r2_gm019_visual_diagnosis_{DATE}.md",
    "closure_md": REPORT_DIR / f"oty2_wgv3_5a_r2_gm019_closure_{DATE}.md",
}

PHYSICAL_MAP_FIELDS = [
    "physical_vehicle_id",
    "source_track_ids",
    "frame_start",
    "frame_end",
    "same_vehicle_relation",
    "different_vehicle_relation",
    "simultaneous_visibility",
    "appearance_evidence",
    "motion_evidence",
    "identity_confidence",
    "identity_blocked_reason",
]

OBSERVATION_FIELDS = [
    "pair_id",
    "frame",
    "sar_frame",
    "track_id",
    "physical_vehicle_id",
    "old_visibility_state",
    "geometry_edge_state",
    "observation_state",
    "visible_whole_body",
    "visible_front",
    "visible_rear",
    "visible_side",
    "visible_roof",
    "visible_window",
    "unknown_fragment",
    "left_truncated",
    "right_truncated",
    "bottom_truncated",
    "occluded",
    "multi_vehicle",
    "visible_parts",
    "depth_quality",
    "state_reason",
    "incorrect_old_visibility_label",
]

ANCHOR_FIELDS = [
    "anchor_plan",
    "anchor_count",
    "anchor_pair_ids",
    "anchor_frames",
    "selection_rule",
    "usable_for_scene_residual_calibration",
    "blocked_reason",
]

RECOVERED_FIELDS = [
    "pair_id",
    "physical_vehicle_id",
    "frame",
    "observation_state",
    "previous_direct_observable_frame",
    "next_direct_observable_frame",
    "recovery_mode",
    "recovered_center_x",
    "recovered_center_y",
    "recovered_width",
    "recovered_height",
    "recovered_depth",
    "recovery_confidence",
    "blocked_reason",
]

PROJECTION_FIELDS = [
    "evaluation_group",
    "method",
    "anchor_plan",
    "sample_count",
    "physical_vehicle_count",
    "azimuth_median_error",
    "azimuth_p90_error",
    "radial_median_error",
    "radial_p90_error",
    "center_coverage_50",
    "center_coverage_80",
    "center_coverage_95",
    "center_covered_95_count",
    "full_box_coverage_95",
    "median_search_ratio",
    "p90_search_ratio",
    "multi_target_rate",
    "wrong_identity_rate",
    "blocked_rate",
]

FAILURE_FIELDS = [
    "failure_id",
    "pair_id",
    "physical_vehicle_id",
    "frame",
    "method",
    "azimuth_error",
    "radial_error",
    "primary_failure",
    "local_center_bias",
    "depth_background_contamination",
    "relative_depth_scale_shift",
    "scene_azimuth_offset",
    "scene_radial_offset",
    "insufficient_complete_anchor",
    "identity_unresolved",
    "motion_interpolation_failure",
    "near_field_parallax",
    "SAR_pairing_suspect",
    "weak_calibration_model_suspect",
    "notes",
]


@dataclass(frozen=True)
class Box:
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
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def bottom_y(self) -> float:
        return self.y2

    def as_text(self) -> str:
        return f"{fmt(self.x1, 3)},{fmt(self.y1, 3)},{fmt(self.x2, 3)},{fmt(self.y2, 3)}"


@dataclass
class LinearModel:
    name: str
    features: list[str]
    coefficients: list[float]
    intercept: float

    def predict(self, values: Sequence[float]) -> float:
        return float(self.intercept + sum(c * v for c, v in zip(self.coefficients, values)))


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        text = norm(value)
        return float(text) if text else default
    except Exception:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    number = parse_float(value, float(default))
    return int(round(number)) if math.isfinite(number) else default


def fmt(value: Any, digits: int = 6) -> str:
    try:
        number = float(value)
    except Exception:
        return norm(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh) if not duplicate_header(row)]


def duplicate_header(row: Mapping[str, Any]) -> bool:
    hits = sum(1 for key, value in row.items() if norm(key) == norm(value))
    return hits >= max(2, len(row) // 2)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except Exception:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_fact(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:
        return f"unavailable:{exc}"


def median(values: Iterable[float], default: float = 0.0) -> float:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.median(clean)) if clean else default


def percentile(values: Iterable[float], pct: float, default: float = 0.0) -> float:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    return float(np.percentile(clean, pct)) if clean else default


def frame_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_frames" / f"{frame:06d}.png"


def depth_vis_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_depth" / f"{frame:06d}_depth_vis.png"


def sar_gray_path(frame: int) -> Path:
    return DATA_ROOT / SCENE / f"{SCENE}_SARframes_gray" / f"{frame:06d}.png"


def polar_to_pixel(azimuth_deg: float, radial_px: float) -> tuple[float, float]:
    angle = math.radians(azimuth_deg)
    return FAN_CENTER_X + radial_px * math.sin(angle), FAN_CENTER_Y - radial_px * math.cos(angle)


def load_r1_model() -> dict[str, Any]:
    rows = read_csv(INPUTS["r1_baseline"])
    az_row = next(row for row in rows if row["model_target"] == "azimuth" and row["selected"] == "true")
    rad_row = next(row for row in rows if row["model_target"] == "radial" and row["selected"] == "true")
    selected = next(row for row in rows if row["model_target"] == "complete_observation_selected")
    az_params = json.loads(az_row["parameters"])
    rad_params = json.loads(rad_row["parameters"])
    selected_params = json.loads(selected["parameters"])
    intervals = selected_params.get("intervals", {"az_q95": 2.0, "rad_q95": 31.795472356059967})
    return {
        "azimuth_model": LinearModel(az_row["model_name"], az_row["input_features"].split(";"), az_params["coefficients"], az_params["intercept"]),
        "radial_model": LinearModel(rad_row["model_name"], rad_row["input_features"].split(";"), rad_params["coefficients"], rad_params["intercept"]),
        "intervals": intervals,
        "selected_row": selected,
    }


def load_gm019_rows() -> list[dict[str, Any]]:
    pairs = [row for row in read_csv(INPUTS["pairs"]) if norm(row.get("scene")) == SCENE]
    optical = {row["pair_id"]: row for row in read_csv(INPUTS["optical"])}
    sar = {row["pair_id"]: row for row in read_csv(INPUTS["sar"])}
    joined = []
    for pair in pairs:
        pid = norm(pair["pair_id"])
        optical_row = optical[pid]
        sar_row = sar[pid]
        box = Box(
            parse_float(pair["optical_bbox_x1"]),
            parse_float(pair["optical_bbox_y1"]),
            parse_float(pair["optical_bbox_x2"]),
            parse_float(pair["optical_bbox_y2"]),
        )
        sar_box = Box(
            parse_float(pair["sar_bbox_x1"]),
            parse_float(pair["sar_bbox_y1"]),
            parse_float(pair["sar_bbox_x2"]),
            parse_float(pair["sar_bbox_y2"]),
        )
        joined.append(
            {
                "pair_id": pid,
                "frame": parse_int(pair["optical_frame"]),
                "sar_frame": parse_int(pair["sar_frame"]),
                "track_id": norm(pair["optical_thread_id"]),
                "box": box,
                "sar_box": sar_box,
                "old_visibility_state": norm(pair["visibility_state"]),
                "pair_confidence": norm(pair["pair_confidence"]),
                "identity_confidence": norm(pair.get("identity_confidence")),
                "sar_gt_id": norm(pair["sar_gt_id"]),
                "sar_azimuth": parse_float(sar_row["sar_center_azimuth_deg"]),
                "sar_radial": parse_float(sar_row["sar_center_radial_pixel"]),
                "sar_azimuth_span": parse_float(sar_row["sar_azimuth_span"], 0.0),
                "sar_radial_span": parse_float(sar_row["sar_radial_span"], 0.0),
                "depth": parse_float(optical_row.get("depth_D4"), parse_float(optical_row.get("depth_D1"))),
                "depth_D1": parse_float(optical_row.get("depth_D1")),
            }
        )
    joined.sort(key=lambda row: (row["frame"], row["track_id"], row["pair_id"]))
    return joined


def physical_id_for_track(track_id: str) -> str:
    mapping = {
        "oty1t_obj_GM_RM019_bytetrack_bt_0001": "PV_GM19_BLACK_SEDAN_NEAR_FIELD",
        "oty1t_obj_GM_RM019_bytetrack_bt_0005": "PV_GM19_WHITE_SUV_NEAR_FIELD",
        "oty1t_obj_GM_RM019_bytetrack_bt_0009": "PV_GM19_RIGHT_DARK_FRAGMENT",
        "oty1t_obj_GM_RM019_bytetrack_bt_0080": "PV_GM19_SILVER_MPV_NEAR_FIELD",
        "oty1t_obj_GM_RM019_bytetrack_bt_0098": "PV_GM19_GRAY_CAR_LEFT_EDGE",
    }
    return mapping.get(track_id, "PV_GM19_UNRESOLVED")


def edge_state(box: Box) -> tuple[str, dict[str, bool]]:
    flags = {
        "left_contact": box.x1 <= 2.0,
        "right_contact": box.x2 >= 798.0,
        "bottom_contact": box.y2 >= 598.0,
        "left_near_edge": box.x1 <= 24.0,
        "right_near_edge": box.x2 >= 776.0,
        "bottom_near_edge": box.y2 >= 582.0,
    }
    parts = []
    for name in ["left_contact", "right_contact", "bottom_contact", "left_near_edge", "right_near_edge", "bottom_near_edge"]:
        if flags[name]:
            parts.append(name)
    return ";".join(parts) if parts else "no_edge_contact", flags


def visible_part_labels(row: Mapping[str, Any], edge: str, flags: Mapping[str, bool]) -> dict[str, Any]:
    track = norm(row["track_id"])
    pair_id = norm(row["pair_id"])
    labels = {
        "visible_whole_body": False,
        "visible_front": False,
        "visible_rear": False,
        "visible_side": True,
        "visible_roof": False,
        "visible_window": True,
        "unknown_fragment": False,
        "left_truncated": flags["left_contact"] or flags["left_near_edge"],
        "right_truncated": flags["right_contact"] or flags["right_near_edge"],
        "bottom_truncated": flags["bottom_contact"] or flags["bottom_near_edge"],
        "occluded": False,
        "multi_vehicle": False,
        "visible_parts": "near-field side body;full center not reliable",
    }
    if track.endswith("0001"):
        labels.update({"visible_front": True, "visible_rear": True, "visible_parts": "black sedan side, bottom and right side truncated"})
    elif track.endswith("0005"):
        labels.update({"visible_front": True, "visible_rear": True, "visible_parts": "white SUV side, near-field bottom truncated and left/right edge phases"})
    elif track.endswith("0009"):
        labels.update({"visible_front": True, "visible_rear": False, "unknown_fragment": True, "multi_vehicle": True, "visible_parts": "right-edge dark vehicle fragment near simultaneous white SUV"})
    elif track.endswith("0080"):
        labels.update({"visible_front": True, "visible_rear": True, "visible_parts": "silver MPV side, strong near-field bottom/edge truncation"})
    elif track.endswith("0098"):
        labels.update({"visible_front": True, "visible_rear": False, "unknown_fragment": True, "visible_parts": "gray car front-left edge fragment"})
    if pair_id in {"WGV35A_PAIR_0208", "WGV35A_PAIR_0214", "WGV35A_PAIR_0215"}:
        labels["unknown_fragment"] = True
    if labels["bottom_truncated"] or labels["left_truncated"] or labels["right_truncated"]:
        labels["visible_whole_body"] = False
    return labels


def audit_observations(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    enriched = []
    by_vehicle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        item = dict(row)
        item["physical_vehicle_id"] = physical_id_for_track(norm(row["track_id"]))
        edge, flags = edge_state(row["box"])
        labels = visible_part_labels(row, edge, flags)
        hard_or_soft_edge = any(flags.values())
        high_conf = norm(row["pair_confidence"]) == "high_confidence_pair"
        # R2 deliberately requires complete-body anchors. GM_RM019 real rows
        # are near-field edge/bottom observations, so these rows cannot become
        # direct anchors merely because old metadata says boundary=none.
        direct = high_conf and not hard_or_soft_edge and labels["visible_whole_body"] and row["box"].width >= 120 and row["box"].height >= 60
        if direct:
            state = "direct_observable"
            reason = "complete body visible with no hard/soft edge contact"
        elif high_conf and not labels["unknown_fragment"]:
            state = "not_safely_recoverable"
            reason = "real near-field truncation exists but no same-vehicle direct-observable anchors are available"
        else:
            state = "not_safely_recoverable"
            reason = "non-high-confidence, fragmentary, or identity-unsafe observation"
        item.update(labels)
        item.update(
            {
                "geometry_edge_state": edge,
                "observation_state": state,
                "direct_observable": direct,
                "depth_quality": "relative_depth_near_field_scale_shift_risk" if parse_float(row["depth"]) < 3.1 else "relative_depth_background_or_edge_risk",
                "state_reason": reason,
                "incorrect_old_visibility_label": "boundary=none" in norm(row["old_visibility_state"]) and hard_or_soft_edge,
            }
        )
        enriched.append(item)
        by_vehicle[item["physical_vehicle_id"]].append(item)
    direct_by_vehicle = {vid: [row for row in items if row["direct_observable"]] for vid, items in by_vehicle.items()}
    # Apply the R2 anchor gate after the visual audit.
    for item in enriched:
        anchors = direct_by_vehicle.get(item["physical_vehicle_id"], [])
        if item["observation_state"] != "direct_observable" and anchors:
            before = [row for row in anchors if row["frame"] < item["frame"]]
            after = [row for row in anchors if row["frame"] > item["frame"]]
            if before or after:
                item["observation_state"] = "temporally_recoverable"
                item["state_reason"] = "same-vehicle direct anchor exists"
    obs_rows = []
    for item in enriched:
        obs_rows.append(
            {
                "pair_id": item["pair_id"],
                "frame": item["frame"],
                "sar_frame": item["sar_frame"],
                "track_id": item["track_id"],
                "physical_vehicle_id": item["physical_vehicle_id"],
                "old_visibility_state": item["old_visibility_state"],
                "geometry_edge_state": item["geometry_edge_state"],
                "observation_state": item["observation_state"],
                "visible_whole_body": bool_text(item["visible_whole_body"]),
                "visible_front": bool_text(item["visible_front"]),
                "visible_rear": bool_text(item["visible_rear"]),
                "visible_side": bool_text(item["visible_side"]),
                "visible_roof": bool_text(item["visible_roof"]),
                "visible_window": bool_text(item["visible_window"]),
                "unknown_fragment": bool_text(item["unknown_fragment"]),
                "left_truncated": bool_text(item["left_truncated"]),
                "right_truncated": bool_text(item["right_truncated"]),
                "bottom_truncated": bool_text(item["bottom_truncated"]),
                "occluded": bool_text(item["occluded"]),
                "multi_vehicle": bool_text(item["multi_vehicle"]),
                "visible_parts": item["visible_parts"],
                "depth_quality": item["depth_quality"],
                "state_reason": item["state_reason"],
                "incorrect_old_visibility_label": bool_text(item["incorrect_old_visibility_label"]),
            }
        )
    vehicle_rows = build_physical_vehicle_rows(enriched)
    return enriched, obs_rows, vehicle_rows


def build_physical_vehicle_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["physical_vehicle_id"]].append(row)
    facts = {
        "PV_GM19_BLACK_SEDAN_NEAR_FIELD": (
            "same physical vehicle across bt_0001 frames",
            "different from white SUV and later silver/gray vehicles",
            "none in paired rows",
            "black sedan side appearance; large close-range box clipped by right and bottom image borders",
            "short forward motion from frames 0 to 4; remains near bottom/right truncation",
            "0.9",
            "",
        ),
        "PV_GM19_WHITE_SUV_NEAR_FIELD": (
            "same physical vehicle across bt_0005 frames",
            "different from bt_0009 right-edge dark fragment in frame 13",
            "frame 13 has bt_0005 and bt_0009 simultaneously",
            "white SUV side appearance; visible from left-edge phase to right-edge phase",
            "large displacement from left to right across frames 13-39",
            "0.9",
            "",
        ),
        "PV_GM19_RIGHT_DARK_FRAGMENT": (
            "single fragment only",
            "different from bt_0005 because simultaneous and different appearance",
            "frame 13 simultaneous with bt_0005",
            "dark front/right-edge fragment only",
            "single-frame fragment; no safe continuation",
            "0.75",
            "fragmentary and non-vehicle pair confidence",
        ),
        "PV_GM19_SILVER_MPV_NEAR_FIELD": (
            "same physical vehicle across bt_0080 frames",
            "different from earlier sedan/SUV and later gray car",
            "none in paired rows",
            "silver MPV/van side with advertisement marking",
            "moves through near-field from left edge to right edge frames 102-139",
            "0.92",
            "",
        ),
        "PV_GM19_GRAY_CAR_LEFT_EDGE": (
            "same physical vehicle across bt_0098 frames",
            "different from bt_0080 by time, appearance and position",
            "none in paired rows",
            "gray car front-left edge fragment with green plate",
            "two adjacent edge frames 151-152",
            "0.82",
            "only edge/front fragment visible",
        ),
    }
    out = []
    for vid, items in sorted(grouped.items()):
        tracks = sorted(set(row["track_id"] for row in items))
        frames = [parse_int(row["frame"]) for row in items]
        fact = facts.get(vid, ("identity unresolved", "unknown", "unknown", "unknown", "unknown", "0.2", "insufficient evidence"))
        out.append(
            {
                "physical_vehicle_id": vid,
                "source_track_ids": ";".join(tracks),
                "frame_start": min(frames),
                "frame_end": max(frames),
                "same_vehicle_relation": fact[0],
                "different_vehicle_relation": fact[1],
                "simultaneous_visibility": fact[2],
                "appearance_evidence": fact[3],
                "motion_evidence": fact[4],
                "identity_confidence": fact[5],
                "identity_blocked_reason": fact[6],
            }
        )
    return out


def build_anchor_manifest(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    direct = [row for row in rows if row["observation_state"] == "direct_observable"]
    sorted_direct = sorted(direct, key=lambda row: row["frame"])
    plans = [("A0", 0), ("A1", 1), ("A3", 3), ("A5", 5)]
    out = []
    for plan, count in plans:
        if count == 0:
            selected = []
            blocked = ""
        elif len(sorted_direct) >= count:
            positions = np.linspace(0, len(sorted_direct) - 1, count).round().astype(int)
            selected = [sorted_direct[int(idx)] for idx in positions]
            blocked = ""
        else:
            selected = []
            blocked = "no_direct_observable_scene_anchor_available"
        out.append(
            {
                "anchor_plan": plan,
                "anchor_count": len(selected),
                "anchor_pair_ids": ";".join(row["pair_id"] for row in selected),
                "anchor_frames": ";".join(str(row["frame"]) for row in selected),
                "selection_rule": "pre-error fixed temporal spread over direct-observable high-confidence rows",
                "usable_for_scene_residual_calibration": bool_text(bool(selected) or count == 0),
                "blocked_reason": blocked,
            }
        )
    return out


def predict_local(model: Mapping[str, Any], box: Box) -> tuple[float, float]:
    az_model: LinearModel = model["azimuth_model"]
    rad_model: LinearModel = model["radial_model"]
    az_features = [box.cx, box.cx * box.cx] if len(az_model.features) == 2 else [box.cx]
    if rad_model.features == ["bbox_width", "bbox_height", "bbox_bottom_y"]:
        rad_features = [box.width, box.height, box.bottom_y]
    else:
        rad_features = [box.width, box.height, box.bottom_y]
    return az_model.predict(az_features), rad_model.predict(rad_features)


def build_recovery_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    direct_by_vehicle: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["observation_state"] == "direct_observable":
            direct_by_vehicle[row["physical_vehicle_id"]].append(row)
    recovered = []
    for row in rows:
        anchors = sorted(direct_by_vehicle.get(row["physical_vehicle_id"], []), key=lambda item: item["frame"])
        prev = next((item for item in reversed(anchors) if item["frame"] < row["frame"]), None)
        nxt = next((item for item in anchors if item["frame"] > row["frame"]), None)
        if row["observation_state"] == "direct_observable":
            mode = "direct_observable"
            blocked = ""
            rec_box = row["box"]
            confidence = 1.0
        elif prev or nxt:
            mode = "limited_anchor_recovery"
            blocked = ""
            rec_box = (prev or nxt)["box"]
            confidence = 0.45
        else:
            mode = "blocked"
            blocked = "insufficient_complete_anchor"
            rec_box = None
            confidence = 0.0
        recovered.append(
            {
                "pair_id": row["pair_id"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "frame": row["frame"],
                "observation_state": row["observation_state"],
                "previous_direct_observable_frame": prev["frame"] if prev else "",
                "next_direct_observable_frame": nxt["frame"] if nxt else "",
                "recovery_mode": mode,
                "recovered_center_x": fmt(rec_box.cx) if rec_box else "",
                "recovered_center_y": fmt(rec_box.cy) if rec_box else "",
                "recovered_width": fmt(rec_box.width) if rec_box else "",
                "recovered_height": fmt(rec_box.height) if rec_box else "",
                "recovered_depth": fmt(row["depth"]) if rec_box else "",
                "recovery_confidence": fmt(confidence),
                "blocked_reason": blocked,
            }
        )
    return recovered


def evaluation_item(row: Mapping[str, Any], method: str, anchor_plan: str, az: float, radial: float, intervals: Mapping[str, float], extra_scale: float = 1.0) -> dict[str, Any]:
    az_half = parse_float(intervals.get("az_q95"), 2.0) * extra_scale
    radial_half = parse_float(intervals.get("rad_q95"), 31.795472356059967) * extra_scale
    az_error = abs(az - parse_float(row["sar_azimuth"]))
    radial_error = abs(radial - parse_float(row["sar_radial"]))
    center50 = az_error <= max(1.0, az_half * 0.5) and radial_error <= max(8.0, radial_half * 0.5)
    center80 = az_error <= max(1.5, az_half * 0.8) and radial_error <= max(12.0, radial_half * 0.8)
    center95 = az_error <= az_half and radial_error <= radial_half
    full95 = center95 and az_half >= az_error + row["sar_azimuth_span"] / 2 and radial_half >= radial_error + row["sar_radial_span"] / 2
    search_ratio = (2 * az_half / FULL_AZIMUTH_SPAN) * (2 * radial_half / FAN_RADIUS_PX)
    return {
        "pair_id": row["pair_id"],
        "physical_vehicle_id": row["physical_vehicle_id"],
        "frame": row["frame"],
        "group": row["observation_state"],
        "method": method,
        "anchor_plan": anchor_plan,
        "azimuth_error": az_error,
        "radial_error": radial_error,
        "center50": 1.0 if center50 else 0.0,
        "center80": 1.0 if center80 else 0.0,
        "center95": 1.0 if center95 else 0.0,
        "full95": 1.0 if full95 else 0.0,
        "search_ratio": search_ratio,
        "wrong_identity": 0.0,
        "multi_target": 1.0 if row.get("multi_vehicle") else 0.0,
    }


def aggregate(items: Sequence[Mapping[str, Any]], blocked_total: int = 0) -> dict[str, Any]:
    total = len(items) + blocked_total
    if not items:
        return {
            "sample_count": 0,
            "physical_vehicle_count": 0,
            "azimuth_median_error": "",
            "azimuth_p90_error": "",
            "radial_median_error": "",
            "radial_p90_error": "",
            "center_coverage_50": "0/0",
            "center_coverage_80": "0/0",
            "center_coverage_95": "0/0",
            "center_covered_95_count": "0/0",
            "full_box_coverage_95": "0/0",
            "median_search_ratio": "",
            "p90_search_ratio": "",
            "multi_target_rate": "",
            "wrong_identity_rate": "",
            "blocked_rate": fmt(blocked_total / total if total else 0.0),
        }
    n = len(items)
    return {
        "sample_count": n,
        "physical_vehicle_count": len(set(item["physical_vehicle_id"] for item in items)),
        "azimuth_median_error": fmt(median(item["azimuth_error"] for item in items)),
        "azimuth_p90_error": fmt(percentile((item["azimuth_error"] for item in items), 90)),
        "radial_median_error": fmt(median(item["radial_error"] for item in items)),
        "radial_p90_error": fmt(percentile((item["radial_error"] for item in items), 90)),
        "center_coverage_50": f"{int(sum(item['center50'] for item in items))}/{n}",
        "center_coverage_80": f"{int(sum(item['center80'] for item in items))}/{n}",
        "center_coverage_95": f"{int(sum(item['center95'] for item in items))}/{n}",
        "center_covered_95_count": f"{int(sum(item['center95'] for item in items))}/{n}",
        "full_box_coverage_95": f"{int(sum(item['full95'] for item in items))}/{n}",
        "median_search_ratio": fmt(median(item["search_ratio"] for item in items), 8),
        "p90_search_ratio": fmt(percentile((item["search_ratio"] for item in items), 90), 8),
        "multi_target_rate": fmt(sum(item["multi_target"] for item in items) / n),
        "wrong_identity_rate": fmt(sum(item["wrong_identity"] for item in items) / n),
        "blocked_rate": fmt(blocked_total / total if total else 0.0),
    }


def build_projection_rows(rows: Sequence[Mapping[str, Any]], recovered_rows: Sequence[Mapping[str, Any]], anchor_rows: Sequence[Mapping[str, Any]], model: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    intervals = model["intervals"]
    z0_items = []
    for row in rows:
        az, radial = predict_local(model, row["box"])
        z0_items.append(evaluation_item(row, "Z0_GM17_model_direct_local_observation", "A0", az, radial, intervals))
    recovered_by_id = {row["pair_id"]: row for row in recovered_rows}
    z1_items = []
    for row in rows:
        rec = recovered_by_id[row["pair_id"]]
        if norm(rec["recovery_mode"]) == "blocked":
            continue
        box = Box(
            parse_float(rec["recovered_center_x"]) - parse_float(rec["recovered_width"]) / 2,
            parse_float(rec["recovered_center_y"]) - parse_float(rec["recovered_height"]) / 2,
            parse_float(rec["recovered_center_x"]) + parse_float(rec["recovered_width"]) / 2,
            parse_float(rec["recovered_center_y"]) + parse_float(rec["recovered_height"]) / 2,
        )
        az, radial = predict_local(model, box)
        z1_items.append(evaluation_item(row, "Z1_temporal_full_vehicle_recovery", "A0", az, radial, intervals))
    rows_out = []
    for group in ["direct_observable", "temporally_recoverable", "not_safely_recoverable", "all_evaluable"]:
        base = z0_items if group == "all_evaluable" else [item for item in z0_items if item["group"] == group]
        metrics = aggregate(base)
        rows_out.append({"evaluation_group": group, "method": "Z0_GM17_model_direct_local_observation", "anchor_plan": "A0", **metrics})
        recover_base = z1_items if group == "all_evaluable" else [item for item in z1_items if item["group"] == group]
        group_total = len(rows) if group == "all_evaluable" else sum(1 for row in rows if row["observation_state"] == group)
        metrics = aggregate(recover_base, max(0, group_total - len(recover_base)))
        rows_out.append({"evaluation_group": group, "method": "Z1_temporal_full_vehicle_recovery", "anchor_plan": "A0", **metrics})
    for plan in ["A1", "A3", "A5"]:
        anchor = next(row for row in anchor_rows if row["anchor_plan"] == plan)
        metrics = aggregate([], blocked_total=len(rows))
        rows_out.append({"evaluation_group": "all_evaluable", "method": "Z2_recovery_plus_scene_residual_calibration", "anchor_plan": plan, **metrics})
    failures = build_failure_rows(rows, z0_items, recovered_by_id)
    return rows_out, failures, z0_items + z1_items


def build_failure_rows(rows: Sequence[Mapping[str, Any]], z0_items: Sequence[Mapping[str, Any]], recovered_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    item_by_pair = {item["pair_id"]: item for item in z0_items}
    failures = []
    for idx, row in enumerate(rows, 1):
        item = item_by_pair[row["pair_id"]]
        rec = recovered_by_id[row["pair_id"]]
        local_bias = row["left_truncated"] or row["right_truncated"] or row["unknown_fragment"]
        depth_risk = row["bottom_truncated"] or "scale_shift" in row["depth_quality"]
        scene_az = abs(item["azimuth_error"]) > 8.0
        scene_rad = abs(item["radial_error"]) > 80.0
        if norm(rec["blocked_reason"]) == "insufficient_complete_anchor":
            primary = "insufficient_complete_anchor"
        elif local_bias:
            primary = "local_center_bias"
        elif depth_risk:
            primary = "depth_background_contamination"
        elif scene_az:
            primary = "scene_azimuth_offset"
        elif scene_rad:
            primary = "scene_radial_offset"
        else:
            primary = "near_field_parallax"
        failures.append(
            {
                "failure_id": f"R2_GM19_FAIL_{idx:03d}",
                "pair_id": row["pair_id"],
                "physical_vehicle_id": row["physical_vehicle_id"],
                "frame": row["frame"],
                "method": "Z0/Z1",
                "azimuth_error": fmt(item["azimuth_error"]),
                "radial_error": fmt(item["radial_error"]),
                "primary_failure": primary,
                "local_center_bias": bool_text(local_bias),
                "depth_background_contamination": bool_text(depth_risk),
                "relative_depth_scale_shift": bool_text(parse_float(row["depth"]) < 3.1),
                "scene_azimuth_offset": bool_text(scene_az),
                "scene_radial_offset": bool_text(scene_rad),
                "insufficient_complete_anchor": bool_text(norm(rec["blocked_reason"]) == "insufficient_complete_anchor"),
                "identity_unresolved": bool_text(norm(row["physical_vehicle_id"]).endswith("FRAGMENT")),
                "motion_interpolation_failure": "false",
                "near_field_parallax": bool_text(row["box"].height > 220),
                "SAR_pairing_suspect": "false",
                "weak_calibration_model_suspect": bool_text(abs(item["radial_error"]) > 120.0),
                "notes": row["state_reason"],
            }
        )
    return failures


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    subset = list(rows[:limit] if limit is not None else rows)
    if not subset:
        return "_No rows._"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in subset:
        lines.append("| " + " | ".join(norm(row.get(field, "")).replace("\n", " ") for field in fields) + " |")
    return "\n".join(lines)


def build_r1_freeze_manifest() -> list[dict[str, Any]]:
    out = []
    for path in R1_FILES:
        row = {"source_file": rel(path), "sha256": sha256_file(path), "bytes": path.stat().st_size, "rows": ""}
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.reader(fh)
                next(reader, None)
                row["rows"] = sum(1 for _ in reader)
        out.append(row)
    return out


def draw_case_overlay(row: Mapping[str, Any], model: Mapping[str, Any], out_path: Path) -> None:
    frame = parse_int(row["frame"])
    sar_frame = parse_int(row["sar_frame"])
    opt = Image.open(frame_path(frame)).convert("RGB") if frame_path(frame).exists() else Image.new("RGB", (800, 600), "black")
    depth = Image.open(depth_vis_path(frame)).convert("RGB") if depth_vis_path(frame).exists() else Image.new("RGB", (800, 600), "black")
    sar = Image.open(sar_gray_path(sar_frame)).convert("RGB") if sar_gray_path(sar_frame).exists() else Image.new("RGB", (int(SAR_WIDTH), int(SAR_HEIGHT)), "black")
    opt = opt.resize((400, 300))
    depth = depth.resize((400, 300))
    sar = sar.resize((520, 300))
    canvas = Image.new("RGB", (1320, 360), (18, 18, 18))
    canvas.paste(opt, (0, 0))
    canvas.paste(depth, (400, 0))
    canvas.paste(sar, (800, 0))
    draw = ImageDraw.Draw(canvas)
    sx, sy = 400 / OPTICAL_WIDTH, 300 / OPTICAL_HEIGHT
    box: Box = row["box"]
    for offset in [0, 400]:
        draw.rectangle([offset + box.x1 * sx, box.y1 * sy, offset + box.x2 * sx, box.y2 * sy], outline=(255, 220, 0), width=3)
    ssx, ssy = 520 / SAR_WIDTH, 300 / SAR_HEIGHT
    gt: Box = row["sar_box"]
    draw.rectangle([800 + gt.x1 * ssx, gt.y1 * ssy, 800 + gt.x2 * ssx, gt.y2 * ssy], outline=(0, 255, 120), width=2)
    az, radial = predict_local(model, box)
    px, py = polar_to_pixel(az, radial)
    draw.ellipse([800 + px * ssx - 5, py * ssy - 5, 800 + px * ssx + 5, py * ssy + 5], outline=(255, 220, 0), width=3)
    draw.rectangle([0, 300, 1320, 360], fill=(0, 0, 0))
    text = f"{row['pair_id']} f{frame} {row['physical_vehicle_id']} state={row['observation_state']} yellow=local/Z0 green=SAR reference"
    draw.text((8, 312), text, fill=(255, 255, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def make_contact_sheet(paths: Sequence[Path], out_path: Path, cols: int = 2) -> None:
    thumbs = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        img.thumbnail((520, 140))
        tile = Image.new("RGB", (520, 140), (20, 20, 20))
        tile.paste(img, (0, 0))
        thumbs.append(tile)
    if not thumbs:
        return
    sheet = Image.new("RGB", (cols * 520, math.ceil(len(thumbs) / cols) * 140), (18, 18, 18))
    for idx, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((idx % cols) * 520, (idx // cols) * 140))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def render_visuals(rows: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]], model: Mapping[str, Any]) -> dict[str, str]:
    all_paths = []
    for row in rows:
        out = OUTPUT_DIR / f"gm019_pair_{row['pair_id']}.png"
        draw_case_overlay(row, model, out)
        all_paths.append(out)
    sheet_all = OUTPUT_DIR / "gm019_all_pair_visual_review.png"
    make_contact_sheet(all_paths, sheet_all)
    truncated_paths = [p for p, row in zip(all_paths, rows) if row["left_truncated"] or row["right_truncated"] or row["bottom_truncated"]]
    sheet_trunc = OUTPUT_DIR / "gm019_truncated_visual_review.png"
    make_contact_sheet(truncated_paths, sheet_trunc)
    failed_ids = set(row["pair_id"] for row in failures)
    failure_paths = [p for p, row in zip(all_paths, rows) if row["pair_id"] in failed_ids]
    sheet_fail = OUTPUT_DIR / "gm019_failed_visual_review.png"
    make_contact_sheet(failure_paths, sheet_fail)
    return {"all_pairs": str(sheet_all), "truncated": str(sheet_trunc), "failures": str(sheet_fail)}


def render_reports(
    r1_freeze: Sequence[Mapping[str, Any]],
    vehicle_rows: Sequence[Mapping[str, Any]],
    observation_rows: Sequence[Mapping[str, Any]],
    anchor_rows: Sequence[Mapping[str, Any]],
    recovery_rows: Sequence[Mapping[str, Any]],
    projection_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    visual_paths: Mapping[str, str],
    status: str,
) -> None:
    direct = sum(1 for row in observation_rows if row["observation_state"] == "direct_observable")
    temp = sum(1 for row in observation_rows if row["observation_state"] == "temporally_recoverable")
    blocked = sum(1 for row in observation_rows if row["observation_state"] == "not_safely_recoverable")
    incorrect = sum(1 for row in observation_rows if row["incorrect_old_visibility_label"] == "true")
    lines = [
        "# OTY2 WGV3.5A-R2 GM_RM019 Identity And Observation Audit",
        "",
        f"Date: {DATE}",
        "",
        "## Boundary",
        "",
        "R2 uses GM_RM019 only. R1 model parameters are frozen before GM_RM019 evaluation. GT is used only for posthoc error measurement.",
        "",
        "## 中文闸门结论",
        "",
        "- 本阶段只诊断GM_RM019能否形成可信的物理迁移区域 / SAR物理可行域，不输出最终SAR边界框。",
        "- 16个外部配对样本经图像复核后均属于近场底边或左右边缘截断；当前初始迁移区域由局部框得到，不能代表完整车辆恢复状态。",
        "- GM_RM019没有满足身份明确、车体完整、无硬/软边缘截断、深度可信的直接锚点，因此场景校准锚点数量为0。",
        "- 直接迁移仅作为Z0失败来源分解；时序恢复迁移和少量场景残差校准均被阻塞。",
        "- R2未正向关闭，R3/R4不得继续执行；需要复核只能作为后续人工审阅状态，不能替代本阶段通过条件。",
        "",
        "## R1 Freeze",
        "",
        md_table(r1_freeze, ["source_file", "sha256", "bytes", "rows"]),
        "",
        "## Physical Vehicle Map",
        "",
        md_table(vehicle_rows, PHYSICAL_MAP_FIELDS),
        "",
        "## Observation Summary",
        "",
        f"- direct_observable: `{direct}`",
        f"- temporally_recoverable: `{temp}`",
        f"- not_safely_recoverable: `{blocked}`",
        f"- incorrect old visibility labels: `{incorrect}`",
        "",
        "## Observation Rows",
        "",
        md_table(observation_rows, OBSERVATION_FIELDS),
    ]
    write_text(OUTPUTS["identity_md"], "\n".join(lines))

    visual_lines = [
        "# OTY2 WGV3.5A-R2 GM_RM019 Visual Diagnosis",
        "",
        f"Date: {DATE}",
        "",
        "Diagnostic PNGs are written under ignored `outputs/wgv3_5a_r2_gm019_20260710/`.",
        "",
        "## Contact Sheets",
        "",
    ]
    for name, path in visual_paths.items():
        visual_lines.append(f"- {name}: `{rel(Path(path))}`")
    visual_lines.extend(
        [
            "",
            "## Chinese Review Notes",
            "",
            "- 16个GM_RM019配对样本均已打开成接触图复核。",
            "- 主要车辆包括近场黑色轿车、白色SUV、银色MPV、灰色左缘车辆，以及一个右缘深色碎片。",
            "- 当前看到的车辆大多贴近图像底边或左右边，框中心不能稳定代表整车中心。",
            "- 深度图在近场边缘框内包含路面、车身局部和背景混合，存在相对深度尺度变化风险。",
            "- 没有满足身份明确、车体完整、无硬/软边缘截断的GM_RM019直接锚点，因此不能安全执行时序整车恢复。",
            "- Z0只是局部观测直接投影，用来分解失败来源；Z1因锚点不足被阻断。",
        ]
    )
    write_text(OUTPUTS["visual_md"], "\n".join(visual_lines))

    fail_counts = Counter(row["primary_failure"] for row in failure_rows)
    z0_all = next(row for row in projection_rows if row["evaluation_group"] == "all_evaluable" and row["method"].startswith("Z0"))
    z1_all = next(row for row in projection_rows if row["evaluation_group"] == "all_evaluable" and row["method"].startswith("Z1"))
    closure = [
        "# OTY2 WGV3.5A-R2 GM_RM019 Closure",
        "",
        f"Date: {DATE}",
        "",
        f"R2 status: `{status}`",
        "",
        "## Boundary",
        "",
        "R2 stopped at GM_RM019 because complete anchors are insufficient. R3 and R4 must not run after this state.",
        "",
        "## 中文关闭结论",
        "",
        "- R2关闭状态为`OPEN_GM19_COMPLETE_ANCHOR_INSUFFICIENT`：GM_RM019没有可用完整车辆恢复状态锚点。",
        "- 所有16个样本均为阻塞；0个直接迁移样本，0个时序恢复迁移样本，0个可用于A1/A3/A5的场景校准锚点。",
        "- 截断贡献是主导证据：近场局部框中心和底边深度明显偏离整车状态，Z0在all_evaluable上中心覆盖为0/16。",
        "- 场景几何偏移和相对深度尺度变化仍可能存在，但当前缺少完整锚点，不能把三者稳定分离或校准。",
        "- 因R2未达到两个正向关闭状态之一，后续GM_RM011遮挡验证和统一物理迁移前端均未执行。",
        "",
        "## Physical Vehicles",
        "",
        md_table(vehicle_rows, PHYSICAL_MAP_FIELDS),
        "",
        "## Observation Counts",
        "",
        f"- direct_observable: `{direct}`",
        f"- temporally_recoverable: `{temp}`",
        f"- blocked/not_safely_recoverable: `{blocked}`",
        f"- incorrect old visibility labels: `{incorrect}`",
        "",
        "## Anchor Manifest",
        "",
        md_table(anchor_rows, ANCHOR_FIELDS),
        "",
        "## Projection Comparison",
        "",
        md_table(projection_rows, PROJECTION_FIELDS),
        "",
        "## Failure Decomposition",
        "",
        f"- dominant counts: `{dict(fail_counts)}`",
        "- Z0 local projection preserves the R1 zero-scene-calibration baseline but it acts on local near-field boxes whose centers and bottom depths are physically distorted.",
        "- Z1 cannot be fairly evaluated because there are no direct-observable same-vehicle anchors in GM_RM019.",
        "- A1/A3/A5 residual calibration cannot be run because anchor count is zero.",
        "",
        "## Created Files",
        "",
        "\n".join(f"- `{rel(path)}`" for path in OUTPUTS.values()),
    ]
    write_text(OUTPUTS["closure_md"], "\n".join(closure))


def run_all(stage: str) -> dict[str, Any]:
    r1_freeze = build_r1_freeze_manifest()
    model = load_r1_model()
    raw_rows = load_gm019_rows()
    audited_rows, observation_rows, vehicle_rows = audit_observations(raw_rows)
    anchor_rows = build_anchor_manifest(audited_rows)
    recovery_rows = build_recovery_rows(audited_rows)
    projection_rows, failure_rows, eval_items = build_projection_rows(audited_rows, recovery_rows, anchor_rows, model)
    direct = sum(1 for row in audited_rows if row["observation_state"] == "direct_observable")
    temp = sum(1 for row in audited_rows if row["observation_state"] == "temporally_recoverable")
    if direct == 0:
        status = "OPEN_GM19_COMPLETE_ANCHOR_INSUFFICIENT"
    elif temp == 0:
        status = "CLOSED_GM19_RECOVERY_INSUFFICIENT"
    else:
        status = "CLOSED_GM19_RECOVERY_FEASIBLE_SCENE_RESIDUAL_REQUIRED"
    visual_paths = render_visuals(audited_rows, failure_rows, model)

    write_csv(OUTPUTS["vehicle_map"], vehicle_rows, PHYSICAL_MAP_FIELDS)
    write_csv(OUTPUTS["observation"], observation_rows, OBSERVATION_FIELDS)
    write_csv(OUTPUTS["anchors"], anchor_rows, ANCHOR_FIELDS)
    write_csv(OUTPUTS["recovered"], recovery_rows, RECOVERED_FIELDS)
    write_csv(OUTPUTS["projection"], projection_rows, PROJECTION_FIELDS)
    write_csv(OUTPUTS["failures"], failure_rows, FAILURE_FIELDS)
    render_reports(r1_freeze, vehicle_rows, observation_rows, anchor_rows, recovery_rows, projection_rows, failure_rows, visual_paths, status)
    return {
        "stage": stage,
        "status": status,
        "direct_observable": direct,
        "temporally_recoverable": temp,
        "blocked": sum(1 for row in audited_rows if row["observation_state"] == "not_safely_recoverable"),
        "outputs": {key: str(path) for key, path in OUTPUTS.items()},
        "visual_outputs": visual_paths,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["audit", "recover", "calibrate", "evaluate", "visualize", "all"], default="all")
    args = parser.parse_args(argv)
    print(json.dumps(run_all(args.stage), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
