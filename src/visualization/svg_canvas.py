"""Small SVG helpers used by the V0 diagnostic views."""

from __future__ import annotations

from html import escape as html_escape
from math import cos, radians, sin
from pathlib import Path
from typing import Any


FAMILY_COLORS = {
    "factor_inference": "#00a6d6",
    "factor_topk": "#2f7dff",
    "visible_support": "#00a878",
    "wedge": "#f28c28",
    "ray": "#b657d8",
    "signed": "#d64550",
    "bidirectional": "#6772e5",
    "base": "#6b7280",
    "other": "#111827",
}


def esc(value: Any) -> str:
    return html_escape(str(value if value is not None else ""), quote=True)


def file_uri(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    try:
        return Path(text).resolve().as_uri()
    except ValueError:
        return text


def svg_document(width: int, height: int, body: str, view_box: str | None = None) -> str:
    vb = f' viewBox="{esc(view_box)}"' if view_box else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"{vb} '
        'font-family="Arial, Helvetica, sans-serif">\n'
        f"{body}\n"
        "</svg>\n"
    )


def image_or_placeholder(path: str, x: float, y: float, width: float, height: float, label: str) -> str:
    if path and Path(path).exists():
        href = file_uri(path)
        return (
            f'<image href="{esc(href)}" x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" '
            f'height="{height:.2f}" preserveAspectRatio="xMidYMid meet" />'
        )
    label_text = label if not path else f"{label}: missing"
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        'fill="#f3f4f6" stroke="#9ca3af" stroke-dasharray="10 8" />'
        f'<text x="{x + width / 2:.2f}" y="{y + height / 2:.2f}" text-anchor="middle" '
        'font-size="24" fill="#6b7280">'
        f"{esc(label_text)}</text>"
    )


def label(x: float, y: float, text: str, size: int = 18, fill: str = "#111827") -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{fill}">{esc(text)}</text>'


def normalize_family(row: dict[str, str]) -> str:
    text = " ".join(
        str(row.get(key, "")).lower()
        for key in ("candidate_source", "candidate_source_family", "candidate_detail", "c1_2_mode_type")
    )
    if "bidirectional" in text:
        return "bidirectional"
    if "signed" in text:
        return "signed"
    if "wedge" in text:
        return "wedge"
    if "ray" in text:
        return "ray"
    if "visible" in text:
        return "visible_support"
    if "topk" in text:
        return "factor_topk"
    if "factor_inference" in text or "factor_runtime_prior" in text or "factor_final" in text:
        return "factor_inference"
    if "base" in text:
        return "base"
    return "other"


def candidate_rank(row: dict[str, str], fallback: int) -> str:
    for key in ("rank", "candidate_rank", "c1_2_mode_rank", "_row_index"):
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return str(fallback)


def first_present(row: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return ""


def float_value(row: dict[str, str], key: str, default: float | None = None) -> float | None:
    value = str(row.get(key, "")).strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def rotated_rect(
    cx: float,
    cy: float,
    width: float,
    height: float,
    heading_deg: float,
    stroke: str,
    fill: str = "none",
    stroke_width: float = 4.0,
    dash: str = "",
    opacity: float = 1.0,
) -> str:
    theta = radians(heading_deg)
    ux = cos(theta)
    uy = sin(theta)
    vx = -sin(theta)
    vy = cos(theta)
    half_w = width / 2.0
    half_h = height / 2.0
    points = []
    for sx, sy in ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)):
        x = cx + sx * ux + sy * vx
        y = cy + sx * uy + sy * vy
        points.append(f"{x:.2f},{y:.2f}")
    dash_attr = f' stroke-dasharray="{esc(dash)}"' if dash else ""
    return (
        f'<polygon points="{" ".join(points)}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{stroke_width:.2f}" opacity="{opacity:.3f}"{dash_attr} />'
    )


def legend(x: float, y: float, families: list[str]) -> str:
    parts = []
    for idx, family in enumerate(families):
        color = FAMILY_COLORS.get(family, FAMILY_COLORS["other"])
        yy = y + idx * 28
        parts.append(f'<rect x="{x:.2f}" y="{yy - 16:.2f}" width="18" height="18" fill="{color}" />')
        parts.append(label(x + 26, yy, family, size=18))
    return "\n".join(parts)


def compact(value: str, limit: int = 44) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
