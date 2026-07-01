"""Temporal strip view for neighboring SAR frames."""

from __future__ import annotations

from pathlib import Path

from src.io.manifest import parse_float, parse_int, parse_xywh, truthy

from .svg_canvas import FAMILY_COLORS, first_present, image_or_placeholder, label, normalize_family, rotated_rect


def _frame_path(scene_config: dict, frame_num: int) -> str:
    sar_dir = scene_config.get("paths", {}).get("sar_frames_dir", "")
    if not sar_dir:
        return ""
    return str(Path(sar_dir) / f"{frame_num:06d}.png")


def _candidate_for_family(candidates: list[dict[str, str]], family: str) -> dict[str, str] | None:
    for row in candidates:
        if normalize_family(row) == family:
            return row
    return None


def _draw_candidate(row: dict[str, str] | None, color: str, label_text: str) -> str:
    if not row:
        return ""
    try:
        shape = rotated_rect(
            float(row.get("cx", "")),
            float(row.get("cy", "")),
            float(row.get("w", "")),
            float(row.get("h", "")),
            float(row.get("heading", "0") or 0.0),
            stroke=color,
            stroke_width=8,
            opacity=0.88,
        )
        return shape + label(float(row.get("cx", "0")) + 14, float(row.get("cy", "0")) - 14, label_text, 40, color)
    except ValueError:
        return ""


def render_temporal_strip(
    sample: dict[str, str],
    candidates: list[dict[str, str]],
    scene_config: dict,
    output_path: str | Path,
) -> tuple[int, list[tuple[str, str, str]]]:
    sar_canvas = scene_config.get("sar_canvas", {"width": 2308, "height": 1334})
    sar_w = int(sar_canvas.get("width", 2308))
    sar_h = int(sar_canvas.get("height", 1334))
    center = parse_int(sample.get("sar_frame_num")) or 0
    frame_nums = [max(0, center + delta) for delta in (-2, -1, 0, 1, 2)]
    frame_paths = [_frame_path(scene_config, frame_num) for frame_num in frame_nums]
    missing_temporal = [
        (sample.get("sample_id", ""), f"temporal_sar_frame_{frame_num:06d}", path)
        for frame_num, path in zip(frame_nums, frame_paths)
        if path and not Path(path).exists()
    ]

    outer_w = 1800
    outer_h = 760
    thumb_w = 330
    thumb_h = 250
    body = [
        f'<rect x="0" y="0" width="{outer_w}" height="{outer_h}" fill="#ffffff" />',
        label(28, 42, f"Temporal Strip: {sample.get('sample_id')} | {sample.get('sample_type')}", 26),
        label(28, 66, f"source={sample.get('source_id', '')} | kind={sample.get('source_kind', '')} | fallback_used={sample.get('_fallback_used', 'false')}", 15, "#374151"),
        label(28, 88, "context shell only; not identity-supported track-level temporal evidence", 15, "#6b7280"),
    ]
    factor = _candidate_for_family(candidates, "factor_inference")
    topk = _candidate_for_family(candidates, "factor_topk")
    wedge = _candidate_for_family(candidates, "wedge")
    ray = _candidate_for_family(candidates, "ray")
    signed = _candidate_for_family(candidates, "signed")
    overlay_rows = [
        (factor, FAMILY_COLORS["factor_inference"], "factor prior"),
        (topk, FAMILY_COLORS["factor_topk"], "top-k"),
        (wedge, FAMILY_COLORS["wedge"], "wedge"),
        (ray, FAMILY_COLORS["ray"], "ray"),
        (signed, FAMILY_COLORS["signed"], "signed"),
    ]
    for idx, (frame_num, path) in enumerate(zip(frame_nums, frame_paths)):
        x = 28 + idx * (thumb_w + 24)
        y = 112
        body.append(label(x, y - 12, f"SAR {frame_num:06d}", 18))
        body.append(f'<svg x="{x}" y="{y}" width="{thumb_w}" height="{thumb_h}" viewBox="0 0 {sar_w} {sar_h}">')
        body.append(image_or_placeholder(path, 0, 0, sar_w, sar_h, f"SAR {frame_num:06d}"))
        if frame_num == center:
            for row, color, text in overlay_rows:
                body.append(_draw_candidate(row, color, text))
            final_box = parse_xywh(sample.get("final_box_xywh", ""))
            if truthy(sample.get("posthoc_debug_enabled")) and final_box:
                fx, fy, fw, fh = final_box
                body.append(
                    rotated_rect(
                        fx + fw / 2.0,
                        fy + fh / 2.0,
                        fw,
                        fh,
                        0,
                        stroke="#ec4899",
                        stroke_width=9,
                        dash="24 16",
                    )
                )
                body.append(label(fx, fy - 14, "posthoc final", 42, "#ec4899"))
        body.append("</svg>")

    plot_x = 60
    plot_y = 430
    plot_w = 1660
    plot_h = 250
    body.extend(
        [
            label(plot_x, plot_y - 16, "range offset curve", 20),
            f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" fill="#f9fafb" stroke="#d1d5db" />',
        ]
    )
    deltas: list[tuple[str, float]] = []
    for row in candidates:
        value = parse_float(first_present(row, ("delta_r_from_pred", "delta_r")))
        if value is not None:
            deltas.append((normalize_family(row), value))
    if deltas:
        values = [value for _, value in deltas]
        min_v = min(values)
        max_v = max(values)
        span = max(max_v - min_v, 1.0)
        step = plot_w / max(len(deltas) - 1, 1)
        points = []
        for idx, (family, value) in enumerate(deltas):
            x = plot_x + idx * step
            y = plot_y + plot_h - ((value - min_v) / span) * plot_h
            points.append(f"{x:.2f},{y:.2f}")
            body.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{FAMILY_COLORS.get(family, FAMILY_COLORS["other"])}" />')
        body.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="#111827" stroke-width="3" opacity="0.65" />')
        body.append(label(plot_x, plot_y + plot_h + 28, f"min={min_v:.3f} max={max_v:.3f}; plotted from available delta_r_from_pred fields", 16, "#6b7280"))
    else:
        body.append(label(plot_x + 30, plot_y + 120, "range offset: missing", 22, "#9ca3af"))

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{outer_w}" height="{outer_h}" '
        f'viewBox="0 0 {outer_w} {outer_h}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )
    Path(output_path).write_text(svg, encoding="utf-8")
    return 1, missing_temporal
