"""Corrected OTY2 GT-local SAR energy-field atlas.

The previous physical shell grammar atlas is marked as a failed visualization
because it reused support-wide panels and still visualized support-internal
peaks/components and small component boxes. This script generates a corrected
atlas using the SAR GT crop as the primary coordinate frame.

Only GT-local energy cues are extracted and displayed: ridge-like side bands,
endpoint hotspots, weak opposite-side returns, boundary occupancy, and
vehicle-scale energy-field contours. It does not draw support-internal
components outside GT, does not draw small component boxes as shell, and does
not produce revised GT, final boxes, selector/ranking, or identity truth.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle
from PIL import Image
from scipy import ndimage

from run_oty2_sar_vehicle_structure_mechanism_beyond_weighted_fusion import (
    box_available,
    gt_box_from_accounting,
    rotated_corners,
    sanitize,
)

try:
    from run_oty2_support_overlay_visualization_qa_and_chinese_review_atlas import (
        FONT,
        wrap_zh,
    )
except Exception:  # pragma: no cover - fallback if helper import changes.
    FONT = None

    def wrap_zh(text: str, width: int = 34) -> str:
        return "\n".join(textwrap.wrap(text, width=width))


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
VISUAL_DIR = REPORT_DIR / "visual_exemplars"
WORKSPACE_LOG_DIR = Path(r"D:\profile\research\workspace\logs")

GT_ACCOUNTING_CSV = REPORT_DIR / "oty2_gt_sample_accounting_audit_20260702_192810.csv"
GT_QUALITY_CSV = REPORT_DIR / "oty2_sar_gt_quality_audit_20260703_222135.csv"
GT_MORPH_CSV = REPORT_DIR / "oty2_gt_anchored_energy_morphology_20260703_222135.csv"
REVIEW_CANDIDATE_CSV = REPORT_DIR / "oty2_gt_quality_visual_review_candidates_20260703_222135.csv"
FAILED_ATLAS = VISUAL_DIR / "oty2_physical_shell_grammar_temporal_drift_atlas_cn_20260704_143456.html"

BOUNDARY_FLAGS = {
    "previous_physical_atlas_marked_failed": True,
    "gt_local_energy_field_atlas_generated": True,
    "gt_crop_primary_coordinate_frame": True,
    "support_internal_components_drawn_as_vehicle_parts": False,
    "small_component_boxes_drawn_as_shell": False,
    "support_boundary_drawn": False,
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "annotation_proposal_entered": False,
    "revised_gt_box_output": False,
    "final_candidate_box_output": False,
    "selector_or_ranking_used": False,
    "training_or_threshold_tuning_entered": False,
    "identity_truth_claimed": False,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "archive_or_old_work_used_as_active_source": False,
    "zip_7z_rar_committed": False,
}

FAILED_FIELDS = [
    "artifact_path",
    "status",
    "failure_reason",
    "do_not_use_as",
    "corrected_visualization",
]

FEATURE_FIELDS = [
    "review_id",
    "gt_id",
    "case_id",
    "scene",
    "sar_frame",
    "pool_type",
    "gt_quality_label",
    "image_available",
    "gt_crop_primary_coordinate_frame",
    "gt_local_width_px",
    "gt_local_height_px",
    "ridge_like_energy_band",
    "ridge_band_mean",
    "ridge_band_occupancy",
    "opposite_side",
    "weak_opposite_side_return",
    "weak_opposite_side_mean",
    "endpoint_hotspot_count",
    "endpoint_hotspot_summary",
    "boundary_occupancy",
    "vehicle_scale_shell_contour",
    "shell_contour_span_x_ratio",
    "shell_contour_span_y_ratio",
    "support_internal_components_drawn",
    "small_component_boxes_drawn_as_shell",
    "posthoc_only",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def compact_counts(values: Sequence[Any]) -> str:
    counts = Counter(str(value) for value in values if str(value) != "")
    return ";".join(f"{key}={value}" for key, value in counts.most_common())


def fmt(value: float, ndigits: int = 4) -> str:
    if not math.isfinite(float(value)):
        return ""
    text = f"{float(value):.{ndigits}f}"
    return text.rstrip("0").rstrip(".")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_image_gray(path_text: str) -> np.ndarray | None:
    path = Path(str(path_text or ""))
    if not path.exists():
        return None
    try:
        with Image.open(path) as image:
            return np.asarray(image.convert("L"), dtype=np.float32)
    except OSError:
        return None


def key(scene: Any, sar_frame: Any, gt_id: Any) -> tuple[str, str, str]:
    return (str(scene), str(sar_frame), str(gt_id))


def sample_gt_local(arr: np.ndarray, box: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    w = max(8.0, float(box["w"]))
    h = max(8.0, float(box["h"]))
    nx = int(min(240, max(96, round(w))))
    ny = int(min(160, max(56, round(h))))
    local_x = np.linspace(-w / 2.0, w / 2.0, nx, dtype=np.float32)
    local_y = np.linspace(-h / 2.0, h / 2.0, ny, dtype=np.float32)
    xx, yy = np.meshgrid(local_x, local_y)
    angle = math.radians(float(box.get("heading", 0.0)))
    ca = math.cos(angle)
    sa = math.sin(angle)
    img_x = float(box["cx"]) + ca * xx - sa * yy
    img_y = float(box["cy"]) + sa * xx + ca * yy
    sampled = ndimage.map_coordinates(arr, [img_y, img_x], order=1, mode="nearest")
    return sampled.astype(np.float32), local_x, local_y


def normalize(field: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(field, [2, 99])
    if hi <= lo:
        return np.zeros_like(field, dtype=np.float32)
    return np.clip((field - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def side_masks(shape: tuple[int, int]) -> dict[str, np.ndarray]:
    ny, nx = shape
    y_band = max(4, int(round(ny * 0.16)))
    x_band = max(4, int(round(nx * 0.16)))
    masks = {
        "upper": np.zeros(shape, dtype=bool),
        "lower": np.zeros(shape, dtype=bool),
        "left": np.zeros(shape, dtype=bool),
        "right": np.zeros(shape, dtype=bool),
    }
    masks["upper"][:y_band, :] = True
    masks["lower"][-y_band:, :] = True
    masks["left"][:, :x_band] = True
    masks["right"][:, -x_band:] = True
    return masks


def opposite_side(side: str) -> str:
    return {"upper": "lower", "lower": "upper", "left": "right", "right": "left"}.get(side, "uncertain")


def side_metrics(norm: np.ndarray) -> dict[str, dict[str, float]]:
    high = norm >= float(np.percentile(norm, 85))
    metrics: dict[str, dict[str, float]] = {}
    for name, mask in side_masks(norm.shape).items():
        metrics[name] = {
            "mean": float(norm[mask].mean()) if mask.any() else 0.0,
            "occupancy": float(high[mask].mean()) if mask.any() else 0.0,
        }
    return metrics


def endpoint_hotspots(norm: np.ndarray, max_points: int = 6) -> list[tuple[float, float, float]]:
    ny, nx = norm.shape
    endpoint = np.zeros_like(norm, dtype=bool)
    if nx >= ny:
        band = max(5, int(round(nx * 0.22)))
        endpoint[:, :band] = True
        endpoint[:, -band:] = True
    else:
        band = max(5, int(round(ny * 0.22)))
        endpoint[:band, :] = True
        endpoint[-band:, :] = True
    mask = (norm >= float(np.percentile(norm, 97))) & endpoint
    labels, count = ndimage.label(mask)
    spots: list[tuple[float, float, float]] = []
    for label in range(1, count + 1):
        yy, xx = np.where(labels == label)
        if yy.size < 2:
            continue
        energy = float(norm[yy, xx].mean())
        spots.append((float(xx.mean()), float(yy.mean()), energy))
    spots.sort(key=lambda item: item[2], reverse=True)
    return spots[:max_points]


def shell_contour_status(norm: np.ndarray) -> tuple[str, float, float, str]:
    smooth = ndimage.gaussian_filter(norm, sigma=1.4)
    threshold = float(np.percentile(smooth, 72))
    mask = smooth >= threshold
    labels, count = ndimage.label(mask)
    if count <= 0:
        return "no", 0.0, 0.0, "no energy-field contour available"
    best_label = max(range(1, count + 1), key=lambda label: int((labels == label).sum()))
    yy, xx = np.where(labels == best_label)
    if yy.size == 0:
        return "no", 0.0, 0.0, "no contour pixels"
    span_x = (float(xx.max() - xx.min() + 1) / max(1, norm.shape[1]))
    span_y = (float(yy.max() - yy.min() + 1) / max(1, norm.shape[0]))
    if span_x >= 0.55 and span_y >= 0.30:
        return "yes", span_x, span_y, "largest GT-local energy contour spans vehicle-scale crop extent"
    if span_x >= 0.35 and span_y >= 0.20:
        return "uncertain", span_x, span_y, "contour spans a partial body-scale field but needs review"
    return "no", span_x, span_y, "contour is too local and must not be called shell"


def boundary_occupancy(norm: np.ndarray) -> float:
    masks = side_masks(norm.shape)
    boundary = masks["upper"] | masks["lower"] | masks["left"] | masks["right"]
    high = norm >= float(np.percentile(norm, 85))
    return float(high[boundary].mean()) if boundary.any() else 0.0


def render_panel(
    idx: int,
    feature: Mapping[str, Any],
    norm: np.ndarray,
    output_path: Path,
) -> None:
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    metrics = side_metrics(norm)
    dominant = str(feature["ridge_like_energy_band"])
    opposite = str(feature["opposite_side"])
    spots = endpoint_hotspots(norm)
    smooth = ndimage.gaussian_filter(norm, sigma=1.4)
    contour_level = float(np.percentile(smooth, 72))
    fig = plt.figure(figsize=(13, 8), dpi=130)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.3, 0.9], height_ratios=[1.0, 0.7])
    ax = fig.add_subplot(gs[:, 0])
    ax_profile = fig.add_subplot(gs[0, 1])
    ax_text = fig.add_subplot(gs[1, 1])
    ax.imshow(norm, cmap="gray", origin="upper", vmin=0, vmax=1)
    ax.set_title(f"{idx:02d} GT-local energy field | {feature['case_id']}", fontsize=10)
    ax.set_xlabel("GT-local x")
    ax.set_ylabel("GT-local y")
    ny, nx = norm.shape
    y_band = max(4, int(round(ny * 0.16)))
    x_band = max(4, int(round(nx * 0.16)))
    band_rects = {
        "upper": (0, 0, nx, y_band),
        "lower": (0, ny - y_band, nx, y_band),
        "left": (0, 0, x_band, ny),
        "right": (nx - x_band, 0, x_band, ny),
    }
    for name, (x, y, w, h) in band_rects.items():
        if name == dominant:
            color = "#00d5ff"
            alpha = 0.28
            linestyle = "-"
            linewidth = 2.0
        elif name == opposite:
            color = "#ffcc33"
            alpha = 0.18
            linestyle = "--"
            linewidth = 1.8
        else:
            color = "#66ff99"
            alpha = 0.08
            linestyle = ":"
            linewidth = 1.0
        ax.add_patch(Rectangle((x, y), w, h, fill=True, facecolor=color, edgecolor=color, alpha=alpha, linestyle=linestyle, linewidth=linewidth))
    if feature["vehicle_scale_shell_contour"] != "no":
        ax.contour(smooth, levels=[contour_level], colors=["#ff7a00"], linewidths=2.0)
    else:
        ax.contour(smooth, levels=[contour_level], colors=["#ff7a00"], linewidths=1.0, linestyles="dashed")
    for x, y, energy in spots:
        radius = 5 + 5 * energy
        ax.add_patch(Circle((x, y), radius=radius, fill=False, edgecolor="#ff2ad4", linewidth=1.8))
    ax.text(
        0.01,
        0.99,
        "GT crop primary frame\nno support components\nno small component boxes",
        transform=ax.transAxes,
        va="top",
        ha="left",
        color="white",
        fontsize=8,
        bbox={"facecolor": "black", "alpha": 0.45, "pad": 3},
    )

    side_names = ["upper", "lower", "left", "right"]
    means = [metrics[name]["mean"] for name in side_names]
    occs = [metrics[name]["occupancy"] for name in side_names]
    xs = np.arange(len(side_names))
    ax_profile.bar(xs - 0.18, means, width=0.36, label="mean", color="#56b4e9")
    ax_profile.bar(xs + 0.18, occs, width=0.36, label="occupancy", color="#e69f00")
    ax_profile.set_xticks(xs, side_names, rotation=20)
    ax_profile.set_ylim(0, max(0.05, min(1.0, max(means + occs) * 1.25)))
    ax_profile.set_title("GT-boundary energy bands", fontsize=9)
    ax_profile.legend(fontsize=8)

    text = (
        "本图为 corrected GT-local energy-field atlas。\n"
        "主坐标系是 SAR GT crop；不画 support；不画 GT 外 support component；不把小 component box 画成 shell。\n"
        f"ridge-like band: {feature['ridge_like_energy_band']} / occupancy {feature['ridge_band_occupancy']}\n"
        f"endpoint hotspots: {feature['endpoint_hotspot_count']} ({feature['endpoint_hotspot_summary']})\n"
        f"weak opposite-side return: {feature['weak_opposite_side_return']} ({feature['opposite_side']})\n"
        f"boundary occupancy: {feature['boundary_occupancy']}\n"
        f"vehicle-scale shell contour: {feature['vehicle_scale_shell_contour']} "
        f"span=({feature['shell_contour_span_x_ratio']}, {feature['shell_contour_span_y_ratio']})\n"
        "仍是 posthoc SAR morphology observation，不是 revised GT、final box、selector 或 identity truth。"
    )
    ax_text.set_axis_off()
    ax_text.text(0.0, 1.0, wrap_zh(text, 34), va="top", ha="left", fontproperties=FONT, fontsize=10, linespacing=1.3)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def select_review_rows(review_rows: Sequence[Mapping[str, str]], limit: int) -> list[Mapping[str, str]]:
    selected = [row for row in review_rows if row.get("gt_id") and row.get("case_id")][:limit]
    return selected


def build_feature(
    review: Mapping[str, str],
    source: Mapping[str, str],
    quality_by_key: Mapping[tuple[str, str, str], Mapping[str, str]],
    morph_by_key: Mapping[tuple[str, str, str], Mapping[str, str]],
) -> tuple[dict[str, Any], np.ndarray | None]:
    gt_id = str(review.get("gt_id", ""))
    scene = str(review.get("scene", ""))
    sar_frame = str(review.get("sar_frame", ""))
    item_key = key(scene, sar_frame, gt_id)
    box = gt_box_from_accounting(source)
    image_path = str(source.get("sar_pseudocolor_path", ""))
    arr = read_image_gray(image_path)
    quality = quality_by_key.get(item_key, {})
    morph = morph_by_key.get(item_key, {})
    base = {
        "review_id": review.get("review_id", ""),
        "gt_id": gt_id,
        "case_id": review.get("case_id", ""),
        "scene": scene,
        "sar_frame": sar_frame,
        "pool_type": morph.get("pool_type", source.get("match_status", "")),
        "gt_quality_label": quality.get("gt_quality_label", morph.get("gt_quality_label", "")),
        "image_available": "yes" if arr is not None else "no",
        "gt_crop_primary_coordinate_frame": "yes",
        "support_internal_components_drawn": "no",
        "small_component_boxes_drawn_as_shell": "no",
        "posthoc_only": "yes",
        "notes": "Corrected GT-local field: no support-internal components, no small component boxes, no final box.",
    }
    if arr is None or not box_available(box):
        base.update(
            {
                "gt_local_width_px": "",
                "gt_local_height_px": "",
                "ridge_like_energy_band": "unavailable",
                "ridge_band_mean": "",
                "ridge_band_occupancy": "",
                "opposite_side": "unavailable",
                "weak_opposite_side_return": "unavailable",
                "weak_opposite_side_mean": "",
                "endpoint_hotspot_count": 0,
                "endpoint_hotspot_summary": "",
                "boundary_occupancy": "",
                "vehicle_scale_shell_contour": "unavailable",
                "shell_contour_span_x_ratio": "",
                "shell_contour_span_y_ratio": "",
            }
        )
        return base, None
    field, _, _ = sample_gt_local(arr, box)
    norm = normalize(field)
    metrics = side_metrics(norm)
    dominant = max(metrics, key=lambda name: metrics[name]["mean"])
    opposite = opposite_side(dominant)
    opp_mean = metrics.get(opposite, {}).get("mean", 0.0)
    interior = norm.copy()
    boundary_mask = np.zeros_like(norm, dtype=bool)
    for mask in side_masks(norm.shape).values():
        boundary_mask |= mask
    interior_mean = float(interior[~boundary_mask].mean()) if (~boundary_mask).any() else float(norm.mean())
    weak_return = "yes" if opp_mean >= interior_mean * 0.85 and metrics[opposite]["occupancy"] > 0.03 else "uncertain"
    spots = endpoint_hotspots(norm)
    shell_status, span_x, span_y, shell_reason = shell_contour_status(norm)
    base.update(
        {
            "gt_local_width_px": norm.shape[1],
            "gt_local_height_px": norm.shape[0],
            "ridge_like_energy_band": dominant,
            "ridge_band_mean": fmt(metrics[dominant]["mean"]),
            "ridge_band_occupancy": fmt(metrics[dominant]["occupancy"]),
            "opposite_side": opposite,
            "weak_opposite_side_return": weak_return,
            "weak_opposite_side_mean": fmt(opp_mean),
            "endpoint_hotspot_count": len(spots),
            "endpoint_hotspot_summary": ";".join(f"x={fmt(x,1)},y={fmt(y,1)},e={fmt(e,2)}" for x, y, e in spots[:4]),
            "boundary_occupancy": fmt(boundary_occupancy(norm)),
            "vehicle_scale_shell_contour": shell_status,
            "shell_contour_span_x_ratio": fmt(span_x),
            "shell_contour_span_y_ratio": fmt(span_y),
            "notes": f"{base['notes']} {shell_reason}",
        }
    )
    return base, norm


def render_report(path: Path, summary: Mapping[str, Any]) -> None:
    km = summary["key_metrics"]
    lines = [
        "# OTY2 Corrected GT-Local Energy-Field Atlas Report",
        "",
        f"Generated: `{summary['timestamp']}`",
        "",
        "This report marks the previous physical shell grammar atlas as failed visualization and replaces it with a GT-local energy-field atlas. The corrected atlas uses the SAR GT crop as the primary coordinate frame.",
        "",
        "## Failed Visualization Mark",
        "",
        f"- failed artifact: `{FAILED_ATLAS}`",
        "- status: `failed_visualization`",
        "- reason: the previous atlas still visualized support-internal peaks/components and small component boxes, so it could still imply baby-car shells.",
        "- do not use as: vehicle shell evidence, selector evidence, final box evidence, or identity truth.",
        "",
        "## Corrected GT-Local Atlas",
        "",
        f"- atlas panels generated: `{km['atlas_panels_generated']}`",
        f"- feature rows: `{km['feature_rows']}`",
        f"- ridge-like band mix: `{km['ridge_band_mix']}`",
        f"- weak opposite-side return mix: `{km['weak_opposite_side_return_mix']}`",
        f"- vehicle-scale shell contour mix: `{km['vehicle_scale_shell_contour_mix']}`",
        f"- endpoint hotspot count mix: `{km['endpoint_hotspot_count_mix']}`",
        "",
        "The corrected atlas displays only GT-local energy cues: ridge-like energy bands, endpoint hotspots, weak opposite-side returns, boundary occupancy, and energy-field contours inside GT.",
        "",
        "## Visualization Contract",
        "",
        "- GT crop is the primary coordinate frame.",
        "- No support boundary is drawn.",
        "- No support-internal component outside GT is drawn as a vehicle part.",
        "- No small component box is drawn as shell.",
        "- Vehicle-scale shell contour is an energy-field contour inside GT, not a component box and not a final box.",
        "",
        "## Boundary Flags",
        "",
    ]
    lines.extend(f"- {key}: `{str(value).lower()}`" for key, value in BOUNDARY_FLAGS.items())
    lines.extend(["", "## Outputs", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in summary["outputs"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--limit", type=int, default=18)
    args = parser.parse_args()
    timestamp = args.timestamp

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORKSPACE_LOG_DIR / f"oty2_gt_local_energy_field_atlas_{timestamp}.log"
    log_path.write_text(
        f"timestamp={timestamp}\n"
        "task=oty2_gt_local_energy_field_atlas\n"
        "phase=before_run\n"
        r"interpreter=D:\MINICONDA\envs\py311\python.exe" + "\n"
        "old_work_dependency=false\narchive_directory_active_source=false\n",
        encoding="utf-8",
    )

    accounting_rows = read_csv(GT_ACCOUNTING_CSV)
    quality_rows = read_csv(GT_QUALITY_CSV)
    morph_rows = read_csv(GT_MORPH_CSV)
    review_rows = read_csv(REVIEW_CANDIDATE_CSV)
    accounting_by_key = {
        key(row.get("scene"), row.get("sar_frame"), row.get("sar_gt_id")): row for row in accounting_rows
    }
    quality_by_key = {
        key(row.get("scene"), row.get("sar_frame"), row.get("gt_id")): row for row in quality_rows
    }
    morph_by_key = {
        key(row.get("scene"), row.get("sar_frame"), row.get("gt_id")): row for row in morph_rows
    }

    failed_rows = [
        {
            "artifact_path": str(FAILED_ATLAS),
            "status": "failed_visualization",
            "failure_reason": "Still visualizes support-internal peaks/components and small component boxes; can imply baby-car shells.",
            "do_not_use_as": "vehicle shell evidence; selector evidence; final box evidence; identity truth",
            "corrected_visualization": "GT-local energy-field atlas with GT crop as primary coordinate frame",
        }
    ]

    feature_rows: list[dict[str, Any]] = []
    panel_paths: list[Path] = []
    html_sections: list[str] = []
    for idx, review in enumerate(select_review_rows(review_rows, args.limit), 1):
        source = accounting_by_key.get(key(review.get("scene"), review.get("sar_frame"), review.get("gt_id")))
        if not source:
            continue
        feature, norm = build_feature(review, source, quality_by_key, morph_by_key)
        feature_rows.append(feature)
        if norm is None:
            continue
        panel_path = VISUAL_DIR / f"{idx:02d}_{sanitize(feature['case_id'])}_gt_local_energy_field_cn.png"
        render_panel(idx, feature, norm, panel_path)
        panel_paths.append(panel_path)
        html_sections.append(
            f"<section><h2>{idx:02d} {html.escape(str(feature['case_id']))}</h2>"
            f"<p>Corrected GT-local energy-field view. No support components or small component boxes are drawn.</p>"
            f"<img src=\"{html.escape(panel_path.name)}\" style=\"max-width:100%;border:1px solid #ccc\"></section>"
        )

    atlas_path = VISUAL_DIR / f"oty2_gt_local_energy_field_atlas_cn_{timestamp}.html"
    atlas_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>OTY2 GT-local energy-field atlas</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.5}section{margin-bottom:32px}</style></head><body>"
        "<h1>OTY2 Corrected GT-Local Energy-Field Atlas</h1>"
        "<p>The previous physical shell grammar atlas is marked as failed visualization. This corrected atlas uses GT crop as the primary coordinate frame and draws no support-internal components or small component boxes.</p>"
        + "\n".join(html_sections)
        + "</body></html>",
        encoding="utf-8",
    )

    outputs = {
        "correction_archive_doc": str(DOCS_DIR / "oty2_gt_local_energy_field_atlas_correction_archive.md"),
        "failed_visualization_correction_csv": str(REPORT_DIR / f"oty2_failed_visualization_correction_{timestamp}.csv"),
        "gt_local_energy_field_features_csv": str(REPORT_DIR / f"oty2_gt_local_energy_field_features_{timestamp}.csv"),
        "report_md": str(REPORT_DIR / f"oty2_gt_local_energy_field_atlas_report_{timestamp}.md"),
        "summary_json": str(REPORT_DIR / f"oty2_gt_local_energy_field_atlas_summary_{timestamp}.json"),
        "visual_atlas_html": str(atlas_path),
        "workspace_log": str(log_path),
    }
    write_csv(Path(outputs["failed_visualization_correction_csv"]), FAILED_FIELDS, failed_rows)
    write_csv(Path(outputs["gt_local_energy_field_features_csv"]), FEATURE_FIELDS, feature_rows)

    key_metrics = {
        "feature_rows": len(feature_rows),
        "atlas_panels_generated": len(panel_paths),
        "ridge_band_mix": compact_counts(row.get("ridge_like_energy_band") for row in feature_rows),
        "weak_opposite_side_return_mix": compact_counts(row.get("weak_opposite_side_return") for row in feature_rows),
        "vehicle_scale_shell_contour_mix": compact_counts(row.get("vehicle_scale_shell_contour") for row in feature_rows),
        "endpoint_hotspot_count_mix": compact_counts(row.get("endpoint_hotspot_count") for row in feature_rows),
        "support_internal_components_drawn": "no",
        "small_component_boxes_drawn_as_shell": "no",
        "previous_physical_atlas_status": "failed_visualization",
    }
    summary = {
        "timestamp": timestamp,
        "failed_visualization": failed_rows[0],
        "key_metrics": key_metrics,
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "atlas_panels": [str(path) for path in panel_paths],
        "sources": {
            "gt_accounting_csv": str(GT_ACCOUNTING_CSV),
            "gt_quality_csv": str(GT_QUALITY_CSV),
            "gt_morphology_csv": str(GT_MORPH_CSV),
            "review_candidate_csv": str(REVIEW_CANDIDATE_CSV),
        },
    }
    render_report(Path(outputs["report_md"]), summary)
    write_json(Path(outputs["summary_json"]), summary)
    log_path.write_text(
        log_path.read_text(encoding="utf-8")
        + "phase=after_run\n"
        + "repo_outputs_written=true\n"
        + "key_metrics="
        + json.dumps(key_metrics, ensure_ascii=False)
        + "\n"
        + "boundary_flags="
        + json.dumps(BOUNDARY_FLAGS, ensure_ascii=False)
        + "\n"
        + "outputs="
        + json.dumps(outputs, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"timestamp": timestamp, "key_metrics": key_metrics, "outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
