"""Candidate source-family overlay for SAR frames."""

from __future__ import annotations

from pathlib import Path

from .svg_canvas import (
    FAMILY_COLORS,
    candidate_rank,
    compact,
    esc,
    first_present,
    image_or_placeholder,
    label,
    legend,
    normalize_family,
    rotated_rect,
)


POSTHOC_IOU_KEYS = (
    "axis_aligned_proxy_iou",
    "posthoc_iou",
    "iou",
    "current_iou",
    "best_proxy_iou",
)


def render_candidate_overlay(
    sample: dict[str, str],
    candidates: list[dict[str, str]],
    scene_config: dict,
    output_path: str | Path,
) -> int:
    sar_canvas = scene_config.get("sar_canvas", {"width": 2308, "height": 1334})
    width = int(sar_canvas.get("width", 2308))
    height = int(sar_canvas.get("height", 1334))
    table_x = width + 34
    view_width = width + 760
    view_height = max(height + 90, 520)
    posthoc_debug = str(sample.get("posthoc_debug_enabled", "")).lower() == "true"
    families = sorted({normalize_family(row) for row in candidates}) or ["other"]

    body = [
        f'<rect x="0" y="0" width="{view_width}" height="{view_height}" fill="#ffffff" />',
        label(20, 34, f"Candidate Overlay: {sample.get('sample_id')} | {sample.get('sample_type')}", 26),
        f'<g transform="translate(0,60)">',
        image_or_placeholder(sample.get("sar_frame_path", ""), 0, 0, width, height, "SAR frame"),
    ]
    for idx, row in enumerate(candidates, start=1):
        try:
            cx = float(row.get("cx", ""))
            cy = float(row.get("cy", ""))
            box_w = float(row.get("w", ""))
            box_h = float(row.get("h", ""))
        except ValueError:
            continue
        heading = float(row.get("heading", "0") or 0.0)
        family = normalize_family(row)
        color = FAMILY_COLORS.get(family, FAMILY_COLORS["other"])
        body.append(rotated_rect(cx, cy, box_w, box_h, heading, stroke=color, stroke_width=5.0, opacity=0.82))
        body.append(
            f'<text x="{cx + 8:.2f}" y="{cy - 8:.2f}" font-size="28" fill="{color}" '
            'paint-order="stroke" stroke="#ffffff" stroke-width="4">'
            f"r{esc(candidate_rank(row, idx))}</text>"
        )
    body.append("</g>")

    body.extend(
        [
            label(table_x, 92, "source families", 22),
            legend(table_x, 126, families),
            label(table_x, 330, "candidates", 22),
            f'<text x="{table_x}" y="360" font-size="16" fill="#6b7280">'
            "IoU appears only when posthoc debug is enabled and an IoU field exists.</text>",
        ]
    )
    y = 392
    header = "rank | family | source | candidate_id"
    if posthoc_debug:
        header += " | IoU"
    body.append(label(table_x, y, header, 16, "#374151"))
    y += 28
    for idx, row in enumerate(candidates[:28], start=1):
        family = normalize_family(row)
        color = FAMILY_COLORS.get(family, FAMILY_COLORS["other"])
        rank = candidate_rank(row, idx)
        source = row.get("candidate_source", "")
        cid = row.get("candidate_id", "")
        iou = first_present(row, POSTHOC_IOU_KEYS) if posthoc_debug else ""
        line = f"{rank} | {family} | {compact(source, 22)} | {compact(cid, 42)}"
        if posthoc_debug:
            line += f" | {iou or 'missing'}"
        body.append(f'<circle cx="{table_x + 8}" cy="{y - 6}" r="6" fill="{color}" />')
        body.append(label(table_x + 22, y, line, 15))
        y += 24
        if y > view_height - 28:
            body.append(label(table_x + 22, y, f"... {max(len(candidates) - idx, 0)} more candidates", 15, "#6b7280"))
            break

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{view_width}" height="{view_height}" '
        f'viewBox="0 0 {view_width} {view_height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )
    Path(output_path).write_text(svg, encoding="utf-8")
    return 1
