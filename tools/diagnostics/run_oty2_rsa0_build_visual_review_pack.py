#!/usr/bin/env python3
from __future__ import annotations

"""Build RSA0 direct visual review packs for selected short windows."""

import argparse
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from oty2_s1x_common import (
    CONFIG_DIR,
    MANIFEST_DIR,
    REPORT_DIR,
    REPO_ROOT,
    WORKSPACE_ROOT,
    aggregate_file_hash,
    load_json,
    parse_rotated_bbox,
    read_csv,
    read_gray,
    row_hash,
    sha256_file,
    verify_git_gate,
    warp_translation,
    write_csv,
    write_json,
)


DEFAULT_CONFIG = CONFIG_DIR / "oty2_rsa0_visual_review_pack.json"
OUTPUT_MANIFEST = MANIFEST_DIR / "oty2_rsa0_visual_review_pack_manifest.csv"
SUMMARY_JSON = REPORT_DIR / "oty2_rsa0_visual_review_pack_summary_20260717.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO_ROOT / path


def display_u8(image: np.ndarray, display_min: float, display_max: float) -> np.ndarray:
    value = np.asarray(image, dtype=np.float32)
    value = np.clip((value - display_min) / max(1.0, display_max - display_min), 0.0, 1.0)
    return np.asarray(np.rint(value * 255.0), dtype=np.uint8)


def to_bgr(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)


def annotate_text(image: np.ndarray, text: str, origin: tuple[int, int] = (8, 22)) -> np.ndarray:
    out = image.copy()
    cv2.putText(out, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(out, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 1, cv2.LINE_AA)
    return out


def draw_rotated_box(image: np.ndarray, bbox_text: str, color: tuple[int, int, int]) -> np.ndarray:
    out = image.copy()
    cx, cy, width, height, angle = parse_rotated_bbox(bbox_text)
    points = cv2.boxPoints(((cx, cy), (width, height), angle))
    points = np.rint(points).astype(np.int32)
    cv2.polylines(out, [points], True, color, 2, cv2.LINE_AA)
    return out


def draw_proxy_cross(image: np.ndarray, x: float, y: float, color: tuple[int, int, int]) -> np.ndarray:
    out = image.copy()
    cx = int(round(x))
    cy = int(round(y))
    cv2.drawMarker(out, (cx, cy), color, markerType=cv2.MARKER_CROSS, markerSize=22, thickness=2, line_type=cv2.LINE_AA)
    return out


def resize_panel(image: np.ndarray, scale: float) -> np.ndarray:
    width = max(1, int(round(image.shape[1] * scale)))
    height = max(1, int(round(image.shape[0] * scale)))
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)


def montage(panels: list[np.ndarray], cols: int, pad: int = 8, background: int = 20) -> np.ndarray:
    rows = int(math.ceil(len(panels) / cols))
    height = max(panel.shape[0] for panel in panels)
    width = max(panel.shape[1] for panel in panels)
    canvas = np.full((rows * height + (rows + 1) * pad, cols * width + (cols + 1) * pad, 3), background, dtype=np.uint8)
    for index, panel in enumerate(panels):
        row = index // cols
        col = index % cols
        y = pad + row * (height + pad)
        x = pad + col * (width + pad)
        canvas[y : y + panel.shape[0], x : x + panel.shape[1]] = panel
    return canvas


def crop_center(image: np.ndarray, center_x: float, center_y: float, width: int, height: int) -> np.ndarray:
    x1 = int(round(center_x - width / 2))
    y1 = int(round(center_y - height / 2))
    x2 = x1 + width
    y2 = y1 + height
    out = np.zeros((height, width), dtype=image.dtype)
    src_x1 = max(0, x1)
    src_y1 = max(0, y1)
    src_x2 = min(image.shape[1], x2)
    src_y2 = min(image.shape[0], y2)
    dst_x1 = src_x1 - x1
    dst_y1 = src_y1 - y1
    out[dst_y1 : dst_y1 + src_y2 - src_y1, dst_x1 : dst_x1 + src_x2 - src_x1] = image[src_y1:src_y2, src_x1:src_x2]
    return out


def frame_map(rows: list[dict[str, str]], scene: str, vehicle_id: str, start: int, end: int) -> dict[int, dict[str, str]]:
    return {
        int(row["sar_frame_index"]): row
        for row in rows
        if row["scene"] == scene
        and row["canonical_vehicle_id"] == vehicle_id
        and start <= int(row["sar_frame_index"]) <= end
    }


def transport_map(rows: list[dict[str, str]], scene: str, start: int, end: int) -> dict[int, tuple[float, float]]:
    values: dict[int, tuple[float, float]] = {}
    for row in rows:
        if row.get("scene") != scene or row.get("state_mode") != "causal":
            continue
        frame = int(row["sar_frame_index"])
        if start <= frame <= end:
            values[frame] = (float(row["cumulative_dx_px"]), float(row["cumulative_dy_px"]))
    return values


def write_image(path: Path, image: np.ndarray, rows: list[dict[str, Any]], window: dict[str, Any], artifact_type: str, coordinate_system: str, source_role: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(path), image)
    if not ok:
        raise RuntimeError(f"failed to write image: {path}")
    rows.append({
        "window_id": window["window_id"],
        "case_id": window["case_id"],
        "scene": window["scene"],
        "canonical_vehicle_id": window["vehicle_id"],
        "sar_frame_start": window["sar_frame_start"],
        "sar_frame_end": window["sar_frame_end"],
        "artifact_type": artifact_type,
        "path": str(path),
        "sha256": sha256_file(path),
        "coordinate_system": coordinate_system,
        "source_role": source_role,
        "review_status": "requires_direct_codex_visual_review",
    })


def write_video(path: Path, frames: list[np.ndarray], fps: float, rows: list[dict[str, Any]], window: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"failed to open video writer: {path}")
    for frame in frames:
        writer.write(frame)
    writer.release()
    rows.append({
        "window_id": window["window_id"],
        "case_id": window["case_id"],
        "scene": window["scene"],
        "canonical_vehicle_id": window["vehicle_id"],
        "sar_frame_start": window["sar_frame_start"],
        "sar_frame_end": window["sar_frame_end"],
        "artifact_type": "continuous_mp4",
        "path": str(path),
        "sha256": sha256_file(path),
        "coordinate_system": "sar_display_px",
        "source_role": "direct_sar_grayscale_sequence",
        "review_status": "requires_direct_codex_visual_review",
    })


def build_window(
    window: dict[str, Any],
    config: dict[str, Any],
    condition_rows: list[dict[str, str]],
    gt_rows: list[dict[str, str]],
    transport_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, Any]],
) -> None:
    display = config["display"]
    out_dir = Path(config["output_root"]) / window["case_id"]
    scene = window["scene"]
    vehicle_id = window["vehicle_id"]
    start = int(window["sar_frame_start"])
    end = int(window["sar_frame_end"])
    frames = list(range(start, end + 1))
    prefix = str(window["case_id"]).lower()
    condition_by_frame = frame_map(condition_rows, scene, vehicle_id, start, end)
    gt_by_frame = frame_map(gt_rows, scene, vehicle_id, start, end)
    transport_by_frame = transport_map(transport_rows, scene, start, end)
    base_transport = transport_by_frame.get(start, (0.0, 0.0))

    raw_images: dict[int, np.ndarray] = {}
    disp_images: dict[int, np.ndarray] = {}
    raw_panels: list[np.ndarray] = []
    overlay_panels: list[np.ndarray] = []
    stabilized_panels: list[np.ndarray] = []
    gt_crops: list[np.ndarray] = []
    proxy_crops: list[np.ndarray] = []
    gt_crop_gray: list[np.ndarray] = []
    proxy_crop_gray: list[np.ndarray] = []
    video_frames: list[np.ndarray] = []
    crop_width = int(display["crop_width"])
    crop_height = int(display["crop_height"])

    for frame in frames:
        condition = condition_by_frame[frame]
        gt = gt_by_frame[frame]
        raw = read_gray(Path(condition["sar_gray_path"]))
        raw_images[frame] = raw
        disp = display_u8(raw, float(display["display_min"]), float(display["display_max"]))
        disp_images[frame] = disp
        bgr = to_bgr(disp)
        raw_panels.append(annotate_text(resize_panel(bgr, float(display["montage_scale"])), f"SAR {frame}"))
        overlay = draw_rotated_box(bgr, gt["bbox"], (0, 255, 255))
        overlay = draw_proxy_cross(overlay, float(condition["predicted_center_x_px"]), float(condition["predicted_center_y_px"]), (255, 0, 255))
        overlay_panels.append(annotate_text(resize_panel(overlay, float(display["montage_scale"])), f"GT/proxy {frame}"))
        dx, dy = transport_by_frame.get(frame, base_transport)
        stabilized = warp_translation(disp, -(dx - base_transport[0]), -(dy - base_transport[1]), cv2.INTER_LINEAR)
        stabilized_panels.append(annotate_text(resize_panel(to_bgr(stabilized), float(display["montage_scale"])), f"world {frame}"))
        bbox = parse_rotated_bbox(gt["bbox"])
        gt_crop = crop_center(disp, bbox[0], bbox[1], crop_width, crop_height)
        proxy_crop = crop_center(disp, float(condition["predicted_center_x_px"]), float(condition["predicted_center_y_px"]), crop_width, crop_height)
        gt_crop_gray.append(gt_crop)
        proxy_crop_gray.append(proxy_crop)
        gt_crops.append(annotate_text(to_bgr(gt_crop), f"GT aligned {frame}"))
        proxy_crops.append(annotate_text(to_bgr(proxy_crop), f"proxy aligned {frame}"))
        video_frames.append(resize_panel(overlay, 0.35))

    write_image(out_dir / f"{prefix}_raw_full_frame_montage.png", montage(raw_panels, cols=7), manifest_rows, window, "raw_full_frame_montage", "sar_display_px", "direct_sar_grayscale")
    write_image(out_dir / f"{prefix}_raw_gt_proxy_overlay_montage.png", montage(overlay_panels, cols=7), manifest_rows, window, "raw_gt_proxy_overlay_montage", "sar_display_px", "gt_context_and_optical_proxy_context")
    write_image(out_dir / f"{prefix}_world_stabilized_montage.png", montage(stabilized_panels, cols=7), manifest_rows, window, "world_stabilized_montage", "world_stabilized_px", "s1d0_background_transport_display_only")
    write_image(out_dir / f"{prefix}_gt_center_aligned_montage.png", montage(gt_crops, cols=7), manifest_rows, window, "gt_center_aligned_montage", "research_gt_conditioned_px", "RESEARCH_ORACLE_COORDINATE_ONLY")
    write_image(out_dir / f"{prefix}_optical_proxy_center_aligned_montage.png", montage(proxy_crops, cols=7), manifest_rows, window, "optical_proxy_center_aligned_montage", "optical_proxy_conditioned_px", "optical_proxy_context")
    write_video(out_dir / f"{prefix}_gt_proxy_overlay.mp4", video_frames, 6.0, manifest_rows, window)

    gt_stack = np.stack(gt_crop_gray).astype(np.float32)
    avg = np.asarray(np.rint(np.mean(gt_stack, axis=0)), dtype=np.uint8)
    write_image(out_dir / f"{prefix}_gt_aligned_average.png", to_bgr(avg), manifest_rows, window, "trajectory_aligned_average", "research_gt_conditioned_px", "RESEARCH_ORACLE_COORDINATE_ONLY")

    center_y = crop_height // 2
    center_x = crop_width // 2
    strip_h = int(display["strip_half_height"])
    strip_w = int(display["strip_half_width"])
    xt = gt_stack[:, center_y - strip_h : center_y + strip_h + 1, :].mean(axis=1)
    yt = gt_stack[:, :, center_x - strip_w : center_x + strip_w + 1].mean(axis=2)
    xt_img = cv2.resize(display_u8(xt, 0, 255), (crop_width, 240), interpolation=cv2.INTER_NEAREST)
    yt_img = cv2.resize(display_u8(yt.T, 0, 255), (crop_height, 240), interpolation=cv2.INTER_NEAREST)
    write_image(out_dir / f"{prefix}_x_t_gt_center_strip.png", to_bgr(xt_img), manifest_rows, window, "x_t_gt_center_strip", "research_gt_conditioned_px", "RESEARCH_ORACLE_COORDINATE_ONLY")
    write_image(out_dir / f"{prefix}_y_t_gt_center_strip.png", to_bgr(yt_img), manifest_rows, window, "y_t_gt_center_strip", "research_gt_conditioned_px", "RESEARCH_ORACLE_COORDINATE_ONLY")

    diff_panels: list[np.ndarray] = []
    for left, right in zip(frames[:-1], frames[1:]):
        delta = raw_images[right].astype(np.int16) - raw_images[left].astype(np.int16)
        pos = np.clip(delta, 0, 85).astype(np.uint8)
        neg = np.clip(-delta, 0, 85).astype(np.uint8)
        color = np.zeros((*pos.shape, 3), dtype=np.uint8)
        color[:, :, 1] = display_u8(pos, 0, 85)
        color[:, :, 2] = display_u8(neg, 0, 85)
        diff_panels.append(annotate_text(resize_panel(color, float(display["montage_scale"])), f"{left}->{right}"))
    write_image(out_dir / f"{prefix}_positive_negative_change_montage.png", montage(diff_panels, cols=5), manifest_rows, window, "positive_negative_change_montage", "sar_display_px", "direct_sar_grayscale_frame_difference")

    mid = frames[len(frames) // 2]
    phase_specs = [(f"{start}_{mid - 1}", range(start, mid)), (str(mid), range(mid, mid + 1)), (f"{mid + 1}_{end}", range(mid + 1, end + 1))]
    phase_panels: list[np.ndarray] = []
    for name, phase_frames in phase_specs:
        stack = np.stack([disp_images[frame] for frame in phase_frames]).astype(np.float32)
        panel = to_bgr(np.asarray(np.rint(stack.mean(axis=0)), dtype=np.uint8))
        phase_panels.append(annotate_text(resize_panel(panel, 0.35), name))
    write_image(out_dir / f"{prefix}_phase_average_montage.png", montage(phase_panels, cols=3), manifest_rows, window, "phase_average_montage", "sar_display_px", "direct_sar_grayscale_phase_average")

    zoom_panels: list[np.ndarray] = []
    for frame in [start, mid, end]:
        gt = gt_by_frame[frame]
        condition = condition_by_frame[frame]
        bbox = parse_rotated_bbox(gt["bbox"])
        crop = crop_center(disp_images[frame], bbox[0], bbox[1], crop_width, crop_height)
        crop_bgr = annotate_text(to_bgr(crop), f"local GT crop {frame}")
        zoom_panels.append(crop_bgr)
        proxy_crop = crop_center(disp_images[frame], float(condition["predicted_center_x_px"]), float(condition["predicted_center_y_px"]), crop_width, crop_height)
        zoom_panels.append(annotate_text(to_bgr(proxy_crop), f"local proxy crop {frame}"))
    write_image(out_dir / f"{prefix}_local_zoom_review_page.png", montage(zoom_panels, cols=2), manifest_rows, window, "local_zoom_review_page", "mixed_gt_and_optical_proxy_conditioned_px", "direct_review_context")


def main() -> None:
    args = parse_args()
    config = load_json(args.config)
    git_state = verify_git_gate(config["expected_branch"], config["expected_start_head"])
    sources = config["sources"]
    condition_rows = read_csv(resolve(sources["s1x_optical_condition_frames"]))
    gt_rows = read_csv(resolve(sources["s0_sar_gt_quality_audit"]))
    transport_rows = read_csv(resolve(sources["s1d0_causal_transport_diagnostics"]))

    manifest_rows: list[dict[str, Any]] = []
    for window in config["windows"]:
        build_window(window, config, condition_rows, gt_rows, transport_rows, manifest_rows)

    write_csv(OUTPUT_MANIFEST, manifest_rows)
    input_paths = [args.config, *[resolve(path_text) for path_text in sources.values()]]
    summary = {
        "version": config["version"],
        "git": git_state,
        "output_manifest": str(OUTPUT_MANIFEST),
        "output_manifest_sha256": sha256_file(OUTPUT_MANIFEST),
        "artifact_count": len(manifest_rows),
        "artifact_types": sorted({row["artifact_type"] for row in manifest_rows}),
        "output_root": config["output_root"],
        "config_sha256": sha256_file(args.config),
        "aggregate_input_sha256": aggregate_file_hash(input_paths),
        "manifest_row_hash": row_hash(manifest_rows),
        "boundary": "visual_review_pack_only_no_response_atlas_labels_no_representation_scoring",
    }
    write_json(SUMMARY_JSON, summary)


if __name__ == "__main__":
    main()
