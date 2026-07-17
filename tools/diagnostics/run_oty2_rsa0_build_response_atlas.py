#!/usr/bin/env python3
from __future__ import annotations

"""Build the RSA0 v0 manual-review-seeded response atlas manifests."""

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from oty2_s1x_common import (
    CONFIG_DIR,
    MANIFEST_DIR,
    REPORT_DIR,
    REPO_ROOT,
    aggregate_file_hash,
    load_json,
    parse_rotated_bbox,
    read_csv,
    read_gray,
    row_hash,
    sha256_file,
    verify_git_gate,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = CONFIG_DIR / "oty2_rsa0_response_atlas.json"
FRAMES_CSV = MANIFEST_DIR / "oty2_rsa0_response_atlas_frames.csv"
REGIONS_CSV = MANIFEST_DIR / "oty2_rsa0_response_atlas_regions.csv"
SKELETONS_CSV = MANIFEST_DIR / "oty2_rsa0_response_skeletons.csv"
BACKGROUND_CSV = MANIFEST_DIR / "oty2_rsa0_background_controls.csv"
REVIEW_REPORT = REPORT_DIR / "oty2_rsa0_response_atlas_direct_visual_review_20260717.md"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_response_atlas_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO_ROOT / path


def frame_map(rows: list[dict[str, str]], scene: str, vehicle_id: str) -> dict[int, dict[str, str]]:
    return {
        int(row["sar_frame_index"]): row
        for row in rows
        if row["scene"] == scene and row["canonical_vehicle_id"] == vehicle_id
    }


def points_to_text(points: list[tuple[float, float]]) -> str:
    return ";".join(f"{x:.3f},{y:.3f}" for x, y in points)


def rect_points(cx: float, cy: float, box: list[float]) -> list[tuple[float, float]]:
    x1, y1, x2, y2 = box
    return [(cx + x1, cy + y1), (cx + x2, cy + y1), (cx + x2, cy + y2), (cx + x1, cy + y2)]


def polyline_length(points: list[tuple[float, float]]) -> float:
    length = 0.0
    for left, right in zip(points[:-1], points[1:]):
        length += float(np.hypot(right[0] - left[0], right[1] - left[1]))
    return length


def display_u8(image: np.ndarray) -> np.ndarray:
    return np.asarray(np.rint(np.clip(image.astype(np.float32) / 85.0, 0.0, 1.0) * 255.0), dtype=np.uint8)


def crop_center(image: np.ndarray, center_x: float, center_y: float, width: int = 460, height: int = 300) -> tuple[np.ndarray, int, int]:
    x1 = int(round(center_x - width / 2))
    y1 = int(round(center_y - height / 2))
    out = np.zeros((height, width), dtype=image.dtype)
    src_x1 = max(0, x1)
    src_y1 = max(0, y1)
    src_x2 = min(image.shape[1], x1 + width)
    src_y2 = min(image.shape[0], y1 + height)
    dst_x1 = src_x1 - x1
    dst_y1 = src_y1 - y1
    out[dst_y1 : dst_y1 + src_y2 - src_y1, dst_x1 : dst_x1 + src_x2 - src_x1] = image[src_y1:src_y2, src_x1:src_x2]
    return out, x1, y1


def localize(points: list[tuple[float, float]], x0: int, y0: int) -> np.ndarray:
    return np.asarray([[int(round(x - x0)), int(round(y - y0))] for x, y in points], dtype=np.int32)


def draw_overlay(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    skeleton: list[tuple[float, float]],
    definite: list[tuple[float, float]],
    probable: list[tuple[float, float]],
    background_line: list[tuple[float, float]],
    background_arc: list[tuple[float, float]],
    unresolved: list[tuple[float, float]],
    mixed: list[tuple[float, float]],
    title: str,
    path: Path,
) -> None:
    crop, x0, y0 = crop_center(display_u8(image), center_x, center_y)
    out = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    cv2.polylines(out, [localize(definite, x0, y0)], True, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.polylines(out, [localize(probable, x0, y0)], True, (255, 0, 255), 2, cv2.LINE_AA)
    cv2.polylines(out, [localize(unresolved, x0, y0)], True, (128, 128, 255), 2, cv2.LINE_AA)
    cv2.polylines(out, [localize(mixed, x0, y0)], True, (255, 128, 0), 2, cv2.LINE_AA)
    cv2.polylines(out, [localize(skeleton, x0, y0)], False, (0, 255, 0), 3, cv2.LINE_AA)
    cv2.polylines(out, [localize(background_line, x0, y0)], False, (0, 0, 255), 2, cv2.LINE_AA)
    cv2.polylines(out, [localize(background_arc, x0, y0)], False, (0, 0, 255), 2, cv2.LINE_AA)
    cv2.putText(out, title, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(out, title, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 1, cv2.LINE_AA)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), out):
        raise RuntimeError(f"failed to write {path}")


def append_region(rows: list[dict[str, Any]], base: dict[str, Any], label: str, subtype: str, points: list[tuple[float, float]], confidence: float, notes: str) -> None:
    rows.append({
        **base,
        "label": label,
        "subtype": subtype,
        "geometry_type": "polygon",
        "points": points_to_text(points),
        "confidence": confidence,
        "notes": notes,
    })


def build() -> None:
    args = parse_args()
    config = load_json(args.config)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    sources = config["sources"]
    condition_rows = read_csv(resolve(sources["s1x_optical_condition_frames"]))
    gt_rows = read_csv(resolve(sources["s0_sar_gt_quality_audit"]))
    template = config["geometry_template"]
    output_root = Path(config["output_root"])

    frame_rows: list[dict[str, Any]] = []
    region_rows: list[dict[str, Any]] = []
    skeleton_rows: list[dict[str, Any]] = []
    background_rows: list[dict[str, Any]] = []
    report_lines = [
        "# OTY2-RSA0 Response Atlas Direct Visual Review",
        "",
        "Date: `2026-07-17`",
        "",
        "This review records the v0 manual-review-seeded response atlas. It is conservative and non-rectangular. GT is used only for research neighbourhood context, not as a response mask.",
        "",
    ]

    for window in config["windows"]:
        scene = window["scene"]
        vehicle_id = window["vehicle_id"]
        condition_by_frame = frame_map(condition_rows, scene, vehicle_id)
        gt_by_frame = frame_map(gt_rows, scene, vehicle_id)
        report_lines.extend([f"## {window['case_id']}", "", window["review_note"], ""])
        for frame in window["keyframes"]:
            condition = condition_by_frame[int(frame)]
            gt = gt_by_frame[int(frame)]
            image = read_gray(Path(condition["sar_gray_path"]))
            cx, cy, _width, _height, _angle = parse_rotated_bbox(gt["bbox"])
            y = cy + float(window["skeleton_y_offsets"][str(frame)])
            skeleton = [(cx + float(xoff), y) for xoff in template["skeleton_x_offsets"]]
            definite = rect_points(cx, y, [min(template["skeleton_x_offsets"]) - 6, -template["definite_half_height"], max(template["skeleton_x_offsets"]) + 6, template["definite_half_height"]])
            probable = rect_points(cx, cy, template["probable_upper_component"])
            support = rect_points(cx, cy, template["support_region"])
            background_line = [(cx + template["vertical_background"][0], cy + template["vertical_background"][1]), (cx + template["vertical_background"][2], cy + template["vertical_background"][3])]
            background_arc = [(cx + template["fan_arc_background"][0], cy + template["fan_arc_background"][1]), (cx, cy + 64), (cx + template["fan_arc_background"][2], cy + template["fan_arc_background"][3])]
            mixed = rect_points(cx, cy, template["mixed_region"])
            unresolved = rect_points(cx, cy, template["unresolved_region"])
            overlay_path = output_root / window["case_id"] / f"{window['case_id'].lower()}_{frame}_atlas_overlay.png"
            draw_overlay(image, cx, cy, skeleton, definite, probable, background_line, background_arc, unresolved, mixed, f"{window['case_id']} SAR {frame}", overlay_path)

            base = {
                "atlas_version": config["version"],
                "window_id": window["window_id"],
                "case_id": window["case_id"],
                "scene": scene,
                "canonical_vehicle_id": vehicle_id,
                "sar_frame": frame,
                "coordinate_system": "sar_display_px",
                "source_role": "manual_direct_visual_review_seeded",
                "review_status": "directly_reviewed_by_codex",
            }
            frame_rows.append({
                **base,
                "keyframe_role": "manual_keyframe",
                "uniform_control": "true" if frame in window["uniform_control_frames"] else "false",
                "sar_gray_path": condition["sar_gray_path"],
                "gt_context_role": "research_identity_neighbourhood_not_response_mask",
                "overlay_path": str(overlay_path),
                "overlay_sha256": sha256_file(overlay_path),
                "notes": "conservative v0 geometry; requires future human correction before training or propagation",
            })
            skeleton_rows.append({
                **base,
                "label": "MAIN_RESPONSE_SKELETON",
                "geometry_type": "polyline",
                "points": points_to_text(skeleton),
                "length_px": f"{polyline_length(skeleton):.3f}",
                "confidence": 1.0,
                "notes": "main near-horizontal response relation; not a vehicle centre",
            })
            skeleton_rows.append({
                **base,
                "label": "HIGH_CONFIDENCE_RESPONSE_SEED",
                "geometry_type": "sparse_scribble",
                "points": points_to_text(skeleton[1:4]),
                "length_px": f"{polyline_length(skeleton[1:4]):.3f}",
                "confidence": 1.0,
                "notes": "minimal central seed inside definite response",
            })
            append_region(region_rows, base, "DEFINITE_TARGET_RESPONSE", "thin_main_band", definite, 1.0, "thin conservative polygon around main skeleton")
            append_region(region_rows, base, "PROBABLE_TARGET_RESPONSE", "upper_or_intermediate_component", probable, 0.5, "possible local component; excluded from hard positive")
            append_region(region_rows, base, "RESPONSE_SUPPORT_REGION", "local_context_container", support, 0.25, "context container only; not positive mask")
            append_region(region_rows, base, "UNRESOLVED", "right_mixed_neighbourhood", unresolved, 0.25, "target/background ownership ambiguous")
            append_region(region_rows, base, "MIXED_STRUCTURE", "right_side_target_background_mix", mixed, 0.25, "mixed target-like and background-like structure")
            background_rows.append({
                **base,
                "label": "BACKGROUND_STRUCTURE",
                "subtype": "vertical_line",
                "geometry_type": "polyline",
                "points": points_to_text(background_line),
                "confidence": 0.0,
                "notes": "vertical bright structure retained as background counterexample",
            })
            background_rows.append({
                **base,
                "label": "BACKGROUND_STRUCTURE",
                "subtype": "fan_arc",
                "geometry_type": "polyline",
                "points": points_to_text(background_arc),
                "confidence": 0.0,
                "notes": "fan-arc structure retained as background counterexample",
            })
            report_lines.extend([
                f"### {window['case_id']} SAR {frame}",
                "",
                f"- Overlay: `{overlay_path}`",
                "- Main response: conservative near-horizontal skeleton, recorded as object relation rather than centre.",
                "- Definite response: thin band around the skeleton only.",
                "- Probable response: upper/local component retained separately.",
                "- Background: vertical line and fan arc retained as counterexamples.",
                "- Unresolved/mixed: right-side neighbourhood is not forced positive or negative.",
                "- Risk: geometry is v0 manual-review-seeded and must be corrected before any propagation prototype.",
                "",
            ])

    write_csv(FRAMES_CSV, frame_rows)
    write_csv(REGIONS_CSV, region_rows)
    write_csv(SKELETONS_CSV, skeleton_rows)
    write_csv(BACKGROUND_CSV, background_rows)
    REVIEW_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

    output_paths = [FRAMES_CSV, REGIONS_CSV, SKELETONS_CSV, BACKGROUND_CSV, REVIEW_REPORT]
    input_paths = [args.config, *[resolve(path_text) for path_text in sources.values()]]
    summary = {
        "version": config["version"],
        "git": git_state,
        "frame_count": len(frame_rows),
        "region_count": len(region_rows),
        "skeleton_count": len(skeleton_rows),
        "background_control_count": len(background_rows),
        "outputs": {path.name: {"path": str(path), "sha256": sha256_file(path)} for path in output_paths},
        "aggregate_input_sha256": aggregate_file_hash(input_paths),
        "aggregate_output_sha256": aggregate_file_hash(output_paths),
        "frame_row_hash": row_hash(frame_rows),
        "region_row_hash": row_hash(region_rows),
        "skeleton_row_hash": row_hash(skeleton_rows),
        "background_row_hash": row_hash(background_rows),
        "boundary": "v0_manual_review_seeded_atlas_no_representation_scoring_no_training",
    }
    write_json(SUMMARY_JSON, summary)


if __name__ == "__main__":
    build()
