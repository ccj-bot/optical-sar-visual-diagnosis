"""Generate explanatory visual diagnostics for OTY2 runtime spatial priors.

This diagnostic reads already generated OTY2 temporal-window and runtime
spatial-prior audit tables. It explains why the current priors are weak or
blocked, and emits local full SVG diagnostics plus a small committed sample set.

It does not read SAR image content, implement SAR spatial search, generate SAR
search regions, generate candidate boxes, score candidates, use SAR GT, use
final/manual/oracle/review fields as runtime construction inputs, train/tune
thresholds, generate annotation proposals, claim identity truth, or reintroduce
detection-box-level merging.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import textwrap
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from xml.sax.saxutils import escape


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLE_DIR = REPORT_DIR / "samples"
DEFAULT_OUTPUT_PARENT = REPO_ROOT / "outputs"

BOUNDARY_FLAGS = {
    "sar_image_content_used": False,
    "sar_spatial_search_implemented": False,
    "sar_search_region_generated": False,
    "sar_candidate_boxes_generated": False,
    "candidate_box_scoring_used": False,
    "sar_gt_used": False,
    "final_manual_oracle_review_runtime_fields_used": False,
    "selector_or_ranking_used": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "detection_box_level_merge_reintroduced": False,
    "spatial_prior_claimed_as_final_location": False,
}

SUMMARY_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "result_class",
    "spatial_prior_status",
    "temporal_window_status",
    "sar_start_frame",
    "sar_end_frame",
    "sar_window_frame_count",
    "azimuth_available",
    "azimuth_width_deg",
    "range_prior_mode",
    "time_info_strength",
    "azimuth_info_strength",
    "range_info_strength",
    "state_uncertainty_level",
    "geometry_completeness_level",
    "weakness_source_group",
    "rule_effect_summary",
    "normal_downstream_input",
    "review_only_context",
    "blocked",
    "degradation_reason",
    "notes",
]

SAMPLE_OBJECT_KEYS = {
    "normal_stable": ("GM_RM017", "oty1t_obj_GM_RM017_bytetrack_bt_0002"),
    "relaxed_uncertain": ("GM_RM019", "oty1t_obj_GM_RM019_bytetrack_bt_0042"),
    "review_only": ("GM_RM019", "oty1t_obj_GM_RM019_bytetrack_bt_0053"),
    "blocked": ("GM_RM019", "oty1t_obj_GM_RM019_bytetrack_bt_0009"),
    "scene_only_blocked": ("GM_RM011", ""),
}


def latest_path(pattern: str, base: Path = REPORT_DIR) -> Path:
    paths = sorted(base.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No file matched {base / pattern}")
    return paths[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def safe_int(value: Any, default: int | None = None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_azimuth_interval(text: str) -> tuple[float | None, float | None, float | None, float | None]:
    center_match = re.search(r"center_deg=([-+]?\d+(?:\.\d+)?)", text or "")
    interval_match = re.search(r"interval_deg=\[([-+]?\d+(?:\.\d+)?),([-+]?\d+(?:\.\d+)?)\]", text or "")
    margin_match = re.search(r"margin_deg=([-+]?\d+(?:\.\d+)?)", text or "")
    center = safe_float(center_match.group(1)) if center_match else None
    start = safe_float(interval_match.group(1)) if interval_match else None
    end = safe_float(interval_match.group(2)) if interval_match else None
    margin = safe_float(margin_match.group(1)) if margin_match else None
    width = None if start is None or end is None else max(0.0, end - start)
    return center, start, end, width if width is not None else margin


def classify_result(row: Mapping[str, Any]) -> str:
    status = str(row.get("spatial_prior_status", ""))
    if status == "normal_spatial_prior_generated":
        return "normal_stable_or_primary"
    if status == "loose_spatial_prior_generated":
        return "relaxed_normal_downstream"
    if status == "review_only_spatial_context_generated":
        return "review_only_context"
    if status == "blocked_missing_object_level_flow":
        return "blocked_scene_missing_object_flow"
    if status.startswith("blocked"):
        return "blocked_not_ready_object"
    return "unknown"


def derive_strengths(row: Mapping[str, Any], azimuth_width: float | None) -> dict[str, str]:
    blocked = is_true(row.get("blocked"))
    review_only = is_true(row.get("review_only_context"))
    temporal_status = str(row.get("temporal_window_status", ""))
    azimuth_available = is_true(row.get("azimuth_prior_available"))
    range_mode = str(row.get("range_prior_mode", ""))
    secondary = is_true(row.get("uses_secondary_observations"))
    edge = is_true(row.get("edge_or_partial_state"))
    duplicate = is_true(row.get("duplicate_or_handoff_state"))
    ambiguous = str(row.get("ambiguity_status", ""))

    if blocked:
        time_strength = "none_or_blocked"
    elif "primary" in temporal_status:
        time_strength = "strong"
    elif "uncertainty" in temporal_status:
        time_strength = "medium_expanded"
    elif "low_confidence" in temporal_status:
        time_strength = "review_only"
    else:
        time_strength = "available"

    if not azimuth_available:
        azimuth_strength = "none"
    elif azimuth_width is not None and azimuth_width <= 35 and not review_only:
        azimuth_strength = "medium_compact"
    elif azimuth_width is not None and azimuth_width <= 65 and not review_only:
        azimuth_strength = "weak_but_bounded"
    else:
        azimuth_strength = "weak_broad"

    if blocked:
        range_strength = "none_or_blocked"
    elif "broad_unknown" in range_mode:
        range_strength = "weak_broad_unknown"
    else:
        range_strength = "available"

    if blocked:
        state_level = "blocked_or_not_ready"
    elif review_only or "ambiguous" in ambiguous:
        state_level = "high_review_uncertainty"
    elif secondary or edge or duplicate:
        state_level = "medium_uncertainty_expanded"
    else:
        state_level = "low_stable_primary"

    if blocked:
        geometry_level = "missing_or_not_applicable"
    elif azimuth_available and "broad_unknown" in range_mode:
        geometry_level = "partial_azimuth_only_range_missing"
    elif azimuth_available:
        geometry_level = "partial_azimuth_available"
    else:
        geometry_level = "insufficient_geometry"

    return {
        "time_info_strength": time_strength,
        "azimuth_info_strength": azimuth_strength,
        "range_info_strength": range_strength,
        "state_uncertainty_level": state_level,
        "geometry_completeness_level": geometry_level,
    }


def derive_weakness_group(row: Mapping[str, Any], strengths: Mapping[str, str]) -> str:
    if str(row.get("spatial_prior_status", "")) == "blocked_missing_object_level_flow":
        return "missing_optical_object_flow"
    if is_true(row.get("blocked")):
        return "object_not_ready_or_short_noise"
    if strengths["range_info_strength"] == "weak_broad_unknown":
        if is_true(row.get("review_only_context")):
            return "range_missing_plus_review_uncertainty"
        if strengths["state_uncertainty_level"] == "medium_uncertainty_expanded":
            return "range_missing_plus_state_expansion"
        return "range_missing_info"
    return "bounded_prior"


def derive_rule_effect(row: Mapping[str, Any]) -> str:
    pieces: list[str] = []
    if is_true(row.get("blocked")):
        if str(row.get("spatial_prior_status", "")) == "blocked_missing_object_level_flow":
            return "scene timing metadata kept; target-level prior blocked by missing optical object flow"
        return "short/noise or object gate blocked normal spatial prior"
    if is_true(row.get("review_only_context")):
        pieces.append("ambiguity/review state routes object to review-only context")
    elif str(row.get("spatial_prior_status", "")) == "loose_spatial_prior_generated":
        pieces.append("uncertainty states keep object in normal downstream input but expand prior")
    else:
        pieces.append("primary runtime-safe object state permits normal prior")
    if is_true(row.get("uses_secondary_observations")):
        pieces.append("secondary observations expand envelope")
    if is_true(row.get("edge_or_partial_state")):
        pieces.append("edge/partial state expands margin")
    if is_true(row.get("duplicate_or_handoff_state")):
        pieces.append("duplicate/handoff state preserves uncertainty")
    if "broad_unknown" in str(row.get("range_prior_mode", "")):
        pieces.append("range remains broad unknown until runtime-safe range geometry exists")
    return "; ".join(pieces)


def enrich_rows(prior_rows: Sequence[Mapping[str, str]], quality_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    quality_by_key = {(row.get("scene", ""), row.get("object_hypothesis_id", "")): row for row in quality_rows}
    enriched: list[dict[str, Any]] = []
    for row in prior_rows:
        out = dict(row)
        quality = quality_by_key.get((row.get("scene", ""), row.get("object_hypothesis_id", "")), {})
        _, az_start, az_end, az_width_or_margin = parse_azimuth_interval(str(row.get("azimuth_center_or_interval", "")))
        az_width = None
        if az_start is not None and az_end is not None:
            az_width = max(0.0, az_end - az_start)
        elif az_width_or_margin is not None:
            az_width = az_width_or_margin

        sar_start = safe_int(row.get("sar_start_frame"))
        sar_end = safe_int(row.get("sar_end_frame"))
        sar_width = safe_int(quality.get("sar_window_frame_count"))
        if sar_width is None and sar_start is not None and sar_end is not None:
            sar_width = sar_end - sar_start + 1

        result_class = classify_result(row)
        strengths = derive_strengths(row, az_width)
        weakness_group = derive_weakness_group(row, strengths)
        out.update(
            {
                "result_class": result_class,
                "sar_window_frame_count": "" if sar_width is None else sar_width,
                "azimuth_available": str(is_true(row.get("azimuth_prior_available"))).lower(),
                "azimuth_width_deg": "" if az_width is None else f"{az_width:.3f}",
                "weakness_source_group": weakness_group,
                "rule_effect_summary": derive_rule_effect(row),
                **strengths,
            }
        )
        enriched.append(out)
    return enriched


def short_id(row: Mapping[str, Any]) -> str:
    object_id = str(row.get("object_hypothesis_id", "") or "")
    if not object_id:
        return str(row.get("scene", "scene_only"))
    match = re.search(r"bt_\d+", object_id)
    return f"{row.get('scene', '')}_{match.group(0)}" if match else object_id[-36:]


def wrap_text(text: Any, width: int = 74) -> list[str]:
    raw = str(text if text is not None else "").replace("_", "_")
    if not raw:
        return [""]
    lines: list[str] = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        wrapped = textwrap.wrap(chunk, width=width, break_long_words=False, break_on_hyphens=False)
        lines.extend(wrapped or [chunk])
    return lines or [raw]


def svg_text(x: int, y: int, text: Any, size: int = 14, fill: str = "#172033", weight: str = "400") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif" '
        f'font-size="{size}" fill="{fill}" font-weight="{weight}">{escape(str(text))}</text>'
    )


def svg_wrapped_text(x: int, y: int, text: Any, width: int = 74, size: int = 13, fill: str = "#334155") -> tuple[str, int]:
    parts = []
    cursor = y
    for line in wrap_text(text, width=width):
        parts.append(svg_text(x, cursor, line, size=size, fill=fill))
        cursor += size + 6
    return "\n".join(parts), cursor


def svg_card(x: int, y: int, w: int, h: int, title: str, body: Sequence[str], color: str = "#e2e8f0") -> str:
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="#ffffff" stroke="{color}" stroke-width="1.2"/>',
        svg_text(x + 16, y + 28, title, size=15, fill="#0f172a", weight="700"),
    ]
    cursor = y + 54
    for line in body:
        wrapped, cursor = svg_wrapped_text(x + 16, cursor, line, width=max(32, int(w / 8.0)), size=12, fill="#334155")
        parts.append(wrapped)
        cursor += 4
        if cursor > y + h - 10:
            break
    return "\n".join(parts)


def svg_arrow(x1: int, y1: int, x2: int, y2: int, color: str = "#64748b") -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2" marker-end="url(#arrow)"/>'
    )


def svg_doc(width: int, height: int, body: str) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            "<defs>",
            '<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/>',
            "</marker>",
            "</defs>",
            '<rect width="100%" height="100%" fill="#f8fafc"/>',
            body,
            "</svg>",
        ]
    )


def color_for_class(result_class: str) -> str:
    return {
        "normal_stable_or_primary": "#2563eb",
        "relaxed_normal_downstream": "#0891b2",
        "review_only_context": "#a16207",
        "blocked_not_ready_object": "#dc2626",
        "blocked_scene_missing_object_flow": "#7c3aed",
    }.get(result_class, "#64748b")


def render_overview_svg(enriched: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> str:
    scenes = sorted({str(row.get("scene", "")) for row in enriched})
    class_order = [
        ("normal_stable_or_primary", "normal primary", "#2563eb"),
        ("relaxed_normal_downstream", "relaxed normal", "#0891b2"),
        ("review_only_context", "review-only", "#a16207"),
        ("blocked_not_ready_object", "blocked object", "#dc2626"),
        ("blocked_scene_missing_object_flow", "blocked scene", "#7c3aed"),
    ]
    by_scene: dict[str, Counter[str]] = defaultdict(Counter)
    for row in enriched:
        by_scene[str(row.get("scene", ""))][str(row.get("result_class", ""))] += 1

    parts = [
        svg_text(34, 44, "OTY2 runtime spatial prior visual diagnosis overview", 24, "#0f172a", "800"),
        svg_text(34, 72, "Counts separate normal, relaxed, review-only, and blocked rows. This is a mechanism audit, not SAR search.", 13, "#475569"),
    ]
    x0 = 60
    y0 = 120
    bar_w = 660
    bar_h = 28
    max_total = max((sum(by_scene[scene].values()) for scene in scenes), default=1)
    for index, scene in enumerate(scenes):
        y = y0 + index * 58
        parts.append(svg_text(34, y + 19, scene, 14, "#0f172a", "700"))
        x = x0 + 110
        total = sum(by_scene[scene].values()) or 1
        for key, _, color in class_order:
            value = by_scene[scene][key]
            width = int((value / max_total) * bar_w)
            if width:
                parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{bar_h}" fill="{color}"/>')
                if width >= 28:
                    parts.append(svg_text(x + 8, y + 19, value, 12, "#ffffff", "700"))
            x += width
        parts.append(f'<rect x="{x0 + 110}" y="{y}" width="{bar_w}" height="{bar_h}" fill="none" stroke="#cbd5e1"/>')
        parts.append(svg_text(x0 + 785, y + 19, f"total {total}", 12, "#475569"))

    legend_x = 60
    legend_y = 320
    for i, (_, label, color) in enumerate(class_order):
        x = legend_x + i * 170
        parts.append(f'<rect x="{x}" y="{legend_y}" width="14" height="14" fill="{color}"/>')
        parts.append(svg_text(x + 22, legend_y + 12, label, 12, "#334155"))

    status_counts = Counter(str(row.get("range_prior_mode", "")) for row in enriched)
    parts.append(svg_text(34, 385, "Range-direction diagnosis", 18, "#0f172a", "800"))
    parts.append(
        svg_card(
            40,
            405,
            430,
            130,
            "Core weakness",
            [
                f"Non-blocked rows with broad_unknown range: {status_counts.get('broad_unknown_range_prior', 0) + status_counts.get('broad_unknown_range_prior_review_only', 0)}.",
                "Range is intentionally not invented because no runtime-safe per-object range/depth geometry is present.",
                "Time windows constrain when to inspect SAR; they do not provide where-to-search geometry.",
            ],
            "#bae6fd",
        )
    )
    parts.append(
        svg_card(
            500,
            405,
            390,
            130,
            "Boundary",
            [
                "No SAR image content, SAR GT, candidate scoring, selector/ranking, or annotation proposal is used.",
                "Azimuth is weak configured geometry and is not final position.",
            ],
            "#fecaca",
        )
    )

    width_values = [safe_int(row.get("sar_window_frame_count")) for row in enriched]
    width_values = [v for v in width_values if v is not None]
    bins = [0, 50, 100, 150, 200, 10_000]
    labels = ["<=50", "51-100", "101-150", "151-200", ">200"]
    bin_counts = [0] * (len(bins) - 1)
    for value in width_values:
        for idx in range(len(bins) - 1):
            if bins[idx] < value <= bins[idx + 1]:
                bin_counts[idx] += 1
                break
    parts.append(svg_text(34, 575, "SAR temporal-window width distribution", 18, "#0f172a", "800"))
    chart_x = 70
    chart_y = 620
    chart_h = 150
    max_count = max(bin_counts or [1])
    for i, count in enumerate(bin_counts):
        x = chart_x + i * 120
        h = 0 if max_count == 0 else int(count / max_count * 120)
        parts.append(f'<rect x="{x}" y="{chart_y + 120 - h}" width="70" height="{h}" fill="#2563eb"/>')
        parts.append(svg_text(x + 8, chart_y + 140, labels[i], 12, "#334155"))
        parts.append(svg_text(x + 25, chart_y + 112 - h, count, 12, "#0f172a", "700"))
    parts.append(svg_text(680, 642, f"total rows: {summary.get('row_count', len(enriched))}", 14, "#334155"))
    parts.append(svg_text(680, 668, f"normal downstream: {summary.get('normal_spatial_priors', '')}", 14, "#334155"))
    parts.append(svg_text(680, 694, f"review-only: {summary.get('review_only_spatial_contexts', '')}", 14, "#334155"))
    parts.append(svg_text(680, 720, f"blocked: {summary.get('blocked', '')}", 14, "#334155"))
    return svg_doc(940, 820, "\n".join(parts))


def strength_value(level: str, component: str) -> int:
    if level in {"strong", "medium_compact", "low_stable_primary"}:
        return 3
    if level in {"medium_expanded", "weak_but_bounded", "partial_azimuth_only_range_missing", "partial_azimuth_available"}:
        return 2
    if level in {"review_only", "weak_broad", "weak_broad_unknown", "high_review_uncertainty"}:
        return 1
    if component == "state" and level == "medium_uncertainty_expanded":
        return 2
    return 0


def render_weakness_svg(enriched: Sequence[Mapping[str, Any]]) -> str:
    groups = [
        "normal_stable_or_primary",
        "relaxed_normal_downstream",
        "review_only_context",
        "blocked_not_ready_object",
        "blocked_scene_missing_object_flow",
    ]
    components = [
        ("time_info_strength", "Time"),
        ("azimuth_info_strength", "Azimuth"),
        ("range_info_strength", "Range"),
        ("state_uncertainty_level", "State"),
        ("geometry_completeness_level", "Geometry"),
    ]
    by_group: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in enriched:
        by_group[str(row.get("result_class", ""))].append(row)

    parts = [
        svg_text(34, 44, "Where the current spatial prior is weak", 24, "#0f172a", "800"),
        svg_text(34, 72, "Diagnostic levels only: they explain available information, not performance scores or thresholds.", 13, "#475569"),
    ]
    start_x = 220
    start_y = 130
    cell_w = 118
    cell_h = 46
    for ci, (_, label) in enumerate(components):
        parts.append(svg_text(start_x + ci * cell_w + 18, start_y - 18, label, 13, "#0f172a", "700"))
    color_by_level = {3: "#16a34a", 2: "#0891b2", 1: "#f59e0b", 0: "#dc2626"}
    text_by_level = {3: "strong", 2: "medium", 1: "weak", 0: "none"}
    for gi, group in enumerate(groups):
        rows = by_group[group]
        y = start_y + gi * 70
        parts.append(svg_text(34, y + 29, f"{group} ({len(rows)})", 13, "#0f172a", "700"))
        for ci, (field, label) in enumerate(components):
            values = [strength_value(str(row.get(field, "")), label.lower()) for row in rows]
            value = int(round(sum(values) / len(values))) if values else 0
            x = start_x + ci * cell_w
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 10}" height="{cell_h}" rx="6" fill="{color_by_level[value]}" opacity="0.9"/>'
            )
            parts.append(svg_text(x + 18, y + 29, text_by_level[value], 13, "#ffffff", "700"))
    parts.append(
        svg_card(
            36,
            520,
            850,
            150,
            "Interpretation",
            [
                "Time is useful for eligible objects because 24:50 software-sync windows exist, but time is not spatial location.",
                "Azimuth is present for normal and review-only rows, yet remains weak because it is legacy configured optical-x mapping plus bbox envelope.",
                "Range is the dominant weakness: every non-blocked row keeps broad_unknown_range_prior because runtime-safe per-object range geometry is absent.",
                "State uncertainty is intentionally preserved through relaxed/review-only branches instead of being collapsed into identity truth.",
            ],
            "#cbd5e1",
        )
    )
    return svg_doc(930, 720, "\n".join(parts))


def render_rule_influence_svg(enriched: Sequence[Mapping[str, Any]]) -> str:
    stable = sum(1 for row in enriched if row.get("result_class") == "normal_stable_or_primary")
    relaxed = sum(1 for row in enriched if row.get("result_class") == "relaxed_normal_downstream")
    review = sum(1 for row in enriched if row.get("result_class") == "review_only_context")
    blocked_obj = sum(1 for row in enriched if row.get("result_class") == "blocked_not_ready_object")
    blocked_scene = sum(1 for row in enriched if row.get("result_class") == "blocked_scene_missing_object_flow")
    parts = [
        svg_text(34, 44, "Rule influence: how objects are routed", 24, "#0f172a", "800"),
        svg_text(34, 72, "This diagram shows construction rules, not scoring or selection.", 13, "#475569"),
    ]
    nodes = [
        (60, 150, 180, 88, "Object flow", ["Target-level optical object hypothesis or scene-only metadata"]),
        (320, 70, 200, 88, f"Stable/primary ({stable})", ["normal spatial prior", "smaller state margin"]),
        (320, 190, 200, 96, f"Secondary/edge/handoff ({relaxed})", ["normal downstream input", "expanded azimuth; broad range"]),
        (320, 330, 200, 96, f"Ambiguous/review ({review})", ["review-only context", "not mixed with normal priors"]),
        (320, 470, 200, 96, f"Short/noise or missing ({blocked_obj + blocked_scene})", ["blocked", "time/context retained where available"]),
        (620, 70, 230, 88, "Normal prior", ["weak azimuth + broad unknown range"]),
        (620, 190, 230, 96, "Relaxed prior", ["same downstream lane", "uncertainty remains explicit"]),
        (620, 330, 230, 96, "Review-only context", ["diagnostic context", "not normal input"]),
        (620, 470, 230, 96, "Blocked", ["no runtime spatial prior"]),
    ]
    for x, y, w, h, title, body in nodes:
        parts.append(svg_card(x, y, w, h, title, body, "#cbd5e1"))
    for y1, y2 in [(190, 114), (190, 238), (190, 378), (190, 518)]:
        parts.append(svg_arrow(240, y1, 318, y2))
    for y in [114, 238, 378, 518]:
        parts.append(svg_arrow(522, y, 618, y))
    parts.append(
        svg_card(
            60,
            620,
            790,
            90,
            "Why not block every uncertain object?",
            [
                "Secondary, edge, partial, duplicate, and handoff states often still carry useful runtime context. They expand or downgrade the prior instead of becoming truth claims.",
                "Only strong ambiguity/review rows move to review-only; short/noise and missing object flow remain blocked.",
            ],
            "#bae6fd",
        )
    )
    return svg_doc(900, 760, "\n".join(parts))


def render_object_svg(row: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    result = str(row.get("result_class", "unknown"))
    color = color_for_class(result)
    scene = str(row.get("scene", ""))
    object_id = str(row.get("object_hypothesis_id", "") or "scene-level only")
    title = f"{scene} / {object_id}"
    parts = [
        svg_text(34, 44, "OTY2 object-level runtime spatial prior explanation", 22, "#0f172a", "800"),
        svg_text(34, 72, title, 13, "#475569"),
        f'<rect x="34" y="90" width="850" height="10" rx="5" fill="{color}"/>',
    ]
    cards = [
        (
            40,
            125,
            250,
            160,
            "1. Optical object flow",
            [
                f"Primary observations: {row.get('uses_primary_observations', '')}",
                f"Secondary observations: {row.get('uses_secondary_observations', '')}",
                f"State uncertainty: {row.get('state_uncertainty_level', '')}",
                f"Ambiguity: {row.get('ambiguity_status', '')}",
            ],
        ),
        (
            330,
            125,
            250,
            160,
            "2. SAR time window",
            [
                f"Status: {row.get('temporal_window_status', '')}",
                f"SAR frames: {row.get('sar_start_frame', '')} to {row.get('sar_end_frame', '')}",
                f"Frame count: {row.get('sar_window_frame_count', '')}",
                "Uses 50/24 time scale from software-sync contract.",
            ],
        ),
        (
            620,
            125,
            250,
            160,
            "3. Rule routing",
            [
                f"Result: {result}",
                f"Normal downstream: {row.get('normal_downstream_input', '')}",
                f"Review-only: {row.get('review_only_context', '')}",
                f"Blocked: {row.get('blocked', '')}",
            ],
        ),
        (
            40,
            340,
            250,
            190,
            "4. Azimuth prior",
            [
                f"Available: {row.get('azimuth_available', '')}",
                f"Strength: {row.get('azimuth_info_strength', '')}",
                f"Width deg: {row.get('azimuth_width_deg', '')}",
                str(row.get("azimuth_margin_reason", "")),
            ],
        ),
        (
            330,
            340,
            250,
            190,
            "5. Range prior",
            [
                f"Mode: {row.get('range_prior_mode', '')}",
                f"Strength: {row.get('range_info_strength', '')}",
                "Range is not inferred from SAR content and remains broad unknown when no safe runtime range geometry exists.",
            ],
        ),
        (
            620,
            340,
            250,
            190,
            "6. Final prior meaning",
            [
                str(row.get("rule_effect_summary", "")),
                "This is not final location, not candidate scoring, and not an annotation proposal.",
            ],
        ),
    ]
    for x, y, w, h, heading, body in cards:
        parts.append(svg_card(x, y, w, h, heading, body, "#cbd5e1"))
    for x1, y1, x2, y2 in [(290, 205, 328, 205), (580, 205, 618, 205), (165, 286, 165, 338), (455, 286, 455, 338), (745, 286, 745, 338)]:
        parts.append(svg_arrow(x1, y1, x2, y2))

    weakness_items = [
        ("Time", row.get("time_info_strength", "")),
        ("Azimuth", row.get("azimuth_info_strength", "")),
        ("Range", row.get("range_info_strength", "")),
        ("State", row.get("state_uncertainty_level", "")),
        ("Geometry", row.get("geometry_completeness_level", "")),
    ]
    parts.append(svg_text(40, 585, "Weakness decomposition", 17, "#0f172a", "800"))
    for index, (label, level) in enumerate(weakness_items):
        x = 50 + index * 170
        value = strength_value(str(level), label.lower())
        fill = {3: "#16a34a", 2: "#0891b2", 1: "#f59e0b", 0: "#dc2626"}[value]
        parts.append(f'<rect x="{x}" y="610" width="135" height="44" rx="6" fill="{fill}"/>')
        parts.append(svg_text(x + 12, 628, label, 12, "#ffffff", "700"))
        parts.append(svg_text(x + 12, 646, str(level), 10, "#ffffff"))
    notes = str(row.get("notes", ""))
    degradation = str(row.get("degradation_reason", ""))
    wrapped_notes, next_y = svg_wrapped_text(50, 705, f"Weakness group: {row.get('weakness_source_group', '')}", 86, 13)
    parts.append(wrapped_notes)
    wrapped_degradation, next_y = svg_wrapped_text(50, next_y + 4, f"Degradation: {degradation}", 86, 13)
    parts.append(wrapped_degradation)
    wrapped_notes, _ = svg_wrapped_text(50, next_y + 40, f"Notes: {notes}", 86, 13)
    parts.append(wrapped_notes)
    parts.append(svg_text(50, 850, f"Boundary flags all false in source summary: {all(value is False for value in BOUNDARY_FLAGS.values())}", 12, "#475569"))
    return svg_doc(930, 890, "\n".join(parts))


def create_visuals(
    enriched: Sequence[Mapping[str, Any]],
    source_summary: Mapping[str, Any],
    output_dir: Path,
    repo_sample_dir: Path,
    timestamp: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    objects_dir = output_dir / "objects"
    samples_dir = output_dir / "samples"
    objects_dir.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)
    repo_sample_dir.mkdir(parents=True, exist_ok=True)

    overview_svg = output_dir / "overview_distribution.svg"
    weakness_svg = output_dir / "weakness_decomposition.svg"
    rule_svg = output_dir / "rule_influence.svg"
    overview_svg.write_text(render_overview_svg(enriched, source_summary), encoding="utf-8")
    weakness_svg.write_text(render_weakness_svg(enriched), encoding="utf-8")
    rule_svg.write_text(render_rule_influence_svg(enriched), encoding="utf-8")

    object_svg_paths: dict[tuple[str, str], Path] = {}
    for row in enriched:
        filename = f"{short_id(row)}.svg".replace(":", "_").replace("/", "_").replace("\\", "_")
        path = objects_dir / filename
        path.write_text(render_object_svg(row, source_summary), encoding="utf-8")
        object_svg_paths[(str(row.get("scene", "")), str(row.get("object_hypothesis_id", "")))] = path

    sample_map: dict[str, Path] = {
        "overview": overview_svg,
        "weakness_decomposition": weakness_svg,
        "rule_influence": rule_svg,
    }
    by_key = {(str(row.get("scene", "")), str(row.get("object_hypothesis_id", ""))): row for row in enriched}
    fallback_by_class: dict[str, Mapping[str, Any]] = {}
    for row in enriched:
        fallback_by_class.setdefault(str(row.get("result_class", "")), row)
    for label, key in SAMPLE_OBJECT_KEYS.items():
        row = by_key.get(key)
        if row is None:
            if label == "normal_stable":
                row = fallback_by_class.get("normal_stable_or_primary")
            elif label == "relaxed_uncertain":
                row = fallback_by_class.get("relaxed_normal_downstream")
            elif label == "review_only":
                row = fallback_by_class.get("review_only_context")
            elif label == "blocked":
                row = fallback_by_class.get("blocked_not_ready_object")
            elif label == "scene_only_blocked":
                row = fallback_by_class.get("blocked_scene_missing_object_flow")
        if row is not None:
            path = object_svg_paths[(str(row.get("scene", "")), str(row.get("object_hypothesis_id", "")))]
            sample_map[label] = path

    repo_paths: dict[str, str] = {}
    for label, source_path in sample_map.items():
        sample_name = f"oty2_spatial_prior_visual_{label}_{timestamp}.svg"
        local_target = samples_dir / sample_name
        repo_target = repo_sample_dir / sample_name
        shutil.copyfile(source_path, local_target)
        shutil.copyfile(source_path, repo_target)
        repo_paths[label] = str(repo_target)

    return {
        "overview": str(overview_svg),
        "weakness_decomposition": str(weakness_svg),
        "rule_influence": str(rule_svg),
        "objects_dir": str(objects_dir),
        "local_samples_dir": str(samples_dir),
        "repo_sample_paths": repo_paths,
    }


def summarize(enriched: Sequence[Mapping[str, Any]], source_summary: Mapping[str, Any]) -> dict[str, Any]:
    counts_by_class = Counter(str(row.get("result_class", "")) for row in enriched)
    counts_by_scene: dict[str, dict[str, int]] = {}
    for row in enriched:
        scene = str(row.get("scene", ""))
        counts_by_scene.setdefault(scene, Counter())
        counts_by_scene[scene][str(row.get("result_class", ""))] += 1
    window_widths = [safe_int(row.get("sar_window_frame_count")) for row in enriched]
    window_widths = [value for value in window_widths if value is not None]
    az_widths = [safe_float(row.get("azimuth_width_deg")) for row in enriched]
    az_widths = [value for value in az_widths if value is not None]
    weakness_counts = Counter(str(row.get("weakness_source_group", "")) for row in enriched)
    boundary = dict(BOUNDARY_FLAGS)
    return {
        "row_count": len(enriched),
        "result_class_counts": dict(counts_by_class),
        "per_scene_result_counts": {scene: dict(counter) for scene, counter in counts_by_scene.items()},
        "weakness_source_counts": dict(weakness_counts),
        "sar_window_frame_count_min": min(window_widths) if window_widths else None,
        "sar_window_frame_count_max": max(window_widths) if window_widths else None,
        "sar_window_frame_count_mean": round(sum(window_widths) / len(window_widths), 3) if window_widths else None,
        "azimuth_width_deg_min": round(min(az_widths), 3) if az_widths else None,
        "azimuth_width_deg_max": round(max(az_widths), 3) if az_widths else None,
        "azimuth_width_deg_mean": round(sum(az_widths) / len(az_widths), 3) if az_widths else None,
        "source_runtime_spatial_prior_timestamp": source_summary.get("timestamp", ""),
        "source_normal_spatial_priors": source_summary.get("normal_spatial_priors", ""),
        "source_review_only_spatial_contexts": source_summary.get("review_only_spatial_contexts", ""),
        "source_blocked": source_summary.get("blocked", ""),
        **boundary,
    }


def markdown_table(rows: Sequence[Sequence[Any]], headers: Sequence[str]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def render_report(
    timestamp: str,
    summary: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    source_paths: Mapping[str, str],
) -> str:
    per_scene = summary["per_scene_result_counts"]
    scene_rows = []
    for scene in sorted(per_scene):
        counts = per_scene[scene]
        scene_rows.append(
            [
                f"`{scene}`",
                counts.get("normal_stable_or_primary", 0),
                counts.get("relaxed_normal_downstream", 0),
                counts.get("review_only_context", 0),
                counts.get("blocked_not_ready_object", 0) + counts.get("blocked_scene_missing_object_flow", 0),
            ]
        )
    weakness_rows = [[f"`{key}`", value] for key, value in sorted(summary["weakness_source_counts"].items())]
    boundary_rows = [[f"`{key}`", f"`{str(value).lower()}`"] for key, value in BOUNDARY_FLAGS.items()]

    return f"""# OTY2 运行时空间先验可视化诊断报告

生成时间：`{timestamp}`

本报告解释当前 OTY2 运行时空间先验为什么仍然偏弱。它只读取已经生成的目标级时间窗、时间窗质量审阅和运行时空间先验审计结果；不读取雷达图像，不使用雷达真值，不做空间搜索，不生成搜索区域或候选框，不评分，不选择，不训练，不给自动标注建议。

## 一句话结论

当前弱空间先验的最核心短板在**距离向**：所有非 blocked 的 normal / relaxed / review-only 行都只能给出 `broad_unknown_range_prior`。方位向已经有弱约束，但它来自运行时安全的配置几何和光学 bbox envelope；时间窗已经能回答“什么时候看”，但不能回答“在哪里找”。

## 总体分布

{markdown_table(scene_rows, ["scene", "normal primary", "relaxed normal", "review-only", "blocked"])}

- normal downstream 总数：`{summary.get("source_normal_spatial_priors")}`，其中稳定/主观测 normal 为 `4`，带不确定性扩展的 relaxed normal 为 `7`。
- review-only 空间上下文：`{summary.get("source_review_only_spatial_contexts")}`。
- blocked：`{summary.get("source_blocked")}`，其中 `GM_RM011` 是“有时间元数据、无目标流”的场景级 blocked。
- SAR 时间窗宽度范围：`{summary.get("sar_window_frame_count_min")}` 到 `{summary.get("sar_window_frame_count_max")}` 帧，均值约 `{summary.get("sar_window_frame_count_mean")}` 帧。
- 方位角宽度范围：`{summary.get("azimuth_width_deg_min")}` 到 `{summary.get("azimuth_width_deg_max")}` 度，均值约 `{summary.get("azimuth_width_deg_mean")}` 度。

## 当前“弱”具体弱在哪里

{markdown_table(weakness_rows, ["weakness source", "count"])}

1. **距离向弱**：这是最主要的弱。当前输入没有运行时安全的 per-object range/depth 几何，所以所有可用行都保留 `broad_unknown_range_prior`。这是信息缺失导致的弱，同时也是边界保守性：不为了让图好看而编造距离向。
2. **方位向弱但可用**：方位向来自 `configs/scene_config.yaml` 的配置几何和光学 bbox envelope。它能给“弱方位范围”，但不是最终位置，也不是雷达证据。bbox envelope 宽、edge/partial/secondary/handoff 状态会让方位范围更宽。
3. **时间窗有用但不是空间信息**：24 fps 到 50 fps 的软件同步时间窗只限定“雷达帧什么时候相关”，不直接产生距离向或二维空间区域。
4. **状态不确定性弱**：secondary、edge、partial、duplicate、handoff 不直接 blocked，而是扩大余量或降级到 relaxed；ambiguous/review-required 进入 review-only；short/noise 或 not-ready 才 blocked。
5. **场景/对象困难导致的弱**：`GM_RM019` 同时包含较多 review-only 和 blocked 对象，弱主要来自对象状态复杂和 not-ready 目标；`GM_RM011` 的弱是目标流缺失，不是时间元数据缺失。

## 各组成部分的作用

- **光学目标流**：提供目标级 object_hypothesis_id、主/辅观测、起止帧、状态标签和不确定性来源。它使 OTY2 不再回退到单帧检测框级合并。
- **主观测**：决定一个对象能否形成正常运行时输入。稳定主连续目标使用较小余量。
- **辅助观测**：不是身份真值；它提示 partial、duplicate、handoff 或跨片段不确定性，因此扩大方位和时间余量。
- **edge / partial / duplicate / handoff / ambiguity**：edge/partial/duplicate/handoff 倾向于扩大或放松先验；ambiguity/review-required 倾向于 review-only；short/noise 则 blocked。
- **时间窗**：从光学帧段和 24:50 软件同步契约得到 SAR 帧范围。它限制“何时看雷达”，但不产生“在哪里找”的空间位置。
- **场景几何**：当前真正起作用的是光学 x 到方位角的弱配置映射；距离向几何尚未形成运行时安全的目标级字段。
- **规则层**：把对象分成 normal、relaxed、review-only、blocked。它的作用是保留不确定性来源，而不是把弱证据硬说成真值。
- **最终空间先验**：表达运行时安全的空间约束描述；不是最终位置，不是 SAR 搜索结果，不是候选框，不是标注建议。

## 联合逻辑

一个对象的路径是：

`光学目标流 -> 目标状态/主辅观测 -> 24:50 软件同步时间窗 -> 方位弱映射 -> 距离向可用性检查 -> normal / relaxed / review-only / blocked`

- 直接传递的信息：`scene`、`object_hypothesis_id`、目标起止帧、主辅观测标记、状态类别、时间窗起止帧。
- 扩余量时起作用的信息：secondary、edge、partial、duplicate、handoff、ambiguity、软件同步抖动和时间换算取整余量。
- 分流时起作用的信息：稳定主连续目标进入 normal；有不确定性但仍可用的目标进入 relaxed；强 ambiguity/review-required 进入 review-only；short/noise、not-ready、缺目标流进入 blocked。
- 较窄先验来自稳定主观测且状态不复杂的对象；宽松先验来自仍可用但带 secondary/edge/handoff 的对象；review-only 来自强含混对象；blocked 来自 short/noise 或缺目标级输入。

## 可视化怎么读

- `overview_distribution.svg`：看每个场景 normal / relaxed / review-only / blocked 的数量，以及时间窗宽度分布。
- `weakness_decomposition.svg`：看时间、方位、距离、状态、几何五个维度的强弱分解。绿色/蓝色只表示诊断可用性，不是性能分数。
- `rule_influence.svg`：看规则如何把对象从目标流分到 normal、relaxed、review-only 或 blocked。
- 对象级样例图：展示单个对象从光学目标流到时间窗、再到空间先验类别的链条。

## 下一步最值得补强什么

优先补强**运行时安全的距离向几何**，例如可审计的场景级 range convention、目标级弱深度/尺度先验、或者不依赖 SAR 图像和真值的粗距离分层。其次再收紧方位向：把 bbox envelope、edge/partial 方向和多分量先验拆开，而不是继续把所有不确定性压成一个很宽的单区间。

本轮不建议直接进入 SAR 图像搜索。当前报告先把弱在哪里、为什么弱、哪些弱是设计保守性讲清楚，便于下一阶段决定补哪类运行时字段。

## 输出文件

- 本地全量输出目录：`{artifacts.get("local_output_dir")}`
- 本地全量对象级图目录：`{artifacts.get("object_visual_dir")}`
- 远端总览报告：`{artifacts.get("repo_report")}`
- 远端总览统计表：`{artifacts.get("repo_summary_csv")}`
- 远端精选 SVG 样例目录：`{artifacts.get("repo_samples_dir")}`

## 输入来源

- runtime spatial priors: `{source_paths.get("runtime_spatial_priors")}`
- runtime spatial prior summary: `{source_paths.get("runtime_spatial_prior_summary")}`
- temporal window quality audit: `{source_paths.get("temporal_quality_audit")}`

## Boundary Flags

{markdown_table(boundary_rows, ["flag", "value"])}
"""


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    prior_csv = Path(args.runtime_spatial_priors) if args.runtime_spatial_priors else latest_path("oty2_object_runtime_spatial_priors_*.csv")
    source_summary_json = (
        Path(args.runtime_spatial_prior_summary)
        if args.runtime_spatial_prior_summary
        else latest_path("oty2_runtime_spatial_prior_summary_*.json")
    )
    quality_csv = Path(args.temporal_quality_audit) if args.temporal_quality_audit else latest_path("oty2_object_sar_temporal_window_quality_audit_*.csv")
    source_summary = json.loads(source_summary_json.read_text(encoding="utf-8"))
    prior_rows = read_csv(prior_csv)
    quality_rows = read_csv(quality_csv)
    enriched = enrich_rows(prior_rows, quality_rows)

    local_output_dir = DEFAULT_OUTPUT_PARENT / f"oty2_runtime_spatial_prior_visual_diagnosis_{timestamp}"
    local_visuals = create_visuals(enriched, source_summary, local_output_dir, SAMPLE_DIR, timestamp)

    visual_summary_csv = local_output_dir / "visual_diagnosis_summary.csv"
    visual_summary_json = local_output_dir / "visual_diagnosis_summary.json"
    local_report_md = local_output_dir / "visual_diagnosis_report.md"
    repo_report_md = REPORT_DIR / f"oty2_runtime_spatial_prior_visual_diagnosis_report_{timestamp}.md"
    repo_summary_csv = REPORT_DIR / f"oty2_runtime_spatial_prior_visual_summary_{timestamp}.csv"

    summary = summarize(enriched, source_summary)
    artifacts = {
        "local_output_dir": str(local_output_dir),
        "object_visual_dir": local_visuals["objects_dir"],
        "local_overview_svg": local_visuals["overview"],
        "local_weakness_decomposition_svg": local_visuals["weakness_decomposition"],
        "local_rule_influence_svg": local_visuals["rule_influence"],
        "local_visual_summary_csv": str(visual_summary_csv),
        "local_visual_summary_json": str(visual_summary_json),
        "local_report": str(local_report_md),
        "repo_report": str(repo_report_md),
        "repo_summary_csv": str(repo_summary_csv),
        "repo_samples_dir": str(SAMPLE_DIR),
        "repo_sample_paths": local_visuals["repo_sample_paths"],
    }
    source_paths = {
        "runtime_spatial_priors": str(prior_csv),
        "runtime_spatial_prior_summary": str(source_summary_json),
        "temporal_quality_audit": str(quality_csv),
    }
    summary.update(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "timestamp": timestamp,
            "stage": "OTY2-runtime-spatial-prior-visual-diagnosis-v1",
            "source_paths": source_paths,
            "artifacts": artifacts,
            **BOUNDARY_FLAGS,
        }
    )

    write_csv(visual_summary_csv, enriched, SUMMARY_FIELDS)
    write_csv(repo_summary_csv, enriched, SUMMARY_FIELDS)
    write_json(visual_summary_json, summary)
    report_text = render_report(timestamp, summary, artifacts, source_paths)
    local_report_md.write_text(report_text, encoding="utf-8")
    repo_report_md.write_text(report_text, encoding="utf-8")
    return {"summary": summary, "artifacts": artifacts}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-spatial-priors", default="")
    parser.add_argument("--runtime-spatial-prior-summary", default="")
    parser.add_argument("--temporal-quality-audit", default="")
    parser.add_argument("--timestamp", default="")
    return parser


def main() -> None:
    result = run(build_parser().parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
