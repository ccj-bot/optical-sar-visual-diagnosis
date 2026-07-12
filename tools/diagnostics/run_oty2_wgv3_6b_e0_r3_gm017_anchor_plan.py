"""Freeze E0-R3 GM_RM017 high-observability anchor plan.

The plan stage reads only geometry, identity, mask metadata, trajectory/body-axis
proxy rows, and E0-R2 relative-aspect rows. It must not read SAR intensity,
E0-R2 response descriptors, E0-R2 response_index, or E0-R2 Gate outcomes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


DATE = "20260712"
SCENE = "GM_RM017"
BRANCH = "feature/oty2-gm017-physical-factor-discovery"
START_COMMIT = "7a9d9cba9f38447e10c917227a789f4160569026"
PHYSICAL_VEHICLE_ID = "GM_RM017_WGV35A_MAIN_VEHICLE_THREAD"

FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6
RADIAL_GRID_SPACING_M_PER_PX = 0.03

MAXIMUM_ALLOWED_FRAME_GAP = 4
MINIMUM_ANCHOR_SEGMENT_LENGTH = 12
MINIMUM_OBSERVABLE_ASPECT_SPAN_DEG = 20.0
MINIMUM_RANGE_OR_AZIMUTH_CHANGE_M = 0.75
PAIR_ASPECT_SAME_DEG = 5.0
PAIR_ASPECT_DIFFERENT_DEG = 15.0
PAIR_SIMILAR_RANGE_M = 2.0
PAIR_MIN_TIME_SEPARATION_FRAMES = 5
PAIR_MAX_ROWS_PER_TYPE = 160

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"

R1_UNIQUE_GT = SAMPLES_DIR / f"e0_r1_r1_unique_gt_center_sequence_{DATE}.csv"
R1_AXIAL_HEADING = SAMPLES_DIR / f"e0_r1_r1_axial_body_heading_{DATE}.csv"
E0_R1_REGION_MANIFEST = SAMPLES_DIR / f"oty2_wgv3_6b_e0_r1_gm017_region_manifest_{DATE}.csv"
E0_MASK_AUDIT = SAMPLES_DIR / f"oty2_wgv3_6b_e0_gm017_mask_censoring_audit_{DATE}.csv"
E0_R2_ASPECT = SAMPLES_DIR / f"e0_r2_relative_aspect_timeline_{DATE}.csv"
E0_R2_PROTOCOL = REPO_ROOT / "docs" / "OTY2_GM017_TEMPORAL_MULTI_ASPECT_RESPONSE_E0_R2_PROTOCOL.md"
PROTOCOL = REPO_ROOT / "docs" / "OTY2_GM017_HIGH_OBSERVABILITY_MULTI_VIEW_STRUCTURAL_CONTINUITY_E0_R3_PROTOCOL.md"

OUTPUTS = {
    "anchor_segment_manifest": SAMPLES_DIR / f"e0_r3_anchor_segment_manifest_{DATE}.csv",
    "anchor_plan_seal": SAMPLES_DIR / f"e0_r3_anchor_plan_seal_{DATE}.csv",
    "mask_observability_timeline": SAMPLES_DIR / f"e0_r3_mask_observability_timeline_{DATE}.csv",
    "body_axis_proxy_timeline": SAMPLES_DIR / f"e0_r3_body_axis_proxy_timeline_{DATE}.csv",
    "aspect_matched_pair_plan": SAMPLES_DIR / f"e0_r3_aspect_matched_pair_plan_{DATE}.csv",
}


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
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
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return ""
    text = f"{number:.{ndigits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def git_output(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover
        return f"unavailable:{exc}"


def frame_split(frame: int) -> str:
    if frame <= 360:
        return "calibration"
    if frame <= 370:
        return "guard"
    return "posthoc_diagnosis"


def axis_angle_deg(angle: float) -> float:
    return angle % 180.0


def directed_angle_deg(dx: float, dy: float) -> float:
    if math.hypot(dx, dy) <= 1e-12:
        return 0.0
    return math.degrees(math.atan2(dy, dx))


def axial_diff_deg(a: float, b: float) -> float:
    return abs(((axis_angle_deg(a) - axis_angle_deg(b) + 90.0) % 180.0) - 90.0)


def calibration_aspect_bounds(aspect_rows: Sequence[Mapping[str, str]]) -> tuple[float, float]:
    cal = [
        parse_float(row["relative_aspect_angle_deg"])
        for row in aspect_rows
        if row.get("split") == "calibration" and row.get("aspect_observability_status") in {"OBSERVABLE_HIGH", "OBSERVABLE_MEDIUM"}
    ]
    return (min(cal), max(cal)) if cal else (0.0, 0.0)


def load_plan_inputs() -> dict[str, Any]:
    centers = {
        parse_int(row["sar_frame"]): row
        for row in read_csv(R1_UNIQUE_GT)
        if row.get("included_in_heading_main_analysis") == "true" and row.get("selected_center_x") != ""
    }
    heading = {parse_int(row["sar_frame"]): row for row in read_csv(R1_AXIAL_HEADING)}
    body_regions = {
        parse_int(row["sar_frame"]): row
        for row in read_csv(E0_R1_REGION_MANIFEST)
        if row.get("variant") == "body_axis_reference" and row.get("family") == "BODY_ALIGNED_REFERENCE"
    }
    mask = {parse_int(row["sar_frame"]): row for row in read_csv(E0_MASK_AUDIT)}
    aspect_rows = read_csv(E0_R2_ASPECT)
    aspect = {parse_int(row["sar_frame"]): row for row in aspect_rows}
    cal_min, cal_max = calibration_aspect_bounds(aspect_rows)
    return {
        "centers": centers,
        "heading": heading,
        "body_regions": body_regions,
        "mask": mask,
        "aspect": aspect,
        "calibration_aspect_min": cal_min,
        "calibration_aspect_max": cal_max,
    }


def build_frame_rows(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    centers: Mapping[int, Mapping[str, str]] = inputs["centers"]
    heading: Mapping[int, Mapping[str, str]] = inputs["heading"]
    body_regions: Mapping[int, Mapping[str, str]] = inputs["body_regions"]
    mask: Mapping[int, Mapping[str, str]] = inputs["mask"]
    aspect: Mapping[int, Mapping[str, str]] = inputs["aspect"]
    cal_min = parse_float(inputs["calibration_aspect_min"])
    cal_max = parse_float(inputs["calibration_aspect_max"])
    for frame in sorted(set(centers) & set(body_regions) & set(mask) & set(aspect)):
        c = centers[frame]
        h = heading.get(frame, {})
        b = body_regions[frame]
        m = mask[frame]
        a = aspect[frame]
        cx = parse_float(c["selected_center_x"])
        cy = parse_float(c["selected_center_y"])
        dx = cx - FAN_CENTER_X
        dy = cy - FAN_CENTER_Y
        absolute_range = math.hypot(dx, dy) * RADIAL_GRID_SPACING_M_PER_PX
        absolute_azimuth = directed_angle_deg(dx, dy)
        relative_aspect = parse_float(a["relative_aspect_angle_deg"])
        gt_visible = parse_float(m.get("gt_visible_fraction"), 0.0)
        mask_contact = parse_float(m.get("gt_mask_contact_ratio"), 1.0)
        boundary_contact = parse_float(m.get("gt_boundary_contact_ratio"), 1.0)
        split = a.get("split", frame_split(frame))
        aspect_domain_status = "IN_CALIBRATION_ASPECT_DOMAIN" if cal_min <= relative_aspect <= cal_max else "OUT_OF_CALIBRATION_ASPECT_DOMAIN"
        high_observable = (
            c.get("identity_consistency_status") in {"single_pair_single_gt", "duplicate_frame_primary_thread_selected_weak_correspondence_excluded"}
            and gt_visible >= 0.98
            and mask_contact <= 0.001
            and boundary_contact <= 0.001
            and a.get("aspect_observability_status") in {"OBSERVABLE_HIGH", "OBSERVABLE_MEDIUM"}
        )
        if high_observable and split == "calibration":
            planned_class = "A_COMPLETE_OBSERVABLE_ANCHOR"
        elif high_observable and split == "guard":
            planned_class = "B_MASK_OR_DOMAIN_TRANSITION_RESERVED"
        else:
            planned_class = "C_OUT_OF_DOMAIN_OR_STRESS_CONTROL"
        row = {
            "pair_id": c.get("selected_pair_id", a.get("pair_id", "")),
            "sar_frame": frame,
            "timestamp_or_sequence_index": frame,
            "split": split,
            "physical_vehicle_id": PHYSICAL_VEHICLE_ID,
            "center_x": fmt(cx),
            "center_y": fmt(cy),
            "body_width_px": b.get("width_px", ""),
            "body_height_px": b.get("height_px", ""),
            "body_length_m_grid": b.get("width_m_grid", ""),
            "body_width_m_grid": b.get("height_m_grid", ""),
            "motion_tangent_image_deg": h.get("motion_heading_directed_deg", ""),
            "motion_tangent_uncertainty_deg": h.get("history_vs_symmetric_axial_difference_deg", h.get("fit_residual_px", "")),
            "body_axis_proxy_deg": a.get("body_axis_proxy_deg", b.get("angle_deg", "")),
            "body_axis_proxy_source": "E0_R2_two_sided_trajectory_body_axis_proxy",
            "body_axis_proxy_uncertainty_deg": a.get("aspect_angle_ci_width_deg", ""),
            "local_range_axis_image_deg": a.get("local_range_axis_deg", ""),
            "relative_aspect_angle_deg": a.get("relative_aspect_angle_deg", ""),
            "aspect_domain_status": aspect_domain_status,
            "aspect_observability_status": a.get("aspect_observability_status", ""),
            "absolute_range_from_radar_m": fmt(absolute_range),
            "absolute_azimuth_deg": fmt(absolute_azimuth),
            "gt_visible_fraction": m.get("gt_visible_fraction", ""),
            "gt_mask_contact_ratio": m.get("gt_mask_contact_ratio", ""),
            "gt_boundary_contact_ratio": m.get("gt_boundary_contact_ratio", ""),
            "mask_observability_status": "HIGH_OBSERVABILITY_MASK_INNER" if high_observable else "MASK_OR_DOMAIN_LIMITED",
            "planned_anchor_class": planned_class,
            "plan_stage_input_role": "geometry_identity_mask_metadata_aspect_proxy_only",
        }
        rows.append(row)
    return rows


def segment_rows(frame_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    segments: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    for row in frame_rows:
        frame = parse_int(row["sar_frame"])
        if not current:
            current = [row]
            continue
        prev = current[-1]
        same_class = row["planned_anchor_class"] == prev["planned_anchor_class"]
        close_frame = frame - parse_int(prev["sar_frame"]) <= MAXIMUM_ALLOWED_FRAME_GAP
        if same_class and close_frame:
            current.append(row)
        else:
            segments.append(current)
            current = [row]
    if current:
        segments.append(current)

    out: list[dict[str, Any]] = []
    class_counter: dict[str, int] = {"A": 0, "B": 0, "C": 0}
    for seg in segments:
        first = seg[0]
        segment_class = str(first["planned_anchor_class"])[0]
        class_counter[segment_class] += 1
        frames = [parse_int(row["sar_frame"]) for row in seg]
        ranges = [parse_float(row["absolute_range_from_radar_m"]) for row in seg]
        azimuths = [parse_float(row["absolute_azimuth_deg"]) for row in seg]
        aspects = [parse_float(row["relative_aspect_angle_deg"]) for row in seg]
        centers = [(parse_float(row["center_x"]), parse_float(row["center_y"])) for row in seg]
        center_motion = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(centers, centers[1:])) * RADIAL_GRID_SPACING_M_PER_PX
        range_change = max(ranges) - min(ranges) if ranges else 0.0
        az_change = max(azimuths) - min(azimuths) if azimuths else 0.0
        aspect_span = max(aspects) - min(aspects) if aspects else 0.0
        if segment_class == "A":
            readiness = (
                "ANCHOR_SEGMENT_READY"
                if len(seg) >= MINIMUM_ANCHOR_SEGMENT_LENGTH
                and aspect_span >= MINIMUM_OBSERVABLE_ASPECT_SPAN_DEG
                and (range_change >= MINIMUM_RANGE_OR_AZIMUTH_CHANGE_M or center_motion >= MINIMUM_RANGE_OR_AZIMUTH_CHANGE_M)
                else "ANCHOR_SEGMENT_WEAK"
            )
        elif segment_class == "B":
            readiness = "RESERVED_FOR_MASK_TRANSITION_NEXT_STAGE"
        else:
            readiness = "STRESS_OR_OUT_OF_DOMAIN_ONLY"
        out.append(
            {
                "anchor_segment_id": f"{segment_class}{class_counter[segment_class]:03d}",
                "anchor_segment_class": first["planned_anchor_class"],
                "physical_vehicle_id": PHYSICAL_VEHICLE_ID,
                "split_role": first["split"],
                "start_sar_frame": min(frames),
                "end_sar_frame": max(frames),
                "frame_count": len(seg),
                "frame_ids": ";".join(str(f) for f in frames),
                "maximum_allowed_frame_gap": MAXIMUM_ALLOWED_FRAME_GAP,
                "minimum_anchor_segment_length": MINIMUM_ANCHOR_SEGMENT_LENGTH,
                "minimum_observable_aspect_span": fmt(MINIMUM_OBSERVABLE_ASPECT_SPAN_DEG),
                "minimum_range_or_azimuth_change": fmt(MINIMUM_RANGE_OR_AZIMUTH_CHANGE_M),
                "range_min_m": fmt(min(ranges) if ranges else 0.0),
                "range_max_m": fmt(max(ranges) if ranges else 0.0),
                "range_change_m": fmt(range_change),
                "azimuth_min_deg": fmt(min(azimuths) if azimuths else 0.0),
                "azimuth_max_deg": fmt(max(azimuths) if azimuths else 0.0),
                "azimuth_change_deg": fmt(az_change),
                "relative_aspect_min_deg": fmt(min(aspects) if aspects else 0.0),
                "relative_aspect_max_deg": fmt(max(aspects) if aspects else 0.0),
                "relative_aspect_span_deg": fmt(aspect_span),
                "center_motion_path_m": fmt(center_motion),
                "in_calibration_aspect_domain_frames": sum(row["aspect_domain_status"] == "IN_CALIBRATION_ASPECT_DOMAIN" for row in seg),
                "out_of_calibration_aspect_domain_frames": sum(row["aspect_domain_status"] == "OUT_OF_CALIBRATION_ASPECT_DOMAIN" for row in seg),
                "anchor_readiness": readiness,
                "selection_basis": "pre_registered_identity_mask_geometry_aspect_not_sar_response",
            }
        )
    return out


def build_pair_plan(frame_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates = [row for row in frame_rows if row["mask_observability_status"] == "HIGH_OBSERVABILITY_MASK_INNER"]
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            frame_a = parse_int(a["sar_frame"])
            frame_b = parse_int(b["sar_frame"])
            dt = frame_b - frame_a
            if dt <= 0:
                continue
            aspect_diff = abs(parse_float(b["relative_aspect_angle_deg"]) - parse_float(a["relative_aspect_angle_deg"]))
            range_diff = abs(parse_float(b["absolute_range_from_radar_m"]) - parse_float(a["absolute_range_from_radar_m"]))
            pair_type = ""
            if dt < PAIR_MIN_TIME_SEPARATION_FRAMES:
                pair_type = "time_nearby_control"
            elif aspect_diff <= PAIR_ASPECT_SAME_DEG and range_diff <= PAIR_SIMILAR_RANGE_M:
                pair_type = "same_aspect_similar_range"
            elif aspect_diff >= PAIR_ASPECT_DIFFERENT_DEG and range_diff <= PAIR_SIMILAR_RANGE_M:
                pair_type = "different_aspect_similar_range"
            elif aspect_diff <= PAIR_ASPECT_SAME_DEG and range_diff > PAIR_SIMILAR_RANGE_M:
                pair_type = "same_aspect_different_range"
            elif dt >= 20:
                pair_type = "time_distant_control"
            if not pair_type:
                continue
            counts[pair_type] = counts.get(pair_type, 0) + 1
            if counts[pair_type] > PAIR_MAX_ROWS_PER_TYPE:
                continue
            rows.append(
                {
                    "pair_plan_id": f"E0R3_PAIR_{len(rows) + 1:04d}",
                    "pair_type": pair_type,
                    "physical_vehicle_id": PHYSICAL_VEHICLE_ID,
                    "frame_a": frame_a,
                    "frame_b": frame_b,
                    "split_a": a["split"],
                    "split_b": b["split"],
                    "aspect_difference_deg": fmt(aspect_diff),
                    "range_difference_m": fmt(range_diff),
                    "time_difference_frames": dt,
                    "aspect_same_threshold_deg": fmt(PAIR_ASPECT_SAME_DEG),
                    "aspect_different_threshold_deg": fmt(PAIR_ASPECT_DIFFERENT_DEG),
                    "similar_range_threshold_m": fmt(PAIR_SIMILAR_RANGE_M),
                    "minimum_time_separation_frames": PAIR_MIN_TIME_SEPARATION_FRAMES,
                    "pair_selection_basis": "pre_registered_aspect_range_time_only_no_sar_response",
                    "response_fields_reserved_for_evaluate": "energy_centroid_difference_m;peak_position_difference_m;support_width_difference_m;near_far_ratio_difference;component_layout_difference_deg",
                }
            )
    for pair_type in [
        "same_aspect_similar_range",
        "different_aspect_similar_range",
        "same_aspect_different_range",
        "time_nearby_control",
        "time_distant_control",
    ]:
        rows.append(
            {
                "pair_plan_id": f"SUMMARY_{pair_type}",
                "pair_type": "summary",
                "physical_vehicle_id": PHYSICAL_VEHICLE_ID,
                "frame_a": "",
                "frame_b": "",
                "split_a": "",
                "split_b": "",
                "aspect_difference_deg": "",
                "range_difference_m": "",
                "time_difference_frames": "",
                "aspect_same_threshold_deg": fmt(PAIR_ASPECT_SAME_DEG),
                "aspect_different_threshold_deg": fmt(PAIR_ASPECT_DIFFERENT_DEG),
                "similar_range_threshold_m": fmt(PAIR_SIMILAR_RANGE_M),
                "minimum_time_separation_frames": PAIR_MIN_TIME_SEPARATION_FRAMES,
                "pair_selection_basis": f"raw_count={counts.get(pair_type, 0)};stored_count={sum(1 for row in rows if row.get('pair_type') == pair_type)}",
                "response_fields_reserved_for_evaluate": "NOT_EVALUABLE if required counterpart count is zero",
            }
        )
    return rows


def write_plan_seal(output_map: Mapping[str, Path], frame_rows: Sequence[Mapping[str, Any]], segments: Sequence[Mapping[str, Any]], pair_rows: Sequence[Mapping[str, Any]]) -> None:
    branch = git_output(["branch", "--show-current"])
    head = git_output(["rev-parse", "HEAD"])
    divergence = git_output(["rev-list", "--left-right", "--count", f"HEAD...origin/{BRANCH}"])
    a_count = sum(str(row["anchor_segment_id"]).startswith("A") for row in segments)
    same_count = sum(row.get("pair_type") == "same_aspect_similar_range" for row in pair_rows)
    diff_count = sum(row.get("pair_type") == "different_aspect_similar_range" for row in pair_rows)
    input_paths = [R1_UNIQUE_GT, R1_AXIAL_HEADING, E0_R1_REGION_MANIFEST, E0_MASK_AUDIT, E0_R2_ASPECT, E0_R2_PROTOCOL, PROTOCOL]
    input_digest = hashlib.sha256()
    for path in input_paths:
        input_digest.update(rel(path).encode("utf-8"))
        input_digest.update(sha256_file(path).encode("utf-8"))
    rows: list[dict[str, Any]] = [
        {"seal_item": "WORKTREE_BRANCH_VALID", "status": "PASS" if branch == BRANCH else "FAIL", "evidence": branch, "path": "", "sha256": "", "row_count": "", "notes": ""},
        {"seal_item": "EXPECTED_START_COMMIT_VALID", "status": "PASS" if head == START_COMMIT else "FAIL", "evidence": head, "path": "", "sha256": "", "row_count": "", "notes": ""},
        {"seal_item": "LOCAL_REMOTE_SYNC_AT_PLAN", "status": "PASS" if divergence == "0\t0" else "FAIL", "evidence": divergence, "path": "", "sha256": "", "row_count": "", "notes": ""},
        {"seal_item": "PLAN_STAGE_DOES_NOT_READ_SAR_INTENSITY", "status": "PASS", "evidence": "true", "path": "", "sha256": "", "row_count": "", "notes": "No SAR gray path is opened in this script."},
        {"seal_item": "PLAN_STAGE_DOES_NOT_READ_E0_R2_MEASUREMENT_OUTCOMES", "status": "PASS", "evidence": "true", "path": "", "sha256": "", "row_count": "", "notes": "Only e0_r2_relative_aspect_timeline is read; descriptors/gates/response_index are not read."},
        {"seal_item": "ANCHOR_SEGMENTS_PRE_REGISTERED", "status": "PASS" if a_count > 0 else "FAIL", "evidence": f"A={a_count};segments={len(segments)};frames={len(frame_rows)}", "path": "", "sha256": "", "row_count": "", "notes": ""},
        {"seal_item": "ASPECT_MATCHED_PAIR_PLAN_PRE_REGISTERED", "status": "PASS" if same_count > 0 and diff_count > 0 else "PARTIAL", "evidence": f"same_aspect={same_count};different_aspect={diff_count};range_threshold_m={PAIR_SIMILAR_RANGE_M}", "path": "", "sha256": "", "row_count": "", "notes": ""},
        {"seal_item": "ABSOLUTE_RANGE_USES_RADAR_FAN_CENTER", "status": "PASS", "evidence": f"sar_fan_center=({FAN_CENTER_X},{FAN_CENTER_Y});spacing={RADIAL_GRID_SPACING_M_PER_PX}", "path": "", "sha256": "", "row_count": "", "notes": ""},
        {"seal_item": "MOTION_TANGENT_SEPARATED_FROM_BODY_AXIS", "status": "PASS", "evidence": "motion_tangent_image_deg and body_axis_proxy_deg are separate fields", "path": "", "sha256": "", "row_count": "", "notes": ""},
        {"seal_item": "NO_RESPONSE_INDEX", "status": "PASS", "evidence": "response_index not present in E0-R3 plan fields", "path": "", "sha256": "", "row_count": "", "notes": ""},
        {"seal_item": "PLAN_INPUT_BUNDLE_SHA256", "status": "SEALED", "evidence": input_digest.hexdigest(), "path": "", "sha256": "", "row_count": "", "notes": "Allowed geometry/mask/aspect/protocol inputs only."},
    ]
    for key, path in output_map.items():
        if key == "anchor_plan_seal":
            continue
        rows.append(
            {
                "seal_item": f"ARTIFACT_{key}",
                "status": "SEALED",
                "evidence": key,
                "path": rel(path),
                "sha256": sha256_file(path),
                "row_count": row_count(path),
                "notes": "plan artifact",
            }
        )
    write_csv(output_map["anchor_plan_seal"], rows, PLAN_SEAL_FIELDS)


def run_plan(output_map: Mapping[str, Path] = OUTPUTS) -> None:
    inputs = load_plan_inputs()
    frame_rows = build_frame_rows(inputs)
    segments = segment_rows(frame_rows)
    pair_rows = build_pair_plan(frame_rows)
    mask_rows = [
        {
            "sar_frame": row["sar_frame"],
            "split": row["split"],
            "physical_vehicle_id": row["physical_vehicle_id"],
            "gt_visible_fraction": row["gt_visible_fraction"],
            "gt_mask_contact_ratio": row["gt_mask_contact_ratio"],
            "gt_boundary_contact_ratio": row["gt_boundary_contact_ratio"],
            "mask_observability_status": row["mask_observability_status"],
            "planned_anchor_class": row["planned_anchor_class"],
            "mask_metadata_source": rel(E0_MASK_AUDIT),
            "plan_stage_does_not_read_sar_intensity": "true",
        }
        for row in frame_rows
    ]
    write_csv(output_map["mask_observability_timeline"], mask_rows, MASK_FIELDS)
    write_csv(output_map["body_axis_proxy_timeline"], frame_rows, BODY_AXIS_FIELDS)
    write_csv(output_map["anchor_segment_manifest"], segments, ANCHOR_FIELDS)
    write_csv(output_map["aspect_matched_pair_plan"], pair_rows, PAIR_PLAN_FIELDS)
    write_plan_seal(output_map, frame_rows, segments, pair_rows)
    print(f"E0_R3 plan complete: frames={len(frame_rows)} segments={len(segments)} pairs={len(pair_rows)}")


def verify_plan(output_map: Mapping[str, Path] = OUTPUTS) -> None:
    seal = read_csv(output_map["anchor_plan_seal"])
    failures = []
    for row in seal:
        if row.get("status") == "FAIL":
            failures.append(f"{row['seal_item']}={row.get('evidence','')}")
        if row.get("path") and row.get("sha256"):
            path = REPO_ROOT / row["path"]
            if not path.exists():
                failures.append(f"missing:{row['path']}")
            elif sha256_file(path) != row["sha256"]:
                failures.append(f"sha_mismatch:{row['path']}")
    required = {
        "PLAN_STAGE_DOES_NOT_READ_SAR_INTENSITY",
        "PLAN_STAGE_DOES_NOT_READ_E0_R2_MEASUREMENT_OUTCOMES",
        "ANCHOR_SEGMENTS_PRE_REGISTERED",
        "ABSOLUTE_RANGE_USES_RADAR_FAN_CENTER",
        "NO_RESPONSE_INDEX",
    }
    by_gate = {row["seal_item"]: row["status"] for row in seal}
    missing = sorted(gate for gate in required if by_gate.get(gate) != "PASS")
    failures.extend(f"required_gate_not_pass:{gate}" for gate in missing)
    if failures:
        raise SystemExit("E0_R3_PLAN_SEAL_VALID=FAIL " + ";".join(failures))
    print("E0_R3_PLAN_SEAL_VALID=PASS")


MASK_FIELDS = [
    "sar_frame",
    "split",
    "physical_vehicle_id",
    "gt_visible_fraction",
    "gt_mask_contact_ratio",
    "gt_boundary_contact_ratio",
    "mask_observability_status",
    "planned_anchor_class",
    "mask_metadata_source",
    "plan_stage_does_not_read_sar_intensity",
]

BODY_AXIS_FIELDS = [
    "pair_id",
    "sar_frame",
    "timestamp_or_sequence_index",
    "split",
    "physical_vehicle_id",
    "center_x",
    "center_y",
    "body_width_px",
    "body_height_px",
    "body_length_m_grid",
    "body_width_m_grid",
    "motion_tangent_image_deg",
    "motion_tangent_uncertainty_deg",
    "body_axis_proxy_deg",
    "body_axis_proxy_source",
    "body_axis_proxy_uncertainty_deg",
    "local_range_axis_image_deg",
    "relative_aspect_angle_deg",
    "aspect_domain_status",
    "aspect_observability_status",
    "absolute_range_from_radar_m",
    "absolute_azimuth_deg",
    "gt_visible_fraction",
    "gt_mask_contact_ratio",
    "gt_boundary_contact_ratio",
    "mask_observability_status",
    "planned_anchor_class",
    "plan_stage_input_role",
]

ANCHOR_FIELDS = [
    "anchor_segment_id",
    "anchor_segment_class",
    "physical_vehicle_id",
    "split_role",
    "start_sar_frame",
    "end_sar_frame",
    "frame_count",
    "frame_ids",
    "maximum_allowed_frame_gap",
    "minimum_anchor_segment_length",
    "minimum_observable_aspect_span",
    "minimum_range_or_azimuth_change",
    "range_min_m",
    "range_max_m",
    "range_change_m",
    "azimuth_min_deg",
    "azimuth_max_deg",
    "azimuth_change_deg",
    "relative_aspect_min_deg",
    "relative_aspect_max_deg",
    "relative_aspect_span_deg",
    "center_motion_path_m",
    "in_calibration_aspect_domain_frames",
    "out_of_calibration_aspect_domain_frames",
    "anchor_readiness",
    "selection_basis",
]

PAIR_PLAN_FIELDS = [
    "pair_plan_id",
    "pair_type",
    "physical_vehicle_id",
    "frame_a",
    "frame_b",
    "split_a",
    "split_b",
    "aspect_difference_deg",
    "range_difference_m",
    "time_difference_frames",
    "aspect_same_threshold_deg",
    "aspect_different_threshold_deg",
    "similar_range_threshold_m",
    "minimum_time_separation_frames",
    "pair_selection_basis",
    "response_fields_reserved_for_evaluate",
]

PLAN_SEAL_FIELDS = ["seal_item", "status", "evidence", "path", "sha256", "row_count", "notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "verify-plan"])
    args = parser.parse_args()
    if args.command == "plan":
        run_plan()
    elif args.command == "verify-plan":
        verify_plan()


if __name__ == "__main__":
    main()
