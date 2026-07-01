"""Optical-to-SAR transfer panel rendering."""

from __future__ import annotations

from math import cos, radians, sin
from pathlib import Path

from src.geometry.fan_polar import fan_polar_to_display_xy
from src.io.manifest import parse_float, parse_xywh, truthy

from .svg_canvas import FAMILY_COLORS, image_or_placeholder, label, normalize_family, rotated_rect


def _first_candidate(candidates: list[dict[str, str]], family: str) -> dict[str, str] | None:
    for row in candidates:
        if normalize_family(row) == family:
            return row
    return None


def _candidate_float(row: dict[str, str] | None, *keys: str) -> float | None:
    if not row:
        return None
    for key in keys:
        value = parse_float(row.get(key, ""))
        if value is not None:
            return value
    return None


def _range_arc(cx: float, cy: float, radius: float, az: float, spread: float, color: str) -> str:
    start = radians(az - spread)
    end = radians(az + spread)
    x1 = cx + radius * sin(start)
    y1 = cy - radius * cos(start)
    x2 = cx + radius * sin(end)
    y2 = cy - radius * cos(end)
    return (
        f'<path d="M {x1:.2f} {y1:.2f} A {radius:.2f} {radius:.2f} 0 0 1 {x2:.2f} {y2:.2f}" '
        f'fill="none" stroke="{color}" stroke-width="20" opacity="0.26" />'
    )


def render_transfer_panel(
    sample: dict[str, str],
    candidates: list[dict[str, str]],
    scene_config: dict,
    output_path: str | Path,
) -> int:
    optical = scene_config.get("optical_canvas", {"width": 1920, "height": 1080})
    sar = scene_config.get("sar_canvas", {"width": 2308, "height": 1334})
    optical_w = int(optical.get("width", 1920))
    optical_h = int(optical.get("height", 1080))
    sar_w = int(sar.get("width", 2308))
    sar_h = int(sar.get("height", 1334))
    fan = scene_config.get("fan", {})
    fan_cx = float(fan.get("center_x", 1154.0))
    fan_cy = float(fan.get("center_y", 1330.6))
    fan_radius = float(fan.get("radius_px_max", 1332.7))
    factor = _first_candidate(candidates, "factor_inference") or (candidates[0] if candidates else None)
    pred_r = _candidate_float(factor, "pred_r", "pred_r_for_delta", "candidate_r", "r")
    pred_az = _candidate_float(factor, "pred_az", "pred_az_for_delta", "candidate_az", "az")
    pred_cross = _candidate_float(factor, "pred_cross", "pred_cross_for_delta", "candidate_cross", "cross") or 0.0
    sigma = parse_float(sample.get("range_prior_sigma_px")) or float(scene_config.get("default_range_prior_sigma_px", 18.0))

    outer_w = 1680
    outer_h = 760
    left_x = 28
    right_x = 858
    panel_w = 790
    panel_h = 620
    body = [
        f'<rect x="0" y="0" width="{outer_w}" height="{outer_h}" fill="#ffffff" />',
        label(28, 42, f"Optical-to-SAR Transfer Panel: {sample.get('sample_id')} | {sample.get('sample_type')}", 26),
        label(left_x, 82, "optical frame", 20),
        label(right_x, 82, "SAR frame with priors", 20),
        f'<svg x="{left_x}" y="102" width="{panel_w}" height="{panel_h}" viewBox="0 0 {optical_w} {optical_h}">',
        image_or_placeholder(sample.get("optical_frame_path", ""), 0, 0, optical_w, optical_h, "optical image"),
    ]
    optical_box = parse_xywh(sample.get("optical_box_xywh", ""))
    if optical_box:
        ox, oy, ow, oh = optical_box
        body.append(f'<rect x="{ox:.2f}" y="{oy:.2f}" width="{ow:.2f}" height="{oh:.2f}" fill="none" stroke="#00a878" stroke-width="6" />')
    else:
        body.append(label(32, 64, "optical box: missing", 44, "#6b7280"))
    body.extend(
        [
            "</svg>",
            f'<svg x="{right_x}" y="102" width="{panel_w}" height="{panel_h}" viewBox="0 0 {sar_w} {sar_h}">',
            image_or_placeholder(sample.get("sar_frame_path", ""), 0, 0, sar_w, sar_h, "SAR image"),
        ]
    )
    if pred_r is not None and pred_az is not None:
        ray_x = fan_cx + fan_radius * sin(radians(pred_az))
        ray_y = fan_cy - fan_radius * cos(radians(pred_az))
        body.append(f'<line x1="{fan_cx:.2f}" y1="{fan_cy:.2f}" x2="{ray_x:.2f}" y2="{ray_y:.2f}" stroke="#f28c28" stroke-width="7" opacity="0.78" />')
        body.append(_range_arc(fan_cx, fan_cy, max(1.0, pred_r - sigma), pred_az, 5.0, "#f59e0b"))
        body.append(_range_arc(fan_cx, fan_cy, pred_r + sigma, pred_az, 5.0, "#f59e0b"))
        px, py = fan_polar_to_display_xy(pred_r, pred_az, pred_cross, scene_config)
        body.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="12" fill="#f59e0b" />')
    else:
        body.append(label(34, 70, "azimuth ray / range prior: missing", 46, "#6b7280"))

    if factor:
        try:
            body.append(
                rotated_rect(
                    float(factor.get("cx", "")),
                    float(factor.get("cy", "")),
                    float(factor.get("w", "")),
                    float(factor.get("h", "")),
                    float(factor.get("heading", "0") or 0.0),
                    stroke=FAMILY_COLORS["factor_inference"],
                    stroke_width=7,
                    opacity=0.86,
                )
            )
        except ValueError:
            body.append(label(34, 126, "factor prior box: missing geometry", 46, "#6b7280"))
    else:
        body.append(label(34, 126, "factor prior box: missing", 46, "#6b7280"))

    final_box = parse_xywh(sample.get("final_box_xywh", ""))
    if truthy(sample.get("posthoc_debug_enabled")) and final_box:
        fx, fy, fw, fh = final_box
        body.append(
            rotated_rect(
                fx + fw / 2.0,
                fy + fh / 2.0,
                fw,
                fh,
                0.0,
                stroke="#ec4899",
                stroke_width=8,
                dash="20 14",
                opacity=0.92,
            )
        )
        body.append(label(fx, fy - 14, "posthoc_only final debug box", 42, "#ec4899"))
    elif sample.get("final_box_xywh", "").strip():
        body.append(label(34, 184, "final box hidden because posthoc debug is disabled", 42, "#9ca3af"))
    body.extend(
        [
            "</svg>",
            label(left_x, 744, "heading fields remain storage-axis conventions, not vehicle heading.", 16, "#6b7280"),
            label(right_x, 744, "final boxes, if shown, are marked posthoc_only and never alter candidates.", 16, "#6b7280"),
        ]
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{outer_w}" height="{outer_h}" '
        f'viewBox="0 0 {outer_w} {outer_h}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )
    Path(output_path).write_text(svg, encoding="utf-8")
    return 1
